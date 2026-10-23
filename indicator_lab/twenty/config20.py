"""Definitions of the Swing 20/21 project (one place, used by research, scanner and the Pine export).

Trade: signal at the close of day i -> buy at the OPEN of day i+1 (variant: buy-stop above the signal high);
target = fill x (1 + TARGET) as a limit order (a gap above it fills at the open); protective stop (variants below);
time exit at the CLOSE of the HORIZON-th trading day counted from the fill day (fill day = day 1).
Inside one bar the order of high and low is unknown: when stop and target are both touched, the stop wins.
Success label: target touched before the stop and within HORIZON days.
"""
from __future__ import annotations

TARGET = 0.20
HORIZON = 21

# protective stop variants (distance below the fill)
STOPS = {
    "signal_low": ("low", None),     # the low of the signal bar
    "atr1.5": ("atr", 1.5),          # 1.5 x ATR14 of the signal bar
    "atr2": ("atr", 2.0),
    "atr3": ("atr", 3.0),
    "pct7": ("pct", 0.07),           # fixed -7%
    "pct10": ("pct", 0.10),          # fixed -10%
}

# costs per side (commission + spread) + extra slippage for thin names, by 50-day average dollar volume
COST = 0.0015
SLIP_TIERS = ((10e6, 0.0025), (25e6, 0.0010), (100e6, 0.0005))   # below $10M: +0.25% per side, ...
# a limit order at the target does not slip; entries (market at the open), stops and time exits do

# universe filters, applied point in time on the signal date
MIN_PRICE = 5.0
MIN_DVOL = 5e6

# phase 0 grid
GRID_TARGETS = (0.10, 0.15, 0.20, 0.25, 0.30)
GRID_HORIZONS = (5, 10, 15, 21, 30)


def slippage(dvol50: float) -> float:
    for lim, s in SLIP_TIERS:
        if dvol50 < lim:
            return s
    return 0.0
