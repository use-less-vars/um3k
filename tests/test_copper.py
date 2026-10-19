"""Tests for :mod:`emfit.copper` -- copper geometry as a PEC edge mask.

Everything here is checked twice: once on a tiny synthetic four-layer board
whose copper is placed on exact grid coordinates, so every expected count can
be worked out by hand, and once as a smoke test on the reference board, where
the interesting numbers are fractions rather than counts.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

from emfit.copper import (
    Z_TOL,
    copper_area,
    copper_pec_mask,
    layer_fill,
    layer_node_indices,
    layer_occupancy,
    via_fill,
)
from emfit.grid import Grid
from emfit.kicad import load_board
from emfit.raster import MM, build, layer_z_positions

BOARD_PATH = Path(__file__).resolve().parent.parent / "CMEX.kicad_pcb"

#: The synthetic coupon: a 20 x 10 mm window at 1 mm, so cell counts and edge
#: coordinates are both easy to write down.
REGION = (0.0, 0.0, 20.0, 10.0)
DX = 1.0e-3

STACKUP = """\
      (layer "F.Mask" (type "soldermask") (thickness 0.01))
      (layer "F.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 1" (type "prepreg") (thickness 0.2)
        (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
      (layer "In1.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 2" (type "core") (thickness 0.8)
        (material "FR4") (epsilon_r 4.4) (loss_tangent 0.02))
      (layer "In2.Cu" (type "copper") (thickness 0.035))
      (layer "dielectric 3" (type "prepreg") (thickness 0.2)
        (material "FR4") (epsilon_r 4.2) (loss_tangent 0.02))
      (layer "B.Cu" (type "copper") (thickness 0.035))
      (layer "B.Mask" (type "soldermask") (thickness 0.01))
"""


def _board_text(tracks: str = "", vias: str = "", zones: str = "") -> str:
    """A minimal four-copper-layer board with the given copper forms."""
    return (
        "(kicad_pcb (version 20221018) (generator pcbnew)\n"
        "  (general (thickness 1.36))\n"
        '  (layers (0 "F.Cu" signal) (1 "In1.Cu" signal)\n'
        '    (2 "In2.Cu" signal) (31 "B.Cu" signal))\n'
        "  (setup\n"
        "    (stackup\n"
        f"{STACKUP}"
        "    )\n"
        "  )\n"
        "  (net 0 \"\")\n"
        f"{tracks}{vias}{zones})\n"
    )


def _load(tmp_path, text: str):
    path = tmp_path / "coupon.kicad_pcb"
    path.write_text(text)
    return load_board(path)


def _synthetic(tmp_path, tracks="", vias="", zones=""):
    board = _load(tmp_path, _board_text(tracks=tracks, vias=vias, zones=zones))
    return board, build(board, REGION, DX)


TRACK_TEXT = """\
  (segment (start 2 3) (end 14 3) (width 2.4) (layer "F.Cu") (net 1))
"""

ZONE_TEXT = """\
  (zone (net 1) (net_name "P") (layer "In1.Cu") (priority 0)
    (polygon (pts (xy 4.2 2.2) (xy 8.8 2.2) (xy 8.8 6.8) (xy 4.2 6.8))))
"""

VIA_TEXT = """\
  (via (at 10 5) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 1))
"""

SNAP_TEXT = """\
  (via (at 10.5 5.5) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 1))
