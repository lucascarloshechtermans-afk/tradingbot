from __future__ import annotations

import numpy as np
import pandas as pd

from relative_strength.correlation import compute_correlation_profile, rolling_correlation


def _idx(n):
    return pd.date_range("2023-01-01", periods=n, freq="D")


def test_rolling_correlation_perfectly_correlated_series():
    rng = np.random.default_rng(0)
    base = pd.Series(100 + rng.normal(0, 1, 100).cumsum(), index=_idx(100))
    identical = base.copy()  # perfectly tracks itself -> correlation 1
    corr = rolling_correlation(identical, base, window=60)
    assert abs(corr.iloc[-1] - 1.0) < 1e-9


def test_rolling_correlation_no_look_ahead():
    rng = np.random.default_rng(1)
    close = pd.Series(100 + rng.normal(0, 1, 120).cumsum(), index=_idx(120))
    benchmark = pd.Series(100 + rng.normal(0, 1, 120).cumsum(), index=_idx(120))
    full = rolling_correlation(close, benchmark, window=60)
    truncated = rolling_correlation(close.iloc[:80], benchmark.iloc[:80], window=60)
    assert full.iloc[79] == truncated.iloc[-1]


def test_compute_correlation_profile_idiosyncratic_when_uncorrelated():
    rng = np.random.default_rng(2)
    close = pd.Series(100 + rng.normal(0, 1, 100).cumsum(), index=_idx(100))
    # unrelated random walk
    spy = pd.Series(100 + rng.normal(0, 1, 100).cumsum(), index=_idx(100))
    profile = compute_correlation_profile(close, spy, window=60)
    assert profile.corr_spy is not None
    assert isinstance(profile.is_idiosyncratic, bool)


def test_compute_correlation_profile_handles_missing_benchmarks():
    close = pd.Series(100.0 + pd.Series(range(100)), index=_idx(100))
    profile = compute_correlation_profile(close, spy_close=None, qqq_close=None, sector_close=None)
    assert profile.corr_spy is None
    assert profile.corr_qqq is None
    assert profile.corr_sector is None
    assert profile.is_idiosyncratic is False
