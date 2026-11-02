"""Swing v4.1 -> v4.2, phase 1 (research only, nothing in Pine changes): realistic costs, model ablation, regime rule,
fill at the signal close, gap filter, earnings block, the user's real portfolio plan, survivorship.

    python -m indicator_lab.swing4.v42_phase1        # indicator_lab/reports/v42_phase1.md

Cells (as in phase3.py): DEV tickers 2015-01-01..2024-10-21, TICKER holdout (84 tickers, same period), TIME holdout (DEV
tickers, 2024-10-22..now), TICKER+TIME holdout. Honest note: the holdout was used ONCE before (phase 3, v4 vs v3). This is a
second look: nothing is chosen on the holdout here, every holdout number is reported only.
Fixed before the run: base cost 0.5% per side for every comparison except the cost table; 10 positions of 1/10, mean of 20
random selection orders; regime threshold 0.03 (v4.1) unless stated; the earnings rule blocks a BUY when an earnings
report date falls in the 7 calendar days after the signal close (dates from week/earnings_eps.load, known weeks ahead).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab.swing4 import protocol as P

P.install_final()

from indicator_lab import meta
from indicator_lab.evaluate import get
from indicator_lab.metrics import equity_stats
from indicator_lab.swing4 import core as C
from indicator_lab.swing4 import lab as L
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.week import earnings_eps as EE

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "v42_phase1.md")
CTX = os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "swing4_ctx_final.pkl")
H = sorted(P.H_TICKERS)
DEV = P.DEV_UNIVERSE
D0, D1, HS, END = P.DEV_PERIOD[0], P.DEV_PERIOD[1], P.H_START, pd.Timestamp("2100-01-01")
CELLS = {"DEV (253, 2015-2024/10)": (DEV, (D0, D1)), "TICKER-holdout (84, 2015-2024/10)": (H, (D0, D1)),
         "TIME-holdout (253, 2024/10-nu)": (DEV, (HS, END)), "TICKER+TIME (84, 2024/10-nu)": (H, (HS, END))}
COST = 0.005
REG = 0.03
FEAT_COLS = meta.FEATS + ["breadth50", "breadth200", "ext200"]


def regime(cx, thr=REG):
    with np.errstate(invalid="ignore"):
        return np.nan_to_num(cx["x"]["spy_roc63"], nan=9) <= thr


def add_model(ctx, feats, name):
    m = C.model(feats)
    for cx in ctx.values():
        f = pd.DataFrame(cx["feat"], index=cx["arr"]["index"], columns=FEAT_COLS)
        cx[f"p_{name}"], cx[f"thr_{name}"] = m.prob(f)


def add_earnings(ctx):
    earn = EE.load()
    cov = 0
    for t, cx in ctx.items():
        idx = cx["arr"]["index"]
        blk = np.zeros(len(idx), bool)
        dates = sorted({pd.Timestamp(ts).normalize() for ts, *_ in earn.get(t, [])})
        cov += bool(dates)
        if dates:
            d = pd.DatetimeIndex(dates)
            pos = d.searchsorted(idx, side="right")       # first report date strictly after the signal date
            nxt = np.where(pos < len(d), d[np.minimum(pos, len(d) - 1)].values, np.datetime64("NaT"))
            with np.errstate(invalid="ignore"):
                gap = (pd.DatetimeIndex(nxt) - idx).days
            blk = np.nan_to_num(np.asarray(gap, float), nan=99) <= 7
        cx["earn7"] = blk
    return cov / len(ctx)


ENTRIES = {
    "a v2 (alleen regels)": lambda cx: cx["cand"],
    "b v2 + regime": lambda cx: cx["cand"] & regime(cx),
    "c v4 (regels + model + regime) = huidig": lambda cx: cx["cand"] & (cx["p_v3"] >= cx["thr_v3"]) & regime(cx),
    "d v2 + regime + mini-model (rvol, spyRoc63, er20)": lambda cx: cx["cand"] & (cx["p_st"] >= cx["thr_st"]) & regime(cx),
    "e v2 + regime + mini-model (rvol, er20)": lambda cx: cx["cand"] & (cx["p_e"] >= cx["thr_e"]) & regime(cx),
}
V4 = ENTRIES["c v4 (regels + model + regime) = huidig"]


def measure(ctx, entry, univ, per, pol=S2.DEFAULT, cost=COST):
    res = L.run(ctx, entry, pol, univ=univ, period=per, cost=cost)
    t = L.tstats(L.C.trade_table(res))
    p = L.pstats(res)
    return t, p, res


def fmt(name, t, p):
    if t["n"] == 0:
        return {"variant": name, "trades": 0}
    return {"variant": name, "trades": t["n"], "winrate": f"{t['win'] * 100:.1f}%", "expectancy": f"{t['exp_pct'] * 100:+.2f}%",
            "exp. (R)": f"{t['exp_R']:+.3f}", "PF": f"{t['pf']:.2f}", "CAGR": f"{p['cagr'] * 100:.1f}%",
            "max DD": f"{p['maxdd'] * 100:.1f}%", "MAR": f"{p['mar']:.2f}", "exposure": f"{p['exposure'] * 100:.0f}%"}


def spy_row(per):
    px = get("SPY")["close"]
    r = px.pct_change().dropna()
    r = r[(r.index >= per[0]) & (r.index <= per[1])]
    s = equity_stats(r)
    return {"variant": "SPY kopen & houden (total return)", "CAGR": f"{s['cagr'] * 100:.1f}%",
            "max DD": f"{s['maxdd'] * 100:.1f}%", "MAR": f"{s['mar']:.2f}", "Sharpe": f"{s['sharpe']:.2f}",
            "exposure": "100%"}


def table(rows):
    return pd.DataFrame(rows).fillna("").to_markdown(index=False) + "\n\n"


def auc(score, y):
    s, y = np.asarray(score, float), np.asarray(y, bool)
    ok = np.isfinite(s)
    s, y = s[ok], y[ok]
    if y.sum() == 0 or (~y).sum() == 0:
        return np.nan
    r = pd.Series(s).rank().to_numpy()
    return (r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum())


def model_diag(ctx, univ, per):
    """On the v2 + regime trades: AUC of each model's score for 'trade won', spread of the scores, share filtered."""
    res = L.run(ctx, ENTRIES["b v2 + regime"], univ=univ, period=per, cost=COST)
    tr = [x for _, (_, tt) in res.items() for x in tt]
    rows = []
    for name, (pk, tk) in {"c v4 (17 features)": ("p_v3", "thr_v3"), "d mini (rvol, spyRoc63, er20)": ("p_st", "thr_st"),
                           "e mini (rvol, er20)": ("p_e", "thr_e")}.items():
        sc = np.array([ctx[x["ticker"]][pk][x["sig_i"]] for x in tr])
        th = np.array([ctx[x["ticker"]][tk][x["sig_i"]] for x in tr])
        y = np.array([x["R"] > 0 for x in tr])
        rows.append({"model": name, "trades v2+regime": len(tr), "AUC (winst ja/nee)": f"{auc(sc, y):.3f}",
                     "score sd": f"{np.nanstd(sc):.3f}", "score p10-p90": f"{np.nanpercentile(sc, 10):.2f}-{np.nanpercentile(sc, 90):.2f}",
                     "% weggefilterd na regime": f"{np.nanmean(sc < th) * 100:.0f}%"})
    return rows


