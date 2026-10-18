#!/usr/bin/env python3
"""Static contract checks for the Unity project that do not need the Unity Editor.

1. Every UiUtil.Req<T>(root, "name") lookup in the runtime exists in NeramMain.uxml with a compatible element type.
2. NeramValidation.RequiredUiNames lists exactly the names the runtime looks up.
3. Every MonoBehaviour / ScriptableObject / AssetPostprocessor class lives in a file with the same name (Unity rule).
4. Wording guard: user-visible text never says "core temperature" and never claims clinical validation, certification,
   medical-grade status, autonomous treatment or hypothermia prevention (negated statements such as "not clinically
   validated" are allowed).
5. No '??' or '?.' applied to UnityEngine.Object-typed members in runtime scripts (Unity fake-null) - heuristic.
Run: python tests/test_unity_ui_contract.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNITY = ROOT / "unity_editor" / "Assets"
fails = []


def check(ok, msg):
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        fails.append(msg)


uxml = (UNITY / "Resources" / "NERAM" / "UI" / "NeramMain.uxml").read_text(encoding="utf-8")
elements = {}
for m in re.finditer(r"<ui:(\w+)\b[^>]*\bname=\"([^\"]+)\"", uxml):
    elements[m.group(2)] = m.group(1)

runtime = [p for p in (UNITY / "Scripts").rglob("*.cs")]
req = {}
for p in runtime:
    for m in re.finditer(r"(?:Req<(\w+)>|AddSpeed|Nav|Setting)\(\w+, \"([^\"]+)\"", p.read_text(encoding="utf-8")):
        req.setdefault(m.group(2), set()).add((m.group(1) or "Button", p.name))
for name, uses in sorted(req.items()):
    for typ, file in uses:
        el = elements.get(name)
        ok = el is not None and (typ == "VisualElement" or el == typ)
        if not ok:
            check(False, f"{file}: Req<{typ}>('{name}') -> UXML has {el or 'nothing'}")
check(all(n in elements for n in req), f"all {len(req)} runtime element lookups resolve in NeramMain.uxml")

val = (UNITY / "Editor" / "NeramValidation.cs").read_text(encoding="utf-8")
block = val[val.index("RequiredUiNames"):val.index("};", val.index("RequiredUiNames"))]
listed = set(re.findall(r"\"([a-z0-9-]+)\"", block))
check(listed == set(req), "NeramValidation.RequiredUiNames matches runtime lookups"
      + ("" if listed == set(req) else f" (missing {sorted(set(req) - listed)}, extra {sorted(listed - set(req))})"))

for p in list(runtime) + list((UNITY / "Editor").glob("*.cs")):
    text = p.read_text(encoding="utf-8")
    for m in re.finditer(r"class (\w+)\s*:\s*(MonoBehaviour|ScriptableObject)\b", text):
        check(m.group(1) == p.stem, f"{p.name}: {m.group(2)} '{m.group(1)}' matches file name")

banned = [r"core temperature", r"clinically validated", r"medical[- ]grade", r"\bcertified\b", r"autonomous",
          r"prevents? hypothermia", r"preventing hypothermia"]
negation = re.compile(r"\b(not|never|no|nor|don't|do not|isn't|is not|without)\b", re.I)
scan = list(UNITY.rglob("*.cs")) + list(UNITY.rglob("*.uxml")) + list(UNITY.rglob("*.uss")) + \
       [ROOT / "config" / "unity_scenarios.json", ROOT / "config" / "unity_display.json"]
bad = []
for p in scan:
    if "Tests" in p.parts:
        continue
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        for b in banned:
            if re.search(b, line, re.I) and not negation.search(line):
                bad.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:120]}")
check(not bad, "wording guard (no 'core temperature', no clinical/certification/autonomy/prevention claims)")
for b in bad:
    print("      " + b)

unity_types = r"(Transform|GameObject|Camera|Renderer|Material|Light|Collider|MonoBehaviour|Component|NeramAssemblyBinder|CameraRig|ModuleView|ControllerView3D)"
fake_null = []
for p in runtime:
    if "Core" in p.parts:
        continue
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"\b(GetComponent<\w+>\(\)|Find\([^)]*\)|\w*[Cc]am(era)?|\w*[Aa]nchor|\w*[Tt]ransform)\s*\?\?", line) or \
           re.search(r"\b(cam|_cam|anchor|assembly|cameraRig|binder)\?\.", line):
            fake_null.append(f"{p.name}:{i}: {line.strip()}")
check(not fake_null, "no '??' / '?.' on UnityEngine.Object references in runtime scripts")
for f in fake_null:
    print("      " + f)

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
sys.exit(1 if fails else 0)
