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

#: A SECOND dump whose |E| volume is saved every 15th step, so the FIVE
#: consecutive frame-slider positions 0..4 (steps 2, 5, 8, 11, 14) all map onto
#: ONE stored volume frame and every draw after the first is a CACHE HIT.
#: The steps are deliberately not ``index + 1``: the volume layer's step mapping
#: is a lookup through ``frame_index``, and a mapping that hardcoded ``index + 1``
#: would answer 1, 2, 3, 4, 5 here - wrong on every one of these positions.
BUCKET_NT = 6
BUCKET_FRAME_INDEX = (2, 5, 8, 11, 14, 17)
BUCKET_DUMP_STRIDE = 3
BUCKET_VOLUME_STEPS = (2, 17)
BUCKET_VOLUME_STRIDE = 15


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


def _bucket_payload() -> dict:
    """``_payload``'s dump, with ONE volume bucket spanning five slider positions.

    ``e_abs_volume_step_index = (2, 17)`` at ``e_abs_volume_stride = 15`` means
    the steps 2..16 are all shown by stored volume frame 0, so five CONSECUTIVE
    frame-slider positions (``frame_index = 2, 5, 8, 11, 14``) share one cache
    key.  That is the shape ``--volume-stride`` produces on a real run, and it
    is the only shape in which the layer's early-return path is taken at all.
    """
    payload = _payload(with_volume=False)
    rng = np.random.default_rng(1)
    payload["nt"] = np.array(BUCKET_NT)
    payload["t_ns"] = np.arange(BUCKET_NT) * 3e-3
    payload["ez_ycut"] = rng.normal(size=(BUCKET_NT, NX, NZ))
    payload["frame_index"] = np.array(BUCKET_FRAME_INDEX)
    payload["dump_stride"] = np.array(BUCKET_DUMP_STRIDE)
    payload["nsteps"] = np.array(BUCKET_FRAME_INDEX[-1] + 1)
    volume = np.abs(rng.normal(size=(len(BUCKET_VOLUME_STEPS), NX, NY, NZ))) * 1e-3
    payload["e_abs_volume"] = volume.astype(np.float32)
    payload["e_abs_volume_step_index"] = np.array(BUCKET_VOLUME_STEPS, dtype=int)
    payload["e_abs_volume_stride"] = np.array(BUCKET_VOLUME_STRIDE)
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


def _boot(
    tmp_path: Path, *, with_volume: bool, payload: dict | None = None
) -> SimpleNamespace:
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
    payload = _payload(with_volume=with_volume) if payload is None else payload
    path = tmp_path / ("volume.npz" if with_volume else "no_volume.npz")
    np.savez(path, **payload)
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

    # MonkeyPatch memorised the INSTANCE attribute with ``getattr``, i.e. through
    # the MRO: what it recorded for ``srv`` was the CLASS double installed just
    # above, and its undo wrote that back onto the instance once the class was
    # restored - leaving ``srv.start`` doubled forever, because an INSTANCE
    # attribute shadows the restored class member.  Put the instance back exactly
    # as it was found, which normally means not having a ``start`` at all.
    if shadow is None:
        vars(srv).pop("start", None)
    else:
        srv.start = shadow

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
        live = _boot(tmp_path_factory.mktemp("vol"), with_volume=True)
        _silence_view(live)
        assert live.page["info"]["e_abs_volume"] is not None, (
            "the fixture dump lost its |E| volume: nothing below would test the "
            "volume layer at all"
        )
        yield live


