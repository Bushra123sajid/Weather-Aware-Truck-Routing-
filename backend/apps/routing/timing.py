"""Turn provider step durations into a per-vertex cumulative time profile."""

from __future__ import annotations

from collections.abc import Sequence

from apps.common.geo import LatLng, haversine_mi


def build_time_profile(
    coords: Sequence[LatLng], steps: Sequence[tuple[int, int, float]]
) -> list[float]:
    """Cumulative seconds per vertex from (start_idx, end_idx, duration) steps.

    A step's duration is spread over its segments by length, so speed varies between
    steps (highway vs. city) but not within one.
    """
    n = len(coords)
    if n < 2:
        return [0.0] * n
    seg_len = [haversine_mi(coords[i], coords[i + 1]) for i in range(n - 1)]
    seg_time = [0.0] * (n - 1)

    for start, end, duration in steps:
        duration = max(0.0, float(duration))
        if duration == 0:
            continue
        a = max(0, min(int(start), n - 1))
        b = max(0, min(int(end), n - 1))
        if b <= a:
            seg_time[max(0, min(a, n - 1) - 1)] += duration
            continue
        length = sum(seg_len[a:b])
        if length <= 0:
            share = duration / (b - a)
            for i in range(a, b):
                seg_time[i] += share
        else:
            for i in range(a, b):
                seg_time[i] += duration * seg_len[i] / length

    cum = [0.0]
    for t in seg_time:
        cum.append(cum[-1] + t)
    return cum
