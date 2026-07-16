using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Services;

// Risk scoring configuration. Defaults mirror the V4 solution document starter weights.
public class RiskConfig
{
    public Dictionary<string, int> Weights { get; set; } = new()
    {
        [nameof(AiEventType.HighValueZoneEntry)] = 15,
        [nameof(AiEventType.Dwell)] = 20,            // max contribution; scaled by dwell duration
        [nameof(AiEventType.RepeatedHandling)] = 15,
        [nameof(AiEventType.BagOpen)] = 20,
        [nameof(AiEventType.Concealment)] = 20,
        [nameof(AiEventType.ExitWithoutCheckout)] = 20,
        [nameof(AiEventType.ShelfPickupNoCheckout)] = 25,
        [nameof(AiEventType.BlindSpotMovement)] = 15,
        [nameof(AiEventType.GroupDistraction)] = 10,
        [nameof(AiEventType.HighValueActivity)] = 15,
        [nameof(AiEventType.LowStaffRemoval)] = 10
    };

    public double DwellThresholdSec { get; set; } = 30;
    public double DwellMaxSec { get; set; } = 90;         // dwell reaching this hits full weight
    public int RepeatedHandlingThreshold { get; set; } = 3;
    public int GroupSizeThreshold { get; set; } = 3;      // persons in a shelf zone for group distraction

    // Low-staff window (local hours). Wraps midnight when start > end (e.g. 22 -> 6).
    public int LowStaffStartHour { get; set; } = 22;
    public int LowStaffEndHour { get; set; } = 6;

    public int LowBand { get; set; } = 40;   // >=40 analytics
    public int MediumBand { get; set; } = 70; // >=70 medium alert
    public int HighBand { get; set; } = 90;   // >=90 high alert

    public const string RuleVersion = "v4-starter-1.1";

    public bool IsLowStaffHour(int hour)
    {
        if (LowStaffStartHour == LowStaffEndHour) return false;
        return LowStaffStartHour < LowStaffEndHour
            ? hour >= LowStaffStartHour && hour < LowStaffEndHour
            : hour >= LowStaffStartHour || hour < LowStaffEndHour; // wraps midnight
    }
}

public class RiskScoreResult
{
    public int Score { get; set; }
    public RiskLevel Level { get; set; }
    public string AlertType { get; set; } = "";
    public List<string> Evidence { get; set; } = new();
    public Guid? PrimaryZoneId { get; set; }
}

public class RiskEngine
{
    private readonly OnevoDbContext _db;

    public RiskEngine(OnevoDbContext db) => _db = db;

    public async Task<RiskConfig> ResolveConfigAsync(Guid storeId, Guid cameraId, CancellationToken ct = default)
    {
        // Resolve global -> store scope (most-specific wins). Camera/zone scoping is supported by schema
        // but store-level is sufficient for the Phase 1A MVP.
        var configs = await _db.RuleConfigs
            .Where(r => (r.StoreId == null && r.CameraId == null && r.ZoneId == null) || r.StoreId == storeId)
            .ToListAsync(ct);

        var cfg = new RiskConfig();
        // Global first, then store override.
        foreach (var scoped in configs.OrderBy(c => c.StoreId == null ? 0 : 1))
        {
            var parsed = TryParse(scoped.ConfigJson);
            if (parsed != null) cfg = parsed;
        }
        return cfg;
    }

