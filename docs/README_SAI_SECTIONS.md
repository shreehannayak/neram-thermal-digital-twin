# Root README — Sai's sections (proposed text; Shreehan assembles and owns README.md)

Paste into the matching sections. Links in §16 stay empty until real URLs exist.

## §1 Title
NERAM — a sequentially updated, patient-specific thermal digital twin for intraoperative temperature forecasting
(proof-of-concept).

## §4 Problem statement
Intraoperative temperature drifts slowly, and a population curve says little about the patient on the table. NERAM
estimates one patient's temperature-signal trajectory from that patient's own monitor data as the case
progresses. It forecasts the next 20–60 minutes with uncertainty, and separates artefacts and level shifts from
real change. Warming/fluid scenarios are shown as clearly labelled ASSUMED simulations, never as predicted
effects.

## §5 Healthcare use case
Decision support for the anaesthesia team: a calibrated look-ahead of the patient temperature signal, with a
flag when the twin is unreliable (gaps, artefacts, initialisation). A simulated, clinician-supervised warming
controller shows how such a forecast could feed a supervised workflow.

## §6 What the prototype is and is not
**Is:**
* A verified state-space twin implementation, exported per minute.
* A reproducible, holdout-protected VitalDB development pipeline.
* A simulated controller and hardware stand-in.
* A Unity replay viewer.

**Is not:**
* It does not measure core temperature: the BT probe site is not established.
* It is not a validated forecaster: the real-data fit has not succeeded yet.
* It is not a treatment device.
* It is not clinically validated or certified.
* It is not evidence of any warming effect: none exists in VitalDB.

## §7 Architecture
See `docs/ARCHITECTURE.md`. Twin = estimation and forecasting. Controller = simulated supervision. Unity =
replay-only visualisation. One JSONL replay contract joins them.

## §8 Digital Twin and results
See `docs/MODEL_CARD.md` and `docs/RESULTS.md`.

The development pipeline and holdout freeze are complete and reproducible. The robust model's real-data fit
**failed**; its two causes (0.1 °C quantisation and empty post-exclusion cases) are diagnosed, and a correction is
pending review. The implementation passes synthetic checks: closed-form Gaussian limit, Monte Carlo agreement of
P(below t_hypo), and no future leakage.

In the earlier exploratory test, persistence beat the old (inconsistent) sequential model. That result is
disclosed.

## §12 Unity demo
Open `unity_editor/` in Unity 6000.3.26f1 and run NERAM → 1. Run full setup, then Play.

All 11 shipped scenarios are SYNTHETIC: the SYN_SCN_* demo set (plan SCN_A layout stand-in, SCN_B, SCN_C, SCN_D),
SYN_ENG_01–06, and SYN_TC07 (Suchita's TC07 over-temperature shutdown log; latch only, no heating). The
development-case SCN_A needs the development fit. Every simulated or assumed value carries a source tag. The footer reads
"Proof-of-concept. SIMULATED / ASSUMED PROTOTYPE RESPONSE where marked."

## §13 Technical stack / model
* Python with NumPy, SciPy and pandas (`environment.yml`).
* GPB2 switching state-space filter with jump/outlier mixtures (`src/thermal_robust_core.py`).
* Unity 6 (URP, UI Toolkit), C# replay loader and validator mirrored by Python.
* Controller: MATLAB/Simulink/Stateflow (Suchita).

## §14 Reproduce Sai's components
```
python src/thermal_robust_core.py                 # core self-test
python tools/make_twin_syn_outputs.py --check     # four synthetic twin exports (canonical filter)
python integration/validate_twin_output.py integration/twin_outputs/twin_SYN_0*.csv
python tools/run_all_tests.py                     # every tests/test_*.py (PASS / FAIL / BLOCKED)
python integration/validate_replay.py integration/replays/*.jsonl.gz
python tools/check_replay_semantics.py integration/replays/*.jsonl.gz
python tools/sync_unity_streaming_assets.py --check
```
The development pipeline runs in Colab in the order listed in `docs/AUDIT_TRAIL.md`.

## §15 Data and licence
VitalDB (Lee H-C et al., Sci Data 2022), used under the VitalDB Data Use Agreement. No case-level clinical data and
no holdout material are in this repository. Replays are synthetic.

## §16 Links
Architecture PDF: `docs/architecture.pdf` (in the repository). Video: TBD (not recorded). Presentation: TBD (Shreehan).
