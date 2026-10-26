"""One-week swing study: build every candidate trade of the 10 strategies once, with the SAME exits for all.

    python -m indicator_lab.week.build          # writes the candidate trades to $WEEK_CACHE (default: /tmp)

Universe (point in time, on the signal day): ADR(20) > 4%, close > $5, 50-day average dollar volume > $20M.
Data: Swing 20/21 daily cache, every ticker (development + its sealed holdout, which is hereby used), 2014 .. 2026-10-23
(signals from 2015-01-01). Survivorship: only stocks still listed in 2026 (flatters every long rule).
Every signal is decided on its close; entry the next day (at the open, or with a buy-stop for strategy 3).

Standard exits (exits.py-style, identical for every strategy):
  stop    = max(fill x 0.92, min(anchor - 0.25 x ATR, fill - 1 x ATR)): below the strategy's support level, at least
            1 ATR, at most 8% risk (anchor = the support / zone / pattern low the entry is tied to)
  T1      = +10%: sell 50%, stop to break-even from the next bar
  T2      = the next strong resistance (S/R strength >= 2) clipped to +10% .. +20%; else +20%: sell the rest
  time    = sell the rest at the close of the 10th trading day (entry day = day 1)
  same bar: the stop is checked before the targets; gaps fill at the open; costs 0.1% + 0.1% slippage per side.
Filters are NOT applied here; every candidate carries its filter flags (run.py applies them as toggles and then
enforces one open position per stock, which equals a sequential simulation because outcomes are independent).
"""
from __future__ import annotations

import os
import pickle

import numpy as np
import pandas as pd

from indicator_lab import sr
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20

CACHE = os.environ.get("WEEK_CACHE", "/tmp")
OUT = os.path.join(CACHE, "week_candidates.pkl")
START, END = pd.Timestamp("2015-01-01"), pd.Timestamp("2026-10-23")
SPLIT = pd.Timestamp("2023-04-06")          # 70% of 2015-01-01 .. 2026-10-23
COST = 0.002                                # 0.1% commission + 0.1% slippage per side
HOLD = 10

NAMES = {1: "VCP (Minervini)", 2: "Qullamaggie breakout", 3: "Episodic pivot", 4: "S/R flip retest",
         5: "Failed breakdown / spring", 6: "Pullback in sterke trend", 7: "Squeeze breakout (TTM)",
         8: "Inside bar / NR7 aan S/R", 9: "Anchored VWAP reclaim", 10: "RS leader breakout"}


def ema(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).ewm(span=n, adjust=False, min_periods=n).mean().to_numpy()


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


def rmax(x, n):
    return pd.Series(x).rolling(n, min_periods=n).max().to_numpy()


def rmin(x, n):
    return pd.Series(x).rolling(n, min_periods=n).min().to_numpy()


def prev(x, k=1):
    return np.r_[np.full(k, np.nan), x[:-k]]


