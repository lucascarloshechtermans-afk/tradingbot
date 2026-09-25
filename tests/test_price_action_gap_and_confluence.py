import pandas as pd

from price_action.levels import Level, confluence_score
from price_action.patterns import classify_gap


def _idx(n):
    return pd.date_range("2024-01-01", periods=n, freq="D")


def test_classify_gap_breakaway_from_consolidation():
    tight = [100.0] * 10
    close = pd.Series(tight + [112.0], index=_idx(11))
    open_ = close.shift(1).fillna(close.iloc[0])
    open_.iloc[-1] = 112.0
    high = close + 0.5
    low = close - 0.5
    sma50 = pd.Series([100.0] * 11, index=_idx(11))
    result = classify_gap(open_, high, low, close, sma50, atr_value=1.0, threshold_pct=1.0, consolidation_window=10)
    assert result == "gap_up_breakaway"


def test_classify_gap_exhaustion_when_already_extended():
    idx = _idx(11)
    close = pd.Series([100 + i * 3 for i in range(10)] + [140.0], index=idx)  # strong prior run, wide range
    open_ = close.shift(1).fillna(close.iloc[0])
    open_.iloc[-1] = 140.0
    high = close + 0.5
    low = close - 0.5
    sma50 = pd.Series([100.0] * 11, index=idx)  # far below the extended price
    result = classify_gap(open_, high, low, close, sma50, atr_value=1.0, threshold_pct=1.0, consolidation_window=10)
    assert result == "gap_up_exhaustion"


def test_classify_gap_continuation_otherwise():
    idx = _idx(11)
    close = pd.Series([100 + i * 0.3 for i in range(10)] + [104.0], index=idx)
    open_ = close.shift(1).fillna(close.iloc[0])
    open_.iloc[-1] = 104.0
    high = close + 2.0
    low = close - 2.0
    sma50 = pd.Series([101.0] * 11, index=idx)
    result = classify_gap(open_, high, low, close, sma50, atr_value=1.0, threshold_pct=1.0, consolidation_window=10)
    assert result == "gap_up_continuation"


def test_classify_gap_returns_none_without_a_gap():
    idx = _idx(11)
    close = pd.Series([100.0] * 11, index=idx)
    open_ = pd.Series([100.0] * 11, index=idx)
    high = close + 0.2
    low = close - 0.2
    sma50 = pd.Series([100.0] * 11, index=idx)
    result = classify_gap(open_, high, low, close, sma50, atr_value=1.0)
    assert result is None


def test_confluence_score_counts_independent_sources():
    levels = [Level(price=100.0, kind="support", touches=3, strength=60, last_touch=None)]
    count, sources = confluence_score(price=100.2, levels=levels, vwap_value=100.1, tolerance_pct=1.0)
    assert count >= 2
    assert any("support" in s for s in sources)
    assert any("VWAP" in s for s in sources)


def test_confluence_score_zero_when_nothing_nearby():
    levels = [Level(price=50.0, kind="support", touches=3, strength=60, last_touch=None)]
    # 197.3 is far from the support level, not a round-$5 number, no VWAP/fib given
    count, sources = confluence_score(price=197.3, levels=levels, vwap_value=None, tolerance_pct=1.0)
    assert count == 0
    assert sources == []


def test_confluence_score_with_fibonacci():
    from price_action.fibonacci import fibonacci_retracement_levels

    # chosen so the 50% level (103.79) isn't coincidentally near a round-$5 number
    fib = fibonacci_retracement_levels(swing_high=108.37, swing_low=99.21)
    count, sources = confluence_score(price=103.79, levels=[], vwap_value=None, fib_levels=fib, tolerance_pct=1.0)
    assert count == 1
    assert "Fibonacci" in sources[0]
