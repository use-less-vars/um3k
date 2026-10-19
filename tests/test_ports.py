"""Tests for :mod:`emfit.ports` -- the analytic primitives of a wave port.

Nothing here runs the solver.  Every number is either arithmetic this file makes
up (a tone of known amplitude, a wave of known phase) or a value worked out by
hand from ``e[k] = k``, so a failure means an algebra or convention error, never
a badly conditioned run.  The groups are: probe voltages (a line integral over
edge unknowns), the running DFT that turns probe samples into phasors, the
two-probe split that turns phasors into travelling waves and S-parameters, and
the Touchstone writer/reader that carries the S-matrix between runs.
"""

from __future__ import annotations

import io

import numpy as np
import pytest

from emfit.ports import (
    DftAccumulator,
    LumpedPort,
    Probe,
    edge_path_voltage,
    probe_voltage,
    read_touchstone,
    reflection,
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
