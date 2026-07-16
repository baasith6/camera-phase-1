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

        var cam = new Camera { StoreId = req.StoreId, Name = req.Name, RtspUrl = req.RtspUrl };
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
        if (req.Status is not null && Enum.TryParse<CameraStatus>(req.Status, true, out var st))
            cam.Status = st;
        await _db.SaveChangesAsync();
        return Ok(cam);
    }

    // Stub: in a full build this validates connectivity via the connector. Here it just acknowledges.
    [HttpPost("{id:guid}/test-stream")]
    [Authorize(Roles = "Admin,Manager,Installer")]
    public async Task<IActionResult> TestStream(Guid id)
    {
        var cam = await _db.Cameras.FindAsync(id);
        if (cam is null) return NotFound();
        return Ok(new { ok = true, message = "Test-stream request acknowledged (validated by connector admin UI in Phase 1A)." });
    }
}
