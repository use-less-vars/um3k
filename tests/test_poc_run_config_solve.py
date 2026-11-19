"""The Run Config form drives the solve: eight boxes, ONE child, auto-loaded.

``server/poc_app.py``'s Run Config card is the eight ``run_*`` states; the two
halves of the gate that draws it are pinned in
``tests/test_poc_run_config_form.py`` (arrives on a no-data page) and
``tests/test_poc_run_config_panel.py`` (absent on a dump-backed one).  This
module pins the FAR end of the same wire: a press of Solve reads those eight
values, builds the ONE ``emfit.config.RunConfig`` the child is given, and hands
it to the ONE argv builder the viewer has always used - so the form has no
second route into a solve that could drift away from the button's.

REAL, not simulated: ``run_web_vis`` boots for real and the handler exercised is
the object ``@ctrl.set("solve_start")`` registered - the one the button calls.
``SolveJob`` is the shipped class, so the child process is really spawned; only
the PROGRAM is a three-line stand-in, reached by pointing ``SOLVER_SCRIPT
``(a module global read at call time) at it, which redirects the shipped path
instead of re-implementing it.  The stand-in sleeps, then writes a dump that
says a DIFFERENT arm, so "the finished run landed on the page" is visible in the
page a reader actually sees, not only in a dict.

The other end of the press is pinned here too: the watcher that loads the dump
DRAWS it (``_poll_solve`` -> ``_show``), so "solved" on screen is a repainted
page and not a sentence over the previous one, and the Run Config form it
describes is put away once a run is behind the page.  WHICH pages may solve at
all is ONE predicate; the boot, the button and the handler are pinned against
that same function rather than against three copies of its answer.

DOUBLED: ``pyvista.Plotter.render`` and the view's ``update`` only - this image
has no EGL, so a real draw segfaults the interpreter.  Nothing inside the
trigger, ``SolveJob``, ``_watch_solve``, ``_poll_solve`` or ``apply_page`` is
replaced or skipped.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server"), str(REPO_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# In this image pyvista/trame/vtk live in the repo's own venv (its bin/python is
# broken, the site-packages tree is not).  On a host where they are installed
# normally this directory is either absent or already on sys.path, so the block
# is inert there.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip("pyvista", reason="pyvista is the web UI's renderer")
pytest.importorskip("trame.app", reason="trame serves the page")
pytest.importorskip("trame.ui.vuetify3", reason="run_web_vis builds this UI")

import poc_app as app  # noqa: E402  (after the importorskip guards)

import test_animation_volume as av  # noqa: E402  (the doubled-render recipe)
import test_poc_bare_board as bb  # noqa: E402  (the no-data page's recipe)
import test_poc_run_config_form as form_recipe  # noqa: E402  (its recorder)
from test_poc_playback import (  # noqa: E402  (the boot recipe, shared)
    _boot_app,
    _closure_cells,
    _fixture_info,
    _registered_trigger,
)

assert av.app is app, (
    "tests/test_animation_volume.py imported a different poc_app; the recipe "
    "above would double the wrong module's renderer"
)
assert form_recipe.app is app and bb.app is app, (
    "the borrowed recipes imported a different poc_app; a second boot through "
    "them would build a page this module cannot reach"
)

#: How long the stand-in child "solves" for. Long enough that a press which WAITED
#: on it could not possibly return inside PRESS_BUDGET_S, which is what makes the
#: non-blocking assertion mean something.
DELAY_S = 0.5
#: What a press that only STARTED the child may spend. Ten times the measured
#: cost, and still below the stand-in's runtime, so the two cannot be confused.
PRESS_BUDGET_S = 0.3
LANDING_TIMEOUT_S = 20.0

_CHILD_SOURCE = """\
import shutil, sys, time
time.sleep({delay})
shutil.copyfile({source!r}, sys.argv[sys.argv.index("--vis-dump") + 1])
print("stand-in solve done")
"""


def _wait_for_idle(solve, timeout=15.0) -> None:
    """Block until the previously spawned stand-in child has exited.

    ONE press at a time is the shipped rule (``_on_solve_start`` refuses while a
    job is running), so each test has to let the previous one finish before it
    presses - otherwise it would be testing the guard, not the wiring.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = solve.get("job")
        if job is None or job.status != "running":
            return
        time.sleep(0.02)
    raise AssertionError(
        "a previous stand-in solve never exited, so the next press would be "
        "refused by the one-at-a-time guard and prove nothing"
    )


