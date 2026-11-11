"""Tests for :mod:`emfit.netlist`: the JSON parser and the transient driver.

The headline test is the RC low-pass step response, because it is the one case
where the answer is known in closed form.  Backward Euler is first order, so the
test asserts *three* separate things rather than one loose tolerance: the shape
(monotone, starting at zero, ending at the step level), the time constant the
discrete solution actually has (``RC * h / ln(1 + h)``, a prediction that is
exact, not approximate), and the measured convergence order when ``dt`` is
halved.  Every tolerance below is argued where it is used.
"""

import json

import numpy as np
import pytest

from emfit.netlist import NetlistError, parse_netlist
from emfit.spice import Branch, CircuitNetwork

# The document from the module docstring: 1 kOhm / 100 nF low pass, so
# RC = 1e-4 s, driven by a 1 V step through "vin".
RC = 1e-4


def _rc_doc():
    return {
        "name": "rc_lowpass",
        "elements": [
            {
                "kind": "V",
                "name": "vin",
                "nodes": ["in", "0"],
                "value": 0.0,
                "waveform": {"type": "step", "amplitude": 1.0},
            },
            {"kind": "R", "name": "r1", "nodes": ["in", "out"], "value": 1000.0},
            {"kind": "C", "name": "c1", "nodes": ["out", "0"], "value": 1e-7},
        ],
    }


def _rc_run(dt, n_steps):
    return parse_netlist(_rc_doc()).transient(dt=dt, n_steps=n_steps)


def _element(overrides):
    """One valid RC document with ``elements[k]`` patched by ``overrides``."""
    doc = _rc_doc()
    for index, patch in overrides.items():
        doc["elements"][index].update(patch)
    return doc


# --------------------------------------------------------------------------
# the headline: RC step response against the analytic solution
# --------------------------------------------------------------------------
def test_rc_lowpass_step_response_against_the_analytic_solution():
    dt, n_steps = 5e-6, 100  # t_end = 5e-4 s = 5 RC
    result = _rc_run(dt, n_steps)
    v_out = result.v["out"]
    amplitude = 1.0

    # -- shape -------------------------------------------------------------
    # The record starts at t = 0 before any step: the source has not risen yet
    # and the capacitor is uncharged, so the first row is exactly the zero state.
    assert result.t[0] == 0.0
    assert v_out[0] == 0.0
    assert len(result.t) == n_steps + 1 == result.n_records
    # An RC charging curve is monotone; a step response that overshoots or
    # rings would be a wrong companion model, not a tolerance problem.
    assert np.all(np.diff(v_out) > 0.0)

    # -- final value -------------------------------------------------------
    # Bounding the last value by "close to amplitude" was the wrong assertion:
    # even the *continuous* solution only reaches 1 - e^-5 = 0.9932621 at 5 RC,
    # i.e. 6.7e-3 short of the step level, so no correct solver can be within
    # 1e-3 of amplitude at this time.  Compare with the analytic value at the
    # same instant instead, at a tolerance smaller than BE's own lag there
    # (measured: discrete 0.9923955, |diff| = 8.7e-4 for h = dt/RC = 0.05).
    exact_at_5rc = amplitude * (1.0 - np.exp(-5.0))
    assert v_out[-1] == pytest.approx(exact_at_5rc, abs=1e-3)
    # and the gap to the asymptote is the analytic 6.7e-3 plus that lag, so it
    # is bounded by 1e-2 for an O(dt) scheme at dt = 5e-6
    assert abs(v_out[-1] - amplitude) < 1e-2
    # The input node is the source: it is at the step level from the first step
    # on, and its current is the negated capacitor current (series loop).
    assert np.allclose(result.v["in"][1:], amplitude, rtol=0, atol=0)
    assert np.allclose(result.i["vin"][1:], -result.i["c1"][1:], rtol=1e-12)
    # The capacitor current is C dv/dt, positive because dv/dt > 0.
    assert result.i["c1"][-1] > 0.0

    # -- the time constant the discrete solution really has -----------------
    # Backward Euler on v' = (A - v)/RC is v_n = A (1 - (1 + h)**-n) with
    # h = dt/RC, so ln(A - v_n) is exactly linear in n with slope -ln(1 + h).
    # Therefore tau_obs = -dt / slope = RC * h / ln(1 + h), which is NOT RC: it
    # is RC * (1 + h/2 + ...) -- backward Euler is numerically damped.  Assert
    # both facts, so this test would catch a solver that is either wrong or
    # silently a different scheme.
    h = dt / RC
    n = np.arange(1, n_steps + 1)
    slope = float(np.polyfit(n, np.log(amplitude - v_out[1:]), 1)[0])
    tau_observed = -dt / slope
    tau_predicted = RC * h / np.log1p(h)
    # (a) the fit is the exact discrete prediction: agreement to 1e-6 relative
    #     is generous for a least-squares fit of 100 exactly-linear points.
    assert tau_observed == pytest.approx(tau_predicted, rel=1e-6)
    # (b) that prediction is RC(1 + h/2) up to O(h^2): h = 0.05, so the gap to
    #     RC is 2.48%, and asserting "above RC" records the direction of the
    #     numerical damping instead of hiding it inside a tolerance.
    assert tau_observed > RC
    assert tau_observed == pytest.approx(RC * (1.0 + 0.5 * h), rel=1e-3)

    # -- convergence: halving dt halves the error --------------------------
    # Fix T = 2 RC and compare with A(1 - e^{-T/RC}) = 0.86466472.  A first
    # order scheme gives err ~ C dt, so halving dt should halve the error; the
    # observed ratio is 1.966 and the observed order 0.976 (measured, not
    # assumed).  The window (1.5, 2.5) / (0.8, 1.2) admits the O(dt^2) terms
    # that keep the ratio a little below 2 without admitting a different order.
    errors = []
    for step in (2e-5, 1e-5):
        count = int(round(2.0 * RC / step))
        coarse = _rc_run(step, count).v["out"][-1]
        exact = amplitude * (1.0 - np.exp(-(count * step) / RC))
        errors.append(abs(float(coarse) - exact))
    ratio = errors[0] / errors[1]
    observed_order = float(np.log2(ratio))
    assert ratio == pytest.approx(2.0, rel=0.25)
    assert 1.5 < ratio < 2.5
    assert 0.8 < observed_order < 1.2
    # and the error is small in absolute terms: 2.6% of the step at dt = 2e-5
    assert errors[0] < 0.05


