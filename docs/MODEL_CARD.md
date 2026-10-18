# Model card — NERAM thermal twin (owner: Sai)

## Intended use
A research prototype that estimates the current level of an intraoperative **patient temperature signal**
(anatomical site not established) from that patient's own minute-by-minute readings. It forecasts the signal at
+20, +30 and +60 min with uncertainty, and flags minutes that look like an artefact or a level shift. It is
meant for a simulated, clinician-supervised decision-support demonstration.

## Not intended for
Treatment decisions, autonomous warming, hypothermia prevention claims, or use as a core-temperature estimate.
It has no clinical validation, no regulatory status and no validated real-data performance.

## Model
`src/thermal_robust_core.py` (canonical, SHA-256 de9c6c6378301ddd6e9378cfd3d5671a97fc68cc79a190a978033aa4161ad2c5).

* State: z_t = [α, β, u_t]. Trend basis φ_t = [e^(−γt) − 1, t/60]. Observation y_t = [φ_t, 1]·z_t + e_t.
* Level innovations: a two-component mixture (calm q, jump q_J, probability π_u).
* Observation noise: a two-component mixture (normal r, outlier r_O, probability π_e).
* Prior: θ = [α, β] ~ N(m0, S).
* Inference: GPB2 Gaussian-sum filter. Forecasts are exact functionals of the retained 4-component mixture
  convolved with the future-jump-count and outlier mixtures.

## Exported fields
Produced by `src/twin_replay_export.py`, per minute:

* T_est, T_est_sd: the filtered, noise-free signal.
* T_pred and the 80 % / 95 % bounds at +20, +30 and +60 min, for the next **observation**.
* P_below_hypo_h: from the same predictive mixture as the bounds.
* P_level_shift and P_outlier: filtered, real-time mode probabilities.
* Twin_Valid.

The offline fixed-lag attribution is never exported in real-time fields.

## Parameters
* **Real data: none.** The development fit failed (`docs/RESULTS.md` §2). The export refuses DEVELOPMENT
  cohorts until fitted parameters with a pre-registered dev_robust_03 decision exist.
* **Synthetic: ASSUMED_SYNTHETIC** (`config/model_params_synthetic.json`). The Gaussian part is copied from the
  core's self-test; the mixture part is illustrative. These values are not estimates.

## Evaluation
Tests: `tests/test_p_below_hypo_mc.py`, `tests/test_twin_export.py`, `tests/test_interface.py`.
Synthetic implementation checks only (`docs/RESULTS.md` §3): closed-form Gaussian limit, Monte Carlo agreement
of P_below_hypo, no future leakage, Twin_Valid rule and reproducibility.

## Known limitations
* The data are quantised to 0.1 °C. The model's continuous noise term is degenerate on such data without the
  pending rounding-variance correction C2.
* α, β and γ are only partly identifiable. The model does not identify redistribution physiology.
* It cannot tell a probe disconnection from a real level shift in real time. The terminal 30 minutes are
  excluded from learning and reported as a separate stratum.
* Forecasts assume no intervention. VitalDB records no warming, so warming effects cannot be learned.
* Thresholds are TBD and not clinically validated. The export reads them from `config/params.json` (t_hypo 36.0 placeholder, sd_degrade 0.25 placeholder). Twin_Valid needs T_est_sd < sd_degrade (strict), tau >= 20 min and >= 10 of the last 15 minutes observed (plan 4A).
