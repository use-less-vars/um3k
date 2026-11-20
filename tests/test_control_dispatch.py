"""Which decorator a control is bound with, proved by driving the page.

WHY THIS FILE EXISTS.  A cut slider declares ``v_model=("cut_y", ...)``
(server/poc_app.py:10859) and ``("cut_z", ...)`` (:10869), so a drag reaches
the server as a WRITE to that state key.  ``@ctrl.set("cut_y")`` registers a
controller TRIGGER - a function the browser calls by name - and no state
listener at all, so a slider bound that way is dead, and nothing fails: a dead
slider and a working one look identical in a layout.
``@state.change("cut_y")`` (:16190) and ``@state.change("cut_z")`` (:16211)
are the decorators that hear the write.  The behavioural tests below drive the
live state, so they fail if a binding is ever reverted; the guards at the end
name the reversion in one line, for a reviewer reading a diff of a 20 000-line
module.

REAL, not simulated: ``run_web_vis`` boots for real - server, state,
controller, layout, and every handler the shipped decorators registered - and
the assertions read the live state object that page built.

DOUBLED: the OpenGL draw and the client push, and nothing else.  This image has
no EGL, no libOSMesa and no X server, so a real ``pyvista.Plotter.render``
segfaults the interpreter (``DISPLAY=`` / ``Failed to load EGL``); and there is
no browser for ``_push_still`` to reach.  Both are the device boundary, not the
code under test: no line of the handler is replaced or skipped.

WHAT PAGE THIS BOOTS.  ``run_web_vis`` - the page ``main`` returns and a
browser actually reaches (:20556, :20608), not the LEGACY ``run_web``
(:11006-11922) that nothing calls.  That repoint is DR-54 in
docs/design/defect_register.md, and it is the whole of this file's history
worth knowing: until it, the fixture booted the dead copy, so the assertions
proved handlers no browser could reach and a reversion of the SERVED page's
own listener (its copy at :16190 / :16211) left this file green.  The
measurement that made it a fixture change rather than a rewrite is
probes/probe_vis_boot.py: the served page boots headless by the same recipe and
its cut listeners can be driven and observed in-process.  The legacy page's own
tests went with the repoint - one page ships, so there is one page to cover.

The station class went the same way, for a harder reason: the shipped page has
NO station slider and registers no ``@state.change("station")``.  It states its
station once, as ``state.station_readout`` (:16134), so what is asserted here
is that sentence, not a control that does not exist.

One class per control: the boot's own flush, the station readout, the two cut
sliders, and the source guards.
"""

from __future__ import annotations

import ast
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

# In this image pyvista/trame/vtk live in the repo's own venv (bin/python is
# broken, the site-packages tree is not).  On a host where they are installed
# normally this directory is either absent or already on sys.path, so the block
# is inert there.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip(
    "pyvista", reason="pyvista is the web UI's renderer; this page needs it"
)
pytest.importorskip("trame.app", reason="trame serves the page")
pytest.importorskip(
    "trame.ui.vuetify3",
    reason="trame.ui.vuetify3 is what run_web builds its layout with",
)

import poc_app  # noqa: E402

#: The fixture dump's grid.  A legacy dump carries no study record, so the
#: station axis falls back to the stated uniform ``i * cell`` and the labels
#: become arithmetic: 0.1 mm cells, nine stations, 0.0000 .. 0.8000 mm.
CELL_M = 1e-4
N_ST = 9

#: The station the served page opens on: the MIDDLE captured plane
#: (server/poc_app.py:16128, ``n_st // 2``).  MEASURED on a boot of the served
#: page, not copied from the legacy page's ``n_st - 1``: 4 of 0..8, which the
#: readout prints one-based as "station 5/9".
BOOT_STATION = 4

#: The station sentence, byte for byte.  ``_station_text`` puts three spaces
#: and four decimals between the two numbers and the mm column is arithmetic
#: (0.1 mm cells).  Published as ``state.station_readout`` at :16134 and
#: rendered by the layout as ``{{ station_readout }}`` (:20066) - text, not a
#: corner annotation, which is why this page redraws with
#: ``station_label=False`` (:16158).
BOOT_READOUT = "station 5/9   x = 0.4000 mm"

