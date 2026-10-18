"""
dev_robust_03_apply_preregistered_rules.py

PRE-REGISTERED development decision rules, applied mechanically to the outputs of
dev_robust_02_fit_and_validate.py. Record this file's SHA-256 (printed below and in the output JSON)
BEFORE running dev_robust_02; the rules must not be edited after development results are seen.

Reads ONLY development outputs (no data, no network, no holdout):
  dev_robust_outputs/dev_val_paired_bootstrap.csv
  dev_robust_outputs/dev_val_calibration.csv
  dev_robust_outputs/dev_fit_parameters.json
Writes:
  dev_robust_outputs/preregistered_decision.json
  dev_robust_outputs/preregistered_decision.md

RULES (fixed before development results exist)
  R1 Forecast superiority (stratum NON_TERMINAL; case-level paired bootstrap of
     persistence case-MAE minus robust case-MAE, 95% CI):
       claim allowed only if CI lower bound > 0 at +20 AND +30,
       AND robust is not significantly worse at +60 (CI upper bound >= 0 at +60).
  R2 Robust significantly WORSE at +20 or +30 (CI upper bound < 0) ->
       no superiority narrative; contribution = persistence-equivalent point forecast
       + calibrated uncertainty (only if R3 holds) + artefact/event attribution.
  R3 Calibrated-uncertainty claim allowed only if robust NON_TERMINAL origin-level 80% coverage
     lies in [0.75, 0.85] at +20, +30 and +60 (case-weighted coverage reported alongside).
  R4 Pathology flags (any flag -> HUMAN REVIEW REQUIRED before interpretation; never an automatic
     abandonment): optimiser failure in r1_full/r2_full/wt0_full; any final parameter near a bound;
     subsample Hessian not positive definite; multi-start NLL spread > MULTISTART_NLL_TOL nats;
     EB round 2 not converged.
Strata, horizons and the stratum used are fixed here; nothing is chosen after seeing results.
"""

import hashlib
import json
import os
import sys

import pandas as pd

OUT = "dev_robust_outputs"
BOOT = os.path.join(OUT, "dev_val_paired_bootstrap.csv")
CAL = os.path.join(OUT, "dev_val_calibration.csv")
PAR = os.path.join(OUT, "dev_fit_parameters.json")
STRATUM = "NON_TERMINAL"
SUPERIORITY_HORIZONS = (20, 30)
NOT_WORSE_HORIZON = 60
CAL_LEVEL, CAL_LO, CAL_HI = 0.8, 0.75, 0.85
MULTISTART_NLL_TOL = 1.0

with open(__file__, "rb") as fh:
    SELF_SHA = hashlib.sha256(fh.read()).hexdigest()
print(f"Rules file SHA-256: {SELF_SHA}")

missing = [p for p in (BOOT, CAL, PAR) if not os.path.exists(p)]
if missing:
    print(f"STOP: development outputs missing {missing}; run dev_robust_02_fit_and_validate.py first.")
    sys.exit(1)

boot = pd.read_csv(BOOT)
cal = pd.read_csv(CAL)
par = json.load(open(PAR))
b = boot[(boot.stratum == STRATUM) & (boot.comparator == "persistence")].set_index("horizon")
need = set(SUPERIORITY_HORIZONS) | {NOT_WORSE_HORIZON}
if not need <= set(b.index):
    print(f"STOP: bootstrap rows for persistence/{STRATUM} missing horizons {sorted(need - set(b.index))}")
    sys.exit(1)

r1 = {h: dict(diff=float(b.loc[h, "mean_caseMAE_comparator_minus_robust"]), ci=[float(b.loc[h, "ci95_lo"]), float(b.loc[h, "ci95_hi"])])
      for h in sorted(need)}
superior = all(r1[h]["ci"][0] > 0 for h in SUPERIORITY_HORIZONS) and r1[NOT_WORSE_HORIZON]["ci"][1] >= 0
worse = any(r1[h]["ci"][1] < 0 for h in SUPERIORITY_HORIZONS)

c = cal[(cal.stratum == STRATUM) & (cal.method == "robust") & (cal.nominal == CAL_LEVEL)].set_index("horizon")
r3 = {int(h): dict(coverage_origin=float(c.loc[h, "coverage_origin"]), coverage_case_weighted=float(c.loc[h, "coverage_case_weighted"]))
      for h in c.index}
calibrated = len(r3) == 3 and all(CAL_LO <= v["coverage_origin"] <= CAL_HI for v in r3.values())

opt = par["optimisation"]
flags = []
for k in ("r1_full", "r2_full", "wt0_full"):
    if not opt[k].get("success"):
        flags.append(f"optimiser not successful: {k} ({opt[k].get('message')})")
if opt["r2_full"].get("near_bounds"):
    flags.append(f"final parameters near bounds: {opt['r2_full']['near_bounds']}")
if not par["diagnostics"].get("hessian_positive_definite"):
    flags.append("subsample Hessian not positive definite (weak identifiability)")
nlls = [m["nll"] for m in par["multistart"]]
if max(nlls) - min(nlls) > MULTISTART_NLL_TOL:
    flags.append(f"multi-start NLL spread {max(nlls) - min(nlls):.2f} > {MULTISTART_NLL_TOL} nats")
if not par["eb_round2"].get("converged"):
    flags.append("EB round 2 not converged")

if flags:
    verdict = "HUMAN_REVIEW_REQUIRED"
elif superior:
    verdict = "SUPERIORITY_CLAIM_ALLOWED"
elif worse:
    verdict = "ROBUST_WORSE_AT_SHORT_HORIZON__NO_SUPERIORITY_NARRATIVE"
else:
    verdict = "NO_DISTINGUISHABLE_DIFFERENCE__PERSISTENCE_EQUIVALENT_POINT_FORECAST"
contribution = ("superior point forecasts" if verdict == "SUPERIORITY_CLAIM_ALLOWED" else "persistence-equivalent point forecasts") \
    + (" + calibrated uncertainty" if calibrated else " (uncertainty NOT claimed calibrated)") + " + artefact/event attribution"

out = dict(rules_sha256=SELF_SHA, stratum=STRATUM, R1_persistence_minus_robust=r1, R1_superiority_claim_allowed=superior,
           R2_robust_worse_at_20_or_30=worse, R3_coverage_80=r3, R3_calibration_claim_allowed=calibrated,
           R4_pathology_flags=flags, VERDICT=verdict, PERMITTED_CONTRIBUTION=contribution,
           note="Development evidence only; the final holdout has not been evaluated.")
json.dump(out, open(os.path.join(OUT, "preregistered_decision.json"), "w"), indent=2)
md = f"""# Pre-registered development decision

Rules file SHA-256: `{SELF_SHA}` (must match the value recorded before dev_robust_02 was run)
Stratum: {STRATUM}; comparator: persistence; case-level paired bootstrap 95% CI.

| horizon | persistence - robust (C) | 95% CI |
|---|---|---|
""" + "\n".join(f"| +{h} | {v['diff']:+.4f} | [{v['ci'][0]:+.4f}, {v['ci'][1]:+.4f}] |" for h, v in r1.items()) + f"""

R1 superiority claim allowed: {superior}
R2 robust significantly worse at +20/+30: {worse}
R3 80% coverage (non-terminal, origin-level / case-weighted): {r3}; calibration claim allowed: {calibrated}
R4 pathology flags: {flags if flags else 'none'}

VERDICT: {verdict}
PERMITTED CONTRIBUTION: {contribution}
Development evidence only; the final holdout has not been evaluated.
"""
open(os.path.join(OUT, "preregistered_decision.md"), "w").write(md)
print(md)
