# Audit trail (owner: Sai)

## 1. Canonical scripts (SHA-256; reverified 18 Oct 2026 against EXPECTED_SHA256 and `neram_recovery_v3/canonical_scripts/SHA256SUMS`)
| Script | SHA-256 | Repository location |
|---|---|---|
| thermal_robust_core.py | de9c6c6378301ddd6e9378cfd3d5671a97fc68cc79a190a978033aa4161ad2c5 | src/ |
| development_model_adequacy.py | d131c745794b3f6807f71121b126588fce375821f7451952885601aa66c580ef | analysis/ |
| development_event_forensics.py | 4f39b93092b9554a77be32da1771807f6bda2102e532672bcb30889e1f5b4063 | analysis/ |
| dev_robust_01_fetch_case_metadata.py | 584d6741b5961978073a39cc9dd1c3883c70f00d4e76e8890568de9954a1a8ae | analysis/ |
| dev_robust_02_fit_and_validate.py (v1) | ab4a251bdc11c7b1d3bc7e48ae465720f6a91007d20992d29418969b991a8938 | analysis/ |
| dev_robust_03_apply_preregistered_rules.py | 0f4b58be36d7ff2ec93332f028a9a57ca682dc13d547b8a92830349446c36a91 | analysis/ |
| robust_statespace_verification.py | 20a1789a6cdba40224b52259e1c1c11b7a632df87438dce254129f6089a03d60 | tests/ |
| recovery_resume.py | f713e28d7ea0c5fb5747d09f4b440890e5a345b7c158f401ca70244e82276012 | tests/ |
| dev_robust_02_fit_and_validate_v2.py (proposed, NOT approved) | c02e5de85240d3cb47f30b06820ed3b404a0883134512a1a47fd9aa682a6339f | neram_recovery_v3.zip only |
| neram_recover.py (helper v3) | f86bd71b501674d2c4b8838d059e601a004e675fa074063cbc52609a66de835c | neram_recovery_v3.zip only |
| neram_recovery_v3.zip | 49b8c065386bab9d8c3629ce4fee56bf64814e8542b192b759ca2173a4f6aa05 | Downloads |

None of the canonical scripts was modified; the copies in `analysis/` and `tests/` are byte-identical.

**Missing from this computer** (plan §7): the Code 1–4 scripts and `freeze_final_holdout.py`
(see analysis/README.md).

## 2. Development pipeline (plan 4B) — status
| # | Step | Status | Evidence |
|---|---|---|---|
| 1 | Restore code4_outputs/ and final_holdout_freeze/ | Done (earlier session) | byte-verified copy; holdout hash prefix 2d9235a38706e151 |
| 2 | Rebuild vitaldb_bt_cache/ (development only) | Done earlier; 4,456 tracks, 0 holdout | ROOT_CAUSE.md "Uploaded Drive backup" |
| 3 | development_model_adequacy.py | Done earlier (MODEL_DECISION B) | earlier Colab log |
| 4 | development_event_forensics.py | Done earlier | earlier Colab log |
| 5 | Core self-test | PASS, rerun 17 Oct in cloud (mean err 5.7e-14, var err 1.8e-13) | this session |
| 6–7 | recovery_resume.py, robust_statespace_verification.py | Passed earlier (synthetic) | helper "SYNTHETIC CHECKS PASS" |
| 8 | dev_robust_01 metadata | Done earlier (4,456 rows) | ROOT_CAUSE.md |
| 9 | Record dev_robust_03 hash, then push | Hash recorded in docs/PREREGISTRATION_dev.md. **The push is NOT done** (no Git repository yet) | — |
| 10 | dev_robust_02 | **FAILED** (v1): quantised likelihood at the bounds, 161 empty cases → NaN S → +∞ NLL → LinAlgError | ROOT_CAUSE.md; DIAGNOSTIC_OUTPUT_2026-10-09.txt |
| 10b | v2 correction C1–C4 | Written; **awaiting approval**; NOT RUN | docs/FIT_DECISION_BRIEF.md |
| 11 | dev_robust_03 | NOT RUN (needs step 10 outputs) | — |
| 12 | Backups and aggregate results | NOT RUN | docs/COLAB_DEV_FIT_RUNBOOK.md |

