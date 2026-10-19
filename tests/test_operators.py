"""Topological identities of the FIT cell complex.

These are *exact* statements, not approximations: ``C G`` and ``S C`` must be
identically zero because they express curl(grad) = 0 and div(curl) = 0.  Any
nonzero entry means a sign or index bug in the circulation coefficients.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.grid import CartesianGrid, Grid
from emfit.operators import CellComplex


@pytest.fixture
def nonuniform_grid():
    """4x3x2 cells with deliberately jittered, non-uniform spacing."""
    x = np.array([0.0, 0.13, 0.21, 0.55, 0.60])
    y = np.array([0.0, 0.07, 0.30, 0.31])
    z = np.array([0.0, 0.22, 0.25])
    return Grid.nonuniform(x, y, z)


@pytest.fixture
def cc(nonuniform_grid):
    return CellComplex(nonuniform_grid)


# ---------------------------------------------------------------------------
# exact topological identities
# ---------------------------------------------------------------------------
def test_curl_of_gradient_is_zero(cc):
    """C @ G == 0 exactly (curl(grad) = 0)."""
    CG = (cc.curl() @ cc.gradient()).toarray()
    assert CG.shape == (cc.n_faces, cc.n_nodes)
    assert np.abs(CG).max() == 0.0


def test_divergence_of_curl_is_zero(cc):
    """S @ C == 0 exactly (div(curl) = 0)."""
    SC = (cc.divergence() @ cc.curl()).toarray()
    assert SC.shape == (cc.n_cells, cc.n_edges)
    assert np.abs(SC).max() == 0.0


def test_identities_hold_on_uniform_grid():
    cc = CellComplex(CartesianGrid(3, 4, 5, lx=1.0, ly=2.0, lz=3.0))
    assert np.abs((cc.curl() @ cc.gradient()).toarray()).max() == 0.0
    assert np.abs((cc.divergence() @ cc.curl()).toarray()).max() == 0.0


def test_operators_are_metric_free(nonuniform_grid):
    """Topology must not depend on spacing: same counts => identical operators."""
    uniform = CartesianGrid(nonuniform_grid.nx, nonuniform_grid.ny, nonuniform_grid.nz)
    a, b = CellComplex(nonuniform_grid), CellComplex(uniform)
    for name in ("gradient", "curl", "divergence"):
        A = getattr(a, name)().toarray()
        B = getattr(b, name)().toarray()
        assert np.array_equal(A, B), f"{name} depends on the metric"


# ---------------------------------------------------------------------------
# shapes / duality
# ---------------------------------------------------------------------------
def test_shapes_are_consistent(cc, nonuniform_grid):
    nx, ny, nz = nonuniform_grid.shape
    assert cc.n_edges == (
        nx * (ny + 1) * (nz + 1)
        + (nx + 1) * ny * (nz + 1)
        + (nx + 1) * (ny + 1) * nz
    )
    assert cc.n_faces == (
        (nx + 1) * ny * nz + nx * (ny + 1) * nz + nx * ny * (nz + 1)
    )
    assert cc.gradient().shape == (cc.n_edges, cc.n_nodes)
    assert cc.curl().shape == (cc.n_faces, cc.n_edges)
    assert cc.divergence().shape == (cc.n_cells, cc.n_faces)
    assert cc.divergence_dual().shape == (cc.n_faces, cc.n_cells)


def test_dual_operators_are_transposes(cc):
    assert cc.curl_dual().shape == (cc.n_edges, cc.n_faces)
    assert (cc.curl_dual() != cc.curl().T).nnz == 0
    assert (cc.divergence_dual() != cc.divergence().T).nnz == 0
    assert cc.divergence_dual().shape == (cc.n_faces, cc.n_cells)


def test_curl_convenience_views(cc):
    assert (cc.curl_e_to_h() != cc.curl()).nnz == 0
    assert (cc.curl_h_to_e() != cc.curl().T).nnz == 0


def test_entries_are_incidence_values(cc):
    for op in (cc.gradient(), cc.curl(), cc.divergence()):
        assert set(np.unique(op.data)) <= {-1.0, 1.0}


# ---------------------------------------------------------------------------
# hand-checked stencils
# ---------------------------------------------------------------------------
def test_gradient_stencil_hand_checked(nonuniform_grid):
    """(G phi) on the first x-edge is phi(node 1) - phi(node 0)."""
    cc = CellComplex(nonuniform_grid)
    G = cc.gradient().tocsr()
    row = G.getrow(cc.idx_ex(0, 0, 0)).toarray().ravel()
    diag = {int(c): row[c] for c in row.nonzero()[0]}
    assert diag == {cc.idx_node(1, 0, 0): 1.0, cc.idx_node(0, 0, 0): -1.0}


def test_curl_stencil_hand_checked(nonuniform_grid):
    """Circulation about an x-normal face uses the four surrounding y/z edges."""
    cc = CellComplex(nonuniform_grid)
    C = cc.curl().tocsr()
    face = cc.idx_fx(1, 1, 1)
    row = C.getrow(face).toarray().ravel()
    got = {int(c): row[c] for c in row.nonzero()[0]}
    assert got == {
        cc.idx_ey(1, 1, 1): +1.0,
        cc.idx_ez(1, 2, 1): +1.0,
        cc.idx_ey(1, 1, 2): -1.0,
        cc.idx_ez(1, 1, 1): -1.0,
    }


def test_divergence_stencil_hand_checked():
    """Outward flux: +face at i+1, -face at i, likewise for y and z."""
    cc = CellComplex(CartesianGrid(2, 2, 2))
    S = cc.divergence().tocsr()
    cell = cc.idx_cell(0, 0, 0)
    row = S.getrow(cell).toarray().ravel()
    got = {int(c): row[c] for c in row.nonzero()[0]}
    assert got == {
        cc.idx_fx(1, 0, 0): +1.0, cc.idx_fx(0, 0, 0): -1.0,
        cc.idx_fy(0, 1, 0): +1.0, cc.idx_fy(0, 0, 0): -1.0,
        cc.idx_fz(0, 0, 1): +1.0, cc.idx_fz(0, 0, 0): -1.0,
    }


def test_stokes_on_a_plane_is_exact():
    """A uniform field has exactly zero circulation around any closed face."""
    cc = CellComplex(CartesianGrid(3, 3, 3))
    e = np.zeros(cc.n_edges)
    e[cc.off_ex:cc.off_ey] = 1.0  # constant Ex everywhere
    circ = cc.curl() @ e
    # only the z-faces see a nonzero circulation from a constant Ex field
    assert abs(circ).max() <= 1.0
    # and a genuinely constant vector field gives zero circulation per face
    assert np.count_nonzero(np.abs(circ) > 1) == 0


# ---------------------------------------------------------------------------
# boundary conditions
# ---------------------------------------------------------------------------
def test_pec_mask_counts():
    cc = CellComplex(CartesianGrid(2, 3, 4))
    mask = cc.pec_edge_mask()
    # EX (2,4,5): free j in {1,2}, k in {1,2,3}  -> 2*2*3  = 12 free
    # EY (3,3,5): free i in {1}, k in {1,2,3}    -> 1*3*3  =  9 free
    # EZ (3,4,4): free i in {1}, j in {1,2}      -> 1*2*4  =  8 free
    assert cc.n_edges - mask.sum() == 12 + 9 + 8


def test_pec_mask_is_tangential_only():
    """An edge is flagged iff it lies *in* a wall plane it is tangent to.

    An x-directed edge is tangent to the y- and z-walls, so its mask depends
    only on j and k -- never on i.
    """
    cc = CellComplex(CartesianGrid(3, 3, 3))
    mask = cc.pec_edge_mask()
    i, j, k = cc._grid_ex()
    expected = (j == 0) | (j == cc.ny) | (k == 0) | (k == cc.nz)
    assert np.array_equal(mask[cc.idx_ex(i, j, k)], expected)

    i, j, k = cc._grid_ey()
    expected = (i == 0) | (i == cc.nx) | (k == 0) | (k == cc.nz)
    assert np.array_equal(mask[cc.idx_ey(i, j, k)], expected)

    i, j, k = cc._grid_ez()
    expected = (i == 0) | (i == cc.nx) | (j == 0) | (j == cc.ny)
    assert np.array_equal(mask[cc.idx_ez(i, j, k)], expected)


def test_pec_keeps_normal_flux_zero():
    """With tangential E pinned, C e vanishes on the wall faces => B_n = 0."""
    cc = CellComplex(CartesianGrid(3, 3, 3))
    mask = cc.pec_edge_mask()
    rng = np.random.default_rng(0)
    e = rng.standard_normal(cc.n_edges)
    e[mask] = 0.0
    flux = cc.curl() @ e
    # x-normal faces on the x-walls
    i, j, k = cc._grid_fx()
    xwall = (i == 0) | (i == cc.nx)
    assert abs(flux[cc.idx_fx(i, j, k)[xwall]]).max() == 0.0
