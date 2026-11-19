"""Which decorator a control is bound with, proved by driving the page.

WHY THIS FILE EXISTS.  A slider declares ``v_model=("station", station)``
(server/poc_app.py:11692), so a drag reaches the server as a WRITE to
``state.station``.  ``@ctrl.set("station")`` registers a controller TRIGGER - a
function the browser calls by name - and no state listener at all, so a slider
bound that way is dead, and nothing fails: a dead slider and a working one look
identical in a layout.  ``@state.change("station")`` (server/poc_app.py:11837)
is the decorator that hears the write.  The behavioural test below drives the
live state, so it fails if the binding is ever reverted; the guard at the end
names the reversion in one line, for a reviewer reading a diff of a
20 000-line module.

REAL, not simulated: ``run_web`` boots for real - server, state, controller,
layout, and every handler the shipped decorators registered - and the
assertions read the live state object that page built.

DOUBLED: the OpenGL draw and the client push, and nothing else.  This image has
no EGL, no libOSMesa and no X server, so a real ``pyvista.Plotter.render``
segfaults the interpreter (``DISPLAY=`` / ``Failed to load EGL``); and there is
no browser for ``_push_still`` to reach.  Both are the device boundary, not the
code under test: no line of the handler is replaced or skipped.

One class per control; the station slider is the first.
"""

from __future__ import annotations

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
BOOT_STATION = N_ST - 1

#: The corner label, byte for byte (``_station_text``: three spaces, 4 dp).
OPENING_LABEL = "station 9/9   x = 0.8000 mm"
STATION_3_LABEL = "station 4/9   x = 0.3000 mm"
STATION_4_LABEL = "station 5/9   x = 0.4000 mm"


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
    """Run ``run_web`` up to the point it would call ``server.start``.

    Same recipe as ``tests/test_poc_playback.py::_boot_web``: wrap
    ``trame.app.get_server`` so the live server object escapes, and make
    ``start`` raise so the event loop is never entered.  ``run_web`` imports
    ``get_server`` inside the function, so patching the module attribute before
    the call is what it sees.  ``Plotter.render`` is doubled for the reason
    the playback tests double it: this image has no EGL, no libOSMesa and no X
    server, so a real render segfaults the interpreter.
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
            poc_app.run_web(info, "127.0.0.1", 8999, BOOT_STATION)
    finally:
        pyvista.Plotter.render = real_render
        trame_app.get_server = real_get_server

    assert "srv" in box, (
        "run_web never reached server.start(): it returned early (missing web "
        "dependency) so its layout was never built"
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
        yield SimpleNamespace(
            state=state, pushes=pushes, boot_pushes=boot_pushes
        )
    finally:
        poc_app._push_still = real_push


def _cut_event(page, value) -> list:
    """Write ``value`` to the y cut and flush: one client event's pushes."""
    before = len(page.pushes)
    page.state.cut_y = value
    page.state.flush()
    return page.pushes[before:]


def _station_event(page, value) -> list:
    """Write ``value`` to the station and flush: one client event's pushes.

    The flush is what runs the listener - trame refuses to flush while the
    state is not ready - so a bare write would only sit pending.
    """
    before = len(page.pushes)
    page.state.station = value
    page.state.flush()
    return page.pushes[before:]


class TestStationSlider:
    """``v_model=("station", station)`` reaches ``_on_station_change``."""

    def test_the_page_opens_on_the_station_it_was_asked_for(self, page):
        """The boot's own station and label, before anything touches them."""
        assert page.state.station == BOOT_STATION
        assert page.state.station_label == OPENING_LABEL

    def test_the_first_flush_fires_the_handler_once_with_the_opening_station(
        self, page
    ):
        """The boot fire, pinned: one call, one push, same station on screen.

        A pending write survives to the first flush (state.py:225-236), and
        flush is trame's own ``ready()`` at port bind, by which time this
        listener IS registered; the slider's ``v_model`` default registers the
        key for listeners whatever the write's context was (state.py:298-306),
        so exactly one call is expected.  It is handed the station already
        drawn, which is why neither the value nor the label moves - the cost is
        one repeat of the draw, not a visible jump.
        """
        # cut_y is bound with @state.change as well, and its opening write fires
        # on this same first flush, so the boot pushes a "cut" beside the
        # "station".  A SET, not an order: the flush runs the listener set, whose
        # iteration order is not fixed.
        assert sorted(page.boot_pushes) == ["cut", "station"], (
            f"the boot flush pushed {page.boot_pushes!r}: the station listener "
            "and the cut_y listener are the two the boot write leaves pending"
        )
        assert page.state.station == BOOT_STATION
        assert page.state.station_label == OPENING_LABEL

    def test_a_chosen_station_moves_and_relabels_the_corner(self, page):
        """THE FIX: a write to ``state.station`` now reaches the handler.

        Under ``@ctrl.set("station")`` this test is the one that fails: the
        write would be swallowed, the label would stay on station 9 and nothing
        would be pushed.
        """
        assert _station_event(page, 3) == ["station"]
        assert page.state.station == 3, (
            "the handler did not take the client's station: the slider is "
            "bound to state.station, so a controller trigger hears nothing"
        )
        assert page.state.station_label == STATION_3_LABEL

    def test_a_coerced_station_is_clamped_and_drawn_once(self, page):
        """The write-back cannot re-enter the handler for one client event.

        A float or an out-of-range value is coerced, and the coerced value
        DIFFERS from the one just pushed: the write-back inside the handler is
        then a new pending key (state.py:225-236) and the flush loop
        (state.py:454-469) would run the handler a second time - two
        ``_focus`` and two ``_push_still`` for one drag.  One push per event is
        what says the write-back is guarded.
        """
        assert _station_event(page, 3.6) == ["station"]
        assert page.state.station == 4
        assert page.state.station_label == STATION_4_LABEL

        assert _station_event(page, 99) == ["station"]
        assert page.state.station == BOOT_STATION
        assert page.state.station_label == OPENING_LABEL


