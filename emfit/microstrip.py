"""Closed-form quasi-static model of a microstrip line.

The model is the Hammerstad and Jensen (1980) closed form for the
characteristic impedance and the effective permittivity of a zero-thickness
strip, with the static strip-thickness correction of Jensen and Stayle applied
through Hammerstad's ``delta u``.  That is the formulation nearly every CAD tool
uses as its quasi-static baseline: the very-wide and very-narrow asymptotes are
blended by ``(1 + 10/u)**(-a b)``, where ``a`` is Hammerstad and Jensen's shape
polynomial and ``b`` their permittivity fit, so the result tends to ``eps_r``
for a very wide strip and to ``(eps_r + 1)/2`` for a very narrow one.

Nothing here is dispersive, radiative or lossy by construction; the frequency
enters only through the propagation constant, the wavelength and the two
perturbation loss estimates.

Units
-----
SI throughout, with every length in metres: ``w``, ``h`` and ``t`` in, ``w`` out
of ``width_for_z0``, propagation constants in rad/m, wavelengths in m, delay in
s/m and both loss coefficients in Np/m.  The ratio-only quantities -- ``Z0``,
``eps_eff``, ``w/h``, ``t/h`` and ``sqrt(eps_eff)`` -- are scale invariant, so a
caller who thinks in millimetres gets those right for free, but has to convert
to metres before asking for anything that carries a length.  Impedances are ohms,
permittivities are dimensionless relative values, frequencies are hertz.

Validity
--------
* Quasi-static: the cross-section must be small compared with the guided
  wavelength, i.e. roughly ``h < lambda_g / 10``.  Above that the true line is
  dispersive and ``eps_eff`` is under-predicted; use a Kirschning-Jansen type
  dispersion correction instead of this module.
* ``0.01 <= w/h <= 100`` and ``1 <= eps_r <= 128`` is the range the source
  paper fits.  Inside it the quoted accuracy is better than about 0.1 % in both
  ``Z0`` and ``eps_eff``; expect 0.1 to 0.5 % away from the fitted range, and
  noticeably worse for very thin strips (``w/h < 0.01``), where the edge
  singularity dominates and any closed form drifts.
* A finite strip thickness is handled only through ``delta u``, i.e. as an
  equivalent zero-thickness strip that is slightly wider.  That is good to a
  few per cent for ``t/h < 0.1`` and degrades quickly beyond it.
* A single strip over an infinite ground plane, uniform dielectric, no
  conductor or dielectric loss in ``Z0``/``eps_eff``, no cover, no side walls.

The two loss estimates are first-order perturbation results: they are exact only
in the limit of small loss, they count the strip but not the ground return (the
return current doubles the conductor loss of a narrow strip in practice), and
they ignore surface roughness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property

__all__ = [
    "C0",
    "COPPER_SIGMA",
    "EPS0",
    "ETA0",
    "MU0",
    "Microstrip",
    "eps_eff",
    "width_for_z0",
    "z0_eps_eff",
]

#: Speed of light in vacuum, m/s.
C0 = 299_792_458.0
#: Vacuum permeability, H/m.
MU0 = 4.0e-7 * math.pi
#: Vacuum permittivity, F/m.
EPS0 = 1.0 / (MU0 * C0 * C0)
#: Wave impedance of free space, ohm.
ETA0 = MU0 * C0
#: Conductivity of annealed copper at 20 C, S/m.
COPPER_SIGMA = 5.8e7


# ---------------------------------------------------------------------------
# the closed form
# ---------------------------------------------------------------------------
def _shape_factor(u: float) -> float:
    """Hammerstad and Jensen's shape polynomial ``f(u)`` for ``u = w/h``.

    Interpolates between the narrow-strip logarithm and the wide-strip
    parallel-plate limit; the constants are the published ones.
    """
    return 6.0 + (2.0 * math.pi - 6.0) * math.exp(-((30.666 / u) ** 0.7528))


def _z0_air(u: float, du: float = 0.0) -> float:
    """Characteristic impedance of the same strip with the dielectric removed.

    ``du`` widens the strip to account for its thickness, so the caller passes
    ``u + delta_u`` through this one entry point rather than duplicating it.
    """
    uu = u + du
    return (ETA0 / (2.0 * math.pi)) * math.log(
        _shape_factor(uu) / uu + math.sqrt(1.0 + (2.0 / uu) ** 2)
    )


def _delta_u(u: float, t_over_h: float) -> float:
    """Jensen and Stayle static thickness correction to ``w/h``.

    ``delta u = (t/(pi h)) ln(1 + 4e / ((t/h) coth^2(sqrt(6.517 u))))``: the
    widening that makes a zero-thickness strip behave like one of thickness
    ``t``, which is how the thickness enters this model.  Returns ``0.0`` for
    ``t_over_h == 0``.
    """
    if t_over_h <= 0.0:
        return 0.0
    coth = 1.0 / math.tanh(math.sqrt(6.517 * u))
    return (t_over_h / math.pi) * math.log(1.0 + 4.0 * math.e / (t_over_h * coth * coth))


def _a_shape(u: float) -> float:
    """Hammerstad and Jensen's ``a(u)`` in the effective-permittivity blend."""
    return (
        1.0
        + math.log((u**4 + (u / 52.0) ** 2) / (u**4 + 0.432)) / 49.0
        + math.log(1.0 + (u / 18.1) ** 3) / 18.7
    )


