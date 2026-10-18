# NERAM Unity Workspace — Final release — read this first

**Version:** NERAM_Unity_Workspace_Final (setup / viewer v3.1.0, 2026-10-10) · Unity **6000.3.26f1 (Unity 6.3 LTS)** · URP 17.3.0 · UI Toolkit · Input System 1.20

> **Status.** This release was opened and run in Unity 6000.3.26f1 on your laptop, from a test copy at `D:\Unity\Projects\NERAM_Final_test\NERAM_Unity_Workspace_Final` (2026-10-10).
> * Setup: "NERAM setup v3.1.0 complete. Validation PASSED" (94 PASS, 13 WARN, 0 FAIL).
> * Play mode: the dashboard, sidebar and drawers, charts, replay controls, camera, selection and view modes were operated by hand.
> * **What was and was not checked** — including the standalone build — is listed row by row in `docs/VERIFICATION_REPORT.md`. Nothing there is marked PASS without evidence.
>
> **Full documentation:** `docs/NERAM_Simulation_Handbook.pdf` (and `.md`): architecture, every field, the formulas with code references, the scenarios and their verified transitions, controls, troubleshooting.

## 1. What changed since v3 (design kept as approved)

* **Readable at 1920×1080, 1600×900 and 1366×768.** The dashboard is laid out on a 1600 × 900 logical reference that scales with screen height, so every 16:9 screen shows the same layout. Narrower screens (16:10, windowed) switch to a compact layout with the region panel collapsed (`◂ Details` brings it back).
* **Header regrouped:** title and scenario · source chips · state · clock · **FULLSCREEN** · Capture.
* **Collapsible sidebar (☰ MENU or `M`), closed by default:** Scenarios · Events · Parameters · All fields · Diagnostics · Sources & badges · Settings & view. One drawer at a time; `Esc` closes them; the replay, selection and chart state are not touched.
* **Always visible:** patient temperature signal (site not established, never "core"), twin estimate ± SD, controller state / alert / fault / safety, CH1–CH4, signal quality, and **HR · SpO₂ · MAP = N/A**.
* **Charts:** shorter legends; chart B ("B · MEASUREMENT vs TWIN (±60 min)") shows the `T_plant` entries only when the ASSUMED compare is switched on; chart A/C subtitles state "not core temperature" and "not measured heating". **Settings → Taller charts** gives the strip more height.
* **Fewer floating labels:** world labels Off / **Compact** (default, e.g. `CH3 18 %`, `CTRL NORMAL`) / Detailed. Clicking a label selects that channel or the controller.
* **FULLSCREEN / EXIT FULLSCREEN** (or `F11`) in the standalone player; **Presentation** (`P`).
* **Standalone Windows build:** **NERAM → 6. Build Windows player**.
* **Patient model:** a restrained refinement in place (face, neck, knees; less glossy skin). Mitts, boots, watch, controller, animations and all camera/replay controls are unchanged.
* **Fresh launch:** always starts at the beginning of the replay, **paused, 1×**.
* Fixes found while testing on your laptop: the safety banner no longer covers the controller banner; the CTRL label no longer clears the selection; the Exploded toolbar no longer overlaps the camera buttons; no horizontal scrollbar in the live-parameter column; the forecast panel no longer collapses the region panel when the forecast appears (cards show one line per value, full values in the tooltip).

The full file list is in `docs/CHANGED_FILES.md`. `config/`, `integration/` (all replays and validators) and `unity/schema/` are byte-identical to v3.

## 2. Install safely (your existing projects stay untouched)

1. Leave `NERAM_unity_layer_1`, `NERAM_Unity_Workspace_v2` and `NERAM_Unity_Workspace_v3` as they are.
   * Note: the `Library` cache folders of v1 and v2 were deleted on 2026-10-10 to free disk space. Their project files are intact; Unity rebuilds `Library` the next time you open them (10–15 min).
