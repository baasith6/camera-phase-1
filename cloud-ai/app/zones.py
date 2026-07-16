"""Zone geometry: parse normalized polygons and point-in-polygon tests."""
import json
from dataclasses import dataclass


@dataclass
class Zone:
    id: str
    name: str
    zone_type: str          # Shelf | HighValue | Checkout | Exit | BlindSpot | Staff
    polygon: list[tuple[float, float]]  # normalized (0..1) coords


def parse_zones(raw: list[dict]) -> list[Zone]:
    zones: list[Zone] = []
    for z in raw:
        try:
            pts = json.loads(z.get("polygonJson") or z.get("PolygonJson") or "[]")
            polygon = [(float(p[0]), float(p[1])) for p in pts]
        except Exception:
            polygon = []
        zones.append(Zone(
            id=z.get("id") or z.get("Id"),
            name=z.get("name") or z.get("Name") or "",
            zone_type=z.get("zoneType") or z.get("ZoneType") or "Shelf",
            polygon=polygon,
        ))
    return zones


def point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    """Ray casting. x,y and poly are normalized 0..1."""
    if len(poly) < 3:
        return False
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def zones_containing(x: float, y: float, zones: list[Zone]) -> list[Zone]:
    return [z for z in zones if point_in_polygon(x, y, z.polygon)]
