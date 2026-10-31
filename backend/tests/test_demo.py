"""Demo scenario: storm model, recorded routes and the scenario field on the API."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.common.geo import encode_polyline, haversine_mi
from apps.demo.routing import RecordedRoutingProvider
from apps.demo.scenarios import WINTER_STORM
from apps.demo.storm import BACKGROUND_WIND_MPH, StormCell, conditions_at
from apps.demo.weather import StormWeatherProvider
from apps.planner import views as plan_views

from .conftest import FakeRoutingProvider, FakeWeather, straight_route

CELL = StormCell(
    name="test",
    lat=40.0,
    lng=-100.0,
    core_radius_mi=10,
    radius_mi=50,
    peak_wind_mph=48,
    peak_rain_in_hr=0.4,
    peak_snow_in_hr=2.0,
    drift_mph=20,
)


def departure() -> datetime:
    return datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=3)


def test_conditions_are_deterministic():
    p = (40.1, -99.8)
    assert conditions_at((CELL,), p, 3.5) == conditions_at((CELL,), p, 3.5)


def test_core_is_full_strength_and_outside_is_background():
    core = conditions_at((CELL,), (40.0, -100.0), 0)
    assert (core.wind_mph, core.rain_in_hr, core.snow_in_hr) == (48, 0.4, 2.0)
    far = conditions_at((CELL,), (45.0, -100.0), 0)
    assert (far.wind_mph, far.rain_in_hr, far.snow_in_hr) == (BACKGROUND_WIND_MPH, 0, 0)


def test_falloff_is_linear_between_core_and_radius():
    # 30 mi north is halfway between the 10 mi core and the 50 mi radius.
    point = (40.0 + 30 / 69.055, -100.0)
    assert haversine_mi(point, (40.0, -100.0)) == pytest.approx(30, abs=0.1)
    c = conditions_at((CELL,), point, 0)
    assert c.snow_in_hr == pytest.approx(1.0, abs=0.01)
    assert c.wind_mph == pytest.approx(
        BACKGROUND_WIND_MPH + (48 - BACKGROUND_WIND_MPH) / 2, abs=0.2
    )


def test_cell_drifts_east_at_its_speed():
    center = CELL.center_at(3)
    assert center[0] == CELL.lat
    assert center[1] > CELL.lng
    assert haversine_mi(center, (CELL.lat, CELL.lng)) == pytest.approx(60, rel=0.01)
    # Three hours later the old center is outside the 50 mi radius.
    assert conditions_at((CELL,), (40.0, -100.0), 3).snow_in_hr == 0


def test_weather_provider_covers_heatmap_range():
    dep = departure()
    [fc] = StormWeatherProvider(WINTER_STORM.cells, dep).fetch([(40.8, -99.0)])
    assert fc.times_utc[0] <= dep - timedelta(hours=48)
    assert fc.times_utc[-1] >= dep + timedelta(hours=48)
    assert fc.timezone == "America/Chicago"


def test_recorded_routes_fixture():
    routes = RecordedRoutingProvider(WINTER_STORM.routes_file).get_routes(None, None, 3)
    assert len(routes) == 3
    durations = [r.duration_min for r in routes]
    assert durations[0] == min(durations)


def plan(client, load=45_000, scenario="winter_storm"):
    body = {
        "origin": WINTER_STORM.origin,
        "destination": WINTER_STORM.destination,
        "departure_time": departure().isoformat(),
        "load_weight_lb": load,
        "interval_miles": 25,
        "scenario": scenario,
    }
    resp = client.post("/api/plan", body, content_type="application/json")
    assert resp.status_code == 200, resp.content
    return resp.json()


def fastest(data):
    return min(data["routes"], key=lambda r: r["duration_min"])


def test_winter_storm_plan_outcomes(client):
    data = plan(client)
    assert data["demo"] is True
    assert data["scenario"] == "winter_storm"
    assert data["scenario_note"]
    fast = fastest(data)
    assert fast["metrics"]["severe_miles"] > 0
    assert fast["metrics"]["no_travel_miles"] > 0
    rec = next(r for r in data["routes"] if r["id"] == data["recommended_route_id"])
    assert rec["id"] != fast["id"]
    assert rec["metrics"]["no_travel_miles"] == 0
    assert data["explanation"]


def test_lighter_load_reduces_no_travel_on_fastest_route(client):
    heavy = fastest(plan(client, load=45_000))["metrics"]["no_travel_miles"]
    light = fastest(plan(client, load=20_000))["metrics"]["no_travel_miles"]
    assert light < heavy


def test_null_scenario_uses_live_provider_path(client, monkeypatch):
    calls = []

    def factory():
        from apps.planner.service import PlanService
        from apps.routing.service import RoutingService

        calls.append(1)
        routes = [straight_route((39.74, -104.99), (41.88, -87.63))]
        return PlanService(RoutingService(FakeRoutingProvider(routes)), FakeWeather())

    monkeypatch.setattr(plan_views, "get_plan_service", factory)
    data = plan(client, scenario=None)
    assert calls == [1]
    assert "demo" not in data and "scenario_note" not in data


def test_unknown_scenario_rejected(client):
    resp = client.post(
        "/api/plan",
        {
            "origin": WINTER_STORM.origin,
            "destination": WINTER_STORM.destination,
            "departure_time": departure().isoformat(),
            "load_weight_lb": 1,
            "scenario": "hurricane",
        },
        content_type="application/json",
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_winter_storm_heatmap_moves(client):
    data = plan(client)
    resp = client.post(
        "/api/heatmap",
        {
            "polylines": [r["geometry"] for r in data["routes"]],
            "load_weight_lb": 45_000,
            "start_time": data["departure_time"],
            "scenario": "winter_storm",
        },
        content_type="application/json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["demo"] is True and body["departure_index"] in (2, 3, 4)
    snow = [p["snow"] for p in body["points"]]
    # The snowiest grid point changes over time as the storm drifts.
    peak_at = {max(range(len(snow)), key=lambda i, h=h: snow[i][h]) for h in (0, 12, 24)}
    assert len(peak_at) > 1


def test_demo_heatmap_cache_is_separate_from_live(client):
    polyline = encode_polyline([(40.0, -100.0), (40.0, -99.0)])
    resp = client.post(
        "/api/heatmap",
        {"polylines": [polyline], "scenario": "winter_storm"},
        content_type="application/json",
    )
    assert resp.status_code == 200 and resp.json()["demo"] is True
