"""Explicit leapfrog time stepping and source waveforms.

Grid equations (see :mod:`emfit.materials`)::

    C e = -d/dt (m_mu h)                      Faraday
    C~ h =  d/dt (m_eps e) + m_sigma e + j ,  Ampere,  C~ = C.T

``m_sigma`` is the diagonal of the conductance star: one non-negative entry
per primal edge, in siemens.  It represents distributed material conductivity
and, *equally*, a lumped circuit load -- a load is nothing but a conductance
between two edges, so the stepper never has to learn what a board is.

Staggered (Yee) leapfrog::

    h^{n+1/2} = h^{n-1/2} - dt * (1/m_mu) * (C e^n)
    e^{n+1}   = [ (m_eps/dt - m_sigma/2) e^n + (C~ h^{n+1/2} - j) ]
                / (m_eps/dt + m_sigma/2)
    e^{n+1}[PEC] = 0

i.e. the Ampere law is discretised by the trapezoidal (Crank-Nicolson) rule
in time, elementwise.  That is the difference between a scheme that is stable
for any load and one that is not: the per-edge amplification factor is
``(1 - a/2) / (1 + a/2)`` with ``a = dt m_sigma / m_eps``, whose magnitude is
strictly below one for every ``m_sigma >= 0``, whereas an explicit
``-dt m_sigma e^n`` term would need ``a < 2``.  For practical loads ``a`` is
small anyway: a 50 ohm load spread over 8 parallel edges (``G = 2.5e-3`` S each)
on a mesh with ``dx = 0.4`` mm gives ``dt m_sigma / (2 m_eps) = 0.06`` on a
substrate edge (``m_eps = 1.558e-14`` F) and ``0.27`` on an air edge
(``m_eps = 3.542e-15`` F).  That pair assumes ``A~/L = dx`` for the mesh, which
holds when the transverse cell spacings equal ``dx``.  With ``m_sigma`` all zero
the update reduces to the lossless line above *bit for bit*.

At the mixed state ``(e^n, h^{n-1/2})`` and with ``m_sigma = 0`` the quantity

    U = 1/2 e.m_eps.e + 1/2 h.m_mu.h - (dt/2) (C e).h

is an *exact* algebraic invariant: the two O(dt) and the two O(dt^2) terms of
the change cancel pairwise.  The cross term is thus not an accuracy nicety --
without it U would only be conserved to O(dt).  With a nonzero ``m_sigma`` U is
no longer invariant (the loads drain energy) and it is mere bookkeeping.

All quantities are SI: ``e`` in V, ``h`` in A, ``j`` in A, ``m_sigma`` in S,
``U`` in J.
"""

from __future__ import annotations

import numpy as np

from .materials import C0

__all__ = ["ricker", "cfl_dt", "FITStepper", "RickerSource", "Leapfrog"]


# ----------------------------------------------------------------------
# waveforms and stability
# ----------------------------------------------------------------------
def ricker(t, t0, fmax):
    """Ricker (Mexican hat) wavelet, peak amplitude 1 at ``t = t0``.

    Spectrally centred on ``fmax``; the useful bandwidth is roughly
    ``[0, 2.5 fmax]``.
    """
    a = np.pi * fmax * (t - t0)
    return (1.0 - 2.0 * a * a) * np.exp(-a * a)


def cfl_dt(grid, c: float = C0, safety: float = 0.99) -> float:
    """Courant-limited time step ``safety / (c sqrt(sum_axis 1/d_axis^2))``.

    ``d_axis`` is the *smallest* cell width on that axis.  The leapfrog
    stability bound is set by the shortest edge in the mesh, so a graded grid
    must use the minimum width rather than the maximum.
    """
    inv_sq = 0.0
    for axis in "xyz":
        d = float(np.min(np.asarray(grid.widths(axis), dtype=float)))
        inv_sq += 1.0 / d ** 2
    return float(safety) / (c * np.sqrt(inv_sq))


