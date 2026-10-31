"""Planner and heatmap services wired to a demo scenario."""

from __future__ import annotations

from datetime import datetime

from apps.heatmap.service import HeatmapService
from apps.planner.service import PlanService
from apps.routing.service import RoutingService

from .routing import RecordedRoutingProvider
from .scenarios import Scenario
from .weather import StormWeatherProvider


def demo_fields(scenario: Scenario) -> dict:
    return {"demo": True, "scenario": scenario.key, "scenario_note": scenario.note}


def build_plan_service(scenario: Scenario, departure: datetime) -> PlanService:
    return PlanService(
        routing=RoutingService(primary=RecordedRoutingProvider(scenario.routes_file)),
        weather=StormWeatherProvider(scenario.cells, departure),
        cache_namespace=f"demo:{scenario.key}",
    )


def build_heatmap_service(scenario: Scenario, anchor: datetime) -> HeatmapService:
    return HeatmapService(
        StormWeatherProvider(scenario.cells, anchor),
        cache_namespace=f"demo:{scenario.key}:{anchor.isoformat()}",
    )
