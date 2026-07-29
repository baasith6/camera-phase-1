namespace Onevo.Api.Auth;

/// <summary>Shared service-key validation for cloud-ai and connector bootstrap endpoints.</summary>
public static class ServiceAuth
{
    public const string DefaultBootstrapKey = "dev-connector-bootstrap-key";

    /// <summary>Key used by edge connectors to register (bootstrap only).</summary>
    public static string ConnectorBootstrapKey(IConfiguration cfg)
        => cfg["Seed:ConnectorBootstrapKey"] ?? DefaultBootstrapKey;

    /// <summary>Key used by the cloud-ai worker for ingest and zone reads.</summary>
    public static string CloudAiServiceKey(IConfiguration cfg)
        => cfg["CloudAi:ServiceKey"]
           ?? cfg["Seed:CloudAiServiceKey"]
           ?? ConnectorBootstrapKey(cfg);

    public static bool ValidateCloudAiKey(IConfiguration cfg, string? provided)
        => !string.IsNullOrEmpty(provided) && provided == CloudAiServiceKey(cfg);

    public static bool ValidateBootstrapKey(IConfiguration cfg, string? provided)
        => !string.IsNullOrEmpty(provided) && provided == ConnectorBootstrapKey(cfg);
}
