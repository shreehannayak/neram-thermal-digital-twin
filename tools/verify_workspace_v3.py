#!/usr/bin/env python3
"""Structural verification of NERAM_Unity_Workspace_v3 WITHOUT the Unity Editor.

Proves file layout, settings, contracts, generated data and replay validity. It does NOT prove that the project imports,
compiles or renders in Unity: only opening it in Unity 6000.3 can do that (see docs/VERIFICATION_REPORT.md).
Run from anywhere:  python tools/verify_workspace_v3.py
"""
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
U = ROOT / "unity_editor"
A = U / "Assets"
sys.path.insert(0, str(ROOT / "integration"))
import validate_replay as vr  # noqa: E402

fails = []


def check(ok, msg):
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        fails.append(msg)


# ---------------------------------------------------------------- layout
for d in ("config", "integration/replays", "unity", "unity_editor/Assets", "unity_editor/Packages", "unity_editor/ProjectSettings", "tests", "tools", "docs"):
    check((ROOT / d).is_dir(), f"workspace folder {d}/")
check((U / "ProjectSettings" / "ProjectVersion.txt").is_file(), "unity_editor/ProjectSettings/ProjectVersion.txt")
check((ROOT / "config" / "enums.json").is_file() and (ROOT / "integration" / "replays").is_dir(), "workspace markers (config/enums.json + integration/replays/) for marker-based discovery")
for junk in ("Library", "Temp", "Logs", "UserSettings", "obj"):
    check(not (U / junk).exists(), f"no {junk}/ shipped (Unity regenerates it)")

# ---------------------------------------------------------------- editor version, input, packages
pv = (U / "ProjectSettings" / "ProjectVersion.txt").read_text()
check(re.search(r"m_EditorVersion: 6000\.3\.26f1", pv) is not None, "ProjectVersion: 6000.3.26f1 (Unity 6.3 LTS)")
ps = (U / "ProjectSettings" / "ProjectSettings.asset").read_text()
check(re.search(r"activeInputHandler: 1\b", ps) is not None, "Active Input Handling = Input System (EventSystem uses InputSystemUIInputModule)")
man = json.loads((U / "Packages" / "manifest.json").read_text())["dependencies"]
check(man.get("com.unity.render-pipelines.universal") == "17.3.0", "URP 17.3.0 (6000.3 line)")
for pkg in ("com.unity.inputsystem", "com.unity.ugui", "com.unity.nuget.newtonsoft-json", "com.unity.test-framework", "com.unity.modules.uielements",
            "com.unity.modules.physics", "com.unity.modules.screencapture", "com.unity.modules.jsonserialize"):
    check(pkg in man, f"package {pkg} declared directly")
for a in ("Scripts/Core/Neram.Core.asmdef", "Scripts/Neram.Runtime.asmdef", "Editor/Neram.Editor.asmdef", "Tests/EditMode/Neram.Tests.EditMode.asmdef"):
    p = A / a
    check(p.is_file() and json.loads(p.read_text())["name"], f"asmdef {a}")

