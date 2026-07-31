using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Onevo.Api.Data;

#nullable disable

namespace Onevo.Api.Migrations;

[DbContext(typeof(OnevoDbContext))]
[Migration("20260729183000_RemoveLegacyDemoZones")]
public partial class RemoveLegacyDemoZones : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.Sql(
            """
            DELETE FROM "CameraZones"
            WHERE ("Name" = 'High-Value Shelf' AND "ZoneType" = 'HighValue'
                   AND "PolygonJson" = '[[0.5,0.1],[0.95,0.1],[0.95,0.9],[0.5,0.9]]')
               OR ("Name" = 'Checkout' AND "ZoneType" = 'Checkout'
                   AND "PolygonJson" = '[[0.0,0.6],[0.25,0.6],[0.25,1.0],[0.0,1.0]]')
               OR ("Name" = 'Exit' AND "ZoneType" = 'Exit'
                   AND "PolygonJson" = '[[0.0,0.0],[0.15,0.0],[0.15,0.4],[0.0,0.4]]')
               OR ("Name" = 'Blind Spot' AND "ZoneType" = 'BlindSpot'
                   AND "PolygonJson" = '[[0.3,0.0],[0.48,0.0],[0.48,0.35],[0.3,0.35]]');
            """);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        // Removed synthetic zones cannot be safely associated with cameras again.
    }
}
