# Verification report — NERAM_Unity_Workspace_Final (viewer / setup v3.1.0)

Date: 2026-10-10.

**Status values.**
* **PASS** — seen working, with the evidence named in the row.
* **FAIL** — seen not working.
* **NOT TESTED** — not checked in the environment that the claim needs.

**Where each check ran.**
* **Unity.** Your laptop: Windows, Unity **6000.3.26f1**, URP 17.3, Input System 1.20. The project copy was `D:\Unity\Projects\NERAM_Final_test\NERAM_Unity_Workspace_Final\unity_editor`, extracted from this release and kept in sync with it file by file. The scripts, Editor scripts, UI and tests (155 files) were confirmed identical by SHA-256 before the final runs. It was operated through remote screen control in the Editor's Play mode, Game view Full HD 1920×1080, and in the standalone player.
* **Standalone.** `build\NERAM_Windows\NERAM.exe`, built from that project and run on the same laptop. The display was 1366×768, which gives a 1594×900 logical layout.
* **Off-Unity.** A Linux container with .NET 8 and Python 3. A stub compile does not prove Unity behaviour, so those rows say *off-Unity*.

## 1. Checklist

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Project imports and compiles in Unity 6000.3.26f1 | **PASS** | Editor.log shows no `error CS` after each change, including the final scripts. Two recompiles after the forecast fixes were clean. |
| 2 | Full setup and validation | **PASS** | Setup: "NERAM setup v3.1.0 complete. Validation PASSED". **NERAM → 4. Validate project** after the last changes: `=== 94 PASS, 13 WARN, 0 FAIL ===` (2026-10-10 07:46 UTC). The 13 WARN lines are pending deliverables: CAD stand-ins ×11, `fault_codes.csv`, `exploded_offsets.csv`. |
| 3 | Workspace discovery from the extracted layout | **PASS** | The setup log reports the workspace root at the parent level of `unity_editor`. The clean-extraction check (§3) found the marker folders. |
| 4 | Scene references persist after an **Editor restart** | **PASS** | Unity was exited (File → Exit) and reopened from Unity Hub. The scene `NERAM_OR_Replay` opened with the dashboard drawn. On disk: `m_PanelSettings: {fileID: 11400000, guid: 540be120…}`, `sourceAsset: {fileID: 9197481963319205126, guid: 4758bb13…}`, `generatorVersion: 3.1.0`. Play mode after the restart loaded SYN_SCN_B normally. |
| 5 | Fresh launch starts at the beginning, **paused, 1×** | **PASS** | Editor: every Play session started at `PAUSED ×1 T+00:00:00`, frame 1, SYN_SCN_B. Standalone: both launches started the same way. Also covered by `LayoutAndStartupTests` (off-Unity). |
| 6 | Readable layout at **1920×1080** | **PASS** | Editor Game view Full HD: header, columns, pipeline, stage, charts, transport and footer all readable. Screenshots were inspected after each fix. |
| 7 | Readable layout at **1366×768** | **PASS** | Standalone fullscreen on the laptop display (1366×768): the same layout scaled to 0.853. Settings showed "Screen 1360×768 px · dashboard 1594×900 logical". The text is smaller but readable. |
| 8 | Readable layout at **1600×900** | **NOT TESTED** | Not run at exactly that size. It is the logical reference, so the layout is identical to rows 6 and 7 (Scale With Screen Size, match height), but this was not looked at on such a display. |
| 9 | Narrow / 16:10 screens: compact layout | **PASS** | In an earlier session of this release, the Editor Game view at 16:10 switched to the compact breakpoint with the region panel collapsed. The chart legends were then shortened. |
| 10 | Header regrouped and readable | **PASS** | Title, scenario and source chips, state, clock, FULLSCREEN and Capture all render. With four chips the last one can be clipped at 1600 logical px; the chip row has a tooltip listing every chip. In the standalone window all four chips were visible. |
| 11 | Always-visible values: temperature signal (site not established, not "core"), twin ± SD, controller / alert / fault / safety, CH1–CH4, quality, **HR · SpO₂ · MAP = N/A** | **PASS** | Seen in the left column in the Editor and the standalone, e.g. "36.15 °C · patient temperature signal · site not established" and "36.19 °C ± 0.050 °C (1 SD, as supplied)". The N/A row appears in the column's scroll area. |
| 12 | Chart A readable; gaps not interpolated; not called core temperature | **PASS** | Legend "T_obs · gap = no observation (not interpolated)"; subtitle "Measurement site not established · not core temperature". |
| 13 | **Chart B** readable | **PASS** | At T+21:00 in SYN_SCN_B: T_obs, T_est ± SD, t_hypo/t_target PLACEHOLDER lines, forecast whiskers and a compact one-row legend. The T_plant entries appear only with "ASSUMED compare" switched on. |
| 14 | Chart C readable; commands not called measured heating | **PASS** | Legend "CH1 L hand … CH4 R foot"; subtitle "Replayed heat commands (0–100 %) · not measured heating". |
| 15 | Fewer floating labels (Off / Compact / Detailed) | **PASS** | Compact by default ("CH3 18 %", "CTRL PREDICTIVE_WARMING"). The modes are in **Settings & view**. Clicking the CH1 label selected "LEFT HAND — CH1". |
| 16 | Sidebar closed by default; seven entries; one drawer at a time; `Esc` closes; replay and selection kept | **PASS** | Editor and standalone. Scenarios, Events, Parameters, All fields, Diagnostics, Sources & badges and Settings & view each opened alone. `Esc` closed drawer, then sidebar. Loading SYN_SCN_C from the drawer kept the LEFT HAND selection. |
| 17 | FULLSCREEN / EXIT FULLSCREEN (button and F11) | **PASS** (standalone) | Standalone: EXIT FULLSCREEN gave a window titled "NERAM Thermal Twin Viewer", with the button reading FULLSCREEN. F11 returned to fullscreen with the button reading EXIT FULLSCREEN, and F11 again gave the window. In the Editor the button shows an explanatory note, which is by design. |
| 18 | Presentation mode | **PASS** | `P` in the Editor (earlier session of this release): the region panel was hidden and the principal values, charts and transport were kept. Not re-checked in the standalone. |
| 19 | Standalone Windows build created | **PASS** | **NERAM → 6. Build Windows player**: "NERAM Windows player built: …\build\NERAM_Windows\NERAM.exe (147.0 MB, 861 s)". Rebuilt with the final UI fixes: 147.0 MB, 75 s. |
| 20 | Standalone runtime: controls and replay | **PASS** | Launched from the final build: SYN_SCN_B loaded and validated (7800 lines), and **Transition** jumped to T+00:21:00 with the forecast and region panel correct. With the first build: Space play/pause (T+21:00 → T+21:05), Free Roam (`R`, `W`, `Esc`), the sidebar and Settings, and chart A seeking all worked. |
| 21 | Play / pause / speed / step / restart | **PASS** | Editor: 10× playing, then paused at T+00:01:10. `>` stepped to T+00:01:11 and `\|<` returned to T+00:00:00. The jumps are in rows 22–23. |
| 22 | Event jumps (Transition, Safety) | **PASS** | SYN_SCN_B Transition → T+00:21:00, NORMAL → PREDICTIVE_WARMING. SYN_SCN_C Safety → T+00:46:00, "SAFETY SHUTDOWN — LATCHED". With no further event the strip reads "no further safety event". |
| 23 | Scenario switching | **PASS** | Scenarios drawer → "Over-temperature fault (synthetic)" (SYN_SCN_C): it loaded paused at T+0 and all panels updated. |
| 24 | Safety banner does not cover other panels | **PASS** | SYN_SCN_C at T+46:00: the banner sits above the controller banner and pipeline without overlap. The region panel's minimum height under the banner was lowered once more afterwards (150 px); that last value was not re-photographed. |
| 25 | Camera: Inspect, presets (`C`), Reset View, Free Roam | **PASS** | Earlier session of this release: C cycled presets to Wearable, Reset View worked, and Free Roam (R / W / Shift+D / Space / Esc) worked. Free Roam was re-checked in the standalone. |
| 26 | Region selection (hand, leg, wearable, controller) | **PASS** | Left hand (mitt and CH1 label), left leg, right hand, wearable and the bedside controller (box and CTRL label). Some remote clicks on the 3D view were dropped by the remote-control tool and repeated; see §2. |
| 27 | View modes External / Internal / Thermal / Exploded + Assemble | **PASS** | Internal: translucent body and legend "ILLUSTRATIVE ANATOMY — NOT PATIENT-SPECIFIC FLOW DATA". Thermal: uniform tint. Exploded CH3 and CH1: layers separated, with the toolbar compact and no overlap after the fix. **Assemble**: back to External with the selection kept. |
| 28 | Warming hardware and animations preserved | **PASS** | At T+21:00, all four modules glow amber at 18 %; the glow is driven only by `Heat_i`. Mitts, boots, watch, controller and IV prop are present. The vessel-pulse and IV-droplet animations were not watched while playing in this release. |
| 29 | Patient refinement (modest, in place) | **PASS** | The regenerated bundle was loaded by setup (708,062 triangles) and the patient is visible in every screenshot. BundleCheck: 78 PASS (off-Unity). |
| 30 | Scientific labelling and honesty rules | **PASS** | No "core temperature" label. HR, SpO₂ and MAP are N/A. Gaps are not interpolated. Commands are labelled as commands. T_plant is ASSUMED. Every shipped replay is SYNTHETIC with a placeholder watermark. Checked by `verify_workspace_v3.py` (103 PASS) and `test_unity_ui_contract.py` (23 PASS, wording guard). |
| 31 | No holdout data; Colab model, fitting code, rules and holdout untouched; Unity stays replay-driven | **PASS** | `config/`, `integration/` and `unity/schema/` are byte-identical to v3. The validator rejects non-SYNTHETIC/DEVELOPMENT cohorts (62/62 fixtures). Unity contains no thermal model or controller (`verify_workspace_v3.py`). |
| 32 | EditMode tests in Unity's Test Runner | **NOT TESTED** | The same test files ran off-Unity: **79 passed, 0 failed, 1 ignored**. They were not run inside Unity's Test Runner. |
| 33 | Clean extraction of the release ZIP and checks | **PASS** (off-Unity) | See §3. The ZIP was extracted to an empty temporary folder; structure, discovery markers, file hashes and every off-Unity check passed there. The ZIP itself was **not** re-extracted on the laptop: the Unity runs used the test copy, whose code is identical (row 1). |

