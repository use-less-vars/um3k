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
from scipy.linalg import cholesky as _dense_cholesky
from scipy.linalg import eig as _dense_eig
from scipy.linalg import qr as _dense_qr
from scipy.linalg import solve_triangular as _solve_triangular
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
    "candidate_records",
    "eps_eff_laplace",
    "k0_from_freq",
    "mesh_from_grid",
    "pec_edge_mask",
    "pec_node_mask",
    "solve_modes",
    "solve_modes_deflated",
    "solve_modes_deflated_v2",
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

#: Mode-eligibility guard, applied at the point of selection in both the
#: ``(k_q, m_eps)`` pencil (:func:`_select_and_pack`) and the mixed pencil
#: (:func:`solve_modes_mixed`).  A candidate is not a candidate for the mode of
#: a cross-section unless
#:
#: (i) it carries real curl energy.  Candidates are normalised so that
#:     ``e^T B e == 1`` *before* the ratio is formed, so ``curl_ratio`` is
#:     dimensionless and comparable across the candidates of one pencil: a
#:     discrete gradient state has ``e^T K_q e == 0`` in exact arithmetic and
#:     measures at roundoff -- 2.6e-10 against a physical state's 3670 at the
#:     20 x 16 box, i.e. 7e-14 of it.  The floor sits four decades above that
#:     measurement and seven decades below the weakest non-gradient candidate in
#:     the observed census (17.3), so it separates the two populations with a
#:     wide margin on both sides.  It was first written as ``1e2``; that is
#:     wrong for a normalised quantity and it rejected legitimate fields on
#:     small synthetic pencils, where the whole spectrum is O(1-10).
#: (ii) it is *slower* than the fastest material present,
#:     ``eps_eff < max(eps_r) - _EPS_EFF_RTOL``.  Test (ii) is what removes the
#:     homogeneous states at ``beta^2 = k0^2 eps_r`` that otherwise compete for
#:     "largest beta^2" and win, the epsilon being the 4.3999999-versus-4.4
#:     roundoff that the band predicate alone cannot see.
#:
#: The guard only ever removes candidates, so a pick that already satisfied it
#: is unchanged.  ``guard=False`` on the solvers switches it off entirely and
#: restores the unguarded selection verbatim.
_CURL_RATIO_MIN = 1.0e-6
_EPS_EFF_RTOL = 1.0e-6

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
        candidate_residuals
                    tuple   ``||C e - beta_sq B e|| / ||B e||`` per candidate,
                            index-aligned with ``candidates``; the chosen mode's
                            value is the scalar ``residual`` above, and the rest
                            are carried so a root paired to a candidate that was
                            *not* chosen can still be scored.
        sigma       float   the shift handed to ``eigsh``
        n_dof       int     free (non-PEC) edge count the solve ran on
        n_pec       int     eliminated edges

    Geometry and field::

        e_t         (ne,)   the eigenvector on the *full* edge list, normalised
                            so that ``e^T B e = 1``, zero on every PEC edge
        e_t_candidates
                    (ne, nc) the *same* representation for **every** candidate
                            the solve kept, one column per entry of
                            ``candidates`` (``nc == len(candidates)``): each
                            column is normalised so that ``e^T B e = 1`` and is
                            zero on every PEC edge, and column ``chosen`` is
                            ``e_t`` itself.  :meth:`candidate_e_t` hands one
                            column out; :func:`solve_modes_mixed` does not fill
                            it, so it is ``None`` on that path.
        e_z         (nn,)   nodal longitudinal field of the *mixed* formulation
                            (:func:`solve_modes_mixed`) as a complex phasor
                            ``-i beta (k_zz - k0^2 m_zz)^{-1} c^T e_t``; ``None``
                            for the ``e_t``-only solve.  For a propagating mode
                            it is purely imaginary, so ``abs(e_z)`` is the
                            physical amplitude.  :meth:`e_at` does *not*
                            include it -- see the note there.
        mesh        Mesh2D  the triangulation; ``nodes``, ``tris`` and ``edges``
                            are properties onto it
        deflation   dict    diagnostics of :func:`solve_modes_deflated`
                            (``None`` on the two undeflated paths): the built
                            dimension of ``Z`` against the structural count,
                            the measured ``||Z^T B R||`` and ``||R^T B R - I||``
                            residuals, the conditioning of the block ``R`` was
                            built from, and the three residual ratios of the
                            preregistration 2.d

    ``e_t`` is the *edge* representation: ``e_t[i]`` is ``INT_edge E . dl`` in
    volts at unit field amplitude, i.e. the edge length is already folded in.
    :meth:`e_at` is the continuous field.

    Every column of ``e_t_candidates`` is an eigenvector, hence fixed only up to
    a scalar.  The solver's normalisation pins the scale (``e^T B e = 1``) but
    not the sign: a different LAPACK/ARPACK build, or a different shift, may
    hand back the opposite sign for the same physical mode.  Compare two
    candidates by ``abs(...)`` or by a normalised inner product
    ``|<u, B v>| / (||u||_B ||v||_B)`` -- never by signed equality.  ``e_t`` is
    the one exception, because it is packed from column ``chosen`` by the same
    two statements, so ``candidate_e_t(chosen)`` reproduces ``e_t`` bit for bit.
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
    deflation: dict | None = None
    candidate_residuals: tuple = ()
    e_t_candidates: np.ndarray | None = None

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

    def _interp_t(self, vec: np.ndarray, points) -> np.ndarray:
        """Whitney interpolation of an arbitrary edge vector.

        The arithmetic of :meth:`e_at` with ``vec`` in place of ``self.e_t``,
        split out so that a candidate other than the chosen one can be drawn;
        :meth:`e_at` keeps its own copy and is unchanged.
        """
        pts = np.ascontiguousarray(points, dtype=float)
        tri = self._locate(pts)
        v = self.mesh.nodes[self.mesh.tris[tri]]          # (n, 3, 2)
        g = self.mesh.grad[tri]                           # (n, 3, 2)
        lam = 1.0 + np.einsum("nij,nij->ni", pts[:, None, :] - v, g)

        sgn = self.mesh.tri_sign[tri]                      # (n, 3)
        w = sgn * vec[self.mesh.tri_edges[tri]]            # (n, 3) oriented DOFs

        n_idx = np.arange(pts.shape[0])[:, None]
        lam_a = lam[n_idx, _LOCAL_A[None, :]]              # (n, 3)
        lam_b = lam[n_idx, _LOCAL_B[None, :]]
        ga = g[:, _LOCAL_A, :]                             # (n, 3, 2)
        gb = g[:, _LOCAL_B, :]
        terms = w[:, :, None] * (lam_a[:, :, None] * gb - lam_b[:, :, None] * ga)
        return terms.sum(axis=1)

    def candidate_e_t(self, index: int) -> np.ndarray:
        """The ``index``-th candidate's eigenvector, in :attr:`e_t`'s layout.

        The return is ``(ne,)`` -- the eigenvector on the *full* edge list, zero
        on every PEC edge, normalised so that ``e^T B e = 1``: exactly the
        representation :attr:`e_t` uses, so any candidate can be drawn with the
        same code that draws the chosen one, and ``candidate_e_t(chosen)`` is
        ``e_t`` bit for bit.  The vector is defined only up to sign (see the
        class docstring), so callers compare ``abs(...)``, not signed values.

        A fresh copy is returned.  An ``index`` outside
        ``0 .. len(candidates) - 1`` raises :class:`IndexError` naming the valid
        range; a result that carries no candidates (``e_t_candidates is None``,
        i.e. :func:`solve_modes_mixed`) raises :class:`RuntimeError`.
        """
        if self.e_t_candidates is None:
            raise RuntimeError(
                "this Mode2D carries no candidate eigenvectors "
                "(e_t_candidates is None): they are retained by solve_modes and "
                "solve_modes_deflated, not by solve_modes_mixed"
            )
        n_cand = int(self.e_t_candidates.shape[1])
        if not 0 <= int(index) < n_cand:
            raise IndexError(
                f"candidate index {index!r} out of range: this solve retained "
                f"{n_cand} candidates, so the valid indices are 0..{n_cand - 1}"
            )
        return np.array(self.e_t_candidates[:, int(index)], dtype=float, copy=True)

    def e_at_candidate(self, index: int, points) -> np.ndarray:
        """Transverse field of candidate ``index`` at arbitrary interior points.

        :meth:`e_at` with ``candidate_e_t(index)`` in place of ``e_t``: ``(n, 2)``
        points in metres, ``(n, 2)`` out, transverse field only (``e_z`` is not
        interpolated -- see :meth:`e_at`).  Raises what :meth:`candidate_e_t`
        raises.
        """
        return self._interp_t(self.candidate_e_t(index), points)


