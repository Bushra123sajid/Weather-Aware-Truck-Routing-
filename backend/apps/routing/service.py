"""Routing orchestration: provider fallback, alternative top-up, dedupe and caching."""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from django.conf import settings

from apps.common.cache import get_or_set, make_key
from apps.common.errors import NoRouteError, ProviderError
from apps.common.geo import MILES_PER_DEG_LAT, LatLng, miles_per_deg_lng

from .models import Route, routes_overlap
from .providers import OpenRouteServiceProvider, OSRMProvider, RoutingProvider

logger = logging.getLogger(__name__)

TARGET_ROUTES = 3
ROUTE_CACHE_TTL = 6 * 3600
# Perpendicular waypoint offsets as a fraction of the straight-line trip length.
DETOUR_OFFSETS = (0.15, -0.15, 0.3, -0.3)
MAX_DETOUR_RATIO = 1.5


@dataclass
class RoutingResult:
    routes: list[Route]
    notices: list[str] = field(default_factory=list)


class RoutingService:
    """Primary provider first, then fallback alternatives, then detour waypoints.

    The public ORS API only computes alternatives for short trips and the OSRM demo
    server often returns a single route, so both are topped up to three where possible.
    """

    def __init__(
        self,
        primary: RoutingProvider | None = None,
        fallback: RoutingProvider | None = None,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    @classmethod
    def from_settings(cls) -> RoutingService:
        primary = OpenRouteServiceProvider(settings.ORS_API_KEY) if settings.ORS_API_KEY else None
        return cls(primary=primary, fallback=OSRMProvider())

    def get_routes(self, origin: LatLng, destination: LatLng) -> RoutingResult:
        key = make_key(
            "routes",
            {
                "o": [round(origin[0], 4), round(origin[1], 4)],
                "d": [round(destination[0], 4), round(destination[1], 4)],
                "p": [getattr(self.primary, "name", None), getattr(self.fallback, "name", None)],
            },
        )
        return get_or_set(key, ROUTE_CACHE_TTL, lambda: self._fetch(origin, destination))

    def _fetch(self, origin: LatLng, destination: LatLng) -> RoutingResult:
        routes: list[Route] = []
        notices: list[str] = []
        errors: list[ProviderError] = []

        if self.primary is not None:
            try:
                routes = self.primary.get_routes(origin, destination, TARGET_ROUTES)
            except ProviderError as exc:
                errors.append(exc)
                # The public ORS API rejects alternative_routes on long trips (HTTP 400/404);
                # retry once for a single route before falling back.
                if exc.upstream_status in (400, 404):
                    try:
                        routes = self.primary.get_routes(origin, destination, 1)
                    except ProviderError as exc2:
                        errors.append(exc2)

        if len(routes) < TARGET_ROUTES and self.fallback is not None:
            try:
                extra = self.fallback.get_routes(origin, destination, TARGET_ROUTES)
            except ProviderError as exc:
                errors.append(exc)
                extra = []
            had_primary_routes = bool(routes)
            added = self._add_distinct(routes, extra)
            name = self.fallback.name.upper()
            if added and self.primary is not None and had_primary_routes:
                notices.append(
                    f"{added} alternative route(s) came from {name} (car profile) because the "
                    "truck routing provider returned fewer than 3."
                )
            elif added and self.primary is not None:
                notices.append(
                    f"Truck routing provider was unavailable; routes come from {name} "
                    "(car profile, durations may be optimistic for trucks)."
                )
            elif added:
                notices.append(
                    f"Routes come from {name} (car profile). Set ORS_API_KEY for "
                    "heavy-goods-vehicle routing."
                )

        if routes and len(routes) < TARGET_ROUTES:
            added = self._add_via_alternatives(origin, destination, routes, errors)
            if added:
                notices.append(
                    f"The routing provider returned fewer than 3 alternatives; {added} extra "
                    "option(s) were added by routing through a detour waypoint."
                )

        if not routes:
            raise NoRouteError(
                "No drivable route found between these locations.",
                details={"providers": [e.details for e in errors]},
            )
        if len(routes) < TARGET_ROUTES:
            notices.append(
                f"Only {len(routes)} distinct route option(s) are available for this trip."
            )
        return RoutingResult(routes=routes[:TARGET_ROUTES], notices=notices)

    @staticmethod
    def _add_distinct(routes: list[Route], candidates: list[Route]) -> int:
        """Append candidates that don't duplicate an existing route; return how many."""
        added = 0
        for candidate in candidates:
            if len(routes) >= TARGET_ROUTES:
                break
            if any(routes_overlap(existing, candidate) for existing in routes):
                continue
            routes.append(candidate)
            added += 1
        return added

    def _add_via_alternatives(
        self,
        origin: LatLng,
        destination: LatLng,
        routes: list[Route],
        errors: list[ProviderError],
    ) -> int:
        """Route through waypoints offset from the midpoint; reject detours over 1.5x the shortest route."""
        provider = (
            self.primary if routes[0].provider == getattr(self.primary, "name", None) else None
        )
        provider = provider or self.fallback or self.primary
        if provider is None:
            return 0
        waypoints = detour_waypoints(origin, destination)

        def fetch(wp: LatLng) -> list[Route]:
            try:
                return provider.get_routes(origin, destination, 1, via=[wp])
            except ProviderError as exc:
                errors.append(exc)
                return []

        with ThreadPoolExecutor(max_workers=len(waypoints)) as pool:
            results = list(pool.map(fetch, waypoints))
        shortest = min(r.distance_mi for r in routes)
        candidates = [
            r
            for batch in results
            for r in batch[:1]
            if r.distance_mi <= shortest * MAX_DETOUR_RATIO
        ]
        return self._add_distinct(routes, candidates)


def detour_waypoints(origin: LatLng, destination: LatLng) -> list[LatLng]:
    """Points offset perpendicular to the trip at its midpoint (alternating sides)."""
    mid_lat = (origin[0] + destination[0]) / 2
    kx = miles_per_deg_lng(mid_lat) or 1e-6
    ky = MILES_PER_DEG_LAT
    dx = (destination[1] - origin[1]) * kx
    dy = (destination[0] - origin[0]) * ky
    length = math.hypot(dx, dy)
    if length < 1:
        return []
    px, py = -dy / length, dx / length  # unit perpendicular (miles space)
    mid = ((origin[0] + destination[0]) / 2, (origin[1] + destination[1]) / 2)
    out = []
    for frac in DETOUR_OFFSETS:
        off = length * frac
        out.append((mid[0] + py * off / ky, mid[1] + px * off / kx))
    return out
