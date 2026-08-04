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

/// <summary>
/// Training dataset collected from human alert reviews (Stage 1+2).
/// Clip-level multi-label classification data only — no spatial/temporal annotation.
/// </summary>
[ApiController]
[Authorize(Roles = "Admin")]
[Route("api/training")]
public class TrainingController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly S3Service _s3;

    public TrainingController(OnevoDbContext db, S3Service s3)
    {
        _db = db;
        _s3 = s3;
    }

    // Admin sees all samples; Manager scoped to their store (same semantics as ScopeAlerts).
    private IQueryable<TrainingSample> Scoped(IQueryable<TrainingSample> query)
    {
        if (TenantAccess.IsAdmin(User)) return query;
        var storeId = TenantAccess.CurrentStoreId(User);
        return storeId is null ? query.Where(_ => false) : query.Where(t => t.StoreId == storeId);
    }

    [HttpGet("samples")]
    public async Task<IActionResult> List([FromQuery] Guid? storeId, [FromQuery] string? status)
    {
        var query = Scoped(_db.TrainingSamples.Include(t => t.Patterns));

        if (storeId is not null)
        {
            if (!TenantAccess.CanAccessStore(User, storeId.Value)) return Forbid();
            query = query.Where(t => t.StoreId == storeId);
        }
        if (status is not null && Enum.TryParse<DatasetStatus>(status, true, out var st))
            query = query.Where(t => t.DatasetStatus == st);

        var rows = await query.OrderByDescending(t => t.UpdatedAt).Take(500).ToListAsync();

        var meta = await LoadMetaAsync(rows);
        var items = rows.Select(t => new TrainingSampleListItem(
            t.Id,
            t.AlertId,
            t.ClipId,
            t.AlertType,
            t.Patterns.Where(p => p.AiDetected).Select(p => p.Pattern.ToString()).ToList(),
            t.Patterns.Where(p => p.HumanConfirmed).Select(p => p.Pattern.ToString()).ToList(),
            t.Patterns.Count(p => p.LabelStatus == PatternLabelStatus.Positive),
            t.Patterns.Count(p => p.LabelStatus == PatternLabelStatus.HardNegative),
            t.ReviewOutcome.ToString(),
            t.DatasetStatus.ToString(),
            t.IncludeInTraining,
            meta.Reviewers.GetValueOrDefault(t.ReviewerId, ""),
            t.ModelVersion,
            meta.Stores.GetValueOrDefault(t.StoreId, ""),
            meta.Cameras.GetValueOrDefault(t.CameraId, ""),
            t.CreatedAt,
            t.UpdatedAt)).ToList();

        return Ok(items);
    }

    [HttpGet("samples/{id:guid}")]
    public async Task<IActionResult> Get(Guid id)
    {
        var sample = await _db.TrainingSamples
            .Include(t => t.Patterns)
            .FirstOrDefaultAsync(t => t.Id == id);
        if (sample is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, sample.StoreId)) return Forbid();

        // Presign the dataset copy; fall back to the source clip if the copy is missing.
        string? clipUrl = null;
        foreach (var key in new[] { sample.DatasetClipObjectKey, sample.SourceClipObjectKey })
        {
            if (string.IsNullOrEmpty(key)) continue;
            if (await _s3.ExistsAsync(key))
            {
                try { clipUrl = await _s3.PresignedGetAsync(key, 86400); }
                catch { /* S3 unavailable — return null URL gracefully */ }
                break;
            }
        }

        var meta = await LoadMetaAsync([sample]);
        return Ok(new TrainingSampleDetail(
            sample.Id,
            sample.AlertId,
            sample.ClipId,
            sample.AlertType,
            sample.Patterns
                .OrderBy(p => p.Pattern.ToString())
                .Select(p => new TrainingPatternLabel(
                    p.Pattern.ToString(), p.AiDetected, p.HumanConfirmed, p.LabelStatus.ToString()))
                .ToList(),
            sample.ReviewOutcome.ToString(),
            sample.DatasetStatus.ToString(),
            sample.IncludeInTraining,
            meta.Reviewers.GetValueOrDefault(sample.ReviewerId, ""),
            sample.ModelVersion,
            sample.RuleVersion,
            meta.Stores.GetValueOrDefault(sample.StoreId, ""),
            meta.Cameras.GetValueOrDefault(sample.CameraId, ""),
            clipUrl,
            sample.EditHistoryJson,
            sample.CreatedAt,
            sample.UpdatedAt));
    }

    // PUT /api/training/samples/{id}/labels — correct confirmed patterns from the Training page.
    [HttpPut("samples/{id:guid}/labels")]
    public async Task<IActionResult> UpdateLabels(Guid id, UpdateLabelsRequest req)
    {
        var sample = await _db.TrainingSamples
            .Include(t => t.Patterns)
            .FirstOrDefaultAsync(t => t.Id == id);
        if (sample is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, sample.StoreId)) return Forbid();

        var confirmed = new List<string>();
        foreach (var p in req.ConfirmedPatterns ?? [])
        {
            if (!Enum.TryParse<AiEventType>(p, true, out var pattern))
                return BadRequest(new { error = $"Unknown pattern '{p}'" });
            var name = pattern.ToString();
            if (confirmed.Contains(name))
                return BadRequest(new { error = $"Duplicate pattern '{p}'" });
            confirmed.Add(name);
        }

        // Recompute labels, preserving which patterns the AI originally detected.
        var detected = sample.Patterns.Where(p => p.AiDetected).Select(p => p.Pattern.ToString()).ToList();
        _db.TrainingSamplePatterns.RemoveRange(sample.Patterns);
        sample.Patterns.Clear();
        foreach (var name in confirmed.Union(detected))
        {
            var isConfirmed = confirmed.Contains(name);
            var pattern = new TrainingSamplePattern
            {
                TrainingSampleId = sample.Id,
                Pattern = Enum.Parse<AiEventType>(name),
                AiDetected = detected.Contains(name),
                HumanConfirmed = isConfirmed,
                LabelStatus = isConfirmed ? PatternLabelStatus.Positive : PatternLabelStatus.HardNegative
            };
            sample.Patterns.Add(pattern);
            // Explicit Add: the client-generated Guid key would otherwise make
            // change tracking treat the new row as Modified (UPDATE → 0 rows → concurrency error).
            _db.TrainingSamplePatterns.Add(pattern);
        }

        // Append-only edit audit.
        var history = JsonSerializer.Deserialize<List<JsonElement>>(sample.EditHistoryJson) ?? [];
        history.Add(JsonSerializer.SerializeToElement(new
        {
            by = TenantAccess.CurrentUserId(User),
            at = DateTimeOffset.UtcNow,
            patterns = confirmed
        }));
        sample.EditHistoryJson = JsonSerializer.Serialize(history);

        if (sample.DatasetStatus is not DatasetStatus.Excluded
            and not DatasetStatus.ClipUnavailable
            and not DatasetStatus.CopyFailed)
        {
            sample.DatasetStatus = DatasetStatus.Ready;
        }
        sample.UpdatedAt = DateTimeOffset.UtcNow;

        await _db.SaveChangesAsync();
        return await Get(id);
    }

    // PUT /api/training/samples/{id}/include — include or exclude from future training.
    [HttpPut("samples/{id:guid}/include")]
    public async Task<IActionResult> SetInclude(Guid id, IncludeRequest req)
    {
        var sample = await _db.TrainingSamples.FirstOrDefaultAsync(t => t.Id == id);
        if (sample is null) return NotFound();
        if (!TenantAccess.CanAccessStore(User, sample.StoreId)) return Forbid();

        sample.IncludeInTraining = req.Include;
        // Only flip Ready <-> Excluded; clip-problem statuses stay visible.
        if (!req.Include && sample.DatasetStatus is DatasetStatus.Ready or DatasetStatus.PendingReview)
            sample.DatasetStatus = DatasetStatus.Excluded;
        else if (req.Include && sample.DatasetStatus is DatasetStatus.Excluded)
            sample.DatasetStatus = DatasetStatus.Ready;
        sample.UpdatedAt = DateTimeOffset.UtcNow;

        await _db.SaveChangesAsync();
        return await Get(id);
    }

    [HttpGet("stats")]
    public async Task<IActionResult> Stats([FromQuery] Guid? storeId)
    {
        var query = Scoped(_db.TrainingSamples.Include(t => t.Patterns));
        if (storeId is not null)
        {
            if (!TenantAccess.CanAccessStore(User, storeId.Value)) return Forbid();
            query = query.Where(t => t.StoreId == storeId);
        }

        var samples = await query.ToListAsync();
        var storeNames = await _db.Stores.ToDictionaryAsync(s => s.Id, s => s.Name);

        var positive = new Dictionary<string, int>();
        var hardNegative = new Dictionary<string, int>();
        foreach (var p in samples.SelectMany(t => t.Patterns))
        {
            var name = p.Pattern.ToString();
            if (p.LabelStatus == PatternLabelStatus.Positive)
                positive[name] = positive.GetValueOrDefault(name) + 1;
            else if (p.LabelStatus == PatternLabelStatus.HardNegative)
                hardNegative[name] = hardNegative.GetValueOrDefault(name) + 1;
        }

        return Ok(new TrainingStatsResponse(
            samples.Count,
            samples.Count(t => t.DatasetStatus == DatasetStatus.Ready),
            samples.Count(t => t.DatasetStatus == DatasetStatus.PendingReview),
            samples.Count(t => t.DatasetStatus == DatasetStatus.Excluded),
            samples.Count(t => t.DatasetStatus is DatasetStatus.ClipUnavailable or DatasetStatus.CopyFailed),
            positive,
            hardNegative,
            samples.GroupBy(t => t.ModelVersion).ToDictionary(g => g.Key, g => g.Count()),
            samples.GroupBy(t => t.StoreId)
                .ToDictionary(g => storeNames.GetValueOrDefault(g.Key, g.Key.ToString()), g => g.Count())));
    }

    // Stage 3 placeholder — actual training is not part of this build.
    [HttpPost("train")]
    public IActionResult Train()
        => StatusCode(501, new { error = "Model training is not available yet." });

    private async Task<(Dictionary<Guid, string> Reviewers, Dictionary<Guid, string> Stores,
        Dictionary<Guid, string> Cameras)> LoadMetaAsync(IReadOnlyCollection<TrainingSample> samples)
    {
        var reviewerIds = samples.Select(t => t.ReviewerId).Distinct().ToList();
        var storeIds = samples.Select(t => t.StoreId).Distinct().ToList();
        var cameraIds = samples.Select(t => t.CameraId).Distinct().ToList();

        var reviewers = await _db.Users
            .Where(u => reviewerIds.Contains(u.Id))
            .ToDictionaryAsync(u => u.Id, u => u.Email);
        var stores = await _db.Stores
            .Where(s => storeIds.Contains(s.Id))
            .ToDictionaryAsync(s => s.Id, s => s.Name);
        var cameras = await _db.Cameras
            .Where(c => cameraIds.Contains(c.Id))
            .ToDictionaryAsync(c => c.Id, c => c.Name);
        return (reviewers, stores, cameras);
    }
}
