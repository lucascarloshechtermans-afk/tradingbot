"""INDEX RSI(2) -- short-term mean reversion on index ETFs (README, "Research round 6").

Pure price data: for SPY, QQQ, IWM and DIA
  * BUY at the next open when the close is above the 200-day SMA and RSI(2)
    (Wilder smoothing) is below 10
  * SELL at the next open after the first close above the 5-day SMA
The one technical rule that was positive in every period and on every ETF
tested (1999-2007, 2008-2021, 2022-2026): +0.2..+0.6% per trade in ~3.5
sessions, 64-79% winners. It is in the market only ~10% of the time, so it is
a small sleeve next to the other systems, not a system on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ETFS = ("SPY", "QQQ", "IWM", "DIA")
RSI_MAX = 10.0


def rsi2_parts(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """RSI(2) with Wilder smoothing (alpha 1/2) and its average up/down moves."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    return rsi.fillna(100.0), up, dn


@dataclass
class IndexSignal:
    etf: str
    date: pd.Timestamp
    close: float
    rsi2: float
    sma5: float
    sma200: float
    state: str                 # KOOP / HOUDEN / VERKOOP / GEEN
    buy_below: float | None    # a close at/below this tomorrow gives RSI(2) < 10 (if still above the 200-day)
    sell_above: float | None   # while holding: a close above this tomorrow is above the 5-day SMA -> sell
    entry_date: pd.Timestamp | None = None

    @property
    def above_200(self) -> bool:
        return self.close > self.sma200


def buy_trigger_price(close: float, up: float, dn: float) -> float:
    """Highest next close X for which RSI(2) < 10, from the Wilder update
    up' = (up + max(X-C,0))/2, dn' = (dn + max(C-X,0))/2 and up'/dn' < 1/9."""
    gap = 9 * up - dn
    return close - gap if gap >= 0 else close + (-gap) / 9


def evaluate(etf: str, df: pd.DataFrame) -> IndexSignal | None:
    c = df["close"].dropna()
    if len(c) < 205:
        return None
    rsi, up, dn = rsi2_parts(c)
    s5, s200 = c.rolling(5).mean(), c.rolling(200).mean()
    inpos, entry = False, None
    state = "GEEN"
    for i in range(200, len(c)):
        last = i == len(c) - 1
        if not inpos and c.iloc[i] > s200.iloc[i] and rsi.iloc[i] < RSI_MAX:
            inpos, entry = True, c.index[i]
            if last:
                state = "KOOP"
        elif inpos and c.iloc[i] > s5.iloc[i]:
            inpos = False
            if last:
                state = "VERKOOP"
    if state == "GEEN" and inpos:
        state = "HOUDEN"
    close = float(c.iloc[-1])
    holding = state in ("KOOP", "HOUDEN")
    sell_above = float(c.iloc[-4:].mean()) if holding else None  # X > (sum of last 4 + X)/5  <=>  X > mean(last 4)
    buy_below = None if holding else buy_trigger_price(close, float(up.iloc[-1]), float(dn.iloc[-1]))
    return IndexSignal(etf=etf, date=c.index[-1], close=close, rsi2=float(rsi.iloc[-1]), sma5=float(s5.iloc[-1]),
                       sma200=float(s200.iloc[-1]), state=state, buy_below=buy_below, sell_above=sell_above,
                       entry_date=entry if holding or state == "VERKOOP" else None)


def index_signals(histories: dict[str, pd.DataFrame]) -> list[IndexSignal]:
    out = []
    for etf in ETFS:
        df = histories.get(etf)
        if df is not None and len(df):
            s = evaluate(etf, df)
            if s is not None:
                out.append(s)
    return out
