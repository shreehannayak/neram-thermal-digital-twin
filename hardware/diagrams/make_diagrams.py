"""Write the three hardware diagrams as draw.io source (.drawio) and image (.png) from one layout, so the source and
the picture always agree.  Usage: python hardware/diagrams/make_diagrams.py   (needs matplotlib)

Content follows hardware/README.md, docs/*.md and bom/electrical_bom.csv. Part names marked PROVISIONAL there are
PROVISIONAL here; values that are TBD there stay TBD here. Proof-of-concept prototype, not a medical device."""
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

HERE = Path(__file__).resolve().parent
PAL = {  # fill, stroke
    "host": ("#e3ecf7", "#3d6da8"), "mcu": ("#fbf0d6", "#a8801f"), "power": ("#ece6f5", "#6b52a0"),
    "safety": ("#f9e0dc", "#b2402f"), "chan": ("#e2f1e2", "#3f8a42"), "module": ("#f6e7d6", "#a86420"),
    "neutral": ("#f2f2f2", "#666666"), "unity": ("#e8f4f4", "#2d8a8a"),
}
INK = "#1d1d1d"


class Diagram:
    def __init__(self, name, w, h, title):
        self.name, self.w, self.h, self.title = name, w, h, title
        self.nodes, self.edges, self.texts = {}, [], []

    def node(self, nid, x, y, w, h, text, kind, bold_first=True, size=13):
        self.nodes[nid] = dict(x=x, y=y, w=w, h=h, text=text, kind=kind, bold=bold_first, size=size)

    def edge(self, pts, label=None, lpos=None, dashed=False, both=False, size=11.5, lbg=True):
        self.edges.append(dict(pts=pts, label=label, lpos=lpos, dashed=dashed, both=both, size=size, lbg=lbg))

    def text(self, x, y, s, size=12, ha="left", bold=False, color=INK):
        self.texts.append(dict(x=x, y=y, s=s, size=size, ha=ha, bold=bold, color=color))

    # ------------------------------------------------------------------ draw.io
    def drawio(self):
        cells, k = [], 2

        def nid():
            nonlocal k
            k += 1
            return f"c{k}"
        v = lambda s: escape(s).replace("\n", "&#xa;")
        for n in self.nodes.values():
            f, s = PAL[n["kind"]]
            cells.append(f'<mxCell id="{nid()}" value="{v(n["text"])}" style="rounded=1;arcSize=8;whiteSpace=wrap;html=0;'
                         f'fillColor={f};strokeColor={s};strokeWidth=1.6;fontColor={INK};fontSize={round(n["size"] * 1.15)};" vertex="1" parent="1">'
                         f'<mxGeometry x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" as="geometry"/></mxCell>')
        for e in self.edges:
            p = e["pts"]
            st = f"endArrow=block;endFill=1;startArrow={'block' if e['both'] else 'none'};startFill=1;html=0;rounded=0;strokeColor={INK};strokeWidth=1.4;" + ("dashed=1;" if e["dashed"] else "")
            mids = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in p[1:-1])
            cells.append(f'<mxCell id="{nid()}" style="{st}" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
                         f'<mxPoint x="{p[0][0]}" y="{p[0][1]}" as="sourcePoint"/><mxPoint x="{p[-1][0]}" y="{p[-1][1]}" as="targetPoint"/>'
                         + (f'<Array as="points">{mids}</Array>' if mids else "") + '</mxGeometry></mxCell>')
            if e["label"]:
                x, y = e["lpos"]
                lw, lh = 9 * max(len(t) for t in e["label"].split("\n")), 18 * (e["label"].count("\n") + 1)
                cells.append(f'<mxCell id="{nid()}" value="{v(e["label"])}" style="text;html=0;align=center;verticalAlign=middle;'
                             f'labelBackgroundColor=#ffffff;fontSize={round(e["size"] * 1.15)};fontColor={INK};" vertex="1" parent="1">'
                             f'<mxGeometry x="{x - lw / 2}" y="{y - lh / 2}" width="{lw}" height="{lh}" as="geometry"/></mxCell>')
        for t in [dict(x=24, y=34, s=self.title, size=17, ha="left", bold=True, color=INK)] + self.texts:
            lw = 9 * max(len(s) for s in t["s"].split("\n"))
            x0 = t["x"] - (lw / 2 if t["ha"] == "center" else 0)
            cells.append(f'<mxCell id="{nid()}" value="{v(t["s"])}" style="text;html=0;align={t["ha"]};verticalAlign=middle;'
                         f'fontSize={round(t["size"] * 1.15)};fontStyle={1 if t["bold"] else 0};fontColor={t["color"]};" vertex="1" parent="1">'
                         f'<mxGeometry x="{x0}" y="{t["y"] - 12}" width="{lw}" height="24" as="geometry"/></mxCell>')
        xml = (f'<mxfile host="make_diagrams.py"><diagram name="{self.name}" id="{self.name}"><mxGraphModel dx="{self.w}" dy="{self.h}" grid="1" '
               f'gridSize="10" page="1" pageWidth="{self.w}" pageHeight="{self.h}" background="#ffffff"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
               + "".join(cells) + "</root></mxGraphModel></diagram></mxfile>\n")
        return xml

    # ------------------------------------------------------------------ PNG
    def png(self, path):
        fig = plt.figure(figsize=(self.w / 100, self.h / 100), dpi=100)
        ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, self.w); ax.set_ylim(self.h, 0); ax.axis("off")
        fig.patch.set_facecolor("white")
        for n in self.nodes.values():
            f, s = PAL[n["kind"]]
            ax.add_patch(FancyBboxPatch((n["x"], n["y"]), n["w"], n["h"], boxstyle="round,pad=0,rounding_size=10",
                                        fc=f, ec=s, lw=1.8, zorder=2))
            lines = n["text"].split("\n"); lh = n["size"] * 1.55
            y0 = n["y"] + n["h"] / 2 - lh * (len(lines) - 1) / 2
            for i, t in enumerate(lines):
                ax.text(n["x"] + n["w"] / 2, y0 + i * lh, t, ha="center", va="center", fontsize=n["size"], color=INK,
                        weight="bold" if (i == 0 and n["bold"]) else "normal", zorder=3)
        for e in self.edges:
            p = e["pts"]; xs = [q[0] for q in p]; ys = [q[1] for q in p]
            ax.plot(xs[:-1] + [xs[-1]], ys[:-1] + [ys[-1]], color=INK, lw=1.5, ls=(0, (5, 4)) if e["dashed"] else "-", zorder=1,
                    solid_capstyle="butt")
            ax.annotate("", xy=p[-1], xytext=p[-2], arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.5, mutation_scale=16,
                                                                    shrinkA=0, shrinkB=0), zorder=4)
            if e["both"]:
                ax.annotate("", xy=p[0], xytext=p[1], arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.5, mutation_scale=16,
                                                                      shrinkA=0, shrinkB=0), zorder=4)
            if e["label"]:
                ax.text(*e["lpos"], e["label"], ha="center", va="center", fontsize=e["size"], color=INK, zorder=5, linespacing=1.35,
                        bbox=dict(fc="white", ec="none", pad=2.5) if e["lbg"] else None)
        ax.text(24, 34, self.title, fontsize=17, weight="bold", va="center", color=INK)
        for t in self.texts:
            ax.text(t["x"], t["y"], t["s"], fontsize=t["size"], ha=t["ha"], va="center", weight="bold" if t["bold"] else "normal",
                    color=t["color"], linespacing=1.4)
        fig.savefig(path, dpi=150, facecolor="white"); plt.close(fig)

    def write(self, stem):
        (HERE / f"{stem}.drawio").write_text(self.drawio(), encoding="utf-8")
        self.png(HERE / f"{stem}.png")
        self.png(HERE / f"{stem}.pdf")      # plan section AC: block diagram as .drawio + .png + .pdf
        print("wrote", stem + ".drawio", stem + ".png", stem + ".pdf")


