# "Wow" feature evaluation

Criteria: (1) shows only replayed data, (2) no clinical/hardware value invented, (3) helps judges understand the twin/controller, (4) cost.

| Feature | Verdict | Notes |
|---|---|---|
| Synchronized 3D + chart + banner + timeline on one clock | **BUILT** | Core of the demo. |
| Heater glow from Heat_i, bloom | **BUILT** | Visual encoding of a replayed command only. |
| Fault outline (inverted hull), plug drop on disconnect, controller LEDs | **BUILT** | Replayed fault/cutoff/connected values. |
| Exploded module view | **BUILT** | Uses CAD layer names; offsets from CAD CSV when provided. |
| World-anchored labels + single thermal-state indicator | **BUILT** | Replaces a body heat map (rejected: no spatial model). |
| Forecast fan with 80/95 % and P_below_hypo cards | **BUILT** | Hidden unless VALID; label states the loop. |
| Event navigation (transition/fault/safety/clinician/flag) + timeline lanes | **BUILT** | Keyboard T/F/S, Shift+arrows. |
| Data-provenance badges (REAL_DEV/MODEL/SIMULATED/ASSUMED) | **BUILT** | Compact/expanded (B). |
| Presentation mode, camera presets, capture | **BUILT** | P, C, Capture button. |
| Comparison vs ASSUMED no-warming trajectory | **BUILT (conditional)** | Only with a plant group in the replay; labelled ASSUMED. |
| Diagnostics drawer (validation report, hashes, CAD-vs-placeholder, perf) | **BUILT** | Judges can see the engineering rigour. |
| Live fault injection | **REJECTED** | Needs the controller inside Unity. Use Suchitha's TC logs. |
| Body temperature heat map | **REJECTED** | Would invent physiology. |
| "What-if" slider changing the heater power | **REJECTED** | Would require a physiological simulator in Unity; possible only as precomputed replays from Sai's plant model, labelled ASSUMED. |
| Smooth interpolation of missing samples | **REJECTED** | Fabricates data. |
| VR / AR | **DEFERRED** | Not needed for the brief; high cost. |
| Side-by-side two-replay comparison (e.g. open loop vs ASSUMED warming of the same case) | **DEFERRED** | Feasible later: two ReplaySessions on one clock; both must be team-produced replays. |
