"""Geocoding adapters (Nominatim and OpenRouteService/Pelias) behind one service."""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Protocol

from django.conf import settings

from apps.common.cache import get_or_set, make_key
from apps.common.errors import LocationNotFoundError
from apps.common.http import build_session, request_json

GEOCODE_CACHE_TTL = 24 * 3600


@dataclass(frozen=True, slots=True)
class Place:
    label: str
    lat: float
    lng: float

    def as_dict(self) -> dict:
        return asdict(self)


class Geocoder(Protocol):
    name: str

    def search(self, query: str, limit: int) -> list[Place]: ...


class NominatimGeocoder:
    """OSM Nominatim. Usage policy: identifying User-Agent, max 1 request/second, cache results."""

    name = "nominatim"
    _lock = threading.Lock()
    _last_call = 0.0
    MIN_INTERVAL_S = 1.0

    def __init__(self) -> None:
        self.base_url = settings.NOMINATIM_BASE_URL.rstrip("/")
        self.session = build_session(user_agent=settings.NOMINATIM_USER_AGENT)

    def _throttle(self) -> None:
        with NominatimGeocoder._lock:
            wait = NominatimGeocoder._last_call + self.MIN_INTERVAL_S - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            NominatimGeocoder._last_call = time.monotonic()

    def search(self, query: str, limit: int) -> list[Place]:
        self._throttle()
        params = {"q": query, "format": "jsonv2", "limit": str(limit), "addressdetails": "0"}
        if settings.GEOCODE_COUNTRY_CODES:
            params["countrycodes"] = settings.GEOCODE_COUNTRY_CODES
        data = request_json(
            self.session, "GET", f"{self.base_url}/search", provider=self.name, params=params
        )
        return [
            Place(label=item["display_name"], lat=float(item["lat"]), lng=float(item["lon"]))
            for item in data
            if "lat" in item and "lon" in item
        ]


class ORSGeocoder:
    """OpenRouteService Pelias autocomplete (requires ORS_API_KEY)."""

    name = "openrouteservice"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.base_url = settings.ORS_BASE_URL.rstrip("/")
        self.session = build_session()

    def search(self, query: str, limit: int) -> list[Place]:
        params = {"api_key": self.api_key, "text": query, "size": str(limit)}
        if settings.GEOCODE_COUNTRY_CODES:
            params["boundary.country"] = settings.GEOCODE_COUNTRY_CODES.upper()
        data = request_json(
            self.session,
            "GET",
            f"{self.base_url}/geocode/autocomplete",
            provider=self.name,
            params=params,
        )
        places = []
        for feat in data.get("features") or []:
            lng, lat = feat["geometry"]["coordinates"][:2]
            label = (feat.get("properties") or {}).get("label") or f"{lat:.4f}, {lng:.4f}"
            places.append(Place(label=label, lat=float(lat), lng=float(lng)))
        return places


class GeocodingService:
    def __init__(self, geocoder: Geocoder) -> None:
        self.geocoder = geocoder

    @classmethod
    def from_settings(cls) -> GeocodingService:
        if settings.ORS_API_KEY:
            return cls(ORSGeocoder(settings.ORS_API_KEY))
        return cls(NominatimGeocoder())

    def search(self, query: str, limit: int = 5) -> list[Place]:
        q = " ".join(query.split()).lower()
        key = make_key("geo", {"q": q, "n": limit, "p": self.geocoder.name})
        return get_or_set(key, GEOCODE_CACHE_TTL, lambda: self.geocoder.search(q, limit)) or []

    def resolve(self, query: str) -> Place:
        """Best match for free text; raises if nothing matches."""
        results = self.search(query, limit=1)
        if not results:
            raise LocationNotFoundError(f"Could not find a location matching '{query}'.")
        return results[0]
