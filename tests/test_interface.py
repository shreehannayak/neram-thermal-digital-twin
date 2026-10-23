"""Plan section 7 tests/test_interface.py: the shared contract (config/interface_spec.csv, config/enums.json,
config/params.json) against the plan (sections 0.4, 0.5, 4A, 4F, 1S, 6) and against its consumers (Python
exporter / builder, replay field registry, the C# built-in enum fallback).
Run: python -m pytest -q tests   or   python tests/test_interface.py   (standard library only)"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integration"))
import build_replay  # noqa: E402

# Plan section 0.4 (FROZEN names; integers as written in the plan)
PLAN_ENUMS = {
    "ControllerState": ["NORMAL", "PREDICTIVE_WARMING", "ACTIVE_WARMING", "TARGET_MAINTENANCE",
                        "CLINICIAN_WARMING", "TWIN_DEGRADED", "SAFETY_SHUTDOWN"],
    "TwinValid": ["NO_DATA", "INITIALISING", "VALID", "DEGRADED"],
    "TriggerReason": ["NONE", "FORECAST_P20", "FORECAST_P30", "TEST_BELOW_HYPO", "CLINICIAN_START", "TARGET_REACHED",
                      "TARGET_LOST", "CLINICIAN_STOP", "SAFETY_FAULT", "TWIN_DEGRADED", "TWIN_RECOVERED",
                      "CLINICIAN_RESET"],
    "AlertCode": ["NONE", "FORECAST_RISK_20_30", "FORECAST_RISK_60_INFO", "TWIN_DEGRADED", "CHANNEL_FAULT",
                  "SAFETY_SHUTDOWN", "DATA_STALE", "CLINICIAN_STOP_ACK", "RESET_BLOCKED"],
}
PLAN_SOURCE_TAGS = ["REAL_DEV", "MODEL", "SIMULATED", "ASSUMED"]
PLAN_PLANT_MODES = ["OPEN_LOOP", "STANDIN", "TWIN_IN_LOOP"]
# Plan section 1S controller-log columns, in order
PLAN_CTRL_LOG = (["t_s", "Controller_State", "Degraded_Substate", "Heat_1", "Heat_2", "Heat_3", "Heat_4",
                  "Demand_Global", "Trigger_Reason", "Alert", "Safety_Shutdown", "Fault_Latched", "fault_code",
                  "Channel_Fault_1", "Channel_Fault_2", "Channel_Fault_3", "Channel_Fault_4", "Data_Stale_Twin",
                  "Data_Stale_HW", "Clinician_Mode"]
                 + [f"Module_Temp_{i}_{s}" for i in range(1, 5) for s in "AB"]
                 + [f"Module_Connected_{i}" for i in range(1, 5)] + [f"Heater_Current_{i}" for i in range(1, 5)]
                 + [f"HW_Cutoff_{i}" for i in range(1, 5)] + ["T_plant", "dT_heat", "plant_mode"])
# Plan section 4A twin CSV columns
PLAN_TWIN = (["T_twin_s", "T_obs", "obs_missing", "T_est", "T_est_sd"]
             + [f"{p}_{h}" for h in (20, 30, 60) for p in ("T_pred", "L80", "U80", "L95", "U95")]
             + [f"P_below_hypo_{h}" for h in (20, 30, 60)] + ["P_level_shift", "P_outlier", "Twin_Valid"])
# Plan section 6: parameter owners (rows listed in the plan)
PLAN_OWNERS = {
    "Sai": ["t_hypo_degC", "t_target_degC", "p_trigger", "p_release", "n_confirm_updates", "sd_degrade_degC",
            "ts_twin_s", "data_stale_twin_s", "k_heat_degC_per_h", "tau_heat_min", "w_ch", "r_obs_degC2"],
    "Suchita": ["band_target_degC", "t_dwell_min_s", "t_recover_s", "t_stop_inhibit_s", "d_pred_max_pct",
                 "d_active_max_pct", "d_maint_max_pct", "d_fallback_pct", "kp_pct_per_degC", "ki_pct_per_degC_s",
                 "ts_ctrl_s", "sd_mod_sensor_degC", "tau_mod_s", "k_mod_degC", "t_skin_base_degC",
                 "sd_standin_degC", "tau_standin_s"],
    "Shreehan": ["data_stale_hw_s", "t_surface_limit_degC", "t_mod_derate_degC", "t_mod_trip_degC",
                 "t_mod_reset_degC", "t_hw_cutoff_degC", "p_max_ch_W", "p_max_ch_pct", "heater_r_ohm",
                 "heater_power_density_W_cm2", "v_bus_V", "i_on_A", "i_open_max_A", "i_over_A", "i_stuck_A",
                 "sensor_accuracy_degC", "sensor_sample_rate_Hz", "dt_sensor_disagree_degC", "wdt_timeout_ms",
                 "host_heartbeat_timeout_s", "hw_status_period_s", "pwm_freq_Hz"],
}
SPEC_COLUMNS = ["signal", "source", "destination", "meaning", "unit", "type", "rate", "range_or_enum", "missing",
                "fault_representation", "owner", "status"]


def enums():
    return json.loads((ROOT / "config" / "enums.json").read_text(encoding="utf-8"))


def spec_rows():
    return list(csv.DictReader(open(ROOT / "config" / "interface_spec.csv", newline="", encoding="utf-8")))


def params():
    return json.loads((ROOT / "config" / "params.json").read_text(encoding="utf-8"))


def test_enums_match_plan_section_0_4():
    e = enums()["enums"]
    for name, names in PLAN_ENUMS.items():
        got = [(v["value"], v["name"]) for v in e[name]["values"]]
        assert got == list(enumerate(names)), (name, got)
    assert [v["value"] for v in e["SourceTag"]["values"]] == PLAN_SOURCE_TAGS
    assert [v["value"] for v in e["PlantMode"]["values"]] == PLAN_PLANT_MODES
    assert enums().get("spec_version")


def test_csharp_builtin_enum_fallback_matches_config():
    """Unity's EnumRegistry carries a built-in copy of enums.json; names and integers must be identical."""
    src = (ROOT / "unity_editor" / "Assets" / "Scripts" / "Core" / "EnumRegistry.cs").read_text(encoding="utf-8")
    m = re.search(r'@"(\{.*?\})";', src, re.S)
    assert m, "built-in enum JSON not found in EnumRegistry.cs"
    builtin = json.loads(m.group(1).replace('""', '"'))
    b = builtin.get("enums", builtin)
    for name in PLAN_ENUMS:
        assert [(v["value"], v["name"]) for v in b[name]["values"]] == \
               [(v["value"], v["name"]) for v in enums()["enums"][name]["values"]], name


