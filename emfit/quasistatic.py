"""Quasi-static (2-D Laplace) cross-sections of transmission lines.

This module solves the *static* problem on a cross-section of a line whose
geometry is invariant along one axis, the **line axis**.  No time stepping, no
ports, no PML: the unknown is a scalar potential ``phi`` in the transverse
plane,

    K phi = 0        in the dielectric,
    phi   = V_i      on conductor ``i`` (Dirichlet),
    d phi / d n = 0  on the outer walls (homogeneous Neumann),

with ``K = G^T diag(m_eps) G`` the 2-D Laplacian assembled from the library's
own Hodge star (:func:`emfit.materials.material_matrices`, which supplies
``m_eps[e] = eps_r(e) * EPS0 * A~_e / L_e``) restricted to the transverse edge
families.  The capacitance of a ``length``-long section is the electrostatic
energy ``phi^T K phi / V^2``, hence

    C' = phi^T K phi / (V^2 * length)                                   [F/m]

with ``V`` the applied potential *difference* ``max(v) - min(v)`` and ``length``
the **cell width along the line axis** -- the only longitudinal length the mass
matrix knows about, so it is read off the grid and never chosen by the caller.
A section meshed with a line-axis cell twice as wide carries twice the
``m_eps``, and normalising by twice the length hands back the same ``C'``.
From ``C'`` the quasi-TEM line parameters follow: ``eps_eff = C'/C'_air`` and
``Z0 = 1/(C0 * C'_air)``.

Grid convention
---------------
The grid must be **one cell thick and periodic along the line axis** -- exactly
one entry of ``grid.periodic`` may be ``True``.  The transverse plane is then
the other two axes, in ``xyz`` order, and a node of the section is addressed by
:func:`node_index` / shaped by :func:`node_shape`.  The periodic axis makes the
section infinitely long: the dual width along it is the full cell width, not a
truncated half cell, so ``C'`` does not depend on how the section is truncated
along the line.

Limitations -- read before trusting a number
--------------------------------------------
* **Permittivity assignment on an interface.** ``eps_r`` is a per-*edge*
  quantity, but an edge lying *in* a material interface has a dual face that
  straddles two materials, and the energy-consistent value there is their
  dual-face average -- the arithmetic mean on a uniform grid.  Two traps
  follow.  (a) A callable ``eps_r(x, y, z)`` is sampled at the edge *centre*,
  which on a node-plane interface sits exactly *on* the interface, so a test
  like ``z < h`` silently selects one branch.  On the microstrip of
  ``tests/test_quasistatic.py`` that misassignment costs about 6% of ``C'``
  and, because the misassigned edges stay on the interface as the mesh is
  refined, the error does **not** converge away.  (b) If the interface is not
  on a node plane, every edge of the family normal to it lies *inside* a cell
  and the potential step across the interface is not represented at all.  Build
  the ``cc.n_edges``-long array explicitly (:func:`material_matrices` accepts
  it) whenever an interface exists; the microstrip tests do exactly that.
* **Geometry.** Conductor thickness and finite conductivity are not modelled:
  a conductor is the set of nodes handed to ``fixed``, so a strip one mesh cell
  wide is a strip of width ``n_cells * dx``.  There is no radiation and nothing
  beyond the box, so the Neumann walls must be pushed out until the answer
  stops moving.
* **``eps_eff`` and ``Z0`` are quasi-TEM.** They are exact for the static
  cross-section and ignore dispersion; ``Z0 = Z0_air / sqrt(eps_eff)`` holds by
  construction.
"""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .grid import Grid
from .materials import C0, material_matrices
from .operators import CellComplex

__all__ = [
    "capacitance_per_length",
    "z0_eps_eff",
    "transverse_potential",
    "node_index",
    "node_shape",
]


