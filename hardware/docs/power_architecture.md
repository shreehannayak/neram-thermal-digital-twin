# Power Architecture

Proof-of-concept prototype, not a medical device. All hardware in the demo is SIMULATED. Standards are cited as design references only; no compliance is claimed.

## 1. Power chain (FROZEN direction: mains-powered, bedside or table-rail)
Mains inlet -> fuse -> isolated AC/DC supply intended for medical equipment -> v_bus_V -> master safety switch -> four channel fuses and switches -> heater modules.
A separate DC/DC regulator (RECOM R-78E5.0-0.5, 24 V to 5 V) supplies the logic through the Nucleo E5V input; the sensors run from the board 3.3 V. One channel is drawn in `hardware/schematics/channel_driver.png`.

For bench testing only, a current-limited laboratory SELV supply may stand in for the AC/DC supply. Any document or figure showing such a setup must say so.

## 2. Parameters
| Parameter | Unit | Required | Source | Status |
|---|---|---|---|---|
| v_bus_V | V | Low-voltage (SELV) level compatible with heater ratings | 24 V: design choice, below the 28 V KHLVA maximum and equal to the MPM-65-24ST output | PROVISIONAL |
| Isolation between mains and outputs | - | Level required for a patient-applied part | IEC 60601-1 (cite clause). The provisional supply states primary-secondary 2 x MOPP (MPM-65 spec sheet); whether that is sufficient is TBD | TBD |
| Applied-part classification of the modules | - | For example type B or BF, with justification | IEC 60601-1 | TBD |
| Leakage-current limits | uA | From the standard | IEC 60601-1 | TBD (stated as a design requirement, not a compliance claim) |
| Creepage and clearance | mm | From the standard for the chosen voltages | IEC 60601-1 | TBD |
| p_logic_W | W | Logic power draw | Datasheets. Upper bound: the logic regulator delivers at most 5 V x 0.5 A = 2.5 W (R-78E5.0-0.5) | TBD |
| psu_rating_W | W | At least P_peak_W x derating factor from the supply datasheet's derating curve | Supply datasheet | TBD |

## 3. Power budget
See hardware/power/power_budget.csv. Formulas:
- P_peak_W = sum of p_max_ch_W (all four at 100 %) + p_logic_W
- P_cont_W = sum of (mean duty_i from T07_duty_stats.csv x p_max_ch_W) + p_logic_W, reported per scenario and for a worst case (95th-percentile duty)
- E_case_Wh = P_cont_W x t_case_h (case duration from development data only)

Every result stays TBD until its inputs are sourced, then PROVISIONAL.

## 4. Why not a battery
The design direction is mains-powered, with no wrist battery in any diagram. To justify this, compare E_case_Wh with the capacity of a realistic wrist-worn cell (from a datasheet). Both numbers are TBD until the power budget is complete and a cell datasheet is chosen: E_case_Wh = TBD; wrist-cell capacity = TBD (datasheet link to be added). This paragraph will be completed when both are known; nothing is estimated here.
