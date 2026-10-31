"""Analytic storm model for the demo scenario.

Cells drift east with a full-strength core and a linear falloff, so weather can be
computed for any point and hour without storing a grid. Time is hours after departure.
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.common.geo import LatLng, haversine_mi, miles_per_deg_lng

BACKGROUND_WIND_MPH = 8.0


@dataclass(frozen=True, slots=True)
class StormCell:
    name: str
    lat: float
    lng: float  # center at departure (hour 0)
    core_radius_mi: float
    radius_mi: float
    peak_wind_mph: float
    peak_rain_in_hr: float
    peak_snow_in_hr: float
    drift_mph: float  # eastward

    def center_at(self, hours: float) -> LatLng:
        return (self.lat, self.lng + self.drift_mph * hours / miles_per_deg_lng(self.lat))

    def intensity(self, point: LatLng, hours: float) -> float:
        """1.0 inside the core, 0.0 outside the radius, linear in between."""
        d = haversine_mi(point, self.center_at(hours))
        if d <= self.core_radius_mi:
            return 1.0
        if d >= self.radius_mi:
            return 0.0
        return (self.radius_mi - d) / (self.radius_mi - self.core_radius_mi)


@dataclass(frozen=True, slots=True)
class Conditions:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float


def conditions_at(cells: tuple[StormCell, ...], point: LatLng, hours: float) -> Conditions:
    """Strongest cell per variable; a max instead of a sum keeps overlaps within tuned values."""
    wind, rain, snow = BACKGROUND_WIND_MPH, 0.0, 0.0
    for cell in cells:
        k = cell.intensity(point, hours)
        if k <= 0:
            continue
        wind = max(wind, BACKGROUND_WIND_MPH + (cell.peak_wind_mph - BACKGROUND_WIND_MPH) * k)
        rain = max(rain, cell.peak_rain_in_hr * k)
        snow = max(snow, cell.peak_snow_in_hr * k)
    return Conditions(round(wind, 1), round(rain, 3), round(snow, 3))
