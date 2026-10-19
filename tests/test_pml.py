"""Tests for the matched lossy layer in :mod:`emfit.pml`.

Two halves.  The first four tests are pure geometry and arithmetic: the closed
form for ``sigma_max``, the shape of ``sigma`` along a cut (exactly zero in the
physical interior, monotone into the layer, summed in a corner), the damping
multipliers, and the guard that refuses a layer that does not fit.

The last two are physics, and both are **relative measurements taken inside the
test** -- nothing here is compared against a number measured on the 320-cell
duct, because a grid this small cannot reproduce one.

Reflection harness (``test_pml_reflects_at_least_10_db_less_than_mur``)
----------------------------------------------------------------------
The near-end and transverse echoes are removed by differencing two runs that
share them bit for bit:

    run A: 1.2 m x 0.6 m box, source at (0.6, 0.3), probe at (0.8, 0.3)
    run B: 2.0 m x 0.6 m box, *same absolute* source and probe, same y extent

A and B differ only in the ``+x`` extent, so every other reflection -- the
``-x`` end, both y walls -- is generated in identical geometry from an
identical source with an identical step and cancels exactly in ``A - B``.  All
that survives is the reflection of the ``+x`` termination.  That is why the
reference box only grows along one axis (4x cheaper than growing both) and why
the probe stays at the same absolute coordinate.

Arrival times (path/c from ``t0``, c = 0.3 m/ns):

    PML inner interface at x = 1.0:  0.4 + 0.2 = 0.6 m  ->  t0 + 2.00 ns
    Mur wall at x = 1.2:             0.6 + 0.4 = 1.0 m  ->  t0 + 3.34 ns
    shared -x wall (-0.6 ... +0.8):  0.6 + 0.8 = 1.4 m  ->  t0 + 4.67 ns
    reference +x end at x = 2.0:     1.4 + 1.2 = 2.6 m  ->  t0 + 8.67 ns

The window must span the layer echo **and** the wall echo, and must exclude the
last two.  ``(t0 + 0.9, t0 + 4.2) ns`` does that.  Closing it at ``t0 + 3.0``
excludes the Mur echo altogether, which differences to ~-186 dB of floating
point noise and makes the wall look 100 dB better than it is; the guard
assertions on ``rel`` below exist so that trap cannot come back silently.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.abc import Mur1Boundary
from emfit.evolve import FITStepper, cfl_dt
from emfit.grid import Grid
from emfit.materials import EPS0, ETA0, material_matrices
from emfit.operators import CellComplex
from emfit.pml import PML

# ---------------------------------------------------------------------------
# 1. the grading formula
# ---------------------------------------------------------------------------
def test_sigma_max_matches_the_closed_form():
    """``sigma_max = -(order+1) ln|target| / (eta0 d)`` for two triples."""
    grid = Grid.uniform(60, 60, 1, 0.6, 0.6, 0.1)      # h = 0.01 m everywhere
    for cells, order, target in ((10, 2, 1e-4), (7, 3, 1e-6)):
        pml = PML(grid, thickness_cells=cells, order=order, target=target,
                  axes=("x", "y"))
        d = cells * 0.01
        want = -(order + 1.0) * np.log(abs(target)) / (ETA0 * d)
        for axis in ("x", "y"):
            assert pml.d[axis] == pytest.approx(d)
            assert pml.sigma_max[axis] == pytest.approx(want, rel=1e-15)


# ---------------------------------------------------------------------------
# 2. the profile: zero inside, monotone into the layer, summed in the corner
# ---------------------------------------------------------------------------
def test_sigma_is_zero_in_the_interior_and_grows_into_the_layer():
    nx = ny = 60
    grid = Grid.uniform(nx, ny, 1, 0.6, 0.6, 0.1)
    cc = CellComplex(grid)
    cells = 10
    h = 0.6 / nx                                # 0.01 m
    pml = PML(grid, thickness_cells=cells, order=2, target=1e-4,
              axes=("x",), cc=cc)

    # a cut through the middle of the domain, along x, via the EZ indices
    cut = np.array([pml.sigma_e[cc.idx_ez(i, ny // 2, 0)] for i in range(nx + 1)])

    # interior from COORDINATES, with one cell of slack past the layer depth so
    # there is no judgement call about which node the last layer cell lands on
    xi = np.asarray(grid.x, dtype=float)
    slack = (cells + 1) * h
    inside = np.array([(xi[i] - xi[0] > slack) and (xi[-1] - xi[i] > slack)
                       for i in range(nx + 1)])
    assert inside.any() and not inside.all()
    edges = np.array([cc.idx_ez(i, ny // 2, 0) for i in range(nx + 1)])
    assert pml.sigma_e[edges[inside]].max() == 0.0     # exact: untouched

    # non-increasing from each wall inwards (tolerance: the profile is graded by
    # a power, so the last cells differ by rounding, not by structure)
    assert np.all(np.diff(cut[:cells + 1]) <= 1e-18)
    assert np.all(np.diff(cut[nx - cells:]) >= -1e-18)


def test_corner_sigma_is_the_sum_of_the_two_profiles():
    """Axes are added, so a corner is lossier than either single-axis layer."""
    grid = Grid.uniform(60, 60, 1, 0.6, 0.6, 0.1)
    cc = CellComplex(grid)
    kw = dict(thickness_cells=10, order=2, target=1e-4, cc=cc)
    only_x = PML(grid, axes=("x",), **kw)
    only_y = PML(grid, axes=("y",), **kw)
    both = PML(grid, axes=("x", "y"), **kw)

    # the sums of the 1-D profiles, elementwise over every edge of the grid.
    # Not exact equality: the profile is a power with a clip, so the corner
    # value is only equal to the sum to rounding.  The inequality is the part
    # that matters physically (a corner is never weaker than one axis alone).
    for total, sx, sy in ((both.sigma_e, only_x.sigma_e, only_y.sigma_e),
                          (both.sigma_m, only_x.sigma_m, only_y.sigma_m)):
        assert np.all(total >= np.maximum(sx, sy) - 1e-18)
        pos = (sx > 0.0) & (sy > 0.0)
        assert pos.any()
        assert np.allclose(total[pos], (sx + sy)[pos], rtol=1e-12, atol=1e-18)

    corner = cc.idx_ez(0, 0, 0)
    assert both.sigma_e[corner] == pytest.approx(
        only_x.sigma_e[corner] + only_y.sigma_e[corner])
    assert both.sigma_e[corner] > only_x.sigma_e[corner]
    assert both.sigma_e[corner] > only_y.sigma_e[corner]
    # and each single-axis array is itself zero away from its own wall
    middle = cc.idx_ez(30, 30, 0)
    assert only_x.sigma_e[middle] == 0.0
    assert only_y.sigma_e[middle] == 0.0


# ---------------------------------------------------------------------------
# 3. the multipliers
# ---------------------------------------------------------------------------
def test_multipliers_are_bounded_exact_and_monotone():
    grid = Grid.uniform(60, 60, 1, 0.6, 0.6, 0.1)
    pml = PML(grid, thickness_cells=10, order=2, target=1e-4, axes=("x", "y"))
    dt = cfl_dt(grid)
    e_f, h_f = pml.multipliers(dt)

    for f in (e_f, h_f):
        assert np.all(f > 0.0)
        assert np.all(f <= 1.0)

    zero = pml.sigma_e == 0.0
    assert zero.any() and not zero.all()
    # a zero conductivity must not perturb the interior at all -- exactly 1
    assert np.all(e_f[zero] == 1.0)

    # the E multiplier is the exact exponential decay of sigma over one step
    exact = np.exp(-pml.sigma_e * dt / EPS0)
    assert np.max(np.abs(e_f - exact)) <= 1e-14

    # non-increasing in sigma.  NOT strictly decreasing: exp(-sigma*dt/eps0)
    # underflows to an exact 0.0 difference in the deepest cells and rounds to
    # about 1e-16 in between, so strict decrease is false by construction.
    order = np.argsort(pml.sigma_e, kind="stable")
    sigma, factor = pml.sigma_e[order], e_f[order]
    assert np.any(np.diff(sigma) > 0.0)
    assert np.all(np.diff(factor) <= 1e-15)


# ---------------------------------------------------------------------------
# 4. the layer refuses to eat the physical region
# ---------------------------------------------------------------------------
def test_layer_thicker_than_half_the_grid_is_refused():
    grid = Grid.uniform(20, 20, 1, 1.0, 1.0, 0.1)
    with pytest.raises(ValueError, match="axis 'x'"):
        PML(grid, thickness_cells=10, axes=("x",))
    with pytest.raises(ValueError, match="do not fit"):
        PML(grid, thickness_cells=25, axes=("x",))

    # one cell less than half the grid is legal
    assert PML(grid, thickness_cells=9, axes=("x",)).thickness_cells == 9

    # the offending axis is named even when it is the second one
    with pytest.raises(ValueError, match="axis 'y'"):
        PML(Grid.uniform(20, 6, 1, 1.0, 1.0, 0.1), thickness_cells=4,
            axes=("x", "y"))


# ---------------------------------------------------------------------------
# 5. physics: the layer against Mur, measured on one small grid
# ---------------------------------------------------------------------------
H = 0.01                    # 10 points per wavelength at 3 GHz
LZ = 0.01
F0, T0, TAU = 3.0e9, 1.0e-9, 0.35e-9
XL, YL = 1.2, 0.6           # test box [m]
XL_REF = 2.0                # reference: same box, extended in +x only
SRC_X, SRC_Y = 0.6, 0.3
PRB_X, PRB_Y = 0.8, 0.3
THICK = 20                  # 2 wavelengths -> the -79 dB anchor
NSTEPS = 285                # 5.43 ns, enough for the window below
WIN = (0.9e-9, 4.2e-9)      # relative to T0; spans the layer AND the wall echo
SIDE = ("ymin", "ymax", "zmin", "zmax")
ENDS = ("xmin", "xmax")


def _waveform(t: float) -> float:
    s = (t - T0) / TAU
    return float(np.sin(2.0 * np.pi * F0 * (t - T0)) * np.exp(-s * s))


def _trace(lx: float, termination: str, dt: float):
    """Probe trace of one run; ``termination`` is ``'pml'`` or ``'mur'``."""
    nx, ny = int(round(lx / H)), int(round(YL / H))
    grid = Grid.uniform(nx, ny, 1, lx, YL, LZ)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    if termination == "mur":
        pml, walls = None, SIDE
    else:
        pml = PML(grid, thickness_cells=THICK, order=2, target=1e-4,
                  axes=("x", "y"), cc=cc)
        walls = ENDS + SIDE          # PEC behind the layer, as the duct does
    stepper = FITStepper(cc, m_eps, m_mu, dt=dt, pec=cc.pec_edge_mask(walls),
                         pml=pml)
    mur = (Mur1Boundary(grid, dt, cc=cc, planes=ENDS, pec=stepper.pec_idx)
           if termination == "mur" else None)

    src = int(cc.idx_ez(int(round(SRC_X / H)), int(round(SRC_Y / H)), 0))
    probe = int(cc.idx_ez(int(round(PRB_X / H)), int(round(PRB_Y / H)), 0))
    current = np.zeros_like(stepper.e)
    out = np.empty(NSTEPS)
    for _ in range(NSTEPS):
        current[:] = 0.0
        current[src] = _waveform(stepper.time)
        e_prev = stepper.e.copy()
        stepper.step(current)
        if mur is not None:
            mur.apply(stepper.e, e_prev)
        out[_] = stepper.e[probe]
    return dt * np.arange(1, NSTEPS + 1), out


def _two_run(termination: str):
    """``(reflection_dB, t_peak_ns, rel)`` of the ``+x`` termination."""
    dt = cfl_dt(Grid.uniform(int(round(XL / H)), int(round(YL / H)), 1,
                             XL, YL, LZ))
    t, a = _trace(XL, termination, dt)
    _, b = _trace(XL_REF, termination, dt)
    d = a - b
    sel = (t > T0 + WIN[0]) & (t < T0 + WIN[1])
    k = int(np.argmax(np.abs(d[sel])))
    incident = float(np.max(np.abs(b)))
    rel = float(abs(d[sel][k]) / incident)
    return 20.0 * np.log10(max(rel, 1e-30)), float(t[sel][k]) * 1e9, rel


def test_pml_reflects_at_least_10_db_less_than_mur():
    """Same grid, step, probe and window -- only the termination changes."""
    mur_db, mur_t, mur_rel = _two_run("mur")
    pml_db, pml_t, pml_rel = _two_run("pml")
    print(f"\ntwo-run reflection, {XL} m x {YL} m box, window "
          f"t0+{WIN[0] * 1e9:.1f}..t0+{WIN[1] * 1e9:.1f} ns:")
    print(f"  Mur (1st order)  {mur_db:8.2f} dB at {mur_t:6.2f} ns "
          f"(rel {mur_rel:.2e})")
    print(f"  PML {THICK} cells o2 t1e-4 {pml_db:8.2f} dB at {pml_t:6.2f} ns "
          f"(rel {pml_rel:.2e})")
    print(f"  margin {mur_db - pml_db:.2f} dB")

    # the window must actually contain both echoes: a difference signal at the
    # 1e-15 level is floating point noise, not a reflection
    assert mur_rel > 1e-6
    assert pml_rel > 1e-6
    assert pml_db <= mur_db - 10.0


# ---------------------------------------------------------------------------
# 6. physics: nothing is left behind once the source stops
# ---------------------------------------------------------------------------
def test_energy_decays_monotonically_after_the_source_stops():
    # n = 40 rather than 60: energy() builds a sparse C @ e product whose cost
    # jumps ~2000x between those two sizes on this machine, and the assertions
    # below do not care about the resolution.
    n, steps_on, steps = 40, 120, 300
    dt = cfl_dt(Grid.uniform(n, n, 1, n * H, n * H, LZ))
    grid = Grid.uniform(n, n, 1, n * H, n * H, LZ)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    pml = PML(grid, thickness_cells=10, order=2, target=1e-4,
              axes=("x", "y"), cc=cc)
    stepper = FITStepper(cc, m_eps, m_mu, dt=dt,
                         pec=cc.pec_edge_mask(ENDS + SIDE), pml=pml)
    src = int(cc.idx_ez(n // 2, n // 2, 0))
    current = np.zeros_like(stepper.e)
    energy = []
    for k in range(steps):
        current[:] = 0.0
        if k < steps_on:
            current[src] = _waveform(stepper.time)
        stepper.step(current)
        energy.append(stepper.energy())

    tail = np.asarray(energy[steps_on + 10:])
    assert tail[0] > 0.0
    assert np.all(np.diff(tail) <= 0.0)          # monotone, no tolerance
    assert tail[-1] < 1e-3 * tail[0]             # and it really dies away
