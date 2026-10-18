# Final-holdout pre-registration — DRAFT, NOT REGISTERED (owner: Sai)

**Status: draft only. The final holdout has not been opened, inspected or scored. The evaluation script does
not exist yet.**

The plan allows exactly one final-holdout evaluation. It may run only after all of these hold:

1. The development fit has completed, and `dev_robust_03` produced a verdict other than HUMAN_REVIEW_REQUIRED,
   or that review has been completed and recorded.
2. The final model (code hashes, parameter file hash) is frozen.
3. This document is completed and committed with a date **before** the evaluation script is first run.
4. The evaluation script is written, reviewed and its hash recorded here.

## Fixed now (from the frozen design)

* **Holdout:** 1,100 cases, sorted-ID SHA-256 prefix 2d9235a38706e151 (`final_holdout_freeze/freeze_manifest.json`).
* **Signal:** Solar8000/BT, "patient temperature signal (site not established)", 1-min medians.
* **Horizons:** +20, +30, +60 min. **Comparators:** persistence, linear extrapolation, population curve, generic
  ML, prior-only ablation.
* **Strata:** NON_TERMINAL (primary) and TERMINAL (final 30 min of each recording, reported separately).
* **Metrics:** case-level MAE with a paired bootstrap 95 % CI; 80 % / 95 % coverage (origin-level and
  case-weighted).
* **Decision rules:** the same R1–R4 as development, applied unchanged.

## To be filled in before the run (TBD)

| Item | Value |
|---|---|
| Final model code hashes | TBD |
| Final parameter file hash | TBD |
| Evaluation script name and hash | TBD |
| Date committed | TBD |
| Person authorising the single run | TBD |
