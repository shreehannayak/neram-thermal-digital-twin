"""Render offline previews of the generated scene from the camera presets (geometry check only, NOT Unity output)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from palette import M, material_name, preview_color
from preview import fill_holes, render, unity_camera

TEXDIR = Path(__file__).resolve().parents[2] / "unity_editor" / "Assets" / "NERAM_Generated" / "Textures"


def items_for(sc, skip=()):
    cache = {}
    items = []
    for m in sc.meshes:
        name = m["name"]
        if any(k in name for k in skip):
            continue
        ref = m["material"]
        mn = material_name(ref)
        spec = M.get(mn, {})
        tex = None
        if ref.startswith("TEX:"):
            t = ref[4:]
            if t not in cache:
                cache[t] = np.asarray(Image.open(TEXDIR / f"{t}.png").convert("RGB"))
            tex = cache[t]
        emis = spec.get("emission") if spec and any(spec.get("emission", [0, 0, 0])) else None
        if emis is not None:
            emis = [min(1.0, e * 0.5) for e in emis]
        items.append((m["mesh"], preview_color(ref), emis, 1.0, tex))
    return items


def render_all(sc, out: Path, presets, log):
    out.mkdir(parents=True, exist_ok=True)
    hidden_inner = ("_Liner", "_Insulation", "Sensor_A", "Sensor_B") 
    items = items_for(sc, skip=("Ceiling", "Laminar", "Wall_Foot", "Skirting_Foot"))
    picks = {"Overview": "01_overview_default_camera.png", "Feet & soles CH3/CH4": "02_feet_soles_ch3_ch4.png",
             "Left hand CH1": "03_left_hand_ch1.png", "Right hand CH2": "04_right_hand_ch2.png", "Wearable (wrist)": "05_wearable.png",
             "Theatre": "06_theatre.png", "Patient (top)": "07_patient_top.png", "Bedside controller": "08_controller.png"}
    for label, pivot, yaw, pitch, dist in presets:
        if label not in picks:
            continue
        img, dep = render(items, unity_camera(pivot, yaw, pitch, dist), size=(1600, 900), fov=40, samples_per_px=6.0)
        img = fill_holes(img, dep)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 868, 1600, 900], fill=(8, 10, 13))
        d.text((12, 876), f"OFFLINE GEOMETRY PREVIEW (numpy rasterizer, flat colours) - not a Unity/URP render - camera preset: {label}", fill=(200, 205, 212))
        img.save(out / picks[label])
        log(f"preview {picks[label]}")
        if label == "Patient (top)":
            # Internal View approximation: body surfaces hidden instead of translucent (the rasterizer has no blending)
            inner = items_for(sc, skip=("Ceiling", "Laminar", "Wall_Foot", "Skirting_Foot", "Skin_", "Gown_", "Drape_"))
            img, dep = render(inner, unity_camera(pivot, yaw, pitch, dist), size=(1600, 900), fov=40, samples_per_px=6.0)
            img = fill_holes(img, dep)
            d = ImageDraw.Draw(img)
            d.rectangle([0, 868, 1600, 900], fill=(8, 10, 13))
            d.text((12, 876), "OFFLINE PREVIEW - Internal View approximation (body surfaces hidden) - ILLUSTRATIVE ANATOMY, NOT PATIENT-SPECIFIC FLOW DATA", fill=(200, 205, 212))
            img.save(out / "09_internal_view_vessels.png")
            log("preview 09_internal_view_vessels.png")
