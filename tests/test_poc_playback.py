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

@pytest.fixture(scope="module", autouse=True)
def _the_volume_layer_is_on():
    """Opt this module in to the |E| volume layer its draws are about.

    ``SHOW_VOLUME_LAYER_DEFAULT`` (server/poc_app.py:892) keeps the 3-D |E|
    volume off the page by default: no volume, no cut sheets and no |E| half of
    the step counter.  The boot, the cut row and the cut redraw asserted below
    are all assertions ABOUT that layer, so the module turns it on through the
    switch's own opt-in clause - the ``scope="module"`` ``field_page`` boot
    included.  Not one assertion moves.
    """
    import poc_app as app

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(app, "SHOW_VOLUME_LAYER_DEFAULT", True)
        yield

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
                  schema=None, frames=None) -> dict:
    """Minimal ``emfit.vis/2`` dump, the same field set verify_wd.py uses.

    ``structure_id`` / ``load_ohm`` are the dump's PROVENANCE keys; pass ``None``
    for either to write a version-1-shaped file that does not carry it.  The
    default pair is Run A's own arm and load, which is what every other test
    here reads back.  ``schema`` overrides the declared version.
    """
    nt, nx, nz = (4 if frames is None else int(frames)), 8, 5
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


#: The keys ``load_vis`` REFUSES a dump for lacking (poc_app.py:461-478): the
#: axes and the three stored field arrays the picture cannot be drawn without.
VIS_MANDATORY_KEYS = (
    "ez_ycut", "ez_xcut_near", "ez_xcut_far", "t_ns", "frame_index",
    "frame_index_xcut", "x_mm", "y_mm", "z_mm", "nx", "ny", "nz", "nt",
    "nt_x", "dt_s", "cell_m",
)

#: Every key ``_fixture_info`` writes that ``load_vis`` does NOT require.  The
#: loader materialises all of them itself - ``_npz_scalar`` answers NaN and
#: ``_npz_text`` answers None (poc_app.py:297, :312) - so a dump carrying none
#: of them still hands the page a dict with the SAME key set as a full one.
VIS_OPTIONAL_KEYS = (
    "j_cut", "dump_stride", "nsteps", "f_ref_hz", "f_pulse_hz",
    "xcut_near_mm", "xcut_far_mm", "port_x_mm", "load_x_mm",
    "substrate_h_mm", "strip_w_mm", "eps_r", "v_analytic_m_s",
    "v_measured_m_s", "t_traverse_ns", "v_measured_reliable",
    "velocity_note", "structure_id", "load_ohm",
)


def _bare_payload(app, *, drop=None) -> dict:
    """The dump ``_fixture_info`` writes MINUS every optional key.

    Only the schema and :data:`VIS_MANDATORY_KEYS` survive, so this is the
    smallest file ``load_vis`` accepts.  ``drop`` removes one of even those, to
    make the mirror image: a file that is one structural fact short.
    """
    nt, nx, nz = 4, 8, 5
    nt_x, ny_x = 3, 6
    rng = np.random.default_rng(0)
    payload = {
        "schema": app.VIS_SCHEMA,
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
    }
    leaked = sorted(set(payload) & set(VIS_OPTIONAL_KEYS))
    assert not leaked, (
        f"the bare dump carries the optional key(s) {leaked}; an optional key "
        "leaking in here hands the page a datum this test exists to deny it, "
        "which weakens the bare-dump test silently instead of failing it"
    )
    assert set(payload) - {"schema"} == set(VIS_MANDATORY_KEYS)
    if drop is not None:
        payload.pop(drop)
    return payload


def _fixture_bare_info(app, path: Path) -> dict:
    """A vis dump with EVERY optional key absent, loaded the way boot loads it."""
    np.savez(path, **_bare_payload(app))
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


def _fixture_one_plane_info(app, path: Path) -> dict:
    """Legacy dump that captured exactly ONE x-plane: port planes, not a stack.

    The recorded shape with its station axis collapsed to one, which is the page
    this fallback is about: ``Available`` answers ``plane_stack`` False and
    ``port_planes`` True for it (server/um3k_context.py).  The two transverse
    axes are deliberately different lengths, so "the middle sample of each" is a
    different number on each (12 -> 6, 5 -> 2) and a transposed copy of the plane
    cannot satisfy the assertions by accident.
    """
    rng = np.random.default_rng(0)
    np.savez(
        path,
        plane_ez=rng.normal(size=(1, 12, 5)),
        nstep=np.array(6),
        nx=np.array(1),
        ny=np.array(12),
        nz=np.array(5),
        cell_m=np.array(1e-4),
    )
    return app.load_dump(path)


def _boot_app(info, loaded_page=None):
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
            app.run_web_vis(
                info, "127.0.0.1", 8999, fps=FPS, loaded_page=loaded_page
            )
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


#: The y-cut timeline the clock tests run on.  The small dump the rest of this
#: file uses has FOUR positions and the loop advances DEFAULT_PLAY_RATE (4)
#: positions a tick, so 4 % 4 == 0: the clock would sit on one position for the
#: whole sweep and "the loop carried on from the operator's position" could not
#: be told from "the loop dragged the picture back".  96 keeps the boot cheap
#: while a tick still moves the clock: 4 steps at 25 fps is 100 positions/s, so
#: the CLOCK_WINDOW_S window below is 15 positions - far short of the half sweep
#: the seek is put away from the clock.
CLOCK_FRAMES = 96


def _playback_page(tmp_path_factory, frames=None):
    """Boot the animation page and yield it with its two devices doubled.

    ``frames`` picks the y-cut timeline length (see :data:`CLOCK_FRAMES`); the
    default is the small dump every non-clock test here reads.
    """
    pyvista = pytest.importorskip("pyvista")
    import poc_app as app

    undos = []
    renders = []
    view_updates = []

    # --- device double #1: the OpenGL draw -------------------------------
    real_render = pyvista.Plotter.render

    def _no_render(self, *args, **kwargs):
        renders.append(1)  # counted, never performed

    pyvista.Plotter.render = _no_render
    undos.append(lambda: setattr(pyvista.Plotter, "render", real_render))

    try:
        info = _fixture_info(
            app, tmp_path_factory.mktemp("wd") / "dump.npz", frames=frames
        )
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
                # With a view on the page this push IS the draw (the plotter
                # renders nothing of its own); counted so a test can see it.
                view_updates.append(1)  # counted, never performed
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
            view_updates=view_updates,
            undos=undos,
        )
    finally:
        for undo in reversed(undos):
            undo()


@pytest.fixture(scope="module")
def playback(tmp_path_factory):
    """The playback page on the small dump the rest of this file uses."""
    yield from _playback_page(tmp_path_factory)


@pytest.fixture(scope="module")
def clock_playback(tmp_path_factory):
    """The same page on a timeline long enough for its clock to MOVE.

    See :data:`CLOCK_FRAMES`: on the four-position dump a tick advances the clock
    by exactly the timeline length, so nothing on ``state.frame`` can be watched
    while playback runs.
    """
    yield from _playback_page(tmp_path_factory, frames=CLOCK_FRAMES)


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



def test_a_failed_draw_ends_playback_instead_of_hanging(playback, monkeypatch):
    """A draw that raises leaves the viewer PAUSED, not silently dead.

    The play loop runs as a task nobody awaits, so before the guard an exception
    in a tick surfaced only as "Task exception was never retrieved" at GC time:
    ``state.playing`` stayed True, the button still read "pause" and nothing ever
    advanced - indistinguishable from the freeze this fix is about, with no trace
    to explain it. ``_volume_player_plan`` is the module-level draw step ``_show``
    resolves at call time, so patching it reaches the shipped ``_show``.
    """
    def _boom(*_args, **_kwargs):
        raise RuntimeError("draw failed")

    monkeypatch.setattr(playback.app, "_volume_player_plan", _boom)

    async def scenario() -> None:
        handles, state, trigger = playback.handles, playback.state, playback.trigger
        assert state.playing is False, "boot already left the page playing"

        tasks_before = _other_tasks()
        await asyncio.wait_for(trigger(), timeout=RETURN_TIMEOUT_S)
        created = _other_tasks() - tasks_before
        assert len(created) == 1, (
            f"the play press scheduled {len(created)} tasks, expected exactly 1"
        )
        task = created.pop()
        try:
            deadline = asyncio.get_running_loop().time() + LOOP_EXIT_TIMEOUT_S
            while not task.done() and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.01)
            assert task.done(), (
                "the play loop was still running "
                f"{LOOP_EXIT_TIMEOUT_S}s after the draw raised: a failed tick must "
                "stop playback, not spin on the same failure"
            )
            exc = None if task.cancelled() else task.exception()
            assert exc is None, f"the play loop leaked an unhandled {exc!r}"
            assert state.playing is False, (
                "the draw raised but state.playing is still True: the button reads "
                "'pause' over a picture that will never advance again"
            )
            assert state.play_label == "play", (
                f"the label says {state.play_label!r} after a failed draw, so the "
                "operator cannot tell playback stopped"
            )
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    asyncio.run(scenario())

# --- the operator's controls while the animation RUNS -------------------------
#
# The report these pin: "while playback runs, the pause button / frame scrubber /
# step buttons do nothing until it stops". The loop held ONE
# ``suppress_frame_listener`` flag across the whole tick - the draw, its flush AND
# the yield after it - so a change that arrived while the loop was suspended was
# swallowed by a listener that took it for the loop's own draw, and ``drawn`` was
# then read back off ``state.frame`` (now the operator's position) so the clock no
# longer noticed the seek either. The loop now names the ONE position it publishes
# (``play_echo_frame``) and pins ``drawn`` from that BEFORE the yield.

#: How long the clock tests watch ``state.frame`` after the operator's change.
#: 4 steps/tick at 25 fps = 100 positions/s, so a sample can be at most
#: ``CLOCK_STEP * CLOCK_WINDOW_S`` = 15 positions past the change - and the loop
#: needs half a sweep (48) to catch up with a position put that far ahead of it.
CLOCK_WINDOW_S = 0.15
CLOCK_STEP = 4 * 25


def _frame_listener(state, handles):
    """The callable trame hands a client's ``frame`` change to.

    ``@state.change("frame")`` registers it on the STATE object, not on the
    controller, so it is not reachable through a ``ctrl`` trigger - this is the
    registration the browser's change is dispatched through.

    ``handles`` picks THIS page's registration out of the list.  trame's
    ``change()`` APPENDS to ``state._change_callbacks['frame']`` and exposes no
    unregister, while ``get_server()`` hands every boot in this process the SAME
    server, so the tests here that boot the page a second time leave their own
    ``_on_frame`` registered as well (see :func:`_kbd_binding`, which walks the
    closure chain for the same reason).  Every boot closes over a FRESH
    ``handles`` dict, so the listener whose closure cell IS this page's dict is
    the one the fixture's draw doubles count.
    """
    entries = [
        entry
        for entry in (state._change_callbacks.get("frame") or [])
        if _closure_cells(entry[0]).get("handles") is handles
    ]
    assert len(entries) == 1, (
        f"{len(entries)} listeners registered on 'frame' for this page; "
        "expected exactly 1"
    )
    fn = entries[0][0]
    assert fn.__qualname__.endswith("._on_frame"), (
        f"the 'frame' listener is {fn.__qualname__!r}, not the page's _on_frame"
    )
    return fn


