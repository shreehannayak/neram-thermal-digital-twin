"""Operating theatre environment, OR table, bedside controller and theatre equipment props (visual only).

Room: floor y = -0.85 (table-top 0.85 m above the floor), ceiling y = 2.15, x in [-3.4, 3.4], z in [-4.0, 3.3].
Equipment screens carry 'demonstration prop - no data' textures: they never show readings.
"""
from __future__ import annotations

import math

import numpy as np

from geom import (Mesh, box, cylinder, lathe, merge, quad, rot_x, rot_y, rot_z, rotation_between, rounded_box, sphere,
                  torus, tube)

FLOOR = -0.85
CEIL = 2.15
XW, ZF, ZH = 3.4, -4.0, 3.3


def T(m: Mesh, R=None, t=(0, 0, 0)):
    return m.transformed(R=R, t=t)


class Placer:
    """Builds props in a local frame (front = local -Z) and places them with yaw + position."""

    def __init__(self, sc, parent, origin, yaw=0.0):
        self.sc, self.parent = sc, parent
        self.R = rot_y(yaw)
        self.o = np.asarray(origin, float)

    def add(self, name, mesh, material):
        self.sc.add(self.parent, name, mesh.transformed(R=self.R, t=self.o), material)

    def world(self, p):
        return self.o + self.R @ np.asarray(p, float)


