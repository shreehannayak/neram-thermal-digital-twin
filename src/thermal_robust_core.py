"""
thermal_robust_core.py

Shared, verified implementation of the combined robust thermal state-space model. Imported by
  robust_statespace_verification.py   (synthetic verification)
  recovery_resume.py                  (synthetic parameter recovery)
  dev_robust_02_fit_and_validate.py   (real-data development fit)
so the code verified on synthetic data is exactly the code used on real data.

There are NO module-level model constants: gamma, m0 and S are always explicit arguments, so synthetic
truth cannot leak into a real-data run.

MODEL
  t        minutes since settled start
  phi_t    [exp(-gamma t) - 1, t/60]';   H_t = [phi_t', 1]
  state    z_t = [alpha, beta, u_t]',  z_t = z_{t-1} + [0, 0, eta_t]'
  level    eta_t | j_t ~ N(0, q_{j_t}),  q_0 = q, q_1 = q_J,  j_t ~ Bernoulli(pi_u), iid over t
  observe  y_t = H_t z_t + e_t,  e_t | o_t ~ N(0, r_{o_t}),  r_0 = r, r_1 = r_O,  o_t ~ Bernoulli(pi_e), iid
  prior    theta = [alpha, beta]' ~ N(m0, S)
  level    exact diffuse at the first observed minute (absolute level carried by u; no T0)

INFERENCE: hypothesis-conditioned Gaussian-sum filter = GPB2 for an iid-switching system.
  The four "modes" are the (j_t, o_t) pairs. GPB2 (Bar-Shalom) keeps one Gaussian per CURRENT mode;
  each minute every retained Gaussian is propagated under each new mode (4 x 4 candidates) and the
  candidates sharing the same new mode are merged by moment matching. With iid switching the mode
  transition probabilities do not depend on the previous mode, which is a special case of standard GPB2.
  EXACT   : each conditional Kalman update; each candidate weight given the retained mixture;
            the first-observation diffuse initialisation (both outlier states kept).
  APPROX  : (1) merging candidates that share the newest mode (loses older mode history);
            (2) a missing minute adds the marginal level variance q_bar to every component and keeps
                the component labels of the last observed minute;
            (3) the likelihood is the product of one-step predictive mixture densities computed from
                the approximate retained mixture.
  FORECAST: mean and variance are exact functionals of the retained 4-component mixture; the
            predictive distribution is that mixture convolved with the exact future-jump-count mixture
            (Binomial(h, pi_u), truncated at k_max with the truncated mass reported) and the outlier mixture.
"""

import numpy as np
from scipy import stats
from scipy.special import expit, logit, logsumexp

LOG2PI = np.log(2 * np.pi)
I3 = np.eye(3)
HYP_J = (0, 0, 1, 1)
HYP_O = (0, 1, 0, 1)
HYP_NAMES = ("calm", "outlier", "jump", "jump+outlier")


def phi(t, gamma):
    t = np.asarray(t, float)
    return np.stack([np.exp(-gamma * t) - 1.0, t / 60.0], axis=-1)


def Hrow(t, gamma):
    p = phi(t, gamma)
    return np.concatenate([p, np.ones(np.shape(p)[:-1] + (1,))], axis=-1)


def mix_moments(p):
    return ((1 - p["pi_u"]) * p["q"] + p["pi_u"] * p["q_J"], (1 - p["pi_e"]) * p["r"] + p["pi_e"] * p["r_O"])


def _log(x):
    with np.errstate(divide="ignore"):
        return np.log(x)


def _merge_by_mode(cl, cz, cP):
    """cl (n, 4 modes, 4 comps); merge comps within each mode by moment matching -> (n, 4)."""
    glse = logsumexp(cl, axis=2)
    fin = np.isfinite(glse)
    w = np.where(fin[:, :, None], np.exp(cl - np.where(fin, glse, 0.0)[:, :, None]), 0.0)
    mz = np.einsum("ngk,ngki->ngi", w, cz)
    dz = cz - mz[:, :, None, :]
    mP = np.einsum("ngk,ngkij->ngij", w, cP + np.einsum("ngki,ngkj->ngkij", dz, dz))
    mP = np.where(fin[:, :, None, None], mP, I3)
    return glse, mz, mP


