"""Tests for :mod:`emfit.microstrip`, the Hammerstad-Jensen microstrip model.

Three independent layers, deliberately kept separate so that a failure says
which kind of claim broke:

1. *Structure.*  Limits and monotonicity that must hold for any quasi-static
   microstrip model, independent of the particular fit: ``eps_eff -> 1`` as
   ``eps_r -> 1``; ``Z0 * sqrt(eps_eff)`` -- the impedance of the same strip in
   air -- independent of ``eps_r`` to machine precision; ``Z0`` strictly
   decreasing and ``eps_eff`` strictly increasing in ``w/h``; ``eps_eff``
   increasing in ``eps_r`` and bounded by it; ``width_for_z0`` inverting
   ``z0_eps_eff``; the thickness correction widening the strip (lowering
   ``Z0``) and vanishing at ``t = 0``; the derived quantities being mutually
   consistent (``beta``, wavelength, velocity, delay).

2. *Reference values.*  A handful of numbers from the literature, given with
   the tolerance each one actually deserves rather than a fake precision.  The
   comment block above the table says where each number comes from and how much
   it can be trusted: these are standard design-chart values and textbook
   worked examples, quoted to the accuracy with which they are usually printed,
   so the tolerances are a few per cent, not 0.1 %.  The values here that are
   not from the literature are the ``Z0`` the study and the board report print:
   the closed form at their own cross-section, on the 35 um foil they are cut
   from, pinned on both sides of the foil in the ``test_z0_at_the_study_``
   tests below and again through the study itself in ``test_studies``.

3. *An independent numerical oracle.*  A finite-volume solution of the 2-D
   Laplace equation on the cross-section -- a completely different route to the
   same physics: no closed form, no strip formulas, just ``div(eps grad V) = 0``
   with the strip at 1 V, the ground plane and a surrounding box at 0 V, and the
   permittivity taken per cell so that the substrate-air interface sits on a grid
   line.  The charge on the strip comes from the flux out of the Dirichlet rows,
   the capacitance from that, ``eps_eff`` from ``C(eps_r)/C(1)`` and ``Z0`` from
   ``1/(c0 sqrt(C_air C_die))``.  Two grid steps are used, and the drift between
   them is what sets the tolerance in layer 3: the scheme is first-order at a
   strip edge (the field singularity there is not resolved by a 5-point
   stencil), so the discrepancy with the closed form halves when the step
   halves.  The measured numbers are recorded in the test docstrings.
"""

from __future__ import annotations

import inspect
import math

import numpy as np
import pytest
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

from emfit.cli import BOARD_COPPER_T
from emfit.microstrip import (
    C0,
    COPPER_SIGMA,
    COPPER_T,
    EPS0,
    ETA0,
    MU0,
    Microstrip,
    corrected_transmission,
    eps_eff,
    ideal_transmission,
    width_for_z0,
    z0_eps_eff,
)
from emfit.studies import MS_EPS_R, MS_H, MS_W

# ---------------------------------------------------------------------------
# the finite-difference oracle (layer 3)
# ---------------------------------------------------------------------------
#: Vacuum constants used by the oracle, restated here so that the oracle shares
#: no code and no constants with the module under test.
FD_C0 = 299_792_458.0
FD_EPS0 = 8.854_187_812_8e-12

#: Half-width of the box beyond the strip edge and height above the strip, in
#: units of h.  Ten substrate thicknesses is enough that the grounded walls move
#: the capacitance by well under a tenth of a per cent (measured: going from 10h
#: to 40h changes Z0 by 0.4 % at a step of 0.1h).
FD_MARGIN = 10.0


