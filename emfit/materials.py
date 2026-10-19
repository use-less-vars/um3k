"""Material (Hodge star) matrices of the FIT discretisation.

Grid equations (Weiland's FIT, on the complex in :mod:`emfit.operators`)::

    Faraday:   C  e = -d/dt b ,      b = M_mu  h
    Ampere:    C~ h =  d/dt d + j ,  d = M_eps e ,      C~ = C.T

with ``e`` the primal edge voltages [V] and ``h`` the *dual* edge magnetic
voltages [A].  Both unknowns are line integrals on the dual pair of edges, so
the Hodge stars are plain diagonal scalings -- there is no matrix to invert:

    m_eps[e] = eps_r(e) * EPS0 * A~_e / L_e     [F]   (units of capacitance)
    m_mu[f]  = mu_r(f)  * MU0  * A_f  / L~_f    [H]   (units of inductance)

``L_e``   primal edge length; ``A~_e`` the DUAL face area perpendicular to it.
``A_f``   primal face area;   ``L~_f`` the DUAL edge length normal to that face.

Consequences of this normalisation (all energies in joules, all powers in W):

    U_e = 1/2 e . (m_eps e)        electrostatic energy
    U_m = 1/2 h . (m_mu  h)        magnetostatic energy
    P   = e . j                    power delivered by the soft current ``j``

Indexing
--------
``m_eps`` is indexed exactly like the primal edges, i.e. like the *columns* of
``C``: the three x/y/z edge blocks of :class:`~emfit.operators.CellComplex`
concatenated in that order (length ``C.shape[1]``).  ``m_mu`` is indexed like
the primal faces, i.e. like the *rows* of ``C`` (length ``C.shape[0]``).

Parameters
----------
``eps_r`` / ``mu_r`` may be a float (uniform), a numpy array matching the
relevant count (``n_edges`` for ``eps_r``, ``n_faces`` for ``mu_r``), or a
callable ``f(x, y, z)`` evaluated at the centre of each edge / face.  A
callable must be vectorised: it receives three coordinate arrays.

Sampling a callable, and material interfaces
--------------------------------------------
The coordinates a callable is evaluated at are built from the grid's node
arrays truncated to :meth:`emfit.grid.Grid.nodes`, so the seam node of a
*periodic* axis -- the first node over again, not a separate entity of the
complex -- is never sampled.  A callable and an explicit per-edge array
therefore describe the same field on periodic and bounded axes alike.

``interface`` decides what happens where an edge or face lies *in* a material
interface.  ``"point"`` evaluates the callable at the entity
centre only; on a node-aligned interface that centre sits exactly *on* the
surface, so the value is whatever the callable's own comparison returns and
one of the two sides is silently picked.  That is deterministic but it is not
the energy-consistent Hodge entry, and the misassigned entities stay on the
interface as the mesh is refined, so the error does not converge away.
``"dual"`` (the default) instead averages over the *dual* entity of the same
edge or face -- the dual face crossed by an edge, the dual edge crossed by a
face -- weighting each part by its own extent, which is the amount of material
the permittivity actually occupies there.  On a node-aligned interface that is
the arithmetic mean of the two sides on a uniform grid and the width weighted
mean on a non-uniform one; for a smoothly varying callable it is a midpoint
rule over the dual entity, exact for a linear profile on a uniform grid.
"""

from __future__ import annotations

import numpy as np

from .grid import Grid
from .operators import CellComplex

__all__ = ["EPS0", "MU0", "C0", "ETA0", "material_matrices",
           "MaterialMatrix", "Material", "M_eps", "M_mu", "M_sigma"]

#: vacuum permittivity [F/m]
EPS0 = 8.854187817e-12
#: vacuum permeability [H/m]
MU0 = 1.2566370614e-6
#: speed of light in vacuum [m/s]
C0 = 299792458.0
#: vacuum wave impedance [ohm]
ETA0 = MU0 * C0


# ----------------------------------------------------------------------
# geometry helpers (private; Grid exposes no coordinate helper)
# ----------------------------------------------------------------------
def _interval_centres(a):
    """Centres of the intervals between consecutive nodes."""
    return 0.5 * (a[1:] + a[:-1])