@pytest.fixture(scope="module")
def viewer(tmp_path_factory):
    """One booted viewer, one stand-in child, both shared by every test here.

    WHY once for the module: ``trame.app.get_server`` hands back ONE server per
    process, so a second boot would serve the same state again while paying for
    the whole layout a second time.  The eight boxes are the same eight states on
    every page, and the child stand-in is stateless, so nothing below depends on
    which test ran first.
    """
    pytest.importorskip("pyvista")
    tmp = tmp_path_factory.mktemp("run_config_solve")

    solved = tmp / "solved_B.npz"
    _fixture_info(app, solved, structure_id="B", load_ohm=100.0)
    child = tmp / "stand_in_solver.py"
    child.write_text(
        _CHILD_SOURCE.format(source=str(solved), delay=DELAY_S), encoding="utf-8"
    )
    live_dump = tmp / "live" / "live_run.npz"
    info = _fixture_info(app, tmp / "boot_A.npz", structure_id="A", load_ohm=50.0)

    patch = pytest.MonkeyPatch()
    # Both are module globals READ AT CALL TIME, so patching the attributes
    # redirects the shipped code paths instead of re-implementing them.
    patch.setattr(app, "SOLVER_SCRIPT", child)
    patch.setattr(app, "LIVE_DUMP", live_dump)
    # apply_page is the ONE door a page walks in through, so recording its first
    # argument shows which page the viewer was actually handed - without any
    # test reaching into a closure for a name the shipped code may rename.
    real_apply_page = app.apply_page
    applied_pages: list[dict] = []

    def _record_apply_page(page, *args, **kwargs):
        result = real_apply_page(page, *args, **kwargs)
        applied_pages.append(page)
        return result

    patch.setattr(app, "apply_page", _record_apply_page)

    # ---- the ONE device double, held for the WHOLE life of the page --------
    # A finished solve now REPAINTS what it loaded (_poll_solve -> _show ->
    # plotter.render), and this image has no EGL, no libOSMesa and no X server:
    # a real draw segfaults the interpreter in the middle of an assertion.
    # Doubling only across the boot - which is all the older tests here needed -
    # would leave that press drawing for real, so the counter below stays
    # installed across the yield. Every scene-building call around it
    # (add_mesh, remove_actor, ...) stays the real one.
    pyvista = pytest.importorskip("pyvista")
    real_render = pyvista.Plotter.render
    renders: list = []

    def _no_render(self, *args, **kwargs):
        renders.append(1)  # counted, never performed

    try:
        with av._render_doubled():
            # Installed INSIDE the borrowed doubling recipe, not before it: that
            # recipe saves whatever ``Plotter.render`` it finds at entry and
            # puts its own uncounted no-op in its place, so a counter installed
            # earlier would be the thing it saves and never the thing the page
            # calls.  Set after entering, this counter IS what the press draws
            # through - and the recipe restores the real one for us on exit.
            pyvista.Plotter.render = _no_render
            _app, srv = _boot_app(info)
            state = srv.state
            trigger = _registered_trigger(srv.controller, "solve_start")
            cells = _closure_cells(trigger)
            assert {"state", "solve", "_start_watch"} <= set(cells), (
                "the solve trigger is not closed over the live page objects "
                f"(freevars: {sorted(cells)}), so nothing here could reach the "
                "job it starts"
            )
            # The watcher's own closure leads to the live handles, so the poller
            # driven below is the one the server would run.
            poll = _closure_cells(
                _closure_cells(cells["_start_watch"])["_watch_solve"]
            )["_poll_solve"]
            poll_cells = _closure_cells(poll)
            assert state.structure_readout == "structure: A (50 \u03a9)", (
                f"the page did not boot on arm A: {state.structure_readout!r}"
            )
            view = poll_cells["handles"].get("view")
            updates: list = []
            if view is not None and hasattr(view, "update"):
                # Counted, not pushed at a browser that is not there: the COUNT is
                # what tells "the new dump was drawn" apart from "the page only
                # said it was".
                view.update = lambda *args, **_kwargs: updates.append(1)
            try:
                yield SimpleNamespace(
                    state=state,
                    solve=cells["solve"],
                    trigger=trigger,
                    applied=applied_pages,
                    live_dump=live_dump,
                    # The page the redraw has to reach, and the ONE flag the
                    # Run Config card's v_if reads: both live on the objects
                    # this boot made, never on a stand-in.
                    handles=poll_cells["handles"],
                    view=view,
                    boot_run_config_visible=state.run_config_visible,
                    # The two device doubles' counters: a delta across one press
                    # is the picture being redrawn.
                    renders=renders,
                    updates=updates,
                )
            finally:
                _wait_for_idle(cells["solve"])
    finally:
        pyvista.Plotter.render = real_render
        patch.undo()


