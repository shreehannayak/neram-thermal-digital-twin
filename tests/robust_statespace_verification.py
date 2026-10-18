"""
robust_statespace_verification.py   (corrected replacement; uses thermal_robust_core)

Synthetic verification of the combined robust state-space model. Reads no real data, no VitalDB,
no holdout. Synthetic truth is local to this file and passed EXPLICITLY to the shared core functions.

Corrections relative to the earlier version
  A  gamma is no longer a module global inside the filter; it is an explicit argument (core).
  B  m0 and S are explicit arguments; synthetic values live only in this file.
  C  the filter is named gpb2_filter (the old name gpb1() was misleading when running GPB2).
  D  the GPB2 approximation is documented precisely in thermal_robust_core.py.
  F  the terminal test is renamed F_terminal_online_trend_contamination_below_0p10_per_h and the online
     LEVEL absorption of the terminal drop is reported explicitly (it is not hidden by a pass).
  G  the report separates exact within-component Kalman updates from approximate mixture-history merging.
  H  verdicts are cast to Python bool before JSON serialisation (previously numpy bools became 1.0).
  The rank-pruned PGS(K) comparison is historical (rejected: non-smooth likelihood) and is not re-run.

Parameter recovery is read from recovery_checkpoint_v2.json written by recovery_resume.py (run it first).
"""

import json
import os
import time

import numpy as np
import pandas as pd
from scipy.special import logsumexp

import thermal_robust_core as C

OUT = "robust_model_verification"
os.makedirs(OUT, exist_ok=True)
LOG2PI, I3 = C.LOG2PI, C.I3

# ---------------- synthetic truth (local to this file; never imported elsewhere) ----------------
SYN_GAMMA = 0.031
SYN_M0 = np.array([0.40, 0.10])
SYN_S = np.array([[0.25, 0.03], [0.03, 0.09]])
TRUE = dict(q=0.15 ** 2 / 60, r=0.03 ** 2, pi_u=0.002, q_J=1.5 ** 2, pi_e=0.005, r_O=2.0 ** 2)
W_T = 30
HORIZONS = [20, 30, 60]
N_REPL = 40
CRIT = dict(smooth_max_event_prob=0.5, smooth_vs_gauss_median_diff=0.01, shift02_tol=0.05, shift15_tol=0.10,
            transient02_tol=0.05, transient20_tol=0.10, outlier_tol=0.05, multijump_tol=0.10, terminal_dbeta_max=0.10,
            exact_limit_tol=1e-10, approx_mean_median=0.01, approx_mean_p90=0.05, approx_var_ratio_median=(0.9, 1.1),
            rbpf_mean_tol=0.05, rbpf_var_ratio=(0.8, 1.25), recover_qr_rel=0.30, recover_rare_ratio=(0.5, 2.0),
            leak_tol=1e-12, likelihood_smooth_max=0.01, interval_mc_tol=0.005)


def filt(Y, p, store=False, S=SYN_S, m0=SYN_M0):
    Y = np.atleast_2d(np.asarray(Y, float))
    return C.gpb2_filter(Y, p, np.tile(m0, (len(Y), 1)), S, SYN_GAMMA, store_probs=store)


def fmean(out, i, o, h, p):
    m, v, *_ = C.forecast_moments(out["LW"][i:i + 1], out["Z"][i:i + 1], out["PP"][i:i + 1], np.array([o]), h, p, SYN_GAMMA)
    return float(m[0]), float(v[0])


def gauss(p):
    return dict(q=p["q"], r=p["r"], pi_u=0.0, q_J=p["q"], pi_e=0.0, r_O=p["r"])


def base_traj(T, seed, u0=36.5):
    rg = np.random.default_rng(seed)
    t = np.arange(T)
    u = u0 + np.concatenate([[0], np.cumsum(rg.normal(0, np.sqrt(TRUE["q"]), T - 1))])
    return C.phi(t, SYN_GAMMA) @ SYN_M0 + u + rg.normal(0, np.sqrt(TRUE["r"]), T)


