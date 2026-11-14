"""The Mode picker: every candidate the pencil kept, offered without a re-solve.

Two layers are proven here, and they are different kinds of claim.

The COMPUTE half is ``mode_view`` returning ``chosen`` / ``candidates`` /
``candidate_grids`` from ONE solve, plus the four module helpers that turn those
into a picker item, a picture and a caption.  Those are called directly, and one
test solves the real synthetic cross-section so the numbers are the shipped
ones - nothing is doubled.

The WIRING half is the shipped ``run_web_vis``: the registered
``mode_view_toggle`` trigger, the ``@state.change("mode_choice")`` listener it
writes under, and what a browser pick therefore repaints.  There ``mode_view``
itself is DOUBLED (a dict in, no scipy) so a failure points at the wiring.

The trame mechanism this rests on is measured, not assumed, and it is why the
listener is a ``@state.change`` and not another ``@ctrl.set``:
``trame_server/state.py::State.__setitem__`` only QUEUES a key
(``_pending_update``); ``State.flush()`` pushes it and then runs every callback
registered for the keys in ``_suppress_change_stack.get_change_listener_keys()``
- with the exception caught into ``logger.warning("@change callback exception
ignored: %s")``, which is why a broken listener shows up as a caption that never
changed rather than as a raise.  ``trame_server/protocol.py`` reaches that flush
twice: ``trigger`` runs the handler inside ``with self.server.state:`` (whose
``__exit__`` is ``flush()``), and ``update_state`` - the RPC a ``v_model`` sends
- does the same.  An ``@ctrl.set("mode_choice")`` would be reachable from
neither: ``trigger_fn(name)`` is only ever called for the names the CLIENT was
told to call, and ``v_model=("mode_choice", 0)`` is a plain state write.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries tests/test_poc_playback.py adds, so `import
        # poc_app` resolves from server/poc_app.py
        sys.path.insert(0, _p)

# pyvista/trame/vtk live in the repo's own venv in this image (its bin/python is
# broken, the site-packages tree is not).  Inert where they are installed
# normally.  Only the wiring test below needs them, so the import is guarded
# there rather than at module scope: the helper tests are pure.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))


def _record(index, beta, beta_sq, eps_eff):
    """One ``mode2d.candidate_records`` row, keyed exactly as that function is."""
    return {
        "index": index,
        "beta": beta,
        "beta_sq": beta_sq,
        "eps_eff": eps_eff,
    }


# --- the picker's TEXT ------------------------------------------------------


def test_candidate_title_repeats_the_compute_layers_numbers() -> None:
    import poc_app as app

    row = app._mode_candidate_title(
        _record(1, 223.180967, 49809.74, 3.338787), chosen=1
    )
    assert row.startswith("#1  beta 223.18 rad/m"), row
    assert "eps_eff 3.339" in row, row
    assert row.endswith("(the solver's pick)"), (
        "the solver's own pick is not named on its own row, so the caption's "
        f"numbers cannot be tied to a row: {row!r}"
    )

    other = app._mode_candidate_title(
        _record(0, 190.0, 36100.0, 2.9), chosen=1
    )
    assert not other.endswith("(the solver's pick)"), (
        f"a row that is NOT the pick is marked as one: {other!r}"
    )
    assert other.startswith("#0  beta 190.00 rad/m"), other


def test_candidate_title_says_when_there_is_no_beta_at_all() -> None:
    import poc_app as app

    row = app._mode_candidate_title(_record(2, None, -12.5, 1.0))
    assert "#2" in row, row
    assert "Evanescent" in row, f"a below-cutoff row is not named as one: {row!r}"
    assert "rad/m" not in row, (
        "a below-cutoff candidate does not propagate, yet the row prints a "
        f"beta: {row!r}"
    )
    assert "alpha 3.54 Np/m" in row, (
        "the row drops the decay constant that explains the missing beta "
        f"(here from the ``beta_sq`` fallback): {row!r}"
    )
    assert "beta_sq -12.5" in row, (
        f"the row drops the beta_sq that explains the missing beta: {row!r}"
    )
    assert "below cutoff, never pickable" in row, (
        "the row does not say WHY it has no beta; a reader would take the gap "
        f"for a recording failure: {row!r}"
    )
    assert "eps_eff 1.000" in row, row


def test_candidate_title_says_when_a_candidate_sits_exactly_at_cutoff() -> None:
    import poc_app as app

    row = app._mode_candidate_title(_record(1, None, 0.0, 1.234))
    assert "#1" in row, row
    assert "At cutoff" in row, (
        f"a candidate exactly at cutoff is named as neither case: {row!r}"
    )
    assert "rad/m" not in row, (
        "a candidate at cutoff does not propagate, yet the row prints a "
        f"beta: {row!r}"
    )
    assert "eps_eff 1.234" in row, row


def test_candidate_title_survives_a_record_it_cannot_read() -> None:
    import poc_app as app

    assert app._mode_candidate_title({"index": "not a number"}) == "candidate"
    assert app._mode_candidate_title({}) == "candidate"
    assert app._mode_candidate_title(None) == "candidate"


# --- the picker's ITEMS -----------------------------------------------------


def _kept_result():
    """A ``mode_view`` result as the compute layer now returns it."""
    return {
        "ok": True,
        "caption": "beta 223.18 rad/m, from the run's own record",
        "chosen": 1,
        "grid": np.ones((3, 3)),
        "beta_rad_per_m": 223.180967,
        "candidates": [
            _record(0, 190.0, 36100.0, 2.9),
            _record(1, 223.180967, 49809.74, 3.338787),
            _record(2, None, -12.5, 1.0),
            _record(3, 240.0, 57600.0, 3.9),
        ],
        "candidate_grids": (
            np.zeros((3, 3)),
            np.ones((3, 3)),
            np.full((3, 3), 2.0),
            np.full((3, 3), 3.0),
        ),
    }


def test_candidate_items_offer_one_row_per_kept_candidate() -> None:
    import poc_app as app

    items = app._mode_candidate_items(_kept_result())

    assert [item["value"] for item in items] == [0, 1, 2, 3], (
        "the items are not keyed by the candidate's OWN index, so a pick cannot "
        f"reach the grid it names: {items!r}"
    )
    assert all(item["title"] for item in items), items
    picked = [item for item in items if "(the solver's pick)" in item["title"]]
    assert len(picked) == 1 and picked[0]["value"] == 1, (
        f"exactly one row must be marked as the pick: {items!r}"
    )


def test_candidate_items_offer_the_reason_when_the_solve_refused() -> None:
    """A refusal is the ONE thing the picker must not swallow.

    The caption line already says ``mode refused: ...``; the dropdown is the
    other half of the same press, and an empty dropdown there tells the reader
    that something failed and then hides what.  The row is keyed by a value no
    candidate index can be, so it does not look like a selection.
    """
    import poc_app as app

    items = app._mode_candidate_items({"ok": False, "reason": "no record"})

    assert [item["value"] for item in items] == [app._MODE_REFUSED_VALUE], (
        "the refusal's row is keyed like a candidate, so the closed picker would "
        f"name one the solver never kept: {items!r}"
    )
    assert app._MODE_REFUSED_VALUE < 0, (
        "a candidate index is never negative, so the refusal's value must be"
    )
    assert "no record" in items[0]["title"], (
        f"the solver's own reason did not reach the row that offers it: {items!r}"
    )


def test_candidate_items_are_empty_when_there_is_nothing_to_offer() -> None:
    import poc_app as app

    assert app._mode_candidate_items({"ok": True}) == []
    assert app._mode_candidate_items({"ok": False}) == [], (
        "a refusal with no reason string has nothing to say, so it must offer "
        "no row rather than an empty one"
    )
    assert app._mode_candidate_items(None) == []
    assert app._mode_candidate_items("not a dict") == []


# --- the picker's PICTURE ---------------------------------------------------


def test_view_for_candidate_swaps_only_the_grid() -> None:
    import poc_app as app

    result = _kept_result()
    view = app._mode_view_for_candidate(result, 2)

    assert view is not None
    assert view["grid"] is result["candidate_grids"][2], (
        "the pick did not install that candidate's own |E|"
    )
    assert view["beta_rad_per_m"] == result["beta_rad_per_m"], (
        "the view re-pointed the NUMBERS as well as the picture; the caption "
        "above the picture would then be describing a different mode"
    )
    assert view["caption"] == result["caption"]
    assert result["grid"] is not view["grid"], (
        "the solve's own result was mutated in place, so the fundamental's "
        "picture is lost for the rest of the session"
    )
    assert view is not result


def test_view_for_candidate_is_none_when_nothing_can_be_drawn() -> None:
    import poc_app as app

    assert app._mode_view_for_candidate({"ok": False, "reason": "x"}, 0) is None
    assert app._mode_view_for_candidate(None, 0) is None
    assert app._mode_view_for_candidate(_kept_result(), 99) is None, (
        "a pick this solve did not keep must not be answered with the "
        "fundamental's grid under the candidate's label"
    )

    misaligned = _kept_result()
    misaligned["candidate_grids"] = (np.zeros((3, 3)),)
    assert app._mode_view_for_candidate(misaligned, 3) is None, (
        "a grid list shorter than the record list was zipped anyway, so a "
        "candidate could be drawn with a neighbour's field"
    )


# --- the picker's CAPTION ---------------------------------------------------


def test_choice_caption_is_unchanged_while_the_pick_is_the_solvers() -> None:
    import poc_app as app

    result = _kept_result()

    assert app._mode_choice_caption_text(result, 1) == app._mode_caption_text(result), (
        "a pick that still names the solver's pick re-worded the caption; the "
        "text a press produces and the text the picker rests on must be one text"
    )


def test_choice_caption_names_the_row_and_keeps_the_numbers_attributed() -> None:
    import poc_app as app

    result = _kept_result()
    base = app._mode_caption_text(result)
    caption = app._mode_choice_caption_text(result, 3)

    assert caption.startswith(base), (
        f"the solve's own caption was dropped instead of kept: {caption!r}"
    )
    assert "#3" in caption and "beta 240.00 rad/m" in caption, (
        f"the caption does not name the row on screen: {caption!r}"
    )
    assert "#1" in caption, (
        "the caption does not say which row the numbers above it still "
        f"describe: {caption!r}"
    )
    assert "showing candidate" in caption, caption


def test_choice_caption_falls_back_to_the_solve_for_a_pick_it_cannot_name() -> None:
    import poc_app as app

    result = _kept_result()
    base = app._mode_caption_text(result)

    assert app._mode_choice_caption_text(result, 99) == base
    assert app._mode_choice_caption_text(result, "not a number") == base
    assert app._mode_choice_caption_text({"ok": False, "reason": "x"}, 0) == (
        app._mode_caption_text({"ok": False, "reason": "x"})
    )


# --- the grid sampler: the reason a pick needs no second solve --------------


class _StubSolved:
    """``Mode2D``'s sampling surface and nothing else, with its calls recorded."""

    def __init__(self, grid_axes=()):
        self.mesh = SimpleNamespace(grid_axes=grid_axes)
        self.calls = []

    def e_at(self, points):
        self.calls.append(("e_at", np.array(points, dtype=float)))
        return np.tile([1.0, 0.0], (len(points), 1))

    def e_at_candidate(self, index, points):
        self.calls.append(("e_at_candidate", index, np.array(points, dtype=float)))
        return np.tile([0.0, float(index) + 2.0], (len(points), 1))


