"""MOMENTUM TOP 20 -- the monthly momentum book (README, "Research round 6").

Pure price data, no fundamentals:
  * universe: S&P 500 + S&P MidCap 400 members (data/sp1000_members.json)
    plus the scanner's own list -- the universe the backtest ranked
  * eligible: close >= $5, 20-day average dollar volume >= $10M, >= 253 closes
  * score: 12-1 month return = close 21 sessions ago / close 252 sessions ago - 1
  * at the close of the LAST trading day of each month: hold the top 20,
    equal weight, bought at the next open -- only if SPY closes above its
    200-day SMA that day, otherwise the whole sleeve sits in cash for the month.

Backtest (next-open fills, 10 bp per side, 2008-2021 / 2022-2026, research /
holdout halves of the stocks): 21.0/20.1% and 13.0/25.4% a year, max
drawdown ~35%. Today's index members are used back in time, which flatters
every stock backtest by roughly 4-5% a year (measured against the real
equal-weight ETF RSP); the momentum ETF MTUM, which has no such bias, also
beat SPY. Expect ~12-18% a year with ~35% drawdowns, not 20%+.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SKIP = 21            # skip the most recent month (short-term reversal)
LOOKBACK = 252       # 12 months
TOP_N = 20
MIN_PRICE = 5.0
MIN_DOLLAR_VOLUME = 10e6
MEMBERS_PATH = Path(__file__).resolve().parent.parent / "data" / "sp1000_members.json"


def load_universe(path: Path = MEMBERS_PATH) -> dict[str, str | None]:
    """ticker -> GICS sector for the S&P 500 + 400 members."""
    with open(path) as f:
        return dict(json.load(f)["members"])


@dataclass
class MomentumPick:
    rank: int
    ticker: str
    sector: str | None
    mom_12_1: float       # % return from 12 months to 1 month ago
    ret_1m: float         # % return over the last 21 sessions (skipped by the score)
    close: float
    status: str           # NIEUW (new this month) / BLIJFT (held over)


@dataclass
class MomentumBook:
    as_of: pd.Timestamp | None           # month-end close the official list was decided on
    invested: bool                       # SPY above its 200-day SMA at that month-end
    picks: list[MomentumPick]            # the official list (hold these this month)
    exits: list[str]                     # in last month's list, not in this one
    preview_date: pd.Timestamp | None    # latest close
    preview: list[MomentumPick]          # what the list would be if the month ended today
    preview_in: list[str] = field(default_factory=list)
    preview_out: list[str] = field(default_factory=list)
    spy_above_200_now: bool | None = None
    next_rebalance: pd.Timestamp | None = None
    eligible_count: int = 0
    universe_size: int = 0


def naive_day(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    if ts.tz is not None:
        ts = ts.tz_convert("America/New_York").tz_localize(None)
    return ts.normalize()


def is_month_end(date: pd.Timestamp) -> bool:
    """True when the next business day falls in another month (holidays ignored)."""
    nxt = date + pd.offsets.BDay(1)
    return nxt.month != date.month


def month_end_rows(index: pd.DatetimeIndex) -> list[int]:
    """Row positions of completed month-ends: the last row of every month, plus
    the latest row only if it is itself the last business day of its month."""
    months = index.to_period("M")
    rows = [i for i in range(len(index) - 1) if months[i] != months[i + 1]]
    if len(index) and is_month_end(index[-1]):
        rows.append(len(index) - 1)
    return rows


def rank_at(closes: pd.DataFrame, volumes: pd.DataFrame, row: int, top_n: int = TOP_N) -> list[tuple[str, float, float, float]]:
    """[(ticker, mom_12_1 %, ret_1m %, close)] best first, using data up to `row`."""
    if row < LOOKBACK:
        return []
    c = closes.iloc[: row + 1]
    last = c.iloc[-1]
    dv = (c * volumes.iloc[: row + 1]).iloc[-20:].mean()
    count = c.notna().sum()
    mom = c.iloc[-1 - SKIP] / c.iloc[-1 - LOOKBACK] - 1
    r1m = last / c.iloc[-1 - SKIP] - 1
    ok = (last >= MIN_PRICE) & (dv >= MIN_DOLLAR_VOLUME) & (count >= LOOKBACK + 1) & mom.notna() & np.isfinite(mom)
    ranked = mom[ok].sort_values(ascending=False).iloc[:top_n]
    return [(t, float(m * 100), float(r1m[t] * 100), float(last[t])) for t, m in ranked.items()]


def eligible_count_at(closes: pd.DataFrame, volumes: pd.DataFrame, row: int) -> int:
    c = closes.iloc[: row + 1]
    last = c.iloc[-1]
    dv = (c * volumes.iloc[: row + 1]).iloc[-20:].mean()
    return int(((last >= MIN_PRICE) & (dv >= MIN_DOLLAR_VOLUME) & (c.notna().sum() >= LOOKBACK + 1)).sum())


def build_book(closes: pd.DataFrame, volumes: pd.DataFrame, spy_close: pd.Series, sectors: dict[str, str | None],
               top_n: int = TOP_N) -> MomentumBook:
    """closes/volumes: date x ticker (split+dividend adjusted closes)."""
    closes = closes.sort_index()
    volumes = volumes.reindex_like(closes)
    spy = spy_close.reindex(closes.index).ffill()
    spy_ok = spy > spy.rolling(200).mean()
    ends = month_end_rows(closes.index)
    ends = [r for r in ends if r >= LOOKBACK]

    def picks(rows, prev: set[str]) -> list[MomentumPick]:
        return [MomentumPick(i + 1, t, sectors.get(t), m, r1, c, "BLIJFT" if t in prev else "NIEUW")
                for i, (t, m, r1, c) in enumerate(rows)]

    as_of, official, exits, invested = None, [], [], False
    if ends:
        cur = rank_at(closes, volumes, ends[-1], top_n)
        prev_rows = rank_at(closes, volumes, ends[-2], top_n) if len(ends) >= 2 else []
        prev = {t for t, *_ in prev_rows}
        as_of = closes.index[ends[-1]]
        invested = bool(spy_ok.iloc[ends[-1]])
        official = picks(cur, prev)
        exits = sorted(prev - {t for t, *_ in cur})
    last_row = len(closes) - 1
    prev_now = {p.ticker for p in official}
    pv_rows = rank_at(closes, volumes, last_row, top_n)
    preview = picks(pv_rows, prev_now)
    pv_set = {t for t, *_ in pv_rows}
    last_date = closes.index[-1] if len(closes) else None
    next_reb = None
    if last_date is not None:
        next_reb = last_date if is_month_end(last_date) else (last_date + pd.offsets.BMonthEnd(0))
    return MomentumBook(
        as_of=as_of, invested=invested, picks=official, exits=exits, preview_date=last_date, preview=preview,
        preview_in=sorted(pv_set - prev_now), preview_out=sorted(prev_now - pv_set),
        spy_above_200_now=bool(spy_ok.iloc[-1]) if len(spy_ok) else None, next_rebalance=next_reb,
        eligible_count=eligible_count_at(closes, volumes, last_row) if len(closes) else 0, universe_size=closes.shape[1],
    )


def fetch_universe(tickers: list[str], cache=None, period: str = "15mo", batch: int = 100,
                   latest_session: pd.Timestamp | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Adjusted daily closes and volumes for the whole universe via batched
    yfinance downloads (one request per 100 tickers instead of 900). Cached
    as two frames in the scanner's DiskCache; refetched when the cache ends
    before `latest_session` (e.g. SPY's last bar), so a weekend run never
    ranks on a stale Thursday close."""
    if cache is not None:
        c, v, miss = cache.get("momuni_close"), cache.get("momuni_volume"), cache.get("momuni_missing")
        missing = set(miss.iloc[:, 0]) if miss is not None and miss.shape[1] else set()
        fresh = c is not None and len(c.index) and (latest_session is None or c.index[-1] >= naive_day(latest_session))
        if fresh and v is not None and set(tickers) <= set(c.columns) | missing:
            return c, v
    import yfinance as yf

    closes, vols = {}, {}
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        try:
            raw = yf.download(chunk, period=period, auto_adjust=True, progress=False, group_by="ticker", threads=True)
        except Exception as exc:  # noqa: BLE001 - one failed batch must not kill the scan
            logger.warning("momentum universe batch %d failed: %s", i // batch, exc)
            continue
        for t in chunk:
            try:
                df = raw[t] if len(chunk) > 1 else raw
                s = df["Close"].dropna()
                if len(s):
                    closes[t], vols[t] = df["Close"], df["Volume"]
            except KeyError:
                continue
    c, v = pd.DataFrame(closes), pd.DataFrame(vols)
    for df in (c, v):
        if len(df.index) and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
    if cache is not None and not c.empty:
        cache.set("momuni_close", c)
        cache.set("momuni_volume", v)
        cache.set("momuni_missing", pd.DataFrame(index=sorted(set(tickers) - set(c.columns))).reset_index())
    return c, v
