"""Supine adult mannequin, surgical gown and drape, CH1/CH2 hand mitts, CH3/CH4 foot boots and the wrist wearable.

Anthropometry (visual only, ~1.72 m adult): heel at z = -0.815, head top at z = +0.905, table-top surface y = 0.
Patient supine, face +Y, head +Z, patient's LEFT = +X (CAD coordinate contract, docs/unity/CAD_INTEGRATION.md).
None of these dimensions are CAD or design values.
"""
from __future__ import annotations

import math

import numpy as np

from geom import (Mesh, box, cylinder, frame_from, lathe, merge, orient_outward, quad, rot_x, rot_z, rounded_box,
                  sd_capsule, sd_ellipsoid, sd_round_box, sdf_mesh, smax, smin, submesh_by_faces, torus, tube)

LEFT, RIGHT = 1, -1
SIDES = (LEFT, RIGHT)
SIDE_NAME = {LEFT: "L", RIGHT: "R"}
SIDE_WORD = {LEFT: "left", RIGHT: "right"}


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# ----------------------------------------------------------------------------------------------- skeleton
class Skeleton:
    def __init__(self):
        self.S = {s: np.array([s * 0.185, 0.078, 0.585]) for s in SIDES}           # shoulder joint
        self.arm_dir = {s: unit((s * 0.996, -0.035, -0.087)) for s in SIDES}        # abducted ~85 deg onto arm boards
        self.E = {s: self.S[s] + 0.29 * self.arm_dir[s] for s in SIDES}             # elbow
        self.W = {s: self.E[s] + 0.25 * self.arm_dir[s] for s in SIDES}             # wrist
        self.H = {s: np.array([s * 0.095, 0.088, 0.065]) for s in SIDES}           # hip joint
        self.K = {s: np.array([s * 0.108, 0.078, -0.335]) for s in SIDES}          # knee
        self.A = {s: np.array([s * 0.118, 0.072, -0.735]) for s in SIDES}          # ankle
        # Foot: plantar-flexed 22 deg, externally rotated 12 deg (relaxed supine position)
        self.footR = {s: rot_z(-12 * s) @ rot_x(-22) for s in SIDES}
        # local foot coords (v lateral, u heel->toe, w height above sole) -> world: origin + R @ (s*v, u, w)
        self.foot_origin = {s: self.A[s] - self.footR[s] @ np.array([0.0, 0.05, 0.075]) for s in SIDES}

    def foot_to_world(self, s, v, u, w):
        L = np.stack([s * np.asarray(v, float), np.asarray(u, float), np.asarray(w, float)], -1)
        return self.foot_origin[s] + L @ self.footR[s].T

    def world_to_foot(self, s, P):
        L = (P - self.foot_origin[s]) @ self.footR[s]
        return s * L[..., 0], L[..., 1], L[..., 2]

    def foot_axes(self, s):
        """(lateral, length, plantar-up) unit vectors in world space."""
        Rm = self.footR[s]
        return Rm @ np.array([s * 1.0, 0, 0]), Rm @ np.array([0, 1.0, 0]), Rm @ np.array([0, 0, 1.0])


SK = Skeleton()


# ----------------------------------------------------------------------------------------------- body SDF
def sdf_head(P):
    """Head and neck. Final-release refinement, deliberately restrained: a cranium resting on the pad, a nose with bridge,
    tip and alae instead of a ball, closed eyelids, soft lips, jaw angles, and a neck that widens into the
    trapezius instead of a straight cylinder. The skeleton and every attachment position are unchanged."""
    d = sd_ellipsoid(P, (0, 0.108, 0.805), (0.077, 0.094, 0.104))
    d = smin(d, sd_ellipsoid(P, (0, 0.094, 0.828), (0.072, 0.078, 0.068)), 0.03)              # occiput / cranium vault
    d = smin(d, sd_ellipsoid(P, (0, 0.118, 0.728), (0.058, 0.062, 0.052)), 0.04)            # jaw / chin
    d = smin(d, sd_ellipsoid(P, (0, 0.150, 0.704), (0.026, 0.020, 0.017)), 0.02)            # chin point
    d = smin(d, sd_ellipsoid(P, (0, 0.176, 0.835), (0.062, 0.03, 0.03)), 0.02)               # brow
    for s in SIDES:
        d = smin(d, sd_ellipsoid(P, (s * 0.079, 0.102, 0.800), (0.011, 0.028, 0.027)), 0.01)  # ears
        d = smin(d, sd_ellipsoid(P, (s * 0.04, 0.16, 0.76), (0.03, 0.03, 0.03)), 0.02)       # cheeks
        d = smin(d, sd_ellipsoid(P, (s * 0.052, 0.108, 0.722), (0.018, 0.034, 0.03)), 0.025)  # jaw angle
        d = smin(d, sd_ellipsoid(P, (s * 0.030, 0.186, 0.806), (0.014, 0.005, 0.007)), 0.01)  # closed upper eyelid (subtle)
        d = smin(d, sd_ellipsoid(P, (s * 0.011, 0.191, 0.768), (0.008, 0.007, 0.007)), 0.008)  # nasal ala
    nose = sd_capsule(P, (0, 0.186, 0.812), (0, 0.204, 0.774), 0.0065, 0.0105)                  # bridge -> tip
    nose = smin(nose, sd_ellipsoid(P, (0, 0.202, 0.772), (0.010, 0.008, 0.010)), 0.006)         # tip
    d = smin(d, nose, 0.01)
    d = smin(d, sd_ellipsoid(P, (0, 0.172, 0.749), (0.020, 0.006, 0.006)), 0.006)              # upper lip
    d = smin(d, sd_ellipsoid(P, (0, 0.170, 0.739), (0.017, 0.006, 0.006)), 0.006)              # lower lip
    d = smax(d, -sd_capsule(P, (-0.016, 0.1775, 0.7445), (0.016, 0.1775, 0.7445), 0.0016, 0.0016), 0.003)  # mouth line
    neck = sd_capsule(P, (0, 0.088, 0.615), (0, 0.098, 0.73), 0.056, 0.05)
    neck = smin(neck, sd_ellipsoid(P, (0, 0.078, 0.640), (0.105, 0.050, 0.055)), 0.03)           # trapezius base of neck
    return smin(d, neck, 0.03)


