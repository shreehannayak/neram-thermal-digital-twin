"""
development_model_adequacy.py

DEVELOPMENT-ONLY model-adequacy study for the latent level process of the corrected
thermal state-space model. Decides between:
  A = Gaussian random-walk level appears adequate
  B = Gaussian random-walk level appears inadequate; a jump-tolerant process is warranted
  C = evidence inconclusive

NEVER touches the 1,100-case final holdout (no tracks loaded, no metadata used).
NEVER modifies code4_outputs/ or final_holdout_freeze/ (verified by SHA-256 before and after).
NO forecasting evaluation, NO MAE, NO use of the old exploratory-test MAE.

MODEL (identical to the verified synthetic specification)
  y_t = H_t z_t + e_t,  H_t = [exp(-gamma t) - 1, t/60, 1],  e_t ~ N(0, r)
  z_t = [alpha, beta, u_t]',  z_t = z_{t-1} + w_t,  w_t ~ N(0, diag(0, 0, q)) per minute
  theta = [alpha, beta]' ~ N(m0(x), S),  m0(x) = B' x  (x = [1, standardised static covariates])
  Exact diffuse level at the first observed settled minute; T0 removed.
  Time: tau = minutes since (first plausible BT sample + 15 min), 1-min median bins (Code 4 rules).

ESTIMATION (development-train only): pooled diffuse Kalman marginal likelihood.
  Because the filter is linear in the prior mean, each case's innovation is v = v0 + dv m0 and
  the log-likelihood is exactly quadratic in vec(B). B is therefore PROFILED OUT in closed form
  (generalised least squares) at every (gamma, q, r, S); the outer optimiser searches 6 numbers:
  log gamma, log q, log r and a Cholesky factor of S. Three pre-specified starting points; best kept.

PRE-SPECIFIED CHOICES (fixed before any real data was run)
  dev split 75/25, seed 20261201; jump screen = Code 3B frozen rules; decision rule below.
"""

import gzip
import hashlib
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from scipy import optimize, stats

# ============================================================================
# CONFIGURATION (pre-specified)
# ============================================================================
API = "https://api.vitaldb.net"
CODE4_DIR = "code4_outputs"
FREEZE_DIR = "final_holdout_freeze"
CACHE_DIR = "vitaldb_bt_cache"
OUT_DIR = "development_adequacy"
FIG_DIR = os.path.join(OUT_DIR, "figures")

DEV_SPLIT_SEED = 20261201
DEV_TRAIN_FRAC = 0.75
MIN_DEV_TRAIN_CASES = 200

# Frozen Code 4 data rules
PLAUS_LO, PLAUS_HI = 25.0, 43.0
EQUIL_MIN = 15
BIN_S = 60

# Frozen static-covariate timing rules (Code 4)
STATIC_SPEC = {
    "age": "numeric", "sex": "categorical", "height": "numeric", "weight": "numeric", "bmi": "numeric",
    "asa": "numeric", "emop": "numeric", "department": "categorical", "optype": "categorical",
    "ane_type": "categorical",
}
STATIC_MIN_COVERAGE = 0.80
MAX_CAT_LEVELS = 20

# Optimisation
STARTS = [dict(gamma=0.01, q=1e-4, r=1e-3), dict(gamma=0.03, q=1e-4, r=1e-3), dict(gamma=0.10, q=1e-3, r=1e-2)]
S_START = np.diag([0.5 ** 2, 0.3 ** 2])
BOUNDS = [(np.log(0.002), np.log(0.2)), (np.log(1e-8), np.log(1.0)), (np.log(1e-8), np.log(1.0)),
          (np.log(1e-4), np.log(10.0)), (-10.0, 10.0), (np.log(1e-4), np.log(10.0))]

# Jump screen — Code 3B frozen values (not chosen for this study)
JUMP_C = 0.5                # |change between consecutive observed minutes| >= 0.5 C
MAX_PAIR_GAP_MIN = 5        # pairs separated by > 5 min are not "abrupt" evidence
EVENT_MERGE_MIN = 5
PRE_POST_N = 5
LOOKAROUND_MIN = 30
RETURN_TOL_C, RETURN_FRAC, PERSIST_FRAC = 0.3, 0.3, 0.5
MIN_SUPPORT = 3

ACF_LAGS = [1, 2, 5, 10]
MIN_ACF_PAIRS = 30
QUANTILES = [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99]

# ---- PRE-SPECIFIED DECISION RULE (written before any real-data run) ----
GAUSS_TAIL3 = 2 * stats.norm.sf(3)          # 0.0027
GAUSS_TAIL4 = 2 * stats.norm.sf(4)          # 6.33e-5
RULE = dict(white_max_abs_median_acf=0.10,  # median within-case ACF at lags 1,2,5,10
            A_tail3_ratio_max=2.0, A_tail4_ratio_max=10.0, A_jump_rate_ratio_max=3.0, A_event_z4_share_max=0.10,
            B_tail4_ratio_min=10.0, B_jump_rate_ratio_min=10.0, B_event_z4_share_min=0.50,
            stable_acf_abs_diff=0.05)   # stability = same A/B sub-criterion verdicts in dev-train and dev-val

os.makedirs(FIG_DIR, exist_ok=True)


# ============================================================================
# PROTECTION: hash every protected file before doing anything
# ============================================================================
def hash_tree(d):
    out = {}
    for root, _, files in os.walk(d):
        for f in sorted(files):
            p = os.path.join(root, f)
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                h.update(fh.read())
            out[p] = h.hexdigest()
    return out


for d in (CODE4_DIR, FREEZE_DIR):
    if not os.path.isdir(d):
        raise SystemExit(f"STOP: required folder {d}/ not found.")
HASH_BEFORE = {**hash_tree(CODE4_DIR), **hash_tree(FREEZE_DIR)}


