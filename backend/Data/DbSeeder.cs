using Microsoft.EntityFrameworkCore;
using Onevo.Api.Domain;
using Onevo.Api.Services;

namespace Onevo.Api.Data;

public static class DbSeeder
{
    public static async Task SeedAsync(OnevoDbContext db, IConfiguration cfg)
    {
        await db.Database.EnsureCreatedAsync();
        // Legacy development databases were created with EnsureCreated, which does not
        // add newly introduced tables. Keep this bootstrap idempotent for both existing
        // installations and clean databases.
        await db.Database.ExecuteSqlRawAsync(
            """
            ALTER TABLE "Cameras" ADD COLUMN IF NOT EXISTS "ConnectorId" uuid NULL;
            CREATE INDEX IF NOT EXISTS "IX_Cameras_ConnectorId" ON "Cameras" ("ConnectorId");
            CREATE TABLE IF NOT EXISTS "ConnectorSetupCodes" (
                "Id" uuid NOT NULL,
                "StoreId" uuid NOT NULL,
                "CodeLookup" text NOT NULL,
                "CodeHash" text NOT NULL,
                "ExpiresAt" timestamp with time zone NOT NULL,
                "UsedAt" timestamp with time zone NULL,
                "CreatedBy" uuid NOT NULL,
                "CreatedAt" timestamp with time zone NOT NULL,
                CONSTRAINT "PK_ConnectorSetupCodes" PRIMARY KEY ("Id")
            );
            CREATE INDEX IF NOT EXISTS "IX_ConnectorSetupCodes_ExpiresAt"
                ON "ConnectorSetupCodes" ("ExpiresAt");
            ALTER TABLE "ConnectorSetupCodes"
                ADD COLUMN IF NOT EXISTS "CodeLookup" text NOT NULL DEFAULT '';
            CREATE UNIQUE INDEX IF NOT EXISTS "IX_ConnectorSetupCodes_CodeLookup"
                ON "ConnectorSetupCodes" ("CodeLookup")
                WHERE "CodeLookup" <> '';
            CREATE INDEX IF NOT EXISTS "IX_Connectors_StoreId_Name"
                ON "Connectors" ("StoreId", "Name");
            """
        );

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

            var storeId = Guid.Parse("11111111-1111-1111-1111-111111111111");
            var store = new Store { Id = storeId, Name = "Demo Store", Organization = "demo", AlertVisibilityMode = mode };
            db.Stores.Add(store);

            var camera = new Camera
            {
                StoreId = store.Id,
                Name = "Aisle 1 - High Value",
                RtspUrl = "file://samples/test.mp4",
                Status = CameraStatus.AnalyticsOnly
            };
            db.Cameras.Add(camera);

            var camera2 = new Camera
            {
                StoreId = store.Id,
                Name = "Aisle 2 - Electronics",
                RtspUrl = "file://samples/test.mp4",
                Status = CameraStatus.AnalyticsOnly
            };
            db.Cameras.Add(camera2);

            // Shared installer/seed templates keep test-video behavior identical.
            db.CameraZones.AddRange(DemoZoneTemplates.Create(camera.Id));
            db.CameraZones.AddRange(DemoZoneTemplates.Create(camera2.Id));
        }

        await db.SaveChangesAsync();
    }
}