# ---------------- independent references ----------------
def exact_enumeration(y, p):
    ph = C.phi(0, SYN_GAMMA)
    lw, Z, PP = [], [], []
    for ro, wo in ((p["r"], 1 - p["pi_e"]), (p["r_O"], p["pi_e"])):
        Pi = np.zeros((3, 3)); Pi[:2, :2] = SYN_S; Pi[:2, 2] = Pi[2, :2] = -SYN_S @ ph; Pi[2, 2] = ph @ SYN_S @ ph + ro
        lw.append(np.log(wo)); Z.append([SYN_M0[0], SYN_M0[1], y[0] - SYN_M0 @ ph]); PP.append(Pi)
    lw, Z, PP = np.array(lw), np.array(Z, float), np.array(PP)
    for t in range(1, len(y)):
        h = C.Hrow(t, SYN_GAMMA)
        nl, nz, nP = [], [], []
        for qj, wj in ((p["q"], 1 - p["pi_u"]), (p["q_J"], p["pi_u"])):
            for ro, wo in ((p["r"], 1 - p["pi_e"]), (p["r_O"], p["pi_e"])):
                Pj = PP.copy(); Pj[:, 2, 2] += qj
                v = y[t] - Z @ h
                Fv = np.einsum("i,nij,j->n", h, Pj, h) + ro
                K = np.einsum("nij,j->ni", Pj, h) / Fv[:, None]
                IKH = I3[None] - np.einsum("ni,j->nij", K, h)
                nz.append(Z + K * v[:, None]); nP.append(np.einsum("nij,njk,nlk->nil", IKH, Pj, IKH) + ro * np.einsum("ni,nj->nij", K, K))
                nl.append(lw + np.log(wj) + np.log(wo) - 0.5 * (LOG2PI + np.log(Fv) + v * v / Fv))
        lw, Z, PP = np.concatenate(nl), np.concatenate(nz), np.concatenate(nP)
    return np.exp(lw - logsumexp(lw)), Z, PP


def mixture_mv(w, Z, PP, o, h, p):
    hh = C.Hrow(o + h, SYN_GAMMA); qbar, rbar = C.mix_moments(p)
    mu = Z @ hh; m = float(w @ mu)
    return m, float(w @ (np.einsum("i,nij,j->n", hh, PP, hh) + (mu - m) ** 2)) + h * qbar + rbar


def rbpf(y, o, p, n_part=3000, seed=0):
    rg = np.random.default_rng(seed)
    qs, rs = np.array([p["q"], p["q_J"]]), np.array([p["r"], p["r_O"]])
    lpj, lpo = np.log([1 - p["pi_u"], p["pi_u"]]), np.log([1 - p["pi_e"], p["pi_e"]])
    _, rbar = C.mix_moments(p)
    ph = C.phi(0, SYN_GAMMA)
    Z = np.tile([SYN_M0[0], SYN_M0[1], y[0] - SYN_M0 @ ph], (n_part, 1))
    Pi = np.zeros((3, 3)); Pi[:2, :2] = SYN_S; Pi[:2, 2] = Pi[2, :2] = -SYN_S @ ph; Pi[2, 2] = ph @ SYN_S @ ph + rbar
    PP = np.tile(Pi, (n_part, 1, 1)); lw = np.zeros(n_part)
    for t in range(1, o + 1):
        h = C.Hrow(t, SYN_GAMMA); v = y[t] - Z @ h; Phb = PP @ h; hPh = Phb @ h
        cz, cP, cl = [], [], []
        for k in range(4):
            qj, ro = qs[C.HYP_J[k]], rs[C.HYP_O[k]]
            Pj = PP.copy(); Pj[:, 2, 2] += qj; Pjh = Phb.copy(); Pjh[:, 2] += qj
            Fv = hPh + qj + ro; K = Pjh / Fv[:, None]; IKH = I3[None] - np.einsum("ni,j->nij", K, h)
            cz.append(Z + K * v[:, None]); cP.append(np.einsum("nij,njk,nlk->nil", IKH, Pj, IKH) + ro * np.einsum("ni,nj->nij", K, K))
            cl.append(-0.5 * (LOG2PI + np.log(Fv) + v * v / Fv) + lpj[C.HYP_J[k]] + lpo[C.HYP_O[k]])
        cl = np.stack(cl, 1); lse = logsumexp(cl, axis=1); pr = np.exp(cl - lse[:, None])
        pick = (rg.random(n_part)[:, None] > np.cumsum(pr, 1)).sum(1).clip(0, 3); idx = np.arange(n_part)
        Z, PP = np.stack(cz, 1)[idx, pick], np.stack(cP, 1)[idx, pick]
        lw = lw + lse; w = np.exp(lw - logsumexp(lw))
        if 1 / np.sum(w ** 2) < n_part / 2:
            sel = np.searchsorted(np.cumsum(w), (rg.random() + np.arange(n_part)) / n_part).clip(0, n_part - 1)
            Z, PP, lw = Z[sel], PP[sel], np.zeros(n_part)
    return np.exp(lw - logsumexp(lw)), Z, PP


