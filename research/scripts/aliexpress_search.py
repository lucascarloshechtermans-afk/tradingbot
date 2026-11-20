"""Read public AliExpress search result pages (one request per keyword) and extract
product id, title, price, 'sold' count, rating, listing date and delivery text.

Locale cookie is set to Netherlands / EUR so prices and delivery estimates reflect NL.
Usage: python aliexpress_search.py out.json "keyword one" "keyword two" ...
"""
import json
import re
import sys
import time
from datetime import datetime, timezone

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
COOKIES = {"aep_usuc_f": "site=nld&c_tp=EUR&region=NL&b_locale=en_US"}


def extract_items(html):
    i = html.find('"itemList":')
    if i < 0:
        return []
    dec = json.JSONDecoder()
    obj, _ = dec.raw_decode(html[i + len('"itemList":'):])
    out = []
    for it in obj.get("content", []):
        if it.get("itemType") != "productV3":
            continue
        pid = it.get("productId")
        price = (it.get("prices") or {}).get("salePrice") or {}
        trade = (it.get("trade") or {}).get("tradeDesc", "")
        ev = (it.get("evaluation") or {}).get("starRating")
        texts = []
        for sp in it.get("sellingPoints") or []:
            for m in sp.get("materials") or []:
                if m.get("type") == "TEXT":
                    texts.append(re.sub(r"<[^>]+>", "", m.get("value", "")))
        out.append({
            "productId": pid,
            "url": f"https://www.aliexpress.com/item/{pid}.html",
            "title": (it.get("title") or {}).get("displayTitle", ""),
            "price": price.get("minPrice"),
            "currency": price.get("currencyCode"),
            "sold": trade,
            "rating": ev,
            "listed": it.get("lunchTime"),
            "selling_points": texts,
        })
    return out


def main(out, kws):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    res = {}
    for kw in kws:
        url = "https://www.aliexpress.com/w/wholesale-" + re.sub(r"\s+", "-", kw.strip()) + ".html?SortType=total_tranpro_desc"
        try:
            r = s.get(url, cookies=COOKIES, timeout=30)
            items = extract_items(r.text)
        except Exception as e:  # noqa: BLE001
            items, r = [], None
            print("ERR", kw, e, file=sys.stderr)
        res[kw] = {"search_url": url, "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "items": items}
        print(kw, len(items), file=sys.stderr)
        json.dump(res, open(out, "w"), indent=1, ensure_ascii=False)
        time.sleep(20)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
