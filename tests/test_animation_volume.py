"""Headless proof that the ANIMATION page's |E| volume layer says what it claims.

REAL, not simulated: ``run_web_vis`` boots for real (state, controller, every
``@ctrl.set(...)`` is the shipped decorator, the plotter is the page's own
``pyvista.Plotter``) and the handler exercised below is the object the page's
``NEXT >>`` button calls.  ``_draw_volume_layer`` is a closure inside
``run_web_vis``, so it is read out of the live closure cells - the function run
here IS the function the button runs, closed over the SHIPPED ``handles``,
``page`` and ``plotter``, not a copy and not a re-implementation.

DOUBLED: the OpenGL / client-push boundary only - ``pyvista.Plotter.render`` and
``update`` on the view ``plotter_ui`` returns.  This image has no EGL, no
libOSMesa and no X server, so a real ``render()`` segfaults the interpreter.
Everything that decides what is in the scene (``add_volume``, ``add_mesh``,
``remove_actor``, the mapper's ``scalar_range``) is the real thing, which is what
lets these tests read the colour range OFF THE ACTOR rather than off a promise.

THE DUMP: a synthetic ``emfit.vis/2`` file whose ``e_abs_volume`` is saved on a
DELIBERATELY IRREGULAR step axis (``e_abs_volume_step_index = [1, 3, 7, 11]`` at
``e_abs_volume_stride = 3``) and whose frames differ by a factor 1e6 in
amplitude.  Both are chosen so a wrong implementation is visible, not merely
different: ``step // stride`` and the recorded step axis disagree at two of the
four frames, and a per-frame colour range differs from the whole-recording one
by three decades.
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
        # the same two entries tests/test_poc_playback.py adds, so `import
        # poc_app` resolves from server/poc_app.py
        sys.path.insert(0, _p)

# In this image pyvista/trame/vtk live in the repo's own venv (its bin/python is
# broken, the site-packages tree is not).  Inert where they are installed
# normally.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip("pyvista", reason="the volume layer is drawn with pyvista")
pytest.importorskip("trame.app", reason="trame serves the page")
pytest.importorskip(
    "trame.ui.vuetify3", reason="trame.ui.vuetify3 is what run_web_vis builds"
)

import poc_app as app  # noqa: E402  (after the importorskip guards)
import trame.app as trame_app  # noqa: E402  (ditto; trame.app is guarded above)
import trame_server.core as trame_server  # noqa: E402  (where Server.start lives)

#: The pristine callables, captured at import before anything here has patched
#: them.  The teardown check below compares against these by IDENTITY.
PRISTINE_GET_SERVER = trame_app.get_server
PRISTINE_SERVER_START = trame_server.Server.start

#: id(server) -> (server, the instance-level ``start`` it had before we booted),
#: so the teardown check can look inside the very instance the page used.
_BOOTED_SERVERS: dict = {}

#: The animation's own axes.  ``frame_index`` is what the volume's step axis is
#: mapped THROUGH, so it is the array the two mappings under test disagree on.
NT, NX, NY, NZ, NT_X = 4, 8, 6, 5, 3
FRAME_INDEX = (0, 3, 6, 9)
FRAME_INDEX_XCUT = (0, 9, 18)

#: The recorded |E| volume axis: four samples of a 12-step run, saved every 3rd
#: step.  Irregular on purpose (``1, 3, 7, 11`` - the 5th and 6th steps were
#: never written), so ``step // 3`` and this array answer differently.
VOLUME_STEPS = (1, 3, 7, 11)
VOLUME_STRIDE = 3

#: The frame whose |E| peak is 1e3 above the rest, and the one 1e6 below it.
LOUD_FRAME = 1
QUIET_FRAME = 3

FPS = 25
TRIGGER_NAME = "step_fwd"


class _Stop(Exception):
    """Unwinds ``run_web_vis`` just before it enters the event loop."""


def _payload(*, with_volume: bool) -> dict:
    """A minimal ``emfit.vis/2`` dump, the field set tests/test_poc_playback.py uses.

    ``with_volume=False`` is the same file minus the three ``e_abs_volume*`` keys:
    the shape ``load_vis`` reads as "this dump carries no volume", which is the
    normal case (only a run asked for with ``--volume-stride`` writes one).
    """
    rng = np.random.default_rng(0)
    payload = {
        "schema": app.VIS_SCHEMA,
        "ez_ycut": rng.normal(size=(NT, NX, NZ)),
        "ez_xcut_near": rng.normal(size=(NT_X, NY, NZ)),
        "ez_xcut_far": rng.normal(size=(NT_X, NY, NZ)),
        "t_ns": np.arange(NT) * 1e-3,
        "frame_index": np.array(FRAME_INDEX),
        "frame_index_xcut": np.array(FRAME_INDEX_XCUT),
        "x_mm": np.linspace(0.0, 7.0, NX),
        "y_mm": np.linspace(-1.0, 1.0, NY),
        "z_mm": np.linspace(0.0, 2.0, NZ),
        "nx": np.array(NX),
        "ny": np.array(NY),
        "nz": np.array(NZ),
        "nt": np.array(NT),
        "nt_x": np.array(NT_X),
        "dt_s": np.array(1e-13),
        "cell_m": np.array(1e-5),
        "j_cut": np.array(3),
        "dump_stride": np.array(VOLUME_STRIDE),
        "nsteps": np.array(12),
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
    if with_volume:
        # |E| on the NODE grid, (n, nx, ny, nz) - see load_vis's validation.
        volume = np.abs(rng.normal(size=(len(VOLUME_STEPS), NX, NY, NZ))) * 1e-3
        volume[LOUD_FRAME] *= 1e3
        volume[QUIET_FRAME] *= 1e-6
        payload["e_abs_volume"] = volume.astype(np.float32)
        payload["e_abs_volume_step_index"] = np.array(VOLUME_STEPS, dtype=int)
        payload["e_abs_volume_stride"] = np.array(VOLUME_STRIDE)
    return payload


def _foreign_get_server_holders() -> list:
    """Loaded modules holding a ``get_server`` that is not the real one.

    ``trame_pyvista.ui`` and ``trame_pyvista.ui.base_viewer`` do ``from trame.app
    import get_server`` when they are first imported - which happens inside a
    boot - and go on calling that cached name.  Whatever a previous module left
    in those names is what this boot would resolve through.
    """
    holders = []
    for mod in list(sys.modules.values()):
        held = getattr(mod, "get_server", None)
        if held is not None and held is not PRISTINE_GET_SERVER:
            holders.append(mod)
    return holders


def _boot(tmp_path: Path, *, with_volume: bool) -> SimpleNamespace:
    """Run ``run_web_vis`` up to the point it would call ``server.start``.

    Same recipe as artifacts/verify_wd.py and tests/test_poc_playback.py: let
    the page build its server for real, and make ``start`` raise so the event
    loop is never entered.  The server object is not hunted for separately: it
    is whatever ``start`` was called on.

    WHY the double goes on the CLASS and not on ``trame.app.get_server``: this
    page reaches the server through ``trame_pyvista.ui.get_viewer``, and that
    module does ``from trame.app import get_server`` at ITS import time - which
    lands on the first boot here - then calls that cached reference forever
    after.  A fake installed on the module attribute is therefore out of reach
    of this function: ``trame_pyvista`` keeps it, hands it back on every later
    boot, re-installs its stop-double on the shared server AFTER the caller has
    installed its own, and the caller's ``contextlib.suppress(_Stop)`` is a
    different module's ``_Stop`` so it has to miss it.  That is how a double
    left here used to break tests/test_poc_playback.py from the outside.
    ``Server.start`` is resolved on the class at call time, so one patch covers
    every server object and every cached reference, and it is undone
    unconditionally on the way out.
    """
    path = tmp_path / ("volume.npz" if with_volume else "no_volume.npz")
    np.savez(path, **_payload(with_volume=with_volume))
    info = app.load_vis(path)

    stopped: list = []

    def _no_start(*_a, **_k):
        stopped.append(True)
        raise _Stop()

    srv = trame_app.get_server()
    #: Whatever another module left parked on the instance before we booted, put
    #: back untouched on the way out.
    shadow = vars(srv).get("start")

    # pytest's own MonkeyPatch: everything ``setattr`` touched is put back when
    # the block exits, exception or not.  The ``monkeypatch`` fixture is not
    # usable here because ``volume_page`` is module-scoped and boots from this
    # helper.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(trame_server.Server, "start", _no_start)
        # Third-party modules bind ``get_server`` at THEIR import time and call
        # that name forever after (``trame_pyvista.ui`` and its ``base_viewer``
        # both do).  A module that booted the page before this one can leave its
        # own ``get_server`` double cached there, and that double would install
        # ITS stop-double mid-boot, over the top of ours.  Point them at the real
        # accessor for the duration; MonkeyPatch puts each one back.
        for holder in _foreign_get_server_holders():
            patch.setattr(holder, "get_server", PRISTINE_GET_SERVER)
        # An INSTANCE attribute shadows the class attribute, and a module that
        # booted the page before this one may still have its own stop-double
        # parked there - the class double would then never be reached and ITS
        # ``_Stop``, which the ``suppress`` below cannot know, would escape.
        # Doubling the instance as well covers that; MonkeyPatch puts back the
        # object it found.
        patch.setattr(srv, "start", _no_start)
        with contextlib.suppress(_Stop):
            app.run_web_vis(info, "127.0.0.1", 8999, fps=FPS)

    assert stopped, (
        "run_web_vis never reached server.start(): it returned early (missing "
        "web dependency) so the volume layer was never built"
    )
    _BOOTED_SERVERS[id(srv)] = (srv, shadow)
    return _live(srv)


@pytest.fixture(autouse=True)
def _nothing_is_left_patched():
    """Fail HERE, in the module that leaked, not two files later.

    The trame server is process-wide and ``trame_pyvista.ui`` calls a
    ``get_server`` reference it cached at import, so anything still doubled
    when a test here ends follows the page into the next module: that is
    exactly how a stop-double left on ``start`` made the page raise this
    module's ``_Stop`` inside tests/test_poc_playback.py, where nothing could
    catch it.  Identity comparison against the references captured at import.
    """
    yield
    assert trame_app.get_server is PRISTINE_GET_SERVER, (
        "trame.app.get_server was left patched by a test in this module; the "
        "page - and trame_pyvista.ui, which caches its own reference to it - "
        "would keep calling the double in every later module"
    )
    assert trame_server.Server.start is PRISTINE_SERVER_START, (
        "trame_server.Server.start is still doubled after the test; every "
        "later module that boots the page would raise this module's _Stop"
    )
    for srv, shadow in _BOOTED_SERVERS.values():
        assert vars(srv).get("start") is shadow, (
            "a stop-double was left as an INSTANCE attribute on the shared "
            f"trame server {srv!r}: it shadows Server.start for every later "
            "module and does not go away with this one"
        )


def _closure_cells(fn) -> dict:
    cells = getattr(fn, "__closure__", None) or ()
    return dict(zip(fn.__code__.co_freevars, [c.cell_contents for c in cells]))


def _registered_trigger(ctrl, name):
    """The raw function registered by ``@ctrl.set(name)`` on the live controller."""
    holder = getattr(ctrl, name, None)
    assert holder is not None, (
        f"the controller exposes no {name!r} trigger; the NEXT button binding is "
        "not registered, so there is nothing for the browser to call"
    )
    fn = getattr(holder, "func", holder)  # ControllerFunction -> the function
    fn = getattr(fn, "func", fn)
    assert callable(fn), f"{name!r} unwrapped to a non-callable: {fn!r}"
    return fn


def _live(srv) -> SimpleNamespace:
    """The live page objects, read out of the shipped closures.

    ``_draw_volume_layer`` is not reachable by name from outside - it is a
    closure inside ``run_web_vis`` - so it is taken from ``_show``'s cells (the
    trigger's own cells hand over ``_show``), and its cells then hand over the
    page dict, the plotter and ``handles`` it actually uses.  Each of those is
    the object the page runs with; nothing here builds a stand-in.
    """
    show = _closure_cells(_registered_trigger(srv.controller, TRIGGER_NAME))["_show"]
    draw = _closure_cells(show)["_draw_volume_layer"]
    cells = _closure_cells(draw)
    for name in ("handles", "page", "plotter", "state"):
        assert name in cells, (
            f"_draw_volume_layer is not closed over {name!r} "
            f"(freevars: {sorted(cells)}) - cannot assert on the live layer"
        )
    return SimpleNamespace(
        draw=draw,
        show=show,
        trigger=_registered_trigger(srv.controller, TRIGGER_NAME),
        handles=cells["handles"],
        page=cells["page"],
        plotter=cells["plotter"],
        state=cells["state"],
        view=cells["handles"].get("view"),
    )


@contextlib.contextmanager
def _render_doubled():
    """``pyvista.Plotter.render`` doubled: this image has no OpenGL device.

    The draw COUNT is not what these tests assert, so a no-op is enough; every
    scene-building call around it (``add_volume``, ``add_mesh``,
    ``remove_actor``) stays the real one, which is what lets the assertions
    above read the colour range off the actor.
    """
    import pyvista

    real_render = pyvista.Plotter.render
    pyvista.Plotter.render = lambda self, *a, **k: None  # no OpenGL here
    try:
        yield
    finally:
        pyvista.Plotter.render = real_render


def _silence_view(live) -> None:
    """Stop the module pushing frames at a browser that is not there."""
    view = live.view
    if view is not None and hasattr(view, "update"):
        view.update = lambda *_a, **_k: None


def _layer_entry(live) -> dict:
    entry = live.handles.get("volume_layer")
    assert isinstance(entry, dict), (
        "the page recorded no volume_layer entry: the layer either never drew "
        f"(handles: {sorted(live.handles)}) or was dropped"
    )
    return entry


def _volume_actor(live):
    """The ONE actor the |E| image is drawn as, out of the layer's own list."""
    import pyvista

    actors = _layer_entry(live)["actors"]
    volumes = [actor for actor in actors if isinstance(actor, pyvista.Volume)]
    assert len(volumes) == 1, (
        "the layer drew "
        f"{len(volumes)} volume actors, expected exactly ONE: two volumes over "
        "one slab occlude each other, which _draw_volume_scene refuses"
    )
    return volumes[0]


