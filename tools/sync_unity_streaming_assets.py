#!/usr/bin/env python3
"""Copy NERAM team outputs into unity_editor/Assets/StreamingAssets (same behaviour as the Unity menu
NERAM > 2. Sync config + replays from repository).

  config/{enums.json, params.json, unity_display.json, unity_scenarios.json, interface_spec.csv} -> StreamingAssets/config/
  hardware/interfaces/fault_codes.csv (Shreehan, optional)                                   -> StreamingAssets/config/
  cad/exploded_offsets.csv (Neharikaa, optional)                                              -> StreamingAssets/cad/
  integration/replays/*.jsonl[.gz]                                                           -> StreamingAssets/replays/

HOLDOUT GUARD: every replay is fully validated (integration/validate_replay.py) before it is copied. A replay that is
invalid, or whose header cohort is not SYNTHETIC/DEVELOPMENT, is NOT copied and any stale copy is removed.
Usage: python tools/sync_unity_streaming_assets.py [--check]   (--check: report differences, change nothing; exit 1 if out of sync)
"""
import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integration"))
import validate_replay as vr  # noqa: E402

SA = ROOT / "unity_editor" / "Assets" / "StreamingAssets"
CONFIG_FILES = ["enums.json", "params.json", "unity_display.json", "unity_scenarios.json", "interface_spec.csv"]


def is_replay(p: Path) -> bool:
    return p.name.endswith(".jsonl") or p.name.endswith(".jsonl.gz")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    plan = []  # (src, dst)
    missing, rejected, remove = [], [], []
    for f in CONFIG_FILES:
        src = ROOT / "config" / f
        (plan.append((src, SA / "config" / f)) if src.exists() else missing.append(f"config/{f} (REQUIRED)"))
    for src, dst in [(ROOT / "hardware" / "interfaces" / "fault_codes.csv", SA / "config" / "fault_codes.csv"),
                     (ROOT / "cad" / "exploded_offsets.csv", SA / "cad" / "exploded_offsets.csv")]:
        (plan.append((src, dst)) if src.exists() else missing.append(f"{src.relative_to(ROOT)} (optional, not yet delivered)"))
    enums = vr.load_enums()
    rdir = ROOT / "integration" / "replays"
    for src in sorted(p for p in rdir.iterdir() if is_replay(p)) if rdir.exists() else []:
        rep, header, _ = vr.validate_file(src, enums)
        if not rep.valid:
            first = next((i for i in rep.issues if i["severity"] == "error"), None)
            rejected.append(f"{src.name}: {rep.errors} error(s)" + (f" | {first['code']} {first['message']}" if first else ""))
            stale = SA / "replays" / src.name
            if stale.exists():
                remove.append(stale)
            continue
        plan.append((src, SA / "replays" / src.name))
    # files in StreamingAssets/replays with no valid source are stale
    valid_names = {d.name for _, d in plan if d.parent.name == "replays"}
    if (SA / "replays").exists():
        for p in (SA / "replays").iterdir():
            if is_replay(p) and p.name not in valid_names and p not in remove:
                remove.append(p)
    changes = [(s, d) for s, d in plan if not d.exists() or not filecmp.cmp(s, d, shallow=False)]
    for m in missing:
        print("missing  ", m)
    for r in rejected:
        print("REJECTED ", r)
    for s, d in changes:
        print(("differs  " if a.check else "copy     ") + str(s.relative_to(ROOT)) + " -> " + str(d.relative_to(ROOT)))
    for p in remove:
        print(("stale    " if a.check else "remove   ") + str(p.relative_to(ROOT)))
    if a.check:
        ok = not changes and not remove and not any("REQUIRED" in m for m in missing)
        print("in sync" if ok else "OUT OF SYNC")
        return 0 if ok else 1
    for s, d in changes:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(s, d)
    for p in remove:
        p.unlink()
        meta = p.with_name(p.name + ".meta")
        if meta.exists():
            meta.unlink()
    print(f"done: {len(changes)} copied, {len(remove)} removed, {len(rejected)} rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
