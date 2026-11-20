"""Download one product photo per shortlisted product.

Photo = the main image of the 'best supplier listing' in data/unit_economics.csv, read from the
public AliExpress search results (one request per keyword, 20 s apart; product pages are
bot-protected and are NOT used). If the listing is no longer on the first results page, the
photo of the most-sold listing with the same keyword is used instead and this is logged.
Hand casting kit has no AliExpress supplier -> og:image of the eBay.de listing used as price anchor.

Output: images/<slug>.jpg and data/images.csv (product, file, source_url, note, fetched_utc)
NOTE: supplier photos are for internal research only. Using them in your own store/ads needs
the supplier's permission or your own photos.
"""
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
COOKIES = {"aep_usuc_f": "site=nld&c_tp=EUR&region=NL&b_locale=en_US"}
KW = {
    "wearable heated blanket": "usb heated blanket wearable",
    "rechargeable hand warmer": "rechargeable hand warmer",
    "sunrise alarm clock": "sunrise alarm clock",
    "self-warming pet bed": "self warming pet bed",
    "electric matcha whisk": "electric matcha whisk",
    "bluetooth label printer": "bluetooth label printer",
    "heated seat cushion": "heated seat cushion",
    "electric ice scraper": "electric ice scraper",
    "titanium cutting board": "titanium cutting board",
    "fascia massage ring": "fascia massage ring",
    "cordless pressure washer": "cordless pressure washer car",
    "mug warmer": "mug warmer",
    "heated eye mask": "heated eye mask",
    "book clamp reading light": "book reading light clamp",
}
EBAY_FALLBACK = {"hand casting kit": ["https://www.ebay.de/itm/364592222775", "https://www.ebay.de/p/9047481728"]}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def items_from_search(s, kw):
    url = "https://www.aliexpress.com/w/wholesale-" + re.sub(r"\s+", "-", kw) + ".html?SortType=total_tranpro_desc"
    t = s.get(url, cookies=COOKIES, timeout=30).text
    i = t.find('"itemList":')
    if i < 0:
        return []
    obj, _ = json.JSONDecoder().raw_decode(t[i + len('"itemList":'):])
    return [it for it in obj.get("content", []) if it.get("itemType") == "productV3"]


def download(s, url, path):
    if url.startswith("//"):
        url = "https:" + url
    r = s.get(url, timeout=30)
    r.raise_for_status()
    path.write_bytes(r.content)
    return url


def main():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    best = {r["product"]: r["best_listing_url"] for r in csv.DictReader(open(ROOT / "data" / "unit_economics.csv"))}
    out_dir = ROOT / "images"
    out_dir.mkdir(exist_ok=True)
    rows = []
    for prod, kw in KW.items():
        pid = re.search(r"/item/(\d+)", best[prod]).group(1)
        note, src = "", best[prod]
        try:
            items = items_from_search(s, kw)
            match = [it for it in items if it.get("productId") == pid]
            if match:
                it = match[0]
            elif items:
                it, note = items[0], "best listing not on page 1 anymore; used most-sold result"
                src = f"https://www.aliexpress.com/item/{it['productId']}.html"
            else:
                raise RuntimeError("empty search page (rate limit?)")
            img = it["image"]["imgUrl"]
            f = out_dir / f"{slug(prod)}.jpg"
            download(s, img, f)
            rows.append((prod, f"images/{f.name}", src, note or "main image of best supplier listing"))
        except Exception as e:  # noqa: BLE001
            rows.append((prod, "", src, f"FAILED: {e}"))
        print(rows[-1])
        time.sleep(20)
    for prod, urls in EBAY_FALLBACK.items():
        done = False
        for u in urls:
            try:
                t = s.get(u, timeout=30).text
                m = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', t)
                if m:
                    f = out_dir / f"{slug(prod)}.jpg"
                    download(s, m.group(1), f)
                    rows.append((prod, f"images/{f.name}", u, "og:image of eBay.de listing (no AliExpress supplier found)"))
                    done = True
                    break
            except Exception:  # noqa: BLE001
                continue
        if not done:
            rows.append((prod, "", urls[0], "FAILED: no image"))
        print(rows[-1])
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(ROOT / "data" / "images.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["product", "file", "source_url", "note", "fetched_utc"])
        w.writerows([(*r, now) for r in rows])


if __name__ == "__main__":
    main()
