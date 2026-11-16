"""Stap 3 (pre-registered): T1 = entry window 09:45-15:00 + exit 15:50; T2 = T1 + time stop after 6 bars if MFE < 0.5R.
Stop S0 (the standard after stap 4). Option estimate for SPY trades."""
import numpy as np, pandas as pd
import study as S

def sim_t(ctx, e, variant, tick, comm):
    d, ent, stop, tgt = e["dir"], e["entry"], e["stop"], e["target"]
    t = e["bar"]; b5 = ctx["b5"]
    et = b5.index[t] + pd.Timedelta(minutes=5)
    if variant != "T0" and not (pd.Timestamp("09:45").time() <= et.time() <= pd.Timestamp("15:00").time()):
        return None
    bars = S.fwd(ctx, t)
    if variant != "T0":
        bars = bars[bars.index < pd.Timestamp(et.date()) + pd.Timedelta(hours=15, minutes=50)]
    if len(bars) == 0:
        return None
    risk = abs(ent - stop); ef = ent + d * tick; mfe = 0.0; ex = None; why = "TIME/EOD"
    for i, (ts, b) in enumerate(bars.iterrows()):
        mins = (ts - bars.index[0]).total_seconds() / 60 + ctx["step"]
        fav = (b.high - ent) if d == 1 else (ent - b.low); mfe = max(mfe, fav / risk)
        if (b.open <= stop) if d == 1 else (b.open >= stop): ex = (b.open, b.open - d * tick); why = "STOP"; break
        if (b.open >= tgt) if d == 1 else (b.open <= tgt): ex = (b.open, b.open); why = "TARGET"; break
        if (b.low <= stop) if d == 1 else (b.high >= stop): ex = (stop, stop - d * tick); why = "STOP"; break
        if (b.high >= tgt) if d == 1 else (b.low <= tgt): ex = (tgt, tgt); why = "TARGET"; break
        if variant == "T2" and mins >= 30 and mfe < 0.5:
            ex = (b.close, b.close - d * tick); why = "TIMESTOP"; break
    if ex is None:
        ex = (bars.close.iloc[-1], bars.close.iloc[-1] - d * tick); ts = bars.index[-1]
    net = ((ex[1] - ef) * d - 2 * comm) / risk
    return dict(net=net, gross=(ex[0] - ent) * d / risk, why=why, bars5=int(np.ceil(mins / 5)), day=f"{ctx['tk']}|{et.date()}",
                opt=S.option_pct(et, ts + pd.Timedelta(minutes=ctx["step"]), ent, ex[0], d) if ctx["tk"] == "SPY" else np.nan)

out = []
for mode in ("S60", "P"):
    res = {}
    for tk in S.TICKERS:
        ctx = S.prepare(tk, mode); sp = S.SPEC[tk]
        for v in ("T0", "T1", "T2"):
            for e in ctx["tw"]["entries"]:
                r = sim_t(ctx, e, v, sp["tick"], sp["comm"])
                if r: res.setdefault((tk, v), []).append(r)
    months = 59 / 21 if mode == "S60" else 20 / 21
    out.append(f"\n######## {mode} (stop S0) ########")
    for v in ("T0", "T1", "T2"):
        for tk, rows in (("SPY", res.get(("SPY", v), [])), ("POOL_OOS", sum([res.get((t, v), []) for t in S.TICKERS[1:]], []))):
            line = S.summarize(rows, months, f"{mode} {v} {tk}", opt=(tk == "SPY"))
            if tk == "SPY" and rows:
                op = np.array([r["opt"] for r in rows], float)
                line += f"  optie% mediaan={np.nanmedian(op):+.1f} winst%={np.mean(op > 0) * 100:.0f}% per-trade={np.round(op, 0).tolist()}"
            out.append(line)
    for v in ("T1", "T2"):
        allnet = [r["net"] for t in S.TICKERS for r in res.get((t, v), [])]
        sr, p = S.dsr(allnet); out.append(f"  DSR {mode} {v} alle tickers: Sharpe/trade={sr:+.3f}  P(Sharpe>0 | 200 pogingen)={p:.3f}  n={len(allnet)}")
open("results_stap3.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out))
