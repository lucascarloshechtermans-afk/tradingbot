import numpy as np
import pandas as pd

from indicator_lab.week import exit_test as X


def _bars(closes, spread=0.5):
    c = np.asarray(closes, float)
    return c.copy(), c + spread, c - spread, c, np.full(len(c), 1.0)


def test_path_target_and_time_exit():
    o, h, lo, c, a = _bars([100, 101, 105, 112, 111])
    # target 110 is reached on bar 3 (high 112.5): exit at max(open, target) = 112 (gap above the target)
    assert X.path(o, h, lo, c, a, 1, 101.0, 90.0, 110.0, 10, 0.0) == (3, 112.0)
    # no target: time exit at the close of the last bar of the holding period (bars 1..3)
    assert X.path(o, h, lo, c, a, 1, 101.0, 90.0, 0.0, 3, 0.0) == (3, 112.0)


def test_path_trailing_stop_follows_the_highest_close():
    o, h, lo, c, a = _bars([100, 100, 110, 120, 116, 114])
    # trail 2 x ATR(1) = 2 below the highest close: after the 120 close the stop is 118; bar 4 (low 115.5) hits it
    # and opens at 116 below the stop -> fills at the open
    xi, px = X.path(o, h, lo, c, a, 1, 100.0, 95.0, 0.0, 60, 2.0)
    assert (xi, px) == (4, 116.0)


def test_simulate_keeps_at_most_three_positions():
    days = pd.bdate_range("2024-01-01", periods=30)
    arrs, cand = {}, {}
    for k in range(6):
        t = f"T{k}"
        c = np.linspace(100, 101, 30)
        arrs[t] = {"idx": days, "o": c, "h": c + 0.1, "l": c - 0.1, "c": c, "atr": np.full(30, 1.0),
                   "sup_lo": np.full(30, 90.0)}
        cand.setdefault(days[1], []).append((t, 0, "open", np.nan, 90.0))
    wk = pd.Series(days.to_period("W-FRI"), index=days)
    week_last = wk.groupby(wk).apply(lambda s: s.index[-1])
    eq, trades = X.simulate(arrs, days, cand, "b", wk, week_last, np.random.default_rng(0), {})
    assert len(trades) == 3                     # 6 signals on one day, 3 slots
    assert abs(eq.iloc[0] - 1.0) < 1e-12        # nothing invested before the entry day
    assert 0.98 < eq.iloc[-1] < 1.02            # flat prices: only costs


def test_path_half_sells_half_at_5_and_rest_at_10():
    o, h, lo, c, a = _bars([100, 100, 104, 106, 111])
    # bar 3: high 106.5 >= 105 -> half at max(open 106, 105) = 106; bar 4: high 111.5 >= 110 -> rest at 111 (gap)
    xi, px, pi, pp = X.path_half(o, h, lo, c, 1, 100.0, 92.0, 105.0, 110.0, 20)
    assert (xi, px, pi, pp) == (4, 111.0, 3, 106.0)


def test_simulate_books_the_half_exit():
    days = pd.bdate_range("2024-01-01", periods=30)
    c = np.r_[np.full(5, 100.0), np.full(25, 106.0)]       # +6%: only the first target is reached
    arrs = {"T0": {"idx": days, "o": c, "h": c + 0.1, "l": c - 0.1, "c": c, "atr": np.full(30, 1.0),
                   "sup_lo": np.full(30, 90.0)}}
    cand = {days[1]: [("T0", 0, "open", np.nan, 90.0)]}
    wk = pd.Series(days.to_period("W-FRI"), index=days)
    week_last = wk.groupby(wk).apply(lambda s: s.index[-1])
    eq, trades = X.simulate(arrs, days, cand, "e", wk, week_last, np.random.default_rng(0), {})
    tr = trades[0]
    assert tr["hit"] and not tr["hit10"]
    # 1/3 of the account in the trade: final equity = 1 + (1/3) x the trade's blended net return
    assert abs(eq.iloc[-1] - (1 + tr["ret"] / 3)) < 1e-9
