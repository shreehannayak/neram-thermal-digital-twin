"""TC01-TC20: scenario set-up and acceptance criteria (plan section N), one row per criterion.

A test is PASS only if every judged criterion passes; REPORTED rows are values reported, not judged.
"""
import math

import numpy as np

from . import testbench as tb
from .blocks import (ACTIVE_WARMING, CLINICIAN_WARMING, NORMAL, PREDICTIVE_WARMING, SAFETY_SHUTDOWN,
                     STATE_NAMES, TARGET_MAINTENANCE, TWIN_DEGRADED)

NAN = float("nan")
# TC17 test-only T_est glitches: 3 s, -0.5 degC, six windows. (The v2 glitch schedule could not be recovered from the
# spec; see controller/REBUILD_2026-10-18_SAI.md.)
GLITCH_STARTS = (1500, 3000, 4500, 6000, 7500, 9000)
GLITCH_LEN_S = 3
GLITCH_DEGC = -0.5
SHORT = {0: "NORMAL", 1: "PRED", 2: "ACTIVE", 3: "MAINT", 4: "CLIN", 5: "DEGRADED", 6: "SHUTDOWN"}


class Rec:
    def __init__(self, tc, title):
        self.tc, self.title, self.rows = tc, title, []

    def add(self, criterion, measured, ok):
        if ok is None:
            res = "REPORTED"
        elif ok == "BLOCKED" or ok == "EXCLUDED":
            res = ok
        else:
            res = "PASS" if ok else "FAIL"
        self.rows.append(dict(tc_id=self.tc, title=self.title, criterion=criterion, measured=measured, result=res))


def col(rows, name):
    return np.array([r[name] for r in rows], dtype=float)


def heats(rows):
    return np.array([[r[f"Heat_{i}"] for i in range(1, 5)] for r in rows])


def first(cond, start=0):
    idx = np.where(cond[start:])[0]
    return int(idx[0] + start) if len(idx) else None


def no_fault(rows, a=0, b=None):
    b = len(rows) if b is None else b
    return all(rows[t]["Safety_Shutdown"] == 0 and rows[t]["Fault_Latched"] == 0 and
               all(rows[t][f"Channel_Fault_{i}"] == 0 for i in range(1, 5)) for t in range(a, b))


def fl(x):
    return [float(round(v, 3)) for v in x]


# ------------------------------------------------------------------------------------------------
def scenarios(P):
    """Scenario runs shared by tests, logs and plots. Returns {name: callable -> rows}."""
    def tc06_inj(t, s):
        s["Clinician_Stop"] = tb.pulse(t, 1800)

    def tc07_off(t):
        if t < 900:
            return 0.0
        if t < 1100:
            return min(0.1 * (t - 900), 9.0)
        return max(9.0 - 0.2 * (t - 1100), 0.0)

    def tc07_inj(t, s):
        s["Module_Temp_A"][1] += tc07_off(t)
        s["Clinician_Reset"] = tb.pulse(t, [1050, 1250])

    def tc08_inj(t, s):
        if 120 <= t <= 199:
            s["Module_Temp_B"][2] = NAN
        s["Clinician_Reset"] = tb.pulse(t, [150, 240])

    def tc09_inj(t, s):
        if t >= 120:
            s["Module_Temp_A"][0] += 3.0

    def tc10_inj(t, s):
        if 120 <= t <= 199:
            s["Module_Connected"][3] = 0
            s["Heater_Current"][3] = 0.0
        s["Clinician_Reset"] = tb.pulse(t, [150, 240])

    def tc11_inj(t, s):
        if 120 <= t <= 179:
            s["HW_Cutoff"][1] = 1
        s["Clinician_Reset"] = tb.pulse(t, [150, 220])

    def tc12_inj(t, s):
        if 200 <= t <= 249:
            s["Heater_Current"][0] = 0.1
        s["Clinician_Reset"] = tb.pulse(t, [230, 270])

    def tc14_tw(t, s):
        if 300 <= t <= 699:
            s.update(tb.syn_twin("SYN_04V", 300, P["ts_twin_s"]))

    def tc15_inj(t, s):
        if 300 <= t <= 359:
            s["HW_Heartbeat_s"] = 300.0
        s["Clinician_Reset"] = tb.pulse(t, [330, 380])

    def tc16_inj(t, s):
        s["Clinician_Start"] = tb.pulse(t, 60)

    def tc16d_inj(t, s):
        s["Clinician_Start"] = tb.pulse(t, 60)
        if 600 <= t <= 799:
            s["Module_Temp_A"][2] = 40.0
            s["Module_Temp_B"][2] = 40.0

    def tc16_tw(t, s):
        if 600 <= t <= 799:
            s["Twin_Valid"] = 3

    def tc17_inj(t, s):
        s["Clinician_Start"] = tb.pulse(t, 60)

    def tc17_glitch(t, s):
        if any(w <= t < w + GLITCH_LEN_S for w in GLITCH_STARTS):
            s["T_est"] = s["T_est"] + GLITCH_DEGC

    return {
        "TC01": lambda: tb.run(P, 900, "SYN_01"),
        "TC02": lambda: tb.run(P, 900, "SYN_02"),
        "TC03": lambda: tb.run(P, 900, "SYN_03"),
        "TC04": lambda: tb.run(P, 43200, None, closed_loop=True),
        "TC05": lambda: tb.run(P, 900, "SYN_01", inject=lambda t, s: s.update(Clinician_Start=tb.pulse(t, 600))),
        "TC06": lambda: tb.run(P, 2400, None, inject=tc06_inj, closed_loop=True),
        "TC07": lambda: tb.run(P, 1320, None, inject=tc07_inj, closed_loop=True),
        "TC08": lambda: tb.run(P, 330, "SYN_BELOW", inject=tc08_inj),
        "TC09": lambda: tb.run(P, 300, "SYN_BELOW", inject=tc09_inj),
        "TC10": lambda: tb.run(P, 330, "SYN_BELOW", inject=tc10_inj),
        "TC11": lambda: tb.run(P, 300, "SYN_BELOW", inject=tc11_inj),
        "TC12": lambda: tb.run(P, 300, "SYN_01", inject=tc12_inj),
        "TC13": lambda: tb.run(P, 900, "SYN_04"),
        "TC13_control": lambda: tb.run(P, 900, "SYN_04V"),
        "TC14": lambda: tb.run(P, 900, "SYN_04V", twin_override=tc14_tw),
        "TC15": lambda: tb.run(P, 420, "SYN_BELOW", inject=tc15_inj),
        "TC16": lambda: tb.run(P, 900, "SYN_01", inject=tc16_inj, twin_override=tc16_tw),
        "TC16_derate": lambda: tb.run(P, 900, "SYN_01", inject=tc16d_inj, twin_override=tc16_tw),
        "TC17": lambda: tb.run(P, 10800, None, inject=tc17_inj, closed_loop=True, T0=37.0,
                                twin_override=tc17_glitch),
        "TC17_stress": lambda: tb.run(P, 10800, None, inject=tc17_inj, closed_loop=True, T0=37.0,
                                      twin_noise_scale=6.0, twin_override=tc17_glitch),
        "TC18_0.5": lambda: tb.run(P, 57600, None, closed_loop=True, k_scale=0.5),
        "TC18_1.0": lambda: tb.run(P, 57600, None, closed_loop=True, k_scale=1.0),
        "TC18_2.0": lambda: tb.run(P, 57600, None, closed_loop=True, k_scale=2.0),
    }


