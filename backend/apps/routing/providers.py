"""Routing provider adapters. Each converts a third-party response into :class:`Route`."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

from django.conf import settings

from apps.common.errors import ProviderError
from apps.common.geo import LatLng, decode_polyline
from apps.common.http import build_session, request_json

from .models import Route, route_from_segment_durations, route_from_steps

logger = logging.getLogger(__name__)


class RoutingProvider(Protocol):
    name: str

    def get_routes(
        self,
        origin: LatLng,
        destination: LatLng,
        alternatives: int,
        via: Sequence[LatLng] = (),
    ) -> list[Route]:
        """Up to `alternatives` routes; `via` forces intermediate waypoints and disables alternatives."""
        ...


class OpenRouteServiceProvider:
    """OpenRouteService directions, ``driving-hgv`` profile (heavy goods vehicle)."""

    name = "openrouteservice"
    profile = "driving-hgv"

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = (base_url or settings.ORS_BASE_URL).rstrip("/")
        self.session = build_session()

    def get_routes(
        self,
        origin: LatLng,
        destination: LatLng,
        alternatives: int,
        via: Sequence[LatLng] = (),
    ) -> list[Route]:
        points = [origin, *via, destination]
        body: dict = {
            "coordinates": [[p[1], p[0]] for p in points],
            "instructions": True,
            "units": "m",
        }
        if alternatives > 1 and not via:
            body["alternative_routes"] = {
                "target_count": alternatives,
                "weight_factor": 1.6,
                "share_factor": 0.6,
            }
        data = request_json(
            self.session,
            "POST",
            f"{self.base_url}/v2/directions/{self.profile}/geojson",
            provider=self.name,
            json=body,
            headers={"Authorization": self.api_key, "Content-Type": "application/json"},
        )
        return self.parse(data)

    @classmethod
    def parse(cls, data: dict) -> list[Route]:
        routes: list[Route] = []
        for feature in data.get("features") or []:
            raw = feature.get("geometry", {}).get("coordinates") or []
            coords = [(float(c[1]), float(c[0])) for c in raw]
            if len(coords) < 2:
                continue
            props = feature.get("properties") or {}
            summary = props.get("summary") or {}
            duration = float(summary.get("duration", 0) or 0)
            steps = [
                (int(st["way_points"][0]), int(st["way_points"][1]), float(st.get("duration", 0)))
                for seg in props.get("segments") or []
                for st in seg.get("steps") or []
                if st.get("way_points")
            ]
            if not steps:
                steps = [(0, len(coords) - 1, duration)]
            routes.append(
                route_from_steps(
                    coords,
                    steps,
                    distance_m=float(summary.get("distance", 0) or 0),
                    duration_s=duration,
                    provider=cls.name,
                    profile=cls.profile,
                )
            )
        if not routes:
            raise ProviderError("OpenRouteService returned no routes", provider=cls.name)
        return routes


class OSRMProvider:
    """OSRM HTTP API (public demo server by default; car profile only)."""

    name = "osrm"
    profile = "driving"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.session = build_session()

    def get_routes(
        self,
        origin: LatLng,
        destination: LatLng,
        alternatives: int,
        via: Sequence[LatLng] = (),
    ) -> list[Route]:
        coords = ";".join(f"{p[1]},{p[0]}" for p in (origin, *via, destination))
        if via:
            alternatives = 1
        data = request_json(
            self.session,
            "GET",
            f"{self.base_url}/route/v1/{self.profile}/{coords}",
            provider=self.name,
            params={
                "alternatives": str(max(0, alternatives)) if alternatives > 1 else "false",
                "overview": "full",
                "geometries": "polyline",
                "steps": "false",
                "annotations": "duration",
            },
        )
        return self.parse(data)

    @classmethod
    def parse(cls, data: dict) -> list[Route]:
        if data.get("code") not in (None, "Ok"):
            raise ProviderError(
                f"OSRM error: {data.get('message') or data.get('code')}", provider=cls.name
            )
        routes: list[Route] = []
        for raw in data.get("routes") or []:
            coords = decode_polyline(raw.get("geometry") or "")
            if len(coords) < 2:
                continue
            distance = float(raw.get("distance", 0) or 0)
            duration = float(raw.get("duration", 0) or 0)
            seg_durations: list[float] = []
            for leg in raw.get("legs") or []:
                seg_durations.extend((leg.get("annotation") or {}).get("duration") or [])
            if len(seg_durations) == len(coords) - 1:
                route = route_from_segment_durations(
                    coords,
                    seg_durations,
                    distance_m=distance,
                    duration_s=duration,
                    provider=cls.name,
                    profile=cls.profile,
                )
            else:
                # Fall back to leg-level durations distributed by distance.
                steps, idx = [], 0
                legs = raw.get("legs") or [{"duration": duration}]
                per_leg = max(1, (len(coords) - 1) // len(legs))
                for n, leg in enumerate(legs):
                    end = len(coords) - 1 if n == len(legs) - 1 else idx + per_leg
                    steps.append((idx, end, float(leg.get("duration", 0) or 0)))
                    idx = end
                route = route_from_steps(
                    coords,
                    steps,
                    distance_m=distance,
                    duration_s=duration,
                    provider=cls.name,
                    profile=cls.profile,
                )
            routes.append(route)
        if not routes:
            raise ProviderError("OSRM returned no routes", provider=cls.name)
        return routes
