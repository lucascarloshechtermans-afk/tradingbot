"""Round 5 C: the user's multi-timeframe EMA style (research/HYPOTHESES.md).

    python -m research.mtf5 DATA.pkl H4.pkl OUT.pkl

Only ~2 years of 4H bars exist, so the cells are the ticker halves
(research = development, holdout = validation); scored against the
same-day, same-half random stock.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import add_context, add_half_day_excess, build_panel, cell_stats, day_baseline_halves, simulate

HOLDS = (5, 10, 20)


def mtf_signals(p, h4: dict) -> dict[str, np.ndarray]:
    T, N = p.c.shape
    C = p.df(p.c)
    e200d = C.ewm(span=200, adjust=False).mean().to_numpy()
    atr = p.atr
    names = ("M00 4H200_BREAK_ANY", "M01 D200_HOLD_4H200_BREAK", "M02 BELOW_D200_4H200_BREAK", "M03 D200_RETEST_ABOVE_4H200")
    S = {k: np.zeros((T, N), bool) for k in names}
    first_valid = np.full(N, T)
    for j, tk in enumerate(p.tickers):
        b = h4.get(tk)
        if b is None or len(b) < 260:
            continue
        c4 = b["close"]
        e4 = c4.ewm(span=200, adjust=False).mean()
        above = c4 > e4
        below6 = (~above).astype(int).rolling(6).sum().shift(1) == 6
        brk = (above & below6).to_numpy()
        valid = np.arange(len(b)) >= 200
        day = b.index.tz_localize(None).normalize() if b.index.tz is not None else b.index.normalize()
        rows = p.dates.get_indexer(day)
        ok = (rows >= 0) & valid
        first_valid[j] = rows[ok].min() if ok.any() else T
        r_brk = rows[ok & brk]
        S["M00 4H200_BREAK_ANY"][r_brk, j] = True
        # last 4H close of each day above its EMA200
        last = pd.Series(above.to_numpy()[ok], index=rows[ok]).groupby(level=0).last()
        above_last = np.zeros(T, bool)
        above_last[last.index.to_numpy()] = last.to_numpy()
        hold = p.c[:, j] > e200d[:, j]
        with np.errstate(invalid="ignore", divide="ignore"):
            dist = (p.c[:, j] - e200d[:, j]) / atr[:, j]
        S["M01 D200_HOLD_4H200_BREAK"][:, j] = S["M00 4H200_BREAK_ANY"][:, j] & hold
        S["M02 BELOW_D200_4H200_BREAK"][:, j] = S["M00 4H200_BREAK_ANY"][:, j] & ~hold
        S["M03 D200_RETEST_ABOVE_4H200"][:, j] = (dist >= 0) & (dist <= 1) & above_last
    # the baseline must cover the same window: blank everything before 4H data is valid
    start = int(np.median(first_valid[first_valid < T])) if (first_valid < T).any() else T
    return S, start


def main(data: str, h4_path: str, out: str) -> int:
    p = build_panel(pd.read_pickle(data))
    h4 = pd.read_pickle(h4_path)
    S, start = mtf_signals(p, h4)
    print(f"4H window from {p.dates[start].date()} to {p.dates[-1].date()}", flush=True)
    p.eligible[:start] = False
    dbh = day_baseline_halves(p, holds=HOLDS)
    allt = {}
    for name, s in S.items():
        tr = simulate(p, s, holds=HOLDS, busy_hold=10)
        if tr.empty:
            continue
        tr = add_half_day_excess(add_context(p, tr, {}), dbh)
        allt[name] = tr
        for half, lab in ((True, "research"), (False, "holdout")):
            d = tr[tr.research == half]
            line = f"{lab:<9}{name:<28} n={len(d):>5}"
            for H in HOLDS:
                st = cell_stats(d, H)
                if st.get("n", 0) >= 30:
                    line += f" | H{H} R {st['R']:+.3f} X {st['X']:+.3f} t {st['t']:+.1f} win {st['win'] * 100:3.0f}%"
            print(line, flush=True)
    pd.to_pickle(allt, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
