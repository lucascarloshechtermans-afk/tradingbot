"""Phase 4: transparent, reproducible scoring of the shortlist.

Score per criterion 0-10. Weights are documented in DECISIONS.md.
  - 'marge' is computed mechanically from data/unit_economics.csv:
        score = clamp(10 * (4.0 - break_even_roas) / (4.0 - 1.5), 0, 10)
    i.e. BE-ROAS <= 1.5 -> 10, BE-ROAS >= 4.0 (or negative margin / unknown cost) -> 0.
  - 'levertijd' is mechanical: no EU-warehouse stock was confirmed for any product
    (all supplier evidence is AliExpress China, 'Delivery' estimates ~1-2 weeks) -> 4 for all.
  - The other six criteria are judgements (AFLEIDING); the one-line reason is stored next to
    every score in products_scored.csv so each number can be challenged.
Independent-signal rule: a product can only enter the final top list with >= 3 supporting
signals from >= 3 different source domains (counter-evidence rows are excluded from the count).

Run: python score.py  -> ../products_scored.csv
"""
import csv
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

WEIGHTS = {
    "trend": 0.15,
    "verzadiging": 0.15,   # 10 = low saturation
    "marge": 0.20,
    "wow": 0.10,
    "levertijd": 0.10,
    "risico": 0.10,        # 10 = low risk / easy compliance
    "probleem": 0.10,
    "seizoen": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1) < 1e-9

