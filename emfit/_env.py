"""Process-level thread hygiene, applied once before numpy is imported.

Why this exists
---------------
Every linear algebra task in :mod:`emfit` is a *small dense pencil*: the
eigenproblem of :mod:`emfit.eigen` has at most a few thousand unknowns, the
material matrices are diagonal and the leapfrog update is a handful of sparse
matrix-vector products.  Multi-threaded BLAS buys nothing at that size -- the
matrices are too small for the worker threads to have any work to do -- but it
does cost a great deal: an OpenBLAS thread pool that spins waiting for its peers
burns CPU on a machine whose cgroup quota is smaller than the number of cores it
advertises.  Measured in the development container (12 cores advertised, about
one core of quota): the ``10 x 7 x 5`` cavity eigen-solve takes ~10.2 s with the
default thread count and ~0.27 s with a single thread -- a factor of ~40, spent
on spin-waiting rather than on arithmetic.

The fix has to happen *before* the BLAS library is loaded, because OpenBLAS and
friends read these environment variables once, at library load time (which
happens the first time numpy is imported).  Setting them from inside a running
program after ``import numpy`` has no effect whatsoever.  That is why
:func:`pin_threads` is called as the very first statement of
:mod:`emfit.__init__`, ahead of any submodule that pulls in numpy in.

Only unset variables are touched: a user who exported ``OMP_NUM_THREADS=8``
because a run of their own wants it keeps that value, and so does a site
administrator who set it in the job script.
"""

from __future__ import annotations

import os

__all__ = ["THREAD_VARS", "pin_threads", "requested_omp_threads"]

THREAD_VARS = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)
"""The thread-count variables pinned by :func:`pin_threads`."""

# Captured HERE, in the module body, because :func:`pin_threads` overwrites the
# variable in place: after it has run, an operator who asked for nothing and an
# operator who asked for ``1`` are the same string in :data:`os.environ`, and
# the difference is unrecoverable.  Read at import time, so the value below is
# the request as the process received it -- ``None`` when it was absent.
_REQUESTED_OMP_THREADS = os.environ.get("OMP_NUM_THREADS")


def requested_omp_threads() -> str | None:
    """``OMP_NUM_THREADS`` as the process received it, before :func:`pin_threads`.

    Read-only by construction: the captured value is module-private and this
    accessor returns it, so no caller can restate what was requested after the
    fact.  ``None`` means the variable was ABSENT -- not that one thread was
    requested.  That is precisely the distinction :func:`pin_threads` erases in
    :data:`os.environ`, and the reason an artefact needs both this and the
    effective value.
    """
    return _REQUESTED_OMP_THREADS


def pin_threads(env=None) -> dict:
    """Set every unset thread-count variable to ``'1'``; return the outcome.

    A variable already present in ``env`` with a non-empty value is left exactly
    as it is -- the caller's choice wins.  An empty value is treated as unset,
    because an empty ``OMP_NUM_THREADS`` means "unspecified" to the runtimes
    that read it.

    Args:
        env: Mutable mapping to act on; defaults to :data:`os.environ`.  A
            plain ``dict`` can be passed to inspect the decision without
            touching the process.

    Returns:
        ``{name: value}`` for every variable in :data:`THREAD_VARS`, holding the
        value now in force: ``'1'`` when this call set it, the original value
        when it was already set (including when set to ``'0'``).
    """
    target = os.environ if env is None else env
    effective = {}
    for name in THREAD_VARS:
        current = target.get(name)
        if current is None or not str(current).strip():
            target[name] = "1"
            current = "1"
        effective[name] = current
    return effective
