using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Domain;
using Onevo.Api.Services;

namespace Onevo.Api.Controllers;

[ApiController]
[Route("api/ai-events")]
public class AiEventsController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly IConfiguration _cfg;
    private readonly RiskEngine _risk;
    private readonly S3Service _s3;

    public AiEventsController(OnevoDbContext db, IConfiguration cfg, RiskEngine risk, S3Service s3)
    {
        _db = db;
        _cfg = cfg;
        _risk = risk;
        _s3 = s3;
    }

    // Called by the cloud-ai worker. Authenticated with the shared service (bootstrap) key.
    [AllowAnonymous]
    [HttpPost]
    public async Task<IActionResult> Ingest(AiEventsBatchRequest req)
    {
        var serviceKey = _cfg["Seed:ConnectorBootstrapKey"];
        if (!Request.Headers.TryGetValue("X-Service-Key", out var provided) ||
            string.IsNullOrEmpty(serviceKey) || provided.ToString() != serviceKey)
            return Unauthorized();

        var clip = await _db.Clips.FindAsync(req.ClipId);
        if (clip is null) return NotFound(new { error = "Unknown clip" });

        var camera = await _db.Cameras.FirstOrDefaultAsync(c => c.Id == clip.CameraId);
        if (camera is null) return BadRequest(new { error = "Unknown camera" });

        // Persist AI events.
        var saved = new List<AiEvent>();
        foreach (var e in req.Events)
        {
            if (!Enum.TryParse<AiEventType>(e.EventType, true, out var type)) continue;
            var ev = new AiEvent
            {
                ClipId = clip.Id,
                CameraId = clip.CameraId,
                TrackId = e.TrackId,
                ZoneId = e.ZoneId,
                EventType = type,
                Value = e.Value,
                Confidence = e.Confidence,
                StartTs = e.StartTs,
                EndTs = e.EndTs,
                EvidenceFramesJson = JsonSerializer.Serialize(e.EvidenceFrames ?? Array.Empty<int>()),
                ModelVersion = req.ModelVersion
            };
            _db.AiEvents.Add(ev);
            saved.Add(ev);
        }

        clip.Status = ClipStatus.Analyzed;
        clip.AnalyzedAt = DateTimeOffset.UtcNow;
        await _db.SaveChangesAsync();

        // Score via the Risk Engine.
        var cfg = await _risk.ResolveConfigAsync(camera.StoreId, camera.Id);
        var result = _risk.Score(saved, cfg);

        _db.RiskEvents.Add(new RiskEvent
        {
            CameraId = clip.CameraId,
            ClipId = clip.Id,
            Source = "camera",
            Score = result.Score,
            DetailsJson = JsonSerializer.Serialize(new { result.AlertType, result.Level, result.Evidence })
        });

        Alert? alert = null;
        // 0-39 => event log only (RiskEvent). 40+ => create a reviewable/analytics alert.
        if (result.Score >= cfg.LowBand)
        {
            var clipUrl = await _s3.PresignedGetAsync(clip.ObjectKey, 3600);
            alert = new Alert
            {
                StoreId = camera.StoreId,
                CameraId = clip.CameraId,
                ZoneId = result.PrimaryZoneId,
                ClipId = clip.Id,
                AlertType = result.AlertType,
                RiskLevel = result.Level,
                RiskScore = result.Score,
                EvidenceJson = JsonSerializer.Serialize(result.Evidence),
                ClipUrl = clipUrl,
                ModelVersion = req.ModelVersion,
                RuleVersion = RiskConfig.RuleVersion,
                Status = AlertStatus.PendingReview
            };
            _db.Alerts.Add(alert);
        }

        await _db.SaveChangesAsync();
        return Ok(new { clipId = clip.Id, score = result.Score, level = result.Level.ToString(), alertId = alert?.Id });
    }
}
