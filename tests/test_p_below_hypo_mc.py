"""Plan section 4A / section 7: Monte Carlo test of P_below_hypo, plus the checks that P_below_hypo and the 80/95 %
bounds come from the same retained-mixture forecast.  Run: python -m pytest -q tests  or  python tests/test_p_below_hypo_mc.py
Requires numpy and scipy (environment.yml)."""
import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import thermal_robust_core as core  # noqa: E402
import twin_replay_export as tre  # noqa: E402

PARAMS = ROOT / "config" / "model_params_synthetic.json"
CONFIG = ROOT / "config" / "twin_export_config.json"


def _setup(obs_name="obs_SYN_02.csv"):
    p, gamma, m0, S, _ = tre.load_model_params(PARAMS, "SYNTHETIC")
    cfg, _ = tre.load_config(CONFIG)
    t, y = tre.read_obs(ROOT / "integration" / "synthetic" / "observations" / obs_name)
    return p, gamma, m0, S, cfg, t, y


def _origin_mixture(y, p, gamma, m0, S, o):
    out = core.gpb2_filter(y[None, :o + 1], p, m0[None], S, gamma)
    return out["LW"], out["Z"], out["PP"]


def test_p_below_hypo_monte_carlo():
    """Sample the model directly (retained mixture -> state, iid future jumps, outlier noise) and compare the
    empirical P(y_{o+h} < x) and the mean/variance with the analytic export. A Gaussian approximation of the same
    forecast differs by about 0.011 at +60 min here, which is well outside the 5-SE tolerance, so this test
    distinguishes the mixture from a moment-matched Gaussian."""
    p, gamma, m0, S, cfg, t, y = _setup()
    o = 40
    LW, Z, PP = _origin_mixture(y, p, gamma, m0, S, o)
    rg = np.random.default_rng(7)
    n = 200_000
    w = np.exp(LW[0] - np.logaddexp.reduce(LW[0]))
    for h in (20, 30, 60):
        comp = rg.choice(4, n, p=w)
        z = np.empty((n, 3))
        for k in range(4):
            idx = comp == k
            z[idx] = rg.multivariate_normal(Z[0, k], PP[0, k], idx.sum())
        hh = core.Hrow(float(o + h), gamma)
        jumps = rg.binomial(h, p["pi_u"], n)
        eta = rg.normal(0, 1, n) * np.sqrt((h - jumps) * p["q"] + jumps * p["q_J"])
        out = rg.random(n) < p["pi_e"]
        e = rg.normal(0, 1, n) * np.sqrt(np.where(out, p["r_O"], p["r"]))
        ys = z @ hh + eta + e
        m, v, wf, cm, cb = core.forecast_moments(LW, Z, PP, np.array([o]), h, p, gamma)
        assert abs(ys.mean() - m[0]) < 4 * np.sqrt(v[0] / n)
        assert abs(ys.var() / v[0] - 1) < 0.03
        for x in (cfg["t_hypo_degC"], m[0] - 0.2, m[0], m[0] + 0.2):
            emp = (ys < x).mean()
            ana = tre.mixture_cdf(wf, cm, cb, h, p, np.array([x]))[0]
            se = np.sqrt(max(ana * (1 - ana), 1e-6) / n)
            assert abs(emp - ana) < 5 * se + 1e-4, (h, x, emp, ana)


def test_cdf_matches_exported_intervals():
    """CDF(L80)=0.10, CDF(U80)=0.90, CDF(L95)=0.025, CDF(U95)=0.975 and CDF(t_hypo)=P_below_hypo for exported rows."""
    p, gamma, m0, S, cfg, t, y = _setup()
    rows, _ = tre.export(t, y, p, gamma, m0, S, cfg)
    for o in (25, 45, 80):
        assert rows[o]["Twin_Valid"] == tre.TV["VALID"]
        LW, Z, PP = _origin_mixture(y, p, gamma, m0, S, o)
        for h in tre.HORIZONS:
            _, _, w, cm, cb = core.forecast_moments(LW, Z, PP, np.array([o]), h, p, gamma)
            for col, q in (("L80", 0.10), ("U80", 0.90), ("L95", 0.025), ("U95", 0.975)):
                c = tre.mixture_cdf(w, cm, cb, h, p, np.array([rows[o][f"{col}_{h}"]]))[0]
                assert abs(c - q) < 2e-4, (o, h, col, c)
            c = tre.mixture_cdf(w, cm, cb, h, p, np.array([cfg["t_hypo_degC"]]))[0]
            assert abs(c - rows[o][f"P_below_hypo_{h}"]) < 1e-6


def test_gaussian_limit_cdf_is_normal():
    p, gamma, m0, S, cfg, t, y = _setup()
    pg = dict(p, pi_u=0.0, pi_e=0.0)
    LW, Z, PP = _origin_mixture(y, pg, gamma, m0, S, 50)
    m, v, w, cm, cb = core.forecast_moments(LW, Z, PP, np.array([50]), 30, pg, gamma)
    assert abs(tre.mixture_cdf(w, cm, cb, 30, pg, np.array([36.0]))[0] - stats.norm.cdf((36.0 - m[0]) / np.sqrt(v[0]))) < 1e-9


def test_probabilities_bounded_and_monotone_in_threshold():
    p, gamma, m0, S, cfg, t, y = _setup()
    LW, Z, PP = _origin_mixture(y, p, gamma, m0, S, 40)
    _, _, w, cm, cb = core.forecast_moments(LW, Z, PP, np.array([40]), 30, p, gamma)
    xs = np.linspace(30, 42, 61)
    c = np.array([tre.mixture_cdf(w, cm, cb, 30, p, np.array([x]))[0] for x in xs])
    assert (c >= 0).all() and (c <= 1).all() and (np.diff(c) >= -1e-12).all()


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as ex:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(ex)[:400])
    sys.exit(1 if fails else 0)