# ============================================================================
# TASK 1 — DEVELOPMENT SPLIT
# ============================================================================
final_ids = set(pd.read_csv(os.path.join(FREEZE_DIR, "final_holdout_case_ids.csv"))["caseid"].astype(int))
dev_tbl = pd.read_csv(os.path.join(FREEZE_DIR, "development_case_ids.csv"))
dev_ids = np.array(sorted(dev_tbl["caseid"].astype(int)))
fman = json.load(open(os.path.join(FREEZE_DIR, "freeze_manifest.json")))
ids_hash = hashlib.sha256(",".join(str(i) for i in sorted(final_ids)).encode()).hexdigest()
protect = {"final_holdout_hash_matches_manifest": ids_hash == fman["final_holdout_ids_sha256"],
           "development_disjoint_from_final_holdout": not (set(dev_ids) & final_ids)}
if not all(protect.values()):
    raise SystemExit(f"STOP: holdout protection check failed before start: {protect}")

perm = dev_ids[np.random.RandomState(DEV_SPLIT_SEED).permutation(len(dev_ids))]
n_tr = int(round(DEV_TRAIN_FRAC * len(perm)))
DTRAIN, DVAL = sorted(int(c) for c in perm[:n_tr]), sorted(int(c) for c in perm[n_tr:])
assert not (set(DTRAIN) & set(DVAL)) and not ((set(DTRAIN) | set(DVAL)) & final_ids)
prov = dev_tbl.set_index("caseid")["former_code4_split"]
split_df = pd.DataFrame({"caseid": DTRAIN + DVAL, "dev_split": ["dev_train"] * len(DTRAIN) + ["dev_val"] * len(DVAL)})
split_df["former_code4_split"] = split_df["caseid"].map(prov)
split_df.sort_values("caseid").to_csv(os.path.join(OUT_DIR, "dev_split.csv"), index=False)
print("=" * 78)
print("DEVELOPMENT-ONLY MODEL ADEQUACY STUDY")
print("=" * 78)
print(f"Task 1: development {len(dev_ids)} -> dev-train {len(DTRAIN)} / dev-val {len(DVAL)} "
      f"(seed {DEV_SPLIT_SEED}); final holdout {len(final_ids)} untouched")
print(f"  provenance dev-train: {split_df[split_df.dev_split == 'dev_train'].former_code4_split.value_counts().to_dict()}")
print(f"  provenance dev-val  : {split_df[split_df.dev_split == 'dev_val'].former_code4_split.value_counts().to_dict()}")


# ============================================================================
# DATA (development cases only; canonical tracks frozen by Code 4 Rule 2)
# ============================================================================
manifest = pd.read_csv(os.path.join(CODE4_DIR, "code4_cohort_manifest.csv"))
manifest = manifest[manifest["caseid"].isin(dev_ids)]                        # holdout rows dropped immediately
canon = manifest.set_index("caseid")["canonical_tid"].astype(str)
LOADED_CASES = set()


