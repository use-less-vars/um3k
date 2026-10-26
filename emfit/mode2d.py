"""2-D full-wave cross-section eigenmode solver (transverse ``e_t``, Whitney 1-forms).

:mod:`emfit.quasistatic` and :mod:`emfit.mode_profile` answer the *quasi-static*
question: ``C'``, ``Z0``, ``eps_eff`` and the field of a TEM-like section.  This
module answers the **full-wave** one -- it keeps the finite ``beta`` and the
vector character of ``e_t``, so it can also describe a *waveguide* cross-section
where the mode is not TEM at all (verification (b) below is the rectangular
``TE10`` mode, whose ``q(e_t) = curl_z e_t`` is not zero).

Formulation
-----------
Cross-section ``Omega`` in the ``(x, y)`` plane, propagation along ``z`` as
``exp(-j beta z)``, and the ansatz

    E = e_t(x, y) exp(-j beta z),      e_t = (e_x, e_y, 0),      e_z := 0.

Then

    curl E = zhat q(e_t) - j beta (zhat x e_t),      q(v) := d_x v_y - d_y v_x,

and the weak form of ``curl curl E - k0^2 eps_r E = 0`` is: find ``beta^2`` and
``e_t != 0`` such that for every test field ``v_t``

    k0^2 INT eps_r e_t . v_t dA  -  INT (1/mu_r) q(e_t) q(v_t) dA
        = beta^2 INT (1/mu_r) e_t . v_t dA,

i.e. the **generalised symmetric pencil**

    C e = beta^2 B e,     C = k0^2 M_eps - K_q,     B = M_mu.

``mu_r = 1`` everywhere here, so ``B`` is the plain vector mass matrix and is
symmetric positive definite; ``K_q`` is symmetric positive *semi*-definite (its
null space is exactly the discrete gradient space).  Both matrices are real and
symmetric, so the solve is ``scipy.sparse.linalg.eigsh`` on a real pencil --
never a complex one.  The one thing that makes the pencil non-trivial is that
``C`` is *indefinite*: ``beta^2`` can be negative (a mode below cutoff), and the
gradient null space of ``K_q`` gives ``beta^2 = k0^2`` exactly, i.e. the
spurious modes of edge elements sit at the top of the spectrum, not the bottom.

Boundary conditions
-------------------
* **PEC**: ``n x e_t = 0`` as an *essential* condition -- the tangential edge
  DOFs on a PEC surface are deleted (rows **and** columns, never a penalty).
* **Neumann**: natural on every other wall; nothing is imposed.

Discretisation
--------------
First-order Nedelec / Whitney 1-forms on a structured quad mesh split into two
triangles per quad by the same diagonal, 3-point barycentric Gauss quadrature
(exact for the degree-2 products that appear), and ``eps_r`` sampled at the
triangle centroid.

Sign rule (the standard reference-element convention): on the reference triangle
with vertices ``(0, 1, 2)`` the three local edge DOFs are directed
``1 -> 2``, ``2 -> 0``, ``0 -> 1``.  The global edge list stores each edge as
``(lo, hi)`` with ``lo < hi`` and its DOF is ``INT E . dl`` directed ``lo -> hi``.
The local shape function ``W_ab = lambda_a grad(lambda_b) - lambda_b grad(lambda_a)``
integrates to ``+1`` along the local direction ``a -> b``, so a local edge that
runs ``a > b`` disagrees with the global orientation and enters with a **minus**
sign.  Equivalently: ``sign = +1`` iff ``a < b``.  This is orientation-agnostic
(it only uses vertex labels) and is what makes the tangential component
continuous across an interior edge -- both triangles see the same global edge
direction, hence the same DOF.

API shape
---------
``structured_mesh`` / ``mesh_from_grid`` build the geometry, ``assemble`` is the
geometry-only assembler (it knows nothing about microstrip, plates or walls),
``pec_edge_mask`` turns caller-supplied boundary predicates into the eliminated
edge set, and ``solve_modes`` drives the eigen-solve and returns a frozen
:class:`Mode2D` that can evaluate ``e_t`` at arbitrary interior points.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import eig as _dense_eig
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import (
    eigsh,
    splu,
    spsolve,
)

from .grid import Grid
from .materials import C0

__all__ = [
    "Mesh2D",
    "Mode2D",
    "assemble",
    "assemble_mixed",
    "eps_eff_laplace",
    "k0_from_freq",
    "mesh_from_grid",
    "pec_edge_mask",
    "pec_node_mask",
    "solve_modes",
    "solve_modes_mixed",
    "structured_mesh",
]


# ----------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------
#: The three local edge DOFs of a triangle, as directed vertex pairs
#: ``(a, b)``: edge ``b`` is the one *opposite* local vertex ``0``, and so on.
#: ``W_ab = lambda_a grad(lambda_b) - lambda_b grad(lambda_a)`` has line
#: integral ``+1`` along ``a -> b``.
_LOCAL_EDGES = ((1, 2), (2, 0), (0, 1))
_LOCAL_A = np.array([a for a, _ in _LOCAL_EDGES], dtype=int)
_LOCAL_B = np.array([b for _, b in _LOCAL_EDGES], dtype=int)

#: 3-point barycentric Gauss rule.  ``sum(w) = 1`` (so the area comes out exact)
#: and it is exact for degree 2, which is exactly the degree of
#: ``lambda_a lambda_b`` and of ``grad(lambda) . grad(lambda)`` -- both mass and
#: curl-curl integrands are therefore integrated **exactly**, not approximately.
#: A closed-form mass matrix is deliberately *not* used: the same quadrature loop
#: then covers the curl-curl term, whose integrand is piecewise constant.
_QUAD_POINTS = ((1.0 / 6.0, 1.0 / 6.0), (2.0 / 3.0, 1.0 / 6.0), (1.0 / 6.0, 2.0 / 3.0))
_QUAD_WEIGHT = 1.0 / 3.0

#: A candidate whose ``e^T K_q e / e^T B e`` is below this fraction of the
#: largest one in the set is "curl-free" to working precision -- in exact
#: arithmetic the discrete gradient space gives *exactly* zero, so the only
#: reason this is not ``0.0`` is the matrix-vector product's roundoff.
_CURL_RTOL = 1.0e-10

#: Relative slack allowed when locating a point in a structured cell, so that a
#: point sitting exactly on a cell boundary (which is where a quadrature node of
#: the neighbouring cell lives) is accepted instead of rejected.
_LOCATE_RTOL = 1.0e-9

#: ``(3, 3)`` pattern of the consistent ``P1`` nodal mass matrix on a triangle:
#: ``INT phi_i phi_j dA = (area / 12) * _P1_MASS_PATTERN[i, j]``.
_P1_MASS_PATTERN = np.array([[2.0, 1.0, 1.0], [1.0, 2.0, 1.0], [1.0, 1.0, 2.0]])

#: Largest scale-aware relative backward error
#: ``||A x - lambda B x|| / ((||A||_F + |lambda| ||B||_F) ||x||)`` a candidate
#: of the *mixed* formulation may carry and still be selected by
#: :func:`solve_modes_mixed`.  The naive ``||A x - lambda B x|| / ||B x||``
#: normalisation is not usable: ``B = m1 - C D C^T`` is strongly indefinite
#: (565 of 1592 eigenvalues negative on the parallel-plate mesh), so ``||B x||``
#: is not a valid denominator and a ``1e-6`` threshold on that ratio is
#: unreachable even for exact eigenpairs.
_MIXED_RESIDUAL_TOL = 1.0e-3
_MIXED_DENSE_MAX = 3000


# ----------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------
def _quadrature_lambda() -> np.ndarray:
    """``(3, 3)`` array: barycentric values ``(l0, l1, l2)`` at each Gauss point."""
    lam = np.empty((len(_QUAD_POINTS), 3))
    for q, (l0, l1) in enumerate(_QUAD_POINTS):
        lam[q] = (l0, l1, 1.0 - l0 - l1)
    return lam


@dataclass(frozen=True)
class Mesh2D:
    """A conforming triangulation of a cross-section with a global edge list.

    Attributes
    ----------
    nodes:
        ``(nn, 2)`` vertex coordinates, metres.
    tris:
        ``(nt, 3)`` vertex indices, **counter-clockwise**.
    edges:
        ``(ne, 2)`` global edge list, one row per edge DOF, stored ``(lo, hi)``
        with ``lo < hi`` -- the global orientation convention.
    tri_edges:
        ``(nt, 3)`` global edge index of each local edge slot; slot ``s`` is the
        directed local edge ``_LOCAL_EDGES[s]``.
    tri_sign:
        ``(nt, 3)`` ``+1`` when the local direction agrees with ``(lo, hi)``,
        ``-1`` otherwise.  This is the whole orientation convention.
    grad:
        ``(nt, 3, 2)`` barycentric gradients ``grad(lambda_i)``, constant on a
        triangle.
    area:
        ``(nt,)`` triangle areas, m^2.
    centroid:
        ``(nt, 2)`` triangle centroids, m -- where ``eps_r`` is sampled.
    grid_axes:
        ``(xs, ys)`` node coordinate arrays when the mesh came from a structured
        grid; enables fast point location.  ``None`` for arbitrary meshes, which
        fall back to a brute-force search.
    """

    nodes: np.ndarray
    tris: np.ndarray
    edges: np.ndarray
    tri_edges: np.ndarray
    tri_sign: np.ndarray
    grad: np.ndarray
    area: np.ndarray
    centroid: np.ndarray
    grid_axes: tuple = ()

    @property
    def n_nodes(self) -> int:
        """Number of vertices."""
        return int(self.nodes.shape[0])

    @property
    def n_tris(self) -> int:
        """Number of triangles."""
        return int(self.tris.shape[0])

    @property
    def n_edges(self) -> int:
        """Number of edges, i.e. of first-order Nedelec DOFs."""
        return int(self.edges.shape[0])

    def boundary_edges(self) -> np.ndarray:
        """Mask of edges on the mesh boundary (an edge used by one triangle)."""
        used = np.concatenate([self.tri_edges.ravel()])
        counts = np.bincount(used, minlength=self.n_edges)
        return counts == 1


def _as_mesh(nodes: np.ndarray, tris: np.ndarray, grid_axes: tuple = ()) -> Mesh2D:
    """Build a :class:`Mesh2D` from vertices and counter-clockwise triangles."""
    nodes = np.ascontiguousarray(nodes, dtype=float)
    tris = np.ascontiguousarray(tris, dtype=np.int64)
    if nodes.ndim != 2 or nodes.shape[1] != 2:
        raise ValueError(f"nodes must be (nn, 2), got {nodes.shape}")
    if tris.ndim != 2 or tris.shape[1] != 3:
        raise ValueError(f"tris must be (nt, 3), got {tris.shape}")
    if tris.min() < 0 or tris.max() >= nodes.shape[0]:
        raise ValueError("tris index outside nodes")

    p0 = nodes[tris[:, 0]]
    p1 = nodes[tris[:, 1]]
    p2 = nodes[tris[:, 2]]
    # signed double area: positive because the triangles are counter-clockwise
    two_a = (p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (
        p2[:, 0] - p0[:, 0]
    ) * (p1[:, 1] - p0[:, 1])
    if not np.all(two_a > 0.0):
        raise ValueError(
            "every triangle must be counter-clockwise (positive signed area); "
            f"{int(np.count_nonzero(two_a <= 0.0))} of {tris.shape[0]} are not"
        )

    grad = np.empty((tris.shape[0], 3, 2))
    grad[:, 0, 0] = (p1[:, 1] - p2[:, 1]) / two_a
    grad[:, 0, 1] = (p2[:, 0] - p1[:, 0]) / two_a
    grad[:, 1, 0] = (p2[:, 1] - p0[:, 1]) / two_a
    grad[:, 1, 1] = (p0[:, 0] - p2[:, 0]) / two_a
    grad[:, 2, 0] = (p0[:, 1] - p1[:, 1]) / two_a
    grad[:, 2, 1] = (p1[:, 0] - p0[:, 0]) / two_a

    # --- global edge list: unique unordered vertex pairs, lower index first ---
    nn = nodes.shape[0]
    lo = tris[:, _LOCAL_A]
    hi = tris[:, _LOCAL_B]
    keys = np.minimum(lo, hi) * nn + np.maximum(lo, hi)
    uniq, inverse = np.unique(keys.ravel(), return_inverse=True)
    tri_edges = inverse.reshape(tris.shape)
    edges = np.stack([uniq // nn, uniq % nn], axis=1).astype(np.int64)
    # local direction agrees with the global (lo, hi) orientation iff a < b
    tri_sign = np.where(lo < hi, 1.0, -1.0)

    return Mesh2D(
        nodes=nodes,
        tris=tris,
        edges=edges,
        tri_edges=tri_edges,
        tri_sign=tri_sign,
        grad=grad,
        area=0.5 * two_a,
        centroid=(p0 + p1 + p2) / 3.0,
        grid_axes=tuple(np.asarray(a, dtype=float).ravel() for a in grid_axes)
        if grid_axes
        else (),
    )


def structured_mesh(xs: np.ndarray, ys: np.ndarray) -> Mesh2D:
    """Structured quad mesh on ``xs x ys``, each quad cut by one diagonal.

    The node coordinate arrays are the *node* (point-layer) values, so ``nx``
    cells along ``x`` means ``len(xs) == nx + 1``.  Every quad is split by the
    diagonal from its ``(low x, low y)`` corner to its ``(high x, high y)``
    corner, consistently over the whole mesh, giving triangles

        (n00, n10, n11)   and   (n00, n11, n01)

    which are both counter-clockwise for increasing ``xs`` / ``ys``.  Quad ``q``
    owns triangles ``2q`` and ``2q + 1``, which is what
    :meth:`Mode2D.e_at` relies on for fast point location.
    """
    xs = np.asarray(xs, dtype=float).ravel()
    ys = np.asarray(ys, dtype=float).ravel()
    nu, nv = xs.size, ys.size
    if nu < 2 or nv < 2:
        raise ValueError(f"need at least 2 nodes per axis, got {nu} x {nv}")
    if np.any(np.diff(xs) <= 0.0) or np.any(np.diff(ys) <= 0.0):
        raise ValueError("xs and ys must be strictly increasing")

    uu, vv = np.meshgrid(xs, ys, indexing="xy")  # (nv, nu)
    nodes = np.stack([uu.ravel(), vv.ravel()], axis=1)

    iu, iv = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1), indexing="xy")
    n00 = (iv * nu + iu).ravel()
    n10 = n00 + 1
    n01 = n00 + nu
    n11 = n01 + 1
    tris = np.empty((2 * n00.size, 3), dtype=np.int64)
    tris[0::2, 0], tris[0::2, 1], tris[0::2, 2] = n00, n10, n11
    tris[1::2, 0], tris[1::2, 1], tris[1::2, 2] = n00, n11, n01
    return _as_mesh(nodes, tris, grid_axes=(xs, ys))


def _transverse_axes(grid: Grid) -> tuple:
    """The two *non-periodic* axes of a house :class:`~emfit.grid.Grid`.

    This is the same axis choice as :func:`emfit.quasistatic.node_shape`: a
    ``microstrip_mode_profile`` section is a grid that is periodic with a single
    cell along the line axis, so the cross-section is the two axes that are not.
    Using it here is what lets :func:`mesh_from_grid` take the grid that
    :func:`emfit.mode_profile._section` already builds, unchanged.
    """
    axes = tuple(a for a in "xyz" if not grid.is_periodic(a))
    if len(axes) != 2:
        raise ValueError(
            f"a cross-section grid needs exactly 2 non-periodic axes, got "
            f"{axes!r} (periodic={grid.periodic!r})"
        )
    return axes


def mesh_from_grid(grid: Grid) -> Mesh2D:
    """Cross-section mesh of a house :class:`~emfit.grid.Grid`.

    The grid is the same object :func:`emfit.mode_profile._section` produces for
    the microstrip profile (one periodic line axis, two transverse node axes),
    so a full-wave section and a quasi-static profile can be built on one
    geometry.  Only the node coordinate arrays are used: this is a *structured
    quad* mesh, not the staggered Yee lattice that the quasi-static module needs.
    """
    a1, a2 = _transverse_axes(grid)
    return structured_mesh(getattr(grid, a1), getattr(grid, a2))


def box_mesh(lx: float, ly: float, nx: int, ny: int) -> Mesh2D:
    """``nx x ny`` uniform cells over an ``lx x ly`` box.

    Built through the house :class:`~emfit.grid.Grid`, with the third axis
    periodic and one cell thick, i.e. the same grid *spec* as
    :func:`emfit.mode_profile._section` -- only the physical meaning of the two
    transverse axes differs (there they are ``y`` and ``z``; here ``x`` and
    ``y``).
    """
    lx, ly = float(lx), float(ly)
    if not (np.isfinite(lx) and lx > 0.0):
        raise ValueError(f"lx must be positive, got {lx!r}")
    if not (np.isfinite(ly) and ly > 0.0):
        raise ValueError(f"ly must be positive, got {ly!r}")
    nx, ny = int(nx), int(ny)
    if nx < 1 or ny < 1:
        raise ValueError(f"nx and ny must be positive integers, got {nx}, {ny}")
    grid = Grid.uniform(nx, ny, 1, lx, ly, 1.0, periodic=(False, False, True))
    return mesh_from_grid(grid)


# ----------------------------------------------------------------------
# assembly
# ----------------------------------------------------------------------
def _per_triangle(value, mesh: Mesh2D, name: str) -> np.ndarray:
    """Broadcast a scalar, an array or a ``centroid -> values`` callable."""
    n = mesh.n_tris
    if callable(value):
        arr = np.asarray(value(mesh.centroid), dtype=float)
    else:
        arr = np.asarray(value, dtype=float)
    if arr.ndim == 0:
        arr = np.full(n, float(arr))
    arr = np.ascontiguousarray(arr.ravel())
    if arr.size != n:
        raise ValueError(
            f"{name} must be one value per triangle ({n}), got {arr.size}"
        )
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains a non-finite value")
    return arr


def assemble(mesh: Mesh2D, eps_r=1.0, mu_r=1.0) -> tuple:
    """Assemble ``(K_q, M_mu, M_eps)`` on the *full* edge list.

    ``K_q[e, f] = INT (1/mu_r) q(W_e) q(W_f) dA``,
    ``M_mu[e, f] = INT (1/mu_r) W_e . W_f dA``,
    ``M_eps[e, f] = INT eps_r W_e . W_f dA``,

    with ``q(W) = d_x W_y - d_y W_x`` the ``z`` component of ``curl W``.  All
    three are real symmetric; the quadrature integrates the mass terms exactly
    (degree-2 integrand) and the curl-curl terms exactly (piecewise constant).

    ``eps_r`` / ``mu_r`` may be a scalar, a per-triangle array, or a callable
    taking the ``(nt, 2)`` centroid array -- that is the only place material ever
    enters, and it is sampled at the centroid as specified.

    The returned matrices are on the **full** edge list *including* the edges
    that :func:`pec_edge_mask` will eliminate; the caller does the deletion so
    that the same matrices can serve several boundary conditions.
    """
    eps_t = _per_triangle(eps_r, mesh, "eps_r")
    mu_t = _per_triangle(mu_r, mesh, "mu_r")
    if np.any(mu_t == 0.0):
        raise ValueError("mu_r must be non-zero")

    g = mesh.grad                                        # (nt, 3, 2)
    lam = _quadrature_lambda()                           # (3, 3)  qp x vertex

    # W[t, s, q, :] = lambda_a grad(lambda_b) - lambda_b grad(lambda_a) at qp q
    w = np.empty((mesh.n_tris, 3, len(_QUAD_POINTS), 2))
    for s in range(3):
        ga = g[:, _LOCAL_A[s], :][:, None, :]            # (nt, 1, 2)
        gb = g[:, _LOCAL_B[s], :][:, None, :]
        la = lam[:, _LOCAL_A[s]][None, :, None]          # (1, 3, 1)
        lb = lam[:, _LOCAL_B[s]][None, :, None]
        w[:, s] = la * gb - lb * ga

    # --- mass: INT W_e . W_f, exactly by the 3-point rule -------------------
    # sum_q (1/3) * W_s(q) . W_r(q), times the area
    dot = np.einsum("tsqc,trqc->tsr", w, w)               # (nt, 3, 3)
    m_loc = (_QUAD_WEIGHT * mesh.area)[:, None, None] * dot * 3.0 / 3.0

    # --- curl-curl: q(W_e) is piecewise CONSTANT on a triangle -------------
    # q(W_ab) = 2 (g_a x g_b)_z, so the rule is exact with any weights; it is
    # still evaluated through the same quadrature sum for one code path.
    cross = g[:, _LOCAL_A, 0] * g[:, _LOCAL_B, 1] - g[:, _LOCAL_A, 1] * g[:, _LOCAL_B, 0]
    q_s = 2.0 * cross                                     # (nt, 3)
    k_loc = mesh.area[:, None, None] * q_s[:, :, None] * q_s[:, None, :]

    # --- local orientation sign -------------------------------------------
    sgn = mesh.tri_sign                                   # (nt, 3)
    outer = sgn[:, :, None] * sgn[:, None, :]
    m_loc = m_loc * outer
    k_loc = k_loc * outer

    ne = mesh.n_edges
    rows = np.repeat(mesh.tri_edges, 3, axis=1).ravel()
    cols = np.tile(mesh.tri_edges, (1, 3)).ravel()

    def _scatter(vals: np.ndarray) -> csr_matrix:
        return coo_matrix(
            (vals.reshape(-1), (rows, cols)), shape=(ne, ne)
        ).tocsr()

    k_q = _scatter(k_loc * mu_t[:, None, None] ** -1.0)
    m_mu = _scatter(m_loc * mu_t[:, None, None] ** -1.0)
    m_eps = _scatter(m_loc * eps_t[:, None, None])
    return k_q, m_mu, m_eps


# ----------------------------------------------------------------------
# mixed (e_t + e_z) assembly
# ----------------------------------------------------------------------
def assemble_mixed(mesh: Mesh2D, eps_r=1.0, mu_r=1.0) -> tuple:
    """Assemble ``(m1, m_eps, c, k_zz, m_zz)`` -- the blocks of the mixed pencil.

    With ``q(v) := d_x v_y - d_y v_x``, ``W_e`` the Whitney 1-form of edge ``e``
    and ``phi_i`` the nodal hat function of vertex ``i``::

        m1[e, f]    = INT (1/mu_r) W_e . W_f dA            (edge x edge)
        m_eps[e, f] = INT eps_r W_e . W_f dA               (edge x edge)
        c[e, i]     = INT (1/mu_r) W_e . grad phi_i dA     (edge x node, ne x nn)
        k_zz[i, j]  = INT (1/mu_r) grad phi_i . grad phi_j dA
        m_zz[i, j]  = INT eps_r phi_i phi_j dA

    ``m1`` and ``m_eps`` are exactly the ``m_mu`` / ``m_eps`` of :func:`assemble`
    and are taken from there instead of being re-assembled: the ``beta^2`` term
    of the mixed weak form carries the ``1/mu_r``, so ``m_mu`` *is* ``m1`` even
    when ``mu_r != 1``.

    The three new blocks use the same scatter / orientation idiom as
    :func:`assemble`: a triangle's ``3 x 3`` local block is scattered through
    ``mesh.tri_edges`` (rows) and ``mesh.tris`` (columns), and the edge row of
    ``c`` carries ``mesh.tri_sign`` so that ``c`` is expressed in the *global*
    edge orientation ``(lo, hi)``.  The node column carries no sign.  The
    per-triangle values are::

        c_local[s, j] = (area / 3) (grad phi_b - grad phi_a) . grad phi_j / mu
        k_zz_local    = area (grad phi_i . grad phi_j) / mu
        m_zz_local    = (area / 12) * _P1_MASS_PATTERN * eps

    all exact for the polynomial degrees that appear (the ``c`` and ``k_zz``
    integrands are piecewise constant, ``m_zz`` is the consistent ``P1`` mass
    matrix).

    Returns five real ``csr_matrix`` objects: ``m1``, ``m_eps`` ``(ne, ne)``,
    ``c`` ``(ne, nn)``, ``k_zz`` and ``m_zz`` ``(nn, nn)``, all on the **full**
    node / edge lists so that the caller does the PEC deletion.
    """
    _k_q, m1, m_eps = assemble(mesh, eps_r=eps_r, mu_r=mu_r)
    eps_t = _per_triangle(eps_r, mesh, "eps_r")
    inv_mu = 1.0 / _per_triangle(mu_r, mesh, "mu_r")

    g = mesh.grad                                           # (nt, 3, 2)
    dg = g[:, _LOCAL_B, :] - g[:, _LOCAL_A, :]              # (nt, 3, 2)

    # c: (nt, s, j), s the local edge slot, j the local node slot
    c_loc = (mesh.area / 3.0)[:, None, None] * np.einsum("tsc,tjc->tsj", dg, g)
    c_loc = c_loc * inv_mu[:, None, None] * mesh.tri_sign[:, :, None]

    dot = np.einsum("tij,tkj->tik", g, g)                   # (nt, 3, 3)
    k_zz_loc = (mesh.area * inv_mu)[:, None, None] * dot
    m_zz_loc = (mesh.area * eps_t / 12.0)[:, None, None] * _P1_MASS_PATTERN[None]

    ne, nn = mesh.n_edges, mesh.n_nodes
    e_rows = np.repeat(mesh.tri_edges, 3, axis=1).ravel()
    e_cols = np.tile(mesh.tri_edges, (1, 3)).ravel()
    n_rows = np.repeat(mesh.tris, 3, axis=1).ravel()
    n_cols = np.tile(mesh.tris, (1, 3)).ravel()

    c = coo_matrix((c_loc.reshape(-1), (e_rows, n_cols)), shape=(ne, nn)).tocsr()
    k_zz = coo_matrix(
        (k_zz_loc.reshape(-1), (n_rows, n_cols)), shape=(nn, nn)
    ).tocsr()
    m_zz = coo_matrix(
        (m_zz_loc.reshape(-1), (n_rows, n_cols)), shape=(nn, nn)
    ).tocsr()
    return m1, m_eps, c, k_zz, m_zz


# ----------------------------------------------------------------------
# boundary conditions
# ----------------------------------------------------------------------
def pec_edge_mask(mesh: Mesh2D, boundaries=()) -> np.ndarray:
    """Boolean mask of edges eliminated by the PEC condition.

    ``boundaries`` is a sequence of predicates, each a callable taking the
    ``(nn, 2)`` node array and returning a boolean mask of *nodes* on that
    conductor surface.  An edge is PEC iff **both** endpoints lie on the **same**
    one of those surfaces.

    "Same one" is not a detail: on the parallel-plate section of verification
    (a) the top and bottom plates are two different predicates, and an edge
    joining a node on the ground plane to a node on the top plate has both
    endpoints on *some* PEC surface -- but it is the gap edge that carries
    ``E_y`` and must stay free.  Taking the union of the node masks first would
    delete exactly the DOFs the mode lives on.

    Nothing here knows about plates, walls or microstrip: the geometry enters
    only through the predicates the caller supplies.
    """
    mask = np.zeros(mesh.n_edges, dtype=bool)
    lo = mesh.edges[:, 0]
    hi = mesh.edges[:, 1]
    for index, predicate in enumerate(boundaries):
        on = np.asarray(predicate(mesh.nodes), dtype=bool)
        if on.shape != (mesh.n_nodes,):
            raise ValueError(
                f"boundary predicate {index} returned shape {on.shape}, "
                f"expected ({mesh.n_nodes},)"
            )
        mask |= on[lo] & on[hi]
    return mask


def pec_node_mask(mesh: Mesh2D, boundaries=()) -> np.ndarray:
    """Boolean mask of *nodes* lying on any PEC surface.

    The nodal counterpart of :func:`pec_edge_mask`: same ``boundaries`` argument
    (a sequence of predicates mapping the ``(nn, 2)`` node array to a boolean
    node mask), deliberately **different** combination rule.

    * a **node** is PEC iff it lies on **any one** of the predicates -- a plain
      union of the masks -- because a node on a conductor is a Dirichlet node
      for the scalar potential and for the longitudinal ``e_z``;
    * an **edge** is PEC iff **both** endpoints lie on the **same** predicate
      (see :func:`pec_edge_mask`), so the gap edge joining two different
      conductors keeps its DOF.

    Using the node union for the edges instead would delete exactly the ``E_y``
    DOFs the parallel-plate mode lives on; that is why the two masks are not
    derived from one another.
    """
    mask = np.zeros(mesh.n_nodes, dtype=bool)
    for index, predicate in enumerate(boundaries):
        on = np.asarray(predicate(mesh.nodes), dtype=bool)
        if on.shape != (mesh.n_nodes,):
            raise ValueError(
                f"boundary predicate {index} returned shape {on.shape}, "
                f"expected ({mesh.n_nodes},)"
            )
        mask |= on
    return mask


# ----------------------------------------------------------------------
# the result
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Mode2D:
    """One cross-section eigenmode, plus every candidate the solve returned.

    Scalars, all in SI (``beta`` and ``k0`` in rad/m, ``beta_sq`` in rad^2/m^2)::

        freq        float   frequency, Hz (``k0 c / 2 pi``)
        k0          float   vacuum wavenumber
        beta        float   propagation constant, ``sqrt(beta_sq)``; NaN when
                            ``beta_sq < 0`` (below cutoff, see ``beta_imag``)
        beta_sq     float   the eigenvalue
        eps_eff     float   ``beta_sq / k0^2``
        residual    float   ``||C e - beta_sq B e|| / ||B e||`` of the chosen mode

    The audit trail -- the solver is only as trustworthy as this::

        candidates  tuple   ``(beta_sq, eps_eff)`` for every candidate, largest
                            ``beta_sq`` first
        curl_ratio  tuple   ``e^T K_q e / e^T B e`` per candidate: zero to
                            working precision marks a spurious gradient mode
                            (whose ``beta_sq`` is exactly ``k0^2``); the wanted
                            mode of a *waveguide* has this equal to the cutoff
                            term, and the quasi-TEM mode of a layered line has a
                            small but non-zero value
        chosen      int     index into ``candidates`` of the mode reported above
        sigma       float   the shift handed to ``eigsh``
        n_dof       int     free (non-PEC) edge count the solve ran on
        n_pec       int     eliminated edges

    Geometry and field::

        e_t         (ne,)   the eigenvector on the *full* edge list, normalised
                            so that ``e^T B e = 1``, zero on every PEC edge
        e_z         (nn,)   nodal longitudinal field of the *mixed* formulation
                            (:func:`solve_modes_mixed`) as a complex phasor
                            ``-i beta (k_zz - k0^2 m_zz)^{-1} c^T e_t``; ``None``
                            for the ``e_t``-only solve.  For a propagating mode
                            it is purely imaginary, so ``abs(e_z)`` is the
                            physical amplitude.  :meth:`e_at` does *not*
                            include it -- see the note there.
        mesh        Mesh2D  the triangulation; ``nodes``, ``tris`` and ``edges``
                            are properties onto it

    ``e_t`` is the *edge* representation: ``e_t[i]`` is ``INT_edge E . dl`` in
    volts at unit field amplitude, i.e. the edge length is already folded in.
    :meth:`e_at` is the continuous field.
    """

    freq: float
    k0: float
    beta: float
    beta_sq: float
    eps_eff: float
    residual: float
    candidates: tuple
    curl_ratio: tuple
    chosen: int
    sigma: float
    n_dof: int
    n_pec: int
    e_t: np.ndarray
    mesh: Mesh2D
    e_z: np.ndarray | None = None

    # -- geometry pass-throughs -------------------------------------------
    @property
    def nodes(self) -> np.ndarray:
        """``(nn, 2)`` vertex coordinates."""
        return self.mesh.nodes

    @property
    def tris(self) -> np.ndarray:
        """``(nt, 3)`` counter-clockwise vertex indices."""
        return self.mesh.tris

    @property
    def edges(self) -> np.ndarray:
        """``(ne, 2)`` global edge list, ``(lo, hi)``."""
        return self.mesh.edges

    @property
    def beta_imag(self) -> float:
        """``sqrt(-beta_sq)`` [1/m] for a below-cutoff mode, else ``0.0``."""
        return float(np.sqrt(max(-self.beta_sq, 0.0)))

    @property
    def is_propagating(self) -> bool:
        """Whether ``beta_sq > 0`` (a mode that actually propagates)."""
        return bool(self.beta_sq > 0.0)

    # -- field evaluation --------------------------------------------------
    def _locate(self, points: np.ndarray) -> np.ndarray:
        """Triangle index containing each point (structured fast path first)."""
        pts = np.ascontiguousarray(points, dtype=float)
        if pts.ndim != 2 or pts.shape[1] != 2:
            raise ValueError(f"points must be (n, 2), got {pts.shape}")
        if self.mesh.grid_axes:
            xs, ys = self.mesh.grid_axes
            nu, nv = xs.size, ys.size
            i = np.clip(np.searchsorted(xs, pts[:, 0], side="right") - 1, 0, nu - 2)
            j = np.clip(np.searchsorted(ys, pts[:, 1], side="right") - 1, 0, nv - 2)
            u = (pts[:, 0] - xs[i]) / (xs[i + 1] - xs[i])
            v = (pts[:, 1] - ys[j]) / (ys[j + 1] - ys[j])
            outside = (
                (u < -_LOCATE_RTOL)
                | (u > 1.0 + _LOCATE_RTOL)
                | (v < -_LOCATE_RTOL)
                | (v > 1.0 + _LOCATE_RTOL)
            )
            if np.any(outside):
                bad = int(np.flatnonzero(outside)[0])
                raise ValueError(
                    f"point {bad} {tuple(pts[bad])} lies outside the mesh; "
                    f"{int(outside.sum())} of {pts.shape[0]} are outside"
                )
            # quad q owns triangles 2q and 2q+1; the diagonal is u == v, and
            # triangle 2q is (n00, n10, n11), i.e. the v <= u half
            quad = j * (nu - 1) + i
            return 2 * quad + np.where(v <= u, 0, 1)

        # generic fallback: brute-force barycentric containment
        tri = np.full(pts.shape[0], -1, dtype=np.int64)
        tol = 1e-9
        for t in range(self.mesh.n_tris):
            todo = np.flatnonzero(tri < 0)
            if todo.size == 0:
                break
            p = pts[todo]
            g = self.mesh.grad[t]
            v = self.mesh.nodes[self.mesh.tris[t]]
            lam = 1.0 + (p - v) * g  # (m, 3)
            inside = np.all(lam >= -tol, axis=1)
            tri[todo[inside]] = t
        if np.any(tri < 0):
            bad = int(np.flatnonzero(tri < 0)[0])
            raise ValueError(f"point {bad} {tuple(pts[bad])} is outside the mesh")
        return tri

    def e_at(self, points) -> np.ndarray:
        """Transverse field ``e_t`` at arbitrary interior points.

        ``points`` is ``(n, 2)`` in metres; the return is ``(n, 2)``.

        Each point is located in its triangle and the Whitney sum

            e_t(p) = sum_s w_s [ lambda_a(p) grad(lambda_b) - lambda_b(p) grad(lambda_a) ]

        is evaluated, with ``w_s`` the oriented edge DOF of that triangle's local
        slot ``s`` and ``lambda_i(p) = 1 + grad(lambda_i) . (p - p_i)``.  Both
        triangles of a cell agree on the shared diagonal, so the field is
        single-valued there; on a PEC edge the DOF is zero and the tangential
        component vanishes on that edge only (the normal component is *not*
        constrained, which is what the essential condition means).

        This is the **transverse** field only.  A mode from
        :func:`solve_modes_mixed` also carries the nodal longitudinal field
        :attr:`e_z`; it is not interpolated here because a nodal field lives on
        the ``P1`` basis, not on the Whitney one -- read ``mode.e_z`` directly
        (see the class docstring for its sign convention).
        """
        pts = np.ascontiguousarray(points, dtype=float)
        tri = self._locate(pts)
        v = self.mesh.nodes[self.mesh.tris[tri]]          # (n, 3, 2)
        g = self.mesh.grad[tri]                           # (n, 3, 2)
        lam = 1.0 + np.einsum("nij,nij->ni", pts[:, None, :] - v, g)

        a = self.mesh.tris[tri][:, _LOCAL_A]               # (n, 3)
        b = self.mesh.tris[tri][:, _LOCAL_B]
        sgn = self.mesh.tri_sign[tri]                      # (n, 3)
        w = sgn * self.e_t[self.mesh.tri_edges[tri]]       # (n, 3) oriented DOFs

        n_idx = np.arange(pts.shape[0])[:, None]
        lam_a = lam[n_idx, _LOCAL_A[None, :]]              # (n, 3)
        lam_b = lam[n_idx, _LOCAL_B[None, :]]
        ga = g[:, _LOCAL_A, :]                             # (n, 3, 2)
        gb = g[:, _LOCAL_B, :]
        terms = w[:, :, None] * (lam_a[:, :, None] * gb - lam_b[:, :, None] * ga)
        return terms.sum(axis=1)


# ----------------------------------------------------------------------
# the solver
# ----------------------------------------------------------------------
def k0_from_freq(freq: float) -> float:
    """Vacuum wavenumber ``2 pi f / c`` [rad/m]."""
    f = float(freq)
    if not (np.isfinite(f) and f > 0.0):
        raise ValueError(f"freq must be positive and finite, got {freq!r}")
    return 2.0 * np.pi * f / C0


def solve_modes(
    mesh: Mesh2D,
    k0: float,
    sigma: float,
    *,
    eps_r=1.0,
    mu_r=1.0,
    boundaries=(),
    k: int = 4,
) -> Mode2D:
    """Solve ``C e = beta^2 B e`` for the ``k`` modes nearest the shift ``sigma``.

    Parameters
    ----------
    mesh:
        The triangulation.
    k0:
        Vacuum wavenumber [rad/m].
    sigma:
        Spectral shift, a **plain float** (never an operator): ``eigsh``
        factorises ``C - sigma B`` with it.  It must not sit exactly on an
        eigenvalue of the pencil; see the note in :func:`solve_modes`.
    eps_r, mu_r:
        Per-triangle material, as for :func:`assemble`.
    boundaries:
        PEC predicates, as for :func:`pec_edge_mask`.
    k:
        Number of candidates to return.

    Returns
    -------
    Mode2D

    Notes
    -----
    The chosen mode is the one with the largest **positive** ``beta_sq`` whose
    relative curl energy ``e^T K_q e / e^T B e`` is not anomalously small -- in
    exact arithmetic a spurious gradient mode has that ratio exactly zero and its
    ``beta_sq`` exactly ``k0^2``, i.e. it would otherwise compete for "largest
    ``beta_sq``" and win.  When *every* candidate is curl-free the filter cannot
    discriminate (a homogeneous ``eps_r`` makes even the physical mode a
    gradient, e.g. the parallel-plate ``TEM`` of verification (a)); it then keeps
    them all and the largest ``beta_sq`` still wins, which is the correct answer
    in that degenerate case and is reported as such by ``curl_ratio``.  The full
    candidate list is always returned so the choice can be audited.

    ``sigma`` is used exactly as given.  If it coincides with an eigenvalue the
    shifted matrix is singular and the factorisation inside ``eigsh`` is expected
    to fail -- that is a property of shift-invert, not of this code, and the
    caller should offset ``sigma`` off the eigenvalue it is looking for.
    """
    k0 = float(k0)
    sigma = float(sigma)
    if not np.isfinite(k0) or k0 <= 0.0:
        raise ValueError(f"k0 must be positive and finite, got {k0!r}")
    if not np.isfinite(sigma):
        raise ValueError(f"sigma must be finite, got {sigma!r}")

    k_q, m_mu, m_eps = assemble(mesh, eps_r=eps_r, mu_r=mu_r)
    mask = pec_edge_mask(mesh, boundaries)
    free = np.flatnonzero(~mask)
    n_dof = int(free.size)
    if n_dof < 3:
        raise ValueError(f"only {n_dof} free edge DOFs after the PEC cut")

    c = (k0 * k0 * m_eps - k_q).tocsr()
    b = m_mu.tocsr()
    c_free = c[free][:, free]
    b_free = b[free][:, free]

    n_k = min(int(k), n_dof - 1)
    if n_k < 1:
        raise ValueError(f"cannot ask for {k} modes with {n_dof} DOFs")
    vals, vecs = eigsh(c_free, k=n_k, M=b_free, sigma=sigma, which="LM")
    vals = np.asarray(vals, dtype=float)

    # --- normalise each candidate so that e^T B e = 1 ---------------------
    ratios = np.empty(n_k)
    residuals = np.empty(n_k)
    normalised = np.empty_like(vecs)
    b_norm = np.empty(n_k)
    for i in range(n_k):
        v = vecs[:, i]
        be = b_free @ v
        scale = float(np.sqrt(v @ be))
        if not np.isfinite(scale) or scale <= 0.0:
            raise RuntimeError(
                f"candidate {i} has e^T B e = {scale ** 2!r}; B must be SPD"
            )
        v = v / scale
        be = be / scale
        normalised[:, i] = v
        b_norm[i] = float(np.linalg.norm(be))
        ratios[i] = float(v @ (k_q[free][:, free] @ v))
        residuals[i] = float(np.linalg.norm(c_free @ v - vals[i] * be) / b_norm[i])

    # --- mode selection ---------------------------------------------------
    order = np.argsort(-vals)
    vals = vals[order]
    ratios = ratios[order]
    residuals = residuals[order]
    normalised = normalised[:, order]

    r_max = float(np.max(np.abs(ratios)))
    if r_max > 0.0:
        acceptable = np.abs(ratios) >= _CURL_RTOL * r_max
    else:
        acceptable = np.ones(n_k, dtype=bool)   # degenerate: all curl-free
    eligible = acceptable & (vals > 0.0)
    if not np.any(eligible):
        raise ValueError(
            "no candidate has a positive beta^2 among "
            f"beta^2 = {vals.tolist()} (curl ratios {ratios.tolist()}); the "
            "shift sigma is probably outside the propagating part of the "
            "spectrum"
        )
    chosen = int(np.flatnonzero(eligible)[np.argmax(vals[eligible])])

    e_t = np.zeros(mesh.n_edges)
    e_t[free] = normalised[:, chosen]

    beta_sq = float(vals[chosen])
    return Mode2D(
        freq=float(k0 * C0 / (2.0 * np.pi)),
        k0=k0,
        beta=float(np.sqrt(beta_sq)) if beta_sq >= 0.0 else float("nan"),
        beta_sq=beta_sq,
        eps_eff=float(beta_sq / (k0 * k0)),
        residual=float(residuals[chosen]),
        candidates=tuple((float(v), float(v / (k0 * k0))) for v in vals),
        curl_ratio=tuple(float(r) for r in ratios),
        chosen=chosen,
        sigma=sigma,
        n_dof=n_dof,
        n_pec=int(mask.sum()),
        e_t=e_t,
        mesh=mesh,
    )


def solve_modes_mixed(
    mesh: Mesh2D,
    k0: float,
    sigma: float = 1.0,
    *,
    eps_r=1.0,
    mu_r=1.0,
    boundaries=(),
    k: int = 8,
    dense: bool | None = None,
) -> Mode2D:
    """Solve the mixed ``(e_t, e_z)`` pencil ``A x = beta^2 B x``.

    Parameters
    ----------
    mesh:
        The triangulation.
    k0:
        Vacuum wavenumber [rad/m].
    sigma:
        Recorded on the result only.  This is a dense QZ solve of the
        *linear-in-``beta^2``* pencil, so there is no shift to choose; the
        argument is kept for signature symmetry with :func:`solve_modes`.
    eps_r, mu_r:
        Per-triangle material, as for :func:`assemble`.
    boundaries:
        PEC predicates.  The **edge** mask of :func:`pec_edge_mask` cuts
        ``e_t`` and the **node** mask of :func:`pec_node_mask` cuts ``e_z``;
        the two combination rules deliberately differ -- see that function.
    k:
        Recorded for signature symmetry; the dense path returns the complete
        spectrum in ``candidates``, so ``k`` truncates nothing.
    dense:
        ``None`` (default) takes the dense path when the number of free edges
        is at most ``_MIXED_DENSE_MAX``.  ``dense=False`` raises
        ``NotImplementedError`` -- see the Notes.

    Returns
    -------
    Mode2D
        With ``e_z`` filled in, ``n_dof = n_free_edges + n_free_nodes`` and
        ``residual`` the *two-field block* residual (see Notes).

    Notes
    -----
    Weak form (fields ``~ exp(-i beta z)``, ``q(v) = d_x v_y - d_y v_x``)::

        INT (1/mu)[ q(e_t) q(w_t) + grad(e_z).grad(w_z) + beta^2 e_t.w_t
                    + i beta ( grad(e_z).w_t - e_t.grad(w_z) ) ] dA
            = k0^2 INT eps [ e_t.w_t + e_z w_z ] dA

    in the blocks of :func:`assemble_mixed` plus ``k_q`` from
    :func:`assemble`: ``m1``, ``k_q``, ``m_eps`` (edge x edge), ``c``
    (edge x node, ``c[e, i] = INT (1/mu) grad(phi_i).w_e``), ``k_zz`` and
    ``m_zz`` (node x node).  ``k_q`` is the curl-curl term and it **does**
    belong in the pencil: ``q`` is a purely transverse operator, so ``k_q`` is
    ``beta``-independent, and that is exactly why the block system below is
    linear in ``beta^2``.  Without it the pencil is a quasi-TEM-only operator
    (``beta^2 = k0^2 eps_r`` is then an identity, not a result)::

        [ [ beta^2 m1 + k_q - k0^2 m_eps ,  i beta c       ] [x_t]   [0]
          [ -i beta c^T                  ,  k_zz - k0^2 m_zz ] [x_z] = [0]

    Row 2 gives ``x_z = i beta D c^T x_t`` with
    ``D = (k_zz - k0^2 m_zz)^{-1}`` -- factored **once** per ``k0`` (``D`` is
    ``beta``-independent) and reused both for the pencil and for the
    reconstruction of ``e_z`` -- and row 1 becomes the linear pencil::

        A x_t = beta^2 B x_t ,   A = k0^2 m_eps - k_q ,   B = m1 - c D c^T .

    The eigenvalue **is** ``beta^2``: no reciprocal ``1 / beta^2`` side is ever
    formed, which keeps the ``k0 -> 0`` end of a dispersion sweep well-posed.
    ``B`` is genuinely **indefinite** (it is the transverse operator of
    :func:`solve_modes` after elimination, hence negative on the
    above-cutoff/evanescent part of the discrete spectrum), so
    ``scipy.linalg.eigh`` is not applicable; the dense path uses
    ``scipy.linalg.eig`` (QZ), which returns the complete spectrum and accepts
    an indefinite ``B``.  Only eigenvalues with
    ``|Im(lambda)| <= 1e-6 max(1, |lambda|)`` are kept.

    What the homogeneous anchors can and cannot see: for a uniform transverse
    field ``q(e_t) = 0`` **and** ``c^T e_t = 0`` hold exactly, so
    ``A x = k0^2 m_eps x``, ``B x = m1 x`` and ``beta^2 / k0^2 = eps_r`` to
    machine precision *whether or not* ``k_q`` is present.  Anchors (i)/(ii)
    therefore validate the plumbing (masks, assembly, elimination,
    reconstruction) only.  The load-bearing anchor is a **curling** mode:
    ``TE10`` in a PEC box, where ``q(e_t) != 0`` and a missing ``k_q`` shows up
    as ``beta^2 / k0^2 = 1.0`` instead of ``0.4383``.

    ``residual`` on the result is the relative *two-field* residual
    ``||M(beta^2) [x_t; x_z]|| / (||M||_F ||[x_t; x_z]||)`` of the block system
    above, rebuilt from the returned fields: it is a *diagnostic* of the
    coupling sign of ``c`` (measured O(1e-1 .. 1) on this pencil), **not** a
    pass/fail guard.
    Candidate selection separately uses the scale-aware relative backward
    error ``||A x - lambda B x|| / ((||A||_F + |lambda| ||B||_F) ||x||)``
    against ``_MIXED_RESIDUAL_TOL``, then takes the largest positive
    ``beta^2``; the whole candidate list is returned either way so the choice
    can be audited.  Normalising by ``||B x||`` instead is not usable here:
    ``B = m1 - C D C^T`` is strongly indefinite, so ``||B x||`` can be orders
    of magnitude below ``||A x - lambda B x||`` on a genuine eigenpair and
    that ratio is unattainable.

    Remaining work: an iterative path.  ``A - sigma B`` is **dense** through
    ``c D c^T``, so the ARPACK shift-invert route used by :func:`solve_modes`
    is not available here as it stands; ``dense=False``, or a mesh with more
    than ``_MIXED_DENSE_MAX`` free edges, raises ``NotImplementedError``
    instead of returning something silently wrong.
    """
    k0 = float(k0)
    sigma = float(sigma)
    if not np.isfinite(k0) or k0 <= 0.0:
        raise ValueError(f"k0 must be positive and finite, got {k0!r}")
    if not np.isfinite(sigma):
        raise ValueError(f"sigma must be finite, got {sigma!r}")

    k_q, m_mu, m_eps = assemble(mesh, eps_r=eps_r, mu_r=mu_r)
    m1, m_eps_mixed, c, k_zz, m_zz = assemble_mixed(mesh, eps_r=eps_r, mu_r=mu_r)
    if m1.shape != k_q.shape or m1.shape != m_eps.shape:
        raise RuntimeError(
            f"assemble() gives {k_q.shape} but assemble_mixed() gives "
            f"{m1.shape}; the two edge numberings do not agree"
        )
    gap_mu = np.abs(m1 - m_mu).max() if (m1 - m_mu).nnz else 0.0
    if gap_mu > 1e-12 * float(np.abs(m1).max()):
        raise RuntimeError(
            f"assemble() and assemble_mixed() disagree on 1/mu mass "
            f"(max |m_mu - m1| = {gap_mu:g})"
        )
    gap_eps = np.abs(m_eps - m_eps_mixed).max() if (m_eps - m_eps_mixed).nnz else 0.0
    if gap_eps > 1e-12 * float(np.abs(m_eps).max()):
        raise RuntimeError(
            f"assemble() and assemble_mixed() disagree on eps mass "
            f"(max |m_eps - m_eps_mixed| = {gap_eps:g})"
        )

    # --- k_q sanity: a uniform transverse field is curl-free ----------------
    tangent = mesh.nodes[mesh.edges[:, 1]] - mesh.nodes[mesh.edges[:, 0]]
    uniform = tangent[:, 1]                                  # tangent . y_hat
    curl_leak = float(np.linalg.norm(k_q @ uniform)) / (
        float(np.abs(k_q).max()) * float(np.linalg.norm(uniform))
    )
    if curl_leak > 1e-8:
        raise RuntimeError(
            "k_q is not the curl-curl operator of the edge numbering in use: "
            f"|k_q @ uniform| / (|k_q|_max |uniform|) = {curl_leak:g}"
        )

    edge_pec = pec_edge_mask(mesh, boundaries)
    node_pec = pec_node_mask(mesh, boundaries)
    free_e = np.flatnonzero(~edge_pec)
    free_n = np.flatnonzero(~node_pec)
    n_e = int(free_e.size)
    n_n = int(free_n.size)
    if n_e < 3:
        raise ValueError(f"only {n_e} free edge DOFs after the PEC cut")
    if n_n < 1:
        raise ValueError("every node is a PEC node; no longitudinal DOFs left")

    use_dense = (n_e <= _MIXED_DENSE_MAX) if dense is None else bool(dense)
    if not use_dense:
        raise NotImplementedError(
            "iterative path pending: A - sigma*B is dense through C D C^T; "
            "dense QZ only"
        )

    m1_f = m1[free_e][:, free_e].tocsc()
    m_eps_f = m_eps[free_e][:, free_e].tocsc()
    k_q_f = k_q[free_e][:, free_e].tocsc()
    c_f = c[free_e][:, free_n].tocsc()
    h = (k_zz[free_n][:, free_n] - k0 * k0 * m_zz[free_n][:, free_n]).tocsc()
    try:
        lu_h = splu(h)
    except RuntimeError as exc:
        raise ValueError(
            f"the longitudinal block k_zz - k0^2 m_zz is singular at "
            f"k0 = {k0!r} ({exc}); nudge k0 off the nodal Dirichlet eigenvalue"
        ) from exc

    d_dense = lu_h.solve(np.eye(n_n))              # D = inv(k_zz - k0^2 m_zz)
    a_dense = k0 * k0 * m_eps_f.toarray() - k_q_f.toarray()
    b_dense = m1_f.toarray() - (c_f @ d_dense) @ c_f.toarray().T
    a_dense = 0.5 * (a_dense + a_dense.T)
    b_dense = 0.5 * (b_dense + b_dense.T)

    lam, vecs = _dense_eig(a_dense, b_dense)
    lam = np.asarray(lam)
    n_cand = int(lam.size)
    lam_real = np.real(lam)
    real_enough = np.abs(np.imag(lam)) <= 1e-6 * np.maximum(1.0, np.abs(lam))

    # --- per-candidate normalisation, pencil residual and curl ratio --------
    normalised = np.real(vecs)
    norms = np.linalg.norm(normalised, axis=0)
    norms[norms == 0.0] = 1.0
    normalised = normalised / norms
    norm_a = float(np.linalg.norm(a_dense))
    norm_b = float(np.linalg.norm(b_dense))
    numer = np.linalg.norm(
        a_dense @ normalised - (b_dense @ normalised) * lam_real, axis=0
    )
    denom_scale = norm_a + np.abs(lam_real) * norm_b
    residuals = np.full(n_cand, np.inf)
    live = denom_scale > 0.0
    residuals[live] = numer[live] / denom_scale[live]
    m1x = np.einsum("ij,ij->j", normalised, m1_f @ normalised)
    ratios = np.full(n_cand, np.nan)
    live = np.abs(m1x) > 0.0
    ratios[live] = (
        np.einsum("ij,ij->j", normalised, k_q_f @ normalised)[live] / m1x[live]
    )

    beta_sq = np.where(real_enough, lam_real, np.nan)

    # --- mode selection ---------------------------------------------------
    order = np.argsort(-beta_sq)
    beta_sq = beta_sq[order]
    residuals = residuals[order]
    ratios = ratios[order]
    normalised = normalised[:, order]

    eligible = (
        np.isfinite(beta_sq)
        & (beta_sq > 0.0)
        & (residuals < _MIXED_RESIDUAL_TOL)
    )
    if not np.any(eligible):
        raise ValueError(
            "no candidate has a finite positive beta^2 with a relative residual "
            f"below {_MIXED_RESIDUAL_TOL:g}: beta^2 = {beta_sq.tolist()}, "
            f"residuals = {residuals.tolist()}"
        )
    chosen = int(np.flatnonzero(eligible)[np.argmax(beta_sq[eligible])])

    x = normalised[:, chosen]
    beta = float(np.sqrt(beta_sq[chosen]))
    e_t = np.zeros(mesh.n_edges)
    e_t[free_e] = x

    e_z = np.zeros(mesh.n_nodes, dtype=complex)
    e_z[free_n] = 1j * beta * lu_h.solve(c_f.T @ x)

    # --- guard: the rebuilt two-field block system must be satisfied --------
    block = vstack(
        [
            hstack([beta * beta * m1_f + k_q_f - k0 * k0 * m_eps_f, 1j * beta * c_f]),
            hstack([-1j * beta * c_f.T, h]),
        ]
    ).tocsc()
    field = np.concatenate([x, e_z[free_n]])
    block_norm = float(np.sqrt(np.sum(np.abs(block.data) ** 2)))
    block_residual = float(np.linalg.norm(block @ field)) / (
        block_norm * float(np.linalg.norm(field))
    )

    return Mode2D(
        freq=float(k0 * C0 / (2.0 * np.pi)),
        k0=k0,
        beta=beta,
        beta_sq=float(beta_sq[chosen]),
        eps_eff=float(beta_sq[chosen] / (k0 * k0)),
        residual=block_residual,
        candidates=tuple((float(b), float(b / (k0 * k0))) for b in beta_sq),
        curl_ratio=tuple(float(r) for r in ratios),
        chosen=chosen,
        sigma=sigma,
        n_dof=n_e + n_n,
        n_pec=int(edge_pec.sum()),
        e_t=e_t,
        mesh=mesh,
        e_z=e_z,
    )


# ----------------------------------------------------------------------
# quasi-static Laplace capacitance
# ----------------------------------------------------------------------
def _p1_stiffness(mesh: Mesh2D, eps_t: np.ndarray) -> csr_matrix:
    """Nodal ``P1`` stiffness ``K[i, j] = sum_t area_t eps_t grad_i . grad_j``."""
    dot = np.einsum("tij,tkj->tik", mesh.grad, mesh.grad)      # (nt, 3, 3)
    k_loc = (mesh.area * eps_t)[:, None, None] * dot
    n = mesh.n_nodes
    rows = np.repeat(mesh.tris, 3, axis=1).ravel()
    cols = np.tile(mesh.tris, (1, 3)).ravel()
    return coo_matrix((k_loc.reshape(-1), (rows, cols)), shape=(n, n)).tocsr()


def _laplace_phi(k: csr_matrix, v1: np.ndarray, v0: np.ndarray) -> np.ndarray:
    """``K phi = 0`` on the free nodes, ``phi = 1`` on ``v1`` and ``0`` on ``v0``."""
    phi = np.zeros(k.shape[0])
    phi[v1] = 1.0
    fixed = v1 | v0
    free = ~fixed
    if not np.any(free):
        raise ValueError("every node is a Dirichlet node; nothing to solve")
    kff = k[free][:, free].tocsc()
    kfc = k[free][:, fixed]
    phi[free] = spsolve(kff, -(kfc @ phi[fixed]))
    return phi


def _dirichlet_groups(mesh: Mesh2D, boundaries=(), groups=None) -> tuple:
    """``(v1, v0)`` node masks of the two conductors of a Laplace problem.

    ``groups`` wins when given.  Otherwise the union of the PEC predicates is
    split by mesh connectivity, which must give exactly two connected groups.
    """
    if groups is not None:
        masks = [np.asarray(m, dtype=bool) for m in groups]
        if len(masks) != 2:
            raise ValueError(f"groups must be two node masks, got {len(masks)}")
        for i, on in enumerate(masks):
            if on.shape != (mesh.n_nodes,):
                raise ValueError(
                    f"groups[{i}] has shape {on.shape}, expected ({mesh.n_nodes},)"
                )
        if np.any(masks[0] & masks[1]):
            raise ValueError("groups[0] and groups[1] overlap")
        if not (np.any(masks[0]) and np.any(masks[1])):
            raise ValueError("both groups must be non-empty")
        return masks[0], masks[1]

    if not boundaries:
        raise ValueError(
            "give boundaries= (PEC predicates, as for pec_edge_mask) or "
            "groups= (explicit node masks)"
        )
    on = np.zeros(mesh.n_nodes, dtype=bool)
    for index, predicate in enumerate(boundaries):
        b = np.asarray(predicate(mesh.nodes), dtype=bool)
        if b.shape != (mesh.n_nodes,):
            raise ValueError(
                f"boundary predicate {index} returned shape {b.shape}, "
                f"expected ({mesh.n_nodes},)"
            )
        on |= b
    if not np.any(on):
        raise ValueError("the boundary predicates mark no nodes")

    lo, hi = mesh.edges[:, 0], mesh.edges[:, 1]
    inner = on[lo] & on[hi]
    node = np.flatnonzero(on)
    local = np.full(mesh.n_nodes, -1, dtype=np.int64)
    local[node] = np.arange(node.size)
    adj = coo_matrix(
        (np.ones(int(inner.sum())), (local[lo[inner]], local[hi[inner]])),
        shape=(node.size, node.size),
    ).tocsr()
    ncomp, label = connected_components(adj, directed=False)
    if ncomp != 2:
        raise ValueError(
            f"the PEC boundary splits into {ncomp} connected groups, not 2; "
            "pass groups=(mask_v1, mask_v0) explicitly"
        )
    full = np.full(mesh.n_nodes, -1, dtype=np.int64)
    full[node] = label
    parts = [on & (full == c) for c in range(2)]
    # ``phi = 1`` on the upper conductor; the other way round gives the same
    # capacitance, so this only fixes which one is "high".
    parts.sort(key=lambda m: -float(mesh.nodes[m, 1].mean()))
    return parts[0], parts[1]


def eps_eff_laplace(mesh: Mesh2D, eps_t, *, boundaries=(), groups=None) -> dict:
    """Effective permittivity from the quasi-static capacitance of a section.

    Weak form
    ---------
    Find a continuous ``P1`` potential ``phi`` satisfying

        INT eps_t grad(phi) . grad(v) dA = 0

    for every test function ``v`` vanishing on the Dirichlet nodes, i.e. the
    Galerkin discretisation of ``div(eps_t grad phi) = 0``.  With

        K[i, j] = sum_t area_t eps_t[t] grad(lambda_i) . grad(lambda_j)

    the free-node equations are ``K phi = 0``; the stiffness is assembled from
    the same ``mesh.grad`` / ``mesh.area`` the full-wave assembler uses, and
    ``eps_t`` is sampled per triangle exactly as :func:`assemble` does it.

    Boundary convention
    -------------------
    * **Dirichlet (essential)**: ``phi = 1`` on conductor ``v1`` and ``phi = 0``
      on conductor ``v0`` -- rows *and* columns eliminated, never a penalty.
      The two groups come from the PEC predicates via mesh connectivity when
      they split in two, else from explicit caller masks (``groups``).
    * **Neumann (natural)**: everywhere else.  Nothing is imposed and no
      boundary term appears in the weak form, so the outer walls are symmetry
      planes, not conductors.

    At ``V = 1`` the stored charge equals the Dirichlet energy

        C = phi^T K phi = INT eps_t |grad phi|^2 dA      (eps0 = 1).

    ``eps_eff`` is the **capacitance ratio**

        eps_eff = C(eps_t) / C(eps_t = 1 everywhere)

    on the same mesh and the same Dirichlet data, so the two solves differ only
    in the right-hand side (one matrix pattern, two ``spsolve`` calls).
    Dividing by ``C0`` is what makes this general: it is correct both for two
    plates of equal width and for a microstrip, where the strip and the ground
    plane have different widths.

    The field-energy quotient ``INT eps |E|^2 / INT |E|^2`` -- the ``e^T M_eps
    e / e^T M_mu e`` functional of the full-wave pencil in this module -- is a
    **different** functional and must not be used as ``eps_eff``: for a section
    with unequal conductors it weights the field by the modal profile rather
    than by the charge, and it does not reduce to ``C / C0``.

    Parameters
    ----------
    mesh : Mesh2D
    eps_t : scalar, (nt,) array or callable
        Relative permittivity per triangle, same layout as ``assemble``
        (a callable is evaluated at ``mesh.centroid``).
    boundaries : sequence of callables, optional
        PEC node predicates, exactly as for :func:`pec_edge_mask`.  Their union
        must split, through the mesh connectivity, into exactly two connected
        groups; those are the two conductors.
    groups : (mask_v1, mask_v0), optional
        Explicit Dirichlet node masks, for a conductor set that does not split
        in two (a connected conductor with a gap, three surfaces, ...).

    Returns
    -------
    dict
        ``eps_eff`` (``C / C0``), ``C``, ``C0`` (both with ``eps0 = 1``),
        ``phi`` (``(nn,)`` the solved potential), ``v1`` / ``v0`` (the node
        masks used) and ``n_free`` (free nodal DOFs).
    """
    eps = _per_triangle(eps_t, mesh, "eps_t")
    if np.any(eps <= 0.0):
        raise ValueError("eps_t must be positive")
    v1, v0 = _dirichlet_groups(mesh, boundaries, groups)

    k = _p1_stiffness(mesh, eps)
    k_unit = _p1_stiffness(mesh, np.ones(mesh.n_tris))
    phi = _laplace_phi(k, v1, v0)
    phi0 = _laplace_phi(k_unit, v1, v0)

    c = float(phi @ (k @ phi))
    c0 = float(phi0 @ (k_unit @ phi0))
    if not (np.isfinite(c) and np.isfinite(c0)) or c0 <= 0.0:
        raise RuntimeError(f"degenerate capacitances C = {c!r}, C0 = {c0!r}")

    return {
        "eps_eff": c / c0,
        "C": c,
        "C0": c0,
        "phi": phi,
        "v1": v1,
        "v0": v0,
        "n_free": int(mesh.n_nodes - np.count_nonzero(v1 | v0)),
    }
