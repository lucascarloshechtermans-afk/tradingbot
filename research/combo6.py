"""Round 6 combinations: momentum book, dip book and index RSI(2) sleeve, blended.
python research/combo6.py SCRATCH_DIR"""

import sys
import pandas as pd
import numpy as np
from research.engine2 import build_panel, simulate_rules
from research.hypotheses4 import indicators, signals
from research.portfolio4 import run_portfolio
from research.systems6 import weight_returns, rsi, stats
from research.stock_systems6 import hold_monthly

S = sys.argv[1]  # scratch dir holding big.pkl and etf.pkl
p = build_panel(pd.read_pickle(S + "/big.pkl"))
etf = pd.read_pickle(S + "/etf.pkl")
rf = (etf["^IRX"]["close"].reindex(p.dates).ffill() / 100 / 252).fillna(0).to_numpy()
C = p.df(p.c)
spy = p.bench["SPY"]["close"].reindex(p.dates)
bull = (spy > spy.rolling(200).mean()).to_numpy()
me = (pd.Series(p.dates.month, index=p.dates) != pd.Series(p.dates.month, index=p.dates).shift(-1)).to_numpy()
mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))


# index RSI2 sleeve: 4 ETFs, each 25% when in trade
def rsi2_sleeve():
    W = []
    O = []
    CC = []
    for t in ("SPY", "QQQ", "IWM", "DIA"):
        c = etf[t]["close"].reindex(p.dates)
        o = etf[t]["open"].reindex(p.dates)
        r2 = rsi(c)
        s5 = c.rolling(5).mean()
        s200 = c.rolling(200).mean()
        pos = np.zeros(len(p.dates))
        inpos = False
        for i in range(len(p.dates)):
            if not inpos and c.iloc[i] > s200.iloc[i] and r2.iloc[i] < 10:
                inpos = True
            elif inpos and c.iloc[i] > s5.iloc[i]:
                inpos = False
            pos[i] = inpos
        W.append(pos * 0.25)
        O.append(o.to_numpy())
        CC.append(c.to_numpy())
    return pd.Series(weight_returns(np.column_stack(W), np.column_stack(O), np.column_stack(CC), rf), index=p.dates)


def rsi2_sleeve_full():  # 100% of the sleeve into whichever are triggered, split equally
    W = []
    O = []
    CC = []
    for t in ("SPY", "QQQ", "IWM", "DIA"):
        c = etf[t]["close"].reindex(p.dates)
        o = etf[t]["open"].reindex(p.dates)
        r2 = rsi(c)
        s5 = c.rolling(5).mean()
        s200 = c.rolling(200).mean()
        pos = np.zeros(len(p.dates))
        inpos = False
        for i in range(len(p.dates)):
            if not inpos and c.iloc[i] > s200.iloc[i] and r2.iloc[i] < 10:
                inpos = True
            elif inpos and c.iloc[i] > s5.iloc[i]:
                inpos = False
            pos[i] = inpos
        W.append(pos)
        O.append(o.to_numpy())
        CC.append(c.to_numpy())
    W = np.column_stack(W)
    n = W.sum(1, keepdims=True)
    W = np.where(n > 0, W / np.maximum(n, 1), 0)
    return pd.Series(weight_returns(W, np.column_stack(O), np.column_stack(CC), rf), index=p.dates)


def mom_book(cols, top=20, filt=True):
    rk = mom.loc[:, cols].rank(axis=1, ascending=False)
    pick = rk <= top
    w = pick.astype(float).div(pick.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    if filt:
        w = w.mul(bull.astype(float), axis=0)
    return pd.Series(weight_returns(hold_monthly(w, me), p.o[:, cols], p.c[:, cols], rf), index=p.dates)


def dip_book(half):
    I = indicators(p)
    sig = signals(p, I)
    tr = simulate_rules(p, sig["H01 LEADER_DIP"], stop_atr=2.5, max_hold=10)
    tr = tr[p.half[tr.j.to_numpy()] == half].copy()
    tr["prio"] = I["mom_rank"].to_numpy()[tr.t.to_numpy(), tr.j.to_numpy()]
    tr["risk_mult"] = np.where(bull[tr.t.to_numpy()], 1.0, 0.5)
    res = run_portfolio(
        p, tr, stop_atr=2.5, risk_pct=1.0, max_positions=10, priority="prio", date_mask=p.dates >= "2008-06-01"
    )
    e = res["curve"].reindex(p.dates).ffill()
    return e.pct_change().fillna(0)


P = {"2008-2021": ("2008-06-01", "2021-12-31"), "2022-2026": ("2022-01-01", "2026-12-31")}


def show(name, r):
    line = f"{name:<44}"
    for k, (a, b) in P.items():
        s = stats(r[(r.index >= a) & (r.index <= b)])
        line += f" | {k}: {s['CAGR'] * 100:5.1f}% DD {s['maxDD'] * 100:4.1f}% Sh {s['sharpe']:.2f} worst {s['worst_yr'] * 100:5.1f}%"
    print(line, flush=True)


spyr = pd.Series(
    weight_returns(
        np.ones((len(p.dates), 1)),
        p.bench["SPY"]["open"].reindex(p.dates).to_numpy()[:, None],
        spy.to_numpy()[:, None],
        rf,
    ),
    index=p.dates,
)
show("SPY buy & hold", spyr)
r4 = rsi2_sleeve()
rf4 = rsi2_sleeve_full()
show("Index RSI2 (25% per ETF)", r4)
show("Index RSI2 (100% split over triggered)", rf4)
for half, lab in ((1, "research"), (0, "holdout")):
    cols = p.half == half
    m = mom_book(cols)
    d = dip_book(half)
    print(
        f"-- {lab} half; corr(mom, dip) {m.corr(d):.2f}, corr(mom, rsi2) {m.corr(rf4):.2f}, corr(dip, rsi2) {d.corr(rf4):.2f}"
    )
    show(f"A momentum top20 >200d [{lab}]", m)
    show(f"B dip scanner 1% risk N/H [{lab}]", d)
    show(f"A+B 50/50 [{lab}]", 0.5 * m + 0.5 * d)
    show(f"A 70% + RSI2 30% [{lab}]", 0.7 * m + 0.3 * rf4)
    show(f"B 70% + RSI2 30% [{lab}]", 0.7 * d + 0.3 * rf4)
    show(f"A 40 / B 40 / RSI2 20 [{lab}]", 0.4 * m + 0.4 * d + 0.2 * rf4)
