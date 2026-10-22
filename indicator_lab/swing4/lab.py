"""Phase 2 harness of the swing v4 round: precomputed per-ticker context, variant runs, a portfolio with ranking and
sizing, and the acceptance checks of the protocol. Development data only (install_dev_cutoff)."""
from __future__ import annotations

import json
import os
import pickle

import numpy as np
import pandas as pd

from indicator_lab.swing4 import protocol as P

P.install_dev_cutoff()

from indicator_lab import data, earnings, ind, meta  # noqa: E402
from indicator_lab.evaluate import get  # noqa: E402
from indicator_lab.metrics import equity_stats  # noqa: E402
from indicator_lab.swing4 import core as C  # noqa: E402
from indicator_lab.swing4 import sim2 as S2  # noqa: E402

UNIV = P.DEV_UNIVERSE
PERIOD = P.DEV_PERIOD
SECTOR_ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
STABLE = ["rvol", "spy_roc63", "er20"]
CACHE = os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "swing4_ctx_dev.pkl")
SEEDS = 20
K = 10


# ------------------------------------------------------------------ context
def _reaction_idx(t: str, index: pd.DatetimeIndex) -> np.ndarray:
    if t in earnings.ETFS:
        return np.array([], int)
    for name in (f"earn_{t}.json", f"earnyf_{t}.json"):
        p = os.path.join(data.CACHE_DIR, name)
        if os.path.exists(p):
            with open(p) as fh:
                rows = json.load(fh)
            break
    else:
        return np.array([], int)
    out = []
    for q in rows:
        i = index.searchsorted(pd.Timestamp(q["reportedDate"]))
        if q.get("reportTime") == "post-market":
            i += 1
        if i < len(index):
            out.append(i)
    return np.array(sorted(set(out)), int)


def _sector_map(index: pd.DatetimeIndex) -> pd.DataFrame:
    """126-day return of each sector ETF and its rank (0..1) among the ETFs with data that day."""
    cl = pd.concat({e: get(e)["close"] for e in SECTOR_ETFS}, axis=1).reindex(index).ffill()
    mom = cl / cl.shift(126) - 1
    return mom, mom.rank(axis=1, pct=True), cl.pct_change()


def build() -> dict:
    m_v3, m_st = C.model(), C.model(STABLE)
    spy = get("SPY")
    sec_mom, sec_rank, sec_ret = _sector_map(spy.index)
    ctx = {}
    for t in UNIV:
        df = get(t)
        f = meta.feature_frame(df)
        c = df["close"]
        a = ind.atr(df, 14)
        atr = a.to_numpy()
        cand = meta.base_candidates(df, 20, 0.7, 200).to_numpy()
        cand_notrend = meta.base_candidates(df, 20, 0.7, None).to_numpy()
        p3, th3 = m_v3.prob(f)
        ps, ths = m_st.prob(f)
        rx = _reaction_idx(t, df.index)
        n = len(df)
        nxt = np.full(n, 10 ** 6)          # sessions until the next reaction day
        prv = np.full(n, 10 ** 6)          # sessions since the last reaction day
        for r in rx:
            lo_ = max(0, r - 400)
            seg = np.arange(lo_, r + 1)
            nxt[seg] = np.minimum(nxt[seg], r - seg)
            seg2 = np.arange(r, min(n, r + 400))
            prv[seg2] = np.minimum(prv[seg2], seg2 - r)
        # sector proxy: the sector ETF this stock correlated with most over the past year (month-end refresh)
        r_t = c.pct_change()
        sr = sec_ret.reindex(df.index)
        corr = pd.concat({e: r_t.rolling(252, min_periods=120).corr(sr[e]) for e in SECTOR_ETFS}, axis=1)
        ok_cols = corr.notna().any(axis=1).to_numpy()
        best = np.where(ok_cols, np.nanargmax(np.where(corr.notna(), corr.to_numpy(), -9), axis=1), -1)
        smv = sec_rank.reindex(df.index).to_numpy()
        sect_rank = np.where(best >= 0, smv[np.arange(n), np.maximum(best, 0)], np.nan)
        gap = (df["open"] - c.shift()) / a.shift()
        rvol = df["volume"] / ind.sma(df["volume"], 50)
        ctx[t] = {
            "arr": S2.arrays(df, atr, (c < df["low"].rolling(20).min().shift(1)).to_numpy(), {
                "sma50": ind.sma(c, 50).to_numpy(), "rsi14": ind.rsi(c, 14).to_numpy(),
                "hi_n": df["high"].rolling(20).max().shift(1).to_numpy(),
                "earn_2": (nxt >= 2) & (nxt <= 3), "earn_3": (nxt >= 2) & (nxt <= 4)}),
            "cand": cand, "cand_notrend": cand_notrend, "p_v3": p3, "thr_v3": th3, "p_st": ps, "thr_st": ths,
            "feat": f[meta.FEATS + ["breadth50", "breadth200", "ext200"]].to_numpy(float),
            "x": {
                "mom126": (c / c.shift(126) - 1).to_numpy(), "mom252": (c / c.shift(252) - 1).to_numpy(),
                "mom_12_1": (c.shift(21) / c.shift(252) - 1).to_numpy(),
                "atr1y": (a / c * 100).rolling(252, min_periods=200).mean().to_numpy(),
                "dvol": np.log10((c * df["volume"]).rolling(50).mean()).to_numpy(),
                "sect_rank": sect_rank,
                "contract": (ind.atr(df, 10) / ind.atr(df, 50)).to_numpy(),
                "bbw_pct": f["bbw_pct"].to_numpy(),
                "hi52": (c >= df["high"].rolling(252, min_periods=200).max().shift(1)).to_numpy(float),
                "hi126": (c >= df["high"].rolling(126).max().shift(1)).to_numpy(float),
                "since_earn": prv.astype(float),
                "earn_gap": np.where(prv < 400, gap.to_numpy()[np.clip(np.arange(n) - prv, 0, n - 1)], np.nan),
                "big_gap10": (pd.Series(((gap > 1.5) & (rvol > 2)).astype(float).to_numpy(), index=df.index)
                              .rolling(10).max().to_numpy()),
                "spy_roc63": f["spy_roc63"].to_numpy(), "breadth50": f["breadth50"].to_numpy(),
                "breadth200": f["breadth200"].to_numpy(), "spy_up": f["spy_up"].to_numpy(),
                "earn_known": np.full(n, float(len(rx) > 0)),
            }}
    # cross-sectional momentum percentile within the development universe (tickers with data that day)
    for key in ("mom126", "mom252", "mom_12_1"):
        panel = pd.concat({t: pd.Series(ctx[t]["x"][key], index=ctx[t]["arr"]["index"]) for t in UNIV}, axis=1)
        rk = panel.rank(axis=1, pct=True)
        for t in UNIV:
            ctx[t]["x"][key + "_xs"] = rk[t].reindex(ctx[t]["arr"]["index"]).to_numpy()
    return ctx