def test_field_grid_samples_the_pick_by_default() -> None:
    import poc_app as app

    solved = _StubSolved()
    grid = app._mode_field_grid(solved, (1e-3, 8.8e-3), cells=5)

    assert grid.shape == (5, 5)
    assert np.allclose(grid, 1.0), (
        "the sampler did not take |E| of the returned phasor pair"
    )
    assert [call[0] for call in solved.calls] == ["e_at"], (
        f"a default sample went through something other than e_at: {solved.calls}"
    )


def test_field_grid_samples_a_candidate_through_the_same_interpolation() -> None:
    import poc_app as app

    solved = _StubSolved()
    grid = app._mode_field_grid(solved, (1e-3, 8.8e-3), cells=5, index=2)

    assert [call[0] for call in solved.calls] == ["e_at_candidate"], solved.calls
    assert solved.calls[0][1] == 2, solved.calls
    assert np.allclose(grid, 4.0), (
        "the candidate's own field was not the one sampled: a candidate row "
        "would show the fundamental's picture"
    )


def test_field_grid_prefers_the_meshs_own_axis_endpoints() -> None:
    import poc_app as app

    solved = _StubSolved(grid_axes=((1e-3, 7e-3), (2e-3, 9e-3)))
    app._mode_field_grid(solved, (1e-3, 8.8e-3), cells=4)

    points = solved.calls[0][1]
    assert points[:, 0].min() == pytest.approx(1e-3)
    assert points[:, 0].max() == pytest.approx(7e-3)
    assert points[:, 1].min() == pytest.approx(2e-3)
    assert points[:, 1].max() == pytest.approx(9e-3), (
        "the sampling was re-derived from the extent instead of the mesh's own "
        "axes, which is how e_at ends up outside the triangulation"
    )