def candidate_records(res) -> tuple:
    """Every candidate of ``res`` as a flat record that carries its diagnostic.

    ``Mode2D.candidates`` is a tuple of ``(beta_sq, eps_eff)`` pairs and
    nothing else, so an artefact that stores only that tuple loses the one
    number that says whether a candidate is a physical mode or a spurious
    gradient mode: the curl ratio ``e^T K_q e / e^T B e`` held in
    :attr:`Mode2D.curl_ratio` (zero to working precision marks a gradient
    null vector, whose ``beta_sq`` is exactly ``k0^2``).  Mode purity is then
    lost to any reader of the stored artefact -- neither the pair list nor the
    chosen index can be re-checked against the curl test.

    This returns *the same* candidates, in the same order, with that
    diagnostic attached: one ``dict`` per candidate, index-aligned with
    ``res.candidates`` (``record["index"] == i`` describes
    ``res.candidates[i]``, and all of them are returned, including those that
    fail the solver's ``acceptable`` curl test).  The key names and the
    ``beta``/``None`` convention follow ``candidate_rows`` in
    ``tools/host/anchor/ladder.py`` (the two agree on what a key holds, not on
    what ``index`` means: ``candidate_rows`` sorts, this function does not).
    ``beta`` states the three cases apart: ``sqrt(beta_sq)`` when
    ``beta_sq > 0`` (propagating), ``None`` when ``beta_sq == 0`` (exactly at
    cutoff -- no real propagation constant and no decay either) and ``None``
    when ``beta_sq < 0`` (evanescent, below cutoff).  ``beta_imag`` carries that
    third case's decay constant ``sqrt(-beta_sq)`` [1/m] and is ``0.0``
    otherwise, matching :attr:`Mode2D.beta_imag`; ``propagating`` is the plain
    ``bool`` of ``beta_sq > 0``, matching :attr:`Mode2D.is_propagating`.
    ``residual`` is that
    candidate's own ``||C e - beta_sq B e|| / ||B e||`` -- the scalar the chosen
    mode reports as ``Mode2D.residual``, carried per candidate so a root paired
    to a candidate that was *not* chosen can still be scored; it is ``None``
    when the result does not carry ``candidate_residuals``.

    Every value is a plain Python ``int``/``float`` (or ``None``), never a
    numpy scalar, so the tuple drops straight into ``json.dump``.

    This is additive: :attr:`Mode2D.candidates` itself is unchanged, nothing
    in the solver calls this, and the class is only read.
    """
    pairs = list(res.candidates)
    ratios = list(res.curl_ratio)
    residuals = list(getattr(res, "candidate_residuals", ()) or ())
    if len(ratios) != len(pairs):
        raise ValueError(
            f"mode 2D result is inconsistent: {len(pairs)} candidates but "
            f"{len(ratios)} curl ratios; the two must be index-aligned"
        )
    if residuals and len(residuals) != len(pairs):
        raise ValueError(
            f"mode 2D result is inconsistent: {len(pairs)} candidates but "
            f"{len(residuals)} residuals; the two must be index-aligned"
        )
    records = []
    for i, ((beta_sq, eps_eff), curl_ratio) in enumerate(zip(pairs, ratios)):
        bsq = float(beta_sq)
        cr = float(curl_ratio)
        propagating = bsq > 0.0
        records.append(
            {
                "index": int(i),
                "beta": float(np.sqrt(bsq)) if propagating else None,
                "beta_imag": float(np.sqrt(-bsq)) if bsq < 0.0 else 0.0,
                "propagating": bool(propagating),
                "beta_sq": bsq,
                "eps_eff": float(eps_eff),
                "curl_ratio": cr,
                "abs_curl_ratio": abs(cr),
                "residual": float(residuals[i]) if residuals else None,
            }
        )
    return tuple(records)


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
    guard: bool = True,
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
    guard:
        Apply the mode-eligibility guard (:data:`_CURL_RATIO_MIN`,
        :data:`_EPS_EFF_RTOL`) at the point of selection: reject candidates with
        ``|curl_ratio| < 1e-6`` and candidates with
        ``eps_eff >= max(eps_r) - 1e-6``, then take the largest positive
        ``beta_sq`` among the survivors.  ``guard=False`` restores the unguarded
        selection verbatim.

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

    eps_t = _per_triangle(eps_r, mesh, "eps_r")
    eps_max = float(np.max(eps_t))
    k_q, m_mu, m_eps = assemble(mesh, eps_r=eps_t, mu_r=mu_r)
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

    return _select_and_pack(
        mesh=mesh,
        k0=k0,
        sigma=sigma,
        k_q=k_q,
        c_free=c_free,
        b_free=b_free,
        free=free,
        mask=mask,
        n_dof=n_dof,
        n_k=n_k,
        vals=vals,
        vecs=vecs,
        eps_max=eps_max,
        guard=guard,
    )


