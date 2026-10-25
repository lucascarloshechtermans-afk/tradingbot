"""Classic technical-analysis swing concepts (EMA trend pullbacks, support / resistance, market structure) on the NASDAQ
universe, daily or 4-hour bars, each with and without a GAMMA-EXPOSURE market filter.

    TA_TF=day python -m indicator_lab.h4.ta_concepts     # 2015-01-01 .. 2024-10-21 (daily, .cache20)
    TA_TF=4h  python -m indicator_lab.h4.ta_concepts     # ~2024-07 .. now (Yahoo 60m grouped to 4H)

Swing points: a 5-bar fractal (a high above the 2 bars on each side) is only KNOWN 2 bars after it, so every level used
on bar t comes from pivots confirmed by bar t (no look-ahead).
  A EMA pullback     EMA21 > EMA50 > EMA200, close > EMA50, the bar's low touches EMA21 and it closes above it, green
                     candle.                                            Exit: close < EMA50.        Stop 2 x ATR.
  B EMA21 reclaim    close crosses back above EMA21 while EMA50 > EMA200.  Exit: close < EMA21.     Stop 2 x ATR.
  C Resistance break resistance = a level hit by >= 2 confirmed swing highs (within 0.5 ATR) in the last 60 bars; close
                     crosses above it on >= 1.5 x the 50-bar average volume.  Exit: close < EMA21.  Stop 1.5 x ATR.
  D Support retest   within 3-20 bars after such a breakout the low comes back to within 0.5 ATR of the broken level and
                     the bar closes green above it.                     Exit: close < EMA21.        Stop 1.5 x ATR.
  E Market structure the last two confirmed swing lows rise (higher low) and the close breaks above the last confirmed
                     swing high (break of structure).                   Exit: close < last swing low. Stop 2 x ATR.
GEX filter: only when the S&P 500 dealer gamma exposure (SqueezeMetrics DIX.csv, daily since 2011) of the PREVIOUS
trading day was positive (dealers dampen moves; quieter market). Per-strike gamma of single stocks has no free history.
All: at most one BUY per stock per two weeks, liquidity floor, 0.1% per side + 0.1% entry slippage, fills next open.
"""
from __future__ import annotations

import os
import urllib.request

import numpy as np
import pandas as pd

os.environ["CLASSIC_TF"] = os.environ.get("TA_TF", "day")
from indicator_lab import ind
from indicator_lab.h4 import (
    classics as C,
)
from indicator_lab.swing4 import sim2 as S2

TF = C.TF
GEX_URL = "https://squeezemetrics.com/monitor/static/DIX.csv"
GEX_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache", "squeezemetrics_dix.csv")


