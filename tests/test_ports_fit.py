"""Tests for :func:`emfit.ports.fit_beta` -- fitting the propagation constant.

Nothing here runs the solver.  Every signal is a synthetic phasor this file
makes up from a known wavenumber, so a recovered value is compared against the
number that generated it and a failure means an algebra, sign or convention
error.
The second test deliberately spans several wavelengths: a two-wave split over a
fraction of a wavelength is ill-conditioned by construction (see the warning in
the docstring of ``fit_beta``), so it is not used as evidence either way.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.ports import fit_beta, fit_line


def test_fit_beta_recovers_a_single_travelling_wave() -> None:
    """A noiseless travelling wave on the probe stations returns its beta."""
    z = np.linspace(10.40e-3, 20.00e-3, 9)
    beta = 237.301
    v = 0.7j * np.exp(-1j * beta * z)

    fit = fit_beta(z, v, n_wave=1)

    assert fit.n_wave == 1
    assert fit.n_stations == z.size
    assert fit.span == pytest.approx(z[-1] - z[0])
    assert fit.backward == 0.0
    assert fit.gamma == 0.0
    assert abs(fit.beta - beta) / beta < 1e-9
    assert fit.residual < 1e-9
    assert abs(fit.forward - 0.7j) < 1e-9


def test_fit_beta_splits_two_counter_propagating_waves() -> None:
    """A known reflection coefficient is recovered; one wave cannot do it."""
    z = np.linspace(0.0, 40.0e-3, 12)
    beta = 237.301
    gamma = 0.12 * np.exp(1.1j)
    v = np.exp(-1j * beta * z) + gamma * np.exp(1j * beta * z)

    fit = fit_beta(z, v, n_wave=2)

    assert fit.n_wave == 2
    assert abs(fit.beta - beta) / beta < 1e-6
    assert abs(fit.gamma - gamma) / abs(gamma) < 1e-6
    assert fit.residual < 1e-6

    one = fit_beta(z, v, n_wave=1)
    assert one.residual > 1e-2


# ---------------------------------------------------------------------------
# fit_line: loss as well as phase
# ---------------------------------------------------------------------------
def _line_signal(z, alpha, beta, forward=0.7j, gamma=0.0):
    """Complex amplitude at stations ``z`` for a line of loss ``alpha``."""
    return (forward * np.exp(-(alpha + 1j * beta) * z)
            + forward * gamma * np.exp(+(alpha + 1j * beta) * z))


def test_fit_line_recovers_alpha_and_beta_together() -> None:
    """A lossy travelling wave returns both constants it was built from."""
    z = np.linspace(10.40e-3, 20.00e-3, 9)
    alpha, beta = 24.0, 237.301
    v = _line_signal(z, alpha, beta)

    fit = fit_line(z, v, n_wave=1)

    assert abs(fit.alpha - alpha) / alpha < 1e-9
    assert abs(fit.beta - beta) / beta < 1e-9
    assert abs(fit.forward - 0.7j) < 1e-9
    assert fit.residual < 1e-9
    assert fit.alpha_sigma / alpha < 1e-6
    # No loss and no phase are not the same equation: the fit must not let one
    # absorb the other, so the two must be very nearly uncorrelated here.
    assert abs(fit.rho) < 1e-6


def test_fit_line_with_zero_alpha_leaves_the_transmission_alone() -> None:
    """``alpha = 0`` reproduces the lossless amplitude ratio exactly."""
    z = np.linspace(10.40e-3, 20.00e-3, 9)
    beta = 237.301
    v = _line_signal(z, 0.0, beta)

    fit = fit_line(z, v, n_wave=1)

    assert fit.alpha == pytest.approx(0.0, abs=1e-9)
    assert np.exp(-fit.alpha * fit.span) == pytest.approx(1.0, abs=1e-12)


def test_fit_line_separates_alpha_from_beta_when_aliasing_is_a_risk() -> None:
    """The two parameters have different best-fit spacings; either must work.

    ``sin(beta d)`` and the exponential decay are nearly collinear when the
    stations span a tiny fraction of a wavelength, so the cases here bracket
    both extremes: a slow wave with heavy loss *and* the reverse.
    """
    z = np.linspace(0.0, 20.00e-3, 17)
    for alpha, beta in ((0.0, 2000.0), (300.0, 50.0), (5.0, 3000.0)):
        v = _line_signal(z, alpha, beta)
        fit = fit_line(z, v, n_wave=1)
        if alpha > 0.0:
            assert abs(fit.alpha - alpha) / alpha < 1e-8
        assert abs(fit.beta - beta) / beta < 1e-8


def test_fit_line_two_wave_recovery_and_covariance_shape() -> None:
    """Both waves recovered; the covariance is a real 2x2 for alpha and beta."""
    z = np.linspace(0.0, 40.0e-3, 12)
    alpha, beta = 12.0, 237.301
    gamma = 0.12 * np.exp(1.1j)
    v = _line_signal(z, alpha, beta, gamma=gamma)

    fit = fit_line(z, v, n_wave=2)

    assert fit.n_wave == 2
    assert abs(fit.beta - beta) / beta < 1e-5
    assert abs(fit.gamma - gamma) / abs(gamma) < 1e-5
    assert fit.covariance.shape == (2, 2)
    assert np.all(np.diag(fit.covariance) >= 0.0)
    assert fit.residual < 1e-6