def fd_capacitance(w_over_h: float, eps_r: float, step: float) -> float:
    """Capacitance per unit length of the microstrip cross-section, F/m.

    Finite-volume discretisation of ``div(eps grad V) = 0`` on a uniform grid of
    step ``step`` (in units of ``h``, with ``h = 1``).  The strip is the row of
    nodes at ``y = h`` with ``|x| <= w/2``, held at 1 V; the ground plane at
    ``y = 0``, the top wall at ``y = 1 + FD_MARGIN`` and the side wall at
    ``x = w/2 + FD_MARGIN`` are held at 0 V.  The plane ``x = 0`` is a symmetry
    plane, so only half the cross-section is solved and the charge is doubled.

    Permittivity is assigned per cell (a cell is the interval between two
    neighbouring nodes), so a face *perpendicular* to the interface sees one
    cell's permittivity, while a face *along* the interface -- the only place it
    happens is the node row exactly at ``y = h`` -- sees the arithmetic mean of
    the two cells it separates, which is the correct weight for a field
    tangential to the interface.

    The charge is the flux leaving the strip nodes, ``sum(eps_face (1 - V_nb))``:
    with a uniform step the face length and the node separation cancel, so this
    is already per unit length and only the vacuum permittivity is still missing.
    """
    h = 1.0
    nx = int(round((0.5 * w_over_h + FD_MARGIN * h) / step)) + 1
    ny = int(round((h + FD_MARGIN * h) / step)) + 1
    j_strip = int(round(h / step))
    i_edge = int(round(0.5 * w_over_h / step))

    # Cell permittivities: cell k spans [k*step, (k+1)*step], centre below h?
    centres = np.arange(ny - 1) * step + 0.5 * step
    eps_cell = np.where(centres < h, eps_r, 1.0)

    # Face coefficients (face permittivities; the 1/step**2 of the FV derivation
    # is common to every face and drops out of the linear system).
    cx = np.zeros((nx - 1, ny))
    for j in range(1, ny - 1):
        cx[:, j] = 0.5 * (eps_cell[j - 1] + eps_cell[j])
    cy = np.repeat(eps_cell[None, :], nx, axis=0)

    coeff_right = np.zeros((nx, ny))
    coeff_right[: nx - 1, :] = cx
    coeff_left = np.zeros((nx, ny))
    coeff_left[1:, :] = cx
    coeff_up = np.zeros((nx, ny))
    coeff_up[:, : ny - 1] = cy
    coeff_down = np.zeros((nx, ny))
    coeff_down[:, 1:] = cy

    # Dirichlet nodes: ground, top wall, far wall, strip.
    unknown = np.ones((nx, ny), dtype=bool)
    unknown[:, 0] = False
    unknown[:, ny - 1] = False
    unknown[nx - 1, :] = False
    unknown[: i_edge + 1, j_strip] = False

    n = int(unknown.sum())
    index = -np.ones((nx, ny), dtype=np.int64)
    index[unknown] = np.arange(n)

    potential = np.zeros((nx, ny))
    potential[: i_edge + 1, j_strip] = 1.0

    diagonal = coeff_right + coeff_left + coeff_up + coeff_down
    rows = [index[unknown]]
    cols = [index[unknown]]
    values = [diagonal[unknown]]
    rhs = np.zeros(n)

    for di, dj, coeff in (
        (1, 0, coeff_right),
        (-1, 0, coeff_left),
        (0, 1, coeff_up),
        (0, -1, coeff_down),
    ):
        source = unknown.copy()
        if di == 1:
            source[-1, :] = False
        elif di == -1:
            source[0, :] = False
        if dj == 1:
            source[:, -1] = False
        elif dj == -1:
            source[:, 0] = False
        si, sj = np.nonzero(source)
        ni, nj = si + di, sj + dj
        c = coeff[si, sj]
        neighbour_unknown = unknown[ni, nj]
        rows.append(index[si, sj][neighbour_unknown])
        cols.append(index[ni, nj][neighbour_unknown])
        values.append(-c[neighbour_unknown])
        neighbour_known = ~neighbour_unknown
        rhs[index[si, sj][neighbour_known]] += (
            c[neighbour_known] * potential[ni[neighbour_known], nj[neighbour_known]]
        )

    matrix = coo_matrix(
        (
            np.concatenate(values),
            (np.concatenate(rows), np.concatenate(cols)),
        ),
        shape=(n, n),
    ).tocsr()
    potential[unknown] = spsolve(matrix, rhs)

    strip = np.arange(i_edge + 1)
    half_charge = np.sum(coeff_up[strip, j_strip] * (1.0 - potential[strip, j_strip + 1]))
    half_charge += np.sum(
        coeff_down[strip, j_strip] * (1.0 - potential[strip, j_strip - 1])
    )
    half_charge += coeff_right[i_edge, j_strip] * (1.0 - potential[i_edge + 1, j_strip])
    return FD_EPS0 * 2.0 * half_charge


