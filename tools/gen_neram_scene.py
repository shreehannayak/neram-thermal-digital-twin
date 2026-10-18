#!/usr/bin/env python3
"""Generate the NERAM theatre scene geometry and textures for Unity (offline, deterministic).

Outputs (inside the Unity project):
  unity_editor/Assets/NERAM_Generated/MeshData/neram_scene.bytes   binary bundle (nodes + meshes), see meshgen/scene.py
  unity_editor/Assets/NERAM_Generated/MeshData/scene_manifest.json materials used, node list, statistics, sha256
  unity_editor/Assets/NERAM_Generated/Textures/*.png               labels, prop screens, floor, fabric
  docs/previews/*.png                                               offline geometry previews (NOT Unity screenshots)

Unity side: NERAM > 1. Run full setup reads the bundle (Assets/Editor/NeramSceneBuilder.cs), creates Mesh assets and
the scene. Requires numpy, scikit-image and Pillow:  python tools/gen_neram_scene.py [--no-preview]
All geometry is a visual stand-in: no dimension here is a CAD or design value.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "meshgen"))

import patient as P  # noqa: E402
import room as RM  # noqa: E402
import textures as TX  # noqa: E402
from geom import cylinder, merge, rot_x, rotation_between, rounded_box, sphere, tube  # noqa: E402
from scene import SceneOut, read_bundle  # noqa: E402
from palette import M as PALETTE, material_name  # noqa: E402

ROOT = HERE.parent
ASSETS = ROOT / "unity_editor" / "Assets"
GEN = ASSETS / "NERAM_Generated"
FONTS = ASSETS / "Resources" / "NERAM" / "Fonts"

REGION_NODE = {
    "torso": "Region_Torso", "arm_left": "Region_Arm_Left", "arm_right": "Region_Arm_Right",
    "leg_left": "Region_Leg_Left", "leg_right": "Region_Leg_Right", "head": "Head_Neck",
}


def build(sc: SceneOut, log):
    t0 = time.time()
    asm = sc.node("NERAM_Assembly", flags="assembly")
    # ---------------------------------------------------------------- patient
    man = sc.node("Patient_Mannequin_PLACEHOLDER", asm, flags="placeholder:Patient_Mannequin")
    for region, node in REGION_NODE.items():
        sc.node(node, man, region="" if region == "head" else region)
    skin = P.build_skin(0.0052)
    log(f"skin {skin.tris} tris ({time.time() - t0:.0f}s)")
    for region, m in P.split_by_region(skin).items():
        sc.add(REGION_NODE[region], f"Skin_{region}", m, "MAT_Skin")
    gown = P.build_gown()
    for region, m in P.split_by_region(gown).items():
        sc.add(REGION_NODE[region], f"Gown_{region}", m, "MAT_Gown")
    drape = P.build_drape()
    for region, m in P.split_by_region(drape).items():
        sc.add(REGION_NODE[region], f"Drape_{region}", m, "MAT_Drape")
    log(f"gown {gown.tris} / drape {drape.tris} tris ({time.time() - t0:.0f}s)")

    # ---------------------------------------------------------------- warming modules (CAD role names)
    relief = {}
    roles = {1: ("Left_Hand_Module", "hand_left"), 2: ("Right_Hand_Module", "hand_right"), 3: ("Left_Foot_Module", "foot_left"), 4: ("Right_Foot_Module", "foot_right")}
    for ch, (role, region) in roles.items():
        s = P.LEFT if ch in (1, 3) else P.RIGHT
        if ch <= 2:
            parts, tip = P.build_hand_module(s)
            pos, R = P.SK.W[s], np.eye(3)  # local +Y = away from the skin (exploded view direction)
        else:
            parts, tip = P.build_foot_module(s)
            lat, length, upf = P.SK.foot_axes(s)
            # local +Y -> away from the sole (plantar direction), local +Z -> heel-to-toe axis
            yv = -upf
            zv = length - yv * np.dot(length, yv)
            zv /= np.linalg.norm(zv)
            xv = np.cross(yv, zv)
            R = np.stack([xv, yv, zv], axis=1)
            pos = P.SK.foot_to_world(s, 0.0, 0.12, 0.0)
        node = sc.node(role + "_PLACEHOLDER", asm, pos=pos, R=R, region=region, flags=f"placeholder:{role};module:{ch}")
        for name, (mesh, mat) in parts.items():
            sc.add(node, name, mesh, mat)
        relief[ch] = tip
    wparts, screen_pos = P.build_watch()
    wn = sc.node("Wearable_Watch", asm, pos=screen_pos, region="wearable", flags="wearable")
    for name, (mesh, mat) in wparts.items():
        sc.add(wn, name, mesh, mat)
    sc.node("Wearable_Screen_Anchor", wn, pos=screen_pos + np.array([0, 0.004, 0]), flags="anchor:wearable")
    log(f"modules + wearable ({time.time() - t0:.0f}s)")

    # ---------------------------------------------------------------- illustrative vessels (Internal View, hidden by default)
    vn = sc.node("Illustrative_Vessels", asm, flags="vessels")
    sc.add(vn, "Vessel_Heart_Illustrative", sphere(0.024, center=(0.012, 0.105, 0.47), scale=(1.0, 0.85, 1.2)), "MAT_VesselArtery")
    for name, kind, pts, radius in P.build_vessels():
        path = P.smooth_polyline(pts, 8)
        node = sc.node(f"Vessel_{name}", vn, pos=path[0], flags=f"vessel:{kind}")
        for k, q in enumerate(path[:: max(1, len(path) // 24)]):
            sc.node(f"wp{k:02d}_{name}", node, pos=q, flags="waypoint")
        sc.add(node, f"Vessel_{name}_Tube", tube(path, radius, 10), "MAT_VesselArtery" if kind == "artery" else "MAT_VesselVein")

    # ---------------------------------------------------------------- table, controller, cables
    RM.build_table(sc, asm, P.SK.arm_dir, P.SK.S)
    ctrl, ports = RM.build_controller(sc, asm)
    routes = {
        1: [(0.36, -0.15, -0.3), (0.34, -0.15, 0.2), (0.45, -0.07, 0.42), (0.6, -0.025, 0.44)],
        2: [(0.3, -0.17, -0.2), (0.12, -0.17, 0.28), (-0.3, -0.16, 0.36), (-0.55, -0.06, 0.42), (-0.6, -0.02, 0.44)],
        3: [(0.38, -0.13, -0.72), (0.26, -0.03, -0.86)],
        4: [(0.32, -0.15, -0.86), (0.05, -0.08, -0.98), (-0.2, -0.01, -0.9)],
    }
    for ch in range(1, 5):
        cn = sc.node(f"Cable_CH{ch}_PLACEHOLDER", asm, pos=ports[ch - 1], flags=f"placeholder:Cable_CH{ch};cable")
        pts = [ports[ch - 1], ports[ch - 1] + np.array([0, -0.09, 0])] + [np.array(p) for p in routes[ch]] + [relief[ch]]
        for k, p in enumerate(pts):
            sc.node(f"wp{k:02d}_CH{ch}", cn, pos=p, flags="waypoint")  # CableTube uses children named "wp*"
        plug = rounded_box((0.018, 0.026, 0.018), 0.004, center=ports[ch - 1] + np.array([0, -0.014, 0]))
        sc.add(cn, f"Connector_CH{ch}", plug, "MAT_Connector")

    # ---------------------------------------------------------------- theatre
    RM.build_room(sc)
    heads = RM.build_surgical_lights(sc)
    RM.build_anaesthesia(sc)
    RM.build_monitor_boom(sc)
    acc, acc_dir = P.iv_access_point()
    RM.build_iv_pump(sc, acc, acc_dir)
    RM.build_ventilator(sc)
    RM.build_carts(sc)
    RM.build_suction(sc)
    RM.build_o2(sc)
    log(f"theatre ({time.time() - t0:.0f}s)")

    # ---------------------------------------------------------------- lights (created by the editor builder)
    lights = sc.node("OT_Lights")
    for k, (pos, aim) in enumerate(heads):
        R = rotation_between((0, 0, 1), aim)  # Unity lights shine along local +Z
        sc.node(f"Surgical_Spot_{k}", lights, pos=pos + aim * 0.03, R=R, flags="light:spot;intensity=4.5;range=4.5;angle=34;inner=18;color=1,0.97,0.93;shadows=soft")
    sc.node("Key_Light", lights, R=rotation_between((0, 0, 1), np.array([0.35, -0.8, 0.48])), flags="light:directional;intensity=0.8;color=0.95,0.97,1;shadows=soft")
    for k, (x, z) in enumerate(((-2.0, -2.0), (2.0, -2.0), (-2.0, 2.0), (2.0, 2.0))):
        sc.node(f"Room_Fill_{k}", lights, pos=(x, 1.9, z), flags="light:point;intensity=2.6;range=7;color=0.92,0.95,1;shadows=none")
    sc.node("Laminar_Fill", lights, pos=(0, 2.0, 0), R=rotation_between((0, 0, 1), (0, -1, 0)), flags="light:spot;intensity=4.5;range=5;angle=100;inner=60;color=0.97,0.98,1;shadows=none")

    # ---------------------------------------------------------------- free-roam navigation bounds (camera keep-out volumes)
    nav = sc.node("NERAM_Navigation")
    sc.node("Nav_Room", nav, pos=(0.0, (RM.FLOOR + RM.CEIL) / 2, (RM.ZH + RM.ZF) / 2), flags=f"navroom:{RM.XW - 0.05},{(RM.CEIL - RM.FLOOR) / 2 - 0.05},{(RM.ZH - RM.ZF) / 2 - 0.05}")
    keepouts = {
        "Patient_Table": ((0.0, -0.33, -0.02), (0.36, 0.62, 1.03)),
        "Arms_Boards": ((0.0, -0.04, 0.47), (1.0, 0.16, 0.13)),
        "Anaesthesia": ((-0.98, -0.0, 1.42), (0.5, 1.0, 0.45)),
        "Ventilator": ((-1.75, -0.2, 0.05), (0.33, 0.85, 0.33)),
        "IV_Stand": ((-0.62, 0.2, 1.18), (0.3, 1.1, 0.3)),
        "Trolley": ((1.25, -0.4, -1.35), (0.45, 0.48, 0.36)),
        "Supply_Cart": ((2.75, -0.3, 0.2), (0.3, 0.6, 0.36)),
        "Cabinets": ((1.85, 0.0, 3.0), (0.85, 1.4, 0.32)),
        "O2_Cylinders": ((2.49, -0.3, 3.1), (0.35, 0.6, 0.22)),
        "Controller": ((0.45, -0.04, -0.58), (0.14, 0.12, 0.14)),
        # surgical light heads (r ~0.32 m, tilted) - added after the in-Unity Free Roam test flew into a head
        "Light_Head_0": ((0.78, 1.64, 0.38), (0.40, 0.18, 0.40)),
        "Light_Head_1": ((-0.80, 1.62, -0.36), (0.40, 0.18, 0.40)),
    }
    for k, (c, h) in keepouts.items():
        sc.node(f"Nav_KeepOut_{k}", nav, pos=c, flags=f"keepout:{h[0]},{h[1]},{h[2]}")

    # ---------------------------------------------------------------- anchors + camera presets
    anchors = sc.node("NERAM_Anchors")
    sc.node("ThermalStateAnchor", anchors, pos=(0.0, 0.32, 0.36))
    presets = sc.node("CameraPresets", anchors)
    plist = [
        ("Overview", (0.0, 0.12, -0.05), -24, 27, 2.75),
        ("Patient (top)", (0.0, 0.05, 0.05), 0, 78, 1.95),
        ("Feet & soles CH3/CH4", (0.0, 0.11, -0.80), -12, 16, 0.95),
        ("Left hand CH1", P.SK.W[P.LEFT] + P.SK.arm_dir[P.LEFT] * 0.06, -62, 40, 0.62),
        ("Right hand CH2", P.SK.W[P.RIGHT] + P.SK.arm_dir[P.RIGHT] * 0.06, 62, 40, 0.62),
        ("Wearable (wrist)", screen_pos, 40, 55, 0.42),
        ("Chest / torso", (0.0, 0.14, 0.4), -18, 46, 1.15),
        ("Bedside controller", ports[1] + np.array([0, 0.09, 0]), -70, 18, 0.8),
        ("Theatre", (0.0, 0.3, 0.6), -32, 22, 5.2),
    ]
    for i, (label, pivot, yaw, pitch, dist) in enumerate(plist):
        sc.node(f"Preset_{i}_{label.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_').replace('&', 'and')}", presets, pos=pivot, flags=f"preset:{label}|{yaw}|{pitch}|{dist}|{i}")
    return plist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--preview-dir", default=str(ROOT / "docs" / "previews"))
    a = ap.parse_args()
    log = lambda m: print("[gen]", m, flush=True)
    tex = TX.write_all(GEN / "Textures", FONTS)
    log(f"textures: {len(tex)}")
    sc = SceneOut()
    plist = build(sc, log)
    sha, size = sc.write(GEN / "MeshData" / "neram_scene.bytes")
    ver, nodes, meshes = read_bundle(GEN / "MeshData" / "neram_scene.bytes")
    assert len(nodes) == len(sc.nodes) and len(meshes) == len(sc.meshes)
    st = sc.stats()
    used_tex = sorted({m["material"][4:] for m in sc.meshes if m["material"].startswith("TEX:")})
    missing_tex = [t for t in used_tex if t not in tex]
    assert not missing_tex, missing_tex
    manifest = {
        "generator": "tools/gen_neram_scene.py",
        "bundle": "NERAM_Generated/MeshData/neram_scene.bytes",
        "bundle_sha256": sha,
        "bundle_bytes": size,
        "stats": st,
        "materials": sc.materials(),
        "textures": tex,
        "regions": sorted({n["region"] for n in sc.nodes if n["region"]}),
        "nodes": [n["name"] for n in sc.nodes],
        "note": "Visual stand-in geometry; not CAD; no dimension is a design value. Coordinate contract: metres, Y up, origin = table-top centre, +Z toward the head, patient's LEFT = +X.",
    }
    (GEN / "MeshData" / "scene_manifest.json").write_text(json.dumps(manifest, indent=1))
    missing_mat = sorted({material_name(m["material"]) for m in sc.meshes} - set(PALETTE))
    assert not missing_mat, f"materials used by meshes but missing from the palette: {missing_mat}"
    (GEN / "MeshData" / "materials.json").write_text(json.dumps({"materials": list(PALETTE.values())}, indent=1))
    log(f"bundle {size / 1e6:.1f} MB sha256 {sha[:12]} · {st}")
    if not a.no_preview:
        import preview_scene
        preview_scene.render_all(sc, Path(a.preview_dir), plist, log)


if __name__ == "__main__":
    main()
