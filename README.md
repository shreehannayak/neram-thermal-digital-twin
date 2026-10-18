# NERAM: Thermal Digital Twin and Simulated Warming Controller

> A sequentially updated, patient-specific thermal digital twin that forecasts one patient's intraoperative
> temperature signal 20–60 minutes ahead with uncertainty, shown with a simulated, clinician-supervised
> four-channel warming controller and a Unity replay viewer. Proof-of-concept.

**Proof-of-concept prototype, not a medical device.** SIMULATED / ASSUMED PROTOTYPE RESPONSE where marked. No
clinical efficacy, clinical validation or standards compliance is claimed.

## 1. Title and one-line summary
**NERAM: Thermal Digital Twin and Simulated Warming Controller** (identical in this README, `CITATION.cff`,
slide 1 and the video title).

A patient-specific thermal digital twin that estimates and forecasts the intraoperative temperature signal from
the patient's own monitor data, with a simulated supervised warming controller and a 3D replay viewer.

## 2. Team and contributions
| Member | Role | Contribution |
|---|---|---|
| Saiyugan (Sai) | Lead; Digital Twin, integration, Unity viewer | Twin model and export (`src/`, `analysis/`), replay contract and validators (`integration/`, `config/`, `tests/`), Unity viewer (`unity_editor/`), CAD integration, documentation (`docs/`) |
| Suchitha | Supervisory controller | Controller states, fault handling, test bench, test cases and logs (`controller/`), Python fallback because MATLAB/Simulink was unavailable |
| Neharika | CAD | Hand and foot warming modules, wearable display concept, bedside controller (`cad/`) |
| Shreehan | Hardware, repository, licences, audit | Hardware architecture, safety layers, comparisons, BOM, power budget, interfaces (`hardware/`), README skeleton, licences, submission audit |

Each member confirms their own line in a GitHub comment.

## 3. College / incubator
TBD: must match the registration exactly (to be filled in from the registration form).

## 4. Problem statement
Intraoperative temperature drifts slowly, and a population curve says little about the patient on the table.
NERAM estimates one patient's temperature-signal trajectory from that patient's own monitor data as the case
progresses. It forecasts the next 20–60 minutes with uncertainty and separates artefacts and level shifts from
real change. Warming and fluid scenarios are shown as clearly labelled ASSUMED simulations, never as predicted
effects.

## 5. Healthcare use case
Decision support for the anaesthesia team: a calibrated look-ahead of the patient temperature signal, with a flag
when the twin is unreliable (gaps, artefacts, initialisation). A simulated, clinician-supervised warming
controller shows how such a forecast could feed a supervised workflow.

## 6. What the prototype is and is not
**Is:**
- A verified state-space twin implementation, exported per minute.
- A reproducible, holdout-protected VitalDB development pipeline.
- A simulated controller with hardware stand-ins, and a paper hardware design.
- A Unity replay viewer (standalone Windows app) that plays validated replay files.

**Is not:**
- It does not measure core temperature: the BT probe site is not established.
- It is not a validated forecaster: the real-data fit has not succeeded yet (section 8).
- It is not a treatment device, and no hardware has been built.
- It is not clinically validated or certified.
- It is not evidence of any warming effect: none exists in VitalDB.

Full text: `docs/SAFETY_AND_LIMITATIONS.md`.

## 7. System architecture
Twin = estimation and forecasting. Controller = simulated supervision. Unity = replay-only visualisation. One JSONL
replay contract (`config/interface_spec.csv`, `unity/schema/`) joins them.

`docs/architecture.pdf` (source `docs/ARCHITECTURE.md`, `docs/architecture_src/`).

## 8. Digital Twin and results
See `docs/MODEL_CARD.md`, `docs/RESULTS.md` and `docs/DATA_CARD.md`.

- **Implementation verified on synthetic data:** closed-form Gaussian limit, Monte Carlo agreement of
  P(below t_hypo), no future leakage, Twin_Valid rules. Figures: `results/figures/` (SYNTHETIC).
