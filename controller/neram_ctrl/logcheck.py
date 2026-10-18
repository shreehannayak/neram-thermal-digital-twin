"""Section-S check of a controller handoff log: column order, 1 Hz time base, enum ranges, NaN as empty cells."""
import csv
import math

from .testbench import LOG_COLUMNS

ENUMS = {"Controller_State": range(7), "Degraded_Substate": range(3), "Trigger_Reason": range(12),
         "Alert": range(9), "Safety_Shutdown": (0, 1), "Fault_Latched": (0, 1), "Data_Stale_Twin": (0, 1),
         "Data_Stale_HW": (0, 1), "Clinician_Mode": (0, 1)}


def check(path):
    errs = []
    with open(path, newline="") as f:
        rd = csv.reader(f)
        hdr = next(rd)
        if hdr != LOG_COLUMNS:
            errs.append("column order differs from section S")
        prev = None
        for n, row in enumerate(rd):
            rec = dict(zip(hdr, row))
            t = float(rec["t_s"])
            if prev is not None and abs(t - prev - 1.0) > 1e-9:
                errs.append("row %d: not 1 Hz" % n)
            prev = t
            for k, rng in ENUMS.items():
                if int(float(rec[k])) not in rng:
                    errs.append("row %d: %s=%s out of range" % (n, k, rec[k]))
            for k, v in rec.items():
                if v.lower() in ("nan", "none", "null"):
                    errs.append("row %d: %s written as '%s' instead of an empty cell" % (n, k, v))
                if k.startswith("Heat_") and v and not (0.0 <= float(v) <= 100.0):
                    errs.append("row %d: %s=%s" % (n, k, v))
            if len(errs) > 20:
                break
    return errs
