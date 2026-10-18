# Unity import check of Neharika's FBX set (Sai, 18 Oct 2026)

Plan reference: Person 2 sections V (export rules), W (names), AB (definition of done); hand-off "Unity import check
within 1 day of each FBX delivery". Files checked: `cad/exports/unity/` (4 FBX, as received). Read with a binary-FBX
inspector (units, axes, object names, triangle counts, materials); not yet imported into the Unity scene.

| Check (plan) | Result | Detail |
|---|---|---|
| Format | PASS | Binary FBX 7.2, exported by Autodesk Fusion (FBX SDK 2020.3.9) |
| Axes: Y up | PASS | UpAxis = Y (+), FrontAxis = Z (+) in all four files |
| **Units: 1 Unity unit = 1 m** | **FAIL** | Header says millimetres (UnitScaleFactor 0.1) but the geometry is in centimetres (controller 22 × 8 × 14, hand shell 11.2 × 16.4 × 0.7, watch case 4 × 4 × 1). Unity would import everything **10× too small** (controller 2.2 cm wide). Fix: export from Blender in metres with Apply Transform (plan V.2), or set the Fusion export unit to cm. No `Reference_Cube_1m` included to confirm. |
| **Names exactly per W** | **FAIL** | Trailing spaces in 10 names: `BC_LED_CH2 `, `CH2_Liner `, `CH2_Strap_1 `, `CH2_Strap_2 `, `CH2_Hook_1 `, `CH2_Hook_2 `, `CH2_Sensor_A `, `CH4_Liner `, `CH4_Hook_1 `, `CH4_Sensor_A `. Roots carry Fusion version suffixes (`NERAM_CH1_Hand_Module v19`). |
| **Hierarchy per W** | **FAIL** | No `Left_Hand_Module` / `Right_Hand_Module` / `Left_Foot_Module` / `Right_Foot_Module` / `Bedside_Controller` parent objects: CH1_* and CH2_* parts are flat siblings in one file. Unity's binder looks for those exact parent names. |
| Child parts | PARTIAL | Liner, Insulation, Shell, Heater, Strap_1/2, Sensor_A/B present for CH1–CH4. `CHn_Strain_Relief` missing; `CHn_Hook_1/2` extra (fine). Controller has all BC_* parts in W plus BC_Power_Switch, BC_PCB_Placeholder, BC_PSU_Placeholder (fine). |
| **Materials** | **FAIL** | Fusion appearance names ("Fabric (Grey)", "PEKK …") instead of `MAT_Liner`, `MAT_Sensor`, `MAT_Heater`, `MAT_Insulation`, `MAT_Shell`, `MAT_Strap`, `MAT_Enclosure`, `MAT_Indicator` (Unity recolours MAT_Heater and MAT_Indicator by state). |
| Triangle targets | PARTIAL | Each module 2,060–4,698 (≤ 20k PASS); **controller 19,890 (> 15k target, FAIL)**, mostly BC_Enclosure 9,772 + BC_Front_Panel 5,770: decimate. Watch 2,430. |
| Missing files | FAIL | `NERAM_Assembly.fbx` (with `Reference_Cube_1m`, `OR_Table`, `Patient_Mannequin`, cables `Cable_CH1..4` + `Connector_CH1..4`), `exploded_offsets.csv`, STEP + native files, renders R01–R08, drawings D01–D05, cad/README.md |
| Watch | NOTE | `NERAM_Watch_Concept.fbx` is not in plan section W; kept as a display-only wearable concept (no controls, no battery, per plan rule "no wrist-mounted controller / wrist battery"). |

## What Neharika needs to do (≈ 1 hour in Fusion/Blender)
1. Re-export in **metres** (Blender: scene unit metres, Apply Transform, Forward −Z, Up Y) and add `Reference_Cube_1m`.
2. Remove the trailing spaces; drop the "vNN" suffixes from root names.
3. Group parts under `Left_Hand_Module`, `Right_Hand_Module`, `Left_Foot_Module`, `Right_Foot_Module`, `Bedside_Controller`.
4. Rename materials to the `MAT_*` names.
5. Decimate the controller to ≤ 15k triangles.
6. Export `NERAM_Assembly.fbx` and `exploded_offsets.csv` (`object,dx_m,dy_m,dz_m`).
7. Use the CAD envelope v2 values now in `hardware/interfaces/cad_envelope.csv` (M12 8-pin ports, 109 × 52 × 33.5 mm PSU, C14 inlet, 25 × 10 mm rail).

Until then the Unity scene keeps its labelled placeholder geometry.
