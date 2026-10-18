"""
recovery_resume.py   (corrected replacement; uses thermal_robust_core)

Synthetic maximum-likelihood recovery of the six mixture/noise parameters (q, r, pi_u, q_J, pi_e, r_O)
with gamma, m0 and S FIXED at synthetic truth (this is NOT full-model recovery; the real-data script
estimates gamma, m0(x) and S). Uses the same constrained parameterisation as the real-data estimator
(q_J > q, r_O > r). Compares W_T = 30 (terminal minutes excluded from learning) with W_T = 0.

Resumable: writes recovery_checkpoint_v2.json after every iteration and stops itself after
BUDGET_S seconds; rerun until it prints ALL DONE. No real data, no network, no holdout.
"""

import json
import os
import sys
import time

import numpy as np
from scipy import optimize

import thermal_robust_core as C

SYN_GAMMA = 0.031
SYN_M0 = np.array([0.40, 0.10])
SYN_S = np.array([[0.25, 0.03], [0.03, 0.09]])
TRUE = dict(q=0.15 ** 2 / 60, r=0.03 ** 2, pi_u=0.002, q_J=1.5 ** 2, pi_e=0.005, r_O=2.0 ** 2)
CK = "recovery_checkpoint_v2.json"
BUDGET_S = float(os.environ.get("RECOVERY_BUDGET_S", "1e9"))


def simulate_cohort(n, seed, terminal_frac=0.5):
    rg = np.random.default_rng(seed)
    Ls = rg.integers(150, 251, n)
    Y = np.full((n, Ls.max()), np.nan)
    for i, L in enumerate(Ls):
        th = rg.multivariate_normal(SYN_M0, SYN_S)
        j = rg.random(L) < TRUE["pi_u"]
        eta = np.where(j, rg.normal(0, np.sqrt(TRUE["q_J"]), L), rg.normal(0, np.sqrt(TRUE["q"]), L)); eta[0] = 0
        o = rg.random(L) < TRUE["pi_e"]
        e = np.where(o, rg.normal(0, np.sqrt(TRUE["r_O"]), L), rg.normal(0, np.sqrt(TRUE["r"]), L))
        t = np.arange(L)
        y = C.phi(t, SYN_GAMMA) @ th + 36.5 + rg.normal(0, .4) + np.cumsum(eta) + e
        if rg.random() < terminal_frac:
            s0 = L - 10
            y[s0:] = 26.0 + (y[s0 - 1] - 26.0) * np.exp(-(t[s0:] - s0 + 1) / 3.0)
        Y[i, :L] = y
    return Y


def truncate_end(Y, w):
    Y = Y.copy()
    if w > 0:
        for i in range(len(Y)):
            last = np.where(~np.isnan(Y[i]))[0].max()
            Y[i, last - w + 1:] = np.nan
    return Y


class Budget(Exception):
    pass


st = json.load(open(CK)) if os.path.exists(CK) else {}
Yc = simulate_cohort(300, 777)
T0 = time.time()
x_true = C.pack(dict(gamma=SYN_GAMMA, **TRUE))
for w in (30, 0):
    key = f"W_T={w}"
    if st.get(key, {}).get("done"):
        continue
    Y = truncate_end(Yc, w)
    M0 = np.tile(SYN_M0, (len(Y), 1))

    def f(x6):
        p = C.unpack(np.concatenate([[x_true[0]], x6]))
        return -C.gpb2_filter(Y, p, M0, SYN_S, SYN_GAMMA)["ll"].sum()

    x0 = st[key]["x"] if key in st else C.pack(dict(gamma=SYN_GAMMA, q=1e-3, r=3e-3, pi_u=0.01, q_J=1.0, pi_e=0.01, r_O=1.0))[1:].tolist()

    def cb(xk):
        st[key] = dict(x=list(map(float, xk)), iters=st.get(key, {}).get("iters", 0) + 1, done=False)
        json.dump(st, open(CK, "w"))
        if time.time() - T0 > BUDGET_S:
            raise Budget()

    try:
        res = optimize.minimize(f, np.array(x0), method="L-BFGS-B", bounds=C.X_BOUNDS[1:], callback=cb, options=dict(maxiter=500))
        est = C.unpack(np.concatenate([[x_true[0]], res.x]))
        est.pop("gamma")
        st[key] = dict(x=res.x.tolist(), iters=st.get(key, {}).get("iters", 0), done=True, success=bool(res.success),
                       message=str(res.message), nll=float(res.fun), estimates=est)
        json.dump(st, open(CK, "w"), indent=2)
        print(f"{key}: FINISHED success={res.success} ({res.message}); " +
              ", ".join(f"{k} {v:.3g} (x{v / TRUE[k]:.2f})" for k, v in est.items()))
    except Budget:
        print(f"{key}: paused at iteration {st[key]['iters']} (time budget); rerun to continue")
        sys.exit(0)
print("ALL DONE")
