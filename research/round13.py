"""Round 13: resistance room and chart patterns as filters for momentum picks
and leader breakouts (research/HYPOTHESES.md).
    python -m research.round13 BIG.pkl OUT.pkl"""
from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from analysis.chart_read import find_zones
from analysis.patterns import detect_patterns
from research.breakout7 import cell_of
from research.engine2 import build_panel
from research.trend_systems6 import donchian_trades

_FRAMES: dict = {}


def _init(frames):
    global _FRAMES
    _FRAMES = frames


def features(args):
    ticker, date = args
    df = _FRAMES[ticker]
    d = df[df.index <= date].iloc[-520:]
    if len(d) < 120:
        return ticker, date, np.nan, np.nan, np.nan
    close = float(d["close"].iloc[-1])
    tr = pd.concat([d["high"] - d["low"], (d["high"] - d["close"].shift()).abs(), (d["low"] - d["close"].shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    try:
        zones = find_zones(d)
    except Exception:  # noqa: BLE001
        zones = []
    above = [z.low for z in zones if z.low > close]
    room = (min(above) - close) / atr if above and atr > 0 else np.inf
    try:
        hits = detect_patterns(d)
    except Exception:  # noqa: BLE001
        hits = []
    pat = any((h.broke_out_today or 0 <= (h.trigger - close) / close <= 0.05) and h.invalidation < close for h in hits)
    return ticker, date, room, float(pat), atr


def main(path: str, out: str) -> int:
    big = pd.read_pickle(path)
    p = build_panel(big)
    frames = {t: big["stocks"][t][["open", "high", "low", "close"]] for t in p.tickers}
    C = p.df(p.c)
    mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    months = pd.Series(p.dates.month, index=p.dates)
    me = np.flatnonzero((months != months.shift(-1)).to_numpy())
    # (a) momentum picks
    picks = []
    for k in range(len(me) - 1):
        r, nxt = me[k], me[k + 1]
        if p.dates[r] < pd.Timestamp("2008-06-01") or not bull[r]:
            continue
        for half in (1, 0):
            cols = np.flatnonzero(p.half == half)
            sc = mom.iloc[r, cols].dropna().sort_values(ascending=False).iloc[:20]
            for t, _m in sc.items():
                j = p.tickers.index(t)
                ret = p.c[nxt, j] / p.c[r, j] - 1
                if np.isfinite(ret):
                    picks.append((t, p.dates[r], half, ret))
    pk = pd.DataFrame(picks, columns=["ticker", "date", "half", "ret"])
    pk["xret"] = pk.ret - pk.groupby(["date", "half"]).ret.transform("mean")
    # (b) leader breakouts
    top50 = (mom.rank(axis=1, ascending=False) <= 50).to_numpy()
    hi = C.rolling(50).max().shift(1)
    sig = ((C > hi) & (C.shift(1) <= hi.shift(1))).fillna(False).to_numpy() & top50 & bull[:, None]
    bo = donchian_trades(p, sig)
    bo["cell"] = cell_of(p, bo)
    bo["ticker"] = [p.tickers[j] for j in bo.j]
    bo["date"] = p.dates[bo.t.to_numpy()]
    jobs = list({(t, d) for t, d in zip(pk.ticker, pk.date)} | {(t, d) for t, d in zip(bo.ticker, bo.date)})
    print(f"{len(pk)} momentum picks, {len(bo)} breakouts, {len(jobs)} chart analyses", flush=True)
    with ProcessPoolExecutor(4, initializer=_init, initargs=(frames,)) as ex:
        res = list(ex.map(features, jobs, chunksize=200))
    f = pd.DataFrame(res, columns=["ticker", "date", "room", "pattern", "atr"])
    pk = pk.merge(f, on=["ticker", "date"], how="left")
    bo = bo.merge(f, on=["ticker", "date"], how="left")
    pk["cell"] = np.select([(pk.half == 1) & (pk.date < "2022"), (pk.half == 1), (pk.date < "2022")],
                           ["DEV", "VAL-T", "VAL-U"], "FINAL")
    pd.to_pickle({"picks": pk, "breakouts": bo}, out)
    groups = {"AT_RESISTANCE (room <= 1 ATR)": lambda d: d.room <= 1,
              "room 1-3 ATR": lambda d: (d.room > 1) & (d.room <= 3),
              "OPEN_SKY (no zone above)": lambda d: np.isinf(d.room),
              "PATTERN near/at trigger": lambda d: d.pattern == 1}
    for name, d, y in (("MOMENTUM PICKS -- next-month return minus the month's pick average (%)", pk, "xret"),
                       ("LEADER BREAKOUTS -- R per trade", bo, "r")):
        print(f"\n{name}")
        for g, fn in groups.items():
            line = f"  {g:<32}"
            for cell in ("DEV", "VAL-T", "VAL-U", "FINAL"):
                x = d[d.cell == cell]
                m = fn(x)
                a, b = x.loc[m, y], x.loc[~m, y]
                if len(a) < 20:
                    line += f" | {cell} n={len(a)}"
                    continue
                scale = 100 if y == "xret" else 1
                diff = (a.mean() - b.mean()) * scale
                t = (a.mean() - b.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b))
                line += f" | {cell} n={len(a):>4} {a.mean() * scale:+.2f} vs {b.mean() * scale:+.2f} diff {diff:+.2f} t {t:+.1f}"
            print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
