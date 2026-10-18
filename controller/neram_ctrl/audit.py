"""Section-G audit of FaultMonitor / Supervisor (plan sections G, K, L, J) with targeted short runs."""
import copy

from . import params as prm
from . import testbench as tb
from .blocks import NAN
from .tests import caps_violations

STD_LIMITS_TEST_ONLY = (20.0, 60.0)
T_EST_D1 = 37.0 - 0.25 / 20.5     # gives Heat ~0.25 % at the CLINICIAN_WARMING entry


def _row(rows, t):
    return rows[t]


def run_audit(P, R):
    out = []

    def add(i, req, meas, ok):
        out.append(dict(id=i, requirement=req, measured=meas,
                        result=ok if isinstance(ok, str) else ("PASS" if ok else "FAIL")))

    # G1: NaN never treated as 0 / cool / no-fault
    rows = tb.run(P, 60, "SYN_BELOW", twin_override=lambda t, s: s.update(T_est=NAN) if t >= 30 else None)
    y = rows[35]
    add("AU-G1a", "Twin_Valid = VALID but T_est = NaN -> twin not ok, TWIN_DEGRADED, no heat (never T_est = 0)",
        "twin_ok=%d, state=%d, Heat=%s" % (0 if y["Controller_State"] == 5 else 1, y["Controller_State"],
                                           [float(y[f"Heat_{i}"]) for i in range(1, 5)]),
        y["Controller_State"] == 5 and all(y[f"Heat_{i}"] == 0 for i in range(1, 5)))

    rows = tb.run(P, 300, "SYN_01", keep_internal=True,
                  twin_override=lambda t, s: s.update(P_below_hypo_20=NAN, P_below_hypo_30=NAN))
    seen = sorted(set(int(r["_tw"]["risk_pred"]) for r in rows))
    add("AU-G1b", "P_below_hypo = NaN never triggers or releases a forecast latch (risk_pred stays 0)",
        "risk_pred seen = %s" % seen, seen == [0])

    def g1c(t, s):
        if 50 <= t < 60:
            s["HW_Cutoff"][0] = 1
        if t >= 80:
            s["Module_Temp_A"][0] = NAN
            s["Module_Temp_B"][0] = NAN
        s["Clinician_Reset"] = tb.pulse(t, 90)
    rows = tb.run(P, 100, "SYN_01", inject=g1c)
    y = rows[90]
    add("AU-G1c", "RESET with an unreadable (NaN) module temperature is blocked, not treated as cool",
        "state=%d, alert=%d" % (y["Controller_State"], y["Alert"]), y["Controller_State"] == 6 and y["Alert"] == 8)

    rows = tb.run(P, 60, "SYN_BELOW", inject=lambda t, s: s["Heater_Current"].__setitem__(0, NAN) if t >= 30 else None)
    y = rows[30]
    add("AU-G1d", "Heater_Current = NaN (sense fault) is a CH1 fault (code 109), not 0 A",
        "Channel_Fault_1=%d" % y["Channel_Fault_1"], y["Channel_Fault_1"] == 109)

    rows = tb.run(P, 60, "SYN_01", inject=lambda t, s: s.update(HW_Heartbeat_s=NAN) if t >= 30 else None)
    y = rows[30]
    add("AU-G1e", "HW_Heartbeat_s = NaN -> hardware stale -> SAFETY_SHUTDOWN (fault 8)",
        "state=%d, fault_code=%d" % (y["Controller_State"], y["fault_code"]),
        y["Controller_State"] == 6 and y["fault_code"] == 8)

    rows = tb.run(P, 60, "SYN_01", twin_override=lambda t, s: s.update(T_twin_s=NAN) if t >= 30 else None)
    y = rows[30]
    add("AU-G1f", "T_twin_s = NaN (no twin output yet) -> Data_Stale_Twin -> TWIN_DEGRADED, no shutdown",
        "state=%d, stale=%d" % (y["Controller_State"], y["Data_Stale_Twin"]),
        y["Controller_State"] == 5 and y["Data_Stale_Twin"] == 1 and y["Safety_Shutdown"] == 0)

    rows = tb.run(P, 60, "SYN_01", inject=lambda t, s: s.update(HW_Fault_Code=NAN) if t >= 30 else None)
    y = rows[30]
    add("AU-G1g", 'HW_Fault_Code = NaN is not read as "no fault": shutdown', "state=%d" % y["Controller_State"],
        y["Controller_State"] == 6)

    # G2: sensor range
    if P.get("module_temp_min_degC") is None or P.get("module_temp_max_degC") is None:
        add("AU-G2a", "Module sensor range check against Shreehan's range",
            "module_temp_min/max_degC not supplied (null). Range hook implemented; checks are DISABLED until Shreehan "
            "supplies the range", "BLOCKED")
    P2 = copy.deepcopy(P)
    P2["module_temp_min_degC"], P2["module_temp_max_degC"] = STD_LIMITS_TEST_ONLY
    rows = tb.run(P2, 60, "SYN_01", inject=lambda t, s: s["Module_Temp_A"].__setitem__(0, 10.0) if t >= 30 else None)
    y = rows[30]
    add("AU-G2b", "range hook works when a range is supplied (self-check with TEST-ONLY limits 20..60 degC, not "
        "project values)", "Channel_Fault_1=%d (102 expected for out-of-range sensor A)" % y["Channel_Fault_1"],
        y["Channel_Fault_1"] == 102)

    # G3: fault priority
    def g3a(t, s):
        if t >= 30:
            s["HW_Fault_Code"] = 3
            s["Module_Temp_A"][0] = 42.0
            s["Module_Temp_B"][0] = 42.0
            s["Module_Temp_B"][2] = NAN
            s["Module_Connected"][3] = 0
    rows = tb.run(P, 40, "SYN_BELOW", inject=g3a)
    y = rows[30]
    add("AU-G3a", "system code outranks channel codes: HW_Fault_Code 3 + CH1 over-temp + CH3 sensor B NaN + CH4 "
        "disconnected", "fault_code=%d; Channel_Fault=%s" % (y["fault_code"],
                                                            [y[f"Channel_Fault_{i}"] for i in range(1, 5)]),
        y["fault_code"] == 3)

    def g3b(t, s):
        if t >= 30:
            s["Module_Temp_B"][2] = NAN
            s["Module_Connected"][3] = 0
    rows = tb.run(P, 40, "SYN_BELOW", inject=g3b)
    y = rows[30]
    add("AU-G3b", "lower channel first among isolating faults", "fault_code=%d" % y["fault_code"],
        y["fault_code"] == 303)

    def g3c(t, s):
        if t >= 30:
            s["Module_Connected"][0] = 0
            s["Module_Temp_A"][3] = 42.0
            s["Module_Temp_B"][3] = 42.0
    rows = tb.run(P, 40, "SYN_BELOW", inject=g3c)
    y = rows[30]
    add("AU-G3c", "a shutdown-class channel fault (CH4 406) outranks a lower channel isolating fault (CH1 408) in "
        "fault_code and in the state", "fault_code=%d, state=%d" % (y["fault_code"], y["Controller_State"]),
        y["fault_code"] == 406 and y["Controller_State"] == 6)

    # G5: HW_Fault_Code 1-6 and over-current
    codes = []
    for c in range(1, 7):
        rows = tb.run(P, 40, "SYN_BELOW", inject=lambda t, s, c=c: s.update(HW_Fault_Code=c) if t >= 30 else None)
        if rows[30]["Controller_State"] == 6 and rows[30]["fault_code"] == c:
            codes.append(c)
    add("AU-G5", "HW_Fault_Code 1-6 each force SAFETY_SHUTDOWN on the same sample with the code reported",
        "codes %s" % codes, codes == [1, 2, 3, 4, 5, 6])
    rows = tb.run(P, 40, "SYN_BELOW", inject=lambda t, s: s["Heater_Current"].__setitem__(1, 2.5) if t >= 30 else None)
    y = rows[30]
    add("AU-G5b", "over-current (CH2 > i_over_A) -> shutdown, code 210",
        "state=%d, fault_code=%d" % (y["Controller_State"], y["fault_code"]),
        y["Controller_State"] == 6 and y["fault_code"] == 210)

    # G7: clinician buttons
    rows = tb.run(P, 400, "SYN_BELOW", inject=lambda t, s: s.update(Clinician_Stop=tb.pulse(t, 10)))
    st = sorted(set(int(r["Controller_State"]) for r in rows[:300]))
    add("AU-G7a", "Clinician_Stop on the exact sample the T10 dwell completes wins: no warming, inhibit starts",
        "states %s" % st, st == [0])
    rows = tb.run(P, 400, "SYN_BELOW", inject=lambda t, s: s.update(Clinician_Stop=tb.pulse(t, 5)))
    st = sorted(set(int(r["Controller_State"]) for r in rows[5:305]))
    add("AU-G7b", "Stop in NORMAL (nothing to stop) still starts the inhibit: no autonomous warming for "
        "t_stop_inhibit_s", "states in window %s" % st, st == [0])
    rows = tb.run(P, 60, "SYN_BELOW", inject=lambda t, s: s.update(Clinician_Start=tb.pulse(t, 30)))
    a, b = rows[29], rows[30]
    add("AU-G7c", "Clinician_Start in ACTIVE_WARMING only sets Clinician_Mode (state unchanged)",
        "state %d->%d, Clinician_Mode %d->%d" % (a["Controller_State"], b["Controller_State"], a["Clinician_Mode"],
                                                  b["Clinician_Mode"]),
        a["Controller_State"] == b["Controller_State"] == 2 and b["Clinician_Mode"] == 1)
    rows = tb.run(P, 60, "SYN_BELOW", inject=lambda t, s: s.update(Clinician_Start=tb.pulse(t, 30)),
                  twin_override=lambda t, s: s.update(Twin_Valid=3) if t >= 40 else None)
    y = rows[40]
    add("AU-G7d", "Clinician_Mode set in ACTIVE is honoured when the twin degrades (-> CLINICIAN_FIXED, not MONITOR)",
        "state=%d, substate=%d" % (y["Controller_State"], y["Degraded_Substate"]),
        y["Controller_State"] == 5 and y["Degraded_Substate"] == 2)

    # G9: invariants over every logged sample of every scenario run
    n, viol = 0, 0
    for k, rows in R.items():
        if k.startswith("_"):
            continue
        n += len(rows)
        viol += len([v for v in caps_violations(P, rows) if "module" not in v])
    add("AU-G9", "invariants on all %d logged samples of every run: Heat = 0 in SAFETY_SHUTDOWN and "
        "TWIN_DEGRADED.MONITOR, 0 <= Heat_i <= p_max_ch_pct_i, Heat <= mode cap, never NaN" % n,
        "%d violations" % viol, viol == 0)

    # D1 evidence: literal vs qualified open-circuit rule at small duty
    def d1(literal):
        old = prm.OPEN_RULE_QUALIFIED
        from . import blocks
        rows = None
        try:
            blocks.OPEN_RULE_QUALIFIED = not literal
            rows = tb.run(P, 120, "SYN_01", twin_override=lambda t, s: s.update(T_est=T_EST_D1),
                          inject=lambda t, s: s.update(Clinician_Start=tb.pulse(t, 5)))
        finally:
            blocks.OPEN_RULE_QUALIFIED = old
        return rows
    lit = d1(True)
    qual = d1(False)
    f_l = next((r["t_s"] for r in lit if r["Channel_Fault_1"] == 109), None)
    f_q = next((r["t_s"] for r in qual if r["Channel_Fault_1"] == 109), None)
    h = qual[6]["Heat_1"]
    add("AU-D1", "DEVIATION D1 evidence: spec-literal open-circuit rule (Heat>0 and I<i_open_max_A held) vs qualified "
        "rule, at a small duty (Clinician_Start at 5 s with T_est just below t_target: Heat ~%.2f %% -> expected "
        "current %.4f A < i_open_max_A %g A)" % (h, h / 100 * P["i_on_A"], P["i_open_max_A"]),
        "literal rule: false HEATER_OPEN at t=%s; qualified rule: first fault t=%s" % (f_l, f_q),
        f_l is not None and f_q is None)
    return out
