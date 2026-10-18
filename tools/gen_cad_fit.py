"""Fit Neharika's CAD (cad/exports/unity/*.fbx, Unity-prepped) to the generated mannequin (Sai, 2026-10-18).

Writes unity_editor/Assets/NERAM_Generated/MeshData/cad_fit.json, read by Editor/NeramCadPlacement.cs:
  poses   : world position + LookRotation(fwd, up) + uniform scale per CAD root
  meshes  : hand and foot skin (visual stand-in) that fit the CAD pads:
            hands = palm-up, dorsum on the arm board, outline = the glove liner outline (every finger under its glove finger)
            feet  = five-toed foot, sole flat on the pad
  parts   : replacement meshes for CAD children, in the CAD root's local frame:
            - the hand pads are fabric layers (liner, heater film, insulation, shell): subdivided and draped onto the
              hand, edges folded around the fingers (v2, Sai: they floated flat over the fingers before)
            - straps rebuilt as bands that follow the limb + pad section (CAD width/thickness kept, length fitted to
              the limb - visual fit, flagged for Neharika); the closure tabs (Hook) lie on the band
            - BC_Display_Screen: lit quad on the controller display (texture controller_screen)
  cables  : waypoints from the controller ports to each pad's cable edge
  watch   : node position for the live watch face
Geometry and sizes of the CAD are unchanged except the documented visual fits (pad drape, strap length, watch scale).
Needs numpy, scipy, scikit-image (the laptop VM has no scikit-image: run where it is installed).
Unity imports these FBX as Unity-local = (x, y, -z) of the FBX coordinates (checked in the editor).
All numbers below are visual layout, not design values."""
import json, sys
from pathlib import Path
import numpy as np
from scipy import ndimage

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "meshgen"))
sys.path.insert(0, str(HERE))
import patient as P
from geom import sdf_mesh, sd_capsule, sd_ellipsoid, smin
import fbxread
import cadfit_lib as CL

CAD = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "unity_editor/Assets/NERAM_CAD"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE.parent / "unity_editor/Assets/NERAM_Generated/MeshData/cad_fit.json"
SK = P.SK
LEFT, RIGHT = P.LEFT, P.RIGHT
BOARD_LIFT = 0.025                    # arm boards raised so the forearm rests on them (arm bottom y = 0.031)
BOARD_TOP = 0.006 + BOARD_LIFT


def unit(v):
    v = np.asarray(v, float); return v / np.linalg.norm(v)


def frame(fwd, up):
    f = unit(fwd); u = unit(np.asarray(up, float) - f * np.dot(up, f)); r = np.cross(u, f)
    return np.stack([r, u, f], 1)  # columns: local X, Y, Z in world


def load(name):
    parts = fbxread.load(CAD / name)
    return {n: (V * np.array([1, 1, -1]), F[:, ::-1]) for n, (V, F) in parts.items()}  # Unity-local


def to_world(p, R, k, V): return p + (np.asarray(V) * k) @ R.T


fit = {"note": __doc__.split("\n")[0], "poses": {}, "meshes": [], "straps": [], "parts": [], "hooks": [], "cables": {}, "boardLift": BOARD_LIFT}


def pose(role, p, R, k=1.0):
    fit["poses"][role] = {"p": list(map(float, p)), "fwd": list(map(float, R[:, 2])), "up": list(map(float, R[:, 1])), "k": float(k)}


def add_mesh(name, role, m):
    fit["meshes"].append({"name": name, "role": role, "v": np.round(m.V, 5).ravel().tolist(), "n": np.round(m.N, 4).ravel().tolist(), "f": m.F.ravel().astype(int).tolist()})


