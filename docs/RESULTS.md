# NERAM results — status at 17 Oct 2026 (owner: Sai)

**No real-data model result exists.** Everything below is either a pre-existing development-data quality
result, synthetic verification, or a recorded failure. No final-holdout number exists, and none will be
produced before the one-time evaluation described in `docs/PREREGISTRATION_final.md`.

## 1. Development data pipeline (real VitalDB, development cases only; recorded earlier)

| Step | Result | Evidence |
|---|---|---|
| BT track census and quality (Code 1) | Done | earlier Colab run (script only in chat history) |
| BT vs pulmonary-artery temperature (Code 2) | 63 usable paired cases | earlier Colab run |
| Duplicate tracks and anomalies (Code 3 / 3B) | 18 duplicate track IDs resolved by a fixed rule | earlier Colab run |
| Code 4 (exploratory sequential model) | Rerun reproduced the earlier numbers exactly | Colab log |
| Final-holdout freeze | 1,100 holdout / 4,456 development cases, sorted-ID hash prefix 2d9235a38706e151, backed up to Drive | `final_holdout_freeze/freeze_manifest.json` (Drive) |

**Disclosure required in every write-up.** In the old Code 4 exploratory test, persistence beat the sequential
model at +20/+30/+60 min (MAE 0.250 vs 0.352, 0.299 vs 0.477, 0.405 vs 0.914 °C). That model was later shown to
be mathematically inconsistent (it estimated with one model and forecast with another). Those cases are now
development data.

## 2. Robust model — real-data development fit: **FAILED / NOT COMPLETED**

The `dev_robust_02_fit_and_validate.py` run on development training data (3,342 cases) did not produce valid
estimates. Two independent faults were reproduced from the saved checkpoint and log (earlier session):

1. **Quantised data.** All 15,673,253 raw readings lie on a 0.1 °C grid, and 88.6 % of consecutive minutes are
   identical. With continuous Gaussian measurement noise, the likelihood keeps improving as the noise variances
   shrink, so every start ended at the lower parameter bounds.
2. **Empty cases.** 161 of 3,342 cases have no data left after the 30-minute terminal exclusion. Their filter
   state is never initialised and gives NaN; the empirical-Bayes spread S becomes NaN, the objective becomes
   infinite, and the Hessian eigen-decomposition fails (LinAlgError).

A correction (C1 empty-case handling, C2 + 0.1²/12 °C² rounding variance, C3 fail-closed numerics, C4 staged
fit) has been written but **not approved or run**. C2 changes the observation model and needs a reviewer
sign-off. On rounded synthetic data the corrected script still left the level variance q and the decay rate γ
at their lower bounds, and EB round 2 did not converge (open items O1–O3). Under the pre-registered rules
(`dev_robust_03`, SHA-256 0f4b58be…), any of those triggers R4 → HUMAN_REVIEW_REQUIRED.

Nothing about the robust model's real-data forecasting performance may be claimed.

Evidence: `neram_recovery_v3.zip` (ROOT_CAUSE.md, diagnostics/DIAGNOSTIC_OUTPUT_2026-10-09.txt).
Decision brief: `docs/FIT_DECISION_BRIEF.md`. Run procedure (not executed): `docs/COLAB_DEV_FIT_RUNBOOK.md`.

## 3. Synthetic verification (this session, reproducible)

| Check | Result |
|---|---|
| Canonical core self-test (Gaussian limit vs closed form) | PASS: mean error 5.7e-14, variance error 1.8e-13 |
| Canonical core SHA-256 | de9c6c63…a2c5, matches EXPECTED_SHA256 |
| P_below_hypo vs Monte Carlo (200,000 draws from the model, +20 and +60 min) | PASS within 5 standard errors; a Gaussian approximation would differ by about 0.011 at +60 and would fail |
| P_below_hypo / 80 % / 95 % bounds come from one mixture (CDF at L80 = 0.10, etc.) | PASS (tolerance 2e-4) |
| No future leakage (changing data after minute m leaves rows ≤ m unchanged) | PASS |
| Twin_Valid rule (NO_DATA / INITIALISING / VALID / DEGRADED from config thresholds) | PASS |
| twin_SYN_01..04 validate, are distinct, regenerate byte-identically | PASS (figures: results/figures/twin_SYN_0x.png, labelled SYNTHETIC) |

These checks verify the **implementation**. They say nothing about how well the model fits real patients.

## 4. What the 20 Oct submission may claim

* A reproducible, leakage-protected development data pipeline and a frozen holdout.
* A verified inference implementation, plus a twin export that runs it unchanged, demonstrated on SYNTHETIC
  data with ASSUMED parameters.
* A simulated, clinician-supervised controller loop shown in a replay viewer, with all simulated and assumed
  content labelled.
* The real-data fit failure, its diagnosed causes and the pending correction.

It must not claim forecast superiority, calibration on real data, core temperature, a warming effect, or clinical
benefit.
