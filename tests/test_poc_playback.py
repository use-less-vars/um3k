"""Headless proof that the emfit-vis play trigger RETURNS while playback runs.

REAL, not simulated: ``run_web_vis`` boots for real (server, state,
controller, every ``@ctrl.set(...)`` registration is the shipped decorator), and
the handler exercised below is the object the page's ``{{ play_label }}`` button
calls.  The handler's closure cells hand back the *live* ``handles`` dict and the
*live* ``state`` object, so the generation counter, ``state.playing``,
``asyncio.create_task`` and the ``_play_loop`` body are the shipped code,
asserted in place - no copies, no re-implementation, no wrapper.

DOUBLED: the OpenGL / client-push boundary only - ``pyvista.Plotter.render`` and
the ``update`` call on the view ``plotter_ui`` returns.  This image has no EGL,
no libOSMesa and no X server, so a real ``render()`` segfaults the interpreter
(``DISPLAY=`` / ``Failed to load EGL`` / ``Segmentation fault``).  That is a
device double, not a mock of the code under test: nothing inside
``_on_play_toggle``, ``_play_loop`` or ``_show`` is replaced or skipped.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries artifacts/verify_wd.py adds, so `import poc_app`
        # resolves from server/poc_app.py
        sys.path.insert(0, _p)

# In this image pyvista/trame/vtk live in the repo's own venv (its bin/python is
# broken, the site-packages tree is not).  On a host where they are installed
# normally this directory is either absent or already on sys.path, so the block
# is inert there.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip(
    "pyvista", reason="pyvista is the web UI's renderer; playback test needs it"
)
pytest.importorskip(
    "trame.app", reason="trame serves the page; playback test needs it"
)
pytest.importorskip(
    "trame.ui.vuetify3",
    reason="trame.ui.vuetify3 is what run_web_vis builds its layout with",
)

FPS = 25
TRIGGER_NAME = "play_toggle"
RETURN_TIMEOUT_S = 1.0
LOOP_EXIT_TIMEOUT_S = 2.0


def _flatten_block(block) -> str:
    """Every string a confidence block carries, joined with newlines.

    The panel is PROSE: the number a reader is meant to see may be in a row's
    text, and the formula it came from is in ``basis``.  A test that only looked
    at the row texts would miss a deviation restated in the basis (or, worse,
    miss that it is NOT restated anywhere), so the assertions look at one blob.
    """
    parts = []
    for label, text in block.get("rows") or []:
        parts.append(str(label))
        parts.append(str(text))
    parts.extend(str(item) for item in block.get("basis") or [])
    parts.extend(str(item) for item in block.get("sources") or [])
    parts.append(str(block.get("caption") or ""))
    return "\n".join(parts)


class _Stop(Exception):
    """Unwinds ``run_web_vis`` just before it enters the event loop."""


def _fixture_info(app, path: Path, *, structure_id="A", load_ohm=50.0,
                  schema=None) -> dict:
    """Minimal ``emfit.vis/2`` dump, the same field set verify_wd.py uses.

    ``structure_id`` / ``load_ohm`` are the dump's PROVENANCE keys; pass ``None``
    for either to write a version-1-shaped file that does not carry it.  The
    default pair is Run A's own arm and load, which is what every other test
    here reads back.  ``schema`` overrides the declared version.
    """
    nt, nx, nz = 4, 8, 5
    nt_x, ny_x = 3, 6
    rng = np.random.default_rng(0)
    payload = {
        "schema": app.VIS_SCHEMA if schema is None else schema,
        "ez_ycut": rng.normal(size=(nt, nx, nz)),
        "ez_xcut_near": rng.normal(size=(nt_x, ny_x, nz)),
        "ez_xcut_far": rng.normal(size=(nt_x, ny_x, nz)),
        "t_ns": np.arange(nt) * 1e-3,
        "frame_index": np.arange(nt),
        "frame_index_xcut": np.arange(nt_x) * 2,
        "x_mm": np.linspace(0.0, 7.0, nx),
        "y_mm": np.linspace(-1.0, 1.0, ny_x),
        "z_mm": np.linspace(0.0, 2.0, nz),
        "nx": np.array(nx),
        "ny": np.array(ny_x),
        "nz": np.array(nz),
        "nt": np.array(nt),
        "nt_x": np.array(nt_x),
        "dt_s": np.array(1e-13),
        "cell_m": np.array(1e-5),
        "j_cut": np.array(3),
        "dump_stride": np.array(2),
        "nsteps": np.array(6),
        "f_ref_hz": np.array(1e10),
        "f_pulse_hz": np.array(1e10),
        "xcut_near_mm": np.array(1.0),
        "xcut_far_mm": np.array(5.0),
        "port_x_mm": np.array(0.5),
        "load_x_mm": np.array(6.5),
        "substrate_h_mm": np.array(0.5),
        "strip_w_mm": np.array(1.0),
        "eps_r": np.array(10.0),
        "v_analytic_m_s": np.array(1.5e8),
        "v_measured_m_s": np.array(1.5e8),
        "t_traverse_ns": np.array(0.05),
        "v_measured_reliable": np.array(1.0),
        "velocity_note": np.array("probe"),
    }
    # Written only when recorded, so `None` produces the version-1 shape: a dump
    # that says nothing about the arm it came from.
    if structure_id is not None:
        payload["structure_id"] = np.array(structure_id)
    if load_ohm is not None:
        payload["load_ohm"] = np.array(float(load_ohm))
    np.savez(path, **payload)
    return app.load_vis(path)


def _fixture_legacy_info(app, path: Path) -> dict:
    """Minimal legacy single-plane dump: the artefact the 8080 path serves.

    ``load_dump`` unpacks ``plane_ez`` plus five scalars and nothing else, and a
    dump that sits without a study record beside it is a supported state - the
    plane positions then fall back to the built-in constants.  That is exactly
    the shape ``evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz``
    has, so ``run_web`` - not ``run_web_vis`` - is the builder this fixture
    feeds.
    """
    rng = np.random.default_rng(0)
    np.savez(
        path,
        plane_ez=rng.normal(size=(9, 12, 5)),
        nstep=np.array(6),
        nx=np.array(9),
        ny=np.array(12),
        nz=np.array(5),
        cell_m=np.array(1e-4),
    )
    return app.load_dump(path)


def _boot_app(info):
    """Run ``run_web_vis`` up to the point it would call ``server.start``.

    Same recipe as artifacts/verify_wd.py: wrap ``trame.app.get_server`` so the
    live server object escapes, and make ``start`` raise so the event loop is
    never entered.  ``run_web_vis`` imports ``get_server`` inside the
    function, so patching the module attribute before the call is what it sees.
    """
    import trame.app as trame_app
    import poc_app as app

    real_get_server = trame_app.get_server
    box: dict = {}

    def fake_get_server(*args, **kwargs):
        srv = real_get_server(*args, **kwargs)
        box["srv"] = srv

        def _no_start(*_a, **_k):
            raise _Stop()

        srv.start = _no_start
        return srv

    trame_app.get_server = fake_get_server
    try:
        with contextlib.suppress(_Stop):
            app.run_web_vis(info, "127.0.0.1", 8999, fps=FPS)
    finally:
        trame_app.get_server = real_get_server

    assert "srv" in box, (
        "run_web_vis never reached server.start(): it returned early "
        "(missing web dependency) so no trigger was registered"
    )
    return app, box["srv"]


def _boot_web(info):
    """The same boot for ``run_web``, the builder a legacy dump is served by.

    ``run_web`` places no station clamp in front of its layout, so the station is
    handed the last captured plane.  ``pyvista.Plotter.render`` is doubled for
    the same reason the ``playback`` fixture doubles it: this image has no EGL,
    no libOSMesa and no X server, so a real render segfaults the interpreter.
    Nothing else about the builder is replaced.
    """
    import pyvista
    import trame.app as trame_app
    import poc_app as app

    real_get_server = trame_app.get_server
    real_render = pyvista.Plotter.render
    box: dict = {}

    def fake_get_server(*args, **kwargs):
        srv = real_get_server(*args, **kwargs)
        box["srv"] = srv

        def _no_start(*_a, **_k):
            raise _Stop()

        srv.start = _no_start
        return srv

    trame_app.get_server = fake_get_server
    pyvista.Plotter.render = lambda self, *a, **k: None  # no OpenGL here
    try:
        with contextlib.suppress(_Stop):
            app.run_web(info, "127.0.0.1", 8999, int(info["plane_ez"].shape[0]) - 1)
    finally:
        pyvista.Plotter.render = real_render
        trame_app.get_server = real_get_server

    assert "srv" in box, (
        "run_web never reached server.start(): it returned early (missing web "
        "dependency) so its layout was never built"
    )
    return app, box["srv"]


def _registered_trigger(ctrl, name):
    """The raw function registered by ``@ctrl.set(name)`` on the live controller."""
    holder = getattr(ctrl, name, None)
    assert holder is not None, (
        f"the controller exposes no {name!r} trigger; the play button binding "
        "is not registered, so there is nothing for the browser to call"
    )
    fn = getattr(holder, "func", holder)  # ControllerFunction -> the function
    fn = getattr(fn, "func", fn)
    assert callable(fn), f"{name!r} unwrapped to a non-callable: {fn!r}"
    return fn


def _closure_cells(fn) -> dict:
    cells = getattr(fn, "__closure__", None) or ()
    return dict(zip(fn.__code__.co_freevars, [c.cell_contents for c in cells]))


@pytest.fixture(scope="module")
def playback(tmp_path_factory):
    pyvista = pytest.importorskip("pyvista")
    import poc_app as app

    undos = []
    renders = []

    # --- device double #1: the OpenGL draw -------------------------------
    real_render = pyvista.Plotter.render

    def _no_render(self, *args, **kwargs):
        renders.append(1)  # counted, never performed

    pyvista.Plotter.render = _no_render
    undos.append(lambda: setattr(pyvista.Plotter, "render", real_render))

    try:
        info = _fixture_info(app, tmp_path_factory.mktemp("wd") / "dump.npz")
        app, srv = _boot_app(info)
        state, ctrl = srv.state, srv.controller

        trigger = _registered_trigger(ctrl, TRIGGER_NAME)
        cells = _closure_cells(trigger)
        assert "handles" in cells, (
            "the play trigger is not closed over the page's `handles` dict "
            f"(freevars: {sorted(cells)}) - cannot assert on the live generation "
            "counter; refusing to substitute a stand-in dict"
        )
        assert "state" in cells, (
            "the play trigger is not closed over `state` "
            f"(freevars: {sorted(cells)})"
        )
        handles, live_state = cells["handles"], cells["state"]
        assert handles is not None and live_state is state, (
            "closure cells do not point at the live server state"
        )

        # --- device double #2: the client push --------------------------
        view = handles.get("view")
        if view is not None and hasattr(view, "update"):
            real_update = view.update

            def _no_update(*_a, **_k):
                return None

            view.update = _no_update
            undos.append(lambda: setattr(view, "update", real_update))

        yield SimpleNamespace(
            app=app,
            server=srv,
            state=live_state,
            handles=handles,
            trigger=trigger,
            view=view,
            renders=renders,
            undos=undos,
        )
    finally:
        for undo in reversed(undos):
            undo()


def _other_tasks() -> set:
    current = asyncio.current_task()
    return {t for t in asyncio.all_tasks() if t is not current}


def test_play_trigger_returns_and_schedules_exactly_one_task(playback):
    async def scenario() -> None:
        handles, state, trigger = playback.handles, playback.state, playback.trigger
        baseline = int(handles.get("generation", 0))
        assert state.playing is False, "boot already left the page playing"

        tasks_before = _other_tasks()
        # ASSERTION 1 - the bug.  The pre-fix handler held the whole
        # `while ... await asyncio.sleep(1.0 / fps)` loop in its own body, so it
        # never resolved: this wait_for raised TimeoutError and the client RPC
        # stayed pending forever (pause/prev/next/switch-plane/camera dead
        # while the picture kept moving).  It must return now.
        try:
            await asyncio.wait_for(trigger(), timeout=RETURN_TIMEOUT_S)
        except asyncio.TimeoutError:
            pytest.fail(
                "the play trigger did not return within "
                f"{RETURN_TIMEOUT_S}s: an async Trame trigger that never returns "
                "blocks the client RPC, so pause/prev/next/switch-plane and "
                "camera drags all stop reaching the server while the animation "
                "keeps running"
            )
        created = _other_tasks() - tasks_before

        # ASSERTION 2 - the first press started playback and bumped the counter.
        assert "generation" in handles, (
            "the trigger did not write handles['generation']; the loop has no "
            "generation to compare against, so nothing could ever stop it"
        )
        assert int(handles["generation"]) == baseline + 1, (
            f"generation counter went {baseline} -> {handles['generation']}, "
            "expected exactly +1"
        )
        assert state.playing is True, "the first press did not set state.playing"

        # ASSERTION 4a - and it handed the loop to a background task.
        assert len(created) == 1, (
            f"expected exactly 1 background task created by the first press, "
            f"found {len(created)}"
        )
        task = created.pop()
        try:
            # ASSERTION 3 - the second press stops it, and the generation
            # counter is what makes the running loop notice.
            try:
                await asyncio.wait_for(trigger(), timeout=RETURN_TIMEOUT_S)
            except asyncio.TimeoutError:
                pytest.fail(
                    "the second press of the play trigger did not return within "
                    f"{RETURN_TIMEOUT_S}s"
                )
            assert state.playing is False, (
                "the second press did not clear state.playing"
            )
            assert int(handles["generation"]) == baseline + 2, (
                "second press went generation "
                f"{handles['generation']}, expected {baseline + 2}"
            )

            # ASSERTION 4b - the loop actually exited (generation counter works,
            # not just the playing flag).  A loop that ignored the counter would
            # still be alive here.
            deadline = asyncio.get_running_loop().time() + LOOP_EXIT_TIMEOUT_S
            while not task.done() and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.01)
            assert task.done(), (
                "the play loop was still alive "
                f"{LOOP_EXIT_TIMEOUT_S}s after the second press: the generation "
                "counter did not stop it"
            )
            exc = None if task.cancelled() else task.exception()
            assert exc is None, f"the play loop died on {exc!r}"
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    asyncio.run(scenario())


# --- the dump's own provenance, read back ------------------------------------
#
# The .npz records WHICH arm wrote it (``structure_id``) and what it was
# terminated in (``load_ohm``).  Neither is in the fields and neither can be
# derived from them, so these tests read the two keys off a written file and
# assert the one line the page shows - not a re-formatted copy of the inputs.

READOUT_A = "structure: A (50 \u03a9)"


def test_dump_provenance_is_read_back_from_the_file(tmp_path: Path) -> None:
    import poc_app as app

    info = _fixture_info(app, tmp_path / "a.npz")
    assert info["structure_id"] == "A", (
        "the loader dropped structure_id; without it the page cannot say which "
        "arm wrote the dump"
    )
    assert info["load_ohm"] == pytest.approx(50.0)
    assert app._structure_readout_text(info) == READOUT_A


def test_readout_names_the_recorded_load_not_a_default(tmp_path: Path) -> None:
    import poc_app as app

    info = _fixture_info(app, tmp_path / "b.npz", structure_id="B",
                         load_ohm=100.0)
    assert app._structure_readout_text(info) == "structure: B (100 \u03a9)", (
        "the readout did not follow the file: a 100 ohm arm must print 100, not "
        "a hard-coded 50"
    )


def test_version_1_dump_without_provenance_still_loads(tmp_path: Path) -> None:
    import poc_app as app

    path = tmp_path / "legacy.npz"
    info = _fixture_info(app, path, structure_id=None, load_ohm=None,
                        schema="emfit.wavedude/1")
    assert info["format"] == "wavedude"
    assert info["structure_id"] is None
    assert app._structure_readout_text(info) == "structure: unknown", (
        "a dump that records no arm must read as unknown, not be guessed"
    )
    assert app.load_any_dump(path)["format"] == "wavedude", (
        "load_any_dump refused a version-1 dump after the schema bump; the bump "
        "must not orphan the files already on disk"
    )


def test_page_publishes_the_structure_readout(playback) -> None:
    assert playback.state.structure_readout == READOUT_A, (
        "the page never published state.structure_readout (got "
        f"{getattr(playback.state, 'structure_readout', '<absent>')!r}); the "
        "readout line is emitted from state and would render blank"
    )


# --- which arm's S-parameters the panel reads --------------------------------
#
# The sweep is chosen by the dump's OWN structure id, never by a constant, and
# never borrowed across arms.  Each test below points the two maps at files it
# writes itself under tmp_path, so nothing here needs evidence/ or artifacts/ to
# be present: what is asserted is WHICH path was resolved and reported.
#
# The dump and the other arm's artefacts deliberately live in DIFFERENT
# directories so these tests exercise the per-arm fallback and the scan as
# separate things - ``test_sweep_beside_the_dump_ignores_the_other_arm`` is the
# one that puts both arms' summaries beside the same dump on purpose.


def _write_sweep(path: Path, rows) -> Path:
    """A sweep summary with one synthetic row per ``(f_ghz, s11, s21)``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dossier": "poc-playback-test",
        "generated_utc": "2026-01-01T00:00:00Z",
        "bin_spacing_mhz": 500.0,
        "rows": [
            {
                "artefact": f"{path.stem}_k{k}.json",
                "f_ghz_used": f_ghz,
                "s11.magnitude": s11,
                "s21.magnitude": s21,
                "k": k,
                "beta_ambiguous": False,
                "errors": [],
            }
            for k, (f_ghz, s11, s21) in enumerate(rows)
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _boot_s_params(app, info, monkeypatch, *, sweeps, runs):
    """Boot the page with these per-arm maps and return the panel it BUILT.

    There is no S-parameters button any more: the tab owns visibility, so
    ``run_web_vis`` fills the panel while it lays the page out and caches it on
    ``handles["s_params"]``. The maps are patched on the module BEFORE the boot
    for exactly that reason - the eager load reads this arm's artefact off disk
    during layout, not on a click.

    ``handles``/``state`` come off the play trigger's closure: it is still the
    page's own dict and object, and a stand-in would prove nothing about the
    live page.
    """
    monkeypatch.setattr(app, "MULTIFREQ_BY_STRUCTURE", dict(sweeps))
    monkeypatch.setattr(app, "SINGLE_RUN_BY_STRUCTURE", dict(runs))
    app, srv = _boot_app(info)
    trigger = _registered_trigger(srv.controller, TRIGGER_NAME)
    cells = _closure_cells(trigger)
    assert "handles" in cells and "state" in cells, (
        "the play trigger is not closed over the page's `handles` and "
        f"`state` (freevars: {sorted(cells)}), so the live panel cannot be "
        "asserted on and a stand-in would prove nothing"
    )
    handles, state = cells["handles"], cells["state"]
    assert "s_params" in handles, (
        "no handles['s_params'] after the layout was built: the panel is now "
        "built AT LAYOUT TIME (there is no S-parameters button left to press), "
        "so a missing entry means run_web_vis never eager-loaded it - or the "
        "loader raised and only printed to stderr"
    )
    return handles["s_params"], state


def test_s_params_panel_dispatches_on_structure(tmp_path: Path, monkeypatch) -> None:
    """A B dump is drawn from B's sweep - A's sweep has four rows and is unused."""
    import poc_app as app

    dump = tmp_path / "dumps" / "b.npz"
    dump.parent.mkdir(parents=True)
    b_summary = _write_sweep(
        tmp_path / "sweeps" / "build_B_100ohm_multifreq_summary.json",
        [(4.0, 0.48, 0.53), (6.0, 0.47, 0.52)],
    )
    a_summary = _write_sweep(
        tmp_path / "sweeps" / "build_A_50ohm_multifreq_summary.json",
        [(3.0, 0.11, 0.99), (4.0, 0.12, 0.98),
         (5.0, 0.13, 0.97), (6.0, 0.14, 0.96)],
    )
    info = _fixture_info(app, dump, structure_id="B", load_ohm=100.0)

    panel, state = _boot_s_params(
        app, info, monkeypatch,
        sweeps={"A": str(a_summary), "B": str(b_summary)},
        runs={},
    )

    assert panel["path"] == b_summary, (
        f"the B dump did not resolve to B's sweep: the panel read {panel['path']} "
        f"instead of {b_summary}, so the |S11| beside a B field picture would be "
        "A's number"
    )
    assert len(panel["points"]) == 2, (
        f"the panel kept {len(panel['points'])} rows, expected B's 2: A's sweep "
        "has 4, so a count of 4 means A's rows were drawn beside a B dump"
    )
    assert panel["single_point"] is False, (
        "a real sweep was present but the panel flagged it as a single point"
    )
    caption = panel["caption"]
    assert b_summary.name in caption, (
        f"the caption does not name B's sweep ({b_summary.name}): {caption!r}"
    )
    assert a_summary.name not in caption, (
        f"the caption names A's sweep on a B dump: {caption!r}"
    )
    assert panel.get("image") or panel.get("rows"), (
        "the panel was built from a real sweep but carries neither a picture nor "
        f"text rows for its tab to show (image={panel.get('image')!r}, "
        f"rows={panel.get('rows')!r}): the eager load built nothing"
    )
    assert state.s_params_caption == panel["caption"] and (
        state.s_params_number == panel["number"]
    ), (
        "the tab's state strings are not the panel's, so its tab would open "
        f"empty beside a real sweep (caption {state.s_params_caption!r}, "
        f"number {state.s_params_number!r})"
    )


def test_s_params_panel_never_borrows_the_other_arm(tmp_path: Path,
                                                   monkeypatch) -> None:
    """B has neither a sweep nor a single run: the panel reports nothing, not A's rows."""
    import poc_app as app

    dump = tmp_path / "dumps" / "b.npz"
    dump.parent.mkdir(parents=True)
    a_summary = _write_sweep(
        tmp_path / "sweeps" / "build_A_50ohm_multifreq_summary.json",
        [(3.0, 0.11, 0.99), (4.0, 0.12, 0.98),
         (5.0, 0.13, 0.97), (6.0, 0.14, 0.96)],
    )
    info = _fixture_info(app, dump, structure_id="B", load_ohm=100.0)

    panel, _state = _boot_s_params(
        app, info, monkeypatch,
        sweeps={"A": str(a_summary),
                "B": str(tmp_path / "sweeps" / "missing_B_multifreq_summary.json")},
        runs={"B": str(tmp_path / "runs" / "missing_B_run.json")},
    )

    assert panel["points"] == [], (
        f"the B panel kept {len(panel['points'])} rows while B has no sweep and no "
        "single run: those rows are A's, i.e. the panel borrowed the other arm"
    )
    assert panel["path"] is None, (
        f"the B panel resolved {panel['path']!r} although only A's sweep exists"
    )
    caption = panel["caption"]
    assert "no S-parameter data" in caption, (
        f"the panel did not say it had no data for B: {caption!r}"
    )
    assert a_summary.name not in caption, (
        f"the caption names A's sweep while reporting no data for B: {caption!r}"
    )


def test_s_params_panel_reports_no_data(tmp_path: Path, monkeypatch) -> None:
    """Neither arm has an artefact: the tab loads and says so, and does not raise."""
    import poc_app as app

    dump = tmp_path / "dumps" / "b.npz"
    dump.parent.mkdir(parents=True)
    info = _fixture_info(app, dump, structure_id="B", load_ohm=100.0)

    panel, state = _boot_s_params(app, info, monkeypatch, sweeps={}, runs={})

    assert panel["reason"] == "no S-parameter data", (
        "the empty panel did not report the reason it had nothing to show: "
        f"{panel['reason']!r}"
    )
    assert "no S-parameter data" in panel["caption"], (
        f"the caption says nothing about the missing data: {panel['caption']!r}"
    )
    assert "structure B" in panel["caption"], (
        "the empty caption does not name the arm it was empty FOR, so a reader "
        f"cannot tell which case looked: {panel['caption']!r}"
    )
    assert panel["points"] == [] and panel["image"] is None and panel["rows"] == [], (
        "the empty panel carried rows, a point or a picture it could not have read"
    )
    assert panel["caption"] in state.s_params_caption, (
        "the 'no S-parameter data' panel was built but its caption never reached "
        f"the tab's state ({state.s_params_caption!r} does not contain "
        f"{panel['caption']!r}), so the tab would open empty instead of saying so "
        "- note the state caption legitimately appends the text-rows reason"
    )


def test_the_s_parameters_tab_is_selected_and_populated_without_a_click(
    tmp_path: Path, monkeypatch
) -> None:
    """The boot alone selects the S-Parameters tab AND fills it - no click.

    The tab owns visibility now: there is no S-parameters button and no
    ``s_params_style`` string, so the page has to arrive with its default tab
    selected AND with a cached, non-empty panel behind it. That is the whole
    contract this test pins.

    What it cannot prove: that Vuetify actually RENDERS the tab body in a
    browser. The layout is a server-side declaration and ``v_model`` is only
    consumed by the client, so a headless proof can show the selection and the
    payload but not the pixels. It also cannot prove which tab a human ends up
    looking at after clicking - only the page's own default selection.
    """
    import poc_app as app

    dump = tmp_path / "dumps" / "b.npz"
    dump.parent.mkdir(parents=True)
    summary = _write_sweep(
        tmp_path / "sweeps" / "build_B_100ohm_multifreq_summary.json",
        [(4.0, 0.48, 0.53), (5.0, 0.47, 0.52)],
    )
    info = _fixture_info(app, dump, structure_id="B", load_ohm=100.0)

    # No interaction of any kind: the helper only boots and looks.
    panel, state = _boot_s_params(
        app, info, monkeypatch,
        sweeps={"B": str(summary)},
        runs={},
    )

    assert state.tab == "s_params", (
        f"the page did not boot onto the S-Parameters tab (state.tab={state.tab!r}), "
        "so the panel it filled would still be one click away"
    )
    assert panel["path"] == summary and len(panel["points"]) == 2, (
        "the panel built at layout time did not read B's two-row sweep: "
        f"path={panel['path']!r}, points={len(panel['points'])}"
    )
    assert panel.get("image") or panel.get("rows"), (
        "the eagerly built tab has neither a picture nor text rows to show "
        f"(image={panel.get('image')!r}, rows={panel.get('rows')!r})"
    )
    assert state.s_params_caption == panel["caption"], (
        "the loader built the panel but never pushed its caption onto the tab's "
        f"state ({state.s_params_caption!r} != {panel['caption']!r})"
    )
    assert state.s_params_number == panel["number"], (
        "the loader never pushed the panel's number line onto the tab's state "
        f"({state.s_params_number!r} != {panel['number']!r})"
    )


def test_sweep_beside_the_dump_wins_over_the_registry(tmp_path: Path,
                                                      monkeypatch) -> None:
    """The scan for a sweep BESIDE the dump actually runs, and wins.

    This is the regression gate for a scan that had never executed once:
    ``_multifreq_candidates`` did ``npz_path.parent`` while every caller passed
    a ``str`` (``load_multifreq(info["path"], ...)``), so the glob raised
    ``'str' object has no attribute 'parent'``, the exception was swallowed
    with a message that named no directory, and every press fell through to the
    registry constant.  Two arms then looked identical for a reason that had
    nothing to do with the physics.

    The two files are deliberately DIFFERENT files in DIFFERENT directories, so
    the assertion cannot pass by both paths coinciding:

    * the dump's own directory carries a correctly-named summary - the one the
      glob is supposed to find, with 3 rows;
    * the registry for arm B points somewhere else entirely, at a file with 1
      row that also must NOT match the glob pattern.

    Before the coercion this test FAILED: ``panel["path"]`` was the registry
    file and the panel kept its 1 row, because the beside-dump glob never ran.
    It passes only once the scan is alive and preferred - which is also the
    precedence the module documents ("looked for beside the dump first, then at
    the entry for this arm").
    """
    import poc_app as app

    dump = tmp_path / "dumps" / "b.npz"
    dump.parent.mkdir(parents=True)
    beside = _write_sweep(
        dump.parent / "build_B_100ohm_multifreq_summary.json",
        [(4.0, 0.48, 0.53), (5.0, 0.47, 0.52), (6.0, 0.46, 0.51)],
    )
    # Not "multifreq"/"summary" in the name, and a different directory, so it
    # cannot be reached by the glob - only by the registry entry.
    registry = _write_sweep(
        tmp_path / "elsewhere" / "registry_B_fallback.json",
        [(9.0, 0.99, 0.01)],
    )
    info = _fixture_info(app, dump, structure_id="B", load_ohm=100.0)
    # The REAL page hands the sweep loader a STRING: `info["path"]` arrives from
    # JSON / a trame value, not from ``load_vis``.  That is the shape that made
    # the beside-dump glob raise, so the gate has to use it too - with a Path
    # here the old code would pass this test without ever scanning.
    info["path"] = str(info["path"])

    panel, _state = _boot_s_params(
        app, info, monkeypatch,
        sweeps={"B": str(registry)},
        runs={},
    )

    assert panel["path"] == beside, (
        f"the panel resolved {panel['path']!r} for a dump that has "
        f"{beside.name!r} sitting beside it: the beside-dump scan did not run "
        "or did not win, so the registry fallback was used instead"
    )
    assert len(panel["points"]) == 3, (
        f"the panel kept {len(panel['points'])} rows, expected the beside-dump "
        "sweep's 3: a count of 1 is the registry file's single row"
    )
    caption = panel["caption"]
    assert beside.name in caption, (
        f"the caption does not name the beside-dump sweep ({beside.name}): "
        f"{caption!r}"
    )
    assert registry.name not in caption, (
        f"the caption names the registry fallback while a sweep sits beside "
        f"the dump: {caption!r}"
    )


def test_sweep_beside_the_dump_ignores_the_other_arm(tmp_path: Path,
                                                     monkeypatch) -> None:
    """Both arms' sweeps sit beside one B dump: B's is read, not the first name.

    ``evidence/termination/`` is exactly this shape - A's and B's summaries lie in
    the same directory as the dumps - so an unfiltered ``sorted()`` over the glob
    resolved a B dump to A's sweep, and nothing failed: ``build_A_50ohm_...``
    simply sorts first.  The arm is the only thing that may decide this; the
    first letter of a filename is not a statement about the physics.

    The other arm's file is a complete, readable, VALID summary (1 row) and does
    sort first, so the unfiltered scan really did resolve to it - these
    assertions (B's path, 3 rows) fail before the filter rather than passing by
    luck.
    """
    import poc_app as app

    dump = tmp_path / "dumps" / "b.npz"
    dump.parent.mkdir(parents=True)
    other_arm = _write_sweep(
        dump.parent / "build_A_50ohm_multifreq_summary.json",
        [(4.0, 0.11, 0.99)],
    )
    beside = _write_sweep(
        dump.parent / "build_B_100ohm_multifreq_summary.json",
        [(4.0, 0.48, 0.53), (5.0, 0.47, 0.52), (6.0, 0.46, 0.51)],
    )
    info = _fixture_info(app, dump, structure_id="B", load_ohm=100.0)
    info["path"] = str(info["path"])

    panel, _state = _boot_s_params(
        app, info, monkeypatch,
        # A registry entry that cannot match: it is not "multifreq"/"summary"
        # named and does not exist, so only the beside-dump scan can supply a
        # sweep - and it has two arms to choose between.
        sweeps={"B": str(tmp_path / "elsewhere" / "missing_B_fallback.json")},
        runs={},
    )

    assert panel["path"] == beside, (
        f"the panel resolved {panel['path']!r} for a dump that records structure "
        f"B while {other_arm.name!r} and {beside.name!r} both sit beside it: the "
        "beside-dump scan chose by filename order instead of by arm"
    )
    assert len(panel["points"]) == 3, (
        f"the panel kept {len(panel['points'])} rows, expected B's 3: a count of "
        f"1 is {other_arm.name!r}, the OTHER arm's single row"
    )
    caption = panel["caption"]
    assert beside.name in caption, (
        f"the caption does not name B's own sweep ({beside.name}): {caption!r}"
    )
    assert other_arm.name not in caption, (
        f"the caption names the other arm's sweep while drawing B: {caption!r}"
    )


# --- the live solve: the command line, and where it may write -----------------
# Nothing here runs a solve.  ``solve_argv`` builds the argv and stops, which is
# the whole point of splitting it out: the flags can be asserted in milliseconds
# instead of by waiting out a field solve, and a wrong flag is caught here rather
# than at the end of one.


def test_solve_argv_targets_the_existing_cut_plane_flag(tmp_path: Path) -> None:
    """The argv is the solver's own command line, with no invented flag.

    ``--xcut-near-mm`` already exists over there (it is what the user asked for
    when they said ``--xcut``), so a new flag would be an option the solver
    would reject.  The length assertion is the other half: ten tokens means no
    stray flag was slipped in beside the five that belong there - ``--out`` is
    the sixth, and it is the one that stops a press rewriting a certified file.
    """
    import poc_app as app

    argv = app.solve_argv("B", 20.4, app.LIVE_DUMP)

    assert len(argv) == 10, (
        f"the solve argv is {argv!r}: exactly [python, solver, --structure, sid, "
        "--xcut-near-mm, value, --vis-dump, out, --out, artefact] is what the "
        "solver accepts"
    )
    assert argv[0] == sys.executable, (
        "the solve does not run on the interpreter that is serving the page; a "
        "bare 'python' would pick whatever is on PATH instead"
    )
    assert "run_build_A.py" in argv[1] and Path(argv[1]) == app.SOLVER_SCRIPT, (
        f"argv[1] is {argv[1]!r}, not the solver at {app.SOLVER_SCRIPT}"
    )
    assert argv[2:4] == ["--structure", "B"], (
        f"the arm is not passed as the solver's own --structure: {argv[2:4]!r}"
    )
    assert argv[4] == "--xcut-near-mm", (
        f"the cut plane is not passed as --xcut-near-mm: {argv[4]!r} - the "
        "solver has no --xcut, so this would exit on an unknown argument"
    )
    assert argv[5] == "20.4", (
        f"the cut position is {argv[5]!r}: it must read as 20.4, not as the "
        "float's long tail 20.400000000000002"
    )
    assert argv[6:8] == ["--vis-dump", str(app.LIVE_DUMP)], (
        f"the dump target is not the solver's --vis-dump: {argv[6:8]!r}"
    )
    assert argv[8] == "--out", (
        f"the run's own artefact is not passed as the solver's --out: {argv[8]!r}"
    )


def test_solve_argv_refuses_to_overwrite_a_certified_dump(tmp_path: Path) -> None:
    """Two refusals, both about not being allowed to guess or to clobber.

    ``evidence/`` holds the certified dumps a report quotes, so a page button
    must not be able to write there at all.  And an unnamed arm has no default:
    solving "whatever A is" when the caller said nothing would write a dump that
    claims a provenance nobody chose.
    """
    import poc_app as app

    certified = app.EVIDENCE_DIR / "vis_dump.npz"
    with pytest.raises(ValueError):
        app.solve_argv("A", 20.4, certified)
    with pytest.raises(ValueError):
        app.solve_argv(None, 20.4, app.LIVE_DUMP)

    assert app.EVIDENCE_DIR.resolve() not in app.LIVE_DUMP.resolve().parents, (
        f"LIVE_DUMP ({app.LIVE_DUMP}) is inside {app.EVIDENCE_DIR}: the default "
        "target a live solve uses must not be a certified directory"
    )


def test_solve_argv_always_names_its_own_out_artefact() -> None:
    """Every press gets its OWN ``--out``, never the solver's certified default.

    With no ``--out`` the solver falls back to its own table -
    ``evidence/termination/build_A_50ohm.json``, a file a report quotes - so one
    press rewrote certified numbers.  The second half is uniqueness: two solves
    that resolved to one name would have the second silently replace the first
    run's artefact while the page still said "solved -> ...".
    """
    import poc_app as app

    first = app.solve_argv("A", 20.4, app.LIVE_DUMP)
    second = app.solve_argv("A", 20.4, app.LIVE_DUMP)

    certified = app.SOLVER_SCRIPT.parent / "build_A_50ohm.json"
    artefacts = []
    for argv in (first, second):
        assert argv.count("--out") == 1, f"no single --out in {argv!r}"
        artefact = Path(argv[argv.index("--out") + 1])
        artefacts.append(artefact)
        assert artefact != certified, (
            f"--out is {artefact}, the solver's own certified default: the press "
            "would overwrite a file the report quotes"
        )
        assert app.EVIDENCE_DIR.resolve() not in artefact.resolve().parents, (
            f"--out is {artefact}, inside {app.EVIDENCE_DIR}"
        )
        assert artefact.parent == app.LIVE_DUMP.parent, (
            f"--out is {artefact}: a live solve writes beside LIVE_DUMP "
            f"({app.LIVE_DUMP.parent}), the existing artefacts convention"
        )
        assert "resistor" in artefact.name, (
            f"--out is {artefact.name}: a resistor run has to be tellable at a "
            "glance from a netlist run"
        )
    assert artefacts[0] != artefacts[1], (
        f"two solves both claim {artefacts[0]}: the second overwrites the first"
    )
    # A resistor run appends NOTHING but its own --out: no --netlist, no file.
    assert app.solve_netlist_file(first) is None, (
        "the built-in resistor run was given a --netlist"
    )


def test_solve_argv_passes_the_netlist_as_a_file(tmp_path: Path) -> None:
    """A supplied netlist reaches the solver as a ``--netlist`` FILE, beside --out.

    The solver's interface is a path, so the text is written to disk - in the
    run's own directory rather than /tmp, where the copy would say nothing about
    which run it belonged to and would survive a crash of the page - and named
    off that run's artefact, so the pair is unmistakable in a listing.
    """
    import poc_app as app

    text = json.dumps({"name": "cut diode", "nodes": ["p", "n"], "elements": []})
    argv = app.solve_argv("A", 20.4, tmp_path / "live_run.npz", netlist_json=text)
    netlist_file = app.solve_netlist_file(argv)
    try:
        assert "--netlist" in argv and "--out" in argv, (
            f"the netlist run is missing a flag: {argv!r}"
        )
        assert netlist_file is not None
        assert argv[argv.index("--netlist") + 1] == str(netlist_file), (
            f"--netlist does not name the file that was written: {argv!r}"
        )
        assert netlist_file.parent == tmp_path, (
            f"the netlist was written to {netlist_file.parent}, not beside the run"
        )
        assert netlist_file.read_text(encoding="utf-8") == text, (
            "the file the solver reads is not the text the user supplied"
        )
        artefact = Path(argv[argv.index("--out") + 1])
        assert artefact.parent == tmp_path
        assert "netlist" in artefact.name and "cut_diode" in artefact.name, (
            f"--out is {artefact.name}: a netlist run has to say so, and say which "
            "circuit"
        )
        assert netlist_file.name.startswith(artefact.stem), (
            f"{netlist_file.name} does not pair with {artefact.name}"
        )
    finally:
        if netlist_file is not None:
            netlist_file.unlink()

    with pytest.raises(ValueError):
        app.solve_argv("A", 20.4, tmp_path / "live_run.npz", netlist_json="{oops")
    assert not list(tmp_path.glob("*netlist*")), (
        "a refused netlist left a file behind - one per bad edit would pile up"
    )


def test_reload_page_sees_a_different_dump(tmp_path: Path) -> None:
    """Reload is a real second load, and it does not reach back into the first.

    Two dumps that record different arms are loaded through the same call boot
    uses.  What is asserted is that the returned dict follows the FILE (path and
    recorded provenance), and that the first dict still describes the first dump
    afterwards - a reload that mutated the live data in place would pass the
    first half and fail this one.
    """
    import poc_app as app

    path_a = tmp_path / "first" / "a.npz"
    path_b = tmp_path / "second" / "b.npz"
    for parent in (path_a.parent, path_b.parent):
        parent.mkdir(parents=True)
    _fixture_info(app, path_a, structure_id="A", load_ohm=50.0)
    _fixture_info(app, path_b, structure_id="B", load_ohm=100.0)

    first = app.reload_page(path_a)
    first_path = first["info"]["path"]
    first_ez = np.array(first["planes"]["ez_ycut"], copy=True)

    second = app.reload_page(path_b)

    assert first["structure_id"] == "A" and second["structure_id"] == "B", (
        f"the two loads reported {first['structure_id']!r} and "
        f"{second['structure_id']!r}: reload did not read the arm off each file"
    )
    assert Path(first["info"]["path"]) == path_a
    assert Path(second["info"]["path"]) == path_b, (
        "the second reload still points at the first dump: the page would "
        "redraw the old file under the new one's name"
    )
    assert first["info"] is not second["info"]
    assert first["planes"] is not second["planes"]
    assert first["info"]["path"] == first_path, (
        "the second load rewrote the first dict's path"
    )
    assert np.array_equal(first["planes"]["ez_ycut"], first_ez), (
        "the second load changed the first page's field arrays in place"
    )



# --- the solve JOB, and the page swap it causes -------------------------------
# No solve is run here: the child is a two-line interpreter, so what is asserted
# is the plumbing (the return code becomes a status, the output becomes a log)
# rather than the physics, which the solver's own tests own.


def test_solve_job_reports_ok_and_failed(tmp_path: Path) -> None:
    """A finished child becomes 'ok'/'failed' with its own return code and log."""
    import poc_app as app

    # A job that has never been started is 'idle', and asking it is not an error:
    # the page's timer polls exactly like this on a page where nobody solved.
    idle = app.SolveJob([sys.executable, "-c", "print('unused')"], cwd=tmp_path)
    assert idle.poll() == "idle", (
        f"an unstarted job reported {idle.status!r}, expected 'idle': the poll "
        "timer must be able to ask before any button is pressed"
    )

    good = app.SolveJob([sys.executable, "-c", "print('hello')"], cwd=tmp_path)
    assert good.run() == "ok", (
        f"a child that exited 0 reported {good.status!r} (rc={good.returncode})"
    )
    assert good.returncode == 0
    assert "hello" in good.log, (
        "the child's stdout never reached the job log, so a failed solve would "
        f"show an empty tail to the operator: {good.log!r}"
    )

    bad = app.SolveJob(
        [sys.executable, "-c", "raise SystemExit(3)"], cwd=tmp_path
    )
    assert bad.run() == "failed", (
        f"a child that exited 3 reported {bad.status!r}: a failed solve would be "
        "shown as a success"
    )
    assert bad.returncode == 3, (
        f"the job recorded rc={bad.returncode} for a child that exited 3"
    )


def test_apply_page_swaps_the_live_page(tmp_path: Path) -> None:
    """apply_page replaces the page's own keys - and nothing else - in place."""
    import poc_app as app

    old = tmp_path / "old" / "a.npz"
    new = tmp_path / "new" / "b.npz"
    for parent in (old.parent, new.parent):
        parent.mkdir(parents=True)
    _fixture_info(app, old, structure_id="A", load_ohm=50.0)
    _fixture_info(app, new, structure_id="B", load_ohm=100.0)

    new_page = app.reload_page(new)
    holder = dict(app.reload_page(old))
    # The live holder also carries the app's own bookkeeping; a reload must not
    # drop it, which is the half of this that a "holder = new_page" would miss.
    holder["frame_of_interest"] = 2

    summary = app.apply_page(holder, new_page)

    for key in app.PAGE_KEYS:
        assert key in new_page, (
            f"reload_page no longer returns {key!r}: apply_page would silently "
            "leave the old page in place"
        )
        assert holder[key] is new_page[key], (
            f"holder[{key!r}] was not replaced by the new page's: a finished "
            "solve would keep drawing the dump it replaced"
        )
    assert holder["frame_of_interest"] == 2, (
        "apply_page dropped an unrelated key from the holder: the page swap "
        "cleared bookkeeping it does not own"
    )
    assert Path(summary["old_path"]) == old, (
        f"the summary names {summary['old_path']!r} as the old page, not {old}"
    )
    assert Path(summary["new_path"]) == new, (
        f"the summary names {summary['new_path']!r} as the new page, not {new}"
    )
    assert summary["changed"], (
        "apply_page reported nothing as changed although every page key moved"
    )



def test_solve_button_reloads_the_page(tmp_path: Path, monkeypatch) -> None:
    """One press of Solve, end to end: the finished dump BECOMES the page.

    Everything under the child process is the shipped code - the ``solve_start``
    trigger the button binds, ``SolveJob.poll``, the ``_watch_solve`` task that
    trigger starts on the server's own loop, ``_poll_solve``, ``apply_page`` and
    ``_rebuild_sheets``.  The child is a stand-in that writes a dump saying a
    DIFFERENT arm, load, colour ceiling and velocity, so "the page swapped" is
    visible in the labels a reader actually sees, not only in a dict.

    Doubled: the OpenGL draw only (this image has no EGL), exactly as the
    playback fixture doubles it.
    """
    pyvista = pytest.importorskip("pyvista")
    import time

    import poc_app as app

    # The dump the child will "solve": arm B, 100 ohm, a different colour
    # ceiling and a different velocity record than the page booted with.
    solved_dump = tmp_path / "solved_B.npz"
    _fixture_info(app, solved_dump, structure_id="B", load_ohm=100.0)
    with np.load(solved_dump) as handle:
        payload = {key: handle[key] for key in handle.files}
    for key in ("ez_ycut", "ez_xcut_near", "ez_xcut_far"):
        payload[key] = payload[key] * 3.0
    payload["v_measured_m_s"] = np.array(2.0e8)
    payload["velocity_note"] = np.array("probe after solve")
    np.savez(solved_dump, **payload)

    fake_solver = tmp_path / "fake_solver.py"
    fake_solver.write_text(
        "import shutil, sys\n"
        f"shutil.copyfile({str(solved_dump)!r}, "
        "sys.argv[sys.argv.index('--vis-dump') + 1])\n"
        "print('fake solve done')\n",
        encoding="utf-8",
    )
    live_dump = tmp_path / "live" / "live_run.npz"
    # Both are module globals read at CALL time, so patching them redirects the
    # shipped code paths instead of re-implementing them.
    monkeypatch.setattr(app, "SOLVER_SCRIPT", fake_solver)
    monkeypatch.setattr(app, "LIVE_DUMP", live_dump)

    info = _fixture_info(
        app, tmp_path / "boot_A.npz", structure_id="A", load_ohm=50.0
    )

    real_render = pyvista.Plotter.render
    pyvista.Plotter.render = lambda self, *args, **kwargs: None
    try:
        app, srv = _boot_app(info)
        state, ctrl = srv.state, srv.controller
        trigger = _registered_trigger(ctrl, "solve_start")
        cells = _closure_cells(trigger)
        assert "state" in cells and "_start_watch" in cells, (
            "the solve trigger is not closed over the live page objects "
            f"(freevars: {sorted(cells)})"
        )
        # The watcher's own closures lead to the LIVE page holder and handles
        # dict, so nothing below is a stand-in for the shipped objects.
        poll = _closure_cells(
            _closure_cells(cells["_start_watch"])["_watch_solve"]
        )["_poll_solve"]
        poll_cells = _closure_cells(poll)
        assert state.structure_readout == "structure: A (50 \u03a9)", (
            f"the page did not boot on arm A: {state.structure_readout!r}"
        )
        boot_readout = state.structure_readout
        boot_scale = state.scale_label
        boot_velocity = state.velocity_label

        handles = poll_cells["handles"]
        view = handles.get("view")
        if view is not None and hasattr(view, "update"):
            view.update = lambda *args, **kwargs: None
        # The LIVE page holder, reached through the shipped watcher's own
        # closure: no stand-in dict is substituted anywhere.
        page = poll_cells["page"]
        assert Path(page["path"]) == Path(info["path"]), (
            f"the live page starts on {page['path']!r}, not the boot dump"
        )

        state.solve_structure = "B"  # the arm the child will actually write
        state.solve_xcut_mm = 20.4

        async def one_press() -> None:
            started = time.monotonic()
            trigger()  # exactly what the button calls; returns immediately
            assert state.solve_status.startswith("solving"), (
                f"the press did not start a solve: {state.solve_status!r}"
            )
            while time.monotonic() - started < 20.0:
                if state.solve_status.startswith("solved"):
                    return
                assert not state.solve_status.startswith("solve "), (
                    "the solve failed instead of landing a page: "
                    f"{state.solve_status!r}"
                )
                await asyncio.sleep(0.05)
            raise AssertionError(
                "nothing landed the finished solve: _watch_solve is not polling, "
                f"so the page still says {state.solve_status!r} and the result "
                "would need a manual reload"
            )

        asyncio.run(one_press())
    finally:
        pyvista.Plotter.render = real_render

    # ASSERTION 1 - the child really ran, and wrote where the UI asked it to.
    assert live_dump.is_file(), (
        f"the solve never produced {live_dump}: the child was not spawned, or "
        f"it wrote somewhere else ({fake_solver})"
    )
    # ASSERTION 2 - the LIVE page holder now carries the solved dump.
    assert page["structure_id"] == "B", (
        f"the page still holds {page['structure_id']!r} after a successful "
        "solve: the swap did not happen"
    )
    assert Path(page["path"]) == live_dump, (
        f"the page holds {page['path']!r}, not the solved dump {live_dump}"
    )
    # ASSERTION 3 - the readout names the arm now on screen, not the boot arm.
    assert state.structure_readout == "structure: B (100 \u03a9)", (
        f"the readout still says {state.structure_readout!r} (boot said "
        f"{boot_readout!r}): a solved page would keep describing the old arm"
    )
    # ASSERTION 4 - the two prose lines were rebuilt from the NEW dump.
    live_info = page["info"]
    assert state.scale_label == app._scale_label(live_info), (
        "the colour-limit line was not rebuilt from the solved dump: it says "
        f"{state.scale_label!r}, this dump's ceiling is "
        f"{app._scale_label(live_info)!r}"
    )
    assert state.velocity_label == app._velocity_label(live_info), (
        "the velocity line was not rebuilt from the solved dump: it says "
        f"{state.velocity_label!r}, this dump records "
        f"{app._velocity_label(live_info)!r}"
    )
    assert state.scale_label != boot_scale, (
        "the colour-limit line is still the boot dump's: a new field would be "
        "drawn against the old ceiling"
    )
    assert state.velocity_label != boot_velocity, (
        "the velocity line is still the boot dump's"
    )
    assert state.velocity_note == "probe after solve", (
        f"the velocity note still reads {state.velocity_note!r}"
    )



# --- the 2D cross-section mode panel -----------------------------------------
# No solve is run against a real dump here: the geometry comes off a study
# record this test writes beside the page's dump, so what is asserted is the
# panel's plumbing - a refusal instead of a raise, the grid it hands to the
# field view, the memo - not the physics, which emfit.mode2d's own tests own.

MODE_GEOMETRY = {
    "eps_r": 4.4,
    "h": 1.6e-3,
    "w": 3.2e-3,
    "height": 8.8e-3,
    "f_hz": 5.827786408327286e9,
}

MODE_BETA_MODEL = 223.35306683909533


def _mode_page(tmp_path: Path) -> dict:
    """A page whose SIBLING RECORD holds ``MODE_GEOMETRY``.

    The dump itself is not written: ``mode_view`` reads the geometry out of the
    record beside the dump, never out of the npz, so a record is the whole input.
    """
    page_path = tmp_path / "arm.npz"
    page_path.with_suffix(".json").write_text(
        json.dumps(
            {"geometry": dict(MODE_GEOMETRY), "line": {"beta_model": MODE_BETA_MODEL}}
        )
    )
    return {"path": str(page_path), "structure_id": "A"}


def test_mode_view_solves_a_synthetic_cross_section(tmp_path: Path) -> None:
    import poc_app as app

    result = app.mode_view(_mode_page(tmp_path), cache={})

    assert result["ok"], result["reason"]
    assert result["grid"].shape == (app.MODE_GRID_CELLS,) * 2, (
        f"the field view was handed {result['grid'].shape}: the panel draws a "
        f"square {app.MODE_GRID_CELLS} x {app.MODE_GRID_CELLS} picture"
    )
    assert np.all(np.isfinite(result["grid"]))
    assert result["beta_rad_per_m"] > 0.0
    assert result["beta_model"] == pytest.approx(MODE_BETA_MODEL)
    caption = result["caption"]
    assert "beta_model" in caption and "beta_banked" in caption, (
        "the caption quotes fewer than the three betas; the banked fit carries a "
        "systematic and must never be printed on its own"
    )


def test_cross_section_mesh_honours_the_node_cap() -> None:
    import poc_app as app

    mesh, _boundaries, _extent = app.cross_section_mesh(MODE_GEOMETRY, node_cap=400)

    assert 0 < mesh.n_nodes <= 400, (
        f"the mesh has {mesh.n_nodes} nodes for a cap of 400: the cap is "
        "silently ignored and the panel solves whatever it likes"
    )


def test_mode_view_refuses_without_a_record(tmp_path: Path) -> None:
    import poc_app as app

    page = {"path": str(tmp_path / "arm.npz"), "structure_id": "A"}
    result = app.mode_view(page, cache={})

    assert result["ok"] is False
    assert result["reason"], "a refusal with no reason leaves the panel blank"
    assert "record" in result["reason"]


def test_mode_view_memo_hits_on_the_second_call(tmp_path: Path) -> None:
    import poc_app as app

    page = _mode_page(tmp_path)
    cache = {}
    first = app.mode_view(page, cache=cache)
    second = app.mode_view(page, cache=cache)

    assert first["ok"], first["reason"]
    assert second is first, (
        "the second press re-solved instead of answering from the memo: "
        "identity is the proof, because a second solve returns the same numbers"
    )



# --- the Mode panel's SHIPPED half ------------------------------------------
#
# The compute half (``mode_view``) is frozen and proven above, by tests that call
# it directly.  What these two cover is the half this layer ships: the registered
# ``mode_view_toggle`` trigger, the module helpers that turn a result into the two
# state strings, and what the browser is therefore told.  ``mode_view`` itself is
# DOUBLED here (a dict in, no scipy) so a failure points at the wiring and never
# at the solver - and the boot is the real ``run_web_vis``, because a stand-in for
# the trigger would prove nothing about what the button calls.


def _press_mode(app, info, monkeypatch, fake_result):
    """Boot the page, then press the SHIPPED Mode button with a doubled solve.

    Returns the two state strings as they were at boot and the live ``state``
    after the press, so a test can assert both the resting text and the answer.
    """
    pyvista = pytest.importorskip("pyvista")

    real_render = pyvista.Plotter.render
    pyvista.Plotter.render = lambda self, *a, **k: None  # no OpenGL in this image
    try:
        # The trigger looks ``mode_view`` up in the module namespace at call time,
        # so patching the attribute is enough - the shipped body still runs.
        monkeypatch.setattr(app, "mode_view", lambda *a, **k: fake_result)
        app_module, srv = _boot_app(info)
        trigger = _registered_trigger(srv.controller, "mode_view_toggle")
        cells = _closure_cells(trigger)
        assert "state" in cells, (
            "the Mode trigger is not closed over the page's `state` (freevars: "
            f"{sorted(cells)}), so what it publishes cannot be asserted on"
        )
        state = cells["state"]
        boot = (state.mode_view_label, state.mode_view_caption)
        asyncio.run(trigger())  # the shipped handler, awaited as trame would
        return app_module, boot, state
    finally:
        pyvista.Plotter.render = real_render


def test_mode_panel_publishes_the_solve_caption(tmp_path: Path,
                                                monkeypatch) -> None:
    import poc_app as app

    info = _fixture_info(app, tmp_path / "dump.npz")
    solved = {
        "ok": True,
        "beta_rad_per_m": 223.180967,
        "eps_eff": 3.338787,
        "caption": "CAPTION from the solve: beta = 223.18 rad/m",
    }
    _app, (boot_label, boot_caption), state = _press_mode(
        app, info, monkeypatch, solved
    )

    assert boot_caption == app.MODE_PANEL_HINT, (
        "the panel does not rest on the hint the module defines: "
        f"{boot_caption!r}"
    )
    assert boot_label == "Mode (2D cross-section)", boot_label
    assert state.mode_view_caption == solved["caption"], (
        "the panel re-worded (or dropped) the solve's own caption: "
        f"{state.mode_view_caption!r}"
    )
    assert "223.18" in state.mode_view_label, (
        "the button does not report the beta it just solved for: "
        f"{state.mode_view_label!r}"
    )


def test_mode_panel_publishes_a_refusal_without_raising(tmp_path: Path,
                                                       monkeypatch) -> None:
    import poc_app as app

    info = _fixture_info(app, tmp_path / "dump.npz")
    refused = {"ok": False, "reason": "arm B has no geometry"}
    _app, (_boot_label, boot_caption), state = _press_mode(
        app, info, monkeypatch, refused
    )

    assert boot_caption == app.MODE_PANEL_HINT, boot_caption
    assert "arm B has no geometry" in state.mode_view_caption, (
        "a refused solve left the panel without its reason: "
        f"{state.mode_view_caption!r}"
    )
    assert state.mode_view_caption.startswith("mode refused:"), (
        state.mode_view_caption
    )
    assert state.mode_view_label == "Mode: refused", state.mode_view_label



def test_mode_picture_grid_lands_on_the_cross_section_plane() -> None:
    """The one picture rule checkable WITHOUT OpenGL: where the quad lands.

    This image has no EGL/OSMesa (a real ``render()`` segfaults the interpreter),
    so what is asserted here is the geometry the actor is built from - the grid
    handed to ``add_mesh``, in the plotter's millimetres - and not one pixel. What
    it pins down is the pair of mistakes that would not raise: a quad in the
    wrong plane (a second picture floating outside the box) and a transposed map
    (the cross-section mirrored into the wrong axis).
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    cells = app.MODE_GRID_CELLS
    result = {
        "ok": True,
        # |E| of the fundamental, indexed (z, y), as the compute layer returns it
        "grid": np.ones((cells, cells), dtype=float),
        "extent": (1.5e-3, 2.0e-3),  # y_max, z_max in METRES
    }
    grid = app._mode_picture_grid(result, x_mm=20.4)

    assert grid is not None, "a solved result produced no picture at all"
    x0, x1, y0, y1, z0, z1 = grid.bounds
    assert x0 == pytest.approx(20.4) and x1 == pytest.approx(20.4), (
        f"the quad stands at x = {x0} / {x1}, not on the cut-plane x = 20.4: it "
        "would float in front of, or behind, the x-cut sheets"
    )
    assert (y0, y1) == (pytest.approx(-1.5), pytest.approx(1.5)), (
        f"y spans {y0}..{y1} mm, not the recorded +-y_max = +-1.5 mm"
    )
    assert (z0, z1) == (pytest.approx(0.0), pytest.approx(2.0)), (
        f"z spans {z0}..{z1} mm, not the recorded 0..z_max = 0..2 mm"
    )
    assert grid.n_points == cells * cells, (
        f"the picture carries {grid.n_points} points, not the {cells} x {cells} "
        "square the solve sampled"
    )
    points = np.asarray(grid.points, dtype=float)
    assert points[1][1] > points[0][1] and points[1][2] == pytest.approx(
        points[0][2]
    ), (
        "the second point of the picture steps along z, not y: a transposed "
        "48 x 48 map draws the cross-section mirrored into the wrong axis and "
        "nothing raises"
    )

    # A refusal, and a grid that is not a picture, are picture-LESS answers and
    # never exceptions: the caption path has to survive them.
    assert (
        app._mode_picture_grid({"ok": False, "reason": "no record"}, x_mm=1.0)
        is None
    ), "a refusal produced a picture"
    assert (
        app._mode_picture_grid(
            {"ok": True, "grid": np.zeros((0, 0)), "extent": (1.0, 1.0)}, x_mm=1.0
        )
        is None
    )
    assert (
        app._mode_picture_grid({"ok": True, "grid": np.ones((4, 4))}, x_mm=1.0)
        is None
    ), "a result with no extent still produced a picture"


# --- the Confidence & Accuracy panel, derived from the record -----------------
#
# The panel is a PURE function of the study record (``build_confidence_block``),
# so every number below is computed from a record dict this file owns: no
# evidence/ file is required, no npz is read, no plotter and no trame layout is
# built.  What is pinned is the arithmetic a reader is shown - cells per
# wavelength at the RECORDED beta and at the model beta, and the referee
# deviation that must never quote the other artefact's 0.49 % - plus the refusal
# to render a missing value (the string "ABSENT", a null commit) as a number.


def test_confidence_panel_computes_cells_per_lambda() -> None:
    """67.5 and 70.3 cells per lambda, derived HERE from the recorded betas.

    A resolution claim is only worth its arithmetic.  The fit's beta and the
    model's beta disagree, so the panel has to print a ratio for EACH and say
    which is which; the ratios are recomputed below from the same betas and
    compared as numbers, so a string that drifted away from the formula fails.
    """
    import poc_app as app

    record = {
        "geometry": {
            "cell_m": 4e-4,
            "grid": [62, 212, 22],
            "cells": 289168,
            "f": 5827786408.327286,
            "f_target": 6e9,
        },
        "line": {
            "beta": 232.79891853803187,
            "beta_model": 223.35306683909533,
        },
        "meta": {"git_rev": None},
        "s11": {"magnitude": 0.32586326001662264},
    }

    block = app.build_confidence_block(record)
    assert block["status"] == "ok", (
        f"a record carrying every key this panel reads produced status "
        f"{block['status']!r}: {block['caption']!r}"
    )

    rows = [
        (str(label), str(text))
        for label, text in block["rows"]
        if "cells per wavelength" in str(label).lower()
    ]
    assert len(rows) == 2, (
        f"{len(rows)} resolution rows for the two betas the record carries: "
        f"{[label for label, _ in rows]}"
    )

    by_label = {label.lower(): text for label, text in rows}
    measured = [label for label in by_label if "measured" in label]
    model = [label for label in by_label if "model" in label]
    assert len(measured) == 1 and len(model) == 1, (
        f"the resolution rows are not labelled measured / model: "
        f"{sorted(by_label)} - a reader cannot tell which beta a ratio came from"
    )
    measured_text = by_label[measured[0]]
    model_text = by_label[model[0]]

    assert "67.5" in measured_text, (
        f"the measured-beta resolution is not 67.5 cells per wavelength: "
        f"{measured_text!r}"
    )
    assert "70.3" in model_text, (
        f"the model-beta resolution is not 70.3 cells per wavelength: "
        f"{model_text!r}"
    )

    # The bad illustrative "N-lambda = 20" phrasing: neither row may quote it.
    for text in (measured_text, model_text):
        assert "20.0" not in text, (
            f"a resolution row quotes 20.0 cells per wavelength, which is not "
            f"what this mesh resolves: {text!r}"
        )
    assert "20.0" not in measured_text

    # 2*pi/beta/cell_m, recomputed here rather than taken on trust, and compared
    # as a NUMBER: the first token of each row is the printed ratio.
    cell_m = record["geometry"]["cell_m"]
    for text, beta in (
        (measured_text, record["line"]["beta"]),
        (model_text, record["line"]["beta_model"]),
    ):
        expected = 2.0 * math.pi / beta / cell_m
        printed = float(text.split()[0])
        assert abs(printed - expected) < 0.1, (
            f"the panel prints {printed} cells per wavelength at beta = {beta}; "
            f"2*pi/beta/cell_m = {expected:.2f}, so the printed ratio is not the "
            f"formula it names: {text!r}"
        )
    # The two ranges, so a silently changed beta cannot slip through the
    # tolerance above: 2*pi/232.7989.../4e-4 = 67.5, 2*pi/223.3530.../4e-4 = 70.3.
    assert 67.46 < 2.0 * math.pi / record["line"]["beta"] / cell_m < 67.56, (
        "the measured beta in this record no longer resolves to 67.5 cells per "
        "wavelength, so the 67.5 asserted above proves nothing"
    )
    assert 70.26 < 2.0 * math.pi / record["line"]["beta_model"] / cell_m < 70.36, (
        "the model beta in this record no longer resolves to 70.3 cells per "
        "wavelength, so the 70.3 asserted above proves nothing"
    )


def test_confidence_panel_labels_the_referee_basis() -> None:
    """0.40 %, naming BOTH sides - and never the other artefact's 0.49 %.

    The referee is a second extraction of the same |S11| at the same frequency:
    0.32716455... against this record's 0.32586326..., i.e. 0.40 %.  The
    historical 0.49 % belongs to a DIFFERENT artefact (the phasors one), so its
    absence is asserted: seeing it here would mean the panel is comparing the
    record with a value carried forward from itself - a check that can only pass.
    """
    import poc_app as app

    record = {
        "geometry": {
            "cell_m": 4e-4,
            "grid": [62, 212, 22],
            "cells": 289168,
            "f": 5827786408.327286,
            "f_target": 6e9,
        },
        "line": {
            "beta": 232.79891853803187,
            "beta_model": 223.35306683909533,
        },
        "meta": {"git_rev": None},
        "s11": {"magnitude": 0.32586326001662264},
    }
    referee = {
        "s11_abs": 0.3271645531273824,
        "f_hz": 5827786408.327286,
    }

    blob = _flatten_block(app.build_confidence_block(record, referee))
    assert "0.40" in blob, (
        f"the referee deviation is not printed as 0.40 %: {blob!r}"
    )
    assert "s11_abs" in blob and "s11.magnitude" in blob, (
        "the panel does not name BOTH comparands (s11_abs, s11.magnitude), so a "
        f"reader cannot tell what was compared with what: {blob!r}"
    )
    assert "0.49" not in blob, (
        f"the panel quotes 0.49 %, which is the OTHER artefact's number: this "
        f"deviation must be 0.40 % or it is not the comparison it claims: {blob!r}"
    )

    # A referee that was never read degrades to a row that says so - and still
    # never to 0.49.
    absent = _flatten_block(app.build_confidence_block(record, None))
    assert "not available" in absent, (
        f"a missing referee did not produce a 'not available' row: {absent!r}"
    )
    assert "0.49" not in absent, (
        f"a missing referee still produced 0.49 %: {absent!r}"
    )

    # The real artefact, when this checkout carries it: same invariants, and a
    # checkout without evidence/ simply does not reach them (it cannot fail).
    record_path = REPO_ROOT / "evidence" / "termination" / (
        "build_A_50ohm_p51_ghostwave.json"
    )
    referee_path = REPO_ROOT / "evidence" / "referee" / "s11_extraction.json"
    if record_path.is_file() and referee_path.is_file():
        real_record = json.loads(record_path.read_text(encoding="utf-8"))
        real_referee = json.loads(referee_path.read_text(encoding="utf-8"))
        real_blob = _flatten_block(
            app.build_confidence_block(
                real_record, real_referee, record_path=str(record_path)
            )
        )
        assert "0.40" in real_blob, (
            f"the real record's referee deviation is not 0.40 %: {real_blob!r}"
        )
        assert "0.49" not in real_blob, (
            f"the real record quotes 0.49 %, the other artefact's number: "
            f"{real_blob!r}"
        )


def test_confidence_panel_survives_absent_and_string_fields() -> None:
    """The adversarial record: a STRING where a number belongs, and a null commit.

    ``line.sigma_beta_from_curvature`` is the TEXT "ABSENT" - not a float, not a
    missing key - and ``meta.git_rev`` is null.  Formatting either with a float
    spec raises, and that raise would cost the reader the whole panel on its
    first press, so the panel is asserted to render them as words.  A refusal
    with no record at all is asserted to be an ANSWER, not an exception.
    """
    import poc_app as app

    record = {
        "geometry": {
            "cell_m": 4e-4,
            "grid": [62, 212, 22],
            "cells": 289168,
            "f": 5827786408.327286,
            "f_target": 6e9,
        },
        "line": {
            "beta": 232.79891853803187,
            "beta_model": 223.35306683909533,
            "sigma_beta_from_curvature": "ABSENT",  # a STRING, not a number
            "station_fit_n": 8,
            "load_station_excluded": True,
            "z0_re": 42.75850315700394,
            "z0_im": -16.046149777568516,
        },
        "run": {
            "station_fit": {
                "z0_re": 47.30581504575999,
                "z0_im": 1.558214298741411,
            },
        },
        "s11": {
            "magnitude": 0.32586326001662264,
            "validation_status": "UNVALIDATED",
            "validation_reason": (
                "the magnitude above is the modulus of the two-wave B/A, not the "
                "one-wave station-fit reflection"
            ),
            "station_phasors": {"n": 9, "beta_used": 232.7989, "status": "ok"},
        },
        "ac": {
            "AC-1": {"pass": None},
            "AC-2": {"pass": True},
            "AC-3": {"pass": False},
            "AC-4": {"pass": None},
        },
        "meta": {"git_rev": None},
    }

    # The call itself must not raise: no pytest.raises, because a raise here is
    # the failure, not the expectation.
    block = app.build_confidence_block(record)
    blob = _flatten_block(block)

    assert "ABSENT" in blob, (
        f"the string sigma is not shown as text: {blob!r}"
    )
    assert "UNVALIDATED" in blob, (
        f"the record's |S11| validation status is not shown: {blob!r}"
    )

    def _row(needle: str) -> str:
        found = [
            str(text)
            for label, text in block["rows"]
            if needle in str(label).lower()
        ]
        assert len(found) == 1, (
            f"{len(found)} rows match {needle!r}: {[l for l, _ in block['rows']]}"
        )
        return found[0]

    # The two station counts, on the stations row specifically - 9 phasors in the
    # dump, 8 stations in the fit, because the load station is dropped.
    stations = _row("stations")
    assert "9" in stations and "8" in stations, (
        f"the stations row carries neither count: {stations!r}"
    )
    assert "phasors" in stations and "station_fit_n" in stations, (
        f"the stations row does not name both keys its counts came from: "
        f"{stations!r}"
    )

    # The failing criterion is NAMED, not just counted.
    criteria = _row("acceptance criteria")
    assert "AC-3" in criteria, (
        f"the acceptance tally does not name the one criterion that failed: "
        f"{criteria!r}"
    )
    assert "1 fail" in criteria and "1 pass" in criteria, (
        f"the acceptance tally miscounts this ac block: {criteria!r}"
    )

    # BOTH z0s, and which one the fit consumed: they differ, so quoting one
    # without its key is ambiguous.
    z0 = _row("z0")
    assert "47.3058" in z0 and "42.7585" in z0, (
        f"the Z0 row does not carry both impedances: {z0!r}"
    )
    assert "station_fit" in z0 and "NOT used by the fit" in z0, (
        f"the Z0 row does not say which impedance the fit consumed: {z0!r}"
    )

    # No record at all is a refusal, and a refusal is an answer.
    refusal = app.build_confidence_block(None, None)
    assert refusal["status"] == "no record", (
        f"a missing record produced status {refusal['status']!r}"
    )
    assert refusal["rows"] == [], (
        f"a refusal still carries rows: {refusal['rows']!r}"
    )
    assert str(refusal["caption"]).startswith("confidence refused"), (
        f"the refusal is not captioned as one: {refusal['caption']!r}"
    )


# --- keyboard shortcuts: Space plays, the arrows step ------------------------
# The BROWSER half is server/web_assets/keyboard.js.  Nothing below dispatches a
# real keydown event - the suite has no browser, and a fake Event would only
# prove the test wrote the same literals twice.  What IS proved here is the
# SERVER half of the contract, which is the half that can silently rot:
#   * the asset is actually registered with the client (otherwise the file can
#     never run, however correct it is), and
#   * the `kbd_shortcut` RPC reaches the very same handler each button is bound
#     to - proved by asserting the effects the buttons have, not by inspecting
#     the mapping in the handler.


async def _press(kbd, key: str) -> None:
    """One keyboard press as the page delivers it: an RPC that must return."""
    try:
        await asyncio.wait_for(kbd(key), timeout=RETURN_TIMEOUT_S)
    except asyncio.TimeoutError:
        pytest.fail(
            f"kbd_shortcut({key!r}) did not return within {RETURN_TIMEOUT_S}s: "
            "an unreturned trigger leaves the client RPC pending and every "
            "later control dead"
        )


async def _drain(tasks) -> None:
    """Stop the play loop(s) these presses started, so the fixture stays clean."""
    deadline = asyncio.get_running_loop().time() + LOOP_EXIT_TIMEOUT_S
    for task in tasks:
        while not task.done() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


def _kbd_binding(server):
    """The `kbd_shortcut` trigger plus the LIVE objects the handler it calls writes.

    Several tests in this module boot the page a second time, and trame's
    ``get_server()`` hands the SAME server back, so ``ctrl.set`` re-registers on
    top of itself over a FRESH ``handles`` dict.  The fixture's snapshot is
    therefore one boot stale by the time these tests run: walk the closure chain
    (kbd -> play handler -> its cells) instead, and assert on the dict the
    registered handler actually bumps.
    """
    kbd = server.controller.trigger_fn("kbd_shortcut")
    assert callable(kbd), (
        "controller.trigger_fn('kbd_shortcut') returned "
        f"{kbd!r}. The trame protocol looks a client trigger up in exactly this "
        "table and returns None (with only a log line) when it is absent, so the "
        "browser's window.trame.trigger('kbd_shortcut', ...) would be a silent "
        "no-op. The handler must be registered with @ctrl.trigger, not @ctrl.set."
    )
    cells = _closure_cells(kbd)
    play = cells.get("_on_play_toggle")
    assert callable(play), (
        "the kbd trigger is not closed over the play handler "
        f"(freevars: {sorted(cells)}) - the shortcut is not dispatching to the "
        "button's handler"
    )
    hcells = _closure_cells(play)
    handles, state = hcells["handles"], hcells["state"]
    assert state is server.state, (
        "the play handler is not closed over the live server state"
    )
    return kbd, handles, state


def test_keyboard_script_is_registered_with_the_client(playback):
    """``keyboard.js`` is on the list of scripts the page loads.

    The listener is not exercised (no browser here); this is the one thing that
    decides whether it can ever run at all.
    """
    scripts = [str(s) for s in list(playback.server.state.trame__scripts)]
    assert scripts, (
        "the client's script list is empty: enable_module never reached state"
    )
    assert any(s.endswith("keyboard.js") for s in scripts), (
        f"the client script list carries no keyboard.js: {scripts!r}"
    )

    # STATIC check of the one name the two halves must agree on. The listener is
    # not executed (no browser here), but the trigger name it sends and the
    # argument shape it sends are readable in the source, and a drift between
    # them and the server registration is exactly the bug that ships silently:
    # an unknown trigger name makes the protocol return None without an error.
    js = (REPO_ROOT / "server" / "web_assets" / "keyboard.js").read_text()
    kbd = playback.server.controller.trigger_fn("kbd_shortcut")
    assert kbd is not None, (
        "keyboard.js sends 'kbd_shortcut' but the server registered no such "
        "trigger (trigger_fn returned None) - every shortcut would be dropped"
    )
    assert "'kbd_shortcut'" in js or '"kbd_shortcut"' in js, (
        f"keyboard.js does not name the 'kbd_shortcut' trigger: {js[:200]!r}"
    )
    assert "[event.key]" in js, (
        "keyboard.js no longer passes the pressed key as the trigger's first "
        "positional argument, which is the shape _on_kbd_shortcut reads"
    )


def test_keyboard_space_is_the_play_button(playback):
    """Space does exactly what the play button does - same handler, same effects.

    A real keydown is not dispatched; this drives the RPC the listener emits.
    """
    async def scenario() -> None:
        kbd, handles, state = _kbd_binding(playback.server)

        if state.playing:  # module-scoped fixture: leave no press behind
            await _press(kbd, " ")
        assert state.playing is False, "could not get back to a stopped page"

        baseline = int(handles.get("generation", 0))
        tasks_before = _other_tasks()

        await _press(kbd, " ")

        # The same three effects the button's handler has, asserted on the live
        # objects: the flag the template binds, the generation counter, and one
        # background loop - not two.
        created = _other_tasks() - tasks_before
        try:
            assert state.playing is True, (
                "Space did not start playback; the shortcut did not reach the "
                "play handler"
            )
            assert int(handles.get("generation", -1)) == baseline + 1, (
                f"Space went generation {handles.get('generation')}, expected "
                f"{baseline + 1}: the shortcut did not go through the play "
                "handler's generation bump"
            )
            assert len(created) == 1, (
                f"expected exactly 1 background loop from a Space press, found "
                f"{len(created)}"
            )
        finally:
            await _press(kbd, " ")
            assert state.playing is False, (
                "the second Space press did not stop playback"
            )
            assert int(handles.get("generation", -1)) == baseline + 2, (
                "the second Space press did not bump the generation counter"
            )
            await _drain(created)

    asyncio.run(scenario())


def test_keyboard_arrows_are_the_step_buttons(playback):
    """ArrowRight/ArrowLeft move the frame exactly as next/prev do.

    A real keydown is not dispatched; this drives the RPC the listener emits.
    The wrap-around is the step handlers' own ``% frames``, asserted here at the
    frame level rather than by reading the handler's source.
    """
    async def scenario() -> None:
        kbd, _handles, state = _kbd_binding(playback.server)

        assert state.mode == "ycut", (
            f"the page booted in mode {state.mode!r}, not 'ycut'"
        )
        frames = int(state.frame_max) + 1
        assert frames > 1, f"the fixture only has {frames} frame(s)"
        start = int(state.frame)

        await _press(kbd, "ArrowRight")
        assert int(state.frame) == (start + 1) % frames, (
            f"ArrowRight moved frame {start} -> {state.frame}, expected "
            f"{(start + 1) % frames}"
        )

        await _press(kbd, "ArrowLeft")
        assert int(state.frame) == start, (
            f"ArrowLeft did not walk the frame back to {start}: it is at "
            f"{state.frame}"
        )

        # The step handlers are the buttons' handlers, so they also stop playback
        # - a frame step while the animation is running is a race.
        assert state.playing is False, (
            "a keyboard frame step left playback running"
        )

    asyncio.run(scenario())


def test_two_identical_space_presses_both_take_effect(playback):
    """Start then stop from two presses of the SAME key.

    The reason the listener uses ``trigger`` and not ``state.set``: a state
    write is compared with the cached value client-side and dropped when equal,
    so the second "pressed" would never be sent and the page would play forever.
    Here the two presses are indistinguishable to the server, and both still
    land.
    """
    async def scenario() -> None:
        kbd, handles, state = _kbd_binding(playback.server)

        if state.playing:
            await _press(kbd, " ")
        assert state.playing is False, "could not get back to a stopped page"

        baseline = int(handles.get("generation", 0))
        tasks_before = _other_tasks()

        await _press(kbd, " ")
        await _press(kbd, " ")

        created = _other_tasks() - tasks_before
        try:
            assert state.playing is False, (
                "the second identical Space press did not stop playback: this is "
                "the state.set equality-guard bug the listener avoids by calling "
                "trigger()"
            )
            assert int(handles.get("generation", -1)) == baseline + 2, (
                f"two Space presses went generation {handles.get('generation')}, "
                f"expected {baseline + 2} - one of them was swallowed"
            )
        finally:
            await _drain(created)

    asyncio.run(scenario())


def test_js_trigger_call_shape_pins_the_wire_contract(playback):
    """The JS -> trigger call shape: `trigger('kbd_shortcut', [key], {})` works.

    This is the check that would have caught the shipped bug. The listener calls
    ``window.trame.trigger(name, args, kwargs)``; the protocol resolves ``name``
    with ``controller.trigger_fn`` (None for a name registered with
    ``@ctrl.set`` - and None is a silent no-op, not an error) and then calls
    ``fn(*args)``. So both halves are pinned here: the NAME resolves, and one
    positional argument (the key) is the signature the handler accepts. A
    handler with only ``**_kwargs`` would raise TypeError at this call.
    """
    async def scenario() -> None:
        # exactly what the protocol does: look the name up in the trigger table
        fn = playback.server.controller.trigger_fn("kbd_shortcut")
        assert callable(fn), (
            "trigger_fn('kbd_shortcut') is not callable "
            f"({fn!r}): the browser's trigger('kbd_shortcut', ...) would be "
            "dropped with a log line and no error"
        )
        cells = _closure_cells(fn)
        play = cells["_on_play_toggle"]
        handles, state = _closure_cells(play)["handles"], _closure_cells(play)["state"]
        kbd = fn

        if state.playing:
            await _press(kbd, " ")
        assert state.playing is False, "could not get back to a stopped page"
        baseline = int(handles.get("generation", 0))
        tasks_before = _other_tasks()

        # the JS's exact call: args = [event.key], no kwargs -> fn(*[' '])
        await _press(kbd, " ")

        created = _other_tasks() - tasks_before
        try:
            assert state.playing is True, (
                "the JS call shape did not reach the play handler"
            )
            assert int(handles.get("generation", -1)) == baseline + 1, (
                "the JS call shape reached no generation bump: "
                f"{handles.get('generation')} vs {baseline + 1}"
            )
        finally:
            await _press(kbd, " ")
            await _drain(created)

    asyncio.run(scenario())


def test_unknown_key_is_a_silent_no_op(playback):
    """A key that is nobody's shortcut changes nothing and does not raise.

    An RPC that raises surfaces as a broken page on a keyboard layout the
    developer never tried, so an unhandled key must be a no-op.
    """
    async def scenario() -> None:
        kbd, handles, state = _kbd_binding(playback.server)

        before = (
            int(state.frame),
            state.playing,
            int(handles.get("generation", 0)),
            state.play_label,
        )

        await _press(kbd, "KeyQ")  # not a shortcut, and no such physical key here

        after = (
            int(state.frame),
            state.playing,
            int(handles.get("generation", 0)),
            state.play_label,
        )
        assert after == before, (
            f"an unknown key changed the page: {before!r} -> {after!r}"
        )

    asyncio.run(scenario())


def _looks_like_vue_expression(expr: str) -> bool:
    """Whether `expr` can be a Vue template expression, decided without node.

    This is the fallback for images that carry no JS parser.  It is weaker than
    compiling the expression, but it fails on the bug class that motivated the
    check: trame renders a Python list passed as ``items=`` by emitting its
    FIRST ELEMENT as a bare expression, so a one-element list ships
    ``:items="fixed (0.5 mm)"`` - a repr, not JavaScript.  Anything this cannot
    recognise is accepted rather than guessed at.
    """
    import json
    import re

    text = expr.strip()
    if not text:
        return False

    # A bare path: frame_max, s_params_image_style, trame.refs['x'], !!busy
    if re.match(
        r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\[[^\[\]]*\])*$",
        text.lstrip("!+-~ "),
    ):
        return True

    # A literal, once the single quotes trame emits are turned back into JSON.
    if text[0] in "[{'\"":
        try:
            json.loads(text.replace("'", '"'))
            return True
        except ValueError:
            pass

    # A parenthesis outside a string is the shape a Python repr leaks in with -
    # `fixed (0.5 mm)`.  Vue parses neither that nor an unbalanced one, and the
    # only expressions that legitimately hold a parenthesis are a call, an arrow
    # function and a template literal.
    quote = None
    for ch in text:
        if quote is not None:
            if ch == quote:
                quote = None
        elif ch in "\"'`":
            quote = ch
        elif ch in "()":
            return bool(re.search(r"=>|\bfunction\b", text)) or "`" in text

    return True


@pytest.mark.parametrize("builder", ["run_web_vis", "run_web"])
def test_every_bound_attribute_is_a_valid_vue_expression(builder, tmp_path):
    """No emitted `:attr="..."` may carry a value that is not JavaScript.

    BOTH builders are swept, because the page has two of them: ``run_web_vis``
    serves an ``emfit.vis/2`` dump, ``run_web`` serves a legacy single-plane
    dump - and that legacy builder is the one ``python3 server/poc_app.py``
    reaches on port 8080, because the default structure's dump carries
    ``plane_ez`` and no ``format`` key.

    trame renders attributes to text in
    trame_client/widgets/vue.py::HtmlElement._process_attrs:

        self._elem._attributes[name] = f'{js_key}="{translated_value}"'

    so a Python list passed as ``items=`` is read as a (state_name, default)
    pair and the FIRST ELEMENT is emitted as a bare JS expression - a
    one-element list therefore ships ``:items="fixed (0.5 mm)"``, which Vue's
    template compiler cannot parse, and the runtime compiler compiles the whole
    page template at once.  Two invariants are cheap to check here and both
    were violated: the value must not contain the attribute delimiter, and the
    expression must parse as JavaScript.
    """
    import json
    import shutil
    import subprocess

    import trame_client.widgets.core as core

    import poc_app as app

    registry = []
    orig_init = core.AbstractElement.__init__

    def recording_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        registry.append(self)

    core.AbstractElement.__init__ = recording_init
    try:
        if builder == "run_web_vis":
            info = _fixture_info(app, tmp_path / "dump.npz")
            _boot_app(info)
        else:
            info = _fixture_legacy_info(app, tmp_path / "legacy.npz")
            _boot_web(info)
    finally:
        core.AbstractElement.__init__ = orig_init

    bound = []
    for elem in registry:
        try:
            elem.html  # forces render() -> _process_attrs()
            attrs = elem._attributes
        except Exception:  # noqa: BLE001 - a widget that cannot render is not this test's subject
            continue
        for name, stored in attrs.items():
            text = str(stored)
            if text.startswith(":") or text.startswith("v-"):
                bound.append((elem._elem_name, name, text))

    assert len(bound) > 5, (
        f"only {len(bound)} bound attributes were captured from {builder}'s "
        "page; the layout did not render, so this test would prove nothing"
    )

    # 1. The whole value must fit inside the one pair of double quotes trame
    #    wraps it in.  `["A", "B"]` looks right in Python and truncates in HTML.
    for comp, name, text in bound:
        assert text.count('"') == 2, (
            f"{comp}.{name} emits {text!r}: the value contains a double quote, "
            "which ends the attribute early and truncates the expression the "
            "browser compiles"
        )

    # 2. The expression must be JavaScript.  node is the only JS parser in this
    #    image (no esprima/pyjsparser/quickjs), so use it when it is there.
    node = shutil.which("node")
    if node is None:
        # No JS parser in this image, so fall back to the Python-side screen.
        # It is weaker than node but it fails on exactly this bug class: a
        # Python repr (`fixed (0.5 mm)`) is not a Vue expression.
        for comp, name, text in bound:
            expr = text[text.index('="') + 2 :].rstrip('"')
            assert _looks_like_vue_expression(expr), (
                f"{comp}.{name} emits {text!r}, whose value is not a Vue "
                "expression (node is not installed, so this was decided "
                "without a JS parser)"
            )
        return

    payload = [
        [comp, name, text[text.index('="') + 2 : -1]] for comp, name, text in bound
    ]
    js = (
        'const rows=JSON.parse(require("fs").readFileSync(0,"utf8"));'
        "const bad=rows.map(([c,n,x])=>{try{new Function('return ('+x+')');"
        "return null}catch(e){return c+'.'+n+' emits :'+n+'=\"'+x+'\" -> '+e.message}});"
        "console.log(JSON.stringify(bad.filter(Boolean)))"
    )
    proc = subprocess.run(
        [node, "-e", js],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    invalid = json.loads(proc.stdout)
    assert invalid == [], (
        "these bound attributes carry an expression Vue's template compiler "
        "cannot parse (the page compiles as one template, so one of these is "
        "enough to leave the app blank):\n  " + "\n  ".join(invalid)
    )



# --- the load's own trace, drawn under the Circuit netlist box ---------------
#
# The panel is emitted STRAIGHT INTO the layout (there is no handle and no
# click for it), so what has to be observed is the widget constructors it
# calls. ``run_web_vis`` resolves Div/Pre/Img off the ``trame.widgets.html``
# module AT CALL TIME, which is what makes patching those three attributes
# before the boot sufficient - and it is why an assertion about the pixels
# would be the wrong assertion: the figure is a data URI and the rows beside
# it are the only part of the picture a headless check can read back.


def _add_load_trace(path: Path, *, netlist_name="cut_A_test", n=5) -> Path:
    """Rewrite the fixture dump with the solver's own load-trace keys.

    ``_fixture_info`` writes the vis field set only, so the trace is added to
    the file and the dump is re-loaded through ``load_vis``: the panel reads
    ``info["load_series"]``, and what must be proved is that the LOADER hands
    it a real series, not that a stand-in dict renders.
    """
    with np.load(path) as data:
        payload = {key: data[key] for key in data.files}
    payload["load_t_ns"] = np.linspace(0.0, 0.5, n)
    payload["load_v"] = np.linspace(-2.0, 0.85, n)
    payload["load_i"] = np.linspace(-2e-3, 1e-3, n)
    payload["load_trace_present"] = np.array(1)
    payload["load_netlist_json"] = np.array(
        json.dumps({"name": netlist_name, "elements": []})
    )
    np.savez(path, **payload)
    return path


def _capture_html_widgets(monkeypatch):
    """Record every Div/Pre/Img the boot builds, in construction order."""
    import trame.widgets.html as html_mod

    log = []
    for name in ("Div", "Pre", "Img"):
        real = getattr(html_mod, name)

        def _factory(*args, _real=real, _name=name, **kwargs):
            log.append(
                {
                    "kind": _name,
                    "text": args[0] if args else None,
                    "src": kwargs.get("src"),
                }
            )
            return _real(*args, **kwargs)

        monkeypatch.setattr(html_mod, name, _factory)
    return log


def _texts(log) -> list:
    return [str(entry["text"]) for entry in log if isinstance(entry["text"], str)]


def test_load_series_panel_draws_the_recorded_trace(tmp_path: Path,
                                                    monkeypatch) -> None:
    """A traced dump puts a picture, a caption and rows on the Circuit tab."""
    import poc_app as app

    # _fixture_info RETURNS the info dict, not the path it wrote, so the file
    # is named here: _add_load_trace rewrites it and load_vis re-reads it.
    dump = tmp_path / "traced.npz"
    _fixture_info(app, dump)
    _add_load_trace(dump)
    info = app.load_vis(dump)
    series = info["load_series"]
    assert isinstance(series, dict), (
        "load_vis did not hand the page a trace for a dump that carries one: "
        f"{series!r} (reason {info['load_series_reason']!r})"
    )

    log = _capture_html_widgets(monkeypatch)
    _boot_app(info)

    texts = _texts(log)
    assert app._LOAD_SERIES_TITLE in texts, (
        "the Circuit tab carries no load-trace panel at all (the title "
        f"{app._LOAD_SERIES_TITLE!r} was never emitted), so a recorded trace "
        "would be invisible on the page"
    )
    caption = [text for text in texts if text.startswith(app._LOAD_SERIES_TITLE + " - ")]
    assert caption, f"the panel drew no caption; texts were:\n" + "\n".join(texts)
    caption = caption[0]
    for fragment in (f"{series['n']} samples", dump.name, "cut_A_test"):
        assert fragment in caption, (
            f"the caption does not name {fragment!r}, so a reader cannot tell "
            f"which trace is on screen: {caption!r}"
        )
    images = [
        str(entry["src"])
        for entry in log
        if entry["kind"] == "Img" and str(entry["src"]).startswith("data:image/png;base64,")
    ]
    assert len(images) == 1, (
        "the traced dump produced "
        f"{len(images)} data-URI images; without one the panel shows no picture "
        "and without exactly one it is drawing somebody else's"
    )
    rows = "\n".join(text for text in texts if "t span [ns]:" in text)
    assert "samples: " + str(series["n"]) in rows, (
        f"the rows do not report this trace's sample count: {rows!r}"
    )
    t_ns = series["load_t_ns"]
    span = f"t span [ns]: {min(t_ns):.6g} .. {max(t_ns):.6g}"
    assert span in rows, (
        f"the rows do not report this trace's own time span ({span!r}): {rows!r}"
    )
    assert "element: netlist circuit 'cut_A_test'" in rows, (
        f"the rows do not name the circuit that terminated the cut: {rows!r}"
    )


def test_load_series_panel_states_the_reason_instead_of_drawing(
    tmp_path: Path, monkeypatch
) -> None:
    """A trace-less dump gets the reason, and no picture and no rows."""
    import poc_app as app

    info = _fixture_info(app, tmp_path / "no_trace.npz")
    reason = info["load_series_reason"]
    assert info["load_series"] is None and isinstance(reason, str), (
        f"the fixture dump is supposed to carry no trace; got {info['load_series']!r} "
        f"and reason {reason!r}"
    )

    log = _capture_html_widgets(monkeypatch)
    _boot_app(info)

    texts = _texts(log)
    assert app._LOAD_SERIES_TITLE in texts, (
        "the panel disappeared entirely for a trace-less dump; the reason it "
        "cannot be drawn has nowhere to be said then"
    )
    assert f"no load trace to show: {reason}" in texts, (
        "the panel did not repeat the dump's own reason, so the page would "
        f"claim something the file does not say: {texts}"
    )
    assert "no picture drawn: no load trace was taken for this run" in texts, (
        f"the panel did not say why there is no figure: {texts}"
    )
    assert not [
        str(entry["src"])
        for entry in log
        if entry["kind"] == "Img"
        and str(entry["src"]).startswith("data:image/png;base64,")
    ], "the panel drew a picture of a trace the dump does not carry"
    assert not [text for text in texts if "t span [ns]:" in text], (
        f"rows from a trace that does not exist were printed: {texts}"
    )
