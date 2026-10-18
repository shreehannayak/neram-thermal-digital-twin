# NERAM: Thermal Digital Twin and Simulated Warming Controller

> One-line summary: TBD (wording from Sai)

Proof-of-concept prototype, not a medical device. SIMULATED / ASSUMED PROTOTYPE RESPONSE where marked.

## 1. Title and one-line summary
TBD (Sai supplies the wording; title must be identical in README, CITATION.cff, slide 1 and video title)

## 2. Team and contributions
TBD (each member confirms their own line in a GitHub comment)

## 3. College / incubator
TBD (must match the registration exactly)

## 4. Problem statement
TBD (Sai)

## 5. Healthcare use case
TBD (Sai)

## 6. What the prototype is and is not
TBD (Sai, from docs/SAFETY_AND_LIMITATIONS.md)

## 7. System architecture
TBD (Sai figure + links)

## 8. Digital Twin and results
TBD (Sai)

## 9. Controller
TBD (Suchitha)

## 10. Hardware
The hardware layer is a paper design of a four-channel warming controller. In the demo every hardware signal is SIMULATED by the controller test bench stand-ins. No physical device has been built, and no heat delivery, clinical effect or standards compliance is claimed. Standards are cited as design references only.

**Architecture.** A bedside host laptop runs the Digital Twin and the supervisory controller. It sends a heating command (Heat_1 to Heat_4, as PWM duty percent) to a microcontroller board every second. The board reads two skin-interface temperature sensors (A and B) per module and a current sensor per channel, drives four heater channels, and reports status back. The four channels are CH1 left hand, CH2 right hand, CH3 left foot and CH4 right foot.

**Three independent safety layers.**
1. Hardware cutoff (no firmware): works with the microcontroller halted and latches until manually reset.
2. Microcontroller firmware: limits, an independent watchdog, a host-heartbeat check and stuck-on detection.
3. Supervisory controller (software).
A master safety switch, default open, sits in series with all four channels. Each layer can remove heater power without the layers above it.

**Provisional choices (CP3).**
- Heater: polyimide flexible heater, Omega KHLVA series (28 V). It is not self-limiting, so the hardware cutoff is essential.
- Microcontroller: STM32 Nucleo-G474RE. Its output state at reset must still be verified.
- Temperature sensor: four types compared (NTC thermistor, Pt1000, digital IC, thermocouple); no final choice yet.

**Status of values.** Every hardware number has a source and a status (FROZEN, PROVISIONAL or TBD). Heater power, current thresholds, module temperature thresholds and the skin-surface limit are TBD until sourced from datasheets, a standard or a clinician. Nothing was estimated to fill a gap.

**Files.** See hardware/README.md for the full list: diagrams (block diagram, safety layers, interface map), comparisons (sensor, MCU, heater), documents (observation interface, module sensing, power architecture, standards references, feasibility), interface files (fault codes, communication protocol, controller interface, CAD envelope), power budget and electrical bill of materials.

## 11. CAD
TBD (Neharika)

## 12. Unity demo
TBD (Sai)

## 13. Technical stack
TBD

## 14. How to reproduce
TBD (each owner's run commands)

## 15. Data and licence notice
TBD (VitalDB citation, data-use terms, no raw data in the repo)

## 16. Demo video, architecture PDF, presentation links
TBD

## 17. Licences
- Code: Apache-2.0 (see LICENSE)
- CAD, docs, figures: CC BY 4.0 (see LICENSE-CAD-DOCS)

## 18. Citation
See CITATION.cff
