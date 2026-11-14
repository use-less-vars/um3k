"""Contract tests for :class:`emfit.evolve.PointSource`.

The class is a thin, named wrapper over the soft-current slot of Ampere's law:
``__call__(t)`` returns the full-length edge current vector that
:meth:`FITStepper.run` subtracts from the curl, with a ramped cosine on one
edge and zeros everywhere else.  These tests pin the waveform (so a later
milestone can size settle / accumulate phases from :attr:`steps_per_period`
and :attr:`ramp_steps`), the index resolution, the ``dt`` default agreeing
with the stepper's, and one tiny smoke run proving the source actually injects
energy into a real 3-D time loop.
"""

import numpy as np
import pytest

from emfit.evolve import FITStepper, PointSource, cfl_dt
from emfit.grid import Grid
from emfit.materials import C0, material_matrices
from emfit.operators import CellComplex

H = 0.02                 # cell size, m
FREQ = 1.0e9             # drive frequency, Hz


def _cell_complex(n=6):
    grid = Grid.uniform(n, n, n, lx=n * H, ly=n * H, lz=n * H)
    return grid, CellComplex(grid)


# ----------------------------------------------------------------------
# 1. index resolution
# ----------------------------------------------------------------------
@pytest.mark.parametrize("component", ["ex", "ey", "ez"])
def test_index_is_the_cell_complex_edge_number(component):
    _, cc = _cell_complex()
    src = PointSource(cc, 2, 3, 4, component=component, frequency=FREQ)
    expected = int(getattr(cc, "idx_" + component)(2, 3, 4))
    assert src.index == expected
    assert isinstance(src.index, int)
    assert (src.component, src.i, src.j, src.k) == (component, 2, 3, 4)


def test_default_component_is_ez():
    _, cc = _cell_complex()
    src = PointSource(cc, 2, 3, 4, frequency=FREQ)
    assert src.component == "ez"
    assert src.index == int(cc.idx_ez(2, 3, 4))


def test_an_unknown_component_is_refused():
    _, cc = _cell_complex()
    with pytest.raises(ValueError, match="component"):
        PointSource(cc, 1, 1, 1, component="hx", frequency=FREQ)


# ----------------------------------------------------------------------
# 2. the vector spans every edge and drives exactly one of them
# ----------------------------------------------------------------------
def test_current_vector_spans_every_edge_and_touches_only_the_source():
    _, cc = _cell_complex()
    src = PointSource(cc, 2, 3, 4, frequency=FREQ, amplitude=3.0)
    j = src(2.0 * src.t_ramp)                       # well past the ramp

    assert j.shape == (cc.n_edges,)
    assert j.size == cc.n_ex + cc.n_ey + cc.n_ez
    nonzero = np.flatnonzero(j)
    assert nonzero.tolist() == [src.index]
    assert j[src.index] != 0.0


# ----------------------------------------------------------------------
# 3./4./5. the waveform
# ----------------------------------------------------------------------
def test_value_is_exactly_zero_at_t_zero():
    _, cc = _cell_complex()
    src = PointSource(cc, 2, 3, 4, frequency=FREQ, amplitude=1.0)
    assert src(0.0)[src.index] == 0.0


@pytest.mark.parametrize("phase", [0.0, 0.3, 1.0])
def test_envelope_is_unity_after_the_ramp(phase):
    _, cc = _cell_complex()
    amp = 2.5
    src = PointSource(cc, 2, 3, 4, frequency=FREQ, amplitude=amp, phase=phase)
    for t in (src.t_ramp, 1.5 * src.t_ramp, 7.25 / FREQ):
        got = float(src(t)[src.index])
        want = amp * np.cos(2.0 * np.pi * FREQ * t + phase)
        assert abs(got - want) < 1e-12, (t, got, want)


def test_mid_ramp_matches_the_raised_cosine():
    _, cc = _cell_complex()
    amp = 1.7
    phase = 0.4
    src = PointSource(cc, 2, 3, 4, frequency=FREQ, amplitude=amp,
                      phase=phase)
    for frac in (0.1, 0.25, 0.5, 0.75, 0.99):
        t = frac * src.t_ramp
        ramp = 0.5 * (1.0 - np.cos(np.pi * t / src.t_ramp))
        got = float(src(t)[src.index])
        want = amp * ramp * np.cos(2.0 * np.pi * FREQ * t + phase)
        assert abs(got - want) < 1e-12, (t, got, want)


def test_t_ramp_defaults_to_four_periods():
    _, cc = _cell_complex()
    src = PointSource(cc, 2, 3, 4, frequency=FREQ)
    assert abs(src.t_ramp - 4.0 / FREQ) < 1e-18


