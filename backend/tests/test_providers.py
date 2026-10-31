"""Provider parsing with mocked HTTP (responses library)."""

from datetime import UTC, datetime

import pytest
import responses

from apps.common.errors import NoRouteError, ProviderError
from apps.common.geo import encode_polyline
from apps.routing.providers import OpenRouteServiceProvider, OSRMProvider
from apps.routing.service import RoutingService
from apps.weather.providers import OpenMeteoProvider, parse_location

from .conftest import FakeRoutingProvider, straight_route


def om_payload(lat=40.0, lng=-100.0, tz="America/Chicago", offset=-18000, snow_unit="inch"):
    return {
        "latitude": lat,
        "longitude": lng,
        "timezone": tz,
        "utc_offset_seconds": offset,
        "hourly_units": {
            "wind_speed_10m": "mp/h",
            "wind_gusts_10m": "mp/h",
            "rain": "inch",
            "snowfall": snow_unit,
            "precipitation": "inch",
        },
        "hourly": {
            "time": ["2026-11-01T00:00", "2026-11-01T01:00", "2026-11-01T02:00"],
            "wind_speed_10m": [10, 30, 50],
            "wind_gusts_10m": [15, 40, 65],
            "rain": [0, 0.2, None],
            "snowfall": [0, 2.54, 0],
            "precipitation": [0, 0.3, 0],
        },
    }


def test_parse_location_converts_times_to_utc():
    fc = parse_location(om_payload())
    # 2026-11-01 00:00 CDT (UTC-5) == 05:00 UTC
    assert fc.times_utc[0] == datetime(2026, 11, 1, 5, tzinfo=UTC)
    assert fc.wind_mph == [10, 30, 50]
    assert fc.rain_in_hr[2] is None


def test_snowfall_cm_converted_to_inches():
    fc = parse_location(om_payload(snow_unit="cm"))
    assert fc.snow_in_hr[1] == pytest.approx(1.0)
    fc2 = parse_location(om_payload(snow_unit="inch"))
    assert fc2.snow_in_hr[1] == pytest.approx(2.54)


def test_unexpected_unit_raises():
    with pytest.raises(ProviderError):
        parse_location(om_payload(snow_unit="furlongs"))


def test_nearest_hour_rounding_in_local_time():
    fc = parse_location(om_payload())
    # 05:29 UTC -> 00:29 local -> rounds to 00:00 local
    assert fc.sample_at(datetime(2026, 11, 1, 5, 29, tzinfo=UTC)).wind_mph == 10
    # 05:30 UTC -> 00:30 local -> rounds up to 01:00 local
    assert fc.sample_at(datetime(2026, 11, 1, 5, 30, tzinfo=UTC)).wind_mph == 30
    # Outside the series -> None
    assert fc.sample_at(datetime(2026, 11, 2, 5, tzinfo=UTC)) is None


def test_nearest_hour_half_hour_timezone():
    # India is UTC+5:30, so local hours fall on :30 UTC.
    p = om_payload(tz="Asia/Kolkata", offset=19800)
    fc = parse_location(p)
    assert fc.times_utc[0] == datetime(2026, 10, 31, 18, 30, tzinfo=UTC)
    # 18:50 UTC is 00:20 local -> 00:00 local -> index 0
    assert fc.index_for(datetime(2026, 10, 31, 18, 50, tzinfo=UTC)) == 0
    # 19:05 UTC is 00:35 local -> 01:00 local -> index 1
    assert fc.index_for(datetime(2026, 10, 31, 19, 5, tzinfo=UTC)) == 1


@responses.activate
def test_open_meteo_batches_and_degrades(settings):
    settings.HTTP_RETRIES = 0
    url = "https://api.open-meteo.com/v1/forecast"
    calls = {"n": 0}

    def callback(request):
        calls["n"] += 1
        lats = request.params["latitude"].split(",")
        if calls["n"] == 1:
            import json

            return 200, {}, json.dumps([om_payload(float(la)) for la in lats])
        return 503, {}, "busy"

    responses.add_callback(responses.GET, url, callback=callback)
    provider = OpenMeteoProvider()
    points = [(30 + i * 0.1, -100.0) for i in range(60)]  # 60 points -> 2 chunks of 50/10
    result = provider.fetch(points, timezone="auto", forecast_days=2)
    assert calls["n"] == 2
    assert sum(r is not None for r in result) in (50, 10)  # one chunk succeeds, other is None
    assert sum(r is None for r in result) in (10, 50)

    # Second call: successful chunk comes from cache, failed chunk is re-requested.
    before = calls["n"]
    provider.fetch(points, timezone="auto", forecast_days=2)
    assert calls["n"] == before + 1


@responses.activate
def test_open_meteo_request_params():
    responses.add(responses.GET, "https://api.open-meteo.com/v1/forecast", json=om_payload())
    OpenMeteoProvider().fetch([(40.0, -100.0)], timezone="auto", forecast_days=3)
    params = responses.calls[0].request.params
    assert params["hourly"] == "wind_speed_10m,wind_gusts_10m,rain,snowfall,precipitation"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["timezone"] == "auto"


