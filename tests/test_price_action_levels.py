import pandas as pd

from price_action.levels import find_levels, nearest_level


def _idx(n):
    return pd.date_range("2024-01-01", periods=n, freq="D")


def test_find_levels_detects_repeated_resistance():
    # price touches ~110 three times as a ceiling, with troughs in between
    high = pd.Series([100, 105, 110, 106, 102, 108, 110, 105, 101, 107, 110, 104, 100], index=_idx(13))
    low = high - 5
    levels = find_levels(high, low, order=1, tolerance_pct=1.0, min_touches=2)
    resistance_levels = [lv for lv in levels if lv.kind == "resistance"]
    assert any(abs(lv.price - 110) < 1 for lv in resistance_levels)


def test_find_levels_respects_min_touches():
    high = pd.Series([100, 110, 100, 120, 100, 130, 100], index=_idx(7))
    low = high - 5
    levels = find_levels(high, low, order=1, tolerance_pct=0.5, min_touches=3)
    # each peak (110, 120, 130) is unique -> no cluster reaches 3 touches
    assert levels == []


def test_nearest_level_picks_closest_of_kind():
    high = pd.Series([100, 110, 100, 108, 100, 111, 100], index=_idx(7))
    low = pd.Series([90, 80, 89, 81, 90, 79, 91], index=_idx(7))
    levels = find_levels(high, low, order=1, tolerance_pct=2.0, min_touches=2)
    resistance = nearest_level(levels, price=109, kind="resistance")
    assert resistance is not None
    assert resistance.kind == "resistance"


def test_nearest_level_returns_none_when_no_levels_of_kind():
    assert nearest_level([], price=100, kind="support") is None
