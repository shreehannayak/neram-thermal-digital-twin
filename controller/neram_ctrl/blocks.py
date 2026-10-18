"""The five controller blocks, executed in this order every ts_ctrl_s = 1 s (spec section 2):

TwinAdapter -> FaultMonitor -> Supervisor -> DemandLaw -> ChannelLimiter

Rebuilt by Sai on 18 Oct 2026 from Suchitha's v2 specification (docs/controller_spec.md) after the original v2
source files were lost. SIMULATED / ASSUMED prototype logic; no clinical claim.
"""
import math

from .params import OPEN_RULE_QUALIFIED, T_EST_PLAUSIBLE_DEGC

NAN = float("nan")

# ---- enumerations (spec section 3) -------------------------------------------------------------
NORMAL, PREDICTIVE_WARMING, ACTIVE_WARMING, TARGET_MAINTENANCE, CLINICIAN_WARMING, TWIN_DEGRADED, \
    SAFETY_SHUTDOWN = range(7)
STATE_NAMES = ["NORMAL", "PREDICTIVE_WARMING", "ACTIVE_WARMING", "TARGET_MAINTENANCE", "CLINICIAN_WARMING",
               "TWIN_DEGRADED", "SAFETY_SHUTDOWN"]
SUB_NONE, SUB_MONITOR, SUB_CLINICIAN_FIXED = 0, 1, 2

TR_NONE, TR_FORECAST_P20, TR_FORECAST_P30, TR_TEST_BELOW_HYPO, TR_CLINICIAN_START, TR_TARGET_REACHED, \
    TR_TARGET_LOST, TR_CLINICIAN_STOP, TR_SAFETY_FAULT, TR_TWIN_DEGRADED, TR_TWIN_RECOVERED, \
    TR_CLINICIAN_RESET = range(12)
TRIGGER_NAMES = ["NONE", "FORECAST_P20", "FORECAST_P30", "TEST_BELOW_HYPO", "CLINICIAN_START", "TARGET_REACHED",
                 "TARGET_LOST", "CLINICIAN_STOP", "SAFETY_FAULT", "TWIN_DEGRADED", "TWIN_RECOVERED",
                 "CLINICIAN_RESET"]

AL_NONE, AL_FORECAST_RISK_20_30, AL_FORECAST_RISK_60_INFO, AL_TWIN_DEGRADED, AL_CHANNEL_FAULT, \
    AL_SAFETY_SHUTDOWN, AL_DATA_STALE, AL_CLINICIAN_STOP_ACK, AL_RESET_BLOCKED = range(9)
ALERT_NAMES = ["NONE", "FORECAST_RISK_20_30", "FORECAST_RISK_60_INFO", "TWIN_DEGRADED", "CHANNEL_FAULT",
               "SAFETY_SHUTDOWN", "DATA_STALE", "CLINICIAN_STOP_ACK", "RESET_BLOCKED"]

TV_NO_DATA, TV_INITIALISING, TV_VALID, TV_DEGRADED = range(4)

# Channel fault sub-codes k (code = 100*ch + k)
K_A_OPEN, K_A_RANGE, K_B_OPEN, K_B_RANGE, K_DISAGREE, K_OVERTEMP_SW, K_HW_CUTOFF, K_DISCONNECTED, \
    K_HEATER_OPEN, K_OVERCURRENT, K_STUCK_ON = range(1, 12)
SHUTDOWN_K = (K_OVERTEMP_SW, K_HW_CUTOFF, K_OVERCURRENT, K_STUCK_ON)
SYS_TWIN_STALE_INFO = 7      # informational, never latched
SYS_HW_DATA_STALE = 8

# Demand modes
DM_OFF, DM_PRED, DM_ACTIVE, DM_MAINT, DM_CLIN, DM_FIXED = range(6)


