"""Detailed standing surgeon figure (visual stand-in) for the NERAM viewer, rebuilt 19 Oct 2026.

Local frame: metres, floor y = 0, the figure faces +Z, its left = +X, stature about 1.78 m. Pose: standing at the
table, elbows bent, gloved hands forward at table height. Every part is a signed-distance field meshed with marching
cubes at a part-specific resolution; normals come from the SDF gradient, so shading is smooth without decimation.

Parts: skin (head, neck, V-neck, forearms), eyes (sclera, iris, pupil), eyebrows, bouffant cap with elastic band,
pleated surgical mask with ear loops, scrub top (V-neck, chest pocket, sleeve bands, side vents), scrub trousers
(drawstring waist, knee folds), gloves with five-finger hands and rolled cuffs, clogs with vent holes, ID badge.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import sparse

from geom import (Mesh, frame_from, orient_outward, sd_capsule, sd_ellipsoid, sd_round_box, sdf_mesh, smax, smin)

S2 = (1, -1)   # +1 = figure's left (+X), -1 = right


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# --------------------------------------------------------------------------------------------- skeleton / pose
SH = {s: np.array([s * 0.188, 1.448, -0.012]) for s in S2}     # shoulder joints
EL = {s: np.array([s * 0.215, 1.175, 0.035]) for s in S2}      # elbows (arms hang, slightly forward)
WR = {s: np.array([s * 0.135, 1.085, 0.285]) for s in S2}      # wrists (forearms forward, hands over the table)
HP = {s: np.array([s * 0.092, 0.935, 0.0]) for s in S2}        # hip joints
KN = {s: np.array([s * 0.100, 0.505, 0.018]) for s in S2}      # knees
AN = {s: np.array([s * 0.104, 0.085, -0.005]) for s in S2}     # ankles
HEAD_C = np.array([0.0, 1.668, 0.004])                          # centre of the cranium


# --------------------------------------------------------------------------------------------- small SDF helpers
def sd_torus_y(P, c, R, r):
    q = P - np.asarray(c, float)
    xz = np.sqrt(q[..., 0] ** 2 + q[..., 2] ** 2) - R
    return np.sqrt(xz ** 2 + q[..., 1] ** 2) - r


def sd_box(P, c, h):
    q = np.abs(P - np.asarray(c, float)) - np.asarray(h, float)
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(np.max(q, axis=-1), 0)


def noise3(P, f, seed=0.0):
    """Cheap smooth pseudo-noise (sum of sines) for cloth wrinkles."""
    x, y, z = P[..., 0] * f, P[..., 1] * f, P[..., 2] * f
    return (np.sin(x * 1.7 + y * 0.9 + seed) * np.sin(z * 1.3 - y * 1.1 + 2.1 * seed)
            + 0.5 * np.sin(x * 3.1 - z * 2.3 + y * 1.7 + seed * 3.0)) / 1.5


# --------------------------------------------------------------------------------------------- head and face
EYE = {s: np.array([s * 0.0315, 1.672, 0.0815]) for s in S2}   # eyeball centres
EYE_R = 0.0118


def sdf_head(P):
    c = HEAD_C
    d = sd_ellipsoid(P, c + (0, 0.012, -0.006), (0.0735, 0.097, 0.0955))                       # cranium
    d = smin(d, sd_ellipsoid(P, c + (0, 0.035, 0.035), (0.066, 0.062, 0.066)), 0.03)            # forehead dome
    d = smin(d, sd_ellipsoid(P, c + (0, -0.052, 0.040), (0.056, 0.060, 0.058)), 0.035)          # maxilla / mid-face
    d = smin(d, sd_ellipsoid(P, c + (0, -0.083, 0.050), (0.047, 0.038, 0.046)), 0.03)           # jaw body
    d = smin(d, sd_ellipsoid(P, c + (0, -0.100, 0.078), (0.021, 0.017, 0.016)), 0.018)          # chin
    d = smin(d, sd_ellipsoid(P, c + (0, 0.020, 0.073), (0.058, 0.014, 0.020)), 0.016)           # brow ridge
    for s in S2:
        d = smin(d, sd_ellipsoid(P, c + (s * 0.047, -0.022, 0.055), (0.022, 0.017, 0.020)), 0.02)   # cheekbone
        d = smin(d, sd_ellipsoid(P, c + (s * 0.050, -0.072, 0.012), (0.017, 0.036, 0.030)), 0.022)  # jaw angle
        d = smin(d, sd_ellipsoid(P, c + (s * 0.060, -0.008, 0.035), (0.012, 0.020, 0.022)), 0.015)  # temple fill
        # eye socket: carve, the eyeball is a separate mesh
        d = smax(d, -sd_ellipsoid(P, EYE[s] + (0, -0.0006, 0.011), (0.0152, 0.0080, 0.0125)), 0.0040)
        d = smin(d, sd_ellipsoid(P, EYE[s] + (0, 0.0062, 0.0058), (0.0150, 0.0052, 0.0094)), 0.0030)  # upper lid
        d = smin(d, sd_ellipsoid(P, EYE[s] + (0, -0.0088, 0.0050), (0.0138, 0.0038, 0.0078)), 0.0030)  # lower lid
    # nose: bridge, dorsum, tip, alae, columella
    nose = sd_capsule(P, c + (0, 0.004, 0.082), c + (0, -0.036, 0.106), 0.0072, 0.0100)
    nose = smin(nose, sd_ellipsoid(P, c + (0, -0.040, 0.106), (0.0115, 0.0098, 0.0105)), 0.006)
    for s in S2:
        nose = smin(nose, sd_ellipsoid(P, c + (s * 0.0125, -0.043, 0.094), (0.0085, 0.0075, 0.0085)), 0.005)
        nose = smax(nose, -sd_ellipsoid(P, c + (s * 0.0062, -0.0495, 0.098), (0.0038, 0.0022, 0.0045)), 0.002)
    d = smin(d, nose, 0.008)
    # lips and philtrum (under the mask, kept for the silhouette)
    d = smin(d, sd_ellipsoid(P, c + (0, -0.064, 0.0865), (0.021, 0.0055, 0.0075)), 0.006)
    d = smin(d, sd_ellipsoid(P, c + (0, -0.074, 0.0840), (0.018, 0.0060, 0.0070)), 0.006)
    # ears: helix rim, concha, lobe
    for s in S2:
        ec = c + (s * 0.0755, -0.012, -0.004)
        ear = sd_ellipsoid(P, ec, (0.0095, 0.031, 0.020))
        q = P - ec
        rim = np.sqrt((q[..., 1] / 1.45) ** 2 + q[..., 2] ** 2) - 0.0172
        rim = np.sqrt(rim ** 2 + (q[..., 0] - s * 0.004) ** 2) - 0.0034
        ear = smin(ear, rim, 0.003)
        ear = smax(ear, -sd_ellipsoid(P, ec + (s * 0.007, -0.002, 0.002), (0.005, 0.012, 0.009)), 0.003)   # concha
        ear = smin(ear, sd_ellipsoid(P, ec + (s * 0.001, -0.031, 0.003), (0.0055, 0.0085, 0.0075)), 0.004)  # lobe
        d = smin(d, ear, 0.006)
    return d


def sdf_neck(P):
    d = sd_capsule(P, (0, 1.445, -0.012), (0, 1.585, 0.004), 0.058, 0.051)
    d = smin(d, sd_ellipsoid(P, (0, 1.468, -0.030), (0.150, 0.045, 0.070)), 0.04)                # trapezius
    for s in S2:   # sternocleidomastoid
        d = smin(d, sd_capsule(P, (s * 0.040, 1.590, -0.020), (s * 0.018, 1.475, 0.040), 0.013, 0.012), 0.012)
    return d


# --------------------------------------------------------------------------------------------- torso, limbs
def sdf_torso(P, delt=1.0):
    d = sd_ellipsoid(P, (0, 1.300, -0.005), (0.170, 0.165, 0.108))                              # rib cage
    d = smin(d, sd_ellipsoid(P, (0, 1.105, 0.008), (0.150, 0.140, 0.104)), 0.07)                # abdomen
    d = smin(d, sd_ellipsoid(P, (0, 0.960, -0.004), (0.172, 0.115, 0.108)), 0.07)               # pelvis
    d = smin(d, sd_ellipsoid(P, (0, 0.905, -0.055), (0.150, 0.090, 0.080)), 0.05)               # gluteal
    for s in S2:
        d = smin(d, sd_ellipsoid(P, (s * 0.074, 1.335, 0.062), (0.078, 0.060, 0.045)), 0.04)    # pectoral
        d = smin(d, sd_ellipsoid(P, SH[s] + (s * 0.006, 0.000, 0.0), (0.052 * delt, 0.056 * delt, 0.058 * delt)), 0.045)  # deltoid cap
        d = smin(d, sd_ellipsoid(P, (s * 0.105, 1.300, -0.060), (0.070, 0.120, 0.050)), 0.05)   # latissimus
    return d


def sdf_arm(P, s, upper=True, lower=True):
    S, E, W = SH[s], EL[s], WR[s]
    d = np.full(P.shape[:-1], 1.0)
    if upper:
        d = sd_capsule(P, S, E, 0.047, 0.037)
        d = smin(d, sd_ellipsoid(P, S + (E - S) * 0.42 + (0, 0, 0.012), (0.045, 0.085, 0.042)), 0.03)  # biceps/triceps
    if lower:
        f = sd_capsule(P, E, W, 0.039, 0.026)
        f = smin(f, sd_ellipsoid(P, E + (W - E) * 0.28, (0.040, 0.040, 0.060), frame_from(W - E)), 0.03)  # forearm bulk
        d = f if not upper else smin(d, f, 0.025)
    return d


def sdf_leg(P, s):
    H, K, A = HP[s], KN[s], AN[s]
    d = sd_capsule(P, H, K, 0.086, 0.055)
    d = smin(d, sd_ellipsoid(P, H + (K - H) * 0.33 + (0, 0, 0.006), (0.082, 0.17, 0.080)), 0.05)   # thigh
    d = smin(d, sd_capsule(P, K, A, 0.050, 0.033), 0.03)
    d = smin(d, sd_ellipsoid(P, K + (A - K) * 0.28 + (0, 0, -0.018), (0.050, 0.11, 0.052)), 0.04)   # calf
    return d


def sdf_body(P):
    d = smin(sdf_torso(P), sdf_neck(P), 0.04)
    for s in S2:
        d = smin(d, sdf_arm(P, s), 0.04)
        d = smin(d, sdf_leg(P, s), 0.05)
    return d


# --------------------------------------------------------------------------------------------- hands
def hand_frame(s):
    """x = across the palm toward the thumb, y = palm normal (back of hand up), z = toward the fingertips."""
    z = unit(WR[s] - EL[s])
    z = unit(z + np.array([0, -0.10, 0]))
    up = np.array([0.0, 1.0, 0.0])
    x = unit(np.cross(up, z)) * (-s)          # thumb points inward (toward the figure's midline)
    y = unit(np.cross(z, x)) * (-s)
    if y[1] < 0:
        y = -y
    return np.stack([x, y, z], 1)


FINGERS = [  # (offset across palm, length proximal/middle/distal, radius, curl deg per joint)
    (0.026, (0.046, 0.028, 0.022), 0.0092, (14, 22, 16)),   # index
    (0.009, (0.050, 0.031, 0.024), 0.0095, (16, 24, 16)),   # middle
    (-0.008, (0.047, 0.029, 0.023), 0.0090, (18, 26, 18)),  # ring
    (-0.024, (0.038, 0.022, 0.020), 0.0080, (22, 28, 20)),  # little
]


def sdf_hand(P, s, glove=0.0):
    R = hand_frame(s)
    W = WR[s]
    q = (P - W) @ R                                                     # hand-local coordinates
    d = sd_round_box(q, (0.0, 0.0, 0.046), (0.074, 0.026, 0.080), 0.013)  # palm (full sizes)
    d = smin(d, sd_capsule(q, (0, 0, -0.03), (0, 0, 0.01), 0.030, 0.031), 0.02)                       # wrist
    d = smin(d, sd_ellipsoid(q, (0.026, -0.006, 0.030), (0.020, 0.016, 0.030)), 0.012)                 # thenar
    for off, L, r, curl in FINGERS:
        base = np.array([off, 0.002, 0.084 - abs(off) * 0.28])
        p0 = base
        ang = 0.0
        rr = r
        spread = math.radians(off * 120)
        for k in range(3):
            ang += math.radians(curl[k])
            dirv = np.array([math.sin(spread), -math.sin(ang), math.cos(ang) * math.cos(spread)])
            p1 = p0 + dirv * L[k]
            d = smin(d, sd_capsule(q, p0, p1, rr, rr * 0.92), 0.006 if k else 0.010)
            d = smin(d, sd_ellipsoid(q, p0 + (0, 0.0012, 0), (rr * 1.03, rr * 0.95, rr * 1.1)), 0.006)    # knuckle
            p0, rr = p1, rr * 0.9
        if glove == 0.0:   # fingernail pad (skin version only)
            pass
    # thumb: metacarpal + two phalanges, pointing forward/inward under the index finger
    t0 = np.array([0.034, -0.010, 0.020])
    dirs = [unit((0.45, -0.25, 0.85)), unit((0.25, -0.35, 0.90)), unit((0.10, -0.42, 0.90))]
    lens = (0.040, 0.032, 0.026)
    rr = 0.0115
    for k in range(3):
        t1 = t0 + dirs[k] * lens[k]
        d = smin(d, sd_capsule(q, t0, t1, rr, rr * 0.9), 0.008 if k == 0 else 0.004)
        t0, rr = t1, rr * 0.9
    return d - glove


def sdf_gloves(P):
    d = np.full(P.shape[:-1], 1.0)
    for s in S2:
        g = sdf_hand(P, s, glove=0.0009)
        # cuff: up the forearm by 7 cm, slightly loose, with a rolled rim
        R = hand_frame(s)
        q = (P - WR[s]) @ R
        cuff = sd_capsule(q, (0, 0, -0.075), (0, 0, 0.002), 0.0315, 0.0315)
        cuff = smax(cuff, -(q[..., 2] + 0.074), 0.002)
        rim = np.sqrt((np.sqrt(q[..., 0] ** 2 + q[..., 1] ** 2) - 0.031) ** 2 + (q[..., 2] + 0.074) ** 2) - 0.0028
        g = smin(g, smin(cuff, rim, 0.002), 0.01)
        d = np.minimum(d, g)
    return d


# --------------------------------------------------------------------------------------------- skin visible parts
def sdf_skin_head(P):
    d = smin(sdf_head(P), sdf_neck(P), 0.02)
    return smin(d, sd_ellipsoid(P, (0, 1.41, 0.045), (0.11, 0.06, 0.05)), 0.03)                 # upper chest in the V


def sdf_skin_arms(P):
    d = np.full(P.shape[:-1], 1.0)
    for s in S2:
        d = np.minimum(d, sdf_arm(P, s))
    return d


# --------------------------------------------------------------------------------------------- clothing
def sdf_scrub_top(P):
    body = smin(sdf_torso(P, 0.90), sd_ellipsoid(P, (0, 1.462, -0.028), (0.150, 0.048, 0.074)), 0.04)   # covers the trapezius
    for s in S2:   # short sleeves: upper-arm capsule, cut square at mid upper arm (only the sleeve is cut)
        S, E = SH[s], EL[s]
        ax = unit(E - S)
        sl = sd_capsule(P, S + ax * 0.03, S + (E - S) * 0.58, 0.052, 0.055)   # widens towards the hem: covers the biceps
        sl = smax(sl, (P - (S + (E - S) * 0.50)) @ ax, 0.004)
        body = smin(body, sl, 0.018)
    wr = 0.0016 * noise3(P, 20.0, 1.0) + 0.0005 * noise3(P, 70.0, 2.0)
    drape = np.clip((1.20 - P[..., 1]) * 4.0, 0, 1) * 0.010                                    # loose below the chest
    d = body - 0.008 - drape + wr
    d = smax(d, -sd_capsule(P, (0, 1.55, 0.13), (0, 1.36, 0.115), 0.060, 0.012), 0.006)        # V-neck
    d = smax(d, -sd_capsule(P, (0, 1.475, -0.010), (0, 1.70, 0.006), 0.066, 0.066), 0.008)      # neck opening (closed at the back)
    d = np.maximum(d, 0.840 - P[..., 1])                                                         # hem (untucked)
    for s in S2:
        # side vents at the hem
        d = smax(d, -sd_box(P, (s * 0.168, 0.86, 0.0), (0.012, 0.045, 0.009)), 0.004)
    return d


def sdf_top_details(P):
    """Sleeve bands, V-neck binding and a chest pocket (separate mesh, darker trim)."""
    d = np.full(P.shape[:-1], 1.0)
    for s in S2:
        S, E = SH[s], EL[s]
        ax = unit(E - S)
        c = S + (E - S) * 0.475
        q = P - c
        t = q @ ax
        rad = np.linalg.norm(q - t[..., None] * ax, axis=-1)
        band = np.maximum(np.abs(rad - 0.0640) - 0.0028, np.abs(t + 0.008) - 0.011)
        d = np.minimum(d, band)
    # V-neck binding: thin tube along the V edge
    d = np.minimum(d, sd_round_box(P, (0.088, 1.285, 0.122), (0.090, 0.095, 0.006), 0.002))    # chest pocket
    return d


def sdf_trousers(P):
    d = sd_ellipsoid(P, (0, 0.97, -0.004), (0.180, 0.125, 0.118))
    for s in S2:
        H, K, A = HP[s], KN[s], AN[s]
        leg = sd_capsule(P, H, K + (0, 0, 0.004), 0.096, 0.072)
        leg = smin(leg, sd_capsule(P, K, A + (0, 0.035, 0), 0.072, 0.064), 0.03)
        d = smin(d, leg, 0.05)
    t = np.clip((0.70 - P[..., 1]) * 2.4, 0, 1)
    wr = 0.0032 * noise3(P, 30.0, 4.0) + 0.0020 * np.sin(P[..., 1] * 140.0) * t * np.clip(1 - np.abs(P[..., 1] - 0.20) * 6, 0, 1)
    d = d + wr
    d = np.maximum(d, P[..., 1] - 1.035)                     # waistband top
    d = np.maximum(d, 0.105 - P[..., 1])                     # hem above the clogs
    return d


def sdf_waistband(P):
    q = P - np.array([0, 1.020, -0.004])
    r = np.sqrt((q[..., 0] / 0.183) ** 2 + (q[..., 2] / 0.121) ** 2)
    band = np.maximum(np.abs(r - 1.0) * 0.12 - 0.0025, np.abs(q[..., 1]) - 0.014)
    tie = sd_capsule(P, (-0.012, 1.012, 0.118), (-0.020, 0.93, 0.125), 0.003, 0.003)
    tie = np.minimum(tie, sd_capsule(P, (0.012, 1.012, 0.118), (0.024, 0.94, 0.124), 0.003, 0.003))
    return np.minimum(band, tie)


def sdf_cap(P):
    c = HEAD_C
    skull = smin(sd_ellipsoid(P, c + (0, 0.012, -0.006), (0.0735, 0.097, 0.0955)),
                 sd_ellipsoid(P, c + (0, 0.035, 0.035), (0.066, 0.062, 0.066)), 0.03)
    shell = smin(skull - 0.009, sd_ellipsoid(P, c + (0, 0.072, -0.030), (0.080, 0.050, 0.092)), 0.03)   # bouffant crown
    shell = shell + 0.0026 * noise3(P, 70.0, 7.0)
    z = P[..., 2] - c[2]
    # edge: above the brow at the front, over the ear tops at the sides, down to the nape at the back
    cut = c[1] + 0.022 + 0.15 * np.maximum(0, z - 0.02) - 0.9 * np.maximum(0, -z - 0.025)
    shell = smax(shell, cut - P[..., 1], 0.004)
    return smax(shell, -(skull - 0.0015), 0.002)


def sdf_cap_band(P):
    """Elastic band following the new cap edge (front above the brow, down to the nape at the back)."""
    c = HEAD_C
    skull = smin(sd_ellipsoid(P, c + (0, 0.012, -0.006), (0.0735, 0.097, 0.0955)),
                 sd_ellipsoid(P, c + (0, 0.035, 0.035), (0.066, 0.062, 0.066)), 0.03)
    z = P[..., 2] - c[2]
    cut = c[1] + 0.022 + 0.15 * np.maximum(0, z - 0.02) - 0.9 * np.maximum(0, -z - 0.025)
    return np.maximum(np.abs(skull - 0.0095) - 0.0026, np.abs(P[..., 1] - cut - 0.0055) - 0.0055)


def sdf_mask(P):
    """Pleated surgical mask: a curved sheet standing off the face (nose bridge to under the chin), 1.6 mm thick."""
    c = HEAD_C
    mc = c + (0, -0.058, 0.026)
    q = P - mc
    pleat = 0.0016 * np.sin((q[..., 1] + 0.06) * 2 * math.pi / 0.024)
    e = sd_ellipsoid(P, mc, (0.086, 0.080, 0.101)) + pleat * np.clip((q[..., 2] - 0.02) * 40, 0, 1)
    shell = np.abs(e) - 0.0016
    region = np.maximum(np.maximum(q[..., 1] - 0.046 + 0.25 * np.abs(q[..., 0]) * 0.4, -0.060 - q[..., 1]), 0.012 - q[..., 2])
    return smax(shell, region, 0.0015)


def mask_loops():
    """Ear-loop polylines (tube meshes are made by the caller)."""
    c = HEAD_C
    out = []
    for s in S2:
        for y0 in (-0.016, -0.100):
            a = c + (s * 0.075, y0, 0.040)
            b = c + (s * 0.079, -0.004 if y0 > -0.05 else -0.040, -0.016)
            m = c + (s * 0.090, (y0 + (-0.004 if y0 > -0.05 else -0.040)) / 2, 0.012)
            out.append(np.array([a, (a + m) / 2 + (s * 0.004, 0, 0), m, (m + b) / 2 + (s * 0.004, 0, 0), b]))
    return out


def sdf_brows(P):
    d = np.full(P.shape[:-1], 1.0)
    for s in S2:
        a = EYE[s] + (-s * 0.012, 0.0150, 0.0110)
        b = EYE[s] + (s * 0.014, 0.0165, 0.0050)
        d = np.minimum(d, sd_capsule(P, a, b, 0.0034, 0.0022))
    return d


def sdf_hair_back(P):
    """Short hair at the back of the head below the cap: a smooth layer over the skin that thins to nothing at a
    curved nape hairline (no hard edges, kept clear of the ears)."""
    c = HEAD_C
    q = P - c
    skin = smin(sdf_head(P), sdf_neck(P), 0.02)
    nape = -0.082 + 0.030 * np.clip(q[..., 0] / 0.060, -1, 1) ** 2               # hairline curves up towards the ears
    fade = np.clip((q[..., 1] - nape) / 0.022, 0.0, 1.0)                          # thickness fades in over 2.2 cm
    shell = skin - (0.0006 + 0.0034 * fade) - 0.00025 * noise3(P, 140.0, 3.0)
    region = smax(nape - q[..., 1], q[..., 1] - 0.012, 0.006)                     # between the hairline and under the cap
    region = smax(region, q[..., 2] + 0.012, 0.010)                               # back half only
    region = smax(region, np.abs(q[..., 0]) - 0.064, 0.008)                       # stop short of the ears
    return smax(smax(shell, region, 0.003), -(skin + 0.0004), 0.0008)


def sdf_eyes(P):
    d = np.full(P.shape[:-1], 1.0)
    for s in S2:
        d = np.minimum(d, np.linalg.norm(P - EYE[s], axis=-1) - EYE_R)
    return d


def sdf_iris(P):
    d = np.full(P.shape[:-1], 1.0)
    for s in S2:
        look = unit((-s * 0.10, -0.35, 1.0))       # looking down at the patient
        c = EYE[s] + look * (EYE_R - 0.0004)
        d = np.minimum(d, sd_ellipsoid(P, c, (0.0058, 0.0058, 0.0012), frame_from(look)))
    return d


def sdf_pupil(P):
    d = np.full(P.shape[:-1], 1.0)
    for s in S2:
        look = unit((-s * 0.10, -0.35, 1.0))
        c = EYE[s] + look * (EYE_R + 0.0004)
        d = np.minimum(d, sd_ellipsoid(P, c, (0.0024, 0.0024, 0.0008), frame_from(look)))
    return d


def sdf_clogs(P):
    d = np.full(P.shape[:-1], 1.0)
    for s in S2:
        c = np.array([s * 0.104, 0.0, 0.050])
        q = P - c
        body = sd_round_box(q, (0, 0.045, 0.0), (0.098, 0.090, 0.285), 0.040)
        toe = sd_ellipsoid(q, (0, 0.045, 0.085), (0.052, 0.050, 0.075))
        body = smin(body, toe, 0.03)
        body = smax(body, q[..., 1] - (0.095 - 0.10 * np.maximum(0, -q[..., 2] - 0.02)), 0.01)   # open heel slope
        opening = sd_ellipsoid(q, (0, 0.100, -0.030), (0.040, 0.050, 0.090))
        body = smax(body, -opening, 0.006)
        sole = sd_round_box(q, (0, 0.012, 0.0), (0.104, 0.024, 0.292), 0.010)
        body = smin(body, sole, 0.004)
        for i in range(3):                                   # vent holes on the toe box
            for j in (-1, 1):
                hole = sd_capsule(q, (j * 0.020, 0.13, 0.060 + i * 0.026), (j * 0.020, 0.05, 0.060 + i * 0.026), 0.0055, 0.0055)
                body = smax(body, -hole, 0.002)
        d = np.minimum(d, body)
    return d


def sdf_badge(P):
    return sd_round_box(P, (-0.085, 1.285, 0.124), (0.052, 0.072, 0.004), 0.004)


# --------------------------------------------------------------------------------------------- meshing utilities
def taubin(m: Mesh, iters=8, lam=0.5, mu=-0.53):
    V = m.V.copy()
    F = m.F
    n = len(V)
    I = np.concatenate([F[:, 0], F[:, 1], F[:, 2], F[:, 1], F[:, 2], F[:, 0]])
    J = np.concatenate([F[:, 1], F[:, 2], F[:, 0], F[:, 0], F[:, 1], F[:, 2]])
    A = sparse.coo_matrix((np.ones(len(I)), (I, J)), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(1)).ravel()
    deg[deg == 0] = 1
    for _ in range(iters):
        for f in (lam, mu):
            L = (A @ V) / deg[:, None] - V
            V = V + f * L
    return Mesh(V, m.N, F, m.UV)


def sdf_normals(fn, V, e=4e-4):
    g = np.stack([fn(V + [e, 0, 0]) - fn(V - [e, 0, 0]), fn(V + [0, e, 0]) - fn(V - [0, e, 0]),
                  fn(V + [0, 0, e]) - fn(V - [0, 0, e])], 1)
    return g / (np.linalg.norm(g, axis=1, keepdims=True) + 1e-12)


def mesh(fn, lo, hi, voxel, smooth=6, cell=None, target=None):
    m0 = sdf_mesh(fn, lo, hi, voxel)
    m = m0
    if cell:
        m = cluster_qem(m0, cell, fn)
    if target:
        c = cell or voxel * 1.5
        while len(m.F) > target:
            c *= 1.25
            m = cluster_qem(m0, c, fn)
    if smooth:
        m = taubin(m, smooth)
    N = sdf_normals(fn, m.V, max(voxel * 0.35, 2e-4))
    return orient_outward(Mesh(m.V, N, m.F, m.UV))


def build_all(log=print, skip=()):
    """Returns [(name, Mesh, material)] in the surgeon's local frame (names in skip are not built)."""
    parts = []
    specs = [
        ("Surgeon_Skin_Head", lambda: mesh(sdf_skin_head, (-0.16, 1.33, -0.13), (0.16, 1.79, 0.13), 0.0013, 3, cell=0.0024, target=60000), "MAT_SurgeonSkin"),
        ("Surgeon_Skin_Arms", lambda: mesh(sdf_skin_arms, (-0.30, 1.03, -0.08), (0.30, 1.48, 0.31), 0.0018, 3, cell=0.0032, target=30000), "MAT_SurgeonSkin"),
        ("Surgeon_Eyes", lambda: mesh(sdf_eyes, (-0.05, 1.655, 0.066), (0.05, 1.690, 0.096), 0.0006, 0, target=6000), "MAT_EyeWhite"),
        ("Surgeon_Iris", lambda: mesh(sdf_iris, (-0.05, 1.652, 0.080), (0.05, 1.690, 0.097), 0.0003, 0, target=3000), "MAT_Iris"),
        ("Surgeon_Pupil", lambda: mesh(sdf_pupil, (-0.05, 1.652, 0.080), (0.05, 1.690, 0.098), 0.0003, 0, target=1200), "MAT_Pupil"),
        ("Surgeon_Brows", lambda: mesh(sdf_brows, (-0.06, 1.675, 0.070), (0.06, 1.702, 0.102), 0.0007, 2, target=3000), "MAT_Hair"),
        ("Surgeon_Hair", lambda: mesh(sdf_hair_back, (-0.08, 1.56, -0.12), (0.08, 1.70, 0.01), 0.0009, 4, cell=0.0016), "MAT_Hair"),
        ("Surgeon_Cap", lambda: mesh(sdf_cap, (-0.11, 1.59, -0.14), (0.11, 1.81, 0.135), 0.0012, 3, cell=0.0022), "MAT_SurgeonCap"),
        ("Surgeon_Cap_Band", lambda: mesh(sdf_cap_band, (-0.10, 1.60, -0.13), (0.10, 1.73, 0.12), 0.0010, 2, cell=0.0020, target=6000), "MAT_SurgeonCapBand"),
        ("Surgeon_Mask", lambda: mesh(sdf_mask, (-0.10, 1.54, 0.02), (0.10, 1.68, 0.14), 0.0008, 2, cell=0.0015), "MAT_SurgicalMask"),
        ("Surgeon_Scrub_Top", lambda: mesh(sdf_scrub_top, (-0.33, 0.82, -0.16), (0.33, 1.58, 0.18), 0.0026, 3, cell=0.0050, target=45000), "MAT_Scrubs"),
        ("Surgeon_Scrub_Trim", lambda: mesh(sdf_top_details, (-0.30, 1.18, -0.10), (0.30, 1.56, 0.16), 0.0011, 2, cell=0.0022, target=10000), "MAT_ScrubsDark"),
        ("Surgeon_Trousers", lambda: mesh(sdf_trousers, (-0.30, 0.09, -0.16), (0.30, 1.05, 0.16), 0.0028, 3, cell=0.0055, target=38000), "MAT_ScrubsDark"),
        ("Surgeon_Waistband", lambda: mesh(sdf_waistband, (-0.21, 0.92, -0.14), (0.21, 1.04, 0.14), 0.0011, 2, cell=0.0022, target=8000), "MAT_Scrubs"),
        ("Surgeon_Gloves", lambda: mesh(sdf_gloves, (-0.24, 1.00, 0.17), (0.24, 1.15, 0.47), 0.0010, 2, cell=0.0016, target=50000), "MAT_Glove"),
        ("Surgeon_Clogs", lambda: mesh(sdf_clogs, (-0.22, -0.005, -0.12), (0.22, 0.14, 0.22), 0.0018, 3, cell=0.0035, target=16000), "MAT_Clog"),
        ("Surgeon_Badge", lambda: mesh(sdf_badge, (-0.12, 1.24, 0.11), (-0.05, 1.33, 0.135), 0.0010, 0, target=2000), "MAT_Badge"),
    ]
    for name, fn, mat in specs:
        if name in skip:
            continue
        m = fn()
        parts.append((name, m, mat))
        log(f"  {name}: {len(m.F)} tris")
    return parts


