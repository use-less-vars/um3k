"""Tests for :mod:`emfit.ports` -- the analytic primitives of a wave port.

Nothing here runs the solver.  Every number is either arithmetic this file makes
up (a tone of known amplitude, a wave of known phase) or a value worked out by
hand from ``e[k] = k``, so a failure means an algebra or convention error, never
a badly conditioned run.  The groups are: probe voltages (a line integral over
edge unknowns), the running DFT that turns probe samples into phasors, the
two-probe split that turns phasors into travelling waves and S-parameters, the
station fit that turns several stations into a line impedance with its
uncertainty, the plane shift that re-quotes a wave where it is wanted and the
power-current check that licenses calling a ``V / I`` an impedance at all, and
the Touchstone writer/reader that carries the S-matrix between runs.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

from emfit.grid import Grid
from emfit.operators import CellComplex
from emfit.ports import (
    DftAccumulator,
    LumpedPort,
    Probe,
    deembed_reflection,
    deembed_transmission,
    edge_path_voltage,
    fit_station_impedance,
    plate_current,
    power_current_check,
    probe_voltage,
    read_touchstone,
    reflection,
    sigma_beta_from_curvature,
    suggest_probe_spacing,
    transmission,
    travelling_waves,
    write_touchstone,
)

#: Record used by the DFT tests: 256 samples at 1 ps, so bin ``k`` sits at
#: ``k / 256 ps`` = 3.90625 GHz * k and every expectation is a closed form.
N_STEPS = 256
DT = 1.0e-12
BIN = 8
F_BIN = BIN / (N_STEPS * DT)


def _run(acc: DftAccumulator, x) -> DftAccumulator:
    """Feed ``x`` (one scalar per step) into ``acc`` and return it."""
    for n, value in enumerate(np.atleast_1d(x)):
        acc.add([value], n)
    return acc


# ---------------------------------------------------------------------------
# probe voltages
# ---------------------------------------------------------------------------
def test_edge_path_voltage_signs_and_orientation():
    """A path integral is a signed sum, so reversing the path flips the sign."""
    e = np.arange(10.0)  # e[k] == k, so every expected value is hand-checkable
    assert edge_path_voltage(e, [3, 4, 5]) == 12.0
    assert edge_path_voltage(e, [3, 4, 5], [1, 1, -1]) == 2.0
    # the same path walked backwards: same edges, every sign reversed
    assert edge_path_voltage(e, [5, 4, 3], [-1, -1, -1]) == -12.0
    assert edge_path_voltage(e, [], []) == 0.0

    # a probe is that same sum; a port is a probe across the feed gap, so the
    # three names must agree to the last bit
    probe = Probe("gap", [1, 2, 1], [1, 1, -1])
    assert probe.voltage(e) == 2.0
    assert probe(e) == 2.0
    assert probe_voltage(e, probe) == 2.0

    port = LumpedPort("p1", [2, 3])
    assert port.voltage(e) == 5.0
    assert port.z0 == 50.0
    gap = port.probe
    assert np.array_equal(gap.edges, [2, 3])
    assert np.all(gap.signs == 1.0)
    assert gap.voltage(e) == port.voltage(e)


def test_probe_and_lumped_port_reject_malformed_paths():
    """Sign and index mistakes are refused where made, not silently summed."""
    with pytest.raises(ValueError):
        Probe("short", [1, 2, 3], [1, 1])  # one sign too few
    with pytest.raises(ValueError):
        Probe("fractional", [1, 2.5], [1, 1])  # an edge index that is not one
    with pytest.raises(ValueError):
        Probe("zero", [1, 2], [1, 0])  # 0 is neither along nor against
    with pytest.raises(ValueError):
        Probe("empty", [], [])
    with pytest.raises(ValueError):
        LumpedPort("bad-z0", [1, 2], z0=0.0)
    with pytest.raises(ValueError):
        LumpedPort("negative-z0", [1, 2], z0=-50.0)
    with pytest.raises(ValueError):
        edge_path_voltage(np.zeros(4), [1, 2], [1, 1, 1])

    # a whole-number float index is unambiguous, so it is accepted
    assert np.array_equal(Probe("ok", [1.0, 2.0], [1, 1]).edges, [1, 2])


# ---------------------------------------------------------------------------
# time to frequency
# ---------------------------------------------------------------------------
def test_dft_exact_bin_recovers_amplitude_and_phase():
    """An on-bin tone comes back as ``A exp(j phi) N / 2``: no dt, no 2x."""
    amp, phi = 2.0, 0.3
    n = np.arange(N_STEPS)
    theta = 2.0 * np.pi * F_BIN * n * DT  # exactly BIN whole cycles
    acc = _run(DftAccumulator([F_BIN, 2.0 * F_BIN, 3.0 * F_BIN], DT),
               amp * np.cos(theta + phi))

    s = acc.spectrum
    assert s.shape == (3, 1)
    assert acc.n_samples == N_STEPS
    assert abs(s[0, 0] - amp * np.exp(1j * phi) * N_STEPS / 2.0) < 1e-9
    assert np.isclose(2.0 * abs(s[0, 0]) / N_STEPS, amp)  # amplitude in volts
    assert abs(np.angle(s[0, 0]) - phi) < 1e-12  # phase in radians
    # harmonics of an on-bin tone stay empty: nothing leaks off the bin
    assert abs(s[1, 0]) < 1e-9
    assert abs(s[2, 0]) < 1e-9

    # exp(-2j pi f n dt) sends sine to -j A N/2, not +j.  Getting that sign
    # backwards would invert the phase of every S-parameter built on top.
    sine = _run(DftAccumulator([F_BIN], DT), amp * np.sin(theta))
    s_sin = sine.spectrum[0, 0]
    assert abs(s_sin - (-1j) * amp * N_STEPS / 2.0) < 1e-9
    assert np.imag(s_sin) < 0.0

    # the Hann taper itself: a constant signal accumulates to sum(weights)
    weights = 0.5 - 0.5 * np.cos(2.0 * np.pi * n / (N_STEPS - 1))
    hann = _run(DftAccumulator([0.0], DT, window="hann", n_steps=N_STEPS),
                np.ones(N_STEPS))
    assert abs(hann.spectrum[0, 0] - np.sum(weights)) < 1e-12
    # ... and an explicit weight array is the same thing
    explicit = _run(DftAccumulator([0.0], DT, window=weights), np.ones(N_STEPS))
    assert abs(explicit.spectrum[0, 0] - np.sum(weights)) < 1e-12
    with pytest.raises(ValueError):
        DftAccumulator([F_BIN], DT, window="hann")  # taper width unknown


def test_dft_off_bin_tone_leaks_by_two_over_pi():
    """Half a bin off and the record cannot tell: 2/pi of the amplitude survives.

    Expected leakage, not a bug: the record is finite, so the tone's image at
    ``-(BIN + 1/2)`` folds into the bin.  Working the geometric sums out,
    ``|S| = A N / pi`` up to that 1/16.5 image term, i.e. ``2A/pi = 0.6366 A``.
    """
    amp = 2.0
    n = np.arange(N_STEPS)
    off_bin = F_BIN + 0.5 / (N_STEPS * DT)
    acc = _run(DftAccumulator([F_BIN], DT),
               amp * np.cos(2.0 * np.pi * off_bin * n * DT))
    recovered = 2.0 * abs(acc.spectrum[0, 0]) / N_STEPS
    assert np.isclose(recovered, 2.0 * amp / np.pi, rtol=0.05)
    assert recovered < 0.7 * amp  # the amplitude really is lost, not shifted


def test_dft_is_linear_and_keeps_its_bookkeeping():
    """Two signals at once == the two one at a time, added."""
    x = np.random.default_rng(20240517).standard_normal((N_STEPS, 2))
    freqs = [F_BIN, 2.0 * F_BIN]
    both = DftAccumulator(freqs, DT)
    first = DftAccumulator(freqs, DT)
    second = DftAccumulator(freqs, DT)
    for i in range(N_STEPS):
        both.add(x[i], i)
        first.add(x[i, :1], i)
        second.add(x[i, 1:], i)

    assert both.spectrum.shape == (2, 2)
    assert first.spectrum.shape == (2, 1)
    assert both.n_samples == N_STEPS
    assert np.allclose(both.spectrum,
                       np.hstack([first.spectrum, second.spectrum]),
                       rtol=0, atol=1e-10)

    both.reset()
    assert both.n_samples == 0
    assert both.spectrum.size == 0  # nothing accumulated since the reset


def test_dft_rejects_inconsistent_signal_count():
    acc = DftAccumulator([F_BIN], DT)
    acc.add([1.0, 2.0], 0)
    with pytest.raises(ValueError):
        acc.add([1.0, 2.0, 3.0], 1)  # this accumulator holds two signals
    with pytest.raises(ValueError):
        acc.add([], 1)  # no signals at all


# ---------------------------------------------------------------------------
# travelling waves
# ---------------------------------------------------------------------------
def test_travelling_waves_round_trip():
    """The split inverts the two-probe equations it is derived from."""
    beta, d = 100.0, 1.0e-3  # beta*d = 0.1 rad, well away from the nulls
    x = beta * d
    v_plus, v_minus = 1.0 + 0.2j, -0.35 + 0.1j
    v1 = v_plus + v_minus
    v2 = v_plus * np.exp(-1j * x) + v_minus * np.exp(+1j * x)

    p, m = travelling_waves(v1, v2, d, beta)
    assert abs(p - v_plus) < 1e-12
    assert abs(m - v_minus) < 1e-12

    # a frequency sweep broadcasts: probe 1 is a single number, probe 2 lags
    betas = np.array([50.0, 75.0, 100.0])
    xs = betas * d
    v2s = v_plus * np.exp(-1j * xs) + v_minus * np.exp(+1j * xs)
    ps, ms = travelling_waves(np.full(3, v1, dtype=complex), v2s, d, betas)
    assert ps.shape == (3,)
    assert np.allclose(ps, v_plus, rtol=0, atol=1e-12)
    assert np.allclose(ms, v_minus, rtol=0, atol=1e-12)


def test_matched_line_has_no_reflection():
    """A forward wave alone: nothing comes back, so S11 vanishes."""
    beta, d = 250.0, 1.0e-3  # beta*d = 0.25 rad
    x = beta * d
    v_plus = 0.8 - 0.3j
    v1, v2 = v_plus, v_plus * np.exp(-1j * x)

    p, m = travelling_waves(v1, v2, d, beta)
    assert abs(p - v_plus) < 1e-12
    assert abs(m) < 1e-15 * abs(v_plus)
    assert abs(reflection(p, m)) < 1e-12


def test_standing_wave_has_unit_reflection():
    """Equal forward and backward waves: total reflection, zero phase."""
    beta, d = 300.0, 1.0e-3  # beta*d = 0.3 rad
    x = beta * d
    v_plus = 0.5 + 0.5j
    v1 = 2.0 * v_plus  # the probes sit on a standing wave
    v2 = v_plus * (np.exp(-1j * x) + np.exp(+1j * x))  # = 2 v cos(beta d)

    p, m = travelling_waves(v1, v2, d, beta)
    assert abs(p - v_plus) < 1e-12
    s11 = reflection(p, m)
    assert abs(abs(s11) - 1.0) < 1e-12
    assert abs(s11 - 1.0) < 1e-12


def test_travelling_waves_refuses_half_wavelength_spacing():
    """Probes a half wavelength apart see one equation twice -- refuse, not noise."""
    with pytest.raises(ValueError):
        travelling_waves(1.0, 1.0, np.pi, 1.0)  # beta*d == pi exactly
    with pytest.raises(ValueError):
        travelling_waves(1.0, 1.0, np.pi + 1e-13, 1.0)  # inside the tolerance

    # one part in 1e6 away it is merely ill-conditioned, not degenerate
    v_plus, v_minus, x = 1.0 + 0j, 0.2 - 0.1j, np.pi + 1e-6
    v1 = v_plus + v_minus
    v2 = v_plus * np.exp(-1j * x) + v_minus * np.exp(+1j * x)
    p, m = travelling_waves(v1, v2, 1.0, np.pi + 1e-6)
    assert np.isfinite(p) and np.isfinite(m)
    assert abs(p - v_plus) < 1e-6  # ~1e-10 in practice; the split is amplifying

    # the helper puts the spacing at a quarter of pi at beta_max
    beta_max = np.pi / 1.0e-3
    spacing = suggest_probe_spacing(beta_max)
    assert np.isclose(spacing * beta_max, 0.25 * np.pi)
    assert np.isfinite(travelling_waves(v1, v2, spacing, beta_max)[0])
    with pytest.raises(ValueError):
        suggest_probe_spacing(0.0)


def test_reflection_needs_a_forward_wave():
    """No forward wave means no reflection coefficient -- not an inf."""
    with pytest.raises(ValueError):
        reflection(0.0, 1.0)
    with pytest.raises(ValueError):
        reflection(np.array([1.0, 0.0]), np.array([0.1, 0.2]))
    assert np.isclose(reflection(2.0 + 0j, 1.0 - 1j), 0.5 - 0.5j)


def test_transmission_deembeds_the_propagation_phase():
    """S21 is the forward-wave ratio with ``exp(-j beta d)`` taken back out."""
    d, beta = 1.0e-3, 700.0  # beta*d = 0.7 rad
    x = beta * d
    v_from = 1.0 + 0j

    # lossless matched line: the far probe sees only the phase
    assert abs(transmission(v_from, v_from * np.exp(-1j * x), d, beta)
               - 1.0) < 1e-12
    # a device that halves the wave: 0.5 exp(-j beta d) measured, 0.5 reported
    v_to = 0.5 * v_from * np.exp(-1j * x)
    assert abs(transmission(v_from, v_to, d, beta) - 0.5) < 1e-12
    # zero separation leaves the ratio alone
    assert abs(transmission(v_from, 0.5 * v_from, 0.0, beta) - 0.5) < 1e-12
    # the de-embedding multiplies by exp(+j beta d): it is not its own inverse
    assert abs(transmission(v_from, v_from, d, beta) - np.exp(1j * x)) < 1e-12
    with pytest.raises(ValueError):
        transmission(0.0, 1.0, d, beta)


# ---------------------------------------------------------------------------
# Touchstone
# ---------------------------------------------------------------------------
def test_touchstone_two_port_round_trip(tmp_path):
    """What is written comes back, in Hz and with the option line spelled out."""
    freqs = np.array([1.0e9, 2.5e9, 4.0e9])
    rng = np.random.default_rng(7)
    s = (rng.standard_normal((3, 2, 2))
         + 1j * rng.standard_normal((3, 2, 2)))

    text = io.StringIO()
    write_touchstone(text, freqs, s)
    lines = text.getvalue().splitlines()
    assert lines[0] == "# HZ S RI R 50"
    assert len(lines) == 1 + freqs.size

    # and through a path, which is how a run writes it
    path = tmp_path / "line.s2p"
    write_touchstone(path, freqs, s)
    f2, s2 = read_touchstone(path)
    assert s2.shape == (3, 2, 2)
    assert np.allclose(f2, freqs, rtol=1e-12, atol=0.0)  # 12 significant digits
    assert np.allclose(s2, s, rtol=0, atol=1e-10)

    f3, s3 = read_touchstone(io.StringIO(text.getvalue()))
    assert np.array_equal(f3, freqs)
    assert np.allclose(s3, s, rtol=0, atol=1e-10)


def test_touchstone_port_order_is_input_slowest():
    """Rows are S11 S21 S12 S22: the input port is the slow index.

    An asymmetric network makes a transposed write fail here rather than in a
    study, where it would look like an unstable device.
    """
    freqs = np.array([1.0e9, 3.0e9])
    s11 = np.array([0.1 + 0.2j, 0.3 - 0.4j])
    s21 = np.array([0.5 + 0.6j, 0.7 - 0.8j])
    s12 = np.array([-0.9 + 0.1j, -0.2 + 0.3j])
    s22 = np.array([0.4 + 0.5j, 0.6 + 0.7j])
    s = np.empty((2, 2, 2), dtype=complex)  # s[f, out, in]
    s[:, 0, 0], s[:, 1, 0], s[:, 0, 1], s[:, 1, 1] = s11, s21, s12, s22

    text = io.StringIO()
    write_touchstone(text, freqs, s, z0=75.0)
    lines = text.getvalue().splitlines()
    assert lines[0] == "# HZ S RI R 75"
    row = [float(token) for token in lines[1].split()]
    assert row[0] == freqs[0]
    assert np.allclose(row[1:3], [s11[0].real, s11[0].imag], rtol=0, atol=1e-10)
    assert np.allclose(row[3:5], [s21[0].real, s21[0].imag], rtol=0, atol=1e-10)
    assert np.allclose(row[5:7], [s12[0].real, s12[0].imag], rtol=0, atol=1e-10)
    assert np.allclose(row[7:9], [s22[0].real, s22[0].imag], rtol=0, atol=1e-10)

    _, back = read_touchstone(io.StringIO(text.getvalue()))
    assert np.allclose(back[:, 1, 0], s21, rtol=0, atol=1e-10)  # s[out=1, in=0]
    assert np.allclose(back[:, 0, 1], s12, rtol=0, atol=1e-10)

    # one port: a single column of numbers, the same two-per-value layout
    one = np.empty((2, 1, 1), dtype=complex)
    one[:, 0, 0] = [0.25 - 0.5j, -0.75 + 0.125j]
    out = io.StringIO()
    write_touchstone(out, freqs, one)
    f1, s1 = read_touchstone(io.StringIO(out.getvalue()))
    assert s1.shape == (2, 1, 1)
    assert np.allclose(f1, freqs, rtol=1e-12, atol=0.0)
    assert np.allclose(s1, one, rtol=0, atol=1e-10)


def test_lossless_two_port_obeys_passivity():
    """The primitives, used the way a run uses them, give a passive network."""
    d, beta = 5.0e-3, 120.0  # beta*d = 0.6 rad
    x = beta * d
    s11_target = 0.3 * np.exp(1j * 0.7)
    s21_target = np.sqrt(1.0 - abs(s11_target) ** 2) * np.exp(-1j * 1.2)
    v_plus = 1.0 + 0j

    # port 1 sits on a feed line carrying the incident wave and its reflection
    near1 = v_plus * (1.0 + s11_target)
    near2 = v_plus * (np.exp(-1j * x) + s11_target * np.exp(+1j * x))
    s11 = reflection(*travelling_waves(near1, near2, d, beta))

    # port 2 sees only the forward wave, delayed by the line and the device
    far1 = s21_target * v_plus * np.exp(-1j * x)
    s21 = transmission(v_plus, far1, d, beta)

    assert abs(s11 - s11_target) < 1e-12
    assert abs(s21 - s21_target) < 1e-12

    power = abs(s11) ** 2 + abs(s21) ** 2
    assert power <= 1.0 + 1e-12  # nothing is created at the port ...
    assert abs(power - 1.0) < 1e-12  # ... and this device is lossless


# ---------------------------------------------------------------------------
# plate current: a sum of dual H unknowns, so a closed form in amperes
# ---------------------------------------------------------------------------
def test_plate_current_scales_with_the_included_columns():
    """``n`` columns carrying ``F`` amperes add up to ``n * F``, and nothing else."""
    grid = Grid.uniform(4, 6, 3, 0.04, 0.06, 0.03)
    cc = CellComplex(grid)
    amp = 2.5
    h = np.zeros(cc.n_faces)
    for j in range(cc.nyn):
        h[cc.idx_fy(2, j, 1)] = amp

    # every y point layer of one station: ny + 1 dual edges, no cell width
    assert plate_current(h, cc, 2, 1) == pytest.approx(amp * cc.nyn)
    # the sum is per station, not global
    assert plate_current(h, cc, 1, 1) == 0.0
    assert plate_current(h, cc, 2, 0) == 0.0
    # a pair of point layers is a half-open run, exactly like column_path
    assert plate_current(h, cc, 2, 1, y_extent=(0, 3)) == pytest.approx(amp * 3)


def test_plate_current_extent_excludes_the_omitted_columns():
    """A strip extent sums the strip only: the omitted columns are not seen."""
    grid = Grid.uniform(3, 8, 2, 0.03, 0.08, 0.02)
    cc = CellComplex(grid)
    y = np.asarray(grid.y, dtype=float)
    centre = 0.5 * (float(y[0]) + float(y[-1]))
    half = 0.025
    inner = [j for j in range(cc.nyn) if abs(float(y[j]) - centre) <= half]
    outer = [j for j in range(cc.nyn) if j not in inner]
    assert inner and outer                     # the strip is neither all nor none

    h = np.zeros(cc.n_faces)
    for j in range(cc.nyn):
        h[cc.idx_fy(1, j, 0)] = (1.0 + j) if j in inner else 100.0

    strip = plate_current(h, cc, 1, 0, y_extent=half)
    whole = plate_current(h, cc, 1, 0)
    assert strip == pytest.approx(float(sum(1.0 + j for j in inner)))
    # what the extent leaves out is exactly the omitted columns' contribution
    assert whole - strip == pytest.approx(100.0 * len(outer))
    # the metre form and the index form of the same strip agree exactly
    assert plate_current(h, cc, 1, 0,
                         y_extent=(inner[0], inner[-1] + 1)) == strip


def test_plate_current_default_extent_is_the_plain_sum():
    """``y_extent=None`` is the hand-written sum over every y column, bit for bit."""
    grid = Grid.uniform(5, 5, 2, 0.05, 0.05, 0.02)
    cc = CellComplex(grid)
    h = np.random.default_rng(20250517).standard_normal(cc.n_faces)
    for ix in range(cc.nx):
        for iz in range(cc.nz):
            want = float(sum(h[cc.idx_fy(ix, j, iz)] for j in range(cc.nyn)))
            assert plate_current(h, cc, ix, iz) == want



# ---------------------------------------------------------------------------
# station impedance: two travelling waves seen at several stations
# ---------------------------------------------------------------------------
#: Nine stations 3 mm apart: a 24 mm span, across which the phase is
#: beta * 24 mm = 4.8 rad at the 200 rad/m used below.  Less than a turn, so
#: neither series aliases, and the two waves stay separable -- which is the
#: whole reason for putting stations along the line rather than one plane.
N_STATIONS = 9
STATION_STEP = 3.0e-3
BETA = 200.0


def _station_x() -> np.ndarray:
    """Station positions [m] for the station-fit tests."""
    return np.arange(N_STATIONS) * STATION_STEP


def _forward(z: np.ndarray, beta: float = BETA, amp: float = 1.0e-3):
    """Voltage and current [V, A] of a pure forward wave on a 50 ohm line.

    ``V = Z0 I`` with the forward phase ``exp(-j beta z)``, so the fit must
    return the real number it was built from and no backward amplitude at all.
    """
    current = amp * np.exp(-1j * beta * z)
    return 50.0 * current, current


def _reflected(z: np.ndarray, beta: float = BETA,
               gamma: complex = 0.1 * np.exp(1j * np.deg2rad(30.0))):
    """Voltage and current [V, A] of a 50 ohm line carrying forward + reflected.

    With ``a = 1 mA`` and ``b = gamma a`` the pair is
    ``V = Z0 (a e^{-j beta z} + b e^{+j beta z})`` and
    ``I = a e^{-j beta z} - b e^{+j beta z}``.  The minus sign on the backward
    current is the physics: a reflected wave carries power backwards, so on a
    line of one direction it is a current of the opposite sign.  Both series
    therefore hold the *same* two exponentials, with coefficients ``b / a`` for
    ``V`` and ``-b / a`` for ``I``, which is what the fit unpicks.
    """
    forward = 1.0e-3 * np.exp(-1j * beta * z)
    backward = gamma * 1.0e-3 * np.exp(1j * beta * z)
    return 50.0 * (forward + backward), forward - backward


def test_fit_station_impedance_recovers_a_pure_forward_wave():
    """One wave only: the fit returns the built-in 50 ohm and no reflection."""
    z = _station_x()
    v, i = _forward(z)
    fit = fit_station_impedance(z, v, i, BETA)

    assert fit.n_stations == N_STATIONS
    assert fit.beta == BETA
    assert fit.reference_plane == pytest.approx(float(z[0]))
    assert abs(fit.z0 - 50.0) <= 1e-9 * 50.0
    # a travelling wave is the pure mode: gamma_I = -gamma_V cancels exactly
    assert fit.mode_purity < 1e-9
    assert abs(fit.gamma_v) < 1e-9
    assert abs(fit.gamma_i) < 1e-9
    # no scatter and no beta lever arm asked for, so every sigma is roundoff
    # or absent rather than a number
    assert fit.residual_v < 1e-9
    assert fit.residual_i < 1e-9
    assert fit.z0_sigma_stat < 1e-9
    assert fit.z0_sigma_beta is None
    assert fit.z0_sigma_total is None
    assert np.all(np.abs(fit.residual_v_stations) < 1e-9)
    assert np.all(np.abs(fit.residual_i_stations) < 1e-9)


def test_fit_station_impedance_separates_the_two_waves():
    """A known reflection comes back as ``+gamma`` on V and ``-gamma`` on I.

    The algebra: with ``A_f = a`` and ``A_b = b`` in both series, the fit
    returns ``gamma_V = b / a`` and ``gamma_I = -b / a``, so their sum is zero
    whatever the reflection -- the pair is still one mode on one line, only
    its impedance magnitude changes.  ``z0 = A_V^f / A_I^f = Z0`` too, because
    the forward amplitudes divide out the common factor.
    """
    z = _station_x()
    gamma = 0.1 * np.exp(1j * np.deg2rad(30.0))
    v, i = _reflected(z, gamma=gamma)
    fit = fit_station_impedance(z, v, i, BETA)

    assert abs(fit.z0 - 50.0) <= 1e-9 * 50.0
    assert fit.gamma_v == pytest.approx(gamma, rel=1e-9, abs=1e-9)
    assert fit.gamma_i == pytest.approx(-gamma, rel=1e-9, abs=1e-9)
    assert fit.mode_purity < 1e-9
    assert abs(fit.phase_deg) < 1e-9


def test_fit_station_impedance_carries_a_wrong_beta_into_z0():
    """A beta that is 2 % too large moves z0 -- and only if a wave reflects.

    With two waves present and the wrong phase constant, the refit can only
    match the data by attributing part of the forward wave to the backward
    one, so the recovered ratio stops being real: here it drops below 50 ohm
    and picks up a positive imaginary part (measured 49.9499 + 0.0714j).  The
    same wrong beta on a pure travelling wave leaves ``z0`` exact, because one
    exponential divided by another cancels whatever phase constant both were
    fitted with -- but the mode test still fails, since the pair of spurious
    coefficients come out with the same sign instead of opposite ones
    (``mode_purity`` 0.0175 against roundoff).  So neither series on its own
    can police ``beta``: only the sum signature can, which is why the beta
    part of the budget is reported separately and not folded into a
    statistical sigma.
    """
    z = _station_x()
    sigma_beta = 4.0

    v, i = _reflected(z)
    shifted = fit_station_impedance(z, v, i, 1.02 * BETA, sigma_beta)
    assert shifted.z0.real < 50.0
    assert shifted.z0.imag > 0.0
    assert shifted.phase_deg > 0.0
    assert shifted.z0_sigma_beta == pytest.approx(0.0911, abs=5e-4)
    # the assumed pair no longer has gamma_I = -gamma_V at the wrong beta
    assert shifted.mode_purity > 0.0

    v, i = _forward(z)
    exact = fit_station_impedance(z, v, i, 1.02 * BETA, sigma_beta)
    assert abs(exact.z0 - 50.0) <= 1e-9 * 50.0
    assert exact.z0_sigma_beta < 1e-9 * 50.0
    # one wave, wrong beta: ``z0`` cannot see it, the mode signature can
    assert exact.mode_purity == pytest.approx(0.01746, abs=1e-4)


def test_sigma_beta_from_curvature_is_roundoff_on_exact_data():
    """Noiseless data: the curvature estimate is roundoff, not a measurement.

    The estimator scales with the residual sum of squares, so exact data give
    ``s = 0`` and a sigma at machine precision (measured 3e-15 rad/m against
    ``beta`` = 200 rad/m).  That is the honest answer for the arithmetic and
    no answer at all for an experiment; the test pins the *behaviour* -- a
    fitted beta that is exact must not be dressed up as a measured one.
    """
    z = _station_x()
    v, i = _forward(z)
    sigma = sigma_beta_from_curvature(z, v, BETA)
    assert sigma is not None
    assert 0.0 <= sigma < 1e-9 * BETA

    # On data that a single wave cannot fit, the same estimate is a real
    # number: a few rad/m, i.e. per cent level, and finite.
    v, i = _reflected(z)
    sigma = sigma_beta_from_curvature(z, v, BETA)
    assert sigma is not None
    assert 0.0 < sigma < 0.1 * BETA



# ---------------------------------------------------------------------------
# reference planes: de-embedding, and the power-current check
# ---------------------------------------------------------------------------
def test_deembed_reflection_round_trip_returns_the_original():
    """Shift a reflection upstream and back: the plane must leave no trace.

    A factor of ``exp(-2j beta d)`` applied twice with opposite ``d`` is the
    identity, for a real phase constant and for a lossy complex one, because
    nothing in the algebra knows which is which.  This is the test that would
    catch a sign error, which is otherwise invisible: a wrong-sign de-embedding
    still returns a number of the right size.
    """
    gamma = 0.21 - 0.13j
    distance = 7.2e-3
    for beta in (232.4, 180.0 - 3.5j):
        there = deembed_reflection(gamma, beta, distance)
        back = deembed_reflection(there, beta, -distance)
        assert abs(back - gamma) < 1e-12

    # the transmission coefficient removes the delay it crossed, so a bare
    # length of line comes back as exactly 1
    beta = 232.4
    delay = np.exp(-1j * beta * distance)
    assert abs(deembed_transmission(delay, beta, distance) - 1.0) < 1e-12


def test_deembed_magnitude_moves_only_through_absorption():
    """Real ``beta``: the plane shift is phase only.  Complex ``beta``: loss.

    With a real phase constant ``|gamma|`` is the same on every plane, so a
    de-embedded magnitude that differs from the measured one is an algebra
    bug.  With ``beta = beta' - 1j * alpha`` the shift multiplies the magnitude
    by ``exp(-2 alpha d)`` -- the round trip the wave makes over that distance
    -- and the transmission by ``exp(-alpha d)``, the one-way loss.  That is
    the definition of the lossy case, not a side effect.
    """
    gamma = 0.0075 + 0.002j
    for distance in (-1.0e-2, 0.0, 7.2e-3):
        moved = deembed_reflection(gamma, 232.4, distance)
        assert abs(abs(moved) - abs(gamma)) < 1e-12

    alpha = 4.0                     # 1/m
    beta = 232.4 - 1j * alpha
    distance = 1.0e-2
    # a reflection referred upstream shrinks: it died twice over the round trip
    got = abs(deembed_reflection(gamma, beta, distance))
    assert abs(got - abs(gamma) * np.exp(-2.0 * alpha * distance)) < 1e-12
    # a transmission referred upstream grows by the attenuation undone
    got = abs(deembed_transmission(1.0, beta, distance))
    assert abs(got - np.exp(alpha * distance)) < 1e-12


def test_power_current_ratio_is_one_for_a_single_wave():
    """One mode, real ``Z0``: the pair's power and current give that ``Z0``.

    ``V = Z0 I`` with ``Z0 = 50`` ohm and 1 mA of current carries 25 uW; the
    impedance the power and the current imply must be the 50 ohm that was put
    in, and the ratio to the fitted value must be 1 at roundoff.  A dead
    current gives no impedance and must come back NaN rather than infinity.
    """
    z0 = 50.0
    current = np.array([1e-3, 1e-3 * np.exp(-0.3j), 0.0])
    voltage = z0 * current
    z0_power, ratio = power_current_check(voltage, current, z0)

    assert abs(z0_power[0] - 50.0) < 1e-9
    assert abs(z0_power[1] - 50.0) < 1e-9
    assert abs(ratio[0] - 1.0) < 1e-12
    assert abs(ratio[1] - 1.0) < 1e-12
    assert np.isnan(z0_power[2]) and np.isnan(ratio[2])


def test_power_current_ratio_follows_the_standing_wave():
    """Forward plus reflected wave: the ratio is the closed form, not 1.

    With ``V = A (e^{-j b u} + G e^{+j b u})`` and
    ``I = (A / Z0) (e^{-j b u} - G e^{+j b u})`` the ratio is

        ``(1 + |G|**2 + 2 Re(G e^{2j b u})) / (1 + |G|**2 - 2 Re(G e^{2j b u}))``

    which is the number the check exists to bound: 1 at a maximum of the
    pattern, and large near a null where the current vanishes.  Getting this
    wrong in either direction means the current convention is wrong, and a
    station impedance fitted through it is then not an impedance.
    """
    z0 = 50.0
    beta = BETA
    gamma = 0.2 + 0.1j
    u = _station_x()
    forward = np.exp(-1j * beta * u)
    backward = np.exp(1j * beta * u)
    amplitude = 1.0e-3
    voltage = z0 * amplitude * (forward + gamma * backward)
    current = amplitude * (forward - gamma * backward)

    z0_power, ratio = power_current_check(voltage, current, z0)
    # the power is plane-independent, 1 - |G|**2; only |I|**2 ripples
    ripple = np.real(gamma * backward ** 2)
    expected = ((1.0 - abs(gamma) ** 2)
                / (1.0 + abs(gamma) ** 2 - 2.0 * ripple))
    assert np.allclose(ratio, expected, rtol=0.0, atol=1e-9)
    assert np.allclose(z0_power, z0 * expected, rtol=0.0, atol=1e-6)
    # a real reflection of this size really does move the ratio off 1
    assert np.max(np.abs(ratio - 1.0)) > 0.15
    assert np.max(np.abs(ratio - 1.0)) < ((1.0 + abs(gamma))
                                          / (1.0 - abs(gamma))) ** 2 - 1.0