def _b_eps(eps_r: float) -> float:
    """Hammerstad and Jensen's ``b(eps_r)`` in the blend exponent."""
    return 0.564 * ((eps_r - 0.9) / (eps_r + 3.0)) ** 0.053


def z0_eps_eff(
    w_over_h: float, eps_r: float, t_over_h: float = 0.0
) -> tuple[float, float]:
    """Characteristic impedance and effective permittivity of a microstrip.

    Parameters
    ----------
    w_over_h:
        Strip width divided by substrate thickness.  Must be positive.
    eps_r:
        Relative permittivity of the substrate, ``>= 1``.
    t_over_h:
        Strip thickness in units of the substrate thickness; ``0`` (the default)
        means an infinitesimally thin strip.

    Returns
    -------
    (Z0, eps_eff)
        Ohms and dimensionless, in that order.

    Notes
    -----
    ``Z0`` is formed as ``Z0_air / sqrt(eps_eff)``, which is exact for a
    quasi-TEM line: the filled line is the air-filled one slowed down.  One
    consequence is that ``Z0 * sqrt(eps_eff)`` depends on ``w/h`` and ``t/h``
    only, never on ``eps_r``; the tests pin that.

    Raises
    ------
    ValueError
        If ``w_over_h`` is not positive, ``eps_r < 1`` or ``t_over_h < 0``.
    """
    u = float(w_over_h)
    eps_r = float(eps_r)
    t = float(t_over_h)
    if not u > 0.0:
        raise ValueError(f"w_over_h must be positive, got {w_over_h!r}")
    if not eps_r >= 1.0:
        raise ValueError(f"eps_r must be at least 1, got {eps_r!r}")
    if not t >= 0.0:
        raise ValueError(f"t_over_h must not be negative, got {t_over_h!r}")

    blend = (1.0 + 10.0 / u) ** (-_a_shape(u) * _b_eps(eps_r))
    ee = 0.5 * (eps_r + 1.0) + 0.5 * (eps_r - 1.0) * blend
    z0 = _z0_air(u, _delta_u(u, t)) / math.sqrt(ee)
    return z0, ee


def eps_eff(w_over_h: float, eps_r: float, t_over_h: float = 0.0) -> float:
    """Effective permittivity on its own; see :func:`z0_eps_eff`."""
    return z0_eps_eff(w_over_h, eps_r, t_over_h)[1]


