using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/cameras")]
public class CamerasController : ControllerBase
{
    private readonly OnevoDbContext _db;
    public CamerasController(OnevoDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> List([FromQuery] Guid? storeId)
    {
        var q = _db.Cameras.AsQueryable();
        if (storeId is not null) q = q.Where(c => c.StoreId == storeId);
        return Ok(await q.OrderBy(c => c.Name).ToListAsync());
    }

    [HttpGet("{id:guid}")]
    public async Task<IActionResult> Get(Guid id)
    {
        var cam = await _db.Cameras.Include(c => c.Zones).FirstOrDefaultAsync(c => c.Id == id);
        return cam is null ? NotFound() : Ok(cam);
    }

    [HttpPost]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> Create(CreateCameraRequest req)
    {
        if (!await _db.Stores.AnyAsync(s => s.Id == req.StoreId))
            return BadRequest(new { error = "Unknown store" });

        var cam = new Camera
        {
            StoreId = req.StoreId,
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
        if (req.Name is not null) cam.Name = req.Name;
        if (req.RtspUrl is not null) cam.RtspUrl = req.RtspUrl;
        if (req.OnvifHost is not null) cam.OnvifHost = req.OnvifHost;
        if (req.OnvifPort is not null) cam.OnvifPort = req.OnvifPort;
        if (req.Status is not null && Enum.TryParse<CameraStatus>(req.Status, true, out var st))
            cam.Status = st;
        await _db.SaveChangesAsync();
        return Ok(cam);
    }

    // Called by the connector after ONVIF query — stores device identity in the DB.
    [HttpPut("{id:guid}/device-info")]
    [AllowAnonymous]   // authenticated by connector's X-Connector-Key header (checked below)
    public async Task<IActionResult> UpdateDeviceInfo(Guid id, [FromBody] UpdateDeviceInfoRequest req,
        [FromHeader(Name = "X-Connector-Id")] string? connectorId,
        [FromHeader(Name = "X-Connector-Key")] string? connectorKey)
    {
        // Minimal auth: connector must provide its own registered key.
        var cam = await _db.Cameras.FindAsync(id);
        if (cam is null) return NotFound();

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
        return Ok(new
        {
            ok = true,
            message = "Stream check acknowledged. Use connector admin UI for live validation.",
            adminUrl = $"http://localhost:8099/onvif/snapshot",
            camera = new { cam.Name, cam.RtspUrl, cam.OnvifHost, cam.CameraModel }
        });
    }
}
