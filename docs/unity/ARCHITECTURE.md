# Unity layer — architecture

```
 Sai: twin CSV (§4A)        Suchita: controller log CSV (§1S, 1 Hz)      Shreehan: fault_codes.csv, HW columns
          \                         |                                              |
           +------ integration/build_replay.py (holdout guard, validates before writing) ---+
                                    |
                     integration/replays/<ID>.jsonl.gz   (header + 1 frame per controller step)
                                    |
             tools/sync_unity_streaming_assets.py / NERAM > Sync (re-validates; rejects anything invalid)
                                    |
                      unity/Assets/StreamingAssets/{config,replays,cad}
                                    |
  ┌──────────────────────────── Unity process ───────────────────────────────────────────────┐
  │ ReplayLoader ── worker thread ──> ReplayValidator (StrictJson → schema/rules → ReplayTable) │
  │      │ valid only                                                                          │
  │      v                                                                                     │
  │ ReplaySession (header, columnar table, EventIndex, enums by NAME, params + header snapshot) │
  │      │                                                                                     │
  │ ReplayClock (single clock: play/pause/step/×1 ×10 ×60/seek) ── FrameChanged(frame, jump) ──┐ │
  │                                                                                          v │
  │ NeramApp (composition root; render coalescing in LateUpdate; text panels ≤ 15 Hz)          │
  │   ├─ fast views : ThermalPanel(+ThermalChartElement) ForecastFan ControllerStatePanel      │
  │   │               SafetyOverlay TransportBar(+TimelineStripElement) WorldLabels            │
  │   │               NeramAssemblyBinder → ModuleView ×4, ControllerView3D, connectors        │
  │   └─ text views : TelemetryPanel EventLogPanel ModuleInspector Diagnostics Parameters      │
  │                   DisclaimerBanner                                                         │
  └────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Assemblies
| Assembly | Depends on | Content | Why |
|---|---|---|---|
| `Neram.Core` (`noEngineReferences`) | Newtonsoft.Json | Schema (`ReplayFields.g.cs` generated from `unity/schema/replay_fields.json`), `StrictJson` (RFC 8259 scanner — same acceptance as Python `json` with strict hooks), `ReplayValidator`, `ReplayTable` (columnar `double[]`, NaN = null), `EventIndex`, `ReplayClockModel`, `EnumRegistry`, `ParamsRegistry`, `FaultCodeTable`, `DisplayConfig`, display rules (`ViewModels.cs`), `ScenarioCatalog`, formatting | Testable without Unity (.NET 8 in CI); one implementation of every rule. |
| `Neram.Runtime` | Neram.Core | MonoBehaviours, UI Toolkit controllers, custom elements, 3D views | Presentation only. |
| `Neram.Editor` | Core, Runtime, URP | Setup, sync, validation, CAD tools | Reproducible project bootstrap. |
| `Neram.Tests.EditMode` | Core, NUnit | 65 tests + 62 fixtures | Same sources run in Unity Test Runner and in .NET CI. |

## Data contract
* **Single schema source**: `unity/schema/replay_fields.json` (78 fields, groups `meta obs twin ctrl hw plant src`) → `tools/gen_replay_schema.py` → `replay_schema.json` (JSON Schema for other tools) + `ReplayFields.g.cs`. `--check` fails CI if stale.
* **Validation parity**: `integration/validate_replay.py` (stdlib) and `ReplayValidator` implement `VALIDATION_RULES.md`; 62 fixtures (valid + every error code + 8 lenient-JSON cases) give identical verdicts in both.
* **Enums by name**: replay integers are resolved through `config/enums.json`; names are frozen, integers provisional.
* **Parameters**: `config/params.json` (status FROZEN/PROVISIONAL/TBD/ASSUMED; TBD has no value) overlaid by the replay header's `params_used` snapshot, so the viewer shows exactly what generated the file.

## Synchronization
One `ReplayClockModel` owns time. Every view renders the same frame index. Seeks, steps, event jumps and pauses set `jump = true` → all panels refresh immediately and the 3D scene snaps (no easing). During playback heater glow eases over 0.25 s (visual only), and text panels refresh at ≤ 15 Hz; the frame they show is always the clock's frame at refresh time.

## Display rules (no controller logic)
| Rule | Reads | Never does |
|---|---|---|
| Forecast visibility | `Twin_Valid`, `Controller_State`, `Degraded_Substate`, `plant_mode`, `AnyHeat` | decide a transition |
| Forecast label | `plant_mode` + whether any channel heats | infer benefit |
| Channel display status | `Safety_Shutdown`, `HW_Cutoff_i`, `Module_Connected_i`, `Channel_Fault_i`, `Heat_i` | apply a limit |
| Safety banner | `Safety_Shutdown`, `Fault_Latched`, `fault_code`, `Alert` (RESET_BLOCKED), shutdown/release times from the log | re-latch / release anything |
| Thermal indicator band | `T_est` vs `t_hypo`/`t_target` *as provided with status* | classify a patient |

## Performance
* Streaming parse (gzip supported) on a worker thread; cancelable; progress overlay.
* Columnar storage: 78 × 8 bytes per frame (≈ 2.2 MB for a 1 h replay at 1 Hz).
* Chart draws ≤ 1 point per pixel column (stride), Painter2D; labels pooled.
* Render coalescing: at ×60 the clock may advance many frames per Unity frame; views render once per Unity frame.
* `UiUtil.SetText` skips unchanged text (no layout churn).

## Failure behaviour
| Failure | Behaviour |
|---|---|
| Invalid replay | Data Error screen with the codes; nothing from that file is displayed. |
| Missing/invalid config | Built-in plan v0.1 defaults + visible warning chips and Diagnostics entries. |
| Missing fault table | PLACEHOLDER table from the plan + chip. |
| Missing UXML element | Explicit setup error naming the element. |
| CAD part missing | Placeholder used / feature disabled for that part; Diagnostics + validation report it. |
