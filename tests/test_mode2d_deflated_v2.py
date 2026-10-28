"""Plumbing tests for the Amendment 3 (5.b) widened deflation route.

These are wiring tests, not acceptance tests, in the style of
``tests/test_mode2d_deflated.py`` (which is left untouched and is not imported
from).  They pin the *structure* of the widened column set
(:func:`emfit.mode2d._deflation_columns` with ``widen=True`` and the public
:func:`emfit.mode2d.solve_modes_deflated_v2`) on the real pre-registered ladder
geometry, and they pin the v1 route to the numbers recorded in
``.scratch/d47/out/deflated_level1.json`` so that a future edit to the v2 path
cannot silently move the v1 path.

The widened set is a *census licence*, not an exactness claim: its columns are
the interior nodes of both homogeneous blocks, and only the ``eps_r == 1/mu_r``
block is an exact null space of the pencil.  The construction identities
(``Z^T B R == 0``, ``R^T B R == I``) therefore still hold exactly -- ``Z`` is an
exact column space -- while ``residual_eps_mu`` / ``residual_pencil`` are
expected to be *non-zero* and are deliberately not asserted here.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from emfit import mode2d as m2

# --- the pre-registered ladder geometry (tools/host/anchor/ladder.py) --------
B = 2.0**-7          # slab height b = 0.0078125 m
A = B / 8.0          # box width a = b/8
T = B / 4.0          # slab thickness t = b/4
EPS_R = 2.0          # slab permittivity
K0 = 448.0 * np.pi   # k0 = 448*pi rad/m
SIGMA = 0.5 * K0 * K0

#: ``level -> (nx, ny)`` of the pre-registered ladder (``ny // 8 == nx``).
LEVELS = {1: (2, 16), 2: (4, 32), 3: (8, 64)}

#: Measured ``z_dim`` of the two column sets on levels 1-3, and the number of
#: columns the widening adds (``(nx-1)(ny-2)``, ``(nx-1)(3 ny//4 - 1)`` and
#: ``(nx-1)(ny//4 - 1)`` respectively).
V2_Z_DIM = {1: 14, 2: 90, 3: 434}
V1_Z_DIM = {1: 11, 2: 69, 3: 329}
ADDED = {1: 3, 2: 21, 3: 105}

#: The same two construction identities the v1 test file asserts.
ORTHO_TOL = 1e-12

#: The v1 route at level 1, verbatim from ``.scratch/d47/out/deflated_level1.json``
#: (recorded with ``solve_modes_deflated(mesh, K0, 0.5*K0**2, eps_r=..., k=16)``).
ANCHOR_Z_DIM = 11
ANCHOR_N_COLUMNS = 67
ANCHOR_BLOCK_DIAG_RATIO = 0.9659258262891854
ANCHOR_Z_ORTH_ABS = 1.2157219620641853e-15
ANCHOR_RESIDUAL_PENCIL = 4.4489541781437845e-18


def _ladder_mesh(level):
    """``(mesh, eps_r_callable, boundaries, nx, ny)`` of a ladder level.

    Reproduces ``tools/host/anchor/ladder.py::build_mesh`` verbatim (including
    its four wall predicates), so the numbers below are the pre-registered ones
    and not a look-alike box.
    """
    nx, ny = LEVELS[level]
    xs = A * np.arange(nx + 1) / nx
    ys = B * np.arange(ny + 1) / ny
    mesh = m2.structured_mesh(xs, ys)
    assert np.any(ys == T), f"level {level}: interface y = T is not a node line"
    eps_r_callable = lambda c: np.where(c[:, 1] < T, EPS_R, 1.0)   # noqa: E731
    boundaries = (
        lambda P: P[:, 1] == 0.0,      # y = 0
        lambda P: P[:, 1] == B,        # y = b
        lambda P: P[:, 0] == 0.0,      # x = 0
        lambda P: P[:, 0] == A,        # x = a
    )
    return mesh, eps_r_callable, boundaries, nx, ny


def _columns(mesh, eps_r_callable, boundaries, widen):
    """``(cols, info)`` from ``_deflation_columns``, fed the way the solver feeds it."""
    eps_t = m2._per_triangle(eps_r_callable, mesh, "eps_r")
    mu_t = m2._per_triangle(1.0, mesh, "mu_r")
    return m2._deflation_columns(
        mesh, eps_t, mu_t, m2.pec_node_mask(mesh, boundaries), widen=widen
    )


def _node_mask(mesh, cols):
    """Per-node boolean mask of the nodes ``cols``."""
    mask = np.zeros(mesh.n_nodes, dtype=bool)
    mask[cols] = True
    return mask


def _rows_of(mesh, nodes):
    """The ``y``-grid level indices occupied by the nodes ``nodes``, ascending."""
    ys = np.asarray(mesh.grid_axes[1], dtype=float).ravel()
    y = np.asarray(mesh.nodes, dtype=float)[np.asarray(nodes, dtype=np.int64), 1]
    level = np.abs(y[:, None] - ys[None, :]).argmin(axis=1)
    return sorted(int(v) for v in np.unique(level))


# ---------------------------------------------------------------------------
# (a) the widened count, against both the closed form and the literal number
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("level", sorted(LEVELS))
def test_v2_z_dim_matches_closed_form(level):
    """``len(cols) == (nx-1)(ny-2) == z_dim_v2 == _closed_form_dim_v2``."""
    mesh, eps, boundaries, nx, ny = _ladder_mesh(level)
    cols, info = _columns(mesh, eps, boundaries, widen=True)
    law = (nx - 1) * (ny - 2)

    assert info["column_region"] == "v1+homogeneous-blocks", (
        f"level {level}: widen=True must report the widened region, "
        f"got {info['column_region']!r}"
    )
    assert len(cols) == law, (
        f"level {level}: len(cols) = {len(cols)!r}, closed form (nx-1)(ny-2) = {law!r}"
    )
    assert len(cols) == V2_Z_DIM[level], (
        f"level {level}: len(cols) = {len(cols)!r}, measured ladder value "
        f"{V2_Z_DIM[level]!r}"
    )
    assert info["z_dim_v2"] == len(cols), (
        f"level {level}: info['z_dim_v2'] = {info['z_dim_v2']!r}, "
        f"len(cols) = {len(cols)!r}"
    )
    assert m2._closed_form_dim_v2(mesh, _node_mask(mesh, cols)) == law, (
        f"level {level}: _closed_form_dim_v2 on the widened mask disagrees with "
        f"(nx-1)(ny-2) = {law!r}"
    )


# ---------------------------------------------------------------------------
# (b) the default route is the pre-registered one, and is not the v2 set
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("level", sorted(LEVELS))
def test_v1_z_dim_unchanged(level):
    """``widen=False`` still yields ``(nx-1)(3 ny//4 - 1)`` = 11 / 69 / 329."""
    mesh, eps, boundaries, nx, ny = _ladder_mesh(level)
    cols, info = _columns(mesh, eps, boundaries, widen=False)
    law = (nx - 1) * (3 * ny // 4 - 1)

    assert info["column_region"] == "v1", (
        f"level {level}: widen=False must report region 'v1', "
        f"got {info['column_region']!r}"
    )
    assert len(cols) == law, (
        f"level {level}: v1 len(cols) = {len(cols)!r}, closed form "
        f"(nx-1)(3 ny//4 - 1) = {law!r}"
    )
    assert len(cols) == V1_Z_DIM[level], (
        f"level {level}: v1 len(cols) = {len(cols)!r}, measured ladder value "
        f"{V1_Z_DIM[level]!r}"
    )
    assert m2._closed_form_dim_v2(mesh, _node_mask(mesh, cols)) is None, (
        f"level {level}: _closed_form_dim_v2 must reject the v1 mask, but it "
        "returned a number"
    )


# ---------------------------------------------------------------------------
# (c) what the widening actually adds: the substrate rows, minus the interface
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("level", sorted(LEVELS))
def test_added_block_is_substrate_rows_excluding_interface(level):
    """The added columns are rows ``1 .. ny//4 - 1``; row ``ny//4`` (y = T) is in neither."""
    mesh, eps, boundaries, nx, ny = _ladder_mesh(level)
    cols_v1, info_v1 = _columns(mesh, eps, boundaries, widen=False)
    cols_v2, info_v2 = _columns(mesh, eps, boundaries, widen=True)
    added = np.setdiff1d(cols_v2, cols_v1, assume_unique=True)
    law = (nx - 1) * (ny // 4 - 1)

    assert added.size == law, (
        f"level {level}: added {added.size!r} columns, closed form "
        f"(nx-1)(ny//4 - 1) = {law!r}"
    )
    assert added.size == ADDED[level], (
        f"level {level}: added {added.size!r} columns, measured ladder value "
        f"{ADDED[level]!r}"
    )
    assert info_v2["columns_added"] == added.size, (
        f"level {level}: info['columns_added'] = {info_v2['columns_added']!r}, "
        f"set difference = {added.size!r}"
    )
    assert np.array_equal(np.setdiff1d(cols_v2, added), cols_v1), (
        f"level {level}: removing the added columns from the widened set must "
        "give the v1 set back"
    )
    assert np.array_equal(np.union1d(cols_v1, added), cols_v2), (
        f"level {level}: v1 set union the added columns must be the widened set"
    )
    assert info_v1["z_dim_v2"] == cols_v2.size, (
        f"level {level}: info['z_dim_v2'] = {info_v1['z_dim_v2']!r} even on the "
        f"v1 route, expected {cols_v2.size!r}"
    )
    assert info_v2["region_rows"] == list(range(1, ny // 4)), (
        f"level {level}: region_rows = {info_v2['region_rows']!r}, expected the "
        f"substrate rows {list(range(1, ny // 4))!r}"
    )
    assert info_v2["region_contrast"] == [EPS_R - 1.0], (
        f"level {level}: region_contrast = {info_v2['region_contrast']!r}, "
        f"expected [EPS_R - 1] = {[EPS_R - 1.0]!r}"
    )

    interface_row = ny // 4
    rows_v1 = _rows_of(mesh, cols_v1)
    rows_v2 = _rows_of(mesh, cols_v2)
    assert interface_row not in rows_v1, (
        f"level {level}: the interface row {interface_row!r} (y = T) must not "
        f"carry a v1 column; v1 rows are {rows_v1!r}"
    )
    assert interface_row not in rows_v2, (
        f"level {level}: the interface row {interface_row!r} (y = T) must not "
        f"carry a v2 column; v2 rows are {rows_v2!r}"
    )
    assert rows_v2 == sorted(set(rows_v1) | set(range(1, ny // 4))), (
        f"level {level}: v2 rows {rows_v2!r} must be the v1 rows {rows_v1!r} "
        f"plus the substrate rows {list(range(1, ny // 4))!r}"
    )


# ---------------------------------------------------------------------------
# (d) the widened Z is still an exact column space: the two defining identities
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("level", [1, 2])
def test_v2_b_orthogonality(level):
    """``Z^T B R == 0`` and ``R^T B R == I`` hold for the widened ``Z`` too."""
    mesh, eps, boundaries, nx, ny = _ladder_mesh(level)
    eps_t = m2._per_triangle(eps, mesh, "eps_r")
    mu_t = m2._per_triangle(1.0, mesh, "mu_r")
    _k_q, m_mu, _m_eps = m2.assemble(mesh, eps_r=eps_t, mu_r=mu_t)
    free = np.flatnonzero(~m2.pec_edge_mask(mesh, boundaries))
    b_free = m_mu[free][:, free]

    cols, info_cols = _columns(mesh, eps, boundaries, widen=True)
    z = m2._incidence(mesh, free, cols)
    r, info = m2._complement_basis(b_free, z)
    p = int(r.shape[1])

    assert z.shape == (free.size, V2_Z_DIM[level]), (
        f"level {level}: Z is {z.shape!r}, expected {(free.size, V2_Z_DIM[level])!r}"
    )
    assert info["z_dim"] == info_cols["z_dim_v2"], (
        f"level {level}: _complement_basis saw z_dim {info['z_dim']!r}, "
        f"_deflation_columns reported {info_cols['z_dim_v2']!r}"
    )
    assert p == free.size - info["z_dim"], (
        f"level {level}: R has {p!r} columns, expected n_free - z_dim = "
        f"{free.size - info['z_dim']!r}"
    )

    ztb = z.T @ b_free
    orth_rel = float(np.linalg.norm(ztb @ r)) / (
        float(np.linalg.norm(ztb.toarray())) * float(np.linalg.norm(r))
    )
    assert orth_rel <= ORTHO_TOL, (
        f"level {level}: ||Z^T B R|| relative = {orth_rel!r} > {ORTHO_TOL!r}"
    )

    gram_dev = float(np.linalg.norm(r.T @ (b_free @ r) - np.eye(p)) / np.sqrt(p))
    assert gram_dev <= ORTHO_TOL, (
        f"level {level}: ||R^T B R - I||_F/sqrt(p) = {gram_dev!r} > {ORTHO_TOL!r}"
    )


# ---------------------------------------------------------------------------
# (e) the public v2 entry point, its diagnostics, and its non-zero residuals
# ---------------------------------------------------------------------------
def test_v2_solve_diagnostics():
    """``solve_modes_deflated_v2`` reports the widened set and a finite spectrum.

    ``residual_eps_mu`` and ``residual_pencil`` are *expected to be non-zero*
    here: the widened block is a census licence, not the pencil null space.  Only
    ``residual_grad`` is asserted, because a gradient field has no curl whatever
    the contrast.
    """
    mesh, eps, boundaries, nx, ny = _ladder_mesh(1)
    assert "solve_modes_deflated_v2" in m2.__all__, (
        "solve_modes_deflated_v2 must be exported in emfit.mode2d.__all__"
    )

    res = m2.solve_modes_deflated_v2(
        mesh, K0, SIGMA, eps_r=eps, boundaries=boundaries, k=16
    )
    info = res.deflation

    assert isinstance(res, m2.Mode2D), f"got {type(res)!r}, expected Mode2D"
    assert info["z_dim"] == V2_Z_DIM[1], (
        f"level 1 v2: z_dim = {info['z_dim']!r}, expected {V2_Z_DIM[1]!r}"
    )
    assert info["n_free"] == 78, f"level 1 v2: n_free = {info['n_free']!r}, expected 78"
    assert info["n_columns"] == 64, (
        f"level 1 v2: n_columns = {info['n_columns']!r}, expected 64"
    )
    assert info["n_columns"] == info["n_free"] - info["z_dim"], (
        f"level 1 v2: n_columns {info['n_columns']!r} != n_free - z_dim "
        f"{info['n_free'] - info['z_dim']!r}"
    )
    assert info["z_dim_closed_form_v2"] == V2_Z_DIM[1], (
        f"level 1 v2: z_dim_closed_form_v2 = {info['z_dim_closed_form_v2']!r}, "
        f"expected {V2_Z_DIM[1]!r}"
    )
    assert info["residual_grad"] == 0.0, (
        f"level 1 v2: residual_grad = {info['residual_grad']!r}, expected exactly "
        "0.0 (a gradient field has no curl)"
    )
    assert np.isfinite(info["residual_eps_mu"]) and np.isfinite(
        info["residual_pencil"]
    ), "level 1 v2: the widened-route residuals must be finite numbers"

    assert len(res.candidates) == 16, (
        f"level 1 v2: {len(res.candidates)!r} candidates, expected k = 16"
    )
    for beta_sq, eps_eff in res.candidates:
        assert np.isfinite(beta_sq) and np.isfinite(eps_eff), (
            f"level 1 v2: non-finite candidate ({beta_sq!r}, {eps_eff!r})"
        )
    assert 0 <= res.chosen < len(res.candidates), (
        f"level 1 v2: chosen index {res.chosen!r} out of range"
    )
    assert np.isfinite(res.beta_sq) and np.isfinite(res.residual), (
        f"level 1 v2: non-finite selected mode beta_sq={res.beta_sq!r} "
        f"residual={res.residual!r}"
    )


# ---------------------------------------------------------------------------
# (f) the v1 route is the default, and still lands on the d47 anchor
# ---------------------------------------------------------------------------
def test_v1_route_is_the_default():
    """``region_widen`` defaults to ``False`` and the v1 numbers are the d47 anchor."""
    default = inspect.signature(m2.solve_modes_deflated).parameters["region_widen"]
    assert default.default is False, (
        f"solve_modes_deflated's region_widen default is {default.default!r}, "
        "expected False (the preregistered set verbatim)"
    )

    mesh, eps, boundaries, nx, ny = _ladder_mesh(1)
    res = m2.solve_modes_deflated(mesh, K0, SIGMA, eps_r=eps, boundaries=boundaries, k=16)
    info = res.deflation

    assert info["column_region"] == "v1", (
        f"level 1 default route: column_region = {info['column_region']!r}, "
        "expected 'v1'"
    )
    assert info["z_dim"] == ANCHOR_Z_DIM, (
        f"level 1 default route: z_dim = {info['z_dim']!r}, d47 anchor "
        f"{ANCHOR_Z_DIM!r}"
    )
    assert info["n_columns"] == ANCHOR_N_COLUMNS, (
        f"level 1 default route: n_columns = {info['n_columns']!r}, d47 anchor "
        f"{ANCHOR_N_COLUMNS!r}"
    )
    assert info["block_diag_ratio"] == ANCHOR_BLOCK_DIAG_RATIO, (
        f"level 1 default route: block_diag_ratio = {info['block_diag_ratio']!r}, "
        f"d47 anchor {ANCHOR_BLOCK_DIAG_RATIO!r}"
    )
    assert info["z_orthogonality_abs"] == ANCHOR_Z_ORTH_ABS, (
        f"level 1 default route: z_orthogonality_abs = "
        f"{info['z_orthogonality_abs']!r}, d47 anchor {ANCHOR_Z_ORTH_ABS!r}"
    )
    assert info["residual_pencil"] == ANCHOR_RESIDUAL_PENCIL, (
        f"level 1 default route: residual_pencil = {info['residual_pencil']!r}, "
        f"d47 anchor {ANCHOR_RESIDUAL_PENCIL!r}"
    )
    assert info["z_dim_closed_form_v2"] is None, (
        f"level 1 default route: z_dim_closed_form_v2 = "
        f"{info['z_dim_closed_form_v2']!r}, expected None on the v1 column set"
    )