# --------------------------------------------------------------------------------------------- decimation
def cluster_qem(m: Mesh, cell: float, fn=None) -> Mesh:
    """Quadric-error vertex clustering (Lindstrom 2000): one vertex per grid cell, placed where it minimises the summed
    plane quadrics of the faces around it. Vectorised; keeps creases far better than averaging."""
    V, F = m.V, m.F
    key = np.floor(V / cell).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    k = inv.max() + 1
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    n = np.cross(b - a, c - a)
    area = np.linalg.norm(n, axis=1) + 1e-20
    n = n / area[:, None]
    dpl = -np.sum(n * a, 1)
    p = np.concatenate([n, dpl[:, None]], 1)                     # plane (nx, ny, nz, d)
    Kf = p[:, :, None] * p[:, None, :] * (area / 2)[:, None, None]
    Q = np.zeros((k, 4, 4))
    for j in range(3):
        np.add.at(Q, inv[F[:, j]], Kf)
    cnt = np.bincount(inv, minlength=k).astype(float)
    mean = np.zeros((k, 3))
    np.add.at(mean, inv, V)
    mean /= cnt[:, None]
    A = Q[:, :3, :3] + np.eye(3)[None] * (1e-9 + 1e-3 * np.trace(Q[:, :3, :3], axis1=1, axis2=2))[:, None, None]
    rhs = -Q[:, :3, 3] + (1e-9 + 1e-3 * np.trace(Q[:, :3, :3], axis1=1, axis2=2))[:, None] * mean
    X = np.linalg.solve(A, rhs[..., None])[..., 0]
    # keep the solution inside (a little beyond) its cell
    lo = np.floor(mean / cell) * cell - cell * 0.5
    X = np.clip(X, lo, lo + cell * 2.0)
    F2 = inv[F]
    ok = (F2[:, 0] != F2[:, 1]) & (F2[:, 1] != F2[:, 2]) & (F2[:, 0] != F2[:, 2])
    F2 = F2[ok]
    srt = np.sort(F2, 1)
    _, uniq = np.unique(srt, axis=0, return_index=True)
    F2 = F2[np.sort(uniq)]
    used = np.unique(F2)
    remap = -np.ones(k, np.int64)
    remap[used] = np.arange(len(used))
    V2 = X[used]
    F2 = remap[F2]
    N2 = sdf_normals(fn, V2) if fn is not None else None
    if N2 is None:
        N2 = np.zeros_like(V2)
        fn_ = np.cross(V2[F2[:, 1]] - V2[F2[:, 0]], V2[F2[:, 2]] - V2[F2[:, 0]])
        for j in range(3):
            np.add.at(N2, F2[:, j], fn_)
        N2 /= np.linalg.norm(N2, axis=1, keepdims=True) + 1e-12
    return orient_outward(Mesh(V2, N2, F2))
