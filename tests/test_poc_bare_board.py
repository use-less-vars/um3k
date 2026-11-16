"""The bare-board page: the board drawn from a study record with no field dump.

``server/poc_app.py`` gained ``_bare_board_page`` so a structure whose field
DEFAULT_STRUCTURE/fixture is not on disk can still show the board the study
solved on.  These tests pin the two halves of that promise:

* the page's numbers come from the record, in the record's own units, and
  anything the record did not carry arrives as NaN (so the draw sites leave
  that part absent instead of drawing a board nobody measured);
* a page built from it actually DRAWS the board - and still has no field,
  no volume layer, no cut sheet and no timeline.

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

    # A record that does not resolve leaves EVERY number NaN - never a
    # fabricated constant, which would put the board at a scale nobody measured.
    empty = app._bare_board_page(structure={"id": "nothing"}, structure_id="nothing")
    assert empty["record"] is None
    for key in (
        "cell_m",
        "nx",
        "ny",
        "nz",
        "substrate_h_mm",
        "strip_w_mm",
        "port_x_mm",
        "load_x_mm",
        "xcut_near_mm",
    ):
        assert math.isnan(empty["info"][key]), f"{key} was invented: {empty['info']}"


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
    assert bare_live.handles["camera_framed"] is True
    assert bare_live.plotter._poc_camera_framed is True


def test_a_plain_no_data_boot_still_draws_no_board(tmp_path):
    """KNOWN GAP, asserted so it cannot drift silently.

    The board appears only when the page is handed ``--bare-board``'s info.
    ``run_web_vis({})`` no longer RAISES (its NaN guards hold), but it draws
    nothing: no structure, no board.  If someone wires the bare page into the
    plain no-data path without the flag, this test is the one that says so.
    """
    with av._render_doubled():
        live = _boot({})
    drawn = set(BOARD_ACTORS) & set(live.plotter.actors)
    assert not drawn, f"the plain no-data path now draws {sorted(drawn)}; the " \
                      "flag may be removable - update this test and main()"


def test_main_refuses_a_record_only_structure_unless_the_flag_is_given(capsys):
    # A record-only entry has its S-parameters but not its field dump, so the
    # case cannot open: refused, never substituted.
    with pytest.raises(SystemExit) as refused:
        app.main(["--structure", "build_A_50ohm_100ohm"])
    assert refused.value.code == 2
    assert "build_A_50ohm_100ohm" in capsys.readouterr().err

    # --bare-board reads no dump, so it is the one way through - but asking for
    # a page and for a dump report at the same time is a usage error.
    with pytest.raises(SystemExit) as clash:
        app.main(["--structure", "build_A_50ohm", "--bare-board", "--list-keys"])
    assert clash.value.code == 2
    assert "cannot be combined" in capsys.readouterr().err
