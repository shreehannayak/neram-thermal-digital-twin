# NERAM supervisory controller - specification (Python fallback)

**Status: SIMULATED / ASSUMED PROTOTYPE.** Clinician-supervised prototype logic only; no clinical efficacy, safety or validation claim.
Code version of the v2 run `sha256:797ce93592f3`; parameters `standalone-0.1`. The v2 source was lost; the code in `neram_ctrl/` was rebuilt from this specification on 18 Oct 2026 and reproduces the v2 logs byte for byte (`REBUILD_2026-10-18_SAI.md`).

## 1. Scope and what this document covers
Suchita's supervisory controller (plan pp. 4-23): TwinAdapter -> FaultMonitor -> Supervisor -> DemandLaw -> ChannelLimiter, run every `ts_ctrl_s` = 1 s.
Implemented in Python because MATLAB/Simulink/Stateflow were unavailable. The Supervisor is a Python state machine standing in for the Stateflow chart
(`docs/figures/stateflow_chart.png` is a Python-drawn diagram, not a Stateflow screenshot). Block diagram: `docs/figures/controller_block_diagram.png`; test bench: `docs/figures/testbench_overview.png`.

## 2. Architecture
1. **TwinAdapter** - consumes the twin outputs held between 1-min updates (`T_twin_s`, `T_est`, `P_below_hypo_20/30/60`, `Twin_Valid`). Derives `Data_Stale_Twin` (age of `T_twin_s` > `data_stale_twin_s`, or NaN), `twin_ok`, `twin_bad`, `risk_pred` (P20/P30 with hysteresis `p_trigger`/`p_release` and `n_confirm_updates`), `risk60` (alert-only), `below_hypo`, `at_target`, `target_lost`, `stop_inhibit`. A NaN or implausible `T_est` (outside 25-43 degC) or `Twin_Valid` DEGRADED/NO_DATA makes the twin *not ok*; a NaN probability never triggers or releases a latch.
2. **FaultMonitor** - persistent latches per channel and system-wide (section 5). A latch clears only on a rising `Clinician_Reset` **and** when the condition has cleared. Produces `Channel_Fault_1..4`, `system_fault`, `fault_code`, `Fault_Latched`, `Data_Stale_HW`.
3. **Supervisor** - states 0-6 (`NORMAL`, `PREDICTIVE_WARMING`, `ACTIVE_WARMING`, `TARGET_MAINTENANCE`, `CLINICIAN_WARMING`, `TWIN_DEGRADED` with `Degraded_Substate` MONITOR/CLINICIAN_FIXED, `SAFETY_SHUTDOWN`) and transitions T1-T14 (section 4). `Trigger_Reason` is held until the next transition; `Alert` is raised per rule.
4. **DemandLaw** - PI on `e = t_target_degC - T_est` (feedback estimate only; the no-intervention forecast is never a DemandLaw input), clamping anti-windup, integrator reset on every state entry. Mode caps: PREDICTIVE `d_pred_max_pct`, ACTIVE `d_active_max_pct`, MAINTENANCE `d_maint_max_pct`, CLINICIAN_FIXED fixed `d_fallback_pct` (not PI). NaN `T_est` -> demand 0.
5. **ChannelLimiter** - `Heat_i = enable_i * min(D, p_max_ch_pct_i * derate_i)`, clamped to `[0, p_max_ch_pct_i]`; `derate_i` falls linearly from 1 at `t_mod_derate_degC` to 0 at `t_mod_trip_degC` using `T_mod_i = max(sensor A, sensor B)`; NaN -> 0. `enable_i = 0` for a faulted, disconnected or hardware-cut-off channel and for every channel in SAFETY_SHUTDOWN. If all four channels are faulted, `D = 0`.

Channels: CH1 left hand, CH2 right hand, CH3 left foot, CH4 right foot.

