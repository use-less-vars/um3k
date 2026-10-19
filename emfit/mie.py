"""Analytic 2-D Mie scattering by a perfectly conducting circular cylinder (TM_z).

Reference solution, not a solver
--------------------------------
Everything else in ``emfit`` is numerical: :mod:`emfit.operators` builds the
discrete complex, :mod:`emfit.evolve` marches it, :mod:`emfit.eigen` diagonalises
the PEC cavity pencil.  None of that is a *reference* -- a number is only known to
be wrong if the same problem can be written in closed form.  This module is that
closed form for one case: a circular perfectly conducting cylinder of infinite
length under a TM_z plane wave.  It is exact, so it costs no mesh, there is no
``h`` to refine and the only numerical knobs are the truncation order ``n_max``
and float64.

The scattering problem
----------------------
The incident wave travels along ``+x`` with its electric field along the cylinder
axis ``z`` (TM_z, "E parallel", "electric" or "soft" polarisation in the older
literature)::

    E_inc = exp(i k x - i omega t) zhat = exp(i k rho cos(phi)) zhat

with ``k = ka / a`` and the radius ``a`` equal to :data:`RADIUS`.  The generating
function of the Bessel functions, ``exp(i k rho cos phi) = sum_n i^n J_n(k rho)
exp(i n phi)``, is summed over *every* integer ``n`` (dropping the negative orders
halves the incident field and underestimates every width below by about a factor
of two, silently), and the scattered field is written on the outgoing cylindrical
waves ``H_n^(1)(k rho) exp(i n phi)``::

    E_sca = sum_n a_n H_n^(1)(k rho) exp(i n phi)

For TM_z the boundary condition on a PEC is Dirichlet: the tangential ``E``
vanishes, and that component *is* ``E_z``, so ``E_z(a, phi) = 0`` term by term and

    a_n = -i^n J_n(ka) / H_n^(1)(ka)

With ``H_n^(1)(z) ~ sqrt(2/(pi z)) exp(i(z - n pi/2 - pi/4))`` and
``i^n (-i)^n = 1`` the far field is a cylindrical wave with a pattern::

    E_sca -> sqrt(2/(pi k rho)) exp(i(k rho - pi/4)) f(phi)
    f(phi) = -sum_n b_n exp(i n phi),     b_n = J_n(ka) / H_n^(1)(ka)

The bistatic scattering width is the 2-D cross section, i.e. a **length** in
metres (cross section per unit length of the cylinder)::

    sigma(phi) = lim_{rho -> inf} 2 pi rho |E_sca|^2 / |E_inc|^2
               = (4/k) |f(phi)|^2

Three normalisations are easy to get wrong here and none of them raises.  The
denominator is ``k`` and not ``k^2``; the far field spreads like ``1/sqrt(rho)``,
which is the 2-D Green function, and a 2-D problem has a width in metres, not an
RCS in m^2; and ``phi`` is measured from the forward direction ``+x``, i.e. from
the propagation direction of the incident wave, counter-clockwise.  A pattern
quoted from ``+y``, or with the incident wave launched along ``-x``, is a mirror
image of this one -- and a mirror image is invisible in a total width.

Summing ``|f|^2`` with the orthogonality of ``exp(i n phi)`` gives the total
width, which for a PEC equals the extinction width (nothing is absorbed)::

    sigma_tot = (4/k) sum_n |b_n|^2

and the optical theorem in this normalisation, ``sigma_ext = -(2 eta) *
Re[ E_inc^* E_sca ]`` integrated over the large circle by stationary phase, reads

    sigma_tot = -(4/k) Re f(0) = (4/k) sum_n Re b_n

The leading minus sign of ``f`` is not cosmetic: ``f`` is the *scattered* wave, it
interferes destructively with the incident one in the forward direction, and
writing ``f`` without that minus sign yields a negative total width.  For a
lossless scatterer at real ``ka`` the coefficients satisfy ``Re b_n = |b_n|^2``
exactly, so both forms of ``sigma_tot`` agree to machine precision -- measured
2.2e-16 at ``ka = 0.5``, 1.1e-16 at ``ka = 1``, 4.4e-16 at ``ka = 3`` and 7.8e-16
at ``ka = 10`` -- and that is the cheapest available guard on the convention.

Radius convention
-----------------
``ka`` is dimensionless and is the only electrical parameter of the problem, yet
the return values must be lengths.  This module therefore fixes ``a = RADIUS =
1.0 m`` and never asks for a radius: a ``ka = 3`` pattern is the pattern of a 1 m
cylinder at ``lambda = 2 pi / 3`` m.  The fields are invariant under a common
rescaling of all lengths at fixed ``ka``, so a cylinder of radius ``a`` has
``sigma_a(phi) = (a / RADIUS) * sigma(phi)`` -- widths are quoted per 1 m of
radius and scale linearly.

Truncation
----------
``n_max = ceil(ka) + 10`` (:func:`_truncation_order`); the series then runs over
``-n_max .. n_max``.  Measured on this module:

    ======  ======  =========  ==================================
    ka      n_max   |b_n_max|  rel. change of sigma_tot at +20
    ======  ======  =========  ==================================
    0.5       11    1.2e-27    0
    1         11    4.9e-21    2.2e-16
    3         13    2.8e-14    0
    10        20    7.2e-09    0
    50        60    1.1e-04    4.3e-11
    100      110    1.3e-03    6.0e-09
    ======  ======  =========  ==================================

Past ``n = ka`` the ratio ``J_n/H_n`` collapses factorially, so the margin is
generous in ``n`` and cheap to pay.  Note that ``|b_n_max|`` is *not* the error
estimate: at ``ka = 100`` the last retained coefficient is still 1.3e-3 in
magnitude, yet the discarded tail moves the width by 6e-9 relative.  The other
direction has no guard at all: shrinking the margin is silently wrong, because
``n_max = ceil(ka)`` alone already loses 1.1 % of the width at ``ka = 10``
(4.378663 m instead of 4.426634 m) and 1.1 % at ``ka = 3`` for ``n_max = 3``.

What is *not* true here
-----------------------
* The far field is asymptotic in ``k rho``: ``2 pi rho |E_sca|^2`` approaches
  ``sigma(phi)`` only like ``1/(k rho)``.  Measured at ``ka = 1, phi = 0``: the
  relative error is ``-5.8e-3`` at ``k rho = 1e2``, ``-5.8e-5`` at ``1e4`` and
  ``-5.8e-6`` at ``1e5``.  A numerical near-to-far-field comparison therefore has
  to sit at ``k rho >= 1e5`` (or subtract the ``1/(k rho)`` term) before a
  percent-level disagreement means anything.
* There is no Rayleigh law to check at small ``ka``: for TM_z the monopole term
  dominates and ``sigma/(2a)`` *grows* as ``ka -> 0`` (5.94 at ``ka = 0.1``,
  8.13 at ``ka = 0.05``, 13.2 at ``ka = 0.02``; the leading behaviour is
  ``1/(ka ln^2(ka/2))`` rather than ``ka^3``, and the two ratios between those
  three points, 1.37 and 1.62, follow the log form).  An ``E``-parallel cylinder
  is precisely the case without a ``k^3`` term; the TE_z cylinder and the 3-D
  sphere are the ones that have it.
* Only ``|f(phi)|^2`` is returned, never ``arg f``.  The phase depends on the sign
  convention of the incident wave (``exp(+i k x)`` here, ``exp(-i k x)`` in most
  engineering texts), which flips ``arg f(0)`` and nothing else -- so compare
  magnitudes against a numerical far field, not phases.
* Not implemented: the TE_z (Neumann) problem ``b_n = J_n'(ka)/H_n'^{(1)}(ka)``;
  the near field (the series for ``E_sca(rho, phi)`` at arbitrary ``rho`` is four
  lines, but no caller in this repo wants it yet); oblique incidence, coated or
  penetrable cylinders, and any axial variation (this is a 2-D problem, the
  cylinder is infinite and uniform along ``z``).

Roadmap: the natural use of this module is the acceptance test ``docs/roadmap.md``
M1 quotes -- a bistatic pattern at ``ka = 1`` and ``ka = 3`` within 0.5 dB of the
analytic series -- and it becomes runnable once the near-to-far-field transform of
M2 (:mod:`emfit.nearfield`) exists.  M1's acceptance test is written for a PEC
*sphere*, which needs the 3-D Mie series (spherical Bessel/Riccati functions,
``mu_r``-dependent ``a_n``/``b_n``) and is **not** this module; that series is a
separate deliverable, not a generalisation of the code below.
"""

