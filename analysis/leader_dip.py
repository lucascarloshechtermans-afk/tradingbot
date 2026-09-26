"""LEADER DIP -- the one setup that survived the optimization-phase audit.

Buy a short-term dip in a cross-sectional momentum leader:
  * composite momentum rank >= 80 among the scanned universe
    (63/126/252-day returns, last 5 days skipped)
  * 5-day move <= -1.0 ATR (the dip)
Graded by four confirmations, each better in ALL four validation cells
(190-ticker development universe and 163-ticker never-used universe, each
split into 2022-09/2025 and the Oct 2025 - Sep 2026 holdout year):
  * deep dip: close >= 1 ATR below the daily 21 EMA
  * fear: VIX > 20
  * weak tape: SPY below its 50-day SMA
  * the stock moves: ATR% >= 3
Grade A = 3-4 confirmations, B = 2, C = 0-1 (watch only).

Trade plan (as backtested): buy the next session's open, stop 2.5 ATR below
the fill (never tighter than 2 ATR -- the audit's minimum-stop rule), no
fixed target, exit at the close of the 10th session. Backtest (research/
leader_dip.py + README): grade A +0.19..+0.35R/trade in all four cells,
grade A+B +0.07..+0.19R, every calendar year positive in both universes.

Why it works where the old setups didn't: the old breakout / trend-
continuation / pullback entries bought short-term STRENGTH and did worse
than random entries in the same stocks; short-term moves tend to reverse,
and inside a longer-term leader a dip is the side of that reversal to be on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from indicators.trend import ema
from indicators.volatility import atr as atr_fn
from relative_strength.relative_strength import compute_universe_momentum_ranks

MOM_MIN = 80.0
DIP_ATR = 1.0
DIP_LOOKBACK = 5
STOP_ATR = 2.5
HOLD_DAYS = 10


@dataclass
class LeaderDip:
    ticker: str
    grade: str
    confirmations: int
    close: float
    stop_estimate: float      # close - 2.5 ATR; recompute from the actual fill
    atr: float
    momentum_rank: float
    dip_atr: float
    hold_days: int
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    daily: pd.DataFrame | None = None

    @property
    def risk_pct(self) -> float:
        return (self.close - self.stop_estimate) / self.close * 100


def market_state(spy: pd.DataFrame | None, vix: pd.DataFrame | None) -> dict:
    out = {"vix": None, "spy_below_50": None}
    if vix is not None and len(vix):
        out["vix"] = float(vix["close"].dropna().iloc[-1])
    if spy is not None and len(spy) >= 50:
        c = spy["close"].dropna()
        out["spy_below_50"] = bool(c.iloc[-1] < c.rolling(50).mean().iloc[-1])
    return out


def evaluate(ticker: str, df: pd.DataFrame, momentum_rank: float | None, market: dict) -> LeaderDip | None:
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < 60 or momentum_rank is None or momentum_rank < MOM_MIN:
        return None
    c = df["close"]
    a = float(atr_fn(df["high"], df["low"], c, 14).iloc[-1])
    if not np.isfinite(a) or a <= 0:
        return None
    close = float(c.iloc[-1])
    dip = (close - float(c.iloc[-1 - DIP_LOOKBACK])) / a
    if dip > -DIP_ATR:
        return None
    reasons = [f"momentum leader: rank {momentum_rank:.0f}/100",
               f"dip: {dip:+.1f} ATR over {DIP_LOOKBACK} sessions"]
    missing = []
    conf = 0
    e21 = float(ema(c, 21).iloc[-1])
    d21 = (close - e21) / a
    if d21 <= -1.0:
        conf += 1
        reasons.append(f"deep dip: {d21:+.1f} ATR below the daily 21 EMA ({e21:.2f})")
    else:
        missing.append(f"not a deep dip yet ({d21:+.1f} ATR vs the 21 EMA; needs <= -1)")
    vix = market.get("vix")
    if vix is not None and vix > 20:
        conf += 1
        reasons.append(f"fear: VIX {vix:.1f} > 20")
    elif vix is not None:
        missing.append(f"VIX {vix:.1f} (<= 20)")
    if market.get("spy_below_50"):
        conf += 1
        reasons.append("weak tape: SPY below its 50-day SMA")
    elif market.get("spy_below_50") is not None:
        missing.append("SPY above its 50-day SMA")
    atr_pct = a / close * 100
    if atr_pct >= 3:
        conf += 1
        reasons.append(f"moves enough: ATR {atr_pct:.1f}%")
    else:
        missing.append(f"ATR {atr_pct:.1f}% (< 3%)")
    grade = "A" if conf >= 3 else ("B" if conf == 2 else "C")
    return LeaderDip(ticker=ticker, grade=grade, confirmations=conf, close=close, stop_estimate=close - STOP_ATR * a,
                     atr=a, momentum_rank=float(momentum_rank), dip_atr=dip, hold_days=HOLD_DAYS,
                     reasons=reasons, missing=missing, daily=df)


def find_leader_dips(histories: dict[str, pd.DataFrame], spy: pd.DataFrame | None, vix: pd.DataFrame | None,
                     min_price: float = 5.0, min_dollar_volume: float = 5e6) -> list[LeaderDip]:
    ranks = compute_universe_momentum_ranks({t: d["close"] for t, d in histories.items() if len(d)})
    mkt = market_state(spy, vix)
    out = []
    for t, df in histories.items():
        if df.empty or df["close"].iloc[-1] < min_price:
            continue
        if (df["close"] * df["volume"]).iloc[-20:].mean() < min_dollar_volume:
            continue
        s = evaluate(t, df, ranks.get(t), mkt)
        if s is not None:
            out.append(s)
    grade_order = {"A": 0, "B": 1, "C": 2}
    return sorted(out, key=lambda s: (grade_order[s.grade], s.dip_atr))
