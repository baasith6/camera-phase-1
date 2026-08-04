namespace Onevo.Api.Domain;

public enum UserRole
{
    Admin,
    Manager,
    Reviewer,
    Installer
}

public enum ZoneType
{
    Shelf,
    HighValue,
    Checkout,
    Exit,
    BlindSpot,
    Staff
}

public enum CameraStatus
{
    Pending,
    Active,
    AnalyticsOnly,
    Offline,
    Disabled
}

public enum ConnectorStatus
{
    Unknown,
    Healthy,
    Degraded,
    Offline
}

public enum ClipStatus
{
    Pending,      // upload URL issued, awaiting upload complete
    Uploaded,     // object present, job enqueued
    Processing,   // picked up by cloud-ai worker
    Analyzed,     // AI events produced
    Failed
}

public enum AiEventType
{
    HighValueZoneEntry,
    Dwell,
    RepeatedHandling,
    BagOpen,
    Concealment,
    ExitWithoutCheckout,
    ShelfPickupNoCheckout,
    BlindSpotMovement,
    GroupDistraction,
    HighValueActivity,
    LowStaffRemoval
}

public enum RiskLevel
{
    None,
    Low,
    Medium,
    High
}

public enum AlertStatus
{
    PendingReview,
    Confirmed,
    Dismissed,
    FalsePositive,
    NeedsFollowUp
}

public enum ReviewAction
{
    Confirm,
    Dismiss,
    FalsePositive,
    NeedsFollowUp
}

public enum AlertVisibilityMode
{
    Silent,       // stored, not surfaced to any staff (baseline collection)
    ManagerOnly,  // only managers/admins see alerts
    All           // all reviewers see alerts
}

/// <summary>Per-pattern label attached to a training sample by human review.</summary>
public enum PatternLabelStatus
{
    Positive,     // reviewer confirmed the pattern is present in the clip
    HardNegative, // AI detected it but reviewer rejected it
    Uncertain     // no final human decision yet
}

/// <summary>Lifecycle of a training dataset sample.</summary>
public enum DatasetStatus
{
    Ready,          // labeled and clip copied; usable for training
    PendingReview,  // awaiting a final reviewer decision (NeedsFollowUp)
    Excluded,       // manually or automatically excluded from training
    ClipUnavailable,// source clip missing when the sample was created
    CopyFailed      // dataset clip copy failed; retry on next re-review
}
