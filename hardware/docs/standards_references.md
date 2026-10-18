# Standards References

Standards are cited as DESIGN REFERENCES ONLY. This project does not claim compliance with any standard. Proof-of-concept prototype, not a medical device.

## 1. Heating pads: skin-surface temperature limit
| Item | Detail | Status |
|---|---|---|
| Standard | IEC 60601-2-35:2020 (with Amendment 1:2023): Medical electrical equipment, Part 2-35: particular requirements for the basic safety and essential performance of heating devices using blankets, pads or mattresses and intended for heating in medical use | Verified to exist (scope text read on IEC and national standards pages) |
| Replaces | IEC 80601-2-35:2009 and Amendment 1:2016 | Verified |
| Note on earlier wording | The project plan names IEC 80601-2-35. That edition has been replaced; Sai to be told so config/params.json source text can be updated | To action |
| Stated scope | Heating devices using blankets, pads or mattresses in medical use (including pre-warming a bed). Excludes physiotherapy heating devices, infant radiant warmers, infant incubators and cooling devices | From scope text |
| Applies to the NERAM hand and foot modules? | Not decided. The modules are heated wraps and pads, so the standard is used as a design reference. Whether they fall in its formal scope is not established | TBD |
| Surface-temperature limit clause | Not read (the standard text is paywalled) | TBD |
| t_surface_limit_degC | Comes from this standard (clause TBD) and/or a clinician. No value is entered anywhere until sourced | TBD |

## 2. General electrical safety
| Item | Detail | Status |
|---|---|---|
| Standard | IEC 60601-1: Medical electrical equipment, general requirements for basic safety and essential performance | Cited as design reference only |
| Isolation between mains and outputs | Clause TBD | TBD |
| Applied-part classification (type B or BF) | Clause and justification TBD | TBD |
| Leakage-current limits | Clause TBD; stated as a design requirement, not a compliance claim | TBD |
| Creepage and clearance | Clause TBD for the chosen voltage | TBD |

## 3. How these feed the threshold ordering (FROZEN)
t_mod_derate_degC < t_mod_trip_degC (software) < t_hw_cutoff_degC (hardware) <= t_surface_limit_degC
All four values are TBD until sourced from the standard, a device datasheet or a clinician.

## 4. What is not claimed
- No compliance with IEC 60601-1, IEC 60601-2-35 or any other standard.
- No claim of heat delivered to a patient or any clinical effect.
