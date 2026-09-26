"""Build the candidate table and run the DEV walk-forward for the ranking model."""
from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

from research.engine2 import build_panel
from research.hypotheses4 import indicators, signals
from research.ml4 import candidate_table, feature_list, feature_panels, walk_forward_years

warnings.filterwarnings("ignore")


def main(big_path: str, out: str) -> int:
    p = build_panel(pd.read_pickle(big_path))
    I = indicators(p)  # noqa: E741
    sig = signals(p, I)
    F = feature_panels(p, I)
    cand = candidate_table(p, sig, F)
    cand.to_pickle(out)
    feats = feature_list(cand)
    print(f"candidates {len(cand)}  cells {cand.cell.value_counts().to_dict()}  features {len(feats)}")
    dev = cand[cand.cell == "DEV"]
    for target in ("r10", "r20"):
        wf = walk_forward_years(dev, target, feats)
        print(f"\n== walk-forward DEV, target {target}: {len(wf)} out-of-sample predictions 2012-2021")
        rho = wf[["pred", target]].rank().corr().iloc[0, 1]
        print(f"   rank corr pred vs outcome: {rho:+.3f}")
        dec = pd.qcut(wf.pred.rank(method='first'), 10, labels=False)
        print("   outcome by predicted decile:", " ".join(f"{v:+.3f}" for v in wf.groupby(dec)[target].mean()))
        for q in (0.9, 0.8, 0.5):
            thr_by_year = wf.groupby("year").pred.transform(lambda s: s.quantile(q))
            top = wf[wf.pred >= thr_by_year]
            yrs = top.groupby("year")[target].mean() - wf.groupby("year")[target].mean()
            print(f"   top {int((1-q)*100)}% per year: R {top[target].mean():+.3f} vs all {wf[target].mean():+.3f}; beats all in {(yrs > 0).mean()*100:.0f}% of years")
        wf.to_pickle(out.replace(".pkl", f"_wf_{target}.pkl"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