def _guarded_choice(
    *,
    eligible: np.ndarray,
    beta_sq: np.ndarray,
    eps_eff: np.ndarray,
    curl: np.ndarray,
    eps_max: float,
    where: str,
) -> int:
    """Index of the largest ``beta_sq`` among the *guard-passing* candidates.

    ``eligible`` is the caller's own eligibility mask (curl-free filter, positive
    ``beta^2``, residual tolerance); the guard is intersected with it.  On the
    surviving set the historical rule is applied unchanged -- largest positive
    ``beta^2`` -- so a pick that already satisfies the guard is not moved.

    Raises
    ------
    ValueError
        When the guard rejects every otherwise-eligible candidate.  That is a
        statement about the candidate set, not a silent fallback: the list is
        printed so the caller can see whether the shift returned gradient states
        only.
    """
    passes = (np.abs(curl) >= _CURL_RATIO_MIN) & (eps_eff < eps_max - _EPS_EFF_RTOL)
    keep = np.asarray(eligible, dtype=bool) & passes
    if not np.any(keep):
        raise ValueError(
            f"the mode-eligibility guard rejects every candidate of {where} "
            f"(|curl_ratio| >= {_CURL_RATIO_MIN:g} and "
            f"eps_eff < {eps_max:g} - {_EPS_EFF_RTOL:g}): "
            f"beta^2 = {beta_sq.tolist()}, eps_eff = {eps_eff.tolist()}, "
            f"curl_ratio = {curl.tolist()}; pass guard=False to restore the "
            "unguarded selection"
        )
    return int(np.flatnonzero(keep)[np.argmax(beta_sq[keep])])


def _select_and_pack(
    mesh: Mesh2D,
    k0: float,
    sigma: float,
    k_q,
    c_free,
    b_free,
    free: np.ndarray,
    mask: np.ndarray,
    n_dof: int,
    n_k: int,
    vals: np.ndarray,
    vecs: np.ndarray,
    eps_max: float,
    guard: bool = True,
    extra: dict | None = None,
) -> Mode2D:
    """Normalise, select and pack the raw ``eigsh`` output for a free-DOF pencil.

    This is the tail of the historical :func:`solve_modes` body, moved out
    verbatim (same variable names, same arithmetic) so that
    :func:`solve_modes_deflated` applies *exactly* the same normalisation and
    selection rules (preregistration 2.e) to a deflated pencil.  Nothing here
    knows about deflation; ``extra`` is merged into the returned
    :class:`Mode2D` as extra keyword fields (the ``deflation`` diagnostics).

    ``guard=True`` intersects the eligibility mask with the mode-eligibility
    guard (:func:`_guarded_choice`) before the historical "largest positive
    ``beta_sq``" rule is applied; ``eps_max`` is ``max(eps_r)`` over the mesh,
    the material bound of the guard's second test.
    """
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
    if guard:
        chosen = _guarded_choice(
            eligible=eligible,
            beta_sq=vals,
            eps_eff=vals / (k0 * k0),
            curl=ratios,
            eps_max=eps_max,
            where="the (k_q, m_eps) pencil",
        )
    else:
        chosen = int(np.flatnonzero(eligible)[np.argmax(vals[eligible])])

    # --- retain every candidate's eigenvector -----------------------------
    # ``normalised`` is exactly ``(n_free, n_k)``; a narrower one would mean the
    # solver returned fewer columns than it was asked for, and the column
    # indices would no longer line up with ``candidates``.
    if normalised.shape[1] != n_k:
        raise RuntimeError(
            f"the eigensolver returned {normalised.shape[1]} columns for "
            f"n_k = {n_k} candidates; candidate_e_t() indices would not match "
            "the candidate list"
        )

    e_t = np.zeros(mesh.n_edges)
    e_t[free] = normalised[:, chosen]

    # Every candidate in ``e_t``'s own layout, so a UI can draw any of them.
    # Built with the same two statements as ``e_t`` -- column ``chosen`` is
    # therefore bit-identical to ``e_t`` and the chosen path is unchanged.
    e_t_candidates = np.zeros((mesh.n_edges, n_k), dtype=normalised.dtype)
    e_t_candidates[free, :] = normalised

    beta_sq = float(vals[chosen])
    fields = {} if extra is None else dict(extra)
    return Mode2D(
        freq=float(k0 * C0 / (2.0 * np.pi)),
        k0=k0,
        beta=float(np.sqrt(beta_sq)) if beta_sq >= 0.0 else float("nan"),
        beta_sq=beta_sq,
        eps_eff=float(beta_sq / (k0 * k0)),
        residual=float(residuals[chosen]),
        candidates=tuple((float(v), float(v / (k0 * k0))) for v in vals),
        curl_ratio=tuple(float(r) for r in ratios),
        candidate_residuals=tuple(float(r) for r in residuals),
        e_t_candidates=e_t_candidates,
        chosen=chosen,
        sigma=sigma,
        n_dof=n_dof,
        n_pec=int(mask.sum()),
        e_t=e_t,
        mesh=mesh,
        **fields,
    )


# ----------------------------------------------------------------------
# deflation of the discrete gradient subspace
# ----------------------------------------------------------------------
#: Largest number of free DOFs for which the dense ``Z -> R`` construction in
#: :func:`solve_modes_deflated` is attempted.  :func:`_complement_basis` holds a
#: dense ``n x n`` Cholesky factor (``8 n^2`` bytes), a dense ``n x p`` remainder
#: basis and one temporary of the same size, i.e. roughly ``24 n^2`` bytes: 6000
#: DOFs is about 0.9 GB, while 24288 DOFs (the finest rung of the preregistered
#: ladder) would be about 14 GB.  Above the limit the deflated solve raises
#: :class:`NotImplementedError` instead of exhausting memory; see the note in
#: :func:`solve_modes_deflated`.
_DEFLATED_DENSE_MAX = 6000


def _frob_norm(mat) -> float:
    """Frobenius norm of a dense array or of a scipy sparse matrix."""
    data = getattr(mat, "data", mat)
    return float(np.sqrt(np.sum(np.asarray(data, dtype=float) ** 2)))


def _ratio(num: float, den: float) -> float:
    """``num / den``, or ``NaN`` when ``den <= 0`` (the operator is empty)."""
    return float(num / den) if den > 0.0 else float("nan")