#: The grid the cut row runs on: the same dump's ny and nz, and the pair the
#: boot settles on - the middle sample of each axis.
N_CUT_Y = 12
N_CUT_Z = 5
BOOT_CUT_Y = 6
BOOT_CUT_Z = 2

#: The cut label, byte for byte, at each index the tests pin; 0.1 mm cells, so
#: the mm column is arithmetic and ``_cut_text`` supplies the three spaces and
#: the four decimals.  Every one of these strings was READ OFF a boot of the
#: served page (probes/probe_vis_boot.py, then a measurement pass), not rebuilt
#: from the code's own f-strings: a label recomputed from the code proves only
#: that the code agrees with itself.
BOOT_LABEL = (
    "cut y = 7/12 (y = 0.6000 mm)   cut z = 3/5 (z = 0.2000 mm)   "
    "one sample each   (one stored x-plane of 9 captured stations, "
    "no interpolation)"
)
#: After the y cut moved to 3: 4/12 -> 0.3000 mm.
Y_3_LABEL = (
    "cut y = 4/12 (y = 0.3000 mm)   cut z = 3/5 (z = 0.2000 mm)   "
    "one sample each   (one stored x-plane of 9 captured stations, "
    "no interpolation)"
)
#: After the y cut was clamped to the last sample (12/12 -> 1.1000 mm).  Also
#: what an unparsable y value leaves on screen: the listener keeps the index it
#: last drew, which by then is this one.
Y_LAST_LABEL = (
    "cut y = 12/12 (y = 1.1000 mm)   cut z = 3/5 (z = 0.2000 mm)   "
    "one sample each   (one stored x-plane of 9 captured stations, "
    "no interpolation)"
)
#: After the z cut moved to (or was clamped to) the last sample, y held on the
#: middle: 5/5 -> 0.4000 mm.
Z_LAST_LABEL = (
    "cut y = 7/12 (y = 0.6000 mm)   cut z = 5/5 (z = 0.4000 mm)   "
    "one sample each   (one stored x-plane of 9 captured stations, "
    "no interpolation)"
)

#: ``state.view_label`` after the y cut moved to 3, byte for byte - the served
#: page's own row summary (:11640 is the legacy page's, which is dead).
Y_3_VIEW_LABEL = (
    "|Ez| volume: 9 captured x-planes, x = 0.0000 .. 0.8000 mm  "
    "cuts: y = 0.3000 mm (j 4/12), z = 0.2000 mm (k 3/5)"
)

#: What the boot's first flush pushes, as a SET: the flush runs the listener
#: set, whose iteration order is not fixed.  MEASURED, not guessed - one push
#: per pending write the layout left behind, and none of them named "station".
BOOT_PUSHES = ["boot", "clim", "clim_resend", "cut", "cut", "family", "seek"]


class _Stop(Exception):
    """Unwinds ``run_web`` just before it enters the event loop."""


def _write_dump(path: Path) -> Path:
    """A minimal dump the ``load_dump`` ingest path accepts verbatim."""
    rng = np.random.default_rng(0)
    np.savez(
        path,
        plane_ez=rng.normal(size=(N_ST, 12, 5)),
        nstep=np.array(6),
        nx=np.array(N_ST),
        ny=np.array(12),
        nz=np.array(5),
        cell_m=np.array(CELL_M),
    )
    return path