def response(perturb, origins, T=240, p=TRUE):
    Y0 = np.array([base_traj(T, 1000 + s) for s in range(N_REPL)])
    Y1 = np.array([y + perturb(np.arange(T), y) for y in Y0])
    rows = []
    for o in origins:
        for name, pp in (("robust", p), ("gaussian_rw", gauss(p))):
            a, b = filt(Y0[:, :o + 1], pp), filt(Y1[:, :o + 1], pp, store=(name == "robust"))
            row = dict(model=name, origin=o, dbeta_C_per_h=float(np.median(b["z"][:, 1] - a["z"][:, 1])),
                       dlevel_u_C=float(np.median(b["z"][:, 2] - a["z"][:, 2])))
            for h in HORIZONS:
                row[f"dforecast_h{h}"] = float(np.median([fmean(b, i, o, h, pp)[0] - fmean(a, i, o, h, pp)[0] for i in range(N_REPL)]))
            if name == "robust":
                row["max_P_jump"] = float(np.median(np.nanmax(b["prob"]["jump"], 1)))
                row["max_P_outlier"] = float(np.median(np.nanmax(b["prob"]["outlier"], 1)))
            rows.append(row)
    return pd.DataFrame(rows)


VERD, RES = {}, {}
t0 = time.time()
print("=" * 78)
print("SYNTHETIC VERIFICATION (corrected; shared core thermal_robust_core.py)")
print("=" * 78)

# ---- exact limits ----
y = base_traj(240, 7)
g_ref = filt(y[:201], gauss(TRUE))
lim = {}
for name, pp in (("pi_to_0", dict(TRUE, pi_u=0.0, pi_e=0.0)), ("components_equal", dict(TRUE, q_J=TRUE["q"], r_O=TRUE["r"]))):
    r_ = filt(y[:201], pp)
    lim[name] = float(max(np.abs(r_["z"] - g_ref["z"]).max(), np.abs(r_["P"] - g_ref["P"]).max()))
t_ = np.arange(201.0); X = C.phi(t_, SYN_GAMMA); one = np.ones(201)
V = X @ SYN_S @ X.T + TRUE["q"] * np.minimum.outer(t_, t_) + TRUE["r"] * np.eye(201); Vi = np.linalg.inv(V)
xs = C.phi(230.0, SYN_GAMMA); c = X @ SYN_S @ xs + TRUE["q"] * np.minimum(t_, 230.0); d = y[:201] - X @ SYN_M0
a = one @ Vi @ one; uh = one @ Vi @ d / a
gm, gv = fmean(g_ref, 0, 200, 30, gauss(TRUE))
lim["analytic_mean"] = float(abs(gm - (xs @ SYN_M0 + uh + c @ Vi @ (d - one * uh))))
lim["analytic_var"] = float(abs(gv - (xs @ SYN_S @ xs + TRUE["q"] * 230 + TRUE["r"] - c @ Vi @ c + (1 - one @ Vi @ c) ** 2 / a)))
VERD["L_exact_gaussian_limits"] = bool(all(v < CRIT["exact_limit_tol"] for v in lim.values()))
RES["limits"] = lim
print("Limits:", {k: f"{v:.1e}" for k, v in lim.items()}, "->", "PASS" if VERD["L_exact_gaussian_limits"] else "FAIL")

