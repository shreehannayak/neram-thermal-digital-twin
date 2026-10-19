"""Surgical instruments and sterile supplies laid out on the instrument trolley, the supply cart and the back counter
(visual stand-ins, 19 Oct 2026). Every instrument is a signed-distance field meshed at sub-millimetre resolution.

Coordinates returned are NERAM_Assembly-local (table top y = 0). Shapes follow common instruments (scalpel with #22
blade, Metzenbaum scissors, Kelly and mosquito clamps, Mayo-Hegar needle holder, Adson forceps, Army-Navy retractor,
towel clip, kidney dish, gallipot, syringes, gauze, suture packs, sharps container, antiseptic bottle). They are props:
no sterility, count or procedure is implied.
"""
from __future__ import annotations

import math

import numpy as np

from geom import Mesh, frame_from, orient_outward, rot_y, sd_capsule, sd_ellipsoid, sd_round_box, smax, smin
from human import cluster_qem, mesh as hmesh, sd_box

TRAY_Y = 0.0875           # top of the trolley drape


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def sd_torus_flat(P, c, R, r, axis="y"):
    q = P - np.asarray(c, float)
    if axis == "y":
        a, b, h = q[..., 0], q[..., 2], q[..., 1]
    else:
        a, b, h = q[..., 0], q[..., 1], q[..., 2]
    return np.sqrt((np.sqrt(a * a + b * b) - R) ** 2 + h * h) - r


# --------------------------------------------------------------------------------------------- instruments (local)
# local frame: instrument lies flat, long axis +Z (tip at +Z), y up, resting on y = 0
def scalpel(P):
    d = sd_round_box(P, (0, 0.0012, 0.0), (0.0090, 0.0024, 0.130), 0.0010)
    for i in range(8):                                                              # grip ridges
        d = smax(d, -sd_box(P, (0, 0.0024, -0.035 + i * 0.006), (0.006, 0.0006, 0.0011)), 0.0004)
    blade = sd_ellipsoid(P, (0.0015, 0.0010, 0.087), (0.0085, 0.00045, 0.026))
    blade = smax(blade, -(P[..., 0] + 0.002), 0.001)
    return smin(d, blade, 0.0015)


def ring_handles(P, z0, spread=0.0105):
    d = np.full(P.shape[:-1], 1.0)
    for s in (1, -1):
        d = np.minimum(d, sd_torus_flat(P, (s * spread, 0.0022, z0), 0.0095, 0.0019))
    return d


def scissors(P, L=0.145):
    d = ring_handles(P, -0.060)
    for s in (1, -1):
        d = np.minimum(d, sd_capsule(P, (s * 0.0085, 0.0022, -0.050), (s * 0.0010, 0.0022, 0.000), 0.0023, 0.0026))
        # curved blade from the pivot to the tip
        pts = [(0.0, 0.0022 + s * 0.0006, 0.0), (-s * 0.0008, 0.0022 + s * 0.0006, 0.035), (0.003, 0.0022 + s * 0.0006, L - 0.07)]
        for a, b in zip(pts[:-1], pts[1:]):
            d = np.minimum(d, sd_capsule(P, a, b, 0.0030, 0.0012))
    d = np.minimum(d, np.sqrt(P[..., 0] ** 2 + P[..., 2] ** 2 + (P[..., 1] - 0.0022) ** 2 * 0.0) - 0.0035 + np.maximum(np.abs(P[..., 1] - 0.0022) - 0.0022, 0))
    return d


def clamp(P, L=0.14, jaw=0.035, curved=False):
    d = ring_handles(P, -L * 0.40)
    for s in (1, -1):
        d = np.minimum(d, sd_capsule(P, (s * 0.0085, 0.0022, -L * 0.36), (s * 0.0012, 0.0022, 0.0), 0.0021, 0.0025))
        # ratchet teeth near the rings
        d = np.minimum(d, sd_box(P, (s * 0.0055, 0.0022, -L * 0.30), (0.0030, 0.0016, 0.0050)))
    tip = (0.004 if curved else 0.0, 0.0022, jaw)
    d = np.minimum(d, sd_capsule(P, (0, 0.0022, 0), tip, 0.0034, 0.0014))
    for i in range(10):                                                              # serrations
        d = smax(d, -sd_box(P, (0, 0.0046, 0.004 + i * jaw / 11), (0.004, 0.0006, 0.0005)), 0.0003)
    d = np.minimum(d, np.sqrt(P[..., 0] ** 2 + P[..., 2] ** 2) - 0.0040 + np.maximum(np.abs(P[..., 1] - 0.0022) - 0.0026, 0))
    return d


