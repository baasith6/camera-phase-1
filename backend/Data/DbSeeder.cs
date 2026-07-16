using Microsoft.EntityFrameworkCore;
using Onevo.Api.Domain;
using Onevo.Api.Services;

namespace Onevo.Api.Data;

public static class DbSeeder
{
    public static async Task SeedAsync(OnevoDbContext db, IConfiguration cfg)
    {
        await db.Database.EnsureCreatedAsync();

        // Seed admin user.
        var adminEmail = cfg["Seed:AdminEmail"] ?? "admin@onevo.local";
        var adminPassword = cfg["Seed:AdminPassword"] ?? "Admin123!";
        if (!await db.Users.AnyAsync(u => u.Email == adminEmail))
        {
            db.Users.Add(new User
            {
                Email = adminEmail,
                PasswordHash = BCrypt.Net.BCrypt.HashPassword(adminPassword),
                Role = UserRole.Admin
            });
        }

        // Seed a global default risk config so the Risk Engine has explicit, tunable values.
        if (!await db.RuleConfigs.AnyAsync(r => r.StoreId == null && r.CameraId == null && r.ZoneId == null))
        {
            var defaultCfg = new RiskConfig();
            db.RuleConfigs.Add(new RuleConfig
            {
                ConfigJson = System.Text.Json.JsonSerializer.Serialize(defaultCfg)
            });
        }

        // Seed a demo store + camera + high-value zone for immediate end-to-end testing.
        if (!await db.Stores.AnyAsync())
        {
            var mode = Enum.TryParse<AlertVisibilityMode>(cfg["Pilot:AlertVisibilityMode"], true, out var m)
                ? m : AlertVisibilityMode.Silent;

            var store = new Store { Name = "Demo Store", Organization = "demo", AlertVisibilityMode = mode };
            db.Stores.Add(store);

            var camera = new Camera
            {
                StoreId = store.Id,
                Name = "Aisle 1 - High Value",
                RtspUrl = "file://samples/test.mp4",
                Status = CameraStatus.AnalyticsOnly
            };
            db.Cameras.Add(camera);

            // Demo zones (normalized coords) so all Phase 1A patterns can fire out of the box.
            db.CameraZones.AddRange(
                new CameraZone
                {
                    CameraId = camera.Id,
                    Name = "High-Value Shelf",
                    ZoneType = ZoneType.HighValue,
                    PolygonJson = "[[0.5,0.1],[0.95,0.1],[0.95,0.9],[0.5,0.9]]"
                },
                new CameraZone
                {
                    CameraId = camera.Id,
                    Name = "Checkout",
                    ZoneType = ZoneType.Checkout,
                    PolygonJson = "[[0.0,0.6],[0.25,0.6],[0.25,1.0],[0.0,1.0]]"
                },
                new CameraZone
                {
                    CameraId = camera.Id,
                    Name = "Exit",
                    ZoneType = ZoneType.Exit,
                    PolygonJson = "[[0.0,0.0],[0.15,0.0],[0.15,0.4],[0.0,0.4]]"
                },
                new CameraZone
                {
                    CameraId = camera.Id,
                    Name = "Blind Spot",
                    ZoneType = ZoneType.BlindSpot,
                    PolygonJson = "[[0.3,0.0],[0.48,0.0],[0.48,0.35],[0.3,0.35]]"
                });
        }

        await db.SaveChangesAsync();
    }
}
