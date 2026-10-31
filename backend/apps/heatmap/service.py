"""Build the 0-48 h corridor forecast grid in one batched, cached fetch."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from apps.common.cache import get_or_set, make_key
from apps.common.geo import LatLng
from apps.risk.rules import assess
from apps.weather.providers import OpenMeteoProvider, WeatherProvider

from .grid import build_corridor_grid

HOURS = 49  # hour 0 (current hour) through hour 48 inclusive
HEATMAP_CACHE_TTL = 30 * 60


def forecast_hours(now: datetime | None = None) -> list[datetime]:
    """UTC hours starting at the current (floored) hour."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    h0 = now.replace(minute=0, second=0, microsecond=0)
    return [h0 + timedelta(hours=i) for i in range(HOURS)]


def departure_index(hours: list[datetime], departure: datetime | None) -> int | None:
    """Slider index of the hour nearest to departure, or ``None`` if outside 0-48 h."""
    if departure is None or not hours:
        return None
    delta_h = (departure.astimezone(UTC) - hours[0]).total_seconds() / 3600
    idx = int(delta_h + 0.5) if delta_h >= 0 else -1
    return idx if 0 <= idx < len(hours) else None


def _r(v: float | None, places: int) -> float | None:
    return None if v is None else round(v, places)


class HeatmapService:
    def __init__(self, weather: WeatherProvider, cache_namespace: str = "live") -> None:
        self.weather = weather
        self.cache_namespace = cache_namespace

    @classmethod
    def from_settings(cls) -> HeatmapService:
        return cls(OpenMeteoProvider())

    def build(
        self,
        routes: list[list[LatLng]],
        load_weight_lb: float,
        start_time: datetime | None = None,
    ) -> dict[str, Any]:
        grid = build_corridor_grid(routes)
        hours = forecast_hours()
        key = make_key(
            "heatmap",
            {
                "pts": grid.points,
                "h0": hours[0].isoformat(),
                "load": load_weight_lb,
                "n": self.cache_namespace,
            },
        )
        body = get_or_set(
            key, HEATMAP_CACHE_TTL, lambda: self._compute(grid.points, hours, load_weight_lb)
        )
        return {
            **body,
            "spacing_mi": grid.spacing_mi,
            "buffer_mi": grid.buffer_mi,
            "departure_index": departure_index(hours, start_time),
        }

    def _compute(
        self, points: list[LatLng], hours: list[datetime], load_lb: float
    ) -> dict[str, Any]:
        # UTC so every point shares one hour axis; the client renders local time.
        forecasts = self.weather.fetch(points, timezone="GMT", forecast_days=4)
        out_points = []
        missing = 0
        for (lat, lng), fc in zip(points, forecasts, strict=True):
            if fc is None:
                missing += 1
                continue
            s = fc.series_for(hours)
            risk = []
            for w, r, sn in zip(s["wind"], s["rain"], s["snow"], strict=True):
                a = assess(w, r, sn, load_lb)
                risk.append(int(a.level) if a else None)
            out_points.append(
                {
                    "lat": lat,
                    "lng": lng,
                    "wind": [_r(v, 1) for v in s["wind"]],
                    "rain": [_r(v, 3) for v in s["rain"]],
                    "snow": [_r(v, 3) for v in s["snow"]],
                    "risk": risk,
                }
            )
        warnings = []
        if missing:
            warnings.append(f"Forecast unavailable for {missing} of {len(points)} grid points.")
        return {
            "hours": [h.isoformat() for h in hours],
            "points": out_points,
            "warnings": warnings,
        }