# ------------------------------------------------------------------------------------------------
def tc01(P, R):
    r = Rec("TC01", "No action when stable (SYN_01)")
    rows = R["TC01"]
    st = col(rows, "Controller_State")
    r.add("NORMAL throughout", "states seen = %s" % [STATE_NAMES[int(s)] for s in sorted(set(st))],
          set(st) == {NORMAL})
    r.add("all Heat_i = 0 throughout", "max Heat = %g" % heats(rows).max(), heats(rows).max() == 0)
    al = sorted(set(int(a) for a in col(rows, "Alert")))
    r.add("Alert = NONE throughout", "alerts seen = %s" % al, al == [0])
    r.add("no channel fault, no shutdown, Fault_Latched=0 throughout", "yes" if no_fault(rows) else "no",
          no_fault(rows))
    return r


def tc02(P, R):
    r = Rec("TC02", "Predictive trigger (SYN_02)")
    rows = R["TC02"]
    st = col(rows, "Controller_State")
    H = heats(rows)
    before = sorted(set(int(x) for x in st[:300]))
    r.add("NORMAL with Heat=0 before the P20 crossing", "states before t=300: %s" % before,
          before == [0] and H[:300].max() == 0)
    te = first(st == PREDICTIVE_WARMING)
    lim = 300 + P["n_confirm_updates"] * P["ts_twin_s"] + 1
    r.add("PREDICTIVE_WARMING entered within n_confirm_updates twin minutes + 1 s of the crossing (t <= %d s) and "
          "not before it" % lim,
          "entered at t = %s s (crossing at 300 s; confirm updates = %d; dwell %d s)" %
          (te, P["n_confirm_updates"], P["t_dwell_min_s"]), te is not None and 300 <= te <= lim)
    tr = rows[te]["Trigger_Reason"]
    r.add("Trigger_Reason = FORECAST_P20 at entry", "Trigger_Reason = %d (1 = FORECAST_P20)" % tr, tr == 1)
    hin = H[st == PREDICTIVE_WARMING]
    r.add("0 < Heat_i <= d_pred_max_pct (%g %%) on all four channels while in PREDICTIVE_WARMING" % P["d_pred_max_pct"],
          "Heat range in state = [%.3f, %.3f] %%" % (hin.min(), hin.max()),
          hin.min() > 0 and hin.max() <= P["d_pred_max_pct"])
    r.add("PREDICTIVE_WARMING does not exit on the forecast (stays to end of run)",
          "state at t=%d: %s" % (len(rows) - 1, STATE_NAMES[int(st[-1])]), bool((st[te:] == PREDICTIVE_WARMING).all()))
    a = rows[te + 1]["Alert"]
    r.add("Alert = FORECAST_RISK_20_30 while in PREDICTIVE_WARMING", "Alert at entry+1 = %d" % a,
          a == 1 and all(rows[t]["Alert"] == 1 for t in range(te, len(rows))))
    r.add("four channels fault-free (no open-circuit etc.) and no shutdown throughout",
          "yes" if no_fault(rows) else "no", no_fault(rows))
    err = max(abs(rows[t][f"Heater_Current_{i}"] - rows[t - 1][f"Heat_{i}"] / 100 * P["i_on_A"])
              for t in range(1, len(rows)) for i in range(1, 5))
    r.add("healthy-hardware feedback Heater_Current_i = (Heat_i/100)*i_on_A (applied one command period later)",
          "max |error| = %.2e A" % err, err < 1e-12)
    return r


def tc03(P, R):
    r = Rec("TC03", "+60 min horizon is alert-only (SYN_03)")
    rows = R["TC03"]
    al = col(rows, "Alert")
    t1 = first(al == 2)
    r.add("Alert = FORECAST_RISK_60_INFO raised once only P60 >= p_trigger",
          "first raised at t = %s s (P60 crosses at 120 s)" % t1, t1 == 120)
    r.add("Alert stays FORECAST_RISK_60_INFO after the crossing", "yes" if (al[120:] == 2).all() else "no",
          bool((al[120:] == 2).all()))
    st = col(rows, "Controller_State")
    r.add("NORMAL throughout", "states seen = %s" % [STATE_NAMES[int(s)] for s in sorted(set(st))],
          set(st) == {NORMAL})
    r.add("all Heat_i = 0 throughout", "max Heat = %g" % heats(rows).max(), heats(rows).max() == 0)
    r.add("FORECAST_RISK_20_30 never raised (only P60 high)", "yes" if not (al == 1).any() else "no",
          not (al == 1).any())
    return r


def closed_loop_metrics(P, rows):
    T = col(rows, "T_plant")
    st = col(rows, "Controller_State")
    tt = first(T >= P["t_target_degC"])
    return T, st, tt


