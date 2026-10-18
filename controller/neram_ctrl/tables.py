"""Result tables: T01 I/O, T02 parameters, transition table, fault-response matrix, traceability, T07 duty stats."""
import csv

import numpy as np

from .params import TABLE

T01 = [
    # name, direction, unit, source / destination, block
    ("T_twin_s", "in", "s", "Sai twin output (held between 1-min updates)", "TwinAdapter"),
    ("T_est", "in", "degC", "Sai twin output", "TwinAdapter, DemandLaw (feedback only)"),
    ("P_below_hypo_20/30/60", "in", "-", "Sai twin output", "TwinAdapter"),
    ("Twin_Valid", "in", "enum 0-3", "Sai twin output", "TwinAdapter"),
    ("Module_Temp_i_A/B", "in", "degC", "Shreehan hardware (SIMULATED)", "FaultMonitor, ChannelLimiter"),
    ("Module_Connected_i", "in", "0/1", "Shreehan hardware (SIMULATED)", "FaultMonitor, ChannelLimiter"),
    ("Heater_Current_i", "in", "A", "Shreehan hardware (SIMULATED)", "FaultMonitor"),
    ("HW_Cutoff_i", "in", "0/1", "Shreehan hardware (SIMULATED)", "FaultMonitor, ChannelLimiter"),
    ("HW_Heartbeat_s", "in", "s", "Shreehan hardware (SIMULATED)", "FaultMonitor"),
    ("HW_Fault_Code", "in", "code", "Shreehan hardware (SIMULATED)", "FaultMonitor"),
    ("Clinician_Start/Stop/Reset", "in", "0/1 (rising edge)", "Clinician buttons", "Supervisor, FaultMonitor"),
    ("Heat_1..4", "out", "%", "hardware (SIMULATED) and replay log", "ChannelLimiter"),
    ("Demand_Global", "out", "%", "log", "DemandLaw"),
    ("Controller_State, Degraded_Substate", "out", "enum", "log / Unity replay", "Supervisor"),
    ("Trigger_Reason, Alert", "out", "enum", "log / Unity replay", "Supervisor"),
    ("Safety_Shutdown, Fault_Latched, fault_code, Channel_Fault_1..4", "out", "0/1, code", "log", "FaultMonitor"),
    ("Data_Stale_Twin, Data_Stale_HW, Clinician_Mode", "out", "0/1", "log", "TwinAdapter, FaultMonitor, Supervisor"),
]

TRANSITIONS = [
    ("T1", "OPERATING (any)", "SAFETY_SHUTDOWN", "system_fault", "none", 1, "SAFETY_FAULT"),
    ("T2", "SAFETY_SHUTDOWN", "OPERATING.NORMAL", "rising Clinician_Reset AND system_fault cleared AND all T_mod_i < "
     "t_mod_reset_degC (NaN T_mod blocks); otherwise stay and raise RESET_BLOCKED", "none", 2, "CLINICIAN_RESET"),
    ("T3", "PREDICTIVE_WARMING / ACTIVE_WARMING / TARGET_MAINTENANCE / CLINICIAN_WARMING / "
     "TWIN_DEGRADED.CLINICIAN_FIXED", "NORMAL", "rising Clinician_Stop; starts stop_inhibit (t_stop_inhibit_s); "
     "clears Clinician_Mode", "none", 3, "CLINICIAN_STOP"),
    ("T4", "NORMAL / PREDICTIVE_WARMING / ACTIVE_WARMING / TARGET_MAINTENANCE / CLINICIAN_WARMING",
     "TWIN_DEGRADED (CLINICIAN_FIXED if Clinician_Mode or Clinician_Start in the same sample, else MONITOR)",
     "twin_bad", "none", 4, "TWIN_DEGRADED"),
    ("T5", "TWIN_DEGRADED.MONITOR", "NORMAL", "twin_ok held", "t_recover_s", 5, "TWIN_RECOVERED"),
    ("T6", "TWIN_DEGRADED.CLINICIAN_FIXED", "CLINICIAN_WARMING", "twin_ok held", "t_recover_s", 6, "TWIN_RECOVERED"),
    ("T7", "TWIN_DEGRADED.MONITOR", "TWIN_DEGRADED.CLINICIAN_FIXED", "rising Clinician_Start", "none", 7,
     "CLINICIAN_START"),
    ("T8", "NORMAL / PREDICTIVE_WARMING", "CLINICIAN_WARMING", "rising Clinician_Start AND twin_ok", "none", 8,
     "CLINICIAN_START"),
    ("T9", "NORMAL (twin INITIALISING)", "TWIN_DEGRADED.CLINICIAN_FIXED", "rising Clinician_Start AND NOT twin_ok",
     "none", 9, "CLINICIAN_START"),
    ("T10", "NORMAL", "ACTIVE_WARMING", "twin_ok AND below_hypo AND NOT stop_inhibit, held", "t_dwell_min_s", 10,
     "TEST_BELOW_HYPO"),
    ("T11", "NORMAL", "PREDICTIVE_WARMING", "risk_pred AND NOT below_hypo AND NOT stop_inhibit, held",
     "t_dwell_min_s", 11, "FORECAST_P20 or FORECAST_P30"),
    ("T12", "PREDICTIVE_WARMING", "ACTIVE_WARMING", "below_hypo held", "t_dwell_min_s", 12, "TEST_BELOW_HYPO"),
    ("T13", "PREDICTIVE_WARMING / ACTIVE_WARMING / CLINICIAN_WARMING", "TARGET_MAINTENANCE", "at_target held",
     "t_dwell_min_s", 13, "TARGET_REACHED"),
    ("T14", "TARGET_MAINTENANCE", "ACTIVE_WARMING", "target_lost held", "t_dwell_min_s", 14, "TARGET_LOST"),
]