# ----------------------------------------------------------------------------------------------- room shell
def build_room(sc):
    p = sc.node("OT_Room", flags="static")
    floor = box((2 * XW, 0.02, ZH - ZF), center=(0, FLOOR - 0.01, (ZH + ZF) / 2))
    floor.UV = np.stack([floor.V[:, 0] / 1.2, floor.V[:, 2] / 1.2], 1)
    sc.add(p, "Floor", floor, "MAT_Floor")
    # walls (inner faces matter; boxes 10 cm thick)
    H = CEIL - FLOOR
    yc = (CEIL + FLOOR) / 2
    walls = {
        "Wall_Head": box((2 * XW, H, 0.1), center=(0, yc, ZH + 0.05)),
        "Wall_Foot": box((2 * XW, H, 0.1), center=(0, yc, ZF - 0.05)),
        "Wall_Left": box((0.1, H, ZH - ZF), center=(XW + 0.05, yc, (ZH + ZF) / 2)),
        "Wall_Right": box((0.1, H, ZH - ZF), center=(-XW - 0.05, yc, (ZH + ZF) / 2)),
    }
    for k, m in walls.items():
        sc.add(p, k, m, "MAT_Wall")
    ceil = box((2 * XW, 0.06, ZH - ZF), center=(0, CEIL + 0.03, (ZH + ZF) / 2))
    sc.add(p, "Ceiling", ceil, "MAT_Ceiling")
    # skirting + bumper rails
    for k, (c, s) in {
        "Head": ((0, FLOOR + 0.06, ZH - 0.01), (2 * XW, 0.12, 0.02)), "Foot": ((0, FLOOR + 0.06, ZF + 0.01), (2 * XW, 0.12, 0.02)),
        "Left": ((XW - 0.01, FLOOR + 0.06, (ZH + ZF) / 2), (0.02, 0.12, ZH - ZF)), "Right": ((-XW + 0.01, FLOOR + 0.06, (ZH + ZF) / 2), (0.02, 0.12, ZH - ZF)),
    }.items():
        sc.add(p, "Skirting_" + k, box(s, center=c), "MAT_WallSkirt")
    for k, c, s in (("Head", (0, 0.05, ZH - 0.03), (2 * XW - 0.2, 0.12, 0.05)), ("Left", (XW - 0.03, 0.05, -0.3), (0.05, 0.12, 5.6)), ("Right", (-XW + 0.03, 0.05, -0.3), (0.05, 0.12, 5.6))):
        sc.add(p, "Bumper_" + k, rounded_box(s, 0.02, center=c), "MAT_WallRail")
    # wall panel seams (subtle vertical strips)
    for x in np.arange(-XW + 1.1, XW, 1.1):
        sc.add(p, f"Seam_Head_{x:+.1f}", box((0.012, H - 0.3, 0.006), center=(x, yc + 0.1, ZH - 0.003)), "MAT_WallSkirt")
    # laminar-flow ceiling field above the table + ceiling light panels
    sc.add(p, "Laminar_Flow_Panel", box((2.6, 0.02, 3.2), center=(0, CEIL - 0.01, 0.0)), "MAT_CeilingPanel")
    sc.add(p, "Laminar_Flow_Frame", merge([box((2.7, 0.03, 0.05), center=(0, CEIL - 0.015, z)) for z in (-1.625, 1.625)] + [box((0.05, 0.03, 3.3), center=(x, CEIL - 0.015, 0)) for x in (-1.325, 1.325)]), "MAT_MetalWhite")
    for x, z in ((-2.3, -2.4), (2.3, -2.4), (-2.3, 2.2), (2.3, 2.2), (0, -3.0)):
        sc.add(p, f"Ceiling_Light_{x:+.1f}_{z:+.1f}", box((1.0, 0.02, 0.5), center=(x, CEIL - 0.01, z)), "MAT_CeilingLight")
    # door (patient's right wall) and scrub window (left wall)
    sc.add(p, "Door_Frame", merge([box((0.08, 2.2, 0.08), center=(-XW + 0.04, FLOOR + 1.1, z)) for z in (-2.45, -0.75)] + [box((0.08, 0.08, 1.78), center=(-XW + 0.04, FLOOR + 2.2, -1.6))]), "MAT_MetalWhite")
    sc.add(p, "Door_Panel", rounded_box((0.05, 2.12, 1.62), 0.01, center=(-XW + 0.1, FLOOR + 1.06, -1.6)), "MAT_Door")
    sc.add(p, "Door_Window", box((0.012, 0.5, 0.36), center=(-XW + 0.128, FLOOR + 1.55, -1.6)), "MAT_GlassDark")
    sc.add(p, "Door_Handle", tube([(-XW + 0.14, FLOOR + 0.85, -2.2), (-XW + 0.17, FLOOR + 0.85, -2.2), (-XW + 0.17, FLOOR + 1.3, -2.2), (-XW + 0.14, FLOOR + 1.3, -2.2)], 0.012, 10), "MAT_Metal")
    sc.add(p, "Scrub_Window", box((0.02, 0.9, 1.6), center=(XW - 0.012, FLOOR + 1.55, -2.2)), "MAT_GlassDark")
    sc.add(p, "Scrub_Window_Frame", merge([box((0.04, 0.05, 1.7), center=(XW - 0.02, FLOOR + 1.55 + dy, -2.2)) for dy in (-0.475, 0.475)] + [box((0.04, 1.0, 0.05), center=(XW - 0.02, FLOOR + 1.55, -2.2 + dz)) for dz in (-0.825, 0.825)]), "MAT_MetalWhite")
    # head wall: dark wall display (off), medical gas panel, cabinets, wall rail with suction
    sc.add(p, "Wall_Display_Frame", rounded_box((1.5, 0.88, 0.05), 0.012, center=(0.0, 1.25, ZH - 0.03)), "MAT_EquipDark")
    sc.add(p, "Wall_Display_Glass", quad(1.42, 0.8, center=(0.0, 1.25, ZH - 0.056), normal=(0, 0, -1)), "MAT_ScreenOff")
    sc.add(p, "Gas_Panel", rounded_box((0.78, 0.30, 0.04), 0.012, center=(-1.0, 0.55, ZH - 0.025)), "MAT_PanelWhite")
    sc.add(p, "Gas_Panel_Label", quad(0.74, 0.245, center=(-1.0, 0.55, ZH - 0.0465), normal=(0, 0, -1)), "TEX:gas_panel")
    outlets = merge([cylinder(0.022, 0.03, center=(-1.0 + dx, 0.62, ZH - 0.06), R=rot_x(90), segments=20, bevel=0.003) for dx in (-0.243, 0.0, 0.243)])
    sc.add(p, "Gas_Outlets", outlets, "MAT_Metal")
    for i, x0 in enumerate((1.45, 2.25)):
        sc.add(p, f"Cabinet_{i}", rounded_box((0.76, 0.9, 0.36), 0.015, center=(x0, 1.2, ZH - 0.18)), "MAT_PanelWhite")
        sc.add(p, f"Cabinet_{i}_Glass", box((0.66, 0.78, 0.01), center=(x0, 1.2, ZH - 0.365)), "MAT_GlassDark")
        sc.add(p, f"Cabinet_{i}_Base", rounded_box((0.76, 0.85, 0.5), 0.015, center=(x0, FLOOR + 0.425, ZH - 0.25)), "MAT_PanelWhite")
        sc.add(p, f"Cabinet_{i}_Handle", tube([(x0 - 0.15, FLOOR + 0.8, ZH - 0.51), (x0 - 0.15, FLOOR + 0.8, ZH - 0.53), (x0 + 0.15, FLOOR + 0.8, ZH - 0.53), (x0 + 0.15, FLOOR + 0.8, ZH - 0.51)], 0.008, 8), "MAT_Teal")
        sc.add(p, f"Cabinet_{i}_Top", box((0.8, 0.03, 0.54), center=(x0, FLOOR + 0.865, ZH - 0.25)), "MAT_Worktop")
    return p


