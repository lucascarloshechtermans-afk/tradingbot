"""Market-regime timing on the index (the only idea in this project that improved risk on development data: "SPY only
above its SMA200, else T-bills"). Published variants, tested on decades the project has never used.

    python -m indicator_lab.timing.regime dev        # SPY 2012-01-03 .. 2024-10-21 (already seen data)
    python -m indicator_lab.timing.regime holdout    # ONE run: never-used periods (see below)

Variants (fixed before any run; no parameter is tuned):
  T1 SMA200          long while close > SMA(200), else T-bills (checked every day)
  T2 SMA200 band 2%  enter when close > 1.02 x SMA200, leave when close < 0.98 x SMA200 (fewer whipsaws)
  T3 Faber 10-month  long while the month-end close > 10-month SMA of month-end closes (Faber 2007), checked monthly
  T4 Abs. momentum   long while the 12-month return beats the 12-month T-bill return (Antonacci), checked monthly
  T5 Vol target 15%  exposure = min(1, 15% / 20-day realised volatility), updated weekly (Moreira & Muir 2017)
  T6 = T1 x T5       T7 = T2 x T5
Execution: decided on a close, traded on the NEXT day's close (one full day of delay); 0.1% cost per unit of exposure
changed; cash earns the 13-week T-bill rate (^IRX, from 1960). Index series without dividends (^GSPC, ^NDX) are
compared with buy & hold of the same price series.

Selection (before the holdout): on dev, the variant with the highest MAR among those with Sharpe (excess) >= SPY's.
Holdout segments: SPY 1993-02-01 .. 2011-12-30, ^GSPC 1960-01-04 .. 1992-12-31, ^NDX 1987-01-02 .. 2011-12-30,
SPY 2024-10-22 .. 2026-10-23. PASS for the selected variant = in at least 3 of the 4 segments both MAR above and
Sharpe (excess) at least equal to buy & hold. All variants are reported on every segment.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "reports")
LONG = os.path.join(os.path.dirname(HERE), ".cache", "long")
COST = 0.001
DEV = ("SPY", "2012-01-03", "2024-10-21")
HOLDOUT = [("SPY", "1993-02-01", "2011-12-30"), ("_GSPC", "1960-01-04", "1992-12-31"),
           ("_NDX", "1987-01-02", "2011-12-30"), ("SPY", "2024-10-22", "2026-10-23")]
SELECTED = os.path.join(HERE, "selected.json")


def load(name: str) -> pd.Series:
    d = pd.read_csv(os.path.join(LONG, f"{name}.csv.gz"), index_col=0, parse_dates=True)
    return d["close"].dropna()


def month_end(idx: pd.DatetimeIndex) -> np.ndarray:
    """True on the last trading day of each month (the final bar of the data is not known to be one)."""
    p = pd.Series(idx, index=idx).dt.to_period("M")
    out = (p != p.shift(-1)).to_numpy()
    out[-1] = False
    return out


def hysteresis(enter: np.ndarray, leave: np.ndarray) -> np.ndarray:
    w = np.zeros(len(enter))
    state = 0.0
    for i in range(len(enter)):
        if state == 0 and enter[i]:
            state = 1.0
        elif state == 1 and leave[i]:
            state = 0.0
        w[i] = state
    return w


def monthly_hold(sig: np.ndarray, me: np.ndarray) -> np.ndarray:
    """Signal sampled at month ends, held until the next month end."""
    w = np.full(len(sig), np.nan)
    w[me] = sig[me]
    return pd.Series(w).ffill().fillna(0).to_numpy()


def weights(c: pd.Series, rf_d: pd.Series) -> dict:
    """Decided exposure on each close (0..1)."""
    sma = c.rolling(200).mean().to_numpy()
    x = c.to_numpy()
    me = month_end(c.index)
    with np.errstate(invalid="ignore"):
        t1 = (x > sma).astype(float)
        t2 = hysteresis(x > 1.02 * sma, x < 0.98 * sma)
        mc = pd.Series(np.where(me, x, np.nan), index=c.index).dropna()
        sma10 = mc.rolling(10).mean().reindex(c.index).to_numpy()
        t3 = monthly_hold(x > sma10, me)
        r12 = x / c.shift(252).to_numpy() - 1
        rf12 = (1 + rf_d).rolling(252).apply(np.prod, raw=True).to_numpy() - 1
        t4 = monthly_hold(r12 > rf12, me)
        vol = c.pct_change().rolling(20).std().to_numpy() * np.sqrt(252)
        vt = np.minimum(1.0, 0.15 / vol)
        wk = np.zeros(len(x), bool)
        wk[::5] = True
        vt = pd.Series(np.where(wk, vt, np.nan)).ffill().to_numpy()
    out = {"T1 SMA200": t1, "T2 SMA200 met 2%-band": t2, "T3 Faber 10-maands SMA": t3,
           "T4 absoluut momentum (12m vs T-bills)": t4, "T5 volatiliteitsdoel 15%": vt,
           "T6 SMA200 x vol-doel": t1 * vt, "T7 SMA200-band x vol-doel": t2 * vt}
    return {k: np.nan_to_num(v) for k, v in out.items()}


def simulate(c: pd.Series, rf_d: pd.Series, w_dec: np.ndarray) -> pd.Series:
    r = c.pct_change().fillna(0).to_numpy()
    w = np.r_[0.0, 0.0, w_dec[:-2]]            # decided at close t, traded at close t+1, earns from t+2
    dw = np.abs(np.diff(np.r_[0.0, w]))
    rf = rf_d.to_numpy()
    return pd.Series(w * r + (1 - w) * rf - dw * COST, index=c.index)


def stats(r: pd.Series, rf: pd.Series) -> dict:
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = float((eq / eq.cummax() - 1).min())
    ex = r - rf
    return {"cagr": float(cagr), "maxdd": dd, "mar": float(cagr / -dd) if dd < 0 else 0.0,
            "sharpe": float(ex.mean() / ex.std() * np.sqrt(252))}


def segment(name: str, start: str, end: str) -> tuple[dict, dict]:
    c = load(name)
    irx = load("_IRX")
    rf_all = (irx.reindex(c.index).ffill() / 100 / 252).shift(1).fillna(0)
    ws = weights(c, rf_all)
    m = (c.index >= start) & (c.index <= end)
    rf = rf_all[m]
    res = {"kopen en vasthouden": stats(c.pct_change().fillna(0)[m], rf)}
    exposure = {}
    for k, w in ws.items():
        r = simulate(c, rf_all, w)[m]
        res[k] = stats(r, rf)
        wd = np.r_[0.0, 0.0, w[:-2]][m]
        exposure[k] = (float(wd.mean()), int((np.abs(np.diff(wd)) > 0.5).sum() / (m.sum() / 252)))
    return res, exposure


def table(res: dict, exposure: dict) -> str:
    rows = []
    for k, s in res.items():
        e = exposure.get(k)
        rows.append({"variant": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                     "MAR": f"{s['mar']:.2f}", "Sharpe": f"{s['sharpe']:.2f}",
                     "gem. belegd": f"{e[0] * 100:.0f}%" if e else "100%",
                     "wissels/jaar": e[1] if e else 0})
    return pd.DataFrame(rows).to_markdown(index=False)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    os.makedirs(OUT, exist_ok=True)
    if mode == "dev":
        res, ex = segment(*DEV)
        bh = res["kopen en vasthouden"]
        ok = {k: s for k, s in res.items() if k != "kopen en vasthouden" and s["sharpe"] >= bh["sharpe"]}
        pick = max(ok, key=lambda k: ok[k]["mar"]) if ok else None
        txt = (f"# Markttiming — ontwikkeling ({DEV[0]} {DEV[1]} .. {DEV[2]})\n\n" + table(res, ex)
               + f"\n\nGekozen volgens de vooraf vastgelegde regel (hoogste MAR met Sharpe >= kopen en vasthouden): "
               f"**{pick}**\n")
        if os.path.exists(SELECTED):
            raise SystemExit("selection already made: " + SELECTED)
        with open(SELECTED, "w") as fh:
            json.dump({"selected": pick}, fh)
        with open(os.path.join(OUT, "dev.md"), "w") as fh:
            fh.write(txt)
        print(txt)
        return
    mark = os.path.join(HERE, "holdout_used.json")
    if os.path.exists(mark):
        raise SystemExit("holdout already used")
    with open(SELECTED) as fh:
        pick = json.load(fh)["selected"]
    with open(mark, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat(), "selected": pick}, fh)
    parts, wins = [], 0
    for seg in HOLDOUT:
        res, ex = segment(*seg)
        bh, s = res["kopen en vasthouden"], res[pick]
        win = s["mar"] > bh["mar"] and s["sharpe"] >= bh["sharpe"]
        wins += win
        parts.append(f"## {seg[0].replace('_', '^')} {seg[1]} .. {seg[2]} — gekozen variant {'beter' if win else 'NIET beter'}"
                     f"\n\n{table(res, ex)}\n")
    verdict = "GESLAAGD" if wins >= 3 else "NIET GESLAAGD"
    txt = (f"# Markttiming — holdout (eenmalig)\n\nGekozen variant (vooraf, op ontwikkeldata): **{pick}**. Beter dan "
           f"kopen en vasthouden (MAR hoger én Sharpe minstens gelijk) in {wins} van de 4 perioden: **{verdict}** "
           "(nodig: 3 van 4).\n\n" + "\n".join(parts))
    with open(os.path.join(OUT, "holdout.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