async def _watch_clock(state, origin, frames, seconds=CLOCK_WINDOW_S):
    """Sample ``state.frame``; return each sample's distance AHEAD of ``origin``.

    ``origin`` is the operator's position, so a distance of 0 is the position
    still on screen and a small distance is the loop having carried on from it.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + seconds
    seen = []
    while loop.time() < deadline:
        seen.append((int(state.frame) - origin) % frames)
        await asyncio.sleep(0.002)
    return seen


def test_the_loop_draws_its_own_echo_once_but_an_operator_seek_always(playback):
    """The loop's own position is not drawn a second time; a seek is drawn.

    ``_show`` writes ``state.frame``, and the position it publishes is the value
    the frame listener is handed back: without the echo every tick would draw
    twice - twice the GL work for one position, the second draw from inside a
    state listener. ``playing`` is set by hand here because what is under test is
    the LISTENER, not the clock: no loop runs, so every render counted is the
    listener's own. The listener is called DIRECTLY, the way trame calls it on a
    client change (``listener(frame=<the new value>)``): this harness never
    enters the event loop, so ``state.flush()`` dispatches nothing and a
    flush-based assertion would pass for the wrong reason.

    A draw is counted as the plotter's own render OR the view push: with a view
    on the page ``_tick_render_and_push`` pushes instead of rendering (04d9658,
    and test_poc_profile.py pins that a tick with a view renders nothing), so
    the push is the draw here.
    """
    handles, state = playback.handles, playback.state
    renders, view_updates = playback.renders, playback.view_updates

    def drawn():
        """How many times the picture has been pushed to the screen."""
        return len(renders) + len(view_updates)

    listener = _frame_listener(state, handles)
    assert state.playing is False, "boot already left the page playing"
    frames = int(state.frame_max) + 1
    was_frame, was_playing = int(state.frame), bool(state.playing)
    try:
        state.playing = True
        # -- the loop's echo: the position it is about to publish, already drawn.
        echoed = (was_frame + 7) % frames
        handles["play_echo_frame"] = echoed
        before = drawn()
        state.frame = echoed
        listener(frame=echoed)
        assert drawn() == before, (
            "the frame listener drew the play loop's own echo: "
            f"{drawn() - before} extra render(s) for position {echoed}, "
            "so every tick costs two draws instead of one"
        )
        # -- an operator's seek: the echo names a DIFFERENT position, so this one
        #    is not the loop's and has to reach the picture immediately.
        handles["play_echo_frame"] = (echoed + 1) % frames
        seek = (echoed + frames // 2) % frames
        before = drawn()
        state.frame = seek
        listener(frame=seek)
        assert drawn() - before == 1, (
            "a frame change while playing was swallowed by the play loop's own "
            "suppression: the scrubber and the step buttons then look dead until "
            "playback stops"
        )
        assert int(state.frame) == seek, (
            f"the seek to {seek} was rewritten to {int(state.frame)!r} by the "
            "listener that was supposed to draw it"
        )
    finally:
        handles["play_echo_frame"] = None
        state.playing = was_playing
        state.frame = was_frame
        state.flush()


def test_a_scrub_while_playing_is_carried_on_from_not_undone(clock_playback):
    """A position sent by the scrubber MID-PLAYBACK survives the next tick.

    The loop must not drag the picture back to where its clock was: it adopts the
    scrubbed position as the new origin (``_play_reanchor``) and carries on from
    there. The seek is put half a sweep away from where the clock is, on the
    ``clock_playback`` timeline (see ``CLOCK_FRAMES``): a tick advances four
    positions, so "still near the seek" and "dragged back to the clock" cannot be
    confused. The four-position ``playback`` page cannot show this at all - a
    four-step tick there is a whole timeline, so the clock never moves.
    """

    async def scenario() -> None:
        handles, state, trigger = clock_playback.handles, clock_playback.state, clock_playback.trigger
        frames = int(state.frame_max) + 1
        was_frame = int(state.frame)
        assert state.playing is False, "boot already left the page playing"

        tasks_before = _other_tasks()
        await asyncio.wait_for(trigger(), timeout=RETURN_TIMEOUT_S)
        created = _other_tasks() - tasks_before
        assert len(created) == 1, (
            f"the play press scheduled {len(created)} tasks, expected exactly 1"
        )
        task = created.pop()
        try:
            await asyncio.sleep(0.1)  # let the clock leave the frame it started on
            assert state.playing is True, "the play press did not start playback"
            clock = int(state.frame)
            # Half a sweep AWAY from the clock: inside CLOCK_WINDOW_S the loop can
            # only cover 15 of those 48 positions by running on regardless, so a
            # sample beside the seek is proof the seek was ADOPTED.
            seek = (clock + frames // 2) % frames

            # Exactly what the scrubber does: write the key. The listener is not
            # called here - this test is about the CLOCK, and the clock reads the
            # key.
            state.frame = seek
            state.flush()
            assert int(state.frame) == seek, (
                f"the scrub to {seek} was rewritten to {int(state.frame)!r} "
                "before the loop even ran a tick"
            )

            ahead = await _watch_clock(state, seek, frames)
            near = [d for d in ahead if 1 <= d <= CLOCK_STEP * CLOCK_WINDOW_S]
            assert near, (
                f"after the scrub from {clock} to {seek} the loop never carried on "
                f"from the seek (distances ahead of it: {ahead[:20]}): it dragged "
                "the picture back to its own clock, so the scrubber snaps back for "
                "as long as the animation runs"
            )
        finally:
            await asyncio.wait_for(trigger(), timeout=RETURN_TIMEOUT_S)  # pause
            await _drain([task])
            state.frame = was_frame
            state.flush()

    asyncio.run(scenario())


def test_a_step_press_while_playing_is_carried_on_from_not_snapped_back(clock_playback):
    """A NEXT press MID-PLAYBACK moves the picture, and the clock follows it.

    Three presses (ten positions each) put the stepped position 30 positions
    ahead of where the clock was - twice what the loop can cover inside
    ``CLOCK_WINDOW_S`` - so "the loop carried on from the step" and "the loop
    dragged the picture back" cannot be confused. The presses run without awaiting, so
    they land where a real burst of clicks does: across the tick the loop is in
    the middle of.
    """

    async def scenario() -> None:
        handles, state, trigger = clock_playback.handles, clock_playback.state, clock_playback.trigger
        step_fwd = _registered_trigger(clock_playback.server.controller, "step_fwd")
        frames = int(state.frame_max) + 1
        was_frame = int(state.frame)
        assert state.playing is False, "boot already left the page playing"

        tasks_before = _other_tasks()
        await asyncio.wait_for(trigger(), timeout=RETURN_TIMEOUT_S)
        created = _other_tasks() - tasks_before
        assert len(created) == 1, (
            f"the play press scheduled {len(created)} tasks, expected exactly 1"
        )
        task = created.pop()
        try:
            await asyncio.sleep(0.1)
            assert state.playing is True, "the play press did not start playback"
            start = int(state.frame)
            presses = 3  # 30 positions ahead of where the clock was
            for _ in range(presses):
                step_fwd()  # exactly what the NEXT button calls
            stepped = int(state.frame)
            assert stepped == (start + 10 * presses) % frames, (
                f"{presses} NEXT presses went {start} -> {stepped}, expected "
                f"{(start + 10 * presses) % frames}: a step while playing is a "
                "ten-frame SEEK, not a stop"
            )

            # The loop's own clock can only be 15 positions past where it was when
            # NEXT was pressed, so a sample BESIDE the stepped position (30 ahead
            # of that) cannot be the loop running on regardless: it can only be
            # the loop having adopted the step.
            ahead = await _watch_clock(state, stepped, frames)
            near = [d for d in ahead if 1 <= d <= CLOCK_STEP * CLOCK_WINDOW_S]
            assert near, (
                f"the step presses left the page at {stepped} (from {start}) but "
                f"the loop never carried on from it (distances ahead: "
                f"{ahead[:20]}): it dragged the picture back to its own clock, so "
                "NEXT does nothing while the animation runs"
            )
        finally:
            await asyncio.wait_for(trigger(), timeout=RETURN_TIMEOUT_S)  # pause
            await _drain([task])
            state.frame = was_frame
            state.flush()

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
    assert info["format"] == app.VIS_FORMAT
    assert info["structure_id"] is None
    assert app._structure_readout_text(info) == "structure: unknown", (
        "a dump that records no arm must read as unknown, not be guessed"
    )
    assert app.load_any_dump(path)["format"] == app.VIS_FORMAT, (
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


def test_the_s_params_tab_says_no_sweep_when_the_arm_has_none(
    tmp_path: Path, monkeypatch
) -> None:
    """The tab is offered with no sweep, so it has to say that in ONE line.

    ``um3k_panels.RIGHT_TABS`` now offers S-Params on every page: an arm with
    nothing registered keeps the tab and fills the refusal. Before this the
    body emitted a blank number line, an empty image and rows that could not
    exist, which reads as a broken tab rather than one that looked and found
    nothing. Both registry maps are emptied first, so this is the real arm-less
    case without depending on which summaries are checked in today.
    """
    import poc_app as app

    dump = tmp_path / "dumps" / "b.npz"
    dump.parent.mkdir(parents=True)
    info = _fixture_info(app, dump, structure_id="B", load_ohm=100.0)
    monkeypatch.setattr(app, "MULTIFREQ_BY_STRUCTURE", {})
    monkeypatch.setattr(app, "SINGLE_RUN_BY_STRUCTURE", {})

    log = _capture_html_widgets(monkeypatch)
    _boot_app(info)

    texts = _texts(log)
    assert "No sweep file found" in texts, (
        "the S-Parameters tab was built over no sweep and never said so, so "
        "the reader gets a heading over an empty panel. Texts emitted:\n"
        + "\n".join(texts)
    )
    drawn = [
        entry["src"]
        for entry in log
        if entry["kind"] == "Img" and "s_params_image" in str(entry["src"])
    ]
    assert not drawn, (
        f"the panel with no sweep still drew the image tag {drawn!r}, which "
        "can only ever be an empty box"
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

    # ``mem_ceiling_mb=None`` is pinned because the DEFAULT is auto, and auto
    # follows this container: on a small one it appends ``--mem-ceiling-mb``
    # and the ten-token count below would fail for a reason that has nothing to
    # do with the flag this test is about.  The ceiling has its own tests.
    argv = app.solve_argv("B", 20.4, app.LIVE_DUMP, mem_ceiling_mb=None)

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

    # THE DEBOUNCE, and WHY this is a SOURCE assertion rather than a behavioural
    # one: ``event.repeat`` is set by the BROWSER and never reaches Python, and
    # there is no server-side clock in the guard either (that is the whole point
    # of using the flag). So nothing on this side can observe a held key - the
    # only checkable contract is where the guard SITS in the listener: after
    # ``preventDefault`` (so a held Space still does not scroll the page) and
    # before the trigger (so a held key fires once, not once per repeat).
    assert "event.repeat" in js, (
        "keyboard.js carries no event.repeat guard: a held arrow or Space now "
        "sends one RPC per OS key repeat, and the ten-frame seek those carry "
        "runs away"
    )
    # Comments are dropped first: the file's own header and the WHY block above
    # the guard both NAME these three tokens long before the statements they
    # describe, so indexing the raw text would compare comment offsets. The
    # call form carries its parenthesis because the readiness check earlier in
    # the listener also reads ``window.trame.trigger`` (without one).
    code = "\n".join(
        line for line in js.splitlines() if not line.lstrip().startswith("//")
    )
    assert (
        code.index("preventDefault")
        < code.index("event.repeat")
        < code.index("window.trame.trigger(")
    ), (
        "keyboard.js no longer guards in the order preventDefault -> "
        "event.repeat -> trigger; a repeat that skipped preventDefault would "
        "scroll the page, and a guard after the trigger would be too late"
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


@pytest.mark.parametrize(
    "builder", ["run_web_vis", "run_web_vis_bare", "run_web"]
)
def test_every_bound_attribute_is_a_valid_vue_expression(builder, tmp_path):
    """No emitted `:attr="..."` may carry a value that is not JavaScript.

    BOTH builders are swept, because the page has two of them: ``run_web_vis``
    serves an ``emfit.vis/2`` dump, ``run_web`` serves a legacy single-plane
    dump - and that legacy builder is the one ``python3 server/poc_app.py``
    reaches on port 8080, because the default structure's dump carries
    ``plane_ez`` and no ``format`` key.

    ``run_web_vis`` is swept TWICE: from the full fixture and from a dump that
    omits every optional key.  The second one is where a defaulted value would
    leak a Python repr into a binding (the readouts are then the "not
    recorded" strings), so the two sweeps cover different values of the same
    template.

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
        elif builder == "run_web_vis_bare":
            info = _fixture_bare_info(app, tmp_path / "bare.npz")
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


def test_every_tab_value_matches_exactly_one_window_item(tmp_path: Path,
                                                         monkeypatch) -> None:
    """The tab bar and its window must name the SAME values, one for one.

    WHY this test exists: a ``VTab`` given only a label registers Vuetify's
    group-item default ``value: null`` - ``useGroupItem`` takes ``toRef(() =>
    props.value)`` as-is, and the tab has no index fallback - while
    ``VTabsWindowItem`` matches on the STRING its ``value`` names. ``VTabs``'
    group is ``mandatory: "force"``, so on mount it coerces the bound ``tab``
    state to the first tab's value, ``null``; ``VTabsWindow`` resolves its own
    model to the SELECTED TAB's value, so it ends up with ``null`` too and no
    window item matches. The page then draws a tab bar over four empty panels:
    S-Parameters blank, Modes blank, and nothing raising anywhere. Comparing the
    two value SETS here is what keeps the call sites paired; a per-widget
    assertion on one side alone would pass while the pairing was broken.
    """
    vuetify3 = pytest.importorskip("trame.widgets.vuetify3")
    import poc_app as app

    log: dict = {"tabs": [], "window": []}
    for name, key in (("VTab", "tabs"), ("VTabsWindowItem", "window")):
        real = getattr(vuetify3, name)

        def _factory(*args, _real=real, _key=key, **kwargs):
            log[_key].append(
                {
                    "label": args[0] if args else None,
                    "value": kwargs.get("value"),
                }
            )
            return _real(*args, **kwargs)

        monkeypatch.setattr(vuetify3, name, _factory)

    info = _fixture_info(app, tmp_path / "dump.npz")
    _boot_app(info)

    assert log["tabs"], "no VTab was built: the tab layout is gone entirely"
    assert log["window"], "no VTabsWindowItem was built: nothing can be shown"
    bare = [entry["label"] for entry in log["tabs"] if entry["value"] is None]
    assert not bare, (
        "these tabs carry no value, so Vuetify registers null for them and "
        "VTabsWindow can never match a window item - the panel behind the tab "
        f"stays empty with no error: {bare}"
    )
    tab_values = [entry["value"] for entry in log["tabs"]]
    window_values = [entry["value"] for entry in log["window"]]
    assert len(set(tab_values)) == len(tab_values), (
        "two tabs share one value, so selecting either shows the same panel: "
        f"{tab_values}"
    )
    assert len(set(window_values)) == len(window_values), (
        "two window items share one value, so one of them is unreachable: "
        f"{window_values}"
    )
    assert sorted(set(tab_values)) == sorted(set(window_values)), (
        "the tab values and the window-item values are different sets, so at "
        "least one tab selects a value no window item answers: tabs "
        f"{sorted(set(tab_values))} vs window {sorted(set(window_values))}"
    )


def test_run_web_vis_stands_the_column_on_the_loaded_page(
    tmp_path: Path, monkeypatch
) -> None:
    """If this fails, the DATA column's tabs are chosen from a hard-coded page.

    ``main`` hands the vis branch the page ``reload_page`` returned
    (``loaded_page=page``), so the snapshot the tab gating reads has to come
    from THAT page - here a sweep and a study record, both of which the
    ``is_vis: True`` literal holds as ``None`` - and the caller's dict must be
    left alone (``run_web_vis`` copies it and fills the copy's ``info``).
    """
    import poc_app as app

    info = _fixture_info(app, tmp_path / "dump.npz")
    freq = {"freq_ghz": [1.0], "s11": [0.0]}
    record = {"solver": "emfit"}
    handed = {
        "path": info.get("path"),
        "planes": None,
        "multifreq": freq,
        "record": record,
        "structure_id": None,
        "is_vis": True,
    }
    seen: dict = {}
    real_build = app.build_right_panel

    def _spy(ctx):
        seen["ctx"] = ctx
        real_build(ctx)

    monkeypatch.setattr(app, "build_right_panel", _spy)

    _boot_app(info, loaded_page=handed)

    assert "ctx" in seen, "run_web_vis never built the DATA column"
    ctx = seen["ctx"]
    assert ctx.dump.multifreq is freq, (
        "the context was built from a page other than the one handed in: "
        f"multifreq is {ctx.dump.multifreq!r}"
    )
    assert ctx.dump.record is record
    assert ctx.available.multifreq and ctx.available.record, (
        f"the snapshot claims {ctx.available!r}"
    )
    assert ctx.available.animation, (
        f"the handed page says is_vis, so the column keeps its five tabs: "
        f"{ctx.available!r}"
    )
    assert "info" not in handed, (
        "run_web_vis filled the caller's page dict instead of a copy of it"
    )


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


def _capture_v_selects(monkeypatch):
    """Record every VSelect the layout builds, in construction order.

    ``poc_app`` resolves the class with ``importlib.import_module`` on the
    vuetify3 MODULE, so patching the attribute on that module is what the page
    sees - the same trick ``_capture_html_widgets`` uses for Div/Pre/Img.  The
    real class is still constructed, so the layout stays the shipped layout and
    only the emitter is observed.
    """
    import trame.widgets.vuetify3 as vuetify3

    log = []
    real = vuetify3.VSelect

    def _factory(*args, **kwargs):
        log.append({"args": args, "kwargs": kwargs})
        return real(*args, **kwargs)

    monkeypatch.setattr(vuetify3, "VSelect", _factory)
    return log


def _capture_v_checkboxes(monkeypatch):
    """Record every VCheckbox the layout builds, in construction order.

    Same module-attribute patch as ``_capture_v_selects``: ``poc_app`` resolves
    ``VCheckbox`` from the vuetify3 MODULE, so the page sees the recorder.  The
    real class is still constructed, so the shipped layout is what is measured.
    """
    import trame.widgets.vuetify3 as vuetify3

    log = []
    real = vuetify3.VCheckbox

    def _factory(*args, **kwargs):
        log.append({"args": args, "kwargs": kwargs})
        return real(*args, **kwargs)

    monkeypatch.setattr(vuetify3, "VCheckbox", _factory)
    return log


def test_setup_project_picker_offers_the_solvers_own_arms(tmp_path: Path,
                                                          monkeypatch) -> None:
    """The SETUP picker's items ARE the solver's arm keys - not a literal list.

    Asserted against ``_structure_registry()`` rather than against a hardcoded
    ``["A", "B", "D"]``: the point of the change was that a new solver arm shows
    up by itself, and a test that spells the three out would pass just as
    happily after the arms had drifted apart again.

    No solve runs here.  The netlist side is asserted where it is CHEAP: the D
    row must carry a ``netlist`` that points at a file that exists, and
    ``solve_argv`` must build the solver's own flags for the arm (the page, not
    the argv builder, is what supplies netlist TEXT).
    """
    import ast

    import poc_app as app

    registry = app._structure_registry()
    assert registry, (
        "_structure_registry() returned nothing: the solver's STRUCTURES could "
        "not be read, so the picker fell back to its literal map and this test "
        "would be asserting on the fallback"
    )

    recorded = _capture_v_selects(monkeypatch)
    info = _fixture_info(app, tmp_path / "arms.npz")
    _boot_app(info)

    pickers = [entry["kwargs"] for entry in recorded
               if entry["kwargs"].get("label") == "Structure"]
    assert len(pickers) == 1, (
        f"expected exactly one 'Structure' VSelect in the SETUP column, found "
        f"{len(pickers)} - the picker moved or gained a twin"
    )
    items = ast.literal_eval(pickers[0]["v_bind_items"])
    assert items == sorted(registry), (
        f"the picker offers {items} while the solver's STRUCTURES has "
        f"{sorted(registry)}: the panel and the solver disagree about which "
        "arms exist"
    )
    assert "D" in items, (
        f"the diode arm is not offered ({items}); a solver arm the panel cannot "
        "select is the drift this test exists to catch"
    )

    # The MODE picker, from the SAME recorded log and the SAME boot: this is
    # the only thing in the suite that notices it vanishing from the layout.
    # tests/test_poc_mode_picker.py never looks at widgets at all, so an
    # `_emit_mode_picker` that returned early - or that was dropped from both
    # builders - would leave that whole file green.
    mode_pickers = [entry["kwargs"] for entry in recorded
                    if entry["kwargs"].get("label") == "solved candidates"]
    assert len(mode_pickers) == 1, (
        "expected exactly one 'solved candidates' VSelect in the Mode panel, "
        f"found {len(mode_pickers)} - the Mode picker is not in the layout, and "
        "tests/test_poc_mode_picker.py never looks at widgets, so nothing else "
        "would say so"
    )
    mode_kwargs = mode_pickers[0]
    assert mode_kwargs["v_model"] == ("mode_choice", 0), (
        f"the Mode picker no longer writes `mode_choice`: {mode_kwargs!r}"
    )
    assert mode_kwargs["v_bind_items"] == ("mode_choice_items", []), (
        "the Mode picker no longer reads the items a press fills: "
        f"{mode_kwargs!r}"
    )
    assert mode_kwargs["item_value"] == "value", (
        "the Mode picker's option value is no longer the candidate index: "
        f"{mode_kwargs!r}"
    )

    row = registry["D"]
    netlist = row.get("netlist")
    assert isinstance(netlist, str) and netlist, (
        f"D is not a netlist row: its STRUCTURES entry is {row!r}, so the arm "
        "would be solved with a lumped resistor and the startup line would say "
        "so"
    )
    assert Path(netlist).is_file(), (
        f"D's netlist row points at {netlist}, which is not on disk - the arm "
        "would refuse at solve time, not at selection time"
    )

    argv = app.solve_argv("D", 20.4, tmp_path / "d.npz")
    assert argv[argv.index("--structure") + 1] == "D", (
        f"the argv built for the diode arm does not name it: {argv}"
    )
    assert "--netlist" not in argv, (
        "solve_argv invented a --netlist of its own; the netlist text comes "
        f"from the page (argv: {argv})"
    )


# --- the Structure picker has to be READABLE, not just selectable ------------
#
# The picker's value is a bare arm id ("A", "B", "C", "D"): one letter, and
# not one number behind it (``load_ohm``, the netlist that closes the cut) is on
# the page at all.  The three tests below are about the caption that fixes that:
# where its sentences come from, that a selection repaints it through the SHIPPED
# state-change listener, and that an id nobody described is a harmless line
# rather than a traceback or an empty box.


def _capture_v_labels(monkeypatch):
    """Record every VLabel the layout builds, in construction order.

    The same module-attribute patch ``_capture_v_selects`` uses: ``poc_app``
    resolves ``VLabel`` from the vuetify3 MODULE, so the page sees the recorder -
    and the real class is still constructed, so what is measured is the shipped
    layout.
    """
    import trame.widgets.vuetify3 as vuetify3

    log = []
    real = vuetify3.VLabel

    def _factory(*args, **kwargs):
        log.append({"args": args, "kwargs": kwargs})
        return real(*args, **kwargs)

    monkeypatch.setattr(vuetify3, "VLabel", _factory)
    return log


def test_every_solver_arm_has_a_blurb() -> None:
    """The caption map may not lag behind the solver's own arm table.

    The picker's ITEMS are read from the solver's ``STRUCTURES``
    (``_structure_registry``), the SENTENCES from ``STRUCTURE_ARM_BLURBS`` in
    this file - two tables that can drift.  An arm with no line still WORKS (it
    is offered, nothing raises inside the handler), it just wears the fallback
    sentence, so not one other test in the suite would say a word about it.
    Asserted against the REGISTRY, not against a hardcoded ``A/B/C/D``: a test
    that spelled the arms out would pass just as happily after the solver had
    grown a fifth one.
    """
    import poc_app as app

    registry = app._structure_registry()
    assert registry, (
        "_structure_registry() returned nothing: the solver's STRUCTURES could "
        "not be read, so this test would be checking the caption against an "
        "empty arm list"
    )

    fallback = app._STRUCTURE_ARM_FALLBACK_BLURB
    missing = sorted(
        arm for arm in registry if arm not in app.STRUCTURE_ARM_BLURBS
    )
    assert not missing, (
        f"the solver dispatches on arm(s) {missing} that STRUCTURE_ARM_BLURBS "
        "does not describe: the picker offers them and their caption would be "
        f"the generic line {fallback!r} - add their sentence beside the arm "
        "row they are read from (evidence/termination/run_build_A.py:689)"
    )

    for arm in sorted(registry):
        blurb = app.structure_arm_blurb(arm)
        assert isinstance(blurb, str) and blurb.strip(), (
            f"arm {arm!r} has a BLANK caption: the line under the picker would "
            "be an empty element on a column that is read before anything is "
            "pressed"
        )
        assert blurb != fallback, (
            f"arm {arm!r} answers with the fallback sentence, so its own line "
            "is missing or unreachable"
        )
        # The two NETLIST rows (C, D) are the ones whose termination is not a
        # number at all: a reader who is not told that would take the arm for
        # another resistor, which is the one thing the caption must not do.
        if registry[arm].get("netlist"):
            assert "netlist" in blurb.lower(), (
                f"arm {arm!r} is a netlist row but its caption never says so: "
                f"{blurb!r}"
            )


def test_selecting_an_arm_repaints_its_blurb(tmp_path: Path, monkeypatch) -> None:
    """A write to ``solve_structure`` repaints the caption - through the shipped listener.

    The listener is taken out of ``state._change_callbacks`` and called the way
    trame's flush calls it (the value as a kwarg, the write already committed to
    the state), so the machinery exercised is the ``@state.change`` the page
    registers, not a copy of it.  The picker itself only WRITES the key, which
    is why the caption cannot hang off a trigger.
    """
    import trame.app as trame_app

    import poc_app as app

    labels = _capture_v_labels(monkeypatch)
    info = _fixture_info(app, tmp_path / "arms.npz")

    # ``@state.change`` registrations are APPENDED per boot and every ``_boot_app``
    # in this process lands on the SAME trame Server (see field_page:4077), so
    # the listeners this boot adds are the TAIL of the list.  Counted rather
    # than picked by closure identity: the handler closes over ``state`` alone,
    # which every boot in the process shares.
    before = len(
        trame_app.get_server().state._change_callbacks.get("solve_structure")
        or ()
    )
    _app, srv = _boot_app(info)
    state = srv.state
    entries = state._change_callbacks.get("solve_structure") or []
    assert len(entries) - before == 1, (
        f"this boot registered {len(entries) - before} 'solve_structure' "
        "listeners; expected exactly 1 - a picker whose write reaches no "
        "listener leaves the old arm's sentence on screen"
    )
    listener = entries[-1][0]

    def pick(arm):
        state.solve_structure = arm          # the client's write, as trame commits it
        listener(solve_structure=arm)        # what the flush calls (state.py:429-447)

    # The caption is ON the page, not just in the state: one VLabel bound to it.
    texts = [str(entry["args"][0]) for entry in labels if entry["args"]]
    assert "{{ solve_structure_blurb }}" in texts, (
        "the SETUP column emitted no VLabel bound to solve_structure_blurb, so "
        f"nothing on screen carries the sentence: {texts}"
    )

    opening = app.structure_arm_blurb(app._structure_key(info.get("structure_id")))
    assert str(state.solve_structure_blurb) == opening, (
        "the page did not open on the loaded dump's own arm: "
        f"{state.solve_structure_blurb!r} (expected {opening!r})"
    )

    pick("B")
    assert str(state.solve_structure_blurb) == app.STRUCTURE_ARM_BLURBS["B"], (
        "selecting arm B did not repaint the caption: "
        f"{state.solve_structure_blurb!r}"
    )
    assert str(state.solve_structure_blurb) != opening, (
        "arm B wears arm A's sentence, so the caption does not follow the "
        "selection at all"
    )

    pick("D")
    assert str(state.solve_structure_blurb) == app.STRUCTURE_ARM_BLURBS["D"], (
        f"selecting arm D did not repaint the caption: "
        f"{state.solve_structure_blurb!r}"
    )

    # The value is normalised the way every other reader of it normalises it
    # (_structure_key): a client that writes lower case is still arm B.
    pick("b")
    assert str(state.solve_structure_blurb) == app.STRUCTURE_ARM_BLURBS["B"], (
        "a lower-case arm id fell through to the wrong sentence: "
        f"{state.solve_structure_blurb!r}"
    )

    # Put the page back on arm A: the trame Server (and its state) is shared by
    # every boot in this process, so leaving an unusual value behind would be a
    # gift to whatever runs next.
    pick("A")
    assert str(state.solve_structure_blurb) == app.STRUCTURE_ARM_BLURBS["A"]


def test_an_arm_with_no_blurb_gets_a_harmless_line(tmp_path: Path, monkeypatch) -> None:
    """An arm id nobody described is a vague caption, not a traceback and not blank.

    A stale browser, a hand-typed value or an arm added to the solver without a
    line in ``STRUCTURE_ARM_BLURBS`` all land here.  None of them may take the
    page down or leave the reader with an empty element: the caption is prose
    about a control, and being one edit behind is not an error state.
    """
    import trame.app as trame_app

    import poc_app as app

    info = _fixture_info(app, tmp_path / "arms.npz")
    before = len(
        trame_app.get_server().state._change_callbacks.get("solve_structure")
        or ()
    )
    _app, srv = _boot_app(info)
    state = srv.state
    entries = state._change_callbacks.get("solve_structure") or []
    assert len(entries) - before == 1, (
        f"this boot registered {len(entries) - before} 'solve_structure' "
        "listeners; expected exactly 1"
    )
    listener = entries[-1][0]

    known = app.STRUCTURE_ARM_BLURBS["A"]
    for unknown in ("Q", "", "   ", None, 7):
        state.solve_structure = unknown     # committed first, as trame does
        listener(solve_structure=unknown)   # must not raise
        blurb = str(state.solve_structure_blurb)
        assert blurb.strip(), (
            f"the caption went BLANK for the unknown arm {unknown!r}: the "
            "SETUP column would show an empty element where the description "
            "belongs"
        )
        assert blurb == app._STRUCTURE_ARM_FALLBACK_BLURB, (
            f"the unknown arm {unknown!r} did not get the fallback sentence: "
            f"{blurb!r}"
        )
        assert blurb != known, (
            f"the unknown arm {unknown!r} was given arm A's own description"
        )

    # Restore arm A for the boots that follow (one trame Server per process).
    state.solve_structure = "A"
    listener(solve_structure="A")
    assert str(state.solve_structure_blurb) == known


def test_selecting_a_solver_arm_with_no_sweep_registry_says_so(
    tmp_path: Path, monkeypatch
) -> None:
    """A D dump has no multifreq summary REGISTERED: the panel says that, not nothing.

    D is the arm the literal ``MULTIFREQ_BY_STRUCTURE`` map does not name (it
    knows A and B), and no ``build_D_diode_multifreq_summary.json`` exists on
    disk.  The regression this covers: the picker offers D, so a D dump can
    reach the S-parameters panel, and the panel must neither raise nor render an
    empty box - it must state that the SWEEP for the arm has not been written
    and registered yet, which is a different fact from "no file beside the
    dump".

    The maps are patched to empty through the shipped ``_boot_s_params`` helper,
    so this asserts the page's behaviour when the registry knows nothing about
    the arm - the real D case - without depending on which summaries happen to
    be checked in today.
    """
    import poc_app as app

    dump = tmp_path / "dumps" / "d.npz"
    dump.parent.mkdir(parents=True)
    info = _fixture_info(app, dump, structure_id="D")

    panel, state = _boot_s_params(app, info, monkeypatch, sweeps={}, runs={})

    assert panel["reason"], (
        "the panel for the diode arm carries no reason at all, so the tab would "
        "open onto an empty box"
    )
    caption = panel["caption"]
    assert "structure D" in caption, (
        f"the caption does not name the arm it is empty for: {caption!r}"
    )
    assert "no multi-frequency summary is registered for arm D yet" in caption, (
        "the caption does not say the ARM has no registered sweep - the reader "
        f"cannot tell a missing registration from a missing file: {caption!r}"
    )
    assert panel["points"] == [] and panel["image"] is None, (
        "the diode arm's panel carried rows or a picture it could not have read"
    )
    assert state.s_params_caption and panel["caption"] in state.s_params_caption, (
        "the panel was built but its caption never reached the tab's state "
        f"({state.s_params_caption!r})"
    )



# --- Task A: the page has to fit the viewport -------------------------------
#
# ``_capture_html_widgets`` records kind/text/src only, so these two tests bring
# their own recorder: what has to be read back is the STYLE string of every Div
# the layout builds, because that is the whole of the fix - the player bar was
# not missing, it was pushed below the bottom of the window by a flex column
# that sized itself ``height: 100%`` inside a ``fill-height`` container and a
# plotter wrapper that demanded ``min-height: 320px``. Nothing here renders, so
# what is asserted is the sizes the browser is asked for, not their result.


def _boot_vis_recording_div_styles(monkeypatch, info) -> list:
    """Boot ``run_web_vis`` and return every ``Div`` style, in build order."""
    pyvista = pytest.importorskip("pyvista")
    import trame.widgets.html as html_mod

    styles = []
    real_div = html_mod.Div

    def _factory(*args, **kwargs):
        style = kwargs.get("style")
        styles.append("" if style is None else str(style))
        return real_div(*args, **kwargs)

    monkeypatch.setattr(html_mod, "Div", _factory)
    real_render = pyvista.Plotter.render
    pyvista.Plotter.render = lambda self, *a, **k: None  # no OpenGL in this image
    try:
        _boot_app(info)
    finally:
        pyvista.Plotter.render = real_render
    assert styles, (
        "no trame Div was built at all: the boot never reached the layout, so "
        "this test would prove nothing"
    )
    return styles


def test_page_is_capped_to_the_viewport_so_the_player_bar_stays_on_screen(
    tmp_path: Path, monkeypatch
) -> None:
    """The page column is one viewport tall and nothing forces it taller.

    The bar at the foot of the column is ``flex: 0 0 auto``, so it keeps its own
    height - but only if the column that holds it is not allowed to grow past
    the window. It was: ``height: 100%`` on a flex column whose parent is
    ``fill-height`` resolved against content, and the 3-D wrapper's
    ``min-height: 320px`` then made that content taller than the window, which
    put the bar off the bottom of a page with ``overflow: hidden``.
    """
    import poc_app as app

    info = _fixture_info(app, tmp_path / "dump.npz")
    styles = _boot_vis_recording_div_styles(monkeypatch, info)

    capped = [
        s
        for s in styles
        if "height: 100vh" in s and "flex-direction: column" in s
        and "overflow: hidden" in s
    ]
    assert capped, (
        "no Div asks for a column exactly one viewport tall (height: 100vh, "
        "flex-direction: column, overflow: hidden); the page column is still "
        "sized against its own content, which is what let it overflow the "
        f"window and hide the player bar. Div styles built: {styles!r}"
    )
    assert any("flex: 1 1 auto; min-height: 0;" in s for s in styles), (
        "the 3-D wrapper no longer takes the leftover height with no floor of "
        f"its own (flex: 1 1 auto; min-height: 0). Div styles built: {styles!r}"
    )
    assert not any("min-height: 320px" in s for s in styles), (
        "a 320px floor is back on a child of the page column: on a viewport "
        "shorter than that floor plus the bar the column cannot shrink and the "
        "player bar goes off the bottom again"
    )
    assert any("flex: 0 0 auto" in s for s in styles), (
        "the player bar is no longer pinned to its own height (flex: 0 0 auto), "
        "so it can be squeezed out of view instead of staying on screen"
    )


def _boot_web_recording_div_styles(monkeypatch, info) -> list:
    """Boot ``run_web`` and return every ``Div`` style, in build order.

    The legacy twin of ``_boot_vis_recording_div_styles``. It is a separate
    helper rather than a flag on that one because the two pages are entered
    through different helpers (``_boot_app`` / ``_boot_web``), and one helper
    that switched between them would hide which page a failure came from.
    ``_boot_web`` doubles ``pyvista.Plotter.render`` itself (this image has no
    EGL) and restores it, so only the style strings are recorded here - nothing
    renders, and the sizes asserted below are the ones the browser is asked
    for, not their result.
    """
    pytest.importorskip("pyvista")
    import trame.widgets.html as html_mod

    styles = []
    real_div = html_mod.Div

    def _factory(*args, **kwargs):
        style = kwargs.get("style")
        styles.append("" if style is None else str(style))
        return real_div(*args, **kwargs)

    monkeypatch.setattr(html_mod, "Div", _factory)
    _boot_web(info)
    assert styles, (
        "no trame Div was built at all: run_web never reached its layout, so "
        "this test would prove nothing"
    )
    return styles


def test_legacy_page_is_capped_to_the_viewport_so_the_panels_stay_on_screen(
    tmp_path: Path, monkeypatch
) -> None:
    """``run_web``'s column is one viewport tall and nothing forces it taller.

    The legacy page carries no player bar - playback lives in ``run_web_vis`` -
    so the row that has to survive at the foot of the column is the panels
    scroll box holding ``_emit_frequency_panel`` and ``_emit_port_wave_panel``.
    It was lost the same way the modern bar was: a ``height: 100%`` flex column
    inside a Vuetify ``fill-height`` container sizes against its own content,
    and the 3-D wrapper's ``min-height: 320px`` made that content taller than
    the window, so the column's ``overflow: hidden`` cut the panels off the
    bottom instead of the plotter giving up height.
    """
    import poc_app as app

    info = _fixture_legacy_info(app, tmp_path / "legacy.npz")
    styles = _boot_web_recording_div_styles(monkeypatch, info)

    columns = [s for s in styles if "flex-direction: column" in s]
    assert columns, (
        "run_web built no flex column at all, so the page column this test is "
        f"about is not there. Div styles built: {styles!r}"
    )
    assert not any("height: 100%;" in s for s in columns), (
        "a page column is sized height: 100% again; inside fill-height that "
        "resolves against the column's own content, which is what let the "
        f"column grow past the window. Div styles built: {styles!r}"
    )
    capped = [
        s for s in columns if "height: 100vh" in s and "overflow: hidden" in s
    ]
    assert capped, (
        "no Div asks for a column exactly one viewport tall (height: 100vh, "
        "flex-direction: column, overflow: hidden); the legacy page column is "
        "still sized against its content, which is what pushed the panels off "
        f"the bottom of the window. Div styles built: {styles!r}"
    )

    assert any("flex: 1 1 auto; min-height: 0;" in s for s in styles), (
        "the 3-D wrapper no longer takes the leftover height with no floor of "
        f"its own (flex: 1 1 auto; min-height: 0). Div styles built: {styles!r}"
    )
    assert not any("min-height: 320px" in s for s in styles), (
        "a 320px floor is back on a child of the page column: on a window "
        "shorter than that floor plus the rows around it the column cannot "
        "shrink and the panels go off the bottom again"
    )
    assert not [
        s for s in styles if "min-height:" in s and "min-height: 0" not in s
    ], (
        "a Div asks for a non-zero min-height; any positive floor on a child "
        "of the page column is a height the column can never give back"
    )

    panels = [
        s for s in styles if "flex: 0 0 auto" in s and "overflow-y: auto" in s
    ]
    assert panels, (
        "the panels scroll box is no longer pinned to its own height and made "
        "scrollable (flex: 0 0 auto ... overflow-y: auto), so the two panels "
        "can be sliced by the column's overflow:hidden instead of scrolled to"
    )


# --- Task B: the mode picture has to be on the eye side of the sheets -------


def test_mode_picture_reaches_the_plotter_in_front_of_the_xcut_sheets(
    tmp_path: Path, monkeypatch
) -> None:
    """The still lands outside the sheet slab, on the camera's side of it.

    Both halves of the original defect are geometry, so both are checkable with
    ``render()`` doubled (this image has no EGL/OSMesa; a real render segfaults
    the interpreter) and neither is checkable as pixels:

    * the picture was drawn at ``xcut_near_mm + cell`` - BETWEEN the near and the
      far opaque sheet, where the near one hides it;
    * its y band was centred on the grid origin while the x-cut sheets occupy
      ``y in [0, (ny - 1) * cell]``, so half of it hung outside the framed strip.

    The eye side is NOT re-derived here with the production formula. The test
    measures ``plotter.camera.position[0]``, REQUIRES the eye to sit outside the
    sheet slab (so "which side" is a fact about the camera and not a sign
    convention), and then checks an independent geometric relation: the picture
    is on that same side of BOTH sheets and nearer the eye than the near sheet.
    Recomputing ``near + side * cell`` and comparing against it would only
    restate whichever formula the fix happened to ship - which is how an earlier
    ``camera.direction`` version of this placement passed its own test while
    being one convention-change away from hiding the picture again.

    Both sides are exercised, and the camera is pushed far enough out that the
    slab cannot straddle it: pyvista's own framing leaves the eye about one
    world unit from the origin, which in this millimetre scene lands inside the
    slab, where "in front" is not defined at all.
    """
    pyvista = pytest.importorskip("pyvista")
    import poc_app as app

    info = _fixture_info(app, tmp_path / "dump.npz")
    cell_mm = float(np.asarray(info["cell_m"]) * 1e3)
    planes_mm = (float(info["xcut_near_mm"]), float(info["xcut_far_mm"]))
    ny = int(info["ny"])
    band_mm = (0.0, (ny - 1) * cell_mm)
    solved = {
        "ok": True,
        "grid": np.ones((app.MODE_GRID_CELLS, app.MODE_GRID_CELLS), dtype=float),
        # y_max, z_max in METRES. 0.02 mm of half-width fits inside the 0.05 mm
        # band the fixture's six y samples span, so the picture can be required
        # to land WHOLE in the framed strip.
        "extent": (0.02e-3, 0.04e-3),
        "caption": "mode picture from the solve",
        "beta_rad_per_m": 223.180967,
    }

    real_render = pyvista.Plotter.render
    pyvista.Plotter.render = lambda self, *a, **k: None  # no OpenGL in this image
    try:
        monkeypatch.setattr(app, "mode_view", lambda *a, **k: solved)
        _app, srv = _boot_app(info)
        trigger = _registered_trigger(srv.controller, "mode_view_toggle")
        cells = _closure_cells(trigger)
        assert {"state", "handles", "plotter"} <= set(cells), (
            "the Mode trigger does not close over state/handles/plotter "
            f"(freevars: {sorted(cells)}), so where the picture landed cannot "
            "be read back"
        )
        state = cells["state"]
        handles = cells["handles"]
        plotter = cells["plotter"]
        # The page boots on the y-cut family, where this picture is drawn hidden;
        # switching to the x-cut family is what the user does to see it.
        state.mode = "xcut"

        band_mid_mm = 0.5 * band_mm[1]
        for frame, expect_side in ((plotter.view_yz, 1.0), (plotter.view_zy, -1.0)):
            frame(render=False)
            framed_x = float(np.asarray(plotter.camera.position, dtype=float)[0])
            eye_side = 1.0 if framed_x > 0.0 else -1.0
            assert eye_side == expect_side, (
                f"{frame.__name__} did not put the camera on the x-side this "
                f"test needs: position {plotter.camera.position!r}"
            )
            # Slide the eye out along the axis that framing chose, keeping the
            # view along x and the sheets centred, until it is unambiguously
            # clear of the slab on that side.
            eye_x_mm = eye_side * 10.0 * max(abs(value) for value in planes_mm)
            plotter.camera_position = [
                (eye_x_mm, band_mid_mm, 0.0),
                (0.0, band_mid_mm, 0.0),
                (0.0, 0.0, 1.0),
            ]
            eye_x_now = float(np.asarray(plotter.camera.position, dtype=float)[0])
            assert eye_x_now == pytest.approx(eye_x_mm), (
                "the camera did not keep the eye x this test set, so nothing "
                f"below is about a known eye: {eye_x_now!r} != {eye_x_mm!r} mm"
            )
            assert eye_x_now > max(planes_mm) or eye_x_now < min(planes_mm), (
                "the eye has to be outside the sheet slab for 'in front' to "
                f"mean anything: eye x {eye_x_now!r} mm, sheets {planes_mm} mm"
            )
            asyncio.run(trigger())

            entry = handles.get("mode_actor")
            assert entry is not None, (
                "the solve returned a drawable grid but no picture reached the "
                f"plotter (handles: {sorted(handles)})"
            )
            actor = entry["actor"]
            assert actor is plotter.actors.get("mode_picture"), (
                "the handle does not point at the actor registered as "
                f"'mode_picture' (plotter actors: {sorted(plotter.actors)})"
            )
            assert actor.visibility, (
                "the picture is in the plotter but hidden, so the x-cut family "
                "shows nothing extra after a solve"
            )

            grid = entry["grid"]
            bounds = grid.bounds
            near_x_mm = max(planes_mm) if eye_side > 0.0 else min(planes_mm)
            # Independent geometry, not the production formula restated: every
            # sheet x has to be behind the picture as seen from the eye, i.e.
            # the picture is clear of BOTH sheets on the eye's side of them.
            for sheet_x_mm in planes_mm:
                assert (bounds[0] - sheet_x_mm) * eye_side > 0.0, (
                    "the picture is not clear of both x-cut sheets on the eye's "
                    f"side: picture x {bounds[0]!r} mm, sheets {planes_mm} mm, "
                    f"eye x {eye_x_now!r} mm (side {eye_side}) - between the two "
                    "sheets, or behind the near one, it is hidden by opaque "
                    "geometry"
                )
            assert abs(eye_x_now - bounds[0]) < abs(eye_x_now - near_x_mm), (
                "the picture did not land in front of the sheet nearest the eye, "
                f"so the near sheet hides it: picture x {bounds[0]!r} mm, near "
                f"sheet {near_x_mm!r} mm, eye x {eye_x_now!r} mm"
            )
            assert bounds[1] == pytest.approx(bounds[0]), (
                "the picture is a single y-z sheet: its two x bounds must agree, "
                f"got {bounds[0]!r} and {bounds[1]!r}"
            )
            assert bounds[2] >= band_mm[0] and bounds[3] <= band_mm[1], (
                "the picture hangs outside the y band the x-cut sheets occupy "
                f"({band_mm} mm): its y span is {(bounds[2], bounds[3])!r} mm, "
                "so the framing _show gives this family crops it"
            )
    finally:
        pyvista.Plotter.render = real_render


# --- what a dump may leave out, and what it may not -------------------------
#
# ``_fixture_info`` writes every optional key, so on its own it cannot tell a
# page that DEFAULTS a missing key from a page that would crash on it.  The two
# tests below are the pair that can: one drops every optional key (the boot must
# still happen, with "not recorded" readouts rather than invented numbers), the
# mirror drops a STRUCTURAL one (the loader must still refuse, loudly, naming
# the key - a missing axis is never defaulted into a wrong picture).


def test_a_dump_with_no_optional_key_boots_without_a_keyerror(tmp_path):
    """If this fails, the page reads an optional key as if the dump owed it.

    The file carries the schema and the mandatory axes and NOTHING else.  Two
    things have to hold for the page to boot from it:

    * ``load_vis`` materialises the absent optionals itself - NaN for a number,
      None for a text - so the key set the page reads is EXACTLY the one a full
      dump hands it (asserted below, so a loader that stopped doing this fails
      here rather than in a browser), and
    * ``run_web_vis`` therefore reaches ``server.start``: every readout that has
      nothing to print says so instead of raising ``KeyError``.
    """
    import poc_app as app

    optional = _fixture_bare_info(app, tmp_path / "bare.npz")
    full = _fixture_info(app, tmp_path / "full.npz")

    assert set(optional) == set(full), (
        "a dump without the optional keys was handed a different key set: "
        f"missing {sorted(set(full) - set(optional))}, extra "
        f"{sorted(set(optional) - set(full))}"
    )
    # A recorded-only number is NaN, a recorded-only text is None: the page
    # prints "not recorded" for these rather than substituting a number.
    for key in (
        "xcut_near_mm", "xcut_far_mm", "port_x_mm", "load_x_mm",
        "substrate_h_mm", "strip_w_mm", "eps_r", "v_analytic_m_s",
        "v_measured_m_s", "t_traverse_ns", "f_ref_hz", "f_pulse_hz",
    ):
        assert math.isnan(optional[key]), (
            f"{key} is {optional[key]!r} on a dump that never recorded it"
        )
    assert optional["velocity_note"] is None
    assert optional["structure_id"] is None
    assert optional["load_series"] is None

    _app, srv = _boot_app(optional)

    assert srv is not None, "the page did not boot from a dump with no optionals"


@pytest.mark.parametrize("key", ["t_ns", "nx", "ez_xcut_far", "frame_index_xcut"])
def test_a_dump_missing_a_mandatory_key_is_still_refused(key, tmp_path, capsys):
    """The mirror image: a STRUCTURAL key is never defaulted, only advertised.

    Drop one of the keys ``load_vis`` refuses a dump for lacking and the boot
    must still stop at that loader, with the key's own name in the message -
    both from ``load_vis`` and through ``reload_page``, the call ``main`` and a
    finished solve actually use, so the fence is at the ONE entry point.
    """
    import poc_app as app

    path = tmp_path / f"no_{key}.npz"
    np.savez(path, **_bare_payload(app, drop=key))

    with pytest.raises(SystemExit) as excinfo:
        app.load_vis(path)
    assert excinfo.value.code == 2, (
        f"a dump without {key} exited {excinfo.value.code!r}, not 2"
    )
    message = capsys.readouterr().err
    assert key in message, (
        f"the refusal for a dump without {key} does not name it: {message!r}"
    )

    with pytest.raises(SystemExit):
        app.reload_page(path)
    assert key in capsys.readouterr().err, (
        f"reload_page let a dump without {key} past the fence that load_vis "
        "still holds"
    )



def test_a_page_that_claims_the_animation_still_raises_nt(tmp_path):
    """The PLAYER fence at the READ SITE, on the pages ``load_vis`` cannot see.

    ``test_a_dump_missing_a_mandatory_key_is_still_refused`` proves the LOADER
    refuses a short dump.  It cannot see a page that DEFAULTS an axis, because
    turning the frame count's ``info["nt"]`` into ``info.get("nt", 0)`` leaves
    that refusal exactly as it was: the file the operator opened is refused by
    ``load_vis``, and every dict that reaches the page by another road - a page
    dict built by hand, a future loader - boots instead into a picture with no
    frames in it.

    So the fence is repeated on the dict the page actually reads, and it is
    keyed on the CLAIM: a page whose ``format`` is a vis format says it carries
    the timeline, so a missing ``nt`` still raises ``KeyError('nt')``.  A crash
    is a report; a page that starts, registers every trigger and paints nothing
    is a silent wrong answer, which is strictly worse.
    """
    import poc_app as app

    info = _fixture_info(app, tmp_path / "vis.npz")
    assert info.get("format") in app.VIS_FORMATS, (
        f"the fixture no longer claims the animation: {info.get('format')!r}"
    )
    page = dict(info)
    page.pop("nt")

    with pytest.raises(KeyError) as excinfo:
        _boot_app(page)
    assert "nt" in str(excinfo.value), (
        "the page claimed the animation and failed on something other than "
        f"the missing axis ({excinfo.value!r}); the fence guards the wrong line"
    )


def test_a_page_that_claims_no_animation_boots_a_shell_without_a_timeline(
    tmp_path, capsys, monkeypatch
):
    """The SHELL fence: no ``format`` means no timeline, and the page LIVES.

    A legacy single-plane dump carries no ``nt`` and does not claim one either
    - it is the field dump ``run_web`` has always served - so the animation
    page booted on one must not read a timeline it never claimed.  Nothing can
    be drawn from it (``_vis_grid`` indexes the arrays a vis dump stores, and a
    field dump has none), so each plane costs ONE stderr line through the
    per-plane guard while the page still boots: the columns build, and the
    centre column is handed ``nt`` of None.

    None, never 0: zero frames is a page CLAIMING an empty animation, and every
    readout built on that count would quote frame 1 of 0.
    """
    import poc_app as app
    import um3k_context

    legacy = _fixture_legacy_info(app, tmp_path / "legacy.npz")
    assert "format" not in legacy, (
        "the legacy fixture now claims a vis format, so this page is not the "
        "shell case any more"
    )
    assert "nt" not in legacy

    registered: dict = {}
    real_register = um3k_context.PageContext.register_handle

    def _record(self, name, obj):
        registered[name] = obj
        return real_register(self, name, obj)

    monkeypatch.setattr(um3k_context.PageContext, "register_handle", _record)

    _app, srv = _boot_app(legacy)  # must not raise: the shell lives

    err = capsys.readouterr().err
    for key in ("ez_ycut", "ez_xcut_near", "ez_xcut_far"):
        assert f"[poc_app] plane {key} not drawn: " in err, (
            f"the undrawable plane {key} reported nothing on stderr: {err!r}"
        )

    assert srv.state.frame_max is None, (
        "a page with no timeline booted with frame_max "
        f"{srv.state.frame_max!r}; absent must read as None, never as frames"
    )
    assert srv.state.frame_label is None, (
        "the page labelled a frame it has no axis for: "
        f"{srv.state.frame_label!r}"
    )
    assert "nt" in registered, (
        f"the layout registered {sorted(registered)}; the centre column reads "
        "its frame count off a registered handle"
    )
    assert registered["nt"] is None, (
        f"the shell page registered nt={registered['nt']!r}"
    )




# --- the cut STATION: recorded, or said out loud as absent -------------------
#
# ``j_cut`` is the y SAMPLE INDEX the x-z sheet was taken from, and it is the
# only fact that says where that sheet belongs.  A dump need not carry it (it is
# not one of VIS_MANDATORY_KEYS), and the page has exactly three ways to get
# that wrong, one test each below: the loader fills in a 0, the geometry draws
# the sheet at that 0, the readout prints that 0 - or the state dump reports it
# as a measured position.  The pair in each test is a bare dump and a full one,
# so "never draws" cannot be satisfied by "never draws at all".


def test_a_dump_without_j_cut_hands_the_page_a_null_station(tmp_path):
    """If this fails, a cut station the dump never recorded has been invented.

    ``load_vis`` is where the station enters the page, and the comment above the
    line already promised recorded values only.  A dump with no ``j_cut`` must
    hand the page ``None`` and KEEP the key - dropping it would change the key
    set the page reads (the fence in
    ``test_a_dump_with_no_optional_key_boots_without_a_keyerror``), and
    defaulting it to 0 puts an x-z sheet at the bottom edge of the grid, which
    is a position nothing recorded.

    Mutation that breaks it: restore
    ``"j_cut": int(_npz_scalar(data, "j_cut", 0.0))`` (poc_app.py:548) - the
    bare dump then reports ``0`` instead of ``None``.
    """
    import poc_app as app

    bare = _fixture_bare_info(app, tmp_path / "bare.npz")
    full = _fixture_info(app, tmp_path / "full.npz")

    assert "j_cut" in bare, (
        "load_vis dropped j_cut instead of nulling it: the page then reads a "
        "different key set from a bare dump than from a full one"
    )
    assert bare["j_cut"] is None, (
        f"a dump that records no j_cut was handed j_cut={bare['j_cut']!r}; the "
        "loader has substituted a station for one the file does not carry"
    )
    assert full["j_cut"] == 3, (
        f"the RECORDED station stopped being read: j_cut={full['j_cut']!r}, "
        "so the null above would prove nothing but a dead loader"
    )


def test_the_x_z_sheet_is_only_placed_at_a_recorded_station(tmp_path):
    """If this fails, the drawn sheet sits at a station nothing recorded.

    ``_vis_grid`` is the ONE place the drawn geometry is built (the reload path
    references its arrays rather than copying the geometry, on purpose), so the
    y of the x-z sheet is decided here and nowhere else.  With no recorded index
    there is no station, and the build must refuse with a message naming
    ``j_cut`` - the caller drops that one sheet and prints why, which is what
    makes the absence visible instead of silent.  With an index, the sheet must
    land on exactly ``j_cut * cell_mm``, i.e. NOT on the y = 0 the old default
    produced (0 is a legal station, so only the millimetres can tell them apart).

    Mutation that breaks it: put
    ``origin = (0.0, float(int(info["j_cut"])) * cell_mm, 0.0)`` back
    (poc_app.py:4944) - the bare build then returns a sheet at y = 0 (or raises
    ``TypeError``) instead of the named refusal.
    """
    pytest.importorskip("pyvista")  # the ImageData is built through it
    import poc_app as app

    bare = _fixture_bare_info(app, tmp_path / "bare.npz")
    with pytest.raises(ValueError) as excinfo:
        app._vis_grid(bare, "ez_ycut", 0)
    assert "j_cut" in str(excinfo.value), (
        "the refusal for an unrecorded station does not name j_cut, so the "
        f"stderr line it produces cannot say what is missing: {excinfo.value!r}"
    )

    full = _fixture_info(app, tmp_path / "full.npz")
    cell_mm = app._cell_mm(full)
    grid = app._vis_grid(full, "ez_ycut", 0)
    assert grid.origin[1] == pytest.approx(full["j_cut"] * cell_mm), (
        f"the x-z sheet was built at y = {grid.origin[1]!r} mm, not at the "
        f"recorded station {full['j_cut'] * cell_mm!r} mm"
    )
    assert grid.origin[1] != 0.0, (
        "the sheet landed on y = 0, which is the station the old default "
        "invented - check the cell size and the index are both still applied"
    )


def test_an_empty_plane_is_dropped_with_a_reason_instead_of_ending_the_page(
    tmp_path, capsys
):
    """If this fails, one empty plane takes the whole vis page down.

    ``_vis_grid`` is called once per plane inside the boot loop's ``try``, whose
    ``except Exception`` prints ``plane <key> not drawn: <why>`` and moves on to
    the next sheet.  An empty plane is a *build* that cannot be made, not an
    entry refusal, so it has to arrive as an ``Exception``: a ``SystemExit``
    walks straight through that guard and ends the page over one blank sheet.
    The dump below is a full vis dump with one plane's frame axis emptied, which
    is the state a truncated archive leaves behind.

    Mutation that breaks it: put ``raise SystemExit(2)`` where ``_vis_grid``
    refuses the empty plane (poc_app.py:5002) - the direct call below then
    raises ``SystemExit`` instead of ``ValueError``, and the boot would exit.
    """
    pytest.importorskip("pyvista")  # the ImageData is built through it
    import poc_app as app

    info = _fixture_info(app, tmp_path / "empty_plane.npz")
    array = info["ez_ycut"]
    info["ez_ycut"] = np.zeros((0, array.shape[1], array.shape[2]), array.dtype)

    with pytest.raises(ValueError) as excinfo:
        app._vis_grid(info, "ez_ycut", 0)
    assert "ez_ycut" in str(excinfo.value), (
        "the refusal does not name the plane it could not build, so the stderr "
        f"line cannot say which sheet is missing: {excinfo.value!r}"
    )

    _app, srv = _boot_app(info)
    err = capsys.readouterr().err
    assert "plane ez_ycut not drawn" in err, (
        "the boot loop's per-plane guard printed nothing for the empty plane, "
        f"so no reason for the missing sheet reaches the log: {err!r}"
    )
    assert "no ez_ycut frames" in err, (
        f"the guard's line does not carry the build's own reason: {err!r}"
    )
    assert srv is not None, (
        "the page did not come up with one empty plane, which is what the "
        "per-plane guard exists to allow"
    )


def test_the_x_z_readout_says_not_recorded_when_no_station_is(tmp_path, monkeypatch):
    """If this fails, a readout names a sheet that is not on screen.

    The mode line is the page's own statement of where the x-z sheet is, and on
    a dump with no ``j_cut`` there is no such sheet: the geometry refuses it, so
    the line has to say "not recorded" in the same words the other readouts use
    rather than format a station out of a 0.  The full dump is the counterpart -
    without it, a line that always said "not recorded" would pass.

    Mutation that breaks it: bring the boot-time ``j_mm = float(int(info[
    "j_cut"])) * cell_mm`` back and format it here - the bare boot then dies
    with a ``TypeError`` inside the page builder instead of reaching the
    readout, and the full-dump assertion below would print ``y = 0.0000``.
    """
    pyvista = pytest.importorskip("pyvista")
    import poc_app as app

    # Same reason the playback fixture doubles it: this image has no EGL, no
    # libOSMesa and no X server.
    monkeypatch.setattr(pyvista.Plotter, "render", lambda self, *a, **k: None)

    bare = _fixture_bare_info(app, tmp_path / "bare.npz")
    _app, srv = _boot_app(bare)
    label = srv.state.mode_label
    assert "not recorded" in label, (
        f"the x-z readout claims a station on a dump that records none: {label!r}"
    )
    assert "j_cut" in label, (
        f"the readout says something is missing without saying what: {label!r}"
    )
    assert " y = " not in label and "y = 0.0000" not in label, (
        f"the readout still quotes a y for a sheet that was not drawn: {label!r}"
    )

    full = _fixture_info(app, tmp_path / "full.npz")
    _app, srv = _boot_app(full)
    full_label = srv.state.mode_label
    station_mm = full["j_cut"] * app._cell_mm(full)
    assert f"y = {station_mm:.4f} mm" in full_label, (
        "a recorded station no longer reaches the readout: "
        f"expected y = {station_mm:.4f} mm in {full_label!r}"
    )


def test_the_state_dump_does_not_record_a_station_the_dump_lacks(tmp_path):
    """If this fails, the state document reports an invented position.

    ``build_state_dump`` is what an operator reads to check what the page
    believes, so a number in it is a claim.  For a dump with no ``j_cut`` the
    x-z plane's ``fixed_mm`` must be null WITH the reason beside it (the shape
    ``geometry_mm.strip_y`` already uses for a position the dump does not
    carry), and for a dump that records one it must be the recorded index times
    the cell size - not the 0.0 an ``int(...)`` default used to print.

    Mutation that breaks it: restore
    ``"fixed_mm": {"y": round(int(info["j_cut"]) * cell_mm, 9)}``
    (poc_app.py:3042) - the bare document then carries ``y = 0.0`` (or raises
    ``TypeError``) and there is no note to read.
    """
    import poc_app as app

    bare = _fixture_bare_info(app, tmp_path / "bare.npz")
    full = _fixture_info(app, tmp_path / "full.npz")

    bare_ycut = app.build_state_dump(bare, {})["animation"]["planes"][0]
    assert bare_ycut["key"] == "ez_ycut", (
        f"the first animation plane is no longer the x-z sheet: {bare_ycut!r}"
    )
    fixed = bare_ycut["fixed_mm"]
    assert fixed["y"] is None, (
        f"a dump that records no j_cut still reports y = {fixed['y']!r} mm in "
        "the state document; that number is a position nothing measured"
    )
    assert "not recorded" in fixed.get("y_note", ""), (
        f"the null station carries no reason: {fixed!r}"
    )
    assert "j_cut" in fixed["y_note"], (
        f"the reason does not name the key that is missing: {fixed['y_note']!r}"
    )

    full_ycut = app.build_state_dump(full, {})["animation"]["planes"][0]
    assert full_ycut["fixed_mm"]["y"] == pytest.approx(
        full["j_cut"] * app._cell_mm(full)
    ), (
        "a RECORDED station no longer reaches the state document: "
        f"{full_ycut['fixed_mm']!r}"
    )



# =============================================================================
# The Y / Z cut sheets on the VIS page (run_web_vis)
# =============================================================================
# The three tests below pin the part of the cut that has no widgets yet: the
# STATE the page opens on, the two controller methods the sliders will call, and
# the fact that a page with no plane stack gets neither.  They boot the real
# builder - same recipe as _boot_app - with Plotter.render doubled, because this
# image has no OpenGL: the boot itself draws, and so does every cut change.


@contextlib.contextmanager
def _counted_render():
    """``Plotter.render`` doubled and COUNTED, for the whole block.

    The page draws four times while it boots and once per cut change, so the
    double has to span both phases; a double installed only around the drive
    would leave the boot's real render in place.
    """
    pyvista = pytest.importorskip("pyvista")
    real_render = pyvista.Plotter.render
    calls = []

    def _no_render(self, *args, **kwargs):
        calls.append(1)  # counted, never performed

    pyvista.Plotter.render = _no_render
    try:
        yield calls
    finally:
        pyvista.Plotter.render = real_render


@pytest.fixture(scope="module")
def field_page(tmp_path_factory):
    """Boot the legacy single-plane page ONCE, and record what it opened on.

    ``trame.app.get_server()`` is a PROCESS-WIDE singleton: every ``_boot_app``
    in one pytest process lands on the SAME ``Server`` - its ``state`` and its
    controller-function registry - so a second boot inherits the first boot's
    keys and the handlers the first boot registered.  Measured before this
    fixture existed: one ``cut_y(9)`` call fired the previous boot's handler as
    well and drew 12 times, and the no-plane-stack page saw ``cut_y = 9`` left
    over from the test before it.  ONE boot per process is therefore what makes
    an exact ``delta == 1`` assertion mean anything at all.

    The render double is entered HERE, not around an individual drive, and stays
    in place for the whole module: the page draws ~4x while it BOOTS as well as
    once per cut change, and this image has no EGL, no libOSMesa and no X server,
    so a real ``render()`` either raises or takes the interpreter down.

    ``opened`` is the opening state RECORDED at boot time.  The opening-state
    test asserts on that record rather than on live state, so a later test
    driving the cut cannot make it pass or fail, and the two tests below do not
    depend on the order pytest happens to run them in.
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    with _counted_render() as renders:
        info = _fixture_legacy_info(
            app, tmp_path_factory.mktemp("field") / "field.npz"
        )
        # _fixture_legacy_info writes the 8080 artefact: plane_ez plus five
        # scalars, and nothing else.
        assert app.PLANE_KEY in info, (
            "the legacy fixture no longer carries plane_ez, so this is not the "
            "plane-stack page the cut sheets are gated on"
        )
        # ---- the two BOOT-level records (see the two tests below) --------
        # Both spies have to be installed BEFORE the boot, and for different
        # reasons:
        #   * `add_volume` is reached by the boot's own first picture, which
        #     goes through `handles["cut_redraw"]` (poc_app.py:8341);
        #   * the cut row's emitter is put on `ctx` as a FUNCTION OBJECT while
        #     the page builds itself (poc_app.py:9633), so a spy installed
        #     after the boot would record nothing while the row still appeared
        #     - the layout already holds the object it found at build time.
        # Both delegate to the callable they replace, so the page is unchanged;
        # both are restored as soon as the boot returns, so what each test reads
        # is exactly "what the boot did" and never a later drive.
        pyvista = pytest.importorskip("pyvista")
        real_add_volume = pyvista.Plotter.add_volume
        volume_calls = []

        def _counted_add_volume(self, *args, **kwargs):
            volume_calls.append((args, kwargs))
            return real_add_volume(self, *args, **kwargs)

        real_emit = app._emit_cut_sliders
        emit_calls = []

        def _cut_snapshot(state):
            # The state the row is handed (:7596) is the LIVE server state, and
            # a later test in the same process drives a cut handler over it, so
            # the sample the emit actually saw is snapshotted HERE, at call
            # time: read back off `args[4]` at assert time it reports whatever
            # the last driver left behind, not what the emit saw.
            snap = {}
            for name in ("cut_y", "cut_z"):
                value = getattr(state, name, None)
                snap[name] = None if value is None else int(value)
            return snap

        def _counted_emit(*args, **kwargs):
            emit_calls.append(
                {"args": args, "kwargs": kwargs, **_cut_snapshot(args[4])}
            )
            return real_emit(*args, **kwargs)

        # WHICH module carries the emitter spy is kept apart from `app`: the
        # boot REBINDS `app` to whatever `_boot_app` returns, so restoring
        # through `app` would put the real emitter back on the returned object
        # (leaving the spy on the module) and, if the boot raised, would have
        # no `app` to restore at all.
        poc_app_module = app
        pyvista.Plotter.add_volume = _counted_add_volume
        app._emit_cut_sliders = _counted_emit
        try:
            app, srv = _boot_app(info)
        finally:
            pyvista.Plotter.add_volume = real_add_volume
            poc_app_module._emit_cut_sliders = real_emit
        state, ctrl = srv.state, srv.controller

        opened = {
            # the dict this boot was handed: ``@state.change`` registrations are
            # APPENDED per boot and this process boots several pages on the same
            # Server, so the identity of ``info`` is what picks this boot's
            # listener out of ``state._change_callbacks``.
            "info": info,
            # what the boot itself drew, reported rather than asserted: that
            # number belongs to the page, not to the cuts.
            "boot_renders": len(renders),
            "has_cut_state": state.has("cut_y") and state.has("cut_z"),
            "cut_y": int(state.cut_y) if state.has("cut_y") else None,
            "cut_z": int(state.cut_z) if state.has("cut_z") else None,
            "has_station": state.has("station"),
            "station": int(state.station) if state.has("station") else None,
            "view_mode": (
                str(state.view_mode) if state.has("view_mode") else None
            ),
            "cut_label": (
                str(state.cut_label) if state.has("cut_label") else None
            ),
            "view_label": (
                str(state.view_label) if state.has("view_label") else None
            ),
            # A @ctrl.set name is a controller METHOD, not a trigger: the
            # sliders bind to these two names, so their presence is the thing
            # to record.
            "handlers": {
                name: getattr(ctrl, name, None) is not None
                for name in ("cut_y", "cut_z")
            },
            # What the BOOT drew the volume with, and the one call the cut
            # row's emitter received while the layout was built.  Both lists
            # were closed when the boot returned (the spies are taken back
            # out in the `finally` above), so these are boot records, not a
            # running log a later test could grow.
            "add_volume_calls": volume_calls,
            "emit_calls": emit_calls,
        }
        yield app, srv, renders, opened


def test_vis_cut_state_opens_on_the_middle_sample(field_page):
    """The opening cut is the middle sample of each transverse axis.

    ``_init_cut_state`` is fed ``n_j, n_k`` from the plane stack, so the page
    must open on j = 12 // 2 = 6 and k = 5 // 2 = 2 of a (9, 12, 5) field.  A
    transposed shape (n_k, n_j in the wrong slots) shows up here as cut_y = 2,
    which is why the two indices are asserted separately from their labels.

    Every assertion here reads ``opened`` - the state RECORDED at boot - not the
    live server state, so this test stands on its own.
    """
    app, srv, renders, opened = field_page

    assert opened["has_cut_state"], (
        "the plane-stack page did not initialise the cut state at all "
        f"(the boot drew {opened['boot_renders']}x)"
    )
    assert (opened["cut_y"], opened["cut_z"]) == (6, 2), (
        "the opening cut is not the middle sample of a (9, 12, 5) field: "
        f"cut_y={opened['cut_y']!r} cut_z={opened['cut_z']!r} (expected 6, 2)"
    )
    assert opened["view_mode"] == "volume", (
        "the cut state did not leave the view on the full volume: "
        f"view_mode={opened['view_mode']!r}"
    )
    # _redraw_scene reads int(state.station): without it every redraw
    # soft-fails inside its own try/except and the picture silently stops
    # following the sliders.
    assert opened["has_station"], (
        "the page has no `station`, so _redraw_scene (poc_app._redraw_scene) "
        "would raise AttributeError and never reach plotter.render() - the "
        "cuts would be dead on arrival"
    )
    assert opened["station"] == 4, (
        "the page did not settle on the middle captured plane: "
        f"station={opened['station']!r} (expected 4 of 9)"
    )

    # _cut_text carries the sample counts and the mm position of each sheet;
    # _view_label carries the axis letter and the capture count.  Both are read
    # because the row a user reads is _cut_text's and the title is _view_label's.
    cut_label = opened["cut_label"] or ""
    assert "7/12" in cut_label and "3/5" in cut_label, (
        f"the cut row does not name the sample it draws: {cut_label!r}"
    )
    assert "0.6000 mm" in cut_label and "0.2000 mm" in cut_label, (
        f"the cut row does not give the mm position of the sheet: {cut_label!r}"
    )
    view_label = opened["view_label"] or ""
    for needle in ("9 captured x-planes", "j 7/12", "k 3/5"):
        assert needle in view_label, (
            f"the view label lost {needle!r}: {view_label!r}"
        )

    # A @ctrl.set name is a controller METHOD, not a trigger: the two names must
    # resolve through the controller or the sliders have nothing to bind to.
    assert opened["handlers"] == {"cut_y": True, "cut_z": True}, (
        "the page does not expose both cut handlers, so a slider "
        f"v_model=cut_y / v_model=cut_z has nothing to call: {opened['handlers']}"
    )


#: How many ``pyvista.Plotter.render`` calls ONE cut change produces.
#:
#: ``_redraw_scene``'s own ``plotter.render()`` is only ONE of them: it calls
#: ``_draw_scene``, which re-adds every actor, and pyvista draws from inside
#: those internals - 8 from ``renderer.add_actor`` on top of the explicit
#: render.  The camera contributes NOTHING here, and that is the point: a cut
#: change rebuilds a plotter the page's BOOT already framed (``_draw_scene``
#: frames on its first build only, through its own ``_poc_camera_framed`` guard),
#: so this path never reaches
#: ``view_isometric`` (measured: 1 draw) or ``reset_camera`` (measured: 2
#: draws).  Those 3 are what the boot pays and every slider tick no longer does;
#: re-pinning this to 12 would re-pin the view snapping back under the
#: operator's hand.
#:
#: The count is asserted EXACTLY, not as ``>= 1``: fewer means ``_redraw_scene``
#: soft-failed (it swallows its exception, leaving the label already moved),
#: more means the scene was built twice.  Both handlers are measured against
#: this one constant, so they must produce the same delta.
#:
#: The number stays EXACT on purpose: a silent extra redraw (one more actor, a
#: camera that went back to re-framing) is real work on every slider tick and
#: must fail here rather than be absorbed, so never relax it to ``>= 1``.
_CUT_REDRAW_RENDERS = 9


def test_vis_cut_change_moves_the_cut_and_redraws(field_page):
    """Driving either cut handler clamps, stores, relabels and redraws.

    The handler is called the way trame calls it - positional value, no kwargs -
    and the render counter is the proof that the scene was really rebuilt rather
    than the label alone being rewritten.  The counter comes from the fixture,
    which is why the expected delta is exact: this process has booted the page
    once.  What the number is made of is in ``_CUT_REDRAW_RENDERS``.
    """
    app, srv, renders, opened = field_page
    state, ctrl = srv.state, srv.controller
    # Both cut sliders are bound with @state.change - cut_y at :16190, cut_z
    # at :16211 - so the browser's event for either is a WRITE to the key the
    # flush then dispatches to the registered listener.  The listener is
    # called DIRECTLY, the way the loop test does (:694) and for the same
    # reason: this harness never marks the state ready, so ``state.flush()``
    # returns without dispatching (state.py:461-462) and a flush-based drive
    # would pass for the wrong reason - it measured 0 renders, not 9.  Both are
    # driven the way the client drives them - the write committed to state
    # first, then the listener - so the two render counts stay comparable.
    entries = [
        entry
        for entry in (state._change_callbacks.get("cut_y") or [])
        if _closure_cells(entry[0]).get("info") is opened["info"]
    ]
    assert len(entries) == 1, (
        f"{len(entries)} 'cut_y' listeners were registered by this page's boot; "
        "expected exactly 1"
    )
    cut_y_listener = entries[0][0]

    def cut_y(value):
        state.cut_y = value          # the client's write, as trame commits it
        cut_y_listener(cut_y=value)  # what the flush calls (state.py:429-447)

    z_entries = [
        entry
        for entry in (state._change_callbacks.get("cut_z") or [])
        if _closure_cells(entry[0]).get("info") is opened["info"]
    ]
    assert len(z_entries) == 1, (
        f"{len(z_entries)} 'cut_z' listeners were registered by this page's "
        "boot; expected exactly 1"
    )
    cut_z_listener = z_entries[0][0]

    def cut_z(value):
        state.cut_z = value          # the client's write, as trame commits it
        cut_z_listener(cut_z=value)  # what the flush calls (state.py:429-447)

    before = len(renders)
    cut_y(9)
    assert int(state.cut_y) == 9, (
        f"cut_y(9) left the cut at {state.cut_y!r}; the handler is not storing "
        "the value the slider sends"
    )
    assert len(renders) - before == _CUT_REDRAW_RENDERS, (
        f"cut_y(9) rebuilt the scene {len(renders) - before} times (expected "
        f"exactly {_CUT_REDRAW_RENDERS}): _redraw_scene soft-fails silently, so "
        "0 here means the cut is dead even though the label moved"
    )
    assert int(state.cut_z) == 2, (
        f"moving the y cut moved the z cut too: cut_z={state.cut_z!r}"
    )
    assert "10/12" in state.cut_label and "0.9000 mm" in state.cut_label, (
        f"the cut row did not follow the y cut: {state.cut_label!r}"
    )
    assert "j 10/12" in str(state.view_label), (
        f"the view label did not follow the y cut: {state.view_label!r}"
    )

    before = len(renders)
    cut_z(4)
    assert int(state.cut_z) == 4, f"cut_z(4) left the cut at {state.cut_z!r}"
    assert len(renders) - before == _CUT_REDRAW_RENDERS, (
        f"cut_z(4) rebuilt the scene {len(renders) - before} times (expected "
        f"exactly {_CUT_REDRAW_RENDERS}, the count cut_y(9) produced: both "
        "handlers must take the same redraw path)"
    )
    assert int(state.cut_y) == 9, (
        f"moving the z cut reset the y cut: cut_y={state.cut_y!r}"
    )
    assert "11/12" not in state.cut_label and "5/5" in state.cut_label, (
        f"the cut row did not follow the z cut: {state.cut_label!r}"
    )

    # The clamp is the handler's, not the slider's: a client may send a value
    # outside the sample range (a stale layout, a typed number).
    cut_y(999)
    assert int(state.cut_y) == 11, (
        "an out-of-range y cut was not clamped to n_j - 1 = 11: "
        f"cut_y={state.cut_y!r}"
    )
    cut_z(-5)
    assert int(state.cut_z) == 0, (
        f"a negative z cut was not clamped to 0: cut_z={state.cut_z!r}"
    )
    cut_y("junk")
    assert int(state.cut_y) == 11, (
        "an unparsable cut value did not fall back to the current one: "
        f"cut_y={state.cut_y!r}"
    )


# =============================================================================
# The cut row on the BOOTED page: what the boot drew, and what it emitted
# =============================================================================
# The tests above pin the cut MACHINERY on a page the fixture built once.  The
# two below read that same boot from the other end: what the boot put on screen
# (a volume to cut into) and what it asked the layout to emit (the row itself).
# Both records come from spies the fixture installs around `_boot_app` only, so
# each count is what the BOOT did and not a running log.


def test_booted_field_page_draws_the_volume_with_ez_abs(field_page):
    """If this fails, the plane-stack page opens on a picture with no volume.

    The boot's first picture goes through ``handles["cut_redraw"]``
    (poc_app.py:8341), and ``_draw_scene`` adds the volume only on its volume
    branch (poc_app.py:3863) - the port branch adds one station's mesh instead
    and no volume at all.  So an ``add_volume`` call during the boot is the
    proof that the two cut sheets are drawn into a real volume rather than into
    an empty plotter, which is the one thing the render counters above cannot
    tell apart.  ``ez_abs`` is the scalar ``build_grid`` publishes (:3698) and
    the one ``create_plotter`` asks for (:3717); a volume added with any other
    scalar comes out uncoloured and no count would notice.
    """
    _app, _srv, _renders, opened = field_page
    calls = opened["add_volume_calls"]
    assert calls, (
        "the plane-stack page's boot never called add_volume, so the picture it "
        "opens on has no volume for the cut sheets to sit in"
    )
    scalars = [kwargs.get("scalars") for _args, kwargs in calls]
    assert "ez_abs" in scalars, (
        "the booted page added its volume with "
        f"{scalars!r}, not with the grid's own 'ez_abs'"
    )


def test_booted_field_page_emits_the_cut_row_once(field_page):
    """If this fails, the booted plane-stack page draws no cut sliders.

    The row is emitted from the LAYOUT build (server/um3k_panels.py:58-74)
    through the emitter poc_app published on `ctx` while it built itself, and
    that publish hands over the FUNCTION OBJECT (:9633) - which is why the spy
    has to predate the boot: patched afterwards it records 0 calls while the
    row still appears on the page.

    This is the only place the REAL page's arguments exist, so all of them are
    pinned here: the placeholder is ``None`` (the centre column has no
    placeholder div and relies on its own ``html_div``), the two bounds are the
    stack's own ``(n_j, n_k) = (12, 5)`` from ``ctx.handle("cut_shape")``
    (:7630), and the state handed over is the server's own object, already on
    the middle sample because ``_init_cut_state`` ran before the build (:7596).
    A stand-in state would make the sliders bind to nothing.
    """
    _app, srv, _renders, opened = field_page
    calls = opened["emit_calls"]
    assert len(calls) == 1, (
        f"the booted page emitted the cut row {len(calls)} time(s); the layout "
        "builds it once, so 0 means the centre column never reached the row and "
        ">1 means a second emitter was installed over the first"
    )
    record = calls[0]
    args = record["args"]
    assert args[1] is None, (
        "the cut row was emitted with "
        f"{args[1]!r} as the placeholder; the centre column has no placeholder "
        "div and passes None"
    )
    assert (args[5], args[6]) == (12, 5), (
        "the cut row was emitted with bounds "
        f"{(args[5], args[6])!r} instead of the stack's (n_j, n_k) = (12, 5), so "
        "a slider would span the wrong number of samples"
    )
    assert args[4] is srv.state, (
        f"the cut row was emitted with {args[4]!r} instead of the page's own "
        "state, so the sliders would bind to a copy nothing writes to"
    )
    # The sample comes from the SNAPSHOT the spy took at emit time, never off
    # `args[4]`: that is the live state, and a test driving a cut handler
    # (test_vis_cut_change_moves_the_cut_and_redraws, earlier in this file)
    # leaves it on 11, so a late read would report the drive, not the emit.
    assert record["cut_y"] == 6, (
        "the cut row was emitted while the page was on cut_y="
        f"{record['cut_y']!r}; _init_cut_state runs before the layout is built, "
        "so the first slider must be drawn on the middle sample"
    )


# =============================================================================
# The cut row's EMITTER: the two sliders, and the label-only fallbacks
# =============================================================================
# ``_emit_cut_sliders`` is the function the centre column calls for a
# plane-stack page (server/um3k_panels.py, build_center_panel).  It is a plain
# function over a widget TABLE and one div factory, so it is tested directly:
# recording callables stand in for the Vuetify classes, and nothing is booted,
# laid out or rendered - the arguments it passes ARE the whole contract of the
# row.  Both fallbacks matter: a plane stack can be captured on a page whose
# widget probe came up short, and the layout that calls it has no placeholder
# div at all (it passes ``None`` and relies on its own ``html_div``).


def _cut_slider_fakes():
    """Recording ``VLabel``/``VSlider`` factories plus a recording div.

    ``widgets`` maps a widget NAME to a callable because that is what the emitter
    is handed: it resolves ``widgets["VSlider"]`` rather than importing the
    class, which is what makes a plain dict a valid stand-in.  Every widget call
    lands in ``calls`` as ``(name, args, kwargs)`` in build order, so one
    assertion can pin the row's order AND each slider's arguments.
    """
    calls = []
    widgets = {}

    def _record(name):
        def _call(*args, **kwargs):
            calls.append((name, args, kwargs))
        return _call

    for name in ("VLabel", "VSlider"):
        widgets[name] = _record(name)

    divs = []

    def div_recorder(*args, **kwargs):
        divs.append((args, kwargs))

    return widgets, calls, div_recorder, divs


def test_emit_cut_sliders_builds_two_sliders_between_their_labels():
    """If this fails, the two cut sliders are not bound to the page's cut axes.

    The row is ``y cut`` / the y slider / ``z cut`` / the z slider / the caption,
    and each slider carries the sample range the page opened on: ``n_j - 1`` and
    ``n_k - 1`` bounded at 0, one sample per step, bound to ``cut_y`` / ``cut_z``
    at the state the page is holding.  A transposed ``(n_j, n_k)`` shows up as the
    two ``max`` values swapping; a slider that lost its ``v_model`` would move
    nothing when dragged.
    """
    import poc_app as app

    widgets, calls, div_recorder, divs = _cut_slider_fakes()

    app._emit_cut_sliders(
        [], None, div_recorder, widgets, SimpleNamespace(cut_y=6, cut_z=2), 12, 5
    )

    assert [name for name, _args, _kwargs in calls] == [
        "VLabel",
        "VSlider",
        "VLabel",
        "VSlider",
        "VLabel",
    ], f"the cut row built {[name for name, _a, _k in calls]!r}"
    assert calls[0][1] == ("y cut",), f"the y label says {calls[0][1]!r}"
    assert calls[2][1] == ("z cut",), f"the z label says {calls[2][1]!r}"
    assert calls[-1][1] == ("{{ cut_label }}",), (
        f"the row does not end on the caption: {calls[-1][1]!r}"
    )

    y_kwargs = calls[1][2]
    assert y_kwargs["v_model"] == ("cut_y", 6), (
        f"the y slider is bound to {y_kwargs['v_model']!r}, not the live cut"
    )
    assert (y_kwargs["min"], y_kwargs["max"], y_kwargs["step"]) == (0, 11, 1), (
        "the y slider does not span n_j = 12 samples one at a time: "
        f"min={y_kwargs['min']!r} max={y_kwargs['max']!r} "
        f"step={y_kwargs['step']!r}"
    )

    z_kwargs = calls[3][2]
    assert z_kwargs["v_model"] == ("cut_z", 2), (
        f"the z slider is bound to {z_kwargs['v_model']!r}, not the live cut"
    )
    assert (z_kwargs["min"], z_kwargs["max"], z_kwargs["step"]) == (0, 4, 1), (
        "the z slider does not span n_k = 5 samples one at a time: "
        f"min={z_kwargs['min']!r} max={z_kwargs['max']!r} "
        f"step={z_kwargs['step']!r}"
    )

    assert divs == [], (
        f"a complete row still drew the label-only fallback: {divs!r}"
    )


def test_emit_cut_sliders_labels_the_row_when_the_sliders_are_missing():
    """If this fails, a plane-stack layout with no placeholder div draws nothing.

    This is the case chunk B creates: ``build_center_panel`` has no placeholder
    div and passes ``None``, so the caption has to go through the row's own
    ``html_div``.  A page whose probe found no ``VSlider`` must still say where
    the cut is, and the absent widgets must not be built at all.
    """
    import poc_app as app

    widgets, calls, div_recorder, divs = _cut_slider_fakes()

    app._emit_cut_sliders(
        ["VSlider"],
        None,
        div_recorder,
        widgets,
        SimpleNamespace(cut_y=6, cut_z=2),
        12,
        5,
    )

    assert divs == [(("{{ cut_label }}",), {})], (
        "the row's own div did not receive the caption: "
        f"{divs!r}"
    )
    assert calls == [], (
        f"a widget the page does not have was built anyway: {calls!r}"
    )


def test_emit_cut_sliders_prefers_a_real_placeholder_over_the_row_div():
    """If this fails, the None-tolerance above proves nothing.

    The two fallbacks are exclusive: a page that HAS a placeholder div (the vis
    page does) gets the caption there and the row's div is not touched.  Without
    this half, an emitter that always called ``html_div`` would pass the previous
    test while painting the caption into the wrong container.
    """
    import poc_app as app

    widgets, calls, div_recorder, divs = _cut_slider_fakes()
    placeholders = []

    def placeholder(*args, **kwargs):
        placeholders.append((args, kwargs))

    app._emit_cut_sliders(
        ["VSlider"],
        placeholder,
        div_recorder,
        widgets,
        SimpleNamespace(cut_y=6, cut_z=2),
        12,
        5,
    )

    assert placeholders == [(("{{ cut_label }}",), {})], (
        f"the placeholder div did not receive the caption: {placeholders!r}"
    )
    assert divs == [], (
        "the row's div was used even though the page has a placeholder: "
        f"{divs!r}"
    )
    assert calls == [], (
        f"a widget the page does not have was built anyway: {calls!r}"
    )


#: The child interpreter for the no-plane-stack test, below.
#:
#: It boots the page in a VIRGIN process.  In the parent, ``get_server()`` has
#: already been handed the field page by the fixture above, so the parent cannot
#: ask "does a page with no plane stack get a cut?" - the answer would be about
#: the leaked server, not about this page.  ``TESTS_DIR`` is substituted with
#: this file's directory by the test; the child puts the repo root and
#: ``server/`` on ``sys.path`` itself (this file's module-level block, which it
#: imports for that reason, does the same for the parent at :21-40).
_ABSENCE_CHILD = """
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, TESTS_DIR)

