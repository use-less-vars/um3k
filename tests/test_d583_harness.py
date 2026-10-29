"""Smoke test for :mod:`emfit.modal_harness` -- a harness check, not physics.

The mesh is the smallest one that still carries a microstrip cross-section on
the study's own cell (``h / n_sub = 0.2 mm``): 24 x 18 x 14 cells.  Nothing here
measures an exponent, an S-parameter or a convergence rate; the claims are only
that the capture

* returns ``complex`` amplitudes, finite, with at least one non-zero magnitude,
  one per station;
* is actually *accumulating* -- the same station sampled over 120 steps differs
  from the same station sampled over 60, which a projector returning a frozen
  snapshot could not do.

The frequency is the record's own DFT bin (``k / (n_acc * dt)``), because
:func:`emfit.modal.modal_station_phasors` refuses a bin it did not capture.
"""

import numpy as np

from emfit.evolve import FITStepper, cfl_dt
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.modal_harness import (ModalStationCapture, build_mode_plane,
                                 station_amplitude)
from emfit.operators import CellComplex
from emfit.pml import PML

# --- the coupon, shrunk -----------------------------------------------------
H = 1.6e-3
N_SUB = 8
CELL = H / N_SUB
EPS_R = 4.4
N_STRIP = 4
W = N_STRIP * CELL
N_CLEAN = 3
N_AIR = 4
N_TOP = 2
N_PML = 4
N_REF = 4
N_LINE = 16
F_TARGET = 10e9
N_ACC = 120
LIMITS = (60, 120)


def _coupon():
    """The tiny guide: grid, complex, stepper, and where the strip is."""
    nx = N_PML + N_REF + N_LINE
    ny = 2 * N_PML + N_STRIP + 2 * N_CLEAN
    nz = N_SUB + N_AIR + N_TOP
    grid = Grid.uniform(nx, ny, nz, nx * CELL, ny * CELL, nz * CELL)
    cc = CellComplex(grid)

    substrate = lambda x, y, z: np.where(z <= H, EPS_R, 1.0)   # noqa: E731
    m_eps, m_mu = material_matrices(grid, cc, eps_r=substrate)

    ix_port = N_PML + N_REF          # node layer of the drive plane
    k_strip = N_SUB                  # node layer of the strip (z = h)
    j0 = N_PML + N_CLEAN             # first y point layer under the strip
    j1 = j0 + N_STRIP

    pec = np.array(cc.pec_edge_mask(), dtype=bool)
    strip = np.zeros(cc.n_edges, dtype=bool)
    strip[cc.idx_ex(np.arange(ix_port, nx)[:, None],
                    np.arange(j0, j1 + 1)[None, :], k_strip)] = True
    strip[cc.idx_ey(np.arange(ix_port, nx + 1)[:, None],
                    np.arange(j0, j1)[None, :], k_strip)] = True
    pec |= strip

    pml = PML(grid, thickness_cells=N_PML, order=2, target=1e-4,
              walls=("xmin", "xmax", "ymin", "ymax", "zmax"), cc=cc)
    stepper = FITStepper(cc, m_eps, m_mu, dt=float(cfl_dt(grid)), pec=pec,
                         pml=pml)
    return cc, stepper, ix_port, k_strip, j0, j1


def _drive_edges(cc, ix_port, k_strip, j0, j1):
    """The E_z column from ground to strip at the port plane (as the study)."""
    return np.unique(np.concatenate(
        [cc.idx_ez(np.array([ix_port]), np.array([j]),
                   np.arange(0, k_strip)).ravel() for j in range(j0, j1 + 1)]))


def _run(steps):
    """One short run; returns the capture's result and the facts around it."""
    cc, stepper, ix_port, k_strip, j0, j1 = _coupon()
    dt = float(stepper.dt)
    span = steps * dt
    f0 = max(1, int(round(F_TARGET * span))) / span     # the record's own bin
    stations = np.linspace(ix_port + 2, cc.nx - 2, 3).astype(int)

    mode = build_mode_plane(cc, h=H, w=W, eps_r=EPS_R, n_sub=N_SUB,
                            k_strip=k_strip,
                            iy_strip_centre=j0 + N_STRIP // 2,
                            n_clean=N_CLEAN, n_air=N_AIR)
    cap = ModalStationCapture(cc, mode, stations, f0=f0, dt=dt, limit=steps,
                              n_warm=steps // 4)
    port_edges = _drive_edges(cc, ix_port, k_strip, j0, j1)
    n_warm = steps // 4

    def drive(n):
        cur = np.zeros(cc.n_edges, dtype=float)
        ramp = min(1.0, (n + 1) / max(n_warm, 1))
        cur[port_edges] = ramp * np.sin(2.0 * np.pi * f0 * n * dt)
        return cur

    result = cap.run(stepper, drive=drive)
    result["f0"] = f0
    result["dt"] = dt
    result["cell"] = CELL
    result["n_edges"] = cc.n_edges
    result["mesh"] = (cc.nx, cc.ny, cc.nz)
    result["single"] = station_amplitude(stepper, cc, mode, int(stations[0]),
                                         f0=f0, dt=dt)
    return result


def test_capture_returns_complex_nonzero_and_accumulates():
    """dtype, finiteness, magnitude, station count, and that it accumulates."""
    short = _run(LIMITS[0])
    long = _run(LIMITS[1])

    for tag, res in (("60", short), ("120", long)):
        amps = res["amplitudes"]
        assert len(amps) == len(res["stations"]) == 3, (tag, amps)
        for ix, a in amps.items():
            assert isinstance(a, complex), (tag, ix, type(a))
            assert np.isfinite(a), (tag, ix, a)
        assert any(abs(a) > 0.0 for a in amps.values()), (tag, amps)
        assert np.isfinite(res["single"]), (tag, res["single"])
        assert res["steps"] == (LIMITS[0] if tag == "60" else LIMITS[1]), (
            tag, res["steps"])

    assert short["f0"] != long["f0"]          # different record lengths, bins
    ix = short["stations"][0]
    a60, a120 = short["amplitudes"][ix], long["amplitudes"][ix]
    assert a120 != a60, (a60, a120)

    print("\n--- d583 harness smoke ---")
    for tag, res in (("60", short), ("120", long)):
        print(f"mesh={res['mesh']} cell={res['cell']:.4e} m "
              f"n_edges={res['n_edges']}")
        print(f"  steps={res['steps']} f0={res['f0']!r} Hz dt={res['dt']!r} s")
        for ix in res["stations"]:
            print(f"  station {ix:3d}: v={res['amplitudes'][ix]!r} "
                  f"|v|={abs(res['amplitudes'][ix]):.6e} "
                  f"a_e={res['a_e'][ix]!r} a_h={res['a_h'][ix]!r}")
        print(f"  single-snapshot station {res['stations'][0]}: "
              f"{res['single']!r}")
    print(f"  station {ix}: 60 -> {a60!r}")
    print(f"  station {ix}: 120 -> {a120!r}")
    print(f"  difference: {a120 - a60!r}")
