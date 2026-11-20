"""Turn REPORT.md into a self-contained REPORT.html (photos embedded as base64) and REPORT.pdf.

Usage: python build_report_pdf.py   (needs: pip install markdown; Playwright/Chromium for the PDF)
"""
import base64
import io
import re
import subprocess
from pathlib import Path

import markdown
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

CSS = """
@page { size: A4; margin: 14mm 12mm; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #1a1a1a; max-width: 980px; margin: 0 auto; padding: 16px; background: #fff; }
h1 { font-size: 20pt; border-bottom: 3px solid #16803d; padding-bottom: 6px; }
h2 { font-size: 15pt; margin-top: 26px; border-bottom: 1px solid #ccc; padding-bottom: 4px; }
h3 { font-size: 12.5pt; margin-top: 22px; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 10px 0; page-break-inside: auto; }
th, td { border: 1px solid #d0d0d0; padding: 4px 5px; vertical-align: middle; }
th { background: #f2f2f2; }
tr { page-break-inside: avoid; }
td img { width: 70px; height: 70px; object-fit: contain; display: block; }
p > img, li > img { max-width: 100%; }
img.hero { width: 240px; height: auto; border: 1px solid #ddd; border-radius: 6px; margin: 6px 0 10px; }
img.overview { width: 100%; height: auto; border: 1px solid #ddd; }
code { background: #f4f4f4; padding: 1px 4px; border-radius: 3px; font-size: 9pt; }
pre { background: #f4f4f4; padding: 8px; overflow-x: auto; }
a { color: #0b5cad; word-break: break-all; }
hr { border: none; border-top: 1px solid #ddd; margin: 22px 0; }
"""


def data_uri(rel, max_px):
    p = ROOT / rel
    im = Image.open(p).convert("RGB")
    im.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    md = (ROOT / "REPORT.md").read_text()
    # python-markdown needs a blank line before a list and 4-space nesting
    fixed = []
    for line in md.split("\n"):
        line = re.sub(r"^ {2,3}(- |\d+\. )", r"    \1", line)
        is_item = re.match(r"^\s*(- |\d+\. )", line)
        prev = fixed[-1] if fixed else ""
        if is_item and prev.strip() and not re.match(r"^\s*(- |\d+\. )", prev) and not line.startswith("    "):
            fixed.append("")
        fixed.append(line)
    md = "\n".join(fixed)
    html = markdown.markdown(md, extensions=["tables", "fenced_code"])

    def repl(m):
        attrs, src = m.group(0), m.group(1)
        if not src.startswith("images/"):
            return attrs
        if not (ROOT / src).exists():
            return '<span style="color:#777;font-size:8pt">geen foto</span>'
        if "overzicht" in src:
            return f'<img class="overview" alt="Overzicht" src="{data_uri(src, 1600)}">'
        width = re.search(r'width="(\d+)"', attrs)
        big = width and int(width.group(1)) >= 200
        cls = ' class="hero"' if big else ""
        return f'<img{cls} alt="" src="{data_uri(src, 700 if big else 220)}">'

    html = re.sub(r'<img[^>]*src="([^"]+)"[^>]*>', repl, html)
    doc = f'<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Dropshipping Benelux Rapport</title><style>{CSS}</style></head><body>{html}</body></html>'
    out_html = ROOT / "REPORT.html"
    out_html.write_text(doc)
    out_pdf = ROOT / "REPORT.pdf"
    js = (
        "const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
        "const p=await b.newPage();await p.goto('file://" + str(out_html) + "',{waitUntil:'load'});"
        "await p.pdf({path:'" + str(out_pdf) + "',format:'A4',printBackground:true,"
        "margin:{top:'14mm',bottom:'14mm',left:'12mm',right:'12mm'}});await b.close()})()"
    )
    subprocess.run(["node", "-e", js], check=True)
    print(out_html, out_html.stat().st_size // 1024, "KB;", out_pdf, out_pdf.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
