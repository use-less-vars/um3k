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

from emfit.ports import fit_beta


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
