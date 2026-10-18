# NERAM: Unity visualisation layer (schema + notes)

This folder holds the replay **schema** (`schema/replay_fields.json`, generated `replay_schema.json`) shared by the
Python tools and the Unity project.

**The Unity project itself is `../unity_editor/`.** Open that folder in Unity Hub with **6000.3.26f1** (Workspace v3). Setup, controls, view modes,
chart meanings, value provenance and limitations are in **`../README_FIRST.md`**.

* **What it is:** a replay viewer.
* **What it is not:** the thermal model, the controller, or a physiological simulator. No twin, controller-state transition or physiology is computed in C#.
* **Warming effects:** every warming effect shown is a **SIMULATED / ASSUMED PROTOTYPE RESPONSE**, because VitalDB contains no warming-response data.
* **Patient temperature signal:** its anatomical measurement site has not been established, so it is never labelled core temperature.
* **Holdout:** replays can only have cohort `SYNTHETIC` or `DEVELOPMENT`. Anything else is rejected by every validator and by the StreamingAssets sync.
