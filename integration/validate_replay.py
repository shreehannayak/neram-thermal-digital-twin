#!/usr/bin/env python3
"""Validate NERAM replay JSONL files (schema 1.0).

Implements the rules in unity/schema/VALIDATION_RULES.md with the same codes as the Unity loader
(unity_editor/Assets/Scripts/Core/ReplayValidator.cs). Field definitions come from
unity/schema/replay_fields.json; integer enum values from config/enums.json.

Usage
    python integration/validate_replay.py FILE [FILE ...] [--enums config/enums.json] [--json]
Exit status 0 when every file is valid (warnings allowed), 1 otherwise.

Only the Python standard library is used.
"""
import argparse
import gzip
import io
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS_PATH = ROOT / "unity" / "schema" / "replay_fields.json"
ENUMS_PATH = ROOT / "config" / "enums.json"

MAX_ERRORS = 200
MAX_STORED_PER_CODE = 25

HEADER_REQUIRED = ["type", "schema_version", "scenario_id", "created_utc", "params_version", "spec_version",
                   "inputs", "disclaimer", "cohort"]
HEADER_OPTIONAL = ["static_context", "placeholder", "generator", "scenario_info", "params_used"]
HEADER_PROPOSED = ["cohort", "placeholder", "generator", "scenario_info", "params_used"]
SOURCE_TAGS = ["REAL_DEV", "MODEL", "SIMULATED", "ASSUMED"]
PLANT_MODES = ["OPEN_LOOP", "STANDIN", "TWIN_IN_LOOP"]
STRING_ENUMS = {"SourceTag": SOURCE_TAGS, "PlantMode": PLANT_MODES}
HORIZONS = (20, 30, 60)
FORECAST_FIELDS = [f"{p}_{h}" for h in HORIZONS for p in ("T_pred", "L80", "U80", "L95", "U95", "P_below_hypo")]


class _BadConstant:
    """Marker for NaN/Infinity literals (rejected with E011, as in the C# loader)."""


class DuplicateKey(Exception):
    pass


def _pairs_hook(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise DuplicateKey(k)
        obj[k] = v
    return obj


def _loads(line):
    return json.loads(line, object_pairs_hook=_pairs_hook, parse_constant=lambda s: _BadConstant())


class Report:
    def __init__(self):
        self.issues = []
        self.count = {}
        self.errors = 0
        self.warnings = 0
        self.truncated = False

    def add(self, sev, code, line, field, msg):
        n = self.count.get(code, 0)
        self.count[code] = n + 1
        if sev == "error":
            self.errors += 1
        elif sev == "warning":
            self.warnings += 1
        if n < MAX_STORED_PER_CODE:
            self.issues.append({"severity": sev, "code": code, "line": line, "field": field, "message": msg})
        if sev == "error" and self.errors == MAX_ERRORS and not self.truncated:
            self.truncated = True
            self.issues.append({"severity": "error", "code": "E099", "line": line, "field": None,
                                "message": f"more than {MAX_ERRORS} errors; validation stopped"})
            self.count["E099"] = 1

    def error(self, *a):
        self.add("error", *a)

    def warn(self, *a):
        self.add("warning", *a)

    def info(self, *a):
        self.add("info", *a)

    @property
    def valid(self):
        return self.errors == 0

    @property
    def stop(self):
        return self.errors >= MAX_ERRORS


def load_fields():
    doc = json.loads(FIELDS_PATH.read_text())
    return doc


def load_enums(path=ENUMS_PATH):
    doc = json.loads(Path(path).read_text())
    enums = {}
    for name, d in doc["enums"].items():
        if d.get("type") == "string":
            continue
        enums[name] = {v["name"]: v["value"] for v in d["values"]}
    return enums


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool))


