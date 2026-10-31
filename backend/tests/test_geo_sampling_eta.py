from datetime import UTC, datetime, timedelta

import pytest

from apps.common.geo import (
    cumulative_miles,
    decode_polyline,
    encode_polyline,
    haversine_mi,
    resample_along,
)
from apps.routing.models import route_from_segment_durations, route_from_steps
from apps.routing.sampling import checkpoint_miles, position_at_mile, sample_checkpoints
from apps.routing.timing import build_time_profile

from .conftest import straight_route


def test_polyline_roundtrip_google_example():
    # Canonical example from Google's polyline docs.
    encoded = "_p~iF~ps|U_ulLnnqC_mqNvxq`@"
    coords = decode_polyline(encoded)
    assert coords == [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
    assert encode_polyline(coords) == encoded


def test_decode_malformed_raises():
    with pytest.raises(ValueError):
        decode_polyline("_p~iF~ps|U_")


def test_haversine_known_distance():
    # One degree of latitude is about 69 miles
    assert haversine_mi((0, 0), (1, 0)) == pytest.approx(69.09, abs=0.1)


def test_resample_includes_both_ends():
    pts = resample_along([(0, 0), (1, 0)], 10)
    assert pts[0] == (0, 0) and pts[-1] == (1, 0)
    assert len(pts) == 8  # 0,10,...,60 + end (~69 mi)


def test_checkpoint_miles_includes_origin_and_destination():
    assert checkpoint_miles(60, 25) == [0, 25, 50, 60]


def test_checkpoint_miles_no_duplicate_when_exact_multiple():
    assert checkpoint_miles(50, 25) == [0, 25, 50]
    assert checkpoint_miles(50.01, 25) == [0, 25, 50.01]


def test_checkpoint_miles_short_route():
    assert checkpoint_miles(7, 10) == [0, 7]


def test_checkpoint_miles_bad_interval():
    with pytest.raises(ValueError):
        checkpoint_miles(10, 0)


@pytest.mark.parametrize("interval", [10, 25, 50])
def test_sample_checkpoints_spacing(interval):
    route = straight_route((35.0, -100.0), (35.0, -97.0), n=200)  # ~170 mi
    pts = sample_checkpoints(route, interval)
    assert pts[0].mile == 0
    assert (pts[0].lat, pts[0].lng) == pytest.approx(route.coords[0])
    assert pts[-1].mile == pytest.approx(route.distance_mi)
    assert (pts[-1].lat, pts[-1].lng) == pytest.approx(route.coords[-1])
    for a, b in zip(pts[:-2], pts[1:-1], strict=True):
        assert b.mile - a.mile == pytest.approx(interval)
    # Interpolated points lie on the line and their geometric spacing matches the mile markers.
    assert haversine_mi(pts[0].latlng, pts[1].latlng) == pytest.approx(interval, rel=0.01)


def test_position_interpolates_between_vertices():
    route = route_from_segment_durations(
        [(0, 0), (0, 1)], [3600], distance_m=0, duration_s=0, provider="t", profile="t"
    )
    mid = position_at_mile(route, route.distance_mi / 2)
    assert mid.lng == pytest.approx(0.5)
    assert mid.elapsed_s == pytest.approx(1800)


def test_route_scaled_to_provider_distance_and_duration():
    coords = [(0, 0), (0, 1)]
    geo_mi = cumulative_miles(coords)[-1]
    r = route_from_segment_durations(
        coords, [100], distance_m=geo_mi * 1.1 * 1609.344, duration_s=200, provider="t", profile="t"
    )
    assert r.cum_miles[-1] == pytest.approx(geo_mi * 1.1)
    assert r.cum_seconds[-1] == pytest.approx(200)


def test_time_profile_distributes_steps_by_length():
    # Three equal segments; step A covers the first one in 600 s, step B the other two in 600 s.
    coords = [(0, 0), (0, 0.1), (0, 0.2), (0, 0.3)]
    cum = build_time_profile(coords, [(0, 1, 600), (1, 3, 600)])
    assert cum == pytest.approx([0, 600, 900, 1200])


def test_time_profile_zero_length_step_goes_to_previous_segment():
    coords = [(0, 0), (0, 0.1), (0, 0.2)]
    cum = build_time_profile(coords, [(0, 2, 100), (2, 2, 30)])
    assert cum[-1] == pytest.approx(130)


def test_eta_uses_step_durations_not_flat_speed():
    # First half: highway (fast), second half: city (slow). Total 2 h for ~138 mi.
    coords = [(0, 0), (0, 1), (0, 2)]
    route = route_from_steps(
        coords, [(0, 1, 1800), (1, 2, 5400)], distance_m=0, duration_s=0, provider="t", profile="t"
    )
    dep = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    half = route.distance_mi / 2
    p_half = position_at_mile(route, half)
    assert p_half.eta(dep) == dep + timedelta(minutes=30)
    # Three quarters along: 30 min + half of the 90 min slow step.
    p_3q = position_at_mile(route, route.distance_mi * 0.75)
    assert p_3q.eta(dep) == dep + timedelta(minutes=75)
    end = sample_checkpoints(route, 1000)[-1]
    assert end.eta(dep) == dep + timedelta(hours=2)


def test_checkpoint_etas_monotonic():
    route = straight_route((40, -105), (40, -100), n=100, mph=55)
    dep = datetime(2026, 5, 1, 12, tzinfo=UTC)
    etas = [p.eta(dep) for p in sample_checkpoints(route, 10)]
    assert etas == sorted(etas)
    assert (etas[-1] - dep).total_seconds() == pytest.approx(route.duration_s)
