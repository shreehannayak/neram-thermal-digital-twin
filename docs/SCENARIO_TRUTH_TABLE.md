# Scenario truth table (updated 18 Oct 2026, 01:30 IST, after the Unity Editor session)

A replay that passes `integration/validate_replay.py` (and its C# twin) is **well-formed**. This table records
whether its frames **behave** as the title says. The checks used:
* `tools/check_replay_semantics.py` (S01–S08);
* the JSON Schema test;
* a reading of the source rows against the controller test definitions in plan §1N.

Every scenario is SYNTHETIC. No VitalDB observation and no holdout case appears anywhere.

## 1. Shipped replays (integration/replays = unity_editor/Assets/StreamingAssets/replays, byte-identical)
| Scenario ID | Source twin | Source controller log | Provenance | Declared behaviour | Actual frame behaviour | Schema | Behaviour | v4 runtime | Demo | Limitation |
|---|---|---|---|---|---|---|---|---|---|---|
| SYN_SCN_A0 | v4 stand-in filter (`twin_SYN_SCN_A0.csv`, src twin SIMULATED) | scripted stand-in (`ctrl_SYN_SCN_A0.csv`) | `tools/make_synthetic_replays.py`, byte-reproducible | Usual-care **layout** stand-in for SCN_A | Predictive → active warming up to 57 % | VALID, 0 W; JSON Schema pass | OK | Played in Editor and build on 10 Oct | YES, as the SCN_A layout stand-in only | Not a development case; SCN_A itself is blocked by the fit |
| SYN_SCN_B | same | same | same | Predictive warming (SCN_B) | NORMAL → PREDICTIVE → ACTIVE → TARGET_MAINTENANCE; heat up to 37 %; ASSUMED dT_heat reproduced by `src/assumed_warming.py` | VALID, 0 W; pass | OK | **Played in Editor 18 Oct (PASS)** at 60×: predictive warming, forecast fan +20/+30/+60 with P<t_hypo, heating channels, TARGET_MAINTENANCE | **YES (SCN_B)** | Stand-in twin and controller; warming ASSUMED |
| SYN_SCN_C | same | same | same | Over-temperature fault (SCN_C) | Warming, then SAFETY_SHUTDOWN | VALID, 0 W; pass | OK | 10 Oct | **YES (SCN_C)** | Stand-in controller |
| SYN_SCN_D | same | same | same | Twin degraded (SCN_D) | TWIN_DEGRADED; forecast hidden; 120 s recovery dwell, then TWIN_RECOVERED | VALID, 0 W; pass | OK (S03 INFO: recovery dwell) | 10 Oct (not replayed 18 Oct) | **YES (SCN_D)** | Stand-in twin and controller |
| SYN_ENG_01–06 | same | same | same | Engineering cases (START/STOP, channel faults, stuck-on/cutoff, HW stale, degraded during clinician warming, +60 info-only) | As titled; ENG_03/04 end still latched | VALID, 0 W; pass | OK | 10 Oct | YES (engineering) | Stand-in controller |
| **SYN_TC07** | `twin_SYN_01.csv`: canonical filter, ASSUMED_SYNTHETIC parameters (src twin MODEL) | `ctrl_TC07.csv` (Suchitha; hash b3f7ce8d…; received 17 Oct; owner confirmation pending) | `build_replay.py --accept-ctrl-input-columns --params-used SYN_TC07_params_used.json --params-version 0.2` (no `--placeholder`: canonical twin + real controller log), byte-reproducible, SHA-256 7714f8a8… | Module over-temperature shutdown (first TC07 criterion only) | Channel-2 module temperature (A and B), an injected stimulus, rises 33 → 45 °C with zero heater current. At t = 200 s (temperature 41.0): SAFETY_SHUTDOWN, Fault_Latched, fault_code = Channel_Fault_2 = 206 (= channel 2 OVERTEMP_SW), Alert SAFETY_SHUTDOWN. Still latched at t = 300 s. Heat 0 % throughout | VALID, 301 × W108 (STANDIN without plant values; kept); pass | OK (S04, S06 INFO) | **Played in Editor 18 Oct (PASS)**: banner "SAFETY SHUTDOWN — LATCHED", fault 206 OVERTEMP_SW CH2 (placeholder text), "CH2 Right hand: 206", latched since T+00:03:20, all heating commands 0, CH1–CH4 SHUTDOWN, "Latched — awaiting clinician RESET"; no placeholder watermark; MONITOR shows OBS SIMULATED / TWIN MODEL; CH2 T_A = T_B = 41.0 °C | **CONDITIONAL**: shutdown and latch display only | No heating, no cooling, no RESET_BLOCKED, no reset/release, so TC07 criteria 3–5 are not shown. HW cutoff threshold TBD |

## 2. Candidates rejected for the demo
| Candidate | Source | Finding (verified from source rows) | Plan §1N criterion | Status |
|---|---|---|---|---|
| TC05 replay | `ctrl_TC05.csv` (7381e4d3…) | t_s 600–610 `Controller_State = 4` (CLINICIAN_WARMING), Trigger 4 (CLINICIAN_START), Clinician_Mode 1, **Heat_1..4 = 0 and Demand_Global = 0**. t_s 611 `Controller_State = 3`, Trigger 5 (TARGET_REACHED), while `t_target_degC` had no value in params.json v0.1 | TC05 requires "Heat set by PI, not fixed 100 %"; zero heat for the whole episode fails it | **Verified, open** (Suchitha). Excluded |
| TC13 replay | `ctrl_TC13.csv` (c1bef0c8…) | t_s 70–80 and 641–651 PREDICTIVE_WARMING with all heat 0, then TARGET_REACHED at 81 and 652. t_s 300–629 TWIN_DEGRADED (MONITOR), Alert TWIN_DEGRADED, heat 0. TWIN_RECOVERED at 630 | The degraded part **meets** its TC13 criteria. The predictive episodes fail TC02's "0 < Heat_i ≤ d_pred_max_pct" | **Verified, open** (Suchitha). Excluded |
| TC13 pairing | — | The log does not record the Twin_Valid timeline it was driven with. Plan says SYN_04 (then a copy of SYN_SCN_D). No single time offset of `twin_SYN_SCN_D` reproduces it: that twin is DEGRADED for 1,140 s (2280–3419 s), the controller for 330 s | — | **Verified, open.** A faithful replay needs Suchitha's twin input file |
| SCN_C / SCN_D from the 17 Oct ChatGPT bundle | bundle | SCN_D's twin was edited to agree with the controller, and stitched from out-of-order segments (jump at 300 s). SCN_C claimed "blocked reset, release", which is not in TC07. Both are SYNTHETIC without the `SYN_` prefix and would fail v4 `AllReplaysSmokeTests` | — | **Superseded**: not used |

## 3. Controller-log contract deviations (for Suchitha; verified)
* **Extra columns.** All three logs carry `HW_Heartbeat_s` and `HW_Fault_Code`. They are declared HW → Ctrl
  inputs in `config/interface_spec.csv`, but are **not** in the §1S log column list. The builder refuses them unless
  `--accept-ctrl-input-columns` is given.
* **Column order.** Module temperatures are ordered 1_A, 2_A, 3_A, 4_A, 1_B…; §1S specifies 1_A, 1_B, 2_A… The
  builder reads by name, so this has no effect, but it is a contract deviation.
* **Fault codes.** `HW_Fault_Code = 0` with `fault_code = 206` is **not** a contradiction. 206 is a channel code
  (100·ch + 6 = OVERTEMP_SW, detected by MCU/controller); HW_Fault_Code carries hardware system codes 0–19. The
  older audit's "contradiction" is resolved.

## 4. Plan conceptual cases → what can be shown on 20 Oct
| Plan case | Shown as | Can the required behaviour be demonstrated? |
|---|---|---|
| SCN_A usual care (development case, open loop) | SYN_SCN_A0 (layout stand-in) | **No.** Needs the development fit and data-use clearance |
| SCN_B predictive warming (synthetic, SIMULATED + ASSUMED) | SYN_SCN_B | Yes (stand-in controller) |
| SCN_C over-temperature fault | SYN_SCN_C; SYN_TC07 (real controller log, latch only) | Yes for the shutdown. TC07's reset/release cannot be shown from Suchitha's log |
| SCN_D twin degraded | SYN_SCN_D | Yes (stand-in) |
| Heating from Suchitha's real controller | — | **No.** No supplied log commands any heat |

## 5. Suchitha's controller package v2 (received 18 Oct 2026, Python fallback) — `integration/controller_logs_received/2026-10-18/`
| Log | SHA-256 (16) | Behaviour verified from the rows | Earlier finding | Unity |
|---|---|---|---|---|
| ctrl_SYN_02 | 624a213f743fcec4 | NORMAL → PREDICTIVE_WARMING at 370 s (FORECAST_P20); heat 10–40 % | — | not built: twin input missing |
| ctrl_TC05 | 377c263ac30f055a | CLINICIAN_WARMING at 600 s (CLINICIAN_START); PI heat 12.3 → 50 % | zero-heat clinician warming: **fixed** | not built: twin input missing |
| ctrl_TC07 | acc87e2a3a315ed6 | ACTIVE from 10 s; SAFETY_SHUTDOWN at 958 s (206, after 205); RESET_BLOCKED; RESET at 1250 s → NORMAL; STANDIN with T_plant | no reset/release: **fixed** (full TC07 cycle) | not built: twin input missing |
| ctrl_TC08 | 196ce49518b7a955 | CH3 sensor B NaN → Channel_Fault_3 = 303, CH3 off, others unchanged | new | not built: twin input missing |
| ctrl_TC13 | 1eae7553531260ac | PRED at 70 s with 40 % heat; TWIN_DEGRADED 300–629 s, heat 0; recovered 630 s | zero-heat predictive episodes: **fixed** | not built: twin input missing |

Checks run (18 Oct): 0 samples of warming with zero heat, 0 samples of heat during SAFETY_SHUTDOWN, 1 Hz continuous, enums in range.
**Why no Unity replay yet:** every log was driven by her own test-bench twin stand-in (not twin_SYN_01..04, which never reached her). The logs do not contain that twin trace, and pairing them with a different twin would show contradictions on screen (e.g. ACTIVE_WARMING "T_est below t_hypo" at 10 s while the displayed twin is above t_hypo and still initialising). Unblocked by either: (a) her exporting the twin input she used per test, or (b) re-running SYN_02/TC05/TC13 on twin_SYN_02/01/04. ctrl_TC04 was not included in this package. SYN_TC07 (previous TC07 log) stays in the demo until then.
