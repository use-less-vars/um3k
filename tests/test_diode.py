"""The nonlinear diode: its model, the Newton loop inside a step, and netlists.

Three things are pinned here, in the order they are built on each other.

* :class:`emfit.spice.Diode` evaluates a Shockley junction law and its
  derivative, with the exponentials clamped so a reverse bias cannot overflow.
* That element is stamped by :func:`emfit.spice._assemble` at a *given* bias,
  and :func:`emfit.spice._solve_step` closes the loop around it: assemble,
  solve, limit the junction voltage, repeat until the bias stops moving.  The
  answers are checked against a closed form (a bisection root of the same
  circuit's DC equation) and against the rectifier behaviour a half-wave
  circuit must show, not against stored numbers.
* A linear network is *not* iterated: the loop is skipped entirely, one
  assembly and one solve, bit-for-bit the same answer as before the diode
  existed.

Nothing here reaches into the field coupling: ``SpicePort`` gained only a
pass-through ``max_iter``, and the diode is exercised on the standalone
network where an exact answer is available.
"""

import math

import numpy as np
import pytest

from emfit import spice
from emfit.netlist import NetlistError, parse_netlist
from emfit.spice import (
    Branch,
    CircuitNetwork,
    Diode,
    DiodeConvergenceError,
    MNASolver,
    _assemble,
    _recover,
    _solve_step,
)

SOURCE_AMPLITUDE = 5.0
FREQUENCY = 1000.0
DT = 1e-5
STEPS = 500
ISAT = 1e-14
EMISSION = 1.0
VT = 0.02585
GMIN = 1e-12
R_LOAD = 1000.0

# v_in -> D -> v_out -> R -> ground, with the diode forward from in to out, so
# the output can only ever be pulled high by the source and falls to the
# reverse leakage when the source is negative.
V_IN = 1
V_OUT = 2


def _half_wave_network():
    # the source's frozen ``value`` is its **DC level**, which is 0 here: the 5 V
    # amplitude rides on the netlist's sine waveform and enters every step
    # through ``sources=``.  That is what makes the hand-built network
    # comparable, element for element, with the one ``parse_netlist`` builds
    # for the document at the bottom of this file.
    return CircuitNetwork(
        branches=(
            Branch("V", (V_IN, 0), 0.0),
            Diode((V_IN, V_OUT), isat=ISAT, n=EMISSION, vt=VT, gmin=GMIN),
            Branch("R", (V_OUT, 0), R_LOAD),
        ),
        n_nodes=3,
    )


def _sine_sources(t):
    """What ``Netlist.source_values`` would produce: only branch 0 moves."""
    return np.array(
        [SOURCE_AMPLITUDE * math.sin(2.0 * math.pi * FREQUENCY * t), 0.0, 0.0]
    )


def _run_by_hand(steps=STEPS, dt=DT):
    """Drive the solver directly, so the netlist path can be compared to it."""
    network = _half_wave_network()
    solver = MNASolver(network)
    state = solver.initial_state()
    voltages = []
    for k in range(steps):
        state, u, _ = solver.step(dt, state, sources=_sine_sources((k + 1) * dt))
        voltages.append(np.array(u, dtype=float))
    return network, np.array(voltages)


# --------------------------------------------------------------------------
# the model itself
# --------------------------------------------------------------------------


def test_diode_is_a_branch_of_kind_d():
    diode = Diode((1, 2), isat=ISAT, n=EMISSION, vt=VT, gmin=GMIN)
    assert diode.kind == "D"
    assert diode.nodes == (1, 2)
    # a network accepts it where it accepts a Branch
    network = CircuitNetwork(branches=(diode, Branch("R", (2, 0), 1.0)), n_nodes=3)
    assert network.branches[0] is diode


def test_diode_current_and_conductance_follow_the_junction_law():
    diode = Diode((1, 2), isat=ISAT, n=EMISSION, vt=VT, gmin=GMIN)

    # forward: exponential, plus the parallel leakage
    v = 0.6
    expected = ISAT * (math.exp(v / VT) - 1.0) + GMIN * v
    assert diode.current(v) == pytest.approx(expected, rel=1e-9)
    assert diode.conductance(v) == pytest.approx(
        ISAT * math.exp(v / VT) / VT + GMIN, rel=1e-9
    )

    # reverse: the expm1 form keeps it at the leakage, not at -isat, and the
    # conductance collapses to gmin
    assert diode.current(-1.0) == pytest.approx(-ISAT - GMIN, rel=1e-9)
    assert diode.conductance(-1.0) == pytest.approx(GMIN, rel=1e-9)

    # at zero bias the current is exactly zero and the conductance is finite
    assert diode.current(0.0) == 0.0
    assert diode.conductance(0.0) == pytest.approx(ISAT / VT + GMIN, rel=1e-9)

    # a wildly forward bias is clamped, not an overflow to inf
    assert np.isfinite(diode.current(50.0))
    assert np.isfinite(diode.conductance(50.0))


