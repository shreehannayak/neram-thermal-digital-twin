# Module Safety Sensing (Role B)

Proof-of-concept prototype, not a medical device. All hardware in the demo is SIMULATED.

These sensors protect the skin. They are NOT the Digital Twin's patient-state input (that is the "patient temperature signal", see patient_observation_interface.md).

| Parameter | Unit | Required value or range | Source | Status |
|---|---|---|---|---|
| sensors_per_module | count | 2, independent (separate lines and ADC inputs) | Project constraint | FROZEN |
| sensor_location | - | Skin interface; flush pockets in the heater area (geometry by Neharika) | Project constraint | FROZEN |
| sensor_range_degC | degC | Must cover ambient to above t_hw_cutoff_degC | Datasheet | TBD |
| sensor_accuracy_degC | degC | Over the operating range | Datasheet | TBD |
| sensor_response_s | s | Thermal response as mounted | Datasheet + mounting estimate | TBD |
| sensor_sample_rate_Hz | Hz | Fast enough that software trip detection lags the temperature rise by less than one controller step | Calculation from response time | TBD (placeholder 1 Hz for simulation) |
| sensor_fault_detectable | - | Open and short must read as out-of-range (NaN), never as a plausible temperature | Design requirement | FROZEN |
| dt_sensor_disagree_degC | degC | At least the combined accuracy of two sensors + expected spatial difference | Calculation from accuracy | TBD |
| sensor_isolation | - | Electrically insulated from skin | Datasheet / construction | TBD |

## Candidates compared
See hardware/comparisons/sensor_comparison.csv (NTC thermistor, Pt1000 RTD, digital IC, thermocouple). No sensor is chosen yet. Every number there comes from a linked datasheet or listing; blanks are TBD.

## Notes
- Sensor A sits near the centre of the heated area; sensor B at the location expected to be hottest (to be identified with Neharika).
- Open or short circuits must never read as a plausible temperature. A digital IC can fail by returning no reply, so the firmware must treat a missing reply as invalid.
- Layer-2 firmware and the supervisory controller both use these readings; the layer-1 hardware cutoff uses its own independent sensor or device.
