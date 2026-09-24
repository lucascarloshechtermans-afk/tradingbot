import pandas as pd

from market_regime.regime import classify_market_regime


def _trending_df(n=260, start=100.0, daily_change=0.3):
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    close = pd.Series([start + i * daily_change for i in range(n)], index=idx)
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000})


def _flat_df(n=260, level=20.0):
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    close = pd.Series([level] * n, index=idx)
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "volume": 1_000_000})


def test_bullish_regime_detected():
    spy = _trending_df(daily_change=0.4)
    qqq = _trending_df(daily_change=0.5)
    iwm = _trending_df(daily_change=0.3)
    vix = _flat_df(level=13.0)
    regime = classify_market_regime(spy, qqq, iwm, vix, breadth_pct_above_50ma=70)
    assert regime.label == "BULLISH"
    assert regime.score > 0


def test_bearish_regime_detected():
    spy = _trending_df(daily_change=-0.4)
    qqq = _trending_df(daily_change=-0.5)
    iwm = _trending_df(daily_change=-0.3)
    vix = _flat_df(level=22.0)
    regime = classify_market_regime(spy, qqq, iwm, vix, breadth_pct_above_50ma=25)
    assert regime.label == "BEARISH"
    assert regime.score < 0


def test_high_volatility_overrides_everything():
    spy = _trending_df(daily_change=0.4)  # otherwise-bullish trend
    qqq = _trending_df(daily_change=0.5)
    iwm = _trending_df(daily_change=0.3)
    vix = _flat_df(level=40.0)  # panic-level VIX
    regime = classify_market_regime(spy, qqq, iwm, vix, breadth_pct_above_50ma=70)
    assert regime.label == "HIGH_VOLATILITY"


def test_neutral_regime_for_mixed_signals():
    spy = _flat_df(level=100.0)
    qqq = _flat_df(level=100.0)
    iwm = _flat_df(level=100.0)
    vix = _flat_df(level=18.0)
    regime = classify_market_regime(spy, qqq, iwm, vix)
    assert regime.label == "NEUTRAL"


def test_regime_factors_are_explained():
    spy = _trending_df(daily_change=0.4)
    qqq = _trending_df(daily_change=0.5)
    iwm = _trending_df(daily_change=0.3)
    vix = _flat_df(level=13.0)
    regime = classify_market_regime(spy, qqq, iwm, vix)
    assert "spy_trend" in regime.factors
    assert "vix" in regime.factors