def load_ctx(rebuild: bool = False) -> dict:
    if os.path.exists(CACHE) and not rebuild:
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    ctx = build()
    with open(CACHE, "wb") as fh:
        pickle.dump(ctx, fh)
    return ctx


# ------------------------------------------------------------------ runs
def v3_entry(cx) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        return cx["cand"] & (cx["p_v3"] >= cx["thr_v3"])


def run(ctx: dict, entry_fn=v3_entry, pol: S2.Policy = S2.Policy(), univ=None) -> dict:
    """{ticker: (daily returns in the period, trades with signal-bar info)}."""
    a0, b0 = PERIOD
    out = {}
    for t in univ or UNIV:
        cx = ctx[t]
        e = entry_fn(cx)
        r, tr = S2.simulate(cx["arr"], np.asarray(e, bool), pol)
        idx = cx["arr"]["index"]
        keep = []
        for x in tr:
            if not (a0 <= x["entry_date"] <= b0):
                continue
            i = x["sig_i"]
            x["ticker"] = t
            x["p_v3"], x["thr_v3"], x["p_st"] = float(cx["p_v3"][i]), float(cx["thr_v3"][i]), float(cx["p_st"][i])
            x["x"] = {k: float(v[i]) for k, v in cx["x"].items()}
            keep.append(x)
        rs = pd.Series(r, index=idx)
        out[t] = (rs[(rs.index >= a0) & (rs.index <= b0)], keep)
    return out


_SPY: dict = {}


def spy_park(idx) -> np.ndarray:
    """Daily SPY return on days SPY closed above its SMA200 the day before (v3.1 parking rule, E48), else 0."""
    if "s" not in _SPY:
        px = get("SPY")["close"]
        on = (px > px.rolling(200).mean()).shift(1).fillna(False)
        _SPY["s"] = (px.pct_change().fillna(0) * on)
    return _SPY["s"].reindex(idx).fillna(0).to_numpy()


