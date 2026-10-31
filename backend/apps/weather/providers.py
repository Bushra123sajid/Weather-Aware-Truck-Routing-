"""Open-Meteo forecast client with batching, caching and graceful degradation."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Protocol

from django.conf import settings
from django.core.cache import cache

from apps.common.errors import ProviderError
from apps.common.geo import LatLng
from apps.common.http import build_session, request_json

from .models import LocationForecast

logger = logging.getLogger(__name__)

HOURLY_VARS = "wind_speed_10m,wind_gusts_10m,rain,snowfall,precipitation"
BATCH_SIZE = 50  # locations per Open-Meteo request (keeps URLs short)
MAX_WORKERS = 4
CACHE_TTL = 1800
COORD_PLACES = 2  # ~1 km; Open-Meteo model grids are coarser than this anyway

# Open-Meteo reports snowfall in cm by default and in inches when
# precipitation_unit=inch. We read ``hourly_units`` and normalise either way.
SNOW_TO_INCH = {"cm": 1 / 2.54, "mm": 1 / 25.4, "inch": 1.0, "in": 1.0}
PRECIP_TO_INCH = {"mm": 1 / 25.4, "inch": 1.0, "in": 1.0}
WIND_TO_MPH = {"mp/h": 1.0, "mph": 1.0, "km/h": 0.621371, "m/s": 2.236936, "kn": 1.150779}


class WeatherProvider(Protocol):
    def fetch(
        self, points: Sequence[LatLng], *, timezone: str, forecast_days: int
    ) -> list[LocationForecast | None]:
        """One forecast per input point, ``None`` where the provider failed."""
        ...


def _convert(values: list | None, factor: float) -> list[float | None]:
    return [None if v is None else round(float(v) * factor, 4) for v in values or []]


def _local_times_to_utc(stamps: list[str], utc_offset_seconds: int) -> list[datetime]:
    """Decode Open-Meteo local stamps with the series' fixed utc_offset_seconds.

    Open-Meteo keeps one offset for the whole series across a DST change (no repeated
    or skipped hour on 2026-11-01), so decoding with the IANA zone would lose an hour.
    """
    offset = timezone(timedelta(seconds=utc_offset_seconds))
    return [datetime.fromisoformat(s).replace(tzinfo=offset).astimezone(UTC) for s in stamps]


def parse_location(payload: dict[str, Any]) -> LocationForecast:
    """Convert one Open-Meteo location object into a :class:`LocationForecast`."""
    hourly = payload.get("hourly") or {}
    units = payload.get("hourly_units") or {}
    tz_name = payload.get("timezone") or "GMT"
    offset = int(payload.get("utc_offset_seconds") or 0)
    times = _local_times_to_utc(hourly.get("time") or [], offset)
    n = len(times)

    def series(name: str, table: dict[str, float], default_unit: str) -> list[float | None]:
        unit = (units.get(name) or default_unit).strip().lower()
        factor = table.get(unit)
        if factor is None:
            raise ProviderError(f"Unexpected unit {unit!r} for {name}", provider="open-meteo")
        out = _convert(hourly.get(name), factor)
        return out + [None] * (n - len(out))

    return LocationForecast(
        lat=float(payload.get("latitude", 0.0)),
        lng=float(payload.get("longitude", 0.0)),
        timezone=tz_name,
        utc_offset_seconds=offset,
        times_utc=times,
        wind_mph=series("wind_speed_10m", WIND_TO_MPH, "mp/h"),
        gust_mph=series("wind_gusts_10m", WIND_TO_MPH, "mp/h"),
        rain_in_hr=series("rain", PRECIP_TO_INCH, "inch"),
        snow_in_hr=series("snowfall", SNOW_TO_INCH, "inch"),
        precip_in_hr=series("precipitation", PRECIP_TO_INCH, "inch"),
    )


class OpenMeteoProvider:
    """Batched multi-location requests to the Open-Meteo forecast API (no key needed)."""

    name = "open-meteo"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.OPEN_METEO_BASE_URL).rstrip("/")
        self.session = build_session()

    @staticmethod
    def _cache_key(point: LatLng, timezone: str, days: int) -> str:
        hour = datetime.now(UTC).strftime("%Y%m%d%H")
        return (
            f"wx:{timezone}:{days}:{point[0]:.{COORD_PLACES}f}:{point[1]:.{COORD_PLACES}f}:{hour}"
        )

    def fetch(
        self, points: Sequence[LatLng], *, timezone: str = "auto", forecast_days: int = 3
    ) -> list[LocationForecast | None]:
        rounded = [(round(p[0], COORD_PLACES), round(p[1], COORD_PLACES)) for p in points]
        unique = list(dict.fromkeys(rounded))
        keys = {p: self._cache_key(p, timezone, forecast_days) for p in unique}
        cached: dict[str, Any] = cache.get_many(list(keys.values()))
        results: dict[LatLng, LocationForecast | None] = {
            p: cached[k] for p, k in keys.items() if k in cached
        }
        missing = [p for p in unique if p not in results]

        chunks = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
        if chunks:
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(chunks))) as pool:
                for chunk, forecasts in zip(
                    chunks,
                    pool.map(lambda c: self._fetch_chunk(c, timezone, forecast_days), chunks),
                    strict=True,
                ):
                    to_cache = {}
                    for p, fc in zip(chunk, forecasts, strict=True):
                        results[p] = fc
                        if fc is not None:
                            to_cache[keys[p]] = fc
                    if to_cache:
                        cache.set_many(to_cache, CACHE_TTL)
        return [results.get(p) for p in rounded]

    def _fetch_chunk(
        self, chunk: list[LatLng], timezone: str, days: int
    ) -> list[LocationForecast | None]:
        params = {
            "latitude": ",".join(f"{p[0]:.{COORD_PLACES}f}" for p in chunk),
            "longitude": ",".join(f"{p[1]:.{COORD_PLACES}f}" for p in chunk),
            "hourly": HOURLY_VARS,
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": timezone,
            "forecast_days": str(days),
        }
        try:
            data = request_json(
                self.session,
                "GET",
                f"{self.base_url}/v1/forecast",
                provider=self.name,
                params=params,
            )
            items = data if isinstance(data, list) else [data]
            if len(items) != len(chunk):
                raise ProviderError("Location count mismatch", provider=self.name)
            return [parse_location(item) for item in items]
        except ProviderError as exc:
            logger.warning("Weather chunk of %d points failed: %s", len(chunk), exc.message)
            return [None] * len(chunk)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Weather chunk of %d points unparseable: %s", len(chunk), exc)
            return [None] * len(chunk)
