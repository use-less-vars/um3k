"""Resonance eigenproblem of the FIT discretisation.

Eliminating the magnetic field from the harmonic grid equations of
:mod:`emfit.evolve` (``d/dt -> i omega``, no current) gives

    C^T M_mu^-1 C e = omega^2 M_eps e ,

with ``C`` the primal curl (``n_faces x n_edges``) and ``M_mu`` / ``M_eps`` the
face / edge Hodge stars from :mod:`emfit.materials`.  Both sides are symmetric
and ``M_eps`` is positive definite, so the pencil is self-adjoint: real
``omega^2`` and ``M_eps``-orthogonal eigenvectors.  A PEC wall pins the
tangential edge voltage to zero, which enters as a *restriction of the unknown
space* to the free (non-PEC) edges.

Spurious gradient modes -- an honest statement
----------------------------------------------
``C G = 0`` holds exactly for the metric-free operators of
:mod:`emfit.operators`, so every gradient field ``G phi`` lies in the kernel of
the curl.  The ideal curl-curl eigenproblem on the PEC-backed primal edges
therefore carries a **gradient null space of dimension ``(nx-1)(ny-1)(nz-1)``**
(the potentials supported on interior nodes; 216 for a ``10x7x5`` grid, 702 for
``14x10x7``).  That null space is *not* removed by the free-edge restriction --
only the divergence-free constraint ``G^T M_eps e = 0`` removes it -- so the
restricted problem is genuinely singular and the lowest ``k`` eigenvalues of a
black-box eigensolver (ARPACK with shift-invert) are contaminated by or made
entirely of static modes.

What this module does about it
------------------------------
The null space is filtered *after* the solve.  Modes at ``omega^2 ~ 0`` are the
gradient modes and are dropped first (``n_rejected_static``); they are separated
from the physical spectrum by ~13 orders of magnitude (``|omega^2| < 1e-13
(pi C0/L)^2`` versus the fundamental at ``3 (pi C0/L)^2``), so this cut is
unambiguous.  The survivours are then screened by the divergence residual
``res = ||Gf^T (m_eps e)|| / ||m_eps e||`` (``n_rejected_nonphysical``).  Note
what is *not* true: for the ideal problem ``G^T A e = (C G)^T M_mu^-1 C e = 0``
would give ``G^T M_eps e = 0`` exactly, but ``C G = 0`` holds only on the full
edge set -- on the free subset ``C_f G_f != 0``, so a genuine restricted
eigenvector is only *approximately* divergence-free.  Measured on a ``10x7x5``
box: gradients give ``res = 2.44-2.48``, physical modes ``0.45-0.78``.  The test
is therefore a threshold between two well separated clusters, not a 1e-6
identity.  The solve itself is
a **dense** ``scipy.linalg.eigh`` on the free-edge pencil, which is exact and
costs 0.1 s on the validation grids; ``n_free > max_dense`` raises
``NotImplementedError`` instead of silently returning a polluted spectrum.

Roadmap: an iterative (ARPACK) path for large grids needs the gradient null
space deflated with the ``M_eps``-orthogonal projector
``P = Gf (Gf^T M_eps Gf)^-1 Gf^T M_eps`` (see ``docs/roadmap.md`` M5); a plain
shift-invert or a shift-escalation heuristic does *not* work here (both were
tried: a shift at ``omega^2 = 0`` returns only static modes, a shift above the
fundamental returns a window that skips the fundamental).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp

from .materials import C0

__all__ = ["ResonanceResult", "resonances", "analytic_box_modes"]


def _free_mask(cc, pec) -> np.ndarray:
    """Boolean mask of the free (non-PEC) edges; ``True`` = unknown."""
    n = int(cc.n_edges)
    if pec is None:
        return ~np.asarray(cc.pec_edge_mask(), dtype=bool)
    a = np.asarray(pec)
    if a.dtype == bool:
        if a.size != n:
            raise ValueError(f"pec mask must have {n} entries, got {a.size}")
        return ~a
    mask = np.ones(n, dtype=bool)
    mask[a.ravel().astype(np.intp)] = False
    return mask


@dataclass
class ResonanceResult:
    """Free-edge eigenmodes, ascending in frequency.

    ``freqs`` [Hz] and ``omegas`` [rad/s] are the surviving eigenvalues;
    ``vectors`` is ``(n_edges, n_modes)`` with the columns in the same order and
    zero-padded at the PEC edges, so each column is a full edge-voltage vector.
    ``n_free`` is the size of the solved problem, ``n_edges`` the total.
    ``n_rejected_static`` counts the eigenvalues dropped at ``omega^2 ~ 0``,
    ``n_rejected_nonphysical`` those dropped by the ``G^T M_eps e = 0`` test.
    """

    freqs: np.ndarray
    omegas: np.ndarray
    vectors: np.ndarray
    n_free: int
    n_edges: int
    n_rejected_static: int = 0
    n_rejected_nonphysical: int = 0

    def report(self, top=None) -> str:
        """Fixed-width table of the lowest ``top`` frequencies in MHz."""
        n = self.freqs.size if top is None else min(int(top), self.freqs.size)
        lines = [
            f"FIT resonances: {n} of {self.freqs.size} modes, "
            f"n_free = {self.n_free} of {self.n_edges} edges "
            f"(rejected: {self.n_rejected_static} static, "
            f"{self.n_rejected_nonphysical} non-physical)",
            f"{'mode':>5}  {'f [MHz]':>12}  {'omega [rad/s]':>16}",
        ]
        for i in range(n):
            lines.append(
                f"{i:5d}  {self.freqs[i] / 1e6:12.4f}  {self.omegas[i]:16.8e}"
            )
        return "\n".join(lines)


def resonances(grid, cc, m_eps, m_mu, pec=None, k=6, sigma=0.0,
               max_dense=3000, res_tol=1.5) -> ResonanceResult:
    """Solve ``C^T M_mu^-1 C e = omega^2 M_eps e`` on the free edges.

    ``m_eps`` / ``m_mu`` are the diagonal material matrices from
    :func:`emfit.materials.material_matrices` (lengths ``n_edges`` /
    ``n_faces``); ``grid`` only carries the interface (the metric lives in the
    Hodge stars).  ``pec`` is a boolean mask (``True`` = PEC) or an index array
    of PEC edges and defaults to ``cc.pec_edge_mask()`` (all six walls).

    The pencil is solved **densely** (``scipy.linalg.eigh``) and the gradient
    null space is then filtered in two steps (see the module docstring):
    eigenvalues at ``omega^2 <= 1e-10 (pi C0/L)^2`` are the ``(nx-1)(ny-1)(nz-1)``
    static/gradient modes and are dropped, then the survivours are screened with
    the divergence residual ``res = ||Gf^T (m_eps e)|| / ||m_eps e||``, keeping
    ``res < res_tol``.  ``res_tol`` is **not** ``1e-6``: on the restricted
    problem ``Gf^T M_eps e`` is *not* exactly zero for a physical mode (the
    identity ``C G = 0`` only holds on the full edge set, not on the free
    subset), it is measured at 0.45-0.78 for the genuine modes and 2.44-2.48 for
    the gradients of a 10x7x5 grid, hence the cut between the two clusters.
    The returned modes may therefore be fewer than ``k`` on a very coarse grid.

    ``sigma`` is accepted for backwards compatibility and **ignored**: the dense
    path does not need a shift, and shifting a singular pencil was shown not to
    work (see the module docstring).  ``max_dense`` bounds the dense solve;
    above it a ``NotImplementedError`` points at the ARPACK deflation roadmap
    item rather than returning static modes as resonances.
    """
    C = cc.curl()
    m_eps = np.asarray(m_eps, dtype=float).ravel()
    m_mu = np.asarray(m_mu, dtype=float).ravel()
    if m_eps.size != C.shape[1]:
        raise ValueError(
            f"m_eps must have {C.shape[1]} entries (primal edges), "
            f"got {m_eps.size}")
    if m_mu.size != C.shape[0]:
        raise ValueError(
            f"m_mu must have {C.shape[0]} entries (primal faces), "
            f"got {m_mu.size}")

    if sigma:
        warnings.warn("resonances: sigma is ignored by the dense solver",
                      RuntimeWarning, stacklevel=2)

    free = _free_mask(cc, pec)
    n_free = int(free.sum())
    k = int(k)
    if k < 1:
        raise ValueError(f"k must be positive, got {k}")

    G = cc.gradient()
    Gf = G[free][:, :]                      # (n_free, n_nodes) sparse
    n_nodes = int(G.shape[1])
    if n_free > int(max_dense):
        raise NotImplementedError(
            f"n_free={n_free} exceeds the dense limit max_dense={int(max_dense)}; "
            f"ARPACK deflation of the gradient null space "
            f"(dim (nx-1)(ny-1)(nz-1) <= {n_nodes} nodes) is not implemented yet "
            f"- see docs/roadmap.md M5.  Use emfit.evolve + FFT for the spectrum "
            f"on large grids.")

    inv_m_mu = sp.spdiags(1.0 / m_mu, 0, C.shape[0], C.shape[0])
    a = (C.T @ inv_m_mu @ C).tocsr()
    a_free = np.asarray(a[free][:, free].todense(), dtype=float)
    b_free = np.diag(m_eps[free])

    extent = max(float(np.sum(grid.widths(ax))) for ax in ("x", "y", "z"))
    lam_ref = (np.pi * C0 / extent) ** 2

    # The lowest eigenvalues are the (up to n_nodes) gradient null modes, so the
    # requested band must reach past them before any physical mode appears.
    m = min(n_free, k + 64 + n_nodes)
    if m < n_free:
        vals, vecs = sla.eigh(a_free, b_free, subset_by_index=[0, m - 1])
    else:
        vals, vecs = sla.eigh(a_free, b_free)

    keep = vals > 1e-10 * lam_ref
    n_static = int((~keep).sum())
    vals, vecs = vals[keep], vecs[:, keep]

    # Dense in the M_eps inner product, so Gf^T (m_eps e) = 0 must hold for a
    # physical mode; the free-edge restriction breaks the identity, so it is
    # measured and compared against the separated clusters (see docstring).
    d = m_eps[free]
    res = np.empty(vals.size, dtype=float)
    for j in range(vals.size):
        u = d * vecs[:, j]
        res[j] = np.linalg.norm(Gf.T @ u) / np.linalg.norm(u)
    phys = res < float(res_tol)
    n_bad = int((~phys).sum())
    vals, vecs = vals[phys], vecs[:, phys]
    if vals.size > k:
        vals, vecs = vals[:k], vecs[:, :k]

    omegas = np.sqrt(np.clip(vals, 0.0, None))
    vectors = np.zeros((C.shape[1], omegas.size), dtype=float)
    vectors[free, :] = vecs

    return ResonanceResult(
        freqs=omegas / (2.0 * np.pi),
        omegas=omegas,
        vectors=vectors,
        n_free=n_free,
        n_edges=int(C.shape[1]),
        n_rejected_static=n_static,
        n_rejected_nonphysical=n_bad,
    )


def analytic_box_modes(a, b, d, count=10, m_max=5, n_max=5, p_max=5) -> np.ndarray:
    """Lowest resonant frequencies [Hz] of a rectangular PEC cavity.

    ``f_mnp = (C0/2) sqrt((m/a)^2 + (n/b)^2 + (p/d)^2)`` over
    ``0 <= m <= m_max``, ``0 <= n <= n_max``, ``0 <= p <= p_max``; sorted
    ascending and truncated to the lowest ``count`` values.

    Selection and degeneracy: a triple with a *single* non-zero index is not a
    Maxwell solution (TM needs ``m, n >= 1``; TE needs ``p >= 1`` together with
    ``m >= 1`` or ``n >= 1``), so such triples are dropped.  A triple with
    exactly two non-zero indices is a single mode -- ``(m, n, 0)`` is TM,
    ``(m, 0, p)`` and ``(0, n, p)`` are TE -- and is listed *once*; a triple with
    all three indices non-zero is TE/TM degenerate and is listed *twice*.  The
    returned array therefore deliberately contains duplicates, which lets it be
    compared one-to-one with a computed spectrum that resolves both
    polarisations as distinct eigenvectors.
    """
    a, b, d = float(a), float(b), float(d)
    if min(a, b, d) <= 0.0:
        raise ValueError("cavity dimensions must be positive")
    values = []
    for m in range(int(m_max) + 1):
        for n in range(int(n_max) + 1):
            for p in range(int(p_max) + 1):
                n_nonzero = int(m > 0) + int(n > 0) + int(p > 0)
                if n_nonzero < 2:
                    continue
                f = 0.5 * C0 * np.sqrt((m / a) ** 2 + (n / b) ** 2 + (p / d) ** 2)
                values.extend([f] * (2 if n_nonzero == 3 else 1))
    values.sort()
    return np.asarray(values[:int(count)], dtype=float)
