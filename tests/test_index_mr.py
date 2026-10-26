"""Mechanics of the index mean-reversion simulator: next-open fills, costs, one position at a time."""
import numpy as np
import pandas as pd

from indicator_lab.meanrev import index_mr as M


def _df():
    idx = pd.bdate_range("2020-01-01", periods=8)
    o = np.array([100, 101, 99, 98, 100, 103, 104, 105], float)
    c = np.array([101, 100, 98, 99, 102, 104, 103, 106], float)
    return pd.DataFrame({"open": o, "high": c + 1, "low": o - 1, "close": c}, index=idx)


def test_next_open_fills_and_trade_return():
    d = _df()
    entry = np.zeros(8, bool)
    exit_ = np.zeros(8, bool)
    entry[2] = True          # signal on the close of bar 2 -> buy at the open of bar 3 (98)
    entry[3] = True          # ignored while in a position
    exit_[4] = True          # exit signal on bar 4 -> sell at the open of bar 5 (103)
    rf = np.zeros(8)
    r, tr, held = M.simulate(d, entry, exit_, rf, 0, 7)
    assert len(tr) == 1
    assert np.isclose(tr[0], 103 * (1 - M.COST) / (98 * (1 + M.COST)) - 1)
    assert np.isclose(r[3], 99 / 98 - 1 - M.COST)
    assert np.isclose(r[4], 102 / 99 - 1)
    assert np.isclose(r[5], 103 / 102 - 1 - M.COST)
    assert list(held) == [False, False, False, True, True, True, False, False]
    eq = np.prod(1 + r)
    assert np.isclose(eq, (103 / 98) * (1 - M.COST) ** 2, rtol=1e-3)


def test_exit_and_entry_same_bar_keeps_position():
    d = _df()
    entry = np.zeros(8, bool)
    exit_ = np.zeros(8, bool)
    entry[1] = True
    exit_[3] = True
    entry[3] = True          # new signal on the exit bar: stay in, no round trip
    exit_[5] = True
    _, tr, held = M.simulate(d, entry, exit_, np.zeros(8), 0, 7)
    assert len(tr) == 1 and held[2:7].all()
