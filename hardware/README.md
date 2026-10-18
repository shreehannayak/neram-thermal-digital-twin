# Hardware (Shreehan)

Proof-of-concept prototype, not a medical device. All hardware in the demo is SIMULATED. Standards are design references only; no compliance is claimed. Every value has a source and a status (FROZEN, PROVISIONAL or TBD); unsourced values are TBD.

## Contents
| Folder or file | What it holds |
|---|---|
| diagrams/ | system_block_diagram, safety_layers, interface_map (.drawio source and .png; both written by make_diagrams.py) |
| comparisons/ | sensor_comparison.csv, mcu_comparison.csv, heater_comparison.csv |
| docs/ | patient_observation_interface.md, module_sensing.md, power_architecture.md, standards_references.md, feasibility.md |
| interfaces/ | fault_codes.csv, comm_protocol.md, controller_hw_interface.md, cad_envelope.csv |
| power/ | power_budget.csv |
| bom/ | electrical_bom.csv |
| schematics/ | channel_driver.png / .pdf: one-channel schematic (written by make_schematic.py) |

## Provisional choices (CP3)
- Heater: polyimide flexible heater, Omega KHLVA series (28 V). Not self-limiting, so the layer-1 cutoff is essential.
- MCU: STM32 Nucleo-G474RE. Reset state of outputs must still be verified.
- Sensor: TDK NTCG163JX103DTDS 10 kOhm NTC (0603) on a flex tail, 2 per module (PROVISIONAL; four types compared, docs/module_sensing.md).
- Supply: Mean Well MPM-65-24ST (24 V, 65 W); bus v_bus_V = 24 V (PROVISIONAL).

## Three safety layers
1. Hardware cutoff (no firmware).
2. MCU firmware (limits, independent watchdog, host heartbeat, stuck-on detection).
3. Supervisory controller (Suchitha).
Each layer can remove heater power without the layers above it.

## How to open the files
- .drawio: open at app.diagrams.net (File, Open from, Device). To regenerate source and images: `python hardware/diagrams/make_diagrams.py` and `python hardware/schematics/make_schematic.py` (matplotlib).
- .csv: any spreadsheet app.
- .md: any text editor or GitHub.