def sdf_torso(P):
    d = sd_ellipsoid(P, (0, 0.108, 0.455), (0.172, 0.108, 0.175))                          # chest
    d = smin(d, sd_ellipsoid(P, (0, 0.098, 0.225), (0.152, 0.102, 0.165)), 0.07)            # abdomen
    d = smin(d, sd_ellipsoid(P, (0, 0.092, 0.065), (0.172, 0.098, 0.13)), 0.07)             # pelvis
    for s in SIDES:
        d = smin(d, sd_ellipsoid(P, SK.S[s] + np.array([-s * 0.012, 0.004, 0.0]), (0.068, 0.064, 0.074)), 0.05)
        d = smin(d, sd_ellipsoid(P, (s * 0.075, 0.172, 0.47), (0.07, 0.04, 0.07)), 0.05)  # pectoral contour
    return d


def sdf_arm(P, s, clip_wrist=True):
    S, E, W, d_ = SK.S[s], SK.E[s], SK.W[s], SK.arm_dir[s]
    a = sd_capsule(P, S, E, 0.047, 0.038)
    a = smin(a, sd_ellipsoid(P, S + d_ * 0.12 + np.array([0, 0.008, 0]), (0.055, 0.046, 0.05), frame_from(d_)), 0.03)  # deltoid/biceps
    end = W - d_ * 0.02 if clip_wrist else W
    a = smin(a, sd_capsule(P, E, end, 0.037, 0.028), 0.03)
    a = smin(a, sd_ellipsoid(P, E + d_ * 0.06, (0.042, 0.04, 0.05), frame_from(d_)), 0.03)  # forearm muscle bulk
    return a


def sdf_leg(P, s):
    H, K, A = SK.H[s], SK.K[s], SK.A[s]
    a = sd_capsule(P, H, K, 0.078, 0.05)
    a = smin(a, sd_ellipsoid(P, H + (K - H) * 0.35 + np.array([0, 0.006, 0]), (0.08, 0.072, 0.17)), 0.05)  # thigh bulk
    a = smin(a, sd_ellipsoid(P, K + np.array([0, 0.03, -0.0]), (0.046, 0.032, 0.04)), 0.03)                # patella
    a = smin(a, sd_capsule(P, K, A + np.array([0, 0, 0.04]), 0.048, 0.033), 0.03)
    a = smin(a, sd_ellipsoid(P, K + (A - K) * 0.28 + np.array([0, -0.008, 0]), (0.052, 0.05, 0.12)), 0.04)  # calf
    a = smin(a, sd_capsule(P, K + (A - K) * 0.12 + np.array([0, 0.036, 0]), K + (A - K) * 0.80 + np.array([0, 0.030, 0]), 0.012, 0.009), 0.03)  # tibial crest (shin)
    for side in (-1, 1):
        a = smin(a, sd_ellipsoid(P, K + np.array([side * 0.030, 0.020, 0.008]), (0.022, 0.024, 0.032)), 0.02)  # femoral condyles (knee shape)
    return a


def sdf_body(P):
    d = smin(sdf_head(P), sdf_torso(P), 0.05)
    for s in SIDES:
        d = smin(d, sdf_arm(P, s), 0.05)
        d = smin(d, sdf_leg(P, s), 0.06)
    return np.maximum(d, -P[..., 1] + 0.0015)  # flattened against the table pad


# ----------------------------------------------------------------------------------------------- region classifier
def bones():
    b = [("head", (0, 0.10, 0.64), (0, 0.11, 0.86), 0.085), ("torso", (0, 0.095, -0.02), (0, 0.10, 0.60), 0.16)]
    for s in SIDES:
        b.append(("arm_" + SIDE_WORD[s], SK.S[s] + SK.arm_dir[s] * 0.035, SK.W[s], 0.045))
        b.append(("leg_" + SIDE_WORD[s], SK.H[s] + np.array([0, 0, -0.06]), SK.A[s], 0.065))
    return b


def classify(points):
    names = []
    dists = []
    for name, a, b_, r in bones():
        a = np.asarray(a, float)
        b_ = np.asarray(b_, float)
        ba = b_ - a
        h = np.clip(((points - a) @ ba) / (ba @ ba), 0, 1)
        dists.append(np.linalg.norm(points - a - h[:, None] * ba, axis=1) - r)
        names.append(name)
    return np.array(names)[np.argmin(np.stack(dists, 1), axis=1)]


def split_by_region(m: Mesh):
    cen = m.V[m.F].mean(axis=1)
    lab = classify(cen)
    out = {}
    for name in np.unique(lab):
        sm = submesh_by_faces(m, lab == name)
        if sm is not None:
            out[str(name)] = sm
    return out


# ----------------------------------------------------------------------------------------------- skin, gown, drape
def folds(P, amp=0.0028):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    return amp * (np.sin(z * 38 + np.sin(x * 9) * 2.2) * 0.6 + np.sin(x * 31 + z * 7) * 0.4) * np.clip((0.2 - y) * 6, 0.3, 1)


def build_skin(voxel=0.0048):
    lo = (-0.78, 0.0, -0.78)
    hi = (0.78, 0.25, 0.93)
    return sdf_mesh(sdf_body, lo, hi, voxel)


