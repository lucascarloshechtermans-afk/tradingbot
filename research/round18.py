"""Round 18: every reasonable technical alternative vs SPY (research/HYPOTHESES.md).
    python -m research.round18 r14.pkl r15.pkl etf.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.round15_data import members_at
from research.systems6 import stats, weight_returns

PERIODS = {"PRE": ("2006-01-01", "2010-12-31"), "DEV": ("2011-07-01", "2018-12-31"),
           "VAL": ("2019-01-01", "2022-12-31"), "OOS": ("2023-01-01", "2026-09-30")}
SECTORS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC"]
ETFS = ["SPY", "QQQ", "EFA", "IEF", "GLD"] + SECTORS


def load_etfs(path: str) -> dict:
    try:
        return pd.read_pickle(path)
    except FileNotFoundError:
        import yfinance as yf

        raw = yf.download(ETFS + ["^IRX"], start="2004-01-01", auto_adjust=True, progress=False, group_by="ticker")
        out = {"open": pd.DataFrame({t: raw[t]["Open"] for t in ETFS}),
               "close": pd.DataFrame({t: raw[t]["Close"] for t in ETFS}), "irx": raw["^IRX"]["Close"]}
        for k in ("open", "close"):
            out[k].index = pd.DatetimeIndex(out[k].index).tz_localize(None) if out[k].index.tz is not None else out[k].index
        pd.to_pickle(out, path)
        return out


def month_rows(dates: pd.DatetimeIndex) -> np.ndarray:
    m = pd.Series(dates.month, index=dates)
    return np.flatnonzero((m != m.shift(-1)).to_numpy())


def from_targets(targets: dict[int, dict[str, float]], cols: list[str], n: int) -> np.ndarray:
    """targets: month-end row -> {ticker: weight}; held until the next decision."""
    W = np.full((n, len(cols)), np.nan)
    idx = {t: j for j, t in enumerate(cols)}
    for r, tw in targets.items():
        w = np.zeros(len(cols))
        for t, x in tw.items():
            w[idx[t]] = x
        W[r] = w
    return pd.DataFrame(W).ffill().fillna(0).to_numpy()


def etf_strategies(e: dict) -> dict[str, pd.Series]:
    C, O = e["close"].sort_index(), e["open"].sort_index()
    dates = C.index[C.index >= "2005-01-01"]
    C, O = C.reindex(dates), O.reindex(dates)
    rf_d = (e["irx"].reindex(dates).ffill() / 100 / 252).fillna(0)
    rf = rf_d.to_numpy()
    rows = month_rows(dates)
    rows = rows[rows >= 260]
    m12_1 = C.shift(21) / C.shift(252) - 1
    m12 = C / C.shift(252) - 1
    tbill12 = (1 + rf_d).rolling(252).apply(np.prod, raw=True) - 1
    sma200 = C.rolling(200).mean()
    sma10m = C.rolling(210).mean()
    cols = list(C.columns)
    o, c = O.to_numpy(), C.to_numpy()
    n = len(dates)

    def run(targets, cost=0.0002):
        return pd.Series(weight_returns(from_targets(targets, cols, n), o, c, rf, cost), index=dates)

    T = {k: {} for k in ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "SPY")}
    for r in rows:
        live = [s for s in SECTORS if np.isfinite(m12_1.iloc[r][s])]
        top3 = sorted(live, key=lambda s: -m12_1.iloc[r][s])[:3]
        T["E1"][r] = {s: 1 / 3 for s in top3}
        T["E2"][r] = T["E1"][r] if C.iloc[r]["SPY"] > sma200.iloc[r]["SPY"] else {}
        best = "SPY" if m12.iloc[r]["SPY"] >= m12.iloc[r]["EFA"] else "EFA"
        T["E3"][r] = {best: 1.0} if m12.iloc[r][best] > tbill12.iloc[r] else {"IEF": 1.0}
        T["E4"][r] = {"QQQ" if m12_1.iloc[r]["QQQ"] >= m12_1.iloc[r]["SPY"] else "SPY": 1.0}
        T["E5"][r] = {a: 0.25 for a in ("SPY", "EFA", "IEF", "GLD") if C.iloc[r][a] > sma10m.iloc[r][a]}
        T["E6"][r] = {"QQQ": 1.0}
        T["E7"][r] = {"SPY": 0.6, "IEF": 0.4}
        T["SPY"][r] = {"SPY": 1.0}
    names = {"SPY": "SPY buy and hold", "E1": "E1 sector momentum top 3", "E2": "E2 E1 + SPY 200d filter",
             "E3": "E3 dual momentum (GEM)", "E4": "E4 QQQ/SPY momentum switch", "E5": "E5 asset-class trend (Faber)",
             "E6": "E6 QQQ buy and hold", "E7": "E7 60/40 SPY/IEF"}
    return {names[k]: run(v) for k, v in T.items()}


def stock_strategies(r14: str, r15: str) -> dict[str, pd.Series]:
    d, m = pd.read_pickle(r14), pd.read_pickle(r15)
    spy = d["spy"]["close"]
    dates = spy.index[spy.index >= "2010-01-01"]
    C = d["close"].reindex(dates).astype(float)
    O = d["open"].reindex(dates).astype(float)
    V = d["volume"].reindex(dates).astype(float)
    for t, df in m["extra"].items():
        df.index = pd.DatetimeIndex(df.index).tz_localize(None) if df.index.tz is not None else df.index
        C[t], O[t], V[t] = (df[k].reindex(dates).astype(float) for k in ("Close", "Open", "Volume"))
    rf = (d["irx"].reindex(dates).ffill() / 100 / 252).fillna(0).to_numpy()
    dv = (C * V).rolling(20, min_periods=20).mean()
    ok = ((C.notna().cumsum() >= 253) & (dv >= 10e6) & (C >= 5)).to_numpy()
    s12 = (C.shift(21) / C.shift(252) - 1).to_numpy()
    s6 = (C.shift(21) / C.shift(126) - 1).to_numpy()
    spy_c = spy.reindex(dates)
    bull = (spy_c > spy_c.rolling(200).mean()).to_numpy()
    rows = month_rows(dates)
    rows = rows[rows >= 260]
    col = {t: j for j, t in enumerate(C.columns)}
    mem = {r: [col[t] for t in members_at(m["base"], m["changes"], dates[r]) if t in col] for r in rows}
    o, c = O.to_numpy(), C.to_numpy()

    def book(score, top, use_filter=True):
        W = np.full(c.shape, np.nan)
        for r in rows:
            w = np.zeros(c.shape[1])
            if bull[r] or not use_filter:
                cand = [j for j in mem[r] if ok[r, j] and (score is None or np.isfinite(score[r, j]))]
                if score is not None:
                    cand = sorted(cand, key=lambda j: -score[r, j])[:top]
                if cand:
                    w[cand] = 1 / len(cand)
            W[r] = w
        return pd.Series(weight_returns(pd.DataFrame(W).ffill().fillna(0).to_numpy(), o, c, rf, 0.001), index=dates)

    return {"M4 momentum top 50 (PIT S&P 500)": book(s12, 50), "M5 6-1 momentum top 20 (PIT)": book(s6, 20),
            "M6 equal weight all members (PIT)": book(None, None, use_filter=False)}


def main(r14: str, r15: str, etf_path: str) -> int:
    books = etf_strategies(load_etfs(etf_path))
    books.update(stock_strategies(r14, r15))
    spy = books["SPY buy and hold"]
    ref = {p: stats(spy[(spy.index >= a) & (spy.index <= b)])["sharpe"] for p, (a, b) in PERIODS.items()}
    print("CAGR / maxDD / Sharpe per period; verdict vs SPY Sharpe in DEV, VAL, OOS")
    for name, r in books.items():
        line, wins = f"{name:<36}", 0
        for p, (a, b) in PERIODS.items():
            s = stats(r[(r.index >= a) & (r.index <= b)])
            if p == "PRE" and name.startswith("M"):   # stock data starts in 2010: no positions before
                s = {}
            if not s:
                line += f" | {p} {'-':>18}"
                continue
            line += f" | {p} {s['CAGR'] * 100:5.1f}% {s['maxDD'] * 100:4.0f}% {s['sharpe']:4.2f}"
            if p != "PRE" and name != "SPY buy and hold" and s["sharpe"] > ref[p]:
                wins += 1
        verdict = "" if name == "SPY buy and hold" else (
            "BEATS SPY" if wins == 3 else "possible (2/3)" if wins == 2 else f"no ({wins}/3)")
        print(line + f" | {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