# ----------------------------------------------------------------------------------------------- OR table
def build_table(sc, parent, arm_dirs, shoulders):
    t = sc.node("OR_Table_PLACEHOLDER", parent, flags="placeholder:OR_Table")
    sc.add(t, "Table_Base", rounded_box((0.62, 0.09, 1.05), 0.03, center=(0, FLOOR + 0.045, -0.15)), "MAT_TableFrame")
    sc.add(t, "Table_Base_Plinth", rounded_box((0.56, 0.02, 0.98), 0.008, center=(0, FLOOR + 0.005, -0.15)), "MAT_EquipDark")
    sc.add(t, "Table_Column", rounded_box((0.30, 0.56, 0.40), 0.04, center=(0, FLOOR + 0.36, -0.1)), "MAT_TableFrame")
    sc.add(t, "Table_Column_Upper", rounded_box((0.26, 0.2, 0.34), 0.035, center=(0, -0.2, -0.1)), "MAT_MetalWhite")
    sc.add(t, "Table_Frame", rounded_box((0.52, 0.045, 1.98), 0.012, center=(0, -0.075, 0.0)), "MAT_TableFrame")
    pads = [("Head", 0.73, 1.0, 0.30), ("Back", 0.16, 0.72, 0.53), ("Seat", -0.33, 0.15, 0.53), ("Legs", -1.0, -0.34, 0.53)]
    for name, z0, z1, w in pads:
        sc.add(t, f"Table_Pad_{name}", rounded_box((w, 0.052, z1 - z0 - 0.006), 0.022, center=(0, -0.026, (z0 + z1) / 2)), "MAT_TablePad")
    for side in (1, -1):
        rail = tube([(side * 0.285, -0.06, z) for z in np.linspace(-0.95, 0.95, 2)], 0.011, 14)
        sc.add(t, f"Side_Rail_{'L' if side > 0 else 'R'}", rail, "MAT_Metal")
        for z in (-0.8, -0.2, 0.4, 0.85):
            sc.add(t, f"Rail_Post_{'L' if side > 0 else 'R'}_{z:+.1f}", rounded_box((0.03, 0.03, 0.03), 0.006, center=(side * 0.272, -0.065, z)), "MAT_MetalWhite")
        d = arm_dirs[side]
        S = shoulders[side]
        c = S + d * 0.42
        R = rotation_between((1, 0, 0), np.array([d[0], 0, d[2]]))
        board = rounded_box((0.70, 0.038, 0.16), 0.016, R=R, center=(c[0], -0.013, c[2]))
        sc.add(t, f"Arm_Board_{'L' if side > 0 else 'R'}", board, "MAT_TablePad")
        frame = rounded_box((0.66, 0.02, 0.12), 0.006, R=R, center=(c[0], -0.043, c[2]))
        sc.add(t, f"Arm_Board_Frame_{'L' if side > 0 else 'R'}", frame, "MAT_TableFrame")
        sc.add(t, f"Arm_Board_Clamp_{'L' if side > 0 else 'R'}", rounded_box((0.06, 0.05, 0.08), 0.01, center=(side * 0.30, -0.06, c[2] + 0.02)), "MAT_Metal")
        strut_top = np.array([c[0] + d[0] * 0.15, -0.053, c[2] + d[2] * 0.15])
        sc.add(t, f"Arm_Board_Strut_{'L' if side > 0 else 'R'}", tube([(side * 0.30, -0.085, c[2] + 0.02), (strut_top[0] * 0.7 + side * 0.09, -0.11, strut_top[2]), strut_top], 0.009, 10), "MAT_Metal")
    # hand control pendant on the patient's right rail
    sc.add(t, "Table_Pendant", rounded_box((0.07, 0.17, 0.03), 0.012, center=(-0.31, -0.24, -0.55)), "MAT_PanelWhite")
    sc.add(t, "Table_Pendant_Cable", tube([(-0.31, -0.155, -0.55), (-0.305, -0.11, -0.54), (-0.29, -0.07, -0.53)], 0.004, 8), "MAT_Cable")
    sc.add(t, "Table_Pendant_Keys", rounded_box((0.05, 0.11, 0.004), 0.003, center=(-0.31, -0.23, -0.566)), "MAT_EquipDark")
    return t


# ----------------------------------------------------------------------------------------------- bedside controller
def build_controller(sc, parent):
    pos = np.array([0.45, -0.035, -0.58])
    R = rot_y(-75)
    c = sc.node("Bedside_Controller_PLACEHOLDER", parent, pos=pos, R=R, region="controller", flags="placeholder:Bedside_Controller")
    L = lambda m: m.transformed(R=R, t=pos)
    W = lambda p: pos + R @ np.asarray(p, float)
    sc.add(c, "BC_Enclosure", L(rounded_box((0.26, 0.18, 0.10), 0.018)), "MAT_Enclosure")
    sc.add(c, "BC_Front_Panel", L(rounded_box((0.245, 0.165, 0.004), 0.012, center=(0, 0, -0.0505))), "MAT_EquipDark")
    sc.add(c, "BC_Display", L(quad(0.15, 0.075, center=(-0.035, 0.03, -0.0535), normal=(0, 0, -1))), "MAT_Indicator")
    ports = []
    for i in range(4):
        sc.add(c, f"BC_LED_CH{i + 1}", L(cylinder(0.006, 0.003, center=(-0.095 + i * 0.04, -0.045, -0.053), R=rot_x(90), segments=16)), "MAT_Indicator")
        port_local = np.array([-0.09 + i * 0.04, -0.092, 0.0])
        sc.add(c, f"BC_Port_CH{i + 1}", L(cylinder(0.009, 0.008, center=port_local, segments=18, bevel=0.0015)), "MAT_Connector")
        ports.append(W(port_local))
    for k, (y, r) in {"Start": (0.045, 0.011), "Stop": (0.005, 0.011), "Reset": (-0.035, 0.009)}.items():
        sc.add(c, f"BC_Button_{k}", L(cylinder(r, 0.006, center=(0.085, y, -0.054), R=rot_x(90), segments=20, bevel=0.0015)), "MAT_Button_" + k)
    sc.add(c, "BC_Mains_Inlet", L(rounded_box((0.03, 0.02, 0.006), 0.003, center=(0.1, -0.05, 0.052))), "MAT_Cable")
    sc.add(c, "BC_Rail_Clamp", L(rounded_box((0.06, 0.05, 0.05), 0.008, center=(0, 0.0, 0.07))), "MAT_Metal")
    sc.add(c, "BC_Label", L(quad(0.08, 0.016, center=(0.0, 0.072, -0.0535), normal=(0, 0, -1))), "TEX:label_controller")
    return c, ports


