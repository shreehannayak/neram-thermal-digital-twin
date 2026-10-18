#!/usr/bin/env python3
"""assumed_warming.py - the ASSUMED, SIMULATED prototype warming response (Team Implementation Plan section 4E).

VitalDB contains no warming-device data, so nothing here is estimated. Every parameter is ASSUMED and
illustrative; any output that uses this response must be labelled "ASSUMED" and shown over the sensitivity
grid 0.5x / 1x / 2x of k_heat (SENSITIVITY_GRID).

    d_t        = sum_i w_i * Heat_{i,t} / 100                 (heater duty 0..100 % -> fraction; weights w_i)
    h_t        = h_{t-1} + (dt / tau_heat) * (d_t - h_{t-1})  (first-order lag, tau_heat in minutes)
    dT_heat_t  = dT_heat_{t-1} + k_heat * (dt / 60) * h_t     (k_heat in degC per hour at 100 % on all channels)
    T_plant_t  = T_pass_t + dT_heat_t

dt is in MINUTES inside the equations (dt_min = dt_s / 60); the replay runs at 1 Hz, so dt_s = 1.

Input rules
  Heat_i outside [0, 100] is rejected (ValueError) - it is never silently clipped.
  A missing (None/NaN) Heat_i is rejected unless missing_as_zero=True, in which case the step uses 0 % for that
  channel and the step index is reported back, so the caller can label the gap.
  w must have 4 non-negative entries; tau_heat > 0; dt_s > 0. Parameters are read from a params snapshot whose
  entries must carry status "ASSUMED" (config/params.json keeps value null; synthetic runs use the labelled
  placeholder recorded in integration/synthetic/meta/params_used.json).

The summit "twin-in-the-loop" version (the twin re-filtering the warmed trajectory) is FUTURE WORK and is not
implemented or claimed here.
"""
import math

SENSITIVITY_GRID = (0.5, 1.0, 2.0)


def params_from_snapshot(snapshot):
    """Read k_heat, tau_heat, w from a params snapshot ({name: {value|placeholder, status, ...}})."""
    out = {}
    for key in ("k_heat_degC_per_h", "tau_heat_min", "w_ch"):
        e = snapshot[key]
        if e.get("status") != "ASSUMED":
            raise ValueError(f"{key} must carry status ASSUMED (got {e.get('status')!r})")
        v = e["value"] if e.get("value") is not None else e.get("placeholder")
        if v is None:
            raise ValueError(f"{key} has neither a value nor a labelled placeholder")
        out[key] = v
    return float(out["k_heat_degC_per_h"]), float(out["tau_heat_min"]), [float(x) for x in out["w_ch"]]


def simulate(heat, t_pass, k_heat, tau_heat_min, w, dt_s=1.0, h0=0.0, dT0=0.0, missing_as_zero=False):
    """heat: sequence of 4-tuples (Heat_1..4 in %); t_pass: sequence of passive temperatures (same length).
    Returns dict(T_plant, dT_heat, h, missing_steps)."""
    if len(heat) != len(t_pass):
        raise ValueError("heat and t_pass must have the same length")
    if len(w) != 4 or any(x < 0 for x in w):
        raise ValueError("w must have 4 non-negative weights")
    if tau_heat_min <= 0 or dt_s <= 0:
        raise ValueError("tau_heat_min and dt_s must be > 0")
    dt_min = dt_s / 60.0
    a = dt_min / tau_heat_min
    if a > 1.0:
        raise ValueError("dt / tau_heat > 1: the explicit update would overshoot")
    h, dT = h0, dT0
    out_T, out_dT, out_h, missing = [], [], [], []
    for n, (row, tp) in enumerate(zip(heat, t_pass)):
        d = 0.0
        for i, x in enumerate(row):
            if x is None or (isinstance(x, float) and math.isnan(x)):
                if not missing_as_zero:
                    raise ValueError(f"step {n}: Heat_{i + 1} missing")
                missing.append(n)
                continue
            if x < 0 or x > 100:
                raise ValueError(f"step {n}: Heat_{i + 1}={x} outside 0..100 %")
            d += w[i] * x / 100.0
        h = h + a * (d - h)
        dT = dT + k_heat * (dt_min / 60.0) * h
        out_h.append(h)
        out_dT.append(dT)
        out_T.append(None if tp is None else tp + dT)
    return dict(T_plant=out_T, dT_heat=out_dT, h=out_h, missing_steps=sorted(set(missing)))


def sensitivity(heat, t_pass, k_heat, tau_heat_min, w, dt_s=1.0, **kw):
    """Run the response for each multiplier of k_heat in SENSITIVITY_GRID."""
    return {m: simulate(heat, t_pass, k_heat * m, tau_heat_min, w, dt_s, **kw) for m in SENSITIVITY_GRID}