## 2. Problems found in Unity during this release and how each was handled

| Found | Fix | Re-checked in Unity |
|---|---|---|
| Chart B legend took five rows and squeezed the plot | Short legend; T_plant entries only with the compare on | Yes |
| The CTRL world label cleared the selection | The label selects the controller | Yes |
| The safety banner covered the controller banner and pipeline | Offsets under `.with-safety` | Yes (SYN_SCN_C T+46:00) |
| The Exploded toolbar (CH1–CH4 + Assemble) overlapped the camera buttons | The toolbar hides its captions while Exploded is active | Yes |
| Horizontal scrollbar in the live-parameter column | `horizontal-scroller-visibility="Hidden"` | Yes |
| **The region panel collapsed when the forecast appeared** (SYN_SCN_B T+21:00). The long "NO-INTERVENTION FORECAST" title squeezed the source badge to zero width; its text wrapped one glyph per line and the title row grew about 200 px. | The badge keeps its width and the title wraps. The cards show one line per value (intervals to 0.1 °C) with the full values in a tooltip. The region panel has a minimum height. | Yes (Editor and standalone) |
| A USS re-import during Play mode detached the UI (`Dashboard tree was detached`) | This is the guard working. Exiting and re-entering Play mode fixes it; the step is in the handbook's troubleshooting table. | n/a |
| Some remote clicks were dropped, and keys go only to a focused Game view | Not a NERAM defect: the remote-control tool and the Editor's focus rule. Each such action was repeated and its outcome checked. | n/a |
| Opening the player through the remote tool while it was already running started a second instance | Not a NERAM defect. Both windows were closed. | n/a |

