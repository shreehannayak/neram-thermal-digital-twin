"""Label and surface textures (PIL). Text on equipment screens states plainly that the props show no data."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TEAL = (45, 212, 191)
AMBER = (245, 158, 11)
SLATE = (22, 30, 40)
WHITE = (235, 240, 245)


def font(fonts_dir: Path, name="Inter-SemiBold.ttf", size=40):
    try:
        return ImageFont.truetype(str(fonts_dir / name), size)
    except Exception:
        return ImageFont.load_default()


def label(fonts, ch, limb, accent, w=512, h=192):
    im = Image.new("RGB", (w, h), SLATE)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([6, 6, w - 7, h - 7], radius=22, outline=accent, width=8)
    d.rounded_rectangle([20, 22, 170, h - 23], radius=14, fill=accent)
    f1 = font(fonts, "Inter-SemiBold.ttf", 82)
    f2 = font(fonts, "Inter-SemiBold.ttf", 54)
    f3 = font(fonts, "Inter-Medium.ttf", 26)
    d.text((95, h / 2), f"CH{ch}", fill=SLATE, font=f1, anchor="mm")
    d.text((190, 62), limb, fill=WHITE, font=f2, anchor="lm")
    d.text((192, 132), "NERAM prototype module", fill=(160, 172, 186), font=f3, anchor="lm")
    return im


def controller_label(fonts, w=512, h=102):
    im = Image.new("RGB", (w, h), (18, 24, 32))
    d = ImageDraw.Draw(im)
    d.text((w / 2, h / 2), "NERAM BEDSIDE CONTROLLER  -  PROTOTYPE", fill=(170, 182, 196), font=font(fonts, "Inter-SemiBold.ttf", 30), anchor="mm")
    return im


def iv_label(fonts, w=320, h=192):
    im = Image.new("RGB", (w, h), (246, 248, 250))
    d = ImageDraw.Draw(im)
    d.text((w / 2, 60), "DEMO PROP", fill=(30, 41, 59), font=font(fonts, "Inter-SemiBold.ttf", 44), anchor="mm")
    d.text((w / 2, 120), "no infusion data", fill=(90, 100, 112), font=font(fonts, "Inter-Medium.ttf", 30), anchor="mm")
    return im


def watch_face(fonts, w=256):
    im = Image.new("RGB", (w, w), (6, 9, 12))
    d = ImageDraw.Draw(im)
    d.ellipse([10, 10, w - 10, w - 10], outline=(30, 120, 112), width=6)
    d.arc([22, 22, w - 22, w - 22], 200, 340, fill=TEAL, width=6)
    d.text((w / 2, w / 2 - 18), "NERAM", fill=TEAL, font=font(fonts, "Inter-SemiBold.ttf", 34), anchor="mm")
    d.text((w / 2, w / 2 + 22), "values on", fill=(150, 160, 170), font=font(fonts, "Inter-Medium.ttf", 20), anchor="mm")
    d.text((w / 2, w / 2 + 44), "dashboard", fill=(150, 160, 170), font=font(fonts, "Inter-Medium.ttf", 20), anchor="mm")
    return im


def prop_screen(fonts, title, w=640, h=400, accent=TEAL):
    im = Image.new("RGB", (w, h), (7, 10, 14))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 54], fill=(16, 22, 30))
    d.text((20, 27), title, fill=WHITE, font=font(fonts, "Inter-SemiBold.ttf", 28), anchor="lm")
    d.text((w - 20, 27), "STANDBY", fill=accent, font=font(fonts, "Inter-SemiBold.ttf", 24), anchor="rm")
    for i in range(6):
        y = 90 + i * 46
        d.line([(24, y), (w - 24, y)], fill=(22, 30, 40), width=2)
    d.text((w / 2, h / 2 + 10), "DEMONSTRATION PROP", fill=(120, 132, 146), font=font(fonts, "Inter-SemiBold.ttf", 30), anchor="mm")
    d.text((w / 2, h / 2 + 52), "no data - not connected to the NERAM replay", fill=(96, 108, 122), font=font(fonts, "Inter-Medium.ttf", 22), anchor="mm")
    return im


def gas_panel(fonts, w=768, h=256):
    im = Image.new("RGB", (w, h), (226, 231, 236))
    d = ImageDraw.Draw(im)
    f = font(fonts, "Inter-SemiBold.ttf", 46)
    cols = [("O₂", (255, 255, 255), (20, 20, 20)), ("AIR", (30, 30, 30), (240, 240, 240)), ("VAC", (250, 204, 21), (20, 20, 20))]
    for i, (t, bg, fg) in enumerate(cols):
        x0 = 30 + i * 250
        d.rounded_rectangle([x0, 150, x0 + 210, 230], radius=12, fill=bg, outline=(90, 98, 108), width=3)
        d.text((x0 + 105, 190), t, fill=fg, font=f, anchor="mm")
    d.text((w / 2, 60), "MEDICAL GAS OUTLETS", fill=(60, 70, 82), font=font(fonts, "Inter-SemiBold.ttf", 34), anchor="mm")
    return im


def o2_label(fonts, w=1024, h=128):
    im = Image.new("RGB", (w, h), (246, 248, 250))
    d = ImageDraw.Draw(im)
    f = font(fonts, "Inter-SemiBold.ttf", 64)
    for k in range(2):
        x = w * (0.25 + 0.5 * k)
        d.text((x, h / 2), "O₂  OXYGEN", fill=(18, 22, 28), font=f, anchor="mm")
    d.rectangle([0, 0, w, 10], fill=(30, 41, 59))
    d.rectangle([0, h - 10, w, h], fill=(30, 41, 59))
    return im


def gauge(fonts, w=256):
    im = Image.new("RGB", (w, w), (240, 242, 245))
    d = ImageDraw.Draw(im)
    c = w / 2
    d.ellipse([6, 6, w - 6, w - 6], outline=(40, 48, 58), width=8)
    for k in range(11):
        a = math.radians(225 - k * 27)
        r0, r1 = c - 22, c - 40 if k % 5 == 0 else c - 32
        d.line([(c + r0 * math.cos(a), c - r0 * math.sin(a)), (c + r1 * math.cos(a), c - r1 * math.sin(a))], fill=(40, 48, 58), width=5)
    d.arc([30, 30, w - 30, w - 30], -45, 0, fill=(22, 163, 74), width=10)
    d.ellipse([c - 10, c - 10, c + 10, c + 10], fill=(30, 30, 30))
    d.text((c, c + 52), "kPa", fill=(80, 88, 98), font=font(fonts, "Inter-Medium.ttf", 26), anchor="mm")
    return im


def floor_tiles(w=1024, tile=256):
    rng = np.random.default_rng(7)
    base = np.array([150, 162, 176], float)
    img = np.ones((w, w, 3)) * base
    noise = rng.normal(0, 1, (w // 4, w // 4))
    noise = np.kron(noise, np.ones((4, 4)))
    img += noise[..., None] * 3.0
    speck = rng.random((w, w)) < 0.02
    img[speck] += rng.normal(0, 18, (speck.sum(), 1))
    for k in range(0, w, tile):
        img[k:k + 3, :, :] = base * 0.78
        img[:, k:k + 3, :] = base * 0.78
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return im.filter(ImageFilter.GaussianBlur(0.6))


def fabric(w=512, period=8):
    y, x = np.mgrid[0:w, 0:w]
    weave = 0.5 + 0.25 * np.sin(x * 2 * math.pi / period) * np.sign(np.sin(y * math.pi / period)) + 0.25 * np.sin(y * 2 * math.pi / period) * np.sign(np.sin(x * math.pi / period))
    rng = np.random.default_rng(3)
    v = 214 + 26 * weave + rng.normal(0, 4, (w, w))
    img = np.stack([v, v, v], -1)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def monitor_live(fonts, w=640, h=400):
    """Patient-monitor face for the animated prop (Sai, 18 Oct 2026). Scripts/Scene/MonitorPulse.cs draws the moving
    traces into the three bands at runtime; band rows here must match its constants. The waveforms are ILLUSTRATIVE
    drawings: no number is shown (readouts are dashes) and nothing comes from the NERAM replay or from patient data."""
    im = Image.new("RGB", (w, h), (6, 9, 13))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 50], fill=(16, 22, 30))
    d.text((18, 25), "PATIENT MONITOR", fill=WHITE, font=font(fonts, "Inter-SemiBold.ttf", 26), anchor="lm")
    d.text((w - 18, 25), "ILLUSTRATIVE", fill=AMBER, font=font(fonts, "Inter-SemiBold.ttf", 22), anchor="rm")
    bands = [("ECG II", (64, 220, 120), 58, 162, "HR", True), ("Pleth", (60, 200, 230), 170, 262, "SpO\u2082", True),
             ("Resp", (240, 200, 80), 270, 346, "TEMP \u00b0C", False)]
    for name, col, y0, y1, rd, dashes in bands:
        d.line([(16, y1 + 3), (462, y1 + 3)], fill=(20, 28, 38), width=1)
        d.text((20, y0 + 10), name, fill=col, font=font(fonts, "Inter-SemiBold.ttf", 17), anchor="lm")
        d.rounded_rectangle([474, y0 + 2, w - 12, y1 - 2], radius=8, outline=(30, 40, 52), width=2, fill=(9, 13, 18))
        d.text((486, y0 + 16), rd, fill=col, font=font(fonts, "Inter-SemiBold.ttf", 18), anchor="lm")
        if dashes:
            d.text((w - 30, (y0 + y1) / 2 + 10), "--", fill=col, font=font(fonts, "Inter-SemiBold.ttf", 44), anchor="rm")
        else:   # live value drawn by MonitorPulse.cs (replay patient temperature signal)
            d.text((486, y1 - 12), "replay signal", fill=(150, 130, 70), font=font(fonts, "Inter-Medium.ttf", 13), anchor="lm")
    d.rectangle([0, 354, w, h], fill=(12, 17, 23))
    d.text((18, 370), "BED 1", fill=TEAL, font=font(fonts, "Inter-SemiBold.ttf", 17), anchor="lm")
    d.text((90, 370), "Synthetic patient \u00b7 supine \u00b7 O\u2082 by face mask", fill=(190, 198, 208), font=font(fonts, "Inter-Medium.ttf", 16), anchor="lm")
    d.text((18, 390), "Warming: NERAM four-channel system (simulated)  \u00b7  waveforms illustrative", fill=(130, 140, 152), font=font(fonts, "Inter-Medium.ttf", 13), anchor="lm")
    return im


def device_screen(fonts, title, status, rows, foot, w=640, h=400, accent=TEAL, wave=None):
    """Equipment screen that describes the patient set-up in words. Readouts that would need real data show dashes;
    nothing here is a measured or invented value (Sai, 18 Oct 2026)."""
    im = Image.new("RGB", (w, h), (7, 10, 14))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 50], fill=(16, 22, 30))
    d.text((18, 25), title, fill=WHITE, font=font(fonts, "Inter-SemiBold.ttf", 25 if w > 520 else 22), anchor="lm")
    d.text((w - 18, 25), status, fill=accent, font=font(fonts, "Inter-SemiBold.ttf", 20), anchor="rm")
    y = 78
    for label, value in rows:
        d.text((24, y), label, fill=(140, 152, 166), font=font(fonts, "Inter-Medium.ttf", 18 if w > 520 else 16), anchor="lm")
        d.text((w - 24, y), value, fill=(225, 232, 240), font=font(fonts, "Inter-SemiBold.ttf", 20 if w > 520 else 17), anchor="rm")
        d.line([(24, y + 20), (w - 24, y + 20)], fill=(22, 30, 40), width=1)
        y += 44 if w > 520 else 38
    if wave is not None:
        y0, col = wave
        pts = [(24 + i * 2, y0 - 22 * max(0.0, math.sin(i / 18.0)) ** 2) for i in range((w - 48) // 2)]
        d.line(pts, fill=col, width=2)
    d.rectangle([0, h - 34, w, h], fill=(12, 17, 23))
    d.text((w / 2, h - 17), foot, fill=(130, 140, 152), font=font(fonts, "Inter-Medium.ttf", 14), anchor="mm")
    return im


def write_all(out_dir: Path, fonts: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    tex = {
        "label_ch1": label(fonts, 1, "LEFT HAND", TEAL),
        "label_ch2": label(fonts, 2, "RIGHT HAND", TEAL),
        "label_ch3": label(fonts, 3, "LEFT FOOT", AMBER),
        "label_ch4": label(fonts, 4, "RIGHT FOOT", AMBER),
        "watch_face": watch_face(fonts),
        "label_controller": controller_label(fonts),
        "controller_screen": controller_screen(fonts),
        "iv_label": iv_label(fonts),
        "screen_monitor": monitor_live(fonts),
        "screen_vent": device_screen(fonts, "VENTILATOR", "STANDBY", [("Patient", "breathing spontaneously"), ("Oxygen", "face mask, cylinder O\u2082"),
                                     ("Mode", "not ventilating"), ("Pressure", "-- cmH\u2082O"), ("Tidal volume", "-- mL")],
                                     "Standby while the patient breathes on mask O\u2082", wave=(330, (240, 200, 80))),
        "screen_pump": device_screen(fonts, "INFUSION PUMP", "LINE 1", [("Line", "IV, right forearm"), ("Rate", "-- mL/h"), ("Volume", "-- mL"),
                                     ("Fluid warming", "not modelled")], "IV fluids are not part of the NERAM model", w=512, h=320),
        "screen_anaesthesia": device_screen(fonts, "ANAESTHESIA WORKSTATION", "CASE IN PROGRESS", [("Airway", "face mask"), ("Fresh gas", "O\u2082 -- L/min"),
                                     ("Breathing", "spontaneous"), ("Temperature", "see NERAM dashboard"), ("Warming", "NERAM, simulated")],
                                     "Synthetic case replay \u00b7 NERAM proof-of-concept"),
        "gas_panel": gas_panel(fonts),
        "o2_label": o2_label(fonts),
        "gauge": gauge(fonts),
        "floor_tiles": floor_tiles(),
        "fabric_weave": fabric(),
    }
    for k, im in tex.items():
        im.save(out_dir / f"{k}.png", optimize=True)
    return sorted(tex)


def controller_screen(fonts, w=1024, h=230):
    """Front display of the CAD bedside controller (Sai, 18 Oct 2026). A prop like the watch face: the replay values are
    shown in the dashboard, so the screen names the channels and says so instead of showing numbers."""
    im = Image.new("RGB", (w, h), (7, 11, 15))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, w - 5, h - 5], radius=14, outline=(26, 52, 58), width=3)
    d.text((26, 42), "NERAM", fill=TEAL, font=font(fonts, "Inter-SemiBold.ttf", 52), anchor="lm")
    d.text((236, 46), "supervisory controller", fill=(150, 162, 176), font=font(fonts, "Inter-Medium.ttf", 28), anchor="lm")
    d.text((w - 26, 44), "SIMULATED", fill=AMBER, font=font(fonts, "Inter-SemiBold.ttf", 26), anchor="rm")
    names = (("CH1", "L HAND", TEAL), ("CH2", "R HAND", TEAL), ("CH3", "L FOOT", AMBER), ("CH4", "R FOOT", AMBER))
    tw = (w - 52 - 3 * 14) / 4
    for i, (ch, limb, acc) in enumerate(names):
        x0 = 26 + i * (tw + 14)
        d.rounded_rectangle([x0, 88, x0 + tw, 176], radius=10, fill=(16, 24, 32), outline=acc, width=3)
        d.text((x0 + 18, 132), ch, fill=acc, font=font(fonts, "Inter-SemiBold.ttf", 36), anchor="lm")
        d.text((x0 + tw - 16, 132), limb, fill=WHITE, font=font(fonts, "Inter-Medium.ttf", 26), anchor="rm")
    d.text((w / 2, 204), "live replay values on the dashboard", fill=(110, 122, 136), font=font(fonts, "Inter-Medium.ttf", 22), anchor="mm")
    return im
