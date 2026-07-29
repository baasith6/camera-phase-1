using System.Security.Claims;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Auth;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;
using Onevo.Api.Services;

namespace Onevo.Api.Controllers;

[ApiController]
[Authorize]
[Route("api/alerts")]
public class AlertsController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly S3Service _s3;
    private readonly AlertChannel _channel;

    public AlertsController(OnevoDbContext db, S3Service s3, AlertChannel channel)
    {
        _db = db;
        _s3 = s3;
        _channel = channel;
    }

    [HttpGet]
    public async Task<IActionResult> List([FromQuery] Guid? storeId, [FromQuery] string? status)
    {
        var role = TenantAccess.CurrentRole(User);

        var query =
            from a in TenantAccess.ScopeAlerts(_db.Alerts, User)
            join s in _db.Stores on a.StoreId equals s.Id
            select new { a, s.AlertVisibilityMode };

        if (storeId is not null)
        {
            if (!TenantAccess.CanAccessStore(User, storeId.Value)) return Forbid();
            query = query.Where(x => x.a.StoreId == storeId);
        }
        if (status is not null && Enum.TryParse<AlertStatus>(status, true, out var st))
            query = query.Where(x => x.a.Status == st);

        var rows = await query.OrderByDescending(x => x.a.CreatedAt).Take(500).ToListAsync();

        var visible = rows.Where(x => IsVisible(x.AlertVisibilityMode, role)).Select(x => x.a).ToList();
        return Ok(visible);
    }

    // GET /api/alerts/{id} — returns alert with a fresh 24-hour presigned clip URL.
    [HttpGet("{id:guid}")]
    public async Task<IActionResult> Get(Guid id)
    {
        var alert = await _db.Alerts.Include(a => a.Reviews).FirstOrDefaultAsync(a => a.Id == id);
        if (alert is null) return NotFound();

        var store = await _db.Stores.FindAsync(alert.StoreId);
        if (store is not null && !IsVisible(store.AlertVisibilityMode, CurrentRole()))
            return Forbid();
        if (!TenantAccess.CanAccessStore(User, alert.StoreId)) return Forbid();

        // Lazy presign: regenerate URL on every GET so it never expires for reviewers.
        // ClipUrl stores the S3 ObjectKey; we return a temporary projected object.
        string? freshUrl = null;
        if (!string.IsNullOrEmpty(alert.ClipUrl) && !alert.ClipUrl.StartsWith("http"))
        {
            // ClipUrl is an ObjectKey — presign only if the object still exists in storage,
            // so the UI can show "clip not available" instead of a broken player.
            if (await _s3.ExistsAsync(alert.ClipUrl))
            {
                try { freshUrl = await _s3.PresignedGetAsync(alert.ClipUrl, 86400); }
                catch { /* S3 unavailable — return null URL gracefully */ }
            }
        }
        else
        {
            freshUrl = alert.ClipUrl;  // already a URL (legacy alerts or dev mode)
        }

        // Return the alert with the fresh URL.
        return Ok(new
        {
            alert.Id,
            alert.StoreId,
            alert.CameraId,
            alert.ZoneId,
            alert.ClipId,
            alert.AlertType,
            alert.RiskLevel,
            alert.RiskScore,
            alert.EvidenceJson,
            alert.ModelVersion,
            alert.RuleVersion,
            alert.Status,
            alert.CreatedAt,
            alert.Reviews,
            ClipUrl = freshUrl,   // fresh presigned URL, valid 24h
        });
    }

    /// <summary>
    /// GET /api/alerts/stream — Server-Sent Events endpoint.
    /// Sends <c>data: {...}\n\n</c> for every new alert as it is created.
    /// Clients connect with <c>EventSource</c> and receive live updates.
    /// </summary>
    [HttpGet("stream")]
    public async Task Stream(CancellationToken ct)
    {
        Response.ContentType = "text/event-stream";
        Response.Headers["Cache-Control"] = "no-cache";
        Response.Headers["X-Accel-Buffering"] = "no";

        // Send an initial heartbeat so the browser knows the connection is live.
        await Response.WriteAsync("event: connected\ndata: {}\n\n", ct);
        await Response.Body.FlushAsync(ct);

        var reader = _channel.Reader;

        // Keep a heartbeat interval so proxies don't kill idle connections.
        using var heartbeatTimer = new PeriodicTimer(TimeSpan.FromSeconds(25));
        var heartbeatTask = Task.Run(async () =>
        {
            while (!ct.IsCancellationRequested)
            {
                await heartbeatTimer.WaitForNextTickAsync(ct);
                try
                {
                    await Response.WriteAsync(": heartbeat\n\n", ct);
                    await Response.Body.FlushAsync(ct);
                }
                catch { break; }
            }
        }, ct);

        try
        {
            await foreach (var ev in reader.ReadAllAsync(ct))
            {
                if (!TenantAccess.CanAccessStore(User, ev.StoreId))
                    continue;

                var store = await _db.Stores.AsNoTracking().FirstOrDefaultAsync(s => s.Id == ev.StoreId, ct);
                if (store is not null && !IsVisible(store.AlertVisibilityMode, TenantAccess.CurrentRole(User)))
                    continue;

                var json = JsonSerializer.Serialize(new
                {
                    alertId  = ev.AlertId,
                    alertType = ev.AlertType,
                    riskLevel = ev.RiskLevel,
                    riskScore = ev.RiskScore,
                    storeId  = ev.StoreId,
                    createdAt = ev.CreatedAt,
                });
                var line = $"event: alert\ndata: {json}\n\n";
                await Response.WriteAsync(line, Encoding.UTF8, ct);
                await Response.Body.FlushAsync(ct);
            }
        }
        catch (OperationCanceledException) { /* client disconnected — normal */ }
    }

    [HttpPut("{id:guid}/review")]
    [Authorize(Roles = "Admin,Manager,Reviewer")]
    public async Task<IActionResult> Review(Guid id, ReviewRequest req)
    {
        var alert = await _db.Alerts.FindAsync(id);
        if (alert is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, alert.StoreId)) return Forbid();
        if (!Enum.TryParse<ReviewAction>(req.Action, true, out var action))
            return BadRequest(new { error = "Invalid action" });

        if ((action is ReviewAction.Dismiss or ReviewAction.FalsePositive) && string.IsNullOrWhiteSpace(req.ReasonCode))
            return BadRequest(new { error = "Reason code required for dismiss / false positive" });

        var review = new AlertReview
        {
            AlertId = alert.Id,
            ReviewerId = TenantAccess.CurrentUserId(User),
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

    [Authorize(Roles = "Admin,Manager")]
    [HttpPost("bulk-delete")]
    public async Task<ActionResult<BulkDeleteResponse>> BulkDelete(BulkDeleteRequest req)
    {
        if (req.DeleteAllInStore)
        {
            if (req.StoreId is null)
                return BadRequest(new { error = "storeId is required for delete all" });
            if (!TenantAccess.CanAccessStore(User, req.StoreId.Value))
                return Forbid();
        }

        var alerts = await ResolveAlertsForDeleteAsync(req);
        if (alerts is null)
            return BadRequest(new { error = "Provide ids or set deleteAllInStore with storeId" });

        if (alerts.Count == 0)
            return Ok(new BulkDeleteResponse(0, 0, []));

        foreach (var alert in alerts)
        {
            _db.AlertReviews.RemoveRange(alert.Reviews);
            _db.Alerts.Remove(alert);
        }

        await _db.SaveChangesAsync();
        return Ok(new BulkDeleteResponse(alerts.Count, 0, []));
    }

    private async Task<List<Alert>?> ResolveAlertsForDeleteAsync(BulkDeleteRequest req)
    {
        IQueryable<Alert> query = TenantAccess.ScopeAlerts(_db.Alerts.Include(a => a.Reviews), User);

        if (req.DeleteAllInStore)
        {
            if (req.StoreId is null) return null;
            if (!TenantAccess.CanAccessStore(User, req.StoreId.Value)) return null;
            query = query.Where(a => a.StoreId == req.StoreId);
        }
        else if (req.Ids is { Count: > 0 })
        {
            var ids = req.Ids.Distinct().ToList();
            query = query.Where(a => ids.Contains(a.Id));
        }
        else
        {
            return null;
        }

        return await query.ToListAsync();
    }

    private static bool IsVisible(AlertVisibilityMode mode, UserRole role) => mode switch
    {
        AlertVisibilityMode.All => true,
        AlertVisibilityMode.ManagerOnly => role is UserRole.Admin or UserRole.Manager,
        AlertVisibilityMode.Silent => role is UserRole.Admin,
        _ => role is UserRole.Admin
    };

    private UserRole CurrentRole() => TenantAccess.CurrentRole(User);
}