def sdf_gown(P):
    d = sdf_torso(P)
    for s in SIDES:
        S, d_ = SK.S[s], SK.arm_dir[s]
        sl = sd_capsule(P, S, S + d_ * 0.17, 0.056, 0.05)
        sl = smax(sl, (P - (S + d_ * 0.13)) @ d_, 0.006)
        d = smin(d, sl, 0.04)
        d = smin(d, sd_capsule(P, SK.H[s], SK.H[s] + (SK.K[s] - SK.H[s]) * 0.32, 0.084, 0.078), 0.05)
    d = d - 0.011 + folds(P)
    d = smax(d, P[..., 2] - 0.655, 0.01)                                         # neckline (top)
    d = smax(d, -(np.linalg.norm(P - np.array([0, 0.235, 0.705]), axis=-1) - 0.115), 0.012)  # scoop neck
    d = smax(d, -0.065 - P[..., 2], 0.006)                                      # hem
    d = np.maximum(d, -P[..., 1] + 0.004)
    return d


def build_gown(voxel=0.0055):
    return sdf_mesh(sdf_gown, (-0.42, 0.0, -0.12), (0.42, 0.26, 0.70), voxel)


def build_drape(nx=150, nz=90):
    """Surgical drape over pelvis and thighs (heightfield sheet that falls over the table sides). Visual only."""
    xs = np.linspace(-0.37, 0.37, nx)
    zs = np.linspace(-0.505, 0.03, nz)
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    ys = np.linspace(0.26, 0.0, 131)
    top = np.zeros_like(X)
    P = np.stack([np.repeat(X[..., None], len(ys), -1), np.broadcast_to(ys, X.shape + (len(ys),)), np.repeat(Z[..., None], len(ys), -1)], -1)
    D = sdf_body(P.reshape(-1, 3)).reshape(P.shape[:3])
    inside = D < 0.0
    has = inside.any(axis=-1)
    first = np.argmax(inside, axis=-1)
    top[has] = ys[first[has]]
    # tenting: smooth envelope over the legs (separable gaussian), never below the body
    def blur(a, sig):
        k = np.arange(-3 * sig, 3 * sig + 1)
        g = np.exp(-(k / sig) ** 2 / 2)
        g /= g.sum()
        a = np.apply_along_axis(lambda r: np.convolve(np.pad(r, 3 * sig, mode="edge"), g, "valid"), 0, a)
        return np.apply_along_axis(lambda r: np.convolve(np.pad(r, 3 * sig, mode="edge"), g, "valid"), 1, a)
    def maxf(a, r):
        out = a.copy()
        for dx in range(-r, r + 1):
            out = np.maximum(out, np.roll(a, dx, axis=0))
        return out
    env = blur(maxf(top, 9), 5)
    h = np.maximum(top + 0.019, env + 0.006)
    h = np.maximum(h, 0.012)
    # fall over the table edge (table half-width 0.275)
    over = np.clip(np.abs(X) - 0.272, 0, None)
    fall = 0.012 - over * 1.0 - (over > 0) * over * 6
    edge_mix = np.clip((np.abs(X) - 0.235) / 0.04, 0, 1)
    h = np.where(np.abs(X) > 0.235, np.minimum(h, (1 - edge_mix) * h + edge_mix * np.maximum(fall, -0.22)), h)
    # cloth folds
    h = h + 0.003 * np.sin(Z * 47 + X * 6) * np.clip(1 - np.abs(X) / 0.3, 0.2, 1) + 0.0025 * np.sin(X * 23 + Z * 13)
    V = np.stack([X, h, Z], -1).reshape(-1, 3)
    # normals from the heightfield gradient
    dhdx = np.gradient(h, xs, axis=0)
    dhdz = np.gradient(h, zs, axis=1)
    N = np.stack([-dhdx, np.ones_like(h), -dhdz], -1).reshape(-1, 3)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    idx = np.arange(nx * nz).reshape(nx, nz)
    a = idx[:-1, :-1].ravel()
    b = idx[1:, :-1].ravel()
    c = idx[1:, 1:].ravel()
    d = idx[:-1, 1:].ravel()
    F = np.vstack([np.stack([a, b, c], 1), np.stack([a, c, d], 1)])
    UV = np.stack([X * 4, Z * 4], -1).reshape(-1, 2)
    top_m = orient_outward(Mesh(V, N, F, UV))
    under = Mesh(V - N * 0.003, -N, top_m.F[:, ::-1].copy(), UV.copy())
    return merge([top_m, under])


# ----------------------------------------------------------------------------------------------- hand mitts (CH1, CH2)
def hand_frame(s):
    d = SK.arm_dir[s]
    up = np.array([0, 1.0, 0])
    side = np.cross(up, d)  # in-plane perpendicular
    side = side if side[2] > 0 else -side  # +Z-ish = thumb side (supinated, thumbs toward the head)
    up = np.cross(d, side) if np.cross(d, side)[1] > 0 else -np.cross(d, side)
    return d, side, up


def sdf_hand(P, s, offset=0.0):
    W = SK.W[s]
    d, t, up = hand_frame(s)
    Rm = np.stack([d, up, t], axis=1)
    palm = sd_round_box(P, W + d * 0.058 + up * 0.016, (0.10, 0.032, 0.086), 0.014, Rm)
    fing = sd_round_box(P, W + d * 0.142 + up * 0.013 - t * 0.003, (0.085, 0.026, 0.080), 0.012, Rm)
    tip = sd_ellipsoid(P, W + d * 0.182 + up * 0.012 - t * 0.004, (0.022, 0.012, 0.038), Rm)
    thumb = sd_capsule(P, W + d * 0.03 + t * 0.03 + up * 0.016, W + d * 0.098 + t * 0.062 + up * 0.02, 0.014, 0.012)
    h = smin(smin(palm, fing, 0.02), tip, 0.02)
    h = smin(h, thumb, 0.018)
    return h - offset


def quilting(P, s, amp=0.0009):
    W = SK.W[s]
    d, t, up = hand_frame(s)
    u = (P - W) @ d
    v = (P - W) @ t
    q = np.cos(u * 2 * math.pi / 0.026) * np.cos(v * 2 * math.pi / 0.026)
    return amp * (0.5 + 0.5 * q)