# ---- approximation vs exact enumeration ----
rows = []
for k in range(30):
    yy = base_traj(8, 500 + k)
    if k % 3 == 1:
        yy[4:] += 1.0
    if k % 3 == 2:
        yy[5] += 3.0
    w, Z, PP = exact_enumeration(yy, TRUE)
    g = filt(yy, TRUE)
    for h in HORIZONS:
        em, ev = mixture_mv(w, Z, PP, 7, h, TRUE); fm, fv = fmean(g, 0, 7, h, TRUE)
        rows.append(dict(kind=["clean", "jump", "outlier"][k % 3], h=h, abs_mean_err=abs(fm - em), var_ratio=fv / ev))
AP = pd.DataFrame(rows); AP.to_csv(f"{OUT}/approx_gpb2_vs_exact.csv", index=False)
VERD["APPROX_gpb2_vs_exact_enumeration"] = bool(AP.abs_mean_err.median() <= CRIT["approx_mean_median"]
                                                and AP.abs_mean_err.quantile(.9) <= CRIT["approx_mean_p90"]
                                                and CRIT["approx_var_ratio_median"][0] <= AP.var_ratio.median() <= CRIT["approx_var_ratio_median"][1])
print(f"GPB2 vs exact: |mean err| median {AP.abs_mean_err.median():.1e}, p90 {AP.abs_mean_err.quantile(.9):.1e}, "
      f"max {AP.abs_mean_err.max():.1e} C; var ratio median {AP.var_ratio.median():.4f} -> "
      f"{'PASS' if VERD['APPROX_gpb2_vs_exact_enumeration'] else 'FAIL'}")

# ---- approximation vs RBPF ----
rows = []
scen = {"smooth": lambda t, y: 0 * t, "multijump": lambda t, y: 1.0 * (t >= 60) - 1.5 * (t >= 120) + 0.8 * (t >= 180),
        "outlier": lambda t, y: 5.0 * (t == 100)}
for name, f_ in scen.items():
    for sd in range(3):
        yy = base_traj(240, 2000 + sd); yy = yy + f_(np.arange(240), yy)
        for o in (61, 101, 125, 185, 230):
            g = filt(yy[:o + 1], TRUE); w, Z, PP = rbpf(yy, o, TRUE, seed=sd)
            for h in (30, 60):
                rm, rv = mixture_mv(w, Z, PP, o, h, TRUE); fm, fv = fmean(g, 0, o, h, TRUE)
                rows.append(dict(scenario=name, origin=o, h=h, abs_mean_diff=abs(fm - rm), var_ratio=fv / rv))
RB = pd.DataFrame(rows); RB.to_csv(f"{OUT}/approx_gpb2_vs_rbpf.csv", index=False)
VERD["APPROX_gpb2_vs_RBPF"] = bool((RB.abs_mean_diff <= CRIT["rbpf_mean_tol"]).all() and RB.var_ratio.between(*CRIT["rbpf_var_ratio"]).all())
print(f"GPB2 vs RBPF: max |mean diff| {RB.abs_mean_diff.max():.4f} C; var ratio [{RB.var_ratio.min():.3f}, {RB.var_ratio.max():.3f}] -> "
      f"{'PASS' if VERD['APPROX_gpb2_vs_RBPF'] else 'FAIL'}")

