# Summit demo script (≈ 6 minutes) — Unity replay viewer

**Before the demo:** replace the `SYN_SCN_*` placeholders with team-built `SCN_A–D` where available (REPLAY_INTEGRATION.md). If a SYN_ replay is shown, the amber "SYNTHETIC PLACEHOLDER DATA" mark is on screen and must be said out loud. Press **P** for presentation mode.

**Say:** "patient temperature signal", "estimate", "forecast", "simulated controller", "assumed warming response", "clinician-supervised prototype".
**Never say:** core temperature, prevents hypothermia, autonomous, clinically validated, medical-grade, certified, "the patient warmed because of NERAM".

| Time | Scenario / action | Point to make |
|---|---|---|
| 0:00 | SCN_A (or SYN_SCN_A0), ×60 | One clock drives everything: signal, twin estimate ± SD, controller log, hardware, 3D scene. Unity replays; the twin is Python, the controller is Simulink/Stateflow. |
| 0:45 | Hover the thermal chart; show a missing-observation gap | Missing data is shown as missing, never filled in. The twin keeps an estimate with widening uncertainty. |
| 1:15 | Press **T** to jump to PREDICTIVE_WARMING | The transition comes from the controller log (trigger reason shown). Open loop: heaters would be commanded, but this replay applies no warming — the forecast is labelled "No-intervention forecast". |
| 2:00 | SCN_B (or SYN_SCN_B) | Twin in the loop with an **ASSUMED** warming response: label "Forecast under ASSUMED warming"; heater glow follows Heat_i; "Compare" shows the ASSUMED no-warming trajectory from the same file. Simulated, not evidence of benefit. |
| 3:00 | SCN_C (or SYN_SCN_C), **F** to the fault | Over-temperature on one channel → SAFETY_SHUTDOWN latched, all heaters dark, fault code and channel outlined; RESET blocked until conditions clear, then released. |
| 4:00 | Click the module → Exploded view | Layer stack (liner, sensors A/B, flexible resistive heater, independent cutoff, insulation, shell). CAD from Neharikaa (or placeholder geometry, labelled). |
| 4:45 | SCN_D (or SYN_SCN_D) | Twin degraded → forecast hidden, banner "Twin unreliable — monitoring only". Uncertainty drives behaviour; no forecast is shown when the twin is not valid. |
| 5:30 | Parameters drawer | Every threshold shows its status (FROZEN / PROVISIONAL / TBD / ASSUMED). TBD values are not invented. |
| 6:00 | Footer | "Simulated / assumed prototype response. Not for treatment decisions." |

Recording: use **Capture** for stills (PNG with disclaimer). For video use OBS on the Game view; keep the footer visible. Only SYNTHETIC/DEVELOPMENT replays can be loaded, so recordings cannot contain holdout data.