def width_for_z0(
    target_z0: float,
    eps_r: float,
    h: float = 1.0,
    t: float = 0.0,
    *,
    max_iterations: int = 200,
) -> float:
    """Strip width that gives ``target_z0`` on a substrate of thickness ``h``.

    The inverse of :func:`z0_eps_eff`, obtained by bisection.  ``Z0`` decreases
    monotonically with ``w/h`` from infinity in the narrow-strip limit to zero in
    the wide-strip limit, so a bracket always exists and bisection cannot wander
    the way a Newton step can; the price is a guaranteed, known accuracy instead
    of a quadratic one.

    Parameters
    ----------
    target_z0:
        Wanted characteristic impedance in ohms; must be positive.
    eps_r:
        Substrate relative permittivity, ``>= 1``.
    h:
        Substrate thickness in metres; the width comes back in metres too.
    t:
        Strip thickness in the same unit as ``h``; default zero.
    max_iterations:
        Safety cap; about 70 iterations suffice for the bracket below.

    Returns
    -------
    float
        Strip width, in the same unit as ``h``.

    Notes
    -----
    The bracket is ``1e-6 <= w/h <= 1e6`` and the iteration stops when it is
    narrower than ``1e-12 * (w/h)`` relative, i.e. the width is converged to
    about twelve significant figures -- far beyond the accuracy of the model
    itself.  Raises ``ValueError`` if the target is not bracketed, which can only
    happen for a non-positive or absurdly large target.
    """
    z_target = float(target_z0)
    eps_r = float(eps_r)
    h = float(h)
    if not z_target > 0.0:
        raise ValueError(f"target_z0 must be positive, got {target_z0!r}")
    if not h > 0.0:
        raise ValueError(f"h must be positive, got {h!r}")
    t_over_h = float(t) / h

    def residual(u: float) -> float:
        return z0_eps_eff(u, eps_r, t_over_h)[0] - z_target

    lo, hi = 1e-6, 1e6
    # Z0 is decreasing in u, so the high-impedance end needs the narrow strip.
    if not (residual(hi) < 0.0 < residual(lo)):
        raise ValueError(
            f"target_z0={target_z0!r} ohm is not reachable for eps_r={eps_r!r}"
        )

    for _ in range(max_iterations):
        mid = 0.5 * (lo + hi)
        if residual(mid) > 0.0:
            lo = mid
        else:
            hi = mid
        if hi - lo <= 1e-12 * hi:
            break
    return 0.5 * (lo + hi) * h


