"""POST /api/plan"""

from dataclasses import replace

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.demo import services as demo
from apps.demo.scenarios import get_scenario

from .serializers import PlanRequestSerializer
from .service import PlanInput, PlanService


def get_plan_service() -> PlanService:
    """Factory, patched in tests to inject fake providers."""
    return PlanService.from_settings()


class PlanView(APIView):
    throttle_scope = "plan"

    def post(self, request: Request) -> Response:
        serializer = PlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        plan_input = PlanInput(
            origin=v["origin"],
            destination=v["destination"],
            departure=v["departure_time"],
            load_weight_lb=v["load_weight_lb"],
            interval_miles=v["interval_miles"],
        )
        if v["scenario"] is None:
            return Response(get_plan_service().plan(plan_input))

        # Demo routes are recorded for fixed endpoints, so those replace the request's.
        scenario = get_scenario(v["scenario"])
        plan_input = replace(plan_input, origin=scenario.origin, destination=scenario.destination)
        result = demo.build_plan_service(scenario, plan_input.departure).plan(plan_input)
        return Response({**result, **demo.demo_fields(scenario)})