def _scalar_ranges(live) -> set:
    """Every colour range the layer's actors are actually painted on."""
    ranges = set()
    for actor in _layer_entry(live)["actors"]:
        mapper = getattr(actor, "mapper", None)
        span = getattr(mapper, "scalar_range", None) if mapper is not None else None
        if span is not None:
            ranges.add(tuple(float(v) for v in span))
    return ranges


def _draw(live, index: int, mode: str = "ycut"):
    """Draw the layer for one frame slider position, forgetting the clim memo.

    ``handles`` is cleared first because the entry it holds is also the cache of
    the colour range (``_draw_volume_layer`` REUSES it while the source volume is
    the same object).  This test is about where that range is measured, so the
    cache is emptied on purpose: every call below re-measures, which is what a
    freshly loaded page does.
    """
    live.handles.pop("volume_layer", None)
    live.draw(index, mode)


@pytest.fixture(scope="module")
def volume_page(tmp_path_factory):
    """A page serving a dump that CARRIES an |E| volume, booted for real."""
    with _render_doubled():
        with contextlib.suppress(Exception):
            live = _boot(tmp_path_factory.mktemp("vol"), with_volume=True)
        _silence_view(live)
        assert live.page["info"]["e_abs_volume"] is not None, (
            "the fixture dump lost its |E| volume: nothing below would test the "
            "volume layer at all"
        )
        yield live