## 3. Enumerations
`Controller_State` 0-6 as above; `Degraded_Substate` 0 none / 1 MONITOR / 2 CLINICIAN_FIXED; `Trigger_Reason` 0-11 (NONE, FORECAST_P20, FORECAST_P30, TEST_BELOW_HYPO, CLINICIAN_START, TARGET_REACHED, TARGET_LOST, CLINICIAN_STOP, SAFETY_FAULT, TWIN_DEGRADED, TWIN_RECOVERED, CLINICIAN_RESET); `Alert` 0-8 (NONE, FORECAST_RISK_20_30, FORECAST_RISK_60_INFO, TWIN_DEGRADED, CHANNEL_FAULT, SAFETY_SHUTDOWN, DATA_STALE, CLINICIAN_STOP_ACK, RESET_BLOCKED); `Twin_Valid` 0-3. Fault codes: channel `100*ch + k` (k = 1..11), system 1-8 (plan section 3W list; `fault_codes.csv` itself was not supplied).

## 4. States and transitions
Full table: `results/tables/transition_table.csv`.

| id | from | to | condition | dwell | priority | reason |
|---|---|---|---|---|---|---|
| T1 | OPERATING (any) | SAFETY_SHUTDOWN | system_fault | none | 1 | SAFETY_FAULT |
| T2 | SAFETY_SHUTDOWN | OPERATING.NORMAL | rising Clinician_Reset AND system_fault cleared AND all T_mod_i < t_mod_reset_degC (NaN T_mod blocks); otherwise stay and raise RESET_BLOCKED | none | 2 | CLINICIAN_RESET |
| T3 | PREDICTIVE_WARMING / ACTIVE_WARMING / TARGET_MAINTENANCE / CLINICIAN_WARMING / TWIN_DEGRADED.CLINICIAN_FIXED | NORMAL | rising Clinician_Stop; starts stop_inhibit (t_stop_inhibit_s); clears Clinician_Mode | none | 3 | CLINICIAN_STOP |
| T4 | NORMAL / PREDICTIVE_WARMING / ACTIVE_WARMING / TARGET_MAINTENANCE / CLINICIAN_WARMING | TWIN_DEGRADED (CLINICIAN_FIXED if Clinician_Mode or Clinician_Start in the same sample, else MONITOR) | twin_bad | none | 4 | TWIN_DEGRADED |
| T5 | TWIN_DEGRADED.MONITOR | NORMAL | twin_ok held | t_recover_s | 5 | TWIN_RECOVERED |
| T6 | TWIN_DEGRADED.CLINICIAN_FIXED | CLINICIAN_WARMING | twin_ok held | t_recover_s | 6 | TWIN_RECOVERED |
| T7 | TWIN_DEGRADED.MONITOR | TWIN_DEGRADED.CLINICIAN_FIXED | rising Clinician_Start | none | 7 | CLINICIAN_START |
| T8 | NORMAL / PREDICTIVE_WARMING | CLINICIAN_WARMING | rising Clinician_Start AND twin_ok | none | 8 | CLINICIAN_START |
| T9 | NORMAL (twin INITIALISING) | TWIN_DEGRADED.CLINICIAN_FIXED | rising Clinician_Start AND NOT twin_ok | none | 9 | CLINICIAN_START |
| T10 | NORMAL | ACTIVE_WARMING | twin_ok AND below_hypo AND NOT stop_inhibit, held | t_dwell_min_s | 10 | TEST_BELOW_HYPO |
| T11 | NORMAL | PREDICTIVE_WARMING | risk_pred AND NOT below_hypo AND NOT stop_inhibit, held (risk_pred already contains twin_ok) | t_dwell_min_s | 11 | FORECAST_P20 or FORECAST_P30 (whichever crossed first) |
| T12 | PREDICTIVE_WARMING | ACTIVE_WARMING | below_hypo held | t_dwell_min_s | 12 | TEST_BELOW_HYPO |
| T13 | PREDICTIVE_WARMING / ACTIVE_WARMING / CLINICIAN_WARMING | TARGET_MAINTENANCE | at_target held | t_dwell_min_s | 13 | TARGET_REACHED |
| T14 | TARGET_MAINTENANCE | ACTIVE_WARMING | target_lost held | t_dwell_min_s | 14 | TARGET_LOST |
| R1 | ACTIVE_WARMING / TARGET_MAINTENANCE | (no state change) | Clinician_Start only sets Clinician_Mode | none | rule | - |
| R2 | PREDICTIVE_WARMING | (no exit on forecast) | exits only via T1, T3, T4, T8, T12, T13 | none | rule | - |
| R3 | TARGET_MAINTENANCE | (no automatic exit to NORMAL) | heating may fall to 0 inside it; clinician ends it with STOP | none | rule | - |

