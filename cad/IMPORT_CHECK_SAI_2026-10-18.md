# Neharika's FBX set: Unity import check and Unity prep (Sai, 18 Oct 2026)

Plan reference: Person 2 sections V (export rules), W (names), AB (definition of done); hand-off "Unity import check
within 1 day of each FBX delivery".

* `cad/exports/source_fusion_2026-10-18/`: the 4 FBX exactly as Neharika exported them from Fusion (unchanged).
* `cad/exports/unity/`: the 6 Unity-ready FBX Sai made from them on 18 Oct (script: `cad/tools/fixneha.py`,
  report: `PREP_REPORT_2026-10-18.json`). **Shapes and sizes are Neharika's.** Only units, axes, names, grouping,
  pivots and material names changed; the controller was decimated.
* These 6 files are placed on the mannequin in the Unity viewer (`NERAM > CAD > Place Neharika CAD on the mannequin`);
  pictures: `cad/renders/unity_preview_2026-10-18/`.

## Check of the files as received

| Check (plan) | Result | Detail |
|---|---|---|
| Format | PASS | Binary FBX 7.2, Autodesk Fusion (FBX SDK 2020.3.9) |
| Size | PASS | Correct real-world size: controller 220 × 140 × 80 mm, hand pad 113 × 164 mm, foot pad 89 × 163 mm, watch case 40 × 40 × 10 mm. **Correction:** an earlier version of this note said "10× too small". That was wrong; it missed the ×10 scale Fusion puts on every part. The ×10 part scale is still untidy for Unity, so the prep folds it into metres. |
| Axes | FAIL (fixed by prep) | Modelled Z-up but tagged Y-up, so in Unity the pads would stand on edge and the controller would lie face-down |
| Names per W | FAIL (fixed) | 10 names had trailing spaces (`CH2_Liner ` …); roots had "vNN" suffixes |
| Hierarchy per W | FAIL (fixed) | No `Left_Hand_Module` / `Right_Hand_Module` / `Left_Foot_Module` / `Right_Foot_Module` / `Bedside_Controller` parents; CH1+CH2 and CH3+CH4 were in one file each |
| Materials | FAIL (fixed) | Fusion appearance names; the fabric appearances export with **no colour** (texture only), so liner/insulation would render black |
| Triangles | controller FAIL (fixed) | Controller 19,890 (> 15k); modules 2,060–4,698 and watch 2,430 PASS |
| Parts | PARTIAL | All BC_* parts present. Modules: Liner, Heater, Insulation, Shell, Strap_1/2, Hook_1/2, Sensor_A/B present. **`CHn_Strain_Relief` missing** (Unity validation shows a WARN); `CHn_Cutoff` is optional in W |
| Hand handedness | PASS | CH1 is a true left hand, CH2 a true right hand (mirrored) |
| Missing deliverables | OPEN | `NERAM_Assembly.fbx` (Reference_Cube_1m, OR_Table, Patient_Mannequin, Cable_CH1..4 + Connector_CH1..4), real `exploded_offsets.csv`, STEP + native .f3d, renders R01–R08, drawings D01–D05, `cad/README.md` |

## What the prep did (`cad/tools/fixneha.py`, reproducible)

1. Units → metres (UnitScaleFactor 100, vertices cm → m, part scale 10 → 1). Unity shows scale 1, size unchanged.
2. Axes → Y up: (x, y, z) → (x, z, −y). Module +Y points away from the skin; controller front faces +Z.
3. Pivots per plan V.4: module origin = centre of the liner's skin-contact face; controller origin = rail-clamp centre;
   watch origin = underside of the case.
4. One file per top-level object (plan V.1): `NERAM_Left_Hand_Module` (CH1), `NERAM_Right_Hand_Module` (CH2),
   `NERAM_Left_Foot_Module` (CH3), `NERAM_Right_Foot_Module` (CH4), `NERAM_Bedside_Controller`, `NERAM_Watch_Concept`;
   root names per W, trailing spaces removed.
5. Materials → one per function: MAT_Liner, MAT_Heater, MAT_Insulation, MAT_Shell, MAT_Strap (straps + hooks),
   MAT_Sensor, MAT_Enclosure, MAT_Indicator (LEDs), MAT_Connector (ports, inlet, switch), plus MAT_Display,
   MAT_Button_Start/Stop/Reset and MAT_Placeholder (magenta, PCB/PSU placeholders, plan convention). Colours are
   Neharika's; texture-only fabrics got the flat colour their appearance name says (light brown / grey / black).
6. Controller decimated to 12,748 triangles (BC_Enclosure 9,772 → 5,200, BC_Front_Panel 5,770 → 3,200), quadric
   edge collapse, edges kept; normals recomputed. Render-quality originals stay in `source_fusion_2026-10-18/`.
7. `exploded_offsets_SAI_DEFAULT.csv`: a default exploded view by layer order (liner 0, sensors 15 mm, heater 30 mm,
   insulation 50 mm, shell 75 mm, straps 100 mm). Visual only; Neharika's own `exploded_offsets.csv` replaces it.

## Still for Neharika

1. Add `CHn_Strain_Relief` to the four modules (cable exit at the wrist / heel edge).
2. Export `NERAM_Assembly.fbx` with `Reference_Cube_1m`, cables and connectors, plus her `exploded_offsets.csv`.
3. Commit STEP + native files, renders R01–R08 and drawings D01–D05; write `cad/README.md`.
4. Next export from Fusion: set Y-up and centimetres/metres, and name materials `MAT_*`, so the prep step is not needed.
5. Use the CAD envelope v2 values in `hardware/interfaces/cad_envelope.csv`.