def gpb2_filter(Y, p, M0, S, gamma, store_probs=False, origin_mask=None, store_states=False, force_t=None, force_k=None):
    """Run the robust filter over N cases at once.
    Y (N, L) minute series, NaN = missing.  p dict(q, r, pi_u, q_J, pi_e, r_O).  M0 (N, 2) prior means.
    S (2, 2) prior covariance.  origin_mask (N, L) bool: record the filtered mixture AFTER the update at t.
    Returns ll (N) approximate log-likelihood, nupd, final mixture + collapsed moments, optional
    per-minute mode probabilities and per-minute collapsed states, and origin states.
    force_t (N,) int / force_k (N,) int: OFFLINE ATTRIBUTION ONLY. At minute force_t[i] case i is restricted to
    mode force_k[i]; ll then equals the log joint density of (data, mode at force_t). Never used for forecasting."""
    N, L = Y.shape
    obs = ~np.isnan(Y)
    qs, rs = np.array([p["q"], p["q_J"]]), np.array([p["r"], p["r_O"]])
    lpj, lpo = _log(np.array([1 - p["pi_u"], p["pi_u"]])), _log(np.array([1 - p["pi_e"], p["pi_e"]]))
    qbar, _ = mix_moments(p)
    LW = np.full((N, 4), -np.inf)
    Z = np.zeros((N, 4, 3))
    PP = np.tile(I3, (N, 4, 1, 1))
    started = np.zeros(N, bool)
    ll, nupd = np.zeros(N), np.zeros(N, int)
    PROB = {k: np.full((N, L), np.nan) for k in ("calm", "jump", "outlier")} if store_probs else None
    ST_Z = np.full((N, L, 3), np.nan) if store_states else None
    ST_P = np.full((N, L, 3, 3), np.nan) if store_states else None
    orig = dict(case=[], t=[], LW=[], Z=[], PP=[])
    for t in range(L):
        ph = np.array([np.exp(-gamma * t) - 1.0, t / 60.0])
        h = np.array([ph[0], ph[1], 1.0])
        o = obs[:, t]
        miss = started & ~o
        if miss.any():
            PP[miss, :, 2, 2] += qbar
        new = o & ~started
        if new.any():
            n_ = int(new.sum())
            Zi = np.zeros((n_, 4, 3)); Pn = np.tile(I3, (n_, 4, 1, 1)); Ln = np.full((n_, 4), -np.inf)
            for k, ro in enumerate((p["r"], p["r_O"])):
                Zi[:, k, :2] = M0[new]
                Zi[:, k, 2] = Y[new, t] - M0[new] @ ph
                Pk = np.zeros((3, 3)); Pk[:2, :2] = S; Pk[:2, 2] = Pk[2, :2] = -S @ ph; Pk[2, 2] = ph @ S @ ph + ro
                Pn[:, k] = Pk
                Ln[:, k] = lpo[k]
            LW[new], Z[new], PP[new] = Ln, Zi, Pn
            started |= new
        upd = o & started & ~new
        if upd.any():
            lw0, Z0, P0 = LW[upd], Z[upd], PP[upd]
            v = Y[upd, t][:, None] - Z0 @ h
            Phb = P0 @ h
            hPh = Phb @ h
            cl, cz, cP = [], [], []
            for k in range(4):
                qj, ro = qs[HYP_J[k]], rs[HYP_O[k]]
                Pj = P0.copy(); Pj[:, :, 2, 2] += qj
                Pjh = Phb.copy(); Pjh[:, :, 2] += qj
                Fv = hPh + qj + ro
                Kg = Pjh / Fv[:, :, None]
                IKH = I3[None, None] - np.einsum("nki,j->nkij", Kg, h)
                cz.append(Z0 + Kg * v[:, :, None])
                cP.append(np.einsum("nkij,nkjl,nkml->nkim", IKH, Pj, IKH) + ro * np.einsum("nki,nkj->nkij", Kg, Kg))
                with np.errstate(invalid="ignore"):
                    cl.append(lw0 + lpj[HYP_J[k]] + lpo[HYP_O[k]] - 0.5 * (LOG2PI + np.log(Fv) + v * v / Fv))
            cl = np.stack(cl, 1); cz = np.stack(cz, 1); cP = np.stack(cP, 1)       # (n, 4 modes, 4 comps, ...)
            cl = np.where(np.isnan(cl), -np.inf, cl)
            if force_t is not None:
                hit = force_t[upd] == t
                if hit.any():
                    keep = np.ones((len(cl), 4), bool)
                    keep[hit] = False
                    keep[np.where(hit)[0], force_k[upd][hit]] = True
                    cl = np.where(keep[:, :, None], cl, -np.inf)
            lse = logsumexp(cl.reshape(len(cl), -1), axis=1)
            cl = cl - lse[:, None, None]
            ll[upd] += lse
            nupd[upd] += 1
            glw, gz, gP = _merge_by_mode(cl, cz, cP)
            LW[upd], Z[upd], PP[upd] = glw, gz, gP
            if store_probs:
                wm = np.exp(glw)
                PROB["calm"][upd, t] = wm[:, 0]
                PROB["outlier"][upd, t] = wm[:, 1] + wm[:, 3]
                PROB["jump"][upd, t] = wm[:, 2] + wm[:, 3]
        if store_states:
            act = started
            if act.any():
                zc, Pc = collapse(LW[act], Z[act], PP[act])
                ST_Z[act, t], ST_P[act, t] = zc, Pc
        if origin_mask is not None:
            om = origin_mask[:, t] & started
            if om.any():
                idx = np.where(om)[0]
                orig["case"].append(idx); orig["t"].append(np.full(len(idx), t))
                orig["LW"].append(LW[idx].copy()); orig["Z"].append(Z[idx].copy()); orig["PP"].append(PP[idx].copy())
    zc, Pc = collapse(LW, Z, PP)
    out = dict(ll=ll, nupd=nupd, LW=LW, Z=Z, PP=PP, z=zc, P=Pc, prob=PROB, st_z=ST_Z, st_P=ST_P)
    if origin_mask is not None:
        out["origins"] = {k: (np.concatenate(v) if v else np.zeros(0)) for k, v in orig.items()}
    return out


