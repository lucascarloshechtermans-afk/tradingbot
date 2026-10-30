"""4H scanner for the user's own indicator, swing v4.1 (pine/swing_v4_1.pine), via its bar-by-bar Python emulation
(pine_sim.V41) run on 4H bars, i.e. what the Pine script shows when it is put on a 4-hour chart.

    python -m indicator_lab.h4.scan_v41_4h 2026-10-26                # refresh Yahoo 60m data, then scan that day
    python -m indicator_lab.h4.scan_v41_4h 2026-10-26 --no-refresh

Same data, bars (09:30-13:30 and 13:30-16:00 New York) and liquidity floor (close >= $5, 50-bar average dollar volume
>= $2.5M) as h4/scan4h.py. Note: v4.1 was designed and tested on DAILY bars (its quality model was trained on daily
breakouts); on 4H every lookback counts 4H bars and the result is untested. The SPY inputs are SPY's daily values of the
bar's date. Watchlist only, never orders. Output: indicator_lab/h4/reports/scan_v41_4h_latest.md.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from indicator_lab import pine_sim as PS
from indicator_lab.h4 import scan4h as S
from indicator_lab.h4.test4h import bars4h

OUT = os.path.join(os.path.dirname(__file__), "reports", "scan_v41_4h_latest.md")


def main():
    day = pd.Timestamp(sys.argv[1])
    univ = S.universe()
    if "--no-refresh" not in sys.argv:
        S.refresh(univ)
    rows, n = [], 0
    for t in univ:
        df = bars4h(t)
        if df is None or len(df) < 400:
            continue
        df = S.completed(df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)])
        if df.index[-1] < day:
            continue
        n += 1
        out = PS.run(df, t, PS.V41)
        liquid = ((df["close"] >= 5) & ((df["close"] * df["volume"]).rolling(50).mean() >= 2.5e6)).to_numpy()
        for i in np.where(np.asarray(out["buy"]) & liquid & (df.index.normalize() == day))[0]:
            c = float(df["close"].iloc[i])
            rows.append({"ticker": t, "BUY (4H-bar)": df.index[i].strftime("%Y-%m-%d %H:%M"), "slot signaalbar": round(c, 2),
                         "laatste koers": round(float(df["close"].iloc[-1]), 2),
                         "sinds signaal": f"{(df['close'].iloc[-1] / c - 1) * 100:+.1f}%"})
    d = pd.DataFrame(rows).sort_values(["BUY (4H-bar)", "ticker"]) if rows else pd.DataFrame()
    txt = (f"# Swing v4.1 BUY op 4H — {day.date()}\n\nGescand: {n} NASDAQ-aandelen met emulatie van "
           "`pine/swing_v4_1.pine` op 4H-bars (09:30-13:30 en 13:30-16:00 New York), liquide: slot >= $5 en 50-bar "
           "dollaromzet >= $2,5M. Let op: v4.1 is ontworpen en getest op dagbars; op 4H is hij niet getest. "
           "Watchlist, geen orders.\n\n" + (d.to_markdown(index=False) if len(d) else "_Geen signalen._") + "\n")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