class TestBindingReversionGuard:
    """A one-line guard on the decorator, because this failure is SILENT.

    The behavioural test above is the real coverage: it drives the live state,
    so it fails if the binding is reverted.  This guard exists because a
    reverted decorator produces no error, no warning and no visible change to
    the layout - the slider simply stops doing anything - and a reviewer
    reading a diff of a twenty-thousand-line module should be told in one line
    which decorator is load-bearing.
    """

    def test_the_station_slider_is_bound_to_the_state_not_the_controller(self):
        source = Path(poc_app.__file__).read_text()
        assert '@state.change("station")' in source, (
            'the station handler is no longer registered with '
            '@state.change("station"): the slider is bound to state.station '
            "through v_model, so a controller trigger hears nothing and the "
            "slider is dead again"
        )
        assert '@ctrl.set("station")' not in source, (
            '@ctrl.set("station") is back: it registers a controller trigger, '
            "not a state listener, so a drag would stop reaching the handler"
        )


class TestCutYSlider:
    """``v_model=("cut_y", cut_y)`` reaches ``_on_cut_y`` (poc_app.py:11335)."""

    def test_the_row_opens_on_the_middle_sample(self, page):
        """The boot's own cut, before anything drags it."""
        assert page.state.cut_y == 6, (
            f"the page opened on cut_y={page.state.cut_y!r}, not the middle "
            "sample of 12 (the legacy dump's ny)"
        )
        assert "7/12" in page.state.cut_label, page.state.cut_label

    def test_a_chosen_cut_moves_and_relabels_the_row(self, page):
        """THE FIX: a write to ``state.cut_y`` moves the cut and redraws.

        Under ``@ctrl.set("cut_y")`` this is the test that fails: the write is
        swallowed, the row keeps its old numbers and nothing is pushed.
        """
        assert _cut_event(page, 3) == ["cut"], (
            "one drag must push exactly one still and no more"
        )
        assert page.state.cut_y == 3
        assert "4/12" in page.state.cut_label, page.state.cut_label
        assert "4/12" in str(page.state.view_label), page.state.view_label

    def test_a_clamped_cut_is_drawn_once(self, page):
        """The write-back cannot re-enter the handler for one client event."""
        assert _cut_event(page, 999) == ["cut"], (
            "a clamped drag pushed more than one still: the write-back in "
            "_on_cut_change re-entered the listener inside the same flush"
        )
        assert page.state.cut_y == 11, "the clamp to n_j - 1 is gone"

    def test_an_unparsable_cut_keeps_the_cut_and_draws_once(self, page):
        """A string from the client cannot move or wedge the cut.

        The junk value has already landed in ``state.cut_y`` by the time the
        listener runs (trame_server/state.py:420-424), which is why the
        fallback reads the index the page last drew instead of ``cut_y``.
        """
        assert _cut_event(page, "junk") == ["cut"], page.pushes[-3:]
        assert page.state.cut_y == 11, page.state.cut_y
        assert "12/12" in page.state.cut_label, page.state.cut_label

    def test_the_cut_slider_is_bound_to_the_state_not_the_controller(self):
        """The one-line guard, for the same silent-failure reason as station."""
        source = Path(poc_app.__file__).read_text()
        assert '@state.change("cut_y")' in source, (
            'the cut_y handler is no longer registered with @state.change: the '
            "slider is bound to state.cut_y through v_model, so a controller "
            "trigger hears nothing and the slider is dead again"
        )
        assert '@ctrl.set("cut_y")' not in source, (
            '@ctrl.set("cut_y") is back: it registers a controller trigger, not '
            "a state listener, so a drag would stop reaching the handler"
        )
