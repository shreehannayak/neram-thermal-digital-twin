"""Tests for src/twin_replay_export.py (Monte Carlo / interval-consistency tests: tests/test_p_below_hypo_mc.py), integration/validate_twin_output.py, tools/make_twin_syn_outputs.py and
src/assumed_warming.py.  Run: python -m pytest -q tests   or   python tests/test_twin_export.py"""
import csv
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "integration"))
import thermal_robust_core as core  # noqa: E402
import twin_replay_export as tre  # noqa: E402
import assumed_warming as aw  # noqa: E402
import validate_twin_output as vto  # noqa: E402

PARAMS = ROOT / "config" / "model_params_synthetic.json"
CONFIG = ROOT / "config" / "twin_export_config.json"


def _setup(obs_name="obs_SYN_02.csv"):
    p, gamma, m0, S, _ = tre.load_model_params(PARAMS, "SYNTHETIC")
    cfg, _ = tre.load_config(CONFIG)
    t, y = tre.read_obs(ROOT / "integration" / "synthetic" / "observations" / obs_name)
    return p, gamma, m0, S, cfg, t, y


def _origin_mixture(y, p, gamma, m0, S, o):
    out = core.gpb2_filter(y[None, :o + 1], p, m0[None], S, gamma)
    return out["LW"], out["Z"], out["PP"]


def test_canonical_core_hash():
    assert tre.check_core() == tre.CORE_SHA256





def test_no_future_leakage():
    p, gamma, m0, S, cfg, t, y = _setup()
    base, _ = tre.export(t, y, p, gamma, m0, S, cfg)
    y2 = y.copy()
    y2[51:] += 2.0
    y2[60] = np.nan
    pert, _ = tre.export(t, y2, p, gamma, m0, S, cfg)
    for mi in range(51):
        assert base[mi] == pert[mi], mi


def test_twin_valid_rule():
    p, gamma, m0, S, cfg, t, y = _setup("obs_SYN_04.csv")
    y = y.copy()
    y[:3] = np.nan                                      # leading missing minutes -> NO_DATA
    rows, _ = tre.export(t, y, p, gamma, m0, S, cfg)
    obs = ~np.isnan(y)
    first = int(np.argmax(obs))
    for mi, r in enumerate(rows):
        if mi < first:
            exp = tre.TV["NO_DATA"]
        elif mi - first < cfg["init_min"]:
            exp = tre.TV["INITIALISING"]
        else:
            recent = obs[max(0, mi - int(cfg["window_min"]) + 1):mi + 1].sum()
            ok = recent >= cfg["min_obs_in_window"] and r["T_est_sd"] < cfg["sd_degrade_degC"]   # plan 4A: strictly less
            exp = tre.TV["VALID"] if ok else tre.TV["DEGRADED"]
        assert r["Twin_Valid"] == exp, (mi, r["Twin_Valid"], exp)
        has_fc = r["T_pred_20"] is not None
        assert has_fc == (r["Twin_Valid"] == tre.TV["VALID"])
    assert any(r["Twin_Valid"] == tre.TV["DEGRADED"] for r in rows)


def test_development_export_refused():
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "p.json"
        d = json.loads(PARAMS.read_text())
        bad.write_text(json.dumps(d))
        try:
            tre.load_model_params(bad, "DEVELOPMENT")
            raise AssertionError("DEVELOPMENT export must be refused")
        except tre.ExportError:
            pass
        d["status"] = "FITTED_DEVELOPMENT"
        bad.write_text(json.dumps(d))
        try:
            tre.load_model_params(bad, "DEVELOPMENT")
            raise AssertionError("FITTED_DEVELOPMENT without a dev_robust_03 decision must be refused")
        except tre.ExportError:
            pass


