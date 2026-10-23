# Sai → team handoffs (ready to send, 18 Oct 2026)

Plan references: 4D (announce every shared-config change), 4T (hand-offs), 9.6 (checkpoints). None of these has been
sent yet; Sai sends them. Nothing here changes another owner's files.

---
## 1. To everyone — params.json v0.2 (plan 4D)
> `config/params.json` is now **v0.2** (spec_version unchanged, 0.1). Only Sai-owned rows changed; no Suchita or
> Shreehan row was touched.
> * Placeholders (value stays null, status unchanged, labelled "SYNTHETIC DEMO placeholder"): p_trigger 0.5,
>   p_release 0.4, n_confirm_updates 2, sd_degrade_degC 0.25, k_heat_degC_per_h 2.0, tau_heat_min 10, w_ch 0.25×4,
>   r_obs_degC2 0.001. These are the values the synthetic replays were already built with.
> * New TBD rows for the passive plant (plan §6): plant_passive_alpha_degC, _beta_degC_per_h, _gamma_per_min,
>   _u0_degC, _q_degC2_per_min, with synthetic-verification placeholders.
> * **t_target_degC stays null** (clinician input; never invented in project config).
> * Read values by name from params.json. Do not hard-code them. The changelog is inside the file.

## 2. To Suchita (controller) — plan 1N, 1S, 4T, CP3
> 1. **TC05** (`ctrl_TC05.csv`, 7381e4d3…): t_s 600–610 is CLINICIAN_WARMING with Heat_1..4 = 0 and Demand_Global = 0,
>    then TARGET_REACHED at 611. TC05 requires "Heat set by PI, not fixed 100 %", so please re-run it with a non-zero
>    PI output.
> 2. **TC13** (`ctrl_TC13.csv`, c1bef0c8…): PREDICTIVE_WARMING at t_s 70–80 and 641–651 with all Heat = 0, which fails
>    TC02's 0 < Heat_i ≤ d_pred_max_pct. The degraded part (300–629, TWIN_RECOVERED at 630) is fine. Please send the
>    **twin input file** you drove it with: no offset of twin_SYN_SCN_D reproduces it.
> 3. **Log format (§1S):** please drop `HW_Heartbeat_s` and `HW_Fault_Code` from the logged columns (they are HW→Ctrl
>    inputs, not log columns) and order the module temperatures 1_A, 1_B, 2_A, 2_B, … as in §1S. Missing values: NaN.
> 4. **New twin inputs to re-run TC01–TC03, TC05 and TC13 on:** `integration/twin_outputs/twin_SYN_01..04.csv`
>    (canonical NERAM filter, ASSUMED_SYNTHETIC parameters). SYN_01 = usual care, SYN_02 = cooling, SYN_03 = outlier
>    at min 40 + level shift at min 60, SYN_04 = gap at min 45–60, DEGRADED from 50 to 69.
> 5. **Needed for the demo:** one predictive-warming log with real (non-zero) heat on twin_SYN_02, plus TC13 on
>    twin_SYN_04. With those I can replace the stand-in SCN_B / SCN_D replays, which removes the "SYNTHETIC
>    STAND-IN" badge.
> 6. **Plant:** use the plant_passive_* and assumed-warming rows of params.json v0.2 (ASSUMED, sensitivity ×0.5 / ×1 / ×2).
> TC07 (b3f7ce8d…) is integrated as SYN_TC07 and verified in Unity (shutdown at 200 s, CH2 code 206, latched).
> It shows no reset/release; if you have a TC07 run with cooling, RESET_BLOCKED and release, please send it.

