"""``emfit.spice``'s transmission line, end to end: the open-end step, the
quarter- and half-wave input impedances, and the netlist that builds a line.

Three gates, in the order the feature is layered.

**The open-end step** --
``test_open_end_line_steps_to_the_closed_form_plateaus`` -- pins the whole
travelling-wave path at once: the history buffer, the two-ended stamp, the
branch current, and the fact that a line is *linear* and must therefore be
solved by the no-diode fast path (one assembly, zero Newton iterations).
Circuit::

    Vs -- R_s = Z0 -- node a -- line(z0 = Z0, tau = 4 dt) -- node b (open)

**Quarter and half wave** --
``test_a_shorted_line_loads_the_source_as_open_then_short`` -- is the reason
the line exists.  A lossless line of delay ``tau`` shorted at the far end
presents ``Zin = j z0 tan(2 pi f tau)``, so at ``tau = T/4`` (``tan = inf``) the
source sees an **open** and at ``tau = T/2`` (``tan = 0``) it sees a **short**.
Driven through ``R_s = Z0``: at quarter wave no current leaves the source, so
``v_a`` is the full source amplitude and ``i_a`` is zero; at half wave the line
looks like a wire to ground, so ``v_a`` is zero and ``i_a = Vs/Z0``.  That is a
statement about *impedance*, and no lumped ladder reproduces it at any order --
which is what an unconditional "a line is not a ladder" claim needs.  This gate
runs through ``parse_netlist`` on a JSON document, so a ``T`` element that fails
to parse fails here too.  The short is an ordinary ``V`` source of ``0.0`` volts
from the far node to ground: an ideal short needs no new machinery, and the
parser accepts any finite source value.

**The ``T`` fields** -- the negative cases at the bottom.  ``z0`` and ``tau``
are required (no defaults: a forgotten ``tau`` would silently become 1 ns), and
geometry is refused, because a ``tau`` derived from ``len_mm``/``eps_eff``
would be a second source of truth for the one number the line is made of.

Exact arithmetic
----------------
``tau = 4 dt`` for the open-end gate and ``T = 40 dt``, ``tau = 10 dt`` /
``20 dt`` for the impedance gate: every ratio is a whole number of steps, the
delay needs no interpolation (the weight is exactly zero), and the sine is
sampled at ``k/40`` of a period, so the samples land exactly on its peaks.  The
amplitudes are therefore ideal to *machine precision*, not to a sampling error,
and they are quoted at 17 digits for that reason.  The impedance gate measures
peak-to-peak over a full period rather than a single sample, so a phase shift
cannot masquerade as a gain, and it measures twice, 200 steps apart, so
"steady state" is checked rather than assumed.

Expected plateaus (open end)
----------------------------
``v_b = 0`` for ``t <= tau``, ``Vs`` for ``t >= tau + dt``;
``v_a = Vs/2`` for ``t <= 2 tau``, ``Vs`` for ``t >= 2 tau + dt``;
``i_a = Vs/(2 Z0)`` before the round trip, ``0`` after it.

The one ``dt`` of slack on each edge is not tolerance: the ideal source is
applied by the *first* step, so the wave leaves at ``t = dt`` and lands exactly
``tau`` later, at ``t = tau + dt``.  The delay the buffer realises is ``tau``;
the offset is the launch, and asserting ``v_b == Vs`` already at ``t == tau``
would be asserting a delay of ``tau - dt``.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.netlist import NetlistError, parse_netlist, quarter_wave_tau
from emfit.spice import (
    Branch,
    CircuitNetwork,
    MNASolver,
    TransmissionLine,
    _line_buffers,
    _line_history,
    _solve_step,
)
from emfit.studies import snapped_tone

RTOL = 1e-12
# Gate-level floor for a quantity that should be *exactly* zero.  The measured
# residues are roundoff of an O(Vs) solve: 7e-15 for the half-wave v_a, 2e-16
# for the quarter-wave i_a -- so this is a roundoff gate with three orders of
# margin, not a tuned number.
ATOL = 1e-12

Z0 = 50.0
VS = 1.0
DT = 1e-12
TAU = 4.0 * DT
PERIOD = 40.0 * DT
TAU_QUARTER = PERIOD / 4.0
TAU_HALF = PERIOD / 2.0

# Branch order fixes the element-current vector: V, R, line.
LINE = 2


def _shorted_line_doc(tau=TAU_QUARTER, *, z0=Z0, drop=None, extra=None):
    """Sine -- R_s = Z0 -- line(z0, tau) -- short, as a JSON-shaped netlist."""
    line = {"kind": "T", "name": "line", "nodes": ["a", "b"],
            "z0": z0, "tau": tau}
    if drop is not None:
        del line[drop]
    if extra is not None:
        line.update(extra)
    return {
        "name": "shorted_line",
        "nodes": ["in", "a", "b", "0"],
        "elements": [
            {"kind": "V", "name": "vs", "nodes": ["in", "0"], "value": 0.0,
             "waveform": {"type": "sine", "amplitude": VS,
                          "frequency": 1.0 / PERIOD}},
            {"kind": "R", "name": "rs", "nodes": ["in", "a"], "value": Z0},
            line,
            # An ideal short: the parser accepts a zero-valued V source, so the
            # far end needs no element the format does not already have.
            {"kind": "V", "name": "short", "nodes": ["b", "0"], "value": 0.0},
        ],
    }


def test_open_end_line_steps_to_the_closed_form_plateaus():
    net = CircuitNetwork(
        (
            Branch("V", (1, 0), VS),
            Branch("R", (1, 2), Z0),
            TransmissionLine((2, 3), z0=Z0, tau=TAU),
        ),
        n_nodes=4,
    )
    solver = MNASolver(net)
    state = solver.initial_state()

    # A line is a linear companion stamp, so the network has no diode and the
    # fast path must take it: one assembly, no Newton loop.  Checked before any
    # stepping, from the same (zero) history the first step will read.
    lines = _line_buffers(net, DT, state.tline)
    history = _line_history(net, lines, DT)
    _, _, iterations = _solve_step(
        net, DT, state.u, state.i_branch, "backward_euler", line_history=history
    )
    assert iterations == 0, (
        "a transmission line is linear, so the no-diode fast path must solve "
        f"this circuit in one assembly; got {iterations} Newton iterations"
    )

    n_steps = 12
    v_a, v_b, i_a = [], [], []
    for _ in range(n_steps):
        state, u, currents = solver.step(DT, state)
        v_a.append(u[2])
        v_b.append(u[3])
        i_a.append(currents[LINE])

    n_tau = int(round(TAU / DT))  # 4
    n_2tau = 2 * n_tau  # 8
    assert n_tau == 4 and TAU / DT == 4.0

    windows = (
        # (label, series, first step, last step, expected)
        ("v_b before arrival", v_b, 1, n_tau, 0.0),
        ("v_b after arrival", v_b, n_tau + 1, n_steps, VS),
        ("v_a before round trip", v_a, 1, n_2tau, VS / 2.0),
        ("v_a after round trip", v_a, n_2tau + 1, n_steps, VS),
        ("i_a before round trip", i_a, 1, n_2tau, VS / (2.0 * Z0)),
        ("i_a after round trip", i_a, n_2tau + 1, n_steps, 0.0),
    )
    for label, series, first, last, expected in windows:
        for k in range(first, last + 1):
            got = series[k - 1]
            assert np.isclose(got, expected, rtol=RTOL, atol=ATOL), (
                f"{label}: step {k} (t = {k * DT / TAU:g} tau) should be "
                f"{expected!r}, got {got!r}"
            )


def test_a_shorted_line_loads_the_source_as_open_then_short():
    # -- quarter wave: Zin = inf, the source drives an open -------------------
    quarter = parse_netlist(_shorted_line_doc(TAU_QUARTER))
    line = quarter.network.branches[quarter.element_index["line"]]
    assert isinstance(line, TransmissionLine), (
        "a 'T' element must build a TransmissionLine branch, not "
        f"{type(line).__name__}"
    )
    assert (line.z0, line.tau) == (Z0, TAU_QUARTER)
    assert quarter.elements[quarter.element_index["line"]].value == 0.0, (
        "a line has no 'value'; its Element must report 0.0, exactly as a "
        "diode does"
    )

    quarter_run = quarter.transient(dt=DT, n_steps=460)
    v_a = np.asarray(quarter_run.v["a"])
    i_a = np.asarray(quarter_run.i["line"])

    # -- half wave: Zin = 0, the line is a wire to ground --------------------
    half = parse_netlist(_shorted_line_doc(TAU_HALF))
    half_run = half.transient(dt=DT, n_steps=460)
    v_b = np.asarray(half_run.v["a"])
    i_b = np.asarray(half_run.i["line"])

    for first, last in ((200, 240), (400, 440)):
        window = slice(first, last + 1)
        where = f"steps {first}..{last} (t = {first * DT / PERIOD:g}..{last * DT / PERIOD:g} T)"

        # Peak-to-peak over one full period: 2 Vs for a full-amplitude sine.
        got = float(np.ptp(v_a[window]))
        assert np.isclose(got, 2.0 * VS, rtol=RTOL, atol=0.0), (
            f"quarter wave (tau = T/4) is an open circuit, so the source must "
            f"see no load and v_a must be the full source, i.e. peak-to-peak "
            f"{2.0 * VS!r} (amplitude {VS!r}); got {got!r} at {where}"
        )
        got = float(np.ptp(i_a[window]))
        assert np.isclose(got, 0.0, rtol=0.0, atol=ATOL * VS / Z0), (
            "quarter wave into a short is an open circuit: no current leaves "
            f"the source, so i_a is zero; got peak-to-peak {got!r} at {where}"
        )

        got = float(np.ptp(v_b[window]))
        assert np.isclose(got, 0.0, rtol=0.0, atol=ATOL * VS), (
            f"half wave (tau = T/2) is a short circuit to ground, so v_a must "
            f"be zero; got peak-to-peak {got!r} at {where}"
        )
        got = float(np.ptp(i_b[window]))
        assert np.isclose(got, 2.0 * VS / Z0, rtol=RTOL, atol=0.0), (
            f"half wave into a short is a short circuit, so i_a = Vs/R_s = "
            f"{VS / Z0!r}, i.e. peak-to-peak {2.0 * VS / Z0!r}; got {got!r} "
            f"at {where}"
        )


@pytest.mark.parametrize(
    "change, message",
    (
        ({"drop": "tau"}, r"element 'line': a T element needs 'tau'"),
        ({"drop": "z0"}, r"element 'line': a T element needs 'z0'"),
        ({"extra": {"len_mm": 15.2}},
         r"element 'line': unexpected field\(s\) \['len_mm'\]"),
    ),
    ids=("missing-tau", "missing-z0", "geometry-field"),
)
def test_a_t_element_must_carry_its_own_delay_and_impedance(change, message):
    with pytest.raises(NetlistError, match=message):
        parse_netlist(_shorted_line_doc(**change))


@pytest.mark.parametrize(
    "change",
    ({"z0": 0.0}, {"z0": -Z0}, {"tau": 0.0}),
    ids=("zero-impedance", "negative-impedance", "zero-delay"),
)
def test_a_line_rejects_a_non_physical_impedance_or_delay(change):
    with pytest.raises(ValueError):
        TransmissionLine((1, 2), **{"z0": Z0, "tau": TAU, **change})


def test_the_parse_path_wraps_a_zero_impedance_in_a_netlist_error():
    """A netlist reader only ever sees what ``parse_netlist`` raises.

    The gate above pins ``TransmissionLine``'s own ``ValueError``.  This one
    pins the BUILD pass of the parser: ``parse_netlist`` constructs the branch
    from the document's ``z0``/``tau`` and must catch that ``ValueError`` and
    re-raise it as a ``NetlistError`` naming the element -- otherwise the same
    malformed netlist escapes as a bare ``ValueError`` and every caller's
    ``except NetlistError`` stops catching it.
    """
    with pytest.raises(NetlistError,
                       match=r"element 'line': z0 must be finite and positive"):
        parse_netlist(_shorted_line_doc(z0=0.0))


def test_a_line_rejects_a_short_circuited_pair():
    with pytest.raises(ValueError):
        TransmissionLine((2, 2), z0=Z0, tau=TAU)
    with pytest.raises(ValueError):
        TransmissionLine((2,), z0=Z0, tau=TAU)


# --------------------------------------------------------------------------
# the quarter-wave delay is DERIVED from a tone, never written down beside it
# --------------------------------------------------------------------------
# The default microstrip mesh's step (cell 0.4 mm -> 0.7626299478123987 ps).  A
# run is never analysed at the tone it asks for: it is analysed at the DFT bin
# nearest the request, and that bin grid is ``k / (n_acc * dt)`` -- so the delay
# a quarter-wave stub has to carry is a function of this number *and* of the
# warm-up window, which is why it cannot be a constant in a document.
MS_DT = 7.626299478123987e-13
#: The same 6 GHz request at ``nsteps = 2400``, on the CW default
#: (``n_warm = nsteps // 4 = 600``, ``span = 1800 dt``) and on the pulse path
#: (``n_warm = 0``, ``span = 2400 dt``): the two bins the study can read.
F_CW = 5827786408.327286
F_PULSE = 6009904733.587513


def test_quarter_wave_tau_is_the_delay_a_quarter_wave_line_needs():
    """``quarter_wave_tau(f) = 1/(4 f)``, and it is the only home of that rule.

    This is the number a ``T`` element's ``tau`` and a document's
    ``quarter_wave_hz`` are tied together by (the parser checks one against the
    other at staging, and re-derives the *delivered* delay from it when it is
    told the run's tone).  It is also the number this file's quarter-wave gate
    relies on: at ``tau = T/4`` a shorted line presents ``tan(2 pi f tau) =
    tan(pi/2) -> inf``, i.e. an OPEN, which is what makes the impedance gate a
    statement no lumped ladder reproduces.  A second copy of ``1/(4f)`` in a
    caller is how the two drift apart, so the closed form is pinned here, in
    one place, with the exponent ranges the tree actually uses (a 1 Hz tone to
    a 1 THz one).
    """
    for f_hz in (1.0, 1e6, F_CW, F_PULSE, 1e12):
        tau = quarter_wave_tau(f_hz)
        # A quarter PERIOD of the tone: 2 pi f tau == pi/2 exactly.
        assert np.isclose(2.0 * np.pi * f_hz * tau, 0.5 * np.pi,
                          rtol=1e-15, atol=0.0), (
            f"quarter_wave_tau({f_hz!r}) = {tau!r} s puts 2 pi f tau at "
            f"{2.0 * np.pi * f_hz * tau!r} rad, not pi/2"
        )
        # That is the same statement as tau = 1/(4 f), in one division.
        assert tau == 1.0 / (4.0 * f_hz)

    # The two tones ``load_stub.json`` and a --vis-dump run of the same arm are
    # cut for, at 17 digits: 42.89793456444743 ps and 41.59799715340357 ps.
    assert quarter_wave_tau(F_CW) == 4.289793456444743e-11
    assert quarter_wave_tau(F_PULSE) == 4.159799715340357e-11

    # A tone that is not a finite, strictly positive number is REFUSED, not
    # turned into an infinite or negative delay: the parser re-raises this as a
    # NetlistError naming the element and the field, so the check has to happen
    # here rather than at the far end of the build pass.
    for f_hz in (0.0, -F_CW, float("nan"), float("inf"), "fast", None):
        with pytest.raises(ValueError, match=r"a quarter-wave tone must be"):
            quarter_wave_tau(f_hz)


def test_the_tone_a_run_is_analysed_at_is_what_cuts_the_stub():
    """The stub's delay follows the ANALYSIS tone, and the tone can move.

    ``emfit.studies.snapped_tone`` is the one home of "which tone is this run
    analysed at", and the answer depends on the warm-up window: a CW run
    discards ``nsteps // 4`` steps, so its DFT spans ``1800 dt`` and the bin
    nearest 6 GHz is 5.827786408328 GHz, while ``excite='pulse'`` passes
    ``n_warm = 0``, spans ``2400 dt``, and reads 6.009904733588 GHz.  A stub cut
    as a quarter wave for the first is 3 % off being one at the second, so the
    delay has to be re-derived per run -- and ``--vis-dump`` in
    ``evidence/termination/run_build_A.py`` sets ``excite='pulse'`` on any run
    it is handed, which is exactly how the two got mixed up once.
    """
    f_cw, n_warm_cw, n_acc_cw = snapped_tone(MS_DT, 2400, 600, 6e9)
    f_pulse, n_warm_pulse, n_acc_pulse = snapped_tone(MS_DT, 2400, 0, 6e9)
    assert (f_cw, n_warm_cw, n_acc_cw) == (F_CW, 600, 1800)
    assert (f_pulse, n_warm_pulse, n_acc_pulse) == (F_PULSE, 0, 2400)
    # ``None`` IS the CW default (a quarter of the record), not a third window.
    assert snapped_tone(MS_DT, 2400, None, 6e9) == (F_CW, 600, 1800)

    tau_cw = quarter_wave_tau(f_cw)
    tau_pulse = quarter_wave_tau(f_pulse)
    # Each delay is exactly a quarter wave at its OWN tone ...
    for f_hz, tau in ((f_cw, tau_cw), (f_pulse, tau_pulse)):
        assert np.isclose(2.0 * np.pi * f_hz * tau, 0.5 * np.pi,
                          rtol=1e-15, atol=0.0)
    # ... and the CW one is NOT a quarter wave at the pulse tone: tan(2 pi f tau)
    # is tan(pi/2) at its own tone and tan(1.54) at the other's, which is a
    # reactance, not an open.  That gap is the whole reason for re-deriving.
    assert abs(f_pulse / f_cw - 1.0) > 0.02
    assert abs(2.0 * np.pi * f_pulse * tau_cw - 0.5 * np.pi) > 0.04

    # Against the mesh's own step NEITHER delay is a whole number of samples,
    # so ``emfit.spice._line_history`` takes its linear-interpolation path
    # (weights 0.25 and 0.5454...) instead of landing on a sample -- and
    # snapping to 56 dt, the nearby sample, would be 0.44 % short.
    assert tau_cw / MS_DT == 56.25
    assert np.isclose(tau_pulse / MS_DT, 54.545454545454545, rtol=0.0, atol=1e-9)
    for tau in (tau_cw, tau_pulse):
        samples = tau / MS_DT
        assert samples != round(samples), (
            f"tau = {tau!r} s is exactly {samples!r} steps: the line would stop "
            "interpolating and the notch would move onto the sample grid"
        )
        assert 0.2 < samples - np.floor(samples) < 0.6
    assert abs((56.0 * MS_DT) / tau_cw - 1.0) > 4e-3

