"""Swing points with an explicit 'known_at' bar.

A swing high at bar i is the highest high of bars i-order .. i+order; it can
only be known once bar i+order has closed. Every consumer must use
`known_swings(swings, t)` (or the frame cut at t), never the raw swing list,
when it reasons about bar t.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd



def _swing_mask(x: np.ndarray, order: int, high: bool) -> np.ndarray:
    """Bar i is a swing high when it is the highest of i-order .. i+order and
    STRICTLY higher than the `order` bars before it, so a flat top counts at its
    FIRST bar. Everything needed is known at bar i + order (no later bar can
    move or remove the swing)."""
    v = pd.Series(x if high else -x)
    win = v.rolling(2 * order + 1, center=True).max()
    before = v.shift(1).rolling(order).max()
    return ((v == win) & (v > before)).to_numpy()


@dataclass
class Swing:
    kind: str            # "H" or "L"
    i: int               # bar position of the extreme
    date: pd.Timestamp
    price: float
    known_at: int        # first bar position at which the swing is confirmed
    label: str = ""      # HH / LH / EH (equal) for highs, HL / LL / EL for lows


def find_swings(df: pd.DataFrame, order: int = 3, atr: pd.Series | None = None, equal_tol_atr: float = 0.1) -> list[Swing]:
    """Confirmed swing highs/lows, chronologically, each labelled against the
    previous swing of the same kind (equal within equal_tol_atr * ATR)."""
    if len(df) < 2 * order + 1:
        return []
    hi_mask = _swing_mask(df["high"].to_numpy(dtype=float), order, True)
    lo_mask = _swing_mask(df["low"].to_numpy(dtype=float), order, False)
    n = len(df)
    out: list[Swing] = []
    for i in np.flatnonzero(hi_mask):
        if i + order < n:
            out.append(Swing("H", int(i), df.index[i], float(df["high"].iloc[i]), int(i + order)))
    for i in np.flatnonzero(lo_mask):
        if i + order < n:
            out.append(Swing("L", int(i), df.index[i], float(df["low"].iloc[i]), int(i + order)))
    out.sort(key=lambda s: (s.i, s.kind))
    a = atr.to_numpy() if atr is not None else None
    prev: dict[str, Swing] = {}
    for s in out:
        p = prev.get(s.kind)
        if p is not None:
            tol = equal_tol_atr * a[s.i] if a is not None and np.isfinite(a[s.i]) else 0.001 * s.price
            if abs(s.price - p.price) <= tol:
                s.label = "EH" if s.kind == "H" else "EL"
            elif s.kind == "H":
                s.label = "HH" if s.price > p.price else "LH"
            else:
                s.label = "HL" if s.price > p.price else "LL"
        prev[s.kind] = s
    return out


def known_swings(swings: list[Swing], t: int) -> list[Swing]:
    return [s for s in swings if s.known_at <= t]


def last_of(swings: list[Swing], kind: str, n: int = 1) -> list[Swing]:
    return [s for s in swings if s.kind == kind][-n:]
