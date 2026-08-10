using System.Security.Cryptography;

namespace Onevo.Api.Services;

/// <summary>
/// Serves the Windows connector installer directly from connector/dist.
/// Re-checks file metadata on each request (no restart needed after replacing the .exe).
/// </summary>
public class ConnectorInstallerService
{
    private readonly IConfiguration _cfg;
    private readonly ILogger<ConnectorInstallerService> _log;
    private readonly object _gate = new();
    private string? _cachedPath;
    private DateTime _cachedWriteUtc;
    private long _cachedSize;
    private string? _cachedSha;

    public ConnectorInstallerService(IConfiguration cfg, ILogger<ConnectorInstallerService> log)
    {
        _cfg = cfg;
        _log = log;
    }

    public string Version =>
        _cfg["ConnectorInstaller:Version"] ?? "1.1.20";

    public string FileName =>
        $"ONETIX-Connector-Setup-{Version}-rev18.exe";

    public string? ResolvePath()
    {
        var configured = _cfg["ConnectorInstaller:Path"];
        if (!string.IsNullOrWhiteSpace(configured))
        {
            // If Path points at a directory, append the expected filename.
            if (Directory.Exists(configured))
                return Path.Combine(configured, FileName);
            return configured;
        }

        // Dev default: ./connector/dist next to the repo when running via docker mount
        var fallback = Path.Combine(AppContext.BaseDirectory, "connector-dist", FileName);
        return fallback;
    }

    public bool TryGetInfo(out string path, out long size, out string sha256)
    {
        path = ResolvePath() ?? "";
        size = 0;
        sha256 = "";
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            _log.LogDebug("Connector installer not found at {Path}", path);
            return false;
        }

        var info = new FileInfo(path);
        lock (_gate)
        {
            if (_cachedPath == path && _cachedWriteUtc == info.LastWriteTimeUtc && _cachedSha is not null)
            {
                size = _cachedSize;
                sha256 = _cachedSha;
                return true;
            }

            using var stream = File.OpenRead(path);
            var hash = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
            _cachedPath = path;
            _cachedWriteUtc = info.LastWriteTimeUtc;
            _cachedSize = info.Length;
            _cachedSha = hash;
            size = info.Length;
            sha256 = hash;
            return true;
        }
    }

    /// <summary>
    /// Local EXE metadata. Remote installer redirects are intentionally unsupported.
    /// </summary>
    public bool TryGetPublishedInfo(
        out string version,
        out string fileName,
        out long size,
        out string sha256,
        out string downloadUrl)
    {
        version = Version;
        fileName = FileName;

        if (TryGetInfo(out _, out size, out sha256))
        {
            downloadUrl = "/api/connectors/installer/download";
            return true;
        }

        size = 0;
        sha256 = "";
        downloadUrl = "";
        return false;
    }

    public static string GenerateSetupCode()
    {
        const string alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
        var bytes = RandomNumberGenerator.GetBytes(8);
        var chars = new char[8];
        for (var i = 0; i < 8; i++)
            chars[i] = alphabet[bytes[i] % alphabet.Length];
        return $"{new string(chars, 0, 4)}-{new string(chars, 4, 4)}";
    }

}