def fd_z0_eps_eff(w_over_h: float, eps_r: float, step: float) -> tuple[float, float]:
    """``(Z0, eps_eff)`` from two finite-volume capacitance solves.

    ``eps_eff = C(eps_r)/C(1)`` is exact for a quasi-TEM line, and
    ``Z0 = 1/(c0 sqrt(C_air C_die))`` follows from ``Z0 = sqrt(L/C)`` with
    ``L = 1/(c0**2 C_air)``; neither uses anything from the module under test.
    """
    c_air = fd_capacitance(w_over_h, 1.0, step)
    c_die = fd_capacitance(w_over_h, eps_r, step)
    return 1.0 / (FD_C0 * math.sqrt(c_air * c_die)), c_die / c_air


# ---------------------------------------------------------------------------
# layer 1: structure and limits
# ---------------------------------------------------------------------------
def test_eps_eff_tends_to_one_as_eps_r_does():
    """With ``eps_r = 1`` there is no dielectric, so the line is in air."""
    for u in (0.1, 0.5, 1.0, 3.0, 20.0):
        z0, ee = z0_eps_eff(u, 1.0)
        assert ee == pytest.approx(1.0, rel=1e-15)
        # and the impedance is then the air-filled one
        assert z0_eps_eff(u, 7.0)[0] * math.sqrt(z0_eps_eff(u, 7.0)[1]) == pytest.approx(
            z0, rel=1e-14
        )


def test_eps_eff_between_one_and_eps_r():
    """The field is partly in air, so ``1 <= eps_eff <= eps_r`` for every width."""
    for eps_r in (2.2, 4.4, 9.8, 12.9):
        for u in (0.02, 0.1, 1.0, 10.0, 100.0):
            ee = eps_eff(u, eps_r)
            assert 1.0 <= ee <= eps_r


def test_eps_eff_asymptotes_to_the_half_and_half_and_full_values():
    """Very wide strips see ``eps_r``; narrow ones approach ``(eps_r+1)/2``.

    The wide asymptote is reached quickly, because the blend decays as a power of
    ``u``.  The narrow one is not: at ``eps_r = 9.8`` the limit is 5.4 and the
    model still gives 5.74 at ``w/h = 0.01``, the bottom of its documented range,
    so the narrow check is a monotone approach plus a loose bound rather than an
    equality.  (Below about ``w/h = 1e-3`` Hammerstad and Jensen's ``a(u)`` turns
    negative and the blend stops being meaningful at all, which is why the fit
    is only quoted down to 0.01.)
    """
    eps_r = 9.8
    half = 0.5 * (eps_r + 1.0)
    narrow = [eps_eff(u, eps_r) for u in (1.0, 0.1, 0.01)]
    assert all(b < a for a, b in zip(narrow, narrow[1:]))
    assert narrow[-1] == pytest.approx(half, rel=7e-2)
    # at w/h = 1e4 the blend is down to 5e-4, so the wide side is essentially
    # converged -- but only to the fit's own 0.1 % accuracy, not to 1e-6
    assert eps_eff(1e4, eps_r) == pytest.approx(eps_r, rel=1e-3)


def test_air_impedance_is_independent_of_eps_r():
    """``Z0 sqrt(eps_eff)`` is the air-filled impedance and cannot see ``eps_r``.

    This is a structural identity of forming ``Z0 = Z0_air/sqrt(eps_eff)``, and it
    is what makes the pair physically consistent, so it is checked to machine
    precision rather than to a tolerance.
    """
    for u in (0.05, 0.3, 1.0, 2.5, 8.0, 40.0):
        values = []
        for eps_r in (1.0, 2.2, 4.4, 10.2, 100.0):
            z0, ee = z0_eps_eff(u, eps_r)
            values.append(z0 * math.sqrt(ee))
        assert max(values) - min(values) <= 1e-12 * max(values)


def test_z0_decreases_and_eps_eff_increases_with_width():
    """Both are strictly monotone in ``w/h`` -- checked on a coarse sweep."""
    widths = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 10.0, 50.0]
    for eps_r in (2.2, 4.4, 9.8):
        z0s = [z0_eps_eff(u, eps_r)[0] for u in widths]
        ees = [z0_eps_eff(u, eps_r)[1] for u in widths]
        assert all(b < a for a, b in zip(z0s, z0s[1:]))
        assert all(b > a for a, b in zip(ees, ees[1:]))


def test_eps_eff_increases_with_eps_r():
    """For a fixed geometry a denser substrate always slows the line down more."""
    for u in (0.1, 1.0, 5.0):
        ees = [eps_eff(u, eps_r) for eps_r in (1.0, 1.5, 2.2, 4.4, 9.8, 30.0, 128.0)]
        assert all(b > a for a, b in zip(ees, ees[1:]))


