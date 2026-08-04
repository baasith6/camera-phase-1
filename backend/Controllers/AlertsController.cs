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

    // GET /api/alerts/patterns — the supported suspicious-activity patterns.
    // Single source of truth: the AiEventType enum.
    [HttpGet("patterns")]
    public IActionResult Patterns() => Ok(Enum.GetNames<AiEventType>());

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

        // AI detections for this clip so the review UI can pre-select patterns.
        var aiEventRows = await _db.AiEvents
            .Where(e => e.ClipId == alert.ClipId)
            .OrderBy(e => e.StartTs)
            .Select(e => new { e.EventType, e.Confidence, e.StartTs, e.EndTs })
            .ToListAsync();
        var aiEvents = aiEventRows
            .Select(e => new
            {
                EventType = e.EventType.ToString(),
                e.Confidence,
                e.StartTs,
                e.EndTs,
            })
            .ToList();

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
            AiEvents = aiEvents,
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

        // Validate confirmed patterns against the AiEventType enum (single source of truth).
        // Null = old client without pattern selection: keep saving the review, no dataset entry.
        List<string>? confirmed = null;
        if (req.ConfirmedPatterns is not null)
        {
            confirmed = new List<string>();
            foreach (var p in req.ConfirmedPatterns)
            {
                if (!Enum.TryParse<AiEventType>(p, true, out var pattern))
                    return BadRequest(new { error = $"Unknown pattern '{p}'" });
                if (!Enum.IsDefined(typeof(AiEventType), pattern))
                    return BadRequest(new { error = $"Unknown pattern '{p}'" });
                var name = pattern.ToString();
                if (confirmed.Contains(name))
                    return BadRequest(new { error = $"Duplicate pattern '{p}'" });
                confirmed.Add(name);
            }

            if (action is ReviewAction.Confirm && confirmed.Count == 0)
                return BadRequest(new { error = "Select at least one pattern to confirm the incident" });
            if (action is ReviewAction.FalsePositive && confirmed.Count > 0)
                return BadRequest(new { error = "False positive reviews must not have confirmed patterns" });
            if ((action is ReviewAction.Dismiss or ReviewAction.NeedsFollowUp) && confirmed.Count > 0)
                return BadRequest(new { error = "Dismiss and NeedsFollowUp reviews must not have confirmed patterns" });
        }

        var review = new AlertReview
        {
            AlertId = alert.Id,
            ReviewerId = TenantAccess.CurrentUserId(User),
            Action = action,
            ReasonCode = req.ReasonCode,
            Notes = req.Notes,
            ConfirmedPatternsJson = confirmed is null ? null : JsonSerializer.Serialize(confirmed)
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

        var destKey = await UpsertTrainingSampleAsync(alert, action, confirmed, review.ReviewerId);

        try
        {
            await _db.SaveChangesAsync();
        }
        catch (DbUpdateException ex) when (ex.InnerException?.Message?.Contains("IX_TrainingSamples_AlertId") == true)
        {
            // Unique constraint violation on AlertId: another concurrent review created the sample.
            // Discard our in-memory sample, reload the winner, and retry the upsert logic.
            _db.ChangeTracker.Clear();  // Detach all tracked entities
            if (!string.IsNullOrEmpty(destKey))
            {
                try { await _s3.DeleteAsync(destKey); }
                catch { /* best-effort cleanup */ }
            }

            // Reload alert and retry: ChangeTracker.Clear() detached the review and the
            // alert status change, so re-add/re-apply them before retrying the upsert.
            alert = await _db.Alerts.FindAsync(id) ?? alert;
            _db.AlertReviews.Add(review);
            alert.Status = action switch
            {
                ReviewAction.Confirm => AlertStatus.Confirmed,
                ReviewAction.Dismiss => AlertStatus.Dismissed,
                ReviewAction.FalsePositive => AlertStatus.FalsePositive,
                ReviewAction.NeedsFollowUp => AlertStatus.NeedsFollowUp,
                _ => alert.Status
            };
            var retryDestKey = await UpsertTrainingSampleAsync(alert, action, confirmed, review.ReviewerId);
            try
            {
                await _db.SaveChangesAsync();
            }
            catch
            {
                if (!string.IsNullOrEmpty(retryDestKey))
                {
                    try { await _s3.DeleteAsync(retryDestKey); }
                    catch { /* best-effort cleanup */ }
                }
                throw;
            }
        }
        catch
        {
            // Cleanup orphaned clip if SaveChanges failed after copying
            if (!string.IsNullOrEmpty(destKey))
            {
                try { await _s3.DeleteAsync(destKey); }
                catch { /* best-effort cleanup */ }
            }
            throw;
        }
        return Ok(alert);
    }

    /// <summary>
    /// Dataset bookkeeping for the human-in-the-loop training pipeline.
    /// Confirm/FalsePositive with pattern data upserts the sample (one per alert) and
    /// copies the clip into training-dataset storage. Dismiss excludes an existing sample;
    /// NeedsFollowUp marks it pending. Never fails the review itself.
    /// Returns the destination key if a clip was copied (for cleanup on SaveChanges failure).
    /// </summary>
    private async Task<string?> UpsertTrainingSampleAsync(
        Alert alert, ReviewAction action, List<string>? confirmed, Guid reviewerId)
    {
        var existing = await _db.TrainingSamples
            .Include(t => t.Patterns)
            .FirstOrDefaultAsync(t => t.AlertId == alert.Id);

        if (action is ReviewAction.Dismiss)
        {
            // Dismiss carries no ground truth — never auto-create a sample.
            if (existing is not null)
            {
                existing.DatasetStatus = DatasetStatus.Excluded;
                existing.IncludeInTraining = false;
                existing.ReviewOutcome = action;
                existing.UpdatedAt = DateTimeOffset.UtcNow;
            }
            return null;
        }

        if (action is ReviewAction.NeedsFollowUp)
        {
            // Undetermined — keep labels but hold the sample out of training.
            if (existing is not null)
            {
                existing.DatasetStatus = DatasetStatus.PendingReview;
                existing.ReviewOutcome = action;
                existing.UpdatedAt = DateTimeOffset.UtcNow;
            }
            return null;
        }

        // Confirm / FalsePositive: only clients that sent pattern data create samples.
        if (confirmed is null) return null;

        var detected = (await _db.AiEvents
                .Where(e => e.ClipId == alert.ClipId)
                .Select(e => e.EventType)
                .Distinct()
                .ToListAsync())
            .Select(e => e.ToString())
            .ToList();
        if (!string.IsNullOrEmpty(alert.AlertType)
            && Enum.TryParse<AiEventType>(alert.AlertType, true, out var alertPattern)
            && Enum.IsDefined(typeof(AiEventType), alertPattern))
        {
            var normalizedAlertType = alertPattern.ToString();
            if (!detected.Contains(normalizedAlertType))
                detected.Add(normalizedAlertType);
        }

        var sample = existing;
        if (sample is null)
        {
            sample = new TrainingSample { AlertId = alert.Id };
            _db.TrainingSamples.Add(sample);
        }

        sample.ClipId = alert.ClipId;
        sample.StoreId = alert.StoreId;
        sample.CameraId = alert.CameraId;
        sample.AlertType = alert.AlertType;
        sample.ReviewOutcome = action;
        sample.ReviewerId = reviewerId;
        sample.ModelVersion = alert.ModelVersion;
        sample.RuleVersion = alert.RuleVersion;
        sample.IncludeInTraining = true;
        sample.UpdatedAt = DateTimeOffset.UtcNow;

        // Recalculate per-pattern labels: confirmed → Positive, AI-only → HardNegative.
        _db.TrainingSamplePatterns.RemoveRange(sample.Patterns);
        sample.Patterns.Clear();
        foreach (var name in confirmed.Union(detected))
        {
            var isConfirmed = confirmed.Contains(name);
            sample.Patterns.Add(new TrainingSamplePattern
            {
                TrainingSampleId = sample.Id,
                Pattern = Enum.Parse<AiEventType>(name),
                AiDetected = detected.Contains(name),
                HumanConfirmed = isConfirmed,
                LabelStatus = isConfirmed ? PatternLabelStatus.Positive : PatternLabelStatus.HardNegative
            });
        }

        // Copy the clip into dedicated dataset storage so it survives alert retention.
        sample.SourceClipObjectKey =
            (!string.IsNullOrEmpty(alert.ClipUrl) && !alert.ClipUrl.StartsWith("http"))
                ? alert.ClipUrl : string.Empty;
        var destKey = $"training-dataset/{alert.StoreId}/{sample.Id}/clip.mp4";

        if (!string.IsNullOrEmpty(sample.DatasetClipObjectKey)
            && await _s3.ExistsAsync(sample.DatasetClipObjectKey))
        {
            sample.DatasetStatus = DatasetStatus.Ready;  // already copied (re-review)
            return null;  // no new copy created
        }
        else if (string.IsNullOrEmpty(sample.SourceClipObjectKey)
                 || !await _s3.ExistsAsync(sample.SourceClipObjectKey))
        {
            sample.DatasetStatus = DatasetStatus.ClipUnavailable;
            return null;
        }
        else
        {
            try
            {
                await _s3.CopyAsync(sample.SourceClipObjectKey, destKey);
                sample.DatasetClipObjectKey = destKey;
                sample.DatasetStatus = DatasetStatus.Ready;
                return destKey;  // clip copied, return key for cleanup if SaveChanges fails
            }
            catch
            {
                // Copy failure must not lose the review; retried on next re-review.
                sample.DatasetStatus = DatasetStatus.CopyFailed;
                return null;
            }
        }
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

