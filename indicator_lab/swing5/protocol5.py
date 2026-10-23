"""Protocol of the swing v5 round: the new holdout (holdout_v5.json, committed before any test), the development
universe (earlier development tickers + the spent v4 holdout), its two halves and the round's own experiment log."""
from __future__ import annotations

import json
import os

import pandas as pd

from indicator_lab.swing4 import protocol as P4

HERE = os.path.dirname(__file__)
with open(os.path.join(HERE, "holdout_v5.json")) as _fh:
    HOLDOUT = json.load(_fh)
H_TICKERS = set(HOLDOUT["ticker_holdout"]["tickers"])
DEV_PERIOD = tuple(pd.Timestamp(x) for x in HOLDOUT["development"]["period"])
CUTOFF = pd.Timestamp("2024-10-22")
DEV_UNIVERSE = sorted(set(P4.DEV_UNIVERSE) | P4.H_TICKERS)
HALF_A = DEV_UNIVERSE[0::2]
HALF_B = DEV_UNIVERSE[1::2]
EXP_LOG = os.path.join(HERE, "experiments.csv")
assert not (H_TICKERS & set(DEV_UNIVERSE))


def install_dev() -> None:
    P4.install_dev_cutoff(blocked=H_TICKERS, start=CUTOFF)


def install_final() -> None:
    P4.install_final()


def log(row: dict) -> int:
    return P4.log(row, EXP_LOG)


def n_trials() -> int:
    return P4.n_trials(EXP_LOG)


bootstrap_ci = P4.bootstrap_ci
