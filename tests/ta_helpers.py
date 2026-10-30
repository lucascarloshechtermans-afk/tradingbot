"""Synthetic OHLCV builders for the ta/ tests (no market data, no network)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def frame(closes, vol=1e6, spread=0.01, start="2024-01-01", opens=None) -> pd.DataFrame:
    c = np.asarray(closes, dtype=float)
    idx = pd.bdate_range(start, periods=len(c))
    o = np.asarray(opens, dtype=float) if opens is not None else np.r_[c[0], c[:-1]]
    hi = np.maximum(o, c) * (1 + spread)
    lo = np.minimum(o, c) * (1 - spread)
    v = np.full(len(c), vol, dtype=float) if np.isscalar(vol) else np.asarray(vol, dtype=float)
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c, "volume": v}, index=idx)


def zigzag(start: float, legs: list[float], bars_per_leg: int = 8) -> list[float]:
    """Piecewise-linear closes through start, start+legs[0], ... (each leg in price units)."""
    out = [start]
    for leg in legs:
        a = out[-1]
        out += list(np.linspace(a, a + leg, bars_per_leg + 1)[1:])
    return out


def uptrend(n: int = 300, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    legs = []
    while len(legs) * 6 < n + 12:
        legs += [8 + rng.random() * 4, -(4 + rng.random() * 2)]
    return zigzag(100, legs, 6)[:n]
