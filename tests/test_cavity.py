"""Spectrum of a rectangular PEC cavity from the FIT eigenproblem.

The reference is the analytic ``f_mnp = (C0/2) sqrt((m/a)^2 + (n/b)^2 + (p/d)^2)``
of a 1.0 x 0.7 x 0.5 m box with all six walls PEC.  The FIT spectrum comes from
:func:`emfit.eigen.resonances` on two uniform grids; it converges from *below*
with a relative error of order ``h^2``, which is what the bounds below encode.

Measured numbers for this box::

    grid          n_free   mean |rel err|   max |rel err|
    10 x 7 x 5      762        1.21 %           1.39 %
    14 x 10 x 7    2355        0.62 %           0.71 %

The reference spectra ``REF_COARSE_MHZ`` / ``REF_FINE_MHZ`` are the values
observed on those grids (they pin the solver regression-wise); the analytic
comparison is the physics statement and is checked separately with the
documented error bounds.  Tolerances are deliberately ~2x the measured errors so
a test failure means a real defect, not the last digit of a dense ``eigh``.

Runtime note: one dense solve of the free-edge pencil takes ~15 s (coarse) and
~30 s (fine) on the validation machine, so each grid is solved **once** per
module and cached; the whole file runs in about a minute.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.eigen import analytic_box_modes, resonances
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.operators import CellComplex

# cavity geometry (all six walls PEC, i.e. the default ``pec=None`` mask)
LX, LY, LZ = 1.0, 0.7, 0.5

# analytic first six modes [MHz]: (1,1,0)=261.388, (2,0,1)=335.178,
# (1,0,2)=368.416 twice, (0,1,2)=397.743 twice.
ANALYTIC_MHZ = np.array([261.388, 335.178, 368.416, 368.416, 397.743, 397.743])

# referenced FIT spectra [MHz]
REF_COARSE_MHZ = np.array([259.5670, 330.5179, 363.3837, 363.3837,
                           392.8516, 392.8516])
REF_FINE_MHZ = np.array([260.4874, 332.7939, 365.8634, 365.8634,
                         395.2604, 395.2604])

_CACHE = {}


def _solve(nx, ny, nz):
    """Solved spectrum of the ``nx x ny x nz`` box, cached per module run."""
    key = (int(nx), int(ny), int(nz))
    if key not in _CACHE:
        grid = Grid.uniform(nx, ny, nz, LX, LY, LZ)
        cc = CellComplex(grid)
        m_eps, m_mu = material_matrices(grid, cc)
        _CACHE[key] = resonances(grid, cc, m_eps, m_mu)
    return _CACHE[key]


def _analytic():
    """Analytic first six resonant frequencies [Hz] of the box."""
    return analytic_box_modes(LX, LY, LZ, count=6)


def _rel_err(freqs):
    """Element-wise relative error of ``freqs`` against the analytic spectrum."""
    return freqs / _analytic() - 1.0


# ---------------------------------------------------------------------------
# analytic reference
# ---------------------------------------------------------------------------
def test_analytic_reference_spectrum():
    """The analytic helper reproduces the closed-form first six modes."""
    f_mhz = _analytic() / 1e6
    np.testing.assert_allclose(
        f_mhz, ANALYTIC_MHZ, rtol=1e-5,
        err_msg="analytic_box_modes does not match f_mnp for the "
                "1.0 x 0.7 x 0.5 m PEC box")
    # (1,0,2) and (0,1,2) are TE/TM degenerate: listed twice each.
    np.testing.assert_allclose(
        f_mhz[2:], [f_mhz[2], f_mhz[2], f_mhz[4], f_mhz[4]], rtol=1e-12,
        err_msg="expected two doubly degenerate pairs among the first six modes")


# ---------------------------------------------------------------------------
# coarse grid 10 x 7 x 5
# ---------------------------------------------------------------------------
def test_coarse_grid_reference_spectrum():
    """10x7x5 reproduces the recorded FIT spectrum to 0.2 %."""
    res = _solve(10, 7, 5)
    assert res.freqs.size == 6, (
        f"expected 6 physical modes on 10x7x5, got {res.freqs.size}: "
        f"{res.freqs / 1e6}")
    assert res.n_free == 762, (
        f"10x7x5 should leave 762 free edges, got {res.n_free} "
        f"of {res.n_edges}")
    np.testing.assert_allclose(
        res.freqs / 1e6, REF_COARSE_MHZ, rtol=2e-3,
        err_msg="10x7x5 spectrum drifted from the recorded reference")


def test_coarse_grid_approximates_analytic_modes():
    """FIT errors on 10x7x5 stay below 3 % and are all on the low side."""
    res = _solve(10, 7, 5)
    err = _rel_err(res.freqs)
    assert np.all(err < 0.0), (
        f"every 10x7x5 mode must lie below the analytic value, got "
        f"relative errors {np.round(100 * err, 3)} %")
    mean_abs = float(np.mean(np.abs(err)))
    max_abs = float(np.max(np.abs(err)))
    assert mean_abs < 0.03, (
        f"mean |relative error| on 10x7x5 is {100 * mean_abs:.3f} %, "
        f"expected < 3 %")
    assert max_abs < 0.03, (
        f"worst |relative error| on 10x7x5 is {100 * max_abs:.3f} %, "
        f"expected < 3 %; errors {np.round(100 * err, 3)} %")


def test_coarse_grid_static_mode_count():
    """The gradient null space of a 10x7x5 grid has (nx-1)(ny-1)(nz-1) = 216."""
    res = _solve(10, 7, 5)
    assert res.n_rejected_static == 216, (
        f"10x7x5 should reject 216 static (gradient) modes, got "
        f"{res.n_rejected_static}")
    assert res.n_rejected_nonphysical == 0, (
        f"no genuine mode of the 10x7x5 box may fail the divergence screen, "
        f"got {res.n_rejected_nonphysical} rejected")


def test_coarse_grid_degenerate_pairs_coincide():
    """The TE/TM degenerate pairs are resolved as exactly equal frequencies."""
    f = _solve(10, 7, 5).freqs / 1e6
    np.testing.assert_allclose(
        f[2:4], np.full(2, f[2]), rtol=1e-6,
        err_msg=f"the (1,0,2) pair must be degenerate, got {f[2]:.6f} and "
                f"{f[3]:.6f} MHz")
    np.testing.assert_allclose(
        f[4:6], np.full(2, f[4]), rtol=1e-6,
        err_msg=f"the (0,1,2) pair must be degenerate, got {f[4]:.6f} and "
                f"{f[5]:.6f} MHz")


# ---------------------------------------------------------------------------
# refined grid 14 x 10 x 7 and convergence
# ---------------------------------------------------------------------------
def test_fine_grid_reference_spectrum():
    """14x10x7 reproduces the recorded FIT spectrum to 0.2 %."""
    res = _solve(14, 10, 7)
    assert res.freqs.size == 6, (
        f"expected 6 physical modes on 14x10x7, got {res.freqs.size}: "
        f"{res.freqs / 1e6}")
    assert res.n_free == 2355, (
        f"14x10x7 should leave 2355 free edges, got {res.n_free} "
        f"of {res.n_edges}")
    np.testing.assert_allclose(
        res.freqs / 1e6, REF_FINE_MHZ, rtol=2e-3,
        err_msg="14x10x7 spectrum drifted from the recorded reference")


def test_fine_grid_approximates_analytic_modes():
    """Refining the grid halves the error: mean < 1.5 %, max < 2 %, below."""
    res = _solve(14, 10, 7)
    err = _rel_err(res.freqs)
    assert np.all(err < 0.0), (
        f"every 14x10x7 mode must lie below the analytic value, got "
        f"relative errors {np.round(100 * err, 3)} %")
    mean_abs = float(np.mean(np.abs(err)))
    max_abs = float(np.max(np.abs(err)))
    assert mean_abs < 0.015, (
        f"mean |relative error| on 14x10x7 is {100 * mean_abs:.3f} %, "
        f"expected < 1.5 %")
    assert max_abs < 0.02, (
        f"worst |relative error| on 14x10x7 is {100 * max_abs:.3f} %, "
        f"expected < 2 %; errors {np.round(100 * err, 3)} %")
    assert res.n_rejected_static == 702, (
        f"14x10x7 should reject 702 static (gradient) modes, got "
        f"{res.n_rejected_static}")
    assert res.n_rejected_nonphysical == 0, (
        f"no genuine mode of the 14x10x7 box may fail the divergence screen, "
        f"got {res.n_rejected_nonphysical} rejected")


def test_error_converges_at_second_order():
    """h is reduced by a factor 1.44 -> the mean error should nearly halve."""
    coarse = float(np.mean(np.abs(_rel_err(_solve(10, 7, 5).freqs))))
    fine = float(np.mean(np.abs(_rel_err(_solve(14, 10, 7).freqs))))
    ratio = fine / coarse
    assert 0.35 < ratio < 0.65, (
        f"mean-error ratio fine/coarse is {ratio:.3f} "
        f"({100 * fine:.3f} % vs {100 * coarse:.3f} %), expected a ~h^2 drop "
        f"into (0.35, 0.65)")


# ---------------------------------------------------------------------------
# dense-solver guard
# ---------------------------------------------------------------------------
def test_dense_limit_raises_not_implemented():
    """Above ``max_dense`` the solver refuses instead of returning junk.

    The check happens before the ``eigh`` call, so this test is cheap.
    """
    grid = Grid.uniform(10, 7, 5, LX, LY, LZ)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    with pytest.raises(NotImplementedError, match=r"max_dense|roadmap\.md M5"):
        resonances(grid, cc, m_eps, m_mu, max_dense=100)
