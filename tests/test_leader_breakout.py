import numpy as np
import pandas as pd

from analysis.leader_breakout import LeaderBreakout, find_leader_breakouts, prioritize_breakouts


def _panel(n_days=320, n=60, seed=3):
    idx = pd.bdate_range(end="2026-09-28", periods=n_days)
    rng = np.random.default_rng(seed)
    c = pd.DataFrame({f"T{i:02d}": 50 * np.exp(np.cumsum(rng.normal(0.0001 * i, 0.01, n_days))) for i in range(n)}, index=idx)
    v = pd.DataFrame(1e6, index=idx, columns=c.columns)
    return c, v


def test_breakout_found_only_on_the_first_close_above_the_50d_high_in_a_leader():
    c, v = _panel()
    lead = c["T59"].to_numpy().copy()
    lead[-60:-1] = lead[-60]            # flat base for 59 sessions
    lead[-1] = lead[-60] * 1.05         # today: breaks the 50-day closing high
    c["T59"] = lead
    c.loc[c.index[:-60], "T59"] = np.linspace(20, lead[-60], len(c) - 60)  # strong 12-month run-up -> leader
    spy = pd.Series(np.linspace(100, 200, len(c)), index=c.index)
    outs, near, bull = find_leader_breakouts(c, v, spy)
    assert bull
    b = next(x for x in outs if x.ticker == "T59")
    assert b.close > b.breakout_level and b.exit_level <= b.close and not b.near
    # the day after (another higher close) is not a new signal
    c2 = pd.concat([c, pd.DataFrame([c.iloc[-1] * 1.01], index=[c.index[-1] + pd.offsets.BDay(1)])])
    v2 = pd.concat([v, v.iloc[[-1]].set_axis([c2.index[-1]])])
    outs2, _, _ = find_leader_breakouts(c2, v2, spy.reindex(c2.index).ffill())
    assert all(x.ticker != "T59" for x in outs2)


def test_near_list_and_priority():
    items = [(LeaderBreakout("A", None, 100, 101, 7, 50.0, 90), None), (LeaderBreakout("B", None, 100, 102, 2, 80.0, 90), None),
             (LeaderBreakout("C", None, 100, 101, 1, 90.0, 90), None)]
    out = prioritize_breakouts(items, momentum_tickers={"C"})
    assert [b.ticker for b, _ in out] == ["B", "A", "C"]
    assert [b.action for b, _ in out] == ["NEEM", "NEEM", "OVERLAP"]
    assert out[0][0].score == 98  # rank 2 of 50
