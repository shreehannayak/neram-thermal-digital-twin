"""Python side of the shared fixture corpus (run: python -m pytest tests  or  python tests/test_validate_replay.py)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integration"))
import validate_replay  # noqa: E402

FIX = ROOT / "unity_editor" / "Assets" / "Tests" / "Fixtures"


def check_all():
    manifest = json.loads((FIX / "fixtures_manifest.json").read_text())["fixtures"]
    enums = validate_replay.load_enums()
    failures = []
    for m in manifest:
        rep, _, _ = validate_replay.validate_file(FIX / m["file"], enums)
        errs = sorted(c for c in rep.count if c.startswith("E"))
        warns = sorted(c for c in rep.count if c.startswith("W"))
        if rep.valid != m["valid"]:
            failures.append(f"{m['file']}: valid={rep.valid}, expected {m['valid']} (codes {rep.count})")
        if errs != m["errors"]:
            failures.append(f"{m['file']}: errors {errs}, expected {m['errors']}")
        for w in m["warnings"]:
            if w not in warns:
                failures.append(f"{m['file']}: missing warning {w} (got {warns})")
    return manifest, failures


def test_fixture_corpus():
    _, failures = check_all()
    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    manifest, failures = check_all()
    print(f"{len(manifest)} fixtures, {len(failures)} failure(s)")
    for f in failures:
        print("  FAIL", f)
    sys.exit(1 if failures else 0)