# --- the real solve: one solve, every candidate ----------------------------

MODE_GEOMETRY = {
    "eps_r": 4.4,
    "h": 1.6e-3,
    "w": 3.2e-3,
    "height": 8.8e-3,
    "f_hz": 5.827786408327286e9,
}

MODE_BETA_MODEL = 223.35306683909533


def _mode_page(tmp_path: Path) -> dict:
    """A page whose SIBLING RECORD holds ``MODE_GEOMETRY``."""
    page_path = tmp_path / "arm.npz"
    page_path.with_suffix(".json").write_text(
        json.dumps(
            {"geometry": dict(MODE_GEOMETRY), "line": {"beta_model": MODE_BETA_MODEL}}
        )
    )
    return {"path": str(page_path), "structure_id": "A"}


def test_mode_view_returns_every_candidate_from_one_solve(tmp_path: Path) -> None:
    import poc_app as app

    result = app.mode_view(_mode_page(tmp_path), cache={})

    assert result["ok"], result["reason"]
    chosen = result["chosen"]
    candidates = result["candidates"]
    grids = result["candidate_grids"]

    assert chosen in [record["index"] for record in candidates], (
        f"the picked index {chosen} is not among the returned candidates: the "
        "picker would point at a row that does not exist"
    )
    assert len(grids) == len(candidates), (
        f"{len(candidates)} candidate records but {len(grids)} pictures; the "
        "two lists are zipped by position"
    )
    assert len(candidates) > 1, (
        "the solve kept a single candidate, so the picker has nothing to offer "
        "and this test proves nothing about it"
    )
    for grid in grids:
        assert grid.shape == (app.MODE_GRID_CELLS,) * 2
        assert np.all(np.isfinite(grid)), (
            "a candidate's picture carries a non-finite sample, so picking it "
            "would draw holes"
        )

    items = app._mode_candidate_items(result)
    assert len(items) == len(candidates)
    assert sum("(the solver's pick)" in item["title"] for item in items) == 1

    view = app._mode_view_for_candidate(result, chosen)
    assert view is not None
    assert np.allclose(view["grid"], result["grid"]), (
        "the picked candidate's picture is not the fundamental's picture: "
        "e_at_candidate(chosen) and e_at must be the same column"
    )


