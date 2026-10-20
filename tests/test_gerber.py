"""Tests for :mod:`emfit.gerber`, the dependency-free RS-274X reader.

Two layers of checking.  The first is a set of five-line files written into a
temporary directory, one per feature the reader claims: 4.6 mm leading-zero
suppression and absolute coordinates, the inch unit factor, a non-circular
aperture (whose stroke width is deliberately ``None``), a ``G02`` arc that must
be counted but never flattened, and the two ways a draw can arrive with no usable
aperture.  Those pin the arithmetic, which a real file can only confirm.

The second is the Gerber export of the project coupon
(``kicad_support_project``): ``F_Cu`` is cross-checked against the same board read
by :mod:`emfit.kicad`, so the two independent readers must agree on the track
widths and on the per-width total copper length.  ``B_Cu`` is checked for
structure and extent only -- its plane is a poured region, not strokes, so there
are no widths to compare.

Both Gerber checks print their comparison tables before asserting, so a failure
shows what disagreed rather than only that something did.

A note on the direction of ``y``: KiCad writes Gerber with ``y`` negated relative
to the board file (Gerber's origin is bottom-left, the board file's is top-left
in pcbnew's own convention).  Nothing here "fixes" that -- :func:`read_gerber`
reports what the file says -- but the extent comparison below has to account for
it, and says so where it does.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest

from emfit.gerber import Aperture, Flash, GerberLayer, Segment, read_gerber
from emfit.kicad import load_board

ROOT = Path(__file__).resolve().parents[1]
GERBER = ROOT / "kicad_support_project"
F_CU = GERBER / "gerbers" / "kicad_support_project-F_Cu.gtl"
B_CU = GERBER / "gerbers" / "kicad_support_project-B_Cu.gbl"
BOARD = GERBER / "kicad_support_project.kicad_pcb"

#: Front-copper aperture that carries the 3 mm RF_IN feed taper's widest step.
FEED_WIDTH = 3.0

#: How far a poured plane is expected to sit inside the board outline.  KiCad's
#: default zone clearance to a board edge is 0.5 mm; measured below, not assumed.
POUR_CLEARANCE = 0.5


def _write(tmp_path: Path, name: str, text: str) -> Path:
    """Write a Gerber fragment to ``tmp_path`` and return its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# minimal files, one feature each
# ---------------------------------------------------------------------------
def test_millimetre_draw_and_flash(tmp_path: Path) -> None:
    """A 4.6 mm absolute file with one stroke and one flash of a 0.5 mm circle."""
    layer = read_gerber(
        _write(
            tmp_path,
            "draw.gbr",
            """%FSLAX46Y46*%
%MOMM*%
%ADD10C,0.500000*%
D10*
X0Y0D02*
X1000000Y0D01*
X500000Y500000D03*
M02*
""",
        )
    )

    assert isinstance(layer, GerberLayer)
    assert layer.units == "mm"
    assert (layer.int_digits, layer.dec_digits) == (4, 6)
    assert layer.apertures[10] == Aperture(10, "C", (0.5,))
    assert layer.segments == [Segment(0.0, 0.0, 1.0, 0.0, width=0.5, aperture=10)]
    assert layer.segments[0].length() == pytest.approx(1.0)
    assert layer.flashes == [Flash(0.5, 0.5, 10)]
    assert layer.bbox == (0.0, 0.0, 1.0, 0.5)
    assert layer.regions == []
    assert layer.arcs == 0


def test_inch_unit_factor(tmp_path: Path) -> None:
    """``%MOIN*%`` scales both coordinates and aperture parameters by 25.4."""
    layer = read_gerber(
        _write(
            tmp_path,
            "inch.gbr",
            """%FSLAX46Y46*%
%MOIN*%
%ADD10C,0.020000*%
D10*
X0Y0D02*
X1000000Y0D01*
M02*
""",
        )
    )

    assert layer.units == "in"
    assert layer.segments[0].x1 == pytest.approx(25.4)
    assert layer.segments[0].width == pytest.approx(0.508)
    assert layer.apertures[10].params == (pytest.approx(0.508),)


