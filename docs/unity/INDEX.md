# NERAM Unity layer — deliverables by phase

| Phase | Deliverable |
|---|---|
| 0 Spec audit | `PHASE0_SPEC_AUDIT.md` — rules carried into Unity, 15 findings (conflicts, gaps, proposals) with owners |
| 1 Architecture | `ARCHITECTURE.md` — data flow, assemblies, schema single source, sync, display rules, performance, failure behaviour |
| 2 Implementation | `unity/` Unity 6 LTS project: `Assets/Scripts` (Core / Runtime / UI / Scene), `Assets/Editor`, `Assets/UI`, `unity/README.md` |
| 3 Synthetic demo | 10 SYNTHETIC placeholder replays (`integration/replays/SYN_*`, synced to StreamingAssets) built by `tools/make_synthetic_replays.py` through `build_replay.py` |
| 4 Testing | 65 NUnit tests (Unity Test Runner + .NET CI), 62 validator fixtures (Python = C#), UI contract + wording guard, compile check vs API stubs (`tools/dotnet/README.md`) |
| 5 CAD integration | `CAD_INTEGRATION.md`, `NeramCadTools.cs` (menu + import postprocessor), placeholder scene following the naming contract |
| 6 Real replay integration | `REPLAY_INTEGRATION.md` (SCN_A–D build commands with the holdout guard) |
| 7 Polish | `FEATURE_EVALUATION.md`, `DEMO_SCRIPT.md`, presentation mode, capture, camera presets |
| 8 Final audit | `FINAL_AUDIT.md` — PASS / BUILT–needs Unity run / PLACEHOLDER / TBD / NOT DONE |
