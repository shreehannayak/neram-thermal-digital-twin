"""
dev_robust_02_fit_and_validate.py

DEVELOPMENT-ONLY real-data fitting and validation of the combined robust thermal state-space model.
Uses the 4,456 development cases only (dev-train / dev-val, seed 20261201, 75/25). The 1,100-case final
holdout is read ONLY as an ID list for exclusion and protection; no holdout temperature, target or
metadata is ever loaded. NO network access (metadata comes from dev_robust_01_fetch_case_metadata.py).

MODEL (thermal_robust_core.py): calm/jump level mixture + contaminated-normal observation, alpha/beta
trajectory state with prior N(m0(x), S), exact diffuse level, GPB2 inference for an iid-switching system.

ESTIMATION (dev-train only; final W_T = 30 observed minutes of every recording excluded from LEARNING ONLY)
  psi = (gamma, q, r, pi_u, q_J, pi_e, r_O): approximate maximum likelihood (GPB2 likelihood), constrained
        q_J > q, r_O > r, pi <= 0.5. Three generic starts on a deterministic 25% subsample; best start refined
        on full dev-train.
  m0(x) = B'x and S: empirical-Bayes EM on per-case theta information obtained by running the filter with
        a vague prior N(0, 100 I) (Gaussian approximation of each case's theta likelihood).
  Alternation: [psi | B0,S0] -> EB -> [psi | B1,S1] -> EB -> final (two rounds; changes reported).
  Online filtering never uses recording length: W_T is applied only to the training data passed to the
  likelihood/EB; evaluation runs the filter on complete dev-val records exactly as it would run live.
SENSITIVITY: W_T = 0 refit (single start from the W_T = 30 solution, B and S held at their final values).

EVALUATION (dev-val): Code 4 origin/target rules; robust model vs persistence, linear (60 min),
population trajectory, generic ML, prior-only (theta fixed at m0(x)), Gaussian random-walk state-space
(from the development adequacy fit, if available and consistent). Strata: all, non-terminal,
terminal-target (target within 30 min of recording end: EVALUATION-ONLY label), excluding forecasts that
cross a > 5-min raw gap, excluding origins with a >= 3 C discontinuity in history, history stage.

Resumable: every optimisation checkpoints after each iteration in dev_robust_outputs/state.json.
Optional DEV_ROBUST_BUDGET_S stops the script cleanly before a time budget (rerun to continue).
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import optimize  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402

import thermal_robust_core as C  # noqa: E402

# ============================================================================
# CONFIGURATION (fixed before the real-data run)
# ============================================================================
CODE4_DIR, FREEZE_DIR, CACHE_DIR = "code4_outputs", "final_holdout_freeze", "vitaldb_bt_cache"
ADQ_DIR, META = "development_adequacy", os.path.join("dev_robust_inputs", "dev_case_metadata.csv")
META_REC = os.path.join("dev_robust_inputs", "dev_case_metadata.sha256.json")
VERIF_JSON = os.path.join("robust_model_verification", "verification_results.json")
OUT = "dev_robust_outputs"
FIG = os.path.join(OUT, "figures")
STATE = os.path.join(OUT, "state.json")
os.makedirs(FIG, exist_ok=True)

DEV_SEED, DEV_TRAIN_FRAC = 20261201, 0.75
W_T = 30
PLAUS_LO, PLAUS_HI, EQUIL_MIN, BIN_S = 25.0, 43.0, 15, 60
MIN_HISTORY, ORIGIN_STEP, RECENT_WIN, RECENT_MIN_OBS, TARGET_TOL = 20, 5, 15, 10, 1
HORIZONS, LEVELS = [20, 30, 60], (0.5, 0.8, 0.95)
LONG_GAP_S, SEVERE_JUMP_C, TERMINAL_EVAL_MIN = 300, 3.0, 30
STAGES = [(20, 60), (60, 120), (120, 240), (240, 10 ** 6)]
STATIC_SPEC = {"age": "numeric", "sex": "categorical", "height": "numeric", "weight": "numeric", "bmi": "numeric",
               "asa": "numeric", "emop": "numeric", "department": "categorical", "optype": "categorical",
               "ane_type": "categorical"}
STATIC_MIN_COV, MAX_CAT_LEVELS, RIDGE = 0.80, 20, 1.0
SUBSAMPLE_FRAC, SUBSAMPLE_SEED = 0.25, 20261202
STARTS = [dict(gamma=0.03, q=1e-4, r=1e-3, pi_u=0.005, q_J=0.1, pi_e=0.005, r_O=1.0),
          dict(gamma=0.01, q=1e-5, r=5e-4, pi_u=0.02, q_J=0.1, pi_e=0.02, r_O=0.05),
          dict(gamma=0.10, q=1e-3, r=3e-3, pi_u=0.001, q_J=0.1, pi_e=0.001, r_O=30.0)]
B_INIT_S = np.diag([0.5 ** 2, 0.5 ** 2])          # initial prior covariance for round 1 (data-independent)
V_VAGUE = 100.0                                    # vague prior variance used to extract per-case theta information
S_TINY = 1e-10                                     # prior-only comparator: theta frozen at m0(x)
LINEAR_WINDOW = 60
ML_PARAMS = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=50, l2_regularization=1.0,
                 random_state=0)
N_BOOT = 2000
MAXITER = 300
BUDGET_S = float(os.environ.get("DEV_ROBUST_BUDGET_S", "1e12"))
T_START = time.time()


class Budget(Exception):
    pass


def stop(msg):
    print(f"\nSTOP (fail-closed): {msg}")
    sys.exit(1)


def sha_file(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def hash_tree(d):
    return {os.path.join(r, f): sha_file(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in sorted(fs)}


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save_state(st):
    json.dump(st, open(STATE + ".tmp", "w"), default=lambda o: o.item() if hasattr(o, "item") else str(o))
    os.replace(STATE + ".tmp", STATE)


# ============================================================================
# 0. PREFLIGHT (fail-closed)
# ============================================================================
print("=" * 80)
print("DEVELOPMENT-ONLY REAL-DATA FIT AND VALIDATION — robust thermal state-space model")
print("=" * 80)
for d in (CODE4_DIR, FREEZE_DIR, CACHE_DIR, ADQ_DIR):
    if not os.path.isdir(d):
        stop(f"required folder {d}/ missing")
HASH_BEFORE = {**hash_tree(CODE4_DIR), **hash_tree(FREEZE_DIR)}
final_ids = set(pd.read_csv(os.path.join(FREEZE_DIR, "final_holdout_case_ids.csv"))["caseid"].astype(int))
dev_tbl = pd.read_csv(os.path.join(FREEZE_DIR, "development_case_ids.csv"))
dev_ids = np.array(sorted(dev_tbl["caseid"].astype(int)))
fman = json.load(open(os.path.join(FREEZE_DIR, "freeze_manifest.json")))
PROT = {
    "final_holdout_hash_matches_manifest":
        hashlib.sha256(",".join(map(str, sorted(final_ids))).encode()).hexdigest() == fman["final_holdout_ids_sha256"],
    "development_disjoint_from_holdout": not (set(dev_ids) & final_ids),
    "counts_match_freeze_manifest": len(final_ids) == fman["final_holdout_n"] and len(dev_ids) == fman["development_n"],
}
if not all(PROT.values()):
    stop(f"protection failed: {PROT}")

perm = dev_ids[np.random.RandomState(DEV_SEED).permutation(len(dev_ids))]
n_tr = int(round(DEV_TRAIN_FRAC * len(perm)))
DTRAIN, DVAL = sorted(int(c) for c in perm[:n_tr]), sorted(int(c) for c in perm[n_tr:])
adq_split = os.path.join(ADQ_DIR, "dev_split.csv")
if os.path.exists(adq_split):
    s_ = pd.read_csv(adq_split)
    if sorted(s_[s_.dev_split == "dev_train"].caseid) != DTRAIN or sorted(s_[s_.dev_split == "dev_val"].caseid) != DVAL:
        stop("re-derived development split differs from development_adequacy/dev_split.csv")
    PROT["dev_split_matches_adequacy_study"] = True
else:
    PROT["dev_split_matches_adequacy_study"] = "adequacy split file absent; split re-derived deterministically"
pd.DataFrame({"caseid": DTRAIN + DVAL, "dev_split": ["dev_train"] * len(DTRAIN) + ["dev_val"] * len(DVAL)}) \
    .to_csv(os.path.join(OUT, "dev_split_used.csv"), index=False)

if not os.path.exists(META):
    stop(f"{META} missing — run dev_robust_01_fetch_case_metadata.py first")
if not os.path.exists(META_REC) or json.load(open(META_REC))["sha256"] != sha_file(META):
    stop("metadata SHA-256 record missing or mismatched")
meta = pd.read_csv(META)
if set(meta.caseid.astype(int)) & final_ids:
    stop("metadata file contains final-holdout rows")
if not set(dev_ids) <= set(meta.caseid.astype(int)):
    stop("metadata file does not cover every development case")
meta = meta.set_index("caseid")

man = pd.read_csv(os.path.join(CODE4_DIR, "code4_cohort_manifest.csv"))
man = man[man.caseid.isin(dev_ids)].set_index("caseid")            # holdout rows dropped immediately
if len(man) != len(dev_ids):
    stop("Code 4 manifest does not contain every development case")
if "settled_minutes" not in man.columns or (man["status"] != "forecast_eligible").any():
    stop("Code 4 manifest lacks settled_minutes or contains non-eligible development cases")
missing_cache = [c for c in dev_ids if not os.path.exists(os.path.join(CACHE_DIR, f"{man.loc[c, 'canonical_tid']}.csv.gz"))]
if missing_cache:
    stop(f"{len(missing_cache)} development cases missing from {CACHE_DIR}/ (e.g. {missing_cache[:5]}); not downloading")
ev_path = os.path.join(ADQ_DIR, "candidate_jump_events.csv")
if not os.path.exists(ev_path):
    stop(f"{ev_path} missing (needed for posterior attribution)")
print(f"Preflight PASS: development {len(dev_ids)} (dev-train {len(DTRAIN)}, dev-val {len(DVAL)}); "
      f"holdout {len(final_ids)} (IDs only); overlap 0; metadata local; cache complete")

# ============================================================================
# 1. LOAD DEVELOPMENT SERIES (cache only)
# ============================================================================
LOADED = set()


def load_case(cid):
    if cid in final_ids or cid not in set(dev_ids):
        stop(f"attempted to load non-development case {cid}")
    LOADED.add(cid)
    df = pd.read_csv(os.path.join(CACHE_DIR, f"{man.loc[cid, 'canonical_tid']}.csv.gz")).iloc[:, :2]
    df.columns = ["t", "v"]
    df = df.apply(pd.to_numeric, errors="coerce").dropna().sort_values("t").drop_duplicates("t")
    df = df[(df.v >= PLAUS_LO) & (df.v <= PLAUS_HI)]
    t = df.t.to_numpy(float)
    med = df.v.groupby((df.t // BIN_S).astype(int)).median()
    s0 = int(np.ceil((t[0] + EQUIL_MIN * 60) / BIN_S))
    keep = med[med.index >= s0]
    y = np.full(int(med.index.max()) - s0 + 1, np.nan)
    y[keep.index.to_numpy() - s0] = keep.to_numpy()
    if len(y) != int(man.loc[cid, "settled_minutes"]):
        stop(f"case {cid}: recomputed settled length {len(y)} != manifest {int(man.loc[cid, 'settled_minutes'])}")
    dt = np.diff(t)
    gi = np.where(dt > LONG_GAP_S)[0]
    return y, s0, np.column_stack([t[gi], t[gi + 1]]) if len(gi) else np.zeros((0, 2))


t0 = time.time()
SER = {}
for k, c in enumerate(DTRAIN + DVAL, 1):
    SER[c] = load_case(c)
    if k % 1000 == 0:
        print(f"  loaded {k}/{len(dev_ids)}")
print(f"Loaded {len(SER)} development series in {time.time() - t0:.0f} s")


def matrix(ids, truncate=0):
    L = max(len(SER[c][0]) for c in ids)
    Y = np.full((len(ids), L), np.nan)
    for i, c in enumerate(ids):
        y = SER[c][0].copy()
        if truncate > 0:
            last = np.where(~np.isnan(y))[0].max()
            y[max(0, last - truncate + 1):] = np.nan
        Y[i, :len(y)] = y
    return Y


# ---- static covariates (Code 4 framework; coverage and scaling from dev-train only) ----
trm = meta.reindex(DTRAIN)
sel_num, sel_cat, cov_rows = [], [], []
for f, typ in STATIC_SPEC.items():
    if f not in meta.columns:
        cov_rows.append(dict(field=f, present=False, coverage=0.0, selected=False))
        continue
    cov = float((pd.to_numeric(trm[f], errors="coerce") if typ == "numeric" else trm[f]).notna().mean())
    cov_rows.append(dict(field=f, present=True, type=typ, coverage=cov, selected=cov >= STATIC_MIN_COV))
    if cov >= STATIC_MIN_COV:
        (sel_num if typ == "numeric" else sel_cat).append(f)
num_med = {f: float(pd.to_numeric(trm[f], errors="coerce").median()) for f in sel_num}
num_mu = {f: float(pd.to_numeric(trm[f], errors="coerce").fillna(num_med[f]).mean()) for f in sel_num}
num_sd = {f: float(pd.to_numeric(trm[f], errors="coerce").fillna(num_med[f]).std() or 1.0) for f in sel_num}
cat_lv = {f: trm[f].astype(str).value_counts().index[:MAX_CAT_LEVELS].tolist()[1:] for f in sel_cat}
XCOLS = ["intercept"] + sel_num + [f"{f}={lv}" for f in sel_cat for lv in cat_lv[f]]


def xvec(c):
    r = meta.loc[c]
    v = [1.0]
    for f in sel_num:
        x = pd.to_numeric(r.get(f, np.nan), errors="coerce")
        v.append(((num_med[f] if pd.isna(x) else float(x)) - num_mu[f]) / num_sd[f])
    for f in sel_cat:
        v.extend(1.0 if str(r.get(f, "nan")) == lv else 0.0 for lv in cat_lv[f])
    return np.array(v)


X_TR = np.array([xvec(c) for c in DTRAIN])
X_VA = np.array([xvec(c) for c in DVAL])
pd.DataFrame(cov_rows).to_csv(os.path.join(OUT, "static_covariates.csv"), index=False)
print(f"Static covariates (dev-train coverage >= 80%): {sel_num + sel_cat} -> {len(XCOLS)} design columns")

Y_TR30 = matrix(DTRAIN, truncate=W_T)
Y_TR0 = matrix(DTRAIN)
sub_idx = np.sort(np.random.RandomState(SUBSAMPLE_SEED).choice(len(DTRAIN), max(50, int(SUBSAMPLE_FRAC * len(DTRAIN))), replace=False))
removed = int(np.sum(~np.isnan(Y_TR0)) - np.sum(~np.isnan(Y_TR30)))
print(f"W_T={W_T}: {removed} dev-train observed minutes excluded from LEARNING ONLY "
      f"({removed / np.sum(~np.isnan(Y_TR0)):.1%})")


# ============================================================================
# 2. ESTIMATION
# ============================================================================
def nll(x, Y, M0, S):
    p = C.unpack(x)
    return -C.gpb2_filter(Y, p, M0, S, p["gamma"])["ll"].sum()


def run_opt(st, key, x0, Y, M0, S):
    """L-BFGS-B with a checkpoint after every iteration; resumes from the last checkpoint."""
    rec = st.get(key, {})
    if rec.get("done"):
        return np.array(rec["x"])
    x0 = np.array(rec.get("x", x0), float)
    t_ = time.time()
    f0 = nll(x0, Y, M0, S)
    print(f"  [{key}] start nll {f0:.1f} (one evaluation {time.time() - t_:.1f} s; iter {rec.get('iters', 0)})")

    def cb(xk):
        rec.update(x=list(map(float, xk)), iters=rec.get("iters", 0) + 1, done=False)
        st[key] = rec
        save_state(st)
        if time.time() - T_START > BUDGET_S:
            raise Budget()

    res = optimize.minimize(nll, x0, args=(Y, M0, S), method="L-BFGS-B", bounds=C.X_BOUNDS, callback=cb,
                            options=dict(maxiter=MAXITER))
    rec.update(x=list(map(float, res.x)), done=True, success=bool(res.success), message=str(res.message),
               nll=float(res.fun), iters=rec.get("iters", 0), near_bounds=C.near_bounds(res.x), params=C.unpack(res.x))
    st[key] = rec
    save_state(st)
    print(f"  [{key}] done: nll {res.fun:.1f}, success {res.success} ({res.message}), iters {rec['iters']}, "
          f"near bounds {rec['near_bounds']}")
    return res.x


def eb_step(x, Y, X):
    """Empirical-Bayes EM for (B, S) from per-case theta information (vague-prior filter)."""
    p = C.unpack(x)
    V = V_VAGUE * np.eye(2)
    out = C.gpb2_filter(Y, p, np.zeros((len(Y), 2)), V, p["gamma"])
    m, Cv = out["z"][:, :2], out["P"][:, :2, :2]
    Ci = np.linalg.inv(Cv)
    Lam = Ci - np.linalg.inv(V)
    ev_, evec = np.linalg.eigh(0.5 * (Lam + Lam.transpose(0, 2, 1)))
    Lam = np.einsum("nij,nj,nkj->nik", evec, np.clip(ev_, 0, None), evec)
    eta = np.einsum("nij,nj->ni", Ci, m)
    k = X.shape[1]
    pen = RIDGE * np.eye(k)
    pen[0, 0] = 0.0
    B = np.linalg.lstsq(X, m, rcond=None)[0]
    S = np.diag([0.25, 0.25])
    for it in range(1000):
        Si = np.linalg.inv(S)
        A = Lam + Si[None]
        Ainv = np.linalg.inv(A)
        mu = np.einsum("nij,nj->ni", Ainv, eta + (X @ B) @ Si.T)
        Bn = np.linalg.solve(X.T @ X + pen, X.T @ mu)
        R = mu - X @ Bn
        Sn = (R.T @ R + Ainv.sum(0)) / len(X) + 1e-8 * np.eye(2)
        delta = max(np.abs(Bn - B).max(), np.abs(Sn - S).max())
        B, S = Bn, Sn
        if delta < 1e-9:
            break
    info = np.trace(Lam, axis1=1, axis2=2)
    return B, S, dict(em_iterations=it + 1, converged=bool(delta < 1e-9), final_delta=float(delta),
                      cases_with_negligible_theta_information=int(np.sum(info < 1e-6)))


st = load_state()
try:
    # ---- round 1: multi-start on subsample, prior mean 0 and S = B_INIT_S (data-independent) ----
    print("\nEstimation round 1: three starts on a deterministic 25% dev-train subsample")
    Ysub = Y_TR30[sub_idx]
    M0_0 = np.zeros((len(Ysub), 2))
    xs = []
    for i, s0 in enumerate(STARTS):
        xs.append(run_opt(st, f"r1_start{i}", C.pack(s0), Ysub, M0_0, B_INIT_S))
    best = int(np.argmin([st[f"r1_start{i}"]["nll"] for i in range(len(STARTS))]))
    print(f"  best start {best}; refining on full dev-train")
    x1 = run_opt(st, "r1_full", xs[best], Y_TR30, np.zeros((len(Y_TR30), 2)), B_INIT_S)
    if "eb1" not in st:
        B1, S1, eb1 = eb_step(x1, Y_TR30, X_TR)
        st["eb1"] = dict(B=B1.tolist(), S=S1.tolist(), **eb1)
        save_state(st)
    B1, S1 = np.array(st["eb1"]["B"]), np.array(st["eb1"]["S"])
    print(f"  EB round 1: S {np.round(S1, 4).tolist()}, EM converged {st['eb1']['converged']}")
    # ---- round 2 ----
    print("\nEstimation round 2: psi refit on full dev-train with EB prior")
    x2 = run_opt(st, "r2_full", x1, Y_TR30, X_TR @ B1, S1)
    if "eb2" not in st:
        B2, S2, eb2 = eb_step(x2, Y_TR30, X_TR)
        st["eb2"] = dict(B=B2.tolist(), S=S2.tolist(), **eb2)
        save_state(st)
    B2, S2 = np.array(st["eb2"]["B"]), np.array(st["eb2"]["S"])
    P2 = C.unpack(x2)
    GAMMA = P2["gamma"]
    # ---- diagnostics ----
    if "diag" not in st:
        print("\nDiagnostics: gamma profile, finite-difference Hessian (subsample)")
        M0_full = X_TR @ B2
        base = nll(x2, Y_TR30, M0_full, S2)
        prof = {f: nll(np.concatenate([[x2[0] + np.log(f)], x2[1:]]), Y_TR30, M0_full, S2) - base for f in (0.5, 0.8, 1.25, 2.0)}
        Msub = M0_full[sub_idx]
        fs = lambda xx: nll(xx, Ysub, Msub, S2)  # noqa: E731
        h = 1e-3
        n = len(x2)
        Hs = np.zeros((n, n))
        f0 = fs(x2)
        for i in range(n):
            for j in range(i, n):
                ei, ej = np.eye(n)[i] * h, np.eye(n)[j] * h
                Hs[i, j] = Hs[j, i] = (fs(x2 + ei + ej) - fs(x2 + ei - ej) - fs(x2 - ei + ej) + fs(x2 - ei - ej)) / (4 * h * h)
            if time.time() - T_START > BUDGET_S:
                raise Budget()
        evals = np.linalg.eigvalsh(Hs)
        pd_ = bool(evals.min() > 0)
        corr = None
        if pd_:
            cov = np.linalg.inv(Hs)
            sd = np.sqrt(np.diag(cov))
            corr = (cov / np.outer(sd, sd)).tolist()
        st["diag"] = dict(base_nll=float(base), gamma_profile_delta_nll={str(k): float(v) for k, v in prof.items()},
                          hessian_eigenvalues=evals.tolist(), hessian_positive_definite=pd_,
                          hessian_condition=float(evals.max() / max(evals.min(), 1e-300)) if pd_ else None,
                          param_corr=corr, names=C.X_NAMES)
        save_state(st)
    # ---- W_T = 0 sensitivity ----
    print("\nSensitivity: W_T = 0 refit (single start from the W_T = 30 solution; B, S fixed)")
    x0w = run_opt(st, "wt0_full", x2, Y_TR0, X_TR @ B2, S2)
except Budget:
    print(f"\nPAUSED (time budget). Progress saved in {STATE}; rerun this script to continue.")
    sys.exit(0)

P0W = C.unpack(x0w)
print(f"\nFinal W_T=30 parameters: " + ", ".join(f"{k} {v:.4g}" for k, v in P2.items()))
print(f"W_T=0 parameters:        " + ", ".join(f"{k} {v:.4g}" for k, v in P0W.items()))


# ============================================================================
# 3. DEV-VAL EVALUATION
# ============================================================================
def origins_targets(y):
    rows = []
    for o in range(MIN_HISTORY, len(y), ORIGIN_STEP):
        if np.isnan(y[o]) or np.sum(~np.isnan(y[max(0, o - RECENT_WIN + 1):o + 1])) < RECENT_MIN_OBS:
            continue
        rows.append(o)
    return rows


def target(y, o, h):
    lo = o + h - TARGET_TOL
    if lo >= len(y):
        return np.nan
    seg = y[lo:min(o + h + TARGET_TOL, len(y) - 1) + 1]
    return float(np.nanmedian(seg)) if np.any(~np.isnan(seg)) else np.nan


def slope(seg):
    m = ~np.isnan(seg)
    if m.sum() < 5:
        return np.nan
    x = np.nonzero(m)[0].astype(float)
    v = seg[m]
    d = ((x - x.mean()) ** 2).sum()
    return float(((x - x.mean()) * (v - v.mean())).sum() / d) if d > 0 else np.nan


def dyn_features(y, o):
    s30 = y[max(0, o - 29):o + 1]
    T0 = float(np.nanmedian(y[:5])) if np.any(~np.isnan(y[:5])) else np.nan
    return [y[o], np.nanmean(y[max(0, o - 4):o + 1]), slope(y[max(0, o - 14):o + 1]), slope(s30), slope(y[max(0, o - 59):o + 1]),
            np.nanmax(s30) - np.nanmin(s30), np.sum(~np.isnan(s30)), o, T0, y[o] - T0]


def origin_table(ids):
    rows = []
    for c in ids:
        y, s0, gaps = SER[c]
        last = int(np.where(~np.isnan(y))[0].max())
        oi = np.where(~np.isnan(y))[0]
        big = oi[1:][np.abs(np.diff(y[oi])) >= SEVERE_JUMP_C]
        first_disc = int(big.min()) if len(big) else 10 ** 9
        for o in origins_targets(y):
            for h in HORIZONS:
                t_from, t_to = (s0 + o + 1) * BIN_S, (s0 + o + h) * BIN_S
                cross = bool(len(gaps) and np.any((gaps[:, 0] < t_to) & (gaps[:, 1] > t_from)))
                rows.append(dict(caseid=c, origin=o, horizon=h, target=target(y, o, h), y_now=float(y[o]),
                                 terminal_target=bool(o + h >= last - TERMINAL_EVAL_MIN + 1),
                                 crosses_long_gap=cross, history_discontinuity=bool(first_disc <= o),
                                 stage=next(f"{a}-{b if b < 10 ** 6 else 'end'}" for a, b in STAGES if a <= o < b)))
    return pd.DataFrame(rows)


OT_VA = origin_table(DVAL)
print(f"\nDev-val origins: {OT_VA[['caseid', 'origin']].drop_duplicates().shape[0]} origins, "
      f"{OT_VA.caseid.nunique()} cases; scorable rows {int(OT_VA.target.notna().sum())}")

Y_VA = matrix(DVAL)
idx_of = {c: i for i, c in enumerate(DVAL)}
omask = np.zeros(Y_VA.shape, bool)
for c, o in OT_VA[["caseid", "origin"]].drop_duplicates().itertuples(index=False):
    omask[idx_of[c], o] = True


def model_forecasts(p, M0, S, label, store_probs=False):
    out = C.gpb2_filter(Y_VA, p, M0, S, p["gamma"], store_probs=store_probs, origin_mask=omask)
    og = out["origins"]
    key = pd.DataFrame({"caseid": np.array(DVAL)[og["case"]], "origin": og["t"]})
    res = []
    for h in HORIZONS:
        m, v, w, cm, cb = C.forecast_moments(og["LW"], og["Z"], og["PP"], og["t"], h, p, p["gamma"])
        ivs, trunc = C.mixture_intervals(w, cm, cb, h, p, LEVELS)
        d = key.copy()
        d["horizon"] = h
        d[f"{label}"] = m
        d[f"{label}_var"] = v
        for lv, (lo, hi) in ivs.items():
            d[f"{label}_lo{int(lv * 100)}"], d[f"{label}_hi{int(lv * 100)}"] = lo, hi
        d[f"{label}_binom_trunc"] = trunc
        res.append(d)
    return pd.concat(res), out


print("Running robust filter on dev-val (W_T=30 parameters) ...")
M0_VA = X_VA @ B2
F_rob, OUT_ROB = model_forecasts(P2, M0_VA, S2, "robust", store_probs=True)
F_pri, _ = model_forecasts(P2, M0_VA, S_TINY * np.eye(2), "prior_only")
F_w0, _ = model_forecasts(P0W, M0_VA, S2, "robust_wt0")
R = OT_VA.merge(F_rob, on=["caseid", "origin", "horizon"]).merge(F_pri, on=["caseid", "origin", "horizon"]) \
    .merge(F_w0, on=["caseid", "origin", "horizon"])

# Gaussian random-walk state-space reference (development adequacy fit), only if consistent
gauss_note = "not available"
adq_json = os.path.join(ADQ_DIR, "adequacy_results.json")
if os.path.exists(adq_json):
    a = json.load(open(adq_json))
    if a.get("static_columns") == XCOLS:
        pg = dict(gamma=a["gamma_hat"], q=a["q_hat"], r=max(a["r_hat"], 1e-12), pi_u=0.0, q_J=a["q_hat"], pi_e=0.0, r_O=a["r_hat"])
        Fg, _ = model_forecasts(pg, X_VA @ np.array(a["B_hat"]), np.array(a["S_hat"]), "gaussian_rw")
        R = R.merge(Fg[["caseid", "origin", "horizon", "gaussian_rw"]], on=["caseid", "origin", "horizon"])
        gauss_note = "included (adequacy-study Gaussian fit, development data only)"
    else:
        gauss_note = "skipped: static design columns differ from the adequacy fit"

# simple baselines
pop_rows = []
for c in DTRAIN:
    y = SER[c][0]
    T0 = np.nanmedian(y[:5]) if np.any(~np.isnan(y[:5])) else np.nan
    if np.isfinite(T0):
        m = ~np.isnan(y)
        pop_rows.append(pd.DataFrame({"tau": np.nonzero(m)[0], "d": y[m] - T0}))
pop = pd.concat(pop_rows).groupby("tau")["d"].agg(["median", "size"])
pop = pop[pop["size"] >= 30]["median"].reindex(np.arange(0, 3000)).interpolate(limit_area="inside").ffill().bfill() \
    .rolling(9, center=True, min_periods=1).median().to_numpy()
base_cols = {"persistence": [], "linear": [], "population": []}
for r_ in R.itertuples():
    y = SER[r_.caseid][0]
    base_cols["persistence"].append(y[r_.origin])
    s = slope(y[max(0, r_.origin - LINEAR_WINDOW + 1):r_.origin + 1])
    base_cols["linear"].append(y[r_.origin] + (0.0 if np.isnan(s) else s * r_.horizon))
    T0 = np.nanmedian(y[:5]) if np.any(~np.isnan(y[:5])) else y[r_.origin]
    base_cols["population"].append(T0 + pop[min(r_.origin + r_.horizon, len(pop) - 1)])
for k, v in base_cols.items():
    R[k] = v

# generic ML (dev-train origins only; history-only features + static covariates)
print("Training generic ML baseline on dev-train origins ...")
OT_TR = origin_table(DTRAIN)
xs_idx = {c: i for i, c in enumerate(DTRAIN)}
feat_tr = OT_TR[["caseid", "origin"]].drop_duplicates()
Ftr = {(c, o): np.concatenate([dyn_features(SER[c][0], o), X_TR[xs_idx[c], 1:]]) for c, o in feat_tr.itertuples(index=False)}
feat_va = R[["caseid", "origin"]].drop_duplicates()
Fva = {(c, o): np.concatenate([dyn_features(SER[c][0], o), X_VA[idx_of[c], 1:]]) for c, o in feat_va.itertuples(index=False)}
R["generic_ml"] = np.nan
for h in HORIZONS:
    d = OT_TR[(OT_TR.horizon == h) & OT_TR.target.notna()]
    Xm = np.array([Ftr[(c, o)] for c, o in zip(d.caseid, d.origin)], float)
    w = 1.0 / d.groupby("caseid")["caseid"].transform("size").to_numpy()
    mdl = HistGradientBoostingRegressor(**ML_PARAMS).fit(Xm, (d.target - d.y_now).to_numpy(), sample_weight=w)
    sel = R.horizon == h
    Xv = np.array([Fva[(c, o)] for c, o in zip(R[sel].caseid, R[sel].origin)], float)
    R.loc[sel, "generic_ml"] = R.loc[sel, "y_now"].to_numpy() + mdl.predict(Xv)

METHODS = ["robust", "prior_only", "robust_wt0", "persistence", "linear", "population", "generic_ml"] + \
          (["gaussian_rw"] if "gaussian_rw" in R.columns else [])
R.to_csv(os.path.join(OUT, "dev_val_predictions.csv"), index=False)
T = R[R.target.notna()].copy()


def case_mae(d, col):
    return (d[col] - d.target).abs().groupby(d.caseid).mean()


strata = {"ALL": T, "NON_TERMINAL": T[~T.terminal_target], "TERMINAL_TARGET": T[T.terminal_target],
          "EXCL_GAP_CROSSING": T[~T.crosses_long_gap], "EXCL_HISTORY_DISCONTINUITY": T[~T.history_discontinuity]}
for s_ in ["20-60", "60-120", "120-240", "240-end"]:
    strata[f"STAGE_{s_}"] = T[T.stage == s_]
summ = []
for sname, d in strata.items():
    for h in HORIZONS:
        dh = d[d.horizon == h]
        for mth in METHODS:
            e = dh[mth] - dh.target
            cm = case_mae(dh, mth) if len(dh) else pd.Series(dtype=float)
            summ.append(dict(stratum=sname, horizon=h, method=mth, n_origins=len(dh), n_cases=dh.caseid.nunique(),
                             MAE=float(e.abs().mean()) if len(dh) else np.nan, RMSE=float(np.sqrt((e ** 2).mean())) if len(dh) else np.nan,
                             bias=float(e.mean()) if len(dh) else np.nan, median_AE=float(e.abs().median()) if len(dh) else np.nan,
                             case_MAE_mean=float(cm.mean()) if len(cm) else np.nan))
SUM = pd.DataFrame(summ)
SUM.to_csv(os.path.join(OUT, "dev_val_metrics.csv"), index=False)

rng = np.random.RandomState(11)
boot = []
for sname in ("ALL", "NON_TERMINAL"):
    for h in HORIZONS:
        dh = strata[sname][strata[sname].horizon == h]
        ref = case_mae(dh, "robust")
        for mth in METHODS[1:]:
            diff = (case_mae(dh, mth) - ref).dropna().to_numpy()
            bs = [diff[rng.randint(0, len(diff), len(diff))].mean() for _ in range(N_BOOT)]
            lo, hi = np.percentile(bs, [2.5, 97.5])
            boot.append(dict(stratum=sname, horizon=h, comparator=mth, n_cases=len(diff),
                             mean_caseMAE_comparator_minus_robust=float(diff.mean()), ci95_lo=float(lo), ci95_hi=float(hi),
                             ci_excludes_zero=bool(lo > 0 or hi < 0), share_cases_robust_lower=float((diff > 0).mean())))
BOOT = pd.DataFrame(boot)
BOOT.to_csv(os.path.join(OUT, "dev_val_paired_bootstrap.csv"), index=False)

calib = []
for sname in ("ALL", "NON_TERMINAL", "TERMINAL_TARGET"):
    for mth in ("robust", "prior_only", "robust_wt0"):
        for h in HORIZONS:
            dh = strata[sname][strata[sname].horizon == h]
            for lv in LEVELS:
                lo, hi = dh[f"{mth}_lo{int(lv * 100)}"], dh[f"{mth}_hi{int(lv * 100)}"]
                inside = (dh.target >= lo) & (dh.target <= hi)
                calib.append(dict(stratum=sname, method=mth, horizon=h, nominal=lv, coverage_origin=float(inside.mean()),
                                  coverage_case_weighted=float(inside.groupby(dh.caseid).mean().mean()),
                                  median_width=float((hi - lo).median()), n_origins=len(dh)))
CAL = pd.DataFrame(calib)
CAL.to_csv(os.path.join(OUT, "dev_val_calibration.csv"), index=False)

# ---- posterior attribution ----
# PRIMARY: offline fixed-lag (10 min) mode posterior at the event minute from four mode-forced filter runs
#          (uses data after the event; a diagnostic, never a forecasting input).
# SECONDARY: filtered (causal) probabilities, which cannot yet see persistence at the event minute.
ATT_LAG = 10
PR = OUT_ROB["prob"]
ev = pd.read_csv(ev_path)
ev = ev[(ev["set"] == "dev_val") & ev.caseid.isin(DVAL)].reset_index(drop=True)
ev = ev[ev.start_min >= 1].reset_index(drop=True)
att = pd.DataFrame()
if len(ev):
    rows_i = np.array([idx_of[c] for c in ev.caseid])
    post, gap = C.fixed_lag_mode_posterior(Y_VA[rows_i], ev.start_min.astype(int).to_numpy(), ATT_LAG, P2, M0_VA[rows_i], S2, GAMMA)
    pj, po = post[:, 2] + post[:, 3], post[:, 1] + post[:, 3]
    att = ev[["caseid", "start_min", "pattern"]].copy()
    att["no_post_window"] = ev.post_level_C.isna().to_numpy()
    att["P_jump_fixed_lag"], att["P_outlier_fixed_lag"], att["P_calm_fixed_lag"] = pj, po, post[:, 0]
    att["consistency_gap_nats"] = gap
    att["attribution"] = np.where((pj >= 0.5) & (pj >= po), "level_jump", np.where(po >= 0.5, "observation_outlier", "neither"))
    att["P_jump_filtered"] = [PR["jump"][i, t] for i, t in zip(rows_i, ev.start_min.astype(int))]
    att["P_outlier_filtered"] = [PR["outlier"][i, t] for i, t in zip(rows_i, ev.start_min.astype(int))]
    att["attribution_filtered"] = np.where((att.P_jump_filtered >= 0.5) & (att.P_jump_filtered >= att.P_outlier_filtered), "level_jump",
                                           np.where(att.P_outlier_filtered >= 0.5, "observation_outlier", "neither"))
ATT = att
ATT.to_csv(os.path.join(OUT, "dev_val_event_attribution.csv"), index=False)
att_tab = pd.crosstab(ATT.pattern, ATT.attribution) if len(ATT) else pd.DataFrame()
att_tab_f = pd.crosstab(ATT.pattern, ATT.attribution_filtered) if len(ATT) else pd.DataFrame()
minute_stats = {k: dict(mean=float(np.nanmean(v)), share_gt_0p5=float(np.nanmean(v > 0.5))) for k, v in PR.items()}

# ---- patient-level states (dev-val, end of record) ----
zc, Pc = OUT_ROB["z"], OUT_ROB["P"]
pat = pd.DataFrame({"caseid": DVAL, "alpha_mean": zc[:, 0], "alpha_sd": np.sqrt(Pc[:, 0, 0]), "beta_mean_C_per_h": zc[:, 1],
                    "beta_sd": np.sqrt(Pc[:, 1, 1]), "alpha_beta_corr": Pc[:, 0, 1] / np.sqrt(Pc[:, 0, 0] * Pc[:, 1, 1]),
                    "level_u_mean": zc[:, 2], "level_u_sd": np.sqrt(Pc[:, 2, 2]),
                    "mean_P_calm": np.nanmean(PR["calm"], 1), "mean_P_jump": np.nanmean(PR["jump"], 1),
                    "mean_P_outlier": np.nanmean(PR["outlier"], 1), "minutes_P_jump_gt_0p5": np.nansum(PR["jump"] > 0.5, 1),
                    "minutes_P_outlier_gt_0p5": np.nansum(PR["outlier"] > 0.5, 1),
                    "prior_m0_alpha": M0_VA[:, 0], "prior_m0_beta": M0_VA[:, 1]})
pat.to_csv(os.path.join(OUT, "dev_val_patient_states.csv"), index=False)

# ---- figures ----
lens = pd.Series({c: len(SER[c][0]) for c in DVAL})
cands = [c for c in DVAL if (R.caseid == c).sum() >= 4 * len(HORIZONS)]
reps = [int(lens[cands].sort_values().index[int(q * (len(cands) - 1))]) for q in (0.1, 0.5, 0.9)] if cands else []
if reps:
    ri = [idx_of[c] for c in reps]
    outr = C.gpb2_filter(Y_VA[ri], P2, M0_VA[ri], S2, GAMMA, store_probs=True, store_states=True)
    fig, axes = plt.subplots(len(reps), 1, figsize=(13, 4 * len(reps)))
    for k, (c, ax) in enumerate(zip(reps, np.atleast_1d(axes))):
        y = SER[c][0]
        tt = np.arange(len(y))
        hz = C.Hrow(tt, GAMMA)
        sm = np.einsum("ti,ti->t", outr["st_z"][k, :len(y)], hz)
        sv = np.einsum("ti,tij,tj->t", hz, outr["st_P"][k, :len(y)], hz)
        ax.plot(tt, y, ".", ms=2, color="k", label="observed BT")
        ax.plot(tt, sm, color="#c44e52", lw=1, label="filtered signal mean H z")
        ax.fill_between(tt, sm - 2 * np.sqrt(sv), sm + 2 * np.sqrt(sv), color="#c44e52", alpha=0.15)
        rc = R[(R.caseid == c) & (R.horizon == 30)]
        for o in rc.origin.iloc[[0, len(rc) // 2, -1]]:
            rr = rc[rc.origin == o].iloc[0]
            ax.errorbar(o + 30, rr.robust, yerr=[[rr.robust - rr.robust_lo80], [rr.robust_hi80 - rr.robust]], fmt="o",
                        color="#4c72b0", capsize=3)
        ax2 = ax.twinx()
        ax2.fill_between(tt, 0, outr["prob"]["jump"][k, :len(y)], color="#dd8452", alpha=0.4, step="mid", label="P(jump)")
        ax2.fill_between(tt, 0, outr["prob"]["outlier"][k, :len(y)], color="#8172b2", alpha=0.4, step="mid", label="P(outlier)")
        ax2.set_ylim(0, 4)
        ax.set(title=f"dev-val case {c} (length percentile {[10, 50, 90][k]}; deterministic, not error-based)",
               xlabel="minutes since settled start", ylabel="C")
        ax.legend(loc="upper left", fontsize=7)
        ax2.legend(loc="upper right", fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "representative_cases.png"), dpi=110)
    plt.close(fig)
fig, ax = plt.subplots(1, 2, figsize=(13, 4))
for a_, sname in zip(ax, ("ALL", "NON_TERMINAL")):
    d = SUM[SUM.stratum == sname]
    for k, mth in enumerate(METHODS):
        a_.bar(np.arange(3) + (k - len(METHODS) / 2) * 0.1, d[d.method == mth].MAE, 0.1, label=mth)
    a_.set_xticks(range(3), [f"+{h}" for h in HORIZONS])
    a_.set(title=f"dev-val MAE ({sname})", ylabel="MAE (C)")
ax[0].legend(fontsize=6)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "mae_by_horizon.png"), dpi=110)
plt.close(fig)
fig, ax = plt.subplots(figsize=(6, 5))
ax.plot([0, 1], [0, 1], "k:")
for h in HORIZONS:
    d = CAL[(CAL.stratum == "NON_TERMINAL") & (CAL.method == "robust") & (CAL.horizon == h)]
    ax.plot(d.nominal, d.coverage_origin, "o-", label=f"robust +{h} (non-terminal)")
ax.set(xlabel="nominal", ylabel="empirical coverage", title="dev-val calibration (no recalibration)")
ax.legend(fontsize=7)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "calibration.png"), dpi=110)
plt.close(fig)

# ============================================================================
# 4. FINAL REPORT, PROTECTION, STATUS
# ============================================================================
HASH_AFTER = {**hash_tree(CODE4_DIR), **hash_tree(FREEZE_DIR)}
PROT["protected_hashes_unchanged"] = HASH_BEFORE == HASH_AFTER
PROT["no_holdout_case_loaded"] = not (LOADED & final_ids)
PROT["all_loaded_cases_development"] = LOADED <= set(dev_ids)
PROTECTED = all(v is True or isinstance(v, str) for v in PROT.values()) and PROT["protected_hashes_unchanged"] \
    and PROT["no_holdout_case_loaded"] and PROT["all_loaded_cases_development"]
fit_ok = all(st[k].get("success") for k in ("r1_full", "r2_full")) and st["eb2"]["converged"]
forecasts_ok = bool(np.isfinite(R[["robust", "robust_var"]].to_numpy()).all())
REAL_OK = fit_ok and forecasts_ok
verif = json.load(open(VERIF_JSON)) if os.path.exists(VERIF_JSON) else {}

params = dict(final_WT30=P2, WT0=P0W, B=B2.tolist(), S=S2.tolist(), design_columns=XCOLS,
              eb_round1=st["eb1"], eb_round2=st["eb2"],
              round_change=dict(psi_r1=C.unpack(np.array(st["r1_full"]["x"])), psi_r2=P2,
                                S_change=float(np.abs(np.array(st["eb2"]["S"]) - np.array(st["eb1"]["S"])).max()),
                                B_change=float(np.abs(np.array(st["eb2"]["B"]) - np.array(st["eb1"]["B"])).max())),
              multistart=[dict(start=i, init=STARTS[i], nll=st[f"r1_start{i}"]["nll"], success=st[f"r1_start{i}"]["success"],
                               params=st[f"r1_start{i}"]["params"], near_bounds=st[f"r1_start{i}"]["near_bounds"])
                          for i in range(len(STARTS))],
              optimisation={k: {kk: st[k].get(kk) for kk in ("nll", "success", "message", "iters", "near_bounds")}
                            for k in ("r1_full", "r2_full", "wt0_full")},
              diagnostics=st["diag"], gaussian_reference=gauss_note,
              minute_mode_probabilities=minute_stats, protection=PROT, created_utc=datetime.now(timezone.utc).isoformat())
json.dump(params, open(os.path.join(OUT, "dev_fit_parameters.json"), "w"), indent=2,
          default=lambda o: o.item() if hasattr(o, "item") else str(o))

A = SUM[(SUM.stratum == "ALL")].pivot(index="method", columns="horizon", values="MAE").round(3)
NT = SUM[(SUM.stratum == "NON_TERMINAL")].pivot(index="method", columns="horizon", values="MAE").round(3)
TT = SUM[(SUM.stratum == "TERMINAL_TARGET")].pivot(index="method", columns="horizon", values="MAE").round(3)
cal_nt = CAL[(CAL.stratum == "NON_TERMINAL") & (CAL.method == "robust")].pivot(index="horizon", columns="nominal", values="coverage_origin").round(3)
report = f"""# Development-only real-data fit and validation (robust thermal state-space model)

