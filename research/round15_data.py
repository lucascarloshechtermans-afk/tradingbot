"""Round 15 data: point-in-time S&P 500 membership from a Wikipedia revision's change
table + yfinance prices of names removed since 2010.
    python -m research.round15_data SP500_REVISION.html R14.pkl OUT.pkl"""
from __future__ import annotations

import io
import sys

import pandas as pd


def _fix(s):
    return str(s).strip().replace(".", "-") if isinstance(s, str) and s.strip() and s != "nan" else None


def changes(html: str) -> tuple[set[str], pd.DataFrame]:
    t = pd.read_html(io.StringIO(html))
    cur, ch = t[0], t[1].copy()
    ch.columns = ["date", "add", "add_name", "rem", "rem_name", "reason"]
    ch["date"] = pd.to_datetime(ch["date"], errors="coerce")
    ch["add"], ch["rem"] = ch["add"].map(_fix), ch["rem"].map(_fix)
    return set(cur["Symbol"].map(_fix)), ch.dropna(subset=["date"]).sort_values("date")


def members_at(base: set[str], ch: pd.DataFrame, day: pd.Timestamp) -> set[str]:
    """Membership at the close of `day`: start from the revision's list, undo later changes."""
    m = set(base)
    for _, r in ch[ch.date > day].iloc[::-1].iterrows():
        if r["add"]:
            m.discard(r["add"])
        if r["rem"]:
            m.add(r["rem"])
    return m


def main(html_path: str, r14: str, out: str) -> int:
    import yfinance as yf

    base, ch = changes(open(html_path).read())
    d = pd.read_pickle(r14)
    have = set(d["close"].columns)
    removed = ch[(ch.date >= "2010-01-01") & ch["rem"].notna()][["rem", "date"]]
    need = sorted(set(removed["rem"]) - have)
    print(f"{len(removed)} removals since 2010, {len(need)} without prices in the round-14 data", flush=True)
    got = {}
    for i in range(0, len(need), 50):
        chunk = need[i:i + 50]
        raw = yf.download(chunk, start="2009-01-01", auto_adjust=True, progress=False, group_by="ticker", threads=True)
        for t in chunk:
            try:
                df = raw[t].dropna(subset=["Close"])
            except KeyError:
                continue
            rd = removed.loc[removed["rem"] == t, "date"].max()
            if len(df) and df.index.min() <= rd - pd.Timedelta(days=200) and df.index.max() >= rd - pd.Timedelta(days=5):
                got[t] = df
        print(f"{i + len(chunk)}/{len(need)} tried, {len(got)} valid", flush=True)
    # removed names that are still listed today but whose ticker now belongs to someone else are rare; the
    # round-14 data is kept as is for tickers that exist today
    pd.to_pickle({"base": base, "changes": ch, "extra": got}, out)
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
