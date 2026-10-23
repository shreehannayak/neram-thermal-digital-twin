# Controller code rebuild (Sai, 18 Oct 2026)

## Why
Suchita's v2 controller (spec, results, logs, figures, video) was produced in a Claude chat session that was not her
own account. The chat's generated files were hidden when the chat was shared, and she does not have the source files
(`neram_ctrl/`, scripts, tests). Her v2 **outputs** arrived on 18 Oct and are in the repository unchanged
(`integration/controller_logs_received/2026-10-18/`). Without code, the README's run commands could not work, so Sai
rebuilt the code from her specification (`docs/controller_spec.md`) the same night, with Claude's help.

The design, the states, transitions, fault table, parameters and test criteria are Suchita's. The Python files in
`neram_ctrl/` and `scripts/` were written on 18 Oct by Sai to that design.

## How the rebuild was checked
| Check | Result |
|---|---|
| `ctrl_SYN_02`, `ctrl_TC05`, `ctrl_TC07`, `ctrl_TC08`, `ctrl_TC13` regenerated vs the received v2 logs | **byte-identical** (all 5; `results/reproduction_check.csv`). This includes every noisy sensor value (numpy seed 42), the closed-loop plant and the CH2 ramp, shutdown, blocked and successful resets of TC07 |
| `results/test_results.csv` vs the received v2 table | 129 of 132 rows identical (criterion text, measured value, result); same totals: 112 PASS, 18 REPORTED, 1 BLOCKED, 1 EXCLUDED, 0 FAIL |
| TC04 (no v2 log was received) | measured values identical to the v2 table: ACTIVE at 10 s, MAINT at 24430 s, time to target 6.97 h (T_plant) / 6.78 h (T_est), overshoot 0.059 degC, max MAINT heat 11.31 % |
| TC18 | identical to v2 (13.94 / 6.97 / 3.59 h; overshoots 0.035 / 0.064 / 0.133 degC) with a 16 h run |
| Section-G audit | 19 PASS, 1 BLOCKED (AU-G2a, sensor range not supplied), as in v2 |
| Section-S check of the six handoff logs | PASS |

## Known differences from v2
1. **TC17 stress run.** The v2 schedule of the six 3 s T_est glitches is not written in the spec. The rebuild uses
   -0.5 degC at 1500, 3000, ..., 9000 s. The prescribed-noise run is identical to v2 (2 transitions); the stress run
   matches v2 transition for transition up to 1330 s and then differs (34 transitions vs 44 in v2). All TC17
   criteria PASS in both.
2. **AU-G2b.** With test-only limits 20..60 degC the rebuild reports 102 (sensor A out of range) as the spec's fault
   table says; v2 reported 101 for its injection.
3. **AU-G9 sample count** differs (the set of runs differs); 0 violations in both.
4. **AU-D1** is shown with a clinician start at 5 s and Heat ~0.25 %: literal rule false HEATER_OPEN at t = 16 s, qualified
   rule none (v2: same times).
5. **Plots:** P01-P05 per test (state, heat/demand, module sensors, alerts/faults, temperature) instead of v2's
   P01-P09. The v2 figures, slides, S01-S07 screenshots and video are not regenerated; the received images and video
   are kept.
6. **New outputs v2 never delivered:** `ctrl_TC04.csv` (12 h, 8 MB), per-test logs for TC01-TC17 and
   `results/tables/T07_duty_stats.csv` (mean / p95 / max Heat per channel per scenario, for the power budget).
7. **Parameters:** still the standalone-0.1 table. `config/params.json` is not read automatically, so the published
   results stay on the values v2 used.

SIMULATED / ASSUMED prototype; no clinical claim. Not a Simulink/Stateflow model.
