# Phase 0 — Specification audit for the Unity layer

Inputs audited: *NERAM — Team Implementation Plan* (§0 rules, §1 Suchitha, §2 Neharika, §3 Shreehan, §4 Sai + Unity, §5 interface spec, §6 parameter table, §7 file tree), `config/interface_spec.csv` (78 rows), `config/params.json` (51 parameters), `config/enums.json` v0.1.

Status legend: **OK** consistent · **GAP** something Unity needs is not specified · **CONFLICT** two sources disagree · **PROPOSED** Unity-side proposal awaiting team sign-off.

## A. Hard rules carried into the Unity design

| Rule (plan §0 / user brief) | How the Unity layer enforces it |
|---|---|
| Signal is the "patient temperature signal", never "core temperature" | Labels, tooltips, UXML, docs; `tests/test_unity_ui_contract.py` wording guard; replay header test (only the negation "not core temperature" is allowed). |
| Every warming effect = SIMULATED / ASSUMED PROTOTYPE RESPONSE | `plant` group must carry source tag `ASSUMED` (E050); open loop forbids any warming effect (E061); comparison curve labelled ASSUMED; forecast label "Forecast under ASSUMED warming" whenever the twin is in the loop. |
| Controller = SIMULATED + CLINICIAN-SUPERVISED PROTOTYPE | `ctrl` and `hw` source tags must be `SIMULATED` (E050); banner and inspector say so; no autonomy / prevention / validation / certification wording (wording guard). |
| No manufactured constants / thresholds / limits / ratings | Unity contains **no** clinical or hardware value. Thresholds shown come from `params.json` (TBD params have no value) or from a replay header `params_used` snapshot, always with their status. Display-only settings live in `config/unity_display.json` and are labelled display-only. |
| Final holdout never in Unity | Required header `cohort` ∈ {SYNTHETIC, DEVELOPMENT} (E052/E053); REAL_DEV observations require DEVELOPMENT (E051); `build_replay.py` refuses holdout case ids; the StreamingAssets sync validates before copying; tests assert every shipped replay's cohort. |
| Unity is not the model / controller / simulator | No state machine, no twin, no physiology in C#. `Neram.Core` only parses, validates and formats. Display rules (forecast visibility, banner text, channel display status) read replayed values; they never decide controller behaviour. |
| Missing ≠ 0 | Columnar table stores `NaN` for `null`; formatters print "—"; the chart draws a missing-observation strip and never interpolates across gaps. |

## B. Findings

| # | Type | Finding | Resolution in this build | Owner / action |
|---|---|---|---|---|
| 1 | CONFLICT | `Data_Stale_Twin`, `Data_Stale_HW` are in interface spec rows (Replay = yes) but not in the §4F replay field list. | Included in the schema as **optional** ctrl fields; banner chips appear only if present. | Suchitha: confirm they are logged; Sai: add to §4F. |
| 2 | GAP | Clinician START/STOP/RESET presses are not logged as fields; only inferable from `Trigger_Reason` / `Alert`. | **PROPOSED** optional `Clinician_Start/Stop/Reset` (bool, ctrl). Without them, presses are *inferred* and the event log says "inferred". | Suchitha: log the button inputs (they exist in the Stateflow model as inputs). |
| 3 | GAP | Replay header has no field stating data origin → holdout cannot be guarded mechanically. | **PROPOSED** required `cohort`; optional `placeholder`, `generator`, `scenario_info`, `params_used`. Reported as I201. | Sai: adopt in §4G. |
| 4 | GAP | `TWIN_DEGRADED.CLINICIAN_FIXED` has no specified display text. | Message: "Twin unreliable — clinician fixed demand only; no autonomous warming" (MONITOR substate: "Twin unreliable — monitoring only"). | Suchitha/Sai: confirm wording. |
| 5 | GAP | `t_target_degC` is TBD with no value. | Target line hidden unless the replay's `params_used` provides a value; synthetic replays use 36.5 marked **SYNTHETIC DEMO placeholder, TBD**. | Sai (clinical source required). |
| 6 | GAP | `t_hypo_degC` placeholder 36.0 is the core-temperature convention; applicability to this signal is unresolved. | Shown with status TBD and the note "applicability to this signal unresolved"; the indicator says "display banding only, not a clinical classification". | Sai. |
| 7 | GAP | `hardware/interfaces/fault_codes.csv` does not exist yet. | Plan-derived **PLACEHOLDER** table (53 codes) with a visible warning chip; unknown codes are shown as "Unknown fault code N (not in <table>)", never given a meaning. | Shreehan: deliver CSV (`code,name,scope,detected_by,description,display_text`). |
| 8 | GAP | Enum integers in `enums.json` v0.1 are PROVISIONAL; names are FROZEN. | Unity resolves by **name** at load (`ReplaySession`), so renumbering needs only a config change. | Suchitha: freeze integers with the Stateflow enum definition. |
| 9 | GAP | No CAD coordinate frame was specified. | Contract: metres, Y up, origin = table-top centre, +Z toward the head, patient supine ⇒ **patient's left = +X** (Unity left-handed). Placeholder scene follows it. | Neharika: export in this frame (CAD_INTEGRATION.md). |
| 10 | GAP | No exploded-view offsets. | Optional `cad/exploded_offsets.csv` (`object,dx_m,dy_m,dz_m`); visual defaults otherwise. | Neharika (optional). |
| 11 | CHECK | Schema hard range `T_obs` 25–43 °C (E013) is a replay plausibility bound, not a clinical value. | Kept as validation-only. | Sai: must equal the Code 4 BT validity filter; change in `unity/schema/replay_fields.json` + regenerate if different. |
| 12 | OK | `ts_twin_s` = 60 FROZEN, `ts_ctrl_s` = 1 PROVISIONAL. | Clock is frame-based (1 frame per controller step); twin minute buckets use `ts_twin_s`. | — |
| 13 | OK | Forecast "NaN unless VALID" (interface spec). | Enforced by validator (E040/E041) and by the display rule (hidden unless VALID and not TWIN_DEGRADED). | — |
| 14 | CHECK | `Heat_i` unit: % (0–100). | Validator range 0–100; glow = Heat_i/100. | Suchitha: confirm unit (not 0–1). |
| 15 | GAP | No team data for SCN_A–D yet. | Catalogue lists them as "awaiting data"; SYN_* placeholders (cohort SYNTHETIC, `placeholder = true`, banner "SYNTHETIC PLACEHOLDER DATA") exercise every view. | Sai + Suchitha (REPLAY_INTEGRATION.md). |

## C. Rejected requests / scope decisions
* **Live fault injection in Unity** — would require Unity to compute the controller response (a re-implementation of Stateflow). Rejected; faults are demonstrated by replaying Suchitha's test-case logs (TC07, TC13, …).
* **Body heat map** — the twin has no spatial temperature field; drawing one would invent physiology. Replaced by a single thermal-state indicator.
* **Interpolating missing observations** — would fabricate data. Missing samples are drawn as gaps plus a strip.
* **"Before/after" benefit claims** — the only comparison offered is the replayed plant trajectory vs the replayed ASSUMED no-warming trajectory (`T_plant − dT_heat`, both from the file), labelled SIMULATED/ASSUMED, available only when the replay has a plant group.
