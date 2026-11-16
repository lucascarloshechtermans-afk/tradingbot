"""HVN absorption study - executes 00_preregistratie.txt (steps 0-4). Writes results_*.txt."""
from __future__ import annotations

import math, sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).parent))
from hvn_pine_twin import run_twin, STOP_BUF_PCT, MIN_RR  # noqa: E402

DATA = Path("/tmp/claude-0/-home-user-tradingbot/098d5ef9-632e-506f-8517-f959c4e449f7/scratchpad/spy")
OUT = Path(__file__).parent
RNG = np.random.default_rng(20261116)
TICKERS = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "ESF"]
SPEC = {t: dict(tick=0.01, comm=0.005) for t in TICKERS[:-1]}
SPEC["ESF"] = dict(tick=0.25, comm=2.50 / 50)          # commission per contract expressed in points
N_TRIALS = 200
NBOOT = 2000


def load(fn):
    d = pd.read_csv(fn, index_col=0)
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("America/New_York").tz_localize(None)
    d.columns = [c.lower() for c in d.columns]
    return d[["open", "high", "low", "close", "volume"]].astype(float)


def rth(d):
    t = d.index.time
    return d[(t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("16:00").time())]


def prepare(tk, mode):
    """mode P: 5m from 1m + 1m-colour split. mode S60: Yahoo 5m + CLV split."""
    is_es = tk == "ESF"
    if mode == "P":
        m1 = load(DATA / f"{tk}_1m.csv")
        if not is_es:
            m1 = rth(m1)
        m1 = m1[m1.volume.notna()]
        sg = np.sign(m1.close - m1.open)
        m1["buy"] = np.where(sg > 0, m1.volume, np.where(sg < 0, 0.0, m1.volume / 2))
        m1["sell"] = m1.volume - m1.buy
        b5 = m1.resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
                                       "buy": "sum", "sell": "sum"}).dropna(subset=["open"])
        buy, sell, hd = b5.buy.to_numpy(), b5.sell.to_numpy(), np.ones(len(b5), bool)
        res = m1
    else:
        b5 = load(DATA / f"{tk}_5m.csv")
        if not is_es:
            b5 = rth(b5)
        b5 = b5[b5.volume.notna()]
        r = (b5.high - b5.low).replace(0, np.nan); clv = ((b5.close - b5.low) / r).fillna(0.5)
        buy, sell, hd = (b5.volume * clv).to_numpy(), (b5.volume * (1 - clv)).to_numpy(), np.zeros(len(b5), bool)
        res = b5
    key = ((b5.index + pd.Timedelta(hours=6)).date if is_es else b5.index.date)
    tw = run_twin(b5[["open", "high", "low", "close", "volume"]], buy, sell, hd, np.array(key))
    return dict(tk=tk, mode=mode, b5=b5, res=res, tw=tw, key=np.array(key), step=5 if mode == "S60" else 1)


# ----------------------------------------------------------------------------- simulation
def fwd(ctx, t):
    """Resolution bars after the close of 5m chart bar t, same RTH day, before 16:00."""
    b5, res = ctx["b5"], ctx["res"]
    start = b5.index[t] + pd.Timedelta(minutes=5)
    day_end = pd.Timestamp(b5.index[t].date()) + pd.Timedelta(hours=16)
    return res[(res.index >= start) & (res.index < day_end)]


def first_passage(bars, up, dn):
    for o, h, l in zip(bars.open.values, bars.high.values, bars.low.values):
        hu, hd = h >= up or o >= up, l <= dn or o <= dn
        if hu and hd:
            return np.nan
        if hu:
            return 1.0
        if hd:
            return 0.0
    return np.nan


