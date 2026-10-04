import numpy as np
import pandas as pd

from ta.candles import evaluate_candles, shapes_at
from ta.core import compute_indicators, normalize
from ta.levels import Zone
from ta.liquidity import assess_liquidity
from ta.swings import find_swings
from ta.timeframes import build_timeframes, monthly_frame, weekly_frame
from ta.volatility import assess_volatility
from ta.volume import assess_volume, breakout_volume_ratio
from tests.ta_helpers import frame, zigzag


def test_volume_unavailable_and_breakout_ratio():
    df = frame(list(np.linspace(100, 120, 80)))
    df["volume"] = 0.0
    ind = compute_indicators(normalize(df))
    va = assess_volume(df, ind, [], len(df) - 1)
    assert not va.available and "niet beschikbaar" in va.notes[0]
    df2 = frame(list(np.linspace(100, 120, 40)), vol=[1e6] * 39 + [3e6])
    assert abs(breakout_volume_ratio(df2, 39) - 3.0) < 1e-9


def test_squeeze_nr7_inside_bars():
    rng = np.random.default_rng(1)
    closes = list(150 + rng.normal(0, 3, 120)) + [150 + (0.02 if i % 2 else -0.02) for i in range(40)]
    df = frame(closes, spread=0.001)
    # last bar inside the previous one and the narrowest of 7
    df.iloc[-1, df.columns.get_loc("high")] = df["high"].iloc[-2] - 0.01
    df.iloc[-1, df.columns.get_loc("low")] = df["low"].iloc[-2] + 0.01
    va = assess_volatility(df, compute_indicators(df))
    assert va.squeeze_on and va.squeeze_bars >= 5
    assert va.nr7 and va.inside_bars >= 1 and va.contraction


def _hammer_frame():
    closes = list(np.linspace(120, 100, 30))
    df = frame(closes, spread=0.002)
    df.iloc[-1] = [99.8, 100.7, 96.0, 100.6, 2e6]   # long lower shadow, small body at the top
    return df


def test_hammer_scores_higher_at_support_than_in_the_middle():
    df = _hammer_frame()
    ind = compute_indicators(df)
    assert "hammer" in shapes_at(df, len(df) - 1, ind.last("atr"))
    at_zone = evaluate_candles(df, ind, [Zone(95.5, 96.5, strength="strong", role="support")], trend_direction=0)
    nowhere = evaluate_candles(df, ind, [Zone(60, 61, strength="strong", role="support")], trend_direction=0)
    s1 = next(x for x in at_zone if x.name == "hammer")
    s2 = next(x for x in nowhere if x.name == "hammer")
    assert s1.score > s2.score and s1.confirmation == "pending"


def test_sweep_and_failed_breakout_and_fvg():
    closes = zigzag(100, [10, -6, 8, -3], 6) + [110, 111, 112, 113, 110]
    df = frame(closes, spread=0.002)
    lows = [s for s in find_swings(df.iloc[:-1], 3) if s.kind == "L"]
    lvl = lows[-1].price
    df.iloc[-1, df.columns.get_loc("low")] = lvl - 1.0   # wick under the last swing low, close back above
    ind = compute_indicators(df)
    la = assess_liquidity(df, ind, find_swings(df, 3))
    assert any(e.kind == "sweep_low" and abs(e.level - lvl) < 1e-9 for e in la.events)
    # a bullish fair value gap: low of bar i above high of bar i-2
    g = frame(list(np.linspace(100, 101, 40)) + [104, 110, 112, 113], spread=0.001)
    gl = assess_liquidity(g, compute_indicators(g), find_swings(g, 3))
    assert any(x.direction == "bull" and x.status == "open" for x in gl.gaps)


def test_timeframes_use_closed_candles_only():
    idx = pd.bdate_range("2026-07-01", "2026-09-30")
    d = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": np.arange(len(idx), dtype=float) + 1, "volume": 1.0}, index=idx)
    wed = d[d.index <= "2026-09-23"]           # Wednesday: the current week is incomplete
    assert weekly_frame(wed).index[-1] == pd.Timestamp("2026-09-18")   # last COMPLETE week
    fri = d[d.index <= "2026-09-25"]
    assert weekly_frame(fri).index[-1] == pd.Timestamp("2026-09-25")
    assert monthly_frame(d[d.index <= "2026-09-29"]).index[-1].month == 8
    assert monthly_frame(d).index[-1].month == 9
    hidx = pd.date_range("2026-09-28 13:30", "2026-10-01 19:30", freq="h", tz="UTC")
    h = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=hidx)
    tf = build_timeframes(d[d.index <= "2026-09-29"], h)
    assert tf["4h"].index.max() < pd.Timestamp("2026-09-30")