def test_ors_parse_uses_step_durations():
    data = {
        "features": [
            {
                "geometry": {"coordinates": [[0, 0], [1, 0], [2, 0]]},
                "properties": {
                    "summary": {"distance": 222_000, "duration": 7200},
                    "segments": [
                        {
                            "steps": [
                                {"way_points": [0, 1], "duration": 1800},
                                {"way_points": [1, 2], "duration": 5400},
                                {"way_points": [2, 2], "duration": 0},
                            ]
                        }
                    ],
                },
            }
        ]
    }
    [r] = OpenRouteServiceProvider.parse(data)
    assert r.coords[1] == (0, 1)  # converted to (lat, lng)
    assert r.cum_seconds == pytest.approx([0, 1800, 7200])
    assert r.distance_mi == pytest.approx(222_000 / 1609.344)


def test_osrm_parse_uses_annotations():
    coords = [(0, 0), (0, 1), (0, 2)]
    data = {
        "code": "Ok",
        "routes": [
            {
                "geometry": encode_polyline(coords),
                "distance": 222_000,
                "duration": 3000,
                "legs": [{"annotation": {"duration": [1000, 2000]}, "duration": 3000}],
            }
        ],
    }
    [r] = OSRMProvider.parse(data)
    assert r.cum_seconds == pytest.approx([0, 1000, 3000])


def test_osrm_error_code():
    with pytest.raises(ProviderError):
        OSRMProvider.parse({"code": "NoRoute", "message": "Impossible route"})


def test_routing_service_tops_up_from_fallback_and_dedupes():
    a = straight_route((35, -100), (35, -97), provider="ors")
    dup = straight_route((35, -100), (35, -97), provider="osrm")
    b = straight_route((35, -100), (35.5, -97), provider="osrm")
    svc = RoutingService(FakeRoutingProvider([a], "ors"), FakeRoutingProvider([dup, b], "osrm"))
    result = svc.get_routes((35, -100), (35, -97))
    assert [r.provider for r in result.routes] == ["ors", "osrm"]
    assert any("Only 2 distinct" in n for n in result.notices)
    assert any("came from OSRM" in n for n in result.notices)


def test_routing_service_falls_back_when_primary_fails():
    class Failing:
        name = "ors"

        def get_routes(self, *a):
            raise ProviderError("down", provider="ors", upstream_status=500)

    routes = [straight_route((35, -100), (35 + i * 0.4, -97)) for i in range(3)]
    result = RoutingService(Failing(), FakeRoutingProvider(routes, "osrm")).get_routes(
        (35, -100), (35, -97)
    )
    assert len(result.routes) == 3
    assert any("unavailable" in n for n in result.notices)


def test_routing_service_no_routes():
    class Failing:
        name = "osrm"

        def get_routes(self, *a):
            raise ProviderError("down", provider="osrm")

    with pytest.raises(NoRouteError):
        RoutingService(None, Failing()).get_routes((35, -100), (35, -97))


def test_detour_waypoints_are_perpendicular_and_symmetric():
    from apps.common.geo import haversine_mi
    from apps.routing.service import detour_waypoints

    o, d = (35.0, -100.0), (35.0, -97.0)  # due east
    wps = detour_waypoints(o, d)
    assert len(wps) == 4
    north, south = wps[0], wps[1]
    assert north[1] == pytest.approx(-98.5) and south[1] == pytest.approx(-98.5)
    assert north[0] > 35 > south[0]
    trip = haversine_mi(o, d)
    assert haversine_mi((35.0, -98.5), north) == pytest.approx(trip * 0.15, rel=0.02)
    assert detour_waypoints(o, o) == []


def test_routing_service_generates_via_alternatives():
    main = straight_route((35, -100), (35, -97))
    detour = straight_route((35, -100), (35.4, -97))
    provider = FakeRoutingProvider([main], "osrm", via_route=detour)
    result = RoutingService(None, provider).get_routes((35, -100), (35, -97))
    # First waypoint yields a distinct route; the rest return the same detour (deduped).
    assert len(result.routes) == 2
    assert len(provider.via_calls) == 4
    assert any("detour waypoint" in n for n in result.notices)


def test_via_alternatives_reject_excessive_detours():
    main = straight_route((35, -100), (35, -97))
    huge = straight_route((35, -100), (40, -97))  # far longer than 1.5x
    provider = FakeRoutingProvider([main], "osrm", via_route=huge)
    result = RoutingService(None, provider).get_routes((35, -100), (35, -97))
    assert len(result.routes) == 1


def test_series_uses_fixed_offset_across_dst_change():
    # Open-Meteo keeps one utc_offset for the whole series; on 2026-11-01 (US DST ends)
    # local stamps continue 00:00, 01:00, 02:00 at -05:00 with no repeated hour.
    p = om_payload()
    p["hourly"]["time"] = ["2026-11-01T00:00", "2026-11-01T01:00", "2026-11-01T02:00"]
    fc = parse_location(p)
    assert fc.times_utc == [datetime(2026, 11, 1, h, tzinfo=UTC) for h in (5, 6, 7)]
    # An ETA of 07:08 UTC (01:08 CST, after the change) must still find the 07:00 UTC hour.
    assert fc.sample_at(datetime(2026, 11, 1, 7, 8, tzinfo=UTC)).wind_mph == 50
