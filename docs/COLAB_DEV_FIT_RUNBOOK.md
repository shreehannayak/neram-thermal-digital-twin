# Colab runbook — development fit (v2, staged) and development-case duration statistics

**Status: NOT EXECUTED.** This needs Google Colab, your Drive backup (`MyDrive/thermal_digital_twin_backup/`) and the
development cache, and none of these is reachable from the laptop workspace. The procedure follows the
`neram_recovery_v3` runbook (SHA-256 of `neram_recovery_v3.zip`: 49b8c065386bab9d8c3629ce4fee56bf64814e8542b192b759ca2173a4f6aa05).
The final holdout is never evaluated here.

Before running, read `docs/FIT_DECISION_BRIEF.md` and decide C2 and O1–O3.

**Working-directory assumptions:**
* scripts and data are restored to `/content`;
* Drive is at `/content/drive/MyDrive`;
* backup root: `/content/drive/MyDrive/thermal_digital_twin_backup`.

Run one cell at a time and read each `RESULT:` line. Any `STOPPED (fail-closed)` or `NUMERICAL_FAILURE` means stop.

```python
# CELL 0 — mount Drive (every new runtime)
from google.colab import drive
drive.mount('/content/drive')
```
```python
# CELL 1 — scripts: 8 canonical + proposed v2 + helper v3, all hash-checked
# (upload Downloads/neram_recovery_v3.zip to MyDrive/thermal_digital_twin_backup/ once, if it is not there)
!rm -rf /content/neram_recovery_v3 && unzip -q /content/drive/MyDrive/thermal_digital_twin_backup/neram_recovery_v3.zip -d /content
!cp /content/neram_recovery_v3/canonical_scripts/*.py /content/ && cp /content/neram_recovery_v3/proposed/dev_robust_02_fit_and_validate_v2.py /content/ && cp /content/neram_recovery_v3/neram_recover.py /content/
!cd /content && sha256sum -c /content/neram_recovery_v3/SHA256SUMS_runtime
```
**PASS:** 10 × OK.
* thermal_robust_core de9c6c63…
* dev_robust_02 ab4a251b…
* dev_robust_03 0f4b58be…
* v2 c02e5de8…
* helper f86bd71b…

```python
# CELL 2 — status (read-only)
!cd /content && python neram_recover.py status --model v2
```
```python
# CELL 3 — inputs: restore code4_outputs/, final_holdout_freeze/, development cache; verify freeze hash and coverage
!cd /content && python neram_recover.py restore-inputs
# CELL 4 — synthetic checks (core self-test, recovery, verification); CELL 5 — development metadata; CELL 6 — lock rules
!cd /content && python neram_recover.py synthetic
!cd /content && python neram_recover.py metadata
!cd /content && python neram_recover.py lock-rules
```
**PASS:**
* `INPUTS RESTORED AND VERIFIED`: holdout ID hash matches `2d9235a3…`; 4,456 / 1,100; 4456/4456 development
  tracks.
* `SYNTHETIC CHECKS PASS`. The known terminal-event limitation is printed as a limitation, not as a pass.
* `METADATA READY`.
* `RULES LOCKED (0f4b58be…6a91)`.

```python
# CELL 7 — development-case duration statistics for Shreehan (aggregates only; development cases only)
import pandas as pd, hashlib, json
dev = set(pd.read_csv('/content/final_holdout_freeze/development_case_ids.csv')['caseid'].astype(int))
cm = pd.read_csv('/content/code4_outputs/code4_cohort_manifest.csv')
cm = cm[cm.caseid.isin(dev)]
assert len(cm) == 4456, len(cm)
out = {'cohort': 'development set only (4,456 cases; final holdout excluded)',
       'source': 'code4_outputs/code4_cohort_manifest.csv',
       'source_sha256': hashlib.sha256(open('/content/code4_outputs/code4_cohort_manifest.csv','rb').read()).hexdigest()}
for col in ('covered_minutes', 'settled_minutes'):
    if col in cm:
        s = cm[col].astype(float)
        out[col] = {'unit': 'min', 'n': int(s.notna().sum()), 'median': float(s.median()), 'p90': float(s.quantile(0.9))}
print(json.dumps(out, indent=2))
json.dump(out, open('/content/drive/MyDrive/thermal_digital_twin_backup/dev_case_duration_stats.json', 'w'), indent=2)
```
Copy only the printed aggregate JSON into `results/development/dev_case_duration_stats.json` and send it to
Shreehan.
* `covered_minutes` is the BT recording coverage per case.
* `settled_minutes` is the span after probe equilibration.
* State which one the power budget uses. No case-level rows leave Drive.

```python
# CELL 8 — ONLY after you approve C1–C4 (docs/FIT_DECISION_BRIEF.md)
!cd /content && python neram_recover.py approve-model --model v2 --reviewer "Sai"
# CELL 9 — pilot: first optimisation start only (25 % subsample, about 10 min)
!cd /content && python neram_recover.py fit --model v2 --until r1_start0
```
**Review A:**
* `Quantisation check … 1.00000`.
* `[r1_start0] done: nll …` is finite, and no longer about −5 per observed minute.
* Note the `near bounds [...]` list.
* `PERSISTENT CHECKPOINT: VERIFIED`.

```python
# CELL 10 — through the first empirical-Bayes step
!cd /content && python neram_recover.py fit --model v2 --until eb1
```
**Review B:**
* `EB round 1: S [...]` is finite and positive definite.
* Note the EM convergence status.
* Record O1–O3 now; the brief recommends "keep canonical" for all three.

```python
# CELL 11 — remaining stages (r2_full, eb2, diag, wt0_full, evaluate); resumable — rerun after any reset
!cd /content && python neram_recover.py fit --model v2
```
**PASS:** `RESULT: FIT COMPLETE — FINAL_HOLDOUT_PROTECTED: PASS`.

The report is at `/content/dev_robust_outputs/dev_robust_report.md`, and on Drive at
`pipeline_recovery_state/runs/robust-v2-quant/dev_robust_outputs/`.

```python
# CELL 12 — apply the locked pre-registered rules (development outputs only)
!cd /content && python neram_recover.py apply-rules            # add --acknowledge-run-fail if REAL_DATA_MODEL_RUN is FAIL
```
**Expect:**
* `Rules file SHA-256: 0f4b58…`;
* `VERDICT …`. Likely `HUMAN_REVIEW_REQUIRED` (see the brief).

```python
# CELL 13 — back up development outputs (plan 4B: after each step)
!cp -r /content/development_adequacy /content/dev_robust_outputs /content/drive/MyDrive/thermal_digital_twin_backup/ 2>/dev/null; echo done
```

## After the run (laptop)
1. Copy only the aggregate files to `results/development/`:
   * `dev_val_paired_bootstrap.csv`
   * `dev_val_calibration.csv`
   * `dev_fit_parameters.json`
   * `preregistered_decision.json` / `.md`
   * `dev_case_duration_stats.json`
2. Update `docs/RESULTS.md` §2 with the verdict and the actual numbers, labelled "development set".
3. Only if the verdict permits, and the VitalDB terms allow it: export one development case and build SCN_A.
   * `python src/twin_replay_export.py --cohort DEVELOPMENT ...`
   * The exporter refuses until the parameter file has status FITTED_DEVELOPMENT and names the dev_robust_03
     decision file.

**After a runtime reset:** run Cells 0, 1 and 3–6, then rerun the last fit cell. The approval and the rules lock
persist on Drive.
