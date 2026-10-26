"""Relative-strength rotation (cross-sectional momentum), the most documented swing/position edge in the literature
(Jegadeesh & Titman 1993; IBD RS rating; Antonacci dual momentum): every two weeks hold the N strongest liquid NASDAQ
stocks, equal weight; optionally only while SPY is above its SMA200 (else T-bills).

    python -m indicator_lab.rotation.mom            # development: NASDAQ dev universe, 2015-01-01 .. 2024-10-21

Decided before the grid ran (8 variants, nothing else is tried on this data):
  score   12-1 momentum (close 21 bars ago / close 252 bars ago - 1)  or  IBD-style RS (0.4 ROC63 + 0.2 ROC126/189/252)
  N       10 or 20 stocks
  filter  none, or SPY > SMA200 at the signal close (else everything in T-bills until the next rebalance)
  rebalance every 10 trading days (the user's two-week rhythm: at most one BUY per stock per two weeks follows from it)
  eligible at the signal close: close >= $5, 50-day average dollar volume >= $5M, 253 days of history
  fills at the next open; 0.1% per side on traded value + 0.1% slippage on buys; idle cash earns the T-bill rate
  ACCEPT = Sharpe (excess of T-bills) AND MAR above SPY buy & hold, on the full universe and on both ticker halves.
Survivorship: the universe is stocks still listed in 2026, which flatters every long strategy; the equal-weight average
of the same liquid stocks is reported as the fair hurdle next to SPY.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "reports")
COST, SLIP, EVERY = 0.001, 0.001, 10
PERIOD = (pd.Timestamp("2015-01-01"), pd.Timestamp("2024-10-21"))


def matrices(fr: dict, cal: pd.DatetimeIndex) -> dict:
    """Close/open matrices on the SPY calendar (ffilled inside a listing only) and the eligibility mask."""
    Cl = pd.concat({t: d["close"] for t, d in fr.items()}, axis=1).reindex(cal)
    Op = pd.concat({t: d["open"] for t, d in fr.items()}, axis=1).reindex(cal)
    V = pd.concat({t: d["volume"] for t, d in fr.items()}, axis=1).reindex(cal)
    alive = Cl.notna()
    Cf = Cl.ffill().where(alive.cummax())
    Of = Op.where(Op.notna(), Cf)
    hist = alive.cumsum() >= 253
    elig = (Cf >= 5) & ((Cl * V).rolling(50, min_periods=40).mean() >= 5e6) & hist & alive
    return {"C": Cf, "O": Of, "elig": elig}


def scores(C: pd.DataFrame) -> dict:
    roc = lambda n: C / C.shift(n) - 1
    return {"12-1 momentum": C.shift(21) / C.shift(252) - 1,
            "IBD-RS": 0.4 * roc(63) + 0.2 * (roc(126) + roc(189) + roc(252))}


def backtest(M: dict, score: pd.DataFrame, n: int, use_filter: bool, mkt: pd.DataFrame, start, end) -> dict:
    """Daily close-to-close portfolio returns; positions rebalanced at the open after each signal close."""
    C, O = M["C"].to_numpy(), M["O"].to_numpy()
    E = M["elig"].to_numpy()
    S = score.to_numpy()
    idx = M["C"].index
    rf = mkt["rf"].reindex(idx).fillna(0).to_numpy()
    spy_up = (mkt["on"].shift(-1)).reindex(idx).fillna(0).to_numpy() > 0   # 'on' is shifted: on[t+1] = SPY>SMA200 at t
    i0 = int(np.searchsorted(idx, start))
    i1 = int(np.searchsorted(idx, end, side="right")) - 1
    sig = set(range(i0, i1, EVERY))
    hv = {}          # column -> value held (at the previous close)
    cash = 1.0
    eq = np.ones(len(idx))
    period_rets: list = []   # (column, price return from the buy open to the sell open) per position
    entry = {}       # column -> buy price (open)
    turnover = []
    for d in range(i0 + 1, i1 + 1):
        if d - 1 in sig:   # trade at today's open
            for j in hv:
                hv[j] *= O[d, j] / C[d - 1, j]
            tot = cash + sum(hv.values())
            picks = []
            s = d - 1
            if not use_filter or spy_up[s]:
                ok = E[s] & np.isfinite(S[s])
                cand = np.where(ok)[0]
                if len(cand):
                    picks = list(cand[np.argsort(-S[s, cand])][:n])
            target = {j: tot / n for j in picks}
            traded = sum(abs(target.get(j, 0) - hv.get(j, 0)) for j in set(target) | set(hv))
            bought = sum(max(target.get(j, 0) - hv.get(j, 0), 0) for j in set(target) | set(hv))
            fee = traded * COST + bought * SLIP
            target = {j: v * (tot - fee) / tot for j, v in target.items()}   # costs buy fewer shares
            for j in list(hv):
                if j not in target:
                    period_rets.append((j, O[d, j] / entry.pop(j) - 1))
            for j in target:
                if j not in hv:
                    entry[j] = O[d, j]
            turnover.append(traded / tot if tot > 0 else 0)
            hv = dict(target)
            cash = tot - sum(hv.values()) - fee
            for j in hv:
                hv[j] *= C[d, j] / O[d, j]
        else:
            for j in hv:
                hv[j] *= C[d, j] / C[d - 1, j]
        cash *= 1 + rf[d]
        eq[d] = cash + sum(hv.values())
    for j in hv:
        period_rets.append((j, C[i1, j] / entry[j] - 1))
    e = pd.Series(eq[i0:i1 + 1], index=idx[i0:i1 + 1])
    return {"ret": e.pct_change().fillna(0), "positions": period_rets, "turnover": float(np.mean(turnover)) * 26}


def stats(r: pd.Series, mkt: pd.DataFrame) -> dict:
    from indicator_lab.metrics import equity_stats
    s = equity_stats(r)
    ex = r - mkt["rf"].reindex(r.index).fillna(0)
    s["sharpe_rf"] = float(ex.mean() / ex.std() * np.sqrt(252)) if ex.std() > 0 else 0.0
    return s


def equal_weight(M: dict, start, end) -> pd.Series:
    """Hurdle: every eligible stock, equal weight, rebalanced daily (close to close), no costs."""
    r = M["C"].pct_change(fill_method=None).clip(-0.9, 1.0)
    r = r.where(M["elig"].shift(1, fill_value=False))
    ew = r.mean(axis=1).fillna(0)
    return ew[(ew.index >= start) & (ew.index <= end)]


def top_share(pos: list, k: int = 10) -> float:
    g = np.sort([p for _, p in pos])[::-1]
    pos_sum = g[g > 0].sum()
    return float(g[:k].sum() / pos_sum) if pos_sum > 0 else np.nan


def run_grid(M: dict, mkt: pd.DataFrame, start, end, halves=None) -> list[dict]:
    rows = []
    sc = scores(M["C"])
    cols = list(M["C"].columns)
    for sname, S in sc.items():
        for n in (10, 20):
            for filt in (False, True):
                bt = backtest(M, S, n, filt, mkt, start, end)
                st = stats(bt["ret"], mkt)
                row = {"variant": f"{sname}, top {n}{', alleen SPY > SMA200' if filt else ''}", "score": sname, "n": n,
                       "filter": filt, **st, "turnover": bt["turnover"], "positions": len(bt["positions"]),
                       "win": float(np.mean([p > 0 for _, p in bt["positions"]])),
                       "top10_share": top_share(bt["positions"]), "ret": bt["ret"]}
                if halves:
                    hs = []
                    for h in halves:
                        keep = [cols.index(t) for t in h]
                        Mh = {k: v.iloc[:, keep] for k, v in M.items()}
                        hs.append(stats(backtest(Mh, S.iloc[:, keep], n, filt, mkt, start, end)["ret"], mkt))
                    row["halves"] = hs
                rows.append(row)
                print(f"{row['variant']:45s} CAGR {st['cagr'] * 100:5.1f}% DD {st['maxdd'] * 100:6.1f}% "
                      f"Sh {st['sharpe_rf']:.2f} MAR {st['mar']:.2f}"
                      + ("" if not halves else " | halves Sh " + " / ".join(f"{h['sharpe_rf']:.2f}" for h in row["halves"])),
                      flush=True)
    return rows


def bench_rows(M, mkt, start, end) -> dict:
    from indicator_lab.evaluate import get
    idx = M["C"].index
    idx = idx[(idx >= start) & (idx <= end)]
    m = mkt.reindex(idx)
    spy = m["spy"].fillna(0)
    timing = spy * m["on"] + m["rf"] * (1 - m["on"])
    qqq = get("QQQ")["close"].pct_change().reindex(idx).fillna(0)
    return {"SPY kopen en vasthouden": spy, "QQQ kopen en vasthouden": qqq,
            "SPY alleen boven SMA200, anders T-bills": timing,
            "gemiddeld liquide aandeel (gelijk gewogen, survivors)": equal_weight(M, start, end)}


def table(rows, bench, mkt) -> str:
    d = []
    for r in rows:
        x = {"variant": r["variant"], "CAGR": f"{r['cagr'] * 100:.1f}%", "max DD": f"{r['maxdd'] * 100:.1f}%",
             "Sharpe": f"{r['sharpe_rf']:.2f}", "MAR": f"{r['mar']:.2f}", "posities": r["positions"],
             "winrate posities": f"{r['win'] * 100:.0f}%", "top-10 posities = % winst": f"{r['top10_share'] * 100:.0f}%",
             "omzet/jaar": f"{r['turnover']:.1f}x"}
        if "halves" in r:
            x["Sharpe helften"] = " / ".join(f"{h['sharpe_rf']:.2f}" for h in r["halves"])
            x["voldoet"] = "JA" if r.get("accept") else "nee"
        d.append(x)
    for k, r in bench.items():
        s = stats(r, mkt)
        d.append({"variant": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                  "Sharpe": f"{s['sharpe_rf']:.2f}", "MAR": f"{s['mar']:.2f}"})
    return pd.DataFrame(d).fillna("–").to_markdown(index=False)


def main():
    os.environ.setdefault("CLASSIC_TF", "day")
    from indicator_lab.evaluate import get
    from indicator_lab.h4 import classics as C
    from indicator_lab.swing5 import port as PT
    fr = C.frames()
    cal = get("SPY").index
    cal = cal[cal <= PERIOD[1]]
    M = matrices(fr, cal)
    mkt = PT.market(cal)
    tick = sorted(fr)
    rows = run_grid(M, mkt, *PERIOD, halves=(tick[0::2], tick[1::2]))
    bench = bench_rows(M, mkt, *PERIOD)
    spy = stats(bench["SPY kopen en vasthouden"], mkt)
    for r in rows:
        r["accept"] = (r["sharpe_rf"] > spy["sharpe_rf"] and r["mar"] > spy["mar"]
                       and all(h["sharpe_rf"] > spy["sharpe_rf"] and h["mar"] > spy["mar"] for h in r["halves"]))
    txt = (f"# Relatieve-sterkte-rotatie — ontwikkeling ({len(fr)} NASDAQ-aandelen, {PERIOD[0].date()} .. "
           f"{PERIOD[1].date()})\n\nElke 10 handelsdagen de N sterkste liquide aandelen, gelijk gewogen; vullen op de "
           "volgende open; 0,1%/kant + 0,1% slippage op kopen; lege kas in T-bills. Criterium (vooraf): Sharpe én MAR "
           "boven SPY, ook in beide tickerhelften.\n\n" + table(rows, bench, mkt) + "\n")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "dev.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