def _gradient_columns(
    mesh: Mesh2D,
    eps_t: np.ndarray,
    mu_t: np.ndarray,
    node_pec: np.ndarray,
    region_tol: float = 0.0,
    region_contrast: float = 0.0,
) -> np.ndarray:
    """Nodes usable as columns of the discrete gradient subspace ``Z``.

    Preregistration 2.a / 2.b: on a triangle where ``eps_r == 1 / mu_r`` the
    pencil row ``k0^2 M_eps - K_q`` is a multiple of the pure gradient row
    ``M_mu @ grad``, so a *node* whose whole star is such a triangle carries the
    nodal-gradient field ``e = Z[:, i]`` that the shift-invert solve sees as a
    spurious state at ``beta^2 = k0^2``.  A node qualifies when

    * every triangle adjacent to it satisfies
      ``|eps_r - 1/mu_r - region_contrast| <= region_tol`` (exact equality at the
      default ``region_tol = 0.0`` and ``region_contrast = 0.0``, which is what
      the exactness hypothesis H2 requires), and
    * it is **not** on a PEC predicate (:func:`pec_node_mask`), because the PEC
      rows and columns are deleted and a PEC node carries no free DOF pattern.

    ``region_contrast`` selects *which* constant contrast the region carries: at
    the default ``0.0`` this is the ``eps_r == 1 / mu_r`` block (the air block of
    the pre-registered ladder and the only block the preregistration deflates);
    ``region_contrast = c`` with ``c != 0`` selects the block where
    ``eps_r - 1 / mu_r == c`` exactly, which is what the Amendment 3 widening of
    :func:`_deflation_columns` unions in as well.  The default reproduces the
    original predicate character for character.

    Returns the qualifying node indices, ascending.
    """
    node_pec = np.asarray(node_pec, dtype=bool)
    if node_pec.shape != (mesh.n_nodes,):
        raise ValueError(
            f"node_pec must have shape ({mesh.n_nodes},), got {node_pec.shape}"
        )
    eps_t = np.asarray(eps_t, dtype=float)
    mu_t = np.asarray(mu_t, dtype=float)
    region_contrast = float(region_contrast)
    on_region = (
        np.abs(eps_t - 1.0 / mu_t - region_contrast) <= float(region_tol)
    )
    owner = np.repeat(np.arange(mesh.n_tris), mesh.tris.shape[1])
    outside = mesh.tris.reshape(-1)[~on_region[owner]]
    in_region = np.ones(mesh.n_nodes, dtype=bool)
    in_region[outside] = False
    return np.flatnonzero(in_region & ~node_pec)


def _incidence(mesh: Mesh2D, free: np.ndarray, cols: np.ndarray) -> csr_matrix:
    """Nodal-to-edge matrix of the free edges restricted to the nodes ``cols``.

    ``Z[e, i] = +1`` when the free edge ``e`` runs *into* ``cols[i]`` (the node is
    its ``hi`` endpoint) and ``-1`` when it runs *out of* it (the node is its
    ``lo`` endpoint).  Since the global DOF of edge ``(lo, hi)`` is
    ``INT E . dl`` directed ``lo -> hi``, ``Z[:, i]`` is exactly the edge-DOF
    pattern of the gradient of the ``P1`` nodal function that is one at
    ``cols[i]`` and zero at every other node -- the restricted gradient operator.

    Rows are the free edges in the order of ``free``, columns the order of
    ``cols``.
    """
    free = np.asarray(free, dtype=np.int64)
    cols = np.asarray(cols, dtype=np.int64)
    position = np.full(mesh.n_nodes, -1, dtype=np.int64)
    position[cols] = np.arange(cols.size, dtype=np.int64)
    sub = mesh.edges[free]
    i_lo = position[sub[:, 0]]
    i_hi = position[sub[:, 1]]
    hit_hi = np.flatnonzero(i_hi >= 0)
    hit_lo = np.flatnonzero(i_lo >= 0)
    data = np.concatenate([np.ones(hit_hi.size), -np.ones(hit_lo.size)])
    rows = np.concatenate([hit_hi, hit_lo])
    colidx = np.concatenate([i_hi[hit_hi], i_lo[hit_lo]])
    return coo_matrix(
        (data, (rows, colidx)), shape=(free.size, cols.size)
    ).tocsr()


#: Height fraction ``y = y_min + _LADDER_REGION_FRAC * (y_max - y_min)`` at which
#: the pre-registered ladder's air region ``eps_r == 1 / mu_r`` begins.  The
#: ladder's graded substrate occupies the lower quarter, so the region that
#: carries the gradient columns is the upper ``3 ny / 4`` rows -- the same
#: ``3 ny / 4`` that appears in the closed form ``(nx - 1) (3 ny / 4 - 1)`` --
#: and the line is therefore at a quarter of ``Ly``.
_LADDER_REGION_FRAC = 0.25


