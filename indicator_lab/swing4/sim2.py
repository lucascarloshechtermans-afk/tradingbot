"""Trade simulation with configurable entries and exits (phase 2 of the swing v4 round).

With the default `Policy` it reproduces `core.simulate` (= the research engine) exactly (tests/test_swing4.py).
Fill rules, conservative by construction:
- events at the open come first: a pending exit fills at the open; an open at or through the stop fills at the open;
  an open at or above a profit target fills that target at the open (a gap never gives a better price than the open)
- then inside the bar the STOP is checked before any target: if both are touched on one bar, the stop wins
- targets are limit orders at their price; a target can not fill on the fill bar of a stop/limit entry (order unknown)
- decisions taken at the close (signal exit, time stop, over-extension, earnings) fill at the next open
- R = `stop` x ATR(signal bar): the distance from the fill to the protective stop
Position accounting per slot: value 1 at the entry (incl. cost); partial sales go to cash (earning 0) and the slot
stays occupied until the whole position is closed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

LEVELS = (0.5, 1.0, 1.5, 2.0, 3.0)


@dataclass(frozen=True)
class Policy:
    trail: float = 4.0               # chandelier: highest high since the fill - trail x ATR
    stop: float = 4.0                # protective stop below the fill in ATR(signal bar); defines R
    exit_low: bool = True            # close < prior m-day low -> exit at the next open
    # entry
    entry: str = "open"              # "open" | "stop" (buy-stop above the signal high) | "pullback" (limit order)
    e_buf: float = 0.0               # buy-stop trigger = signal high + e_buf x ATR
    e_days: int = 1                  # sessions a buy-stop / limit order stays valid
    pb: float = 0.5                  # pullback limit = signal close - pb x ATR  (pb_mode "atr")
    pb_mode: str = "atr"             # or "brk": limit = the breakout level (prior n-day high)
    # profit taking
    partial: tuple = ()              # ((R level, fraction of the original position), ...)
    target: float | None = None      # whole (remaining) position out at +target R
    tgt_pct: float | None = None     # or at +tgt_pct of the fill price (limit order; a gap above fills at the open)
    max_week: int | None = None      # at most this many BUY signals acted on per calendar week (ISO week)
    stop_pct: float | None = None    # protective stop at fill x (1 - stop_pct) instead of fill - stop x ATR (defines R)
    min_gap_days: int | None = None  # a BUY signal is only acted on if the previous one on this stock was >= this many
                                     #   calendar days earlier (e.g. 14 = at most one BUY per two weeks)
    be_at: float | None = None       # stop to entry + costs once the high reached +be_at R
    tight_at: float | None = None    # once the high reached +tight_at R, trail tighter:
    tight_mult: float | None = None  #   highest high - tight_mult x ATR, or
    tight_low: int | None = None     #   the lowest low of the last tight_low bars
    time_n: int | None = None        # after time_n bars without ever touching +time_r R: exit next open
    time_r: float = 0.5
    ox_atr: float | None = None      # over-extension: close > SMA50 + ox_atr x ATR -> sell ox_frac next open
    ox_rsi: float | None = None      # or RSI14 > ox_rsi
    ox_frac: float = 1.0
    earn_days: int | None = None     # next earnings reaction day <= earn_days sessions ahead and in profit:
    earn_frac: float = 1.0           #   sell earn_frac at the next open
    fb_days: int | None = None       # failed breakout: within the first fb_days bars (fill bar = 1) a close below the
    fb_buf: float = 0.0              #   breakout level (prior n-day high at the signal) - fb_buf x ATR -> exit next open


DEFAULT = Policy()


def simulate(a: dict, entry: np.ndarray, pol: Policy = DEFAULT, cost: float = 0.001, slip: float = 0.0):
    """`a`: per-bar arrays o h l c atr exit_sig (+ sma50 rsi14 hi_n earn_k as needed), index (DatetimeIndex).
    `slip`: extra slippage on the entry fill (fraction of the price, on top of `cost`); R stays the stop distance."""
    o, h, lo, c, atr = a["o"], a["h"], a["l"], a["c"], a["atr"]
    exit_sig = a["exit_sig"] if pol.exit_low else np.zeros(len(c), bool)
    n = len(c)
    idx = a["index"]
    ret = np.zeros(n)
    trades = []
    parts = tuple(sorted(pol.partial))
    earn = a.get(f"earn_{pol.earn_days}") if pol.earn_days else None

    st = {"in": False}
    week_buys: dict = {}
    last_buy = None
    order = None  # pending entry: dict(kind, level, until, sig)

    def sell(t, px, frac):
        """Sell `frac` of the ORIGINAL position (capped at what is left) at px."""
        f = min(frac, st["left"])
        if f <= 0:
            return
        st["cash"] += f * st["q0"] * px * (1 - cost)
        st["left"] -= f
        if st["left"] <= 1e-12:
            st["left"] = 0.0

    def finish(t, reason):
        ep, rp = st["ep"], st["risk_px"]
        # drawdown from the highest price since the fill, with the high of every bar assumed BEFORE its low (the
        # Pine engine's convention): the fill bar's high counts for an open fill, the exit bar's high only when the
        # exit happened inside the bar (not at the open)
        peak, dd = ep, 0.0
        for i in range(st["ei"], t):
            if not (i == st["ei"] and st["intrabar"]):
                peak = max(peak, h[i])
            dd = min(dd, lo[i] / peak - 1)
        if not st["at_open"] and not (t == st["ei"] and st["intrabar"]):
            peak = max(peak, h[t])
        dd = min(dd, st["last_px"] / peak - 1)
        seg_h, seg_l = h[st["ei"]:t], lo[st["ei"]:t]
        hi = seg_h.max() if len(seg_h) else ep
        lw = min(seg_l.min() if len(seg_l) else ep, st["last_px"])
        touch = {}
        for k in LEVELS:
            hit = np.flatnonzero(seg_h >= ep + k * rp)
            touch[k] = int(hit[0]) if len(hit) else None
        r = st["cash"] - 1
        trades.append({"entry_i": st["ei"], "sig_i": st["sig"], "exit_i": t, "entry_date": idx[st["ei"]],
                       "exit_date": idx[t], "entry": ep, "ret": r, "bars": t - st["ei"], "reason": reason,
                       "risk": rp / ep, "R": r / (rp / ep), "mfe_R": (hi - ep) / rp, "mae_R": (lw - ep) / rp,
                       "touch": touch, "parts_hit": st["parts_hit"], "dd": dd})
        st["in"] = False

    def value(t):
        return st["cash"] + st["left"] * st["q0"] * c[t]

    for t in range(n):
        if st["in"]:
            ep, rp = st["ep"], st["risk_px"]
            v_prev = st["v_prev"]
            done = None
            st["at_open"] = False
            # ---- at the open
            if st["pend_all"]:
                st["last_px"] = o[t]
                st["at_open"] = True
                sell(t, o[t], 1.0)
                done = st["pend_all"]
            else:
                if st["pend_frac"] > 0:
                    sell(t, o[t], st["pend_frac"])
                    st["pend_frac"] = 0.0
                if o[t] <= st["stop"]:
                    st["last_px"] = o[t]
                    st["at_open"] = True
                    sell(t, o[t], 1.0)
                    done = "stop"
                else:
                    for j, (lv, fr) in enumerate(parts):
                        if not st["phit"][j] and o[t] >= ep + lv * rp:
                            st["phit"][j] = True
                            st["parts_hit"] += 1
                            sell(t, o[t], fr)
                    if st["tgt"] is not None and o[t] >= st["tgt"]:
                        st["last_px"] = o[t]
                        st["at_open"] = True
                        sell(t, o[t], 1.0)
                        done = "target"
                # ---- inside the bar: stop first, then targets
                if done is None and st["left"] > 0:
                    if lo[t] <= st["stop"]:
                        st["last_px"] = st["stop"]
                        sell(t, st["stop"], 1.0)
                        done = "stop"
                    else:
                        for j, (lv, fr) in enumerate(parts):
                            if not st["phit"][j] and h[t] >= ep + lv * rp:
                                st["phit"][j] = True
                                st["parts_hit"] += 1
                                sell(t, ep + lv * rp, fr)
                        if st["tgt"] is not None and h[t] >= st["tgt"]:
                            st["last_px"] = st["tgt"]
                            sell(t, st["tgt"], 1.0)
                            done = "target"
                if done is None and st["left"] <= 0:
                    done = "partials"
            v = value(t)
            ret[t] = v / v_prev - 1
            st["v_prev"] = v
            if done is not None:
                finish(t, done)
                continue
            _at_close(t, st, a, pol, exit_sig, earn)
            continue

        # ---- flat: pending entry order?
        if order is not None:
            i = order["sig"]
            fill = None
            if order["kind"] == "open":
                fill = o[t]
            elif order["kind"] == "stop":
                lvl = order["level"]
                fill = o[t] if o[t] >= lvl else (lvl if h[t] >= lvl else None)
            else:  # limit
                lvl = order["level"]
                fill = o[t] if o[t] <= lvl else (lvl if lo[t] <= lvl else None)
            if fill is None:
                if t >= order["until"]:
                    order = None
                continue
            kind = order["kind"]
            order = None
            rp = fill * pol.stop_pct if pol.stop_pct is not None else pol.stop * atr[i]
            st.update({"in": True, "ep": fill, "ei": t, "sig": i, "risk_px": rp, "stop": fill - rp, "hh": h[t],
                       "q0": 1 / (fill * (1 + slip) * (1 + cost)), "cash": 0.0, "left": 1.0, "pend_all": None, "pend_frac": 0.0,
                       "phit": [False] * len(parts), "parts_hit": 0, "tight": False, "ox_done": False,
                       "earn_done": False, "last_px": fill, "intrabar": False, "at_open": False,
                       "tgt": fill * (1 + pol.tgt_pct) if pol.tgt_pct is not None else
                       (fill + pol.target * rp if pol.target is not None else None)})
            done = None
            if lo[t] <= st["stop"]:
                st["last_px"] = st["stop"]
                sell(t, st["stop"], 1.0)
                done = "stop"
            elif kind == "open":
                for j, (lv, fr) in enumerate(parts):
                    if h[t] >= fill + lv * rp:
                        st["phit"][j] = True
                        st["parts_hit"] += 1
                        sell(t, fill + lv * rp, fr)
                if st["tgt"] is not None and h[t] >= st["tgt"]:
                    st["last_px"] = st["tgt"]
                    sell(t, st["tgt"], 1.0)
                    done = "target"
                elif st["left"] <= 0:
                    done = "partials"
            if kind != "open":  # an intrabar fill: the bar's high may have come before the fill
                st["hh"] = max(fill, c[t])
                st["intrabar"] = True
            v = value(t)
            ret[t] = v - 1
            st["v_prev"] = v
            if done is not None:
                finish(t, done)
                continue
            _at_close(t, st, a, pol, exit_sig, earn)
            continue

        if entry[t] and t + 1 < n and np.isfinite(atr[t]):
            if pol.min_gap_days is not None:
                if last_buy is not None and (idx[t] - last_buy).days < pol.min_gap_days:
                    continue
                last_buy = idx[t]
            if pol.max_week is not None:
                wk = tuple(idx[t].isocalendar()[:2])
                if week_buys.get(wk, 0) >= pol.max_week:
                    continue
                week_buys[wk] = week_buys.get(wk, 0) + 1
            if pol.entry == "open":
                order = {"kind": "open", "sig": t, "until": t + 1}
            elif pol.entry == "stop":
                order = {"kind": "stop", "sig": t, "level": h[t] + pol.e_buf * atr[t], "until": t + pol.e_days}
            else:
                lvl = a["hi_n"][t] if pol.pb_mode == "brk" else c[t] - pol.pb * atr[t]
                order = {"kind": "limit", "sig": t, "level": lvl, "until": t + pol.e_days}
    return ret, trades


def _at_close(t, st, a, pol: Policy, exit_sig, earn):
    """End-of-bar updates of an open position: trail, break-even, tight trail, exit decisions for the next open."""
    h, lo, c, atr = a["h"], a["l"], a["c"], a["atr"]
    ep, rp = st["ep"], st["risk_px"]
    if not (t == st["ei"] and st.get("intrabar")):
        st["hh"] = max(st["hh"], h[t])
    gain = st["hh"] - ep
    if pol.tight_at is not None and gain >= pol.tight_at * rp:
        st["tight"] = True
    if np.isfinite(atr[t]):
        mult = pol.tight_mult if (st["tight"] and pol.tight_mult is not None) else pol.trail
        st["stop"] = max(st["stop"], st["hh"] - mult * atr[t])
    if st["tight"] and pol.tight_low is not None:
        st["stop"] = max(st["stop"], lo[max(0, t - pol.tight_low + 1):t + 1].min())
    if pol.be_at is not None and gain >= pol.be_at * rp:
        st["stop"] = max(st["stop"], ep * (1 + 0.001) / (1 - 0.001))
    if exit_sig[t]:
        st["pend_all"] = "signal"
    if pol.fb_days is not None and t - st["ei"] < pol.fb_days:
        i = st["sig"]
        if c[t] < a["hi_n"][i] - pol.fb_buf * atr[i]:
            st["pend_all"] = st["pend_all"] or "failed"
    if pol.time_n is not None and t - st["ei"] == pol.time_n and gain < pol.time_r * rp:
        st["pend_all"] = st["pend_all"] or "time"
    if not st["ox_done"] and (
            (pol.ox_atr is not None and c[t] > a["sma50"][t] + pol.ox_atr * atr[t])
            or (pol.ox_rsi is not None and a["rsi14"][t] > pol.ox_rsi)):
        st["ox_done"] = True
        if pol.ox_frac >= 1:
            st["pend_all"] = st["pend_all"] or "overext"
        else:
            st["pend_frac"] = max(st["pend_frac"], pol.ox_frac)
    if earn is not None and not st["earn_done"] and earn[t] and c[t] > ep:
        st["earn_done"] = True
        if pol.earn_frac >= 1:
            st["pend_all"] = st["pend_all"] or "earnings"
        else:
            st["pend_frac"] = max(st["pend_frac"], pol.earn_frac)


def arrays(df: pd.DataFrame, atr: np.ndarray, exit_sig: np.ndarray, extra: dict | None = None) -> dict:
    a = {"o": df["open"].to_numpy(float), "h": df["high"].to_numpy(float), "l": df["low"].to_numpy(float),
         "c": df["close"].to_numpy(float), "atr": atr, "exit_sig": exit_sig, "index": df.index}
    a.update(extra or {})
    return a
