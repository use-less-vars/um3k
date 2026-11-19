"""The board page: the board drawn with no field dump, from record or builder.

``server/poc_app.py`` gained ``_bare_board_page`` so a structure whose field
DEFAULT_STRUCTURE/fixture is not on disk can still show the board the study
solved on.  The numbers come from the study record when that record carries a
mesh, and from the BUILDER that defines the default cross-section
(``emfit.studies.microstrip_reference_board`` turned into a mesh by its own
``to_cell_counts``) when it does not - never from a constant written into the
viewer.  These tests pin both halves of that promise:

* the page's numbers come from the record, in the record's own units, and
  anything the record did not carry arrives as NaN (so the draw sites leave
  that part absent instead of drawing a board nobody measured) - and a record
  that resolves no mesh falls back to the builder's board rather than to none;
* a page built from it actually DRAWS the board - and still has no field,
  no volume layer, no cut sheet and no timeline.  That holds for the plain
  no-data boot as well, because a page with no data at all IS the builder's
  board: there is no flag to ask for it.

The boot recipe is NOT re-invented here: ``_boot``'s no-event-loop dance, the
headless ``_render_doubled`` and the ``_live`` page introspection are taken from
``tests/test_animation_volume.py``, which is where the recipe is documented.
"""

from __future__ import annotations

import contextlib
import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server"), str(REPO_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip("pyvista", reason="the board is drawn with pyvista")
pytest.importorskip("trame.app", reason="trame serves the page")
pytest.importorskip("trame.ui.vuetify3", reason="run_web_vis builds this UI")

import poc_app as app  # noqa: E402  (after the importorskip guards)
import trame_server.core as trame_server  # noqa: E402  (where Server.start lives)

#: The established recipe, reused rather than re-written.
import test_animation_volume as av  # noqa: E402

assert av.app is app, (
    "tests/test_animation_volume.py imported a different poc_app; the recipe "
    "below would boot the wrong module"
)

#: A study record in the shape ``_geom_mm`` reads: ``geometry`` is in METRES,
#: the port is a CELL INDEX and a load may give a column instead of an x.
RECORD = {
    "geometry": {
        "cell": 0.4e-3,
        "h": 1.6e-3,
        "w": 3.2e-3,
        "ix_port": 8,
        "loads": [{"column": 50}],
        "grid": [72, 212, 22],
    }
}

#: Every wire the board is made of, by the name the draw sites give it.
BOARD_ACTORS = ("ground_plane", "substrate", "strip_feed", "port_source", "port_load")


def _page(tmp_path: Path, record: dict = RECORD) -> dict:
    """The bare page for ``record``, written where ``load_record`` finds it."""
    path = tmp_path / "study_record.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return app._bare_board_page(record_path=path, structure_id="probe")


def _boot(info: dict, page: dict | None = None):
    """``run_web_vis`` up to the point it would block in ``server.start``.

    The body is ``tests/test_animation_volume.py::_boot`` with the dump loading
    taken out: this page is handed its ``info`` instead of a file.
    """
    stopped: list = []

    def _no_start(*_a, **_k):
        stopped.append(True)
        raise av._Stop()

    srv = av.trame_app.get_server()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(trame_server.Server, "start", _no_start)
        for holder in av._foreign_get_server_holders():
            patch.setattr(holder, "get_server", av.PRISTINE_GET_SERVER)
        patch.setattr(srv, "start", _no_start)
        kwargs = {} if page is None else {"loaded_page": page}
        with contextlib.suppress(av._Stop):
            app.run_web_vis(info, "127.0.0.1", 8999, fps=av.FPS, **kwargs)

    assert stopped, (
        "run_web_vis returned before server.start(): it bailed out early, so no "
        "board was drawn and these assertions would read an empty page"
    )
    return av._live(srv)


@pytest.fixture(scope="module")
def bare_live(tmp_path_factory):
    """One boot of the bare page: three tests read this same page."""
    page = _page(tmp_path_factory.mktemp("bare_board"))
    with av._render_doubled():
        yield _boot(page["info"], page)


