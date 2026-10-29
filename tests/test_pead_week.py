"""Exit families of the post-earnings gap study (indicator_lab/week/pead_week.exit_sim)."""
import numpy as np

from indicator_lab.week import pead_week as P

BUY = 100.02 * 1.0005


def _net(px):
    return (px - 0.02) * 0.9995


def test_a_breakeven_after_1r_then_ema_exit_next_open():
    o = np.array([100, 100, 103, 106, 104, 101.0])
    h = np.array([100, 101, 106, 107, 105, 102.0])
    lo = np.array([100, 99, 102, 104, 101, 100.0])
    c = np.array([100, 100.5, 105, 106, 101.5, 101.0])
    e20 = np.array([90, 90, 90, 90, 103, 103.0])           # close 101.5 < 103 on bar 4 -> sell at the open of bar 5
    a = np.full(6, 2.0)
    r, bars = P.exit_sim(o, h, lo, c, e20, a, 1, 100.0, 95.0, 0, 40)   # R = 5, +1R = 105 hit on bar 2
    assert bars == 5 and np.isclose(r, _net(101.0) / BUY - 1)


def test_a_3atr_chandelier():
    o = np.array([100, 100, 110, 112, 106.0])
    h = np.array([100, 105, 115, 113, 107.0])
    lo = np.array([100, 99, 109, 108, 100.0])
    c = np.array([100, 104, 114, 110, 101.0])
    a = np.full(5, 2.0)
    r, bars = P.exit_sim(o, h, lo, c, c * 0, a, 1, 100.0, 95.0, 1, 40)  # chandelier 115 - 6 = 109 from bar 3
    assert bars == 3 and np.isclose(r, _net(109.0) / BUY - 1)


def test_b_half_at_10_rest_at_20():
    o = np.array([100, 100, 108, 115.0])
    h = np.array([100, 104, 111, 121.0])
    lo = np.array([100, 99, 107, 114.0])
    c = np.array([100, 103, 110, 120.0])
    r, bars = P.exit_sim(o, h, lo, c, c * 0, np.full(4, 2.0), 1, 100.0, 95.0, 2, 40)
    assert bars == 3 and np.isclose(r, (0.5 * _net(110.0) + 0.5 * _net(120.0)) / BUY - 1)


def test_time_exit():
    n = 30
    o = np.full(n, 100.0)
    r, bars = P.exit_sim(o, o + 1, o - 1, o + 0.5, o - 10, np.full(n, 2.0), 1, 100.0, 95.0, 0, 10)
    assert bars == 10 and np.isclose(r, _net(100.5) / BUY - 1)
