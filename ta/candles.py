"""Candlestick patterns judged in context.

Shape rules are fixed fractions of the candle's own range / body. A pattern's
significance then depends on WHERE it appears: at a support/resistance zone or
key moving average, after a move it could reverse, with volume, with a
reasonable size, and whether the next candle confirmed it. The same hammer in
the middle of nowhere scores far lower than at a strong support zone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.core import Indicators
from ta.levels import Zone

NAMES_NL = {
    "bullish_engulfing": "bullish engulfing", "bearish_engulfing": "bearish engulfing", "hammer": "hammer",
    "hanging_man": "hanging man", "shooting_star": "shooting star", "inverted_hammer": "inverted hammer",
    "morning_star": "morning star", "evening_star": "evening star", "doji": "doji", "dragonfly_doji": "dragonfly doji",
    "gravestone_doji": "gravestone doji", "piercing": "piercing pattern", "dark_cloud": "dark cloud cover",
    "inside_bar": "inside bar", "outside_bar": "outside bar", "bullish_marubozu": "bullish marubozu",
    "bearish_marubozu": "bearish marubozu",
}
BULLISH = {"bullish_engulfing", "hammer", "inverted_hammer", "morning_star", "piercing", "dragonfly_doji", "bullish_marubozu"}
BEARISH = {"bearish_engulfing", "hanging_man", "shooting_star", "evening_star", "dark_cloud", "gravestone_doji", "bearish_marubozu"}
REVERSAL = (BULLISH | BEARISH) - {"bullish_marubozu", "bearish_marubozu"}


@dataclass
class CandleSignal:
    name: str
    direction: str            # bull | bear | neutral
    i: int
    date: pd.Timestamp
    score: float              # 0..100 significance
    significance: str         # low | medium | high
    confirmation: str         # confirmed | failed | pending
    context: list[str] = field(default_factory=list)

    @property
    def name_nl(self) -> str:
        return NAMES_NL.get(self.name, self.name)


def shapes_at(df: pd.DataFrame, i: int, atr: float) -> list[str]:
    """Candle shapes completed on bar i (uses bars i-2..i only)."""
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    if i < 2:
        return []
    out = []
    rng = h[i] - lo[i]
    if rng <= 0:
        return out
    body = abs(c[i] - o[i])
    upper, lower = h[i] - max(o[i], c[i]), min(o[i], c[i]) - lo[i]
    prior_up = c[i - 1] > c[max(i - 6, 0)]
    pb_o, pb_c = o[i - 1], c[i - 1]
    pbody = abs(pb_c - pb_o)
    if body <= 0.1 * rng:
        if upper <= 0.1 * rng and lower >= 0.6 * rng:
            out.append("dragonfly_doji")
        elif lower <= 0.1 * rng and upper >= 0.6 * rng:
            out.append("gravestone_doji")
        else:
            out.append("doji")
    elif lower >= 2 * body and upper <= 0.3 * rng:
        out.append("hanging_man" if prior_up else "hammer")
    elif upper >= 2 * body and lower <= 0.3 * rng:
        out.append("shooting_star" if prior_up else "inverted_hammer")
    if pb_c < pb_o and c[i] > o[i] and o[i] <= pb_c and c[i] >= pb_o and body > pbody:
        out.append("bullish_engulfing")
    if pb_c > pb_o and c[i] < o[i] and o[i] >= pb_c and c[i] <= pb_o and body > pbody:
        out.append("bearish_engulfing")
    if pb_c < pb_o and pbody >= 0.5 * (h[i - 1] - lo[i - 1]) and o[i] < pb_c and (pb_o + pb_c) / 2 < c[i] < pb_o:
        out.append("piercing")
    if pb_c > pb_o and pbody >= 0.5 * (h[i - 1] - lo[i - 1]) and o[i] > pb_c and pb_o < c[i] < (pb_o + pb_c) / 2:
        out.append("dark_cloud")
    b2 = abs(c[i - 2] - o[i - 2])
    if b2 > 0 and np.isfinite(atr) and b2 >= 0.6 * atr and abs(c[i - 1] - o[i - 1]) <= 0.3 * b2:
        if c[i - 2] < o[i - 2] and c[i] > o[i] and c[i] > (o[i - 2] + c[i - 2]) / 2:
            out.append("morning_star")
        if c[i - 2] > o[i - 2] and c[i] < o[i] and c[i] < (o[i - 2] + c[i - 2]) / 2:
            out.append("evening_star")
    if h[i] <= h[i - 1] and lo[i] >= lo[i - 1]:
        out.append("inside_bar")
    if h[i] > h[i - 1] and lo[i] < lo[i - 1]:
        out.append("outside_bar")
    if body >= 0.9 * rng and np.isfinite(atr) and rng >= atr:
        out.append("bullish_marubozu" if c[i] > o[i] else "bearish_marubozu")
    return out


def evaluate_candles(df: pd.DataFrame, ind: Indicators, zones: list[Zone], trend_direction: int,
                     lookback: int = 3) -> list[CandleSignal]:
    atr_s = ind["atr"].to_numpy()
    rvol = ind["rvol"].to_numpy() if "rvol" in ind else None
    c, h, lo = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
    ema21, sma50 = ind["ema21"].to_numpy(), ind["sma50"].to_numpy()
    n = len(df)
    out: list[CandleSignal] = []
    for i in range(max(2, n - lookback), n):
        atr = atr_s[i] if np.isfinite(atr_s[i]) else np.nan
        for name in shapes_at(df, i, atr):
            direction = "bull" if name in BULLISH else ("bear" if name in BEARISH else "neutral")
            ctx, s = [], 20.0
            if np.isfinite(atr):
                key_px = lo[i] if direction == "bull" else h[i]
                zone_hit = None
                for z in zones:
                    if z.low - 0.5 * atr <= key_px <= z.high + 0.5 * atr:
                        zone_hit = z
                        break
                if zone_hit is not None:
                    s += 30 if zone_hit.strength == "strong" else 18
                    ctx.append(f"op een {zone_hit.strength} zone {zone_hit.low:,.2f}-{zone_hit.high:,.2f}")
                elif any(np.isfinite(m) and abs(key_px - m) <= 0.5 * atr for m in (ema21[i], sma50[i])):
                    s += 15
                    ctx.append("aan de EMA21/SMA50")
                else:
                    ctx.append("niet op een belangrijk niveau (midden in de grafiek)")
            prior_down = c[i - 1] < c[max(i - 6, 0)]
            if name in REVERSAL:
                if (direction == "bull" and prior_down) or (direction == "bear" and not prior_down):
                    s += 15
                    ctx.append("na een beweging die hij kan keren")
                else:
                    s -= 10
                    ctx.append("zonder voorafgaande beweging om te keren")
            if direction != "neutral" and trend_direction != 0:
                with_trend = (direction == "bull") == (trend_direction > 0)
                s += 10 if with_trend else 0
                ctx.append("met de trend mee" if with_trend else "tegen de trend in")
            if rvol is not None and np.isfinite(rvol[i]):
                if rvol[i] >= 1.2:
                    s += 10
                    ctx.append(f"met volume (RVOL {rvol[i]:.1f})")
                else:
                    ctx.append(f"zonder extra volume (RVOL {rvol[i]:.1f})")
            if np.isfinite(atr):
                size = (h[i] - lo[i]) / atr
                if size < 0.5:
                    s -= 10
                    ctx.append(f"kleine kaars ({size:.1f} ATR)")
                elif size >= 1:
                    s += 5
            if i == n - 1:
                conf = "pending"
            elif direction == "bull":
                conf = "confirmed" if c[i + 1:].max() > h[i] else ("failed" if c[i + 1:].min() < lo[i] else "pending")
            elif direction == "bear":
                conf = "confirmed" if c[i + 1:].min() < lo[i] else ("failed" if c[i + 1:].max() > h[i] else "pending")
            else:
                conf = "pending"
            if conf == "confirmed":
                s += 10
            elif conf == "failed":
                s -= 20
            s = float(np.clip(s, 0, 100))
            out.append(CandleSignal(name, direction, i, df.index[i], s, "high" if s >= 60 else ("medium" if s >= 40 else "low"),
                                    conf, ctx))
    return out
