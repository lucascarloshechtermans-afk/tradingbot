import numpy as np
import pandas as pd

from indicator_lab import pine_emulator as PE
from indicator_lab import strategies as S
from indicator_lab.engine import simulate


def _trending_ohlc(seed, n=1500):
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0012, 0.018, n) + 0.002 * np.sin(np.arange(n) / 60)
    c = 100 * np.exp(np.cumsum(r))
    o = c * np.exp(rng.normal(0, 0.006, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.008, n)))
    lo = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.008, n)))
    idx = pd.bdate_range("2015-01-01", periods=n)
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": 1e6}, index=idx)


def test_pine_state_machine_matches_engine_signal_for_signal():
    """The Pine script's BUY/SELL marks (emulated bar by bar) must equal the research
    engine's trades for v2 (model off): buy on the signal bar, sell on the bar the
    stop is hit or the exit signal fires."""
    for seed in range(5):
        df = _trending_ohlc(seed)
        p = {"n": 20, "m": 20, "trail": 4.0, "ibs_min": 0.7}
        entry, ex, rules, atr, _ = S.breakout(df, p)
        _, trades = simulate(df, entry, ex, atr, rules)
        idx = df.index
        eng_buy = {idx.get_loc(x["entry_date"]) - 1 for x in trades}
        eng_sell = {idx.get_loc(x["exit_date"]) - (0 if x["reason"] == "stop" else 1) for x in trades}
        buy, sell = PE.run(df, df["close"], use_model=False)
        last_exit = max(idx.get_loc(x["exit_date"]) for x in trades)
        pine_buy = {i for i in np.flatnonzero(buy) if i < last_exit}  # engine only logs closed trades
        assert len(trades) >= 5
        assert pine_buy == eng_buy
        assert {i for i in np.flatnonzero(sell) if i <= last_exit} == eng_sell


def test_pine_chart_statistics_book_the_same_returns_as_the_engine():
    df = _trending_ohlc(7)
    p = {"n": 20, "m": 20, "trail": 4.0, "ibs_min": 0.7}
    entry, ex, rules, atr, _ = S.breakout(df, p)
    _, trades = simulate(df, entry, ex, atr, rules, cost=0.001)
    _, _, rets = PE.run(df, df["close"], use_model=False, cost_pct=0.1, with_trades=True)
    assert len(trades) >= 5
    assert np.allclose(rets[:len(trades)], [x["ret"] for x in trades])
