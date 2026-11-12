"""The writer's ``s11.station_phasors`` block: the fit's inputs, re-runnable.

Pre-registered with the dispatch ``s11-writer-station-phasors-2026-11-04``: a
synthetic forward/backward pair is pushed through the SAME path the artefact
takes -- ``_station_phasor_block`` -> ``json.dumps``/``json.loads`` -> complex
recombination -> ``emfit.ports.fit_station_impedance`` -- and the resulting
``gamma_v = amp_v[1] / amp_v[0]`` must come back as ``B / A`` to 1e-10 in
magnitude and in phase.  A refit at a 2% different beta must NOT agree, which is
what makes the first assertion evidence rather than a tautology.  A second,
separate group of tests pins the writer's passivity gate (``passivity_guard``):
a published ``|S11|^2 + |S21|^2`` above ``1 + PASSIVITY_TOL`` is FLAGGED, and
the magnitudes are never clipped to make the pair pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from emfit.ports import fit_station_impedance


def _load_run_build_a():
    """Import ``evidence/termination/run_build_A.py`` as a module."""
    evidence = Path(__file__).resolve().parents[1] / "evidence" / "termination"
    if str(evidence) not in sys.path:
        sys.path.insert(0, str(evidence))
    import run_build_A

    return run_build_A


# A line constant and a standing wave on eight stations over 15.4 mm: beta from
# 5 GHz on an effective index near 2.5, A the forward wave, B the reflected one,
# Z0 the line.  Every number below is synthetic; no solver is involved.
BETA = 2.0 * np.pi * 5.0e9 / 2.0e8
X_M = np.array([1.0, 3.2, 5.4, 7.6, 9.8, 12.0, 14.2, 16.4]) * 1e-3
A = 0.73 + 0.11j
B = 0.21 - 0.34j
Z0 = 47.5 + 1.8j


def _synthetic_record(*, n_stations: int = X_M.size, beta_used: float = BETA,
                      fit_beta=None, geometry=None) -> SimpleNamespace:
    """A ``MicrostripWave``-shaped stand-in: only the fields the block reads."""
    u = X_M[:n_stations] - X_M[0]
    fwd = A * np.exp(-1j * BETA * u)
    bwd = B * np.exp(1j * BETA * u)
    return SimpleNamespace(
        station_x=X_M[:n_stations],
        v_stations=fwd + bwd,
        i_stations=fwd / Z0 - bwd / Z0,
        beta=beta_used,
        beta_two_wave=beta_used,
        station_fit=SimpleNamespace(
            beta=beta_used if fit_beta is None else fit_beta),
        deembed_distance=1.0e-3,
        geometry=geometry,
    )


def _through_the_file(block: dict):
    """Serialise, reload, recombine: what a reader of the artefact actually does."""
    text = json.dumps(block)
    assert "NaN" not in text and "Infinity" not in text
    reloaded = json.loads(text)
    x = np.array(reloaded["x_m"], dtype=float)
    v = np.array(reloaded["v_re"], dtype=float) + 1j * np.array(reloaded["v_im"], dtype=float)
    i = np.array(reloaded["i_re"], dtype=float) + 1j * np.array(reloaded["i_im"], dtype=float)
    return reloaded, x, v, i


def test_station_phasors_round_trip_reproduces_gamma_v():
    run_build_A = _load_run_build_a()
    record = _synthetic_record()
    block = run_build_A._station_phasor_block(record)

    assert block["status"] == "ok"
    assert block["n"] == X_M.size
    reloaded, x, v, i = _through_the_file(block)

    # Full float64: the arrays survive the file bit for bit, not "close enough".
    assert np.array_equal(x, record.station_x)
    assert np.array_equal(v, record.v_stations)
    assert np.array_equal(i, record.i_stations)

    fit = fit_station_impedance(x, v, i, reloaded["beta_used"])
    expected = B / A
    assert abs(fit.gamma_v - expected) < 1e-10
    assert abs(abs(fit.gamma_v) - abs(expected)) < 1e-10
    assert abs(np.angle(fit.gamma_v) - np.angle(expected)) < 1e-10


def test_a_different_beta_does_not_agree():
    """The same phasors at beta * 1.02 must miss B/A by far more than 1e-10."""
    run_build_A = _load_run_build_a()
    block = run_build_A._station_phasor_block(_synthetic_record())
    _, x, v, i = _through_the_file(block)

    fit = fit_station_impedance(x, v, i, block["beta_used"] * 1.02)
    assert abs(fit.gamma_v - B / A) > 1e-3


def test_beta_used_is_the_beta_the_fit_was_given_and_beta_one_is_null():
    run_build_A = _load_run_build_a()
    # res.beta deliberately differs: StationFit.beta is the one that was used.
    block = run_build_A._station_phasor_block(
        _synthetic_record(beta_used=123.0, fit_beta=BETA))

    assert block["beta_used"] == pytest.approx(BETA)
    assert block["beta_two"] == pytest.approx(123.0)
    # Not stored on the record at all, so it is null rather than faked.
    assert block["beta_one"] is None
    assert block["deembed_distance_m"] == pytest.approx(1.0e-3)
    assert set(block) == {
        "status", "n", "x_m", "js", "fit_x", "fit_selected",
        "v_re", "v_im", "i_re", "i_im",
        "beta_used", "beta_one", "beta_two", "deembed_distance_m", "note",
    }


def test_a_mismatched_length_is_unavailable_not_partial():
    run_build_A = _load_run_build_a()
    res = _synthetic_record()
    res.v_stations = res.v_stations[:-1]  # one station short of x_m

    block = run_build_A._station_phasor_block(res)

    assert block["status"] == "unavailable"
    for key in ("n", "x_m", "js", "fit_x", "fit_selected",
                "v_re", "v_im", "i_re", "i_im",
                "beta_used", "beta_one", "beta_two", "deembed_distance_m"):
        assert block[key] is None
    assert "station_x" in block["note"]
    _through_the_file(block)
    # Both branches emit the same key set, as the note promises.
    ok = _load_run_build_a()._station_phasor_block(_synthetic_record())
    assert set(block) == set(ok)


# The station columns the study publishes for the reference geometry: eight
# stations, the last one sitting on the lumped load's column (50), so the
# impedance fit saw the first seven -- the shape emfit/studies.py:3817-3821
# writes and the artefact quotes as station_fit_cells/station_fit_n.
CELLS = [3, 8, 13, 18, 23, 28, 33, 50]
GEOMETRY = {
    "cell": 0.4e-3,
    "station_cells": CELLS,
    "station_fit_cells": CELLS[:-1],
    "station_fit_n": len(CELLS) - 1,
    "load_station_excluded": True,
}


def test_the_selection_keys_name_the_stations_the_fit_was_handed():
    run_build_A = _load_run_build_a()
    record = _synthetic_record(geometry=dict(GEOMETRY))
    block = run_build_A._station_phasor_block(record)

    assert block["status"] == "ok"
    assert block["js"] == CELLS
    assert block["fit_selected"] == [True] * 7 + [False]
    assert len(block["fit_selected"]) == block["n"]
    # The full station list is still written; only the selection is a subset.
    assert block["x_m"] == [float(v) for v in X_M]
    assert block["fit_x"] == [float(v) for v in X_M[:7]]

    # And the selection is usable: refitting the rows it names reproduces B/A,
    # so fit_x and fit_selected line up with v_re/v_im/i_re/i_im row for row.
    reloaded, x, v, i = _through_the_file(block)
    mask = np.array(reloaded["fit_selected"], dtype=bool)
    fit = fit_station_impedance(x[mask], v[mask], i[mask],
                               reloaded["beta_used"])
    assert np.array_equal(x[mask], np.array(reloaded["fit_x"], dtype=float))
    assert abs(fit.gamma_v - B / A) < 1e-10


def test_a_record_without_the_cells_leaves_the_selection_null_not_guessed():
    run_build_A = _load_run_build_a()
    # No geometry at all, and a geometry whose fit cells are inconsistent with
    # the station rows: both write null rather than a selection the writer
    # cannot know (the rule is emfit's, not the writer's).
    inconsistent = dict(GEOMETRY, station_fit_n=len(CELLS))
    for record in (_synthetic_record(),
                   _synthetic_record(geometry=inconsistent)):
        block = run_build_A._station_phasor_block(record)
        assert block["status"] == "ok"
        assert block["js"] is None
        assert block["fit_x"] is None
        assert block["fit_selected"] is None
        _through_the_file(block)


# The passivity gate, in both directions.  A gate that only ever said "ok" would
# be indistinguishable from no gate at all, so the failing case is pinned beside
# the passing one -- and pinned as a FLAG, not a repair: the sum that failed has
# to come back at its real value, because a gate that clipped |S11| or |S21| to
# make the pair passive would destroy the very numbers it exists to report.


def test_a_sum_over_one_is_flagged_not_clipped():
    run_build_A = _load_run_build_a()
    record = run_build_A.passivity_guard(0.8, 0.7)  # 0.64 + 0.49 = 1.13

    assert record["status"] == "FAIL_PASSIVITY"
    # The real sum, not 1.0: a clipping implementation could only report 1.0.
    assert record["power_sum"] == pytest.approx(1.13)
    assert record["power_sum"] > 1.0
    assert record["tolerance"] == pytest.approx(4.0e-9)
    # Nothing was silently repaired, and the failing pair is still quotable.
    assert "unclipped" in record["basis"]
    assert "not passive" in record["verdict"]
    assert set(record) == {"status", "power_sum", "tolerance", "basis", "verdict"}


def test_a_sum_of_exactly_one_is_not_flagged():
    run_build_A = _load_run_build_a()
    record = run_build_A.passivity_guard(0.6, 0.8)  # 0.36 + 0.64 = 1.00

    assert record["status"] is None
    assert record["power_sum"] == pytest.approx(1.0)
    # A null status is the signal the caller uses to leave the record's own
    # validation_status alone; the key set is identical to the fired branch's,
    # so a reader never has to guess which one wrote the file.
    assert set(record) == set(run_build_A.passivity_guard(0.8, 0.7))


def test_an_absent_magnitude_is_not_evaluated_rather_than_flagged():
    run_build_A = _load_run_build_a()
    fired = set(run_build_A.passivity_guard(0.8, 0.7))
    for s11_mag, s21_mag in ((None, 0.7), (0.8, None)):
        record = run_build_A.passivity_guard(s11_mag, s21_mag)
        # An absent number is not evidence of passivity, and it is not evidence
        # of a violation either: the gate declines to rule.
        assert record["status"] is None
        assert record["power_sum"] is None
        assert set(record) == fired