## 3. Clean extraction (off-Unity)

The values below are filled in from the final packaging run.

* ZIP: `NERAM_Unity_Workspace_Final.zip` — see `NERAM_Unity_Workspace_Final.zip.sha256` for the SHA-256.
* Extracted to an empty temporary folder. The tree has one top folder, `NERAM_Unity_Workspace_Final/`, containing `README_FIRST.md config docs integration tests tools unity unity_editor`. It has no `Library`, `Temp`, `Logs`, `UserSettings`, `build`, `bin`, `obj` or `__pycache__` folders.
* Every extracted file matches the source tree by SHA-256.
* The discovery markers (`config/enums.json` and `integration/replays/` next to `unity_editor/`) are present.
* Re-run inside the extracted copy: `test_validate_replay.py` 62/62 · `test_unity_ui_contract.py` ALL PASS · `verify_workspace_v3.py` ALL PASS · schema / synthetic / sync `--check` up to date · .NET tests 79 passed / 1 ignored · UnityCheck (Input System and legacy) 0 errors · BundleCheck ALL PASS.

## 4. Off-Unity checks on the final source

| Check | Result |
|---|---|
| Core + EditMode tests (`tools/dotnet/Tests`) | 79 passed, 0 failed, 1 ignored |
| Unity scripts vs stubs, Input System variant | 0 errors, 0 warnings |
| Same, legacy Input Manager variant | 0 errors |
| BundleCheck (same reader as the editor) | ALL PASS (78) |
| `tests/test_unity_ui_contract.py` | ALL PASS (23) |
| `tests/test_validate_replay.py` | 62 fixtures, 0 failures |
| `tools/verify_workspace_v3.py` | ALL PASS (103) |
| `gen_replay_schema.py --check` / `make_synthetic_replays.py --check` / `sync_unity_streaming_assets.py --check` | up to date / byte-identical / in sync |

## 5. Not covered

* A display that is physically 1600×900 or 1920×1080 for the standalone player. The laptop panel is 1366×768.
* Unity's Test Runner (row 32).
* Watching the vessel pulses and IV droplet animate in this release (row 28).
* Re-extracting the final ZIP on the laptop and running setup from it (row 33).
* Performance figures for the standalone player were not measured.
