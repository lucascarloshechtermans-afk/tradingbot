"""The user's weekly plan: at most 3 new positions per week, each sold at +10% ("max 10% en eruit"), everything that is
still open sold at the week's last close. Which strategy fills those 3 slots best?

    python -m indicator_lab.week.three_week            # results/three_week.md

Fixed before the run:
  Universe (the week brief): close > $5, 50-day dollar volume > $20M, ADR(20) > 4% on the signal day.
  Strategies: the 10 setups of build.py (their own entry: next open or a buy-stop), S11 earnings gap (earnings reaction
    day, open >= 5% above the previous close, volume >= 2 x the 50-day average, close > open; next open),
    S12 the user's own indicator v4.1 (pine_sim.V41 BUY; next open), and RANDOM (a random universe stock on a
    random universe day, next open).
  Exits: whole position out at +10% (a gap above fills at the open), stop = mfe.std_stop (below the setup's support,
    >= 1 ATR, <= 8%; random/S11/S12 use the nearest support zone), stop first on the same bar, else out at the CLOSE OF
    THE LAST TRADING DAY OF THE ENTRY WEEK. Costs: 0.05% per side + $0.02 per side. Win = net > 0.
  Weekly book: two entry modes,
    M1 "maandag": only entries on the week's first trading day (signals of the previous week's last day);
    M2 "doorlopend": entries on any day of the week, first come first served,
    at most 3 positions per week (one per stock), ties on the same day in random order (20 runs, averaged);
    each position = 1/3 of the account, an empty slot earns 0. Weekly account return = sum of the 3 slots / 3.
  Train = entries 2015-2022, test = 2023-2026-10. The ranking uses the TRAIN average weekly return; the test is
  reported for every strategy (12 strategies x 2 modes = 24 variants + random, all shown).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab import pine_sim as PS
from indicator_lab import sr
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import earnings_eps as EE
from indicator_lab.week import mfe as M
from indicator_lab.week import run as W

OUT = os.path.join(os.path.dirname(W.LOG), "three_week.md")
TGT = 0.10
RUNS = 20
TRAIN_END = pd.Timestamp("2022-12-31")
NAMES = {**B.NAMES, "S11": "earnings gap", "S12": "jouw indicator v4.1", "RND": "willekeurig (controle)"}


def load():
    data20.final_mode()
    spy = R.load("SPY")
    spy = spy[(spy.index >= B.START) & (spy.index <= B.END)]
    wk = pd.Series(spy.index.to_period("W-FRI"), index=spy.index)
    week_last = wk.groupby(wk).apply(lambda s: s.index[-1])           # last trading day of each week
    week_first = wk.groupby(wk).apply(lambda s: s.index[0])
    earn = EE.load()
    arrs, cands = {}, {k: [] for k in NAMES}
    tickers = sorted(set(data20.DEV) | data20.H_TICKERS)
    for j, t in enumerate(tickers):
        try:
            df = data20.load(t)
        except PermissionError:
            continue
        if df is None or len(df) < 300:
            continue
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
        m = B.universe_mask(df) & np.asarray(df.index >= B.START)
        if not m.any():
            continue
        lv = sr.levels(df)
        o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
        arrs[t] = {"idx": df.index, "o": o, "h": h, "l": lo, "c": c, "atr": lv["atr"].to_numpy(),
                   "sup_lo": lv["sup_lo"].to_numpy()}
        sup = arrs[t]["sup_lo"]

        def add(sid, s, etype="open", elevel=np.nan, anchor=None, t=t, m=m, sup=sup):
            if s + 1 < len(m) and m[s]:
                cands[sid].append((t, int(s), etype, elevel, sup[s] if anchor is None else anchor))

        for sid, lst in B.signals(df, lv, spy.reindex(df.index).ffill().to_numpy()).items():
            for s, etype, elevel, anchor in lst:
                add(sid, s, etype, elevel, anchor)
        va50 = B.prev(B.sma(v, 50))
        for ts, rule, _e, _r in earn.get(t, []):
            i = int(df.index.searchsorted(ts))
            if i < len(df) and df.index[i] == ts and rule == "next":
                i += 1
            if 1 <= i < len(df) and o[i] >= 1.05 * c[i - 1] and v[i] >= 2 * va50[i] and c[i] > o[i]:
                add("S11", i)
        for s in np.where(PS.run(df, t, PS.V41)["buy"])[0]:
            add("S12", int(s))
        for s in np.where(m)[0]:
            add("RND", int(s))
        if j % 400 == 0:
            print(f"load {j}/{len(tickers)}", flush=True)
    return arrs, cands, wk, week_first, week_last


def trade(ar, s, etype, elevel, anchor, last_day):
    o, h, lo, c, a = ar["o"], ar["h"], ar["l"], ar["c"], ar["atr"]
    d, fill = M.entry(o, h, s, etype, elevel)
    if d is None or not (fill > 0 and a[s] > 0) or ar["idx"][d] > last_day:
        return None
    hold = int(ar["idx"].searchsorted(last_day, side="right")) - d
    if hold < 1:
        return None
    stop = M.std_stop(fill, anchor, a[s])
    px, _bars, kind, _mfe, _mae = M.outcome(o, h, lo, c, d, fill, stop, fill * (1 + TGT), hold)
    return M.net(fill, px), kind, d


def group(arrs, lst, wk, week_first, mode) -> dict:
    """{week: list of (entry day, ticker, s, etype, elevel, anchor)} for one strategy and entry mode."""
    by_week: dict = {}
    for t, s, etype, elevel, anchor in lst:
        dday = arrs[t]["idx"][s + 1]
        w = wk.get(dday)
        if w is None or (mode == "M1" and dday != week_first[w]):
            continue
        by_week.setdefault(w, []).append((dday, t, s, etype, elevel, anchor))
    return by_week


def book(arrs, by_week, week_last, rng):
    """Weekly book -> (weekly returns Series, list of trades (ret, kind, week)); same-day order random per run."""
    rets, trades = {}, []
    for w in week_last.index:
        lst = by_week.get(w, [])
        keys = rng.random(len(lst))
        order = sorted(range(len(lst)), key=lambda i: (lst[i][0], keys[i]))
        got, seen = [], set()
        for i in order:
            _dday, t, s, etype, elevel, anchor = lst[i]
            if len(got) == 3 or t in seen:
                continue
            res = trade(arrs[t], s, etype, elevel, anchor, week_last[w])
            if res is None:
                continue                                  # a buy-stop that never triggered frees the slot
            got.append(res)
            seen.add(t)
            trades.append((res[0], res[1], w))
        rets[w] = sum(r for r, _k, _d in got) / 3
    return pd.Series(rets), trades


def stats(weekly: pd.Series, trades, part):
    keep = lambda w: (w.end_time <= TRAIN_END + pd.Timedelta(days=1)) == (part == "train")
    wr = weekly[[keep(w) for w in weekly.index]]
    tr = [x for x in trades if keep(x[2])]
    r = np.array([x[0] for x in tr]) if tr else np.zeros(0)
    k = np.array([x[1] for x in tr]) if tr else np.zeros(0)
    per_week = pd.Series([x[2] for x in tr]).value_counts() if tr else pd.Series(dtype=int)
    hits = pd.Series([x[2] for x in tr if x[1] == 1]).value_counts() if tr else pd.Series(dtype=int)
    full10 = int((hits == 3).sum())
    eq = (1 + wr).cumprod()
    yrs = len(wr) / 52.0
    return {"trades": len(r), "per_week": len(r) / max(len(wr), 1), "hit": (k == 1).mean() if len(k) else np.nan,
            "win": (r > 0).mean() if len(r) else np.nan, "exp": r.mean() if len(r) else np.nan,
            "wk": wr.mean(), "wk_pos": (wr > 0).mean(), "full10": full10 / max(len(wr), 1),
            "cagr": eq.iloc[-1] ** (1 / yrs) - 1 if len(eq) else np.nan, "dd": (eq / eq.cummax() - 1).min(),
            "weeks3": (per_week == 3).sum() / max(len(wr), 1)}


def main():
    arrs, cands, wk, week_first, week_last = load()
    rows = []
    for mode in ("M1", "M2"):
        for sid, label in NAMES.items():
            acc = {"train": [], "test": []}
            by_week = group(arrs, cands[sid], wk, week_first, mode)
            for run in range(RUNS):
                rng = np.random.default_rng(run)
                weekly, trades = book(arrs, by_week, week_last, rng)
                for part, lst in acc.items():
                    lst.append(stats(weekly, trades, part))
            avg = {p: {k: float(np.nanmean([x[k] for x in v])) for k in v[0]} for p, v in acc.items()}
            tr_, te = avg["train"], avg["test"]
            rows.append({"modus": mode, "strategie": f"{sid} {label}", "train gem./week": tr_["wk"],
                         "test trades/week": te["per_week"], "test +10% geraakt": te["hit"], "test winrate": te["win"],
                         "test gem./trade": te["exp"], "test gem./week": te["wk"], "test weken > 0": te["wk_pos"],
                         "test weken 3x +10%": te["full10"], "test CAGR": te["cagr"], "test max daling": te["dd"]})
            print(mode, sid, f"train {tr_['wk'] * 100:+.2f}%/wk test {te['wk'] * 100:+.2f}%/wk hit {te['hit'] * 100:.0f}% "
                  f"win {te['win'] * 100:.0f}% 3x10 {te['full10'] * 100:.1f}%", flush=True)
    d = pd.DataFrame(rows).sort_values(["modus", "train gem./week"], ascending=[True, False])
    pct = ["train gem./week", "test +10% geraakt", "test winrate", "test gem./trade", "test gem./week", "test weken > 0",
           "test weken 3x +10%", "test CAGR", "test max daling"]
    show = d.copy()
    for col in pct:
        fmt = "{:+.2f}%" if "gem." in col else "{:.1f}%"
        show[col] = (show[col] * 100).map(fmt.format)
    show["test trades/week"] = show["test trades/week"].map(lambda x: f"{x:.2f}")
    spy = R.load("SPY")
    sw = spy.groupby(spy.index.to_period("W-FRI")).last().pct_change()
    sw = sw[(sw.index.start_time > TRAIN_END) & (sw.index.end_time <= B.END + pd.Timedelta(days=7))]
    txt = ("# Jouw weekplan: max 3 posities per week, +10% en eruit, rest eruit op vrijdag\n\n"
           "Zie `indicator_lab/week/three_week.py` (regels vooraf vastgelegd). Universum: > $5, > $20M/dag, ADR > 4%. "
           "Kosten 0,05% + $0,02 per kant. Elke positie = 1/3 van je rekening. Gemiddelde van 20 runs (volgorde bij "
           "gelijke dagen willekeurig). Train 2015-2022 (alleen voor de rangorde), test 2023-2026.\n\n"
           f"SPY in dezelfde testweken: gemiddeld {sw.mean() * 100:+.2f}% per week, {(sw > 0).mean() * 100:.0f}% van de weken "
           "positief.\n\n" + show.to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    best = d[d["strategie"] != "RND willekeurig (controle)"].sort_values("train gem./week", ascending=False).iloc[0]
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## Weekplan 3 posities, +10% en eruit, vrijdag eruit (results/three_week.md): 26 varianten; beste op "
                 f"train = {best['modus']} {best['strategie']}: test {best['test gem./week'] * 100:+.2f}%/week, +10% geraakt "
                 f"{best['test +10% geraakt'] * 100:.0f}%, winrate {best['test winrate'] * 100:.0f}%, 3x +10% in "
                 f"{best['test weken 3x +10%'] * 100:.1f}% van de weken\n")
    print(txt)


if __name__ == "__main__":
    main()
