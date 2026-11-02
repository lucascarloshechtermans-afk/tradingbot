"""Backtest of the user's strategy: daily 20-day Donchian channel breakout trend follower on Exxon Mobil (XOM), long only.

    python -m indicator_lab.xom_donchian            # downloads XOM and SPY (Yahoo, adjusted), writes results/xom_donchian.md
    DATA_DIR=/path python -m indicator_lab.xom_donchian   # use XOM_max.pkl / SPY_max.pkl from that folder instead

Rules (fixed before the run, exactly as described by the user):
  * Signal on the close of day t (daily OHLCV, adjusted for splits and dividends):
      BUY  when close > highest high of the previous 20 days (t-20 .. t-1) and flat;
      SELL when close < lowest low of the previous 20 days and long.
  * Execution at the OPEN of day t+1 (the decision is made once per day when the new daily bar arrives).
  * Costs: 0.05% commission + 0.05% slippage per side (0.10% per side). Flat = cash at 0%.
  * Main result: the full XOM history (1962-2026) and the sub-periods 1962-1992, 1993-2009, 2010-2026, 2021-2026.
Compared with: buy & hold XOM (same costs once in, once out) and buy & hold SPY (from 1993).
Robustness (reported, nothing is selected on it): channel lengths 10 / 20 / 55 / 100 days, and 1,000 random-timing
controls (the same number of trades with the same holding periods, placed at random start dates) to see whether the
breakout TIMING beats random timing with the same time in the market.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results", "xom_donchian.md")
COST = 0.001
PERIODS = [("1962-01-01", "2026-12-31"), ("1962-01-01", "1992-12-31"), ("1993-01-01", "2009-12-31"),
           ("2010-01-01", "2026-12-31"), ("2021-01-01", "2026-12-31")]


def load(t: str) -> pd.DataFrame:
    d = os.environ.get("DATA_DIR")
    if d and os.path.exists(os.path.join(d, f"{t}_max.pkl")):
        return pd.read_pickle(os.path.join(d, f"{t}_max.pkl"))
    import yfinance as yf
    df = yf.download(t, period="max", auto_adjust=True, progress=False)
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[["open", "high", "low", "close", "volume"]].dropna()


def backtest(df: pd.DataFrame, n: int = 20) -> tuple[pd.Series, list[dict]]:
    """Daily equity curve (marked at the close) and the list of trades."""
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    hi_n = pd.Series(h).rolling(n).max().shift(1).to_numpy()
    lo_n = pd.Series(lo).rolling(n).min().shift(1).to_numpy()
    eq = np.ones(len(c))
    cash, shares, pos, pend, trades, entry = 1.0, 0.0, False, None, [], None
    for i in range(len(c)):
        if pend == "buy":
            shares = cash * (1 - COST) / o[i]
            cash, pos = 0.0, True
            entry = (i, o[i])
        elif pend == "sell":
            cash = shares * o[i] * (1 - COST)
            trades.append({"in": df.index[entry[0]], "out": df.index[i], "days": i - entry[0],
                           "ret": o[i] * (1 - COST) / (entry[1] / (1 - COST)) - 1})
            shares, pos = 0.0, False
        pend = None
        eq[i] = cash + shares * c[i]
        if not pos and c[i] > hi_n[i]:
            pend = "buy"
        elif pos and c[i] < lo_n[i]:
            pend = "sell"
    if pos:                                  # open trade at the end: marked at the last close, not counted as closed
        trades.append({"in": df.index[entry[0]], "out": None, "days": len(c) - 1 - entry[0],
                       "ret": c[-1] * (1 - COST) / (entry[1] / (1 - COST)) - 1})
    return pd.Series(eq, index=df.index), trades


def stats(eq: pd.Series, trades: list[dict], a: str, b: str) -> dict:
    e = eq[(eq.index >= a) & (eq.index <= b)]
    if len(e) < 2:
        return {}
    r = e.pct_change().dropna()
    yrs = (e.index[-1] - e.index[0]).days / 365.25
    tr = [t for t in trades if pd.Timestamp(a) <= t["in"] <= pd.Timestamp(b) and t["out"] is not None]
    rr = np.array([t["ret"] for t in tr]) if tr else np.zeros(0)
    w, lz = rr[rr > 0], rr[rr <= 0]
    return {"CAGR": (e.iloc[-1] / e.iloc[0]) ** (1 / yrs) - 1, "max DD": float((e / e.cummax() - 1).min()),
            "Sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else np.nan,
            "trades": len(rr), "winrate": (rr > 0).mean() if len(rr) else np.nan,
            "PF": w.sum() / -lz.sum() if lz.sum() < 0 else np.nan,
            "avg trade": rr.mean() if len(rr) else np.nan, "avg win": w.mean() if len(w) else np.nan,
            "avg loss": lz.mean() if len(lz) else np.nan,
            "avg days": float(np.mean([t["days"] for t in tr])) if tr else np.nan}


def buy_hold(df: pd.DataFrame) -> pd.Series:
    c = df["close"]
    return c / c.iloc[0] * (1 - COST)


def random_timing(df: pd.DataFrame, trades: list[dict], a: str, b: str, runs: int = 1000, seed: int = 1) -> np.ndarray:
    """CAGR of `runs` random strategies: the same holding periods, non-overlapping, at random start dates in [a, b]."""
    d = df[(df.index >= a) & (df.index <= b)]
    o = d["open"].to_numpy(float)
    holds = [t["days"] for t in trades if pd.Timestamp(a) <= t["in"] <= pd.Timestamp(b) and t["out"] is not None]
    if not holds:
        return np.zeros(0)
    n, total = len(o), sum(holds)
    rng = np.random.default_rng(seed)
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    out = []
    for _ in range(runs):
        hs = rng.permutation(holds)
        gaps = rng.multinomial(n - 1 - total, np.ones(len(hs) + 1) / (len(hs) + 1))
        i, g = 0, 1.0
        for k, hd in enumerate(hs):
            i += gaps[k]
            j = min(i + hd, n - 1)
            g *= o[j] * (1 - COST) / (o[i] / (1 - COST))
            i = j
        out.append(g ** (1 / yrs) - 1)
    return np.array(out)


def main():
    xom, spy = load("XOM"), load("SPY")
    eq, trades = backtest(xom, 20)
    bh = buy_hold(xom)
    sp = buy_hold(spy)
    pc = lambda x: "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.1f}%"
    rows = []
    for a, b in PERIODS:
        s, sb = stats(eq, trades, a, b), stats(bh, [], a, b)
        ss = stats(sp, [], a, b) if pd.Timestamp(a) >= spy.index[0] - pd.Timedelta(days=40) else {}   # SPY from 1993
        rnd = random_timing(xom, trades, a, b)
        rows.append({"periode": f"{a[:4]}-{min(int(b[:4]), xom.index[-1].year)}", "trades": s["trades"],
                     "winrate": pc(s["winrate"]), "PF": f"{s['PF']:.2f}", "gem./trade": pc(s["avg trade"]),
                     "gem. winst / verlies": f"{pc(s['avg win'])} / {pc(s['avg loss'])}", "gem. dagen": f"{s['avg days']:.0f}",
                     "CAGR strategie": pc(s["CAGR"]), "max daling": pc(s["max DD"]), "Sharpe": f"{s['Sharpe']:.2f}",
                     "CAGR XOM kopen+houden": pc(sb["CAGR"]), "max daling XOM": pc(sb["max DD"]),
                     "CAGR SPY": pc(ss.get("CAGR")) if ss else "-",
                     "random timing: mediaan CAGR / % beter dan strategie":
                         f"{pc(float(np.median(rnd)))} / {(rnd >= s['CAGR']).mean() * 100:.0f}%" if len(rnd) else "-"})
    sens = []
    for nn in (10, 20, 55, 100):
        e2, t2 = backtest(xom, nn)
        for a, b in (PERIODS[0], PERIODS[3]):
            s2 = stats(e2, t2, a, b)
            sens.append({"kanaal": f"{nn} dagen", "periode": f"{a[:4]}-{xom.index[-1].year}", "trades": s2["trades"],
                         "winrate": pc(s2["winrate"]), "PF": f"{s2['PF']:.2f}", "CAGR": pc(s2["CAGR"]),
                         "max daling": pc(s2["max DD"])})
    in_mkt = sum(t["days"] for t in trades) / len(xom)
    last = trades[-1]
    status = (f"op dit moment LONG sinds {last['in'].date()} ({pc(last['ret'])})" if last["out"] is None
              else f"op dit moment FLAT (laatste verkoop {last['out'].date()})")
    txt = ("# Donchian 20-daagse breakout op XOM\n\n<!-- CONCLUSIE -->\n\n"
           "Regels (vooraf vastgelegd in `indicator_lab/xom_donchian.py`): kopen op de open na een slot boven het hoogste "
           "hoog van de vorige 20 dagen, verkopen op de open na een slot onder het laagste laag van de vorige 20 dagen; "
           f"alleen long; kosten 0,10% per kant; cash 0% rente. Data: Yahoo, gecorrigeerd voor splitsingen en dividend, "
           f"{xom.index[0].date()} .. {xom.index[-1].date()}. Tijd in de markt: {in_mkt * 100:.0f}%. Strategie {status}.\n\n"
           "## Resultaat\n\n" + pd.DataFrame(rows).to_markdown(index=False)
           + "\n\nRandom timing = 1.000 strategieën met precies dezelfde houdperiodes op willekeurige startdagen "
             "(zelfde tijd in de markt): als de breakout-timing iets toevoegt, moet de strategie beter zijn dan de meeste.\n\n"
             "## Gevoeligheid voor de kanaallengte (alleen ter controle, niets gekozen)\n\n"
           + pd.DataFrame(sens).to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
