"""Shared fixtures and fake providers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

import pytest
from django.core.cache import cache

from apps.common.geo import LatLng
from apps.routing.models import Route, route_from_segment_durations
from apps.weather.models import LocationForecast


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _no_throttle(settings):
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}


def straight_route(
    start: LatLng, end: LatLng, n: int = 50, mph: float = 60.0, provider: str = "fake"
) -> Route:
    """A straight route with ``n`` vertices driven at constant speed."""
    coords = [
        (start[0] + (end[0] - start[0]) * i / (n - 1), start[1] + (end[1] - start[1]) * i / (n - 1))
        for i in range(n)
    ]
    from apps.common.geo import haversine_mi

    seg = [haversine_mi(coords[i], coords[i + 1]) / mph * 3600 for i in range(n - 1)]
    dist_mi = sum(haversine_mi(coords[i], coords[i + 1]) for i in range(n - 1))
    return route_from_segment_durations(
        coords,
        seg,
        distance_m=dist_mi * 1609.344,
        duration_s=sum(seg),
        provider=provider,
        profile="test",
    )


class FakeRoutingProvider:
    """Returns canned routes; ``via_route`` (if given) answers any waypoint request."""

    def __init__(
        self, routes: list[Route], name: str = "fake", via_route: Route | None = None
    ) -> None:
        self.routes = routes
        self.name = name
        self.via_route = via_route
        self.calls = 0
        self.via_calls: list[LatLng] = []

    def get_routes(self, origin, destination, alternatives, via=()):
        if via:
            self.via_calls.append(via[0])
            return [self.via_route] if self.via_route else []
        self.calls += 1
        return self.routes[:alternatives]


WeatherFn = Callable[[LatLng, datetime], tuple[float, float, float]]


class FakeWeather:
    """Generates hourly UTC forecasts from a function of (point, hour)."""

    def __init__(
        self, fn: WeatherFn | None = None, fail_if: Callable[[LatLng], bool] | None = None
    ):
        self.fn = fn or (lambda p, t: (5.0, 0.0, 0.0))
        self.fail_if = fail_if or (lambda p: False)
        self.calls: list[tuple[int, str, int]] = []

    def fetch(
        self, points: Sequence[LatLng], *, timezone: str = "auto", forecast_days: int = 3
    ) -> list[LocationForecast | None]:
        self.calls.append((len(points), timezone, forecast_days))
        start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
        times = [start + timedelta(hours=i) for i in range(24 * forecast_days + 4)]
        out: list[LocationForecast | None] = []
        for p in points:
            if self.fail_if(p):
                out.append(None)
                continue
            vals = [self.fn(p, t) for t in times]
            out.append(
                LocationForecast(
                    lat=p[0],
                    lng=p[1],
                    timezone="UTC",
                    utc_offset_seconds=0,
                    times_utc=times,
                    wind_mph=[v[0] for v in vals],
                    gust_mph=[v[0] * 1.3 for v in vals],
                    rain_in_hr=[v[1] for v in vals],
                    snow_in_hr=[v[2] for v in vals],
                    precip_in_hr=[v[1] + v[2] for v in vals],
                )
            )
        return out