def sdf_mitt(P, s, offset):
    W, d = SK.W[s], SK.arm_dir[s]
    h = sdf_hand(P, s, offset) - quilting(P, s) * (offset > 0.006)
    r_cuff = 0.028 + offset + 0.004
    cuff = sd_capsule(P, W - d * 0.085, W + d * 0.02, r_cuff + 0.002, r_cuff)
    cuff = smax(cuff, -((P - (W - d * 0.082)) @ d), 0.004)
    m = smin(h, cuff, 0.022)
    return np.maximum(m, -P[..., 1] + 0.003)


def build_hand_module(s):
    """Returns (parts dict name -> (mesh, material)), strain-relief world position, label info."""
    ch = 1 if s == LEFT else 2
    W, d = SK.W[s], SK.arm_dir[s]
    _, t, up = hand_frame(s)
    lo = np.minimum(W - d * 0.1, W + d * 0.22) - 0.07
    hi = np.maximum(W - d * 0.1, W + d * 0.22) + 0.07
    lo[1], hi[1] = 0.0, 0.12
    outer = sdf_mesh(lambda P: sdf_mitt(P, s, 0.0105), lo, hi, 0.0028)
    cen = outer.V[outer.F].mean(axis=1)
    fn = np.cross(outer.V[outer.F[:, 1]] - outer.V[outer.F[:, 0]], outer.V[outer.F[:, 2]] - outer.V[outer.F[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    u = (cen - W) @ d
    v = (cen - W) @ t
    panel = (fn @ up > 0.55) & (u > 0.018) & (u < 0.178) & (np.abs(v + 0.002) < 0.036)
    cuffm = u < -0.004
    parts = {}
    parts[f"CH{ch}_Heater"] = (submesh_by_faces(outer, panel), "MAT_HeaterPanel")
    parts[f"CH{ch}_Shell"] = (submesh_by_faces(outer, ~panel & ~cuffm), "MAT_GloveFabric")
    parts[f"CH{ch}_Cuff"] = (submesh_by_faces(outer, ~panel & cuffm), "MAT_GloveCuff")
    inner_lo, inner_hi = lo, hi
    parts[f"CH{ch}_Insulation"] = (sdf_mesh(lambda P: sdf_mitt(P, s, 0.0065), inner_lo, inner_hi, 0.0045), "MAT_Insulation")
    parts[f"CH{ch}_Liner"] = (sdf_mesh(lambda P: sdf_mitt(P, s, 0.003), inner_lo, inner_hi, 0.0045), "MAT_Liner")
    # sensors on the palm panel (visible pads), cutoff, strain relief, straps, label
    top_y = lambda p: surface_y(lambda Q: sdf_mitt(Q, s, 0.0105), p)
    for name, uu, vv in (("Sensor_A", 0.06, 0.022), ("Sensor_B", 0.12, -0.024)):
        p = W + d * uu + t * vv
        p = np.array([p[0], top_y(p), p[2]])
        parts[f"CH{ch}_{name}"] = (cylinder(0.0065, 0.003, center=p + up * 0.001, segments=20, bevel=0.0008), "MAT_Sensor")
    pc = W - d * 0.05 + t * 0.03
    pc = np.array([pc[0], top_y(pc), pc[2]])
    parts[f"CH{ch}_Cutoff"] = (rounded_box((0.014, 0.006, 0.012), 0.002, center=pc + up * 0.002), "MAT_Connector")
    relief_base = W - d * 0.087 + up * 0.012 - t * 0.012
    relief_tip = relief_base - d * 0.03 - up * 0.004
    parts[f"CH{ch}_Strain_Relief"] = (tube([relief_base, (relief_base + relief_tip) / 2, relief_tip], 0.008, 16, radii=[0.0085, 0.007, 0.0055]), "MAT_Connector")
    # straps: one around the cuff, one around the mitt
    r_c = 0.028 + 0.0105 + 0.006
    parts[f"CH{ch}_Strap_1"] = (strap_around(lambda Q: sdf_mitt(Q, s, 0.0105), W - d * 0.045, d, up, 0.0045), "MAT_Strap")
    parts[f"CH{ch}_Strap_2"] = (strap_around(lambda Q: sdf_mitt(Q, s, 0.0105), W + d * 0.085, d, up, 0.0042), "MAT_Strap")
    buckle_p = W - d * 0.045 + up * (surface_y(lambda Q: sdf_mitt(Q, s, 0.0105), W - d * 0.045) - W[1] + 0.004)
    parts[f"CH{ch}_Buckle"] = (rounded_box((0.016, 0.006, 0.02), 0.002, center=buckle_p + t * 0.012), "MAT_Metal")
    # label plate on top of the cuff, text readable from the foot end (text up = +Z, right = +X)
    lp = W - d * 0.03 - t * 0.008
    lp = np.array([lp[0], top_y(lp) + 0.002, lp[2]])
    parts[f"CH{ch}_Label_Plate"] = (rounded_box((0.058, 0.003, 0.024), 0.0012, center=lp), "MAT_LabelPlate")
    parts[f"CH{ch}_Label"] = (quad(0.054, 0.0195, center=lp + np.array([0, 0.0018, 0]), normal=(0, 1, 0), up=(0, 0, 1)), f"TEX:label_ch{ch}")
    return parts, relief_tip


def surface_y(fn, p, y0=0.16):
    """Highest y where fn < 0 above point p (x,z)."""
    ys = np.linspace(y0, 0.0, 400)
    P = np.stack([np.full_like(ys, p[0]), ys, np.full_like(ys, p[2])], 1)
    D = fn(P)
    i = int(np.argmax(D < 0))
    return float(ys[i])


def strap_ring(center, axis, ry, rz, width, thickness=0.0028, seg=48):
    """Flat band around an axis (elliptical section): inner/outer surfaces + edges."""
    axis = unit(axis)
    up = np.array([0, 1.0, 0])
    up = unit(up - axis * np.dot(up, axis))
    side = np.cross(axis, up)
    th = np.linspace(0, 2 * math.pi, seg + 1)
    ring = lambda r_add, w: np.array([center + axis * w + up * (ry + r_add) * math.sin(a) + side * (rz + r_add) * math.cos(a) for a in th])
    parts = []
    for r_add in (0.0, thickness):
        pts = [ring(r_add, -width / 2), ring(r_add, width / 2)]
        parts.append(strip(pts[0], pts[1], outward=(r_add > 0), center=center, axis=axis))
    return merge(parts)


def strip(A, B, outward, center, axis):
    n = len(A)
    V = np.vstack([A, B])
    radial = V - center
    radial = radial - np.outer(radial @ axis, axis)
    N = radial / (np.linalg.norm(radial, axis=1, keepdims=True) + 1e-12)
    if not outward:
        N = -N
    F = []
    for i in range(n - 1):
        F.append((i, i + 1, n + i + 1))
        F.append((i, n + i + 1, n + i))
    return orient_outward(Mesh(V, N, np.array(F)))


def strap_around(fn, center, axis, up, radius, seg=72):
    """Tube following the cross-section contour of an SDF solid in the plane through `center` normal to `axis`."""
    axis = unit(axis)
    up = unit(up - axis * np.dot(up, axis))
    side = np.cross(axis, up)
    pts = []
    for a in np.linspace(0, 2 * math.pi, seg, endpoint=False):
        dirv = up * math.sin(a) + side * math.cos(a)
        rs = np.linspace(0.0, 0.09, 220)
        P = center + np.outer(rs, dirv)
        D = fn(P)
        inside = np.where(D < 0)[0]
        if len(inside) == 0:
            continue
        r = rs[inside[-1]] + radius * 0.6
        pts.append(center + dirv * r)
    pts.append(pts[0])
    return tube(pts, radius, 10, closed_ends=False)


# ----------------------------------------------------------------------------------------------- foot boots (CH3, CH4)
def sdf_foot_local(v, u, w):
    P = np.stack([v, u, w], -1)
    d = sd_ellipsoid(P, (0, 0.042, 0.036), (0.032, 0.044, 0.036))
    d = smin(d, sd_ellipsoid(P, (0.002, 0.112, 0.034), (0.037, 0.062, 0.034)), 0.03)
    d = smin(d, sd_ellipsoid(P, (0.004, 0.182, 0.025), (0.046, 0.045, 0.025)), 0.03)
    d = smin(d, sd_ellipsoid(P, (0.0, 0.228, 0.016), (0.043, 0.032, 0.016)), 0.02)
    return d


def sdf_boot(P, s, offset):
    v, u, w = SK.world_to_foot(s, P)
    f = sdf_foot_local(v, u, w)
    A, K = SK.A[s], SK.K[s]
    leg_axis = unit(K - A)
    shaft = sd_capsule(P, A - leg_axis * 0.005, A + leg_axis * 0.14, 0.04, 0.043)
    d = smin(f, shaft, 0.035) - offset
    d = smax(d, (P - (A + leg_axis * 0.125)) @ leg_axis, 0.006)  # shaft top
    d = np.maximum(d, -w + 0.0)                                   # stops at the sole top
    return np.maximum(d, -P[..., 1] + 0.0025)


def sole_outline(s, w_level=0.003, n=56, inflate=0.0):
    """Outline (v_lat, v_med) half-widths along u from the boot upper's section; medial arch concavity applied."""
    us = np.linspace(-0.012, 0.262, n)
    vl, vm = np.zeros(n), np.zeros(n)
    vs = np.linspace(0, 0.08, 161)
    for i, u in enumerate(us):
        for sign, arr in ((1, vl), (-1, vm)):
            P = SK.foot_to_world(s, sign * vs, np.full_like(vs, u), np.full_like(vs, w_level))
            D = sdf_boot(P, s, 0.011)
            inside = np.where(D < 0)[0]
            arr[i] = vs[inside[-1]] if len(inside) else 0.0
    # medial longitudinal arch: narrower midfoot on the medial side
    arch = np.exp(-((us - 0.105) / 0.035) ** 2)
    vm = vm * (1 - 0.22 * arch)
    ok = (vl > 0.004) | (vm > 0.004)
    us, vl, vm = us[ok], vl[ok], vm[ok]
    # round the heel/toe ends
    vl = np.maximum(vl, 0.0) + inflate
    vm = np.maximum(vm, 0.0) + inflate
    return us, vl, vm


def sole_layer(s, us, vl, vm, w_bot, w_top, bevel):
    """Extruded sole layer between w_bot and w_top with bevelled edges; outline = lateral side heel->toe then medial
    side toe->heel. Built in foot-local space then mapped to world."""
    # closed outline in local (v, u): lateral side (v = +vl) and medial side (v = -vm)
    ring = [(vl[i], us[i]) for i in range(len(us))] + [(-vm[i], us[i]) for i in range(len(us) - 1, -1, -1)]
    # round the ends with semicircles
    def cap(u0, half_l, half_m, sign):
        pts = []
        c = (half_l - half_m) / 2
        r = (half_l + half_m) / 2
        for a in np.linspace(0, math.pi, 9)[1:-1]:
            pts.append((c + r * math.cos(a) * (1 if sign > 0 else -1) * 1.0, u0 + sign * r * 0.55 * math.sin(a)))
        return pts
    lat = [(vl[i], us[i]) for i in range(len(us))]
    med = [(-vm[i], us[i]) for i in range(len(us) - 1, -1, -1)]
    toe = cap(us[-1], vl[-1], vm[-1], +1)
    heel = cap(us[0], vl[0], vm[0], -1)
    ring = lat + toe + med + heel[::-1]
    ring = np.array(ring)
    # make CCW in (v,u)
    area = 0.5 * np.sum(ring[:, 0] * np.roll(ring[:, 1], -1) - np.roll(ring[:, 0], -1) * ring[:, 1])
    if area < 0:
        ring = ring[::-1]
    nrm = np.roll(ring, -1, 0) - np.roll(ring, 1, 0)
    nrm = np.stack([nrm[:, 1], -nrm[:, 0]], 1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    rows = [(-bevel, w_top, (0.0, 1.0)), (0.0, w_top - bevel, (1.0, 0.0)), (0.0, w_bot + bevel, (1.0, 0.0)), (-bevel, w_bot, (0.0, -1.0))]
    V, N = [], []
    for (inset, w, (nh, nv)) in rows:
        for k in range(len(ring)):
            p2 = ring[k] + nrm[k] * inset
            V.append((p2[0], p2[1], w))
            nn = (nrm[k][0] * nh, nrm[k][1] * nh, nv)
            N.append(nn)
    V = np.array(V)
    N = np.array(N)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    L = len(ring)
    F = []
    for r_ in range(len(rows) - 1):
        for k in range(L):
            a = r_ * L + k
            b = r_ * L + (k + 1) % L
            F.append((a, b, b + L))
            F.append((a, b + L, a + L))
    # caps: fan from centroid (outline is star-shaped about its centroid)
    for (r_, sign) in ((0, 1), (len(rows) - 1, -1)):
        cidx = len(V)
        ctr = ring.mean(axis=0)
        w = rows[r_][1]
        V = np.vstack([V, [[ctr[0], ctr[1], w]]])
        N = np.vstack([N, [[0, 0, sign]]])
        for k in range(L):
            a = r_ * L + k
            b = r_ * L + (k + 1) % L
            F.append((cidx, a, b) if sign > 0 else (cidx, b, a))
    m_local = Mesh(V, N, np.array(F))
    return local_to_world_foot(m_local, s)


def local_to_world_foot(m: Mesh, s):
    Rm = SK.footR[s]
    flip = np.diag([s, 1, 1])
    M = Rm @ flip
    V = SK.foot_origin[s] + m.V @ M.T
    N = m.N @ M.T
    N /= np.linalg.norm(N, axis=1, keepdims=True) + 1e-12
    F = m.F if s > 0 else m.F[:, ::-1].copy()
    return orient_outward(Mesh(V, N, F))


def tread_lugs(s, us, vl, vm, w_bot):
    parts = []
    for u0 in np.arange(0.006, 0.07, 0.016).tolist() + np.arange(0.142, 0.252, 0.016).tolist():
        i = int(np.argmin(np.abs(us - u0)))
        half = (vl[i] + vm[i]) / 2 - 0.006
        cv = (vl[i] - vm[i]) / 2
        if half < 0.01:
            continue
        for side_sign in (-1, 1):
            # chevron halves
            a = np.array([cv, u0, w_bot])
            b = np.array([cv + side_sign * half, u0 - 0.006, w_bot])
            pts_local = [a, (a + b) / 2, b]
            Pw = [SK.foot_to_world(s, p[0], p[1], p[2] - 0.0012) for p in pts_local]
            parts.append(tube(Pw, 0.0022, 6))
    return merge(parts)


def build_foot_module(s):
    ch = 3 if s == LEFT else 4
    lat_ax, len_ax, up_ax = SK.foot_axes(s)
    A = SK.A[s]
    lo = np.minimum(SK.foot_to_world(s, -0.09, -0.04, -0.02), SK.foot_to_world(s, 0.09, 0.3, 0.12))
    hi = np.maximum(SK.foot_to_world(s, -0.09, -0.04, -0.02), SK.foot_to_world(s, 0.09, 0.3, 0.12))
    leg_top = A + unit(SK.K[s] - A) * 0.16
    lo = np.minimum(lo, leg_top) - 0.06
    hi = np.maximum(hi, leg_top) + 0.06
    lo[1] = 0.0
    upper = sdf_mesh(lambda P: sdf_boot(P, s, 0.011), lo, hi, 0.003)
    cen = upper.V[upper.F].mean(axis=1)
    v, u, w = SK.world_to_foot(s, cen)
    toe = (u > 0.198) & (w < 0.034)
    heel = (u < 0.03) & (w < 0.055) & (w > -0.001)
    parts = {}
    parts[f"CH{ch}_Shell"] = (submesh_by_faces(upper, ~toe & ~heel), "MAT_BootFabric")
    parts[f"CH{ch}_Toe_Cap"] = (submesh_by_faces(upper, toe), "MAT_BootTrim")
    parts[f"CH{ch}_Heel_Counter"] = (submesh_by_faces(upper, heel), "MAT_BootTrim")
    # layered sole (from the foot outward): liner, heating layer, cushioning midsole, outsole + tread
    us, vl, vm = sole_outline(s)
    parts[f"CH{ch}_Liner"] = (sole_layer(s, us, vl - 0.004, vm - 0.004, 0.0, 0.0035, 0.0012), "MAT_Liner")
    parts[f"CH{ch}_Heater"] = (sole_layer(s, us, vl + 0.002, vm + 0.002, -0.0055, 0.0, 0.0012), "MAT_HeaterLayer")
    parts[f"CH{ch}_Insulation"] = (sole_layer(s, us, vl + 0.0058, vm + 0.0058, -0.0205, -0.0055, 0.003), "MAT_Midsole")
    parts[f"CH{ch}_Sole_Outsole"] = (sole_layer(s, us, vl + 0.003, vm + 0.003, -0.029, -0.0205, 0.0025), "MAT_Outsole")
    parts[f"CH{ch}_Sole_Tread"] = (tread_lugs(s, us, vl + 0.002, vm + 0.002, -0.029), "MAT_Outsole")
    # sole label in the arch (visible from the foot end), printed on the outsole bottom
    lc = SK.foot_to_world(s, (vl[len(us) // 2] - vm[len(us) // 2]) / 2, 0.105, -0.0292)
    nrm = -up_ax
    parts[f"CH{ch}_Sole_Label"] = (quad(0.07, 0.026, center=lc + nrm * 0.0004, normal=nrm, up=up_ax * 0 + len_ax), f"TEX:label_ch{ch}")
    # sensors inside on the heating layer (visible in exploded view), cutoff on the lateral heel
    for name, uu in (("Sensor_A", 0.045), ("Sensor_B", 0.175)):
        p = SK.foot_to_world(s, 0.0, uu, 0.0006)
        parts[f"CH{ch}_{name}"] = (cylinder(0.007, 0.0028, center=p, R=rot_between_y(up_ax), segments=18, bevel=0.0007), "MAT_Sensor")
    cp = SK.foot_to_world(s, 0.05, 0.03, 0.012)
    parts[f"CH{ch}_Cutoff"] = (rounded_box((0.012, 0.012, 0.008), 0.002, center=cp), "MAT_Connector")
    # straps: instep and ankle, with buckles on the lateral side
    fn = lambda Q: sdf_boot(Q, s, 0.011)
    c1 = SK.foot_to_world(s, 0.0, 0.118, 0.02)
    parts[f"CH{ch}_Strap_1"] = (strap_partial(fn, c1, len_ax, up_ax, 0.0045, lambda Q: SK.world_to_foot(s, Q)[2] > 0.004), "MAT_Strap")
    leg_axis = unit(SK.K[s] - A)
    c2 = A + leg_axis * 0.07
    parts[f"CH{ch}_Strap_2"] = (strap_partial(fn, c2, leg_axis, unit(np.cross(leg_axis, lat_ax)) * -1, 0.0045, lambda Q: Q[..., 1] > 0.006), "MAT_Strap")
    b1 = boundary_point(fn, c1, lat_ax) + lat_ax * 0.005
    b2 = boundary_point(fn, c2, lat_ax) + lat_ax * 0.005
    parts[f"CH{ch}_Buckle"] = (merge([rounded_box((0.006, 0.02, 0.016), 0.002, center=b1), rounded_box((0.006, 0.02, 0.016), 0.002, center=b2)]), "MAT_Metal")
    # padded collar at the shaft top
    top_c = A + leg_axis * 0.122
    parts[f"CH{ch}_Collar"] = (strap_partial(fn, top_c - leg_axis * 0.004, leg_axis, unit(np.cross(leg_axis, lat_ax)) * -1, 0.0062, lambda Q: Q[..., 1] > 0.004), "MAT_BootTrim")
    # label plate on the lateral shaft
    lpc = boundary_point(fn, A + leg_axis * 0.05 + len_ax * 0.0, lat_ax * 0.75 - leg_axis * 0 + up_ax * 0.0 + np.array([0, 0.66, 0]))
    nrm_l = unit(lat_ax * 0.75 + np.array([0, 0.66, 0]))
    parts[f"CH{ch}_Label_Plate"] = (rounded_box((0.05, 0.003, 0.022), 0.0012, center=lpc + nrm_l * 0.0015, R=rot_between_y(nrm_l)), "MAT_LabelPlate")
    parts[f"CH{ch}_Label"] = (quad(0.046, 0.0175, center=lpc + nrm_l * 0.0033, normal=nrm_l, up=leg_axis), f"TEX:label_ch{ch}")
    # strain relief at the back of the heel (cable runs toward the controller)
    rb = boundary_point(fn, SK.foot_to_world(s, 0.02, 0.0, 0.03), -len_ax * 0.7 + lat_ax * 0.7)
    dirc = unit(-len_ax * 0.6 + lat_ax * 0.5 + np.array([0, -0.4, 0]))
    rtip = rb + dirc * 0.03
    parts[f"CH{ch}_Strain_Relief"] = (tube([rb - dirc * 0.004, rb + dirc * 0.015, rtip], 0.008, 16, radii=[0.009, 0.0075, 0.0058]), "MAT_Connector")
    return parts, rtip


def rot_between_y(n):
    from geom import rotation_between
    return rotation_between((0, 1, 0), n)


def boundary_point(fn, center, direction, rmax=0.12):
    dirv = unit(direction)
    rs = np.linspace(0, rmax, 400)
    P = center + np.outer(rs, dirv)
    D = fn(P)
    inside = np.where(D < 0)[0]
    r = rs[inside[-1]] if len(inside) else 0.0
    return center + dirv * r


def strap_partial(fn, center, axis, up, radius, keep, seg=90):
    axis = unit(axis)
    up = unit(up - axis * np.dot(up, axis))
    side = np.cross(axis, up)
    runs, cur = [], []
    for a in np.linspace(0, 2 * math.pi, seg, endpoint=False):
        dirv = up * math.sin(a) + side * math.cos(a)
        p = boundary_point(fn, center, dirv) + dirv * radius * 0.55
        if bool(np.atleast_1d(keep(p[None, :]))[0]):
            cur.append(p)
        else:
            if len(cur) > 2:
                runs.append(cur)
            cur = []
    if len(cur) > 2:
        if runs and np.linalg.norm(runs[0][0] - cur[-1]) < 0.02:
            runs[0] = cur + runs[0]
        else:
            runs.append(cur)
    return merge([tube(r, radius, 8, closed_ends=True) for r in runs])


# ----------------------------------------------------------------------------------------------- wearable
def build_watch():
    s = RIGHT
    E, W, d = SK.E[s], SK.W[s], SK.arm_dir[s]
    c = E + (W - E) * 0.5
    r_arm = 0.037 + (0.028 - 0.037) * 0.5
    parts = {}
    up = np.array([0, 1.0, 0])
    up = unit(up - d * np.dot(up, d))
    band = strap_ring(c, d, r_arm + 0.002, r_arm + 0.004, 0.022, 0.003, 64)
    parts["Watch_Band"] = (band, "MAT_WatchBand")
    top = c + up * (r_arm + 0.007)
    Rm = np.stack([d, up, np.cross(d, up)], axis=1)  # local x along arm, y up
    body = rounded_box((0.044, 0.011, 0.04), 0.0045, center=top + up * 0.003, R=Rm)
    parts["Watch_Body"] = (body, "MAT_WatchBody")
    bezel = torus(0.0175, 0.0012, center=top + up * 0.0088, Rm=None, seg_major=48, seg_minor=8)
    parts["Watch_Bezel"] = (bezel, "MAT_Metal")
    parts["Watch_Screen"] = (disc_up(0.0165, top + up * 0.0089), "TEX:watch_face")
    crown = cylinder(0.0028, 0.004, center=top + up * 0.003 + np.cross(d, up) * 0.0225 * (-1), R=rot_x(90), segments=14, bevel=0.0005)
    parts["Watch_Crown"] = (crown, "MAT_Metal")
    return parts, top + up * 0.009


def disc_up(r, center, seg=40):
    from geom import disc_mesh
    m = disc_mesh(r, seg, up=True)
    # UV: (u right = +X, v up = +Z) for a viewer from the foot end looking down
    m = Mesh(m.V, m.N, m.F, np.stack([0.5 + m.V[:, 0] / (2 * r), 0.5 + m.V[:, 2] / (2 * r)], 1))
    return m.transformed(t=center)


# ----------------------------------------------------------------------------------------------- illustrative vessels
def build_vessels():
    """Simplified, ILLUSTRATIVE network of major vessels (not patient-specific anatomy or flow data).
    Returns [(name, kind 'artery'|'vein', [points ordered in the illustrative flow direction], radius)].
    Arteries run from the heart outward, veins toward the heart."""
    heart = np.array([0.012, 0.105, 0.47])
    arch = np.array([0.0, 0.118, 0.53])
    bif = np.array([0.0, 0.085, 0.10])
    out = []

    def poly(*pts):
        return [np.asarray(p, float) for p in pts]

    out.append(("Aorta", "artery", poly(heart, arch + [0.01, 0, 0.0], [0.0, 0.10, 0.50], [0.0, 0.085, 0.38], [0.0, 0.08, 0.22], bif), 0.0095))
    out.append(("Vena_Cava", "vein", poly(bif + [-0.022, 0.004, -0.01], [-0.024, 0.085, 0.22], [-0.024, 0.09, 0.38], heart + [-0.03, 0, -0.01]), 0.0105))
    for s in SIDES:
        n = SIDE_WORD[s].capitalize()
        S, E, W, d = SK.S[s], SK.E[s], SK.W[s], SK.arm_dir[s]
        H, K, A = SK.H[s], SK.K[s], SK.A[s]
        # head/neck
        out.append((f"Carotid_{n}", "artery", poly(arch + [s * 0.012, 0, 0.0], [s * 0.022, 0.11, 0.62], [s * 0.03, 0.115, 0.72], [s * 0.035, 0.11, 0.78]), 0.0045))
        out.append((f"Jugular_{n}", "vein", poly([s * 0.045, 0.10, 0.77], [s * 0.04, 0.10, 0.70], [s * 0.035, 0.098, 0.62], heart + [s * 0.01 - 0.02, 0.0, 0.03]), 0.0055))
        # arms
        a_up = S + np.array([0, -0.006, 0])
        out.append((f"Subclavian_Brachial_{n}", "artery", poly(arch + [s * 0.02, 0, -0.01], [s * 0.09, 0.11, 0.555], a_up, S + d * 0.15 + [0, -0.006, 0.006], E + [0, -0.004, 0.008]), 0.005))
        out.append((f"Radial_{n}", "artery", poly(E + [0, -0.004, 0.008], E + d * 0.12 + [0, 0.0, 0.012], W + [0, 0.004, 0.012]), 0.0034))
        out.append((f"Ulnar_{n}", "artery", poly(E + [0, -0.004, 0.008], E + d * 0.12 + [0, -0.004, -0.012], W + [0, 0.0, -0.012]), 0.003))
        out.append((f"Arm_Vein_{n}", "vein", poly(W + [0, 0.012, 0.0], E + d * 0.05 + [0, 0.014, 0.0], S + d * 0.12 + [0, 0.012, -0.012], [s * 0.09, 0.105, 0.545], heart + [s * 0.015 - 0.02, 0.0, 0.02]), 0.0045))
        # legs
        out.append((f"Iliac_Femoral_{n}", "artery", poly(bif, [s * 0.05, 0.08, 0.05], H + [s * 0.01, -0.005, -0.06], H + (K - H) * 0.5 + [0, 0.0, 0], K + [0, -0.02, 0.02]), 0.0065))
        out.append((f"Tibial_{n}", "artery", poly(K + [0, -0.02, 0.02], K + (A - K) * 0.5 + [0, -0.01, 0], A + [0, -0.005, 0.03]), 0.0042))
        out.append((f"Leg_Vein_{n}", "vein", poly(A + [s * 0.012, 0.0, 0.03], K + (A - K) * 0.5 + [s * 0.014, 0.0, 0], K + [s * 0.016, -0.015, 0.02], H + (K - H) * 0.5 + [s * 0.016, 0.0, 0], H + [s * 0.012, 0.0, -0.06], bif + [-0.022 + s * 0.03, 0.004, -0.01]), 0.0065))
    return out


def smooth_polyline(pts, samples_per_seg=8):
    """Catmull-Rom resampling for smooth tubes and pulse paths."""
    P = [np.asarray(p, float) for p in pts]
    if len(P) < 3:
        return np.array(P)
    ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(samples_per_seg):
            t = k / samples_per_seg
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return np.array(out)


def iv_access_point():
    """Antecubital access on the patient's RIGHT arm (-X): skin surface point and outward direction."""
    s = RIGHT
    E, d = SK.E[s], SK.arm_dir[s]
    p = E + d * 0.035
    top = surface_y(sdf_body, p, 0.2)
    return np.array([p[0], top, p[2]]), d
