"""Tests for :mod:`emfit.nearfield`: time to frequency, contour to far field.

The chain from the FDTD state to a scattering width has three links, and each is
tested on its own before the whole of it is tested once against Mie:

* :class:`emfit.nearfield.DFTAccumulator` against the closed form of a window
  that holds an integer number of periods, to 1e-10 relative;
* :func:`emfit.nearfield.kirchhoff_amplitude` against an exact known far field,
  the ``(j/4) H0^(2)(k R)`` point source: its amplitude is a circle of radius
  ``(1/4) sqrt(2/(pi k))`` and its phase a ramp of slope ``k``;
* :func:`emfit.nearfield.run_rcs` against :mod:`emfit.mie`, once.

Only the last test integrates anything, and it is a single run pair at
``ka = 3``, ``ppw = 12``: 0.38 s, 289 steps, contour 2.16 x 2.16 wavelengths.
Measured there, ``sigma_2d`` is 5.822 m forward and 1.720 m back against Mie's
9.756 m and 1.569 m, that is -2.24 dB and +0.40 dB; the worst of the five
angles the default call reports is 90 deg at -3.56 dB.  The 6 dB tolerance is
sized against that worst angle, not against the two the test asserts, so the
test keeps a margin while still failing if the far-field normalisation or the
phase convention drifts.

The two analytic tests are resolution limited, not model limited.  The
calibration gate at ``ppw = 20`` measures a modulus 0.7 per cent below
``(1/4) sqrt(2/(pi k))`` with 0.11 dB of ripple, both of which are the second
order ``(k h)^2`` quadrature error of the contour rule and nothing else; the
phase slopes come out within 0.1 per cent of ``k x0`` and ``k y0``.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.special import hankel2

from emfit import nearfield
from emfit.grid import Grid
from emfit.operators import CellComplex

#: Expensive results, computed at most once per module.
_CACHE: dict = {}


class _FakeStepper:
    """The two attributes :class:`nearfield.DFTAccumulator` reads from a stepper.

    A real stepper holds the whole Yee state; the accumulator only ever looks at
    ``dt`` and at the ``Ez`` slots of ``e``, so a scalar field is enough to test
    it and keeps the test a pure numpy exercise.
    """

    def __init__(self, cc: CellComplex, dt: float) -> None:
        self.cc = cc
        self.dt = float(dt)
        self.e = np.zeros(cc.n_edges, dtype=float)

    def put(self, value: float) -> None:
        """Write one ``Ez`` value to every node of the grid."""
        self.e[self.cc.off_ez:self.cc.off_ez + self.cc.n_ez] = float(value)


def _point_source(ppw: int, offset) -> tuple:
    """Analytic cylindrical wave on a uniform grid, with a 1-wavelength contour.

    Returns ``(cc, u, k, contour, reference)``.  The source sits ``offset``
    wavelengths away from the contour centre, which is what turns the phase
    check into a test of the ``exp(j k s . r')`` factor rather than of a
    constant.
    """
    lam = nearfield.LAM0
    k = 2.0 * np.pi / lam
    h = lam / ppw
    n_half = ppw + 4
    n = 2 * n_half
    grid = Grid.uniform(n, n, 1, n * h, n * h, h)
    cc = CellComplex(grid)
    x = np.asarray(grid.x, dtype=float)
    y = np.asarray(grid.y, dtype=float)
    x_ref = 0.5 * (x[0] + x[-1])
    y_ref = 0.5 * (y[0] + y[-1])
    x_src = x_ref + float(offset[0]) * lam
    y_src = y_ref + float(offset[1]) * lam
    radius = np.hypot(x[:, None] - x_src, y[None, :] - y_src)
    u = 0.25j * hankel2(0, k * radius)
    contour = nearfield.rectangle_contour(cc, n_half - ppw, n_half + ppw,
                                          n_half - ppw, n_half + ppw)
    return cc, u, k, contour, (x_ref, y_ref)


@pytest.fixture(scope="module")
def calibration() -> dict:
    """The point-source flatness gate at ``ppw = 20``, evaluated once."""
    if "calibration" not in _CACHE:
        _CACHE["calibration"] = nearfield.flatness_gate(
            ppw=20, tol_abs=0.02, tol_ripple_db=0.2)
    return _CACHE["calibration"]


@pytest.fixture(scope="module")
def rcs() -> nearfield.RCSResult:
    """One real measurement, at the resolution the module is meant for."""
    if "rcs" not in _CACHE:
        _CACHE["rcs"] = nearfield.run_rcs(
            ka=3.0, ppw=12, phis_deg=np.array([0.0, 180.0]))
    return _CACHE["rcs"]


# ---------------------------------------------------------------------------
# (a) time to frequency
# ---------------------------------------------------------------------------
def test_accumulator_reproduces_the_closed_form_phasor() -> None:
    """An integer number of periods gives exactly ``A T/2 exp(j phi)``.

    The rectangle sum of ``A cos(w t + phi) exp(-j w t)`` over whole periods is
    the continuous-time answer with no quadrature error at all, so this pins the
    ``dt``, the ``-j`` sign and the ``1/2`` of ``Re{u e^{j w t}}``.  Two
    frequencies are accumulated at once and both are checked, which also covers
    the broadcasting over the frequency axis.  Both are below the Nyquist
    frequency ``1/(2 dt)``: above it a tone aliases exactly onto a lower one on
    a window of whole periods, which would look like a failure of the
    accumulator.
    """
    lam = nearfield.LAM0
    h = lam / 20.0
    grid = Grid.uniform(4, 4, 1, 4.0 * h, 4.0 * h, h)
    cc = CellComplex(grid)

    dt = 2.0e-11
    n_steps = 64
    freqs = np.array([1.0 / (8.0 * dt), 3.0 / (8.0 * dt)])
    amplitudes = np.array([1.0, 0.25])
    phases = np.array([0.7, -2.1])

    stepper = _FakeStepper(cc, dt)
    accumulator = nearfield.DFTAccumulator(cc, freqs)
    for n in range(n_steps):
        t = n * dt
        stepper.put(np.sum(amplitudes * np.cos(2.0 * np.pi * freqs * t + phases)))
        accumulator(t, stepper)

    expected = 0.5 * n_steps * dt * amplitudes * np.exp(1j * phases)
    assert accumulator.n_samples == n_steps
    assert accumulator.phasors.shape == (freqs.size, cc.nxn, cc.nyn)
    assert np.allclose(accumulator.phasors[:, 3, 2], expected,
                       rtol=1e-10, atol=0.0)


# ---------------------------------------------------------------------------
# (b) contour to far field: modulus and phase of a known exact pattern
# ---------------------------------------------------------------------------
def test_point_source_amplitude_is_flat_and_correctly_normalised(
        calibration: dict) -> None:
    """The recovered modulus is a circle of radius ``(1/4) sqrt(2/(pi k))``.

    The contour representation is an identity, not an approximation, so a point
    source must come back as a pattern that does not depend on ``phi`` and whose
    absolute level is the analytic one.  Anything wrong with the normalisation
    of the integral, of the Green's function or of the ``n . s`` term shows up
    here as a wrong level or as ripple.
    """
    analytic = 0.25 * np.sqrt(2.0 / (np.pi * calibration["k"]))
    assert calibration["analytic_abs"] == pytest.approx(analytic, rel=1e-12)
    assert calibration["passed"]

    assert len(calibration["rows"]) == 3
    for row in calibration["rows"]:
        assert row["mean_abs"] / analytic == pytest.approx(1.0, abs=0.02)
        # 0.2 dB peak to peak is a 2.3 per cent spread of the modulus.
        assert row["ripple_db"] <= 0.2


def test_point_source_phase_ramp_has_the_right_slopes() -> None:
    """Fitting ``c0 + cx cos phi + cy sin phi`` to the phase gives ``k x0, k y0``.

    ``(x0, y0)`` is the source offset from the phase reference, so the two
    slopes must be ``k x0`` and ``k y0`` with their signs.  This is the test
    that catches an ``exp(+j k s . r')`` where the module needs
    ``exp(-j k s . r')``: a flipped sign on the exponential flips both slopes,
    and nothing else in the suite looks at the sign of the far-field phase.
    """
    offset = (0.3, -0.2)
    cc, u, k, contour, reference = _point_source(20, offset)
    phis = np.linspace(0.0, 2.0 * np.pi, 24, endpoint=False)
    amplitude = nearfield.kirchhoff_amplitude(
        cc, contour, u, k, phis, reference=reference)

    phase = np.unwrap(np.angle(amplitude))
    basis = np.column_stack([np.ones_like(phis), np.cos(phis), np.sin(phis)])
    (c0, cx, cy), *_ = np.linalg.lstsq(basis, phase, rcond=None)

    lam = 2.0 * np.pi / k
    assert cx / (k * offset[0] * lam) == pytest.approx(1.0, abs=0.01)
    assert cy / (k * offset[1] * lam) == pytest.approx(1.0, abs=0.01)
    # The model has to be the whole story, not merely the right slope.
    assert np.max(np.abs(phase - basis @ (c0, cx, cy))) < 0.02


# ---------------------------------------------------------------------------
# (c) degenerate input
# ---------------------------------------------------------------------------
def test_zero_phasor_gives_exactly_zero_amplitude_and_width() -> None:
    """No field means no number: ``a == 0.0`` and ``sigma == 0.0``, exactly.

    No tolerance anywhere.  The integral is linear, so a zero phasor has to give
    a bitwise zero, and a bitwise zero has to survive the normalisation by the
    incident phasor; a stray offset in the quadrature or in the derivative would
    show up as a non-zero floor here long before it mattered in a pattern.
    """
    cc, u, k, contour, reference = _point_source(8, (0.0, 0.0))
    zero = np.zeros_like(u)
    amplitude = nearfield.kirchhoff_amplitude(
        cc, contour, zero, k, (0.0, 1.0), reference=reference)
    assert np.all(amplitude == 0.0)

    sigma = nearfield.scattering_width(amplitude, 1.0 - 0.5j)
    assert np.all(sigma == 0.0)


# ---------------------------------------------------------------------------
# (d) the whole measurement, once
# ---------------------------------------------------------------------------
def test_scattering_width_beats_the_mirror_and_tracks_mie(
        rcs: nearfield.RCSResult) -> None:
    """Forward scattering exceeds back scattering, and both are near Mie.

    A ``ka = 3`` PEC cylinder is forward scattering, so ``sigma(0) > sigma(180)``
    is a statement about the geometry and about the phase convention together: a
    conjugated far field mirrors the pattern, and this is the assertion that
    notices.  The 6 dB band around Mie is a regression band, not a claim of
    accuracy; measured at this resolution the two angles are 2.2 dB and 0.4 dB
    away.
    """
    sigma = np.asarray(rcs.sigma_2d, dtype=float)
    assert list(np.asarray(rcs.phi_deg, dtype=float)) == [0.0, 180.0]
    assert np.all(np.isfinite(sigma))
    assert np.all(sigma > 0.0)

    forward, back = sigma[0], sigma[1]
    assert forward > back

    diff_db = np.asarray(rcs.db_diff, dtype=float)
    assert np.all(np.abs(diff_db) <= 6.0)

    assert np.all(np.isfinite(np.asarray(rcs.sigma_mie, dtype=float)))
    assert abs(rcs.incidence) > 0.0
