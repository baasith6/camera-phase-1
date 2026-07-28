using System.Data;
using Microsoft.EntityFrameworkCore;
using Npgsql;
using NpgsqlTypes;
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
        string sourceKey,
        string name,
        string rtspUrl,
        string? onvifHost,
        int? onvifPort,
        bool useDemoZones,
        CancellationToken ct = default)
    {
        var normalizedSourceKey = sourceKey?.Trim() ?? "";
        if (string.IsNullOrWhiteSpace(normalizedSourceKey))
            throw new ArgumentException("sourceKey is required", nameof(sourceKey));
        if (normalizedSourceKey.Length > 128)
            throw new ArgumentException("sourceKey is too long", nameof(sourceKey));

        var normalizedName = name.Trim();
        var normalizedUrl = rtspUrl?.Trim() ?? "";

        // PostgreSQL performs identity reconciliation atomically. The partial
        // unique index closes the concurrent check/insert race, while ON CONFLICT
        // makes network retries update and return the same camera.
        var connection = (NpgsqlConnection)_db.Database.GetDbConnection();
        var shouldClose = connection.State != ConnectionState.Open;
        if (shouldClose)
            await connection.OpenAsync(ct);

        Guid cameraId;
        try
        {
            await using var command = connection.CreateCommand();
            command.CommandText =
                """
                INSERT INTO "Cameras"
                    ("Id", "StoreId", "ConnectorId", "SourceKey", "Name",
                     "RtspUrl", "Status", "CreatedAt", "OnvifHost", "OnvifPort")
                VALUES
                    (@id, @storeId, @connectorId, @sourceKey, @name,
                     @rtspUrl, @status, @createdAt, @onvifHost, @onvifPort)
                ON CONFLICT ("ConnectorId", "SourceKey")
                    WHERE "SourceKey" IS NOT NULL
                DO UPDATE SET
                    "Name" = EXCLUDED."Name",
                    "RtspUrl" = EXCLUDED."RtspUrl",
                    "OnvifHost" = EXCLUDED."OnvifHost",
                    "OnvifPort" = EXCLUDED."OnvifPort"
                RETURNING "Id";
                """;
            command.Parameters.AddWithValue("id", Guid.NewGuid());
            command.Parameters.AddWithValue("storeId", connector.StoreId);
            command.Parameters.AddWithValue("connectorId", connector.Id);
            command.Parameters.AddWithValue("sourceKey", normalizedSourceKey);
            command.Parameters.AddWithValue("name", normalizedName);
            command.Parameters.AddWithValue("rtspUrl", normalizedUrl);
            command.Parameters.AddWithValue("status", CameraStatus.Pending.ToString());
            command.Parameters.AddWithValue("createdAt", DateTimeOffset.UtcNow);
            command.Parameters.AddWithValue(
                "onvifHost", NpgsqlDbType.Text, (object?)onvifHost ?? DBNull.Value);
            command.Parameters.AddWithValue(
                "onvifPort", NpgsqlDbType.Integer, (object?)onvifPort ?? DBNull.Value);
            cameraId = (Guid)(await command.ExecuteScalarAsync(ct)
                ?? throw new InvalidOperationException("Camera upsert returned no id"));
        }
        finally
        {
            if (shouldClose)
                await connection.CloseAsync();
        }

        var camera = await _db.Cameras
            .Include(c => c.Zones)
            .SingleAsync(c => c.Id == cameraId, ct);

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
