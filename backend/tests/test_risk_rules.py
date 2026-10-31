import math

import pytest

from apps.risk.rules import (
    RiskLevel,
    assess,
    classify_rain,
    classify_snow,
    classify_wind,
    load_adjusted_wind,
    wind_level,
)

L, M, H, S, NT = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def test_numeric_scores():
    assert [int(x) for x in (L, M, H, S, NT)] == [1, 2, 3, 4, 5]
    assert NT.label == "No Travel"


@pytest.mark.parametrize(
    "mph,expected",
    [
        (0, L),
        (24.99, L),
        (25, M),
        (34.99, M),
        (35, H),
        (44.99, H),
        (45, S),
        (54.99, S),
        (55, NT),
        (80, NT),
    ],
)
def test_wind_boundaries(mph, expected):
    assert classify_wind(mph) == expected


@pytest.mark.parametrize(
    "rain,expected",
    [
        (0, L),
        (0.099, L),
        (0.10, M),
        (0.249, M),
        (0.25, H),
        (0.499, H),
        (0.50, S),
        (0.999, S),
        (1.00, S),
        (1.0001, NT),
        (2.5, NT),
    ],
)
def test_rain_boundaries(rain, expected):
    assert classify_rain(rain) == expected


@pytest.mark.parametrize(
    "snow,expected",
    [
        (0, L),
        (0.49, L),
        (0.5, M),
        (0.99, M),
        (1.0, H),
        (1.99, H),
        (2.0, S),
        (2.99, S),
        (3.0, S),
        (3.01, NT),
        (6, NT),
    ],
)
def test_snow_boundaries(snow, expected):
    assert classify_snow(snow) == expected


@pytest.mark.parametrize(
    "mph,load,expected_level,adjusted",
    [
        # >=55 is No Travel for any load (base rule already gives it, so not "adjusted").
        (55, 0, NT, False),
        (60, 80_000, NT, False),
        # 45-54 + >30,000 lb -> No Travel
        (45, 30_001, NT, True),
        (54.9, 45_000, NT, True),
        (45, 30_000, S, False),  # exactly 30,000 is not "> 30,000"
        (50, 10_000, S, False),
        # 35-44 + >40,000 lb -> Severe
        (35, 40_001, S, True),
        (44.9, 80_000, S, True),
        (35, 40_000, H, False),  # exactly 40,000 is not "> 40,000"
        (40, 35_000, H, False),
        # Below 35 mph loads never matter
        (34.9, 80_000, M, False),
        (10, 80_000, L, False),
    ],
)
def test_load_rules(mph, load, expected_level, adjusted):
    assert wind_level(mph, load) == (expected_level, adjusted)


def test_load_adjusted_wind_returns_none_when_no_rule():
    assert load_adjusted_wind(40, 10_000) is None
    assert load_adjusted_wind(20, 99_000) is None
    assert load_adjusted_wind(55, 0) == NT


def test_load_rule_never_lowers_level():
    # Wind 45-54 base Severe; heavy load rule for 35-44 (Severe) must not reduce anything.
    for mph in (35, 40, 45, 50, 55, 70):
        for load in (0, 30_001, 40_001, 80_000):
            assert wind_level(mph, load)[0] >= classify_wind(mph)


def test_assess_takes_max_and_driver():
    a = assess(10, 0.3, 0.6, 0)
    assert a.level == H and a.driver == "rain"
    assert a.factors == {"wind": L, "rain": H, "snow": M}

    b = assess(40, 0.0, 0.0, 45_000)
    assert b.level == S and b.driver == "wind" and b.load_adjusted is True

    c = assess(5, 0.0, 3.5, 0)
    assert c.level == NT and c.driver == "snow"


def test_assess_all_low_has_no_driver():
    a = assess(5, 0.01, 0.0, 80_000)
    assert a.level == L and a.driver == "none" and a.load_adjusted is False


def test_assess_tie_priority_wind_then_snow_then_rain():
    assert assess(36, 0.3, 1.5, 0).driver == "wind"
    assert assess(10, 0.3, 1.5, 0).driver == "snow"


def test_assess_load_adjusted_only_when_wind_drives():
    # Wind raised to Severe by load, but snow is No Travel -> driver snow, not load adjusted.
    a = assess(40, 0.0, 4.0, 45_000)
    assert a.driver == "snow" and a.level == NT and a.load_adjusted is False
    assert a.factors["wind"] == S


@pytest.mark.parametrize("bad", [None, math.nan, math.inf, "x"])
def test_assess_unknown_inputs(bad):
    assert assess(bad, 0, 0, 0) is None
    assert assess(5, bad, 0, 0) is None
    assert assess(5, 0, bad, 0) is None


def test_negative_values_clamped():
    assert assess(-3, -0.1, -1, 0).level == L


def test_as_dict_shape():
    d = assess(40, 0, 0, 45_000).as_dict()
    assert d == {
        "risk": 4,
        "risk_label": "Severe",
        "driver": "wind",
        "load_adjusted": True,
        "factor_levels": {"wind": 4, "rain": 1, "snow": 1},
    }
