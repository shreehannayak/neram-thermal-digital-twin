"""Run everything: TC01-TC19 (+TC20 listed as EXCLUDED), section-G audit, logs, tables, plots.

    cd controller
    python scripts/run_all_tests.py            # full run (~1 min + plots)
    python scripts/run_all_tests.py --no-figs  # skip the PNG plots

Deterministic (numpy seed 42). PYTHON FALLBACK, SIMULATED / ASSUMED prototype; no clinical claim.
"""
import argparse
import csv
import glob
import hashlib
import io
import os
import shutil
import sys
import time
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
CTRL = os.path.dirname(HERE)
ROOT = os.path.dirname(CTRL)
sys.path.insert(0, CTRL)

from neram_ctrl import audit, logcheck, tables, tests  # noqa: E402
from neram_ctrl import testbench as tb  # noqa: E402
from neram_ctrl.params import PARAMS_VERSION, TABLE, default_params  # noqa: E402
from neram_ctrl.tc19 import status as tc19_status  # noqa: E402

HANDOFF = {"TC02": "SYN_02", "TC04": "TC04", "TC05": "TC05", "TC07": "TC07", "TC08": "TC08", "TC13": "TC13"}
LOG_TESTS = ["TC01", "TC02", "TC03", "TC04", "TC05", "TC06", "TC07", "TC08", "TC09", "TC10", "TC11", "TC12", "TC13",
             "TC14", "TC15", "TC16", "TC17"]
RECEIVED = os.path.join(ROOT, "integration", "controller_logs_received", "2026-10-18")


def code_version():
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(CTRL, "neram_ctrl", "*.py"))):
        h.update(open(f, "rb").read())
    return "sha256:" + h.hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-figs", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    P = default_params()
    res_dir = os.path.join(CTRL, "results")
    for d in ("logs", "tables", "plots"):
        os.makedirs(os.path.join(res_dir, d), exist_ok=True)
    print("NERAM supervisory controller - PYTHON FALLBACK (rebuilt 18 Oct 2026 from Suchita's v2 spec)")
    print("Parameters:", PARAMS_VERSION)
    for k, v in TABLE.items():
        if v[2] != "FROZEN":
            print("  %-26s %-22s %-22s owner %s" % (k, P[k], v[2], v[3]))
    R, rows = tests.run_all(P)
    cv = code_version()

    # logs
    for tc in LOG_TESTS:
        name = HANDOFF.get(tc, tc)
        tb.write_log(os.path.join(res_dir, "logs", "ctrl_%s.csv" % name), R[tc])
    handoff_dir = os.path.join(ROOT, "integration", "controller_logs")
    os.makedirs(handoff_dir, exist_ok=True)
    sums = []
    for tc, name in HANDOFF.items():
        src = os.path.join(res_dir, "logs", "ctrl_%s.csv" % name)
        shutil.copyfile(src, os.path.join(handoff_dir, "ctrl_%s.csv" % name))
        sums.append("%s  ctrl_%s.csv" % (hashlib.sha256(open(src, "rb").read()).hexdigest(), name))
    for d in (os.path.join(res_dir, "logs"), handoff_dir):
        with open(os.path.join(d, "SHA256SUMS"), "w") as f:
            f.write("\n".join(sums) + "\n")

    # interface check of the six handoff logs
    lc_ok = True
    for tc, name in HANDOFF.items():
        errs = logcheck.check(os.path.join(handoff_dir, "ctrl_%s.csv" % name))
        print("LOGCHECK ctrl_%s.csv: %s" % (name, "PASS" if not errs else "FAIL " + "; ".join(errs[:3])))
        lc_ok = lc_ok and not errs

    # reproduction check against the v2 logs received from Suchita on 18 Oct
    rep = []
    for name in ("SYN_02", "TC05", "TC07", "TC08", "TC13"):
        mine = os.path.join(res_dir, "logs", "ctrl_%s.csv" % name)
        ref = os.path.join(RECEIVED, "ctrl_%s.csv" % name)
        if os.path.exists(ref):
            same = open(mine, "rb").read() == open(ref, "rb").read()
            rep.append((name, "byte-identical" if same else "DIFFERENT"))
            print("REPRODUCTION ctrl_%s.csv vs Suchita's v2 log: %s" % (name, rep[-1][1]))

    # audit and tables
    au = audit.run_audit(P, R)
    for r in au:
        print("%-7s %-8s %s" % (r["id"], r["result"], r["measured"][:100]))
    st19, why19 = tc19_status()
    print("TC19:", st19, "-", why19)
    with open(os.path.join(res_dir, "test_results.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["tc_id", "title", "criterion", "measured", "PASS/FAIL", "params version", "code version"])
        for r in rows:
            w.writerow([r["tc_id"], r["title"], r["criterion"], r["measured"], r["result"], PARAMS_VERSION, cv])
    shutil.copyfile(os.path.join(res_dir, "test_results.csv"), os.path.join(res_dir, "tables", "test_results.csv"))
    summary = tables.write_all(os.path.join(res_dir, "tables"), P, rows, au, R, lc_ok)
    with open(os.path.join(res_dir, "reproduction_check.csv"), "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["log", "rebuilt vs Suchita v2 log (integration/controller_logs_received/2026-10-18)"])
        w.writerows(rep)

    # per-test summary
    print("\n%-6s %-70s %s" % ("test", "title", "result"))
    titles = {}
    for r in rows:
        titles.setdefault(r["tc_id"], r["title"])
    n = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "EXCLUDED": 0}
    for tc, title in titles.items():
        s = summary.get(tc, "PASS")
        n[s] = n.get(s, 0) + 1
        print("%-6s %-70s %s" % (tc, title[:70], s))
    crit = {}
    for r in rows:
        crit[r["result"]] = crit.get(r["result"], 0) + 1
    print("Criteria:", ", ".join("%d %s" % (v, k) for k, v in sorted(crit.items())))
    print("Tests:", ", ".join("%s %d" % (k, v) for k, v in n.items()))

    if not a.no_figs:
        for tc in LOG_TESTS:
            title = titles.get(tc, "")
            tests_rows = R[tc]
            from neram_ctrl.plots import plot_test
            plot_test(tc, title, tests_rows, os.path.join(res_dir, "plots"))
        print("plots written to results/plots/")
    print("Run time %.0f s; code version %s" % (time.time() - t0, cv))
    return 0 if n.get("FAIL", 0) == 0 and lc_ok else 1


if __name__ == "__main__":
    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s)
            buf.write(s)
            return len(s)

    with redirect_stdout(Tee()):
        code = main()
    with open(os.path.join(CTRL, "results", "run_console.txt"), "w") as f:
        f.write(buf.getvalue())
    sys.exit(code)
