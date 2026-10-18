"""Re-validate the six handoff logs in ../integration/controller_logs/ against section S."""
import os
import sys

CTRL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CTRL)
from neram_ctrl.logcheck import check  # noqa: E402

D = os.path.join(os.path.dirname(CTRL), "integration", "controller_logs")
bad = 0
for n in ("SYN_02", "TC04", "TC05", "TC07", "TC08", "TC13"):
    e = check(os.path.join(D, "ctrl_%s.csv" % n))
    print("ctrl_%s.csv: %s" % (n, "PASS" if not e else "FAIL: " + "; ".join(e[:5])))
    bad += bool(e)
sys.exit(1 if bad else 0)
