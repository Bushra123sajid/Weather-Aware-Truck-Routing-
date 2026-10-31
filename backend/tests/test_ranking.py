import pytest

from apps.planner.aggregation import RouteMetrics, compute_metrics, segment_miles
from apps.planner.ranking import build_explanation, compare_routes, rank_routes


def m(rid, *, nt=0.0, sev=0.0, high=0.0, avg=1.0, dur=600.0, unknown=0.0):
    return RouteMetrics(
        route_id=rid,
        name=f"Route {rid[-1]}",
        distance_mi=500,
        duration_min=dur,
        no_travel_miles=nt,
        severe_miles=sev,
        high_miles=high,
        avg_risk=avg,
        unknown_miles=unknown,
    )


def test_segment_miles_midpoint_attribution():
    assert segment_miles([0, 25, 50, 60], 60) == [12.5, 25, 17.5, 5]


def test_segment_miles_sum_to_total():
    miles = [0, 10, 20, 30, 37.3]
    assert sum(segment_miles(miles, 37.3)) == pytest.approx(37.3)


def test_segment_miles_edge_cases():
    assert segment_miles([], 10) == []
    assert segment_miles([0], 10) == [10]


def test_compute_metrics_weighted_average_and_worst():
    levels = [1, 4, 2, None]
    segs = [10, 20, 10, 5]
    met = compute_metrics("r1", "Route 1", 45, 60, levels, segs)
    assert met.low_miles == 10 and met.severe_miles == 20 and met.moderate_miles == 10
    assert met.unknown_miles == 5
    assert met.avg_risk == pytest.approx((10 * 1 + 20 * 4 + 10 * 2) / 40)
    assert met.max_risk == 4 and met.worst_index == 1


def test_compute_metrics_all_unknown():
    met = compute_metrics("r1", "Route 1", 10, 10, [None, None], [5, 5])
    assert met.avg_risk is None and met.unknown_miles == 10 and met.worst_index is None


def test_fewest_severe_wins_over_duration():
    a, b = m("r1", sev=18, dur=500), m("r2", sev=0, dur=600)
    assert [x.route_id for x in rank_routes([a, b])] == ["r2", "r1"]


def test_high_breaks_severe_tie():
    a, b = m("r1", sev=5, high=30), m("r2", sev=5, high=10)
    assert rank_routes([a, b])[0].route_id == "r2"


def test_avg_risk_breaks_high_tie():
    a, b = m("r1", high=10, avg=1.8), m("r2", high=10, avg=1.3)
    assert rank_routes([a, b])[0].route_id == "r2"


def test_duration_is_last_tiebreaker():
    a, b = m("r1", avg=1.2, dur=700), m("r2", avg=1.2, dur=650)
    assert compare_routes(b, a) == (-1, "duration")
    assert rank_routes([a, b])[0].route_id == "r2"


def test_tolerance_ignores_small_mile_differences():
    # 0.3 mi more Severe is within tolerance -> falls through to High miles.
    a, b = m("r1", sev=10.3, high=0), m("r2", sev=10.0, high=5)
    assert compare_routes(a, b) == (-1, "high")


def test_any_no_travel_ranks_last_even_if_otherwise_better():
    clean = m("r1", sev=100, high=100, avg=3.5, dur=900)
    nt = m("r2", nt=1, sev=0, high=0, avg=1.01, dur=300)
    assert [x.route_id for x in rank_routes([nt, clean])] == ["r1", "r2"]
    assert compare_routes(clean, nt)[1] == "any_no_travel"


def test_all_no_travel_ranked_by_no_travel_miles():
    a, b, c = m("r1", nt=40), m("r2", nt=5), m("r3", nt=20)
    assert [x.route_id for x in rank_routes([a, b, c])] == ["r2", "r3", "r1"]


def test_full_tie_keeps_provider_order():
    a, b = m("r1"), m("r2")
    assert [x.route_id for x in rank_routes([a, b])] == ["r1", "r2"]
    assert compare_routes(a, b) == (0, "tie")


def test_unknown_avg_risk_ranks_behind_known():
    a, b = m("r1", avg=None), m("r2", avg=2.5)
    assert rank_routes([a, b])[0].route_id == "r2"


def test_explanation_mentions_severe_and_time():
    best = m("r1", sev=0, dur=612)
    r2 = m("r2", sev=18, dur=600)
    r3 = m("r3", sev=0, high=7, dur=630)
    text = build_explanation(rank_routes([best, r2, r3]))
    assert text.startswith("Route 1 is recommended")
    assert "0 Severe miles vs 18 on Route 2" in text
    assert "0 High miles vs 7.0 on Route 3" in text
    assert "12 min slower than the fastest (Route 2)" in text


def test_explanation_fastest():
    text = build_explanation(rank_routes([m("r1", dur=500), m("r2", sev=3, dur=550)]))
    assert "also the fastest" in text


def test_explanation_all_no_travel_warns():
    text = build_explanation(rank_routes([m("r1", nt=10), m("r2", nt=30)]))
    assert text.startswith("WARNING: every route crosses No Travel")
    assert "10 No Travel miles vs 30 on Route 2" in text


def test_explanation_single_route_and_unknown_note():
    text = build_explanation([m("r1", unknown=12)])
    assert "only route available" in text
    assert "unavailable for 12 mi" in text
