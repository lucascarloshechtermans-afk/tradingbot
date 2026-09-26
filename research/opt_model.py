"""A deliberately simple, robust RANKING model for candidate trades -- not a
win-probability model.

fit(train):
  1. candidate features = numeric columns of the dataset (f_*, x_*) with
     enough coverage
  2. keep a feature only if its rank correlation with R has the SAME sign in
     each of `k` chronological sub-folds of the training data and
     |rho| >= min_rho overall (stability, not just in-sample strength)
  3. drop redundancy: walk the kept features by |rho| and skip any whose rank
     correlation with an already-chosen feature exceeds max_corr
  4. setups (and setup x regime cells) whose mean R is negative in the
     majority of sub-folds are marked NO TRADE
score(rows): mean over chosen features of sign * percentile-rank of the value
  inside the TRAINING distribution (0..1) -- a rank-sum, so no feature can
  dominate through its scale and no coefficient can be over-fitted
threshold: a score quantile of the training trades (e.g. keep the top 40%)

The score is an ordering of setup quality, NOT a probability of winning
(see calibrate() in research/opt_walkforward.py).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

EXCLUDE_FEATURES = {"x_entry_gap_atr"}  # known only at the fill, not at the signal


def _spearman(a: pd.Series, b: pd.Series) -> float:
    return a.rank().corr(b.rank())


@dataclass
class RankModel:
    features: list[str] = field(default_factory=list)
    signs: dict[str, float] = field(default_factory=dict)
    rhos: dict[str, float] = field(default_factory=dict)
    quantiles: dict[str, list[float]] = field(default_factory=dict)  # 101 training quantiles per feature
    no_trade_setups: list[str] = field(default_factory=list)
    no_trade_cells: list[list[str]] = field(default_factory=list)  # [setup, regime]
    threshold: float = 0.0
    keep_top: float = 0.4

    def feature_score(self, df: pd.DataFrame) -> pd.Series:
        parts = []
        for f in self.features:
            q = np.asarray(self.quantiles[f])
            v = df[f].to_numpy(dtype=float)
            pct = np.searchsorted(q, v, side="right") / len(q)
            pct = np.where(np.isfinite(v), pct, 0.5)  # unknown = neutral
            parts.append(pct if self.signs[f] > 0 else 1 - pct)
        return pd.Series(np.mean(parts, axis=0) if parts else 0.5, index=df.index)

    def blocked(self, df: pd.DataFrame) -> pd.Series:
        b = df["setup"].isin(self.no_trade_setups)
        for s, r in self.no_trade_cells:
            b |= (df["setup"] == s) & (df["regime"] == r)
        return b

    def select(self, df: pd.DataFrame) -> pd.Series:
        return (~self.blocked(df)) & (self.feature_score(df) >= self.threshold)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> "RankModel":
        return cls(**json.loads(s))


def candidate_features(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if (c.startswith("f_") or c.startswith("x_")) and c not in EXCLUDE_FEATURES
            and pd.api.types.is_numeric_dtype(df[c])]
    return [c for c in cols if df[c].notna().mean() > 0.6 and df[c].nunique() > 1]


def fit(train: pd.DataFrame, k: int = 3, min_rho: float = 0.02, max_corr: float = 0.7,
        keep_top: float = 0.4, setup_rules: bool = True) -> RankModel:
    train = train.dropna(subset=["r"]).sort_values("entry_date")
    parts = [train.iloc[len(train) * i // k: len(train) * (i + 1) // k] for i in range(k)]
    stable = {}
    for c in candidate_features(train):
        rho = _spearman(train[c], train["r"])
        if not np.isfinite(rho) or abs(rho) < min_rho:
            continue
        fold_rhos = [_spearman(p[c], p["r"]) for p in parts]
        if all(np.isfinite(x) and np.sign(x) == np.sign(rho) for x in fold_rhos):
            stable[c] = rho
    chosen: list[str] = []
    for c in sorted(stable, key=lambda c: -abs(stable[c])):
        if any(abs(_spearman(train[c], train[o])) > max_corr for o in chosen):
            continue
        chosen.append(c)
    m = RankModel(features=chosen, signs={c: float(np.sign(stable[c])) for c in chosen},
                  rhos={c: float(stable[c]) for c in chosen},
                  quantiles={c: np.nanquantile(train[c].to_numpy(dtype=float), np.linspace(0, 1, 101)).tolist() for c in chosen},
                  keep_top=keep_top)
    if setup_rules:
        for s, g in train.groupby("setup"):
            neg = sum(1 for p in parts if len(p[p.setup == s]) >= 20 and p[p.setup == s].r.mean() < 0)
            if neg >= 2 and g.r.mean() < 0.02:
                m.no_trade_setups.append(s)
        for (s, r), g in train.groupby(["setup", "regime"]):
            if s in m.no_trade_setups or len(g) < 60:
                continue
            neg = sum(1 for p in parts if len(p[(p.setup == s) & (p.regime == r)]) >= 15
                      and p[(p.setup == s) & (p.regime == r)].r.mean() < 0)
            if neg >= 2 and g.r.mean() < 0:
                m.no_trade_cells.append([s, r])
    allowed = train[~m.blocked(train)]
    sc = m.feature_score(allowed)
    m.threshold = float(sc.quantile(1 - keep_top)) if len(sc) else 0.0
    return m
