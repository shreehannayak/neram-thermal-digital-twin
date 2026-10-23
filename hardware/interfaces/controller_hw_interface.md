# Controller-Hardware Interface (v1, CP1)

Status: PROVISIONAL. All hardware in the demo is SIMULATED (Suchita's stand-ins). Proof-of-concept prototype, not a medical device.

## 1. Meaning of Heat_i
- Heat_i (i = 1..4) is the PWM duty in percent at pwm_freq_Hz (TBD).
- Range 0 to p_max_ch_pct_i. Sent every 1 s.
- The MCU applies it within one command period.
- Heat_i = 0 means heater power is removed within one command period.
- CH1 = left hand, CH2 = right hand, CH3 = left foot, CH4 = right foot.

## 2. Status signals (MCU to host, every hw_status_period_s = 1 s, PROVISIONAL)
| Signal | Wire type | Encoding | Invalid value |
|---|---|---|---|
| Module_Temp_i_A / _B | int16 | 0.01 degC | 0x7FFF -> NaN |
| Heater_Current_i | uint16 | mA | 0xFFFF -> NaN |
| Module_Connected_i | bit in connected_bits (uint8) | 1 = connected | - |
| HW_Cutoff_i | bit in hw_cutoff_bits (uint8) | 1 = cutoff tripped | - |
| HW_Fault_Code | uint16 | see fault_codes.csv | 0 = none |
| HW_Heartbeat_s | derived | time of last valid status frame | NaN |

Open or short sensor circuits must read as invalid (0x7FFF), never as a plausible temperature.

## 3. Fault codes
See hardware/interfaces/fault_codes.csv (names FROZEN at CP1).

## 4. Parameter rows for config/params.json
Sai merges these. No value is invented: TBD means no sourced value yet.

| Parameter | Unit | Value | Placeholder | Source | Status |
|---|---|---|---|---|---|
| p_max_ch_pct (4 values) | % | - | TBD | Calculation from p_max_ch_W | TBD |
| t_mod_derate_degC | degC | - | TBD | Standard / clinician | TBD |
| t_mod_trip_degC | degC | - | TBD | Standard / clinician | TBD |
| t_mod_reset_degC | degC | - | TBD | Standard / clinician | TBD |
| t_hw_cutoff_degC | degC | - | TBD | Device datasheet / comparator design | TBD |
| dt_sensor_disagree_degC | degC | - | TBD | Calculation from sensor accuracy | TBD |
| i_on_A | A | - | TBD | v_bus_V / heater_r_ohm | TBD |
| i_open_max_A | A | - | TBD | Calculation from i_on_A | TBD |
| i_over_A | A | - | TBD | Calculation from i_on_A | TBD |
| i_stuck_A | A | - | TBD | Calculation from sense noise floor | TBD |
| data_stale_hw_s | s | - | 2 (>= 2 x hw_status_period_s) | Derived | PROVISIONAL |
| sensor_sample_rate_Hz | Hz | - | 1 (simulation only) | Placeholder | TBD |

Required ordering (FROZEN): t_mod_derate_degC < t_mod_trip_degC < t_hw_cutoff_degC <= t_surface_limit_degC.

## 5. Hardware assumptions (for Suchita to confirm)
- Command update every 1 s.
- Hardware removes heater power within one command period after Heat_i = 0.
- Status heartbeat at least every data_stale_hw_s / 2.
- Hardware cutoff (layer 1) and MCU watchdog (layer 2) exist independently of the controller.
- On host heartbeat loss, the MCU switches all heaters OFF.
