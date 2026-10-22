"""Anti-overfitting protocol of the swing v4 round.

- `holdout.json` (committed before any test) fixes the holdout: the last two years and a set of tickers that
  never appeared in this repo. `install_dev_cutoff()` cuts every price series before the holdout start and
  refuses holdout tickers, so development code cannot see either by accident.
- `log()` appends every tried idea (also the failures) to experiments.csv.
- `bootstrap_ci()` gives a confidence interval for the expectancy.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os

import numpy as np
import pandas as pd

from indicator_lab import data

HERE = os.path.dirname(__file__)
HOLDOUT = json.load(open(os.path.join(HERE, "holdout.json")))  # noqa: SIM115
H_START = pd.Timestamp(HOLDOUT["time_holdout"]["start"])
H_TICKERS = set(HOLDOUT["ticker_holdout"]["tickers"])
DEV_PERIOD = tuple(pd.Timestamp(x) for x in HOLDOUT["development"]["period"])
EXP_LOG = os.path.join(HERE, "experiments.csv")

DEV_UNIVERSE = sorted(set(data.DEV + data.HOLDOUT + data.TRAIN_EXTRA + data.VOLATILE + data.LOCKBOX + data.LOCKBOX2))
HALF_A = DEV_UNIVERSE[0::2]
HALF_B = DEV_UNIVERSE[1::2]

_orig_load = data.load
_MODE = {"mode": None}


def install_dev_cutoff() -> None:
    """Development mode: every series ends the day before the holdout start; holdout tickers raise."""
    if _MODE["mode"] == "dev":
        return
    if _MODE["mode"] is not None:
        raise RuntimeError("data mode already set to " + str(_MODE["mode"]))

    def load(ticker: str, *a, **k) -> pd.DataFrame:
        if ticker in H_TICKERS:
            raise PermissionError(f"{ticker} is a holdout ticker: not available during development")
        df = _orig_load(ticker, *a, **k)
        return df[df.index < H_START]

    data.load = load
    _MODE["mode"] = "dev"


def install_final() -> None:
    """Phase 3 only: full data incl. the holdout (no fitting is allowed after this run)."""
    if _MODE["mode"] is not None:
        raise RuntimeError("data mode already set to " + str(_MODE["mode"]))
    _MODE["mode"] = "final"


def bootstrap_ci(x, n: int = 5000, seed: int = 0, q=(0.025, 0.975)) -> tuple[float, float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), (n, len(x)))].mean(axis=1)
    return tuple(float(v) for v in np.quantile(means, q))


FIELDS = ["id", "time", "phase", "idea", "params", "new_free_params", "universe", "period", "n", "win",
          "exp_pct", "exp_R", "pf", "avg_win", "avg_loss", "cagr", "maxdd", "mar", "hold", "exposure",
          "exp_ci_lo", "exp_ci_hi", "years_better", "half_a", "half_b", "accepted", "notes"]


def log(row: dict) -> int:
    """Append one trial to experiments.csv; returns its id. Every trial is logged, also the failures."""
    exists = os.path.exists(EXP_LOG)
    n = 0
    if exists:
        with open(EXP_LOG) as fh:
            n = sum(1 for _ in fh) - 1
    row = {"id": n + 1, "time": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **row}
    if isinstance(row.get("params"), dict):
        row["params"] = json.dumps(row["params"], sort_keys=True)
    with open(EXP_LOG, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerow({k: (round(v, 6) if isinstance(v, float) else v) for k, v in row.items()})
    return n + 1


def n_trials() -> int:
    if not os.path.exists(EXP_LOG):
        return 0
    with open(EXP_LOG) as fh:
        return sum(1 for _ in fh) - 1
