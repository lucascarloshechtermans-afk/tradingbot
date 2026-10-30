"""Volatility and compression: ATR, Bollinger / Keltner squeeze, historical
volatility, contraction / expansion, NR4 / NR7, inside-bar sequences.
Identifies conditions only -- it never predicts that a breakout will happen."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.core import Indicators


@dataclass
class VolatilityAssessment:
    atr: float
    atr_pct: float
    bb_width_pct: float           # percentile of BB width over 120 bars (0..1)
    squeeze_on: bool
    squeeze_bars: int
    squeeze_fired: str | None     # 'up' / 'down' when the squeeze released in the last 3 bars
    hv20: float
    hv_pct: float
    contraction: bool
    expansion: bool
    range10_atr: float
    inside_bars: int
    nr4: bool
    nr7: bool
    score: float = 0.0            # 0..100 'coiled' (compression) score
    notes: list[str] = field(default_factory=list)


def inside_bar_run(df: pd.DataFrame) -> int:
    h, lo = df["high"].to_numpy(), df["low"].to_numpy()
    n = 0
    for i in range(len(df) - 1, 0, -1):
        if h[i] <= h[i - 1] and lo[i] >= lo[i - 1]:
            n += 1
        else:
            break
    return n


def narrow_range(df: pd.DataFrame, n: int) -> bool:
    r = (df["high"] - df["low"]).iloc[-n:]
    return bool(len(r) == n and r.iloc[-1] <= r.min())


def assess_volatility(df: pd.DataFrame, ind: Indicators) -> VolatilityAssessment:
    sq = ind["squeeze_on"].fillna(False).to_numpy()
    run = 0
    for x in sq[::-1]:
        if x:
            run += 1
        else:
            break
    fired = None
    if len(sq) >= 4 and not sq[-1] and sq[-4:-1].any():
        fired = "up" if float(df["close"].iloc[-1]) > ind.last("kc_mid") else "down"
    atr, atr10, atr50 = ind.last("atr"), ind.last("atr10"), ind.last("atr50")
    ratio = atr10 / atr50 if np.isfinite(atr10) and np.isfinite(atr50) and atr50 > 0 else np.nan
    bbp = ind.last("bb_width_pct")
    rng10 = (df["high"].iloc[-10:].max() - df["low"].iloc[-10:].min()) / atr if np.isfinite(atr) and atr > 0 else np.nan
    today = float(df["high"].iloc[-1] - df["low"].iloc[-1])
    va = VolatilityAssessment(
        atr=atr, atr_pct=ind.last("atr_pct"), bb_width_pct=bbp, squeeze_on=bool(sq[-1]) if len(sq) else False,
        squeeze_bars=run, squeeze_fired=fired, hv20=ind.last("hv20"), hv_pct=ind.last("hv20_pct"),
        contraction=bool((np.isfinite(ratio) and ratio < 0.8) or (np.isfinite(bbp) and bbp <= 0.2)),
        expansion=bool((np.isfinite(ratio) and ratio > 1.3) or (np.isfinite(atr) and today >= 2 * atr)),
        range10_atr=rng10, inside_bars=inside_bar_run(df), nr4=narrow_range(df, 4), nr7=narrow_range(df, 7))
    s = 0.0
    s += 30 if va.squeeze_on else 0
    s += 20 * (1 - bbp) if np.isfinite(bbp) else 0
    s += 20 if va.contraction else 0
    s += 15 * np.clip((6 - rng10) / 4, 0, 1) if np.isfinite(rng10) else 0
    s += 10 if va.nr7 else (5 if va.nr4 else 0)
    s += 5 if va.inside_bars >= 1 else 0
    va.score = float(round(min(s, 100), 1))
    va.notes.append(f"ATR {atr:,.2f} ({va.atr_pct:.1f}% van de koers); BB-breedte op percentiel {bbp * 100:.0f} van 120 dagen"
                    if np.isfinite(bbp) else f"ATR {atr:,.2f}")
    if va.squeeze_on:
        va.notes.append(f"Squeeze actief: Bollinger binnen Keltner sinds {run} bars (energie bouwt op, richting onbekend)")
    if fired:
        va.notes.append(f"Squeeze losgelaten naar {'boven' if fired == 'up' else 'beneden'}")
    if va.contraction:
        va.notes.append(f"Volatiliteit krimpt (ATR10/ATR50 = {ratio:.2f})" if np.isfinite(ratio) else "Volatiliteit krimpt")
    if va.expansion:
        va.notes.append("Volatiliteit zet uit (brede kaars of ATR10 >> ATR50)")
    if va.nr7 or va.nr4:
        va.notes.append("NR7: smalste range van 7 dagen" if va.nr7 else "NR4: smalste range van 4 dagen")
    if va.inside_bars:
        va.notes.append(f"{va.inside_bars} inside bar(s) op rij")
    return va
