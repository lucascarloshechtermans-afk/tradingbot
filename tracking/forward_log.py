"""Forward test: log every live signal and track how it turns out with the same
rules as the backtest -- the only honest test of a trading system.

  logs/signal_log.csv   one row per signal (system, signal date, ticker, level, ATR, ...)

LEADER BREAKOUT rows are evaluated like research/trend_systems6.donchian_trades:
entry at the next open after the signal close, initial stop 2.5 ATR under the
fill (gap-aware), exit at the next open after a close below the lowest close of
the prior 20 sessions. MOMENTUM rows (the month-end list) are evaluated close to
close until the next month-end, equal weight, against SPY over the same window.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

LOG_PATH = os.path.join("logs", "signal_log.csv")
FIELDS = ["system", "signal_date", "ticker", "close", "level", "atr", "note"]
STOP_ATR = 2.5
EXIT_LOOKBACK = 20


def read_log(path: str = LOG_PATH) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=FIELDS)
    df = pd.read_csv(path, dtype={"ticker": str, "system": str, "note": str})
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    return df


def append_signals(rows: list[dict], path: str = LOG_PATH) -> int:
    """Append new signals; (system, signal_date, ticker) already logged are skipped.
    Returns how many rows were added."""
    have = read_log(path)
    seen = {(r.system, pd.Timestamp(r.signal_date).date(), r.ticker) for r in have.itertuples()}
    new = [r for r in rows if (r["system"], pd.Timestamp(r["signal_date"]).date(), r["ticker"]) not in seen]
    if not new:
        return 0
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    exists = os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        for r in new:
            w.writerow({k: (pd.Timestamp(r[k]).date().isoformat() if k == "signal_date" else r.get(k, "")) for k in FIELDS})
    return len(new)


def rows_from_scan(breakouts: list, book) -> list[dict]:
    """Log rows for today's LEADER BREAKOUTs (action NEEM) and the official momentum list."""
    rows = []
    for b, _read in breakouts or []:
        if getattr(b, "action", "") != "NEEM" or b.daily is None or not len(b.daily):
            continue
        rows.append({"system": "BREAKOUT", "signal_date": _day(b.daily.index[-1]), "ticker": b.ticker,
                     "close": round(b.close, 4), "level": round(b.breakout_level, 4),
                     "atr": round(b.atr, 4) if b.atr else "", "note": f"leader #{b.leader_rank}"})
    if book is not None and book.as_of is not None:
        for p in book.picks:
            rows.append({"system": "MOMENTUM", "signal_date": book.as_of, "ticker": p.ticker, "close": round(p.close, 4),
                         "level": "", "atr": "", "note": "invested" if book.invested else "cash (SPY < 200d)"})
    return rows


def _day(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    if ts.tz is not None:
        ts = ts.tz_convert("America/New_York").tz_localize(None)
    return ts.normalize()


def _naive(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.index = pd.DatetimeIndex([_day(t) for t in df.index])
    return df


@dataclass
class BreakoutResult:
    ticker: str
    signal_date: pd.Timestamp
    status: str            # WAIT (no bar after the signal yet) / OPEN / CLOSED
    entry: float | None
    exit: float | None
    r: float | None        # R multiple (closed) or open R at the last close
    days: int
    reason: str


def evaluate_breakout(ticker: str, daily: pd.DataFrame, signal_date, atr: float) -> BreakoutResult:
    d = _naive(daily).sort_index()
    sd = _day(signal_date)
    after = d[d.index > sd]
    if after.empty or not atr or not np.isfinite(atr):
        return BreakoutResult(ticker, sd, "WAIT", None, None, None, 0, "no session after the signal yet")
    entry = float(after["open"].iloc[0])
    stop = entry - STOP_ATR * atr
    closes = d["close"]
    for i, (day, row) in enumerate(after.iterrows()):
        if row["low"] <= stop:
            px = min(float(row["open"]), stop) if i > 0 else min(entry, stop)
            return BreakoutResult(ticker, sd, "CLOSED", entry, px, (px - entry) / (STOP_ATR * atr), i + 1, "stop")
        prior = closes[closes.index < day].iloc[-EXIT_LOOKBACK:]
        if len(prior) == EXIT_LOOKBACK and row["close"] < prior.min():
            nxt = after.iloc[i + 1] if i + 1 < len(after) else None
            if nxt is None:
                return BreakoutResult(ticker, sd, "OPEN", entry, None, (row["close"] - entry) / (STOP_ATR * atr), i + 1,
                                      "trailing exit triggered: sell at the next open")
            px = float(nxt["open"])
            return BreakoutResult(ticker, sd, "CLOSED", entry, px, (px - entry) / (STOP_ATR * atr), i + 2, "trailing exit")
    last = float(after["close"].iloc[-1])
    return BreakoutResult(ticker, sd, "OPEN", entry, None, (last - entry) / (STOP_ATR * atr), len(after), "open")


def evaluate_momentum(log: pd.DataFrame, closes: pd.DataFrame, spy_close: pd.Series) -> pd.DataFrame:
    """Per logged month-end list: equal-weight close-to-close return until the next
    logged month-end (or the last close) vs SPY."""
    m = log[log.system == "MOMENTUM"]
    if m.empty or closes is None or closes.empty:
        return pd.DataFrame(columns=["as_of", "until", "n", "invested", "book_pct", "spy_pct"])
    closes = _naive(closes)
    spy = _naive(spy_close.to_frame("close"))["close"]
    dates = sorted(m.signal_date.unique())
    out = []
    for i, d in enumerate(dates):
        end = dates[i + 1] if i + 1 < len(dates) else closes.index[-1]
        if end <= d:
            continue
        rows = m[m.signal_date == d]
        invested = not rows["note"].astype(str).str.startswith("cash").any()
        tick = [t for t in rows.ticker if t in closes.columns]
        seg = closes.loc[(closes.index >= d) & (closes.index <= end), tick]
        if len(seg) < 2:
            continue
        book = float((seg.iloc[-1] / seg.iloc[0] - 1).mean() * 100) if invested and tick else 0.0
        s = spy[(spy.index >= d) & (spy.index <= end)]
        out.append({"as_of": d, "until": end, "n": len(tick), "invested": invested, "book_pct": book,
                    "spy_pct": float((s.iloc[-1] / s.iloc[0] - 1) * 100) if len(s) > 1 else np.nan})
    return pd.DataFrame(out)


def summary(breakouts: list[BreakoutResult]) -> dict:
    closed = [b for b in breakouts if b.status == "CLOSED"]
    rs = [b.r for b in closed]
    return {"signals": len(breakouts), "closed": len(closed), "open": sum(b.status == "OPEN" for b in breakouts),
            "win_pct": 100 * np.mean([r > 0 for r in rs]) if rs else None,
            "avg_r": float(np.mean(rs)) if rs else None, "total_r": float(np.sum(rs)) if rs else 0.0}