# ----------------------------------------------------------------------------------------------- surgical lights
def build_surgical_lights(sc):
    p = sc.node("OT_Surgical_Lights", flags="static")
    hub = np.array([0.0, CEIL, 0.15])
    sc.add(p, "Light_Mount_Hub", cylinder(0.11, 0.08, center=hub - [0, 0.04, 0], segments=32, bevel=0.01), "MAT_MetalWhite")
    sc.add(p, "Light_Mount_Column", cylinder(0.045, 0.30, center=hub - [0, 0.23, 0], segments=24), "MAT_MetalWhite")
    heads = []
    for k, (elbow, head, target) in enumerate([
        ((0.62, 1.90, 0.42), (0.78, 1.62, 0.38), (0.0, 0.10, 0.10)),
        ((-0.62, 1.88, -0.20), (-0.80, 1.60, -0.36), (0.0, 0.10, -0.20)),
    ]):
        top = hub - np.array([0, 0.36, 0])
        arm = [top, top + (np.array(elbow) - top) * 0.5 + np.array([0, 0.03, 0]), np.array(elbow)]
        sc.add(p, f"Light_Arm_{k}", tube(arm, 0.032, 16), "MAT_MetalWhite")
        sc.add(p, f"Light_Spring_Arm_{k}", tube([np.array(elbow), np.array(elbow) + (np.array(head) - np.array(elbow)) * 0.5 + [0, 0.06, 0], np.array(head) + [0, 0.10, 0]], 0.024, 14), "MAT_MetalWhite")
        sc.add(p, f"Light_Joint_{k}", sphere(0.04, center=elbow), "MAT_MetalWhite")
        aim = np.array(target) - np.array(head)
        aim /= np.linalg.norm(aim)
        R = rotation_between((0, -1, 0), aim)
        shell = lathe([(0.0, 0.095), (0.12, 0.10), (0.27, 0.07), (0.315, 0.035), (0.31, 0.0), (0.29, -0.006)], 48, creases=(4,), cap=False)
        sc.add(p, f"Light_Head_{k}", shell.transformed(R=R, t=head), "MAT_LightHead")
        sc.add(p, f"Light_Lens_{k}", disc_down(0.285, R, head), "MAT_LightLens")
        cells = []
        for ring, n in ((0.09, 6), (0.17, 12), (0.24, 16)):
            for i in range(n):
                a = 2 * math.pi * i / n
                cells.append(cylinder(0.026, 0.006, center=(ring * math.cos(a), -0.008, ring * math.sin(a)), segments=16, bevel=0.002))
        sc.add(p, f"Light_Cells_{k}", merge(cells).transformed(R=R, t=head), "MAT_LightCell")
        sc.add(p, f"Light_Handle_{k}", cylinder(0.022, 0.12, center=(0, -0.06, 0), segments=20, bevel=0.006).transformed(R=R, t=head), "MAT_Teal")
        heads.append((np.array(head), aim))
    return heads


def disc_down(r, R, center):
    from geom import disc_mesh
    return disc_mesh(r, 48, up=False).transformed(t=(0, -0.0045, 0)).transformed(R=R, t=center)


# ----------------------------------------------------------------------------------------------- anaesthesia workstation
def castors(pl, name, xs, zs, y0=FLOOR):
    parts = []
    for x in xs:
        for z in zs:
            parts.append(cylinder(0.035, 0.025, center=(x, y0 + 0.035, z), R=rot_z(90), segments=18, bevel=0.004))
            parts.append(rounded_box((0.03, 0.05, 0.05), 0.008, center=(x, y0 + 0.085, z)))
    pl.add(name, merge(parts), "MAT_EquipDark")


