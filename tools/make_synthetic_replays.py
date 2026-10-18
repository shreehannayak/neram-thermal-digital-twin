#!/usr/bin/env python3
"""Deterministic SYNTHETIC placeholder replays for developing the NERAM Unity layer.

WHAT THIS IS
  Development scaffolding. It produces twin-format and controller-log-format CSVs from a simple synthetic
  world, then builds replays with integration/build_replay.py (the same builder the real pipeline uses).

WHAT THIS IS NOT
  - Not the NERAM twin: twin fields come from a simple stand-in (exponential filter + fixed rules),
    tagged src.twin = SIMULATED.
  - Not Suchitha's controller: controller fields come from a simplified scripted stand-in that follows the
    plan's state list so the UI can be exercised. It is not the Simulink/Stateflow model.
  - Not physiology: the baseline trajectory, the assumed warming response and the module temperatures use
    illustrative values chosen only so that every display path is exercised. Every such value is listed
    in each replay header (params_used) with status and the note "SYNTHETIC DEMO".
  - No safety threshold is encoded: over-temperature and cutoff faults are injected at scripted TIMES.
  Every replay is marked placeholder = true and cohort = SYNTHETIC. No VitalDB data is used.

Usage
    python tools/make_synthetic_replays.py            # writes integration/synthetic/* and integration/replays/SYN_*.jsonl.gz
    python tools/make_synthetic_replays.py --check    # regenerate in a temp dir and compare bytes (determinism test)
"""
import argparse
import csv
import filecmp
import json
import math
import random
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "integration"))
import build_replay  # noqa: E402
import validate_replay  # noqa: E402

GENERATOR = "tools/make_synthetic_replays.py v1.0 (synthetic placeholder; stand-in twin + scripted stand-in controller)"
CREATED_UTC = "2026-10-08T00:00:00Z"  # fixed so that output bytes are reproducible
Z80 = 1.2815515655446004
Z95 = 1.959963984540054

ENUMS = validate_replay.load_enums(ROOT / "config" / "enums.json")
CS = ENUMS["ControllerState"]
TV = ENUMS["TwinValid"]
TR = ENUMS["TriggerReason"]
AL = ENUMS["AlertCode"]
SUB = ENUMS["DegradedSubstate"]

# --- SYNTHETIC DEMO values (all listed in params_used with their status; none is a clinical or hardware value) ---
SYN = {
    "t_hypo_degC": 36.0,          # config placeholder (plan: 36.0 core-temperature convention, applicability TBD)
    "t_target_degC": 36.5,        # SYNTHETIC DEMO placeholder only
    "p_trigger": 0.5, "p_release": 0.4, "n_confirm_updates": 2,
    "t_dwell_min_s": 60, "t_recover_s": 120, "t_stop_inhibit_s": 600, "band_target_degC": 0.2,
    "d_pred_max_pct": 40, "d_active_max_pct": 70, "d_maint_max_pct": 30, "d_fallback_pct": 25,
    "kp_pct_per_degC": 60.0, "ki_pct_per_degC_s": 0.02,
    "k_heat_degC_per_h": 2.0, "tau_heat_min": 10.0, "w_ch": [0.25, 0.25, 0.25, 0.25],
    "r_obs_sd_degC": 0.03,
    "sd_degrade_degC": 0.25,
    "t_skin_base_degC": 33.0, "k_mod_degC": 6.0, "tau_mod_s": 120.0, "sd_mod_sensor_degC": 0.03,
    "i_on_A": 1.0,
    "data_stale_hw_s": 3,
}

