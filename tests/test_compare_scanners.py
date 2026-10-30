import numpy as np
import pandas as pd
import pytest

pytest.importorskip("alt_scanners.explosive_breakout_scanner")

import alt_scanners.explosive_breakout_scanner as eb  # noqa: E402
from config.schema import load_config  # noqa: E402
from research.compare_scanners import RULESETS, composite_momentum, simulate  # noqa: E402


def _synthetic(n=420, seed=1):
    rng = np.random.default_rng(seed)
    close = 50 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    open_ = close * (1 + rng.normal(0, 0.01, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, n)))
    idx = pd.bdate_range("2022-01-03", periods=n)
    df = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": 1e6}, index=idx)
    return eb.compute_indicators(df)


def test_vectorized_momentum_matches_their_function():
    df = _synthetic()
    vec = composite_momentum(df["Close"])
    for i in (300, 350, 419):
        assert vec.iloc[i] == pytest.approx(eb.bereken_samengesteld_momentum(df.iloc[: i + 1], "multi"))


def test_as_published_rules_reproduce_their_simuleer_exit():
    df = _synthetic()
    days = df.index[330:400:7]
    signals = pd.DataFrame({"date": days, "ticker": "X", "pct": 95.0})
    m1 = next(r for r in RULESETS if r.name.startswith("M1 "))
    got = simulate({"X": df}, signals, m1, load_config(None)).set_index("signal_date")
    method = eb.EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"]
    for day in days:
        i = df.index.get_loc(day)
        row = df.iloc[i]
        entry = row["Close"]
        stop0 = eb.compute_stop(row, entry)
        pct, outcome, _ = eb.simuleer_exit(df.iloc[i + 1 : i + 1 + eb.MAX_HOLD_DAYS], entry, row["ATR"], stop0, method)
        if "stop" in outcome:
            pct -= eb.get_dynamic_slippage(row["VOL_SMA20"] * entry) * 100
        pct -= eb.COMMISSION_PCT * 2 * 100
        assert got.loc[day, "pct"] == pytest.approx(pct)


def test_gap_aware_rules_fill_stop_at_the_gapped_open():
    df = _synthetic()
    i = 350
    row = df.iloc[i]
    stop0 = eb.compute_stop(row, row["Close"])
    # next session opens 5% below the stop and never trades back up to it
    gap_open = stop0 * 0.95
    j = df.index[i + 1]
    df.loc[j, ["Open", "High", "Low", "Close"]] = [gap_open, gap_open * 1.001, gap_open * 0.99, gap_open]
    signals = pd.DataFrame({"date": [df.index[i]], "ticker": "X", "pct": 95.0})
    cfg = load_config(None)
    naive = next(r for r in RULESETS if r.name.startswith("M1b"))
    aware = next(r for r in RULESETS if r.name.startswith("M1c"))
    naive_pct = simulate({"X": df}, signals, naive, cfg)["pct"].iloc[0]
    aware = simulate({"X": df}, signals, aware, cfg).iloc[0]
    assert aware["gap_through"]
    assert aware["pct"] == pytest.approx(naive_pct + (gap_open - stop0) / row["Close"] * 100)