FOOT = "Proof-of-concept prototype, not a medical device. All hardware is SIMULATED in the demo; no hardware has been built. PROVISIONAL parts per bom/electrical_bom.csv."


def block_diagram():
    d = Diagram("system_block_diagram", 1900, 1030, "NERAM system block diagram (paper design; hardware SIMULATED in the demo)")
    A, B, C, D = 40, 600, 1090, 1570
    SB, PB = 1030, 1060          # signal bus (PWM out; sensors + current in) and heater-power bus x positions
    d.node("host", A, 90, 380, 130, "Host computer (bedside laptop)\nDigital Twin (Sai; Python)\nSupervisory controller, layer 3\n(Suchitha; Python fallback)", "host")
    d.node("obs", A, 310, 380, 100, "Patient-observation interface\n(prototype: replay of recorded\nmonitor data)", "neutral")
    d.node("dcdc", A, 500, 380, 90, "Logic DC/DC (PROVISIONAL)\nRECOM R-78E5.0-0.5: 24 V to 5 V", "power")
    d.node("psu", A, 680, 380, 110, "Isolated AC/DC supply (PROVISIONAL)\nMean Well MPM-65-24ST\n24 V bus (v_bus_V), 65 W", "power")
    d.node("mains", A, 870, 380, 70, "Mains inlet + fuse", "neutral")
    d.node("mcu", B, 90, 380, 170, "MCU board, layer 2 (PROVISIONAL)\nNUCLEO-G474RE\n8 sensor + 4 current-sense inputs\n4 PWM outputs; firmware limits\nindependent watchdog; host heartbeat", "mcu")
    d.node("cut", B, 470, 300, 120, "Hardware cutoff, layer 1\ncomparator on its own NTC\nper channel; latched;\nworks with the MCU halted", "safety")
    d.node("msw", B, 690, 380, 100, "Master safety switch\ndefault open; in series\nwith all four channels", "safety")
    limbs = ["left hand", "right hand", "left foot", "right foot"]
    ys = [90, 270, 450, 630]
    for i, (lb, y) in enumerate(zip(limbs, ys), 1):
        d.node(f"ch{i}", C, y, 360, 120, f"CH{i} driver ({lb})\nlow-side switch; current sense\nfuse; connector", "chan")
        d.node(f"m{i}", D, y, 300, 120, f"{lb.capitalize()} module\nheater film\nsensors A and B", "module")
        d.edge([(C + 360, y + 60), (D, y + 60)], both=True)
    mid = (A + 380 + B) / 2
    d.edge([(A + 380, 165), (B, 165)], both=True)
    d.text(mid, 120, "USB serial\nevery 1 s", size=10.5, ha="center")
    d.text(mid, 205, "Heat_1..4, enable\nstatus, heartbeat", size=10.5, ha="center")
    d.edge([(A + 190, 310), (A + 190, 220)], label="patient temperature signal", lpos=(A + 190, 266))
    d.edge([(A + 190, 870), (A + 190, 790)])
    d.edge([(A + 190, 680), (A + 190, 590)], dashed=True, label="24 V", lpos=(A + 225, 636))
    d.edge([(A + 380, 545), (500, 545), (500, 240), (B, 240)], label="5 V logic", lpos=(500, 400))
    d.edge([(A + 380, 735), (B, 735)], dashed=True, label="24 V bus", lpos=(510, 712))
    d.edge([(B + 380, 140), (SB, 140), (SB, ys[-1] + 40), (C, ys[-1] + 40)])
    for y in ys[:-1]:
        d.edge([(SB, y + 40), (C, y + 40)])
    d.edge([(B + 380, 740), (PB, 740), (PB, ys[0] + 85), (C, ys[0] + 85)], dashed=True)
    for y in ys[1:]:
        d.edge([(PB, y + 85), (C, y + 85)], dashed=True)
    d.edge([(C, 560), (B + 300, 560)], label="own NTC\nper module", lpos=(985, 520), size=10.5)
    d.edge([(B + 150, 590), (B + 150, 690)], label="opens + latches", lpos=(B + 150, 640))
    d.edge([(B + 340, 260), (B + 340, 690)], label="MCU or watchdog\nopens", lpos=(B + 340, 380), size=10.5)
    d.text(SB, 76, "PWM out; sensors A/B + current in (x4)", size=10.5, ha="center")
    d.text(PB + 20, 805, "heater power, dashed (x4)", size=10.5, ha="right")
    d.text(24, 975, "Solid arrows: signals. Dashed arrows: heater power, which passes the master switch before reaching any channel.", size=11)
    d.text(24, 1003, FOOT, size=11)
    d.write("system_block_diagram")


