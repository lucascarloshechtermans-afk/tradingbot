"""Vectorised trade outcomes for the 20/21 definitions (config20): for many signal bars of one stock at once,
every target x horizon x stop combination.

Per bar after the fill (the fill bar included) the events are resolved in this order:
  1. open >= target            -> target filled at the open (a gap above the limit)
  2. open <= stop              -> stopped at the open (a gap through the stop)
  3. low <= stop               -> stopped at the stop  (wins when the target is also inside the bar)
  4. high >= target            -> target filled at the target
The first bar with an event decides; without an event the trade is closed at the close of the last horizon day.
"""
from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from indicator_lab.twenty import config20 as K

WMAX = 30


def windows(o, h, lo, c, starts):
    """(fill, O, H, L, C) for signal bars `starts`: row k holds bars starts[k]+1 .. starts[k]+WMAX."""
    W = [sliding_window_view(x, WMAX) for x in (o, h, lo, c)]
    rows = starts + 1
    O, H, L, C = (w[rows] for w in W)
    return O[:, 0], O, H, L, C


def events(O, H, L, stop, tgt):
    """First event per row: (index of the bar, 1 = target / 2 = stop / 0 = none, exit price)."""
    t_open = O >= tgt[:, None]
    s_open = O <= stop[:, None]
    s_in = L <= stop[:, None]
    t_in = H >= tgt[:, None]
    code = np.where(t_open, 1, np.where(s_open | s_in, 2, np.where(t_in, 1, 0)))
    px = np.where(t_open, O, np.where(s_open, O, np.where(s_in, stop[:, None], tgt[:, None])))
    has = code != 0
    first = np.where(has.any(axis=1), has.argmax(axis=1), WMAX)
    r = np.arange(len(O))
    fi = np.minimum(first, WMAX - 1)
    return first, np.where(first < WMAX, code[r, fi], 0), np.where(first < WMAX, px[r, fi], np.nan)


def outcome(fill, C, stop, tgt, first, ev, px, horizon, slip):
    """Net return and success flag for one horizon (days counted from the fill day = day 1)."""
    entry = fill * (1 + K.COST + slip)
    inside = first < horizon
    hit = inside & (ev == 1)
    stopped = inside & (ev == 2)
    exit_net = np.where(hit, px * (1 - K.COST),                          # limit order: no slippage
                        np.where(stopped, px * (1 - K.COST - slip),
                                 C[:, horizon - 1] * (1 - K.COST - slip)))
    return exit_net / entry - 1, hit, stopped


def stop_price(kind, val, fill, sig_low, sig_atr):
    if kind == "low":
        return sig_low
    if kind == "atr":
        return fill - val * sig_atr
    return fill * (1 - val)
