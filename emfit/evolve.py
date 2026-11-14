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

import os
import site
import sysconfig
from pathlib import Path

import numpy as np

from .materials import C0

__all__ = ["ricker", "cfl_dt", "step_explicit", "FITStepper", "RickerSource",
           "PointSource", "Leapfrog"]


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


def cfl_dt(grid, *, c: float = C0, safety: float = 0.99) -> float:
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
def step_explicit(e, h, C, C_tilde, inv_m_mu, inv_m_eps, dt, loss_num=None,
                  loss_den=None, pml=None, pec_idx=None, j=None):
    """One leapfrog update on bare arrays; mutates ``e`` and ``h`` in place.

    This is the whole time-stepping kernel of :class:`FITStepper.step` written
    as a free function over plain arrays, so that it can be ported to a
    compiled kernel without dragging the stepper object along.  It is the
    *only* implementation: ``FITStepper.step`` calls straight through to it.

    The update, in this exact order::

        h -= dt * inv_m_mu * (C e)                 Faraday
        [pml.damp_h(h, dt)]
        ce = C_tilde h [- j]
        e += dt * inv_m_eps * ce                   lossless Ampere
          or  e = (e loss_num + ce) loss_den       lossy Ampere
        [pml.damp_e(e, dt)]
        e[pec_idx] = 0

    ``C`` and ``C_tilde`` are ``scipy.sparse`` matrices of shape
    ``(n_faces, n_edges)`` and ``(n_edges, n_faces)`` respectively; the
    remaining vectors are 1-D ``float64`` arrays.  ``loss_num`` /
    ``loss_den`` are ``None`` for the lossless scheme, ``pml`` and ``pec_idx``
    are ``None`` when absent.

    Returns
    -------
    (e, h) : tuple of ndarray
        The same objects that were passed in (they are mutated, not copied).
    """
    h -= dt * (inv_m_mu * (C @ e))
    if pml is not None:
        pml.damp_h(h, dt)
    ce = C_tilde @ h
    if j is not None:
        ce = ce - j
    if loss_den is None:
        e += dt * (inv_m_eps * ce)
    else:
        # e = (e*loss_num + ce) * loss_den, done in place.  Elementwise
        # bit-identical to the single expression and keeps array identity.
        e *= loss_num
        e += ce
        e *= loss_den
    if pml is not None:
        pml.damp_e(e, dt)
    if pec_idx is not None:
        e[pec_idx] = 0.0
    return e, h


# ----------------------------------------------------------------------
# Optional compiled kernel
# ----------------------------------------------------------------------
# ``emfit_core`` is the C++ twin of ``step_explicit`` built from ``src/``.  It is
# OPTIONAL: without it (no pybind11, no build) the pure-Python function above is
# the whole implementation and everything still runs.  With it -- and only when
# it reports the ABI this module was written against -- ``FITStepper.step``
# dispatches to it.  The two produce the same bytes (verified in
# tests/test_cpp_parity.py against frozen goldens, and through this dispatcher in
# tests/test_cpp_dispatch.py), so which path ran is a performance fact, not a
# correctness one.
#
# The reference ``step_explicit`` stays unconditionally available and unchanged.
# It is what the kernel is validated against, so it must never grow a fast path
# of its own.
_KERNEL_ABI = 2                      # must equal emfit_core.KERNEL_ABI (src/bindings.cpp)
_KERNEL_NAME = "emfit_core.fit_leapfrog"


_FORCE_PYTHON_ENV = "EMFIT_FORCE_PYTHON"
"""Set to ``1``/``true``/``yes`` to choose the Python reference deliberately."""

_FORCE_PYTHON_TRUE = frozenset({"1", "true", "yes"})


def _python_forced():
    """True if this process was asked, explicitly, to skip the kernel."""
    value = os.environ.get(_FORCE_PYTHON_ENV, "")
    return str(value).strip().lower() in _FORCE_PYTHON_TRUE


def _extension_search_dirs():
    """Directories a built ``emfit_core`` extension could plausibly sit in.

    Nothing is hardcoded to one machine: the repository root comes from this
    file's own location, the interpreter's directories from ``sysconfig`` and
    ``site``, and any ``.venv*`` beside the sources from the filesystem.  Used
    only on :func:`_load_kernel`'s error path, where the question is "is there
    a build here that THIS interpreter failed to import?"
    """
    repo = Path(__file__).resolve().parent.parent
    dirs = [repo / "build", repo / "src"]
    try:
        for venv in sorted(repo.glob(".venv*")):
            if venv.is_dir():
                dirs.extend(sorted(venv.glob("lib/python*/site-packages")))
                dirs.append(venv / "Lib" / "site-packages")
    except OSError:
        pass
    try:
        paths = sysconfig.get_paths()
    except Exception:
        paths = {}
    for key in ("purelib", "platlib"):
        path = paths.get(key)
        if path:
            dirs.append(Path(path))
    try:
        dirs.extend(Path(p) for p in site.getsitepackages())
    except Exception:
        pass
    return dirs