def portfolio(res: dict, k: int = K, seed: int = 0, key=None, size=None, park: bool = False) -> dict:
    """At most k positions. Slot weight 1/k (or size(trade)/k, capped by free capital). Same-day signals: priority
    `key(trade)` (higher first) with random tie-breaks, else random order."""
    rng = np.random.default_rng(seed)
    rets = pd.concat({t: r for t, (r, _) in res.items()}, axis=1).fillna(0.0)
    idx = rets.index
    R = rets.to_numpy()
    cols = {t: i for i, t in enumerate(rets.columns)}
    allt = []
    for t, (_, tr) in res.items():
        for x in tr:
            pri = -key(x) if key is not None else 0.0
            allt.append((x["entry_date"], pri if np.isfinite(pri) else 0.0, rng.random(), t, x))
    allt.sort(key=lambda z: (z[0], z[1], z[2]))
    w = np.zeros(R.shape)
    active: list = []          # (exit_date, weight)
    taken = []
    for ed, _, _, t, x in allt:
        active = [z for z in active if z[0] > ed]
        if len(active) >= k:
            continue
        wt = 1.0 / k if size is None else float(np.clip(size(x), 0.5, 1.5)) / k
        free = 1.0 - sum(z[1] for z in active)
        wt = min(wt, free)
        if wt < 0.25 / k:
            continue
        active.append((x["exit_date"], wt))
        taken.append(x)
        i0, i1 = idx.searchsorted(ed), idx.searchsorted(x["exit_date"])
        w[i0:i1 + 1, cols[t]] = wt
    port = pd.Series((R * w).sum(axis=1), index=idx)
    if park:  # idle capital (weights are fixed fractions of equity) earns SPY while SPY > SMA200
        port = port + np.clip(1 - w.sum(axis=1), 0, 1) * spy_park(idx)
    st = equity_stats(port)
    st.update({"exposure": float(np.minimum(w.sum(axis=1), 1).mean()), "taken": taken,
               "equity": (1 + port).cumprod(), "port": port})
    return st


def tstats(trades) -> dict:
    tt = pd.DataFrame(trades) if not isinstance(trades, pd.DataFrame) else trades
    if len(tt) == 0:
        return {"n": 0, "win": np.nan, "exp_pct": np.nan, "exp_R": np.nan}
    return C.trade_metrics(tt)


def pstats(res, key=None, size=None, seeds=SEEDS, park=False) -> dict:
    runs = [portfolio(res, K, s, key, size, park) for s in range(seeds)]
    out = {m: float(np.mean([x[m] for x in runs])) for m in ("cagr", "maxdd", "mar", "sharpe", "exposure")}
    out["mar_lo"] = float(np.min([x["mar"] for x in runs]))
    out["mar_hi"] = float(np.max([x["mar"] for x in runs]))
    tk = [pd.DataFrame(x["taken"]) for x in runs]
    tm = [C.trade_metrics(d) for d in tk]
    out["taken"] = {m: float(np.mean([z[m] for z in tm])) for m in ("n", "win", "exp_pct", "exp_R", "pf", "hold")}
    yr = pd.concat([d.assign(year=d.entry_date.dt.year).groupby("year").agg(win=("R", lambda r: (r > 0).mean()),
                                                                             exp_R=("R", "mean")) for d in tk])
    out["taken_year"] = yr.groupby(level=0).mean()
    out["equity"] = runs[0]["equity"]
    out["ports"] = [x["port"] for x in runs]
    return out


# ------------------------------------------------------------------ acceptance
def year_table(tt: pd.DataFrame) -> pd.DataFrame:
    return tt.assign(year=tt.entry_date.dt.year).groupby("year").agg(win=("R", lambda r: (r > 0).mean()),
                                                                      exp_R=("R", "mean"))


def better(win, expR, bwin, bexpR, tol):
    return (win > bwin) and (expR >= bexpR - tol)


class Baseline:
    def __init__(self, ctx, entry=None, pol=None, key=None, size=None, park=False, name="v3"):
        self.name, self.key, self.size, self.park = name, key, size, park
        self.res = run(ctx, entry or v3_entry, pol or S2.Policy())
        self.tt = C.trade_table(self.res)
        self.t = tstats(self.tt)
        self.p = pstats(self.res, key, size, park=park)
        self.years = year_table(self.tt)
        self.halves = {h: tstats(self.tt[self.tt.ticker.isin(u)]) for h, u in (("a", P.HALF_A), ("b", P.HALF_B))}
        self.top_keys = set(self.tt.sort_values("ret", ascending=False).head(round(0.1 * len(self.tt)))
                            .apply(lambda x: (x.ticker, x.sig_i), axis=1))
        self.top_R = float(self.tt.sort_values("ret", ascending=False).head(round(0.1 * len(self.tt))).R.mean())


