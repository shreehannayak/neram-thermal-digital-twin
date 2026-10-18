#!/usr/bin/env python3
"""Validate a thermal-twin output CSV against the interface spec (plan section 4A columns).

Checks (errors unless marked W):
  T01  exact column set and order (twin columns of config/interface_spec.csv)
  T02  T_twin_s numeric, starts on a minute boundary, step exactly ts_twin_s (60 s), strictly increasing
  T03  numeric cells parse; empty = missing (NaN); no 'nan'/'inf' text tokens, no -999 sentinels
  T04  obs_missing in {0,1} and agrees with T_obs empty
  T05  T_obs / T_est / forecast values inside the frozen plausibility range 25-43 degC; T_est_sd >= 0
  T06  Twin_Valid integer in config/enums.json TwinValid
  T07  NO_DATA rows have empty T_est/T_est_sd; other rows have both
  T08  NO_DATA only before the first observation (never after the twin has started)
  T09  forecast columns (T_pred, L80, U80, L95, U95, P_below_hypo) all present iff Twin_Valid == VALID
  T10  L95 <= L80 <= U80 <= U95 at each horizon; T_pred inside [L80, U80] (W)
  T11  probabilities (P_below_hypo_*, P_level_shift, P_outlier) inside [0, 1]
Exit 0 if no errors. Usage: python integration/validate_twin_output.py twin.csv [...] [--json]
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HORIZONS = (20, 30, 60)
FORECAST = [f"{p}_{h}" for h in HORIZONS for p in ("T_pred", "L80", "U80", "L95", "U95")] + \
           [f"P_below_hypo_{h}" for h in HORIZONS]
TWIN_COLUMNS = (["T_twin_s", "T_obs", "obs_missing", "T_est", "T_est_sd"]
                + [f"{p}_{h}" for h in HORIZONS for p in ("T_pred", "L80", "U80", "L95", "U95")]
                + [f"P_below_hypo_{h}" for h in HORIZONS] + ["P_level_shift", "P_outlier", "Twin_Valid"])
PLAUS = (25.0, 43.0)


def spec_twin_columns():
    """Twin columns in the order they appear in the interface spec (source Twin / Twin (observation))."""
    rows = list(csv.DictReader(open(ROOT / "config" / "interface_spec.csv", newline="", encoding="utf-8")))
    return [r["signal"] for r in rows if r["source"].startswith("Twin") and r["rate"].strip() == "1/60 Hz"]


def twin_valid_enum():
    e = json.loads((ROOT / "config" / "enums.json").read_text(encoding="utf-8"))["enums"]["TwinValid"]["values"]
    return {v["name"]: v["value"] for v in e}


def validate(path):
    errs, warns = [], []
    E = lambda c, line, msg: errs.append(f"{c} line {line}: {msg}")
    W = lambda c, line, msg: warns.append(f"{c} line {line}: {msg}")
    tv = twin_valid_enum()
    with open(path, newline="", encoding="utf-8") as f:
        rdr = csv.reader(f)
        header = next(rdr, None)
        rows = list(rdr)
    if header != TWIN_COLUMNS:
        E("T01", 1, f"columns must be exactly {TWIN_COLUMNS}")
        return errs, warns, 0
    spec = spec_twin_columns()
    if set(spec) != set(TWIN_COLUMNS):
        E("T01", 1, f"interface_spec twin rows {sorted(set(spec) ^ set(TWIN_COLUMNS))} differ from the export contract")
    prev_t, started = None, False
    for i, cells in enumerate(rows, start=2):
        if len(cells) != len(TWIN_COLUMNS):
            E("T01", i, "wrong number of cells")
            continue
        r = dict(zip(TWIN_COLUMNS, cells))
        val = {}
        for c in TWIN_COLUMNS:
            s = r[c].strip()
            if s == "":
                val[c] = None
                continue
            if s.lower() in ("nan", "inf", "-inf", "infinity"):
                E("T03", i, f"{c}: write missing values as an empty cell, not {s!r}")
                val[c] = None
                continue
            try:
                v = float(s)
            except ValueError:
                E("T03", i, f"{c}: not a number: {s!r}")
                val[c] = None
                continue
            if not math.isfinite(v):
                E("T03", i, f"{c}: non-finite")
            if v == -999:
                E("T03", i, f"{c}: -999 sentinel is not allowed; use an empty cell")
            val[c] = v
        t = val["T_twin_s"]
        if t is None:
            E("T02", i, "T_twin_s empty")
        else:
            if prev_t is None and abs(t % 60) > 1e-9:
                E("T02", i, "first T_twin_s must be on a minute boundary")
            if prev_t is not None and abs(t - prev_t - 60) > 1e-9:
                E("T02", i, f"step {t - prev_t} s (twin period is 60 s)")
            prev_t = t
        om = val["obs_missing"]
        if om not in (0.0, 1.0):
            E("T04", i, "obs_missing must be 0 or 1")
        elif (om == 1.0) != (val["T_obs"] is None):
            E("T04", i, "obs_missing disagrees with T_obs")
        for c in ["T_obs", "T_est"] + [x for x in FORECAST if not x.startswith("P_")]:
            if val[c] is not None and not (PLAUS[0] <= val[c] <= PLAUS[1]):
                E("T05", i, f"{c}={val[c]} outside {PLAUS}")
        if val["T_est_sd"] is not None and val["T_est_sd"] < 0:
            E("T05", i, "T_est_sd < 0")
        v = val["Twin_Valid"]
        if v is None or v != int(v) or int(v) not in tv.values():
            E("T06", i, f"Twin_Valid {r['Twin_Valid']!r} not in TwinValid enum")
            continue
        v = int(v)
        if v == tv["NO_DATA"]:
            if val["T_est"] is not None or val["T_est_sd"] is not None:
                E("T07", i, "NO_DATA requires empty T_est and T_est_sd")
            if started:
                E("T08", i, "NO_DATA after the twin has started")
        else:
            started = True
            if val["T_est"] is None or val["T_est_sd"] is None:
                E("T07", i, "T_est and T_est_sd required unless NO_DATA")
        present = [c for c in FORECAST if val[c] is not None]
        if v == tv["VALID"] and len(present) != len(FORECAST):
            E("T09", i, f"VALID row missing {len(FORECAST) - len(present)} forecast value(s)")
        if v != tv["VALID"] and present:
            E("T09", i, f"{len(present)} forecast value(s) present while Twin_Valid is not VALID")
        if v == tv["VALID"] and len(present) == len(FORECAST):
            for h in HORIZONS:
                m, l80, u80, l95, u95 = (val[f"{p}_{h}"] for p in ("T_pred", "L80", "U80", "L95", "U95"))
                if not (l95 <= l80 <= u80 <= u95):
                    E("T10", i, f"+{h}: interval bounds not ordered")
                elif not (l80 <= m <= u80):
                    W("T10", i, f"+{h}: T_pred outside its 80% interval")
        for c in [f"P_below_hypo_{h}" for h in HORIZONS] + ["P_level_shift", "P_outlier"]:
            if val[c] is not None and not (0.0 <= val[c] <= 1.0):
                E("T11", i, f"{c}={val[c]} outside [0, 1]")
    return errs, warns, len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    ok = True
    for f in a.files:
        errs, warns, n = validate(f)
        ok &= not errs
        if a.json:
            print(json.dumps({"file": f, "valid": not errs, "rows": n, "errors": len(errs), "warnings": len(warns)}))
        else:
            print(f"{'VALID' if not errs else 'INVALID'}: {f} ({n} rows, {len(errs)} errors, {len(warns)} warnings)")
            for m in errs[:30] + warns[:10]:
                print("  ", m)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
