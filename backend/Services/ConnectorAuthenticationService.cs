using Microsoft.EntityFrameworkCore;
using Onevo.Api.Data;
using Onevo.Api.Domain;

namespace Onevo.Api.Services;

/// <summary>
/// Authenticates machine-to-machine connector requests in one place.
/// Human users continue to use JWT bearer authentication.
/// </summary>
public sealed class ConnectorAuthenticationService
{
    public const string ConnectorIdHeader = "X-Connector-Id";
    public const string ConnectorKeyHeader = "X-Connector-Key";

    private readonly OnevoDbContext _db;

    public ConnectorAuthenticationService(OnevoDbContext db) => _db = db;

    public async Task<Connector?> AuthenticateAsync(
        HttpRequest request,
        CancellationToken ct = default)
    {
        if (!request.Headers.TryGetValue(ConnectorIdHeader, out var idValue) ||
            !request.Headers.TryGetValue(ConnectorKeyHeader, out var keyValue) ||
            !Guid.TryParse(idValue.ToString(), out var connectorId))
            return null;

        var connector = await _db.Connectors
            .SingleOrDefaultAsync(c => c.Id == connectorId, ct);

        if (connector is null || string.IsNullOrWhiteSpace(connector.ApiKeyHash))
            return null;

        return BCrypt.Net.BCrypt.Verify(keyValue.ToString(), connector.ApiKeyHash)
            ? connector
            : null;
    }

    public Task<bool> OwnsCameraAsync(
        Connector connector,
        Guid cameraId,
        CancellationToken ct = default) =>
        _db.Cameras.AnyAsync(
            c => c.Id == cameraId &&
                 c.StoreId == connector.StoreId &&
                 c.ConnectorId == connector.Id,
            ct);
}