def outline_sdf(V, F, res=0.0005, pad=0.03):
    """2D signed distance (metres, negative inside) of the x-z silhouette of a mesh."""
    lo = V[:, [0, 2]].min(0) - pad; hi = V[:, [0, 2]].max(0) + pad
    nx, nz = np.ceil((hi - lo) / res).astype(int) + 1
    mask = np.zeros((nx, nz), bool)
    gx = lo[0] + np.arange(nx) * res; gz = lo[1] + np.arange(nz) * res
    X, Z = np.meshgrid(gx, gz, indexing="ij")
    for t in F:
        a, b, c = V[t][:, [0, 2]]
        x0, z0 = np.minimum(np.minimum(a, b), c); x1, z1 = np.maximum(np.maximum(a, b), c)
        i0, i1 = int((x0 - lo[0]) / res), int((x1 - lo[0]) / res) + 2
        j0, j1 = int((z0 - lo[1]) / res), int((z1 - lo[1]) / res) + 2
        px, pz = X[i0:i1, j0:j1], Z[i0:i1, j0:j1]
        d = (b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])
        if abs(d) < 1e-14: continue
        w1 = ((b[0] - px) * (c[1] - pz) - (c[0] - px) * (b[1] - pz)) / d
        w2 = ((c[0] - px) * (a[1] - pz) - (a[0] - px) * (c[1] - pz)) / d
        mask[i0:i1, j0:j1] |= (w1 >= -1e-9) & (w2 >= -1e-9) & (w1 + w2 <= 1 + 1e-9)
    D = (ndimage.distance_transform_edt(~mask) - ndimage.distance_transform_edt(mask)) * res

    def f(x, z):
        i = np.clip((x - lo[0]) / res, 0, nx - 1.001); j = np.clip((z - lo[1]) / res, 0, nz - 1.001)
        return ndimage.map_coordinates(D, [i.ravel(), j.ravel()], order=1, mode="nearest").reshape(np.shape(x))
    return f, mask, gx, gz


def rounded_extrude(s2, y, y0, y1, r):
    """Rounded slab between y0 and y1 with outline sdf s2 (all arrays)."""
    h = (y1 - y0) / 2; c = (y1 + y0) / 2
    r = np.minimum(r, h * 0.95)
    wx = s2 + r; wy = np.abs(y - c) - (h - r)
    return np.minimum(np.maximum(wx, wy), 0) + np.hypot(np.maximum(wx, 0), np.maximum(wy, 0)) - r



def add_band(role, obj, V, N, F):
    fit["parts"].append({"role": role, "obj": obj, "v": np.round(V, 5).ravel().tolist(), "n": np.round(N, 4).ravel().tolist(), "f": F.ravel().astype(int).tolist()})


def pad_parts(parts):
    return [n for n in parts if not any(k in n for k in ("Strap", "Hook"))]


