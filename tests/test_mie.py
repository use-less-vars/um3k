"""Validation of the analytic 2-D Mie series for a PEC cylinder (TM_z).

:mod:`emfit.mie` is exact, so there is no ``h`` to refine: the only numerical
knobs are the truncation order ``n_max`` and float64.  These tests therefore do
not compare against a *finer* solution, they re-derive the same closed form
through a different route and demand agreement to machine precision where the
identity is algebraic, and to a documented tolerance where it is asymptotic.

What is checked, and why it is the right check
---------------------------------------------
1. **Truncation.** ``n_max = ceil(ka) + 10`` and ``sigma_tot`` unchanged when the
   margin is raised to ``+20``.  A too-small ``n_max`` is silent: it lowers the
   width by ~1.1 % at ``ka = 3`` with no warning, so the rule has to be pinned.
2. **Losslessness.** ``Re b_n = |b_n|^2`` and ``b_{-n} = b_n`` for real ``ka``.
   Both follow from ``Re H_n^(1) = J_n`` and are exact to float64; they are the
   cheapest guard on the coefficients themselves.
3. **Optical theorem.** ``(4/k) sum |b_n|^2 = -(4/k) Re f(0)``.  This is the
   guard that fixes the *sign* of ``f`` and the ``4/k`` (not ``4/k^2``)
   normalisation, neither of which fails loudly on its own.
4. **Pattern.** Pinned values at 0/45/90/135/180 deg for ``ka = 1`` and ``ka = 3``,
   symmetry under ``phi -> -phi``, and ``(1/2 pi) int sigma dphi = sigma_tot``.
   The pattern is deliberately *not* mirror-symmetric under ``phi -> pi - phi``,
   so a pattern quoted from the wrong axis is detectable (and a total width is
   not).
5. **Limit and far field.** ``sigma_tot/(4a) -> 1`` (measured 1.0366 at ``ka = 50``,
   1.0231 at ``ka = 100``), and the exact near field summed over the same
   coefficients reproduces ``sigma(phi)`` at ``k rho = 1e5``, where the far-field
   asymptotics is good to ``1/(k rho)``.

Measured numbers on this machine (``RADIUS = 1 m``, so ``k = ka``)::

    ka     n_max   |b_n_max|   rel. change of sigma_tot at n_max+20
    0.5      11     1.2e-27     0
    1        11     4.9e-21     2.2e-16
    3        13     2.8e-14     0
    10       20     7.2e-09     0
    50       60     1.1e-04     4.3e-11
    100     110     1.3e-03     6.0e-09

    ka     sigma_tot [m]   sigma_tot/(4a)
    0.5      6.956821662   1.739205
    1        5.913113722   1.478278
    3        4.942260821   1.235565
    10       4.426633944   1.106658
    50       4.146534807   1.036634
    100      4.092376281   1.023094

    sigma(phi) [m]       0 deg      45 deg     90 deg    135 deg    180 deg
    ka = 1              11.887015   7.993806   4.074360   3.709455   3.862653
    ka = 3              20.432144   2.400780   2.796431   3.151990   3.286289

Honest notes
------------
* The pinned constants are the values *this* implementation produced, so on their
  own they only catch regressions.  The physics statements (optical theorem,
  quadrature, ``4a`` limit, far field) are checked independently of them, and
  those are what make a wrong convention visible.
* ``|b_n_max|`` is not an error estimate: at ``ka = 100`` the last retained
  coefficient is still 1.3e-3 yet the width is converged to 6e-9 relative.  The
  order-of-magnitude check on ``|b_n_max|`` below is pinned loosely for that
  reason.
* There is no Rayleigh ``k^3`` law in this polarisation (TM_z is the monopole-
  dominated, "soft" case), so no low-``ka`` power law is asserted here; the
  low-``ka`` behaviour is documented in :mod:`emfit.mie` instead.
* Everything is a *width* (metres, cross section per unit length).  The
  quadrature check below would still pass if the module returned an area, but
  the ``4a`` limit and the ``(4/k)`` optical-theorem form would not.
"""

