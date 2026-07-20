using System.Security.Cryptography;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Controllers;

[ApiController]
[Route("api/connectors")]
public class ConnectorsController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly IConfiguration _cfg;

    public ConnectorsController(OnevoDbContext db, IConfiguration cfg)
    {
        _db = db;
        _cfg = cfg;
    }

    // Connector self-registration using the shared bootstrap key. Returns a per-connector API key
    // (shown once). Only a scoped key is stored (hashed) — never broad storage credentials.
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
            Name = req.Name,
            Version = req.Version,
            ApiKeyHash = BCrypt.Net.BCrypt.HashPassword(apiKey),
            Status = ConnectorStatus.Healthy,
            LastHeartbeat = DateTimeOffset.UtcNow
        };
        _db.Connectors.Add(connector);
        await _db.SaveChangesAsync();

        return new RegisterConnectorResponse(connector.Id, apiKey);
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

        var cameras = await _db.Cameras
            .Where(c => c.StoreId == connector.StoreId)
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
}
