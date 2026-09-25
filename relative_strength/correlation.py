from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

DEFAULT_CORRELATION_WINDOW = 60
LOW_CORRELATION_THRESHOLD = 0.3
HIGH_CORRELATION_THRESHOLD = 0.7


def rolling_correlation(close: pd.Series, benchmark_close: pd.Series, window: int = DEFAULT_CORRELATION_WINDOW) -> pd.Series:
    """Rolling Pearson correlation of daily returns against a benchmark. Built
    from pandas' `.rolling().corr()`, which only ever looks at the trailing
    `window` bars — safe to use walk-forward with no look-ahead.
    """
    returns = close.pct_change()
    benchmark_returns = benchmark_close.reindex(close.index).ffill().pct_change()
    return returns.rolling(window).corr(benchmark_returns)


@dataclass
class CorrelationProfile:
    corr_spy: float | None
    corr_qqq: float | None
    corr_sector: float | None
    is_idiosyncratic: bool  # low correlation across the board — moving on its own, not just riding the market
    reasons: list[str] = field(default_factory=list)


def compute_correlation_profile(
    close: pd.Series,
    spy_close: pd.Series | None,
    qqq_close: pd.Series | None = None,
    sector_close: pd.Series | None = None,
    window: int = DEFAULT_CORRELATION_WINDOW,
) -> CorrelationProfile:
    """Understand whether a stock's move reflects genuine idiosyncratic strength
    or is mostly just the market/sector moving and dragging it along — a stock
    up 5% with 0.9 correlation to SPY during a 5% SPY rally isn't showing
    special strength; the same 5% move with 0.1 correlation is a very different
    signal. Context only, not a gate: a highly-correlated stock isn't
    automatically a worse setup, but the scanner should be honest about which
    kind of move it's looking at.
    """
    reasons: list[str] = []
    corr_spy = corr_qqq = corr_sector = None

    if spy_close is not None:
        series = rolling_correlation(close, spy_close, window)
        corr_spy = float(series.iloc[-1]) if len(series) and pd.notna(series.iloc[-1]) else None
    if qqq_close is not None:
        series = rolling_correlation(close, qqq_close, window)
        corr_qqq = float(series.iloc[-1]) if len(series) and pd.notna(series.iloc[-1]) else None
    if sector_close is not None:
        series = rolling_correlation(close, sector_close, window)
        corr_sector = float(series.iloc[-1]) if len(series) and pd.notna(series.iloc[-1]) else None

    available = [c for c in (corr_spy, corr_qqq, corr_sector) if c is not None]
    is_idiosyncratic = bool(available) and max(abs(c) for c in available) < LOW_CORRELATION_THRESHOLD

    if corr_spy is not None:
        reasons.append(f"{window}-day correlation to SPY: {corr_spy:+.2f}")
    if corr_sector is not None:
        reasons.append(f"{window}-day correlation to its sector ETF: {corr_sector:+.2f}")
    if is_idiosyncratic:
        reasons.append("Low correlation to broad market/sector — this move looks idiosyncratic, not market-driven")
    elif available and max(abs(c) for c in available) >= HIGH_CORRELATION_THRESHOLD:
        reasons.append("High correlation to broad market/sector — this move is largely riding the market, not standing out on its own")

    return CorrelationProfile(
        corr_spy=corr_spy, corr_qqq=corr_qqq, corr_sector=corr_sector,
        is_idiosyncratic=is_idiosyncratic, reasons=reasons,
    )