def test_the_page_numbers_are_the_records_and_unknowns_are_nan(tmp_path):
    page = _page(tmp_path)
    info = page["info"]

    # The record's metres become millimetres; the port and load positions are
    # derived from the cell size exactly as the viewer derives them elsewhere.
    assert info["cell_m"] == pytest.approx(0.4e-3)  # 0.4 mm
    assert (info["nx"], info["ny"], info["nz"]) == (72.0, 212.0, 22.0)
    assert info["substrate_h_mm"] == pytest.approx(1.6)
    assert info["strip_w_mm"] == pytest.approx(3.2)
    assert info["port_x_mm"] == pytest.approx(3.2)  # ix_port 8 x 0.4 mm
    assert info["load_x_mm"] == pytest.approx(20.0)  # column 50 x 0.4 mm
    # The near cut plane is a viewer choice, not a recorded one.
    assert math.isnan(info["xcut_near_mm"])

    # A page with no dump claims no dump: no path key, and none of the field,
    # plane or timeline plumbing a dump-backed page carries.
    assert "path" not in info
    assert page["path"] is None
    assert page["planes"] is None
    assert page["multifreq"] is None
    assert page["is_vis"] is False
    assert page["structure_id"] == "probe"

    # A record that resolves NO mesh does not leave the page blank: the numbers
    # then come from the BUILDER, so these are emfit's, not the viewer's.  62
    # cells over a 24.8 mm line at the 0.4 mm cell the fit picks, 44 across the
    # 17.6 mm width, and z from the study's own layer counts - a change in the
    # builder moves this test instead of silently redrawing a different board.
    fallback = app._bare_board_page(
        structure={"id": "nothing"}, structure_id="nothing"
    )
    built = fallback["info"]
    assert fallback["record"] is None
    assert fallback["structure_id"] == "nothing"
    assert built["cell_m"] == pytest.approx(0.4e-3)
    assert (built["nx"], built["ny"], built["nz"]) == (62, 44, 22)
    assert built["substrate_h_mm"] == pytest.approx(1.6)
    assert built["strip_w_mm"] == pytest.approx(3.2)
    assert built["port_x_mm"] == pytest.approx(3.2)
    # The reference board declares NO load, so that plane is genuinely unknown
    # and stays NaN: the one number the fallback must not invent.
    assert math.isnan(built["load_x_mm"])
    # The near cut is the port plane (the strip is one run to the far wall) and
    # the node axis stops one cell short of the 24.8 mm box, as a dump's does.
    assert built["xcut_near_mm"] == pytest.approx(3.2)
    assert len(built["x_mm"]) == 62
    assert built["x_mm"][-1] == pytest.approx(24.4)
    assert "path" not in built
    assert fallback["path"] is None
    assert fallback["is_vis"] is False


def test_a_no_data_page_draws_the_board(bare_live):
    actors = set(bare_live.plotter.actors)
    missing = [name for name in BOARD_ACTORS if name not in actors]
    assert not missing, f"{missing} were not drawn; actors: {sorted(actors)}"
    # `add_point_labels(name="port_labels")` lands as a child actor, so the
    # source/load labels are checked under that name.
    assert "port_labels-labels" in actors, sorted(actors)


def test_a_bare_page_carries_no_field_volume_or_cut_sheet(bare_live):
    actors = sorted(bare_live.plotter.actors)
    # The title text, the five wires and the label block - nothing else.
    assert len(actors) == 7, actors
    # NB "plane" is not in this list: the board's own ground_plane carries it.
    for banned in ("volume", "field", "cut", "slice", "ez_"):
        assert not [a for a in actors if banned in a.lower()], actors
    assert "volume_layer" not in bare_live.handles, sorted(bare_live.handles)
    assert bare_live.handles.get("far_field") is not None
    assert bare_live.state.frame_max is None, (
        "a bare page claims no timeline"
    )