class Validator:
    def __init__(self, enums):
        doc = load_fields()
        self.doc = doc
        self.fields = doc["fields"]
        self.groups = doc["groups"]
        self.by_group = {g: [f for f in self.fields if f["group"] == g] for g in self.groups}
        self.by_key = {(f["group"], f["name"]): f for f in self.fields}
        self.src_allowed = doc["src_allowed"]
        self.versions = doc["supported_schema_versions"]
        self.cohorts = doc["header"]["cohort_allowed"]
        self.enums = enums
        self.enum_values = {k: set(v.values()) for k, v in enums.items()}
        e = enums
        self.VALID = e["TwinValid"]["VALID"]
        self.NO_DATA = e["TwinValid"]["NO_DATA"]
        self.SHUTDOWN = e["ControllerState"]["SAFETY_SHUTDOWN"]
        self.DEGRADED = e["ControllerState"]["TWIN_DEGRADED"]
        self.SUB_NONE = e["DegradedSubstate"]["NONE"]

    # -- header -----------------------------------------------------------------------------------
    def header(self, o, line, rep):
        if not isinstance(o, dict) or o.get("type") != "header":
            rep.error("E001", line, "type", 'first line must be a header object ("type": "header")')
            return None
        for name in HEADER_REQUIRED:
            if name not in o:
                if name == "cohort":
                    rep.error("E053", line, "cohort", "header.cohort is missing; it must be SYNTHETIC or DEVELOPMENT (holdout guard)")
                else:
                    rep.error("E002", line, name, "required header field missing")
                continue
            want_obj = name == "inputs"
            ok = isinstance(o[name], dict) if want_obj else isinstance(o[name], str)
            if not ok:
                rep.error("E002", line, name, "header field has the wrong JSON type (expected %s)" % ("object" if want_obj else "string"))
        for k in o:
            if k not in HEADER_REQUIRED and k not in HEADER_OPTIONAL:
                rep.error("E003", line, k, "unknown header field")
        sv = o.get("schema_version") if isinstance(o.get("schema_version"), str) else None
        if sv is not None and sv not in self.versions:
            rep.error("E071", line, "schema_version", f"unsupported schema_version '{sv}'")
        sid = o.get("scenario_id")
        if isinstance(sid, str) and len(sid) == 0:
            rep.error("E002", line, "scenario_id", "scenario_id is empty")
        disc = o.get("disclaimer")
        if isinstance(disc, str) and len(disc.strip()) == 0:
            rep.error("E002", line, "disclaimer", "disclaimer is empty")
        coh = o.get("cohort") if isinstance(o.get("cohort"), str) else None
        if coh is not None and coh not in self.cohorts:
            rep.error("E052", line, "cohort", f"cohort '{coh}' is not allowed; only SYNTHETIC or DEVELOPMENT may be displayed")
        if isinstance(o.get("inputs"), dict):
            for k, v in o["inputs"].items():
                if not isinstance(v, str):
                    rep.error("E002", line, "inputs." + k, "input hash must be a string")
        sc = o.get("static_context")
        if "static_context" in o and sc is not None and not isinstance(sc, dict):
            rep.error("E002", line, "static_context", "static_context must be an object or null")
        if "placeholder" in o and not isinstance(o["placeholder"], bool):
            rep.error("E002", line, "placeholder", "placeholder must be true/false")
        if "generator" in o and not isinstance(o["generator"], str):
            rep.error("E002", line, "generator", "generator must be a string")
        if "scenario_info" in o:
            si = o["scenario_info"]
            if not isinstance(si, dict):
                rep.error("E002", line, "scenario_info", "scenario_info must be an object")
            elif isinstance(si.get("limitations"), list):
                for l in si["limitations"]:
                    if not isinstance(l, str):
                        rep.error("E002", line, "scenario_info.limitations", "limitations must be strings")
        if "params_used" in o and not isinstance(o["params_used"], dict):
            rep.error("E002", line, "params_used", "params_used must be an object")
        proposed = [f for f in HEADER_PROPOSED if f in o]
        if proposed:
            rep.info("I201", line, None, "proposed header fields present: " + ", ".join(proposed))
        if o.get("placeholder") is True:
            rep.info("I202", line, "placeholder", "placeholder file")
        return o

    # -- frames -----------------------------------------------------------------------------------
    def validate_lines(self, lines):
        rep = Report()
        header = None
        rows = []
        state = {"first_step": None, "prev_plant": None, "prev_tags": {}, "proposed_noted": False}
        line_no = 0
        fatal = False
        for raw in lines:
            line_no += 1
            if not raw.strip():
                continue
            try:
                obj = _loads(raw)
            except DuplicateKey as ex:
                rep.error("E093", line_no, None, f"duplicate key: {ex}")
                if header is None:
                    fatal = True
            except ValueError as ex:
                rep.error("E090", line_no, None, f"invalid JSON: {ex}")
                if header is None:
                    fatal = True
            else:
                if not isinstance(obj, dict):
                    rep.error("E091", line_no, None, "line is not a JSON object")
                    if header is None:
                        fatal = True
                elif header is None:
                    header = self.header(obj, line_no, rep)
                    if header is None:
                        fatal = True
                else:
                    t = obj.get("type")
                    if not isinstance(t, str):
                        rep.error("E092", line_no, "type", 'frame line must have "type": "frame"')
                    elif t == "header":
                        rep.error("E092", line_no, "type", "second header line")
                    elif t != "frame":
                        rep.error("E092", line_no, "type", f"unknown line type '{t}'")
                    else:
                        rows.append(self.frame(obj, line_no, rep, header, rows, state))
            if fatal or rep.stop:
                break
        if header is None and not any(c in rep.count for c in ("E001", "E090", "E091", "E093")):
            rep.error("E001", 0, None, "empty file: no header line")
        if header is not None and len(rows) < 2:
            rep.error("E021", 0, None, f"a replay needs at least 2 frames (found {len(rows)})")
        return rep, header, rows

    def _read(self, go, f, line, rep, header, state):
        name = f["name"]
        key = f"{f['group']}.{name}"
        if name not in go:
            if not f.get("optional"):
                rep.error("E010", line, key, "field missing")
            return None
        if f.get("proposed") and not state["proposed_noted"]:
            state["proposed_noted"] = True
            rep.info("I201", line, key, "proposed frame field present")
        v = go[name]
        if v is None:
            if not f["nullable"]:
                rep.error("E012", line, key, "null is not allowed")
            return None
        k = f["kind"]
        if isinstance(v, _BadConstant):
            rep.error("E011", line, key, "NaN/Infinity literals are not allowed; use null")
            return None
        if k == "number":
            if not _is_num(v):
                rep.error("E011", line, key, "wrong JSON type (expected number)")
                return None
            val = float(v)
            if math.isnan(val) or math.isinf(val):
                rep.error("E011", line, key, "NaN/Infinity literals are not allowed; use null")
                return None
        elif k in ("int", "enum"):
            if not _is_int(v):
                rep.error("E011", line, key, "wrong JSON type (expected integer)")
                return None
            val = v
        elif k == "bool":
            if not isinstance(v, bool):
                rep.error("E011", line, key, "wrong JSON type (expected true/false)")
                return None
            val = 1.0 if v else 0.0
        elif k == "string":
            if not isinstance(v, str):
                rep.error("E011", line, key, "wrong JSON type (expected string)")
                return None
            if name == "schema_version" and v != header.get("schema_version"):
                rep.error("E071", line, key, "frame schema_version differs from header")
            if name == "scenario_id" and v != header.get("scenario_id"):
                rep.error("E070", line, key, "frame scenario_id differs from header")
            return None
        elif k == "string_enum":
            if not isinstance(v, str):
                rep.error("E011", line, key, "wrong JSON type (expected string)")
                return None
            allowed_all = STRING_ENUMS[f["enum"]]
            if v not in allowed_all:
                rep.error("E014", line, key, f"unknown {f['enum']} '{v}'")
                return None
            if f["group"] == "src" and v not in self.src_allowed[name]:
                rep.error("E050", line, key, f"source tag '{v}' not allowed for group {name}")
            return v
        else:
            return None
        mode = f.get("range_mode", "none")
        if mode != "none":
            lo, hi = f.get("min"), f.get("max")
            if (lo is not None and val < lo) or (hi is not None and val > hi):
                msg = f"value {val} outside [{lo}, {hi}]"
                if mode == "error":
                    rep.error("E013", line, key, msg)
                else:
                    rep.warn("W102", line, key, msg)
        if k == "enum" and val not in self.enum_values.get(f["enum"], set()):
            rep.error("E014", line, key, f"value {val} is not defined in {f['enum']}")
        return val

    def frame(self, obj, line, rep, header, rows, state):
        row = {}
        for k in obj:
            if k != "type" and k not in self.groups:
                rep.error("E080", line, k, "unknown group")
        for g in self.groups:
            if g not in obj:
                rep.error("E010", line, g, "group missing")
                continue
            go = obj[g]
            if not isinstance(go, dict):
                rep.error("E011", line, g, "group must be an object")
                continue
            for k in go:
                if (g, k) not in self.by_key:
                    rep.error("E080", line, f"{g}.{k}", "unknown field")
            for f in self.by_group[g]:
                row[(g, f["name"])] = self._read(go, f, line, rep, header, state)
        self.cross(row, line, rep, header, rows, state)
        return row

    def cross(self, r, line, rep, header, rows, state):
        g = lambda grp, name: r.get((grp, name))
        t = g("meta", "t_s")
        if t is not None and rows:
            pt = rows[-1].get(("meta", "t_s"))
            if pt is not None:
                step = t - pt
                if step <= 0:
                    rep.error("E020", line, "meta.t_s", "t_s must be strictly increasing")
                elif state["first_step"] is None:
                    state["first_step"] = step
                elif abs(step - state["first_step"]) > 1e-6:
                    rep.warn("W101", line, "meta.t_s", f"non-uniform step {step} s")
        om = g("obs", "obs_missing")
        if om is not None:
            missing = om > 0.5
            if missing != (g("obs", "T_obs") is None):
                rep.error("E060", line, "obs.T_obs", "obs_missing and T_obs disagree")
        tv = g("twin", "Twin_Valid")
        if tv is not None:
            if tv == self.NO_DATA:
                if g("twin", "T_est") is not None or g("twin", "T_est_sd") is not None:
                    rep.error("E043", line, "twin.T_est", "Twin_Valid NO_DATA requires T_est and T_est_sd to be null")
            elif g("twin", "T_est") is None or g("twin", "T_est_sd") is None:
                rep.error("E044", line, "twin.T_est", "T_est and T_est_sd are required unless Twin_Valid is NO_DATA")
            vals = [g("twin", n) for n in FORECAST_FIELDS]
            if tv != self.VALID:
                present = sum(v is not None for v in vals)
                if present:
                    rep.error("E040", line, "twin.forecast", f"{present} forecast field(s) present while Twin_Valid is not VALID")
            else:
                missing = sum(v is None for v in vals)
                if missing:
                    rep.error("E041", line, "twin.forecast", f"{missing} forecast field(s) null while Twin_Valid is VALID")
                else:
                    for h in HORIZONS:
                        m, l80, u80, l95, u95 = (g("twin", f"{p}_{h}") for p in ("T_pred", "L80", "U80", "L95", "U95"))
                        if not (l95 <= l80 <= u80 <= u95):
                            rep.error("E042", line, f"twin.+{h}", "interval bounds must satisfy L95 <= L80 <= U80 <= U95")
                        elif m < l80 or m > u80:
                            rep.warn("W103", line, f"twin.T_pred_{h}", "forecast mean outside its 80% interval")
        st = g("ctrl", "Controller_State")
        if st is not None:
            in_sd = st == self.SHUTDOWN
            sf = g("ctrl", "Safety_Shutdown")
            if sf is not None and (sf > 0.5) != in_sd:
                rep.error("E031", line, "ctrl.Safety_Shutdown", "Safety_Shutdown must be true exactly in SAFETY_SHUTDOWN")
            if in_sd:
                for i in range(1, 5):
                    h = g("ctrl", f"Heat_{i}")
                    if h is not None and h > 0:
                        rep.error("E030", line, f"ctrl.Heat_{i}", "heating command > 0 during SAFETY_SHUTDOWN")
            sub = g("ctrl", "Degraded_Substate")
            if sub is not None and ((sub != self.SUB_NONE) != (st == self.DEGRADED)):
                rep.warn("W104", line, "ctrl.Degraded_Substate", "Degraded_Substate inconsistent with Controller_State")
        for i in range(1, 5):
            c = g("ctrl", f"Channel_Fault_{i}")
            if c is None or c == 0:
                continue
            lo, hi = 100 * i + 1, 100 * i + 99
            if c < lo or c > hi:
                rep.error("E032", line, f"ctrl.Channel_Fault_{i}", f"channel fault code {c} outside {lo}-{hi}")
            h = g("ctrl", f"Heat_{i}")
            if h is not None and h > 0:
                rep.error("E033", line, f"ctrl.Heat_{i}", f"faulted channel {i} has a heating command > 0")
        mode = g("plant", "plant_mode")
        if mode is not None:
            if mode == "OPEN_LOOP" and (g("plant", "T_plant") is not None or g("plant", "dT_heat") is not None):
                rep.error("E061", line, "plant.plant_mode", "OPEN_LOOP requires T_plant and dT_heat to be null")
            if mode != "OPEN_LOOP" and (g("plant", "T_plant") is None or g("plant", "dT_heat") is None):
                rep.warn("W108", line, "plant.plant_mode", f"{mode} with T_plant or dT_heat null")
            if state["prev_plant"] is not None and state["prev_plant"] != mode:
                rep.warn("W107", line, "plant.plant_mode", f"plant_mode changed from {state['prev_plant']} to {mode}")
            state["prev_plant"] = mode
        for grp in ("obs", "twin", "ctrl", "hw", "plant"):
            tag = g("src", grp)
            if tag is None:
                continue
            if grp == "obs" and tag == "REAL_DEV":
                if header.get("cohort") != "DEVELOPMENT":
                    rep.error("E051", line, "src.obs", "REAL_DEV observations require header.cohort DEVELOPMENT")
                if header.get("placeholder") is True:
                    rep.error("E054", line, "src.obs", "a placeholder file must not contain REAL_DEV observations")
            prev = state["prev_tags"].get(grp)
            if prev is not None and prev != tag:
                rep.warn("W106", line, f"src.{grp}", f"source tag changed from {prev} to {tag}")
            state["prev_tags"][grp] = tag


def open_text(path):
    p = str(path)
    if p.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(p, "rb"), encoding="utf-8-sig")
    return open(p, "r", encoding="utf-8-sig")


def validate_file(path, enums=None):
    enums = enums or load_enums()
    v = Validator(enums)
    with open_text(path) as fh:
        rep, header, rows = v.validate_lines(fh)
    return rep, header, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--enums", default=str(ENUMS_PATH))
    ap.add_argument("--json", action="store_true", help="print a JSON summary per file")
    args = ap.parse_args(argv)
    enums = load_enums(args.enums)
    ok = True
    for f in args.files:
        rep, header, rows = validate_file(f, enums)
        ok &= rep.valid
        if args.json:
            print(json.dumps({"file": f, "valid": rep.valid, "errors": rep.errors, "warnings": rep.warnings,
                              "codes": rep.count, "frames": len(rows)}))
        else:
            status = "VALID" if rep.valid else "INVALID"
            print(f"{status}: {f} ({len(rows)} frames, {rep.errors} errors, {rep.warnings} warnings)")
            for i in rep.issues:
                if i["severity"] != "info" or not rep.valid:
                    print(f"  {i['code']} [{i['severity']}] line {i['line']} {i['field'] or ''}: {i['message']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