# --------------------------------------------------------------------------
# the parse itself
# --------------------------------------------------------------------------
def test_parsed_network_equals_the_hand_built_one():
    netlist = parse_netlist(_rc_doc())
    expected = CircuitNetwork(
        branches=(
            Branch("V", (1, 0), 0.0),
            Branch("R", (1, 2), 1000.0),
            Branch("C", (2, 0), 1e-7),
        ),
        n_nodes=3,
    )
    assert netlist.network == expected


def test_name_and_index_maps_round_trip():
    netlist = parse_netlist(_rc_doc())
    assert netlist.name == "rc_lowpass"
    # deterministic numbering: ground 0, then names in first-appearance order
    assert netlist.node_index["out"] == 2
    assert netlist.node_names[2] == "out"
    assert netlist.node_index["in"] == 1
    assert netlist.node_names[0] == "0"
    assert netlist.element_index["c1"] == 2
    assert netlist.element("c1").nodes == (2, 0)
    assert netlist.element("c1").index == 2
    assert [element.name for element in netlist.elements] == ["vin", "r1", "c1"]
    assert [element.is_source for element in netlist.elements] == [True, False, False]


def test_bare_value_is_a_dc_source():
    """A source with a ``value`` and no ``waveform`` holds that level forever."""
    netlist = parse_netlist(
        {
            "elements": [
                {"kind": "V", "name": "vin", "nodes": ["in", "0"], "value": 2.0},
                {"kind": "R", "name": "r1", "nodes": ["in", "0"], "value": 1000.0},
            ]
        }
    )
    assert netlist.element("vin").waveform is None
    assert np.allclose(netlist.source_values(0.0), [2.0, 1000.0])
    result = netlist.transient(dt=1e-6, n_steps=2)
    # row 0 is the initial (all-zero) state, so the source level shows from step 1
    assert np.allclose(result.v["in"][1:], 2.0)


def test_source_level_is_value_plus_waveform():
    doc = _element({0: {"value": 0.5, "waveform": {"type": "step", "amplitude": 2.0}}})
    netlist = parse_netlist(doc)
    assert netlist.source_values(0.0)[0] == pytest.approx(2.5)  # right-continuous
    assert netlist.waveforms[0].amplitude == 2.0
    assert netlist.waveforms[1] is None


def test_dc_divider_matches_hand_arithmetic():
    """10 V across 1 k in series with 3 k: the tap sits at 7.5 V exactly."""
    netlist = parse_netlist(
        {
            "elements": [
                {"kind": "V", "name": "vin", "nodes": ["in", "0"], "value": 10.0},
                {"kind": "R", "name": "r1", "nodes": ["in", "out"], "value": 1000.0},
                {"kind": "R", "name": "r2", "nodes": ["out", "0"], "value": 3000.0},
            ]
        }
    )
    result = netlist.transient(dt=1e-6, n_steps=3)
    # purely resistive, so the answer is reached in one step and to round-off;
    # row 0 is the initial all-zero state, so the source is applied from row 1 on
    assert np.allclose(result.v["out"][1:], 7.5, rtol=1e-12, atol=0)
    assert np.allclose(result.i["r1"][1:], 2.5e-3, rtol=1e-12, atol=0)


