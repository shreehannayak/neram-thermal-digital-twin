#!/usr/bin/env python3
"""Build the controller demo replays SCN_B-SCN_F from Suchita's supervisory controller (controller/neram_ctrl,
v2 design, code rebuilt 18 Oct 2026) and its test bench.

For every scenario the controller test run is executed, the twin values the controller actually received are written
as a per-minute twin CSV (integration/twin_outputs/twin_CTRL_<id>.csv), the 1 Hz controller log is the run's own log,
and integration/build_replay.py merges the two into integration/replays/<id>.jsonl.gz (validated before writing).

The twin values are TEST-BENCH STAND-INS (synthetic inputs or the first-order twin stand-in), never the NERAM twin,
so every replay is built with --twin-source SIMULATED. Closed-loop scenarios carry the ASSUMED patient plant
(T_plant, dT_heat). SIMULATED / ASSUMED PROTOTYPE RESPONSE; no clinical claim.

Usage: python tools/make_controller_replays.py
"""
import csv
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "controller"))
from neram_ctrl import testbench as tb  # noqa: E402
from neram_ctrl import tests as T  # noqa: E402
from neram_ctrl.params import default_params  # noqa: E402

TWIN_COLS = (["T_twin_s", "T_obs", "obs_missing", "T_est", "T_est_sd"]
             + [f"{p}_{h}" for h in (20, 30, 60) for p in ("T_pred", "L80", "U80", "L95", "U95")]
             + ["P_below_hypo_20", "P_below_hypo_30", "P_below_hypo_60", "P_level_shift", "P_outlier", "Twin_Valid"])
CREATED = "2026-10-19T00:00:00Z"
COMMON_LIMITS = [
    "Controller: Suchita's supervisory controller design (v2 specification); Python fallback code rebuilt by Sai on "
    "18 Oct 2026 from that specification (reproduces her v2 logs byte for byte). Not a Simulink/Stateflow model.",
    "Twin fields are test-bench stand-ins (synthetic inputs or a first-order filter stand-in), NOT the NERAM twin. "
    "The forecast is the stand-in's flat persistence (T_pred = T_est) with normal bands from T_est_sd.",
    "Hardware signals and module temperatures come from test stand-ins; no hardware exists. Thresholds are "
    "placeholders (Shreehan, TBD).",
    "No clinical, hardware or treatment claim is made.",
]

SCEN = {
    "SCN_B": dict(test="TC02", title="Predictive warming (controller TC02, synthetic forecast input)",
                  purpose="A synthetic forecast risk (P_below_hypo_20 crosses 0.3 at 300 s) is confirmed over two twin "
                          "updates; the controller enters PREDICTIVE_WARMING at 370 s and raises all four channels "
                          "with the PI law, capped at 40 %.",
                  loop="Open loop: the synthetic twin input does not respond to heating (no patient plant).",
                  extra=["Synthetic constant T_est 36.5 degC and stepped forecast probability; not a forecast made "
                         "by the twin."]),
    "SCN_C": dict(test="TC07", title="Over-temperature fault (controller TC07, closed loop)",
                  purpose="Active warming of a patient stand-in from 35 degC; a test ramp on CH2 sensor A first "
                          "isolates CH2 (205 sensor disagreement), then crosses 41 degC: SAFETY_SHUTDOWN (206) in the "
                          "same second, RESET blocked at 1050 s while still hot, latch held after cooling, RESET at "
                          "1250 s releases, warming resumes.",
                  loop="Closed loop with the ASSUMED patient plant and the twin stand-in.",
                  extra=["The CH2 sensor-A ramp is an injected test stimulus, not a heater response.",
                         "T_plant is an ASSUMED plant response (k_heat 0.6 degC/h at 100 %), not a prediction."]),
    "SCN_D": dict(test="TC13", title="Twin degraded (controller TC13, synthetic)",
                  purpose="Forecast-triggered warming is running when Twin_Valid becomes DEGRADED at 300 s: "
                          "TWIN_DEGRADED.MONITOR, all heat 0, no autonomous warming; the twin is VALID again from "
                          "600 s and the controller returns to NORMAL after t_recover_s (630 s).",
                  loop="Open loop: synthetic twin input, no patient plant.",
                  extra=["Synthetic twin input values; the degradation is scripted."]),
    "SCN_E": dict(test="TC04", title="Active recovery to target (controller TC04, closed loop, 12 h)",
                  purpose="Patient stand-in starts at 35 degC (below t_hypo 36 degC): ACTIVE_WARMING after the 10 s "
                          "dwell, PI warming at the 50 % channel cap, TARGET_MAINTENANCE at 24430 s (6.8 h) with low "
                          "maintenance heat.",
                  loop="Closed loop with the ASSUMED patient plant and the twin stand-in.",
                  extra=["Time to target (about 7 h) is a property of the ASSUMED plant gain; TC18 shows 3.6-13.9 h "
                         "for 2x-0.5x gain. It is not a prediction.",
                         "Flat passive trajectory: no passive cooling is modelled."]),
    "SCN_F": dict(test="TC08", title="Sensor fault isolates one channel (controller TC08, synthetic)",
                  purpose="CH3 sensor B becomes unreadable at 120 s: only CH3 is switched off (303) and CHANNEL_FAULT "
                          "is raised; a RESET at 150 s with the sensor still open is refused; the sensor recovers at "
                          "200 s but the latch holds until the RESET at 240 s.",
                  loop="Open loop: synthetic below-hypo twin input, no patient plant.",
                  extra=["The NaN on CH3 sensor B is an injected test fault."]),
}


