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
import sys
from pathlib import Path

import numpy as np
import pytest

from emfit.netlist import NetlistError, parse_netlist
from emfit.spice import Branch, CircuitNetwork, TransmissionLine
from emfit.studies import _quarter_wave_retune

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


# --------------------------------------------------------------------------
# a line's delay is DECLARED as a tone and DERIVED from the tone in use
# --------------------------------------------------------------------------
# ``load_stub.json`` (evidence/termination/netlists/) — the C arm's
# termination, a shorted stub hung on the cut — cut for the tone every banked A
# artefact reports, and for the tone the SAME 6 GHz request is analysed at once
# ``excite='pulse'`` sets ``n_warm = 0``.  Both are ``emfit.studies.snapped_tone``
# bins at ``nsteps = 2400`` on the default mesh, and they are 3 % apart:
# ``round(6e9 * 1800 dt) / (1800 dt)`` versus ``round(6e9 * 2400 dt) / (2400 dt)``.
F_CW = 5827786408.327286
F_PULSE = 6009904733.587513
TAU_CW = 4.289793456444743e-11       # 1/(4 F_CW)    = 42.89793456444743 ps
TAU_PULSE = 4.159799715340357e-11    # 1/(4 F_PULSE) = 41.59799715340357 ps
#: The default mesh's step (cell 0.4 mm): ``TAU_CW / dt = 56.25`` and
#: ``TAU_PULSE / dt = 54.5454...``, so neither delay lands on a sample.
MS_DT = 7.626299478123987e-13
#: Where ``emfit.studies.microstrip_wave`` records the pair it actually used.
QW_KEY = "load_netlist_quarter_wave"


def _stub_doc(*, tau=TAU_CW, declared_hz=F_CW):
    """The C arm's termination: a 50 ohm stub shorted at its far end.

    The document says two things about its line -- ``tau`` and, optionally, the
    tone that delay was cut for -- and the parser holds it to both: ``tau``
    must BE ``quarter_wave_tau(quarter_wave_hz)``, so a file cannot claim one
    tone and carry another's delay.
    """
    stub = {"kind": "T", "name": "stub", "nodes": ["1", "2"],
            "z0": 50.0, "tau": tau}
    if declared_hz is not None:
        stub["quarter_wave_hz"] = declared_hz
    return {
        "name": "load_stub",
        "nodes": ["1", "0", "2"],
        "elements": [
            stub,
            {"kind": "V", "name": "short", "nodes": ["2", "0"], "value": 0.0},
        ],
    }


def _stub_tau(netlist):
    """The delay the built branch actually carries, in seconds."""
    branch = netlist.network.branches[netlist.element_index["stub"]]
    assert isinstance(branch, TransmissionLine), (
        "a 'T' element must build a TransmissionLine branch, not "
        f"{type(branch).__name__}"
    )
    return branch.tau