def _centres(grid: Grid, axis: str, along_mid: bool):
    """Coordinates of every edge (``along_mid``) or face centre of ``axis``.

    For an edge parallel to ``axis`` the coordinate along ``axis`` is the cell
    centre and the two transverse coordinates are node values; for a face
    normal to ``axis`` it is the other way round.  Node values are truncated to
    :meth:`emfit.grid.Grid.nodes`: on a periodic axis the last node is the
    first one again and is not part of the complex, so the full node array
    carries one entry too many there.
    """
    target = grid.edge_shape(axis) if along_mid else grid.face_shape(axis)
    a = "xyz".index(axis)
    out = []
    for t, name in enumerate("xyz"):
        v = getattr(grid, name)
        if (t == a) == along_mid:
            v = _interval_centres(v)          # cell centres: one per cell
        else:
            v = v[:grid.nodes(name)]          # node values: seam node dropped
        shp = [1, 1, 1]
        shp[t] = v.size
        out.append(np.broadcast_to(v.reshape(shp), target))
    return out


def _node_halves(grid: Grid, axis: str):
    """Extent of the two cells that meet at every node of ``axis``.

    The dual entity centred on a node is cut *by that node* into half of each
    adjacent cell, so the two parts have extent ``w[j-1] / 2`` and
    ``w[j] / 2``.  The returns here are the un-halved widths, i.e. the weights:
    their sum is the full dual width ``2 * dual_widths(axis)[j]``.  A bounded
    axis terminates at its outer nodes (the outside part is zero), a periodic
    one wraps.
    """
    w = np.asarray(grid.widths(axis), dtype=float)
    if grid.is_periodic(axis):
        return np.roll(w, 1), w.copy()
    return np.concatenate(([0.0], w)), np.concatenate((w, [0.0]))


def _dual_samples(grid: Grid, axis: str, along_mid: bool):
    """Midpoints of the parts of every edge's / face's *dual* entity.

    An edge is crossed by a dual *face* (an area) and a face by a dual *edge*
    (a line).  Both are centred on the primal entity, and the primal nodes cut
    them into ``2**k`` parts, ``k`` being the number of directions
    perpendicular to the primal entity: two for an edge, one for a face.

    Returns a list of ``(coords, weight)`` pairs -- the three coordinate arrays
    of the part midpoints and the part's share of the dual entity, the weights
    summing to one.  Averaging with them is the ``interface="dual"`` rule of
    :func:`material_matrices`.
    """
    target = grid.edge_shape(axis) if along_mid else grid.face_shape(axis)
    a = "xyz".index(axis)
    base = _centres(grid, axis, along_mid)          # the primal midpoint
    averaged = [t for t in range(3) if t != a] if along_mid else [a]

    halves = {}
    for t in averaged:
        lo, hi = _node_halves(grid, "xyz"[t])
        shp = [1, 1, 1]
        shp[t] = lo.size
        halves[t] = (np.broadcast_to(lo.reshape(shp), target),
                     np.broadcast_to(hi.reshape(shp), target))

    out = []
    for mask in range(2 ** len(averaged)):
        upper = [bool((mask >> i) & 1) for i in range(len(averaged))]
        coords = list(base)
        weight = np.ones(target, dtype=float)
        for t, up in zip(averaged, upper):
            lo, hi = halves[t]
            side, other = (hi, lo) if up else (lo, hi)
            # ``side`` is a whole cell width and the part keeps HALF of it, so
            # its midpoint sits side/4 from the primal entity -- sampling at
            # side/2 would land on the neighbouring cell centre instead.
            coords[t] = base[t] + (0.25 if up else -0.25) * side
            weight = weight * (side / (side + other))
        out.append((tuple(coords), weight))
    return out


def _check_interface(interface):
    """Reject an unknown dual-entity sampling rule."""
    if interface not in ("point", "dual"):
        raise ValueError(
            f"interface must be 'point' or 'dual', got {interface!r}"
        )