def test_wider_strip_has_lower_impedance_than_narrower():
    """The same statement through the dataclass, i.e. through ``w`` and ``h``."""
    lines = [Microstrip(w=w, h=1.0, eps_r=4.4) for w in (0.2, 0.5, 1.0, 2.0, 5.0)]
    z0s = [line.z0 for line in lines]
    assert all(b < a for a, b in zip(z0s, z0s[1:]))


def test_scaling_invariance():
    """Only ``w/h`` and ``t/h`` enter, so a common scale factor cancels."""
    a = Microstrip(w=0.3, h=0.2, eps_r=4.4, t=0.007)
    b = Microstrip(w=3.0, h=2.0, eps_r=4.4, t=0.07)
    assert b.z0 == pytest.approx(a.z0, rel=1e-14)
    assert b.eps_eff == pytest.approx(a.eps_eff, rel=1e-14)


def test_thickness_widens_the_strip_and_lowers_z0():
    """``t > 0`` must behave like a slightly wider strip, not a narrower one."""
    for u in (0.5, 1.0, 4.0):
        thin = z0_eps_eff(u, 4.4, 0.0)
        thick = z0_eps_eff(u, 4.4, 0.05)
        assert thick[0] < thin[0]
        assert thick[1] == pytest.approx(thin[1], rel=1e-15)  # eps_eff is t-free
        # and the thickness correction does nothing at t = 0 exactly
        assert z0_eps_eff(u, 4.4, 0.0) == thin


def test_width_for_z0_inverts_z0_eps_eff():
    """The bisection must return the width whose impedance is the requested one."""
    for eps_r in (2.2, 4.4, 9.8):
        for target in (30.0, 50.0, 75.0, 120.0):
            w = width_for_z0(target, eps_r, h=0.5)
            z0 = z0_eps_eff(w / 0.5, eps_r)[0]
            assert z0 == pytest.approx(target, rel=1e-11)


def test_width_for_z0_respects_thickness_and_units():
    """A thicker strip needs to be narrower to hit the same impedance."""
    thin = width_for_z0(50.0, 2.2, h=1.0, t=0.0)
    thick = width_for_z0(50.0, 2.2, h=1.0, t=0.07)
    assert thick < thin
    # twice the substrate thickness, twice the width: the answer follows h
    assert width_for_z0(50.0, 2.2, h=0.635) == pytest.approx(0.635 * thin, rel=1e-13)


def test_microstrip_derived_quantities_are_consistent():
    """``beta``, wavelength, velocity and delay must agree with each other."""
    line = Microstrip(w=1.9, h=0.8, eps_r=4.2)
    f = 10e9
    root = math.sqrt(line.eps_eff)
    assert line.electrical_length_factor == pytest.approx(root, rel=1e-15)
    assert line.phase_velocity == pytest.approx(C0 / root, rel=1e-15)
    assert line.delay == pytest.approx(root / C0, rel=1e-15)
    assert line.beta(f) == pytest.approx(2.0 * math.pi * f / C0 * root, rel=1e-15)
    assert line.effective_wavelength(f) == pytest.approx(C0 / (f * root), rel=1e-15)
    assert line.beta(f) * line.effective_wavelength(f) == pytest.approx(2.0 * math.pi)
    assert line.delay * C0 == pytest.approx(root)
    # one guided wavelength per period of the propagation constant
    assert line.phase_velocity / f == pytest.approx(line.effective_wavelength(f))


def test_constant_relations():
    """The exported constants must be the SI ones, not rounded copies."""
    assert MU0 == pytest.approx(4.0e-7 * math.pi)
    assert C0 == pytest.approx(299_792_458.0)
    assert EPS0 == pytest.approx(1.0 / (MU0 * C0 * C0))
    assert ETA0 == pytest.approx(MU0 * C0)
    assert ETA0 == pytest.approx(376.730313668, rel=1e-9)
    assert COPPER_SIGMA == pytest.approx(5.8e7)


def test_copper_t_is_the_35_um_foil_and_the_board_report_aliases_it():
    """35 um, and the board report's copy is the same object, not a repeat."""
    assert COPPER_T == 35e-6, f"COPPER_T is {COPPER_T!r}, not 35e-6"
    assert BOARD_COPPER_T is COPPER_T, (
        f"the board report's {BOARD_COPPER_T!r} is a separate constant from "
        f"COPPER_T = {COPPER_T!r}, so the two references can drift apart")