def test_a_declared_tone_is_rederived_for_the_tone_in_use():
    """``f_hz`` replaces the declared line's delay; without it, nothing moves.

    The delay a quarter-wave stub has to carry is ``1 / (4 f)`` at the tone the
    run is ANALYSED at, and that tone is not the one a document was written
    for: it is the DFT bin nearest the request, and the bin grid moves with the
    warm-up window (``excite='pulse'`` passes ``n_warm = 0``).  So
    ``parse_netlist(..., f_hz=...)`` delivers ``quarter_wave_tau(f_hz)`` to
    every ``T`` element that declared a tone, and records BOTH delays — the one
    in the file and the one the branch got — in ``Netlist.quarter_wave``.

    Three cases, in the order a caller meets them:

    1. ``f_hz`` given: the branch carries the run's quarter-wave delay, and the
       record says which document number it replaced (a 3 % move here, not a
       rounding).
    2. ``f_hz`` omitted: the document's own delay is delivered unchanged and
       the record keeps ``f_hz = None``.  This is what keeps every existing
       caller byte-identical.
    3. no ``quarter_wave_hz`` declared: there is nothing to re-derive, ``f_hz``
       is a no-op for that element, and the record tuple stays EMPTY — absent
       means "no declaration", never "the tone we used last time".
    """
    # -- 1. the run's tone wins over the document's tau -----------------------
    parsed = parse_netlist(_stub_doc(), f_hz=F_PULSE)
    assert _stub_tau(parsed) == TAU_PULSE, (
        "f_hz= must deliver quarter_wave_tau(f_hz); got "
        f"{_stub_tau(parsed)!r} s for {F_PULSE!r} Hz"
    )
    assert _stub_tau(parsed) != TAU_CW
    assert isinstance(parsed.quarter_wave, tuple) and len(parsed.quarter_wave) == 1
    (record,) = parsed.quarter_wave
    assert set(record) == {"name", "declared_hz", "tau_document_s", "tau_s",
                           "f_hz"}
    assert record["name"] == "stub"
    assert record["declared_hz"] == F_CW
    assert record["tau_document_s"] == TAU_CW
    assert record["tau_s"] == TAU_PULSE
    assert record["f_hz"] == F_PULSE
    # The delivered delay is a quarter wave at the RUN's tone ...
    assert np.isclose(2.0 * np.pi * F_PULSE * _stub_tau(parsed), 0.5 * np.pi,
                      rtol=1e-15, atol=0.0)
    # ... and NOT at the declared one, which is why the substitution matters.
    assert abs(2.0 * np.pi * F_CW * _stub_tau(parsed) - 0.5 * np.pi) > 0.04

    # -- 2. no tone given: the document's own delay, verbatim ------------------
    verbatim = parse_netlist(_stub_doc())
    assert _stub_tau(verbatim) == TAU_CW
    (record,) = verbatim.quarter_wave
    assert record["tau_s"] == record["tau_document_s"] == TAU_CW
    assert record["f_hz"] is None
    # The delay is a quarter wave at the tone the document names, and that is
    # the only tone it could be one at.
    assert np.isclose(2.0 * np.pi * F_CW * _stub_tau(verbatim), 0.5 * np.pi,
                      rtol=1e-15, atol=0.0)

    # -- 3. an undeclared line has no tone to re-derive -----------------------
    plain = parse_netlist(_stub_doc(declared_hz=None), f_hz=F_PULSE)
    assert _stub_tau(plain) == TAU_CW, (
        "f_hz must only move a line that DECLARED a tone: a document with no "
        "'quarter_wave_hz' cannot be re-derived from a tone it never named"
    )
    assert plain.quarter_wave == ()


def test_a_line_may_not_declare_one_tone_and_carry_anothers_delay():
    """The self-check is relative (1e-6), and a bad tone is a document error.

    ``tau ~ 1e-11 s`` makes an absolute delay tolerance meaningless (1e-6 s
    would accept every tone in the band), so the slack is ``1e-6 * tau``: a
    delay written down as a rounded float still agrees with its own tone, while
    the smallest real retune in this tree -- 3 % -- cannot pass.  Both
    directions are pinned below, because a tolerance nobody ever straddles is a
    tolerance nobody has checked.

    A ``quarter_wave_hz`` that is not a finite, positive number is re-raised as
    a :class:`NetlistError` naming the element and the field (``quarter_wave_tau``
    raises the ``ValueError``; the parser owns the wording), so a malformed
    declaration never escapes as a bare ``ValueError`` from inside the build.
    """
    # -- inside the slack: the same tone, written down as a rounded float -----
    parse_netlist(_stub_doc(tau=TAU_CW * (1.0 + 1e-9)))
    parse_netlist(_stub_doc(tau=TAU_CW))

    # -- outside it: a declared tone and a delay that belongs to a different one
    message = (
        r"element 'stub': field 'tau' \(.*\) is not the quarter-wave delay of "
        r"field 'quarter_wave_hz' \(5827786408\.327286 Hz\), which is "
        r"quarter_wave_tau = .* s; a T element may not declare one tone and "
        r"carry another's delay"
    )
    for tau in (TAU_PULSE, TAU_CW * (1.0 + 2e-6), 0.0, float("inf")):
        with pytest.raises(NetlistError, match=message):
            parse_netlist(_stub_doc(tau=tau))

    # -- a tone that is not a tone at all -------------------------------------
    for bad, why in (
        (0.0, r"a quarter-wave tone must be finite and strictly positive"),
        (-F_CW, r"a quarter-wave tone must be finite and strictly positive"),
        (float("nan"), r"a quarter-wave tone must be finite and strictly positive"),
        ("fast", r"a quarter-wave tone must be a number in hertz"),
        ("", r"a quarter-wave tone must be a number in hertz"),
    ):
        with pytest.raises(
            NetlistError,
            match=r"element 'stub': field 'quarter_wave_hz': " + why,
        ):
            parse_netlist(_stub_doc(declared_hz=bad))