def gex() -> pd.Series:
    if not os.path.exists(GEX_FILE):
        req = urllib.request.Request(GEX_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r, open(GEX_FILE, "wb") as fh:
            fh.write(r.read())
    d = pd.read_csv(GEX_FILE, parse_dates=["date"]).set_index("date")
    return d["gex"]


def pivots(h: np.ndarray, lo: np.ndarray, w: int = 2):
    """Confirmed swing highs/lows: value known at bar i + w for a pivot at bar i."""
    n = len(h)
    ph = np.full(n, np.nan)
    pl = np.full(n, np.nan)
    for i in range(w, n - w):
        if h[i] == h[i - w:i + w + 1].max():
            ph[i + w] = h[i]
        if lo[i] == lo[i - w:i + w + 1].min():
            pl[i + w] = lo[i]
    return ph, pl


def signals(df: pd.DataFrame) -> dict:
    """name -> (entry, exit, stop in ATR)"""
    o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    cs = df["close"]
    e21, e50, e200 = (ind.ema(cs, n).to_numpy() for n in (21, 50, 200))
    a = ind.atr(df, 14).to_numpy()
    vavg = df["volume"].rolling(50).mean().to_numpy()
    n = len(c)
    green = c > o
    with np.errstate(invalid="ignore"):
        ema_a = (e21 > e50) & (e50 > e200) & (c > e50) & (lo <= e21) & (c > e21) & green
        prev_c, prev_e21 = np.r_[np.nan, c[:-1]], np.r_[np.nan, e21[:-1]]
        ema_b = (c > e21) & (prev_c <= prev_e21) & (e50 > e200)
    ph, pl = pivots(h, lo)
    brk = np.zeros(n, bool)
    retest = np.zeros(n, bool)
    bos = np.zeros(n, bool)
    last_low = np.full(n, np.nan)
    highs: list = []    # (bar, price) of confirmed swing highs
    lows: list = []
    broken = None        # (bar, level) of the last resistance break
    for t in range(1, n):
        if not np.isnan(ph[t]):
            highs.append((t, ph[t]))
        if not np.isnan(pl[t]):
            lows.append((t, pl[t]))
        highs = [x for x in highs if x[0] > t - 60]
        if lows:
            last_low[t] = lows[-1][1]
        if not np.isfinite(a[t]):
            continue
        tol = 0.5 * a[t]
        # resistance: the highest level touched by >= 2 swing highs in the window
        lvl = None
        for _, p in highs:
            if sum(1 for _, q in highs if abs(q - p) <= tol) >= 2 and (lvl is None or p > lvl):
                lvl = p
        if lvl is not None and c[t] > lvl >= c[t - 1] and v[t] >= 1.5 * vavg[t]:
            brk[t] = True
            broken = (t, lvl)
        if broken is not None and 3 <= t - broken[0] <= 20:
            L = broken[1]
            if lo[t] <= L + tol and c[t] > L and green[t]:
                retest[t] = True
                broken = None
        if len(lows) >= 2 and lows[-1][1] > lows[-2][1] and highs:
            last_h = max(highs, key=lambda x: x[0])[1]
            if c[t] > last_h >= c[t - 1]:
                bos[t] = True
    with np.errstate(invalid="ignore"):
        below21 = c < e21
        return {"A EMA-pullback (21>50>200, raakt EMA21)": (ema_a, c < e50, 2.0),
                "B EMA21-reclaim (EMA50>EMA200)": (ema_b, below21, 2.0),
                "C Resistance-breakout (2x geraakt, 1.5x volume)": (brk, below21, 1.5),
                "D Support-retest na breakout": (retest, below21, 1.5),
                "E Marktstructuur: hogere bodem + break of structure": (bos, c < np.nan_to_num(last_low, nan=-1), 2.0)}


def run_all(fr: dict, start, end, g: pd.Series) -> dict:
    res: dict = {}
    min_dvol = 5e6 if TF == "day" else 2.5e6
    gpos = (g.shift(1) > 0)
    for t, df in fr.items():
        liquid = ((df["close"] >= 5) & ((df["close"] * df["volume"]).rolling(50).mean() >= min_dvol)).to_numpy()
        inwin = (df.index >= start) & (df.index <= end)
        gok = gpos.reindex(df.index.normalize(), method="ffill").fillna(False).to_numpy()
        a = ind.atr(df, 14).to_numpy()
        for name, (e, x, stop) in signals(df).items():
            pol = S2.Policy(trail=1e6, stop=stop, min_gap_days=14)
            arr = S2.arrays(df, a, x)
            for tag, filt in (("", np.ones(len(df), bool)), (" + GEX > 0", gok)):
                r, tr = S2.simulate(arr, e & liquid & inwin & filt, pol, slip=C.SLIP)
                for z in tr:
                    z["ticker"] = t
                rs = pd.Series(r, index=df.index)
                res.setdefault(name + tag, {})[t] = (rs[(rs.index >= start) & (rs.index <= end)], tr)
    return res


def main():
    from indicator_lab.evaluate import get
    from indicator_lab.metrics import equity_stats
    g = gex()
    fr = C.frames()
    if TF == "day":
        start, end = C.PERIOD_DAY
    else:
        idx = pd.DatetimeIndex(sorted({d for df in fr.values() for d in df.index}))
        start, end = idx[300], idx[-1]
    res = run_all(fr, start, end, g)
    rows = [C.summary(name, r) for name, r in res.items()]
    spy = get("SPY")["close"].pct_change()
    spy = spy[(spy.index >= start.normalize()) & (spy.index <= end)].fillna(0)
    s = equity_stats(spy)
    rows.append({"strategie": "SPY kopen en vasthouden", "CAGR (10 pos.)": f"{s['cagr'] * 100:.1f}%",
                 "max DD": f"{s['maxdd'] * 100:.1f}%", "Sharpe": f"{s['sharpe']:.2f}"})
    gw = g[(g.index >= start.normalize()) & (g.index <= end)]
    txt = (f"# TA-concepten, {'dagbars' if TF == 'day' else '4H-bars'}, {len(fr)} NASDAQ-aandelen, {start.date()} .. "
           f"{end.date()}\n\nGEX > 0 op {(gw > 0).mean() * 100:.0f}% van de handelsdagen in deze periode. Max 1 BUY per "
           "aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%.\n\n"
           + pd.DataFrame(rows).fillna("–").to_markdown(index=False) + "\n")
    os.makedirs(C.OUT, exist_ok=True)
    with open(os.path.join(C.OUT, f"ta_concepts_{TF}.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
