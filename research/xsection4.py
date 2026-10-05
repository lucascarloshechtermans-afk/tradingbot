"""Cross-sectional feature study (round 4c): which stock characteristics predict
R relative to the SAME-DAY average of all eligible stocks (no market timing)?
Samples every 5th session, research half, 2008-2021 (DEV). Also writes the
panel for later validation cells.

    python -m research.xsection4 BIG.pkl EARNINGS.pkl OUT.pkl
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.earnings4 import reaction_days
from research.engine2 import SPLIT_DATE, _simulate_all, build_panel
from research.hypotheses4 import indicators
from research.ml4 import feature_panels


def earnings_panels(p, ev) -> dict[str, np.ndarray]:
    T, N = p.c.shape
    sur = np.full((T, N), np.nan)
    ear = np.full((T, N), np.nan)
    since = np.full((T, N), np.nan)
    j, E = ev["j"].to_numpy(), ev["E"].to_numpy()
    a = (p.c[E, j] - p.c[E - 1, j]) / p.atr[E - 1, j]
    sur[E, j] = np.clip(ev["surprise"].to_numpy(dtype=float), -100, 100)
    ear[E, j] = a
    ev_mark = np.zeros((T, N))
    ev_mark[E, j] = 1
    df_s, df_e = pd.DataFrame(sur).ffill(limit=63), pd.DataFrame(ear).ffill(limit=63)
    idx = np.where(ev_mark > 0, np.arange(T)[:, None], np.nan)
    last = pd.DataFrame(idx).ffill().to_numpy()
    since = np.arange(T)[:, None] - last
    nxt = pd.DataFrame(idx).bfill().to_numpy() - np.arange(T)[:, None]  # sessions to next report (date known ahead)
    return {"last_surprise": df_s.to_numpy(), "last_ear": df_e.to_numpy(), "days_since_er": since,
            "days_to_er": nxt}


def main(big_path: str, earn_path: str, out: str) -> int:
    p = build_panel(pd.read_pickle(big_path))
    I = indicators(p)  # noqa: E741
    F = feature_panels(p, I)
    ev = reaction_days(p, pd.read_pickle(earn_path))
    F.update(earnings_panels(p, ev))
    C = I["C"]
    F["mom_12_1"] = ((C.shift(21) / C.shift(252) - 1) * 100).to_numpy()
    F["ret21"] = ((C / C.shift(21) - 1) * 100).to_numpy()
    F["ret5"] = ((C / C.shift(5) - 1) * 100).to_numpy()
    spy_r = p.bench["SPY"]["close"].reindex(p.dates).pct_change()
    R = C.pct_change()
    cov = R.rolling(126).cov(spy_r)
    F["beta"] = (cov.div(spy_r.rolling(126).var(), axis=0)).to_numpy()
    F["idio_vol"] = (R.sub(spy_r, axis=0).rolling(63).std() * 100).to_numpy()
    F["dollar_vol"] = np.log10((C * I["V"]).rolling(20).mean()).to_numpy()
    T = len(p.dates)
    sample = np.zeros(T, bool)
    sample[::5] = True
    s = p.eligible & sample[:, None]
    tr = _simulate_all(p, s, 2.5, (5, 10, 20, 40))
    t, j = tr["t"].to_numpy(), tr["j"].to_numpy()
    df = pd.DataFrame({"t": t, "j": j})
    for H in (5, 10, 20, 40):
        df[f"r{H}"] = tr[f"r{H}"].to_numpy()
    for k, a in F.items():
        df[k] = a[t, j]
    df["date"] = p.dates[t]
    df["year"] = df["date"].dt.year
    df["research"] = p.half[j] == 1
    df["late"] = df["date"] >= SPLIT_DATE
    df["sector"] = np.array(p.sector, dtype=object)[j]
    # same-day, same-half excess
    for H in (5, 10, 20, 40):
        df[f"xd{H}"] = df[f"r{H}"] - df.groupby(["t", "research"])[f"r{H}"].transform("mean")
    df.to_pickle(out)
    dev = df[df.research & ~df.late & (df.year >= 2008)]
    print(f"DEV rows {len(dev):,}; days {dev.t.nunique()}")
    feats = [c for c in df.columns if c not in {"t", "j", "date", "year", "research", "late", "sector"}
             and not c.startswith(("r", "xd")) and not c.startswith(("spy", "vix", "breadth"))] + ["ret21", "ret5", "rsi2", "rsi14"]
    feats = list(dict.fromkeys(feats))
    print(f"{'feature':<16}{'xd20 by same-day quintile Q1..Q5':<42}{'Q5-Q1':>8}{'yrs+':>6}{'xd10 Q5-Q1':>11}{'yrs+':>6}")
    for f in feats:
        rk = dev.groupby("t")[f].rank(pct=True)
        q = np.floor(rk.clip(upper=0.9999) * 5)
        ok = q.notna()
        d = dev[ok].assign(q=q[ok])
        m = d.groupby("q")["xd20"].mean()
        y = d.groupby(["year", "q"])["xd20"].mean().unstack()
        y10 = d.groupby(["year", "q"])["xd10"].mean().unstack()
        if 0 not in m.index or 4 not in m.index:
            continue
        sp, sp10 = m[4] - m[0], d[d.q == 4].xd10.mean() - d[d.q == 0].xd10.mean()
        print(f"{f:<16}" + " ".join(f"{v:+.3f}" for v in m) + f"{sp:>+10.3f}{((y[4] - y[0]) > 0).mean() * 100:>5.0f}%"
              f"{sp10:>+10.3f}{((y10[4] - y10[0]) > 0).mean() * 100:>5.0f}%", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
