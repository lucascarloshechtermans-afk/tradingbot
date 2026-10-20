import numpy as np
import pandas as pd

from indicator_lab.engine import ExitRules, simulate


def _df(o, h, lo, c):
    idx = pd.bdate_range("2020-01-01", periods=len(c))
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": 1}, index=idx)


def test_signal_fills_next_open_and_exits_next_open_with_costs():
    df = _df([10, 10, 11, 12, 13], [10, 11, 12, 13, 14], [10, 10, 11, 12, 13], [10, 11, 12, 13, 14])
    entry = np.array([True, False, False, False, False])
    exit_sig = np.array([False, False, True, False, False])
    r, trades = simulate(df, entry, exit_sig, np.ones(5), ExitRules(), cost=0.001)
    assert len(trades) == 1
    t = trades[0]
    assert t["entry"] == 10 and t["exit"] == 12  # entered bar1 open, exited bar3 open
    assert np.isclose(t["ret"], 12 * 0.999 / (10 * 1.001) - 1)
    assert r[0] == 0.0  # no exposure on the signal bar itself
    assert np.isclose(np.prod(1 + r) - 1, t["ret"])


def test_gap_through_stop_fills_at_open_not_stop():
    df = _df([10, 10, 7, 7], [10, 10.5, 7.5, 7.5], [10, 9.8, 6.5, 6.5], [10, 10, 7, 7])
    entry = np.array([True, False, False, False])
    r, trades = simulate(df, entry, None, np.ones(4), ExitRules(stop_atr=1.0), cost=0.0)
    assert trades[0]["reason"] == "stop" and trades[0]["exit"] == 7  # opened below the 9.0 stop


def test_stop_beats_target_when_both_inside_one_bar():
    df = _df([10, 10, 10], [10, 13, 10], [10, 7, 10], [10, 10, 10])
    entry = np.array([True, False, False])
    _, trades = simulate(df, entry, None, np.ones(3), ExitRules(stop_atr=1.0, tgt_atr=1.0), cost=0.0)
    assert trades[0]["reason"] == "stop" and trades[0]["exit"] == 9
