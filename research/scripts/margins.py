"""Phase 3c: unit economics per shortlisted product.

FEIT inputs (with source in DECISIONS.md / raw_signals.csv):
  - VAT NL and BE standard rate 21%  (government.nl/topics/vat/vat-rates-and-exemptions;
    accountable.eu/nl-be/help-center/welke-btw-tarieven-gelden-er-in-belgie)
  - Supplier cost: AliExpress search results fetched 2026-11-20 with NL locale. The API field
    'taxRate' = 0.21, so prices INCLUDE 21% VAT; most listings say 'Free shipping' and
    'No import charges'. The price is the CHEAPEST SKU of a listing (minPrice), which can be an
    accessory variant -> we use the MEDIAN over relevant listings with >=100 sold, and show p25-p75.
  - Meta CPA benchmarks: ONBEVESTIGD. Search snippets showed Triple Whale Meta CPA $38.99 and
    SuperAds NL EUR 43.67, but at re-verification Triple Whale returned 403 and SuperAds showed
    only an all-countries average of ~$34.34 (see data/verification.csv). Therefore the CPA is
    treated as a SCENARIO (EUR 20 / 30 / 40), not as a fact.

AANNAME (assumptions, see DECISIONS.md):
  - Payment fee 2% + EUR 0.25 (Shopify Payments UK Basic proxy via Airwallex; NL rate not found)
  - VAT on AliExpress purchases is NOT reclaimed (B2C IOSS invoice) -> cost incl. VAT
  - Returns: return_rate x product cost written off (dropship returns rarely resold)
  - CPA scenarios EUR 20 / 30 / 40 (no verified Benelux benchmark)

AFLEIDING: the selling price per product, derived from Benelux competitor prices (sources in
the PRODUCTS table and raw_signals.csv).

Run: python margins.py  -> data/unit_economics.csv
"""
import csv
import glob
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAT = 0.21
PAY_PCT, PAY_FIX = 0.02, 0.25
CPA_PLAN = 40.0
CVR_ASSUMED = 0.02  # AANNAME: 2% landing-page conversion, used only for the test stop-rule