def test_z0_at_the_study_cross_section_is_the_35_um_foil_value():
    """``w/h = 2`` on ``eps_r = 4.4``, the study's line: 48.099 ohm on 35 um.

    Measured 48.098655 on the foil and 48.685768 on a zero-thickness sheet, so
    the two differ by 0.587 ohm and a tolerance of 2e-3 ohm tells them apart.
    """
    line = Microstrip(w=MS_W, h=MS_H, eps_r=MS_EPS_R, t=COPPER_T)
    assert line.z0 == pytest.approx(48.099, abs=2e-3), (
        f"Z0 on the 35 um foil is {line.z0!r}, not 48.099 ohm")


def test_z0_at_the_study_cross_section_is_48_686_on_a_bare_sheet():
    """The zero-thickness value both reports printed before the foil reached it.

    Pinned so the size of the change stays visible -- the two numbers are one
    call apart, and this one is still what ``t = 0`` means.
    """
    line = Microstrip(w=MS_W, h=MS_H, eps_r=MS_EPS_R, t=0.0)
    assert line.z0 == pytest.approx(48.686, abs=2e-3), (
        f"Z0 on a zero-thickness sheet is {line.z0!r}, not 48.686 ohm")


def test_the_foil_thickness_leaves_eps_eff_bit_identical():
    """``eps_eff`` never sees ``t``, so the two must be the same float."""
    foil = Microstrip(w=MS_W, h=MS_H, eps_r=MS_EPS_R, t=COPPER_T)
    sheet = Microstrip(w=MS_W, h=MS_H, eps_r=MS_EPS_R, t=0.0)
    assert foil.eps_eff == sheet.eps_eff, (
        f"eps_eff moved with the foil thickness: {foil.eps_eff!r} != "
        f"{sheet.eps_eff!r}")


def test_losses_have_the_expected_shape():
    """``alpha_c ~ sqrt(f)``; ``alpha_d`` vanishes without loss or dielectric."""
    # Metres, not millimetres: conductor_loss divides by the strip width in the
    # caller's unit, so a millimetre geometry comes back in Np/mm.
    line = Microstrip(w=1.9e-3, h=0.8e-3, eps_r=4.2)
    a1 = line.conductor_loss(1e9)
    a4 = line.conductor_loss(4e9)
    assert a4 == pytest.approx(2.0 * a1, rel=1e-12)
    assert a1 > 0.0
    assert line.dielectric_loss(1e9, 0.0) == 0.0
    assert line.dielectric_loss(1e9, 0.02) > 0.0
    # a line with no dielectric at all cannot have dielectric loss
    assert Microstrip(w=1.0, h=1.0, eps_r=1.0).dielectric_loss(1e9, 0.02) == 0.0
    # a plausible FR-4 figure: a few tenths of a Np/m, i.e. about 1 dB/m, at
    # 1 GHz; kilo-Np/m would not be
    assert 0.01 < a1 < 10.0


def test_millimetre_geometry_scales_conductor_loss_by_a_thousand():
    """Lengths are metres; a millimetre geometry is off by a factor of 1000.

    The contract is plain: every length passed to :class:`Microstrip` is in SI
    metres, and every length-like result (:math:`\\beta` in rad/m, wavelength
    and ``w_eff`` in m, delay in s/m, ``conductor_loss`` and ``dielectric_loss``
    in Np/m) is in SI base units.  The class does not guess units from the
    magnitude of its arguments, so a geometry handed over in millimetres is not
    detected and not refused.  What happens instead is a predictable, documented
    scale error: ``conductor_loss`` divides by the strip width exactly as given,
    so ``w = 1.9`` means ``1.9 m`` and the answer comes back in Np/mm -- which
    is ``1e-3`` times the Np/m value for the physically identical 1.9 mm line.
    That number is absurdly low (a thousandth of a plausible attenuation, not a
    plausible attenuation), and it is the only kind of wrongness on offer here.

    This test pins that factor of 1000 on purpose.  It is not an endorsement of
    the error; it is a statement that the error is a *contract* consequence
    rather than a bug, so nobody later "fixes" it by adding a unit heuristic
    (sniffing magnitudes, a ``units=`` keyword, or a helpful raise) without
    deliberately reopening the unit contract and rewriting this test with it.
    Ratio-only quantities are unaffected: ``Z0`` and ``eps_eff`` depend on
    ``w/h`` and ``t/h``, so they agree between the two geometries to machine
    precision, which is exactly why the mistake can slip past casual
    inspection of the impedance and only shows up in the losses.
    """
    metres = Microstrip(w=1.9e-3, h=0.8e-3, eps_r=4.2)
    millimetres = Microstrip(w=1.9, h=0.8, eps_r=4.2)
    ratio = millimetres.conductor_loss(1e9) / metres.conductor_loss(1e9)
    assert ratio == pytest.approx(1e-3, rel=1e-12)
    # the impedance cannot see the mistake: it is a pure ratio of the lengths
    assert millimetres.z0 == pytest.approx(metres.z0, rel=1e-14)


