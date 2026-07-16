using Minio;
using Minio.DataModel.Args;

namespace Onevo.Api.Services;

public class S3Options
{
    public string Endpoint { get; set; } = "http://minio:9000";
    public string PublicEndpoint { get; set; } = "http://localhost:9000";
    public string Bucket { get; set; } = "onevo-clips";
    public string AccessKey { get; set; } = "";
    public string SecretKey { get; set; } = "";
    public string Region { get; set; } = "us-east-1";
}

// Wraps MinIO (S3-compatible) storage: presigned upload/download URLs and existence checks.
public class S3Service
{
    private readonly IMinioClient _internal;   // used by backend to talk to minio (in-cluster host)
    private readonly IMinioClient _public;      // used to mint URLs the connector (outside) can reach
    private readonly S3Options _opts;

    public S3Service(S3Options opts)
    {
        _opts = opts;
        _internal = BuildClient(opts.Endpoint, opts);
        _public = BuildClient(opts.PublicEndpoint, opts);
    }

    private static IMinioClient BuildClient(string endpoint, S3Options opts)
    {
        var uri = new Uri(endpoint);
        var builder = new MinioClient()
            .WithEndpoint(uri.Host, uri.Port)
            .WithCredentials(opts.AccessKey, opts.SecretKey)
            .WithRegion(opts.Region);
        if (uri.Scheme == "https") builder = builder.WithSSL();
        return builder.Build();
    }

    public string Bucket => _opts.Bucket;

    public async Task<string> PresignedPutAsync(string objectKey, int expirySeconds = 3600)
    {
        var args = new PresignedPutObjectArgs()
            .WithBucket(_opts.Bucket)
            .WithObject(objectKey)
            .WithExpiry(expirySeconds);
        return await _public.PresignedPutObjectAsync(args);
    }

    public async Task<string> PresignedGetAsync(string objectKey, int expirySeconds = 3600)
    {
        var args = new PresignedGetObjectArgs()
            .WithBucket(_opts.Bucket)
            .WithObject(objectKey)
            .WithExpiry(expirySeconds);
        return await _public.PresignedGetObjectAsync(args);
    }

    public async Task<bool> ExistsAsync(string objectKey)
    {
        try
        {
            await _internal.StatObjectAsync(new StatObjectArgs()
                .WithBucket(_opts.Bucket)
                .WithObject(objectKey));
            return true;
        }
        catch
        {
            return false;
        }
    }
}
