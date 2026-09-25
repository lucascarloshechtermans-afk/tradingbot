import pytest

from price_action.fibonacci import fibonacci_retracement_levels, nearest_fib_ratio


def test_fibonacci_retracement_levels_basic():
    levels = fibonacci_retracement_levels(swing_high=110.0, swing_low=100.0)
    assert levels[0.5] == pytest.approx(105.0)
    assert levels[0.618] == pytest.approx(110.0 - 10 * 0.618)


def test_nearest_fib_ratio_within_tolerance():
    levels = fibonacci_retracement_levels(swing_high=110.0, swing_low=100.0)
    ratio = nearest_fib_ratio(105.0, levels, tolerance_pct=1.0)
    assert ratio == 0.5


def test_nearest_fib_ratio_none_outside_tolerance():
    levels = fibonacci_retracement_levels(swing_high=110.0, swing_low=100.0)
    ratio = nearest_fib_ratio(107.0, levels, tolerance_pct=0.5)
    assert ratio is None
