#!/usr/bin/env python
"""End-to-end demo: a first-order Mur absorber versus a PEC wall.

Run from the repository root::

    python examples/abc_duct.py

The script launches the same 2 GHz TE10 tone burst down a ``320 x 16 x 1``
cell duct twice -- once with :class:`emfit.abc.Mur1Boundary` on the two ``x``
end planes, once with all six faces PEC -- records ``E_z(t)`` at a probe one
metre from each end, prints the measured reflection of each termination next
to the continuum prediction ``|v_ph - c| / (v_ph + c)``, and saves::

    docs/figures/abc_duct.png    probe waveform, linear and dB, Mur vs PEC

The PEC run is the control: its echoes come back at the incident amplitude,
while the Mur echoes sit at the numerical-dispersion floor (~-49.6 dB here,
against a -49.2 dB prediction).  The point of the figure is that the returning
pulse is plainly there for PEC and plainly gone for Mur.

Dependency note: this module is deliberately **self-contained** about the duct
setup.  It does not import ``tests.test_abc`` (a shipping example must not
depend on the test tree, nor pull in ``pytest``), and ``tests/test_abc.py``
does not import this module (the tests must not require matplotlib, which is
an optional ``[viz]`` dependency).  The configuration constants are therefore
stated twice on purpose; the test module is the authority on pass/fail, this
script on what the effect looks like.

The whole run (two 900-step ducts + one two-panel PNG) takes a few seconds.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:                      # runnable from anywhere
    sys.path.insert(0, _ROOT)

import numpy as np

from emfit import viz
from emfit.abc import Mur1Boundary
from emfit.evolve import FITStepper
from emfit.grid import Grid
from emfit.materials import C0, M_eps, M_mu
from emfit.operators import CellComplex

import matplotlib.pyplot as plt  # noqa: E402  (backend set by emfit.viz)

# --- problem definition ----------------------------------------------------
NX, NY, NZ = 320, 16, 1                        # cells
LX, LY, LZ = 2.4, 0.64, 0.04                   # duct dimensions [m]
SRC_X, PRB_X = 1.2, 0.9                        # source / probe positions [m]
F0, T0, TAU = 2.0e9, 3.0e-9, 0.8e-9            # burst: 2 GHz, 3 ns, 0.8 ns
NSTEPS = 900                                   # 21.5 ns simulated

SIDE_WALLS = ("ymin", "ymax", "zmin", "zmax")  # make the problem exactly 2-D
ABC_PLANES = ("xmin", "xmax")                  # the walls under test
THRESHOLD_DB = -40.0                           # regression-test threshold

FIG_PATH = os.path.join(_ROOT, "docs", "figures", "abc_duct.png")


def waveform(t):
    """Gaussian-windowed 2 GHz tone burst."""
    s = (t - T0) / TAU
    return float(np.sin(2.0 * np.pi * F0 * (t - T0)) * np.exp(-s * s))


def peak(trace, t, t_expected, half_window):
    """Largest ``|trace|`` inside ``t_expected +/- half_window``; returns (amp, t)."""
    sel = np.flatnonzero(np.abs(t - t_expected) <= half_window)
    assert sel.size > 0, "sampling window fell outside the trace"
    k = sel[int(np.argmax(np.abs(trace[sel])))]
    return float(abs(trace[k])), float(t[k])


def run_duct(with_abc):
    """Run one duct; return the probe trace, timings and reflection levels.

    With ``with_abc`` the ``x`` walls carry Mur's condition and the four side
    walls are PEC; without it all six walls are PEC (the control).
    """
    grid = Grid.uniform(NX, NY, NZ, lx=LX, ly=LY, lz=LZ)
    cc = CellComplex(grid)
    walls = SIDE_WALLS if with_abc else ABC_PLANES + SIDE_WALLS
    stepper = FITStepper(
        cc, M_eps(grid, cc, 1.0).diag, M_mu(grid, cc, 1.0).diag,
        pec=cc.pec_edge_mask(walls))
    mur = None
    if with_abc:
        mur = Mur1Boundary(grid, stepper.dt, cc=cc,
                           planes=ABC_PLANES, pec=stepper.pec_idx)

    dx = LX / NX
    i_src, i_prb = int(round(SRC_X / dx)), int(round(PRB_X / dx))
    profile = np.sin(np.pi * np.arange(NY + 1) / NY)     # TE10 across y
    src = np.array([cc.idx_ez(i_src, j, 0) for j in range(NY + 1)], dtype=np.intp)
    probe = int(cc.idx_ez(i_prb, NY // 2, 0))

    current = np.zeros_like(stepper.e)
    trace = np.empty(NSTEPS)
    for n in range(NSTEPS):
        current[:] = 0.0
        current[src] = profile * waveform(stepper.time)
        e_prev = stepper.e.copy()          # field at time n, BEFORE the step
        stepper.step(current)              # e -> time n+1
        if mur is not None:
            mur.apply(stepper.e, e_prev)   # pre-step field = correct time level
        trace[n] = stepper.e[probe]

    t = stepper.dt * np.arange(1, NSTEPS + 1)
    omega = 2.0 * np.pi * F0
    kx = np.sqrt((omega / C0) ** 2 - (np.pi / LY) ** 2)
    v_ph = omega / kx

    t_inc = T0 + (SRC_X - PRB_X) / v_ph
    t_near = T0 + (SRC_X + PRB_X) / v_ph                  # xmin echo
    t_far = T0 + (2.0 * LX - SRC_X - PRB_X) / v_ph        # xmax echo
    inc, _ = peak(trace, t, t_inc, 1.0e-9)
    near, t_near_meas = peak(trace, t, t_near, 1.2e-9)
    far, t_far_meas = peak(trace, t, t_far, 1.2e-9)
    return {
        "t": t, "trace": trace, "dt": stepper.dt, "v_ph": v_ph,
        "inc": inc, "near": near, "far": far,
        "db_near": 20.0 * np.log10(near / inc),
        "db_far": 20.0 * np.log10(far / inc),
        "t_inc": t_inc, "t_near": t_near, "t_far": t_far,
        "t_near_meas": t_near_meas, "t_far_meas": t_far_meas,
    }


def print_summary(mur, pec):
    """Print the measured-versus-predicted table."""
    theory = 20.0 * np.log10(abs((mur["v_ph"] - C0) / (mur["v_ph"] + C0)))
    print(f"Absorbing-boundary demo: 2 GHz TE10 pulse in a "
          f"{NX}x{NY}x{NZ} cell duct")
    print(f"  duct        : {LX:g} x {LY:g} x {LZ:g} m "
          f"(dx = {1e3 * LX / NX:.1f} mm), PEC on ymin/ymax/zmin/zmax")
    print(f"  source/probe: x = {SRC_X:g} m / {PRB_X:g} m, "
          f"E_z(t) on the duct axis")
    print(f"  run         : dt = {mur['dt']:.4e} s, {NSTEPS} steps, "
          f"{mur['t'][-1] * 1e9:.2f} ns simulated")
    print(f"  TE10 mode   : v_ph = {mur['v_ph'] / C0:.5f} c at {F0 / 1e9:g} GHz, "
          f"theory |R| = {theory:+.2f} dB")
    print()
    print(f"  termination            xmin echo      xmax echo")
    print("  " + "-" * 46)
    for label, run in (("Mur1 on xmin/xmax", mur), ("PEC (control)", pec)):
        print(f"  {label:<20s} {run['db_near']:+11.2f} dB "
              f"{run['db_far']:+11.2f} dB")
    print(f"  {'theory (Mur)':<20s} {theory:+11.2f} dB {theory:+11.2f} dB")
    print()
    print(f"  incident peak: {mur['inc']:.3f} (Mur) / {pec['inc']:.3f} (PEC), "
          f"ratio {mur['inc'] / pec['inc']:.6f} -- the ABC leaves the "
          f"outgoing pulse untouched")
    print(f"  echo timing  : xmin {mur['t_near_meas'] * 1e9:.2f} ns "
          f"(expected {mur['t_near'] * 1e9:.2f}), xmax "
          f"{mur['t_far_meas'] * 1e9:.2f} ns "
          f"(expected {mur['t_far'] * 1e9:.2f})")


def figure(mur, pec, path):
    """Two panels: linear probe trace, then the same data in dB."""
    t_ns = mur["t"] * 1e9
    inc = mur["inc"]
    fig, (ax_lin, ax_db) = plt.subplots(1, 2, figsize=(9.2, 3.2))

    # --- (a) linear amplitude: the money shot ------------------------------
    ax_lin.plot(t_ns, pec["trace"], color=viz.COL_ACCENT, lw=1.0, ls="--",
                label="PEC walls (total reflection)")
    ax_lin.plot(t_ns, mur["trace"], color=viz.COL_PRIMARY, lw=1.0,
                label="Mur1 on $x_{min}/x_{max}$")
    ax_lin.set_xlabel("$t$ [ns]")
    ax_lin.set_ylabel("$E_z$ at the probe [arb. units]")
    ax_lin.set_title("probe waveform: echo present for PEC, absent for Mur1")
    ax_lin.axhline(0.0, color=viz.COL_INK, lw=0.5)
    ax_lin.legend(loc="upper right")

    span = 1.12 * np.abs(pec["trace"]).max()
    ax_lin.set_ylim(-span, span)
    for t_mark, label in ((mur["t_inc"], "incident"),
                          (mur["t_near"], "$x_{min}$ echo"),
                          (mur["t_far"], "$x_{max}$ echo")):
        ax_lin.axvline(t_mark * 1e9, color=viz.COL_MUTED, lw=0.6, ls=":")
        ax_lin.text(t_mark * 1e9, 0.94 * span, " " + label, rotation=90,
                    va="top", ha="left", fontsize=7, color=viz.COL_MUTED)

    # --- (b) the same data in dB ------------------------------------------
    floor = 1e-7 * inc
    db_mur = 20.0 * np.log10(np.maximum(np.abs(mur["trace"]), floor) / inc)
    db_pec = 20.0 * np.log10(np.maximum(np.abs(pec["trace"]), floor) / inc)
    ax_db.plot(t_ns, db_pec, color=viz.COL_ACCENT, lw=1.0, ls="--",
               label=f"PEC: {pec['db_far']:+.2f} dB")
    ax_db.plot(t_ns, db_mur, color=viz.COL_PRIMARY, lw=1.0,
               label=f"Mur1: {mur['db_far']:+.2f} dB")
    ax_db.axhline(THRESHOLD_DB, color=viz.COL_MUTED, lw=0.8, ls="-.",
                  label=f"test threshold {THRESHOLD_DB:g} dB")
    ax_db.set_xlabel("$t$ [ns]")
    ax_db.set_ylabel("$20\\log_{10}|E_z| / |E_z|^{inc}$ [dB]")
    ax_db.set_title("same data in dB: the absorption floor is ~-50 dB")
    ax_db.set_ylim(-80.0, 10.0)
    ax_db.legend(loc="lower left")

    for ax in (ax_lin, ax_db):
        ax.set_xlim(t_ns[0], t_ns[-1])

    return viz.save(fig, path)


def main() -> int:
    """Run both terminations, print the table, save the figure."""
    mur = run_duct(True)
    pec = run_duct(False)
    print_summary(mur, pec)
    path = figure(mur, pec, FIG_PATH)
    print(f"  wrote {path} ({os.path.getsize(path)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
