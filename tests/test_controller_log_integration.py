"""Controller-log integration tests: integration/build_replay.py with the received TC logs, plus
tools/check_replay_semantics.py.  Run: python -m pytest -q tests   or   python tests/test_controller_log_integration.py"""
import csv
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_replay_semantics as sem  # noqa: E402

PY = sys.executable
LOGS = ROOT / "integration" / "controller_logs_received"
TWIN = ROOT / "integration" / "twin_outputs" / "twin_SYN_01.csv"


def build(ctrl, out, scenario="T_TEST", extra=(), accept_inputs=True):
    flag = ["--accept-ctrl-input-columns"] if accept_inputs else []
    return subprocess.run([PY, str(ROOT / "integration" / "build_replay.py"), "--scenario-id", scenario,
                           "--twin", str(TWIN), "--ctrl", str(ctrl), "--cohort", "SYNTHETIC",
                           "--obs-source", "SIMULATED", "--twin-source", "MODEL",
                           "--created-utc", "2026-10-17T00:00:00Z", "--out", str(out), *flag, *extra],
                          capture_output=True, text=True)


def test_section_1s_contract_is_strict_by_default():
    """HW_Heartbeat_s / HW_Fault_Code are declared HW->Ctrl inputs but not section-1S log columns: refused unless
    the deviation is accepted explicitly."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "r.jsonl.gz"
        r = build(LOGS / "ctrl_TC07.csv", out, accept_inputs=False)
        assert r.returncode != 0 and "HW_Heartbeat_s" in r.stderr and not out.exists()


def frames(p):
    with gzip.open(p, "rt") as f:
        return [json.loads(x) for x in f if x.strip()]


def test_tc07_controller_fields_survive_exactly():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "r.jsonl.gz"
        r = build(LOGS / "ctrl_TC07.csv", out)
        assert r.returncode == 0, r.stderr
        assert "HW_Fault_Code non-zero rows: 0; controller fault_code non-zero rows: 101" in r.stderr
        F = frames(out)
        src = list(csv.DictReader(open(LOGS / "ctrl_TC07.csv", newline="")))
        assert len(F) - 1 == len(src)
        for fr, row in zip(F[1:], src):
            c = fr["ctrl"]
            assert fr["meta"]["t_s"] == float(row["t_s"])
            assert c["Controller_State"] == int(float(row["Controller_State"]))
            assert c["fault_code"] == int(float(row["fault_code"]))
            assert c["Safety_Shutdown"] == (row["Safety_Shutdown"].strip() in ("1", "1.0", "true"))
            assert c["Fault_Latched"] == (row["Fault_Latched"].strip() in ("1", "1.0", "true"))
            for i in range(1, 5):
                assert c[f"Heat_{i}"] == float(row[f"Heat_{i}"])
                assert fr["hw"][f"Module_Temp_{i}_A"] == round(float(row[f"Module_Temp_{i}_A"]), 3)
            # 206 = channel 2 OVERTEMP_SW (100 x ch + 6); HW_Fault_Code (system codes) stays 0 - consistent
            if c["Safety_Shutdown"]:
                assert c["fault_code"] == 206 and c["Channel_Fault_2"] == 206 and row["HW_Fault_Code"].strip() in ("0", "0.0")
            # provenance is not rewritten: the log says STANDIN, the replay says STANDIN
            assert fr["plant"]["plant_mode"] == row["plant_mode"].strip()
            assert "HW_Fault_Code" not in fr["hw"] and "HW_Heartbeat_s" not in fr["hw"]
        h = F[0]
        # canonical NERAM twin + Suchita's controller log: real pipeline outputs, so NOT a placeholder replay
        assert h["cohort"] == "SYNTHETIC" and h.get("placeholder") is not True
        assert set(h["inputs"]) == {"twin_SYN_01.csv", "ctrl_TC07.csv"}


def test_standin_without_plant_values_is_a_visible_warning():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "r.jsonl.gz"
        assert build(LOGS / "ctrl_TC07.csv", out).returncode == 0
        v = subprocess.run([PY, str(ROOT / "integration" / "validate_replay.py"), str(out), "--json"],
                           capture_output=True, text=True)
        rep = json.loads(v.stdout.strip().splitlines()[-1])
        assert rep["valid"] and rep["errors"] == 0
        assert rep["codes"].get("W108") == 301


def test_undeclared_controller_column_still_rejected():
    with tempfile.TemporaryDirectory() as td:
        src = LOGS / "ctrl_TC07.csv"
        alt = Path(td) / "c.csv"
        with open(src, newline="") as a, open(alt, "w", newline="") as b:
            rd = csv.DictReader(a)
            wr = csv.DictWriter(b, fieldnames=rd.fieldnames + ["SURPRISE"])
            wr.writeheader()
            for row in rd:
                row["SURPRISE"] = "1"
                wr.writerow(row)
        out = Path(td) / "x.jsonl.gz"
        r = build(alt, out)
        assert r.returncode != 0 and "SURPRISE" in r.stderr and not out.exists()


def test_shipped_tc07_replay_is_reproducible():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "SYN_TC07.jsonl.gz"
        r = build(LOGS / "ctrl_TC07.csv", out, "SYN_TC07",
                  ("--generator", "integration/build_replay.py (Sai, 2026-10-18)",
                   "--created-utc", "2026-10-18T00:00:00Z", "--params-version", "0.2",
                   "--params-used", str(ROOT / "integration" / "scenario_info" / "SYN_TC07_params_used.json"),
                   "--scenario-info", str(ROOT / "integration" / "scenario_info" / "SYN_TC07.json")))
        assert r.returncode == 0, r.stderr
        assert out.read_bytes() == (ROOT / "integration" / "replays" / "SYN_TC07.jsonl.gz").read_bytes()


def test_semantics_flags_zero_heat_warming_in_tc05_and_tc13():
    with tempfile.TemporaryDirectory() as td:
        for name, n_s01 in (("ctrl_TC05.csv", 1), ("ctrl_TC13.csv", 2)):
            out = Path(td) / f"{name}.jsonl.gz"
            assert build(LOGS / name, out).returncode == 0
            r = sem.check(out)
            s01 = [x for x in r["findings"] if x["code"] == "S01"]
            assert len(s01) == n_s01, (name, s01)
            assert all("11 s" in x["message"] for x in s01)
            assert r["verdict"] == "SEMANTIC_ISSUES"


def test_semantics_passes_tc07_and_shipped_synthetic_replays():
    for p in sorted((ROOT / "integration" / "replays").glob("*.jsonl.gz")):
        r = sem.check(p)
        assert r["verdict"] == "SEMANTIC_OK", (p.name, r["findings"])


def test_semantics_detects_injected_contradictions():
    src = ROOT / "integration" / "replays" / "SYN_SCN_B.jsonl.gz"
    with gzip.open(src, "rt") as f:
        lines = [json.loads(x) for x in f]
    for fr in lines[1:]:
        if fr["ctrl"]["Controller_State"] == 2:          # ACTIVE_WARMING: also heat a disconnected module
            fr["hw"]["Module_Connected_1"] = False
            fr["ctrl"]["Heat_1"] = 10.0
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "bad.jsonl.gz"
        with gzip.open(p, "wt") as f:
            f.write("\n".join(json.dumps(x) for x in lines) + "\n")
        codes = {x["code"] for x in sem.check(p)["findings"]}
        assert "S08" in codes


def test_tc07_shutdown_timing_and_channel():
    """TC07 source rows vs replay frames: SAFETY_SHUTDOWN first at t = 200 s, when Module_Temp_2_A first reaches 41.0;
    only channel 2 carries a fault; the latch is still set at the last frame (no reset in the log)."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "r.jsonl.gz"
        assert build(LOGS / "ctrl_TC07.csv", out).returncode == 0
        F = frames(out)[1:]
        first = next(f for f in F if f["ctrl"]["Safety_Shutdown"])
        assert first["meta"]["t_s"] == 200.0 and first["ctrl"]["Controller_State"] == 6
        assert first["hw"]["Module_Temp_2_A"] == 41.0
        prev = next(f for f in F if f["meta"]["t_s"] == 199.0)
        assert prev["hw"]["Module_Temp_2_A"] < 41.0 and not prev["ctrl"]["Safety_Shutdown"]
        for f in F:
            c = f["ctrl"]
            assert c["Channel_Fault_1"] == c["Channel_Fault_3"] == c["Channel_Fault_4"] == 0
            assert all(c[f"Heat_{i}"] == 0 for i in range(1, 5))
        assert F[-1]["ctrl"]["Fault_Latched"] and F[-1]["ctrl"]["Controller_State"] == 6
        assert "Clinician_Reset" not in F[0]["ctrl"]


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
