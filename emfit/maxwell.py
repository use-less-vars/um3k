"""Assembly of the FIT Maxwell system.

Faraday and Ampere in discrete FIT form, with ``h`` the dual edge magnetic
voltage [A] and ``e`` the primal edge voltage [V]::

    C e            = -d/dt (M_mu h)
    C^T h          =  d/dt (M_eps e) + j

PEC walls are imposed as a *constraint*: the tangential electric edge voltages
are identically zero, so those edges simply never participate.  Splitting
``e = (e_free, 0)`` keeps the algebra exact (a zero column contributes nothing
to ``C e``) and preserves the discrete energy invariant bit-for-bit, whereas
"update then overwrite with zero" would silently leak the discarded work.
"""

from __future__ import annotations

import numpy as np

from .grid import Grid
from .materials import C0, M_eps, M_mu, M_sigma, Material
from .operators import CellComplex

__all__ = ["FITSystem", "ALL_WALLS"]

#: the six walls of a shoebox domain
ALL_WALLS = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


class FITSystem:
    """Discrete Maxwell system: operators + material matrices + boundary mask.

    Attributes
    ----------
    grid, cc : Grid, CellComplex
    material : Material
    M_eps, M_mu, M_sigma : MaterialMatrix
        Diagonal material matrices (see :mod:`emfit.materials`).
    C : csr_matrix, C_tilde : csc_matrix (zero-copy view sharing C.data)
        Primal curl ``(n_faces, n_edges)`` and its dual ``C.T``.
    pec : ndarray of bool, shape ``(n_edges,)``
        ``True`` where the edge voltage is pinned to zero by a PEC wall.
    free : ndarray of bool
        Complement of ``pec``; only these edge voltages are unknowns.
    dt : float
        Time step actually used by default (``safety * cfl_dt()``).
    """

    def __init__(self, grid: Grid, material: Material | None = None,
                 cc: CellComplex | None = None, walls=ALL_WALLS,
                 dt: float | None = None, safety: float = 0.95):
        self.grid = grid
        self.cc = cc if cc is not None else CellComplex(grid)
        self.material = (material if material is not None
                         else Material.uniform()).check(grid)

        self.M_eps = M_eps(grid, self.cc, self.material.eps_r)
        self.M_mu = M_mu(grid, self.cc, self.material.mu_r)
        self.M_sigma = M_sigma(grid, self.cc, self.material.sigma)

        self.C = self.cc.curl()
        self.C_tilde = self.cc.curl_dual()

        self.pec = self.cc.pec_edge_mask(walls)
        self.free = ~self.pec

        self.safety = float(safety)
        self.dt = float(dt) if dt is not None else self.safety * self.cfl_dt()

    # ------------------------------------------------------------------
    @property
    def n_edges(self) -> int:
        return self.cc.n_edges

    @property
    def n_faces(self) -> int:
        return self.cc.n_faces

    def cfl_dt(self, safety: float = 1.0) -> float:
        """Largest stable step for the 3-D Yee/FIT stability limit.

        ``dt <= 1 / (c sqrt(1/dx^2 + 1/dy^2 + 1/dz^2))`` with the *finest*
        cell width on each axis (a bounding-box bound for non-uniform grids).
        """
        inv = sum(1.0 / float(np.min(self.grid.widths(ax))) ** 2 for ax in "xyz")
        return float(safety) / (C0 * np.sqrt(inv))

    def check_dt(self, dt: float) -> float:
        """Return ``dt`` if it is stable, raise :class:`ValueError` otherwise."""
        limit = self.cfl_dt()
        dt = float(dt)
        if dt <= 0.0:
            raise ValueError(f"dt must be positive, got {dt!r}")
        if dt > limit:
            raise ValueError(
                f"dt = {dt:.6g} s exceeds the CFL limit {limit:.6g} s "
                f"for this grid (refine the grid or reduce dt)"
            )
        return dt

    def __repr__(self):  # pragma: no cover - cosmetic
        return (f"FITSystem(cells={self.grid.shape}, edges={self.n_edges}, "
                f"free={int(self.free.sum())}, dt={self.dt:.4g} s)")
