using Microsoft.EntityFrameworkCore;
using Onevo.Api.Domain;
using Onevo.Api.Services;

namespace Onevo.Api.Data;

public static class DbSeeder
{
    public static async Task SeedAsync(OnevoDbContext db, IConfiguration cfg)
    {
        try
        {
            await db.Database.MigrateAsync();
        }
        catch
        {
            await db.Database.EnsureCreatedAsync();
        }
        // Legacy development databases were created with EnsureCreated, which does not
        // add newly introduced tables. Keep this bootstrap idempotent for both existing
        // installations and clean databases.
        await db.Database.ExecuteSqlRawAsync(
            """
            ALTER TABLE "Cameras" ADD COLUMN IF NOT EXISTS "ConnectorId" uuid NULL;
            ALTER TABLE "Cameras" ADD COLUMN IF NOT EXISTS "SourceKey" text NULL;
            CREATE INDEX IF NOT EXISTS "IX_Cameras_ConnectorId" ON "Cameras" ("ConnectorId");
            CREATE UNIQUE INDEX IF NOT EXISTS "IX_Cameras_ConnectorId_SourceKey"
                ON "Cameras" ("ConnectorId", "SourceKey")
                WHERE "SourceKey" IS NOT NULL;
            CREATE TABLE IF NOT EXISTS "ConnectorSetupCodes" (
                "Id" uuid NOT NULL,
                "StoreId" uuid NOT NULL,
                "CodeHash" text NOT NULL,
                "ExpiresAt" timestamp with time zone NOT NULL,
                "UsedAt" timestamp with time zone NULL,
                "CreatedBy" uuid NOT NULL,
                "CreatedAt" timestamp with time zone NOT NULL,
                CONSTRAINT "PK_ConnectorSetupCodes" PRIMARY KEY ("Id")
            );
            CREATE INDEX IF NOT EXISTS "IX_ConnectorSetupCodes_ExpiresAt"
                ON "ConnectorSetupCodes" ("ExpiresAt");

            -- Consolidate legacy duplicate connectors before enforcing the
            -- one-store/one-connector invariant. Preserve camera and clip history
            -- by moving references to the most recently active connector.
            WITH ranked AS (
                SELECT "Id", "StoreId",
                       FIRST_VALUE("Id") OVER (
                           PARTITION BY "StoreId"
                           ORDER BY "LastHeartbeat" DESC NULLS LAST, "CreatedAt" DESC, "Id"
                       ) AS keeper_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY "StoreId"
                           ORDER BY "LastHeartbeat" DESC NULLS LAST, "CreatedAt" DESC, "Id"
                       ) AS row_number
                FROM "Connectors"
            )
            UPDATE "Cameras" AS camera
            SET "ConnectorId" = ranked.keeper_id
            FROM ranked
            WHERE camera."ConnectorId" = ranked."Id" AND ranked.row_number > 1;

            WITH ranked AS (
                SELECT "Id",
                       FIRST_VALUE("Id") OVER (
                           PARTITION BY "StoreId"
                           ORDER BY "LastHeartbeat" DESC NULLS LAST, "CreatedAt" DESC, "Id"
                       ) AS keeper_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY "StoreId"
                           ORDER BY "LastHeartbeat" DESC NULLS LAST, "CreatedAt" DESC, "Id"
                       ) AS row_number
                FROM "Connectors"
            )
            UPDATE "Clips" AS clip
            SET "ConnectorId" = ranked.keeper_id
            FROM ranked
            WHERE clip."ConnectorId" = ranked."Id" AND ranked.row_number > 1;

            WITH ranked AS (
                SELECT "Id",
                       ROW_NUMBER() OVER (
                           PARTITION BY "StoreId"
                           ORDER BY "LastHeartbeat" DESC NULLS LAST, "CreatedAt" DESC, "Id"
                       ) AS row_number
                FROM "Connectors"
            )
            DELETE FROM "Connectors" AS connector
            USING ranked
            WHERE connector."Id" = ranked."Id" AND ranked.row_number > 1;

            -- Ensure a legacy non-unique FK index with this name cannot silently
            -- defeat the one-connector-per-store invariant.
            DROP INDEX IF EXISTS "IX_Connectors_StoreId";
            CREATE UNIQUE INDEX "IX_Connectors_StoreId"
                ON "Connectors" ("StoreId");

            -- Detach dependants from orphan connectors, then remove those
            -- connectors before enforcing Connectors(StoreId) -> Stores(Id).
            UPDATE "Cameras" AS camera
            SET "ConnectorId" = NULL
            WHERE camera."ConnectorId" IN (
                SELECT connector."Id"
                FROM "Connectors" connector
                WHERE NOT EXISTS (
                    SELECT 1 FROM "Stores" store
                    WHERE store."Id" = connector."StoreId"
                )
            );

            UPDATE "Clips" AS clip
            SET "ConnectorId" = NULL
            WHERE clip."ConnectorId" IN (
                SELECT connector."Id"
                FROM "Connectors" connector
                WHERE NOT EXISTS (
                    SELECT 1 FROM "Stores" store
                    WHERE store."Id" = connector."StoreId"
                )
            );

            DELETE FROM "Connectors" AS connector
            WHERE NOT EXISTS (
                SELECT 1 FROM "Stores" store
                WHERE store."Id" = connector."StoreId"
            );

            -- Remove any other invalid legacy camera assignments before adding the FK.
            UPDATE "Cameras" AS camera
            SET "ConnectorId" = NULL
            WHERE camera."ConnectorId" IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM "Connectors" connector
                  WHERE connector."Id" = camera."ConnectorId"
              );

            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'FK_Connectors_Stores_StoreId'
                ) THEN
                    ALTER TABLE "Connectors"
                    ADD CONSTRAINT "FK_Connectors_Stores_StoreId"
                    FOREIGN KEY ("StoreId") REFERENCES "Stores" ("Id")
                    ON DELETE CASCADE;
                END IF;

                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'FK_Cameras_Connectors_ConnectorId'
                ) THEN
                    ALTER TABLE "Cameras"
                    ADD CONSTRAINT "FK_Cameras_Connectors_ConnectorId"
                    FOREIGN KEY ("ConnectorId") REFERENCES "Connectors" ("Id")
                    ON DELETE SET NULL;
                END IF;
            END $$;
            ALTER TABLE "Users" ADD COLUMN IF NOT EXISTS "StoreId" uuid NULL;
            CREATE INDEX IF NOT EXISTS "IX_Users_StoreId" ON "Users" ("StoreId");
            ALTER TABLE "Stores" ADD COLUMN IF NOT EXISTS "NotificationEmail" text NULL;
            ALTER TABLE "Connectors" ADD COLUMN IF NOT EXISTS "AdminHost" text NULL;
            ALTER TABLE "Connectors" ADD COLUMN IF NOT EXISTS "AdminPort" integer NULL;

            -- Human-in-the-loop training dataset (Stage 1+2).
            ALTER TABLE "AlertReviews" ADD COLUMN IF NOT EXISTS "ConfirmedPatternsJson" text NULL;
            CREATE TABLE IF NOT EXISTS "TrainingSamples" (
                "Id" uuid NOT NULL,
                "AlertId" uuid NOT NULL,
                "ClipId" uuid NOT NULL,
                "SourceClipObjectKey" text NOT NULL,
                "DatasetClipObjectKey" text NOT NULL,
                "StoreId" uuid NOT NULL,
                "CameraId" uuid NOT NULL,
                "AlertType" text NOT NULL,
                "ReviewOutcome" text NOT NULL,
                "ReviewerId" uuid NOT NULL,
                "ModelVersion" text NOT NULL,
                "RuleVersion" text NOT NULL,
                "DatasetStatus" text NOT NULL,
                "IncludeInTraining" boolean NOT NULL,
                "EditHistoryJson" text NOT NULL,
                "CreatedAt" timestamp with time zone NOT NULL,
                "UpdatedAt" timestamp with time zone NOT NULL,
                CONSTRAINT "PK_TrainingSamples" PRIMARY KEY ("Id")
            );
            CREATE UNIQUE INDEX IF NOT EXISTS "IX_TrainingSamples_AlertId"
                ON "TrainingSamples" ("AlertId");
            CREATE INDEX IF NOT EXISTS "IX_TrainingSamples_StoreId"
                ON "TrainingSamples" ("StoreId");
            CREATE INDEX IF NOT EXISTS "IX_TrainingSamples_DatasetStatus"
                ON "TrainingSamples" ("DatasetStatus");
            CREATE INDEX IF NOT EXISTS "IX_TrainingSamples_CreatedAt"
                ON "TrainingSamples" ("CreatedAt");
            CREATE TABLE IF NOT EXISTS "TrainingSamplePatterns" (
                "Id" uuid NOT NULL,
                "TrainingSampleId" uuid NOT NULL,
                "Pattern" text NOT NULL,
                "AiDetected" boolean NOT NULL,
                "HumanConfirmed" boolean NOT NULL,
                "LabelStatus" text NOT NULL,
                CONSTRAINT "PK_TrainingSamplePatterns" PRIMARY KEY ("Id")
            );
            CREATE UNIQUE INDEX IF NOT EXISTS "IX_TrainingSamplePatterns_TrainingSampleId_Pattern"
                ON "TrainingSamplePatterns" ("TrainingSampleId", "Pattern");
            CREATE INDEX IF NOT EXISTS "IX_TrainingSamplePatterns_Pattern_LabelStatus"
                ON "TrainingSamplePatterns" ("Pattern", "LabelStatus");
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'FK_TrainingSamplePatterns_TrainingSamples_TrainingSampleId'
                ) THEN
                    ALTER TABLE "TrainingSamplePatterns"
                    ADD CONSTRAINT "FK_TrainingSamplePatterns_TrainingSamples_TrainingSampleId"
                    FOREIGN KEY ("TrainingSampleId") REFERENCES "TrainingSamples" ("Id")
                    ON DELETE CASCADE;
                END IF;
            END $$;
            """
        );

        // Seed admin user (skip default credentials in Production unless explicitly enabled).
        var isProduction = string.Equals(
            cfg["ASPNETCORE_ENVIRONMENT"], "Production", StringComparison.OrdinalIgnoreCase);
        var allowDefaultSeed = bool.TryParse(cfg["Seed:AllowDefaultInProduction"], out var allowSeed) && allowSeed;
        var adminEmail = cfg["Seed:AdminEmail"] ?? "admin@onevo.local";
        var adminPassword = cfg["Seed:AdminPassword"] ?? "Admin123!";
        var skipDefaultAdmin = isProduction && !allowDefaultSeed
            && adminEmail == "admin@onevo.local"
            && adminPassword == "Admin123!";

        if (!skipDefaultAdmin && !await db.Users.AnyAsync(u => u.Email == adminEmail))
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

        // Seed demo store in Development; in Production only when Seed:DemoStore=true.
        var seedDemo = !isProduction
            || (bool.TryParse(cfg["Seed:DemoStore"], out var demoOn) && demoOn);
        if (seedDemo && !await db.Stores.AnyAsync())
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