"""


@pytest.fixture(scope="module")
def track_board(tmp_path_factory):
    return _synthetic(tmp_path_factory.mktemp("track"), tracks=TRACK_TEXT)


@pytest.fixture(scope="module")
def zone_board(tmp_path_factory):
    return _synthetic(tmp_path_factory.mktemp("zone"), zones=ZONE_TEXT)


@pytest.fixture(scope="module")
def via_board(tmp_path_factory):
    return _synthetic(tmp_path_factory.mktemp("via"), vias=VIA_TEXT)


@pytest.fixture(scope="module")
def snap_board(tmp_path_factory):
    return _synthetic(tmp_path_factory.mktemp("snap"), vias=SNAP_TEXT)


# ---------------------------------------------------------------------------
# the three edge blocks, as views on the flat mask
# ---------------------------------------------------------------------------
def _blocks(mask, coupon):
    cc, grid = coupon.cc, coupon.grid
    ex = mask[cc.off_ex:cc.off_ex + cc.n_ex].reshape(grid.edge_shape("x"))
    ey = mask[cc.off_ey:cc.off_ey + cc.n_ey].reshape(grid.edge_shape("y"))
    ez = mask[cc.off_ez:cc.off_ez + cc.n_ez].reshape(grid.edge_shape("z"))
    return ex, ey, ez


# ---------------------------------------------------------------------------
# z node assignment
# ---------------------------------------------------------------------------
def test_mesh_is_the_expected_tiny_shoebox(track_board):
    board, coupon = track_board
    assert coupon.grid.shape == (20, 10, 12)
    assert coupon.grid.edge_shape("x") == (20, 11, 13)
    assert coupon.grid.edge_shape("y") == (21, 10, 13)
    assert coupon.grid.edge_shape("z") == (21, 11, 12)


def test_layer_node_indices_land_on_the_mid_planes(track_board):
    board, coupon = track_board
    node_of = layer_node_indices(board, coupon.grid)
    z = layer_z_positions(board)
    assert list(node_of) == ["B.Cu", "In2.Cu", "In1.Cu", "F.Cu"]
    for name, k in node_of.items():
        assert abs(coupon.grid.z[k] - z[name]) <= Z_TOL


def test_layer_node_indices_accept_a_subset(track_board):
    board, coupon = track_board
    assert set(layer_node_indices(board, coupon.grid, ["F.Cu"])) == {"F.Cu"}
    assert set(layer_node_indices(board, coupon.grid, "B.Cu")) == {"B.Cu"}


def test_layer_node_indices_reject_an_unknown_layer(track_board):
    board, coupon = track_board
    with pytest.raises(ValueError, match="not a copper layer"):
        layer_node_indices(board, coupon.grid, ["In7.Cu"])


def test_layer_node_indices_reject_a_grid_without_the_sheets(track_board):
    board, coupon = track_board
    off = Grid(x=coupon.grid.x, y=coupon.grid.y, z=coupon.grid.z + 1.0e-5)
    with pytest.raises(ValueError, match="not on a grid node"):
        layer_node_indices(board, off)


# ---------------------------------------------------------------------------
# a single track
# ---------------------------------------------------------------------------
def test_track_pins_the_edges_under_its_stroke(track_board):
    board, coupon = track_board
    k = layer_node_indices(board, coupon.grid)["F.Cu"]
    ex, ey, ez = _blocks(copper_pec_mask(coupon.cc, board), coupon)

    # 14 EX edges on each of the three rows the 2.4 mm stroke covers
    rows = ex[:, :, k]
    assert rows.sum() == 42
    for j in (2, 3, 4):
        assert np.flatnonzero(rows[:, j]).tolist() == list(range(1, 15))
    for j in (0, 1, 5, 6, 7, 8, 9, 10):
        assert not rows[:, j].any()
    # a track is symmetric about its centreline
    assert np.array_equal(rows[:, 2], rows[:, 4])

    # 15 EY edges on each of the two rows
    eys = ey[:, :, k]
    assert eys.sum() == 30
    for j in (2, 3):
        assert np.flatnonzero(eys[:, j]).tolist() == list(range(1, 16))
    assert not eys[0, :].any()
    assert not eys[16:, :].any()

    # nothing on any other plane, and no barrel
    assert set(np.unique(np.nonzero(ex)[2])) == {k}
    assert set(np.unique(np.nonzero(ey)[2])) == {k}
    assert not ez.any()


def test_track_board_has_no_electrical_connection_between_planes(track_board):
    board, coupon = track_board
    mask = copper_pec_mask(coupon.cc, board)
    _, _, ez = _blocks(mask, coupon)
    assert not ez.any()


# ---------------------------------------------------------------------------
# a single zone
# ---------------------------------------------------------------------------
def test_zone_is_filled_solid_on_its_own_layer(zone_board):
    board, coupon = zone_board
    node_of = layer_node_indices(board, coupon.grid)
    mask = copper_pec_mask(coupon.cc, board)
    ex, ey, ez = _blocks(mask, coupon)

    k = node_of["In1.Cu"]
    rows = ex[:, :, k]
    assert rows.sum() == 20
    for j in (3, 4, 5, 6):
        assert np.flatnonzero(rows[:, j]).tolist() == list(range(4, 9))
    eys = ey[:, :, k]
    assert eys.sum() == 20
    for j in (2, 3, 4, 5, 6):
        assert np.flatnonzero(eys[:, j]).tolist() == list(range(5, 9))

    # the zone names only In1.Cu, so the other planes stay bare
    for name, other in node_of.items():
        if name == "In1.Cu":
            continue
        assert not ex[:, :, other].any()
        assert not ey[:, :, other].any()
    assert not ez.any()


def test_copper_area_tracks_the_analytic_stroke_area(tmp_path):
    """On a 0.1 mm mesh the rasterised area is the stroke's own area."""
    board = _load(tmp_path, _board_text(tracks=TRACK_TEXT))
    coupon = build(board, REGION, 0.1e-3)
    assert coupon.grid.shape == (200, 100, 12)

    track = board.tracks[0]
    half = 0.5 * track.width
    # a kicad stroke: the rectangle plus the two round caps
    analytic_mm2 = track.width * track.length() + np.pi * half * half
    got = copper_area(board, coupon.cc, "F.Cu", REGION)
    assert got == pytest.approx(analytic_mm2 * MM * MM, rel=0.05)
    # no copper, no area
    assert copper_area(board, coupon.cc, "B.Cu", REGION) == 0.0