@pytest.fixture
def no_volume_page(tmp_path_factory):
    """A page serving the same dump with every ``e_abs_volume*`` key absent."""
    with _render_doubled():
        live = _boot(tmp_path_factory.mktemp("novol"), with_volume=False)
        _silence_view(live)
        yield live


def test_the_volume_clim_is_the_whole_recording_not_the_frame(volume_page):
    """Every frame is painted on the range of the WHOLE clip, not its own.

    WHY this is the assertion and not "the colours look right": a range measured
    per frame renormalises each frame to its own peak, so the recorded decay -
    the whole point of an animation - is painted away, and each frame silently
    claims to fill the scale.  The dump here decays by 1e6 across the clip, so
    the two answers are three decades apart and cannot be confused.

    Both frames are drawn with the clim cache EMPTIED first, so the number read
    below is one this call measured, not one an earlier frame left behind.
    """
    live = volume_page
    volume = live.page["info"]["e_abs_volume"]
    peak = float(np.max(volume))
    whole = (peak * 1e-3, peak)
    assert app._volume_abs_global_clim(volume) == pytest.approx(whole, rel=1e-12), (
        "the resolver does not answer (peak * 1e-3, peak) over the whole volume, "
        "so the test's own expectation is wrong before the page is asked"
    )

    # The bite: on BOTH frames below, a per-frame range would be at least 100x
    # away from the whole-recording one.
    for frame in (0, 2):
        frame_peak = float(np.max(volume[frame]))
        assert frame_peak * 100.0 < peak, (
            f"volume frame {frame} peaks at {frame_peak!r} against a whole-clip "
            f"peak of {peak!r}: the two ranges are not far enough apart for this "
            "test to tell a per-frame clim from a global one"
        )

    for index in (0, 3):
        _draw(live, index)
        drawn = tuple(_volume_actor(live).mapper.scalar_range)
        assert drawn == pytest.approx(whole, rel=1e-9), (
            f"frame slider {index} was painted on {drawn}, but the recording's "
            f"own range is {whole}: a range per frame paints the recorded decay "
            "away and makes every frame claim the top of the scale"
        )


