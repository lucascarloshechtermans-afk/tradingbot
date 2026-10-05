"""US trading-session helpers: only COMPLETED daily bars may drive signals.

A scan run during market hours gets a partial bar for today from yfinance;
treating it as a close produced signals on prices that were not final (e.g. a
'breakout' at 14:45 New York time). Every daily frame is cut to the last
completed session before it is used or cached.
"""
from __future__ import annotations

import pandas as pd

CLOSE_BUFFER = pd.Timedelta(hours=16, minutes=15)  # official close 16:00 NY + 15 min for the final print


def last_completed_session(now: pd.Timestamp | None = None) -> pd.Timestamp:
    """NY calendar date (tz-naive midnight) of the last weekday session that has
    closed. Holidays are not modelled: on a holiday this is the holiday's date,
    which simply matches no bar."""
    now = pd.Timestamp.now(tz="America/New_York") if now is None else pd.Timestamp(now).tz_convert("America/New_York")
    day = now.normalize()
    if now.weekday() >= 5 or now < day + CLOSE_BUFFER:
        day -= pd.tseries.offsets.BDay(1)
    while day.weekday() >= 5:
        day -= pd.Timedelta(days=1)
    return day.tz_localize(None)


def _ny_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if index.tz is not None:
        return index.tz_convert("America/New_York").tz_localize(None).normalize()
    return index.normalize()


def drop_incomplete_daily(df: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Remove daily rows dated after the last completed session (today's live bar)."""
    if df is None or df.empty:
        return df
    return df[_ny_dates(df.index) <= last_completed_session(now)]