def plan_portfolio(res, seeds=20, risk=0.01, cap=0.10, k=10):
    """The user's plan: <= k positions, weight = min(risk / stop distance, cap), idle cash in SPY while SPY > SMA200."""
    rets = pd.concat({t: r for t, (r, _) in res.items()}, axis=1).fillna(0.0)
    idx, R = rets.index, rets.to_numpy()
    cols = {t: i for i, t in enumerate(rets.columns)}
    park = L.spy_park(idx)
    out = []
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        allt = sorted([(x["entry_date"], rng.random(), t, x) for t, (_, tt) in res.items() for x in tt],
                      key=lambda z: (z[0], z[1]))
        w = np.zeros(R.shape)
        active = []
        for ed, _, t, x in allt:
            active = [z for z in active if z[0] > ed]
            if len(active) >= k:
                continue
            wt = min(risk / x["risk"], cap, 1.0 - sum(z[1] for z in active))
            if wt <= 0.005:
                continue
            active.append((x["exit_date"], wt))
            w[idx.searchsorted(ed):idx.searchsorted(x["exit_date"]) + 1, cols[t]] = wt
        port = pd.Series((R * w).sum(axis=1) + np.clip(1 - w.sum(axis=1), 0, 1) * park, index=idx)
        s = equity_stats(port)
        s["expo"] = float(np.minimum(w.sum(axis=1), 1).mean())
        out.append(s)
    return {m: float(np.mean([s[m] for s in out])) for m in ("cagr", "maxdd", "mar", "sharpe", "expo")}