def test_mode_view_memo_keys_on_k(tmp_path: Path) -> None:
    import poc_app as app

    page = _mode_page(tmp_path)
    cache = {}

    two = app.mode_view(page, k=2, cache=cache)
    four = app.mode_view(page, cache=cache)

    assert two["ok"] and four["ok"], (two["reason"], four["reason"])
    assert four is not two, (
        "a k=2 solve answered a k=4 request: `k` is not in the memo key, so the "
        "panel would report two modes while asking the pencil for four"
    )
    assert app.mode_view(page, cache=cache) is four, (
        "the identical request did not answer from the memo"
    )


# --- the refusal the dropdown has to SHOW -----------------------------------

#: ``eps_r`` 1 next to a 1.6 mm substrate is not a microstrip: every candidate of
#: the pencil then has ``eps_eff == 1.0``, so the mode-eligibility guard
#: (``emfit.mode2d``, which requires ``|curl_ratio| >= 1e-06`` AND
#: ``eps_eff < eps_max - 1e-06``) rejects all of them and ``mode_view`` returns a
#: REFUSAL.  Deliberately invalid, and cheap (0.03 s): it is the shape of a page
#: whose geometry record is wrong, which is exactly the press whose reason must
#: not be lost.
INVALID_MODE_GEOMETRY = dict(MODE_GEOMETRY, eps_r=1.0)


def _invalid_mode_page(tmp_path: Path) -> dict:
    """A page whose SIBLING RECORD holds ``INVALID_MODE_GEOMETRY``."""
    page_path = tmp_path / "arm.npz"
    page_path.with_suffix(".json").write_text(
        json.dumps({"geometry": dict(INVALID_MODE_GEOMETRY)})
    )
    return {"path": str(page_path), "structure_id": "A"}


def test_the_picker_carries_the_solver_s_own_refusal_reason(tmp_path: Path) -> None:
    import poc_app as app

    result = app.mode_view(_invalid_mode_page(tmp_path), cache={})

    assert not result["ok"], (
        "this geometry no longer refuses, so the test is not on the refusal "
        f"path at all: {result.get('reason')!r}"
    )
    reason = result["reason"]
    assert "mode-eligibility guard rejects every candidate" in reason, (
        f"the refusal is not the eligibility guard's, so the reason asserted "
        f"below is not the one this test was written for: {reason!r}"
    )

    items = app._mode_candidate_items(result)

    assert len(items) == 1, (
        "a refusal must offer exactly one row - its reason - and nothing that "
        f"reads as a candidate: {items!r}"
    )
    assert items[0]["value"] == app._MODE_REFUSED_VALUE, (
        f"the refusal's row is keyed like a candidate: {items!r}"
    )
    assert reason in items[0]["title"], (
        "the solver's reason does not reach the dropdown a press offers, so a "
        "failed press looks like a press that had nothing to offer: "
        f"{items[0]['title']!r}"
    )
    # The two channels a press publishes must not disagree about what happened.
    assert reason in app._mode_caption_text(result), app._mode_caption_text(result)


def test_the_evidence_archive_still_offers_its_four_candidates() -> None:
    """The shipped artefact, really solved: the refusal row must not replace it.

    The positive control for the test above - on a page that DOES solve, the
    picker is still one row per kept candidate, in the solver's own order, with
    no ``Error: ...`` in sight.
    """
    import poc_app as app

    dump = (
        REPO_ROOT
        / "evidence"
        / "termination"
        / "build_A_50ohm_p51_ghostwave_fields.npz"
    )
    if not dump.is_file():
        pytest.skip(f"the evidence archive is not in this checkout: {dump}")

    result = app.mode_view(app.reload_page(dump), cache={})

    assert result["ok"], result["reason"]
    items = app._mode_candidate_items(result)

    assert [item["value"] for item in items] == [0, 1, 2, 3], (
        "the evidence archive's four candidates are not offered, in their own "
        f"order, any more: {items!r}"
    )
    assert all(
        item["title"].startswith(f"#{item['value']} ") for item in items
    ), f"a row's title no longer labels the candidate it points at: {items!r}"
    assert not any("Error:" in item["title"] for item in items), (
        f"a solved page is offering a refusal row: {items!r}"
    )
    picked = [
        item["value"] for item in items if "(the solver's pick)" in item["title"]
    ]
    assert picked == [int(result["chosen"])], (
        f"the one row marked as the pick is not the solver's chosen candidate "
        f"{result['chosen']}: {items!r}"
    )


# --- the shipped wiring -----------------------------------------------------


