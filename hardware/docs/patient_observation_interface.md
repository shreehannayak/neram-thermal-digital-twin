# Patient-observation interface (Role A)

Owner: Shreehan (hardware). Source of the table: NERAM Team Implementation Plan, Person 3, section D.
**Proof-of-concept prototype, not a medical device.** In the demo the observation is a replay of
development-set VitalDB data; no hardware reads a patient.

The Digital Twin uses the temperature channel that the existing clinical monitor already provides.
No new body sensor is added to the twin path.

| Parameter | Unit | Required value / range | Source | Status |
|---|---|---|---|---|
| obs_source | – | Existing clinical monitor temperature channel; no new body sensor in the twin path | Project constraint (model trained on Solar8000/BT) | FROZEN |
| obs_name | – | "patient temperature signal"; never "core temperature" | Project constraint | FROZEN |
| obs_site | – | Site of the probe used by the clinical monitor | Clinician input | TBD |
| obs_rate_min | samples/min | ≥ 1 (the twin uses 1-min medians) | Project model | PROVISIONAL |
| obs_protocol | – | Vendor data export (serial/network); in the prototype, file replay | Monitor vendor documentation | TBD (out of scope; replay used) |
| obs_domain_shift_note | – | Any source other than Solar8000/BT is a domain shift and must be stated | Project constraint | FROZEN |

## Notes
* The observation reaches the host computer, which runs the Digital Twin (Sai) and the supervisory controller
  (Suchitha). It never goes to the MCU board; the MCU only handles the warming modules.
* The anatomical site of the signal is not established, so it is called a *patient temperature signal* everywhere.
* Using a monitor other than Solar8000 (VitalDB `BT`) changes the signal the model was developed on; any such
  use must state the domain shift and is outside the 20 Oct prototype.