from __future__ import annotations

import numpy as np
from scipy.special import hankel1

from emfit.mie import (
    RADIUS,
    _truncation_order,
    cylinder_tm_bistatic,
    cylinder_tm_coefficients,
    cylinder_tm_total_width,
)

# electrical sizes used by the convergence / sum-rule tests
KA_GRID = np.array([0.5, 1.0, 3.0, 10.0, 50.0, 100.0])

# measured |b| at the last retained order (order of magnitude only)
REF_TAIL_COEFFICIENT = np.array([1.2e-27, 4.9e-21, 2.8e-14, 7.2e-09, 1.1e-04, 1.3e-03])

# measured total widths [m] for RADIUS = 1 m
REF_TOTAL_WIDTH = np.array([6.956821662, 5.913113722, 4.942260821,
                            4.426633944, 4.146534807, 4.092376281])

# observation angles of the pinned pattern
PATTERN_ANGLES_DEG = np.array([0.0, 45.0, 90.0, 135.0, 180.0])

# measured bistatic widths [m] at PATTERN_ANGLES_DEG
REF_PATTERN = {
    1.0: np.array([11.887015, 7.993806, 4.074360, 3.709455, 3.862653]),
    3.0: np.array([20.432144, 2.400780, 2.796431, 3.151990, 3.286289]),
}

# measured forward/backward ratios sigma(0)/sigma(pi)
REF_FWD_BACK_RATIO = {1.0: 3.077422, 3.0: 6.217392}

# measured sigma_tot/(4a) in the short-wavelength limit
REF_GEOMETRIC_RATIO = {50.0: 1.036634, 100.0: 1.023094}

# angles of the quadrature (dense enough that the trapezoid rule is exact for
# the truncated trigonometric polynomial: 20001 > 2*n_max+1)
QUADRATURE_POINTS = 20001


def _truncation_default(ka):
    """Default truncation order the module must be using for ``ka``."""
    return int(np.ceil(ka)) + 10


def _far_field_width(ka, phi, kr):
    """Exact scattered field at ``k*rho = kr``, turned into 2 pi rho |E_sca|^2.

    The sum is the same series as in :mod:`emfit.mie` but evaluated at finite
    ``rho`` instead of in the far zone, so it converges to ``sigma(phi)`` only
    like ``1/(k rho)``.
    """
    n, b = cylinder_tm_coefficients(ka)
    k = ka / RADIUS
    rho = kr / k
    # a_n = -i^n J_n(ka)/H_n^(1)(ka) = -i^n b_n, the coefficient of
    # H_n^(1)(k rho) exp(i n phi) for a unit incident exp(i k x).
    a = -(1j ** n) * b
    psi = np.exp(1j * np.outer(phi, n)) @ (a * hankel1(n, kr))
    return 2.0 * np.pi * rho * np.abs(psi) ** 2


