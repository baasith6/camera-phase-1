using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Onevo.Api.Data;

#nullable disable

namespace Onevo.Api.Migrations;

[DbContext(typeof(OnevoDbContext))]
[Migration("20260810120000_AddClipTrackOverlay")]
public partial class AddClipTrackOverlay : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>(
            name: "TrackOverlayJson",
            table: "Clips",
            type: "text",
            nullable: true);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(
            name: "TrackOverlayJson",
            table: "Clips");
    }
}