def test_rectangular_aperture_has_no_scalar_width(tmp_path: Path) -> None:
    """A rectangle has no single stroke width, so ``Segment.width`` is ``None``."""
    layer = read_gerber(
        _write(
            tmp_path,
            "rect.gbr",
            """%FSLAX46Y46*%
%MOMM*%
%ADD12R,1.000000X0.500000*%
D12*
X0Y0D02*
X2000000Y0D01*
M02*
""",
        )
    )

    assert layer.apertures[12] == Aperture(12, "R", (1.0, 0.5))
    assert layer.segments == [Segment(0.0, 0.0, 2.0, 0.0, width=None, aperture=12)]


def test_draw_without_aperture_raises(tmp_path: Path) -> None:
    """A stroke with no aperture selected is refused, not guessed at."""
    path = _write(
        tmp_path,
        "noaperture.gbr",
        """%FSLAX46Y46*%
%MOMM*%
X0Y0D02*
X1000000Y0D01*
M02*
""",
    )

    with pytest.raises(ValueError, match="no aperture selected"):
        read_gerber(path)


def test_draw_with_undefined_aperture_raises(tmp_path: Path) -> None:
    """A stroke naming a code that no ``%ADD`` defines names that code."""
    path = _write(
        tmp_path,
        "undefined.gbr",
        """%FSLAX46Y46*%
%MOMM*%
D11*
X0Y0D02*
X1000000Y0D01*
M02*
""",
    )

    with pytest.raises(ValueError, match="D11"):
        read_gerber(path)


def test_arc_is_counted_not_flattened(tmp_path: Path) -> None:
    """``G02`` increments ``arcs`` and contributes no chord to ``segments``."""
    layer = read_gerber(
        _write(
            tmp_path,
            "arc.gbr",
            """%FSLAX46Y46*%
%MOMM*%
%ADD10C,0.250000*%
D10*
X0Y0D02*
G02X1000000Y0I500000J0D01*
G01*
M02*
""",
        )
    )

    assert layer.arcs == 1
    assert layer.segments == []


# ---------------------------------------------------------------------------
# the coupon, read both ways
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def front() -> GerberLayer:
    """The coupon's front copper, parsed once for the module."""
    return read_gerber(F_CU)


def _width_totals(pairs) -> dict[float, tuple[float, int]]:
    """``{(x0, y0, x1, y1, width)} -> {width: (total length, count)}``."""
    totals: dict[float, list] = defaultdict(lambda: [0.0, 0])
    for x0, y0, x1, y1, width in pairs:
        key = round(width, 6)
        totals[key][0] += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        totals[key][1] += 1
    return {width: (total, count) for width, (total, count) in totals.items()}