Priority: T1 (system fault) > T2 > T3 (Stop) > T4 (twin bad) > the rest. Dwell (`t_dwell_min_s`, `t_recover_s`) is counted in 1 s steps and is never applied to T1-T4. `Clinician_Stop` always wins on the sample where an automatic entry would complete and starts `stop_inhibit` (`t_stop_inhibit_s`), even from NORMAL.

## 5. Fault behaviour
Persistent latches; shutdown-class faults (over-temperature, hardware cut-off, over-current, stuck-on driver, hardware stale, `HW_Fault_Code` != 0) -> SAFETY_SHUTDOWN with all `Heat_i = 0` in the same step. Isolating faults (sensor NaN, sensor disagreement, module disconnected, open circuit) switch off only that channel and raise `CHANNEL_FAULT`. A stale or unreliable twin is *not* a shutdown: it goes to TWIN_DEGRADED and heating stops (MONITOR) or falls back to a fixed, module-limited demand (CLINICIAN_FIXED, only with clinician mode). `fault_code` priority: system codes before channel codes, shutdown-class before isolating, lower channel first.

| fault condition | fault code | channel action | system action | latched | reset / release condition |
|---|---|---|---|---|---|
| CH1 Module_Temp_1_A NaN (open/unreadable) | 101 | Channel 1 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid |
| CH1 Module_Temp_1_A short or out of sensor range | 102 | Channel 1 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid. NOT DETECTED: needs the module sensor range from Shreehan (not supplied); range hook is in FaultMonitor (module_temp_min/max_degC = null) |
| CH1 Module_Temp_1_B NaN (open/unreadable) | 103 | Channel 1 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid |
| CH1 Module_Temp_1_B short or out of sensor range | 104 | Channel 1 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid. NOT DETECTED: needs the module sensor range from Shreehan (not supplied) |
| CH1 \|A - B\| > dt_sensor_disagree_degC held t_dwell_min_s | 105 | Channel 1 off | Alert CHANNEL_FAULT | Yes | Reset + agreement |
| CH1 T_mod_1 >= t_mod_trip_degC (software over-temperature; max of the working sensors) | 106 | All off | SAFETY_SHUTDOWN | Yes | Reset + all T_mod < t_mod_reset_degC |
| CH1 HW_Cutoff_1 = 1 | 107 | All off | SAFETY_SHUTDOWN | Yes | Reset + cutoff cleared |
| CH1 Module_Connected_1 = 0 | 108 | Channel 1 off | Alert CHANNEL_FAULT | Yes | Reset + reconnected |
| CH1 Heat_1 > 0 and Heater_Current_1 < i_open_max_A held t_dwell_min_s (qualified: only when (Heat_1/100)*i_on_A >= i_open_max_A; see docs D1) or Heater_Current_1 = NaN... | 109 | Channel 1 off | Alert CHANNEL_FAULT | Yes | Reset (NaN sense must be readable again) |
| CH1 Heater_Current_1 > i_over_A | 110 | All off | SAFETY_SHUTDOWN | Yes | Reset + current back below i_over_A |
| CH1 Heat_1 = 0 and Heater_Current_1 > i_stuck_A for 2 steps (stuck-on) | 111 | All off (master cutoff) | SAFETY_SHUTDOWN | Yes | Reset + current back below i_stuck_A |
| CH2 Module_Temp_2_A NaN (open/unreadable) | 201 | Channel 2 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid |
| CH2 Module_Temp_2_A short or out of sensor range | 202 | Channel 2 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid. NOT DETECTED: needs the module sensor range from Shreehan (not supplied); range hook is in FaultMonitor (module_temp_min/max_degC = null) |
| CH2 Module_Temp_2_B NaN (open/unreadable) | 203 | Channel 2 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid |
| CH2 Module_Temp_2_B short or out of sensor range | 204 | Channel 2 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid. NOT DETECTED: needs the module sensor range from Shreehan (not supplied) |
| CH2 \|A - B\| > dt_sensor_disagree_degC held t_dwell_min_s | 205 | Channel 2 off | Alert CHANNEL_FAULT | Yes | Reset + agreement |
| CH2 T_mod_2 >= t_mod_trip_degC (software over-temperature; max of the working sensors) | 206 | All off | SAFETY_SHUTDOWN | Yes | Reset + all T_mod < t_mod_reset_degC |
| CH2 HW_Cutoff_2 = 1 | 207 | All off | SAFETY_SHUTDOWN | Yes | Reset + cutoff cleared |
| CH2 Module_Connected_2 = 0 | 208 | Channel 2 off | Alert CHANNEL_FAULT | Yes | Reset + reconnected |
| CH2 Heat_2 > 0 and Heater_Current_2 < i_open_max_A held t_dwell_min_s (qualified: only when (Heat_2/100)*i_on_A >= i_open_max_A; see docs D1) or Heater_Current_2 = NaN... | 209 | Channel 2 off | Alert CHANNEL_FAULT | Yes | Reset (NaN sense must be readable again) |
| CH2 Heater_Current_2 > i_over_A | 210 | All off | SAFETY_SHUTDOWN | Yes | Reset + current back below i_over_A |
| CH2 Heat_2 = 0 and Heater_Current_2 > i_stuck_A for 2 steps (stuck-on) | 211 | All off (master cutoff) | SAFETY_SHUTDOWN | Yes | Reset + current back below i_stuck_A |
| CH3 Module_Temp_3_A NaN (open/unreadable) | 301 | Channel 3 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid |
| CH3 Module_Temp_3_A short or out of sensor range | 302 | Channel 3 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid. NOT DETECTED: needs the module sensor range from Shreehan (not supplied); range hook is in FaultMonitor (module_temp_min/max_degC = null) |
| CH3 Module_Temp_3_B NaN (open/unreadable) | 303 | Channel 3 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid |
| CH3 Module_Temp_3_B short or out of sensor range | 304 | Channel 3 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid. NOT DETECTED: needs the module sensor range from Shreehan (not supplied) |
| CH3 \|A - B\| > dt_sensor_disagree_degC held t_dwell_min_s | 305 | Channel 3 off | Alert CHANNEL_FAULT | Yes | Reset + agreement |
| CH3 T_mod_3 >= t_mod_trip_degC (software over-temperature; max of the working sensors) | 306 | All off | SAFETY_SHUTDOWN | Yes | Reset + all T_mod < t_mod_reset_degC |
| CH3 HW_Cutoff_3 = 1 | 307 | All off | SAFETY_SHUTDOWN | Yes | Reset + cutoff cleared |
| CH3 Module_Connected_3 = 0 | 308 | Channel 3 off | Alert CHANNEL_FAULT | Yes | Reset + reconnected |
| CH3 Heat_3 > 0 and Heater_Current_3 < i_open_max_A held t_dwell_min_s (qualified: only when (Heat_3/100)*i_on_A >= i_open_max_A; see docs D1) or Heater_Current_3 = NaN... | 309 | Channel 3 off | Alert CHANNEL_FAULT | Yes | Reset (NaN sense must be readable again) |
| CH3 Heater_Current_3 > i_over_A | 310 | All off | SAFETY_SHUTDOWN | Yes | Reset + current back below i_over_A |
| CH3 Heat_3 = 0 and Heater_Current_3 > i_stuck_A for 2 steps (stuck-on) | 311 | All off (master cutoff) | SAFETY_SHUTDOWN | Yes | Reset + current back below i_stuck_A |
| CH4 Module_Temp_4_A NaN (open/unreadable) | 401 | Channel 4 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid |
| CH4 Module_Temp_4_A short or out of sensor range | 402 | Channel 4 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid. NOT DETECTED: needs the module sensor range from Shreehan (not supplied); range hook is in FaultMonitor (module_temp_min/max_degC = null) |
| CH4 Module_Temp_4_B NaN (open/unreadable) | 403 | Channel 4 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid |
| CH4 Module_Temp_4_B short or out of sensor range | 404 | Channel 4 off | Alert CHANNEL_FAULT | Yes | Reset + sensor valid. NOT DETECTED: needs the module sensor range from Shreehan (not supplied) |
| CH4 \|A - B\| > dt_sensor_disagree_degC held t_dwell_min_s | 405 | Channel 4 off | Alert CHANNEL_FAULT | Yes | Reset + agreement |
| CH4 T_mod_4 >= t_mod_trip_degC (software over-temperature; max of the working sensors) | 406 | All off | SAFETY_SHUTDOWN | Yes | Reset + all T_mod < t_mod_reset_degC |
| CH4 HW_Cutoff_4 = 1 | 407 | All off | SAFETY_SHUTDOWN | Yes | Reset + cutoff cleared |
| CH4 Module_Connected_4 = 0 | 408 | Channel 4 off | Alert CHANNEL_FAULT | Yes | Reset + reconnected |
| CH4 Heat_4 > 0 and Heater_Current_4 < i_open_max_A held t_dwell_min_s (qualified: only when (Heat_4/100)*i_on_A >= i_open_max_A; see docs D1) or Heater_Current_4 = NaN... | 409 | Channel 4 off | Alert CHANNEL_FAULT | Yes | Reset (NaN sense must be readable again) |
| CH4 Heater_Current_4 > i_over_A | 410 | All off | SAFETY_SHUTDOWN | Yes | Reset + current back below i_over_A |
| CH4 Heat_4 = 0 and Heater_Current_4 > i_stuck_A for 2 steps (stuck-on) | 411 | All off (master cutoff) | SAFETY_SHUTDOWN | Yes | Reset + current back below i_stuck_A |
| Data_Stale_HW (HW_Heartbeat_s older than data_stale_hw_s, or NaN) | 8 | All off | SAFETY_SHUTDOWN | Yes | Reset + heartbeat back |
| HW_Fault_Code = 1 (HOST_HEARTBEAT_LOST) (any non-zero HW_Fault_Code incl. 9-19 is treated the same) | 1 | All off | SAFETY_SHUTDOWN | Yes | Reset + code cleared |
| HW_Fault_Code = 2 (MCU_WATCHDOG_RESET) (any non-zero HW_Fault_Code incl. 9-19 is treated the same) | 2 | All off | SAFETY_SHUTDOWN | Yes | Reset + code cleared |
| HW_Fault_Code = 3 (PSU_UNDERVOLTAGE) (any non-zero HW_Fault_Code incl. 9-19 is treated the same) | 3 | All off | SAFETY_SHUTDOWN | Yes | Reset + code cleared |
| HW_Fault_Code = 4 (PSU_OVERVOLTAGE) (any non-zero HW_Fault_Code incl. 9-19 is treated the same) | 4 | All off | SAFETY_SHUTDOWN | Yes | Reset + code cleared |
| HW_Fault_Code = 5 (MASTER_SWITCH_FAULT) (any non-zero HW_Fault_Code incl. 9-19 is treated the same) | 5 | All off | SAFETY_SHUTDOWN | Yes | Reset + code cleared |
| HW_Fault_Code = 6 (COMM_CRC_ERROR_RATE) (any non-zero HW_Fault_Code incl. 9-19 is treated the same) | 6 | All off | SAFETY_SHUTDOWN | Yes | Reset + code cleared |
| HW_Fault_Code = NaN (unreadable) | 8 | All off | SAFETY_SHUTDOWN | Yes | Reset + code readable (treated as hardware stale) |
| All 4 channels faulted (non-shutdown) | - | - | Alert CHANNEL_FAULT; demand 0 | - | - |
| Data_Stale_Twin (T_twin_s older than data_stale_twin_s, or NaN) | 7 | - | TWIN_DEGRADED (not a shutdown) | No | Automatic via T5/T6 (twin_ok held t_recover_s) |
| Twin_Valid = DEGRADED or NO_DATA; or VALID with T_est NaN / outside 25-43 degC | - | - | TWIN_DEGRADED (not a shutdown) | No | Automatic via T5/T6 |