def fixed_lag_mode_posterior(Y, t_event, lag, p, M0, S, gamma):
    """OFFLINE fixed-lag attribution. Rows of Y are series; t_event (n,) the event minute. Data after
    t_event + lag are removed. Returns P(mode at t_event | y_1..t_event+lag) for the four modes, computed from
    four mode-forced runs of the filter (approximate: GPB2 merging), plus the log-sum-exp consistency gap
    |logsumexp_k ll_k - ll_unforced| (zero for an exact filter)."""
    Yc = Y.copy()
    for i, te in enumerate(t_event):
        Yc[i, te + lag + 1:] = np.nan
    t_event = np.asarray(t_event, int)
    lls = np.stack([gpb2_filter(Yc, p, M0, S, gamma, force_t=t_event, force_k=np.full(len(Yc), k))["ll"]
                    for k in range(4)], 1)
    free = gpb2_filter(Yc, p, M0, S, gamma)["ll"]
    post = np.exp(lls - logsumexp(lls, axis=1)[:, None])
    return post, np.abs(logsumexp(lls, axis=1) - free)


def collapse(LW, Z, PP):
    """Exact first two moments of a Gaussian mixture (rows = cases)."""
    w = np.exp(LW - logsumexp(LW, axis=1)[:, None])
    zc = np.einsum("nk,nki->ni", w, Z)
    dz = Z - zc[:, None, :]
    return zc, np.einsum("nk,nkij->nij", w, PP + np.einsum("nki,nkj->nkij", dz, dz))


def forecast_moments(LW, Z, PP, o, h, p, gamma):
    """Vectorised over origins. LW (n,4), Z (n,4,3), PP (n,4,3,3), o (n,). Returns mean, var, and
    per-component means/base variances for interval computation."""
    hh = Hrow(np.asarray(o, float) + h, gamma)                      # (n, 3)
    w = np.exp(LW - logsumexp(LW, axis=1)[:, None])
    cm = np.einsum("nki,ni->nk", Z, hh)
    cb = np.einsum("ni,nkij,nj->nk", hh, PP, hh)
    qbar, rbar = mix_moments(p)
    m = (w * cm).sum(1)
    v = (w * (cb + (cm - m[:, None]) ** 2)).sum(1) + h * qbar + rbar
    return m, v, w, cm, cb


def kmax_for(h, pi_u, tail=1e-6):
    return int(stats.binom.ppf(1 - tail, h, pi_u)) + 1 if pi_u > 0 else 0


