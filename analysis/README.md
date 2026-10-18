# analysis/ — development pipeline scripts (owner: Sai)

Byte-identical copies of the canonical Colab scripts (verified against EXPECTED_SHA256 and
`neram_recovery_v3/canonical_scripts/SHA256SUMS`). **Do not edit**: their hashes are the audit trail
(docs/AUDIT_TRAIL.md). They run in Colab from `/content` with `thermal_robust_core.py` beside them; from the
repository, run with `PYTHONPATH=src`.

| File | SHA-256 | Order (plan 4B) |
|---|---|---|
| development_model_adequacy.py | d131c745794b3f6807f71121b126588fce375821f7451952885601aa66c580ef | 1 |
| development_event_forensics.py | 4f39b93092b9554a77be32da1771807f6bda2102e532672bcb30889e1f5b4063 | 2 |
| dev_robust_01_fetch_case_metadata.py | 584d6741b5961978073a39cc9dd1c3883c70f00d4e76e8890568de9954a1a8ae | 3 |
| dev_robust_02_fit_and_validate.py (v1, canonical, fails on quantised data) | ab4a251bdc11c7b1d3bc7e48ae465720f6a91007d20992d29418969b991a8938 | 4 |
| dev_robust_03_apply_preregistered_rules.py (pre-registered rules) | 0f4b58be36d7ff2ec93332f028a9a57ca682dc13d547b8a92830349446c36a91 | 5 |

The proposed v2 fit (`dev_robust_02_fit_and_validate_v2.py`, c02e5de8…339f) is **not** copied here until
you approve it (docs/FIT_DECISION_BRIEF.md). It lives in `neram_recovery_v3.zip`.

**Missing (plan section 7 lists them; not found on this computer):**
* Code 1 (census) and Code 2 (BT vs PA): these exist only in earlier chat transcripts and must be recovered and
  hash-recorded.
* Code 3 / 3B, Code 4 and `freeze_final_holdout.py`: they ran in Colab; take them from the Colab notebook or Drive.
* `final_holdout_evaluation.py`: written only after `docs/PREREGISTRATION_final.md` (CP6).
