namespace Onevo.Api.Domain;

public class User
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Email { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;
    public UserRole Role { get; set; } = UserRole.Reviewer;
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public class Store
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Name { get; set; } = string.Empty;
    public string Organization { get; set; } = "default";
    public AlertVisibilityMode AlertVisibilityMode { get; set; } = AlertVisibilityMode.Silent;
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

    public List<Camera> Cameras { get; set; } = new();
}

public class Camera
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid StoreId { get; set; }
    public Store? Store { get; set; }
    public string Name { get; set; } = string.Empty;
    public string RtspUrl { get; set; } = string.Empty;
    public CameraStatus Status { get; set; } = CameraStatus.Pending;
    public DateTimeOffset? LastSeen { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

    public List<CameraZone> Zones { get; set; } = new();
}

public class CameraZone
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid CameraId { get; set; }
    public Camera? Camera { get; set; }
    public string Name { get; set; } = string.Empty;
    public ZoneType ZoneType { get; set; } = ZoneType.Shelf;
    // Normalized polygon points [[x,y],...] in 0..1 image coordinates, JSON encoded.
    public string PolygonJson { get; set; } = "[]";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public class Connector
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid StoreId { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Version { get; set; } = string.Empty;
    public string ApiKeyHash { get; set; } = string.Empty;
    public ConnectorStatus Status { get; set; } = ConnectorStatus.Unknown;
    public DateTimeOffset? LastHeartbeat { get; set; }
    public double DiskFreePct { get; set; } = 100;
    public int UploadQueueDepth { get; set; } = 0;
    public string? DegradedReason { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public class Clip
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid CameraId { get; set; }
    public Guid? ConnectorId { get; set; }
    public string ObjectKey { get; set; } = string.Empty;
    public ClipStatus Status { get; set; } = ClipStatus.Pending;
    public double DurationSec { get; set; }
    public string TriggerReason { get; set; } = "motion";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset? AnalyzedAt { get; set; }
}

public class AiEvent
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid ClipId { get; set; }
    public Guid CameraId { get; set; }
    public int TrackId { get; set; }
    public Guid? ZoneId { get; set; }
    public AiEventType EventType { get; set; }
    // Numeric payload: dwell seconds, handling count, or bag-open confidence-derived value.
    public double Value { get; set; }
    public double Confidence { get; set; }
    public DateTimeOffset StartTs { get; set; }
    public DateTimeOffset EndTs { get; set; }
    public string EvidenceFramesJson { get; set; } = "[]";
    public string ModelVersion { get; set; } = "unknown";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public class RiskEvent
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid CameraId { get; set; }
    public Guid ClipId { get; set; }
    public string Source { get; set; } = "camera";
    public int Score { get; set; }
    public string DetailsJson { get; set; } = "{}";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public class Alert
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid StoreId { get; set; }
    public Guid CameraId { get; set; }
    public Guid? ZoneId { get; set; }
    public Guid ClipId { get; set; }
    public string AlertType { get; set; } = string.Empty;
    public RiskLevel RiskLevel { get; set; } = RiskLevel.None;
    public int RiskScore { get; set; }
    // Evidence-language strings only (never "theft"): JSON array of strings.
    public string EvidenceJson { get; set; } = "[]";
    public AlertStatus Status { get; set; } = AlertStatus.PendingReview;
    public string? ClipUrl { get; set; }
    public string ModelVersion { get; set; } = "unknown";
    public string RuleVersion { get; set; } = "v4-starter-1.0";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

    public List<AlertReview> Reviews { get; set; } = new();
}

public class AlertReview
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid AlertId { get; set; }
    public Alert? Alert { get; set; }
    public Guid ReviewerId { get; set; }
    public ReviewAction Action { get; set; }
    public string? ReasonCode { get; set; }
    public string? Notes { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

// Scoped risk configuration. Null scope fields = applies as store-wide/global default.
public class RuleConfig
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid? StoreId { get; set; }
    public Guid? CameraId { get; set; }
    public Guid? ZoneId { get; set; }
    // JSON: weights + thresholds. See RiskEngine for schema.
    public string ConfigJson { get; set; } = "{}";
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;
}
