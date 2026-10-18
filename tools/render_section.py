"""R08 (plan section U): sensor-pocket section of Neharika's CH1 hand module (Unity-ready FBX, shapes as exported), cut through the
centre of CH1_Sensor_A by the plane z = const. Thicknesses are measured from the cut, not typed in.
Usage: python tools/render_section.py [hand_module.fbx] [out.png]   (needs git-lfs files, numpy, matplotlib, Pillow)"""
import sys, json
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); import fbxread  # noqa: E402
FBX = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "cad/exports/unity/NERAM_Left_Hand_Module.fbx"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "cad/renders/R08_sensor_pocket_section.png"
P = fbxread.load(FBX)
ORDER = ["CH1_Liner", "CH1_Heater", "CH1_Sensor_A", "CH1_Insulation", "CH1_Shell"]
COL = {"CH1_Liner": "#d9c7a3", "CH1_Heater": "#8a3b1e", "CH1_Sensor_A": "#2bb5c9", "CH1_Insulation": "#e8e6df", "CH1_Shell": "#a9bcd6"}
NAME = {"CH1_Liner": "Liner (skin side)", "CH1_Heater": "Heater film", "CH1_Sensor_A": "Sensor A", "CH1_Insulation": "Insulation", "CH1_Shell": "Shell"}
SA = P["CH1_Sensor_A"][0]; zc = float((SA[:, 2].min() + SA[:, 2].max()) / 2); xc = float((SA[:, 0].min() + SA[:, 0].max()) / 2)

def cut(V, F, z):
    segs = []
    for tri in F:
        p = V[tri]; d = p[:, 2] - z; pts = []
        for i in range(3):
            a, b = p[i], p[(i + 1) % 3]; da, db = d[i], d[(i + 1) % 3]
            if (da < 0) != (db < 0): t = da / (da - db); pts.append(a + t * (b - a))
        if len(pts) == 2: segs.append((pts[0][[0, 1]], pts[1][[0, 1]]))
    return segs

def loops(segs, tol=1e-7):
    key = lambda q: (round(q[0] / tol), round(q[1] / tol)) if False else (round(q[0], 6), round(q[1], 6))
    adj = {}
    for a, b in segs:
        ka, kb = key(a), key(b)
        if ka == kb: continue
        adj.setdefault(ka, []).append(kb); adj.setdefault(kb, []).append(ka)
    seen = set(); out = []
    for s in list(adj):
        if s in seen: continue
        loop = [s]; seen.add(s); prev = None; cur = s
        while True:
            nx = [n for n in adj[cur] if n != prev and n not in seen]
            if not nx: break
            prev, cur = cur, nx[0]; seen.add(cur); loop.append(cur)
        if len(loop) > 2: out.append(np.array(loop))
    return out

def ys_at(segs, x):
    ys = []
    for a, b in segs:
        if (a[0] - x) * (b[0] - x) < 0: t = (x - a[0]) / (b[0] - a[0]); ys.append(a[1] + t * (b[1] - a[1]))
    return sorted(ys)

S = {n: cut(*P[n], zc) for n in ORDER}; L = {n: loops(S[n]) for n in ORDER}
meas = {}
for x, tag in ((xc, "at Sensor A"), (-30.0e-3, "away from sensor")):
    meas[tag] = {n: [round(y * 1000, 2) for y in ys_at(S[n], x)] for n in ORDER}
print(json.dumps({"z_cut_mm": round(zc * 1000, 1), "x_sensor_mm": round(xc * 1000, 1), "y_crossings_mm": meas}, indent=1))

