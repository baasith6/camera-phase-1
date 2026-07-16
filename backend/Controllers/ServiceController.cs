using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Data;

namespace Onevo.Api.Controllers;

// Endpoints consumed by the cloud-ai worker. Authenticated with the shared service key
// (X-Service-Key), not a user JWT.
[ApiController]
[Route("api/service")]
public class ServiceController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly IConfiguration _cfg;

    public ServiceController(OnevoDbContext db, IConfiguration cfg)
    {
        _db = db;
        _cfg = cfg;
    }

    [AllowAnonymous]
    [HttpGet("cameras/{cameraId:guid}/zones")]
    public async Task<IActionResult> Zones(Guid cameraId)
    {
        if (!IsService()) return Unauthorized();
        var zones = await _db.CameraZones
            .Where(z => z.CameraId == cameraId)
            .Select(z => new { z.Id, z.Name, ZoneType = z.ZoneType.ToString(), z.PolygonJson })
            .ToListAsync();
        return Ok(zones);
    }

    private bool IsService()
    {
        var serviceKey = _cfg["Seed:ConnectorBootstrapKey"];
        return Request.Headers.TryGetValue("X-Service-Key", out var provided)
               && !string.IsNullOrEmpty(serviceKey)
               && provided.ToString() == serviceKey;
    }
}
