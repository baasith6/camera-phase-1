using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/alerts")]
public class AlertsController : ControllerBase
{
    private readonly OnevoDbContext _db;
    public AlertsController(OnevoDbContext db) => _db = db;

    [HttpGet]
    public async Task<IActionResult> List([FromQuery] Guid? storeId, [FromQuery] string? status)
    {
        var role = CurrentRole();

        var query =
            from a in _db.Alerts
            join s in _db.Stores on a.StoreId equals s.Id
            select new { a, s.AlertVisibilityMode };

        if (storeId is not null) query = query.Where(x => x.a.StoreId == storeId);
        if (status is not null && Enum.TryParse<AlertStatus>(status, true, out var st))
            query = query.Where(x => x.a.Status == st);

        var rows = await query.OrderByDescending(x => x.a.CreatedAt).Take(500).ToListAsync();

        // Apply pilot visibility mode per the alert's store.
        var visible = rows.Where(x => IsVisible(x.AlertVisibilityMode, role)).Select(x => x.a).ToList();
        return Ok(visible);
    }

    [HttpGet("{id:guid}")]
    public async Task<IActionResult> Get(Guid id)
    {
        var alert = await _db.Alerts.Include(a => a.Reviews).FirstOrDefaultAsync(a => a.Id == id);
        if (alert is null) return NotFound();

        var store = await _db.Stores.FindAsync(alert.StoreId);
        if (store is not null && !IsVisible(store.AlertVisibilityMode, CurrentRole()))
            return Forbid();

        return Ok(alert);
    }

    [HttpPut("{id:guid}/review")]
    [Authorize(Roles = "Admin,Manager,Reviewer")]
    public async Task<IActionResult> Review(Guid id, ReviewRequest req)
    {
        var alert = await _db.Alerts.FindAsync(id);
        if (alert is null) return NotFound();
        if (!Enum.TryParse<ReviewAction>(req.Action, true, out var action))
            return BadRequest(new { error = "Invalid action" });

        // Reason code required for dismiss / false positive (V4 rule).
        if ((action is ReviewAction.Dismiss or ReviewAction.FalsePositive) && string.IsNullOrWhiteSpace(req.ReasonCode))
            return BadRequest(new { error = "Reason code required for dismiss / false positive" });

        var review = new AlertReview
        {
            AlertId = alert.Id,
            ReviewerId = CurrentUserId(),
            Action = action,
            ReasonCode = req.ReasonCode,
            Notes = req.Notes
        };
        _db.AlertReviews.Add(review);

        alert.Status = action switch
        {
            ReviewAction.Confirm => AlertStatus.Confirmed,
            ReviewAction.Dismiss => AlertStatus.Dismissed,
            ReviewAction.FalsePositive => AlertStatus.FalsePositive,
            ReviewAction.NeedsFollowUp => AlertStatus.NeedsFollowUp,
            _ => alert.Status
        };

        await _db.SaveChangesAsync();
        return Ok(alert);
    }

    private static bool IsVisible(AlertVisibilityMode mode, UserRole role) => mode switch
    {
        AlertVisibilityMode.All => true,
        AlertVisibilityMode.ManagerOnly => role is UserRole.Admin or UserRole.Manager,
        AlertVisibilityMode.Silent => role is UserRole.Admin,
        _ => role is UserRole.Admin
    };

    private UserRole CurrentRole()
        => Enum.TryParse<UserRole>(User.FindFirstValue(ClaimTypes.Role), true, out var r) ? r : UserRole.Reviewer;

    private Guid CurrentUserId()
        => Guid.TryParse(User.FindFirstValue("uid"), out var id) ? id : Guid.Empty;
}