def test_a_pick_repaints_the_mode_picture_without_a_second_solve(
    tmp_path: Path, monkeypatch
) -> None:
    """The real ``run_web_vis``, the real trigger, the real state flush.

    ``mode_view`` is doubled (a dict in, no scipy) - nothing else is: the boot,
    the registered ``mode_view_toggle``, the ``@state.change("mode_choice")``
    listener and the two draws are the shipped code.  ``Plotter.render`` is
    doubled for the reason every visual test here doubles it (no EGL, no
    libOSMesa, no X server in this image).

    What is COUNTED is not ``render`` but the picture itself: the mode picture
    is ONE named actor - ``_draw_mode_picture`` hands its grid to ``add_mesh``
    under ``name="mode_picture"`` - so counting that name counts draws of the
    field on the plane, which is the thing the suppression is supposed to keep
    at one per press.
    """
    pyvista = pytest.importorskip("pyvista")
    pytest.importorskip("trame.app")
    pytest.importorskip("trame.ui.vuetify3")
    from test_poc_playback import (
        _boot_app,
        _closure_cells,
        _fixture_info,
        _registered_trigger,
    )

    import poc_app as app

    cells = app.MODE_GRID_CELLS
    fake = {
        "ok": True,
        "reason": "",
        "beta_rad_per_m": 223.180967,
        "eps_eff": 3.338787,
        "caption": "CAPTION from the solve: beta = 223.18 rad/m",
        "grid": np.ones((cells, cells)),
        "extent": (1.6e-3, 8.8e-3),
        "chosen": 1,
        "candidates": [
            _record(0, 190.0, 36100.0, 2.9),
            _record(1, 223.180967, 49809.74, 3.338787),
            _record(2, None, -12.5, 1.0),
        ],
        "candidate_grids": (
            np.zeros((cells, cells)),
            np.ones((cells, cells)),
            np.full((cells, cells), 2.0),
        ),
    }
    presses = {"n": 0}

    def fake_solve(*_args, **_kwargs):
        presses["n"] += 1
        return fake

    # Doubled, not measured: a real render segfaults in this image.  `render`
    # calls are deliberately NOT the count - the handlers also call
    # `handles["view"].update()`, which reaches `Plotter.render` as well, and
    # that is a client push, not a draw.
    real_render = pyvista.Plotter.render
    pyvista.Plotter.render = lambda self, *args, **kwargs: None
    # The count that IS the contract: draws of the `mode_picture` actor.
    draws = {"n": 0}
    real_add_mesh = pyvista.Plotter.add_mesh

    def counting_add_mesh(self, *args, **kwargs):
        if kwargs.get("name") == "mode_picture":
            draws["n"] += 1
        return real_add_mesh(self, *args, **kwargs)

    pyvista.Plotter.add_mesh = counting_add_mesh
    try:
        monkeypatch.setattr(app, "mode_view", fake_solve)
        info = _fixture_info(app, tmp_path / "dump.npz")
        _app, srv = _boot_app(info)
        trigger = _registered_trigger(srv.controller, "mode_view_toggle")
        page_cells = _closure_cells(trigger)
        assert "state" in page_cells, (
            "the Mode trigger is not closed over the page's state (freevars: "
            f"{sorted(page_cells)}), so nothing it publishes is assertable"
        )
        state = page_cells["state"]
        handles = page_cells["handles"]

        # The one framework step the boot double skips.  `_boot_app` replaces
        # `server.start` with a raise, so `protocol.port_callback` - whose job
        # this call is - never runs, and until it does `State.flush()` refuses:
        # `_status.skip_flushing` is true while `not ready`.  A refused flush
        # runs no `@state.change` listener, so the pick below would be
        # invisible and this test would be asserting on nothing.  `ready()` is
        # trame's own call, not a substitute for shipped code.
        assert state.is_ready is False, (
            "the boot double unexpectedly bound a port, so the flush path this "
            "test drives is no longer the one a real server uses"
        )
        srv.state.ready()
        assert state.is_ready, (
            "trame's state.ready() did not mark the page state ready, so no "
            "flush can run a listener"
        )

        # The resting picker: no items, and `mode_choice` at the value the
        # select declares, because nothing has been solved yet.
        assert state.mode_choice == 0
        assert state.mode_choice_items == [], (
            f"the picker offers rows before a solve: {state.mode_choice_items!r}"
        )
        state.flush()  # push the boot writes; not part of the counts below

        # `with state:` is trame's own rpc frame around a trigger
        # (protocol.py::trigger), and its __exit__ is the flush that runs the
        # @state.change listeners.
        with state:
            asyncio.run(trigger())

        assert state.mode_choice == fake["chosen"], (
            "the press did not re-point the picker at the solver's pick: "
            f"{state.mode_choice!r}"
        )
        assert [item["value"] for item in state.mode_choice_items] == [0, 1, 2]
        assert state.mode_view_caption == fake["caption"], state.mode_view_caption
        assert handles["mode_result"] is fake, (
            "the press did not KEEP the solve's result, so a pick would have to "
            "solve again"
        )
        assert presses["n"] == 1
        # ONE press, ONE picture.  The press writes `mode_choice` under
        # `suppress_change_listeners("mode_choice")`, so the listener must not
        # draw the same grid again: if the suppression were dropped, this
        # count would be 2 and the operator would pay two full-field draws for
        # one click.
        assert draws["n"] == 1, (
            f"one press drew the mode picture {draws['n']} times: the write to "
            "`mode_choice` is suppressed precisely so the @state.change "
            "listener does not re-draw the grid the press already drew"
        )

        def picture_values():
            """The |E| array actually on the plane, read off the LIVE handle."""
            entry = handles.get("mode_actor")
            assert entry is not None, (
                "no `handles['mode_actor']` after the draw: nothing is on the "
                "plane, so the counts below would count nothing"
            )
            return np.asarray(entry["grid"].point_data["mode_e_abs"], dtype=float)

        # The press drew the SOLVE's grid, which the double sets to all ones.
        assert np.allclose(picture_values(), 1.0), (
            "the press did not put the solve's own grid on the plane"
        )

        # A pick that the browser makes: `mode_choice` changes, the listener
        # repaints from the KEPT result.
        state.mode_choice = 0
        state.flush()

        # ONE pick, ONE more picture - and it is CANDIDATE 0's grid (all
        # zeros), which the solve carried in `candidate_grids`.  A re-solve or
        # a redraw of the fundamental would leave ones on the plane.
        assert draws["n"] == 2, (
            f"a pick left the picture drawn {draws['n']} times in total "
            "(press = 1): a pick must draw exactly once, from the grid the "
            "solve already kept"
        )
        assert np.allclose(picture_values(), 0.0), (
            "the pick did not repaint from the candidate's own kept grid: "
            f"the plane still carries {picture_values().max():.3g}, the "
            "solve's own field"
        )

        picked = state.mode_view_caption
        assert picked.startswith(fake["caption"]), (
            f"the pick discarded the solve's caption: {picked!r}"
        )
        assert "showing candidate" in picked, picked
        assert "#0" in picked, (
            f"the caption does not name the row now on screen: {picked!r}"
        )
        assert "#1" in picked, (
            "the caption does not say whose numbers it is still quoting: "
            f"{picked!r}"
        )
        assert presses["n"] == 1, (
            "the pick ran `mode_view` a second time: the whole point of "
            "carrying every candidate's grid is that a pick is a lookup"
        )

        # A pick this solve cannot draw changes NOTHING - the picture and the
        # caption stay as they were rather than showing the fundamental under
        # another candidate's label.
        state.mode_choice = 999
        state.flush()
        assert state.mode_view_caption == picked, (
            "an undrawable pick re-worded the caption: "
            f"{state.mode_view_caption!r}"
        )
        assert draws["n"] == 2, (
            "an undrawable pick still drew the mode picture - something was "
            "painted, and it can only have been the wrong field"
        )
    finally:
        pyvista.Plotter.render = real_render
        pyvista.Plotter.add_mesh = real_add_mesh