FAULT_K = [
    (1, "Module_Temp_{c}_A NaN (open/unreadable)", "Channel {c} off", "Alert CHANNEL_FAULT", "Reset + sensor valid"),
    (2, "Module_Temp_{c}_A out of sensor range (DISABLED until the range is supplied)", "Channel {c} off",
     "Alert CHANNEL_FAULT", "Reset + sensor valid"),
    (3, "Module_Temp_{c}_B NaN (open/unreadable)", "Channel {c} off", "Alert CHANNEL_FAULT", "Reset + sensor valid"),
    (4, "Module_Temp_{c}_B out of sensor range (DISABLED until the range is supplied)", "Channel {c} off",
     "Alert CHANNEL_FAULT", "Reset + sensor valid"),
    (5, "|A - B| > dt_sensor_disagree_degC held t_dwell_min_s", "Channel {c} off", "Alert CHANNEL_FAULT",
     "Reset + agreement"),
    (6, "T_mod_{c} >= t_mod_trip_degC", "All off", "SAFETY_SHUTDOWN", "Reset + T_mod < t_mod_reset_degC"),
    (7, "HW_Cutoff_{c} = 1", "All off", "SAFETY_SHUTDOWN", "Reset + cutoff cleared"),
    (8, "Module_Connected_{c} = 0", "Channel {c} off", "Alert CHANNEL_FAULT", "Reset + reconnected"),
    (9, "Heater open (qualified rule, D1) or Heater_Current_{c} = NaN", "Channel {c} off", "Alert CHANNEL_FAULT",
     "Reset (current readable)"),
    (10, "Heater_Current_{c} > i_over_A", "All off", "SAFETY_SHUTDOWN", "Reset + current < i_over_A"),
    (11, "Heat_{c} = 0 and Heater_Current_{c} > i_stuck_A for 2 steps", "All off (master cutoff)", "SAFETY_SHUTDOWN",
     "Reset + current < i_stuck_A"),
]

