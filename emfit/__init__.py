"""emfit -- Finite Integration Technique (FIT) for computational electromagnetics.

FIT discretises Maxwell's equations on a pair of interlocked cell complexes (a
*primal* grid and a *dual* grid) rather than on a single mesh of elements.  The
approach was introduced by Thomas Weiland.  Its defining structural property is
the separation of

* **topology** -- the incidence matrices ``G`` (gradient), ``C`` (curl) and
  ``S`` (divergence).  These contain only -1, 0 and +1, depend on no length at
  all, and satisfy ``C G = 0`` and ``S C = 0`` *exactly*.
* **metric** -- the diagonal material (Hodge) matrices ``M_eps`` and ``M_mu``,
  which carry every edge length, face area and dual area.  Non-orthogonal and
  non-uniform grids therefore only change the metric, never the topology.

Grid conventions
----------------
Arrays are indexed ``(i, j, k)`` and flattened in C order.  A grid of
``nx * ny * nz`` cells has ``nx+1`` nodes per axis; cell ``(i,j,k)`` spans
nodes ``i..i+1``, ``j..j+1``, ``k..k+1``.

===============  =========================================  ====================
quantity         location                                   array shape
===============  =========================================  ====================
``EX, EY, EZ``   primal edge, electric voltage (V)          (nx,ny+1,nz+1) etc.
``FX, FY, FZ``   primal face, magnetic flux / H (Wb, A/m)   (nx+1,ny,nz) etc.
``N``            primal node, scalar potential (V)          (nx+1,ny+1,nz+1)
``V``            primal cell, charge / divergence (C)       (nx,ny,nz)
===============  =========================================  ====================

The package version is not released yet.
"""

# Thread pinning must run before anything imports numpy: BLAS reads its thread
# count once, when the shared library is loaded (see emfit/_env.py).
from ._env import pin_threads as _pin_threads

_pin_threads()

del _pin_threads

__version__ = "0.1.0.dev0"

DEFAULT_PORT = 8010
"""Port that ``python -m emfit serve`` binds when no ``--port`` is given.

Deliberately not 8000: that is the first port a local tool reaches for, so it is
routinely already held by an unrelated development server, and this front end is
a single-user convenience that should start rather than negotiate.  ``--port N``
moves it, and ``--port 0`` asks the OS for a free one.
"""
