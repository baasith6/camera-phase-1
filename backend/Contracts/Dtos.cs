using Onevo.Api.Domain;

namespace Onevo.Api.Contracts;

// ---- Auth ----
public record LoginRequest(string Email, string Password);
public record LoginResponse(string Token, string Email, string Role);

// ---- Stores ----
public record CreateStoreRequest(string Name, string? Organization);
public record UpdateStoreRequest(string? Name, string? AlertVisibilityMode);

// ---- Cameras ----
public record CreateCameraRequest(Guid StoreId, string Name, string RtspUrl, string? OnvifHost, int? OnvifPort);
public record UpdateCameraRequest(string? Name, string? RtspUrl, string? Status, string? OnvifHost, int? OnvifPort);
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
public record HeartbeatRequest(double DiskFreePct, int UploadQueueDepth, string? DegradedReason, string Version);

// ---- Clips ----
public record UploadUrlRequest(Guid CameraId, double DurationSec, string? TriggerReason);
public record UploadUrlResponse(Guid ClipId, string ObjectKey, string UploadUrl, int ExpirySeconds);
public record CompleteClipRequest(Guid ClipId);

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
