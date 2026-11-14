"""End-to-end test: a real FDTD run -> ``SurfaceRecorder`` -> NTFF far field.

Why this test looks the way it does
-----------------------------------
The two modules involved are tested apart and agree only at a seam that neither
of them owns.  :mod:`emfit.huygens_fields` is tested on its own field sums --
``tests/test_huygens_fields.py::test_flux_matches_the_dipole_power`` already
runs a real solve and lands ``rec.flux`` on the analytic ``P_rad`` within 1.5%
-- and :mod:`emfit.ntff` is tested on surfaces it is handed by hand.  What
neither of those checks is the *chain*: the eighteen-key archive
``SurfaceRecorder.save_npz`` writes, the reader ``load_surface_dump`` that
validates it, and the fact that the two modules' two independent routes to the
radiated power land on each other.

The two routes are genuinely different sums of the same recorded fields, and
that is the point of using both:

* ``rec.flux`` is ``0.5 Re sum(J x conj(H) . n) dA`` on the surface -- the
  direct Poynting integral, with the ``dA`` and ``cos(w dt / 2)`` weighting the
  recorder owns;
* ``far.P_rad`` is ``4 pi`` times the mean of ``|E_theta|^2 + |E_phi|^2`` over
  the sphere, from the equivalent currents ``J_s``/``M_s`` -- a different
  quadrature, on a different surface (the 64x128 midpoint sphere of
  :func:`emfit.ntff.far_field`), with the ``exp(+j k rhat . r)`` phase and the
  ``j k / 4 pi`` normalisation the transform owns.

A sign error in the phase, a ``dA`` applied twice or not at all, a dropped
``1 / 2`` or a ``J``/``M`` swap changes either number by a factor of order one,
so agreement between them is a statement about the seam and not a coincidence
of two tolerances.

The run is the one of ``test_flux_matches_the_dipole_power``, unchanged, so the
residuals here are directly comparable with the ones quoted there: 20 cells
per wavelength at 300 MHz, 12 cells of PML on each side, 40 steps per period,
4 periods of raised-cosine ramp and 8 periods of recording, and two closed
boxes of 3 and 4 cells half-width recorded in the *same* run, each written to
its own archive.  ``pytest -m slow`` runs it; it is 800 steps on a ``56^3``
grid, a few seconds.

Measured here (this is a measurement, not a coincidence)
--------------------------------------------------------
``p_rad = eta k^2 (amp h)^2 / 12 pi = 9.8628e-01 W`` for ``amp = 1 A`` on one
edge of length ``h``.  Relative residuals, both boxes::

    box 3 cells   flux/analytic +1.780e-03   far/analytic +2.134e-03
                  far/flux      +3.531e-04
    box 4 cells   flux/analytic +3.078e-03   far/analytic +6.507e-03
                  far/flux      +3.418e-03

    box-to-box: small/large - 1 = -1.294e-03

The ``flux`` numbers repeat the ones quoted by
``test_flux_matches_the_dipole_power`` bit for bit, which is what makes the
``far`` ones comparable to them: the far field of the same run is a further
7e-04 (3-cell box) and 3.4e-03 (4-cell box) away from the direct integral, on
top of the 1.8e-03 / 3.1e-03 the run already carries.  Neither residual is
converged -- what is left is the dispersion of a 20-cells-per-wavelength grid,
as that test's docstring shows -- so the fences below are upper *bounds* on a
non-converged quantity and not error estimates of it: a route taken wrongly
misses by a factor, not by a fraction of a percent.  ``far/flux`` is fenced
tighter (1%) than either route against the analytic value (1.5%) because it
compares two sums of the *same* non-converged fields, where the dispersion
common to both mostly cancels; 1% is also the box-to-box bound, and the largest
measured value is 3.4e-03.

The archive records the power crossing the surface, not the power the source
delivered, so ``far_field`` cannot compute a gain: with no ``p_in_w`` passed it
emits the documented ``RuntimeWarning`` and leaves ``G`` as ``None`` rather than
inventing an input power.  This test asserts that warning, because a silently
defaulted gain is the failure mode it exists to catch.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.evolve import FITStepper
from emfit.grid import Grid
from emfit.huygens import HuygensBounds
from emfit.huygens_fields import SurfaceRecorder
from emfit.materials import C0, ETA0, material_matrices
from emfit.ntff import far_field, load_surface_dump
from emfit.operators import CellComplex
from emfit.pml import PML

FREQ = 300e6                             # Hz
CELLS_PER_LAMBDA = 20
H_CELL = C0 / FREQ / CELLS_PER_LAMBDA    # m
SUB = 2 * CELLS_PER_LAMBDA               # steps per period
DT = 1.0 / (FREQ * SUB)
NH = 28                                  # half the domain in cells: 56^3
PML_CELLS = 12
AMP = 1.0                                # A, on one primal edge
T_RAMP = 4.0 / FREQ
HALVES = (3, 4)                          # box half-widths, in cells

#: ``rec.flux`` against the analytic ``P_rad`` of the dipole the run drives.
FLUX_TOL = 1.5e-2
#: the same power seen by two boxes in one run: the quadrature difference.
BOX_TOL = 1.0e-2
#: ``far.P_rad`` against ``rec.flux``: two routes to one number.
TWO_ROUTES_TOL = 1.0e-2
#: ``far.P_rad`` against the analytic ``P_rad``, the sphere quadrature included.
FAR_TOL = 1.5e-2


@pytest.mark.slow
def test_far_field_of_a_recorded_surface_matches_its_own_flux(tmp_path):
    """One run, two boxes, two archives: ``far.P_rad`` lands on ``rec.flux``.

    ``rec.flux`` is the direct Poynting integral on the box and ``far.P_rad``
    the angular integral of the equivalent-current pattern of the same box
    after a round trip through ``save_npz``/``load_surface_dump``.  Measured
    residuals above; every fence is an upper bound on a non-converged grid,
    not an error estimate.
    """
    h = H_CELL
    nh = NH
    n = 2 * nh
    grid = Grid.uniform(n, n, n, n * h, n * h, n * h)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    pml = PML(grid, thickness_cells=PML_CELLS, order=2, target=1e-6,
              axes=("x", "y", "z"), cc=cc)

    w = 2.0 * np.pi * FREQ
    src = int(cc.idx_ez(nh, nh, nh))
    j = np.zeros(cc.n_edges)

    def drive(t):
        """Soft current on the centre edge: ramped cosine, ``j[src] = A``."""
        j[:] = 0.0
        ramp = 1.0
        if t < T_RAMP:
            ramp = 0.5 * (1.0 - np.cos(np.pi * t / T_RAMP))
        j[src] = AMP * ramp * np.cos(w * t)
        return j

    def box(half):
        """Closed cube of ``half`` cells half-width, centred on the source."""
        lo, hi = nh - half, nh + half
        return HuygensBounds(xmin=grid.x[lo], xmax=grid.x[hi],
                             ymin=grid.y[lo], ymax=grid.y[hi],
                             zmin=grid.z[lo], zmax=grid.z[hi]).conform_to(cc)

    recs = {half: SurfaceRecorder(box(half), FREQ, cc=cc) for half in HALVES}

    def record(stepper):
        for rec in recs.values():
            rec(stepper)

    stepper = FITStepper(cc, m_eps, m_mu, dt=DT, pml=pml)
    stepper.run((4 + 8) * SUB, source=drive)
    stepper.run(8 * SUB, source=drive, callback=record)

    k = 2.0 * np.pi * FREQ / C0
    p_rad = ETA0 * k ** 2 * (AMP * h) ** 2 / (12.0 * np.pi)

    far = {}
    for half, rec in recs.items():
        path = tmp_path / f"huygens_box_{half}.npz"
        rec.save_npz(path)
        dump = load_surface_dump(path)
        # the archive IS the record: not close to it, the same bits
        np.testing.assert_array_equal(dump.flux, rec.flux)
        # one direction is enough: P_rad is integrated by far_field on its own
        # 64x128 sphere, so the angles asked for do not enter it
        with pytest.warns(RuntimeWarning, match="input power is absent"):
            far[half] = far_field(dump, np.pi / 2.0, 0.0)
        # no input power in the archive, so no gain is invented
        assert far[half].G is None
        assert far[half].p_in is None

    for half in HALVES:
        rel = float(recs[half].flux[0]) / p_rad - 1.0
        assert abs(rel) < FLUX_TOL, (half, rel)

    rel_box = float(recs[HALVES[0]].flux[0]) / float(recs[HALVES[1]].flux[0]) - 1.0
    assert abs(rel_box) < BOX_TOL, rel_box

    for half in HALVES:
        two_routes = far[half].P_rad / float(recs[half].flux[0]) - 1.0
        rel_rad = far[half].P_rad / p_rad - 1.0
        assert abs(two_routes) < TWO_ROUTES_TOL, (half, two_routes)
        assert abs(rel_rad) < FAR_TOL, (half, rel_rad)
