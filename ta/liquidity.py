"""Liquidity / market-structure events from observable price only.

Nothing here claims to know where stop orders sit. 'Equal highs' are simply
two or more confirmed swing highs within 0.15 ATR of each other that have not
been closed through -- an area where many traders' reference points coincide.
A 'sweep' is a bar that trades beyond such a level but closes back inside it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.core import Indicators
from ta.swings import Swing, known_swings


@dataclass
class LiquidityEvent:
    kind: str          # sweep_high | sweep_low | failed_breakout | failed_breakdown | reclaim | displacement_up | displacement_down
    i: int
    date: pd.Timestamp
    level: float
    note: str


@dataclass
class Gap:
    direction: str     # bull | bear
    i: int             # middle candle of the three
    date: pd.Timestamp
    low: float
    high: float
    status: str        # open | retested | filled


@dataclass
class LiquidityAssessment:
    equal_highs: list[float] = field(default_factory=list)
    equal_lows: list[float] = field(default_factory=list)
    events: list[LiquidityEvent] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _pools(sw: list[Swing], atr: float, closes: np.ndarray, kind: str) -> list[float]:
    out = []
    pts = [s for s in sw if s.kind == kind]
    for a_idx in range(len(pts)):
        for b_idx in range(a_idx + 1, len(pts)):
            a, b = pts[a_idx], pts[b_idx]
            if b.i - a.i >= 5 and abs(a.price - b.price) <= 0.15 * atr:
                lvl = max(a.price, b.price) if kind == "H" else min(a.price, b.price)
                after = closes[b.i + 1:]
                taken = (after > lvl).any() if kind == "H" else (after < lvl).any()
                if not taken and not any(abs(lvl - x) <= 0.15 * atr for x in out):
                    out.append(float(lvl))
    return out


def assess_liquidity(df: pd.DataFrame, ind: Indicators, swings: list[Swing], recent: int = 10) -> LiquidityAssessment:
    n = len(df)
    t = n - 1
    atr_s = ind["atr"].to_numpy()
    atr = float(atr_s[-1]) if np.isfinite(atr_s[-1]) else np.nan
    if not np.isfinite(atr) or n < 30:
        return LiquidityAssessment()
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    la = LiquidityAssessment()
    known = [s for s in known_swings(swings, t) if s.i >= t - 120]
    la.equal_highs = _pools(known, atr, c, "H")
    la.equal_lows = _pools(known, atr, c, "L")
    for j in range(max(1, n - recent), n):
        prior = [s for s in known_swings(swings, j - 1) if s.i >= j - 120]
        hs = [s.price for s in prior if s.kind == "H"][-3:]
        ls = [s.price for s in prior if s.kind == "L"][-3:]
        for lvl in hs:
            if h[j] > lvl and c[j] < lvl:
                la.events.append(LiquidityEvent("sweep_high", j, df.index[j], lvl,
                                                f"{df.index[j]:%d-%m}: boven swing high {lvl:,.2f} geweest, onder gesloten (sweep)"))
                break
        for lvl in ls:
            if lo[j] < lvl and c[j] > lvl:
                la.events.append(LiquidityEvent("sweep_low", j, df.index[j], lvl,
                                                f"{df.index[j]:%d-%m}: onder swing low {lvl:,.2f} geweest, erboven gesloten (sweep + reclaim)"))
                break
        # close beyond a swing level, then back inside within 5 bars
        for lvl in hs:
            k = next((k for k in range(max(1, j - 5), j) if c[k] > lvl and c[k - 1] <= lvl), None)
            if k is not None and c[j] < lvl and (c[k:j] > lvl).all():
                la.events.append(LiquidityEvent("failed_breakout", j, df.index[j], lvl,
                                                f"Mislukte breakout: {df.index[k]:%d-%m} boven {lvl:,.2f}, {df.index[j]:%d-%m} er weer onder"))
                break
        for lvl in ls:
            k = next((k for k in range(max(1, j - 5), j) if c[k] < lvl and c[k - 1] >= lvl), None)
            if k is not None and c[j] > lvl and (c[k:j] < lvl).all():
                la.events.append(LiquidityEvent("failed_breakdown", j, df.index[j], lvl,
                                                f"Valse breakdown: {df.index[k]:%d-%m} onder {lvl:,.2f}, {df.index[j]:%d-%m} heroverd"))
                break
        rng, body = h[j] - lo[j], abs(c[j] - o[j])
        aj = atr_s[j - 1] if np.isfinite(atr_s[j - 1]) else atr
        if rng >= 2 * aj and body >= 0.7 * rng:
            d = "displacement_up" if c[j] > o[j] else "displacement_down"
            la.events.append(LiquidityEvent(d, j, df.index[j], c[j],
                                            f"{df.index[j]:%d-%m}: displacement-kaars {'omhoog' if c[j] > o[j] else 'omlaag'} "
                                            f"({rng / aj:.1f} ATR, body {body / rng * 100:.0f}%)"))
    for i in range(max(2, n - 60), n):
        if lo[i] > h[i - 2] and lo[i] - h[i - 2] >= 0.1 * atr:
            g_lo, g_hi, d = h[i - 2], lo[i], "bull"
            later = lo[i + 1:]
            status = "filled" if (later <= g_lo).any() else ("retested" if (later < g_hi).any() else "open")
        elif h[i] < lo[i - 2] and lo[i - 2] - h[i] >= 0.1 * atr:
            g_lo, g_hi, d = h[i], lo[i - 2], "bear"
            later = h[i + 1:]
            status = "filled" if (later >= g_hi).any() else ("retested" if (later > g_lo).any() else "open")
        else:
            continue
        la.gaps.append(Gap(d, i - 1, df.index[i - 1], float(g_lo), float(g_hi), status))
    # one event per (kind, level): keep the latest
    dedup: dict[tuple[str, int], LiquidityEvent] = {}
    for e in la.events:
        dedup[(e.kind, int(round(e.level / (0.3 * atr))))] = e
    la.events = sorted(dedup.values(), key=lambda e: e.i)
    if la.equal_highs:
        la.notes.append("Equal highs (niet doorbroken) op " + ", ".join(f"{x:,.2f}" for x in la.equal_highs[-3:]))
    if la.equal_lows:
        la.notes.append("Equal lows (niet doorbroken) op " + ", ".join(f"{x:,.2f}" for x in la.equal_lows[-3:]))
    la.notes += [e.note for e in la.events[-4:]]
    open_g = [g for g in la.gaps if g.status != "filled"][-3:]
    for g in open_g:
        la.notes.append(f"Fair value gap {'omhoog' if g.direction == 'bull' else 'omlaag'} {g.low:,.2f}-{g.high:,.2f} "
                        f"({g.date:%d-%m}), {'nog open' if g.status == 'open' else 'al hertest'}")
    return la
