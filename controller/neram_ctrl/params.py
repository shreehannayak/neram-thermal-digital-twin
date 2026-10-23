"""Standalone parameter table (T02).

Values are the ones listed in Suchita's docs/controller_spec.md section 6 ("standalone-0.1"), which she carried
unchanged from her submitted script. Every row keeps its status and owner. ``None`` means "not supplied, feature
disabled", never a guessed number.

The repository's config/params.json is NOT read by default: the published results were produced with this table and
the rebuild reproduces them. ``load_params(path)`` overlays a JSON file of {name: value} for experiments.
"""
import copy
import json

PARAMS_VERSION = "standalone-0.1 (config/params.json NOT used)"

# name: (value, unit, status, owner)
TABLE = {
    "ts_ctrl_s": (1, "s", "PROVISIONAL", "Suchita"),
    "ts_twin_s": (60, "s", "FROZEN", "Sai"),
    "data_stale_twin_s": (120, "s", "PROVISIONAL", "Sai"),
    "data_stale_hw_s": (5, "s", "TBD/PLACEHOLDER", "Shreehan"),
    "t_hypo_degC": (36.0, "degC", "TBD/PLACEHOLDER", "Sai"),
    "t_target_degC": (37.0, "degC", "TBD/PLACEHOLDER", "Sai"),
    "p_trigger": (0.3, "-", "PROVISIONAL", "Sai"),
    "p_release": (0.2, "-", "PROVISIONAL", "Sai"),
    "n_confirm_updates": (2, "count", "PROVISIONAL", "Sai"),
    "band_target_degC": (0.3, "degC", "PROVISIONAL", "Suchita"),
    "t_dwell_min_s": (10, "s", "PROVISIONAL", "Suchita"),
    "t_recover_s": (30, "s", "PROVISIONAL", "Suchita"),
    "t_stop_inhibit_s": (300, "s", "PROVISIONAL", "Suchita"),
    "d_pred_max_pct": (40, "%", "PROVISIONAL", "Suchita"),
    "d_active_max_pct": (70, "%", "PROVISIONAL", "Suchita"),
    "d_maint_max_pct": (50, "%", "PROVISIONAL", "Suchita"),
    "d_fallback_pct": (20, "%", "PROVISIONAL", "Suchita"),
    "kp_pct_per_degC": (20, "%/degC", "PROVISIONAL", "Suchita"),
    "ki_pct_per_degC_s": (0.5, "%/(degC*s)", "PROVISIONAL", "Suchita"),
    "p_max_ch_pct": ([50, 50, 50, 50], "%", "TBD/PLACEHOLDER", "Shreehan"),
    "t_mod_derate_degC": (38, "degC", "TBD/PLACEHOLDER", "Shreehan"),
    "t_mod_trip_degC": (41, "degC", "TBD/PLACEHOLDER", "Shreehan"),
    "t_mod_reset_degC": (37, "degC", "TBD/PLACEHOLDER", "Shreehan"),
    "t_hw_cutoff_degC": (None, "degC", "TBD (no placeholder)", "Shreehan"),
    "dt_sensor_disagree_degC": (2.0, "degC", "TBD/PLACEHOLDER", "Shreehan"),
    "i_on_A": (0.5, "A", "TBD/PLACEHOLDER", "Shreehan"),
    "i_open_max_A": (0.05, "A", "TBD/PLACEHOLDER", "Shreehan"),
    "i_over_A": (2.0, "A", "TBD/PLACEHOLDER", "Shreehan"),
    "i_stuck_A": (0.05, "A", "TBD/PLACEHOLDER", "Shreehan"),
    "module_temp_min_degC": (None, "degC", "TBD (no placeholder)", "Shreehan"),
    "module_temp_max_degC": (None, "degC", "TBD (no placeholder)", "Shreehan"),
    "k_heat_degC_per_h": (0.6, "degC/h at 100% all ch", "ASSUMED", "Sai"),
    "tau_heat_min": (15, "min", "ASSUMED", "Sai"),
    "w_ch": ([0.25, 0.25, 0.25, 0.25], "-", "ASSUMED", "Sai"),
    "r_obs_degC2": (0.0025, "degC^2", "PLACEHOLDER", "Sai"),
    "plant_passive.mode": ("flat", "-", "PLACEHOLDER", "Sai"),
    "t_skin_base_degC": (33.0, "degC", "ASSUMED", "Suchita"),
    "k_mod_degC": (6.0, "degC", "ASSUMED", "Suchita"),
    "tau_mod_s": (90, "s", "ASSUMED", "Suchita"),
    "sd_mod_sensor_degC": (0.05, "degC", "ASSUMED", "Suchita"),
    "sd_standin_degC": (0.05, "degC", "ASSUMED", "Suchita"),
    "tau_standin_s": (15, "s", "ASSUMED", "Suchita"),
}

# Implausible-T_est guard used by TwinAdapter (spec section 2).
T_EST_PLAUSIBLE_DEGC = (25.0, 43.0)
# Open-circuit rule: True = qualified rule (default, deviation D1), False = spec-literal rule.
OPEN_RULE_QUALIFIED = True


def default_params():
    return {k: copy.deepcopy(v[0]) for k, v in TABLE.items()}


def load_params(path=None):
    p = default_params()
    if path:
        with open(path) as f:
            over = json.load(f)
        for k, v in over.items():
            if k in p:
                p[k] = v
    return p
