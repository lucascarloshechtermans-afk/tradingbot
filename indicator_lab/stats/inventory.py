"""Step 1 of the overfitting measurement: the trials inventory, daily return series on one common basis, N and N_eff.

    python -m indicator_lab.stats.inventory            # writes trials_inventory.csv, reports/step1_trials.md

Common basis for every rebuilt variant (so the series are comparable and the correlations mean something):
  universe   DEV-U, the 253 development tickers of the v4 round (= every universe the E-experiments used:
             DEV, HOLDOUT, TRAIN_EXTRA, VOLATILE, LOCKBOX, LOCKBOX2); no v4- or v5-holdout ticker
  period     entries and returns 2015-01-01 .. 2024-10-21 (data cut before the v4 time holdout)
  portfolio  at most 10 positions of 10% (a variant that itself uses fewer slots keeps its own number), same-day
             signals in one fixed random order (seed 0), idle cash at 0% unless the variant parks it
  costs      0.1% per side on every fill
Nothing is fitted to choose anything: variants with a walk-forward model rebuild that model exactly as the variant
defined it (yearly refits on the DEV tickers, or the training set the variant names).
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

from indicator_lab.swing4 import protocol as P4

P4.install_dev_cutoff()

from indicator_lab import evaluate as E  # noqa: E402
from indicator_lab import meta, strategies  # noqa: E402
from indicator_lab.stats import trials as TR  # noqa: E402

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "reports")
WORK = os.environ.get("STATS_WORK", os.path.join(HERE, "out"))
MATRIX = os.path.join(WORK, "returns_dev.csv.gz")
UNIV = P4.DEV_UNIVERSE
PERIOD = P4.DEV_PERIOD
K = 10
SEED = 0

FN = {"v0": strategies.v0_repo_pullback, "rsi2": strategies.rsi2_pullback, "ema": strategies.ema_trend,
      "donchian": strategies.donchian_breakout, "breakout": strategies.breakout, "brk_pb": strategies.breakout_pullback,
      "family": strategies.family, "weekly": strategies.weekly_breakout, "short": strategies.breakdown_short,
      "meta": meta.meta_breakout, "meta_mr": meta.meta_mr, "pyramid": meta.pyramid_add}


def calendar() -> pd.DatetimeIndex:
    idx = E.get("SPY").index
    return idx[(idx >= PERIOD[0]) & (idx <= PERIOD[1])]


def rf_daily(idx) -> np.ndarray:
    irx = E.get("^IRX")["close"].reindex(idx).ffill().shift(1).bfill()
    return (irx / 100 / 252).to_numpy()


# ------------------------------------------------------------------ research-engine variants
def run_engine(rc: dict) -> pd.Series:
    E.RANK, E.PARK, E.DYN, E.CORR_MAX = rc.get("rank"), rc.get("park"), rc.get("dyn"), rc.get("corr")
    meta.XS_UNIVERSE[:] = UNIV
    s = rc["strat"]
    if s == "parts":
        res = E.run([(FN[a], p) for a, p in rc["parts"]], {}, UNIV)
    elif s == "blend":
        res = E.run({"blend": [(FN[a], p) for a, p in rc["parts"]]}, {}, UNIV)
    else:
        res = E.run(FN[s], rc["p"], UNIV)
    a, b = PERIOD
    rdf = pd.concat({t: r[(r.index >= a) & (r.index <= b)] for t, (r, _) in res.items()}, axis=1).fillna(0.0)
    tmap = {t: [x for x in tr if a <= x["entry_date"] <= b] for t, (_, tr) in res.items()}
    k = rc.get("k", K)
    port = E.slot_portfolio(rdf, tmap, k, seed=SEED)
    if rc.get("tbill"):
        # occupancy of the same selection: the same trades in the same seeded order on a matrix of ones
        park, dyn = E.PARK, E.DYN
        E.PARK, E.DYN = None, None
        occ = E.slot_portfolio(pd.DataFrame(1.0, index=rdf.index, columns=rdf.columns), tmap, k, seed=SEED)
        E.PARK, E.DYN = park, dyn
        idle = (1 - occ.clip(upper=1.0)).to_numpy()
        if park:
            px = E.get(park[0])["close"]
            on = (px > px.rolling(park[1]).mean()).shift(1).reindex(rdf.index).fillna(False).to_numpy()
            idle = idle * (1 - on)
        port = port + idle * rf_daily(rdf.index)
    E.RANK = E.PARK = E.DYN = E.CORR_MAX = None
    return port


# ------------------------------------------------------------------ swing4 / swing5 variants
_S: dict = {}


def swing_specs() -> dict:
    """idea name -> (entry fn, policy, key, size, park, portfolio kind)."""
    if "spec" in _S:
        return _S["spec"]
    from indicator_lab.swing4 import lab as L
    from indicator_lab.swing4 import phase2 as P2
    ctx = L.load_ctx()
    for t, cx in ctx.items():
        cx["_t"] = t
    spec = {"v2 (no model)": (P2.v2, P2.BASE, None, None, False, "lab"),
            "v3 (baseline)": (L.v3_entry, P2.BASE, None, None, False, "lab"),
            "v3 stable features": (P2.stable, P2.BASE, None, None, False, "lab")}
    fams = [P2.ideas_A(), P2.ideas_B(), P2.ideas_C(), P2.ideas_D(), P2.ideas_F(), P2.ideas_E(ctx), P2.ideas_G()]
    for fam in fams:
        for name, sp, _, _, _ in fam:
            spec[name] = (sp.get("entry", P2.v3), sp.get("pol", P2.BASE), sp.get("key"), sp.get("size"),
                          sp.get("park", False), "lab")
    spec.update(swing5_specs(ctx))
    _S["spec"], _S["ctx"] = spec, ctx
    return spec


def swing5_specs(ctx) -> dict:
    """The swing5 phase-0 systems and model variants, rebuilt as swing5/phase0.py defines them (on DEV-U here)."""
    from indicator_lab import data
    from indicator_lab.swing4 import lab as L
    from indicator_lab.swing5 import phase0 as P0
    out = {"v4 complete (breakouts + SPY parking + regime)": (P0.v4_entry, None, None, None, True, "port5"),
           "v4 breakouts only (idle = T-bills)": (P0.v4_entry, None, None, None, False, "port5"),
           "v3 complete (no regime rule)": (L.v3_entry, None, None, None, True, "port5"),
           "v3 breakouts only": (L.v3_entry, None, None, None, False, "port5")}
    tab = meta.candidate_table(data.DEV, 20, 20, 4.0, 0.7, 200)
    tab_reg = tab[tab["spy_roc63"] <= P0.REGIME_MAX]
    mods = {"without spy_roc63/spy_up (15; rs63 keeps SPY inside)": (meta.YearlyModels(tab, feats=P0.NO_SPY, keep=0.75, l2=100.0), P0.NO_SPY),
            "no SPY at all: also without rs63 (14)": (meta.YearlyModels(tab, feats=P0.NO_SPY_RS, keep=0.75, l2=100.0), P0.NO_SPY_RS),
            "no SPY at all (14), trained on regime-passing breakouts": (meta.YearlyModels(tab_reg, feats=P0.NO_SPY_RS, keep=0.75, l2=100.0), P0.NO_SPY_RS)}
    for k in [k for k in mods if k.startswith("no SPY at all")]:   # the iterated sign-stable subset (phase0.main)
        sub = tab_reg if "regime" in k else tab
        keep = P0.stable_feats(P0.coef_table(*mods[k]))
        while True:
            mm = meta.YearlyModels(sub, feats=keep, keep=0.75, l2=100.0)
            k2 = P0.stable_feats(P0.coef_table(mm, keep))
            if k2 == keep or not k2:
                break
            keep = k2
        mods[f"{k}: sign-stable subset ({len(keep)})"] = (mm, keep)
    for k, (mdl, feats) in mods.items():
        out[k] = (P0.model_entry(P0.model_probs(ctx, mdl, feats)), None, None, None, True, "port5")
    return out


def run_swing(name: str) -> pd.Series:
    from indicator_lab.swing4 import lab as L
    from indicator_lab.swing5 import port as PT
    spec = swing_specs()
    if name not in spec:   # swing5 names are logged with a truncated tail
        hit = [k for k in spec if k.startswith(name.rstrip(".").rstrip("…")[:60])]
        name = hit[0]
    entry, pol, key, size, park, kind = spec[name]
    res = L.run(_S["ctx"], entry, pol or L.S2.DEFAULT)
    if kind == "port5":
        return PT.portfolio(res, K, SEED, park=park)["port"]
    return L.portfolio(res, K, SEED, key, size, park)["port"]


# ------------------------------------------------------------------ driver
def _one(item):
    tid, rc = item
    t0 = time.time()
    try:
        s = run_engine(rc) if rc["kind"] == "engine" else run_swing(rc["name"])
        s = s.reindex(_CAL).fillna(0.0)
        return tid, s.to_numpy(), None, time.time() - t0
    except Exception as ex:  # noqa: BLE001  (a variant that cannot be rebuilt is reported, not hidden)
        return tid, None, f"{type(ex).__name__}: {ex}", time.time() - t0


_CAL = None


def rebuild(trials, procs: int = 4) -> tuple[pd.DataFrame, dict]:
    global _CAL
    _CAL = calendar()
    for t in UNIV + ["SPY", "QQQ", "IWM", "^IRX", "^VIX"]:
        E.get(t)
    meta.market_breadth()
    todo = [(t.id, t.recon) for t in trials if t.recon is not None]
    swing = [x for x in todo if x[1]["kind"] != "engine"]
    if swing:
        swing_specs()       # build the context and the swing models once, before the workers fork
    cols, errs = {}, {}
    with Pool(procs) as pool:
        for i, (tid, arr, err, dt) in enumerate(pool.imap_unordered(_one, todo, chunksize=1)):
            if err:
                errs[tid] = err
            else:
                cols[tid] = arr
            print(f"[{i + 1}/{len(todo)}] {tid} {dt:.0f}s {err or ''}", flush=True)
    M = pd.DataFrame(cols, index=_CAL)
    M = M[[t for t, _ in todo if t in cols]]
    return M, errs


# ------------------------------------------------------------------ N and N_eff
def n_eff(M: pd.DataFrame) -> dict:
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    from sklearn.metrics import silhouette_score
    live = M.loc[:, M.std() > 0]
    C = live.corr().to_numpy()
    C = np.clip((C + C.T) / 2, -1, 1)
    np.fill_diagonal(C, 1.0)
    D = np.sqrt(0.5 * (1 - C))
    np.fill_diagonal(D, 0.0)
    Z = linkage(squareform(D, checks=False), method="average")
    sil = {}
    for k in range(2, min(len(C) - 1, 200) + 1):
        lab = fcluster(Z, k, criterion="maxclust")
        if len(set(lab)) > 1:
            sil[k] = float(silhouette_score(D, lab, metric="precomputed"))
    k_best = max(sil, key=sil.get)
    thr = {}
    for rho in (0.95, 0.9, 0.8, 0.7, 0.5):
        thr[rho] = int(len(set(fcluster(Z, np.sqrt(0.5 * (1 - rho)), criterion="distance"))))
    ev = np.sort(np.linalg.eigvalsh(C))[::-1]
    share = np.cumsum(ev) / ev.sum()
    n90 = int(np.searchsorted(share, 0.90) + 1)
    iu = np.triu_indices_from(C, 1)
    rho_bar = float(C[iu].mean())
    return {"n_live": len(C), "dropped_flat": [c for c in M.columns if c not in live.columns], "k_silhouette": k_best,
            "silhouette": sil, "labels": dict(zip(live.columns, fcluster(Z, k_best, criterion="maxclust"))),
            "by_threshold": thr, "eig90": n90, "eig_share": share, "rho_bar": rho_bar,
            "n_rho": rho_bar + (1 - rho_bar) * len(C), "Z": Z, "C": C, "cols": list(live.columns)}


def inventory_frame(trials, errs: dict, M: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for t in trials:
        if t.recon is None:
            status, why = "nee", t.reason
        elif t.id in errs:
            status, why = "nee", "herbouw faalde: " + errs[t.id]
        elif t.id in M.columns and M[t.id].std() == 0:
            status, why = "leeg", "herbouwd, maar geen enkele trade op de basis"
        else:
            status, why = "ja", ("parameters deels afgeleid uit de tekst; " if t.inferred else "") + t.reason
        rows.append({"id": t.id, "beschrijving": t.desc, "parameters": json.dumps(t.params, default=str),
                     "datum": t.date, "bron": t.source, "groep": t.group, "geteld": t.counted,
                     "reconstrueerbaar": status, "toelichting": why.strip("; "), "tags": ",".join(t.tags)})
    return pd.DataFrame(rows)


def report(inv: pd.DataFrame, M: pd.DataFrame, ne: dict) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.cluster.hierarchy import dendrogram
    os.makedirs(OUT, exist_ok=True)
    cnt = inv[inv.geteld]
    line_ = cnt[cnt.groep.isin(["E", "swing4", "swing5"])]
    rec = line_[line_.reconstrueerbaar == "ja"]
    n_grid = int((line_.id.str.endswith(".grid")).sum())
    e33 = line_[(line_.groep == "E") & line_.id.str.extract(r"E(\d+)\.")[0].astype(float).le(33)]
    e19 = line_[(line_.groep == "E") & line_.id.str.extract(r"E(\d+)\.")[0].astype(float).le(19)]
    L = ["# Overfitting-meting — stap 1: trials-inventaris, N en N_eff\n",
         "Alleen meten: geen strategieregel is veranderd, niets is opnieuw gekozen of getuned. Varianten met een "
         "walk-forward-model bouwen dat model precies zoals de variant het definieerde (jaarlijkse refits).\n",
         "## Gemeenschappelijke basis\n",
         f"- universum: DEV-U, {len(UNIV)} ontwikkeltickers (bevat alle universums van E0–E60; geen v4- of v5-holdoutticker)",
         f"- periode: {PERIOD[0].date()} .. {PERIOD[1].date()} ({len(M)} handelsdagen), data afgekapt vóór de v4-tijdholdout",
         "- portefeuille: max 10 posities van 10%, signalen op dezelfde dag in één vaste willekeurige volgorde (seed 0), "
         "lege slots 0% tenzij de variant zelf parkeert; kosten 0,1% per kant op elke fill",
         "- dagrendementen op portefeuilleniveau, één kolom per variant\n",
         "## Aantallen\n",
         "| | aantal |\n|---|---|",
         f"| rijen in trials_inventory.csv | {len(inv)} |",
         f"| **getelde trials in de v3/v4-lijn (E0–E60, swing4, swing5) = N** | **{len(line_)}** |",
         f"|   waarvan E-experimenten | {int((line_.groep == 'E').sum())} |",
         f"|   waarvan swing4-ronde (fase 1–2, gelogd) | {int((line_.groep == 'swing4').sum())} |",
         f"|   waarvan swing5 fase 0 | {int((line_.groep == 'swing5').sum())} |",
         f"|   waarvan placeholder voor een grid zonder vastgelegde punten | {n_grid} |",
         f"| gereconstrueerd met een dagreeks | {len(rec)} ({len(rec) / len(line_) * 100:.0f}%) |",
         f"| niet gereconstrueerd | {len(line_) - len(rec)} |",
         f"| niet geteld: herbeoordelingen, Pine, R1–R7, dubbele | {int((~inv.geteld & inv.groep.isin(['E', 'swing4', 'swing5', 'R'])).sum())} |",
         f"| buiten de lijn (scanner-voorloper uit git, 20/21-strategie), apart gelijst | "
         f"{int(inv.groep.isin(['scanner', 'twenty']).sum())} |\n",
         "Controle tegen de totalen die het log zelf noemt: "
         f"E0–E19 hier {len(e19)} trials (log: \"~150 variants\"), E0–E33 hier {len(e33)} (log: \"~35 families and ~250 "
         "variants\"). " + ("Het log noemt méér dan hier is vastgelegd; het verschil zit in grids waarvan de punten niet "
                            "zijn opgeschreven. " if len(e33) < 250 else "De telling hier is minstens zo hoog als het log. ")]
    n_strict = max(len(line_), len(line_) - len(e33) + 250)
    L.append(f"Strengste telling (log-totaal voor E0–E33 als dat hoger is): **N_streng = {n_strict}**. "
             f"Met de scanner-voorloper erbij: {n_strict + int((inv.groep == 'scanner').sum())}.\n")
    L.append("## Effectief aantal onafhankelijke trials (op de gereconstrueerde reeksen)\n")
    L.append(f"Correlatiematrix van {ne['n_live']} dagreeksen ({len(ne['dropped_flat'])} zonder enige trade weggelaten). "
             f"Gemiddelde paarsgewijze correlatie ρ̄ = {ne['rho_bar']:.2f}.\n")
    L.append("| methode | N_eff |\n|---|---|")
    L.append(f"| hiërarchische clustering (afstand √(½(1−ρ)), average linkage), aantal clusters met de hoogste "
             f"silhouette-score | **{ne['k_silhouette']}** |")
    for rho, k in ne["by_threshold"].items():
        L.append(f"| zelfde boom, afgesneden waar clusters onderling ρ ≥ {rho} hebben | {k} |")
    L.append(f"| eigenwaarden van de correlatiematrix die samen 90% van de variantie verklaren | **{ne['eig90']}** |")
    L.append(f"| ρ̄ + (1 − ρ̄)·N (Bailey e.a., gemiddelde-correlatie-benadering) | {ne['n_rho']:.0f} |\n")
    L.append("Niet-gereconstrueerde varianten zitten niet in de matrix. Bijna allemaal zijn het buren van wel "
             "gereconstrueerde varianten (andere slots, kosten, of grids rond een vastgelegd punt), dus ze vallen vrijwel "
             "zeker in bestaande clusters; als bovengrens schaal ik N_eff mee met N: "
             f"{ne['k_silhouette']} × {n_strict}/{ne['n_live']} = {ne['k_silhouette'] * n_strict / ne['n_live']:.0f}.\n")
    # cluster table
    lab = pd.Series(ne["labels"])
    names = inv.set_index("id")["beschrijving"]
    L.append("## De clusters (silhouette-snede)\n")
    L.append("| cluster | varianten | voorbeelden |\n|---|---|---|")
    for c, g in sorted(lab.groupby(lab), key=lambda z: -len(z[1])):
        ex = ", ".join(f"{i}" for i in list(g.index)[:6])
        L.append(f"| {c} | {len(g)} | {ex}{' …' if len(g) > 6 else ''} |")
    tagged = inv[inv.tags != ""][["id", "tags"]]
    L.append("\nWaar de eindsystemen zitten: " + "; ".join(
        f"{r.tags} = {r.id} (cluster {lab.get(r.id, '–')})" for r in tagged.itertuples()) + "\n")
    # figures
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    ks = sorted(ne["silhouette"])
    ax[0].plot(ks, [ne["silhouette"][k] for k in ks])
    ax[0].axvline(ne["k_silhouette"], color="gray", ls="--")
    ax[0].set_title("silhouette vs aantal clusters")
    ax[1].plot(np.arange(1, len(ne["eig_share"]) + 1), ne["eig_share"])
    ax[1].axhline(0.9, color="gray", ls="--")
    ax[1].axvline(ne["eig90"], color="gray", ls=":")
    ax[1].set_xscale("log")
    ax[1].set_title("cumulatief aandeel variantie (eigenwaarden)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "s1_neff.png"), dpi=100)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(14, 5))
    dendrogram(ne["Z"], no_labels=True, ax=ax, color_threshold=np.sqrt(0.5 * (1 - 0.7)))
    ax.axhline(np.sqrt(0.5 * (1 - 0.7)), color="gray", ls="--")
    ax.set_title("dendrogram van de varianten (afstand √(½(1−ρ)); stippellijn ρ = 0.7)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "s1_dendrogram.png"), dpi=100)
    plt.close(fig)
    L.append("![N_eff](s1_neff.png)\n\n![dendrogram](s1_dendrogram.png)\n")
    # not rebuilt
    L.append("## Niet gereconstrueerd (getelde trials)\n")
    nr = line_[line_.reconstrueerbaar != "ja"]
    L.append("| reden | aantal | ids |\n|---|---|---|")
    for why, g in nr.groupby("toelichting"):
        L.append(f"| {why} | {len(g)} | {', '.join(g.id[:8])}{' …' if len(g) > 8 else ''} |")
    inf = line_[(line_.reconstrueerbaar == "ja") & line_.toelichting.str.contains("afgeleid", na=False)]
    L.append(f"\nGereconstrueerd met deels afgeleide parameters (de tekst geeft geen volledige specificatie): {len(inf)} "
             f"— {', '.join(inf.id)}.\n")
    return "\n".join(L)


def main():
    os.makedirs(WORK, exist_ok=True)
    trials = TR.all_trials()
    if os.path.exists(MATRIX) and "--rebuild" not in sys.argv:
        M = pd.read_csv(MATRIX, index_col=0, parse_dates=True)
        errs = json.load(open(MATRIX + ".errors.json")) if os.path.exists(MATRIX + ".errors.json") else {}  # noqa: SIM115
    else:
        M, errs = rebuild(trials)
        M.to_csv(MATRIX, float_format="%.7g")
        with open(MATRIX + ".errors.json", "w") as fh:
            json.dump(errs, fh, indent=1)
    inv = inventory_frame(trials, errs, M)
    inv.to_csv(os.path.join(HERE, "trials_inventory.csv"), index=False)
    line_ids = set(inv[inv.geteld & inv.groep.isin(["E", "swing4", "swing5"])].id)
    ne = n_eff(M[[c for c in M.columns if c in line_ids]])
    txt = report(inv, M, ne)
    with open(os.path.join(OUT, "step1_trials.md"), "w") as fh:
        fh.write(txt)
    with open(os.path.join(WORK, "neff.json"), "w") as fh:
        json.dump({k: ne[k] for k in ("n_live", "k_silhouette", "by_threshold", "eig90", "rho_bar", "n_rho")} |
                  {"labels": {k: int(v) for k, v in ne["labels"].items()}}, fh, indent=1, default=str)
    print(txt)


if __name__ == "__main__":
    main()
