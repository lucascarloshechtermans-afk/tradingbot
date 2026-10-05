"""All US-listed common stocks (NASDAQ + NYSE + NYSE American) from the
official NASDAQ Trader symbol directories -- the same source the external
'explosive breakout' scanner uses for its full-NASDAQ scan.

Only common stock is kept: no ETFs, test issues, warrants, units, rights,
preferreds, notes, closed-end funds or SPACs.
"""

from __future__ import annotations

import io
import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
EXCHANGES = {"N", "A"}          # otherlisted.txt: NYSE, NYSE American (Arca/BATS/IEX are ETF/ETP venues)
NOT_COMMON = re.compile(r"warrant|\bunits?\b|\brights?\b|preferred|\bnotes?\b|debenture|\bfund\b|acquisition corp"
                        r"|depositary shares,? each representing a (fraction|1/)|%", re.I)


def parse_listings(nasdaq_txt: str, other_txt: str) -> dict[str, str]:
    """ticker -> security name for common stocks in the two directory files."""
    out: dict[str, str] = {}
    n = pd.read_csv(io.StringIO(nasdaq_txt), sep="|", dtype=str).fillna("")
    n = n[~n["Symbol"].str.startswith("File Creation Time")]
    n = n[(n["Test Issue"] == "N") & (n["ETF"] == "N") & (n["Financial Status"].isin(["N", ""]))]
    for sym, name in zip(n["Symbol"], n["Security Name"]):
        if len(sym) == 5 and sym[-1] in "WURQ":     # NASDAQ 5th-letter codes: warrant, unit, right, bankrupt
            continue
        out[sym] = name
    o = pd.read_csv(io.StringIO(other_txt), sep="|", dtype=str).fillna("")
    o = o[~o["ACT Symbol"].str.startswith("File Creation Time")]
    o = o[(o["Test Issue"] == "N") & (o["ETF"] == "N") & (o["Exchange"].isin(EXCHANGES))]
    for sym, name in zip(o["ACT Symbol"], o["Security Name"]):
        out.setdefault(sym, name)
    return {s: nm for s, nm in out.items() if s.isalpha() and 1 <= len(s) <= 5 and not NOT_COMMON.search(nm)}


def fetch_us_listed(cache=None) -> dict[str, str]:
    """Download (or read from the scanner's DiskCache) the US common-stock list."""
    if cache is not None:
        hit = cache.get("us_listed")
        if hit is not None and len(hit):
            return dict(zip(hit["ticker"], hit["name"]))
    import urllib.request

    def get(url: str) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (swing-scanner)"})
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

    listed = parse_listings(get(NASDAQ_URL), get(OTHER_URL))
    if cache is not None and listed:
        cache.set("us_listed", pd.DataFrame({"ticker": list(listed), "name": list(listed.values())}))
    logger.info("US-listed common stocks: %d", len(listed))
    return listed