## 3. To Shreehan (hardware, README, audit) — plan 3, 7, 8
> 1. **`hardware/interfaces/fault_codes.csv`**, header exactly `code,name,scope,detected_by,description,display_text`.
>    Channel codes are 100·ch + k (e.g. 206 = CH2 OVERTEMP_SW); system codes 0–19. Until it arrives the viewer
>    shows "FAULT TEXT TBD".
> 2. **Your params.json rows:** t_mod_trip_degC, t_mod_reset_degC, t_hw_cutoff_degC, t_surface_limit_degC (they are
>    TBD; the viewer shows no invented limit).
> 3. **README:** merge `docs/README_SAI_SECTIONS.md` (§1, 4–8, 12–16) and keep the title exactly as written there.
> 4. **Repository:** please create the GitHub repo (or send me the URL) with LICENSE, CITATION.cff, .gitignore
>    (exclude unity_editor/Library, Temp, Logs, UserSettings, build/, vitaldb_bt_cache/, code4_outputs/,
>    final_holdout_freeze/, any case-level CSV) and .gitattributes (LFS for *.fbx, *.png, *.pdf, *.jsonl.gz).
>    I have to commit docs/PREREGISTRATION_dev.md there **before** the development fit.
> 5. **Power budget:** the development-case duration median/P90 comes from Colab (runbook Cell 7); I'll send it
>    as soon as it has run.

## 4. To Neharikaa (CAD) — plan 2, 4P; full spec in docs/unity/CAD_INTEGRATION.md
> 1. **FBX exports:** metres, Y up, origin = table-top centre, +Z toward the head (patient's left = +X). Object
>    names per the CAD contract: `Left_Hand_Module` (children CH1_Liner … CH1_Heater …), the other three modules,
>    `Bedside_Controller` (BC_Enclosure, BC_Display, BC_LED_CH1…4, BC_Button_Start/Stop/Reset, …). Each object placed in
>    this frame; scale is checked against `Reference_Cube_1m` in the scene (1 m edge).
> 2. **`cad/exploded_offsets.csv`** with columns `object,dx_m,dy_m,dz_m` (metres), one row per top-level object.
> 3. Send them and I integrate them with NERAM → CAD → Integrate selected CAD models. Until then the viewer uses
>    labelled placeholder geometry.

---
## 5. To Suchita — after her v2 package (18 Oct 2026) — replaces section 2 items 1–3
> Thanks — the v2 package fixes everything I flagged: TC05 now heats by PI, TC13's predictive episodes heat, TC07 has the
> full RESET_BLOCKED → RESET cycle, and the module temperatures are interleaved. Logs filed with hashes in
> integration/controller_logs_received/2026-10-18/. To put them in the Unity demo I need:
> 1. **The twin input you drove each test with** (per test, 1 row per minute or per second): T_twin_s, T_obs, T_est,
>    T_est_sd, T_pred_20/30/60, P_below_hypo_20/30/60, Twin_Valid. Your testbench already has these. Without them the
>    viewer would show a twin that contradicts your controller.
>    — or — re-run SYN_02, TC05 and TC13 on my files integration/twin_outputs/twin_SYN_02 / _01 / _04.csv (plan CP0).
> 2. **ctrl_TC04.csv** (recovery) — the plan lists it for the demo; it was not in the package.
> 3. **Re-run with config/params.json v0.3** (attached): your 15 rows are now in it exactly as in your spec; your code
>    picks the file up automatically. Two of my rows differ from your standalone table (p_trigger 0.5 / p_release 0.4,
>    k_heat 2.0 °C/h, tau_heat 10 min, r_obs 0.001); please use the file values so the twin, controller and replays agree.
>    Shreehan's rows stay null in the file (your numbers came from the old script); keep them as test-only placeholders.
> 4. **Slide fix:** slide_architecture shows a leftover matplotlib axis (0–160 ticks, stray "0" labels) and the
>    transition footnotes overlap the caption line; please re-export without the axes.
> 5. **Log columns:** HW_Heartbeat_s and HW_Fault_Code are still logged; §1S does not list them (harmless — my builder
>    accepts them with a flag — but please drop them or tell me to add them to §1S).
