# CAD renders R01-R08 (plan section U)

Made by Sai on 18 Oct 2026, taking over the render task for Neharikaa. **The geometry is Neharikaa's Fusion CAD**
(`cad/exports/unity/`, shapes unchanged). The mannequin, OR table, room and cables are generated stand-ins, and the
pad drape and strap length are visual fits in the viewer (see `cad/IMPORT_CHECK_SAI_2026-10-18.md`). Each image
carries the footer "NERAM proof-of-concept prototype — not a medical device".

| File | View | Made with |
|---|---|---|
| `R01_full_scene.png` | Full scene: patient, four modules, wrist display, controller, cables | Unity viewer |
| `R02_hand_module_iso.png` | CH1 hand module, isometric | Unity viewer |
| `R03_foot_module_iso.png` | CH3 / CH4 foot modules, isometric | Unity viewer |
| `R04_hand_module_exploded.png` | CH1 exploded, labelled layers | Unity viewer |
| `R05_foot_module_exploded.png` | CH3 exploded, labelled layers | Unity viewer |
| `R06_controller_front_ports.png` | Bedside controller front and CH1-CH4 ports | Unity viewer |
| `R07_cable_routing_top.png` | Cable routing, top view (ceiling hidden) | Unity viewer |
| `R08_sensor_pocket_section.png` | Section through CH1_Sensor_A, measured layer stack | `tools/render_section.py` (from the FBX) |

Exploded offsets are visual only (`cad/exports/unity/exploded_offsets_SAI_DEFAULT.csv` × 1.4) (no exploded-offsets file is part of the CAD
deliverable). The R08 cut shows a 0.5 mm overlap between insulation (from 3.0 mm) and heater film
(to 3.5 mm) in the exported model; it is noted, not changed.

## Reproduce
1. Unity (workspace `unity_editor/`): **NERAM > CAD > Render plan renders R01-R07** (`unity_editor/Assets/Editor/NeramRenders.cs`) writes
   the raw 1920 × 1080 images and `R04/R05_*_labels.json` to `docs/evidence/cad_renders/`.
2. `python tools/annotate_renders.py docs/evidence/cad_renders cad/renders` adds the title, labels and footer.
3. `python tools/render_section.py` writes R08 from `cad/exports/unity/NERAM_Left_Hand_Module.fbx` (git-lfs files needed).
