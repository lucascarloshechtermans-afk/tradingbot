"""Mechanics of the relative-strength rotation backtest on synthetic prices with a known answer."""
import numpy as np
import pandas as pd

from indicator_lab.rotation import mom


def _setup(n_days=300, growth=(0.002, 0.001, -0.001)):
    idx = pd.bdate_range("2020-01-01", periods=n_days)
    C = pd.DataFrame({f"S{i}": 10 * (1 + g) ** np.arange(n_days) for i, g in enumerate(growth)}, index=idx)
    O = C.shift(1).fillna(C.iloc[0])          # open = previous close (no gaps)
    elig = pd.DataFrame(True, index=idx, columns=C.columns)
    mkt = pd.DataFrame({"rf": 0.0, "on": 1.0, "spy": 0.0}, index=idx)
    return {"C": C, "O": O, "elig": elig}, mkt


def test_holds_strongest_and_pays_costs_once():
    M, mkt = _setup()
    S = M["C"] / M["C"].shift(20) - 1
    start, end = M["C"].index[30], M["C"].index[-1]
    bt = mom.backtest(M, S, 1, False, mkt, start, end)
    eq = (1 + bt["ret"]).prod()
    i0, i1 = 30, len(M["C"]) - 1
    # buys S0 at the open of day i0+1 (= close of i0), holds to the end: one buy, never rotated
    expect = (M["C"]["S0"].iloc[i1] / M["C"]["S0"].iloc[i0]) * (1 - mom.COST - mom.SLIP)
    assert np.isclose(eq, expect, rtol=1e-9)
    assert len(bt["positions"]) == 1


def test_filter_off_keeps_cash_at_tbill_rate():
    M, mkt = _setup()
    mkt["on"] = 0.0
    mkt["rf"] = 0.0001
    S = M["C"] / M["C"].shift(20) - 1
    bt = mom.backtest(M, S, 2, True, mkt, M["C"].index[30], M["C"].index[-1])
    days = len(bt["ret"]) - 1
    assert np.isclose((1 + bt["ret"]).prod(), 1.0001 ** days)
    assert bt["positions"] == []


def test_rotation_when_leader_changes():
    idx = pd.bdate_range("2020-01-01", periods=200)
    a = np.r_[10 * 1.01 ** np.arange(100), 10 * 1.01 ** 99 * 0.99 ** np.arange(1, 101)]
    b = 10 * 1.001 ** np.arange(200)
    C = pd.DataFrame({"A": a, "B": b}, index=idx)
    M = {"C": C, "O": C.shift(1).fillna(C.iloc[0]), "elig": pd.DataFrame(True, index=idx, columns=C.columns)}
    mkt = pd.DataFrame({"rf": 0.0, "on": 1.0, "spy": 0.0}, index=idx)
    bt = mom.backtest(M, C / C.shift(5) - 1, 1, False, mkt, idx[20], idx[-1])
    names = [j for j, _ in bt["positions"]]
    assert names[0] == 0 and 1 in names     # starts in A, rotates to B after A turns down
