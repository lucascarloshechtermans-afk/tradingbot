import pandas as pd

from indicators.trend_strength import adx


def _trending_ohlc(n=60):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series([100 + i * 1.5 for i in range(n)], index=idx)
    high = close + 0.5
    low = close - 0.5
    return high, low, close


def _choppy_ohlc(n=60):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series([100 + (2 if i % 2 == 0 else -2) for i in range(n)], index=idx)
    high = close + 1.0
    low = close - 1.0
    return high, low, close


def test_adx_higher_for_strong_trend_than_choppy_market():
    high_t, low_t, close_t = _trending_ohlc()
    high_c, low_c, close_c = _choppy_ohlc()

    adx_trend, plus_di_t, minus_di_t = adx(high_t, low_t, close_t, window=14)
    adx_choppy, plus_di_c, minus_di_c = adx(high_c, low_c, close_c, window=14)

    assert adx_trend.dropna().iloc[-1] > adx_choppy.dropna().iloc[-1]


def test_plus_di_dominates_in_uptrend():
    high, low, close = _trending_ohlc()
    _, plus_di, minus_di = adx(high, low, close, window=14)
    assert plus_di.dropna().iloc[-1] > minus_di.dropna().iloc[-1]


def test_minus_di_dominates_in_downtrend():
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    close = pd.Series([200 - i * 1.5 for i in range(60)], index=idx)
    high = close + 0.5
    low = close - 0.5
    _, plus_di, minus_di = adx(high, low, close, window=14)
    assert minus_di.dropna().iloc[-1] > plus_di.dropna().iloc[-1]


def test_adx_values_within_0_100_bounds():
    high, low, close = _trending_ohlc()
    adx_series, plus_di, minus_di = adx(high, low, close, window=14)
    valid = adx_series.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()
