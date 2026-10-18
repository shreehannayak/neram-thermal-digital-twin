# Development fit — decision brief for Sai (17 Oct 2026)

**Your decisions needed before the development fit can run:**
* approve or reject correction **C2**;
* record the **O1–O3** choices.

C1, C3 and C4 do not change the model. Everything here is development-only; the final holdout is not touched.
Evidence comes from `neram_recovery_v3.zip` (SHA-256 49b8c065…aa05, in Downloads):
* `ROOT_CAUSE.md`
* `PROPOSED_CORRECTION.md`
* `diagnostics/DIAGNOSTIC_OUTPUT_2026-10-09.txt` (run read-only on your real dev-train data)

## 1. What exactly failed (verified evidence)
| Step | Evidence | Failing operation |
|---|---|---|
| Likelihood degenerate on quantised data | 15,673,253 / 15,673,253 raw dev-train samples on the 0.1 °C grid. 88.6 % of consecutive minute medians identical. NLL on a 25 % subsample falls monotonically as r → 0: −95,991 at r = 1e-2 down to −504,443 at the 1e-7 bound | All three r1 starts end at γ = 0.002 and q = r = 1e-7 (bounds); q_J = r_O = 0.1 (ratio caps). "success True" only means the optimiser stopped at the bounds |
| Empty learning windows | 161 / 3,342 dev-train cases have 17–30 observed minutes, so all are removed by W_T = 30 | `collapse()` computes −∞ − (−∞) = NaN (core line 196 warning). `eb_step` then `lstsq` gives NaN B, so S = NaN |
| Infinite objective | M0 = X·B1 = NaN for every case | r2_full start NLL = +∞; L-BFGS-B ABNORMAL after 0 iterations, but recorded `done: True` |
| Crash | Hessian finite differences of ∞ − ∞ | `np.linalg.eigvalsh` → LinAlgError |

A rerun of the canonical v1 script (`ab4a251b…`) fails the same way, deterministically. The run produced **no**
dev-val output, so nothing has been unblinded.

## 2. The correction (script `dev_robust_02_fit_and_validate_v2.py`, SHA-256 c02e5de8…339f)
| ID | What | Changes the method? | Recommendation |
|---|---|---|---|
| C1 | Cases with no learning-window observation get the exact zero-information EB values (Λ = 0, η = 0) instead of NaN; they stay in the population | No (numerical bug fix) | Approve |
| **C2** | Adds the known quantisation variance Δ²/12 = 8.33e-4 °C² to r and r_O in every filter, forecast and interval call. A preflight requires ≥ 99.9 % of raw values on the 0.1 grid; the real data give 100 % | **Yes: the observation model** | **Approve, as the smallest defensible change** (reason below) |
| C3 | Fail-closed: any non-finite objective, EB estimate or Hessian stops the run with NUMERICAL_FAILURE; the stage is not marked complete | No | Approve |
| C4 | Staged checkpoints (`--until`), metadata, and refusal of a checkpoint from another model version | No | Approve |

**Why C2:**
* The 0.1 °C resolution is a property of the recording, fixed before any outcome was seen. Sheppard's correction
  is the standard variance of uniform rounding error.
* It bounds the likelihood: each minute contributes at most about +2.6 nats.
* It is implemented by passing adjusted variances to the **unchanged** canonical core, so the synthetic
  verification still applies.

**Alternatives and why not:**
* Raise the lower bound of r: same numbers, but r then sits at a bound, so R4 always fires.
* Exact interval-censored likelihood: correct, but needs non-Gaussian updates inside verified code. Too large a
  change for now.
* Deduplicate repeated values: manipulates data; rejected.

**Effect on pre-registration:**
* C2 changes the model **before** any development result exists.
* The decision rules (`dev_robust_03`, `0f4b58…`) are unchanged.
* The approval command records the v2 script hash and a timestamp on Drive. That record is the evidence that the
  change came before the results.

## 3. Open items O1–O3
These were seen on the quantised synthetic mock with v2. They are expected on real data.

| Item | What it is | Stage affected | Options | Consequence | Recommendation |
|---|---|---|---|---|---|
| **O1** | The empirical-Bayes EM may not reach tol 1e-9 in 1,000 iterations (mock ended at Δ ≈ 1e-3) | `eb1`, `eb2` → `fit_ok` and R4 | (a) keep canonical: report "not converged"; R4 → HUMAN_REVIEW_REQUIRED. (b) Pre-specify a looser stopping rule before running | (a) is honest but blocks an automatic verdict. (b) changes the pre-registered pathology rule | **(a) keep canonical.** Any change now, after O1 has been observed on the mock, invites the forking-paths criticism. HUMAN_REVIEW is an allowed, reportable outcome |
| **O2** | q (calm level variance) at its lower bound 1e-7. q_J = q(1+eˣ) with x ≤ log 1e6 then caps the jump variance at 0.1 °C² | Every fit stage; R4 "near bounds" | (a) keep canonical bounds; R4 flags it. (b) Re-parametrise q_J independently of q | (a) Reported as weak identifiability. (b) A new model, needing new synthetic verification and a new pre-registration | **(a) keep canonical.** A near-zero minute-scale level variance is plausibly a real feature of slowly drifting, quantised data |
| **O3** | γ at its lower bound 0.002/min, where exp(−γt) − 1 becomes almost collinear with t/60 | Every fit stage; R4 | (a) keep canonical; R4 flags it. (b) Fix γ, or drop the redistribution term | (a) Reported as a weakly identified drift shape. (b) Changes the model after seeing mock behaviour | **(a) keep canonical.** The plan already says the parameters are partially confounded and that redistribution physiology is not claimed |

The review pack's cell C18 (v4.2.x) accepts exactly "keep canonical" for O1–O3 and requires the decider's name.
It refuses anything else before a fit starts.

**Most likely outcome on real data:** R4 → `HUMAN_REVIEW_REQUIRED`.

That is a valid result for 20 Oct. The plan (4C.5) allows submission with development results labelled
"development set", and the holdout is deferred to CP6. Report it as: "the twin implementation is verified on
synthetic data; the real-data fit reaches the parameter bounds the quantised signal implies; human review
pending".

## 4. What you are approving (one line each)
* `approve-model --model v2 --reviewer "Sai"` records: C1–C4 accepted; script hash c02e5de8…339f.
* O1, O2, O3 = keep canonical (decider: Sai, date).

The exact commands are in `docs/COLAB_DEV_FIT_RUNBOOK.md`.
