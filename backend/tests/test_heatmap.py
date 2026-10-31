from datetime import UTC, datetime, timedelta

import pytest

from apps.common.geo import encode_polyline, haversine_mi, resample_along
from apps.heatmap import views as heatmap_views
from apps.heatmap.grid import build_corridor_grid
from apps.heatmap.service import HeatmapService, departure_index, forecast_hours

from .conftest import FakeWeather

LONG_ROUTE = [(41.88, -87.63), (39.10, -94.58), (39.74, -104.99)]  # Chicago-KC-Denver
SHORT_ROUTE = [(40.0, -100.0), (40.0, -99.5)]


@pytest.mark.parametrize("route", [LONG_ROUTE, SHORT_ROUTE])
def test_grid_respects_cap_and_corridor(route):
    grid = build_corridor_grid([route], max_points=250)
    assert 0 < len(grid.points) <= 250
    samples = resample_along(route, 2)
    for p in grid.points:
        assert min(haversine_mi(p, s) for s in samples) <= 25 + 3  # buffer + sampling error


def test_grid_min_spacing_for_short_routes():
    grid = build_corridor_grid([SHORT_ROUTE], max_points=1000)
    assert grid.spacing_mi >= 5


def test_grid_multiple_routes_and_empty():
    grid = build_corridor_grid([LONG_ROUTE, SHORT_ROUTE], max_points=150)
    assert len(grid.points) <= 150
    assert build_corridor_grid([]).points == []


def test_forecast_hours_and_departure_index():
    now = datetime(2026, 11, 1, 10, 42, tzinfo=UTC)
    hours = forecast_hours(now)
    assert len(hours) == 49
    assert hours[0] == datetime(2026, 11, 1, 10, tzinfo=UTC)
    assert departure_index(hours, now + timedelta(hours=5)) == 6  # 15:42 -> nearest 16:00
    assert departure_index(hours, hours[0] - timedelta(hours=2)) is None
    assert departure_index(hours, hours[0] + timedelta(hours=60)) is None
    assert departure_index(hours, None) is None


def test_heatmap_service_one_batched_fetch_and_cache():
    weather = FakeWeather(lambda p, t: (40.0, 0.0, 0.0))
    svc = HeatmapService(weather)
    out = svc.build([LONG_ROUTE], load_weight_lb=45_000)
    assert len(weather.calls) == 1
    assert weather.calls[0][1] == "GMT"
    assert len(out["hours"]) == 49
    p = out["points"][0]
    assert len(p["wind"]) == len(p["rain"]) == len(p["snow"]) == len(p["risk"]) == 49
    assert set(p["risk"]) == {4}  # 40 mph + 45,000 lb -> Severe via load rule
    svc.build([LONG_ROUTE], load_weight_lb=45_000)
    assert len(weather.calls) == 1  # served from cache


def test_heatmap_endpoint(client, monkeypatch):
    weather = FakeWeather(fail_if=lambda p: p[1] > -96)
    monkeypatch.setattr(heatmap_views, "get_heatmap_service", lambda: HeatmapService(weather))
    resp = client.post(
        "/api/heatmap",
        {
            "polylines": [encode_polyline(LONG_ROUTE)],
            "load_weight_lb": 20000,
            "start_time": (datetime.now(UTC) + timedelta(hours=3)).isoformat(),
        },
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["departure_index"] in (3, 4)
    assert body["warnings"] and "unavailable" in body["warnings"][0]
    assert body["spacing_mi"] > 0


def test_heatmap_endpoint_validation(client):
    resp = client.post("/api/heatmap", {"load_weight_lb": 1}, content_type="application/json")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"

    resp = client.post(
        "/api/heatmap", {"plan_id": "nope", "route_ids": ["r1"]}, content_type="application/json"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "plan_expired"
