"""Route ranking and the recommendation text.

Order: any No Travel ranks last (then fewer No Travel miles), fewest Severe miles,
fewest High miles, lowest average risk, shortest duration. Miles compare with a 0.5 mi
tolerance so sampling noise between routes does not decide the winner.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from functools import cmp_to_key
from typing import Literal

from .aggregation import RouteMetrics

MILES_TOLERANCE = 0.5
AVG_RISK_TOLERANCE = 0.01
DURATION_TOLERANCE_MIN = 0.5

Criterion = Literal["any_no_travel", "no_travel", "severe", "high", "avg_risk", "duration", "tie"]


def _cmp(a: float, b: float, tol: float) -> int:
    if abs(a - b) <= tol:
        return 0
    return -1 if a < b else 1


def _avg(m: RouteMetrics) -> float:
    return m.avg_risk if m.avg_risk is not None else math.inf


def compare_routes(a: RouteMetrics, b: RouteMetrics) -> tuple[int, Criterion]:
    """Return (-1|0|1, deciding criterion). Negative means ``a`` ranks ahead of ``b``."""
    a_nt, b_nt = a.no_travel_miles > 0, b.no_travel_miles > 0
    if a_nt != b_nt:
        return (1 if a_nt else -1), "any_no_travel"
    checks: list[tuple[Criterion, float, float, float]] = [
        ("no_travel", a.no_travel_miles, b.no_travel_miles, MILES_TOLERANCE),
        ("severe", a.severe_miles, b.severe_miles, MILES_TOLERANCE),
        ("high", a.high_miles, b.high_miles, MILES_TOLERANCE),
        ("avg_risk", _avg(a), _avg(b), AVG_RISK_TOLERANCE),
        ("duration", a.duration_min, b.duration_min, DURATION_TOLERANCE_MIN),
    ]
    for name, x, y, tol in checks:
        if math.isinf(x) and math.isinf(y):
            continue
        result = _cmp(x, y, tol)
        if result:
            return result, name
    return 0, "tie"


def rank_routes(metrics: Sequence[RouteMetrics]) -> list[RouteMetrics]:
    """Sort best-first. Python's sort is stable, so full ties keep provider order."""
    return sorted(metrics, key=cmp_to_key(lambda a, b: compare_routes(a, b)[0]))


def _mi(x: float) -> str:
    return f"{x:.0f}" if x >= 10 or x == 0 else f"{x:.1f}"


def format_minutes(minutes: float) -> str:
    minutes = round(abs(minutes))
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if h else f"{m} min"


def _reason(best: RouteMetrics, other: RouteMetrics, criterion: Criterion) -> str:
    if criterion == "any_no_travel":
        return f"no No Travel miles vs {_mi(other.no_travel_miles)} on {other.name}"
    if criterion == "no_travel":
        return f"{_mi(best.no_travel_miles)} No Travel miles vs {_mi(other.no_travel_miles)} on {other.name}"
    if criterion == "severe":
        return f"{_mi(best.severe_miles)} Severe miles vs {_mi(other.severe_miles)} on {other.name}"
    if criterion == "high":
        return (
            f"{_mi(best.high_miles)} High miles vs {_mi(other.high_miles)} on {other.name} "
            "(same Severe mileage)"
        )
    if criterion == "avg_risk":
        other_avg = "unknown" if other.avg_risk is None else f"{other.avg_risk:.2f}"
        return (
            f"average risk {_avg(best):.2f} vs {other_avg} on {other.name} "
            "(same Severe/High mileage)"
        )
    if criterion == "duration":
        return (
            f"same risk profile as {other.name} but "
            f"{format_minutes(other.duration_min - best.duration_min)} faster"
        )
    return f"equivalent to {other.name} on every criterion"


def build_explanation(ranked: Sequence[RouteMetrics]) -> str:
    """One-paragraph "why" comparing the recommended route with each alternative."""
    if not ranked:
        return "No routes to compare."
    best = ranked[0]
    parts: list[str] = []

    if all(m.no_travel_miles > 0 for m in ranked):
        parts.append(
            "WARNING: every route crosses No Travel conditions; consider delaying departure. "
            f"{best.name} has the least exposure."
        )

    if len(ranked) == 1:
        parts.append(
            f"{best.name} is the only route available: {_mi(best.severe_miles)} Severe and "
            f"{_mi(best.high_miles)} High miles."
        )
    else:
        reasons = [_reason(best, other, compare_routes(best, other)[1]) for other in ranked[1:]]
        parts.append(f"{best.name} is recommended: " + "; ".join(reasons) + ".")
        fastest = min(ranked, key=lambda m: m.duration_min)
        delta = best.duration_min - fastest.duration_min
        if delta <= DURATION_TOLERANCE_MIN:
            parts.append("It is also the fastest option.")
        else:
            parts.append(f"It is {format_minutes(delta)} slower than the fastest ({fastest.name}).")

    if best.unknown_miles > 0:
        parts.append(f"Weather was unavailable for {_mi(best.unknown_miles)} mi of this route.")
    return " ".join(parts)
