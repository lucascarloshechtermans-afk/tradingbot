from __future__ import annotations

import pandas as pd

from price_action.historical_context import compute_historical_context
from price_action.levels import Level


def _idx(n):
    return pd.date_range("2023-01-01", periods=n, freq="D")


def test_fresh_52w_high_detected():
    close = pd.Series(range(100, 200), index=_idx(100), dtype=float)  # strictly rising, today IS the high
    ctx = compute_historical_context(close, last_close=199.0, levels=[])
    assert ctx.is_fresh_52w_high is True
    assert ctx.fifty_two_week_high == 199.0
    assert ctx.distance_to_52w_high_pct == 0.0


def test_not_fresh_when_well_below_high():
    close = pd.Series([100.0] * 50 + [150.0] + [100.0] * 49, index=_idx(100))
    ctx = compute_historical_context(close, last_close=100.0, levels=[])
    assert ctx.is_fresh_52w_high is False
    assert ctx.fifty_two_week_high == 150.0
    assert ctx.distance_to_52w_high_pct < 0


def test_distance_to_52w_low_positive_above_low():
    close = pd.Series([50.0] + [100.0] * 99, index=_idx(100))
    ctx = compute_historical_context(close, last_close=100.0, levels=[])
    assert ctx.fifty_two_week_low == 50.0
    assert ctx.distance_to_52w_low_pct == 100.0  # 100% above the low


def test_major_resistance_overhead_picks_strongest_level_above_price():
    levels = [
        Level(price=110.0, kind="resistance", touches=2, strength=40, last_touch=None),
        Level(price=115.0, kind="resistance", touches=5, strength=100, last_touch=None),
        Level(price=90.0, kind="resistance", touches=8, strength=100, last_touch=None),  # below price, ignored
        Level(price=105.0, kind="support", touches=3, strength=60, last_touch=None),
    ]
    close = pd.Series(100.0, index=_idx(60))
    ctx = compute_historical_context(close, last_close=100.0, levels=levels)
    assert ctx.major_resistance_overhead is not None
    assert ctx.major_resistance_overhead.price == 115.0  # strongest (touches=5) among those still above price


def test_no_look_ahead_in_52w_window():
    close = pd.Series(range(100, 200), index=_idx(100), dtype=float)
    full = compute_historical_context(close, last_close=199.0, levels=[])
    truncated = compute_historical_context(close.iloc[:50], last_close=149.0, levels=[])
    assert truncated.fifty_two_week_high == 149.0  # unaffected by the later, higher closes