## 6. Parameters
All read through `neram_ctrl/params.py`. **`config/params.json` was not supplied**; the controller uses a standalone table whose values are carried unchanged from the submitted script, each labelled with status, source and owner (table below = `T02_params_used.csv`). Rationale: Suchita's own design choices (dwell, recover, inhibit, mode caps, PI gains) are PROVISIONAL and tuned only on the ASSUMED plant; Sai's thermal/twin rows and Shreehan's hardware rows are placeholders and are *not* project decisions. A `None`/null value (module sensor range, `t_hw_cutoff_degC`) means "not supplied, feature disabled", never a guessed number.

| name | value | unit | status | owner |
|---|---|---|---|---|
| ts_ctrl_s | 1 | s | PROVISIONAL | Suchita |
| ts_twin_s | 60 | s | FROZEN | Sai |
| data_stale_twin_s | 120 | s | PROVISIONAL | Sai |
| data_stale_hw_s | 5 | s | TBD/PLACEHOLDER | Shreehan |
| t_hypo_degC | 36.0 | degC | TBD/PLACEHOLDER | Sai |
| t_target_degC | 37.0 | degC | TBD/PLACEHOLDER | Sai |
| p_trigger | 0.3 | - | PROVISIONAL | Sai |
| p_release | 0.2 | - | PROVISIONAL | Sai |
| n_confirm_updates | 2 | count | PROVISIONAL | Sai |
| band_target_degC | 0.3 | degC | PROVISIONAL | Suchita |
| t_dwell_min_s | 10 | s | PROVISIONAL | Suchita |
| t_recover_s | 30 | s | PROVISIONAL | Suchita |
| t_stop_inhibit_s | 300 | s | PROVISIONAL | Suchita |
| d_pred_max_pct | 40 | % | PROVISIONAL | Suchita |
| d_active_max_pct | 70 | % | PROVISIONAL | Suchita |
| d_maint_max_pct | 50 | % | PROVISIONAL | Suchita |
| d_fallback_pct | 20 | % | PROVISIONAL | Suchita |
| kp_pct_per_degC | 20 | %/degC | PROVISIONAL | Suchita |
| ki_pct_per_degC_s | 0.5 | %/(degC*s) | PROVISIONAL | Suchita |
| p_max_ch_pct | [50, 50, 50, 50] | % | TBD/PLACEHOLDER | Shreehan |
| t_mod_derate_degC | 38 | degC | TBD/PLACEHOLDER | Shreehan |
| t_mod_trip_degC | 41 | degC | TBD/PLACEHOLDER | Shreehan |
| t_mod_reset_degC | 37 | degC | TBD/PLACEHOLDER | Shreehan |
| t_hw_cutoff_degC | null | degC | TBD (no placeholder) | Shreehan |
| dt_sensor_disagree_degC | 2.0 | degC | TBD/PLACEHOLDER | Shreehan |
| i_on_A | 0.5 | A | TBD/PLACEHOLDER | Shreehan |
| i_open_max_A | 0.05 | A | TBD/PLACEHOLDER | Shreehan |
| i_over_A | 2.0 | A | TBD/PLACEHOLDER | Shreehan |
| i_stuck_A | 0.05 | A | TBD/PLACEHOLDER | Shreehan |
| module_temp_min_degC | null | degC | TBD (no placeholder) | Shreehan |
| module_temp_max_degC | null | degC | TBD (no placeholder) | Shreehan |
| k_heat_degC_per_h | 0.6 | degC/h at 100% all ch | ASSUMED | Sai |
| tau_heat_min | 15 | min | ASSUMED | Sai |
| w_ch | [0.25, 0.25, 0.25, 0.25] | - | ASSUMED | Sai |
| r_obs_degC2 | 0.0025 | degC^2 | PLACEHOLDER | Sai |
| plant_passive.mode | flat | - | PLACEHOLDER | Sai |
| t_skin_base_degC | 33.0 | degC | ASSUMED | Suchita |
| k_mod_degC | 6.0 | degC | ASSUMED | Suchita |
| tau_mod_s | 90 | s | ASSUMED | Suchita |
| sd_mod_sensor_degC | 0.05 | degC | ASSUMED | Suchita |
| sd_standin_degC | 0.05 | degC | ASSUMED | Suchita |
| tau_standin_s | 15 | s | ASSUMED | Suchita |

