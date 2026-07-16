using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/zones")]
public class ZonesController : ControllerBase
{
    private readonly OnevoDbContext _db;
    public ZonesController(OnevoDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> List([FromQuery] Guid cameraId)
        => Ok(await _db.CameraZones.Where(z => z.CameraId == cameraId).ToListAsync());

    [HttpPost]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> Create(CreateZoneRequest req)
    {
        if (!await _db.Cameras.AnyAsync(c => c.Id == req.CameraId))
            return BadRequest(new { error = "Unknown camera" });
        if (!Enum.TryParse<ZoneType>(req.ZoneType, true, out var zt))
            return BadRequest(new { error = "Invalid zoneType" });

        var zone = new CameraZone
        {
            CameraId = req.CameraId,
            Name = req.Name,
            ZoneType = zt,
            PolygonJson = req.PolygonJson
        };
        _db.CameraZones.Add(zone);
        await _db.SaveChangesAsync();
        return Ok(zone);
    }

    [HttpPut("{id:guid}")]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> Update(Guid id, UpdateZoneRequest req)
    {
        var zone = await _db.CameraZones.FindAsync(id);
        if (zone is null) return NotFound();
        if (req.Name is not null) zone.Name = req.Name;
        if (req.PolygonJson is not null) zone.PolygonJson = req.PolygonJson;
        if (req.ZoneType is not null && Enum.TryParse<ZoneType>(req.ZoneType, true, out var zt))
            zone.ZoneType = zt;
        await _db.SaveChangesAsync();
        return Ok(zone);
    }

    [HttpDelete("{id:guid}")]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> Delete(Guid id)
    {
        var zone = await _db.CameraZones.FindAsync(id);
        if (zone is null) return NotFound();
        _db.CameraZones.Remove(zone);
        await _db.SaveChangesAsync();
        return NoContent();
    }
}
