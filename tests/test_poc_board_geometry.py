"""The board the field sits on: millimetres, provenance, and where it is drawn.

Claims pinned by this file, one per test group:

1. ``_geom_mm`` resolves the board profile in MILLIMETRES from one documented
   order - the ``info`` dict (which carries millimetres already, because the
   loader writes them there), then the record's ``geometry`` block (which
   carries METRES, the study's SI units, and is scaled by 1e3), then the x
   positions that are *derived* rather than recorded: the port from
   ``ix_port x cell`` and the load from ``loads[0]``. It names the source of
   every number it returns, so a page can say where a millimetre came from.
2. Nothing is invented: a number that no source carries comes back ``None``
   with source ``"absent"`` - never 0.0 - and the resolver never raises, not on
   a ``None`` record, not on a string ``geometry`` block, not on a cell size
   that is not a number.
3. ``_vis_geometry`` draws the board the RECORD describes even when every
   millimetre in ``info`` is NaN. That is the regression this file exists for:
   the board used to go missing on a dump whose info carries the geometry as
   NaN placeholders rather than as numbers.
4. The drawn actors are the ones the numbers ask for - ground plane, board box,
   the feed strip from the port to the load, the stub from the near S21 cut to
   the end of the line, one wire per port - and the strip LEAVES A GAP around
   the load, so the two segments never paint over the termination.
5. A missing number costs exactly the actor that needed it: with the near cut
   unknown the stub is gone and the board, the feed and both wires stay; with
   no number known at all only the ground plane is drawn and ONE stderr line
   names the five keys and their sources. A drawn board prints nothing.
6. ``_add_markers`` sizes its two discs from the FIELD grid - ``(shape - 1) *
   cell`` about the y/z mid-plane - not from the board.  ``(shape - 1) * cell``
   and not ``shape * cell`` because the grid places its samples at ``i * cell``
   (i in 0..n-1), so n samples span n - 1 cells: the 213 y samples span 212
   cells and the 22 z samples span 21, and a disc one cell wider at each end
   would overhang the volume it is a cross-section of.
7. ``_draw_scene`` draws the board UNDER the markers and after the axes, and
   hands both layers the same ``info`` and the same ``planes``.
8. The near cut's provenance is the route ``_plane_layout`` ACTUALLY took: when
   no S21 plane was recorded the label says so instead of repeating the
   recorded-plane key, because that string is what ``_vis_geometry`` prints in
   the one diagnostic line that tells a measured x from a substituted one.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import poc_app  # noqa: E402
import um3k_context  # noqa: E402 - the named FALLBACK provenance constant

# --- the shipped numbers ---------------------------------------------------
#
# The grid cell and the field shape of the shipped Build A dump: the board
# spans nx*cell by ny*cell, the marker discs (n - 1)*cell.
CELL_M = 0.0004
CELL_MM = CELL_M * 1e3
NX, NY, NZ = 62, 212, 22
N_ST = 9  # captured stations in the shipped dump

# The record's geometry block is METRES (the study writes SI). These are the
# shipped Build A values; the millimetres they resolve to are spelled below.
GEOMETRY_M = {
    "cell": 0.0004,
    "h": 0.0016,
    "w": 0.0032,
    "length": 0.0248,
    "width": 0.0848,
    "height": 0.0088,
    "ix_port": 8,
    "j_centre": 106,
    "k_strip": 4,
    "n_pml": 6,
}

SUBSTRATE_MM = 1.6  # geometry.h     1.6 mm  -> 1.6e-3 m
STRIP_MM = 3.2  # geometry.w     3.2 mm  -> 3.2e-3 m
PORT_MM = 3.2  # ix_port 8 x 0.4 mm
LOAD_MM = 20.0  # loads[0].x     20.0 mm -> 20.0e-3 m
XCUT_MM = 20.4  # s21_plane.x_m  20.4 mm -> 20.4e-3 m
X_SPAN_MM = NX * CELL_MM  # 24.8
Y_SPAN_MM = NY * CELL_MM  # 84.8
LINE_END_MM = (NX - 1) * CELL_MM  # 24.4: the dump's x axis stops one cell in
EPS_MM = 0.001 * SUBSTRATE_MM  # the lift the board and its wires share


# --- helpers ---------------------------------------------------------------


def _record(loads=None, **overrides) -> dict:
    """The shipped Build A record, trimmed to the fields the resolver reads.

    ``loads`` is nested INSIDE the ``geometry`` block, because that is where
    ``_geom_mm`` reads it from (``geom.get("loads")``); a top-level copy is not
    a source at all. It is given here rather than in ``GEOMETRY_M`` so a test
    can replace it without rebuilding the block.
    """
    geometry = dict(GEOMETRY_M)
    geometry["loads"] = [{"x": 0.020, "column": 50}] if loads is None else loads
    record = {
        "geometry": geometry,
        "grid": [NX, NY, NZ],
        "s21_plane": {"x_m": 0.0204},
    }
    record.update(overrides)
    return record


#: The nine keys ``_geom_mm`` always returns, in the order it fills them.
GEOM_KEYS = (
    "cell_mm",
    "substrate_h_mm",
    "strip_w_mm",
    "port_x_mm",
    "load_x_mm",
    "xcut_near_mm",
    "length_mm",
    "width_mm",
    "height_mm",
)

#: The ``geometry_mm`` block, in millimetres, as ``_plane_layout`` attaches it.
_GEOM_MM = {
    "cell_mm": CELL_MM,
    "substrate_h_mm": SUBSTRATE_MM,
    "strip_w_mm": STRIP_MM,
    "port_x_mm": PORT_MM,
    "load_x_mm": LOAD_MM,
    "xcut_near_mm": XCUT_MM,
    "length_mm": 24.8,
    "width_mm": 84.8,
    "height_mm": 8.8,
}


def _geom_block(absent=(), **overrides) -> dict:
    """A ``geometry_mm`` block with its ``src`` map; ``absent`` keys are None.

    ``_plane_layout`` builds this dict from ``_geom_mm``; the shape of the
    ``src`` map (one entry per key) is what the stderr line reads, so a hand
    built block keeps the same two-level shape.
    """
    block = dict(_GEOM_MM)
    block.update(overrides)
    for key in absent:
        block[key] = None
    block["src"] = {key: ("absent" if key in absent else f"geom.{key}") for key in GEOM_KEYS}
    return block


def _mm_info(**overrides) -> dict:
    """An ``info`` that carries the profile in millimetres, as the loader does."""
    info = {
        "cell_m": CELL_M,
        "nx": NX,
        "ny": NY,
        "nz": NZ,
        "nstep": 0,
        "x_mm": np.arange(NX) * CELL_MM,
        "substrate_h_mm": SUBSTRATE_MM,
        "strip_w_mm": STRIP_MM,
        "port_x_mm": PORT_MM,
        "load_x_mm": LOAD_MM,
        "xcut_near_mm": XCUT_MM,
    }
    info.update(overrides)
    return info


def _nan_info(**overrides) -> dict:
    """The ``info`` the vis page really gets: NaN placeholders, not numbers.

    This is the profile the missing board was found on - every geometry key is
    a NaN FLOAT rather than absent, so a resolver that only checks ``is not
    None`` would believe it.
    """
    info = {
        "cell_m": CELL_M,
        "nx": NX,
        "ny": NY,
        "nz": NZ,
        "nstep": 0,
        "x_mm": np.arange(NX) * CELL_MM,
    }
    for key in ("substrate_h_mm", "strip_w_mm", "port_x_mm", "load_x_mm", "xcut_near_mm"):
        info[key] = float("nan")
    info.update(overrides)
    return info


def _planes(geometry=True, **overrides) -> dict:
    """The ``planes`` dict as ``_plane_layout`` hands it over.

    The key set follows tests/test_poc_volume_arrows.py::_planes, extended with
    the ``geometry_mm`` block that ``_vis_geometry`` reads (and that the older
    stub predates).
    """
    stations = [10.4 + 1.2 * i for i in range(N_ST)]
    planes = {
        "cell_mm": CELL_MM,
        "n_st": N_ST,
        "stations_mm": stations,
        "x_load_mm": LOAD_MM,
        "src_load": "record",
        "ix_load": 50,
        "x_s11_mm": PORT_MM,
        "src_s11": "record",
        "x_s21_mm": XCUT_MM,
        "src_s21": "record",
        "s21_valid": True,
        "s21_valid_src": "record",
        "s21_reason": "",
        "slice_index": 0,
    }
    if geometry:
        planes["geometry_mm"] = _geom_block()
        planes["geometry_src"] = planes["geometry_mm"]["src"]
    planes.update(overrides)
    return planes


class _Plotter:
    """Records what the board layer asks for; draws nothing.

    Copied from the ``_StubPlotter`` in tests/test_poc_volume_arrows.py, with
    the meshes kept (name, mesh, kwargs) so a test can measure the geometry
    that was handed to pyvista rather than spy on pyvista itself.
    """

    def __init__(self):
        self.meshes = []
        self.labels = []
        self.axes = []

    def add_mesh(self, mesh, **kwargs):
        self.meshes.append((kwargs.get("name"), mesh, kwargs))
        return object()

    def add_point_labels(self, points, labels, **kwargs):
        self.labels.append(([tuple(p) for p in points], list(labels), kwargs))
        return object()

    def add_axes(self, **kwargs):
        self.axes.append(kwargs)

    def add_text(self, text, **kwargs):
        return object()

    def names(self) -> list:
        return [name for name, _mesh, _kw in self.meshes]

    def mesh(self, name):
        for got, mesh, _kw in self.meshes:
            if got == name:
                return mesh
        raise AssertionError(f"no {name!r} actor; drawn: {self.names()}")


def _stripe(mesh):
    """(long-axis interval, short-axis span, z interval, short-axis centre).

    The board's strip segments are ``pv.Plane``s normal to z, so their bounds
    are the segment's own rectangle: the longer side is the strip's length and
    the shorter one its width. Reading them this way keeps the claim ("16.8 mm
    long, 3.2 mm wide, at 1.6 mm") independent of which in-plane axis pyvista
    happened to lay the longer side along.
    """
    x0, x1, y0, y1, z0, z1 = mesh.bounds
    if (x1 - x0) >= (y1 - y0):
        return (x0, x1), y1 - y0, (z0, z1), 0.5 * (y0 + y1)
    return (y0, y1), x1 - x0, (z0, z1), 0.5 * (x0 + x1)


# --- 1..9: _geom_mm --------------------------------------------------------


def test_geom_mm_takes_millimetres_from_info_as_they_are():
    """The ``info`` profile IS millimetres: reading it must not rescale it."""
    out = poc_app._geom_mm(_mm_info(), None)
    assert out["cell_mm"] == pytest.approx(CELL_MM)
    assert out["substrate_h_mm"] == pytest.approx(SUBSTRATE_MM)
    assert out["strip_w_mm"] == pytest.approx(STRIP_MM)
    assert out["port_x_mm"] == pytest.approx(PORT_MM)
    assert out["load_x_mm"] == pytest.approx(LOAD_MM)
    assert out["xcut_near_mm"] == pytest.approx(XCUT_MM)
    # The provenance names the info key verbatim, and the cell by its metres.
    src = out["src"]
    assert src["substrate_h_mm"] == "info.substrate_h_mm"
    assert src["strip_w_mm"] == "info.strip_w_mm"
    assert src["port_x_mm"] == "info.port_x_mm"
    assert src["load_x_mm"] == "info.load_x_mm"
    assert src["xcut_near_mm"] == "info.xcut_near_mm"
    assert src["cell_mm"] == "info.cell_m"


def test_geom_mm_scales_the_record_geometry_from_metres():
    """The record writes SI: 0.0016 m has to arrive as 1.6 mm, not 0.0016 mm."""
    out = poc_app._geom_mm({"cell_m": CELL_M}, _record())
    assert out["substrate_h_mm"] == pytest.approx(SUBSTRATE_MM)
    assert out["strip_w_mm"] == pytest.approx(STRIP_MM)
    assert out["length_mm"] == pytest.approx(24.8)
    assert out["width_mm"] == pytest.approx(84.8)
    assert out["height_mm"] == pytest.approx(8.8)
    assert out["src"]["substrate_h_mm"] == "geometry.h"
    assert out["src"]["strip_w_mm"] == "geometry.w"
    assert out["src"]["length_mm"] == "geometry.length"
    assert out["src"]["width_mm"] == "geometry.width"
    assert out["src"]["height_mm"] == "geometry.height"


def test_geom_mm_derives_the_port_from_ix_port_times_the_cell():
    """The port x is not recorded in mm: it is cell index 8 of a 0.4 mm grid."""
    out = poc_app._geom_mm({"cell_m": CELL_M}, _record())
    assert out["port_x_mm"] == pytest.approx(PORT_MM)
    assert out["src"]["port_x_mm"] == "geometry.ix_port*cell"
    # Without a cell there is no port x, and no guess is made for one.
    no_cell = {k: v for k, v in GEOMETRY_M.items() if k != "cell"}
    assert poc_app._geom_mm({}, _record(geometry=no_cell))["port_x_mm"] is None


def test_geom_mm_takes_the_load_from_the_first_loads_x():
    """The load's recorded METRE x wins over its cell column."""
    out = poc_app._geom_mm({"cell_m": CELL_M}, _record())
    assert out["load_x_mm"] == pytest.approx(LOAD_MM)
    assert out["src"]["load_x_mm"] == "geometry.loads[0].x"
    # The loads live INSIDE the geometry block: a top-level copy beside it is
    # not read, so a record that grows one does not move the load wire.
    stray = _record()
    stray["loads"] = [{"x": 0.5}]
    assert poc_app._geom_mm({}, stray)["load_x_mm"] == pytest.approx(LOAD_MM)


def test_geom_mm_falls_back_to_the_load_column_times_the_cell():
    """A load with no x still has a column, and column x cell is its position."""
    out = poc_app._geom_mm({"cell_m": CELL_M}, _record(loads=[{"column": 50}]))
    assert out["load_x_mm"] == pytest.approx(LOAD_MM)  # 50 x 0.4 mm
    assert out["src"]["load_x_mm"] == "geometry.loads[0].column*cell"


def test_geom_mm_takes_the_near_cut_from_the_x_s21_argument():
    """The near cut is passed IN; a record that carries an s21 plane is not it."""
    out = poc_app._geom_mm({}, _record(), x_s21_mm=XCUT_MM)
    assert out["xcut_near_mm"] == pytest.approx(XCUT_MM)
    assert out["src"]["xcut_near_mm"] == "s21_plane.x_m"
    # The record's own s21_plane is NOT a source for this number: a caller that
    # passes no plane gets None, not the record's 20.4 mm by accident.
    silent = poc_app._geom_mm({}, _record())
    assert silent["xcut_near_mm"] is None
    assert silent["src"]["xcut_near_mm"] == "absent"


def test_geom_mm_prefers_the_info_millimetres_over_the_record():
    """First finite source wins: the loader's number beats the study's."""
    out = poc_app._geom_mm(
        {"cell_m": CELL_M, "substrate_h_mm": 2.5}, _record()
    )
    assert out["substrate_h_mm"] == pytest.approx(2.5)
    assert out["src"]["substrate_h_mm"] == "info.substrate_h_mm"
    # ... and only that key: the rest still comes from the record.
    assert out["strip_w_mm"] == pytest.approx(STRIP_MM)
    assert out["src"]["strip_w_mm"] == "geometry.w"


def test_geom_mm_returns_none_not_zero_when_nothing_carries_the_number():
    """Absent is ``None`` with an ``"absent"`` source - never a plausible 0.0."""
    out = poc_app._geom_mm({}, None)
    for key in GEOM_KEYS:
        assert out[key] is None, f"{key} was invented as {out[key]!r}"
        assert out["src"][key] == "absent"
    assert set(out) == set(GEOM_KEYS) | {"src"}


def test_geom_mm_never_raises_on_junk_input():
    """A resolver on the page's hot path costs nothing when its input is junk."""
    cases = [
        (None, None),
        ({}, {}),
        ({"cell_m": "not a number"}, {}),
        ({}, {"geometry": "not a dict"}),
        ({}, {"geometry": {"h": "tall", "w": None}, "loads": "none"}),
        ([], "record"),
        ({"cell_m": CELL_M}, {"geometry": {"ix_port": "eight"}}),
    ]
    for info, record in cases:
        out = poc_app._geom_mm(info, record)
        assert isinstance(out, dict), f"info={info!r} record={record!r} gave {out!r}"
        assert "src" in out
        assert out["substrate_h_mm"] is None, f"info={info!r} record={record!r}"
    # The shipped record still resolves after all of that.
    assert poc_app._geom_mm({}, _record())["substrate_h_mm"] == pytest.approx(
        SUBSTRATE_MM
    )


# --- the near cut's provenance: what _plane_layout hands _geom_mm -----------


def test_the_near_cut_label_names_the_fallback_when_nothing_was_recorded():
    """No record at all: the constant must not be printed as a measured plane."""
    info = {poc_app.PLANE_KEY: np.zeros((3, 4, 5), dtype=complex), "cell_m": 1e-4}
    layout = poc_app._plane_layout(info, None)
    src = layout["geometry_mm"]["src"]["xcut_near_mm"]

    # The scenario really is the substituted one: the S21 plane itself is the
    # module's fallback constant, and that is the label it carries.
    assert layout["src_s21"] == um3k_context.FALLBACK_SRC
    # The near cut BORROWS that x, so it borrows its route as well.
    assert src == layout["src_s21"]
    assert src == um3k_context.FALLBACK_SRC
    # WHY the negative claim: until _geom_mm took a label this entry always read
    # "s21_plane.x_m" - the recorded-plane key - even on a dump that recorded
    # no plane, so a hard-coded constant was presented as a measurement in the
    # very diagnostic line that exists to tell the two apart.
    assert src != "s21_plane.x_m"
    # And the value the honest label describes is the borrowed fallback x.
    assert layout["geometry_mm"]["xcut_near_mm"] == pytest.approx(layout["x_s21_mm"])


def test_the_near_cut_label_is_the_recorded_plane_when_it_was_recorded():
    """A recorded S21 x keeps its own key as the near cut's route."""
    info = {poc_app.PLANE_KEY: np.zeros((3, 4, 5), dtype=complex), "cell_m": CELL_M}
    # _record() carries s21_plane.x_m = 0.0204 m, which is the recorded route.
    layout = poc_app._plane_layout(info, _record())
    src = layout["geometry_mm"]["src"]["xcut_near_mm"]

    assert layout["src_s21"] == "s21_plane.x_m"
    assert src == layout["src_s21"]
    assert src != um3k_context.FALLBACK_SRC
    # Value and label agree: the near cut IS that recorded plane, 20.4 mm.
    assert layout["geometry_mm"]["xcut_near_mm"] == pytest.approx(layout["x_s21_mm"])
    assert layout["geometry_mm"]["xcut_near_mm"] == pytest.approx(XCUT_MM)


# --- 10..15: _vis_geometry -------------------------------------------------


def test_vis_geometry_draws_the_board_from_the_record_when_info_is_nan(capsys):
    """THE regression: NaN info + a record with geometry still draws the board."""
    plotter = _Plotter()
    poc_app._vis_geometry(plotter, _nan_info(), _planes())
    assert set(plotter.names()) == {
        "ground_plane",
        "substrate",
        "strip_feed",
        "strip_stub",
        "port_source",
        "port_load",
    }, f"the board layer drew {plotter.names()}"
    assert len(plotter.labels) == 1, "the two port labels are one add_point_labels"
    # Nothing was reported missing, so the stderr line stays silent: a drawn
    # board must not also print the "not drawn" sentence.
    assert capsys.readouterr().err == ""
    # The ground plane goes down first, then the board on top of it.
    names = plotter.names()
    assert names.index("ground_plane") < names.index("substrate")
    assert names.index("substrate") < names.index("strip_feed")


def test_the_board_box_is_the_recorded_dimensions():
    """24.8 x 84.8 x 1.6 mm: the record's board, not a default box."""
    plotter = _Plotter()
    poc_app._vis_geometry(plotter, _nan_info(), _planes())
    box = plotter.mesh("substrate")
    assert tuple(box.bounds) == pytest.approx(
        (0.0, X_SPAN_MM, 0.0, Y_SPAN_MM, 0.0, SUBSTRATE_MM)
    )
    ground = plotter.mesh("ground_plane")
    x0, x1, y0, y1, z0, z1 = ground.bounds
    assert (x1 - x0, y1 - y0) == pytest.approx((X_SPAN_MM, Y_SPAN_MM))
    # The plane is lifted off the box by one thousandth of the board height and
    # sits just above z=0, so it does not z-fight with the box's own bottom.
    assert z0 == pytest.approx(-EPS_MM)


def test_the_strip_leaves_a_gap_around_the_load():
    """Feed port->load, stub cut->line end; 20.0..20.4 mm is left bare."""
    plotter = _Plotter()
    poc_app._vis_geometry(plotter, _nan_info(), _planes())

    feed = plotter.mesh("strip_feed")
    feed_span, feed_width, feed_z, feed_y = _stripe(feed)
    assert feed_span == pytest.approx((PORT_MM, LOAD_MM))
    assert feed_width == pytest.approx(STRIP_MM)
    assert feed_y == pytest.approx(0.5 * Y_SPAN_MM)
    # Both segments sit ON TOP of the board, by the same eps the plane uses.
    assert feed_z == pytest.approx((SUBSTRATE_MM + EPS_MM, SUBSTRATE_MM + EPS_MM))

    stub = plotter.mesh("strip_stub")
    stub_span, stub_width, stub_z, stub_y = _stripe(stub)
    assert stub_span == pytest.approx((XCUT_MM, LINE_END_MM))
    assert stub_width == pytest.approx(STRIP_MM)
    assert stub_y == pytest.approx(0.5 * Y_SPAN_MM)
    assert stub_z == pytest.approx(feed_z)

    # The two segments really do not touch: the load gap is one cell wide.
    assert stub_span[0] - feed_span[1] == pytest.approx(CELL_MM)


def test_the_wires_land_on_the_port_and_in_the_gap():
    """One wire per port, through the board, the load one at the gap's centre."""
    plotter = _Plotter()
    poc_app._vis_geometry(plotter, _nan_info(), _planes())

    source = np.asarray(plotter.mesh("port_source").points)
    assert source[0, 0] == pytest.approx(PORT_MM)
    assert source[0, 1] == pytest.approx(0.5 * Y_SPAN_MM)
    assert (source[:, 2].min(), source[:, 2].max()) == pytest.approx(
        (-EPS_MM, SUBSTRATE_MM + EPS_MM)
    )

    load = np.asarray(plotter.mesh("port_load").points)
    # Halfway between the load (20.0 mm) and the near cut (20.4 mm): the wire
    # marks the termination the gap surrounds, not the strip's end.
    assert load[0, 0] == pytest.approx(0.5 * (LOAD_MM + XCUT_MM))
    assert load[0, 1] == pytest.approx(0.5 * Y_SPAN_MM)
    assert (load[:, 2].min(), load[:, 2].max()) == pytest.approx(
        (-EPS_MM, SUBSTRATE_MM + EPS_MM)
    )


def test_a_missing_near_cut_costs_the_stub_and_not_the_board(capsys):
    """The stub needs the near cut; the board, the feed and both wires do not."""
    plotter = _Plotter()
    poc_app._vis_geometry(plotter, _nan_info(), _planes(geometry=True))
    capsys.readouterr()  # drop the full-board output from the check below

    plotter = _Plotter()
    planes = _planes()
    planes["geometry_mm"] = _geom_block(absent=("xcut_near_mm",))
    poc_app._vis_geometry(plotter, _nan_info(), planes)
    assert set(plotter.names()) == {
        "ground_plane",
        "substrate",
        "strip_feed",
        "port_source",
        "port_load",
    }, f"a missing near cut cost more than the stub: {plotter.names()}"
    err = capsys.readouterr().err
    assert err.count("not drawn") == 1
    assert "xcut_near_mm=absent" in err
    assert "substrate_h_mm=absent" not in err


def test_vis_geometry_draws_nothing_but_the_ground_plane(capsys):
    """No number known anywhere: the floor is drawn and ONE line says why."""
    plotter = _Plotter()
    poc_app._vis_geometry(plotter, _nan_info(), None)
    assert plotter.names() == ["ground_plane"], (
        f"nothing is known about the board, yet it drew {plotter.names()}"
    )
    assert plotter.labels == [], "the port labels need ports the board does not have"
    err = capsys.readouterr().err
    assert err.count("not drawn") == 1, f"one line, not many: {err!r}"
    for key in (
        "substrate_h_mm",
        "strip_w_mm",
        "port_x_mm",
        "load_x_mm",
        "xcut_near_mm",
    ):
        assert f"{key}=absent" in err, f"{key} was not named as missing in {err!r}"


def test_vis_geometry_takes_the_millimetres_from_info_when_it_has_them():
    """The same board, this time out of an ``info`` that carries the numbers."""
    plotter = _Plotter()
    poc_app._vis_geometry(plotter, _mm_info(), None)
    assert set(plotter.names()) == {
        "ground_plane",
        "substrate",
        "strip_feed",
        "strip_stub",
        "port_source",
        "port_load",
    }, f"info millimetres were not enough for the board: {plotter.names()}"
    feed_span, _w, _z, _y = _stripe(plotter.mesh("strip_feed"))
    assert feed_span == pytest.approx((PORT_MM, LOAD_MM))


# --- 16..17: _add_markers --------------------------------------------------


def test_add_markers_sizes_its_discs_from_the_field_grid():
    """(shape - 1) * cell about the mid-plane: 84.8 x 8.4 mm at y 42.4, z 4.2."""
    plotter = _Plotter()
    # shape (9, 213, 22): the spans the markers read are (shape - 1) * cell, the
    # n samples span n - 1 cells rule (build_grid places its mesh POINTS at
    # i * cell for i in 0..n-1), so 212 and 21 cells are drawn, not 213 and 22 -
    # the rectangles must not overhang the volume they cross-section.
    info = {poc_app.PLANE_KEY: np.zeros((N_ST, NY + 1, NZ), dtype=complex)}
    poc_app._add_markers(plotter, info, _planes())

    # Two discs, in the order the page names them: the load first, the S11
    # port second. Neither is given a plotter actor name - the colour is what
    # the legend reads - so they are found by position.
    drawn = [mesh for _name, mesh, _kw in plotter.meshes]
    assert len(drawn) == 2, f"expected two discs, got {plotter.names()}"
    for mesh in drawn:
        x0, x1, y0, y1, z0, z1 = mesh.bounds
        assert x0 == pytest.approx(x1, abs=1e-4), "a disc is not a plane normal to x"
        # pyvista lays the plane's two sides however it likes inside the plane
        # normal to x (here i_size lands on z), so the claim is the RECTANGLE
        # and its centre, not which side went where: 84.8 mm by 8.4 mm,
        # centred on the y/z mid-plane of the field.
        # WHY the -1: n samples span n - 1 cells (build_grid points at i*cell).
        assert sorted([y1 - y0, z1 - z0]) == pytest.approx(
            [(NZ - 1) * CELL_MM, NY * CELL_MM], abs=1e-4
        )
        # Same rule for the centre: half of each (n - 1)*cell span.
        assert (0.5 * (y0 + y1), 0.5 * (z0 + z1)) == pytest.approx(
            (0.5 * NY * CELL_MM, 0.5 * (NZ - 1) * CELL_MM), abs=1e-4
        )
    # Each disc sits at its own x, and the colours are the ones the page reads.
    assert [m.bounds[0] for m in drawn] == pytest.approx([LOAD_MM, PORT_MM], abs=1e-4)
    assert [kw.get("color") for _n, _m, kw in plotter.meshes] == ["red", "purple"]
    # Only the first disc flushes the frame; the second one is drawn next.
    assert [kw.get("render") for _n, _m, kw in plotter.meshes] == [True, False]


def test_add_markers_puts_its_labels_on_the_mid_plane():
    """The three anchors are the three x positions, at the y/z centre."""
    plotter = _Plotter()
    info = {poc_app.PLANE_KEY: np.zeros((N_ST, NY + 1, NZ), dtype=complex)}
    planes = _planes()
    poc_app._add_markers(plotter, info, planes)

    assert len(plotter.labels) == 1
    points, labels, kwargs = plotter.labels[0]
    assert [p[0] for p in points] == pytest.approx(
        [planes["x_s11_mm"], planes["x_load_mm"], planes["x_s21_mm"]]
    )
    for _x, y, z in points:
        # WHY the -1: the anchors sit on the mid-plane of the (n - 1)*cell spans.
        assert (y, z) == pytest.approx((0.5 * NY * CELL_MM, 0.5 * (NZ - 1) * CELL_MM))
    assert len(labels) == 3
    assert kwargs.get("font_size") == 9


# --- 18: the _draw_scene call site -----------------------------------------


class _FakeImageData:
    """Stands in for ``pv.ImageData``: attributes, no VTK, no GL.

    Copied from tests/test_poc_volume_arrows.py, where the same driver is used
    to prove a refused port slice costs the slice and not the page.
    """

    def __init__(self):
        self.dimensions = None
        self.spacing = None
        self.origin = None
        self.point_data = {}


class _ScenePlotter:
    """Records the plotter half of ``_draw_scene`` into one ordered log."""

    def __init__(self, log):
        self.log = log

    def clear(self):
        self.log.append("clear")

    def add_mesh(self, mesh, **kwargs):
        self.log.append("slice" if isinstance(mesh, _FakeImageData) else "add_mesh")
        return object()

    def add_axes(self, **kwargs):
        self.log.append("add_axes")

    def add_text(self, text, **kwargs):
        self.log.append(("add_text", kwargs.get("name")))

    def view_isometric(self):
        self.log.append("view_isometric")

    def reset_camera(self):
        self.log.append("reset_camera")


def _drive_scene(monkeypatch, plotter, planes, log):
    """``_draw_scene`` in port mode against stubs; returns (info, seen).

    The stub set is the one tests/test_poc_volume_arrows.py::_drive_port_scene
    uses, with the two board/marker layers replaced by spies so this file can
    read WHERE they were called from instead of what they draw.
    """
    fake_pv = types.SimpleNamespace(ImageData=_FakeImageData)
    monkeypatch.setitem(sys.modules, "pyvista", fake_pv)

    outline = object()
    monkeypatch.setattr(
        poc_app,
        "build_grid",
        lambda _info, _stations_mm=None: types.SimpleNamespace(outline=lambda: outline),
    )
    monkeypatch.setattr(
        poc_app,
        "_cut_layout",
        lambda _info, j, k, _stations_mm=None: {
            "y_mm": 0.0,
            "j": 0,
            "n_j": 1,
            "z_mm": 0.0,
            "k": 0,
            "n_k": 1,
        },
    )
    monkeypatch.setattr(poc_app, "_marker_cut_lines", lambda pl, cl, drawn, vm: {})
    monkeypatch.setattr(poc_app, "_marker_text", lambda pl, cuts: "legend")

    seen = {}

    def _spy_board(p, i, pl):
        seen["board"] = (p, i, pl)
        log.append("board")

    def _spy_markers(p, i, pl):
        seen["markers"] = (p, i, pl)
        log.append("markers")

    monkeypatch.setattr(poc_app, "_vis_geometry", _spy_board)
    monkeypatch.setattr(poc_app, "_add_markers", _spy_markers)

    info = {poc_app.PLANE_KEY: np.ones((N_ST, 4, 5), dtype=complex)}
    poc_app._draw_scene(plotter, info, planes, "port", 0)
    return info, seen


def test_draw_scene_puts_the_board_under_the_markers(monkeypatch):
    """Axes, then the board, then the markers - each given the caller's dicts."""
    log = []
    planes = _planes()
    info, seen = _drive_scene(monkeypatch, _ScenePlotter(log), planes, log)

    assert "board" in log, f"the board layer was never called: {log}"
    assert log.index("add_axes") < log.index("board") < log.index("markers"), (
        "the board must be drawn after the axes and before the markers: "
        f"{log}"
    )
    # Both layers get the CALLER's info and the SAME planes dict: a copy here
    # would silently detach the board from the resolved geometry block.
    assert seen["board"][1] is info
    assert seen["board"][2] is planes
    assert seen["markers"][1] is info
    assert seen["markers"][2] is planes


def test_the_first_draw_scene_frames_the_camera(monkeypatch):
    """A plotter is put in isometric view and fitted on the FIRST build.

    Framing is what keeps the marker planes - which overhang the captured slab,
    the S11 plane at the port end of the line and the S21 plane one cell past
    the load - inside the picture, so it has to happen at least once.
    """
    log = []
    _drive_scene(monkeypatch, _ScenePlotter(log), _planes(), log)

    assert "view_isometric" in log, f"the first build did not aim the camera: {log}"
    assert "reset_camera" in log, f"the first build did not fit the scene: {log}"
    # Aimed, then fitted, and only once every actor is in place - a fit taken
    # before the last marker exists would frame less than the build draws.
    assert log.index("markers") < log.index("view_isometric") < log.index(
        "reset_camera"
    ), f"the camera work is not the last thing the build does: {log}"


def test_a_second_draw_scene_leaves_the_camera_alone(monkeypatch):
    """A rebuild is a slider move: it must not re-frame what the operator set.

    The same plotter, built twice - the only difference between the runs is that
    the first one already framed it. The two builds are handed DIFFERENT ``info``
    dicts on purpose: the camera state is a fact about the render window, and a
    flag kept on the dict would be lost here and re-frame the picture on every
    tick. The board and the markers still have to be redrawn, so this cannot
    pass by the second build doing nothing.
    """
    log = []
    plotter = _ScenePlotter(log)
    planes = _planes()
    _drive_scene(monkeypatch, plotter, planes, log)
    assert "reset_camera" in log, (
        f"the first build did not frame the camera, so there is nothing to "
        f"compare the second build against: {log}"
    )

    del log[:]
    _drive_scene(monkeypatch, plotter, planes, log)

    assert "view_isometric" not in log, (
        "the second build re-aimed the camera: the rotation the operator had "
        f"just made would snap back on the next slider tick: {log}"
    )
    assert "reset_camera" not in log, (
        f"the second build re-fitted the scene under the operator's hand: {log}"
    )
    assert "board" in log and "markers" in log, (
        f"the second build dropped the picture it was supposed to redraw: {log}"
    )
    assert ("add_text", "marker_legend") in log, (
        f"the second build lost the marker legend: {log}"
    )