def _write_boxes(state, **boxes) -> None:
    """Put the eight boxes where the browser would, then press.

    ``boxes`` uses the short names (``nsteps``, ``volume_stride``, ...); a box
    NOT named is written BLANK, which is exactly what an untouched VTextField
    hands over.  Written through ``state`` because RUN_CONFIG_FIELDS IS the
    binding: there is no other place a press could read these eight from.
    """
    for state_name, _label, _field in app.RUN_CONFIG_FIELDS:
        setattr(state, state_name, str(boxes.get(state_name[len("run_"):], "")))
    # The Action card's own cut plane, at its default: a blank Run Config box is
    # meant to leave it alone, so it must be a known value for that to show.
    state.solve_xcut_mm = 20.4


def _press(viewer, **boxes):
    """Write the boxes, press Solve once, and return the job it started."""
    _write_boxes(viewer.state, **boxes)
    _wait_for_idle(viewer.solve)
    viewer.solve.pop("job", None)
    viewer.state.solve_status = ""
    viewer.trigger()  # exactly what the button calls
    return viewer.solve.get("job")


def test_the_eight_form_values_reach_the_solver(viewer) -> None:
    """Every box the user typed is in the child's command line, as typed.

    WHY the argv and not a config object: the argv is the last thing this process
    writes before the child owns the run, so it is the widest place the values
    could be lost.  ``--nsteps``/``--volume-stride`` are INTEGER flags, so a
    ``600.0`` that the solver would reject must not appear either - and the same
    holds for the three budget boxes (``--dump-stride``, ``--n-line``,
    ``--volume-frames``), which the same kind split parses as whole numbers.
    """
    job = _press(
        viewer,
        nsteps="600",
        volume_stride="5",
        dump_stride="3",
        volume_frames="7",
        pulse_freq_ghz="10",
        xcut_near_mm="18",
        xcut_far_mm="21",
        n_line="40",
    )
    assert job is not None, (
        "the press spawned nothing, so the eight boxes went nowhere: "
        f"{viewer.state.solve_status!r}"
    )
    argv = list(job.argv)
    for flag, want in (
        ("--nsteps", "600"),
        ("--volume-stride", "5"),
        ("--pulse-freq-ghz", "10"),
        ("--xcut-near-mm", "18"),
        ("--xcut-far-mm", "21"),
        ("--dump-stride", "3"),
        ("--n-line", "40"),
        ("--volume-frames", "7"),
    ):
        assert flag in argv, (
            f"the child was never told {flag}: the Run Config box behind it is "
            f"read by nothing ({argv!r})"
        )
        assert argv[argv.index(flag) + 1] == want, (
            f"{flag} is {argv[argv.index(flag) + 1]!r}, not {want!r} as typed: "
            f"the box the user filled did not reach the solver ({argv!r})"
        )
    assert "600.0" not in argv and "5.0" not in argv, (
        f"a whole-number box reached the solver as a float ({argv!r}): "
        "RunConfig refuses a float where an int belongs, and so does the solver"
    )
    assert "3.0" not in argv and "40.0" not in argv and "7.0" not in argv, (
        f"a whole-number BUDGET box reached the solver as a float ({argv!r}): "
        "--dump-stride, --n-line and --volume-frames are integers on the "
        "writer's side too, so the same refusal waits there"
    )