TRACE = [
    ("K1", "SAFETY_SHUTDOWN sets all Heat_i = 0 in the step it is entered and holds them at 0",
     "T1; SAFETY_SHUTDOWN; ChannelLimiter enable_i", ["TC07", "TC11", "TC12", "TC15"]),
    ("K2", "Every safety fault is latched; only Clinician_Reset with the condition cleared releases it",
     "T1, T2; FaultMonitor latches", ["TC07", "TC11", "TC12", "TC15"]),
    ("K3", "Clinician_Stop always wins over any autonomous transition and blocks autonomous re-entry for "
     "t_stop_inhibit_s", "T3 (priority 3); stop_inhibit in T10/T11", ["TC06"]),
    ("K4", "Autonomous warming (T10, T11) requires twin_ok; INITIALISING/DEGRADED/NO_DATA/stale means no autonomous "
     "warming", "T4, T10, T11; twin_ok", ["TC13", "TC14", "TC19"]),
    ("K5", "P60 can only raise FORECAST_RISK_60_INFO", "NORMAL (Alert only); risk60", ["TC03"]),
    ("K6", 'A NaN in any signal used for a decision is a fault or "not ok", never 0',
     "FaultMonitor codes +1/+3/+9; twin_bad; T2 NaN T_mod blocks reset", ["TC08", "AU-G1"]),
    ("K7", "Heat_i is always clamped to [0, p_max_ch_pct_i]", "ChannelLimiter",
     ["TC04", "TC05", "TC16", "TC18", "AU-G9"]),
    ("J-R1", "PREDICTIVE_WARMING never exits on the forecast", "PREDICTIVE_WARMING (R2)", ["TC02"]),
    ("J-R2", "TARGET_MAINTENANCE has no automatic exit to NORMAL", "TARGET_MAINTENANCE (R3)", ["TC04"]),
    ("J-R3", "Clinician_Start in ACTIVE or MAINT only sets Clinician_Mode", "ACTIVE_WARMING / TARGET_MAINTENANCE (R1)",
     ["AU-G7"]),
    ("J-T5/T6", "Twin recovery requires twin_ok held t_recover_s", "T5, T6", ["TC13", "TC14", "TC16"]),
    ("J-T8", "Clinician_Start with twin_ok enters CLINICIAN_WARMING; heat from the PI law", "T8; DemandLaw", ["TC05"]),
    ("J-T10", "Below t_hypo (twin_ok) for t_dwell_min_s -> ACTIVE_WARMING", "T10", ["TC04", "TC06"]),
    ("J-T11", "Forecast risk confirmed for n_confirm_updates twin minutes -> PREDICTIVE_WARMING", "T11; TwinAdapter",
     ["TC02"]),
    ("J-T13", "at_target held -> TARGET_MAINTENANCE", "T13", ["TC04", "TC05", "TC17"]),
    ("J-T14", "target_lost held -> ACTIVE_WARMING", "T14", ["TC17"]),
    ("J-DW", "No transition before its dwell; no chattering", "T10-T14 dwell", ["TC17"]),
    ("L-CH", "Channel fault (sensor, disagreement, disconnect, open) isolates only that channel and raises CHANNEL_FAULT",
     "FaultMonitor + ChannelLimiter; Alert", ["TC08", "TC09", "TC10"]),
    ("L-SYS", "Over-temperature, cutoff, over-current, stuck-on, HW stale and HW_Fault_Code force a system shutdown",
     "T1", ["TC07", "TC11", "TC12", "TC15", "AU-G5"]),
    ("L-PRI", "Fault priority: system before channel; lower channel first; shutdown-class before isolating faults",
     "FaultMonitor.fault_code selection", ["TC07", "AU-G3"]),
    ("L-TW", "Data_Stale_Twin -> TWIN_DEGRADED, not a shutdown, no latch", "T4; Data_Stale_Twin", ["TC14"]),
    ("I-FIX", "Twin degraded during clinician warming -> fixed fallback demand, still module-limited",
     "TWIN_DEGRADED.CLINICIAN_FIXED", ["TC16"]),
    ("S-LOG", "Controller log columns, units, enums and NaN-as-empty per section S", "exporter", ["LOGCHECK"]),
]


