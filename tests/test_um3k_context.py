"""The page context: what one um3k page loaded, can show, and has registered.

``server/um3k_context.py`` exists so that the three questions a page asks of
itself - which key names the data is read by, which views the loaded data
supports (``Available``), and which callable or handle a draw path left under a
name - can be answered, and tested, with no trame, no VTK and no window open.
Nothing here loads a file: every page below is a dict shaped like the one
``reload_page`` assembles (poc_app.py:5364-5376).

The claims, one per test:

* a page constructs BARE - no dump, no plotter, no handles, view ``"volume"``,
  and every availability flag false - so a window can exist before a load;
* importing the module in a FRESH interpreter leaves ``trame`` and ``pyvista``
  out of ``sys.modules``, which is what keeps the flag layer importable on a
  machine with no UI stack installed;
* ``Available.compute`` on a realistic legacy field page turns on the plane
  views from the station AXIS, not from any widget;
* ``volume_field`` (the 3-D vector field, a question about the KEYS present) and
  ``plane_stack`` (more than one captured x-plane) are INDEPENDENT, proved on a
  one-station dump that carries a volume and a nine-station dump that does not;
* ``Available.compute`` on a realistic animation page says "animation" and says
  nothing about stations, because that page forks to its own viewer;
* the snapshot really is a snapshot: replacing ``dump`` moves no flag until
  ``recompute_available`` is called, and the retired object stays as it was;
* ``set_view_mode`` accepts both strings the label branches on and reports the
  mode it stored;
* ``set_view_mode`` refuses a misspelling with a message naming the bad string
  and both legal ones, and leaves the stored mode untouched;
* ``from_any_dump`` maps the page dict by key and a seven-element page by
  position in ``PAGE_FIELDS`` order - proved with one distinct value per field,
  so a transposed pair fails;
* a page of the wrong length is refused with a message naming both counts;
* a callback and a handle come back by name, and a name nobody registered
  raises ``KeyError`` naming it rather than handing back ``None``;
* an empty page answers every flag false and never raises - a deleted dump must
  not become a traceback;
* every name literal the module copies is pinned against poc_app's own source
  of truth, so the copies cannot drift in silence.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import um3k_context  # noqa: E402 - the path above is what makes it importable


class _Stack:
    """Just enough of an ndarray for ``_stations``: a ``shape`` and nothing else.

    Standing in for ``np.load``'s ``plane_ez`` keeps this file free of the dump
    it would otherwise have to read; the axis order is the loaded one
    (poc_app.py:214-217: station, y, z).
    """

    def __init__(self, n_st, n_y=17, n_z=19):
        self.shape = (n_st, n_y, n_z)


def _field_info(n_st=9):
    """The info dict a legacy field dump loads into (poc_app.py:215-223)."""
    return {
        um3k_context.PLANE_KEY: _Stack(n_st),
        "nstep": n_st,
        "nx": 17,
        "ny": 19,
        "nz": 21,
        "cell_m": 1e-4,
        "path": REPO_ROOT / "evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz",
    }


def _field_planes(src_s11="geometry.ix_port"):
    """The layout ``_plane_layout`` returns for a field page (poc_app.py:3172-3187)."""
    return {
        "cell_mm": 0.1,
        "n_st": 9,
        "stations_mm": [i * 0.1 for i in range(9)],
        "x_load_mm": 0.4,
        "src_load": "geometry.loads[0].x",
        "ix_load": 4.0,
        "x_s11_mm": 0.1,
        "src_s11": src_s11,
        "x_s21_mm": 0.8,
        "src_s21": "geometry.s21_plane.x_m",
        "s21_valid": True,
        "s21_valid_src": "computed",
        "s21_reason": "",
        "slice_index": 1,
    }


def _vis_info():
    """The info dict a vis dump loads into (poc_app.py:483-532)."""
    return {
        "path": REPO_ROOT / "evidence/termination/build_A_50ohm_p51_wavedude.npz",
        "format": um3k_context.VIS_FORMAT,
        "schema": "emfit.vis/2",
        "engine": "emfit",
        "created_utc": "2026-01-01T00:00:00Z",
        "structure_id": "build_A_50ohm_p51",
        "load_ohm": 50.0,
        "frames": 41,
        "fps": 12.0,
    }


def test_page_context_constructs_bare():
    """If this fails, a page cannot exist before a dump is loaded.

    Everything downstream - the empty-window path, and every other test here -
    assumes ``PageContext()`` is legal with no arguments: no path, no plotter,
    the default view, and every flag false rather than unset.
    """
    ctx = um3k_context.PageContext()

    assert isinstance(ctx.dump, um3k_context.LoadedDump)
    assert ctx.dump.path is None
    assert ctx.dump.info == {}
    assert ctx.dump.planes == {}
    assert ctx.dump.multifreq is None
    assert ctx.dump.structure_id is None
    assert ctx.dump.record is None
    assert ctx.dump.is_vis is None

    assert ctx.view_mode == "volume"
    assert ctx.plotter is None
    assert ctx.handles == {}
    assert ctx.callbacks == {}

    available = ctx.available
    assert available.volume_field is False
    assert available.plane_stack is False
    assert available.port_planes is False
    assert available.multifreq is False
    assert available.record is False
    assert available.s11_record is False
    assert available.animation is False
    assert available.source_format == "field"


def test_importing_the_module_pulls_in_no_ui_stack():
    """If this fails, the flag layer dragged trame or pyvista in on import.

    The point of the module is to be importable where the UI stack is absent,
    so the check runs in a FRESH interpreter: this process has already imported
    pytest (and whatever pytest loads), which would hide the module's own
    behaviour. A non-zero exit or a missing ``clean`` is the failure, and the
    child's stderr is printed so the offending import is named.
    """
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
        f"sys.path.insert(0, {str(REPO_ROOT / 'server')!r})\n"
        "import um3k_context\n"
        "assert 'trame' not in sys.modules, "
        "[m for m in sys.modules if m.startswith('trame')]\n"
        "assert 'pyvista' not in sys.modules, [m for m in sys.modules "
        "if m.startswith('pyvista')]\n"
        "print('clean')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=str(REPO_ROOT),
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"importing um3k_context in a fresh interpreter failed\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "clean" in proc.stdout, (
        f"the child printed {proc.stdout!r} instead of clean\n"
        f"stderr:\n{proc.stderr}"
    )


def test_available_from_a_legacy_field_page():
    """If this fails, a field dump's plane/volume views are read from the wrong axis.

    The station AXIS decides ``port_planes`` and ``plane_stack`` (poc_app.py:3167-
    3170 for one plane, :3280-3281 for the stack), and the loader's info dict is
    the only place that axis lives. Neither page below carries a volume key, so
    ``volume_field`` stays false while the station flags move.
    """
    planed = um3k_context.Available.compute(
        _field_info(n_st=1), _field_planes(), multifreq=None, record=None,
    )
    assert planed.port_planes is True
    assert planed.plane_stack is False  # one station is not a stack
    assert planed.volume_field is False  # and no volume key is present
    assert planed.record is False
    assert planed.s11_record is True  # the record carried the port plane
    assert planed.animation is False
    assert planed.source_format == "field"

    stacked = um3k_context.Available.compute(
        _field_info(n_st=9), _field_planes(), multifreq=None,
        record={"geometry": {"ix_port": 4}, "f_hz": 1.0e9},
    )
    assert stacked.port_planes is True
    assert stacked.plane_stack is True
    assert stacked.volume_field is False  # nine x-planes, still no volume
    assert stacked.record is True
    assert stacked.multifreq is False
    assert stacked.animation is False

    # An unrecorded port x is the FALLBACK constant and the flag says so
    # (poc_app.py:3123, :3248).
    fallback = um3k_context.Available.compute(
        _field_info(), _field_planes(src_s11=um3k_context.FALLBACK_SRC),
    )
    assert fallback.s11_record is False


def test_available_from_an_animation_page():
    """If this fails, a vis dump is described as a field page or vice versa.

    An animation page forks to its own viewer before any station logic runs
    (poc_app.py:9734-9750), so only ``animation``/``source_format`` describe it:
    it has no plane stack, and its layout carries no recorded port plane.
    """
    available = um3k_context.Available.compute(
        _vis_info(),
        {"src_s11": um3k_context.FALLBACK_SRC, "slice_index": 3, "n_st": 9},
        multifreq=[um3k_context.VIS_FORMAT],
        record=None,
    )
    assert available.animation is True
    assert available.source_format == "vis"
    assert available.volume_field is False
    assert available.plane_stack is False
    assert available.port_planes is False
    assert available.s11_record is False
    assert available.multifreq is True
    assert available.record is False

    # Nobody has said which loader produced the page: the loader's own rule
    # decides (poc_app.py:338), and an explicit answer wins over it.
    assert um3k_context.Available.compute(_vis_info()).animation is True
    assert um3k_context.Available.compute({}, {}, is_vis=True).animation is True
    assert um3k_context.Available.compute(_vis_info(), {}, is_vis=False).animation is False


def test_available_is_a_frozen_snapshot_until_recomputed():
    """If this fails, a flag read and the draw after it can see the ground move.

    ``available`` is computed once and frozen (the dataclass is frozen, and
    nothing recomputes behind a setter), so replacing ``dump`` must NOT move a
    flag: whoever swaps the page calls ``recompute_available`` and passes the
    new snapshot on. Both halves matter - a silent recompute is as wrong as a
    missing one, because the caller cannot tell which flags it read.
    """
    seeded = um3k_context.PageContext(dump=um3k_context.LoadedDump(info=_field_info(3)))
    assert seeded.available.port_planes is True  # computed at construction
    assert seeded.available.plane_stack is True
    assert seeded.available.volume_field is False

    ctx = um3k_context.PageContext()
    before = ctx.available
    assert before.plane_stack is False
    assert before.volume_field is False

    loaded = _field_info(9)
    loaded[um3k_context.VOLUME_KEY] = object()
    ctx.dump = um3k_context.LoadedDump(
        info=loaded, planes=_field_planes(), record={"geometry": {}},
    )
    assert ctx.available is before, "replacing the dump recomputed by itself"
    assert ctx.available.plane_stack is False
    assert ctx.available.volume_field is False

    after = ctx.recompute_available()
    assert after is ctx.available
    assert after is not before
    assert after.plane_stack is True
    assert after.volume_field is True
    assert after.port_planes is True
    assert after.record is True
    assert before.plane_stack is False, "the retired snapshot moved with the page"
    assert before.volume_field is False, "the retired snapshot moved with the page"


def test_set_view_mode_accepts_both_modes():
    """If this fails, a legal view cannot be selected, or the stored one lags.

    The label branches on the exact string ``"port"`` and draws the volume
    otherwise (poc_app.py:3242, :3257), so both members of ``VIEW_MODES`` must
    round-trip through the setter and be what ``view_mode`` then holds.
    """
    ctx = um3k_context.PageContext()
    assert ctx.set_view_mode("port") == "port"
    assert ctx.view_mode == "port"
    assert ctx.set_view_mode("volume") == "volume"
    assert ctx.view_mode == "volume"

    assert um3k_context.PageContext(view_mode="port").view_mode == "port"
    assert um3k_context.PageContext(view_mode="volume").view_mode == "volume"
    assert tuple(um3k_context.VIEW_MODES) == ("port", "volume")


def test_set_view_mode_refuses_a_misspelling():
    """If this fails, a typo'd view mode is stored and only blows up at draw time.

    The message must name the offending string and both legal ones, and the
    refused value must not land: a page whose mode says ``"volum"`` would draw
    the volume while claiming a view that does not exist.
    """
    ctx = um3k_context.PageContext()
    with pytest.raises(ValueError) as excinfo:
        ctx.set_view_mode("volum")
    message = str(excinfo.value)
    assert "'volum'" in message
    assert "'port'" in message
    assert "'volume'" in message
    assert ctx.view_mode == "volume"

    with pytest.raises(ValueError):
        um3k_context.PageContext(view_mode="")

    with pytest.raises(ValueError):
        um3k_context.PageContext(view_mode="Port")


def test_from_any_dump_preserves_the_page_order():
    """If this fails, two page fields were swapped and the page reads garbage.

    ``reload_page`` hands its seven values over in one order (poc_app.py:5365-
    5375). A distinct value per field, in that order, proves position-for-field
    placement: any transposition mismatches at least one ``getattr``.
    """
    marks = {name: f"<{name} sentinel>" for name in um3k_context.PAGE_FIELDS}
    page = tuple(marks[name] for name in um3k_context.PAGE_FIELDS)

    positional = um3k_context.LoadedDump.from_any_dump(page)
    for name in um3k_context.PAGE_FIELDS:
        assert getattr(positional, name) == marks[name], f"{name} landed elsewhere"

    # The same seven as the mapping reload_page actually returns.
    by_key = um3k_context.LoadedDump.from_any_dump(dict(marks))
    for name in um3k_context.PAGE_FIELDS:
        assert getattr(by_key, name) == marks[name], f"{name} landed elsewhere"

    # A mapping that is missing a key reads as None rather than as a guess.
    sparse = um3k_context.LoadedDump.from_any_dump({"path": "x.npz"})
    assert sparse.path == "x.npz"
    assert sparse.info is None
    assert sparse.planes is None
    assert sparse.multifreq is None
    assert sparse.structure_id is None
    assert sparse.record is None
    assert sparse.is_vis is None


def test_from_any_dump_refuses_a_page_of_the_wrong_length():
    """If this fails, a short page is silently padded with Nones and misread.

    A six- or eight-element page is not a ``reload_page`` page: the mismatch has
    to be refused where it is made, with a message naming both counts and the
    order it expected.
    """
    expected = len(um3k_context.PAGE_FIELDS)

    with pytest.raises(ValueError) as short:
        um3k_context.LoadedDump.from_any_dump(tuple(range(expected - 1)))
    message = str(short.value)
    assert str(expected) in message
    assert str(expected - 1) in message

    with pytest.raises(ValueError):
        um3k_context.LoadedDump.from_any_dump(tuple(range(expected + 1)))

    with pytest.raises(ValueError):
        um3k_context.LoadedDump.from_any_dump(())


def test_callbacks_and_handles_round_trip():
    """If this fails, a draw path cannot find what it registered.

    Raising is the reason ``callback``/``handle`` exist instead of a bare dict
    lookup: a missing name must say so, and name what IS stored, at the point
    of the lookup rather than as an unrelated "NoneType is not callable" later.
    """
    ctx = um3k_context.PageContext()

    def play():
        return "playing"

    actor = object()
    ctx.register("play_pause", play)
    ctx.register_handle("volume_actor", actor)

    assert ctx.callback("play_pause") is play
    assert ctx.handle("volume_actor") is actor
    assert ctx.callback("play_pause")() == "playing"
    assert ctx.callbacks == {"play_pause": play}
    assert ctx.handles == {"volume_actor": actor}

    with pytest.raises(KeyError) as missing_callback:
        ctx.callback("stop")
    assert "stop" in str(missing_callback.value)
    assert "play_pause" in str(missing_callback.value)

    with pytest.raises(KeyError) as missing_handle:
        ctx.handle("nothing")
    assert "nothing" in str(missing_handle.value)


def test_available_of_an_empty_page_never_raises():
    """If this fails, a page with no dump becomes a traceback instead of a page.

    A deleted or unreadable dump still has to render as "nothing available":
    every flag false, and a non-dict / non-array value where the loader would
    have put one is treated as absent rather than indexed.
    """
    empty = um3k_context.Available.compute()
    assert (
        empty.volume_field, empty.plane_stack, empty.port_planes, empty.multifreq,
        empty.record, empty.s11_record, empty.animation,
    ) == (False,) * 7
    assert empty.source_format == "field"
    assert empty == um3k_context.Available.compute({}, {})
    assert empty == um3k_context.Available()

    assert um3k_context.Available.compute(None, None, None, None, None) == empty
    # Not every info dict carries the plane stack, and a shape-less value is not one.
    assert um3k_context.Available.compute({um3k_context.PLANE_KEY: 5}).port_planes is False
    shapeless = um3k_context.Available.compute({um3k_context.PLANE_KEY: _Stack(0)})
    assert shapeless.port_planes is False
    assert shapeless.plane_stack is False
    assert shapeless.volume_field is False


def test_volume_field_and_plane_stack_are_independent():
    """If this fails, the volume flag was derived from the station count again.

    ``volume_field`` is a question about the KEYS the page carries - ``e_centres``
    (poc_app.py:85) or ``e_raw`` (:91), the two ``_volume_quiver_mesh`` tests
    before it draws anything (:6737-6790) - while ``plane_stack`` is a question
    about how many x-planes were captured (:3280-3281). A one-station dump CAN
    carry a volume and a nine-station one can carry none, so the flags must move
    independently. ``volume_3d`` must also be gone: a half-done rename would
    leave a stale alias answering the old, wrong question.
    """
    assert not hasattr(um3k_context.Available, "volume_3d")
    assert not hasattr(um3k_context.Available(), "volume_3d")

    one_station = _field_info(n_st=1)
    stacked_stations = _field_info(n_st=9)
    cell_centred = dict(one_station, **{um3k_context.VOLUME_KEY: object()})
    staggered = dict(one_station, **{um3k_context.VOLUME_RAW_KEY: {"e": object()}})
    both = dict(stacked_stations, **{um3k_context.VOLUME_KEY: object()})
    both[um3k_context.VOLUME_RAW_KEY] = {"e": object()}

    volume_one_station = um3k_context.Available.compute(info=cell_centred)
    assert volume_one_station.volume_field is True
    assert volume_one_station.plane_stack is False
    assert volume_one_station.port_planes is True

    raw_one_station = um3k_context.Available.compute(info=staggered)
    assert raw_one_station.volume_field is True
    assert raw_one_station.plane_stack is False

    stack_no_volume = um3k_context.Available.compute(info=stacked_stations)
    assert stack_no_volume.volume_field is False
    assert stack_no_volume.plane_stack is True
    assert stack_no_volume.port_planes is True

    both_page = um3k_context.Available.compute(info=both)
    assert both_page.volume_field is True
    assert both_page.plane_stack is True

    plain = um3k_context.Available.compute(info=one_station)
    assert plain.volume_field is False
    assert plain.plane_stack is False
    assert plain.port_planes is True


def test_name_literals_are_pinned_against_poc_app():
    """If this fails, a copied key name drifted and the page reads nothing.

    The literals are copies on purpose (the module must import with no UI stack,
    and poc_app is a 441 KB UI module), so poc_app is imported HERE, inside the
    test, and each copy is compared against the authority it was copied from.
    ``_is_vis``, ``_view_label`` and ``_plane_layout`` are used where the name
    lives as behaviour rather than as a constant.
    """
    import poc_app  # noqa: E402 - imported here so the module under test stays clean

    assert um3k_context.PLANE_KEY == poc_app.PLANE_KEY
    assert um3k_context.VOLUME_KEY == poc_app.VOLUME_KEY
    assert um3k_context.VOLUME_RAW_KEY == poc_app.VOLUME_RAW_KEY
    assert um3k_context.PAGE_FIELDS[:len(poc_app.PAGE_KEYS)] == poc_app.PAGE_KEYS

    # The animation format is whatever _is_vis compares against (poc_app.py:338).
    assert poc_app._is_vis({"format": um3k_context.VIS_FORMAT}) is True
    assert poc_app._is_vis({}) is False
    assert poc_app._is_vis({um3k_context.VIS_FORMAT: True}) is False

    # The label branches on these two strings and on the FALLBACK provenance.
    planes = {
        "slice_index": 0, "n_st": 3, "stations_mm": [0.0, 1.0, 2.0],
        "src_s11": um3k_context.FALLBACK_SRC,
    }
    port_label = poc_app._view_label(um3k_context.VIEW_MODES[0], planes, True)
    volume_label = poc_app._view_label(um3k_context.VIEW_MODES[1], planes, True)
    assert port_label.startswith("port-plane")
    assert volume_label.startswith("|Ez| volume")
    assert "FALLBACK" in port_label
    assert "FALLBACK" not in poc_app._view_label(
        um3k_context.VIEW_MODES[0], dict(planes, src_s11="geometry.ix_port"), True,
    )

    # ... and the layout writes FALLBACK_SRC itself (poc_app.py:3123).
    layout = poc_app._plane_layout({um3k_context.PLANE_KEY: _Stack(3), "cell_m": 1e-4}, None)
    assert layout["src_s11"] == um3k_context.FALLBACK_SRC
    assert layout["src_load"] == um3k_context.FALLBACK_SRC
    assert set(layout) == {
        "cell_mm", "n_st", "stations_mm", "x_load_mm", "src_load", "ix_load",
        "x_s11_mm", "src_s11", "x_s21_mm", "src_s21", "s21_valid",
        "s21_valid_src", "s21_reason", "slice_index",
    }

    # The page's default view is the one the boot assignment states
    # (poc_app.py:4091); pinning the source line keeps the copy honest.
    source = Path(poc_app.__file__).read_text(encoding="utf-8")
    assert f'view_mode = "{um3k_context.DEFAULT_VIEW_MODE}"' in source
    assert um3k_context.DEFAULT_VIEW_MODE in um3k_context.VIEW_MODES
