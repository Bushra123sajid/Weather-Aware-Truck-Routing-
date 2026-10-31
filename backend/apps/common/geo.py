"""Distance, interpolation and polyline helpers. Coordinates are (lat, lng) tuples."""

from __future__ import annotations

import math
from collections.abc import Sequence

LatLng = tuple[float, float]

EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344
MILES_PER_DEG_LAT = 69.055


def haversine_mi(a: LatLng, b: LatLng) -> float:
    """Great-circle distance between two points in statute miles."""
    lat1, lng1 = map(math.radians, a)
    lat2, lng2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def interpolate(a: LatLng, b: LatLng, t: float) -> LatLng:
    """Linear interpolation in degrees; accurate enough for vertices a few miles apart."""
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def cumulative_miles(coords: Sequence[LatLng]) -> list[float]:
    """Cumulative distance (miles) at each vertex; first element is 0."""
    out = [0.0]
    for i in range(1, len(coords)):
        out.append(out[-1] + haversine_mi(coords[i - 1], coords[i]))
    return out


def decode_polyline(encoded: str, precision: int = 5) -> list[LatLng]:
    """Decode a Google encoded polyline string into ``(lat, lng)`` tuples."""
    coords: list[LatLng] = []
    index = lat = lng = 0
    factor = 10**precision
    length = len(encoded)
    while index < length:
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                if index >= length:
                    raise ValueError("Malformed polyline")
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lng += deltas[1]
        coords.append((lat / factor, lng / factor))
    return coords


def encode_polyline(coords: Sequence[LatLng], precision: int = 5) -> str:
    """Encode ``(lat, lng)`` tuples as a Google encoded polyline string."""
    factor = 10**precision
    out: list[str] = []
    prev_lat = prev_lng = 0
    for lat, lng in coords:
        ilat = round(lat * factor)
        ilng = round(lng * factor)
        for delta in (ilat - prev_lat, ilng - prev_lng):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev_lat, prev_lng = ilat, ilng
    return "".join(out)


def resample_along(coords: Sequence[LatLng], step_mi: float) -> list[LatLng]:
    """Return points every ``step_mi`` along a polyline, always including both ends."""
    if not coords:
        return []
    if len(coords) == 1:
        return [coords[0]]
    cum = cumulative_miles(coords)
    total = cum[-1]
    out: list[LatLng] = []
    target = 0.0
    i = 0
    while target < total:
        while i < len(cum) - 2 and cum[i + 1] < target:
            i += 1
        seg = cum[i + 1] - cum[i]
        t = 0.0 if seg <= 0 else (target - cum[i]) / seg
        out.append(interpolate(coords[i], coords[i + 1], max(0.0, min(1.0, t))))
        target += step_mi
    out.append(coords[-1])
    return out


def miles_per_deg_lng(lat: float) -> float:
    """Miles per degree of longitude at a given latitude."""
    return MILES_PER_DEG_LAT * math.cos(math.radians(lat))