# ---------------------------------------------------------------------------
# truncation
# ---------------------------------------------------------------------------
def test_truncation_rule_and_convergence():
    """n_max = ceil(ka)+10 is what the default uses, and it is converged."""
    for ka, tail in zip(KA_GRID, REF_TAIL_COEFFICIENT):
        n, b = cylinder_tm_coefficients(ka)
        top = _truncation_default(ka)
        assert _truncation_order(ka) == top, (
            f"truncation rule for ka={ka} gave {_truncation_order(ka)}, "
            f"expected ceil(ka)+10 = {top}")
        assert n.size == 2 * top + 1, (
            f"ka={ka}: expected 2*n_max+1 = {2 * top + 1} orders, got {n.size}")
        assert n[0] == -top and n[-1] == top, (
            f"ka={ka}: orders must run from -n_max to +n_max (both signs!), "
            f"got {n[0]}..{n[-1]}")
        assert np.all(np.diff(n) == 1), f"ka={ka}: orders are not consecutive"

        # order of magnitude of the last retained coefficient (loose: see the
        # module docstring -- this is not an error estimate)
        np.testing.assert_allclose(
            abs(b[-1]), tail, rtol=2.0,
            err_msg=f"ka={ka}: |b_n_max| = {abs(b[-1]):.2e}, expected of order {tail:.2e}")

        # the width must not care whether the margin is 10 or 30
        coarse = cylinder_tm_total_width(ka)
        fine = cylinder_tm_total_width(ka, n_max=top + 20)
        rel = abs(fine / coarse - 1.0)
        assert rel < 1e-6, (
            f"ka={ka}: raising n_max from {top} to {top + 20} moves sigma_tot by "
            f"{rel:.2e} relative ({coarse:.9f} -> {fine:.9f} m); the default "
            f"truncation is not converged")

        # |b_n| collapses factorially past the transition region at n ~ ka, but
        # it *oscillates* on the way (J_n/H_n near their turning point) -- do not
        # demand monotonicity, demand a decayed tail.
        mags = np.abs(b[n >= 0])
        assert np.all(np.diff(mags[-5:]) < 0.0), (
            f"ka={ka}: last five |b_n| must decay, got {mags[-5:]}")
        assert abs(b[-1]) < 1e-2, (
            f"ka={ka}: last retained coefficient |b_n_max| = {abs(b[-1]):.2e} is not "
            f"small; the truncation rule is not cutting the series anywhere useful")

    # the other direction has no guard in the module: under-truncation is silent
    for ka, n_max in ((10.0, 10), (3.0, 3)):
        full = cylinder_tm_total_width(ka)
        cut = cylinder_tm_total_width(ka, n_max=n_max)
        rel = cut / full - 1.0
        assert -3e-2 < rel < -5e-3, (
            f"ka={ka}, n_max={n_max}: under-truncation should lose ~1 % of the "
            f"width silently, measured {100 * rel:.2f} % ({cut:.6f} vs {full:.6f} m)")


# ---------------------------------------------------------------------------
# coefficients
# ---------------------------------------------------------------------------
def test_coefficients_are_lossless():
    """Re b_n == |b_n|^2 and b_-n == b_n for real ka (machine precision)."""
    for ka in KA_GRID:
        n, b = cylinder_tm_coefficients(ka)
        np.testing.assert_allclose(
            b.real, np.abs(b) ** 2, rtol=0.0, atol=1e-12,
            err_msg=f"ka={ka}: Re b_n must equal |b_n|^2 (lossless, Re H_n^(1) = J_n); "
                    f"worst deviation {np.max(np.abs(b.real - np.abs(b) ** 2)):.2e}")
        # the result is a probability-like quantity: 0 <= b_n <= 1
        assert np.all(b.real >= -1e-14), f"ka={ka}: Re b_n must be non-negative"
        assert np.all(np.abs(b) <= 1.0 + 1e-12), (
            f"ka={ka}: |b_n| <= 1 is implied by Re b_n = |b_n|^2, "
            f"got max {np.max(np.abs(b)):.6f}")
        # even symmetry in the order: J_-n = (-1)^n J_n, H_-n = (-1)^n H_n
        np.testing.assert_allclose(
            b, b[::-1], rtol=1e-12, atol=1e-15,
            err_msg=f"ka={ka}: b_-n must equal b_n, worst deviation "
                    f"{np.max(np.abs(b - b[::-1])):.2e}")


