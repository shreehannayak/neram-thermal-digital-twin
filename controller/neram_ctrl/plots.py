"""Per-test plots (1600x900 PNG), labelled PYTHON FALLBACK / SIMULATED."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .blocks import STATE_NAMES  # noqa: E402

FOOT = ("PYTHON FALLBACK (rebuilt controller) - SIMULATED / ASSUMED PROTOTYPE RESPONSE. Not a Simulink/Stateflow "
        "screenshot. No clinical claim.")


def _fig(title):
    fig = plt.figure(figsize=(16, 9), dpi=100)
    fig.suptitle(title, fontsize=15, x=0.05, ha="left")
    fig.text(0.05, 0.015, FOOT, fontsize=9, color="#a00000")
    return fig


def plot_test(name, title, rows, outdir):
    t = np.array([r["t_s"] for r in rows], dtype=float)
    xl, unit = (t / 3600.0, "t (h)") if t[-1] > 7200 else (t, "t (s)")
    files = []
    # P01 state + trigger reason
    fig = _fig("%s %s - P01 controller state" % (name, title))
    ax = fig.add_subplot(111)
    ax.step(xl, [r["Controller_State"] for r in rows], where="post", color="#1f4e79")
    ax.set_yticks(range(7))
    ax.set_yticklabels(STATE_NAMES)
    ax.set_xlabel(unit)
    ax.grid(alpha=0.3)
    files.append(_save(fig, outdir, name, "P01"))
    # P02 heat + demand
    fig = _fig("%s %s - P02 Heat_1..4 and Demand_Global" % (name, title))
    ax = fig.add_subplot(111)
    for i in range(1, 5):
        ax.plot(xl, [r[f"Heat_{i}"] for r in rows], label=f"Heat_{i} (%)")
    ax.plot(xl, [r["Demand_Global"] for r in rows], "k--", lw=1, label="Demand_Global (%)")
    ax.set_xlabel(unit)
    ax.set_ylabel("%")
    ax.legend()
    ax.grid(alpha=0.3)
    files.append(_save(fig, outdir, name, "P02"))
    # P03 module temperatures
    fig = _fig("%s %s - P03 module sensors (SIMULATED stand-in)" % (name, title))
    ax = fig.add_subplot(111)
    for i in range(1, 5):
        for s, ls in (("A", "-"), ("B", ":")):
            ax.plot(xl, [r[f"Module_Temp_{i}_{s}"] for r in rows], ls, lw=1, label=f"Module_Temp_{i}_{s}")
    ax.set_xlabel(unit)
    ax.set_ylabel("degC")
    ax.legend(ncol=4, fontsize=8)
    ax.grid(alpha=0.3)
    files.append(_save(fig, outdir, name, "P03"))
    # P04 faults / alerts
    fig = _fig("%s %s - P04 alert, fault_code, channel faults" % (name, title))
    ax = fig.add_subplot(211)
    ax.step(xl, [r["Alert"] for r in rows], where="post", label="Alert")
    ax.step(xl, [r["Safety_Shutdown"] for r in rows], where="post", label="Safety_Shutdown")
    ax.legend()
    ax.grid(alpha=0.3)
    ax = fig.add_subplot(212)
    ax.step(xl, [r["fault_code"] for r in rows], where="post", label="fault_code")
    for i in range(1, 5):
        ax.step(xl, [r[f"Channel_Fault_{i}"] for r in rows], where="post", lw=1, label=f"Channel_Fault_{i}")
    ax.set_xlabel(unit)
    ax.legend(ncol=5, fontsize=8)
    ax.grid(alpha=0.3)
    files.append(_save(fig, outdir, name, "P04"))
    # P05 temperature (closed loop: plant and twin stand-in estimate; open loop: synthetic T_est)
    fig = _fig("%s %s - P05 T_est%s" % (name, title, " and T_plant (ASSUMED plant)"
                                       if rows[0]["plant_mode"] == "STANDIN" else " (synthetic input)"))
    ax = fig.add_subplot(111)
    ax.plot(xl, [r["T_est"] for r in rows], label="T_est")
    if rows[0]["plant_mode"] == "STANDIN":
        ax.plot(xl, [r["T_plant"] for r in rows], label="T_plant (ASSUMED plant)")
    ax.axhline(37.0, color="k", ls="--", lw=0.8, label="t_target_degC (placeholder)")
    ax.axhline(36.0, color="#a00000", ls=":", lw=0.8, label="t_hypo_degC (placeholder)")
    ax.set_xlabel(unit)
    ax.set_ylabel("degC")
    ax.legend()
    ax.grid(alpha=0.3)
    files.append(_save(fig, outdir, name, "P05"))
    return files


def _save(fig, outdir, name, p):
    path = f"{outdir}/{name}_{p}.png"
    fig.savefig(path)
    plt.close(fig)
    return path