# --- the page TITLE ---------------------------------------------------------
#
# The title is a CLAIM about the picture under it, so it is asserted the way the
# picture is: through the shipped handlers, on the state string the browser
# reads.  Two pictures live on this view - the |Ez| dump animation and a solved
# mode cross-section's |E_t| - and every test below asks the same question of
# the same string: does it describe what is on screen?  The header half of
# ``_set_picture_title`` (``handles["title_setter"]``, a Vuetify toolbar title)
# is exercised only by a live layout, so nothing here reads it: the assertion
# is on ``state.trame__title``, the string the browser tab carries.


def _fake_press_result(cells: int, chosen: int = 1) -> dict:
    """A ``mode_view`` result with three candidates: the press's only input."""
    return {
        "ok": True,
        "reason": "",
        "beta_rad_per_m": 223.180967,
        "eps_eff": 3.338787,
        "caption": "CAPTION from the solve: beta = 223.18 rad/m",
        "grid": np.ones((cells, cells)),
        "extent": (1.6e-3, 8.8e-3),
        "chosen": chosen,
        "candidates": [
            _record(0, 190.0, 36100.0, 2.9),
            _record(1, 223.180967, 49809.74, 3.338787),
            _record(2, None, -12.5, 1.0),
        ],
        "candidate_grids": (
            np.zeros((cells, cells)),
            np.ones((cells, cells)),
            np.full((cells, cells), 2.0),
        ),
    }


@contextlib.contextmanager
def _headless_draws():
    """``Plotter.render`` doubled for the duration: this image has no EGL."""
    pyvista = pytest.importorskip("pyvista")

    real_render = pyvista.Plotter.render
    pyvista.Plotter.render = lambda self, *args, **kwargs: None
    try:
        yield
    finally:
        pyvista.Plotter.render = real_render


