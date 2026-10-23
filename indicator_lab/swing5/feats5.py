"""Extra per-bar inputs of the swing v5 round, added to a swing4.lab context (no data-mode side effects, so the
development scripts and the single holdout run share exactly the same definitions)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from indicator_lab.evaluate import get

SECTOR_ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]


def add(ctx: dict) -> dict:
    spy = get("SPY")["close"]
    sect = pd.concat({e: get(e)["close"].pct_change() for e in SECTOR_ETFS}, axis=1)
    for t, cx in ctx.items():
        cx["_t"] = t
        idx = cx["arr"]["index"]
        c = pd.Series(cx["arr"]["c"], index=idx)
        rs = c / spy.reindex(idx).ffill()
        for k in (63, 126, 252):   # relative-strength line (stock / SPY) at a new k-day high (vs the prior k closes)
            cx["x"][f"rs_hi{k}"] = (rs >= rs.rolling(k).max().shift(1)).to_numpy(float)
        # sector proxy, point in time: the sector ETF this stock moved most like over the past year
        r = c.pct_change()
        cor = pd.concat({e: r.rolling(252, min_periods=120).corr(sect[e].reindex(idx)) for e in SECTOR_ETFS}, axis=1)
        ok = cor.notna().any(axis=1).to_numpy()
        best = np.nanargmax(np.where(cor.notna(), cor.to_numpy(), -9), axis=1)
        cx["x"]["sect_id"] = np.where(ok, best, np.nan).astype(float)
    return ctx
