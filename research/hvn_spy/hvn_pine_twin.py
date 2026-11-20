"""Python twin of pine/hvn_absorption.pine (default inputs), bar-for-bar.

Mirrors the Pine execution order per 5m chart bar:
  1. intrabar buy/sell split (1m candle colour, or CLV fallback without intrabar data)
  2. ATR(14) (RMA), rvol = volume / SMA(volume, 20)[1]
  3. new period -> profile of the completed period, nodes created, old periods pruned
  4. node loop: level absorption (lvlDir), active/armed state, retest events
  5. confirmation entries (pending signal from the previous bar)
Every Pine line that matters is referenced as "Pine: <construct>".

Known unverifiable point: Pine's array.percentile_linear_interpolation formula could not be
read from the official reference (JS-rendered). numpy's 'linear' percentile is used; HVN
selection can differ only for peaks exactly at the cutoff.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

ROWS, SIGMA, THR_PCT, ZONE_RATIO, MIN_SEP, MAX_NODES, MAX_PERIODS = 120, 2.0, 60.0, 80.0, 5, 8, 5
# LVL_RVOL / LVL_WICK = Pine 'Signal frequency' preset; default 'Normal' since 2026-11-18 (was Strict 2.0 / 50)
RVOL_LEN, ATR_LEN, LVL_RVOL, HEAVY_RVOL, LVL_WICK, MIN_DELTA = 20, 14, 1.5, 2.5, 40.0, 10.0
MIN_RR, STOP_BUF_PCT = 1.5, 0.014


@dataclass
class Node:
    lo: float            # thin band (peak row)  - Pine: zLo/zHi with thinBands = true
    hi: float
    price: float
    full_lo: float       # full HVN zone (zoneRatio) - used by stop variant S3
    full_hi: float
    is_poc: bool
    period: int
    vol: float
    buy_pct: float
    active: bool = True
    armed: bool = False


def build_profile(h, l, v, bshare, n_rows=ROWS, sig=SIGMA):
    """Pine: buildProfile(off, n, nRows, sig)."""
    p_hi, p_lo = float(np.max(h)), float(np.min(l))
    step = (p_hi - p_lo) / n_rows
    raw = np.zeros(n_rows); rbuy = np.zeros(n_rows)
    if step > 0:
        for hh, ll, vv, bs in zip(h, l, v, bshare):
            vv = 0.0 if np.isnan(vv) else vv
            r = hh - ll
            if r <= 0:
                k = max(0, min(n_rows - 1, int((hh - p_lo) / step)))
                raw[k] += vv; rbuy[k] += vv * bs
            else:
                k0 = max(0, min(n_rows - 1, int((ll - p_lo) / step)))
                k1 = max(k0, min(n_rows - 1, int((hh - p_lo) / step)))
                for k in range(k0, k1 + 1):
                    b_lo = p_lo + k * step
                    ov = min(hh, b_lo + step) - max(ll, b_lo)
                    if ov > 0:
                        raw[k] += vv * ov / r; rbuy[k] += vv * bs * ov / r
    sm = np.zeros(n_rows)
    rad = max(1, int(round(3 * sig))) if sig > 0 else 0
    if rad == 0:
        sm = raw.copy()
    else:
        j = np.arange(-rad, rad + 1); w = np.exp(-0.5 * (j / sig) ** 2); wsum = w.sum()
        for k in range(n_rows):
            acc = 0.0
            for jj, ww in zip(j, w):
                kk = k + jj
                if 0 <= kk < n_rows:
                    acc += ww * raw[kk]
            sm[k] = acc / wsum
    return p_lo, step, sm, raw, rbuy


def nodes_of(sm, max_n=MAX_NODES):
    """Pine: nodesOf(sm, maxN). Returns [(peak, lo_row, hi_row)] in selection order."""
    n = len(sm)
    cutoff = float(np.percentile(sm, THR_PCT))  # Pine: percentile_linear_interpolation (formula unverified)
    poc_v = float(np.max(sm))
    peaks = []
    if poc_v > 0:
        for k in range(n):
            v = sm[k]; left = sm[k - 1] if k > 0 else -1.0; right = sm[k + 1] if k < n - 1 else -1.0
            if v >= left and v > right and v >= cutoff:
                peaks.append(k)
    chosen = []
    while peaks and len(chosen) < max_n:
        best = 0
        for p in range(len(peaks)):
            if sm[peaks[p]] > sm[peaks[best]]:
                best = p
        k = peaks.pop(best)
        if all(abs(k - c) >= MIN_SEP for c, _, _ in chosen):
            pk = sm[k]; lo = hi = k
            while lo > 0 and sm[lo - 1] >= pk * ZONE_RATIO / 100 and sm[lo - 1] <= sm[lo]:
                lo -= 1
            while hi < n - 1 and sm[hi + 1] >= pk * ZONE_RATIO / 100 and sm[hi + 1] <= sm[hi]:
                hi += 1
            chosen.append((k, lo, hi))
    return chosen


def rma(x, n):
    out = np.full(len(x), np.nan); s = np.nan
    for i, v in enumerate(x):
        if i < n - 1:
            continue
        s = np.nanmean(x[i - n + 1:i + 1]) if np.isnan(s) else (s * (n - 1) + v) / n
        out[i] = s
    return out


def run_twin(b5: pd.DataFrame, buy: np.ndarray, sell: np.ndarray, has_delta: np.ndarray, session_key: np.ndarray,
             max_per_day: int = 2, day_key: np.ndarray | None = None, confirm: bool = False):
    """b5: 5m OHLCV (chart bars, chronological). buy/sell: per-bar buy/sell volume (intrabar or CLV).
    session_key: period id per bar (Pine timeframe.change("D")).
    Returns dict with per-bar arrays and event lists."""
    o, h, l, c, v = (b5[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    n = len(b5)
    tot = buy + sell
    bshare = np.where(tot > 0, buy / np.where(tot > 0, tot, 1), 0.5)            # Pine: bShareBar
    dratio = np.where(has_delta & (tot > 0), (buy - sell) / np.where(tot > 0, tot, 1) * 100, 0.0)  # Pine: dRatioL
    prev_c = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - prev_c), np.abs(l - prev_c)]), axis=0); tr[0] = h[0] - l[0]
    atr = rma(tr, ATR_LEN)                                                      # Pine: ta.atr(14)
    sma = pd.Series(v).rolling(RVOL_LEN).mean().shift(1).to_numpy()            # Pine: ta.sma(volume,20)[1]
    rvol = np.where(sma > 0, v / np.where(sma > 0, sma, 1), np.nan)

    nodes: list[Node] = []
    p_start, p_id = 0, 0
    day_nodes = {}          # snapshot of kept nodes per bar-day (constant within a period)
    signals, entries, retests = [], [], []
    pend = None             # (dir, bar, close, ext, node)
    day_key = session_key if day_key is None else day_key
    ent_today = {}          # Pine: entToday, reset on timeframe.change("D")
    rng = h - l
    up_w = np.where(rng > 0, (h - np.maximum(o, c)) / np.where(rng > 0, rng, 1) * 100, 0.0)
    dn_w = np.where(rng > 0, (np.minimum(o, c) - l) / np.where(rng > 0, rng, 1) * 100, 0.0)
    for t in range(n):
        new_period = t > 0 and session_key[t] != session_key[t - 1]          # Pine: timeframe.change("D")
        if new_period and t > p_start:
            cnt = min(t - p_start, 4999)
            sl_ = slice(t - cnt, t)
            p_lo, step, sm, raw, rbuy = build_profile(h[sl_], l[sl_], v[sl_], bshare[sl_])
            p_id += 1
            if step > 0:
                poc_v = sm.max()
                for k, lo, hi in nodes_of(sm):
                    zv = raw[lo:hi + 1].sum(); zb = rbuy[lo:hi + 1].sum()
                    bp = zb / zv * 100 if zv > 0 else 50.0
                    nodes.append(Node(lo=p_lo + k * step, hi=p_lo + (k + 1) * step, price=p_lo + (k + 0.5) * step,
                                      full_lo=p_lo + lo * step, full_hi=p_lo + (hi + 1) * step,
                                      is_poc=bool(sm[k] == poc_v), period=p_id, vol=zv, buy_pct=bp))
            nodes = [nd for nd in nodes if nd.period > p_id - MAX_PERIODS]
            p_start = t
        elif new_period:
            p_start = t
        day_nodes[session_key[t]] = list(nodes)

        lvl_dir, lvl_node = 0, None
        heavy_vol = rvol[t] >= LVL_RVOL if not np.isnan(rvol[t]) else False
        for nd in nodes:
            inside = l[t] <= nd.hi and h[t] >= nd.lo
            live = nd.active or nd.period == p_id
            if live and heavy_vol:
                if o[t] < nd.lo and h[t] >= nd.lo and c[t] < nd.lo and up_w[t] >= LVL_WICK and (not has_delta[t] or dratio[t] >= MIN_DELTA):
                    lvl_dir, lvl_node = -1, nd
                if o[t] > nd.hi and l[t] <= nd.hi and c[t] > nd.hi and dn_w[t] >= LVL_WICK and (not has_delta[t] or dratio[t] <= -MIN_DELTA):
                    lvl_dir, lvl_node = 1, nd
            if nd.active:
                if inside and nd.armed:
                    nd.active = False
                    retests.append(dict(bar=t, node=nd, side=-1 if (t > 0 and c[t - 1] < nd.lo) else 1))
                elif not inside:
                    nd.armed = True
        if lvl_dir != 0:
            signals.append(dict(bar=t, dir=lvl_dir, node=lvl_node, heavy=bool(rvol[t] >= HEAVY_RVOL), rvol=float(rvol[t]),
                                dratio=float(dratio[t]), wick=float(up_w[t] if lvl_dir == -1 else dn_w[t])))
        # Pine: entries block (after the absorption block). Without confirmation the absorption bar
        # itself is the entry bar.
        if not confirm and lvl_dir != 0:
            pend = (lvl_dir, t, c[t], l[t] if lvl_dir == 1 else h[t], lvl_node)
        if pend is not None and t == pend[1] + (1 if confirm else 0):
            d, _, pc, ext, nd0 = pend
            if (not confirm or (c[t] - pc) * d > 0) and (max_per_day == 0 or ent_today.get(day_key[t], 0) < max_per_day):
                ent_today[day_key[t]] = ent_today.get(day_key[t], 0) + 1
                ent = c[t]
                sl = ext - c[t] * STOP_BUF_PCT / 100 if d == 1 else ext + c[t] * STOP_BUF_PCT / 100
                risk = abs(ent - sl); best = None
                for nd in nodes:
                    dd = (nd.price - ent) * d
                    if dd >= MIN_RR * risk and (best is None or dd < (best - ent) * d):
                        best = nd.price
                tp = ent + 2 * risk * d if best is None else best
                entries.append(dict(bar=t, sig_bar=pend[1], dir=d, entry=ent, stop=sl, target=tp, ext=ext, node=nd0,
                                    target_is_hvn=best is not None, atr=float(atr[t])))
            pend = None
        if confirm and lvl_dir != 0:
            pend = (lvl_dir, t, c[t], l[t] if lvl_dir == 1 else h[t], lvl_node)
    return dict(atr=atr, rvol=rvol, dratio=dratio, signals=signals, entries=entries, retests=retests, day_nodes=day_nodes)
