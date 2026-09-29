"""Round 7: breakouts inside momentum leaders vs leaders without a breakout
(research/HYPOTHESES.md, "Round 7").   python -m research.breakout7 BIG.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import SPLIT_DATE, build_panel, simulate_rules
from research.hypotheses4 import indicators
from research.trend_systems6 import donchian_trades

CELLS = (("DEV", 1, False), ("VAL-T", 1, True), ("VAL-U", 0, False), ("FINAL", 0, True))


def cell_of(p, tr):
    late = p.dates[tr.t.to_numpy()] >= SPLIT_DATE
    half = p.half[tr.j.to_numpy()]
    return np.select([(half == 1) & ~late, (half == 1) & late, (half == 0) & ~late], ["DEV", "VAL-T", "VAL-U"], "FINAL")


def diff_stats(a: pd.DataFrame, b: pd.DataFrame, col: str = "r") -> tuple[float, float, float, float]:
    """mean(a) - mean(b) by day-matched means: t-stat over days where both exist."""
    da, db = a.groupby("t")[col].mean(), b.groupby("t")[col].mean()
    common = da.index.intersection(db.index)
    d = (da[common] - db[common]).dropna()
    t = d.mean() / (d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 2 and d.std() > 0 else np.nan
    return a[col].mean(), b[col].mean(), d.mean(), t


def main(path: str) -> int:
    p = build_panel(pd.read_pickle(path))
    I = indicators(p)  # noqa: E741
    C, V = I["C"], I["V"]
    elig = p.df(p.eligible)
    mom = (C.shift(21) / C.shift(252) - 1).where(elig)
    top50 = (mom.rank(axis=1, ascending=False) <= 50).to_numpy()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()[:, None]
    hi50 = C.rolling(50).max().shift(1)
    b1 = ((C > hi50) & (C.shift(1) <= hi50.shift(1))).fillna(False).to_numpy() & top50 & bull
    b2 = ((C > C.rolling(20).max().shift(1)) & (V > 1.5 * I["vol20"])).fillna(False).to_numpy() & top50 & bull
    rng = np.random.default_rng(20260929)
    lead_nb = top50 & bull & ~b1 & ~b2
    c1 = lead_nb & (rng.random(p.c.shape) < b1.sum() / max(lead_nb.sum(), 1) * 1.5)
    allst = p.eligible & bull
    c2 = allst & (rng.random(p.c.shape) < b1.sum() / max(allst.sum(), 1) * 1.5)
    print(f"signals: B1 {b1.sum()}, B2 {b2.sum()}, C1 {c1.sum()}, C2 {c2.sum()}", flush=True)
    res = {}
    for name, sig in (("B1 leader 50d breakout", b1), ("B2 leader 20d breakout+vol", b2),
                      ("C1 leader, no breakout", c1), ("C2 random stock", c2)):
        trend = donchian_trades(p, sig)
        trend["cell"] = cell_of(p, trend)
        fixed = simulate_rules(p, sig, stop_atr=2.5, max_hold=20)
        fixed["cell"] = cell_of(p, fixed)
        res[name] = {"trend": trend, "fixed": fixed}
        print(f"  {name}: {len(trend)} trend-exit trades (median {np.median(trend.exit_t - trend.t):.0f} bars), "
              f"{len(fixed)} fixed-exit trades", flush=True)
    for exit_name in ("trend", "fixed"):
        print(f"\n=== exit: {'next open after close < 20-day low (trailing)' if exit_name == 'trend' else '20 sessions'} "
              f"— mean R per trade; diff = day-matched difference vs control, t-stat")
        for b in ("B1 leader 50d breakout", "B2 leader 20d breakout+vol"):
            for ctrl in ("C1 leader, no breakout", "C2 random stock"):
                line = f"{b[:2]} vs {ctrl[:2]}:"
                for cell, *_ in CELLS:
                    a = res[b][exit_name]
                    c = res[ctrl][exit_name]
                    ma, mc, d, t = diff_stats(a[a.cell == cell], c[c.cell == cell])
                    line += f" | {cell} {ma:+.3f} vs {mc:+.3f} diff {d:+.3f} t {t:+.1f}"
                print(line, flush=True)
    pd.to_pickle(res, path.replace("big.pkl", "breakout7.pkl"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
