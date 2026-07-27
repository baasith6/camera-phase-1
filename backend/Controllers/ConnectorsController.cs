using System.Security.Cryptography;
using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;
using Onevo.Api.Services;

namespace Onevo.Api.Controllers;

[ApiController]
[Route("api/connectors")]
public class ConnectorsController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly IConfiguration _cfg;
    private readonly ConnectorInstallerService _installer;
    private readonly CameraProvisioningService _cameraProvisioning;

    public ConnectorsController(
        OnevoDbContext db,
        IConfiguration cfg,
        ConnectorInstallerService installer,
        CameraProvisioningService cameraProvisioning)
    {
        _db = db;
        _cfg = cfg;
        _installer = installer;
        _cameraProvisioning = cameraProvisioning;
    }

    // Connector self-registration using the shared bootstrap key. Returns a per-connector API key
    // (shown once). Only a scoped key is stored (hashed) - never broad storage credentials.
    [AllowAnonymous]
    [HttpPost("register")]
    public async Task<ActionResult<RegisterConnectorResponse>> Register(RegisterConnectorRequest req)
    {
        var bootstrap = _cfg["Seed:ConnectorBootstrapKey"];
        if (string.IsNullOrEmpty(bootstrap) || req.BootstrapKey != bootstrap)
            return Unauthorized(new { error = "Invalid bootstrap key" });
        if (!await _db.Stores.AnyAsync(s => s.Id == req.StoreId))
            return BadRequest(new { error = "Unknown store" });

        var apiKey = Convert.ToHexString(RandomNumberGenerator.GetBytes(24));
        var connector = new Connector
        {
            StoreId = req.StoreId,
            Name = string.IsNullOrWhiteSpace(req.Name) ? "edge-connector-1" : req.Name.Trim(),
            Version = req.Version,
            ApiKeyHash = BCrypt.Net.BCrypt.HashPassword(apiKey),
            Status = ConnectorStatus.Healthy,
            LastHeartbeat = DateTimeOffset.UtcNow
        };
        _db.Connectors.Add(connector);
        await _db.SaveChangesAsync();

        return new RegisterConnectorResponse(connector.Id, apiKey);
    }

    /// <summary>Claim a short-lived setup code from the dashboard wizard.</summary>
    [AllowAnonymous]
    [EnableRateLimiting("connector-claim")]
    [HttpPost("claim")]
    public async Task<ActionResult<ClaimSetupCodeResponse>> Claim(ClaimSetupCodeRequest req)
    {
        var code = (req.SetupCode ?? "").Trim().ToUpperInvariant();
        if (string.IsNullOrWhiteSpace(code))
            return BadRequest(new { error = "setupCode is required" });

        var lookup = ComputeSetupCodeLookup(code);
        var now = DateTimeOffset.UtcNow;
        await using var transaction = await _db.Database.BeginTransactionAsync(
            HttpContext.RequestAborted);
        var row = await _db.ConnectorSetupCodes
            .SingleOrDefaultAsync(
                c => c.CodeLookup == lookup && c.UsedAt == null && c.ExpiresAt >= now,
                HttpContext.RequestAborted);
        if (row is null || !BCrypt.Net.BCrypt.Verify(code, row.CodeHash))
            return BadRequest(new { error = "Invalid, used, or expired setup code" });

        var name = string.IsNullOrWhiteSpace(req.Name) ? "edge-connector-1" : req.Name.Trim();
        var version = string.IsNullOrWhiteSpace(req.Version) ? "1.0.0" : req.Version.Trim();
        var apiKey = Convert.ToHexString(RandomNumberGenerator.GetBytes(24));
        var claimed = await _db.ConnectorSetupCodes
            .Where(c => c.Id == row.Id && c.UsedAt == null && c.ExpiresAt >= now)
            .ExecuteUpdateAsync(
                setters => setters.SetProperty(c => c.UsedAt, now),
                HttpContext.RequestAborted);
        if (claimed != 1)
            return BadRequest(new { error = "Invalid, used, or expired setup code" });

        var connector = new Connector
        {
            StoreId = row.StoreId,
            Name = name,
            Version = version,
            ApiKeyHash = BCrypt.Net.BCrypt.HashPassword(apiKey),
            Status = ConnectorStatus.Healthy,
            LastHeartbeat = now
        };
        _db.Connectors.Add(connector);
        await _db.SaveChangesAsync(HttpContext.RequestAborted);
        await transaction.CommitAsync(HttpContext.RequestAborted);

        return new ClaimSetupCodeResponse(connector.Id, apiKey, row.StoreId);
    }

    /// <summary>Generate a one-time setup code for the Windows installer wizard.</summary>
    [Authorize(Roles = "Admin")]
    [HttpPost("setup-codes")]
    public async Task<ActionResult<CreateSetupCodeResponse>> CreateSetupCode(CreateSetupCodeRequest req)
    {
        if (!await _db.Stores.AnyAsync(s => s.Id == req.StoreId))
            return BadRequest(new { error = "Unknown store" });

        var code = ConnectorInstallerService.GenerateSetupCode();
        var userId = User.FindFirstValue("uid");
        if (!Guid.TryParse(userId, out var createdBy))
            return Unauthorized();

        var row = new ConnectorSetupCode
        {
            StoreId = req.StoreId,
            CodeLookup = ComputeSetupCodeLookup(code),
            CodeHash = BCrypt.Net.BCrypt.HashPassword(code),
            ExpiresAt = DateTimeOffset.UtcNow.AddHours(24),
            CreatedBy = createdBy
        };
        _db.ConnectorSetupCodes.Add(row);
        await _db.SaveChangesAsync();
        return new CreateSetupCodeResponse(code, row.StoreId, row.ExpiresAt);
    }

    [AllowAnonymous]
    [HttpPost("heartbeat")]
    public async Task<IActionResult> Heartbeat(HeartbeatRequest req)
    {
        var connector = await AuthConnectorAsync();
        if (connector is null) return Unauthorized();

        connector.DiskFreePct = req.DiskFreePct;
        connector.UploadQueueDepth = req.UploadQueueDepth;
        connector.DegradedReason = req.DegradedReason;
        connector.Version = req.Version;
        connector.LastHeartbeat = DateTimeOffset.UtcNow;
        connector.Status = req.DegradedReason is null ? ConnectorStatus.Healthy : ConnectorStatus.Degraded;
        await _db.SaveChangesAsync();
        return Ok(new { ok = true });
    }

    // Health list for the dashboard.
    [Authorize]
    [HttpGet]
    public async Task<IActionResult> List([FromQuery] Guid? storeId)
    {
        var q = _db.Connectors.AsQueryable();
        if (storeId is not null) q = q.Where(c => c.StoreId == storeId);
        return Ok(await q.OrderBy(c => c.Name).ToListAsync());
    }

    // Connector fetches its assigned cameras.
    [AllowAnonymous]
    [HttpGet("cameras")]
    public async Task<IActionResult> GetCameras()
    {
        var connector = await AuthConnectorAsync();
        if (connector is null) return Unauthorized();

        var hasAssignedCameras = await _db.Cameras
            .AnyAsync(c => c.StoreId == connector.StoreId && c.ConnectorId == connector.Id);

        // Self-heal MP4 cameras created by installer versions that predate
        // automatic demo-zone provisioning. Real RTSP/ONVIF cameras are untouched.
        var testVideoCameras = await _db.Cameras
            .Include(c => c.Zones)
            .Where(c => c.StoreId == connector.StoreId &&
                        c.ConnectorId == connector.Id &&
                        c.RtspUrl.StartsWith("file://"))
            .ToListAsync(HttpContext.RequestAborted);
        await _cameraProvisioning.EnsureDemoZonesAsync(
            testVideoCameras,
            HttpContext.RequestAborted);

        var cameras = await _db.Cameras
            .Where(c => c.StoreId == connector.StoreId &&
                        (hasAssignedCameras ? c.ConnectorId == connector.Id : c.ConnectorId == null))
            .OrderBy(c => c.Name)
            .Select(c => new
            {
                c.Id,
                c.Name,
                c.RtspUrl,
                c.OnvifHost,
                c.OnvifPort,
                c.Status
            })
            .ToListAsync();

        return Ok(cameras);
    }

    /// <summary>Wizard creates cameras for the connector's store.</summary>
    [AllowAnonymous]
    [HttpPost("cameras")]
    public async Task<IActionResult> CreateCamera(ConnectorCreateCameraRequest req)
    {
        var connector = await AuthConnectorAsync();
        if (connector is null) return Unauthorized();
        if (string.IsNullOrWhiteSpace(req.Name))
            return BadRequest(new { error = "name is required" });
        if (!TryValidateCameraUrl(req.RtspUrl, out var urlError))
            return BadRequest(new { error = urlError });

        var cam = await _cameraProvisioning.ProvisionConnectorCameraAsync(
            connector,
            req.Name,
            req.RtspUrl,
            req.OnvifHost,
            req.OnvifPort,
            req.UseDemoZones,
            HttpContext.RequestAborted);
        return Ok(cam);
    }

    /// <summary>Installer metadata (version / size / sha256). File must exist on disk.</summary>
    [Authorize(Roles = "Admin,Manager,Installer")]
    [HttpGet("installer")]
    public ActionResult<InstallerInfoResponse> InstallerInfo()
    {
        if (!_installer.TryGetInfo(out _, out var size, out var sha))
            return NotFound(new { error = "Installer not found. Build ONEVO-Connector-Setup and set ConnectorInstaller:Path." });

        return new InstallerInfoResponse(
            _installer.Version,
            _installer.FileName,
            size,
            sha,
            "/api/connectors/installer/download");
    }

    /// <summary>Download the Windows setup EXE.</summary>
    [Authorize(Roles = "Admin,Manager,Installer")]
    [HttpGet("installer/download")]
    public IActionResult DownloadInstaller()
    {
        if (!_installer.TryGetInfo(out var path, out _, out _))
            return NotFound(new { error = "Installer not found" });

        return PhysicalFile(path, "application/octet-stream", _installer.FileName);
    }

    private async Task<Connector?> AuthConnectorAsync()
    {
        if (!Request.Headers.TryGetValue("X-Connector-Id", out var idVal) ||
            !Request.Headers.TryGetValue("X-Connector-Key", out var keyVal))
            return null;
        if (!Guid.TryParse(idVal, out var id)) return null;

        var connector = await _db.Connectors.FindAsync(id);
        if (connector is null) return null;
        return BCrypt.Net.BCrypt.Verify(keyVal.ToString(), connector.ApiKeyHash) ? connector : null;
    }

    private string ComputeSetupCodeLookup(string code)
    {
        var key = _cfg["ConnectorInstaller:SetupCodeLookupKey"];
        if (string.IsNullOrWhiteSpace(key))
            throw new InvalidOperationException(
                "ConnectorInstaller:SetupCodeLookupKey must be configured");
        using var hmac = new HMACSHA256(System.Text.Encoding.UTF8.GetBytes(key));
        return Convert.ToHexString(hmac.ComputeHash(System.Text.Encoding.UTF8.GetBytes(code)));
    }

    private static bool TryValidateCameraUrl(string? value, out string error)
    {
        error = "rtspUrl must be an absolute rtsp:// or file:// URL";
        if (string.IsNullOrWhiteSpace(value) ||
            !Uri.TryCreate(value.Trim(), UriKind.Absolute, out var uri))
            return false;
        return uri.Scheme.Equals("rtsp", StringComparison.OrdinalIgnoreCase) ||
               uri.Scheme.Equals("file", StringComparison.OrdinalIgnoreCase);
    }
}
