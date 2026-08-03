using Onevo.Api.Domain;

namespace Onevo.Api.Contracts;

// ---- Auth ----
public record LoginRequest(string Email, string Password);
public record ChangePasswordRequest(string CurrentPassword, string NewPassword);
public record LoginResponse(string Token, string Email, string Role, Guid? StoreId);

// ---- Users ----
public record CreateUserRequest(string Email, string Password, string Role, Guid? StoreId);
public record UserResponse(Guid Id, string Email, string Role, Guid? StoreId, DateTimeOffset CreatedAt);

// ---- Stores ----
public record CreateStoreRequest(
    string Name,
    string? Organization,
    string? NotificationEmail,
    string? AlertVisibilityMode);
public record UpdateStoreRequest(string? Name, string? AlertVisibilityMode, string? NotificationEmail);
public record StoreOverviewResponse(
    Guid Id,
    string Name,
    string AlertVisibilityMode,
    string? NotificationEmail,
    int CameraCount,
    int ConnectorCount,
    int OnlineConnectorCount,
    int PendingAlertCount,
    DateTimeOffset? LastAlertAt);

// ---- Cameras ----
public record CreateCameraRequest(Guid StoreId, string Name, string RtspUrl, string? OnvifHost, int? OnvifPort);
public record UpdateCameraRequest(string? Name, string? RtspUrl, string? Status, string? OnvifHost, int? OnvifPort);
public record BulkDisableCamerasRequest(List<Guid> CameraIds);
public record UpdateDeviceInfoRequest(
    string? Manufacturer,
    string? Model,
    string? Serial,
    string? Firmware,
    string? OnvifHost,
    int? OnvifPort,
    string? RtspUrl);

// ---- Zones ----
public record CreateZoneRequest(Guid CameraId, string Name, string ZoneType, string PolygonJson);
public record UpdateZoneRequest(string? Name, string? ZoneType, string? PolygonJson);

// ---- Connectors ----
public record RegisterConnectorRequest(Guid StoreId, string Name, string Version, string BootstrapKey);
public record RegisterConnectorResponse(Guid ConnectorId, string ApiKey);
public record HeartbeatRequest(
    double DiskFreePct,
    int UploadQueueDepth,
    string? DegradedReason,
    string Version,
    string? AdminHost = null,
    int? AdminPort = null);
public record CreateSetupCodeRequest(Guid StoreId);
public record CreateSetupCodeResponse(string Code, Guid StoreId, DateTimeOffset ExpiresAt);
public record ClaimSetupCodeRequest(string SetupCode, string Name, string Version);
public record ClaimSetupCodeResponse(Guid ConnectorId, string ApiKey, Guid StoreId);
public record ConnectorCreateCameraRequest(
    string SourceKey,
    string Name,
    string RtspUrl,
    string? OnvifHost,
    int? OnvifPort);
public record FinalizeConnectorSetupRequest(List<string> SourceKeys);
public record InstallerInfoResponse(string Version, string FileName, long SizeBytes, string Sha256, string DownloadPath);
public record ReferenceFrameUploadResponse(string ObjectKey, string UploadUrl, int ExpirySeconds);
public record CompleteReferenceFrameRequest(string ObjectKey, DateTimeOffset? CapturedAt);

// ---- Clips ----
public record UploadUrlRequest(Guid CameraId, double DurationSec, string? TriggerReason);
public record UploadUrlResponse(Guid ClipId, string ObjectKey, string UploadUrl, int ExpirySeconds);
public record CompleteClipRequest(Guid ClipId);

public record ClipListItemResponse(
    Guid Id,
    Guid CameraId,
    string CameraName,
    Guid StoreId,
    string StoreName,
    string Status,
    double DurationSec,
    string TriggerReason,
    DateTimeOffset CreatedAt,
    DateTimeOffset? AnalyzedAt,
    int EventCount,
    int? RiskScore,
    Guid? AlertId);

public record ClipAiEventItemResponse(
    string EventType,
    string? ZoneName,
    double Value,
    double Confidence,
    DateTimeOffset StartTs,
    DateTimeOffset EndTs,
    string ModelVersion);

public record ClipDetailResponse(
    Guid Id,
    Guid CameraId,
    string CameraName,
    Guid StoreId,
    string StoreName,
    string Status,
    double DurationSec,
    string TriggerReason,
    DateTimeOffset CreatedAt,
    DateTimeOffset? AnalyzedAt,
    string? ClipUrl,
    int EventCount,
    int? RiskScore,
    string? RiskDetails,
    Guid? AlertId,
    string? ModelVersion,
    string? AnalysisNote,
    List<ClipAiEventItemResponse> AiEvents);

public record PipelineHealthResponse(int RedisQueueDepth, int FailedJobs);

public record AnalyticsSummaryResponse(
    int TotalAlerts,
    int PendingAlerts,
    int HighRiskAlerts,
    int MediumRiskAlerts,
    int FalsePositives,
    int TotalClips,
    int AnalyzedClips,
    Dictionary<string, int> AlertsByType);

public record ConnectorLogEntry(
    Guid Id,
    Guid StoreId,
    string Name,
    string Status,
    string Version,
    DateTimeOffset? LastHeartbeat,
    string? DegradedReason,
    int UploadQueueDepth,
    double DiskFreePct);

public record SystemLogsResponse(
    List<ConnectorLogEntry> Connectors,
    int RedisQueueDepth,
    int FailedJobs,
    DateTimeOffset GeneratedAt);

// ---- AI events (posted by cloud-ai worker) ----
public record AiEventDto(
    int TrackId,
    Guid? ZoneId,
    string EventType,
    double Value,
    double Confidence,
    DateTimeOffset StartTs,
    DateTimeOffset EndTs,
    int[]? EvidenceFrames,
    float[]? Embedding);

public record AiEventsBatchRequest(Guid ClipId, string ModelVersion, List<AiEventDto> Events);

// ---- Alerts / reviews ----
public record ReviewRequest(string Action, string? ReasonCode, string? Notes);

public record BulkDeleteRequest(Guid? StoreId, List<Guid>? Ids, bool DeleteAllInStore = false);

public record BulkDeleteResponse(int Deleted, int Skipped, List<string> Errors);