def _probe_kernel_files():
    """Paths of ``emfit_core`` extension files this machine actually has.

    Sorted, deduplicated, ``.so`` and ``.pyd``.  A directory that cannot be
    listed is skipped rather than fatal: this exists to make an error message
    name a file, not to guard anything.
    """
    found = set()
    for directory in _extension_search_dirs():
        for pattern in ("emfit_core*.so", "emfit_core*.pyd"):
            try:
                found.update(str(p) for p in directory.rglob(pattern))
            except OSError:
                continue
    return sorted(found)


def _import_kernel():
    """Import and return ``emfit_core`` -- a function so a test can replace it."""
    import emfit_core

    return emfit_core


def _load_kernel(abi=_KERNEL_ABI):
    """The compiled ``step_explicit``, or ``None`` if there is none usable.

    ``None`` means Python does the arithmetic, and there are exactly three
    honest reasons for it: no extension is importable anywhere (nothing built,
    or this interpreter cannot see the build), the extension reports another
    ABI (that is a rebuild, not a fault), or this process was asked for the
    reference on purpose -- ``EMFIT_FORCE_PYTHON=1``, ``--force-python``, or
    :func:`force_python`.  A caller that wants to know which path a stepper
    chose should read ``FITStepper.kernel`` or :func:`engine_report`.

    What is not silent any more: an extension file that is ON DISK and fails to
    import.  That is not a missing option, it is a broken build or an
    interpreter that cannot reach site-packages, and returning ``None`` for it
    let a process record ``step_engine='python'`` while a perfectly good ``.so``
    sat beside it -- provenance that is wrong rather than absent.  So it raises
    ``RuntimeError`` naming every candidate file found, the original exception,
    and both ways out.  Running the Python path stays supported; it stops being
    something that can happen by accident.  The same loudness covers the thread
    team (DR-42): a kernel that claims ABI 2 and cannot be pinned to one thread
    raises rather than handing back a figure whose thread count is unknown.
    """
    if _python_forced():
        return None
    try:
        kernel = _import_kernel()
    except Exception as exc:
        candidates = _probe_kernel_files()
        if not candidates:
            return None
        listed = "\n".join(f"    {path}" for path in candidates)
        raise RuntimeError(
            "emfit_core exists on disk but could not be imported, so this "
            "process would have run the Python reference and recorded "
            "step_engine='python' with a compiled kernel sitting beside it.\n"
            f"  extension file(s) found:\n{listed}\n"
            f"  import failed with {type(exc).__name__}: {exc}\n"
            "  either put the venv site-packages on PYTHONPATH "
            "(e.g. PYTHONPATH=.venv/lib/python3.12/site-packages) so this "
            "interpreter can import the build, or rebuild it; or\n"
            "  pass --force-python / set EMFIT_FORCE_PYTHON=1 to run the "
            "Python reference deliberately."
        ) from exc
    if not callable(getattr(kernel, "step_explicit", None)):
        return None
    if abi is not None and getattr(kernel, "KERNEL_ABI", None) != abi:
        return None
    # ABI 2 pins the kernel's thread team, and a kernel announcing ABI 2 must be
    # able to.  DR-42: the same call costs 3.71 us on one thread and 291 us on
    # the team an inherited OMP_NUM_THREADS asks for, so a figure taken from a
    # kernel nobody pinned is a measurement of the environment, not the kernel.
    setter = getattr(kernel, "set_num_threads", None)
    if not callable(setter):
        raise RuntimeError(
            "emfit_core reports ABI 2 but has no set_num_threads(), so its "
            "thread team cannot be pinned and any timing taken from it would "
            "measure the ambient OMP_NUM_THREADS rather than the kernel "
            "(DR-42).\n"
            f"  kernel file: {getattr(kernel, '__file__', 'unknown')}\n"
            "  rebuild the extension from src/ (BUILD_COMMANDS in "
            "tests/test_cpp_parity.py): ABI 2 exports get_num_threads and "
            "set_num_threads."
        )
    try:
        setter(1)
    except Exception as exc:
        raise RuntimeError(
            "emfit_core has set_num_threads() but pinning its thread team to 1 "
            "failed, so this process cannot state the thread count its kernel "
            "figure was taken at (DR-42).\n"
            f"  kernel file: {getattr(kernel, '__file__', 'unknown')}\n"
            f"  set_num_threads(1) raised {type(exc).__name__}: {exc}"
        ) from exc
    return kernel


