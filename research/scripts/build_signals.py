"""Merge all raw signals into data/raw_signals.csv.

Sources merged:
  - scripts/manual_signals.py          (hand-collected from web pages)
  - data/aliexpress_search*.json       (own fetch of AliExpress search, NL locale, sorted by orders)
  - data/amazon_lists.json             (own fetch of Amazon.de/.fr/.nl/.com list pages)

Columns: product, bron, url, metric, waarde, datum_opgezocht
"""
import csv
import glob
import json
import re
from pathlib import Path

from manual_signals import SIGNALS

ROOT = Path(__file__).resolve().parent.parent

# Amazon item text -> candidate product (only items that match a candidate are logged)
AMAZON_MAP = {
    r"(electric|recharg|oplaadba|elektrisch|magnetic).{0,40}(hand ?warmer|handwärmer|handwarmer)|(hand ?warmer|handwärmer|handwarmer).{0,40}(electric|recharg|elektrisch|4000 ?mah)": "rechargeable hand warmer",
    r"book clamp|book lamp|reading lamp": "book clamp reading light",
    r"electric ice scraper": "electric ice scraper",
    r"dehumidifier bag": "car dehumidifier bag",
    r"foot warmers|heat insoles": "heated insoles / foot warmers",
    r"wake[- ]?up light|sunrise": "sunrise alarm clock",
    r"electric heated blanket|heizdecke|wearable (heated )?blanket": "wearable heated blanket",
    r"matcha": "electric matcha whisk",
    r"label (printer|maker)": "bluetooth label printer",
    r"pilates bar": "pilates bar kit",
    r"water fountain": "cat water fountain",
    r"travel mug|quencher|drinking cup": "insulated tumbler",
}


# AliExpress search-keyword variants -> canonical candidate name
ALIAS = {
    "book reading light clamp": "book clamp reading light",
    "cordless pressure washer car": "cordless pressure washer",
    "self warming pet bed": "self-warming pet bed",
    "sunrise alarm clock wake up light": "sunrise alarm clock",
    "usb heated blanket wearable": "wearable heated blanket",
    "digital calendar wall display": "digital family calendar",
}
# searches whose results were off-topic (adult products, unrelated tools) -> not a signal
IRRELEVANT = {"hand casting kit couples", "alginate hand casting kit", "hand mold casting kit"}


def sold_num(s):
    s = (s or "").replace(",", "").replace("+", "")
    m = re.search(r"([\d.]+)\s*(k?)", s, re.I)
    if not m:
        return 0.0
    v = float(m.group(1))
    return v * 1000 if m.group(2).lower() == "k" else v


def ali_rows():
    rows = []
    merged = {}
    for f in sorted(glob.glob(str(ROOT / "data" / "aliexpress_search*.json"))):
        for kw, rec in json.load(open(f)).items():
            if rec["items"]:
                merged[kw] = rec
    for kw0, rec in merged.items():
        if kw0 in IRRELEVANT:
            continue
        kw = ALIAS.get(kw0, kw0)
        date = rec["fetched_utc"][:10]
        top = sorted(rec["items"], key=lambda x: sold_num(x["sold"]), reverse=True)[:3]
        for it in top:
            rows.append((kw, "AliExpress (own fetch, NL/EUR, sorted by orders)", it["url"],
                         "price EUR | sold (cumulative) | rating | listed since",
                         f"{it['price']} {it['currency']} | {it['sold'] or 'n/a'} | {it['rating'] or 'n/a'} | {(it['listed'] or '')[:10]}",
                         date))
        n_new = sum(1 for it in rec["items"] if (it.get("listed") or "") >= "2026-08-20")
        rows.append((kw, "AliExpress (own fetch)", rec["search_url"],
                     "share of first-page listings created in last 90 days (>=2026-08-20)",
                     f"{n_new}/{len(rec['items'])}", date))
    return rows, merged


def amazon_rows():
    rows = []
    p = ROOT / "data" / "amazon_lists.json"
    if not p.exists():
        return rows
    for rec in json.load(open(p)):
        if rec.get("status") != "OK":
            continue
        seen = set()
        for it in rec["items"]:
            if it["asin"] in seen:
                continue
            seen.add(it["asin"])
            for pat, prod in AMAZON_MAP.items():
                if re.search(pat, it["text"], re.I):
                    rank = (re.match(r"#(\d+)", it["text"]) or [None, "?"])[1]
                    rows.append((prod, "Amazon list page (own fetch)", rec["url"],
                                 f"rank on list (ASIN {it['asin']})", f"#{rank}: " + re.sub(r"^#\d+\s*", "", it["text"])[:110],
                                 rec["fetched_utc"][:10]))
                    break
    return rows


def main():
    ali, _ = ali_rows()
    rows = list(SIGNALS) + ali + amazon_rows()
    out = ROOT / "data" / "raw_signals.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["product", "bron", "url", "metric", "waarde", "datum_opgezocht"])
        w.writerows(rows)
    prods = {r[0] for r in rows if not r[0].startswith("(")}
    print(f"{len(rows)} signals, {len(prods)} distinct products/keywords -> {out}")


if __name__ == "__main__":
    main()
