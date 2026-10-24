"""Well-known swing strategies (long only, their classic entry and exit rules) on the NASDAQ universe, on DAILY or
4-HOUR bars, with the user's rule (at most one BUY per stock per two weeks) and the liquidity floor.

    CLASSIC_TF=day python -m indicator_lab.h4.classics     # 2015-01-01 .. 2024-10-21, daily cache (.cache20)
    CLASSIC_TF=4h  python -m indicator_lab.h4.classics     # ~2024-07 .. now, Yahoo 60m grouped to 4H (.cache4h)

Signals on a bar's close, fills at the next bar's open, exits at the next open after the exit condition (no stop or
trail unless the strategy itself has one, as they are usually published). Costs 0.1% per side + 0.1% entry slippage.
Liquidity floor on the signal bar: close >= $5 and 50-bar average dollar volume >= $5M (4H: >= $2.5M per bar, about
the same per day). Two views: all trades (as if every signal were taken) and an account with at most 10 positions of
10% (idle cash 0%), mean of 10 random orders of same-day signals.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

TF = os.environ.get("CLASSIC_TF", "day")
if TF == "day":
    from indicator_lab.swing5 import protocol5 as P5
    P5.install_dev()
else:
    from indicator_lab.h4 import (
        test4h,  # noqa: F401  (sets the full-data mode itself; provides the 4H bars)
    )

from indicator_lab import ind
from indicator_lab.evaluate import get
from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.metrics import equity_stats
from indicator_lab.swing4 import lab as L
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.twenty import data20

OUT = os.path.join(os.path.dirname(__file__), "reports")
PERIOD_DAY = (pd.Timestamp("2015-01-01"), pd.Timestamp("2024-10-21"))
SLIP = 0.001
SEEDS = 10
NO_STOP = S2.Policy(trail=1e6, stop=1e6, min_gap_days=14)   # exits come only from the strategy's own signal


def strategies(df: pd.DataFrame) -> dict:
    """name -> (entry, exit) boolean arrays, both decided at the bar's close."""
    c, h, lo = df["close"], df["high"], df["low"]
    up = c > ind.sma(c, 200)
    r2 = ind.rsi(c, 2)
    low_b, mid, _ = ind.bbands(c, 20, 2.0)
    k = ind.stoch(df, 14, 3)
    m, sig, _ = ind.macd(c)
    e9, e21 = ind.ema(c, 9), ind.ema(c, 21)
    st = ind.supertrend(df, 10, 3.0)
    ibs = ind.ibs(df)
    hi20, lo20 = h.rolling(20).max().shift(1), lo.rolling(20).min().shift(1)
    out = {
        "1 RSI(2) < 10 (Connors), uit: slot > SMA5": (up & (r2 < 10), c > ind.sma(c, 5)),
        "2 Cumulatieve RSI(2) 2 dagen < 35, uit: RSI(2) > 65": (up & (r2 + r2.shift(1) < 35), r2 > 65),
        "3 Double 7s: 7-daags laagste slot, uit: 7-daags hoogste": (up & (c <= c.rolling(7).min()), c >= c.rolling(7).max()),
        "4 IBS < 0.2, uit: slot > high van gisteren": (up & (ibs < 0.2), c > h.shift(1)),
        "5 Bollinger: slot < onderband, uit: slot > middenband": (up & (c < low_b), c > mid),
        "6 Stochastic %K kruist 20 omhoog, uit: %K > 80": (up & (k > 20) & (k.shift(1) <= 20), k > 80),
        "7 MACD kruist signaal omhoog, uit: kruist omlaag": (up & (m > sig) & (m.shift(1) <= sig.shift(1)), m < sig),
        "8 EMA 9/21 kruist omhoog, uit: kruist omlaag": ((e9 > e21) & (e9.shift(1) <= e21.shift(1)), e9 < e21),
        "9 Supertrend(10,3) draait long, uit: draait short": (st & ~st.shift(1, fill_value=False), ~st),
        "10 Donchian 20-breakout + sterke slot (v2), uit: 20-laagste of 4xATR-trail": (
            up & (c > hi20) & (ibs >= 0.7), c < lo20),
    }
    return {name: (np.nan_to_num(e.to_numpy(dtype=float)).astype(bool), np.nan_to_num(x.to_numpy(dtype=float)).astype(bool))
            for name, (e, x) in out.items()}