def safety_layers():
    d = Diagram("safety_layers", 1500, 900, "Safety layers: each layer can remove heater power without the layers above it")
    L, R = 40, 960
    d.node("l3", L, 90, 640, 150, "Layer 3: supervisory controller (software; Suchitha)\nPython fallback for MATLAB/Simulink (not available)\nderate at t_mod_derate_degC; trip at t_mod_trip_degC\nfault latch; SAFETY_SHUTDOWN sets Heat_i = 0, master_enable = 0", "host", size=12.5)
    d.node("l2", L, 300, 640, 150, "Layer 2: MCU firmware (Shreehan)\nfirmware limits; independent watchdog (wdt_timeout_ms, TBD)\nhost-heartbeat timeout: all heaters OFF\nstuck-on detection from current sense", "mcu", size=12.5)
    d.node("l1", L, 510, 640, 150, "Layer 1: hardware cutoff (no firmware; Shreehan)\ncomparator on its own NTC per channel at t_hw_cutoff_degC (TBD)\nlatched until manual RESET\nworks with the MCU halted", "safety", size=12.5)
    d.node("msw", R, 200, 480, 110, "Master safety switch\nin series with all four channels\ndefault open (relay coil off)", "safety")
    d.node("chs", R, 400, 480, 110, "Channel switches CH1 to CH4\ndefault off (gate pull-down)\nlow-side MOSFET per channel", "chan")
    d.node("mods", R, 590, 480, 90, "Heater modules\nhands CH1, CH2; feet CH3, CH4", "module")
    d.edge([(L + 320, 240), (L + 320, 300)], label="Heat_i = 0, master_enable = 0 (USB)", lpos=(L + 500, 270), size=11)
    d.edge([(L + 640, 345), (800, 345), (800, 255), (R, 255)], label="opens", lpos=(800, 300))
    d.edge([(L + 640, 405), (R, 455)], label="PWM off", lpos=(840, 420))
    d.edge([(L + 640, 585), (880, 585), (880, 290), (R, 290)], label="opens + latches", lpos=(880, 540))
    d.edge([(R + 240, 310), (R + 240, 400)], dashed=True, label="24 V bus", lpos=(R + 290, 355))
    d.edge([(R + 240, 510), (R + 240, 590)], dashed=True)
    d.node("ord", L, 710, 1400, 80, "Threshold ordering (FROZEN; values TBD, never guessed)\nt_mod_derate_degC  <  t_mod_trip_degC  <  t_hw_cutoff_degC  <=  t_surface_limit_degC", "neutral", size=13)
    d.text(24, 835, "Default state with no power, MCU in reset or host lost: master switch open and every channel switch off.", size=11)
    d.text(24, 865, FOOT, size=11)
    d.write("safety_layers")