def tc04(P, R):
    r = Rec("TC04", "Active recovery to target (STANDIN closed loop)")
    rows = R["TC04"]
    T, st, tt = closed_loop_metrics(P, rows)
    H = heats(rows)
    r.add("start below t_hypo_degC", "T_plant(0) = %.2f degC < %.1f" % (T[0], P["t_hypo_degC"]),
          T[0] < P["t_hypo_degC"])
    ta = first(st == ACTIVE_WARMING)
    r.add("ACTIVE_WARMING entered", "first ACTIVE at t = %s s" % ta, ta is not None)
    tm = first(st == TARGET_MAINTENANCE)
    r.add("ACTIVE_WARMING transitions to TARGET_MAINTENANCE with Trigger_Reason = TARGET_REACHED",
          "entered MAINT at t = %s s from %s; reason = %d" % (tm, STATE_NAMES[int(st[tm - 1])],
                                                              rows[tm]["Trigger_Reason"]),
          tm is not None and st[tm - 1] == ACTIVE_WARMING and rows[tm]["Trigger_Reason"] == 5)
    hm = H[st == TARGET_MAINTENANCE].max()
    r.add("max Heat in TARGET_MAINTENANCE <= d_maint_max_pct (%g %%)" % P["d_maint_max_pct"], "%.2f %%" % hm,
          hm <= P["d_maint_max_pct"])
    viol = caps_violations(P, rows)
    r.add("no shutdown, no channel fault, Heat within per-mode and per-channel caps, module temp < trip",
          "none" if not viol else "; ".join(viol[:3]), (not viol) and no_fault(rows))
    est = col(rows, "T_est")
    r.add("time-to-target (T_plant >= t_target_degC) - reported, not judged", "%.2f h (%d s)" % (tt / 3600, tt), None)
    if est is not None:
        te = first(est >= P["t_target_degC"])
        r.add("time-to-target (T_est >= t_target_degC)", "%.2f h (%d s)" % (te / 3600, te), None)
    r.add("overshoot above t_target (max T_plant - t_target)", "%.3f degC" % (T.max() - P["t_target_degC"]), None)
    r.add("final T_plant after %d h" % round((len(rows) - 1) / 3600), "%.3f degC" % T[-1], None)
    r.add("flat passive trajectory (plant_passive.* not supplied by Sai)", "T_pass = T0 = %.1f degC, PLACEHOLDER" % T[0],
          None)
    return r


def caps_violations(P, rows):
    out = []
    capmap = {PREDICTIVE_WARMING: P["d_pred_max_pct"], ACTIVE_WARMING: P["d_active_max_pct"],
              TARGET_MAINTENANCE: P["d_maint_max_pct"], CLINICIAN_WARMING: P["d_active_max_pct"]}
    for r_ in rows:
        s = r_["Controller_State"]
        for i in range(1, 5):
            h = r_[f"Heat_{i}"]
            if h != h or h < 0 or h > P["p_max_ch_pct"][i - 1]:
                out.append("t=%d Heat_%d=%g" % (r_["t_s"], i, h))
            if s in capmap and h > capmap[s] + 1e-9:
                out.append("t=%d Heat_%d above mode cap" % (r_["t_s"], i))
            if s == TWIN_DEGRADED and r_["Degraded_Substate"] == 2 and h > P["d_fallback_pct"] + 1e-9:
                out.append("t=%d Heat_%d above fallback" % (r_["t_s"], i))
            if s in (NORMAL, SAFETY_SHUTDOWN) and h != 0:
                out.append("t=%d Heat_%d != 0 in %s" % (r_["t_s"], i, STATE_NAMES[s]))
            if s == TWIN_DEGRADED and r_["Degraded_Substate"] == 1 and h != 0:
                out.append("t=%d Heat_%d != 0 in MONITOR" % (r_["t_s"], i))
            for x in "AB":
                v = r_[f"Module_Temp_{i}_{x}"]
                if v == v and v >= P["t_mod_trip_degC"]:
                    out.append("t=%d module %d%s >= trip" % (r_["t_s"], i, x))
    return out


def tc05(P, R):
    r = Rec("TC05", "Clinician early start (SYN_01, Start at 600 s)")
    rows = R["TC05"]
    st = col(rows, "Controller_State")
    H = heats(rows)
    r.add("NORMAL with Heat=0 before the clinician event (T_est between t_hypo and t_target, no autonomous trigger)",
          "T_est = 36.4 degC", bool((st[:600] == 0).all() and H[:600].max() == 0))
    te = first(st == CLINICIAN_WARMING)
    r.add("CLINICIAN_WARMING entered within 1 s of the 600 s Clinician_Start pulse", "entered at t = %s s" % te,
          te is not None and 600 <= te <= 601)
    tr = rows[te]["Trigger_Reason"]
    r.add("Trigger_Reason = CLINICIAN_START", "Trigger_Reason = %d (4)" % tr, tr == 4)
    cm = rows[te]["Clinician_Mode"]
    r.add("Clinician_Mode = 1", "%d" % cm, cm == 1)
    # independent PI re-computation
    integ, dmax = 0.0, 0.0
    e = P["t_target_degC"] - 36.4
    for t in range(te, len(rows)):
        trial_i = integ + P["ki_pct_per_degC_s"] * e
        trial = P["kp_pct_per_degC"] * e + trial_i
        if 0 <= trial <= P["d_active_max_pct"]:
            integ = trial_i
        dref = min(max(trial, 0), P["d_active_max_pct"])
        dmax = max(dmax, abs(rows[t]["Demand_Global"] - dref))
    D = col(rows, "Demand_Global")
    r.add("Demand_Global equals an independent PI re-computation (kp*e + integrator, cap d_active_max_pct)",
          "max |D - D_ref| = %.2e %%; D at entry = %.3f %%, after 5 min = %.2f %%" % (dmax, D[te], D[te + 300]),
          dmax < 1e-9)
    hent, hpl = H[te, 0], H[-1, 0]
    capok = np.allclose(H[te:], np.minimum(D[te:, None], np.array(P["p_max_ch_pct"])[None, :]))
    r.add("Heat_i = min(D, p_max_ch_pct_i) (channel cap applied, not hard-coded to 100 %)",
          "Heat at entry = %.3f %%, plateau = %.1f %%" % (hent, hpl), bool(capok))
    r.add("Heat rises gradually with the PI integrator (entry value < plateau)", "%.2f %% -> %.2f %%" % (hent, hpl),
          hent < hpl)
    r.add("no channel fault, no shutdown, Fault_Latched=0 throughout", "yes" if no_fault(rows) else "no",
          no_fault(rows))
    return r


def tc06(P, R):
    r = Rec("TC06", "Clinician STOP mid-warming (TC04 scenario)")
    rows = R["TC06"]
    st = col(rows, "Controller_State")
    H = heats(rows)
    r.add("warming in progress just before STOP (ACTIVE_WARMING, Heat > 0)",
          "state = %s, Heat_1 = %.1f %%" % (STATE_NAMES[int(st[1799])], H[1799, 0]),
          st[1799] == ACTIVE_WARMING and H[1799, 0] > 0)
    r.add("NORMAL and all Heat = 0 within 1 s of Clinician_Stop",
          "NORMAL at t = 1800 s; Heat = %s" % [float(h) for h in H[1800]], st[1800] == NORMAL and H[1800].max() == 0)
    r.add("Trigger_Reason = CLINICIAN_STOP and Alert = CLINICIAN_STOP_ACK on the STOP sample",
          "reason = %d, alert = %d" % (rows[1800]["Trigger_Reason"], rows[1800]["Alert"]),
          rows[1800]["Trigger_Reason"] == 7 and rows[1800]["Alert"] == 7)
    win = range(1800, 1800 + P["t_stop_inhibit_s"])
    sw = sorted(set(int(st[t]) for t in win))
    tw = [rows[t] for t in win]
    r.add("no autonomous re-entry and Heat = 0 for t_stop_inhibit_s (%d s) although the patient stays below t_hypo"
          % P["t_stop_inhibit_s"], "states in window = %s; below_hypo true throughout = %s" %
          (sw, all(R["_TC06_below"][t] for t in win)), sw == [0] and H[1800:2100].max() == 0)
    tre = first(st != NORMAL, 1801)
    r.add("autonomous re-entry happens only after the inhibit expires (shows the inhibit was the blocker)",
          "first re-entry at t = %s s (inhibit ends at %d s)" % (tre, 1800 + P["t_stop_inhibit_s"]),
          tre is not None and tre >= 2100)
    r.add("no channel fault, no shutdown, Fault_Latched=0 throughout", "yes" if no_fault(rows) else "no",
          no_fault(rows))
    return r


