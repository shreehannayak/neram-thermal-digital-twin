# tests/ (owner: Sai)

| File | What it proves | Needs |
|---|---|---|
| test_interface.py | config/enums.json equals plan 0.4; interface spec complete; twin columns agree across spec, exporter, builder and validator; section-1S log contract; replay field registry = plan 4F; params structure, statuses and owners per plan section 6; C# built-in enum fallback = config | stdlib |
| test_replay_schema.py | every line of every shipped replay validates against unity/schema/replay_schema.json; broken lines are rejected | jsonschema |
| test_p_below_hypo_mc.py | P_below_hypo vs 200,000-draw Monte Carlo at +20/+30/+60; the CDF agrees with the exported 80/95 % bounds; Gaussian limit; monotone and bounded | numpy, scipy |
| test_twin_export.py | core hash; no future leakage; Twin_Valid rule (plan 4A, strict <); thresholds read from params.json; DEVELOPMENT export refused; 4 synthetic outputs valid, distinct, reproducible; twin-validator negative cases; assumed-warming equation and ×0.5/1/2 grid | numpy, scipy |
| test_controller_log_integration.py | section-1S strict by default; exact field survival TC07; shutdown timing; STANDIN kept (W108); unknown columns rejected; SYN_TC07 reproducible; semantic checks catch TC05/TC13 and injected faults | stdlib |
| test_validate_replay.py | 62-fixture corpus shared with the C# validator | stdlib |
| test_unity_ui_contract.py | static UI contract (72 element lookups, wording guards). STATIC only — not runtime proof | stdlib |
| robust_statespace_verification.py, recovery_resume.py | canonical synthetic verification (unchanged copies; run with `PYTHONPATH=src`, recovery first, until ALL DONE) | numpy, scipy |

Run everything: `conda env create -f environment.yml && conda activate neram && python -m pytest -q tests`.
