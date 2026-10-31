"""Plan orchestration: routes -> checkpoints -> ETAs -> weather -> risk -> ranking."""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from django.core.cache import cache

from apps.common.cache import make_key
from apps.common.geo import LatLng, encode_polyline
from apps.geocoding.providers import GeocodingService
from apps.risk.rules import assess
from apps.routing.models import Route
from apps.routing.sampling import SampledPoint, sample_checkpoints
from apps.routing.service import RoutingService
from apps.weather.models import LocationForecast
from apps.weather.providers import OpenMeteoProvider, WeatherProvider

from .aggregation import compute_metrics, segment_miles
from .ranking import build_explanation, rank_routes

logger = logging.getLogger(__name__)

PLAN_CACHE_TTL = 10 * 60
PLAN_GEOMETRY_TTL = 60 * 60
MAX_FORECAST_DAYS = 16  # Open-Meteo limit


@dataclass(frozen=True)
class PlanInput:
    origin: dict[str, Any]
    destination: dict[str, Any]
    departure: datetime
    load_weight_lb: float
    interval_miles: int


def _round(x: float | None, places: int = 2) -> float | None:
    return None if x is None else round(x, places)


def plan_geometry_key(plan_id: str) -> str:
    return f"plan-geom:{plan_id}"


class PlanService:
    def __init__(
        self,
        routing: RoutingService,
        weather: WeatherProvider,
        geocoding: GeocodingService | None = None,
        cache_namespace: str = "live",
    ) -> None:
        self.routing = routing
        self.weather = weather
        self.geocoding = geocoding
        self.cache_namespace = cache_namespace

    @classmethod
    def from_settings(cls) -> PlanService:
        return cls(
            routing=RoutingService.from_settings(),
            weather=OpenMeteoProvider(),
            geocoding=GeocodingService.from_settings(),
        )

    def _resolve(self, loc: dict[str, Any]) -> dict[str, Any]:
        if "lat" in loc:
            return loc
        if self.geocoding is None:
            raise ValueError("Free-text locations need a geocoding service")
        place = self.geocoding.resolve(loc["query"])
        return {"label": place.label, "lat": place.lat, "lng": place.lng}

    @staticmethod
    def _forecast_days(departure: datetime, routes: list[Route]) -> int:
        """Enough forecast days to cover the latest ETA (from today, local midnight slack)."""
        longest = max(r.cum_seconds[-1] for r in routes)
        hours_ahead = (departure - datetime.now(UTC)).total_seconds() / 3600 + longest / 3600
        return max(1, min(MAX_FORECAST_DAYS, math.ceil(max(0.0, hours_ahead) / 24) + 1))

    def plan(self, data: PlanInput) -> dict[str, Any]:
        origin = self._resolve(data.origin)
        destination = self._resolve(data.destination)
        cache_key = make_key(
            "plan",
            {
                "o": [round(origin["lat"], 4), round(origin["lng"], 4)],
                "d": [round(destination["lat"], 4), round(destination["lng"], 4)],
                "t": data.departure.astimezone(UTC).strftime("%Y%m%d%H%M"),
                "w": data.load_weight_lb,
                "i": data.interval_miles,
                "n": self.cache_namespace,
            },
        )
        if (cached := cache.get(cache_key)) is not None:
            return cached

        o: LatLng = (origin["lat"], origin["lng"])
        d: LatLng = (destination["lat"], destination["lng"])
        routing = self.routing.get_routes(o, d)
        routes = routing.routes

        samples: list[list[SampledPoint]] = [
            sample_checkpoints(r, data.interval_miles) for r in routes
        ]
        flat = [p.latlng for pts in samples for p in pts]
        forecasts = self.weather.fetch(
            flat, timezone="auto", forecast_days=self._forecast_days(data.departure, routes)
        )

        warnings: list[str] = []
        route_payloads: list[dict[str, Any]] = []
        metrics_list = []
        cursor = 0
        unknown_total = 0
        for idx, (route, pts) in enumerate(zip(routes, samples, strict=True)):
            route_id = f"r{idx + 1}"
            name = f"Route {idx + 1}"
            segs = segment_miles([p.mile for p in pts], route.cum_miles[-1])
            checkpoints = []
            levels: list[int | None] = []
            for i, (p, seg) in enumerate(zip(pts, segs, strict=True)):
                fc: LocationForecast | None = forecasts[cursor]
                cursor += 1
                checkpoints.append(
                    self._checkpoint(i, p, seg, data.departure, fc, data.load_weight_lb)
                )
                levels.append(checkpoints[-1]["risk"])
            unknown_total += sum(1 for lv in levels if lv is None)
            metrics = compute_metrics(
                route_id, name, route.distance_mi, route.duration_min, levels, segs
            )
            metrics_list.append(metrics)
            route_payloads.append(
                {
                    "id": route_id,
                    "name": name,
                    "provider": route.provider,
                    "profile": route.profile,
                    "geometry": encode_polyline(route.coords),
                    "distance_mi": round(route.distance_mi, 1),
                    "duration_min": round(route.duration_min, 1),
                    "arrival_time": (pts[-1].eta(data.departure).astimezone(UTC).isoformat()),
                    "checkpoints": checkpoints,
                }
            )

        if unknown_total:
            warnings.append(
                f"Weather data was unavailable for {unknown_total} checkpoint(s); they are marked "
                "'Unknown' and excluded from the average risk."
            )

        ranked = rank_routes(metrics_list)
        rank_of = {m.route_id: i + 1 for i, m in enumerate(ranked)}
        by_id = {m.route_id: m for m in metrics_list}
        for payload in route_payloads:
            m = by_id[payload["id"]]
            worst = payload["checkpoints"][m.worst_index] if m.worst_index is not None else None
            payload["metrics"] = {
                **m.as_dict(),
                "worst_checkpoint": (
                    {k: worst[k] for k in ("index", "mile", "eta", "risk", "risk_label", "driver")}
                    if worst
                    else None
                ),
            }
            payload["rank"] = rank_of[payload["id"]]
            payload["recommended"] = payload["rank"] == 1

        plan_id = uuid.uuid4().hex
        cache.set(
            plan_geometry_key(plan_id),
            {p["id"]: p["geometry"] for p in route_payloads},
            PLAN_GEOMETRY_TTL,
        )
        result = {
            "plan_id": plan_id,
            "origin": origin,
            "destination": destination,
            "departure_time": data.departure.astimezone(UTC).isoformat(),
            "load_weight_lb": data.load_weight_lb,
            "interval_miles": data.interval_miles,
            "routes": route_payloads,
            "recommended_route_id": ranked[0].route_id,
            "ranking": [m.route_id for m in ranked],
            "explanation": build_explanation(ranked),
            "all_routes_no_travel": all(m.no_travel_miles > 0 for m in metrics_list),
            "notices": routing.notices,
            "warnings": warnings,
        }
        cache.set(cache_key, result, PLAN_CACHE_TTL)
        return result

    @staticmethod
    def _checkpoint(
        index: int,
        p: SampledPoint,
        seg_mi: float,
        departure: datetime,
        fc: LocationForecast | None,
        load_lb: float,
    ) -> dict[str, Any]:
        eta = p.eta(departure)
        sample = fc.sample_at(eta) if fc else None
        base: dict[str, Any] = {
            "index": index,
            "lat": round(p.lat, 5),
            "lng": round(p.lng, 5),
            "mile": round(p.mile, 1),
            "segment_miles": round(seg_mi, 2),
            "eta": eta.astimezone(UTC).isoformat(),
            "timezone": fc.timezone if fc else None,
            "forecast_hour": sample.time.isoformat() if sample else None,
            "wind_mph": _round(sample.wind_mph if sample else None, 1),
            "gust_mph": _round(sample.gust_mph if sample else None, 1),
            "rain_in_hr": _round(sample.rain_in_hr if sample else None, 3),
            "snow_in_hr": _round(sample.snow_in_hr if sample else None, 3),
        }
        assessment = (
            assess(sample.wind_mph, sample.rain_in_hr, sample.snow_in_hr, load_lb)
            if sample
            else None
        )
        if assessment is None:
            base.update(
                risk=None,
                risk_label="Unknown",
                driver="unknown",
                load_adjusted=False,
                factor_levels=None,
            )
        else:
            base.update(assessment.as_dict())
        return base