# (score, reason) per judged criterion
J = {
    "wearable heated blanket": dict(
        trend=(7, "AliExpress listings created 3-15 Nov 2026 already 183-900+ sold; Benable Nov-2026 list; STT shark-blanket"),
        verzadiging=(5, "sold by ANWB/MediaMarkt/Vanden Borre but few USB-wearable specialists; no Amazon.nl/de bestseller hit"),
        wow=(6, "cosy, but warmth itself is not visible on video"),
        risico=(4, "heating element on the body: GPSR + Safety Gate focus on heated products; 5V USB lowers risk vs mains"),
        probleem=(7, "cold home office / energy cost (Clearscore: 100W blanket 2.6p/h vs 52.6p/h heater)"),
        seizoen=(9, "peak Dec-Feb, fully inside window")),
    "rechargeable hand warmer": dict(
        trend=(8, "Amazon.nl Sports #1/#5/#6; Amazon.de 6 of top 36; Amazon.fr #6/#33/#50; Jan peak (Accio)"),
        verzadiging=(1, "Amazon.de EUR 11-19 for 2-packs, ANWB, Decathlon, Sandberg - fully mainstream"),
        wow=(6, "magnet/heat-up demo"),
        risico=(3, "lithium cells; CPSC recall of rechargeable hand warmers 1 Oct 2026"),
        probleem=(6, "cold hands commuting/cycling"),
        seizoen=(9, "Jan peak")),
    "sunrise alarm clock": dict(
        trend=(6, "Jan peak (SaleHoo); 5,000+ sold AliExpress listing created Oct 2026; ASInsight 20k/mo top seller US"),
        verzadiging=(2, "Philips home market + >=6 budget brands on bol.com from EUR 29.98"),
        wow=(6, "sunrise visual works on video"),
        risico=(6, "low-voltage lamp with adapter; CE/RED if radio/bluetooth"),
        probleem=(7, "dark Benelux winter mornings"),
        seizoen=(9, "Jan-Feb")),
    "self-warming pet bed": dict(
        trend=(5, "STT January-2026 pick, Chewy/fypower 2026 roundups; no hard growth number"),
        verzadiging=(5, "cheap mats EUR 11-20 and many baskets on bol, but self-warming caves are less common"),
        wow=(6, "pet videos convert; heat itself not visible"),
        risico=(9, "no electronics, no battery: textile only (GPSR general)"),
        probleem=(6, "older/thin-coated pets in winter"),
        seizoen=(8, "Dec-Feb")),
    "electric matcha whisk": dict(
        trend=(7, "ASInsight 40k/mo top seller US; Innova: DE among matcha growth markets; ET hojicha latte +733%"),
        verzadiging=(2, "Action sells 5-pc matcha set EUR 6.95; T2 electric whisk EUR 9.95"),
        wow=(6, "green foam demo"),
        risico=(8, "small battery whisk; food-contact (LFGB/EU 1935/2004) docs needed"),
        probleem=(4, "nice-to-have"),
        seizoen=(5, "neutral; 'healthy January' slight plus")),
    "bluetooth label printer": dict(
        trend=(5, "TikTok Shop listings; Accio: basic household segment 'mature and saturated'"),
        verzadiging=(3, "MediaMarkt NL/BE and Proshop sell Phomemo/Niimbot"),
        wow=(7, "satisfying printing demo"),
        risico=(7, "small electronics, RED/CE + WEEE registration"),
        probleem=(7, "January home organisation"),
        seizoen=(7, "Jan organisation")),
    "heated seat cushion": dict(
        trend=(4, "only AliExpress orders + existing NL retail; no growth evidence"),
        verzadiging=(5, "ANWB, Beslist, Action (mains version EUR 14.95)"),
        wow=(4, "not visual"),
        risico=(4, "12V heating element in car; UK OPSS fire-risk report on a warming pad"),
        probleem=(7, "cold car seats without built-in heating"),
        seizoen=(8, "winter")),
    "electric ice scraper": dict(
        trend=(4, "Kaercher EDI 4 #22 Amazon.de automotive; supplier evidence weak (1 listing, a heated USB scraper)"),
        verzadiging=(6, "Kaercher dominant, few generic rotating scrapers"),
        wow=(8, "rotating disc on icy windscreen = strong demo"),
        risico=(4, "battery; possible design/patent overlap with Kaercher - unverified"),
        probleem=(8, "frozen windscreens"),
        seizoen=(7, "only frost days; Benelux winters mild")),
    "titanium cutting board": dict(
        trend=(5, "Accio: Amazon avg sales doubled Nov 2025->Jan 2026; heavy advertorial push"),
        verzadiging=(3, "KatuChef, TIBO, Taima, Tivano, TitaChef, Apex... all advertising"),
        wow=(6, "knife-on-board demo"),
        risico=(1, "AliExpress best-sellers are stainless steel sold as 'titanium'; Trustpilot fraud complaints -> misleading-claim liability"),
        probleem=(5, "microplastics worry; EFSA says evidence still emerging"),
        seizoen=(5, "neutral")),
    "fascia massage ring": dict(
        trend=(6, "Kalodata US $1.78M July 2026 (ADDWIN); STT May 2026 listing; MediaMarkt NL/BE now lists a massage ring"),
        verzadiging=(6, "few Benelux sellers found (one MediaMarkt marketplace listing)"),
        wow=(7, "vibrating ring on calf/arm is visual"),
        risico=(4, "massage device: no medical/'fat burning' claims allowed; battery; CE/EMC"),
        probleem=(6, "sore muscles, desk workers"),
        seizoen=(7, "January fitness/wellness")),
    "cordless pressure washer": dict(
        trend=(6, "Kalodata US $1.97M July 2026 (SEESE); EU TikTok home-improvement +202-298% (Kalodata via Lengow)"),
        verzadiging=(4, "Lidl Parkside battery washer; many AliExpress sellers"),
        wow=(9, "dirty car -> clean in seconds"),
        risico=(4, "battery pack, pressure-injury warnings, CE machinery/EMC"),
        probleem=(7, "no outdoor tap / apartment dwellers"),
        seizoen=(3, "Benelux car-wash season starts ~March; Dec-Feb weak")),
    "hand casting kit": dict(
        trend=(4, "US TikTok Shop $779k Dec 2025 (Luna Bean); trend dates from 2020"),
        verzadiging=(6, "few NL couple kits; baby kits exist (EUR 17.95)"),
        wow=(7, "reveal of the cast is a strong video"),
        risico=(6, "alginate/plaster powders need CLP labelling; adult use only"),
        probleem=(3, "gift, not a problem"),
        seizoen=(8, "Valentine 14 Feb inside window")),
    "mug warmer": dict(
        trend=(4, "4,000+ sold AliExpress; Accio Nextmug 26k/mo US (smart mug, different product)"),
        verzadiging=(4, "generic USB warmers ~EUR 10-12 (ONBEVESTIGD)"),
        wow=(5, "steam demo"),
        risico=(6, "USB heating plate, LVD/EMC"),
        probleem=(5, "cold coffee at desk"),
        seizoen=(6, "winter/office")),
    "heated eye mask": dict(
        trend=(4, "Accio 'poised for growth' (qualitative); few NL sellers"),
        verzadiging=(5, "pharmacy masks + Renpho"),
        wow=(5, "low visual"),
        risico=(3, "dry-eye claims = medical device (Blephasol); heat near eyes"),
        probleem=(6, "screen-tired eyes, sleep"),
        seizoen=(6, "neutral")),
    "book clamp reading light": dict(
        trend=(6, "Amazon.de Lighting #10/#21/#40; BookTok (PureWow)"),
        verzadiging=(1, "Amazon.de EUR 10.49-15.99 with 14k-43k ratings"),
        wow=(5, "cosy reading shot"),
        risico=(8, "small LED + battery"),
        probleem=(6, "reading in bed without waking partner"),
        seizoen=(7, "long evenings")),
}

