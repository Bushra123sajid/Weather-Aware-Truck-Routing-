"""Hourly forecast series for one location, with ETA-to-hour lookup."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True, slots=True)
class HourlySample:
    time: datetime  # aware, UTC
    wind_mph: float | None
    gust_mph: float | None
    rain_in_hr: float | None
    snow_in_hr: float | None
    precip_in_hr: float | None


def resolve_tz(name: str | None, utc_offset_seconds: int = 0) -> tzinfo:
    """IANA zone if known (DST-correct), else a fixed offset."""
    from datetime import timezone

    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return timezone(timedelta(seconds=utc_offset_seconds))


@dataclass(slots=True)
class LocationForecast:
    """Hourly arrays aligned with ``times_utc``. Values are already in mph / in-per-hour."""

    lat: float
    lng: float
    timezone: str
    utc_offset_seconds: int
    times_utc: list[datetime]
    wind_mph: list[float | None]
    gust_mph: list[float | None]
    rain_in_hr: list[float | None]
    snow_in_hr: list[float | None]
    precip_in_hr: list[float | None]
    _index: dict[datetime, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._index = {t: i for i, t in enumerate(self.times_utc)}

    @property
    def tz(self) -> tzinfo:
        return resolve_tz(self.timezone, self.utc_offset_seconds)

    def nearest_hour(self, eta: datetime) -> datetime:
        """Round ``eta`` to the nearest hour in this location's local timezone (returns UTC)."""
        local = eta.astimezone(self.tz)
        floored = local.replace(minute=0, second=0, microsecond=0)
        if local - floored >= timedelta(minutes=30):
            floored = floored + timedelta(hours=1)
        return floored.astimezone(UTC)

    def index_for(self, eta: datetime) -> int | None:
        return self._index.get(self.nearest_hour(eta))

    def sample_at(self, eta: datetime) -> HourlySample | None:
        """Forecast for the hour matching ``eta``, or ``None`` if outside the series."""
        i = self.index_for(eta)
        if i is None:
            return None
        return HourlySample(
            time=self.times_utc[i],
            wind_mph=self.wind_mph[i],
            gust_mph=self.gust_mph[i],
            rain_in_hr=self.rain_in_hr[i],
            snow_in_hr=self.snow_in_hr[i],
            precip_in_hr=self.precip_in_hr[i],
        )

    def series_for(self, hours_utc: list[datetime]) -> dict[str, list[float | None]]:
        """Values for each requested UTC hour (``None`` where unavailable)."""
        idx = [self._index.get(h) for h in hours_utc]

        def pick(arr: list[float | None]) -> list[float | None]:
            return [arr[i] if i is not None else None for i in idx]

        return {
            "wind": pick(self.wind_mph),
            "gust": pick(self.gust_mph),
            "rain": pick(self.rain_in_hr),
            "snow": pick(self.snow_in_hr),
        }
