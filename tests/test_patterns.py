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


def test_setup_finder_skips_patterns_that_failed_out_of_sample():
    # flat base / horizontal range broke out here, but both failed the
    # out-of-sample test, so the finder must not list them
    assert evaluate_ticker("TEST", _range_then(103.0), momentum_rank=90.0) is None


def test_score_rewards_4h_200_ema_and_penalises_below_it():
    from analysis.setup_finder import score_setup

    df = _range_then(103.0)
    hit = next(h for h in detect_patterns(df) if h.broke_out_today)
    hit.name = "bull flag"  # score it as a pattern that held up out-of-sample
    above = score_setup(df, "BREAKOUT TODAY", hit, [hit], None, 1.5, ema200_4h=95.0)
    below = score_setup(df, "BREAKOUT TODAY", hit, [hit], None, 1.5, ema200_4h=110.0)
    none = score_setup(df, "BREAKOUT TODAY", hit, [hit], None, 1.5, ema200_4h=None)
    assert above[0] > none[0] > below[0]
    stop, target, rr = above[2], above[3], above[4]
    assert stop < hit.trigger < target and rr >= 1.99
