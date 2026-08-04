namespace Onevo.Api.Domain;

public class User
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Email { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;
    public UserRole Role { get; set; } = UserRole.Reviewer;
    /// <summary>When set, Manager/Reviewer users are scoped to this store.</summary>
    public Guid? StoreId { get; set; }
    public Store? Store { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

public class Store
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string Name { get; set; } = string.Empty;
    public string Organization { get; set; } = "default";
    public AlertVisibilityMode AlertVisibilityMode { get; set; } = AlertVisibilityMode.ManagerOnly;
    /// <summary>Gmail or Workspace address for medium/high alert notifications.</summary>
    public string? NotificationEmail { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

    public List<Camera> Cameras { get; set; } = new();
    public Connector? Connector { get; set; }
    public List<User> Users { get; set; } = new();
}

public class Camera
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid StoreId { get; set; }
    public Store? Store { get; set; }
    public Guid? ConnectorId { get; set; }
    public Connector? Connector { get; set; }
    public string? SourceKey { get; set; }
    public string Name { get; set; } = string.Empty;
    public string RtspUrl { get; set; } = string.Empty;
    public CameraStatus Status { get; set; } = CameraStatus.Pending;
    public DateTimeOffset? LastSeen { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

    // ONVIF metadata (populated by connector after ONVIF query)
    public string? OnvifHost { get; set; }
    public int? OnvifPort { get; set; }
    public string? CameraManufacturer { get; set; }
    public string? CameraModel { get; set; }
    public string? CameraSerial { get; set; }
    public string? CameraFirmware { get; set; }
    /// <summary>MinIO object captured while zones were last created or updated.</summary>
    public string? ReferenceFrameObjectKey { get; set; }
    public DateTimeOffset? ReferenceFrameCapturedAt { get; set; }

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
    public Store? Store { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Version { get; set; } = string.Empty;
    public string ApiKeyHash { get; set; } = string.Empty;
    public ConnectorStatus Status { get; set; } = ConnectorStatus.Unknown;
    public DateTimeOffset? LastHeartbeat { get; set; }
    /// <summary>Reachable admin UI host reported by connector heartbeat (shop PC LAN IP).</summary>
    public string? AdminHost { get; set; }
    public int? AdminPort { get; set; }
    public double DiskFreePct { get; set; } = 100;
    public int UploadQueueDepth { get; set; } = 0;
    public string? DegradedReason { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public List<Camera> Cameras { get; set; } = new();
}

/// <summary>Short-lived code generated on the dashboard for the Windows setup wizard.</summary>
public class ConnectorSetupCode
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid StoreId { get; set; }
    public string CodeHash { get; set; } = string.Empty;
    public DateTimeOffset ExpiresAt { get; set; }
    public DateTimeOffset? UsedAt { get; set; }
    public Guid CreatedBy { get; set; }
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
    public string? EmbeddingJson { get; set; }
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
    // Patterns the reviewer confirmed at review time, JSON array of AiEventType names.
    // Null = review submitted by a client without pattern selection (pre-feature).
    public string? ConfirmedPatternsJson { get; set; }
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
}

/// <summary>
/// Current training-ready dataset entry built from human alert reviews.
/// Deliberately has no FK to Alerts: samples must survive alert retention/bulk-delete.
/// One sample per alert (unique AlertId); re-reviews update it in place.
/// </summary>
public class TrainingSample
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid AlertId { get; set; }
    public Guid ClipId { get; set; }
    /// <summary>Original alert clip object key (may be deleted by retention later).</summary>
    public string SourceClipObjectKey { get; set; } = string.Empty;
    /// <summary>Dedicated dataset copy: training-dataset/{storeId}/{sampleId}/clip.mp4</summary>
    public string DatasetClipObjectKey { get; set; } = string.Empty;
    public Guid StoreId { get; set; }
    public Guid CameraId { get; set; }
    public string AlertType { get; set; } = string.Empty;
    public ReviewAction ReviewOutcome { get; set; }
    public Guid ReviewerId { get; set; }
    public string ModelVersion { get; set; } = "unknown";
    public string RuleVersion { get; set; } = string.Empty;
    public DatasetStatus DatasetStatus { get; set; } = DatasetStatus.Ready;
    public bool IncludeInTraining { get; set; } = true;
    // Append-only audit of label edits made from the Training page: [{by, at, patterns}].
    public string EditHistoryJson { get; set; } = "[]";
    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.UtcNow;

    public List<TrainingSamplePattern> Patterns { get; set; } = new();
}

/// <summary>Per-pattern label for a training sample (clip-level multi-label classification).</summary>
public class TrainingSamplePattern
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid TrainingSampleId { get; set; }
    public TrainingSample? TrainingSample { get; set; }
    public AiEventType Pattern { get; set; }
    public bool AiDetected { get; set; }
    public bool HumanConfirmed { get; set; }
    public PatternLabelStatus LabelStatus { get; set; }
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