def forceps(P, L=0.125):
    d = np.full(P.shape[:-1], 1.0)
    for s in (1, -1):
        a = (s * 0.0040, 0.0025, -L * 0.5)
        b = (s * 0.0012, 0.0016, L * 0.5)
        d = np.minimum(d, sd_capsule(P, a, b, 0.0034, 0.0011))
        for i in range(9):                                                           # grip grooves
            d = smax(d, -sd_box(P, (s * (0.0038 - i * 0.0001), 0.0058, -0.02 + i * 0.004), (0.004, 0.0008, 0.0006)), 0.0003)
    d = np.minimum(d, sd_round_box(P, (0, 0.0025, -L * 0.5 + 0.004), (0.012, 0.005, 0.010), 0.002))
    return d


def retractor(P):
    d = sd_round_box(P, (0, 0.0015, 0.0), (0.014, 0.003, 0.160), 0.0012)
    for z, h in ((0.080, 0.028), (-0.080, 0.020)):
        s = 1 if z > 0 else -1
        d = smin(d, sd_round_box(P, (0, h / 2, z + s * 0.0015), (0.016 if z > 0 else 0.012, h, 0.003), 0.0012), 0.003)
    return d


def towel_clip(P):
    d = ring_handles(P, -0.045, 0.0095)
    for s in (1, -1):
        d = np.minimum(d, sd_capsule(P, (s * 0.008, 0.0022, -0.036), (-s * 0.006, 0.0022, 0.020), 0.0018, 0.0016))
        d = np.minimum(d, sd_capsule(P, (-s * 0.006, 0.0022, 0.020), (s * 0.001, 0.0022, 0.030), 0.0016, 0.0007))
    return d


def needle_holder(P):
    return clamp(P, L=0.16, jaw=0.022)


# --------------------------------------------------------------------------------------------- bowls, trays, supplies
def kidney_dish(P):
    # bean outline in xz: two arcs; shell 1.2 mm, height 0.035
    q = P
    outer = sd_ellipsoid(q, (0, 0.047, 0), (0.125, 0.046, 0.060))   # bottom just above the tray (not clipped open)
    notch = sd_ellipsoid(q, (0, 0.040, 0.085), (0.060, 0.08, 0.050))
    shape = smax(outer, -notch, 0.02)
    shell = smax(shape, -(shape + 0.0030), 0.0004)   # 3 mm wall so it meshes without holes
    shell = np.maximum(shell, q[..., 1] - 0.040)
    rim = smax(np.abs(shape + 0.0012) - 0.0030, np.abs(q[..., 1] - 0.0395) - 0.0022, 0.0006)
    return np.maximum(np.minimum(shell, rim), -q[..., 1])


def gallipot(P, r=0.040, h=0.035):
    rr = np.sqrt(P[..., 0] ** 2 + P[..., 2] ** 2)
    body = np.maximum(rr - (r - 0.006 + 0.006 * P[..., 1] / h), np.maximum(-P[..., 1], P[..., 1] - h))
    inner = np.maximum(rr - (r - 0.0090 + 0.006 * P[..., 1] / h), np.maximum(0.0035 - P[..., 1], P[..., 1] - h - 0.01))
    d = smax(body, -inner, 0.0005)
    lip = np.sqrt((rr - r + 0.0015) ** 2 + (P[..., 1] - h) ** 2) - 0.0024
    return np.minimum(d, lip)


def tray(P, w=0.32, l=0.22, h=0.024):
    outer = sd_round_box(P, (0, h / 2, 0), (w, h, l), 0.010)
    inner = sd_round_box(P, (0, h / 2 + 0.0050, 0), (w - 0.0080, h, l - 0.0080), 0.008)   # 4 mm walls, 5 mm floor
    d = smax(outer, -inner, 0.0005)
    qx = np.abs(P[..., 0]) - (w / 2 - 0.001 - 0.010)
    qz = np.abs(P[..., 2]) - (l / 2 - 0.001 - 0.010)
    outline = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qz, 0) ** 2) + np.minimum(np.maximum(qx, qz), 0) - 0.010   # 2-D rounded rectangle
    rim = smax(np.abs(outline) - 0.0030, np.abs(P[..., 1] - h) - 0.0024, 0.0005)     # rolled rim on the wall top only
    return np.minimum(d, rim)