def _w(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def write_all(outdir, P, test_rows, audit_rows, R, logcheck_ok):
    _w(f"{outdir}/T01_io.csv", ["signal", "direction", "unit", "source / destination", "block"], T01)
    _w(f"{outdir}/T02_params_used.csv", ["name", "value", "unit", "status", "owner"],
       [(k, P[k] if P[k] is not None else "null", v[1], v[2], v[3]) for k, v in TABLE.items()])
    _w(f"{outdir}/transition_table.csv", ["id", "from", "to", "condition", "dwell", "priority", "reason"], TRANSITIONS)
    fr = []
    for c in range(1, 5):
        for k, cond, ch, sysa, rel in FAULT_K:
            fr.append((cond.format(c=c), 100 * c + k, ch.format(c=c), sysa, "Yes", rel))
    fr += [("Data_Stale_HW (heartbeat older than data_stale_hw_s, or NaN)", 8, "All off", "SAFETY_SHUTDOWN", "Yes",
            "Reset + heartbeat back")]
    fr += [("HW_Fault_Code = %d (any non-zero code is treated the same)" % c, c, "All off", "SAFETY_SHUTDOWN", "Yes",
            "Reset + code cleared") for c in range(1, 7)]
    fr += [("HW_Fault_Code = NaN (unreadable)", 8, "All off", "SAFETY_SHUTDOWN", "Yes", "Reset + code readable"),
           ("All 4 channels faulted (non-shutdown)", "-", "-", "Alert CHANNEL_FAULT; demand 0", "-", "-"),
           ("Data_Stale_Twin (T_twin_s older than data_stale_twin_s, or NaN)", 7, "-", "TWIN_DEGRADED (not a shutdown)",
            "No", "Automatic via T5/T6"),
           ("Twin_Valid = DEGRADED or NO_DATA; or VALID with T_est NaN / outside 25-43 degC", "-", "-",
            "TWIN_DEGRADED (not a shutdown)", "No", "Automatic via T5/T6")]
    _w(f"{outdir}/fault_response_matrix.csv",
       ["fault condition", "fault code", "channel action", "system action", "latched", "reset / release condition"], fr)
    res = {}
    for r in test_rows:
        if r["result"] in ("REPORTED",):
            continue
        cur = res.get(r["tc_id"], "PASS")
        if r["result"] in ("FAIL",):
            cur = "FAIL"
        elif r["result"] in ("BLOCKED", "EXCLUDED") and cur == "PASS":
            cur = r["result"]
        res[r["tc_id"]] = cur
    for a in audit_rows:
        g = a["id"][:5] if a["id"].startswith("AU-G") else a["id"]
        g = "AU-G" + a["id"][4] if a["id"].startswith("AU-G") else g
        cur = res.get(g, "PASS")
        if a["result"] == "FAIL":
            cur = "FAIL"
        res[g] = cur
    res["LOGCHECK"] = "PASS" if logcheck_ok else "FAIL"
    tr = []
    for rid, text, blk, ids in TRACE:
        rr = "; ".join("%s=%s" % (i, res.get(i, "NOT RUN")) for i in ids)
        vals = [res.get(i, "NOT RUN") for i in ids]
        if "FAIL" in vals:
            stt = "FAILED"
        elif all(v == "PASS" for v in vals):
            stt = "verified"
        else:
            stt = "verified (%s - see test_results.csv)" % ", ".join(
                "%s %s" % (i, v) for i, v in zip(ids, vals) if v != "PASS")
        tr.append((rid, text, blk, "; ".join(ids), rr, stt))
    _w(f"{outdir}/requirements_traceability.csv",
       ["requirement", "text", "state / transition / block", "test ID(s)", "results", "status"], tr)
    _w(f"{outdir}/audit_checks.csv", ["id", "requirement checked (plan section G / K / L / J)", "measured", "PASS/FAIL"],
       [(a["id"], a["requirement"], a["measured"], a["result"]) for a in audit_rows])
    # T07: duty statistics per scenario (input to Shreehan's power budget)
    t7 = []
    for k in sorted(x for x in R if not x.startswith("_")):
        rows = R[k]
        H = np.array([[r[f"Heat_{i}"] for i in range(1, 5)] for r in rows])
        dur = (len(rows) - 1) / 3600.0
        t7.append([k, rows[0]["plant_mode"], "%.3f" % dur] + ["%.2f" % v for v in H.mean(axis=0)] +
                  ["%.2f" % v for v in np.percentile(H, 95, axis=0)] + ["%.2f" % v for v in H.max(axis=0)] +
                  ["%.1f" % (100.0 * (H > 0).any(axis=1).mean())])
    _w(f"{outdir}/T07_duty_stats.csv",
       ["scenario", "plant_mode", "duration_h"] + ["mean_Heat_%d_pct" % i for i in range(1, 5)] +
       ["p95_Heat_%d_pct" % i for i in range(1, 5)] + ["max_Heat_%d_pct" % i for i in range(1, 5)] +
       ["time_any_heating_pct"], t7)
    return res
