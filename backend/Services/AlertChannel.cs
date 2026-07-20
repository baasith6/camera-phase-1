/* Alert SSE channel — in-memory broadcast for real-time dashboard updates.

A singleton `AlertChannel` is registered in DI. When the AI ingest pipeline
creates an alert, it writes an `AlertSseEvent` here. The SSE endpoint
(`GET /api/alerts/stream`) reads from it and forwards to connected clients.

For a single-server Phase 1A deployment this is sufficient.
Phase 1B: swap the in-memory channel for Redis Pub/Sub.
*/
namespace Onevo.Api.Services;

/// <summary>Lightweight event pushed over SSE to dashboard clients.</summary>
public record AlertSseEvent(
    Guid AlertId,
    string AlertType,
    string RiskLevel,
    int RiskScore,
    Guid StoreId,
    DateTimeOffset CreatedAt);

/// <summary>Thread-safe broadcast channel for SSE alert push.</summary>
public sealed class AlertChannel
{
    // Unbounded channel — the SSE endpoint drains it per connection.
    private readonly System.Threading.Channels.Channel<AlertSseEvent> _channel =
        System.Threading.Channels.Channel.CreateUnbounded<AlertSseEvent>(
            new System.Threading.Channels.UnboundedChannelOptions
            {
                SingleWriter = false,
                SingleReader = false
            });

    /// <summary>Write a new alert event (called from AiEventsController).</summary>
    public void Publish(AlertSseEvent ev) => _channel.Writer.TryWrite(ev);

    /// <summary>Read events as they arrive (used by the SSE endpoint).</summary>
    public System.Threading.Channels.ChannelReader<AlertSseEvent> Reader => _channel.Reader;
}
