#!/usr/bin/env python3
"""check_replay_semantics.py - behaviour checks that a schema-valid replay can still fail.

validate_replay.py (and its C# twin) prove a replay is WELL-FORMED. This tool asks whether the frames actually
behave like a coherent scenario. It is Python-only and advisory for the demo list; it does not change the
schema contract shared with Unity.

  S01 ERROR  a warming episode (PREDICTIVE_WARMING / ACTIVE_WARMING / CLINICIAN_WARMING) in which every Heat_i
             and Demand_Global stay 0 for the whole episode (state says "warming", nothing is commanded)
  S02 WARN   TARGET_REACHED trigger while no target temperature is defined (t_target has no value and the replay
             header records no placeholder for it)
  S03 ERROR  Controller_State TWIN_DEGRADED while Twin_Valid is VALID, or autonomous warming
             (PREDICTIVE_WARMING / ACTIVE_WARMING) entered while Twin_Valid is not VALID
  S04 INFO   SAFETY_SHUTDOWN still latched at the last frame (no reset / release is shown)
  S05 ERROR  Fault_Latched cleared without a Clinician_Reset press in the replay (when the field is present)
  S06 INFO   a module temperature rises while that channel's heater current is 0 and HW_Cutoff_i stays false
             (injected stimulus; the hardware cutoff threshold is TBD, so it is not shown tripping)
  S07 WARN   T_est discontinuity between consecutive twin updates larger than 4 combined SDs with no
             observation gap (possible stitched twin trajectory)
  S08 ERROR  Heat_i > 0 on a channel whose Module_Connected_i is false

Usage: python tools/check_replay_semantics.py integration/replays/*.jsonl.gz [--json]
"""
import argparse
import gzip
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CS = {v["name"]: v["value"] for v in json.loads((ROOT / "config" / "enums.json").read_text())["enums"]["ControllerState"]["values"]}
TVE = {v["name"]: v["value"] for v in json.loads((ROOT / "config" / "enums.json").read_text())["enums"]["TwinValid"]["values"]}
TRE = {v["name"]: v["value"] for v in json.loads((ROOT / "config" / "enums.json").read_text())["enums"]["TriggerReason"]["values"]}
WARMING_ENTRY = {CS["PREDICTIVE_WARMING"], CS["ACTIVE_WARMING"], CS["CLINICIAN_WARMING"]}
AUTONOMOUS = {CS["PREDICTIVE_WARMING"], CS["ACTIVE_WARMING"]}
NAME = {v: k for k, v in CS.items()}


def read(path):
    op = gzip.open if str(path).endswith(".gz") else open
    with op(path, "rt", encoding="utf-8") as f:
        lines = [json.loads(x) for x in f if x.strip()]
    return lines[0], lines[1:]


def target_defined(header):
    pu = header.get("params_used") or {}
    e = pu.get("t_target_degC") or {}
    if e.get("value") is not None or e.get("placeholder") is not None:
        return True
    cfg = json.loads((ROOT / "config" / "params.json").read_text())["params"]["t_target_degC"]
    return cfg.get("value") is not None