def force_python():
    """Run the Python reference in this process, on purpose.  Returns the kernel it dropped.

    Sets ``EMFIT_FORCE_PYTHON`` in the environment -- which is what a later
    :func:`_load_kernel` call, and every child process, reads -- and withdraws
    the kernel this module may already hold.  Withdrawal is the part that
    matters for a tool that imports ``emfit.evolve`` before it parses its own
    command line (``tools/host_ladder.py`` does): a module already imported
    cannot be un-imported, but the dispatch decision is a module global, and
    ``_ACTIVE_STEP`` is updated with it because the artefact writers read
    exactly that.  ``engine_report()`` needs no update: it reads ``_KERNEL``.
    """
    global _KERNEL, _ACTIVE_STEP
    previous = _KERNEL
    os.environ[_FORCE_PYTHON_ENV] = "1"
    _KERNEL = None
    _ACTIVE_STEP = "python"
    return previous


_KERNEL = _load_kernel()
_ACTIVE_STEP = "cpp" if _KERNEL is not None else "python"


def engine_report():
    """Which step engine *this process* is running, for artefact provenance.

    Returns ``{"step_engine": "cpp" | "python", "kernel_abi": int | None,
    "kernel_name": str | None}`` -- the identity of the arithmetic that produced
    a number, so a banked artefact says which path generated it rather than
    leaving a reader to infer it from the machine it was graded on.

    The module globals are re-read on every call (never captured in a default
    argument), so a test that swaps ``_KERNEL`` gets the swapped answer, and a
    process that fails to load the kernel reports ``"python"`` even though a
    ``.so`` exists on disk.  ``kernel_abi``/``kernel_name`` are ``None`` on the
    Python path: there is no ABI to name.
    """
    kernel = _KERNEL
    if kernel is None:
        return {"step_engine": "python", "kernel_abi": None, "kernel_name": None}
    abi = getattr(kernel, "KERNEL_ABI", _KERNEL_ABI)
    return {
        "step_engine": "cpp",
        "kernel_abi": int(abi) if abi is not None else None,
        "kernel_name": _KERNEL_NAME,
    }


def _can_damp_in_kernel(pml):
    """True if ``pml`` can be expressed as the kernel's two multiplier vectors.

    ``PML.damp_e`` / ``damp_h`` are exactly ``field *= multipliers(dt)[i]`` and
    nothing else (emfit/pml.py), so the kernel reproduces them bit for bit --
    UNLESS the layer carries an absorbed-work audit, whose ``record()`` needs the
    pre-damp field from outside and cannot be reconstructed from the two
    multipliers alone.  Such a layer forces the Python path.
    """
    if pml is None:
        return True
    if getattr(pml, "_audit", None) is not None:
        return False
    return callable(getattr(pml, "multipliers", None))


def _csr_arrays(A):
    """``(data, indices, indptr)`` of a scipy sparse matrix, in the kernel's types.

    float64 data and int64 index arrays, each C-contiguous: the binding is strict
    and a 32-bit scipy index would be rejected by name rather than silently
    widened.  ``A`` is copied to CSR if it is not already (the dual curl is a CSC
    view of ``C.T``, emfit/operators.py), so this is where that copy is paid --
    once, when the plan is built, never per step.
    """
    A = A.tocsr()
    return (np.ascontiguousarray(A.data, dtype=np.float64),
            np.ascontiguousarray(A.indices, dtype=np.int64),
            np.ascontiguousarray(A.indptr, dtype=np.int64))