@pytest.mark.skipif(not GERBER.exists(), reason="kicad_support_project coupon absent")
def test_front_copper_matches_board_tracks(front: GerberLayer) -> None:
    """The front copper reproduces the board's F.Cu tracks width for width."""
    board = load_board(BOARD)

    print("\n--- front copper apertures (code, shape, params mm) ---")
    for aperture in sorted(front.apertures.values(), key=lambda a: a.code):
        print(f"  D{aperture.code:<3d} {aperture.shape:<6s} {aperture.params}")

    # D11 (C,2.5) is a pad-flash aperture: no board *track* carries it, so the
    # comparison below is over stroked segments, not over every aperture.
    board_totals = _width_totals(
        (track.start[0], track.start[1], track.end[0], track.end[1], track.width)
        for track in board.tracks
        if track.layer == "F.Cu"
    )
    gerber_totals = _width_totals(
        (s.x0, s.y0, s.x1, s.y1, s.width)
        for s in front.segments
        if s.width is not None
    )

    print("--- F.Cu track length per width: board vs gerber (mm) ---")
    print(f"  {'width':>9s} {'board':>10s} {'n':>3s} {'gerber':>10s} {'n':>3s} {'delta':>10s}")
    for width in sorted(set(board_totals) | set(gerber_totals)):
        total_board, count_board = board_totals.get(width, (0.0, 0))
        total_gerber, count_gerber = gerber_totals.get(width, (0.0, 0))
        print(
            f"  {width:9.6f} {total_board:10.6f} {count_board:3d} "
            f"{total_gerber:10.6f} {count_gerber:3d} {total_board - total_gerber:+10.2e}"
        )
    print(
        f"  totals: board {sum(t for t, _ in board_totals.values()):.6f} mm "
        f"over {sum(c for _, c in board_totals.values())} tracks, "
        f"gerber {sum(t for t, _ in gerber_totals.values()):.6f} mm "
        f"over {sum(c for _, c in gerber_totals.values())} strokes"
    )

    assert front.units == "mm"
    assert (front.int_digits, front.dec_digits) == (4, 6)
    assert len(front.segments) == 58
    assert len(front.flashes) == 12
    assert set(gerber_totals) == set(board_totals)
    for width in sorted(board_totals):
        residual = board_totals[width][0] - gerber_totals[width][0]
        assert abs(residual) < 1e-3, f"width {width} mm: residual {residual:+.2e} mm"
    assert any(
        aperture.shape == "C" and aperture.params == (FEED_WIDTH,)
        for aperture in front.apertures.values()
    )


@pytest.mark.skipif(not GERBER.exists(), reason="kicad_support_project coupon absent")
def test_back_copper_parses_and_spans_the_board() -> None:
    """The back copper parses, and its pour sits inside the board outline.

    Its plane is a ``G36`` region with no strokes at all, so -- unlike the front
    -- there is no per-width length to cross-check; the aperture and flash
    numbers are only reported.
    """
    board = load_board(BOARD)
    back = read_gerber(B_CU)

    print("\n--- back copper ---")
    print(f"  format      : {back.units} {back.int_digits}.{back.dec_digits}")
    print(f"  apertures   : {len(back.apertures)}")
    for aperture in sorted(back.apertures.values(), key=lambda a: a.code):
        print(f"    D{aperture.code:<3d} {aperture.shape:<6s} {aperture.params}")
    print(
        f"  flashes     : {len(back.flashes)}  segments: {len(back.segments)}"
        f"  regions: {len(back.regions)}  arcs: {back.arcs}"
        f"  polarity switches: {back.polarity_switches}"
    )
    print(f"  bbox        : {back.bbox}")
    print(f"  board edge  : {board.edge_bbox}")

    assert isinstance(back, GerberLayer)
    assert (back.int_digits, back.dec_digits) == (4, 6)
    assert back.apertures
    assert back.flashes
    # The pour itself: one G36/G37 region per island, no strokes.
    assert back.regions and back.segments == []
    assert back.bbox is not None

    # The board frame is 70 x 20 mm at the origin; the Gerber frame has y
    # negated, so compare |y|.  The pour does NOT reach the outline: it is
    # inset by the zone clearance on all four sides, so the extents agree to
    # that clearance (0.5 mm) and not to a tenth of a millimetre.  What is
    # asserted is that it stays inside the outline and that the inset is the
    # same on all four sides -- i.e. that the pour follows the outline.
    xmin, ymin, xmax, ymax = back.bbox
    edge_xmin, edge_ymin, edge_xmax, edge_ymax = board.edge_bbox
    insets = (
        xmin - edge_xmin,
        edge_xmax - xmax,
        -ymax - edge_ymin,
        edge_ymax - (-ymin),
    )
    print(f"  insets      : {tuple(round(v, 4) for v in insets)} mm")
    assert min(insets) > 0.0, "pour extends beyond the board outline"
    for inset in insets:
        assert inset == pytest.approx(POUR_CLEARANCE, abs=0.01)
