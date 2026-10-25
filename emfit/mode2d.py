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
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import eigsh

from .grid import Grid
from .materials import C0

__all__ = [
    "Mesh2D",
    "Mode2D",
    "assemble",
    "k0_from_freq",
    "mesh_from_grid",
    "pec_edge_mask",
    "solve_modes",
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
