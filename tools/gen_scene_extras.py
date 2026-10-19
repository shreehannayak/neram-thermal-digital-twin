#!/usr/bin/env python3
"""Scene extras for the NERAM viewer (Sai, 18 Oct 2026): patient head detail (theatre cap, ears, brows, closed-eye
lash lines), an anaesthesia face mask with head strap, a portable O2 cylinder on a trolley beside the head with
flowmeter, humidifier and tubing to the mask, an ILLUSTRATIVE airway (pharynx, trachea, bronchi, lungs) shown in the
Internal view, a surgeon figure that can be walked around (I J K L, U O), and the airflow paths used at runtime.

Writes unity_editor/Assets/NERAM_Generated/MeshData/scene_extras.json, applied by Editor/NeramSceneExtras.cs
(menu NERAM > Scene > Apply scene extras, automation job "extras"). Coordinates are NERAM_Assembly-local, the same
frame as tools/gen_neram_scene.py (patient supine, face +Y, head +Z, table top y = 0, floor y = -0.85).

Everything here is a visual stand-in. The mask, oxygen set-up and airway are illustrative: no gas flow, oxygen
concentration, respiratory rate or anatomy of a real patient is modelled or implied. Usage:
    python tools/gen_scene_extras.py [--preview out_dir]      (numpy, scikit-image; preview needs the glrender tool)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "meshgen"))
import patient as P  # noqa: E402
from geom import (Mesh, cylinder, merge, rot_x, rot_z, rotation_between, rounded_box, sd_capsule,  # noqa: E402
                  sd_ellipsoid, sd_round_box, sdf_mesh, smax, smin, sphere, torus, tube)

ROOT = HERE.parent
OUT = ROOT / "unity_editor" / "Assets" / "NERAM_Generated" / "MeshData" / "scene_extras.json"
FLOOR = -0.85

MATERIALS = [  # name, rgba, smoothness, metallic, transparent, emission
    ("MAT_Cap", (0.40, 0.58, 0.84, 1), 0.10, 0.0, False, None),
    ("MAT_Hair", (0.16, 0.11, 0.08, 1), 0.25, 0.0, False, None),
    ("MAT_Lash", (0.06, 0.05, 0.05, 1), 0.2, 0.0, False, None),
    ("MAT_MaskClear", (0.86, 0.93, 0.96, 0.30), 0.92, 0.0, True, None),
    ("MAT_MaskCushion", (0.55, 0.80, 0.92, 0.62), 0.6, 0.0, True, None),
    ("MAT_MaskElbow", (0.25, 0.55, 0.75, 1), 0.5, 0.0, False, None),
    ("MAT_O2Tube", (0.72, 0.96, 0.82, 0.42), 0.9, 0.0, True, None),
    ("MAT_Scrubs", (0.10, 0.44, 0.47, 1), 0.12, 0.0, False, None),
    ("MAT_ScrubsDark", (0.07, 0.33, 0.36, 1), 0.12, 0.0, False, None),
    ("MAT_SurgeonCap", (0.24, 0.42, 0.72, 1), 0.12, 0.0, False, None),
    ("MAT_SurgicalMask", (0.58, 0.78, 0.92, 1), 0.10, 0.0, False, None),
    ("MAT_Glove", (0.36, 0.56, 0.86, 1), 0.45, 0.0, False, None),
    ("MAT_Clog", (0.92, 0.93, 0.95, 1), 0.5, 0.0, False, None),
    ("MAT_Airway", (0.93, 0.56, 0.60, 0.55), 0.6, 0.0, True, None),
    ("MAT_LungGhost", (0.96, 0.62, 0.66, 0.26), 0.6, 0.0, True, None),
    ("MAT_AirParticle", (0.62, 0.95, 1.00, 1), 0.8, 0.0, False, (0.55, 1.5, 1.9)),
    ("MAT_FlowFloat", (0.20, 0.85, 0.35, 1), 0.7, 0.0, False, None),
    ("MAT_GaugeFace", (0.95, 0.96, 0.97, 1), 0.6, 0.0, False, None),
    ("MAT_GreenCap", (0.12, 0.62, 0.30, 1), 0.5, 0.0, False, None),
    # 19 Oct: detailed surgeon, instruments, supplies
    ("MAT_SurgeonSkin", (0.80, 0.60, 0.49, 1), 0.42, 0.0, False, None),
    ("MAT_EyeWhite", (0.93, 0.92, 0.89, 1), 0.85, 0.0, False, None),
    ("MAT_Iris", (0.27, 0.18, 0.11, 1), 0.90, 0.0, False, None),
    ("MAT_Pupil", (0.02, 0.02, 0.02, 1), 0.95, 0.0, False, None),
    ("MAT_SurgeonCapBand", (0.18, 0.33, 0.60, 1), 0.15, 0.0, False, None),
    ("MAT_MaskLoop", (0.92, 0.94, 0.96, 1), 0.2, 0.0, False, None),
    ("MAT_Badge", (0.95, 0.96, 0.97, 1), 0.55, 0.0, False, None),
    ("MAT_SterileTowel", (0.17, 0.42, 0.55, 1), 0.10, 0.0, False, None),
    ("MAT_Steel", (0.80, 0.81, 0.83, 1), 0.86, 1.0, False, None),
    ("MAT_Instrument", (0.86, 0.87, 0.89, 1), 0.90, 1.0, False, None),
    ("MAT_Gauze", (0.97, 0.97, 0.95, 1), 0.08, 0.0, False, None),
    ("MAT_SyringeClear", (0.92, 0.96, 0.98, 0.38), 0.95, 0.0, True, None),
    ("MAT_SyringePlunger", (0.96, 0.96, 0.96, 1), 0.5, 0.0, False, None),
    ("MAT_SuturePack", (0.55, 0.36, 0.70, 1), 0.55, 0.0, False, None),
    ("MAT_SuturePack2", (0.18, 0.58, 0.42, 1), 0.55, 0.0, False, None),
    ("MAT_SharpsYellow", (0.97, 0.80, 0.10, 1), 0.45, 0.0, False, None),
    ("MAT_BottleAmber", (0.45, 0.22, 0.06, 0.88), 0.9, 0.0, True, None),
    ("MAT_BottleCap", (0.95, 0.95, 0.95, 1), 0.5, 0.0, False, None),
    ("MAT_SpecimenPot", (0.93, 0.95, 0.97, 0.55), 0.9, 0.0, True, None),
    ("MAT_GloveBox", (0.92, 0.94, 0.97, 1), 0.4, 0.0, False, None),
]
TEX = "Assets/NERAM_Generated/Textures"
NORMAL_MAPS = {  # material -> (texture, strength, tiling); fabrics and skin get a fine surface normal map (needs UVs)
    "MAT_Scrubs": ("weave_normal.png", 0.45, 14.0), "MAT_ScrubsDark": ("weave_normal.png", 0.45, 14.0),
    "MAT_SurgeonCap": ("nonwoven_normal.png", 0.30, 10.0), "MAT_SurgicalMask": ("nonwoven_normal.png", 0.22, 14.0),
    "MAT_SterileTowel": ("weave_normal.png", 0.7, 10.0), "MAT_Gauze": ("weave_normal.png", 0.9, 22.0),
    "MAT_SurgeonSkin": ("skin_normal.png", 0.25, 18.0), "MAT_Glove": ("skin_normal.png", 0.10, 18.0),
}

PARTS = []
BIN = bytearray()
BIN_PATH = ROOT / "unity_editor" / "Assets" / "NERAM_Generated" / "MeshData" / "scene_extras_mesh.bytes"
UV_MATS = set(NORMAL_MAPS) | {"MAT_Skin", "MAT_Gown"}
BUDGET = {"Patient_Theatre_Cap": 9000, "Airway_Lung_Right": 4500, "Airway_Lung_Left": 4500,
          "Patient_Ear_Left": 2600, "Patient_Ear_Right": 2600}
sys.path.insert(0, str(ROOT / "cad" / "tools"))


def add(group, name, mesh: Mesh, mat, parent="NERAM_Assembly", replace=None, binary=False):
    mesh = mesh if isinstance(mesh, Mesh) else merge(mesh)
    if mesh is None or len(mesh.F) == 0:
        return
    if name in BUDGET and len(mesh.F) > BUDGET[name]:
        import qem
        Fw = mesh.F
        if np.mean(np.sum(vertex_normals((mesh.V, Fw)) * mesh.N, 1)) < 0:   # winding disagrees with SDF normals
            Fw = Fw[:, ::-1]
        V2, F2 = qem.decimate(mesh.V, Fw, BUDGET[name])
        mesh = mk(V2, F2)
    N = mesh.N if getattr(mesh, "N", None) is not None and len(mesh.N) == len(mesh.V) else vertex_normals(mesh)
    if binary or len(mesh.V) > 4000:
        uv = None
        if mat in UV_MATS:
            from geom import box_uv
            uv = np.asarray(box_uv(mesh.V, N, 1.0), np.float32)
        off = len(BIN)
        BIN.extend(np.asarray(mesh.V, "<f4").tobytes()); BIN.extend(np.asarray(N, "<f4").tobytes())
        if uv is not None:
            BIN.extend(np.asarray(uv, "<f4").tobytes())
        BIN.extend(np.asarray(mesh.F, "<i4").ravel().tobytes())
        PARTS.append(dict(group=group, name=name, parent=parent, mat=mat, replace=replace or "", bin=off, nv=len(mesh.V),
                          ni=int(mesh.F.size), has_uv=uv is not None))
        return
    PARTS.append(dict(group=group, name=name, parent=parent, mat=mat,
                      v=np.round(mesh.V, 5).ravel().tolist(), n=np.round(N, 4).ravel().tolist(), f=mesh.F.astype(int).ravel().tolist()))


def vertex_normals(m):
    V, F = (m.V, m.F) if hasattr(m, "V") else m
    N = np.zeros_like(V)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)


def mk(V, F):
    V = np.asarray(V, float); F = np.asarray(F, int)
    return Mesh(V, vertex_normals((V, F)), F)


def catmull(pts, k=10):
    pts = [np.asarray(p, float) for p in pts]
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
        for t in np.linspace(0, 1, k, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return np.array(out)


def head_surface_y(x, z, y0=0.26):
    """Highest y on the patient head SDF at (x, z) (face points +Y)."""
    ys = np.linspace(y0, 0.0, 600)
    P_ = np.stack([np.full_like(ys, x), ys, np.full_like(ys, z)], 1)
    d = P.sdf_head(P_)
    i = np.argmax(d < 0)
    return float(ys[i]) if d[i] < 0 else float("nan")


def head_radius(center, direction, rmax=0.14):
    rs = np.linspace(rmax, 0.0, 700)
    P_ = center[None, :] + rs[:, None] * direction[None, :]
    d = P.sdf_head(P_)
    i = np.argmax(d < 0)
    return float(rs[i])


# ======================================================================================== patient head
def build_head():
    def cut(Pp):  # positive above the cap edge (forehead high at the front, lower behind the ears)
        return Pp[..., 2] - (0.851 - 0.42 * (0.19 - Pp[..., 1]))

    def sdf_cap(Pp):
        d = sd_ellipsoid(Pp, (0, 0.106, 0.818), (0.087, 0.106, 0.112))
        d = smin(d, sd_ellipsoid(Pp, (0, 0.090, 0.842), (0.083, 0.088, 0.083)), 0.02)       # bouffant crown
        wrinkle = 0.0011 * np.sin(Pp[..., 0] * 260) * np.sin(Pp[..., 2] * 210 + Pp[..., 1] * 90)
        d = d + wrinkle
        d = smax(d, -cut(Pp), 0.004)
        band = smax(sd_ellipsoid(Pp, (0, 0.106, 0.818), (0.0905, 0.1095, 0.1155)), np.abs(cut(Pp) - 0.004) - 0.0045, 0.002)
        d = smin(d, band, 0.003)                                                           # elastic rim
        return np.maximum(d, -Pp[..., 1] + 0.004)                                            # flat on the head pad
    add("head", "Patient_Theatre_Cap", sdf_mesh(sdf_cap, (-0.10, 0.0, 0.69), (0.10, 0.23, 0.95), 0.0022), "MAT_Cap", parent="Head_Neck")

    def sdf_ear(Pp, s):
        c = np.array([s * 0.0835, 0.102, 0.797])
        q = Pp - c
        q = q @ rot_x(8).T
        body = sd_ellipsoid(q, (0, 0, 0), (0.0065, 0.019, 0.029))
        concha = sd_ellipsoid(q, (s * 0.006, 0.003, -0.004), (0.0045, 0.010, 0.013))
        body = smax(body, -concha, 0.003)
        helix = sd_capsule(q, (s * 0.002, -0.012, 0.022), (s * 0.002, 0.010, 0.020), 0.0042, 0.0038)
        helix = smin(helix, sd_capsule(q, (s * 0.002, 0.012, 0.016), (s * 0.002, 0.014, -0.012), 0.0038, 0.003), 0.004)
        lobe = sd_ellipsoid(q, (0, 0.004, -0.026), (0.0055, 0.008, 0.008))
        return smin(smin(body, helix, 0.004), lobe, 0.004)
    for s, w in ((1, "Left"), (-1, "Right")):
        c = np.array([s * 0.0835, 0.102, 0.797])
        add("head", f"Patient_Ear_{w}", sdf_mesh(lambda Q, s=s: sdf_ear(Q, s), c - 0.04, c + 0.04, 0.0012), "MAT_Skin", parent="Head_Neck")

    for s, w in ((1, "Left"), (-1, "Right")):
        # eyebrow: arc of short strands on the brow ridge
        xs = np.linspace(0.010, 0.050, 14) * s
        pts = []
        for x in xs:
            z = 0.832 + 0.004 * math.sin(math.pi * (abs(x) - 0.010) / 0.040)
            pts.append((x, head_surface_y(x, z) + 0.0012, z))
        r = 0.0022 * np.sin(np.linspace(0.35, math.pi - 0.2, len(pts)))
        add("head", f"Patient_Brow_{w}", tube(np.array(pts), 0.002, segments=8, radii=np.maximum(r, 0.0009)), "MAT_Hair", parent="Head_Neck")
        # closed eyelid lash line
        xs = np.linspace(0.017, 0.043, 12) * s
        pts = [(x, head_surface_y(x, 0.8035 - 0.0028 * math.sin(math.pi * (abs(x) - 0.017) / 0.026)) + 0.0008,
                0.8035 - 0.0028 * math.sin(math.pi * (abs(x) - 0.017) / 0.026)) for x in xs]
        add("head", f"Patient_Lashes_{w}", tube(np.array(pts), 0.0009, segments=6), "MAT_Lash", parent="Head_Neck")


# ======================================================================================== anaesthesia mask
def mask_rim():
    ts = np.linspace(0, 2 * math.pi, 72, endpoint=False)
    pts = []
    for t in ts:
        # pear-shaped outline round nose and mouth: narrow at the nasal bridge (top, +z), wide over the chin
        zc, ax = 0.763, 0.040 + 0.010 * (1 - math.cos(t)) * 0.5      # t=0 -> nasal bridge
        z = zc + 0.060 * math.cos(t)
        x = ax * math.sin(t) * (0.72 + 0.28 * (1 - math.cos(t)) * 0.5)
        y = head_surface_y(x, z) + 0.0045
        pts.append((x, y, z))
    return np.array(pts)


def build_mask():
    rim = mask_rim()
    add("mask", "O2_Mask_Cushion", tube(np.vstack([rim, rim[:1]]), 0.0065, segments=10, closed_ends=False), "MAT_MaskCushion")
    apex = np.array([0.0, rim[:, 1].max() + 0.050, 0.770])
    rings, n = 14, len(rim)
    V, F = [], []
    for i in range(rings + 1):
        t = i / rings
        e = 1 - (1 - t) ** 2.2
        for p in rim:
            q = p + (apex - p) * t
            q[1] = p[1] + (apex[1] - p[1]) * e
            V.append(q)
    for i in range(rings):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            F += [[a, b, a + n], [b, b + n, a + n]]
    V = np.array(V)
    Fo = np.array(F)
    front = mk(V, Fo)
    shell = merge([front, Mesh(V.copy(), -front.N, Fo[:, ::-1].copy())])
    add("mask", "O2_Mask_Shell", shell, "MAT_MaskClear")
    # 22 mm swivel elbow on top of the mask, outlet towards the head end
    elbow_path = catmull([apex - [0, 0.004, 0], apex + [0, 0.014, 0.002], apex + [0, 0.024, 0.016], apex + [0, 0.026, 0.040]], 6)
    add("mask", "O2_Mask_Elbow", tube(elbow_path, 0.0105, segments=20), "MAT_MaskElbow")
    # head strap from the mask sides round the back of the head
    c = np.array([0.0, 0.106, 0.752])
    strap = []
    for a in np.linspace(math.radians(40), math.radians(320), 46):
        d = np.array([math.sin(a), math.cos(a), 0.0])
        strap.append(c + d * (head_radius(c, d) + 0.0035))
    strap = np.array(strap)
    strap = strap[strap[:, 1] > 0.006]
    add("mask", "O2_Mask_Strap", tube(strap, 0.0032, segments=8), "MAT_Strap")
    return apex + np.array([0, 0.026, 0.050])


# ======================================================================================== oxygen cylinder on trolley
def build_o2(mask_inlet):
    base = np.array([0.46, FLOOR, 1.22])
    g = "o2"
    # trolley
    frame = [tube(np.array([base + [-0.09, 0.03, -0.07], base + [-0.09, 0.95, -0.07]]), 0.012, 12),
             tube(np.array([base + [0.09, 0.03, -0.07], base + [0.09, 0.95, -0.07]]), 0.012, 12),
             tube(np.array([base + [-0.09, 0.95, -0.07], base + [0.09, 0.95, -0.07]]), 0.012, 12),
             tube(np.array([base + [-0.09, 0.04, -0.07], base + [-0.09, 0.04, 0.09], base + [0.09, 0.04, 0.09], base + [0.09, 0.04, -0.07]]), 0.011, 12),
             tube(np.array([base + [-0.09, 0.55, -0.07], base + [-0.09, 0.55, 0.02], base + [0.09, 0.55, 0.02], base + [0.09, 0.55, -0.07]]), 0.008, 10)]
    add(g, "O2_Trolley_Frame", merge(frame), "MAT_Metal")
    wheels = [cylinder(0.06, 0.03, center=base + [sx * 0.115, 0.06, -0.07], R=rot_z(90), segments=28, bevel=0.006) for sx in (-1, 1)]
    add(g, "O2_Trolley_Wheels", merge(wheels), "MAT_EquipDark")
    # cylinder (size-D style portable): black body, white shoulder (Indian Standard / ISO 32 medical O2 colour code)
    cb = base + [0, 0.06, 0.01]
    add(g, "O2_Portable_Body", cylinder(0.062, 0.62, center=cb + [0, 0.31, 0], segments=40, bevel=0.02), "MAT_O2Body")
    add(g, "O2_Portable_Shoulder", lathe_shoulder(cb + [0, 0.62, 0]), "MAT_O2Shoulder")
    add(g, "O2_Portable_Straps", merge([torus(0.066, 0.006, center=cb + [0, h, 0], seg_major=40, seg_minor=8) for h in (0.18, 0.48)]), "MAT_Strap")
    top = cb + [0, 0.72, 0]
    add(g, "O2_Portable_Valve", merge([cylinder(0.018, 0.05, center=top + [0, 0.025, 0], segments=20),
                                       rounded_box((0.05, 0.045, 0.045), 0.008, center=top + [0, 0.07, 0])]), "MAT_Brass")
    add(g, "O2_Portable_Handwheel", torus(0.026, 0.006, center=top + [0, 0.105, 0], seg_major=26, seg_minor=8), "MAT_GreenCap")
    reg = top + [0, 0.07, -0.05]
    add(g, "O2_Regulator_Body", cylinder(0.022, 0.07, center=reg, R=rot_x(90), segments=22, bevel=0.004), "MAT_Metal")
    add(g, "O2_Regulator_Gauge", cylinder(0.032, 0.016, center=reg + [0, 0.045, -0.02], R=rot_x(90), segments=28, bevel=0.003), "MAT_Metal")
    add(g, "O2_Regulator_Gauge_Face", cylinder(0.027, 0.002, center=reg + [0, 0.045, -0.029], R=rot_x(90), segments=28), "MAT_GaugeFace")
    # Thorpe-tube flowmeter + float, humidifier bottle with water
    fm = reg + [0, 0.06, -0.035]
    add(g, "O2_Flowmeter_Tube", cylinder(0.012, 0.11, center=fm + [0, 0.055, 0], segments=18), "MAT_GlassClear")
    add(g, "O2_Flowmeter_Float", sphere(0.0065, center=fm + [0, 0.05, 0]), "MAT_FlowFloat")
    add(g, "O2_Flowmeter_Knob", cylinder(0.012, 0.018, center=fm + [0.02, 0.0, 0], R=rot_z(90), segments=18, bevel=0.003), "MAT_GreenCap")
    hb = reg + [0, -0.12, -0.06]
    add(g, "O2_Humidifier_Bottle", cylinder(0.034, 0.12, center=hb, segments=28, bevel=0.01), "MAT_GlassClear")
    add(g, "O2_Humidifier_Water", cylinder(0.031, 0.07, center=hb - [0, 0.022, 0], segments=28), "MAT_IVLiquid")
    add(g, "O2_Humidifier_Lid", cylinder(0.036, 0.02, center=hb + [0, 0.068, 0], segments=28, bevel=0.004), "MAT_GreenCap")
    add(g, "O2_Flowmeter_Link", tube(np.array([fm + [0, -0.004, 0], fm + [0, -0.03, -0.01], hb + [0, 0.08, 0.0]]), 0.005, 10), "MAT_Metal")
    outlet = hb + [0.0, 0.07, -0.03]
    # tubing: humidifier outlet -> along the head-end pad -> mask elbow
    path = catmull([outlet, outlet + [-0.02, -0.12, -0.08], np.array([0.30, 0.02, 1.02]), np.array([0.16, 0.035, 0.955]),
                    np.array([0.07, 0.15, 0.90]), mask_inlet + [0, 0.004, 0.03], mask_inlet], 12)
    add(g, "O2_Tubing", tube(path, 0.0055, segments=14), "MAT_O2Tube")
    return path


def lathe_shoulder(c):
    # dome from cylinder radius to neck, as stacked rings
    rs = [(0.062, 0.0), (0.058, 0.03), (0.046, 0.06), (0.028, 0.085), (0.018, 0.098), (0.018, 0.10)]
    V, F = [], []
    seg = 40
    for r, h in rs:
        for k in range(seg):
            a = 2 * math.pi * k / seg
            V.append(c + [r * math.cos(a), h, r * math.sin(a)])
    for i in range(len(rs) - 1):
        for k in range(seg):
            a, b = i * seg + k, i * seg + (k + 1) % seg
            F += [[a, a + seg, b], [b, a + seg, b + seg]]
    return mk(V, F)


# ======================================================================================== illustrative airway
AIR_IN = None


def build_airway():
    g = "airway"
    par = "Illustrative_Vessels"
    pharynx = catmull([(0, 0.196, 0.772), (0, 0.17, 0.768), (0, 0.13, 0.752), (0, 0.112, 0.728), (0, 0.118, 0.70)], 8)
    trachea = catmull([(0, 0.118, 0.70), (0, 0.124, 0.64), (0, 0.124, 0.58), (0, 0.120, 0.525)], 8)
    add(g, "Airway_Pharynx", tube(pharynx, 0.0075, segments=14), "MAT_Airway", parent=par)
    add(g, "Airway_Trachea", tube(trachea, 0.0095, segments=16), "MAT_Airway", parent=par)
    rings = [torus(0.0105, 0.0017, center=p, Rm=rotation_between((0, 1, 0), (0, 0, 1)), seg_major=20, seg_minor=6) for p in trachea[2:-1:3]]
    add(g, "Airway_Trachea_Rings", merge(rings), "MAT_Airway", parent=par)
    bronchi = {}
    for s, w in ((1, "Left"), (-1, "Right")):
        b = catmull([(0, 0.120, 0.525), (s * 0.03, 0.118, 0.505), (s * 0.06, 0.113, 0.48), (s * 0.075, 0.11, 0.44)], 8)
        add(g, f"Airway_Bronchus_{w}", tube(b, 0.0068, segments=12), "MAT_Airway", parent=par)
        twigs = []
        for dz, dx in ((0.06, 0.02), (0.0, 0.035), (-0.06, 0.02)):
            tw = catmull([b[-1], b[-1] + [s * dx * 0.6, 0.0, dz * 0.6], b[-1] + [s * dx, -0.004, dz]], 6)
            twigs.append(tube(tw, 0.0035, segments=8))
        add(g, f"Airway_Bronchioles_{w}", merge(twigs), "MAT_Airway", parent=par)
        bronchi[w] = b

    def sdf_lung(Pp, s):
        c = (s * 0.078, 0.112, 0.445)
        d = sd_ellipsoid(Pp, c, (0.062 if s < 0 else 0.056, 0.066, 0.135))
        d = smin(d, sd_ellipsoid(Pp, (s * 0.09, 0.10, 0.37), (0.06, 0.06, 0.06)), 0.03)   # base
        if s > 0:
            d = smax(d, -sd_ellipsoid(Pp, (0.035, 0.14, 0.40), (0.035, 0.05, 0.05)), 0.01)  # cardiac notch
        d = smax(d, -sd_ellipsoid(Pp, (s * 0.02, 0.115, 0.47), (0.022, 0.04, 0.07)), 0.01)   # hilum side
        return d
    for s, w in ((1, "Left"), (-1, "Right")):
        add(g, f"Airway_Lung_{w}", sdf_mesh(lambda Q, s=s: sdf_lung(Q, s), (s * 0.078 - 0.09, 0.03, 0.27), (s * 0.078 + 0.09, 0.2, 0.62), 0.004),
            "MAT_LungGhost", parent=par)
    paths = [np.vstack([pharynx, trachea[1:], bronchi[w][1:]]) for w in ("Left", "Right")]
    return paths


# ======================================================================================== surgeon (detailed, 19 Oct)
def cached(prefix, builder):
    """Mesh parts from a cache directory (NERAM_MESH_CACHE/<prefix>_<name>.npz) when present, else built (slow)."""
    import os
    cache = os.environ.get("NERAM_MESH_CACHE")
    if cache:
        files = sorted(Path(cache).glob(prefix + "_*.npz"))
        if files:
            out = []
            for f in files:
                d = np.load(f)
                out.append((f.stem[len(prefix) + 1:], Mesh(d["V"], d["N"], d["F"]), str(d["mat"])))
            return out
    return builder(print)


def build_surgeon():
    import human as H
    par = "Surgeon_Figure"
    for name, m, mat in cached("sg", H.build_all):
        add("surgeon", name, m, mat, parent=par, binary=True)
    loops = [tube(catmull(pl, 6), 0.0011, 8) for pl in H.mask_loops()]
    add("surgeon", "Surgeon_Mask_Loops", merge(loops), "MAT_MaskLoop", parent=par, binary=True)


def build_instruments():
    import instruments as I
    for name, m, mat in cached("in", I.build_all):
        add("instruments", name, m, mat, binary=True)


def build_patient_hq():
    import patient_hq as PH
    for name, m, mat in cached("pt", PH.build_all):
        add("patient_hq", "HQ_" + name, m, mat, replace=name, binary=True)


SURGEON_POSE = dict(position=[-0.66, FLOOR, 0.05], yaw_deg=90.0)   # patient's right, facing the table (clear of the default camera)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default=None)
    a = ap.parse_args()
    build_head()
    inlet = build_mask()
    tubing = build_o2(inlet)
    lungs = build_airway()
    build_surgeon()
    build_instruments()
    build_patient_hq()
    BIN_PATH.write_bytes(bytes(BIN))
    out = dict(
        version=1, generator="tools/gen_scene_extras.py (Sai, 2026-10-18)",
        note="Visual stand-ins. Mask, oxygen set-up, airway and airflow are ILLUSTRATIVE: no gas flow, oxygen concentration, "
             "respiratory rate or patient anatomy is modelled.",
        materials=[dict(name=n, color=list(c), smoothness=s, metallic=m, transparent=t, emission=list(e) if e else None,
                        normal_map=(TEX + "/" + NORMAL_MAPS[n][0]) if n in NORMAL_MAPS else "",
                        normal_scale=NORMAL_MAPS[n][1] if n in NORMAL_MAPS else 0.0,
                        tiling=NORMAL_MAPS[n][2] if n in NORMAL_MAPS else 0.0)
                   for n, c, s, m, t, e in MATERIALS],
        bin_file="Assets/NERAM_Generated/MeshData/scene_extras_mesh.bytes",
        hide_prefixes=["O2_Cylinder_", "Trolley_Tray_"],          # wall cylinders merged with the cupboards: replaced by the trolley set
        surgeon=SURGEON_POSE,
        # flat point lists (Unity JsonUtility reads no nested arrays): external = humidifier -> mask (always shown),
        # internal = mask -> each lung (Internal view only). Timing is a visual constant, not a respiratory rate.
        airflow=[dict(internal=False, p=np.round(tubing[::-1], 4).ravel().tolist())] +
                [dict(internal=True, p=np.round(q, 4).ravel().tolist()) for q in lungs],
        breath_s=4.2,
        parts=PARTS)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    tri = sum((len(p["f"]) if "f" in p else p["ni"]) // 3 for p in PARTS)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB) + {BIN_PATH.name} ({len(BIN) / 1e6:.1f} MB): {len(PARTS)} parts, {tri} triangles")


if __name__ == "__main__":
    main()