# ----------------------------------------------------------------------
class FITStepper:
    """Leapfrog stepper for the FIT Maxwell system.

    Parameters
    ----------
    cc : CellComplex
        Provides ``C`` / ``C.T`` and the grid (used for the default ``dt``).
    m_eps, m_mu : array_like, shape (n_edges,) and (n_faces,)
        Diagonal material matrices from :func:`emfit.materials.material_matrices`.
    m_sigma : array_like, shape (n_edges,), optional
        Diagonal of the conductance star: a non-negative conductance [S] per
        primal edge.  Both material conductivity and a lumped load are just a
        conductance between two edges.  ``None`` or an all-zero vector leaves
        the lossless update untouched, bit for bit.
    dt : float, optional
        Time step; defaults to :func:`cfl_dt` of the grid.
    pec : array_like, optional
        Either a boolean mask of length ``n_edges`` or the index array of the
        PEC-constrained edges.  Their voltages are reset to zero after every
        update, so they are never unknowns.
    pml : emfit.pml.PML, optional
        Absorbing layer to apply inside :meth:`step` (at the two leapfrog
        points, see below).  Left as ``None`` the update is bit-identical to
        the one without a layer.

    Attributes
    ----------
    e : ndarray (n_edges,)
        Primal edge voltages [V], at time ``self.time``.
    h : ndarray (n_faces,)
        Dual edge magnetic voltages [A], at ``self.time - dt/2``.
    time : float
        Simulation time of the current ``e`` state [s].
    n : int
        Number of steps taken.
    pml : emfit.pml.PML or None
        The layer given to the constructor, if any.
    """

    def __init__(self, cc, m_eps, m_mu, dt: float | None = None, pec=None,
                 pml=None, m_sigma=None):
        self.cc = cc
        self.C = cc.curl()
        self.C_tilde = cc.curl_dual()
        self.m_eps = np.asarray(m_eps, dtype=float).ravel()
        self.m_mu = np.asarray(m_mu, dtype=float).ravel()
        if self.m_eps.size != self.C.shape[1]:
            raise ValueError(
                f"m_eps must have {self.C.shape[1]} entries (primal edges), "
                f"got {self.m_eps.size}")
        if self.m_mu.size != self.C.shape[0]:
            raise ValueError(
                f"m_mu must have {self.C.shape[0]} entries (primal faces), "
                f"got {self.m_mu.size}")
        self.inv_m_eps = 1.0 / self.m_eps
        self.inv_m_mu = 1.0 / self.m_mu

        self.dt = float(cfl_dt(cc.grid) if dt is None else dt)

        # Lossy Ampere law, trapezoidal in time (see the module docstring).
        self.m_sigma = None
        self.loss_num = None
        self.loss_den = None
        if m_sigma is not None:
            ms = np.asarray(m_sigma, dtype=float).ravel()
            if ms.size != self.C.shape[1]:
                raise ValueError(
                    f"m_sigma must have {self.C.shape[1]} entries (primal "
                    f"edges), got {ms.size}")
            if np.any(ms):
                self.m_sigma = ms
                rate = self.m_eps / self.dt
                half = 0.5 * ms
                self.loss_num = rate - half
                self.loss_den = 1.0 / (rate + half)

        self.pml = pml
        self.power_audit = getattr(pml, "_audit", None)
        if self.power_audit is not None:
            self.power_audit.bind_materials(self.m_eps, self.m_mu)
        self.pec_idx = self._index_array(pec, self.C.shape[1])
        if self.pec_idx is not None:
            self.free = np.ones(self.C.shape[1], dtype=bool)
            self.free[self.pec_idx] = False

        self.e = np.zeros(self.C.shape[1], dtype=np.float64)
        self.h = np.zeros(self.C.shape[0], dtype=np.float64)
        self.time = 0.0
        self.n = 0

    @staticmethod
    def _index_array(pec, n):
        if pec is None:
            return None
        a = np.asarray(pec)
        if a.dtype == bool:
            if a.size != n:
                raise ValueError(f"pec mask must have {n} entries, got {a.size}")
            return np.flatnonzero(a)
        a = a.ravel().astype(np.intp)
        return a

    # ------------------------------------------------------------------
    def step(self, j=None):
        """One leapfrog step; advances ``self.time`` by ``dt``.

        ``j`` is an optional current vector [A] on the primal edges.
        """
        self.h -= self.dt * (self.inv_m_mu * (self.C @ self.e))
        if self.pml is not None:
            self.pml.damp_h(self.h, self.dt)
        ce = self.C_tilde @ self.h
        if j is not None:
            ce = ce - j
        if self.loss_den is None:
            self.e += self.dt * (self.inv_m_eps * ce)
        else:
            self.e = (self.e * self.loss_num + ce) * self.loss_den
        if self.pml is not None:
            self.pml.damp_e(self.e, self.dt)
        if self.pec_idx is not None:
            self.e[self.pec_idx] = 0.0
        self.time += self.dt
        self.n += 1
        return self

    # ------------------------------------------------------------------
    def energy(self) -> float:
        """Exact mixed-state invariant ``U`` [J] (see the module docstring)."""
        # Winner (a): the -dt/2*(C e).h cross term at mixed state (e^n, h^{n-1/2}) is what makes U exact.
        Ce = self.C @ self.e
        return float(
            0.5 * float(self.e @ (self.m_eps * self.e))
            + 0.5 * float(self.h @ (self.m_mu * self.h))
            - 0.5 * self.dt * float(Ce @ self.h)
        )

    def energy_components(self) -> dict:
        """Break ``energy()`` into its three named terms."""
        Ce = self.C @ self.e
        electric = 0.5 * float(self.e @ (self.m_eps * self.e))
        magnetic = 0.5 * float(self.h @ (self.m_mu * self.h))
        correction = -0.5 * self.dt * float(Ce @ self.h)
        return {
            "electric": electric,
            "magnetic": magnetic,
            "correction": correction,
            "total": electric + magnetic + correction,
        }

    # ------------------------------------------------------------------
    def run(self, nsteps, probe=None, source=None, callback=None):
        """Take ``nsteps`` steps and optionally record a probe signal.

        Order within each iteration: ``j = source(self.time)`` (if given),
        :meth:`step`, then the probe sample, then ``callback(self)``.

        Parameters
        ----------
        probe : int or sequence of ints, optional
            Edge indices to record.  An int records ``e[i]``; a sequence
            records their sum; the returned array is time-ordered.
        source : callable, optional
            ``f(t) -> j`` returning the full current vector for time ``t``.
        callback : callable, optional
            ``f(stepper)`` invoked after each completed step.

        Returns
        -------
        ndarray or None
            The probe samples (empty array if ``probe`` is None -> ``None``).
        """
        samples = [] if probe is not None else None
        if probe is not None:
            idx = np.asarray(probe)
            scalar_probe = idx.ndim == 0
            idx = np.atleast_1d(idx).astype(np.intp)
        for _ in range(int(nsteps)):
            j = source(self.time) if callable(source) else None
            self.step(j)
            if samples is not None:
                v = self.e[idx]
                samples.append(float(v[0]) if scalar_probe else float(np.sum(v)))
            if callback is not None:
                callback(self)
        return None if samples is None else np.asarray(samples, dtype=float)