def build_anaesthesia(sc):
    p = sc.node("OT_Anaesthesia_Workstation", flags="static")
    pl = Placer(sc, p, (-0.98, 0.0, 1.42), yaw=-120)
    y0 = FLOOR
    castors(pl, "AW_Castors", (-0.3, 0.3), (-0.25, 0.25))
    pl.add("AW_Cart", rounded_box((0.74, 0.80, 0.62), 0.03, center=(0, y0 + 0.12 + 0.40, 0)), "MAT_EquipWhite")
    pl.add("AW_Worktop", rounded_box((0.80, 0.04, 0.68), 0.012, center=(0, y0 + 0.94, -0.02)), "MAT_Worktop")
    for i in range(3):
        y = y0 + 0.25 + i * 0.22
        pl.add(f"AW_Drawer_{i}", rounded_box((0.66, 0.19, 0.012), 0.01, center=(0, y, -0.312)), "MAT_PanelWhite")
        pl.add(f"AW_Drawer_Handle_{i}", tube([(-0.12, y + 0.06, -0.32), (-0.12, y + 0.06, -0.335), (0.12, y + 0.06, -0.335), (0.12, y + 0.06, -0.32)], 0.007, 8), "MAT_Teal")
    pl.add("AW_Tower", rounded_box((0.72, 0.64, 0.30), 0.03, center=(0, y0 + 1.28, 0.16)), "MAT_EquipWhite")
    pl.add("AW_Tower_Panel", rounded_box((0.62, 0.30, 0.01), 0.008, center=(0, y0 + 1.22, 0.005)), "MAT_EquipDark")
    pl.add("AW_Flowmeters", merge([cylinder(0.012, 0.22, center=(-0.2 + i * 0.05, y0 + 1.22, 0.0), segments=12) for i in range(4)]), "MAT_GlassClear")
    pl.add("AW_Display_Arm", tube([(0.0, y0 + 1.6, 0.16), (0.0, y0 + 1.72, 0.12), (0.05, y0 + 1.78, 0.02)], 0.02, 12), "MAT_MetalWhite")
    Rm = rot_x(-12)
    pl.add("AW_Display", rounded_box((0.40, 0.30, 0.05), 0.014, R=Rm, center=(0.05, y0 + 1.88, -0.02)), "MAT_EquipDark")
    n_aw = Rm @ np.array([0, 0, -1.0])
    pl.add("AW_Display_Screen", quad(0.36, 0.25, center=np.array([0.05, y0 + 1.88, -0.02]) + n_aw * 0.0255, normal=n_aw, up=Rm @ np.array([0, 1.0, 0])), "TEX:screen_anaesthesia")
    # bellows housing on the worktop
    pl.add("AW_Bellows_Housing", lathe([(0.0, 0.0), (0.09, 0.0), (0.09, 0.24), (0.0, 0.24)], 32, creases=(1, 2), cap=False, center=(0.22, y0 + 0.96, -0.12)), "MAT_GlassClear")
    bel = [(0.0, 0.0)] + [(0.07 + 0.008 * (i % 2), 0.01 + i * 0.016) for i in range(12)] + [(0.0, 0.2)]
    pl.add("AW_Bellows", lathe(bel, 32, cap=False, center=(0.22, y0 + 0.97, -0.12)), "MAT_Bellows")
    # vaporizers on the back bar
    for i, mat in enumerate(("MAT_VapA", "MAT_VapB")):
        x = -0.24 + i * 0.13
        pl.add(f"AW_Vaporizer_{i}", rounded_box((0.10, 0.19, 0.13), 0.015, center=(x, y0 + 1.06, 0.05)), "MAT_EquipWhite")
        pl.add(f"AW_Vaporizer_Dial_{i}", cylinder(0.04, 0.025, center=(x, y0 + 1.17, 0.05), segments=24, bevel=0.004), mat)
    # breathing circuit hoses (parked on the machine, not connected to the patient)
    hose = [(0.25, y0 + 1.0, -0.33), (0.30, y0 + 0.8, -0.45), (0.15, y0 + 0.72, -0.5), (-0.05, y0 + 0.82, -0.42), (-0.2, y0 + 0.98, -0.34)]
    rad = [0.011 + 0.0025 * (math.sin(i * 1.7) > 0) for i in range(60)]
    pts = np.array([np.interp(np.linspace(0, 1, 60), np.linspace(0, 1, len(hose)), np.array(hose)[:, k]) for k in range(3)]).T
    pl.add("AW_Breathing_Circuit", tube(pts, 0.012, 12, radii=rad), "MAT_Hose")
    pl.add("AW_Circuit_Hook", tube([(-0.2, y0 + 0.98, -0.34), (-0.2, y0 + 1.02, -0.32), (-0.2, y0 + 1.02, -0.30)], 0.006, 8), "MAT_Metal")


# ----------------------------------------------------------------------------------------------- patient monitor (ceiling boom)
def build_monitor_boom(sc):
    p = sc.node("OT_Patient_Monitor", flags="static")
    top = np.array([-1.25, CEIL, 0.95])
    sc.add(p, "Boom_Mount", cylinder(0.12, 0.06, center=top - [0, 0.03, 0], segments=32, bevel=0.01), "MAT_MetalWhite")
    sc.add(p, "Boom_Column", cylinder(0.06, 0.45, center=top - [0, 0.285, 0], segments=24), "MAT_MetalWhite")
    elbow = top - [0, 0.5, 0]
    end = np.array([-0.78, 1.62, 1.0])
    sc.add(p, "Boom_Arm", tube([elbow, (elbow + end) / 2 + [0, 0.02, 0], end], 0.045, 16), "MAT_MetalWhite")
    sc.add(p, "Boom_Head", rounded_box((0.18, 0.5, 0.18), 0.03, center=end - [0, 0.25, 0]), "MAT_EquipWhite")
    aim = np.array([0.0, 0.1, 0.2]) - (end - [0, 0.38, 0])
    yaw = math.degrees(math.atan2(aim[0], aim[2]))
    R = rot_y(yaw) @ rot_x(14)
    mc = end - np.array([0, 0.40, 0]) + rot_y(yaw) @ np.array([0, 0, 0.14])
    sc.add(p, "Monitor_Body", rounded_box((0.46, 0.33, 0.06), 0.014, R=R, center=mc), "MAT_EquipDark")
    n = R @ np.array([0, 0, 1.0])
    sc.add(p, "Monitor_Screen", quad(0.42, 0.28, center=mc + n * 0.0305, normal=n, up=R @ np.array([0, 1.0, 0])), "TEX:screen_monitor")
    sc.add(p, "Monitor_Mount", tube([end - [0, 0.36, 0], mc - n * 0.03], 0.02, 10), "MAT_MetalWhite")