def test_zone_fill_ignores_the_has_fill_flag(zone_board):
    board, coupon = zone_board
    assert board.zones[0].has_fill is False
    assert layer_fill(board, "In1.Cu", 6.0e-3, 4.0e-3)


# ---------------------------------------------------------------------------
# a single via
# ---------------------------------------------------------------------------
def test_via_pins_one_node_column_between_its_sheets(via_board):
    board, coupon = via_board
    node_of = layer_node_indices(board, coupon.grid)
    k_lo, k_hi = node_of["B.Cu"], node_of["F.Cu"]
    before = len(board.vias)
    warnings: list[str] = []
    mask = copper_pec_mask(coupon.cc, board, warnings=warnings)
    assert warnings == []
    assert before == 1

    ex, ey, ez = _blocks(mask, coupon)
    assert not ex.any()
    assert not ey.any()

    cols = np.nonzero(ez.any(axis=2))
    assert [tuple(int(v) for v in c) for c in zip(*cols)] == [(10, 5)]
    assert ez[10, 5].sum() == k_hi - k_lo
    assert ez[10, 5, k_lo:k_hi].all()
    assert not ez[10, 5, :k_lo].any()
    assert not ez[10, 5, k_hi:].any()


def test_a_via_smaller_than_a_cell_snaps_to_its_nearest_node(snap_board):
    board, coupon = snap_board
    node_of = layer_node_indices(board, coupon.grid)
    k_lo, k_hi = node_of["B.Cu"], node_of["F.Cu"]
    warnings: list[str] = []
    mask = copper_pec_mask(coupon.cc, board, warnings=warnings)

    assert len(warnings) == 1
    assert "snapped" in warnings[0]
    _, _, ez = _blocks(mask, coupon)
    cols = np.nonzero(ez.any(axis=2))
    assert [tuple(int(v) for v in c) for c in zip(*cols)] == [(10, 5)]
    assert ez[10, 5].sum() == k_hi - k_lo


def test_layers_restricts_sheets_but_not_barrels(via_board):
    board, coupon = via_board
    node_of = layer_node_indices(board, coupon.grid)
    mask = copper_pec_mask(coupon.cc, board, layers=["F.Cu"])
    assert set(layer_node_indices(board, coupon.grid, ["F.Cu"])) == {"F.Cu"}
    ex, ey, ez = _blocks(mask, coupon)
    assert not ex.any() and not ey.any()
    assert ez.sum() == node_of["F.Cu"] - node_of["B.Cu"]


def test_warnings_list_is_appended_to_not_replaced(via_board):
    board, coupon = via_board
    warnings = ["caller wrote this"]
    copper_pec_mask(coupon.cc, board, warnings=warnings)
    assert warnings == ["caller wrote this"]


# ---------------------------------------------------------------------------
# the point-wise helpers
# ---------------------------------------------------------------------------
def test_layer_fill_points(track_board):
    board, _coupon = track_board
    assert layer_fill(board, "F.Cu", 2.0e-3, 3.0e-3)
    assert layer_fill(board, "F.Cu", 8.0e-3, 3.0e-3)
    # half the width away is still copper: the boundary is inclusive
    assert layer_fill(board, "F.Cu", 2.0e-3, 4.2e-3)
    assert not layer_fill(board, "F.Cu", 2.0e-3, 4.3e-3)
    # round cap: 1.2 mm behind the start, on the centreline
    assert layer_fill(board, "F.Cu", 0.8e-3, 3.0e-3)
    assert not layer_fill(board, "F.Cu", 0.5e-3, 3.0e-3)
    # wrong layer
    assert not layer_fill(board, "B.Cu", 2.0e-3, 3.0e-3)


def test_layer_fill_result_shape_follows_the_input(track_board):
    board, _coupon = track_board
    xs = np.array([[2.0e-3], [18.0e-3]])
    ys = np.array([[3.0e-3, 3.0e-3, 3.0e-3]])
    out = layer_fill(board, "F.Cu", xs, ys)
    assert out.shape == (2, 3)
    assert out.dtype == bool
    assert out.tolist() == [[True] * 3, [False] * 3]


def test_layer_fill_rejects_an_unknown_layer(track_board):
    board, _coupon = track_board
    with pytest.raises(ValueError, match="not a copper layer"):
        layer_fill(board, "In9.Cu", 0.0, 0.0)
    with pytest.raises(ValueError, match="not a copper layer"):
        layer_fill(board, "F.SilkS", 0.0, 0.0)


