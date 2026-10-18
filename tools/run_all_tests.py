#!/usr/bin/env python3
"""Run every tests/test_*.py file (each has its own __main__ runner) without needing pytest, and classify the result:
PASS (exit 0), FAIL (exit 1 / any other), BLOCKED (exit 2, or a missing third-party module such as scipy or
jsonschema). Writes nothing. Usage: python tools/run_all_tests.py"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    rows, worst = [], 0
    for f in sorted((ROOT / "tests").glob("test_*.py")):
        r = subprocess.run([sys.executable, "-B", str(f)], capture_output=True, text=True, cwd=str(ROOT))
        out = r.stdout + r.stderr
        if r.returncode == 0:
            status = "PASS"
        elif r.returncode == 2 or "ModuleNotFoundError" in out:
            status = "BLOCKED"
        else:
            status = "FAIL"
            worst = 1
        n_pass = out.count("PASS")
        n_fail = sum(1 for line in out.splitlines() if line.startswith("FAIL") or line.strip().startswith("FAIL"))
        note = ""
        if status == "BLOCKED":
            missing = [line for line in out.splitlines() if "ModuleNotFoundError" in line or "BLOCKED" in line]
            note = missing[-1].strip() if missing else ""
        rows.append((f.name, status, n_pass, n_fail, note))
    w = max(len(r[0]) for r in rows)
    for name, status, p, fl, note in rows:
        print(f"{name.ljust(w)}  {status:8s} pass-lines={p:<3d} fail-lines={fl:<3d} {note}")
    print("OVERALL:", "FAIL" if worst else ("PASS (with BLOCKED files)" if any(r[1] == "BLOCKED" for r in rows) else "PASS"))
    return worst


if __name__ == "__main__":
    sys.exit(main())