def evaluate(name: str, res: dict, B: Baseline, params: dict, n_free: int, story: str, level: str = "trade",
             key=None, size=None, log: bool = True, phase: str = "P2", park: bool = False) -> dict:
    """level "trade": win/expectancy/years/halves on all trades of the universe; "portfolio": on the trades the
    10-position portfolio actually takes (ranking / sizing ideas). MAR always from the portfolio (20 orders)."""
    tt = C.trade_table(res)
    t = tstats(tt)
    p = pstats(res, key, size, park=park)
    tol = 0.15 * abs(B.t["exp_R"])
    if level == "trade":
        win, expR, expP = t["win"], t["exp_R"], t["exp_pct"]
        bwin, bexpR, bexpP = B.t["win"], B.t["exp_R"], B.t["exp_pct"]
        yrs = year_table(tt)
        byrs = B.years
        halves = {h: tstats(tt[tt.ticker.isin(u)]) for h, u in (("a", P.HALF_A), ("b", P.HALF_B))}
        bh = B.halves
    else:
        win, expR, expP = p["taken"]["win"], p["taken"]["exp_R"], p["taken"]["exp_pct"]
        bwin, bexpR, bexpP = B.p["taken"]["win"], B.p["taken"]["exp_R"], B.p["taken"]["exp_pct"]
        yrs, byrs = p["taken_year"], B.p["taken_year"]
        halves, bh = {}, {}
        for h, u in (("a", P.HALF_A), ("b", P.HALF_B)):
            sub = {tk: v for tk, v in res.items() if tk in u}
            bsub = {tk: v for tk, v in B.res.items() if tk in u}
            halves[h] = pstats(sub, key, size, seeds=8, park=park)["taken"]
            bh[h] = pstats(bsub, B.key, B.size, seeds=8, park=B.park)["taken"]
    common = yrs.index.intersection(byrs.index)
    yb = [better(yrs.at[y, "win"], yrs.at[y, "exp_R"], byrs.at[y, "win"], byrs.at[y, "exp_R"], tol) for y in common]
    half_ok = {h: better(halves[h]["win"], halves[h]["exp_R"], bh[h]["win"], bh[h]["exp_R"], tol) for h in ("a", "b")}
    crit = {"win_up": win > bwin, "exp_pct_ok": expP >= 0.85 * bexpP, "exp_R_ok": expR >= 0.85 * bexpR,
            "mar_ok": p["mar"] >= B.p["mar"], "years70": float(np.mean(yb)) >= 0.7, "half_a": half_ok["a"],
            "half_b": half_ok["b"], "params_ok": n_free <= 2}
    accepted = all(crit.values())
    # what happens to the baseline's top-10% winners (matched on ticker + signal bar)
    k_new = {(x["ticker"], x["sig_i"]): x for _, (_, tr) in res.items() for x in tr}
    top_now = [k_new[k]["R"] for k in B.top_keys if k in k_new]
    out = {"name": name, "params": params, "trade": t, "port": p, "win": win, "exp_R": expR, "exp_pct": expP,
           "years_better": float(np.mean(yb)), "halves": half_ok, "crit": crit, "accepted": accepted,
           "top10_kept": len(top_now) / len(B.top_keys), "top10_R": float(np.mean(top_now)) if top_now else np.nan,
           "tt": tt}
    if log:
        P.log({"phase": phase, "idea": name, "params": params, "new_free_params": n_free, "universe": f"DEV-U {len(res)}",
               "period": "2015-01-01..2024-10-21", "n": t["n"], "win": win, "exp_pct": expP, "exp_R": expR,
               "pf": t["pf"], "avg_win": t["avg_win"], "avg_loss": t["avg_loss"], "cagr": p["cagr"],
               "maxdd": p["maxdd"], "mar": p["mar"], "hold": t["hold"], "exposure": p["exposure"],
               "exp_ci_lo": P.bootstrap_ci(tt["R"])[0], "exp_ci_hi": P.bootstrap_ci(tt["R"])[1],
               "years_better": out["years_better"], "half_a": half_ok["a"], "half_b": half_ok["b"],
               "accepted": accepted, "notes": f"level={level}; top10 kept {out['top10_kept']:.2f} meanR "
                                             f"{out['top10_R']:.2f} (base {B.top_R:.2f}); vs {B.name}; " + story})
    return out


def line(e: dict, B: Baseline | None = None) -> str:
    t, p = e["trade"], e["port"]
    flags = "".join("✓" if v else "·" for v in e["crit"].values())
    return (f"{e['name'][:46]:46s} win {e['win'] * 100:5.1f}% exp {e['exp_pct'] * 100:5.2f}% {e['exp_R']:+.3f}R "
            f"PF {t['pf']:.2f} hold {t['hold']:4.1f} | CAGR {p['cagr'] * 100:5.1f}% DD {p['maxdd'] * 100:6.1f}% "
            f"MAR {p['mar']:.2f} expo {p['exposure'] * 100:3.0f}% | yrs {e['years_better']:.1f} "
            f"top10R {e['top10_R']:.2f} | {flags} {'ACCEPT' if e['accepted'] else ''}")
