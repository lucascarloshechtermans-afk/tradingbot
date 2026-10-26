"""The NASDAQ test universe (no side effects, shared by the daily and the 4H backtest): every NASDAQ-listed common
stock / ADR in nasdaqlisted.txt (nasdaqtrader.com, 2026-10-24; no ETFs, warrants, rights, units, preferreds) that is in
the Swing 20/21 development universe (~70% of NASDAQ; the other ~30% is the 20/21 project's sealed random holdout)."""
from __future__ import annotations

import os

import pandas as pd

from indicator_lab.twenty import data20

LIST = os.path.join(os.path.dirname(__file__), "nasdaqlisted.txt")


def nasdaq(pool=None) -> list[str]:
    """pool: the ticker set to intersect with (default the 20/21 development universe)."""
    d = pd.read_csv(LIST, sep="|")
    d = d[d["Symbol"].notna() & ~d["Symbol"].astype(str).str.contains("File Creation")]
    bad = r"Warrant|Right|Unit|Preferred|Notes|Debenture|Subordinated"
    cs = d[(d.ETF == "N") & (d["Test Issue"] == "N") & ~d["Security Name"].str.contains(bad, case=False, regex=True)
           & ~d.Symbol.astype(str).str.contains(r"[\.\$]")]
    return sorted(set(cs.Symbol) & set(data20.DEV if pool is None else pool))