These steps cannot run in the laptop workspace or the cloud workspace: there is no Colab, Drive or development
cache. No result was fabricated.

## 3. Change history in the v4 workspace (`D:\Unity\Projects\NERAM_v4_test\NERAM_Unity_Workspace_v4`, not a Git repository)
Originals of every modified file are in `_sai_backup_2026-10-17/`:
* `integration/build_replay.py`
* `config/unity_scenarios.json` and its StreamingAssets copy
* `tools/verify_workspace_v3.py`
* `config/params.json` v0.1 and its StreamingAssets copy (in `config_v0.1/`)

### 17 Oct (pass 1)
* **builder:** accepts HW_Heartbeat_s and HW_Fault_Code (not serialized).
* **Added:**
  * the twin export, `twin_SYN_01..04`, the twin validator, assumed warming and the semantic checker;
  * SYN_TC07, two test files and the documents.
* **Fixed:** the hard-coded replay count in `verify_workspace_v3.py`.

### 18 Oct (pass 2, against the full 71-page plan)
| Change | Reason (plan ref) |
|---|---|
| `src/twin_replay_export.py`: Twin_Valid uses **T_est_sd < sd_degrade** (was ≤) | 4A says "<" |
| Exporter reads t_hypo_degC and sd_degrade_degC from `config/params.json`; `twin_export_config.json` v0.2 keeps only the 20 / 10-of-15 rule constants | 0.3: one source of truth; nobody hard-codes a value that has a params row |
| `config/params.json` **v0.2**: placeholders for Sai-owned rows only (t_target 36.5, p_trigger 0.5, p_release 0.4, n_confirm 2, sd_degrade 0.25, k_heat 2.0, tau_heat 10, w_ch equal, r_obs 0.001), plus new TBD rows `plant_passive_*` (α, β, γ, u0, q). All values stay null. Changelog inside the file | §6 (plant_passive; "labelled placeholder for simulation"); 4T hand-off of plant_passive and assumed-warming values to Suchitha. Placeholders equal those the synthetic replays were already built with (tested) |
| `integration/build_replay.py`: HW_Heartbeat_s / HW_Fault_Code are now **refused by default** and accepted only with `--accept-ctrl-input-columns` | §1S lists the log columns, and these two are not in it |
| SYN_TC07 rebuilt with the flag; scenario_info and catalog limitations rewritten (fault 206 meaning, TC07 criteria not covered, §1S deviation) | truthfulness |
| Tests renamed or added per plan §7: `test_interface.py`, `test_replay_schema.py`, `test_p_below_hypo_mc.py` (the MC tests moved from test_twin_export.py), plus TC07 timing and strict-default tests | §7 |
| `analysis/` (5 canonical scripts) and `tests/` (2 canonical scripts): byte-identical copies | §7 file tree |
| `results/{development,final,figures}/` with READMEs; 4 SYNTHETIC-labelled figures | §7 |
| `docs/architecture.pdf` + `docs/architecture_src/architecture.html`; ARCHITECTURE.md rewritten | Box 9 |
| `docs/FIT_DECISION_BRIEF.md`, `docs/COLAB_DEV_FIT_RUNBOOK.md` (including duration statistics) | 4B, 4T |
| `tools/run_all_tests.py` (no pytest available on either machine), `tools/make_twin_syn_figures.py` | reproducibility |
| `environment.yml`: jsonschema added; imports listed | §7 |
| StreamingAssets re-synced (params.json v0.2, catalog, SYN_TC07) with the project's own sync tool | 4G |