def _boot(tmp_path: Path) -> tuple:
    """Run ``run_web_vis`` up to the point it would call ``server.start``.

    ``run_web_vis`` is the page ``main`` serves (:20556, :20608).  Its 4th
    positional is ``fps``, not a station (:15426-15438), so the dump and the
    frame rate are the whole of the call and every other knob defaults - the
    same call ``probes/probe_vis_boot.py`` boots.  The rest is the recipe
    ``tests/test_poc_playback.py::_boot_web`` uses: patch
    ``trame.app.get_server`` so the live server object escapes, and make
    ``start`` raise so the event loop is never entered.  ``run_web_vis``
    imports ``get_server`` inside the function, so patching the module
    attribute before the call is what it sees.  ``Plotter.render`` is
    doubled for the reason the playback tests double it: this image has no
    EGL, no libOSMesa and no X server, so a real render segfaults the
    interpreter.
    """
    import pyvista
    import trame.app as trame_app

    info = poc_app.load_dump(_write_dump(tmp_path / "dump.npz"))
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
            poc_app.run_web_vis(info, "127.0.0.1", 8999, poc_app.DEFAULT_FPS)
    finally:
        pyvista.Plotter.render = real_render
        trame_app.get_server = real_get_server

    assert "srv" in box, (
        "run_web_vis never reached server.start(): it returned early "
        "(missing web dependency) so its layout was never built"
    )
    return box["srv"]


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    """The live page one boot built, plus every client push it attempted.

    ``_push_still`` is replaced for the whole module: it is the push to a
    browser that is not there, and counting its calls is how "the handler ran
    once" is told from "the handler ran twice".  It is the module function
    the handler resolves at call time, so the substitute sees the shipped call.
    """
    pushes: list = []
    real_push = poc_app._push_still
    poc_app._push_still = lambda view, name: pushes.append(name) or True
    try:
        srv = _boot(tmp_path_factory.mktemp("control_dispatch"))
        state = srv.state
        assert not state.is_ready, (
            "the boot double skipped the port, so the state must still be "
            "unready; a ready state here means ready() ran twice"
        )
        # The one framework step the boot double skips: no port was bound, so
        # ``State.flush()`` refuses (``_status.skip_flushing`` while the state
        # is not ready) and a refused flush runs no ``@state.change`` listener.
        # ``ready()`` is trame's own call at port bind
        # (trame_server/protocol.py:105).
        state.ready()
        boot_pushes = list(pushes)
        assert state.is_ready, (
            "trame's state.ready() did not mark this page ready, so no flush "
            "can run a listener"
        )
        # The cut indices, the cut label and the station sentence the boot
        # itself left, read here: after its first flush, before any test
        # writes a key.  ``_settle_row`` pins both cut indices, so a test
        # that read them afterwards would be asserting the value it had
        # just written.
        boot_cut_y = state.cut_y
        boot_cut_z = state.cut_z
        boot_cut_label = state.cut_label
        boot_readout = state.station_readout
        yield SimpleNamespace(
            state=state,
            pushes=pushes,
            boot_pushes=boot_pushes,
            boot_cut_y=boot_cut_y,
            boot_cut_z=boot_cut_z,
            boot_cut_label=boot_cut_label,
            boot_readout=boot_readout,
        )
    finally:
        poc_app._push_still = real_push


def _cut_event(page, value) -> list:
    """Write ``value`` to the y cut and flush: one client event's pushes."""
    before = len(page.pushes)
    page.state.cut_y = value
    page.state.flush()
    return page.pushes[before:]


def _settle_row(page, cut_y, cut_z) -> list:
    """Pin both cut axes and flush: the row the z tests start from.

    The one page is shared in file order, so ``cut_y`` is left on 11 by the y
    class's clamp and ``cut_z`` wherever a previous z test left it.  Writing
    both keys makes every z test independent of that order.  The pushes this
    produces are the row moving into place, not the event under test, so they
    are returned only so a caller can assert on them if it wants to.
    """
    before = len(page.pushes)
    page.state.cut_y = cut_y
    page.state.cut_z = cut_z
    page.state.flush()
    return page.pushes[before:]


def _cut_z_event(page, value) -> list:
    """Write ``value`` to the z cut and flush: one client event's pushes."""
    before = len(page.pushes)
    page.state.cut_z = value
    page.state.flush()
    return page.pushes[before:]


def _station_write(page, value) -> list:
    """Write ``value`` to ``state.station`` and flush: one event's pushes.

    The served page has no station control at all (see ``TestStationReadout``),
    so this exists to show that the write goes nowhere - not to drive a
    handler.  The flush is what would run one - trame refuses to flush while
    the state is not ready - so a bare write would only sit pending.
    """
    before = len(page.pushes)
    page.state.station = value
    page.state.flush()
    return page.pushes[before:]


