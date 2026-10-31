"""GET /api/geocode?q=..."""

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .providers import GeocodingService


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=3, max_length=200, trim_whitespace=True)
    limit = serializers.IntegerField(min_value=1, max_value=10, default=5)


def get_geocoding_service() -> GeocodingService:
    """Factory, patched in tests."""
    return GeocodingService.from_settings()


class GeocodeView(APIView):
    throttle_scope = "geocode"

    def get(self, request: Request) -> Response:
        params = GeocodeQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        places = get_geocoding_service().search(
            params.validated_data["q"], params.validated_data["limit"]
        )
        return Response({"results": [p.as_dict() for p in places]})