**Deliberately unchanged:**
* the canonical core and the Colab scripts;
* Suchitha's logs (copies only, in `integration/controller_logs_received/`);
* all Unity scenes, C# scripts, UXML/USS and EditMode tests. Static review found the plan's §4H–4P features
  already implemented; see SAI_REMAINING_WORK_AUDIT §D;
* v4's synthetic generator and its 10 replays (byte-identical);
* `interface_spec.csv` and `enums.json` (verified against the plan, no change needed);
* other owners' params rows;
* the holdout.

## 4. Test runs (18 Oct 2026)
| Command | Environment | Result |
|---|---|---|
| `python tools/run_all_tests.py` | laptop VM, Python 3.10.12, no scipy/jsonschema | test_controller_log_integration 9/9 PASS · test_interface 8/8 PASS · test_unity_ui_contract PASS (STATIC) · test_validate_replay 62 fixtures PASS · test_p_below_hypo_mc **BLOCKED** (scipy) · test_twin_export **BLOCKED** (scipy) · test_replay_schema **BLOCKED** (jsonschema) |
| `python tools/run_all_tests.py` | cloud workspace, Python 3.13.16, numpy 2.5.3, scipy 1.18.1, jsonschema 4.26.0 | test_controller_log_integration 9/9 · test_interface 8/8 · test_p_below_hypo_mc 4/4 · test_replay_schema 2/2 · test_twin_export 9/9: all PASS |
| `python tools/gen_replay_schema.py --check` | laptop VM | PASS (up to date) |
| `python tools/make_synthetic_replays.py --check` | laptop VM | PASS (byte-identical) |
| `python tools/make_twin_syn_outputs.py --check` | cloud | PASS (byte-identical) |
| `python integration/validate_replay.py` (11 integration + 11 StreamingAssets) | laptop VM | 22 VALID, 0 errors; SYN_TC07 301 × W108 (expected) |
| `python integration/validate_twin_output.py` (14 twin CSVs) | laptop VM | 14 VALID |
| `python tools/check_replay_semantics.py integration/replays/*` | laptop VM | 11 SEMANTIC_OK |
| `python tools/sync_unity_streaming_assets.py --check` | laptop, real workspace | in sync (fault_codes.csv and exploded_offsets.csv not delivered) |
| `python tools/verify_workspace_v3.py` | laptop VM copy | 102 PASS. 2 FAIL, both artefacts of the check: "stale scene" (the Editor-generated scene exists on this machine; the check targets a shipped ZIP) and "previews" (the test copy excluded docs/previews; the real workspace has 9) |
| `python -m compileall` (integration tools tests src analysis) | laptop VM | PASS |
| Unity Editor setup, EditMode tests, Play mode | — | superseded by §6 (run on 18 Oct) |
| Development fit | — | **BLOCKED** (Colab and Drive) |

## 5. Replay inventory (SHA-256; integration/replays = StreamingAssets/replays, byte-compared)
| File | SHA-256 |
|---|---|
| SYN_ENG_01.jsonl.gz | 665a38999c5a48300808697f2a6bf5fee5ca23425be64d42ded33891fd5eab16 |
| SYN_ENG_02.jsonl.gz | 4be7f24f24d29be4b58b744f928a88ef944bc9b8719e1f443ddd8dfdfd302594 |
| SYN_ENG_03.jsonl.gz | 3bbc7e3bffa31c371d06241dc7e7e33a04f9730241bc6d6371c6d7d7619a62e1 |
| SYN_ENG_04.jsonl.gz | 5bfb5aa12008d84060080902f64f07ff3133b8026c3586f02ab1eb07d0b6338f |
| SYN_ENG_05.jsonl.gz | 08f345bc2e76aa51f773f928a619ccc5b098d3f1f7ca1878fefa89124c83870e |
| SYN_ENG_06.jsonl.gz | 85ca6f043538d1dec1c3ca13af5c388a4717ad5026b54e613ac26f14a4d4869c |
| SYN_SCN_A0.jsonl.gz | 8ab6623bceca7f762f8f6a9cad633b3200bfde1303967c014c8c31483ac656aa |
| SYN_SCN_B.jsonl.gz | 645db8618e00b76190da63266fdd0060d453bc2b1b21c4d9c94d705cc5fbf9cd |
| SYN_SCN_C.jsonl.gz | 0cb35a081a8c39ba8dddbf47ea9b38531616dc9ab1a8422b8dbeb556135ac7ed |
| SYN_SCN_D.jsonl.gz | a87ab246b37451bfba8f47e488dddb1726d947ee4001f653bb21d5e0d99788e2 |
| SYN_TC07.jsonl.gz | 7714f8a8895e2ff90144e10ec567e31350254e4ba92f8071950e448b7976a6ea (rebuilt 18 Oct; previous a16155bb… kept in _sai_backup_2026-10-17/unity_2026-10-18/) |

