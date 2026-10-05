"""Technical market regime from the benchmark chart (SPY) -- price, moving
averages, structure, ADX and volatility only. Used to interpret setups in
context, never for portfolio or account risk."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.core import compute_indicators, normalize
from ta.structure import assess_trend, structure_events
from ta.swings import find_swings

REGIME_NL = {"trending_bullish": "trend omhoog", "trending_bearish": "trend omlaag", "range_bound": "zijwaarts",
             "potential_transition": "mogelijke trendwissel"}
VOL_NL = {"expansion": "volatiliteit zet uit", "contraction": "volatiliteit krimpt", "normal": "normale volatiliteit"}


@dataclass
class Regime:
    label: str
    volatility: str
    trend_label: str
    adx: float
    vix: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def label_nl(self) -> str:
        return REGIME_NL.get(self.label, self.label)

    def breakout_context(self) -> str:
        if self.label == "trending_bullish":
            return "Markt in een opwaartse trend: breakouts met volume passen bij de omgeving."
        if self.label == "range_bound":
            return "Markt zijwaarts: wacht bij breakouts op bevestiging (tweede slot boven het niveau, volume)."
        if self.label == "trending_bearish":
            return "Markt in een neerwaartse trend: long-breakouts gaan tegen de markt in -- extra voorzichtig interpreteren."
        return "Markt mogelijk aan het kantelen: setups in beide richtingen kunnen falen; wacht op bevestiging."


def classify_regime(spy: pd.DataFrame, vix: pd.DataFrame | None = None) -> Regime:
    d = normalize(spy)
    if len(d) < 220:
        return Regime("range_bound", "normal", "n/a", np.nan, notes=["te weinig SPY-data voor een regime"])
    ind = compute_indicators(d)
    sw = find_swings(d, 5, ind["atr"])
    ev, st = structure_events(d, sw)
    tr = assess_trend(d, ind, sw, ev, st)
    c = d["close"]
    sma200 = ind["sma200"]
    crossed = bool(((c > sma200) != (c.shift(1) > sma200.shift(1))).iloc[-10:].any())
    adx = ind.last("adx")
    if tr.label in ("potential_reversal_up", "potential_reversal_down") or crossed:
        label = "potential_transition"
    elif tr.direction > 0 and c.iloc[-1] > sma200.iloc[-1] and adx >= 18:
        label = "trending_bullish"
    elif tr.direction < 0 and c.iloc[-1] < sma200.iloc[-1] and adx >= 18:
        label = "trending_bearish"
    else:
        label = "range_bound"
    hvp = ind.last("hv20_pct")
    ratio = ind.last("atr10") / ind.last("atr50")
    vol = "expansion" if (hvp > 0.8 or ratio > 1.3) else ("contraction" if (hvp < 0.2 or ratio < 0.8) else "normal")
    vix_last = None
    if vix is not None and len(vix):
        vix_last = float(normalize(vix)["close"].iloc[-1])
    notes = [f"SPY: {tr.label_nl}, ADX {adx:.0f}, {'boven' if c.iloc[-1] > sma200.iloc[-1] else 'onder'} de SMA200; "
             f"volatiliteit-percentiel {hvp * 100:.0f}" + (f"; VIX {vix_last:.1f}" if vix_last else "")]
    return Regime(label, vol, tr.label, adx, vix_last, notes)
