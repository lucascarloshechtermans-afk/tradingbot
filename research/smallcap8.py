"""Round 8: does adding S&P 600 small caps priced >= $50 help the momentum book
and the leader breakouts?   python -m research.smallcap8 BIG.pkl SMALL.pkl ETF.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import build_panel
from research.stock_systems6 import hold_monthly
from research.systems6 import fmt, weight_returns
from research.trend_systems6 import donchian_trades, report

P2 = {"2008-2021": ("2008-06-01", "2021-12-31"), "2022-2026": ("2022-01-01", "2026-12-31")}


def main(big_path: str, small_path: str, etf_path: str, min_small: float = 50.0) -> int:
    big, small = pd.read_pickle(big_path), pd.read_pickle(small_path)
    small_names = set(small["stocks"]) - set(big["stocks"])
    merged = {"stocks": {**big["stocks"], **{t: small["stocks"][t] for t in small_names}}, "bench": big["bench"],
              "sectors": {**big["sectors"], **{t: small["sectors"].get(t) for t in small_names}},
              "half": {**big["half"], **{t: small["half"][t] for t in small_names}}}
    p = build_panel(merged)
    etf = pd.read_pickle(etf_path)
    rf = (etf["^IRX"]["close"].reindex(p.dates).ffill() / 100 / 252).fillna(0).to_numpy()
    is_small = np.array([t in small_names for t in p.tickers])
    C = p.df(p.c)
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    me = (pd.Series(p.dates.month, index=p.dates) != pd.Series(p.dates.month, index=p.dates).shift(-1)).to_numpy()
    base_elig = p.df(p.eligible)
    price_ok = (C >= min_small) | ~pd.Series(is_small, index=p.tickers)
    variants = {"large+mid only": base_elig & ~pd.Series(is_small, index=p.tickers),
                f"+ small caps >= ${min_small:.0f}": base_elig & price_ok,
                "+ all small caps (>= $5)": base_elig}
    print("share of small caps among eligible stocks >= $50 today:",
          f"{(base_elig & price_ok).iloc[-1][is_small].sum()} of {base_elig.iloc[-1][is_small].sum()}")
    for half, lab in ((1, "research"), (0, "holdout")):
        cols = p.half == half
        print(f"\n=== MOMENTUM TOP 20, SPY>200d, {lab} half")
        for name, el in variants.items():
            mom = (C.shift(21) / C.shift(252) - 1).where(el).loc[:, cols]
            pick = mom.rank(axis=1, ascending=False) <= 20
            w = pick.astype(float).div(pick.sum(axis=1).replace(0, np.nan), axis=0).fillna(0).mul(bull.astype(float), axis=0)
            r = pd.Series(weight_returns(hold_monthly(w, me), p.o[:, cols], p.c[:, cols], rf), index=p.dates)
            share = (pick & pd.DataFrame(is_small[cols][None, :].repeat(len(p.dates), 0), index=p.dates, columns=pick.columns)).sum(axis=1)
            print(fmt(name, r, P2, extra=f"  avg small caps in list {share[me & (p.dates >= '2008-06-01')].mean():.1f}"), flush=True)
    print("\n=== LEADER BREAKOUT (top 50 leaders, 50d breakout, trailing exit), one account 0.5% risk max 20")
    I_c, I_v = C, p.df(p.v)
    for name, el in variants.items():
        mom = (C.shift(21) / C.shift(252) - 1).where(el)
        top50 = (mom.rank(axis=1, ascending=False) <= 50).to_numpy()
        hi50 = I_c.rolling(50).max().shift(1)
        b1 = ((I_c > hi50) & (I_c.shift(1) <= hi50.shift(1))).fillna(False).to_numpy() & top50 & bull[:, None]
        tr = donchian_trades(p, b1)
        tr["prio"] = -np.nan_to_num(mom.to_numpy()[tr.t.to_numpy(), tr.j.to_numpy()])
        print(f"-- {name}: {len(tr)} trades, mean R {tr.r.mean():+.3f}", flush=True)
        report(p, name, tr, risk=0.5, maxpos=20, stop_atr=2.5)
    del I_v
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