COUNTER = re.compile(r"counter", re.I)


def margin_score(be):
    try:
        be = float(be)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, 10 * (4.0 - be) / (4.0 - 1.5)))


def main():
    econ = {r["product"]: r for r in csv.DictReader(open(ROOT / "data" / "unit_economics.csv"))}
    sigs = list(csv.DictReader(open(ROOT / "data" / "raw_signals.csv")))
    rows = []
    for p, j in J.items():
        support = [s for s in sigs if s["product"] == p and not COUNTER.search(s["bron"])]
        domains = sorted({urlparse(s["url"]).netloc.replace("www.", "") for s in support})
        e = econ[p]
        scores = {k: v[0] for k, v in j.items()}
        scores["marge"] = round(margin_score(e["break_even_roas_median"]), 1)
        scores["levertijd"] = 4
        total = round(sum(scores[k] * w for k, w in WEIGHTS.items()), 2)
        gm = e["gross_margin_eur_median"]
        eligible = (len(domains) >= 3 and float(e["sell_price_eur"]) >= 20
                    and gm not in ("ONBEKEND",) and float(gm) > 0)
        why_not = [] if eligible else [x for x, bad in [
            ("<3 bron-domeinen", len(domains) < 3),
            ("verkoopprijs < EUR 20", float(e["sell_price_eur"]) < 20),
            ("kostprijs ONBEKEND", gm == "ONBEKEND"),
            ("negatieve marge", gm != "ONBEKEND" and float(gm) <= 0)] if bad]
        row = {"product": p, "total_score": total, "final_list_eligible": eligible,
               "not_eligible_because": "; ".join(why_not),
               "required_aov_at_cpa40": e["required_aov_at_cpa40"],
               **{f"s_{k}": scores[k] for k in WEIGHTS},
               "n_support_signals": len(support), "n_source_domains": len(domains),
               "passes_3_signal_rule": len(domains) >= 3,
               "sell_price_eur": e["sell_price_eur"], "cost_median_eur": e["cost_median"],
               "gross_margin_eur": e["gross_margin_eur_median"], "gross_margin_pct": e["gross_margin_pct_median"],
               "break_even_roas": e["break_even_roas_median"], "max_cpa_eur": e["max_cpa_eur"],
               "best_supplier_url": e["best_listing_url"],
               **{f"why_{k}": v[1] for k, v in j.items()},
               "source_domains": "; ".join(domains)}
        rows.append(row)
    rows.sort(key=lambda r: r["total_score"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    out = ROOT / "products_scored.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rank"] + [k for k in rows[0] if k != "rank"])
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(f"{r['rank']:2}. {r['product'][:26]:26} {r['total_score']:5} | marge {r['s_marge']:4} BE-ROAS {r['break_even_roas']:>6} | "
              f"domains {r['n_source_domains']} | {'ELIGIBLE' if r['final_list_eligible'] else 'out: ' + r['not_eligible_because']}")
    print("->", out)


if __name__ == "__main__":
    main()