def sim_trade(ctx, t, d, entry, stop, target, tick, comm):
    bars = fwd(ctx, t)
    risk = abs(entry - stop)
    if risk <= 0 or len(bars) == 0:
        return None
    ef = entry + d * tick
    mae = mfe = 0.0; exit_raw = exit_fill = None; why = "EOD"; nmin = 0
    O, H, L, C, T = bars.open.values, bars.high.values, bars.low.values, bars.close.values, bars.index
    for i in range(len(bars)):
        o, h, l = O[i], H[i], L[i]
        nmin = (T[i] - bars.index[0]).total_seconds() / 60 + ctx["step"]
        adv = (l - entry) * d if d == 1 else (entry - h)
        fav = (h - entry) if d == 1 else (entry - l)
        mae, mfe = min(mae, adv / risk), max(mfe, fav / risk)
        gap_stop = (o <= stop) if d == 1 else (o >= stop)
        hit_stop = (l <= stop) if d == 1 else (h >= stop)
        gap_tgt = (o >= target) if d == 1 else (o <= target)
        hit_tgt = (h >= target) if d == 1 else (l <= target)
        if gap_stop:
            exit_raw, exit_fill, why = o, o - d * tick, "STOP"; break
        if gap_tgt:
            exit_raw = exit_fill = o; why = "TARGET"; break
        if hit_stop:
            exit_raw, exit_fill, why = stop, stop - d * tick, "STOP"; break
        if hit_tgt:
            exit_raw = exit_fill = target; why = "TARGET"; break
    if exit_raw is None:
        exit_raw = exit_fill = C[-1]; i = len(bars) - 1
    after_hit = np.nan
    if why == "STOP":
        rest = bars.iloc[i + 1:]
        after_hit = float(((rest.high >= target) if d == 1 else (rest.low <= target)).any()) if len(rest) else 0.0
    gross = (exit_raw - entry) * d / risk
    net = ((exit_fill - ef) * d - 2 * comm) / risk
    return dict(gross=gross, net=net, why=why, bars5=math.ceil(nmin / 5), mae=mae, mfe=mfe, risk=risk,
                cost_R=(2 * tick * (1 if why != "TARGET" else 0.5) + 2 * comm) / risk, after_target=after_hit,
                exit_px=exit_raw, exit_time=T[i])


def stops_for(ctx, e, kind):
    """kind 'real': entry dict from twin. Returns {S0..S3: stop price}."""
    d, ent, ext, a = e["dir"], e["entry"], e["ext"], e["atr"]
    s0 = ext - ent * STOP_BUF_PCT / 100 if d == 1 else ext + ent * STOP_BUF_PCT / 100
    s1 = ext - 0.25 * a if d == 1 else ext + 0.25 * a
    dist = max(abs(ent - s0), 1.0 * a); s2 = ent - dist if d == 1 else ent + dist
    nd = e.get("node")
    if nd is not None:
        s3 = nd.full_lo - 0.1 * a if d == 1 else nd.full_hi + 0.1 * a
    else:
        s3 = s1
    if (ent - s3) * d <= 0:
        s3 = s1
    return {"S0": s0, "S1": s1, "S2": s2, "S3": s3}


def target_for(nodes, ent, d, risk):
    best = None
    for nd in nodes:
        dd = (nd.price - ent) * d
        if dd >= MIN_RR * risk and (best is None or dd < (best - ent) * d):
            best = nd.price
    return (ent + 2 * risk * d if best is None else best), best is not None


def random_entries(ctx, n_draw):
    b5 = ctx["b5"]; tw = ctx["tw"]; out = []
    tt = b5.index.time
    ok = np.where((tt >= pd.Timestamp("09:35").time()) & (tt <= pd.Timestamp("15:30").time()))[0]
    ok = ok[ok > 30]
    if len(ok) == 0:
        return out
    for t in RNG.choice(ok, size=n_draw, replace=True):
        d = int(RNG.choice([-1, 1])); bar = b5.iloc[t]; a = tw["atr"][t]
        if np.isnan(a):
            continue
        nodes = tw["day_nodes"][ctx["key"][t]]
        ent = bar.close; ext = bar.low if d == 1 else bar.high
        nd = None
        cands = [x for x in nodes if (ent - (x.full_lo if d == 1 else x.full_hi)) * d > 0 and abs(ent - x.price) <= 3 * a]
        if cands:
            nd = min(cands, key=lambda x: abs(ent - x.price))
        e = dict(bar=t, dir=d, entry=ent, ext=ext, atr=a, node=nd)
        e["stops"] = stops_for(ctx, e, "random")
        r0 = abs(ent - e["stops"]["S0"])
        e["target"], e["target_is_hvn"] = target_for(nodes, ent, d, r0)
        out.append(e)
    return out