def check(path):
    header, F = read(path)
    out = []
    add = lambda sev, code, t, msg: out.append(dict(severity=sev, code=code, t_s=t, message=msg))
    # S01 episodes
    ep = None
    for f in F + [None]:
        st = None if f is None else f["ctrl"]["Controller_State"]
        if ep is not None and st != ep["state"]:
            if not ep["any_heat"]:
                add("ERROR", "S01", ep["t0"], f"{NAME[ep['state']]} for {ep['n']} s with Heat_1..4 = 0 and Demand_Global = 0 throughout")
            ep = None
        if f is None:
            break
        c = f["ctrl"]
        heat = any((c[f"Heat_{i}"] or 0) > 0 for i in range(1, 5)) or (c["Demand_Global"] or 0) > 0
        if st in WARMING_ENTRY:
            if ep is None:
                ep = dict(state=st, t0=f["meta"]["t_s"], n=0, any_heat=False)
            ep["n"] += 1
            ep["any_heat"] |= heat
    # S02
    if not target_defined(header):
        for f in F:
            if f["ctrl"]["Trigger_Reason"] == TRE["TARGET_REACHED"]:
                add("WARN", "S02", f["meta"]["t_s"], "TARGET_REACHED while t_target_degC has no value or placeholder")
    # S03  (a TWIN_DEGRADED run that overlaps VALID and ends with a TWIN_RECOVERED transition is the controller's
    #       recovery dwell - reported as INFO with its length; any other overlap is an ERROR)
    prev_st, run = None, None
    for k, f in enumerate(F):
        st, tv = f["ctrl"]["Controller_State"], f["twin"]["Twin_Valid"]
        bad = st == CS["TWIN_DEGRADED"] and tv == TVE["VALID"]
        if bad and run is None:
            run = [f["meta"]["t_s"], f["meta"]["t_s"]]
        elif bad:
            run[1] = f["meta"]["t_s"]
        if run is not None and (not bad or k == len(F) - 1):
            recovered = (not bad) and f["ctrl"]["Trigger_Reason"] == TRE["TWIN_RECOVERED"]
            n = run[1] - run[0] + 1
            if recovered:
                add("INFO", "S03", run[0], f"controller stays TWIN_DEGRADED for {n:.0f} s after Twin_Valid becomes VALID, then TWIN_RECOVERED (recovery dwell)")
            else:
                add("ERROR", "S03", run[0], f"controller TWIN_DEGRADED for {n:.0f} s while Twin_Valid is VALID, with no TWIN_RECOVERED transition")
            run = None
        if st in AUTONOMOUS and st != prev_st and tv != TVE["VALID"]:
            add("ERROR", "S03", f["meta"]["t_s"], f"{NAME[st]} entered while Twin_Valid={tv} (not VALID)")
        prev_st = st
    # S04 / S05
    if F and F[-1]["ctrl"]["Controller_State"] == CS["SAFETY_SHUTDOWN"]:
        add("INFO", "S04", F[-1]["meta"]["t_s"], "SAFETY_SHUTDOWN still latched at the last frame; no reset or release is shown")
    has_reset = "Clinician_Reset" in F[0]["ctrl"] if F else False
    for a, b in zip(F, F[1:]):
        if a["ctrl"]["Fault_Latched"] and not b["ctrl"]["Fault_Latched"]:
            if not has_reset:
                add("ERROR", "S05", b["meta"]["t_s"], "Fault_Latched cleared; replay has no Clinician_Reset field to show the reset")
            elif not any(x["ctrl"].get("Clinician_Reset") for x in F if a["meta"]["t_s"] - 5 <= x["meta"]["t_s"] <= b["meta"]["t_s"]):
                add("ERROR", "S05", b["meta"]["t_s"], "Fault_Latched cleared without a Clinician_Reset press")
    # S06
    for i in range(1, 5):
        temps = [(f["meta"]["t_s"], f["hw"][f"Module_Temp_{i}_A"], f["hw"][f"Heater_Current_{i}"], f["hw"][f"HW_Cutoff_{i}"]) for f in F]
        rise = [(t, x) for t, x, cur, cut in temps if x is not None and (cur or 0) == 0 and not cut]
        if len(rise) > 2 and rise[-1][1] - min(x for _, x in rise) > 2.0:
            lo = min(rise, key=lambda r: r[1])
            add("INFO", "S06", lo[0], f"Module_Temp_{i}_A rises {rise[-1][1] - lo[1]:.1f} degC to {rise[-1][1]:.1f} with Heater_Current_{i}=0 and HW_Cutoff_{i} never true")
    # S07
    upd = []
    for f in F:
        tw = f["twin"]
        key = (tw["T_est"], tw["T_est_sd"])
        if tw["T_est"] is not None and (not upd or upd[-1][1] != key):
            upd.append((f["meta"]["t_s"], key, f["obs"]["obs_missing"]))
    for (t0, (e0, s0), _), (t1, (e1, s1), m1) in zip(upd, upd[1:]):
        comb = math.sqrt((s0 or 0) ** 2 + (s1 or 0) ** 2)
        if comb > 0 and abs(e1 - e0) > 4 * comb and not m1:
            add("WARN", "S07", t1, f"T_est jumps {e1 - e0:+.3f} degC ({abs(e1 - e0) / comb:.1f} combined SDs) between updates")
    # S08
    for f in F:
        for i in range(1, 5):
            if (f["ctrl"][f"Heat_{i}"] or 0) > 0 and f["hw"][f"Module_Connected_{i}"] is False:
                add("ERROR", "S08", f["meta"]["t_s"], f"Heat_{i} > 0 while module {i} is disconnected")
                break
    states = sorted({NAME[f["ctrl"]["Controller_State"]] for f in F})
    max_heat = max((max(f["ctrl"][f"Heat_{i}"] or 0 for i in range(1, 5)) for f in F), default=0)
    return dict(file=str(path), scenario_id=header["scenario_id"], cohort=header.get("cohort"), frames=len(F),
                states=states, max_heat_pct=max_heat, findings=out,
                verdict="SEMANTIC_ISSUES" if any(x["severity"] == "ERROR" for x in out) else "SEMANTIC_OK")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    bad = False
    for p in a.files:
        r = check(p)
        bad |= r["verdict"] != "SEMANTIC_OK"
        if a.json:
            print(json.dumps(r))
            continue
        print(f"{r['verdict']}: {r['scenario_id']} ({r['frames']} frames, states {r['states']}, max Heat {r['max_heat_pct']} %)")
        for x in r["findings"]:
            print(f"   {x['severity']:5s} {x['code']} t={x['t_s']:.0f}s {x['message']}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