## 6. Pass 3 — Unity Editor session on the laptop (18 Oct 2026, 00:30–01:40 IST, Unity 6000.3.26f1, project `unity_editor/`)
| Check (run in the Editor by computer control) | Result |
|---|---|
| NERAM → 2 Sync config + replays | PASS (copied params.json, SYN_TC07; fault_codes.csv and exploded_offsets.csv not delivered) |
| NERAM → 4 Validate project | PASS |
| EditMode, before fixes | **FAIL** 82 pass / 4 fail / 1 skip (3 caused by params v0.2 t_target placeholder; 1 pre-existing StrictJson 1e400 defect) |
| EditMode, final code | **PASS** 86 pass / 0 fail / 1 skipped (`GeneratedFieldTableMatchesReplayFieldsJson` ignores itself: unity/schema is one level above unity_editor in this layout; the same check passes in Python via gen_replay_schema.py --check). XML: docs/evidence/unity_editmode_TestResults_2026-10-18_final.xml |
| Play: SYN_SCN_B (THEATRE, MONITOR, FULL ANALYSIS, 1× and 60×) | PASS (visual) |
| Play: SYN_TC07 shutdown/latch (Safety jump, all three screens) | PASS (visual), see SCENARIO_TRUTH_TABLE |
| Play: SYN_SCN_D degraded twin | NOT RUN this session (passed in Editor/build on 10 Oct) |
| Windows player rebuild (NERAM → 6) | see §7 |
| Python, laptop VM (no scipy/jsonschema) | controller_log_integration 9/9, interface 8/8, unity_ui_contract, validate_replay: PASS; 3 files BLOCKED (scipy/jsonschema) |

