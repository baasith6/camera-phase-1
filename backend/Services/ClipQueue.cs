using StackExchange.Redis;

namespace Onevo.Api.Services;

// Publishes clip-analysis jobs to a Redis list consumed by the cloud-ai worker.
public class ClipQueue
{
    public const string QueueKey = "onevo:clip-jobs";
    private readonly IConnectionMultiplexer _redis;

    public ClipQueue(IConnectionMultiplexer redis) => _redis = redis;

    public async Task EnqueueAsync(Guid clipId, string objectKey, Guid cameraId)
    {
        var db = _redis.GetDatabase();
        var payload = System.Text.Json.JsonSerializer.Serialize(new
        {
            clipId,
            objectKey,
            cameraId
        });
        await db.ListLeftPushAsync(QueueKey, payload);
    }
}
