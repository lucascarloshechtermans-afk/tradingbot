"""Analysis of the optimization dataset (research/opt_dataset.py).

Everything here runs on the DEVELOPMENT slice only (entries before
--holdout-start); the holdout period and the out-of-sample universe are only
touched by research/opt_validate.py at the end.

Sections: feature importance (quintile spread + Spearman, stability across
three time folds), redundancy, losers vs winners, regime x setup, pairwise
interactions of the stable conditions.

    python -m research.opt_analysis --data ds_dev.pkl --section importance
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

HOLDOUT_START = pd.Timestamp("2025-10-01", tz="UTC")


def dev_slice(ds: pd.DataFrame, holdout_start=HOLDOUT_START) -> pd.DataFrame:
    return ds[ds["entry_date"] < holdout_start].dropna(subset=["r"]).copy()


def folds(ds: pd.DataFrame, k: int = 3) -> list[pd.DataFrame]:
    order = ds.sort_values("entry_date")
    return [order.iloc[len(order) * i // k: len(order) * (i + 1) // k] for i in range(k)]


def spearman(a: pd.Series, b: pd.Series) -> float:
    """Rank correlation without scipy: Pearson on ranks."""
    return a.rank().corr(b.rank())


def numeric_features(ds: pd.DataFrame) -> list[str]:
    cols = [c for c in ds.columns if (c.startswith("f_") or c.startswith("x_")) and pd.api.types.is_numeric_dtype(ds[c])]
    return [c for c in cols if ds[c].notna().mean() > 0.5 and ds[c].nunique() > 1]


def importance(ds: pd.DataFrame) -> pd.DataFrame:
    fs = folds(ds)
    rows = []
    for c in numeric_features(ds):
        sub = ds[[c, "r", "entry_date"]].dropna()
        if sub[c].nunique() <= 2:
            t, f_ = sub[sub[c] > 0.5], sub[sub[c] <= 0.5]
            if min(len(t), len(f_)) < 100:
                continue
            spread = t["r"].mean() - f_["r"].mean()
            per_fold = []
            for fd in fs:
                x = fd[[c, "r"]].dropna()
                a, b = x[x[c] > 0.5]["r"], x[x[c] <= 0.5]["r"]
                per_fold.append(a.mean() - b.mean() if len(a) > 30 and len(b) > 30 else np.nan)
            rows.append({"feature": c, "kind": "bool", "n": len(sub), "share_true": len(t) / len(sub),
                         "spread": spread, "rho": np.nan, **{f"fold{i + 1}": v for i, v in enumerate(per_fold)},
                         "q1": f_["r"].mean(), "q5": t["r"].mean()})
            continue
        q = pd.qcut(sub[c].rank(method="first"), 5, labels=False)
        means = sub.groupby(q)["r"].mean()
        rho = spearman(sub[c], sub["r"])
        per_fold = []
        for fd in fs:
            x = fd[[c, "r"]].dropna()
            per_fold.append(spearman(x[c], x["r"]) if len(x) > 100 else np.nan)
        rows.append({"feature": c, "kind": "num", "n": len(sub), "share_true": np.nan,
                     "spread": means.iloc[-1] - means.iloc[0], "rho": rho,
                     **{f"fold{i + 1}": v for i, v in enumerate(per_fold)},
                     "q1": means.iloc[0], "q5": means.iloc[-1], "qs": " ".join(f"{m:+.2f}" for m in means)})
    out = pd.DataFrame(rows)
    fcols = [c for c in out.columns if c.startswith("fold")]
    out["stable"] = out[fcols].apply(lambda r: (np.sign(r.dropna()) == np.sign(r.dropna().iloc[0])).all() if r.notna().sum() >= 3 else False, axis=1)
    return out.sort_values("spread", key=lambda s: -s.abs())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--section", default="importance")
    args = ap.parse_args(argv)
    ds = dev_slice(pd.read_pickle(args.data))
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)
    print(f"dev slice: {len(ds)} trades {ds.entry_date.min().date()}..{ds.entry_date.max().date()}  meanR {ds.r.mean():+.3f}")
    if args.section == "importance":
        imp = importance(ds)
        print(imp.drop(columns=["n"]).round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
