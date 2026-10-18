"""Test bench: test-only stand-ins, synthetic twin scenarios and fault injection (spec section 7).

Every plant and stand-in here is labelled SIMULATED / ASSUMED PROTOTYPE RESPONSE. None of them is Sai's Digital Twin
or Shreehan's hardware.

Random numbers: one numpy Generator with seed 42 per run. Per 1 s tick the module sensors draw 8 normals (sensor A of
CH1..CH4, then sensor B of CH1..CH4); in closed loop the twin stand-in draws one more at each 1-min twin update.
"""
import math

import numpy as np

from .blocks import Controller, NAN, TV_VALID, isnan

SEED = 42
LOG_COLUMNS = (["t_s", "Controller_State", "Degraded_Substate", "Heat_1", "Heat_2", "Heat_3", "Heat_4",
                "Demand_Global", "Trigger_Reason", "Alert", "Safety_Shutdown", "Fault_Latched", "fault_code",
                "Channel_Fault_1", "Channel_Fault_2", "Channel_Fault_3", "Channel_Fault_4", "Data_Stale_Twin",
                "Data_Stale_HW", "Clinician_Mode"]
               + [f"Module_Temp_{c}_{s}" for c in range(1, 5) for s in "AB"]
               + [f"Module_Connected_{c}" for c in range(1, 5)]
               + [f"Heater_Current_{c}" for c in range(1, 5)]
               + [f"HW_Cutoff_{c}" for c in range(1, 5)]
               + ["HW_Heartbeat_s", "HW_Fault_Code", "T_plant", "dT_heat", "plant_mode"])


def phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# ---- synthetic twin scenarios (open loop; values are test inputs, not twin outputs) -------------
def syn_twin(name, t_s, ts_twin=60):
    """Twin outputs held between 1-min updates for the synthetic scenarios SYN_01..SYN_04 and SYN_BELOW."""
    tu = ts_twin * (t_s // ts_twin)
    base = dict(T_twin_s=float(tu), Twin_Valid=TV_VALID, T_obs=NAN, T_est_sd=0.1,
                P_below_hypo_20=0.05, P_below_hypo_30=0.05, P_below_hypo_60=0.05)
    if name == "SYN_01":            # stable, between t_hypo and t_target
        base.update(T_est=36.4)
    elif name == "SYN_02":          # P20 crosses p_trigger at 300 s
        base.update(T_est=36.5, P_below_hypo_20=0.4 if tu >= 300 else 0.05)
    elif name == "SYN_03":          # only P60 crosses at 120 s
        base.update(T_est=36.5, P_below_hypo_60=0.4 if tu >= 120 else 0.05)
    elif name == "SYN_04V":         # SYN_04 with the twin VALID throughout (TC13 counterfactual, TC14 base)
        base.update(T_est=36.5, P_below_hypo_20=0.4)
    elif name == "SYN_04":          # P20 high from the start; twin DEGRADED 300..599 s
        base.update(T_est=36.5, P_below_hypo_20=0.4, Twin_Valid=3 if 300 <= tu < 600 else TV_VALID)
    elif name == "SYN_BELOW":       # below t_hypo (test-only open-loop input for fault tests)
        base.update(T_est=35.5)
    else:
        raise ValueError(name)
    for h in (20, 30, 60):
        base[f"T_pred_{h}"] = base["T_est"]
    return base


class ModuleThermal:
    """ASSUMED per-channel module stand-in: T_mod_i -> t_skin_base + k_mod*Heat_i/100 with tau_mod_s."""

    def __init__(self, P, rng):
        self.P, self.rng = P, rng
        self.T = [float(P["t_skin_base_degC"])] * 4

    def advance(self, heat_applied, dt=1.0):
        P = self.P
        for i in range(4):
            tgt = P["t_skin_base_degC"] + P["k_mod_degC"] * heat_applied[i] / 100.0
            self.T[i] += dt / P["tau_mod_s"] * (tgt - self.T[i])

    def read(self):
        sd = self.P["sd_mod_sensor_degC"]
        a = [self.T[i] + self.rng.normal(0.0, sd) for i in range(4)]
        b = [self.T[i] + self.rng.normal(0.0, sd) for i in range(4)]
        return a, b


class PatientPlant:
    """SIMULATED / ASSUMED PROTOTYPE RESPONSE: d = sum w_i Heat_i/100, h += dt/tau (d - h),
    dT += k_heat*dt/3600*h, T_plant = T_pass + dT with a flat T_pass (plant_passive.* not supplied)."""

    def __init__(self, P, T0=35.0, k_scale=1.0):
        self.P, self.T_pass, self.k = P, T0, P["k_heat_degC_per_h"] * k_scale
        self.h = 0.0
        self.dT = 0.0

    def advance(self, heat_applied, dt=1.0):
        P = self.P
        d = sum(w * h / 100.0 for w, h in zip(P["w_ch"], heat_applied))
        self.h += dt / (P["tau_heat_min"] * 60.0) * (d - self.h)
        self.dT += self.k * dt / 3600.0 * self.h

    @property
    def T(self):
        return self.T_pass + self.dT


class TwinStandin:
    """TWIN STAND-IN (not the Digital Twin). Once per ts_twin_s (the 1-min twin update): T_obs = T_plant + N(0, r_obs);
    T_est = first-order filter of T_obs with time constant tau_standin_s, discretised at the update interval
    (alpha = 1 - exp(-ts_twin_s / tau_standin_s)); P_below_hypo = Phi((t_hypo - T_est) / sd_standin_degC).
    All outputs are held between updates, like the real twin's."""

    def __init__(self, P, rng, noise_scale=1.0):
        self.P, self.rng = P, rng
        self.sd_obs = math.sqrt(P["r_obs_degC2"]) * noise_scale
        self.alpha = 1.0 - math.exp(-P["ts_twin_s"] / P["tau_standin_s"])
        self.filt = None
        self.pub = None

    def step(self, t_s, T_plant):
        P = self.P
        tu = P["ts_twin_s"] * (t_s // P["ts_twin_s"])
        if self.pub is None or self.pub[0] != tu:
            obs = T_plant + self.rng.normal(0.0, self.sd_obs)
            self.filt = obs if self.filt is None else self.filt + self.alpha * (obs - self.filt)
            pb = phi((P["t_hypo_degC"] - self.filt) / P["sd_standin_degC"])
            self.pub = (tu, self.filt, pb, obs)
        tu, est, pb, obs = self.pub
        return dict(T_twin_s=float(tu), Twin_Valid=TV_VALID, T_obs=obs, T_est=est,
                    T_est_sd=P["sd_standin_degC"], T_pred_20=est, T_pred_30=est, T_pred_60=est,
                    P_below_hypo_20=pb, P_below_hypo_30=pb, P_below_hypo_60=pb)


# ---- one run ------------------------------------------------------------------------------------
def run(P, duration_s, scenario, inject=None, closed_loop=False, T0=35.0, k_scale=1.0, twin_noise_scale=1.0,
        twin_override=None, seed=SEED, keep_internal=False):
    """Run the controller for duration_s+1 samples (t = 0..duration_s).

    inject(t, sig) may change any input in place (fault injector, plan M.6): it sits between the stand-ins and the
    controller inputs. Heat commanded at t is applied by the stand-ins one command period later (t+1).
    Returns a list of row dicts in LOG_COLUMNS order (+ internals if keep_internal).
    """
    rng = np.random.default_rng(seed)
    ctrl = Controller(P)
    mod = ModuleThermal(P, rng)
    plant = PatientPlant(P, T0, k_scale) if closed_loop else None
    twin = TwinStandin(P, rng, twin_noise_scale) if closed_loop else None
    heat_applied = [0.0] * 4
    rows = []
    for t in range(int(duration_s) + 1):
        if t > 0:
            mod.advance(heat_applied)
            if plant:
                plant.advance(heat_applied)
        A, B = mod.read()
        if closed_loop:
            tw = twin.step(t, plant.T)
        else:
            tw = syn_twin(scenario, t, P["ts_twin_s"])
        sig = dict(tw)
        if twin_override:
            twin_override(t, sig)
        sig.update(Module_Temp_A=A, Module_Temp_B=B, Module_Connected=[1, 1, 1, 1],
                   Heater_Current=[h / 100.0 * P["i_on_A"] for h in heat_applied], HW_Cutoff=[0, 0, 0, 0],
                   HW_Heartbeat_s=float(t), HW_Fault_Code=0, Clinician_Start=0, Clinician_Stop=0,
                   Clinician_Reset=0)
        if inject:
            inject(t, sig)
        out = ctrl.step(t, sig)
        row = dict(t_s=t, Controller_State=out["Controller_State"], Degraded_Substate=out["Degraded_Substate"])
        for i in range(4):
            row[f"Heat_{i + 1}"] = out["Heat"][i]
        row.update(Demand_Global=out["Demand_Global"], Trigger_Reason=out["Trigger_Reason"], Alert=out["Alert"],
                   Safety_Shutdown=out["Safety_Shutdown"], Fault_Latched=out["Fault_Latched"],
                   fault_code=out["fault_code"])
        for i in range(4):
            row[f"Channel_Fault_{i + 1}"] = out["Channel_Fault"][i]
        row.update(Data_Stale_Twin=out["Data_Stale_Twin"], Data_Stale_HW=out["Data_Stale_HW"],
                   Clinician_Mode=out["Clinician_Mode"])
        for i in range(4):
            row[f"Module_Temp_{i + 1}_A"] = sig["Module_Temp_A"][i]
            row[f"Module_Temp_{i + 1}_B"] = sig["Module_Temp_B"][i]
        for i in range(4):
            row[f"Module_Connected_{i + 1}"] = sig["Module_Connected"][i]
        for i in range(4):
            row[f"Heater_Current_{i + 1}"] = sig["Heater_Current"][i]
        for i in range(4):
            row[f"HW_Cutoff_{i + 1}"] = sig["HW_Cutoff"][i]
        row.update(HW_Heartbeat_s=sig["HW_Heartbeat_s"], HW_Fault_Code=sig["HW_Fault_Code"],
                   T_plant=plant.T if plant else NAN, dT_heat=plant.dT if plant else NAN,
                   plant_mode="STANDIN" if closed_loop else "OPEN_LOOP")
        row["T_est"] = sig["T_est"]
        row["below_hypo"] = out["_tw"]["below_hypo"]
        if keep_internal:
            row["_sig"] = {k: (list(v) if isinstance(v, list) else v) for k, v in sig.items()}
            row["_tw"] = out["_tw"]
        rows.append(row)
        heat_applied = list(out["Heat"])
    return rows


def pulse(t, at):
    return 1 if t in (at if isinstance(at, (list, tuple, set)) else (at,)) else 0


def fmt(v):
    if isinstance(v, str):
        return v
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    if float(v).is_integer():
        return str(int(v))
    return "%.6g" % v


def write_log(path, rows):
    """Section-S CSV: %.6g numbers, NaN as an empty cell, CRLF line ends (as csv.writer writes by default)."""
    with open(path, "w", newline="") as f:
        f.write(",".join(LOG_COLUMNS) + "\r\n")
        for r in rows:
            f.write(",".join(fmt(r[c]) for c in LOG_COLUMNS) + "\r\n")
