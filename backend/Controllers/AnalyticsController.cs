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
[Route("api/analytics")]
public class AnalyticsController : ControllerBase
{
    private readonly OnevoDbContext _db;

    public AnalyticsController(OnevoDbContext db) => _db = db;

    [HttpGet("summary")]
    public async Task<ActionResult<AnalyticsSummaryResponse>> Summary([FromQuery] Guid? storeId)
    {
        if (storeId is not null && !TenantAccess.CanAccessStore(User, storeId.Value))
            return Forbid();

        var alerts = TenantAccess.ScopeAlerts(_db.Alerts, User);
        IQueryable<Clip> clips = from c in _db.Clips
                                   join cam in TenantAccess.ScopeCameras(_db.Cameras, User)
                                       on c.CameraId equals cam.Id
                                   select c;

        if (storeId is not null)
        {
            alerts = alerts.Where(a => a.StoreId == storeId);
            clips = from c in clips
                    join cam in _db.Cameras on c.CameraId equals cam.Id
                    where cam.StoreId == storeId
                    select c;
        }

        var alertRows = await alerts.AsNoTracking().ToListAsync();
        var clipCount = await clips.CountAsync();
        var analyzedClips = await clips.CountAsync(c => c.Status == ClipStatus.Analyzed);

        return Ok(new AnalyticsSummaryResponse(
            TotalAlerts: alertRows.Count,
            PendingAlerts: alertRows.Count(a => a.Status == AlertStatus.PendingReview),
            HighRiskAlerts: alertRows.Count(a => a.RiskLevel == RiskLevel.High),
            MediumRiskAlerts: alertRows.Count(a => a.RiskLevel == RiskLevel.Medium),
            FalsePositives: alertRows.Count(a => a.Status == AlertStatus.FalsePositive),
            TotalClips: clipCount,
            AnalyzedClips: analyzedClips,
            AlertsByType: alertRows
                .GroupBy(a => a.AlertType)
                .ToDictionary(g => g.Key, g => g.Count())
        ));
    }
}
