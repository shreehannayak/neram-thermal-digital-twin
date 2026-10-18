# Submission Checklist (Shreehan; scientific wording signed off by Sai)

Audit date: Mon 19 Oct 2026 (CP5). Do it from a logged-out browser. Tick each box with the date.

## The 11 submission requirements
- [ ] 1. Team details: names, roles, contributions in README section 2; each member confirmed their line in a GitHub comment
- [ ] 2. College / incubator in README section 3; matches the registration exactly
- [ ] 3. Project title identical in README section 1, CITATION.cff, slide 1 and video title (text search done)
- [ ] 4. Problem statement in README section 4; no "core temperature"; no clinical-efficacy claim
- [ ] 5. Healthcare use case in README section 5; same check as 4
- [ ] 6. Technical stack in README section 13 and docs/MODEL_CARD.md; every tool named has a folder or file in the repo
- [ ] 7. Demo video 15 to 20 min, unlisted YouTube; plays logged out; every simulated element labelled on screen; no holdout case shown; link in README section 16
- [ ] 8. Open-source licence: LICENSE (Apache-2.0) and LICENSE-CAD-DOCS (CC BY 4.0) present; GitHub shows the licence badge; README section 17 says which applies where
- [ ] 9. Architecture PDF at docs/architecture.pdf (and ARCHITECTURE.md); shows twin = estimation + forecasting, Unity = visualisation; data sources labelled
- [ ] 10. Presentation PDF at docs/presentation.pdf; opens logged out; claims match SAFETY_AND_LIMITATIONS.md
- [ ] 11. Public repository: repo is public; every link reachable logged out; Git LFS files download

## Additional checks
- [ ] README complete: all 18 sections, run commands for each component, no unsupported claims
- [ ] LICENSE, LICENSE-CAD-DOCS and CITATION.cff present and consistent (CITATION.cff has final authors and VitalDB reference; LICENSE-CAD-DOCS holds the full CC BY 4.0 text)
- [ ] docs/architecture.pdf and docs/presentation.pdf present and linked
- [ ] Demo video link works logged out
- [ ] Reproducibility: environment.yml pinned; docs/AUDIT_TRAIL.md lists every script with SHA-256 and run order; controller/README.md and unity/README.md give run and build steps; cad/README.md says how to open files
- [ ] docs/SAFETY_AND_LIMITATIONS.md, MODEL_CARD.md, DATA_CARD.md present; VitalDB cited with its data-use terms
- [ ] PREREGISTRATION_dev.md committed before development results; PREREGISTRATION_final.md committed before any holdout run (commit timestamps checked)
- [ ] No forbidden data: searched the repo for vitaldb_bt_cache, .csv.gz, dev_robust_inputs, case-level holdout files, Colab folders, Unity Library/, keys; ran git lfs ls-files and git count-objects -vH for unexpected large files
- [ ] Text search finds no "core temperature" (except in the sentence that says we do not claim it), "clinically validated", "prevents hypothermia", "medical-grade", "certified"
- [ ] Every figure with simulated or assumed content carries its label

## Hardware definition of done (Shreehan)
- [ ] Block diagram, safety-layer diagram and interface map committed (source + image)
- [ ] Sensor, MCU and heater comparisons with datasheet links; chosen candidates marked PROVISIONAL with reasons
- [ ] One-channel schematic with master switch, current sense, hardware cutoff and default-off behaviour
- [ ] Power budget with every input sourced; peak, continuous and per-case energy; battery note
- [ ] fault_codes.csv, comm_protocol.md, controller_hw_interface.md and cad_envelope.csv v1 delivered
- [ ] Electrical BOM with links and costs; feasibility document with explicit non-claims
- [ ] Threshold ordering documented; t_surface_limit_degC sourced or TBD, never guessed
- [ ] README, licences, CITATION.cff, .gitignore, .gitattributes committed

Scientific wording signed off by Sai: [ ] (date: ______ )
