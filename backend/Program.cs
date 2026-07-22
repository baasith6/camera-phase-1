using System.Text;
using System.Text.Json.Serialization;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using Onevo.Api.Auth;
using Onevo.Api.Data;
using Onevo.Api.Services;
using StackExchange.Redis;

var builder = WebApplication.CreateBuilder(args);
var cfg = builder.Configuration;

// ---- Database ----
var conn = cfg.GetConnectionString("Postgres")
           ?? "Host=localhost;Port=5432;Database=onevo;Username=onevo;Password=onevo_dev_pw";
builder.Services.AddDbContext<OnevoDbContext>(o => o.UseNpgsql(conn));

// ---- Redis ----
var redisConn = cfg["Redis:Connection"] ?? "localhost:6379";
builder.Services.AddSingleton<IConnectionMultiplexer>(
    ConnectionMultiplexer.Connect(new ConfigurationOptions
    {
        EndPoints = { redisConn },
        AbortOnConnectFail = false
    }));
builder.Services.AddSingleton<ClipQueue>();
builder.Services.AddSingleton<AlertChannel>();

// ---- Object storage (MinIO / S3) ----
var s3Opts = new S3Options
{
    Endpoint = cfg["S3:Endpoint"] ?? "http://localhost:9000",
    PublicEndpoint = cfg["S3:PublicEndpoint"] ?? "http://localhost:9000",
    Bucket = cfg["S3:Bucket"] ?? "onevo-clips",
    AccessKey = cfg["S3:AccessKey"] ?? "",
    SecretKey = cfg["S3:SecretKey"] ?? "",
    Region = cfg["S3:Region"] ?? "us-east-1"
};
builder.Services.AddSingleton(new S3Service(s3Opts));

// ---- Auth ----
var jwtOpts = new JwtOptions
{
    SigningKey = cfg["Jwt:SigningKey"] ?? "dev-super-secret-signing-key-change-me-please-32+",
    Issuer = cfg["Jwt:Issuer"] ?? "onevo",
    Audience = cfg["Jwt:Audience"] ?? "onevo"
};
builder.Services.AddSingleton(jwtOpts);
builder.Services.AddSingleton<JwtTokenService>();

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(o =>
    {
        o.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = jwtOpts.Issuer,
            ValidAudience = jwtOpts.Audience,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(jwtOpts.SigningKey))
        };
        // Allow JWT via ?access_token= query param for SSE (EventSource can't set headers).
        o.Events = new Microsoft.AspNetCore.Authentication.JwtBearer.JwtBearerEvents
        {
            OnMessageReceived = ctx =>
            {
                var token = ctx.Request.Query["access_token"];
                if (!string.IsNullOrEmpty(token) &&
                    ctx.Request.Path.StartsWithSegments("/api/alerts/stream"))
                {
                    ctx.Token = token;
                }
                return Task.CompletedTask;
            }
        };
    });
builder.Services.AddAuthorization();

// ---- Risk engine (scoped: uses DbContext) ----
builder.Services.AddScoped<RiskEngine>();

// ---- Theft Orchestrator (Singleton: creates its own scopes) ----
builder.Services.AddSingleton<TheftOrchestrator>();

// ---- Web ----
builder.Services.AddControllers()
    .AddJsonOptions(o =>
    {
        o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter());
        // EF navigation properties (Alert.Reviews <-> Review.Alert) form cycles; ignore them.
        o.JsonSerializerOptions.ReferenceHandler = ReferenceHandler.IgnoreCycles;
    });
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
// CORS — driven by CORS_ORIGINS env var (comma-separated list of allowed origins).
// Falls back to http://localhost:4200 for local development.
var allowedOrigins = (cfg["CORS_ORIGINS"] ?? "http://localhost:4200")
    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
builder.Services.AddCors(o => o.AddDefaultPolicy(p =>
    p.WithOrigins(allowedOrigins).AllowAnyHeader().AllowAnyMethod()));

var app = builder.Build();

// ---- Migrate/seed on startup (dev convenience; uses EnsureCreated) ----
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<OnevoDbContext>();
    var maxTries = 10;
    for (var i = 1; i <= maxTries; i++)
    {
        try { await DbSeeder.SeedAsync(db, cfg); break; }
        catch (Exception ex) when (i < maxTries)
        {
            app.Logger.LogWarning("DB not ready (attempt {Attempt}/{Max}): {Msg}", i, maxTries, ex.Message);
            await Task.Delay(3000);
        }
    }
}

app.UseSwagger();
app.UseSwaggerUI();
app.UseCors();
app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();

app.Run();