def test_the_camera_is_framed_once_for_the_board(bare_live):
    assert bare_live.handles["camera_framed_for"] == ()
    assert bare_live.plotter._poc_camera_framed is True


def test_a_plain_no_data_boot_draws_the_board_from_the_builder():
    """No info at all draws the builder's board instead of an empty column.

    ``run_web_vis({})`` used to draw nothing: a page with no cell size has no
    board to draw.  It now falls through to the builder's board, so the plain
    no-data boot is the seam under test here - if it is lost, the viewer opens
    with an empty centre column again and this is the test that says so.
    """
    with av._render_doubled():
        live = _boot({})
    actors = set(live.plotter.actors)
    for name in ("ground_plane", "substrate", "strip_stub", "port_source"):
        assert name in actors, (
            f"{name} was not drawn from the builder's board: {sorted(actors)}"
        )
    assert "port_labels-labels" in actors, sorted(actors)
    # The reference board declares NO load, so there is no load plane to open a
    # gap at: the strip is ONE run from the port to the far wall (strip_stub)
    # and there is no Load wire.  A feed segment or a load wire here would mean
    # the builder's "no loads" was lost and a load was invented.
    assert "strip_feed" not in actors, (
        f"a feed segment was drawn on a board that declares no load: {sorted(actors)}"
    )
    assert "port_load" not in actors, (
        f"a Load wire was drawn on a board that declares no load: {sorted(actors)}"
    )


def test_main_serves_the_board_page_for_a_record_only_structure(capsys, monkeypatch):
    """A record-only entry opens its BOARD page, with no flag to ask for it.

    The entry has its S-parameters recorded but no field dump, so no field can
    be shown - it opens the board the study solved on (the builder's here, since
    its own record resolves no mesh), never another structure's field data, and
    the ``--bare-board`` flag that used to be the only way in is gone.
    """
    calls: list = []

    def _recorder(info, host, port, fps, structure=None, structures=None, **kwargs):
        calls.append((info, host, port, fps, structure, structures, kwargs))
        return 0

    monkeypatch.setattr(app, "run_web_vis", _recorder)

    assert app.main(["--structure", "build_A_50ohm_100ohm"]) == 0
    assert len(calls) == 1, f"the shell was not opened exactly once: {calls}"
    info, _host, _port, _fps, structure, _structures, kwargs = calls[0]

    assert app._finite(info.get("cell_m")) is not None, (
        f"the board page carries no scale, so nothing can be drawn: {info}"
    )
    assert info["cell_m"] == pytest.approx(0.4e-3)
    assert info["nx"] == 62
    page = kwargs["loaded_page"]
    assert page["record"] is None, "a record-only entry's page claims a record"
    assert page["is_vis"] is False, "a board page claims no field"
    assert page["structure_id"] == "build_A_50ohm_100ohm"
    assert structure is not None and structure.get("id") == "build_A_50ohm_100ohm"

    # The flag is GONE, not merely redundant: an unknown option is a usage error.
    with pytest.raises(SystemExit) as gone:
        app.main(["--bare-board"])
    assert gone.value.code == 2

    # The dump-READING exits still refuse: there is no dump to report on, and
    # the refusal says which entries can be opened instead.
    with pytest.raises(SystemExit) as refused:
        app.main(["--structure", "build_A_50ohm_100ohm", "--list-keys"])
    assert refused.value.code == 2
    assert "record only" in capsys.readouterr().err


#: The shipped legacy dump: nine captured x-planes and NO |E| volume, so the cut
#: sheets a page booted from it draws are the ones it builds from ``plane_ez``.
LEGACY_NPZ = (
    REPO_ROOT
    / "evidence"
    / "termination"
    / "build_A_50ohm_p51_ghostwave_fields.npz"
)

#: ``_marker_cut_lines``'s sentence for "the sheets are not drawn".  The sheets
#: are NOT the |E| volume layer's, so a page that draws none and blames that
#: layer is the regression this test exists for.
LAYER_OFF_SENTENCE = "cut sheets: not drawn - the |E| volume layer is off"


