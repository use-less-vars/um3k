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
    normal to ``axis`` it is the other way round.
    """
    target = grid.edge_shape(axis) if along_mid else grid.face_shape(axis)
    a = "xyz".index(axis)
    out = []
    for t, name in enumerate("xyz"):
        v = getattr(grid, name)
        v = _interval_centres(v) if ((t == a) == along_mid) else v
        shp = [1, 1, 1]
        shp[t] = v.size
        out.append(np.broadcast_to(v.reshape(shp), target))
    return out


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
def material_matrices(grid: Grid, cc: CellComplex, eps_r=1.0, mu_r=1.0):
    """Return ``(m_eps, m_mu)``, both 1-D float arrays (diagonal matrices).

    ``m_eps`` has length ``cc.n_edges`` (edge order = column order of ``C``),
    ``m_mu`` has length ``cc.n_faces`` (face order = row order of ``C``).
    """
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
            val = np.asarray(eps_r(*_centres(grid, axis, along_mid=True)),
                             dtype=float).ravel()
            if val.size == 1:
                val = np.full(n, float(val[0]))
            if val.size != n:
                raise ValueError(f"eps_r callable returned {val.size} values, expected {n}")
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
            val = np.asarray(mu_r(*_centres(grid, axis, along_mid=False)),
                             dtype=float).ravel()
            if val.size == 1:
                val = np.full(n, float(val[0]))
            if val.size != n:
                raise ValueError(f"mu_r callable returned {val.size} values, expected {n}")
        else:
            val = mu_all[off:off + n]
        m_mu[off:off + n] = val * MU0 * (A_f / L_dual)

    return m_eps, m_mu


def _sigma_diag(grid: Grid, cc: CellComplex, sigma=0.0) -> np.ndarray:
    """Edge-wise conductance ``sigma * A~_e / L_e`` [S]."""
    sig = sigma if not callable(sigma) else None
    if not callable(sigma):
        sig_all = _parameter(sigma, cc.n_edges, "sigma")
    out = np.empty(cc.n_edges, dtype=float)
    for axis, off, n in _edge_blocks(cc):
        L_e = np.asarray(grid.edge_length(axis), dtype=float).ravel()
        A_dual = np.asarray(
            getattr(grid, f"dual_face_area_{axis}")(), dtype=float
        ).ravel()
        if callable(sigma):
            val = np.asarray(sigma(*_centres(grid, axis, along_mid=True)),
                             dtype=float).ravel()
            if val.size == 1:
                val = np.full(n, float(val[0]))
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


def M_eps(grid: Grid, cc: CellComplex | None = None, eps_r=1.0) -> MaterialMatrix:
    """``M_eps`` as a :class:`MaterialMatrix`."""
    cc = cc if cc is not None else CellComplex(grid)
    return MaterialMatrix(material_matrices(grid, cc, eps_r=eps_r)[0], "M_eps")


def M_mu(grid: Grid, cc: CellComplex | None = None, mu_r=1.0) -> MaterialMatrix:
    """``M_mu`` as a :class:`MaterialMatrix`."""
    cc = cc if cc is not None else CellComplex(grid)
    return MaterialMatrix(material_matrices(grid, cc, mu_r=mu_r)[1], "M_mu")


def M_sigma(grid: Grid, cc: CellComplex | None = None, sigma=0.0) -> MaterialMatrix:
    """``M_sigma`` as a :class:`MaterialMatrix` (units of siemens)."""
    cc = cc if cc is not None else CellComplex(grid)
    return MaterialMatrix(_sigma_diag(grid, cc, sigma), "M_sigma")


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