# ``poc_app`` lives in the repo's server/ directory and is on no default path:
# importing this test module is what puts it there (tests/test_poc_playback.py:
# 21-40), so import that FIRST and add the two paths explicitly - a child that
# opens with ``import poc_app`` dies with ModuleNotFoundError.
import test_poc_playback as tp
sys.path.insert(0, str(Path(TESTS_DIR).parent))
sys.path.insert(0, str(Path(TESTS_DIR).parent / "server"))

import pyvista

import poc_app as app

renders = []
real_render = pyvista.Plotter.render
# The child's boot draws too, and this image has no OpenGL: double it for the
# whole child, then report how often the page drew.
pyvista.Plotter.render = lambda self, *a, **k: renders.append(1)

# The cut row's emitter, spied for the same reason and BEFORE the boot: the
# page publishes the FUNCTION OBJECT on `ctx` while it builds itself
# (poc_app.py:9633), so a spy installed after the boot would report 0 calls even
# if the row had been emitted. It delegates, so a page that does emit the row
# still gets its row - and the count, not the picture, is what this child
# reports.
real_emit = app._emit_cut_sliders
emit_calls = []


def _counted_emit(*args, **kwargs):
    emit_calls.append(1)
    return real_emit(*args, **kwargs)


app._emit_cut_sliders = _counted_emit
try:
    info = tp._fixture_info(app, Path(tempfile.mkdtemp()) / "vis.npz")
    if app.PLANE_KEY in info:
        raise SystemExit("the vis fixture carries plane_ez: wrong page")
    _app, srv = tp._boot_app(info)
    state, ctrl = srv.state, srv.controller

    def has_handler(name):
        # Controller.__getattr__ fabricates a ControllerFunction proxy for ANY
        # name, registered or not (trame_server/controller.py), so "the
        # attribute is not None" is a tautology that every controller passes.
        # ControllerFunction.exists() is the real question: is there a function
        # behind the proxy?
        proxy = getattr(ctrl, name, None)
        return bool(proxy is not None and proxy.exists())

    verdict = {
        "state_keys": {
            key: state.has(key) for key in ("cut_y", "cut_z", "cut_label")
        },
        "handlers": {name: has_handler(name) for name in ("cut_y", "cut_z")},
        "emit_calls": len(emit_calls),
        "renders": len(renders),
    }
    print("VERDICT " + json.dumps(verdict))