def fnum(v, nd=6):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return ("%." + str(nd) + "f") % v


def twin_csv(rows, path):
    """One row per twin update (T_twin_s change) with the values the controller received."""
    out, last = [], None
    for r in rows:
        s = r["_sig"]
        tu = s["T_twin_s"]
        if tu == last or (isinstance(tu, float) and math.isnan(tu)):
            continue
        last = tu
        obs = s.get("T_obs", float("nan"))
        miss = obs is None or (isinstance(obs, float) and math.isnan(obs))
        rec = {"T_twin_s": int(tu), "T_obs": "" if miss else fnum(obs), "obs_missing": 1 if miss else 0,
               "T_est": fnum(s["T_est"]), "T_est_sd": fnum(s["T_est_sd"]),
               "P_below_hypo_20": fnum(s["P_below_hypo_20"]), "P_below_hypo_30": fnum(s["P_below_hypo_30"]),
               "P_below_hypo_60": fnum(s["P_below_hypo_60"]), "P_level_shift": "", "P_outlier": "",
               "Twin_Valid": int(s["Twin_Valid"])}
        sd = s["T_est_sd"]
        for h in (20, 30, 60):
            tp = s.get(f"T_pred_{h}")
            rec[f"T_pred_{h}"] = fnum(tp)
            # stand-in persistence forecast: normal bands from T_est_sd (z80 = 1.2816, z95 = 1.96)
            for p, z in (("L80", -1.2816), ("U80", 1.2816), ("L95", -1.96), ("U95", 1.96)):
                rec[f"{p}_{h}"] = fnum(tp + z * sd)
        if rec["Twin_Valid"] != 2:
            # interface 4A: no forecast is published unless the twin is VALID (the controller ignores it then)
            for k in rec:
                if k.startswith(("T_pred", "L80", "U80", "L95", "U95", "P_below")):
                    rec[k] = ""
        out.append(rec)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TWIN_COLS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)


def write_ctrl(path, rows):
    """Section-1S log plus the optional clinician button columns (so the viewer can show Start/Stop/Reset)."""
    cols = tb.LOG_COLUMNS + ["Clinician_Start", "Clinician_Stop", "Clinician_Reset"]
    with open(path, "w", newline="") as f:
        f.write(",".join(cols) + "\r\n")
        for r in rows:
            vals = [tb.fmt(r[c]) for c in tb.LOG_COLUMNS] + [str(int(r["_sig"].get(b, 0) or 0)) for b in cols[-3:]]
            f.write(",".join(vals) + "\r\n")


def main():
    P = default_params()
    S = T.scenarios(P)
    tw_dir = ROOT / "integration" / "twin_outputs"
    ci_dir = ROOT / "integration" / "scenario_info"
    log_dir = ROOT / "integration" / "controller_logs"
    for sid, cfg in SCEN.items():
        fn = S[cfg["test"]]
        # re-run with internals kept (same deterministic run as the published test)
        import neram_ctrl.testbench as tbm
        orig = tbm.run

        def run_keep(*a, **k):
            k["keep_internal"] = True
            return orig(*a, **k)
        tbm.run = run_keep
        try:
            rows = fn()
        finally:
            tbm.run = orig
        twin_path = tw_dir / f"twin_CTRL_{sid}.csv"
        twin_csv(rows, twin_path)
        ctrl_path = log_dir / f"ctrl_CTRL_{sid}.csv"
        write_ctrl(ctrl_path, rows)
        info = {"title": cfg["title"], "purpose": cfg["purpose"],
                "data_source": "Controller: Suchita's supervisory controller test %s (SIMULATED test bench, "
                               "controller/neram_ctrl). Twin fields: test-bench stand-in values the controller "
                               "received (SIMULATED)." % cfg["test"],
                "loop_description": cfg["loop"], "limitations": cfg["extra"] + COMMON_LIMITS}
        info_path = ci_dir / f"{sid}.json"
        info_path.write_text(json.dumps(info, indent=2) + "\n")
        out = ROOT / "integration" / "replays" / f"{sid}.jsonl.gz"
        cmd = [sys.executable, str(ROOT / "integration" / "build_replay.py"), "--scenario-id", sid,
               "--twin", str(twin_path), "--ctrl", str(ctrl_path), "--cohort", "SYNTHETIC",
               "--obs-source", "SIMULATED", "--twin-source", "SIMULATED", "--accept-ctrl-input-columns",
               "--scenario-info", str(info_path), "--params-version", "standalone-0.1",
               "--generator", "tools/make_controller_replays.py (Sai, 2026-10-19) + controller/neram_ctrl",
               "--created-utc", CREATED, "--out", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(sid, cfg["test"], "rc", r.returncode, (r.stderr.strip().splitlines() or [""])[-1][:200])
        if r.returncode:
            print(r.stderr[-2000:])
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