# ----------------------------------------------------------------------------------------------- IV stand + infusion pump
def build_iv_pump(sc, access=None, access_dir=None):
    """IV stand with a transparent bag containing visible fluid, drip chamber, infusion pump and tubing routed to an
    access point on the patient's right arm. DEMONSTRATION PROP: no infusion rate or fluid balance is represented."""
    p = sc.node("OT_IV_Stand_Pump", flags="static")
    base = np.array([-0.62, FLOOR, 1.18])
    legs = []
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.3
        tip = base + np.array([0.28 * math.cos(a), 0.07, 0.28 * math.sin(a)])
        legs.append(tube([base + [0, 0.1, 0], tip], 0.014, 10))
        legs.append(cylinder(0.025, 0.02, center=tip - [0, 0.04, 0], R=rot_z(90), segments=14, bevel=0.003))
    sc.add(p, "IV_Base", merge(legs), "MAT_Metal")
    sc.add(p, "IV_Pole", cylinder(0.013, 2.0, center=base + [0, 1.08, 0], segments=16), "MAT_Metal")
    hooks = []
    for a in range(4):
        R = rot_y(a * 90)
        hooks.append(torus(0.05, 0.005, Rm=R @ rot_x(90), center=base + [0, 2.06, 0] + R @ np.array([0.05, 0, 0]), seg_major=16, seg_minor=6, arc=math.pi))
    sc.add(p, "IV_Hooks", merge(hooks), "MAT_Metal")
    bag_c = base + np.array([0.1, 1.80, 0.0])
    sc.add(p, "IV_Bag", sphere(0.07, center=bag_c, scale=(1.0, 1.6, 0.35)), "MAT_IVBag")
    # visible fluid: lower ~70 % of the bag
    fluid = sphere(0.064, center=bag_c - [0, 0.012, 0], scale=(0.97, 1.35, 0.30))
    keep = fluid.V[fluid.F].mean(axis=1)[:, 1] < bag_c[1] + 0.045
    from geom import submesh_by_faces
    sc.add(p, "IV_Fluid", submesh_by_faces(fluid, keep), "MAT_IVLiquid")
    sc.add(p, "IV_Bag_Label", quad(0.05, 0.03, center=bag_c + [0, 0.03, -0.0255], normal=(0, 0, -1)), "TEX:iv_label")
    sc.add(p, "IV_Bag_Port", cylinder(0.008, 0.04, center=bag_c - [0, 0.13, 0], segments=12), "MAT_IVBag")
    ch_c = bag_c - [0, 0.195, 0]
    sc.add(p, "IV_Drip_Chamber", cylinder(0.012, 0.065, center=ch_c, segments=18, bevel=0.003), "MAT_GlassClear")
    sc.add(p, "IV_Drip_Chamber_Fluid", cylinder(0.0105, 0.022, center=ch_c - [0, 0.019, 0], segments=18), "MAT_IVLiquid")
    sc.node("IV_Drop_Anchor", "OT_IV_Stand_Pump", pos=ch_c + [0, 0.026, 0], flags="anchor:ivdrop;fall=0.034")
    pump_c = base + np.array([0.0, 1.22, -0.09])
    sc.add(p, "Pump_Body", rounded_box((0.16, 0.2, 0.13), 0.018, center=pump_c), "MAT_EquipWhite")
    sc.add(p, "Pump_Screen", quad(0.11, 0.07, center=pump_c + [0, 0.035, -0.0655], normal=(0, 0, -1)), "TEX:screen_pump")
    sc.add(p, "Pump_Clamp", rounded_box((0.05, 0.05, 0.06), 0.01, center=base + [0, 1.22, -0.01]), "MAT_Metal")
    line = [ch_c - [0, 0.034, 0], ch_c - [0.01, 0.2, 0.03], pump_c + [0.06, 0.13, -0.03], pump_c + [0.07, 0.05, -0.068], pump_c + [0.07, -0.12, -0.068]]
    if access is not None:
        a = np.asarray(access, float)
        d = np.asarray(access_dir, float)
        hub = a + np.array([0, 0.006, 0]) - d * 0.012
        line += [pump_c + [0.06, -0.35, -0.12], np.array([a[0] - 0.05, 0.02, a[2] + 0.18]), np.array([a[0] - 0.02, a[1] + 0.03, a[2] + 0.08]), hub - d * 0.02 + [0, 0.004, 0], hub]
        sc.add(p, "IV_Cannula_Hub", cylinder(0.0045, 0.016, center=hub, R=rotation_between((0, 1, 0), d), segments=14, bevel=0.001), "MAT_Cannula")
        sc.add(p, "IV_Dressing", rounded_box((0.034, 0.0015, 0.03), 0.0007, center=a + [0, 0.0012, 0]), "MAT_Dressing")
    else:
        line += [pump_c + [0.03, -0.3, -0.05], pump_c + [0.08, -0.42, -0.02]]
    from patient import smooth_polyline
    sc.add(p, "IV_Line", tube(smooth_polyline(line, 6), 0.0022, 6), "MAT_IVBag")


