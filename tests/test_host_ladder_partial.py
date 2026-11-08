"""Regression test for the partial-JSON contract in :mod:`tools.host_ladder`.

The defect
----------
``main()`` built ``meta`` and the payload, created the output directory and
called ``json.dump`` some sixty lines *below* the branch that handles a
mid-ladder ``LadderError``.  That branch printed ``LADDER FAIL``, printed
``no JSON written to <path>`` and returned 1, so a ladder that died on rung 3
of 5 threw away every rung it had already measured -- exactly the opposite of
what a debugging artifact is for, and the one moment the artifact matters
most.

What these tests pin
--------------------
* a ``LadderError`` on rung 2 still writes the JSON, ``status``
  ``"incomplete"``, ``abort_reason`` ``"ladder_error"``, a ``failure`` naming
  the rung, and carrying the one rung that did finish;
* a ``LadderError`` on rung 1 writes a valid payload too, with an empty
  ``rungs`` list rather than no file at all;
* the memory-ceiling abort keeps its own partial write (``abort_reason``
  ``"memory_ceiling"``) -- that path was already correct and must not
  regress.

The real API is used unchanged: ``main(argv) -> int``, with the rung loop
calling the module-level ``run_rung``.  Only that one function is
monkeypatched, so no FDTD and no modal solve ever runs.
"""

import json

import pytest

import tools.host_ladder as host_ladder
from tools.host_ladder import LadderError, MemoryCeilingError

H_FAIL_SECOND = "the modal box is not the FDTD box: height 1.6e-03 against 1.5e-03 m"


def _row(h_mm, beta_fdtd=389.0):
    """One completed rung, keyed like ``run_rung()`` output.

    Every key ``print_table()``, ``print_tone()`` and ``meta`` read is here,
    so a fake rung can stand in for a measured one without a solver.
    """
    beta_eig = beta_fdtd - 0.04
    k0 = 209.7857
    return {
        "h_mm": float(h_mm),
        "cell_m": 1.0e-4,
        "n_cells": 100000,
        "n_sub": 16,
        "n_strip": 5,
        "strip_width_m": 8.0e-4,
        "strip_width_mm": 0.8,
        "grid": [21, 11, 40],
        "npml": 8,
        "n_top": 8,
        "pml_mm": None,
        "nsteps": 100,
        "f_hz": 10.0096e9,
        "f_target_hz": 10.0096e9,
        "k0": k0,
        # 88e7498 made meta() read r["sigma"] (tools/host_ladder.py:1324), so the
        # fake owes that key; derived exactly as :1318-1319 derive it.
        "sigma": k0 ** 2 * host_ladder.ER * host_ladder.SIGMA_MULT,
        "dt_s": 1.0e-15,
        "n_acc": 100000,
        "beta_fdtd": beta_fdtd,
        "beta_eig": beta_eig,
        "beta_fit_one": beta_fdtd,
        "beta_fit_two": beta_fdtd + 0.01,
        "beta_two_station": beta_fdtd - 0.02,
        "beta_model": beta_fdtd + 1.0,
        "fit_residual_one": 0.004,
        "rel_gap_pct": 100.0 * (beta_eig - beta_fdtd) / beta_fdtd,
        "alpha_fdtd_db_per_mm": 0.02,
        "b_over_a": 1.0,
        "alpha_scaled_L_over_H": 1.8,
        "alpha_floor_db_per_mm": 0.0139,
        "alpha_floor_exceeded": True,
        "n_stations": 9,
        "eps_eff_fdtd": 3.0,
        "eps_eff_eig": 3.0,
        "cavity_shift_pct": 0.5,
        "free_e": 1000,
        "free_n": 3000,
        "n_dof": 4000,
        "wall_fdtd_s": 10.0,
        "wall_eig_s": 20.0,
        "t_assembly_s": 1.0,
        "t_splu_s": 2.0,
        "t_eigs_s": 17.0,
        "opinv_calls": 40,
        "factor_nnz": 100000,
        "factor_memory_gb_measured": 0.01,
        "residual": 1.0e-13,
        "curl_ratio": 0.1,
        "n_converged": 16,
        "n_physical": 1,
        "runners_up": [],
        "peak_rss_mb": 100.0,
        "rss_branch": "linux: ru_maxrss is KiB, divided by 1024",
    }


def _payload(path):
    assert path.exists(), "the partial JSON was not written at all"
    return json.loads(path.read_text(encoding="utf-8"))


def test_ladder_error_on_rung_two_keeps_the_rungs_that_finished(
        monkeypatch, tmp_path):
    """The rung that was measured must survive the rung that failed."""
    out = tmp_path / "ladder.json"
    calls = []

    def fake_run_rung(h_mm, args, rss_branch):
        calls.append(float(h_mm))
        if len(calls) == 1:
            return _row(h_mm)
        raise LadderError(H_FAIL_SECOND)

    monkeypatch.setattr(host_ladder, "run_rung", fake_run_rung)

    rc = host_ladder.main(["--max-rungs", "2", "--json", str(out)])

    assert rc == 1, "a hard check must still stop the ladder with exit 1"
    assert len(calls) == 2, "the ladder must stop at the failing rung"
    payload = _payload(out)
    assert len(payload["rungs"]) == 1, (
        f"wrote {len(payload['rungs'])} rungs: the completed rung was dropped")
    assert payload["rungs"][0]["h_mm"] == pytest.approx(0.4)

    meta = payload["meta"]
    assert meta["status"] == "incomplete"
    assert meta["complete"] is False
    assert meta["abort_reason"] == "ladder_error"
    assert meta["failure"], "the partial file must name what stopped it"
    assert "h = 0.26667 mm" in meta["failure"], (
        f"failure {meta['failure']!r} does not name the failing rung")
    assert H_FAIL_SECOND in meta["failure"]


