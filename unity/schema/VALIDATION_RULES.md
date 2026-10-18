# NERAM replay validation rules (schema 1.0)

These rules are implemented **identically** in:

- `unity/Assets/Scripts/Core/ReplayValidator.cs` (Unity loader, refuses to display an invalid file)
- `integration/validate_replay.py` (Python, run by `build_replay.py` before writing and by CI)

Both are tested against the same fixture corpus in `unity/Assets/Tests/Fixtures/` (`fixtures_manifest.json`
lists the expected codes per file). A replay with **any error** is rejected as a whole; Unity shows the
Replay Data Error screen and draws nothing from it. Warnings and info are listed in the Diagnostics panel.

Structural field definitions (names, groups, JSON types, nullability, units, ranges) come from
`replay_fields.json`; `replay_schema.json` is generated from it.

## File structure

| Code | Severity | Rule |
| --- | --- | --- |
| E001 | error | The first non-empty line must be a JSON object with `"type": "header"`. |
| E002 | error | Every required header field is present with the right JSON type (`type, schema_version, scenario_id, created_utc, params_version, spec_version, inputs, disclaimer, cohort`). |
| E003 | error | No unknown header fields (allowed optional: `static_context, placeholder, generator, scenario_info, params_used`). |
| E021 | error | At least 2 frames. |
| E090 | error | Every line parses as JSON. |
| E091 | error | Every line is a JSON object. |
| E092 | error | Every line after the header has `"type": "frame"`; a second header is an error. |
| E093 | error | No duplicate keys in any object. |
| E099 | error | More than 200 errors: validation stops (the file is already rejected). |

## Header and cohort (holdout guard)

| Code | Severity | Rule |
| --- | --- | --- |
| E071 | error | `schema_version` is supported (`1.0`); every frame `meta.schema_version` equals the header's. |
| E052 | error | `cohort` is `SYNTHETIC` or `DEVELOPMENT`. Anything else (for example `HOLDOUT`, `FINAL`) is rejected. |
| E053 | error | `cohort` is missing. (Proposed field; required so that a replay can never be ambiguous about its data origin.) |
| E051 | error | A frame with `src.obs = REAL_DEV` requires `cohort = DEVELOPMENT`. |
| E054 | error | A file with `placeholder = true` must not contain `src.obs = REAL_DEV`. |
| E070 | error | Every frame `meta.scenario_id` equals the header's `scenario_id`. |

## Fields

| Code | Severity | Rule |
| --- | --- | --- |
| E010 | error | Every group (`meta obs twin ctrl hw plant src`) and every non-optional field is present. |
| E080 | error | No unknown groups or fields. |
| E011 | error | JSON types: number fields accept numbers; `int`/`enum` fields accept integers only (2.0 is rejected); booleans accept `true/false` only (not 0/1); strings accept strings. `NaN`/`Infinity` literals are rejected: missing values are `null`. |
| E012 | error | `null` only where the field is nullable. |
| E013 | error | Values inside hard ranges (`range_mode = error`), e.g. `T_obs` 25-43 degC, probabilities 0-1, `Heat_i` 0-100 %. |
| W102 | warning | Values outside soft ranges (`range_mode = warn`), e.g. `T_est` outside 25-43 degC. |
| E014 | error | Integer enums are values defined in `config/enums.json`; string enums (`plant_mode`, source tags) are the frozen names. |
| E050 | error | Source tags allowed per group: `obs` REAL_DEV or SIMULATED; `twin` MODEL or SIMULATED; `ctrl` SIMULATED; `hw` SIMULATED; `plant` ASSUMED. |

## Time

| Code | Severity | Rule |
| --- | --- | --- |
| E020 | error | `meta.t_s` strictly increasing. |
| W101 | warning | Step between frames differs from the first step (non-uniform logical clock). |

## Observation and twin

| Code | Severity | Rule |
| --- | --- | --- |
| E060 | error | `obs_missing = true` if and only if `T_obs = null`. |
| E043 | error | `Twin_Valid = NO_DATA` requires `T_est = null` and `T_est_sd = null`. |
| E044 | error | `Twin_Valid != NO_DATA` requires `T_est` and `T_est_sd` non-null. |
| E040 | error | `Twin_Valid != VALID` requires every forecast field (`T_pred_h, L80_h, U80_h, L95_h, U95_h, P_below_hypo_h`, h = 20, 30, 60) to be null ("NaN unless VALID", interface spec). |
| E041 | error | `Twin_Valid = VALID` requires every forecast field non-null. |
| E042 | error | `L95_h <= L80_h <= U80_h <= U95_h`. |
| W103 | warning | `T_pred_h` outside `[L80_h, U80_h]` (possible for a mixture, but unusual). |

## Controller and hardware consistency

These check that the external controller log is self-consistent. They do **not** re-implement the controller.

| Code | Severity | Rule |
| --- | --- | --- |
| E031 | error | `Safety_Shutdown = true` if and only if `Controller_State = SAFETY_SHUTDOWN`. |
| E030 | error | In SAFETY_SHUTDOWN every `Heat_i = 0`. |
| E032 | error | A non-zero `Channel_Fault_i` lies in channel i's range `100*i + 1 ... 100*i + 99`. |
| E033 | error | A channel with `Channel_Fault_i != 0` has `Heat_i = 0`. |
| W104 | warning | `Degraded_Substate != 0` exactly when `Controller_State = TWIN_DEGRADED`. |
| W105 | warning | `fault_code` or `Channel_Fault_i` not in the loaded fault-code table (Unity runtime only, when a table is loaded). |

## Plant (simulated / assumed)

| Code | Severity | Rule |
| --- | --- | --- |
| E061 | error | `plant_mode = OPEN_LOOP` requires `T_plant = null` and `dT_heat = null` (no warming effect exists in open loop). |
| W108 | warning | `plant_mode` STANDIN or TWIN_IN_LOOP with `T_plant` or `dT_heat` null. |
| W107 | warning | `plant_mode` changes within a file. |
| W106 | warning | A source tag changes within a file. |

## Information

| Code | Severity | Rule |
| --- | --- | --- |
| I201 | info | Proposed (not yet in interface spec v0.1) fields are present: `cohort`, `placeholder`, `generator`, `scenario_info`, `params_used`, `Clinician_Start/Stop/Reset`. |
| I202 | info | `placeholder = true`: the file is development scaffolding, not an output of the NERAM twin or controller. |