PRODUCTS = {
    "wearable heated blanket": dict(
        kw=["wearable heated blanket", "usb heated blanket wearable"],
        keep=r"wearable|shawl|poncho|cape", drop=r"mat\b|pad|socks|vest|jacket",
        price=59.95, basis="Pleafs cordless EUR 87.96 (ANWB, herbevestigd); USB poncho EUR 44.74 (Fruugo) en Lanaform EUR 74.12 (MediaMarkt BE) ONBEVESTIGD (403)",
        ret=0.08),
    "rechargeable hand warmer": dict(
        kw=["rechargeable hand warmer"], keep=r"hand warmer", drop=r"glove|belt|waist",
        price=24.95, basis="Amazon.de 2-packs EUR 11.39-18.99; NL retail EUR 19.99-49.95 (ANWB, Decathlon)",
        ret=0.08),
    "sunrise alarm clock": dict(
        kw=["sunrise alarm clock", "sunrise alarm clock wake up light"], keep=r"wake.?up light|sunrise", drop=r"weather station",
        price=44.95, basis="bol.com LotaHome EUR 29.98, UPLY EUR 59.99, Philips HF3519 EUR 84.80+",
        ret=0.08),
    "self-warming pet bed": dict(
        kw=["self warming pet bed"], keep=r"bed|cave|nest|tent|house", drop=r"electric|usb|heating pad|\bmat\b|pads",
        price=39.95, basis="NL baskets EUR 25.99-59.99 (bol), self-warming mats EUR 10.99-20.09 (beslist), STT SnuggleHeat sell $39.95 (herbevestigd)",
        ret=0.05),
    "electric matcha whisk": dict(
        kw=["electric matcha whisk"], keep=r"matcha|whisk|frother", drop=r"$^",
        price=14.95, basis="T2 electric whisk EUR 9.95; Action matcha set EUR 6.95; bol wooden set EUR 27.67",
        ret=0.05),
    "bluetooth label printer": dict(
        kw=["bluetooth label printer"], keep=r"label (printer|maker)", drop=r"paper|tape|sticker roll", min_price=10,
        price=39.95, basis="Phomemo M150 EUR 49.99 (MediaMarkt BE), Niimbot K3 EUR 78.81 (Proshop)",
        ret=0.08),
    "heated seat cushion": dict(
        kw=["heated seat cushion"], keep=r"12v|car", drop=r"massage|vibrat|usb",
        price=39.95, basis="Olevo 12V EUR 44.69, AutoStyle EUR 59.95 (ANWB), Carpoint EUR 15.95 (Beslist)",
        ret=0.08),
    "electric ice scraper": dict(
        kw=["electric ice scraper"], keep=r"electric.*scraper|scraper.*electric|rotat", drop=r"plow|sweeper|shovel|brush",
        price=49.95, basis="Kaercher EDI 4 EUR 61.40 (Amazon.de)",
        ret=0.08),
    "titanium cutting board": dict(
        kw=["titanium cutting board"], keep=r"pure tita", drop=r"304|316|stainless",
        price=34.95, basis="AANNAME - no Benelux retail price found for pure-titanium boards",
        ret=0.06),
    "fascia massage ring": dict(
        kw=["fascia massage ring"], keep=r"electric|rechargeable|vibration|hot compress|leg massager", drop=r"yoga|pilates|face|eye|stretch|silicone|wrist|acupuncture|32 wheel|stovepipe|detachable handles|roller",
        price=44.95, basis="Italian Design ring EUR 43.99 promo (MediaMarkt BE) / EUR 74.99 (MediaMarkt NL) - ONBEVESTIGD (403 bij herverificatie); eBay.de EUR 18.83",
        ret=0.08),
    "cordless pressure washer": dict(
        kw=["cordless pressure washer car"], keep=r"cordless|wireless|battery|portable", drop=r"nozzle|hose only|foam cannon|makita|without battery|no battery|foam sprayer",
        price=59.95, basis="AANNAME - Lidl Parkside battery washer sold in DE (price not shown); no NL price found",
        ret=0.08),
    "hand casting kit": dict(
        kw=["hand casting kit couples"], keep=r"hand.{0,20}(cast|mold|mould)|(cast|mold|mould).{0,20}hand", drop=r"bdsm|sex|erotic|bondage",
        price=29.95, basis="DE alginate set ~EUR 22.90 (eBay.de); Luna Bean US $29.30 (FastMoss)",
        ret=0.04),
    "mug warmer": dict(
        kw=["mug warmer"], keep=r"warmer|heater|coaster", drop=r"$^",
        price=19.95, basis="generic USB warmers ~EUR 10-12 NL (ONBEVESTIGD); Jura EUR 119.99",
        ret=0.06),
    "heated eye mask": dict(
        kw=["heated eye mask"], keep=r"usb|electric|heated|heating", drop=r"gel|ice|cold|microwav|steam",
        price=29.95, basis="Blephasol EUR 27.95 (medisch hulpmiddel), Renpho Eyeris 1 EUR 61.99",
        ret=0.06),
    "book clamp reading light": dict(
        kw=["book reading light clamp"], keep=r"book", drop=r"desk lamp|swing arm|monitor",
        price=19.95, basis="Amazon.de EUR 10.49-15.99 (14k-43k ratings)",
        ret=0.05),
}


def sold_num(s):
    s = (s or "").replace(",", "").replace("+", "")
    m = re.search(r"([\d.]+)\s*(k?)", s, re.I)
    if not m:
        return 0.0
    return float(m.group(1)) * (1000 if m.group(2).lower() == "k" else 1)


def load_ali():
    data = {}
    for f in sorted(glob.glob(str(ROOT / "data" / "aliexpress_search*.json"))):
        for kw, rec in json.load(open(f)).items():
            if rec["items"]:
                data[kw] = rec
    return data