def main():
    ctx = L.load_ctx(rebuild=not os.path.exists(CTX), univ=DEV + H, path=CTX)
    add_model(ctx, ["rvol", "er20"], "e")
    cov = add_earnings(ctx)
    md = ["# Swing v4.1 → v4.2 — fase 1 (onderzoek in Python)\n\n<!-- CONCLUSIE -->\n\n",
          ("Engine: `swing4/lab.py` + `sim2.py` (= de v4.1-regels; fill volgende open, 4×ATR-trail, 20-daagse-laag-exit, "
           "max 10 posities à 1/10, gemiddelde van 20 selectievolgordes). **De holdout is al één keer gebruikt (fase 3)**: "
           "alles hieronder op de holdout is een tweede blik en wordt alleen gerapporteerd, er wordt niets op gekozen.\n\n")]
    # 1 costs
    md.append("## 1. Kosten per kant (v4 = huidig)\n\n")
    for cell, (u, per) in CELLS.items():
        rows = [fmt(f"kosten {c * 100:.1f}%/kant", *measure(ctx, V4, u, per, cost=c)[:2]) for c in (0.001, 0.003, 0.005, 0.007)]
        rows.append(spy_row(per))
        md.append(f"**{cell}**\n\n" + table(rows))
        print("1", cell, flush=True)
    # 2 ablation
    md.append("## 2. Ablatie van het model (kosten 0,5%/kant)\n\n")
    for cell, (u, per) in CELLS.items():
        rows = [fmt(n, *measure(ctx, e, u, per)[:2]) for n, e in ENTRIES.items()] + [spy_row(per)]
        md.append(f"**{cell}**\n\n" + table(rows) + "Model-diagnose op de v2+regime-trades:\n\n" + table(model_diag(ctx, u, per)))
        print("2", cell, flush=True)
    # 3 regime
    spy = get("SPY")["close"]
    roc = spy / spy.shift(63) - 1
    yr = (roc > REG)[(roc.index >= "2015-01-01")].groupby(roc.index[roc.index >= "2015-01-01"].year).mean()
    md.append("## 3. Regime-regel\n\n% handelsdagen waarop de regel (SPY 63d > 3%) een BUY blokkeert:\n\n"
              + table([{"jaar": y, "% geblokkeerd": f"{v * 100:.0f}%"} for y, v in yr.items()])
              + f"Gemiddeld 2015-2026: {(roc > REG)[roc.index >= '2015-01-01'].mean() * 100:.0f}%.\n\n"
              "Gevoeligheid van de drempel (v4, 0,5%/kant; op de holdout alleen rapporteren):\n\n")
    for cell, (u, per) in CELLS.items():
        rows = [fmt(f"drempel {thr:.3f}", *measure(ctx, lambda cx, thr=thr: cx["cand"] & (cx["p_v3"] >= cx["thr_v3"])
                                                       & regime(cx, thr), u, per)[:2]) for thr in (0.0, 0.015, 0.03, 0.045, 0.06)]
        md.append(f"**{cell}**\n\n" + table(rows))
        print("3", cell, flush=True)
    # 4 fill at the signal close + overnight gap
    md.append("## 4. Fill op de signaal-close (live BUY) vs volgende open (v4, 0,5%/kant)\n\n")
    for cell, (u, per) in CELLS.items():
        t_o, p_o, res_o = measure(ctx, V4, u, per)
        t_c, p_c, _ = measure(ctx, V4, u, per, S2.Policy(entry="close"))
        gaps, gatr = [], []
        for tk, (_, tt) in res_o.items():
            a = ctx[tk]["arr"]
            for x in tt:
                i = x["sig_i"]
                if i + 1 < len(a["o"]):
                    gaps.append(a["o"][i + 1] / a["c"][i] - 1)
                    gatr.append((a["o"][i + 1] - a["c"][i]) / a["atr"][i])
        md.append(f"**{cell}**\n\n" + table([fmt("fill volgende open (v4.1)", t_o, p_o), fmt("fill op signaal-close", t_c, p_c)])
                  + f"Overnight gap na een signaal: gemiddeld {np.mean(gaps) * 100:+.2f}% (mediaan {np.median(gaps) * 100:+.2f}%), "
                    f"= {np.mean(gatr):+.2f} ATR; {np.mean(np.array(gaps) > 0) * 100:.0f}% van de gaps is omhoog.\n\n")
        print("4", cell, flush=True)
    # 5 gap filter
    md.append("## 5. Gap-filter bij instap (sla over als open > signaal-close + x·ATR; v4, 0,5%/kant)\n\n")
    for cell, (u, per) in CELLS.items():
        rows = [fmt("geen filter (v4.1)", *measure(ctx, V4, u, per)[:2])]
        rows += [fmt(f"x = {x}", *measure(ctx, V4, u, per, S2.Policy(gap_max=x))[:2]) for x in (1.0, 1.5, 2.0)]
        md.append(f"**{cell}**\n\n" + table(rows))
        print("5", cell, flush=True)
    # 6 earnings
    md.append(f"## 6. Earnings-regel: geen BUY als er cijfers zijn binnen 7 kalenderdagen (v4, 0,5%/kant)\n\n"
              f"Aandelen met earnings-data: {cov * 100:.0f}%.\n\n")
    for cell, (u, per) in CELLS.items():
        rows = [fmt("zonder regel (v4.1)", *measure(ctx, V4, u, per)[:2]),
                fmt("met earnings-blok", *measure(ctx, lambda cx: V4(cx) & ~cx["earn7"], u, per)[:2])]
        md.append(f"**{cell}**\n\n" + table(rows))
        print("6", cell, flush=True)
    # 7 the real plan
    md.append("## 7. Jouw echte plan: max 10 posities, 1% risico per trade, max 10% per positie, idle cash in SPY als "
              "SPY > SMA200 (E48), kosten 0,5%/kant\n\n")
    for cell, (u, per) in CELLS.items():
        rows = []
        for name in ("c v4 (regels + model + regime) = huidig", "b v2 + regime"):
            res = L.run(ctx, ENTRIES[name], univ=u, period=per, cost=COST)
            s = plan_portfolio(res)
            rows.append({"variant": name, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                         "MAR": f"{s['mar']:.2f}", "Sharpe": f"{s['sharpe']:.2f}", "exposure (aandelen)": f"{s['expo'] * 100:.0f}%"})
        rows.append(spy_row(per))
        md.append(f"**{cell}**\n\n" + table(rows))
        print("7", cell, flush=True)
    # 8 survivorship
    md.append("## 8. Survivorship bias\n\n"
              "- De 84 holdout-tickers (`swing4/holdout.json`) zijn **S&P 500-leden van ~2015**, gekozen op lidmaatschap rond "
              "2015 (niet op latere prestaties), met bewust latere achterblijvers en index-verlaters (KSS, M, XRX, NWL, VFC, "
              "LUMN, IVZ, BEN, F, VTRS, BIIB, MOS). Dat is grotendeels point-in-time.\n"
              "- Maar: alleen aandelen waarvan Yahoo nog data heeft konden gekozen worden. Drie vielen af (IPG overgenomen, EA en "
              "EQR zonder data); aandelen die tussen 2015 en 2024 verdwenen (overnames, faillissementen) en waarvan geen data "
              "meer bestaat, ontbreken. Ongeveer een kwart van de S&P 500 van 2015 is er in 2024 niet meer; een deel daarvan zou "
              "in de holdout hebben gezeten. Faillissementen ontbreken dus vooral → de holdout is licht te optimistisch, "
              "overnames (vaak met een koerssprong) ontbreken ook → dat werkt de andere kant op. Netto: kleine, onbekende "
              "bias; geen point-in-time-database met gedelistte koersen beschikbaar in deze omgeving.\n"
              "- De 253 DEV-tickers zijn **niet** point-in-time: grotendeels namen die eerder in dit project gekozen werden "
              "(o.a. bekende volatiele groeiers) — daar zijn de cijfers duidelijk te optimistisch.\n\n")
    with open(OUT, "w") as fh:
        fh.write("".join(md))
    print("done", flush=True)


if __name__ == "__main__":
    main()
