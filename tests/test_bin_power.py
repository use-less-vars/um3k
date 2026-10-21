"""What a bin's power-normalised ``|S21|`` sees that the amplitude one cannot.

A lossless forward wave that steps in impedance carries the same power on both
sides of the step but neither the same voltage nor the same current.  The bin
row's ``s21`` divides by one assumed ``zc`` for the whole span, so a step shows
up there as a small export/import of power; the power row divides each station
by nothing at all, and the step cancels exactly.

The numbers below are the ones the current code produces for that wave -- not
tidy ideals.  ``OLD_S21`` is 1.000572, i.e. 0.06 %: the single-``zc`` formula
is almost blind to a step, which is why this test pins the power row (exact)
and only pins the *direction* of the old one.
"""

import numpy as np

import emfit.studies as S

#: Lossless, flux-conserving forward wave with the impedance stepped by 1.07.
_Z0_FIRST = 50.0
_Z0_LAST = _Z0_FIRST / 1.07
_BETA = 120.0
_X = np.array([0.0, 0.02])
_POWER = 1.0


def _station(z0):
    """Voltage and current of a ``_POWER``-watt forward wave on ``z0``."""
    current = np.sqrt(2.0 * _POWER / z0)
    return z0 * current, current


def test_power_passivity_is_one_across_an_impedance_step():
    first, last = _station(_Z0_FIRST), _station(_Z0_LAST)
    p_first = S._station_power(first[0], first[1])
    p_last = S._station_power(last[0], last[1])

    assert p_first == p_last, "a pure impedance step must not move the power"
    s21_power = float(np.sqrt(p_last / p_first))
    assert s21_power == 1.0


def test_amplitude_s21_is_blind_to_the_step_but_not_exact():
    first, last = _station(_Z0_FIRST), _station(_Z0_LAST)
    a1, a2 = S.forward_wave_amplitude(
        np.array([first[0], last[0]]), np.array([first[1], last[1]]),
        _X, 0j, complex(_Z0_FIRST), indices=[0, -1])
    old = float(abs(S.line_s21(a1, float(_X[0]), a2, float(_X[-1]), _BETA)[0]))

    assert old > 1.0, "the single-zc formula reads the step as a small gain"
    assert abs(old - 1.0) < 1e-2, (
        "the old row moves by thousandths, not by the 7 % the step suggests")