class TestBootFlush:
    """What the boot's first flush runs, on the page ``main`` serves."""

    def test_the_boot_flush_pushes_one_still_per_pending_listener(self, page):
        """The boot fire, pinned: seven pushes, named, and no station.

        A pending write survives to the first flush (trame_server/state.py
        225-236), and that flush is trame's own ``ready()`` at port bind
        (trame_server/protocol.py:105), by which time every listener IS
        registered; a layout default registers its key for the listeners
        whatever that write's context was (state.py:298-306), so each of those
        listeners runs exactly once and pushes once.  One push per name, from
        the shipped call sites: "boot" is the page's own first draw (:17647),
        "seek" the frame listener (:17713), "family" the other-family box
        (:18319), "clim" and "clim_resend" the clim-mode listener's own pair
        (:18182, :18191), and one "cut" for each bound cut axis
        (:16190, :16211).  There is NO "station": this page has no station
        control at all - it states its station once, in
        ``state.station_readout`` (:16134) - so the legacy page's third push
        has no counterpart here.  A SET, not an order: the flush runs the
        listener set, whose iteration order is not fixed.
        """
        assert sorted(page.boot_pushes) == BOOT_PUSHES, (
            f"the boot flush pushed {sorted(page.boot_pushes)!r}, not the "
            f"measured {BOOT_PUSHES!r}: one still per pending listener, and "
            "no station push, because this page has no station control"
        )


class TestStationReadout:
    """The shipped page has no station slider: it states its station ONCE.

    ``state.station`` is set at boot (:16128, the middle captured plane) and
    ``state.station_readout`` is built from it by the helper the legacy page's
    corner label used (:16134).  No ``@state.change("station")`` is registered
    anywhere in ``run_web_vis``, so nothing this page offers can re-state it.
    The one other write of that key (:16036, the volume-layer branch) belongs
    to a page with no x-plane stack; this fixture IS a stack (:16097), so that
    write never runs here and there is nothing about it to assert.
    """

    def test_the_readout_names_the_middle_captured_station_at_boot(self, page):
        """The boot's own station and sentence, before anything writes."""
        assert page.state.station == BOOT_STATION, page.state.station
        assert page.boot_readout == BOOT_READOUT, page.boot_readout
        assert page.state.station_readout == BOOT_READOUT

    def test_nothing_the_page_offers_changes_the_readout(self, page):
        """No listener, no push, no new sentence - that is the whole truth.

        ``_change_callbacks`` is trame's own registry of ``@state.change``
        targets - the map ``probes/probe_vis_boot.py`` read to find the cut
        listeners - and ``station`` is absent from it, which is WHY a write to
        the key cannot reach anything.  Asserted rather than assumed: if a
        station control is ever added to this page, the readout has to be
        rebuilt by its listener, and this is where that is said out loud.
        """
        assert "station" not in page.state._change_callbacks, (
            'a @state.change("station") listener now exists on the served '
            "page: the readout asserted below must then be rebuilt by it"
        )
        assert _station_write(page, 3) == [], (
            "writing state.station pushed a still, so something on this page "
            "now hears it"
        )
        assert page.state.station_readout == BOOT_READOUT, (
            "the readout followed state.station, so it is not the boot's own "
            "sentence any more"
        )


def _served_source() -> str:
    """The source of the page ``main`` serves, and nothing else.

    WHY a slice and not a search of the whole file: ``run_web``
    (:11006-11922) is an unreachable LEGACY copy of this code carrying the
    SAME decorator strings, so a whole-file search cannot see a reversion of
    the served copy - the dead copy's identical line still matches, and that
    is how the first version of these guards passed while proving nothing.
    The slice is ``run_web_vis``'s own extent, taken from its AST
    ``end_lineno`` (:20303), so a reversion of :16190 or :16211 - or of
    :16084 / :16092 on the volume branch - fails here.
    """
    source = Path(poc_app.__file__).read_text()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == "run_web_vis":
            if node.end_lineno is None:  # pragma: no cover - always set
                break
            return "\n".join(
                source.splitlines()[node.lineno - 1:node.end_lineno]
            )
    raise AssertionError(
        "run_web_vis is gone from server/poc_app.py: the page main() returns "
        "(server/poc_app.py:20556, :20608) no longer exists in the module"
    )