def fetch_bytes(url, retries=4, timeout=120):
    last = None
    for a in range(retries):
        try:
            rr = requests.get(url, timeout=timeout)
            rr.raise_for_status()
            raw = rr.content
            return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (a + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def settled_series(cid):
    """Code 4 rules: plausible 25-43 C, 1-min medians, settled start = first plausible + 15 min."""
    assert cid not in final_ids
    LOADED_CASES.add(cid)
    tid = canon[cid]
    path = os.path.join(CACHE_DIR, f"{tid}.csv.gz")
    df = pd.read_csv(path) if os.path.exists(path) else pd.read_csv(io.BytesIO(fetch_bytes(f"{API}/{tid}")))
    df = df.iloc[:, :2].copy()
    df.columns = ["t", "v"]
    df = df.apply(pd.to_numeric, errors="coerce").dropna().sort_values("t").drop_duplicates("t")
    df = df[(df.v >= PLAUS_LO) & (df.v <= PLAUS_HI)]
    if len(df) == 0:
        return np.array([])
    b = (df.t // BIN_S).astype(int)
    med = df.v.groupby(b).median()
    s0 = int(np.ceil((df.t.iloc[0] + EQUIL_MIN * 60) / BIN_S))
    if s0 > med.index.max():
        return np.array([])
    y = np.full(int(med.index.max()) - s0 + 1, np.nan)
    keep = med[med.index >= s0]
    y[keep.index.to_numpy() - s0] = keep.to_numpy()
    return y


def load(ids):
    ser, bad = {}, []
    for k, c in enumerate(ids, 1):
        try:
            y = settled_series(c)
            if np.sum(~np.isnan(y)) >= 2:
                ser[c] = y
            else:
                bad.append(c)
        except Exception:  # noqa: BLE001
            bad.append(c)
        if k % 500 == 0:
            print(f"  loaded {k}/{len(ids)}")
    return ser, bad


print("\nLoading development-train series ...")
SER_TR, BAD_TR = load(DTRAIN)
TR_IDS = sorted(SER_TR)
print(f"  dev-train usable {len(TR_IDS)}; unusable {len(BAD_TR)} (fewer than 2 settled observations or load failure)")
if len(TR_IDS) < MIN_DEV_TRAIN_CASES:
    raise SystemExit(f"STOP: only {len(TR_IDS)} usable dev-train cases (< {MIN_DEV_TRAIN_CASES}).")


def to_matrix(ser, ids):
    L = max(len(ser[c]) for c in ids)
    Y = np.full((len(ids), L), np.nan)
    for i, c in enumerate(ids):
        Y[i, :len(ser[c])] = ser[c]
    return Y


Y_TR = to_matrix(SER_TR, TR_IDS)

# ---- static covariates (Code 4 timing rule; coverage on dev-train only) ----
cases = pd.read_csv(io.BytesIO(fetch_bytes(f"{API}/cases")))
cases = cases[cases["caseid"].isin(dev_ids)].set_index("caseid")              # holdout rows dropped
trm = cases.reindex(TR_IDS)
sel_num, sel_cat, cov_rows = [], [], []
for f, typ in STATIC_SPEC.items():
    if f not in cases.columns:
        cov_rows.append(dict(field=f, present=False, coverage=0.0, selected=False))
        continue
    cov = float((pd.to_numeric(trm[f], errors="coerce") if typ == "numeric" else trm[f]).notna().mean())
    sel = cov >= STATIC_MIN_COVERAGE
    cov_rows.append(dict(field=f, present=True, type=typ, coverage=cov, selected=sel))
    if sel:
        (sel_num if typ == "numeric" else sel_cat).append(f)
num_stats = {f: (float(pd.to_numeric(trm[f], errors="coerce").median()),) for f in sel_num}
num_mu, num_sd = {}, {}
for f in sel_num:
    x = pd.to_numeric(trm[f], errors="coerce").fillna(num_stats[f][0])
    num_mu[f], num_sd[f] = float(x.mean()), float(x.std() or 1.0)
cat_levels = {f: trm[f].astype(str).value_counts().index[:MAX_CAT_LEVELS].tolist()[1:] for f in sel_cat}  # drop reference level
STATIC_COLS = ["intercept"] + sel_num + [f"{f}={lv}" for f in sel_cat for lv in cat_levels[f]]


def xvec(c):
    r = cases.loc[c] if c in cases.index else pd.Series(dtype=object)
    v = [1.0]
    for f in sel_num:
        x = pd.to_numeric(r.get(f, np.nan), errors="coerce")
        v.append(((num_stats[f][0] if pd.isna(x) else float(x)) - num_mu[f]) / num_sd[f])
    for f in sel_cat:
        val = str(r.get(f, "nan"))
        v.extend(1.0 if val == lv else 0.0 for lv in cat_levels[f])
    return np.array(v)


X_TR = np.array([xvec(c) for c in TR_IDS])


# ============================================================================
# VECTORISED DIFFUSE KALMAN FILTER
# ============================================================================
def kalman(Y, gamma, q, r, S, M0=None, store=False):
    """Returns per-case sums for the profiled likelihood, and optionally the innovations.
    With M0=None the filter runs at m0 = 0 and tracks d(innovation)/d(m0) (exact linearity)."""
    N, L = Y.shape
    obs = ~np.isnan(Y)
    m0 = np.zeros((N, 2)) if M0 is None else M0
    started = np.zeros(N, bool)
    z, P, D = np.zeros((N, 3)), np.zeros((N, 3, 3)), np.zeros((N, 3, 2))
    slogF, c, b, A, nupd = np.zeros(N), np.zeros(N), np.zeros((N, 2)), np.zeros((N, 2, 2)), np.zeros(N)
    V = np.full((N, L), np.nan) if store else None
    F = np.full((N, L), np.nan) if store else None
    I3 = np.eye(3)
    for t in range(L):
        ph = np.array([np.exp(-gamma * t) - 1.0, t / 60.0])
        h = np.array([ph[0], ph[1], 1.0])
        P[started, 2, 2] += q
        o = obs[:, t]
        new = o & ~started
        if new.any():
            yt = Y[new, t]
            z[new, :2] = m0[new]
            z[new, 2] = yt - m0[new] @ ph
            Pi = np.zeros((3, 3))
            Pi[:2, :2] = S
            Pi[:2, 2] = Pi[2, :2] = -S @ ph
            Pi[2, 2] = ph @ S @ ph + r
            P[new] = Pi
            D[new] = np.array([[1.0, 0.0], [0.0, 1.0], [-ph[0], -ph[1]]])
            started |= new
        upd = o & started & ~new
        if upd.any():
            zi, Pi, Di = z[upd], P[upd], D[upd]
            v = Y[upd, t] - zi @ h
            Ph = Pi @ h
            Fv = Ph @ h + r
            K = Ph / Fv[:, None]
            dv = -np.einsum("j,njk->nk", h, Di)
            slogF[upd] += np.log(Fv)
            c[upd] += v * v / Fv
            b[upd] += dv * (v / Fv)[:, None]
            A[upd] += np.einsum("ni,nj->nij", dv, dv) / Fv[:, None, None]
            nupd[upd] += 1
            z[upd] = zi + K * v[:, None]
            D[upd] = Di + K[:, :, None] * dv[:, None, :]
            IKH = I3[None] - np.einsum("ni,j->nij", K, h)
            P[upd] = np.einsum("nij,njk,nlk->nil", IKH, Pi, IKH) + r * np.einsum("ni,nj->nij", K, K)
            if store:
                V[upd, t] = v
                F[upd, t] = Fv
    return dict(slogF=slogF, c=c, b=b, A=A, nupd=nupd, V=V, F=F)


def unpack(p):
    g, q, r = np.exp(p[0]), np.exp(p[1]), np.exp(p[2])
    Lc = np.array([[np.exp(p[3]), 0.0], [p[4], np.exp(p[5])]])
    return g, q, r, Lc @ Lc.T


def profiled_nll(p, Y, X, return_B=False):
    g, q, r, S = unpack(p)
    k = kalman(Y, g, q, r, S)
    k_ = X.shape[1]
    G = np.zeros((2 * k_, 2 * k_))
    gv = np.zeros(2 * k_)
    for a_ in range(2):
        gv[a_ * k_:(a_ + 1) * k_] = X.T @ k["b"][:, a_]
        for b_ in range(2):
            G[a_ * k_:(a_ + 1) * k_, b_ * k_:(b_ + 1) * k_] = (X * k["A"][:, a_, b_][:, None]).T @ X
    beta = -np.linalg.lstsq(G + 1e-9 * np.eye(2 * k_), gv, rcond=None)[0]
    nll = 0.5 * (k["slogF"].sum() + k["nupd"].sum() * np.log(2 * np.pi) + k["c"].sum() + 2 * gv @ beta + beta @ G @ beta)
    if return_B:
        return nll, beta.reshape(2, k_).T
    return nll


# ============================================================================
# TASK 2 — FIT ON DEV-TRAIN ONLY
# ============================================================================
print("\nTask 2: pooled diffuse Kalman marginal likelihood on dev-train (B profiled exactly) ...")
fits = []
for s in STARTS:
    Ls = np.linalg.cholesky(S_START)
    p0 = np.array([np.log(s["gamma"]), np.log(s["q"]), np.log(s["r"]), np.log(Ls[0, 0]), Ls[1, 0], np.log(Ls[1, 1])])
    t0 = time.time()
    res = optimize.minimize(profiled_nll, p0, args=(Y_TR, X_TR), method="L-BFGS-B", bounds=BOUNDS,
                            options=dict(maxiter=300))
    fits.append(res)
    print(f"  start gamma={s['gamma']}: nll {res.fun:.2f}, success {res.success} ({res.message}), {time.time() - t0:.0f} s")
best = min(fits, key=lambda r_: r_.fun)
G_HAT, Q_HAT, R_HAT, S_HAT = unpack(best.x)
_, B_HAT = profiled_nll(best.x, Y_TR, X_TR, return_B=True)
at_bound = [i for i, (v_, (lo, hi)) in enumerate(zip(best.x, BOUNDS)) if abs(v_ - lo) < 1e-6 or abs(v_ - hi) < 1e-6]
start_spread = max(r_.fun for r_ in fits) - best.fun
fit_converged = bool(best.success)
interior_fit = not at_bound      # a boundary solution is evidence of misfit; it blocks decision A
rw_sd = {f"{k}_min": float(np.sqrt(Q_HAT * k)) for k in (1, 5, 15, 30, 60)}
print(f"  gamma_hat {G_HAT:.4f}/min | q_hat {Q_HAT:.3e} C^2/min | r_hat {R_HAT:.3e} C^2 (sd {np.sqrt(R_HAT):.3f} C)")
print("  implied random-walk SD: " + ", ".join(f"{k} {v:.3f} C" for k, v in rw_sd.items()))
print(f"  S_hat {np.round(S_HAT, 4).tolist()} | parameters at a bound: {at_bound} | nll spread across starts {start_spread:.2f}")


# ============================================================================
# TASKS 3, 4, 6 — diagnostics (functions reused unchanged for Task 7)
# ============================================================================
def innovations(Y, ids, X):
    M0 = X @ B_HAT
    k = kalman(Y, G_HAT, Q_HAT, R_HAT, S_HAT, M0=M0, store=True)
    return k["V"], k["F"], k["V"] / np.sqrt(k["F"])


def pooled_summary(Z, V, label):
    zf, vf = Z[~np.isnan(Z)], V[~np.isnan(V)]
    sk = stats.skew(zf) if len(zf) > 3 else np.nan
    ku = stats.kurtosis(zf) if len(zf) > 4 else np.nan
    row = dict(set=label, n_innovations=int(len(zf)), z_mean=float(zf.mean()), z_sd=float(zf.std()),
               z_median=float(np.median(zf)), z_mad=float(stats.median_abs_deviation(zf, scale="normal")),
               v_mean_C=float(vf.mean()), v_sd_C=float(vf.std()), v_median_C=float(np.median(vf)),
               frac_abs_z_gt2=float(np.mean(np.abs(zf) > 2)), frac_abs_z_gt3=float(np.mean(np.abs(zf) > 3)),
               frac_abs_z_gt4=float(np.mean(np.abs(zf) > 4)), skewness=float(sk), excess_kurtosis=float(ku))
    for qq in QUANTILES:
        row[f"z_q{int(qq * 100):02d}"] = float(np.quantile(zf, qq))
    return row


def case_summaries(Z, ids):
    rows = []
    for i, c in enumerate(ids):
        z = Z[i]
        zz = z[~np.isnan(z)]
        if len(zz) < 5:
            continue
        row = dict(caseid=c, n=int(len(zz)), z_mean=float(zz.mean()), z_sd=float(zz.std()),
                   frac_gt3=float(np.mean(np.abs(zz) > 3)), frac_gt4=float(np.mean(np.abs(zz) > 4)))
        for lag in ACF_LAGS:
            a, b = z[:-lag], z[lag:]
            m = ~np.isnan(a) & ~np.isnan(b)
            row[f"acf_lag{lag}"] = float(np.corrcoef(a[m], b[m])[0, 1]) if m.sum() >= MIN_ACF_PAIRS and \
                np.std(a[m]) > 0 and np.std(b[m]) > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def jump_events(ser, ids):
    """Code 3B screening on observed settled BT (no model involved)."""
    ev = []
    pair_rows = []
    for c in ids:
        y = ser[c]
        oi = np.where(~np.isnan(y))[0]
        if len(oi) < 2:
            continue
        gap = np.diff(oi)
        dv = np.diff(y[oi])
        ok = gap <= MAX_PAIR_GAP_MIN
        one = gap == 1
        pair_rows.append(dict(caseid=c, n_1min_pairs=int(one.sum()), n_1min_ge_jump=int((np.abs(dv[one]) >= JUMP_C).sum()),
                              abs_dy_1min=np.abs(dv[one])))
        at = oi[1:][ok & (np.abs(dv) >= JUMP_C)]
        if len(at) == 0:
            continue
        clusters, cur = [], [int(at[0])]
        for a_ in at[1:]:
            if a_ - cur[-1] <= EVENT_MERGE_MIN:
                cur.append(int(a_))
            else:
                clusters.append(cur)
                cur = [int(a_)]
        clusters.append(cur)
        for cl in clusters:
            t0, t1 = cl[0], cl[-1]
            pre_i = oi[(oi < t0) & (oi >= t0 - LOOKAROUND_MIN)][-PRE_POST_N:]
            post_i = oi[(oi > t1) & (oi <= t1 + LOOKAROUND_MIN)][:PRE_POST_N]
            pre = float(np.median(y[pre_i])) if len(pre_i) else np.nan
            post = float(np.median(y[post_i])) if len(post_i) else np.nan
            seg = y[t0:t1 + 1]
            seg = seg[~np.isnan(seg)]
            peak = float(seg[np.argmax(np.abs(seg - pre))] - pre) if len(seg) and np.isfinite(pre) else np.nan
            p10 = y[t1 + 9: t1 + 12]
            p10 = float(np.nanmedian(p10)) if np.any(~np.isnan(p10)) else np.nan
            tol = max(RETURN_TOL_C, RETURN_FRAC * abs(peak)) if np.isfinite(peak) else np.nan
            returned = bool(np.isfinite(p10) and np.isfinite(pre) and abs(p10 - pre) <= tol)
            persistent = bool(np.isfinite(p10) and np.isfinite(pre) and np.isfinite(peak)
                              and abs(p10 - pre) >= PERSIST_FRAC * abs(peak))
            supported = len(pre_i) >= MIN_SUPPORT and len(post_i) >= MIN_SUPPORT
            span = float(np.mean(post_i) - np.mean(pre_i)) if supported else np.nan
            net = post - pre
            sd_model = np.sqrt(Q_HAT * span + R_HAT * (1 / max(len(pre_i), 1) + 1 / max(len(post_i), 1))) if supported else np.nan
            ev.append(dict(caseid=c, start_min=t0, end_min=t1, duration_min=t1 - t0 + 1, n_jumps=len(cl),
                           pre_level_C=pre, post_level_C=post, net_change_C=net, peak_excursion_C=peak,
                           supported=supported, returned_by_plus10=returned, persistent_at_plus10=persistent,
                           pattern=("isolated_returning" if returned else ("persistent_shift" if persistent
                                    else ("undetermined" if not np.isfinite(p10) else "partial_return"))),
                           span_between_windows_min=span, model_sd_C=sd_model,
                           z_event=float(net / sd_model) if supported and sd_model > 0 else np.nan))
    return pd.DataFrame(ev), pair_rows


def jump_scale(pair_rows, label):
    allabs = np.concatenate([p["abs_dy_1min"] for p in pair_rows]) if pair_rows else np.array([])
    sd1 = np.sqrt(Q_HAT + 2 * R_HAT)        # 1-min change of y: eta + e_t - e_{t-1} (trend <= ~0.02 C/min ignored)
    model_rate = 2 * stats.norm.sf(JUMP_C / sd1)
    per_case = np.array([p["n_1min_ge_jump"] / p["n_1min_pairs"] for p in pair_rows if p["n_1min_pairs"] > 0])
    rows = []
    for pc in (50, 90, 95, 99, 99.9):
        rows.append(dict(set=label, percentile=pc, observed_abs_dy_1min_C=float(np.percentile(allabs, pc)),
                         model_abs_dy_1min_C=float(sd1 * stats.norm.ppf(0.5 + pc / 200))))
    rows.append(dict(set=label, percentile="max", observed_abs_dy_1min_C=float(allabs.max()),
                     model_abs_dy_1min_C=float(sd1 * stats.norm.ppf(1 - 0.5 / max(len(allabs), 1)))))
    return pd.DataFrame(rows), dict(model_sd_1min_C=float(sd1), model_rate_ge_jump=float(model_rate),
                                    observed_rate_pooled=float((allabs >= JUMP_C).mean()),
                                    observed_rate_case_weighted=float(per_case.mean()) if len(per_case) else np.nan,
                                    rate_ratio_case_weighted=float(per_case.mean() / model_rate) if model_rate > 0 else np.inf,
                                    n_1min_pairs=int(len(allabs)))


def metrics(Z, V, ids, ser, label):
    ps = pooled_summary(Z, V, label)
    cs = case_summaries(Z, ids)
    ev, pairs = jump_events(ser, ids)
    js, jr = jump_scale(pairs, label)
    sup = ev[ev.supported] if len(ev) else ev
    m = dict(set=label, n_cases=len(ids), **{f"median_acf_lag{l}": float(cs[f"acf_lag{l}"].median()) for l in ACF_LAGS},
             cases_with_acf=int(cs["acf_lag1"].notna().sum()),
             tail3_ratio_case_weighted=float(cs.frac_gt3.mean() / GAUSS_TAIL3),
             tail4_ratio_case_weighted=float(cs.frac_gt4.mean() / GAUSS_TAIL4),
             tail3_ratio_pooled=ps["frac_abs_z_gt3"] / GAUSS_TAIL3, tail4_ratio_pooled=ps["frac_abs_z_gt4"] / GAUSS_TAIL4,
             jump_rate_ratio=jr["rate_ratio_case_weighted"],
             n_events=int(len(ev)), n_supported_events=int(len(sup)),
             pct_cases_with_event=float(ev.caseid.nunique() / len(ids) * 100) if len(ev) else 0.0,
             events_per_case_mean=float(len(ev) / len(ids)),
             event_z4_share=float((sup.z_event.abs() > 4).mean()) if len(sup) else np.nan)
    return ps, cs, ev, js, jr, m


Vtr, Ftr, Ztr = innovations(Y_TR, TR_IDS, X_TR)
ps_tr, cs_tr, ev_tr, js_tr, jr_tr, m_tr = metrics(Ztr, Vtr, TR_IDS, SER_TR, "dev_train")
print("\nTask 3 (dev-train): z mean {:.3f}, sd {:.3f}, median {:.3f}, MAD {:.3f}; |z|>2 {:.4f}, >3 {:.4f}, >4 {:.5f}; "
      "skew {:.2f}, excess kurtosis {:.1f}".format(ps_tr["z_mean"], ps_tr["z_sd"], ps_tr["z_median"], ps_tr["z_mad"],
                                                   ps_tr["frac_abs_z_gt2"], ps_tr["frac_abs_z_gt3"], ps_tr["frac_abs_z_gt4"],
                                                   ps_tr["skewness"], ps_tr["excess_kurtosis"]))
print("  case-level median ACF: " + ", ".join(f"lag{l} {m_tr[f'median_acf_lag{l}']:+.3f}" for l in ACF_LAGS)
      + f"  ({m_tr['cases_with_acf']} cases with >= {MIN_ACF_PAIRS} pairs)")
print(f"Task 4 (dev-train): {m_tr['n_events']} candidate events ({m_tr['n_supported_events']} supported) in "
      f"{m_tr['pct_cases_with_event']:.1f}% of cases; mean {m_tr['events_per_case_mean']:.2f}/case")
print(f"Task 6 (dev-train): 1-min |dy| >= {JUMP_C} C: observed rate {jr_tr['observed_rate_case_weighted']:.2e} vs "
      f"model {jr_tr['model_rate_ge_jump']:.2e} (ratio {jr_tr['rate_ratio_case_weighted']:.1f}); "
      f"supported events with |z_event| > 4: {m_tr['event_z4_share']:.1%}")

# ============================================================================
# TASK 7 — DEV-VALIDATION (frozen parameters, no tuning)
# ============================================================================
print("\nTask 7: applying FROZEN dev-train parameters to dev-val ...")
SER_VA, BAD_VA = load(DVAL)
VA_IDS = sorted(SER_VA)
Y_VA = to_matrix(SER_VA, VA_IDS)
X_VA = np.array([xvec(c) for c in VA_IDS])
Vva, Fva, Zva = innovations(Y_VA, VA_IDS, X_VA)
ps_va, cs_va, ev_va, js_va, jr_va, m_va = metrics(Zva, Vva, VA_IDS, SER_VA, "dev_val")


# ============================================================================
# TASK 8 — PRE-SPECIFIED DECISION
# ============================================================================
def criteria(m):
    """Evaluate every A and B sub-criterion on one development set. A missing event share (no supported
    events) cannot violate an A criterion and cannot satisfy a B criterion."""
    ez = m["event_z4_share"]
    A = {"white": all(abs(m[f"median_acf_lag{l}"]) <= RULE["white_max_abs_median_acf"] for l in ACF_LAGS),
         "tail3": m["tail3_ratio_case_weighted"] <= RULE["A_tail3_ratio_max"],
         "tail4": m["tail4_ratio_case_weighted"] <= RULE["A_tail4_ratio_max"],
         "jump_rate": m["jump_rate_ratio"] <= RULE["A_jump_rate_ratio_max"],
         "event_z4": (not np.isfinite(ez)) or ez <= RULE["A_event_z4_share_max"]}
    B = {"tail4": m["tail4_ratio_case_weighted"] > RULE["B_tail4_ratio_min"],
         "jump_rate": m["jump_rate_ratio"] > RULE["B_jump_rate_ratio_min"],
         "event_z4": bool(np.isfinite(ez) and ez > RULE["B_event_z4_share_min"])}
    return A, B


# Stability = DECISION-RELEVANT agreement: dev-train and dev-val reach the same verdict on every A and B
# sub-criterion, and median ACFs differ by <= stable_acf_abs_diff. (Rate RATIOS between sets are not used:
# with rare events such as |z| > 4 the ratio of two tiny counts is noise — corrected on synthetic data
# BEFORE any real-data run.)
A_tr, B_tr = criteria(m_tr)
A_va, B_va = criteria(m_va)
checks = {**{f"A_{k}_train": v for k, v in A_tr.items()}, **{f"A_{k}_val": v for k, v in A_va.items()},
          **{f"B_{k}_train": v for k, v in B_tr.items()}, **{f"B_{k}_val": v for k, v in B_va.items()},
          "stable_A_verdicts": A_tr == A_va, "stable_B_verdicts": B_tr == B_va,
          "stable_acf": all(abs(m_tr[f"median_acf_lag{l}"] - m_va[f"median_acf_lag{l}"]) <= RULE["stable_acf_abs_diff"]
                            for l in ACF_LAGS)}
stable = checks["stable_A_verdicts"] and checks["stable_B_verdicts"] and checks["stable_acf"]
checks["A_interior_fit"] = interior_fit
A_ok = all(A_tr.values()) and interior_fit
B_ok = any(B_tr.values())
DECISION = "A" if (A_ok and stable) else ("B" if (B_ok and stable) else "C")

# ============================================================================
# TASK 9 — OUTPUTS
# ============================================================================
pd.DataFrame([ps_tr, ps_va]).to_csv(os.path.join(OUT_DIR, "innovation_pooled_summary.csv"), index=False)
pd.concat([cs_tr.assign(set="dev_train"), cs_va.assign(set="dev_val")]).to_csv(
    os.path.join(OUT_DIR, "innovation_case_summary_and_acf.csv"), index=False)
pd.concat([ev_tr.assign(set="dev_train"), ev_va.assign(set="dev_val")]).to_csv(
    os.path.join(OUT_DIR, "candidate_jump_events.csv"), index=False)
pd.concat([js_tr, js_va]).to_csv(os.path.join(OUT_DIR, "jump_scale_observed_vs_model.csv"), index=False)
pd.DataFrame([m_tr, m_va]).to_csv(os.path.join(OUT_DIR, "train_validation_comparison.csv"), index=False)
pd.DataFrame(cov_rows).to_csv(os.path.join(OUT_DIR, "static_covariates_used.csv"), index=False)

# figures (dev-train solid, dev-val dashed)
zt, zv = Ztr[~np.isnan(Ztr)], Zva[~np.isnan(Zva)]
xs = np.linspace(-8, 8, 400)
fig, ax = plt.subplots(1, 2, figsize=(12, 4))
for a_ in ax:
    a_.hist(np.clip(zt, -8, 8), bins=160, density=True, alpha=0.5, label="dev-train")
    a_.hist(np.clip(zv, -8, 8), bins=160, density=True, histtype="step", label="dev-val")
    a_.plot(xs, stats.norm.pdf(xs), "k", lw=1, label="N(0,1)")
ax[1].set_yscale("log")
ax[0].set(title="Standardised innovations (clipped at +/-8)", xlabel="z")
ax[1].set(title="Same, log density (tails)", xlabel="z")
ax[0].legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(FIG_DIR, "innovation_hist_vs_gaussian.png"), dpi=120); plt.close(fig)

qs = np.linspace(0.0005, 0.9995, 400)
fig, ax = plt.subplots(figsize=(5.5, 5.5))
ax.plot(stats.norm.ppf(qs), np.quantile(zt, qs), ".", ms=3, label="dev-train")
ax.plot(stats.norm.ppf(qs), np.quantile(zv, qs), ".", ms=3, label="dev-val")
lim = max(4, np.abs(np.quantile(zt, [0.0005, 0.9995])).max())
ax.plot([-lim, lim], [-lim, lim], "k:", lw=1)
ax.set(xlabel="N(0,1) quantile", ylabel="empirical z quantile", title="QQ plot (0.05%-99.95%)")
ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(FIG_DIR, "innovation_qq.png"), dpi=120); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 4))
ax.boxplot([cs_tr[f"acf_lag{l}"].dropna() for l in ACF_LAGS], positions=np.arange(4) - 0.15, widths=0.25, showfliers=False)
ax.boxplot([cs_va[f"acf_lag{l}"].dropna() for l in ACF_LAGS], positions=np.arange(4) + 0.15, widths=0.25, showfliers=False)
ax.axhline(0, color="k", lw=0.8)
for y_ in (RULE["white_max_abs_median_acf"], -RULE["white_max_abs_median_acf"]):
    ax.axhline(y_, color="r", ls=":", lw=0.8)