## 7. Hardware and plant assumptions
- No hardware limit, sensor range or fault code was invented. Shreehan's rows (`p_max_ch_pct`, `t_mod_*`, `i_*_A`, `dt_sensor_disagree_degC`, `data_stale_hw_s`) are the placeholders of the submitted script.
- Test bench stand-ins (all test-only and labelled `SIMULATED / ASSUMED PROTOTYPE RESPONSE`): patient plant `d = sum w_i Heat_i/100`, `h += dt/tau (d-h)`, `dT += k dt/60 h`, `T_plant = T_pass + dT` with a *flat* `T_pass`; twin stand-in (first-order filter of a noisy observation, normal-CDF `P_below_hypo`); module thermal stand-in; hardware stand-in (`Heater_Current = Heat/100 * i_on_A`). None of these is Sai's twin or Shreehan's hardware.
- Closed-loop times (e.g. time to target in TC04) depend on the ASSUMED gain and caps. TC18 shows 13.9 h / 7.0 h / 3.6 h at 0.5x / 1x / 2x gain; these are sensitivity numbers, not predictions.

## 8. Deviations and corrections
- **D1 (open-circuit rule).** The literal rule (`Heat_i > 0` and `Heater_Current_i < i_open_max_A` held) raises false HEATER_OPEN on every channel when the PI demand is small (expected current < `i_open_max_A` already at about 10 % duty with the placeholder values). The default is the *qualified* rule: only when the expected current `Heat_i/100 * i_on_A >= i_open_max_A`; NaN current is always a fault. Evidence: `audit_checks.csv` AU-D1. The two placeholders are inconsistent and need Shreehan's confirmation.
- **Defects of the supplied script, fixed:** handoff column grouping (A then B) -> interleaved per channel; CHANNEL_FAULT alert never raised; wrong sensor-B code (302 vs 303); TC04 plant with a restoring pull (target unreachable); TC05/07/13 vacuous set-ups; `Heater_Current` not following `Heat`; `Trigger_Reason` pulsed instead of held; Python `max()` with NaN; NaN treated as cool/released; FIXED mode used the PI law; Reset rising edge not computed once per sample.
- `AlertCode.DATA_STALE` (6) has no emitting rule in the plan; it is not emitted.

