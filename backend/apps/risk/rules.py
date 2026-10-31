"""Weather risk classification.

Ranges are lower-bound inclusive and upper-bound exclusive, except the No Travel
cutoffs: wind >= 55 mph, rain > 1.00 in/hr, snow > 3.0 in/hr. So rain at exactly
1.00 and snow at exactly 3.0 are Severe.

Load rules adjust wind only and never lower a level: 45-54 mph above 30,000 lb is
No Travel, 35-44 mph above 40,000 lb is Severe.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Literal

Factor = Literal["wind", "rain", "snow"]
Driver = Literal["wind", "rain", "snow", "none"]

# When several factors share the top level, the driver is reported in this order.
# Wind first because it is the only factor the load rules act on.
DRIVER_PRIORITY: tuple[Factor, ...] = ("wind", "snow", "rain")


class RiskLevel(IntEnum):
    LOW = 1
    MODERATE = 2
    HIGH = 3
    SEVERE = 4
    NO_TRAVEL = 5

    @property
    def label(self) -> str:
        return RISK_LABELS[self]


RISK_LABELS: dict[RiskLevel, str] = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}


def classify_wind(mph: float) -> RiskLevel:
    """Base wind level from sustained wind speed (mph), ignoring load."""
    if mph >= 55:
        return RiskLevel.NO_TRAVEL
    if mph >= 45:
        return RiskLevel.SEVERE
    if mph >= 35:
        return RiskLevel.HIGH
    if mph >= 25:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_rain(in_per_hr: float) -> RiskLevel:
    """Rain level from rain rate (in/hr). Exactly 1.00 is Severe; above is No Travel."""
    if in_per_hr > 1.00:
        return RiskLevel.NO_TRAVEL
    if in_per_hr >= 0.50:
        return RiskLevel.SEVERE
    if in_per_hr >= 0.25:
        return RiskLevel.HIGH
    if in_per_hr >= 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def classify_snow(in_per_hr: float) -> RiskLevel:
    """Snow level from snowfall rate (in/hr). Exactly 3.0 is Severe; above is No Travel."""
    if in_per_hr > 3.0:
        return RiskLevel.NO_TRAVEL
    if in_per_hr >= 2.0:
        return RiskLevel.SEVERE
    if in_per_hr >= 1.0:
        return RiskLevel.HIGH
    if in_per_hr >= 0.5:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def load_adjusted_wind(mph: float, load_lb: float) -> RiskLevel | None:
    """Level imposed by the load rules, or ``None`` when no load rule applies."""
    if mph >= 55:
        return RiskLevel.NO_TRAVEL
    if 45 <= mph < 55 and load_lb > 30_000:
        return RiskLevel.NO_TRAVEL
    if 35 <= mph < 45 and load_lb > 40_000:
        return RiskLevel.SEVERE
    return None


def wind_level(mph: float, load_lb: float) -> tuple[RiskLevel, bool]:
    """Wind level after load rules, and whether the load rule raised it."""
    base = classify_wind(mph)
    adjusted = load_adjusted_wind(mph, load_lb)
    if adjusted is not None and adjusted > base:
        return adjusted, True
    return base, False


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    level: RiskLevel
    driver: Driver
    load_adjusted: bool
    factors: dict[Factor, RiskLevel]

    def as_dict(self) -> dict:
        return {
            "risk": int(self.level),
            "risk_label": self.level.label,
            "driver": self.driver,
            "load_adjusted": self.load_adjusted,
            "factor_levels": {k: int(v) for k, v in self.factors.items()},
        }


def _clean(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return max(0.0, f)


def assess(
    wind_mph: float | None,
    rain_in_hr: float | None,
    snow_in_hr: float | None,
    load_lb: float,
) -> RiskAssessment | None:
    """Classify one checkpoint. Returns ``None`` (unknown) if any input is missing."""
    wind, rain, snow = _clean(wind_mph), _clean(rain_in_hr), _clean(snow_in_hr)
    if wind is None or rain is None or snow is None:
        return None

    w_level, load_adjusted = wind_level(wind, load_lb)
    factors: dict[Factor, RiskLevel] = {
        "wind": w_level,
        "rain": classify_rain(rain),
        "snow": classify_snow(snow),
    }
    level = max(factors.values())
    if level == RiskLevel.LOW:
        driver: Driver = "none"
    else:
        driver = next(f for f in DRIVER_PRIORITY if factors[f] == level)
    return RiskAssessment(
        level=level,
        driver=driver,
        load_adjusted=load_adjusted and driver == "wind",
        factors=factors,
    )
