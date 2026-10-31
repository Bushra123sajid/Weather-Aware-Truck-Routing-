"""Integration tests for /api/plan and /api/geocode with fake providers."""

from datetime import UTC, datetime, timedelta

import pytest

from apps.geocoding import views as geocode_views
from apps.geocoding.providers import GeocodingService, Place
from apps.heatmap import views as heatmap_views
from apps.heatmap.service import HeatmapService
from apps.planner import views as plan_views
from apps.planner.service import PlanService
from apps.routing.service import RoutingService

from .conftest import FakeRoutingProvider, FakeWeather, straight_route

ORIGIN = {"label": "A", "lat": 35.0, "lng": -100.0}
DEST = {"label": "B", "lat": 35.0, "lng": -97.0}


def three_routes():
    # r1 straight & fastest; r2 north detour; r3 south detour (slower).
    return [
        straight_route((35, -100), (35, -97), mph=60),
        straight_route((35, -100), (35.6, -97), mph=58),
        straight_route((35, -100), (34.4, -97), mph=50),
    ]


class FakeGeocoder:
    name = "fake"

    def search(self, query, limit):
        return [
            Place(label=f"{query.title()}, USA", lat=35.0, lng=-100.0 if "a" in query else -97.0)
        ]


def install(monkeypatch, routes, weather, primary_name="ors"):
    svc = PlanService(
        routing=RoutingService(FakeRoutingProvider(routes, primary_name), None),
        weather=weather,
        geocoding=GeocodingService(FakeGeocoder()),
    )
    monkeypatch.setattr(plan_views, "get_plan_service", lambda: svc)
    return svc


def body(**overrides):
    b = {
        "origin": ORIGIN,
        "destination": DEST,
        "departure_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "load_weight_lb": 35000,
        "interval_miles": 25,
    }
    b.update(overrides)
    return b


def post(client, payload):
    return client.post("/api/plan", payload, content_type="application/json")


def test_plan_happy_path_shape(client, monkeypatch):
    weather = FakeWeather()
    install(monkeypatch, three_routes(), weather)
    resp = post(client, body())
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert len(data["routes"]) == 3
    assert data["recommended_route_id"] == "r1"  # all Low -> fastest wins
    assert "fastest" in data["explanation"]
    assert len(weather.calls) == 1  # one batched weather call for all checkpoints
    r = data["routes"][0]
    assert {
        "id",
        "geometry",
        "distance_mi",
        "duration_min",
        "checkpoints",
        "metrics",
        "rank",
    } <= r.keys()
    cps = r["checkpoints"]
    assert cps[0]["mile"] == 0 and cps[-1]["mile"] == pytest.approx(r["distance_mi"], abs=0.1)
    assert all(cps[i + 1]["mile"] - cps[i]["mile"] <= 25.01 for i in range(len(cps) - 1))
    cp = cps[1]
    for key in (
        "lat",
        "lng",
        "mile",
        "eta",
        "wind_mph",
        "rain_in_hr",
        "snow_in_hr",
        "risk",
        "driver",
    ):
        assert key in cp
    assert sum(c["segment_miles"] for c in cps) == pytest.approx(r["distance_mi"], abs=0.2)
    assert sorted(x["rank"] for x in data["routes"]) == [1, 2, 3]


def test_plan_recommends_route_avoiding_severe(client, monkeypatch):
    # Severe wind band north of latitude 35.1, only for heavy loads (40 mph + >40,000 lb => Severe).
    weather = FakeWeather(lambda p, t: (40.0 if p[0] > 35.1 else 10.0, 0.0, 0.0))
    install(monkeypatch, three_routes(), weather)
    data = post(client, body(load_weight_lb=45000)).json()
    by_id = {r["id"]: r for r in data["routes"]}
    assert by_id["r2"]["metrics"]["severe_miles"] > 0
    assert by_id["r2"]["rank"] == 3
    severe_cp = next(c for c in by_id["r2"]["checkpoints"] if c["risk"] == 4)
    assert severe_cp["driver"] == "wind" and severe_cp["load_adjusted"] is True
    assert "Severe miles vs" in data["explanation"]