def towel(P, w=0.46, l=0.34):
    wave = 0.0012 * np.sin(P[..., 0] * 70 + np.sin(P[..., 2] * 40)) * np.sin(P[..., 2] * 55)
    Q = P.copy()
    Q[..., 1] = Q[..., 1] - wave                      # displace the cloth instead of thinning it (no holes)
    return sd_round_box(Q, (0, 0.0024, 0), (w, 0.0040, l), 0.0018)


def syringe(P, L=0.090, r=0.0082):
    rr = np.sqrt(P[..., 0] ** 2 + (P[..., 1] - r) ** 2)
    barrel = np.maximum(rr - r, np.abs(P[..., 2]) - L / 2)
    barrel = smax(barrel, -np.maximum(rr - (r - 0.0016), np.abs(P[..., 2]) - (L / 2 - 0.0012)), 0.0003)
    flange = sd_round_box(P, (0, r, -L / 2), (0.036, 0.016, 0.0022), 0.002)
    tip = np.maximum(rr - 0.0022, np.abs(P[..., 2] - (L / 2 + 0.006)) - 0.006)
    return np.minimum(np.minimum(barrel, flange), tip)


def plunger(P, L=0.090, r=0.0082):
    rr = np.sqrt(P[..., 0] ** 2 + (P[..., 1] - r) ** 2)
    rod = np.maximum(np.maximum(np.abs(P[..., 0]) - 0.0013, np.abs(P[..., 1] - r) - (r - 0.0022)), np.abs(P[..., 2] + 0.006) - L / 2)
    rod = np.minimum(rod, np.maximum(np.maximum(np.abs(P[..., 0]) - (r - 0.0022), np.abs(P[..., 1] - r) - 0.0013), np.abs(P[..., 2] + 0.006) - L / 2))
    seal = np.maximum(rr - (r - 0.0010), np.abs(P[..., 2] - (L * 0.06)) - 0.004)
    thumb = np.maximum(rr - 0.0105, np.abs(P[..., 2] + L / 2 + 0.018) - 0.0014)
    return np.minimum(np.minimum(rod, seal), thumb)


def gauze_stack(P, n=5):
    d = np.full(P.shape[:-1], 1.0)
    for i in range(n):
        off = (0.002 * math.sin(i * 1.7), 0.0, 0.002 * math.cos(i * 2.3))
        d = np.minimum(d, sd_round_box(P, (off[0], 0.003 + i * 0.0052, off[2]), (0.100, 0.0050, 0.100), 0.0022)
                       + 0.0004 * np.sin(P[..., 0] * 400) * np.sin(P[..., 2] * 400))
    return d


def suture_pack(P):
    return sd_round_box(P, (0, 0.0012, 0), (0.060, 0.0024, 0.135), 0.0008)


def sharps_box(P):
    d = sd_round_box(P, (0, 0.095, 0), (0.17, 0.19, 0.12), 0.012)
    d = smin(d, sd_round_box(P, (0, 0.197, 0), (0.18, 0.016, 0.13), 0.006), 0.003)
    d = smax(d, -sd_round_box(P, (0, 0.205, 0.015), (0.10, 0.02, 0.035), 0.008), 0.002)
    return d


def bottle(P, r=0.030, h=0.12):
    rr = np.sqrt(P[..., 0] ** 2 + P[..., 2] ** 2)
    body = np.maximum(rr - r, np.maximum(-P[..., 1], P[..., 1] - h))
    body = smin(body, np.maximum(rr - 0.012, np.maximum(-P[..., 1], P[..., 1] - h - 0.025)), 0.012)
    return body


def bottle_cap(P, h=0.12):
    rr = np.sqrt(P[..., 0] ** 2 + P[..., 2] ** 2)
    return np.maximum(rr - 0.0135, np.abs(P[..., 1] - (h + 0.030)) - 0.009) - 0.0004 * np.sin(np.arctan2(P[..., 2], P[..., 0]) * 40)


def specimen_pot(P):
    return gallipot(P, r=0.028, h=0.055)


# --------------------------------------------------------------------------------------------- placement
def place(fn, pos, yaw_deg=0.0, scale=1.0):
    R = rot_y(yaw_deg)
    c = np.asarray(pos, float)

    def g(P):
        q = ((P - c) @ R) / scale
        return fn(q) * scale
    return g