PARAMS_USED = {
    "t_hypo_degC": {"value": None, "placeholder": SYN["t_hypo_degC"], "unit": "degC", "status": "TBD", "owner": "Sai",
                    "source": "config/params.json placeholder: 36.0 is the core-temperature convention; applicability to this signal unresolved"},
    "t_target_degC": {"value": None, "placeholder": SYN["t_target_degC"], "unit": "degC", "status": "TBD", "owner": "Sai",
                      "source": "SYNTHETIC DEMO placeholder chosen for display only; not a clinical target"},
    "p_trigger": {"value": None, "placeholder": SYN["p_trigger"], "unit": "1", "status": "PROVISIONAL", "owner": "Sai",
                  "source": "SYNTHETIC DEMO placeholder for the scripted stand-in controller"},
    "p_release": {"value": None, "placeholder": SYN["p_release"], "unit": "1", "status": "PROVISIONAL", "owner": "Sai",
                  "source": "SYNTHETIC DEMO placeholder for the scripted stand-in controller"},
    "t_dwell_min_s": {"value": None, "placeholder": SYN["t_dwell_min_s"], "unit": "s", "status": "PROVISIONAL", "owner": "Suchitha",
                      "source": "SYNTHETIC DEMO placeholder for the scripted stand-in controller"},
    "t_stop_inhibit_s": {"value": None, "placeholder": SYN["t_stop_inhibit_s"], "unit": "s", "status": "PROVISIONAL", "owner": "Suchitha",
                         "source": "SYNTHETIC DEMO placeholder for the scripted stand-in controller"},
    "k_heat_degC_per_h": {"value": None, "placeholder": SYN["k_heat_degC_per_h"], "unit": "degC/h at 100% on all channels", "status": "ASSUMED", "owner": "Sai",
                          "source": "SYNTHETIC DEMO illustrative value; not estimated; no warming data exist"},
    "tau_heat_min": {"value": None, "placeholder": SYN["tau_heat_min"], "unit": "min", "status": "ASSUMED", "owner": "Sai",
                     "source": "SYNTHETIC DEMO illustrative value"},
    "w_ch": {"value": None, "placeholder": SYN["w_ch"], "unit": "1", "status": "ASSUMED", "owner": "Sai",
             "source": "ASSUMED equal channel weights (plan section 4E default)"},
    "k_mod_degC": {"value": None, "placeholder": SYN["k_mod_degC"], "unit": "degC", "status": "ASSUMED", "owner": "Suchitha",
                   "source": "SYNTHETIC DEMO module stand-in; not a heater or skin value"},
    "i_on_A": {"value": None, "placeholder": SYN["i_on_A"], "unit": "A", "status": "TBD", "owner": "Shreehan",
               "source": "SYNTHETIC DEMO normalised current (1.0 = nominal); not an electrical rating"},
}

COMMON_LIMITATIONS = [
    "SYNTHETIC placeholder: no patient data; every value comes from tools/make_synthetic_replays.py.",
    "Twin fields come from a stand-in filter, not the NERAM robust state-space twin.",
    "Controller fields come from a simplified scripted stand-in, not the Simulink/Stateflow controller.",
    "Hardware signals and module temperatures come from a test stand-in; no hardware exists.",
    "Thresholds shown are placeholders (status TBD); no clinical or safety limit is implied.",
]


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class Scenario:
    def __init__(self, sid, title, purpose, minutes, plant_mode, seed, u0, alpha, gamma_per_min, beta_per_h, rw_sd,
                 presses=(), faults=(), gaps=(), outliers=(), level_shifts=(), data_source=None, loop_description=None,
                 extra_limitations=(), press_fields=False):
        self.sid, self.title, self.purpose = sid, title, purpose
        self.minutes, self.plant_mode, self.seed = minutes, plant_mode, seed
        self.u0, self.alpha, self.gamma, self.beta, self.rw_sd = u0, alpha, gamma_per_min, beta_per_h, rw_sd
        self.presses = {t: k for t, k in presses}
        self.faults = list(faults)
        self.gap_minutes = set()
        for a, b in gaps:
            self.gap_minutes.update(range(a, b + 1))
        self.outliers = dict(outliers)
        self.level_shifts = dict(level_shifts)
        self.data_source = data_source or "Synthetic trajectory generated by tools/make_synthetic_replays.py (SIMULATED)"
        self.loop_description = loop_description
        self.extra_limitations = list(extra_limitations)
        self.press_fields = press_fields

    def drift(self, tau_min):
        """Deterministic no-intervention trajectory shape (used for the stand-in no-intervention forecast)."""
        return self.alpha * (math.exp(-self.gamma * tau_min) - 1.0) + self.beta * tau_min / 60.0


class Fault:
    def __init__(self, kind, ch, t_on, t_clear=None):
        self.kind, self.ch, self.t_on, self.t_clear = kind, ch, t_on, t_clear

    def active(self, t):
        return t >= self.t_on and (self.t_clear is None or t < self.t_clear)


SHUTDOWN_KINDS = {"overtemp_sw": 6, "hw_cutoff": 7, "stuck_on": 11}
ISOLATE_KINDS = {"sensorB_open": 3, "disagree": 5, "disconnect": 8}


