"""Round 14 Q4: do the dashboard warnings / technical score predict next-month returns of the picks?
    python -m research.round14b r14.pkl"""
from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from research.round14 import PERIODS

WINDOW = 650


def _picks(d: dict) -> list[tuple[str, pd.Timestamp, pd.Timestamp, str]]:
    """(ticker, month-end, next month-end, book) for B2 and N3, same rules as research/round14."""
    spy = d["spy"]["close"]
    dates = spy.index[spy.index >= "2010-01-01"]
    C, V = d["close"].reindex(dates).astype(float), d["volume"].reindex(dates).astype(float)
    dv = (C * V).rolling(20, min_periods=20).mean()
    big = dv.rank(axis=1, ascending=False) <= 500
    base = (C.notna().cumsum() >= 253) & (dv >= 10e6) & C.notna()
    m12 = C.shift(21) / C.shift(252) - 1
    f1 = C >= 0.75 * C.rolling(252, min_periods=200).max()
    gain = np.log(C.shift(21) / C.shift(252))
    f2 = (gain > 0) & (np.log(C).diff().shift(21).rolling(231, min_periods=200).max() < gain / 3)
    scores = {"B2": m12.where(base & big & (C >= 5)), "N3": m12.where(base & ~big & (C >= 10) & f1 & f2)}
    top = {"B2": 20, "N3": 10}
    bull = (spy > spy.rolling(200).mean()).reindex(dates)
    months = pd.Series(dates.month, index=dates)
    rebal = np.flatnonzero((months != months.shift(-1)).to_numpy())
    rebal = rebal[rebal >= 260]
    out = []
    for k, r in enumerate(rebal[:-1]):
        if not bull.iloc[r]:
            continue
        for name, sc in scores.items():
            row = sc.iloc[r].dropna().sort_values(ascending=False).iloc[:top[name]]
            out += [(t, dates[r], dates[rebal[k + 1]], name) for t in row.index]
    return out


def _work(args) -> list[dict]:
    rows, frames = args
    from ta.engine import analyze
    from ui.portfolio import chart_flags

    res = []
    for t, d0, d1, book in rows:
        df = frames[t]
        hist = df[df.index <= d0].iloc[-WINDOW:]
        fut = df[(df.index > d0) & (df.index <= d1)]
        if len(hist) < 260 or len(fut) < 5:
            continue
        ret = (fut["close"].iloc[-1] / fut["open"].iloc[0] - 1) * 100
        try:
            rep = analyze(t, hist, light=True)
        except Exception:  # noqa: BLE001
            continue
        if not rep.daily.ok:
            continue
        fa = rep.daily
        above = [z for z in fa.zones if z.low > fa.close]
        room = min((z.low - fa.close) / fa.atr for z in above) if above and fa.atr > 0 else np.inf
        warn, _ = chart_flags(rep)
        res.append({"ticker": t, "date": d0, "book": book, "ret": ret, "W1_resistance": room <= 1,
                    "W2_downtrend": fa.trend.direction < 0, "W3_exhausted": bool(fa.trend.exhaustion),
                    "any_warning": warn, "score": rep.score.total})
    return res


def main(path: str, workers: int = 4) -> int:
    d = pd.read_pickle(path)
    picks = _picks(d)
    tick = sorted({p[0] for p in picks})
    frames = {t: pd.DataFrame({k: d[k][t].astype(float) for k in ("open", "high", "low", "close", "volume")}).dropna(subset=["close"])
              for t in tick}
    print(f"{len(picks)} picks, {len(tick)} tickers", flush=True)
    by_t: dict[str, list] = {}
    for p in picks:
        by_t.setdefault(p[0], []).append(p)
    jobs = [(rows, {t: frames[t]}) for t, rows in by_t.items()]
    res = []
    with ProcessPoolExecutor(workers) as ex:
        for r in ex.map(_work, jobs, chunksize=8):
            res += r
    df = pd.DataFrame(res)
    df["excess"] = df["ret"] - df.groupby(["book", "date"])["ret"].transform("mean")
    df["period"] = "?"
    for p, (a, b) in PERIODS.items():
        df.loc[(df.date >= a) & (df.date <= b), "period"] = p
    df.to_pickle(path.replace(".pkl", "_q4.pkl"))
    print("flagged minus unflagged picks, next-month excess vs the month's pick average (%), t-stat, share flagged")
    for book in ("B2", "N3"):
        for flag in ("W1_resistance", "W2_downtrend", "W3_exhausted", "any_warning"):
            line = f"{book} {flag:<14}"
            for p in PERIODS:
                x = df[(df.book == book) & (df.period == p)]
                a, b = x[x[flag]]["excess"], x[~x[flag]]["excess"]
                if len(a) > 5 and len(b) > 5:
                    diff = a.mean() - b.mean()
                    t = diff / np.sqrt(a.var() / len(a) + b.var() / len(b))
                    line += f" | {p} {diff:+6.2f}% t {t:+5.1f} ({len(a) / len(x) * 100:3.0f}% flagged)"
                else:
                    line += f" | {p} -"
            print(line, flush=True)
        line = f"{book} score rank-corr  "
        for p in PERIODS:
            x = df[(df.book == book) & (df.period == p)]
            ic = pd.Series([g["score"].rank().corr(g["ret"].rank()) for _, g in x.groupby("date") if len(g) > 4],
                           dtype=float).dropna()
            line += f" | {p} IC {ic.mean():+.3f} t {ic.mean() / ic.std() * np.sqrt(len(ic)):+5.1f}"
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
