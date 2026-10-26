"""Swing methods that well-known professional traders publish and teach, as hard rules without look-ahead, on the NASDAQ
universe (daily or 4-hour bars), each with and without the market-uptrend rule (SPY > SMA200 on the previous day,
O'Neil's "M").

    PRO_TF=day python -m indicator_lab.h4.pro_concepts     # 2015-01-01 .. 2024-10-21 (daily, .cache20)
    PRO_TF=4h  python -m indicator_lab.h4.pro_concepts     # ~2024-07 .. now (Yahoo 60m grouped to 4H)

On 4H the same rules are applied in 4H bars (as on a 4H chart), not rescaled to calendar days.
RS = IBD-style relative strength: 0.4 x ROC63 + 0.2 x (ROC126 + ROC189 + ROC252), ranked across the universe per bar.
  P1 Minervini trend template + VCP breakout: close > SMA50 > SMA150 > SMA200, SMA200 above its level 21 bars ago,
     close >= 1.3 x 252-bar low and >= 0.75 x 252-bar high, RS >= 80th pct; the prior 10 bars range <= 10% and
     < half of the 40-bar range, 10-bar volume < 50-bar volume (dry-up); close above the 10-bar high on >= 1.4 x volume.
     Exit close < SMA50. Stop -8%.
  P2 Qullamaggie breakout: >= +30% over 63 bars, ADR(20) >= 4%, EMA10 > EMA20, close > EMA20, prior 10-bar range <= 15%;
     close above the 10-bar high on >= 1.5 x volume. Exit close < EMA10. Stop 1 x ATR (about the low of the day).
  P3 Episodic pivot (Qullamaggie): open >= 10% above the prior close, volume >= 3 x average, closes green in the upper
     half of the bar. Exit close < EMA10. Stop 1 x ATR.
  P4 Holy Grail (Linda Raschke): ADX(14) > 30 with +DI > -DI, the prior bar's low touched EMA20, close above that bar's
     high. Exit close < EMA20. Stop 1.5 x ATR.
  P5 Turtle Soup (Raschke): the low breaks the prior 20-bar low (made >= 4 bars earlier) and the bar closes back above
     it. Exit close > the prior 5-bar high. Stop 1 x ATR.
  P6 Weinstein stage-2 breakout: SMA150 (30 weeks) rising, close > SMA150 and above the prior 50-bar high on >= 2 x
     volume, RS >= 50th pct. Exit close < SMA150. Stop 3 x ATR.
  P7 Pocket pivot (Morales & Kacher): green bar, close up, volume > the largest down-bar volume of the prior 10 bars,
     close > SMA50 (rising), close <= 1.05 x SMA10 (not extended). Exit close < SMA50. Stop -8%.
  P8 Anchored-VWAP pullback (Brian Shannon): VWAP anchored at the lowest low of the last 252 bars (>= 20 bars ago);
     close > SMA50, the low comes within 1% of the AVWAP, closes green above it, prior close above it. Exit close <
     AVWAP. Stop 1.5 x ATR.
  P9 NR7 inside-bar breakout (Toby Crabel): the prior bar is an inside bar with the narrowest range of 7, close > SMA50 >
     SMA200, close above the NR7 bar's high. Exit close < EMA20. Stop 1 x ATR.
All: at most one BUY per stock per two weeks, liquidity floor, 0.1% per side + 0.1% entry slippage, fills next open.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

os.environ["CLASSIC_TF"] = os.environ.get("PRO_TF", "day")
from indicator_lab import ind
from indicator_lab.h4 import (
    classics as C,  # sets the data mode
)
from indicator_lab.swing4 import sim2 as S2

TF = C.TF


def rs_rank(fr: dict) -> pd.DataFrame:
    sc = {}
    for t, df in fr.items():
        c = df["close"]
        sc[t] = 0.4 * ind.roc(c, 63) + 0.2 * (ind.roc(c, 126) + ind.roc(c, 189) + ind.roc(c, 252))
    return pd.concat(sc, axis=1).rank(axis=1, pct=True) * 100


def avwap_low(h, lo, c, v, n=252, min_age=20) -> np.ndarray:
    """VWAP anchored at the lowest low of the last n bars (only once that low is >= min_age bars old)."""
    tp = (h + lo + c) / 3
    cpv = np.r_[0, np.cumsum(np.nan_to_num(tp * v))]
    cv = np.r_[0, np.cumsum(np.nan_to_num(v))]
    out = np.full(len(c), np.nan)
    dq: list = []   # monotonic deque of indices with increasing lows
    head = 0
    for t in range(len(c)):
        while len(dq) > head and lo[dq[-1]] >= lo[t]:
            dq.pop()
        dq.append(t)
        if dq[head] <= t - n:
            head += 1
        a = dq[head]
        if t - a >= min_age and cv[t + 1] > cv[a]:
            out[t] = (cpv[t + 1] - cpv[a]) / (cv[t + 1] - cv[a])
    return out


def signals(df: pd.DataFrame, rs: np.ndarray) -> dict:
    """name -> (entry, exit, stop in ATR, stop in %)"""
    cs, hs, ls, vs = df["close"], df["high"], df["low"], df["volume"]
    o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    sma = {n: ind.sma(cs, n).to_numpy() for n in (10, 50, 150, 200)}
    ema = {n: ind.ema(cs, n).to_numpy() for n in (10, 20)}
    va50 = vs.rolling(50).mean().to_numpy()
    p = lambda x: np.r_[False if x.dtype == bool else np.nan, x[:-1]]   # previous bar
    hi = lambda n: hs.rolling(n).max().shift(1).to_numpy()   # prior n-bar high
    green = c > o
    with np.errstate(invalid="ignore", divide="ignore"):
        # P1 Minervini
        s200 = sma[200]
        tt = ((c > sma[50]) & (sma[50] > sma[150]) & (sma[150] > s200) & (s200 > np.r_[np.full(21, np.nan), s200[:-21]])
              & (c >= 1.3 * ls.rolling(252).min().to_numpy()) & (c >= 0.75 * hs.rolling(252).max().to_numpy()) & (rs >= 80))
        r10 = (hs.rolling(10).max() - ls.rolling(10).min()).to_numpy() / c
        r40 = (hs.rolling(40).max() - ls.rolling(40).min()).to_numpy() / c
        vcp = (r10 <= 0.10) & (r10 < 0.5 * r40) & (vs.rolling(10).mean().to_numpy() < va50)
        p1 = p(tt) & p(vcp) & (c > hi(10)) & (v >= 1.4 * va50)
        # P2 Qullamaggie breakout
        adr = ((hs / ls - 1).rolling(20).mean()).to_numpy()
        move = c / cs.rolling(63).min().to_numpy() - 1
        p2 = (p(move) >= 0.30) & (adr >= 0.04) & (ema[10] > ema[20]) & (c > ema[20]) & (p(r10) <= 0.15) \
            & (c > hi(10)) & (v >= 1.5 * va50)
        # P3 episodic pivot
        p3 = (o >= 1.10 * p(c)) & (v >= 3 * p(va50)) & green & (c >= (h + lo) / 2)
        # P4 Holy Grail
        pdi, mdi, adx = (x.to_numpy() for x in ind.adx(df, 14))
        p4 = p((adx > 30) & (pdi > mdi) & (lo <= ema[20]) & (c > ema[20] * 0.98)) & (c > p(h))
        # P5 Turtle Soup
        lo20 = ls.rolling(20).min().shift(1).to_numpy()
        age = ls.rolling(20).apply(np.argmin, raw=True).shift(1).to_numpy()   # 0 = oldest bar of the window
        p5 = (lo < lo20) & (c > lo20) & (age <= 16)
        # P6 Weinstein stage 2
        s150 = sma[150]
        p6 = (s150 > np.r_[np.full(20, np.nan), s150[:-20]]) & (c > s150) & (c > hi(50)) & (v >= 2 * va50) & (rs >= 50)
        # P7 pocket pivot
        downv = pd.Series(np.where(c < p(c), v, 0.0), index=df.index).rolling(10).max().shift(1).to_numpy()
        s50 = sma[50]
        p7 = green & (c > p(c)) & (v > downv) & (c > s50) & (s50 > np.r_[np.full(10, np.nan), s50[:-10]]) \
            & (c <= 1.05 * sma[10])
        # P8 anchored VWAP pullback
        aw = avwap_low(h, lo, c, v)
        p8 = (c > s50) & (lo <= aw * 1.01) & (c > aw) & green & (p(c) > p(aw))
        # P9 NR7 inside bar
        rng = h - lo
        nr7 = (rng <= pd.Series(rng).rolling(7).min().to_numpy()) & (h <= p(h)) & (lo >= p(lo))
        p9 = p(nr7) & (c > s50) & (s50 > s200) & (c > p(h))
        x5 = c > hi(5)
    nz = lambda x: np.nan_to_num(np.asarray(x, dtype=float)).astype(bool)
    return {"P1 Minervini trend template + VCP-breakout": (nz(p1), nz(c < s50), 1e6, 0.08),
            "P2 Qullamaggie momentum-breakout": (nz(p2), nz(c < ema[10]), 1.0, None),
            "P3 Qullamaggie episodic pivot (gap >= 10%, 3x volume)": (nz(p3), nz(c < ema[10]), 1.0, None),
            "P4 Raschke Holy Grail (ADX > 30, pullback EMA20)": (nz(p4), nz(c < ema[20]), 1.5, None),
            "P5 Raschke Turtle Soup (valse 20-bar-low-break)": (nz(p5), nz(x5), 1.0, None),
            "P6 Weinstein stage-2-breakout (30-weeks lijn)": (nz(p6), nz(c < s150), 3.0, None),
            "P7 Pocket pivot (Morales & Kacher)": (nz(p7), nz(c < s50), 1e6, 0.08),
            "P8 Anchored-VWAP-pullback (Shannon)": (nz(p8), nz(c < np.nan_to_num(aw, nan=-1)), 1.5, None),
            "P9 NR7-insidebar-breakout (Crabel)": (nz(p9), nz(c < ema[20]), 1.0, None)}


def market_up(idx: pd.DatetimeIndex) -> np.ndarray:
    from indicator_lab.evaluate import get
    spy = get("SPY")["close"]
    up = (spy > ind.sma(spy, 200)).shift(1)
    return up.reindex(idx.normalize(), method="ffill").fillna(False).to_numpy(bool)


def run_all(fr: dict, start, end) -> dict:
    res: dict = {}
    min_dvol = 5e6 if TF == "day" else 2.5e6
    rs = rs_rank(fr)
    for t, df in fr.items():
        liquid = ((df["close"] >= 5) & ((df["close"] * df["volume"]).rolling(50).mean() >= min_dvol)).to_numpy()
        inwin = (df.index >= start) & (df.index <= end)
        mup = market_up(df.index)
        a = ind.atr(df, 14).to_numpy()
        for name, (e, x, stop, spct) in signals(df, rs[t].reindex(df.index).to_numpy()).items():
            pol = S2.Policy(trail=1e6, stop=stop, stop_pct=spct, min_gap_days=14)
            arr = S2.arrays(df, a, x)
            for tag, filt in (("", np.ones(len(df), bool)), (" + markt-uptrend", mup)):
                r, tr = S2.simulate(arr, e & liquid & inwin & filt, pol, slip=C.SLIP)
                for z in tr:
                    z["ticker"] = t
                rs_ = pd.Series(r, index=df.index)
                res.setdefault(name + tag, {})[t] = (rs_[(rs_.index >= start) & (rs_.index <= end)], tr)
    return res


def main():
    from indicator_lab.evaluate import get
    from indicator_lab.metrics import equity_stats
    fr = C.frames()
    if TF == "day":
        start, end = C.PERIOD_DAY
    else:
        idx = pd.DatetimeIndex(sorted({d for df in fr.values() for d in df.index}))
        start, end = idx[300], idx[-1]
    print(f"{TF}: {len(fr)} stocks {start.date()} .. {end.date()}", flush=True)
    res = run_all(fr, start, end)
    rows = [C.summary(name, r) for name, r in res.items()]
    spy = get("SPY")["close"]
    up = (spy > ind.sma(spy, 200)).shift(1, fill_value=False)
    ret = spy.pct_change()
    win = (ret.index >= start.normalize()) & (ret.index <= end)
    for label, r in (("SPY kopen en vasthouden", ret[win].fillna(0)),
                     ("SPY alleen boven SMA200 (anders cash 0%)", (ret * up)[win].fillna(0))):
        s = equity_stats(r)
        rows.append({"strategie": label, "CAGR (10 pos.)": f"{s['cagr'] * 100:.1f}%",
                     "max DD": f"{s['maxdd'] * 100:.1f}%", "Sharpe": f"{s['sharpe']:.2f}"})
    txt = (f"# Pro-swingmethodes, {'dagbars' if TF == 'day' else '4H-bars'}, {len(fr)} NASDAQ-aandelen, {start.date()} .. "
           f"{end.date()}\n\nMax 1 BUY per aandeel per 2 weken, liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, "
           "rekening max 10 posities van 10%, lege kas 0%. 'markt-uptrend' = alleen kopen als SPY gisteren boven SMA200 "
           "sloot.\n\n" + pd.DataFrame(rows).fillna("–").to_markdown(index=False) + "\n")
    os.makedirs(C.OUT, exist_ok=True)
    with open(os.path.join(C.OUT, f"pro_concepts_{TF}.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