finally:
    pyvista.Plotter.render = real_render
    app._emit_cut_sliders = real_emit
"""


def test_vis_page_without_a_plane_stack_has_no_cut():
    """The vis dump has no plane stack, so it gets no cut state and no handlers.

    The gate is ``ctx.available.plane_stack``: a page that cannot draw the
    volume must not expose sliders that would move a sheet that is not there,
    and must not read ``info["plane_ez"]`` - that KeyError takes the whole boot
    down, not just the cut.

    This runs in a CHILD interpreter: ``trame.app.get_server()`` is a
    process-wide singleton, and in this process the field page above already
    owns that server.  A crash, a non-zero exit or a missing verdict FAILS the
    test; nothing about the child is allowed to pass by silence.
    """
    import subprocess

    script = _ABSENCE_CHILD.replace(
        "TESTS_DIR", repr(str(Path(__file__).resolve().parent))
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, (
        "the child that boots the no-plane-stack page failed, so there is no "
        "evidence this page is free of the cut machinery:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("VERDICT ")]
    assert len(lines) == 1, (
        f"the child printed {len(lines)} verdict line(s), expected exactly 1 - "
        "without it this test would assert nothing:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    verdict = json.loads(lines[0][len("VERDICT "):])

    assert verdict["state_keys"] == {
        "cut_y": False, "cut_z": False, "cut_label": False
    }, (
        "a page with no plane stack still exposes cut state, so the cut is not "
        f"gated on ctx.available.plane_stack: {verdict['state_keys']}"
    )
    assert verdict["handlers"] == {"cut_y": False, "cut_z": False}, (
        "a page with no plane stack still registers a cut controller method, so "
        "a slider would call into a redraw of a scene that does not exist: "
        f"{verdict['handlers']}"
    )
    assert verdict["emit_calls"] == 0, (
        "a page with no plane stack still emitted the cut row, so the layout "
        "would draw two sliders over a sheet that is not there: "
        f"{verdict['emit_calls']} call(s)"
    )
    # The boot's own draw count is REPORTED here, never asserted as zero: this
    # page draws a few times while it builds and that number is not the subject -
    # a cut handler firing during the boot would be, and the three records above
    # are what would catch it.  What is asserted is that the verdict is a REAL
    # verdict: exactly the four records the child builds, no more, so a child
    # that printed a hand-written line instead of running the boot cannot pass.
    assert sorted(verdict) == [
        "emit_calls", "handlers", "renders", "state_keys"
    ], (
        "the child's verdict does not carry the records it is supposed to build: "
        f"{sorted(verdict)}"
    )



#: The child interpreter for the one-plane test, below.
#:
#: It boots the page in a VIRGIN process for the same reason
#: ``_ABSENCE_CHILD`` does: ``trame.app.get_server()`` is a process-wide
#: singleton.  What it REPORTS is what the boot actually did - the state keys the
#: shared redraw reads, and the ``_draw_scene`` calls the boot produced - because
#: ``handles["cut_redraw"]`` is a local of ``run_web_vis`` and cannot be read from
#: outside; a draw call carrying station_label=False IS that handle being found
#: and invoked.  ``TESTS_DIR`` is substituted by the test.
_ONE_PLANE_CHILD = """
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, TESTS_DIR)

