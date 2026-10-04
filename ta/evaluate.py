"""Historical validation of technical signals (signal research, not risk management).

For each ticker and each sample date t (every `stride` sessions) the SAME
engine (ta.engine.analyze, light mode, daily + weekly + monthly from data up to
and including t) is run on the frame cut at t. Every setup it reports is then
measured from the next session's open:

  ret_h      return to the close h sessions later, signed by the setup direction
  excess_h   ret_h minus the same-day average of all sampled tickers (signed)
  mfe / mae  maximum favourable / adverse excursion within 20 sessions (% and ATR)

Results are split chronologically: train <= 2014, validation 2015-2019,
out-of-sample >= 2020, and grouped by setup x status, market regime, volatility
bucket, sector and score bucket. Nothing is optimised here. 4H/1H history is
only ~2 years at the data source, so historical results are daily-timeframe
results (weekly/monthly confluence included). The universe and the sector
labels are TODAY's S&P 1000 membership: survivorship bias (delisted losers are
missing) and current GICS sectors -- compare signals with the same-day
baseline (excess), not with zero.

    python -m ta.evaluate --tickers 120 --stride 10 --out ta_eval.pkl
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (5, 10, 20, 40)
SPLITS = (("train", None, "2014-12-31"), ("validation", "2015-01-01", "2019-12-31"), ("oos", "2020-01-01", None))
WINDOW = 650   # bars handed to the engine per sample (enough for monthly/weekly structure and SMA200)


PURGE_DAYS = 60   # calendar days before a split boundary whose 40-session outcome would reach into the next split


def split_of(date: pd.Timestamp) -> str:
    """train / validation / oos, or 'purged' for samples whose outcome window crosses into the next split."""
    for _name, a, _b in SPLITS[1:]:
        if pd.Timestamp(a) - pd.Timedelta(days=PURGE_DAYS) <= date < pd.Timestamp(a):
            return "purged"
    for name, a, b in SPLITS:
        if (a is None or date >= pd.Timestamp(a)) and (b is None or date <= pd.Timestamp(b)):
            return name
    return "?"


def forward(df: pd.DataFrame, t: int, direction: int, atr: float) -> dict | None:
    """Outcome of a signal on the close of bar t (entry at the open of t+1)."""
    n = len(df)
    if t + 1 >= n:
        return None
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    entry = o[t + 1]
    if not np.isfinite(entry) or entry <= 0:
        return None
    out = {}
    for hz in HORIZONS:
        j = t + hz
        out[f"ret{hz}"] = (c[j] / entry - 1) * 100 * direction if j < n else np.nan
        out[f"raw{hz}"] = (c[j] / entry - 1) * 100 if j < n else np.nan
    atr_pct = atr / c[t] * 100 if np.isfinite(atr) and c[t] > 0 else np.nan
    if t + 20 < n:     # excursions only over a FULL 20-session window (a partial one is biased toward 0)
        seg = slice(t + 1, t + 21)
        hi, low = np.nanmax(h[seg]), np.nanmin(lo[seg])
        up, dn = (hi / entry - 1) * 100, (low / entry - 1) * 100
        out["mfe"], out["mae"] = (up, dn) if direction > 0 else (-dn, -up)
    else:
        out["mfe"] = out["mae"] = np.nan
    out["mfe_atr"], out["mae_atr"] = out["mfe"] / atr_pct, out["mae"] / atr_pct
    out["atr_pct"] = atr_pct
    return out


def _work(args) -> list[dict]:
    ticker, df, sector, spy_close, regimes, dates = args
    from ta.engine import analyze

    rows = []
    pos = {d: i for i, d in enumerate(df.index)}
    for d in dates:
        t = pos.get(d)
        if t is None or t < 260 or t + 1 >= len(df):
            continue
        cut = df.iloc[max(0, t - WINDOW + 1):t + 1]
        try:
            rep = analyze(ticker, cut, None, {"SPY": spy_close[spy_close.index <= d]}, regimes.get(d), light=True)
        except Exception:  # noqa: BLE001 - one bad slice must not stop the study
            continue
        if not rep.daily.ok:
            continue
        atr = rep.daily.atr
        base = {"ticker": ticker, "date": d, "sector": sector, "regime": regimes[d].label if d in regimes else "?",
                "trend": rep.daily.trend.label}
        f_long = forward(df, t, 1, atr)
        if f_long is None:
            continue
        rows.append({**base, "kind": "_all", "status": "", "direction": 1, "score": np.nan, **f_long})
        if rep.primary is not None:
            fp = forward(df, t, rep.primary.direction, atr)
            rows.append({**base, "kind": "_primary", "status": rep.primary.status, "direction": rep.primary.direction,
                         "score": rep.score.total, "primary_kind": rep.primary.kind, **fp})
        for s in rep.setups:
            fs = forward(df, t, s.direction, atr)
            rows.append({**base, "kind": s.kind, "status": s.status, "direction": s.direction, "score": s.quality,
                         "combo": bool(s.combos), **fs})
    return rows


def load_data(n_tickers: int, start: str, seed: int = 20261004) -> tuple[dict, dict, pd.DataFrame]:
    import yfinance as yf

    members = json.load(open(Path(__file__).resolve().parent.parent / "data" / "sp1000_members.json"))["members"]
    rng = np.random.default_rng(seed)
    tickers = sorted(rng.choice(sorted(members), size=min(n_tickers, len(members)), replace=False).tolist())
    raw = yf.download(tickers + ["SPY"], start=start, auto_adjust=True, progress=False, group_by="ticker", threads=True)
    frames = {}
    for t in tickers + ["SPY"]:
        try:
            df = raw[t].rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
        except KeyError:
            continue
        if len(df) > 400:
            df.index = pd.DatetimeIndex(df.index).tz_localize(None) if df.index.tz is not None else df.index
            frames[t] = df
    spy = frames.pop("SPY")
    return frames, {t: members.get(t) for t in frames}, spy


def summarize(res: pd.DataFrame, stride: int | None = None) -> str:
    """Tables per group and split. Rows whose 20-session outcome is not known yet are
    left out of n / hit rate / means alike (they would count as losses in a hit rate)."""
    res = res.copy()
    if stride is None:   # sessions between sample dates, for the exposure (frequency) denominator
        d = pd.Series(sorted(res["date"].unique()))
        stride = int(max(round(d.diff().dt.days.median() * 252 / 365.25), 1)) if len(d) > 1 else 1
    res["split"] = res["date"].map(split_of)
    base = res[res.kind == "_all"].groupby("date")[[f"raw{h}" for h in HORIZONS]].mean()
    for h in HORIZONS:
        res[f"excess{h}"] = res[f"ret{h}"] - res["direction"] * res["date"].map(base[f"raw{h}"])
    expo_yrs = (res.kind == "_all").sum() * stride / 252    # ticker-years actually sampled
    res = res[res["ret20"].notna() & (res["split"] != "purged")]
    sig = res[~res.kind.isin(["_all", "_primary"])]
    lines = [f"Steekproef: {res.ticker.nunique()} aandelen, {res.date.nunique()} datums, stride {stride} sessies, "
             f"{expo_yrs:,.0f} aandeel-jaren; alleen signalen met een bekende 20-daagse uitkomst."]

    def table(df, keys, title):
        g = df.groupby(keys + ["split"])
        t = g.agg(n=("ret20", "size"), ret10=("ret10", "mean"), ret20=("ret20", "mean"), ex20=("excess20", "mean"),
                  hit20=("ret20", lambda x: (x > 0).mean() * 100), mfe=("mfe", "mean"), mae=("mae", "mean")).round(2)
        t = t.unstack("split")
        cols = [(m, s) for m in ("n", "ex20", "ret20", "hit20") for s in ("train", "validation", "oos") if (m, s) in t.columns]
        lines.append(f"\n== {title}  (ex20 = 20-daags rendement minus alle aandelen dezelfde dag, %)\n" + t[cols].to_string())

    table(sig[sig.status.isin(["triggered", "confirmed"])], ["kind", "status"], "SETUPS getriggerd/bevestigd")
    table(sig[sig.status == "developing"], ["kind"], "SETUPS in ontwikkeling (nog niet getriggerd)")
    prim = res[res.kind == "_primary"].copy()
    prim["score_bucket"] = pd.cut(prim["score"], [0, 45, 55, 65, 75, 101], labels=["<45", "45-55", "55-65", "65-75", "75+"])
    table(prim[prim.direction > 0], ["score_bucket"], "HOOFDSETUP long, per scorebucket")
    # one row per stock-day: several setups on the same stock-day are ONE trade in these splits
    longs = sig[sig.status.isin(["triggered", "confirmed"]) & (sig.direction > 0)].drop_duplicates(["ticker", "date"])
    table(longs, ["regime"], "Long-signalen per marktregime (1 per aandeel-dag)")
    longs = longs.assign(vol=pd.cut(longs["atr_pct"], [0, 2, 4, 100], labels=["ATR<2%", "ATR 2-4%", "ATR>4%"]))
    table(longs, ["vol"], "Long-signalen per volatiliteit (1 per aandeel-dag)")
    table(longs, ["sector"], "Long-signalen per sector (1 per aandeel-dag, sector = huidige GICS)")
    freq = sig[sig.status.isin(["triggered", "confirmed"])].groupby("kind").size() / max(expo_yrs, 1e-9)
    lines.append(f"\n== Frequentie (getriggerd/bevestigd per aandeel per jaar; elke {stride}e sessie bekeken, een setup die "
                 f"langer dan {stride} sessies leeft kan dubbel tellen)\n" + freq.round(2).to_string())
    mm = sig[sig.status.isin(["triggered", "confirmed"])].groupby("kind")[["mfe", "mae", "mfe_atr", "mae_atr"]].mean().round(2)
    lines.append("\n== MFE/MAE binnen 20 dagen (%, en in ATR)\n" + mm.to_string())
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tickers", type=int, default=120)
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--start", default="2007-01-01")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="ta_eval.pkl")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args(argv)
    if args.summary_only:
        print(summarize(pd.read_pickle(args.out)))
        return 0
    from ta.regime import classify_regime

    frames, sectors, spy = load_data(args.tickers, args.start)
    dates = list(spy.index[260::args.stride])
    regimes = {d: classify_regime(spy[spy.index <= d].iloc[-600:]) for d in dates}
    print(f"{len(frames)} tickers, {len(dates)} sample dates", flush=True)
    jobs = [(t, df, sectors.get(t), spy["close"], regimes, dates) for t, df in frames.items()]
    rows = []
    with ProcessPoolExecutor(args.workers) as ex:
        for k, r in enumerate(ex.map(_work, jobs), 1):
            rows += r
            if k % 10 == 0:
                print(f"  {k}/{len(jobs)} tickers done, {len(rows)} records", flush=True)
    res = pd.DataFrame(rows)
    res.to_pickle(args.out)
    print(summarize(res, args.stride))
    return 0


if __name__ == "__main__":
    sys.exit(main())
