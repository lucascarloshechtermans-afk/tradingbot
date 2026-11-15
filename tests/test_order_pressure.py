import numpy as np
import pandas as pd
import pytest

from indicators.order_pressure import (
    multi_signal,
    order_pressure,
    passive_zones,
    period_hvns,
    psych_levels,
    psych_step,
    touches_psych_level,
)


def _bars(closes, volume=1_000_000.0, spread=0.5, freq="D"):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq=freq)
    close = pd.Series(closes, index=idx, dtype=float)
    open_ = close.shift(1).fillna(close.iloc[0])
    high = pd.concat([open_, close], axis=1).max(axis=1) + spread
    low = pd.concat([open_, close], axis=1).min(axis=1) - spread
    vol = volume if isinstance(volume, pd.Series) else pd.Series(volume, index=idx)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol})


def _set_last(df, o, h, lo, c, v, pos=-1):
    for col, val in zip(("open", "high", "low", "close", "volume"), (o, h, lo, c, v)):
        df.iloc[pos, df.columns.get_loc(col)] = val
    return df


# ------------------------------------------------------------- psych levels ---

@pytest.mark.parametrize("price,step", [(754.0, 10.0), (6000.0, 100.0), (21500.0, 1000.0), (1.08, 0.1)])
def test_psych_step_auto(price, step):
    assert psych_step(price) == pytest.approx(step)


def test_psych_levels_are_round_numbers_around_price():
    assert psych_levels(754.0, count=2) == [730.0, 740.0, 750.0, 760.0, 770.0]


def test_touches_psych_level():
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    high = pd.Series([751.0, 758.0], index=idx)
    low = pd.Series([748.0, 752.0], index=idx)
    assert touches_psych_level(high, low).tolist() == [True, False]


# ----------------------------------------------------------- order pressure ---

def test_order_pressure_uses_delta_when_given():
    df = _bars([100, 101, 102])
    delta = pd.Series([600_000.0, 600_000.0, 600_000.0], index=df.index)
    out = order_pressure(df, delta=delta, window=3)
    assert out["buy_volume"].iloc[-1] == pytest.approx(800_000)
    assert out["buy_pressure"].iloc[-1] == pytest.approx(80.0)


def test_aggressive_bar_needs_volume_and_result():
    df = _bars(100 + np.sin(np.arange(40) / 3), spread=1.0)
    _set_last(df, 100.0, 104.2, 99.8, 104.0, 4_000_000)
    assert order_pressure(df)["aggressive"].iloc[-1] == 1
    df2 = _set_last(df.copy(), 100.0, 100.6, 99.0, 100.5, 4_000_000)  # absorption, not aggression
    assert order_pressure(df2)["aggressive"].iloc[-1] == 0


# ------------------------------------------------------------ passive zones ---

def test_bullish_absorption_creates_zone_that_is_retested_then_broken():
    closes = list(100 + np.sin(np.arange(30) / 3)) + [100.0, 102.0, 103.0, 101.0, 98.0]
    df = _bars(closes, spread=1.0)
    _set_last(df, 100.0, 100.6, 99.0, 100.5, 4_000_000, pos=30)    # bullish absorption, lower wick
    # bar 31-32 trade away above the zone, bar 33 comes back into it, bar 34 closes below it
    df.iloc[33, df.columns.get_loc("low")] = 99.5
    df.iloc[33, df.columns.get_loc("close")] = 101.0
    zones, ev = passive_zones(df)
    z = next(z for z in zones if z.created == df.index[30])
    assert z.direction == 1 and z.bottom == pytest.approx(99.0)
    assert ev["zone_retest"].iloc[33] == 1
    assert ev["zone_broken"].iloc[34] == 1
    assert not z.active


# ------------------------------------------------------- rolling period HVN ---

def _weekly_history(seed=0):
    """Week 1 trades busy around 100, week 2 rallies to 110, week 3 drops back to 100."""
    rng = np.random.default_rng(seed)
    w1 = 100 + rng.normal(0, 0.3, 7)
    w2 = np.linspace(102, 110, 7)
    w3 = np.array([108, 105, 102, 100.2, 100.1, 103, 104])
    df = _bars(np.concatenate([w1, w2, w3]), spread=0.3)
    df.index = pd.date_range("2024-01-01", periods=21, freq="D")  # Monday start
    return df


def test_period_hvns_are_only_available_after_their_period_closes():
    df = _weekly_history()
    nodes, per = period_hvns(df, freq="W")
    first_week = [pn for pn in nodes if pn.period == pd.Period("2024-01-01", "W")]
    assert first_week and all(pn.available_from == pd.Timestamp("2024-01-08") for pn in first_week)
    assert per["prev_poc"].iloc[:7].isna().all()
    assert abs(per["prev_poc"].iloc[8] - 100) < 1.0


def test_period_hvn_retest_after_price_left():
    df = _weekly_history()
    _, per = period_hvns(df, freq="W")
    # week 3 returns to the week-1 node around 100 (bar 17/18)
    assert per["hvn_retest"].iloc[14:].any()
    first = per.index[per["hvn_retest"]][0]
    assert first >= pd.Timestamp("2024-01-15")


# ------------------------------------------------------------- multi signal ---

def test_multi_signal_scores_absorption_at_round_number():
    df = _bars(100 + np.sin(np.arange(40) / 3) + 3, spread=1.0)   # trades around 103
    _set_last(df, 100.2, 100.8, 99.2, 100.7, 4_000_000)           # absorption through 100.0
    out = multi_signal(df, psych=10.0)
    last = out.iloc[-1]
    assert last["absorption"] and last["at_psych"]
    assert last["confluence"] >= 2 and last["signal"] == 1