def mixture_intervals(w, cm, cb, h, p, levels=(0.5, 0.8, 0.95), iters=60):
    """Central intervals of the predictive mixture by vectorised bisection.
    Components: retained state components x future jump count k ~ Binomial(h, pi_u) (k <= k_max)
    x observation outlier state. Returns {level: (lo, hi)} and the truncated binomial mass."""
    km = kmax_for(h, p["pi_u"])
    k = np.arange(km + 1)
    bk = stats.binom.pmf(k, h, p["pi_u"])
    trunc = float(1 - bk.sum())
    bk = bk / bk.sum()
    po = np.array([1 - p["pi_e"], p["pi_e"]])
    ro = np.array([p["r"], p["r_O"]])
    W = (w[:, :, None, None] * bk[None, None, :, None] * po[None, None, None, :])          # (n,4,K,2)
    M = np.broadcast_to(cm[:, :, None, None], W.shape)
    SD = np.sqrt(cb[:, :, None, None] + (h - k)[None, None, :, None] * p["q"]
                 + k[None, None, :, None] * p["q_J"] + ro[None, None, None, :])
    n = len(w)
    W, M, SD = W.reshape(n, -1), M.reshape(n, -1), SD.reshape(n, -1)
    span = 10 * np.sqrt((W * (SD ** 2 + M ** 2)).sum(1) - (W * M).sum(1) ** 2) + 1.0
    centre = (W * M).sum(1)

    def quantile(qv):
        lo, hi = centre - span, centre + span
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            c = (W * stats.norm.cdf((mid[:, None] - M) / SD)).sum(1)
            lo, hi = np.where(c < qv, mid, lo), np.where(c < qv, hi, mid)
        return 0.5 * (lo + hi)

    out = {lv: (quantile(0.5 - lv / 2), quantile(0.5 + lv / 2)) for lv in levels}
    return out, trunc


# ---------------- parameter vector (identifiability constraints built in) ----------------
# x = [log gamma, log q, log r, logit pi_u, log(q_J/q - 1), logit pi_e, log(r_O/r - 1)]
# q_J > q and r_O > r always (prevents calm/jump and normal/outlier label switching);
# pi bounded <= 0.5 through the bounds below.
X_BOUNDS = [(np.log(0.002), np.log(0.2)), (np.log(1e-7), np.log(1.0)), (np.log(1e-7), np.log(1.0)),
            (-12.0, 0.0), (0.0, np.log(1e6)), (-12.0, 0.0), (0.0, np.log(1e6))]
X_NAMES = ["log_gamma", "log_q", "log_r", "logit_pi_u", "log_qJ_over_q_minus_1", "logit_pi_e", "log_rO_over_r_minus_1"]


def unpack(x):
    q, r = np.exp(x[1]), np.exp(x[2])
    return dict(gamma=float(np.exp(x[0])), q=float(q), r=float(r), pi_u=float(expit(x[3])),
                q_J=float(q * (1 + np.exp(x[4]))), pi_e=float(expit(x[5])), r_O=float(r * (1 + np.exp(x[6]))))


def pack(d):
    return np.array([np.log(d["gamma"]), np.log(d["q"]), np.log(d["r"]), logit(d["pi_u"]),
                     np.log(d["q_J"] / d["q"] - 1), logit(d["pi_e"]), np.log(d["r_O"] / d["r"] - 1)])


def near_bounds(x, tol=1e-3):
    return [X_NAMES[i] for i, (v, (lo, hi)) in enumerate(zip(x, X_BOUNDS)) if v - lo < tol or hi - v < tol]


# ---------------- self-test ----------------
if __name__ == "__main__":
    rg = np.random.default_rng(0)
    g, m0, S = 0.03, np.array([0.3, 0.1]), np.array([[0.2, 0.02], [0.02, 0.05]])
    p = dict(q=4e-4, r=1e-3, pi_u=0.0, q_J=4e-4, pi_e=0.0, r_O=1e-3)
    t = np.arange(201.0)
    y = phi(t, g) @ m0 + 36.5 + np.cumsum(rg.normal(0, 0.02, 201)) + rg.normal(0, 0.03, 201)
    out = gpb2_filter(y[None, :181], p, m0[None], S, g)
    m, v, *_ = forecast_moments(out["LW"], out["Z"], out["PP"], np.array([180]), 20, p, g)
    X = phi(t[:181], g); one = np.ones(181)
    V = X @ S @ X.T + p["q"] * np.minimum.outer(t[:181], t[:181]) + p["r"] * np.eye(181); Vi = np.linalg.inv(V)
    xs = phi(200.0, g); c = X @ S @ xs + p["q"] * np.minimum(t[:181], 200.0); d = y[:181] - X @ m0
    a = one @ Vi @ one; uh = one @ Vi @ d / a
    am = xs @ m0 + uh + c @ Vi @ (d - one * uh)
    av = xs @ S @ xs + p["q"] * 200 + p["r"] - c @ Vi @ c + (1 - one @ Vi @ c) ** 2 / a
    print(f"Gaussian-limit self-test: |mean err| {abs(m[0] - am):.1e}, |var err| {abs(v[0] - av):.1e} ->",
          "PASS" if abs(m[0] - am) < 1e-9 and abs(v[0] - av) < 1e-9 else "FAIL")
    x = pack(dict(gamma=0.03, q=1e-4, r=1e-3, pi_u=0.01, q_J=1.0, pi_e=0.01, r_O=2.0))
    print("pack/unpack round trip:", np.allclose(pack(unpack(x)), x))
