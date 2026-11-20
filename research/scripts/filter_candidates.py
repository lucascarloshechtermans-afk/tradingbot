"""Phase 2: apply the hard filters to every candidate in data/raw_signals.csv.

Filter codes (from the brief):
  SAT  saturated (many stores / mainstream Benelux retail at low price / popular for years)
  BIG  fragile, large/heavy or size-sensitive (high return risk)
  IP   brand/IP risk (branded or copied branded product)
  REG  regulated/risky in EU (medical claims, cosmetics/CPNP, food/supplements, toys/CE,
       loose lithium batteries, high-risk GPSR)
  LOW  expected selling price < ~EUR 20 and no natural bundle
  WOW  no 3-second 'wow' that can be shown on video
  FIT  no Benelux market fit / season already over / not enough info
PASS -> goes to the shortlist for phase 3.

Every verdict is a judgement (AFLEIDING) based on the signals in raw_signals.csv; the reason
column says which signal drove it. Output: data/filter_results.csv
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

V = {
    # ---- PASS (shortlist) -------------------------------------------------------------------
    "wearable heated blanket": ("PASS", "AliExpress listings created 15 Nov 2026 already 457-900+ sold; NL/BE retail EUR 45-110 leaves room; winter fit"),
    "rechargeable hand warmer": ("PASS", "6 of top-36 Amazon.de Sports bestsellers; Jan peak (Accio); watch SAT + battery recall risk"),
    "sunrise alarm clock": ("PASS", "Jan seasonal peak; 5,000+ sold AliExpress listing from Oct 2026; watch SAT on bol.com (>=6 budget brands)"),
    "self-warming pet bed": ("PASS", "no electronics (low compliance risk); STT January pick; watch cheap self-warming mats EUR 11-20"),
    "electric matcha whisk": ("PASS", "only as bundle (whisk alone EUR 10): matcha trend, DE named growth market; LOW risk if sold alone"),
    "bluetooth label printer": ("PASS", "January organisation season; TikTok-native; watch SAT (MediaMarkt sells Phomemo)"),
    "heated seat cushion": ("PASS", "2,000+ sold AliExpress listings; winter/car + office; mains/12V device -> CE needed"),
    "electric ice scraper": ("PASS", "Kaercher EDI 4 #22 Amazon.de automotive in Nov; strong 3-sec demo; battery + brand dominance to check"),
    "titanium cutting board": ("PASS", "microplastics angle, many brands advertising; strong counter-evidence (Trustpilot fakes) to weigh in phase 3"),
    "fascia massage ring": ("PASS", "Kalodata $1.78M July 2026 US; STT May 2026; must avoid medical claims"),
    "cordless pressure washer": ("PASS", "Kalodata $1.97M July 2026 US; EU TikTok home-improvement +200%; watch Lidl Parkside + battery"),
    "hand casting kit": ("PASS", "Valentine (14 Feb) inside the 3-6 month window; TikTok Shop US $779k Dec 2025; old trend (2020)"),
    "mug warmer": ("PASS", "only as bundle with mug (warmer alone EUR 8-12 cost); 4,000+ sold AliExpress; office/gift"),
    "heated eye mask": ("PASS", "only without dry-eye claims (medical device territory in NL); sleep/relax angle"),
    "book clamp reading light": ("PASS", "3 of top-46 Amazon.de Lighting; BookTok; only as 2-pack/gift bundle (single < EUR 20)"),
    # ---- FAIL --------------------------------------------------------------------------------
    "heated blanket": ("MERGED", "merged into 'wearable heated blanket'"),
    "walking pad": ("BIG", "heavy/bulky; merged with treadmill"),
    "treadmill / walking pad": ("BIG", "25-30 kg device, return cost prohibitive"),
    "pilates bar kit": ("SAT", "Kruidvat/Decathlon/Teamsports sell from EUR 9.90; popular since 2023"),
    "electric vacuum storage bag pump": ("SAT", "Action EUR 6.77 / ALDI EUR 12.99 sets in NL"),
    "flame humidifier diffuser": ("SAT", "BCC/MediaMarkt/Praxis/bol many brands EUR 30-120; review: weak flame effect"),
    "rotating spice rack": ("SAT", "US $5-28, crowded; no EU signal"),
    "under desk bike": ("BIG", "EUR 100-240 bulky device"),
    "weighted vest": ("BIG", "heavy shipping + size; AliExpress orders low"),
    "smart water bottle reminder": ("WOW", "no clear 3-sec demo; weak signals"),
    "electric protein shaker": ("LOW", "< EUR 20, saturated"),
    "grip strength trainer counter": ("LOW", "< EUR 20"),
    "smart jump rope": ("LOW", "AliExpress top sellers EUR 2.6-5; retail < EUR 20"),
    "yoga wheel": ("SAT", "commodity since 2018"),
    "balance board": ("BIG", "bulky, low wow"),
    "toe spacers": ("LOW", "EUR 2.7-4.7 on AliExpress; foot-correction claims = REG"),
    "acrylic drawer organizer": ("LOW", "< EUR 20, bulky per value"),
    "cable management box": ("LOW", "< EUR 20, low wow"),
    "heated lunch box": ("WOW", "low wow, mains + food contact"),
    "light therapy lamp": ("REG", "AliExpress results are LED face masks/red-light belts: medical/cosmetic claims"),
    "window insulation kit": ("LOW", "seal strips EUR 2.8-6.2"),
    "draft stopper door": ("LOW", "EUR 3-6"),
    "insulated tumbler": ("IP", "Stanley/Owala dominate (Amazon.de #15, #21)"),
    "heated insoles / foot warmers": ("LOW", "disposable chemical warmers EUR 7"),
    "car dehumidifier bag": ("LOW", "< EUR 20"),
    "cordless steam cleaner": ("REG", "scalding hazard + mains; saturated"),
    "shiatsu neck massager": ("SAT", "on the market since ~2019; medical-claim risk"),
    "support pillow": ("FIT", "too little information"),
    "squishy advent calendar": ("REG", "toy (CE/EN71) + season ends 1 Dec"),
    "AI voice sticker printer": ("REG", "children's toy + electronics; $130-200"),
    "magnetic collision ball game": ("IP", "Kollide is a brand; toy"),
    "family conversation cards": ("LOW", "printed cards, Dutch translation needed"),
    "electric baby nail trimmer": ("REG", "baby product, high GPSR risk"),
    "freeze-dried strawberries": ("REG", "food"),
    "black seed oil capsules": ("REG", "supplement"),
    "teeth whitening strips": ("REG", "peroxide limits in EU cosmetics law"),
    "hypochlorous acid spray": ("REG", "cosmetic/biocide"),
    "sourdough starter kit": ("REG", "food"),
    "hojicha / matcha latte": ("REG", "food (the powder); hardware part covered by matcha whisk"),
    "seamless yoga leggings": ("BIG", "clothing, size returns"),
    "shoe insoles": ("LOW", "EUR 1.04"),
    "wet and dry vacuum cleaner": ("BIG", "bulky appliance, brand competition"),
    "electric food processor": ("BIG", "appliance, saturated"),
    "frozen drink maker": ("IP", "Ninja SLUSHi brand product"),
    "smokeless indoor grill": ("BIG", "bulky, crowdfunding-stage"),
    "4K laser projector": ("BIG", "EUR 1,000+ brand hardware"),
    "portable cast iron wood stove": ("BIG", "heavy, fire risk"),
    "twin floor bed": ("BIG", "furniture"),
    "loop earplugs": ("IP", "brand"),
    "20K power bank": ("REG", "battery product"),
    "V16 emergency beacon": ("FIT", "mandatory in Spain only; not Benelux"),
    "bag charms": ("LOW", "EUR 5-30, fashion"),
    "scent beads": ("LOW", "EUR 8-20"),
    "spoon rest": ("LOW", "$9-12; units falling -29.8% w/w"),
    "expandable steamer basket": ("LOW", "$7"),
    "year planner": ("FIT", "paper, Dutch content needed"),
    "snack bag sealer": ("LOW", "< EUR 20"),
    "mushroom lamp": ("SAT", "popular since 2021"),
    "japandi lamp": ("BIG", "fragile; source is unverified summary"),
    "renter friendly wallpaper": ("BIG", "size/quantity selection, returns"),
    "microplastic water filter": ("REG", "health claims; $25-500 spread"),
    "stainless steel chopping board": ("MERGED", "merged into titanium cutting board (same 'non-plastic board' need)"),
    "stainless steel food storage set": ("WOW", "low wow"),
    "outdoor fairy mesh lights": ("FIT", "Christmas season over by the time a test runs"),
    "pie mold set": ("FIT", "US Thanksgiving"),
    "foldable LED lantern 4-pack": ("FIT", "units falling -14.3% w/w; US outage context"),
    "foldable drying rack": ("BIG", "bulky"),
    "AI desk companion": ("FIT", "crowdfunding stage, no supply"),
    "high speed hair dryer": ("IP", "Dyson/Shark dominate; mains heating appliance"),
    "cat water fountain": ("SAT", "Catit Pixi EUR 18.99 #28 Amazon.de pets"),
    "digital family calendar": ("BIG", "fragile 15-27 inch screen + app/subscription support; AliExpress results are LED wall clocks, not family calendars"),
    "pull out spice rack": ("BIG", "cabinet-size dependent (measurements), low wow"),
    "under sink organizer": ("BIG", "cabinet-size dependent, bulky, low wow"),
}


def main():
    prods = sorted({r["product"] for r in csv.DictReader(open(ROOT / "data" / "raw_signals.csv"))
                    if not r["product"].startswith("(")})
    rows, missing = [], []
    for p in prods:
        if p not in V:
            missing.append(p)
            continue
        rows.append((p, *V[p]))
    with open(ROOT / "data" / "filter_results.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product", "verdict", "reason"])
        w.writerows(rows)
    n_pass = sum(1 for r in rows if r[1] == "PASS")
    print(f"{len(rows)} candidates filtered, {n_pass} PASS")
    if missing:
        print("NO VERDICT YET:", missing)


if __name__ == "__main__":
    main()
