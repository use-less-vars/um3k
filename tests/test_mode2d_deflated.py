"""Plumbing tests for :func:`emfit.mode2d.solve_modes_deflated`.

These are wiring tests, not acceptance tests: they say the deflated route
builds ``Z`` and ``R`` as documented, that ``R`` really is the ``B``-orthogonal
complement of ``Z``, that the solver returns a :class:`~emfit.mode2d.Mode2D`
carrying the ``deflation`` diagnostics, and that ``solve_modes`` (the undeflated
route) still returns what it returned before the deflation work was added.  No
pre-registered geometry is used and no acceptance number is asserted; every
mesh here is a homogeneous synthetic box of 4-5 cells per side, so each test
runs in well under a second.

The one hard-coded number is ``REGRESSION_BETA_SQ`` below, measured from the
undeflated solver at the time this file was written (see its comment).
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit import mode2d as m2

#: The walls sit exactly on coordinates, so the node predicates need far less
#: slack than a cell edge.
WALL_TOL = 1e-12

#: ``Z^T B R == 0`` and ``R^T B R == I`` are exact identities of the
#: construction (``emfit/mode2d.py`` ``_complement_basis``); this bound is what
#: roundoff on a small mesh actually satisfies, with room to spare.
ORTHO_TOL = 1e-12

#: The three scale-free residuals of the gradient columns against the pencil.
#: On a homogeneous box the gradient space is an exact null space of
#: ``k0^2 M_eps - K_q``, so these are pure roundoff.
RESIDUAL_TOL = 1e-12

#: ``solve_modes`` value recorded before the deflation dispatch, on the fixed
#: case built by :func:`_tiny_box` with ``k0^2 = 5``, ``sigma = 0.5``, ``k = 2``:
#: the deflated machinery is supposed to leave the undeflated path untouched.
#: Measured 2026-10-28 on a 4 x 4 cell ``2.0 x 1.0`` box (the median of four
#: repeats, which agreed to 5e-15 relative).
REGRESSION_BETA_SQ = 2.528401365660726

#: Relative band on that regression value -- eigsh starts from a random vector,
#: so the last few digits move between runs.
REGRESSION_RTOL = 1e-9


def _walls(lx, ly):
    """Four PEC node predicates, one per wall of the ``lx x ly`` box."""
    return (
        lambda p: np.abs(p[:, 0] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 0] - lx) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - ly) <= WALL_TOL,
    )


def _tiny_box(nx, ny, lx, ly):
    """A homogeneous ``nx x ny`` cell box with its four PEC wall predicates."""
    mesh = m2.box_mesh(lx, ly, nx, ny)
    return mesh, _walls(lx, ly)


def _gradient_basis(mesh, boundaries):
    """``(free, B_free, cols, Z, R, info)``, assembled the way the solver does.

    ``Z`` and ``R`` stay internal to :func:`solve_modes_deflated`, so the shape
    and orthogonality checks rebuild them from the same private helpers that
    solver calls.
    """
    eps_t = m2._per_triangle(1.0, mesh, "eps_r")
    mu_t = m2._per_triangle(1.0, mesh, "mu_r")
    _k_q, m_mu, _m_eps = m2.assemble(mesh, eps_r=eps_t, mu_r=mu_t)
    mask = m2.pec_edge_mask(mesh, boundaries)
    free = np.flatnonzero(~mask)
    b_free = m_mu[free][:, free]
    cols = m2._gradient_columns(
        mesh, eps_t, mu_t, m2.pec_node_mask(mesh, boundaries)
    )
    z = m2._incidence(mesh, free, cols)
    r, info = m2._complement_basis(b_free, z)
    return free, b_free, cols, z, r, info


# ---------------------------------------------------------------------------
# (a) shapes, and the two identities that define R
# ---------------------------------------------------------------------------
def test_gradient_basis_shapes_and_b_orthogonality():
    """``Z`` is (n_free, z_dim), ``R`` is the ``B``-orthogonal complement."""
    nx = ny = 4
    mesh, boundaries = _tiny_box(nx, ny, 1.0, 1.0)
    free, b_free, cols, z, r, info = _gradient_basis(mesh, boundaries)

    n_free = int(free.size)
    z_dim = int(info["z_dim"])
    p = int(r.shape[1])

    # on a homogeneous box every node strictly inside carries a gradient column
    inside = np.flatnonzero(
        (mesh.nodes[:, 0] > WALL_TOL)
        & (mesh.nodes[:, 0] < 1.0 - WALL_TOL)
        & (mesh.nodes[:, 1] > WALL_TOL)
        & (mesh.nodes[:, 1] < 1.0 - WALL_TOL)
    )
    assert np.array_equal(np.sort(cols), inside)
    assert z.shape == (n_free, (nx - 1) * (ny - 1))
    assert r.shape == (n_free, n_free - (nx - 1) * (ny - 1))
    assert p == n_free - z_dim

    ztb = z.T @ b_free
    orth_scale = float(np.linalg.norm(ztb.toarray())) * float(np.linalg.norm(r))
    orth_rel = float(np.linalg.norm(ztb @ r)) / orth_scale
    assert orth_rel <= ORTHO_TOL, f"||Z^T B R|| relative = {orth_rel!r}"

    gram_dev = float(
        np.linalg.norm(r.T @ (b_free @ r) - np.eye(p)) / np.sqrt(p)
    )
    assert gram_dev <= ORTHO_TOL, f"||R^T B R - I||_F/sqrt(p) = {gram_dev!r}"

    # the same two numbers are what the helper reports
    assert info["z_orthogonality_rel"] <= ORTHO_TOL
    assert float(info["r_gram_dev"]) <= ORTHO_TOL


# ---------------------------------------------------------------------------
# (b) the column count of the gradient space on a homogeneous box
# ---------------------------------------------------------------------------
def test_z_dim_is_interior_node_count():
    """``deflation['z_dim'] == (nx-1)(ny-1)`` on a homogeneous PEC box."""
    nx = ny = 5
    mesh, boundaries = _tiny_box(nx, ny, 2.0, 1.0)
    res = m2.solve_modes_deflated(
        mesh, float(np.sqrt(5.0)), 4.0, boundaries=boundaries, k=3
    )
    info = res.deflation
    assert info["z_dim"] == (nx - 1) * (ny - 1)
    assert info["n_free"] == info["n_dof"]
    assert info["n_columns"] == info["n_free"] - info["z_dim"]
    # ny = 5 is not a multiple of 4, so the ladder closed form does not apply
    assert info["z_dim_closed_form"] is None


# ---------------------------------------------------------------------------
# (c) the returned mode, its diagnostics, and the undeflated regression
# ---------------------------------------------------------------------------
def test_deflated_solve_returns_diagnostics_and_selection():
    """The deflated solve returns a mode with diagnostics and a curl-acceptable pick."""
    nx = ny = 5
    mesh, boundaries = _tiny_box(nx, ny, 2.0, 1.0)
    res = m2.solve_modes_deflated(
        mesh, float(np.sqrt(5.0)), 4.0, boundaries=boundaries, k=3
    )
    assert isinstance(res, m2.Mode2D)

    info = res.deflation
    assert isinstance(info, dict)
    assert info["z_dim"] > 0
    assert info["n_columns"] == info["n_free"] - info["z_dim"]
    for key in ("residual_grad", "residual_eps_mu", "residual_pencil"):
        value = float(info[key])
        assert np.isfinite(value)
        assert value <= RESIDUAL_TOL, f"{key} = {value!r}"

    # the chosen candidate passed the curl filter of _select_and_pack
    ratios = np.abs(np.asarray(res.curl_ratio, dtype=float))
    assert ratios[res.chosen] >= m2._CURL_RTOL * float(ratios.max())
    assert ratios[res.chosen] > 0.0
    assert res.candidates[res.chosen][0] == pytest.approx(res.beta_sq)

    # and the undeflated route still returns the value recorded before this work
    tiny, tiny_walls = _tiny_box(4, 4, 2.0, 1.0)
    reg = m2.solve_modes(
        tiny, float(np.sqrt(5.0)), 0.5, boundaries=tiny_walls, k=2
    )
    assert reg.beta_sq == pytest.approx(REGRESSION_BETA_SQ, rel=REGRESSION_RTOL)