Development cases only (dev-train {len(DTRAIN)}, dev-val {len(DVAL)}; seed {DEV_SEED}). Final holdout ({len(final_ids)}) read as
IDs only; overlap 0. W_T={W_T} was selected from development-only edge forensics and fixed before final holdout
evaluation; W_T=0 is reported as a sensitivity analysis. Exploratory development results, not final evidence.

## Fitted parameters (W_T=30)
{json.dumps({k: round(v, 6) for k, v in P2.items()})}
Prior covariance S: {np.round(S2, 5).tolist()}; m0(x) design columns: {XCOLS}
Multi-start (25% subsample): {[ (round(m['nll'], 1), m['success']) for m in params['multistart']]}
Near bounds (final): {st['r2_full']['near_bounds']}; gamma profile delta-NLL: {st['diag']['gamma_profile_delta_nll']}
Hessian positive definite (subsample): {st['diag']['hessian_positive_definite']}

## Dev-val MAE (C) — all scorable
{A.to_string()}

## Non-terminal targets
{NT.to_string()}

## Terminal targets (target within {TERMINAL_EVAL_MIN} min of recording end; evaluation label only)
{TT.to_string()}

## Robust-model interval coverage (non-terminal, no recalibration)
{cal_nt.to_string()}

## Event attribution — PRIMARY: offline fixed-lag ({ATT_LAG} min) posterior at the event minute
{att_tab.to_string() if len(att_tab) else 'no events'}
Max consistency gap (approximation diagnostic): {float(ATT.consistency_gap_nats.max()) if len(ATT) else float('nan'):.2e} nats

