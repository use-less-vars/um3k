"""The writer's ``s11.station_phasors`` block: the fit's inputs, re-runnable.

Pre-registered with the dispatch ``s11-writer-station-phasors-2026-11-04``: a
synthetic forward/backward pair is pushed through the SAME path the artefact
takes -- ``_station_phasor_block`` -> ``json.dumps``/``json.loads`` -> complex
recombination -> ``emfit.ports.fit_station_impedance`` -- and the resulting
``gamma_v = amp_v[1] / amp_v[0]`` must come back as ``B / A`` to 1e-10 in
magnitude and in phase.  A refit at a 2% different beta must NOT agree, which is
what makes the first assertion evidence rather than a tautology.
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
                      fit_beta=None) -> SimpleNamespace:
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
        "status", "n", "x_m", "v_re", "v_im", "i_re", "i_im",
        "beta_used", "beta_one", "beta_two", "deembed_distance_m", "note",
    }


def test_a_mismatched_length_is_unavailable_not_partial():
    run_build_A = _load_run_build_a()
    res = _synthetic_record()
    res.v_stations = res.v_stations[:-1]  # one station short of x_m

    block = run_build_A._station_phasor_block(res)

    assert block["status"] == "unavailable"
    for key in ("n", "x_m", "v_re", "v_im", "i_re", "i_im",
                "beta_used", "beta_one", "beta_two", "deembed_distance_m"):
        assert block[key] is None
    assert "station_x" in block["note"]
    _through_the_file(block)