def isnan(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def _dwell(timer, cond, t_s, limit):
    """Hold timer: returns (new_timer, satisfied). Counted in 1 s steps from the first true sample."""
    if not cond:
        return NAN, False
    if isnan(timer):
        timer = t_s
    return timer, (t_s - timer) >= limit


# ================================================================================================
class TwinAdapter:
    """Block 1: consumes the twin outputs held between 1-min updates."""

    def __init__(self, P):
        self.P = P
        self.last_twin_s = NAN
        self.confirm = 0
        self.latched = False
        self.leg = TR_NONE          # FORECAST_P20 or FORECAST_P30, whichever crossed first
        self.stop_t = -math.inf

    def step(self, t_s, sig, stop_rising):
        P = self.P
        T_twin_s = sig["T_twin_s"]
        T_est = sig["T_est"]
        tv = sig["Twin_Valid"]
        stale = isnan(T_twin_s) or (t_s - T_twin_s) > P["data_stale_twin_s"]
        lo, hi = T_EST_PLAUSIBLE_DEGC
        est_ok = (not isnan(T_est)) and lo <= T_est <= hi
        tv_nan = isnan(tv)
        twin_ok = (not tv_nan) and tv == TV_VALID and not stale and est_ok
        twin_bad = tv_nan or tv in (TV_NO_DATA, TV_DEGRADED) or stale or (tv == TV_VALID and not est_ok)

        new_update = (not isnan(T_twin_s)) and (isnan(self.last_twin_s) or T_twin_s != self.last_twin_s)
        if new_update:
            self.last_twin_s = T_twin_s
            p20, p30 = sig["P_below_hypo_20"], sig["P_below_hypo_30"]
            trig20 = (not isnan(p20)) and p20 >= P["p_trigger"]
            trig30 = (not isnan(p30)) and p30 >= P["p_trigger"]
            # A NaN probability never triggers and never releases.
            rel = (not isnan(p20)) and (not isnan(p30)) and p20 < P["p_release"] and p30 < P["p_release"]
            if self.latched:
                if rel or not twin_ok:
                    self.latched, self.confirm, self.leg = False, 0, TR_NONE
            elif twin_ok and (trig20 or trig30):
                if self.leg == TR_NONE:
                    self.leg = TR_FORECAST_P20 if trig20 else TR_FORECAST_P30
                self.confirm += 1
                if self.confirm >= P["n_confirm_updates"]:
                    self.latched = True
            elif not (isnan(p20) and isnan(p30)):
                self.confirm, self.leg = 0, TR_NONE
        if not twin_ok:
            # risk_pred already contains twin_ok (spec T11)
            pass
        risk_pred = self.latched and twin_ok
        p60 = sig["P_below_hypo_60"]
        risk60 = twin_ok and (not isnan(p60)) and p60 >= P["p_trigger"]
        if est_ok:
            below_hypo = T_est < P["t_hypo_degC"]
            at_target = T_est >= P["t_target_degC"]
            target_lost = T_est < P["t_target_degC"] - P["band_target_degC"]
        else:
            below_hypo = at_target = target_lost = False
        if stop_rising:
            self.stop_t = t_s
        stop_inhibit = (t_s - self.stop_t) < P["t_stop_inhibit_s"]
        return dict(Data_Stale_Twin=int(stale), twin_ok=twin_ok, twin_bad=twin_bad, risk_pred=risk_pred,
                    risk_leg=self.leg, risk60=risk60, below_hypo=below_hypo, at_target=at_target,
                    target_lost=target_lost, stop_inhibit=stop_inhibit)


# ================================================================================================
class FaultMonitor:
    """Block 2: persistent latches per channel and system-wide (spec section 5)."""

    def __init__(self, P):
        self.P = P
        self.ch = [0, 0, 0, 0]
        self.hw_latch = 0             # latched system code from HW_Fault_Code / hardware stale
        self.disagree_t = [NAN] * 4
        self.open_t = [NAN] * 4
        self.stuck_n = [0, 0, 0, 0]
        self.literal_open_rule = not OPEN_RULE_QUALIFIED

    @staticmethod
    def _rank(code):
        return 2 if code % 100 in SHUTDOWN_K else 1

    def step(self, t_s, sig, heat_prev, reset_rising):
        P = self.P
        hb = sig["HW_Heartbeat_s"]
        hw_stale = isnan(hb) or (t_s - hb) > P["data_stale_hw_s"]
        hwc = sig["HW_Fault_Code"]
        lo_r, hi_r = P.get("module_temp_min_degC"), P.get("module_temp_max_degC")
        tmods = []
        present = [0, 0, 0, 0]
        for i in range(4):
            c = i + 1
            A, B = sig["Module_Temp_A"][i], sig["Module_Temp_B"][i]
            conn = sig["Module_Connected"][i]
            I = sig["Heater_Current"][i]
            cut = sig["HW_Cutoff"][i]
            a_bad, b_bad = isnan(A), isnan(B)
            work = [x for x in (A, B) if not isnan(x)]
            T_mod = max(work) if work else NAN
            tmods.append(T_mod)
            cand = []
            disconnected = isnan(conn) or conn == 0
            if disconnected:
                cand.append(K_DISCONNECTED)
                self.open_t[i] = NAN
            if a_bad:
                cand.append(K_A_OPEN)
            elif lo_r is not None and hi_r is not None and not (lo_r <= A <= hi_r):
                cand.append(K_A_RANGE)
            if b_bad:
                cand.append(K_B_OPEN)
            elif lo_r is not None and hi_r is not None and not (lo_r <= B <= hi_r):
                cand.append(K_B_RANGE)
            if not a_bad and not b_bad and abs(A - B) > P["dt_sensor_disagree_degC"]:
                self.disagree_t[i], ok = _dwell(self.disagree_t[i], True, t_s, P["t_dwell_min_s"])
                if ok:
                    cand.append(K_DISAGREE)
            else:
                self.disagree_t[i] = NAN
            if not isnan(T_mod) and T_mod >= P["t_mod_trip_degC"]:
                cand.append(K_OVERTEMP_SW)
            if (not isnan(cut)) and cut:
                cand.append(K_HW_CUTOFF)
            hp = heat_prev[i]
            if not disconnected:
                if isnan(I):
                    cand.append(K_HEATER_OPEN)
                    self.stuck_n[i] = 0
                else:
                    expected = hp / 100.0 * P["i_on_A"]
                    open_cond = hp > 0 and I < P["i_open_max_A"]
                    if not self.literal_open_rule:
                        open_cond = open_cond and expected >= P["i_open_max_A"]
                    self.open_t[i], ok = _dwell(self.open_t[i], open_cond, t_s, P["t_dwell_min_s"])
                    if ok:
                        cand.append(K_HEATER_OPEN)
                    if I > P["i_over_A"]:
                        cand.append(K_OVERCURRENT)
                    if hp == 0 and I > P["i_stuck_A"]:
                        self.stuck_n[i] += 1
                    else:
                        self.stuck_n[i] = 0
                    if self.stuck_n[i] >= 2:
                        cand.append(K_STUCK_ON)
            if cand:
                # shutdown class first, then lowest sub-code
                k = sorted(cand, key=lambda k: (0 if k in SHUTDOWN_K else 1, k))[0]
                code = 100 * c + k
                if self.ch[i] == 0 or self._rank(code) > self._rank(self.ch[i]):
                    self.ch[i] = code
            # condition-cleared test for the latched code (used on Reset)
            k = self.ch[i] % 100
            still = False
            if k in (K_A_OPEN, K_A_RANGE):
                still = a_bad or K_A_RANGE in cand
            elif k in (K_B_OPEN, K_B_RANGE):
                still = b_bad or K_B_RANGE in cand
            elif k == K_DISAGREE:
                still = (not a_bad) and (not b_bad) and abs(A - B) > P["dt_sensor_disagree_degC"]
            elif k == K_OVERTEMP_SW:
                still = isnan(T_mod) or T_mod >= P["t_mod_reset_degC"]
            elif k == K_HW_CUTOFF:
                still = isnan(cut) or bool(cut)
            elif k == K_DISCONNECTED:
                still = disconnected
            elif k == K_HEATER_OPEN:
                still = isnan(I)
            elif k == K_OVERCURRENT:
                still = isnan(I) or I > P["i_over_A"]
            elif k == K_STUCK_ON:
                still = isnan(I) or I > P["i_stuck_A"]
            present[i] = still

        hw_code_now = 0
        if isnan(hwc):
            hw_code_now = SYS_HW_DATA_STALE
        elif hwc != 0:
            hw_code_now = int(hwc)
        if hw_stale:
            hw_code_now = hw_code_now or SYS_HW_DATA_STALE
        if hw_code_now and not self.hw_latch:
            self.hw_latch = hw_code_now

        if reset_rising:
            for i in range(4):
                if self.ch[i] and not present[i]:
                    self.ch[i] = 0
                    self.disagree_t[i] = NAN
                    self.open_t[i] = NAN
                    self.stuck_n[i] = 0
            if self.hw_latch and hw_code_now == 0:
                self.hw_latch = 0

        shut_ch = [c for c in self.ch if c and c % 100 in SHUTDOWN_K]
        iso_ch = [c for c in self.ch if c and c % 100 not in SHUTDOWN_K]
        system_fault = bool(self.hw_latch) or bool(shut_ch)
        if self.hw_latch:
            fc = self.hw_latch
        elif shut_ch:
            fc = shut_ch[0]
        elif iso_ch:
            fc = iso_ch[0]
        else:
            fc = 0
        return dict(Channel_Fault=list(self.ch), system_fault=system_fault, fault_code=fc,
                    Fault_Latched=int(system_fault or any(self.ch)), Data_Stale_HW=int(hw_stale), T_mod=tmods)


# ================================================================================================
class Supervisor:
    """Block 3: Python state machine standing in for the Stateflow chart (states 0-6, T1-T14)."""

    def __init__(self, P):
        self.P = P
        self.state = NORMAL
        self.sub = SUB_NONE
        self.clin_mode = False
        self.reason = TR_NONE
        self.timers = {}

    def _t(self, name, cond, t_s, limit):
        self.timers[name], ok = _dwell(self.timers.get(name, NAN), cond, t_s, limit)
        return ok

    def step(self, t_s, tw, fm, start_r, stop_r, reset_r, T_mod):
        P = self.P
        prev = (self.state, self.sub)
        dw, rec = P["t_dwell_min_s"], P["t_recover_s"]
        reset_blocked = stop_ack = False
        new_state, new_sub, reason = None, None, None
        st = self.state
        warming = st in (PREDICTIVE_WARMING, ACTIVE_WARMING, TARGET_MAINTENANCE, CLINICIAN_WARMING) or \
            (st == TWIN_DEGRADED and self.sub == SUB_CLINICIAN_FIXED)

        # timers are evaluated every sample (held conditions)
        t5 = self._t("T5", st == TWIN_DEGRADED and self.sub == SUB_MONITOR and tw["twin_ok"], t_s, rec)
        t6 = self._t("T6", st == TWIN_DEGRADED and self.sub == SUB_CLINICIAN_FIXED and tw["twin_ok"], t_s, rec)
        t10 = self._t("T10", st == NORMAL and tw["twin_ok"] and tw["below_hypo"] and not tw["stop_inhibit"],
                      t_s, dw)
        t11 = self._t("T11", st == NORMAL and tw["risk_pred"] and not tw["below_hypo"] and not tw["stop_inhibit"],
                      t_s, dw)
        t12 = self._t("T12", st == PREDICTIVE_WARMING and tw["below_hypo"], t_s, dw)
        t13 = self._t("T13", st in (PREDICTIVE_WARMING, ACTIVE_WARMING, CLINICIAN_WARMING) and tw["at_target"],
                      t_s, dw)
        t14 = self._t("T14", st == TARGET_MAINTENANCE and tw["target_lost"], t_s, dw)

        if st != SAFETY_SHUTDOWN and fm["system_fault"]:                              # T1
            new_state, new_sub, reason = SAFETY_SHUTDOWN, SUB_NONE, TR_SAFETY_FAULT
        elif st == SAFETY_SHUTDOWN:                                                     # T2
            if reset_r:
                cool = all((not isnan(t)) and t < P["t_mod_reset_degC"] for t in T_mod)
                if not fm["system_fault"] and cool:
                    new_state, new_sub, reason = NORMAL, SUB_NONE, TR_CLINICIAN_RESET
                    self.clin_mode = False
                else:
                    reset_blocked = True
        elif stop_r and warming:                                                        # T3
            new_state, new_sub, reason = NORMAL, SUB_NONE, TR_CLINICIAN_STOP
            self.clin_mode = False
            stop_ack = True
        elif stop_r:
            pass                     # Stop in NORMAL/MONITOR: no transition; stop_inhibit already started
        elif tw["twin_bad"] and st in (NORMAL, PREDICTIVE_WARMING, ACTIVE_WARMING, TARGET_MAINTENANCE,
                                       CLINICIAN_WARMING):                              # T4
            if self.clin_mode or start_r:
                self.clin_mode = True
                new_sub = SUB_CLINICIAN_FIXED
            else:
                new_sub = SUB_MONITOR
            new_state, reason = TWIN_DEGRADED, TR_TWIN_DEGRADED
        elif st == TWIN_DEGRADED and self.sub == SUB_MONITOR:
            if start_r:                                                                 # T7
                new_state, new_sub, reason = TWIN_DEGRADED, SUB_CLINICIAN_FIXED, TR_CLINICIAN_START
                self.clin_mode = True
            elif t5:                                                                    # T5
                new_state, new_sub, reason = NORMAL, SUB_NONE, TR_TWIN_RECOVERED
        elif st == TWIN_DEGRADED and self.sub == SUB_CLINICIAN_FIXED:
            if t6:                                                                      # T6
                new_state, new_sub, reason = CLINICIAN_WARMING, SUB_NONE, TR_TWIN_RECOVERED
        elif st in (NORMAL, PREDICTIVE_WARMING) and start_r and tw["twin_ok"]:          # T8
            new_state, new_sub, reason = CLINICIAN_WARMING, SUB_NONE, TR_CLINICIAN_START
            self.clin_mode = True
        elif st == NORMAL and start_r and not tw["twin_ok"]:                            # T9
            new_state, new_sub, reason = TWIN_DEGRADED, SUB_CLINICIAN_FIXED, TR_CLINICIAN_START
            self.clin_mode = True
        elif st == NORMAL and t10:                                                      # T10
            new_state, new_sub, reason = ACTIVE_WARMING, SUB_NONE, TR_TEST_BELOW_HYPO
        elif st == NORMAL and t11:                                                      # T11
            new_state, new_sub, reason = PREDICTIVE_WARMING, SUB_NONE, tw["risk_leg"] or TR_FORECAST_P20
        elif st == PREDICTIVE_WARMING and t12:                                          # T12
            new_state, new_sub, reason = ACTIVE_WARMING, SUB_NONE, TR_TEST_BELOW_HYPO
        elif st in (PREDICTIVE_WARMING, ACTIVE_WARMING, CLINICIAN_WARMING) and t13:     # T13
            new_state, new_sub, reason = TARGET_MAINTENANCE, SUB_NONE, TR_TARGET_REACHED
        elif st == TARGET_MAINTENANCE and t14:                                          # T14
            new_state, new_sub, reason = ACTIVE_WARMING, SUB_NONE, TR_TARGET_LOST
        elif st in (ACTIVE_WARMING, TARGET_MAINTENANCE) and start_r:                    # R1
            self.clin_mode = True

        if new_state is not None:
            self.state, self.sub, self.reason = new_state, new_sub, reason
        entry = (self.state, self.sub) != prev
        if entry:
            self.timers = {}

        s = self.state
        if s == SAFETY_SHUTDOWN:
            mode = DM_OFF
        elif s == TWIN_DEGRADED:
            mode = DM_FIXED if self.sub == SUB_CLINICIAN_FIXED else DM_OFF
        else:
            mode = {NORMAL: DM_OFF, PREDICTIVE_WARMING: DM_PRED, ACTIVE_WARMING: DM_ACTIVE,
                    TARGET_MAINTENANCE: DM_MAINT, CLINICIAN_WARMING: DM_CLIN}[s]

        if reset_blocked:
            alert = AL_RESET_BLOCKED
        elif s == SAFETY_SHUTDOWN:
            alert = AL_SAFETY_SHUTDOWN
        elif stop_ack:
            alert = AL_CLINICIAN_STOP_ACK
        elif any(fm["Channel_Fault"]):
            alert = AL_CHANNEL_FAULT
        elif s == TWIN_DEGRADED:
            alert = AL_TWIN_DEGRADED
        elif s in (NORMAL, PREDICTIVE_WARMING) and (tw["risk_pred"] or s == PREDICTIVE_WARMING):
            alert = AL_FORECAST_RISK_20_30
        elif s == NORMAL and tw["risk60"]:
            alert = AL_FORECAST_RISK_60_INFO
        else:
            alert = AL_NONE
        return dict(Controller_State=s, Degraded_Substate=self.sub, Trigger_Reason=self.reason, Alert=alert,
                    Safety_Shutdown=int(s == SAFETY_SHUTDOWN), Clinician_Mode=int(self.clin_mode),
                    demand_mode=mode, state_entry=entry)


# ================================================================================================
class DemandLaw:
    """Block 4: PI on e = t_target - T_est with clamping anti-windup; integrator reset on every state entry."""

    def __init__(self, P):
        self.P = P
        self.integ = 0.0

    def step(self, T_est, mode, entry):
        P = self.P
        if entry:
            self.integ = 0.0
        if mode == DM_OFF:
            self.integ = 0.0
            return 0.0
        if mode == DM_FIXED:
            return float(P["d_fallback_pct"])
        cap = {DM_PRED: P["d_pred_max_pct"], DM_ACTIVE: P["d_active_max_pct"], DM_MAINT: P["d_maint_max_pct"],
               DM_CLIN: P["d_active_max_pct"]}[mode]
        if isnan(T_est):
            return 0.0
        e = P["t_target_degC"] - T_est
        trial_i = self.integ + P["ki_pct_per_degC_s"] * e * P["ts_ctrl_s"]
        trial = P["kp_pct_per_degC"] * e + trial_i
        if 0.0 <= trial <= cap:
            self.integ = trial_i
        return float(min(max(trial, 0.0), cap))


# ================================================================================================
def channel_limiter(P, D, fm, sig, shutdown):
    """Block 5: Heat_i = enable_i * min(D, p_max_ch_pct_i * derate_i), clamped to [0, p_max_ch_pct_i]."""
    heat = []
    if all(fm["Channel_Fault"]):
        D = 0.0
    for i in range(4):
        conn = sig["Module_Connected"][i]
        cut = sig["HW_Cutoff"][i]
        enable = not (fm["Channel_Fault"][i] or isnan(conn) or conn == 0 or isnan(cut) or cut or shutdown)
        A, B = sig["Module_Temp_A"][i], sig["Module_Temp_B"][i]
        if isnan(A) or isnan(B):
            derate = 0.0
        else:
            tm = max(A, B)
            if tm <= P["t_mod_derate_degC"]:
                derate = 1.0
            elif tm >= P["t_mod_trip_degC"]:
                derate = 0.0
            else:
                derate = (P["t_mod_trip_degC"] - tm) / (P["t_mod_trip_degC"] - P["t_mod_derate_degC"])
        pmax = P["p_max_ch_pct"][i]
        h = min(D, pmax * derate) if enable else 0.0
        heat.append(float(min(max(h, 0.0), pmax)))
    return heat


# ================================================================================================
class Controller:
    """Wires the five blocks; one step() = one 1 s control tick."""

    def __init__(self, P):
        self.P = P
        self.twin = TwinAdapter(P)
        self.fault = FaultMonitor(P)
        self.sup = Supervisor(P)
        self.dem = DemandLaw(P)
        self.heat_prev = [0.0] * 4
        self.prev_btn = dict(Clinician_Start=0, Clinician_Stop=0, Clinician_Reset=0)

    def step(self, t_s, sig):
        # Rising edges computed once per sample and shared by every block.
        r = {}
        for k in self.prev_btn:
            v = sig.get(k, 0) or 0
            r[k] = bool(v) and not bool(self.prev_btn[k])
            self.prev_btn[k] = v
        tw = self.twin.step(t_s, sig, r["Clinician_Stop"])
        fm = self.fault.step(t_s, sig, self.heat_prev, r["Clinician_Reset"])
        sv = self.sup.step(t_s, tw, fm, r["Clinician_Start"], r["Clinician_Stop"], r["Clinician_Reset"],
                           fm["T_mod"])
        D = self.dem.step(sig["T_est"], sv["demand_mode"], sv["state_entry"])
        heat = channel_limiter(self.P, D, fm, sig, sv["Safety_Shutdown"])
        if all(fm["Channel_Fault"]):
            D = 0.0
        self.heat_prev = heat
        fc = fm["fault_code"]
        if fc == 0 and tw["Data_Stale_Twin"]:
            fc = SYS_TWIN_STALE_INFO
        return dict(Controller_State=sv["Controller_State"], Degraded_Substate=sv["Degraded_Substate"],
                    Heat=heat, Demand_Global=D, Trigger_Reason=sv["Trigger_Reason"], Alert=sv["Alert"],
                    Safety_Shutdown=sv["Safety_Shutdown"], Fault_Latched=fm["Fault_Latched"], fault_code=fc,
                    Channel_Fault=fm["Channel_Fault"], Data_Stale_Twin=tw["Data_Stale_Twin"],
                    Data_Stale_HW=fm["Data_Stale_HW"], Clinician_Mode=sv["Clinician_Mode"],
                    _tw=tw, _fm=fm, _sv=sv)
