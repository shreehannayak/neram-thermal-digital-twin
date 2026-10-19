"""KiCad 8 conceptual schematic of ONE heater channel (plan section K / AC: hardware/schematics/channel_driver.kicad_sch).

Same topology as make_schematic.py (the PNG/PDF drawing): master switch K1 (normally open) with coil driver and flyback
diode, channel fuse, low-side logic-level MOSFET with gate resistor and gate pull-down (default OFF), shunt + INA180
current sense, NTC_A / NTC_B dividers, presence detect, layer-1 hardware cutoff (LM393 comparator -> latch -> AND with
master_enable -> K1 coil driver) with a manual RESET, and the MCU header. Nets are joined by net labels.

PROVISIONAL paper design drafted by Sai for Shreehan (19 Oct 2026): never built, simulated or tested. Part numbers are
the PROVISIONAL ones in hardware/bom/electrical_bom.csv; every component VALUE is TBD unless a datasheet gives it.
Symbols are embedded (library "NERAM"), so the file opens in KiCad 8 without extra libraries.
Usage: python hardware/schematics/make_kicad_schematic.py   (writes channel_driver.kicad_sch and channel_driver_netlist.csv)
Open it in KiCad 8 (Eeschema) and use File > Plot > PDF to regenerate a KiCad-drawn PDF.
"""
import csv
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
NS = uuid.UUID("6f1c6a52-6a8e-4f3e-9d1e-2b5a7c3d9e10")
_n = [0]


def uid():
    _n[0] += 1
    return str(uuid.uuid5(NS, str(_n[0])))


ROOT = uid()
F = '(effects (font (size 1.27 1.27)))'
FH = '(effects (font (size 1.27 1.27)) hide)'


def pin(kind, x, y, ang, length, name, num):
    return (f'(pin {kind} line (at {x:.2f} {y:.2f} {ang}) (length {length:.2f}) '
            f'(name "{name}" {F}) (number "{num}" {F}))')


def lib_symbol(name, ref, body, pins, show_names=True, show_numbers=True):
    pn = "" if show_numbers else "(pin_numbers hide) "
    pnm = "(pin_names (offset 0.762))" if show_names else "(pin_names hide)"
    return (f'(symbol "NERAM:{name}" {pn}{pnm} (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
            f'  (property "Reference" "{ref}" (at 0 0 0) {F})\n  (property "Value" "{name}" (at 0 0 0) {F})\n'
            f'  (property "Footprint" "" (at 0 0 0) {FH})\n  (property "Datasheet" "" (at 0 0 0) {FH})\n'
            f'  (property "Description" "" (at 0 0 0) {FH})\n'
            f'  (symbol "{name}_0_1" {body})\n  (symbol "{name}_1_1" {" ".join(pins)}))')


def rect(x1, y1, x2, y2, fill="background"):
    return f'(rectangle (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.254) (type default)) (fill (type {fill})))'


def poly(*pts, fill="none"):
    p = " ".join(f"(xy {x} {y})" for x, y in pts)
    return f'(polyline (pts {p}) (stroke (width 0.254) (type default)) (fill (type {fill})))'


# ------------------------------------------------------------------ symbol library (lib coordinates: y up)
# each entry: lib text, pin map {pin number: (dx, dy)} giving the connection point in lib coordinates
LIB = {}
LIB["R"] = (lib_symbol("R", "R", rect(-1.016, -2.54, 1.016, 2.54, "none"),
                       [pin("passive", 0, 3.81, 270, 1.27, "~", 1), pin("passive", 0, -3.81, 90, 1.27, "~", 2)], False, False),
            {"1": (0, 3.81), "2": (0, -3.81)})
LIB["NTC"] = (lib_symbol("NTC", "TH", rect(-1.016, -2.54, 1.016, 2.54, "none") + poly((-1.9, -2.2), (1.9, 2.2)),
                         [pin("passive", 0, 3.81, 270, 1.27, "~", 1), pin("passive", 0, -3.81, 90, 1.27, "~", 2)], False, False),
              {"1": (0, 3.81), "2": (0, -3.81)})
LIB["Fuse"] = (lib_symbol("Fuse", "F", rect(-2.54, -0.762, 2.54, 0.762, "none") + poly((-2.54, 0), (2.54, 0)),
                          [pin("passive", -3.81, 0, 0, 1.27, "~", 1), pin("passive", 3.81, 0, 180, 1.27, "~", 2)], False, False),
               {"1": (-3.81, 0), "2": (3.81, 0)})
LIB["D"] = (lib_symbol("D", "D", poly((-1.27, 1.27), (-1.27, -1.27), (1.27, 0), (-1.27, 1.27)) + poly((1.27, 1.27), (1.27, -1.27)),
                       [pin("passive", -3.81, 0, 0, 2.54, "A", 2), pin("passive", 3.81, 0, 180, 2.54, "K", 1)], False, True),
            {"1": (3.81, 0), "2": (-3.81, 0)})