def tc07(P, R):
    r = Rec("TC07", "Over-temperature shutdown (STANDIN; CH2 sensor A ramp)")
    rows = R["TC07"]
    st = col(rows, "Controller_State")
    H = heats(rows)
    A2 = col(rows, "Module_Temp_2_A")
    tc = first(A2 >= P["t_mod_trip_degC"])
    tsd = first(st == SAFETY_SHUTDOWN)
    r.add("all four channels are actively heating when the ramp starts, and CH1/CH3/CH4 still heat one sample before "
          "the trip (CH2 was already isolated by SENSOR_DISAGREE 205) - so the shutdown interrupts real heating",
          "Heat_1..4 at t=899 s = %s; at t=%d s = %s" % (fl(H[899]), tsd - 1, fl(H[tsd - 1])),
          H[899].min() > 0 and H[tsd - 1][[0, 2, 3]].min() > 0)
    r.add("SAFETY_SHUTDOWN entered within 1 s of the module sensor crossing t_mod_trip_degC",
          "sensor crossed %g degC at t = %d s; shutdown at t = %d s" % (P["t_mod_trip_degC"], tc, tsd),
          tsd is not None and 0 <= tsd - tc <= 1)
    rb = [t for t in range(len(rows)) if rows[t]["Clinician_Mode"] >= 0 and R["_TC07_reset"][t]]
    t_ok = rb[-1]
    r.add("all four Heat = 0 on the shutdown sample and on every sample until RESET",
          "max Heat over t = %d..%d s: %g" % (tsd, t_ok - 1, H[tsd:t_ok].max()), H[tsd:t_ok].max() == 0)
    x = rows[tsd]
    r.add("Trigger_Reason = SAFETY_FAULT, fault_code = 206 (CH2 OVERTEMP_SW), Alert = SAFETY_SHUTDOWN",
          "reason %d, fault_code %d, alert %d" % (x["Trigger_Reason"], x["fault_code"], x["Alert"]),
          x["Trigger_Reason"] == 8 and x["fault_code"] == 206 and x["Alert"] == 5)
    y = rows[rb[0]]
    r.add("RESET with the over-temperature still present -> RESET_BLOCKED, stays in SAFETY_SHUTDOWN",
          "t=%d: Module_Temp_2_A = %.1f degC, alert = %d, state = %s" % (rb[0], y["Module_Temp_2_A"], y["Alert"],
                                                                         STATE_NAMES[y["Controller_State"]]),
          y["Alert"] == 8 and y["Controller_State"] == SAFETY_SHUTDOWN)
    cool = first((col(rows, "Module_Temp_2_A") < P["t_mod_reset_degC"]) &
                 (col(rows, "Module_Temp_2_B") < P["t_mod_reset_degC"]), rb[0])
    z = rows[cool + 5]
    r.add("fault remains latched after the module has cooled below t_mod_reset_degC (no RESET pressed)",
          "all CH2 sensors < %g degC from t = %d s; at t = %d s: state %s, Fault_Latched %d, Channel_Fault_2 = %d" %
          (P["t_mod_reset_degC"], cool, cool + 5, STATE_NAMES[z["Controller_State"]], z["Fault_Latched"],
           z["Channel_Fault_2"]),
          z["Controller_State"] == SAFETY_SHUTDOWN and z["Fault_Latched"] == 1 and z["Channel_Fault_2"] == 206)
    w = rows[t_ok]
    r.add("RESET after the condition clears -> NORMAL (Trigger_Reason = CLINICIAN_RESET), latches cleared",
          "t=%d: state %s, reason %d, Fault_Latched %d, Channel_Fault_2 %d" %
          (t_ok, STATE_NAMES[w["Controller_State"]], w["Trigger_Reason"], w["Fault_Latched"], w["Channel_Fault_2"]),
          w["Controller_State"] == NORMAL and w["Trigger_Reason"] == 11 and w["Fault_Latched"] == 0)
    t205 = first(col(rows, "Channel_Fault_2") == 205)
    r.add("fault-priority evidence: first latched CH2 code, then the shutdown code",
          "t=%d s: Channel_Fault_2 = 205 (205 SENSOR_DISAGREE after dwell, since only sensor A ramps); shutdown "
          "latches 206 and outranks it" % t205, None)
    return r


def _iso_test(P, R, name, title, ch, code, label, t_f, resets, recover_t):
    r = Rec(name, title)
    rows = R[name]
    H = heats(rows)
    i = ch - 1
    others = [k for k in range(4) if k != i]
    pre = H[110:121].mean(axis=0) if name == "TC08" else H[t_f - 1]
    return r, rows, H, i, others, pre


