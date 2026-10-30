"""Backtest of the plan exactly as configured in the scanner (defaults):
50% MOMENTUM TOP 20 (month-end, 12-1 return, SPY > 200d) + 50% LEADER BREAKOUT
(top-50 leader, first close above the 50-day closing high, SPY > 200d, bought at
the close, 2.5 ATR stop, 20-day trailing exit, 1% risk of the sleeve, max 20).
Universe: S&P 500 + 400 + scanner list + S&P 600 small caps priced >= $50.
Next-open / close fills with 0.05% slippage per side plus commissions; idle cash
earns T-bills.   python -m research.final_backtest BIG.pkl SMALL.pkl ETF.pkl OUT_DIR"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import build_panel
from research.portfolio4 import run_portfolio
from research.round10 import momentum_weights
from research.systems6 import stats, weight_returns
from research.trend_systems6 import donchian_trades


def main(big_path: str, small_path: str, etf_path: str, out_dir: str, min_small: float = 50.0) -> int:
    big, small = pd.read_pickle(big_path), pd.read_pickle(small_path)
    extra = set(small["stocks"]) - set(big["stocks"])
    merged = {"stocks": {**big["stocks"], **{t: small["stocks"][t] for t in extra}}, "bench": big["bench"],
              "sectors": {**big["sectors"], **{t: small["sectors"].get(t) for t in extra}},
              "half": {**big["half"], **{t: small["half"][t] for t in extra}}}
    p = build_panel(merged)
    is_small = np.array([t in extra for t in p.tickers])
    p.eligible &= ~(is_small[None, :] & (p.c < min_small))      # small caps only at >= $50
    etf = pd.read_pickle(etf_path)
    rf = (etf["^IRX"]["close"].reindex(p.dates).ffill() / 100 / 252).fillna(0).to_numpy()
    C = p.df(p.c)
    mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    vol = C.pct_change().rolling(63).std()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    months = pd.Series(p.dates.month, index=p.dates)
    me = np.flatnonzero((months != months.shift(-1)).to_numpy())
    start = "2008-06-01"
    allcols = np.ones(len(p.tickers), bool)

    # momentum sleeve
    W = momentum_weights(p, allcols, mom, vol, bull, me)
    mom_r = pd.Series(weight_returns(W, p.o, p.c, rf), index=p.dates)

    # breakout sleeve
    top50 = (mom.rank(axis=1, ascending=False) <= 50).to_numpy()
    hi = C.rolling(50).max().shift(1)
    sig = ((C > hi) & (C.shift(1) <= hi.shift(1))).fillna(False).to_numpy() & top50 & bull[:, None]
    tr = donchian_trades(p, sig, entry_at="close")
    tr["prio"] = -np.nan_to_num(mom.to_numpy()[tr.t.to_numpy(), tr.j.to_numpy()])
    res = run_portfolio(p, tr, stop_atr=2.5, risk_pct=1.0, max_positions=20, priority="prio",
                        date_mask=p.dates >= start)
    bo_curve = res["curve"].reindex(p.dates).ffill()
    bo_r = bo_curve.pct_change().fillna(0)

    plan = 0.5 * mom_r + 0.5 * bo_r                     # rebalanced daily to 50/50 (approx. monthly in practice)
    spy_o = p.bench["SPY"]["open"].reindex(p.dates).to_numpy()[:, None]
    spy_r = pd.Series(weight_returns(np.ones((len(p.dates), 1)), spy_o, spy.to_numpy()[:, None], rf), index=p.dates)
    series = {"PLAN 50/50": plan, "momentum sleeve": mom_r, "breakout sleeve": bo_r, "SPY buy & hold": spy_r}
    series = {k: v[v.index >= start] for k, v in series.items()}

    print("PERIOD STATS (CAGR / max drawdown / Sharpe / worst year / % years up)")
    for per, (a, b) in {"2008-06 .. 2026-09": (start, "2026-12-31"), "2008-2021": (start, "2021-12-31"),
                        "2022-2026": ("2022-01-01", "2026-12-31")}.items():
        print(f"  {per}")
        for k, r in series.items():
            s = stats(r[(r.index >= a) & (r.index <= b)])
            print(f"    {k:<18} {s['CAGR'] * 100:6.1f}%  DD {s['maxDD'] * 100:5.1f}%  Sh {s['sharpe']:.2f}  "
                  f"worst {s['worst_yr'] * 100:6.1f}%  up {s['yrs_pos'] * 100:3.0f}%")
    yearly = pd.DataFrame({k: (1 + r).groupby(r.index.year).prod() - 1 for k, r in series.items()}) * 100
    print("\nYEARLY RETURNS (%)")
    print(yearly.round(1).to_string())
    e = (1 + series["PLAN 50/50"]).cumprod()
    dd = 1 - e / e.cummax()
    trough = dd.idxmax()
    peak = e[:trough].idxmax()
    rec = e[trough:][e[trough:] >= e[peak]]
    print(f"\nWORST DRAWDOWN: {dd.max() * 100:.1f}% from {peak.date()} to {trough.date()}, "
          f"recovered {rec.index[0].date() if len(rec) else 'not yet'}")
    under = (dd > 0.10).astype(int)
    b = tr[p.dates[tr.t.to_numpy()] >= start]
    yrs = (p.dates[-1] - pd.Timestamp(start)).days / 365.25
    print(f"\nBREAKOUTS: {len(b)} signals ({len(b) / yrs / 52:.1f}/week), taken by the account {res['trades']} "
          f"({res['trades'] / yrs / 52:.1f}/week); win {(b.r > 0).mean() * 100:.0f}%, avg winner {b.r[b.r > 0].mean():+.2f}R, "
          f"avg loser {b.r[b.r <= 0].mean():+.2f}R, avg R {b.r.mean():+.3f}, median hold {np.median(b.exit_t - b.t):.0f} sessions, "
          f"avg open positions {res['avg_open']:.1f}")
    small_share = (W[:, is_small].sum(1) / np.maximum(W.sum(1), 1e-9))[p.dates >= start]
    print(f"MOMENTUM: avg names from the small caps {small_share[W.sum(1)[p.dates >= start] > 0].mean() * 20:.1f} of 20; "
          f"invested {100 * (W.sum(1)[p.dates >= start] > 0).mean():.0f}% of the time; days with plan >10% under water: "
          f"{under.mean() * 100:.0f}%")
    out = pd.DataFrame({k: (1 + v).cumprod() for k, v in series.items()})
    out["plan_drawdown"] = -dd
    out.to_csv(f"{out_dir}/final_backtest_equity.csv")
    yearly.to_csv(f"{out_dir}/final_backtest_yearly.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
