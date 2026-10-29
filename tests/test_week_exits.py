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


def test_variant_no_partial_runs_to_target():
    o, h, lo, c = _bars([100, 100, 105, 112], [100, 104, 111, 121], [100, 99, 104, 111], [100, 103, 110, 120])
    tr = B.trade(o, h, lo, c, 0, "open", np.nan, 95.0, 2.0, np.nan, partial=False)
    assert not tr["half"] and tr["reason"] == "target"
    assert np.isclose(tr["ret"], 120 * K / (100 * (1 + B.COST)) - 1)


def test_variant_hold_5_and_wider_stop():
    n = 14
    o = np.full(n, 100.0)
    tr = B.trade(o, o + 1, o - 1, o + 0.5, 0, "open", np.nan, 99.5, 2.0, np.nan, hold=5)
    assert tr["hold"] == 5 and tr["reason"] == "tijdstop"
    tr2 = B.trade(o, o + 1, o - 1, o + 0.5, 0, "open", np.nan, 99.5, 2.0, np.nan, min_atr=1.5)
    assert np.isclose(tr2["risk"], 0.03)                     # stop = 100 - 1.5 x 2


def test_variant_fixed_small_target():
    o, h, lo, c = _bars([100, 100, 101], [100, 104, 103], [100, 99, 100], [100, 103, 102])
    tr = B.trade(o, h, lo, c, 0, "open", np.nan, 95.0, 2.0, np.nan, tgt=0.03)
    assert tr["reason"] == "target" and tr["exit_i"] == 1
    assert np.isclose(tr["ret"], 103 * K / (100 * (1 + B.COST)) - 1)


def test_step1_outcome_fixed_target_costs_and_gaps():
    from indicator_lab.week import mfe as M
    o = np.array([100.0, 100.0, 104.5, 101.0])
    h = np.array([100.0, 102.0, 105.0, 102.0])
    lo = np.array([100.0, 99.5, 104.0, 100.0])
    c = np.array([100.0, 101.0, 104.8, 101.0])
    px, bars, kind, _, _ = M.outcome(o, h, lo, c, 1, 100.0, 95.0, 103.0, 10)
    assert kind == 1 and bars == 2 and px == 104.5           # gap over the target fills at the open
    assert np.isclose(M.net(100.0, 103.0), (103 - 0.02) * (1 - 0.0005) / (100.02 * 1.0005) - 1)
    px, bars, kind, _, _ = M.outcome(o, h, lo, c, 1, 100.0, 99.6, 103.0, 10)
    assert kind == 0 and bars == 1 and px == 99.6            # stop first on the entry bar


def test_step3_partial_then_breakeven_and_cap():
    from indicator_lab.week import variants as V
    buy = 100.02 * 1.0005
    o = np.array([100.0, 100.0, 104.0, 103.0, 99.0])
    h = np.array([100.0, 101.0, 106.0, 104.0, 100.0])
    lo = np.array([100.0, 99.0, 103.0, 101.0, 98.0])
    c = np.array([100.0, 100.5, 105.5, 102.0, 99.0])
    e10 = np.full(5, 90.0)
    a = np.full(5, 2.0)
    r, bars, hit = V.run_exit(o, h, lo, c, e10, a, 1, 100.0, 95.0, 105.0, 0.5, 3, 10)
    assert hit and bars == 4                                         # half at 105, rest stopped at break-even (open 99)
    assert np.isclose(r, (0.5 * (105 - 0.02) * 0.9995 + 0.5 * (99 - 0.02) * 0.9995) / buy - 1)
    h2 = h.copy()
    h2[2] = 115.0                                                    # rest capped at +10%
    r2, _, _ = V.run_exit(o, h2, lo, c, e10, a, 1, 100.0, 95.0, 105.0, 0.5, 3, 10)
    assert np.isclose(r2, (0.5 * (105 - 0.02) * 0.9995 + 0.5 * (110 - 0.02) * 0.9995) / buy - 1)