class _KernelPlan:
    """Per-system bundles of the kernel's arguments, built once.

    Holds the operator arrays, the material diagonals and the PEC index set in
    exactly the dtypes and shapes the binding declares, so :meth:`step` does no
    conversion per call -- only the two PML multipliers, which the layer already
    caches per ``dt``.  ``e`` and ``h`` are mutated in place; their identity is
    the stepper's.
    """

    __slots__ = ("kernel", "C", "C_tilde", "C_shape", "C_tilde_shape",
                 "inv_m_mu", "inv_m_eps", "pec_idx", "loss_num", "loss_den",
                 "pml")

    def __init__(self, kernel, C, C_tilde, inv_m_mu, inv_m_eps, loss_num,
                 loss_den, pec_idx, pml):
        self.kernel = kernel
        self.C_shape = tuple(int(v) for v in C.shape)
        self.C_tilde_shape = tuple(int(v) for v in C_tilde.shape)
        self.C = _csr_arrays(C)
        self.C_tilde = _csr_arrays(C_tilde)
        self.inv_m_mu = np.ascontiguousarray(inv_m_mu, dtype=np.float64)
        self.inv_m_eps = np.ascontiguousarray(inv_m_eps, dtype=np.float64)
        self.pec_idx = (None if pec_idx is None
                        else np.ascontiguousarray(pec_idx, dtype=np.int64))
        self.loss_num = loss_num
        self.loss_den = loss_den
        self.pml = pml

    def step(self, e, h, dt, j=None):
        """One compiled leapfrog step, in place on ``e``/``h``.

        Mirrors :func:`step_explicit` argument for argument.  ``j`` is coerced
        to a contiguous float64 array if it is anything else -- the kernel only
        reads it, so a value-preserving copy keeps the step bit-identical while
        sparing every call site the strict-dtype requirement.
        """
        if self.pml is not None:
            damp_e, damp_h = self.pml.multipliers(dt)
        else:
            damp_e = damp_h = None
        if j is not None:
            j = np.ascontiguousarray(j, dtype=np.float64)
        C_data, C_indices, C_indptr = self.C
        Ct_data, Ct_indices, Ct_indptr = self.C_tilde
        self.kernel.step_explicit(
            e, h,
            C_data, C_indices, C_indptr, self.C_shape,
            Ct_data, Ct_indices, Ct_indptr, self.C_tilde_shape,
            self.inv_m_mu, self.inv_m_eps, float(dt),
            self.loss_num, self.loss_den, damp_e, damp_h, self.pec_idx, j)


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

        # Select the compiled twin when it is importable, ABI-compatible, and can
        # express this step's PML (no absorbed-work audit).  Otherwise stay on the
        # Python reference.  The two are bit-identical, so ``self.kernel`` is a
        # performance detail, not a correctness switch -- ``None`` here means
        # "Python did the arithmetic", by choice or by absence.
        if _KERNEL is not None and _can_damp_in_kernel(pml):
            self.kernel = _KernelPlan(
                _KERNEL, self.C, self.C_tilde, self.inv_m_mu, self.inv_m_eps,
                self.loss_num, self.loss_den, self.pec_idx, pml)
        else:
            self.kernel = None

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

        The numerical work is delegated to the module-level kernel
        :func:`step_explicit`, which is the function a compiled (C++) update
        is expected to reproduce bit for bit.  When a compiled kernel is
        available (see :data:`_ACTIVE_STEP`) the same update runs there instead;
        it mutates ``self.e`` / ``self.h`` in place, leaving their objects (and
        their identity) unchanged.
        """
        if self.kernel is not None:
            self.kernel.step(self.e, self.h, self.dt, j)
        else:
            e, h = step_explicit(self.e, self.h, self.C, self.C_tilde,
                                self.inv_m_mu, self.inv_m_eps, self.dt,
                                self.loss_num, self.loss_den, self.pml,
                                self.pec_idx, j)
            self.e = e
            self.h = h
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
class PointSource:
    """Soft-current drive on ONE primal edge: a point source at ``(i, j, k)``.

    ``__call__(t)`` returns the length-``n_edges`` current vector that
    :meth:`FITStepper.run` expects, carrying a ramped cosine on the single
    edge ``cc.idx_<component>(i, j, k)`` and zero on every other edge::

        j[index] = amplitude * ramp(t) * cos(omega t + phase)

    with ``omega = 2 pi frequency`` and the raised-cosine switch-on::

        ramp(t) = 0.5 (1 - cos(pi t / t_ramp))   for t <  t_ramp
                  1.0                            for t >= t_ramp

    The ramp is not cosmetic.  A sinusoid switched on at full amplitude
    injects a step whose spectrum decays only as ``1/f``, which contaminates
    every frequency the run is later analysed at; ``t_ramp`` defaults to four
    periods.

    The drive enters where :func:`step_explicit` documents it, through the
    ``j`` slot of Ampere's law (``ce = ce - j``), so it is a *soft* current:
    it adds to the field instead of overwriting it, and a PEC edge would
    still be zeroed afterwards.

    Parameters
    ----------
    cc : CellComplex
        Supplies the edge numbering and the grid, hence the default ``dt``.
    i, j, k : int
        Cell index of the driven edge.  Wrapping is whatever ``cc.idx_*``
        does (``%`` per axis, a no-op on a bounded axis).
    component : {'ex', 'ey', 'ez'}, optional
        Which edge block the point sits in; ``'ez'`` by default.
    frequency : float
        Drive frequency in Hz.  Must be finite and positive.
    amplitude : float, optional
        A *normalised drive knob*, NOT a current density in A/m^2.
    dt : float, optional
        Time step used only to size :attr:`steps_per_period` and
        :attr:`ramp_steps`.  Defaults to :func:`cfl_dt`, the same default
        :class:`FITStepper` takes, so the two agree with nothing passed.  A
        time step above the CFL limit is refused here rather than left to
        diverge.
    t_ramp : float, optional
        Switch-on duration in seconds; defaults to ``4 / frequency``.
    phase : float, optional
        Phase offset in radians, added inside the cosine.

    Notes
    -----
    ``amplitude`` is deliberately dimensionless: this class attaches NO
    radiated power and NO dipole moment to it.  Turning a drive amplitude
    into a physical moment -- and hence into a power -- depends on the grid
    and on the whole experiment, so it is the caller's job, not the source's.

    The array returned by ``__call__`` is the *same object* on every call,
    re-zeroed first, exactly as :class:`RickerSource` does.  Do not keep the
    return value across steps; copy it if you need a history.
    """

    _COMPONENTS = ("ex", "ey", "ez")

    def __init__(self, cc, i: int, j: int, k: int, *, component: str = "ez",
                 frequency: float, amplitude: float = 1.0,
                 dt: float | None = None, t_ramp: float | None = None,
                 phase: float = 0.0) -> None:
        if component not in self._COMPONENTS:
            raise ValueError(
                f"component={component!r}: must be one of {self._COMPONENTS}")
        frequency = float(frequency)
        if not np.isfinite(frequency) or frequency <= 0.0:
            raise ValueError(
                f"frequency={frequency!r}: must be finite and positive")
        amplitude = float(amplitude)
        if not np.isfinite(amplitude):
            raise ValueError(f"amplitude={amplitude!r}: must be finite")

        dt_max = cfl_dt(cc.grid)
        if dt is None:
            dt = dt_max
        else:
            dt = float(dt)
            if not np.isfinite(dt) or dt <= 0.0:
                raise ValueError(f"dt={dt!r}: must be finite and positive")
            if dt > dt_max * (1.0 + 1e-9):
                raise ValueError(
                    f"dt={dt!r} s exceeds the Courant limit {dt_max!r} s of "
                    f"this grid: the leapfrog scheme is unstable above it")

        # The current vector has to span EVERY primal edge, because ``step``
        # subtracts it from the whole curl vector.  ``cc.n_edges`` is that
        # total (n_ex + n_ey + n_ez); summing the blocks is the same number
        # spelled out, for a cell complex that predates the total.
        n_edges = getattr(cc, "n_edges", None)
        if n_edges is None:
            n_edges = cc.n_ex + cc.n_ey + cc.n_ez

        self.cc = cc
        self.component = component
        self.i, self.j, self.k = int(i), int(j), int(k)
        self._index = int(getattr(cc, "idx_" + component)(self.i, self.j, self.k))
        self.frequency = frequency
        self.amplitude = amplitude
        self.dt = float(dt)
        self.omega = 2.0 * np.pi * frequency
        self.t_ramp = float(4.0 / frequency if t_ramp is None else t_ramp)
        self.phase = float(phase)
        self.n_edges = int(n_edges)
        self._j = np.zeros(self.n_edges, dtype=float)

    @property
    def index(self):
        """Flat index of the driven edge in the global edge vector."""
        return self._index

    @property
    def steps_per_period(self):
        """``int(round(1 / (frequency * dt)))``, driver steps per period."""
        return int(round(1.0 / (self.frequency * self.dt)))

    @property
    def ramp_steps(self):
        """``int(round(t_ramp / dt))``, driver steps spent ramping up."""
        return int(round(self.t_ramp / self.dt))

    def __call__(self, t):
        """Return the full current vector at ``t`` (the same buffer each call)."""
        j = self._j
        j[:] = 0.0
        t = float(t)
        if t < self.t_ramp:
            ramp = 0.5 * (1.0 - np.cos(np.pi * t / self.t_ramp))
        else:
            ramp = 1.0
        j[self._index] = (self.amplitude * ramp
                          * np.cos(self.omega * t + self.phase))
        return j

    def __repr__(self):  # pragma: no cover - cosmetic
        return (f"PointSource(component={self.component!r}, "
                f"ijk=({self.i}, {self.j}, {self.k}), index={self._index}, "
                f"frequency={self.frequency:g}, amplitude={self.amplitude:g})")


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