# ----------------------------------------------------------------------------- statistics
def boot_mean(vals, days, nboot=NBOOT):
    vals, days = np.asarray(vals, float), np.asarray(days)
    m = ~np.isnan(vals); vals, days = vals[m], days[m]
    if len(vals) == 0:
        return np.nan, np.nan, np.nan
    ud = np.unique(days); idx = {u: np.where(days == u)[0] for u in ud}
    bs = []
    for _ in range(nboot):
        pick = RNG.choice(ud, size=len(ud), replace=True)
        sel = np.concatenate([idx[p] for p in pick])
        bs.append(vals[sel].mean())
    return vals.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)


def dsr(r, n_trials=N_TRIALS):
    r = np.asarray(r, float); r = r[~np.isnan(r)]
    if len(r) < 3 or r.std(ddof=1) == 0:
        return np.nan, np.nan
    sr = r.mean() / r.std(ddof=1); T = len(r)
    g3 = pd.Series(r).skew(); g4 = pd.Series(r).kurt() + 3
    em = 0.5772156649
    sr0 = math.sqrt(1 / (T - 1)) * ((1 - em) * norm.ppf(1 - 1 / n_trials) + em * norm.ppf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(max(1e-12, 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))
    return sr, float(norm.cdf((sr - sr0) * math.sqrt(T - 1) / den))


def longest_loss_streak(x):
    best = cur = 0
    for v in x:
        cur = cur + 1 if v <= 0 else 0
        best = max(best, cur)
    return best


def bs_price(S, K, T, sig, r, call):
    if T <= 0 or sig <= 0:
        return max(0.0, (S - K) if call else (K - S))
    d1 = (math.log(S / K) + (r + 0.5 * sig * sig) * T) / (sig * math.sqrt(T)); d2 = d1 - sig * math.sqrt(T)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2) if call else K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


VIX1D = None


def option_pct(entry_time, exit_time, S0, S1, d):
    global VIX1D
    if VIX1D is None:
        v = load(DATA / "VIX1D_1d.csv"); VIX1D = v.close
        VIX1D.index = VIX1D.index.normalize()
    prev = VIX1D[VIX1D.index < pd.Timestamp(entry_time.date())]
    if len(prev) == 0:
        return np.nan
    sig = prev.iloc[-1] / 100
    close_t = pd.Timestamp(entry_time.date()) + pd.Timedelta(hours=16)
    T0 = (close_t - entry_time).total_seconds() / 60 / 525600; T1 = max(0.0, (close_t - exit_time).total_seconds() / 60 / 525600)
    K = round(S0); call = d == 1
    p0 = bs_price(S0, K, T0, sig, 0.04, call); p1 = bs_price(S1, K, T1, sig, 0.04, call)
    buy = p0 + 0.01 + 0.0065; sell = max(0.0, p1 - 0.01 - 0.0065)
    return (sell / buy - 1) * 100 if buy > 0 else np.nan


