"""Short-term mean reversion on stock INDICES (Larry Connors, "Short Term Trading Strategies That Work", 2008; the
classics were designed for the S&P 500, not for small caps, which is where this project tested them before).

    python -m indicator_lab.meanrev.index_mr        # ONE run (marker file blocks reruns)

Fixed before any result was seen (the book's parameters, nothing tuned):
  M1 RSI(2) < 10 and close > SMA200            exit: close > SMA5
  M2 2-day cumulative RSI(2) < 35, > SMA200    exit: RSI(2) > 65
  M3 Double 7s: close = lowest close of 7 days, > SMA200      exit: close = highest close of 7 days
  M4 IBS < 0.2 (close in the bottom 20% of the day's range), > SMA200   exit: close > the previous day's high
Execution: signal on the close, buy at the NEXT open; exit signal on a close, sell at the next open; one position at a
time; 0.1% cost per side; idle cash earns the 13-week T-bill rate on US segments (from 1960) and 0% elsewhere (the
buy & hold comparison uses the same cash rate in its Sharpe).
Segments (only years with real opening prices): development SPY and QQQ 2012-01-03 .. 2024-10-21 (reported only);
holdout: SPY 1993-11-15 .. 2011-12-30, ^GSPC 1963-01-02 .. 1992-12-31, ^NDX 1987-01-02 .. 2011-12-30,
SPY and QQQ 2024-10-22 .. 2026-10-22, and 12 foreign indices from their first year with opens to 2026-10-22
(these foreign series were used for the SMA200 trend test, a different rule; disclosed).
PASS for a rule = Sharpe above buy & hold's in at least 13 of the 17 holdout segments AND the pooled average trade
after costs above +0.2%. Every rule is reported on every segment.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab import ind
from indicator_lab.timing import regime as R

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "reports")
MARK = os.path.join(HERE, "index_mr_used.json")
COST = 0.001
END = "2026-10-22"
DEV = [("SPY", "2012-01-03", "2024-10-21"), ("QQQ", "2012-01-03", "2024-10-21")]
HOLD = [("SPY", "1993-11-15", "2011-12-30"), ("_GSPC", "1963-01-02", "1992-12-31"), ("_NDX", "1987-01-02", "2011-12-30"),
        ("SPY", "2024-10-22", END), ("QQQ", "2024-10-22", END),
        ("_AEX", "1993-01-04", END), ("_BVSP", "1994-01-03", END), ("_FCHI", "1991-01-02", END), ("_FTSE", "1985-01-02", END),
        ("_GDAXI", "1995-01-02", END), ("_GSPTSE", "1980-01-02", END), ("_HSI", "1991-01-02", END), ("_KS11", "1998-01-02", END),
        ("_N225", "1990-01-04", END), ("_SSMI", "1991-01-03", END), ("_TWII", "1998-01-05", END), ("_AXJO", "2002-01-02", END)]
US = {"SPY", "QQQ", "_GSPC", "_NDX"}


def load(name: str) -> pd.DataFrame:
    d = pd.read_csv(os.path.join(R.LONG, f"{name}.csv.gz"), index_col=0, parse_dates=True)
    d = d[["open", "high", "low", "close"]].dropna()
    return d[(d > 0).all(axis=1)]


def rules(d: pd.DataFrame) -> dict:
    c, h, lo = d["close"], d["high"], d["low"]
    up = c > ind.sma(c, 200)
    r2 = ind.rsi(c, 2)
    rng = (h - lo).replace(0, np.nan)
    ibs = (c - lo) / rng
    out = {"M1 RSI(2) < 10, uit: slot > SMA5": (up & (r2 < 10), c > ind.sma(c, 5)),
           "M2 cumulatieve RSI(2) < 35, uit: RSI(2) > 65": (up & (r2 + r2.shift(1) < 35), r2 > 65),
           "M3 Double 7s": (up & (c <= c.rolling(7).min()), c >= c.rolling(7).max()),
           "M4 IBS < 0.2, uit: slot > high van gisteren": (up & (ibs < 0.2), c > h.shift(1))}
    return {k: (np.nan_to_num(e.to_numpy(float)).astype(bool), np.nan_to_num(x.to_numpy(float)).astype(bool))
            for k, (e, x) in out.items()}


def simulate(d: pd.DataFrame, entry: np.ndarray, exit_: np.ndarray, rf: np.ndarray, i0: int, i1: int):
    """Daily returns on [i0, i1] and the trades; signals only from bars i0 .. i1-1 (fills inside the window)."""
    o, c = d["open"].to_numpy(), d["close"].to_numpy()
    ret = np.zeros(i1 - i0 + 1)
    held = np.zeros(i1 - i0 + 1, bool)     # invested at some point of the day
    trades = []
    pos = False
    ep = 0.0
    sell_next = buy_next = False
    for t in range(i0, i1 + 1):
        k = t - i0
        if buy_next:                       # fill at today's open
            pos, ep, buy_next = True, o[t], False
            ret[k] = c[t] / o[t] - 1 - COST
            held[k] = True
        elif sell_next:
            ret[k] = o[t] / c[t - 1] - 1 - COST   # sold at the open, rest of the day in cash
            trades.append(o[t] * (1 - COST) / (ep * (1 + COST)) - 1)
            pos, sell_next = False, False
            held[k] = True
        elif pos:
            ret[k] = c[t] / c[t - 1] - 1
            held[k] = True
        else:
            ret[k] = rf[t]
        if t == i1:
            break
        if pos and exit_[t] and not entry[t]:
            sell_next = True
        elif not pos and not buy_next and entry[t]:
            buy_next = True
    if pos:
        trades.append(c[i1] * (1 - COST) / (ep * (1 + COST)) - 1)
    return ret, trades, held


def stats(r: np.ndarray, rf: np.ndarray) -> dict:
    eq = np.cumprod(1 + r)
    yrs = len(r) / 252
    dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    ex = r - rf
    cagr = eq[-1] ** (1 / yrs) - 1
    return {"cagr": float(cagr), "maxdd": dd, "sharpe": float(ex.mean() / ex.std() * np.sqrt(252)) if ex.std() > 0 else 0.0}


def segment(name, start, end) -> dict:
    d = load(name)
    d = d[d.index <= end]
    if name in US:
        irx = pd.read_csv(os.path.join(R.LONG, "_IRX.csv.gz"), index_col=0, parse_dates=True)["close"]
        rf = (irx.reindex(d.index).ffill() / 100 / 252).shift(1).fillna(0).to_numpy()
    else:
        rf = np.zeros(len(d))
    i0 = int(np.searchsorted(d.index, pd.Timestamp(start)))
    i1 = len(d) - 1
    seg_rf = rf[i0:i1 + 1]
    c = d["close"].to_numpy()
    bh = np.r_[0.0, c[i0 + 1:i1 + 1] / c[i0:i1] - 1]
    out = {"bh": stats(bh, seg_rf), "label": f"{name.replace('_', '^')} {d.index[i0].date()} .. {d.index[i1].date()}"}
    for k, (e, x) in rules(d).items():
        r, tr, held = simulate(d, e, x, rf, i0, i1)
        s = stats(r, seg_rf)
        s.update({"trades": tr, "exposure": float(held.mean())})
        out[k] = s
    return out


def table(seg: dict, names) -> str:
    rows = [{"regel": "kopen en vasthouden", "CAGR": f"{seg['bh']['cagr'] * 100:.1f}%",
             "max DD": f"{seg['bh']['maxdd'] * 100:.0f}%", "Sharpe": f"{seg['bh']['sharpe']:.2f}"}]
    for k in names:
        s = seg[k]
        t = np.array(s["trades"])
        rows.append({"regel": k, "trades": len(t), "winrate": f"{(t > 0).mean() * 100:.0f}%" if len(t) else "–",
                     "gem. trade": f"{t.mean() * 100:.2f}%" if len(t) else "–", "belegd": f"{s['exposure'] * 100:.0f}%",
                     "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.0f}%", "Sharpe": f"{s['sharpe']:.2f}",
                     "beter dan B&H": "ja" if s["sharpe"] > seg["bh"]["sharpe"] else "nee"})
    return pd.DataFrame(rows).fillna("–").to_markdown(index=False)


def main():
    if os.path.exists(MARK):
        raise SystemExit("already run")
    with open(MARK, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    dev = [segment(*s) for s in DEV]
    hold = [segment(*s) for s in HOLD]
    names = [k for k in dev[0] if k not in ("bh", "label")]
    summ = []
    for k in names:
        wins = sum(h[k]["sharpe"] > h["bh"]["sharpe"] for h in hold)
        pooled = np.concatenate([h[k]["trades"] for h in hold])
        ok = wins >= 13 and pooled.mean() > 0.002
        summ.append({"regel": k, "holdout: Sharpe > B&H": f"{wins} / {len(hold)}", "trades": len(pooled),
                     "winrate": f"{(pooled > 0).mean() * 100:.0f}%", "gem. trade": f"{pooled.mean() * 100:.2f}%",
                     "oordeel": "GESLAAGD" if ok else "niet geslaagd"})
    txt = ("# Connors-mean-reversion op indexen — eenmalige test\n\nRegels en criterium vooraf vastgelegd (zie "
           "`index_mr.py`): Sharpe boven kopen-en-vasthouden in >= 13 van 17 holdout-perioden én gemiddelde trade > 0,2%.\n\n"
           "## Samenvatting holdout\n\n" + pd.DataFrame(summ).to_markdown(index=False) + "\n\n## Ontwikkeling (alleen ter info)\n\n"
           + "\n\n".join(f"### {s['label']}\n\n{table(s, names)}" for s in dev)
           + "\n\n## Holdout per periode\n\n" + "\n\n".join(f"### {s['label']}\n\n{table(s, names)}" for s in hold) + "\n")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "index_mr.md"), "w") as fh:
        fh.write(txt)
    print(txt[:3000])


if __name__ == "__main__":
    main()