@pytest.fixture(scope="module")
def bucket_page(tmp_path_factory):
    """A page whose |E| volume buckets FIVE consecutive slider positions at once."""
    with _render_doubled():
        live = _boot(
            tmp_path_factory.mktemp("bucket"),
            with_volume=True,
            payload=_bucket_payload(),
        )
        _silence_view(live)
        assert live.page["info"]["e_abs_volume"] is not None, (
            "the bucket fixture dump lost its |E| volume: the cache-hit path "
            "below would never be taken"
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


def test_a_cache_hit_still_reports_the_step_being_asked_for(bucket_page):
    """A CACHE HIT must still name the step the frame slider is asking for.

    ``_draw_volume_layer`` caches on ``(page, volume frame, load, port)``, and
    ONE stored volume frame covers a whole BUCKET of animation steps
    (``dump_stride * volume_stride`` of them).  So the early return is not an
    edge case - it is every frame of a recorded clip except one in a hundred -
    and ``step``, which names the SIM TIME this layer is showing, has to be
    rewritten on that path exactly as a rebuild would write it.

    The bug this pins: the entry kept the step of the FIRST draw in the bucket,
    so a readout fed from ``entry['step']`` froze while the animation advanced.
    The assertion is on the SECOND..FIFTH draw of one bucket, all reached
    through the early return; it fails on any implementation that returns
    before refreshing the field.
    """
    live = bucket_page
    info = live.page["info"]
    requested = [int(step) for step in info["frame_index"][:5]]
    assert requested == [2, 5, 8, 11, 14], requested

    # The premise, stated so a fixture change cannot make this test vacuous:
    # all five positions resolve to the SAME stored volume frame, so the draws
    # below are one rebuild followed by four cache hits.
    frames = {
        app._volume_frame_for_step(info["e_abs_volume_step_index"], step)
        for step in requested
    }
    assert frames == {0}, (
        f"the five slider positions mapped to volume frames {sorted(frames)}, "
        "not to ONE bucket: the early-return path would never be taken"
    )
    for index, step in enumerate(requested):
        assert step != index + 1, (
            f"slider {index} happens to ask for step {index + 1}: a step mapping "
            "hardcoded to index + 1 would pass this case, so the dump cannot "
            "tell it from the real one"
        )

    # The cache is dropped ONCE, on purpose: ``_draw`` (used elsewhere) empties
    # it before every call, which is exactly the rebuild path and never this one.
    live.handles.pop("volume_layer", None)
    live.draw(0, "ycut")
    first = _layer_entry(live)
    assert first["step"] == requested[0], (
        f"the first draw of the bucket recorded step {first['step']!r}, expected "
        f"{requested[0]} (frame_index[0]); the rebuild path is wrong too"
    )

    for index in range(1, 5):
        live.draw(index, "ycut")
        entry = _layer_entry(live)
        assert entry is first, (
            f"slider {index} rebuilt the layer instead of hitting the cache (a "
            "new entry object): this test is about the early-return path"
        )
        assert entry["step"] == requested[index], (
            f"cache hit at slider {index} left entry['step'] = {entry['step']!r} "
            f"while the frame slider asks for step {requested[index]} "
            f"(frame_index[{index}]): a readout fed from this entry names the "
            f"step of the FIRST draw in the bucket ({requested[0]}) instead of "
            "the frame on screen"
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


# ---------------------------------------------------------------------------
# THE SELECTABLE CLIM MODE.  ``state.volume_clim_mode`` is the ONE name a
# left-panel control will write; there is no control yet, so these tests write
# that field themselves and then redraw - exactly what the control's handler will
# do - and read the range back off the VOLUME ACTOR's mapper, never off a
# promise.  "global" (the default) is today's whole-recording range;
# "per_frame" is the same 60 dB window referenced to the current frame's peak.
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _clim_mode(live, mode):
    """Set the page's clim mode for the block, and put the boot value back."""
    before = getattr(live.state, "volume_clim_mode", None)
    live.state.volume_clim_mode = mode
    try:
        yield
    finally:
        live.state.volume_clim_mode = before


def _drawn_range(live) -> tuple:
    """The colour range the |E| VOLUME actor is actually painted on."""
    return tuple(float(value) for value in _volume_actor(live).mapper.scalar_range)


def _only_the_layers_volume(live) -> None:
    """Forget the clim memo AND take every stray volume OFF the plotter.

    WHY the second half is not optional (measured on pyvista 0.49.2): a scene
    shares ONE volume scalar range between every volume actor in it, so with two
    volumes present ``mapper.scalar_range`` - and the transfer function the
    renderer uploads - reads the UNION of their ranges.  A per-frame window
    measured next to an earlier whole-clip volume therefore comes back as
    ``(frame floor, clip peak)``: neither range, and no picture this page ever
    draws.  ``_draw_volume_layer`` never has two volumes - ``_volume_layer_drop``
    takes the old one off before the new one is added - so a test that pops
    ``handles`` to force a rebuild has to take the orphan off itself.
    """
    import pyvista

    entry = live.handles.pop("volume_layer", None)
    if isinstance(entry, dict):
        for actor in entry.get("actors", ()):
            live.plotter.remove_actor(actor, render=False)
    for actor in list(live.plotter.actors.values()):
        if isinstance(actor, pyvista.Volume):
            live.plotter.remove_actor(actor, render=False)
    # The bar goes with the volume: a colour bar is a reading of a volume that is
    # no longer on the plotter, and a stale bar's TITLE now names the window in
    # force, so it is not one the next draw replaces.  ``_volume_layer_drop`` does
    # sweep every spelling, but only once the handle above is still there, and
    # popping it is what this helper is for - so the orphan is this helper's to
    # take off, exactly like the actors.
    for stale_title in app._volume_bar_titles():
        app._remove_scalar_bar(live.plotter, stale_title)


def test_switching_the_clim_mode_repaints_the_frame_already_on_screen(volume_page):
    """The mode is part of the cache KEY, not a field a stale entry keeps.

    THE TRAP this pins: the layer caches on ``(page, volume frame, load, port)``
    and remembers the clim it painted.  A mode that only changes the clim is
    invisible to that key, so the second draw below would be a CACHE HIT - the
    early return keeps the global range and the control looks dead until the
    slider reaches another stored frame.  So the SAME frame slider position is
    drawn twice with ``handles`` left ALONE in between: a cache hit is the
    failure this test exists to catch.
    """
    live = volume_page
    volume = live.page["info"]["e_abs_volume"]
    peak = float(np.max(volume))
    whole = (peak * 1e-3, peak)
    index = 3
    _only_the_layers_volume(live)

    with _clim_mode(live, app.VOLUME_CLIM_GLOBAL):
        live.draw(index, "ycut")
        first = _layer_entry(live)
        before = _drawn_range(live)

    # NOTHING is popped from handles here: the only thing that changed is the
    # mode, which is exactly the state a dead toggle leaves behind.
    with _clim_mode(live, app.VOLUME_CLIM_PER_FRAME):
        live.draw(index, "ycut")
        second = _layer_entry(live)
        after = _drawn_range(live)

    assert first["frame"] == second["frame"], (
        f"the two draws landed on volume frames {first['frame']} and "
        f"{second['frame']}: this test needs ONE frame, so that the mode is the "
        "only difference between the two ranges"
    )
    frame_peak = float(np.max(volume[first["frame"]]))
    assert frame_peak * 100.0 < peak, (
        f"volume frame {first['frame']} peaks at {frame_peak!r} against a clip "
        f"peak of {peak!r}: the two ranges are too close for this test to tell "
        "a per-frame clim from a global one"
    )

    assert first["key"] != second["key"], (
        f"changing the clim mode left the cache key unchanged ({first['key']!r}): "
        "the mode does not participate in the key, so the next draw of this same "
        "frame is a HIT and keeps the old clim"
    )
    assert second is not first, (
        "the second draw reused the first entry instead of rebuilding the layer: "
        "a mode change must repaint, not repaint-nothing"
    )
    assert before == pytest.approx(whole, rel=1e-9), (
        f"the global-mode draw painted {before}, expected the whole-recording "
        f"range {whole}"
    )
    assert after == pytest.approx((frame_peak * 1e-3, frame_peak), rel=1e-9), (
        f"after switching to per_frame the SAME frame is still painted on "
        f"{after}; its own 60 dB window is {(frame_peak * 1e-3, frame_peak)}. A "
        "cache hit keeps the global clim and the mode switch does nothing until "
        "the slider moves"
    )
    assert after != pytest.approx(before), (
        f"the clim did not change when the mode did ({before} -> {after}): the "
        "toggle is inert on a frame that is already on screen"
    )

    # ... and back, so the mode is read on EVERY draw and not latched once.
    with _clim_mode(live, app.VOLUME_CLIM_GLOBAL):
        live.draw(index, "ycut")
        assert _drawn_range(live) == pytest.approx(whole, rel=1e-9), (
            "switching back to global did not restore the whole-recording range"
        )


def _zero_peak_payload() -> dict:
    """``_payload``'s dump with one stored |E| frame that peaks at EXACTLY 0.0.

    ``QUIET_FRAME`` is zeroed: per-frame scaling divides that frame by its own
    peak, and 0/0 is the number that must never reach a clim.
    """
    payload = _payload(with_volume=True)
    payload["e_abs_volume"][QUIET_FRAME] = 0.0
    return payload


@pytest.fixture(scope="module")
def zero_peak_page(tmp_path_factory):
    """A page serving a dump whose ``QUIET_FRAME`` |E| frame peaks at 0.0."""
    with _render_doubled():
        live = _boot(
            tmp_path_factory.mktemp("zeropeak"),
            with_volume=True,
            payload=_zero_peak_payload(),
        )
        _silence_view(live)
        assert float(np.max(live.page["info"]["e_abs_volume"][QUIET_FRAME])) == 0.0, (
            "the fixture's zeroed |E| frame is not flat zero: this page cannot "
            "test the 0/0 branch"
        )
        yield live


def test_a_frame_with_no_peak_falls_back_to_the_global_range(zero_peak_page):
    """A 0 / NaN / inf frame peak must not make a degenerate or invented clim.

    THE FALLBACK, stated: ``_volume_abs_frame_clim`` answers **None** for a frame
    that cannot name a reference (peak 0, not finite, wrong rank, index off the
    end) and ``_volume_clim_for`` turns that None into the WHOLE-RECORDING range.
    So a dead frame is drawn on the measured global range - on which it is
    empty, which is the truth - instead of on ``(0.0, 0.0)`` (degenerate: every
    voxel at the bottom of a zero-width range) or on a number this code invented.
    """
    live = zero_peak_page
    volume = live.page["info"]["e_abs_volume"]
    peak = float(np.max(volume))
    whole = (peak * 1e-3, peak)
    assert np.isfinite(peak) and peak > 0.0, (
        f"the fixture's whole-clip peak is {peak!r}: this page cannot test a "
        "frame-local fallback against a real global range"
    )

    # The resolver, directly: None - never a tuple - for a 0 peak.
    assert app._volume_abs_frame_clim(volume, QUIET_FRAME) is None, (
        "a frame that peaks at 0.0 was given a colour range "
        f"{app._volume_abs_frame_clim(volume, QUIET_FRAME)!r}: 0/0 has produced "
        "a degenerate clim instead of 'no reference'"
    )
    assert app._volume_clim_for(
        volume, QUIET_FRAME, app.VOLUME_CLIM_PER_FRAME
    ) == pytest.approx(whole, rel=1e-12), (
        "the per_frame range for the zero-peak frame is not the whole-recording "
        f"range {whole}: the fallback is missing, so the layer would be painted "
        "on a degenerate range"
    )

    # A non-finite peak cannot name a reference either - no crash, no tuple.
    for poison in (np.nan, np.inf, -np.inf):
        poisoned = np.array(volume, dtype=float, copy=True)
        poisoned[QUIET_FRAME] = poison
        assert app._volume_abs_frame_clim(poisoned, QUIET_FRAME) is None, (
            f"a frame holding a {poison!r} sample was given a colour range "
            f"{app._volume_abs_frame_clim(poisoned, QUIET_FRAME)!r} instead of "
            "'no reference'"
        )
    # A NaN poisons the global peak too, so THAT dump has no honest range at
    # all and the caller drops the layer (``clim is None``) rather than paint.
    nan_volume = np.array(volume, dtype=float, copy=True)
    nan_volume[QUIET_FRAME] = np.nan
    assert app._volume_clim_for(
        nan_volume, QUIET_FRAME, app.VOLUME_CLIM_PER_FRAME
    ) is None, (
        "an all-NaN recording still produced a colour range: the fallback "
        "invented one instead of reporting that there is none"
    )

    # The LIVE layer on the zero-peak frame: rebuilt, drawn, on the fallback.
    with _clim_mode(live, app.VOLUME_CLIM_PER_FRAME):
        _only_the_layers_volume(live)
        live.draw(2, "xcut")  # step 18 -> the stored frame that peaks at 0.0
        entry = _layer_entry(live)
        drawn = _drawn_range(live)
    assert entry["frame"] == QUIET_FRAME, (
        f"this draw landed on volume frame {entry['frame']}, not the zero-peak "
        f"frame {QUIET_FRAME}: the branch below was never reached"
    )
    assert entry["clim_mode"] == app.VOLUME_CLIM_PER_FRAME, (
        f"the entry stamped clim mode {entry['clim_mode']!r}"
    )
    assert drawn == pytest.approx(whole, rel=1e-9), (
        f"the zero-peak frame was painted on {drawn}, not on the fallback "
        f"whole-recording range {whole}"
    )
    assert drawn[1] > drawn[0] > 0.0, (
        f"the fallback range is degenerate or inverted: {drawn}"
    )


def test_a_page_that_never_touches_the_mode_draws_todays_layer(volume_page):
    """Requirement 3: the DEFAULT draw is byte-for-byte the layer that shipped.

    A page (or a caller) that never mentions the mode must get the same clim and
    the same actors as before the mode existed - that is what makes this safe to
    land while no control sets it.  Asserted three ways: the boot value and the
    normaliser, the range read off the actor, and the layer compared against an
    EXPLICIT ``"global"`` draw (which must equal it exactly).
    """
    live = volume_page
    volume = live.page["info"]["e_abs_volume"]
    peak = float(np.max(volume))
    whole = (peak * 1e-3, peak)

    assert live.state.volume_clim_mode == app.VOLUME_CLIM_DEFAULT == "global", (
        f"the page boots with clim mode {live.state.volume_clim_mode!r}, not the "
        "default 'global'"
    )
    for absent in (None, "", "GLOBAL", "per-frame", "perFrame"):
        assert app._volume_clim_mode(absent) == "global", (
            f"a mode of {absent!r} normalises to "
            f"{app._volume_clim_mode(absent)!r}: an absent or misspelled mode "
            "must not select the renormalising one"
        )

    # A plain rebuild with NOTHING set: no fixture, no explicit mode.
    _only_the_layers_volume(live)
    live.draw(0, "ycut")
    default_entry = _layer_entry(live)
    default_drawn = _drawn_range(live)
    default_ranges = _scalar_ranges(live)
    default_actor_count = len(live.plotter.actors)
    assert default_drawn == pytest.approx(whole, rel=1e-9), (
        f"the default draw painted the volume on {default_drawn}, but today's "
        f"layer is (global_peak * 1e-3, global_peak) = {whole}"
    )
    assert default_entry["clim"] == pytest.approx(whole, rel=1e-12), (
        f"the entry recorded clim {default_entry['clim']!r} for a default draw"
    )
    assert default_entry["clim_mode"] == "global", (
        f"a default draw stamped clim mode {default_entry['clim_mode']!r}"
    )
    assert default_entry["key"][-1] == "global", (
        f"the default draw's cache key {default_entry['key']!r} does not carry "
        "the default mode"
    )

    # ... and that is exactly what an explicit "global" (and a state object
    # that holds no mode at all) draws.
    for explicit in ("global", None):
        with _clim_mode(live, explicit):
            _only_the_layers_volume(live)
            live.draw(0, "ycut")
            entry = _layer_entry(live)
            assert _drawn_range(live) == pytest.approx(default_drawn, rel=1e-12), (
                f"clim mode {explicit!r} painted the volume on "
                f"{_drawn_range(live)}, not on the default draw's "
                f"{default_drawn}: the default is not today's behaviour"
            )
            assert _scalar_ranges(live) == default_ranges, (
                f"clim mode {explicit!r} drew the layer's actors on "
                f"{sorted(_scalar_ranges(live))} instead of "
                f"{sorted(default_ranges)}"
            )
            assert len(entry["actors"]) == len(default_entry["actors"]), (
                "the layer drew "
                f"{len(entry['actors'])} actors under {explicit!r} against "
                f"{len(default_entry['actors'])} for the default draw"
            )
            assert len(live.plotter.actors) == default_actor_count, (
                f"the scene holds {len(live.plotter.actors)} actors under "
                f"{explicit!r}, against {default_actor_count} for the default "
                "draw"
            )


def test_a_weak_frame_is_blank_in_global_mode_and_drawn_per_frame(volume_page):
    """The behavioural payoff, both branches on ONE weak frame.

    ``QUIET_FRAME`` peaks six decades below the loud one, which puts it BELOW the
    global floor ``global_peak * 1e-3`` - the shape the real dump has on its late
    frames (peak 0.128 against a floor of 0.1587).  Under the default mode that
    frame is painted entirely below its own range, i.e. fully transparent, while
    the cut sheets and markers stay drawn: the picture a PI reads as "the volume
    was clipped away".  Under per_frame the floor is that frame's own peak / 1000,
    so the frame renders.

    The transparency is asserted on the numbers that decide it (the frame against
    the range the mapper was given), not on pixels: this image has no OpenGL.
    """
    live = volume_page
    volume = live.page["info"]["e_abs_volume"]
    frame = volume[QUIET_FRAME]
    frame_peak = float(np.max(frame))
    global_clim = app._volume_abs_global_clim(volume)
    assert global_clim is not None, "the dump's whole-recording range is missing"
    assert frame_peak < global_clim[0], (
        f"the quiet frame peaks at {frame_peak!r}, not below the global floor "
        f"{global_clim[0]!r}: this dump cannot show a frame the default mode "
        "leaves empty"
    )
    assert int(np.count_nonzero(frame >= global_clim[0])) == 0

    _only_the_layers_volume(live)
    live.draw(2, "xcut")  # step 18 -> the quiet stored frame
    entry = _layer_entry(live)
    assert entry["frame"] == QUIET_FRAME
    drawn_global = _drawn_range(live)
    assert drawn_global == pytest.approx(global_clim, rel=1e-9), (
        f"the default draw painted the weak frame on {drawn_global}, not on the "
        f"whole-recording range {global_clim}"
    )
    above_global = int(np.count_nonzero(frame >= drawn_global[0]))
    assert above_global == 0, (
        f"{above_global} of {frame.size} voxels of the weak frame are above the "
        f"global floor {drawn_global[0]!r}: the default mode should leave this "
        "frame empty"
    )

    with _clim_mode(live, app.VOLUME_CLIM_PER_FRAME):
        _only_the_layers_volume(live)
        live.draw(2, "xcut")
        assert _layer_entry(live)["frame"] == QUIET_FRAME
        drawn_frame = _drawn_range(live)
    assert drawn_frame != pytest.approx(drawn_global), (
        f"per_frame painted the weak frame on the same range as global "
        f"({drawn_frame}): the mode changes nothing"
    )
    assert drawn_frame == pytest.approx((frame_peak * 1e-3, frame_peak), rel=1e-9), (
        f"per_frame painted the weak frame on {drawn_frame}, not on its own 60 dB "
        f"window {(frame_peak * 1e-3, frame_peak)}"
    )
    assert drawn_frame[0] < frame_peak, (
        f"the per-frame floor {drawn_frame[0]!r} is not below the frame's own peak "
        f"{frame_peak!r}: nothing on this frame can render"
    )
    above_frame = int(np.count_nonzero(frame >= drawn_frame[0]))
    assert above_frame > 0.9 * frame.size, (
        f"only {above_frame} of {frame.size} voxels of the weak frame are above "
        f"the per-frame floor {drawn_frame[0]!r}: the frame still does not render"
    )



# ---------------------------------------------------------------------------
# THE VOLUME'S OWN CLOCK, INSIDE THE PLANE'S.  A dump written with
# ``--volume-stride`` saves the |E| volume on a COARSER grid than the cut planes,
# so the page carries two clocks - and the timeline is the PLANE family's: one
# position is one recorded plane frame, i.e. one solver step, and the volume is a
# decimated LAYER painted at the position's NEAREST capture.  The rejected
# alternative - counting positions in the volume's frames - offered this dump
# three positions for twelve recorded steps and left nine of them, the tail
# included, unreachable.  Both halves come out of ONE index space,
# ``_volume_player_plan``, and these tests pin it on the player the page's own
# buttons call, never on a re-implementation.
# ---------------------------------------------------------------------------

#: Twelve plane frames against three |E| captures: one volume frame every 4th
#: step.  ``frame_index`` is the IDENTITY so a mapping that is off by a stride
#: reads as "step k shown at frame k" instead of hiding behind arithmetic.
DESYNC_NT = 12
DESYNC_FRAME_INDEX = tuple(range(DESYNC_NT))
DESYNC_VOLUME_STEPS = (0, 4, 8)
DESYNC_VOLUME_STRIDE = 4
#: Position -> stored |E| capture, now that the positions ARE the twelve plane
#: steps: step 1 is nearest capture 0, steps 2 and 6 are EXACT ties between two
#: captures and the earlier one wins.  Written out because it is the evidence - a
#: layer that rounded to the NEXT capture instead would read 0, 1, 1, 1, 2, ...
#: and be half a stride early from step 2 onwards.
DESYNC_VOLUME_NEAREST = (0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2)


def _desync_payload() -> dict:
    """``_payload``'s dump with the |E| volume saved every 4th step.

    The three volume frames are scaled by 1e3 apiece, so a per-frame colour
    range NAMES the frame it was measured on: a window measured on the wrong
    frame is a different pair of numbers, not a rounding difference.
    """
    payload = _payload(with_volume=False)
    rng = np.random.default_rng(2)
    payload["nt"] = np.array(DESYNC_NT)
    payload["t_ns"] = np.arange(DESYNC_NT) * 2e-3
    payload["ez_ycut"] = rng.normal(size=(DESYNC_NT, NX, NZ))
    payload["frame_index"] = np.array(DESYNC_FRAME_INDEX)
    payload["dump_stride"] = np.array(1)
    payload["nsteps"] = np.array(DESYNC_FRAME_INDEX[-1] + 1)
    volume = np.abs(rng.normal(size=(len(DESYNC_VOLUME_STEPS), NX, NY, NZ))) * 1e-3
    for frame in range(1, len(DESYNC_VOLUME_STEPS)):
        volume[frame] *= 1e3**frame
    payload["e_abs_volume"] = volume.astype(np.float32)
    payload["e_abs_volume_step_index"] = np.array(DESYNC_VOLUME_STEPS, dtype=int)
    payload["e_abs_volume_stride"] = np.array(DESYNC_VOLUME_STRIDE)
    return payload


@pytest.fixture(scope="module")
def desync_page(tmp_path_factory):
    """A page whose |E| volume is the COARSER recording: 3 captures, 12 planes."""
    with _render_doubled():
        live = _boot(
            tmp_path_factory.mktemp("desync"),
            with_volume=True,
            payload=_desync_payload(),
        )
        _silence_view(live)
        info = live.page["info"]
        assert info["e_abs_volume"] is not None, (
            "the desync fixture dump lost its |E| volume: nothing below would "
            "test the two clocks at all"
        )
        assert int(info["nt"]) > len(DESYNC_VOLUME_STEPS), (
            f"the desync dump has {int(info['nt'])} plane frames against "
            f"{len(DESYNC_VOLUME_STEPS)} volume frames: the volume is not the "
            "coarser recording, so there is no desynchronisation to test"
        )
        yield live


def _drawn_plane_frame(live, key: str = "ez_ycut") -> int:
    """WHICH stored plane frame the sheet is showing, read off the lattice.

    ``_show`` writes the selected frame into ``ez_abs`` on the sheet's own grid,
    so the drawn array IS one of the dump's frames and the index it matches is
    the frame on screen - the same evidence the volume layer leaves in
    ``handles["volume_layer"]["frame"]``, taken from the other half of the pair.
    """
    entry = _closure_cells(live.show)["sheets"][key]
    drawn = np.asarray(entry["grid"].point_data["ez_abs"], dtype=float)
    stored = np.abs(np.asarray(live.page["info"][key], dtype=float))
    for frame in range(stored.shape[0]):
        if np.array_equal(drawn, stored[frame].ravel(order="F")):
            return frame
    raise AssertionError(
        f"the {key} sheet is showing an array matching no stored frame: the "
        "picture on screen is not one of the dump's frames at all"
    )


def test_every_player_position_draws_one_time_step(desync_page):
    """Position k is ONE recorded plane frame, hence ONE solver step.

    THE BUG the other design had, which this pins the fix against: counting the
    timeline in the VOLUME's frames gave this dump three positions for twelve
    recorded steps, so nine plane frames - the tail included - could be reached
    by no slider position at all. The position is the plane family's own frame
    now, so every stored step is reachable, and the volume answers a DIFFERENT
    question: which stored capture is NEAREST this step. That is why the two
    indices are checked against the PLAN, never against each other - the old
    ``frame_index[plane] == steps[volume]`` would demand that the decimated layer
    advance in lockstep with the clock, i.e. hand the coarse grid the timeline
    back, which IS the defect. Counted on the RECORDED steps, not on the pixels:
    the sheet must be the instant the label names, and the layer must be the
    capture the plan names for that same instant.
    """
    live = desync_page
    info = live.page["info"]
    plan = app._volume_player_plan(info, "ycut")
    assert plan is not None, (
        "the desync dump carries an |E| volume, so the player must have a plan; "
        "without one there is no nearest capture to paint on the plane's clock"
    )
    steps = plan["steps"]
    assert plan["frames"] == DESYNC_NT, (
        f"the player steps {plan['frames']} positions for {DESYNC_NT} stored "
        "plane frames: a position IS one recorded plane frame, so the two "
        "counts are one number"
    )
    assert live.state.frame_max == DESYNC_NT - 1, (
        f"the slider's maximum is {live.state.frame_max}, not {DESYNC_NT - 1}: "
        "it is counted on the volume's captures, so most of the dump's steps "
        "cannot be reached from the input"
    )
    assert app._frame_span_max(plan["frames"], int(info["nt_x"]), "ycut") == (
        DESYNC_NT - 1
    ), (
        "the scrubber's range is "
        f"{app._frame_span_max(plan['frames'], int(info['nt_x']), 'ycut')}, not "
        f"{DESYNC_NT - 1}: the range is the y-cut family's own last frame"
    )
    assert plan["plane"] == tuple(range(DESYNC_NT)), (
        f"the plan maps the positions onto plane frames {plan['plane']}: the "
        "position IS that family's stored frame, so the map is the identity"
    )
    assert plan["volume"] == DESYNC_VOLUME_NEAREST, (
        f"the plan paints the volume as {plan['volume']}, not "
        f"{DESYNC_VOLUME_NEAREST}: the layer is the capture NEAREST the "
        "position's step (ties to the earlier one), never the position itself"
    )
    assert list(plan["volume"]) == sorted(plan["volume"]), (
        f"the layer visits the volume as {plan['volume']}: it may hold one "
        "capture and then advance, but it can never snap back to an earlier one"
    )

    frame_index = [int(value) for value in info["frame_index"]]
    t_ns = np.asarray(info["t_ns"], dtype=float)
    drawn = []
    with _render_doubled():
        for position in range(plan["frames"]):
            live.show(position, "ycut")
            plane_frame = _drawn_plane_frame(live)
            volume_frame = int(_layer_entry(live)["frame"])
            assert frame_index[plane_frame] == steps[position], (
                f"position {position} drew the cut plane at step "
                f"{frame_index[plane_frame]}, not the step {steps[position]} it "
                "is counted on: the sheet is not the instant the slider names"
            )
            assert volume_frame == plan["volume"][position], (
                f"position {position} painted volume frame {volume_frame}, not "
                f"the nearest capture {plan['volume'][position]}: the layer and "
                "the clock disagree about which capture this instant is"
            )
            assert live.state.t_label == f"sim time: t = {t_ns[plane_frame]:.6f} ns", (
                f"position {position} printed {live.state.t_label!r} beside a "
                f"cut plane at step {frame_index[plane_frame]} "
                f"(t = {t_ns[plane_frame]!r}): the label is a third clock"
            )
            drawn.append(plane_frame)
    assert drawn == list(range(DESYNC_NT)), (
        f"the player drew plane frames {drawn}: every stored frame is a "
        "position, so none may be skipped and none shown twice"
    )


def test_a_dump_without_a_volume_keeps_the_plane_clock(no_volume_page):
    """No volume, no plan: every position is still its own plane frame.

    The negative half of the fix, and the reason it can land at all - most dumps
    carry no |E| volume (only ``--volume-stride`` writes one), and for them the
    player must behave byte-for-byte as it did: the slider spans ``nt`` frames,
    position k draws plane frame k, and the label names that frame's time.
    """
    live = no_volume_page
    info = live.page["info"]
    assert app._volume_player_plan(info, "ycut") is None, (
        "a dump with no |E| volume was given a player plan: there is no second "
        "clock to reconcile, so nothing may be remapped"
    )
    assert app._volume_player_plan(info, "xcut") is None
    nt = int(info["nt"])
    assert live.state.frame_max == nt - 1, (
        f"the slider's maximum is {live.state.frame_max}, not {nt - 1}: a page "
        "with no volume must keep its plane clock"
    )

    t_ns = np.asarray(info["t_ns"], dtype=float)
    with _render_doubled():
        for position in range(nt):
            live.show(position, "ycut")
            assert _drawn_plane_frame(live) == position, (
                f"position {position} drew plane frame "
                f"{_drawn_plane_frame(live)}: the position is no longer the frame"
            )
            assert live.state.t_label == (
                f"sim time: t = {t_ns[position]:.6f} ns"
            ), (
                f"position {position} printed {live.state.t_label!r}, not that "
                "frame's own recorded time"
            )


def test_the_plan_maps_the_boundaries_and_the_tail(desync_page):
    """The plan's arrays, checked at the boundaries and at the TAIL it reaches.

    ``plane`` is the whole content of the fix: position k IS plane frame k, the
    identity, because a position is one recorded plane frame. The TAIL is the
    half the other design lost: with the positions counted in the volume's
    frames the timeline ended at the last capture's step, so every plane frame
    recorded after it - nine of these twelve, the whole last quarter of the run -
    was unreachable from the player. Here the last position is the last stored
    plane frame and the last capture is merely PAINTED at it, which is why both
    ends are asserted: a reachable tail that never shows the end of the film
    would be the same lost frame at the other end.
    """
    info = desync_page.page["info"]
    nt, nt_x = int(info["nt"]), int(info["nt_x"])
    plan = app._volume_player_plan(info, "ycut")
    assert plan is not None, (
        "the desync dump carries an |E| volume, so a plan is expected; None "
        "here means the volume would have to be drawn off some other index"
    )
    axis = [int(value) for value in info["frame_index"]]
    assert plan["steps"] == tuple(axis), (
        f"the plan's steps are {plan['steps']}, not the recorded {tuple(axis)}: "
        "a position is one recorded plane frame, so the steps ARE that axis"
    )
    assert plan["frames"] == DESYNC_NT == nt, (
        f"the plan counts {plan['frames']} positions where the file holds {nt} "
        "plane frames: the timeline is that family's own recorded frames"
    )
    assert plan["plane"] == tuple(range(plan["frames"])), (
        f"the plan walks the plane as {plan['plane']}: position k IS plane "
        "frame k"
    )
    assert plan["plane"][-1] == DESYNC_NT - 1, (
        f"the last position maps to plane frame {plan['plane'][-1]}, not to the "
        f"last stored frame {DESYNC_NT - 1}: the tail of the timeline is "
        "unreachable again"
    )
    assert plan["volume"][-1] == len(DESYNC_VOLUME_STEPS) - 1, (
        f"the last position paints volume frame {plan['volume'][-1]}, not the "
        f"last capture {len(DESYNC_VOLUME_STEPS) - 1}: the end of the film is "
        "never shown"
    )
    assert app._synced_frame_counts(info, nt, nt_x) == (nt, nt_x), (
        f"the synced counts are {app._synced_frame_counts(info, nt, nt_x)}, "
        f"not ({nt}, {nt_x}): each family's timeline is its own recorded "
        "frames, so the coarser |E| volume can no longer shorten the y-cut clock"
    )


def test_per_frame_clim_follows_the_volume_frame_the_player_is_showing(desync_page):
    """Requirement 3, on the frame the PLAYER is showing.

    A per-frame colour range is only meaningful if it is measured on the frame
    on screen, and on this dump that frame is the capture NEAREST the position's
    step (``_volume_player_plan``'s ``volume``) - never the position itself,
    because the |E| recording is decimated. A window taken from any other
    capture grades a picture that is not there, and the nearest ones are a stride
    apart, so that is a different pair of numbers and not a rounding difference.
    Asserted on the numbers the mapper was given (this image has no OpenGL), for
    every position, plus the sequence of frames the layer actually reported -
    which is the plan's mapping and NOT a walk through the captures: positions
    0..2 all show frame 0, so asserting ``range(3)`` would be asserting the
    coarse timeline back.
    """
    live = desync_page
    info = live.page["info"]
    volume = info["e_abs_volume"]
    plan = app._volume_player_plan(info, "ycut")
    assert plan is not None, "no plan: the positions below would not be the volume's"

    seen = []
    with _clim_mode(live, app.VOLUME_CLIM_PER_FRAME), _render_doubled():
        for position in range(plan["frames"]):
            # One volume at a time: pyvista shares ONE scalar range between the
            # volumes in a scene, so an orphan from the previous position would
            # widen this position's window into a union of two ranges.
            _only_the_layers_volume(live)
            live.show(position, "ycut")
            frame = int(_layer_entry(live)["frame"])
            expected = int(plan["volume"][position])
            assert frame == expected, (
                f"position {position} painted volume frame {frame}, not the "
                f"nearest capture {expected}: the window below would be "
                "measured on whatever this layer happened to show"
            )
            peak = float(np.max(np.abs(volume[expected])))
            window = (peak * 1e-3, peak)
            assert _drawn_range(live) == pytest.approx(window, rel=1e-6), (
                f"position {position} painted volume frame {frame} on "
                f"{_drawn_range(live)}, not on that frame's own 60 dB window "
                f"{window}: the range is measured on a picture that is not on "
                "screen"
            )
            seen.append(frame)

    assert seen == list(plan["volume"]), (
        f"the player painted volume frames {seen} over "
        f"{plan['frames']} positions, not the plan's {list(plan['volume'])}: "
        "the positions are counted on one clock and painted on another"
    )




# ---------------------------------------------------------------------------
# THE TWO COLOUR BARS.  The plane sheets and the |E| volume are two DIFFERENT
# fields on two different scales (the FFT normalisation makes the volume ~2053x
# smaller in V/m), so each needs its own bar - and, because a title is pyvista's
# KEY for a bar, "own bar" is a claim about the title as much as about the
# numbers: a second bar added under an existing title is MERGED with it, and the
# range becomes the UNION of both mappers'.  Everything below reads the bar off
# the real plotter; the lookup table ``add_scalar_bar(mapper=...)`` hands it IS
# the mapper's own, so the range read here is the range the bar grades.
# ---------------------------------------------------------------------------


# The |E| bar's title NAMES the colour-scale window the picture was drawn under,
# so it is no longer one fixed string.  These two are the titles of the two modes;
# a test reading a bar asks for the one the draw in front of it used.
VOLUME_BAR = app._volume_bar_title(app.VOLUME_CLIM_DEFAULT)
VOLUME_BAR_PER_FRAME = app._volume_bar_title(app.VOLUME_CLIM_PER_FRAME)


def _bar(live, title: str):
    """The bar standing under ``title``, or a failure that names what IS there."""
    bars = live.plotter.scalar_bars
    assert title in bars, (
        f"no colour bar titled {title!r} is on the page; it stands "
        f"{sorted(bars.keys())}"
    )
    return bars[title]


def _bar_range(live, title: str) -> tuple:
    """The range the bar for ``title`` actually grades.

    ``add_scalar_bar(mapper=...)`` gives the bar that mapper's OWN lookup table,
    so this reads what the bar shows - not what a call was asked for.
    """
    lut = _bar(live, title).GetLookupTable()
    assert lut is not None, f"the bar titled {title!r} carries no lookup table"
    return tuple(float(value) for value in lut.GetRange())


def _bar_span(bar) -> tuple:
    """A bar's horizontal footprint in normalised viewport coordinates."""
    left = float(bar.GetPosition()[0])
    return (left, left + float(bar.GetWidth()))


def _volume_frame_shown(info: dict, index: int, mode: str = "ycut") -> int:
    """The stored |E| frame animation position ``index`` maps onto."""
    axis = info["frame_index" if mode == "ycut" else "frame_index_xcut"]
    frame = app._volume_frame_for_step(
        info.get("e_abs_volume_step_index"), int(axis[index])
    )
    assert frame is not None, (
        f"animation position {index} (step {int(axis[index])}) maps onto no "
        "stored |E| frame, so the assertions below would have nothing to read"
    )
    return int(frame)


def test_the_page_stands_exactly_two_bars_named_for_the_two_fields(tmp_path):
    """TWO bars, titled for the two fields - at boot and after.

    The |E| bar's title also NAMES the colour-scale window in force, so the exact
    strings asserted here are the default (global) window's.

    WHY the titles are written out as literals here: they are what a reader of
    the picture sees, and they are pyvista's keys.  Asserting them against the
    module's own constants would pin nothing - a renamed constant would move the
    bar with it and the test would still pass.

    WHY after a draw too: the boot picture is one frame, and every later frame
    rebuilds the volume layer (and, on a plane switch, the plane's bar).  A bar
    added per draw without being removed first is how this page would end up
    with three, or with two bars unioned into one.
    """
    with _render_doubled():
        live = _boot(tmp_path, with_volume=True)
        _silence_view(live)

        assert set(live.plotter.scalar_bars.keys()) == {
            app.PLANE_BAR_TITLE,
            VOLUME_BAR,
        }, (
            "the first picture the page draws stands "
            f"{sorted(live.plotter.scalar_bars.keys())}, not one bar for the "
            "planes and one for |E|"
        )
        assert set(live.plotter.scalar_bars.keys()) == {
            "Ez (Linear)",
            "|E| (Log) - Global (Comparable)",
        }, (
            "the bars are titled "
            f"{sorted(live.plotter.scalar_bars.keys())}, not "
            '{"Ez (Linear)", "|E| (Log) - Global (Comparable)"}: a title is the '
            "key pyvista stores a bar under, and it is what the reader is told "
            "the colours mean"
        )

        for index in (0, 3):
            _only_the_layers_volume(live)
            live.draw(index, "ycut")
            assert set(live.plotter.scalar_bars.keys()) == {
                app.PLANE_BAR_TITLE,
                VOLUME_BAR,
            }, (
                f"after drawing frame slider {index} the page stands "
                f"{sorted(live.plotter.scalar_bars.keys())}: a draw added or "
                "dropped a bar"
            )

    # Explicitly positioned bars consume NO auto-placement slot, so a page that
    # ever falls back to the theme's slot engine would collide with itself.
    slots = getattr(live.plotter, "_scalar_bar_slot_lookup", None)
    assert slots == {}, (
        f"the two bars took {slots!r} of pyvista's auto-placement slots; both "
        "are placed by explicit position and must take none"
    )


def test_the_volume_bar_follows_the_frame_the_volume_is_painted_on(volume_page):
    """The |E| bar grades each frame's OWN window - and SHRINKS back after a peak.

    WHY the shrink is the assertion and not merely the value: a bar re-added
    under an existing title is MERGED, and the merged range is the union of
    every mapper ever bound to that key.  On this dump the loud frame peaks 1e6
    above the quiet one, so a merged bar would keep the loud peak forever and
    every later frame would paint itself into the bottom pixel of the scale -
    the reading would be wrong while the colours still looked plausible.
    """
    live = volume_page
    info = live.page["info"]
    volume = info["e_abs_volume"]

    loud = _volume_frame_shown(info, LOUD_FRAME)
    quiet = _volume_frame_shown(info, QUIET_FRAME)
    loud_peak = float(np.max(volume[loud]))
    quiet_peak = float(np.max(volume[quiet]))
    assert loud_peak > quiet_peak * 100.0, (
        f"volume frame {loud} peaks at {loud_peak!r} against {quiet_peak!r} on "
        f"frame {quiet}: the two are too close for this test to tell a fresh "
        "range from a union of both"
    )

    with _clim_mode(live, app.VOLUME_CLIM_PER_FRAME):
        for index in range(NT):
            # One volume at a time: a scene shares ONE scalar range between the
            # volumes in it, so an orphan would widen this frame's window.
            _only_the_layers_volume(live)
            live.draw(index, "ycut")
            frame = _volume_frame_shown(info, index)
            assert int(_layer_entry(live)["frame"]) == frame, (
                f"frame slider {index} drew volume frame "
                f"{_layer_entry(live)['frame']}, expected {frame}: the "
                "assertions below would be reading another frame's bar"
            )
            peak = float(np.max(volume[frame]))
            window = app._volume_abs_frame_clim(volume, frame)
            assert window == pytest.approx((peak * 1e-3, peak), rel=1e-12), (
                f"the resolver answers {window} for frame {frame}, not its own "
                f"60 dB window {(peak * 1e-3, peak)}"
            )
            drawn = _bar_range(live, VOLUME_BAR_PER_FRAME)
            assert drawn == pytest.approx(window, rel=1e-6), (
                f"frame slider {index} (volume frame {frame}) leaves the "
                f"\"{VOLUME_BAR_PER_FRAME}\" bar grading {drawn}, not that "
                f"frame's own window {window}: the bar does not describe the "
                "picture it stands over"
            )

    # The LAST position drawn was the quiet frame, right after the loud one - and
    # nothing has been redrawn since, so the bar still stands under the per-frame
    # title (the mode the block drew with).
    last = _bar_range(live, VOLUME_BAR_PER_FRAME)
    assert last[1] == pytest.approx(quiet_peak, rel=1e-6), (
        f"after the loud frame {loud} the bar still reads up to {last[1]!r}, "
        f"not the quiet frame {quiet}'s peak {quiet_peak!r}: the range was "
        "UNIONed with the frame before it (a bar re-added under the same title "
        "merges) instead of being replaced"
    )
    assert last[1] < loud_peak, (
        f"the bar never came back down from {loud_peak!r} (still {last[1]!r}): "
        "one loud frame left its peak on the scale for good"
    )


def test_the_volume_bar_never_touches_the_plane_bar(volume_page):
    """|E| draws change the |E| bar and leave the PLANE bar exactly as it was.

    WHY identity and not just the number: the plane bar is ONE object the page
    keeps for the whole plane family, placed from the sheet on screen.  A volume
    draw that removed and re-created it under the same title would merge its
    range with the volume's mappers - the plane bar would then grade the plane
    colours on a range that includes a field 2053x smaller, i.e. not at all.
    """
    live = volume_page
    vmin, vmax = live.page["info"]["color_range"]

    _only_the_layers_volume(live)
    live.draw(0, "ycut")
    plane = _bar(live, app.PLANE_BAR_TITLE)
    plane_range = _bar_range(live, app.PLANE_BAR_TITLE)
    assert plane_range == pytest.approx(
        (float(vmin), float(vmax)), rel=1e-9
    ), (
        f"the plane bar grades {plane_range}, not the sheets' fixed "
        f"{(float(vmin), float(vmax))}: nothing below could then show that the "
        "volume leaves it alone"
    )

    volume_bar = _bar(live, VOLUME_BAR)
    assert volume_bar is not plane, (
        "the plane and the |E| volume share ONE bar object: two fields on two "
        "scales cannot be read off one scale"
    )
    assert volume_bar.GetLookupTable() is not plane.GetLookupTable(), (
        "the two bars share a lookup table, so each one's range moves with the "
        "other's"
    )

    for index in (1, 2, 3):
        _only_the_layers_volume(live)
        live.draw(index, "ycut")
    with _clim_mode(live, app.VOLUME_CLIM_PER_FRAME):
        _only_the_layers_volume(live)
        live.draw(1, "ycut")

    assert _bar(live, app.PLANE_BAR_TITLE) is plane, (
        "a volume draw replaced the plane bar: the new one is bound to whatever "
        "mappers the volume brought, so the plane colours are now graded on a "
        "range that is not the sheets'"
    )
    assert _bar_range(live, app.PLANE_BAR_TITLE) == pytest.approx(
        plane_range, rel=1e-12
    ), (
        "the plane bar's range moved from "
        f"{plane_range} to {_bar_range(live, app.PLANE_BAR_TITLE)} while only "
        "the |E| volume was being drawn"
    )


def test_watching_the_clip_piles_up_neither_bars_nor_actors(volume_page):
    """Eight frame steps: still TWO bars, still the same scene, still apart.

    WHY both halves: a bar per frame is the same leak as an actor per frame, only
    harder to notice - the picture looks right and the third bar sits on top of
    the first.  The footprints are checked as well because two bars placed over
    each other would be one readable bar and one hidden, whatever their count.
    """
    live = volume_page
    _only_the_layers_volume(live)
    live.draw(0, "ycut")

    actors = len(live.plotter.actors)
    bars = len(live.plotter.scalar_bars)
    for step in range(2 * NT):
        live.trigger()
        assert len(live.plotter.scalar_bars) == bars, (
            f"{step + 1} frame steps left "
            f"{len(live.plotter.scalar_bars)} bars on the page, not {bars}: a "
            "draw adds a bar without removing the one it replaces"
        )
        assert set(live.plotter.scalar_bars.keys()) == {
            app.PLANE_BAR_TITLE,
            VOLUME_BAR,
        }, (
            f"after {step + 1} frame steps the page stands "
            f"{sorted(live.plotter.scalar_bars.keys())}"
        )
        assert len(live.plotter.actors) == actors, (
            f"the scene grew from {actors} to {len(live.plotter.actors)} actors "
            f"after {step + 1} frame steps"
        )

    plane_span = _bar_span(_bar(live, app.PLANE_BAR_TITLE))
    volume_span = _bar_span(_bar(live, VOLUME_BAR))
    assert (
        plane_span[1] <= volume_span[0] or volume_span[1] <= plane_span[0]
    ), (
        f"the two bars overlap: the plane bar covers {plane_span} and the |E| "
        f"bar {volume_span} of the viewport width - whichever is behind the "
        "other is unreadable"
    )
    for name, span in (
        (app.PLANE_BAR_TITLE, plane_span),
        (VOLUME_BAR, volume_span),
    ):
        assert 0.0 <= span[0] < span[1] <= 1.0, (
            f"the bar titled {name!r} spans {span} of the viewport, which is "
            "not on screen"
        )



def test_the_frame_label_counts_the_positions_the_player_steps(desync_page):
    """The step sentence's denominator is the count the player actually steps.

    ``_frame_label`` is the only place that sentence is composed, and it is what
    ``_show`` prints, so the denominator a reader sees must be the number of
    positions the scrubber can reach - twelve here, NOT the volume's three: a
    label reading "frame 1 / 3" beside a slider that runs to 11 offers three
    positions for twelve recorded steps, which is the coarse timeline speaking.

    On THIS dump the sentence is the frame-only one, and that is the recorded
    truth rather than a gap: ``frame_index`` is ZERO-BASED here, and a solver
    step is 1-based in every dump on disk, so ``TimeAxis`` refuses to name a
    step for it (0 is a broken record, not step zero) and the fallback prints
    the frame it does stand on. Asserted, not fixed: inventing "Step 0 / 12"
    would be this label claiming an axis the file does not record.
    """
    live = desync_page
    nt = int(live.page["info"]["nt"])
    assert nt == DESYNC_NT, (
        f"the fixture stores {nt} plane frames, not {DESYNC_NT}: the denominator "
        "below would not be the count under test"
    )
    assert app._frame_label(0, nt) == f"frame 1 / {nt}", (
        f"the label composes {app._frame_label(0, nt)!r}, not 'frame 1 / {nt}'"
    )
    assert app._frame_label(nt - 1, nt) == f"frame {nt} / {nt}", (
        "the LAST position no longer prints as the last frame: "
        f"{app._frame_label(nt - 1, nt)!r}"
    )
    assert app._frame_label(0, None) is None, (
        "a page with no timeline composed a label instead of leaving it ABSENT: "
        "None is 'no timeline', never 'frame 1 / None'"
    )

    with _render_doubled():
        live.show(0, "ycut")
    axis = live.page["info"].get(app.TIME_AXIS_KEY)
    named = None if axis is None else axis.label(1)
    assert axis is not None and named is None, (
        f"the zero-based frame_index is being labelled as a solver step "
        f"({named!r}): a step axis that starts at 0 is a broken record, so the "
        "sentence has to fall back instead of quoting it"
    )
    assert live.state.frame_label == f"frame 1 / {nt}", (
        f"the player printed {live.state.frame_label!r} on a timeline of {nt} "
        f"positions: the denominator is the dump's {nt} plane frames - the "
        "volume's captures are a layer on that clock, not the clock"
    )


def test_the_state_dump_counts_the_frames_the_player_steps(desync_page):
    """``_animation_block`` must not drift from ``_synced_frame_counts``.

    The state document is what an operator reads to check what the page
    believes, so its two counts - and the wall clock built from them - are
    claims. Both are now each family's OWN recorded frames (twelve y-cut, three
    x-cut here), because a position is a plane frame and the |E| volume is a
    layer painted on that clock: reporting three would claim the y-cut slider
    ends at the last capture, i.e. throw away the nine steps after it - the
    coarse timeline the design change removed.

    The wall clock is those counts over ``fps``, which is ONE POSITION PER TICK,
    while the play loop advances ``PLAY_STEPS_PER_TICK`` positions per tick - so
    the time the page really takes is that over the same constant. Written
    through ``app.PLAY_STEPS_PER_TICK`` rather than a typed-in 8: the two
    numbers describe one advance, and a change to either must fail here instead
    of leaving the state dump quietly describing the old rate.
    """
    info = desync_page.page["info"]
    nt, nt_x = int(info["nt"]), int(info["nt_x"])
    synced = app._synced_frame_counts(info, nt, nt_x)
    assert synced == (nt, nt_x), (
        f"the fixture no longer reports its own frames: synced {synced} against "
        f"({nt}, {nt_x}), so the counts below cannot be read as the player's"
    )
    assert nt == DESYNC_NT > len(DESYNC_VOLUME_STEPS), (
        f"the fixture stores {nt} plane frames over "
        f"{len(DESYNC_VOLUME_STEPS)} captures: the volume is not the coarser "
        "recording, so nothing below can tell the two counts apart"
    )

    block = app._animation_block(info)
    assert block["frames"] == synced[0] == nt, (
        f"the state dump says the animation has {block['frames']} frames, not "
        f"{nt}: the y-cut timeline is that family's own recorded frames"
    )
    assert block["frames_xcut"] == synced[1], (
        f"the x-cut count is {block['frames_xcut']}, not {synced[1]}: each "
        "family's count is its own, and the volume touches neither"
    )
    assert block["wall_clock_s"] == pytest.approx(
        block["frames"] / block["fps"], rel=1e-12
    ), (
        f"the wall clock is {block['wall_clock_s']} s: it is the "
        f"{block['frames']} positions the player steps over {block['fps']} "
        "fps, i.e. at one position per tick"
    )
    assert block["wall_clock_s"] == pytest.approx(
        block["frames"]
        / (block["fps"] * app.PLAY_STEPS_PER_TICK)
        * app.PLAY_STEPS_PER_TICK,
        rel=1e-12,
    ), (
        f"the wall clock {block['wall_clock_s']} s is not the one-position-per-"
        f"tick reading of {block['frames']} positions at {block['fps']} fps "
        f"over {app.PLAY_STEPS_PER_TICK} positions per tick: the state dump and "
        "the play loop no longer describe the same advance"
    )
    assert block["planes"][0]["frames"] == nt, (
        "the stored ez_ycut plane is reported as holding "
        f"{block['planes'][0]['frames']} frames, not the {nt} it holds: a "
        "plane entry states a fact about the FILE, not about the timeline"
    )


def test_the_left_panel_header_counts_the_frames_the_player_steps(tmp_path):
    """The LEFT column's header line and the state dump tell ONE frame count.

    ``build_left_panel`` prints ``state.page_source_text`` (um3k_panels.py:38) and
    ``run_web_vis`` fills it from ``_page_source_text(info, nt)`` with the ``nt``
    the timeline fence has already re-synced (poc_app.py:10047, then 10292) - a
    DIFFERENT expression from the state dump's ``_animation_block``, so the two
    can drift apart. What ``_synced_frame_counts`` now answers, and therefore
    what both must say on the desync dump, is the PLANE family's twelve frames:
    the player steps one plane position per step, and the |E| volume's three
    captures are a decimated layer ON that clock, not a clock of their own
    (``_volume_player_plan`` reports the same twelve). A header reading "3 of
    12 frames on ez_ycut" would name the volume's three-value grid as the
    timeline the scrubber runs on - the very misreading this change removes -
    so on this dump the plain one-number form is the correct one, quoting the
    twelve the player actually steps.

    The helper's two-number branch is NOT dead: it still fires whenever the
    player's timeline and the stored array disagree, which the pure call below
    exercises directly rather than through a boot.

    Booted HERE instead of read off the module-scoped ``desync_page``: the frame
    server is process-wide (see ``_boot``), so ``state`` is shared and every
    later boot in this file would overwrite ``page_source_text`` under the test -
    the desync dump has to be the LAST write.
    """
    three = len(DESYNC_VOLUME_STEPS)
    with _render_doubled():
        live = _boot(tmp_path, with_volume=True, payload=_desync_payload())
        _silence_view(live)
        info = live.page["info"]
        nt, nt_x = int(info["nt"]), int(info["nt_x"])
        assert nt > three, (
            f"the desync dump has {nt} plane frames against {three} volume "
            "frames: the volume is not the coarser recording, so there is no "
            "desynchronisation to test"
        )
        assert app._synced_frame_counts(info, nt, nt_x) == (nt, nt_x), (
            f"the timeline fence answers {app._synced_frame_counts(info, nt, nt_x)}, "
            f"not ({nt}, {nt_x}): the header below would then be quoting a "
            "clock the plane family does not hold"
        )
        assert app._volume_player_plan(info, "ycut")["frames"] == nt, (
            "the player does not step the plane family's frames on this dump, "
            "so the header cannot agree with the scrubber beside it"
        )
        text = live.state.page_source_text
        assert f"animation, {nt} frames on ez_ycut" in text, (
            f"the left panel prints {text!r}, not 'animation, {nt} frames on "
            "ez_ycut': the player steps the plane family's own frames, so the "
            "header must quote the count the scrubber reaches"
        )
        assert " of " not in text, (
            f"the left panel printed {text!r}: the 'of' form is for a page "
            "whose player timeline and stored array DIFFER, and on this dump "
            "both are the plane family's twelve frames"
        )
        # The two-number branch the header keeps for a page where the player's
        # timeline and the stored array really do differ - still reachable, so
        # it is asserted through the pure helper.
        assert app._page_source_text(info, three).endswith(
            f"animation, {three} of {nt} frames on ez_ycut"
        ), (
            f"quoting a {three}-frame timeline over a {nt}-frame array printed "
            f"{app._page_source_text(info, three)!r}: a header that quotes only "
            "one of two differing numbers names the wrong one for the other"
        )

    # A page with no |E| volume: one clock, so the plain form must be untouched.
    with _render_doubled():
        plain = _boot(tmp_path, with_volume=False)
        _silence_view(plain)
        n = int(plain.page["info"]["nt"])
        plain_text = plain.state.page_source_text
    assert f"animation, {n} frames on ez_ycut" in plain_text, (
        f"a dump with no |E| volume prints {plain_text!r}, not 'animation, {n} "
        "frames on ez_ycut': its timeline and its stored array are one clock, "
        "so the plain form must be untouched"
    )
    assert " of " not in plain_text, (
        f"a page whose two frame counts agree printed {plain_text!r}: the "
        "'of' form is for a page where they DIFFER"
    )

