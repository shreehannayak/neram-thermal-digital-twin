#!/usr/bin/env python3
"""Figures for results/figures/: the four SYNTHETIC twin exports (twin_SYN_01..04).
Every figure is labelled SYNTHETIC (simulated observations; canonical filter with ASSUMED_SYNTHETIC parameters).
Usage: python tools/make_twin_syn_figures.py"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "figures"
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
EST, FLAG = "#2a78d6", "#eb6834"


def f(x):
    return None if x == "" else float(x)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    man = json.loads((ROOT / "integration" / "twin_outputs" / "twin_SYN_manifest.json").read_text())
    P = json.loads((ROOT / "config" / "params.json").read_text())["params"]
    t_hypo = P["t_hypo_degC"]["value"] if P["t_hypo_degC"]["value"] is not None else P["t_hypo_degC"]["placeholder"]
    disp = json.loads((ROOT / "config" / "unity_display.json").read_text())["settings"]
    thr = disp["flag_p_outlier_display"]["value"]
    for sc in man["scenarios"]:
        rows = list(csv.DictReader(open(ROOT / sc["twin"])))
        tm = [float(r["T_twin_s"]) / 60 for r in rows]
        obs = [f(r["T_obs"]) for r in rows]
        est = [f(r["T_est"]) for r in rows]
        sd = [f(r["T_est_sd"]) for r in rows]
        p30 = [f(r["P_below_hypo_30"]) for r in rows]
        po = [f(r["P_outlier"]) for r in rows]
        pl = [f(r["P_level_shift"]) for r in rows]
        fig, (a, b) = plt.subplots(2, 1, figsize=(16 / 1.5, 9 / 1.5), dpi=150, sharex=True,
                                   gridspec_kw=dict(height_ratios=[3, 1.2]), facecolor=SURF)
        for ax in (a, b):
            ax.set_facecolor(SURF)
            ax.grid(color=GRID, lw=0.8)
            for s in ("top", "right"):
                ax.spines[s].set_visible(False)
            for s in ("left", "bottom"):
                ax.spines[s].set_color(INK2)
            ax.tick_params(colors=INK2, labelsize=8)
        lo = [e - s if e is not None else None for e, s in zip(est, sd)]
        hi = [e + s if e is not None else None for e, s in zip(est, sd)]
        a.fill_between(tm, [x if x is not None else float("nan") for x in lo],
                       [x if x is not None else float("nan") for x in hi], color=EST, alpha=0.18, lw=0, label="T_est ± SD")
        a.plot(tm, [x if x is not None else float("nan") for x in est], color=EST, lw=2, label="T_est (filtered estimate)")
        a.scatter([t for t, o in zip(tm, obs) if o is not None], [o for o in obs if o is not None], s=14,
                  color=INK2, zorder=3, label="T_obs (simulated observation)")
        miss = [t for t, o in zip(tm, obs) if o is None]
        if miss:
            ymin = min(min(o for o in obs if o is not None), t_hypo) - 0.1
            a.scatter(miss, [ymin] * len(miss), s=14, facecolors="none", edgecolors=INK2,
                      label="missing minute (hollow, drawn at the bottom)")
        fl = [(t, o) for t, o, x in zip(tm, obs, po) if x is not None and x >= thr and o is not None]
        if fl:
            a.scatter([x for x, _ in fl], [y for _, y in fl], s=90, facecolors="none", edgecolors=FLAG, lw=2, zorder=4,
                      label=f"possible artefact (model P_outlier ≥ {thr})")
        fs = [t for t, x in zip(tm, pl) if x is not None and x >= thr]
        for t in fs:
            a.axvline(t, color=FLAG, lw=1, ls=":")
        a.axhline(t_hypo, color=INK, lw=1, ls="--")
        a.text(tm[-1], t_hypo, f"  t_hypo {t_hypo} °C (PLACEHOLDER, TBD)", va="bottom", ha="right", fontsize=8, color=INK)
        a.set_ylabel("Patient temperature signal (°C)", color=INK2, fontsize=9)
        h, lab = a.get_legend_handles_labels()
        a.set_title(f"{sc['id']} — {sc['title']}\nSYNTHETIC: simulated observations; twin = canonical NERAM filter with ASSUMED "
                    "parameters (not fitted, not patient data)", fontsize=10, color=INK, loc="left")
        b.plot(tm, [x if x is not None else float("nan") for x in p30], color=EST, lw=2)
        b.set_ylim(-0.02, 1.02)
        b.set_ylabel("P(obs +30 min < t_hypo)", color=INK2, fontsize=8)
        b.set_xlabel("Minutes since settled start (gaps = forecast hidden: Twin_Valid ≠ VALID)", color=INK2, fontsize=8)
        fig.legend(h, lab, fontsize=7.5, frameon=False, loc="lower center", ncol=3)
        fig.tight_layout(rect=(0, 0.07, 1, 1))
        fig.savefig(OUT / f"twin_{sc['id']}.png", facecolor=SURF)
        plt.close(fig)
        print("wrote", OUT / f"twin_{sc['id']}.png")


if __name__ == "__main__":
    main()
