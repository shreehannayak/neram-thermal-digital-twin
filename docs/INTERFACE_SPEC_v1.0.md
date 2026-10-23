# Interface specification v1.0 (frozen 18 Oct 2026, Sai)

`config/interface_spec.csv` is frozen at **spec_version 1.0** (`config/enums.json`, `config/params.json`). The plan
asked for this freeze at CP2; it was held at v0.1 until the delivered files could be checked against it.

## What "frozen" means
* Signal **names, units, types, rates and missing/fault representation** do not change without a new spec version.
* **Values** (thresholds, gains, limits) are not part of the spec; they live in `config/params.json` with their own
  status (FROZEN / PROVISIONAL / TBD / ASSUMED) and owner.

## Status after the freeze (78 signals)
| Status | Count | Meaning |
|---|---|---|
| FROZEN | 34 | Sai-owned signals (twin outputs, replay metadata): produced by `src/twin_replay_export.py`, checked by `integration/validate_twin_output.py`, `integration/validate_replay.py` and the Unity loader |
| FROZEN names | 38 | Suchita / Shreehan signals: names, units and types fixed as used in Suchita's delivered v2 logs and Shreehan's `hardware/interfaces/controller_hw_interface.md`; ranges and values remain the owner's (params.json) |
| FROZEN (Replay field PROPOSED) | 3 | Clinician_Start / Stop / Reset: frozen controller inputs; not yet a replay field |
| ASSUMED | 2 | T_plant, dT_heat: assumed warming response (test bench only) |
| TBD | 1 | static_context.*: not used in v1.0 replays |

## Evidence (checked 18 Oct 2026)
* Every column of Suchita's v2 controller logs (`integration/controller_logs_received/2026-10-18/ctrl_*.csv`) is a
  spec signal; no log column is missing from the spec.
* Every column of the twin exports (`integration/twin_outputs/twin_SYN_0*.csv`) is a spec signal.
* Every spec signal appears in a log, a twin export or `unity/schema/replay_fields.json`, except the documented
  ones above (source_tag is the replay `src` group; clinician buttons; static_context).
* Replays built before the freeze record `spec_version` "0.1" in their header as provenance; no signal name changed,
  so they remain valid (validators do not compare spec_version).
