# Submission Checklist (Shreehan; scientific wording signed off by Sai)

Audit date: Mon 19 Oct 2026 (CP5). Do it from a logged-out browser. Tick each box with the date.

Ticked 19 Oct 2026 by Sai from the automated checks in docs/SUBMISSION_DRYRUN_2026-10-19.md; Shreehan confirms the logged-out items (public links, LFS download).

## The 11 submission requirements
- [x] 1. Team details: names, roles, contributions in README section 2; each member confirmed their line in a GitHub comment (19 Oct; all four confirmed in issue #3)
- [x] 2. College / incubator in README section 3; matches the registration exactly (19 Oct; checked against the registration)
- [x] 3. Project title identical in README section 1, CITATION.cff, slide 1 and video title (text search done) (19 Oct; README, CITATION.cff, slide 1 and video title identical)
- [x] 4. Problem statement in README section 4; no "core temperature"; no clinical-efficacy claim (19 Oct)
- [x] 5. Healthcare use case in README section 5; same check as 4 (19 Oct)
- [x] 6. Technical stack in README section 13 and docs/MODEL_CARD.md; every tool named has a folder or file in the repo (19 Oct)
- [x] 7. Demo video 15 to 20 min, unlisted YouTube; plays logged out; every simulated element labelled on screen; no holdout case shown; link in README section 16 (19 Oct; 17:58, https://youtu.be/22L1wyx7IZk)
- [x] 8. Open-source licence: LICENSE (Apache-2.0) and LICENSE-CAD-DOCS (CC BY 4.0) present; GitHub shows the licence badge; README section 17 says which applies where (19 Oct)
- [x] 9. Architecture PDF at docs/architecture.pdf (and ARCHITECTURE.md); shows twin = estimation + forecasting, Unity = visualisation; data sources labelled (19 Oct)
- [x] 10. Presentation PDF at docs/presentation.pdf; opens logged out; claims match SAFETY_AND_LIMITATIONS.md (19 Oct)
- [x] 11. Public repository: repo is public; every link reachable logged out; Git LFS files download (19 Oct)

## Additional checks
- [x] README complete: all 18 sections, run commands for each component, no unsupported claims (19 Oct)
- [x] LICENSE, LICENSE-CAD-DOCS and CITATION.cff present and consistent (CITATION.cff has final authors and VitalDB reference; LICENSE-CAD-DOCS holds the full CC BY 4.0 text) (19 Oct)
- [x] docs/architecture.pdf and docs/presentation.pdf present and linked (19 Oct)
- [x] Demo video link works logged out (19 Oct)
- [x] Reproducibility: environment.yml pinned; docs/AUDIT_TRAIL.md lists every script with SHA-256 and run order; controller/README.md and unity/README.md give run and build steps; cad/README.md says how to open files (19 Oct)
- [x] docs/SAFETY_AND_LIMITATIONS.md, MODEL_CARD.md, DATA_CARD.md present; VitalDB cited with its data-use terms (19 Oct)
- [ ] PREREGISTRATION_dev.md committed before development results; PREREGISTRATION_final.md committed before any holdout run (commit timestamps checked) — NOTE: both entered the repo in the same commit, so timestamps cannot show order; no development result or holdout run exists
- [x] No forbidden data: searched the repo for vitaldb_bt_cache, .csv.gz, dev_robust_inputs, case-level holdout files, Colab folders, Unity Library/, keys; ran git lfs ls-files and git count-objects -vH for unexpected large files (19 Oct)
- [x] Text search finds no "core temperature" (except in the sentence that says we do not claim it), "clinically validated", "prevents hypothermia", "medical-grade", "certified" (19 Oct)
- [x] Every figure with simulated or assumed content carries its label (19 Oct)

## Hardware definition of done (Shreehan)
- [x] Block diagram, safety-layer diagram and interface map committed (source + image) (19 Oct)
- [x] Sensor, MCU and heater comparisons with datasheet links; chosen candidates marked PROVISIONAL with reasons (19 Oct)
- [x] One-channel schematic with master switch, current sense, hardware cutoff and default-off behaviour (19 Oct)
- [ ] Power budget with every input sourced; peak, continuous and per-case energy; battery note — PARTIAL: heater power per channel and case durations are TBD (never guessed)
- [x] fault_codes.csv, comm_protocol.md, controller_hw_interface.md and cad_envelope.csv v1 delivered (19 Oct)
- [ ] Electrical BOM with links and costs; feasibility document with explicit non-claims — PARTIAL: 7 rows priced; remaining prices TBD
- [x] Threshold ordering documented; t_surface_limit_degC sourced or TBD, never guessed (19 Oct)
- [x] README, licences, CITATION.cff, .gitignore, .gitattributes committed (19 Oct)

Scientific wording signed off by Sai: [x] (date: 19 Oct 2026)
