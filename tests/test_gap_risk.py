from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from risk.gap_risk import analyze_gap_risk, compute_gap_series, earnings_gap_fraction


def _idx(n):
    return pd.date_range("2023-01-01", periods=n, freq="D")


def _history_with_gaps(n=80, base=100.0, gap_indices=None, gap_pcts=None):
    close = pd.Series(base, index=_idx(n))
    open_ = close.shift(1).fillna(close.iloc[0])
    gap_indices = gap_indices or []
    gap_pcts = gap_pcts or []
    for pos, pct in zip(gap_indices, gap_pcts):
        prior_close = close.iloc[pos - 1]
        open_.iloc[pos] = prior_close * (1 + pct / 100)
    high = pd.concat([open_, close], axis=1).max(axis=1) + 0.5
    low = pd.concat([open_, close], axis=1).min(axis=1) - 0.5
    volume = pd.Series(1_000_000.0, index=_idx(n))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def test_compute_gap_series_matches_manual_calc():
    idx = _idx(3)
    close = pd.Series([100.0, 100.0, 110.0], index=idx)
    open_ = pd.Series([100.0, 100.0, 105.0], index=idx)
    gaps = compute_gap_series(open_, close)
    assert np.isnan(gaps.iloc[0])
    assert gaps.iloc[1] == 0.0
    assert gaps.iloc[2] == 5.0  # (105 - 100) / 100 * 100


def test_analyze_gap_risk_detects_large_gap_frequency():
    history = _history_with_gaps(n=80, gap_indices=[70, 72, 74, 76], gap_pcts=[5.0, -6.0, 4.0, -5.0])
    profile = analyze_gap_risk(history, window=60, large_gap_threshold_pct=3.0)
    assert profile.large_gap_frequency_pct is not None
    assert profile.large_gap_frequency_pct > 0
    assert profile.avg_abs_gap_pct is not None and profile.avg_abs_gap_pct > 0


def test_analyze_gap_risk_zero_for_calm_stock():
    history = _history_with_gaps(n=80)  # no injected gaps at all
    profile = analyze_gap_risk(history, window=60, large_gap_threshold_pct=3.0)
    assert profile.large_gap_frequency_pct == 0.0


def test_analyze_gap_risk_insufficient_history():
    history = _history_with_gaps(n=10)
    profile = analyze_gap_risk(history, window=60)
    assert profile.avg_gap_pct is None
    assert "insufficient" in profile.reasons[0].lower()


def test_analyze_gap_risk_no_look_ahead():
    history = _history_with_gaps(n=100, gap_indices=[90], gap_pcts=[8.0])
    full = analyze_gap_risk(history, window=60)
    truncated = analyze_gap_risk(history.iloc[:70], window=60)
    # a future gap (at index 90) must not affect a profile computed only through index 69
    assert truncated.large_gap_frequency_pct == 0.0
    assert full.large_gap_frequency_pct is not None and full.large_gap_frequency_pct > 0


def test_earnings_gap_fraction_matches_known_earnings_dates():
    history = _history_with_gaps(n=80, gap_indices=[70, 75], gap_pcts=[5.0, -5.0])
    earnings_dates = [datetime.combine(history.index[70].date(), datetime.min.time())]
    frac = earnings_gap_fraction(history, earnings_dates, window=60, large_gap_threshold_pct=3.0)
    assert frac == 0.5  # 1 of 2 large gaps landed on a known earnings date


def test_earnings_gap_fraction_none_without_earnings_dates():
    history = _history_with_gaps(n=80, gap_indices=[70], gap_pcts=[5.0])
    assert earnings_gap_fraction(history, [], window=60) is None