LIB["NMOS"] = (lib_symbol("NMOS", "Q", poly((0.762, 2.032), (0.762, -2.032)) + poly((1.524, 2.286), (1.524, 1.27)) +
                          poly((1.524, 0.508), (1.524, -0.508)) + poly((1.524, -1.27), (1.524, -2.286)) +
                          poly((-1.27, 0), (0.762, 0)) + poly((1.524, 1.778), (2.54, 1.778), (2.54, 2.54)) +
                          poly((1.524, -1.778), (2.54, -1.778), (2.54, -2.54)) + poly((1.524, 0), (2.54, 0), (2.54, -1.778)),
                          [pin("input", -3.81, 0, 0, 2.54, "G", 1), pin("passive", 2.54, 5.08, 270, 2.54, "D", 3),
                           pin("passive", 2.54, -5.08, 90, 2.54, "S", 2)], False, True),
               {"G": (-3.81, 0), "D": (2.54, 5.08), "S": (2.54, -5.08)})
LIB["Relay_NO"] = (lib_symbol("Relay_NO", "K", rect(-5.08, -5.08, 5.08, 5.08) + poly((-3.81, 1.27), (-1.27, 1.27)) +
                              poly((1.27, 1.27), (3.302, 2.54)) + poly((-3.81, -2.54), (-1.27, -2.54), (-1.27, -1.27), (1.27, -3.81), (1.27, -2.54), (3.81, -2.54)),
                              [pin("passive", -7.62, 2.54, 0, 2.54, "COM", "11"), pin("passive", 7.62, 2.54, 180, 2.54, "NO", "14"),
                               pin("passive", -7.62, -2.54, 0, 2.54, "A1", "A1"), pin("passive", 7.62, -2.54, 180, 2.54, "A2", "A2")]),
                   {"11": (-7.62, 2.54), "14": (7.62, 2.54), "A1": (-7.62, -2.54), "A2": (7.62, -2.54)})


def ic(name, ref, w, h, left, right, top=(), bottom=()):
    """Box symbol; left/right/top/bottom: lists of (number, name)."""
    pins, pmap = [], {}
    hw, hh = w / 2, h / 2
    for i, (num, nm) in enumerate(left):
        y = hh - 2.54 * (i + 1)
        pins.append(pin("passive", -hw - 2.54, y, 0, 2.54, nm, num)); pmap[num] = (-hw - 2.54, y)
    for i, (num, nm) in enumerate(right):
        y = hh - 2.54 * (i + 1)
        pins.append(pin("passive", hw + 2.54, y, 180, 2.54, nm, num)); pmap[num] = (hw + 2.54, y)
    for i, (num, nm) in enumerate(top):
        x = -hw + 2.54 * (i + 1)
        pins.append(pin("power_in", x, hh + 2.54, 270, 2.54, nm, num)); pmap[num] = (x, hh + 2.54)
    for i, (num, nm) in enumerate(bottom):
        x = -hw + 2.54 * (i + 1)
        pins.append(pin("power_in", x, -hh - 2.54, 90, 2.54, nm, num)); pmap[num] = (x, -hh - 2.54)
    LIB[name] = (lib_symbol(name, ref, rect(-hw, -hh, hw, hh), pins), pmap)


ic("Conn_M12_8", "J", 10.16, 22.86, [("1", "HTR+"), ("2", "HTR-"), ("3", "NTC_A"), ("4", "A_RTN"), ("5", "NTC_B"),
                                    ("6", "B_RTN"), ("7", "PRES"), ("8", "PRES_RTN")], [])
ic("MCU_Header", "J", 12.7, 22.86, [], [("1", "PWM_i"), ("2", "I_SENSE_i"), ("3", "T_A_i"), ("4", "T_B_i"), ("5", "PRES_i"),
                                       ("6", "MASTER_EN"), ("7", "+3V3"), ("8", "GND")])
ic("INA180A2", "U", 10.16, 7.62, [("3", "IN+"), ("4", "IN-")], [("1", "OUT")], top=[("5", "V+")], bottom=[("2", "GND")])
ic("LM393_half", "U", 10.16, 7.62, [("3", "+"), ("2", "-")], [("1", "OUT")], top=[("8", "V+")], bottom=[("4", "GND")])
ic("SR_Latch", "U", 10.16, 7.62, [("1", "S"), ("2", "R")], [("3", "Q")], top=[("5", "VCC")], bottom=[("4", "GND")])
ic("AND2", "U", 10.16, 7.62, [("1", "A"), ("2", "B")], [("4", "Y")], top=[("5", "VCC")], bottom=[("3", "GND")])
ic("SW_Push", "SW", 5.08, 2.54, [("1", "1")], [("2", "2")])

