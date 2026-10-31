"""Request validation for POST /api/plan."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from apps.demo.scenarios import SCENARIOS

MAX_DEPARTURE_AHEAD = timedelta(hours=48)
# Allow a small grace period so a "now" picked a few minutes ago isn't rejected.
PAST_GRACE = timedelta(minutes=15)
INTERVAL_CHOICES = (10, 25, 50)


def validate_departure_window(value: datetime, now: datetime | None = None) -> datetime:
    """Departure must fall between now (minus a short grace) and now + 48 h, the heatmap range."""
    now = now or timezone.now()
    if timezone.is_naive(value):
        value = value.replace(tzinfo=UTC)  # documented: naive times are treated as UTC
    if value < now - PAST_GRACE:
        raise serializers.ValidationError("Departure time is in the past. Pick a time from now on.")
    if value > now + MAX_DEPARTURE_AHEAD:
        raise serializers.ValidationError(
            "Departure time is more than 48 hours ahead; forecasts are only shown for the next 48 hours."
        )
    return value


class LocationField(serializers.Field):
    """Accepts free text (geocoded server-side) or ``{"label", "lat", "lng"}``."""

    default_error_messages = {
        "invalid": "Provide a place name or an object with lat and lng.",
        "range": "Latitude must be between -90 and 90 and longitude between -180 and 180.",
    }

    def to_internal_value(self, data: Any) -> dict[str, Any]:
        if isinstance(data, str):
            text = data.strip()
            if len(text) < 2:
                self.fail("invalid")
            return {"query": text}
        if isinstance(data, dict):
            try:
                lat, lng = float(data["lat"]), float(data["lng"])
            except (KeyError, TypeError, ValueError):
                self.fail("invalid")
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                self.fail("range")
            label = str(data.get("label") or f"{lat:.4f}, {lng:.4f}")[:300]
            return {"lat": lat, "lng": lng, "label": label}
        self.fail("invalid")

    def to_representation(self, value: Any) -> Any:
        return value


class PlanRequestSerializer(serializers.Serializer):
    origin = LocationField()
    destination = LocationField()
    departure_time = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=0, max_value=200_000)
    interval_miles = serializers.ChoiceField(choices=INTERVAL_CHOICES, default=25)
    scenario = serializers.ChoiceField(
        choices=list(SCENARIOS), required=False, allow_null=True, default=None
    )

    def validate_departure_time(self, value: datetime) -> datetime:
        return validate_departure_window(value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        o, d = attrs["origin"], attrs["destination"]
        if (
            "lat" in o
            and "lat" in d
            and abs(o["lat"] - d["lat"]) < 1e-4
            and abs(o["lng"] - d["lng"]) < 1e-4
        ):
            raise serializers.ValidationError("Origin and destination must be different.")
        if "query" in o and "query" in d and o["query"].lower() == d["query"].lower():
            raise serializers.ValidationError("Origin and destination must be different.")
        attrs["interval_miles"] = int(attrs["interval_miles"])
        return attrs
