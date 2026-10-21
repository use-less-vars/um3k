"""Tests for :mod:`emfit.kicad`, the dependency-free KiCad board reader.

Two things are checked.  First, the tokeniser and the S-expression parser, which
must cope with quoted strings, escapes and nesting without pulling in a library.
Second, a full read of the real ``CMEX.kicad_pcb`` that ships with the project:
an eight-layer board with 93 nets, 583 segments, 81 vias, 81 footprints and four
poured planes.  Every number asserted below was read out of the file itself, so
the tests pin the reader to that board rather than to a guess about what KiCad
usually writes.

All coordinates are millimetres, exactly as KiCad stores them.  Pad positions
are footprint-local -- that is what the file holds -- so the pad assertions
check the local frame and not the placed board position.

A third group builds a deliberately small board in a temporary file: no
stackup, no zones, one unknown form.  It exists to pin down the degradation
behaviour, because a reader that raises on an unfamiliar form is useless for
files written by a KiCad version newer than the reader.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pytest

from emfit.gerber import read_gerber
from emfit.kicad import (
    LayerError,
    PlacedPad,
    Board,
    Footprint,
    Net,
    Pad,
    Track,
    Via,
    Zone,
    load_board,
    parse_file,
    parse_sexpr,
    tokenize,
)

BOARD_PATH = Path(__file__).resolve().parent.parent / "CMEX.kicad_pcb"


# ---------------------------------------------------------------------------
# the real board
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def board() -> Board:
    """The project board, parsed once for the whole module."""
    return load_board(BOARD_PATH)


def test_load_returns_board(board: Board) -> None:
    assert isinstance(board, Board)


def test_header(board: Board) -> None:
    assert board.version == 20221018
    assert board.generator == "pcbnew"
    assert board.thickness == pytest.approx(1.6)


def test_copper_layer_order(board: Board) -> None:
    assert board.copper_layers == [
        "F.Cu",
        "In1.Cu",
        "In2.Cu",
        "In3.Cu",
        "In4.Cu",
        "In5.Cu",
        "In6.Cu",
        "B.Cu",
    ]


def test_user_layer_names(board: Board) -> None:
    assert board.layer_names["F.Cu"] == "signal_front"
    assert board.layer_names["In1.Cu"] == "pwr3.3"
    assert board.layer_names["In2.Cu"] == "signal_in1"
    assert board.layer_names["In3.Cu"] == "gnd"
    assert board.layer_names["In4.Cu"] == "signal_in2"
    assert board.layer_names["In5.Cu"] == "pwr1.8"
    assert board.layer_names["In6.Cu"] == "pwr5"
    assert board.layer_names["B.Cu"] == "signal_bottom"


def test_non_copper_layers_are_named_too(board: Board) -> None:
    # The reader keeps every renamed layer, not only the copper ones.
    assert board.layer_names["B.SilkS"] == "B.Silkscreen"
    assert board.layer_names["F.CrtYd"] == "F.Courtyard"
    assert len(board.layer_names) == 18


# ---- stackup --------------------------------------------------------------
def test_stackup_entry_count(board: Board) -> None:
    # Eight copper, seven dielectric, two mask, two silk and two paste.
    assert len(board.stackup) == 21


def test_stackup_copper(board: Board) -> None:
    copper = [entry for entry in board.stackup if entry.is_copper]
    assert [entry.name for entry in copper] == board.copper_layers
    assert [entry.thickness for entry in copper] == [pytest.approx(0.035)] * 8
    assert {entry.kind for entry in copper} == {"copper"}


def test_stackup_dielectrics(board: Board) -> None:
    diel = [e for e in board.stackup if e.kind in ("core", "prepreg")]
    assert len(diel) == 7
    assert [e.kind for e in diel] == [
        "prepreg",
        "core",
        "prepreg",
        "core",
        "prepreg",
        "core",
        "prepreg",
    ]
    assert [e.thickness for e in diel] == [
        pytest.approx(0.1),
        pytest.approx(0.3),
        pytest.approx(0.1),
        pytest.approx(0.3),
        pytest.approx(0.1),
        pytest.approx(0.3),
        pytest.approx(0.1),
    ]
    assert {e.material for e in diel} == {"FR4"}
    assert [e.epsilon_r for e in diel] == [pytest.approx(4.5)] * 7
    assert [e.loss_tangent for e in diel] == [pytest.approx(0.02)] * 7


def test_stackup_masks_have_no_material(board: Board) -> None:
    masks = [e for e in board.stackup if e.kind == "soldermask"]
    assert [e.name for e in masks] == ["F.Mask", "B.Mask"]
    assert [e.thickness for e in masks] == [pytest.approx(0.01)] * 2
    assert all(e.material is None for e in masks)
    assert all(e.epsilon_r is None for e in masks)


def test_stackup_silk_and_paste_carry_no_thickness(board: Board) -> None:
    # Four entries (two silk, two paste) have no thickness at all.
    assert [e.name for e in board.stackup if e.thickness is None] == [
        "F.SilkS",
        "F.Paste",
        "B.Paste",
        "B.SilkS",
    ]
    assert {e.kind for e in board.stackup if e.thickness is None} == {
        "silkscreen",
        "paste",
    }


def test_stackup_sums_to_declared_thickness(board: Board) -> None:
    total = board.stackup_thickness()
    assert total == pytest.approx(1.6, abs=1e-9)
    assert total == pytest.approx(board.thickness, abs=1e-9)


# ---- nets -----------------------------------------------------------------
def test_net_count(board: Board) -> None:
    assert len(board.nets) == 93
    assert all(isinstance(net, Net) for net in board.nets)
    assert [net.code for net in board.nets] == list(range(93))


def test_net_zero_is_unnamed(board: Board) -> None:
    assert board.net_name(0) == ""
    assert board.nets[0].name == ""


def test_named_nets(board: Board) -> None:
    assert board.net_name(1) == "/Power_suppy/2V"
    assert board.net_name(2) == "GND"
    assert board.net_name(3) == "5V"
    assert board.net_name(4) == "1V8a"
    assert board.net_name(6) == "3V3"


def test_unknown_net_name_is_empty(board: Board) -> None:
    assert board.net_name(999) == ""


def test_routing_uses_72_of_93_nets(board: Board) -> None:
    routed = {track.net for track in board.tracks} | {via.net for via in board.vias}
    assert len(routed) == 72
    # Every net is nevertheless attached to something, pads included.
    assert board.used_net_codes() == set(range(93))


def test_used_net_codes_includes_pads(board: Board) -> None:
    used = board.used_net_codes()
    assert isinstance(used, set)
    # Some nets reach no track and no via, so they only appear because pads are
    # folded in.  Which ones is a property of the file, so compute them.
    routed = {track.net for track in board.tracks} | {via.net for via in board.vias}
    pad_only = {pad.net for pad in board.pads} - routed
    assert pad_only
    assert pad_only <= used


# ---- tracks ---------------------------------------------------------------
def test_track_count(board: Board) -> None:
    assert len(board.tracks) == 583
    assert all(isinstance(track, Track) for track in board.tracks)


def test_track_widths(board: Board) -> None:
    widths = Counter(round(track.width, 6) for track in board.tracks)
    assert widths == {0.25: 576, 0.35: 3, 0.5: 4}


def test_tracks_per_layer(board: Board) -> None:
    per_layer = Counter(track.layer for track in board.tracks)
    assert per_layer == {
        "F.Cu": 462,
        "In2.Cu": 50,
        "In4.Cu": 64,
        "In6.Cu": 1,
        "B.Cu": 6,
    }


def test_track_geometry(board: Board) -> None:
    track = board.tracks[0]
    assert track.start == (pytest.approx(173.175), pytest.approx(139.32))
    assert track.end == (pytest.approx(173.175), pytest.approx(138.45))
    assert track.layer == "F.Cu"
    assert track.net == 1
    assert track.length() == pytest.approx(0.87)


def test_total_routed_length(board: Board) -> None:
    # Only a sanity bound: the exact sum depends on every segment in the file.
    total = sum(track.length() for track in board.tracks)
    assert total > 500.0


def test_footprint_local_pads_are_not_board_coordinates(board: Board) -> None:
    # Pad positions stay in the footprint frame, so the spread is small even
    # though the board itself is roughly 95 mm across.
    xs = [pad.position[0] for pad in board.pads]
    ys = [pad.position[1] for pad in board.pads]
    assert min(xs) == pytest.approx(-5.675)
    assert max(xs) == pytest.approx(5.675)
    assert min(ys) == pytest.approx(-5.675)
    assert max(ys) == pytest.approx(36.83)


# ---- vias -----------------------------------------------------------------
def test_via_count(board: Board) -> None:
    assert len(board.vias) == 81
    assert all(isinstance(via, Via) for via in board.vias)


def test_vias_are_through_only(board: Board) -> None:
    assert Counter(via.span for via in board.vias) == {"through": 81}
    assert all(via.is_through for via in board.vias)
    assert {via.layers for via in board.vias} == {("F.Cu", "B.Cu")}


def test_via_dimensions(board: Board) -> None:
    assert {via.size for via in board.vias} == {0.8}
    assert {via.drill for via in board.vias} == {0.4}


def test_first_via(board: Board) -> None:
    via = board.vias[0]
    assert via.position == (pytest.approx(185.975), pytest.approx(132.55))
    assert via.net == 1


# ---- footprints and pads --------------------------------------------------
def test_footprint_count(board: Board) -> None:
    assert len(board.footprints) == 81
    assert all(isinstance(fp, Footprint) for fp in board.footprints)


def test_all_footprints_on_front_copper(board: Board) -> None:
    assert {fp.layer for fp in board.footprints} == {"F.Cu"}


def test_reference_designators(board: Board) -> None:
    refs = [fp.reference for fp in board.footprints]
    assert len(set(refs)) == 81
    assert Counter("".join(c for c in ref if c.isalpha()) for ref in refs) == {
        "C": 53,
        "R": 16,
        "U": 9,
        "L": 2,
        "J": 1,
    }


def test_footprint_rotation_is_read(board: Board) -> None:
    assert set(fp.rotation for fp in board.footprints) == {0.0, 90.0, 180.0, -90.0}


def test_first_footprint(board: Board) -> None:
    fp = board.footprints[0]
    assert fp.reference == "R1"
    assert fp.value == "R0402_215k"
    assert fp.position == (pytest.approx(166.025), pytest.approx(140.01))
    assert fp.rotation == pytest.approx(90.0)
    assert fp.library_link == "Resistor_SMD:R_0402_1005Metric"
    assert len(fp.pads) == 2


def test_library_links(board: Board) -> None:
    links = {fp.library_link for fp in board.footprints}
    assert len(links) == 12
    assert None not in links


def test_pad_count(board: Board) -> None:
    pads = board.pads
    assert len(pads) == 388
    assert all(isinstance(pad, Pad) for pad in pads)
    assert sum(len(fp.pads) for fp in board.footprints) == 388


def test_pad_types(board: Board) -> None:
    pads = board.pads
    assert Counter(pad.type for pad in pads) == {"smd": 358, "thru_hole": 30}


def test_pad_shapes(board: Board) -> None:
    shapes = Counter(pad.shape for pad in board.pads)
    assert shapes == {"roundrect": 304, "rect": 55, "oval": 29}


def test_through_hole_drill(board: Board) -> None:
    drilled = [pad for pad in board.pads if pad.type == "thru_hole"]
    assert len(drilled) == 30
    assert {pad.drill for pad in drilled} == {0.65}
    # Surface-mount pads have no drill at all.
    assert all(pad.drill is None for pad in board.pads if pad.type == "smd")


def test_pad_layer_tokens(board: Board) -> None:
    layers = Counter(pad.layers for pad in board.pads)
    assert layers == {
        ("F.Cu", "F.Paste", "F.Mask"): 331,
        ("*.Cu", "*.Mask"): 30,
        ("F.Paste",): 23,
        ("F.Cu", "F.Mask"): 4,
    }


def test_on_layer_honours_wildcards(board: Board) -> None:
    pads = board.pads
    # 331 front pads + 4 mask-only pads + 30 through-hole pads on *.Cu.
    assert sum(pad.on_layer("F.Cu") for pad in pads) == 365
    # Only the through-hole pads reach the back copper.
    assert sum(pad.on_layer("B.Cu") for pad in pads) == 30
    # *.Cu also expands to the inner layers.
    assert sum(pad.on_layer("In3.Cu") for pad in pads) == 30
    assert sum(pad.on_layer("F.Paste") for pad in pads) == 354
    # Nothing reaches a layer the board does not have.
    assert sum(pad.on_layer("B.SilkS") for pad in pads) == 0


def test_pad_size_and_number(board: Board) -> None:
    pad = board.pads[0]
    assert pad.number == "1"
    assert pad.position == (pytest.approx(-0.51), pytest.approx(0.0))
    assert pad.size == (pytest.approx(0.54), pytest.approx(0.64))
    assert pad.net == 59


# ---- zones ----------------------------------------------------------------
def test_zone_count(board: Board) -> None:
    assert len(board.zones) == 4
    assert all(isinstance(zone, Zone) for zone in board.zones)


def test_zone_nets_and_layers(board: Board) -> None:
    zones = board.zones
    assert zones[0].net == 2
    assert zones[0].net_name == "GND"
    assert zones[0].layers == ("F.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")
    assert zones[1].net_name == "3V3"
    assert zones[1].layers == ("In1.Cu",)
    assert zones[2].net_name == "1V8a"
    assert zones[2].layers == ("In5.Cu",)
    assert zones[3].net_name == "5V"
    assert zones[3].layers == ("In6.Cu",)


def test_zone_priority(board: Board) -> None:
    assert [zone.priority for zone in board.zones] == [0, 1, 2, 3]


def test_zones_are_unpoured(board: Board) -> None:
    # The saved file has outlines but no fill geometry at all.
    assert all(zone.has_fill is False for zone in board.zones)
    assert all(zone.keepout is False for zone in board.zones)


def test_zone_outlines_are_arrays(board: Board) -> None:
    for zone in board.zones:
        assert isinstance(zone.outline, np.ndarray)
        assert zone.outline.shape == (4, 2)
        assert zone.outline.dtype == np.float64


def test_first_zone_outline(board: Board) -> None:
    expected = np.array(
        [[164.15, 76.2], [164.175, 166.325], [259.45, 166.35], [259.475, 76.15]]
    )
    assert np.allclose(board.zones[0].outline, expected)


def test_zone_min_thickness(board: Board) -> None:
    assert [zone.min_thickness for zone in board.zones] == [pytest.approx(0.25)] * 4


# ---- outline --------------------------------------------------------------
def test_edge_bbox(board: Board) -> None:
    assert board.edge_bbox == (
        pytest.approx(164.15),
        pytest.approx(76.15),
        pytest.approx(259.475),
        pytest.approx(166.35),
    )


def test_plane_outlines_overhang_the_drawn_edge(board: Board) -> None:
    # A poured plane is clipped by copper-to-edge clearance, not by the canvas
    # rectangle, so its outline may sit slightly outside the Edge.Cuts bbox.
    xmin, ymin, xmax, ymax = board.edge_bbox
    left = min(zone.outline[:, 0].min() for zone in board.zones)
    right = max(zone.outline[:, 0].max() for zone in board.zones)
    assert xmin - left == pytest.approx(0.1, abs=1e-9)
    assert right - xmax == pytest.approx(0.1, abs=1e-9)
    assert 0.0 < xmin - left < 0.5
    assert 0.0 < right - xmax < 0.5


# ---------------------------------------------------------------------------
# tokeniser and parser
# ---------------------------------------------------------------------------
def test_tokenize_keeps_quoted_strings_whole() -> None:
    tokens = list(tokenize('(pad "1" smd (at -0.51 0))'))
    assert tokens == ["(", "pad", '"1"', "smd", "(", "at", "-0.51", "0", ")", ")"]


def test_tokenize_is_lazy() -> None:
    # A generator, so a large board need not sit in memory as a token list.
    stream = tokenize("(a b)")
    assert not isinstance(stream, list)
    assert next(iter(stream)) == "("


def test_parse_nesting() -> None:
    forms = parse_sexpr('(kicad_pcb (version 20221018) (net 0 ""))')
    assert forms == [["kicad_pcb", ["version", 20221018], ["net", 0, ""]]]


def test_parse_several_top_level_forms() -> None:
    assert parse_sexpr("(a 1) (b 2)") == [["a", 1], ["b", 2]]


def test_parse_empty_input() -> None:
    assert parse_sexpr("") == []
    assert parse_sexpr("   \n\t ") == []


def test_parse_escapes() -> None:
    # Quoted tokens are unescaped; atoms outside quotes are left alone.
    assert parse_sexpr(r'(x "a\"b" "c\\d")') == [["x", 'a"b', "c\\d"]]


def test_atom_types() -> None:
    parsed = parse_sexpr('(x 42 1.5 yes no "7" "GND")')[0]
    assert isinstance(parsed[1], int) and parsed[1] == 42
    assert isinstance(parsed[2], float) and parsed[2] == 1.5
    assert isinstance(parsed[3], str) and parsed[3] == "yes"
    # A quoted number stays a string: pad numbers and net names are labels.
    assert isinstance(parsed[5], str) and parsed[5] == "7"
    assert isinstance(parsed[6], str) and parsed[6] == "GND"


def test_parse_file_returns_top_level_forms() -> None:
    forms = parse_file(BOARD_PATH)
    assert len(forms) == 1
    assert forms[0][0] == "kicad_pcb"


def test_parse_file_reads_utf8(tmp_path: Path) -> None:
    path = tmp_path / "utf8.kicad_pcb"
    # A non-ASCII silkscreen label is legal in a KiCad file and must not crash
    # the read, which is decoded as UTF-8 rather than as bytes.
    path.write_text('(kicad_pcb (net 0 "") (gr_text "\u00b5strip"))', encoding="utf-8")
    forms = parse_file(path)
    assert forms[0][2] == ["gr_text", "\u00b5strip"]


# ---------------------------------------------------------------------------
# graceful degradation on a sparse board
# ---------------------------------------------------------------------------
SPARSE = """(kicad_pcb (version 20221018) (generator pcbnew)
  (general (thickness 1.6))
  (net 0 "")
  (net 1 "GND")
  (net 2 "VCC")
  (segment (start 1 2) (end 3 4) (width 0.25) (layer "F.Cu") (net 1))
  (via (at 5 6) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net 2))
  (footprint "Test:Thing" (layer "F.Cu") (at 10 20 90)
    (property "Reference" "X1")
    (property "Value" "VAL")
    (pad "1" smd roundrect (at 0 0) (size 1 1)
         (layers "F.Cu" "F.Paste") (net 1 "GND"))
  )
  (something_new (a 1) (b (c 2)))
  (gr_line (start 0 0) (end 10 0) (layer "F.SilkS") (width 0.12))
)
"""


@pytest.fixture()
def sparse(tmp_path: Path) -> Board:
    path = tmp_path / "sparse.kicad_pcb"
    path.write_text(SPARSE, encoding="utf-8")
    return load_board(path)


def test_sparse_header(sparse: Board) -> None:
    assert sparse.version == 20221018
    assert sparse.generator == "pcbnew"
    assert sparse.thickness == pytest.approx(1.6)


def test_sparse_has_no_stackup_or_layer_table(sparse: Board) -> None:
    assert sparse.stackup == []
    assert sparse.stackup_thickness() is None
    assert sparse.copper_layers == []
    assert sparse.layer_names == {}


def test_sparse_single_segment(sparse: Board) -> None:
    assert len(sparse.tracks) == 1
    track = sparse.tracks[0]
    assert track.start == (pytest.approx(1.0), pytest.approx(2.0))
    assert track.end == (pytest.approx(3.0), pytest.approx(4.0))
    assert track.length() == pytest.approx(np.hypot(2.0, 2.0))


def test_sparse_single_via(sparse: Board) -> None:
    assert len(sparse.vias) == 1
    via = sparse.vias[0]
    assert via.position == (pytest.approx(5.0), pytest.approx(6.0))
    assert via.span == "through"
    assert via.is_through


def test_sparse_footprint_and_pad(sparse: Board) -> None:
    assert len(sparse.footprints) == 1
    fp = sparse.footprints[0]
    assert fp.reference == "X1"
    assert fp.value == "VAL"
    assert fp.position == (pytest.approx(10.0), pytest.approx(20.0))
    assert fp.rotation == pytest.approx(90.0)
    assert fp.library_link == "Test:Thing"
    assert len(fp.pads) == 1
    pad = fp.pads[0]
    assert pad.number == "1"
    assert pad.on_layer("F.Cu")
    assert not pad.on_layer("B.Cu")
    assert sparse.pads == fp.pads


def test_sparse_nets(sparse: Board) -> None:
    assert [net.code for net in sparse.nets] == [0, 1, 2]
    assert sparse.net_name(2) == "VCC"
    assert sparse.used_net_codes() == {1, 2}


def test_sparse_no_zones_and_no_outline(sparse: Board) -> None:
    assert sparse.zones == []
    # Only a silkscreen line was drawn, so there is no outline at all.
    assert sparse.edge_bbox is None


def test_unknown_forms_are_ignored(sparse: Board) -> None:
    # The board parses and keeps its known content; the unknown form is dropped.
    assert len(sparse.tracks) == 1
    assert len(sparse.vias) == 1
    assert len(sparse.footprints) == 1


def test_keepout_zone_blind_via_and_rect_outline(tmp_path: Path) -> None:
    """A keepout, a blind via and a rectangle outline; none is on the real board."""
    src = """(kicad_pcb (version 20221018) (generator pcbnew)
  (net 0 "")
  (net 1 "A")
  (via blind (at 1 1) (size 0.5) (drill 0.2) (layers "F.Cu" "In1.Cu") (net 1))
  (zone (net 1) (net_name "A") (layer "F.Cu") (min_thickness 0.2)
    (fill yes)
    (polygon (pts (xy 0 0) (xy 10 0) (xy 10 10)))
    (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 10 0) (xy 10 10)))
  )
  (zone (net 0) (net_name "") (layers "F.Cu" "B.Cu")
    (keepout (tracks not_allowed))
    (polygon (pts (xy 1 1) (xy 2 1) (xy 2 2)))
  )
  (gr_rect (start 0 0) (end 4 3) (layer "Edge.Cuts") (width 0.1))
)"""
    path = tmp_path / "extra.kicad_pcb"
    path.write_text(src, encoding="utf-8")
    parsed = load_board(path)

    assert parsed.vias[0].span == "blind"
    assert not parsed.vias[0].is_through
    assert parsed.vias[0].layers == ("F.Cu", "In1.Cu")

    assert len(parsed.zones) == 2
    assert parsed.zones[0].has_fill is True
    assert parsed.zones[0].priority == 0
    assert parsed.zones[0].outline.shape == (3, 2)
    assert parsed.zones[1].keepout is True
    assert parsed.zones[1].has_fill is False
    assert parsed.zones[1].layers == ("F.Cu", "B.Cu")

    assert parsed.edge_bbox == (
        pytest.approx(0.0),
        pytest.approx(0.0),
        pytest.approx(4.0),
        pytest.approx(3.0),
    )


def test_missing_kicad_pcb_form_raises(tmp_path: Path) -> None:
    path = tmp_path / "empty.kicad_pcb"
    path.write_text("(not_a_board (version 1))", encoding="utf-8")
    with pytest.raises(ValueError):
        load_board(path)


# ---------------------------------------------------------------------------
# pads in board coordinates, against the two importers that can contradict them
# ---------------------------------------------------------------------------
COUPON = Path(__file__).resolve().parent.parent / "kicad_support_project"
COUPON_BOARD = COUPON / "kicad_support_project.kicad_pcb"
COUPON_GERBERS = COUPON / "gerbers"
COUPON_F_CU = COUPON_GERBERS / "kicad_support_project-F_Cu.gtl"
COUPON_F_SILK = COUPON_GERBERS / "kicad_support_project-F_Silkscreen.gto"
COUPON_DRILL = COUPON_GERBERS / "kicad_support_project.drl"

#: A Gerber position is written under ``%FSLAX46Y46``: four integer and six
#: decimal digits of a millimetre, so one nanometre.  A placed pad may therefore
#: differ from the artwork by that resolution and no more.  The number is read
#: off the file's own format rather than fitted to the data.
PLACEMENT_TOL = 1e-6


@pytest.fixture(scope="module")
def coupon() -> Board:
    """The Gerber-exported coupon, parsed once for the placement tests."""
    return load_board(COUPON_BOARD)


def _distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _match_one_for_one(left, right, tol: float = PLACEMENT_TOL):
    """Pair two point lists greedily; return ``(pairs, left_only, right_only)``.

    Greedy nearest match, one partner per point.  Returning what was left over
    on *both* sides is the point: a pad no artwork claims and a piece of
    artwork no pad claims fail separately, so neither a missing nor a doubly
    counted pad can hide behind a matching total.
    """
    pairs, left_only = [], []
    remaining = list(right)
    for point in left:
        best = min(remaining, key=lambda c: _distance(point, c), default=None)
        if best is not None and _distance(point, best) <= tol:
            pairs.append((point, best))
            remaining.remove(best)
        else:
            left_only.append(point)
    return pairs, left_only, remaining


def _assert_points_match(found, expected, tol: float = 1e-9) -> None:
    pairs, only_found, only_expected = _match_one_for_one(found, expected, tol)
    assert only_found == []
    assert only_expected == []
    assert len(pairs) == len(expected)


def test_front_copper_pads_match_the_gerber_flashes(coupon: Board) -> None:
    """Every front pad is one ``D03`` flash of the exported ``F.Cu`` layer."""
    layer = read_gerber(COUPON_F_CU)
    # KiCad writes Gerber with y negated relative to the board file.
    flashes = [(flash.x, -flash.y) for flash in layer.flashes]
    pads = [p for p in coupon.pads_in_board_frame() if "F.Cu" in p.copper_layers]

    assert all(isinstance(pad, PlacedPad) for pad in pads)
    assert len(pads) == 12
    assert len(flashes) == 12

    pairs, pad_only, flash_only = _match_one_for_one(
        [pad.position for pad in pads], flashes
    )

    print(f"{len(pairs)} of {len(pads)} pads matched one of {len(flashes)} flashes")
    for pad in pads:
        hit = [f for pos, f in pairs if pos is pad.position or pos == pad.position]
        print(
            f"  {pad.reference:>3} {pad.number:>2} "
            f"({pad.position[0]:8.3f}, {pad.position[1]:8.3f}) -> {hit}"
        )

    assert pad_only == []
    assert flash_only == []
    assert len(pairs) == len(pads) == len(flashes)


def _excellon_hits(path: Path) -> list[tuple[float, float, float]]:
    """Parse a metric Excellon file into ``(diameter, x, y)``, y un-negated.

    Deliberately here and not in the package: the drill file is a fixture for
    cross-checking the board reader, not something emfit ships a reader for.
    """
    tools: dict[int, float] = {}
    diameter: float | None = None
    hits: list[tuple[float, float, float]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        tool = re.fullmatch(r"T(\d+)C([\d.]+)", line)
        if tool:
            tools[int(tool.group(1))] = float(tool.group(2))
            continue
        select = re.fullmatch(r"T(\d+)", line)
        if select:
            diameter = tools[int(select.group(1))]
            continue
        hit = re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
        if hit and diameter is not None:
            hits.append((diameter, float(hit.group(1)), -float(hit.group(2))))
    return hits


def test_through_hole_pads_match_the_excellon_drill(coupon: Board) -> None:
    """Every drilled hole is a through-hole pad, and every such pad a hole."""
    hits = _excellon_hits(COUPON_DRILL)
    through = [p for p in coupon.pads_in_board_frame() if p.drill is not None]

    assert Counter(round(d, 6) for d, _, _ in hits) == {1.5: 2, 1.7: 8}
    assert len(through) == 10

    matched = 0
    for diameter in (1.5, 1.7):
        pads = [p for p in through if p.drill == pytest.approx(diameter)]
        holes = [(x, y) for d, x, y in hits if d == pytest.approx(diameter)]
        pairs, pad_only, hole_only = _match_one_for_one(
            [p.position for p in pads], holes
        )
        print(
            f"  T{diameter}: {len(pairs)} pairs from "
            f"{len(pads)} pads and {len(holes)} holes"
        )
        assert pad_only == []
        assert hole_only == []
        matched += len(pairs)

    assert matched == len(through) == len(hits)


def test_rotated_footprints_land_on_the_board(coupon: Board) -> None:
    """J1 is placed at 90 degrees and J2 at 270; both centres are by hand."""
    placed = [p for p in coupon.pads_in_board_frame() if p.reference in ("J1", "J2")]
    by_ref = defaultdict(list)
    for pad in placed:
        by_ref[pad.reference].append(pad)

    assert sorted(by_ref) == ["J1", "J2"]
    # 4.5/65.5 +/- 2.54 keeps the same four offsets at either quarter turn.
    _assert_points_match(
        [p.position for p in by_ref["J1"]],
        [
            (4.5, 10.0),
            (1.96, 7.46),
            (1.96, 12.54),
            (7.04, 7.46),
            (7.04, 12.54),
        ],
    )
    _assert_points_match(
        [p.position for p in by_ref["J2"]],
        [
            (65.5, 10.0),
            (62.96, 7.46),
            (62.96, 12.54),
            (68.04, 7.46),
            (68.04, 12.54),
        ],
    )

    for pad in by_ref["J1"]:
        assert pad.rotation == pytest.approx(90.0)
    for pad in by_ref["J2"]:
        assert pad.rotation == pytest.approx(270.0)
    for pad in placed:
        assert pad.side == "front"
        assert pad.copper_layers == ("F.Cu", "B.Cu")
        assert pad.drill in (pytest.approx(1.5), pytest.approx(1.7))

QUARTER_TURN = """(kicad_pcb (version 20221018) (generator pcbnew)
  (net 0 "")
  (net 1 "N")
  (footprint "Test:Asymmetric" (layer "F.Cu") (at 10 10 90)
    (property "Reference" "Q1")
    (property "Value" "ASYM")
    (pad "1" smd rect (at 1 0) (size 1 1) (layers "F.Cu" "F.Mask") (net 1 "N"))
    (pad "2" smd rect (at 0 2) (size 1 1) (layers "F.Cu" "F.Mask") (net 1 "N"))
  )
)
"""


def test_quarter_turn_of_an_asymmetric_footprint(tmp_path: Path) -> None:
    """A 90-degree footprint whose pads cannot be confused with each other.

    Every pad on the coupon is symmetric under a quarter turn, so the coupon
    cannot say which way a rotation goes; this board can.  Under the documented
    rule local ``(1, 0)`` becomes ``(0, -1)`` and local ``(0, 2)`` becomes
    ``(2, 0)``; the opposite handedness would give ``(10, 11)`` and
    ``(8, 10)``.
    """
    path = tmp_path / "rotated.kicad_pcb"
    path.write_text(QUARTER_TURN, encoding="utf-8")

    pads = {pad.number: pad for pad in load_board(path).pads_in_board_frame()}
    assert set(pads) == {"1", "2"}
    assert pads["1"].position == (pytest.approx(10.0), pytest.approx(9.0))
    assert pads["2"].position == (pytest.approx(12.0), pytest.approx(10.0))
    assert pads["1"].rotation == pytest.approx(90.0)
    assert pads["1"].reference == "Q1"
    assert pads["1"].side == "front"
    assert pads["1"].net_name == "N"
    assert pads["1"].copper_layers == ("F.Cu",)
    assert pads["1"].shape == "rect"
    assert pads["1"].size == (1.0, 1.0)
    assert pads["1"].drill is None


def test_rotation_sign_is_the_one_kicad_silkscreen_uses(coupon: Board) -> None:
    """The handedness comes from KiCad's own plot, not from a guess.

    J1 carries an asymmetric silk chevron at footprint-local
    ``(-4.1, 0.5) -> (-3.6, 0) -> (-4.1, -0.5)``.  Rotating it by J1's own
    ``at`` angle must land on the chevron KiCad plotted; the opposite sign would
    put it at ``(4.0, 5.9) -> (4.5, 6.4) -> (5.0, 5.9)``, which is not in the
    file.
    """
    j1 = next(fp for fp in coupon.footprints if fp.reference == "J1")
    assert j1.rotation == pytest.approx(90.0)

    theta = math.radians(j1.rotation)
    local = [(-4.1, 0.5), (-3.6, 0.0), (-4.1, -0.5)]
    expected = [
        (
            round(j1.position[0] + x * math.cos(theta) + y * math.sin(theta), 6),
            round(j1.position[1] + y * math.cos(theta) - x * math.sin(theta), 6),
        )
        for x, y in local
    ]
    assert expected == [(5.0, 14.1), (4.5, 13.6), (4.0, 14.1)]

    layer = read_gerber(COUPON_F_SILK)
    plotted = {
        (round(s.x0, 6), round(-s.y0, 6))
        for s in layer.segments
        if abs(s.width - 0.12) < 1e-9 and 4.0 <= s.x0 <= 5.1 and 13.5 <= -s.y0 <= 14.2
    }
    # The chevron is two strokes meeting at the apex, i.e. three points; the
    # box above excludes the squares it sits inside.  Only each stroke's start
    # is collected, so the apex shows up once, as the second stroke's start.
    assert plotted == {(5.0, 14.1), (4.5, 13.6)}
    assert (5.0, 14.1) in plotted
    assert (4.5, 13.6) in plotted


def test_unintelligible_layers_are_refused(tmp_path: Path) -> None:
    """A layer this module cannot place raises instead of being guessed."""
    inner = tmp_path / "inner.kicad_pcb"
    inner.write_text(
        "(kicad_pcb (version 20221018) (generator pcbnew)\n"
        '  (net 0 "")\n'
        '  (footprint "Test:Inner" (layer "In1.Cu") (at 1 1)\n'
        '    (property "Reference" "U9")\n'
        '    (pad "1" smd rect (at 0 0) (size 1 1) (layers "In1.Cu") (net 0 ""))\n'
        "  )\n)\n",
        encoding="utf-8",
    )
    with pytest.raises(LayerError, match="U9"):
        load_board(inner).pads_in_board_frame()

    silk = tmp_path / "silk.kicad_pcb"
    silk.write_text(
        "(kicad_pcb (version 20221018) (generator pcbnew)\n"
        '  (net 0 "")\n'
        '  (footprint "Test:Silk" (layer "F.Cu") (at 1 1)\n'
        '    (property "Reference" "U8")\n'
        '    (pad "3" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.SilkS") (net 0 ""))\n'
        "  )\n)\n",
        encoding="utf-8",
    )
    with pytest.raises(LayerError, match="U8") as raised:
        load_board(silk).pads_in_board_frame()
    assert "'3'" in str(raised.value)


FLIPPED = """(kicad_pcb (version 20221018) (generator pcbnew)
  (net 0 "")
  (net 1 "N")
  (footprint "Test:Asymmetric" (layer "B.Cu") (at 10 10 90)
    (property "Reference" "Q2")
    (property "Value" "ASYM")
    (pad "1" smd rect (at 1 0) (size 1 1) (layers "B.Cu" "B.Mask") (net 1 "N"))
  )
)
"""


def test_flipped_footprint_follows_the_documented_rule(tmp_path: Path) -> None:
    """A back-side footprint is placed by the same rule as a front one.

    KiCad writes a flipped footprint's pads already mirrored -- the stored local
    coordinates are post-flip and the pad layer set reads ``B.Cu``/``B.Mask`` --
    so no second mirror is applied here.  No board in this repository has a
    ``B.Cu`` footprint, so this test pins the choice rather than an oracle: it
    exists so that changing the back-side rule has to break a test.
    """
    path = tmp_path / "flipped.kicad_pcb"
    path.write_text(FLIPPED, encoding="utf-8")

    pads = {pad.number: pad for pad in load_board(path).pads_in_board_frame()}
    assert pads["1"].side == "back"
    assert pads["1"].copper_layers == ("B.Cu",)
    # The same arithmetic as the front: local (1, 0) at +90 -> (0, -1).
    assert pads["1"].position == (pytest.approx(10.0), pytest.approx(9.0))


# ---------------------------------------------------------------------------
# naming one pad, for a port
# ---------------------------------------------------------------------------
def test_pad_at_finds_the_connector_pad_in_board_frame(coupon: Board) -> None:
    """``pad_at`` returns the file's own pad, placed and unrotated.

    Kills a footprint-local position, a lost drill and a guessed side.
    """
    pad = coupon.pad_at("J1", "1")

    assert pad.position == (pytest.approx(4.5), pytest.approx(10.0))
    assert pad.net_name == "RF_IN"
    assert pad.side == "front"
    assert pad.shape == "roundrect"
    assert pad.size == (pytest.approx(2.3), pytest.approx(2.3))
    assert pad.drill == pytest.approx(1.5)


def test_pad_at_refuses_a_pad_number_that_appears_four_times(coupon: Board) -> None:
    """A number that names four legs is refused, not resolved by position.

    Kills returning the first match, or the nearest one to a caller's guess.
    """
    with pytest.raises(ValueError, match="4 pads") as caught:
        coupon.pad_at("J1", "2")

    assert "J1.2" in str(caught.value)


def test_pad_at_lists_the_pads_when_the_pair_is_absent(coupon: Board) -> None:
    """An absent reference.number names what the board does declare.

    Kills a bare "not found" that leaves the caller to guess at the edit.
    """
    with pytest.raises(ValueError, match="R1.2"):
        coupon.pad_at("J9", "1")


def test_pad_at_reads_the_far_connector_too(coupon: Board) -> None:
    """The down-stream connector is placed by the same lookup.

    Kills an answer pinned to the first footprint, or to the only one.
    """
    pad = coupon.pad_at("J2", "1")

    assert pad.position == (pytest.approx(65.5), pytest.approx(10.0))