# ----------------------------------------------------------------------
# geometry of the section
# ----------------------------------------------------------------------
def _line_and_transverse(grid: Grid):
    """Return ``(line_axis, (t1, t2))`` or raise ``ValueError``.

    The section geometry is only meaningful if exactly one axis is periodic
    (the line axis) and the mesh is one cell thick along it: a thicker periodic
    stack would be several identical sections in series, and any variation of
    the material across those layers would be silently discarded here.
    """
    if not isinstance(grid, Grid):
        raise ValueError(
            f"grid must be an emfit.grid.Grid, got {type(grid).__name__}"
        )
    periodic = [a for a in "xyz" if grid.is_periodic(a)]
    if len(periodic) != 1:
        raise ValueError(
            "exactly one axis must be periodic (the line axis), got "
            f"periodic={grid.periodic!r}"
        )
    line = periodic[0]
    thick = grid.shape["xyz".index(line)]
    if thick != 1:
        raise ValueError(
            "the grid must be one cell thick along the periodic line axis "
            f"{line!r}, got {thick} cells"
        )
    transverse = tuple(a for a in "xyz" if a != line)
    return line, transverse


def node_shape(grid: Grid) -> tuple:
    """Shape ``(N1, N2)`` of the transverse node array.

    ``N1`` and ``N2`` are the point-layer counts (:meth:`emfit.grid.Grid.nodes`)
    of the two transverse axes in ``xyz`` order; the line axis drops out because
    it is periodic with a single cell.
    """
    _, transverse = _line_and_transverse(grid)
    return tuple(int(grid.nodes(a)) for a in transverse)


def node_index(grid: Grid, iy: int, iz: int) -> int:
    """Flat node index of transverse node ``(iy, iz)``, C order.

    ``iy`` and ``iz`` are indices along the first and second transverse axis
    (see :func:`node_shape`); the flat index is ``iy * N2 + iz``.
    """
    n1, n2 = node_shape(grid)
    i, j = int(iy), int(iz)
    if not 0 <= i < n1:
        raise ValueError(f"first transverse node index {iy!r} outside [0, {n1})")
    if not 0 <= j < n2:
        raise ValueError(f"second transverse node index {iz!r} outside [0, {n2})")
    return i * n2 + j


def _edge_eps(grid: Grid, cc: CellComplex, eps_r):
    """Expand a callable ``eps_r(x, y, z)`` to one value per primal edge.

    :func:`emfit.materials.material_matrices` samples a callable at the edge
    centre itself, but it builds those centres from the *full* node arrays and
    so cannot handle the periodic line axis, where the seam node is not part of
    the complex.  The sampling rule here is the same one -- cell centres along
    the edge, node values transversely -- with the seam node dropped.
    """
    if not callable(eps_r):
        return eps_r
    out = np.empty(cc.n_edges, dtype=float)
    for axis in "xyz":
        shape = grid.edge_shape(axis)
        coords = []
        for name in "xyz":
            a = getattr(grid, name)
            coords.append(0.5 * (a[:-1] + a[1:]) if name == axis
                          else a[:grid.nodes(name)])
        x, y, z = np.meshgrid(*coords, indexing="ij")
        val = np.asarray(eps_r(x, y, z), dtype=float).ravel()
        count = int(np.prod(shape))
        if val.size == 1:
            val = np.full(count, float(val[0]))
        elif val.size != count:
            raise ValueError(
                f"eps_r callable returned {val.size} values, expected {count}"
            )
        off = getattr(cc, f"off_e{axis}")
        out[off:off + count] = val
    return out


