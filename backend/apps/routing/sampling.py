"""Checkpoint sampling along a route and ETA computation."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta

from apps.common.geo import LatLng, interpolate

from .models import Route

# A final checkpoint closer than this to the previous one is merged into it.
DUPLICATE_EPSILON_MI = 0.05


@dataclass(frozen=True, slots=True)
class SampledPoint:
    lat: float
    lng: float
    mile: float
    elapsed_s: float

    @property
    def latlng(self) -> LatLng:
        return (self.lat, self.lng)

    def eta(self, departure: datetime) -> datetime:
        """Arrival time at this point given an aware departure datetime."""
        return departure + timedelta(seconds=self.elapsed_s)


def position_at_mile(route: Route, mile: float) -> SampledPoint:
    """Interpolate position and elapsed time at a mile marker along the route."""
    cum = route.cum_miles
    mile = max(0.0, min(mile, cum[-1]))
    i = bisect_right(cum, mile) - 1
    i = max(0, min(i, len(cum) - 2))
    seg = cum[i + 1] - cum[i]
    t = 0.0 if seg <= 0 else (mile - cum[i]) / seg
    t = max(0.0, min(1.0, t))
    lat, lng = interpolate(route.coords[i], route.coords[i + 1], t)
    secs = route.cum_seconds[i] + (route.cum_seconds[i + 1] - route.cum_seconds[i]) * t
    return SampledPoint(lat=lat, lng=lng, mile=mile, elapsed_s=secs)


def checkpoint_miles(total_mi: float, interval_mi: float) -> list[float]:
    """Mile markers 0, N, 2N, ... plus the destination (never duplicated)."""
    if interval_mi <= 0:
        raise ValueError("interval must be positive")
    marks = []
    k = 0
    while k * interval_mi < total_mi - DUPLICATE_EPSILON_MI:
        marks.append(k * interval_mi)
        k += 1
    marks.append(total_mi)
    return marks


def sample_checkpoints(route: Route, interval_mi: float) -> list[SampledPoint]:
    """Interpolated checkpoints every interval_mi, always including origin and destination."""
    return [position_at_mile(route, m) for m in checkpoint_miles(route.cum_miles[-1], interval_mi)]
