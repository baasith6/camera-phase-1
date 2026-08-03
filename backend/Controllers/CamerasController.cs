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
[Authorize]
[Route("api/cameras")]
public class CamerasController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly ConnectorAuthenticationService _connectorAuth;
    private readonly S3Service _s3;
    private readonly ILogger<CamerasController> _logger;
    public CamerasController(
        OnevoDbContext db,
        ConnectorAuthenticationService connectorAuth,
        S3Service s3,
        ILogger<CamerasController> logger)
    {
        _db = db;
        _connectorAuth = connectorAuth;
        _s3 = s3;
        _logger = logger;
    }

    [HttpGet]
    public async Task<IActionResult> List([FromQuery] Guid? storeId)
    {
        var q = TenantAccess.ScopeCameras(_db.Cameras, User);
        if (storeId is not null)
        {
            if (!TenantAccess.CanAccessStore(User, storeId.Value)) return Forbid();
            q = q.Where(c => c.StoreId == storeId);
        }
        return Ok(await q.OrderBy(c => c.Name).ToListAsync());
    }

    [HttpGet("{id:guid}")]
    public async Task<IActionResult> Get(Guid id)
    {
        var cam = await _db.Cameras.Include(c => c.Zones).FirstOrDefaultAsync(c => c.Id == id);
        if (cam is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, cam.StoreId)) return Forbid();
        return Ok(cam);
    }

    [HttpGet("{id:guid}/reference-frame")]
    public async Task<IActionResult> ReferenceFrame(Guid id)
    {
        var cam = await _db.Cameras.AsNoTracking().FirstOrDefaultAsync(c => c.Id == id);
        if (cam is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, cam.StoreId)) return Forbid();
        if (string.IsNullOrWhiteSpace(cam.ReferenceFrameObjectKey))
            return NotFound(new { error = "No saved reference frame" });
        try
        {
            if (cam.ReferenceFrameCapturedAt is { } capturedAt)
                Response.Headers["X-ONEVO-Frame-Captured-At"] = capturedAt.ToString("O");
            Response.Headers["X-Content-Type-Options"] = "nosniff";
            Response.Headers.CacheControl = "private, max-age=60";
            Response.ContentType = "image/jpeg";
            await _s3.CopyToAsync(
                cam.ReferenceFrameObjectKey,
                Response.Body,
                HttpContext.RequestAborted);
            return new EmptyResult();
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(
                ex,
                "Reference frame {ObjectKey} for camera {CameraId} could not be read",
                cam.ReferenceFrameObjectKey,
                id);
            return StatusCode(
                StatusCodes.Status503ServiceUnavailable,
                new { error = "Saved reference frame is temporarily unavailable" });
        }
    }

    [HttpPost]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> Create(CreateCameraRequest req)
    {
        if (!TenantAccess.CanAccessStore(User, req.StoreId))
            return Forbid();
        if (!await _db.Stores.AnyAsync(s => s.Id == req.StoreId))
            return BadRequest(new { error = "Unknown store" });

        var connectorId = await _db.Connectors
            .Where(c => c.StoreId == req.StoreId)
            .Select(c => (Guid?)c.Id)
            .SingleOrDefaultAsync();

        var cam = new Camera
        {
            StoreId = req.StoreId,
            ConnectorId = connectorId,
            Name = req.Name,
            RtspUrl = req.RtspUrl,
            OnvifHost = req.OnvifHost,
            OnvifPort = req.OnvifPort,
        };
        _db.Cameras.Add(cam);
        await _db.SaveChangesAsync();
        return CreatedAtAction(nameof(Get), new { id = cam.Id }, cam);
    }

    [HttpPut("{id:guid}")]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> Update(Guid id, UpdateCameraRequest req)
    {
        var cam = await _db.Cameras.FindAsync(id);
        if (cam is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, cam.StoreId)) return Forbid();
        if (req.Name is not null) cam.Name = req.Name;
        if (req.RtspUrl is not null) cam.RtspUrl = req.RtspUrl;
        if (req.OnvifHost is not null) cam.OnvifHost = req.OnvifHost;
        if (req.OnvifPort is not null) cam.OnvifPort = req.OnvifPort;
        if (req.Status is not null && Enum.TryParse<CameraStatus>(req.Status, true, out var st))
            cam.Status = st;
        await _db.SaveChangesAsync();
        return Ok(cam);
    }

    [HttpDelete("{id:guid}")]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> Disable(Guid id)
    {
        var cam = await _db.Cameras.FindAsync(id);
        if (cam is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, cam.StoreId)) return Forbid();
        cam.Status = CameraStatus.Disabled;
        await _db.SaveChangesAsync();
        return Ok(new { ok = true, cameraId = cam.Id });
    }

    [HttpPost("bulk-disable")]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> BulkDisable(BulkDisableCamerasRequest req)
    {
        var ids = (req.CameraIds ?? []).Distinct().ToList();
        if (ids.Count == 0) return BadRequest(new { error = "Select at least one camera" });
        var cameras = await TenantAccess.ScopeCameras(_db.Cameras, User)
            .Where(c => ids.Contains(c.Id))
            .ToListAsync();
        foreach (var camera in cameras) camera.Status = CameraStatus.Disabled;
        await _db.SaveChangesAsync();
        return Ok(new { ok = true, disabled = cameras.Count });
    }

    // Called by the connector after ONVIF query — stores device identity in the DB.
    [HttpPut("{id:guid}/device-info")]
    [AllowAnonymous]   // authenticated by connector's X-Connector-Key header (checked below)
    public async Task<IActionResult> UpdateDeviceInfo(Guid id, [FromBody] UpdateDeviceInfoRequest req,
        [FromHeader(Name = "X-Connector-Id")] string? connectorId,
        [FromHeader(Name = "X-Connector-Key")] string? connectorKey)
    {
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();
        var cam = await _db.Cameras.FindAsync(id);
        if (cam is null) return NotFound();
        if (cam.StoreId != connector.StoreId || cam.ConnectorId != connector.Id)
            return Forbid();

        if (req.Manufacturer is not null) cam.CameraManufacturer = req.Manufacturer;
        if (req.Model is not null) cam.CameraModel = req.Model;
        if (req.Serial is not null) cam.CameraSerial = req.Serial;
        if (req.Firmware is not null) cam.CameraFirmware = req.Firmware;
        if (req.OnvifHost is not null) cam.OnvifHost = req.OnvifHost;
        if (req.OnvifPort is not null) cam.OnvifPort = req.OnvifPort;
        if (req.RtspUrl is not null) cam.RtspUrl = req.RtspUrl;  // auto-update RTSP URL from ONVIF
        cam.Status = CameraStatus.Active;
        cam.LastSeen = DateTimeOffset.UtcNow;
        await _db.SaveChangesAsync();
        return Ok(cam);
    }

    // Test-stream: acknowledges connectivity check (validated by connector admin UI).
    [HttpPost("{id:guid}/test-stream")]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> TestStream(Guid id)
    {
        var cam = await _db.Cameras.FindAsync(id);
        if (cam is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, cam.StoreId)) return Forbid();
        return Ok(new
        {
            ok = true,
            message = "Stream check acknowledged. Use connector admin UI for live validation.",
            adminUrl = $"http://localhost:8099/onvif/snapshot",
            camera = new { cam.Name, cam.RtspUrl, cam.OnvifHost, cam.CameraModel }
        });
    }
}