def test_four_synthetic_outputs_valid_distinct_reproducible():
    files = [ROOT / "integration" / "twin_outputs" / f"twin_SYN_0{i}.csv" for i in range(1, 5)]
    hashes = set()
    for f in files:
        errs, _, n = vto.validate(f)
        assert not errs, (f, errs[:3])
        assert n == 90
        hashes.add(f.read_bytes())
    assert len(hashes) == 4
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "make_twin_syn_outputs.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def _write_variant(td, mutate):
    src = ROOT / "integration" / "twin_outputs" / "twin_SYN_02.csv"
    rows = list(csv.reader(open(src, newline="")))
    mutate(rows)
    p = Path(td) / "v.csv"
    with open(p, "w", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return p


def test_validator_rejects_contract_violations():
    H = list(csv.reader(open(ROOT / "integration" / "twin_outputs" / "twin_SYN_02.csv")))[0]
    col = {c: i for i, c in enumerate(H)}

    def set_cell(r, c, v):
        def m(rows):
            rows[r][col[c]] = v
        return m

    cases = [
        ("T01", lambda rows: rows[0].pop()),
        ("T02", set_cell(5, "T_twin_s", "250")),
        ("T03", set_cell(30, "T_obs", "nan")),
        ("T03", set_cell(30, "T_est_sd", "-999")),
        ("T04", set_cell(30, "obs_missing", "1")),
        ("T05", set_cell(30, "T_est", "50.0")),
        ("T06", set_cell(30, "Twin_Valid", "7")),
        ("T09", set_cell(5, "T_pred_20", "36.1")),
        ("T09", set_cell(40, "U95_60", "")),
        ("T10", set_cell(40, "L95_20", "40.0")),
        ("T11", set_cell(40, "P_outlier", "1.5")),
    ]
    with tempfile.TemporaryDirectory() as td:
        for code, mut in cases:
            errs, _, _ = vto.validate(_write_variant(td, mut))
            assert any(e.startswith(code) for e in errs), (code, errs[:3])


def test_assumed_warming_matches_synthetic_replay_and_sensitivity():
    """src/assumed_warming.py reproduces the dT_heat sequence that tools/make_synthetic_replays.py wrote into
    SYN_SCN_B (same section 4E equation), and the 0.5x/1x/2x grid scales dT_heat linearly."""
    snap = json.loads((ROOT / "integration" / "synthetic" / "meta" / "params_used.json").read_text())
    k, tau, w = aw.params_from_snapshot(snap)
    with gzip.open(ROOT / "integration" / "replays" / "SYN_SCN_B.jsonl.gz", "rt") as f:
        F = [json.loads(x) for x in f][1:]
    heat = [tuple(fr["ctrl"][f"Heat_{i}"] for i in range(1, 5)) for fr in F]
    tp = [None] * len(F)
    res = aw.simulate(heat, tp, k, tau, w, dt_s=1.0)
    ref = [fr["plant"]["dT_heat"] for fr in F]
    err = max(abs(a - b) for a, b in zip(res["dT_heat"], ref) if b is not None)
    assert err < 2e-3, err
    grid = aw.sensitivity(heat, tp, k, tau, w)
    last = {m: g["dT_heat"][-1] for m, g in grid.items()}
    assert abs(last[2.0] - 2 * last[1.0]) < 1e-12 and abs(last[0.5] - 0.5 * last[1.0]) < 1e-12
    for bad in ([(101, 0, 0, 0)], [(-1, 0, 0, 0)], [(None, 0, 0, 0)]):
        try:
            aw.simulate(bad, [36.0], k, tau, w)
            raise AssertionError("invalid heat input accepted")
        except ValueError:
            pass
    r = aw.simulate([(None, 0, 0, 0)], [36.0], k, tau, w, missing_as_zero=True)
    assert r["missing_steps"] == [0]


def test_thresholds_come_from_params_json():
    """t_hypo_degC and sd_degrade_degC are read from config/params.json (single source of truth, plan 0.3)."""
    params = json.loads((ROOT / "config" / "params.json").read_text())["params"]
    cfg, doc = tre.load_config(CONFIG)
    for k in ("t_hypo_degC", "sd_degrade_degC"):
        e = params[k]
        assert cfg[k] == (e["value"] if e["value"] is not None else e["placeholder"])
        assert e["value"] is not None or k in doc["placeholders_in_use"]
    with tempfile.TemporaryDirectory() as td:
        alt = json.loads((ROOT / "config" / "params.json").read_text())
        alt["params"]["sd_degrade_degC"]["placeholder"] = 0.01      # tighter than any T_est_sd -> never VALID
        pp = Path(td) / "params.json"
        pp.write_text(json.dumps(alt))
        cfg2, _ = tre.load_config(CONFIG, pp)
        p, gamma, m0, S, _ = tre.load_model_params(PARAMS, "SYNTHETIC")
        t, y = tre.read_obs(ROOT / "integration" / "synthetic" / "observations" / "obs_SYN_01.csv")
        rows, _ = tre.export(t, y, p, gamma, m0, S, cfg2)
        assert not any(r["Twin_Valid"] == tre.TV["VALID"] for r in rows)


def test_settled_start_and_minute_grid():
    for i in range(1, 5):
        rows = list(csv.DictReader(open(ROOT / "integration" / "twin_outputs" / f"twin_SYN_0{i}.csv")))
        ts = [float(r["T_twin_s"]) for r in rows]
        assert ts[0] == 0.0 and all(b - a == 60.0 for a, b in zip(ts, ts[1:]))


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