def test_clim_override_reaches_the_volume_and_stops_at_it(volume_page):
    """The resolved range is applied to the |E| MESH - and to the cuts it is not.

    ``_draw_volume_scene`` takes ``clim_override`` and hands it to the volume's
    ``add_volume(..., clim=...)``; the two cut sheets keep the ranges
    ``build_cut_sheets`` measured off the samples each sheet actually holds.  One
    range over both would be the lie that block refuses, so the test reads the
    painted range off every actor of the layer: exactly one of them is the clip's
    range, and it is the volume.
    """
    live = volume_page
    info = live.page["info"]
    volume = info["e_abs_volume"]
    peak = float(np.max(volume))
    whole = (peak * 1e-3, peak)

    _draw(live, 3)
    painted = _scalar_ranges(live)

    assert (whole[0], whole[1]) in painted, (
        "no actor of the layer is painted on the |E| volume's own range "
        f"{(whole[0], whole[1])}; the layer drew {sorted(painted)} - the clim "
        "the caller resolved never reached the mesh"
    )
    assert tuple(_volume_actor(live).mapper.scalar_range) == pytest.approx(
        whole, rel=1e-9
    ), "the |E| volume actor itself is not on the recording's range"

    sheet_clims = {
        axis: tuple(float(v) for v in clim)
        for axis, _sheet, clim in app.build_cut_sheets(info, app._cut_layout(info))
    }
    assert sheet_clims, (
        "build_cut_sheets drew no sheet, so this test cannot tell whether the "
        "override stopped at the volume"
    )
    for axis, clim in sheet_clims.items():
        assert clim in painted, (
            f"the {axis} cut sheet is not painted on its own range {clim}; the "
            f"layer drew {sorted(painted)} - the volume's range was applied to a "
            "sheet, which is the one thing clim_override must not do"
        )
        assert max(clim) < whole[1], (
            f"the {axis} sheet's own range {clim} is not below the volume's "
            f"{whole}: this dump cannot show the override stopping at the volume"
        )


