# Suchitha's Colab notebook, 17 Oct 2026 version (superseded)

`neram.ipynb`: Suchitha's single-cell Colab controller (supervisor, fault monitor, closed-loop stand-in plant, TC01–TC03
and fault demos) plus the integration-log exporter. Received from Sai on 18 Oct 2026, kept unchanged with its saved
outputs. **Superseded** by the 18 Oct v2 package (`controller/README.md`; results in `controller/results/`), whose code
folder `neram_ctrl/` is still to come.

Why it is kept: it is the source of the controller logs received on 17 Oct. Re-run on 18 Oct (Python 3.13, numpy,
pandas, matplotlib; Colab-only download cell skipped), its exporter reproduces `integration/controller_logs_received/`
`ctrl_TC05.csv`, `ctrl_TC07.csv` and `ctrl_TC13.csv` **byte for byte** (line endings normalised). `ctrl_TC07.csv` is
the log behind the shipped replay `SYN_TC07`. In this version TC04 does not reach TARGET_MAINTENANCE with the
placeholder plant gain (the notebook says so itself); the v2 package changed that.

SIMULATED / ASSUMED prototype responses; no clinical claim.