def test_diode_critical_voltage_is_the_linearisation_limit():
    diode = Diode((1, 2), isat=ISAT, n=EMISSION, vt=VT, gmin=GMIN)
    expected = EMISSION * VT * math.log(EMISSION * VT / (math.sqrt(2.0) * ISAT))
    assert diode.vcrit == pytest.approx(expected, rel=1e-12)
    # and it is where the conductance equals the secant: a real limit, not a
    # decoration, so it must sit in the forward knee
    assert 0.5 < diode.vcrit < 0.9


@pytest.mark.parametrize(
    "kwargs",
    [
        {"nodes": (1, 1)},
        {"nodes": (-1, 0)},
        {"isat": 0.0},
        {"isat": -1.0},
        {"isat": float("nan")},
        {"n": 0.0},
        {"vt": -0.1},
        {"gmin": -1e-12},
        {"n": float("inf")},
    ],
)
def test_diode_rejects_impossible_parameters(kwargs):
    fields = {"nodes": (1, 2), "isat": ISAT, "n": EMISSION, "vt": VT, "gmin": GMIN}
    fields.update(kwargs)
    nodes = fields.pop("nodes")
    with pytest.raises(ValueError):
        Diode(nodes, **fields)


# --------------------------------------------------------------------------
# one step: the Newton loop
# --------------------------------------------------------------------------


def test_a_steady_5V_step_lands_on_the_bisection_root():
    """With no L or C the first step *is* the DC operating point."""
    network = _half_wave_network()
    solver = MNASolver(network)
    state = solver.initial_state()
    _, u, _ = solver.step(DT, state, sources=np.array([SOURCE_AMPLITUDE, 0.0, 0.0]))

    # the same circuit in closed form: I(5 - v) == v / R, decreasing in v
    diode = network.branches[1]

    def f(v_out):
        return diode.current(SOURCE_AMPLITUDE - v_out) - v_out / R_LOAD

    lo, hi = 0.0, SOURCE_AMPLITUDE
    assert f(lo) > 0.0 > f(hi)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    root = 0.5 * (lo + hi)

    assert u[0] == 0.0
    assert u[V_IN] == pytest.approx(SOURCE_AMPLITUDE, rel=0, abs=1e-12)
    assert u[V_OUT] == pytest.approx(root, abs=1e-6)
    # ~0.70 V of forward drop across the junction, as a silicon diode should
    assert SOURCE_AMPLITUDE - u[V_OUT] == pytest.approx(0.6963, abs=1e-2)


def test_the_newton_loop_reports_convergence_failure_instead_of_lying():
    network = _half_wave_network()
    solver = MNASolver(network)
    state = solver.initial_state()
    sources = np.array([SOURCE_AMPLITUDE, 0.0, 0.0])

    # from an all-zero history the junction walk has to take many limited
    # steps to climb to 0.7 V, so a cap of one or two cannot reach it
    with pytest.raises(DiodeConvergenceError) as printed:
        solver.step(DT, state, sources=sources, max_iter=2)
    exc = printed.value
    assert isinstance(exc, RuntimeError)
    assert exc.iterations >= 1
    assert exc.step > exc.tolerance
    assert exc.tolerance > 0.0

    # and the same step, uncapped, does converge -- the failure above was the
    # cap, not the circuit
    solver.step(DT, state, sources=sources)


def test_max_iter_must_be_at_least_one():
    network = _half_wave_network()
    solver = MNASolver(network)
    state = solver.initial_state()
    with pytest.raises(ValueError):
        solver.step(DT, state, sources=np.array([SOURCE_AMPLITUDE, 0.0, 0.0]),
                    max_iter=0)


