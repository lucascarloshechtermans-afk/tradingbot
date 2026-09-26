"""Round 4b: pre-registered earnings-event hypotheses E01-E07 (research/HYPOTHESES.md).

    python -m research.earnings4 BIG.pkl EARNINGS.pkl OUT.pkl [CELLS]

Prints the DEV cell only unless CELLS (comma list) is given.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import Panel, add_context, baseline, build_panel, cell_stats, simulate
from research.hypotheses4 import indicators

HOLDS4B = (5, 10, 20, 40)


def reaction_days(p: Panel, earn: dict) -> pd.DataFrame:
    """One row per report: j, E (row index of the reaction session), surprise.
    Rule from HYPOTHESES.md: after the close -> next session; before the open ->
    that session; unknown/intraday -> the session with the larger |open gap|."""
    rows = []
    didx = p.dates
    for j, tk in enumerate(p.tickers):
        ev = earn.get(tk)
        if ev is None or ev.empty:
            continue
        ev = ev[ev["date"] <= didx[-1]]
        k_all = didx.searchsorted(ev["date"].to_numpy())  # first session >= report date
        for d, hour, minute, sur, k in zip(ev["date"], ev["hour"], ev["ts"].dt.minute, ev["surprise"], k_all):
            if k >= len(didx) or k < 1:
                continue
            is_session = didx[k] == d
            if hour >= 16:
                E = k + 1 if is_session else k
            elif 0 < hour * 60 + minute < 9 * 60 + 30:
                E = k
            else:
                g0 = abs(p.o[k, j] - p.c[k - 1, j])
                g1 = abs(p.o[k + 1, j] - p.c[k, j]) if k + 1 < len(didx) else 0.0
                E = k if np.nan_to_num(g0) >= np.nan_to_num(g1) else k + 1
            if 1 <= E < len(didx):
                rows.append((j, E, sur))
    return pd.DataFrame(rows, columns=["j", "E", "surprise"]).drop_duplicates(["j", "E"])


def event_signals(p: Panel, ev: pd.DataFrame, I: dict) -> dict[str, np.ndarray]:
    T, N = p.c.shape
    A = p.atr
    j, E = ev["j"].to_numpy(), ev["E"].to_numpy()
    sur = ev["surprise"].to_numpy(dtype=float)
    ear = (p.c[E, j] - p.c[E - 1, j]) / A[E - 1, j]
    rng = p.h[E, j] - p.l[E, j]
    upper = (p.c[E, j] - p.l[E, j]) >= 0.5 * rng
    mom_prev = I["mom_rank"].to_numpy()[E - 1, j]
    S = {k: np.zeros((T, N), bool) for k in
         ("E01 EARNINGS_GAP_UP", "E02 SURPRISE_POSITIVE", "E03 SURPRISE_AND_GAP", "E04 LEADER_EARNINGS_FLUSH",
          "E05 PRE_EARNINGS_RUNUP", "E06 DRIFT_AFTER_HOLD", "E07 NEGATIVE_SURPRISE")}

    def put(name, mask, shift=0):
        tt = E[mask] + shift
        ok = (tt >= 0) & (tt < T)
        S[name][tt[ok], j[mask][ok]] = True

    put("E01 EARNINGS_GAP_UP", (ear >= 2) & upper)
    put("E02 SURPRISE_POSITIVE", (sur >= 10) & (ear >= 0))
    e03 = (sur >= 10) & (ear >= 1)
    put("E03 SURPRISE_AND_GAP", e03)
    put("E04 LEADER_EARNINGS_FLUSH", (ear <= -2) & (mom_prev >= 80))
    put("E05 PRE_EARNINGS_RUNUP", np.ones(len(E), bool), shift=-6)
    E5 = np.minimum(E + 5, T - 1)
    put("E06 DRIFT_AFTER_HOLD", e03 & (E + 5 < T) & (p.c[E5, j] >= p.c[E, j]), shift=5)
    put("E07 NEGATIVE_SURPRISE", (sur < 0) & (ear <= -1))
    return S


def main(big_path: str, earn_path: str, out: str, cells: str = "DEV") -> int:
    p = build_panel(pd.read_pickle(big_path))
    earn = pd.read_pickle(earn_path)
    ev = reaction_days(p, earn)
    print(f"events {len(ev)} across {ev.j.nunique()} stocks", flush=True)
    I = indicators(p)  # noqa: E741
    sig = event_signals(p, ev, I)
    base = baseline(p, holds=HOLDS4B)
    allt = {}
    for name, s in sig.items():
        tr = add_context(p, simulate(p, s, holds=HOLDS4B, busy_hold=10), base)
        allt[name] = tr
        for cell in cells.split(","):
            d = tr[tr.cell == cell]
            line = f"{cell:<6}{name:<28} n={len(d):>6}"
            for H in HOLDS4B:
                st = cell_stats(d, H)
                if st.get("n", 0) >= 30:
                    line += f" | H{H}: R {st['R']:+.3f} X {st['X']:+.3f} t {st['t']:+.1f} yrs {st['yrs+'] * 100:3.0f}%"
            print(line, flush=True)
    pd.to_pickle({"trades": allt, "events": ev}, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