# ---- likelihood smoothness on event-rich data ----
Ysm = np.array([base_traj(200, 8000 + i) for i in range(40)]); Ysm[:, 80:] += 1.0; Ysm[:, 120] += 3.0; Ysm[:, 150:153] -= 2.0
vals = [-filt(Ysm, dict(TRUE, q_J=TRUE["q_J"] * np.exp(dd)))["ll"].sum() for dd in np.linspace(-0.02, 0.02, 21)]
smooth = float(np.abs(np.diff(vals, 2)).max())
VERD["LIKELIHOOD_SMOOTH"] = bool(smooth < CRIT["likelihood_smooth_max"])
print(f"Likelihood smoothness (max |2nd diff|, event-rich slice): {smooth:.5f} -> {'PASS' if VERD['LIKELIHOOD_SMOOTH'] else 'FAIL'}")

# ---- predictive mixture intervals vs Monte Carlo ----
rg = np.random.default_rng(3); g = filt(base_traj(240, 99)[:151], TRUE)
m, v, w, cm, cb = C.forecast_moments(g["LW"], g["Z"], g["PP"], np.array([150]), 60, TRUE, SYN_GAMMA)
ivs, trunc = C.mixture_intervals(w, cm, cb, 60, TRUE)
n = 1_000_000; comp = rg.choice(4, n, p=w[0]); hh = C.Hrow(210, SYN_GAMMA)
x = np.array([rg.multivariate_normal(g["Z"][0, k], g["PP"][0, k] + 1e-12 * I3, n) for k in range(4)])[comp, np.arange(n)] @ hh
kk = rg.binomial(60, TRUE["pi_u"], n); x += rg.normal(0, np.sqrt((60 - kk) * TRUE["q"] + kk * TRUE["q_J"]))
x += np.where(rg.random(n) < TRUE["pi_e"], rg.normal(0, np.sqrt(TRUE["r_O"]), n), rg.normal(0, np.sqrt(TRUE["r"]), n))
cov = {lv: float(np.mean((x >= lo[0]) & (x <= hi[0]))) for lv, (lo, hi) in ivs.items()}
VERD["INTERVALS_match_monte_carlo"] = bool(all(abs(cov[lv] - lv) <= CRIT["interval_mc_tol"] for lv in cov))
RES["interval_mc"] = dict(coverage=cov, truncated_binomial_mass=trunc)
print(f"Mixture intervals vs 1e6-sample Monte Carlo coverage {cov} -> {'PASS' if VERD['INTERVALS_match_monte_carlo'] else 'FAIL'}")

# ---- A smooth ----
mx, diffs = [], []
for s in range(20):
    yy = base_traj(240, 3000 + s); b = filt(yy, TRUE, store=True); gg = filt(yy, gauss(TRUE))
    mx.append(max(np.nanmax(b["prob"]["jump"]), np.nanmax(b["prob"]["outlier"])))
    diffs.append(abs(fmean(b, 0, 239, 30, TRUE)[0] - fmean(gg, 0, 239, 30, TRUE)[0]))
VERD["A_smooth"] = bool(max(mx) < CRIT["smooth_max_event_prob"] and np.median(diffs) < CRIT["smooth_vs_gauss_median_diff"])
RES["A_smooth"] = dict(max_event_prob=float(max(mx)), median_abs_diff_vs_gaussian=float(np.median(diffs)))
print(f"A smooth: max P(event) {max(mx):.3f}; median |robust-Gaussian| {np.median(diffs):.1e} -> {'PASS' if VERD['A_smooth'] else 'FAIL'}")

# ---- regressions ----
EV = 100
cases = {"R1_persistent_+0.2": (lambda t, y: 0.2 * (t >= EV), 0.2, CRIT["shift02_tol"]),
         "B_persistent_+1.5": (lambda t, y: 1.5 * (t >= EV), 1.5, CRIT["shift15_tol"]),
         "R2_transient_+0.2_3min": (lambda t, y: 0.2 * ((t >= EV) & (t < EV + 3)), 0.0, CRIT["transient02_tol"]),
         "C_transient_+2.0_3min": (lambda t, y: 2.0 * ((t >= EV) & (t < EV + 3)), 0.0, CRIT["transient20_tol"]),
         "E_outlier_+5_1min": (lambda t, y: 5.0 * (t == EV), 0.0, CRIT["outlier_tol"])}