def bbox(local_lo, local_hi, pos, yaw, scale=1.0):
    lo, hi = np.asarray(local_lo, float) * scale, np.asarray(local_hi, float) * scale
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    W = corners @ rot_y(yaw).T + np.asarray(pos, float)
    return W.min(0) - 0.002, W.max(0) + 0.002


def build_all(log=print):
    """Returns [(name, Mesh, material, uv_scale)] in NERAM_Assembly coordinates."""
    out = []
    y = TRAY_Y

    def add(name, fn, lo, hi, pos, yaw, mat, voxel=0.00045, cell=0.0009, smooth=2, scale=1.0, target=-1):
        lo_w, hi_w = bbox(lo, hi, pos, yaw, scale)
        if target == -1:
            target = 30000 if ("Tray" in name or "Towel" in name) else 14000 if ("Gauze" in name or "Sharps" in name) else 9000
        elif target == 0:
            target = None      # thin steel shells: fixed fine cell (no coarsening loop, which opens holes in the walls)
        m = hmesh(place(fn, pos, yaw, scale), lo_w, hi_w, voxel, smooth, cell=cell, target=target)
        out.append((name, m, mat))
        log(f"  {name}: {len(m.F)} tris")

    # instrument trolley (drape top x 0.75..1.75, z -1.77..-0.93): towel, two trays with instruments, bowls
    add("Instr_Towel", towel, (-0.24, -0.002, -0.18), (0.24, 0.006, 0.18), (1.25, y, -1.33), 0.0, "MAT_SterileTowel",
        voxel=0.0012, cell=0.0030, smooth=2, target=0)
    ty = y + 0.003
    add("Instr_Tray_Main", tray, (-0.17, 0.0012, -0.12), (0.17, 0.03, 0.12), (1.07, ty, -1.40), 0.0, "MAT_Steel",
        voxel=0.0012, cell=0.0032, target=0)
    add("Instr_Tray_Small", lambda P: tray(P, 0.22, 0.15, 0.020), (-0.12, 0.0012, -0.08), (0.12, 0.025, 0.08), (1.42, ty, -1.52), 0.0,
        "MAT_Steel", voxel=0.0012, cell=0.0032, target=0)
    iy = ty + 0.0055                      # on the 5 mm tray floor
    lay = [  # name, fn, local lo/hi, x, z, yaw
        ("Instr_Scalpel", scalpel, (-0.006, -0.001, -0.068), (0.012, 0.006, 0.115)),
        ("Instr_Scissors_Metzenbaum", scissors, (-0.024, -0.001, -0.074), (0.024, 0.008, 0.080)),
        ("Instr_Clamp_Kelly_1", clamp, (-0.024, -0.001, -0.070), (0.024, 0.008, 0.040)),
        ("Instr_Clamp_Kelly_2", clamp, (-0.024, -0.001, -0.070), (0.024, 0.008, 0.040)),
        ("Instr_Clamp_Mosquito", lambda P: clamp(P, 0.12, 0.028, curved=True), (-0.024, -0.001, -0.060), (0.024, 0.008, 0.034)),
        ("Instr_Needle_Holder", needle_holder, (-0.024, -0.001, -0.080), (0.024, 0.008, 0.026)),
        ("Instr_Forceps_Adson", forceps, (-0.012, -0.001, -0.066), (0.012, 0.009, 0.066)),
        ("Instr_Towel_Clip", towel_clip, (-0.022, -0.001, -0.058), (0.022, 0.008, 0.034)),
    ]
    xs = np.linspace(0.935, 1.205, len(lay))
    for (name, fn, lo, hi), x in zip(lay, xs):
        add(name, fn, lo, hi, (x, iy, -1.40 + (-0.014 if "Scalpel" in name else 0.0)), 0.0, "MAT_Instrument")
    add("Instr_Retractor_ArmyNavy", retractor, (-0.012, -0.001, -0.086), (0.012, 0.030, 0.086), (1.42, iy, -1.52), 90.0, "MAT_Instrument",
        voxel=0.0006, cell=0.0012)
    add("Instr_Kidney_Dish", kidney_dish, (-0.128, -0.006, -0.064), (0.128, 0.046, 0.064), (1.52, y, -1.18), -15.0, "MAT_Steel",
        voxel=0.0009, cell=0.0024, target=0)
    add("Instr_Gallipot_1", gallipot, (-0.044, 0.0010, -0.044), (0.044, 0.040, 0.044), (1.18, y, -1.12), 0.0, "MAT_Steel",
        voxel=0.0008, cell=0.0022, target=0)
    add("Instr_Gallipot_2", gallipot, (-0.044, 0.0010, -0.044), (0.044, 0.040, 0.044), (1.29, y, -1.10), 0.0, "MAT_Steel",
        voxel=0.0008, cell=0.0022, target=0)
    add("Instr_Gauze", gauze_stack, (-0.055, -0.001, -0.055), (0.055, 0.032, 0.055), (0.98, y, -1.12), 12.0, "MAT_Gauze",
        voxel=0.0010, cell=0.0020, smooth=1)
    for i, (x, z, yaw) in enumerate(((1.62, -1.43, 80.0), (1.62, -1.33, 84.0))):
        add(f"Instr_Syringe_{i + 1}", syringe, (-0.020, -0.001, -0.050), (0.020, 0.018, 0.058), (x, y, z), yaw, "MAT_SyringeClear",
            voxel=0.0004, cell=0.0008, target=0)
        add(f"Instr_Plunger_{i + 1}", plunger, (-0.012, -0.001, -0.072), (0.012, 0.018, 0.010), (x, y, z), yaw, "MAT_SyringePlunger",
            voxel=0.0005, cell=0.0010)
    for i, (x, z, yaw) in enumerate(((1.60, -1.62, 8.0), (1.66, -1.60, 14.0), (1.56, -1.66, -4.0))):
        add(f"Instr_Suture_Pack_{i + 1}", suture_pack, (-0.032, -0.001, -0.070), (0.032, 0.004, 0.070), (x, y + 0.0004 * i, z), yaw,
            "MAT_SuturePack" if i != 1 else "MAT_SuturePack2", voxel=0.0010, cell=0.0020, smooth=1)

    # supply cart top (x 2.48..3.02, z -0.13..0.53, top y 0.213)
    sy = 0.2135
    add("Supply_Sharps_Box", sharps_box, (-0.09, -0.001, -0.065), (0.09, 0.215, 0.065), (2.82, sy, 0.38), 90.0, "MAT_SharpsYellow",
        voxel=0.0018, cell=0.0036)
    add("Supply_Antiseptic_Bottle", bottle, (-0.032, -0.001, -0.032), (0.032, 0.150, 0.032), (2.62, sy, 0.02), 0.0, "MAT_BottleAmber",
        voxel=0.0010, cell=0.0020)
    add("Supply_Antiseptic_Cap", bottle_cap, (-0.016, 0.115, -0.016), (0.016, 0.165, 0.016), (2.62, sy, 0.02), 0.0, "MAT_BottleCap",
        voxel=0.0006, cell=0.0012)
    add("Supply_Gauze", gauze_stack, (-0.055, -0.001, -0.055), (0.055, 0.032, 0.055), (2.74, sy, 0.05), -8.0, "MAT_Gauze",
        voxel=0.0010, cell=0.0020, smooth=1)
    add("Supply_Kidney_Dish", kidney_dish, (-0.128, -0.006, -0.064), (0.128, 0.046, 0.064), (2.73, sy, 0.20), 90.0, "MAT_Steel",
        voxel=0.0009, cell=0.0024, target=0)

    # back counter (cabinet tops at y 0.03, x 1.05..2.65, z 2.78..3.32)
    cy = 0.030
    for i, x in enumerate((1.25, 1.36, 1.47)):
        add(f"Counter_Specimen_Pot_{i + 1}", specimen_pot, (-0.032, -0.001, -0.032), (0.032, 0.060, 0.032), (x, cy, 2.95), 0.0,
            "MAT_SpecimenPot", voxel=0.0008, cell=0.0022, target=0)
    add("Counter_Glove_Box", lambda P: sd_round_box(P, (0, 0.045, 0), (0.25, 0.09, 0.125), 0.004), (-0.13, -0.001, -0.07),
        (0.13, 0.095, 0.07), (1.95, cy, 3.02), 0.0, "MAT_GloveBox", voxel=0.0020, cell=0.0040, smooth=1)
    add("Counter_Tray", tray, (-0.17, 0.0012, -0.12), (0.17, 0.03, 0.12), (2.35, cy, 3.05), 6.0, "MAT_Steel", voxel=0.0012, cell=0.0032,
        target=0)
    return out