def tc08(P, R):
    r = Rec("TC08", "Sensor fault isolates one channel (CH3 sensor B NaN)")
    rows = R["TC08"]
    H = heats(rows)
    pre = H[110:120].mean(axis=0)
    r.add('all four channels at a steady non-zero command before the fault (so "unchanged" is meaningful)',
          "Heat_1..4 mean over 110..120 s = %s %%" % fl(pre), pre.min() > 0 and np.ptp(H[110:120], axis=0).max() == 0)
    x = rows[120]
    r.add("Channel_Fault_3 = 303 (SENSOR_B_OPEN, CH3) set within 1 s of the NaN",
          "Channel_Fault_3 at t=120: %d; Channel_Fault_1,2,4 = %s" % (x["Channel_Fault_3"],
                                                                   [x["Channel_Fault_1"], x["Channel_Fault_2"],
                                                                    x["Channel_Fault_4"]]),
          x["Channel_Fault_3"] == 303 and x["Channel_Fault_1"] == x["Channel_Fault_2"] == x["Channel_Fault_4"] == 0)
    lat = [t for t in range(len(rows)) if rows[t]["Channel_Fault_3"]]
    r.add("Heat_3 = 0 within 1 s and for as long as the fault is latched", "Heat_3 at t=120: %.2f" % H[120, 2],
          H[lat, 2].max() == 0)
    dev = np.abs(H[120:, [0, 1, 3]] - pre[[0, 1, 3]]).max()
    r.add("Heat_1, Heat_2, Heat_4 unchanged (equal to their pre-fault value)", "max deviation = %.2e %%" % dev,
          dev == 0)
    al = sorted(set(int(rows[t]["Alert"]) for t in range(120, 240)))
    r.add("Alert = CHANNEL_FAULT from the fault sample until the latch clears", "alerts in 120..239: %s" % al,
          al == [4])
    r.add("fault_code = 303, Fault_Latched = 1, no system shutdown (channel isolation only)",
          "fault_code %d, Fault_Latched %d, shutdown %d" % (x["fault_code"], x["Fault_Latched"], x["Safety_Shutdown"]),
          x["fault_code"] == 303 and x["Fault_Latched"] == 1 and x["Safety_Shutdown"] == 0)
    y = rows[151]
    r.add("RESET while the sensor is still NaN does not clear the latch",
          "t=151: Channel_Fault_3 = %d, Heat_3 = %.1f" % (y["Channel_Fault_3"], y["Heat_3"]), y["Channel_Fault_3"] == 303)
    y = rows[220]
    r.add("latch persists after the sensor recovers (no RESET)",
          "t=220: Channel_Fault_3 = %d, Heat_3 = %.1f" % (y["Channel_Fault_3"], y["Heat_3"]), y["Channel_Fault_3"] == 303)
    y = rows[241]
    r.add("RESET with a valid sensor clears CH3, Alert returns to NONE, Heat_3 resumes",
          "t=241: Channel_Fault_3 = %d, Heat_3 = %.1f, Alert = %d" % (y["Channel_Fault_3"], y["Heat_3"], y["Alert"]),
          y["Channel_Fault_3"] == 0 and y["Heat_3"] > 0 and y["Alert"] == 0)
    return r


def tc09(P, R):
    r = Rec("TC09", "Sensor disagreement (CH1 sensor A offset)")
    rows = R["TC09"]
    H = heats(rows)
    r.add("injected offset exceeds dt_sensor_disagree_degC", "offset 3.0 degC > %.1f degC" %
          P["dt_sensor_disagree_degC"], 3.0 > P["dt_sensor_disagree_degC"])
    y = rows[129]
    r.add("t_dwell_min_s (%d s) is honoured: CH1 not yet isolated one sample before the dwell elapses" %
          P["t_dwell_min_s"],
          "t=129: Channel_Fault_1 = %d, Heat_1 = %.1f %% (derated by the hot sensor reading, > 0)" %
          (y["Channel_Fault_1"], y["Heat_1"]), y["Channel_Fault_1"] == 0 and y["Heat_1"] > 0)
    ti = first(col(rows, "Channel_Fault_1") != 0)
    r.add("CH1 off after t_dwell_min_s: Channel_Fault_1 = 105 and Heat_1 = 0",
          "isolated at t = %d s (offset applied at 120 s); code %d" % (ti, rows[ti]["Channel_Fault_1"]),
          ti == 130 and rows[ti]["Channel_Fault_1"] == 105 and H[ti:, 0].max() == 0)
    dev = np.abs(H[120:, 1:] - H[119, 1:]).max()
    oth = any(rows[t][f"Channel_Fault_{k}"] for t in range(len(rows)) for k in (2, 3, 4))
    r.add("Heat_2..4 unchanged and no other channel fault", "max deviation = %.2e %%" % dev, dev == 0 and not oth)
    r.add("Alert = CHANNEL_FAULT after isolation, no shutdown", "alert at t=131: %d" % rows[131]["Alert"],
          rows[131]["Alert"] == 4 and col(rows, "Safety_Shutdown").max() == 0)
    return r


def tc10(P, R):
    r = Rec("TC10", "Module disconnected (Module_Connected_4 = 0)")
    rows = R["TC10"]
    H = heats(rows)
    y = rows[120]
    r.add("Heat_4 = 0 and Channel_Fault_4 = 408 (DISCONNECTED) within 1 s",
          "t=120: Heat_4 = %.1f, code = %d" % (y["Heat_4"], y["Channel_Fault_4"]),
          y["Heat_4"] == 0 and y["Channel_Fault_4"] == 408)
    dev = np.abs(H[120:, :3] - H[119, :3]).max()
    al = sorted(set(int(rows[t]["Alert"]) for t in range(120, 240)))
    r.add("Heat_1..3 unchanged; Alert = CHANNEL_FAULT; no shutdown",
          "max deviation %.2e %%; alerts %s" % (dev, al), dev == 0 and al == [4] and col(rows, "Safety_Shutdown").max() == 0)
    seen = sorted(set(int(v) for v in col(rows, "Channel_Fault_4")))
    r.add("no spurious HEATER_OPEN (409) from the dropped current on the disconnect sample",
          "Channel_Fault_4 values seen = %s" % seen, 409 not in seen)
    y = rows[151]
    r.add("RESET while still disconnected does not release the latch",
          "t=151: code %d, Heat_4 %.1f" % (y["Channel_Fault_4"], y["Heat_4"]), y["Channel_Fault_4"] == 408)
    y = rows[220]
    r.add("latch persists after reconnection until RESET is pressed",
          "t=220: Module_Connected_4 = %d, code %d, Heat_4 %.1f" % (y["Module_Connected_4"], y["Channel_Fault_4"],
                                                                   y["Heat_4"]),
          y["Module_Connected_4"] == 1 and y["Channel_Fault_4"] == 408)
    y = rows[241]
    r.add("RESET after reconnection clears CH4 and Heat_4 resumes",
          "t=241: code %d, Heat_4 %.1f" % (y["Channel_Fault_4"], y["Heat_4"]), y["Channel_Fault_4"] == 0 and y["Heat_4"] > 0)
    return r


def _shutdown_common(r, rows, t_on, code, label, rb, rclear, t_clear_check, late_check_t):
    return