for name, (f_, ideal, tol) in cases.items():
    R = response(f_, [EV - 1, EV, EV + 1, EV + 5, EV + 15, EV + 30, EV + 60]); R.to_csv(f"{OUT}/{name}.csv", index=False)
    rob = R[(R.model == "robust") & (R.origin >= EV + 15)]
    VERD[name] = bool(all((rob[f"dforecast_h{h}"] - ideal).abs().le(tol).all() for h in HORIZONS))
    last = R[(R.model == "robust")].iloc[-1]; lastg = R[(R.model == "gaussian_rw")].iloc[-3]
    print(f"{name}: robust +60 change at o>=event+15 {rob.dforecast_h60.round(3).tolist()} (ideal {ideal}); "
          f"Gaussian RW at event+15 {lastg.dforecast_h60:+.3f}; max P(jump) {last.max_P_jump:.2f}, "
          f"max P(outlier) {last.max_P_outlier:.2f} -> {'PASS' if VERD[name] else 'FAIL'}")
fD = lambda t, y: 1.0 * (t >= 60) - 1.5 * (t >= 120) + 0.8 * (t >= 180)
RD = response(fD, [75, 135, 195, 230]); RD = RD[RD.model == "robust"].copy(); RD["ideal"] = [1.0, -0.5, 0.3, 0.3]
VERD["D_multiple_jumps"] = bool(all((RD[f"dforecast_h{h}"] - RD.ideal).abs().le(CRIT["multijump_tol"]).all() for h in HORIZONS))
RD.to_csv(f"{OUT}/D_multiple_jumps.csv", index=False)
print(f"D multiple jumps: {RD.dforecast_h30.round(3).tolist()} vs ideal {RD.ideal.tolist()} -> {'PASS' if VERD['D_multiple_jumps'] else 'FAIL'}")


def fF(t, y):
    out = np.zeros_like(y); m = t >= 200
    out[m] = (26.0 + (y[200] - 26.0) * np.exp(-(t[m] - 200) / 3.0)) - y[m]
    return out


RF = response(fF, [199, 201, 205, 215, 229], T=230); RF.to_csv(f"{OUT}/F_terminal_online.csv", index=False)
rf = RF[RF.model == "robust"]
VERD["F_terminal_online_trend_contamination_below_0p10_per_h"] = bool(rf.dbeta_C_per_h.abs().max() <= CRIT["terminal_dbeta_max"])
RES["F_terminal_online_LEVEL_absorption_C"] = rf.dlevel_u_C.round(3).tolist()
print(f"F terminal (online): max |dbeta| {rf.dbeta_C_per_h.abs().max():.3f} C/h -> "
      f"{'PASS' if VERD['F_terminal_online_trend_contamination_below_0p10_per_h'] else 'FAIL'} (trend criterion only). "
      f"REPORTED, NOT PASSED: latent level change by origin {dict(zip(rf.origin.tolist(), rf.dlevel_u_C.round(2).tolist()))} C "
      f"— the online level absorbs the terminal drop; the filter cannot distinguish probe-out from physiology.")

# ---- G gaps, H leakage ----
yy = base_traj(240, 4242); rows = []
for gap in (0, 5, 15, 30):
    ya = yy.copy()
    if gap:
        ya[121 - gap:121] = np.nan
    b = filt(ya[:121], TRUE)
    rows.append(dict(gap=gap, n_updates=int(b["nupd"][0]) + 1, n_observed=int(np.sum(~np.isnan(ya[:121]))),
                     **{f"var_h{h}": fmean(b, 0, 120, h, TRUE)[1] for h in HORIZONS}))
