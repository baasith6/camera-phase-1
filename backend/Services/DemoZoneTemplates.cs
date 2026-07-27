using Onevo.Api.Domain;

namespace Onevo.Api.Services;

/// <summary>Single source of truth for the synthetic/test-video demo layout.</summary>
public static class DemoZoneTemplates
{
    private static readonly (string Name, ZoneType Type, string Polygon)[] Templates =
    [
        ("High-Value Shelf", ZoneType.HighValue, "[[0.5,0.1],[0.95,0.1],[0.95,0.9],[0.5,0.9]]"),
        ("Checkout", ZoneType.Checkout, "[[0.0,0.6],[0.25,0.6],[0.25,1.0],[0.0,1.0]]"),
        ("Exit", ZoneType.Exit, "[[0.0,0.0],[0.15,0.0],[0.15,0.4],[0.0,0.4]]"),
        ("Blind Spot", ZoneType.BlindSpot, "[[0.3,0.0],[0.48,0.0],[0.48,0.35],[0.3,0.35]]")
    ];

    public static IEnumerable<CameraZone> Create(Guid cameraId) =>
        Templates.Select(template => new CameraZone
        {
            CameraId = cameraId,
            Name = template.Name,
            ZoneType = template.Type,
            PolygonJson = template.Polygon
        });
}
