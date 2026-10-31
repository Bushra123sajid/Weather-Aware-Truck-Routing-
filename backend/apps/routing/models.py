"""Provider-agnostic route representation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from apps.common.geo import LatLng, cumulative_miles, haversine_mi

from .timing import build_time_profile


@dataclass(slots=True)
class Route:
    """Route geometry with per-vertex cumulative miles and seconds.

    Both are scaled to the provider's reported distance and duration so checkpoint
    miles agree with the route summary.
    """

    coords: list[LatLng]
    cum_miles: list[float]
    cum_seconds: list[float]
    distance_mi: float
    duration_s: float
    provider: str
    profile: str
    notes: list[str] = field(default_factory=list)

    @property
    def duration_min(self) -> float:
        return self.duration_s / 60.0


def _scaled(values: list[float], target_total: float) -> list[float]:
    if not values or values[-1] <= 0 or target_total <= 0:
        return values
    k = target_total / values[-1]
    return [v * k for v in values]


def route_from_segment_durations(
    coords: Sequence[LatLng],
    segment_seconds: Sequence[float],
    *,
    distance_m: float,
    duration_s: float,
    provider: str,
    profile: str,
) -> Route:
    """Build a :class:`Route` when the provider gives one duration per geometry segment."""
    coords = list(coords)
    cum_s = [0.0]
    for d in segment_seconds:
        cum_s.append(cum_s[-1] + max(0.0, float(d)))
    return _finish(coords, cum_s, distance_m, duration_s, provider, profile)


def route_from_steps(
    coords: Sequence[LatLng],
    steps: Sequence[tuple[int, int, float]],
    *,
    distance_m: float,
    duration_s: float,
    provider: str,
    profile: str,
) -> Route:
    """Build a :class:`Route` from steps ``(start_idx, end_idx, duration_s)``."""
    coords = list(coords)
    cum_s = build_time_profile(coords, steps)
    return _finish(coords, cum_s, distance_m, duration_s, provider, profile)


def _finish(
    coords: list[LatLng],
    cum_s: list[float],
    distance_m: float,
    duration_s: float,
    provider: str,
    profile: str,
) -> Route:
    if len(coords) < 2:
        raise ValueError("A route needs at least two coordinates")
    if len(cum_s) != len(coords):
        raise ValueError("Time profile does not match geometry length")
    cum_mi = cumulative_miles(coords)
    distance_mi = distance_m / 1609.344 if distance_m > 0 else cum_mi[-1]
    duration_s = duration_s if duration_s > 0 else cum_s[-1]
    return Route(
        coords=coords,
        cum_miles=_scaled(cum_mi, distance_mi),
        cum_seconds=_scaled(cum_s, duration_s),
        distance_mi=distance_mi,
        duration_s=duration_s,
        provider=provider,
        profile=profile,
    )


def routes_overlap(a: Route, b: Route, *, tolerance_mi: float = 0.5) -> bool:
    """True when b follows the same roads as a, checked at nine interior points of b."""
    if abs(a.distance_mi - b.distance_mi) > max(1.0, 0.05 * a.distance_mi):
        return False
    stride = max(1, len(a.coords) // 2000)
    ref = a.coords[::stride] + [a.coords[-1]]
    total = b.cum_miles[-1]
    j = 0
    for k in range(1, 10):
        target = total * k / 10
        while j < len(b.cum_miles) - 1 and b.cum_miles[j] < target:
            j += 1
        p = b.coords[j]
        if min(haversine_mi(p, q) for q in ref) > tolerance_mi:
            return False
    return True
