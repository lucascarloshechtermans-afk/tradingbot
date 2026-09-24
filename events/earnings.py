from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd


@dataclass
class EarningsWarning:
    has_upcoming_earnings: bool
    days_until_earnings: int | None
    should_avoid: bool
    message: str | None


def check_earnings_proximity(
    earnings_dates: list[datetime],
    as_of: datetime,
    buffer_days: int = 5,
    avoid_earnings: bool = True,
) -> EarningsWarning:
    """Flag when the next known earnings date falls within `buffer_days` of `as_of`.

    `should_avoid` only fires when `avoid_earnings` is enabled in config AND the
    date falls inside the buffer — the warning message itself (`message`, via
    `has_upcoming_earnings`) is still populated even when avoidance is switched off,
    so the scanner can surface it as context either way.
    """
    future_dates = [d for d in earnings_dates if d.date() >= as_of.date()]
    if not future_dates:
        return EarningsWarning(has_upcoming_earnings=False, days_until_earnings=None, should_avoid=False, message=None)

    next_earnings = min(future_dates)
    days_until = (next_earnings.date() - as_of.date()).days
    within_buffer = days_until <= buffer_days
    should_avoid = bool(avoid_earnings and within_buffer)
    message = f"Earnings in {days_until} days" if within_buffer else f"Next earnings in {days_until} days"

    return EarningsWarning(
        has_upcoming_earnings=True,
        days_until_earnings=days_until,
        should_avoid=should_avoid,
        message=message,
    )


def _naive_index(series: pd.Series) -> pd.Series:
    if series.index.tz is not None:
        series = series.copy()
        series.index = series.index.tz_localize(None)
    return series


def _naive_timestamp(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize(None) if ts.tz is not None else ts


def check_recent_split(splits: pd.Series, as_of: datetime, lookback_days: int = 30) -> str | None:
    """Warn about a recent stock split — technicals computed on raw (non-adjusted)
    history can show artificial gaps/jumps around a split date."""
    if splits is None or splits.empty:
        return None
    splits = _naive_index(splits)
    cutoff = _naive_timestamp(as_of) - pd.Timedelta(days=lookback_days)
    recent = splits[splits.index >= cutoff]
    if recent.empty:
        return None
    latest_date = recent.index[-1]
    ratio = recent.iloc[-1]
    return f"Stock split {ratio:g}:1 on {latest_date.date()} — technicals near this date may be distorted"


def check_upcoming_dividend(dividends: pd.Series, as_of: datetime, lookback_days: int = 10) -> str | None:
    """Note a recent ex-dividend date (adjusted-close vs raw-close discontinuity)."""
    if dividends is None or dividends.empty:
        return None
    dividends = _naive_index(dividends)
    cutoff = _naive_timestamp(as_of) - pd.Timedelta(days=lookback_days)
    recent = dividends[dividends.index >= cutoff]
    if recent.empty:
        return None
    latest_date = recent.index[-1]
    amount = recent.iloc[-1]
    return f"Ex-dividend of {amount:.2f} on {latest_date.date()}"
