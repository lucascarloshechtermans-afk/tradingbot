"""Round 16: wait for a confirmed break of the resistance above a momentum pick.
    python -m research.round16 r14.pkl r15.pkl"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from research.round14 import PERIODS
from research.round15_data import members_at

WINDOW = 650


def _zone(args):
    """(ticker, [(date, ...)] , frame) -> {(ticker, date): (zone_low, zone_high, atr, close) or None}"""
    t, days, df = args
    from ta.engine import analyze

    out = {}
    for d0 in days:
        hist = df[df.index <= d0].iloc[-WINDOW:]
        if len(hist) < 260:
            continue
        try:
            fa = analyze(t, hist, light=True).daily
        except Exception:  # noqa: BLE001
            continue
        if not fa.ok or not fa.atr > 0:
            continue
        cand = [z for z in fa.zones if z.high > fa.close and z.low - fa.close <= fa.atr]
        z = min(cand, key=lambda z: z.low) if cand else None
        out[(t, d0)] = (z.low, z.high) if z else None
    return out


def main(r14: str, r15: str, workers: int = 4) -> int:
    d, m = pd.read_pickle(r14), pd.read_pickle(r15)
    spy = d["spy"]["close"]
    dates = spy.index[spy.index >= "2010-01-01"]
    F = {k: d[k].reindex(dates).astype(float) for k in ("open", "high", "low", "close", "volume")}
    for t, df in m["extra"].items():
        df.index = pd.DatetimeIndex(df.index).tz_localize(None) if df.index.tz is not None else df.index
        for k in F:
            F[k][t] = df[k.capitalize()].reindex(dates).astype(float)
    C, O, V = F["close"], F["open"], F["volume"]
    dv = (C * V).rolling(20, min_periods=20).mean()
    ok = (C.notna().cumsum() >= 253) & (dv >= 10e6) & (C >= 5)
    m12 = (C.shift(21) / C.shift(252) - 1).where(ok)
    bull = (spy > spy.rolling(200).mean()).reindex(dates)
    months = pd.Series(dates.month, index=dates)
    rebal = np.flatnonzero((months != months.shift(-1)).to_numpy())
    rebal = rebal[rebal >= 260]
    sp1000 = set(json.load(open(Path(__file__).resolve().parent.parent / "data" / "sp1000_members.json"))["members"])
    books = {"P1": lambda day: members_at(m["base"], m["changes"], day), "R1": lambda day: sp1000}
    picks = {b: [] for b in books}          # (k, ticker)
    for k, r in enumerate(rebal[:-1]):
        if not bull.iloc[r]:
            continue
        for b, mem in books.items():
            row = m12.iloc[r]
            row = row[row.index.isin(mem(dates[r]))].dropna().sort_values(ascending=False).iloc[:20]
            picks[b] += [(k, t) for t in row.index]
    need: dict[str, set] = {}
    for b in picks:
        for k, t in picks[b]:
            need.setdefault(t, set()).add(dates[rebal[k]])
    jobs = [(t, sorted(ds), pd.DataFrame({k: F[k][t] for k in F}).dropna(subset=["close"])) for t, ds in need.items()]
    zones = {}
    with ProcessPoolExecutor(workers) as ex:
        for z in ex.map(_zone, jobs, chunksize=4):
            zones.update(z)
    print(f"analysed {len(zones)} pick-months", flush=True)
    rf = (d["irx"].reindex(dates).ffill() / 100 / 252).fillna(0)
    c, o = C.to_numpy(), O.to_numpy()
    col = {t: j for j, t in enumerate(C.columns)}
    for b in picks:
        rows = []
        for k, t in picks[b]:
            r0, r1 = rebal[k], rebal[k + 1]
            j = col[t]
            z = zones.get((t, dates[r0]), "na")
            if z == "na":
                continue
            entry = o[r0 + 1, j]
            if not np.isfinite(entry) or entry <= 0:
                continue
            exit_ = c[r1, j] if np.isfinite(c[r1, j]) else np.nan
            ra = exit_ / entry - 1 - 0.002
            cash = float((1 + rf.iloc[r0 + 1:r1 + 1]).prod() - 1)
            res = {"k": k, "date": dates[r0], "ticker": t, "flag": z is not None, "A": ra}
            for name, need_closes in (("B", 2), ("B1", 1)):
                if z is None:
                    res[name] = ra
                    continue
                above = c[r0 + 1:r1, j] > z[1]
                run, hit = 0, None
                for i, a in enumerate(above):
                    run = run + 1 if a else 0
                    if run >= need_closes:
                        hit = r0 + 1 + i
                        break
                if hit is None or hit + 1 > r1:
                    res[name] = cash
                else:
                    e2 = o[hit + 1, j]
                    res[name] = exit_ / e2 - 1 - 0.002 if np.isfinite(e2) and e2 > 0 else cash
            rows.append(res)
        df = pd.DataFrame(rows)
        df["period"] = "?"
        for p, (a, bb) in PERIODS.items():
            df.loc[(df.date >= a) & (df.date <= bb), "period"] = p
        df.to_pickle(r14.replace(".pkl", f"_r16_{b}.pkl"))
        print(f"\n== {b}: {len(df)} pick-months, {df.flag.mean() * 100:.0f}% at resistance (zone within 1 ATR above)")
        fl = df[df.flag]
        for p in PERIODS:
            x = fl[fl.period == p]
            for name in ("B", "B1"):
                dif = (x[name] - x["A"]) * 100
                print(f"  {p} {name}: flagged picks, per-month return A {x['A'].mean() * 100:+.2f}%  {name} {x[name].mean() * 100:+.2f}%  "
                      f"diff {dif.mean():+.2f}% (t {dif.mean() / dif.std() * np.sqrt(len(dif)):+.1f}, n {len(dif)}); "
                      f"{name} never confirmed in {((x[name] - x['A']).abs() > 0).mean() * 100:.0f}% changed", flush=True)
        monthly = df.groupby("date")[["A", "B", "B1"]].mean()
        line = "  book (equal weight over the slots, monthly) Sharpe:"
        for p, (a, bb) in PERIODS.items():
            mm = monthly[(monthly.index >= a) & (monthly.index <= bb)]
            sh = {n: mm[n].mean() / mm[n].std() * np.sqrt(12) for n in ("A", "B", "B1")}
            line += f" | {p} A {sh['A']:.2f} B {sh['B']:.2f} B1 {sh['B1']:.2f}"
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