# Importing this module is what puts the repo root and ``server/`` on sys.path,
# so it comes FIRST; a child that opens with ``import poc_app`` dies with
# ModuleNotFoundError.
import test_poc_playback as tp
sys.path.insert(0, str(Path(TESTS_DIR).parent))
sys.path.insert(0, str(Path(TESTS_DIR).parent / "server"))

import pyvista

import poc_app as app

# This image has no OpenGL: double the render call for the whole child.
pyvista.Plotter.render = lambda self, *a, **k: None

draws = []
real_draw = app._draw_scene


def spy_draw(plotter, info, planes, view_mode, station, j_cut=None, k_cut=None,
             station_label=True):
    # Records the SCENE call only, and delegates: a redraw that raises still
    # raises (and is still swallowed) exactly where the shipped code swallows it.
    draws.append([view_mode, station, j_cut, k_cut, station_label])
    return real_draw(
        plotter, info, planes, view_mode, station,
        j_cut=j_cut, k_cut=k_cut, station_label=station_label,
    )


app._draw_scene = spy_draw
try:
    info = tp._fixture_one_plane_info(app, Path(tempfile.mkdtemp()) / "one.npz")
    stations = int(info[app.PLANE_KEY].shape[0])
    if stations != 1:
        raise SystemExit("the one-plane fixture is not one station")
    _app, srv = tp._boot_app(info)
    state = srv.state
    keys = ("station", "cut_y", "cut_z", "view_mode", "station_readout")
    verdict = {
        "stations": stations,
        "state_keys": {key: state.has(key) for key in keys},
        "values": {key: state[key] for key in keys if state.has(key)},
        "draws": draws,
    }
    print("VERDICT " + json.dumps(verdict))