# ----------------------------------------------------------------------------------------------- ventilator (stand-alone)
def build_ventilator(sc):
    p = sc.node("OT_Ventilator", flags="static")
    pl = Placer(sc, p, (-1.75, 0.0, 0.05), yaw=-95)
    castors(pl, "Vent_Castors", (-0.22, 0.22), (-0.22, 0.22))
    pl.add("Vent_Base", rounded_box((0.55, 0.08, 0.55), 0.02, center=(0, FLOOR + 0.15, 0)), "MAT_EquipWhite")
    pl.add("Vent_Pole", cylinder(0.03, 0.75, center=(0, FLOOR + 0.55, 0.12), segments=16), "MAT_Metal")
    pl.add("Vent_Body", rounded_box((0.36, 0.42, 0.30), 0.03, center=(0, FLOOR + 1.1, 0.05)), "MAT_EquipWhite")
    pl.add("Vent_Body_Front", rounded_box((0.30, 0.14, 0.01), 0.006, center=(0, FLOOR + 0.98, -0.103)), "MAT_EquipDark")
    Rm = rot_x(-10)
    pl.add("Vent_Screen_Body", rounded_box((0.34, 0.26, 0.04), 0.012, R=Rm, center=(0, FLOOR + 1.47, 0.0)), "MAT_EquipDark")
    n = Rm @ np.array([0, 0, -1.0])
    pl.add("Vent_Screen", quad(0.31, 0.22, center=np.array([0, FLOOR + 1.47, 0.0]) + n * 0.0205, normal=n, up=Rm @ np.array([0, 1.0, 0])), "TEX:screen_vent")
    pl.add("Vent_Hose", tube([(0.12, FLOOR + 1.0, -0.11), (0.2, FLOOR + 0.85, -0.2), (0.05, FLOOR + 0.8, -0.26), (-0.12, FLOOR + 0.92, -0.12)], 0.011, 10), "MAT_Hose")


# ----------------------------------------------------------------------------------------------- carts
def build_carts(sc):
    p = sc.node("OT_Carts", flags="static")
    # stainless instrument trolley with a sterile drape (patient's left, foot end)
    pl = Placer(sc, p, (1.25, 0.0, -1.35), yaw=15)
    legs = []
    for x in (-0.36, 0.36):
        for z in (-0.24, 0.24):
            legs.append(tube([(x, FLOOR + 0.07, z), (x, FLOOR + 0.92, z)], 0.013, 10))
    pl.add("Trolley_Frame", merge(legs), "MAT_Metal")
    castors(pl, "Trolley_Castors", (-0.36, 0.36), (-0.24, 0.24), FLOOR - 0.03)
    pl.add("Trolley_Shelf", rounded_box((0.78, 0.02, 0.54), 0.006, center=(0, FLOOR + 0.3, 0)), "MAT_Metal")
    pl.add("Trolley_Top", rounded_box((0.80, 0.02, 0.56), 0.006, center=(0, FLOOR + 0.92, 0)), "MAT_Metal")
    drape = merge([box((0.86, 0.006, 0.62), center=(0, FLOOR + 0.934, 0))] + [box((0.006, 0.24, 0.62), center=(sx * 0.433, FLOOR + 0.814, 0)) for sx in (-1, 1)] + [box((0.86, 0.24, 0.006), center=(0, FLOOR + 0.814, sz * 0.313)) for sz in (-1, 1)])
    pl.add("Trolley_Drape", drape, "MAT_Drape")
    for i, (x, z, s) in enumerate(((-0.2, -0.1, (0.18, 0.03, 0.12)), (0.1, 0.08, (0.22, 0.025, 0.1)), (0.25, -0.12, (0.12, 0.04, 0.12)))):
        pl.add(f"Trolley_Tray_{i}", rounded_box(s, 0.006, center=(x, FLOOR + 0.937 + s[1] / 2, z)), "MAT_Metal")
    # supply cart (patient's left, mid room)
    pl2 = Placer(sc, p, (2.75, 0.0, 0.2), yaw=-90)
    castors(pl2, "Supply_Castors", (-0.25, 0.25), (-0.2, 0.2))
    pl2.add("Supply_Body", rounded_box((0.62, 0.92, 0.50), 0.025, center=(0, FLOOR + 0.12 + 0.46, 0)), "MAT_EquipWhite")
    for i in range(5):
        y = FLOOR + 0.22 + i * 0.17
        pl2.add(f"Supply_Drawer_{i}", rounded_box((0.56, 0.15, 0.012), 0.008, center=(0, y, -0.252)), "MAT_PanelWhite")
        pl2.add(f"Supply_Drawer_Tab_{i}", rounded_box((0.18, 0.025, 0.012), 0.006, center=(0, y + 0.05, -0.262)), "MAT_Teal")
    pl2.add("Supply_Top", box((0.66, 0.025, 0.54), center=(0, FLOOR + 1.05, 0)), "MAT_Worktop")
    # waste bin
    sc.add(p, "Waste_Bin", lathe([(0.0, 0.0), (0.16, 0.0), (0.18, 0.5), (0.0, 0.5)], 32, creases=(1, 2), cap=False, center=(1.95, FLOOR, -2.0)), "MAT_EquipWhite")
    sc.add(p, "Waste_Bin_Lid", cylinder(0.185, 0.03, center=(1.95, FLOOR + 0.515, -2.0), segments=32, bevel=0.006), "MAT_Teal")


