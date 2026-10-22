"""Fill rules of the swing v4 simulator on hand-made bars (no market data needed)."""
import numpy as np
import pandas as pd

from indicator_lab.swing4.sim2 import Policy, simulate

COST = 0.001


def bars(rows, atr=1.0):
    o, h, lo, c = (np.array(x, float) for x in zip(*rows))
    n = len(o)
    return {"o": o, "h": h, "l": lo, "c": c, "atr": np.full(n, atr), "exit_sig": np.zeros(n, bool),
            "index": pd.date_range("2020-01-01", periods=n, freq="B"), "sma50": np.full(n, 0.0),
            "rsi14": np.full(n, 50.0), "hi_n": np.full(n, 100.0)}


def entry_at(n, i=0):
    e = np.zeros(n, bool)
    e[i] = True
    return e


def net(entry, px):
    return px * (1 - COST) / (entry * (1 + COST)) - 1


def test_stop_wins_when_stop_and_target_touch_the_same_bar():
    # signal bar 0, fill at 100 on bar 1; R = 4. After bar 1 the trail is 101 - 4 = 97. Bar 2 touches both
    # +1R (104) and that stop.
    a = bars([(99, 100, 98, 100), (100, 101, 99, 100), (100, 105, 95, 100), (100, 100, 100, 100)])
    _, tr = simulate(a, entry_at(4), Policy(target=1.0))
    assert tr[0]["reason"] == "stop" and abs(tr[0]["ret"] - net(100, 97)) < 1e-12


def test_gap_beyond_target_fills_at_the_open():
    a = bars([(99, 100, 98, 100), (100, 101, 99, 100), (110, 111, 109, 110), (110, 110, 110, 110)])
    _, tr = simulate(a, entry_at(4), Policy(target=1.0))
    assert tr[0]["reason"] == "target" and abs(tr[0]["ret"] - net(100, 110)) < 1e-12


def test_gap_through_stop_fills_at_the_open():
    a = bars([(99, 100, 98, 100), (100, 101, 99, 100), (90, 91, 89, 90), (90, 90, 90, 90)])
    _, tr = simulate(a, entry_at(4), Policy())
    assert tr[0]["reason"] == "stop" and abs(tr[0]["ret"] - net(100, 90)) < 1e-12


def test_partial_then_rest_and_daily_returns_compound_to_the_trade_return():
    # half out at +1R (104), the rest stopped by break-even (entry + costs) two bars later (wide trail, so the
    # break-even stop is the binding one)
    a = bars([(99, 100, 98, 100), (100, 101, 99, 100), (101, 104.5, 100.5, 103), (103, 103.5, 101.5, 102),
              (101, 101, 99, 100), (100, 100, 100, 100)])
    ret, tr = simulate(a, entry_at(6), Policy(trail=10.0, partial=((1.0, 0.5),), be_at=1.0))
    be = 100 * (1 + COST) / (1 - COST)
    q0 = 1 / (100 * (1 + COST))
    expect = 0.5 * q0 * 104 * (1 - COST) + 0.5 * q0 * be * (1 - COST) - 1
    assert tr[0]["parts_hit"] == 1 and abs(tr[0]["ret"] - expect) < 1e-12
    assert abs(np.prod(1 + ret) - 1 - tr[0]["ret"]) < 1e-12


def test_time_stop_exits_at_the_next_open_without_progress():
    rows = [(99, 100, 98, 100)] + [(100, 101, 99.5, 100)] * 6 + [(100.5, 101, 100, 100.5)]
    a = bars(rows)
    _, tr = simulate(a, entry_at(len(rows)), Policy(time_n=3))
    assert tr[0]["reason"] == "time" and tr[0]["exit_i"] == 1 + 3 + 1


def test_buy_stop_entry_only_fills_above_the_signal_high_and_expires():
    a = bars([(99, 100, 98, 100), (99.5, 99.9, 99, 99.5), (99.5, 99.8, 99, 99.6), (99, 101, 99, 100.5)])
    _, tr = simulate(a, entry_at(4), Policy(entry="stop", e_days=1))
    assert tr == []
    _, tr = simulate(a, entry_at(4), Policy(entry="stop", e_days=3))
    assert len(tr) == 0 or tr[0]["entry"] == 100.0
