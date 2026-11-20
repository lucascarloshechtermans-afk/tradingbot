"""Build images/overzicht.png: one tile per shortlisted product (photo + rank + key numbers).

Reads products_scored.csv and data/images.csv. Run after fetch_images.py.
"""
import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
NL = {
    "self-warming pet bed": "Zelfverwarmende dierenmand",
    "book clamp reading light": "Leeslampje met klem",
    "electric matcha whisk": "Elektrische matcha-klopper",
    "wearable heated blanket": "Draagbare USB-warmtedeken",
    "electric ice scraper": "Elektrische ijskrabber",
    "fascia massage ring": "Fascia-massagering",
    "sunrise alarm clock": "Wake-up light",
    "bluetooth label printer": "Bluetooth-labelprinter",
    "mug warmer": "Mok-warmer",
    "hand casting kit": "Handafdruk-gipsset",
    "cordless pressure washer": "Draadloze hogedrukreiniger",
    "rechargeable hand warmer": "Oplaadbare handwarmer",
    "heated seat cushion": "Verwarmd zitkussen 12V",
    "heated eye mask": "Verwarmd oogmasker (USB)",
    "titanium cutting board": "'Titanium' snijplank",
}
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TILE_W, IMG_H, TXT_H, PAD, COLS = 360, 360, 150, 20, 5
GREEN, RED, GREY, INK = (22, 128, 61), (185, 28, 28), (90, 90, 90), (20, 20, 20)


def main():
    scored = list(csv.DictReader(open(ROOT / "products_scored.csv")))
    imgs = {r["product"]: r for r in csv.DictReader(open(ROOT / "data" / "images.csv"))}
    rows = (len(scored) + COLS - 1) // COLS
    W = COLS * TILE_W + (COLS + 1) * PAD
    H = 110 + rows * (IMG_H + TXT_H) + (rows + 1) * PAD
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    f_title, f_name, f_txt, f_rank = (ImageFont.truetype(FB, 34), ImageFont.truetype(FB, 20),
                                      ImageFont.truetype(F, 17), ImageFont.truetype(FB, 26))
    d.text((PAD, 25), "Shortlist dropshipping Benelux - 15 producten (20-11-2026)", font=f_title, fill=INK)
    d.text((PAD, 70), "Groen = eindlijst (voldoet aan alle harde regels)   Rood = afgevallen   "
           "Foto = hoofdfoto beste AliExpress-listing (alleen intern gebruik)", font=f_txt, fill=GREY)
    for i, r in enumerate(scored):
        cx, cy = PAD + (i % COLS) * (TILE_W + PAD), 110 + PAD + (i // COLS) * (IMG_H + TXT_H + PAD)
        ok = r["final_list_eligible"] == "True"
        col = GREEN if ok else RED
        d.rectangle([cx - 3, cy - 3, cx + TILE_W + 3, cy + IMG_H + TXT_H + 3], outline=col, width=5)
        rec = imgs.get(r["product"], {})
        try:
            im = Image.open(ROOT / rec["file"]).convert("RGB")
            im.thumbnail((TILE_W, IMG_H))
            sheet.paste(im, (cx + (TILE_W - im.width) // 2, cy + (IMG_H - im.height) // 2))
        except Exception:  # noqa: BLE001
            d.rectangle([cx, cy, cx + TILE_W, cy + IMG_H], fill=(242, 242, 242))
            d.text((cx + 105, cy + IMG_H // 2 - 30), "geen foto", font=f_name, fill=GREY)
            d.text((cx + 40, cy + IMG_H // 2), "geen leverancier gevonden", font=f_txt, fill=GREY)
        d.rectangle([cx, cy, cx + 46, cy + 40], fill=col)
        d.text((cx + 8, cy + 5), f"{r['rank']}", font=f_rank, fill="white")
        ty = cy + IMG_H + 8
        d.text((cx + 8, ty), NL.get(r["product"], r["product"]), font=f_name, fill=INK)
        gm = r["gross_margin_eur"]
        gm_txt = f"EUR {float(gm):.2f}".replace(".", ",") if gm not in ("ONBEKEND",) else "?"
        d.text((cx + 8, ty + 32), f"Score {r['total_score'].replace('.', ',')}  |  verkoop EUR {r['sell_price_eur'].replace('.', ',')}",
               font=f_txt, fill=INK)
        d.text((cx + 8, ty + 56), f"Marge/order {gm_txt}  |  BE-ROAS {r['break_even_roas'].replace('.', ',').replace('ONBEKEND', '?')}", font=f_txt, fill=INK)
        status = "EINDLIJST" if ok else "uit: " + r["not_eligible_because"]
        d.text((cx + 8, ty + 84), status[:40], font=ImageFont.truetype(FB if ok else F, 17), fill=col)
    out = ROOT / "images" / "overzicht.png"
    sheet.save(out, optimize=True)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
