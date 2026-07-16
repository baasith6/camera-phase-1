using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
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
    public async Task<IActionResult> List() => Ok(await _db.Stores.OrderBy(s => s.Name).ToListAsync());

    [HttpGet("{id:guid}")]
    public async Task<IActionResult> Get(Guid id)
    {
        var store = await _db.Stores.FindAsync(id);
        return store is null ? NotFound() : Ok(store);
    }

    [HttpPost]
    [Authorize(Roles = "Admin,Manager")]
    public async Task<IActionResult> Create(CreateStoreRequest req)
    {
        var store = new Store { Name = req.Name, Organization = req.Organization ?? "default" };
        _db.Stores.Add(store);
        await _db.SaveChangesAsync();
        return CreatedAtAction(nameof(Get), new { id = store.Id }, store);
    }

    [HttpPut("{id:guid}")]
    [Authorize(Roles = "Admin,Manager")]
    public async Task<IActionResult> Update(Guid id, UpdateStoreRequest req)
    {
        var store = await _db.Stores.FindAsync(id);
        if (store is null) return NotFound();
        if (req.Name is not null) store.Name = req.Name;
        if (req.AlertVisibilityMode is not null &&
            Enum.TryParse<AlertVisibilityMode>(req.AlertVisibilityMode, true, out var mode))
            store.AlertVisibilityMode = mode;
        await _db.SaveChangesAsync();
        return Ok(store);
    }
}
