using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Services;

public class TheftOrchestrator
{
    private readonly IServiceProvider _sp;
    private readonly ILogger<TheftOrchestrator> _logger;

    public TheftOrchestrator(IServiceProvider sp, ILogger<TheftOrchestrator> logger)
    {
        _sp = sp;
        _logger = logger;
    }

    /// <summary>
    /// Checks if a newly saved AiEvent (with an embedding) matches prior events on other cameras
    /// to form a multi-camera theft pattern.
    /// </summary>
    public async Task EvaluateCrossCameraTheftAsync(Guid storeId, List<AiEvent> recentEvents)
    {
        using var scope = _sp.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<OnevoDbContext>();
        
        var relevantEvents = recentEvents.Where(e => e.EmbeddingJson != null && e.EmbeddingJson != "null").ToList();
        if (!relevantEvents.Any()) return;

        // Fetch recent events for this store that have embeddings (last 30 minutes)
        var thirtyMinsAgo = DateTimeOffset.UtcNow.AddMinutes(-30);
        
        // We know Clip -> Camera -> StoreId
        var cameraIds = await db.Cameras.Where(c => c.StoreId == storeId).Select(c => c.Id).ToListAsync();

        var historicEvents = await db.AiEvents
            .Where(e => e.CreatedAt >= thirtyMinsAgo && e.EmbeddingJson != null && e.EmbeddingJson != "null" && cameraIds.Contains(e.CameraId))
            .ToListAsync();

        foreach (var ev in relevantEvents)
        {
            if (ev.EventType == AiEventType.ExitWithoutCheckout || ev.EventType == AiEventType.ShelfPickupNoCheckout)
            {
                var exitEmbedding = JsonSerializer.Deserialize<float[]>(ev.EmbeddingJson!);
                if (exitEmbedding == null || exitEmbedding.Length == 0) continue;

                // Look for a pickup/concealment on a DIFFERENT camera
                var matchingPickups = historicEvents.Where(h => 
                    h.CameraId != ev.CameraId && 
                    (h.EventType == AiEventType.LowStaffRemoval || h.EventType == AiEventType.Concealment || h.EventType == AiEventType.ShelfPickupNoCheckout))
                    .ToList();

                foreach (var pickup in matchingPickups)
                {
                    var pickupEmbedding = JsonSerializer.Deserialize<float[]>(pickup.EmbeddingJson!);
                    if (pickupEmbedding == null || pickupEmbedding.Length == 0) continue;

                    var sim = CosineSimilarity(exitEmbedding, pickupEmbedding);
                    if (sim >= 0.75f) // threshold
                    {
                        _logger.LogInformation("CROSS-CAMERA THEFT DETECTED: Person picked up on {cam1} and exited on {cam2} with {sim} similarity", pickup.CameraId, ev.CameraId, sim);
                        
                        // Escalate by creating a high severity alert
                        db.Alerts.Add(new Alert
                        {
                            StoreId = storeId,
                            CameraId = ev.CameraId, // alert on the exit camera
                            ZoneId = ev.ZoneId,
                            ClipId = ev.ClipId,
                            AlertType = "CrossCameraTheft",
                            RiskLevel = RiskLevel.High,
                            RiskScore = 95,
                            EvidenceJson = JsonSerializer.Serialize(new {
                                MatchSimilarity = sim,
                                PickupCameraId = pickup.CameraId,
                                ExitCameraId = ev.CameraId,
                            }),
                            ClipUrl = "multi-camera-event", 
                            Status = AlertStatus.PendingReview
                        });
                        
                        break; // generated one alert for this exit
                    }
                }
            }
        }

        await db.SaveChangesAsync();
    }

    private static float CosineSimilarity(float[] vector1, float[] vector2)
    {
        if (vector1.Length != vector2.Length) return 0f;
        float dotProduct = 0;
        float normA = 0;
        float normB = 0;
        for (int i = 0; i < vector1.Length; i++)
        {
            dotProduct += vector1[i] * vector2[i];
            normA += vector1[i] * vector1[i];
            normB += vector2[i] * vector2[i];
        }
        if (normA == 0 || normB == 0) return 0;
        return dotProduct / (float)(Math.Sqrt(normA) * Math.Sqrt(normB));
    }
}
