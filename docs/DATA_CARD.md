# Data card (owner: Sai)

## Source
VitalDB: an open intraoperative biosignal dataset, 6,388 non-cardiac surgical cases from Seoul National University
Hospital (Aug 2016 – Jun 2017). It is accessed through its public API.

Cite: Lee H-C et al., *VitalDB, a high-fidelity multi-parameter vital signs database in surgical patients*,
Scientific Data 9, 279 (2022). Use is governed by the VitalDB Data Use Agreement. **Read it before redistributing
anything derived from cases.**

## Signal
`Solar8000/BT`, used as the "patient temperature signal". **Its anatomical site is not established.** It is
recorded on a 0.1 °C grid. It was checked against pulmonary-artery catheter temperature in 63 usable
liver-transplant cases (Code 2). That check does not establish it as core temperature.

## Cohort and splits
* Usable BT cases after the census, duplicate resolution (18 duplicate track IDs, fixed rule) and plausibility
  filtering (25–43 °C): see the Code 1–4 outputs (Drive).
* **Final holdout:** 1,100 cases, frozen deterministically (seed 20261101), sorted-ID hash prefix
  2d9235a38706e151. It has never been used in fitting, plots, controller tests, Unity or video.
* **Development pool:** 4,456 cases, split into dev-train 3,342 / dev-val 1,114 (seed 20261201).
* The former Code 4 exploratory test cases are now development data, and their earlier persistence result
  is disclosed (`docs/RESULTS.md`).

## What is and is not in this repository
* **Included:** code, configuration, synthetic data and synthetic replays, the holdout freeze manifest and the ID
  lists (once committed). All replays are `cohort: SYNTHETIC`.
* **Not included:** `vitaldb_bt_cache/`, case-level clinical metadata, case-level predictions or metrics, and any
  holdout output. A development-case replay (SCN_A) may only be built locally, and committed only if the Data Use
  Agreement allows it.

## Guards
* `build_replay.py` refuses holdout case IDs, and refuses REAL_DEV observations in a SYNTHETIC replay.
* Both validators reject any cohort other than SYNTHETIC or DEVELOPMENT.
* Unity's EditMode tests assert each shipped replay's cohort.
* `twin_replay_export.py` refuses DEVELOPMENT exports until fitted parameters exist.

## Development-case duration statistics (hardware power-budget handoff, plan 4T)
**BLOCKED in the laptop workspace.** The only valid source, `code4_outputs/code4_cohort_manifest.csv`
(`covered_minutes`, `settled_minutes`), is on Drive and in Colab.

The exact development-only procedure is Cell 7 of `docs/COLAB_DEV_FIT_RUNBOOK.md`:
* it filters to the 4,456 development IDs;
* it reports n, median and P90 in minutes, plus the source hash;
* the output is aggregates only, written to `results/development/dev_case_duration_stats.json`.

No estimate is given until that cell has run.

## Fit status
The robust model's real-data development fit **failed** (docs/RESULTS.md §2; cause and decision in
docs/FIT_DECISION_BRIEF.md). No fitted parameter exists, so no real-data twin output and no development replay
(SCN_A / DEV_<pseudo>) has been produced.