def _title_page(tmp_path: Path, monkeypatch, result: dict):
    """The shipped page, booted with ``mode_view`` doubled, ready to be pressed.

    The same harness the wiring test above uses - ``_boot_app``,
    ``_registered_trigger``, ``_closure_cells``, ``_fixture_info`` - plus the
    one framework step that boot double skips: ``srv.state.ready()``, without
    which ``State.flush()`` runs no ``@state.change`` listener (see above).
    Returns the two triggers the browser would call, so a family switch is
    driven through the shipped handler rather than by writing ``state.mode``.
    """
    pytest.importorskip("trame.app")
    pytest.importorskip("trame.ui.vuetify3")
    from test_poc_playback import (
        _boot_app,
        _closure_cells,
        _fixture_info,
        _registered_trigger,
    )

    import poc_app as app

    monkeypatch.setattr(app, "mode_view", lambda *_a, **_k: result)
    info = _fixture_info(app, tmp_path / "dump.npz")
    _app, srv = _boot_app(info)
    press = _registered_trigger(srv.controller, "mode_view_toggle")
    toggle = _registered_trigger(srv.controller, "mode_toggle")
    page_cells = _closure_cells(press)
    state = page_cells["state"]
    handles = page_cells["handles"]
    # ``trame.app.get_server`` hands back ONE server per process, so a boot
    # earlier in this file may already have marked its state ready; only the
    # first boot of the process needs the step the boot double skips.
    if not state.is_ready:
        srv.state.ready()
    assert state.is_ready, (
        "trame's state.ready() did not mark the page state ready, so no flush "
        "can run a @state.change listener"
    )
    state.flush()  # push the boot writes; not part of any count
    return app, state, handles, press, toggle


def test_a_press_titles_the_page_with_the_mode_it_drew(
    tmp_path: Path, monkeypatch
) -> None:
    """One press, one title: the picture is |E_t| of the candidate it names."""
    with _headless_draws():
        _app, state, handles, press, toggle = _title_page(
            tmp_path, monkeypatch, _fake_press_result(8)
        )
        assert "|Ez| animation" in state.trame__title, (
            f"a freshly booted page shows the dump animation but titles itself "
            f"{state.trame__title!r}"
        )
        # The shipped family switch: y-cut -> x-cut, the view the mode picture
        # is drawn FOR.  Nothing is solved yet, so the picture does not exist
        # and the title must still be the animation's.
        with state:
            toggle()
        assert state.mode == "xcut", (
            f"the family switch left the page on {state.mode!r}, so the press "
            "below would be made from the wrong view"
        )
        assert "|Ez| animation" in state.trame__title, (
            "a family switch with no mode picture on the view re-titled the "
            f"page as {state.trame__title!r}"
        )

        with state:
            asyncio.run(press())

        assert handles.get("mode_actor") is not None, (
            "no mode picture reached the plane, so there is nothing the title "
            "could be describing"
        )
        title = state.trame__title
        assert "|E_t|" in title, (
            f"the mode picture is on screen but the title says {title!r}: the "
            "mode cross-section is |E_t|, and |Ez| is a field only the dump has"
        )
        assert "candidate #1" in title, (
            f"the title does not name the candidate on screen: {title!r} "
            "(the solve's own pick is #1)"
        )
        assert "candidate #0" not in title, (
            f"the title names the wrong candidate: {title!r} - the picture is "
            "the solver's pick, #1"
        )
        assert "|Ez|" not in title, (
            f"the title still claims the |Ez| dump while a mode cross-section "
            f"is on screen: {title!r}"
        )


def test_a_refused_press_puts_the_animation_title_back(
    tmp_path: Path, monkeypatch
) -> None:
    """The refusal path: picture gone, so the |E_t| title must go with it.

    This is the case that a title sync placed BEFORE the actor is popped got
    wrong: the sync then read the handle it was about to drop, concluded the
    picture was still on screen, and left the mode title standing over an
    error caption.
    """
    with _headless_draws():
        app, state, handles, press, toggle = _title_page(
            tmp_path, monkeypatch, _fake_press_result(8)
        )
        with state:
            toggle()
        with state:
            asyncio.run(press())
        assert "|E_t|" in state.trame__title, (
            "the precondition of this test is not met: the first press left no "
            f"|E_t| title to restore from ({state.trame__title!r})"
        )

        refused = {"ok": False, "reason": "no cross-section recorded in this dump"}
        monkeypatch.setattr(app, "mode_view", lambda *_a, **_k: refused)
        with state:
            asyncio.run(press())

        assert handles.get("mode_actor") is None, (
            "a refused press left the mode picture on the plane: a stale mode "
            "beside an error caption is a lie about what was solved"
        )
        title = state.trame__title
        assert "|Ez| animation" in title, (
            f"the picture is gone and the title still says {title!r}: the "
            "animation is what this view is showing again"
        )
        assert "|E_t|" not in title, (
            f"a refused press kept the |E_t| title over an error caption: {title!r}"
        )