## 9. Test results (this run)
Unified table: `results/test_results.csv` (one row per criterion, with params version and code version). A test is PASS only if every judged criterion passes; REPORTED rows are values reported, not judged.

| test | title | criteria passed | result |
|---|---|---|---|
| TC01 | No action when stable (SYN_01) | 4/4 | PASS |
| TC02 | Predictive trigger (SYN_02) | 8/8 | PASS |
| TC03 | +60 min horizon is alert-only (SYN_03) | 5/5 | PASS |
| TC04 | Active recovery to target (STANDIN closed loop) | 5/5 | PASS |
| TC05 | Clinician early start (SYN_01, Start at 600 s) | 8/8 | PASS |
| TC06 | Clinician STOP mid-warming (TC04 scenario) | 6/6 | PASS |
| TC07 | Over-temperature shutdown (STANDIN; CH2 sensor A ramp) | 7/7 | PASS |
| TC08 | Sensor fault isolates one channel (CH3 sensor B NaN) | 9/9 | PASS |
| TC09 | Sensor disagreement (CH1 sensor A offset) | 5/5 | PASS |
| TC10 | Module disconnected (Module_Connected_4 = 0) | 6/6 | PASS |
| TC11 | Hardware cutoff reported (HW_Cutoff_2 = 1) | 6/6 | PASS |
| TC12 | Stuck-on driver (CH1 current > i_stuck_A with Heat_1 = 0) | 7/7 | PASS |
| TC13 | Twin unreliable: no autonomous warming (SYN_04) | 7/7 | PASS |
| TC14 | Twin stale (T_twin_s frozen) | 6/6 | PASS |
| TC15 | Hardware stale (HW_Heartbeat_s frozen) | 7/7 | PASS |
| TC16 | Twin degraded during clinician warming | 7/7 | PASS |
| TC17 | No chattering (STANDIN, T_est noise around t_target) | 8/8 | PASS |
| TC18 | Assumed-gain sensitivity (TC04 at 0.5x, 1x, 2x k_heat_degC_per_h) | 1/1 | PASS |
| TC19 | Development-case open-loop replay (twin_DEV_<pseudo>.csv) | 0/1 | BLOCKED |
| TC20 | Twin in the loop (summit) | 0/0 | EXCLUDED |

