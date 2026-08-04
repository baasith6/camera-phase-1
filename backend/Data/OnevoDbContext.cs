using Microsoft.EntityFrameworkCore;
using Onevo.Api.Domain;

namespace Onevo.Api.Data;

public class OnevoDbContext : DbContext
{
    public OnevoDbContext(DbContextOptions<OnevoDbContext> options) : base(options) { }

    public DbSet<User> Users => Set<User>();
    public DbSet<Store> Stores => Set<Store>();
    public DbSet<Camera> Cameras => Set<Camera>();
    public DbSet<CameraZone> CameraZones => Set<CameraZone>();
    public DbSet<Connector> Connectors => Set<Connector>();
    public DbSet<ConnectorSetupCode> ConnectorSetupCodes => Set<ConnectorSetupCode>();
    public DbSet<Clip> Clips => Set<Clip>();
    public DbSet<AiEvent> AiEvents => Set<AiEvent>();
    public DbSet<RiskEvent> RiskEvents => Set<RiskEvent>();
    public DbSet<Alert> Alerts => Set<Alert>();
    public DbSet<AlertReview> AlertReviews => Set<AlertReview>();
    public DbSet<RuleConfig> RuleConfigs => Set<RuleConfig>();
    public DbSet<TrainingSample> TrainingSamples => Set<TrainingSample>();
    public DbSet<TrainingSamplePattern> TrainingSamplePatterns => Set<TrainingSamplePattern>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<User>().HasIndex(u => u.Email).IsUnique();
        b.Entity<User>()
            .HasOne(u => u.Store)
            .WithMany(s => s.Users)
            .HasForeignKey(u => u.StoreId)
            .OnDelete(DeleteBehavior.SetNull);

        b.Entity<Camera>()
            .HasOne(c => c.Store)
            .WithMany(s => s.Cameras)
            .HasForeignKey(c => c.StoreId)
            .OnDelete(DeleteBehavior.Cascade);

        b.Entity<Connector>()
            .HasOne(c => c.Store)
            .WithOne(s => s.Connector)
            .HasForeignKey<Connector>(c => c.StoreId)
            .OnDelete(DeleteBehavior.Cascade);

        b.Entity<Connector>()
            .HasIndex(c => c.StoreId)
            .IsUnique();

        b.Entity<Camera>()
            .HasOne(c => c.Connector)
            .WithMany(c => c.Cameras)
            .HasForeignKey(c => c.ConnectorId)
            .OnDelete(DeleteBehavior.SetNull);

        b.Entity<Camera>()
            .HasIndex(c => new { c.ConnectorId, c.SourceKey })
            .IsUnique()
            .HasFilter("\"SourceKey\" IS NOT NULL");

        b.Entity<CameraZone>()
            .HasOne(z => z.Camera)
            .WithMany(c => c.Zones)
            .HasForeignKey(z => z.CameraId)
            .OnDelete(DeleteBehavior.Cascade);

        b.Entity<AlertReview>()
            .HasOne(r => r.Alert)
            .WithMany(a => a.Reviews)
            .HasForeignKey(r => r.AlertId)
            .OnDelete(DeleteBehavior.Cascade);

        b.Entity<Clip>().HasIndex(c => c.Status);
        b.Entity<Alert>().HasIndex(a => a.Status);
        b.Entity<AiEvent>().HasIndex(e => e.ClipId);

        // Training dataset: no FK to Alerts (samples must survive alert deletion).
        b.Entity<TrainingSample>().HasIndex(t => t.AlertId).IsUnique();
        b.Entity<TrainingSample>().HasIndex(t => t.StoreId);
        b.Entity<TrainingSample>().HasIndex(t => t.DatasetStatus);
        b.Entity<TrainingSample>().HasIndex(t => t.CreatedAt);
        b.Entity<TrainingSample>()
            .Property(t => t.Version)
            .HasColumnName("xmin")
            .HasColumnType("xid")
            .ValueGeneratedOnAddOrUpdate()
            .IsConcurrencyToken();
        b.Entity<TrainingSamplePattern>()
            .HasOne(p => p.TrainingSample)
            .WithMany(t => t.Patterns)
            .HasForeignKey(p => p.TrainingSampleId)
            .OnDelete(DeleteBehavior.Cascade);
        b.Entity<TrainingSamplePattern>()
            .HasIndex(p => new { p.TrainingSampleId, p.Pattern })
            .IsUnique();
        b.Entity<TrainingSamplePattern>().HasIndex(p => new { p.Pattern, p.LabelStatus });

        // Store enums as strings for readability in the DB.
        b.Entity<User>().Property(x => x.Role).HasConversion<string>();
        b.Entity<Store>().Property(x => x.AlertVisibilityMode).HasConversion<string>();
        b.Entity<Camera>().Property(x => x.Status).HasConversion<string>();
        b.Entity<CameraZone>().Property(x => x.ZoneType).HasConversion<string>();
        b.Entity<Connector>().Property(x => x.Status).HasConversion<string>();
        b.Entity<Clip>().Property(x => x.Status).HasConversion<string>();
        b.Entity<AiEvent>().Property(x => x.EventType).HasConversion<string>();
        b.Entity<Alert>().Property(x => x.RiskLevel).HasConversion<string>();
        b.Entity<Alert>().Property(x => x.Status).HasConversion<string>();
        b.Entity<AlertReview>().Property(x => x.Action).HasConversion<string>();
        b.Entity<TrainingSample>().Property(x => x.ReviewOutcome).HasConversion<string>();
        b.Entity<TrainingSample>().Property(x => x.DatasetStatus).HasConversion<string>();
        b.Entity<TrainingSamplePattern>().Property(x => x.Pattern).HasConversion<string>();
        b.Entity<TrainingSamplePattern>().Property(x => x.LabelStatus).HasConversion<string>();

        base.OnModelCreating(b);
    }
}