def tc11(P, R):
    r = Rec("TC11", "Hardware cutoff reported (HW_Cutoff_2 = 1)")
    rows = R["TC11"]
    H = heats(rows)
    st = col(rows, "Controller_State")
    r.add("all channels heating before the cutoff report", "Heat_1..4 = %s" % fl(H[119]), H[119].min() > 0)
    tsd = first(st == SAFETY_SHUTDOWN)
    r.add("SAFETY_SHUTDOWN within 1 s of HW_Cutoff_2 = 1; all Heat = 0 until RESET", "shutdown at t = %d s" % tsd,
          tsd is not None and tsd <= 121 and H[tsd:220].max() == 0)
    y = rows[tsd]
    r.add("fault_code = 207 (OVERTEMP_HW_CUTOFF, CH2) and Alert = SAFETY_SHUTDOWN",
          "fault_code %d, alert %d" % (y["fault_code"], y["Alert"]), y["fault_code"] == 207 and y["Alert"] == 5)
    y = rows[150]
    r.add("RESET while the cutoff is still reported -> RESET_BLOCKED, stays shut down",
          "t=150: alert %d, state %s" % (y["Alert"], STATE_NAMES[y["Controller_State"]]),
          y["Alert"] == 8 and y["Controller_State"] == SAFETY_SHUTDOWN)
    y = rows[200]
    r.add("fault remains latched after the cutoff report clears (no RESET)",
          "t=200: state %s, Fault_Latched %d, HW_Cutoff_2 %d" % (STATE_NAMES[y["Controller_State"]], y["Fault_Latched"],
                                                                y["HW_Cutoff_2"]),
          y["Controller_State"] == SAFETY_SHUTDOWN and y["Fault_Latched"] == 1 and y["HW_Cutoff_2"] == 0)
    y = rows[220]
    r.add("RESET after clearing -> NORMAL, latches cleared",
          "t=220: state %s, Fault_Latched %d" % (STATE_NAMES[y["Controller_State"]], y["Fault_Latched"]),
          y["Controller_State"] == NORMAL and y["Fault_Latched"] == 0)
    return r


def tc12(P, R):
    r = Rec("TC12", "Stuck-on driver (CH1 current > i_stuck_A with Heat_1 = 0)")
    rows = R["TC12"]
    st = col(rows, "Controller_State")
    r.add("injected current exceeds i_stuck_A while Heat_1 = 0 commanded",
          "0.1 A > %g A; Heat_1 at t=200 = %.1f" % (P["i_stuck_A"], rows[200]["Heat_1"]),
          0.1 > P["i_stuck_A"] and rows[200]["Heat_1"] == 0)
    tsd = first(st == SAFETY_SHUTDOWN)
    r.add("SAFETY_SHUTDOWN within 2 s of the stuck current appearing",
          "shutdown at t = %d s (current injected at 200 s)" % tsd, tsd is not None and tsd <= 201)
    r.add('"for 2 steps" rule respected: not shut down on the first over-threshold sample',
          "state at t=200: %s" % STATE_NAMES[int(st[200])], st[200] != SAFETY_SHUTDOWN)
    y = rows[tsd]
    r.add("fault_code = 111 (STUCK_ON, CH1); Channel_Fault_1 = 111; all Heat = 0",
          "fault_code %d, Channel_Fault_1 %d" % (y["fault_code"], y["Channel_Fault_1"]),
          y["fault_code"] == 111 and y["Channel_Fault_1"] == 111 and heats(rows)[tsd:270].max() == 0)
    r.add("RESET while the stuck current persists -> RESET_BLOCKED", "t=230: alert %d" % rows[230]["Alert"],
          rows[230]["Alert"] == 8)
    y = rows[260]
    r.add("latched after the current stops", "t=260: state %s, Fault_Latched %d" %
          (STATE_NAMES[y["Controller_State"]], y["Fault_Latched"]),
          y["Controller_State"] == SAFETY_SHUTDOWN and y["Fault_Latched"] == 1)
    r.add("RESET after clearing -> NORMAL", "t=270: state %s" % STATE_NAMES[rows[270]["Controller_State"]],
          rows[270]["Controller_State"] == NORMAL)
    return r


def tc13(P, R):
    r = Rec("TC13", "Twin unreliable: no autonomous warming (SYN_04)")
    rows, ctl = R["TC13"], R["TC13_control"]
    Hc = heats(ctl)
    r.add("counterfactual: with the twin VALID throughout, the same signals DO request autonomous warming in the "
          "degraded window", "control run: max Heat in 300..600 s = %.1f %%, state %s" %
          (Hc[300:601].max(), STATE_NAMES[ctl[450]["Controller_State"]]), Hc[300:601].max() > 0)
    y = rows[299]
    r.add("warming is already running when the twin degrades (so the drop to zero is meaningful)",
          "t=299: state %s, Heat_1 = %.1f %%" % (STATE_NAMES[y["Controller_State"]], y["Heat_1"]), y["Heat_1"] > 0)
    st = col(rows, "Controller_State")
    te = first(st == TWIN_DEGRADED)
    y = rows[te]
    r.add("TWIN_DEGRADED.MONITOR entered within 1 s of Twin_Valid = DEGRADED",
          "entered at t = %d s, Degraded_Substate = %d, Trigger_Reason = %d" % (te, y["Degraded_Substate"],
                                                                                y["Trigger_Reason"]),
          te <= 301 and y["Degraded_Substate"] == 1 and y["Trigger_Reason"] == 9)
    al = sorted(set(int(rows[t]["Alert"]) for t in range(300, 600)))
    r.add("Alert = TWIN_DEGRADED for the whole degraded window", "alerts = %s" % al, al == [3])
    H = heats(rows)
    r.add("all Heat = 0 for the whole degraded window (no autonomous warming)", "max Heat = %g %%" % H[300:600].max(),
          H[300:600].max() == 0)
    tn = first(st == NORMAL, 600)
    r.add("NORMAL once VALID has been sustained for t_recover_s (Trigger_Reason = TWIN_RECOVERED)",
          "VALID from 600 s; NORMAL at t = %d s (t_recover_s = %d); reason %d" % (tn, P["t_recover_s"],
                                                                                 rows[tn]["Trigger_Reason"]),
          tn == 600 + P["t_recover_s"] and rows[tn]["Trigger_Reason"] == 10)
    r.add("still no heating while VALID is being re-established (t_recover_s hold)",
          "max Heat 600..%d s = %g" % (tn, H[600:tn + 1].max()), H[600:tn + 1].max() == 0)
    tr = first(st != NORMAL, tn)
    r.add("after recovery the confirmed forecast may legitimately re-trigger warming (not part of the criteria)",
          "first non-NORMAL after recovery: t = %s" % tr, None)
    return r