# ---------------------------------------------------------------- dashboard root cause + discovery
ps_asset = A / "Resources" / "NERAM" / "NeramPanelSettings.asset"
check(ps_asset.is_file() and (A / "Resources" / "NERAM" / "NeramPanelSettings.asset.meta").is_file(), "PanelSettings in Resources/NERAM (runtime fallback Resources.Load)")
theme_meta = (A / "Resources" / "NERAM" / "UI" / "NeramRuntimeTheme.tss.meta").read_text()
theme_guid = re.search(r"guid: (\w+)", theme_meta).group(1)
check(theme_guid in ps_asset.read_text(), "PanelSettings references the NERAM runtime theme")
setup = (A / "Editor" / "NeramSetup.cs").read_text()
check('FindProperty("m_PanelSettings")' in setup and "VerifySavedScene" in setup, "setup assigns PanelSettings via SerializedObject and verifies the saved scene")
_bs = setup[setup.index("public static NeramSceneBuilder.Result BuildScene"):]
_ns = _bs.index("EditorSceneManager.NewScene(")
check("LoadAssetAtPath<PanelSettings>(psPath)" in _bs[_ns:_ns + 600], "BuildScene reloads PanelSettings from disk AFTER NewScene (v2 root cause: NewScene unloaded the asset, scene saved with m_PanelSettings {fileID: 0})")
check("m_PanelSettings: {fileID: 0}" in setup, "setup fails loudly when the saved scene has an empty PanelSettings reference")
app = (A / "Scripts" / "NeramApp.cs").read_text()
check('Resources.Load<PanelSettings>(PanelSettingsResource)' in app, "runtime falls back to Resources PanelSettings with an error log")
check('Resources.Load<VisualTreeAsset>(UxmlResource)' in app and "CloneTree(top)" in app, "runtime loads the UXML from Resources and clones it when the document tree is empty")
check((A / "Resources" / "NERAM" / "UI" / "NeramMain.uxml").is_file() and (A / "Resources" / "NERAM" / "UI" / "neram.uss").is_file(), "dashboard UXML/USS live in Resources/NERAM/UI")
uss = (A / "Resources" / "NERAM" / "UI" / "neram.uss").read_text()
fonts = set(re.findall(r'url\("([^"]+)"\)', uss))
check(all((A / "Resources" / "NERAM" / "UI" / f).resolve().is_file() for f in fonts), f"every USS font url resolves ({len(fonts)} fonts)")
# final-release UI features
_uxml = (A / "Resources" / "NERAM" / "UI" / "NeramMain.uxml").read_text(encoding="utf-8")
_uss = (A / "Resources" / "NERAM" / "UI" / "neram.uss").read_text(encoding="utf-8")
check(all(f'name="{n}"' in _uxml for n in ("sidebar", "btn-menu", "btn-fullscreen", "drawer-settings", "drawer-sources", "btn-details")), "sidebar, menu, fullscreen, settings/sources drawers and details toggle exist in the UXML")
check('class="ui-block hidden"' in _uxml[_uxml.index('name="sidebar"') - 40:_uxml.index('name="sidebar"') + 60], "sidebar is collapsed by default and blocks 3D input")
check("m_ReferenceResolution: {x: 1600, y: 900}" in ps_asset.read_text() and "m_Match: 1" in ps_asset.read_text(), "PanelSettings: 1600x900 reference matched to screen height (no shrink-to-fit of a 1920 layout)")
check(all(c in _uss for c in (".bp-compact", ".bp-narrow", ".details-collapsed", ".presentation", ".wl-mode-compact")), "responsive breakpoint, details, presentation and compact-label rules present in the USS")
check((A / "Editor" / "NeramBuild.cs").is_file() and "StandaloneWindows64" in (A / "Editor" / "NeramBuild.cs").read_text(encoding="utf-8"), "Windows standalone build script present (NERAM > 6. Build Windows player)")
check("NeramSceneStamp" in setup and "generatorVersion" in (A / "Editor" / "NeramFirstRun.cs").read_text(), "scene version stamp written by setup and checked on open (outdated-scene detection)")
inp = (A / "Scripts" / "Scene" / "NeramInputController.cs").read_text()
check("ui-block" in inp and "Cursor.lockState" in inp, "camera/selection input polled independently of the UI, ignored over ui-block elements; Free Roam locks the cursor")
uxml = (A / "Resources" / "NERAM" / "UI" / "NeramMain.uxml").read_text()
for blk in ("top-bar", "left-column", "right-column", "charts-strip", "transport", "view-toolbar", "pipeline-strip"):
    check(re.search(r'name="%s"[^>]*class="[^"]*ui-block' % blk, uxml) is not None, f"#{blk} blocks 3D input (class ui-block)")
mv = (A / "Scripts" / "ModuleView.cs").read_text()
check("v.Heat" in mv and "T_obs" not in mv and "TObs" not in mv, "device glow is driven by the replayed Heat_i only (never by the temperature signal)")
sync = (A / "Editor" / "NeramSync.cs").read_text()
check("NeramWorkspace.Root" in sync and '"..", ".."' not in sync, "NeramSync uses marker-based workspace discovery (no fixed depth)")
abs_paths = []
for p in list(A.rglob("*.cs")) + [q for q in (ROOT / "tools").rglob("*.py") if q.name != "verify_workspace_v3.py"]:
    t = p.read_text(encoding="utf-8", errors="ignore")
    if re.search(r"[A-Za-z]:\\\\(Unity|Users)|/home/claude|D:/Unity", t):
        abs_paths.append(str(p.relative_to(ROOT)))
