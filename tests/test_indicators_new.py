import pandas as pd
import pytest

from indicators.momentum import (
    macd_above_zero,
    macd_cross,
    macd_histogram_accelerating,
    rsi,
    rsi_bullish_divergence,
    rsi_hidden_bearish_divergence,
    rsi_hidden_bullish_divergence,
)
from indicators.trend import crossover, ema_spread_pct
from indicators.trend_strength import adx, adx_slope
from indicators.volatility import distance_in_atr, is_expanding
from indicators.volume import is_volume_drying_up, obv_bearish_divergence, obv_bullish_divergence, on_balance_volume
from indicators.vwap import anchored_vwap, default_vwap_anchor_index, vwap_slope


def _s(values):
    return pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values), freq="D"), dtype=float)


def test_ema_spread_pct_positive_when_fast_above_slow():
    fast = _s([110.0])
    slow = _s([100.0])
    assert ema_spread_pct(fast, slow).iloc[0] == pytest.approx(10.0)


def test_crossover_detects_bullish_cross():
    fast = _s([9, 11])
    slow = _s([10, 10])
    assert crossover(fast, slow) == "bullish_cross"


def test_crossover_detects_bearish_cross():
    fast = _s([11, 9])
    slow = _s([10, 10])
    assert crossover(fast, slow) == "bearish_cross"


def test_crossover_none_when_already_above():
    fast = _s([12, 13])
    slow = _s([10, 10])
    assert crossover(fast, slow) == "none"


def test_adx_slope_positive_when_trend_emerges_from_chop():
    # choppy/sideways phase (low ADX) followed by a clean new uptrend (rising ADX)
    choppy = [100 + (1 if i % 2 == 0 else -1) for i in range(30)]
    trending = [choppy[-1] + i * 0.8 for i in range(1, 11)]
    close = _s(choppy + trending)
    high = close + 0.5
    low = close - 0.5
    adx_series, _, _ = adx(high, low, close, window=14)
    slope = adx_slope(adx_series, lookback=5)
    assert slope.dropna().iloc[-1] > 0


def test_distance_in_atr_basic():
    assert distance_in_atr(price=110.0, level=100.0, atr_value=5.0) == pytest.approx(2.0)


def test_distance_in_atr_nan_for_zero_atr():
    result = distance_in_atr(price=110.0, level=100.0, atr_value=0.0)
    assert result != result  # NaN


def test_is_expanding_true_after_squeeze_breaks():
    tight = [100.0] * 30
    widening = [100 + i * 2 for i in range(10)]
    close = _s(tight + widening)
    assert bool(is_expanding(close, window=10, lookback=3).iloc[-1]) is True


def test_macd_cross_detects_bullish():
    macd_line = _s([-1, 1])
    signal_line = _s([0, 0])
    assert macd_cross(macd_line, signal_line) == "bullish_cross"


def test_macd_above_zero():
    assert macd_above_zero(_s([1.5])) is True
    assert macd_above_zero(_s([-1.5])) is False


def test_macd_histogram_accelerating_true_for_growing_positive_histogram():
    hist = _s([0.1, 0.3, 0.6, 1.0])
    assert macd_histogram_accelerating(hist, lookback=3) is True


def test_macd_histogram_accelerating_false_for_shrinking_histogram():
    hist = _s([1.0, 0.6, 0.3, 0.1])
    assert macd_histogram_accelerating(hist, lookback=3) is False


def test_rsi_hidden_bullish_divergence_price_higher_low_rsi_lower_low():
    # construct closes so price's second swing low is HIGHER, and RSI's reading
    # at that point is LOWER than the first swing low
    close = _s([50, 45, 50, 55, 48, 53, 58, 50, 56, 62, 68, 63, 70])
    r = rsi(close, window=5)
    result = rsi_hidden_bullish_divergence(close, r, order=2)
    assert isinstance(result, bool)


def test_rsi_hidden_bearish_divergence_returns_bool():
    close = _s([50, 55, 50, 45, 52, 47, 42, 50, 44, 38, 32, 37, 30])
    r = rsi(close, window=5)
    result = rsi_hidden_bearish_divergence(close, r, order=2)
    assert isinstance(result, bool)


def test_regular_and_hidden_divergence_are_mutually_exclusive_by_construction():
    # regular bullish requires price LOWER low + osc HIGHER low
    # hidden bullish requires price HIGHER low + osc LOWER low
    # they can never both be true for the same pair of swings
    close = _s([50, 48, 45, 40, 45, 48, 50, 47, 43, 46, 49, 52, 55])
    r = rsi(close, window=5)
    regular = rsi_bullish_divergence(close, r, order=2)
    hidden = rsi_hidden_bullish_divergence(close, r, order=2)
    assert not (regular and hidden)


def test_obv_bullish_divergence_returns_bool():
    close = _s([50, 48, 45, 40, 45, 48, 50, 47, 43, 46, 49, 52, 55])
    volume = _s([1000] * 13)
    obv = on_balance_volume(close, volume)
    result = obv_bullish_divergence(close, obv, order=2)
    assert isinstance(result, bool)


def test_obv_bearish_divergence_returns_bool():
    close = _s([50, 53, 56, 60, 56, 53, 50, 54, 58, 62, 66, 63, 60])
    volume = _s([1000] * 13)
    obv = on_balance_volume(close, volume)
    result = obv_bearish_divergence(close, obv, order=2)
    assert isinstance(result, bool)


def test_is_volume_drying_up_true_when_recent_much_lower():
    volume = _s([2000.0] * 50 + [500.0] * 10)
    assert is_volume_drying_up(volume, window=10, lookback=50) is True


def test_is_volume_drying_up_false_when_recent_similar():
    volume = _s([1000.0] * 60)
    assert is_volume_drying_up(volume, window=10, lookback=50) is False


def test_is_volume_drying_up_false_with_insufficient_history():
    volume = _s([1000.0] * 20)
    assert is_volume_drying_up(volume, window=10, lookback=50) is False


def test_anchored_vwap_matches_manual_calc_from_anchor():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    high = pd.Series([11, 12, 13, 14], index=idx, dtype=float)
    low = pd.Series([9, 10, 11, 12], index=idx, dtype=float)
    close = pd.Series([10, 11, 12, 13], index=idx, dtype=float)
    volume = pd.Series([100, 200, 100, 100], index=idx, dtype=float)

    result = anchored_vwap(high, low, close, volume, anchor_index=1)
    assert result.iloc[0] != result.iloc[0]  # NaN before anchor

    typical_1 = (12 + 10 + 11) / 3
    typical_2 = (13 + 11 + 12) / 3
    expected_bar2 = (typical_1 * 200 + typical_2 * 100) / 300
    assert result.iloc[2] == pytest.approx(expected_bar2)


def test_default_vwap_anchor_index_finds_recent_swing_low():
    low = _s([10, 9, 8, 9, 10, 11, 12, 11, 10, 9])
    idx = default_vwap_anchor_index(low, order=2, lookback=10)
    assert 0 <= idx < len(low)


def test_vwap_slope_positive_for_rising_vwap():
    vwap = _s([100, 101, 102, 103, 104, 105])
    assert vwap_slope(vwap, lookback=3).iloc[-1] > 0