def _transverse_metric(grid: Grid, eps_r):
    """2-D transverse incidence ``G`` and its diagonal ``m``, plus the line axis."""
    line, transverse = _line_and_transverse(grid)
    t1, t2 = transverse
    cc = CellComplex(grid)
    m_eps, _ = material_matrices(grid, cc, eps_r=_edge_eps(grid, cc, eps_r))

    n1_cells = grid.shape["xyz".index(t1)]
    n2_cells = grid.shape["xyz".index(t2)]
    N1, N2 = node_shape(grid)

    def block(axis):
        """``m_eps`` of the edges along ``axis``, layer 0 on the line axis."""
        off = getattr(cc, f"off_e{axis}")
        count = getattr(cc, f"n_e{axis}")
        shaped = np.asarray(m_eps[off:off + count], dtype=float).reshape(
            grid.edge_shape(axis)
        )
        pick = [slice(None)] * 3
        pick["xyz".index(line)] = 0
        return np.ascontiguousarray(shaped[tuple(pick)])

    m1 = block(t1)          # shape (n1_cells, N2)
    m2 = block(t2)          # shape (N1, n2_cells)
    if m1.shape != (n1_cells, N2) or m2.shape != (N1, n2_cells):
        raise ValueError(  # pragma: no cover - structural guard
            f"unexpected edge block shapes {m1.shape} / {m2.shape}"
        )
    m = np.concatenate([m1.ravel(), m2.ravel()])

    # --- incidence: edge = node[head] - node[tail] ----------------------
    n_nodes = N1 * N2
    n_edges = m.size

    def node(i, j):
        i, j = np.broadcast_arrays(np.asarray(i, dtype=int), np.asarray(j, dtype=int))
        return i.ravel() * N2 + j.ravel()

    i1 = np.arange(n1_cells)[:, None]
    j1 = np.arange(N2)[None, :]
    col1 = np.arange(n1_cells * N2).reshape(n1_cells, N2)
    rows1 = np.concatenate([node(i1 + 1, j1), node(i1, j1)])
    cols1 = np.concatenate([col1.ravel(), col1.ravel()])
    vals1 = np.concatenate([np.ones(col1.size), -np.ones(col1.size)])

    i2 = np.arange(N1)[:, None]
    j2 = np.arange(n2_cells)[None, :]
    col2 = n1_cells * N2 + np.arange(N1 * n2_cells).reshape(N1, n2_cells)
    rows2 = np.concatenate([node(i2, j2 + 1), node(i2, j2)])
    cols2 = np.concatenate([col2.ravel(), col2.ravel()])
    vals2 = np.concatenate([np.ones(col2.size), -np.ones(col2.size)])

    G = sp.coo_matrix(
        (np.concatenate([vals1, vals2]),
         (np.concatenate([rows1, rows2]), np.concatenate([cols1, cols2]))),
        shape=(n_nodes, n_edges),
    ).tocsr()
    return G, m, line


def _dirichlet(grid: Grid, fixed):
    """Turn ``[(potential, nodes), ...]`` into ``(isdir, vd, v_scale)``."""
    if fixed is None:
        raise ValueError("fixed must give the conductor potentials, got None")
    try:
        pairs = list(fixed)
    except TypeError:
        raise ValueError(
            "fixed must be a sequence of (potential, node indices) pairs, got "
            f"{fixed!r}"
        ) from None
    if not pairs:
        raise ValueError(
            "fixed is empty: at least two distinct conductor potentials are needed"
        )

    n_nodes = int(np.prod(node_shape(grid)))
    isdir = np.zeros(n_nodes, dtype=bool)
    vd = np.zeros(n_nodes)
    values = []
    for item in pairs:
        try:
            value, nodes = item
        except (TypeError, ValueError):
            raise ValueError(
                "fixed must be a sequence of (potential, node indices) pairs, "
                f"got element {item!r}"
            ) from None
        idx = np.asarray(nodes, dtype=int).ravel()
        if idx.size == 0:
            raise ValueError("a conductor in fixed has no nodes")
        if idx.min() < 0 or idx.max() >= n_nodes:
            raise ValueError(
                f"conductor node indices must lie in [0, {n_nodes}), got "
                f"[{idx.min()}, {idx.max()}]"
            )
        value = float(value)
        isdir[idx] = True
        vd[idx] = value
        values.append(value)

    v_scale = max(values) - min(values)
    if v_scale == 0.0:
        raise ValueError(
            "all conductor potentials are equal: the Laplace problem is then a "
            "pure-Neumann problem with no unique solution"
        )
    return isdir, vd, v_scale


