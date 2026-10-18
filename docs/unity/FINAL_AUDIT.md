# Final audit — Unity visualization layer

Statuses: **PASS** = built and verified here (tests / compile / static checks) · **BUILT – needs Unity run** = code complete, verified only off-Unity (no Unity Editor was available to this build) · **PLACEHOLDER** = works with stand-in content until a team deliverable lands · **TBD** = value or decision not established; nothing invented · **NOT DONE**.

Verification available in this build: .NET 8 build of `Neram.Core` (warnings as errors) + 65 NUnit tests; runtime/editor scripts compile against Unity API stubs; Python validator 62/62 fixtures with identical C# verdicts; UI contract + wording guard; deterministic regeneration of schema and synthetic replays; StreamingAssets in sync.

## Data and science rules
| Item | Status | Evidence |
|---|---|---|
| Signal named "patient temperature signal", never "core temperature" | PASS | wording guard (`tests/test_unity_ui_contract.py`), replay header test |
| Every warming effect labelled SIMULATED / ASSUMED | PASS | plant tag must be ASSUMED (E050); open loop forbids warming (E061); forecast label rule tests |
| Controller described as SIMULATED + CLINICIAN-SUPERVISED PROTOTYPE; no autonomy/prevention/validation/certification claims | PASS | wording guard; banner/inspector text |
| No invented clinical/hardware constants | PASS | Unity holds none; thresholds only from params.json (status shown) or header `params_used` |
| Final holdout can never appear | PASS | cohort guard E052/E053/E051/E054; build_replay refuses holdout ids; sync re-validates; smoke test asserts cohorts |
| Missing ≠ 0, no interpolation | PASS | NaN storage, "—" formatting, missing strip; tests |
| No controller logic / no state transitions in Unity | PASS | code review: display rules read replayed fields only (ARCHITECTURE.md) |
| `t_target_degC` | TBD | no value in params.json; synthetic headers use 36.5 marked SYNTHETIC DEMO placeholder |
| `t_hypo_degC` applicability to this signal | TBD | placeholder 36.0 shown with status TBD |
| `T_obs` validation range 25–43 °C equals Code 4 BT filter | TBD | Sai to confirm (PHASE0 #11) |
| Enum integers | PROVISIONAL | resolved by name; Suchitha to freeze |

## Replay engine
| Item | Status | Evidence |
|---|---|---|
| JSONL header + frames, groups meta/obs/twin/ctrl/hw/plant/src | PASS | schema 1.0, 78 fields, generated code |
| Strict schema validation with error screen | PASS (engine) / BUILT – needs Unity run (screen) | 62 fixtures; DataErrorScreen |
| Python ↔ C# validator parity | PASS | identical verdicts on all fixtures |
| Play/pause/step/×1/×10/×60/scrub/restart | PASS (model) / BUILT – needs Unity run (UI) | ClockAndEventTests |
| Jump to event / scenario start | PASS (model) / BUILT – needs Unity run | EventIndex tests |
| All views synchronized | BUILT – needs Unity run | single clock + coalesced render (NeramApp) |
| Large files / performance | PASS (parse) / BUILT – needs Unity run (frame rate) | worker-thread parse, columnar table, ≤15 Hz text |

## Views
| Item | Status |
|---|---|
| 3D scene: mannequin, table, 4 modules CH1 LH / CH2 RH / CH3 LF / CH4 RF, bedside controller (BC_*), cables | BUILT – needs Unity run · geometry PLACEHOLDER |
| No body heat map; single thermal indicator | BUILT – needs Unity run |
| Thermal panel: 60-min rolling, T_obs vs T_est ± SD, missing distinct, hover/click, markers | BUILT – needs Unity run (compiled vs stubs) |
| Forecast fan + cards (+20/+30/+60, 80/95 %, P_below_hypo), hidden unless VALID, loop-specific labels | PASS (rules, tests) / BUILT – needs Unity run (drawing) |
| "Possible level shift" / "Possible artefact" flags | BUILT – needs Unity run · display cut-offs 0.5 are display-only settings |
| Controller banner + timeline + START/STOP/RESET marks | BUILT – needs Unity run · presses inferred until Clinician_* fields are logged |
| SAFETY_SHUTDOWN banner latched, heaters dark, channel outline + code, TWIN_DEGRADED message | PASS (rules) / BUILT – needs Unity run |
| Live telemetry panel | BUILT – needs Unity run |
| Parameters inspector with statuses | BUILT – needs Unity run |
| Source badges | BUILT – needs Unity run |
| Disclaimer footer (always visible) | BUILT – needs Unity run |
| Scenario selector (SCN_A–D + engineering) | BUILT – needs Unity run · SCN_A–D PLACEHOLDER (SYN_* until team data) |
| Before/after comparison labelled SIMULATED/ASSUMED | BUILT – needs Unity run (conditional on plant group) |
| Fault-code texts | PLACEHOLDER (plan-derived table until Shreehan's CSV) |

## Project / tooling
| Item | Status |
|---|---|
| Unity 6 LTS + URP + Newtonsoft packages, asmdefs | BUILT – needs Unity run (package versions may be bumped by the Editor) |
| Editor bootstrap (pipeline, materials, PanelSettings, scene, build settings) | BUILT – needs Unity run |
| Validation menu (pipeline, input backend, config, replays, UI, materials, scene names) | BUILT – needs Unity run |
| CAD integration tool + import postprocessor | BUILT – needs Unity run · awaiting FBX |
| Automated tests (Unity Test Runner + .NET CI) | PASS (65 .NET) / needs Unity run in Test Runner |
| Screenshots / video of the running viewer | NOT DONE (no Unity Editor here) |
| Real SCN_A–D replays | NOT DONE — team data (REPLAY_INTEGRATION.md) |

## Known risks to check on first open in Unity
1. URP asset creation by script (`UniversalRenderPipelineAsset.Create`) — if materials render pink, assign a URP asset manually (README troubleshooting).
2. UI Toolkit runtime keyboard events need an input backend (validation checks it).
3. `ScreenCapture` output includes the UI overlay on desktop players; verify once.
4. Transparent URP Lit materials (shell/insulation) are set by keywords; if they render opaque, set *Surface Type = Transparent* on `MAT_Shell`/`MAT_Insulation`.
5. Package versions in `manifest.json` (URP 17.0.3, test-framework 1.4.5) are resolved to the Editor's bundled versions; accept the Editor's upgrade prompt.
