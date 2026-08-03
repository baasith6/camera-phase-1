using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using Onevo.Api.Data;

#nullable disable

namespace Onevo.Api.Migrations;

[DbContext(typeof(OnevoDbContext))]
[Migration("20260803130000_AddCameraReferenceFrame")]
public partial class AddCameraReferenceFrame : Migration
{
    protected override void Up(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.AddColumn<string>(
            name: "ReferenceFrameObjectKey",
            table: "Cameras",
            type: "text",
            nullable: true);

        migrationBuilder.AddColumn<DateTimeOffset>(
            name: "ReferenceFrameCapturedAt",
            table: "Cameras",
            type: "timestamp with time zone",
            nullable: true);
    }

    protected override void Down(MigrationBuilder migrationBuilder)
    {
        migrationBuilder.DropColumn(
            name: "ReferenceFrameObjectKey",
            table: "Cameras");

        migrationBuilder.DropColumn(
            name: "ReferenceFrameCapturedAt",
            table: "Cameras");
    }
}
