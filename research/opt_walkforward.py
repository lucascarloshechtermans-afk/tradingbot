"""Walk-forward test of research/opt_model.RankModel on the optimization
dataset: train on everything before T, test on [T, T+step), move T, retrain.
Only the development slice is used unless --include-holdout is given.

Reports per window and pooled: all candidates vs. the model's selection
(mean R, PF, n), plus score-decile monotonicity and a calibration check.

    python -m research.opt_walkforward --data ds_dev.pkl
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from research.opt_analysis import HOLDOUT_START
from research.opt_model import fit


def stats(r: pd.Series) -> str:
    r = r.dropna()
    if len(r) < 5:
        return f"n={len(r):>4}"
    pf = r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf
    return f"n={len(r):>5} win={(r > 0).mean() * 100:4.1f}% R={r.mean():+.3f} PF={pf:.2f}"


def walk_forward(ds: pd.DataFrame, first_test: str = "2023-07-01", step_months: int = 3, end=None,
                 **fit_kw) -> pd.DataFrame:
    ds = ds.dropna(subset=["r"]).sort_values("entry_date")
    t = pd.Timestamp(first_test, tz="UTC")
    end = end or ds["entry_date"].max()
    out = []
    while t < end:
        t2 = t + pd.DateOffset(months=step_months)
        train, test = ds[ds.entry_date < t], ds[(ds.entry_date >= t) & (ds.entry_date < t2)]
        if len(train) > 500 and len(test) > 20:
            m = fit(train, **fit_kw)
            test = test.assign(score=m.feature_score(test), blocked=m.blocked(test), selected=m.select(test),
                               window=str(t.date()), n_features=len(m.features))
            out.append(test)
        t = t2
    return pd.concat(out) if out else pd.DataFrame()


def report(wf: pd.DataFrame) -> None:
    print(f"{'window':<12}{'all candidates':<42}{'model selection':<42}features")
    for w, g in wf.groupby("window"):
        print(f"{w:<12}{stats(g.r):<42}{stats(g[g.selected].r):<42}{g.n_features.iloc[0]}")
    print(f"\n{'POOLED':<12}{stats(wf.r):<42}{stats(wf[wf.selected].r)}")
    print(f"{'blocked':<12}{stats(wf[wf.blocked].r)}")
    print(f"{'not blocked':<12}{stats(wf[~wf.blocked].r)}")
    ok = wf[~wf.blocked]
    dec = pd.qcut(ok.score.rank(method="first"), 10, labels=False)
    print("\nscore decile (out-of-sample, non-blocked):", " ".join(f"{v:+.2f}" for v in ok.groupby(dec).r.mean()))
    wins = sum(1 for _, g in wf.groupby("window") if g[g.selected].r.mean() > g.r.mean())
    print(f"windows where selection beat all candidates: {wins}/{wf.window.nunique()}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--keep-top", type=float, default=0.4)
    ap.add_argument("--include-holdout", action="store_true")
    args = ap.parse_args(argv)
    ds = pd.read_pickle(args.data)
    if not args.include_holdout:
        ds = ds[ds.entry_date < HOLDOUT_START]
    wf = walk_forward(ds, keep_top=args.keep_top)
    report(wf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
