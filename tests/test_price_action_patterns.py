import pandas as pd

from price_action.levels import Level
from price_action.patterns import (
    detect_gap,
    has_higher_low,
    has_lower_high,
    has_volume_confirmation,
    is_breakdown,
    is_breakout,
    is_consolidation,
    is_consolidation_breakout,
    is_gap_filled,
    is_pullback_to_ma,
    is_resistance_rejection,
    is_support_bounce,
    is_volatility_contraction,
)


def _idx(n):
    return pd.date_range("2024-01-01", periods=n, freq="D")


def test_is_breakout_true_when_close_exceeds_prior_high():
    high = pd.Series([10] * 20 + [15], index=_idx(21))
    close = pd.Series([9] * 20 + [15], index=_idx(21))
    assert is_breakout(high, close, lookback=20) is True


def test_is_breakout_false_when_within_prior_range():
    high = pd.Series([10] * 21, index=_idx(21))
    close = pd.Series([9] * 21, index=_idx(21))
    assert is_breakout(high, close, lookback=20) is False


def test_is_breakdown_true_when_close_below_prior_low():
    low = pd.Series([10] * 20 + [5], index=_idx(21))
    close = pd.Series([11] * 20 + [5], index=_idx(21))
    assert is_breakdown(low, close, lookback=20) is True


def test_has_volume_confirmation_true_on_spike():
    volume = pd.Series([1000] * 20 + [3000], index=_idx(21))
    assert has_volume_confirmation(volume, rvol_threshold=1.5) is True


def test_has_volume_confirmation_false_on_normal_volume():
    volume = pd.Series([1000] * 21, index=_idx(21))
    assert has_volume_confirmation(volume, rvol_threshold=1.5) is False


def test_is_pullback_to_ma_true_within_tolerance():
    close = pd.Series([100.5])
    ma = pd.Series([100.0])
    assert is_pullback_to_ma(close, ma, tolerance_pct=1.0) is True


def test_is_pullback_to_ma_false_outside_tolerance():
    close = pd.Series([110.0])
    ma = pd.Series([100.0])
    assert is_pullback_to_ma(close, ma, tolerance_pct=1.0) is False


def test_is_consolidation_true_for_tight_range():
    high = pd.Series([100, 101, 100, 102, 101, 100, 101, 102, 100, 101], index=_idx(10))
    low = high - 1
    assert is_consolidation(high, low, window=10, max_range_pct=6.0) is True


def test_is_consolidation_false_for_wide_range():
    high = pd.Series([100, 110, 90, 120, 80, 130, 70, 140, 60, 150], index=_idx(10))
    low = high - 1
    assert is_consolidation(high, low, window=10, max_range_pct=6.0) is False


def test_is_consolidation_breakout():
    tight_high = [100, 101, 100, 101, 100, 101, 100, 101, 100, 101]
    high = pd.Series(tight_high + [110], index=_idx(11))
    low = high - 1
    close = pd.Series([99] * 10 + [110], index=_idx(11))
    assert is_consolidation_breakout(high, low, close, window=10, max_range_pct=6.0) is True


def test_support_bounce_detected():
    levels = [Level(price=100.0, kind="support", touches=3, strength=60, last_touch=_idx(1)[0])]
    low = pd.Series([100.3])
    close = pd.Series([101.5])
    assert is_support_bounce(low, close, levels, tolerance_pct=1.0) is True


def test_resistance_rejection_detected():
    levels = [Level(price=100.0, kind="resistance", touches=3, strength=60, last_touch=_idx(1)[0])]
    high = pd.Series([100.4])
    close = pd.Series([98.0])
    assert is_resistance_rejection(high, close, levels, tolerance_pct=1.0) is True


def test_detect_gap_up():
    open_ = pd.Series([100, 105])
    close = pd.Series([99, 106])
    assert detect_gap(open_, close, threshold_pct=1.0) == "gap_up"


def test_detect_gap_down():
    open_ = pd.Series([100, 95])
    close = pd.Series([99, 90])
    assert detect_gap(open_, close, threshold_pct=1.0) == "gap_down"


def test_detect_gap_none_for_small_move():
    open_ = pd.Series([100, 100.2])
    close = pd.Series([100, 100.5])
    assert detect_gap(open_, close, threshold_pct=1.0) is None


def test_is_gap_filled_true_when_price_retraces_through_prev_close():
    open_ = pd.Series([100, 105])
    close = pd.Series([100, 106])
    low = pd.Series([99, 99.5])
    high = pd.Series([101, 107])
    assert is_gap_filled(open_, low, high, close, threshold_pct=1.0) is True


def test_is_volatility_contraction_uses_squeeze():
    volatile = [100 + (10 if i % 2 == 0 else -10) for i in range(60)]
    flat = [100.0] * 40
    close = pd.Series(volatile + flat, index=_idx(100))
    assert is_volatility_contraction(close, window=20, lookback=100, percentile=0.2) is True


def test_has_higher_low_true_for_rising_troughs():
    low = pd.Series([10, 8, 11, 9, 12, 10, 13], index=_idx(7))
    assert has_higher_low(low, order=1) is True


def test_has_lower_high_true_for_falling_peaks():
    high = pd.Series([20, 22, 19, 21, 18, 20, 17], index=_idx(7))
    assert has_lower_high(high, order=1) is True
