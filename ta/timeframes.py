"""Build monthly / weekly / daily / 4H / 1H frames from daily and hourly data
using CLOSED candles only, all as of the same moment: the last daily close.

* daily: the input is assumed to be completed sessions (data.sessions)
* weekly (W-FRI) / monthly: the last period is kept only if the last daily bar
  is the period's last weekday; otherwise that partial candle is dropped
* 4H / 1H: bars dated after the last daily close are removed, so a lower
  timeframe never sees prices the daily frame has not seen yet
"""

from __future__ import annotations

import pandas as pd

from ta.core import normalize

AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def ny_naive(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df) == 0:
        return df
    idx = df.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    return df.set_axis(idx)


def daily_frame(daily: pd.DataFrame) -> pd.DataFrame:
    d = ny_naive(normalize(daily))
    return d.set_axis(d.index.normalize())


def _resample(d: pd.DataFrame, rule: str, complete: bool) -> pd.DataFrame:
    out = d.resample(rule).agg(AGG).dropna(subset=["open", "high", "low", "close"])
    if len(out) and not complete:
        out = out.iloc[:-1]
    return out


def weekly_frame(d: pd.DataFrame) -> pd.DataFrame:
    if len(d) == 0:
        return d
    return _resample(d, "W-FRI", d.index[-1].weekday() == 4)


def monthly_frame(d: pd.DataFrame) -> pd.DataFrame:
    if len(d) == 0:
        return d
    last = d.index[-1]
    return _resample(d, "ME", (last + pd.offsets.BDay(1)).month != last.month)


def intraday_frames(hourly: pd.DataFrame | None, last_daily: pd.Timestamp) -> dict[str, pd.DataFrame]:
    if hourly is None or len(hourly) == 0:
        return {}
    from analysis.chart_read import resample_to_4h

    h = normalize(hourly)
    if getattr(h.index, "tz", None) is None:
        h.index = h.index.tz_localize("UTC")
    h4 = ny_naive(resample_to_4h(h))
    h1 = ny_naive(h)
    cutoff = last_daily + pd.Timedelta(days=1)
    return {"4h": h4[h4.index < cutoff], "1h": h1[h1.index < cutoff].iloc[-400:]}


def build_timeframes(daily: pd.DataFrame, hourly: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    d = daily_frame(daily)
    out = {"monthly": monthly_frame(d), "weekly": weekly_frame(d), "daily": d}
    if len(d):
        out.update(intraday_frames(hourly, d.index[-1]))
    return out