TC19 is BLOCKED (needs Sai's `twin_DEV_<pseudo>.csv`); TC20 is summit-stage and excluded. Section-G audit: `results/tables/audit_checks.csv`
(AU-G2a *BLOCKED*: module sensor range not supplied). The traceability table is `results/tables/requirements_traceability.csv`.

### Requirements traceability

| requirement | text | test ID(s) | status |
|---|---|---|---|
| K1 | SAFETY_SHUTDOWN sets all Heat_i = 0 in the step it is entered and holds them at 0 | TC07; TC11; TC12; TC15 | verified |
| K2 | Every safety fault is latched; only Clinician_Reset with the condition cleared releases it | TC07; TC11; TC12; TC15 | verified |
| K3 | Clinician_Stop always wins over any autonomous transition and blocks autonomous re-entry for t_stop_inhibit_s | TC06 | verified |
| K4 | Autonomous warming (T10, T11) requires twin_ok; INITIALISING/DEGRADED/NO_DATA/stale means no autonomous warming | TC13; TC14; TC19 | verified (TC19 BLOCKED - see test_results.csv) |
| K5 | P60 can only raise FORECAST_RISK_60_INFO | TC03 | verified |
| K6 | A NaN in any signal used for a decision is a fault or "not ok", never 0 | TC08; AU-G1 | verified |
| K7 | Heat_i is always clamped to [0, p_max_ch_pct_i] | TC04; TC05; TC16; TC18; AU-G9 | verified |
| J-R1 | PREDICTIVE_WARMING never exits on the forecast | TC02 | verified |
| J-R2 | TARGET_MAINTENANCE has no automatic exit to NORMAL | TC04 | verified |
| J-R3 | Clinician_Start in ACTIVE or MAINT only sets Clinician_Mode | AU-G7 | verified |
| J-T5/T6 | Twin recovery requires twin_ok held t_recover_s | TC13; TC14; TC16 | verified |
| J-T8 | Clinician_Start with twin_ok enters CLINICIAN_WARMING; heat from the PI law | TC05 | verified |
| J-T10 | Below t_hypo (twin_ok) for t_dwell_min_s -> ACTIVE_WARMING | TC04; TC06 | verified |
| J-T11 | Forecast risk confirmed for n_confirm_updates twin minutes -> PREDICTIVE_WARMING | TC02 | verified |
| J-T13 | at_target held -> TARGET_MAINTENANCE | TC04; TC05; TC17 | verified |
| J-T14 | target_lost held -> ACTIVE_WARMING | TC17 | verified |
| J-DW | No transition before its dwell; no chattering | TC17 | verified |
| L-CH | Channel fault (sensor, disagreement, disconnect, open) isolates only that channel and raises CHANNEL_FAULT | TC08; TC09; TC10 | verified |
| L-SYS | Over-temperature, cutoff, over-current, stuck-on, HW stale and HW_Fault_Code force a system shutdown | TC07; TC11; TC12; TC15; AU-G5 | verified |
| L-PRI | Fault priority: system before channel; lower channel first; shutdown-class before isolating faults | TC07; AU-G3 | verified |
| L-TW | Data_Stale_Twin -> TWIN_DEGRADED, not a shutdown, no latch | TC14 | verified |
| I-FIX | Twin degraded during clinician warming -> fixed fallback demand, still module-limited | TC16 | verified |
| S-LOG | Controller log columns, units, enums and NaN-as-empty per section S | LOGCHECK | verified |

## 10. Limitations
- Everything runs on assumed plants and synthetic twin signals; passing a test shows the *logic* meets its stated criteria on those signals, nothing about real warming, comfort or safety.
- Module sensor range faults (x02/x04) are not detected until Shreehan supplies the range; `t_hw_cutoff_degC` is only exercised by injection.
- `plant_passive.*` is a flat placeholder; drift or circadian cooling is not represented.
- Handoff logs follow section S as written in the plan text; they have not been checked against the team's `interface_spec.csv` (not supplied).
- TC19 (real development-case replay) has not been run on any input.

## 11. Reproduction
`python scripts/run_all_tests.py` (see `README.md`). Python 3.13.16, numpy 2.5.3, pandas 3.0.5, matplotlib 3.11.2.