@pytest.mark.parametrize("ground", ["0", 0, "gnd", "ground"])
def test_ground_spellings(ground):
    netlist = parse_netlist(
        {
            "elements": [
                {"kind": "V", "name": "vin", "nodes": ["in", ground], "value": 1.0},
                {"kind": "R", "name": "r1", "nodes": ["in", ground], "value": 1000.0},
            ]
        }
    )
    assert netlist.node_index["0"] == 0
    assert netlist.elements[0].nodes[1] == 0
    assert netlist.elements[1].nodes[1] == 0


def test_integer_node_references_are_indices():
    netlist = parse_netlist(
        {
            "nodes": ["a"],
            "elements": [
                {"kind": "V", "name": "vin", "nodes": [1, 0], "value": 1.0},
                {"kind": "R", "name": "r1", "nodes": [1, "a"], "value": 1000.0},
                {"kind": "C", "name": "c1", "nodes": ["a", 3], "value": 1e-9},
                {"kind": "R", "name": "r2", "nodes": [3, 0], "value": 1.0},
            ],
        }
    )
    # Explicit indices are reserved first (0, 1 and 3), so numbering continues
    # above the highest of them -- next_free = max(indices) + 1 = 4 -- and the
    # declared name "a" takes 4.  The rule is "above the highest explicit
    # index", not "fill the gaps", so node 2 is deliberately left unnamed.
    assert netlist.node_index["a"] == 4
    assert netlist.network.n_nodes == 5
    assert netlist.elements[1].nodes == (1, 4)
    assert netlist.elements[2].nodes == (4, 3)


def test_unnamed_explicit_index_still_gets_a_name():
    netlist = parse_netlist(
        {
            "elements": [
                {"kind": "V", "name": "vin", "nodes": [1, 0], "value": 1.0},
                {"kind": "R", "name": "r1", "nodes": [1, 4], "value": 1000.0},
                {"kind": "C", "name": "c1", "nodes": [4, 0], "value": 1e-9},
            ]
        }
    )
    assert netlist.node_names[4] == "4"
    assert netlist.node_index["4"] == 4
    assert netlist.node_names == ("0", "1", "2", "3", "4")


def test_step_delay_holds_the_source_at_zero():
    doc = _element({0: {"waveform": {"type": "step", "amplitude": 1.0, "delay": 2e-6}}})
    netlist = parse_netlist(doc)
    assert netlist.source_values(1e-6)[0] == 0.0
    assert netlist.source_values(2e-6)[0] == 1.0  # right-continuous
    result = netlist.transient(dt=1e-6, n_steps=4)
    # The driver evaluates sources at t^{n+1}, so each row shows the level one
    # step later than its own t: row 0 is the initial zero state, row 1 is the
    # level at t = 1e-6 (< delay), row 2 the level at t = 2e-6 == delay, which
    # the step reaches because it is right-continuous.
    assert np.allclose(result.v["in"][:2], 0.0)
    assert np.allclose(result.v["in"][2:], 1.0)


def test_sine_is_sampled_at_the_step_times():
    doc = _element(
        {
            0: {
                "waveform": {
                    "type": "sine",
                    "amplitude": 2.0,
                    "frequency": 2500.0,  # period 4e-4 s
                    "phase": 0.0,
                }
            }
        }
    )
    netlist = parse_netlist(doc)
    dt = 1e-5
    result = netlist.transient(dt=dt, n_steps=8)
    expected = 2.0 * np.sin(2.0 * np.pi * 2500.0 * result.t)
    # the source node follows the waveform exactly, so the only error is the
    # linear solve, i.e. round-off
    assert np.allclose(result.v["in"], expected, rtol=0, atol=1e-12)


def test_parse_accepts_dict_json_text_and_path(tmp_path):
    doc = _rc_doc()
    text = json.dumps(doc)
    path = tmp_path / "rc.json"
    path.write_text(text, encoding="utf-8")
    from_dict = parse_netlist(doc)
    from_text = parse_netlist(text)
    from_bytes = parse_netlist(text.encode("utf-8"))
    from_path = parse_netlist(path)
    from_str_path = parse_netlist(str(path))
    for other in (from_text, from_bytes, from_path, from_str_path):
        assert other.network == from_dict.network
        assert other.node_index == from_dict.node_index


