"""POST /api/heatmap"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.errors import PlanExpiredError
from apps.common.geo import decode_polyline
from apps.demo import services as demo
from apps.demo.scenarios import SCENARIOS, get_scenario
from apps.planner.service import plan_geometry_key

from .service import HeatmapService


class HeatmapRequestSerializer(serializers.Serializer):
    polylines = serializers.ListField(
        child=serializers.CharField(max_length=500_000), min_length=1, max_length=3, required=False
    )
    plan_id = serializers.CharField(max_length=64, required=False)
    route_ids = serializers.ListField(
        child=serializers.CharField(max_length=8), min_length=1, max_length=3, required=False
    )
    load_weight_lb = serializers.FloatField(min_value=0, max_value=200_000, default=0)
    start_time = serializers.DateTimeField(required=False)
    scenario = serializers.ChoiceField(
        choices=list(SCENARIOS), required=False, allow_null=True, default=None
    )

    def validate_polylines(self, value: list[str]) -> list[list[tuple[float, float]]]:
        decoded = []
        for s in value:
            try:
                coords = decode_polyline(s)
            except ValueError as exc:
                raise serializers.ValidationError("Invalid encoded polyline.") from exc
            if len(coords) < 2:
                raise serializers.ValidationError("Each polyline needs at least two points.")
            decoded.append(coords)
        return decoded

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if "polylines" in attrs:
            return attrs
        if "plan_id" in attrs and "route_ids" in attrs:
            return attrs
        raise serializers.ValidationError("Provide 'polylines', or 'plan_id' with 'route_ids'.")


def get_heatmap_service() -> HeatmapService:
    """Factory, patched in tests."""
    return HeatmapService.from_settings()


class HeatmapView(APIView):
    throttle_scope = "heatmap"

    def post(self, request: Request) -> Response:
        s = HeatmapRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data
        routes = v.get("polylines")
        if routes is None:
            # route_ids only work while the plan's geometry is cached (per-process with
            # LocMem); the frontend sends polylines so it never depends on this.
            stored = cache.get(plan_geometry_key(v["plan_id"]))
            if not stored:
                raise PlanExpiredError("Plan not found or expired; send 'polylines' instead.")
            try:
                routes = [decode_polyline(stored[rid]) for rid in v["route_ids"]]
            except KeyError as exc:
                raise PlanExpiredError(f"Unknown route id {exc.args[0]!r}.") from exc
        if v["scenario"] is None:
            result = get_heatmap_service().build(routes, v["load_weight_lb"], v.get("start_time"))
            return Response(result)

        scenario = get_scenario(v["scenario"])
        anchor = v.get("start_time") or timezone.now()
        result = demo.build_heatmap_service(scenario, anchor).build(
            routes, v["load_weight_lb"], v.get("start_time")
        )
        return Response({**result, **demo.demo_fields(scenario)})