def frames() -> dict:
    out = {}
    univ = nasdaq()[:int(os.environ["CLASSIC_N"])] if os.environ.get("CLASSIC_N") else nasdaq()
    if TF == "day":
        for t in univ:
            df = data20.load(t)
            if df is None:
                continue
            df = df[(df.index < pd.Timestamp("2024-10-22")) & (df[["open", "high", "low", "close"]] > 0).all(axis=1)]
            if len(df) >= 400 and df.index[-1] >= pd.Timestamp("2016-01-01"):
                out[t] = df
    else:
        from indicator_lab.h4.test4h import bars4h
        for t in univ:
            df = bars4h(t)
            if df is not None and len(df) >= 400:
                out[t] = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
    return out


def run_all(fr: dict, start, end) -> dict:
    """{strategy: {ticker: (returns, trades)}}"""
    res: dict = {}
    min_dvol = 5e6 if TF == "day" else 2.5e6
    for t, df in fr.items():
        liquid = ((df["close"] >= 5) & ((df["close"] * df["volume"]).rolling(50).mean() >= min_dvol)).to_numpy()
        inwin = ((df.index >= start) & (df.index <= end))
        a = ind.atr(df, 14).to_numpy()
        for name, (e, x) in strategies(df).items():
            pol = S2.Policy(min_gap_days=14) if name.startswith("10 ") else NO_STOP
            arr = S2.arrays(df, a, x)
            r, tr = S2.simulate(arr, e & liquid & inwin, pol, slip=SLIP)
            for z in tr:
                z["ticker"] = t
            rs = pd.Series(r, index=df.index)
            res.setdefault(name, {})[t] = (rs[(rs.index >= start) & (rs.index <= end)], tr)
    return res


def daily(port: pd.Series) -> pd.Series:
    return port if TF == "day" else (1 + port).groupby(port.index.normalize()).prod() - 1


def summary(name, res) -> dict:
    tt = pd.DataFrame([x for _, tr in res.values() for x in tr])
    if tt.empty:
        return {"strategie": name, "trades": 0}
    r = tt["ret"].to_numpy()
    w, lz = r[r > 0], r[r <= 0]
    ports = [daily(L.portfolio(res, 10, s)["port"]) for s in range(SEEDS)]
    st = [equity_stats(p) for p in ports]
    m = {k: float(np.mean([s[k] for s in st])) for k in ("cagr", "maxdd", "sharpe")}
    unit = "dagen" if TF == "day" else "4H-bars"
    return {"strategie": name, "trades": len(r), "winrate": f"{(r > 0).mean() * 100:.0f}%",
            "gem. winst": f"{w.mean() * 100:.1f}%", "gem. verlies": f"{lz.mean() * 100:.1f}%",
            "gem. trade": f"{r.mean() * 100:.2f}%", "PF": f"{w.sum() / -lz.sum():.2f}" if len(lz) else "∞",
            f"hold ({unit})": f"{tt['bars'].mean():.0f}", "CAGR (10 pos.)": f"{m['cagr'] * 100:.1f}%",
            "max DD": f"{m['maxdd'] * 100:.1f}%", "Sharpe": f"{m['sharpe']:.2f}"}


def main():
    fr = frames()
    if TF == "day":
        start, end = PERIOD_DAY
    else:
        idx = pd.DatetimeIndex(sorted({d for df in fr.values() for d in df.index}))
        start, end = idx[300], idx[-1]   # first ~150 trading days: SMA200 (4H) warm-up
    print(f"{TF}: {len(fr)} NASDAQ stocks, {start.date()} .. {end.date()}", flush=True)
    res = run_all(fr, start, end)
    rows = []
    for name, r in res.items():
        rows.append(summary(name, r))
        print(rows[-1], flush=True)
    spy = get("SPY")["close"].pct_change()
    spy = spy[(spy.index >= start.normalize()) & (spy.index <= end)].fillna(0)
    s = equity_stats(spy)
    rows.append({"strategie": "SPY kopen en vasthouden", "CAGR (10 pos.)": f"{s['cagr'] * 100:.1f}%",
                 "max DD": f"{s['maxdd'] * 100:.1f}%", "Sharpe": f"{s['sharpe']:.2f}"})
    d = pd.DataFrame(rows).fillna("–")
    txt = (f"# Bekende swingstrategieën, {'dagbars' if TF == 'day' else '4H-bars'}, {len(fr)} NASDAQ-aandelen, "
           f"{start.date()} .. {end.date()}\n\nRegels zoals ze bekend zijn (long only), max 1 BUY per aandeel per 2 weken, "
           "liquiditeitsvloer, kosten 0,1%/kant + 0,1% slippage, rekening max 10 posities van 10%.\n\n"
           + d.to_markdown(index=False) + "\n")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"classics_{TF}.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