2. Extract `NERAM_Unity_Workspace_Final.zip` to a **new** folder, e.g. `D:\Unity\Projects\NERAM_Final\`. It contains `NERAM_Unity_Workspace_Final\` with `config/ integration/ unity/ unity_editor/ tools/ tests/ docs/` and this file.
3. Allow about **3 GB** free for `Library/` on first import, and about **1 GB** more if you build the player.
4. `D:\Unity\Projects\NERAM_Final_test\` is the copy used for testing. You can delete it once you have your own extraction.

## 3. Open, set up, play

1. Unity Hub → **Add → Add project from disk** → select **`…\NERAM_Unity_Workspace_Final\unity_editor`** (the folder with `Assets/`, `Packages/`, `ProjectSettings/`).
2. Open with **6000.3.26f1**. First import resolves packages and compiles (about 10–15 minutes on your laptop).
3. Dialog **"NERAM first run"** → **Run setup now** (or **NERAM → 1. Run full setup**). Setup finds the workspace, syncs config and validated replays into `StreamingAssets` (the holdout guard rejects any cohort other than SYNTHETIC/DEVELOPMENT), builds the scene from the generated bundle, saves and re-checks it, and runs validation.
   * Expected: **"NERAM setup v3.1.0 complete. Validation PASSED."** The 13 WARN lines are pending team deliverables (CAD stand-ins ×11, `fault_codes.csv`, `exploded_offsets.csv`).
4. Game view **Full HD (1920×1080)**, then **Play**. `SYN_SCN_B` loads paused at T+00:00:00, 1×.
5. **Click once inside the Game view** before using keys: the Editor gives input to the Game view only when it has focus.

`NoSubscription` messages come from the template's Unity AI Assistant package and are unrelated to NERAM.

## 4. Build and run the standalone Windows application

1. **NERAM → 6. Build Windows player** → **Build**. The first build compiles every shader variant (about 14 minutes on your laptop); later builds took about 75 s.
2. Output: `…\NERAM_Unity_Workspace_Final\build\NERAM_Windows\NERAM.exe` (with `NERAM_Data\`). Copy the whole `NERAM_Windows` folder if you move it.
3. Command line alternative:
   `Unity.exe -batchmode -quit -projectPath <…>\unity_editor -executeMethod Neram.EditorTools.NeramBuild.BuildWindowsBatch -logFile build.log`
4. Run it by double-clicking `NERAM.exe` or with **NERAM → 7. Run Windows player**. The first launch is borderless fullscreen at the display's native resolution; **EXIT FULLSCREEN** (or `F11`) gives a resizable window. Like every Unity player it remembers the last window state. Close with Alt+F4 or the window's ✕.

The build output is not in the ZIP (it is regenerable and machine-specific).

## 5. Controls

| Action | How |
|---|---|
| Play / pause | **PLAY** or `Space` |
| Speed | `1×` `2×` `4×` `10×` `60×` or keys `1`–`5` |
| Seek | timeline click/drag; click chart A or C; `←`/`→` step; `Shift+←/→` previous/next event; `Home` restart |
| Jump | `T` transition, `F` fault, `S` safety shutdown (`Shift` = backwards), or the JUMP buttons |
| Sidebar | **☰ MENU** or `M`; `Esc` closes drawer → sidebar → inspector → view mode → selection → Presentation |
| Select a region | click a hand, arm, foot, leg, the torso, the watch, the controller or a world label; `Esc` deselects |
| Inspect camera | left-drag orbit · right/middle-drag pan · wheel zoom · **Preset ▸** or `C` (9 presets) · **Reset View** |
| Free Roam | **Free Roam (R)** or `R`; `W A S D`, mouse look, `Space` up, `Ctrl` down, `Shift` faster, `Esc` exit |
| View modes | **External · Internal · Thermal · Exploded** (CH1–CH4, **Assemble**) |
| Display | **FULLSCREEN** / `F11` (standalone) · `P` Presentation · `B` badge detail · `D` diagnostics · **Capture** (PNG) |

## 6. Where every value comes from

| On screen | Replay field | Tag in the shipped replays | Meaning |
|---|---|---|---|
| Patient temperature signal | `obs.T_obs`, `obs.obs_missing` | SIMULATED | Synthetic demonstration signal. A development replay would carry REAL_DEV (VitalDB signal, **site not established**, never called core temperature). |
| Twin estimate, SD, forecasts | `twin.*` | SIMULATED | Synthetic stand-in. The real-data fit has not completed; only a replay produced by the canonical model (outside Unity) would carry MODEL. |
| Controller state, heat commands, faults, alerts | `ctrl.*` | SIMULATED | Replayed controller output — a command, not measured heating. |
| Module temperature, heater current, connection, cutoff | `hw.*` | SIMULATED | Simulated hardware telemetry; no hardware exists. |
| `T_plant`, `dT_heat` | `plant.*` | ASSUMED | Assumed prototype response. VitalDB has no warming-response data. |
| HR, SpO₂, MAP | none | none | **N/A** — not in replay schema 1.0, never invented. |

Missing observations are shown as gaps, never interpolated. All ten shipped replays are SYNTHETIC. No holdout data is in this workspace. Unity contains no thermal model or controller: everything is replayed. The Colab model, fitting code, preregistered rules and holdout were not touched.

## 7. Limitations

* Proof-of-concept viewer: no clinical validation, certification, treatment efficacy, autonomous treatment or prevention of hypothermia is claimed.
* Geometry is a stylised stand-in, not CAD.
* The images in `docs/previews/` are offline renders without URP lighting or the dashboard.
* In the Editor the scene runs at about 20–25 fps on your laptop.

## 8. Re-running the checks without Unity

```bash
python tests/test_unity_ui_contract.py
python tests/test_validate_replay.py              # 62 fixtures
python tools/verify_workspace_v3.py
python tools/gen_replay_schema.py --check
python tools/make_synthetic_replays.py --check
python tools/sync_unity_streaming_assets.py --check
# .NET 8: see tools/dotnet/README.md (79 tests, stub compile in two input variants, bundle check)
```

## 9. If something fails

Send the Console text of **NERAM → 4. Validate project**, the first red compile error, and `%LOCALAPPDATA%\Unity\Editor\Editor.log`.
