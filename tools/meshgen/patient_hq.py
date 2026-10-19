"""High-resolution patient skin and gown (19 Oct 2026): the same anatomy and skeleton as patient.py (every module,
strap and cable position is unchanged), meshed at 3 mm instead of 5 mm, Taubin-smoothed and with SDF normals. The
gown gets fuller shoulder caps so the deltoids no longer show through it. Applied in Unity as in-place mesh upgrades of
the existing Skin_* / Gown_* objects (regions, thermal overlay and colliders are kept)."""
from __future__ import annotations

import numpy as np

import patient as P
from geom import sd_capsule, sd_ellipsoid, smax, smin
from human import mesh as hmesh

EXISTING = {"Skin": {"torso", "arm_left", "arm_right", "leg_left", "leg_right", "head"},
            "Gown": {"torso", "arm_left", "arm_right"}}
TARGET = {"Skin_torso": 90000, "Skin_head": 45000, "Skin_arm_left": 26000, "Skin_arm_right": 26000,
          "Skin_leg_left": 30000, "Skin_leg_right": 30000, "Gown_torso": 80000, "Gown_arm_left": 14000,
          "Gown_arm_right": 14000}


def sdf_gown_hq(Pp):
    d = P.sdf_torso(Pp)
    for s in P.SIDES:
        S, d_ = P.SK.S[s], P.SK.arm_dir[s]
        cap = sd_ellipsoid(Pp, S + np.array([-s * 0.004, 0.010, 0.0]), (0.085, 0.080, 0.088))     # shoulder cap covers the deltoid
        sl = sd_capsule(Pp, S, S + d_ * 0.19, 0.066, 0.058)
        sl = smin(sl, cap, 0.03)
        sl = smax(sl, (Pp - (S + d_ * 0.15)) @ d_, 0.006)
        d = smin(d, sl, 0.04)
        d = smin(d, sd_capsule(Pp, P.SK.H[s], P.SK.H[s] + (P.SK.K[s] - P.SK.H[s]) * 0.32, 0.084, 0.078), 0.05)
    d = d - 0.011 + P.folds(Pp)
    d = smax(d, Pp[..., 2] - 0.655, 0.01)
    d = smax(d, -(np.linalg.norm(Pp - np.array([0, 0.235, 0.705]), axis=-1) - 0.115), 0.012)
    d = smax(d, -0.065 - Pp[..., 2], 0.006)
    return np.maximum(d, -Pp[..., 1] + 0.004)


def build_all(log=print):
    out = []
    skin = hmesh(P.sdf_body, (-0.78, 0.0, -0.78), (0.78, 0.25, 0.93), 0.0030, 3, cell=0.0034)
    log(f"  patient skin {len(skin.F)} tris")
    for region, m in P.split_by_region(skin).items():
        name = f"Skin_{region}"
        if region in EXISTING["Skin"]:
            out.append((name, m, "MAT_Skin"))
    gown = hmesh(sdf_gown_hq, (-0.45, 0.0, -0.12), (0.45, 0.27, 0.70), 0.0032, 3, cell=0.0036)
    log(f"  patient gown {len(gown.F)} tris")
    for region, m in P.split_by_region(gown).items():
        name = f"Gown_{region}"
        if region in EXISTING["Gown"]:
            out.append((name, m, "MAT_Gown"))
    return out
