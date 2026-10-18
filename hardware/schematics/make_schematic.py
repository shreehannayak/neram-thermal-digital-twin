"""One-channel schematic (CH_i; the other three channels are identical): master safety switch, channel fuse, low-side
heater switch with gate pull-down, current sense, two NTC sensors, presence detect and the layer-1 hardware cutoff
latch. Writes hardware/schematics/channel_driver.png and .pdf.  Usage: python hardware/schematics/make_schematic.py

PROVISIONAL topology drafted by Sai for Shreehan (paper design, never built, simulated or tested). Part numbers are the
PROVISIONAL ones in hardware/bom/electrical_bom.csv. Component VALUES are TBD unless a datasheet gives them: nothing
here is an invented electrical value. Proof-of-concept prototype, not a medical device."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle, FancyBboxPatch  # noqa: E402

HERE = Path(__file__).resolve().parent
W, H = 268, 166
fig = plt.figure(figsize=(W / 10, H / 10), dpi=100)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.axis("off"); fig.patch.set_facecolor("white")
INK, LW, FS = "#111", 1.6, 11


def line(*pts, ls="-", c=INK, lw=LW):
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=c, lw=lw, ls=ls, solid_capstyle="round", zorder=2)


def dot(x, y):
    ax.add_patch(Circle((x, y), 0.7, color=INK, zorder=4))


def txt(x, y, s, ha="center", va="center", fs=FS, bold=False, c=INK, **kw):
    ax.text(x, y, s, ha=ha, va=va, fontsize=fs, weight="bold" if bold else "normal", color=c, zorder=5, linespacing=1.3, **kw)


def zig(a, b, n=6, amp=1.3):
    (x1, y1), (x2, y2) = a, b
    import numpy as np
    t = np.linspace(0, 1, 2 * n + 1)
    vert = abs(x2 - x1) < 1e-9
    pts = []
    for i, ti in enumerate(t):
        off = 0 if i in (0, len(t) - 1) else (amp if i % 2 else -amp)
        x = x1 + (x2 - x1) * ti + (off if vert else 0)
        y = y1 + (y2 - y1) * ti + (0 if vert else off)
        pts.append((x, y))
    line(*pts)


def res(a, b, label=None, side="right", ntc=False):
    (x1, y1), (x2, y2) = a, b
    L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    s = min(2.5, L * 0.2)
    p1, p2 = (x1 + ux * s, y1 + uy * s), (x2 - ux * s, y2 - uy * s)
    line(a, p1); line(p2, b); zig(p1, p2)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    if ntc:
        line((mx - 3, my - 3), (mx + 3, my + 3)); line((mx - 3, my - 3), (mx - 4.5, my - 3))
        txt(mx + 4.6, my + 3.6, "−t°", fs=9)
    if label:
        if abs(ux) < 0.5:   # vertical
            txt(mx + (3 if side == "right" else -3), my, label, ha="left" if side == "right" else "right", fs=10)
        else:
            txt(mx, my + (3 if side == "up" else -3.4), label, fs=10)


def fuse(x1, x2, y, label):
    line((x1, y), (x1 + 1.5, y)); line((x2 - 1.5, y), (x2, y))
    ax.add_patch(Rectangle((x1 + 1.5, y - 1.3), x2 - x1 - 3, 2.6, fill=False, ec=INK, lw=LW, zorder=3))
    line((x1 + 1.5, y), (x2 - 1.5, y), lw=1.0)
    txt((x1 + x2) / 2, y + 3.6, label, fs=10)


def contact(x1, x2, y, label):
    a, b = x1 + 2, x2 - 2
    line((x1, y), (a, y)); line((b, y), (x2, y))
    ax.add_patch(Circle((a, y), 0.8, fill=False, ec=INK, lw=LW, zorder=3)); ax.add_patch(Circle((b, y), 0.8, fill=False, ec=INK, lw=LW, zorder=3))
    line((a + 0.6, y + 0.5), (b - 0.3, y + 3.2))
    txt((x1 + x2) / 2, y + 6.6, label, fs=10)


def gnd(x, y):
    line((x, y), (x, y - 1.6)); line((x - 2.2, y - 1.6), (x + 2.2, y - 1.6)); line((x - 1.4, y - 2.5), (x + 1.4, y - 2.5)); line((x - 0.6, y - 3.4), (x + 0.6, y - 3.4))


def supply(x, y, label):
    line((x, y), (x, y + 1.6)); line((x - 2, y + 1.6), (x + 2, y + 1.6)); txt(x, y + 3.4, label, fs=9.5)


def pin(x, y, label):
    ax.add_patch(Circle((x, y), 0.9, fill=True, fc="white", ec=INK, lw=LW, zorder=4)); txt(x - 1.6, y + 2.2, label, ha="right", fs=9)


def box(x0, y0, x1, y1, s, fc="#f7f7f7", fs=10, bold_first=True):
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=INK, lw=LW, zorder=3))
    lines = s.split("\n")
    for i, t in enumerate(lines):
        txt((x0 + x1) / 2, (y0 + y1) / 2 + (len(lines) - 1) * 1.6 - i * 3.2, t, fs=fs, bold=(i == 0 and bold_first))


def mosfet(x, yd, ys, xg, label):
    ym = (yd + ys) / 2; h = (yd - ys)
    line((x, yd), (x, yd - h * 0.2)); line((x, ys), (x, ys + h * 0.2))
    line((x, yd - h * 0.2), (x - 2.6, yd - h * 0.2)); line((x, ys + h * 0.2), (x - 2.6, ys + h * 0.2))
    for a, b in ((0.12, 0.34), (0.42, 0.58), (0.66, 0.88)):
        line((x - 2.6, ys + h * a), (x - 2.6, ys + h * b), lw=2.4)
    line((x - 3.8, ys + h * 0.15), (x - 3.8, ys + h * 0.85), lw=2.2)
    line((xg, ym), (x - 3.8, ym))
    line((x - 2.6, ym), (x, ym)); line((x, ym), (x, ys + h * 0.2))
    ax.add_patch(Polygon([(x - 2.5, ym), (x - 1.0, ym + 0.9), (x - 1.0, ym - 0.9)], color=INK, zorder=4))
    txt(x + 2, ym, label, ha="left", fs=10)


def comparator(x0, yc, w, h, label):
    ax.add_patch(Polygon([(x0, yc + h / 2), (x0, yc - h / 2), (x0 + w, yc)], closed=True, fill=True, fc="#fbeeee", ec=INK, lw=LW, zorder=3))
    txt(x0 + 1.6, yc + h / 4, "−", fs=11); txt(x0 + 1.6, yc - h / 4, "+", fs=11)
    txt(x0 + w / 2 - 1, yc - h / 2 - 2.6, label, fs=9.5)


def button(x, y1, y2, label):
    line((x, y1), (x, y1 - 1.5)); line((x, y2), (x, y2 + 1.5))
    ax.add_patch(Circle((x, y1 - 1.5), 0.6, fill=False, ec=INK, lw=LW)); ax.add_patch(Circle((x, y2 + 1.5), 0.6, fill=False, ec=INK, lw=LW))
    xm = x - 2.2; line((xm, y1 - 1.2), (xm, y2 + 1.2)); line((xm - 1.5, (y1 + y2) / 2), (xm, (y1 + y2) / 2))
    txt(x + 2.2, (y1 + y2) / 2, label, ha="left", fs=9.5)


# ---------------------------------------------------------------- title
txt(4, 160, "NERAM one-channel schematic: heater channel CH_i with master switch, current sense and layer-1 hardware cutoff",
    ha="left", fs=16, bold=True)
txt(4, 154.5, "PROVISIONAL topology (Sai draft for Shreehan, 18 Oct 2026). Paper design: not built, not simulated, not tested. "
              "Parts from bom/electrical_bom.csv; every value marked TBD is unsourced and must not be guessed.", ha="left", fs=11)

# ---------------------------------------------------------------- MCU block
box(6, 30, 40, 134, "MCU board (layer 2)\nNUCLEO-G474RE\n(PROVISIONAL)\n\nPins are high-Z\nduring reset and\nafter a watchdog\nreset", fc="#fbf0d6")
pins_mcu = {"PWM_i": 112, "I_sense_i (ADC)": 86, "T_A_i (ADC)": 72, "T_B_i (ADC)": 56, "presence_i (GPIO)": 40}
for name, y in pins_mcu.items():
    txt(41, y + 2, name, ha="left", fs=9.5)
txt(41, 35, "master_enable (GPIO)", ha="left", fs=9.5)

# ---------------------------------------------------------------- power path
YR = 138
txt(44, YR + 3.2, "+24 V bus (v_bus_V)\nfrom MPM-65-24ST", ha="left", fs=9.5)
line((44, YR), (58, YR)); contact(58, 72, YR, "K1 (NO)\nmaster switch,\nshared CH1-CH4")
line((72, YR), (78, YR)); dot(78, YR); line((78, YR), (78, YR + 6)); txt(79.5, YR + 6, "to CH2-CH4\n(same as CH_i)", ha="left", fs=9)
line((78, YR), (86, YR)); fuse(86, 100, YR, "F_i\nfuse_ch_A (TBD)")
line((100, YR), (180, YR))
XJ = 180
for lbl, y in (("J_i.1 heater +", YR), ("J_i.2 heater −", 116), ("J_i.3 sensor A", 72), ("J_i.4 A return", 62),
               ("J_i.5 sensor B", 56), ("J_i.6 B return", 46), ("J_i.7 presence", 40), ("J_i.8 presence rtn", 32)):
    pin(XJ, y, lbl)
txt(XJ - 2, YR + 8, "J_i: M12 8-pin A-coded\n(2 A, 30 V per contact)", ha="right", fs=9)
# module (dashed)
ax.add_patch(Rectangle((185, 24), 34, 122, fill=False, ec="#a86420", lw=1.6, ls=(0, (5, 3)), zorder=1))
txt(202, 149.5, "Heater module (CH_i)", fs=10.5, bold=True, c="#a86420")
line((XJ, YR), (202, YR)); res((202, YR), (202, 116), "R_H heater\nOmega KHLVA\nR, W: TBD", side="left")
line((202, 116), (XJ, 116))
line((XJ, 72), (202, 72)); res((202, 72), (202, 62), "NTC_A", ntc=True); line((202, 62), (XJ, 62))
line((XJ, 56), (202, 56)); res((202, 56), (202, 46), "NTC_B", ntc=True); line((202, 46), (XJ, 46))
txt(202, 86, "TDK NTCG163JX103DTDS\n10 kΩ, B 3435 K\n(on flex tails)", fs=8.5)
line((XJ, 40), (196, 40), (196, 32), (XJ, 32)); txt(198, 36, "link in plug", ha="left", fs=8.5)

# low-side switch, shunt, current sense
QX = 150
line((XJ, 116), (QX, 116)); mosfet(QX, 116, 106, 128, "Q_i  IRLML6344\n30 V, 5.0 A\n(low side)")
line((QX, 106), (QX, 104)); res((QX, 104), (QX, 96), "R_S shunt (TBD,\nsized for i_over_A)", side="left")
line((QX, 96), (QX, 94))
YG = 94
line((112, YG), (QX, YG)); gnd(131, YG)
line((40, 112), (96, 112)); res((96, 112), (112, 112), "R_G (TBD)", side="up"); line((112, 112), (131, 112)); dot(120, 112)
res((120, 112), (120, YG), "R_PD (TBD)\ngate pull-down:\nQ_i OFF by default", side="left")
dot(120, YG); line((112, YG), (120, YG))
# INA180 box right of shunt
box(160, 97, 172, 105, "U2\nINA180A2", fs=8.5)
line((QX, 104), (QX + 3, 104), (QX + 3, 103), (160, 103)); dot(QX, 104)
line((QX, 96), (QX + 3, 96), (QX + 3, 99), (160, 99)); dot(QX, 96)
txt(158.6, 103.8, "+", fs=8); txt(158.6, 99.8, "−", fs=8)
line((166, 97), (166, 86), (40, 86)); txt(105, 88, "50 V/V × shunt voltage to ADC (firmware: i_open_max_A, i_over_A, i_stuck_A; TBD)", fs=9)
supply(166, 105, "3.3 V")

# sensors: dividers
line((40, 72), (XJ, 72)); res((110, 82 - 2), (110, 72), None); dot(110, 72)
txt(112, 77, "R_A (TBD)", ha="left", fs=9.5)
supply(110, 80, "3.3 V")
line((XJ, 62), (170, 62)); gnd(170, 62)
line((40, 56), (XJ, 56)); res((100, 64), (100, 56), None); dot(100, 56); supply(100, 64, "3.3 V"); txt(102, 61, "R_B (TBD)", ha="left", fs=9.5)
line((XJ, 46), (170, 46)); gnd(170, 46)
line((40, 40), (XJ, 40)); res((90, 48), (90, 40), None); dot(90, 40); supply(90, 48, "3.3 V"); txt(92, 45, "R_P pull-up (TBD)", ha="left", fs=9.5)
line((XJ, 32), (170, 32)); gnd(170, 32)
txt(140, 66.5, "open or short reads out of range → invalid (0x7FFF), never a plausible temperature", fs=9)

# ---------------------------------------------------------------- layer-1 cutoff (bottom band)
ax.add_patch(Rectangle((60, 2), 120, 25, fill=True, fc="#fff6f4", ec="#b2402f", lw=1.2, ls=(0, (4, 3)), zorder=0))
txt(62, 24.6, "Layer 1: hardware cutoff (no firmware)", ha="left", fs=10, bold=True, c="#b2402f")
line((100, 56), (100, 18)); comparator(100, 15, 13, 10, "U3 LM393 (1/2)")
line((100, 18), (101, 18))
line((86, 12), (100, 12)); txt(85, 12, "V_ref set for\nt_hw_cutoff_degC\n(TBD)", ha="right", fs=9)
txt(97.8, 20.5, "NTC_B node", ha="right", fs=8.5)
box(120, 8, 134, 20, "Latch\nS: trip\nR: RESET", fs=8.5)
line((113, 15), (120, 15))
button(127, 8, 4.5, "") ; line((127, 3), (127, 2.6)); gnd(127, 3.4)
txt(129.5, 5.6, "RESET\n(manual)", ha="left", fs=8.5)
box(140, 9, 152, 21, "AND\nOK and\nenable", fs=8.5)
line((134, 16), (140, 16)); txt(137, 18, "OK", fs=8)
line((40, 33), (154, 33), (154, 23), (146, 23), (146, 21)); txt(60, 35, "master_enable (pull-down: 0 = K1 open)", ha="left", fs=9)
box(156, 9, 166, 21, "Q_K\ncoil\ndriver\n(TBD)", fs=8)
line((152, 15), (156, 15))
# coil
ax.add_patch(Rectangle((169, 10), 6, 10, fill=False, ec=INK, lw=LW, zorder=3)); line((169, 10), (175, 20))
line((166, 15), (169, 15)); txt(172, 22.4, "K1 coil", fs=9)
line((175, 15), (177, 15), (177, 17)); txt(177, 19.6, "24 V", fs=9)
line((63, 126), (63, 132), ls=(0, (2, 2)), lw=1.0); txt(64, 128, "K1 mechanical link (coil below)", ha="left", fs=8.5, c="#555")

# ---------------------------------------------------------------- notes (right column)
notes = [
    ("Default-off (all must hold with no firmware)", True),
    ("• K1 is normally open: no coil current → no heater power", False),
    ("• master_enable has a pull-down; MCU pins are high-Z in reset", False),
    ("• R_PD holds Q_i off when PWM_i floats", False),
    ("• A cutoff trip latches until the manual RESET", False),
    ("", False),
    ("Who can remove heater power", True),
    ("• Layer 1: comparator → latch → K1 opens", False),
    ("• Layer 2: MCU sets PWM_i = 0 and master_enable = 0;", False),
    ("   watchdog reset → pins high-Z → same result", False),
    ("• Layer 3: controller sends Heat_i = 0 (via the MCU)", False),
    ("", False),
    ("Stuck-on driver (Q_i shorted)", True),
    ("• current while commanded off → firmware opens K1;", False),
    ("   over-temperature → layer-1 cutoff opens K1", False),
    ("", False),
    ("Open items (owner Shreehan)", True),
    ("• All values marked TBD; shunt and V_ref from i_over_A", False),
    ("   and t_hw_cutoff_degC once those are sourced", False),
    ("• The 8 contacts are all used (heater 2, A 2, B 2,", False),
    ("   presence 2), so the cutoff reads the NTC_B divider;", False),
    ("   a buffer may be needed so the ADC and the", False),
    ("   comparator do not load each other", False),
    ("• Q_i: 30 V rating on a 24 V bus (check transients)", False),
    ("• Flyback/snubber for K1 coil; fuse rating", False),
    ("• Output state of the Nucleo pins at reset: verify", False),
]
y = 140
for s, b in notes:
    txt(224, y, s, ha="left", fs=9.6 if not b else 10.2, bold=b, c="#b2402f" if b else INK); y -= 4.1
txt(224, 8, "Proof-of-concept prototype, not a medical device.\nNo hardware has been built. Standards are design\nreferences only; no compliance is claimed.",
    ha="left", va="bottom", fs=9.5, c="#444")

fig.savefig(HERE / "channel_driver.png", dpi=100, facecolor="white")
fig.savefig(HERE / "channel_driver.pdf", facecolor="white")
print("wrote channel_driver.png / .pdf")