ax.set_xticks(range(4), [f"lag {l}" for l in ACF_LAGS])
ax.set(title="Within-case ACF of z (left dev-train, right dev-val)", ylabel="autocorrelation")
fig.tight_layout(); fig.savefig(os.path.join(FIG_DIR, "innovation_acf_summary.png"), dpi=120); plt.close(fig)

for col, fname, lab in (("net_change_C", "jump_magnitude_distribution.png", "net level change (C)"),
                        ("duration_min", "jump_duration_distribution.png", "event duration (min)")):
    fig, ax = plt.subplots(figsize=(7, 4))
    for d_, name in ((ev_tr, "dev-train"), (ev_va, "dev-val")):
        if len(d_):
            ax.hist(d_[col].dropna(), bins=60, alpha=0.5, label=name)
    if not (len(ev_tr) or len(ev_va)):
        ax.text(0.5, 0.5, "no candidate events", ha="center", transform=ax.transAxes)
    ax.set(xlabel=lab, ylabel="events", title=f"Candidate abrupt changes: {lab}")
    if len(ev_tr) or len(ev_va):
        ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG_DIR, fname), dpi=120); plt.close(fig)

fig, ax = plt.subplots(figsize=(7, 4))
d_ = js_tr[js_tr.percentile != "max"]
ax.plot(d_.percentile.astype(float), d_.observed_abs_dy_1min_C, "o-", label="observed |dy| (1 min)")
ax.plot(d_.percentile.astype(float), d_.model_abs_dy_1min_C, "s--", label="model-implied (q_hat, r_hat)")
ax.set(xlabel="percentile", ylabel="|change| in 1 min (C)", yscale="log", title="Observed vs model-implied 1-min change scale (dev-train)")
ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(FIG_DIR, "observed_vs_model_jump_scale.png"), dpi=120); plt.close(fig)