def test_a_moved_tone_is_warned_about_and_recorded_never_raised(capsys):
    """A tone that moved is REPORTED, not refused -- and the pair is recorded.

    ``_quarter_wave_retune`` is what ``microstrip_wave`` calls with the parsed
    records and the tone the run is actually analysed at.  A moved tone is
    warned about on stderr and kept: the run about to be launched is
    self-consistent (``tau`` is now the quarter-wave delay of its OWN tone), so
    raising would refuse a correct run and destroy the forensic record of a
    tone that moved, which is the one thing this check exists to keep.

    The warning has to carry everything a reader needs to reproduce the pair:
    both tones, both delays, the step they are counted in, and where the pair is
    written in the artefact.
    """
    doc = _stub_doc()

    # -- the CW-document / pulse-run case that actually happened -------------
    # These are the records of a parse at the RUN's tone: ``tau_s`` is already
    # the pulse delay, so this call only labels the pair and shouts about it.
    records = parse_netlist(doc, f_hz=F_PULSE).quarter_wave
    report = _quarter_wave_retune(records, F_PULSE, dt=MS_DT)
    assert isinstance(report, tuple) and len(report) == 1
    (entry,) = report
    assert entry["name"] == "stub"
    assert entry["declared_hz"] == F_CW
    assert entry["f_hz"] == F_PULSE
    assert entry["declared_tone_retuned"] is True
    assert entry["tau_document_s"] == TAU_CW
    assert entry["tau_s"] == TAU_PULSE
    steps = (f"(tau/dt = {TAU_CW / MS_DT!r} -> {TAU_PULSE / MS_DT!r})")
    err = capsys.readouterr().err
    for needle in (
        "=" * 78,
        "QUARTER-WAVE TONE MISMATCH",
        "netlist element 'stub' declares a quarter-wave line",
        "at 5.827786 GHz, but this run is ANALYSED at",
        "6.009905 GHz.",
        f"Its tau has been re-derived for the tone in use: {TAU_CW!r} s -> "
        f"{TAU_PULSE!r} s {steps}.",
        "--vis-dump",
        f"geometry['{QW_KEY}']",
    ):
        assert needle in err, (
            f"the warning must contain {needle!r}; stderr was:\n{err}"
        )

    # -- a tone that did not move is silent, and says so in the record -------
    still = _quarter_wave_retune(parse_netlist(doc, f_hz=F_CW).quarter_wave,
                                 F_CW, dt=MS_DT)
    assert [e["declared_tone_retuned"] for e in still] == [False]
    assert capsys.readouterr().err == ""

    # -- an ALREADY-PARSED Netlist keeps its frozen delay, and the warning
    #    says so instead of claiming a re-derivation that did not happen ------
    frozen = _quarter_wave_retune(parse_netlist(doc).quarter_wave, F_PULSE,
                                 dt=MS_DT)
    (entry,) = frozen
    assert entry["declared_tone_retuned"] is True
    assert entry["tau_s"] == entry["tau_document_s"] == TAU_CW
    err = capsys.readouterr().err
    assert "Its tau was NOT re-derived:" in err
    assert "arrived already parsed" in err
    assert "re-derived for the tone in use" not in err
    assert "Raising here was" in err

    # -- and the step is optional: without it the warning drops the tau/dt pair
    #    rather than inventing one ---------------------------------------------
    _quarter_wave_retune(parse_netlist(doc, f_hz=F_PULSE).quarter_wave, F_PULSE)
    err = capsys.readouterr().err
    assert "tau/dt" not in err
    assert "QUARTER-WAVE TONE MISMATCH" in err


