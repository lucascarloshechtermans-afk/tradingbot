"""LEADER BREAKOUT -- a breakout, but only in a momentum leader (README, "Research round 7").

Pure price data:
  * leader: top 50 of the momentum universe by 12-1 month return, today
  * breakout: the first close above the highest close of the prior 50 sessions
  * only while SPY is above its 200-day SMA
Trade plan (as backtested): buy the next open, initial stop 2.5 ATR under the
fill, then a trailing exit -- sell at the next open after a close below the
lowest close of the prior 20 sessions. No target: winners run (median ~24
sessions; 38% winners, average winner +2.1R, average loser -0.8R).

Honest result (research/breakout7.py): +0.22..+0.53R per trade in all four
cells and better than a random stock bought the same day in all four, but NOT
better than simply buying a leader without a breakout, and not significant
(t < 2). Plain breakouts outside leaders were WORSE than random. So: if you
trade breakouts, trade them in leaders, with the trailing exit.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from analysis.momentum_portfolio import rank_at

LEADER_TOP = 50
BREAKOUT_LOOKBACK = 50
EXIT_LOOKBACK = 20
STOP_ATR = 2.5
NEAR_PCT = 3.0


@dataclass
class LeaderBreakout:
    ticker: str
    sector: str | None
    close: float
    breakout_level: float   # highest close of the prior 50 sessions (the level just cleared / to clear)
    leader_rank: int        # 1..50 by 12-1 month return
    mom_12_1: float
    exit_level: float       # a close below this (lowest close of the last 20 sessions) -> sell next open
    near: bool = False      # True = not broken out yet, within NEAR_PCT of the level
    atr: float | None = None
    stop_estimate: float | None = None
    priority: int | None = None
    action: str = ""        # NEEM / OVERLAP / ALERT
    in_momentum: bool = False
    daily: pd.DataFrame | None = None

    @property
    def score(self) -> float:
        """0-100: position in the leader list (rank 1 of 50 -> 100)."""
        return round(100 * (LEADER_TOP - self.leader_rank + 1) / LEADER_TOP, 0)

    @property
    def distance_pct(self) -> float:
        return (self.breakout_level / self.close - 1) * 100

    @property
    def risk_pct(self) -> float | None:
        return None if self.stop_estimate is None else (self.close - self.stop_estimate) / self.close * 100


def find_leader_breakouts(closes: pd.DataFrame, volumes: pd.DataFrame, spy_close: pd.Series,
                          sectors: dict[str, str | None] | None = None,
                          min_price=None) -> tuple[list[LeaderBreakout], list[LeaderBreakout], bool]:
    """(breakouts today, leaders within NEAR_PCT of their 50-day closing high, spy_above_200)."""
    sectors = sectors or {}
    if closes.empty or len(closes) < 260:
        return [], [], False
    spy = spy_close.reindex(closes.index).ffill()
    bull = bool(spy.iloc[-1] > spy.rolling(200).mean().iloc[-1])
    leaders = rank_at(closes, volumes, len(closes) - 1, top_n=LEADER_TOP, min_price=min_price)
    out, near = [], []
    for rank, (t, mom, _r1m, _close) in enumerate(leaders, 1):
        c = closes[t].dropna()
        if len(c) < BREAKOUT_LOOKBACK + 2:
            continue
        level_today = float(c.iloc[-1 - BREAKOUT_LOOKBACK:-1].max())
        level_prev = float(c.iloc[-2 - BREAKOUT_LOOKBACK:-2].max())
        last, prev = float(c.iloc[-1]), float(c.iloc[-2])
        exit_level = float(c.iloc[-EXIT_LOOKBACK:].min())
        item = LeaderBreakout(ticker=t, sector=sectors.get(t), close=last, breakout_level=level_today,
                              leader_rank=rank, mom_12_1=mom, exit_level=exit_level)
        if last > level_today and prev <= level_prev:
            out.append(item)
        elif last <= level_today and (level_today / last - 1) * 100 <= NEAR_PCT:
            # tomorrow's level is the max of the last 50 closes (includes today)
            item.breakout_level = float(c.iloc[-BREAKOUT_LOOKBACK:].max())
            item.near = True
            near.append(item)
    return out, sorted(near, key=lambda b: b.distance_pct), bull


def attach_daily(item: LeaderBreakout, daily: pd.DataFrame | None) -> None:
    """ATR(14) and the initial-stop estimate from full OHLC history."""
    if daily is None or len(daily) < 20:
        return
    from indicators.volatility import atr as atr_fn

    a = float(atr_fn(daily["high"], daily["low"], daily["close"], 14).iloc[-1])
    if np.isfinite(a) and a > 0:
        item.atr = a
        item.stop_estimate = item.close - STOP_ATR * a
    item.daily = daily


def prioritize_breakouts(items: list, momentum_tickers: set[str] | None = None) -> list:
    """Leader rank order; stocks already in the momentum book last as OVERLAP."""
    momentum_tickers = momentum_tickers or set()
    get = (lambda x: x[0]) if items and isinstance(items[0], tuple) else (lambda x: x)  # noqa: E731
    fresh = sorted((x for x in items if get(x).ticker not in momentum_tickers), key=lambda x: get(x).leader_rank)
    overlap = sorted((x for x in items if get(x).ticker in momentum_tickers), key=lambda x: get(x).leader_rank)
    for i, x in enumerate(fresh + overlap, 1):
        b = get(x)
        b.priority = i
        b.in_momentum = b.ticker in momentum_tickers
        b.action = "OVERLAP" if b.in_momentum else ("ALERT" if b.near else "NEEM")
    return fresh + overlap
