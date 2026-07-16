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
    Offline
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