# ------------------------------------------------------------------------------------------------ hands
# Palm-up hand, back of the hand on the (raised) arm board. Built from the medial axis of the glove liner outline:
# one rounded blob per axis point (round for fingers, flattened for the palm), so every glove finger has its own
# finger underneath. The pad (fabric layers) is then draped onto the hand surface.
HAND_INSET = 0.0016
EDGE_FOLD = 0.0045                  # fabric pad edges fold down around the fingers (visual drape)
for s, role, ch, f in ((LEFT, "Left_Hand_Module", 1, "NERAM_Left_Hand_Module.fbx"), (RIGHT, "Right_Hand_Module", 2, "NERAM_Right_Hand_Module.fbx")):
    parts = load(f)
    LV, LF = parts[f"CH{ch}_Liner"]
    W, d = SK.W[s], SK.arm_dir[s]
    _, t_side, up = P.hand_frame(s)
    R = frame(d, up)
    res = 0.0005
    sdf2, mask, gx, gz = outline_sdf(LV, LF, res=res)
    T = 0.0315                                                   # palm thickness (board to palm surface)
    skin_y = BOARD_TOP + T
    p = W + d * 0.07
    p = p + R[:, 1] * ((skin_y - p[1]) / R[1, 1])
    pose(role, p, R)
    hm = (ndimage.distance_transform_edt(mask) * res) > HAND_INSET
    bx, bz, br = CL.skeleton_blobs(hm, gx, gz, res, rmin=0.0022)
    ry_of = lambda r, T=T: np.minimum(0.92 * r, T / 2)
    yc_of = lambda r, T=T: -T + np.minimum(0.92 * r, T / 2) + 0.0003
    fore_a, fore_b = W - d * 0.07, W + d * 0.012 + np.array([0.0, (BOARD_TOP + skin_y) / 2 - W[1], 0.0])

    def hand_local(L, p=p, R=R, bx=bx, bz=bz, br=br, ry_of=ry_of, yc_of=yc_of, fa=fore_a, fb=fore_b):
        X = p + L @ R.T
        h = CL.blobs_sdf(L, bx, bz, br, ry_of, yc_of, k=0.0018)
        fore = sd_capsule(X, fa, fb, 0.0245, 0.0145)
        return np.maximum(smin(h, fore, 0.022), -X[..., 1] + BOARD_TOP)

    def hand_sdf(X, p=p, R=R):
        return hand_local((X - p) @ R)
    c = p.copy()
    lo = np.minimum(c - 0.13, fore_a - 0.04); hi = np.maximum(c + 0.13, fore_a + 0.04)
    lo[1], hi[1] = BOARD_TOP - 0.004, skin_y + 0.004
    add_mesh("Skin_hand_" + P.SIDE_WORD[s], role, sdf_mesh(hand_sdf, lo, hi, 0.0013))
    # drape grid: top of the hand under the pad (local y, <= 0), 1 mm grid over the liner footprint
    step = 0.001
    xg = np.arange(gx[0], gx[-1], step); zg = np.arange(gz[0], gz[-1], step)
    top = CL.skin_top(hand_local, xg, zg, sdf2, -T - 0.002, 0.004)
    H = np.minimum(CL.fill_smooth(top, 1.8) + 0.0006, 0.0)
    Hs = lambda x, z, H=H, x0=xg[0], z0=zg[0]: CL.sample_grid(H, x0, z0, step, x, z)
    ntri = 0
    for pn in pad_parts(parts):                                    # fabric layers draped onto the hand
        PV, PF = parts[pn]
        need = lambda a, b, Hs=Hs, sdf2=sdf2: (float(sdf2((a[0] + b[0]) / 2, (a[2] + b[2]) / 2)) > -0.004 and np.linalg.norm(a - b) > 0.006) or abs(float(Hs((a[0] + b[0]) / 2, (a[2] + b[2]) / 2)) - (float(Hs(a[0], a[2])) + float(Hs(b[0], b[2]))) / 2) > 0.0002
        PV, PF = CL.subdivide(PV, PF, 0.003, need=need)
        din = -sdf2(PV[:, 0], PV[:, 2])                            # distance inside the glove outline
        w_ = np.clip(1 - din / 0.0035, 0, 1); fold = EDGE_FOLD * w_ * w_ * (3 - 2 * w_)
        PV = PV + np.c_[np.zeros(len(PV)), Hs(PV[:, 0], PV[:, 2]) - fold, np.zeros(len(PV))]
        V_, N_, F_ = CL.corner_normals(PV, PF)
        add_band(role, pn, V_, N_, F_); ntri += len(F_)

    def inside(x, y, z, hand_local=hand_local, Hs=Hs, sdf2=sdf2):
        L = np.stack([x, y, z], -1)
        h = hand_local(L) < 0
        hz = Hs(x, z)
        pad = (sdf2(x, z) < 0) & (y >= hz - 0.0002) & (y <= hz + 0.0092)
        return h | pad
    for k in (1, 2):
        SV, _ = parts[f"CH{ch}_Strap_{k}"]
        z0, z1 = SV[:, 2].min(), SV[:, 2].max()
        xl = (SV[:, 0].min() - 0.004, SV[:, 0].max() + 0.004)
        V, N, F, loop = CL.band(inside, z0, z1, xl, (-T - 0.006, 0.02))
        add_band(role, f"CH{ch}_Strap_{k}", V, N, F)
        HV, _ = parts[f"CH{ch}_Hook_{k}"]
        add_band(role, f"CH{ch}_Hook_{k}", *CL.hook_patch(loop, z0, z1, float(np.ptp(HV[:, 0]))))
    end_local = np.array([0.0, 0.004 + float(Hs(0.0, LV[:, 2].min() + 0.004)), LV[:, 2].min()])
    fit["cables"][str(ch)] = {"end": list(map(float, to_world(p, R, 1, end_local))), "side": list(map(float, -t_side))}
    print(role, "draped pad tris", ntri, "blobs", len(bx), "finger drop", round(float(H.min()), 4), "pose", np.round(p, 3))

