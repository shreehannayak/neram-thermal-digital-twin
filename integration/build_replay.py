#!/usr/bin/env python3
"""Build a NERAM replay (JSONL, schema 1.0) from a twin output CSV and a controller log CSV.

Plan section 4G: twin CSV (per minute, section 4A columns) + controller CSV (1 Hz, section 1S columns)
-> one JSONL file with a header line and one frame per controller second. Twin fields are held between
minute updates. The output is validated with validate_replay.py BEFORE it is written; an invalid
replay is never produced.

HOLDOUT GUARD
  --cohort DEVELOPMENT requires --case-id and --holdout-ids (path to final_holdout_freeze/final_holdout_case_ids.csv).
  The build refuses if the case is in the final holdout. --dev-ids (development_case_ids.csv) additionally
  requires the case to be a development case. Only SYNTHETIC and DEVELOPMENT cohorts can be built.

Examples
  # development case (real observations, NERAM twin, Simulink controller log)
  python integration/build_replay.py --scenario-id SCN_A \\
      --twin integration/twin_outputs/twin_DEV_ab12.csv --ctrl integration/controller_logs/ctrl_DEV_ab12.csv \\
      --cohort DEVELOPMENT --case-id 1234 --holdout-ids /content/final_holdout_freeze/final_holdout_case_ids.csv \\
      --dev-ids /content/final_holdout_freeze/development_case_ids.csv \\
      --obs-source REAL_DEV --twin-source MODEL --scenario-info scenario_A.json --out integration/replays/SCN_A.jsonl.gz

  # synthetic (used by tools/make_synthetic_replays.py)
  python integration/build_replay.py --scenario-id SYN_SCN_B --twin t.csv --ctrl c.csv --cohort SYNTHETIC \\
      --obs-source SIMULATED --twin-source SIMULATED --placeholder --out integration/replays/SYN_SCN_B.jsonl.gz

Only the Python standard library is used.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_replay  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1.0"
DEFAULT_DISCLAIMER = ("Proof-of-concept. SIMULATED / ASSUMED PROTOTYPE RESPONSE where marked. "
                      "Not for treatment decisions. The temperature input is a patient temperature signal "
                      "(anatomical site not established), not core temperature.")

TWIN_COLUMNS = (["T_twin_s", "T_obs", "obs_missing", "T_est", "T_est_sd"]
                + [f"{p}_{h}" for h in (20, 30, 60) for p in ("T_pred", "L80", "U80", "L95", "U95")]
                + ["P_below_hypo_20", "P_below_hypo_30", "P_below_hypo_60", "P_level_shift", "P_outlier", "Twin_Valid"])
CTRL_REQUIRED = (["t_s", "Controller_State", "Degraded_Substate", "Heat_1", "Heat_2", "Heat_3", "Heat_4", "Demand_Global",
                  "Trigger_Reason", "Alert", "Safety_Shutdown", "Fault_Latched", "fault_code",
                  "Channel_Fault_1", "Channel_Fault_2", "Channel_Fault_3", "Channel_Fault_4",
                  "Data_Stale_Twin", "Data_Stale_HW", "Clinician_Mode"]
                 + [f"Module_Temp_{i}_{s}" for i in range(1, 5) for s in "AB"]
                 + [f"Module_Connected_{i}" for i in range(1, 5)]
                 + [f"Heater_Current_{i}" for i in range(1, 5)]
                 + [f"HW_Cutoff_{i}" for i in range(1, 5)]
                 + ["T_plant", "dT_heat", "plant_mode"])
CTRL_OPTIONAL = ["Clinician_Start", "Clinician_Stop", "Clinician_Reset"]
# HW -> Ctrl inputs declared in config/interface_spec.csv (owner Shreehan, destination Ctrl only). They are NOT part of
# the controller-log contract (plan section 1S), so by default a log that carries them is REFUSED like any other
# unexpected column. With --accept-ctrl-input-columns they are accepted and NOT serialized (schema 1.0 has no replay
# field for them); the builder prints a NOTE and the deviation must be stated in the scenario's limitations.
# HW_Fault_Code is the hardware-reported SYSTEM fault (codes 0-19); fault_code is the controller's highest-priority
# active fault and may be a CHANNEL code (100 x ch + k). A zero HW_Fault_Code with a non-zero fault_code is
# consistent (e.g. 206 = channel 2 OVERTEMP_SW, detected by MCU/controller).
CTRL_INPUT_ONLY = ["HW_Heartbeat_s", "HW_Fault_Code"]


class BuildError(Exception):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path, required, optional=(), input_only=()):
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames or []
        missing = [c for c in required if c not in cols]
        if missing:
            raise BuildError(f"{path}: missing columns: {', '.join(missing)}")
        allowed = set(required) | set(optional) | set(input_only)
        extra = [c for c in cols if c not in allowed]
        if extra:
            raise BuildError(f"{path}: unexpected columns (update the interface spec first): {', '.join(extra)}")
        return list(rdr), [c for c in optional if c in cols]


def num(s, col, line):
    s = (s or "").strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        v = float(s)
    except ValueError:
        raise BuildError(f"{col} line {line}: not a number: {s!r}")
    if math.isinf(v):
        raise BuildError(f"{col} line {line}: infinite value")
    return v


def integer(s, col, line):
    v = num(s, col, line)
    if v is None:
        return None
    if v != int(v):
        raise BuildError(f"{col} line {line}: expected an integer, got {s!r}")
    return int(v)


def boolean(s, col, line):
    s = (s or "").strip().lower()
    if s in ("1", "true", "1.0"):
        return True
    if s in ("0", "false", "0.0"):
        return False
    if s == "" or s == "nan":
        return None
    raise BuildError(f"{col} line {line}: expected 0/1 or true/false, got {s!r}")


def round_or_none(v, nd):
    return None if v is None else round(v, nd)


def load_ids(path):
    with open(path, newline="") as f:
        rdr = csv.DictReader(f)
        if "caseid" not in (rdr.fieldnames or []):
            raise BuildError(f"{path}: expected a 'caseid' column")
        return {int(r["caseid"]) for r in rdr}


def holdout_guard(args):
    if args.cohort not in ("SYNTHETIC", "DEVELOPMENT"):
        raise BuildError(f"cohort {args.cohort!r} cannot be built; only SYNTHETIC or DEVELOPMENT")
    if args.cohort == "DEVELOPMENT":
        if args.case_id is None or args.holdout_ids is None:
            raise BuildError("DEVELOPMENT replays require --case-id and --holdout-ids (holdout guard)")
        holdout = load_ids(args.holdout_ids)
        if args.case_id in holdout:
            raise BuildError(f"case {args.case_id} is in the FINAL HOLDOUT; it must never be replayed")
        if args.dev_ids:
            dev = load_ids(args.dev_ids)
            if args.case_id not in dev:
                raise BuildError(f"case {args.case_id} is not in the development set")
        if args.obs_source != "REAL_DEV":
            raise BuildError("DEVELOPMENT replays carry real development observations: use --obs-source REAL_DEV")
        if args.placeholder:
            raise BuildError("a DEVELOPMENT replay cannot be marked --placeholder")
    else:
        if args.obs_source == "REAL_DEV":
            raise BuildError("SYNTHETIC replays cannot carry REAL_DEV observations")


def build(args):
    holdout_guard(args)
    enums = validate_replay.load_enums(args.enums)
    no_data = enums["TwinValid"]["NO_DATA"]
    twin_rows, _ = read_csv(args.twin, TWIN_COLUMNS)
    ctrl_rows, ctrl_opt = read_csv(args.ctrl, CTRL_REQUIRED, CTRL_OPTIONAL,
                                   CTRL_INPUT_ONLY if getattr(args, "accept_ctrl_input_columns", False) else ())
    if ctrl_rows and "HW_Fault_Code" in ctrl_rows[0]:
        nz_hw = sum(1 for r in ctrl_rows if (r.get("HW_Fault_Code") or "0").strip() not in ("0", "0.0", ""))
        nz_fc = sum(1 for r in ctrl_rows if (r.get("fault_code") or "0").strip() not in ("0", "0.0", ""))
        print(f"NOTE log deviates from the section 1S contract (--accept-ctrl-input-columns): "
              f"input-only columns not serialized: HW_Heartbeat_s, HW_Fault_Code "
              f"(HW_Fault_Code non-zero rows: {nz_hw}; controller fault_code non-zero rows: {nz_fc})", file=sys.stderr)
    if not twin_rows or not ctrl_rows:
        raise BuildError("empty input CSV")

    twin = []
    for i, r in enumerate(twin_rows, start=2):
        rec = {"T_twin_s": num(r["T_twin_s"], "T_twin_s", i)}
        for c in TWIN_COLUMNS[1:]:
            if c == "obs_missing":
                rec[c] = boolean(r[c], c, i)
            elif c == "Twin_Valid":
                rec[c] = integer(r[c], c, i)
            else:
                rec[c] = num(r[c], c, i)
        if rec["T_twin_s"] is None:
            raise BuildError(f"twin CSV line {i}: T_twin_s is empty")
        twin.append(rec)
    for a, b in zip(twin, twin[1:]):
        if b["T_twin_s"] <= a["T_twin_s"]:
            raise BuildError("twin CSV: T_twin_s must be strictly increasing")

    params_used = json.loads(Path(args.params_used).read_text()) if args.params_used else None
    scenario_info = json.loads(Path(args.scenario_info).read_text()) if args.scenario_info else None
    static_context = json.loads(Path(args.static_context).read_text()) if args.static_context else None

    header = {
        "type": "header",
        "schema_version": SCHEMA_VERSION,
        "scenario_id": args.scenario_id,
        "created_utc": args.created_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "params_version": args.params_version,
        "spec_version": args.spec_version,
        "inputs": {Path(args.twin).name: sha256_file(args.twin), Path(args.ctrl).name: sha256_file(args.ctrl)},
        "disclaimer": args.disclaimer or DEFAULT_DISCLAIMER,
        "cohort": args.cohort,
    }
    if static_context is not None:
        header["static_context"] = static_context
    if args.placeholder:
        header["placeholder"] = True
    if args.generator:
        header["generator"] = args.generator
    if scenario_info is not None:
        header["scenario_info"] = scenario_info
    if params_used is not None:
        header["params_used"] = params_used

    lines = [json.dumps(header, separators=(",", ":"), ensure_ascii=False)]
    ti = 0
    for li, r in enumerate(ctrl_rows, start=2):
        t = num(r["t_s"], "t_s", li)
        if t is None:
            raise BuildError(f"ctrl CSV line {li}: t_s is empty")
        while ti + 1 < len(twin) and twin[ti + 1]["T_twin_s"] <= t:
            ti += 1
        tw = twin[ti] if twin[ti]["T_twin_s"] <= t else None
        if tw is None:
            obs = {"T_obs": None, "obs_missing": True}
            tw_out = {c: None for c in TWIN_COLUMNS[3:-1]}
            tw_out["Twin_Valid"] = no_data
        else:
            obs = {"T_obs": round_or_none(tw["T_obs"], 4), "obs_missing": bool(tw["obs_missing"])}
            tw_out = {c: round_or_none(tw[c], 5) for c in TWIN_COLUMNS[3:-1]}
            tw_out["Twin_Valid"] = tw["Twin_Valid"]
        ctrl = {}
        for c in ("Controller_State", "Degraded_Substate", "Trigger_Reason", "Alert", "fault_code",
                  "Channel_Fault_1", "Channel_Fault_2", "Channel_Fault_3", "Channel_Fault_4"):
            ctrl[c] = integer(r[c], c, li)
        for i in range(1, 5):
            ctrl[f"Heat_{i}"] = round_or_none(num(r[f"Heat_{i}"], f"Heat_{i}", li), 3)
        ctrl["Demand_Global"] = round_or_none(num(r["Demand_Global"], "Demand_Global", li), 3)
        for c in ("Safety_Shutdown", "Fault_Latched", "Clinician_Mode", "Data_Stale_Twin", "Data_Stale_HW"):
            ctrl[c] = boolean(r[c], c, li)
        for c in ctrl_opt:
            ctrl[c] = boolean(r[c], c, li)
        hw = {}
        for i in range(1, 5):
            for s in "AB":
                c = f"Module_Temp_{i}_{s}"
                hw[c] = round_or_none(num(r[c], c, li), 3)
        for i in range(1, 5):
            hw[f"Module_Connected_{i}"] = boolean(r[f"Module_Connected_{i}"], f"Module_Connected_{i}", li)
        for i in range(1, 5):
            hw[f"Heater_Current_{i}"] = round_or_none(num(r[f"Heater_Current_{i}"], f"Heater_Current_{i}", li), 4)
        for i in range(1, 5):
            hw[f"HW_Cutoff_{i}"] = boolean(r[f"HW_Cutoff_{i}"], f"HW_Cutoff_{i}", li)
        plant = {"T_plant": round_or_none(num(r["T_plant"], "T_plant", li), 4),
                 "dT_heat": round_or_none(num(r["dT_heat"], "dT_heat", li), 5),
                 "plant_mode": (r["plant_mode"] or "").strip()}
        frame = {
            "type": "frame",
            "meta": {"schema_version": SCHEMA_VERSION, "scenario_id": args.scenario_id, "t_s": t},
            "obs": obs,
            "twin": tw_out,
            "ctrl": ctrl,
            "hw": hw,
            "plant": plant,
            "src": {"obs": args.obs_source, "twin": args.twin_source, "ctrl": "SIMULATED", "hw": "SIMULATED", "plant": "ASSUMED"},
        }
        lines.append(json.dumps(frame, separators=(",", ":"), ensure_ascii=False))

    rep, _, _ = validate_replay.Validator(enums).validate_lines(lines)
    if not rep.valid:
        msgs = "\n".join(f"  {i['code']} line {i['line']} {i['field'] or ''}: {i['message']}"
                         for i in rep.issues if i["severity"] == "error")
        raise BuildError("generated replay failed validation; nothing written:\n" + msgs)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = ("\n".join(lines) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(out.parent), suffix=".tmp")
    os.close(fd)
    try:
        if str(out).endswith(".gz"):
            with open(tmp, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
                gz.write(data)
        else:
            with open(tmp, "wb") as f:
                f.write(data)
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return out, rep, len(lines) - 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario-id", required=True)
    ap.add_argument("--twin", required=True, help="twin output CSV (plan section 4A columns)")
    ap.add_argument("--ctrl", required=True, help="controller log CSV (plan section 1S columns)")
    ap.add_argument("--out", required=True, help="output .jsonl or .jsonl.gz")
    ap.add_argument("--cohort", required=True, choices=["SYNTHETIC", "DEVELOPMENT"])
    ap.add_argument("--obs-source", required=True, choices=["REAL_DEV", "SIMULATED"])
    ap.add_argument("--twin-source", required=True, choices=["MODEL", "SIMULATED"])
    ap.add_argument("--case-id", type=int)
    ap.add_argument("--holdout-ids")
    ap.add_argument("--dev-ids")
    ap.add_argument("--params-version", default="0.1")
    ap.add_argument("--spec-version", default="0.1")
    ap.add_argument("--params-used", help="JSON file with the parameter snapshot used to generate this replay")
    ap.add_argument("--scenario-info", help="JSON file: title, purpose, data_source, loop_description, limitations[]")
    ap.add_argument("--static-context", help="JSON file (development case only, if the data-use terms allow)")
    ap.add_argument("--placeholder", action="store_true", help="mark as development scaffolding")
    ap.add_argument("--accept-ctrl-input-columns", action="store_true",
                    help="accept HW_Heartbeat_s / HW_Fault_Code (declared HW->Ctrl inputs, not section-1S log columns); not serialized")
    ap.add_argument("--generator", help="free text naming the generating tool and version")
    ap.add_argument("--disclaimer")
    ap.add_argument("--created-utc", help="fixed timestamp for reproducible builds")
    ap.add_argument("--enums", default=str(ROOT / "config" / "enums.json"))
    args = ap.parse_args(argv)
    try:
        out, rep, n = build(args)
    except BuildError as ex:
        print("BUILD REFUSED:", ex, file=sys.stderr)
        return 2
    print(f"wrote {out} ({n} frames; {rep.warnings} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