def test_the_volume_frame_is_looked_up_not_step_over_stride(volume_page):
    """The slider's step is mapped through the RECORDED step axis, not divided.

    ``e_abs_volume`` holds every ``e_abs_volume_stride``-th step and records
    WHICH steps those are.  ``step // stride`` agrees with that array only while
    the cadence is complete and uniform; this dump's is neither, so the two
    answers differ at two of the four frames - and the test states both, so a
    regression to arithmetic fails here instead of quietly drawing a different
    slice of time.
    """
    live = volume_page
    volume = live.page["info"]["e_abs_volume"]

    cases = ((3, FRAME_INDEX[3], 2), (2, FRAME_INDEX[2], 1))
    for index, step, expected_frame in cases:
        assert step == FRAME_INDEX[index]
        assert step // VOLUME_STRIDE != expected_frame, (
            f"step {step} at stride {VOLUME_STRIDE} divides to "
            f"{step // VOLUME_STRIDE} and the recorded axis answers "
            f"{expected_frame}: this case cannot tell the two apart"
        )
        _draw(live, index)
        entry = _layer_entry(live)
        assert entry["step"] == step, (
            f"frame slider {index} read step {entry['step']} out of the dump's "
            f"frame_index, expected {step}"
        )
        assert entry["frame"] == expected_frame, (
            f"step {step} drew volume frame {entry['frame']}, but the last frame "
            f"recorded at or before step {step} is frame {expected_frame} "
            f"(steps {VOLUME_STEPS}); step // {VOLUME_STRIDE} answers "
            f"{step // VOLUME_STRIDE}, which is a different slice of time"
        )
        memo = live.page["info"][app.VOLUME_ABS_KEY]
        on_screen = float(np.max(np.asarray(memo["image"].point_data["e_abs"])))
        assert on_screen == pytest.approx(
            float(np.max(volume[expected_frame])), rel=1e-6
        ), (
            f"the image on screen peaks at {on_screen!r}, but volume frame "
            f"{expected_frame} peaks at {float(np.max(volume[expected_frame]))!r} "
            "- the frame the bookkeeping named is not the frame that was drawn"
        )


