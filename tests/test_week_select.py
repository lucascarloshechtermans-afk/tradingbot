"""Filters as toggles and one open position per stock in the one-week study (indicator_lab/week/run.select)."""
import numpy as np
import pandas as pd

from indicator_lab.week import run as W


def _z(t, sig, ent, ex, **flags):
    base = {"strategy": 1, "ticker": t, "signal": pd.Timestamp(sig), "entry": pd.Timestamp(ent), "exit": pd.Timestamp(ex),
            "regime": True, "room10": True, "rs_top20": True, "vol_surge": True}
    base.update(flags)
    return base


def test_one_position_per_stock_and_filters():
    c = [_z("A", "2020-01-02", "2020-01-03", "2020-01-10"),
         _z("A", "2020-01-06", "2020-01-07", "2020-01-14"),            # overlaps the first A trade: skipped
         _z("A", "2020-01-10", "2020-01-13", "2020-01-20"),            # entry after the first exit: taken
         _z("B", "2020-01-02", "2020-01-03", "2020-01-08", regime=False)]
    assert [z["entry"].day for z in W.select(c, 1, (), None)] == [3, 3, 13]
    assert [z["ticker"] for z in W.select(c, 1, ("regime",), None)] == ["A", "A"]


def test_no_earnings_filter():
    c = [_z("A", "2020-01-02", "2020-01-03", "2020-01-10"), _z("B", "2020-01-02", "2020-01-03", "2020-01-10"),
         _z("C", "2020-01-02", "2020-01-03", "2020-01-10")]
    earn = {"A": np.array(["2020-01-08"], dtype="datetime64[ns]"), "B": np.array(["2020-02-08"], dtype="datetime64[ns]")}
    assert [z["ticker"] for z in W.select(c, 1, ("no_earnings",), earn)] == ["B"]   # A has a report inside, C unknown