def test_the_argv_builder_carries_the_whole_form() -> None:
    """The flag list IS the form: all eight boxes, in the solver's own spelling.

    Called directly, with no boot and no child: this function is the last thing
    the press writes before the solver owns the run, so a box dropped here is
    named here rather than three assertions into a spawned run.  The three flags
    the page has always sent first keep their order, ``--pulse-freq-ghz`` keeps
    its place behind them, and the dump budget travels after it.
    """
    from emfit.config import RunConfig

    config = RunConfig(
        nsteps=600,
        volume_stride=5,
        dump_stride=3,
        volume_frames=7,
        pulse_freq_ghz=10.0,
        xcut_near_mm=18.0,
        xcut_far_mm=21.0,
        n_line=40,
    )
    flags = app._run_config_argv(config)
    wanted = [
        "--nsteps",
        "600",
        "--volume-stride",
        "5",
        "--xcut-far-mm",
        "21",
        "--pulse-freq-ghz",
        "10",
        "--dump-stride",
        "3",
        "--n-line",
        "40",
        "--volume-frames",
        "7",
    ]
    assert flags == wanted, (
        f"the argv builder produced {flags!r}, not {wanted!r}: a box missing "
        "from this list is a box the press SHOWS and the solver never hears "
        "about - the dump budget travels with the same press as the physics"
    )


def test_the_argv_builder_omits_the_caps_it_does_not_have() -> None:
    """``None`` is "no cap", not a number to pass - and no form is no flags."""
    from emfit.config import RunConfig

    flags = app._run_config_argv(
        RunConfig(nsteps=600, volume_frames=None, pulse_freq_ghz=None)
    )
    assert "--volume-frames" not in flags, (
        f"a config carrying no frame cap still asked the solver for one "
        f"({flags!r}): None is the ABSENCE of the flag, and an invented cap "
        "would shorten the volume the reader asked for"
    )
    assert "--pulse-freq-ghz" not in flags, (
        f"a config carrying no pulse still asked the solver for a frequency "
        f"({flags!r}): None is the reference's own pulse, not a number"
    )
    assert app._run_config_argv(None) == [], (
        "the no-form case stopped producing the bare command line every caller "
        f"had before the form existed ({app._run_config_argv(None)!r})"
    )


def test_a_blank_box_takes_the_run_config_default(viewer) -> None:
    """An untouched form solves what it has always solved - no zero, no refusal.

    A VTextField that nobody typed into is ``""`` (and an absent state field is
    ``None``), and ``int("")`` is an exception: both have to read as "leave this
    box alone", which means the value ``RunConfig`` itself carries - never a
    literal copied into the UI, and never a zero that would make the solver run
    nothing.
    """
    from emfit.config import RunConfig

    reference = RunConfig()
    for blank in ("", "   ", None):
        config = app.run_config_from_form(
            {state_name: blank for state_name, _label, _field in app.RUN_CONFIG_FIELDS}
        )
        for _state_name, _label, field in app.RUN_CONFIG_FIELDS:
            assert getattr(config, field) == getattr(reference, field), (
                f"a {blank!r} box gave {field} {getattr(config, field)!r} instead of "
                f"the RunConfig default {getattr(reference, field)!r}: a blank box "
                "is not a zero and not a crash"
            )
        assert config.pulse_freq_ghz is None, (
            f"a {blank!r} pulse box invented a frequency ({config.pulse_freq_ghz!r}): "
            "None is the reference's own pulse, which is the absence of the flag"
        )

    job = _press(viewer)  # every box blank, exactly as an untouched form leaves it
    assert job is not None, (
        "a blank form refused the press instead of using the defaults: "
        f"{viewer.state.solve_status!r}"
    )


def test_a_box_that_is_not_a_number_refuses_the_press(viewer) -> None:
    """Garbage in one box costs a message and a child process, in that order.

    The alternative - substituting a default and pressing on - runs a solve the
    user did not ask for and says nothing about it, which is the failure mode
    this refusal exists to prevent.
    """
    job = _press(
        viewer,
        nsteps="lots",
        volume_stride="1",
        xcut_near_mm="20.4",
        xcut_far_mm="22",
    )
    assert job is None, (
        "a press with 'lots' in Steps still spawned a child "
        f"({list(job.argv)!r}): the box was ignored or silently replaced"
    )
    assert viewer.state.solve_status.startswith("refused"), (
        f"the press did not refuse: {viewer.state.solve_status!r}"
    )
    assert "Steps" in viewer.state.solve_status, (
        "the refusal does not say which box is wrong, so the user cannot fix it: "
        f"{viewer.state.solve_status!r}"
    )