# ---------------------------------------------------------------------------
# a line you can ask questions of
# ---------------------------------------------------------------------------
@dataclass
class Microstrip:
    """A uniform microstrip cross-section and its quasi-static properties.

    **All lengths are SI metres**: ``w``, ``h`` and ``t``, with ``eps_r`` the
    relative permittivity of the substrate.  Everything that carries a length
    comes back in metres as well -- ``beta`` in rad/m, ``effective_wavelength`` in
    m, ``delay`` in s/m and both loss coefficients in Np/m -- because all of those
    route through the SI constants ``C0``, ``ETA0`` and ``MU0``.  Only ``z0``,
    ``eps_eff``, ``w_over_h``, ``t_over_h`` and ``electrical_length_factor`` are
    scale invariant, so a caller who thinks in millimetres gets those right for
    free but must convert before asking for anything else.  The derived
    quantities are cached, so building one of these and asking it repeatedly
    costs one evaluation.

    Every property is the zero-loss quasi-static one; the two loss methods are
    first-order perturbations and are documented on their own.
    """

    w: float
    h: float
    eps_r: float
    t: float = 0.0

    def __post_init__(self) -> None:
        if not self.w > 0.0:
            raise ValueError(f"w must be positive, got {self.w!r}")
        if not self.h > 0.0:
            raise ValueError(f"h must be positive, got {self.h!r}")
        if not self.eps_r >= 1.0:
            raise ValueError(f"eps_r must be at least 1, got {self.eps_r!r}")
        if not self.t >= 0.0:
            raise ValueError(f"t must not be negative, got {self.t!r}")

    @property
    def w_over_h(self) -> float:
        """Normalised strip width, the only geometric input the model needs."""
        return self.w / self.h

    @property
    def t_over_h(self) -> float:
        """Strip thickness in units of the substrate thickness."""
        return self.t / self.h

    @cached_property
    def z0(self) -> float:
        """Quasi-static characteristic impedance, ohm."""
        return z0_eps_eff(self.w_over_h, self.eps_r, self.t_over_h)[0]

    @cached_property
    def eps_eff(self) -> float:
        """Quasi-static effective permittivity, dimensionless."""
        return z0_eps_eff(self.w_over_h, self.eps_r, self.t_over_h)[1]

    @property
    def phase_velocity(self) -> float:
        """Phase velocity ``c0 / sqrt(eps_eff)``, m/s."""
        return C0 / math.sqrt(self.eps_eff)

    @property
    def delay(self) -> float:
        """Delay per unit length, ``sqrt(eps_eff)/c0``, in s/m."""
        return math.sqrt(self.eps_eff) / C0

    @cached_property
    def electrical_length_factor(self) -> float:
        """``sqrt(eps_eff)``: multiply by ``k0 * l`` for the line's phase."""
        return math.sqrt(self.eps_eff)

    def beta(self, f: float) -> float:
        """Propagation constant ``k0 sqrt(eps_eff) = 2 pi f sqrt(eps_eff)/c0``, rad/m.

        Valid in the quasi-static regime only; a real line bends away from this
        as ``f`` approaches the point where ``h`` is a tenth of a wavelength.
        """
        if f < 0.0:
            raise ValueError(f"frequency must not be negative, got {f!r}")
        return 2.0 * math.pi * float(f) * self.electrical_length_factor / C0

    def effective_wavelength(self, f: float) -> float:
        """Guided wavelength ``c0 / (f sqrt(eps_eff))``, in metres.

        ``f`` is in hertz and every length in this class is in metres, so the
        answer is metres; multiply by 1e3 for millimetres.
        """
        if not f > 0.0:
            raise ValueError(f"frequency must be positive, got {f!r}")
        return C0 / (float(f) * self.electrical_length_factor)

    def conductor_loss(self, f: float, sigma: float = COPPER_SIGMA) -> float:
        """Strip conductor loss, Np/m, from the surface-resistance perturbation.

        ``alpha_c = Rs / (Z0 w_eff)`` with ``Rs = sqrt(pi f mu0 / sigma)`` and
        ``w_eff`` the thickness-corrected strip width.  ``w_eff`` is metres, like
        every length in this class, and the formula cannot know what unit it was
        handed: a millimetre geometry therefore comes back a factor of 1000 too
        small.  That is left as a documented factor rather than being guessed
        at, because a unit heuristic that fires on the wrong caller is worse than
        an obviously low attenuation; the tests pin the factor of 1000.  Only the
        strip is counted: the ground return carries a comparable current, so a
        real narrow line loses roughly twice as much.  Surface roughness and the
        edge current singularity are not modelled.
        """
        if not f > 0.0:
            raise ValueError(f"frequency must be positive, got {f!r}")
        if not sigma > 0.0:
            raise ValueError(f"sigma must be positive, got {sigma!r}")
        rs = math.sqrt(math.pi * float(f) * MU0 / float(sigma))
        w_eff = self.h * (self.w_over_h + _delta_u(self.w_over_h, self.t_over_h))
        return rs / (self.z0 * w_eff)

    def dielectric_loss(self, f: float, tan_delta: float) -> float:
        """Substrate dielectric loss, Np/m, from the standard perturbation.

        ``alpha_d = k0 eps_r (eps_eff - 1) tan(delta) / (2 sqrt(eps_eff) (eps_r - 1))``,
        the usual Pucel/Schneider result for a microstrip.  ``tan_delta`` is the
        substrate loss tangent at ``f``; dispersion, and the fact that only part
        of the field sits in the substrate, are both already folded into the
        ``(eps_eff - 1)/(eps_r - 1)`` factor.
        """
        if not f > 0.0:
            raise ValueError(f"frequency must be positive, got {f!r}")
        if tan_delta < 0.0:
            raise ValueError(f"tan_delta must not be negative, got {tan_delta!r}")
        if self.eps_r == 1.0:
            # No dielectric, so nothing to absorb: the formula is 0/0 here.
            return 0.0
        k0 = 2.0 * math.pi * float(f) / C0
        return (
            k0
            * self.eps_r
            * (self.eps_eff - 1.0)
            * float(tan_delta)
            / (2.0 * math.sqrt(self.eps_eff) * (self.eps_r - 1.0))
        )
