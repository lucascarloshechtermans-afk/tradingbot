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
    s["day"] = spy.index.normalize()
    m = s.reindex(df.index, method="ffill")
    if version in ("current", "step1"):
        # current Pine: spy = today's/previous SPY close mapped to chart bars; roc63 and SMA200 computed
        # on the CHART's bars (so the lookback counts chart bars, not SPY trading days)
        spy_chart = (m["close"] if us else m["close1"]).to_numpy(float)
        roc = spy_chart / T.shift(spy_chart, 63) - 1
        sma = T.sma(spy_chart, 200)
        up = np.where(np.isfinite(sma), (spy_chart > sma).astype(float), np.nan)
        return roc, up
    if version == "v41" and not us:
        # v4.1: on a chart date where SPY has no bar (US holiday), request.security already returns SPY's previous
        # (closed) day, so [0] is the right value; [1] would be two SPY days old. On other dates use [1] as before.
        same = (m["day"] == df.index.normalize()).to_numpy()
        return (np.where(same, m["roc63_1"], m["roc63"]).astype(float),
                np.where(same, m["up1"], m["up"]).astype(float))
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


TV_FEATS = {"f " + k: k for k in ("ibs", "rvol", "roc21", "roc63", "roc126", "atr_pct", "rsi14", "ext50", "rs63",
                                   "dist52", "bbw_pct", "gap", "spy_up", "spy_roc63", "range_atr", "brk_atr", "er20")}


def read_tv_export(path: str) -> pd.DataFrame:
    """A TradingView "Export chart data" CSV of a chart with swing_v4_1.pine (Debug input on): OHLCV + every plot,
    including the Data Window plots. The time column (unix seconds or ISO) becomes a date index."""
    d = pd.read_csv(path)
    t = d["time"]
    idx = pd.to_datetime(t, unit="s") if np.issubdtype(t.dtype, np.number) else pd.to_datetime(t, utc=True).dt.tz_localize(None)
    d.index = pd.DatetimeIndex(idx).normalize()
    d.columns = [c.strip() for c in d.columns]
    vol = next((c for c in d.columns if c.lower() == "volume"), None)
    d = d.rename(columns={vol: "volume"} if vol else {})
    return d


def compare_tv(path: str, us: bool = True, version: str = "v41", warmup: int = 300) -> dict:
    """Pine <-> Python parity on REAL TradingView output. The Python side recomputes every feature from the exported
    OHLCV itself (so data-vendor differences in the stock's prices drop out); SPY comes from the local cache, so the two
    SPY features can differ slightly (TradingView's SPY is not dividend-adjusted by default). Returns the max |diff| per
    feature in z-units after `warmup` bars, the max quality difference, and the bars where BUY/SELL differ when the
    Pine state machine (pine_sim.machine) is run on TradingView's own quality values."""
    from indicator_lab import pine_sim as PS
    d = read_tv_export(path)
    with open(MODEL) as fh:
        model = json.load(fh)
    sd = dict(zip(model["feats"], model["sd"]))
    df = d[["open", "high", "low", "close", "volume"]].astype(float)
    py = pine_features(df, us=us, version=version)
    keep = np.arange(len(d)) >= warmup
    feat = {}
    for col, k in TV_FEATS.items():
        if col in d:
            diff = (d[col].astype(float) - py[k]).abs()[keep] / sd[k]
            feat[k] = float(diff.max())
    out = {"bars": int(keep.sum()), "feature_max_z": feat}
    qcol = next((c for c in d.columns if c.startswith("Breakout quality")), None)
    scol = next((c for c in d.columns if c.startswith("Status")), None)
    if qcol:
        _, q_py = score(py, model)
        out["quality_max"] = float((d[qcol].astype(float) - q_py).abs()[keep].max())
    if qcol and scol:
        o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        from indicator_lab import pine_ta as T2
        st = d[scol].astype(float).to_numpy()
        # TradingView's own quality and SPY value decide the model + regime check, so this compares the breakout
        # conditions and the state machine (fills, stops, exits) on TradingView's bars
        final, yearly = PS.load_models()
        thr = np.full(len(d), final["thr"])
        for fit in yearly["fits"]:
            thr[(d.index.year == fit["year"]) & (d.index <= pd.Timestamp(yearly["train_end"]))] = fit["thr"]
        q_tv = d[qcol].astype(float).to_numpy()
        spy_tv = d["f spy_roc63"].astype(float).to_numpy() if "f spy_roc63" in d else py["spy_roc63"].to_numpy()
        with np.errstate(invalid="ignore"):
            ok = (q_tv >= thr) & (spy_tv <= PS.V41["regime_max"])
        entry_ok, exit_sig = PS.signals(o, h, lo, c, {**PS.DEFAULT}, ok)
        m = PS.machine(d.index, o, h, lo, c, T2.atr_py(h, lo, c, 14), entry_ok, exit_sig, PS.DEFAULT)
        out["buy_mismatch"] = [x.date() for x in d.index[(m["buy"] != (st == 1)) & keep]]
        out["sell_mismatch"] = [x.date() for x in d.index[(m["sell"] != (st == -1)) & keep]]
    return out


def main(argv):
    if "--tv" in argv:   # python -m indicator_lab.pine_parity --tv export.csv [--non-us]
        r = compare_tv(argv[argv.index("--tv") + 1], us="--non-us" not in argv)
        for k, v in r.items():
            print(k, v)
        return r
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