def _closed_form_dim(mesh: Mesh2D, in_region: np.ndarray) -> int | None:
    """Closed-form column count ``(nx - 1) (3 ny / 4 - 1)`` of the ladder meshes.

    A cross-check on :func:`_gradient_columns` for the pre-registered ladder
    only, and ``None`` for everything else -- a diagnostic that reports a wrong
    number is worse than one that reports nothing.

    The closed form counts the interior nodes of the air block, so it is only
    quoted when the mesh really is the pre-registered geometry: a structured
    ``(nx, ny)`` cell mesh, ``nx >= 2``, ``ny >= 4``, ``ny`` a multiple of 4,
    *and* the air region ``eps_r == 1 / mu_r`` exactly filling the upper
    ``3 ny / 4`` rows -- every triangle whose centroid is above the line
    ``y = y_min + Ly / 4`` inside it, every triangle below it outside it.

    Parameters
    ----------
    mesh : Mesh2D
        The mesh the columns came from.
    in_region : (nt,) bool array
        Per-triangle region predicate (``|eps_r - 1 / mu_r| <= region_tol``),
        passed in by :func:`solve_modes_deflated` so that this function never
        has to know about ``eps_r`` or ``mu_r``.

    Returns ``None`` when the mesh is not of that shape (the columns actually
    used are whatever :func:`_gradient_columns` returns; this number is
    diagnostics only).
    """
    axes = getattr(mesh, "grid_axes", ()) or ()
    if len(axes) != 2:
        return None
    xs, ys = axes
    xs = np.asarray(xs, dtype=float).ravel()
    ys = np.asarray(ys, dtype=float).ravel()
    nx = int(xs.size) - 1
    ny = int(ys.size) - 1
    if nx < 2 or ny < 4 or ny % 4 != 0:
        return None
    in_region = np.asarray(in_region, dtype=bool)
    if in_region.shape != (mesh.n_tris,):
        raise ValueError(
            f"in_region must have shape ({mesh.n_tris},), got {in_region.shape}"
        )
    y_min = float(np.min(ys))
    y_line = y_min + _LADDER_REGION_FRAC * (float(np.max(ys)) - y_min)
    above = np.asarray(mesh.centroid[:, 1], dtype=float) > y_line
    if not np.all(in_region[above]):
        return None
    if np.any(in_region[~above]):
        return None
    return (nx - 1) * (3 * ny // 4 - 1)


def _closed_form_dim_v2(mesh: Mesh2D, in_region: np.ndarray) -> int | None:
    """Widened column count ``(nx - 1) (ny - 2)`` of the ladder meshes.

    The sibling of :func:`_closed_form_dim` for the Amendment 3 (5.b) widened
    set.  The widened columns are the interior nodes of *both* homogeneous
    blocks of the ladder, so they are the interior nodes minus the interface row
    ``y = T = Ly / 4``, whose stars straddle the material jump and belong to
    neither block: ``ny - 1`` interior rows per interior ``x`` column, less the
    one interface row, i.e. ``(nx - 1) (ny - 2)``.

    Like its v1 sibling this is a cross-check rather than a guess, so it is
    quoted only when the mesh really is the pre-registered geometry -- a
    structured ``(nx, ny)`` cell mesh with ``nx >= 2``, ``ny >= 4`` and ``ny`` a
    multiple of 4 -- *and* ``in_region`` is exactly that node set; ``None``
    otherwise.

    Parameters
    ----------
    mesh : Mesh2D
        The mesh the columns came from.
    in_region : (nn,) bool array
        Per-*node* column mask (``True`` on the nodes that carry a column),
        unlike the per-*triangle* region predicate of :func:`_closed_form_dim`.

    Returns ``None`` when the mesh is not of that shape or the mask is not the
    ladder's widened column set.
    """
    axes = getattr(mesh, "grid_axes", ()) or ()
    if len(axes) != 2:
        return None
    xs, ys = axes
    xs = np.asarray(xs, dtype=float).ravel()
    ys = np.asarray(ys, dtype=float).ravel()
    nx = int(xs.size) - 1
    ny = int(ys.size) - 1
    if nx < 2 or ny < 4 or ny % 4 != 0:
        return None
    in_region = np.asarray(in_region, dtype=bool)
    if in_region.shape != (mesh.n_nodes,):
        raise ValueError(
            f"in_region must have shape ({mesh.n_nodes},), got {in_region.shape}"
        )
    nodes = np.asarray(mesh.nodes, dtype=float)
    x = nodes[:, 0]
    y = nodes[:, 1]
    span = max(
        1.0,
        float(np.max(xs) - np.min(xs)),
        float(np.max(ys) - np.min(ys)),
    )
    tol = 1e-12 * span
    y_line = float(ys[ny // 4])
    wanted = (
        (x >= float(xs[1]) - tol)
        & (x <= float(xs[nx - 1]) + tol)
        & (y >= float(ys[1]) - tol)
        & (y <= float(ys[ny - 1]) + tol)
        & (np.abs(y - y_line) > tol)
    )
    if np.any(in_region & ~wanted):
        return None
    if np.any(wanted & ~in_region):
        return None
    return (nx - 1) * (ny - 2)


def _structured_rows(mesh: Mesh2D, nodes: np.ndarray) -> list[int]:
    """The ``y``-grid levels occupied by ``nodes``, or ``[]`` for a free mesh."""
    axes = getattr(mesh, "grid_axes", ()) or ()
    nodes = np.asarray(nodes, dtype=np.int64)
    if len(axes) != 2 or nodes.size == 0:
        return []
    ys = np.asarray(axes[1], dtype=float).ravel()
    y = np.asarray(mesh.nodes, dtype=float)[nodes, 1]
    level = np.abs(y[:, None] - ys[None, :]).argmin(axis=1)
    return [int(v) for v in np.unique(level)]


def _deflation_columns(
    mesh: Mesh2D,
    eps_t: np.ndarray,
    mu_t: np.ndarray,
    node_pec: np.ndarray,
    widen: bool = False,
    region_tol: float = 0.0,
) -> tuple[np.ndarray, dict]:
    """The deflated column set, and a description of the region it spans.

    ``widen = False`` is preregistration 2.a / 2.b verbatim: the columns of
    :func:`_gradient_columns`, i.e. the nodes whose whole star satisfies
    ``eps_r == 1 / mu_r`` (the air block of the ladder).

    ``widen = True`` is the Amendment 3 (5.b) widened set: those columns *plus*
    the columns of every *other* constant-contrast block.  For each distinct
    contrast value ``c`` of ``eps_r - 1 / mu_r`` present on the mesh with
    ``|c| > region_tol``, the nodes whose whole star has ``eps_r - 1 / mu_r == c``
    exactly are added.  On the pre-registered ladder the only such block is the
    substrate (``eps_r = 2``, ``mu_r = 1``, so ``c = 1``) and the nodes it adds
    are the substrate interior less the interface row ``y = T``, whose stars
    straddle the material jump and so belong to neither block.

    The widening is a *licence* from the Amendment 3 census, not an exactness
    claim: only the ``c = 0`` block is an exact null space of the pencil, so the
    ``residual_eps_mu`` / ``residual_pencil`` diagnostics are expected to be
    non-zero on the widened route (``residual_grad`` stays zero, since a
    gradient field has no curl whatever the contrast).

    Parameters
    ----------
    mesh, eps_t, mu_t, node_pec :
        As for :func:`_gradient_columns`.
    widen : bool
        Use the widened set as the column set (default ``False``: v1 verbatim).
    region_tol : float
        Contrast band, passed through to :func:`_gradient_columns`.

    Returns
    -------
    (cols, info) : (int array, dict)
        ``cols`` are the column node indices actually to be used, ascending.
        ``info`` always describes both sets -- ``column_region`` (``"v1"`` or
        ``"v1+homogeneous-blocks"``: which one ``cols`` is), ``columns_v1``,
        ``columns_added``, ``z_dim_v2`` (= ``columns_v1 + columns_added``, the
        widened total), ``region_contrast`` (the added contrast values) and
        ``region_rows`` (the ``y``-grid levels of the added nodes, ``[]`` off a
        structured mesh).
    """
    eps_t = np.asarray(eps_t, dtype=float)
    mu_t = np.asarray(mu_t, dtype=float)
    cols_v1 = _gradient_columns(mesh, eps_t, mu_t, node_pec, region_tol)
    contrast = eps_t - 1.0 / mu_t
    blocks = []
    added_contrast = []
    for value in np.unique(contrast):
        value = float(value)
        if abs(value) <= float(region_tol):
            continue  # the v1 block, already counted in cols_v1
        block = _gradient_columns(
            mesh, eps_t, mu_t, node_pec, region_tol, region_contrast=value
        )
        if block.size:
            blocks.append(block)
            added_contrast.append(value)
    if blocks:
        cols_all = np.union1d(cols_v1, np.concatenate(blocks))
    else:
        cols_all = cols_v1
    added = np.setdiff1d(cols_all, cols_v1, assume_unique=True)
    info = {
        "column_region": "v1+homogeneous-blocks" if widen else "v1",
        "columns_v1": int(cols_v1.size),
        "columns_added": int(added.size),
        "z_dim_v2": int(cols_all.size),
        "region_contrast": added_contrast,
        "region_rows": _structured_rows(mesh, added),
    }
    return (cols_all if widen else cols_v1), info


def _complement_basis(b_free, z, dense_max: int = _DEFLATED_DENSE_MAX):
    """Dense basis ``R`` of the ``B``-orthogonal complement of ``Z``.

    With ``B = L L^T`` (Cholesky of the free-DOF mass matrix) and the full QR
    ``L^T Z = Q1 R1``, take ``Q = Q1[:, m:]`` (the trailing ``n - m`` columns) and
    set ``R := L^{-T} Q``.  Then ``Z^T B R = R1[:, m:]^T Q = 0`` exactly, and
    ``R^T B R = Q^T Q = I``, so ``eigsh`` on ``(R^T C R, R^T B R)`` is a genuine
    symmetric-definite pencil and the candidates come back already
    mass-normalised.

    Returns ``(R, info)`` with ``R`` dense ``(n, n - m)`` and ``info`` carrying
    ``z_dim``, ``n_free``, ``block_diag_ratio`` (smallest over largest column
    norm of the triangular factor of ``L^T Z`` -- the ``m by m`` block used to
    decide the split), ``z_orthogonality_abs`` (``||Z^T B R||_F``),
    ``z_orthogonality_rel`` (the same, normalised by ``||Z^T B||_F ||R||_F``) and
    ``r_gram_dev`` (``||R^T B R - I||_F / sqrt(n - m)``).

    Raises :class:`NotImplementedError` above ``dense_max`` DOFs (the dense
    factor alone is ``8 n^2`` bytes) and :class:`ValueError` when ``B`` is not
    positive definite on the free DOFs.
    """
    b_dense = b_free.toarray() if hasattr(b_free, "toarray") else np.asarray(
        b_free, dtype=float
    )
    b_dense = np.asarray(b_dense, dtype=float)
    z_dense = z.toarray() if hasattr(z, "toarray") else np.asarray(z, dtype=float)
    z_dense = np.asarray(z_dense, dtype=float)
    n = int(b_dense.shape[0])
    m = int(z_dense.shape[1])
    if n > int(dense_max):
        raise NotImplementedError(
            f"the deflated solve builds a dense {n} x {n} Cholesky factor "
            f"(about {24.0 * n * n / 1e9:.1f} GB); this route is limited to "
            f"{int(dense_max)} free DOFs (see _DEFLATED_DENSE_MAX).  A sparse "
            "or matrix-free complement belongs in a dated amendment of the "
            "preregistration, not in this function."
        )
    if m == 0:
        raise ValueError(
            "no gradient columns: no node has its whole star in the "
            "eps_r == 1/mu_r region, so there is nothing to deflate"
        )
    b_dense = 0.5 * (b_dense + b_dense.T)
    try:
        l_factor = _dense_cholesky(b_dense, lower=True)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            f"B is not positive definite on the free DOFs: {exc}"
        ) from exc
    w = l_factor.T @ z_dense
    q_full, r_factor = _dense_qr(w, mode="full")
    diag = np.abs(np.diag(r_factor)[:m])
    if not np.isfinite(diag).all() or diag.min() <= 0.0:
        raise RuntimeError(
            f"the gradient columns are rank deficient: |R1| diagonal {diag.tolist()}"
        )
    block_diag_ratio = float(diag.min() / diag.max())
    q = q_full[:, m:]
    p = int(n - m)
    r_basis = _solve_triangular(l_factor.T, q, lower=False)
    ztb = (z.T @ b_free).tocsr()
    orth = _frob_norm(ztb @ r_basis)
    if p > 0:
        gram_dev = _frob_norm(r_basis.T @ (b_free @ r_basis) - np.eye(p)) / np.sqrt(p)
    else:
        gram_dev = float("nan")
    info = {
        "z_dim": m,
        "n_free": n,
        "block_diag_ratio": block_diag_ratio,
        "z_orthogonality_abs": orth,
        "z_orthogonality_rel": _ratio(orth, _frob_norm(ztb) * _frob_norm(r_basis)),
        "r_gram_dev": gram_dev,
    }
    return r_basis, info


def solve_modes_deflated(
    mesh: Mesh2D,
    k0: float,
    sigma: float,
    *,
    eps_r=1.0,
    mu_r=1.0,
    boundaries=(),
    k: int = 4,
    region_widen: bool = False,
    guard: bool = True,
) -> Mode2D:
    """Solve the same pencil as :func:`solve_modes`, with the gradient space deflated.

    The pencil is unchanged -- ``A = k0^2 M_eps - K_q``, ``B = M_mu`` -- and so
    are the normalisation and the selection rule.  What changes is the subspace
    the ``eigsh`` call lives on.

    **Z (preregistration 2.a / 2.b).**  ``Z`` collects the nodal-gradient edge
    patterns of every node whose whole star lies in a region with
    ``eps_r == 1 / mu_r`` and which is not on a PEC predicate
    (:func:`_gradient_columns`, :func:`_incidence`).  On the pre-registered
    ladder that is ``11, 69, 329, 1425, 5921`` columns at levels 1-5, against
    ``78, 348, 1464, 6000, 24288`` free DOFs; these are the spurious states that
    sit at ``beta^2 = k0^2`` and otherwise win the "largest positive beta^2"
    selection whenever the physical mode is below them.

    ``region_widen = False`` (the default) is that preregistered set verbatim.
    ``region_widen = True`` -- the widened route of
    :func:`solve_modes_deflated_v2`, licensed by Amendment 3 (5.b) -- also
    deflates the columns of every *other* homogeneous contrast block
    (:func:`_deflation_columns`), which on the ladder adds the substrate
    interior less the interface row: ``3, 21, 105`` columns at levels 1-3, for
    totals of ``14, 90, 434``.  That widening is a census licence, not an
    exactness claim: only the ``eps_r == 1 / mu_r`` block is an exact null space
    of the pencil, so ``residual_eps_mu`` and ``residual_pencil`` are non-zero
    on the widened route by construction.

    **R (2.c / 2.d).**  ``R`` spans the ``B``-orthogonal complement of ``Z``
    with ``Z^T B R = 0`` and ``R^T B R = I`` (:func:`_complement_basis`).  The
    eigenproblem is solved on the deflated pair
    ``(R^T A R, R^T B R)`` and each eigenvector is lifted back with ``x = R y``,
    so the candidates returned are ordinary free-DOF fields.

    **Selection (2.e) is unchanged.**  The candidates are handed to the same
    normalisation and selection code as :func:`solve_modes`
    (:func:`_select_and_pack`), so ``chosen``, ``candidates`` and ``curl_ratio``
    mean exactly what they mean there -- except that the deflated gradient states
    are no longer among the candidates.  ``guard`` is that function's
    mode-eligibility guard, passed through unchanged.

    **Diagnostics.**  ``mode.deflation`` is a dict with ``z_dim``,
    ``z_dim_closed_form`` (the ladder closed form, or ``None`` off the ladder),
    ``n_free``, ``n_dof``, ``n_columns`` (the dimension of ``R``),
    ``block_diag_ratio``, ``z_orthogonality_abs``, ``z_orthogonality_rel``,
    ``r_gram_dev``, and the scale-free residuals ``residual_grad``
    (``||K_q Z||``), ``residual_eps_mu`` (``||(M_eps - M_mu) Z||``) and
    ``residual_pencil`` (``||(A - k0^2 B) Z||``), each normalised by the
    correspondingly scaled norms so that ``0`` means "exactly in the null space".

    The Amendment 3 diagnostics are ``column_region`` (which set the columns
    are: ``"v1"`` or ``"v1+homogeneous-blocks"``), ``columns_v1``,
    ``columns_added``, ``z_dim_v2`` (the widened total, whether or not it was
    used), ``region_contrast`` and ``region_rows`` (the contrast values added
    and the ``y``-grid levels they occupy), and ``z_dim_closed_form_v2``
    (``(nx - 1) (ny - 2)`` on the ladder, else ``None``).  ``z_dim`` and
    ``z_dim_closed_form`` keep their v1 meanings on both routes.

    **Limit.**  Building ``R`` densely costs about ``24 n^2`` bytes, so this
    route is capped at ``_DEFLATED_DENSE_MAX = 6000`` free DOFs and raises
    :class:`NotImplementedError` above it.  That cap is reported, not worked
    around: a sparse or matrix-free complement is a change of method and
    belongs in a dated amendment of the preregistration.
    """
    k0 = float(k0)
    sigma = float(sigma)
    if not np.isfinite(k0) or k0 <= 0.0:
        raise ValueError(f"k0 must be positive and finite, got {k0!r}")
    if not np.isfinite(sigma):
        raise ValueError(f"sigma must be finite, got {sigma!r}")

    eps_t = _per_triangle(eps_r, mesh, "eps_r")
    mu_t = _per_triangle(mu_r, mesh, "mu_r")
    if np.any(mu_t == 0.0):
        raise ValueError("mu_r must be non-zero on every triangle")

    k_q, m_mu, m_eps = assemble(mesh, eps_r=eps_t, mu_r=mu_t)
    mask = pec_edge_mask(mesh, boundaries)
    free = np.flatnonzero(~mask)
    n_dof = int(free.size)
    if n_dof < 3:
        raise ValueError(f"only {n_dof} free edge DOFs after the PEC cut")

    c = (k0 * k0 * m_eps - k_q).tocsr()
    b = m_mu.tocsr()
    c_free = c[free][:, free]
    b_free = b[free][:, free]

    cols, column_info = _deflation_columns(
        mesh,
        eps_t,
        mu_t,
        pec_node_mask(mesh, boundaries),
        widen=region_widen,
    )
    z = _incidence(mesh, free, cols)
    r_basis, info = _complement_basis(b_free, z)
    n_columns = int(r_basis.shape[1])
    if n_columns < 1:
        raise ValueError(
            f"the gradient subspace has dimension {info['z_dim']} of {n_dof} "
            "free DOFs; nothing is left to solve for"
        )

    n_k = min(int(k), n_dof - 1)
    if n_k < 1:
        raise ValueError(f"cannot ask for {k} modes with {n_dof} DOFs")
    if n_k > n_columns - 1:
        raise ValueError(
            f"cannot ask for {n_k} modes: the deflated basis has only "
            f"{n_columns} columns"
        )

    a_c = r_basis.T @ (c_free @ r_basis)
    b_c = r_basis.T @ (b_free @ r_basis)
    a_c = csr_matrix(0.5 * (a_c + a_c.T))
    b_c = csr_matrix(0.5 * (b_c + b_c.T))
    vals, y = eigsh(a_c, k=n_k, M=b_c, sigma=sigma, which="LM")
    vals = np.asarray(vals, dtype=float)
    vecs = r_basis @ y

    kq_f = k_q[free][:, free]
    me_f = m_eps[free][:, free]
    mm_f = m_mu[free][:, free]
    z_norm = _frob_norm(z)
    on_region = np.abs(eps_t - 1.0 / mu_t) <= 0.0  # same as _gradient_columns' default
    info["z_dim_closed_form"] = _closed_form_dim(mesh, on_region)
    column_mask = np.zeros(mesh.n_nodes, dtype=bool)
    column_mask[cols] = True
    info["column_region"] = column_info["column_region"]
    info["columns_v1"] = column_info["columns_v1"]
    info["columns_added"] = column_info["columns_added"]
    info["z_dim_v2"] = column_info["z_dim_v2"]
    info["region_contrast"] = column_info["region_contrast"]
    info["region_rows"] = column_info["region_rows"]
    info["z_dim_closed_form_v2"] = _closed_form_dim_v2(mesh, column_mask)
    info["n_dof"] = n_dof
    info["n_columns"] = n_columns
    info["residual_grad"] = _ratio(_frob_norm(kq_f @ z), _frob_norm(kq_f) * z_norm)
    info["residual_eps_mu"] = _ratio(
        _frob_norm((me_f - mm_f) @ z),
        (_frob_norm(me_f) + _frob_norm(mm_f)) * z_norm,
    )
    info["residual_pencil"] = _ratio(
        _frob_norm(c_free @ z - k0 * k0 * (b_free @ z)),
        (_frob_norm(c_free) + k0 * k0 * _frob_norm(b_free)) * z_norm,
    )

    return _select_and_pack(
        mesh=mesh,
        k0=k0,
        sigma=sigma,
        k_q=k_q,
        c_free=c_free,
        b_free=b_free,
        free=free,
        mask=mask,
        n_dof=n_dof,
        n_k=n_k,
        vals=vals,
        vecs=vecs,
        eps_max=float(np.max(eps_t)),
        guard=guard,
        extra={"deflation": info},
    )


def solve_modes_deflated_v2(
    mesh: Mesh2D,
    k0: float,
    sigma: float,
    *,
    eps_r=1.0,
    mu_r=1.0,
    boundaries=(),
    k: int = 4,
    guard: bool = True,
) -> Mode2D:
    """The Amendment 3 (5.b) widened deflation route.

    Exactly :func:`solve_modes_deflated` with ``region_widen = True``: the
    deflated subspace is the preregistered ``eps_r == 1 / mu_r`` block *plus*
    every other homogeneous contrast block of the mesh
    (:func:`_deflation_columns`).  On the pre-registered ladder that is
    ``14, 90, 434`` columns at levels 1-3, against ``11, 69, 329`` for the
    preregistered route -- the widened ladder closed form ``(nx - 1) (ny - 2)``,
    reported as ``deflation["z_dim_closed_form_v2"]``.

    The pencil, the normalisation, the selection rule, the ``R`` construction and
    the dense cap are those of :func:`solve_modes_deflated`, and the diagnostics
    are the same dict plus the widening keys, so a v1 result and a v2 result are
    comparable field by field.
    """
    return solve_modes_deflated(
        mesh,
        k0,
        sigma,
        eps_r=eps_r,
        mu_r=mu_r,
        boundaries=boundaries,
        k=k,
        region_widen=True,
        guard=guard,
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
    guard: bool = True,
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
    guard:
        Mode-eligibility guard, as for :func:`solve_modes`: reject candidates
        with ``|curl_ratio| < 1e-6`` or ``eps_eff >= max(eps_r) - 1e-6`` before
        taking the largest positive ``beta^2``; ``guard=False`` disables it.

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

    eps_max = float(np.max(_per_triangle(eps_r, mesh, "eps_r")))
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
    if guard:
        chosen = _guarded_choice(
            eligible=eligible,
            beta_sq=beta_sq,
            eps_eff=beta_sq / (k0 * k0),
            curl=ratios,
            eps_max=eps_max,
            where="the mixed (e_t, e_z) pencil",
        )
    else:
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


# ----------------------------------------------------------------------
# power-voltage impedance of a solved cross-section mode
# ----------------------------------------------------------------------
def mode_z0_from_power(
    mesh: Mesh2D,
    k0: float,
    sigma: float = 1.0,
    *,
    eps_r=1.0,
    mu_r=1.0,
    boundaries=(),
    k: int = 8,
    dense: bool | None = None,
    guard: bool = True,
) -> tuple:
    r"""``Z0 = V**2 / (2 P)`` of the mode :func:`solve_modes_mixed` selects [ohm].

    The same inputs (and therefore the same mode) as :func:`solve_modes_mixed`;
    nothing here changes that solve, it only adds the two integrals the
    impedance needs.

    Definitions -- exactly what is integrated
    -----------------------------------------
    ``V`` (volts, peak phasor)
        the line integral ``int E . dl`` along the **shortest edge chain** of
        the mesh between the two conductor groups, oriented from
        ``boundaries[0]``'s group **to** ``boundaries[1]``'s group (for the
        microstrip predicates that is *ground -> strip*, i.e. straight up the
        substrate).  The groups are the two connected node masks
        :func:`_dirichlet_groups` splits the PEC union into.  Each edge
        contributes its own DOF ``e_t[e] = int_e E . t_hat dl`` with the sign
        taken from the traversal direction, so the chain telescopes and ``V``
        is a pure sum of solver unknowns -- no interpolation, no normalisation
        of the eigenvector beyond the unit ``|x|`` the solve returns (it
        cancels in ``V**2 / P``).
    ``P`` (watts, **time-averaged** for a peak amplitude of 1)
        ``P = 0.5 * int_Omega (1/eta) |E_t|**2 dA`` over the whole
        cross-section ``Omega``, ``eta = eta0 / sqrt(eps_r)`` locally.  It is
        assembled with the *same* Whitney mass matrix the pencil uses,
        ``int sqrt(eps_r) W_e . W_f dA`` (``assemble_mixed`` with
        ``eps_r -> sqrt(eps_r)``), so the discrete field energy being
        integrated is the one the eigenvector actually represents.  The
        ``0.5`` is the phasor convention: ``P = 0.5 Re int (E x conj(H)) . z``
        for peak amplitudes, i.e. ``V`` is a peak voltage and ``P`` its
        time-averaged power -- hence ``Z0 = V**2 / (2P)`` and not ``V**2/P``.

    Modelling assumptions (a reviewer may reject any of these)
    ----------------------------------------------------------
    * ``H_t = z_hat x E_t / eta`` -- the **local TEM (quasi-TEM)** relation
      between the transverse fields.  The solve returns ``e_t`` and ``e_z``
      only, **no ``h_t``**, so ``P`` cannot be a Poynting integral of two
      independently solved fields; this is the modelling choice, stated
      rather than buried.
    * the longitudinal field ``e_z`` is omitted from ``P`` (its contribution
      is the ``E_z H_y`` cross term, second order in the quasi-TEM regime).
    * the eigenvector normalisation is arbitrary, so only the **ratio**
      ``V**2/P`` is meaningful; it is invariant to rescaling ``e_t``.
    * ``eps_r`` is treated as real and piecewise constant per triangle
      (lossless; no dispersion), exactly as in the solve.

    Returns
    -------
    ``(z0, beta, eps_eff, converged)``: the impedance [ohm], the propagation
    constant [rad/m], ``beta**2 / k0**2``, and whether the numbers may be
    trusted (finite positive ``z0``, positive ``beta``, and the block residual
    of the solve below :data:`_MIXED_RESIDUAL_TOL`).  ``converged=False``
    comes with the numbers still returned, for inspection, never raised away.
    """
    mode = solve_modes_mixed(
        mesh, k0, sigma=sigma, eps_r=eps_r, mu_r=mu_r,
        boundaries=boundaries, k=k, dense=dense, guard=guard,
    )

    # --- two conductor groups: A = boundaries[0]'s group, B = the other ------
    nodes_a, nodes_b = _dirichlet_groups(mesh, boundaries)

    # --- V: shortest edge chain, A -> B, then sum the (signed) edge DOFs ----
    edges = mesh.edges
    n_node = int(mesh.n_nodes)
    src = np.concatenate([edges[:, 0], edges[:, 1]])
    dst = np.concatenate([edges[:, 1], edges[:, 0]])
    eid = np.concatenate([np.arange(edges.shape[0], dtype=int)] * 2)
    order = np.argsort(src, kind="stable")
    src, dst, eid = src[order], dst[order], eid[order]
    ptr = np.searchsorted(src, np.arange(n_node + 1))

    start = int(np.flatnonzero(nodes_a)[0])
    prev = np.full(n_node, -1, dtype=int)        # predecessor node
    via = np.full(n_node, -1, dtype=int)         # edge used to reach it
    seen = np.zeros(n_node, dtype=bool)
    seen[start] = True
    queue = [start]
    qi = 0
    found = -1
    while qi < len(queue) and found < 0:
        u = queue[qi]
        qi += 1
        for kk in range(int(ptr[u]), int(ptr[u + 1])):
            w = int(dst[kk])
            if seen[w]:
                continue
            seen[w] = True
            prev[w] = u
            via[w] = int(eid[kk])
            if nodes_b[w]:
                found = w
                break
            queue.append(w)
    if found < 0:
        raise ValueError(
            "no edge chain connects the two conductor groups; the PEC "
            "predicates must touch the same triangulation"
        )

    v = 0.0 + 0.0j
    cur = found
    while cur != start:
        u = int(prev[cur])
        e = int(via[cur])
        # e_t[e] is int E.t_hat dl along edges[e,0] -> edges[e,1]: take it as is
        # when the chain runs that way (u == edges[e, 0]), negate otherwise.
        step = mode.e_t[e] if edges[e, 0] == u else -mode.e_t[e]
        v += step
        cur = u

    # --- P: 0.5 * int (1/eta)|E_t|^2 dA, eta0 = mu0 c0 ----------------------
    eta0 = 376.73031366804177                    # vacuum wave impedance [ohm]
    eps_tri = _per_triangle(eps_r, mesh, "eps_r")
    _m1, m_sqrt_eps, _c, _kzz, _mzz = assemble_mixed(
        mesh, eps_r=np.sqrt(eps_tri), mu_r=mu_r
    )
    x = np.asarray(mode.e_t)
    p_avg = 0.5 * float(np.real(x @ (m_sqrt_eps @ x))) / eta0

    converged = bool(
        np.isfinite(p_avg) and p_avg > 0.0 and mode.beta > 0.0
        and np.isfinite(mode.residual) and mode.residual < _MIXED_RESIDUAL_TOL
    )
    if not (np.isfinite(p_avg) and p_avg > 0.0):
        return float("nan"), float(mode.beta), float(mode.eps_eff), False

    z0 = float(abs(v) ** 2 / (2.0 * p_avg))
    return z0, float(mode.beta), float(mode.eps_eff), converged

