using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Auth;
using Onevo.Api.Contracts;
using Onevo.Api.Data;
using Onevo.Api.Services;
using StackExchange.Redis;

namespace Onevo.Api.Controllers;

[ApiController]
[Authorize(Roles = "Admin,Manager")]
[Route("api/logs")]
public class LogsController : ControllerBase
{
    private readonly OnevoDbContext _db;
    private readonly IConnectionMultiplexer? _redis;

    public LogsController(OnevoDbContext db, IConnectionMultiplexer? redis = null)
    {
        _db = db;
        _redis = redis;
    }

    [HttpGet("system")]
    public async Task<ActionResult<SystemLogsResponse>> System([FromQuery] Guid? storeId)
    {
        if (storeId is not null && !TenantAccess.CanAccessStore(User, storeId.Value))
            return Forbid();

        var connectors = TenantAccess.ScopeConnectors(_db.Connectors, User);
        if (storeId is not null)
            connectors = connectors.Where(c => c.StoreId == storeId);

        var rows = await connectors
            .OrderByDescending(c => c.LastHeartbeat)
            .Select(c => new ConnectorLogEntry(
                c.Id,
                c.StoreId,
                c.Name,
                c.Status.ToString(),
                c.Version,
                c.LastHeartbeat,
                c.DegradedReason,
                c.UploadQueueDepth,
                c.DiskFreePct))
            .ToListAsync();

        var queueDepth = 0;
        var failedJobs = 0;
        if (_redis is not null)
        {
            var db = _redis.GetDatabase();
            queueDepth = (int)await db.ListLengthAsync(ClipQueue.QueueKey);
            failedJobs = (int)await db.ListLengthAsync(ClipQueue.FailedQueueKey);
        }

        return Ok(new SystemLogsResponse(rows, queueDepth, failedJobs, DateTimeOffset.UtcNow));
    }
}
