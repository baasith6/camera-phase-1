using System.Security.Cryptography;
using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Auth;
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
    private readonly ConnectorAuthenticationService _connectorAuth;
    private readonly ConnectorPairingService _pairing;

    public ConnectorsController(
        OnevoDbContext db,
        IConfiguration cfg,
        ConnectorInstallerService installer,
        CameraProvisioningService cameraProvisioning,
        ConnectorAuthenticationService connectorAuth,
        ConnectorPairingService pairing)
    {
        _db = db;
        _cfg = cfg;
        _installer = installer;
        _cameraProvisioning = cameraProvisioning;
        _connectorAuth = connectorAuth;
        _pairing = pairing;
    }

    // Connector self-registration using the shared bootstrap key. Returns a per-connector API key
    // (shown once). Only a scoped key is stored (hashed) â€” never broad storage credentials.
    [AllowAnonymous]
    [HttpPost("register")]
    public async Task<ActionResult<RegisterConnectorResponse>> Register(RegisterConnectorRequest req)
    {
        var bootstrap = ServiceAuth.ConnectorBootstrapKey(_cfg);
        if (!ServiceAuth.ValidateBootstrapKey(_cfg, req.BootstrapKey))
            return Unauthorized(new { error = "Invalid bootstrap key" });
        if (!await _db.Stores.AnyAsync(s => s.Id == req.StoreId))
            return BadRequest(new { error = "Unknown store" });

        var (connector, apiKey) = await _pairing.PairAsync(
            req.StoreId, req.Name, req.Version,
            ct: HttpContext.RequestAborted);

        return new RegisterConnectorResponse(connector.Id, apiKey);
    }

    /// <summary>Claim a short-lived setup code from the dashboard wizard.</summary>
    [AllowAnonymous]
    [HttpPost("claim")]
    public async Task<ActionResult<ClaimSetupCodeResponse>> Claim(ClaimSetupCodeRequest req)
    {
        var code = (req.SetupCode ?? "").Trim().ToUpperInvariant();
        if (string.IsNullOrWhiteSpace(code))
            return BadRequest(new { error = "setupCode is required" });

        var candidates = await _db.ConnectorSetupCodes
            .Where(c => c.UsedAt == null && c.ExpiresAt >= DateTimeOffset.UtcNow)
            .ToListAsync();
        var row = candidates.FirstOrDefault(c => BCrypt.Net.BCrypt.Verify(code, c.CodeHash));
        if (row is null)
            return BadRequest(new { error = "Invalid, used, or expired setup code" });

        // A store owns one connector identity. Do not let a second PC claim a
        // code and rotate the active shop connector's API key. Re-pairing is
        // allowed only after uninstall/offline timeout.
        var activeCutoff = DateTimeOffset.UtcNow.AddMinutes(-2);
        var activeConnector = await _db.Connectors
            .AsNoTracking()
            .AnyAsync(c =>
                c.StoreId == row.StoreId &&
                c.LastHeartbeat >= activeCutoff &&
                (c.Status == ConnectorStatus.Healthy ||
                 c.Status == ConnectorStatus.Degraded),
                HttpContext.RequestAborted);
        if (activeConnector)
            return Conflict(new {
                error = "This store already has an active connector. Uninstall or stop it before pairing another PC."
            });

        await using var transaction = await _db.Database.BeginTransactionAsync(
            HttpContext.RequestAborted);

        // Consume the code before pairing. The conditional update is atomic, so a
        // concurrent claimant can never receive a second connector key.
        var consumed = await _db.ConnectorSetupCodes
            .Where(c => c.Id == row.Id &&
                        c.UsedAt == null &&
                        c.ExpiresAt >= DateTimeOffset.UtcNow)
            .ExecuteUpdateAsync(
                setters => setters.SetProperty(c => c.UsedAt, DateTimeOffset.UtcNow),
                HttpContext.RequestAborted);
        if (consumed != 1)
            return BadRequest(new { error = "Invalid, used, or expired setup code" });

        var (connector, apiKey) = await _pairing.PairAsync(
            row.StoreId, req.Name, req.Version,
            ct: HttpContext.RequestAborted);
        await transaction.CommitAsync(HttpContext.RequestAborted);

        return new ClaimSetupCodeResponse(connector.Id, apiKey, row.StoreId);
    }

    /// <summary>Generate a one-time setup code for the Windows installer wizard.</summary>
    [Authorize(Roles = "Admin,Manager,Installer")]
    [HttpPost("setup-codes")]
    public async Task<ActionResult<CreateSetupCodeResponse>> CreateSetupCode(CreateSetupCodeRequest req)
    {
        if (!TenantAccess.CanAccessStore(User, req.StoreId))
            return Forbid();
        if (!await _db.Stores.AnyAsync(s => s.Id == req.StoreId))
            return BadRequest(new { error = "Unknown store" });

        var code = ConnectorInstallerService.GenerateSetupCode();
        var userId = User.FindFirstValue("uid");
        if (!Guid.TryParse(userId, out var createdBy))
            return Unauthorized();

        var row = new ConnectorSetupCode
        {
            StoreId = req.StoreId,
            CodeHash = BCrypt.Net.BCrypt.HashPassword(code),
            ExpiresAt = DateTimeOffset.UtcNow.AddMinutes(30),
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
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();
        // An uninstall is terminal for these credentials. This also closes the
        // small race where an already in-flight heartbeat arrives after the
        // Windows uninstaller has marked the connector as removed.
        if (string.Equals(
                connector.DegradedReason, "uninstalled",
                StringComparison.OrdinalIgnoreCase))
            return Conflict(new { error = "Connector has been uninstalled" });

        connector.DiskFreePct = req.DiskFreePct;
        connector.UploadQueueDepth = req.UploadQueueDepth;
        connector.DegradedReason = req.DegradedReason;
        connector.Version = req.Version;
        connector.LastHeartbeat = DateTimeOffset.UtcNow;
        if (!string.IsNullOrWhiteSpace(req.AdminHost))
            connector.AdminHost = req.AdminHost.Trim();
        if (req.AdminPort is > 0 and <= 65535)
            connector.AdminPort = req.AdminPort;
        connector.Status = req.DegradedReason is null ? ConnectorStatus.Healthy : ConnectorStatus.Degraded;
        await _db.SaveChangesAsync();
        return Ok(new { ok = true });
    }

    // Called by the Windows uninstaller before it removes local credentials.
    // The connector row is retained so a reinstall can safely re-pair the same
    // store and cameras, but the dashboard stops treating it as installed.
    [AllowAnonymous]
    [HttpPost("uninstall")]
    public async Task<IActionResult> Uninstall()
    {
        var connector = await _connectorAuth.AuthenticateAsync(
            Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();

        connector.Status = ConnectorStatus.Offline;
        connector.LastHeartbeat = null;
        connector.DegradedReason = "uninstalled";
        connector.UploadQueueDepth = 0;
        await _db.SaveChangesAsync(HttpContext.RequestAborted);
        return Ok(new { ok = true });
    }

    /// <summary>
    /// Lets an authorized store user clear a connector that was removed outside
    /// the Windows uninstaller. An active connector cannot be reset this way.
    /// </summary>
    [Authorize(Roles = "Admin,Manager,Installer")]
    [HttpPost("{id:guid}/mark-uninstalled")]
    public async Task<IActionResult> MarkUninstalled(Guid id)
    {
        var connector = await _db.Connectors.FindAsync([id], HttpContext.RequestAborted);
        if (connector is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, connector.StoreId)) return Forbid();

        var activeCutoff = DateTimeOffset.UtcNow.AddMinutes(-2);
        if (connector.LastHeartbeat >= activeCutoff &&
            (connector.Status == ConnectorStatus.Healthy ||
             connector.Status == ConnectorStatus.Degraded))
        {
            return Conflict(new {
                error = "This connector is online. Uninstall it from the shop PC instead."
            });
        }

        connector.Status = ConnectorStatus.Offline;
        connector.LastHeartbeat = null;
        connector.DegradedReason = "uninstalled";
        connector.UploadQueueDepth = 0;
        await _db.SaveChangesAsync(HttpContext.RequestAborted);
        return Ok(new { ok = true });
    }

    // Health list for the dashboard.
    [Authorize]
    [HttpGet]
    public async Task<IActionResult> List([FromQuery] Guid? storeId)
    {
        var q = TenantAccess.ScopeConnectors(_db.Connectors, User);
        if (storeId is not null)
        {
            if (!TenantAccess.CanAccessStore(User, storeId.Value)) return Forbid();
            q = q.Where(c => c.StoreId == storeId);
        }
        return Ok(await q.OrderBy(c => c.Name).ToListAsync());
    }

    // Connector fetches its assigned cameras.
    [AllowAnonymous]
    [HttpGet("cameras")]
    public async Task<IActionResult> GetCameras()
    {
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();

        var cameras = await _db.Cameras
            .Where(c => c.StoreId == connector.StoreId &&
                        c.ConnectorId == connector.Id &&
                        c.Status != CameraStatus.Disabled)
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
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();
        if (string.IsNullOrWhiteSpace(req.Name))
            return BadRequest(new { error = "name is required" });

        var cam = await _cameraProvisioning.ProvisionConnectorCameraAsync(
            connector,
            req.SourceKey,
            req.Name,
            req.RtspUrl,
            req.OnvifHost,
            req.OnvifPort,
            HttpContext.RequestAborted);
        return Ok(cam);
    }

    /// <summary>
    /// Atomically makes the successfully provisioned source set authoritative.
    /// Safe to retry: applying the same source-key set produces the same result.
    /// </summary>
    [AllowAnonymous]
    [HttpPost("finalize-setup")]
    public async Task<IActionResult> FinalizeSetup(FinalizeConnectorSetupRequest req)
    {
        var connector = await _connectorAuth.AuthenticateAsync(
            Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();

        var sourceKeys = (req.SourceKeys ?? [])
            .Where(k => !string.IsNullOrWhiteSpace(k))
            .Select(k => k.Trim())
            .Distinct(StringComparer.Ordinal)
            .ToList();
        if (sourceKeys.Count == 0)
            return BadRequest(new { error = "At least one sourceKey is required" });

        await using var transaction = await _db.Database.BeginTransactionAsync(
            HttpContext.RequestAborted);

        var provisionedCount = await _db.Cameras
            .CountAsync(c => c.ConnectorId == connector.Id &&
                             c.SourceKey != null &&
                             sourceKeys.Contains(c.SourceKey),
                        HttpContext.RequestAborted);
        if (provisionedCount != sourceKeys.Count)
            return BadRequest(new { error = "One or more sources were not provisioned" });

        var detached = await _db.Cameras
            .Where(c => c.ConnectorId == connector.Id &&
                        (c.SourceKey == null || !sourceKeys.Contains(c.SourceKey)))
            .ExecuteUpdateAsync(
                setters => setters.SetProperty(c => c.ConnectorId, (Guid?)null),
                HttpContext.RequestAborted);

        await transaction.CommitAsync(HttpContext.RequestAborted);
        return Ok(new { ok = true, activeCameraCount = sourceKeys.Count, detached });
    }

    [AllowAnonymous]
    [HttpGet("cameras/{cameraId:guid}/zones")]
    public async Task<IActionResult> ConnectorZones(Guid cameraId)
    {
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();
        if (!await OwnsCameraAsync(connector.Id, cameraId)) return Forbid();
        return Ok(await _db.CameraZones
            .Where(z => z.CameraId == cameraId)
            .OrderBy(z => z.Name)
            .ToListAsync(HttpContext.RequestAborted));
    }

    [AllowAnonymous]
    [HttpPost("cameras/{cameraId:guid}/zones")]
    public async Task<IActionResult> CreateConnectorZone(Guid cameraId, CreateZoneRequest req)
    {
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();
        if (req.CameraId != cameraId || !await OwnsCameraAsync(connector.Id, cameraId))
            return Forbid();
        if (!Enum.TryParse<ZoneType>(req.ZoneType, true, out var zoneType))
            return BadRequest(new { error = "Invalid zoneType" });
        if (string.IsNullOrWhiteSpace(req.Name))
            return BadRequest(new { error = "Zone name is required" });
        if (!ZonePolygonValidator.IsValid(req.PolygonJson))
            return BadRequest(new { error = "polygonJson must be normalized [[x,y], ...] with at least three points" });

        var zone = new CameraZone {
            CameraId = cameraId,
            Name = req.Name.Trim(),
            ZoneType = zoneType,
            PolygonJson = req.PolygonJson
        };
        _db.CameraZones.Add(zone);
        await _db.SaveChangesAsync(HttpContext.RequestAborted);
        return Ok(zone);
    }

    [AllowAnonymous]
    [HttpPut("zones/{zoneId:guid}")]
    public async Task<IActionResult> UpdateConnectorZone(Guid zoneId, UpdateZoneRequest req)
    {
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();
        var zone = await _db.CameraZones.FindAsync([zoneId], HttpContext.RequestAborted);
        if (zone is null) return NotFound();
        if (!await OwnsCameraAsync(connector.Id, zone.CameraId)) return Forbid();
        if (req.Name is not null) zone.Name = req.Name.Trim();
        if (req.PolygonJson is not null)
        {
            if (!ZonePolygonValidator.IsValid(req.PolygonJson))
                return BadRequest(new { error = "polygonJson must be normalized [[x,y], ...] with at least three points" });
            zone.PolygonJson = req.PolygonJson;
        }
        if (req.ZoneType is not null)
        {
            if (!Enum.TryParse<ZoneType>(req.ZoneType, true, out var zoneType))
                return BadRequest(new { error = "Invalid zoneType" });
            zone.ZoneType = zoneType;
        }
        await _db.SaveChangesAsync(HttpContext.RequestAborted);
        return Ok(zone);
    }

    [AllowAnonymous]
    [HttpDelete("zones/{zoneId:guid}")]
    public async Task<IActionResult> DeleteConnectorZone(Guid zoneId)
    {
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();
        var zone = await _db.CameraZones.FindAsync([zoneId], HttpContext.RequestAborted);
        if (zone is null) return NotFound();
        if (!await OwnsCameraAsync(connector.Id, zone.CameraId)) return Forbid();
        _db.CameraZones.Remove(zone);
        await _db.SaveChangesAsync(HttpContext.RequestAborted);
        return NoContent();
    }

    private Task<bool> OwnsCameraAsync(Guid connectorId, Guid cameraId) =>
        _db.Cameras.AnyAsync(
            c => c.Id == cameraId && c.ConnectorId == connectorId,
            HttpContext.RequestAborted);

    /// <summary>Public tray-update manifest. The installer hash is calculated from disk.</summary>
    [AllowAnonymous]
    [HttpGet("updates/latest")]
    public IActionResult LatestUpdate()
    {
        if (!_installer.TryGetInfo(out _, out var size, out var sha))
            return NotFound(new { error = "Installer not found" });
        var downloadUrl =
            $"{Request.Scheme}://{Request.Host}/api/connectors/updates/download";
        return Ok(new {
            version = _installer.Version,
            fileName = _installer.FileName,
            downloadUrl,
            sizeBytes = size,
            sha256 = sha
        });
    }

    [AllowAnonymous]
    [HttpGet("updates/download")]
    public IActionResult DownloadUpdate()
    {
        if (!_installer.TryGetInfo(out var path, out _, out _))
            return NotFound(new { error = "Installer not found" });
        return PhysicalFile(path, "application/octet-stream", _installer.FileName);
    }

    /// <summary>Installer metadata (version / size / sha256). File must exist on disk.</summary>
    [Authorize(Roles = "Admin,Manager,Installer")]
    [HttpGet("installer")]
    public ActionResult<InstallerInfoResponse> InstallerInfo()
    {
        if (!_installer.TryGetPublishedInfo(out var size, out var sha, out var downloadUrl))
            return NotFound(new { error = "Installer is not published." });

        return new InstallerInfoResponse(
            _installer.Version,
            _installer.FileName,
            size,
            sha,
            downloadUrl);
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
}