def test_the_finished_solve_is_loaded_into_the_viewer(viewer) -> None:
    """The dump the child wrote BECOMES the page - no reload, no second press.

    The whole loop is shipped code: the trigger starts ``_watch_solve`` on the
    server's own loop, that task polls ``SolveJob``, ``_poll_solve`` reloads
    ``LIVE_DUMP`` and ``apply_page`` swaps the live holder.
    """
    # A FILLED form: this test is about the swap landing, not about blanks - a
    # blank box has its own test, so nothing here leans on blank tolerance.
    _write_boxes(
        viewer.state,
        nsteps=300,
        volume_stride=2,
        pulse_freq_ghz=10,
        xcut_near_mm=20.4,
        xcut_far_mm=22.0,
    )
    _wait_for_idle(viewer.solve)
    viewer.solve.pop("job", None)
    viewer.state.solve_status = ""

    async def one_press() -> None:
        started = time.monotonic()
        viewer.trigger()
        assert viewer.state.solve_status.startswith("solving"), (
            f"the press did not start a solve: {viewer.state.solve_status!r}"
        )
        while time.monotonic() - started < LANDING_TIMEOUT_S:
            if viewer.state.solve_status.startswith("solved"):
                return
            assert not viewer.state.solve_status.startswith("solve "), (
                "the solve failed instead of landing a page: "
                f"{viewer.state.solve_status!r}"
            )
            await asyncio.sleep(0.05)
        raise AssertionError(
            "nothing loaded the finished solve: _watch_solve is not polling, so "
            f"the page still says {viewer.state.solve_status!r} and the result "
            "would need a manual reload"
        )

    asyncio.run(one_press())

    assert viewer.applied, (
        "nothing was handed to apply_page, so the finished dump was found and "
        "then dropped: the viewer still draws the previous page "
        f"(status {viewer.state.solve_status!r})"
    )
    page = viewer.applied[-1]
    assert Path(page["path"]) == viewer.live_dump, (
        f"the page holds {page['path']!r}, not the solved dump "
        f"{viewer.live_dump}: the swap did not happen"
    )
    assert page["structure_id"] == "B", (
        f"the page still holds {page['structure_id']!r} after a "
        "successful solve: the finished dump was found but never applied"
    )


def test_the_press_does_not_block_the_event_loop(viewer) -> None:
    """A press returns while the child is still solving, and the loop lives on.

    Two failures this rules out: a press that WAITS for the child (the solve
    takes ~31 s in reality, and the page would freeze for all of it), and a
    watcher that is not on the server's loop at all (nothing would ever poll, so
    the finished dump would sit on disk unread).
    """
    # A FILLED form: this test is about the loop staying alive, not about blanks.
    _write_boxes(
        viewer.state,
        nsteps=300,
        volume_stride=2,
        pulse_freq_ghz=10,
        xcut_near_mm=20.4,
        xcut_far_mm=22.0,
    )
    _wait_for_idle(viewer.solve)
    viewer.solve.pop("job", None)
    viewer.state.solve_status = ""

    async def one_press():
        ticks = 0

        async def ticker() -> None:
            nonlocal ticks
            while True:
                await asyncio.sleep(0.02)
                ticks += 1

        helper = asyncio.create_task(ticker())
        try:
            started = time.monotonic()
            viewer.trigger()
            elapsed = time.monotonic() - started
            watchers = [
                task
                for task in asyncio.all_tasks()
                if "watch_solve" in getattr(task.get_coro(), "__qualname__", "")
            ]
            assert watchers, (
                "no _watch_solve task is on the server's loop after a press: "
                "nothing would poll the child, so its dump would never be loaded"
            )
            assert elapsed < PRESS_BUDGET_S, (
                f"the press took {elapsed:.2f} s: it waited for the child (the "
                f"stand-in alone sleeps {DELAY_S} s) instead of returning and "
                "letting _watch_solve bring the result back"
            )
            deadline = time.monotonic() + LANDING_TIMEOUT_S
            while time.monotonic() < deadline:
                if viewer.state.solve_status.startswith("solved"):
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError(
                    "the solve never landed, so how busy the loop was cannot be "
                    f"told apart from a dead watcher: {viewer.state.solve_status!r}"
                )
            return elapsed, ticks
        finally:
            helper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await helper

    _elapsed, ticks = asyncio.run(one_press())
    assert ticks >= 5, (
        f"the event loop only ran {ticks} tick(s) while the child solved: the "
        "press or the poller is blocking it, so the page stops responding for "
        "the length of a real solve"
    )


