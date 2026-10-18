"""
dev_robust_01_fetch_case_metadata.py

The ONLY step in this bundle that uses the network. Downloads VitalDB /cases (static clinical metadata:
no temperatures, no targets), DISCARDS every final-holdout row in memory before anything is written, and
saves the development rows to dev_robust_inputs/dev_case_metadata.csv with a SHA-256 record.

If the file already exists it is verified (hash, no holdout IDs, all development IDs present) and NOTHING
is downloaded. Never writes to code4_outputs/ or final_holdout_freeze/ (checked by hashing before/after).
"""

import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd

API_CASES = "https://api.vitaldb.net/cases"
FREEZE_DIR, CODE4_DIR = "final_holdout_freeze", "code4_outputs"
OUT_DIR = "dev_robust_inputs"
META = os.path.join(OUT_DIR, "dev_case_metadata.csv")
META_REC = os.path.join(OUT_DIR, "dev_case_metadata.sha256.json")


def sha_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def hash_tree(d):
    return {os.path.join(r, f): sha_file(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in sorted(fs)}


def stop(msg):
    print(f"STOP: {msg}")
    sys.exit(1)


for d in (FREEZE_DIR, CODE4_DIR):
    if not os.path.isdir(d):
        stop(f"{d}/ not found")
before = {**hash_tree(FREEZE_DIR), **hash_tree(CODE4_DIR)}
final_ids = set(pd.read_csv(os.path.join(FREEZE_DIR, "final_holdout_case_ids.csv"))["caseid"].astype(int))
dev_ids = set(pd.read_csv(os.path.join(FREEZE_DIR, "development_case_ids.csv"))["caseid"].astype(int))
man = json.load(open(os.path.join(FREEZE_DIR, "freeze_manifest.json")))
if hashlib.sha256(",".join(map(str, sorted(final_ids))).encode()).hexdigest() != man["final_holdout_ids_sha256"]:
    stop("final holdout ID hash does not match freeze_manifest.json")
if dev_ids & final_ids:
    stop("development and final holdout overlap")

os.makedirs(OUT_DIR, exist_ok=True)
if os.path.exists(META):
    if not os.path.exists(META_REC) or json.load(open(META_REC))["sha256"] != sha_file(META):
        stop(f"{META} exists but its SHA-256 record is missing or does not match; not overwriting")
    action = "verified existing local file (no network access)"
else:
    import requests
    last = None
    for a in range(4):
        try:
            r = requests.get(API_CASES, timeout=120)
            r.raise_for_status()
            break
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (a + 1))
    else:
        stop(f"could not download /cases: {last}")
    cases = pd.read_csv(io.BytesIO(r.content))
    cases = cases[cases["caseid"].isin(dev_ids)].reset_index(drop=True)          # holdout rows discarded here
    cases.to_csv(META, index=False)
    json.dump(dict(sha256=sha_file(META), rows=len(cases), columns=list(cases.columns), source=API_CASES,
                   created_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   note="development rows only; final-holdout rows were discarded in memory before saving"),
              open(META_REC, "w"), indent=2)
    action = "downloaded /cases once; saved development rows only"

meta = pd.read_csv(META)
ids = set(meta["caseid"].astype(int))
checks = {"no_final_holdout_rows": not (ids & final_ids), "all_development_ids_present": dev_ids <= ids,
          "only_development_rows": ids <= dev_ids,
          "protected_folders_unchanged": before == {**hash_tree(FREEZE_DIR), **hash_tree(CODE4_DIR)}}
print(f"{action}: {META} ({len(meta)} rows, {meta.shape[1]} columns)")
for k, v in checks.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
print(f"METADATA_READY: {'PASS' if all(checks.values()) else 'FAIL'}")
sys.exit(0 if all(checks.values()) else 1)