def _sampled(func, grid: Grid, axis: str, along_mid: bool, interface: str,
             count: int, name: str) -> np.ndarray:
    """Evaluate the callable ``func`` on every edge (``along_mid``) / face."""
    if interface == "point":
        val = np.asarray(func(*_centres(grid, axis, along_mid)),
                         dtype=float).ravel()
    else:                                    # "dual", validated by the caller
        target = grid.edge_shape(axis) if along_mid else grid.face_shape(axis)
        total = np.zeros(target, dtype=float)
        for coords, weight in _dual_samples(grid, axis, along_mid):
            val = np.asarray(func(*coords), dtype=float)
            if val.ndim == 0:
                return np.full(count, float(val))
            if val.shape != target:
                if val.size != count:
                    raise ValueError(
                        f"{name} callable returned shape {val.shape}, "
                        f"expected {target}"
                    )
                val = val.reshape(target)
            total = total + weight * val
        val = total.ravel()
    if val.size == 1:
        return np.full(count, float(val[0]))
    if val.size != count:
        raise ValueError(
            f"{name} callable returned {val.size} values, expected {count}"
        )
    return val


def _edge_blocks(cc: CellComplex):
    return (("x", cc.off_ex, cc.n_ex),
            ("y", cc.off_ey, cc.n_ey),
            ("z", cc.off_ez, cc.n_ez))


def _face_blocks(cc: CellComplex):
    return (("x", cc.off_fx, cc.n_fx),
            ("y", cc.off_fy, cc.n_fy),
            ("z", cc.off_fz, cc.n_fz))


def _parameter(value, count: int, name: str) -> np.ndarray:
    """Expand a scalar to ``count`` values; pass an array of that length through."""
    a = np.asarray(value, dtype=float)
    if a.ndim == 0:
        return np.full(count, float(a))
    a = a.ravel()
    if a.size != count:
        raise ValueError(
            f"{name}: expected a scalar, a callable, or {count} values, got {a.size}"
        )
    return a


# ----------------------------------------------------------------------
# the material matrices
# ----------------------------------------------------------------------
def material_matrices(grid: Grid, cc: CellComplex, eps_r=1.0, mu_r=1.0,
                      *, interface="dual"):
    """Return ``(m_eps, m_mu)``, both 1-D float arrays (diagonal matrices).

    ``m_eps`` has length ``cc.n_edges`` (edge order = column order of ``C``),
    ``m_mu`` has length ``cc.n_faces`` (face order = row order of ``C``).

    ``interface`` selects how a callable ``eps_r`` / ``mu_r`` is sampled where
    an edge or face lies in a material interface: ``"point"`` at the entity
    centre itself, ``"dual"`` (the default) as the weighted average over the
    whole dual entity (see the module docstring).  Floats and arrays are
    unaffected.
    """
    _check_interface(interface)

    # --- permittivity, on primal edges, needs the DUAL perpendicular area ---
    if not callable(eps_r):
        eps_all = _parameter(eps_r, cc.n_edges, "eps_r")
    m_eps = np.empty(cc.n_edges, dtype=float)
    for axis, off, n in _edge_blocks(cc):
        L_e = np.asarray(grid.edge_length(axis), dtype=float).ravel()
        A_dual = np.asarray(
            getattr(grid, f"dual_face_area_{axis}")(), dtype=float
        ).ravel()
        if callable(eps_r):
            val = _sampled(eps_r, grid, axis, True, interface, n, "eps_r")
        else:
            val = eps_all[off:off + n]
        m_eps[off:off + n] = val * EPS0 * (A_dual / L_e)

    # --- permeability, on primal faces, needs the DUAL perpendicular length --
    if not callable(mu_r):
        mu_all = _parameter(mu_r, cc.n_faces, "mu_r")
    m_mu = np.empty(cc.n_faces, dtype=float)
    for axis, off, n in _face_blocks(cc):
        A_f = np.asarray(getattr(grid, f"face_area_{axis}")(), dtype=float).ravel()
        w = grid.dual_widths(axis)
        shp = [1, 1, 1]
        shp["xyz".index(axis)] = w.size
        L_dual = np.broadcast_to(w.reshape(shp), grid.face_shape(axis)).ravel()
        if callable(mu_r):
            val = _sampled(mu_r, grid, axis, False, interface, n, "mu_r")
        else:
            val = mu_all[off:off + n]
        m_mu[off:off + n] = val * MU0 * (A_f / L_dual)

    return m_eps, m_mu


