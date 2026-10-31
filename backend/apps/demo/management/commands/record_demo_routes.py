"""Record the demo trip's routes from the live routing provider into a fixture."""

from __future__ import annotations

import json
from datetime import date

from django.core.management.base import BaseCommand

from apps.demo.scenarios import get_scenario
from apps.routing.models import Route
from apps.routing.providers import OSRMProvider
from apps.routing.service import RoutingService

MIN_VERTEX_SPACING_MI = 0.2


def simplify(route: Route) -> tuple[list, list[float]]:
    """Drop vertices closer than MIN_VERTEX_SPACING_MI, summing the dropped segments' time."""
    coords = [route.coords[0]]
    seconds: list[float] = []
    last = 0
    for i in range(1, len(route.coords)):
        is_last = i == len(route.coords) - 1
        if is_last or route.cum_miles[i] - route.cum_miles[last] >= MIN_VERTEX_SPACING_MI:
            coords.append(route.coords[i])
            seconds.append(round(route.cum_seconds[i] - route.cum_seconds[last], 1))
            last = i
    return coords, seconds


class Command(BaseCommand):
    help = "Fetch routes for a demo scenario from OSRM and save them as a fixture."

    def add_arguments(self, parser):
        parser.add_argument("--scenario", default="winter_storm")

    def handle(self, *args, **options):
        scenario = get_scenario(options["scenario"])
        o, d = scenario.origin, scenario.destination
        result = RoutingService(primary=None, fallback=OSRMProvider())._fetch(
            (o["lat"], o["lng"]), (d["lat"], d["lng"])
        )
        routes = []
        for route in result.routes:
            coords, seconds = simplify(route)
            routes.append(
                {
                    "provider": "osrm-recorded",
                    "profile": route.profile,
                    "distance_m": round(route.distance_mi * 1609.344),
                    "duration_s": round(route.duration_s),
                    "coordinates": [[round(lat, 5), round(lng, 5)] for lat, lng in coords],
                    "segment_seconds": seconds,
                }
            )
            self.stdout.write(
                f"{route.distance_mi:7.1f} mi  {route.duration_min:6.0f} min  {len(coords)} vertices"
            )
        payload = {
            "recorded_on": date.today().isoformat(),
            "source": "OSRM public server, car profile",
            "origin": o,
            "destination": d,
            "routes": routes,
        }
        scenario.routes_file.write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8"
        )
        self.stdout.write(f"Wrote {scenario.routes_file}")