G = pd.DataFrame(rows); G.to_csv(f"{OUT}/G_gaps.csv", index=False)
VERD["G_gaps"] = bool((G.n_updates == G.n_observed).all() and all((np.diff(G[f"var_h{h}"]) > 0).all() for h in HORIZONS))
print(f"G gaps: var+60 {G.var_h60.round(4).tolist()} -> {'PASS' if VERD['G_gaps'] else 'FAIL'}")
yy = base_traj(240, 555); yy[150] += 4.0; mx = 0.0
for poison in (np.nan, -100.0, 1e6):
    yp = yy.copy(); yp[121:] = poison
    a, b = filt(yy[:121], TRUE), filt(yp[:121], TRUE)
    for h in HORIZONS:
        mx = max(mx, *np.abs(np.array(fmean(a, 0, 120, h, TRUE)) - np.array(fmean(b, 0, 120, h, TRUE))))
VERD["H_no_future_leakage"] = bool(mx < CRIT["leak_tol"])
print(f"H leakage: {mx:.1e} -> {'PASS' if VERD['H_no_future_leakage'] else 'FAIL'}")

# ---- offline fixed-lag attribution (criteria fixed before running) ----
att = {k: [] for k in ("persistent_+1.5", "outlier_+5", "transient_+2_3min", "no_event")}
for s_ in range(20):
    y0 = base_traj(160, 6000 + s_); tt = np.arange(160)
    for k, yy in {"persistent_+1.5": y0 + 1.5 * (tt >= 100), "outlier_+5": y0 + 5.0 * (tt == 100),
                  "transient_+2_3min": y0 + 2.0 * ((tt >= 100) & (tt < 103)), "no_event": y0}.items():
        post, gap = C.fixed_lag_mode_posterior(yy[None], [100], 10, TRUE, SYN_M0[None], SYN_S, SYN_GAMMA)
        att[k].append((post[0, 2] + post[0, 3], post[0, 1] + post[0, 3], gap[0]))
att = {k: np.array(v) for k, v in att.items()}
VERD["ATTRIBUTION_fixed_lag_persistent_jump_outlier_noevent"] = bool(
    np.median(att["persistent_+1.5"][:, 0]) > 0.5 and np.median(att["outlier_+5"][:, 1]) > 0.5
    and np.median(att["no_event"][:, 0]) < 0.5 and np.median(att["no_event"][:, 1]) < 0.5)
RES["attribution_fixed_lag"] = {k: dict(median_P_jump=float(np.median(v[:, 0])), median_P_outlier=float(np.median(v[:, 1])),
                                        max_consistency_gap=float(v[:, 2].max())) for k, v in att.items()}
print("Fixed-lag attribution (lag 10 min): " + "; ".join(f"{k} P(jump) {d['median_P_jump']:.2f} P(outlier) {d['median_P_outlier']:.2f}"
                                                        for k, d in RES["attribution_fixed_lag"].items())
      + f" -> {'PASS' if VERD['ATTRIBUTION_fixed_lag_persistent_jump_outlier_noevent'] else 'FAIL'}"
      + " (transient: reported only — inherently ambiguous)")

# ---- recovery (from recovery_resume.py) ----
CK = "recovery_checkpoint_v2.json"
rec = json.load(open(CK)) if os.path.exists(CK) else {}
if rec.get(f"W_T={W_T}", {}).get("done") and rec.get("W_T=0", {}).get("done"):
    e = rec[f"W_T={W_T}"]["estimates"]
    VERD["RECOVERY_WT30_mixture_params_gamma_m0_S_fixed"] = bool(
        rec[f"W_T={W_T}"]["success"] and all(abs(e[k] / TRUE[k] - 1) <= CRIT["recover_qr_rel"] for k in ("q", "r"))
        and all(CRIT["recover_rare_ratio"][0] <= e[k] / TRUE[k] <= CRIT["recover_rare_ratio"][1] for k in ("pi_u", "q_J", "pi_e", "r_O")))
    for kk in (f"W_T={W_T}", "W_T=0"):
        print(f"Recovery {kk}: " + ", ".join(f"{k} x{v / TRUE[k]:.2f}" for k, v in rec[kk]["estimates"].items()))
    print(f"  -> {'PASS' if VERD['RECOVERY_WT30_mixture_params_gamma_m0_S_fixed'] else 'FAIL'} (gamma, m0, S fixed at truth)")
