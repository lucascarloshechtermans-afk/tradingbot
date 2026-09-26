"""LEADER DIP -- a disciplined entry: buy a short-term dip in a momentum leader.

  * composite momentum rank >= 80 among the scanned universe
    (63/126/252-day returns, last 5 days skipped)
  * 5-day move <= -1.0 ATR (the dip)
Trade plan: buy the next session's open, stop 2.5 ATR below the fill, no fixed
target, exit at the close of the 10th session.

What the research says (README, "Research round 4"; 966 S&P 500/400 stocks,
2008-2026, four validation cells): NO daily price or earnings setup -- this
one included -- beat a random eligible stock bought on the SAME day. Round 3's
grades (deep dip + ATR% >= 3 in a stressed market) were +0.16..+0.19R in
2022-2026 but -0.03R vs random over 2008-2021; the "edge" of dips in earlier
rounds came from a biased baseline and from market timing that stopped working
after 2021. So the grade is no longer a claim of edge; it is a RISK DIAL:

  * N (normal): SPY above its 200-day SMA -> normal size (0.5% account risk)
  * H (half):   SPY below its 200-day SMA -> half size (0.25%)
The 200-day trend filter is the one rule that held in every period tested
(1993-2007, 2008-2021, 2022-2026): it cut SPY's max drawdown from 47/52/25%
to 29/21/21% (at the cost of some return).

The deep-dip / VIX / 50-day / ATR checks are still reported as context only.
Why keep a dip entry at all: it is not worse than random (breakouts at a new
high were slightly WORSE than random in 3 of 4 cells), it gives a defined
stop, and it stops you from chasing extended moves.
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
    out = {"vix": None, "spy_below_50": None, "spy_below_200": None}
    if vix is not None and len(vix):
        out["vix"] = float(vix["close"].dropna().iloc[-1])
    if spy is not None and len(spy) >= 50:
        c = spy["close"].dropna()
        out["spy_below_50"] = bool(c.iloc[-1] < c.rolling(50).mean().iloc[-1])
        if len(c) >= 200:
            out["spy_below_200"] = bool(c.iloc[-1] < c.rolling(200).mean().iloc[-1])
    return out


def grade_for(market: dict, deep_dip: bool = False, moves: bool = False) -> str:
    """Risk dial, not an edge claim (module docstring): N = normal size while
    SPY is above its 200-day SMA (or unknown), H = half size below it.
    deep_dip / moves are accepted for compatibility and deliberately ignored:
    they did not beat random entries over 2008-2021."""
    return "H" if market.get("spy_below_200") else "N"


RISK_PCT = {"N": 0.5, "H": 0.25}


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
    grade = grade_for(market)
    if grade == "H":
        missing.append("SPY below its 200-day SMA: half size (0.25% risk) -- the trend filter is the one rule "
                       "that reduced drawdowns in every period tested")
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
    return sorted(out, key=lambda s: s.dip_atr)


@dataclass
class DipAlert:
    """A momentum leader that is NOT dipping yet, with the prices at which it
    would qualify on the next session -- for setting alerts."""
    ticker: str
    close: float
    momentum_rank: float
    atr: float
    alert_price: float       # next close <= this -> 5-day move <= -1 ATR (setup)
    deep_dip_price: float    # close <= this -> >= 1 ATR under the 21 EMA (confirmation)
    atr_pct: float
    daily: pd.DataFrame | None = None

    @property
    def distance_pct(self) -> float:
        return (self.close / self.alert_price - 1) * 100


def dip_alerts(histories: dict[str, pd.DataFrame], min_price: float = 5.0, min_dollar_volume: float = 5e6,
               top: int = 15) -> list[DipAlert]:
    """Leaders (momentum >= 80) closest to their dip trigger. For the next
    session's 5-day move the reference close is today's close[-4]: the setup
    fires if the next close <= close[-4] - 1 ATR."""
    ranks = compute_universe_momentum_ranks({t: d["close"] for t, d in histories.items() if len(d)})
    out = []
    for t, df in histories.items():
        df = df.dropna(subset=["open", "high", "low", "close"])
        mr = ranks.get(t)
        if mr is None or mr < MOM_MIN or len(df) < 60 or df["close"].iloc[-1] < min_price:
            continue
        if (df["close"] * df["volume"]).iloc[-20:].mean() < min_dollar_volume:
            continue
        c = df["close"]
        a = float(atr_fn(df["high"], df["low"], c, 14).iloc[-1])
        close = float(c.iloc[-1])
        if (close - float(c.iloc[-1 - DIP_LOOKBACK])) / a <= -DIP_ATR:
            continue  # already a setup
        alert = float(c.iloc[-DIP_LOOKBACK]) - DIP_ATR * a  # next session's 5-day reference close
        out.append(DipAlert(ticker=t, close=close, momentum_rank=float(mr), atr=a, alert_price=alert,
                            deep_dip_price=float(ema(c, 21).iloc[-1]) - a, atr_pct=a / close * 100, daily=df))
    return sorted(out, key=lambda x: x.distance_pct)[:top]