Fixes in pass 3 (originals in `_sai_backup_2026-10-17/unity_2026-10-18/`):
* `config/params.json`: t_target_degC placeholder removed again (clinical value; never invented in project config). Changelog entry added.
* `Assets/Scripts/Core/StrictJson.cs`: numbers outside the double range (1e400) now read as ±Infinity / 0 like Python json.loads, after the strict syntax check; E011 then rejects them per field.
* SYN_TC07 rebuilt without `--placeholder` (it is canonical NERAM twin + Suchitha's real log, so the "NOT NERAM TWIN OR CONTROLLER OUTPUT" watermark was false) and with a 2-value params_used snapshot (t_hypo 36.0, sd_degrade 0.25 — the values twin_SYN_01 was computed with). `integration/scenario_info/SYN_TC07_params_used.json` added.
* Header / overlay polish at 1366×768 (NeramApp.cs, HeaderStatus.cs, NeramMain.uxml, neram.uss): short chips (PLACEHOLDER, FAULT TEXT TBD) with full-text tooltips; duplicate "1 config warning" chip for the missing fault table removed; status line "Ctrl … · Twin …" (full text in tooltip); watermark is a solid readable badge "SYNTHETIC STAND-IN DATA · NOT NERAM TWIN / CONTROLLER OUTPUT"; redundant header "ASSUMED / SIMULATED" badge hidden (footer + panel tags carry it); FULL ANALYSIS cards opaque (3D chips no longer bleed through); channel table spacing; graph C bottom legend hidden in FULL ANALYSIS (channel names are inside the plot).
* tests: test_interface.py (t_target exception), test_controller_log_integration.py (SYN_TC07 not placeholder; reproducible with the new arguments).

Known, not fixed: the Editor Game view at 0.81× crops the bottom ~4 px of the footer (Editor display scale, not layout; check in the built player). A transient "Failed to create CoreCLR (0x80004005)" from Unity.ILPP.Trigger.exe was cleared by restarting the Editor.

## 7. Windows player rebuilt (18 Oct 2026, ~01:35 IST)
* NERAM → 6 Build Windows player: success, `build/NERAM_Windows/NERAM.exe`, 147.1 MB, 109 s (incremental).
* The build's StreamingAssets SYN_TC07 is byte-identical to `integration/replays/SYN_TC07.jsonl.gz` (7714f8a8…); params.json and StreamingAssets copies identical; `sync_unity_streaming_assets.py --check`: in sync.
* Running the built player was **NOT RUN** by Claude (the player window cannot be granted to computer control). Manual check: run NERAM.exe, confirm the footer disclaimer is fully visible at the bottom edge and the header chips are whole.
* Canonical core hash rechecked: de9c6c63… (unchanged).

## 8. Desktop app identity (18 Oct 2026, ~02:00 IST) — source changed, player NOT yet rebuilt
* `Assets/Settings/neram_app_icon.png` (new, 256×256, drawn from the project's Inter font; no third-party artwork).
* `Editor/NeramBuild.cs`: player opens as a **maximised desktop window** (title bar, taskbar icon, pinnable) instead of borderless fullscreen; the NERAM icon is applied on every build. F11 / FULLSCREEN still toggle fullscreen.
* `Scripts/NeramWindowMode.cs` (new): the built player always starts maximised-windowed even if a previous run was left fullscreen.
* `Scripts/NeramApp.cs`: fullscreen toggle returns to the maximised window.
* Unity crashed with "Could not allocate memory: System out of memory" when the rebuild started (laptop RAM exhausted); the rebuild must be repeated: NERAM → 6.

## 9. Menu redesign + user guide (18 Oct 2026, ~10:15 IST)
* `Scripts/UI/ParametersPanel.cs`: default view = 16 key parameters in 6 plain-language groups (patient temperature, digital twin, predictive trigger, controller, assumed warming, hardware safety), each with SET / PLACEHOLDER / NOT SET YET / ASSUMED and who supplies the real value; summary tiles; the complete audit table is kept behind "All parameters (advanced)".
* `Scripts/UI/DiagnosticsPanel.cs`: default view = status tiles (file valid, length, twin updates), source of each stream, "still placeholders — and who replaces them", file checks; the previous full view is behind "Technical details".
* `neram.uss`: styles for both (kp-*, dg-*); advanced table status chips no longer overlap the owner column.
* Compiled 0 errors / 0 warnings; checked in Play mode; tests/test_unity_ui_contract.py ALL PASS; Windows player rebuilt (147.1 MB). EditMode suite not re-run after this UI-only change.
* `docs/NERAM_Viewer_User_Guide.pdf` (14 pages, screenshots from the Editor) — plain-language guide to every screen.
* Originals: `_sai_backup_2026-10-17/unity_2026-10-18/` (ParametersPanel.cs, DiagnosticsPanel.cs). No files deleted.

## 10. Suchitha's controller package v2 integrated (18 Oct 2026, ~11:00 IST)
* Received: README, controller_spec.md, test_results.csv (TC01–TC18 PASS, TC19 BLOCKED, TC20 EXCLUDED), requirements_traceability.csv, audit_checks.csv, 5 logs, demo_controller.mp4 (141 s), 5 figures. Copied read-only with SHA256SUMS to integration/controller_logs_received/2026-10-18/.
* Verified from the rows: no warming with zero heat, no heat in SAFETY_SHUTDOWN, 1 Hz continuous; previous TC05/TC07/TC13 findings resolved.
* config/params.json **v0.3**: Suchitha's 10 PROVISIONAL rows set to her values, 6 ASSUMED test-bench rows given her placeholders; data_stale_twin_s placeholder 120 s (Sai). Shreehan rows unchanged. Synced to StreamingAssets (sync tool) and copied into build/NERAM_Windows (no rebuild needed). test_interface 8/8 PASS.
* Unity replays from the v2 logs: NOT BUILT — the twin input she used is not in the logs (see SCENARIO_TRUTH_TABLE §5). Hand-off in TEAM_HANDOFFS_SAI.md §5.
* No files deleted.

## 11. Neharika's CAD in the viewer (Sai, 2026-10-18)
- Source: Neharika's 4 Fusion FBX (received 18 Oct). Unity prep (metres, Y up, plan V/W names, MAT_* materials, plan pivots, controller decimated 19,890 -> 12,748 tris) by `cad/tools/fixneha.py` in the team repo; report in the repo `cad/IMPORT_CHECK_SAI_2026-10-18.md`.
- Unity: 6 FBX in `Assets/NERAM_CAD/`; `Editor/NeramCadPlacement.cs` (NERAM > CAD > Place Neharika CAD on the mannequin) poses them from the stand-ins and runs automatically after a scene rebuild; `Editor/NeramCadSnapshots.cs` writes `docs/evidence/cad_unity/*.png`.
- The stand-in mitts/boots enclosed the hands/feet, so the mannequin had none; `tools/gen_cad_body_parts.py` generates hand/foot skin from the same SDF shapes (`Assets/NERAM_Generated/MeshData/cad_body_parts.json`, visual stand-in).
- `StreamingAssets/cad/exploded_offsets.csv`: Sai default by layer order (visual only) until Neharika supplies hers.
- Validator: `CHn_Cutoff` optional (plan W brackets it); a CAD module without `CHn_Strain_Relief` is a WARN naming the part. NERAM > 4 Validate: PASSED. Windows player rebuilt.

## 12. CAD fit v2: gloves, feet, watch, controller (Sai, 18 Oct 2026, ~16:00 IST)
- Builds on the fit pipeline added at ~12:30 IST (`tools/gen_cad_fit.py`, `_automation/` queue, raised arm boards, reshaped wrists, rail-mounted controller). That version's originals: `_sai_backup_2026-10-17/unity_2026-10-18/cad_fit_v1_before_v2/`.
- Hands: anatomical palm-up hand built from the medial axis of the glove liner outline (one rounded finger under every glove finger, flattened palm), back of the hand on the board. Neharika's pad layers (liner, heater, insulation, shell, sensors) subdivided and draped onto the hand with the edges folded around the fingers (visual fit of a fabric pad).
- Straps (hands and feet): rebuilt as bands following the limb + pad cross-section at the CAD strap position (CAD width/thickness kept, length fitted); closure tabs lie on the band. Visual fit - Neharika's CAD straps enclose a 29 mm limb.
- Feet: adult toe lengths (big toe ~3 cm), sole pad heel-to-ball, toes free.
- Controller: lit display quad with `controller_screen.png` (channel names + SIMULATED; values stay on the dashboard, like the watch face); cables re-routed under the rail/table and onto the boards/table at each pad.
- New/changed files: `tools/gen_cad_fit.py` (v2), `tools/cadfit_lib.py`, `tools/fbxio.py`, `tools/meshgen/textures.py` (controller_screen), `Editor/NeramCadPlacement.cs` (fitted part meshes + texture material), `Assets/NERAM_Generated/MeshData/cad_fit.json`, `Assets/NERAM_Generated/Textures/controller_screen.png`.
- Checks: NERAM validation PASSED (98 PASS, 10 WARN = stand-ins / missing strain relief); EditMode tests 86 pass, 0 fail, 1 skip; Windows player rebuilt (159.3 MB). Evidence: `docs/evidence/cad_unity_v2/`. No files deleted.
