"""Attribute route mileage to checkpoints and compute per-route risk metrics (pure)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from apps.risk.rules import RiskLevel


def segment_miles(miles: Sequence[float], total_mi: float) -> list[float]:
    """Road length each checkpoint represents: midpoint to midpoint, so segments tile the route."""
    n = len(miles)
    if n == 0:
        return []
    if n == 1:
        return [total_mi]
    bounds = [0.0] + [(miles[i] + miles[i + 1]) / 2 for i in range(n - 1)] + [total_mi]
    return [max(0.0, bounds[i + 1] - bounds[i]) for i in range(n)]


@dataclass(slots=True)
class RouteMetrics:
    route_id: str
    name: str
    distance_mi: float
    duration_min: float
    low_miles: float = 0.0
    moderate_miles: float = 0.0
    high_miles: float = 0.0
    severe_miles: float = 0.0
    no_travel_miles: float = 0.0
    unknown_miles: float = 0.0
    avg_risk: float | None = None
    max_risk: int | None = None
    worst_index: int | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 2)
        return d


_BUCKET = {
    RiskLevel.LOW: "low_miles",
    RiskLevel.MODERATE: "moderate_miles",
    RiskLevel.HIGH: "high_miles",
    RiskLevel.SEVERE: "severe_miles",
    RiskLevel.NO_TRAVEL: "no_travel_miles",
}


def compute_metrics(
    route_id: str,
    name: str,
    distance_mi: float,
    duration_min: float,
    levels: Sequence[int | None],
    seg_miles: Sequence[float],
) -> RouteMetrics:
    """Miles per level and mileage-weighted average risk; unknown miles are excluded from the average."""
    m = RouteMetrics(
        route_id=route_id, name=name, distance_mi=distance_mi, duration_min=duration_min
    )
    weighted = known = 0.0
    for i, (level, seg) in enumerate(zip(levels, seg_miles, strict=True)):
        if level is None:
            m.unknown_miles += seg
            continue
        lvl = RiskLevel(level)
        setattr(m, _BUCKET[lvl], getattr(m, _BUCKET[lvl]) + seg)
        weighted += int(lvl) * seg
        known += seg
        if m.max_risk is None or int(lvl) > m.max_risk:
            m.max_risk, m.worst_index = int(lvl), i
    if known > 0:
        m.avg_risk = weighted / known
    elif any(level is not None for level in levels):
        # Degenerate zero-length route: fall back to the plain mean.
        vals = [int(x) for x in levels if x is not None]
        m.avg_risk = sum(vals) / len(vals)
    return m
