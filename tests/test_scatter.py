"""Tests for :mod:`emfit.scatter`: the staircase, the subtraction, the shadow.

The expensive part of this module is a *pair* of leapfrog integrations, so the
default experiment (``ka = 3``, ``ppw = 15``) is run once in a module-scoped
fixture and every test reads the same :class:`emfit.scatter.ScatterResult`.
Measured numbers on that grid (90 x 90 x 1 cells, 361 steps, dt = 1.2710e-10 s):

* the PEC mask pins **161** ``Ez`` nodes, against ``pi a^2 / h^2 = 161.14``
  from the continuum area -- the staircase is 0.09 % light, not 10 %;
* ``peak |Ez|`` is 246.41 V/m with the body present and ``peak |Ez scattered|``
  is 191.85 V/m, i.e. 0.9149 of the incident peak;
* the largest scattered amplitude sits one cell **downstream** of the centre
  and 0.3184 of the scattered energy is downstream of it, which is what a
  forward-scattering body at ``ka = 3`` should do.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit import scatter

#: One solve, shared by every test in the module.
_CACHE: dict = {}


@pytest.fixture(scope="module")
def result() -> scatter.ScatterResult:
    """The default experiment, integrated once."""
    if "result" not in _CACHE:
        _CACHE["result"] = scatter.run_scatter(ka=3.0, ppw=15)
    return _CACHE["result"]


def _mask2d(cc, mask) -> np.ndarray:
    """The ``(nx + 1, ny + 1)`` node view of an edge mask."""
    ii, jj = np.meshgrid(np.arange(cc.nxn), np.arange(cc.nyn), indexing="ij")
    return np.asarray(mask, dtype=bool)[cc.idx_ez(ii, jj, 0)]


def test_pec_mask_area_matches_the_disc(result: scatter.ScatterResult) -> None:
    """The pinned nodes cover the geometric disc area to better than 10 %."""
    cc, h = result.cc, result.lam0 / result.ppw
    assert result.mask.shape == (cc.n_edges,)
    assert result.mask.dtype == np.bool_
    assert int(result.mask.sum()) == result.n_pec_edges

    # Only Ez edges may be pinned: a z-directed edge is the only one that can
    # carry the TMz boundary condition Ez = 0.
    outside = np.ones(cc.n_edges, dtype=bool)
    outside[cc.off_ez:cc.off_ez + cc.n_ez] = False
    assert not np.any(result.mask[outside])

    analytic = np.pi * result.a ** 2 / h ** 2
    assert abs(result.n_pec_edges / analytic - 1.0) < 0.10


def test_empty_mask_gives_an_exactly_zero_scattered_field(
        result: scatter.ScatterResult) -> None:
    """``radius = 0`` must reproduce the background run bit for bit."""
    st = result.setup
    empty = scatter.cylinder_pec_mask(st.cc, st.centre, 0.0)
    assert not np.any(empty)

    frames = scatter.frame_indices(st, [(st.centre[0] - st.x_src) / scatter.C0])
    total, background = scatter.run_pair(st, frames, mask=empty)
    scattered = scatter.background_subtract(total.frames, background.frames)
    assert np.array_equal(scattered, np.zeros_like(scattered))
    assert total.pec_edges == background.pec_edges


def test_scattered_field_is_large_and_forward_peaked(
        result: scatter.ScatterResult) -> None:
    """The body response is big, radiated downstream, and zero on the PEC."""
    assert result.peak_scattered > 0.05 * result.peak_total

    x = np.asarray(result.cc.grid.x, dtype=float)
    cx, cy = result.setup.centre
    energy = np.asarray(result.ez_scattered, dtype=float) ** 2
    i, j = np.unravel_index(int(np.argmax(energy)), energy.shape)
    assert x[i] > cx                      # forward scattering at ka = 3
    assert energy[x > cx].sum() / energy.sum() > 0.2

    # The PEC condition the mask claims: Ez is exactly zero on every pinned node.
    pinned = _mask2d(result.cc, result.mask)
    assert pinned.any()
    assert np.all(np.asarray(result.ez_total, dtype=float)[pinned] == 0.0)
