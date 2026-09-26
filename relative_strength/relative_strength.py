from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from indicators.momentum import roc

PERFORMANCE_WINDOWS = {"1W": 5, "1M": 20, "3M": 60, "6M": 120}


@dataclass
class RelativeStrength:
    performance: dict[str, float]
    benchmark_performance: dict[str, float]
    relative: dict[str, float]
    outperforming_benchmark_1m: bool


def _ytd_return(close: pd.Series) -> float | None:
    if close.empty:
        return None
    last_ts = close.index[-1]
    year_start = pd.Timestamp(year=last_ts.year, month=1, day=1, tz=close.index.tz)
    ytd_slice = close[close.index >= year_start]
    if len(ytd_slice) < 2:
        return None
    first = ytd_slice.iloc[0]
    if first == 0:
        return None
    return float((ytd_slice.iloc[-1] / first - 1) * 100)


def _performance_snapshot(close: pd.Series) -> dict[str, float]:
    perf = {}
    for label, window in PERFORMANCE_WINDOWS.items():
        value = roc(close, window).iloc[-1]
        perf[label] = float(value) if pd.notna(value) else float("nan")
    ytd = _ytd_return(close)
    perf["YTD"] = ytd if ytd is not None else float("nan")
    return perf


def compute_relative_strength(close: pd.Series, benchmark_close: pd.Series) -> RelativeStrength:
    """Performance across 1W/1M/3M/6M/YTD for a stock and a benchmark, plus the
    difference (relative strength) for each window.
    """
    perf = _performance_snapshot(close)
    bench_perf = _performance_snapshot(benchmark_close)
    relative = {
        k: (perf[k] - bench_perf[k]) if pd.notna(perf[k]) and pd.notna(bench_perf[k]) else float("nan")
        for k in perf
    }
    outperforming = pd.notna(relative["1M"]) and relative["1M"] > 0
    return RelativeStrength(
        performance=perf,
        benchmark_performance=bench_perf,
        relative=relative,
        outperforming_benchmark_1m=bool(outperforming),
    )


RS_RANK_WINDOW = 60  # ~3 trading months, matching the CANSLIM/Minervini RS Rating lookback


def compute_universe_rs_ranks(closes: dict[str, pd.Series], window: int = RS_RANK_WINDOW) -> dict[str, float]:
    """Percentile rank (0-100) of each ticker's trailing `window`-day return among
    ALL tickers currently being scanned — this is the live-scan equivalent of an
    IBD-style RS Rating (require >=70 to even consider a setup, per Minervini's
    Trend Template / CANSLIM). Every input closes at the SAME (most recent) date,
    so this is a single point-in-time snapshot, not a walk-forward series — use
    `universe_rs_rank_series` for a backtest instead.
    """
    trailing_return = {}
    for ticker, close in closes.items():
        if len(close) <= window:
            continue
        r = roc(close, window).iloc[-1]
        if pd.notna(r):
            trailing_return[ticker] = float(r)
    if not trailing_return:
        return {}
    ranks = pd.Series(trailing_return).rank(pct=True) * 100
    return ranks.to_dict()


def universe_rs_rank_series(closes: dict[str, pd.Series], window: int = RS_RANK_WINDOW) -> pd.DataFrame:
    """Walk-forward version of `compute_universe_rs_ranks`: for EVERY date, the
    percentile rank (0-100) of each ticker's trailing `window`-day return among
    all other tickers with data on that date. Each row only depends on prices
    through that row's own date (roc() is strictly trailing), so this is safe to
    use as a same-day entry gate in an event-driven backtest without introducing
    look-ahead bias. Returns a DataFrame indexed by date, one column per ticker;
    a ticker missing data on a given date is simply excluded from that date's
    ranking (NaN), not treated as the weakest.
    """
    roc_frame = pd.DataFrame({ticker: roc(close, window) for ticker, close in closes.items()})
    return roc_frame.rank(axis=1, pct=True) * 100


# Composite momentum, from the externally supplied "Explosive Breakout"
# scanner (alt_scanners/): the mean of three trailing returns, all measured
# up to 5 sessions ago -- the most recent week is skipped because of the
# short-term reversal effect. research/compare_scanners.py found its top-decile
# rank the one ingredient of that scanner that also improves OUR trades.
MOMENTUM_HORIZONS = (63, 126, 252)
MOMENTUM_SKIP = 5
MIN_MOMENTUM_RANK_TICKERS = 10  # below this a percentile is meaningless (their rule too)


def composite_momentum(close: pd.Series, horizons: tuple[int, ...] = MOMENTUM_HORIZONS, skip: int = MOMENTUM_SKIP) -> pd.Series:
    """Per-bar composite momentum in %: mean over `horizons` of
    close[t-skip] / close[t-skip-h] - 1. Strictly trailing; NaN until the
    longest horizon has enough history (max(horizons) + skip + 1 bars)."""
    parts = [(close.shift(skip) / close.shift(skip + h) - 1) * 100 for h in horizons]
    return pd.concat(parts, axis=1).mean(axis=1, skipna=False)


def universe_momentum_rank_series(closes: dict[str, pd.Series]) -> pd.DataFrame:
    """Walk-forward percentile rank (0-100) of each ticker's composite momentum
    among all tickers with a value on that date (NaN = not enough history,
    excluded from the ranking rather than treated as weakest). A date with
    fewer than MIN_MOMENTUM_RANK_TICKERS ranked tickers is all-NaN."""
    frame = pd.DataFrame({ticker: composite_momentum(close) for ticker, close in closes.items()})
    ranks = frame.rank(axis=1, pct=True) * 100
    ranks[frame.notna().sum(axis=1) < MIN_MOMENTUM_RANK_TICKERS] = float("nan")
    return ranks


def compute_universe_momentum_ranks(closes: dict[str, pd.Series]) -> dict[str, float]:
    """Live-scan snapshot of `universe_momentum_rank_series`: each ticker's
    percentile on its most recent bar. Tickers lacking the history are absent."""
    latest = {}
    for ticker, close in closes.items():
        m = composite_momentum(close).iloc[-1] if len(close) else float("nan")
        if pd.notna(m):
            latest[ticker] = float(m)
    if len(latest) < MIN_MOMENTUM_RANK_TICKERS:
        return {}
    return (pd.Series(latest).rank(pct=True) * 100).to_dict()


def efficiency_ratio(close: pd.Series, window: int = 30) -> float | None:
    """Kaufman efficiency ratio of the last `window` bars: |net move| / total
    path length (0 = pure chop, 1 = straight line). None without enough data."""
    if len(close) < window + 1:
        return None
    tail = close.iloc[-(window + 1):]
    path = tail.diff().abs().sum()
    if path <= 0:
        return 0.0
    return float(abs(tail.iloc[-1] - tail.iloc[0]) / path)
