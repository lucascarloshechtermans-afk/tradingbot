"""Momentum family: RSI 7/14/21, MACD, ROC, Stochastic, StochRSI, ADX/DI.

These indicators all measure the same thing (recent price change), so this
module returns ONE momentum assessment -- the scorer counts momentum once, not
once per oscillator. Overbought / oversold is interpreted in trend context.

Divergences use confirmed swing points only (Swing.known_at <= last bar) and
compare consecutive swings of the same kind 5-60 bars apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ta.core import Indicators
from ta.swings import Swing, known_swings

DIV_NL = {"regular_bull": "bullish divergentie", "regular_bear": "bearish divergentie",
          "hidden_bull": "verborgen bullish divergentie", "hidden_bear": "verborgen bearish divergentie"}


@dataclass
class Divergence:
    kind: str            # regular_bull | regular_bear | hidden_bull | hidden_bear
    oscillator: str      # rsi14 | macd_hist
    a: Swing
    b: Swing
    osc_a: float
    osc_b: float
    bars_ago: int        # since swing b

    def describe(self) -> str:
        osc = "RSI14" if self.oscillator == "rsi14" else "MACD-histogram"
        return (f"{DIV_NL[self.kind]} op {osc}: koers {self.a.price:,.2f} ({self.a.date:%d-%m}) -> {self.b.price:,.2f} "
                f"({self.b.date:%d-%m}), {osc} {self.osc_a:.1f} -> {self.osc_b:.1f}")


@dataclass
class MomentumAssessment:
    state: str                      # strong_bullish | bullish | neutral | bearish | strong_bearish
    score: float                    # -100..+100 (one number for the whole family)
    acceleration: str               # accelerating | decelerating | flat
    rsi: dict[int, float]
    macd_hist: float
    roc: dict[int, float]
    stoch: float
    stochrsi: float
    adx: float
    divergences: list[Divergence] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def find_divergences(ind: Indicators, swings: list[Swing], t: int, lookback: int = 90) -> list[Divergence]:
    out: list[Divergence] = []
    known = [s for s in known_swings(swings, t) if s.i >= t - lookback]
    for osc in ("rsi14", "macd_hist"):
        series = ind[osc].to_numpy()
        for kind in ("L", "H"):
            sw = [s for s in known if s.kind == kind][-2:]
            if len(sw) < 2:
                continue
            a, b = sw
            if not 5 <= b.i - a.i <= 60:
                continue
            oa, ob = series[a.i], series[b.i]
            if not (np.isfinite(oa) and np.isfinite(ob)):
                continue
            if kind == "L":
                if b.price < a.price and ob > oa:
                    k = "regular_bull"
                elif b.price > a.price and ob < oa:
                    k = "hidden_bull"
                else:
                    continue
            else:
                if b.price > a.price and ob < oa:
                    k = "regular_bear"
                elif b.price < a.price and ob > oa:
                    k = "hidden_bear"
                else:
                    continue
            out.append(Divergence(k, osc, a, b, float(oa), float(ob), t - b.i))
    return out


def assess_momentum(ind: Indicators, swings: list[Swing], t: int, trend_direction: int,
                    near_resistance: bool = False, broke_out: bool = False) -> MomentumAssessment:
    rsi = {w: ind.last(f"rsi{w}") for w in (7, 14, 21)}
    roc = {w: ind.last(f"roc{w}") for w in (5, 10, 20, 60)}
    hist = ind["macd_hist"]
    h_now = ind.last("macd_hist")
    macd_line = ind.last("macd")
    stoch, srsi, adx = ind.last("stoch_k"), ind.last("stochrsi_k"), ind.last("adx")
    pdi, mdi = ind.last("plus_di"), ind.last("minus_di")

    # one family score from four different angles, each capped
    parts = []
    r14 = rsi[14]
    parts.append(np.clip((r14 - 50) / 20, -1, 1) if np.isfinite(r14) else 0)                  # level
    parts.append(np.sign(macd_line) * 0.5 + np.sign(h_now) * 0.5 if np.isfinite(h_now) else 0)  # MACD regime
    parts.append(np.clip(roc[20] / 10, -1, 1) if np.isfinite(roc[20]) else 0)                 # 1-month rate
    parts.append(np.clip((pdi - mdi) / 20, -1, 1) if np.isfinite(pdi) and np.isfinite(mdi) else 0)  # directional
    score = float(np.mean(parts) * 100)

    h3 = hist.iloc[-4:].to_numpy() if len(hist) >= 4 else np.array([])
    if len(h3) == 4 and np.all(np.isfinite(h3)):
        d = np.diff(h3)
        if np.all(d > 0):
            accel = "accelerating" if h_now > 0 else "improving"
        elif np.all(d < 0):
            accel = "decelerating" if h_now > 0 else "worsening"
        else:
            accel = "flat"
    else:
        accel = "flat"

    if score >= 50:
        state = "strong_bullish"
    elif score >= 15:
        state = "bullish"
    elif score <= -50:
        state = "strong_bearish"
    elif score <= -15:
        state = "bearish"
    else:
        state = "neutral"

    notes = []
    if np.isfinite(r14) and r14 >= 70:
        notes.append(f"RSI14 {r14:.0f}: overbought" + (" -- in een sterke uptrend is dat kracht, geen verkoopsignaal op zich"
                                                       if trend_direction > 0 else " zonder uptrend: kwetsbaar"))
    if np.isfinite(r14) and r14 <= 30:
        notes.append(f"RSI14 {r14:.0f}: oversold" + (" -- in een downtrend kan dat lang aanhouden, geen koopsignaal op zich"
                                                     if trend_direction < 0 else " in een uptrend: diepe pullback"))
    divs = find_divergences(ind, swings, t)
    for dv in divs:
        notes.append(dv.describe() + f" ({dv.bars_ago} bars geleden bevestigd)")
    if broke_out:
        ok = np.isfinite(r14) and r14 > 55 and np.isfinite(h_now) and h_now > 0
        notes.append("Momentum bevestigt de breakout (RSI14 > 55, MACD-histogram positief)" if ok
                     else "Momentum bevestigt de breakout NIET (RSI14 <= 55 of MACD-histogram negatief)")
    if near_resistance and (accel in ("decelerating", "worsening") or any(d.kind == "regular_bear" for d in divs)):
        notes.append("Momentum verzwakt vlak onder weerstand")
    return MomentumAssessment(state=state, score=round(score, 1), acceleration=accel, rsi=rsi, macd_hist=h_now, roc=roc,
                              stoch=stoch, stochrsi=srsi, adx=adx, divergences=divs, notes=notes)