# ------------------------------------------------------------------------------------------------ wrists
# The generated forearm ends in a round 28 mm cap (it used to disappear inside the stand-in mitt). Flatten the last
# ~9 cm into an oval wrist: the top is lowered towards the palm, the bottom (resting on the board) is unchanged.
import scene as SCN
BUNDLE = Path(sys.argv[3]) if len(sys.argv) > 3 else HERE.parent / "unity_editor/Assets/NERAM_Generated/MeshData/neram_scene.bytes"
_, _, bmeshes = SCN.read_bundle(BUNDLE)
fit["replace"] = []
ARMV = {}
for s_ in (LEFT, RIGHT):
    m = [m for m in bmeshes if m["name"] == "Skin_arm_" + P.SIDE_WORD[s_]][0]
    V = m["V"].astype(float) + np.array(m["pivot"]); N = m["N"].astype(float).copy(); I = m["I"].reshape(-1, 3)
    S_, d_ = SK.S[s_], SK.arm_dir[s_]
    side_ = unit(np.cross(np.array([0, 1.0, 0]), d_))
    t = (V - S_) @ d_
    w = np.clip((t - 0.495) / 0.05, 0, 1); w = w * w * (3 - 2 * w)
    axis = S_ + np.outer(t, d_)
    # slimmer lower forearm/wrist (generated arm is ~60 mm across at the wrist; adult wrists are ~50-55 mm)
    w2 = np.clip((t - 0.38) / 0.09, 0, 1); w2 = w2 * w2 * (3 - 2 * w2)
    rel0 = V - axis
    V = axis + rel0 * (1 - 0.11 * w2)[:, None]
    rel = V - axis
    dy = rel[:, 1]; lat = rel @ side_
    top = dy > 0
    newV = V.copy()
    newV[:, 1] = np.where(top, axis[:, 1] + dy * (1 - 0.45 * w), V[:, 1])
    newV += np.outer(lat * 0.12 * w, side_)
    moved = (w > 0) | (w2 > 0)
    fn = np.cross(newV[I[:, 1]] - newV[I[:, 0]], newV[I[:, 2]] - newV[I[:, 0]])
    acc = np.zeros_like(V)
    for k in range(3): np.add.at(acc, I[:, k], fn)
    acc /= np.maximum(np.linalg.norm(acc, axis=1, keepdims=True), 1e-12)
    if np.mean(np.einsum("ij,ij->i", acc[~moved], N[~moved])) < 0: acc = -acc
    N[moved] = acc[moved]
    ARMV[s_] = newV
    fit["replace"].append({"name": m["name"], "v": np.round(newV, 5).ravel().tolist(), "n": np.round(N, 4).ravel().tolist()})
    print(m["name"], "wrist flattened,", int(moved.sum()), "vertices")


# ------------------------------------------------------------------------------------------------ feet
# Supine feet (toes up, sole towards the foot end). Toe lengths of an adult foot (big toe ~3 cm, others ~2 cm);
# the sole pad covers heel-to-ball, toes stay free.
TOES = [(-0.028, 0.196, 0.238, 0.0125), (-0.0085, 0.199, 0.229, 0.0088), (0.0075, 0.197, 0.223, 0.0083),
        (0.0215, 0.193, 0.215, 0.0078), (0.0340, 0.187, 0.205, 0.0072)]   # (v, u0, u1, r), v > 0 lateral


def foot_local(v, u, w):
    X = np.stack([v, u, w], -1)
    dd = sd_ellipsoid(X, (0.0, 0.040, 0.032), (0.031, 0.046, 0.033))              # heel
    dd = smin(dd, sd_ellipsoid(X, (0.004, 0.108, 0.030), (0.037, 0.072, 0.031)), 0.03)   # midfoot
    dd = smin(dd, sd_ellipsoid(X, (-0.004, 0.094, 0.040), (0.028, 0.055, 0.027)), 0.03)   # instep
    dd = smin(dd, sd_ellipsoid(X, (-0.001, 0.168, 0.021), (0.047, 0.036, 0.022)), 0.025) # forefoot / ball
    toes = None
    for tv, u0, u1, r in TOES:
        tt = sd_capsule(X, np.array([tv, u0, r * 1.02]), np.array([tv * 1.03, u1 - r, r * 0.97]), r, r * 0.93)
        toes = tt if toes is None else np.minimum(toes, tt)
    dd = smin(dd, toes, 0.006)
    return np.maximum(dd, -w)                                                      # flat sole (w = 0)