# ----------------------------------------------------------------------
class RickerSource:
    """Soft-current excitation on a chosen set of edges.

    ``__call__(t)`` returns a length-``n_edges`` current vector with
    ``j[idx] = amplitude * ricker(t, t0, fmax)`` and zero elsewhere.

    The amplitude is a *normalised tuning knob* for the soft source, not a
    physical current density in A/m^2: it fixes how hard the chosen edges are
    driven, and the resulting field amplitudes are whatever the FIT system
    produces.  ``t0`` defaults to ``1/fmax`` so the wavelet starts near zero.
    """

    def __init__(self, n_edges, idx, fmax, t0=None, amplitude=1.0):
        self.n_edges = int(n_edges)
        self.idx = np.atleast_1d(np.asarray(idx, dtype=np.intp))
        self.fmax = float(fmax)
        self.t0 = float(1.0 / fmax if t0 is None else t0)
        self.amplitude = float(amplitude)
        self._j = np.zeros(self.n_edges, dtype=float)

    def __call__(self, t):
        j = self._j
        j[:] = 0.0
        j[self.idx] = self.amplitude * ricker(t, self.t0, self.fmax)
        return j

    def __repr__(self):  # pragma: no cover - cosmetic
        return (f"RickerSource(n_edges={self.n_edges}, n_idx={self.idx.size}, "
                f"fmax={self.fmax:g}, t0={self.t0:g})")


# ----------------------------------------------------------------------
class Leapfrog(FITStepper):
    """Adapter for a pre-assembled :class:`emfit.maxwell.FITSystem`.

    Kept for call sites that build the material matrices via ``FITSystem``;
    it validates ``dt`` against the CFL limit (raising ``ValueError``) and
    accepts initial fields.
    """

    def __init__(self, system, e0=None, h0=None, dt: float | None = None):
        dt_used = system.check_dt(system.dt if dt is None else dt)
        super().__init__(system.cc, system.M_eps.diag, system.M_mu.diag,
                         dt=dt_used, pec=np.flatnonzero(system.pec),
                         m_sigma=system.M_sigma.diag)
        self.system = system
        self.j = np.zeros_like(self.e)
        if e0 is not None:
            self.e[:] = np.asarray(e0, dtype=float).ravel()
        if h0 is not None:
            self.h[:] = np.asarray(h0, dtype=float).ravel()
        self.e[self.pec_idx] = 0.0

    def step(self, j=None):
        return super().step(self.j if j is None else j)
