"""The v4 breakout on the 4-HOUR timeframe, as the user asked: at most 2 BUY signals per week per stock and a profit
target of +10 / +15 / +20% (vs none), against v4 on daily bars and SPY over the same period.

    python -m indicator_lab.h4.test4h

Data: Yahoo 60-minute bars (the last ~730 days only), adjusted, grouped into TradingView's 4H bars for US stocks:
09:30-13:30 and 13:30-16:00 (two bars a day). Cache: indicator_lab/.cache4h (gitignored).
Signal on a 4H close: close > highest high of the prior 20 bars, close > SMA200 (4H), close in the top 30% of the bar
(IBS >= 0.7), and the v4 regime rule on DAILY SPY (63-day return <= 3%, previous day's close). The daily quality model
is left out: it was trained on daily features. Exits as v4 on 4H bars (protective stop fill - 4 x ATR, 4 x ATR chandelier
trail, close < prior 20-bar low -> next open) plus the profit target. Fills: next bar's open; costs 0.1% per side +
0.1% entry slippage. Portfolio: at most 10 positions of 10%, idle cash 0%, mean of 20 random orders.
"""
from __future__ import annotations

import os
from dataclasses import replace

import numpy as np
import pandas as pd

from indicator_lab.swing4 import protocol as P4

P4.install_final()   # full daily data (this test only uses development tickers)

from indicator_lab import ind
from indicator_lab.evaluate import get
from indicator_lab.metrics import equity_stats
from indicator_lab.swing4 import lab as L
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.swing5 import protocol5 as P5

CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache4h")
OUT = os.path.join(os.path.dirname(__file__), "reports")
NASDAQ = os.environ.get("H4_UNIV") == "nasdaq"
if NASDAQ:
    from indicator_lab.h4.nasdaq_list import nasdaq
    UNIV = nasdaq()
else:
    UNIV = P5.DEV_UNIVERSE
SUFFIX = "_nasdaq" if NASDAQ else ""
SLIP = 0.001
SEEDS = 20
BASE = S2.Policy(max_week=2)


def download(tickers, batch=80):
    import yfinance as yf
    os.makedirs(CACHE, exist_ok=True)
    todo = [t for t in tickers if not os.path.exists(os.path.join(CACHE, f"{t}.csv.gz"))]
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        raw = yf.download(chunk, period="730d", interval="60m", auto_adjust=True, progress=False, group_by="ticker",
                          threads=True)
        for t in chunk:
            try:
                df = raw[t].rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
            except KeyError:
                continue
            if len(df) > 500:
                df.to_csv(os.path.join(CACHE, f"{t}.csv.gz"), compression="gzip")
        print(f"download {min(i + batch, len(todo))}/{len(todo)}", flush=True)


def bars4h(t) -> pd.DataFrame | None:
    p = os.path.join(CACHE, f"{t}.csv.gz")
    if not os.path.exists(p):
        return None
    h = pd.read_csv(p, index_col=0)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("America/New_York").tz_localize(None)
    h = h[(h.index.time >= pd.Timestamp("09:30").time()) & (h.index.time < pd.Timestamp("16:00").time())]
    second = h.index.time >= pd.Timestamp("13:30").time()
    key = h.index.normalize() + pd.to_timedelta(np.where(second, 13.5, 9.5), unit="h")
    g = h.groupby(key)
    return pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                         "close": g["close"].last(), "volume": g["volume"].sum()}).dropna()


def regime_on(idx: pd.DatetimeIndex) -> np.ndarray:
    """v4 regime rule from DAILY SPY: 63-day return <= 3%, known from the previous trading day's close."""
    spy = get("SPY")["close"]
    roc = (spy / spy.shift(63) - 1).shift(1)
    return (roc.reindex(idx.normalize(), method="ffill").to_numpy() <= 0.03)


def context():
    ctx = {}
    for t in UNIV:
        df = bars4h(t)
        if df is None or len(df) < 400:
            continue
        c = df["close"]
        a = ind.atr(df, 14).to_numpy()
        hi = df["high"].rolling(20).max().shift(1)
        rng = (df["high"] - df["low"]).replace(0, np.nan)
        ibs = ((c - df["low"]) / rng).fillna(0.5)
        with np.errstate(invalid="ignore"):
            entry = ((c > hi) & (c > ind.sma(c, 200)) & (ibs >= 0.7)).to_numpy() & regime_on(df.index)
        exit_sig = (c < df["low"].rolling(20).min().shift(1)).to_numpy()
        ctx[t] = {"arr": S2.arrays(df, a, exit_sig, {"hi_n": hi.to_numpy()}), "entry": entry}
    return ctx


def run(ctx, pol):
    res = {}
    for t, cx in ctx.items():
        r, tr = S2.simulate(cx["arr"], cx["entry"], pol, slip=SLIP)
        for x in tr:
            x["ticker"] = t
        res[t] = (pd.Series(r, index=cx["arr"]["index"]), tr)
    return res


def daily(port4h: pd.Series) -> pd.Series:
    return (1 + port4h).groupby(port4h.index.normalize()).prod() - 1