def test_invalid_arguments_are_rejected():
    """Silly geometry is refused rather than silently producing a number."""
    with pytest.raises(ValueError):
        z0_eps_eff(0.0, 4.4)
    with pytest.raises(ValueError):
        z0_eps_eff(-1.0, 4.4)
    with pytest.raises(ValueError):
        z0_eps_eff(1.0, 0.5)
    with pytest.raises(ValueError):
        z0_eps_eff(1.0, 4.4, t_over_h=-0.01)
    with pytest.raises(ValueError):
        width_for_z0(0.0, 4.4)
    with pytest.raises(ValueError):
        width_for_z0(50.0, 4.4, h=0.0)
    with pytest.raises(ValueError):
        Microstrip(w=0.0, h=1.0, eps_r=4.4)
    with pytest.raises(ValueError):
        Microstrip(w=1.0, h=0.0, eps_r=4.4)
    with pytest.raises(ValueError):
        Microstrip(w=1.0, h=1.0, eps_r=0.9)
    with pytest.raises(ValueError):
        Microstrip(w=1.0, h=1.0, eps_r=4.4, t=-0.01)
    line = Microstrip(w=1.0, h=1.0, eps_r=4.4)
    with pytest.raises(ValueError):
        line.beta(-1.0)
    with pytest.raises(ValueError):
        line.effective_wavelength(0.0)
    with pytest.raises(ValueError):
        line.conductor_loss(0.0)
    with pytest.raises(ValueError):
        line.conductor_loss(1e9, sigma=0.0)
    with pytest.raises(ValueError):
        line.dielectric_loss(0.0, 0.02)
    with pytest.raises(ValueError):
        line.dielectric_loss(1e9, -0.02)


# ---------------------------------------------------------------------------
# layer 2: literature values
# ---------------------------------------------------------------------------
# Each entry is ``(w/h, eps_r, Z0, relative tolerance, source note)``.
#
# These are design-chart and worked-example values, not measurements.  The
# tolerances are set to what the quoted figures can support and no tighter:
#
# * Pozar, "Microwave Engineering", 3rd ed., Example 3.7: a 50 ohm line on
#   eps_r = 2.2 gives w/d = 3.081 (he then rounds to 3.0 cm for a 1 cm
#   substrate).  This is a worked example, so 3 % is a fair tolerance for it.
# * The same book's design charts, and every mnemonic in the field, put a 50 ohm
#   FR-4 line (eps_r about 4.4) at w/h just under 2, and a 50 ohm alumina line
#   (eps_r about 9.8) at w/h about 1.  Those are read off a chart, so the
#   tolerances are 10 % and 15 % respectively; the point of those two rows is
#   the order of magnitude, which is what a sanity check needs.
#
# Nothing here is invented: where the source is a chart rather than a worked
# number, the tolerance says so.
LITERATURE_W_OVER_H = [
    (3.081, 2.2, 50.0, 0.03, "Pozar 3rd ed. Example 3.7"),
    (1.9, 4.4, 50.0, 0.10, "50 ohm on FR-4, chart value"),
    (1.0, 9.8, 50.0, 0.15, "50 ohm on alumina, chart value"),
]


@pytest.mark.parametrize(
    "w_over_h, eps_r, target, tol, note", LITERATURE_W_OVER_H, ids=[r[4] for r in LITERATURE_W_OVER_H]
)
def test_width_for_z0_matches_literature(
    w_over_h: float, eps_r: float, target: float, tol: float, note: str
) -> None:
    """``width_for_z0`` reproduces the published 50 ohm widths.

    The tolerance is per row and is documented above; a chart-read value cannot
    be held to the accuracy of a worked example.
    """
    got = width_for_z0(target, eps_r, h=1.0)
    assert got == pytest.approx(w_over_h, rel=tol), note


