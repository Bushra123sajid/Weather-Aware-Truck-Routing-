"""Routing provider that replays routes recorded from OSRM."""

from __future__ import annotations

import json
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from apps.common.geo import LatLng
from apps.routing.models import Route, route_from_segment_durations


@lru_cache(maxsize=4)
def load_route_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class RecordedRoutingProvider:
    """Returns the recorded routes regardless of the requested endpoints."""

    name = "recorded"

    def __init__(self, path: Path) -> None:
        self.path = path

    def get_routes(
        self,
        origin: LatLng,
        destination: LatLng,
        alternatives: int,
        via: Sequence[LatLng] = (),
    ) -> list[Route]:
        if via:
            return []
        data = load_route_fixture(self.path)
        return [
            route_from_segment_durations(
                [(lat, lng) for lat, lng in r["coordinates"]],
                r["segment_seconds"],
                distance_m=r["distance_m"],
                duration_s=r["duration_s"],
                provider=r["provider"],
                profile=r["profile"],
            )
            for r in data["routes"][:alternatives]
        ]
