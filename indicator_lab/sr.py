"""Support / resistance module (point in time: every value on bar t uses only bars <= t).

Levels, combined on every bar:
  1. Swing-pivot ZONES: pivot highs and lows (w bars each side, KNOWN only w bars later) of the last `age` bars,
     clustered when neighbours lie within `tol` x ATR. Zone = [lowest, highest] pivot of the cluster.
     Strength = touches x (1 + 0.25 x mean relative volume at the touches, capped at 2) x recency factor
     (1.0 if the last touch is < 60 bars old, 0.75 if < 120, else 0.5).
  2. Extra levels: previous calendar week's high and low (strength 1), the 52-week high (prior 252 bars, strength 2),
     round numbers (strength 0.5) and high-volume nodes of the last 120 bars' volume profile (30 bins; a bin with
     >= 1.5 x the mean bin volume, strength 1).
  3. Flip: the nearest support is a zone that contains a pivot HIGH (it was resistance) and some close of the last 20
     bars was below its middle: an old resistance that became support after a breakout.
Per bar output (dict of arrays): sup, sup_lo (bottom of the support zone, for stops), sup_str, res, res_str,
dist_sup_pct / dist_sup_atr, dist_res_pct / dist_res_atr, res_strong (nearest resistance with strength >= 2) and
room_pct (% distance to it = upside potential), flip (bool).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from numba import njit
except ImportError:          # the module also runs (slower) without numba
    def njit(*a, **k):
        return (lambda f: f) if not a or not callable(a[0]) else a[0]

STRONG = 2.0


def atr(h, lo, c, n=14) -> np.ndarray:
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - lo, np.abs(h - pc), np.abs(lo - pc)]), axis=0)
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()


def pivots(h, lo, w):
    """Pivot flags at the pivot bar (known at bar + w)."""
    n = len(h)
    ph = np.zeros(n, np.bool_)
    pl = np.zeros(n, np.bool_)
    hs = pd.Series(h).rolling(2 * w + 1, center=True).max().to_numpy()
    ls = pd.Series(lo).rolling(2 * w + 1, center=True).min().to_numpy()
    ph[w:n - w] = h[w:n - w] >= hs[w:n - w]
    pl[w:n - w] = lo[w:n - w] <= ls[w:n - w]
    return ph, pl


def round_step(p: float) -> float:
    return 1.0 if p < 10 else 5.0 if p < 50 else 10.0 if p < 200 else 50.0 if p < 1000 else 100.0


@njit(cache=True)
def _core(h, lo, c, v, a, ph, pl, relv, wk_hi, wk_lo, hi52, w, tol, age, vp_n, vp_bins):
    n = len(c)
    sup = np.full(n, np.nan)
    sup_lo = np.full(n, np.nan)
    sup_str = np.full(n, np.nan)
    res = np.full(n, np.nan)
    res_str = np.full(n, np.nan)
    res_strong = np.full(n, np.nan)
    flip = np.zeros(n, np.bool_)
    piv_px = np.empty(4 * age + 8)
    piv_bar = np.empty(4 * age + 8, np.int64)
    piv_hi = np.empty(4 * age + 8, np.bool_)
    piv_rv = np.empty(4 * age + 8)
    lv_px = np.empty(4 * age + 200)
    lv_lo = np.empty(4 * age + 200)
    lv_st = np.empty(4 * age + 200)
    lv_fl = np.empty(4 * age + 200, np.bool_)
    for t in range(n):
        if not np.isfinite(a[t]) or a[t] <= 0:
            continue
        # 1. confirmed pivots of the window
        m = 0
        for i in range(max(0, t - age), t - w + 1):
            if ph[i]:
                piv_px[m] = h[i]
                piv_bar[m] = i
                piv_hi[m] = True
                piv_rv[m] = relv[i]
                m += 1
            if pl[i]:
                piv_px[m] = lo[i]
                piv_bar[m] = i
                piv_hi[m] = False
                piv_rv[m] = relv[i]
                m += 1
        order = np.argsort(piv_px[:m])
        k = 0
        j = 0
        tl = tol * a[t]
        while j < m:
            s = j
            while j + 1 < m and piv_px[order[j + 1]] - piv_px[order[j]] <= tl:
                j += 1
            zlo = piv_px[order[s]]
            zhi = piv_px[order[j]]
            cnt = j - s + 1
            rv = 0.0
            last = -1
            has_hi = False
            for q in range(s, j + 1):
                o_ = order[q]
                rv += piv_rv[o_] if np.isfinite(piv_rv[o_]) else 1.0
                last = max(last, piv_bar[o_])
                if piv_hi[o_]:
                    has_hi = True
            agef = t - last
            rec = 1.0 if agef < 60 else (0.75 if agef < 120 else 0.5)
            st = cnt * (1.0 + 0.25 * min(rv / cnt, 2.0)) * rec
            mid = 0.5 * (zlo + zhi)
            fl = False
            if has_hi:
                for q in range(max(0, t - 20), t):
                    if c[q] < mid:
                        fl = True
                        break
            lv_px[k] = mid
            lv_lo[k] = zlo
            lv_st[k] = st
            lv_fl[k] = fl
            k += 1
            j += 1
        # 2. extra levels
        if np.isfinite(wk_hi[t]):
            lv_px[k] = wk_hi[t]; lv_lo[k] = wk_hi[t]; lv_st[k] = 1.0; lv_fl[k] = False; k += 1
            lv_px[k] = wk_lo[t]; lv_lo[k] = wk_lo[t]; lv_st[k] = 1.0; lv_fl[k] = False; k += 1
        if np.isfinite(hi52[t]):
            lv_px[k] = hi52[t]; lv_lo[k] = hi52[t]; lv_st[k] = 2.0; lv_fl[k] = False; k += 1
        p = c[t]
        stp = 1.0 if p < 10 else (5.0 if p < 50 else (10.0 if p < 200 else (50.0 if p < 1000 else 100.0)))
        base = np.floor(p / stp) * stp
        for r in range(-2, 4):
            lv_px[k] = base + r * stp; lv_lo[k] = base + r * stp; lv_st[k] = 0.5; lv_fl[k] = False; k += 1
        if t >= vp_n:
            pmin = np.min(lo[t - vp_n + 1:t + 1])
            pmax = np.max(h[t - vp_n + 1:t + 1])
            if pmax > pmin:
                hist = np.zeros(vp_bins)
                bw = (pmax - pmin) / vp_bins
                for i in range(t - vp_n + 1, t + 1):
                    tp = (h[i] + lo[i] + c[i]) / 3.0
                    b = int((tp - pmin) / bw)
                    if b >= vp_bins:
                        b = vp_bins - 1
                    hist[b] += v[i]
                mean = hist.mean()
                for b in range(vp_bins):
                    if hist[b] >= 1.5 * mean and k < len(lv_px):
                        px = pmin + (b + 0.5) * bw
                        lv_px[k] = px; lv_lo[k] = px; lv_st[k] = 1.0; lv_fl[k] = False; k += 1
        # 3. nearest support (<= close) and resistance (> close); strongest wins inside 0.25 ATR ties
        bs, br, bstrong = -1, -1, -1
        for q in range(k):
            if lv_px[q] <= p:
                if bs < 0 or lv_px[q] > lv_px[bs] + 0.25 * a[t] or (abs(lv_px[q] - lv_px[bs]) <= 0.25 * a[t] and lv_st[q] > lv_st[bs]):
                    bs = q
            else:
                if br < 0 or lv_px[q] < lv_px[br] - 0.25 * a[t] or (abs(lv_px[q] - lv_px[br]) <= 0.25 * a[t] and lv_st[q] > lv_st[br]):
                    br = q
                if lv_st[q] >= 2.0 and (bstrong < 0 or lv_px[q] < lv_px[bstrong]):
                    bstrong = q
        if bs >= 0:
            sup[t] = lv_px[bs]; sup_lo[t] = lv_lo[bs]; sup_str[t] = lv_st[bs]; flip[t] = lv_fl[bs]
        if br >= 0:
            res[t] = lv_px[br]; res_str[t] = lv_st[br]
        if bstrong >= 0:
            res_strong[t] = lv_px[bstrong]
    return sup, sup_lo, sup_str, res, res_str, res_strong, flip


def levels(df: pd.DataFrame, w: int = 5, tol: float = 0.5, age: int = 250, vp_n: int = 120, vp_bins: int = 30) -> pd.DataFrame:
    h, lo, c, v = (df[k].to_numpy(float) for k in ("high", "low", "close", "volume"))
    a = atr(h, lo, c)
    ph, pl = pivots(h, lo, w)
    relv = v / pd.Series(v).rolling(50, min_periods=20).mean().to_numpy()
    wk = df.index.to_period("W")
    g = pd.DataFrame({"h": h, "l": lo, "wk": wk}, index=df.index)
    whl = g.groupby("wk").agg(hh=("h", "max"), ll=("l", "min"))
    prev = whl.shift(1)                       # the previous COMPLETED calendar week
    wk_hi = prev["hh"].reindex(wk).to_numpy()
    wk_lo = prev["ll"].reindex(wk).to_numpy()
    hi52 = pd.Series(h).rolling(252, min_periods=200).max().shift(1).to_numpy()
    sup, sup_lo, sup_str, res, res_str, res_strong, flip = _core(
        h, lo, c, v, a, ph, pl, relv, wk_hi, wk_lo, hi52, w, tol, age, vp_n, vp_bins)
    out = pd.DataFrame({"atr": a, "sup": sup, "sup_lo": sup_lo, "sup_str": sup_str, "res": res, "res_str": res_str,
                        "res_strong": res_strong, "flip": flip}, index=df.index)
    out["dist_sup_pct"] = (c / sup - 1) * 100
    out["dist_sup_atr"] = (c - sup) / a
    out["dist_res_pct"] = (res / c - 1) * 100
    out["dist_res_atr"] = (res - c) / a
    out["room_pct"] = (res_strong / c - 1) * 100
    return out