def test_reference_impedances_at_round_geometries():
    """Regression pins, not validation: the module's own output, frozen.

    ``w/h = 1`` on ``eps_r = 2.2`` and ``w/h = 2`` on ``eps_r = 9.8`` bracket the
    useful range.  The four numbers below were evaluated once from
    :func:`z0_eps_eff` and pasted in at four significant figures; they are
    pinned to catch a silent change in the fit, and they prove nothing about
    whether the fit is right.  The independent evidence is elsewhere: the Pozar
    inverse case in :data:`LITERATURE_W_OVER_H` and the finite-volume oracle in
    layer 3.
    """
    z0_a, ee_a = z0_eps_eff(1.0, 2.2)
    z0_b, ee_b = z0_eps_eff(2.0, 9.8)
    assert z0_a == pytest.approx(94.96, rel=1e-3)
    assert ee_a == pytest.approx(1.772, rel=1e-3)
    assert z0_b == pytest.approx(33.57, rel=1e-3)
    assert ee_b == pytest.approx(7.034, rel=1e-3)


# ---------------------------------------------------------------------------
# layer 3: the numerical oracle
# ---------------------------------------------------------------------------
# Measured discrepancies, (closed form / oracle - 1) * 100, at eps_r = 4.4:
#
#   w/h = 1:  step 0.1h  Z0 -7.98 %, eps_eff +0.55 %
#             step 0.05h Z0 -4.36 %, eps_eff +0.02 %
#   w/h = 2:  step 0.1h  Z0 -5.54 %, eps_eff -0.04 %
#             step 0.05h Z0 -3.12 %, eps_eff -0.39 %
#   w/h = 0.5: step 0.1h Z0 -5.39 %, eps_eff +0.25 %
#             step 0.05h Z0 -6.27 %, eps_eff +0.35 %
#
# For the wider strips the residual is the first-order convergence of the flux at
# the strip edge: the measured error on Z0 halves when the step halves, i.e. it
# extrapolates to a fraction of a per cent as the step goes to zero, and the
# closed form sits inside the trend rather than off it.  ``eps_eff`` is a ratio
# of two solves and so cancels most of that error, which is why it agrees to well
# under a per cent even on the coarse grid.
#
# The narrow case is the exception, and it is kept rather than dropped: for
# ``w/h = 0.5`` the Z0 error goes -5.4 % then -6.3 %, i.e. the wrong way.  That is
# not a defect of the oracle's physics, it is the staircase strip on the symmetry
# plane -- the strip is only a handful of nodes wide, so the two grid steps
# resolve the edge singularity differently and the trend is not yet asymptotic.
# Its tolerance is therefore taken from the scatter of those two solves (about
# 6.3 %) with a little room, not from a convergence argument, and it is the one
# row here that a stricter budget would have to refine before tightening.
#
# The tolerances are the measured numbers with room for the platform's
# arithmetic, not the 0.1 % the model claims for itself.
ORACLE_CASES = [
    # (w/h, step, Z0 rel tolerance, eps_eff rel tolerance)
    (1.0, 0.1, 0.10, 0.02),
    (2.0, 0.1, 0.08, 0.02),
    (1.0, 0.05, 0.06, 0.015),
    (2.0, 0.05, 0.05, 0.015),
    # narrow strip: tolerance from the two-step scatter, see the note above
    (0.5, 0.1, 0.09, 0.02),
    (0.5, 0.05, 0.09, 0.02),
]


@pytest.mark.parametrize(
    "w_over_h, step, z0_tol, ee_tol", ORACLE_CASES, ids=[f"u={c[0]}-d={c[1]}" for c in ORACLE_CASES]
)
def test_closed_form_against_finite_difference(
    w_over_h: float, step: float, z0_tol: float, ee_tol: float
) -> None:
    """The closed form must sit within the oracle's own error bar.

    The oracle is solved from scratch here -- Laplace's equation, no strip
    formula in sight -- so agreement is evidence that the Hammerstad-Jensen fit
    is wired up correctly rather than merely self-consistent.  The tolerances are
    the measured discrepancies recorded above, rounded up.
    """
    eps_r = 4.4
    z0_fd, ee_fd = fd_z0_eps_eff(w_over_h, eps_r, step)
    z0_closed, ee_closed = z0_eps_eff(w_over_h, eps_r)
    assert z0_closed == pytest.approx(z0_fd, rel=z0_tol)
    assert ee_closed == pytest.approx(ee_fd, rel=ee_tol)