def _v_model(record):
    """A recorded widget's ``v_model``: what the browser binds it to."""
    return record[2].get("v_model")


def _land_one_press(viewer) -> str:
    """Fill the form, press Solve once, and WAIT for the finished dump to land.

    The same ONE press ``test_the_finished_solve_is_loaded_into_the_viewer``
    drives, kept in one place because the two tests below are about what the
    press LEAVES BEHIND, not about the press itself (which has its own tests
    above). The status the page carries once it says "solved" is returned, so
    what the reader is TOLD can be asserted next to what the page was drawn
    with - the pair is what "the result is on screen" actually means.
    """
    _write_boxes(
        viewer.state,
        nsteps=300,
        volume_stride=2,
        pulse_freq_ghz=10,
        xcut_near_mm=20.4,
        xcut_far_mm=22.0,
    )
    _wait_for_idle(viewer.solve)
    viewer.solve.pop("job", None)
    viewer.state.solve_status = ""

    async def one_press() -> str:
        started = time.monotonic()
        viewer.trigger()
        while time.monotonic() - started < LANDING_TIMEOUT_S:
            status = viewer.state.solve_status
            if status.startswith("solved"):
                return status
            assert not status.startswith("solve "), (
                "the solve failed instead of landing a page: "
                f"{status!r}"
            )
            await asyncio.sleep(0.05)
        raise AssertionError(
            "nothing loaded the finished solve: _watch_solve is not polling, so "
            f"the page still says {viewer.state.solve_status!r}"
        )

    return asyncio.run(one_press())


def test_the_solved_page_is_drawn_here_and_not_reloaded(viewer) -> None:
    """The dump that lands is PAINTED by the watcher that loaded it.

    The failure this rules out is the one that reads as success: the arrays are
    swapped, the status says "solved", and the picture on screen is still the
    dump the reader opened - because nothing drew the new one, and there is no
    second visit to the page to draw it. A sentence that asks for a reload is
    the same failure said out loud, so it is refused too.

    WHY a DELTA on the fixture's two counters: ``_show`` ends in one
    ``plotter.render`` and one ``view.update``, both of which the fixture
    doubles (this image has no OpenGL device) - so how far each counter moved
    across this one press is exactly "the new dump was drawn", counted where
    the shipped code draws rather than inferred from the status string.
    """
    assert viewer.view is not None, (
        "the page has no view handle, so there is nothing a redraw could reach "
        "and the rest of this test would pass for the wrong reason"
    )
    renders_before, updates_before = len(viewer.renders), len(viewer.updates)

    status = _land_one_press(viewer)

    assert len(viewer.renders) > renders_before, (
        "the finished solve drew nothing (no plotter.render across the press): "
        "the page swapped its arrays and left the OLD picture on screen, so the "
        f"reader sees the dump they opened while the status says {status!r}"
    )
    assert len(viewer.updates) > updates_before, (
        "the finished solve never pushed a frame at the browser (no view.update "
        f"across the press): the status says {status!r} over a stale image"
    )
    assert "reload" not in status, (
        f"the page asks the reader to reload it ({status!r}): a manual reload is "
        "what a landed solve exists to make unnecessary"
    )
    assert "not refreshed" not in status, (
        f"the redraw was attempted and failed ({status!r}): the solve landed but "
        "the picture is still the previous dump"
    )


