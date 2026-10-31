"""Operational endpoints."""

from django.conf import settings
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness probe for the hosting platform."""

    throttle_classes: list = []

    def get(self, request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "routing_provider": "openrouteservice" if settings.ORS_API_KEY else "osrm",
            }
        )
