from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from indicators.momentum import roc

SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"]

SECTOR_ETF_MAP = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Utilities": "XLU",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


@dataclass
class SectorStrength:
    etf: str
    performance_5d: float
    performance_1m: float
    performance_3m: float
    relative_strength_vs_spy: float
    volatility_pct: float  # annualized stdev of daily returns over the trailing month, as a %
    rank: int
    trend: str  # "improving" | "deteriorating" | "stable"


def rank_sectors(sector_histories: dict[str, pd.DataFrame], spy_history: pd.DataFrame) -> list[SectorStrength]:
    """Rank sector ETFs by 1-month relative strength vs SPY.

    `trend` compares the most recent relative-strength reading against the reading
    5 trading days ago (an "improving" sector is one whose relative strength is
    itself increasing, not just currently positive).
    """
    spy_close = spy_history["close"]
    spy_1m = roc(spy_close, 20)

    results: list[SectorStrength] = []
    for etf, df in sector_histories.items():
        close = df["close"]
        perf_5d = roc(close, 5).iloc[-1]
        perf_1m_series = roc(close, 20)
        perf_1m = perf_1m_series.iloc[-1]
        perf_3m = roc(close, 60).iloc[-1]
        rs_series = perf_1m_series - spy_1m
        rs_now = rs_series.iloc[-1]

        daily_returns = close.pct_change().tail(20)
        volatility_pct = float(daily_returns.std() * (252**0.5) * 100) if len(daily_returns.dropna()) > 1 else float("nan")

        trend = "stable"
        if len(rs_series.dropna()) > 5:
            rs_5d_ago = rs_series.iloc[-6]
            if pd.notna(rs_now) and pd.notna(rs_5d_ago):
                if rs_now > rs_5d_ago + 0.5:
                    trend = "improving"
                elif rs_now < rs_5d_ago - 0.5:
                    trend = "deteriorating"

        results.append(
            SectorStrength(
                etf=etf,
                performance_5d=float(perf_5d) if pd.notna(perf_5d) else float("nan"),
                performance_1m=float(perf_1m) if pd.notna(perf_1m) else float("nan"),
                performance_3m=float(perf_3m) if pd.notna(perf_3m) else float("nan"),
                relative_strength_vs_spy=float(rs_now) if pd.notna(rs_now) else float("nan"),
                volatility_pct=volatility_pct,
                rank=0,
                trend=trend,
            )
        )

    def _sort_key(s: SectorStrength) -> float:
        return s.relative_strength_vs_spy if pd.notna(s.relative_strength_vs_spy) else float("-inf")

    results.sort(key=_sort_key, reverse=True)
    for i, r in enumerate(results, start=1):
        r.rank = i
    return results


def sector_strength_for(sector_name: str | None, ranked: list[SectorStrength]) -> SectorStrength | None:
    if sector_name is None:
        return None
    etf = SECTOR_ETF_MAP.get(sector_name)
    if etf is None:
        return None
    return next((r for r in ranked if r.etf == etf), None)
