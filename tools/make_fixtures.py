#!/usr/bin/env python3
"""Generate the replay validation fixture corpus used by BOTH validators.

Writes unity_editor/Assets/Tests/Fixtures/*.jsonl and fixtures_manifest.json. Each fixture is a small valid base
replay with exactly one mutation; the manifest lists whether it must be valid and the exact set of ERROR codes
(plus the warning codes) that must be reported. The Unity EditMode tests (ReplayValidatorFixtureTests) and the
Python tests (tests/test_validate_replay.py) assert the same expectations, so the C# and Python validators
cannot drift apart.

Base frames are taken from the deterministic synthetic replay SYN_SCN_C (run make_synthetic_replays.py first).
"""
import copy
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "unity_editor" / "Assets" / "Tests" / "Fixtures"
SRC = ROOT / "integration" / "replays" / "SYN_SCN_C.jsonl.gz"


def load_base():
    lines = gzip.open(SRC, "rt", encoding="utf-8").read().splitlines()
    header = json.loads(lines[0])
    frames = [json.loads(l) for l in lines[1:]]
    return header, frames


def dump(path, header, frames, raw_lines=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    out = []
    if header is not None:
        out.append(json.dumps(header, separators=(",", ":")))
    out += [json.dumps(f, separators=(",", ":")) for f in frames]
    if raw_lines:
        for idx, text in raw_lines:
            out.insert(idx, text)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main():
    header, frames = load_base()
    by_t = {int(f["meta"]["t_s"]): f for f in frames}
    valid_frames = [copy.deepcopy(by_t[t]) for t in (1800, 1801, 1802, 1803)]      # minute 30: VALID, clinician warming
    init_frames = [copy.deepcopy(by_t[t]) for t in (60, 61, 62)]                    # minute 1: INITIALISING
    shutdown_frames = [copy.deepcopy(by_t[t]) for t in (2760, 2761, 2762)]          # minute 46: SAFETY_SHUTDOWN
    h = copy.deepcopy(header)
    h["scenario_info"]["title"] = "Fixture"
    for f in valid_frames + init_frames + shutdown_frames:
        f["meta"]["scenario_id"] = h["scenario_id"]

    manifest = []

    def fx(name, valid, errors=(), warnings=(), header_=None, frames_=None, raw=None, header_none=False, text=None):
        p = OUT / f"{name}.jsonl"
        if text is not None:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        else:
            dump(p, None if header_none else (header_ if header_ is not None else h),
                 frames_ if frames_ is not None else valid_frames, raw)
        manifest.append({"file": p.name, "valid": valid, "errors": sorted(errors), "warnings": sorted(warnings)})

    def mut(fn, frames_src=None):
        fr = copy.deepcopy(frames_src or valid_frames)
        fn(fr)
        return fr

    def hmut(fn):
        hh = copy.deepcopy(h)
        fn(hh)
        return hh

    # ---- valid files ----
    fx("valid_minimal", True)
    fx("valid_initialising", True, frames_=init_frames)
    fx("valid_shutdown", True, frames_=shutdown_frames)
    gz = OUT / "valid_minimal_gz.jsonl.gz"
    with open(gz, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as g:
        g.write((OUT / "valid_minimal.jsonl").read_bytes())
    manifest.append({"file": gz.name, "valid": True, "errors": [], "warnings": []})

    # ---- file structure ----
    fx("E001_no_header", False, ["E001"], header_none=True)
    fx("E001_empty_file", False, ["E001"], text="")
    fx("E090_invalid_json", False, ["E090"], raw=[(2, '{"type":"frame",')])
    fx("E091_array_line", False, ["E091"], raw=[(2, "[1,2,3]")])
    fx("E092_second_header", False, ["E092"], raw=[(2, json.dumps(h, separators=(",", ":")))])
    fx("E092_missing_type", False, ["E092"], frames_=mut(lambda fr: fr[1].pop("type")))
    fx("E093_duplicate_key", False, ["E093"], raw=[(2, json.dumps(valid_frames[0], separators=(",", ":"))[:-1] + ',"type":"frame"}')])
    fx("E021_one_frame", False, ["E021"], frames_=valid_frames[:1])

    # Non-standard JSON that Newtonsoft.Json would accept but Python (and RFC 8259) rejects: must be E090 in both.
    line1 = json.dumps(valid_frames[1], separators=(",", ":"))
    lenient = {
        "E090_single_quotes": line1.replace('"type":"frame"', "'type':'frame'"),
        "E090_unquoted_key": line1.replace('"type":', "type:"),
        "E090_trailing_comma": line1[:-1] + ",}",
        "E090_hex_number": line1.replace('"fault_code":0', '"fault_code":0x0'),
        "E090_leading_zero": line1.replace('"fault_code":0', '"fault_code":00'),
        "E090_comment": line1 + " /* note */",
        "E090_undefined": line1.replace('"T_plant":', '"T_plant":undefined,"x":'),
        "E090_trailing_content": line1 + " {}",
    }
    for name, text in lenient.items():
        fx(name, False, ["E090"], raw=[(2, text)], frames_=[valid_frames[0], valid_frames[2], valid_frames[3]])

    # ---- header / cohort / holdout guard ----
    fx("E002_header_missing_disclaimer", False, ["E002"], header_=hmut(lambda x: x.pop("disclaimer")))
    fx("E003_header_unknown_field", False, ["E003"], header_=hmut(lambda x: x.__setitem__("case_id", 1234)))
    fx("E053_cohort_missing", False, ["E053"], header_=hmut(lambda x: x.pop("cohort")))
    fx("E052_cohort_holdout", False, ["E052"], header_=hmut(lambda x: x.__setitem__("cohort", "HOLDOUT")))
    fx("E051_real_dev_in_synthetic", False, ["E051"], header_=hmut(lambda x: x.pop("placeholder")),
       frames_=mut(lambda fr: [f["src"].__setitem__("obs", "REAL_DEV") for f in fr]))

    def dev_placeholder(x):
        x["cohort"] = "DEVELOPMENT"
    fx("E054_placeholder_with_real_dev", False, ["E054"], header_=hmut(dev_placeholder),
       frames_=mut(lambda fr: [f["src"].__setitem__("obs", "REAL_DEV") for f in fr]))
    fx("E071_frame_schema_version", False, ["E071"], frames_=mut(lambda fr: fr[2]["meta"].__setitem__("schema_version", "2.0")))
    fx("E071_header_schema_version", False, ["E071"], header_=hmut(lambda x: x.__setitem__("schema_version", "9.9")),
       frames_=mut(lambda fr: [f["meta"].__setitem__("schema_version", "9.9") for f in fr]))
    fx("E070_scenario_mismatch", False, ["E070"], frames_=mut(lambda fr: fr[1]["meta"].__setitem__("scenario_id", "OTHER")))

    # ---- fields ----
    fx("E010_field_missing", False, ["E010"], frames_=mut(lambda fr: fr[1]["ctrl"].pop("Alert")))
    fx("E010_group_missing", False, ["E010"], frames_=mut(lambda fr: fr[1].pop("hw")))
    fx("E080_unknown_field", False, ["E080"], frames_=mut(lambda fr: fr[1]["twin"].__setitem__("T_core", 37.0)))
    fx("E080_unknown_group", False, ["E080"], frames_=mut(lambda fr: fr[1].__setitem__("extra", {})))
    fx("E011_bool_as_int", False, ["E011"], frames_=mut(lambda fr: fr[1]["obs"].__setitem__("obs_missing", 0)))
    fx("E011_enum_as_float", False, ["E011"], frames_=mut(lambda fr: fr[1]["ctrl"].__setitem__("Controller_State", 4.0)))
    fx("E011_nan_literal", False, ["E011", "E060"], raw=[(2, json.dumps(valid_frames[1], separators=(",", ":")).replace(
        '"T_obs":' + json.dumps(valid_frames[1]["obs"]["T_obs"]), '"T_obs":NaN'))], frames_=[valid_frames[0], valid_frames[2], valid_frames[3]])
    fx("E012_null_heat", False, ["E012"], frames_=mut(lambda fr: fr[1]["ctrl"].__setitem__("Heat_1", None)))
    fx("E013_tobs_out_of_range", False, ["E013"], frames_=mut(lambda fr: fr[1]["obs"].__setitem__("T_obs", 50.0)))
    fx("E013_heat_over_100", False, ["E013"], frames_=mut(lambda fr: fr[1]["ctrl"].__setitem__("Heat_2", 120.0)))
    fx("E013_probability_over_1", False, ["E013"], frames_=mut(lambda fr: fr[1]["twin"].__setitem__("P_outlier", 1.2)))
    fx("E014_unknown_state", False, ["E014"], frames_=mut(lambda fr: fr[1]["ctrl"].__setitem__("Controller_State", 9)))
    fx("E014_unknown_plant_mode", False, ["E014"], frames_=mut(lambda fr: fr[1]["plant"].__setitem__("plant_mode", "CLOSED")))
    fx("E050_ctrl_tag_model", False, ["E050"], frames_=mut(lambda fr: [f["src"].__setitem__("ctrl", "MODEL") for f in fr]))
    fx("W102_test_soft_range", True, warnings=["W102"], frames_=mut(lambda fr: fr[1]["twin"].__setitem__("T_est", 43.5)))

    # ---- time ----
    fx("E020_time_not_increasing", False, ["E020"], frames_=mut(lambda fr: fr[2]["meta"].__setitem__("t_s", fr[1]["meta"]["t_s"])))
    fx("W101_nonuniform_step", True, warnings=["W101"], frames_=mut(lambda fr: fr[3]["meta"].__setitem__("t_s", fr[3]["meta"]["t_s"] + 4)))

    # ---- observation / twin ----
    fx("E060_obs_missing_mismatch", False, ["E060"], frames_=mut(lambda fr: fr[1]["obs"].__setitem__("obs_missing", True)))

    def nodata_with_est(fr):
        fr[1]["twin"]["Twin_Valid"] = 0
        for k in [k for k in fr[1]["twin"] if k.startswith(("T_pred", "L80", "U80", "L95", "U95", "P_below"))]:
            fr[1]["twin"][k] = None
    fx("E043_nodata_with_estimate", False, ["E043"], frames_=mut(nodata_with_est))
    fx("E044_estimate_missing", False, ["E044"], frames_=mut(lambda fr: fr[1]["twin"].__setitem__("T_est", None)))
    fx("E040_forecast_when_initialising", False, ["E040"], frames_=mut(lambda fr: fr[1]["twin"].__setitem__("T_pred_20", 36.1), init_frames))
    fx("E041_forecast_missing_when_valid", False, ["E041"], frames_=mut(lambda fr: fr[1]["twin"].__setitem__("U95_60", None)))

    def bad_interval(fr):
        t = fr[1]["twin"]
        t["L80_30"], t["U80_30"] = t["U80_30"], t["L80_30"]
    fx("E042_interval_order", False, ["E042"], frames_=mut(bad_interval))

    def mean_outside(fr):
        t = fr[1]["twin"]
        t["T_pred_20"] = (t["U80_20"] + t["U95_20"]) / 2
    fx("W103_mean_outside_80", True, warnings=["W103"], frames_=mut(mean_outside))

    # ---- controller / hardware consistency ----
    fx("E030_heat_in_shutdown", False, ["E030"], frames_=mut(lambda fr: fr[1]["ctrl"].__setitem__("Heat_1", 10.0), shutdown_frames))
    fx("E031_shutdown_flag_mismatch", False, ["E031"], frames_=mut(lambda fr: fr[1]["ctrl"].__setitem__("Safety_Shutdown", False), shutdown_frames))
    fx("E032_channel_code_range", False, ["E032"], frames_=mut(lambda fr: fr[1]["ctrl"].__setitem__("Channel_Fault_2", 106), shutdown_frames))

    def faulted_heat(fr):
        fr[1]["ctrl"]["Channel_Fault_2"] = 203
    fx("E033_faulted_channel_heat", False, ["E033"], frames_=mut(faulted_heat))
    fx("W104_substate_inconsistent", True, warnings=["W104"], frames_=mut(lambda fr: fr[1]["ctrl"].__setitem__("Degraded_Substate", 1)))

    # ---- plant / tags ----
    def open_loop_with_plant(fr):
        for f in fr:
            f["plant"]["plant_mode"] = "OPEN_LOOP"
    fx("E061_open_loop_with_plant", False, ["E061"], frames_=mut(open_loop_with_plant))
    fx("W108_standin_without_plant", True, warnings=["W108"], frames_=mut(lambda fr: fr[1]["plant"].__setitem__("T_plant", None)))

    def mode_change(fr):
        for f in fr[2:]:
            f["plant"]["plant_mode"] = "OPEN_LOOP"
            f["plant"]["T_plant"] = None
            f["plant"]["dT_heat"] = None
    fx("W107_plant_mode_change", True, warnings=["W107"], frames_=mut(mode_change))
    fx("W106_tag_change", True, warnings=["W106"], frames_=mut(lambda fr: [f["src"].__setitem__("twin", "MODEL") for f in fr[2:]]))

    (OUT / "fixtures_manifest.json").write_text(json.dumps({
        "note": "Generated by tools/make_fixtures.py. 'errors' is the exact set of error codes; 'warnings' must be present.",
        "fixtures": manifest}, indent=1) + "\n")
    print(f"wrote {len(manifest)} fixtures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