class TestBindingReversionGuard:
    """One-line guards on the decorators, because this failure is SILENT.

    The behavioural tests above are the real coverage: they drive the live
    state, so they fail if a binding is reverted.  These guards exist because
    a reverted decorator produces no error, no warning and no visible change
    to the layout - the slider simply stops doing anything - and a reviewer
    reading a diff of a twenty-thousand-line module should be told in one
    line which decorator is load-bearing.
    """

    def test_the_y_cut_listener_is_bound_to_the_state_not_the_controller(self):
        served = _served_source()
        assert '@state.change("cut_y")' in served, (
            "the y cut listener is no longer registered with "
            '@state.change("cut_y") (server/poc_app.py:16190, and the volume '
            "branch's own copy at :16084): the slider is bound to state.cut_y "
            "through v_model, so a controller trigger hears nothing and the "
            "slider is dead again"
        )
        assert '@ctrl.set("cut_y")' not in served, (
            '@ctrl.set("cut_y") is back in the served page: it registers a '
            "controller trigger, not a state listener, so a drag would stop "
            "reaching the handler"
        )

    def test_the_z_cut_listener_is_bound_to_the_state_not_the_controller(self):
        served = _served_source()
        assert '@state.change("cut_z")' in served, (
            "the z cut listener is no longer registered with "
            '@state.change("cut_z") (server/poc_app.py:16211, and the volume '
            "branch's own copy at :16092): the slider is bound to state.cut_z "
            "through v_model, so a controller trigger hears nothing and the "
            "slider is dead again"
        )
        assert '@ctrl.set("cut_z")' not in served, (
            '@ctrl.set("cut_z") is back in the served page: it registers a '
            "controller trigger, not a state listener, so a drag would stop "
            "reaching the handler"
        )

    def test_the_station_is_stated_once_and_never_listened_for(self):
        """``TestStationReadout`` rests on this, so guard the line it rests on.

        Both halves are facts about the SERVED page: the sentence is built at
        :16134, and no ``@state.change("station")`` exists in ``run_web_vis``
        to rebuild it - which is why nothing on this page can change it.
        """
        served = _served_source()
        assert "state.station_readout = _station_text(" in served, (
            "the station readout is no longer built on the page that ships: "
            "server/poc_app.py:16134 is the only line that writes it"
        )
        assert '@state.change("station")' not in served, (
            "a station listener is back on the served page: the page has no "
            "station slider, so the readout it states once (:16134) would "
            "then need rebuilding there, and TestStationReadout must change"
        )


class TestCutYSlider:
    """``v_model=("cut_y", ...)`` reaches ``_on_cut_y`` (poc_app.py:16190)."""

    def test_the_row_opens_on_the_middle_sample(self, page):
        """The boot's own cut and label, before anything drags them."""
        assert page.boot_cut_y == BOOT_CUT_Y, (
            f"the page opened on cut_y={page.boot_cut_y!r}, not the middle "
            f"sample of {N_CUT_Y} (the dump's ny)"
        )
        assert page.boot_cut_label == BOOT_LABEL, page.boot_cut_label

    def test_a_chosen_cut_moves_and_relabels_the_row(self, page):
        """THE FIX: a write to ``state.cut_y`` moves the cut and redraws.

        Under ``@ctrl.set("cut_y")`` this is the test that fails: the write is
        swallowed, the row keeps its old numbers and nothing is pushed.
        """
        _settle_row(page, BOOT_CUT_Y, BOOT_CUT_Z)
        assert _cut_event(page, 3) == ["cut"], (
            "one drag must push exactly one still and no more"
        )
        assert page.state.cut_y == 3
        assert page.state.cut_label == Y_3_LABEL, page.state.cut_label
        assert page.state.view_label == Y_3_VIEW_LABEL, page.state.view_label

    def test_a_clamped_cut_is_drawn_once(self, page):
        """The write-back cannot re-enter the handler for one client event."""
        assert _cut_event(page, 999) == ["cut"], (
            "a clamped drag pushed more than one still: the write-back in "
            "_on_cut_change re-entered the listener inside the same flush"
        )
        assert page.state.cut_y == N_CUT_Y - 1, "the clamp to n_j - 1 is gone"
        assert page.state.cut_label == Y_LAST_LABEL, page.state.cut_label

    def test_an_unparsable_cut_keeps_the_cut_and_draws_once(self, page):
        """A string from the client cannot move or wedge the cut.

        The junk value has already landed in ``state.cut_y`` by the time the
        listener runs (trame_server/state.py:420-424), which is why the
        fallback reads the index the page last drew (``handles["cut_last_y"]``,
        :16187) instead of ``cut_y``.
        """
        assert _cut_event(page, "junk") == ["cut"], page.pushes[-3:]
        assert page.state.cut_y == N_CUT_Y - 1, page.state.cut_y
        assert page.state.cut_label == Y_LAST_LABEL, page.state.cut_label


