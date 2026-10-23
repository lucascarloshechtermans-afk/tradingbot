"""Registry of every variant that was ever tried on the way to swing v3/v4, with how to rebuild it.

Sources: the experiment log in PROGRESS.md (E0-E60, written as prose and tables, no code of their own was kept),
swing4/experiments.csv (phase 1-3 of the v4 round), swing5/experiments.csv (v5 phase 0), the git history (the
scanner the research started from) and twenty/experiments_20in21.csv (a different strategy).

Counting rule (strict): every grid point and every named variant that produced a result is one trial, also when
it was a robustness neighbour or a stress test. Not counted: pure re-evaluations of an already counted variant on
another universe or with more data (E29, E35, E40, E47, E52, swing4 P3) and work without a variant (Pine, R1-R7).
Where the prose gives a range ("1.18-1.23") without the grid, the most likely grid is used and the row is
flagged `inferred`. Grids that the log mentions without their points get one placeholder row each; their real
size is covered by the stated totals ("~150 variants" after E19, "~250" after E33), reported next to the count.

`recon` says how the daily return series is rebuilt on the common basis (see inventory.py):
  {"kind": "engine", "strat": name, "p": params, ...portfolio options}   research engine (evaluate.py)
  {"kind": "swing4", "name": idea}                                       swing4 lab, phase2 definitions
  {"kind": "swing5", "name": idea}                                       swing5 phase 0 definitions
  None -> not rebuilt; `reason` says why.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import pandas as pd

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(os.path.dirname(HERE))
LAB = os.path.dirname(HERE)


@dataclass
class Trial:
    id: str
    group: str
    desc: str
    params: dict
    date: str
    source: str
    counted: bool = True
    recon: dict | None = None
    reason: str = ""
    inferred: bool = False
    tags: list = field(default_factory=list)


V1 = {"n": 20, "m": 20, "trail": 4.0}
V2 = {**V1, "ibs_min": 0.7}
V3 = {**V2, "keep": 0.75, "l2": 100.0}
V3S = {**V3, "stop": 4.0}                 # E51 onward: entry-day protective stop
PARK = ("SPY", 200)                       # v3.1 parking rule (E48)


def eng(strat, p, **opt):
    return {"kind": "engine", "strat": strat, "p": p, **opt}


def _progress_lines() -> dict:
    """'E7' -> line number of its heading in PROGRESS.md."""
    out = {}
    with open(os.path.join(ROOT, "PROGRESS.md")) as fh:
        for i, ln in enumerate(fh, 1):
            m = re.match(r"### (E\d+|R\d+) ", ln)
            if m and m.group(1) not in out:
                out[m.group(1)] = i
    return out


# --------------------------------------------------------------------------- E0-E60
def e_trials() -> list[Trial]:
    lines = _progress_lines()
    T: list[Trial] = []

    def add(e: int, sub: str, desc: str, params: dict, recon=None, reason: str = "", counted=True, inferred=False,
            tags=None):
        date = "2026-10-20" if e <= 39 else "2026-10-21"
        T.append(Trial(f"E{e}.{sub}", "E", desc, params, date, f"PROGRESS.md E{e} (r.{lines.get(f'E{e}', '?')})",
                       counted, recon, reason, inferred, tags or []))

    def ga(e, sub, desc, strat, p, inferred=False, tags=None, **opt):
        add(e, sub, desc, {"strategy": strat, **p, **{k: v for k, v in opt.items()}},
            eng(strat, p, **opt), inferred=inferred, tags=tags)

    def grid(e, desc, why):
        add(e, "grid", desc, {}, None, why)

    # E0 baseline v0
    ga(0, "v0", "repo Bullish Pullback als indicator (2 ATR stop, 3.35 ATR target, 5 bars)", "v0", {"tol": 1.5})
    # E1 RSI2 mean reversion
    ga(1, "rsi2_10_sma5", "RSI2<10 + SMA200, exit close>SMA5 of RSI2>90", "rsi2", {"lo": 10, "exit_ma": 5})
    ga(1, "rsi2_20_sma10", "RSI2<20, exit SMA10 (beste IS-gridpunt)", "rsi2", {"lo": 20, "exit_ma": 10})
    grid(1, "overige IS-gridpunten RSI2-drempel x exit-MA", "gridpunten niet vastgelegd in het log")
    # E2 EMA trend
    ga(2, "ema20_50_t3", "EMA 20/50 cross + SMA200, 3 ATR trail", "ema", {"fast": 20, "slow": 50, "trail": 3.0})
    ga(2, "ema10_50", "EMA 10/50 cross + SMA200, geen trail", "ema", {"fast": 10, "slow": 50})
    # E3 Donchian
    for n, m, tr in ((55, 20, 3.0), (20, 40, None), (20, 40, 4.0), (20, 20, 4.0), (16, 20, 4.0), (24, 20, 4.0),
                     (20, 16, 4.0), (20, 24, 4.0), (20, 20, 3.2), (20, 20, 4.8)):
        p = {"n": n, "m": m} | ({"trail": tr} if tr else {})
        ga(3, f"don{n}_{m}_{tr}", f"Donchian {n}/{m}, trail {tr}", "donchian", p,
           tags=["v1"] if (n, m, tr) == (20, 20, 4.0) else None)
    grid(3, "IS-grid n x m x trail en walk-forward hertuning", "gridpunten niet vastgelegd in het log")
    # E4 filters on v1
    for r in (200, 100, 50):
        ga(4, f"regime{r}", f"v1 + SPY > SMA{r}", "breakout", {**V1, "regime": r})
    for r in (126, 63, 252):
        ga(4, f"rs{r}", f"v1 + RS vs SPY {r}d", "breakout", {**V1, "rs": r})
    ga(4, "regime_rs", "v1 + SPY>SMA200 + RS126", "breakout", {**V1, "regime": 200, "rs": 126}, inferred=True)
    for a in (20, 25):
        ga(4, f"adx{a}", f"v1 + ADX >= {a}", "breakout", {**V1, "adx_min": a})
    for v in (0.8, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5):
        ga(4, f"vol{v}", f"v1 + breakout-volume >= {v}x SMA50", "breakout", {**V1, "vol_mult": v})
    for x in (2, 2.5, 3, 3.5, 4, 5):
        ga(4, f"ext{x}", f"v1 + max {x} ATR boven SMA50", "breakout", {**V1, "ext_max": x})
    ga(4, "vol1.2_ext3", "v1 + volume 1.2 + extensie 3", "breakout", {**V1, "vol_mult": 1.2, "ext_max": 3})
    # E5 v1 + RSI2 in shared slots
    for lo, xm in ((10, 5), (5, 5), (20, 10)):
        add(5, f"v1+rsi2_{lo}_{xm}", f"v1 breakout + RSI2<{lo}/SMA{xm} in gedeelde slots",
            {"parts": ["breakout v1", f"rsi2 lo {lo} exit {xm}"]},
            eng("parts", {}, parts=[("breakout", V1), ("rsi2", {"lo": lo, "exit_ma": xm})]))
    # E6 exits / sizing on v1
    for k, v, d in (("stop", 2.0, "init stop 2 ATR"), ("stop", 3.0, "init stop 3 ATR"), ("be", 2.0, "breakeven +2 ATR"),
                    ("be", 3.0, "breakeven +3 ATR"), ("max_bars", 20, "time stop 20"), ("max_bars", 40, "time stop 40"),
                    ("exit_ema", 10, "exit close<EMA10"), ("exit_ema", 20, "exit close<EMA20"),
                    ("vol_target", 1.5, "vol-sizing 1.5%"), ("vol_target", 2.0, "vol-sizing 2%"),
                    ("vol_target", 3.0, "vol-sizing 3%")):
        ga(6, f"{k}{v}", f"v1 + {d}", "breakout", {**V1, k: v})
    ga(6, "fixed3", "vaste 3 ATR stop zonder trail", "breakout", {"n": 20, "m": 20, "stop": 3.0})
    # E7 IBS -> v2
    for v in (0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9):
        ga(7, f"ibs{v}", f"v1 + IBS >= {v}", "breakout", {**V1, "ibs_min": v}, tags=["v2"] if v == 0.7 else None)
    for k, v in (("n", 16), ("n", 24), ("m", 16), ("m", 24), ("trail", 3.2), ("trail", 4.8)):
        ga(7, f"v2_{k}{v}", f"v2 buur {k}={v}", "breakout", {**V2, k: v})
    grid(7, "walk-forward grid incl. IBS 0/0.5/0.7", "hertuningsgrid niet vastgelegd")
    # E8
    for tr in (4.0, 3.5, 3.0):
        ga(8, f"closestop{tr}", f"v2, trail {tr} alleen op slotkoers", "breakout", {**V2, "trail": tr, "close_stop": True})
    ga(8, "closebreak", "v2, breakout van hoogste slot", "breakout", {**V2, "close_break": True})
    for tl in (50, 100, 150):
        ga(8, f"trend{tl}", f"v2, trend-MA {tl}", "breakout", {**V2, "trend_len": tl})
    ga(8, "slope20", "v2, SMA200 stijgend over 20 bars", "breakout", {**V2, "slope": 20})
    for k in (252, 126):
        ga(8, f"absmom{k}", f"v2, {k}d momentum > 0", "breakout", {**V2, "abs_mom": k})
    for g in (1, 2):
        ga(8, f"gap{g}", f"v2, skip gap-up > {g} ATR", "breakout", {**V2, "gap_max": g})
    for q in (0.2, 0.35):
        ga(8, f"squeeze{q}", f"v2, BB-squeeze pct <= {q}", "breakout", {**V2, "squeeze": q})
    # E9 pullback after breakout
    for w in (5, 10, 20):
        for lo in (10, 20, 30):
            ga(9, f"pb_w{w}_rsi{lo}", f"pullback na breakout ({w} bars, RSI2<{lo})", "brk_pb",
               {**V2, "within": w, "rsi_lo": lo}, inferred=True)
    add(9, "pb+v2", "pullback-variant + v2 in gedeelde slots", {}, None, "welke pullback-parameters niet vastgelegd")
    # E10
    for n in (30, 40, 55, 100, 252):
        ga(10, f"n{n}", f"v2 met n={n}", "breakout", {**V2, "n": n})
    ga(10, "n40m40", "v2 40/40", "breakout", {**V2, "n": 40, "m": 40})
    ga(10, "n55m30", "v2 55/30", "breakout", {**V2, "n": 55, "m": 30})
    for w in (10, 20):
        ga(10, f"wkema{w}", f"v2 + weekly close > weekly EMA{w}", "breakout", {**V2, "wk_ema": w})
    ga(10, "wkmacd", "v2 + weekly MACD-hist > 0", "breakout", {**V2, "wk_macd": True})
    for nh in (5, 10):
        ga(10, f"nearhigh{nh}", f"v2 binnen {nh}% van 52w-high", "breakout", {**V2, "near_high": nh})
    # E11
    for a in (1.0, 1.25, 1.5, 2.0):
        ga(11, f"atrmin{a}", f"v2 + ATR% >= {a}", "breakout", {**V2, "atr_pct_min": a})
    for e in (0.2, 0.3, 0.4):
        ga(11, f"er50_{e}", f"v2 + ER50 >= {e}", "breakout", {**V2, "er_min": e, "er_n": 50})
    for e in (0.3, 0.4):
        ga(11, f"er20_{e}", f"v2 + ER20 >= {e}", "breakout", {**V2, "er_min": e, "er_n": 20})
    # E12 ranking same-day signals (v2)
    for f in ("roc21", "roc63", "roc126", "roc252", "rs63", "atr_pct", "rsi14", "ibs", "ext50", "rvol", "ret_vol"):
        for hi in (True, False):
            ga(12, f"rank_{f}_{'hi' if hi else 'lo'}", f"v2, rangschik op {f} ({'hoog' if hi else 'laag'} eerst)",
               "breakout", V2, rank=(f, hi))
    # E13
    for at, tt in ((4, 2.5), (6, 2.5), (6, 3.0), (8, 3.0)):
        ga(13, f"tight{at}_{tt}", f"v2, trail -> {tt} ATR na +{at} ATR", "breakout",
           {**V2, "tight_after": at, "tight_trail": tt}, inferred=True)
    for v in (0.8, 0.9, 1.0):
        ga(13, f"vdry{v}", f"v2 + volume dry-up <= {v}", "breakout", {**V2, "vdry": v})
    for v in (1.0, 1.3):
        ga(13, f"range{v}", f"v2 + breakout-range >= {v} ATR", "breakout", {**V2, "range_min": v})
    for v in (4, 7):
        ga(13, f"nr{v}", f"v2 + NR{v} voor de breakout", "breakout", {**V2, "nr": v})
    # E14 ensembles (v2 parts)
    def v2n(n, **kw):
        return ("breakout", {**V2, "n": n, **kw})
    add(14, "parts10_20_55", "10/20/55 als drie losse delen (eigen slots)", {"parts": [10, 20, 55]},
        eng("parts", {}, parts=[v2n(10), v2n(20), v2n(55)]), inferred=True)
    add(14, "parts20_40", "20/40 als twee losse delen", {"parts": [20, 40]},
        eng("parts", {}, parts=[v2n(20), v2n(40)]), inferred=True)
    for ns in ((10, 20, 55), (10, 20, 40), (15, 20, 30), (20, 55), (10, 20)):
        add(14, "blend" + "_".join(map(str, ns)), f"blend {ns}: één positie per ticker, grootte = aandeel delen long",
            {"blend": list(ns)}, eng("blend", {}, parts=[v2n(n) for n in ns]), inferred=True)
    for tr in (3.0, 5.0):
        add(14, f"blend10_20_55_t{tr}", f"blend 10/20/55 met trail {tr}", {"blend": [10, 20, 55], "trail": tr},
            eng("blend", {}, parts=[v2n(n, trail=tr) for n in (10, 20, 55)]), inferred=True)
    # E15 classic families
    for kind in ("supertrend", "keltner", "macd", "ichimoku", "aroon", "bb", "roc"):
        for ib in (None, 0.7):
            p = {"kind": kind, "m": 20, "trail": 4.0} | ({"ibs_min": ib} if ib else {})
            ga(15, f"{kind}_{'ibs' if ib else 'raw'}", f"{kind} als entry{' + IBS>=0.7' if ib else ''}, v2-exits",
               "family", p)
    # E16
    for m in (20, 15):
        ga(16, f"closelow{m}", f"v2, exit onder laagste slot van {m}", "breakout", {**V2, "m": m, "exit_close_low": True})
    for m in (50, 20):
        ga(16, f"exitsma{m}", f"v2, exit onder SMA{m}", "breakout", {**V2, "m": m, "exit_sma": True})
    for f in (20, 40):
        ga(16, f"fresh{f}", f"v2, alleen verse breakout ({f})", "breakout", {**V2, "fresh": f})
    for c in (10, 20):
        ga(16, f"cont{c}", f"v2, alleen vervolg-breakout ({c})", "breakout", {**V2, "cont": c})
    for nm, mo in (("novapr", [11, 12, 1, 2, 3, 4]), ("mayoct", [5, 6, 7, 8, 9, 10]),
                   ("skipsepoct", [1, 2, 3, 4, 5, 6, 7, 8, 11, 12])):
        ga(16, nm, f"v2, entries alleen maanden {mo}", "breakout", {**V2, "months": mo})
    # E17 meta-labeling on v1
    for k in (0.3, 0.5, 0.7):
        ga(17, f"v1meta_keep{k}", f"model op v1-basis, keep {k}", "meta", {**V1, "keep": k, "l2": 10.0})
    for l2 in (1.0, 100.0):
        ga(17, f"v1meta_l2_{l2}", f"model op v1-basis, l2 {l2}", "meta", {**V1, "keep": 0.5, "l2": l2})
    for i in (1, 2):
        add(17, f"v1meta_6feat_{i}", "klein 6-feature model op v1-basis", {}, None, "welke 6 features niet vastgelegd")
    # E18 meta on v2 -> v3
    for k in (0.6, 0.7, 0.75, 0.8, 0.9):
        ga(18, f"keep{k}", f"v2 + model keep {k} (l2 100)", "meta", {**V3, "keep": k},
           tags=["v3_engine"] if k == 0.75 else None)
    for l2 in (30.0, 300.0, 1000.0):
        ga(18, f"l2_{l2}", f"v2 + model l2 {l2} (keep 0.75)", "meta", {**V3, "l2": l2})
    for k, v in (("n", 16), ("n", 24), ("m", 16), ("m", 24), ("trail", 3.2), ("trail", 4.8)):
        ga(18, f"v3_{k}{v}", f"v3 buur {k}={v}", "meta", {**V3, k: v})
    for k in (0.6, 0.75, 0.9):
        ga(18, f"4feat_keep{k}", f"4-feature model (rvol, spy_roc63, er20, bbw_pct) keep {k}", "meta",
           {**V3, "keep": k, "feats": ["rvol", "spy_roc63", "er20", "bbw_pct"]}, inferred=True)
    # E19
    for s in (0.25, 0.5):
        ga(19, f"lowsize{s}", f"v3, afgewezen breakouts op {int(s * 100)}% grootte", "meta", {**V3, "low_size": s})
    F = __import__("indicator_lab.meta", fromlist=["FEATS"]).FEATS
    for nm, extra in (("winter", ["winter"]), ("spyvol", ["spy_vol20"]), ("volratio", ["vol_ratio"]),
                      ("all3", ["winter", "spy_vol20", "vol_ratio"])):
        ga(19, f"feat_{nm}", f"v3-model + {'+'.join(extra)}", "meta", {**V3, "feats": F + extra})
    # E20 stress tests
    for k in (3, 5, 8):
        ga(20, f"v3_K{k}", f"v3 met {k} slots", "meta", V3, k=k)
        ga(20, f"v2_K{k}", f"v2 met {k} slots", "breakout", V2, k=k)
    for nm in ("v3", "v2"):
        add(20, f"{nm}_cost0.25", f"{nm} met 0.25% kosten per kant", {"cost": 0.0025}, None,
            "andere kosten dan de gemeenschappelijke basis (0.1%/kant)")
    # E21 model instead of the SMA200 trend filter
    for tl in (None, 50, 100, 150):
        for k in (0.5, 0.75):
            ga(21, f"trend{tl}_keep{k}", f"model op basis met trend {tl or 'geen'}, keep {k}", "meta",
               {**V3, "trend_len": tl, "keep": k})
    # E22 partial profit (half at +X ATR) = blend of a run with and without the target
    def half(p, x):
        return eng("blend", {}, parts=[("meta", p), ("meta", {**p, "tgt": x})])
    for x in (2.0, 3.0, 3.5, 4.0, 5.0, 6.0):
        add(22, f"half{x}", f"v3, helft verkopen op +{x} ATR", {**V3, "half_at": x}, half(V3, x))
    for k, v in (("n", 16), ("n", 24), ("m", 16), ("m", 24), ("trail", 3.2), ("trail", 4.8), ("ibs_min", 0.56),
                 ("ibs_min", 0.84), ("keep", 0.6), ("keep", 0.9)):
        add(22, f"half4_{k}{v}", f"helft op +4 ATR, buur {k}={v}", {**V3, k: v, "half_at": 4.0}, half({**V3, k: v}, 4.0))
    for v in (0.56, 0.84):
        ga(22, f"v3_ibs{v}", f"v3 buur IBS {v}", "meta", {**V3, "ibs_min": v})
    # E23 training data
    for tr in ("dev+extra", "extra"):
        for k in (0.6, 0.75, 0.9):
            ga(23, f"train_{tr}_keep{k}", f"v3-model getraind op {tr}, keep {k}", "meta", {**V3, "train": tr, "keep": k})
    # E24
    for k in (0.4, 0.5, 0.6):
        ga(24, f"v1meta_dx_keep{k}", f"v1-basis + model (dev+extra), keep {k}", "meta",
           {**V1, "keep": k, "l2": 100.0, "train": "dev+extra"})
    for lm in (0.01, 0.03):
        ga(24, f"label{lm}", f"v3 met label 'trade > {lm * 100:.0f}%'", "meta", {**V3, "label_min": lm})
    # E25 mean reversion with a model
    MR = {"lo": 10.0, "exit_ma": 5, "train": "dev+extra", "l2": 100.0}
    ga(25, "mr_raw", "RSI2<10 MR zonder model", "meta_mr", {**MR, "keep": 1.0})
    for k in (0.3, 0.5, 0.7):
        ga(25, f"mr_keep{k}", f"RSI2 MR met eigen model, keep {k}", "meta_mr", {**MR, "keep": k})
    ga(25, "mr20", "RSI2<20 MR", "meta_mr", {**MR, "lo": 20.0, "keep": 1.0}, inferred=True)
    for k in (0.3, 0.7):
        add(25, f"v3+mr{k}", f"v3 + MR (top {int(k * 100)}%) in gedeelde slots", {"parts": ["v3", f"mr keep {k}"]},
            eng("parts", {}, parts=[("meta", V3), ("meta_mr", {**MR, "keep": k})]))
    # E26
    for fb in (5, 10, 15, 20):
        ga(26, f"fail{fb}", f"v3, exit als na {fb} bars nog <= entry", "meta", {**V3, "fail_bars": fb})
    for nm, p in (("w10_10", {"n": 10, "m": 10, "trail": 4.0}), ("w10_10_ibs", {"n": 10, "m": 10, "trail": 4.0, "ibs_min": 0.7}),
                  ("w4_4_ibs", {"n": 4, "m": 4, "trail": 4.0, "ibs_min": 0.7}), ("w4_4_notrail", {"n": 4, "m": 4, "ibs_min": 0.7}),
                  ("w10_5_t6", {"n": 10, "m": 5, "trail": 6.0})):
        ga(26, nm, f"v2-logica op weekbars {p}", "weekly", p, inferred=nm in ("w4_4_notrail", "w10_5_t6"))
    # E27
    ga(27, "moc", "v3, kopen op de slot van de signaaldag (MOC)", "meta", {**V3, "entry_close": True})
    # E28 breadth / VIX
    for nm, extra in (("b50", ["breadth50"]), ("b200", ["breadth200"]), ("vix", ["vix"]), ("vixrel", ["vix_rel"]),
                      ("all5", ["breadth50", "breadth200", "vix", "vix_rel", "spy_vol20"]),
                      ("all5w", ["breadth50", "breadth200", "vix", "vix_rel", "spy_vol20", "winter"])):
        ga(28, f"feat_{nm}", f"v3-model + {'+'.join(extra)}", "meta", {**V3, "feats": F + extra},
           inferred=nm.startswith("all5"))
    # E30 volatility universe filter
    for a in (1.5, 1.75, 2.0, 2.25, 2.5):
        ga(30, f"univatr{a}", f"v3 alleen tickers met 1j-gem. ATR% >= {a}", "meta", {**V3, "univ_atr": a})
    # E31 ranking on v3
    for f, hi in (("atr_pct", True), ("atr_pct", False), ("roc126", True), ("rs63", True), ("ret_vol", True)):
        ga(31, f"rank_{f}_{'hi' if hi else 'lo'}", f"v3, rangschik op {f}", "meta", V3, rank=(f, hi))
    # E32
    ga(32, "baserate", "v3, drempel = basisfrequentie", "meta", {**V3, "keep": 1.0})
    for tr in (4.0, 3.5, 4.5, 5.0):
        ga(32, f"trailonly{tr}", f"v3 alleen trail {tr} (geen 20d-low exit)", "meta", {**V3, "trail": tr, "m": 100000},
           inferred=True)
    ga(32, "trailonly_n16", "v3 alleen trail, n=16", "meta", {**V3, "n": 16, "m": 100000}, inferred=True)
    ga(32, "notrail", "v3 zonder trail (alleen 20d-low)", "meta", {**V3, "trail": None})
    ga(32, "low40", "v3 alleen 40d-low exit", "meta", {**V3, "m": 40, "trail": None})
    # E33 T-bill cash
    ga(33, "tbill", "v3, idle cash rentend tegen T-bill", "meta", V3, tbill=True)
    # E36
    for v in (2.0, 3.0, 4.0):
        ga(36, f"voltgt{v}", f"v3, equal-risk sizing {v}% ATR", "meta", {**V3, "vol_target": v})
    # E37 short side
    SH = {"n": 20, "m": 20, "trail": 4.0, "ibs_max": 0.3}
    ga(37, "short", "short-spiegel van v2", "short", SH)
    ga(37, "short_spy200", "short alleen als SPY < SMA200", "short", {**SH, "spy_ma": 200})
    ga(37, "short_t2.5", "short met trail 2.5", "short", {**SH, "trail": 2.5})
    ga(37, "short_tb10", "short met time stop 10", "short", {**SH, "max_bars": 10})
    add(37, "v3+short", "v3 + short in gedeelde slots", {"parts": ["v3", "short"]},
        eng("parts", {}, parts=[("meta", V3), ("short", SH)]))
    # E38 earnings
    for d in (3, 5, 7, 10):
        ga(38, f"earnskip{d}", f"v3, geen entry {d} sessies voor earnings", "meta", {**V3, "earn_skip": d})
    # E45
    ga(45, "rank_quality", "v3, hoogste modelkwaliteit eerst", "meta", V3, rank=("quality", True))
    for q in (0.5, 0.7, 0.8):
        ga(45, f"xsmom{q}", f"v3, alleen top {round((1 - q) * 100)}% 126d-momentum", "meta",
           {**V3, "xs_mom": q, "xs_n": 126})
    # E46 lookback x trail x slots
    for n in (20, 30, 40, 55):
        for tr in (3.0, 4.0, 5.0):
            for k in (10, 15, 20):
                if (n, tr, k) == (20, 4.0, 10):
                    continue
                if k == 10:
                    ga(46, f"n{n}_t{tr}_K{k}", f"v3 n={n} trail {tr}, {k} slots", "meta", {**V3, "n": n, "trail": tr}, k=k)
                else:
                    add(46, f"n{n}_t{tr}_K{k}", f"v3 n={n} trail {tr}, {k} slots", {**V3, "n": n, "trail": tr, "k": k},
                        None, "meer dan 10 posities: buiten de basis 'max 10 posities'")
    # E48 parking
    ga(48, "park_spy200", "v3.1: idle cash in SPY als SPY > SMA200", "meta", V3, park=PARK, tags=["v3.1_engine"])
    ga(48, "park_spy100", "idle cash in SPY als SPY > SMA100", "meta", V3, park=("SPY", 100))
    ga(48, "park_qqq200", "idle cash in QQQ als QQQ > SMA200", "meta", V3, park=("QQQ", 200))
    # E49
    for k in (3, 5, 8):
        ga(49, f"park_K{k}", f"v3.1 met {k} slots", "meta", V3, park=PARK, k=k)
    ga(49, "park_tbill", "v3.1 + T-bill op de rest", "meta", V3, park=PARK, tbill=True)
    # E50 dynamic size
    for d in (3, 5):
        ga(50, f"dyn{d}", f"v3.1, dynamische grootte min {d}", "meta", V3, park=PARK, dyn=d)
    # E51 entry-day stop (the published v3)
    ga(51, "stop4", "v3.1 + beschermende stop vanaf de instapdag", "meta", V3S, park=PARK)
    # E53
    for a in (10, 20, 50):
        ga(53, f"atr{a}", f"trail op ATR{a}", "meta", {**V3S, "atr_n": a}, park=PARK)
    for tr in (4.0, 3.5):
        ga(53, f"trailclose{tr}", f"chandelier vanaf hoogste slot, {tr} ATR", "meta",
           {**V3S, "trail": tr, "trail_close": True}, park=PARK)
    for g in (0.5, 1.0, 2.0):
        ga(53, f"maxgap{g}", f"skip als fill > {g} ATR boven signaalslot", "meta", {**V3S, "max_gap": g}, park=PARK)
    # E54 pyramiding (+ controls)
    for nm, extra in (("add1", {"add_atr": 1.0}), ("add2", {"add_atr": 2.0}), ("add3", {"add_atr": 3.0}),
                      ("time5", {"add_mode": "time", "add_bars": 5}), ("time10", {"add_mode": "time", "add_bars": 10}),
                      ("time20", {"add_mode": "time", "add_bars": 20}), ("profit2", {"add_mode": "profit", "add_atr": 2.0}),
                      ("profit3", {"add_mode": "profit", "add_atr": 3.0})):
        add(54, f"pyr_{nm}", f"pyramiding {extra}", {**V3S, **extra},
            eng("parts", {}, parts=[("meta", V3S), ("pyramid", {**V3S, **extra})], park=PARK))
    # E55 non-linear model
    M = __import__("indicator_lab.meta", fromlist=["POLY_FEATS"])
    poly = F + [f for f in M.POLY_FEATS if f not in F]
    for l2 in (100.0, 300.0, 1000.0):
        ga(55, f"poly_l2_{l2}", f"17 lineair + 21 polynoomtermen, l2 {l2}", "meta", {**V3S, "feats": poly, "l2": l2}, park=PARK)
    ga(55, "poly6", "polynoom op de 6 stabiele features", "meta", {**V3S, "feats": M.POLY_FEATS}, park=PARK)
    # E57
    ga(57, "trainbig", "live-model getraind op ~135 namen", "meta", {**V3S, "train": "big"}, park=PARK)
    # E58 dual momentum parking
    for nm, pk in (("dual126", ("DUAL", 200, 126, ["SPY", "QQQ"])), ("dual63", ("DUAL", 200, 63, ["SPY", "QQQ"])),
                   ("dual126_iwm", ("DUAL", 200, 126, ["SPY", "QQQ", "IWM"]))):
        ga(58, nm, f"dual-momentum parking {pk[2]}d {pk[3]}", "meta", V3S, park=pk)
    # E59 correlation guard
    for c in (0.8, 0.7, 0.6):
        ga(59, f"corr{c}", f"skip signaal met corr > {c} (60d) met een positie", "meta", V3S, park=PARK, corr=(c, 60))
    # not counted: re-evaluations and work without a variant
    for e, what in ((29, "v1/v2/v3 op de 48 TRAIN_EXTRA-tickers"), (34, "probe-posities (= E19 lowsize 0.25) op vers universum"),
                    (35, "v1/v2/v3 op VOLATILE"), (39, "Pine-optie half-profit"), (40, "E38 opnieuw met meer earnings-data"),
                    (47, "LOCKBOX-bevestiging v1/v2/v3"), (52, "instapstop op volatiele namen"), (56, "diagnose ATR-buckets"),
                    (60, "bootstrap-zekerheid")):
        add(e, "eval", what, {}, None, "herbeoordeling van al getelde varianten / geen nieuwe variant", counted=False)
    for e in range(41, 45):
        add(e, "pine", "Pine-werk (compileren, pariteit, dashboard)", {}, None, "geen strategievariant", counted=False)
    return T


# --------------------------------------------------------------------------- swing4 / swing5 logs
def log_trials() -> list[Trial]:
    T = []
    d4 = pd.read_csv(os.path.join(LAB, "swing4", "experiments.csv"))
    for _, r in d4.iterrows():
        src = f"swing4/experiments.csv id {r.id}"
        date = str(r.time)[:10]
        if r.phase == "P1" and r.idea != "v3 stable features":
            T.append(Trial(f"S4.{r.id}", "swing4", r.idea, {"model": r.idea}, date, src, True,
                           {"kind": "swing4", "name": r.idea},
                           tags=["v3"] if r.idea.startswith("v3") else ["v2_lab"]))
            T[-1].reason = "zelfde variant als E7/E18 (v2/v3); hier op DEV-U, met de swing4-simulator"
            T[-1].counted = False
        elif r.phase in ("P1", "P2", "P2-stack"):
            tags = []
            if r.idea.startswith("F1 SPY 63d return <= 0.03"):
                tags = ["v4"]
            if r.idea.startswith("G10 "):
                tags = ["v4_park"]
            T.append(Trial(f"S4.{r.id}", "swing4", r.idea, eval_params(r.params), date, src, True,
                           {"kind": "swing4", "name": r.idea}, tags=tags))
        else:
            T.append(Trial(f"S4.{r.id}", "swing4", r.idea, {}, date, src, False, None,
                           "holdout-evaluatie van de bevroren v3/v4 (geen nieuwe variant)"))
    d5 = pd.read_csv(os.path.join(LAB, "swing5", "experiments.csv"))
    for _, r in d5.iterrows():
        src = f"swing5/experiments.csv id {r.id}"
        dup = r.idea == "v4 model (17 features)"
        T.append(Trial(f"S5.{r.id}", "swing5", r.idea, eval_params(r.params), str(r.time)[:10], src, not dup,
                       None if dup else {"kind": "swing5", "name": r.idea},
                       "zelfde model als v4 (al geteld)" if dup else "",
                       tags=["v4_complete"] if r.idea.startswith("v4 complete") else []))
    return T


def eval_params(s) -> dict:
    import json
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return {"raw": str(s)}


# --------------------------------------------------------------------------- outside the v3/v4 line
SCANNER = [  # git history 2026-09-25/26: A/B decisions on the repo scanner (the source of baseline v0)
    ("3e19b98", "harde entry-gates (RS vs universe, regime, min R:R)"), ("4a609d1", "Momentum Continuation strakker"),
    ("ea106fb", "volume-vloer Support Bounce"), ("a000d4b", "min-score 70 i.p.v. 60"), ("1ce1629", "Volatility Contraction uit"),
    ("bd47853", "52-weeks context in Breakout-kwaliteit"), ("68dd9e0", "overextensie-filter"),
    ("b0423e8", "RS-drempel 70 -> 50 (A/B)"), ("749a4a3", "target-multiplier + Support Bounce strakker"),
    ("064cb6e", "terugdraaien 749a4a3 na backtest"), ("2e1bffc", "min_atr_pct filter"),
    ("048cd90", "opties D/C/B/A (4 varianten)"), ("25a20b0", "optie E: herkalibratie scores"),
    ("bb5c26c", "optie F: confluence-bonus"), ("b640a58", "prijsband $100-200"), ("5bd2078", "prijsband $50-300"),
    ("da34ac6", "opties 1-4 (EPS-gate, RS-bonus, VCP, Episodic Pivot)"), ("2a7ce11", "max market cap"),
    ("175ca90", "prijsband uit, ATR-vloer 3.0"), ("c656fe1", "overextensie-hypothese getoetst"),
]


def other_trials() -> list[Trial]:
    T = []
    for h, d in SCANNER:
        k = 4 if ("D/C/B/A" in d or "1-4" in d) else 1
        for i in range(k):
            T.append(Trial(f"SC.{h}.{i}", "scanner", d, {}, "2026-09-25", f"git {h}", False, None,
                           "repo-scanner (andere strategie, voorloper van baseline v0); code later gewijzigd"))
    d20 = pd.read_csv(os.path.join(LAB, "twenty", "experiments_20in21.csv"))
    for _, r in d20.iterrows():
        T.append(Trial(f"T20.{r.id}", "twenty", r.idea, {}, str(r.time)[:10], f"twenty/experiments_20in21.csv id {r.id}",
                       False, None, "andere strategie (+20% in 21 dagen), na v4 bevroren; geen v3/v4-kandidaat"))
    for i in range(1, 8):
        T.append(Trial(f"R{i}", "R", "betrouwbaarheidsstap Pine/Python", {}, "2026-10-22", f"PROGRESS.md R{i}", False,
                       None, "geen strategievariant (pariteit, data, Pine)"))
    return T


def all_trials() -> list[Trial]:
    return e_trials() + log_trials() + other_trials()


STATED = {  # totals the log itself gives (PROGRESS.md), used as a check on the count
    "E0-E19": ("~150 variants", 150, "E19"),
    "E0-E33": ("~35 families and ~250 variants", 250, "status after E33"),
}
