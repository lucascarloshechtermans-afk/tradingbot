import numpy as np

from ta.core import compute_indicators, normalize
from ta.structure import assess_trend, structure_events
from ta.swings import find_swings, known_swings
from tests.ta_helpers import frame, uptrend, zigzag


def test_indicators_are_causal():
    df = frame(uptrend(320, seed=1), vol=np.linspace(1e6, 2e6, 320))
    full = compute_indicators(df)
    part = compute_indicators(df.iloc[:250])
    for k in ("sma50", "ema21", "rsi7", "rsi14", "rsi21", "macd_hist", "atr", "adx", "bb_upper", "kc_upper",
              "stoch_k", "stochrsi_k", "rvol", "obv", "cmf", "roc20"):
        a, b = full[k].iloc[:250].to_numpy(dtype=float), part[k].to_numpy(dtype=float)
        assert np.allclose(a, b, equal_nan=True), k


def test_missing_volume_is_reported_not_guessed():
    df = frame(uptrend(200)).drop(columns=["volume"])
    ind = compute_indicators(normalize(df))
    assert "rvol" not in ind and "obv" not in ind


def test_swings_are_known_only_after_order_bars_and_labelled():
    df = frame(zigzag(100, [10, -5, 10, -5, 10, -5], 6))
    sw = find_swings(df, 3)
    assert all(s.known_at == s.i + 3 for s in sw)
    highs = [s for s in sw if s.kind == "H"]
    lows = [s for s in sw if s.kind == "L"]
    assert [s.label for s in highs[1:]] == ["HH"] * (len(highs) - 1)
    assert all(s.label == "HL" for s in lows[1:])
    t = highs[-1].i + 2
    assert highs[-1] not in known_swings(sw, t)


def test_bos_then_choch_and_no_lookahead():
    closes = zigzag(100, [10, -5, 10, -5, 10, -20, 5, -8], 6)
    df = frame(closes)
    sw = find_swings(df, 3)
    ev, states = structure_events(df, sw)
    kinds = [(e.kind, e.direction) for e in ev]
    assert ("BOS", "bull") in kinds and ("CHoCH", "bear") in kinds
    assert kinds.index(("CHoCH", "bear")) > kinds.index(("BOS", "bull"))
    # prefix property: events up to bar k do not change when later bars are added
    k = 40
    ev_k, _ = structure_events(df.iloc[:k], find_swings(df.iloc[:k], 3))
    assert [(e.kind, e.i) for e in ev_k] == [(e.kind, e.i) for e in ev if e.i < k]


def test_trend_labels():
    for closes, expect in ((uptrend(320, 2), "strong_uptrend"),
                           (list(400 - np.array(uptrend(320, 3)) + 100), "strong_downtrend")):
        df = frame(closes)
        ind = compute_indicators(df)
        sw = find_swings(df, 3, ind["atr"])
        ev, st = structure_events(df, sw)
        tr = assess_trend(df, ind, sw, ev, st)
        assert tr.label == expect, (tr.label, tr.reasons)
    rng = np.random.default_rng(5)
    flat = list(100 + np.cumsum(rng.normal(0, 0.3, 320)) * 0 + rng.normal(0, 0.6, 320))
    df = frame(flat)
    ind = compute_indicators(df)
    sw = find_swings(df, 3, ind["atr"])
    ev, st = structure_events(df, sw)
    assert assess_trend(df, ind, sw, ev, st).label == "consolidation"


def test_flat_top_swing_is_dated_at_its_first_bar_and_never_moves():
    from ta.swings import find_swings
    highs = [10, 10.5, 11, 11.5, 11, 10.8, 10.9, 11.2, 11.6, 12.0, 12.0, 11.4, 11.2, 11.0, 11.1, 11.3]
    closes = [h - 0.3 for h in highs]
    df = frame(closes, spread=0.0)
    df["high"] = highs
    full = [(s.i, s.known_at) for s in find_swings(df, order=3) if s.kind == "H"]
    assert (9, 12) in full and all(i != 10 for i, _ in full)
    for k in range(8, len(df) + 1):     # every prefix reports a subset of the full list, never a moved swing
        part = {(s.i, s.known_at) for s in find_swings(df.iloc[:k], order=3) if s.kind == "H"}
        assert part == {x for x in full if x[1] < k}
