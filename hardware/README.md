# Hardware (Shreehan)

Proof-of-concept prototype, not a medical device. All hardware in the demo is SIMULATED. Standards are design references only; no compliance is claimed. Every value has a source and a status (FROZEN, PROVISIONAL or TBD); unsourced values are TBD.

## Contents
| Folder or file | What it holds |
|---|---|
| diagrams/ | system_block_diagram, safety_layers, interface_map (.drawio source and .png) |
| comparisons/ | sensor_comparison.csv, mcu_comparison.csv, heater_comparison.csv |
| docs/ | patient_observation_interface.md, module_sensing.md, power_architecture.md, standards_references.md, feasibility.md |
| interfaces/ | fault_codes.csv, comm_protocol.md, controller_hw_interface.md, cad_envelope.csv |
| power/ | power_budget.csv (and .xlsx) |
| bom/ | electrical_bom.csv |
| schematics/ | channel_driver one-channel schematic |

## Provisional choices (CP3)
- Heater: polyimide flexible heater, Omega KHLVA series (28 V). Not self-limiting, so the layer-1 cutoff is essential.
- MCU: STM32 Nucleo-G474RE. Reset state of outputs must still be verified.
- Sensor: no final choice yet; four candidates compared.

## Three safety layers
1. Hardware cutoff (no firmware).
2. MCU firmware (limits, independent watchdog, host heartbeat, stuck-on detection).
3. Supervisory controller (Suchitha).
Each layer can remove heater power without the layers above it.

## How to open the files
- .drawio: open at app.diagrams.net (File, Open from, Device).
- .csv: any spreadsheet app.
- .md: any text editor or GitHub.
