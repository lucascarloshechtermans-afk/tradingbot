import numpy as np
import pandas as pd

from analysis.patterns import detect_patterns
from analysis.setup_finder import evaluate_ticker


def _frame(close: np.ndarray, wick: float = 0.004) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-01", periods=len(close), tz="UTC")
    c = pd.Series(close, index=idx)
    o = c.shift(1).fillna(c.iloc[0])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * (1 + wick), "low": np.minimum(o, c) * (1 - wick),
                         "close": c, "volume": 1e6})


def _range_then(breakout: float) -> pd.DataFrame:
    trend = np.linspace(40, 100, 250)
    t = np.arange(40)
    rng = 97 + 3 * np.sin(t / 2.2)                 # sideways 94-100 with repeated tops near 100
    return _frame(np.concatenate([trend, rng, [breakout]]))


def test_flat_base_breakout_today_is_detected():
    hits = {h.name: h for h in detect_patterns(_range_then(103.0))}
    assert "flat base" in hits or "horizontal range" in hits
    hit = hits.get("flat base") or hits["horizontal range"]
    assert hit.broke_out_today
    assert hit.invalidation < hit.trigger < 103.0 < hit.target


def test_no_breakout_when_the_last_close_stays_inside():
    hits = detect_patterns(_range_then(98.0))
    assert hits and not any(h.broke_out_today for h in hits)


def test_setup_finder_ranks_a_fresh_breakout():
    df = _range_then(103.0)
    df.loc[df.index[-1], "volume"] = 3e6
    s = evaluate_ticker("TEST", df, momentum_rank=90.0)
    assert s is not None and s.status == "BREAKOUT TODAY"
    assert s.stop < s.trigger < s.target and s.rr >= 1.99
    assert any("momentum rank" in r for r in s.reasons)