def test_a_family_switch_titles_the_page_with_the_field_on_screen(
    tmp_path: Path, monkeypatch
) -> None:
    """The picture hidden by a family switch is not what the title describes."""
    with _headless_draws():
        _app, state, handles, press, toggle = _title_page(
            tmp_path, monkeypatch, _fake_press_result(8)
        )
        with state:
            toggle()  # y-cut -> x-cut
        with state:
            asyncio.run(press())
        assert "|E_t|" in state.trame__title, (
            f"no |E_t| title to switch away from: {state.trame__title!r}"
        )

        with state:
            toggle()  # x-cut -> y-cut: the mode picture is drawn for x-cut only
        assert state.mode == "ycut", state.mode
        title = state.trame__title
        assert "|Ez| animation" in title, (
            f"the mode picture is hidden on the y-cut view but the title says "
            f"{title!r}: a title must describe the field on screen, not one "
            "that exists off it"
        )
        assert "|E_t|" not in title, title

        with state:
            toggle()  # back to x-cut: the same picture is on screen again
        assert state.mode == "xcut", state.mode
        title = state.trame__title
        assert "|E_t|" in title, (
            f"the mode picture came back on screen but the title stayed on the "
            f"animation: {title!r}"
        )
        assert "candidate #1" in title, (
            f"the restored title does not name the candidate still on screen: "
            f"{title!r}"
        )


# --- load_any_dump routes a surface archive by schema ---


def test_load_any_dump_refuses_a_huygens_surface_dump_by_name(
    tmp_path: Path, capsys
) -> None:
    """A surface archive is refused BY NAME on both routes, never read as a plane.

    Nothing in this viewer draws surface currents, so the loader hands such a
    file to ``emfit.ntff.load_surface_dump`` - the reader built for it - and
    then refuses it, because returning the validated record would trade a named
    refusal for an AttributeError in ``reload_page`` two frames down.

    Two predicates reach that refusal and both are pinned here: the ``schema``
    discriminator, and the key SIGNATURE that is all an archive predating the
    discriminator carries.  The arrays are zeros on purpose - the claim under
    test is which READER the file is handed to, not the physics - so the zeros
    land in whichever branch of ``load_surface_dump`` they happen to satisfy
    (validated, or refused by it), and the loader refuses at exit code 2 either
    way.
    """
    import poc_app as app

    from emfit.ntff import SURFACE_DUMP_KEYS, SURFACE_DUMP_SCHEMA

    def _write(path, stamp_schema):
        payload = {
            "schema_version": np.asarray(1),
            "stray": np.asarray(False),
            "dt": np.asarray(1e-12),
            "dx": np.asarray(1e-3),
            "dy": np.asarray(1e-3),
            "dz": np.asarray(1e-3),
            "colocation_rule": np.asarray("zeros, for the route"),
            "freqs": np.zeros(2),
            "coordinates": np.zeros((3, 3)),
            "normals": np.zeros((3, 3)),
            "face_id": np.zeros(3, dtype=np.int8),
            "dA": np.zeros(3),
            "E_t": np.zeros((2, 3, 2), dtype=np.complex128),
            "H_t": np.zeros((2, 3, 2), dtype=np.complex128),
            "J_s": np.zeros((2, 3, 3), dtype=np.complex128),
            "M_s": np.zeros((2, 3, 3), dtype=np.complex128),
            "flux": np.zeros(2),
            "flux_face": np.zeros((2, 3), dtype=np.complex128),
        }
        # the fixture is only a surface dump if it carries exactly the reader's
        # keys, so a key added to the writer later fails here rather than
        # silently turning this test into a plane-dump test
        assert set(payload) == set(SURFACE_DUMP_KEYS), (
            sorted(set(SURFACE_DUMP_KEYS) ^ set(payload))
        )
        assert app.PLANE_KEY not in payload
        if stamp_schema:
            payload["schema"] = np.asarray(SURFACE_DUMP_SCHEMA)
        np.savez(path, **payload)
        return path

    stamped = _write(tmp_path / "surface.npz", stamp_schema=True)
    with pytest.raises(SystemExit) as stamped_exit:
        app.load_any_dump(stamped)
    assert stamped_exit.value.code == 2, (
        "a surface dump reached the plane loader instead of being refused: "
        f"exit code {stamped_exit.value.code!r}"
    )
    stamped_err = capsys.readouterr().err
    assert "Huygens surface dump" in stamped_err, (
        "the refusal does not say what the file IS, so a caller cannot tell a "
        f"surface archive from a corrupt plane dump: {stamped_err!r}"
    )

    # the branch that most needs pinning: an archive written BEFORE the
    # discriminator existed carries no ``schema`` at all, and the key signature
    # alone has to route it to the same refusal
    legacy = _write(tmp_path / "surface_legacy.npz", stamp_schema=False)
    with pytest.raises(SystemExit) as legacy_exit:
        app.load_any_dump(legacy)
    assert legacy_exit.value.code == 2, (
        "an archive with no ``schema`` key fell through to the plane loader on "
        f"its key signature alone: exit code {legacy_exit.value.code!r}"
    )
    legacy_err = capsys.readouterr().err
    assert "Huygens surface dump" in legacy_err, (
        "the legacy key-signature route does not name the file as a surface "
        f"dump: {legacy_err!r}"
    )
