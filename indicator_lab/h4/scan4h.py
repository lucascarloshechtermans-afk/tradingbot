"""Live 4H scanner: which NASDAQ stocks gave a BUY signal on the 4-hour timeframe with the newest stock rule,
P1 Minervini trend template + VCP breakout (h4/pro_concepts.py, the best 4H rule of the research; NOTE: it failed its
one-shot holdout test, see h4/reports/holdout_minervini4h.md, so this is a watchlist, not a proven edge).

    python -m indicator_lab.h4.scan4h              # refresh the last 60 days of Yahoo 60m data, then scan
    python -m indicator_lab.h4.scan4h --no-refresh # scan the cached data only
    SCAN_BARS=20 python -m indicator_lab.h4.scan4h # look back 20 4H bars (default 10 = 5 trading days)

Only completed 4H bars are used (09:30-13:30 and 13:30-16:00 New York). Liquidity floor as in the research
(close >= $5, 50-bar average dollar volume >= $2.5M). RS rank is taken across all scanned stocks.
Output: indicator_lab/h4/reports/scan4h_latest.md and .csv. This never places orders.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

os.environ["PRO_TF"] = os.environ["CLASSIC_TF"] = "4h"
from indicator_lab import ind
from indicator_lab.h4 import pro_concepts as PC
from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.h4.test4h import CACHE, bars4h
from indicator_lab.twenty import data20

OUT = os.path.join(os.path.dirname(__file__), "reports")
RULE = "P1 Minervini trend template + VCP-breakout"
LOOKBACK = int(os.environ.get("SCAN_BARS", "10"))


def universe() -> list[str]:
    return nasdaq(set(data20.DEV) | data20.H_TICKERS)


def refresh(tickers, batch: int = 80):
    """Append the last 60 days of 60-minute bars to the cache (keeps the older history)."""
    import yfinance as yf
    os.makedirs(CACHE, exist_ok=True)
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        try:
            raw = yf.download(chunk, period="60d", interval="60m", auto_adjust=True, progress=False, group_by="ticker",
                              threads=True)
        except Exception as e:  # noqa: BLE001  transient Yahoo errors
            print("batch failed:", e, flush=True)
            continue
        for t in chunk:
            try:
                new = raw[t].rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
            except KeyError:
                continue
            if new.empty:
                continue
            p = os.path.join(CACHE, f"{t}.csv.gz")
            new.index = new.index.map(str)
            if os.path.exists(p):
                try:
                    old = pd.read_csv(p, index_col=0)
                    new = pd.concat([old, new])
                    new = new[~new.index.duplicated(keep="last")].sort_index()
                except (pd.errors.EmptyDataError, OSError, EOFError):
                    pass
            new.to_csv(p, compression="gzip")
        print(f"refresh {min(i + batch, len(tickers))}/{len(tickers)}", flush=True)


def completed(df: pd.DataFrame) -> pd.DataFrame:
    """Drop a 4H bar that is still forming (its session part has not closed yet in New York)."""
    now = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    end = df.index + pd.to_timedelta(np.where(df.index.hour == 9, 4.0, 2.5), unit="h")
    return df[end <= now]


def main():
    univ = universe()
    if "--no-refresh" not in sys.argv:
        refresh(univ)
    fr = {}
    for t in univ:
        df = bars4h(t)
        if df is not None and len(df) >= 400:
            df = completed(df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)])
            fr[t] = df
    rs = PC.rs_rank(fr)
    last = max(df.index[-1] for df in fr.values())
    rows = []
    for t, df in fr.items():
        if df.index[-1] < last - pd.Timedelta(days=4):     # stale ticker (delisted / no recent data)
            continue
        liquid = ((df["close"] >= 5) & ((df["close"] * df["volume"]).rolling(50).mean() >= 2.5e6)).to_numpy()
        e, _, _, stop_pct = PC.signals(df, rs[t].reindex(df.index).to_numpy())[RULE]
        hit = np.where(e & liquid)[0]
        hit = hit[hit >= len(df) - LOOKBACK]
        for i in hit:
            c = float(df["close"].iloc[i])
            rows.append({"ticker": t, "signaal (4H-bar)": df.index[i].strftime("%Y-%m-%d %H:%M"),
                         "slot signaalbar": round(c, 2), "laatste koers": round(float(df["close"].iloc[-1]), 2),
                         "sinds signaal": f"{(df['close'].iloc[-1] / c - 1) * 100:+.1f}%",
                         "stop (-8% van instap)": round(c * (1 - stop_pct), 2),
                         "RS-percentiel": round(float(rs[t].reindex(df.index).iloc[i]), 0),
                         "ATR%": f"{float(ind.atr(df, 14).iloc[i]) / c * 100:.1f}%"})
    d = pd.DataFrame(rows).sort_values("signaal (4H-bar)", ascending=False) if rows else pd.DataFrame()
    from indicator_lab.timing import regime as R
    try:
        s = R.load("SPY")
        regime = "IN (SPY boven SMA200)" if s.iloc[-1] > s.rolling(200).mean().iloc[-1] else "UIT (SPY onder SMA200)"
    except FileNotFoundError:
        regime = "onbekend"
    txt = (f"# 4H BUY-signalen — {RULE}\n\nGescand: {len(fr)} NASDAQ-aandelen, laatste afgesloten 4H-bar {last}. "
           f"Signalen in de laatste {LOOKBACK} 4H-bars. Marktregime (dagbasis): {regime}.\n\n"
           "Let op: deze regel zakte voor zijn eenmalige holdout-test (-0,4%/jaar op nooit gebruikte aandelen). Gebruik "
           "dit als watchlist, niet als bewezen voordeel. Geen orders.\n\n"
           + (d.to_markdown(index=False) if len(d) else "_Geen signalen._") + "\n")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "scan4h_latest.md"), "w") as fh:
        fh.write(txt)
    if len(d):
        d.to_csv(os.path.join(OUT, "scan4h_latest.csv"), index=False)
    print(txt)


if __name__ == "__main__":
    main()