# ------------------------------------------------------------------ placement (schematic coordinates: mm, y down)
items, nets_rows = [], []


def snap(v):
    return round(v / 1.27) * 1.27


def place(lib, ref, value, x, y, nets, footprint="", note=""):
    """nets: {pin number: net name}. Draws a 2.54 mm stub from every pin and puts the net label at its end."""
    x, y = snap(x), snap(y)
    text, pmap = LIB[lib]
    small = lib in ("R", "NTC")
    vx, vy = (x + 3.0, y + 2.5) if small else (x, y + 8.89)
    pins_txt = " ".join(f'(pin "{n}" (uuid "{uid()}"))' for n in pmap)
    items.append(f'(symbol (lib_id "NERAM:{lib}") (at {x:.2f} {y:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom yes) '
                 f'(on_board yes) (dnp no) (uuid "{uid()}")\n'
                 f'  (property "Reference" "{ref}" (at {x + 3.0 if small else x:.2f} {y - 0.5 if small else y - 7.62:.2f} 0) {F})\n'
                 f'  (property "Value" "{value}" (at {vx:.2f} {vy:.2f} 0) {F})\n'
                 f'  (property "Footprint" "{footprint}" (at {x:.2f} {y:.2f} 0) {FH})\n'
                 f'  (property "Datasheet" "" (at {x:.2f} {y:.2f} 0) {FH})\n'
                 f'  (property "Description" "{note}" (at {x:.2f} {y:.2f} 0) {FH})\n'
                 f'  {pins_txt}\n'
                 f'  (instances (project "channel_driver" (path "/{ROOT}" (reference "{ref}") (unit 1)))))')
    for num, net in nets.items():
        dx, dy = pmap[num]
        px, py = x + dx, y - dy                       # lib y up -> schematic y down
        ox = 2.54 if dx > 0.01 else -2.54 if dx < -0.01 else 0.0
        oy = -2.54 if dy > 0.01 and abs(dx) < 0.01 else 2.54 if dy < -0.01 and abs(dx) < 0.01 else 0.0
        lx, ly = px + ox, py + oy
        items.append(f'(wire (pts (xy {px:.2f} {py:.2f}) (xy {lx:.2f} {ly:.2f})) (stroke (width 0) (type default)) (uuid "{uid()}"))')
        just = "left" if ox > 0 else "right" if ox < 0 else "left"
        ang = 0 if oy == 0 else 90
        items.append(f'(label "{net}" (at {lx:.2f} {ly:.2f} {ang}) (fields_autoplaced yes) '
                     f'(effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid "{uid()}"))')
        nets_rows.append((net, ref, num, value))


def note(x, y, s, size=1.27):
    s = s.replace('"', "'")
    items.append(f'(text "{s}" (exclude_from_sim no) (at {x:.2f} {y:.2f} 0) '
                 f'(effects (font (size {size} {size})) (justify left bottom)) (uuid "{uid()}"))')


# power path
place("Relay_NO", "K1", "Relay SPST-NO 24 V coil (TBD)", 60, 40,
      {"11": "VBUS", "14": "VBUS_SW", "A1": "VBUS", "A2": "K1_COIL"}, note="Master safety switch, shared CH1-CH4; NO = default off")
place("D", "D1", "Flyback diode (TBD)", 60, 58, {"1": "VBUS", "2": "K1_COIL"})
place("Fuse", "F1", "fuse_ch_A (TBD)", 95, 37.5, {"1": "VBUS_SW", "2": "HTR_P"})
place("Conn_M12_8", "J1", "M12A-08PFFS-SF8001 (to module CH_i)", 175, 60,
      {"1": "HTR_P", "2": "HTR_N", "3": "NTC_A", "4": "GND", "5": "NTC_B", "6": "GND", "7": "PRES", "8": "GND"})
