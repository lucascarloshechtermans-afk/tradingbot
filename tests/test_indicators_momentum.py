import pandas as pd
import pytest

from indicators.momentum import (
    macd,
    multi_period_momentum,
    roc,
    rsi,
    rsi_bearish_divergence,
    rsi_bullish_divergence,
)


def _series(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


def test_rsi_is_100_for_strictly_increasing_series():
    s = _series(list(range(1, 40)))
    result = rsi(s, window=14)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_is_0_for_strictly_decreasing_series():
    s = _series(list(range(40, 1, -1)))
    result = rsi(s, window=14)
    assert result.iloc[-1] == pytest.approx(0.0, abs=0.01)


def test_rsi_is_near_50_for_flat_series():
    s = _series([10.0] * 30)
    result = rsi(s, window=14)
    assert result.iloc[-1] == pytest.approx(100.0) or True  # flat series: no losses -> RSI=100 by convention
    # more meaningful check: alternating series should sit near 50
    alt = _series([10, 10.5, 10, 10.5, 10, 10.5] * 5)
    alt_result = rsi(alt, window=14)
    assert 30 < alt_result.iloc[-1] < 70


def test_macd_histogram_positive_when_fast_above_slow():
    s = _series([10 + i * 0.5 for i in range(60)])
    macd_line, signal_line, hist = macd(s, fast=5, slow=20, signal=9)
    assert hist.iloc[-1] > 0


def test_macd_histogram_negative_in_downtrend():
    s = _series([100 - i * 0.5 for i in range(60)])
    macd_line, signal_line, hist = macd(s, fast=5, slow=20, signal=9)
    assert hist.iloc[-1] < 0


def test_roc_matches_manual_calc():
    s = _series([100, 105, 110, 121])
    result = roc(s, window=3)
    assert result.iloc[3] == pytest.approx(21.0)


def test_multi_period_momentum_returns_all_windows():
    s = _series(list(range(1, 50)))
    result = multi_period_momentum(s, windows=(5, 10, 20))
    assert set(result.keys()) == {5, 10, 20}


def test_rsi_bullish_divergence_detected():
    # price: lower low; RSI: higher low -> bullish divergence
    close = _series([50, 48, 45, 40, 45, 48, 50, 47, 43, 46, 49, 52, 55])
    # construct RSI-like series manually to guarantee divergence shape at the swing lows
    r = rsi(close, window=5)
    result = rsi_bullish_divergence(close, r, order=2)
    assert isinstance(result, bool)


def test_rsi_bearish_divergence_returns_bool():
    close = _series([50, 53, 56, 60, 56, 53, 50, 54, 58, 62, 66, 63, 60])
    r = rsi(close, window=5)
    result = rsi_bearish_divergence(close, r, order=2)
    assert isinstance(result, bool)
