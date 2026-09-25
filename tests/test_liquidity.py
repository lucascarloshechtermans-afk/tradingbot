from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.volatility import atr_percent
from liquidity.liquidity import (
    average_dollar_volume,
    average_share_volume,
    corwin_schultz_spread_estimate,
    evaluate_liquidity,
)


def _idx(n):
    return pd.date_range("2023-01-01", periods=n, freq="D")


def _history(n=60, price=100.0, volume=1_000_000.0, hl_spread_pct=0.5, seed=0):
    rng = np.random.default_rng(seed)
    close = pd.Series(price + rng.normal(0, 0.5, n).cumsum() * 0, index=_idx(n))  # keep flat-ish for determinism
    close = pd.Series(price, index=_idx(n))
    high = close * (1 + hl_spread_pct / 100)
    low = close * (1 - hl_spread_pct / 100)
    open_ = close
    vol = pd.Series(volume, index=_idx(n))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol})


def test_average_dollar_volume_basic():
    history = _history(n=30, price=50.0, volume=2_000_000.0)
    result = average_dollar_volume(history, window=20)
    assert result == 100_000_000.0


def test_average_share_volume_basic():
    history = _history(n=30, volume=3_000_000.0)
    result = average_share_volume(history, window=20)
    assert result == 3_000_000.0


def test_average_dollar_volume_none_with_insufficient_history():
    history = _history(n=5)
    assert average_dollar_volume(history, window=20) is None


def test_corwin_schultz_wider_range_gives_higher_spread_estimate():
    tight = _history(n=60, hl_spread_pct=0.1)
    wide = _history(n=60, hl_spread_pct=2.0)
    tight_spread = corwin_schultz_spread_estimate(tight["high"], tight["low"], window=20).iloc[-1]
    wide_spread = corwin_schultz_spread_estimate(wide["high"], wide["low"], window=20).iloc[-1]
    assert wide_spread > tight_spread
    assert wide_spread >= 0 and tight_spread >= 0


def test_corwin_schultz_no_look_ahead():
    history = _history(n=60, hl_spread_pct=0.8, seed=1)
    full = corwin_schultz_spread_estimate(history["high"], history["low"], window=20)
    truncated = corwin_schultz_spread_estimate(history["high"].iloc[:40], history["low"].iloc[:40], window=20)
    assert full.iloc[39] == truncated.iloc[-1]


def test_evaluate_liquidity_rejects_thin_dollar_volume():
    history = _history(n=60, price=2.0, volume=100.0)  # $200/day, nowhere near tradeable
    atr_pct = atr_percent(history["high"], history["low"], history["close"], 14)
    profile = evaluate_liquidity(history, atr_pct, min_avg_dollar_volume=5_000_000)
    assert profile.tradeable is False
    assert any("dollar volume" in r.lower() for r in profile.reasons)


def test_evaluate_liquidity_rejects_wide_spread():
    history = _history(n=60, price=50.0, volume=1_000_000.0, hl_spread_pct=5.0)  # unrealistically wide range
    atr_pct = atr_percent(history["high"], history["low"], history["close"], 14)
    profile = evaluate_liquidity(history, atr_pct, min_avg_dollar_volume=1000, max_spread_pct_estimate=0.5)
    assert profile.tradeable is False
    assert any("spread" in r.lower() for r in profile.reasons)


def test_evaluate_liquidity_accepts_healthy_stock():
    history = _history(n=60, price=100.0, volume=5_000_000.0, hl_spread_pct=0.3)
    atr_pct = atr_percent(history["high"], history["low"], history["close"], 14)
    profile = evaluate_liquidity(history, atr_pct, min_avg_dollar_volume=5_000_000, max_spread_pct_estimate=1.0)
    assert profile.tradeable is True
    assert profile.avg_dollar_volume == 500_000_000.0