# ----------------------------------------------------------------------
# 6. the returned buffer is reused, exactly as RickerSource does
# ----------------------------------------------------------------------
def test_the_returned_buffer_is_reused_and_overwritten():
    _, cc = _cell_complex()
    src = PointSource(cc, 2, 3, 4, frequency=FREQ)
    first = src(0.5 * src.t_ramp)
    stale = first[src.index]
    second = src(2.0 * src.t_ramp)
    assert second is first                # same object, not a copy
    assert second[src.index] != stale     # the stale read is now garbage
    assert np.flatnonzero(second).tolist() == [src.index]


# ----------------------------------------------------------------------
# 7. dt default and the CFL guard, plus frequency validation
# ----------------------------------------------------------------------
def test_dt_defaults_to_the_courant_limit_of_the_grid():
    grid, cc = _cell_complex()
    src = PointSource(cc, 2, 3, 4, frequency=FREQ)
    assert src.dt == cfl_dt(grid)


def test_a_time_step_above_the_courant_limit_is_refused():
    grid, cc = _cell_complex()
    dt_max = cfl_dt(grid)
    with pytest.raises(ValueError, match="Courant"):
        PointSource(cc, 2, 3, 4, frequency=FREQ, dt=2.0 * dt_max)
    # ... and the limit itself is accepted (the guard is one-sided).
    src = PointSource(cc, 2, 3, 4, frequency=FREQ, dt=dt_max)
    assert src.dt == dt_max


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_a_non_positive_or_non_finite_frequency_is_refused(bad):
    _, cc = _cell_complex()
    with pytest.raises(ValueError, match="frequency"):
        PointSource(cc, 2, 3, 4, frequency=bad)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_non_finite_amplitude_is_refused(bad):
    _, cc = _cell_complex()
    with pytest.raises(ValueError, match="amplitude"):
        PointSource(cc, 2, 3, 4, frequency=FREQ, amplitude=bad)


@pytest.mark.parametrize("bad", [0.0, -1e-12, float("nan")])
def test_an_invalid_explicit_dt_is_refused(bad):
    _, cc = _cell_complex()
    with pytest.raises(ValueError, match="dt="):
        PointSource(cc, 2, 3, 4, frequency=FREQ, dt=bad)


# ----------------------------------------------------------------------
# 8. the step counters a later milestone sizes its phases from
# ----------------------------------------------------------------------
def test_step_counters_are_ints_and_agree_with_the_waveform():
    _, cc = _cell_complex()
    src = PointSource(cc, 2, 3, 4, frequency=FREQ)
    assert isinstance(src.steps_per_period, int)
    assert isinstance(src.ramp_steps, int)
    # An integer step count cannot land on the period exactly (26 steps here
    # for 26.2252 steps per period), so the honest guarantee -- and the one a
    # caller sizing a settle phase relies on -- is rounding to the nearest
    # step, i.e. at most half a step of error.
    assert abs(src.steps_per_period - 1.0 / (FREQ * src.dt)) <= 0.5
    assert abs(src.steps_per_period * FREQ * src.dt - 1.0) <= 0.5 * FREQ * src.dt
    assert abs(src.ramp_steps * src.dt - src.t_ramp) <= 0.5 * src.dt


# ----------------------------------------------------------------------
# 9. smoke: a real 3-D leapfrog run is driven by the source
# ----------------------------------------------------------------------
def test_source_injects_energy_into_a_real_run():
    """Catch a source wired to the wrong vector length or the wrong slot.

    16 cells per wavelength, one cubic wavelength of vacuum, 150 steps
    (about five periods, the last one past the four-period ramp).  Nothing
    is asserted about amplitude or power -- only that the loop stays finite
    and that the source put energy in.
    """
    lam = C0 / FREQ
    h = lam / 16.0
    n = 16
    grid = Grid.uniform(n, n, n, lx=n * h, ly=n * h, lz=n * h)
    cc = CellComplex(grid)

    m_eps, m_mu = material_matrices(grid, cc)
    stepper = FITStepper(cc, m_eps, m_mu)          # dt = cfl_dt(grid)
    src = PointSource(cc, n // 2, n // 2, n // 2, frequency=FREQ)
    assert src.dt == stepper.dt

    stepper.run(150, source=src)
    print(f"\n[point_source_smoke] energy = {stepper.energy():.6e} J, "
          f"steps_per_period = {src.steps_per_period}, "
          f"ramp_steps = {src.ramp_steps}")

    assert np.isfinite(stepper.e).all()
    assert np.isfinite(stepper.h).all()
    assert stepper.energy() > 0.0