- **Real-data development fit: FAILED / not completed.** Two causes are diagnosed (0.1 °C quantisation of the
  readings; cases left empty after the terminal exclusion). A correction is written but not approved or run.
  Nothing about real-data forecasting performance is claimed.
- **Disclosure:** in the earlier exploratory test, persistence beat the old (inconsistent) sequential model at
  +20/+30/+60 min.
- **Holdout:** 1,100 cases are frozen and untouched; the one-time evaluation is defined in
  `docs/PREREGISTRATION_final.md`. No holdout result exists.

## 9. Controller
Supervisory controller (owner: Suchitha), implemented as a **Python fallback** because MATLAB/Simulink/Stateflow
were not available. Seven states, 14 transitions and latched faults; five blocks run every second (TwinAdapter,
FaultMonitor, Supervisor, DemandLaw, channel limiter). Test results: TC01–TC18 PASS, TC19 BLOCKED (needs a
development twin file), TC20 excluded. All responses are SIMULATED / ASSUMED.

Details: `controller/README.md`, `controller/docs/controller_spec.md`, results in `controller/results/`, demo video
`controller/docs/demo_controller.mp4`. Still to come from Suchitha: the code folder (`neram_ctrl/`) and the v2
TC04 log (`controller/RECEIVED_2026-10-18_SAI.md`).

## 10. Hardware
The hardware layer is a paper design of a four-channel warming controller. In the demo every hardware signal is SIMULATED by the controller test bench stand-ins. No physical device has been built, and no heat delivery, clinical effect or standards compliance is claimed. Standards are cited as design references only.

**Architecture.** A bedside host laptop runs the Digital Twin and the supervisory controller. It sends a heating command (Heat_1 to Heat_4, as PWM duty percent) to a microcontroller board every second. The board reads two skin-interface temperature sensors (A and B) per module and a current sensor per channel, drives four heater channels, and reports status back. The four channels are CH1 left hand, CH2 right hand, CH3 left foot and CH4 right foot.

**Three independent safety layers.**
1. Hardware cutoff (no firmware): works with the microcontroller halted and latches until manually reset.
2. Microcontroller firmware: limits, an independent watchdog, a host-heartbeat check and stuck-on detection.
3. Supervisory controller (software).
A master safety switch, default open, sits in series with all four channels. Each layer can remove heater power without the layers above it.

**Provisional choices (CP3).**
- Heater: polyimide flexible heater, Omega KHLVA series (28 V). It is not self-limiting, so the hardware cutoff is essential.
- Microcontroller: STM32 Nucleo-G474RE. Its output state at reset must still be verified.
- Temperature sensor: four types compared (NTC thermistor, Pt1000, digital IC, thermocouple); NTC chosen PROVISIONAL (`hardware/docs/module_sensing.md`).

**Status of values.** Every hardware number has a source and a status (FROZEN, PROVISIONAL or TBD). Heater power, current thresholds, module temperature thresholds and the skin-surface limit are TBD until sourced from datasheets, a standard or a clinician. Nothing was estimated to fill a gap.

**Files.** See hardware/README.md for the full list: diagrams (block diagram, safety layers, interface map), comparisons (sensor, MCU, heater), documents (observation interface, module sensing, power architecture, standards references, feasibility), interface files (fault codes, communication protocol, controller interface, CAD envelope), power budget and electrical bill of materials.

## 11. CAD
Owner: Neharika. Hand modules (CH1 left, CH2 right: palmar pad of liner, heater film, insulation and shell with two
sensors and two straps), foot modules (CH3, CH4: sole pads), a display-only wrist wearable concept (no controls, no
battery) and the bedside controller enclosure.

- `cad/exports/source_fusion_2026-10-18/`: the Fusion exports as received.
- `cad/exports/unity/`: Unity-ready copies (metres, Y up, plan names, `MAT_*` materials; shapes unchanged).
- `cad/IMPORT_CHECK_SAI_2026-10-18.md`: import check, what was changed, what is still open (strain relief,
  assembly file, STEP/native files, renders, drawings).