def rsi(c, n=2):
    d = np.diff(c, prepend=np.nan)
    up = pd.Series(np.where(d > 0, d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    dn = pd.Series(np.where(d < 0, -d, 0.0)).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        return 100 - 100 / (1 + up / dn)


def universe_mask(df: pd.DataFrame) -> np.ndarray:
    h, lo, c, v = (df[k].to_numpy(float) for k in ("high", "low", "close", "volume"))
    adr = sma(h / lo - 1, 20) * 100
    dv = sma(c * v, 50)
    with np.errstate(invalid="ignore"):
        return (adr > 4) & (c > 5) & (dv > 20e6)


def rs_score(c: np.ndarray) -> np.ndarray:
    r = lambda n: c / prev(c, n) - 1
    return 0.4 * r(63) + 0.2 * (r(126) + r(189) + r(252))


# ----------------------------------------------------------------------------------------------- strategies
def signals(df: pd.DataFrame, lv: pd.DataFrame, spy_c: np.ndarray) -> dict:
    """{strategy id: list of (signal bar s, entry type, entry level, anchor)}; all decided on the close of s."""
    o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    n = len(c)
    a = lv["atr"].to_numpy()
    va50 = prev(sma(v, 50))                         # average volume BEFORE the signal bar
    vol15 = v >= 1.5 * va50
    e10, e20, e50, e200 = ema(c, 10), ema(c, 20), ema(c, 50), ema(c, 200)
    s50, s200 = sma(c, 50), sma(c, 200)
    sup, sup_lo, sup_str = lv["sup"].to_numpy(), lv["sup_lo"].to_numpy(), lv["sup_str"].to_numpy()
    dsa = lv["dist_sup_atr"].to_numpy()
    flip = lv["flip"].to_numpy()
    out = {k: [] for k in NAMES}
    with np.errstate(invalid="ignore", divide="ignore"):
        # 1 VCP: >= 2 successively smaller contractions (pivot high -> next pivot low, pivots of 3 bars, last 60
        #   bars), the last <= 12%, volume drying up (10-day < 50-day), close > SMA50 > SMA200; BUY on a close above
        #   the last contraction's high on >= 1.5 x volume.
        ph, pl = sr.pivots(h, lo, 3)
        dry = sma(v, 10) < sma(v, 50)
        trend = (c > s50) & (s50 > s200)
        for s in np.where(vol15 & trend & (c > prev(rmax(h, 5))))[0]:
            if s < 70:
                continue
            his = [i for i in range(s - 60, s - 2) if ph[i]]
            depths, last_hi, last_lo = [], np.nan, np.nan
            for j, i in enumerate(his):
                nxt = his[j + 1] if j + 1 < len(his) else s - 2
                lows = [k for k in range(i + 1, min(nxt, s - 2)) if pl[k]]
                if lows:
                    lmin = min(lo[k] for k in lows)
                    depths.append(1 - lmin / h[i])
                    last_hi, last_lo = h[i], lmin
            if len(depths) < 2:
                continue
            d = depths[-4:]
            k2 = 1
            while k2 < len(d) and d[-k2 - 1] > d[-k2]:
                k2 += 1
            if k2 >= 2 and d[-1] <= 0.12 and dry[s - 1] and c[s] > last_hi >= c[s - 1]:
                out[1].append((s, "open", np.nan, last_lo))
        # 2 Qullamaggie: +30% run-up (max close of the last 63 bars / min close of bars s-126 .. s-21), a tight
        #   10-bar flag (range <= 15%) riding the 20 EMA (>= 8 of 10 closes above it); BUY on a close above the flag
        #   high on >= 1.5 x volume.
        runup = rmax(c, 63) / prev(rmin(c, 106), 20)
        flag_hi, flag_lo = prev(rmax(h, 10)), prev(rmin(lo, 10))
        tight = (flag_hi - flag_lo) / c <= 0.15
        ride = prev(pd.Series((c > e20).astype(float)).rolling(10).sum().to_numpy()) >= 8
        for s in np.where((runup >= 1.30) & tight & ride & (c > flag_hi) & vol15)[0]:
            out[2].append((s, "open", np.nan, flag_lo[s]))
        # 3 Episodic pivot: open >= 10% above the prior close on >= 3 x volume, closes at or above its open;
        #   entry the next day with a buy-stop at the gap day's high (proxy for the opening-range high).
        for s in np.where((o >= 1.10 * prev(c)) & (v >= 3 * va50) & (c >= o))[0]:
            out[3].append((s, "stop", h[s], lo[s]))
        # 4 S/R flip retest: the nearest support is a flipped zone (old resistance), the low tags it (<= +0.25 ATR),
        #   bullish candle (green, close in the top 40% of the range) closing above it.
        rng = np.where(h > lo, h - lo, np.nan)
        bull = (c > o) & ((c - lo) / rng >= 0.6)
        for s in np.where(flip & (lo <= sup + 0.25 * a) & (c > sup) & bull)[0]:
            out[4].append((s, "open", np.nan, sup_lo[s]))
        # 5 Failed breakdown / spring: a close below a strong support zone (strength >= 2, known the bar before),
        #   then within 1-3 bars the first close back above the zone's middle.
        for s in range(3, n):
            for k in range(s - 3, s):
                if k < 1 or not (sup_str[k - 1] >= 2) or not (c[k] < sup_lo[k - 1]):
                    continue
                zmid = sup[k - 1]
                if c[s] > zmid and all(c[q] <= zmid for q in range(k, s)):
                    out[5].append((s, "open", np.nan, np.nanmin(lo[k:s + 1])))
                    break
        # 6 Pullback in a strong trend: close > EMA50 > EMA200, RSI(2) < 10, the low tags the 10/20 EMA (the 10 EMA
        #   lies above the 20 EMA in an uptrend, so tagging it covers both) or a support zone (within 0.5 ATR).
        r2 = rsi(c, 2)
        tag = (lo <= e10) | (dsa <= 0.5)
        for s in np.where((c > e50) & (e50 > e200) & (r2 < 10) & tag)[0]:
            anc = sup_lo[s] if dsa[s] <= 1.0 else lo[s]
            out[6].append((s, "open", np.nan, anc))
        # 7 TTM squeeze: Bollinger(20, 2) inside Keltner(20 EMA +- 1.5 x ATR) for >= 5 bars, released today, with
        #   upward momentum (close > prior close and > SMA20) above the 50 EMA.
        sd = pd.Series(c).rolling(20).std(ddof=0).to_numpy()
        m20 = sma(c, 20)
        sq = (m20 + 2 * sd < e20 + 1.5 * a) & (m20 - 2 * sd > e20 - 1.5 * a)
        sq5 = pd.Series(sq.astype(float)).rolling(5).sum().to_numpy() == 5
        for s in np.where(prev(sq5).astype(bool) & ~sq & (c > prev(c)) & (c > m20) & (c > e50))[0]:
            out[7].append((s, "open", np.nan, np.nanmin(lo[s - 5:s + 1])))
        # 8 Inside bar + NR7 at support: bar s-1 is an inside bar with the narrowest range of 7 and lies within
        #   0.75 ATR of a support; BUY on a close above its high.
        ins = (h <= prev(h)) & (lo >= prev(lo))
        nr7 = (h - lo) <= rmin(h - lo, 7)
        cond = prev(ins & nr7).astype(bool) & (prev(dsa) <= 0.75) & (c > prev(h))
        for s in np.where(cond)[0]:
            out[8].append((s, "open", np.nan, lo[s - 1]))
        # 9 Anchored VWAP reclaim: VWAP anchored at the lowest low of bars s-60 .. s-5; BUY on the first green close
        #   back above it.
        tp = (h + lo + c) / 3
        cpv, cv = np.r_[0, np.cumsum(np.nan_to_num(tp * v))], np.r_[0, np.cumsum(np.nan_to_num(v))]
        for s in range(65, n):
            i0 = s - 60 + int(np.nanargmin(lo[s - 60:s - 4]))
            if cv[s + 1] - cv[i0] <= 0 or cv[s] - cv[i0] <= 0:
                continue
            aw = (cpv[s + 1] - cpv[i0]) / (cv[s + 1] - cv[i0])
            aw1 = (cpv[s] - cpv[i0]) / (cv[s] - cv[i0])
            if c[s] > aw and c[s - 1] <= aw1 and c[s] > o[s]:
                out[9].append((s, "open", np.nan, np.nanmin(lo[s - 2:s + 1])))
        # 10 RS leader: the RS line (close / SPY) made a 126-bar high while the price was still >= 3% below its own
        #   126-bar high, in the last 10 bars; BUY on a 20-bar breakout on >= 1.5 x volume.
        rsl = c / spy_c
        rs_nh = (rsl >= prev(rmax(rsl, 126))) & (c < 0.97 * prev(rmax(h, 126)))
        recent = pd.Series(prev(rs_nh).astype(float)).rolling(10).max().to_numpy() == 1
        for s in np.where(recent & (c > prev(rmax(h, 20))) & vol15)[0]:
            out[10].append((s, "open", np.nan, prev(rmin(lo, 20))[s]))
    return out


# ----------------------------------------------------------------------------------------------- exits
def trade(o, h, lo, c, s, etype, elevel, anchor, atr_s, res_strong_s):
    n = len(c)
    d = s + 1
    if d >= n:
        return None
    if etype == "stop":
        if not h[d] >= elevel:
            return None
        fill = max(o[d], elevel)
    else:
        fill = o[d]
    if not (fill > 0 and atr_s > 0):
        return None
    base = anchor - 0.25 * atr_s if np.isfinite(anchor) and anchor < fill else fill - 1.5 * atr_s
    stop = max(fill * 0.92, min(base, fill - 1.0 * atr_s))
    t1 = fill * 1.10
    t2 = min(max(res_strong_s, fill * 1.10), fill * 1.20) if np.isfinite(res_strong_s) and res_strong_s > fill else fill * 1.20
    buy = fill * (1 + COST)
    left, cash, half = 1.0, 0.0, False
    vals, hit10, hit20, mfe = [], False, False, 0.0
    exit_k, reason = None, None
    for k in range(HOLD):
        day = d + k
        if day >= n:
            exit_k, reason = k - 1, "einde data"
            break
        op = fill if k == 0 else o[day]
        if lo[day] <= stop:                                  # stop first (conservative)
            px = stop if k == 0 else min(op, stop)
            cash += left * px * (1 - COST)
            left = 0.0
            reason = "breakeven" if half else "stop"
        else:
            mfe = max(mfe, h[day] / fill - 1)
            if h[day] >= fill * 1.10:
                hit10 = True
            if h[day] >= fill * 1.20:
                hit20 = True
            if not half and h[day] >= t1:
                px = t1 if k == 0 else max(op, t1)
                cash += 0.5 * px * (1 - COST)
                left, half = 0.5, True
                newstop = fill
            else:
                newstop = None
            if half and h[day] >= t2:
                px = t2 if k == 0 else max(op, t2)
                cash += left * px * (1 - COST)
                left = 0.0
                reason = "target"
            if left > 0 and k == HOLD - 1:
                cash += left * c[day] * (1 - COST)
                left = 0.0
                reason = "tijdstop"
            if newstop is not None:
                stop = max(stop, newstop)
        vals.append((cash + left * c[day]) / buy)
        if left == 0.0:
            exit_k = k
            break
    if exit_k is None or exit_k < 0:
        return None
    path = np.diff(np.r_[1.0, vals])
    rets = path / np.r_[1.0, vals[:-1]]
    return {"entry_i": d, "exit_i": d + exit_k, "ret": vals[-1] - 1, "hold": exit_k + 1, "reason": reason,
            "hit10": hit10, "hit20": hit20, "half": half, "mfe": mfe, "daily": rets, "risk": 1 - stop / fill}


def main():
    data20.final_mode()
    spy = R.load("SPY")
    tickers = sorted(set(data20.DEV) | data20.H_TICKERS)
    frames, elig, score = {}, {}, {}
    for t in tickers:
        try:
            df = data20.load(t)
        except PermissionError:
            continue
        if df is None or len(df) < 300:
            continue
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= END)]
        m = universe_mask(df)
        win = (df.index >= START).to_numpy()
        if (m & win).sum() < 20:
            continue
        frames[t] = df
        elig[t] = pd.Series(m, index=df.index)
        score[t] = pd.Series(rs_score(df["close"].to_numpy(float)), index=df.index)
    E = pd.concat(elig, axis=1).fillna(False)
    S = pd.concat(score, axis=1).where(E)
    thr80 = S.quantile(0.8, axis=1)
    spy_c = spy["close"]
    up = (spy_c > spy_c.rolling(50).mean()) & (spy_c.ewm(span=20, adjust=False).mean() > spy_c.ewm(span=50, adjust=False).mean())
    print(f"{len(frames)} tickers ever in the universe; median eligible per day "
          f"{int(E.loc[E.index >= START].sum(axis=1).median())}", flush=True)
    cands = []
    for j, (t, df) in enumerate(frames.items()):
        lv = sr.levels(df)
        sc = spy_c.reindex(df.index).ffill().to_numpy()
        sig = signals(df, lv, sc)
        o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
        va50 = prev(sma(v, 50))
        m = elig[t].to_numpy()
        a = lv["atr"].to_numpy()
        rs_ok = (score[t] >= thr80.reindex(df.index)).to_numpy()
        reg = up.reindex(df.index).ffill().fillna(False).to_numpy()
        room = lv["room_pct"].to_numpy()
        rstrong = lv["res_strong"].to_numpy()
        for sid, lst in sig.items():
            for s, etype, elevel, anchor in lst:
                day = df.index[s]
                if not (START <= day <= END) or not m[s]:
                    continue
                tr = trade(o, h, lo, c, s, etype, elevel, anchor, a[s], rstrong[s])
                if tr is None:
                    continue
                tr.update({"strategy": sid, "ticker": t, "signal": day, "entry": df.index[tr["entry_i"]],
                           "exit": df.index[tr["exit_i"]], "dates": df.index[tr["entry_i"]:tr["exit_i"] + 1],
                           "regime": bool(reg[s]), "rs_top20": bool(rs_ok[s]), "vol_surge": bool(v[s] >= 1.5 * va50[s]),
                           "room10": bool(room[s] >= 10) if np.isfinite(room[s]) else True,
                           "split": "train" if day <= SPLIT else "test"})
                cands.append(tr)
        if j % 200 == 0:
            print(f"{j}/{len(frames)} tickers, {len(cands)} candidates", flush=True)
    with open(OUT, "wb") as fh:
        pickle.dump({"cands": cands, "spy": spy_c[(spy_c.index >= START) & (spy_c.index <= END)]}, fh)
    print(f"saved {len(cands)} candidate trades to {OUT}")


if __name__ == "__main__":
    main()