# ---------------------------------------------------------------------------
# optical theorem
# ---------------------------------------------------------------------------
def test_optical_theorem_forward_amplitude():
    """sigma_tot = (4/k) sum|b_n|^2 = -(4/k) Re f(0) and sigma(0) = k sigma^2/4."""
    for ka, ref in zip(KA_GRID, REF_TOTAL_WIDTH):
        n, b = cylinder_tm_coefficients(ka)
        k = ka / RADIUS
        sigma_tot = cylinder_tm_total_width(ka)
        np.testing.assert_allclose(
            sigma_tot, ref, rtol=1e-6,
            err_msg=f"ka={ka}: sigma_tot = {sigma_tot:.9f} m, recorded {ref:.9f} m")

        # forward amplitude in the module convention: f(0) = -sum_n b_n.  It is
        # complex (Im b_n != 0), but only its real part enters the theorem.
        f0 = -np.sum(b)
        sigma_from_forward = -(4.0 / k) * f0.real
        assert sigma_from_forward > 0.0, (
            f"ka={ka}: -(4/k) Re f(0) = {sigma_from_forward:.6f} is negative; the "
            f"minus sign of f(phi) is missing")
        np.testing.assert_allclose(
            sigma_from_forward, sigma_tot, rtol=1e-12,
            err_msg=f"ka={ka}: optical theorem broken: -(4/k) Re f(0) = "
                    f"{sigma_from_forward:.9f} vs (4/k) sum|b|^2 = {sigma_tot:.9f} m")

        # |f(0)|^2 >= (Re f(0))^2 with equality only for real f(0), so
        # sigma(0) >= (k/4) sigma_ext^2.  This ties the pattern of the module to
        # the optical theorem with no reference constants, and a k <-> k^2 slip
        # in the normalisation breaks it (sigma(0) would miss by a factor k).
        sigma_zero = float(cylinder_tm_bistatic(ka, 0.0))
        bound = 0.25 * k * sigma_from_forward ** 2
        assert sigma_zero >= bound * (1.0 - 1e-12), (
            f"ka={ka}: sigma(0) = {sigma_zero:.9f} m is below the optical-theorem "
            f"bound (k/4) sigma_ext^2 = {bound:.9f} m")
        assert sigma_zero < 4.0 * bound, (
            f"ka={ka}: sigma(0) = {sigma_zero:.9f} m is implausibly far above the "
            f"optical-theorem bound (k/4) sigma_ext^2 = {bound:.9f} m")


# ---------------------------------------------------------------------------
# bistatic pattern
# ---------------------------------------------------------------------------
def test_bistatic_pattern_integrates_to_total_width():
    """Pinned pattern, forward/backward asymmetry, phi -> -phi symmetry, quadrature."""
    angles = np.linspace(-np.pi, np.pi, QUADRATURE_POINTS)
    phi = np.deg2rad(PATTERN_ANGLES_DEG)

    for ka, ref in REF_PATTERN.items():
        sigma = cylinder_tm_bistatic(ka, phi)
        np.testing.assert_allclose(
            sigma, ref, rtol=1e-6,
            err_msg=f"ka={ka}: pattern at {PATTERN_ANGLES_DEG} deg drifted from "
                    f"{ref}, got {sigma}")

        # forward/backward asymmetry: sigma(0) > sigma(pi), ratio pinned
        ratio = sigma[0] / sigma[-1]
        np.testing.assert_allclose(
            ratio, REF_FWD_BACK_RATIO[ka], rtol=1e-5,
            err_msg=f"ka={ka}: sigma(0)/sigma(pi) = {ratio:.6f}, expected "
                    f"{REF_FWD_BACK_RATIO[ka]:.6f}")
        assert sigma[0] > sigma[-1], (
            f"ka={ka}: forward scattering must exceed backscattering for phi "
            f"measured from +x, got {sigma[0]:.6f} vs {sigma[-1]:.6f} m")

        # scalar and array input agree (the module reshapes back to phi)
        np.testing.assert_allclose(
            float(cylinder_tm_bistatic(ka, 0.0)), sigma[0], rtol=1e-13,
            err_msg=f"ka={ka}: scalar and array calls disagree at phi = 0")
        assert cylinder_tm_bistatic(ka, phi).shape == phi.shape

    for ka in KA_GRID:
        sigma = cylinder_tm_bistatic(ka, angles)

        # symmetry about the incidence axis only
        np.testing.assert_allclose(
            sigma, cylinder_tm_bistatic(ka, -angles), rtol=0.0,
            atol=1e-10 * np.max(sigma),
            err_msg=f"ka={ka}: sigma(phi) must equal sigma(-phi)")

        # (1/2 pi) int sigma dphi = sigma_tot: orthogonality of exp(i n phi)
        integral = float(np.trapezoid(sigma, angles) / (2.0 * np.pi))
        np.testing.assert_allclose(
            integral, cylinder_tm_total_width(ka), rtol=1e-10,
            err_msg=f"ka={ka}: (1/2pi) int sigma dphi = {integral:.9f} m but "
                    f"sigma_tot = {cylinder_tm_total_width(ka):.9f} m")

    # the pattern is NOT mirror-symmetric under phi -> pi - phi, so a pattern
    # quoted from the +y axis instead of +x is visible here (and only here:
    # a total width is blind to it).
    for ka in (1.0, 3.0):
        mirrored = cylinder_tm_bistatic(ka, np.pi - phi)
        worst = float(np.max(np.abs(cylinder_tm_bistatic(ka, phi) - mirrored)))
        assert worst > 1.0, (
            f"ka={ka}: the pattern came out symmetric under phi -> pi - phi "
            f"(worst difference {worst:.3e}); the angle is probably measured "
            f"from +y instead of from the direction of incidence")