def simulate(sc):
    rng = random.Random(sc.seed)
    n_min = sc.minutes
    n_s = n_min * 60
    # passive baseline per minute (random walk + level shifts), linearly interpolated per second
    rw = [0.0]
    for m in range(1, n_min + 2):
        rw.append(rw[-1] + rng.gauss(0.0, sc.rw_sd))
    shift = [0.0] * (n_min + 2)
    acc = 0.0
    for m in range(n_min + 2):
        acc += sc.level_shifts.get(m, 0.0)
        shift[m] = acc

    def t_pass(t_s):
        tau = t_s / 60.0
        m = int(tau)
        frac = tau - m
        rwi = rw[m] + (rw[m + 1] - rw[m]) * frac
        return sc.u0 + sc.drift(tau) + rwi + shift[m]

    obs_noise = [rng.gauss(0.0, SYN["r_obs_sd_degC"]) for _ in range(n_min + 1)]
    sens_noise = [[(rng.gauss(0, SYN["sd_mod_sensor_degC"]), rng.gauss(0, SYN["sd_mod_sensor_degC"])) for _ in range(4)] for _ in range(n_s)]

    twin_rows, ctrl_rows = [], []
    # twin stand-in state
    est = None
    sd = 0.12
    pending = 0
    obs_hist = []
    tw = None
    # controller stand-in state
    state, sub, reason, alert = CS["NORMAL"], SUB["NONE"], TR["NONE"], AL["NONE"]
    clin_mode = False
    stop_time = -1e9
    held = {}
    integ = 0.0
    risk_count = 0
    risk_pred = False
    ch_fault = [0, 0, 0, 0]
    sys_code = 0
    reset_blocked_until = -1
    stop_ack_until = -1
    shutdown_cause = None
    # plant / module state
    h = 0.0
    dT = 0.0
    tmod = [SYN["t_skin_base_degC"]] * 4
    extra = [0.0] * 4
    prev_heat = [0.0] * 4
    stale_since = None

    def hold(name, cond, t, dwell):
        if not cond:
            held.pop(name, None)
            return False
        held.setdefault(name, t)
        return t - held[name] >= dwell

    warming = {CS["PREDICTIVE_WARMING"], CS["ACTIVE_WARMING"], CS["TARGET_MAINTENANCE"], CS["CLINICIAN_WARMING"]}

    for t in range(n_s):
        m = t // 60
        tau = t / 60.0
        # ---------------- twin stand-in: update once per minute ----------------
        if t % 60 == 0:
            true_now = t_pass(t) + (dT if sc.plant_mode == "STANDIN" else 0.0)
            missing = m in sc.gap_minutes
            obs = None if missing else true_now + obs_noise[m] + sc.outliers.get(m, 0.0)
            p_out, p_lvl = 0.02, 0.01
            if est is None:
                if obs is not None:
                    est, sd = obs, 0.12
            elif obs is None:
                sd = min(0.6, sd + 0.02)
                pending = 0
            else:
                resid = obs - est
                if abs(resid) > 0.4:
                    pending += 1
                    if pending == 1:
                        p_out, p_lvl = 0.88, 0.10
                    else:
                        p_out, p_lvl = 0.06, 0.91
                        est, sd = obs, 0.15
                else:
                    if pending == 1:
                        p_out, p_lvl = 0.10, 0.05
                    pending = 0
                    est = est + 0.35 * resid
                    sd = max(0.05, sd * 0.85)
            obs_hist.append(obs is not None)
            recent = obs_hist[-15:]
            if est is None:
                tv = TV["NO_DATA"]
            elif m < 20:
                tv = TV["INITIALISING"]
            elif sum(recent) >= 10 and sd < SYN["sd_degrade_degC"]:
                tv = TV["VALID"]
            else:
                tv = TV["DEGRADED"]
            tw = {"T_twin_s": t, "T_obs": obs, "obs_missing": 1 if obs is None else 0,
                  "T_est": est, "T_est_sd": None if est is None else sd, "Twin_Valid": tv,
                  "P_level_shift": None if est is None else p_lvl, "P_outlier": None if est is None else p_out}
            for hz in (20, 30, 60):
                if tv == TV["VALID"]:
                    mean = est + sc.drift(tau + hz) - sc.drift(tau)
                    s_h = math.sqrt(sd * sd + 0.0004 * hz)
                    tw.update({f"T_pred_{hz}": mean, f"L80_{hz}": mean - Z80 * s_h, f"U80_{hz}": mean + Z80 * s_h,
                               f"L95_{hz}": mean - Z95 * s_h, f"U95_{hz}": mean + Z95 * s_h,
                               f"P_below_hypo_{hz}": phi((SYN["t_hypo_degC"] - mean) / s_h)})
                else:
                    tw.update({f"{p}_{hz}": None for p in ("T_pred", "L80", "U80", "L95", "U95", "P_below_hypo")})
            twin_rows.append(tw)
            # risk confirmation counts twin updates (minutes)
            if tv == TV["VALID"]:
                p20, p30 = tw["P_below_hypo_20"], tw["P_below_hypo_30"]
                if p20 >= SYN["p_trigger"] or p30 >= SYN["p_trigger"]:
                    risk_count += 1
                elif p20 < SYN["p_release"] and p30 < SYN["p_release"]:
                    risk_count = 0
                risk_pred = risk_count >= SYN["n_confirm_updates"] or (risk_pred and not (p20 < SYN["p_release"] and p30 < SYN["p_release"]))
            else:
                risk_count, risk_pred = 0, False

        tv = tw["Twin_Valid"]
        twin_ok = tv == TV["VALID"]
        twin_bad = tv in (TV["DEGRADED"], TV["NO_DATA"])
        est_now = tw["T_est"]
        below = est_now is not None and est_now < SYN["t_hypo_degC"]
        at_target = est_now is not None and est_now >= SYN["t_target_degC"]
        lost = est_now is not None and est_now < SYN["t_target_degC"] - SYN["band_target_degC"]
        risk60 = twin_ok and tw["P_below_hypo_60"] is not None and tw["P_below_hypo_60"] >= SYN["p_trigger"]
        inhibit = t - stop_time < SYN["t_stop_inhibit_s"]

        # ---------------- scripted faults ----------------
        connected = [True] * 4
        sensor_open_b = [False] * 4
        offset_a = [0.0] * 4
        cutoff = [False] * 4
        stuck = [False] * 4
        hw_stale = False
        new_shutdown = None
        for f in sc.faults:
            i = f.ch - 1 if f.ch else None
            if f.kind == "hotspot" and t >= f.t_on:
                # simulated hot-spot: rises while the injection window is active, then decays
                extra[i] = min(12.0, extra[i] + 0.012) if f.active(t) else extra[i] * 0.995
            if not f.active(t):
                continue
            if f.kind == "disconnect":
                connected[i] = False
            if f.kind == "sensorB_open":
                sensor_open_b[i] = True
            if f.kind == "disagree":
                offset_a[i] = 0.9
            if f.kind == "hw_cutoff":
                cutoff[i] = True
            if f.kind == "stuck_on":
                stuck[i] = True
            if f.kind == "hw_stale":
                hw_stale = True
            if f.kind in ISOLATE_KINDS and ch_fault[i] == 0:
                ch_fault[i] = 100 * f.ch + ISOLATE_KINDS[f.kind]
            if f.kind in SHUTDOWN_KINDS and t == f.t_on + (2 if f.kind == "stuck_on" else 0):
                new_shutdown = (100 * f.ch + SHUTDOWN_KINDS[f.kind], f)
        if hw_stale:
            stale_since = stale_since if stale_since is not None else t
            if t - stale_since == SYN["data_stale_hw_s"]:
                new_shutdown = (8, None)
        else:
            stale_since = None
        data_stale_hw = hw_stale and t - stale_since >= SYN["data_stale_hw_s"]

        press = sc.presses.get(t)
        prev_state = state
        # ---------------- scripted stand-in supervisor (priority order of plan section 1J) ----------------
        if new_shutdown and state != CS["SAFETY_SHUTDOWN"]:
            sys_code = new_shutdown[0]
            shutdown_cause = new_shutdown[1]
            if sys_code >= 100:
                ch_fault[sys_code // 100 - 1] = sys_code
            state, sub, reason = CS["SAFETY_SHUTDOWN"], SUB["NONE"], TR["SAFETY_FAULT"]
            clin_mode = False
        elif state == CS["SAFETY_SHUTDOWN"]:
            if press == "reset":
                cleared = (shutdown_cause is None and not hw_stale) or (shutdown_cause is not None and
                                                                        shutdown_cause.t_clear is not None and t >= shutdown_cause.t_clear)
                if cleared:
                    state, reason = CS["NORMAL"], TR["CLINICIAN_RESET"]
                    sys_code = 0
                    for i in range(4):
                        still = any(f.ch == i + 1 and f.active(t) and (f.kind in ISOLATE_KINDS or f.kind in SHUTDOWN_KINDS) for f in sc.faults)
                        if not still:
                            ch_fault[i] = 0
                else:
                    reset_blocked_until = t + 20
        elif press == "stop" and state in warming | {CS["TWIN_DEGRADED"]} and (state != CS["TWIN_DEGRADED"] or sub == SUB["CLINICIAN_FIXED"]):
            state, sub, reason = CS["NORMAL"], SUB["NONE"], TR["CLINICIAN_STOP"]
            stop_time, stop_ack_until, clin_mode = t, t + 10, False
        elif twin_bad and state in warming | {CS["NORMAL"]}:
            state, reason = CS["TWIN_DEGRADED"], TR["TWIN_DEGRADED"]
            sub = SUB["CLINICIAN_FIXED"] if clin_mode else SUB["MONITOR"]
        elif state == CS["TWIN_DEGRADED"] and hold("recover", twin_ok, t, SYN["t_recover_s"]):
            state, reason = (CS["CLINICIAN_WARMING"] if sub == SUB["CLINICIAN_FIXED"] else CS["NORMAL"]), TR["TWIN_RECOVERED"]
            sub = SUB["NONE"]
        elif press == "start" and state == CS["TWIN_DEGRADED"] and sub == SUB["MONITOR"]:
            sub, reason, clin_mode = SUB["CLINICIAN_FIXED"], TR["CLINICIAN_START"], True
        elif press == "start" and state in (CS["NORMAL"], CS["PREDICTIVE_WARMING"]):
            clin_mode = True
            if twin_ok:
                state, reason = CS["CLINICIAN_WARMING"], TR["CLINICIAN_START"]
            else:
                state, sub, reason = CS["TWIN_DEGRADED"], SUB["CLINICIAN_FIXED"], TR["CLINICIAN_START"]
        elif press == "start" and state in (CS["ACTIVE_WARMING"], CS["TARGET_MAINTENANCE"]):
            clin_mode = True
        elif state == CS["NORMAL"] and twin_ok and not inhibit and hold("below", below, t, SYN["t_dwell_min_s"]):
            state, reason = CS["ACTIVE_WARMING"], TR["TEST_BELOW_HYPO"]
        elif state == CS["NORMAL"] and risk_pred and not below and not inhibit:
            p20 = tw["P_below_hypo_20"]
            state, reason = CS["PREDICTIVE_WARMING"], (TR["FORECAST_P20"] if p20 >= SYN["p_trigger"] else TR["FORECAST_P30"])
        elif state == CS["PREDICTIVE_WARMING"] and hold("below_p", below, t, SYN["t_dwell_min_s"]):
            state, reason = CS["ACTIVE_WARMING"], TR["TEST_BELOW_HYPO"]
        elif state in (CS["PREDICTIVE_WARMING"], CS["ACTIVE_WARMING"], CS["CLINICIAN_WARMING"]) and hold("target", at_target, t, SYN["t_dwell_min_s"]):
            state, reason = CS["TARGET_MAINTENANCE"], TR["TARGET_REACHED"]
        elif state == CS["TARGET_MAINTENANCE"] and hold("lost", lost, t, SYN["t_dwell_min_s"]):
            state, reason = CS["ACTIVE_WARMING"], TR["TARGET_LOST"]
        if state != prev_state:
            integ = 0.0
            held.clear()

        # ---------------- demand (scripted PI stand-in; forecast never used for dose) ----------------
        caps = {CS["PREDICTIVE_WARMING"]: SYN["d_pred_max_pct"], CS["ACTIVE_WARMING"]: SYN["d_active_max_pct"],
                CS["CLINICIAN_WARMING"]: SYN["d_active_max_pct"], CS["TARGET_MAINTENANCE"]: SYN["d_maint_max_pct"]}
        if state in caps and est_now is not None:
            cap = caps[state]
            e = SYN["t_target_degC"] - est_now
            integ += e
            u = SYN["kp_pct_per_degC"] * e + SYN["ki_pct_per_degC_s"] * integ
            if u > cap:
                integ -= e
                u = cap
            elif u < 0:
                integ -= e if e < 0 else 0.0
                u = 0.0
            demand = max(0.0, min(cap, u))
        elif state == CS["TWIN_DEGRADED"] and sub == SUB["CLINICIAN_FIXED"]:
            demand = float(SYN["d_fallback_pct"])
        else:
            demand = 0.0
        heat = [0.0] * 4
        for i in range(4):
            if state == CS["SAFETY_SHUTDOWN"] or ch_fault[i] != 0 or not connected[i]:
                heat[i] = 0.0
            else:
                heat[i] = demand

        # ---------------- alerts (highest priority) ----------------
        if state == CS["SAFETY_SHUTDOWN"]:
            alert = AL["RESET_BLOCKED"] if t < reset_blocked_until else AL["SAFETY_SHUTDOWN"]
        elif state == CS["TWIN_DEGRADED"]:
            alert = AL["TWIN_DEGRADED"]
        elif any(ch_fault):
            alert = AL["CHANNEL_FAULT"]
        elif t < stop_ack_until:
            alert = AL["CLINICIAN_STOP_ACK"]
        elif risk_pred:
            alert = AL["FORECAST_RISK_20_30"]
        elif risk60:
            alert = AL["FORECAST_RISK_60_INFO"]
        else:
            alert = AL["NONE"]
        degraded_alert_override = data_stale_hw and state != CS["SAFETY_SHUTDOWN"]
        if degraded_alert_override:
            alert = AL["DATA_STALE"]

        # ---------------- module + plant stand-ins (driven by this second's heat) ----------------
        mod_a, mod_b, cur = [None] * 4, [None] * 4, [None] * 4
        for i in range(4):
            target_t = SYN["t_skin_base_degC"] + SYN["k_mod_degC"] * heat[i] / 100.0 + extra[i]
            tmod[i] += (target_t - tmod[i]) / SYN["tau_mod_s"]
            if connected[i] and not hw_stale:
                na, nb = sens_noise[t][i]
                mod_a[i] = tmod[i] + na + offset_a[i]
                mod_b[i] = None if sensor_open_b[i] else tmod[i] + nb
                on_current = SYN["i_on_A"] if (stuck[i] and state != CS["SAFETY_SHUTDOWN"]) else SYN["i_on_A"] * heat[i] / 100.0
                cur[i] = on_current
            elif not hw_stale:
                cur[i] = 0.0
        if sc.plant_mode == "STANDIN":
            d = sum(SYN["w_ch"][i] * heat[i] / 100.0 for i in range(4))
            h += (d - h) / (SYN["tau_heat_min"] * 60.0)
            dT += SYN["k_heat_degC_per_h"] * h / 3600.0
            t_plant, dT_out = t_pass(t) + dT, dT
        else:
            t_plant, dT_out = None, None

        sd_flag = state == CS["SAFETY_SHUTDOWN"]
        row = {"t_s": t, "Controller_State": state, "Degraded_Substate": sub if state == CS["TWIN_DEGRADED"] else SUB["NONE"],
               "Heat_1": heat[0], "Heat_2": heat[1], "Heat_3": heat[2], "Heat_4": heat[3], "Demand_Global": demand,
               "Trigger_Reason": reason, "Alert": alert, "Safety_Shutdown": int(sd_flag),
               "Fault_Latched": int(sd_flag or any(ch_fault)),
               "fault_code": sys_code if sys_code and sys_code < 100 else (sys_code or next((c for c in ch_fault if c), 0)),
               "Data_Stale_Twin": 0, "Data_Stale_HW": int(data_stale_hw), "Clinician_Mode": int(clin_mode),
               "T_plant": t_plant, "dT_heat": dT_out, "plant_mode": sc.plant_mode}
        for i in range(4):
            row[f"Channel_Fault_{i + 1}"] = ch_fault[i]
            row[f"Module_Temp_{i + 1}_A"] = mod_a[i]
            row[f"Module_Temp_{i + 1}_B"] = mod_b[i]
            row[f"Module_Connected_{i + 1}"] = int(connected[i])
            row[f"Heater_Current_{i + 1}"] = cur[i]
            row[f"HW_Cutoff_{i + 1}"] = int(cutoff[i])
        if sc.press_fields:
            row["Clinician_Start"] = int(press == "start")
            row["Clinician_Stop"] = int(press == "stop")
            row["Clinician_Reset"] = int(press == "reset")
        ctrl_rows.append(row)
        prev_heat = heat
    return twin_rows, ctrl_rows


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            out = []
            for c in columns:
                v = r.get(c)
                if v is None:
                    out.append("")
                elif isinstance(v, float):
                    out.append(f"{v:.6f}")
                else:
                    out.append(str(v))
            w.writerow(out)


def scenarios():
    return [
        Scenario("SYN_SCN_A0", "Usual-care layout stand-in (synthetic, open loop)",
                 "Stand-in for SCN_A until a development-case replay exists: open-loop replay where controller commands do not affect the signal.",
                 90, "OPEN_LOOP", 101, 36.62, 0.45, 1 / 35, -0.35, 0.012,
                 gaps=[(50, 52)], outliers=[(33, 0.85)],
                 loop_description="OPEN LOOP: heating commands are logged but no warming effect is applied (dT_heat null).",
                 extra_limitations=["SCN_A itself requires a development case replay built by build_replay.py; this file only exercises the layout."]),
        Scenario("SYN_SCN_B", "Predictive warming (synthetic, stand-in loop)",
                 "Forecast-triggered warming with an ASSUMED warming response, target maintenance, a level shift and an artefact.",
                 130, "STANDIN", 202, 36.55, 0.35, 1 / 30, -0.25, 0.010,
                 outliers=[(70, 0.9)], level_shifts=[(104, -0.45)],
                 loop_description="STAND-IN LOOP: warming changes the synthetic signal through the ASSUMED response (plan section 4E).",
                 extra_limitations=["The warming effect is the ASSUMED equation with illustrative parameters; it is not a measured or predicted benefit."]),
        Scenario("SYN_SCN_C", "Over-temperature fault (synthetic)",
                 "Clinician-started warming, a simulated CH2 hot-spot, latched SAFETY_SHUTDOWN, a blocked reset, then release.",
                 75, "STANDIN", 303, 36.30, 0.30, 1 / 30, -0.20, 0.010,
                 presses=[(25 * 60, "start"), (52 * 60, "reset"), (60 * 60, "reset")],
                 faults=[Fault("hotspot", 2, 40 * 60, t_clear=46 * 60), Fault("overtemp_sw", 2, 46 * 60, t_clear=57 * 60)],
                 press_fields=True,
                 loop_description="STAND-IN LOOP with scripted fault injection.",
                 extra_limitations=["The fault is injected at a scripted time; module temperatures are illustrative and imply no safety limit (thresholds TBD by Shreehan)."]),
        Scenario("SYN_SCN_D", "Twin degraded (synthetic)",
                 "Observation dropout makes the twin DEGRADED; the forecast is hidden and no autonomous warming occurs until recovery.",
                 80, "STANDIN", 404, 36.45, 0.40, 1 / 30, -0.30, 0.010,
                 gaps=[(33, 47)],
                 loop_description="STAND-IN LOOP; observation gap minutes 33-47."),
        Scenario("SYN_ENG_01", "Clinician START / STOP (synthetic)",
                 "Clinician start, automatic regulation, clinician stop, then the stop-inhibit window before any autonomous trigger.",
                 60, "STANDIN", 505, 36.35, 0.35, 1 / 25, -0.30, 0.010,
                 presses=[(15 * 60, "start"), (30 * 60, "stop")], press_fields=True),
        Scenario("SYN_ENG_02", "Channel faults isolate single channels (synthetic)",
                 "CH3 sensor B open and CH4 disconnected: those channels stop while CH1 and CH2 continue.",
                 60, "STANDIN", 606, 36.25, 0.30, 1 / 30, -0.25, 0.010,
                 presses=[(10 * 60, "start")], press_fields=True,
                 faults=[Fault("sensorB_open", 3, 25 * 60), Fault("disconnect", 4, 35 * 60)]),
        Scenario("SYN_ENG_03", "Stuck-on driver and hardware cutoff (synthetic)",
                 "A stuck-on CH1 driver forces SAFETY_SHUTDOWN; after reset, a CH3 hardware cutoff forces another shutdown.",
                 55, "STANDIN", 707, 36.30, 0.30, 1 / 30, -0.25, 0.010,
                 presses=[(5 * 60, "start"), (18 * 60, "stop"), (30 * 60, "reset"), (35 * 60, "start")], press_fields=True,
                 faults=[Fault("stuck_on", 1, 20 * 60, t_clear=20 * 60 + 3), Fault("hw_cutoff", 3, 44 * 60)]),
        Scenario("SYN_ENG_04", "Hardware data stale (synthetic)",
                 "Hardware status frames stop; after the stale timeout the controller log enters SAFETY_SHUTDOWN.",
                 40, "STANDIN", 808, 36.30, 0.30, 1 / 30, -0.25, 0.010,
                 presses=[(8 * 60, "start")], press_fields=True,
                 faults=[Fault("hw_stale", 0, 25 * 60)]),
        Scenario("SYN_ENG_05", "Twin degraded during clinician warming (synthetic)",
                 "CLINICIAN_FIXED: the twin becomes unreliable while the clinician has warming on; a fixed demand continues, still module-limited.",
                 60, "STANDIN", 909, 36.35, 0.35, 1 / 30, -0.25, 0.010,
                 presses=[(15 * 60, "start")], press_fields=True, gaps=[(30, 41)]),
        Scenario("SYN_ENG_06", "+60 min risk is information only (synthetic)",
                 "Only the +60 min probability exceeds the trigger: an information alert, no heating.",
                 42, "STANDIN", 1010, 36.75, 0.0, 1 / 30, -0.60, 0.004),
    ]


def build_one(sc, out_dir, synth_dir):
    twin_rows, ctrl_rows = simulate(sc)
    twin_cols = build_replay.TWIN_COLUMNS
    ctrl_cols = list(build_replay.CTRL_REQUIRED) + (build_replay.CTRL_OPTIONAL if sc.press_fields else [])
    twin_csv = synth_dir / "twin_outputs" / f"twin_{sc.sid}.csv"
    ctrl_csv = synth_dir / "controller_logs" / f"ctrl_{sc.sid}.csv"
    write_csv(twin_csv, twin_rows, twin_cols)
    write_csv(ctrl_csv, ctrl_rows, ctrl_cols)
    meta = synth_dir / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    info = {"title": sc.title, "purpose": sc.purpose, "data_source": sc.data_source,
            "loop_description": sc.loop_description or "",
            "limitations": COMMON_LIMITATIONS + sc.extra_limitations}
    (meta / f"{sc.sid}.scenario_info.json").write_text(json.dumps(info, indent=1))
    (meta / "params_used.json").write_text(json.dumps(PARAMS_USED, indent=1))
    args = argparse.Namespace(
        scenario_id=sc.sid, twin=str(twin_csv), ctrl=str(ctrl_csv), out=str(out_dir / f"{sc.sid}.jsonl.gz"),
        cohort="SYNTHETIC", obs_source="SIMULATED", twin_source="SIMULATED", case_id=None, holdout_ids=None, dev_ids=None,
        params_version="0.1", spec_version="0.1", params_used=str(meta / "params_used.json"),
        scenario_info=str(meta / f"{sc.sid}.scenario_info.json"), static_context=None, placeholder=True,
        generator=GENERATOR, disclaimer=None, created_utc=CREATED_UTC, enums=str(ROOT / "config" / "enums.json"))
    out, rep, n = build_replay.build(args)
    return out, rep, n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="regenerate into a temp dir and compare with the committed files")
    ap.add_argument("--only", help="comma-separated scenario ids")
    args = ap.parse_args(argv)
    only = set(args.only.split(",")) if args.only else None
    if args.check:
        tmp = Path(tempfile.mkdtemp())
        try:
            bad = []
            for sc in scenarios():
                if only and sc.sid not in only:
                    continue
                out, _, _ = build_one(sc, tmp / "replays", tmp / "synthetic")
                ref = ROOT / "integration" / "replays" / out.name
                if not ref.exists() or not filecmp.cmp(out, ref, shallow=False):
                    bad.append(out.name)
            if bad:
                print("NOT REPRODUCIBLE / STALE:", ", ".join(bad))
                return 1
            print("synthetic replays are byte-identical on regeneration")
            return 0
        finally:
            shutil.rmtree(tmp)
    out_dir = ROOT / "integration" / "replays"
    synth_dir = ROOT / "integration" / "synthetic"
    for sc in scenarios():
        if only and sc.sid not in only:
            continue
        out, rep, n = build_one(sc, out_dir, synth_dir)
        print(f"{out.relative_to(ROOT)}: {n} frames, {rep.warnings} warning(s), codes {sorted(rep.count)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