finally:
    app._draw_scene = real_draw
"""


def test_a_page_with_one_captured_plane_draws_its_picture_and_publishes_its_cut_state():
    """One captured x-plane: not a stack, but still a picture on screen.

    ``plane_stack`` is ``stations > 1`` and ``port_planes`` is ``stations > 0``,
    so a one-station dump used to take NEITHER branch of the boot: no ``planes``,
    no state for the shared redraw to read, no ``handles["cut_redraw"]`` - and
    the browser showed an empty view with no error, because ``_redraw_scene``
    catches its own exceptions.  The fix is a ``port_planes`` branch: the same
    draw path, minus the sliders it cannot have.

    Run in a CHILD interpreter, like the no-plane-stack test above, because
    ``trame.app.get_server()`` is a process-wide singleton this process has
    already handed to another page.  A crash, a non-zero exit or a missing
    verdict FAILS the test.
    """
    import subprocess

    script = _ONE_PLANE_CHILD.replace(
        "TESTS_DIR", repr(str(Path(__file__).resolve().parent))
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, (
        "the child that boots the one-plane page failed, so there is no "
        "evidence the fallback drew anything:\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("VERDICT ")]
    assert len(lines) == 1, (
        f"the child printed {len(lines)} verdict line(s), expected exactly 1 - "
        f"without it this test would assert nothing:\nstdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )
    verdict = json.loads(lines[0][len("VERDICT "):])
    assert verdict["stations"] == 1, (
        "the fixture is no longer the one-plane page this test is about: "
        f"{verdict}"
    )

    # What was MISSING before: every field the shared redraw reads.  Without
    # them _redraw_scene raises AttributeError into the silent blank picture.
    assert verdict["state_keys"] == {
        "station": True,
        "cut_y": True,
        "cut_z": True,
        "view_mode": True,
        "station_readout": False,
    }, (
        "a one-plane page does not publish exactly the state its redraw reads "
        f"(station_readout must stay absent: nothing renders that line here): "
        f"{verdict['state_keys']}"
    )
    # station 0 is the only captured plane; 6 = 12 // 2 and 2 = 5 // 2 are the
    # middle samples of the two transverse axes.
    assert verdict["values"] == {
        "station": 0,
        "cut_y": 6,
        "cut_z": 2,
        "view_mode": "volume",
    }, (
        "the one-plane page opened on the wrong cut: expected the single "
        f"captured station and the middle of each transverse axis, got "
        f"{verdict['values']}"
    )

    # The redraw HANDLE, observed where it is observable: the boot found
    # cut_redraw and drove it, and that draw reached the scene with the state
    # asserted above and with the page's own station_label=False.
    assert verdict["draws"] == [["volume", 0, 6, 2, False]], (
        "the boot did not draw the one-plane picture exactly once, through the "
        f"shared redraw, in the volume view: {verdict['draws']}"
    )
    assert "redraw skipped" not in proc.stderr, (
        "the page has a redraw handle now but the redraw FAILED, so the picture "
        f"is still blank for a second reason:\n{proc.stderr}"
    )
    # Not "no warnings": a bare legacy dump legitimately says plane ez_ycut and
    # friends were not drawn. What must NOT be there is an exception escaping the
    # boot - that would be a blank picture with a crash instead of a blank
    # picture with a missing handle.
    assert "Traceback" not in proc.stderr, (
        "the one-plane page raised while drawing, so the picture is not the "
        f"picture this test is about:\n{proc.stderr}"
    )


class _MarkerPlotter:
    """A plotter that RECORDS the marker layer and draws nothing.

    Doubled, not simulated: ``pv.Plane`` is the real pyvista construction (a
    plain ``PolyData``, no render window), and only ``add_mesh`` /
    ``add_point_labels`` - the boundaries that reach VTK's pipeline - are
    replaced.  This image has no EGL, no libOSMesa and no X server, so a real
    plotter would segfault before the first assertion.
    """

    def __init__(self) -> None:
        self.meshes: list = []
        self.labels: list = []

    def add_mesh(self, mesh, **kwargs):
        self.meshes.append((mesh, kwargs))
        return None

    def add_point_labels(self, points, labels, **kwargs):
        self.labels.append((list(points), list(labels), kwargs))
        return None


def _marker_draw(app, info, planes, **switches):
    """``_add_markers`` once, into a recording plotter.

    The switches ride INSIDE the mapping, which is how the source carries them:
    ``_add_markers`` keeps its three-argument signature and reads
    ``planes.get("show_load_plane", True)``, so a caller that wants a disc hidden
    folds the flag in rather than passing another argument.
    """
    plotter = _MarkerPlotter()
    app._add_markers(plotter, info, dict(planes, **switches))
    return plotter


def test_the_s11_port_plane_is_drawn_parallel_to_the_load_plane() -> None:
    """The purple S11 disc: same construction, same y/z, its own x - and its own
    switch.

    The point of the layer is a POSITION in space, so the assertions are the
    three numbers a reader needs: where each disc sits on x, that they share the
    y/z mid-plane and the grid's own spans (two parallel slices of one pair, not
    two differently-shaped markers), and that hiding one leaves the other - and
    the labels that place both - alone.
    """
    import poc_app as app

    info = {app.PLANE_KEY: np.zeros((2, 3, 4)), "cell_m": 1e-4}
    planes = app._plane_layout(info, None)
    # Both boxes are ON at boot: the default call is every page's picture.  The
    # layout itself carries no switches - they are folded in by the redraw - and
    # a state that predates them still asks for both discs.
    assert "show_load_plane" not in planes
    assert "show_port_plane" not in planes
    absent = app._scene_planes(planes, SimpleNamespace())
    assert (absent["show_load_plane"], absent["show_port_plane"]) == (True, True)

    both = _marker_draw(app, info, planes)
    assert [kwargs["color"] for _mesh, kwargs in both.meshes] == ["red", "purple"], (
        "the S11 port plane is not drawn, is not purple, or is drawn in some "
        f"other order: {[kwargs['color'] for _mesh, kwargs in both.meshes]}"
    )
    (red, red_kwargs), (purple, purple_kwargs) = both.meshes
    # REPLACED (was: ``opacity == 0.25`` on both): the two markers are drawn as
    # the EDGE of their rectangle, not as a 25 % sheet. WHY: a filled sheet the
    # size of the slab's y/z cross-section laid an opaque-ish lid across the
    # translucent |E| volume the layer exists to point at, so an edge occludes
    # nothing. An opacity keyword here would mean the lid came back.
    for kwargs in (red_kwargs, purple_kwargs):
        assert "opacity" not in kwargs, (
            f"a marker was drawn with an opacity, so it is a sheet again: {kwargs}"
        )
        assert kwargs.get("line_width") == 2, (
            f"the marker edge is not drawn at line width 2: {kwargs}"
        )
    # The rectangle itself did not move: the edge mesh keeps the plane's own
    # bounds and centre, and every cell in it is a line (a face would occlude).
    for mesh in (red, purple):
        assert mesh.n_cells > 0, "the marker edge mesh is empty"
        assert mesh.n_lines == mesh.n_cells, (
            f"{mesh.n_cells - mesh.n_lines} non-line cell(s): a fill came back"
        )
        assert int(mesh.n_faces) == 0, (
            f"the marker still has {int(mesh.n_faces)} face(s) to occlude with"
        )

    assert red.center[0] == pytest.approx(planes["x_load_mm"])
    assert purple.center[0] == pytest.approx(planes["x_s11_mm"])
    # Parallel and concentric: same y/z centre, same two spans.
    assert purple.center[1:] == pytest.approx(red.center[1:])
    y_span, z_span = red.bounds[3] - red.bounds[2], red.bounds[5] - red.bounds[4]
    assert purple.bounds[3] - purple.bounds[2] == pytest.approx(y_span)
    assert purple.bounds[5] - purple.bounds[4] == pytest.approx(z_span)
    # WHICH of the two grid spans each plane axis gets is pyvista's own business
    # (with an x direction it maps i/j onto y/z in its order, and the red disc
    # has always been built that way), so what is asserted is the pair: both
    # discs carry the grid's own two spans, unchanged by the second disc.
    cell_mm = planes["cell_mm"]
    # WHY the -1: n samples span n - 1 cells (build_grid points at i*cell), so
    # the markers read (shape - 1) * cell, not shape * cell.
    grid_spans = sorted(
        [
            (info[app.PLANE_KEY].shape[1] - 1) * cell_mm,
            (info[app.PLANE_KEY].shape[2] - 1) * cell_mm,
        ]
    )
    assert sorted([y_span, z_span]) == pytest.approx(grid_spans)

    # The labels are the legend of where the planes are, so they are drawn with
    # either disc hidden - and they are the same three sentences as before.
    assert len(both.labels) == 1
    _points, labels, _kwargs = both.labels[0]
    assert len(labels) == 3
    assert labels[0].startswith("S11 port plane - purple"), (
        f"the S11 label does not name its disc's colour: {labels[0]!r}"
    )
    assert labels[1].startswith("load (termination) - red"), (
        f"the load label does not name its disc's colour: {labels[1]!r}"
    )
    assert f"x = {planes['x_s11_mm']:.4f} mm" in labels[0], (
        f"the S11 label does not carry the mm position: {labels[0]!r}"
    )
    assert f"x = {planes['x_load_mm']:.4f} mm" in labels[1], (
        f"the load label does not carry the mm position: {labels[1]!r}"
    )

    only_load = _marker_draw(app, info, planes, show_port_plane=False)
    assert [kwargs["color"] for _mesh, kwargs in only_load.meshes] == ["red"]
    assert len(only_load.labels[0][1]) == 3

    only_port = _marker_draw(app, info, planes, show_load_plane=False)
    assert [kwargs["color"] for _mesh, kwargs in only_port.meshes] == ["purple"]
    assert len(only_port.labels[0][1]) == 3


def test_the_marker_legend_names_each_discs_colour(tmp_path: Path,
                                                   monkeypatch) -> None:
    """A disc is a translucent sheet; its COLOUR is what tells the two apart, so
    the legend - and the two boxes that show or hide them - have to name it.

    The label and the disc are asserted AGAINST EACH OTHER: the sentence at the
    red load disc says "red", the one at the purple S11 disc says "purple".  A
    hardcoded pair of strings would satisfy the wording assertions while being
    swapped, which is exactly what nobody would notice on screen.
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    info = {app.PLANE_KEY: np.zeros((2, 3, 4)), "cell_m": 1e-4}
    planes = app._plane_layout(info, None)
    drawn = _marker_draw(app, info, planes)
    (_, load_kwargs), (_, port_kwargs) = drawn.meshes
    assert (load_kwargs["color"], port_kwargs["color"]) == ("red", "purple"), (
        "the discs are no longer red (load) then purple (S11 port), so the "
        "colour words below are not the ones on screen: "
        f"{[kwargs['color'] for _mesh, kwargs in drawn.meshes]}"
    )
    _points, labels, _kwargs = drawn.labels[0]
    assert "red" in labels[1], (
        f"the label at the red load disc does not name its colour: {labels[1]!r}"
    )
    assert "purple" in labels[0], (
        f"the label at the purple S11 disc does not name its colour: {labels[0]!r}"
    )
    assert "purple" not in labels[1] and "red" not in labels[0], (
        "the two colour words are on the wrong discs: "
        f"S11={labels[0]!r}, load={labels[1]!r}"
    )
    # Still a position as well as a colour: the mm value is the other half.
    assert f"{planes['x_s11_mm']:.4f} mm" in labels[0], (
        f"the S11 label lost its mm position: {labels[0]!r}"
    )
    assert f"{planes['x_load_mm']:.4f} mm" in labels[1], (
        f"the load label lost its mm position: {labels[1]!r}"
    )

    # The boxes that show and hide those discs are the other half of the legend.
    # They are built BY THE PAGE, so they are read back from a boot - and from
    # the PLANE-STACK boot: the two plane boxes are emitted only where a redraw
    # is bound (poc_app.py:10038-10039), so a page with no plane stack never
    # builds them.  pyvista's own plotter toolbar adds label-less boxes of its
    # own on every boot, so the recorder is filtered by label, not indexed.
    recorded = _capture_v_checkboxes(monkeypatch)
    pyvista = pytest.importorskip("pyvista")
    real_render = pyvista.Plotter.render
    pyvista.Plotter.render = lambda self, *a, **k: None  # no OpenGL in this image
    try:
        _boot_app(_fixture_legacy_info(app, tmp_path / "legend.npz"))
    finally:
        pyvista.Plotter.render = real_render
    # Each label is pinned TOGETHER with the state flag it drives: two boxes
    # that say the right words while switching the other disc - or one flag
    # twice - would be the same swapped pair as the sentences above.
    boxes = {}
    for entry in recorded:
        label = entry["kwargs"].get("label")
        v_model = entry["kwargs"].get("v_model")
        if label and isinstance(v_model, tuple) and v_model:
            boxes[label] = v_model[0]
    assert boxes.get("Show Load Plane (red)") == "show_load_plane", (
        "no plane box names the red load disc and switches its flag: "
        f"{sorted(boxes.items())}"
    )
    assert boxes.get("Show S11 Port Plane (purple)") == "show_port_plane", (
        "no plane box names the purple S11 port disc and switches its flag: "
        f"{sorted(boxes.items())}"
    )


