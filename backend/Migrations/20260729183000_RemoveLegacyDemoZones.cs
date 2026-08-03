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
        // The schema has no reliable demo provenance marker. Deleting by zone
        // name and polygon alone could remove legitimate customer zones.
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        // Removed synthetic zones cannot be safely associated with cameras again.
    }
}