def test_a_finished_solve_puts_the_run_form_away(viewer) -> None:
    """Once a run is behind the page, the eight boxes describe a job nobody starts.

    The form is a form for the NEXT run; the dump that just landed IS a run, and
    its own numbers are fixed. Leaving the boxes on screen invites the reader to
    edit numbers that no longer reach anything - so the press clears the flag
    the card's ``v_if`` reads, and the page stops being one a press is refused.
    """
    assert viewer.boot_run_config_visible is False, (
        "the animated page booted with the Run Config form on screen: that page "
        "has a recording behind it, so the flag asserted below starts in the "
        "state the redraw would have produced anyway"
    )
    # A page that was STILL offering the form when its solve landed - the only
    # page where clearing it is observable at all.
    viewer.state.run_config_visible = True

    _land_one_press(viewer)

    assert viewer.state.run_config_visible is False, (
        "the solved page still shows the Run Config form: its eight boxes now "
        "describe a run that has already happened, and editing them reaches "
        "nothing"
    )
    assert viewer.state.solve_disabled is False, (
        "the solved page greys out Solve: the dump that landed brought a "
        "timeline with it, so the press it refused before is a press it can run"
    )


def test_the_refusal_is_one_shared_decision(viewer) -> None:
    """Boot, button and handler ask the SAME predicate - not three copies of it.

    ``_solve_refused_page`` is the whole of "may this page solve": no timeline
    and no Run Config form. The two failures worth pinning are a page with no
    data at all being refused (the form is its entire point) and a page with a
    timeline being refused (the timeline is where the result lands).

    The last assertion is the anti-drift one: the handler the button calls has
    to NAME that function, or the greyed-out button and the refusal inside the
    handler can disagree and nothing here would notice.
    """
    no_data = SimpleNamespace(
        plane_stack=None, volume_field=None, port_planes=None, animation=False
    )
    with_data = SimpleNamespace(
        plane_stack=None, volume_field=object(), port_planes=None, animation=False
    )

    assert app._run_config_form_shown(no_data) is True, (
        "a page with no field data at all is not offered the Run Config form"
    )
    assert app._run_config_form_shown(with_data) is False, (
        "a page already showing a field is offered the Run Config form: those "
        "eight boxes would describe a run nobody is going to start"
    )

    assert app._solve_refused_page(None, no_data) is False, (
        "a page with no data was refused: solving IS what that page is for"
    )
    assert app._solve_refused_page(None, with_data) is True, (
        "a static field snapshot with no form was allowed to solve: a new run "
        "has nowhere to land and there is not even a config to run one with"
    )
    assert app._solve_refused_page(4, with_data) is False, (
        "a page WITH a timeline was refused: the timeline is where the result "
        "of the press lands"
    )

    assert "_solve_refused_page" in viewer.trigger.__code__.co_names, (
        "the press handler does not consult the shared predicate (names: "
        f"{sorted(viewer.trigger.__code__.co_names)}), so what the button greys "
        "out and what the handler refuses can drift apart"
    )


@pytest.fixture(scope="module")
def bare_page(tmp_path_factory):
    """A SECOND boot - the page with no data at all - recorded as it is built.

    WHY A SECOND BOOT IS ALLOWED HERE, when this module exists because one
    process builds one panel: the LEFT PANEL is emitted once per process, but a
    boot after it still emits its widgets (``tests/test_poc_run_config_form.py``
    reads that boot for exactly this), and what is asserted below is the WIDGETS
    a data-less page gets. One process serves ONE state object, so this boot
    REPLACES what the dump-backed page left on it: the fixture is defined after
    every test that reads the viewer's page, and definition order is run order.

    The child is a STUB, not the shipped ``SolveJob``: what is pinned is that a
    data-less page may press AT ALL, and the argv that press builds is pinned in
    the viewer's tests above - spawning python twice to re-learn it would cost
    seconds and prove nothing. ``app.SolveJob`` is a module global read at call
    time, so the patch redirects the shipped path instead of re-implementing it,
    and it stays applied across the yield because the press happens inside it.
    """
    tmp = tmp_path_factory.mktemp("run_config_bare_solve")
    page = bb._page(tmp)
    records: list = []
    spawned: list = []

    class _StubJob:
        """``SolveJob``'s surface, minus the process: it never finishes."""

        def __init__(self, argv, cwd=None):
            self.argv = list(argv)
            self.cwd = cwd
            self.status = "running"
            self.returncode = None
            self.log = ""
            spawned.append(self)

        def run(self) -> None:
            self.status = "running"  # the worker thread's call; nothing to do

        def poll(self) -> str:
            return self.status

    patch = pytest.MonkeyPatch()
    patch.setattr(app, "SolveJob", _StubJob)
    patch.setattr(app, "LIVE_DUMP", tmp / "live" / "live_run.npz")
    try:
        with av._render_doubled():
            with form_recipe._recording(records):
                live = bb._boot(page["info"], page)
        av._silence_view(live)
        assert records, (
            "no widget call was recorded during the bare boot: the recorder did "
            "not reach the module the panel builds its widgets from, so the "
            "assertions below would read an empty list and prove nothing"
        )
        srv = av.trame_app.get_server()
        yield SimpleNamespace(
            state=live.state,
            trigger=_registered_trigger(srv.controller, "solve_start"),
            records=records,
            spawned=spawned,
            page=page,
        )
    finally:
        patch.undo()