fig = plt.figure(figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor("white")
fig.text(0.02, 0.955, "R08  Sensor-pocket section, CH1 hand module (left)", fontsize=26, weight="bold")
fig.text(0.02, 0.918, f"Section plane through the centre of CH1_Sensor_A (z = {zc*1000:.1f} mm in module coordinates). Geometry: Neharika's Fusion export (Unity-ready copy, shapes unchanged). "
         "All dimensions measured from the cut.", fontsize=13, color="#333")
def draw(ax, xlim, ylim, scale_note):
    for n in ORDER:
        for lp in L[n]:
            ax.add_patch(Polygon(lp * 1000, closed=True, fc=COL[n], ec="#222", lw=0.8, alpha=0.95 if n != "CH1_Shell" else 0.55, zorder={"CH1_Liner": 2, "CH1_Insulation": 3, "CH1_Shell": 1, "CH1_Heater": 5, "CH1_Sensor_A": 6}[n]))
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal"); ax.set_xlabel("x across the palm (mm)"); ax.set_ylabel("y from skin face (mm)")
    ax.axhspan(ylim[0], 0, color="#f3d9c4", zorder=0); ax.text(xlim[0] + 0.3 * (xlim[1] - xlim[0]) / 25, ylim[0] / 2, "skin (palm)", va="center", fontsize=11, color="#7a4a2a")
    ax.set_title(scale_note, fontsize=13, loc="left"); ax.grid(alpha=0.25)
ax1 = fig.add_axes([0.04, 0.60, 0.92, 0.27]); draw(ax1, (-62, 62), (-3, 12), "Full width (true scale)")
ax1.add_patch(Rectangle((xc * 1000 - 9, -1.5), 22, 12, fill=False, ec="#d33", lw=2, ls="--")); ax1.text(xc * 1000 + 14, 10.5, "detail", color="#d33", fontsize=12)
ax2 = fig.add_axes([0.04, 0.09, 0.55, 0.45]); draw(ax2, (xc * 1000 - 9, xc * 1000 + 18), (-1.5, 10.5), "Detail at Sensor A (true proportions, enlarged)")
# dimensions from the measured crossings at the sensor centre and away from it
def dim(ax, x, y0, y1, txt, side=1):
    ax.annotate("", (x, y0), (x, y1), arrowprops=dict(arrowstyle="<->", lw=1.4, color="#111"), zorder=30)
    ax.text(x + 0.35 * side, (y0 + y1) / 2, txt, va="center", ha="left" if side > 0 else "right", fontsize=12, zorder=30,
            bbox=dict(fc="white", ec="none", alpha=0.85, pad=1))
m = meas["at Sensor A"]
xs = xc * 1000
if len(m["CH1_Sensor_A"]) >= 2: dim(ax2, xs - 3.0, m["CH1_Sensor_A"][0], m["CH1_Sensor_A"][-1], f"sensor {m['CH1_Sensor_A'][-1]-m['CH1_Sensor_A'][0]:.1f}", -1)
if len(m["CH1_Liner"]) >= 2: dim(ax2, xs + 3.0, m["CH1_Liner"][0], m["CH1_Liner"][-1], f"liner {m['CH1_Liner'][-1]-m['CH1_Liner'][0]:.1f}")
mw = meas["away from sensor"]
for n, x0 in (("CH1_Heater", xs + 7.5), ("CH1_Insulation", xs + 11.0)):
    yy = ys_at(S[n], (xs + 9) / 1000) or mw[n]
    yy = [round(v * 1000, 2) for v in yy] if yy and abs(yy[0]) < 1 else yy
    if len(yy) >= 2: dim(ax2, x0, yy[0], yy[-1], f"{NAME[n].split()[0].lower()} {yy[-1]-yy[0]:.1f}")
sh = ys_at(S["CH1_Shell"], (xs + 9) / 1000)
if sh: dim(ax2, xs + 14.8, 0, round(max(sh) * 1000, 2), f"overall {max(sh)*1000:.1f}")
# legend + notes
ax3 = fig.add_axes([0.62, 0.09, 0.36, 0.45]); ax3.axis("off")
y = 0.97
for n in ORDER:
    ax3.add_patch(Rectangle((0.0, y - 0.045), 0.06, 0.05, fc=COL[n], ec="#222", transform=ax3.transAxes)); 
    c = mw[n] if mw[n] else m[n]
    rng = f"{c[0]:.1f}–{c[-1]:.1f} mm" if len(c) >= 2 else "—"
    ax3.text(0.09, y - 0.02, f"{NAME[n]}", fontsize=15, weight="bold", va="center", transform=ax3.transAxes)
    ax3.text(0.55, y - 0.02, f"y = {rng}", fontsize=14, va="center", transform=ax3.transAxes); y -= 0.085
notes = ["y-ranges measured on the cut: Sensor A at x = %.1f mm,\n   the other layers at x = \u221230 mm." % xs,
         "Sensor A (10 \u00d7 10 \u00d7 0.8 mm) sits on the liner in a recess\n   under the heater film (film 3.3\u20133.5 mm over the sensor).",
         "Shell: cap at 7.0\u20139.0 mm, walls down to 2.0 mm at the rim.",
         "CAD check: insulation starts at 3.0 mm, the heater film ends\n   at 3.5 mm \u2192 0.5 mm overlap in the export (for Neharika).",
         "CAD geometry only: no thermal or electrical value is implied."]
for t in notes:
    ax3.text(0.0, y - 0.03, "\u2022 " + t, fontsize=13, va="top", transform=ax3.transAxes)
    y -= 0.135 if chr(10) in t else 0.075
fig.text(0.5, 0.03, "NERAM proof-of-concept prototype — not a medical device. No hardware has been built.", ha="center", fontsize=15, weight="bold")
fig.text(0.5, 0.008, "CAD: Neharika (Fusion export). Section drawn by tools/render_section.py from the Unity-ready FBX.", ha="center", fontsize=11, color="#444")
fig.savefig(OUT, dpi=100, facecolor="white"); from PIL import Image as _I; _I.open(OUT).convert("RGB").save(OUT); print("saved", OUT)
