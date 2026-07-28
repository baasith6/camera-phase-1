using System.Security.Cryptography;
using Microsoft.EntityFrameworkCore;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Services;

/// <summary>
/// Creates or re-pairs the single connector owned by a store and assigns that
/// store's unassigned cameras. Registration and setup-code claim share this path.
/// </summary>
public sealed class ConnectorPairingService
{
    private readonly OnevoDbContext _db;

    public ConnectorPairingService(OnevoDbContext db) => _db = db;

    public async Task<(Connector Connector, string ApiKey)> PairAsync(
        Guid storeId,
        string name,
        string version,
        CancellationToken ct = default)
    {
        var connector = await _db.Connectors
            .SingleOrDefaultAsync(c => c.StoreId == storeId, ct);

        if (connector is null)
        {
            connector = new Connector { StoreId = storeId };
            _db.Connectors.Add(connector);
        }

        var apiKey = Convert.ToHexString(RandomNumberGenerator.GetBytes(24));
        connector.Name = string.IsNullOrWhiteSpace(name) ? "edge-connector-1" : name.Trim();
        connector.Version = string.IsNullOrWhiteSpace(version) ? "1.0.0" : version.Trim();
        connector.ApiKeyHash = BCrypt.Net.BCrypt.HashPassword(apiKey);
        connector.Status = ConnectorStatus.Healthy;
        connector.LastHeartbeat = DateTimeOffset.UtcNow;
        connector.DegradedReason = null;

        await _db.SaveChangesAsync(ct);

        // With one connector per store, every unassigned store camera belongs to it.
        await _db.Cameras
            .Where(c => c.StoreId == storeId && c.ConnectorId == null)
            .ExecuteUpdateAsync(
                setters => setters.SetProperty(c => c.ConnectorId, connector.Id),
                ct);

        return (connector, apiKey);
    }
}
