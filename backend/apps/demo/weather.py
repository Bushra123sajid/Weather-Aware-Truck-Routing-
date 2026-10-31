"""Weather provider that evaluates the storm model instead of calling Open-Meteo."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from apps.common.geo import LatLng
from apps.weather.models import LocationForecast

from .storm import StormCell, conditions_at

HOURS_BEFORE = 48  # the heatmap axis can start up to 48 h before departure
HOURS_AFTER = 72  # departure + longest demo trip + slack
GUST_FACTOR = 1.35

# Approximate Mountain/Central boundary for the demo corridor, used only for display.
CENTRAL_TIME_EAST_OF_LNG = -101.5


def zone_for(point: LatLng) -> str:
    return "America/Chicago" if point[1] >= CENTRAL_TIME_EAST_OF_LNG else "America/Denver"


class StormWeatherProvider:
    """Same interface as OpenMeteoProvider; values come from the storm cells."""

    name = "demo-storm"

    def __init__(self, cells: tuple[StormCell, ...], anchor: datetime) -> None:
        self.cells = cells
        self.anchor = anchor.astimezone(UTC)

    def fetch(
        self, points: Sequence[LatLng], *, timezone: str = "auto", forecast_days: int = 3
    ) -> list[LocationForecast | None]:
        start = self.anchor.replace(minute=0, second=0, microsecond=0) - timedelta(
            hours=HOURS_BEFORE
        )
        times = [start + timedelta(hours=i) for i in range(HOURS_BEFORE + HOURS_AFTER + 1)]
        offsets = [(t - self.anchor).total_seconds() / 3600 for t in times]
        return [self._forecast(p, times, offsets) for p in points]

    def _forecast(
        self, point: LatLng, times: list[datetime], offsets: list[float]
    ) -> LocationForecast:
        zone = zone_for(point)
        utc_offset = ZoneInfo(zone).utcoffset(self.anchor.replace(tzinfo=None))
        series = [conditions_at(self.cells, point, h) for h in offsets]
        return LocationForecast(
            lat=point[0],
            lng=point[1],
            timezone=zone,
            utc_offset_seconds=int(utc_offset.total_seconds()) if utc_offset else 0,
            times_utc=times,
            wind_mph=[c.wind_mph for c in series],
            gust_mph=[round(c.wind_mph * GUST_FACTOR, 1) for c in series],
            rain_in_hr=[c.rain_in_hr for c in series],
            snow_in_hr=[c.snow_in_hr for c in series],
            precip_in_hr=[round(c.rain_in_hr + c.snow_in_hr / 10, 3) for c in series],
        )
