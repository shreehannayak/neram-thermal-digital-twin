#!/usr/bin/env python3
"""twin_replay_export.py - export per-minute thermal-twin output (interface spec section 4A columns)
by running the CANONICAL NERAM robust state-space core (src/thermal_robust_core.py, imported unchanged).

What it does
  input   a per-minute observation series (CSV: T_twin_s, T_obs; T_obs empty/NaN = missing minute)
  model   thermal_robust_core.gpb2_filter (GPB2 Gaussian-sum filter, jump/outlier mixture), forecast_moments,
          mixture_intervals - the SAME functions verified in robust_statespace_verification.py
  output  twin CSV with exactly the interface-spec columns, one row per minute, values held by the replay builder

Real-time only: every exported value at minute m uses observations up to and including minute m. The offline
fixed-lag attribution in the core (fixed_lag_mode_posterior) is NEVER called here, so no future data can leak
into P_level_shift / P_outlier (they are the FILTERED mode probabilities at m).

P_below_hypo_h is computed from the same predictive mixture that mixture_intervals uses (retained components x
future jump count x observation outlier state), so P_below_hypo, T_pred and the 80/95 % bounds are mutually
consistent (tested in tests/test_twin_export.py, including a Monte Carlo check).

Parameter provenance
  The real-data development fit has NOT succeeded (see docs/RESULTS.md). This script therefore refuses to export a
  DEVELOPMENT case unless the parameter file declares status "FITTED_DEVELOPMENT" AND names the dev_robust_03
  decision file - which does not exist yet. SYNTHETIC exports must use a parameter file whose status is
  "ASSUMED_SYNTHETIC"; those values are illustrative, not estimates.

Twin_Valid rule (plan section 4A; no threshold is a code constant)
  NO_DATA       before the first observed minute
  INITIALISING  tau < init_min minutes since the settled start (T_twin_s = 0 is the settled start; for a
                synthetic run the first row is the settled start)
  VALID         tau >= init_min AND at least min_obs_in_window of the last window_min minutes observed AND
                T_est_sd < sd_degrade_degC (strictly less, as written in the plan)
  DEGRADED      otherwise
  t_hypo_degC and sd_degrade_degC are read from config/params.json (the single source of truth, plan 0.3);
  the three rule constants init_min / window_min / min_obs_in_window come from config/twin_export_config.json
  (they are the plan-4A rule, not params rows).
Forecast columns are empty unless Twin_Valid is VALID (interface spec: "NaN unless VALID").

Usage
  python src/twin_replay_export.py --obs obs.csv --model-params params_model.json \
      --config config/twin_export_config.json --cohort SYNTHETIC --out integration/twin_outputs/twin_SYN_01.csv
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import thermal_robust_core as core  # noqa: E402

CORE_SHA256 = "de9c6c6378301ddd6e9378cfd3d5671a97fc68cc79a190a978033aa4161ad2c5"
HORIZONS = (20, 30, 60)
TWIN_COLUMNS = (["T_twin_s", "T_obs", "obs_missing", "T_est", "T_est_sd"]
                + [f"{p}_{h}" for h in HORIZONS for p in ("T_pred", "L80", "U80", "L95", "U95")]
                + [f"P_below_hypo_{h}" for h in HORIZONS] + ["P_level_shift", "P_outlier", "Twin_Valid"])
TV = {"NO_DATA": 0, "INITIALISING": 1, "VALID": 2, "DEGRADED": 3}


class ExportError(Exception):
    pass


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_core():
    got = sha256(Path(core.__file__))
    if got != CORE_SHA256:
        raise ExportError(f"thermal_robust_core.py hash {got} != canonical {CORE_SHA256}; refusing to export")
    return got


def _mixture_components(w, cm, cb, h, p):
    """Identical component construction to thermal_robust_core.mixture_intervals (weights, means, SDs)."""
    km = core.kmax_for(h, p["pi_u"])
    k = np.arange(km + 1)
    bk = stats.binom.pmf(k, h, p["pi_u"])
    bk = bk / bk.sum()
    po = np.array([1 - p["pi_e"], p["pi_e"]])
    ro = np.array([p["r"], p["r_O"]])
    W = (w[:, :, None, None] * bk[None, None, :, None] * po[None, None, None, :])
    M = np.broadcast_to(cm[:, :, None, None], W.shape)
    SD = np.sqrt(cb[:, :, None, None] + (h - k)[None, None, :, None] * p["q"]
                 + k[None, None, :, None] * p["q_J"] + ro[None, None, None, :])
    n = len(w)
    return W.reshape(n, -1), M.reshape(n, -1), SD.reshape(n, -1)


def mixture_cdf(w, cm, cb, h, p, x):
    """P(y_{o+h} < x) under the predictive mixture used by mixture_intervals."""
    W, M, SD = _mixture_components(w, cm, cb, h, p)
    return np.clip((W * stats.norm.cdf((np.asarray(x, float)[..., None] - M) / SD)).sum(1), 0.0, 1.0)


def read_obs(path):
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames or "T_twin_s" not in rdr.fieldnames or "T_obs" not in rdr.fieldnames:
            raise ExportError(f"{path}: needs columns T_twin_s, T_obs")
        rows = list(rdr)
    t = np.array([float(r["T_twin_s"]) for r in rows])
    if len(t) == 0:
        raise ExportError("empty observation file")
    if not np.allclose(np.diff(t), 60.0) or abs(t[0] % 60) > 1e-9:
        raise ExportError("T_twin_s must start on a minute boundary and step exactly 60 s (twin period ts_twin_s = 60)")
    y = np.array([float(r["T_obs"]) if (r["T_obs"] or "").strip() not in ("", "nan", "NaN") else np.nan for r in rows])
    if np.isinf(y).any():
        raise ExportError("infinite T_obs value")
    return t, y


def load_model_params(path, cohort):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    status = d.get("status")
    if cohort == "SYNTHETIC" and status != "ASSUMED_SYNTHETIC":
        raise ExportError("a SYNTHETIC export needs a model-parameter file with status ASSUMED_SYNTHETIC")
    if cohort == "DEVELOPMENT":
        if status != "FITTED_DEVELOPMENT" or not d.get("dev_robust_03_decision_file"):
            raise ExportError("DEVELOPMENT export refused: no fitted development parameters with a pre-registered "
                              "dev_robust_03 decision exist (the real-data fit has not succeeded)")
    p = {k: float(d["params"][k]) for k in ("q", "r", "pi_u", "q_J", "pi_e", "r_O")}
    gamma = float(d["params"]["gamma"])
    m0 = np.asarray(d["m0"], float)
    S = np.asarray(d["S"], float)
    if m0.shape != (2,) or S.shape != (2, 2):
        raise ExportError("m0 must have 2 entries and S must be 2x2")
    if not (p["q_J"] > p["q"] and p["r_O"] > p["r"] and 0 <= p["pi_u"] <= 0.5 and 0 <= p["pi_e"] <= 0.5):
        raise ExportError("model parameters violate the core's identifiability constraints")
    return p, gamma, m0, S, d


PARAMS_JSON = ROOT / "config" / "params.json"


def _effective(entry, name, origin):
    v = entry["value"] if entry.get("value") is not None else entry.get("placeholder")
    if v is None:
        raise ExportError(f"{origin} {name} has neither a value nor a labelled placeholder")
    return float(v), entry.get("value") is None


def load_config(path, params_path=None):
    """Rule constants from twin_export_config.json; t_hypo_degC / sd_degrade_degC from config/params.json."""
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    params = json.loads(Path(params_path or PARAMS_JSON).read_text(encoding="utf-8"))["params"]
    out, placeholders = {}, []
    for k in ("init_min", "window_min", "min_obs_in_window"):
        out[k], ph = _effective(c["entries"][k], k, "twin_export_config")
        if ph:
            placeholders.append(k)
    for k in ("t_hypo_degC", "sd_degrade_degC"):
        out[k], ph = _effective(params[k], k, "params.json")
        if ph:
            placeholders.append(k)
    c = dict(c, placeholders_in_use=placeholders, params_version=json.loads(
        Path(params_path or PARAMS_JSON).read_text(encoding="utf-8"))["params_version"])
    return out, c


def export(t, y, p, gamma, m0, S, cfg):
    L = len(y)
    out = core.gpb2_filter(y[None, :], p, m0[None, :], S, gamma, store_probs=True, store_states=True,
                           origin_mask=np.ones((1, L), bool))
    org = out["origins"]
    o_t = org["t"].astype(int)                       # minutes with an active filter (after first observation)
    obs = ~np.isnan(y)
    first = int(np.argmax(obs)) if obs.any() else None
    rows = []
    fc = {}
    if len(o_t):
        for h in HORIZONS:
            m, v, w, cm, cb = core.forecast_moments(org["LW"], org["Z"], org["PP"], o_t, h, p, gamma)
            iv, trunc = core.mixture_intervals(w, cm, cb, h, p, levels=(0.8, 0.95))
            pb = mixture_cdf(w, cm, cb, h, p, np.full(len(o_t), cfg["t_hypo_degC"]))
            fc[h] = dict(m=m, l80=iv[0.8][0], u80=iv[0.8][1], l95=iv[0.95][0], u95=iv[0.95][1], pb=pb, trunc=trunc)
    idx = {int(tt): i for i, tt in enumerate(o_t)}
    for mi in range(L):
        row = {c: None for c in TWIN_COLUMNS}
        row["T_twin_s"] = float(t[mi])
        row["T_obs"] = None if not obs[mi] else float(y[mi])
        row["obs_missing"] = 0 if obs[mi] else 1
        if first is None or mi < first:
            row["Twin_Valid"] = TV["NO_DATA"]
            rows.append(row)
            continue
        z = out["st_z"][0, mi]
        P = out["st_P"][0, mi]
        hrow = core.Hrow(float(mi), gamma)
        row["T_est"] = float(hrow @ z)
        row["T_est_sd"] = float(math.sqrt(max(hrow @ P @ hrow, 0.0)))
        if obs[mi] and mi != first:
            row["P_level_shift"] = float(out["prob"]["jump"][0, mi])
            row["P_outlier"] = float(out["prob"]["outlier"][0, mi])
        lo = max(0, mi - int(cfg["window_min"]) + 1)
        recent = int(obs[lo:mi + 1].sum())
        if mi - first < cfg["init_min"]:
            tv = TV["INITIALISING"]
        elif recent >= cfg["min_obs_in_window"] and row["T_est_sd"] < cfg["sd_degrade_degC"]:
            tv = TV["VALID"]
        else:
            tv = TV["DEGRADED"]
        row["Twin_Valid"] = tv
        if tv == TV["VALID"]:
            j = idx[mi]
            for h in HORIZONS:
                f = fc[h]
                row[f"T_pred_{h}"] = float(f["m"][j])
                row[f"L80_{h}"], row[f"U80_{h}"] = float(f["l80"][j]), float(f["u80"][j])
                row[f"L95_{h}"], row[f"U95_{h}"] = float(f["l95"][j]), float(f["u95"][j])
                row[f"P_below_hypo_{h}"] = float(f["pb"][j])
        rows.append(row)
    return rows, {h: fc[h]["trunc"] for h in fc}


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, int):
        return str(v)
    return f"{v:.6f}"


def write_csv(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(TWIN_COLUMNS)
        for r in rows:
            w.writerow([fmt(r[c]) if c != "T_twin_s" else f"{r[c]:.0f}" for c in TWIN_COLUMNS])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--obs", required=True)
    ap.add_argument("--model-params", required=True)
    ap.add_argument("--config", default=str(ROOT / "config" / "twin_export_config.json"))
    ap.add_argument("--cohort", required=True, choices=["SYNTHETIC", "DEVELOPMENT"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta-out", help="JSON sidecar with hashes and parameter provenance")
    a = ap.parse_args(argv)
    try:
        core_sha = check_core()
        t, y = read_obs(a.obs)
        p, gamma, m0, S, pdoc = load_model_params(a.model_params, a.cohort)
        cfg, cdoc = load_config(a.config)
        rows, trunc = export(t, y, p, gamma, m0, S, cfg)
    except ExportError as ex:
        print("EXPORT REFUSED:", ex, file=sys.stderr)
        return 2
    write_csv(rows, a.out)
    if a.meta_out:
        meta = dict(core_sha256=core_sha, obs_sha256=sha256(a.obs), model_params_sha256=sha256(a.model_params),
                    config_sha256=sha256(a.config), params_sha256=sha256(PARAMS_JSON), cohort=a.cohort,
                    model_params_status=pdoc["status"], config_used=cfg,
                    placeholders_in_use=cdoc["placeholders_in_use"], binomial_truncation_mass=trunc, out_sha256=sha256(a.out),
                    note="Real-time filtered outputs only; fixed-lag attribution not used.")
        Path(a.meta_out).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    nv = sum(r["Twin_Valid"] == TV["VALID"] for r in rows)
    print(f"wrote {a.out}: {len(rows)} minutes, {nv} VALID")
    return 0


if __name__ == "__main__":
    sys.exit(main())
