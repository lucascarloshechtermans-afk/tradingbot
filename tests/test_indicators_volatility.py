import pandas as pd
import pytest

from indicators.volatility import (
    atr,
    atr_percent,
    bollinger_bands,
    bollinger_band_width,
    historical_volatility,
    is_squeeze,
    true_range,
)


def _ohlc(closes, spread=1.0):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    close = pd.Series(closes, index=idx, dtype=float)
    high = close + spread / 2
    low = close - spread / 2
    return high, low, close


def test_true_range_uses_largest_of_three_components():
    high, low, close = _ohlc([100, 101, 99])
    tr = true_range(high, low, close)
    # bar 1: high-low=1, |high-prevclose|=|101.5-100|=1.5, |low-prevclose|=|100.5-100|=0.5
    assert tr.iloc[1] == pytest.approx(1.5)


def test_atr_is_positive_and_smoothed():
    high, low, close = _ohlc([100 + i for i in range(30)], spread=2.0)
    result = atr(high, low, close, window=14)
    assert result.dropna().gt(0).all()


def test_atr_percent_scales_with_price():
    high, low, close = _ohlc([100] * 30, spread=2.0)
    pct = atr_percent(high, low, close, window=14)
    assert pct.dropna().iloc[-1] == pytest.approx(2.0, abs=0.3)


def test_bollinger_bands_upper_above_lower():
    high, low, close = _ohlc([100 + (i % 5) for i in range(40)], spread=1.0)
    upper, middle, lower = bollinger_bands(close, window=20)
    valid = upper.dropna().index
    assert (upper[valid] >= lower[valid]).all()


def test_bollinger_band_width_zero_for_constant_series():
    high, low, close = _ohlc([50.0] * 40)
    width = bollinger_band_width(close, window=20)
    assert width.dropna().iloc[-1] == pytest.approx(0.0)


def test_historical_volatility_higher_for_choppier_series():
    calm = [100 + (0.01 if i % 2 == 0 else -0.01) for i in range(60)]
    wild = [100 + (5 if i % 2 == 0 else -5) for i in range(60)]
    _, _, calm_close = _ohlc(calm)
    _, _, wild_close = _ohlc(wild)
    calm_vol = historical_volatility(calm_close, window=20).iloc[-1]
    wild_vol = historical_volatility(wild_close, window=20).iloc[-1]
    assert wild_vol > calm_vol


def test_is_squeeze_true_during_flat_period_after_volatility():
    volatile = [100 + (10 if i % 2 == 0 else -10) for i in range(60)]
    flat = [100.0] * 40
    _, _, close = _ohlc(volatile + flat)
    squeeze = is_squeeze(close, window=20, lookback=100, percentile=0.2)
    assert bool(squeeze.iloc[-1]) is True
