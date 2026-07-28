using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Auth;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Controllers;

[ApiController]
[Authorize(Roles = "Admin")]
[Route("api/users")]
public class UsersController : ControllerBase
{
    private readonly OnevoDbContext _db;

    public UsersController(OnevoDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> List([FromQuery] Guid? storeId)
    {
        var q = _db.Users.AsQueryable();
        if (storeId is not null)
            q = q.Where(u => u.StoreId == storeId);
        var users = await q.OrderBy(u => u.Email).ToListAsync();
        return Ok(users.Select(ToResponse));
    }

    [HttpPost]
    public async Task<IActionResult> Create(CreateUserRequest req)
    {
        var email = req.Email.Trim().ToLowerInvariant();
        if (string.IsNullOrEmpty(email) || string.IsNullOrWhiteSpace(req.Password))
            return BadRequest(new { error = "Email and password are required" });

        if (!Enum.TryParse<UserRole>(req.Role, true, out var role))
            return BadRequest(new { error = "Invalid role" });

        if (role is UserRole.Admin && req.StoreId is not null)
            return BadRequest(new { error = "Admin users cannot be assigned to a store" });

        if (role is UserRole.Manager or UserRole.Reviewer or UserRole.Installer)
        {
            if (req.StoreId is null)
                return BadRequest(new { error = "StoreId is required for Manager, Reviewer, and Installer roles" });
            if (!await _db.Stores.AnyAsync(s => s.Id == req.StoreId))
                return BadRequest(new { error = "Unknown store" });
        }

        if (await _db.Users.AnyAsync(u => u.Email == email))
            return Conflict(new { error = "Email already registered" });

        var user = new User
        {
            Email = email,
            PasswordHash = BCrypt.Net.BCrypt.HashPassword(req.Password),
            Role = role,
            StoreId = role == UserRole.Admin ? null : req.StoreId
        };
        _db.Users.Add(user);
        await _db.SaveChangesAsync();
        return CreatedAtAction(nameof(List), new { id = user.Id }, ToResponse(user));
    }

    private static UserResponse ToResponse(User u)
        => new(u.Id, u.Email, u.Role.ToString(), u.StoreId, u.CreatedAt);
}
