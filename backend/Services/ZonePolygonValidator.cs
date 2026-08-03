using System.Text.Json;
using System.Collections.Generic;

namespace Onevo.Api.Services;

public static class ZonePolygonValidator
{
    /// <summary>Validates the canonical normalized polygon format: [[x,y], ...].</summary>
    public static bool IsValid(string? polygonJson)
    {
        if (string.IsNullOrWhiteSpace(polygonJson)) return false;

        try
        {
            using var document = JsonDocument.Parse(polygonJson);
            if (document.RootElement.ValueKind != JsonValueKind.Array ||
                document.RootElement.GetArrayLength() < 3)
                return false;

            var points = new List<(double X, double Y)>();
            foreach (var point in document.RootElement.EnumerateArray())
            {
                if (point.ValueKind != JsonValueKind.Array || point.GetArrayLength() != 2)
                    return false;

                var coordinates = point.EnumerateArray().ToArray();
                if (coordinates.Any(c => c.ValueKind != JsonValueKind.Number) ||
                    !coordinates[0].TryGetDouble(out var x) ||
                    !coordinates[1].TryGetDouble(out var y) ||
                    double.IsNaN(x) || double.IsInfinity(x) ||
                    double.IsNaN(y) || double.IsInfinity(y) ||
                    x is < 0 or > 1 || y is < 0 or > 1)
                    return false;

                points.Add((x, y));
            }

            // A line or a repeated point sequence has no monitorable area.
            // Reject it even though it technically contains three coordinates.
            double twiceArea = 0;
            for (var index = 0; index < points.Count; index++)
            {
                var current = points[index];
                var next = points[(index + 1) % points.Count];
                twiceArea += (current.X * next.Y) - (next.X * current.Y);
            }

            for (var first = 0; first < points.Count; first++)
            {
                var firstNext = (first + 1) % points.Count;
                for (var second = first + 1; second < points.Count; second++)
                {
                    var secondNext = (second + 1) % points.Count;
                    if (first == second || firstNext == second ||
                        secondNext == first)
                        continue;
                    if (SegmentsIntersect(
                        points[first], points[firstNext],
                        points[second], points[secondNext]))
                        return false;
                }
            }

            return Math.Abs(twiceArea) >= 0.00002;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool SegmentsIntersect(
        (double X, double Y) a,
        (double X, double Y) b,
        (double X, double Y) c,
        (double X, double Y) d)
    {
        static double Cross(
            (double X, double Y) p,
            (double X, double Y) q,
            (double X, double Y) r) =>
            (q.X - p.X) * (r.Y - p.Y) -
            (q.Y - p.Y) * (r.X - p.X);

        const double epsilon = 1e-12;
        var abC = Cross(a, b, c);
        var abD = Cross(a, b, d);
        var cdA = Cross(c, d, a);
        var cdB = Cross(c, d, b);
        return abC * abD < -epsilon && cdA * cdB < -epsilon;
    }
}
