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

from emfit.netlist import NetlistError, parse_netlist
from emfit.spice import (
    Branch,
    CircuitNetwork,
    MNASolver,
    TransmissionLine,
    _line_buffers,
    _line_history,
    _solve_step,
)

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