def _sigma_diag(grid: Grid, cc: CellComplex, sigma=0.0,
                *, interface="dual") -> np.ndarray:
    """Edge-wise conductance ``sigma * A~_e / L_e`` [S].

    ``interface`` is the sampling rule of :func:`material_matrices`, so a
    conductivity step on a node plane carries the same dual-face average as a
    permittivity step does.
    """
    _check_interface(interface)
    if not callable(sigma):
        sig_all = _parameter(sigma, cc.n_edges, "sigma")
    out = np.empty(cc.n_edges, dtype=float)
    for axis, off, n in _edge_blocks(cc):
        L_e = np.asarray(grid.edge_length(axis), dtype=float).ravel()
        A_dual = np.asarray(
            getattr(grid, f"dual_face_area_{axis}")(), dtype=float
        ).ravel()
        if callable(sigma):
            val = _sampled(sigma, grid, axis, True, interface, n, "sigma")
        else:
            val = sig_all[off:off + n]
        out[off:off + n] = val * (A_dual / L_e)
    return out


# ----------------------------------------------------------------------
# thin object wrappers (convenience only; the arrays above are canonical)
# ----------------------------------------------------------------------
class MaterialMatrix:
    """A diagonal material matrix: holds the diagonal and its reciprocal."""

    def __init__(self, diag, name: str = "M"):
        self.diag = np.asarray(diag, dtype=float).ravel()
        self.name = name
        self._inv = None

    @property
    def shape(self):
        return (self.diag.size, self.diag.size)

    def __len__(self):
        return self.diag.size

    @property
    def inv_diag(self) -> np.ndarray:
        if self._inv is None:
            self._inv = 1.0 / self.diag
        return self._inv

    def apply(self, x):
        """``M @ x``."""
        return self.diag * x

    def solve(self, x):
        """``M^-1 @ x``."""
        return self.inv_diag * x

    def __matmul__(self, x):
        return self.apply(x)

    def __repr__(self):  # pragma: no cover - cosmetic
        return f"MaterialMatrix({self.name}, n={self.diag.size})"


def M_eps(grid: Grid, cc: CellComplex | None = None, eps_r=1.0,
          *, interface="dual") -> MaterialMatrix:
    """``M_eps`` as a :class:`MaterialMatrix`."""
    cc = cc if cc is not None else CellComplex(grid)
    return MaterialMatrix(
        material_matrices(grid, cc, eps_r=eps_r, interface=interface)[0], "M_eps"
    )


def M_mu(grid: Grid, cc: CellComplex | None = None, mu_r=1.0,
         *, interface="dual") -> MaterialMatrix:
    """``M_mu`` as a :class:`MaterialMatrix`."""
    cc = cc if cc is not None else CellComplex(grid)
    return MaterialMatrix(
        material_matrices(grid, cc, mu_r=mu_r, interface=interface)[1], "M_mu"
    )


def M_sigma(grid: Grid, cc: CellComplex | None = None, sigma=0.0,
            *, interface="dual") -> MaterialMatrix:
    """``M_sigma`` as a :class:`MaterialMatrix` (units of siemens)."""
    cc = cc if cc is not None else CellComplex(grid)
    return MaterialMatrix(_sigma_diag(grid, cc, sigma, interface=interface),
                          "M_sigma")


class Material:
    """Homogeneous material description (scalars only).

    Per-cell parameter arrays are handled by the :func:`material_matrices`
    arguments directly; this class is a convenience for the common case.
    """

    def __init__(self, eps_r: float = 1.0, mu_r: float = 1.0, sigma: float = 0.0):
        self.eps_r = float(eps_r)
        self.mu_r = float(mu_r)
        self.sigma = float(sigma)

    @classmethod
    def uniform(cls, eps_r: float = 1.0, mu_r: float = 1.0, sigma: float = 0.0):
        """Homogeneous material."""
        return cls(eps_r, mu_r, sigma)

    def check(self, grid: Grid) -> "Material":
        """No-op validation hook (kept so callers can chain); returns ``self``."""
        return self

    def __repr__(self):  # pragma: no cover - cosmetic
        return (f"Material(eps_r={self.eps_r}, mu_r={self.mu_r}, "
                f"sigma={self.sigma})")
