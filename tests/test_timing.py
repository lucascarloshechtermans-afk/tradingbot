"""Mechanics of the index regime-timing simulation."""
import numpy as np
import pandas as pd

from indicator_lab.timing import regime as R


def test_hysteresis_band():
    enter = np.array([0, 1, 0, 0, 0, 1, 0], bool)
    leave = np.array([1, 0, 0, 1, 0, 0, 1], bool)
    assert list(R.hysteresis(enter, leave)) == [0, 1, 1, 0, 0, 1, 0]


def test_monthly_hold_only_changes_at_month_end():
    idx = pd.bdate_range("2021-01-25", "2021-03-05")
    me = R.month_end(idx)
    assert list(idx[me]) == [pd.Timestamp("2021-01-29"), pd.Timestamp("2021-02-26")]
    sig = np.ones(len(idx), bool)
    w = R.monthly_hold(sig, me)
    assert w[: int(np.argmax(me))].sum() == 0 and w[int(np.argmax(me)):].min() == 1


def test_simulate_one_day_delay_and_cost():
    idx = pd.bdate_range("2021-01-01", periods=6)
    c = pd.Series([100, 101, 102, 103, 104, 105], index=idx, dtype=float)
    rf = pd.Series(0.0, index=idx)
    w = np.array([1, 1, 1, 1, 1, 1], float)            # decided long at every close
    r = R.simulate(c, rf, w)
    assert r.iloc[0] == 0 and r.iloc[1] == 0             # nothing earned before the trade at close of day 1
    assert np.isclose(r.iloc[2], 102 / 101 - 1 - R.COST)  # first earned day pays the entry cost
    assert np.isclose(r.iloc[3], 103 / 102 - 1)
