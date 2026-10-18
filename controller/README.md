# NERAM supervisory controller - Python fallback

Owner: Suchitha (supervisory controller, plan pp. 4-23). **SIMULATED / ASSUMED prototype. No clinical efficacy or clinical validation is claimed.**

MATLAB/Simulink/Stateflow were not available, so the controller, test bench, tests, logs, plots and tables are implemented and
run in Python. This is a *fallback*: the native `.slx`/Stateflow deliverables are **not** produced (list at the end).

> **Code rebuilt on 18 Oct 2026.** Suchitha's v2 design, specification, results and logs are hers. The original v2
> source files (made in a Claude chat session) were lost before upload, so Sai rebuilt `neram_ctrl/` and the scripts
> from her specification (`docs/controller_spec.md`) on 18 Oct. The rebuild reproduces her five received v2 logs
> **byte for byte** and 129 of her 132 result rows exactly; the 3 remaining rows are the TC17 stress-noise
> transition counts (all criteria still PASS). Evidence and every known difference: `REBUILD_2026-10-18_SAI.md`.

## Environment actually used

| item | version |
|---|---|
| Python | 3.13.16 |
| numpy | 2.5.3 |
| matplotlib | 3.11.2 |

Linux, no GPU. Install: `pip install numpy matplotlib` (both are in the repository's `environment.yml`). The v2
video and figure images in `docs/` were made with Suchitha's v2 tooling (pandas, Pillow, imageio-ffmpeg) and are
kept as received; the rebuild does not regenerate them.

## Run everything (one command, about 1 minute)

```
cd controller
python scripts/run_all_tests.py             # TC01-TC19 (+TC20 listed as EXCLUDED), audit, logs, tables, plots
python scripts/run_all_tests.py --no-figs   # same without the PNG plots (~40 s)
python scripts/check_interface.py           # re-validates the six handoff logs against section S
```

The run is deterministic (numpy seed 42). It prints every PROVISIONAL / ASSUMED / placeholder parameter used, checks
the six handoff logs, and compares five of them with Suchitha's received v2 logs (`results/reproduction_check.csv`).

## Where things are

| path | content |
|---|---|
| `neram_ctrl/` | `params.py` (standalone table), `blocks.py` (TwinAdapter, FaultMonitor, Supervisor, DemandLaw, channel limiter), `testbench.py` (test-only stand-ins, synthetic scenarios, fault injection, log writer), `tests.py` (TC01-TC20 set-ups and criteria), `tc19.py`, `audit.py`, `logcheck.py`, `tables.py`, `plots.py` |
| `scripts/run_all_tests.py`, `scripts/check_interface.py` | orchestrator; section-S check of the handoff logs |
| `../integration/controller_logs/` | the six handoff logs `ctrl_SYN_02, ctrl_TC04, ctrl_TC05, ctrl_TC07, ctrl_TC08, ctrl_TC13` (copies in `results/logs/`) |
| `results/test_results.csv` | unified results table (one row per acceptance criterion) |
| `results/tables/` | T01 `T01_io.csv`, T02 `T02_params_used.csv`, `transition_table.csv`, `test_results.csv`, `fault_response_matrix.csv`, `requirements_traceability.csv`, T07 `T07_duty_stats.csv`, `audit_checks.csv` (section-G audit) |
| `results/plots/` | P01-P05 per test as `TCxx_P0n.png` (1600x900): state, heat and demand, module sensors, alerts and faults, temperature. (v2 had P01-P09; the rebuild draws these five.) |
| `results/logs/` | per-test 1 Hz controller logs (handoff names + one per remaining TC up to TC17) |
| `results/reproduction_check.csv`, `results/run_console.txt` | rebuilt vs received v2 logs; console output of the last run |
| `docs/controller_spec.md` | architecture, states, transitions, faults, parameters, assumptions, limitations (Suchitha v2) |
| `docs/figures/*_PYTHON_FALLBACK.jpg`, `docs/slide_controller_1/2.jpg`, `docs/demo_controller.mp4` | v2 figures, slides and ~2.3 min video, as received (S01-S07 screenshots were not received) |

## Inputs that were NOT supplied (dependencies)

- `config/params.json` (Sai) -> the controller uses the standalone table in `neram_ctrl/params.py` (values carried unchanged from the submitted script, every one labelled). The rebuild keeps the published results on this table and does **not** read `config/params.json` automatically (it now exists in the repository, with for example `data_stale_hw_s` = 2 s instead of the placeholder 5 s); `load_params(path)` overlays a JSON file for experiments. Nothing was changed in Sai's or Shreehan's values.
- `interface_spec.csv`, `fault_codes.csv`, `twin_SYN_xx.csv` -> section-S columns/enums and the section-3W fault-code list were taken from the plan text; synthetic twin signals are generated in `testbench.py`.
- `twin_DEV_<pseudo>.csv` (Sai) -> **TC19 is BLOCKED**. The integration path is ready in `neram_ctrl/tc19.py` (drop the file into `integration/twin_outputs/` or set `NERAM_TWIN_DEV`).
- Shreehan: module sensor valid range and `t_hw_cutoff_degC` -> range check (codes x02/x04) is implemented but disabled until supplied; no value invented.
- Sai: `plant_passive.*` -> flat passive trajectory placeholder; plant gain is `ASSUMED`.

## Native deliverables NOT produced (need MATLAB/Simulink/Stateflow)

`neram_controller.slx`, `neram_testbench.slx`, the MATLAB `.m` scripts and enum classes, a native Stateflow chart, native S01-S06 screenshots, the Simulation Data Inspector view, and a native `run_all_tests.m`. The `*_PYTHON_FALLBACK.png` images are drawn by code from the Python run and are labelled as such; none is a Simulink/Stateflow/SDI screenshot.

## Figures

All figures are drawn from the Python fallback run (labelled `PYTHON_FALLBACK`; none is a Simulink/Stateflow screenshot).
SIMULATED / ASSUMED prototype responses.

| Controller architecture | State chart (7 states, 14 transitions) |
|---|---|
| <img src="docs/figures/controller_block_diagram_PYTHON_FALLBACK.jpg" width="100%"> | <img src="docs/figures/stateflow_chart_PYTHON_FALLBACK.jpg" width="100%"> |
| **Test bench (hardware stand-ins)** | **Architecture slide** |
| <img src="docs/figures/testbench_overview_PYTHON_FALLBACK.jpg" width="100%"> | <img src="docs/slide_controller_1.jpg" width="100%"> |

<img src="docs/slide_controller_2.jpg" width="100%">

Demo video of the real run data: [`docs/demo_controller.mp4`](docs/demo_controller.mp4).

