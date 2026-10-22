"""Step 1 of the reliability round: Pine <-> Python feature parity.

Computes the 17 model features, the score and the quality EXACTLY as the Pine script defines
them (Pine `ta.*` semantics from `pine_ta`), and compares them with the features `meta.py` used
in training (`meta.feature_frame`). Reports, per feature, the max |difference| in z-units
(difference / the model's training sd for that feature) on random dates.

    python -m indicator_lab.pine_parity            # AAPL NVDA JPM KO + ASML.AS, 20 random dates each
    python -m indicator_lab.pine_parity --version current|fixed
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

from indicator_lab import meta
from indicator_lab import pine_ta as T
from indicator_lab.evaluate import get

MODEL = os.path.join(os.path.dirname(__file__), "pine", "v3_model.json")
TICKERS = ["AAPL", "NVDA", "JPM", "KO", "ASML.AS"]
NON_US = {"ASML.AS"}  # exchange timezone != America/New_York


def _spy_series(df: pd.DataFrame, us: bool, version: str):
    """SPY inputs as the Pine script sees them on this chart's bars.
    request.security(SPY, "D", expr) evaluates expr on SPY's own daily bars and maps the SPY bar
    with the chart bar's date (or the latest earlier one) onto the chart bar."""
    spy = get("SPY")
    sc = spy["close"].to_numpy(float)
    sroc63 = sc / T.shift(sc, 63) - 1
    ssma200 = T.sma(sc, 200)
    s = pd.DataFrame({"close": sc, "close1": T.shift(sc, 1), "roc63": sroc63, "roc63_1": T.shift(sroc63, 1),
                      "up": (sc > ssma200).astype(float), "up1": T.shift((sc > ssma200).astype(float), 1)},
                     index=spy.index)
    s.loc[~np.isfinite(ssma200), "up"] = np.nan
    m = s.reindex(df.index, method="ffill")
    if version in ("current", "step1"):
        # current Pine: spy = today's/previous SPY close mapped to chart bars; roc63 and SMA200 computed
        # on the CHART's bars (so the lookback counts chart bars, not SPY trading days)
        spy_chart = (m["close"] if us else m["close1"]).to_numpy(float)
        roc = spy_chart / T.shift(spy_chart, 63) - 1
        sma = T.sma(spy_chart, 200)
        up = np.where(np.isfinite(sma), (spy_chart > sma).astype(float), np.nan)
        return roc, up
    # fixed (step 7): computed inside request.security on SPY's own bars
    return (m["roc63"] if us else m["roc63_1"]).to_numpy(float), (m["up"] if us else m["up1"]).to_numpy(float)


def pine_features(df: pd.DataFrame, us: bool = True, version: str = "current") -> pd.DataFrame:
    o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    a = T.atr(h, lo, c, 14) if version == "current" else T.atr_py(h, lo, c, 14)  # "step1"/"fixed": pandas-style
    f = pd.DataFrame(index=df.index)
    rng = h - lo
    f["ibs"] = np.where(rng > 0, (c - lo) / np.where(rng > 0, rng, 1), 0.5)
    vr = v / T.sma(v, 50)
    f["rvol"] = np.log(np.maximum(vr, 0.05))
    f.loc[~np.isfinite(vr), "rvol"] = np.nan
    f["roc21"] = c / T.shift(c, 21) - 1
    f["roc63"] = c / T.shift(c, 63) - 1
    f["roc126"] = c / T.shift(c, 126) - 1
    f["atr_pct"] = a / c * 100
    f["rsi14"] = T.rsi(c, 14) if version == "current" else T.rsi_py(c, 14)
    f["ext50"] = (c - T.sma(c, 50)) / a
    spy_roc, spy_up = _spy_series(df, us, version)
    f["spy_roc63"] = spy_roc
    f["rs63"] = f["roc63"] - spy_roc
    if version == "current":
        f["dist52"] = c / T.highest(h, 252) - 1
        bbw = 4 * T.stdev(c, 20) / T.sma(c, 20)
        f["bbw_pct"] = T.percentrank(bbw, 252) / 100
    else:
        # fixed: follow Python (rolling 252 max with min 200 bars; rank incl. current, min 100 values)
        f["dist52"] = c / T.highest_min(h, 252, 200) - 1
        bbw = 4 * T.stdev(c, 20) / T.sma(c, 20)
        f["bbw_pct"] = T.rank_pct_incl(bbw, 252, 100)
    f["gap"] = (o - T.shift(c)) / T.shift(a)
    f["spy_up"] = spy_up
    f["range_atr"] = (h - lo) / T.shift(a)
    f["brk_atr"] = (c - T.shift(T.highest(h, 20))) / a
    f["er20"] = np.abs(c - T.shift(c, 20)) / T.msum(np.abs(np.r_[np.nan, np.diff(c)]), 20)
    return f


def score(f: pd.DataFrame, model: dict) -> tuple[pd.Series, pd.Series]:
    s = pd.Series(model["b"], index=f.index)
    for name, mu, sd, w in zip(model["feats"], model["mu"], model["sd"], model["w"]):
        s = s + w * ((f[name] - mu) / sd)
    return s, 1 / (1 + np.exp(-s))


def compare(version: str = "current", n_dates: int = 20, seed: int = 7, tickers=TICKERS):
    with open(MODEL) as fh:
        model = json.load(fh)
    sd = dict(zip(model["feats"], model["sd"]))
    rng = np.random.default_rng(seed)
    rows = []
    for t in tickers:
        df = get(t)
        py = meta.feature_frame(df)  # training definition (pandas)
        pf = pine_features(df, us=t not in NON_US, version=version)
        ok = py[model["feats"]].notna().all(axis=1) & pf[model["feats"]].notna().all(axis=1)
        dates = df.index[ok.to_numpy()]
        dates = dates[dates >= pd.Timestamp("2015-01-01")]
        pick = rng.choice(len(dates), size=min(n_dates, len(dates)), replace=False)
        for d in dates[np.sort(pick)]:
            r = {"ticker": t, "date": d}
            for k in model["feats"]:
                r[k] = abs(pf.at[d, k] - py.at[d, k]) / sd[k]
            ps, pq = score(pf.loc[[d]], model)
            ys, yq = score(py.loc[[d]], model)
            r["score"] = abs(ps.iloc[0] - ys.iloc[0])
            r["quality"] = abs(pq.iloc[0] - yq.iloc[0])
            rows.append(r)
    return pd.DataFrame(rows)


def main(argv):
    version = argv[argv.index("--version") + 1] if "--version" in argv else "current"
    d = compare(version)
    with open(MODEL) as fh:
        feats = json.load(fh)["feats"]
    print(f"Pine '{version}' vs Python training features — max |diff| in z-units over {len(d)} ticker-dates")
    for scope, sub in (("US (AAPL NVDA JPM KO)", d[d.ticker != "ASML.AS"]), ("Euronext (ASML.AS)", d[d.ticker == "ASML.AS"])):
        print(f"  {scope}:")
        worst = sub[feats].max().sort_values(ascending=False)
        print("   " + " | ".join(f"{k} {v:.3f}" for k, v in worst.items()))
        print(f"   score max |diff| {sub['score'].max():.4f} (logit), quality max |diff| {sub['quality'].max()*100:.2f} %-pt")
    return d


if __name__ == "__main__":
    main(sys.argv[1:])