def interface_map():
    d = Diagram("interface_map", 1800, 1040, "NERAM interface map: who hands what to whom (hardware SIMULATED in the demo)")
    d.node("sai", 690, 100, 420, 110, "Sai\nDigital Twin; config files; replay builder", "host")
    d.node("uni", 1360, 100, 400, 110, "Unity replay viewer\nreads only the merged replay", "unity")
    d.node("suc", 50, 470, 400, 110, "Suchitha\nSupervisory controller (Python fallback)", "chan")
    d.node("neh", 1360, 470, 400, 110, "Neharika\nCAD: modules, wearable, controller", "module")
    d.node("shr", 690, 830, 420, 110, "Shreehan\nHardware; README; licences; audit", "mcu")
    d.edge([(1110, 155), (1360, 155)], label="replay .jsonl.gz", lpos=(1235, 132))
    d.edge([(690, 185), (300, 470)], both=True, label="Sai to Suchitha: twin CSV, interface spec, enums, params\nSuchitha to Sai: ctrl_*.csv logs, test results", lpos=(470, 330))
    d.edge([(900, 210), (900, 830)], both=True, label="Shreehan to Sai: fault codes, channel map, hardware signals\nSai to Shreehan: case-duration statistics, scientific wording", lpos=(900, 520))
    d.edge([(1110, 185), (1500, 470)], both=True, label="Neharika to Sai: FBX set\nSai to Neharika: Unity import check", lpos=(1330, 330))
    d.edge([(250, 580), (690, 885)], both=True, label="Shreehan to Suchitha: fault_codes.csv, controller_hw_interface.md\nSuchitha to Shreehan: T07_duty_stats.csv, hardware assumptions", lpos=(420, 720))
    d.edge([(1560, 580), (1110, 885)], both=True, label="Shreehan to Neharika: cad_envelope.csv\nNeharika to Shreehan: coverage area, ports", lpos=(1380, 720))
    d.text(24, 990, "Rule: change a row you do not own through a GitHub issue tagged interface-change; the owner approves and Sai merges. "
                    "Nothing reaches Unity except through Sai's replay.", size=11)
    d.write("interface_map")


if __name__ == "__main__":
    block_diagram(); safety_layers(); interface_map()
