using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
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
        if (!await _connectorAuth.OwnsCameraAsync(connector, req.CameraId, HttpContext.RequestAborted))
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
    [HttpGet("{id:guid}")]
    public async Task<IActionResult> Get(Guid id)
    {
        var clip = await _db.Clips.FindAsync(id);
        if (clip is null) return NotFound();
        string? url = null;
        if (clip.Status is ClipStatus.Uploaded or ClipStatus.Analyzed or ClipStatus.Processing)
            url = await _s3.PresignedGetAsync(clip.ObjectKey, 3600);
        return Ok(new { clip, clipUrl = url });
    }
}
