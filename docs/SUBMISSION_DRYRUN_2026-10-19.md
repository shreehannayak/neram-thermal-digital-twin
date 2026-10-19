# Team cross-check against the implementation plan (Sai, 19 Oct 2026)

Checked against plan §9.7 (final definition of done) and each person's checklist (1Y, 2AB, 3AG, Sai §4) on the
repository as it will be pushed on 19 Oct. Status: DONE = in the repo and checked; DONE (scope) = done to the scope
the team agreed; BLOCKED = cannot be done without data we may not publish; LEFT = still to do, owner named.

## What is left before submission
1. **GitHub comments (all four members).**
   - Issue #1 "Hardware rows for params.json" and issue #2 "Hardware assumptions: please confirm" have no comments
     yet: Shreehan confirms the hardware rows and assumptions; Suchitha confirms the controller uses them.
   - Each member confirms their line in README §2 in a GitHub comment (checklist item 1) and adds their family name
     to `CITATION.cff`.
2. **Demo video (Sai).** Record, upload unlisted, put the link in README §16. The plan asks for 15–20 min
   (checklist item 7); the script prepared today is 7 min, so either extend it or note the shorter length.
3. **Final tick of `docs/SUBMISSION_CHECKLIST.md` from a logged-out browser (Shreehan).** All automated checks below
   pass; the boxes are ticked by a person.

Everything else in the plan is done, done to the agreed scope, or blocked for a data-use reason (below).

## Suchitha — controller (checklist 1Y)
| Item | Status | Evidence |
|---|---|---|
| Runs from a clean clone | DONE (scope) | Python fallback `controller/neram_ctrl` (MATLAB/Simulink were not available); `python controller/scripts/run_all_tests.py` |
| TC01–TC17, TC19 PASS; TC18 reported | DONE except TC19 | TC01–TC18 PASS/REPORTED; **TC19 BLOCKED** (needs a development-case twin file) |
| Interface check zero mismatches | DONE | `config/interface_spec.csv`, `tests/test_interface.py` PASS |
| Parameters from params.json, placeholders listed | DONE | `controller/results/run_console.txt` |
| Seven controller logs | DONE | `integration/controller_logs/` (TC04, TC05, TC07, TC08, TC13, SYN_02 + five CTRL_SCN logs) |
| Spec, T01–T07, P01–P09, S01–S07, video, slides | DONE | `controller/docs/` |
| SIMULATED / ASSUMED labels | DONE | every replay, plot and log header |
| Shreehan confirms hardware assumptions in a GitHub comment | **LEFT** | issue #2 |
| Controller output in the simulation | DONE (19 Oct) | SCN_B–SCN_F replays from her test runs; SCN_C is the start-up scenario |

## Neharika — CAD (checklist 2AB)
| Item | Status | Evidence |
|---|---|---|
| Four modules, controller, assembly | DONE (scope) | `cad/exports/`, placed in the viewer |
| Sensor pockets, heater insert, layers | DONE | exploded view in the viewer, every layer named on screen |
| Renders | DONE | `cad/renders/` R01–R08 |
| FBX set imported and checked in Unity | DONE | `cad/IMPORT_CHECK_SAI_2026-10-18.md` |
| STEP/native files, 2D drawings, mechanical BOM | Out of scope | team decision 18 Oct: 3D models only |

## Shreehan — hardware, README, audit (checklist 3AG)
| Item | Status | Evidence |
|---|---|---|
| Block, safety-layer, interface diagrams (source + image) | DONE | `hardware/diagrams/` (.drawio, .png, .pdf) |
| Sensor, MCU, heater comparisons, PROVISIONAL choices | DONE | `hardware/comparisons/` |
| One-channel schematic | DONE | `hardware/schematics/channel_driver.kicad_sch` (KiCad 8, added 19 Oct; generated, **not yet opened in KiCad by Shreehan**) + PDF/PNG |
| Power budget | DONE with TBDs | `hardware/power/power_budget.csv/.xlsx`; heater power per channel and case durations stay TBD (never guessed) |
| fault_codes, comm_protocol, controller_hw_interface, cad_envelope | DONE | `hardware/interfaces/` |
| Electrical BOM, feasibility non-claims | DONE with TBDs | `hardware/bom/electrical_bom.csv` (some prices TBD), `hardware/docs/feasibility.md` |
| Threshold ordering; t_surface_limit_degC | DONE | ordering FROZEN; surface limit TBD with IEC 80601-2-35 named |
| README, licences, CITATION.cff, .gitignore, .gitattributes | DONE | family names still to add (all) |
| Section 8 audit, logged-out check | **LEFT** | automated part passes (below) |

## Sai — twin, validation, integration, Unity
| Item | Status | Evidence |
|---|---|---|
| Development decision `dev_robust_03` | BLOCKED (recorded) | fit not completed; no development result claimed |
| Twin export, replay builder, validators, tests | DONE | `src/twin_replay_export.py`, `integration/build_replay.py`, validators; `tools/run_all_tests.py` OVERALL PASS |
| Four Unity scenarios with labels | DONE for SCN_B/C/D; SCN_A BLOCKED | SCN_A shows AWAITING DATA by design (needs a development-case export and VitalDB data-use clearance); SYN_SCN_A0 is its layout stand-in |
| Architecture PDF, model/data cards, safety doc, audit trail | DONE | `docs/` |
| Final holdout preregistered, not run | DONE | `docs/PREREGISTRATION_final.md`; no holdout run |
| Viewer: detailed surgeon and patient, instruments, lighting, explode labels, surgeon walk/views | DONE (19 Oct) | `docs/AUDIT_TRAIL.md` §17 |
| Demo video | **LEFT** | see above |

## Automated checks run on 19 Oct
- `tools/run_all_tests.py`: OVERALL PASS. Unity EditMode: 86 pass, 0 fail, 1 skip. Project validation: PASSED.
- Windows player rebuilt (190.4 MB) and opened: SCN_C loads, no placeholder watermark on SCN_* replays.
- Text search: "core temperature", "clinically validated", "prevents hypothermia", "medical-grade", "certified" occur
  only in negations and in the banned-word tests.
- Forbidden data: no VitalDB cache, `.csv.gz`, development inputs, holdout files or Unity `Library/` tracked. Largest
  non-LFS file: `scene_extras_mesh.bytes` 34 MB (below GitHub's 50 MB warning).
- Repository is public (GitHub API).
