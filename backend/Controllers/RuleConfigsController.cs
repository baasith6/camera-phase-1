using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Data;
using Onevo.Api.Domain;
using Onevo.Api.Services;

namespace Onevo.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/rule-configs")]
public class RuleConfigsController : ControllerBase
{
    private readonly OnevoDbContext _db;
    public RuleConfigsController(OnevoDbContext db) => _db = db;

    // Effective (resolved) config for tuning UI: global default merged view.
    [HttpGet]
    public async Task<IActionResult> Get([FromQuery] Guid? storeId)
    {
        var configs = await _db.RuleConfigs
            .Where(r => (r.StoreId == null && r.CameraId == null && r.ZoneId == null) || r.StoreId == storeId)
            .ToListAsync();
        return Ok(configs);
    }

    // Upsert a store-scoped (or global if storeId null) risk config.
    [HttpPut]
    [Authorize(Roles = "Admin,Manager")]
    public async Task<IActionResult> Upsert([FromQuery] Guid? storeId, [FromBody] RiskConfig config)
    {
        // Validate JSON round-trips.
        var json = JsonSerializer.Serialize(config);

        var existing = await _db.RuleConfigs.FirstOrDefaultAsync(r =>
            r.StoreId == storeId && r.CameraId == null && r.ZoneId == null);

        if (existing is null)
        {
            existing = new RuleConfig { StoreId = storeId, ConfigJson = json };
            _db.RuleConfigs.Add(existing);
        }
        else
        {
            existing.ConfigJson = json;
            existing.UpdatedAt = DateTimeOffset.UtcNow;
        }
        await _db.SaveChangesAsync();
        return Ok(existing);
    }
}
