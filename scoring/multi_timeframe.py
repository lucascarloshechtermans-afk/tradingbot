from __future__ import annotations

import pandas as pd

from strategies.context import TickerContext

RESAMPLE_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def resample_weekly(daily_history: pd.DataFrame) -> pd.DataFrame:
    agg = {k: v for k, v in RESAMPLE_AGG.items() if k in daily_history.columns}
    weekly = daily_history.resample("W").agg(agg)
    return weekly.dropna(subset=["open", "high", "low", "close"])


def multi_timeframe_confluence(
    daily_ctx: TickerContext,
    weekly_ctx: TickerContext,
    intraday_ctx: TickerContext | None = None,
) -> tuple[float, list[str]]:
    """Confluence score (0-100) across Weekly (higher timeframe trend), Daily (the
    setup timeframe) and, when available, an intraday timeframe (entry timing).

    Weekly carries the most weight deliberately: a daily setup fighting the weekly
    trend is a lower-conviction trade than one aligned with it.
    """
    score = 0.0
    reasons: list[str] = []

    weekly_trend = weekly_ctx.trend.iloc[-1]
    if weekly_trend == "bullish":
        score += 55
        reasons.append("Weekly trend bullish (higher-timeframe tailwind)")
    elif weekly_trend == "bearish":
        reasons.append("Weekly trend bearish (fighting the higher-timeframe trend)")
    else:
        score += 20
        reasons.append("Weekly trend mixed/insufficient data")

    daily_trend = daily_ctx.trend.iloc[-1]
    if daily_trend == "bullish" and weekly_trend == "bullish":
        score += 30
        reasons.append("Daily trend agrees with Weekly (aligned, not just a bounce)")
    elif daily_trend == "bullish":
        score += 15
        reasons.append("Daily trend bullish, ahead of Weekly")
    elif daily_trend == "bearish" and weekly_trend == "bullish":
        reasons.append("Daily pullback within a bullish Weekly trend")
        score += 10

    if intraday_ctx is not None:
        intraday_trend = intraday_ctx.trend.iloc[-1]
        if intraday_trend == "bullish":
            score += 15
            reasons.append("Intraday (4H) trend bullish — timing confluence")
        elif intraday_trend == "bearish":
            reasons.append("Intraday (4H) trend bearish — timing not yet confirmed")
    else:
        reasons.append("Intraday (4H) timeframe not available for this data source/window")

    return min(score, 100.0), reasons
