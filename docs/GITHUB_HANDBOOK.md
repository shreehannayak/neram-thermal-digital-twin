# NERAM GitHub handbook (team)

Written by Sai, 18 Oct 2026. How to work in this repository until the 20 Oct submission.

## 1. The repository at a glance

Everything lives in one public repository, `shreehannayak/neram-thermal-digital-twin`, branch `main`.

| Folder | What is in it | Owner |
|---|---|---|
| `README.md` | The 18-section submission README, picture gallery at the top | Shreehan (skeleton), Sai |
| `src/`, `analysis/` | Digital Twin model and development pipeline | Sai |
| `integration/`, `config/`, `unity/schema/`, `tests/` | Replay builder, validators, interface spec v1.0, parameters, tests | Sai |
| `controller/` | Supervisory controller (Python fallback): spec, results, figures, logs, video | Suchita |
| `hardware/` | Diagrams, one-channel schematic, comparisons, BOM, power budget, interfaces | Shreehan |
| `cad/` | FBX exports, Unity-ready copies, renders R01–R08 | Neharikaa |
| `unity_editor/` | Unity 6000.3.26f1 project of the replay viewer | Sai |
| `docs/` | Architecture and presentation PDFs, safety page, cards, audit trail, screenshots | Sai |
| `tools/` | Scripts that generate scenes, figures, renders, fixtures | Sai |
| `results/figures/` | The four synthetic twin figures (the only published results) | Sai |

## 2. Daily workflow in GitHub Desktop

1. Check **Current repository** = `neram-thermal-digital-twin` (GitHub Desktop may still show the old name `neram-thermal-ditital-twin` for the local folder) and **Current branch** = `main`.
2. **Fetch origin**; if it becomes **Pull origin**, click it.
3. Make your changes in the clone folder.
4. In **Changes**, untick anything that should not go up.
5. Write a short summary (for example "Hardware: BOM prices for MOSFET and NTC") and **Commit to main**.
6. **Push origin**.

`.fbx` and `.mp4` files use Git LFS; GitHub Desktop handles it. Push from GitHub Desktop, not from a terminal
without `git lfs`. The **History** tab shows every commit and its diff.

## 3. Adding or updating your part

Work only inside your own folder.

| Member | Folder | How to add something |
|---|---|---|
| Suchita | `controller/` | Code in `controller/neram_ctrl/` (run `python scripts/run_all_tests.py` from `controller/`), logs in `controller/results/logs/`; handoff logs are copied to `integration/controller_logs/` |
| Neharikaa | `cad/` | Done: the 3D models are in `cad/exports/`. Any new FBX: tell Sai the same day so the Unity import check runs |
| Shreehan | `hardware/` | Edit CSV/Markdown directly; diagrams and schematic come from `hardware/diagrams/make_diagrams.py` and `hardware/schematics/make_schematic.py` (commit script and images) |
| Sai | everything else | Unity changes in the workspace, copied to `unity_editor/` with their `.meta` files |

**Interface-change rule.** A row in `config/params.json` or `config/interface_spec.csv` you do not own changes
only through a GitHub issue tagged `interface-change`; the owner approves and Sai merges. Names in spec v1.0 are frozen.

**Confirm your contribution:** one GitHub comment confirming your line in README section 2, and your family name in
`CITATION.cff`.

## 4. Running and rebuilding

```
python tools/run_all_tests.py
python integration/validate_replay.py integration/replays/*.jsonl.gz
python tools/sync_unity_streaming_assets.py --check
```

Unity (open `unity_editor/` with 6000.3.26f1): **NERAM > 1. Run full setup** after a fresh clone; **NERAM > Scene >
Apply scene extras** (mask, O2 trolley, airway, surgeon; already saved in the scene); Test Runner EditMode: 86 pass,
0 fail, 1 skipped; **NERAM > 6. Build Windows player** writes `build/NERAM_Windows/NERAM.exe` (its own window, F11
full screen). Viewer keys: I / K walk the surgeon, J / L turn, U / O side-step; **Internal** shows the airway and
oxygen flow.

| What | Command |
|---|---|
| Hardware diagrams | `python hardware/diagrams/make_diagrams.py` |
| One-channel schematic | `python hardware/schematics/make_schematic.py` |
| Sensor-pocket section R08 | `python tools/render_section.py` |
| Annotate R01–R07 | `python tools/annotate_renders.py <raw dir> cad/renders` |
| Scene extras | `python tools/gen_scene_extras.py` (about 8 minutes) |

## 5. Rules that keep the submission safe

- Never publish holdout or case-level data: `results/development/` and `results/final/` stay out of git; no VitalDB
  downloads, `.csv.gz` caches or Colab folders.
- Never invent a number: unsourced values stay TBD.
- Label everything simulated, assumed or illustrative.
- Never "core temperature", "clinically validated", "prevents hypothermia", "medical-grade" or "certified" (tested).
- Code Apache-2.0 (`LICENSE`); CAD, docs, figures CC BY 4.0 (`LICENSE-CAD-DOCS`).
- No force-push; fix mistakes with a new commit and tell Sai.

## 6. What is left before 20 Oct

- **Everyone:** GitHub confirmation comment; family name in `CITATION.cff`.
- **Sai:** demo video (link in README section 16); sign-off of scientific wording in the checklist.
- **Suchita:** done (code rebuilt from her spec on 18 Oct, TC04 log and `T07_duty_stats.csv` generated). Only a reply on issue #2, the GitHub confirmation and family name.
- **Neharikaa:** done (3D models delivered 18 Oct). Only the GitHub confirmation and family name, as for everyone.
- **Shreehan:** 19 Oct audit from a logged-out browser (`docs/SUBMISSION_CHECKLIST.md`, dry run in
  `docs/SUBMISSION_DRYRUN_2026-10-18.md`); remaining BOM prices (supply, inlet, relay, heaters, small parts); review the
  one-channel schematic; close issue #1.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| Push rejected | Fetch, Pull, then push again |
| Merge conflict | Keep the owner's version of files you do not own; ask Sai for shared files |
| `.fbx`/`.mp4` is a tiny text file | Install Git LFS (`git lfs install`) and pull again, or download from GitHub |
| "File exists" / `index.lock` | Close GitHub Desktop, delete `.git/index.lock`, reopen |
| Unity window blank, not responding | End Unity in Task Manager, reopen from Unity Hub |
| NERAM.exe build: file in use | Close every running NERAM.exe |
| Test fails after editing `params.json` | `python tools/sync_unity_streaming_assets.py`, then re-run tests |
