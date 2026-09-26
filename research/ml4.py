"""Ranking model for dip candidates (round 4).

Candidates = union of the dip hypotheses (H01-H06, H14-H16). Features are
taken at the signal close (no look-ahead). Target: trade R (time exit 10 or
20 bars, 2.5 ATR stop). Walk-forward by calendar year inside the DEV cell:
train on years < Y, predict year Y. Nothing from VAL/FINAL cells is used
for training or model choice.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.engine2 import SPLIT_DATE, Panel, simulate_rules
from research.hypotheses4 import SECTOR_ETF

DIP_HYPS = ["H01 LEADER_DIP", "H02 LEADER_DIP_DEEP", "H03 IBS_UPTREND", "H04 RSI2_UPTREND", "H05 DOWN3_UPTREND",
            "H06 GAPDOWN_REVERSAL", "H14 SECTOR_LEADER_DIP", "H15 CAPITULATION", "H16 LEADER_PANIC_DAY"]


def feature_panels(p: Panel, I: dict[str, pd.DataFrame]) -> dict[str, np.ndarray]:
    C, O, V, A = I["C"], I["O"], I["V"], I["A"]  # noqa: E741
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi14 = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    ret = C.pct_change()
    vol20 = ret.rolling(20).std()
    vol100 = ret.rolling(100).std()
    down = (C < C.shift(1)).astype(float)
    cs = down.cumsum()
    streak = cs - cs.where(down == 0).ffill().fillna(0)
    elig = p.df(p.eligible)
    above50 = (C > I["sma50"]).astype(float).where(elig)
    breadth = above50.mean(axis=1)
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    vix = p.bench["^VIX"]["close"].reindex(p.dates).ffill()
    etf_ret = pd.DataFrame({e: p.bench[e]["close"].reindex(p.dates).pct_change(21) for e in SECTOR_ETF.values() if e in p.bench})
    etf_rank = etf_ret.rank(axis=1, ascending=False)
    sec_rank = pd.DataFrame(np.nan, index=p.dates, columns=p.tickers)
    for col, sec in zip(p.tickers, p.sector):
        e = SECTOR_ETF.get(sec or "")
        if e in etf_rank:
            sec_rank[col] = etf_rank[e]
    bcast = lambda s: np.repeat(s.to_numpy()[:, None], len(p.tickers), axis=1)  # noqa: E731
    F = {
        "mom_rank": I["mom_rank"], "ret1_atr": I["ret1_atr"], "ret5_atr": I["ret5_atr"],
        "ret20_atr": (C - C.shift(20)) / A, "ema21_atr": (C - I["ema21"]) / A, "sma50_atr": (C - I["sma50"]) / A,
        "sma200_atr": (C - I["sma200"]) / A, "rsi2": I["rsi2"], "rsi14": rsi14, "ibs": I["ibs"],
        "atr_pct": A / C * 100, "hi252_atr": (C.rolling(252).max() - C) / A, "vol_ratio": V / I["vol20"],
        "gap_atr": (O - C.shift(1)) / A, "down_streak": streak, "sec_rank": sec_rank,
        "volreg": vol20 / vol100, "bbw_pct": I["bbw_pct"],
    }
    F = {k: v.to_numpy(dtype=np.float64) for k, v in F.items()}
    F.update({
        "spy_ret5": bcast(spy.pct_change(5) * 100), "spy_ret20": bcast(spy.pct_change(20) * 100),
        "spy_200": bcast((spy / spy.rolling(200).mean() - 1) * 100), "spy_50": bcast((spy / spy.rolling(50).mean() - 1) * 100),
        "vix": bcast(vix), "vix_chg5": bcast(vix - vix.shift(5)), "vix_pct1y": bcast(vix.rolling(252).rank(pct=True)),
        "breadth50": bcast(breadth * 100),
    })
    return F


def candidate_table(p: Panel, sig: dict[str, np.ndarray], F: dict[str, np.ndarray], holds=(10, 20)) -> pd.DataFrame:
    union = np.zeros_like(p.eligible)
    for h in DIP_HYPS:
        union |= sig[h]
    base = None
    for H in holds:
        tr = simulate_rules(p, union, stop_atr=2.5, max_hold=H)
        tr = tr.rename(columns={"r": f"r{H}", "bars": f"bars{H}", "exit_t": f"exit{H}"})
        base = tr if base is None else base.merge(tr, on=["t", "j"], how="outer")
    base = base.dropna(subset=[f"r{holds[0]}"]).reset_index(drop=True)
    t, j = base["t"].to_numpy(), base["j"].to_numpy()
    for k, a in F.items():
        base[k] = a[t, j]
    for h in DIP_HYPS:
        base["is_" + h.split()[1].lower()] = sig[h][t, j].astype(float)
    base["date"] = p.dates[t]
    base["year"] = base["date"].dt.year
    base["research"] = p.half[j] == 1
    base["late"] = base["date"] >= SPLIT_DATE
    base["cell"] = np.select([base.research & ~base.late, base.research & base.late, ~base.research & ~base.late],
                             ["DEV", "VAL-T", "VAL-U"], "FINAL")
    return base


FEATURES = None  # filled by feature_list()


def feature_list(df: pd.DataFrame) -> list[str]:
    skip = {"t", "j", "date", "year", "research", "late", "cell"}
    return [c for c in df.columns if c not in skip and not c.startswith(("r1", "r2", "bars", "exit"))]


def fit_lgbm(train: pd.DataFrame, target: str, feats: list[str], seed: int = 0):
    import lightgbm as lgb

    y = train[target].clip(-3, 5)
    m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=300,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0,
                          random_state=seed, verbose=-1)
    m.fit(train[feats], y)
    return m


def walk_forward_years(dev: pd.DataFrame, target: str, feats: list[str], first_test_year: int = 2012) -> pd.DataFrame:
    out = []
    for y in sorted(dev.year.unique()):
        if y < first_test_year:
            continue
        tr, te = dev[dev.year < y], dev[dev.year == y]
        if len(tr) < 2000 or te.empty:
            continue
        m = fit_lgbm(tr, target, feats)
        out.append(te.assign(pred=m.predict(te[feats])))
    return pd.concat(out)