def pct(vals, q):
    vals = sorted(vals)
    if not vals:
        return None
    k = (len(vals) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def economics(price, cost, ret):
    if cost is None:
        return dict(net=None, gm=None, gm_pct=None, be_roas=None)
    net = price / (1 + VAT)
    fee = price * PAY_PCT + PAY_FIX
    gm = net - cost - fee - ret * cost
    return dict(net=net, gm=gm, gm_pct=gm / price,
                be_roas=(price / gm) if gm > 0 else float("inf"))


def main():
    ali = load_ali()
    rows = []
    for name, p in PRODUCTS.items():
        items = []
        for kw in p["kw"]:
            for it in ali.get(kw, {}).get("items", []):
                t = it["title"].lower()
                if (re.search(p["keep"], t) and not re.search(p["drop"], t)
                        and sold_num(it["sold"]) >= 100 and it["price"]
                        and it["price"] >= p.get("min_price", 0)):
                    items.append(it)
        # de-duplicate by product id
        items = list({it["productId"]: it for it in items}.values())
        prices = [it["price"] for it in items]
        med = statistics.median(prices) if prices else None
        best = max(items, key=lambda x: sold_num(x["sold"])) if items else None
        e_med = economics(p["price"], med, p["ret"])
        e_p75 = economics(p["price"], pct(prices, 0.75), p["ret"])
        rows.append({
            "product": name,
            "sell_price_eur": p["price"],
            "sell_price_basis": p["basis"],
            "n_supplier_listings": len(items),
            "cost_p25": round(pct(prices, 0.25), 2) if prices else "ONBEKEND",
            "cost_median": round(med, 2) if med else "ONBEKEND",
            "cost_p75": round(pct(prices, 0.75), 2) if prices else "ONBEKEND",
            "best_listing_url": best["url"] if best else "ONBEKEND",
            "best_listing_price": best["price"] if best else "ONBEKEND",
            "best_listing_sold": best["sold"] if best else "ONBEKEND",
            "return_rate_assumed": p["ret"],
            "gross_margin_eur_median": round(e_med["gm"], 2) if e_med["gm"] is not None else "ONBEKEND",
            "gross_margin_pct_median": round(e_med["gm_pct"] * 100, 1) if e_med["gm_pct"] is not None else "ONBEKEND",
            "break_even_roas_median": (round(e_med["be_roas"], 2) if e_med["be_roas"] not in (None, float("inf")) else ("NEG" if e_med["be_roas"] else "ONBEKEND")),
            "gross_margin_eur_p75cost": round(e_p75["gm"], 2) if e_p75["gm"] is not None else "ONBEKEND",
            "max_cpa_eur": round(e_med["gm"], 2) if e_med["gm"] is not None else "ONBEKEND",
            "cpa_headroom_vs_40": round(e_med["gm"] - CPA_PLAN, 2) if e_med["gm"] is not None else "ONBEKEND",
            # order value needed so that gross margin covers a EUR 40 CPA, keeping the same margin %
            "profit_per_order_cpa20": round(e_med["gm"] - 20, 2) if e_med["gm"] is not None else "ONBEKEND",
            "profit_per_order_cpa30": round(e_med["gm"] - 30, 2) if e_med["gm"] is not None else "ONBEKEND",
            "max_cpc_at_2pct_cvr": round(e_med["gm"] * CVR_ASSUMED, 2) if e_med["gm"] is not None and e_med["gm"] > 0 else "n.v.t.",
            "required_aov_at_cpa40": (round(CPA_PLAN / e_med["gm_pct"], 2) if e_med["gm_pct"] and e_med["gm_pct"] > 0 else "n.v.t."),
        })
    out = ROOT / "data" / "unit_economics.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['product'][:26]:26} price {r['sell_price_eur']:6} | n={r['n_supplier_listings']:2} cost med {r['cost_median']!s:8} "
              f"| GM {r['gross_margin_eur_median']!s:7} ({r['gross_margin_pct_median']}%) | BE-ROAS {r['break_even_roas_median']!s:6} | headroom vs CPA40 {r['cpa_headroom_vs_40']}")
    print("->", out)


if __name__ == "__main__":
    main()
