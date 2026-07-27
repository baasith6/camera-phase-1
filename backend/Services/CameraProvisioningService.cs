using Microsoft.EntityFrameworkCore;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Services;

/// <summary>
/// Creates connector cameras and applies source-specific defaults in one place.
/// Demo zones are only suitable for installer test videos; real camera zones must
/// be drawn against the actual camera view in the dashboard.
/// </summary>
public class CameraProvisioningService
{
    private readonly OnevoDbContext _db;

    public CameraProvisioningService(OnevoDbContext db) => _db = db;

    public async Task<Camera> ProvisionConnectorCameraAsync(
        Connector connector,
        string name,
        string rtspUrl,
        string? onvifHost,
        int? onvifPort,
        bool useDemoZones,
        CancellationToken ct = default)
    {
        var normalizedName = name.Trim();
        var normalizedUrl = rtspUrl?.Trim() ?? "";

        // Installer retries must be safe: reuse the connector camera for the same
        // source instead of creating duplicate cameras and split alert histories.
        var camera = await _db.Cameras
            .Include(c => c.Zones)
            .FirstOrDefaultAsync(c =>
                c.StoreId == connector.StoreId &&
                c.ConnectorId == connector.Id &&
                c.Name == normalizedName &&
                c.RtspUrl == normalizedUrl, ct);

        if (camera is null)
        {
            camera = new Camera
            {
                StoreId = connector.StoreId,
                ConnectorId = connector.Id,
                Name = normalizedName,
                RtspUrl = normalizedUrl,
                OnvifHost = onvifHost,
                OnvifPort = onvifPort,
                Status = CameraStatus.Pending
            };
            _db.Cameras.Add(camera);
        }
        else
        {
            camera.OnvifHost = onvifHost;
            camera.OnvifPort = onvifPort;
        }

        if (useDemoZones)
            AddMissingDemoZones(camera);

        await _db.SaveChangesAsync(ct);
        return camera;
    }

    /// <summary>
    /// Repairs test-video cameras created by an older installer. Safe to call more
    /// than once because templates are matched by name and type.
    /// </summary>
    public async Task EnsureDemoZonesAsync(
        IEnumerable<Camera> cameras,
        CancellationToken ct = default)
    {
        var changed = false;
        foreach (var camera in cameras)
            changed |= AddMissingDemoZones(camera);

        if (changed)
            await _db.SaveChangesAsync(ct);
    }

    private bool AddMissingDemoZones(Camera camera)
    {
        var changed = false;
        foreach (var zone in DemoZoneTemplates.Create(camera.Id))
        {
            if (camera.Zones.Any(z => z.Name == zone.Name && z.ZoneType == zone.ZoneType))
                continue;

            camera.Zones.Add(zone);
            // CameraZone IDs are assigned in the entity constructor. Explicitly mark
            // the entity Added so EF does not treat a non-empty GUID as an existing row.
            _db.CameraZones.Add(zone);
            changed = true;
        }

        return changed;
    }
}
