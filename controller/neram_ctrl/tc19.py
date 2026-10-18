"""TC19 - development-case open-loop replay. BLOCKED until Sai supplies integration/twin_outputs/twin_DEV_<pseudo>.csv.

The path below is prepared but has never been executed: no development twin output exists (the real-data fit
failed), so nothing is run and no data is fabricated. The final holdout is never used.
"""
import glob
import os

TWIN_DIR = os.environ.get("NERAM_TWIN_DEV_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "integration",
                                                             "twin_outputs"))


def find_inputs():
    files = sorted(glob.glob(os.path.join(TWIN_DIR, "twin_DEV_*.csv")))
    return [f for f in files if "holdout" not in f.lower() and "final" not in f.lower()]


def status():
    files = find_inputs()
    if not files:
        return "BLOCKED", "no twin_DEV_<pseudo>.csv in integration/twin_outputs/"
    return "READY (not run)", ", ".join(os.path.basename(f) for f in files)