# =============================================================================
# WHICH PAGE: the source line, and what a static page does with a Solve press
# =============================================================================
# Every other readout on this page says which ARM and which COLOUR LIMIT are on
# screen; none of them says which FILE, so a copy of a dump and the dump a solve
# replaced on disk read exactly like the original. ``state.page_source_text`` is
# that missing line, and its sentence differs between the two kinds of page the
# shell serves - so it is pinned on both.
#
# NOTE on the shared Server: ``trame.app.get_server()`` is a process-wide
# singleton, so ``state`` has already been written by earlier boots in this
# process. That is why every assertion below compares the WHOLE string rather
# than asking whether the key exists - a stale line from a previous boot cannot
# satisfy these by accident.


def test_a_static_page_names_its_dump_and_says_it_has_no_timeline(
    tmp_path: Path,
) -> None:
    """The 8080 artefact says WHICH file it is, that it is static, and its count.

    ``_fixture_legacy_info`` writes plane_ez with nine stations and no frame axis
    at all, so the expected sentence names all three facts: the file the page was
    loaded from, the kind of page, and the station count the plane stack carries.
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    info = _fixture_legacy_info(app, tmp_path / "field_A.npz")
    with _counted_render():
        _app, srv = _boot_app(info)
    state = srv.state

    assert state.has("page_source_text"), (
        "the static page publishes no source line at all, so nothing on it says "
        "which dump is on screen: the provenance block in run_web_vis never "
        "reached the assignment"
    )
    assert str(state.page_source_text) == (
        "showing field_A.npz - static field snapshot, 9 stations, no timeline"
    ), (
        "the static page does not name its own dump, its kind and its station "
        f"count: {str(state.page_source_text)!r}"
    )


def test_an_animation_page_names_its_dump_and_its_frame_count(
    tmp_path: Path,
) -> None:
    """The animation page's same line, in the animation words: nt frames on ycut.

    ``_fixture_info`` writes nt = 4, so the sentence has to carry that number and
    the sweep axis - a static page's wording here would mean the line is not
    reading the page it is drawn on.
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    info = _fixture_info(
        app, tmp_path / "anim_A.npz", structure_id="A", load_ohm=50.0
    )
    with _counted_render():
        _app, srv = _boot_app(info)
    state = srv.state

    assert state.has("page_source_text"), (
        "the animation page publishes no source line: the same provenance block "
        "serves both kinds of page, so this is the vis path's own miss"
    )
    assert str(state.page_source_text) == (
        "showing anim_A.npz - animation, 4 frames on ez_ycut"
    ), (
        "the animation page does not name its own dump, its kind and its frame "
        f"count: {str(state.page_source_text)!r}"
    )


def test_a_static_page_refuses_a_solve_and_spawns_nothing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A Solve press on a static page is REFUSED before any child or file exists.

    The button is greyed out, but a press can still arrive - a stale browser tab,
    or a caller driving the registered trigger - and the page has no timeline for
    a new run to land in. ``SolveJob`` is replaced by a recorder that raises if it
    is ever constructed, and ``LIVE_DUMP`` is pointed at a path under ``tmp_path``,
    so the two things a press must not do are both observable: no child, no dump.
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    info = _fixture_legacy_info(app, tmp_path / "static_refuse.npz")
    live_dump = tmp_path / "live" / "live_run.npz"
    launched: list = []

    class _RecordingJob:
        """A launcher that records the argv it was handed, then refuses."""

        def __init__(self, argv, *args, **kwargs) -> None:
            launched.append(list(argv))
            raise AssertionError(
                "a static page spawned a solver: the press was supposed to be "
                f"refused before this, argv={argv!r}"
            )

    # Both are module globals the shipped trigger reads at CALL time, so patching
    # the attributes redirects it instead of re-implementing it.
    monkeypatch.setattr(app, "LIVE_DUMP", live_dump)
    monkeypatch.setattr(app, "SolveJob", _RecordingJob)

    with _counted_render():
        _app, srv = _boot_app(info)
        state, ctrl = srv.state, srv.controller
        assert str(state.solve_label) == "Solve (static field snapshot)", (
            "this is not the static page the refusal is about: "
            f"solve_label={str(state.solve_label)!r}"
        )
        assert state.solve_disabled, (
            "the static page left Solve enabled, so a press is offered on a page "
            "that cannot take one"
        )
        trigger = _registered_trigger(ctrl, "solve_start")
        trigger()  # exactly what the button calls
        printed = capsys.readouterr().err

    assert not launched, (
        f"the static page built a solver job anyway: {launched!r}"
    )
    assert not live_dump.exists(), (
        f"the refused press wrote {live_dump}: a solve that cannot land must not "
        "leave a dump behind, and must not touch the live one"
    )
    assert "[poc_app] solve refused" in printed, (
        "the refusal is silent: nothing reached stderr, so an operator reading "
        f"the server log sees no reason for the dead button. stderr was {printed!r}"
    )
    assert str(state.solve_status) == (
        "solve refused: this page is a static field snapshot, which has no "
        "timeline for a new run to land in - open an animation dump to solve, "
        "then reload the page to view the result"
    ), (
        "the status line does not say WHY nothing happened, or what to do "
        f"instead: {str(state.solve_status)!r}"
    )


# =============================================================================
# THE FAMILY SWITCH'S RANGE, and the lines that say what a reader is looking
# at: a page with no timeline, two discs that are MARKERS, a caption that is
# small print
# =============================================================================


def _capture_html_divs(monkeypatch):
    """Record every ``Div`` the page builds, with its TEXT and its STYLE.

    ``_capture_html_widgets`` (:2487) records the html layer too, but it keeps
    only kind/text/src - and the point of the note and of the caption below is
    their SIZE, so the style has to come back with them.  ``poc_app`` resolves
    ``Div`` from the html MODULE at boot (:7566), so patching the module
    attribute is what the page sees; the real class is still constructed, so
    the shipped layout is what is measured.
    """
    import trame.widgets.html as html_mod

    log = []
    real = html_mod.Div

    def _factory(*args, **kwargs):
        log.append(
            {"text": args[0] if args else None, "style": kwargs.get("style")}
        )
        return real(*args, **kwargs)

    monkeypatch.setattr(html_mod, "Div", _factory)
    return log


def test_the_family_switch_returns_the_selected_clocks_own_range() -> None:
    """ONE range for both families, and the SAME one after a switch.

    OBSOLETE as written: this test used to pin the range to the selected
    family's own length (``nt - 1`` in ycut, ``nt_x - 1`` in xcut), which is
    exactly the rescaling this refactor removes - switching plane changed the
    playback speed tenfold on the reference recording. The range is now the
    timeline's last position in EITHER mode, and a page with no timeline at all
    still has NO range: ``None`` is "absent", not "0 frames".
    """
    import poc_app as app

    # A recording whose two families differ by ten, as the reference one does.
    info = {"nt": 40, "nt_x": 4, "frame_index": np.arange(1, 41), "frame_index_xcut": np.arange(1, 40, 10)}
    assert app._frame_max_for(info) == 39, (
        "the scrubber's range is not the timeline's last index: "
        f"{app._frame_max_for(info)!r}, not 39"
    )
    # Both families now share the ONE clock, so the maximum cannot move.
    assert app._frame_max_for(info) == app._frame_max_for(info)
    # No timeline at all: absent, never 0 frames.
    assert app._frame_max_for({"ez_ycut": np.zeros((2, 2, 2))}) is None
    assert app._frame_max_for({}) is None