## Event attribution — SECONDARY: filtered (causal) probabilities at the event minute
{att_tab_f.to_string() if len(att_tab_f) else 'no events'}

## Inference accounting
Exact: within-component Kalman updates, candidate weights given the retained mixture, diffuse initialisation.
Approximate: GPB2 merging of histories sharing the newest (jump, outlier) mode; missing-minute moment step;
likelihood from the approximate retained mixture; Gaussian approximation of per-case theta information in EB.
Forecast mean/variance and intervals are exact functionals of the retained mixture, not of the exact posterior.
The latent level u is a latent measured-signal level; it is not claimed to be core temperature.

FINAL_HOLDOUT_PROTECTED: {'PASS' if PROTECTED else 'FAIL'}
REAL_DATA_MODEL_RUN: {'PASS' if REAL_OK else 'FAIL'}
"""
open(os.path.join(OUT, "dev_robust_report.md"), "w").write(report)

pd.set_option("display.width", 220)
print(report)
print("Paired case-level bootstrap (comparator minus robust; positive = robust lower error):")
print(BOOT[BOOT.stratum == "NON_TERMINAL"].round(3).to_string(index=False))
print(f"\nreal development cases loaded: {len(LOADED)} | dev-train {len(DTRAIN)} | dev-val {len(DVAL)} | "
      f"holdout {len(final_ids)} | holdout overlap {len(LOADED & final_ids)} | protected hashes "
      f"{'UNCHANGED' if PROT['protected_hashes_unchanged'] else 'CHANGED'}")
print(f"\nFINAL_HOLDOUT_PROTECTED: {'PASS' if PROTECTED else 'FAIL'}")
print(f"COMBINED_MODEL_MATH: {verif.get('COMBINED_MODEL_MATH', 'NOT CHECKED (run robust_statespace_verification.py)')}")
print(f"SYNTHETIC_VERIFICATION: {verif.get('SYNTHETIC_VERIFICATION', 'NOT CHECKED (run robust_statespace_verification.py)')}")
print(f"REAL_DATA_MODEL_RUN: {'PASS' if REAL_OK else 'FAIL'}")
print(f"REAL_DATA_DEVELOPMENT_ONLY: {'PASS' if PROTECTED else 'FAIL'}")