# ---------------------------------------------------------------------------
# short-wavelength limit and far field
# ---------------------------------------------------------------------------
def test_high_frequency_geometric_limit_and_far_field():
    """sigma_tot/(4a) -> 1 at large ka, and the exact near field reproduces sigma."""
    for ka, ref in REF_GEOMETRIC_RATIO.items():
        ratio = cylinder_tm_total_width(ka) / (4.0 * RADIUS)
        np.testing.assert_allclose(
            ratio, ref, rtol=1e-6,
            err_msg=f"ka={ka}: sigma_tot/(4a) = {ratio:.6f}, recorded {ref:.6f}")
        assert 1.0 < ratio < 1.10, (
            f"ka={ka}: sigma_tot/(4a) = {ratio:.6f} should be a little above the "
            f"geometric limit 1 (2-D PEC cylinder, no shadow-forming term)"

        )
    # monotone approach to the geometric limit from above
    ratios = [cylinder_tm_total_width(ka) / (4.0 * RADIUS) for ka in (10.0, 50.0, 100.0)]
    assert ratios[0] > ratios[1] > ratios[2] > 1.0, (
        f"sigma_tot/(4a) must decrease towards 1 with ka, got {ratios}")

    # near field -> far field: 2 pi rho |E_sca|^2 -> sigma(phi), error O(1/(k rho))
    phi = np.deg2rad(PATTERN_ANGLES_DEG)
    for ka in (1.0, 3.0):
        far = cylinder_tm_bistatic(ka, phi)
        at_1e5 = _far_field_width(ka, phi, 1e5)
        np.testing.assert_allclose(
            at_1e5, far, rtol=1e-3,
            err_msg=f"ka={ka}: 2 pi rho |E_sca|^2 at k rho = 1e5 gives {at_1e5}, "
                    f"but sigma(phi) = {far} (relative deviation "
                    f"{np.max(np.abs(at_1e5 / far - 1.0)):.2e})")
        err_coarse = float(np.max(np.abs(_far_field_width(ka, phi, 1e3) - far)))
        err_fine = float(np.max(np.abs(at_1e5 - far)))
        assert err_coarse > 30.0 * err_fine, (
            f"ka={ka}: the far field must converge like 1/(k rho), measured "
            f"|error| {err_coarse:.3e} at k rho = 1e3 and {err_fine:.3e} at "
            f"1e5 (ratio {err_coarse / max(err_fine, 1e-30):.1f}, expected ~100)")
