"""Daily scanner for the user's own indicator, swing v4.1 (pine/swing_v4_1.pine), via its bar-by-bar Python emulation
(pine_sim.V41, parity-tested against the Pine script): which NASDAQ stocks printed a BUY in the last N trading days.

    python -m indicator_lab.scan_v41            # last 5 completed trading days
    SCAN_DAYS=10 python -m indicator_lab.scan_v41

v4.1 = 20-day breakout + close > SMA200 + strong close (IBS >= 0.7) + quality model, and only while SPY's 63-day
return <= 3% (the regime rule). Daily data: Swing 20/21 cache. Liquidity shown, as in the research (close >= $5,
50-day average dollar volume >= $5M). Research status: v4 lags SPY on every unseen test (PROGRESS.md). Never orders.
Output: indicator_lab/reports/scan_v41_latest.md and .csv.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab import pine_sim as S
from indicator_lab.evaluate import get
from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.twenty import data20

OUT = os.path.join(os.path.dirname(__file__), "reports")
DAYS = int(os.environ.get("SCAN_DAYS", "5"))


def main():
    data20.final_mode()
    now = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    spy = get("SPY")
    spy = spy[spy.index.normalize() + pd.Timedelta(hours=16) <= now]
    roc63 = spy["close"] / spy["close"].shift(63) - 1
    window = spy.index[-DAYS:]
    rows, n = [], 0
    for t in nasdaq(set(data20.DEV) | data20.H_TICKERS):
        df = data20.load(t)
        if df is None or len(df) < 300:
            continue
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
        df = df[df.index.normalize() + pd.Timedelta(hours=16) <= now]
        if df.index[-1] < window[0]:
            continue
        n += 1
        out = S.run(df, t, S.V41)
        buy = out["buy"]
        dv = (df["close"] * df["volume"]).rolling(50).mean()
        for i in np.where(buy)[0]:
            day = df.index[i]
            if day < window[0]:
                continue
            c = float(df["close"].iloc[i])
            rows.append({"ticker": t, "BUY op slot van": day.date(), "slot": round(c, 2),
                         "laatste slot": round(float(df["close"].iloc[-1]), 2),
                         "sinds signaal": f"{(df['close'].iloc[-1] / c - 1) * 100:+.1f}%",
                         "liquide (>= $5, >= $5M/dag)": "ja" if c >= 5 and dv.iloc[i] >= 5e6 else "nee"})
    d = pd.DataFrame(rows).sort_values("BUY op slot van", ascending=False) if rows else pd.DataFrame()
    reg = pd.DataFrame({"SPY 63-daags rendement": (roc63.loc[window] * 100).round(1).astype(str) + "%",
                        "BUY toegestaan (<= 3%)": np.where(roc63.loc[window] <= 0.03, "ja", "nee")},
                       index=[x.date() for x in window])
    txt = (f"# Swing v4.1 (dagbars) — BUY-signalen laatste {DAYS} handelsdagen ({window[0].date()} .. {window[-1].date()})"
           f"\n\nGescand: {n} NASDAQ-aandelen met emulatie van `pine/swing_v4_1.pine`. Geen orders.\n\n"
           "## Marktregel van v4.1 (BUY alleen als SPY in 63 dagen hooguit 3% steeg)\n\n" + reg.to_markdown()
           + "\n\n## Signalen\n\n" + (d.to_markdown(index=False) if len(d) else "_Geen BUY-signalen in deze periode._") + "\n")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "scan_v41_latest.md"), "w") as fh:
        fh.write(txt)
    if len(d):
        d.to_csv(os.path.join(OUT, "scan_v41_latest.csv"), index=False)
    print(txt)


if __name__ == "__main__":
    main()
