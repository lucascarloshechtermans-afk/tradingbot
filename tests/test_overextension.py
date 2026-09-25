from __future__ import annotations

import pandas as pd
import pytest

from risk.overextension import compute_overextension


def _idx(n):
    return pd.date_range("2023-01-01", periods=n, freq="D")


def test_no_stretched_references_when_price_near_all_anchors():
    close = pd.Series(100.0, index=_idx(30))
    profile = compute_overextension(
        close, last_close=100.5, atr_value=2.0,
        ema8=100.0, ema21=100.0, ema50=100.0, vwap=100.0, swing_low=99.0,
    )
    assert profile.stretched_reference_count == 0
    assert profile.is_severely_overextended is False


def test_severely_overextended_when_multiple_references_agree():
    close = pd.Series(100.0, index=_idx(30))
    # price far above every reference, each by >= 3 ATRs (ATR=1.0)
    profile = compute_overextension(
        close, last_close=120.0, atr_value=1.0,
        ema8=100.0, ema21=99.0, ema50=98.0, vwap=100.0, swing_low=95.0,
    )
    assert profile.stretched_reference_count == 5
    assert profile.is_severely_overextended is True
    assert any("multiple independent references" in r.lower() for r in profile.reasons)


def test_single_stretched_reference_not_severe():
    close = pd.Series(100.0, index=_idx(30))
    # only swing_low far away, everything else close by
    profile = compute_overextension(
        close, last_close=100.5, atr_value=1.0,
        ema8=100.0, ema21=100.0, ema50=100.0, vwap=100.0, swing_low=90.0,
    )
    assert profile.stretched_reference_count == 1
    assert profile.is_severely_overextended is False


def test_gain_percentages_computed_from_close_series():
    values = [100.0] * 20 + [110.0]  # +10% in the most recent bar vs 1 day ago
    close = pd.Series(values, index=_idx(len(values)))
    profile = compute_overextension(close, last_close=110.0, atr_value=2.0, ema8=None, ema21=None, ema50=None, vwap=None, swing_low=None)
    assert profile.gain_1d_pct == pytest.approx(10.0)


def test_missing_references_handled_without_crashing():
    close = pd.Series(100.0, index=_idx(30))
    profile = compute_overextension(close, last_close=100.0, atr_value=2.0, ema8=None, ema21=None, ema50=None, vwap=None, swing_low=None)
    assert profile.stretched_reference_count == 0
    assert profile.distance_from_ema8_atr is None