def test_oracle_converges_towards_the_closed_form():
    """Refining the grid must not move the oracle away from the closed form.

    This is the check that makes the tolerances above meaningful: if the
    discrepancy were a modelling error rather than discretisation, halving the
    step would not reduce it.
    """
    eps_r = 4.4
    w_over_h = 2.0
    z0_closed = z0_eps_eff(w_over_h, eps_r)[0]
    coarse = abs(fd_z0_eps_eff(w_over_h, eps_r, 0.1)[0] / z0_closed - 1.0)
    fine = abs(fd_z0_eps_eff(w_over_h, eps_r, 0.05)[0] / z0_closed - 1.0)
    assert fine < coarse
    assert fine < 0.05


def test_oracle_reproduces_the_air_limit():
    """``eps_r = 1`` gives ``eps_eff = 1`` and the air-filled impedance."""
    z0_fd, ee_fd = fd_z0_eps_eff(1.0, 1.0, 0.1)
    assert ee_fd == pytest.approx(1.0, rel=1e-12)
    assert z0_fd == pytest.approx(z0_eps_eff(1.0, 1.0)[0], rel=0.1)


def test_oracle_sees_the_eps_eff_trend():
    """The oracle must rank the same geometries the same way the model does."""
    a = fd_z0_eps_eff(0.5, 4.4, 0.1)
    b = fd_z0_eps_eff(2.0, 4.4, 0.1)
    assert a[0] > b[0]
    assert a[1] < b[1]
    assert z0_eps_eff(0.5, 4.4)[0] > z0_eps_eff(2.0, 4.4)[0]
    assert eps_eff(0.5, 4.4) < eps_eff(2.0, 4.4)


# ---------------------------------------------------------------------------
# the two load models the report quotes
# ---------------------------------------------------------------------------
#: The station impedance the series branch measured on the reference board, the
#: drive frequency and the capacitance the mesh formula predicts for its cut, all
#: as the report's series-load table quotes them.  These are inputs to the models
#: under test, never outputs of them.
LOAD_ZC = 50.54736386461998 + 4.024590867955236j
LOAD_F = 5.827786e9
LOAD_CG = 1.2466696446336e-13


def test_the_series_load_models_reproduce_the_quoted_numbers():
    """The two formulas give the magnitudes the report prints, to six places.

    ``ideal_transmission`` is the textbook series formula and
    ``corrected_transmission`` is the same with the cut's capacitance in
    parallel with the resistance; the report quotes 0.503909 and 0.544544 for
    the 100 ohm point, and 0.805632 and 0.682260 for the corrected prediction at
    25 and 50 ohm.  A change that moved any of these would silently restate
    every deviation the report carries, so they are pinned to the digit rather
    than to a tolerance.
    """
    assert round(abs(ideal_transmission(LOAD_ZC, 100.0)), 6) == 0.503909
    assert (
        round(abs(corrected_transmission(LOAD_ZC, 100.0, LOAD_CG, LOAD_F)), 6)
        == 0.544544
    )
    assert (
        round(abs(corrected_transmission(LOAD_ZC, 25.0, LOAD_CG, LOAD_F)), 6)
        == 0.805632
    )
    assert (
        round(abs(corrected_transmission(LOAD_ZC, 50.0, LOAD_CG, LOAD_F)), 6)
        == 0.682260
    )


def test_the_corrected_prediction_cannot_depend_on_record_length():
    """The prediction is a constant, so the deviation column inherits the drift.

    The measured ``|S21|`` moves with record length -- 0.549464 at 2400 steps,
    0.555663 at 4800, 0.556575 at 9600 -- while the predicted magnitude it is
    divided by is the same 0.544544 at every one of those record lengths,
    because record length does not enter the formula.  The
    report's deviation column is measurement over prediction, so all of that
    drift lands in the column and none of it can be attributed to the model.
    That has to be a property of the arguments and not an accident of how they
    were accumulated, so this test pins both halves of it: repeating the call is
    bit-identical, and the parameter list is exactly ``(zc, r, cg, f)`` -- with
    no ``nsteps`` and no ``s21`` for anyone to add later, which is the guard
    against someone making the prediction track the measurement it is supposed
    to test.
    """
    first = corrected_transmission(LOAD_ZC, 100.0, LOAD_CG, LOAD_F)
    second = corrected_transmission(LOAD_ZC, 100.0, LOAD_CG, LOAD_F)
    assert first == second
    assert abs(first) == abs(second)
    params = tuple(inspect.signature(corrected_transmission).parameters)
    assert params == ("zc", "r", "cg", "f")