def test_a_dump_without_a_volume_is_left_as_it_was(no_volume_page):
    """No volume, no layer: the page is not touched at all.

    Most dumps carry no |E| volume (only ``--volume-stride`` writes one), so
    this is the normal path.  Its contract is negative - no actor, no memo, no
    bookkeeping entry - and the only way to test a negative is to compare the
    page against itself.
    """
    live = no_volume_page
    info = live.page["info"]
    assert info["e_abs_volume"] is None, (
        "the fixture dump carries a volume, so this is not the no-volume path"
    )

    before = list(live.plotter.actors)
    live.draw(0, "ycut")

    assert list(live.plotter.actors) == before, (
        "the layer drew an actor for a dump that carries no |E| volume "
        f"(before {len(before)} actors, after {len(live.plotter.actors)}): a "
        "picture of a field this run never recorded"
    )
    assert "volume_layer" not in live.handles, (
        f"a layer entry was recorded for a no-volume dump: "
        f"{sorted(live.handles)}"
    )
    assert info.get(app.VOLUME_ABS_KEY) is None, (
        "the |E| grid memo was seeded for a dump that carries no |E| volume; the "
        "cut sheets and the plane markers resolve their lattice through it and "
        "would now be sized from a frame that does not exist"
    )


def test_the_layer_cannot_grow_with_the_number_of_frames_watched(volume_page):
    """Eight frame steps leave the scene exactly the size it was.

    A rebuild per frame is deliberate (a frame IS a different image), but it must
    be a REPLACEMENT: the entry is dropped before the new one is built, and a
    redraw that lands on the frame already on screen rebuilds nothing.  If either
    half regressed, watching a clip would pile up one image per frame - and the
    last one to leave also removes exactly its own actors and nothing else.
    """
    live = volume_page
    info = live.page["info"]
    volume = info["e_abs_volume"]
    live.handles.pop("volume_layer", None)
    live.draw(0, "ycut")

    baseline = len(live.plotter.actors)
    watched = []
    for _ in range(2 * NT):
        live.trigger()
        assert len(live.plotter.actors) == baseline, (
            f"the scene grew from {baseline} to {len(live.plotter.actors)} "
            f"actors after {len(watched) + 1} frame steps: the volume layer is "
            "not being replaced"
        )
        watched.append(_layer_entry(live)["frame"])
    assert len(set(watched)) >= 3, (
        f"the volume frame never changed over {len(watched)} steps "
        f"(frames seen: {sorted(set(watched))}): the actor count above is "
        "constant because nothing was redrawn, which proves nothing"
    )

    dropped = len(_layer_entry(live)["actors"])

    try:
        info["e_abs_volume"] = None
        live.trigger()
        assert "volume_layer" not in live.handles, (
            "the layer survived a dump with no |E| volume: the entry and the "
            "screen no longer agree"
        )
        assert len(live.plotter.actors) == baseline - dropped, (
            f"dropping the layer left {len(live.plotter.actors)} actors, "
            f"expected {baseline - dropped} ({baseline} minus the {dropped} the "
            "layer owned): it removed more or less than its own"
        )
    finally:
        info["e_abs_volume"] = volume