def tc14(P, R):
    r = Rec("TC14", "Twin stale (T_twin_s frozen)")
    rows = R["TC14"]
    y = rows[299]
    r.add("warming running when the twin output freezes",
          "t=299: state %s, Heat_1 %.1f %%" % (STATE_NAMES[y["Controller_State"]], y["Heat_1"]), y["Heat_1"] > 0)
    st = col(rows, "Controller_State")
    te = first(st == TWIN_DEGRADED)
    age = te - 300
    r.add("TWIN_DEGRADED entered after data_stale_twin_s (age of T_twin_s > data_stale_twin_s), not before",
          "T_twin_s frozen at 300 s; entered at t = %d s; age at entry = %d s (limit %d s)" %
          (te, age, P["data_stale_twin_s"]), age == P["data_stale_twin_s"] + 1)
    y = rows[te]
    r.add("Data_Stale_Twin = 1, Trigger_Reason = TWIN_DEGRADED, Alert = TWIN_DEGRADED, fault_code = 7 (informational)",
          "stale %d, reason %d, alert %d, fault_code %d" % (y["Data_Stale_Twin"], y["Trigger_Reason"], y["Alert"],
                                                            y["fault_code"]),
          y["Data_Stale_Twin"] == 1 and y["Trigger_Reason"] == 9 and y["Alert"] == 3 and y["fault_code"] == 7)
    H = heats(rows)
    stale = col(rows, "Data_Stale_Twin") == 1
    r.add("all Heat = 0 while stale", "max Heat %g" % H[stale].max(), H[stale].max() == 0)
    ok = col(rows, "Safety_Shutdown").max() == 0 and col(rows, "Data_Stale_HW").max() == 0 and \
        col(rows, "Fault_Latched").max() == 0
    r.add("NO hardware shutdown: Safety_Shutdown = 0, Data_Stale_HW = 0, Fault_Latched = 0 throughout",
          "yes" if ok else "no", bool(ok))
    tn = first(st == NORMAL, te)
    r.add("automatic recovery (no latch): NORMAL t_recover_s after T_twin_s updates again",
          "twin resumes at 700 s; NORMAL at t = %d s" % tn, tn == 700 + P["t_recover_s"])
    return r


def tc15(P, R):
    r = Rec("TC15", "Hardware stale (HW_Heartbeat_s frozen)")
    rows = R["TC15"]
    H = heats(rows)
    st = col(rows, "Controller_State")
    r.add("warming running when the heartbeat freezes", "t=299: Heat_1..4 = %s" % fl(H[299]), H[299].min() > 0)
    tsd = first(st == SAFETY_SHUTDOWN)
    r.add("SAFETY_SHUTDOWN after data_stale_hw_s (heartbeat age > limit), not before",
          "heartbeat frozen at 300 s; shutdown at t = %d s; age = %d s (limit %d s)" % (tsd, tsd - 300,
                                                                                     P["data_stale_hw_s"]),
          tsd - 300 == P["data_stale_hw_s"] + 1)
    y = rows[tsd]
    r.add("fault_code = 8 (HW_DATA_STALE), Data_Stale_HW = 1, Trigger_Reason = SAFETY_FAULT, Alert = SAFETY_SHUTDOWN, "
          "all Heat = 0", "fault_code %d, stale %d, reason %d, alert %d, Heat %s" %
          (y["fault_code"], y["Data_Stale_HW"], y["Trigger_Reason"], y["Alert"], [float(h) for h in H[tsd]]),
          y["fault_code"] == 8 and y["Data_Stale_HW"] == 1 and y["Trigger_Reason"] == 8 and y["Alert"] == 5 and
          H[tsd].max() == 0)
    r.add("Data_Stale_Twin stays 0 (this is a hardware, not a twin, fault)",
          "yes" if col(rows, "Data_Stale_Twin").max() == 0 else "no", col(rows, "Data_Stale_Twin").max() == 0)
    r.add("RESET while the heartbeat is still stale -> RESET_BLOCKED", "t=330: alert %d" % rows[330]["Alert"],
          rows[330]["Alert"] == 8)
    y = rows[370]
    r.add("latched after the heartbeat returns (no RESET)", "t=370: state %s, Data_Stale_HW %d, Fault_Latched %d" %
          (STATE_NAMES[y["Controller_State"]], y["Data_Stale_HW"], y["Fault_Latched"]),
          y["Controller_State"] == SAFETY_SHUTDOWN and y["Data_Stale_HW"] == 0 and y["Fault_Latched"] == 1)
    r.add("RESET + heartbeat back -> NORMAL", "t=380: state %s" % STATE_NAMES[rows[380]["Controller_State"]],
          rows[380]["Controller_State"] == NORMAL)
    return r


def tc16(P, R):
    r = Rec("TC16", "Twin degraded during clinician warming")
    rows = R["TC16"]
    y = rows[599]
    r.add("CLINICIAN_WARMING with PI heating before the degradation",
          "t=599: state %s, Heat_1 %.1f %%, Clinician_Mode %d" % (STATE_NAMES[y["Controller_State"]], y["Heat_1"],
                                                                 y["Clinician_Mode"]),
          y["Controller_State"] == CLINICIAN_WARMING and y["Heat_1"] > 0 and y["Clinician_Mode"] == 1)
    y = rows[600]
    r.add("TWIN_DEGRADED.CLINICIAN_FIXED entered (Degraded_Substate = 2, Trigger_Reason = TWIN_DEGRADED)",
          "t = 600 s, substate %d, reason %d" % (y["Degraded_Substate"], y["Trigger_Reason"]),
          y["Controller_State"] == TWIN_DEGRADED and y["Degraded_Substate"] == 2 and y["Trigger_Reason"] == 9)
    H = heats(rows)
    r.add("Heat_i = min(d_fallback_pct = %g %%, p_max_ch_pct_i) on all channels (fixed fallback, not PI)" %
          P["d_fallback_pct"], "Heat_1..4 at t=605: %s" % fl(H[605]),
          np.allclose(H[605], P["d_fallback_pct"]))
    Hd = heats(R["TC16_derate"])
    der = (P["t_mod_trip_degC"] - 40.0) / (P["t_mod_trip_degC"] - P["t_mod_derate_degC"])
    exp3 = min(P["d_fallback_pct"], P["p_max_ch_pct"][2] * der)
    r.add("fallback demand is still module-limited: CH3 module at 40.0 degC derates Heat_3 below d_fallback_pct",
          "Heat_3 = %.3f %% (expected min(%g, %g*%.4f) = %.3f); Heat_1,2,4 = %.1f %%" %
          (Hd[605, 2], P["d_fallback_pct"], P["p_max_ch_pct"][2], der, exp3, Hd[605, 0]),
          abs(Hd[605, 2] - exp3) < 1e-9)
    st = col(rows, "Controller_State")
    tc = first(st == CLINICIAN_WARMING, 601)
    r.add("CLINICIAN_WARMING resumes after VALID for t_recover_s (Trigger_Reason = TWIN_RECOVERED), Clinician_Mode "
          "still 1", "VALID from 800 s; CLINICIAN_WARMING at t = %d s; reason %d; Clinician_Mode %d" %
          (tc, rows[tc]["Trigger_Reason"], rows[tc]["Clinician_Mode"]),
          tc == 800 + P["t_recover_s"] and rows[tc]["Trigger_Reason"] == 10 and rows[tc]["Clinician_Mode"] == 1)
    al = sorted(set(int(rows[t]["Alert"]) for t in range(600, 800)))
    r.add("Alert = TWIN_DEGRADED during the degraded window", "alerts %s" % al, al == [3])
    r.add("no fault, no shutdown", "yes" if no_fault(rows) else "no", no_fault(rows))
    return r