    private static RiskConfig? TryParse(string json)
    {
        try
        {
            if (string.IsNullOrWhiteSpace(json) || json == "{}") return null;
            return JsonSerializer.Deserialize<RiskConfig>(json,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
        }
        catch { return null; }
    }

    public RiskScoreResult Score(IReadOnlyList<AiEvent> events, RiskConfig cfg)
    {
        var result = new RiskScoreResult();
        if (events.Count == 0) return result;

        var scored = new HashSet<AiEventType>();  // signals that actually contributed points

        void Award(AiEventType type, int pts, string evidence, Guid? zoneId)
        {
            result.Score += pts;
            result.Evidence.Add(evidence);
            result.PrimaryZoneId ??= zoneId;
            scored.Add(type);
        }

        foreach (var e in events)
        {
            switch (e.EventType)
            {
                case AiEventType.HighValueZoneEntry:
                    if (!scored.Contains(AiEventType.HighValueZoneEntry))
                        Award(e.EventType, cfg.Weights[nameof(AiEventType.HighValueZoneEntry)],
                            "Customer entered high-value shelf zone", e.ZoneId);
                    break;

                case AiEventType.Dwell:
                    if (e.Value >= cfg.DwellThresholdSec)
                    {
                        var span = Math.Max(1, cfg.DwellMaxSec - cfg.DwellThresholdSec);
                        var frac = Math.Clamp((e.Value - cfg.DwellThresholdSec) / span, 0, 1);
                        var pts = (int)Math.Round(10 + frac * (cfg.Weights[nameof(AiEventType.Dwell)] - 10));
                        Award(e.EventType, pts, $"Dwell {e.Value:0}s in high-value zone", e.ZoneId);
                    }
                    break;

                case AiEventType.RepeatedHandling:
                    if (e.Value >= cfg.RepeatedHandlingThreshold)
                        Award(e.EventType, cfg.Weights[nameof(AiEventType.RepeatedHandling)],
                            $"Repeated shelf handling ({e.Value:0} interactions)", e.ZoneId);
                    break;

                case AiEventType.BagOpen:
                    Award(e.EventType, cfg.Weights[nameof(AiEventType.BagOpen)],
                        "Bag / open-bag cue detected near shelf", e.ZoneId);
                    break;

                case AiEventType.Concealment:
                    Award(e.EventType, cfg.Weights[nameof(AiEventType.Concealment)],
                        "Item handled at shelf then a bag/open-bag cue followed", e.ZoneId);
                    break;

                case AiEventType.ExitWithoutCheckout:
                    Award(e.EventType, cfg.Weights[nameof(AiEventType.ExitWithoutCheckout)],
                        "Moved to exit after shelf interaction without passing checkout", e.ZoneId);
                    break;

                case AiEventType.ShelfPickupNoCheckout:
                    Award(e.EventType, cfg.Weights[nameof(AiEventType.ShelfPickupNoCheckout)],
                        "Product taken from shelf and carried to exit without checkout (POS cross-check pending)", e.ZoneId);
                    break;

                case AiEventType.BlindSpotMovement:
                    Award(e.EventType, cfg.Weights[nameof(AiEventType.BlindSpotMovement)],
                        "Movement into a configured blind-spot zone", e.ZoneId);
                    break;

                case AiEventType.GroupDistraction:
                    if (e.Value >= cfg.GroupSizeThreshold)
                        Award(e.EventType, cfg.Weights[nameof(AiEventType.GroupDistraction)],
                            $"Group of {e.Value:0} persons active at a shelf zone", e.ZoneId);
                    break;

                case AiEventType.HighValueActivity:
                    Award(e.EventType, cfg.Weights[nameof(AiEventType.HighValueActivity)],
                        "Multiple activity cues inside a high-value zone", e.ZoneId);
                    break;

                case AiEventType.LowStaffRemoval:
                    // Camera-only proxy: only scores inside the configured low-staff window.
                    if (cfg.IsLowStaffHour(e.StartTs.ToLocalTime().Hour))
                        Award(e.EventType, cfg.Weights[nameof(AiEventType.LowStaffRemoval)],
                            "Product removed from shelf during low-staff hours (staff-count cross-check pending)", e.ZoneId);
                    break;
            }
        }

        result.Level = result.Score >= cfg.HighBand ? RiskLevel.High
            : result.Score >= cfg.MediumBand ? RiskLevel.Medium
            : result.Score >= cfg.LowBand ? RiskLevel.Low
            : RiskLevel.None;

        result.AlertType = DeriveAlertType(scored);
        return result;
    }

    private static string DeriveAlertType(HashSet<AiEventType> types)
    {
        // Ordered by signal strength / specificity.
        if (types.Contains(AiEventType.ShelfPickupNoCheckout)) return "SHELF_PICKUP_NO_CHECKOUT";
        if (types.Contains(AiEventType.Concealment)) return "CONCEALMENT_MOVEMENT";
        if (types.Contains(AiEventType.ExitWithoutCheckout)) return "EXIT_WITHOUT_CHECKOUT";
        if (types.Contains(AiEventType.BagOpen)) return "BAG_OPEN_NEAR_SHELF";
        if (types.Contains(AiEventType.BlindSpotMovement)) return "BLIND_SPOT_MOVEMENT";
        if (types.Contains(AiEventType.LowStaffRemoval)) return "LOW_STAFF_REMOVAL";
        if (types.Contains(AiEventType.GroupDistraction)) return "GROUP_DISTRACTION";
        if (types.Contains(AiEventType.HighValueActivity)) return "HIGH_VALUE_ACTIVITY";
        if (types.Contains(AiEventType.RepeatedHandling)) return "REPEATED_SHELF_HANDLING";
        if (types.Contains(AiEventType.Dwell) || types.Contains(AiEventType.HighValueZoneEntry))
            return "LONG_DWELL_HIGH_VALUE";
        return "CAMERA_RISK_EVENT";
    }
}
