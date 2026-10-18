"""Plan section 7 tests/test_replay_schema.py: every shipped replay line validates against
unity/schema/replay_schema.json (JSON Schema draft 2020-12), and deliberately broken lines are rejected.
The semantic rules (validate_replay.py / ReplayValidator.cs) are tested by the 62-fixture corpus; this file tests
the structural JSON Schema itself. Needs the 'jsonschema' package (environment.yml); without it the run reports
BLOCKED (exit 2) instead of passing.  Run: python -m pytest -q tests   or   python tests/test_replay_schema.py"""
import copy
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "unity" / "schema" / "replay_schema.json").read_text(encoding="utf-8"))
REPLAYS = sorted((ROOT / "integration" / "replays").glob("*.jsonl*"))

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover
    jsonschema = None


def _validator():
    Draft202012Validator.check_schema(SCHEMA)
    return Draft202012Validator(SCHEMA)


def _lines(p):
    op = gzip.open if p.suffix == ".gz" else open
    with op(p, "rt", encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def _require():
    if jsonschema is None:
        try:
            import pytest
            pytest.skip("BLOCKED: jsonschema not installed (see environment.yml)")
        except ImportError:
            raise RuntimeError("BLOCKED: jsonschema not installed")


def test_every_shipped_replay_line_matches_the_schema():
    _require()
    v = _validator()
    assert len(REPLAYS) >= 10
    for p in REPLAYS:
        L = _lines(p)
        assert L[0]["type"] == "header"
        for i, o in enumerate(L):
            errs = list(v.iter_errors(o))
            assert not errs, (p.name, i, errs[0].message)


def test_broken_lines_are_rejected():
    _require()
    v = _validator()
    L = _lines(ROOT / "integration" / "replays" / "SYN_SCN_B.jsonl.gz")
    frame = next(x for x in L[1:] if x["twin"]["Twin_Valid"] == 2)
    bad = []
    f1 = copy.deepcopy(frame); f1["twin"]["UNKNOWN_FIELD"] = 1; bad.append(("unknown field", f1))
    f2 = copy.deepcopy(frame); f2["ctrl"]["Controller_State"] = "NORMAL"; bad.append(("enum as string", f2))
    f3 = copy.deepcopy(frame); f3["obs"]["T_obs"] = "NaN"; bad.append(("NaN as a string", f3))
    f4 = copy.deepcopy(frame); del f4["src"]; bad.append(("missing group", f4))
    f5 = copy.deepcopy(frame); f5["src"]["ctrl"] = "REAL"; bad.append(("bad source tag", f5))
    h1 = copy.deepcopy(L[0]); h1["schema_version"] = "2.0"; bad.append(("unknown schema version", h1))
    h2 = copy.deepcopy(L[0]); del h2["inputs"]; bad.append(("no input hashes", h2))
    h3 = copy.deepcopy(L[0]); h3["cohort"] = "FINAL_HOLDOUT"; bad.append(("holdout cohort", h3))
    for what, o in bad:
        assert list(v.iter_errors(o)), f"schema accepted: {what}"


if __name__ == "__main__":
    if jsonschema is None:
        print("BLOCKED: jsonschema is not installed; install it (environment.yml) and rerun")
        sys.exit(2)
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as ex:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(ex)[:400])
    sys.exit(1 if fails else 0)