def test_ladder_error_on_the_first_rung_still_writes_an_empty_payload(
        monkeypatch, tmp_path):
    """No completed rung is still a result: an empty, labelled payload."""
    out = tmp_path / "ladder.json"

    def fake_run_rung(h_mm, args, rss_branch):
        raise LadderError("the FDTD loss fit is unavailable")

    monkeypatch.setattr(host_ladder, "run_rung", fake_run_rung)

    rc = host_ladder.main(["--max-rungs", "2", "--json", str(out)])

    assert rc == 1
    payload = _payload(out)
    assert payload["rungs"] == []
    assert payload["meta"]["status"] == "incomplete"
    assert payload["meta"]["abort_reason"] == "ladder_error"
    assert "h = 0.4 mm" in payload["meta"]["failure"]


def test_memory_ceiling_abort_keeps_its_partial_payload(monkeypatch, tmp_path):
    """The budget abort was already correct and must not regress."""
    out = tmp_path / "ladder.json"

    def fake_run_rung(h_mm, args, rss_branch):
        raise MemoryCeilingError(
            "peak RSS 512.0 MB is over the 256.0 MB ceiling",
            h_mm=h_mm, peak_mb=512.0, row=_row(h_mm))

    monkeypatch.setattr(host_ladder, "run_rung", fake_run_rung)

    rc = host_ladder.main(["--max-rungs", "2", "--json", str(out)])

    assert rc == 1
    payload = _payload(out)
    assert len(payload["rungs"]) == 1, "the aborted rung's own row is valid"
    assert payload["meta"]["abort_reason"] == "memory_ceiling"
    assert payload["meta"]["status"] == "incomplete"
    assert payload["meta"]["complete"] is False


def test_box_padding_flags_split_the_lateral_and_lid_clearances(
        monkeypatch, tmp_path):
    """``--box-lateral-mult`` / ``--box-lid-mult`` must reach BOTH halves.

    The two paddings are one CLI pair feeding two different builders: the FDTD
    half takes them as cell counts (``n_clean`` lateral, ``n_air`` lid) and the
    modal half as clearance in units of H (``dm.section``'s positional lid
    clearance and its ``clearance_lateral``).  A flag reaching only one of the
    two would leave the halves meshing different boxes -- the very thing the
    metre check exists to catch -- so both front doors are checked here.

    ``run_rung`` is the real one: only ``run_fdtd`` and ``dm.section`` are
    stubbed, and each raises ``_Stop`` as soon as it has recorded its call, so
    no FDTD run and no modal assembly ever happens.
    """
    class _Stop(Exception):
        pass

    seen = {}
    argv = ["--h", "0.4", "--clearance", "3.0",
            "--box-lateral-mult", "2.0", "--box-lid-mult", "1.5",
            "--json", str(tmp_path / "ladder.json")]

    # --- FDTD half: what does run_rung hand to run_fdtd? -------------------
    def fake_run_fdtd(h_mm, **kw):
        seen["fdtd"] = dict(kw, h_mm=h_mm)
        raise _Stop()

    monkeypatch.setattr(host_ladder, "run_fdtd", fake_run_fdtd)
    with pytest.raises(_Stop):
        host_ladder.main(argv)
    assert seen["fdtd"]["clearance"] == pytest.approx(3.0)
    assert seen["fdtd"]["lateral_mult"] == pytest.approx(2.0), (
        "the lateral multiplier never reached the FDTD half")
    assert seen["fdtd"]["lid_mult"] == pytest.approx(1.5), (
        "the lid multiplier never reached the FDTD half")

    # --- modal half: what does run_rung hand to dm.section? ---------------
    class _Fit:
        alpha = 1.0e-3

    class _Wave:
        loss_fit = _Fit()
        beta = 380.0
        eps_eff = 3.0
        gamma = 380.0j
        station_x = [0.0, 1.0]

    fake_fd = {
        "geometry": {"f": 10.0096e9, "nx": 41, "ny": 21, "nz": 41,
                     "cell": 4.0e-4, "length": 100.0e-3, "h": 0.4e-3},
        "wave": _Wave(), "n_cells": 1000, "nsteps": 120, "wall": 1.0,
        "n_clean": 12, "n_air": 18,
    }

    def fake_run_fdtd_ok(h_mm, **kw):
        seen["fdtd_ok"] = dict(kw, h_mm=h_mm)
        return fake_fd

    def fake_section(*a, **kw):
        seen["section"] = {"args": list(a), "kwargs": dict(kw)}
        raise _Stop()

    monkeypatch.setattr(host_ladder, "run_fdtd", fake_run_fdtd_ok)
    monkeypatch.setattr(host_ladder.dm, "section", fake_section)
    with pytest.raises(_Stop):
        host_ladder.main(argv)

    assert seen["fdtd_ok"]["lateral_mult"] == pytest.approx(2.0)
    assert seen["fdtd_ok"]["lid_mult"] == pytest.approx(1.5)
    section = seen["section"]
    assert section["args"][1] == pytest.approx(3.0 * 1.5), (
        "dm.section's positional clearance is the LID: clearance * lid_mult")
    assert section["kwargs"]["clearance_lateral"] == pytest.approx(3.0 * 2.0), (
        "dm.section's clearance_lateral must be clearance * lateral_mult")