# ----------------------------------------------------------------------------------------------- suction + O2 cylinders
def build_suction(sc):
    p = sc.node("OT_Suction", flags="static")
    x0, y0, z0 = -2.2, 0.32, ZH - 0.05
    sc.add(p, "Wall_Rail", rounded_box((1.4, 0.03, 0.02), 0.006, center=(x0, y0, z0)), "MAT_Metal")
    sc.add(p, "Suction_Regulator", rounded_box((0.09, 0.14, 0.07), 0.012, center=(x0 + 0.3, y0 + 0.12, z0 - 0.05)), "MAT_EquipWhite")
    sc.add(p, "Suction_Gauge", cylinder(0.035, 0.012, center=(x0 + 0.3, y0 + 0.15, z0 - 0.09), R=rot_x(90), segments=24, bevel=0.003), "MAT_Metal")
    sc.add(p, "Suction_Gauge_Face", quad(0.06, 0.06, center=(x0 + 0.3, y0 + 0.15, z0 - 0.0965), normal=(0, 0, -1)), "TEX:gauge")
    can_c = np.array([x0 - 0.1, y0 - 0.26, z0 - 0.1])
    sc.add(p, "Suction_Canister", lathe([(0.0, 0.0), (0.075, 0.0), (0.08, 0.24), (0.0, 0.24)], 32, creases=(1, 2), cap=False, center=can_c), "MAT_GlassClear")
    sc.add(p, "Suction_Canister_Lid", cylinder(0.085, 0.03, center=can_c + [0, 0.255, 0], segments=32, bevel=0.005), "MAT_SuctionLid")
    sc.add(p, "Suction_Bracket", rounded_box((0.18, 0.04, 0.12), 0.008, center=can_c + [0, 0.27, 0.04]) , "MAT_Metal")
    sc.add(p, "Suction_Tubing", tube([can_c + [0.04, 0.27, 0], can_c + [0.2, 0.38, -0.05], (x0 + 0.3, y0 + 0.05, z0 - 0.06)], 0.006, 8), "MAT_Hose")


def build_o2(sc):
    p = sc.node("OT_O2_Cylinders", flags="static")
    for k, x in enumerate((2.35, 2.62)):
        base = np.array([x, FLOOR + 0.03, ZH - 0.22])
        prof = [(0.0, 0.0), (0.085, 0.0), (0.09, 0.02), (0.09, 0.80), (0.075, 0.88), (0.04, 0.93), (0.022, 0.95), (0.022, 0.98), (0.0, 0.98)]
        body = lathe(prof[:4] + [(0.09, 0.80), (0.0, 0.80)], 40, creases=(1, 3), cap=False, center=base)
        shoulder = lathe([(0.0, 0.80), (0.09, 0.80), (0.075, 0.88), (0.04, 0.93), (0.022, 0.95), (0.022, 0.98), (0.0, 0.98)], 40, creases=(1,), cap=False, center=base)
        sc.add(p, f"O2_Cylinder_{k}_Body", body, "MAT_O2Body")
        sc.add(p, f"O2_Cylinder_{k}_Shoulder", shoulder, "MAT_O2Shoulder")
        band = lathe([(0.0915, 0.52), (0.0915, 0.66)], 40, cap=False, center=base)
        sc.add(p, f"O2_Cylinder_{k}_Label", band, "TEX:o2_label")
        valve = base + np.array([0, 1.0, 0])
        sc.add(p, f"O2_Cylinder_{k}_Valve", rounded_box((0.05, 0.06, 0.05), 0.008, center=valve), "MAT_Brass")
        sc.add(p, f"O2_Cylinder_{k}_Handwheel", torus(0.03, 0.006, center=valve + [0, 0.045, 0], seg_major=24, seg_minor=8), "MAT_EquipDark")
        reg = valve + np.array([0, 0.0, -0.06])
        sc.add(p, f"O2_Cylinder_{k}_Regulator", cylinder(0.022, 0.06, center=reg, R=rot_x(90), segments=18, bevel=0.004), "MAT_Metal")
        sc.add(p, f"O2_Cylinder_{k}_Gauge", cylinder(0.03, 0.014, center=reg + [0, 0.04, -0.01], R=rot_x(90), segments=24, bevel=0.003), "MAT_Metal")
        sc.add(p, f"O2_Cylinder_{k}_Gauge_Face", quad(0.05, 0.05, center=reg + [0, 0.04, -0.0175], normal=(0, 0, -1)), "TEX:gauge")
        # securing straps to the wall bracket
        for h in (0.35, 0.72):
            sc.add(p, f"O2_Cylinder_{k}_Strap_{h:.2f}", torus(0.097, 0.006, center=base + [0, h, 0], seg_major=40, seg_minor=8), "MAT_Strap")
    sc.add(p, "O2_Wall_Bracket", merge([rounded_box((0.62, 0.06, 0.03), 0.01, center=(2.485, FLOOR + 0.03 + h, ZH - 0.035)) for h in (0.35, 0.72)] + [box((0.03, 0.06, 0.12), center=(x, FLOOR + 0.03 + h, ZH - 0.1)) for x in (2.35, 2.62) for h in (0.35, 0.72)]), "MAT_Metal")
    sc.add(p, "O2_Floor_Stand", rounded_box((0.62, 0.03, 0.3), 0.008, center=(2.485, FLOOR + 0.015, ZH - 0.22)), "MAT_EquipDark")
    sc.add(p, "O2_Wall_Sign", quad(0.5, 0.0625, center=(2.485, FLOOR + 1.35, ZH - 0.002), normal=(0, 0, -1)), "TEX:o2_label")
