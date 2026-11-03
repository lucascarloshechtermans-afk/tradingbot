"""Daily GEX levels (gamma exposure) from the free Yahoo option chain, to type into pine/gex_levels.pine.

    python -m indicator_lab.gex_levels            # SPY, expirations within 45 days
    python -m indicator_lab.gex_levels QQQ 30     # other symbol / horizon

Method (the usual dealer-gamma convention: dealers are long the calls and short the puts that customers trade):
  gamma per contract from Black-Scholes with Yahoo's implied volatility, r = 4%;
  GEX per strike = gamma x open interest x 100 x spot^2 x 1%, calls positive, puts negative (dollars per 1% move).
  CALL WALL = strike with the largest call GEX, PUT WALL = strike with the largest put GEX (absolute),
  ZERO GAMMA = the spot level where the total GEX changes sign (recomputed on a grid of hypothetical spot prices),
  LEVELS = the other strikes with the largest |net GEX|.
Limits: Yahoo's open interest is from the previous session and its IVs can be stale for illiquid strikes; this is an
estimate, not the data a paid GEX provider uses. Run it DURING US market hours (15:45-22:00 Belgian time): outside them
Yahoo returns open interest and implied volatility as 0. Missing IVs (< 2%) are replaced by the median valid IV of the
same expiration (or 18% if none).
"""
from __future__ import annotations

import sys
import time
from math import exp, log, pi, sqrt

import numpy as np
import pandas as pd

R = 0.04


def _gamma(s, k, t, iv):
    if t <= 0 or iv <= 0.01 or s <= 0 or k <= 0:
        return 0.0
    d1 = (log(s / k) + (R + 0.5 * iv * iv) * t) / (iv * sqrt(t))
    return exp(-0.5 * d1 * d1) / sqrt(2 * pi) / (s * iv * sqrt(t))


def chain(sym: str, days: int, tries: int = 3, wait: float = 20) -> tuple[float, pd.DataFrame]:
    import yfinance as yf
    tk = yf.Ticker(sym)
    spot = float(tk.history(period="5d")["Close"].iloc[-1])
    now = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    rows = []
    exps = ()
    for _ in range(tries):                     # Yahoo answers HTTP 429 (rate limit) with an empty expiration list
        exps = tk.options
        if exps:
            break
        time.sleep(wait)
    if not exps:
        raise SystemExit("Yahoo geeft nu geen optieketen (geblokkeerd met HTTP 429 of geen data). Probeer het over een paar minuten opnieuw.")
    for e in exps:
        exp_ts = pd.Timestamp(e) + pd.Timedelta(hours=16)
        t = (exp_ts - now).total_seconds() / (365.25 * 86400)
        if t <= 0 or t > days / 365.25:
            continue
        oc = tk.option_chain(e)
        both = pd.concat([oc.calls.assign(kind="call"), oc.puts.assign(kind="put")])
        valid = both["impliedVolatility"][(both["impliedVolatility"] >= 0.02) & (both["impliedVolatility"] < 3)]
        iv_fill = float(valid.median()) if len(valid) else 0.18
        for _, r in both.iterrows():
            oi = r.get("openInterest")
            if pd.notna(oi) and oi > 0:
                iv = float(r["impliedVolatility"])
                rows.append({"kind": r["kind"], "strike": float(r["strike"]), "oi": float(oi),
                             "iv": iv if 0.02 <= iv < 3 else iv_fill, "t": t})
    return spot, pd.DataFrame(rows, columns=["kind", "strike", "oi", "iv", "t"])


def gex_at(d: pd.DataFrame, s: float) -> pd.Series:
    g = np.array([_gamma(s, k, t, iv) for k, t, iv in zip(d.strike, d.t, d.iv, strict=True)])
    val = g * d.oi.to_numpy() * 100 * s * s * 0.01 * np.where(d.kind == "call", 1.0, -1.0)
    return pd.Series(val, index=d.index)


def levels(sym="SPY", days=45, n_levels=6, data=None):
    spot, d = data if data is not None else chain(sym, days)
    d = d[(d.strike > spot * 0.85) & (d.strike < spot * 1.15)].copy()
    if d.oi.sum() < 1000:
        raise SystemExit("Geen bruikbare open interest van Yahoo (buiten de beurstijden staat die op 0). "
                         "Draai dit tijdens de Amerikaanse beurs: 15:45-22:00 Belgische tijd.")
    d["gex"] = gex_at(d, spot)
    by = d.groupby(["strike", "kind"])["gex"].sum().unstack(fill_value=0.0)
    for col in ("call", "put"):
        if col not in by:
            by[col] = 0.0
    net = by["call"] + by["put"]
    cw, pw = float(by["call"].idxmax()), float(by["put"].idxmin())
    grid = np.linspace(spot * 0.94, spot * 1.06, 121)
    tot = np.array([gex_at(d, s).sum() for s in grid])
    sign = np.sign(tot)
    flips = np.where(np.diff(sign) != 0)[0]
    if len(flips):
        i = flips[np.argmin(np.abs(grid[flips] - spot))]
        zg = float(grid[i] - tot[i] * (grid[i + 1] - grid[i]) / (tot[i + 1] - tot[i]))
    else:
        zg = float("nan")
    others = [float(k) for k in net.abs().sort_values(ascending=False).index if k not in (cw, pw)][:n_levels]
    return spot, cw, pw, zg, sorted(others), float(net.sum())


def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "SPY"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    spot, cw, pw, zg, others, total = levels(sym, days)
    print(f"{sym} koers {spot:.2f} | totale GEX {total / 1e9:+.2f} mld $ per 1% ({'positief: rustiger' if total > 0 else 'negatief: beweeglijker'})")
    print(f"CALL WALL  {cw:.2f}")
    print(f"PUT WALL   {pw:.2f}")
    print(f"ZERO GAMMA {zg:.2f}")
    print("LEVELS     " + ", ".join(f"{x:.2f}" for x in others))
    print("\nIn TradingView (gex_levels.pine) invullen:")
    print(f"  Call wall = {cw:.2f} | Put wall = {pw:.2f} | Zero gamma = {zg:.2f} | Andere levels = {','.join(f'{x:g}' for x in others)}")


if __name__ == "__main__":
    main()
