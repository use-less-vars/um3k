"""First-order Mur absorbing boundary conditions for the FIT leapfrog scheme.

The scheme
----------
On an outer boundary plane with outward unit normal ``n``, Mur's first-order
local condition for the tangential electric field is

    (d/dt + c d/dn) E_tan = 0

Discretised between the boundary layer (index 0, the plane of E-edges that
lies *on* the domain face) and the first interior layer (index 1, one cell
inward), with ``h`` the normal cell width, the explicit update of the
leapfrog scheme is

    E_tan^{n+1}(0) = E_tan^n(1)
                     + K * ( E_tan^{n+1}(1) - E_tan^n(0) ),

    K = (c*dt - h) / (c*dt + h).

``E_tan^{n+1}(1)`` and ``E_tan^n(1)`` are field values on the *parallel* edge
one cell inward (the Yee grid puts the two tangential components of the
boundary layer on the plane and their twins half a cell inside), while
``E_tan^n(0)`` is the value of the boundary edge itself *before* the step that
produced level ``n+1``.  The update therefore couples a boundary edge to the
parallel edge one cell inward -- not to anything on its own layer beyond the
two time levels of the left-hand/right-hand terms above.

Mind the time levels: **both** history terms sit at level ``n``, the field as
it was *before* the leapfrog step.  Reaching one level further back (``n-1``)
in either term is a natural-looking mistake and is quantitatively fatal -- on
a 2-D duct with 7.5 mm cells and a 2 GHz TE10 pulse it degrades the measured
reflection from ``-49.6 dB`` to ``-9.0 dB``, because the doubly retarded copy
no longer matches the discrete dispersion relation the one-way condition was
derived for.  The ``K -> 0`` limit is the quick sanity check: the update then
collapses to ``E_tan^{n+1}(0) = E_tan^n(1)``, the exact one-cell translation
of an outgoing wave in one step, which is only sharp when the history term is
the pre-step field.  (Both numbers above are measurement, not theory; the
continuum prediction for that duct is ``-49.2 dB``.)

Reference
---------
G. Mur, "Absorbing boundary conditions for the finite-difference approximation
of the time-domain electromagnetic-field equations", *IEEE Trans. Electromagn.
Compat.*, vol. EMC-23, no. 4, pp. 377-382, 1981.

Accuracy
--------
* First order accurate in the boundary discretisation (error ``O(h)`` in the
  reflection coefficient, i.e. the residual reflection scales like the cell
  size and like the angle away from normal incidence).
* *Exact* for one-dimensional propagation at normal incidence -- in 1-D the
  scheme above reproduces the outgoing solution of the 1-D wave equation with
  no residual at all (up to the numerical dispersion of the interior scheme,
  which is a property of the bulk stencil, not of the boundary).
* Imperfect at oblique incidence and for evanescent/surface content: the
  reflection grows with the angle of incidence and with the mismatch between
  the phase velocity of the discrete mode and the nominal ``c`` used here
  (a waveguide mode travelling faster than ``c`` is absorbed only to the
  extent that ``c`` approximates its phase velocity).
* It is a *local* condition: one cell of stencil, no auxiliary variables, no
  global solve, and it does not distinguish incoming from outgoing energy --
  it simply enforces the one-way relation.

Corner / edge handling
----------------------
An E-edge lying in the intersection of two (or three) outer planes -- e.g. an
``EX`` edge at ``y = 0, z = 0`` -- cannot satisfy both one-way conditions at
once, and applying the update twice would use two different formulas on the
same value.  The deliberate choice made here is: **each edge is updated by
exactly one plane, namely the first plane in the fixed priority order**

    xmin, xmax, ymin, ymax, zmin, zmax

that contains it (so priority decreases x > y > z, and min > max).  Rationale:
a single consistent one-way relation keeps the update well posed and cannot
double-count or feed one plane's boundary value into another plane's stencil;
corner/edge edges straddle a set of measure zero (their dual face area is a
quarter or an eighth of an interior one) and carry negligible energy in any
resolved field, so any fixed, deterministic priority gives the same overall
reflection to within the first-order error of the method itself.  The
priority is fixed internally by ``ALL_PLANES`` and does not depend on the
order of the ``planes`` argument.

Implementation layout
---------------------
``__init__`` precomputes, per plane, two integer index arrays into the global
edge vector: ``idx`` (the boundary-layer tangential edges) and ``nbr`` (their
parallel inward neighbours), plus the scalar normal step ``h`` and the
coefficient ``K``.  PEC edges are removed from ``idx`` at construction time so
they are never touched, and edges already claimed by an earlier plane are
removed as well.  :meth:`Mur1Boundary.apply` is then a handful of vectorised
gather/scatter operations per plane -- no Python loop over edges.

The class never reshapes or reorders the global vector: it works directly on
the flat layout produced by :class:`emfit.operators.CellComplex`.

Wiring into a time loop::

    stepper = FITStepper(cc, m_eps.diag, m_mu.diag,
                         pec=cc.pec_edge_mask(("ymin", "ymax", "zmin", "zmax")))
    mur = Mur1Boundary(grid, stepper.dt, cc=cc, pec=stepper.pec_idx)
    for n in range(nsteps):
        e_prev = stepper.e.copy()            # field at time n, BEFORE the step
        stepper.step(source(stepper.time))    # e -> time n+1, then PEC zeroed
        mur.apply(stepper.e, e_prev)          # overwrite boundary tangential E

Save the history *before* stepping (copy, step, apply).  Rolling the saved
copy at the *end* of the loop instead is the classic slip: the first
iteration then hands ``apply`` an all-zero field and every later one a field
one level too old, which silently costs about 40 dB of absorption.

``apply`` must be called *after* the leapfrog step (so that
``E_tan^{n+1}(1)`` exists) and *after* the PEC constraint has been enforced;
the PEC edges themselves are excluded from the update, so it cannot resurrect
a value that the constraint pinned to zero.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .materials import C0
from .operators import CellComplex

__all__ = ["ALL_PLANES", "Mur1Boundary"]

#: the six walls of a shoebox domain, in the fixed priority order used for
#: corner/edge edges (see the module docstring)
ALL_PLANES = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")


@dataclass(frozen=True)
class _Plane:
    """Precomputed index arrays and coefficient of one boundary plane."""

    name: str
    idx: np.ndarray
    nbr: np.ndarray
    h: float
    K: float

    @property
    def count(self):
        return int(self.idx.size)


class Mur1Boundary:
    """First-order Mur absorbing boundary on the outer planes of a grid.

    Parameters
    ----------
    grid : emfit.grid.Grid
        The grid the edge vector belongs to.
    dt : float
        Leapfrog time step [s].  It enters the coefficient
        ``K = (c*dt - h)/(c*dt + h)``; it must be the step actually used by the
        stepper.
    cc : emfit.operators.CellComplex, optional
        Cell complex of ``grid``; built on the fly if omitted.
    planes : sequence of str, optional
        Subset of ``("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")``, i.e.
        ``ALL_PLANES``.  Only the listed planes are made absorbing; the
        remaining outer planes keep whatever condition the caller imposed
        (typically PEC).
    pec : array_like, optional
        Either a boolean mask of length ``n_edges`` or the index array of the
        PEC-constrained edges -- the same convention as
        :class:`emfit.evolve.FITStepper`.  Tangential edges pinned by PEC are
        excluded from ``idx``, so they keep their zero value.
    c : float, optional
        Nominal wave speed used in ``K``; defaults to ``emfit.materials.C0``.
        A material with ``eps_r*mu_r != 1`` should pass
        ``C0/sqrt(eps_r*mu_r)``.

    Attributes
    ----------
    planes : list of _Plane
        The active planes, in priority order, with their precomputed index
        arrays (read-only use).
    e_prev : ndarray (n_edges,)
        Internal history buffer, used by :meth:`apply` when no explicit
        ``e_prev`` is given; fill it with :meth:`update_history`.
    """

    def __init__(self, grid, dt, cc=None, planes=ALL_PLANES, pec=None, c=C0):
        self.grid = grid
        self.cc = CellComplex(grid) if cc is None else cc
        self.dt = float(dt)
        if not np.isfinite(self.dt) or self.dt <= 0.0:
            raise ValueError(f"dt must be positive and finite, got {dt!r}")
        self.c = float(c)

        planes = tuple(planes)
        for name in planes:
            if name not in ALL_PLANES:
                raise ValueError(
                    f"unknown plane {name!r}; expected one of {ALL_PLANES}")

        pec_mask = self._pec_mask(pec, self.cc.n_edges)
        claimed = np.zeros(self.cc.n_edges, dtype=bool)

        self.planes = []
        for name in ALL_PLANES:            # fixed priority order
            if name not in planes:
                continue
            idx, nbr, h = self._plane_arrays(name)
            keep = ~pec_mask[idx]
            keep &= ~claimed[idx]          # corner/edge edges: first plane wins
            idx = idx[keep]
            nbr = nbr[keep]
            claimed[idx] = True
            cdt = self.c * self.dt
            self.planes.append(
                _Plane(name=name, idx=idx, nbr=nbr, h=h,
                       K=float((cdt - h) / (cdt + h))))

        self.e_prev = np.zeros(self.cc.n_edges, dtype=np.float64)

    # ------------------------------------------------------------------
    @staticmethod
    def _pec_mask(pec, n_edges):
        if pec is None:
            return np.zeros(int(n_edges), dtype=bool)
        a = np.asarray(pec)
        if a.dtype == bool:
            if a.size != n_edges:
                raise ValueError(
                    f"pec mask must have {n_edges} entries, got {a.size}")
            return a.copy()
        mask = np.zeros(int(n_edges), dtype=bool)
        mask[a.ravel().astype(np.intp)] = True
        return mask

    # ------------------------------------------------------------------
    def _plane_arrays(self, name):
        """``(idx, nbr, h)`` for one plane, via the CellComplex index helpers.

        ``idx`` are the tangential edges lying on the plane, ``nbr`` the
        parallel edges one cell inward, ``h`` the normal cell width between
        the two layers.
        """
        cc = self.cc
        nx, ny, nz = cc.nx, cc.ny, cc.nz
        if name in ("xmin", "xmax"):
            if nx < 2:
                raise ValueError(f"{name}: need at least 2 cells along x")
            i0, i1 = (0, 1) if name == "xmin" else (nx, nx - 1)
            J, K = np.indices((ny, nz + 1))          # EY edges (parallel to y)
            J2, K2 = np.indices((ny + 1, nz))        # EZ edges (parallel to z)
            idx = np.concatenate([cc.idx_ey(i0, J, K).ravel(),
                                  cc.idx_ez(i0, J2, K2).ravel()])
            nbr = np.concatenate([cc.idx_ey(i1, J, K).ravel(),
                                  cc.idx_ez(i1, J2, K2).ravel()])
            h = float(self.grid.widths("x")[0 if name == "xmin" else -1])
        elif name in ("ymin", "ymax"):
            if ny < 2:
                raise ValueError(f"{name}: need at least 2 cells along y")
            j0, j1 = (0, 1) if name == "ymin" else (ny, ny - 1)
            I, K = np.indices((nx, nz + 1))          # EX edges (parallel to x)
            I2, K2 = np.indices((nx + 1, nz))        # EZ edges (parallel to z)
            idx = np.concatenate([cc.idx_ex(I, j0, K).ravel(),
                                  cc.idx_ez(I2, j0, K2).ravel()])
            nbr = np.concatenate([cc.idx_ex(I, j1, K).ravel(),
                                  cc.idx_ez(I2, j1, K2).ravel()])
            h = float(self.grid.widths("y")[0 if name == "ymin" else -1])
        elif name in ("zmin", "zmax"):
            if nz < 2:
                raise ValueError(f"{name}: need at least 2 cells along z")
            k0, k1 = (0, 1) if name == "zmin" else (nz, nz - 1)
            I, J = np.indices((nx, ny + 1))          # EX edges (parallel to x)
            I2, J2 = np.indices((nx + 1, ny))        # EY edges (parallel to y)
            idx = np.concatenate([cc.idx_ex(I, J, k0).ravel(),
                                  cc.idx_ey(I2, J2, k0).ravel()])
            nbr = np.concatenate([cc.idx_ex(I, J, k1).ravel(),
                                  cc.idx_ey(I2, J2, k1).ravel()])
            h = float(self.grid.widths("z")[0 if name == "zmin" else -1])
        else:  # pragma: no cover - guarded by __init__
            raise ValueError(name)
        return idx.astype(np.intp), nbr.astype(np.intp), h

    # ------------------------------------------------------------------
    # history
    # ------------------------------------------------------------------
    def update_history(self, e):
        """Store ``e`` as the internal history for the *next* step.

        ``e`` must be the field at time level ``n``, sampled **before** the
        leapfrog step that advances it to ``n+1``::

            mur.update_history(stepper.e)     # e at time n
            stepper.step(source(stepper.time))
            mur.apply(stepper.e)              # uses the stored time-n field

        Storing an older level (or calling this after the step with a stale
        copy) is the one easy way to break this boundary.
        """
        self.e_prev[:] = np.asarray(e, dtype=float).ravel()
        return self

    def reset_history(self):
        """Zero the internal history buffer."""
        self.e_prev[:] = 0.0
        return self

    # ------------------------------------------------------------------
    # the boundary update
    # ------------------------------------------------------------------
    def apply(self, e_new, e_prev=None):
        """Overwrite the tangential E on every active plane, in place.

        Parameters
        ----------
        e_new : ndarray, shape (n_edges,)
            Post-step field, i.e. the time level ``n+1``; modified in place at
            the boundary-layer indices (and nowhere else).
        e_prev : ndarray, shape (n_edges,), optional
            Field at time level ``n`` -- the value of ``e`` *before* the step
            that produced ``e_new``.  It must carry the time-``n`` values at
            both ``p.idx`` and ``p.nbr``.  If omitted, the internal buffer
            ``self.e_prev`` is used (see :meth:`update_history`).  Passing the
            level ``n-1`` field is accepted silently but degrades the boundary
            badly (measured: -9.0 dB instead of -49.6 dB).

        Returns
        -------
        ndarray
            The same ``e_new`` object, for convenience.
        """
        prev = self.e_prev if e_prev is None else np.asarray(e_prev)
        for p in self.planes:
            e_new[p.idx] = (prev[p.nbr]
                            + p.K * (e_new[p.nbr] - prev[p.idx]))
        return e_new

    # ------------------------------------------------------------------
    def plane_summary(self):
        """``{plane: n_edges_updated}`` -- useful in tests and diagnostics."""
        return {p.name: p.count for p in self.planes}

    def __repr__(self):  # pragma: no cover - cosmetic
        counts = ", ".join(f"{k}={v}" for k, v in self.plane_summary().items())
        return (f"Mur1Boundary(planes=[{counts}], dt={self.dt:.4g} s, "
                f"c={self.c:.6g} m/s)")
