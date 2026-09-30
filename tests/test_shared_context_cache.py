from __future__ import annotations

import pandas as pd

from backtest_screener import SharedContextCache
from sector.rotation import sector_rank_series


def _ohlcv(n, start=100.0, daily_change=0.5):
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    close = pd.Series([start + i * daily_change for i in range(n)], index=idx)
    return pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000.0}, index=idx
    )


def test_shared_context_cache_truncates_benchmark_close_no_look_ahead():
    """Regression test for the bug fixed alongside this class: build_context
    must never see benchmark data AFTER the bar it's being built for. Rig SPY
    to crash hard only in the back half of its history and confirm an early
    bar's relative-strength read is unaffected by that future crash."""
    n = 120
    ticker_history = _ohlcv(n, start=100.0, daily_change=0.3)

    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    spy_close = pd.Series([100.0 + i * 0.1 for i in range(n)], index=idx)
    # after bar 90, SPY crashes -- must NOT affect a context built from bar 70
    spy_close.iloc[90:] = spy_close.iloc[90] - 50.0

    cache = SharedContextCache("TEST", spy_close=spy_close)
    early_slice = ticker_history.iloc[:70]
    ctx_early = cache.get(early_slice)

    # build the same context directly from a benchmark series truncated by hand
    # to the same date -- if the cache's own truncation is correct, the two must
    # produce identical relative-strength numbers regardless of what happens to
    # spy_close AFTER that date.
    from strategies.context import build_context

    date = early_slice.index[-1]
    ctx_reference = build_context("TEST", early_slice, benchmark_close=spy_close.loc[:date])

    assert ctx_early.relative_strength is not None
    for window, value in ctx_early.relative_strength.relative.items():
        reference_value = ctx_reference.relative_strength.relative[window]
        if pd.isna(value):
            assert pd.isna(reference_value)
        else:
            assert value == reference_value

    # And prove the truncation actually matters: building from the FULL
    # (untruncated, leaking-the-future) spy_close gives a DIFFERENT 1M relative
    # return, since the untruncated benchmark_performance would reflect a crash
    # that, as of bar 70, hasn't happened yet.
    ctx_leaked = build_context("TEST", early_slice, benchmark_close=spy_close)
    assert ctx_early.relative_strength.relative["1M"] != ctx_leaked.relative_strength.relative["1M"]


def test_shared_context_cache_looks_up_sector_strength_for_the_bars_own_date():
    n = 100
    ticker_history = _ohlcv(n)
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    spy = pd.DataFrame({"close": pd.Series([100 + i * 0.1 for i in range(n)], index=idx)})
    sector_histories = {
        "XLK": pd.DataFrame({"close": pd.Series([100 + i * 0.5 for i in range(n)], index=idx)}),  # strong
        "XLU": pd.DataFrame({"close": pd.Series([100 - i * 0.2 for i in range(n)], index=idx)}),  # weak
    }
    rank_df, trend_df = sector_rank_series(sector_histories, spy)

    cache = SharedContextCache(
        "TEST", sector_name="Technology", sector_close=sector_histories["XLK"]["close"],
        sector_rank_df=rank_df, sector_trend_df=trend_df,
    )
    history_slice = ticker_history.iloc[:60]
    ctx = cache.get(history_slice)
    date = history_slice.index[-1]

    assert ctx.sector_strength is not None
    assert ctx.sector_strength.etf == "XLK"
    assert ctx.sector_strength.rank == int(rank_df.loc[date, "XLK"])