for s, role, ch, f in ((LEFT, "Left_Foot_Module", 3, "NERAM_Left_Foot_Module.fbx"), (RIGHT, "Right_Foot_Module", 4, "NERAM_Right_Foot_Module.fbx")):
    parts = load(f)
    LV, LF = parts[f"CH{ch}_Liner"]
    wide = lambda z0: np.ptp(LV[np.abs(LV[:, 2] - z0) < 0.01, 0])
    assert wide(0.06) > wide(-0.06), "wide (forefoot) end is not at local +Z"
    lat, length, plant_up = SK.foot_axes(s)
    R = frame(length, -plant_up)                    # pad +Z -> toes, pad +Y -> out of the sole
    U_C = 0.112
    p = SK.foot_to_world(s, 0.0, U_C, 0.0)
    pose(role, p, R)
    A, K = SK.A[s], SK.K[s]
    leg = unit(K - A)

    def foot_sdf(X, s=s, A=A, leg=leg):
        v, u, w = SK.world_to_foot(s, X)
        dd = foot_local(v, u, w)
        dd = smin(dd, sd_capsule(X, A - leg * 0.005, A + leg * 0.075, 0.035, 0.0335), 0.028)
        return np.maximum(dd, -X[..., 1] + 0.0015)
    c = SK.foot_to_world(s, 0.0, 0.13, 0.03)
    add_mesh("Skin_foot_" + P.SIDE_WORD[s], role, sdf_mesh(foot_sdf, c - 0.19, c + 0.19, 0.0019))
    sdf2, _, _, _ = outline_sdf(LV, LF)

    def inside(x, y, z, p=p, R=R, foot_sdf=foot_sdf, sdf2=sdf2):
        L = np.stack([x, y, z], -1)
        f_ = foot_sdf(p + L @ R.T) < 0
        pad = (sdf2(x, z) < 0) & (y >= -0.0002) & (y <= 0.0087)
        return f_ | pad
    for k in (1, 2):
        SV, _ = parts[f"CH{ch}_Strap_{k}"]
        z0, z1 = SV[:, 2].min(), SV[:, 2].max()
        V, N, F, loop = CL.band(inside, z0, z1, (-0.075, 0.075), (-0.12, 0.02))
        add_band(role, f"CH{ch}_Strap_{k}", V, N, F)
        HV, _ = parts[f"CH{ch}_Hook_{k}"]
        add_band(role, f"CH{ch}_Hook_{k}", *CL.hook_patch(loop, z0, z1, float(np.ptp(HV[:, 0]))))
    end_local = np.array([0.0, 0.004, LV[:, 2].min()])
    fit["cables"][str(ch)] = {"end": list(map(float, to_world(p, R, 1, end_local))), "side": list(map(float, -length))}
    print(role, "pose", np.round(p, 3))

# ------------------------------------------------------------------------------------------------ watch on the right wrist
parts = load("NERAM_Watch_Concept.fbx")
SV, _ = parts["Watch_Strap"]
yc = (SV[:, 1].max() + SV[:, 1].min()) / 2
r_in = np.min(np.hypot(SV[:, 0], SV[:, 1] - yc))
s = RIGHT
W, d = SK.W[s], SK.arm_dir[s]
Ax = W - d * 0.062                                   # just proximal of the reshaped wrist (round section)
up = unit(np.array([0, 1.0, 0]) - d * d[1])
side = np.cross(d, up)
AV = ARMV[s]
tt = (AV - Ax) @ d
sl = AV[np.abs(tt) < 0.012]
rel = sl - Ax - np.outer((sl - Ax) @ d, d)
r_arm = float(np.linalg.norm(rel, axis=1).max())
k = (r_arm + 0.0015) / r_in
R = frame(d, up)
p = Ax - up * yc * k
pose("Watch_Concept", p, R, k)
disp_top = parts["Watch_Display"][0][:, 1].max()
fit["watchScreen"] = list(map(float, p + up * (disp_top * k + 0.0007)))
print("watch: arm radius", round(r_arm, 4), "strap inner", round(r_in, 4), "scale", round(k, 3))