def _transitions(rows):
    out = []
    for t in range(1, len(rows)):
        a, b = rows[t - 1]["Controller_State"], rows[t]["Controller_State"]
        if a != b:
            out.append((t, a, b))
    return out


def tc17(P, R):
    r = Rec("TC17", "No chattering (STANDIN, T_est noise around t_target)")
    for key, lab in (("TC17", "prescribed noise (sd_standin_degC)"),
                     ("TC17_stress", "stress noise (6 x sd_standin_degC = %.2f degC, test-only)" %
                      (6 * P["sd_standin_degC"]))):
        rows = R[key]
        tr = _transitions(rows)
        dwell_tr = [x for x in tr if x[2] in (ACTIVE_WARMING, TARGET_MAINTENANCE, PREDICTIVE_WARMING)]
        viol = 0
        for t, a, b in dwell_tr:
            prev = [x[0] for x in tr if x[0] < t]
            if prev and t - prev[-1] < P["t_dwell_min_s"]:
                viol += 1
        r.add("[%s] no dwell-governed transition occurs before its dwell has elapsed" % lab,
              "%d dwell-governed transitions audited, %d violations" % (len(dwell_tr), viol), viol == 0)
        gaps = np.diff([x[0] for x in tr]) if len(tr) > 1 else np.array([])
        mg = int(gaps.min()) if len(gaps) else None
        r.add("[%s] at most 1 transition per t_dwell_min_s (%d s) window" % (lab, P["t_dwell_min_s"]),
              "%d transitions in %d h; minimum gap = %s s" % (len(tr), round((len(rows) - 1) / 3600), mg),
              mg is None or mg > P["t_dwell_min_s"])
        gl = R["_%s_glitch" % key]
        r.add("[%s] 3 s T_est glitches (<< dwell) never change the state" % lab,
              "%d/%d glitch windows without a transition" % (gl[0], gl[1]), gl[0] == gl[1])
        viol2 = caps_violations(P, rows)
        r.add("[%s] no shutdown / channel fault / cap violation" % lab, "none" if not viol2 else viol2[0],
              (not viol2) and no_fault(rows))
        s = ", ".join("%ds:%s->%s" % (t, SHORT[a], SHORT[b]) for t, a, b in tr[:12]) + (" ..." if len(tr) > 12 else "")
        r.add("[%s] transitions seen" % lab, s, None)
    return r


def tc18(P, R):
    r = Rec("TC18", "Assumed-gain sensitivity (TC04 at 0.5x, 1x, 2x k_heat_degC_per_h)")
    allok = True
    for k in ("0.5", "1.0", "2.0"):
        rows = R["TC18_" + k]
        T, st, tt = closed_loop_metrics(P, rows)
        kk = float(k)
        lab = "k_heat x%s" % k
        r.add("%s (%.2f degC/h): time-to-target (T_plant)" % (lab, P["k_heat_degC_per_h"] * kk) if True else "",
              "%.2f h" % (tt / 3600), None)
        r.add("%s: overshoot (max T_plant - t_target)" % lab, "%.3f degC" % (T.max() - P["t_target_degC"]), None)
        tm = first(st == TARGET_MAINTENANCE)
        viol = caps_violations(P, rows)
        mx = max(max(rw[f"Module_Temp_{i}_{x}"] for i in range(1, 5) for x in "AB") for rw in rows)
        allok = allok and not viol and no_fault(rows)
        r.add("%s: ACTIVE->MAINT entry / safety outcome" % lab,
              "MAINT at %.2f h; safety violations: %s; max module sensor %.2f degC" %
              (tm / 3600, "none" if not viol else len(viol), mx), None)
    r.add("no safety violation in any of the three runs (sensitivity study - not a performance pass)",
          "none" if allok else "see rows", allok)
    return r


def tc19(P, R):
    r = Rec("TC19", "Development-case open-loop replay (twin_DEV_<pseudo>.csv)")
    r.add("twin_DEV_<pseudo>.csv supplied by Sai",
          "BLOCKED: no valid development-case twin output exists (Sai's real-data fit failed). Needed from Sai: "
          "integration/twin_outputs/twin_DEV_<pseudo>.csv with the interface-spec twin columns (T_twin_s/t_s, T_obs, "
          "T_est, T_est_sd, T_pred_20/30/60, P_below_hypo_20/30/60, Twin_Valid). Integration path is prepared in "
          "neram_ctrl/tc19.py and NOT executed. No data fabricated; final holdout not used.", "BLOCKED")
    return r


def tc20(P, R):
    r = Rec("TC20", "Twin in the loop (summit)")
    r.add("summit-stage task, excluded from the 20 Oct code deadline", "not implemented by design", "EXCLUDED")
    return r


ALL = [tc01, tc02, tc03, tc04, tc05, tc06, tc07, tc08, tc09, tc10, tc11, tc12, tc13, tc14, tc15, tc16, tc17, tc18,
       tc19, tc20]


def glitch_tally(rows):
    """(windows without a transition, windows) for the TC17 glitch windows."""
    tr = [x[0] for x in _transitions(rows)]
    ok = sum(1 for w in GLITCH_STARTS if not any(w <= t < w + GLITCH_LEN_S + 1 for t in tr))
    return ok, len(GLITCH_STARTS)


def run_all(P, scen=None):
    """Run every scenario once; returns (R, result_rows)."""
    S = scenarios(P)
    R = {k: (scen or {}).get(k) or fn() for k, fn in S.items()}
    R["_TC06_below"] = [bool(r["below_hypo"]) for r in R["TC06"]]
    R["_TC07_reset"] = [t in (1050, 1250) for t in range(len(R["TC07"]))]
    R["_TC17_glitch"] = glitch_tally(R["TC17"])
    R["_TC17_stress_glitch"] = glitch_tally(R["TC17_stress"])
    out = []
    for fn in ALL:
        out.extend(fn(P, R).rows)
    return R, out
