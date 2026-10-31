"""Registry of demo scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .storm import StormCell

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@dataclass(frozen=True)
class Scenario:
    key: str
    note: str
    origin: dict
    destination: dict
    routes_file: Path
    cells: tuple[StormCell, ...]
    default_load_lb: float


# Cell positions were tuned against the recorded routes:
# - "core" sits on I-80 in central Nebraska when the fastest route gets there.
#   Its 45-54 mph winds are No Travel above 30,000 lb and Severe below.
# - "north" clips the northern route; its 35-44 mph winds are Severe above
#   40,000 lb and High below.
# - "kansas" is a weak rain band on the southern route (Moderate at most).
WINTER_STORM_CELLS = (
    StormCell(
        name="core",
        lat=40.8,
        lng=-100.62,
        core_radius_mi=35,
        radius_mi=110,
        peak_wind_mph=52,
        peak_rain_in_hr=0.0,
        peak_snow_in_hr=2.6,
        drift_mph=15,
    ),
    StormCell(
        name="north",
        lat=42.25,
        lng=-100.2,
        core_radius_mi=15,
        radius_mi=60,
        peak_wind_mph=42,
        peak_rain_in_hr=0.0,
        peak_snow_in_hr=1.4,
        drift_mph=15,
    ),
    StormCell(
        name="kansas",
        lat=39.2,
        lng=-96.0,
        core_radius_mi=20,
        radius_mi=70,
        peak_wind_mph=30,
        peak_rain_in_hr=0.2,
        peak_snow_in_hr=0.0,
        drift_mph=15,
    ),
)

WINTER_STORM = Scenario(
    key="winter_storm",
    note="Simulated winter storm. This is not real weather.",
    origin={"label": "Denver, Colorado, United States", "lat": 39.7392, "lng": -104.9903},
    destination={"label": "Chicago, Illinois, United States", "lat": 41.8781, "lng": -87.6298},
    routes_file=FIXTURES / "winter_storm_routes.json",
    cells=WINTER_STORM_CELLS,
    default_load_lb=45_000,
)

SCENARIOS: dict[str, Scenario] = {WINTER_STORM.key: WINTER_STORM}


def get_scenario(key: str) -> Scenario:
    return SCENARIOS[key]
