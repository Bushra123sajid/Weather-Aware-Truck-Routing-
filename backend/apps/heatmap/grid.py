"""Corridor sample grid around a set of routes (pure)."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from apps.common.geo import MILES_PER_DEG_LAT, LatLng, miles_per_deg_lng, resample_along

DEFAULT_BUFFER_MI = 25.0
DEFAULT_MAX_POINTS = 250
MIN_SPACING_MI = 5.0


@dataclass(frozen=True)
class CorridorGrid:
    points: list[LatLng]
    spacing_mi: float
    buffer_mi: float


class _Projector:
    """Local equirectangular projection to miles (accurate enough at corridor scale)."""

    def __init__(self, ref_lat: float) -> None:
        self.kx = max(miles_per_deg_lng(ref_lat), 1e-6)
        self.ky = MILES_PER_DEG_LAT

    def to_xy(self, p: LatLng) -> tuple[float, float]:
        return p[1] * self.kx, p[0] * self.ky

    def to_latlng(self, x: float, y: float) -> LatLng:
        return y / self.ky, x / self.kx


def _lattice(
    samples_xy: list[tuple[float, float]], buffer: float, spacing: float
) -> list[tuple[float, float]]:
    cells: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for x, y in samples_xy:
        cells[(math.floor(x / buffer), math.floor(y / buffer))].append((x, y))
    xs = [p[0] for p in samples_xy]
    ys = [p[1] for p in samples_xy]
    min_x, max_x = min(xs) - buffer, max(xs) + buffer
    min_y, max_y = min(ys) - buffer, max(ys) + buffer
    b2 = buffer * buffer
    out = []
    # Anchor the lattice to a multiple of spacing so it's stable across requests.
    y = math.floor(min_y / spacing) * spacing
    while y <= max_y:
        x = math.floor(min_x / spacing) * spacing
        while x <= max_x:
            cx, cy = math.floor(x / buffer), math.floor(y / buffer)
            hit = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for sx, sy in cells.get((cx + dx, cy + dy), ()):
                        if (sx - x) ** 2 + (sy - y) ** 2 <= b2:
                            hit = True
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit:
                out.append((x, y))
            x += spacing
        y += spacing
    return out


def build_corridor_grid(
    routes: Sequence[Sequence[LatLng]],
    *,
    buffer_mi: float = DEFAULT_BUFFER_MI,
    max_points: int = DEFAULT_MAX_POINTS,
    min_spacing_mi: float = MIN_SPACING_MI,
) -> CorridorGrid:
    """Regular grid of points within buffer_mi of any route, widened until it fits max_points."""
    all_coords = [p for r in routes for p in r]
    if not all_coords:
        return CorridorGrid(points=[], spacing_mi=0.0, buffer_mi=buffer_mi)
    ref_lat = sum(p[0] for p in all_coords) / len(all_coords)
    proj = _Projector(ref_lat)
    step = min(5.0, buffer_mi / 4)
    samples = [proj.to_xy(p) for r in routes for p in resample_along(list(r), step)]

    coarse = buffer_mi / 2
    area = len(_lattice(samples, buffer_mi, coarse)) * coarse * coarse
    spacing = max(min_spacing_mi, math.sqrt(area / max_points))
    pts = _lattice(samples, buffer_mi, spacing)
    while len(pts) > max_points:
        spacing *= 1.1
        pts = _lattice(samples, buffer_mi, spacing)

    latlngs = [tuple(round(c, 4) for c in proj.to_latlng(x, y)) for x, y in pts]
    return CorridorGrid(points=latlngs, spacing_mi=round(spacing, 2), buffer_mi=buffer_mi)  # type: ignore[arg-type]
