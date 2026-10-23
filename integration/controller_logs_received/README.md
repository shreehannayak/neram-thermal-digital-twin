# Controller logs received (owner: Suchita)

These are copies of the controller test-bench logs that reached Sai on 17 Oct 2026, taken from
`NERAM_delivery_2026-10-17.zip` (`integration/controller_logs/`). They are kept **unchanged** and outside
`integration/controller_logs/` so that the controller owner's own handoff folder is not edited by Sai.

| File | SHA-256 | Rows | t_s | Notes |
|---|---|---|---|---|
| ctrl_TC05.csv | 7381e4d3b3b19f836c5e716639185dd9e7930c6ce9c7d8dcdb7a44bb1b70b92e | 901 | 0–900 s, 1 Hz | Heat_1..4 = 0 and Demand_Global = 0 in every row |
| ctrl_TC07.csv | b3f7ce8dbfac60c2cb9dfe459b5cb17149020495538953d725b64f22a67ece20 | 301 | 0–300 s, 1 Hz | Heat_1..4 = 0 in every row; plant_mode STANDIN, T_plant/dT_heat empty |
| ctrl_TC13.csv | c1bef0c86e97e99033ec716c0620c1153a44990a5a8aa1d4468257ae3c1192aa | 901 | 0–900 s, 1 Hz | Heat_1..4 = 0 and Demand_Global = 0 in every row |

**Authenticity:** these hashes were computed on receipt. They have not been confirmed against a hash published
by the controller owner, so the source is recorded as UNVERIFIED until Suchita confirms them.

All three logs carry two extra columns, `HW_Heartbeat_s` and `HW_Fault_Code`. Both are declared in
`config/interface_spec.csv` as HW → Ctrl inputs (owner Shreehan). The replay builder accepts them and does not
serialize them (schema 1.0 has no replay field for them).

Findings for the controller owner are in `docs/SCENARIO_TRUTH_TABLE.md` and
`docs/SAI_REMAINING_WORK_AUDIT.md` (section "Upstream blockers").