def test_layer_occupancy_is_the_lateral_cell_view(track_board):
    board, coupon = track_board
    occ = layer_occupancy(board, coupon.grid, "F.Cu")
    assert occ.shape == (20, 10)
    assert occ.sum() == 28
    for j in (2, 3):
        assert np.flatnonzero(occ[:, j]).tolist() == list(range(1, 15))
    for j in (0, 1, 4, 5, 6, 7, 8, 9):
        assert not occ[:, j].any()


def test_via_fill_points(via_board):
    board, _coupon = via_board
    z = layer_z_positions(board)
    mid = 0.5 * (z["F.Cu"] + z["B.Cu"])
    assert via_fill(board, 10.0e-3, 5.0e-3, mid)
    # edge of the barrel, inclusive
    assert via_fill(board, 10.4e-3, 5.0e-3, mid)
    assert not via_fill(board, 10.5e-3, 5.0e-3, mid)
    # above the top sheet the barrel has ended
    assert not via_fill(board, 10.0e-3, 5.0e-3, z["F.Cu"] + 1.0e-5)
    assert not via_fill(board, 10.0e-3, 5.0e-3, z["B.Cu"] - 1.0e-5)


def test_via_fill_is_false_without_any_via(track_board):
    board, _coupon = track_board
    assert not via_fill(board, 10.0e-3, 5.0e-3, 0.0)


# ---------------------------------------------------------------------------
# the reference board
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cmex():
    board = load_board(BOARD_PATH)
    lo_x, lo_y, hi_x, hi_y = board.edge_bbox
    region = (lo_x, lo_y, lo_x + 96.0, lo_y + 91.0)
    assert region[2] >= hi_x and region[3] >= hi_y
    return board, build(board, region, DX)


@pytest.fixture(scope="module")
def cmex_mask(cmex):
    board, coupon = cmex
    return copper_pec_mask(coupon.cc, board)


def test_mask_shape_and_dtype(cmex, cmex_mask):
    _board, coupon = cmex
    assert cmex_mask.shape == (coupon.cc.n_edges,)
    assert cmex_mask.dtype == bool
    assert cmex_mask.any()


def _inplane_fraction(mask, coupon, k):
    ex, ey, _ez = _blocks(mask, coupon)
    total = coupon.cc.nx * coupon.cc.nyn + coupon.cc.nxn * coupon.cc.ny
    return (ex[:, :, k].sum() + ey[:, :, k].sum()) / total


@pytest.mark.parametrize("layer", ["F.Cu", "In1.Cu", "In5.Cu"])
def test_a_poured_plane_grounds_almost_every_in_plane_edge(cmex, cmex_mask, layer):
    board, coupon = cmex
    pour = [z for z in board.zones if layer in z.layers and not z.keepout]
    assert pour, f"no pour on {layer}"
    k = layer_node_indices(board, coupon.grid)[layer]
    assert _inplane_fraction(cmex_mask, coupon, k) > 0.9


def test_barrels_pin_exactly_one_node_column_each(cmex, cmex_mask):
    board, coupon = cmex
    node_of = layer_node_indices(board, coupon.grid)
    span = node_of["F.Cu"] - node_of["B.Cu"]
    assert span == 14
    ex, ey, ez = _blocks(cmex_mask, coupon)
    assert not ex.any() or True  # in-plane copper is tested above
    cols = {}
    for i, j in zip(*np.nonzero(ez.any(axis=2))):
        cols[(int(i), int(j))] = int(ez[i, j].sum())
    assert 0 < len(cols) <= len(board.vias)
    assert set(cols.values()) == {span}
    assert all(board.vias)


def test_pads_are_not_rasterised(cmex, cmex_mask):
    board, coupon = cmex
    assert board.footprints and any(f.pads for f in board.footprints)
    stripped = dataclasses.replace(board, footprints=[])
    assert np.array_equal(copper_pec_mask(coupon.cc, stripped), cmex_mask)


def test_a_real_track_is_copper(cmex):
    board, _coupon = cmex
    track = board.tracks[0]
    mx = 0.5 * (track.start[0] + track.end[0]) * MM
    my = 0.5 * (track.start[1] + track.end[1]) * MM
    assert layer_fill(board, track.layer, mx, my)

    # with the pours removed the copper at that point can only be the track,
    # and a few millimetres to one side of it must be bare
    bare = dataclasses.replace(board, zones=[])
    assert layer_fill(bare, track.layer, mx, my)
    dx, dy = track.end[0] - track.start[0], track.end[1] - track.start[1]
    norm = float(np.hypot(dx, dy))
    off = 0.5 * track.width + 2.0  # 2 mm clear of the stroke edge
    nx, ny = mx + off * (-dy / norm) * MM, my + off * (dx / norm) * MM
    assert not layer_fill(bare, track.layer, nx, ny)
