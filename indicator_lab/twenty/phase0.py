"""Phase 0 of Swing 20/21: base rates (development data only, before anything is built).

    python -m indicator_lab.twenty.phase0       # writes twenty/reports/phase0.md + heatmaps, logs the base cells

For EVERY stock-day that passes the point-in-time filters (price > $5, 50-day dollar volume > $5M, a year of history)
a trade is simulated with the 20/21 rules (config20): buy at the next open, target limit, stop variants, time exit.
1. how often +20% within 21 days comes before the stop, split by volatility, size (dollar volume), price, sector,
   market regime and year
2. heatmaps target x horizon x stop: hit rate and expectancy
3. the break-even hit rate for each target / stop given the costs
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

from indicator_lab import data as MAIN
from indicator_lab import ind
from indicator_lab.twenty import config20 as K
from indicator_lab.twenty import data20 as D
from indicator_lab.twenty import outcomes20 as X

DRY = bool(os.environ.get("TWENTY_DRYRUN"))
OUT = os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "dry20") if DRY else os.path.join(D.HERE, "reports")
EXP = os.path.join(OUT, "experiments_dry.csv") if DRY else os.path.join(D.HERE, "experiments_20in21.csv")
SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
START = pd.Timestamp("2013-01-01")
SAMPLE_EVERY = 3            # row-level sample for the splits (every 3rd eligible day); the grid uses every day
ROW_STOPS = ("signal_low", "atr2", "pct7", "pct10", "atr3", "atr1.5")


def _main_series(t):
    df = MAIN.load(t)
    return df[df.index < D.H_START]


def market() -> dict:
    spy = _main_series("SPY")["close"]
    vix = _main_series("^VIX")["close"]
    sect = pd.concat({e: _main_series(e)["close"] for e in SECTORS}, axis=1)
    return {"spy_up": (spy > spy.rolling(200).mean()).astype(float), "spy_roc63": spy / spy.shift(63) - 1,
            "vix": vix, "sect_ret": sect.pct_change()}


MKT: dict = {}


def _init():
    MKT.update(market())


def one(t: str):
    df = D.load(t)
    if df is None or len(df) < 320:
        return None
    df = df[~df.index.duplicated()]
    o, h, lo, c, _v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    n = len(c)
    atr = ind.atr(df, 14).to_numpy()
    atr1y = (ind.atr(df, 14) / df["close"] * 100).rolling(252, min_periods=200).mean().to_numpy()
    dvol = (df["close"] * df["volume"]).rolling(50).mean().to_numpy()
    ok = (c > K.MIN_PRICE) & (dvol > K.MIN_DVOL) & np.isfinite(atr1y) & np.isfinite(atr) & (df.index >= START)
    ok &= np.arange(n) <= n - 1 - X.WMAX
    ok &= (o > 0) & (lo > 0)
    starts = np.flatnonzero(ok)
    if len(starts) == 0:
        return None
    fill, O, H, L, C = X.windows(o, h, lo, c, starts)
    slip = np.array([K.slippage(x) for x in dvol[starts]])
    grid = {}
    rows = {"ticker": t, "date": df.index[starts], "atr1y": atr1y[starts], "price": c[starts], "dvol": dvol[starts]}
    for sname, (kind, val) in K.STOPS.items():
        sp = X.stop_price(kind, val, fill, lo[starts], atr[starts])
        valid = (sp < fill) & (sp > 0)
        for T in K.GRID_TARGETS:
            tg = fill * (1 + T)
            first, ev, px = X.events(O, H, L, sp, tg)
            for hz in K.GRID_HORIZONS:
                r, hit, stopped = X.outcome(fill, C, sp, tg, first, ev, px, hz, slip)
                rv, hv, sv = r[valid], hit[valid], stopped[valid]
                grid[(sname, T, hz)] = (len(rv), hv.sum(), sv.sum(), rv.sum(), (rv ** 2).sum())
                if T == K.TARGET and hz == K.HORIZON and sname in ROW_STOPS:
                    rows[f"r_{sname}"] = np.where(valid, r, np.nan)
                    rows[f"hit_{sname}"] = np.where(valid, hit, np.nan)
                    rows[f"stop_{sname}"] = np.where(valid, stopped, np.nan)
                    rows[f"days_{sname}"] = np.where(valid & hit, first + 1, np.nan)
                    rows[f"dist_{sname}"] = 1 - sp / fill
    rd = pd.DataFrame(rows)
    # market regime and the sector proxy (sector ETF with the highest 1-year return correlation), at the signal close
    idx = df.index
    for k in ("spy_up", "spy_roc63", "vix"):
        rd[k] = MKT[k].reindex(idx).ffill().to_numpy()[starts]
    rt = df["close"].pct_change()
    sr = MKT["sect_ret"].reindex(idx)
    corr = np.column_stack([rt.rolling(252, min_periods=120).corr(sr[e]).to_numpy() for e in SECTORS])
    has = np.isfinite(corr).any(axis=1)
    best = np.where(has, np.nanargmax(np.where(np.isfinite(corr), corr, -9), axis=1), -1)
    rd["sector"] = [SECTORS[b] if b >= 0 else "?" for b in best[starts]]
    rd = rd.iloc[::SAMPLE_EVERY].reset_index(drop=True)
    return grid, rd, (t, df.index[0])


def month_ci(df, col, n=2000, seed=0):
    """95% CI of the mean of `col`, resampling calendar months (days overlap and stocks co-move)."""
    d = df[[col]].dropna().assign(m=df["date"].dt.to_period("M"))
    g = d.groupby("m")[col].agg(["sum", "count"]).to_numpy()
    rng = np.random.default_rng(seed)
    b = g[rng.integers(0, len(g), (n, len(g)))]
    return tuple(np.quantile(b[:, :, 0].sum(1) / b[:, :, 1].sum(1), [0.025, 0.975]))


def breakeven(T, S, slip=0.0):
    win = (1 + T) * (1 - K.COST) / (1 + K.COST + slip) - 1
    loss = (1 - S) * (1 - K.COST - slip) / (1 + K.COST + slip) - 1
    return -loss / (win - loss), win, loss


def log(row):
    fields = ["id", "time", "phase", "idea", "params", "n", "hit_rate", "hit_ci", "exp_pct", "exp_ci", "notes"]
    exists = os.path.exists(EXP)
    n = 0
    if exists:
        with open(EXP) as fh:
            n = sum(1 for _ in fh) - 1
    with open(EXP, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerow({"id": n + 1, "time": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **row})


def bucket_table(rows, col, cuts, labels, stops=("pct10", "atr2")):
    b = pd.cut(rows[col], cuts, labels=labels)
    out = []
    for lab, g in rows.groupby(b, observed=True):
        rec = {"bucket": lab, "n": len(g)}
        for s in stops:
            rec[f"hit_{s}"] = g[f"hit_{s}"].mean()
            rec[f"exp_{s}"] = g[f"r_{s}"].mean()
        out.append(rec)
    return pd.DataFrame(out)


def fmt_tab(d, stops=("pct10", "atr2")):
    head = "| bucket | n (sampled days) | " + " | ".join(f"hit {s} | exp {s}" for s in stops) + " |"
    L = [head, "|" + "---|" * (2 + 2 * len(stops))]
    for _, r in d.iterrows():
        L.append(f"| {r['bucket']} | {r['n']} | " + " | ".join(f"{r[f'hit_{s}'] * 100:.1f}% | {r[f'exp_{s}'] * 100:+.2f}%"
                                                         for s in stops) + " |")
    return "\n".join(L)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(OUT, exist_ok=True)
    tickers = [t for t in D.DEV if os.path.exists(D.path(t))]
    if os.environ.get("TWENTY_DRYRUN"):          # code check on a few stocks; nothing is logged or written to reports/
        tickers = tickers[:150]
    with Pool(4, initializer=_init) as pool:
        res = [r for r in pool.imap_unordered(one, tickers, chunksize=8) if r is not None]
    grid = {}
    for g, _, _ in res:
        for k, v in g.items():
            grid[k] = tuple(a + b for a, b in zip(grid.get(k, (0, 0, 0, 0.0, 0.0)), v))
    rows = pd.concat([r for _, r, _ in res], ignore_index=True)
    firsts = pd.Series({t: d0 for _, _, (t, d0) in res})
    rows["year"] = rows["date"].dt.year
    G = pd.DataFrame([{"stop": k[0], "T": k[1], "H": k[2], "n": v[0], "hit": v[1] / v[0], "stopped": v[2] / v[0],
                       "exp": v[3] / v[0]} for k, v in grid.items()])
    G.to_csv(os.path.join(OUT, "p0_grid.csv"), index=False)
    rows.to_pickle(os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "p0_20in21_rows.pkl"))

    # ---- heatmaps
    fig, axes = plt.subplots(len(K.STOPS), 2, figsize=(10, 3.0 * len(K.STOPS)))
    for k, s in enumerate(K.STOPS):
        sub = G[G.stop == s]
        for j, (col, ttl, fmt) in enumerate((("hit", "hit rate (target before stop)", "{:.0%}"),
                                             ("exp", "expectancy per trade (net)", "{:+.2%}"))):
            piv = sub.pivot(index="T", columns="H", values=col)
            ax = axes[k, j]
            ax.imshow(piv.values, cmap="RdYlGn" if col == "exp" else "viridis", aspect="auto", origin="lower",
                           vmin=(-abs(piv.values).max() if col == "exp" else None),
                           vmax=(abs(piv.values).max() if col == "exp" else None))
            ax.set_xticks(range(piv.shape[1]), [str(x) for x in piv.columns])
            ax.set_yticks(range(piv.shape[0]), [f"+{int(x * 100)}%" for x in piv.index])
            ax.set_xlabel("horizon (trading days)")
            ax.set_ylabel("target")
            for i_ in range(piv.shape[0]):
                for j_ in range(piv.shape[1]):
                    ax.text(j_, i_, fmt.format(piv.values[i_, j_]), ha="center", va="center", fontsize=7)
            ax.set_title(f"stop {s}: {ttl}", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p0_heatmaps.png"), dpi=90)
    plt.close(fig)

    # ---- report
    L = ["# Swing 20/21 — phase 0: base rates (development data, before any setup)\n"]
    L.append(f"Every day of {len(res)} development stocks (of {len(D.DEV)}) from 2013-01 to 2024-09 that passes the point-in-"
             f"time filters (close > ${K.MIN_PRICE:.0f}, 50-day dollar volume > ${K.MIN_DVOL / 1e6:.0f}M, a year of history) "
             f"is treated as a signal: {grid[('pct10', 0.2, 21)][0]:,} stock-days. Buy at the next open, +20% limit, stop, "
             f"time exit at the close of day 21 (fill day = day 1); stop wins inside a bar; costs {K.COST * 100:.2f}% per "
             "side + slippage by dollar volume on market fills. Survivor-biased: only stocks listed today are in the data.\n")
    L.append("## 1. +20% within 21 days, a random stock on a random day\n")
    L.append("| stop | median stop distance | hit (target first) | 95% CI (by month) | stopped | time exit | expectancy "
             "| 95% CI | break-even hit rate | median days to target |\n|" + "---|" * 10)
    for s in K.STOPS:
        if f"r_{s}" not in rows:
            continue
        hit, st = rows[f"hit_{s}"].mean(), rows[f"stop_{s}"].mean()
        e = rows[f"r_{s}"].mean()
        hci, eci = month_ci(rows, f"hit_{s}"), month_ci(rows, f"r_{s}")
        dist = rows[f"dist_{s}"].median()
        be, _, _ = breakeven(0.20, dist, 0.0)
        L.append(f"| {s} | {dist * 100:.1f}% | {hit * 100:.1f}% | {hci[0] * 100:.1f}–{hci[1] * 100:.1f}% | {st * 100:.1f}% | "
                 f"{(1 - hit - st) * 100:.1f}% | {e * 100:+.2f}% | {eci[0] * 100:+.2f}–{eci[1] * 100:+.2f}% | {be * 100:.1f}% | "
                 f"{rows[f'days_{s}'].median():.0f} |")
        log({"phase": "P0", "idea": f"base rate +20%/21d stop {s}", "params": json.dumps({"stop": s}), "n": int(rows[f'r_{s}'].notna().sum()),
             "hit_rate": round(hit, 5), "hit_ci": f"{hci[0]:.4f}-{hci[1]:.4f}", "exp_pct": round(e, 5),
             "exp_ci": f"{eci[0]:.4f}-{eci[1]:.4f}", "notes": "random stock-day (every 3rd eligible day)"})
    L.append("\nThe break-even hit rate assumes every trade ends at the target or the stop; time exits (most trades) "
             "add their own average, which is why the expectancy is the number that counts.\n")
    splits = [
        ("Volatility (1-year mean ATR% of the stock)", "atr1y", [0, 1.5, 2.5, 3.5, 5, 7, 100],
         ["<1.5%", "1.5–2.5%", "2.5–3.5%", "3.5–5%", "5–7%", ">7%"]),
        ("Size proxy: 50-day dollar volume (no point-in-time market cap available)", "dvol",
         [0, 10e6, 25e6, 100e6, 500e6, 1e13], ["$5–10M", "$10–25M", "$25–100M", "$100–500M", ">$500M"]),
        ("Price", "price", [0, 10, 20, 50, 200, 1e9], ["$5–10", "$10–20", "$20–50", "$50–200", ">$200"]),
        ("Market: SPY 63-day return", "spy_roc63", [-1, -0.05, 0, 0.03, 0.06, 1], ["<−5%", "−5–0%", "0–3%", "3–6%", ">6%"]),
        ("Market: VIX", "vix", [0, 15, 20, 30, 200], ["<15", "15–20", "20–30", ">30"]),
        ("Market: SPY above its SMA200", "spy_up", [-0.5, 0.5, 1.5], ["no", "yes"]),
    ]
    for title, col, cuts, labels in splits:
        L.append(f"\n### {title}\n")
        L.append(fmt_tab(bucket_table(rows, col, cuts, labels)))
    L.append("\n### Sector proxy (sector ETF the stock correlated with most over the past year)\n")
    sec = rows.groupby("sector").agg(n=("r_pct10", "size"), hit_pct10=("hit_pct10", "mean"), exp_pct10=("r_pct10", "mean"), hit_atr2=("hit_atr2", "mean"), exp_atr2=("r_atr2", "mean"))
    L.append(fmt_tab(sec.reset_index().rename(columns={"sector": "bucket"})))
    L.append("\n### Year\n")
    yr = rows.groupby("year").agg(n=("r_pct10", "size"), hit_pct10=("hit_pct10", "mean"), exp_pct10=("r_pct10", "mean"),
                                  hit_atr2=("hit_atr2", "mean"), exp_atr2=("r_atr2", "mean"))
    yr = yr.reset_index().rename(columns={"year": "bucket"})
    yr["bucket"] = yr["bucket"].astype(int).astype(str)
    yr["n"] = yr["n"].astype(int)
    L.append(fmt_tab(yr))

    L.append("\n## 2. Target x horizon x stop\n")
    L.append("![heatmaps](p0_heatmaps.png)\n")
    L.append("Best cells by expectancy (all stops):\n")
    L.append("| stop | target | horizon | hit rate | stopped | expectancy |\n|---|---|---|---|---|---|")
    for _, r in G.sort_values("exp", ascending=False).head(12).iterrows():
        L.append(f"| {r.stop} | +{r['T'] * 100:.0f}% | {r.H} | {r.hit * 100:.1f}% | {r.stopped * 100:.1f}% | {r.exp * 100:+.2f}% |")
    base = G[(G['T'] == 0.20) & (G.H == 21)].set_index("stop")
    L.append("\n+20% / 21 days per stop (all days):\n")
    L.append("| stop | hit | stopped | expectancy |\n|---|---|---|---|")
    for s, r in base.iterrows():
        L.append(f"| {s} | {r.hit * 100:.1f}% | {r.stopped * 100:.1f}% | {r.exp * 100:+.2f}% |")

    L.append("\n## 3. Break-even hit rate (target or stop, costs 0.15%/side, no extra slippage)\n")
    L.append("| target \\ stop | −5% | −7% | −10% | −15% |\n|---|---|---|---|---|")
    for T in K.GRID_TARGETS:
        L.append(f"| +{T * 100:.0f}% | " + " | ".join(f"{breakeven(T, S)[0] * 100:.1f}%" for S in (0.05, 0.07, 0.10, 0.15)) + " |")

    n13 = int((firsts <= pd.Timestamp("2013-01-31")).sum())
    L.append("\n## Survivorship\n")
    L.append(f"- Only stocks listed on 2026-10-23 are in the data. Of the {len(res)} development stocks with data, {n13} were already "
             "trading in January 2013. Around 4,000+ US common stocks were listed then (NYSE + NASDAQ + AMEX), so a large "
             "part of the 2013 universe (failures, but also take-overs) is missing.")
    L.append("- Direction of the bias: failed stocks (stops, never +20%) are missing → base hit rates and expectancies are too "
             "high; acquired stocks (often a +20–40% premium in one day) are missing too → part of the real +20% events is missing. "
             "Net effect unknown, but for a long-only random-day study the first effect usually dominates.")
    with open(os.path.join(OUT, "phase0.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
