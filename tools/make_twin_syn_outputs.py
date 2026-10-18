#!/usr/bin/env python3
"""Generate the four SYNTHETIC twin outputs twin_SYN_01..04.csv by running the canonical twin
(src/twin_replay_export.py -> src/thermal_robust_core.py) on four deterministic synthetic observation series.

These are genuinely different scenarios (not copies), and the twin values come from the real NERAM filter,
not from a stand-in. Everything is SYNTHETIC: observations are SIMULATED from the model's own structure using
the ASSUMED_SYNTHETIC parameter file (config/model_params_synthetic.json); scripted events are listed below.

  SYN_01  usual care          stable trajectory well above the placeholder t_hypo          (pairs with plan SCN_A)
  SYN_02  cooling risk        trajectory that drifts below the placeholder t_hypo          (pairs with plan SCN_B)
  SYN_03  artefact handling   one +1.5 degC outlier at minute 40, +0.3 degC level shift at 60 (twin-side companion
                              for fault scenarios; SCN_C itself is a hardware/controller fault)
  SYN_04  data gap            observations missing for minutes 45-60 -> DEGRADED, then recovery (pairs with SCN_D)

Outputs
  integration/synthetic/observations/obs_SYN_0x.csv      simulated per-minute observation input
  integration/twin_outputs/twin_SYN_0x.csv               twin export (interface spec columns)
  integration/twin_outputs/twin_SYN_0x.meta.json         hashes + parameter/config provenance
  integration/twin_outputs/twin_SYN_manifest.json        scenario list and hashes

Usage: python tools/make_twin_syn_outputs.py [--check]   (--check: regenerate in memory, compare bytes, change nothing)
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import thermal_robust_core as core  # noqa: E402
import twin_replay_export as tre  # noqa: E402

PARAMS = ROOT / "config" / "model_params_synthetic.json"
CONFIG = ROOT / "config" / "twin_export_config.json"
OBS_DIR = ROOT / "integration" / "synthetic" / "observations"
OUT_DIR = ROOT / "integration" / "twin_outputs"

SCENARIOS = [
    dict(id="SYN_01", title="Usual care (synthetic)", seed=101, minutes=90, u0=36.6, theta=[0.3, 0.1],
         outliers={}, shifts={}, gaps=[], pairs_with="SCN_A"),
    dict(id="SYN_02", title="Cooling toward the placeholder t_hypo (synthetic)", seed=102, minutes=90, u0=36.45,
         theta=[0.7, -0.25], outliers={}, shifts={}, gaps=[], pairs_with="SCN_B"),
    dict(id="SYN_03", title="Outlier and level shift (synthetic)", seed=103, minutes=90, u0=36.6, theta=[0.3, 0.1],
         outliers={40: 1.5}, shifts={60: 0.3}, gaps=[], pairs_with="SCN_C (twin-side companion only)"),
    dict(id="SYN_04", title="Observation gap -> degraded twin (synthetic)", seed=104, minutes=90, u0=36.6,
         theta=[0.3, 0.1], outliers={}, shifts={}, gaps=[(45, 60)], pairs_with="SCN_D"),
]


def simulate(sc, p, gamma):
    rg = np.random.default_rng(sc["seed"])
    L = sc["minutes"]
    t = np.arange(L, dtype=float)
    level = sc["u0"] + np.cumsum(rg.normal(0.0, np.sqrt(p["q"]), L))
    for m, d in sc["shifts"].items():
        level[m:] += d
    y = core.phi(t, gamma) @ np.asarray(sc["theta"], float) + level + rg.normal(0.0, np.sqrt(p["r"]), L)
    for m, d in sc["outliers"].items():
        y[m] += d
    for a, b in sc["gaps"]:
        y[a:b + 1] = np.nan
    return t * 60.0, y


def write_obs(path, ts, y):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write("T_twin_s,T_obs\n")
        for a, b in zip(ts, y):
            f.write(f"{a:.0f},{'' if np.isnan(b) else f'{b:.6f}'}\n")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(root_out):
    p, gamma, m0, S, pdoc = tre.load_model_params(PARAMS, "SYNTHETIC")
    cfg, _ = tre.load_config(CONFIG)
    obs_dir = root_out / "integration" / "synthetic" / "observations"
    out_dir = root_out / "integration" / "twin_outputs"
    manifest = dict(generator="tools/make_twin_syn_outputs.py", core_sha256=tre.check_core(),
                    model_params_sha256=sha(PARAMS), config_sha256=sha(CONFIG), cohort="SYNTHETIC",
                    note="SIMULATED observations; twin values computed by the canonical NERAM filter with "
                         "ASSUMED_SYNTHETIC parameters (not fitted).", scenarios=[])
    for sc in SCENARIOS:
        ts, y = simulate(sc, p, gamma)
        obs_path = obs_dir / f"obs_{sc['id']}.csv"
        write_obs(obs_path, ts, y)
        t2, y2 = tre.read_obs(obs_path)
        rows, trunc = tre.export(t2, y2, p, gamma, m0, S, cfg)
        twin_path = out_dir / f"twin_{sc['id']}.csv"
        tre.write_csv(rows, twin_path)
        counts = {k: sum(r["Twin_Valid"] == v for r in rows) for k, v in tre.TV.items()}
        meta = dict(scenario=sc, core_sha256=manifest["core_sha256"], obs_sha256=sha(obs_path),
                    twin_sha256=sha(twin_path), model_params_status=pdoc["status"], config_used=cfg,
                    binomial_truncation_mass={str(k): v for k, v in trunc.items()}, twin_valid_counts=counts)
        (out_dir / f"twin_{sc['id']}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        manifest["scenarios"].append(dict(id=sc["id"], title=sc["title"], pairs_with=sc["pairs_with"],
                                          obs=f"integration/synthetic/observations/obs_{sc['id']}.csv",
                                          twin=f"integration/twin_outputs/twin_{sc['id']}.csv",
                                          twin_sha256=meta["twin_sha256"], twin_valid_counts=counts))
    (out_dir / "twin_SYN_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if not a.check:
        m = build(ROOT)
        for s in m["scenarios"]:
            print(f"{s['id']}: {s['twin']} {s['twin_valid_counts']}")
        return 0
    with tempfile.TemporaryDirectory() as td:
        build(Path(td))
        bad = []
        for sub in ("integration/synthetic/observations", "integration/twin_outputs"):
            for f in sorted((Path(td) / sub).iterdir()):
                ref = ROOT / sub / f.name
                if not ref.exists() or ref.read_bytes() != f.read_bytes():
                    bad.append(str(ref.relative_to(ROOT)))
    if bad:
        print("NOT reproducible / out of date:", ", ".join(bad))
        return 1
    print("twin_SYN_01..04 outputs are byte-identical on regeneration")
    return 0


if __name__ == "__main__":
    sys.exit(main())