class TestCutZSlider:
    """``v_model=("cut_z", ...)`` reaches ``_on_cut_z`` (poc_app.py:16211)."""

    def test_the_row_opens_with_z_on_the_middle_sample(self, page):
        """The index is the boot's own; the label is the settled row's.

        ``page.boot_cut_y`` and ``page.boot_cut_z`` are recorded by the
        fixture at the boot's first flush and written by no test, so the two
        index assertions are about the page opening on the middle sample.
        The label is then asserted byte for byte on the row the shared page is
        pinned to here: the y class above left ``cut_y`` on its clamp, so a
        label read now would say so.
        """
        assert page.boot_cut_y == BOOT_CUT_Y, (
            f"the page opened on cut_y={page.boot_cut_y!r}, not the middle "
            f"sample of {N_CUT_Y} (the dump's ny)"
        )
        assert page.boot_cut_z == BOOT_CUT_Z, (
            f"the page opened on cut_z={page.boot_cut_z!r}, not the middle "
            f"sample of {N_CUT_Z} (the dump's nz)"
        )
        _settle_row(page, BOOT_CUT_Y, BOOT_CUT_Z)
        assert page.state.cut_label == BOOT_LABEL, page.state.cut_label

    def test_a_chosen_z_cut_moves_and_relabels_the_row(self, page):
        """THE FIX: a write to ``state.cut_z`` moves the cut and redraws.

        Under ``@ctrl.set("cut_z")`` this is the test that fails: the write is
        swallowed, the row keeps its old numbers and nothing is pushed.
        """
        _settle_row(page, BOOT_CUT_Y, BOOT_CUT_Z)
        assert _cut_z_event(page, N_CUT_Z - 1) == ["cut"], (
            "one drag must push exactly one still and no more"
        )
        assert page.state.cut_z == N_CUT_Z - 1
        assert page.state.cut_y == BOOT_CUT_Y, (
            "moving the z cut dragged the y cut with it"
        )
        assert page.state.cut_label == Z_LAST_LABEL, page.state.cut_label

    def test_a_clamped_z_cut_is_drawn_once(self, page):
        """The write-back cannot re-enter the handler for one client event."""
        _settle_row(page, BOOT_CUT_Y, BOOT_CUT_Z)
        assert _cut_z_event(page, 999) == ["cut"], (
            "a clamped drag pushed more than one still: the write-back in "
            "_on_cut_change re-entered the listener inside the same flush"
        )
        assert page.state.cut_z == N_CUT_Z - 1, "the clamp to n_k - 1 is gone"
        assert page.state.cut_label == Z_LAST_LABEL, page.state.cut_label

    def test_an_unparsable_z_cut_keeps_the_cut_and_draws_once(self, page):
        """A string from the client cannot move or wedge the z cut.

        The junk value has already landed in ``state.cut_z`` by the time the
        listener runs (trame_server/state.py:420-424), which is why the
        fallback reads the index the page last drew (``handles["cut_last_z"]``,
        :16188) instead of ``cut_z``.
        """
        _settle_row(page, BOOT_CUT_Y, N_CUT_Z - 1)
        assert _cut_z_event(page, "junk") == ["cut"], page.pushes[-3:]
        assert page.state.cut_z == N_CUT_Z - 1, page.state.cut_z
        assert page.state.cut_label == Z_LAST_LABEL, page.state.cut_label