- `cad/renders/unity_preview_2026-10-18/`: the models in the Unity viewer.

## 12. Unity demo
Replay viewer for the twin, controller and hardware stand-ins (Unity 6000.3.26f1, URP, UI Toolkit).

- **Run the app:** build it once with **NERAM → 6. Build Windows player**, then start
  `build/NERAM_Windows/NERAM.exe`. It opens as a normal maximised window that can be pinned to the taskbar; F11 or
  FULLSCREEN toggles full screen.
- **Open the project:** Unity Hub → Add → `unity_editor/`, open with 6000.3.26f1, then **NERAM → 1. Run full setup**
  and Play. Guides: `docs/UNITY_WORKSPACE_README.md`, `docs/NERAM_Viewer_User_Guide.pdf`,
  `docs/NERAM_Simulation_Handbook.pdf`.
- **Scenarios:** all 11 shipped replays are SYNTHETIC: SYN_SCN_A0/B/C/D (demo set), SYN_ENG_01–06 and SYN_TC07
  (Suchitha's over-temperature shutdown log; latch only). Every simulated or assumed value carries a source tag.
- **3D models:** Neharika's CAD placed on a generated mannequin (`tools/gen_cad_fit.py`, `Editor/NeramCadPlacement.cs`).
  The mannequin, table, room and cables are generated stand-ins; the pad drape and strap length are visual fits.

## 13. Technical stack
| Part | Stack | Where |
|---|---|---|
| Digital Twin | Python 3, NumPy, SciPy, pandas; GPB2 switching state-space filter with jump/outlier mixtures | `src/`, `analysis/`, `environment.yml` |
| Integration | Python validators, JSONL replay contract, JSON Schema | `integration/`, `config/`, `unity/schema/`, `tests/` |
| Controller | Python (fallback for MATLAB/Simulink/Stateflow) | `controller/` |
| Viewer | Unity 6000.3.26f1, URP, UI Toolkit, Input System, C# | `unity_editor/` |
| CAD | Autodesk Fusion (FBX export); Python FBX prep tools | `cad/` |
| Hardware | draw.io diagrams, CSV/Markdown design files | `hardware/` |

## 14. How to reproduce
Twin, integration and tests (Python, `environment.yml`):
```
python src/thermal_robust_core.py                 # core self-test
python tools/make_twin_syn_outputs.py --check     # four synthetic twin exports
python integration/validate_twin_output.py integration/twin_outputs/twin_SYN_0*.csv
python tools/run_all_tests.py                     # every tests/test_*.py (PASS / FAIL / BLOCKED)
python integration/validate_replay.py integration/replays/*.jsonl.gz
python tools/check_replay_semantics.py integration/replays/*.jsonl.gz
python tools/sync_unity_streaming_assets.py --check
```
The development pipeline runs in Colab in the order listed in `docs/AUDIT_TRAIL.md` (`docs/COLAB_DEV_FIT_RUNBOOK.md`).

Unity viewer: section 12 (EditMode tests: Window → General → Test Runner → EditMode → Run All).

Controller: `controller/README.md` (needs the `neram_ctrl/` code folder, still to be uploaded).

CAD prep: `python cad/tools/fixneha.py <out_dir> cad/exports/source_fusion_2026-10-18/`.

## 15. Data and licence notice
VitalDB (Lee H-C et al., *Sci Data* 9:279, 2022, doi:10.1038/s41597-022-01411-5), used under the VitalDB Data Use
Agreement. No case-level clinical data and no holdout material are in this repository; every replay and twin file
here is SYNTHETIC. Development and holdout outputs (`results/development/`, `results/final/`) are not published.

## 16. Demo video, architecture PDF, presentation links
- Architecture PDF: `docs/architecture.pdf`
- Demo video: TBD (to be recorded)
- Presentation: TBD (`docs/presentation.pdf`)

## 17. Licences
- Code: Apache-2.0 (see LICENSE)
- CAD, docs, figures: CC BY 4.0 (see LICENSE-CAD-DOCS)

## 18. Citation
See CITATION.cff
