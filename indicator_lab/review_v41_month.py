"""How is every swing v4.1 BUY of one month doing so far? (dagbars, NASDAQ, emulation of pine/swing_v4_1.pine)

    python -m indicator_lab.review_v41_month              # October 2026
    python -m indicator_lab.review_v41_month 2026-11      # another month

Prices: the Swing 20/21 cache (ends 2026-10-23) extended with fresh Yahoo daily bars (spliced on the overlap, the
cache itself is not touched). Each BUY is followed the way the indicator trades it: entry at the next open, exit by
the indicator's own stop / trail stop / m-day-low SELL; still-open trades are valued at the last close. Returns are
raw price returns (no costs), compared with SPY over the same days. Never orders. Output:
indicator_lab/reports/v41_<month>.md and .csv.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

from indicator_lab import data as D
from indicator_lab import evaluate as E
from indicator_lab import pine_sim as S
from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.twenty import data20

OUT = os.path.join(os.path.dirname(__file__), "reports")
COLS = ["open", "high", "low", "close", "volume"]


def fresh(tickers: list[str], start: str, batch: int = 100) -> dict[str, pd.DataFrame]:
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        for _ in range(3):
            try:
                raw = yf.download(chunk, start=start, auto_adjust=True, progress=False, group_by="ticker", threads=True)
                break
            except Exception:  # noqa: BLE001  (network hiccup: retry the chunk)
                raw = None
        if raw is None:
            continue
        for t in chunk:
            try:
                df = raw[t].rename(columns=str.lower)[COLS].dropna()
            except KeyError:
                continue
            if len(df):
                df.index = pd.to_datetime(df.index).tz_localize(None)
                out[t] = df
        print(f"{min(i + batch, len(tickers))}/{len(tickers)} gedownload", file=sys.stderr, flush=True)
    return out


def splice(old: pd.DataFrame, new: pd.DataFrame | None) -> pd.DataFrame:
    """Append the new bars after the cache's last day, scaled so both series agree on the overlap."""
    old = old[COLS]
    if new is None or not len(new):
        return old
    ov = old.index.intersection(new.index)
    if len(ov) == 0:
        return old
    f = float(np.median(old.loc[ov, "close"] / new.loc[ov, "close"]))
    add = new[new.index > old.index[-1]].copy()
    add[["open", "high", "low", "close"]] *= f
    return pd.concat([old, add])


def main():
    month = pd.Period(sys.argv[1] if len(sys.argv) > 1 else "2026-10", "M")
    start = str((month.start_time - pd.Timedelta(days=45)).date())
    data20.final_mode()
    now = pd.Timestamp.now(tz="America/New_York").tz_localize(None)
    tickers = sorted(nasdaq(set(data20.DEV) | data20.H_TICKERS))
    new = fresh(["SPY", *tickers], start)
    spy = splice(D.load("SPY"), new.get("SPY"))
    spy = spy[spy.index.normalize() + pd.Timedelta(hours=16) <= now]
    E._DATA["SPY"] = spy                          # the regime rule and features see the extended SPY
    last = spy.index[-1]
    rows = []
    for t in tickers:
        df = data20.load(t)
        if df is None or len(df) < 300 or t not in new:
            continue
        df = splice(df[(df[COLS[:4]] > 0).all(axis=1)], new[t])
        df = df[(df.index.normalize() + pd.Timedelta(hours=16) <= now) & (df.index <= last)]
        out = S.run(df, t, S.V41)
        idx, c, h = df.index, df["close"].to_numpy(float), df["high"].to_numpy(float)
        dv = (df["close"] * df["volume"]).rolling(50).mean().to_numpy(float)
        trades = {x["entry_date"]: x for x in out["trades"]}
        for i in np.where(out["buy"])[0]:
            if idx[i].to_period("M") != month:
                continue
            liq = "ja" if c[i] >= 5 and dv[i] >= 5e6 else "nee"
            base = {"ticker": t, "BUY (slot)": idx[i].date(), "signaalprijs": round(c[i], 2), "liquide": liq}
            if i + 1 >= len(idx):                   # BUY on the last bar: entry is tomorrow's open
                rows.append({**base, "instap (open)": np.nan, "status": "instap morgen", "rendement": np.nan,
                             "hoogste winst": np.nan, "SPY zelfde periode": np.nan, "dagen": 0})
                continue
            e = i + 1
            entry = float(df["open"].iloc[e])
            tr = trades.get(idx[e])
            if tr is not None:
                x = idx.get_loc(tr["exit_date"])
                px, status = float(tr["exit"]), f"verkocht {tr['exit_date'].date()} ({tr['kind']})"
            else:
                x, px, status = len(idx) - 1, c[-1], "open"
            spy_ret = spy["close"].iloc[spy.index.get_loc(idx[x])] / spy["open"].iloc[spy.index.get_loc(idx[e])] - 1
            rows.append({**base, "instap (open)": round(entry, 2), "status": status, "rendement": px / entry - 1,
                         "hoogste winst": h[e:x + 1].max() / entry - 1, "SPY zelfde periode": spy_ret,
                         "dagen": x - e + 1})
    d = pd.DataFrame(rows).sort_values(["BUY (slot)", "ticker"]).reset_index(drop=True)
    d.to_csv(os.path.join(OUT, f"v41_{month}.csv"), index=False)
    write(d, month, last)


