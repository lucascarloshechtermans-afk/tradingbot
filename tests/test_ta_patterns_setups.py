import numpy as np

from ta.core import compute_indicators
from ta.engine import analyze
from ta.frame import analyze_frame
from ta.patterns import find_patterns, rounded_bottom
from ta.scoring import DEFAULT_WEIGHTS
from ta.setups import classify
from tests.ta_helpers import frame, zigzag


def test_double_top_found_on_the_mirrored_chart():
    closes = list(np.linspace(80, 100, 60)) + zigzag(100, [20, -10, 10, -12], 10)[1:]
    df = frame(closes, spread=0.003)
    ps = find_patterns(df, compute_indicators(df)["atr"], [], 1, True)
    dt = next(p for p in ps if p.name == "double top")
    assert dt.direction == "bear" and dt.status in ("breakout", "confirmed")
    assert 108 < dt.trigger < 111 and dt.invalidation > dt.trigger


def test_rounded_bottom_rule():
    x = np.linspace(-1, 1, 150)
    closes = list(np.linspace(140, 130, 40)) + list(100 + 30 * x ** 2) + [131, 132]
    rb = rounded_bottom(frame(closes, spread=0.003))
    assert rb is not None and abs(rb["trigger"] - 130.4) < 1.5
    assert rounded_bottom(frame(list(np.linspace(100, 160, 200)))) is None   # a straight line is no bowl


def _box(extra_closes, extra_vol):
    """Uptrend, then a 100-110 box tested 4x at the top, then the given closes."""
    closes = list(np.linspace(60, 100, 120)) + zigzag(100, [10, -9, 9, -9, 9, -9, 9, -4], 6)[1:] + list(extra_closes)
    vol = [1e6] * (len(closes) - len(extra_vol)) + list(extra_vol)
    return frame(closes, vol=vol, spread=0.004)


def _breakout(df):
    fa = analyze_frame(df, "daily")
    return next((s for s in classify(fa) if s.kind == "confirmed_breakout"), None), fa


def test_breakout_is_never_confirmed_on_the_trigger_bar():
    s, _ = _breakout(_box([113], [1e6]))
    assert s is not None and s.status == "triggered"
    s2, _ = _breakout(_box([113, 114], [1e6, 1e6]))
    assert s2.status == "confirmed"           # second close above the level
    s3, _ = _breakout(_box([113.5], [3e6]))   # one close with a volume thrust: evidence, still not confirmed
    assert s3.status == "triggered" and any("volume-uitbraak" in e for e in s3.evidence)


def test_failed_breakout_when_price_closes_back_inside():
    df = _box([113, 108], [1e6, 1e6])
    fa = analyze_frame(df, "daily")
    kinds = {s.kind: s for s in classify(fa)}
    assert "confirmed_breakout" not in kinds or kinds["confirmed_breakout"].status != "confirmed"
    fb = kinds.get("failed_breakout")
    if fb is not None:   # a failed long is reported as a short with SHORT-side levels
        assert fb.direction == -1 and fb.invalidation_price > df["close"].iloc[-1]
        assert "boven" in fb.invalidation and not any("momentum bevestigt (" in e for e in fb.evidence)


def test_score_is_explained_and_correlated_oscillators_count_once():
    df = _box([113, 114], [1e6, 3e6])
    rep = analyze("TEST", df)
    sc = rep.score
    used = [c for c in sc.contributions if c.sub is not None]
    assert abs(sum(c.points for c in used) - sc.total) < 0.5
    assert abs(sum(c.weight for c in used) - 100) < 0.5
    assert {c.family for c in sc.contributions} == set(DEFAULT_WEIGHTS)   # one momentum family, not rsi/macd/roc
    assert all(c.why for c in sc.contributions)
    df_nov = df.copy()
    df_nov["volume"] = 0.0
    rep2 = analyze("TEST", df_nov)
    vol = next(c for c in rep2.score.contributions if c.family == "volume")
    assert vol.sub is None and "weggelaten" in vol.why
    assert abs(sum(c.weight for c in rep2.score.contributions if c.sub is not None) - 100) < 0.5


def test_engine_handles_short_and_missing_data():
    rep = analyze("TINY", frame(list(np.linspace(10, 12, 50))))
    assert rep.primary is None and rep.setups == [] and "te weinig" in rep.notes[0]


def test_no_setup_is_confirmed_on_its_trigger_bar_and_levels_sit_on_the_right_side():
    """Walk synthetic series bar by bar: a setup never jumps from 'developing' straight
    to 'confirmed' (that would be confirmation on the trigger bar), and a live setup's
    invalidation lies on the losing side of the close."""
    from tests.ta_helpers import uptrend
    rng = np.random.default_rng(7)
    series = [uptrend(330, seed=1), list(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 330))))]
    for closes in series:
        df = frame(closes, spread=0.006, vol=list(rng.uniform(0.5e6, 2e6, len(closes))))
        prev: dict = {}
        for k in range(200, len(df)):
            cur = {}
            for st in classify(analyze_frame(df.iloc[:k + 1], "daily")):
                key = (st.kind, st.direction)
                cur[key] = st.status
                # zone setups are exempt: zones are re-scored every bar, so a candle that was already
                # confirmed by a later bar can become 'at a zone' only now (not a trigger-bar confirmation)
                if st.status == "confirmed" and st.kind not in ("support_bounce", "resistance_rejection"):
                    assert prev.get(key) != "developing", (k, key)
                if st.status in ("triggered", "confirmed") and st.invalidation_price is not None and \
                        np.isfinite(st.invalidation_price):
                    c = df["close"].iloc[k]
                    assert (st.invalidation_price <= c) if st.direction > 0 else (st.invalidation_price >= c), (k, key, st.invalidation)
            prev = cur
