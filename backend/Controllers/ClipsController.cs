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
[Route("api/clips")]
public class ClipsController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly S3Service _s3;
    private readonly ClipQueue _queue;
    private readonly ConnectorAuthenticationService _connectorAuth;

    public ClipsController(
        OnevoDbContext db,
        S3Service s3,
        ClipQueue queue,
        ConnectorAuthenticationService connectorAuth)
    {
        _db = db;
        _s3 = s3;
        _queue = queue;
        _connectorAuth = connectorAuth;
    }

    // Connector requests a short-lived signed upload URL for a new candidate clip.
    [AllowAnonymous]
    [HttpPost("upload-url")]
    public async Task<ActionResult<UploadUrlResponse>> UploadUrl(UploadUrlRequest req)
    {
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();
        var camera = await _db.Cameras
            .AsNoTracking()
            .FirstOrDefaultAsync(c => c.Id == req.CameraId, HttpContext.RequestAborted);
        if (camera is null)
            return BadRequest(new { error = "Unknown camera" });
        if (camera.StoreId != connector.StoreId || camera.ConnectorId != connector.Id)
            return Forbid();

        var clip = new Clip
        {
            CameraId = req.CameraId,
            ConnectorId = connector.Id,
            DurationSec = req.DurationSec,
            TriggerReason = req.TriggerReason ?? "motion",
            Status = ClipStatus.Pending
        };
        clip.ObjectKey = $"clips/{clip.Id}.mp4";
        _db.Clips.Add(clip);
        await _db.SaveChangesAsync();

        const int expiry = 3600;
        var url = await _s3.PresignedPutAsync(clip.ObjectKey, expiry);
        return new UploadUrlResponse(clip.Id, clip.ObjectKey, url, expiry);
    }

    // Connector confirms upload finished; we verify the object and enqueue an analysis job.
    [AllowAnonymous]
    [HttpPost("{id:guid}/complete")]
    public async Task<IActionResult> Complete(Guid id, CompleteClipRequest req)
    {
        var connector = await _connectorAuth.AuthenticateAsync(Request, HttpContext.RequestAborted);
        if (connector is null) return Unauthorized();

        var clip = await _db.Clips.FindAsync(id);
        if (clip is null) return NotFound();
        if (clip.ConnectorId != connector.Id) return Forbid();

        if (!await _s3.ExistsAsync(clip.ObjectKey))
            return BadRequest(new { error = "Object not found in storage" });

        clip.Status = ClipStatus.Uploaded;
        await _db.SaveChangesAsync();
        await _queue.EnqueueAsync(clip.Id, clip.ObjectKey, clip.CameraId);
        return Ok(new { ok = true, clipId = clip.Id });
    }

    [Authorize]
    [HttpGet]
    public async Task<ActionResult<List<ClipListItemResponse>>> List(
        [FromQuery] Guid? storeId,
        [FromQuery] Guid? cameraId,
        [FromQuery] int limit = 100)
    {
        limit = Math.Clamp(limit, 1, 500);

        if (storeId is not null && !TenantAccess.CanAccessStore(User, storeId.Value))
            return Forbid();

        var cameraQuery = TenantAccess.ScopeCameras(_db.Cameras, User);
        if (storeId is not null)
            cameraQuery = cameraQuery.Where(c => c.StoreId == storeId);
        if (cameraId is not null)
            cameraQuery = cameraQuery.Where(c => c.Id == cameraId);

        var rows = await (
            from clip in _db.Clips
            join cam in cameraQuery on clip.CameraId equals cam.Id
            join store in _db.Stores on cam.StoreId equals store.Id
            orderby clip.CreatedAt descending
            select new { clip, cam, store }
        ).Take(limit).ToListAsync();

        if (rows.Count == 0)
            return Ok(new List<ClipListItemResponse>());

        var clipIds = rows.Select(r => r.clip.Id).ToList();

        var eventCounts = await _db.AiEvents
            .Where(e => clipIds.Contains(e.ClipId))
            .GroupBy(e => e.ClipId)
            .Select(g => new { ClipId = g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.ClipId, x => x.Count);

        var riskScores = await _db.RiskEvents
            .Where(r => clipIds.Contains(r.ClipId))
            .GroupBy(r => r.ClipId)
            .Select(g => new
            {
                ClipId = g.Key,
                Score = g.OrderByDescending(r => r.CreatedAt).Select(r => r.Score).First()
            })
            .ToDictionaryAsync(x => x.ClipId, x => x.Score);

        var alertIds = await _db.Alerts
            .Where(a => clipIds.Contains(a.ClipId))
            .Select(a => new { a.ClipId, a.Id })
            .ToDictionaryAsync(x => x.ClipId, x => x.Id);

        var items = rows.Select(r => new ClipListItemResponse(
            r.clip.Id,
            r.cam.Id,
            r.cam.Name,
            r.store.Id,
            r.store.Name,
            r.clip.Status.ToString(),
            r.clip.DurationSec,
            r.clip.TriggerReason,
            r.clip.CreatedAt,
            r.clip.AnalyzedAt,
            eventCounts.GetValueOrDefault(r.clip.Id),
            riskScores.TryGetValue(r.clip.Id, out var score) ? score : null,
            alertIds.GetValueOrDefault(r.clip.Id)
        )).ToList();

        return Ok(items);
    }

    [Authorize]
    [HttpGet("{id:guid}")]
    public async Task<ActionResult<ClipDetailResponse>> Get(Guid id)
    {
        var row = await (
            from clip in _db.Clips
            where clip.Id == id
            join cam in TenantAccess.ScopeCameras(_db.Cameras, User) on clip.CameraId equals cam.Id
            join store in _db.Stores on cam.StoreId equals store.Id
            select new { clip, cam, store }
        ).FirstOrDefaultAsync();

        if (row is null) return NotFound();

        string? url = null;
        if (row.clip.Status is ClipStatus.Uploaded or ClipStatus.Analyzed or ClipStatus.Processing)
        {
            if (await _s3.ExistsAsync(row.clip.ObjectKey))
            {
                try { url = await _s3.PresignedGetAsync(row.clip.ObjectKey, 3600); }
                catch { /* S3 unavailable — return null URL gracefully */ }
            }
        }

        var aiEvents = await _db.AiEvents
            .Where(e => e.ClipId == id)
            .OrderBy(e => e.StartTs)
            .ToListAsync();

        var zoneIds = aiEvents.Where(e => e.ZoneId.HasValue).Select(e => e.ZoneId!.Value).Distinct().ToList();
        var zoneNames = zoneIds.Count == 0
            ? new Dictionary<Guid, string>()
            : await _db.CameraZones
                .Where(z => zoneIds.Contains(z.Id))
                .ToDictionaryAsync(z => z.Id, z => z.Name);

        var latestRisk = await _db.RiskEvents
            .Where(r => r.ClipId == id)
            .OrderByDescending(r => r.CreatedAt)
            .FirstOrDefaultAsync();

        var alert = await _db.Alerts
            .Where(a => a.ClipId == id)
            .Select(a => new { a.Id })
            .FirstOrDefaultAsync();

        var modelVersion = aiEvents.FirstOrDefault()?.ModelVersion;
        var eventCount = aiEvents.Count;
        string? analysisNote = null;
        if (row.clip.Status == ClipStatus.Analyzed && eventCount == 0)
        {
            analysisNote =
                "No retail cues detected — common for test/synthetic video without visible shoppers.";
        }
        else if (row.clip.Status == ClipStatus.Uploaded)
        {
            analysisNote = "Uploaded — waiting for cloud-ai analysis (usually 30–60 seconds on CPU).";
        }

        return Ok(new ClipDetailResponse(
            row.clip.Id,
            row.cam.Id,
            row.cam.Name,
            row.store.Id,
            row.store.Name,
            row.clip.Status.ToString(),
            row.clip.DurationSec,
            row.clip.TriggerReason,
            row.clip.CreatedAt,
            row.clip.AnalyzedAt,
            url,
            eventCount,
            latestRisk?.Score,
            latestRisk?.DetailsJson,
            alert?.Id,
            modelVersion,
            analysisNote,
            aiEvents.Select(e => new ClipAiEventItemResponse(
                e.EventType.ToString(),
                e.ZoneId.HasValue && zoneNames.TryGetValue(e.ZoneId.Value, out var zn) ? zn : null,
                e.Value,
                e.Confidence,
                e.StartTs,
                e.EndTs,
                e.ModelVersion
            )).ToList()
        ));
    }

    [Authorize(Roles = "Admin,Manager")]
    [HttpDelete("{id:guid}")]
    public async Task<IActionResult> Delete(Guid id)
    {
        var result = await TryDeleteClipAsync(id);
        return result switch
        {
            DeleteClipResult.Deleted => Ok(new { ok = true, clipId = id }),
            DeleteClipResult.NotFound => NotFound(),
            DeleteClipResult.SkippedConfirmed => Conflict(new { error = "Cannot delete clip linked to a confirmed alert" }),
            _ => NotFound(),
        };
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

        var targetIds = await ResolveClipDeleteIdsAsync(req);
        if (targetIds is null)
            return BadRequest(new { error = "Provide ids or set deleteAllInStore with storeId" });

        var deleted = 0;
        var skipped = 0;
        var errors = new List<string>();

        foreach (var id in targetIds.Distinct())
        {
            var result = await TryDeleteClipAsync(id);
            switch (result)
            {
                case DeleteClipResult.Deleted:
                    deleted++;
                    break;
                case DeleteClipResult.SkippedConfirmed:
                    skipped++;
                    break;
                case DeleteClipResult.NotFound:
                    break;
            }
        }

        return Ok(new BulkDeleteResponse(deleted, skipped, errors));
    }

    private async Task<List<Guid>?> ResolveClipDeleteIdsAsync(BulkDeleteRequest req)
    {
        if (req.DeleteAllInStore)
        {
            if (req.StoreId is null) return null;
            if (!TenantAccess.CanAccessStore(User, req.StoreId.Value)) return null;

            return await (
                from clip in _db.Clips
                join cam in TenantAccess.ScopeCameras(_db.Cameras, User) on clip.CameraId equals cam.Id
                where cam.StoreId == req.StoreId
                select clip.Id
            ).ToListAsync();
        }

        if (req.Ids is { Count: > 0 }) return req.Ids;
        return null;
    }

    private enum DeleteClipResult { Deleted, NotFound, SkippedConfirmed }

    private async Task<DeleteClipResult> TryDeleteClipAsync(Guid id)
    {
        var row = await (
            from clip in _db.Clips
            where clip.Id == id
            join cam in TenantAccess.ScopeCameras(_db.Cameras, User) on clip.CameraId equals cam.Id
            select new { clip, cam }
        ).FirstOrDefaultAsync();

        if (row is null) return DeleteClipResult.NotFound;

        var alert = await _db.Alerts
            .Include(a => a.Reviews)
            .FirstOrDefaultAsync(a => a.ClipId == id);

        if (alert is not null && alert.Status == AlertStatus.Confirmed)
            return DeleteClipResult.SkippedConfirmed;

        if (!string.IsNullOrEmpty(row.clip.ObjectKey))
            await _s3.DeleteAsync(row.clip.ObjectKey);

        var aiEvents = await _db.AiEvents.Where(e => e.ClipId == id).ToListAsync();
        var riskEvents = await _db.RiskEvents.Where(r => r.ClipId == id).ToListAsync();
        _db.AiEvents.RemoveRange(aiEvents);
        _db.RiskEvents.RemoveRange(riskEvents);

        if (alert is not null)
        {
            _db.AlertReviews.RemoveRange(alert.Reviews);
            _db.Alerts.Remove(alert);
        }

        _db.Clips.Remove(row.clip);
        await _db.SaveChangesAsync();
        return DeleteClipResult.Deleted;
    }
}