def test_a_static_page_never_breaks_the_family_switch(tmp_path: Path) -> None:
    """A "Switch plane" press on a page with NO timeline must not take it down.

    The button is emitted unconditionally (um3k_panels.py:205-210; the playback
    buttons beside it are guarded by ``if nt is not None``, this one is not), so
    a static field dump carries it ON SCREEN with both clocks None.  The press
    used to reach ``int(None)`` through the range arithmetic and raise inside a
    trame trigger; here it is driven exactly as the browser drives it.
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    with _counted_render():
        info = _fixture_legacy_info(app, tmp_path / "switch.npz")
        _app, srv = _boot_app(info)
        toggle = _registered_trigger(srv.controller, "mode_toggle")
        state = _closure_cells(toggle)["state"]
        assert state.frame_max is None, (
            "this is not the static page the press is about: the boot already "
            f"handed the scrubber a range (frame_max={state.frame_max!r})"
        )
        # NO ready()/flush() here, deliberately: the press must change nothing,
        # so there is no write for a listener to react to - and marking the
        # PROCESS-WIDE server state ready would break the picker file's own
        # "the boot double never bound a port" assertion (:647) when both run
        # in one pytest process.
        with state:
            toggle()  # exactly what the button calls

    assert state.frame_max is None, (
        "the press handed the scrubber a range on a page that has no "
        f"timeline: frame_max={state.frame_max!r}"
    )
    assert int(state.frame) == 0, (
        f"the press moved the frame to {state.frame!r} on a page with one "
        "picture, so the readouts now name a frame that was never drawn"
    )
    assert str(state.mode) == "ycut", (
        f"the press switched the family to {state.mode!r} on a page that has "
        "no second family: there is nothing to draw and the readouts name "
        "keys this dump does not carry"
    )


def test_the_plane_boxes_carry_a_note_saying_they_are_markers(
    tmp_path: Path, monkeypatch
) -> None:
    """The two discs are X-markers, and the page has to SAY so where the boxes are.

    A reader who takes the red/purple planes for two more field slices reads a
    correct, localized field as a broken one.  The note rides with the boxes
    (it is emitted inside the same ``cut_redraw`` guard), so the pair is
    asserted together: a note on a page with no plane stack would be describing
    boxes that are not there.
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    divs = _capture_html_divs(monkeypatch)
    boxes = _capture_v_checkboxes(monkeypatch)
    with _counted_render():
        _boot_app(_fixture_legacy_info(app, tmp_path / "note.npz"))

    note = (
        "Note: Port and Load planes are X-markers. The 3D field is "
        "localized to the microstrip."
    )
    found = [entry for entry in divs if entry["text"] == note]
    assert len(found) == 1, (
        f"the plane note is on the page {len(found)} times, not once: a note "
        "that is missing leaves the discs readable as field slices, and two "
        f"of them is noise. divs={[e['text'] for e in divs]}"
    )
    style = found[0]["style"] or ""
    assert "font-size: 10px" in style, (
        "the plane note is not drawn as small print: it is one line under the "
        f"boxes for them, not a paragraph. style={style!r}"
    )
    assert "color: #555" in style, (
        f"the plane note is not the muted grey the other footnotes use: {style!r}"
    )

    labels = {
        entry["kwargs"].get("label")
        for entry in boxes
        if entry["kwargs"].get("label")
    }
    for wanted in ("Show Load Plane (red)", "Show S11 Port Plane (purple)"):
        assert wanted in labels, (
            f"the note describes boxes that are not on this page: {wanted!r} "
            f"is missing. labels={sorted(labels)}"
        )


def test_the_mode_caption_is_drawn_as_small_print(
    tmp_path: Path, monkeypatch
) -> None:
    """The Mode panel's caption is a NOTE, and it is drawn as one.

    The line carries the boot hint, the solved numbers or a refusal - never the
    page's headline - so it is 11 px and dark grey rather than the default body
    size it used to inherit.
    """
    pytest.importorskip("pyvista")
    import poc_app as app

    divs = _capture_html_divs(monkeypatch)
    with _counted_render():
        _boot_app(_fixture_info(app, tmp_path / "caption.npz"))

    captions = [e for e in divs if e["text"] == "{{ mode_view_caption }}"]
    assert len(captions) == 1, (
        f"the Mode caption is emitted {len(captions)} times, not once: the "
        "panel is supposed to be ONE line, and a second copy would say the "
        f"same thing twice. divs={[e['text'] for e in divs]}"
    )
    assert captions[0]["style"] == (
        "font-size: 11px; color: #333; padding: 2px 0;"
    ), (
        "the Mode caption is not drawn as small print: it inherits the body "
        f"size and reads as the panel's headline. style={captions[0]['style']!r}"
    )


def test_a_busy_port_moves_the_server_up_instead_of_failing() -> None:
    """A port someone else holds must NOT end the run: it moves one up.

    The bind used to be attempted at the very END of a boot - after the archive
    was loaded, every chart built and the animation scanned - so a busy port
    threw minutes of work away to print one line and exit 1. ``is_free`` is
    injected, so the scan is asserted here without binding a socket.
    """
    import poc_app as app

    taken = {8080}

    def is_free(port: int) -> bool:
        return port not in taken

    assert app._pick_port(8080, is_free) == 8081, (
        "a busy port was not stepped over: the run would fail on a bind it could "
        "have seen coming before loading anything"
    )
    taken.add(8081)
    assert app._pick_port(8080, is_free) == 8082, (
        "the scan stopped at the first neighbour instead of finding the next "
        "free port above it"
    )
    assert app._pick_port(9000, is_free) == 9000, (
        "a free port was abandoned for a free port: the request must be honoured "
        "as given"
    )
    assert app._pick_port(8080, lambda _p: False) == 8080, (
        "with nothing free above, the requested port must come back unchanged so "
        "the bind error names the port that was actually asked for"
    )


def test_a_busy_port_is_reported_in_one_line_naming_the_port(
    capsys, monkeypatch
) -> None:
    """ONE line: the port, who holds it, and what this run took instead.

    The old report was three stderr lines after all the work was done, and it
    said nothing about who was on the port: the operator was left to find their
    own stray server. ``_port_holder`` is doubled here (it reads /proc), the port
    probe too - the shipped formatter is what is asserted.
    """
    import poc_app as app

    monkeypatch.setattr(app, "_port_is_free", lambda _host, port: port != 8080)
    monkeypatch.setattr(
        app, "_port_holder", lambda _port: "pid 4321 python3 other_viewer.py"
    )

    assert app._port_for_serving("127.0.0.1", 8080) == 8081
    printed = capsys.readouterr().out.splitlines()
    busy = [line for line in printed if "busy" in line]
    assert busy == [
        "[poc_app] port 8080 busy (pid 4321 python3 other_viewer.py); "
        "using 8081 instead"
    ], (
        "the busy port is not reported as ONE line naming the port, the holder "
        f"and the port actually used. lines={printed}"
    )
    assert any(line.startswith("[poc_app] pid ") for line in printed), (
        "the run never prints its own pid: a busy port cannot be traced back to "
        f"the process that holds it. lines={printed}"
    )


# =============================================================================
# WHICH VIEW THE CENTRE PLOTTER IS BUILT AS (--local-view / POC_LOCAL_VIEW)
# =============================================================================
# Default OFF, and off is exactly the page that shipped before: the centre
# column builds its plotter_ui with mode="server" and the view the page caches
# on handles["view"] is the REMOTE one.  The flag - or POC_LOCAL_VIEW, combined
# inside run_web_vis - moves the rendering into the BROWSER instead, which is
# what a host with no GL to render WITH needs.
#
# The switch and the page it produces are pinned here.  WHICH mode string
# reaches plotter_ui is pinned in tests/test_um3k_panels.py, where the centre
# column is built against a fake context and no server is needed at all.


def test_local_view_is_off_unless_asked_and_the_env_is_read_at_call_time(
    monkeypatch,
) -> None:
    """If this fails, a plain run renders in the browser or ignores the variable.

    ``POC_LOCAL_VIEW`` is set AFTER the import on purpose: the switch has to
    answer with the environment as it is when the page is built, not as it was
    when the module was read - a captured value would make a run started with
    the variable set behave exactly like one started without it.
    """
    import poc_app as app

    monkeypatch.delenv("POC_LOCAL_VIEW", raising=False)
    assert app.LOCAL_VIEW_DEFAULT is False, (
        "the shipped default is not off: every run would render the centre "
        "plotter in the browser"
    )
    assert app._local_view_enabled() is False, (
        "with no flag and no variable the page is no longer server-rendered"
    )
    monkeypatch.setenv("POC_LOCAL_VIEW", "1")
    assert app._local_view_enabled() is True, (
        "POC_LOCAL_VIEW was set after import and had no effect: the variable is "
        "being captured somewhere other than call time"
    )
    monkeypatch.setenv("POC_LOCAL_VIEW", " TRUE ")
    assert app._local_view_enabled() is True, (
        "a padded/uppercase 'true' is refused, so a documented spelling of the "
        "variable silently does nothing"
    )
    for said in ("0", "", "   "):
        monkeypatch.setenv("POC_LOCAL_VIEW", said)
        assert app._local_view_enabled() is False, (
            f"POC_LOCAL_VIEW={said!r} turned the local view ON: anything that is "
            "not 1/true must leave the default page alone"
        )
    monkeypatch.setenv("POC_LOCAL_VIEW", "0")
    assert app._local_view_enabled(True) is True, (
        "the flag lost to a variable that says no: --local-view is the explicit "
        "ask, so it must win"
    )


def test_the_local_view_default_is_the_switch_the_switch_reads(monkeypatch) -> None:
    """``LOCAL_VIEW_DEFAULT`` is the module-level default, not a dead constant."""
    import poc_app as app

    monkeypatch.delenv("POC_LOCAL_VIEW", raising=False)
    monkeypatch.setattr(app, "LOCAL_VIEW_DEFAULT", True)
    assert app._local_view_enabled() is True, (
        "LOCAL_VIEW_DEFAULT was flipped and nothing changed: the switch does not "
        "read the module constant"
    )


class _Shell:
    """Stand-in for ``run_web_vis``: records the call, boots nothing."""

    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, *args, **kwargs) -> int:
        self.calls.append((args, kwargs))
        return 0


def _main_kwargs_for(monkeypatch, tmp_path: Path, *extra: str) -> dict:
    """The keyword arguments ``main`` hands the shell, with its seams recorded.

    Same recipe as tests/test_poc_dispatch.py: the registry, the record-only
    probe and the dump read are replaced, so no trame server boots and no npz is
    opened - the argument ``main`` carries is the whole subject here.
    """
    import poc_app as app

    page = {
        "info": {"format": app.VIS_FORMAT, "nt": 4},
        "path": str(tmp_path / "d.npz"),
    }
    monkeypatch.setattr(app, "load_structures", lambda: [{"id": "s1"}])
    monkeypatch.setattr(app, "_structure_is_record_only", lambda structure: False)
    monkeypatch.setattr(
        app, "reload_page", lambda npz_path, structure_id=None: page
    )
    shell = _Shell()
    monkeypatch.setattr(app, "run_web_vis", shell)
    monkeypatch.setattr(app, "run_web", _Shell())
    monkeypatch.setattr(app, "print_keys", _Shell())

    assert app.main(["--structure", "s1", "--input", "fake.npz", *extra]) == 0
    assert len(shell.calls) == 1, (
        "main did not hand this dump to the unified shell once: "
        f"{shell.calls}"
    )
    return shell.calls[0][1]


def test_the_shell_is_told_local_view_only_when_the_flag_was_given(
    monkeypatch, tmp_path: Path
) -> None:
    """If this fails, --local-view never reaches the page or is always on."""
    assert _main_kwargs_for(monkeypatch, tmp_path)["local_view"] is False, (
        "a plain run asks the shell for the local view: the default page moved "
        "the rendering into the browser"
    )
    assert (
        _main_kwargs_for(monkeypatch, tmp_path, "--local-view")["local_view"]
        is True
    ), "--local-view was given and the shell was not told"


def test_the_env_alone_does_not_reach_the_shell_as_a_flag(
    monkeypatch, tmp_path: Path
) -> None:
    """``POC_LOCAL_VIEW`` is combined INSIDE the shell, never by ``main``.

    ``main`` passes what was typed on the command line; the variable is read by
    ``_local_view_enabled`` when the page is built.  Asserting the env on the
    keyword would pin the wrong seam - and a ``main`` that folded the variable
    in itself would be a second place to keep in step.
    """
    monkeypatch.setenv("POC_LOCAL_VIEW", "1")
    assert _main_kwargs_for(monkeypatch, tmp_path)["local_view"] is False, (
        "main folded POC_LOCAL_VIEW into the argument it passes: the variable "
        "belongs to the switch inside run_web_vis"
    )


def _view_handle(info) -> object:
    """``handles["view"]`` off the live page, after the layout was built.

    The dict comes off the play trigger's closure: it is the page's own dict,
    and a stand-in would prove nothing about what the boot really built.
    """
    app, srv = _boot_app(info)
    trigger = _registered_trigger(srv.controller, TRIGGER_NAME)
    cells = _closure_cells(trigger)
    assert "handles" in cells, (
        "the play trigger is not closed over the page's `handles` "
        f"(freevars: {sorted(cells)}), so the built view cannot be asserted on"
    )
    handles = cells["handles"]
    assert "view" in handles, (
        "no handles['view'] after the layout was built: the centre column "
        "returned nothing, or the boot returned before the row was laid out"
    )
    return handles["view"]


def test_the_default_page_renders_its_picture_on_the_server(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """If this fails, a plain run renders in the BROWSER - the default moved."""
    pytest.importorskip("pyvista")
    import poc_app as app

    monkeypatch.delenv("POC_LOCAL_VIEW", raising=False)
    with _counted_render():
        view = _view_handle(_fixture_info(app, tmp_path / "default.npz"))

    assert type(view).__name__ == "PyVistaRemoteView", (
        "the default page did not build the server-rendered view: "
        f"{type(view).__name__} was built instead, so a plain run now depends on "
        "the client's WebGL context"
    )
    out, err = capsys.readouterr()
    assert app._local_view_notice(True) not in out + err, (
        "a plain run warned about the local view: nothing about the browser "
        "mode belongs in the default page's log, and a run that never opted in "
        f"must not be told it did: {(out, err)!r}"
    )


def test_local_view_builds_the_browser_rendered_view(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """If this fails, --local-view reaches the page but not the picture."""
    pytest.importorskip("pyvista")
    import poc_app as app

    monkeypatch.setenv("POC_LOCAL_VIEW", "1")
    with _counted_render():
        view = _view_handle(_fixture_info(app, tmp_path / "local.npz"))

    assert type(view).__name__ == "PyVistaLocalView", (
        "POC_LOCAL_VIEW=1 did not move the rendering into the browser: "
        f"{type(view).__name__} was built, so a host with no GL to render WITH "
        "still gets nothing"
    )
    notice = app._local_view_notice(True)
    assert capsys.readouterr().out.count(notice) == 1, (
        "the browser-rendered boot did not print its ONE warning line: the "
        "operator whose server draws no pixels is told exactly once, and a run "
        "that prints nothing looks like a page whose pictures silently vanished"
    )


class _ScreenshotProbe:
    """A plotter whose only interesting surface is ``screenshot``.

    ``suppress_rendering`` is pyvista's own flag, set by trame_pyvista for a
    ``mode="client"`` view; ``asked`` records every path handed to the readback,
    which is the subject here - a refused still must never reach the filter.
    """

    def __init__(self, suppress_rendering) -> None:
        self.suppress_rendering = suppress_rendering
        self.asked: list = []

    def screenshot(self, path, **_kwargs):
        self.asked.append(path)
        return None


def test_a_browser_rendered_plotter_is_never_asked_for_a_screenshot(
    monkeypatch,
) -> None:
    """If this fails, the timing probe renders a window a browser view never had.

    pyvista's ``render()`` honours ``suppress_rendering`` (plotter.py:2557), but
    the STILL does not: ``Plotter.image`` goes through vtkWindowToImageFilter,
    which renders the window ITSELF.  On a client-rendered view that is a
    C-level crash rather than an exception, so it cannot be caught downstream -
    the refusal has to happen before the request.
    """
    import poc_app as app

    monkeypatch.setattr(
        app,
        "_TIMING",
        {
            "tick": 0,
            "shot_count": 0,
            "shots_ok": True,
            "shot_error_logged": False,
        },
    )
    monkeypatch.setattr(app, "_timing_ensure_dirs", lambda: None)

    client = _ScreenshotProbe(True)
    assert app._timing_screenshot(client) is None, (
        "a plotter that suppresses its rendering was not refused a still: the "
        "readback renders the very window this view has no GL context for"
    )
    assert client.asked == [], (
        "the suppress_rendering guard let a readback through anyway: "
        f"{client.asked!r}"
    )

    # The OTHER half of the pin: the guard is about the flag, not about refusing
    # every plotter.  A server-rendered view must still be screenshotted, or the
    # probe silently stops measuring what it exists to measure.
    server = _ScreenshotProbe(False)
    assert app._timing_screenshot(server) is not None, (
        "a normally-rendered plotter got no screenshot either: the guard refuses "
        "unconditionally instead of on suppress_rendering"
    )
    assert len(server.asked) == 1, (
        f"a server-rendered view was screenshotted {len(server.asked)} times, "
        "not once"
    )
    assert app._TIMING["shot_count"] == 1, (
        "the shot that WAS taken was not counted, so the 60-file ration is off"
    )


def test_the_local_view_notice_is_one_line_and_only_when_the_mode_is_on() -> None:
    """If this fails, either mode says the wrong thing about where it renders.

    One LINE because it is a boot message, not a manual: an operator scrolling
    the log must see it whole.  None when the mode is off, because a plain run's
    output is not allowed to grow a warning about a mode it did not ask for.
    """
    import poc_app as app

    assert app._local_view_notice(False) is None, (
        "a run that is NOT browser-rendered was given a warning saying it is"
    )
    notice = app._local_view_notice(True)
    assert isinstance(notice, str) and notice, (
        f"the browser-rendered boot got no notice to print: {notice!r}"
    )
    assert "\n" not in notice, (
        f"the boot notice spans more than one line: {notice!r}"
    )
    assert "BROWSER" in notice, (
        f"the notice does not say where the picture is actually drawn: {notice!r}"
    )
    assert "crash" in notice, (
        "the notice does not warn that this experimental path can take the "
        f"process down: {notice!r}"
    )