# ------------------------------------------------------------------------------------------------ controller on the left side rail
parts = load("NERAM_Bedside_Controller.fbx")
R = frame((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0))     # front (local -Z) faces +X, away from the table; local X along the rail
p = np.array([0.285, -0.06, -0.55])                # clamp centre on Side_Rail_L (x 0.285, y -0.06)
pose("Bedside_Controller", p, R)
ports = {}
for ch in range(1, 5):
    PV, _ = parts[f"BC_Port_CH{ch}"]
    ports[ch] = to_world(p, R, 1, (PV.max(0) + PV.min(0)) / 2)
fit["ports"] = {str(ch): list(map(float, v)) for ch, v in ports.items()}
# display screen: a lit quad on the front of BC_Display (texture controller_screen, made by tools/meshgen/textures.py)
DV, _ = parts["BC_Display"]
x0, y0 = DV[:, 0].min() + 0.003, DV[:, 1].min() + 0.002
x1, y1 = DV[:, 0].max() - 0.003, DV[:, 1].max() - 0.002
zf = DV[:, 2].min() - 0.0004
qv = np.array([[x0, y0, zf], [x1, y0, zf], [x1, y1, zf], [x0, y1, zf]])
qf = np.array([[0, 1, 2], [0, 2, 3]])
if np.cross(qv[1] - qv[0], qv[2] - qv[0])[2] > 0: qf = qf[:, ::-1]          # face the front (local -Z)
fit["parts"].append({"role": "Bedside_Controller", "obj": "BC_Display_Screen", "v": qv.ravel().tolist(), "n": [0, 0, -1.0] * 4,
                     "f": qf.ravel().tolist(), "uv": [0, 0, 1, 0, 1, 1, 0, 1], "mat": "TEX:controller_screen"})

# cables: drop from the port, run under the rail / table, rise at the board or table edge, lie on it to the pad
BT = BOARD_TOP + 0.0055
routes = {
    1: [(0.342, -0.195, -0.50), (0.322, -0.21, -0.30), (0.31, -0.205, 0.05), (0.325, -0.17, 0.34), (0.395, -0.055, 0.445), (0.52, BT, 0.468)],
    2: [(0.342, -0.20, -0.49), (0.31, -0.215, -0.30), (0.18, -0.24, 0.14), (-0.18, -0.24, 0.16), (-0.31, -0.20, 0.26), (-0.325, -0.17, 0.34), (-0.395, -0.055, 0.445), (-0.52, BT, 0.468)],
    3: [(0.342, -0.185, -0.60), (0.325, -0.185, -0.70), (0.30, -0.11, -0.855), (0.282, 0.0045, -0.88), (0.19, 0.0045, -0.865)],
    4: [(0.342, -0.19, -0.585), (0.32, -0.20, -0.68), (0.12, -0.19, -0.90), (-0.18, -0.19, -0.90), (-0.30, -0.11, -0.86), (-0.282, 0.0045, -0.88), (-0.19, 0.0045, -0.865)],
}
for ch in range(1, 5):
    c = fit["cables"][str(ch)]
    end = np.array(c["end"])
    drop = ports[ch] + np.array([0, -0.045, 0])
    if ch <= 2:
        dd = SK.arm_dir[LEFT if ch == 1 else RIGHT]
        pre = end - dd * 0.07 + np.array(c["side"]) * 0.035
        pre[1] = BT
        pts = [ports[ch], drop] + [np.array(q) for q in routes[ch]] + [pre, end]
    else:
        pre = end + np.array([0.0, -0.02, -0.03])
        pre[1] = max(pre[1], 0.0045)
        pts = [ports[ch], drop] + [np.array(q) for q in routes[ch]] + [pre, end]
    c["waypoints"] = [list(map(float, q)) for q in pts]

# Unity JsonUtility has no dictionaries / nested arrays: flatten
out = {"replace": fit["replace"], "note": fit["note"], "boardLift": BOARD_LIFT, "watchScreen": fit["watchScreen"], "meshes": fit["meshes"], "straps": fit["straps"], "parts": fit["parts"], "hooks": fit["hooks"],
       "poses": [dict(role=r, **v) for r, v in fit["poses"].items()],
       "cables": [{"ch": int(ch), "port": fit["ports"][ch], "w": [x for q in c["waypoints"] for x in q]} for ch, c in sorted(fit["cables"].items())]}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(out, separators=(",", ":")))
print("wrote", OUT, OUT.stat().st_size, "bytes;", len(fit["meshes"]), "meshes")
