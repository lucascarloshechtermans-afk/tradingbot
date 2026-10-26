"""The Pine script indicator_lab/pine/minervini_vcp_4h.pine must mark the same BUY bars as rule P1 of
indicator_lab/h4/pro_concepts.py (with the RS condition switched off on both sides: Pine cannot rank a universe)."""
import os

import numpy as np
import pandas as pd
import pytest

CACHE = os.path.join(os.path.dirname(__file__), "..", "indicator_lab", ".cache4h")


def pine_signal(df: pd.DataFrame) -> np.ndarray:
    """Line-by-line transcription of the Pine conditions (ta.highest/lowest include the current bar)."""
    c, h, lo, v = df["close"], df["high"], df["low"], df["volume"]
    sma = lambda n: c.rolling(n).mean()
    s50, s150, s200 = sma(50), sma(150), sma(200)
    tt = (c > s50) & (s50 > s150) & (s150 > s200) & (s200 > s200.shift(21)) & (c >= 1.3 * lo.rolling(252).min()) \
        & (c >= 0.75 * h.rolling(252).max())
    r10 = (h.rolling(10).max() - lo.rolling(10).min()) / c
    r40 = (h.rolling(40).max() - lo.rolling(40).min()) / c
    va50 = v.rolling(50).mean()
    vcp = (r10 <= 0.10) & (r10 < 0.5 * r40) & (v.rolling(10).mean() < va50)
    sig = tt.shift(1, fill_value=False) & vcp.shift(1, fill_value=False) & (c > h.rolling(10).max().shift(1)) & (v >= 1.4 * va50)
    return sig.to_numpy(bool)


@pytest.mark.skipif(not os.path.isdir(CACHE), reason="4H cache not present")
def test_pine_matches_research_rule():
    os.environ.setdefault("PRO_TF", "4h")
    os.environ.setdefault("CLASSIC_TF", "4h")
    from indicator_lab.h4 import pro_concepts as PC
    from indicator_lab.h4.test4h import bars4h
    checked = signals = 0
    for t in ("AAPL", "NVDA", "MSFT", "AMD", "COST", "SMCI"):
        df = bars4h(t)
        if df is None or len(df) < 400:
            continue
        research = PC.signals(df, np.full(len(df), 100.0))["P1 Minervini trend template + VCP-breakout"][0]
        assert (pine_signal(df) == research).all(), t
        checked += 1
        signals += int(research.sum())
    assert checked >= 3 and signals >= 5    # not vacuous: real BUY bars were compared
