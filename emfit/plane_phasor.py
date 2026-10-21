"""Station cross-section phasors, and the ``x``-flux they imply, in phasor form.

This module is the *other* route to the power crossing a station plane, written
out on its own so that it can disagree with the first one.

:func:`emfit.ports.station_poynting` multiplies **one** ``e`` sample by **one**
``h`` sample -- ``e`` at ``t^n``, ``h`` at ``t^{n-1/2}`` -- and returns
instantaneous watts; the caller accumulates those and divides by the sample
count.  Nothing in that path is a phasor, and it is time-domain arithmetic
through and through.

The check here multiplies two **accumulated** phasors instead, once per station::

    P = 0.5 Re( sum conj(E_y) H_z  -  sum conj(E_z) H_y )

It must not call ``station_poynting``, and does not: a cross-check that ran the
code under test would agree with it by construction.  The summation is
re-derived here, and the two numbers are compared afterwards by
:func:`compare_with_time_domain`.  They agree only if

* the same station slice is integrated -- the ``h`` faces averaged over the two
  ``x`` cells that straddle the station node layer, ``ix - 1`` and ``ix``;
* the same measure is used (see below); and
* the record holds a whole number of periods, so that a two-term DFT of a real
  sinusoid *is* half a phasor and no leakage drags in a quadrature part.

The measure
-----------
The captured blocks carry the mesh metric already: the ``E`` block is
``E . dl`` on primal edges and the ``H`` block is ``H . dl`` on dual faces, so
``(E_y dy_j) (H_z dzt_k)`` is the flux through that face and no width factor is
wanted.  That is also why ``station_poynting``'s ``wy * dwz`` and ``dwy * wz``
weights cancel -- it divides by them and multiplies by them again.  A caller
holding *field* values (V/m, A/m) rather than line integrals passes
``area_yz`` / ``area_zy`` to put the cross-section area back.

The half step, and why it is ``omega dt / 2`` and not ``omega dt``
------------------------------------------------------------------
:meth:`FITStepper.step` leaves ``e`` at ``t^n`` and ``h`` at ``t^{n-1/2}``.
Only ``h`` is staggered; ``e`` needs no correction at all.  So the relative
offset between the two sampled fields is *half* a step, and the phase of the
accumulated ``H`` phasor relative to a co-located one is

    ``-omega dt / 2 = -pi f dt``

which is :func:`half_step_angle` (negative: the stored ``H`` lags).  At the
wave run's tone, ``f = 7.833566 GHz`` and ``dt = 1.906574869531e-13 s``:
``f dt = 1.4935280e-3`` cycles, so ``-pi f dt = -4.6920566e-3 rad``
(``-0.2688 deg``) -- half of the ``-omega dt = -9.3841132e-3 rad`` a whole-step
stagger would give, because half a step is the whole of the stagger.

The time-domain mean carries the same factor exactly: ``station_poynting`` does
not interpolate ``h`` forward, and its docstring says so.  Both routes are
therefore offset together, and the residual the comparison is left with is the
``cos`` of that angle, ``0.9999889923`` -- ``1.10e-5``, eleven parts per
million, far inside the one-per-cent band the check allows.  Which is the point
of leaving the half step in both routes instead of removing it from one: the
check then measures the two *summations*, not a convention applied to one side.

Removing it, for a caller who wants co-located phasors (a mode profile, say),
is an explicit multiplication by ``exp(+j pi f dt)`` -- :func:`destagger` --
never a silent interpolation.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "PLANE_CONVENTION",
    "compare_with_time_domain",
    "destagger",
    "flux_from_phasors",
    "half_step_angle",
]

#: Written into the bin dump beside the four plane blocks, because a phasor
#: record without its convention is a set of complex numbers and nothing else.
PLANE_CONVENTION = (
    "phasors S[f] = sum_n exp(-2j*pi*f*n*dt) * v[n] (time convention "
    "Re(V exp(+j*omega tn)), phase from the integer step index n, rectangular "
    "window, same accumulator window and phase as the station voltages); "
    "E_y at t^n on the primal edges of node layer ix, E_z likewise on the E_z "
    "edges of ix; H_z, H_y are the *dual-face* quantities averaged over the two "
    "x cells ix-1 and ix that straddle the station, and are therefore at "
    "t^(n-1/2): the half step is NOT removed, so the H phasors carry a factor "
    "exp(-j*pi*f*dt) relative to a co-located H; entries are mesh line "
    "integrals (E.dl on primal edges, H.dl on dual faces), so "
    "0.5*Re(sum(conj(E_y)*H_z) - sum(conj(E_z)*H_y)) is already the flux in "
    "watts and no area weight is applied"
)


def half_step_angle(f, dt) -> float:
    r"""Phase of the stored ``H`` phasor relative to a co-located one [rad].

    ``-omega dt / 2 = -pi f dt``: half a step, negative because
    :meth:`FITStepper.step` leaves ``h`` at ``t^{n-1/2}`` and the accumulator's
    ``exp(-2j pi f n dt)`` is referenced to ``t^n``.  Half, not whole: only
    ``h`` is staggered, ``e`` is already on ``t^n``.

    Args:
        f: The tone the phasors were summed at [Hz].
        dt: The leapfrog step [s].

    Returns:
        The signed angle in radians, ``-pi f dt``.

    Raises:
        ValueError: If ``f`` or ``dt`` is not positive and finite.
    """
    f = float(f)
    dt = float(dt)
    if not (np.isfinite(f) and f > 0.0):
        raise ValueError(f"f must be positive and finite, got {f!r}")
    if not (np.isfinite(dt) and dt > 0.0):
        raise ValueError(f"dt must be positive and finite, got {dt!r}")
    return float(-np.pi * f * dt)


def destagger(plane_H, f, dt):
    """Rotate captured ``H`` phasors onto ``t^n``, removing the half step.

    ``H_aligned = H * exp(+j pi f dt)`` -- the inverse of
    :func:`half_step_angle`.  Explicit, because the half step is a modelling
    choice and a silent interpolation would hide it.

    Args:
        plane_H: The captured ``H`` phasor block, any shape, complex.
        f: The tone the phasors were summed at [Hz].
        dt: The leapfrog step [s].

    Returns:
        ``plane_H * exp(+1j * pi * f * dt)``, same shape.
    """
    return np.asarray(plane_H, dtype=complex) * np.exp(
        1j * np.pi * float(f) * float(dt))


def flux_from_phasors(plane_Ey, plane_Ez, plane_Hy, plane_Hz, *,
                      area_yz=None, area_zy=None):
    r"""``x``-directed flux through the station planes, from phasors alone [W].

    ``P = 0.5 Re( sum conj(E_y) H_z - sum conj(E_z) H_y )`` per station, summed
    over the transverse plane.  Derived here rather than borrowed from
    :func:`emfit.ports.station_poynting`: the two are cross-checks, and the only
    thing they are allowed to share is the station slice itself.

    No width factor is applied by default, because the captured ``E`` and ``H``
    entries are mesh line integrals and their product is already a flux; see
    the module docstring.  ``area_yz`` / ``area_zy`` exist for callers whose
    blocks hold field values instead.

    The half step is *not* removed: the stored ``H`` phasors are at
    ``t^{n-1/2}``, and the time-domain mean this is compared against carries the
    same factor.  Call :func:`destagger` first if co-located phasors are wanted.

    Normalisation.  The blocks are raw DFT sums, and a two-term DFT of a real
    sinusoid returns ``N/2`` times the phasor; this is a *product* of two such
    sums, so it carries ``(N/2)**2 = N**2/4`` on top of the physical flux.
    Multiply by ``4/N**2`` (``N`` = accumulated samples, the ``n_samples``
    :func:`compare_with_time_domain` takes) to get watts.  The function returns
    the raw number and does not apply the factor: the scale it is checked
    against is derived and compared, never fitted and absorbed.

    Args:
        plane_Ey: ``(n_stations, n_y, n_zn)`` complex, ``E_y . dl`` on the
            station node layers.
        plane_Ez: ``(n_stations, n_y+1, n_z)`` complex, ``E_z . dl`` likewise.
        plane_Hy: ``(n_stations, n_y+1, n_z)`` complex, ``H_y . dl`` averaged
            onto the station node layers.
        plane_Hz: ``(n_stations, n_y, n_zn)`` complex, ``H_z . dl`` likewise.
        area_yz: Optional face areas for the ``E_y H_z`` term, broadcastable to
            ``plane_Ey.shape[1:]``; ``None`` means the measure is already in
            the data.
        area_zy: Optional face areas for the ``E_z H_y`` term, broadcastable to
            ``plane_Ez.shape[1:]``; ``None`` likewise.

    Returns:
        ``(n_stations,)`` float array of watts, positive along ``+x``.

    Raises:
        ValueError: If the four blocks do not agree in their station axis or in
            their transverse shapes.
    """
    ey = np.asarray(plane_Ey, dtype=complex)
    ez = np.asarray(plane_Ez, dtype=complex)
    hy = np.asarray(plane_Hy, dtype=complex)
    hz = np.asarray(plane_Hz, dtype=complex)
    for name, arr in (("plane_Ey", ey), ("plane_Ez", ez),
                      ("plane_Hy", hy), ("plane_Hz", hz)):
        if arr.ndim != 3:
            raise ValueError(
                f"{name} must be (n_stations, n_a, n_b), got shape {arr.shape}")
    n = ey.shape[0]
    if ez.shape[0] != n or hy.shape[0] != n or hz.shape[0] != n:
        raise ValueError(
            f"the planes disagree on the station axis: "
            f"{ey.shape[0]}, {ez.shape[0]}, {hy.shape[0]}, {hz.shape[0]}")
    if hz.shape[1:] != ey.shape[1:]:
        raise ValueError(
            f"plane_Hz {hz.shape[1:]} does not sit on plane_Ey {ey.shape[1:]}")
    if hy.shape[1:] != ez.shape[1:]:
        raise ValueError(
            f"plane_Hy {hy.shape[1:]} does not sit on plane_Ez {ez.shape[1:]}")
    p_yz = np.conj(ey) * hz
    if area_yz is not None:
        p_yz = p_yz * np.asarray(area_yz, dtype=float)
    p_zy = np.conj(ez) * hy
    if area_zy is not None:
        p_zy = p_zy * np.asarray(area_zy, dtype=float)
    return 0.5 * np.real(np.sum(p_yz, axis=(-2, -1)) - np.sum(p_zy, axis=(-2, -1)))


def compare_with_time_domain(flux, sx_station, *, n_samples, f, dt,
                             tolerance: float = 0.01):
    r"""Compare the phasor-domain flux with the time-domain mean, per station.

    Only the **magnitude** is gated, and the scale it is gated against is
    derived in closed form, not fitted to the record.

    The scale.  The capture accumulates ``S = sum_n exp(-2j pi f n dt) v[n]``.
    For a real sinusoid ``v[n] = Re(V exp(+j omega tn))`` over a whole number of
    periods that two-term DFT is exactly ``(N/2) V``, so ``V = 2 S / N``.  The
    phasor flux is a *product* of two such sums, so it carries
    ``(N/2)**2 = N**2/4`` on top of the physical flux, while ``sx_station`` is
    the plain running mean of the instantaneous flux, ``sum p[n] / N``, with no
    DFT factor at all.  Hence, exactly,

        ``flux(block) / sx_station = N**2 / 4``
        ``flux_physical = 4 flux / N**2``

    with ``N = n_samples`` the accumulated sample count (not the step count).
    The measured scale is reported beside the derived one rather than divided
    out: a run that comes back a factor 2 or a factor ``N`` away is a finding
    about the capture, and absorbing it into a per-run normalisation would hide
    it.

    The phase cannot be gated: both routes carry the *identical* half step
    ``-pi f dt`` (:func:`half_step_angle`) -- the time-domain mean does not
    interpolate ``h`` forward and the phasors do not remove it either -- so it
    cancels between them, and all it can leave is
    ``1 - cos(pi f dt) = 1.10e-5`` on a quadrature component, eleven parts per
    million at this run's tone.  No plausible error in either sum would move
    that number, so a phase gate could never fail and would only look like a
    check.  ``half_step_rad`` and ``cos_factor`` are therefore returned as
    printed diagnostics beside the ratio and never enter ``ok``.

    Args:
        flux: ``(n_stations,)`` from :func:`flux_from_phasors`, on the raw
            (unscaled) captured blocks.
        sx_station: ``(n_stations,)`` time-domain mean flux, e.g.
            :func:`emfit.ports.station_poynting` averaged over the record [W].
        n_samples: ``N``, the accumulated sample count the phasors were summed
            over -- the same window the time-domain mean was taken over.
        f: The tone the phasors were summed at [Hz].
        dt: The leapfrog step [s].
        tolerance: Allowed relative disagreement, as a fraction; ``0.01`` is the
            one-per-cent band the plane record is checked against.

    Returns:
        dict with ``scale_measured`` (``flux / sx_station`` per station),
        ``scale_derived`` (``N**2 / 4``, the closed form above), ``deviation_pc``
        (``100 |scale_measured / scale_derived - 1|`` per station), ``ratio``
        (``4 flux / (N**2 sx_station)``, i.e. the physical flux over the
        time-domain mean, so ``1`` is agreement), ``half_step_rad`` and
        ``cos_factor`` (printed diagnostics, not gated) and ``ok`` (every
        station's magnitude inside ``tolerance``).

    Raises:
        ValueError: If the arrays differ in length, ``n_samples`` is not
            positive, a station of ``sx_station`` is zero, or ``tolerance`` is
            not positive.
    """
    p = np.asarray(flux, dtype=float).ravel()
    s = np.asarray(sx_station, dtype=float).ravel()
    if p.size != s.size:
        raise ValueError(
            f"flux has {p.size} stations, sx_station has {s.size}")
    if np.any(s == 0.0):
        raise ValueError(
            f"a zero time-domain station has no ratio: {s!r}")
    n = int(n_samples)
    if n <= 0:
        raise ValueError(f"n_samples must be positive, got {n_samples!r}")
    tol = float(tolerance)
    if not tol > 0.0:
        raise ValueError(f"tolerance must be positive, got {tolerance!r}")
    # Closed form, from the derivation in the docstring: two-term DFT is (N/2)V,
    # so a product of two raw sums carries N**2/4 and the running mean carries
    # none.  Never divided out -- reported, so a factor 2 or N shows up.
    scale_derived = float(n * n) / 4.0
    scale_measured = p / s
    deviation = 100.0 * np.abs(scale_measured / scale_derived - 1.0)
    # Printed diagnostics only: the half step is in both routes identically.
    angle = half_step_angle(f, dt)
    return {
        "scale_measured": scale_measured,
        "scale_derived": scale_derived,
        "deviation_pc": deviation,
        "ratio": 4.0 * p / (float(n * n) * s),
        "half_step_rad": angle,
        "cos_factor": float(np.cos(angle)),
        "ok": bool(np.all(deviation < 100.0 * tol)),
    }