# heater module side (through J1): heater, two NTCs on flex tails, presence link in the plug
place("R", "R_H", "Heater Omega KHLVA (R, W: TBD)", 215, 50, {"1": "HTR_P", "2": "HTR_N"}, note="In the module")
place("NTC", "TH_A", "NTCG163JX103DTDS 10k", 230, 50, {"1": "NTC_A", "2": "GND"}, note="Sensor A, in the module")
place("NTC", "TH_B", "NTCG163JX103DTDS 10k", 245, 50, {"1": "NTC_B", "2": "GND"}, note="Sensor B, in the module")
place("R", "LNK", "Presence link (in plug)", 260, 50, {"1": "PRES", "2": "GND"})
note(205, 38, "Heater module CH_i (connects through J1)")
# low-side switch and current sense
place("NMOS", "Q1", "IRLML6344TRPBF", 120, 75, {"D": "HTR_N", "G": "GATE", "S": "SHUNT_H"})
place("R", "R_S", "Shunt (TBD, from i_over_A)", 135, 95, {"1": "SHUNT_H", "2": "GND"})
place("R", "R_G", "TBD", 100, 65, {"1": "PWM", "2": "GATE"})
place("R", "R_PD", "TBD (gate pull-down)", 100, 90, {"1": "GATE", "2": "GND"})
place("INA180A2", "U2", "INA180A2IDBVR", 160, 100, {"3": "SHUNT_H", "4": "GND", "1": "I_SENSE", "5": "+3V3", "2": "GND"})
# sensor dividers and presence detect
place("R", "R_A", "TBD", 140, 125, {"1": "+3V3", "2": "NTC_A"})
place("R", "R_B", "TBD", 155, 125, {"1": "+3V3", "2": "NTC_B"})
place("R", "R_P", "TBD (pull-up)", 170, 125, {"1": "+3V3", "2": "PRES"})
# layer-1 hardware cutoff
place("R", "R_REF1", "TBD", 40, 110, {"1": "+3V3", "2": "VREF"})
place("R", "R_REF2", "TBD", 40, 130, {"1": "VREF", "2": "GND"})
place("LM393_half", "U3", "LM393DR (1/2)", 65, 120, {"3": "NTC_B", "2": "VREF", "1": "TRIP", "8": "+3V3", "4": "GND"},
      note="Layer 1: trips at t_hw_cutoff_degC (TBD), no firmware")
place("SR_Latch", "U4", "SR latch (TBD)", 90, 140, {"1": "TRIP", "2": "RESET_N", "3": "OK", "5": "+3V3", "4": "GND"},
      note="Latched until manual RESET")
place("SW_Push", "SW1", "RESET (manual, recessed)", 70, 155, {"1": "RESET_N", "2": "GND"})
place("R", "R_RST", "TBD (pull-up)", 55, 150, {"1": "+3V3", "2": "RESET_N"})
place("AND2", "U5", "74LVC1G08 (TBD)", 115, 140, {"1": "OK", "2": "MASTER_EN", "4": "KDRV", "5": "+3V3", "3": "GND"})
place("R", "R_EN", "TBD (pull-down: 0 = K1 open)", 130, 160, {"1": "MASTER_EN", "2": "GND"})
place("NMOS", "Q2", "Coil driver (TBD)", 140, 140, {"G": "KDRV", "D": "K1_COIL", "S": "GND"})
# MCU header
place("MCU_Header", "J2", "to NUCLEO-G474RE (layer 2)", 30, 70,
      {"1": "PWM", "2": "I_SENSE", "3": "NTC_A", "4": "NTC_B", "5": "PRES", "6": "MASTER_EN", "7": "+3V3", "8": "GND"})

note(15, 15, "NERAM one-channel conceptual schematic (CH_i; CH1-CH4 identical, K1 shared)", 2.0)
note(15, 20, "PROVISIONAL paper design (Sai draft for Shreehan, 19 Oct 2026): not built, not simulated, not tested. Values marked TBD are unsourced.")
note(15, 24, "Default-off: K1 normally open; MASTER_EN pull-down; MCU pins high-Z in reset; R_PD holds Q1 off; cutoff trip latches until RESET.")
note(15, 28, "VBUS = +24 V from MPM-65-24ST (PROVISIONAL). Proof-of-concept prototype, not a medical device; standards are design references only.")
note(185, 125, "Who can remove heater power: layer 1 comparator -> latch -> K1;\nlayer 2 MCU (PWM = 0, MASTER_EN = 0, watchdog -> high-Z);\nlayer 3 supervisory controller (Heat_i = 0).")

lib_txt = "\n".join(v[0] for v in LIB.values())
sch = (f'(kicad_sch (version 20231120) (generator "eeschema") (generator_version "8.0")\n'
       f'(uuid "{ROOT}")\n(paper "A3")\n'
       f'(title_block (title "NERAM channel driver (one channel, conceptual)") (date "2026-10-19") (rev "P1")\n'
       f'  (company "NERAM team, CEG Anna University") (comment 1 "PROVISIONAL - not built, simulated or tested")\n'
       f'  (comment 2 "Owner: Shreehan (hardware); drafted by Sai") (comment 3 "Parts: hardware/bom/electrical_bom.csv"))\n'
       f'(lib_symbols\n{lib_txt}\n)\n' + "\n".join(items) +
       f'\n(sheet_instances (path "/" (page "1")))\n)\n')
(HERE / "channel_driver.kicad_sch").write_text(sch)
with open(HERE / "channel_driver_netlist.csv", "w", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["net", "reference", "pin", "value"])
    w.writerows(sorted(nets_rows))
print(f"wrote channel_driver.kicad_sch ({len(sch) // 1024} kB) and channel_driver_netlist.csv ({len(nets_rows)} pin connections)")
