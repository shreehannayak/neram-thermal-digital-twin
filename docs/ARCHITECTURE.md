# NERAM architecture (owner: Sai; Box 9 — rendered as docs/architecture.pdf)

Source of the PDF: `docs/architecture_src/architecture.html`, rendered with headless Chromium
(`docs/architecture_src/README.md`). Unity-layer detail: `docs/unity/ARCHITECTURE.md`.

## 1. Roles in one sentence each
* **Digital Twin = estimation and forecasting** of one patient's temperature-signal state
  (`src/twin_replay_export.py` running the unchanged canonical `src/thermal_robust_core.py`).
* **Supervisory controller = simulated, clinician-supervised prototype** (Suchitha, MATLAB/Simulink/Stateflow).
  It decides the four heating commands from the twin outputs, module telemetry and clinician buttons.
* **Hardware = specification and simulated telemetry only** (Shreehan). No hardware is built; every hardware
  value in the demo is SIMULATED.
* **CAD = physical design** of the four modules and the bedside controller (Neharika). Unity imports the FBX.
* **Unity = visualisation and integration only.** It reads one replay file. No model, no controller and no physics
  run in C#.

## 2. Data flow (open loop, 20 Oct)
```
 patient temperature signal, 1-min medians          SIMULATED observations (synthetic scenarios)
 (VitalDB Solar8000/BT, site NOT established;  ──┐  integration/synthetic/observations/obs_SYN_0x.csv
  development cases only, local only)            │
                                                 ▼
        ┌──────────────────────────── DIGITAL TWIN (Sai) ───────────────────────────┐
        │ src/twin_replay_export.py → imports src/thermal_robust_core.py (hash-checked)│
        │ GPB2 robust state-space filter: T_est ± SD, forecasts +20/30/60 (80/95 %),   │
        │ P_below_hypo_h (same mixture), P_level_shift, P_outlier, Twin_Valid          │
        └──────────────┬───────────────────────────────────────────────────────────────┘
          twin CSV, 1 row/min, interface spec §4A — integration/twin_outputs/twin_<id>.csv
          checked by integration/validate_twin_output.py
                       ▼
 ┌─────── SUPERVISORY CONTROLLER (Suchitha, simulated) ──────┐     ┌── HARDWARE (Shreehan, simulated) ──┐
 │ Stateflow: 7 states, triggers on forecast probability,     │◄───►│ Module_Temp_i_A/B, Module_Connected│
 │ doses from feedback (never from forecasts), latched faults │     │ Heater_Current, HW_Cutoff, faults  │
 └──────────────┬─────────────────────────────────────────────┘     └────────────────────────────────────┘
          controller log, 1 Hz, plan §1S — integration/controller_logs/ctrl_<id>.csv
          (+ T_plant / dT_heat only when the ASSUMED warming term of src/assumed_warming.py is used)
                       ▼
   integration/build_replay.py — twin values held between minute updates; holdout guard; strict §1S columns;
   validates with integration/validate_replay.py BEFORE writing; behaviour check tools/check_replay_semantics.py
                       ▼
   replay JSONL (schema 1.0, unity/schema/replay_schema.json): header + 1-Hz frames {meta, obs, twin, ctrl, hw, plant, src}
                       ▼
   Unity v4 viewer (unity_editor/, Assets/Scenes/NERAM_OR_Replay.unity) — REPLAY ONLY
```

## 3. Shared contracts (single sources of truth, plan 0.3)
| File | Content | Version |
|---|---|---|
| `config/interface_spec.csv` | every signal: source, destination, unit, type, rate, range/enum, missing, fault, owner, status | spec 0.1 |
| `config/enums.json` | ControllerState, TwinValid, TriggerReason, AlertCode, SourceTag, PlantMode (FaultCode lives in Shreehan's `hardware/interfaces/fault_codes.csv`) | spec 0.1 |
| `config/params.json` | every parameter with value / placeholder / unit / status / source / owner | params 0.2 |
| `unity/schema/replay_fields.json` → `replay_schema.json` | replay field registry and JSON Schema (generated) | schema 1.0 |

Rates: twin 1/60 Hz, held between updates. Controller and hardware 1 Hz. Replay frames 1 Hz logical time.
Missing numbers are NaN in MATLAB and CSV, and null in JSONL; never 0 or −999.

## 4. Assumed warming (plan §4E) — ASSUMED, SIMULATED prototype response
d_t = Σ_i w_i·Heat_i,t/100;  h_t = h_{t−1} + (Δt/τ_heat)(d_t − h_{t−1});  ΔT_t = ΔT_{t−1} + k_heat·(Δt/60)·h_t;
T_plant = T_pass + ΔT_heat. Here Δt is in minutes and k_heat in °C/h at 100 % on all channels.

* k_heat, τ_heat and w_ch are ASSUMED (`config/params.json` placeholders 2.0 °C/h, 10 min, equal weights).
* Every output that uses them is run at ×0.5 / ×1 / ×2.
* VitalDB contains no warming data, so nothing here is estimated.
* Summit (CP6, not implemented): the twin's level equation receives the same input, and its forecasts are then
  labelled "forecast under ASSUMED warming".

## 5. Source tags (plan §4P)
| Group | Tag |
|---|---|
| obs | REAL_DEV (development case, local only) or SIMULATED (synthetic) |
| twin | MODEL: the canonical filter. Note: v4's SYN_SCN_* / SYN_ENG_* replays use a stand-in filter and are tagged SIMULATED |
| ctrl | SIMULATED |
| hw | SIMULATED |
| plant | ASSUMED |

## 6. What is not built yet (shown as TBD in the PDF)
* Real-data twin parameters: the development fit failed (docs/RESULTS.md).
* Development-case replay SCN_A (DEV_<pseudo>).
* Hardware fault-code display text (Shreehan).
* CAD FBX (Neharika).
* A controller log with heating (Suchitha).
* Summit closed loop.