def test_each_step_needs_only_a_handful_of_iterations(monkeypatch):
    """A converged operating point makes the next step cheap: Newton warm-starts."""
    network = _half_wave_network()
    original = spice._assemble
    calls = {"n": 0}

    def counting(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(spice, "_assemble", counting)
    solver = MNASolver(network)
    state = solver.initial_state()
    per_step = []
    for k in range(100):
        before = calls["n"]
        state, _, _ = solver.step(DT, state, sources=_sine_sources((k + 1) * DT))
        per_step.append(calls["n"] - before)

    assert min(per_step) >= 1  # every step assembles at least once
    assert max(per_step) <= 20  # and none grinds towards the cap of 100


def test_a_linear_network_is_not_iterated_at_all(monkeypatch):
    """The diode-free path must be untouched: one assembly, one solve, same bits."""
    network = CircuitNetwork(
        branches=(
            Branch("V", (1, 0), 1.0),
            Branch("L", (1, 2), 1e-3),
            Branch("C", (2, 0), 1e-6),
            Branch("R", (2, 0), 50.0),
        ),
        n_nodes=3,
    )
    solver = MNASolver(network)
    state = solver.initial_state()
    sources = np.array([1.0, 0.0, 0.0, 0.0])

    A, b, info = _assemble(network, DT, state.u, state.i_branch, "backward_euler",
                           sources=sources)
    x = np.linalg.solve(A, b)
    u_expected, i_expected = _recover(network, x, info)

    original = spice._assemble
    calls = []

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(spice, "_assemble", counting)
    _, u, i_branch = solver.step(DT, state, sources=sources)

    assert len(calls) == 1
    assert np.array_equal(u, u_expected)
    assert np.array_equal(i_branch, i_expected)

    # and it reports "no iteration happened", rather than a fake 1
    result = _solve_step(network, DT, state.u, state.i_branch, "backward_euler",
                         sources=sources)
    assert result[2] == 0


# --------------------------------------------------------------------------
# a half-wave rectifier: compared against an exact reference waveform
# --------------------------------------------------------------------------


def _reference_output(v_in, diode, r_load):
    """The exact quasi-static ``v_out`` for this ``v_in``, by bisection on KCL.

    This network has **no capacitor and no inductor**, so backward Euler's
    companion models contribute nothing: there is no ``u_prev`` term and no
    ``i_prev`` term in the system, and the discrete solution at ``t^{n+1}``
    *is* the exact solution at ``t^{n+1}``.  Time discretisation therefore
    introduces exactly zero error here, which is what lets the trace below be
    compared to this reference at Newton tolerance rather than to a few
    percent.

    Kirchhoff at the output node: the diode's branch current equals the load
    current, with ``vd = v_in - v_out``,

        ``isat*(exp(vd/(n*vt)) - 1) + gmin*vd == v_out / r_load``

    including the ``gmin`` term on the junction side, so the equation is the
    same one the solver's stamp encodes and not a simplification of it.  The
    residual is strictly decreasing in ``v_out`` (the junction conductance and
    ``1/r_load`` are both positive), so one bracket suffices: at ``v_out = 0``
    the residual is ``i(v_in)`` and at ``v_out = v_in`` it is ``-v_in/r_load``,
    which always straddle zero.
    """
    if v_in == 0.0:
        return 0.0
    lo, hi = (0.0, v_in) if v_in > 0.0 else (v_in, 0.0)

    def residual(v_out):
        return diode.current(v_in - v_out) - v_out / r_load

    assert residual(lo) > 0.0 > residual(hi)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if residual(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def test_half_wave_rectifier_matches_an_exact_reference_waveform():
    network, voltages = _run_by_hand()
    diode = network.branches[1]
    v_in = voltages[:, V_IN]
    v_out = voltages[:, V_OUT]
    reference = np.array([_reference_output(v, diode, R_LOAD) for v in v_in])

    # Not a discretisation tolerance: this circuit has no memory, so the only
    # error left is the Newton convergence floor.  Measured over all 500 steps:
    # max |solver - reference| = 1.8e-15 V.
    assert np.max(np.abs(v_out - reference)) < 1e-6

    # The shape, with every expected value taken from the reference rather than
    # from a hand formula.  Measured: peak 4.30751 V, min -5.01e-9 V,
    # min(v_in) -5.0 V, mean(v_out) 1.26854 V, mean(v_in) -7.7e-17 V, and 0.39
    # of the samples above 1 V.
    assert np.all(np.isfinite(v_out))
    assert v_out.max() == pytest.approx(reference.max(), abs=1e-6)
    # the peak is the source peak *minus* the junction drop: 5 - 0.6963
    assert v_out.max() == pytest.approx(SOURCE_AMPLITUDE - 0.6963, abs=0.02)
    assert v_out.max() < SOURCE_AMPLITUDE

    # negative halves are blocked: the output sits on the reverse leakage,
    # nine orders of magnitude below the forward drop and nowhere near -5 V
    assert v_out.min() < 1e-4
    assert v_out.min() == pytest.approx(reference.min(), abs=1e-12)
    assert v_in.min() == pytest.approx(-SOURCE_AMPLITUDE, abs=1e-9)

    # a rectified sine has real DC content while the input has none
    mean_out = float(np.mean(v_out))
    assert mean_out > 1.0
    assert mean_out == pytest.approx(float(np.mean(reference)), abs=1e-6)
    assert abs(float(np.mean(v_in))) < 0.1

    # v_out > 1 V exactly where 5 sin(theta) - 0.6963 > 1, i.e. over
    # (pi - 2*asin(1.6963/5)) / (2pi) = 0.39 of the cycle -- and read off the
    # reference here, so the number is checked, not assumed
    fraction_high = float(np.mean(v_out > 1.0))
    assert fraction_high == pytest.approx(
        float(np.mean(reference > 1.0)), abs=1e-12
    )
    assert 0.35 < fraction_high < 0.45


# --------------------------------------------------------------------------
# netlists: a 'D' element reaches the same circuit the API builds
# --------------------------------------------------------------------------


NETLIST_DOCUMENT = {
    "name": "half-wave",
    "elements": [
        {"kind": "V", "name": "src", "nodes": ["in", "0"],
         "waveform": {"type": "sine", "amplitude": SOURCE_AMPLITUDE,
                      "frequency": FREQUENCY}},
        {"kind": "D", "name": "d1", "nodes": ["in", "out"]},
        {"kind": "R", "name": "load", "nodes": ["out", "0"], "value": R_LOAD},
    ],
}


def test_netlist_d_builds_the_same_network_as_the_api():
    netlist = parse_netlist(NETLIST_DOCUMENT)
    # 'in' appears first, then 'out': names are numbered in that order
    assert netlist.node_index["in"] == V_IN
    assert netlist.node_index["out"] == V_OUT

    branch = netlist.network.branches[1]
    assert isinstance(branch, Diode)
    assert branch == Diode((V_IN, V_OUT))  # defaults are the model's defaults
    assert netlist.network == _half_wave_network()

    # a diode has a model, not a value; the record says so with 0.0
    element = netlist.elements[1]
    assert element.kind == "D"
    assert element.value == 0.0
    assert not element.is_source
    # the source's own frozen value is its DC level, 0 here, with the 5 V
    # amplitude carried by the waveform -- which is why it matches the
    # hand-built network exactly
    assert netlist.elements[0].value == 0.0
    assert netlist.elements[0].waveform is not None


def test_netlist_d_transient_reproduces_the_hand_run():
    netlist = parse_netlist(NETLIST_DOCUMENT)
    result = netlist.transient(dt=DT, n_steps=STEPS)
    _, voltages = _run_by_hand()

    # row 0 is the t = 0 initial state; the steps follow
    assert result.node_voltages.shape == (STEPS + 1, 3)
    assert np.all(result.node_voltages[0] == 0.0)
    assert np.allclose(result.node_voltages[1:], voltages, rtol=0.0, atol=1e-12)
    assert result.v["out"][-1] == pytest.approx(voltages[-1, V_OUT], abs=1e-12)


def test_netlist_d_rejects_a_diode_value_and_unknown_model_fields():
    with_value = {
        "elements": [
            {"kind": "D", "name": "d1", "nodes": [1, 0], "value": 0.7},
        ]
    }
    with pytest.raises(NetlistError):
        parse_netlist(with_value)

    bad_model = {
        "elements": [
            {"kind": "D", "name": "d1", "nodes": [1, 0], "saturation": 1e-14},
        ]
    }
    with pytest.raises(NetlistError):
        parse_netlist(bad_model)

    # a bad parameter value is reported against the model field, not 'value'
    bad_number = {
        "elements": [
            {"kind": "D", "name": "d1", "nodes": [1, 0], "isat": -1.0},
        ]
    }
    with pytest.raises(NetlistError) as printed:
        parse_netlist(bad_number)
    assert "isat" in str(printed.value)
