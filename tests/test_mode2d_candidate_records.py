"""Tests for :func:`emfit.mode2d.candidate_records`.

The helper exists because a stored artefact that carries only
``Mode2D.candidates`` -- the ``(beta_sq, eps_eff)`` pairs -- cannot be audited:
the curl ratio that distinguishes a physical mode from a spurious gradient mode
is dropped.  These tests pin the record's key set, its JSON-plainness, its
index alignment with the source pairs, and its refusal to paper over a
length mismatch.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from emfit import mode2d as m2

#: Every key a record must carry (a superset is allowed).
KEYS = {"index", "beta", "beta_sq", "eps_eff", "curl_ratio", "abs_curl_ratio"}

#: The walls sit exactly on coordinates, so the node predicates need far less
#: slack than a cell edge.
WALL_TOL = 1e-12


def _stub(candidates, curl_ratio):
    """A minimal stand-in for a :class:`~emfit.mode2d.Mode2D` result."""
    return SimpleNamespace(candidates=tuple(candidates), curl_ratio=tuple(curl_ratio))


def _stub_records():
    """Three candidates: above cutoff, below cutoff, and above cutoff."""
    return _stub(
        [(3.0, 1.5), (-1.0, -0.5), (2.0, 1.0)],
        [1.0e-3, 0.0, -2.0e-3],
    )


# ---------------------------------------------------------------------------
# (a) the diagnostic keys are present
# ---------------------------------------------------------------------------
def test_record_carries_diagnostic_keys():
    """Each record exposes at least the six documented diagnostics."""
    records = m2.candidate_records(_stub_records())
    assert len(records) == 3
    for position, record in enumerate(records):
        assert isinstance(record, dict)
        assert KEYS.issubset(set(record)), f"record {position} keys {sorted(record)}"


# ---------------------------------------------------------------------------
# (b) plain Python types, so a stored payload stays JSON
# ---------------------------------------------------------------------------
def test_record_is_json_serialisable():
    """Records hold no numpy scalars and survive a ``json`` round trip.

    This is the d49 two-column defect made checkable: the stored artefact kept
    ``[[beta_sq, eps_eff], ...]``, two numbers per candidate, so nothing in the
    file could be used to re-run the curl test.  The replacement must be
    storable *and* still carry the ratio, which is what a ``json.dump`` of a
    numpy scalar would silently break (``TypeError: Object of type float64 is
    not JSON serializable``).
    """
    records = m2.candidate_records(_stub_records())
    text = json.dumps(records)
    back = json.loads(text)
    assert isinstance(back, list) and len(back) == len(records)
    for record in records:
        for key, value in record.items():
            if value is None:
                continue
            assert isinstance(value, (int, float)), f"{key} is {type(value)!r}"
            assert not isinstance(value, np.generic), f"{key} is a numpy scalar"
            assert type(value) in (int, float), f"{key} is {type(value)!r}"
    # the below-cutoff candidate keeps the ``candidate_rows`` convention
    assert back[1]["beta"] is None
    assert back[1]["beta_sq"] == -1.0


# ---------------------------------------------------------------------------
# (c) alignment and values
# ---------------------------------------------------------------------------
def test_record_index_alignment_and_values():
    """``index`` names the source pair and every value is copied across."""
    stub = _stub_records()
    records = m2.candidate_records(stub)
    assert len(records) == len(stub.candidates)
    for position, (record, (beta_sq, eps_eff), curl_ratio) in enumerate(
        zip(records, stub.candidates, stub.curl_ratio)
    ):
        assert record["index"] == position
        assert record["beta_sq"] == pytest.approx(beta_sq)
        assert record["eps_eff"] == pytest.approx(eps_eff)
        assert record["curl_ratio"] == pytest.approx(curl_ratio)
        assert record["abs_curl_ratio"] == abs(record["curl_ratio"])
        if beta_sq >= 0.0:
            assert record["beta"] == pytest.approx(np.sqrt(beta_sq))
        else:
            assert record["beta"] is None


# ---------------------------------------------------------------------------
# (d) an inconsistent result is refused, not silently truncated
# ---------------------------------------------------------------------------
def test_length_mismatch_raises():
    """A candidate/curl-ratio length mismatch raises ``ValueError``."""
    stub = _stub(candidates=[(3.0, 1.5), (2.0, 1.0)], curl_ratio=[1.0e-3])
    with pytest.raises(ValueError) as excinfo:
        m2.candidate_records(stub)
    message = str(excinfo.value)
    assert "2" in message and "1" in message


# ---------------------------------------------------------------------------
# (e) end to end: a real deflated solve carries its curl ratios
# ---------------------------------------------------------------------------
def _walls(lx, ly):
    """Four PEC node predicates, one per wall of the ``lx x ly`` box."""
    return (
        lambda p: np.abs(p[:, 0] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 0] - lx) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - ly) <= WALL_TOL,
    )


def test_real_deflated_result_carries_curl_ratio():
    """A 5 x 5 homogeneous box solution records every candidate's ratio."""
    lx, ly = 2.0, 1.0
    mesh = m2.box_mesh(lx, ly, 5, 5)
    res = m2.solve_modes_deflated(
        mesh, float(np.sqrt(5.0)), 4.0, boundaries=_walls(lx, ly), k=3
    )
    records = m2.candidate_records(res)
    assert len(records) > 0
    assert len(records) == len(res.candidates) == len(res.curl_ratio)
    for record, curl_ratio in zip(records, res.curl_ratio):
        assert record["curl_ratio"] == float(curl_ratio)
    json.dumps(records)