from __future__ import annotations

import numpy as np
from scipy.special import hankel1, jv

__all__ = [
    "RADIUS",
    "cylinder_tm_bistatic",
    "cylinder_tm_total_width",
    "cylinder_tm_coefficients",
]

RADIUS: float = 1.0
"""Radius of the reference cylinder [m]; every length below is quoted for it."""

# margin on ceil(ka) in the truncation rule; see the module docstring table
_MARGIN: int = 10


def _truncation_order(ka: float, margin: int = _MARGIN) -> int:
    """Highest retained cylindrical order for electrical size ``ka``: ``ceil(ka)+margin``."""
    return int(np.ceil(ka)) + int(margin)


def _check_ka(ka: float) -> float:
    """Return ``ka`` as a positive finite float, or raise ``ValueError``."""
    size = float(ka)
    if not np.isfinite(size) or size <= 0.0:
        raise ValueError(
            f"ka is the electrical size k*a and must be positive and finite, "
            f"got {size}"
        )
    return size


def cylinder_tm_coefficients(
    ka: float,
    n_max: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Cylindrical orders and TM_z scattering coefficients of the PEC cylinder.

    Returns ``(n, b)`` with ``n = [-n_max, ..., n_max]`` (integer, ``2*n_max + 1``
    entries, negative orders first) and

    ::

        b_n = J_n(ka) / H_n^(1)(ka)

    which is the coefficient of ``-b_n exp(i n phi)`` in the far-field pattern
    ``f(phi)`` of the module docstring.  ``n_max`` defaults to the truncation rule
    ``ceil(ka) + 10``; passing it explicitly is what the tests use to show that
    the default is converged.  Because the boundary condition is Dirichlet, these
    are the "TM_z" or "E parallel" coefficients; the TE_z problem would need
    ``J_n'(ka)/H_n'^{(1)}(ka)`` and is not implemented.

    Parameters
    ----------
    ka : float
        Electrical size ``k*a`` (dimensionless, must be ``> 0``); with
        :data:`RADIUS` fixed at 1 m it is also the value of ``k`` in 1/m.
    n_max : int, optional
        Highest retained order in either direction; default ``ceil(ka) + 10``.

    Returns
    -------
    n : numpy.ndarray
        Integer orders, shape ``(2*n_max + 1,)``.
    b : numpy.ndarray
        Complex scattering coefficients, same shape as ``n``.
    """
    size = _check_ka(ka)
    top = _truncation_order(size) if n_max is None else int(n_max)
    if top < 1:
        raise ValueError(
            f"n_max must be at least 1 to keep both signs of the order, got {top}"
        )
    n = np.arange(-top, top + 1)
    b = jv(n, size) / hankel1(n, size)
    return n, b


def cylinder_tm_bistatic(
    ka: float,
    phi: float | np.ndarray,
    n_max: int | None = None,
) -> np.ndarray:
    """Bistatic scattering width of the PEC cylinder [m], vectorised over ``phi``.

    ::

        sigma(phi) = (4/k) |f(phi)|^2,   f(phi) = -sum_n b_n exp(i n phi)

    with ``b_n`` from :func:`cylinder_tm_coefficients` and ``k = ka / RADIUS``.
    This is ``2 pi rho |E_sca|^2 / |E_inc|^2`` in the limit ``k rho -> inf``, a
    width in metres (2-D cross section per unit length), not an area.

    Parameters
    ----------
    ka : float
        Electrical size ``k*a`` of the cylinder whose radius is :data:`RADIUS`.
    phi : float or numpy.ndarray
        Observation angle [rad] measured from the **forward** direction ``+x``
        (the propagation direction of the incident wave), counter-clockwise.
        ``phi = 0`` is forward scattering, ``phi = pi`` is backscattering.  Any
        shape is accepted and is preserved in the result.
    n_max : int, optional
        Highest retained order; default ``ceil(ka) + 10``.

    Returns
    -------
    numpy.ndarray
        Scattering width in metres, shaped like ``phi``.
    """
    size = _check_ka(ka)
    n, b = cylinder_tm_coefficients(size, n_max)
    angles = np.asarray(phi, dtype=float)
    shape = angles.shape
    # f(phi) = -sum_n b_n exp(i n phi); the minus sign is fixed by the optical
    # theorem, see the module docstring.
    f = -(np.exp(1j * np.outer(angles.reshape(-1), n)) @ b)
    k = size / RADIUS
    sigma = (4.0 / k) * np.abs(f) ** 2
    return sigma.reshape(shape)


def cylinder_tm_total_width(ka: float, n_max: int | None = None) -> float:
    """Total (and extinction) scattering width of the PEC cylinder [m].

    From the orthogonality of ``exp(i n phi)``::

        sigma_tot = (4/k) sum_n |b_n|^2 = -(4/k) Re f(0)

    the second form being the optical theorem in the normalisation of this module
    (``sigma_ext = sigma_sca`` because the cylinder is lossless).  Only the
    ``|b_n|^2`` sum is accumulated here; the two forms agree to machine precision
    for real ``ka``, and that equality -- not this function -- is what
    ``tests/test_mie.py`` uses as its convention guard.

    Parameters
    ----------
    ka : float
        Electrical size ``k*a`` of the cylinder whose radius is :data:`RADIUS`.
    n_max : int, optional
        Highest retained order; default ``ceil(ka) + 10``.

    Returns
    -------
    float
        Total scattering width in metres (per unit length along ``z``).
    """
    size = _check_ka(ka)
    n, b = cylinder_tm_coefficients(size, n_max)
    k = size / RADIUS
    return float((4.0 / k) * np.sum(np.abs(b) ** 2))
