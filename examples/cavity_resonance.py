#!/usr/bin/env python
"""End-to-end demo: PEC cavity eigenmodes and a leapfrog ring-down.

Run from the repository root::

    python examples/cavity_resonance.py

The script solves the ``10 x 7 x 5`` eigenproblem of a ``1.0 x 0.7 x 0.5 m``
all-PEC cavity with :func:`emfit.eigen.resonances`, prints the lowest six modes
against the closed form ``f_mnp``, then rings the same cavity with a Ricker soft
source on a single z-directed edge near a corner and saves three figures for the
LaTeX document::

    docs/figures/cavity_spectrum.png   FIT vs analytic spectrum
    docs/figures/cavity_field_z.png    Ez slice at the field maximum
    docs/figures/energy_drift.png      leapfrog energy and its relative drift

The whole run (dense eigen-solve + 1800 explicit steps + three PNGs) takes well
under a minute on a laptop.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:                      # runnable from anywhere
    sys.path.insert(0, _ROOT)

import numpy as np

from emfit.eigen import analytic_box_modes, resonances
from emfit.evolve import FITStepper, RickerSource, cfl_dt
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.operators import CellComplex
from emfit.viz import plot_energy, plot_field_slice, plot_spectrum, save

# --- problem definition ----------------------------------------------------
NX, NY, NZ = 10, 7, 5                          # cells
LX, LY, LZ = 1.0, 0.7, 0.5                     # cavity dimensions [m]
NMODE = 6                                      # modes to report

FMAX = 400e6                                   # Ricker centre frequency [Hz]
N_WARM = 300                                   # driven steps
N_REC = 1500                                   # recorded ring-down steps

FIG_DIR = os.path.join(_ROOT, "docs", "figures")


def build():
    """Return the cavity grid, cell complex and material diagonals."""
    grid = Grid.uniform(NX, NY, NZ, LX, LY, LZ)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    return grid, cc, m_eps, m_mu


def spectrum(grid, cc, m_eps, m_mu):
    """Solve the eigenproblem and return ``(fit_hz, analytic_hz, result)``."""
    result = resonances(grid, cc, m_eps, m_mu, k=NMODE)
    fit = np.asarray(result.freqs, dtype=float)[:NMODE]
    exact = analytic_box_modes(LX, LY, LZ, count=NMODE)
    return fit, exact, result


def print_table(fit, exact):
    """Print the mode-by-mode comparison table."""
    print(f"PEC cavity {NX}x{NY}x{NZ} cells, "
          f"{LX:g} x {LY:g} x {LZ:g} m (all six walls PEC)")
    print(f"  mode   FIT [MHz]   analytic [MHz]   rel. error")
    print("  " + "-" * 46)
    for i, (fc, fa) in enumerate(zip(fit, exact)):
        print(f"  {i:4d} {fc / 1e6:12.4f} {fa / 1e6:16.3f} "
              f"{100.0 * (fc / fa - 1.0):+13.3f} %")


def ringdown(grid, cc, m_eps, m_mu):
    """Drive the cavity, then record the lossless ring-down.

    Returns:
        ``(t, energies, snapshot, snapshot_time)`` where ``snapshot`` is the
        edge-vector copy with the largest L2 norm seen during the run.
    """
    dt = cfl_dt(grid)
    stepper = FITStepper(cc, m_eps, m_mu, dt=dt, pec=cc.pec_edge_mask())
    source = RickerSource(cc.n_edges, cc.idx_ez(1, 1, 1), fmax=FMAX)
    stepper.run(N_WARM, source=source)

    times: list[float] = []
    energies: list[float] = []
    best = {"norm": -1.0, "e": None, "t": 0.0}

    def record(st):
        times.append(st.time)
        energies.append(st.energy())
        norm = float(np.linalg.norm(st.e))
        if norm > best["norm"]:
            best.update(norm=norm, e=st.e.copy(), t=st.time)

    stepper.run(N_REC, callback=record)
    return np.asarray(times), np.asarray(energies), best["e"], best["t"]


def main() -> int:
    """Build, solve, run and save the three figures."""
    grid, cc, m_eps, m_mu = build()
    fit, exact, result = spectrum(grid, cc, m_eps, m_mu)
    print_table(fit, exact)
    print(f"  free edges: {result.n_free} of {result.n_edges}, "
          f"rejected: {result.n_rejected_static} static, "
          f"{result.n_rejected_nonphysical} non-physical")

    fig, _ = plot_spectrum(fit, exact,
                           title=f"PEC cavity {LX:g} x {LY:g} x {LZ:g} m, "
                                 f"{NX}x{NY}x{NZ} cells")
    paths = [save(fig, os.path.join(FIG_DIR, "cavity_spectrum.png"))]

    t, energies, snapshot, t_snap = ringdown(grid, cc, m_eps, m_mu)
    drift = (energies - energies[0]) / energies[0]
    peak_drift = float(np.max(np.abs(drift)))

    fig, _ = plot_field_slice(grid, snapshot, "EZ", axis="z",
                              title=f"$E_z$ at $t = {t_snap * 1e9:.1f}$ ns "
                                    f"(mid-plane)")
    paths.append(save(fig, os.path.join(FIG_DIR, "cavity_field_z.png")))

    fig, _ = plot_energy(t, energies,
                         title="lossless ring-down: energy and drift")
    paths.append(save(fig, os.path.join(FIG_DIR, "energy_drift.png")))

    print("\nSummary")
    print(f"  first {NMODE} modes: "
          + ", ".join(f"{f / 1e6:.4f}" for f in fit) + " MHz")
    print(f"  analytic          : "
          + ", ".join(f"{f / 1e6:.4f}" for f in exact) + " MHz")
    print(f"  mean |rel. error| : "
          f"{100.0 * np.mean(np.abs(fit / exact - 1.0)):.3f} %")
    print(f"  time step         : {cfl_dt(grid):.4e} s, "
          f"{N_WARM + N_REC} steps, {t[-1] * 1e9:.1f} ns simulated")
    print(f"  max |energy drift|: {peak_drift:.3e} (relative, after drive)")
    for path in paths:
        print(f"  wrote {path} ({os.path.getsize(path)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