def test_a_page_with_no_data_at_all_may_be_solved(bare_page) -> None:
    """The page the form exists for is a page whose Solve button WORKS.

    A form that is offered on a page whose press is refused is worse than no
    form: the reader fills it in and learns nothing. Both halves come from the
    one predicate, so the page that ARRIVES with the form must also arrive with
    a live button and a press that spawns a child.
    """
    assert bare_page.state.run_config_visible is True, (
        "the bare page did not arrive with its Run Config form: the flag the "
        "eight fields' v_if reads starts false, so the boxes would be hidden on "
        "the one page that has nothing else to offer"
    )
    assert bare_page.state.solve_disabled is False, (
        "the bare page greyed out Solve: this page has no field data, so a run "
        "is the only thing it could show"
    )

    bare_page.trigger()  # exactly what the button calls

    assert bare_page.state.solve_status.startswith("solving"), (
        "the press on a page with no data did not start a solve: "
        f"{bare_page.state.solve_status!r}"
    )
    assert bare_page.spawned, (
        "a page with no data validated a config and then spawned nothing "
        f"(status {bare_page.state.solve_status!r}): the form leads nowhere"
    )


def test_the_clim_select_is_not_gated_with_the_form(bare_page) -> None:
    """The gate is on the eight run fields, not on the Clim Mode select.

    Clim Mode changes how a volume is RENDERED, so it is meaningful exactly
    where there is a volume - gating it with the run form would make it dead in
    the place it matters. The eight run fields are the opposite kind of control
    (a run that has not happened) so they carry the ``v_if``; the select must
    not, and both halves are read off the widgets the boot actually emitted.
    """
    records = bare_page.records
    run_state_names = {state_name for state_name, _label, _field in app.RUN_CONFIG_FIELDS}

    clim = [
        record
        for record in records
        if record[0] == "VSelect"
        and _v_model(record)
        and _v_model(record)[0] == "volume_clim_mode"
    ]
    assert len(clim) == 1, (
        f"the Clim Mode select was emitted {len(clim)} times on a page with no "
        "field data: it is the run form that is gated, not the select"
    )
    assert _v_model(clim[0]) == ("volume_clim_mode", app.VOLUME_CLIM_DEFAULT), (
        f"the Clim Mode select binds {_v_model(clim[0])!r}, not the module "
        f"default {app.VOLUME_CLIM_DEFAULT!r}"
    )
    assert "v_if" not in clim[0][2], (
        "the Clim Mode select carries a v_if: it was gated with the run form, so "
        "it disappears on exactly the pages that have a volume to colour"
    )

    fields = [
        record
        for record in records
        if record[0] == "VTextField"
        and _v_model(record)
        and _v_model(record)[0] in run_state_names
    ]
    assert len(fields) == len(app.RUN_CONFIG_FIELDS), (
        f"{len(fields)} of the {len(app.RUN_CONFIG_FIELDS)} run fields were "
        "emitted on a page with no field data: the form is offered there, so a "
        "missing box is a run the reader cannot configure"
    )
    for record in fields:
        assert record[2].get("v_if") == ("run_config_visible", True), (
            f"the {_v_model(record)[0]!r} box is gated on "
            f"{record[2].get('v_if')!r}, not on the one flag the finished solve "
            "clears - so a solved page would keep offering a form for a run that "
            "has already happened"
        )

