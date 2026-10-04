"""Support / resistance zones, scored -- not every old price is equally important.

Candidate points: confirmed daily swings (order 5), weekly swings (order 2,
weighted higher), and levels that were broken by a BOS/CHoCH (previous
breakout / breakdown levels). Nearby points merge into a zone (width capped at
1.5 ATR). Each zone is then measured on the actual bars:

  reaction   a touch of the zone followed, within 10 bars, by a close at least
             1 ATR away from it; touches closer than 5 bars count once
  score      reactions (35) + recency (20) + reaction size (15) + weekly
             timeframe (15) + confirmed role flip (10) + volume on reactions (5)
             + round number nearby (secondary, max 3 -- the rest of the score
             must come from price)
  role       support / resistance by position; a zone that acted as resistance
             and was then closed through is 'broken resistance -> support' (and
             mirror)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.structure import StructureEvent
from ta.swings import find_swings

ROLE_NL = {"support": "steun", "resistance": "weerstand", "flip_support": "gebroken weerstand -> steun",
           "flip_resistance": "gebroken steun -> weerstand", "at": "koers in de zone"}


@dataclass
class Zone:
    low: float
    high: float
    score: float = 0.0
    role: str = ""                 # support | resistance | flip_support | flip_resistance | at
    strength: str = "weak"         # strong | weak
    reactions: int = 0
    support_reactions: int = 0
    resistance_reactions: int = 0
    last_reaction: pd.Timestamp | None = None
    avg_reaction_atr: float = 0.0
    sources: list[str] = field(default_factory=list)
    volume_ratio: float | None = None
    round_number: float | None = None
    score_parts: dict[str, float] = field(default_factory=dict)

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2

    def describe(self) -> str:
        return (f"{self.strength} {ROLE_NL.get(self.role, self.role)} {self.low:,.2f}-{self.high:,.2f} "
                f"(score {self.score:.0f}, {self.reactions} reacties)")


def _weekly(df: pd.DataFrame) -> pd.DataFrame:
    idx = df.index.tz_localize(None) if getattr(df.index, "tz", None) is not None else df.index
    d = df.set_axis(idx)
    w = d.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    if len(w) and len(idx) and idx[-1].weekday() != 4:   # closed weeks only: drop the unfinished current week
        w = w.iloc[:-1]
    return w


def _round_number(lo: float, hi: float) -> float | None:
    mid = (lo + hi) / 2
    step = 10 ** np.floor(np.log10(max(mid, 1e-9)))
    for s in (step, step / 2, step / 4):
        r = round(mid / s) * s
        if lo - 0.1 * (hi - lo) <= r <= hi + 0.1 * (hi - lo):
            return float(r)
    return None


def find_zones(df: pd.DataFrame, atr: pd.Series, events: list[StructureEvent] | None = None,
               rvol: pd.Series | None = None, lookback: int = 500, max_zones: int = 12) -> list[Zone]:
    d = df.iloc[-lookback:]
    if len(d) < 30:
        return []
    a_now = float(atr.iloc[-1])
    if not np.isfinite(a_now) or a_now <= 0:
        return []
    close = float(d["close"].iloc[-1])
    offset = len(df) - len(d)
    pts: list[tuple[float, str]] = []
    for s in find_swings(d, order=5):
        pts.append((s.price, "daily swing"))
    w = _weekly(d)
    if len(w) >= 10:
        for s in find_swings(w, order=2):
            pts.append((s.price, "weekly swing"))
    for e in events or []:
        if e.i >= offset:
            pts.append((e.level, "breakout level" if e.direction == "bull" else "breakdown level"))
    if not pts:
        return []
    pts.sort()
    tol, cap = 0.5 * a_now, 1.5 * a_now
    clusters: list[list[tuple[float, str]]] = [[pts[0]]]
    for p, src in pts[1:]:
        cl = clusters[-1]
        mean = sum(x for x, _ in cl) / len(cl)
        if p - mean <= tol and p - cl[0][0] <= cap:
            cl.append((p, src))
        else:
            clusters.append([(p, src)])

    hi_a, lo_a, cl_a = d["high"].to_numpy(), d["low"].to_numpy(), d["close"].to_numpy()
    atr_a = atr.iloc[-len(d):].to_numpy()
    rv = rvol.iloc[-len(d):].to_numpy() if rvol is not None else None
    n = len(d)
    zones: list[Zone] = []
    for cl in clusters:
        lo, hi = min(p for p, _ in cl), max(p for p, _ in cl)
        if hi - lo < 0.4 * a_now:
            m = (hi + lo) / 2
            lo, hi = m - 0.2 * a_now, m + 0.2 * a_now
        z = Zone(low=lo, high=hi, sources=sorted({s for _, s in cl}))
        sizes, vols, last_j = [], [], -10
        sup = res = 0
        reaction_dirs: list[tuple[int, str]] = []
        for j in range(1, n):
            aj = atr_a[j] if np.isfinite(atr_a[j]) else a_now
            if not (lo_a[j] <= hi + 0.1 * aj and hi_a[j] >= lo - 0.1 * aj) or j - last_j < 10:
                continue
            fut_c = cl_a[j + 1:j + 11]
            if len(fut_c) == 0:
                continue
            # a reaction needs an approach from one side and a move away to the SAME side:
            # from above and bouncing = support; from below and rejected = resistance
            if cl_a[j - 1] > hi:
                broke = np.flatnonzero(fut_c < lo - 0.25 * aj)
                held = fut_c[:broke[0]] if len(broke) else fut_c
                move = (held.max() - hi) / aj if len(held) else 0.0
                if move < 1:
                    continue
                sup += 1
                reaction_dirs.append((j, "sup"))
            elif cl_a[j - 1] < lo:
                broke = np.flatnonzero(fut_c > hi + 0.25 * aj)
                held = fut_c[:broke[0]] if len(broke) else fut_c
                move = (lo - held.min()) / aj if len(held) else 0.0
                if move < 1:
                    continue
                res += 1
                reaction_dirs.append((j, "res"))
            else:
                continue
            sizes.append(min(move, 5))
            last_j = j
            z.last_reaction = d.index[j]
            if rv is not None and np.isfinite(rv[j]):
                vols.append(rv[j])
        z.support_reactions, z.resistance_reactions = sup, res
        z.reactions = sup + res
        z.avg_reaction_atr = float(np.mean(sizes)) if sizes else 0.0
        z.volume_ratio = float(np.mean(vols)) if vols else None
        # position and role
        if close > hi:
            z.role = "support"
        elif close < lo:
            z.role = "resistance"
        else:
            z.role = "at"
        # role flip: the zone acted >= 2x as resistance BEFORE price closed up through it (or mirror),
        # within the last 250 bars; 'confirmed' when it has held at least once from the new side since
        crossed = None
        for j in range(n - 1, max(n - 250, 0), -1):
            if cl_a[j] > hi and cl_a[j - 1] <= hi:
                crossed = ("up", j)
                break
            if cl_a[j] < lo and cl_a[j - 1] >= lo:
                crossed = ("down", j)
                break
        flipped = False
        if crossed:
            j0 = crossed[1]
            if z.role == "support" and crossed[0] == "up" and reaction_dirs and \
                    sum(1 for jj, dd in reaction_dirs if dd == "res" and jj < j0) >= 2:
                z.role, flipped = "flip_support", any(jj > j0 and dd == "sup" for jj, dd in reaction_dirs)
            elif z.role == "resistance" and crossed[0] == "down" and reaction_dirs and \
                    sum(1 for jj, dd in reaction_dirs if dd == "sup" and jj < j0) >= 2:
                z.role, flipped = "flip_resistance", any(jj > j0 and dd == "res" for jj, dd in reaction_dirs)
        z.round_number = _round_number(lo, hi)
        bars_since = n - 1 - last_j if z.reactions else n
        parts = {
            "reacties": 35 * min(z.reactions, 6) / 6,
            "recent": 20 * float(np.exp(-bars_since / 120)) if z.reactions else 0.0,
            "reactiegrootte": 15 * min(z.avg_reaction_atr / 3, 1),
            "weekgrafiek": 15.0 if "weekly swing" in z.sources else 0.0,
            "rolwissel": 10.0 if flipped else (4.0 if z.role.startswith("flip") else 0.0),
            "volume": 5.0 if z.volume_ratio is not None and z.volume_ratio >= 1.3 else 0.0,
            "rond getal": 3.0 if z.round_number is not None else 0.0,
        }
        z.score_parts = {k: round(v, 1) for k, v in parts.items()}
        z.score = round(min(sum(parts.values()), 100.0), 1)
        z.strength = "strong" if z.score >= 60 else "weak"
        zones.append(z)
    zones = [z for z in zones if (z.reactions >= 1 or "weekly swing" in z.sources) and abs(z.mid / close - 1) <= 0.35]
    zones.sort(key=lambda z: abs(z.mid - close))
    return sorted(zones[:max_zones], key=lambda z: z.low)


def nearest(zones: list[Zone], close: float, side: str) -> Zone | None:
    """side='above' -> nearest zone whose low is above close; 'below' -> highest zone below."""
    if side == "above":
        c = [z for z in zones if z.low > close]
        return min(c, key=lambda z: z.low) if c else None
    c = [z for z in zones if z.high < close]
    return max(c, key=lambda z: z.high) if c else None


def containing(zones: list[Zone], price: float, pad: float = 0.0) -> Zone | None:
    for z in zones:
        if z.low - pad <= price <= z.high + pad:
            return z
    return None
