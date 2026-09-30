"""Final validation of candidate rule sets on data NOT used to develop them.

The rank model is fitted ONCE on the development slice (190-ticker universe,
entries before HOLDOUT_START) and then applied, frozen, to:
  A. holdout period, development universe (entries >= HOLDOUT_START)
  B. out-of-sample universe (163 other US stocks), whole period
  C. out-of-sample universe, holdout period only
Rule sets compared (same trades, same engine, same costs):
  ALL      every candidate the scanner's strategies/gates produce
  LIVE     the gates adopted earlier: momentum rank >= 80 and efficiency >= 0.25
  RANK     rank-model top 40%
  RANK+M   rank-model top 40% and momentum rank >= 80
  RANK+M+R RANK+M, and no pullback / trend-continuation entry with a
           resistance zone closer than 1 ATR
Robustness: extra round-trip cost (in R: 2 x slip x entry / risk), and the
thresholds moved around their chosen values.

    python -m research.opt_validate --dev ds_dev.pkl --oos ds_oos.pkl
"""

from __future__ import annotations

import argparse
import sys
import warnings

import numpy as np
import pandas as pd

from research.opt_analysis import HOLDOUT_START
from research.opt_model import fit

warnings.filterwarnings("ignore")


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 5:
        return {"n": len(r)}
    pf = r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf
    return {"n": len(r), "win": (r > 0).mean() * 100, "R": r.mean(), "PF": pf, "sumR": r.sum(),
            "worst1%": r.quantile(0.01)}


def fmt(s: dict) -> str:
    if s.get("n", 0) < 5:
        return f"n={s.get('n', 0):>5}"
    return f"n={s['n']:>5} win={s['win']:4.1f}% R={s['R']:+.3f} PF={s['PF']:.2f} sumR={s['sumR']:+7.1f}"


def rule_sets(df: pd.DataFrame, model, mom: float = 80, eff: float = 0.25, res_atr: float = 1.0,
              keep_top: float | None = None) -> dict[str, pd.Series]:
    score = model.feature_score(df)
    thr = model.threshold if keep_top is None else model.threshold_for(keep_top)
    rank = score >= thr
    m = df["x_mom_rank"] >= mom
    near_res = df["setup"].isin(["PULLBACK", "TREND CONTINUATION"]) & (df["x_res_zone_dist_atr"] < res_atr)
    return {
        "ALL": pd.Series(True, index=df.index),
        "LIVE": m & (df["x_eff30"] >= eff),
        "RANK": rank,
        "RANK+M": rank & m,
        "RANK+M+R": rank & m & ~near_res,
    }


def with_cost(df: pd.DataFrame, extra_slip_pct: float) -> pd.Series:
    risk_frac = (df["entry"] - df["stop"]) / df["entry"]
    return df["r"] - 2 * extra_slip_pct / 100 / risk_frac


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", required=True)
    ap.add_argument("--oos", required=True)
    ap.add_argument("--model-out", default=None)
    args = ap.parse_args(argv)
    dev_all = pd.read_pickle(args.dev).dropna(subset=["r"])
    oos = pd.read_pickle(args.oos).dropna(subset=["r"])
    dev = dev_all[dev_all.entry_date < HOLDOUT_START]
    model = fit(dev, setup_rules=False, keep_top=0.4)
    # thresholds for other keep_top values, from the same training scores
    train_scores = model.feature_score(dev)
    model.threshold_for = lambda kt: float(train_scores.quantile(1 - kt))  # type: ignore[attr-defined]
    print("model features (fitted on dev only):", {f: round(model.rhos[f], 3) for f in model.features})
    if args.model_out:
        with open(args.model_out, "w") as f:
            f.write(model.to_json())

    sets = {
        "DEV (in-sample fit)": dev,
        "A holdout period, dev universe": dev_all[dev_all.entry_date >= HOLDOUT_START],
        "B OOS universe, all periods": oos,
        "C OOS universe, holdout period": oos[oos.entry_date >= HOLDOUT_START],
    }
    for name, df in sets.items():
        print(f"\n== {name}  ({df.entry_date.min().date()}..{df.entry_date.max().date()})")
        for rs, mask in rule_sets(df, model).items():
            print(f"   {rs:<10} {fmt(stats(df[mask].r))}")

    print("\n== ROBUSTNESS on B (OOS universe): extra round-trip slippage")
    for slip in (0.0, 0.1, 0.25, 0.5):
        rr = with_cost(oos, slip)
        line = "  ".join(f"{k}:{rr[m].mean():+.3f}" for k, m in rule_sets(oos, model).items())
        print(f"   +{slip:.2f}% per side  {line}")
    print("\n== ROBUSTNESS on B: thresholds around the chosen values (mean R / n)")
    for mom in (70, 80, 90):
        for eff in (0.20, 0.25, 0.30):
            m = rule_sets(oos, model, mom=mom, eff=eff)
            print(f"   mom>={mom} eff>={eff:.2f}  LIVE {oos[m['LIVE']].r.mean():+.3f} ({m['LIVE'].sum():>4})   "
                  f"RANK+M {oos[m['RANK+M']].r.mean():+.3f} ({m['RANK+M'].sum():>4})")
    for kt in (0.3, 0.4, 0.5):
        m = rule_sets(oos, model, keep_top=kt)
        print(f"   rank keep top {kt:.0%}   RANK {oos[m['RANK']].r.mean():+.3f} ({m['RANK'].sum():>4})   "
              f"RANK+M {oos[m['RANK+M']].r.mean():+.3f} ({m['RANK+M'].sum():>4})")
    for ra in (0.5, 1.0, 2.0):
        m = rule_sets(oos, model, res_atr=ra)
        print(f"   resistance rule < {ra} ATR   RANK+M+R {oos[m['RANK+M+R']].r.mean():+.3f} ({m['RANK+M+R'].sum():>4})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
