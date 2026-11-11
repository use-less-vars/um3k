"""Headless proof that the wave-dude play trigger RETURNS while playback runs.

REAL, not simulated: ``run_web_wavedude`` boots for real (server, state,
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
    reason="trame.ui.vuetify3 is what run_web_wavedude builds its layout with",
)

FPS = 25
TRIGGER_NAME = "play_toggle"
RETURN_TIMEOUT_S = 1.0
LOOP_EXIT_TIMEOUT_S = 2.0


class _Stop(Exception):
    """Unwinds ``run_web_wavedude`` just before it enters the event loop."""


def _fixture_info(app, path: Path) -> dict:
    """Minimal ``emfit.wavedude/1`` dump, the same field set verify_wd.py uses."""
    nt, nx, nz = 4, 8, 5
    nt_x, ny_x = 3, 6
    rng = np.random.default_rng(0)
    payload = {
        "schema": app.WAVEDUDE_SCHEMA,
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
    np.savez(path, **payload)
    return app.load_wavedude(path)


def _boot_app(info):
    """Run ``run_web_wavedude`` up to the point it would call ``server.start``.

    Same recipe as artifacts/verify_wd.py: wrap ``trame.app.get_server`` so the
    live server object escapes, and make ``start`` raise so the event loop is
    never entered.  ``run_web_wavedude`` imports ``get_server`` inside the
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
            app.run_web_wavedude(info, "127.0.0.1", 8999, fps=FPS)
    finally:
        trame_app.get_server = real_get_server

    assert "srv" in box, (
        "run_web_wavedude never reached server.start(): it returned early "
        "(missing web dependency) so no trigger was registered"
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