def test_simulate_is_the_driver():
    netlist = parse_netlist(_rc_doc())
    result = netlist.simulate(dt=5e-6, t_end=5e-5)
    assert result.n_records == len(netlist.transient(dt=5e-6, n_steps=10).t)


def test_driver_rejects_bad_time_arguments():
    netlist = parse_netlist(_rc_doc())
    with pytest.raises(ValueError, match="exactly one of t_end or n_steps"):
        netlist.transient(dt=1e-6)
    with pytest.raises(ValueError, match="exactly one of t_end or n_steps"):
        netlist.transient(dt=1e-6, t_end=1e-5, n_steps=10)
    with pytest.raises(ValueError, match="dt must be finite and positive"):
        netlist.transient(dt=0.0, n_steps=1)
    with pytest.raises(ValueError, match="shorter than one step"):
        netlist.transient(dt=1e-6, t_end=1e-9)


def test_recorded_arrays_are_read_only():
    result = _rc_run(dt=1e-5, n_steps=2)
    with pytest.raises(ValueError):
        result.node_voltages[0, 1] = 1.0
    with pytest.raises(KeyError, match="no node named"):
        result.v["nope"]
    with pytest.raises(KeyError, match="no element named"):
        result.i["nope"]


# --------------------------------------------------------------------------
# validation: every one of these is an error, none is repaired silently
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "doc, match",
    [
        # unknown kind
        (_element({1: {"kind": "Q"}}), "unknown kind|kind"),
        # missing required field
        (_element({1: {"value": None}}), "field 'value'|value"),
        # extra field on an element
        (_element({1: {"tolerance": 0.05}}), "tolerance"),
        # extra field at the top level
        ({"name": "x", "colour": "red", "elements": _rc_doc()["elements"]}, "colour"),
        # duplicate element name
        (_element({2: {"name": "r1"}}), "r1"),
        # node the netlist never declares, with a `nodes` declaration present
        (
            {
                "nodes": ["in", "out"],
                "elements": [
                    {"kind": "V", "name": "vin", "nodes": ["in", "0"], "value": 1.0},
                    {"kind": "R", "name": "r1", "nodes": ["in", "other"], "value": 1.0},
                ],
            },
            "unknown node name|other",
        ),
        # declared node that nothing reaches
        (
            {
                "nodes": ["in", "out", "spare"],
                "elements": [
                    {"kind": "V", "name": "vin", "nodes": ["in", "0"], "value": 1.0},
                    {"kind": "R", "name": "r1", "nodes": ["in", "out"], "value": 1.0},
                ],
            },
            "no element reaches",
        ),
        # fewer than two distinct nodes
        (
            {
                "elements": [
                    {"kind": "R", "name": "r1", "nodes": ["0", "gnd"], "value": 1.0}
                ]
            },
            "fewer than 2 distinct nodes",
        ),
        # non-positive resistance
        (_element({1: {"value": -1.0}}), "value"),
        # non-finite source level
        (_element({0: {"value": float("inf")}}), "value"),
        # waveform on a non-source
        (
            _element({1: {"waveform": {"type": "step", "amplitude": 1.0}}}),
            "waveform",
        ),
        # source with neither value nor waveform
        (
            {"elements": [{"kind": "V", "name": "vin", "nodes": ["in", "0"]}]},
            "value|waveform",
        ),
        # the reserved pulse waveform is refused, not ignored
        (
            _element({0: {"waveform": {"type": "pulse", "amplitude": 1.0}}}),
            "pulse",
        ),
        # unknown waveform type
        (
            _element({0: {"waveform": {"type": "ramp", "amplitude": 1.0}}}),
            "unknown waveform type|ramp",
        ),
        # sine without a frequency
        (
            _element({0: {"waveform": {"type": "sine", "amplitude": 1.0}}}),
            "frequency",
        ),
        # element nodes must be exactly two references
        (_element({1: {"nodes": ["in", "out", "0"]}}), "nodes"),
        # duplicate node in a `nodes` declaration
        (
            {
                "nodes": ["in", "in"],
                "elements": [
                    {"kind": "R", "name": "r1", "nodes": ["in", "0"], "value": 1.0}
                ],
            },
            "twice",
        ),
        # not a JSON document at all
        ("this is not json", "JSON"),
        # a path that does not exist
        ("no/such/file.json", "neither JSON text"),
    ],
)
def test_netlist_errors(doc, match):
    with pytest.raises(NetlistError, match=match):
        parse_netlist(doc)


def test_netlist_error_is_a_value_error():
    assert issubclass(NetlistError, ValueError)
