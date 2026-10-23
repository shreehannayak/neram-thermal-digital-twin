"""Build docs/NERAM_Simulation_Handbook.pdf from docs/NERAM_Simulation_Handbook.md (A4, page numbers).
Usage: python tools/build_handbook_pdf.py docs/NERAM_Simulation_Handbook.md docs/NERAM_Simulation_Handbook.pdf
Needs: markdown, playwright (chromium)."""
import re, sys, markdown, asyncio
from pathlib import Path
src = Path(sys.argv[1]); out = Path(sys.argv[2])
text = src.read_text(encoding='utf-8')
fm = {}
m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
if m:
    for line in m.group(1).splitlines():
        k, v = line.split(':', 1); fm[k.strip()] = v.strip().strip('"')
    text = text[m.end():]
# drop the H1 + byline paragraph (cover replaces them), keep the "Read this first" box
text = re.sub(r'^# .*\n', '', text, count=1, flags=re.M)
md = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc', 'sane_lists', 'attr_list'], extension_configs={'toc': {'toc_depth': '2'}})
body = md.convert(text)
fonts = (Path(__file__).resolve().parents[1] / 'unity_editor/Assets/Resources/NERAM/Fonts')
css = f"""
@font-face{{font-family:Inter;font-weight:400;src:url(file://{fonts}/Inter-Regular.ttf)}}
@font-face{{font-family:Inter;font-weight:500;src:url(file://{fonts}/Inter-Medium.ttf)}}
@font-face{{font-family:Inter;font-weight:600 900;src:url(file://{fonts}/Inter-SemiBold.ttf)}}
@page{{size:A4;margin:18mm 16mm 18mm 16mm}}
body{{font-family:Inter,DejaVu Sans,sans-serif;font-size:9.6pt;line-height:1.5;color:#1d2b30}}
.cover{{height:250mm;display:flex;flex-direction:column;justify-content:center;page-break-after:always}}
.cover h1{{font-size:40pt;letter-spacing:3px;color:#0f5560;margin:0}}
.cover .sub{{font-size:17pt;color:#0f5560;margin:6px 0 14px}}
.cover .bar{{width:110mm;height:5px;background:linear-gradient(90deg,#2ec4b6,#e3a20b);margin-bottom:28mm}}
.cover .meta{{color:#4b5d63;font-size:10pt;line-height:1.7}}
.cover .poc{{margin-top:12mm;border-left:4px solid #e3a20b;background:#fdf6e7;padding:10px 14px;font-size:9pt}}
h2{{color:#0f5560;font-size:16pt;border-bottom:2px solid #2ec4b6;padding-bottom:4px;margin-top:22px;page-break-before:always}}
h2#contents{{page-break-before:avoid}}
h3{{color:#16707b;font-size:12.5pt;margin-top:18px}} h4{{color:#1d2b30;font-size:10.5pt}}
table{{border-collapse:collapse;width:100%;margin:8px 0;font-size:8.6pt;page-break-inside:auto}}
th{{background:#e6f4f3;color:#0f5560;text-align:left}} th,td{{border:1px solid #cfdcdc;padding:4px 6px;vertical-align:top}}
tr{{page-break-inside:avoid}}
code{{font-family:DejaVu Sans Mono,monospace;font-size:8.4pt;background:#f2f5f5;padding:0 3px;border-radius:3px}}
pre{{background:#f2f5f5;padding:8px 10px;border-radius:6px;white-space:pre-wrap;font-size:8.2pt;page-break-inside:avoid}}
blockquote{{border-left:4px solid #e3a20b;background:#fdf6e7;margin:10px 0;padding:6px 14px}}
a{{color:#16707b;text-decoration:none}} hr{{border:0;border-top:1px solid #dfe7e7}}
"""
cover = f"""<div class='cover'><h1>NERAM</h1><div class='sub'>Simulation Handbook</div><div class='bar'></div>
<div class='meta'>{fm.get('subtitle','')}<br>{fm.get('version','')}<br>Team: Saiyugan Jegan · Suchita Venkatesh · Neharikaa M · Shreehan S Nayak</div>
<div class='poc'><b>Proof-of-concept.</b> Every value in the shipped replays is SYNTHETIC or SIMULATED; warming responses are ASSUMED; the temperature
signal's anatomical site is not established (never "core temperature"). No claim of clinical validation, certification, treatment efficacy,
autonomous treatment or prevention of hypothermia.</div></div>"""
html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{cover}{body}</body></html>"
tmp = out.with_suffix('.html'); tmp.write_text(html, encoding='utf-8')
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=['--no-sandbox'])
        pg = await b.new_page(); await pg.goto('file://' + str(tmp)); await pg.wait_for_timeout(500)
        hdr = "<div style='font-size:7px;width:100%;padding:0 16mm;color:#555;font-family:sans-serif'>NERAM Simulation Handbook · SYNTHETIC / SIMULATED / ASSUMED where marked</div>"
        ftr = "<div style='font-size:7px;width:100%;text-align:center;color:#555;font-family:sans-serif'>Page <span class='pageNumber'></span> / <span class='totalPages'></span></div>"
        await pg.pdf(path=str(out), format='A4', display_header_footer=True, header_template=hdr, footer_template=ftr,
                     margin={'top':'18mm','bottom':'18mm','left':'16mm','right':'16mm'}, print_background=True)
        await b.close()
asyncio.run(main())
print('wrote', out)