# ---- protection re-check ----
HASH_AFTER = {**hash_tree(CODE4_DIR), **hash_tree(FREEZE_DIR)}
protect.update({"protected_files_unchanged": HASH_BEFORE == HASH_AFTER,
                "no_final_holdout_case_loaded": not (LOADED_CASES & final_ids)})
PROTECTED = all(protect.values())
STUDY_OK = fit_converged and len(VA_IDS) > 0 and m_tr["cases_with_acf"] > 0

result = dict(created_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
              dev_split_seed=DEV_SPLIT_SEED, n_dev_train=len(TR_IDS), n_dev_val=len(VA_IDS),
              unusable_dev_train=len(BAD_TR), unusable_dev_val=len(BAD_VA),
              gamma_hat=G_HAT, q_hat=Q_HAT, r_hat=R_HAT, S_hat=S_HAT.tolist(), B_hat=B_HAT.tolist(),
              static_columns=STATIC_COLS, implied_rw_sd_C=rw_sd, optimiser_success=bool(best.success),
              optimiser_message=str(best.message), params_at_bound=at_bound, nll=float(best.fun),
              nll_spread_across_starts=float(start_spread),
              metrics_dev_train=m_tr, metrics_dev_val=m_va, jump_scale_dev_train=jr_tr, jump_scale_dev_val=jr_va,
              decision_rule=RULE, decision_checks=checks, A_conditions_met=bool(A_ok), B_conditions_met=bool(B_ok),
              stable=bool(stable), MODEL_DECISION=DECISION, protection=protect,
              FINAL_HOLDOUT_PROTECTED="PASS" if PROTECTED else "FAIL",
              DEVELOPMENT_ADEQUACY_STUDY="PASS" if STUDY_OK else "FAIL")
