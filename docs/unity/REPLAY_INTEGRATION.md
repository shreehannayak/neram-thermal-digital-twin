# Real replay integration (SCN_A–SCN_D)

Unity only displays what `build_replay.py` produces. Steps per scenario:

## 1. Inputs
| File | Producer | Columns |
|---|---|---|
| `integration/twin_outputs/<run>.csv` | Sai | plan §4A: `T_twin_s, T_obs, obs_missing, T_est, T_est_sd, Twin_Valid, P_level_shift, P_outlier, T_pred_{20,30,60}, L80_*, U80_*, L95_*, U95_*, P_below_hypo_*` (one row per minute) |
| `integration/controller_logs/<run>.csv` | Suchitha (Simulink/Stateflow) | plan §1S: `t_s, Controller_State, Degraded_Substate, Heat_1..4, Demand_Global, Trigger_Reason, Alert, Safety_Shutdown, Fault_Latched, fault_code, Channel_Fault_1..4, Clinician_Mode` (+ optional `Data_Stale_Twin, Data_Stale_HW, Clinician_Start/Stop/Reset`), HW telemetry `Module_Temp_i_A, Module_Temp_i_B, Module_Connected_i, Heater_Current_i, HW_Cutoff_i`, plant `T_plant, dT_heat, plant_mode` (one row per controller step) |
| `hardware/interfaces/fault_codes.csv` | Shreehan | `code,name,scope,detected_by,description,display_text` |
| `scenario_<X>.json` | Sai | `title, purpose, data_source, loop_description, limitations[]` |
| `params_used_<X>.json` | Sai/Suchitha | parameter snapshot `{name: {value|placeholder, unit, status, owner, source}}` |

Use `null` (empty CSV cell) for missing values — **never 0**.

## 2. Build
```bash
# SCN_A — usual-care replay of a DEVELOPMENT case (real observations + NERAM twin + open-loop controller log)
python integration/build_replay.py --scenario-id SCN_A \
  --twin integration/twin_outputs/twin_DEV_<case>.csv --ctrl integration/controller_logs/ctrl_TC19_<case>.csv \
  --cohort DEVELOPMENT --case-id <case> \
  --holdout-ids /content/final_holdout_freeze/final_holdout_case_ids.csv \
  --dev-ids /content/final_holdout_freeze/development_case_ids.csv \
  --obs-source REAL_DEV --twin-source MODEL \
  --scenario-info scenario_A.json --params-used params_used_A.json \
  --out integration/replays/SCN_A.jsonl.gz

# SCN_B/C/D — synthetic trajectories through the twin + Simulink logs (TC07 over-temperature, TC13 twin degraded)
python integration/build_replay.py --scenario-id SCN_C --twin <twin.csv> --ctrl <TC07.csv> --cohort SYNTHETIC \
  --obs-source SIMULATED --twin-source MODEL --scenario-info scenario_C.json --params-used params_used_C.json \
  --out integration/replays/SCN_C.jsonl.gz
```
* The holdout file is **read only to refuse** holdout ids; nothing from it is copied. `final_holdout_freeze/` and `code4_outputs/` are never modified.
* The output is validated before it is written; an invalid replay is never produced.
* Choose the development case for SCN_A from `development_case_ids.csv` only.

## 3. Check and sync
```bash
python integration/validate_replay.py integration/replays/SCN_A.jsonl.gz      # VALID / INVALID with codes
python tools/sync_unity_streaming_assets.py                                     # validates again, copies to StreamingAssets
```
In Unity: *NERAM → 2. Sync* (same thing) → Scenarios drawer → SCN_A now "available" instead of "awaiting data". Remove the `SYN_SCN_*` placeholders from the demo playlist once the real ones exist (keep them in tests).

## 4. Field mapping notes
* `Twin_Valid != VALID` ⇒ forecast cells must be empty (validator E040).
* `Safety_Shutdown` must equal `Controller_State == SAFETY_SHUTDOWN` (E031) and all `Heat_i = 0` then (E030).
* Channel fault codes live in `100·i + 1 … 100·i + 99` for channel i (E032).
* `plant_mode = OPEN_LOOP` ⇒ `T_plant`, `dT_heat` empty (E061): an open-loop replay can show no warming effect.
* Source tags (`src.*`) are set by `build_replay.py` from the CLI flags: obs REAL_DEV|SIMULATED, twin MODEL|SIMULATED, ctrl/hw SIMULATED, plant ASSUMED.
