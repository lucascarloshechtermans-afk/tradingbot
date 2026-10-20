"""Long-only, single-position, fully-invested-when-in-trade simulator.

Timing rules (no look-ahead):
- An entry/exit *signal* is computed from bar t's close and filled at bar t+1's OPEN.
- Stop/target levels use ATR known at the signal bar (t), never the fill bar.
- A protective stop is checked from the entry bar onward. If the bar OPENS through the
  stop (gap), the fill is the open, not the stop. If stop and target are both inside
  one bar, the stop is assumed first (conservative).
- Trailing stops ratchet only after a bar has closed, so they apply from the next bar.
- A time exit (max_bars) fills at that bar's close (a market-on-close order).
- Costs: `cost` per side as a fraction of price (default 0.10% = 0.05% commission +
  0.05% slippage), charged on every entry and exit, stops included.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ExitRules:
    stop_atr: float | None = None   # initial protective stop, ATR multiples below entry
    tgt_atr: float | None = None    # profit target, ATR multiples above entry
    trail_atr: float | None = None  # chandelier: highest high since entry - k*ATR
    max_bars: int | None = None     # time stop, bars held
    be_atr: float | None = None     # move stop to breakeven once high >= entry + k*ATR
    close_stop: bool = False        # stops only trigger on a CLOSE below them (fill next open)
    tight_after: float | None = None  # once high >= entry + k*ATR(signal), trail with tight_trail
    fail_bars: int | None = None    # after this many bars, exit (next open) if close is still <= entry
    entry_close: bool = False       # fill at the SIGNAL bar's close (market-on-close) instead of next open
    side: int = 1                   # 1 = long, -1 = short (see simulate_short)
    tight_trail: float | None = None


def simulate(df: pd.DataFrame, entry: np.ndarray, exit_sig: np.ndarray | None, atr: np.ndarray,
             rules: ExitRules, cost: float = 0.001, size: np.ndarray | None = None):
    """Return (daily_returns: np.ndarray, trades: list[dict]).

    `size` (optional, 0..1 per bar) scales exposure of a trade opened on the next bar,
    e.g. for volatility-targeted sizing; the rest sits in cash at 0%.
    """
    if rules.side == -1:
        return simulate_short(df, entry, exit_sig, atr, rules, cost, size)
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    n = len(c)
    ret = np.zeros(n)
    trades: list[dict] = []
    if exit_sig is None:
        exit_sig = np.zeros(n, dtype=bool)

    in_pos = False
    pend_entry = False
    pend_exit = False
    ep = stop = tgt = hh = 0.0
    ei = 0
    w = 1.0
    sig_atr = 0.0

    for t in range(n):
        if in_pos:
            prev = c[t - 1]
            px = None
            reason = None
            if pend_exit:
                px, reason = o[t], "signal"
            elif not rules.close_stop and o[t] <= stop:
                px, reason = o[t], "stop"
            elif not rules.close_stop and lo[t] <= stop:
                px, reason = stop, "stop"
            elif o[t] >= tgt:
                px, reason = o[t], "target"
            elif h[t] >= tgt:
                px, reason = tgt, "target"
            elif rules.max_bars is not None and t - ei >= rules.max_bars:
                px, reason = c[t], "time"
            if px is not None:
                ret[t] = w * ((px * (1 - cost)) / prev - 1)
                trades.append(_trade(df, ei, t, ep, px, cost, reason))
                in_pos = pend_exit = False
            else:
                ret[t] = w * (c[t] / prev - 1)
                hh = max(hh, h[t])
                a = atr[t]
                if rules.trail_atr is not None and np.isfinite(a):
                    stop = max(stop, hh - rules.trail_atr * a)
                if rules.tight_after is not None and hh >= ep + rules.tight_after * sig_atr and np.isfinite(a):
                    stop = max(stop, hh - rules.tight_trail * a)
                if rules.be_atr is not None and hh >= ep + rules.be_atr * sig_atr:
                    stop = max(stop, ep)
                if exit_sig[t] or (rules.close_stop and c[t] <= stop):
                    pend_exit = True
                if rules.fail_bars is not None and t - ei >= rules.fail_bars and c[t] <= ep:
                    pend_exit = True
            continue

        if pend_entry:
            pend_entry = False
            a = atr[t - 1]
            ep = o[t]
            sig_atr = a
            stop = ep - rules.stop_atr * a if rules.stop_atr is not None else -np.inf
            tgt = ep + rules.tgt_atr * a if rules.tgt_atr is not None else np.inf
            hh = h[t]
            ei = t
            w = 1.0 if size is None else float(np.clip(size[t - 1], 0.0, 1.0))
            in_pos = True
            # same-bar stop/target (stop first)
            px = reason = None
            if not rules.close_stop and lo[t] <= stop:
                px, reason = stop, "stop"
            elif h[t] >= tgt:
                px, reason = tgt, "target"
            if px is not None:
                ret[t] = w * ((px * (1 - cost)) / (ep * (1 + cost)) - 1)
                trades.append(_trade(df, ei, t, ep, px, cost, reason))
                in_pos = False
                continue
            ret[t] = w * (c[t] / (ep * (1 + cost)) - 1)
            if rules.trail_atr is not None and np.isfinite(atr[t]):
                stop = max(stop, hh - rules.trail_atr * atr[t])
            if exit_sig[t] or (rules.close_stop and c[t] <= stop):
                pend_exit = True
            continue

        if entry[t] and t + 1 < n and np.isfinite(atr[t]):
            if rules.entry_close:
                ep = c[t]
                sig_atr = atr[t]
                stop = ep - rules.stop_atr * sig_atr if rules.stop_atr is not None else -np.inf
                tgt = ep + rules.tgt_atr * sig_atr if rules.tgt_atr is not None else np.inf
                hh = c[t]
                if rules.trail_atr is not None:
                    stop = max(stop, hh - rules.trail_atr * sig_atr)
                ei = t
                w = 1.0 if size is None else float(np.clip(size[t], 0.0, 1.0))
                ret[t] = w * (1 / (1 + cost) - 1)
                in_pos = True
                if exit_sig[t]:
                    pend_exit = True
            else:
                pend_entry = True

    return ret, trades


def _trade(df, ei, xi, ep, xp, cost, reason):
    r = (xp * (1 - cost)) / (ep * (1 + cost)) - 1
    return {"entry_date": df.index[ei], "exit_date": df.index[xi], "entry": ep, "exit": xp,
            "ret": r, "bars": xi - ei, "reason": reason}


def simulate_short(df, entry, exit_sig, atr, rules: ExitRules, cost: float = 0.001, size=None):
    """Mirror of `simulate` for short positions: stop above entry, chandelier trail from the
    lowest low since entry, target below. Same next-open timing, gap and stop-first rules.
    Borrow fees are not modelled (fine for liquid ETFs/mega caps, optimistic otherwise)."""
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    lo = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    n = len(c)
    ret = np.zeros(n)
    trades: list[dict] = []
    if exit_sig is None:
        exit_sig = np.zeros(n, dtype=bool)
    in_pos = pend_entry = pend_exit = False
    ep = stop = tgt = ll = 0.0
    ei = 0
    w = 1.0

    def close_trade(t, px, reason):
        r = 1 - (px * (1 + cost)) / (ep * (1 - cost))
        trades.append({"entry_date": df.index[ei], "exit_date": df.index[t], "entry": ep, "exit": px,
                       "ret": r, "bars": t - ei, "reason": reason})

    for t in range(n):
        if in_pos:
            prev = c[t - 1]
            px = reason = None
            if pend_exit:
                px, reason = o[t], "signal"
            elif o[t] >= stop:
                px, reason = o[t], "stop"
            elif h[t] >= stop:
                px, reason = stop, "stop"
            elif o[t] <= tgt:
                px, reason = o[t], "target"
            elif lo[t] <= tgt:
                px, reason = tgt, "target"
            elif rules.max_bars is not None and t - ei >= rules.max_bars:
                px, reason = c[t], "time"
            if px is not None:
                ret[t] = w * (1 - px * (1 + cost) / prev)
                close_trade(t, px, reason)
                in_pos = pend_exit = False
            else:
                ret[t] = w * (1 - c[t] / prev)
                ll = min(ll, lo[t])
                if rules.trail_atr is not None and np.isfinite(atr[t]):
                    stop = min(stop, ll + rules.trail_atr * atr[t])
                if exit_sig[t]:
                    pend_exit = True
            continue
        if pend_entry:
            pend_entry = False
            a = atr[t - 1]
            ep = o[t]
            stop = ep + rules.stop_atr * a if rules.stop_atr is not None else np.inf
            tgt = ep - rules.tgt_atr * a if rules.tgt_atr is not None else -np.inf
            ll = lo[t]
            ei = t
            w = 1.0 if size is None else float(np.clip(size[t - 1], 0.0, 1.0))
            in_pos = True
            px = reason = None
            if h[t] >= stop:
                px, reason = stop, "stop"
            elif lo[t] <= tgt:
                px, reason = tgt, "target"
            if px is not None:
                ret[t] = w * (1 - px * (1 + cost) / (ep * (1 - cost)))
                close_trade(t, px, reason)
                in_pos = False
                continue
            ret[t] = w * (1 - c[t] / (ep * (1 - cost)))
            if rules.trail_atr is not None and np.isfinite(atr[t]):
                stop = min(stop, ll + rules.trail_atr * atr[t])
            if exit_sig[t]:
                pend_exit = True
            continue
        if entry[t] and t + 1 < n and np.isfinite(atr[t]):
            pend_entry = True
    return ret, trades