json.dump(result, open(os.path.join(OUT_DIR, "adequacy_results.json"), "w"), indent=2, default=float)


def f(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}g}"


md = f"""# Development-only model adequacy report

Created {result['created_utc']}. Development cases only; final holdout ({len(final_ids)} cases) never loaded.

## Task 1 — split
Development {len(dev_ids)} cases -> dev-train {len(DTRAIN)} / dev-val {len(DVAL)} (seed {DEV_SPLIT_SEED}, 75/25, case level).
Usable (>= 2 settled observations): dev-train {len(TR_IDS)}, dev-val {len(VA_IDS)}.

## Task 2 — fitted Gaussian random-walk model (dev-train only)
gamma_hat {G_HAT:.4f}/min; q_hat {Q_HAT:.3e} C^2/min; r_hat {R_HAT:.3e} C^2 (sd {np.sqrt(R_HAT):.3f} C).
Implied random-walk SD: {', '.join(f'{k} {v:.3f} C' for k, v in rw_sd.items())}.
S_hat {np.round(S_HAT, 4).tolist()}. Optimiser success {best.success}; parameters at bounds {at_bound};
nll spread across 3 starts {start_spread:.2f}.
{"**WARNING: parameter(s) " + str(at_bound) + " at an optimisation bound (index 0 gamma, 1 q, 2 r, 3-5 Cholesky of S). A boundary fit blocks decision A.**" if at_bound else "Interior optimum (no parameter at a bound)."}

## Tasks 3-7 — diagnostics

| Metric | dev-train | dev-val | Gaussian reference |
|---|---|---|---|
| z mean / sd | {f(ps_tr['z_mean'])} / {f(ps_tr['z_sd'])} | {f(ps_va['z_mean'])} / {f(ps_va['z_sd'])} | 0 / 1 |
| z median / MAD | {f(ps_tr['z_median'])} / {f(ps_tr['z_mad'])} | {f(ps_va['z_median'])} / {f(ps_va['z_mad'])} | 0 / 1 |
| fraction abs z > 2 / > 3 / > 4 (pooled) | {f(ps_tr['frac_abs_z_gt2'])} / {f(ps_tr['frac_abs_z_gt3'])} / {f(ps_tr['frac_abs_z_gt4'])} | {f(ps_va['frac_abs_z_gt2'])} / {f(ps_va['frac_abs_z_gt3'])} / {f(ps_va['frac_abs_z_gt4'])} | 0.0455 / 0.0027 / 6.3e-5 |
| skewness / excess kurtosis | {f(ps_tr['skewness'])} / {f(ps_tr['excess_kurtosis'])} | {f(ps_va['skewness'])} / {f(ps_va['excess_kurtosis'])} | 0 / 0 |
| median within-case ACF lag 1/2/5/10 | {' / '.join(f(m_tr[f'median_acf_lag{l}']) for l in ACF_LAGS)} | {' / '.join(f(m_va[f'median_acf_lag{l}']) for l in ACF_LAGS)} | 0 |
| tail ratio abs z > 3 (case-weighted) | {f(m_tr['tail3_ratio_case_weighted'])} | {f(m_va['tail3_ratio_case_weighted'])} | 1 |
| tail ratio abs z > 4 (case-weighted) | {f(m_tr['tail4_ratio_case_weighted'])} | {f(m_va['tail4_ratio_case_weighted'])} | 1 |
| % cases with candidate event | {f(m_tr['pct_cases_with_event'])} | {f(m_va['pct_cases_with_event'])} | — |
| 1-min change >= {JUMP_C} C: observed / model rate | {f(jr_tr['observed_rate_case_weighted'])} / {f(jr_tr['model_rate_ge_jump'])} | {f(jr_va['observed_rate_case_weighted'])} / {f(jr_va['model_rate_ge_jump'])} | ratio 1 |
| supported events with abs z_event > 4 | {f(m_tr['event_z4_share'])} | {f(m_va['event_z4_share'])} | ~0 |

## Task 8 — decision (rule pre-specified before any real-data run)
A requires: an interior optimum, whiteness (abs median ACF <= {RULE['white_max_abs_median_acf']} at lags 1,2,5,10), tail3 ratio <= {RULE['A_tail3_ratio_max']},
tail4 ratio <= {RULE['A_tail4_ratio_max']}, jump-rate ratio <= {RULE['A_jump_rate_ratio_max']}, event z>4 share <= {RULE['A_event_z4_share_max']}, and train/val stability.
B requires: tail4 ratio > {RULE['B_tail4_ratio_min']} OR jump-rate ratio > {RULE['B_jump_rate_ratio_min']} OR event z>4 share > {RULE['B_event_z4_share_min']}, and stability.
Stability: dev-train and dev-val give the same verdict on every A and B sub-criterion and median ACFs\ndiffer by <= {RULE['stable_acf_abs_diff']}. Otherwise C. Checks: {checks}. A conditions met: {A_ok}; B conditions met: {B_ok}; stable: {stable}.

- OBSERVED DATA: the table above (innovations, abrupt-change frequency and size, train vs validation).
- MODEL-BASED INFERENCE: z_event and the model rate assume the fitted Gaussian random walk; trend contribution over
  1 minute is ignored; medians of 5 observations are treated as means for the z_event variance.
- LIMITATION: minute medians are quantised (~0.1 C); pooled counts are dominated by long cases (case-weighted metrics
  are used for the decision); abrupt changes are not labelled artifacts; no forecasting performance was used.

FINAL_HOLDOUT_PROTECTED: {result['FINAL_HOLDOUT_PROTECTED']}
DEVELOPMENT_ADEQUACY_STUDY: {result['DEVELOPMENT_ADEQUACY_STUDY']}
MODEL_DECISION: {DECISION}
"""
open(os.path.join(OUT_DIR, "development_model_adequacy_report.md"), "w").write(md)

print("\nTask 7 (dev-val): " + ", ".join(f"{k} {m_va[k]:.3g}" for k in
      ("tail3_ratio_case_weighted", "tail4_ratio_case_weighted", "jump_rate_ratio", "event_z4_share", "median_acf_lag1")))
print(f"Task 8 checks: {checks}")
print(f"  A conditions {A_ok}; B conditions {B_ok}; stable {stable}")
print(f"\nOutputs in {os.path.abspath(OUT_DIR)}")
print(f"\nFINAL_HOLDOUT_PROTECTED: {result['FINAL_HOLDOUT_PROTECTED']}")
print(f"DEVELOPMENT_ADEQUACY_STUDY: {result['DEVELOPMENT_ADEQUACY_STUDY']}")
print(f"MODEL_DECISION: {DECISION}")