check(not abs_paths, "no hard-coded absolute paths in scripts" + (f" ({abs_paths})" if abs_paths else ""))
check(not (A / "Scenes" / "NERAM_OR_Replay.unity").exists(), "stale scene not shipped (setup regenerates it; NeramFirstRun offers setup on first open)")
check((A / "Editor" / "NeramFirstRun.cs").is_file(), "first-run helper present")
check("EnsureEventSystem" in setup and "InputSystemUIInputModule" in setup, "setup adds EventSystem + InputSystemUIInputModule")

# ---------------------------------------------------------------- generated geometry
gen = A / "NERAM_Generated"
bundle = gen / "MeshData" / "neram_scene.bytes"
manifest = json.loads((gen / "MeshData" / "scene_manifest.json").read_text())
check(bundle.is_file() and hashlib.sha256(bundle.read_bytes()).hexdigest() == manifest["bundle_sha256"], "scene bundle present and matches scene_manifest.json sha256")
pal = json.loads((gen / "MeshData" / "materials.json").read_text())["materials"]
pal_names = {m["name"] for m in pal}
used = {("MAT_TEX_" + m[4:]) if m.startswith("TEX:") else m for m in manifest["materials"]}
check(used <= pal_names, f"every mesh material exists in materials.json ({len(used)} used, {len(pal_names)} in palette)")
for m in pal:
    if m["texture"]:
        check((gen / "Textures" / f"{m['texture']}.png").is_file(), f"texture {m['texture']}.png for {m['name']}")
regions = set(manifest["regions"])
need = {"hand_left", "hand_right", "arm_left", "arm_right", "torso", "leg_left", "leg_right", "foot_left", "foot_right", "wearable", "controller"}
check(need <= regions, f"all 11 selectable regions in the bundle ({sorted(regions)})")
st = manifest["stats"]
check(st["triangles"] < 1_200_000, f"scene size reasonable ({st['triangles']:,} triangles, {st['meshes']} meshes)")
prev = sorted((ROOT / "docs" / "previews").glob("*.png"))
check(len(prev) >= 7, f"{len(prev)} offline geometry previews in docs/previews (labelled: not Unity renders)")

# ---------------------------------------------------------------- replays + holdout guard
enums = vr.load_enums(ROOT / "config" / "enums.json")
sa = sorted((A / "StreamingAssets" / "replays").glob("*.jsonl.gz"))
src = sorted((ROOT / "integration" / "replays").glob("*.jsonl.gz"))
check(len(sa) >= 10 and [p.name for p in sa] == [p.name for p in src], f"{len(sa)} replays in StreamingAssets (>= 10), same set as integration/replays")
for r in sa:
    rep, header, _ = vr.validate_file(r, enums)
    same = (ROOT / "integration" / "replays" / r.name).read_bytes() == r.read_bytes()
    check(rep.valid and header.get("cohort") == "SYNTHETIC" and same, f"replay {r.name}: valid, cohort {header.get('cohort')}, identical to integration copy")
for sid in ("SYN_SCN_A0", "SYN_SCN_B", "SYN_SCN_C", "SYN_SCN_D"):
    check((A / "StreamingAssets" / "replays" / f"{sid}.jsonl.gz").is_file(), f"scenario {sid}")
holdout_like = []
for p in list(ROOT.rglob("*.jsonl.gz")) + list(ROOT.rglob("*.csv")) + list(ROOT.rglob("*.parquet")):
    n = p.name.lower()
    if "holdout" in n or "final_holdout" in str(p).lower():
        holdout_like.append(str(p.relative_to(ROOT)))
check(not holdout_like, "no holdout-named data files anywhere in the workspace")
for r in sa:
    with gzip.open(r, "rt", encoding="utf-8") as fh:
        head = json.loads(fh.readline())
    if head.get("cohort") not in ("SYNTHETIC", "DEVELOPMENT"):
        check(False, f"{r.name}: cohort {head.get('cohort')} not allowed")

# ---------------------------------------------------------------- replay-driven only (no model/controller in C#)
writers = [p.name for p in (A / "Scripts").rglob("*.cs") if "Core" not in p.parts and re.search(r"ColumnBuilder|\.Set\(\s*f\.|Table\.Set", p.read_text())]
check(not writers, "runtime scripts never write replay columns (values come only from validated files)")
model_terms = [p.name for p in (A / "Scripts").rglob("*.cs") if re.search(r"\b(Kalman|GPB2|eb_step|thermal_robust_core|Hysteresis|PID)\b", p.read_text())]
check(not model_terms, "no thermal-model / controller implementation terms in Unity scripts")

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
sys.exit(1 if fails else 0)
