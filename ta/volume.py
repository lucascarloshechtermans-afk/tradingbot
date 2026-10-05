"""Volume family. Every metric reports 'unavailable' instead of guessing when
the frame has no usable volume (e.g. some indices / FX)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.core import Indicators
from ta.swings import Swing, known_swings


@dataclass
class VolumeAssessment:
    available: bool
    rvol: float = np.nan
    spike: bool = False
    climax: bool = False
    up_down_ratio: float = np.nan
    obv_trend: str = "n/a"
    ad_trend: str = "n/a"
    cmf: float = np.nan
    pullback_contraction: bool | None = None
    divergence: str | None = None
    score: float = 0.0            # -100..+100
    notes: list[str] = field(default_factory=list)


def _trend(series: pd.Series, n: int = 20) -> str:
    s = series.dropna()
    if len(s) < n + 1:
        return "n/a"
    rng = (s.iloc[-n * 3:].max() - s.iloc[-n * 3:].min()) or 1.0
    ch = (s.iloc[-1] - s.iloc[-n - 1]) / rng
    return "rising" if ch > 0.15 else ("falling" if ch < -0.15 else "flat")


def breakout_volume_ratio(df: pd.DataFrame, i: int, base: int = 20) -> float:
    """Volume on bar i divided by the average volume of the `base` bars before it."""
    v = df["volume"].to_numpy(dtype=float)
    if i < base or not np.isfinite(v[i]):
        return np.nan
    b = np.nanmean(v[i - base:i])
    return float(v[i] / b) if b > 0 else np.nan


def assess_volume(df: pd.DataFrame, ind: Indicators, swings: list[Swing], t: int) -> VolumeAssessment:
    if "rvol" not in ind:
        return VolumeAssessment(available=False, notes=["Volume niet beschikbaar voor dit instrument -- volumecontrole overgeslagen."])
    rvol = ind.last("rvol")
    atr = ind.last("atr")
    rng = float(df["high"].iloc[-1] - df["low"].iloc[-1])
    v = df["volume"].iloc[-50:].astype(float)
    ch = df["close"].diff().iloc[-50:]
    up_v, dn_v = v[ch > 0].sum(), v[ch < 0].sum()
    udr = float(up_v / dn_v) if dn_v > 0 else np.nan
    va = VolumeAssessment(available=True, rvol=rvol, spike=bool(np.isfinite(rvol) and rvol >= 2),
                          up_down_ratio=udr, obv_trend=_trend(ind["obv"]), ad_trend=_trend(ind["ad"]), cmf=ind.last("cmf"))
    va.climax = bool(va.spike and rvol >= 3 and np.isfinite(atr) and rng >= 2 * atr)
    known = known_swings(swings, t)
    highs = [s for s in known if s.kind == "H"]
    if highs:
        h = highs[-1]
        pull = df["volume"].iloc[h.i + 1:t + 1].astype(float)
        before = df["volume"].iloc[max(0, h.i - 20):h.i + 1].astype(float)
        if len(pull) >= 3 and before.mean() > 0 and df["close"].iloc[-1] < h.price:
            va.pullback_contraction = bool(pull.mean() / before.mean() < 0.8)
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        obv = ind["obv"].to_numpy()
        if b.price > a.price and obv[b.i] < obv[a.i]:
            va.divergence = "bearish (koers hogere top, OBV lagere top)"
    lows = [s for s in known if s.kind == "L"]
    if len(lows) >= 2 and va.divergence is None:
        a, b = lows[-2], lows[-1]
        obv = ind["obv"].to_numpy()
        if b.price < a.price and obv[b.i] > obv[a.i]:
            va.divergence = "bullish (koers lagere bodem, OBV hogere bodem)"
    s = 0.0
    s += 35 * (np.clip((udr - 1) / 0.5, -1, 1) if np.isfinite(udr) else 0)
    s += 25 * {"rising": 1, "flat": 0, "falling": -1, "n/a": 0}[va.obv_trend]
    s += 25 * (np.clip(va.cmf / 0.15, -1, 1) if np.isfinite(va.cmf) else 0)
    s += 15 * (1 if va.pullback_contraction else 0)
    va.score = float(round(s, 1))
    va.notes.append(f"RVOL {rvol:.2f} (volume t.o.v. 20-daags gemiddelde)" if np.isfinite(rvol) else "RVOL n.v.t.")
    if np.isfinite(udr):
        va.notes.append(f"Kooppdruk vs verkoopdruk (50 d): volume op stijgdagen / daaldagen = {udr:.2f}")
    va.notes.append(f"OBV {va.obv_trend}, A/D {va.ad_trend}, CMF20 {va.cmf:+.2f}" if np.isfinite(va.cmf) else f"OBV {va.obv_trend}")
    if va.pullback_contraction is not None:
        va.notes.append("Volume droogt op tijdens de pullback (gezond)" if va.pullback_contraction
                        else "Geen volumekrimp tijdens de pullback (verkopers actief)")
    if va.climax:
        va.notes.append("Climax-volume: RVOL >= 3 met een range >= 2 ATR -- vaak einde van een beweging, geen begin")
    if va.divergence:
        va.notes.append(f"Volume-prijs divergentie: {va.divergence}")
    va.notes = [n.replace("Kooppdruk", "Koopdruk") for n in va.notes]
    return va
