# Development pre-registration (owner: Sai)

**Status: rules fixed in code. The dated commit is NOT yet made.** The laptop workspace is not a Git repository,
so there is no commit timestamp yet. Plan 4B requires this file to be pushed **before** `dev_robust_02` runs. The
v3 helper's `lock-rules` step also records the hash on Drive with a timestamp (docs/COLAB_DEV_FIT_RUNBOOK.md,
Cell 6). Do both before the fit.

The development decision rules are implemented in `dev_robust_03_apply_preregistered_rules.py`. Its SHA-256
must be recorded in a dated commit, or a dated Drive copy, **before** `dev_robust_02_fit_and_validate.py`
produces any development-validation output:

```
0f4b58be36d7ff2ec93332f028a9a57ca682dc13d547b8a92830349446c36a91  dev_robust_03_apply_preregistered_rules.py
```

This hash matches the file in the project's EXPECTED_SHA256 list. No dev-val result has been produced yet: the
fit failed before validation, so the rules have not been seen against results.

## Rules (summary of the code; the code is authoritative)

* **Stratum:** NON_TERMINAL targets of the dev-val split (1,114 cases). Comparator: persistence. Case-level
  paired bootstrap, 95 % CI.
* **R1 forecast superiority:** CI lower bound for (persistence MAE − robust MAE) > 0 at +20 and +30 min, AND
  the CI upper bound ≥ 0 at +60.
* **R2:** robust significantly worse at +20 or +30 (CI upper bound < 0) → no superiority narrative.
* **R3 calibrated uncertainty:** non-terminal origin-level 80 % coverage within [0.75, 0.85] at all three
  horizons.
* **R4 pathology → HUMAN_REVIEW_REQUIRED:** any optimiser failure, any final parameter near a bound, a subsample
  Hessian that is not positive definite, a multi-start NLL spread above 1 nat, or EB round 2 not converged.

## Open decisions to make BEFORE any development result exists

* O1–O3 (C18 in recovery pack v4.2.2): the only accepted value for each is "keep canonical". A decider's name is
  required.
* C2 (0.1 °C rounding variance) needs a reviewer sign-off; approval records the v2 script hash
  (c02e5de85240d3cb47f30b06820ed3b404a0883134512a1a47fd9aa682a6339f). Analysis and recommendation:
  docs/FIT_DECISION_BRIEF.md.