def test_plan_light_load_same_wind_is_only_high(client, monkeypatch):
    weather = FakeWeather(lambda p, t: (40.0 if p[0] > 35.1 else 10.0, 0.0, 0.0))
    install(monkeypatch, three_routes(), weather)
    data = post(client, body(load_weight_lb=10000)).json()
    r2 = next(r for r in data["routes"] if r["id"] == "r2")
    assert r2["metrics"]["severe_miles"] == 0 and r2["metrics"]["high_miles"] > 0


def test_plan_all_routes_no_travel(client, monkeypatch):
    install(monkeypatch, three_routes(), FakeWeather(lambda p, t: (60.0, 0, 0)))
    data = post(client, body()).json()
    assert data["all_routes_no_travel"] is True
    assert data["explanation"].startswith("WARNING")
    assert len(data["routes"]) == 3


def test_plan_partial_weather_failure_marks_unknown(client, monkeypatch):
    install(monkeypatch, three_routes(), FakeWeather(fail_if=lambda p: p[1] > -98))
    resp = post(client, body())
    assert resp.status_code == 200
    data = resp.json()
    assert data["warnings"] and "unavailable" in data["warnings"][0]
    unknown = [c for r in data["routes"] for c in r["checkpoints"] if c["risk"] is None]
    assert unknown and all(c["risk_label"] == "Unknown" for c in unknown)
    assert data["routes"][0]["metrics"]["unknown_miles"] > 0


def test_plan_fewer_than_three_routes_notice(client, monkeypatch):
    install(monkeypatch, three_routes()[:1], FakeWeather())
    data = post(client, body()).json()
    assert len(data["routes"]) == 1
    assert any("Only 1 distinct" in n for n in data["notices"])


def test_plan_free_text_locations_are_geocoded(client, monkeypatch):
    install(monkeypatch, three_routes(), FakeWeather())
    resp = post(client, body(origin="amarillo", destination="oklahoma city"))
    assert resp.status_code == 200, resp.content
    assert resp.json()["origin"]["label"] == "Amarillo, USA"


@pytest.mark.parametrize("interval", [10, 50])
def test_plan_interval_option(client, monkeypatch, interval):
    install(monkeypatch, three_routes(), FakeWeather())
    data = post(client, body(interval_miles=interval)).json()
    cps = data["routes"][0]["checkpoints"]
    assert cps[1]["mile"] == pytest.approx(interval, abs=0.1)


@pytest.mark.parametrize(
    "overrides,fragment",
    [
        ({"departure_time": (datetime.now(UTC) - timedelta(hours=2)).isoformat()}, "past"),
        ({"departure_time": (datetime.now(UTC) + timedelta(hours=49)).isoformat()}, "48 hours"),
        ({"interval_miles": 30}, "interval_miles"),
        ({"load_weight_lb": -5}, "load_weight_lb"),
        ({"origin": {"lat": 200, "lng": 0}}, "Latitude"),
        ({"destination": ORIGIN}, "different"),
    ],
)
def test_plan_validation_errors(client, monkeypatch, overrides, fragment):
    install(monkeypatch, three_routes(), FakeWeather())
    resp = post(client, body(**overrides))
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    assert fragment in err["message"]


def test_plan_no_route_error_format(client, monkeypatch):
    install(monkeypatch, [], FakeWeather())
    resp = post(client, body())
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "no_route"


def test_heatmap_by_plan_id(client, monkeypatch):
    install(monkeypatch, three_routes(), FakeWeather())
    plan = post(client, body()).json()
    monkeypatch.setattr(heatmap_views, "get_heatmap_service", lambda: HeatmapService(FakeWeather()))
    resp = client.post(
        "/api/heatmap",
        {"plan_id": plan["plan_id"], "route_ids": ["r1", "r2"], "load_weight_lb": 0},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["points"]


def test_geocode_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        geocode_views, "get_geocoding_service", lambda: GeocodingService(FakeGeocoder())
    )
    resp = client.get("/api/geocode", {"q": "dallas"})
    assert resp.status_code == 200
    assert resp.json()["results"][0]["label"] == "Dallas, USA"
    assert client.get("/api/geocode", {"q": "d"}).status_code == 400


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"
