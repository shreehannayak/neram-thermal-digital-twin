# Safety and limitations (owner: Sai; enforced in the README by Shreehan)

NERAM is a **proof-of-concept**. Every display, slide, replay and video must stay consistent with this page.

1. **Signal.** The input is a "patient temperature signal" whose anatomical measurement site has not been
   established. It is **not** called or treated as core temperature.
2. **Model status.** The real-data development fit has not succeeded. No real-data forecasting accuracy or
   calibration is claimed. The demonstrations use SYNTHETIC observations, and the twin runs with ASSUMED
   parameters.
3. **Warming response.** VitalDB contains no warming-device data. Any warming effect is an **ASSUMED, SIMULATED
   prototype response** (`src/assumed_warming.py`, plan section 4E). It is shown with a 0.5× / 1× / 2×
   sensitivity grid and is never presented as a measured or predicted treatment effect.
4. **Controller.** The supervisory controller is simulated and clinician-supervised. NERAM does not provide
   autonomous treatment and makes no claim of preventing hypothermia or of clinical efficacy.
5. **Hardware.** No hardware has been built. All module, current and cutoff signals are simulated test-bench
   values. Thresholds such as the module surface limit and the hardware cutoff are TBD (owner Shreehan); none is
   invented.
6. **Placeholders.** t_hypo 36.0 °C is the core-temperature convention used only as a labelled placeholder.
   t_target, sd_degrade and the controller tunings are placeholders where shown. Each is marked TBD,
   PROVISIONAL or ASSUMED, with its source.
7. **No clinical validation, certification or standards compliance** is claimed. "Medical-grade" is not used.
8. **Holdout.** The final holdout is never shown, plotted or used in any demo, replay, controller test or video.
9. **Known controller-log issues** (17 Oct): none of the supplied controller logs commands any heating. Two show
   warming states with zero heat, followed by "target reached" with no target defined
   (`docs/SCENARIO_TRUTH_TABLE.md`). Those logs are excluded from the demo.

Persistent footer (viewer and video):
"Proof-of-concept. SIMULATED / ASSUMED PROTOTYPE RESPONSE where marked."