def summary(name, res, weeks, k=10):
    tt = pd.DataFrame([x for _, tr in res.values() for x in tr])
    ports = [daily(L.portfolio(res, k, s)["port"]) for s in range(SEEDS)]
    st = [equity_stats(p) for p in ports]
    m = {k: float(np.mean([s[k] for s in st])) for k in ("cagr", "maxdd", "mar", "sharpe")}
    r = tt["ret"].to_numpy()
    win, loss = r[r > 0], r[r <= 0]
    top = np.sort(r)[::-1]
    return {"systeem": name if k == 10 else f"{name} ({k} posities)", "trades": len(r),
            "trades/week (alle aandelen)": round(len(r) / weeks, 1),
            "mediaan trade": f"{np.median(r) * 100:.2f}%", "PF": f"{win.sum() / -loss.sum():.2f}",
            "beste 1% = % van winst": f"{top[:max(1, len(r) // 100)].sum() / r.sum() * 100:.0f}%",
            "winrate": f"{(r > 0).mean() * 100:.0f}%", "gem. winst": f"{win.mean() * 100:.1f}%",
            "gem. verlies": f"{loss.mean() * 100:.1f}%", "gem. trade": f"{r.mean() * 100:.2f}%",
            "hold (4H-bars)": round(float(tt["bars"].mean()), 1),
            "target geraakt": f"{(tt['reason'] == 'target').mean() * 100:.0f}%",
            "CAGR": f"{m['cagr'] * 100:.1f}%", "max DD": f"{m['maxdd'] * 100:.1f}%", "Sharpe": f"{m['sharpe']:.2f}",
            "MAR": f"{m['mar']:.2f}"}, ports[0]


def v4_daily(start, end):
    ctx = L.load_ctx(rebuild=True, univ=UNIV, path=os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "h4_v4daily.pkl"))
    res = L.run(ctx, lambda cx: L.v3_entry(cx) & (np.nan_to_num(cx["x"]["spy_roc63"], nan=9) <= 0.03),
                univ=list(ctx), period=(start, end), slip=SLIP)
    tt = pd.DataFrame([x for _, tr in res.values() for x in tr])
    ports = [L.portfolio(res, 10, s)["port"] for s in range(SEEDS)]
    st = [equity_stats(p) for p in ports]
    m = {k: float(np.mean([s[k] for s in st])) for k in ("cagr", "maxdd", "mar", "sharpe")}
    r = tt["ret"].to_numpy()
    return {"systeem": "v4 op dagbars (met model)", "trades": len(r), "winrate": f"{(r > 0).mean() * 100:.0f}%",
            "gem. winst": f"{r[r > 0].mean() * 100:.1f}%", "gem. verlies": f"{r[r <= 0].mean() * 100:.1f}%",
            "gem. trade": f"{r.mean() * 100:.2f}%", "CAGR": f"{m['cagr'] * 100:.1f}%", "max DD": f"{m['maxdd'] * 100:.1f}%",
            "Sharpe": f"{m['sharpe']:.2f}", "MAR": f"{m['mar']:.2f}"}


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    download(UNIV + ["SPY"])
    ctx = context()
    idx = pd.DatetimeIndex(sorted({d for cx in ctx.values() for d in cx["arr"]["index"]}))
    start, end = idx[300].normalize(), idx[-1].normalize()   # first ~150 days are SMA200 warm-up
    for cx in ctx.values():   # signals only after the warm-up, the same window for every variant
        cx["entry"] = cx["entry"] & (cx["arr"]["index"] >= start)
    weeks = (end - start).days / 7
    rows, curves = [], {}
    for name, pol in (("4H, max 2/week, geen target", BASE), ("4H, max 2/week, target +10%", replace(BASE, tgt_pct=0.10)),
                      ("4H, max 2/week, target +15%", replace(BASE, tgt_pct=0.15)),
                      ("4H, max 2/week, target +20%", replace(BASE, tgt_pct=0.20)),
                      ("4H, zonder week-limiet, geen target", S2.Policy())):
        res = run(ctx, pol)
        for k in ((10, 20) if NASDAQ else (10,)):
            row, curve = summary(name, res, weeks, k)
            rows.append(row)
            curves[row["systeem"]] = curve
            print(row, flush=True)
    if not NASDAQ:   # the NASDAQ daily comparison is nasdaq_daily.py
        rows.append(v4_daily(start, end))
    spy = get("SPY")["close"].pct_change()
    spy = spy[(spy.index >= start) & (spy.index <= end)].fillna(0)
    s = equity_stats(spy)
    rows.append({"systeem": "SPY kopen en vasthouden", "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                 "Sharpe": f"{s['sharpe']:.2f}", "MAR": f"{s['mar']:.2f}"})
    curves["SPY"] = spy
    d = pd.DataFrame(rows).fillna("–")
    os.makedirs(OUT, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for k, r in curves.items():
        ax.plot((1 + r).cumprod(), label=k)
    ax.legend(fontsize=8)
    ax.set_title(f"4H-varianten vs SPY, {start.date()} .. {end.date()} (één willekeurige volgorde)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"test4h{SUFFIX}.png"), dpi=100)
    txt = (f"# v4-breakout op 4H — jouw regels getest\n\nPeriode {start.date()} .. {end.date()} ({weeks:.0f} weken), "
           f"{len(ctx)} {'NASDAQ-aandelen' if NASDAQ else 'ontwikkelaandelen (geen holdout)'}, Yahoo-uurdata gegroepeerd tot 4H. Kosten 0,1%/kant + 0,1% "
           f"slippage op instappen, max 10 posities van 10%, lege kas 0%.\n\n{d.to_markdown(index=False)}\n\n"
           f"![equity](test4h{SUFFIX}.png)\n")
    with open(os.path.join(OUT, f"test4h{SUFFIX}.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