def test_interface_spec_rows_complete_and_unique():
    rows = spec_rows()
    assert rows and all(c in rows[0] for c in SPEC_COLUMNS)
    names = [r["signal"] for r in rows]
    assert len(names) == len(set(names))
    for r in rows:
        for c in SPEC_COLUMNS:
            assert r[c].strip() != "", (r["signal"], c)
        if r["type"].startswith("double"):
            assert "-999" not in r["missing"] and r["missing"].strip() not in ("0",), r["signal"]


def test_twin_columns_agree_everywhere():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tre_cols", ROOT / "integration" / "validate_twin_output.py")
    vto = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vto)
    spec_twin = [r["signal"] for r in spec_rows() if r["source"].startswith("Twin") and r["rate"].strip() == "1/60 Hz"]
    assert set(spec_twin) == set(PLAN_TWIN)
    assert list(build_replay.TWIN_COLUMNS) == PLAN_TWIN
    assert list(vto.TWIN_COLUMNS) == PLAN_TWIN
    src = (ROOT / "src" / "twin_replay_export.py").read_text(encoding="utf-8")
    assert "TWIN_COLUMNS = (" in src            # the exporter defines the same list (checked byte-free below)
    for r in spec_rows():
        if r["signal"] in PLAN_TWIN and r["signal"] not in ("T_twin_s", "obs_missing", "Twin_Valid"):
            assert r["rate"].strip() == "1/60 Hz"


