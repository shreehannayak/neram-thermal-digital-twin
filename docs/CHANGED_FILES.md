# Changed files: NERAM_Unity_Workspace_Final vs. NERAM_Unity_Workspace_v3

Compared by SHA-256 against the delivered v3 workspace (`.meta` files, `Library`, `build` and other caches excluded).

* `config/`, `integration/` (all ten replays, validators, fixtures) and `unity/schema/` are **byte-identical** to v3.
* No Colab model, fitting code, preregistered rule or holdout file is part of this workspace, and none was touched.
* 323 files are unchanged; 5 were added; 34 were modified (31 listed below, plus `README_FIRST.md`, `docs/VERIFICATION_REPORT.md` and this file).

## Added

| File | Purpose |
|---|---|
| `docs/NERAM_Simulation_Handbook.md` / `.pdf` | Comprehensive handbook (20 sections + parameter appendix, 61-page PDF with contents page) |
| `unity_editor/Assets/Editor/NeramBuild.cs` | **NERAM → 6. Build Windows player**, **7. Run Windows player** and the batch-mode method `NeramBuild.BuildWindowsBatch` |
| `unity_editor/Assets/Scripts/Core/LayoutRules.cs` | Logical-size and breakpoint rules (compact < 1500, narrow < 1300 logical px) |
| `unity_editor/Assets/Tests/EditMode/LayoutAndStartupTests.cs` | Tests for breakpoints and the fresh-launch state (frame 0, paused, 1×) |

## Modified — Unity runtime

| File | Change |
|---|---|
| `Scripts/NeramApp.cs` | Collapsible sidebar and drawers (incl. Sources & badges, Settings & view); `Esc` order; details panel collapse; breakpoints; FULLSCREEN / EXIT FULLSCREEN; `M`/`F11`; world-label click selects channel or controller; compact Exploded toolbar |
| `Scripts/ForecastFan.cs` | Forecast cards shortened to one line per value (full values in the card tooltip); t_hypo status stated once in the panel note |
| `Scripts/ThermalPanel.cs` | Chart B: compact legend; T_plant entries only while the ASSUMED compare is on; "Compare: n/a (open loop)" |
| `Scripts/UI/ChartsPanel.cs` | Chart A/C legends and subtitles ("not core temperature", "not measured heating") |
| `Scripts/UI/OverviewPanel.cs` | Always-visible live parameters regrouped |
| `Scripts/UI/WorldLabels.cs` | Label modes Off / Compact / Detailed; click events |
| `Scripts/ControllerStatePanel.cs` | Status chips only while the replay says so; HW stale shown as warning |
| `Scripts/Scene/NeramInput.cs` | `M` (menu) and `F11` (fullscreen) |
| `Scripts/NeramVersion.cs` | 3.1.0 |
| `Resources/NERAM/UI/NeramMain.uxml` | Header regrouped; sidebar, drawers, settings; vertical-only live-parameter scroll; chart titles/tooltips |
| `Resources/NERAM/UI/neram.uss` | 1600×900 layout, breakpoints, sidebar, Presentation, taller charts, safety-banner offsets, chart sizing, compact Exploded toolbar, forecast/region panel sizing, smaller header chips |
| `Resources/NERAM/NeramPanelSettings.asset` | Scale With Screen Size, 1600×900 reference, match height |

## Modified — Editor, generated scene, tools, tests

| File | Change |
|---|---|
| `Editor/NeramSetup.cs`, `Editor/NeramValidation.cs` | PanelSettings 1600×900; new required UI names; reference-size check |
| `NERAM_Generated/MeshData/*` | Regenerated bundle with the refined patient (face, neck, knees, skin) |
| `tools/meshgen/patient.py`, `tools/meshgen/palette.py` | Patient refinement; less glossy skin |
| `docs/previews/*.png` (8) | Re-rendered offline previews |
| `tests/test_unity_ui_contract.py`, `tools/verify_workspace_v3.py` | Contract and workspace checks extended to the new UI |
| `tools/dotnet/UnityStubs/*.cs` | Stub signatures for the new APIs (`Screen.SetResolution`, `BuildPipeline`, …) |