def _load_run_build_a():
    """Import ``evidence/termination/run_build_A.py`` as a module.

    The runner, not the library: the record above is built by
    ``emfit.studies`` and then has to survive the writer that puts it in the
    artefact.  ``tests/test_writer_station_phasors.py`` loads the same file the
    same way.
    """
    evidence = Path(__file__).resolve().parents[1] / "evidence" / "termination"
    if str(evidence) not in sys.path:
        sys.path.insert(0, str(evidence))
    import run_build_A

    return run_build_A


def test_the_writer_carries_a_declared_tone_into_the_artefact():
    """A declared tone reaches ``geometry[QW_KEY]`` -- matching tone or not.

    ``microstrip_wave`` writes the key only when a ``T`` element declared a
    tone, and the runner rebuilds ``geometry`` from scalars, so a list of dicts
    is dropped unless it is carried across by hand -- the same reason
    ``load_records`` exists for ``loads``.  Both halves are pinned here:

    1. a declared tone is PRESENT, and the record says whether it moved,
       because the MATCHED case is the one a reader has to be able to tell
       apart from a document that declared no tone at all;
    2. nothing declared (and no netlist at all) is EMPTY, so the writer's
       ``if qw:`` leaves the key out and a netlist-free geometry is unchanged.
    """
    runner = _load_run_build_a()
    doc = _stub_doc()

    # -- declared, and the run's tone: present, labelled NOT moved -----------
    matched = runner.quarter_wave_records(
        _quarter_wave_retune(parse_netlist(doc, f_hz=F_CW).quarter_wave, F_CW))
    assert len(matched) == 1
    (entry,) = matched
    assert set(entry) == {"name", "declared_hz", "tau_document_s", "tau_s",
                          "f_hz", "declared_tone_retuned"}
    assert entry["name"] == "stub"
    assert entry["declared_hz"] == F_CW
    assert entry["tau_document_s"] == TAU_CW
    assert entry["tau_s"] == TAU_CW
    assert entry["f_hz"] == F_CW
    assert entry["declared_tone_retuned"] is False
    # plain JSON, because that is what the writer puts in the artefact
    assert json.loads(json.dumps(matched)) == matched

    # -- declared, and the run's tone MOVED: present, and it says so ---------
    (entry,) = runner.quarter_wave_records(
        _quarter_wave_retune(parse_netlist(doc, f_hz=F_PULSE).quarter_wave,
                            F_PULSE))
    assert entry["declared_hz"] == F_CW
    assert entry["tau_document_s"] == TAU_CW
    assert entry["tau_s"] == TAU_PULSE
    assert entry["f_hz"] == F_PULSE
    assert entry["declared_tone_retuned"] is True

    # -- nothing declared: EMPTY, so the key is never added ------------------
    assert runner.quarter_wave_records(_quarter_wave_retune(
        parse_netlist(_stub_doc(declared_hz=None), f_hz=F_CW).quarter_wave,
        F_CW)) == []
    # ... including the geometry of a run with no netlist at all, where the
    #     read is a miss on a dict that never had the key
    assert runner.quarter_wave_records({}.get(QW_KEY)) == []
    assert runner.quarter_wave_records(None) == []

