"""Standard exits of the one-week study (indicator_lab/week/build.trade): stop, +10% half, break-even, +20%, time stop."""
import numpy as np

from indicator_lab.week import build as B

K = 1 - B.COST


def _bars(path_o, path_h, path_l, path_c):
    return (np.array(path_o, float), np.array(path_h, float), np.array(path_l, float), np.array(path_c, float))


def test_stop_hit():
    o, h, lo, c = _bars([100, 100, 99], [101, 101, 100], [99, 99, 90], [100, 100, 91])
    tr = B.trade(o, h, lo, c, 0, "open", np.nan, 95.0, 2.0, np.nan)      # fill 100 at bar 1, stop = max(92, min(94.5, 98))
    assert tr["reason"] == "stop" and tr["exit_i"] == 2
    assert np.isclose(tr["ret"], 94.5 * K / (100 * (1 + B.COST)) - 1)


def test_half_at_10_then_20():
    o, h, lo, c = _bars([100, 100, 105, 112], [100, 104, 111, 121], [100, 99, 104, 111], [100, 103, 110, 120])
    tr = B.trade(o, h, lo, c, 0, "open", np.nan, 95.0, 2.0, np.nan)
    assert tr["reason"] == "target" and tr["half"] and tr["hit10"] and tr["hit20"]
    assert np.isclose(tr["ret"], (0.5 * 110 * K + 0.5 * 120 * K) / (100 * (1 + B.COST)) - 1)


def test_half_then_breakeven():
    o, h, lo, c = _bars([100, 100, 108, 104], [100, 104, 111, 105], [100, 99, 107, 99], [100, 103, 109, 100])
    tr = B.trade(o, h, lo, c, 0, "open", np.nan, 95.0, 2.0, np.nan)
    assert tr["reason"] == "breakeven"
    assert np.isclose(tr["ret"], (0.5 * 110 * K + 0.5 * 100 * K) / (100 * (1 + B.COST)) - 1)


def test_resistance_caps_second_target():
    o, h, lo, c = _bars([100, 100, 105, 112], [100, 104, 111, 121], [100, 99, 104, 111], [100, 103, 110, 120])
    tr = B.trade(o, h, lo, c, 0, "open", np.nan, 95.0, 2.0, 115.0)      # strong resistance at +15%
    assert np.isclose(tr["ret"], (0.5 * 110 * K + 0.5 * 115 * K) / (100 * (1 + B.COST)) - 1)


def test_time_stop_after_10_days():
    n = 14
    o = np.full(n, 100.0)
    h, lo, c = o + 1, o - 1, o + 0.5
    tr = B.trade(o, h, lo, c, 0, "open", np.nan, 95.0, 2.0, np.nan)
    assert tr["reason"] == "tijdstop" and tr["hold"] == 10 and tr["exit_i"] == 10
    assert np.isclose(tr["ret"], 100.5 * K / (100 * (1 + B.COST)) - 1)
    assert np.isclose(np.prod(1 + tr["daily"]) - 1, tr["ret"])


def test_buy_stop_entry_not_triggered():
    o, h, lo, c = _bars([100, 100, 100], [100, 101, 101], [99, 99, 99], [100, 100, 100])
    assert B.trade(o, h, lo, c, 0, "stop", 105.0, 95.0, 2.0, np.nan) is None


def test_max_risk_8pct():
    o, h, lo, c = _bars([100, 100, 100], [100, 101, 101], [99, 99, 50], [100, 100, 60])
    tr = B.trade(o, h, lo, c, 0, "open", np.nan, 70.0, 2.0, np.nan)      # support far below: stop capped at -8%
    assert np.isclose(tr["risk"], 0.08)