def test_a_plane_stack_page_draws_its_cut_sheets_with_the_layer_off(monkeypatch):
    """The two cut sheets are the page's field, not the |E| layer's.

    This module is the only boot recipe in the tree that does NOT switch the |E|
    layer on (``tests/test_poc_volume_view.py`` and
    ``tests/test_animation_volume.py`` both patch ``SHOW_VOLUME_LAYER_DEFAULT``
    True), which makes it the only place the layer-OFF page can be read.  The
    page is booted from the shipped dump, which carries ``plane_ez`` and no
    volume, so the sheets come off the plane stack: with the layer off they used
    to be gated away with it and the corner legend said so.  What is recorded is
    what the boot really did - the datasets it handed ``add_mesh`` and the
    legend text it wrote - not a re-derivation of the layout.
    """
    if not LEGACY_NPZ.is_file():
        pytest.skip(f"the shipped field dump is absent: {LEGACY_NPZ}")
    import pyvista

    assert app.SHOW_VOLUME_LAYER_DEFAULT is False, (
        "this test reads the layer-OFF page, but the default layer is "
        f"{app.SHOW_VOLUME_LAYER_DEFAULT!r}"
    )
    assert app._volume_layer_enabled() is False, (
        "POC_SHOW_VOLUME is set, so this boot is not the layer-OFF page"
    )

    info = app.load_dump(LEGACY_NPZ)
    assert app.PLANE_KEY in info, (
        f"the shipped dump no longer carries {app.PLANE_KEY}, so this is not the "
        "plane-stack page the cut sheets are drawn on"
    )
    assert app.VOLUME_RAW_KEY not in info, (
        f"the dump now carries {app.VOLUME_RAW_KEY}: this test pins the "
        "volume-less page, whose sheets come off the plane stack"
    )

    real_add_mesh = pyvista.Plotter.add_mesh
    added: list = []

    def _counted_add_mesh(self, dataset, *args, **kwargs):
        added.append((dataset, kwargs))
        return real_add_mesh(self, dataset, *args, **kwargs)

    real_marker_text = app._marker_text
    legends: list = []

    def _spy_marker_text(*args, **kwargs):
        text = real_marker_text(*args, **kwargs)
        legends.append(text)
        return text

    monkeypatch.setattr(pyvista.Plotter, "add_mesh", _counted_add_mesh)
    monkeypatch.setattr(app, "_marker_text", _spy_marker_text)
    with av._render_doubled():
        _boot(info)

    # The two sheets, by the samples they carry: one row in y (the y cut) and one
    # column in z (the z cut), each 9 stations deep and painted on the plane
    # stack's own ``ez_abs`` (this dump has no ``e_abs`` to paint them with).
    sheets = sorted(
        (*tuple(int(n) for n in shot.dimensions), kwargs.get("scalars"))
        for shot, kwargs in added
        if kwargs.get("scalars") in ("ez_abs", "e_abs")
    )
    assert sheets == [(9, 1, 22, "ez_abs"), (9, 213, 1, "ez_abs")], (
        "the layer-OFF page did not draw both cut sheets off the plane stack: "
        f"{sheets}"
    )

    # And the legend claims them: no draw may tell the operator the sheets are
    # missing, and the last one must place a marker ON a drawn cut.  The marker
    # that is ON is the page's own answer for this dump (its load plane falls in
    # the slab the sheets span), so the sentence is matched by its relation
    # rather than by a name: any marker named "off both cuts" here would mean the
    # legend is describing sheets that are not on screen.
    assert legends, "the boot wrote no corner legend, so these assertions read nothing"
    for text in legends:
        assert LAYER_OFF_SENTENCE not in str(text), (
            "the page drew its cut sheets and still says they are missing: "
            f"{text!r}"
        )
    legend = str(legends[-1])
    assert "marker is on the y cut" in legend, (
        f"the closing legend places no marker on the drawn cuts: {legend!r}"
    )

