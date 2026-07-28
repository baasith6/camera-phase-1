using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Onevo.Api.Contracts;
using Onevo.Api.Services;
using StackExchange.Redis;

namespace Onevo.Api.Controllers;

[ApiController]
[Route("api/health")]
public class HealthController : ControllerBase
{
    private readonly IConnectionMultiplexer? _redis;

    public HealthController(IConnectionMultiplexer? redis = null)
    {
        _redis = redis;
    }

    [AllowAnonymous]
    [HttpGet]
    public IActionResult Get() => Ok(new { status = "ok", ts = DateTimeOffset.UtcNow });

    [Authorize(Roles = "Admin")]
    [HttpGet("pipeline")]
    public async Task<ActionResult<PipelineHealthResponse>> Pipeline()
    {
        if (_redis is null)
            return Ok(new PipelineHealthResponse(0, 0));

        var db = _redis.GetDatabase();
        var queueDepth = (int)await db.ListLengthAsync(ClipQueue.QueueKey);
        var failedJobs = (int)await db.ListLengthAsync(ClipQueue.FailedQueueKey);
        return Ok(new PipelineHealthResponse(queueDepth, failedJobs));
    }
}