def test_controller_log_contract_section_1s():
    req = list(build_replay.CTRL_REQUIRED)
    assert sorted(req) == sorted(PLAN_CTRL_LOG)
    signals = {r["signal"] for r in spec_rows()}
    for c in PLAN_CTRL_LOG:
        assert c in signals, c
    for r in spec_rows():
        if r["signal"] in ("HW_Heartbeat_s", "HW_Fault_Code"):
            assert r["destination"].strip() == "Ctrl" and r["replay_group"].strip() == ""
    for c in ("Heat_1", "Controller_State", "Module_Temp_1_A"):
        assert next(r for r in spec_rows() if r["signal"] == c)["rate"].strip() == "1 Hz"


def test_replay_field_registry_matches_plan_section_4f():
    f = json.loads((ROOT / "unity" / "schema" / "replay_fields.json").read_text(encoding="utf-8"))
    groups = {g: [x["name"] for x in f["fields"] if x["group"] == g] for g in ("meta", "obs", "twin", "ctrl", "hw", "plant", "src")}
    assert groups["meta"] == ["schema_version", "scenario_id", "t_s"]
    assert groups["obs"] == ["T_obs", "obs_missing"]
    assert set(groups["twin"]) == set(PLAN_TWIN) - {"T_twin_s", "T_obs", "obs_missing"}
    assert set(groups["hw"]) == {c for c in PLAN_CTRL_LOG if c.startswith(("Module_", "Heater_", "HW_Cutoff"))}
    assert groups["plant"] == ["T_plant", "dT_heat", "plant_mode"]
    assert groups["src"] == ["obs", "twin", "ctrl", "hw", "plant"]


def test_params_structure_status_and_ownership():
    d = params()
    assert d.get("params_version") and d.get("spec_version")
    P = d["params"]
    for k, e in P.items():
        for key in ("value", "placeholder", "unit", "status", "source", "owner"):
            assert key in e, (k, key)
        assert e["status"] in ("FROZEN", "PROVISIONAL", "TBD", "ASSUMED"), k
        if e["status"] == "TBD":
            assert e["value"] is None, f"{k}: TBD must not carry a value"
        assert re.fullmatch(r"[a-z][a-z0-9]*(_[A-Za-z0-9]+)*", k), f"{k}: parameters are lower_snake_case with a unit suffix (plan 0.5)"
    for owner, keys in PLAN_OWNERS.items():
        for k in keys:
            assert k in P, k
            assert P[k]["owner"] == owner, (k, P[k]["owner"], owner)
    assert P["ts_twin_s"]["value"] == 60 and P["ts_twin_s"]["status"] == "FROZEN"
    for k in ("k_heat_degC_per_h", "tau_heat_min", "w_ch"):
        assert P[k]["status"] == "ASSUMED" and P[k]["value"] is None
    w = P["w_ch"]["placeholder"]
    assert len(w) == 4 and abs(sum(w) - 1.0) < 1e-12
    for k in [x for x in P if x.startswith("plant_passive_")]:
        assert P[k]["owner"] == "Sai" and P[k]["status"] == "TBD" and P[k]["value"] is None


def test_placeholders_match_the_synthetic_generator_snapshot():
    """params.json is the single source: the placeholders must equal what the synthetic replays were built with."""
    # Exception: t_target_degC. A warming target is a clinical value; project config never invents one (the Unity
    # viewer asserts this). The synthetic replays carry their own labelled SYNTHETIC DEMO target in params_used.
    used = json.loads((ROOT / "integration" / "synthetic" / "meta" / "params_used.json").read_text(encoding="utf-8"))
    P = params()["params"]
    assert P["t_target_degC"]["value"] is None and P["t_target_degC"]["placeholder"] is None
    for k, e in used.items():
        if k in P and P[k]["owner"] == "Sai" and k != "t_target_degC":
            assert P[k]["placeholder"] == e["placeholder"], (k, P[k]["placeholder"], e["placeholder"])


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as ex:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(ex)[:400])
    sys.exit(1 if fails else 0)