else:
    VERD["RECOVERY_WT30_mixture_params_gamma_m0_S_fixed"] = False
    print("Recovery: NOT AVAILABLE — run recovery_resume.py until it prints ALL DONE, then rerun this script.")
RES["recovery"] = rec

ident = []
for wdw in (20, 40, 60, 120, 240):
    Pm = C.phi(np.arange(wdw + 1), SYN_GAMMA); b = filt(base_traj(241, 707)[:wdw + 1], TRUE); Pp = b["P"][0]
    ident.append(dict(window=f"0-{wdw}", basis_corr=float(np.corrcoef(Pm[:, 0], Pm[:, 1])[0, 1]),
                      posterior_corr_alpha_beta=float(Pp[0, 1] / np.sqrt(Pp[0, 0] * Pp[1, 1]))))
pd.DataFrame(ident).to_csv(f"{OUT}/identifiability.csv", index=False)

math_keys = ["L_exact_gaussian_limits", "APPROX_gpb2_vs_exact_enumeration", "APPROX_gpb2_vs_RBPF", "LIKELIHOOD_SMOOTH",
             "INTERVALS_match_monte_carlo", "H_no_future_leakage", "G_gaps"]
MATH = all(VERD[k] for k in math_keys)
SYN = all(v for k, v in VERD.items() if k not in math_keys)
VERD = {k: bool(v) for k, v in VERD.items()}
json.dump(dict(truth=dict(gamma=SYN_GAMMA, m0=SYN_M0.tolist(), S=SYN_S.tolist(), **TRUE), W_T=W_T, criteria=CRIT,
               verdicts=VERD, results=RES, COMBINED_MODEL_MATH="PASS" if MATH else "FAIL",
               SYNTHETIC_VERIFICATION="PASS" if SYN else "FAIL"),
          open(f"{OUT}/verification_results.json", "w"), indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o))
report = f"""# Synthetic verification report (corrected; shared core)

No real data, no VitalDB, no holdout. Truth and criteria fixed before the tests.

Inference accounting (see thermal_robust_core.py):
- EXACT: each conditional Kalman update; candidate weights given the retained mixture; diffuse initialisation.
- APPROXIMATE: merging histories that share the newest (jump, outlier) mode (GPB2 for an iid-switching system);
  missing-minute moment approximation; likelihood from the approximate retained mixture.
- Forecast mean/variance are exact functionals of the retained mixture (not of the exact posterior);
  predictive intervals are exact quantiles of that mixture convolved with the future jump/outlier mixture.

Terminal: the online latent level absorbs a probe-out-like drop (level change by origin
{RES['F_terminal_online_LEVEL_absorption_C']} C). The F test passes ONLY its trend-contamination criterion.

Verdicts:
""" + "\n".join(f"- {'PASS' if v else 'FAIL'}: {k}" for k, v in VERD.items()) + f"""

COMBINED_MODEL_MATH: {'PASS' if MATH else 'FAIL'}
SYNTHETIC_VERIFICATION: {'PASS' if SYN else 'FAIL'}
"""
open(f"{OUT}/synthetic_verification_report.md", "w").write(report)
print(f"\n(runtime {time.time() - t0:.0f} s)")
for k, v in VERD.items():
    print(f"  [{'PASS' if v else 'FAIL'}] {k}")
print(f"\nCOMBINED_MODEL_MATH: {'PASS' if MATH else 'FAIL'}")
print(f"SYNTHETIC_VERIFICATION: {'PASS' if SYN else 'FAIL'}")
