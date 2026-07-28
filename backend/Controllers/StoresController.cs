using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Auth;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/stores")]
public class StoresController : ControllerBase
{
    private readonly OnevoDbContext _db;
    public StoresController(OnevoDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> List()
    {
        var stores = await TenantAccess.ScopeStores(_db.Stores, User)
            .OrderBy(s => s.Name)
            .ToListAsync();
        return Ok(stores);
    }

    [HttpGet("overview")]
    [Authorize(Roles = "Admin")]
    public async Task<IActionResult> Overview()
    {
        var stores = await _db.Stores.OrderBy(s => s.Name).ToListAsync();
        var storeIds = stores.Select(s => s.Id).ToList();

        var cameraCounts = await _db.Cameras
            .Where(c => storeIds.Contains(c.StoreId))
            .GroupBy(c => c.StoreId)
            .Select(g => new { StoreId = g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.StoreId, x => x.Count);

        var connectors = await _db.Connectors
            .Where(c => storeIds.Contains(c.StoreId))
            .ToListAsync();

        var alertStats = await _db.Alerts
            .Where(a => storeIds.Contains(a.StoreId))
            .GroupBy(a => a.StoreId)
            .Select(g => new
            {
                StoreId = g.Key,
                Pending = g.Count(a => a.Status == AlertStatus.PendingReview),
                LastAt = g.Max(a => a.CreatedAt)
            })
            .ToListAsync();

        var overview = stores.Select(s =>
        {
            var storeConnectors = connectors.Where(c => c.StoreId == s.Id).ToList();
            var online = storeConnectors.Count(c =>
                (c.Status == ConnectorStatus.Healthy || c.Status == ConnectorStatus.Degraded) &&
                c.LastHeartbeat > DateTimeOffset.UtcNow.AddMinutes(-5));
            var stats = alertStats.FirstOrDefault(a => a.StoreId == s.Id);
            return new StoreOverviewResponse(
                s.Id,
                s.Name,
                s.AlertVisibilityMode.ToString(),
                s.NotificationEmail,
                cameraCounts.GetValueOrDefault(s.Id),
                storeConnectors.Count,
                online,
                stats?.Pending ?? 0,
                stats?.LastAt);
        });

        return Ok(overview);
    }

    [HttpGet("{id:guid}")]
    public async Task<IActionResult> Get(Guid id)
    {
        if (!TenantAccess.CanAccessStore(User, id)) return Forbid();
        var store = await _db.Stores.FindAsync(id);
        return store is null ? NotFound() : Ok(store);
    }

    [HttpPost]
    [Authorize(Roles = "Admin,Manager")]
    public async Task<IActionResult> Create(CreateStoreRequest req)
    {
        if (!TenantAccess.IsAdmin(User))
            return Forbid();

        var mode = AlertVisibilityMode.ManagerOnly;
        if (!string.IsNullOrWhiteSpace(req.AlertVisibilityMode) &&
            Enum.TryParse<AlertVisibilityMode>(req.AlertVisibilityMode, true, out var parsed))
            mode = parsed;

        var store = new Store
        {
            Name = req.Name.Trim(),
            Organization = req.Organization ?? "default",
            NotificationEmail = string.IsNullOrWhiteSpace(req.NotificationEmail)
                ? null : req.NotificationEmail.Trim(),
            AlertVisibilityMode = mode
        };
        _db.Stores.Add(store);
        await _db.SaveChangesAsync();
        return CreatedAtAction(nameof(Get), new { id = store.Id }, store);
    }

    [HttpPut("{id:guid}")]
    [Authorize(Roles = "Admin,Manager")]
    public async Task<IActionResult> Update(Guid id, UpdateStoreRequest req)
    {
        if (!TenantAccess.CanAccessStore(User, id)) return Forbid();
        var store = await _db.Stores.FindAsync(id);
        if (store is null) return NotFound();
        if (req.Name is not null) store.Name = req.Name;
        if (req.NotificationEmail is not null)
            store.NotificationEmail = string.IsNullOrWhiteSpace(req.NotificationEmail)
                ? null : req.NotificationEmail.Trim();
        if (req.AlertVisibilityMode is not null &&
            Enum.TryParse<AlertVisibilityMode>(req.AlertVisibilityMode, true, out var mode))
            store.AlertVisibilityMode = mode;
        await _db.SaveChangesAsync();
        return Ok(store);
    }
}