def summarize(rows, months, label, opt=False):
    if not rows:
        return f"{label:34s} n=0"
    net = np.array([r["net"] for r in rows]); gross = np.array([r["gross"] for r in rows])
    days = [r["day"] for r in rows]
    m, lo, hi = boot_mean(net, days)
    wins, losses = net[net > 0], net[net <= 0]
    wl = (wins.mean() / -losses.mean()) if len(wins) and len(losses) and losses.mean() < 0 else np.nan
    st2 = np.mean([(r["why"] == "STOP" and r["bars5"] <= 2) for r in rows]) * 100
    eq = np.cumsum(net) * 100; dd = (eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()
    s = (f"{label:34s} n={len(net):4d} win={np.mean(net > 0) * 100:5.1f}% grossR={gross.mean():+.3f} netR={m:+.3f} "
         f"[{lo:+.3f},{hi:+.3f}] med={np.median(net):+.2f} W/L={wl:4.2f} stop<=2bars={st2:5.1f}% "
         f"maxLossStreak={longest_loss_streak(net)} maxDD=${dd:,.0f} $/mnd={net.sum() * 100 / months:+,.0f}")
    if opt:
        op = [r.get("opt", np.nan) for r in rows]
        s += f" optie%/trade={np.nanmean(op):+.1f}"
    return s


# ----------------------------------------------------------------------------- main
def main():
    lines = {k: [] for k in ("stap0", "stap1", "stap2", "stap3", "stap4")}
    ctxs = {}
    for mode in ("S60", "P"):
        for tk in TICKERS:
            ctxs[(tk, mode)] = prepare(tk, mode)
    # STAP 0 - logic consistency: how many signals differ between 1m-colour logic and CLV logic on the same window
    for tk in TICKERS:
        P, S = ctxs[(tk, "P")], ctxs[(tk, "S60")]
        start = P["b5"].index[0]
        sP = {P["b5"].index[s["bar"]] for s in P["tw"]["signals"]}
        sS = {S["b5"].index[s["bar"]] for s in S["tw"]["signals"] if S["b5"].index[s["bar"]] >= start}
        lines["stap0"].append(f"{tk}: signalen zelfde venster  1m-kleur={len(sP)}  CLV-fallback={len(sS)}  beide={len(sP & sS)}  "
                              f"alleen-1m={len(sP - sS)}  alleen-CLV={len(sS - sP)}")
    for mode in ("S60", "P"):
        lines["stap1"].append(f"\n######## DATASET {mode} ########")
        pool = {"a_real": [], "a_mirror": [], "a_shift": [], "b_abs": [], "b1_touch": [], "c_conf": [], "c_unconf": []}
        for tk in TICKERS:
            ctx = ctxs[(tk, mode)]; b5, tw = ctx["b5"], ctx["tw"]; atr = tw["atr"]
            tt = b5.index.time; okt = lambda t: pd.Timestamp("09:35").time() <= tt[t] <= pd.Timestamp("15:30").time()
            day = lambda t: f"{tk}|{b5.index[t].date()}"
            # (a) real retests
            a_real = []
            for ev in tw["retests"]:
                t = ev["bar"]
                if not okt(t) or np.isnan(atr[t]):
                    continue
                s, L, A = ev["side"], ev["node"].price, atr[t]
                a_real.append((first_passage(fwd(ctx, t), L + A if s == 1 else L + A, L - A) if s == 1
                               else 1 - first_passage(fwd(ctx, t), L + A, L - A), day(t)))
            # (a) controls: mirrored / shifted node sets through the same state machine
            def ctrl_events(transform):
                evs = []; prev_nodes = None; cnodes = []
                for t in range(len(b5)):
                    nodes = tw["day_nodes"][ctx["key"][t]]
                    if nodes is not prev_nodes:
                        prev_nodes = nodes; a = atr[t] if not np.isnan(atr[t]) else np.nan
                        if np.isnan(a):
                            cnodes = []; continue
                        o0 = b5.open.iloc[t]; real = [n.price for n in nodes]; cnodes = []
                        for n in nodes:
                            Lp = transform(n.price, o0, a)
                            if Lp is None or min(abs(Lp - r) for r in real) < a:
                                continue
                            half = (n.hi - n.lo) / 2
                            cnodes.append(dict(lo=Lp - half, hi=Lp + half, price=Lp, active=True, armed=False))
                    hh, ll = b5.high.iloc[t], b5.low.iloc[t]
                    for n in cnodes:
                        inside = ll <= n["hi"] and hh >= n["lo"]
                        if n["active"]:
                            if inside and n["armed"]:
                                n["active"] = False
                                if okt(t) and not np.isnan(atr[t]):
                                    s = -1 if b5.close.iloc[t - 1] < n["lo"] else 1; L, A = n["price"], atr[t]
                                    fp = first_passage(fwd(ctx, t), L + A, L - A)
                                    evs.append((fp if s == 1 else (1 - fp if not np.isnan(fp) else np.nan), day(t)))
                            elif not inside:
                                n["armed"] = True
                return evs
            a_mir = ctrl_events(lambda L, o0, a: o0 - (L - o0))
            a_sh = []
            for _ in range(20):
                a_sh += ctrl_events(lambda L, o0, a: L + RNG.choice([-1, 1]) * RNG.uniform(1, 3) * a)
            # (b) absorption, fixed +-1 ATR from signal close
            sig_bars = {s["bar"] for s in tw["signals"]}
            b_abs = []
            for s in tw["signals"]:
                t = s["bar"]
                if np.isnan(atr[t]):
                    continue
                c0, A = b5.close.iloc[t], atr[t]; fp = first_passage(fwd(ctx, t), c0 + A, c0 - A)
                b_abs.append(((fp if s["dir"] == 1 else (1 - fp if not np.isnan(fp) else np.nan)), day(t)))
            b1 = []
            for ev in tw["retests"]:
                t = ev["bar"]
                if t in sig_bars or not okt(t) or np.isnan(atr[t]):
                    continue
                c0, A = b5.close.iloc[t], atr[t]; fp = first_passage(fwd(ctx, t), c0 + A, c0 - A)
                b1.append(((fp if ev["side"] == 1 else (1 - fp if not np.isnan(fp) else np.nan)), day(t)))
            # (c) confirmation: outcome from the close of bar t+1 in signal direction
            conf_bars = {e["sig_bar"] for e in tw["entries"]}
            c_conf, c_un = [], []
            for s in tw["signals"]:
                t = s["bar"] + 1
                if t >= len(b5) or np.isnan(atr[t]) or b5.index[t].date() != b5.index[s["bar"]].date():
                    continue
                c0, A = b5.close.iloc[t], atr[t]; fp = first_passage(fwd(ctx, t), c0 + A, c0 - A)
                val = fp if s["dir"] == 1 else (1 - fp if not np.isnan(fp) else np.nan)
                (c_conf if s["bar"] in conf_bars else c_un).append((val, day(t)))
            for k, v in (("a_real", a_real), ("a_mirror", a_mir), ("a_shift", a_sh), ("b_abs", b_abs), ("b1_touch", b1),
                         ("c_conf", c_conf), ("c_unconf", c_un)):
                pool[k] += v
            if tk == "SPY":
                lines["stap1"].append(f"-- SPY ({mode})")
                for k, v in (("a_real", a_real), ("a_mirror", a_mir), ("a_shift", a_sh), ("b_abs", b_abs), ("b1_touch", b1),
                             ("c_conf", c_conf), ("c_unconf", c_un)):
                    vals = [x for x, _ in v]; m, lo, hi = boot_mean(vals, [d for _, d in v])
                    lines["stap1"].append(f"   {k:9s} n={np.sum(~np.isnan(vals)):4d} (onbeslist {np.sum(np.isnan(vals))})  P={m:.3f} [{lo:.3f},{hi:.3f}]")
        lines["stap1"].append(f"-- GEPOOLD alle tickers ({mode})")
        for k, v in pool.items():
            vals = [x for x, _ in v]; m, lo, hi = boot_mean(vals, [d for _, d in v])
            lines["stap1"].append(f"   {k:9s} n={np.sum(~np.isnan(vals)):5d} (onbeslist {np.sum(np.isnan(vals))})  P={m:.3f} [{lo:.3f},{hi:.3f}]")
        # differences with CI (bootstrap of difference via combined resampling of days)
        def diff(a, b, name):
            va = np.array([x for x, _ in a], float); da = np.array([d for _, d in a])
            vb = np.array([x for x, _ in b], float); db = np.array([d for _, d in b])
            ma, mb = ~np.isnan(va), ~np.isnan(vb); va, da, vb, db = va[ma], da[ma], vb[mb], db[mb]
            if len(va) == 0 or len(vb) == 0:
                lines["stap1"].append(f"   {name}: onvoldoende data"); return
            ud = sorted(set(da) | set(db))
            ia = {u: np.where(da == u)[0] for u in ud}; ib = {u: np.where(db == u)[0] for u in ud}
            bs = []
            for _ in range(NBOOT):
                pick = [ud[i] for i in RNG.integers(0, len(ud), len(ud))]
                sa = np.concatenate([ia[p] for p in pick]); sb = np.concatenate([ib[p] for p in pick])
                if len(sa) and len(sb):
                    bs.append(va[sa].mean() - vb[sb].mean())
            lines["stap1"].append(f"   {name}: verschil={va.mean() - vb.mean():+.3f}  95%=[{np.percentile(bs, 2.5):+.3f},{np.percentile(bs, 97.5):+.3f}]")
        lines["stap1"].append(f"-- VERSCHILLEN gepoold ({mode})")
        diff(pool["a_real"], pool["a_mirror"], "(a) HVN-bounce minus gespiegelde levels")
        diff(pool["a_real"], pool["a_shift"], "(a) HVN-bounce minus verschoven levels")
        half = [(0.5, d) for _, d in pool["b_abs"]]
        diff(pool["b_abs"], half, "(b2) absorptie minus willekeurige richting (=0,5)")
        diff(pool["b_abs"], pool["b1_touch"], "(b1) absorptie minus gewone HVN-aanraking (fade)")
        diff(pool["c_conf"], pool["c_unconf"], "(c) bevestigd minus niet-bevestigd")
        diff(pool["c_conf"], [(0.5, d) for _, d in pool["c_conf"]], "(c) bevestigd minus willekeurige richting")
        ctxs[("pool1", mode)] = pool

    # STAP 2 - stops, real vs random entries
    months = {"S60": 59 / 21, "P": 20 / 21}
    allres = {}
    for mode in ("S60", "P"):
        lines["stap2"].append(f"\n######## DATASET {mode} ########")
        for tk in TICKERS:
            ctx = ctxs[(tk, mode)]; tw = ctx["tw"]; b5 = ctx["b5"]; sp = SPEC[tk]
            real = []
            for e in tw["entries"]:
                e = dict(e); e["stops"] = stops_for(ctx, e, "real"); real.append(e)
            rnd = random_entries(ctx, max(20 * len(real), 200))
            for kind, evs in (("real", real), ("random", rnd)):
                for e in evs:
                    for sv, stp in e["stops"].items():
                        r = sim_trade(ctx, e["bar"], e["dir"], e["entry"], stp, e["target"], sp["tick"], sp["comm"])
                        if r is None:
                            continue
                        r.update(day=f"{tk}|{b5.index[e['bar']].date()}", entry_time=b5.index[e["bar"]] + pd.Timedelta(minutes=5),
                                 under15=abs(e["target"] - e["entry"]) / abs(e["entry"] - stp) < 1.5, sid=(tk, e["bar"]),
                                 entry=e["entry"], dir=e["dir"], stop_px=stp)
                        if tk == "SPY":
                            r["opt"] = option_pct(r["entry_time"], r["exit_time"], e["entry"], r["exit_px"], e["dir"])
                        allres.setdefault((mode, tk, kind, sv), []).append(r)
        for kind in ("real", "random"):
            for tk in TICKERS + ["POOL_OOS"]:
                for sv in ("S0", "S1", "S2", "S3"):
                    rows = (sum([allres.get((mode, t, kind, sv), []) for t in TICKERS[1:]], []) if tk == "POOL_OOS"
                            else allres.get((mode, tk, kind, sv), []))
                    lines["stap2"].append(summarize(rows, months[mode],
                                                    f"{mode} {kind:6s} {tk:8s} {sv}", opt=(tk == "SPY" and kind == "real")))
        # paired differences
        lines["stap2"].append(f"-- gepaarde verschillen Sx - S0 (netto R), dag-geclusterd 95% ({mode})")
        for kind in ("real", "random"):
            for scope, tks in (("SPY", ["SPY"]), ("OOS", TICKERS[1:]), ("ALLES", TICKERS)):
                base = {r["sid"]: r for t in tks for r in allres.get((mode, t, kind, "S0"), [])}
                for sv in ("S1", "S2", "S3"):
                    dv, dd = [], []
                    for t in tks:
                        for r in allres.get((mode, t, kind, sv), []):
                            if r["sid"] in base:
                                dv.append(r["net"] - base[r["sid"]]["net"]); dd.append(r["day"])
                    m, lo, hi = boot_mean(dv, dd)
                    u15 = np.mean([r["under15"] for t in tks for r in allres.get((mode, t, kind, sv), [])]) * 100 if dv else np.nan
                    lines["stap2"].append(f"   {kind:6s} {scope:5s} {sv}-S0: n={len(dv):4d} diff={m:+.3f} [{lo:+.3f},{hi:+.3f}]  target<1.5R: {u15:4.1f}%")
    # S0 diagnosis (S60, SPY and pooled)
    diag = []
    for mode in ("S60", "P"):
        for scope, tks in (("SPY", ["SPY"]), ("ALLE", TICKERS)):
            rows = sum([allres.get((mode, t, "real", "S0"), []) for t in tks], [])
            rr = sum([allres.get((mode, t, "random", "S0"), []) for t in tks], [])
            if not rows:
                diag.append(f"{mode} {scope}: geen trades"); continue
            risk = np.array([r["risk"] for r in rows]); px = np.array([r["entry"] for r in rows])
            atrs = []
            for t in tks:
                ctx = ctxs[(t, mode)]
                for r in allres.get((mode, t, "real", "S0"), []):
                    atrs.append(r["risk"] / ctx["tw"]["atr"][r["sid"][1]] if ctx["tw"]["atr"][r["sid"][1]] > 0 else np.nan)
            q = lambda x: " / ".join(f"{np.nanpercentile(x, p):.3f}" for p in (10, 25, 50, 75, 90))
            st = [r for r in rows if r["why"] == "STOP"]
            diag += [f"\n== {mode} {scope}: {len(rows)} trades (S0)",
                     f"stopafstand $        p10/p25/p50/p75/p90: {q(risk)}",
                     f"stopafstand ATR      p10/p25/p50/p75/p90: {q(atrs)}",
                     f"stopafstand % koers  p10/p25/p50/p75/p90: {q(risk / px * 100)}",
                     f"op stop: {len(st) / len(rows) * 100:.1f}%   binnen 1 bar: {np.mean([r['bars5'] <= 1 for r in st]) * 100 if st else 0:.1f}%  "
                     f"2 bars: {np.mean([r['bars5'] <= 2 for r in st]) * 100 if st else 0:.1f}%  5 bars: {np.mean([r['bars5'] <= 5 for r in st]) * 100 if st else 0:.1f}% (van de stops)",
                     f"MAE (R) p10/p25/p50/p75/p90: {q([r['mae'] for r in rows])}",
                     f"MFE (R) p10/p25/p50/p75/p90: {q([r['mfe'] for r in rows])}"]
            qs = np.quantile(risk / px, [0.25, 0.5, 0.75])
            for i, (a, b) in enumerate(zip([-1, *qs], [*qs, 9])):
                sel = [r for r in rows if a < r["risk"] / r["entry"] <= b]
                if sel:
                    diag.append(f"  kosten in R, stop-kwartiel {i + 1}: gem {np.mean([r['cost_R'] for r in sel]):.3f}R (n={len(sel)})")
            ra = [r["after_target"] for r in st]; rb = [r["after_target"] for r in rr if r["why"] == "STOP"]
            diag.append(f"na stop alsnog target geraakt: echt {np.nanmean(ra) * 100 if ra else np.nan:.1f}% (n={len(ra)})  vs willekeurig {np.nanmean(rb) * 100 if rb else np.nan:.1f}% (n={len(rb)})")
    # STAP 4 decision + DSR (S60 primary)
    mode = "S60"
    best = max(("S0", "S1", "S2", "S3"), key=lambda sv: np.mean([r["net"] for r in allres.get((mode, "SPY", "real", sv), [{"net": -9}])]))
    lines["stap4"].append(f"Beste stop op SPY ({mode}) op gem. netto R: {best}")
    better = 0
    for t in TICKERS[1:]:
        a = allres.get((mode, t, "real", best), []); b = allres.get((mode, t, "real", "S0"), [])
        ma, mb = (np.mean([r["net"] for r in a]) if a else np.nan), (np.mean([r["net"] for r in b]) if b else np.nan)
        better += int(ma > mb) if not (np.isnan(ma) or np.isnan(mb)) else 0
        lines["stap4"].append(f"  {t}: {best} {ma:+.3f}  vs S0 {mb:+.3f}  (n={len(a)})")
    lines["stap4"].append(f"  beter dan S0 op {better} van 6 OOS-tickers (eis >= 4)")
    for sv in ("S0", best):
        allnet = [r["net"] for t in TICKERS for r in allres.get((mode, t, "real", sv), [])]
        sr, p = dsr(allnet)
        lines["stap4"].append(f"  DSR {sv} alle tickers: per-trade Sharpe={sr:+.3f}  P(echte Sharpe>0 na {N_TRIALS} pogingen)={p:.3f}  n={len(allnet)}")
    for k, v in lines.items():
        (OUT / f"results_{k}.txt").write_text("\n".join(v) + "\n")
    (OUT / "results_stap2_diagnose_S0.txt").write_text("\n".join(diag) + "\n")
    print("\n".join(sum(lines.values(), [])))
    print("\n".join(diag))


if __name__ == "__main__":
    main()
