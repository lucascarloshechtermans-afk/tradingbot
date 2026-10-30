import numpy as np
import pandas as pd

from tracking.forward_log import append_signals, evaluate_breakout, evaluate_momentum, read_log, summary


def _daily(closes, opens=None, lows=None):
    idx = pd.bdate_range("2026-06-01", periods=len(closes), tz="UTC")
    c = pd.Series(closes, index=idx, dtype=float)
    o = pd.Series(opens if opens is not None else c.shift(1).fillna(c.iloc[0]), index=idx, dtype=float)
    lo = pd.Series(lows if lows is not None else np.minimum(o, c) * 0.99, index=idx, dtype=float)
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.01, "low": lo, "close": c})


def test_append_is_idempotent(tmp_path):
    path = str(tmp_path / "log.csv")
    row = {"system": "BREAKOUT", "signal_date": pd.Timestamp("2026-09-29"), "ticker": "MRNA", "close": 203.46,
           "level": 198.88, "atr": 13.1, "note": "leader #3"}
    assert append_signals([row], path) == 1
    assert append_signals([row], path) == 0
    assert len(read_log(path)) == 1


def test_breakout_stop_trailing_and_open():
    closes = list(np.linspace(100, 130, 40))
    d = _daily(closes)
    sig = d.index[25]
    res = evaluate_breakout("X", d, sig, atr=2.0)
    assert res.status == "OPEN" and res.r > 0 and res.entry == d["open"].iloc[26]
    # a crash through the stop on the day after entry
    crash = closes[:27] + [closes[26] - 20] * 3
    res2 = evaluate_breakout("X", _daily(crash), d.index[25], atr=2.0)
    assert res2.status == "CLOSED" and res2.reason == "stop" and res2.r <= -1.0
    # a slow roll-over below the 20-day low -> trailing exit at the next open
    roll = closes[:30] + list(np.linspace(129, 110, 20))
    res3 = evaluate_breakout("X", _daily(roll, lows=np.array(roll) * 0.999), d.index[25], atr=20.0)
    assert res3.status == "CLOSED" and res3.reason == "trailing exit"
    assert evaluate_breakout("X", d, d.index[-1], atr=2.0).status == "WAIT"


def test_momentum_and_summary():
    idx = pd.bdate_range("2026-08-03", "2026-09-29")
    closes = pd.DataFrame({"A": np.linspace(10, 12, len(idx)), "B": np.linspace(10, 11, len(idx))}, index=idx)
    spy = pd.Series(np.linspace(100, 101, len(idx)), index=idx)
    log = pd.DataFrame({"system": ["MOMENTUM", "MOMENTUM"], "signal_date": [pd.Timestamp("2026-08-31")] * 2,
                        "ticker": ["A", "B"], "note": ["invested", "invested"]})
    m = evaluate_momentum(log, closes, spy)
    assert len(m) == 1 and m.book_pct.iloc[0] > m.spy_pct.iloc[0] > 0
    s = summary([])
    assert s["signals"] == 0 and s["avg_r"] is None