def summary(d: pd.DataFrame) -> dict:
    v = d.dropna(subset=["rendement"])
    r, s = v["rendement"], v["SPY zelfde periode"]
    return {"buys": len(d), "nog open": int((v.status == "open").sum()), "verkocht": int((v.status != "open").sum()),
            "in winst": f"{(r > 0).mean() * 100:.0f}%" if len(v) else "-",
            "gem. rendement": f"{r.mean() * 100:+.1f}%" if len(v) else "-",
            "mediaan": f"{r.median() * 100:+.1f}%" if len(v) else "-",
            "beste": f"{r.max() * 100:+.1f}%" if len(v) else "-", "slechtste": f"{r.min() * 100:+.1f}%" if len(v) else "-",
            "+10% ooit geraakt": f"{(v['hoogste winst'] >= 0.10).mean() * 100:.0f}%" if len(v) else "-",
            "gem. SPY zelfde dagen": f"{s.mean() * 100:+.1f}%" if len(v) else "-",
            "beter dan SPY": f"{(r > s).mean() * 100:.0f}%" if len(v) else "-"}


def write(d: pd.DataFrame, month, last):
    pc = lambda x: "-" if pd.isna(x) else f"{x * 100:+.1f}%"
    show = d.copy()
    for k in ("rendement", "hoogste winst", "SPY zelfde periode"):
        show[k] = show[k].map(pc)
    tab = pd.DataFrame({"alle buys": summary(d), "alleen liquide (>= $5, >= $5M/dag)": summary(d[d.liquide == "ja"])})
    week = d.assign(week=pd.to_datetime(d["BUY (slot)"]).dt.to_period("W").astype(str))
    per_week = week.groupby("week").apply(lambda g: pd.Series(summary(g)), include_groups=False)
    txt = (f"# Swing v4.1 — alle BUY-signalen van {month.strftime('%B %Y')}: hoe doen ze het (stand {last.date()})\n\n"
           "Dagbars, NASDAQ-aandelen, emulatie van `pine/swing_v4_1.pine` (geen orders). Instap op de open van de dag na "
           "de BUY, uitstap via de eigen SELL van de indicator (stop / trailing stop / m-daagse laag); open trades "
           "gewaardeerd op het laatste slot. Rendementen zonder kosten.\n\n## Samenvatting\n\n" + tab.to_markdown()
           + "\n\n## Per week van het signaal\n\n" + per_week[["buys", "nog open", "in winst", "gem. rendement",
                                                              "gem. SPY zelfde dagen", "beter dan SPY"]].to_markdown()
           + "\n\n## Elke BUY\n\n" + show.to_markdown(index=False) + "\n")
    with open(os.path.join(OUT, f"v41_{month}.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
