"""Annotate the Unity plan renders R01-R07 (NERAM > CAD > Render plan renders, Editor/NeramRenders.cs): title bar,
footer (plan disclaimer + stand-in note) and, for the exploded views, layer labels from <id>_labels.json.
Usage: python tools/annotate_renders.py <raw_render_dir> <out_dir>"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
SRC = Path(sys.argv[1]); OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"; FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
f_t, f_s, f_l, f_f = ImageFont.truetype(FB, 34), ImageFont.truetype(F, 22), ImageFont.truetype(FB, 24), ImageFont.truetype(F, 20)
TITLES = {
 "R01_full_scene": ("R01  Full scene", "Patient on OR table: CH1/CH2 hand modules, CH3/CH4 foot modules, wrist display, bedside controller, cables"),
 "R02_hand_module_iso": ("R02  Hand module (CH1, left), isometric", "Palmar pad: liner, heater film, insulation, shell; two sensors; two straps"),
 "R03_foot_module_iso": ("R03  Foot modules (CH3 / CH4), isometric", "Sole pad from heel to ball, toes free; two straps"),
 "R04_hand_module_exploded": ("R04  Hand module (CH1), exploded", "Layer order from the skin outward; offsets are visual only (exploded_offsets_SAI_DEFAULT.csv x1.4)"),
 "R05_foot_module_exploded": ("R05  Foot module (CH3), exploded", "Layer order from the skin outward; offsets are visual only (exploded_offsets_SAI_DEFAULT.csv x1.4)"),
 "R06_controller_front_ports": ("R06  Bedside controller, front and ports", "Display, START / STOP / RESET, status LEDs, CH1-CH4 module ports; screen text is illustrative"),
 "R07_cable_routing_top": ("R07  Cable routing, top view", "CH1-CH4 cables from each module to the rail-mounted controller (ceiling hidden for this view)"),
}
FOOT = ("NERAM proof-of-concept prototype \u2014 not a medical device. No hardware has been built.", "CAD: Neharika (Fusion, as exported). Mannequin, table, room and cables are generated stand-ins; pad drape and strap length are visual fits.")
NICE = {"Liner": "Liner (skin side)", "Sensor_A": "Sensor A", "Sensor_B": "Sensor B", "Heater": "Heater film", "Insulation": "Insulation",
        "Shell": "Shell", "Strap": "Straps", "Hook": "Hook patches"}

def labels(img, d, items):
    seen = {}
    for it in items:
        part = it["name"].split("_", 1)[1]; key = part.split("_")[0] if part.startswith(("Strap", "Hook")) else part
        seen.setdefault(key, it)
    W, H = img.size
    xs = [v["x"] for v in seen.values()]; right = sum(xs) / len(xs) < W * 0.55
    col = W - 380 if right else 40
    order = sorted(seen.items(), key=lambda kv: kv[1]["y"])
    top, bot = 150, H - 130; step = min(70, (bot - top) / max(1, len(order)))
    y0 = (top + bot) / 2 - step * (len(order) - 1) / 2
    for i, (k, it) in enumerate(order):
        ly = y0 + i * step; tx = col + (0 if right else 0)
        text = f"{it['name'].split('_')[0]}  {NICE.get(k, k)}"
        tw = d.textlength(text, font=f_l)
        bx0 = tx - 10; bx1 = tx + tw + 10
        anchor_x = bx0 if right else bx1
        d.line([(it["x"], it["y"]), (anchor_x, ly)], fill=(255, 214, 10), width=3)
        d.ellipse([it["x"] - 6, it["y"] - 6, it["x"] + 6, it["y"] + 6], fill=(255, 214, 10), outline=(20, 20, 20), width=2)
        d.rounded_rectangle([bx0, ly - 18, bx1, ly + 18], 8, fill=(18, 22, 28, 230), outline=(255, 214, 10), width=2)
        d.text((tx, ly), text, font=f_l, fill=(255, 255, 255), anchor="lm")

for p in sorted(SRC.glob("R0*.png")):
    rid = p.stem
    if rid not in TITLES: continue
    img = Image.open(p).convert("RGBA"); W, H = img.size
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    lj = SRC / f"{rid}_labels.json"
    if lj.exists(): labels(img, d, json.load(open(lj)))
    d.rectangle([0, 0, W, 104], fill=(14, 18, 24, 215))
    t, s = TITLES[rid]
    d.text((36, 18), t, font=f_t, fill=(255, 255, 255)); d.text((36, 64), s, font=f_s, fill=(190, 205, 220))
    d.text((W - 36, 30), "NERAM", font=f_t, fill=(64, 210, 200), anchor="ra"); d.text((W - 36, 70), "Unity viewer render, 2026-10-18", font=f_f, fill=(170, 180, 190), anchor="ra")
    d.rectangle([0, H - 72, W, H], fill=(14, 18, 24, 225)); d.text((W / 2, H - 50), FOOT[0], font=f_l, fill=(255, 255, 255), anchor="mm"); d.text((W / 2, H - 20), FOOT[1], font=f_f, fill=(200, 205, 212), anchor="mm")
    Image.alpha_composite(img, ov).convert("RGB").save(OUT / f"{rid}.png", optimize=True)
    print("ok", rid)