def _solve(grid: Grid, eps_r, fixed):
    """Solve for ``phi``; return ``(phi, K, length)``, ``length`` from the grid.

    ``length`` is the cell width along the line axis.  It is not a free
    parameter: the edge mass matrix is built from the *dual* face areas, which
    already carry that width, so any other value would rescale ``C'`` by
    ``grid_width / length`` and silently report a different capacitance.
    """
    line, _ = _line_and_transverse(grid)
    isdir, vd, _ = _dirichlet(grid, fixed)
    length = float(grid.widths(line)[0])

    G, m, _ = _transverse_metric(grid, eps_r)
    K = (G @ sp.diags(m) @ G.T).tocsr()

    free = np.flatnonzero(~isdir)
    held = np.flatnonzero(isdir)
    phi = vd.copy()
    phi[free] = spla.spsolve(
        K[free][:, free].tocsc(), -(K[free][:, held] @ vd[held])
    )
    return phi, K, length


def capacitance_per_length(grid: Grid, eps_r=1.0, fixed=None) -> float:
    """Capacitance per unit length ``C'`` [F/m] of the cross-section.

    Parameters
    ----------
    grid:
        Cross-section mesh: one cell thick and periodic along the line axis,
        any number of cells transversely (:func:`node_shape`).
    eps_r:
        Relative permittivity of every primal edge -- a float, a callable
        ``eps_r(x, y, z)``, or an explicit array of length ``cc.n_edges``.  See
        the module docstring for the interface-plane caveat: build the array by
        hand whenever a material interface exists.
    fixed:
        ``[(potential, node_indices), ...]`` with the conductor potentials in
        volts and flat node indices from :func:`node_index`.  At least two
        distinct potentials are required.  Every node not listed is free, and
        the outer box walls are homogeneous Neumann.
    Returns
    -------
    float
        ``phi^T K phi / (V^2 * length)`` with ``V = max(v) - min(v)`` and
        ``length`` the cell width along the line axis.

    Notes
    -----
    ``length`` is the cell width along the line axis and is read from the grid,
    not passed in.  The mass matrix already carries that width, so the two
    cancel: a section meshed with a line-axis cell twice as wide has twice the
    ``m_eps`` and returns the same ``C'``.  There is nothing for the caller to
    choose and no way to accidentally rescale the answer.

    Raises
    ------
    ValueError
        If the grid is not one cell thick and periodic along exactly one axis,
        if a node index is out of range, if fewer than two distinct conductor
        potentials are given, or if ``eps_r`` does not match ``cc.n_edges``.
    """
    phi, K, length = _solve(grid, eps_r, fixed)
    _, _, v_scale = _dirichlet(grid, fixed)
    return float(phi @ (K @ phi)) / (v_scale ** 2 * length)


def transverse_potential(grid: Grid, eps_r=1.0, fixed=None) -> np.ndarray:
    """Potential ``phi`` on the transverse nodes, shape :func:`node_shape`.

    Same conventions and ``ValueError`` paths as
    :func:`capacitance_per_length`; this is the field the capacitance is
    computed from, handy for inspecting a cross-section.
    """
    phi, _, _ = _solve(grid, eps_r, fixed)
    return np.asarray(phi, dtype=float).reshape(node_shape(grid))


def z0_eps_eff(grid: Grid, eps_r=1.0, fixed=None) -> tuple:
    """Quasi-TEM ``(Z0 [ohm], eps_eff [-])`` of the line.

    ``eps_eff = C'/C'_air`` and ``Z0 = sqrt(eps_eff) / (C0 * C')``, i.e.
    ``Z0 = 1 / (C0 * C'_air * sqrt(eps_eff))``: the air-filled line is the
    reference, so ``C'_air`` is solved with ``eps_r = 1`` everywhere and the
    passed ``eps_r`` is ignored there.  Equivalently ``C' = sqrt(eps_eff) /
    (C0 * Z0)``, the quasi-TEM relation the numbers are built on.

    Raises
    ------
    ValueError
        Exactly as :func:`capacitance_per_length`, for the filled and for the
        air-filled solve.
    """
    c_line = capacitance_per_length(grid, eps_r, fixed)
    c_air = capacitance_per_length(grid, 1.0, fixed)
    eps_eff = c_line / c_air
    return np.sqrt(eps_eff) / (C0 * c_line), float(eps_eff)
