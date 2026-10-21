"""Tests for :mod:`emfit.board`, the one bridge from a KiCad board to a study.

A board file states its geometry in millimetres and a solver state is written in
metres, so exactly one place is allowed to convert: :class:`MicrostripBoard`.
These tests pin that place from both ends.  On the KiCad side, the project's
support coupon is read for real -- a tapering line that has to be refused unless
the caller says which width it means -- and a deliberately small board is built
in a temporary file to pin the degradation: no stackup, so ``h`` comes from
``(general (thickness ...))`` and ``eps_r`` has to come from the caller and be
recorded as such.  On the study side,
:func:`emfit.studies.microstrip_reference_board` is the default cross-section of
:func:`emfit.studies.microstrip_wave` written down as a spec, and
:func:`emfit.studies.microstrip_wave_board` is the only route from that spec into
the solver: it must reproduce the historical ``62 x 44 x 22`` mesh and the
default run's numbers, because the spec adds bookkeeping, not physics.

Every length in the specs asserted here is in metres; every length read out of a
file, and every message quoting one, is in millimetres.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emfit.board import MicrostripBoard, Port
from emfit.kicad import load_board
from emfit.studies import (
    MS_EPS_R,
    microstrip_reference_board,
    microstrip_wave,
    microstrip_wave_board,
)

BOARD_PATH = (Path(__file__).resolve().parent.parent
              / "kicad_support_project" / "kicad_support_project.kicad_pcb")

#: A board with no stackup and one straight strip: 30 x 10 mm of outline, a 1 mm
#: track from 2 mm to ``strip_end`` on the centre line, and a second net that
#: carries no track at all.  ``strip_end = 30`` reaches the far wall; anything
#: less is a coupon the study cannot represent.
SYNTHETIC = """(kicad_pcb (version 20221018) (generator pcbnew)
  (general (thickness 1.6))
  (net 0 "")
  (net 1 "RF")
  (net 2 "SPARE")
  (segment (start 2 5) (end {strip_end} 5) (width 1.0) (layer "F.Cu") (net 1))
  (gr_line (start 0 0) (end 30 0) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 30 0) (end 30 10) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 30 10) (end 0 10) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 0 10) (end 0 0) (layer "Edge.Cuts") (width 0.1))
)
"""


@pytest.fixture(scope="module")
def support():
    """The project's support coupon, parsed once for the whole module."""
    return load_board(BOARD_PATH)


@pytest.fixture()
def synthetic(tmp_path: Path):
    """A parsed board built from :data:`SYNTHETIC`, for a given strip end."""
    def build(strip_end: float = 30):
        path = tmp_path / f"synthetic_{strip_end:g}.kicad_pcb"
        path.write_text(SYNTHETIC.format(strip_end=strip_end), encoding="utf-8")
        return load_board(path)
    return build


# ---------------------------------------------------------------------------
# the reference spec, and the run it pins
# ---------------------------------------------------------------------------
def test_reference_board_is_the_default_mesh() -> None:
    spec = microstrip_reference_board()
    # 62 x 44 cells of 0.4 mm, with the port plane eight node layers in from
    # the xmin wall and the strip running out into the far absorber.
    assert spec.length == pytest.approx(24.8e-3)
    assert spec.width == pytest.approx(17.6e-3)
    assert spec.x_port == pytest.approx(3.2e-3)
    assert spec.x_far == pytest.approx(spec.length)
    assert spec.h == pytest.approx(1.6e-3)
    assert spec.eps_r == pytest.approx(MS_EPS_R)
    assert spec.w == pytest.approx(3.2e-3)
    assert spec.name == "reference"
    assert spec.supplied == ()
    assert spec.w_over_h == pytest.approx(2.0)
    assert spec.clearance == pytest.approx(7.2e-3)

    counts = spec.to_cell_counts(n_sub=4, n_pml=6)
    assert counts == {"n_strip": 8, "n_clean": 12, "n_ref": 2, "n_line": 54,
                      "cell": pytest.approx(0.4e-3)}


def test_reference_board_round_trips_the_default_run_at_short_length() -> None:
    # 300 steps rather than the default 2400: this is about the two routes
    # agreeing, not about the numbers, and a second full-length run would spend
    # the solver budget twice over on the same mesh.  300 is the shortest record
    # that produces a result at all -- at 64 steps the accumulated window is 48
    # steps of a transient still in flight and the impedance fit has no
    # curvature to read, so it raises rather than returning something to
    # compare.  The mesh itself is the same at any length.
    direct = microstrip_wave(nsteps=300)
    via_board = microstrip_wave_board(microstrip_reference_board(), nsteps=300)

    assert via_board.geometry == direct.geometry
    assert via_board.geometry["nsteps"] == 300
    assert np.array_equal(via_board.station_x, direct.station_x)
    assert np.array_equal(via_board.v_stations, direct.v_stations, equal_nan=True)
    assert np.array_equal(via_board.i_stations, direct.i_stations, equal_nan=True)
    assert via_board.beta == direct.beta
    assert via_board.gamma == direct.gamma
    assert via_board.z0 == direct.z0
    assert via_board.eps_eff == direct.eps_eff
    assert via_board.s21 == direct.s21


# ---------------------------------------------------------------------------
# reading a real coupon
# ---------------------------------------------------------------------------
def test_from_kicad_reads_the_support_board(support) -> None:
    # The net is a taper: 27 widths from 0.64 mm up to 3.0 mm and back down, so
    # the uniform run has to be asked for.  The 3.0 mm width covers 8.65-32.22 mm
    # (two abutting segments, 23.57 mm together), which is the strip; the taper
    # either side of it is not part of the line this model can represent.
    spec = MicrostripBoard.from_kicad(support, net="RF_IN", taper="dominant")

    assert spec.name == "RF_IN"
    assert spec.length == pytest.approx(70e-3)
    assert spec.width == pytest.approx(20e-3)
    assert spec.h == pytest.approx(1.6e-3)
    assert spec.eps_r == pytest.approx(4.4)
    assert spec.w == pytest.approx(3.0e-3)
    assert spec.x_port == pytest.approx(8.65e-3)
    assert spec.x_far == pytest.approx(32.22e-3)
    assert spec.clearance == pytest.approx(8.5e-3)
    # Everything came out of the file: the stackup carries both the thickness
    # and the permittivity, so nothing was supplied by the caller.
    assert spec.supplied == ()


def test_from_kicad_raises_on_a_taper(support) -> None:
    with pytest.raises(ValueError, match="distinct track widths"):
        MicrostripBoard.from_kicad(support, net="RF_IN")
    with pytest.raises(ValueError, match="taper must be"):
        MicrostripBoard.from_kicad(support, net="RF_IN", taper="widest")


# ---------------------------------------------------------------------------
# a board with no stackup
# ---------------------------------------------------------------------------
def test_from_kicad_reads_a_board_without_a_stackup(synthetic) -> None:
    board = synthetic()
    assert board.stackup == [] and board.stackup_thickness() is None

    spec = MicrostripBoard.from_kicad(board, net="RF", eps_r=4.2)

    assert spec.length == pytest.approx(30e-3)
    assert spec.width == pytest.approx(10e-3)
    assert spec.w == pytest.approx(1.0e-3)
    assert spec.x_port == pytest.approx(2e-3)
    assert spec.x_far == pytest.approx(30e-3)
    # Thickness fell back to (general (thickness 1.6)); the permittivity had to
    # be given, and saying so is the point of ``supplied``.
    assert spec.h == pytest.approx(1.6e-3)
    assert spec.eps_r == pytest.approx(4.2)
    assert spec.supplied == ("eps_r",)


def test_from_kicad_requires_an_eps_r(synthetic) -> None:
    with pytest.raises(ValueError, match="eps_r"):
        MicrostripBoard.from_kicad(synthetic(), net="RF")
    # A net with no track is not a coupon either: pads and zones are not a strip.
    with pytest.raises(ValueError, match="carries no track segments"):
        MicrostripBoard.from_kicad(synthetic(), net="SPARE", eps_r=4.2)


# ---------------------------------------------------------------------------
# to the mesh, where the geometry has to be representable
# ---------------------------------------------------------------------------
def test_to_cell_counts_refuses_what_the_mesh_cannot_hold(synthetic, support) -> None:
    short = MicrostripBoard.from_kicad(synthetic(strip_end=20), net="RF", eps_r=4.2)
    with pytest.raises(ValueError, match="far absorber at the x wall"):
        short.to_cell_counts(n_sub=4, n_pml=6)

    # The support coupon is a shorter line inside a 70 mm outline, so it is the
    # same refusal: the far end of the net is not the wall of the board.
    tapered = MicrostripBoard.from_kicad(support, net="RF_IN", taper="dominant")
    with pytest.raises(ValueError, match="far absorber at the x wall"):
        tapered.to_cell_counts(n_sub=4, n_pml=6)

    # 0.4 mm cells are what the reference spec was written for; at 1.6/3 the
    # clearance is half a cell out, and the message says which n_sub would fit.
    with pytest.raises(ValueError, match="n_sub = 2, 4, 6"):
        microstrip_reference_board().to_cell_counts(n_sub=3, n_pml=6)


# ---------------------------------------------------------------------------
# the one full-length run
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_the_board_path_reaches_the_default_run() -> None:
    result = microstrip_wave_board(microstrip_reference_board())
    g = result.geometry

    # The default cross-section, cell for cell: this is what "the spec adds
    # bookkeeping, not physics" means.
    assert (g["nx"], g["ny"], g["nz"]) == (62, 44, 22)
    assert g["cell"] == pytest.approx(0.4e-3)
    assert (g["n_strip"], g["n_clean"], g["n_ref"], g["n_line"]) == (8, 12, 2, 54)
    assert g["ix_port"] == 8
    assert g["nsteps"] == 2400

    # And the settled diagnostics the docstring quotes for the default run.
    assert result.beta == pytest.approx(232.45, rel=0.01)
    assert abs(result.gamma) < 0.02
    assert result.fit_residual < 0.05
    assert 1.0 < result.eps_eff < MS_EPS_R


# ---------------------------------------------------------------------------
# a port on a named pad
# ---------------------------------------------------------------------------
def test_from_kicad_places_the_port_on_the_connector_pad(support) -> None:
    """Reading the port off J1.1 puts the port plane at the start of the strip.

    Kills a port that decides the width: the copper under the connector is a
    2.0 mm launch over 4.15 mm of fan-out, and the line it launches onto is the
    3.0 mm run that begins 4.15 mm further on.  Pins the coupon's published
    numbers so they cannot drift.
    """
    spec = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1"))

    assert spec.w == pytest.approx(0.003)
    assert spec.x_port == pytest.approx(0.00865)
    assert spec.x_far == pytest.approx(0.03222)
    assert spec.length == pytest.approx(0.07)
    assert spec.width == pytest.approx(0.02)
    assert spec.h == pytest.approx(0.0016)
    assert spec.eps_r == pytest.approx(4.4)

    assert spec.port is not None
    assert spec.port.side == "front"
    assert spec.port.y == pytest.approx(0.01)
    assert spec.port.net == "RF_IN"
    assert spec.port.reference == "J1"
    assert spec.port.number == "1"
    assert spec.port.position == pytest.approx(0.00865)
    assert spec.port.position == spec.x_port

    # The pad chose the launch and nothing else, so the same net reads the same
    # line without it: the port comes from the extreme x of the run that carries
    # the dominant width.
    whole = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, taper="dominant")
    assert whole.w == pytest.approx(0.003)
    assert whole.x_port == pytest.approx(0.00865)
    assert whole.x_far == pytest.approx(0.03222)
    assert whole.port is None

    # A port says where the *launch* is; it says nothing about where the board
    # ends.  x_far is 32.22 mm inside a 70 mm outline, so the mesh still refuses
    # the line -- this exists so that a port cannot be read as a fix for that.
    with pytest.raises(ValueError, match="32.220000") as caught:
        spec.to_cell_counts(n_sub=8, n_pml=12)
    assert "70.000000" in str(caught.value)


def test_from_kicad_refuses_a_port_pad_on_another_net(support) -> None:
    """A pad on RF_OUT cannot launch an RF_IN line.

    Kills matching the pad by reference and number only, which would port the
    wrong end of the coupon.
    """
    with pytest.raises(ValueError, match="RF_IN") as caught:
        MicrostripBoard.from_kicad(
            support, net="RF_IN", eps_r=4.4, port_pad=("R1", "2"))

    assert "RF_OUT" in str(caught.value)


def test_from_kicad_refuses_a_port_on_the_far_end(support) -> None:
    """J2.1 sits at the down-stream end, so the line would have to run backwards.

    Kills an empty line (x_far == x_port) or a negative one, instead of saying
    that the model runs from the port towards the far wall.
    """
    with pytest.raises(ValueError, match="65.500000") as caught:
        MicrostripBoard.from_kicad(
            support, net="RF_OUT", eps_r=4.4, port_pad=("J2", "1"))

    assert "63.000000" in str(caught.value)


def test_port_validates_its_own_numbers() -> None:
    """A port carries metres, a net and a side, and refuses the rest.

    Kills a frozen dataclass that accepts a zero position, an unnamed net or an
    invented side.
    """
    with pytest.raises(ValueError, match="all lengths are metres"):
        Port(position=0.0, y=0.0, net="x", reference="J1", number="1",
             side="front")
    with pytest.raises(ValueError, match="net must be"):
        Port(position=1e-3, y=0.0, net="", reference="J1", number="1",
             side="front")
    with pytest.raises(ValueError, match="side must be"):
        Port(position=1e-3, y=0.0, net="x", reference="J1", number="1",
             side="left")


# ---------------------------------------------------------------------------
# cropping the outline to the line
# ---------------------------------------------------------------------------
def test_cropped_to_strip_lands_the_far_plane_on_the_wall(support) -> None:
    """The crop moves the far wall to the strip and leaves the line alone.

    Kills a crop that rescales the geometry -- changing the box must not change
    the strip -- and kills a ``length`` that is quietly replaced without being
    declared: after the call that number is the caller's, not the outline's.
    """
    whole = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1"))
    assert whole.length == pytest.approx(0.07)
    assert "length" not in whole.supplied

    cropped = whole.cropped_to_strip()

    assert cropped.length == pytest.approx(0.03222)
    assert cropped.length == pytest.approx(cropped.x_far)
    assert cropped.supplied == ("eps_r", "length")

    # The line is the same line: only the box was cropped.
    assert cropped.w == pytest.approx(whole.w) == pytest.approx(0.003)
    assert cropped.x_port == pytest.approx(whole.x_port) == pytest.approx(0.00865)
    assert cropped.x_far == pytest.approx(whole.x_far) == pytest.approx(0.03222)
    assert cropped.width == pytest.approx(0.02)
    assert cropped.h == pytest.approx(0.0016)
    assert cropped.eps_r == pytest.approx(4.4)
    assert cropped.name == whole.name
    assert cropped.loads == whole.loads
    assert cropped.port == whole.port
    assert cropped.port is not None
    assert cropped.port.reference == "J1"
    assert cropped.port.position == pytest.approx(0.00865)


def test_cropped_to_strip_is_idempotent_and_declares_only_what_it_did(
        support) -> None:
    """Cropping a crop changes nothing, and a spec already ending at its far
    wall is not told it supplied a length.

    Kills a second crop that appends ``'length'`` again or drifts the geometry,
    and kills a declaration that fires when nothing was supplied: there
    ``supplied`` has to be the identical tuple.
    """
    whole = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1"))
    once = whole.cropped_to_strip()
    twice = once.cropped_to_strip()

    assert twice == once
    assert twice.supplied == once.supplied
    assert twice.supplied.count("length") == 1

    # The plain dominant spec is the same line in the same box, so the same crop
    # lands on the same wall: the pad had chosen the launch, not the geometry.
    dominant = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, taper="dominant")
    assert dominant.x_far == pytest.approx(0.03222)
    assert dominant.length == pytest.approx(0.07)
    assert dominant.cropped_to_strip().length == pytest.approx(0.03222)
    assert dominant.cropped_to_strip().x_port == pytest.approx(0.00865)

    # Written directly, already ending at its own far wall: the crop supplied
    # nothing, so it may declare nothing.
    already = MicrostripBoard(length=0.03, width=0.02, h=0.0016, eps_r=4.4,
                              w=0.003, x_port=0.00865, x_far=0.03)
    assert already.supplied == ()
    assert already.cropped_to_strip().supplied == already.supplied
    assert already.cropped_to_strip().length == pytest.approx(already.length)


def test_the_cropped_port_coupon_meshes_at_sixteen_substrate_cells(support) -> None:
    """The cropped 3.0 mm coupon, snapped and then meshed by the real method.

    Kills trusting the arithmetic instead of running it: the snap lands the far
    plane on the wall, which is the condition ``to_cell_counts`` checks first,
    so 0.1 mm cells hold 30 strip cells, 73 clean cells, 75 cells of port plane
    and a 235-cell line.  It does not relax the mesh, though -- the coarse 0.2 mm
    snap leaves the clearance at 30.5 cells, so the cropped coupon refuses
    exactly as the uncropped one did.
    """
    cropped = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1")
    ).cropped_to_strip(n_sub=16)

    assert cropped.to_cell_counts(n_sub=16, n_pml=12) == {
        "n_strip": 30, "n_clean": 73, "n_ref": 75, "n_line": 235,
        "cell": pytest.approx(0.0001)}

    with pytest.raises(
            ValueError,
            match="n_clean = 8.500000 mm / 0.200000 mm") as caught:
        MicrostripBoard.from_kicad(
            support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1")
        ).cropped_to_strip(n_sub=8).to_cell_counts(n_sub=8, n_pml=12)
    assert "n_clean = 8.500000 mm / 0.200000 mm - 12 = 30.500000 cells" \
        in str(caught.value)
    assert "n_sub = 16, 32 would fit every dimension" in str(caught.value)


def test_even_the_cropped_dominant_coupon_needs_a_finer_mesh(support) -> None:
    """23.57 mm of line over a 1.6 mm substrate does not divide at 32 cells.

    Kills reading the crop as a fix for the mesh: the far plane is on the wall
    now, but ``n_line`` is ``0.02357 * n_sub / 0.0016`` -- 2357 * n_sub / 160 --
    so a whole number of cells is only reached when 160 divides ``n_sub``.  The
    first fit is therefore a 0.01 mm mesh: 300 strip cells, 838 clean, 853 of
    port plane and 2357 of line.
    """
    cropped = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, taper="dominant").cropped_to_strip()

    with pytest.raises(
            ValueError,
            match="no n_sub in 1..32 fits every dimension") as caught:
        cropped.to_cell_counts(n_sub=32, n_pml=12)
    assert "n_line = 23.570000 mm / 0.050000 mm = 471.400000 cells" \
        in str(caught.value)

    # Worked out here rather than quoted from the message: every dimension has
    # to be a whole number of cells, and 160 is the first ``n_sub`` that is.
    dims = (("n_strip", cropped.w, 0),
            ("n_clean", cropped.clearance, 12),
            ("n_ref", cropped.x_port, 12),
            ("n_line", cropped.x_far - cropped.x_port, 0))
    fits = [n_sub for n_sub in range(1, 201)
            if all(abs(run / (cropped.h / n_sub) - cut
                       - round(run / (cropped.h / n_sub) - cut)) <= 1e-9
                   for _, run, cut in dims)]
    assert fits[0] == 160

    counts = cropped.to_cell_counts(n_sub=160, n_pml=12)
    assert counts["cell"] == pytest.approx(1e-5)
    assert (counts["n_strip"], counts["n_clean"], counts["n_ref"],
            counts["n_line"]) == (300, 838, 853, 2357)


# ---------------------------------------------------------------------------
# what the port pad does, and what snapping the planes to a mesh does
def test_the_port_pad_chooses_the_launch_not_the_width(support) -> None:
    """The pad moves the port plane to the end of the run it is nearest.

    Kills a port that reads its width off the copper under the pad: on this
    coupon that is a 2.0 mm launch, and the line it launches onto is 3.0 mm.
    Also kills a port that made ``taper`` matter, now that the width no longer
    depends on where the pad is.
    """
    plain = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, taper="dominant")

    for mode in ("raise", "dominant"):
        spec = MicrostripBoard.from_kicad(
            support, net="RF_IN", eps_r=4.4, taper=mode, port_pad=("J1", "1"))
        assert spec.w == pytest.approx(plain.w) == pytest.approx(0.003)
        assert spec.x_port == pytest.approx(plain.x_port) == pytest.approx(0.00865)
        assert spec.x_far == pytest.approx(plain.x_far) == pytest.approx(0.03222)
        assert spec.length == pytest.approx(0.07)
        # Nothing about the line was supplied: the file carries all of it.
        assert spec.supplied == ("eps_r",)
        assert spec.port is not None
        assert spec.port.position == spec.x_port
        # The pad is at 4.5 mm; the plane it launches on is at 8.65 mm.
        assert spec.port.y == pytest.approx(0.01)


def test_cropped_to_strip_at_sixteen_cells_snaps_inward(support) -> None:
    """0.1 mm cells move the port forward and the far plane back, never out.

    Kills an outward snap, which would model copper the board does not have, and
    a snap that moves the planes without declaring them: after the call those
    numbers are the caller's, not the file's.
    """
    raw = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1"))
    snapped = raw.cropped_to_strip(n_sub=16)

    cell = snapped.h / 16
    assert cell == pytest.approx(1e-4)
    assert snapped.x_port == pytest.approx(0.0087)
    assert snapped.x_far == pytest.approx(0.0322)
    assert snapped.length == pytest.approx(0.0322)
    assert snapped.x_far - snapped.x_port == pytest.approx(0.0235)
    assert snapped.supplied == ("eps_r", "length", "x_far", "x_port")

    # The port plane moved with the copper, so the port still describes the
    # plane the study drives.
    assert snapped.port is not None
    assert snapped.port.position == snapped.x_port
    assert snapped.port.reference == raw.port.reference

    # Every one of those three numbers is a whole number of cells, and so is the
    # span between the planes.
    for value in (snapped.x_port, snapped.x_far, snapped.x_far - snapped.x_port):
        assert value / cell == pytest.approx(round(value / cell), abs=1e-9)

    # Everything else is still the board's.
    assert snapped.w == pytest.approx(raw.w)
    assert snapped.width == pytest.approx(raw.width)
    assert snapped.h == pytest.approx(raw.h)
    assert snapped.eps_r == pytest.approx(raw.eps_r)
    assert snapped.name == raw.name

    # Cropping a snap is not a change.
    assert snapped.cropped_to_strip(n_sub=16) == snapped


def test_cropped_to_strip_without_a_mesh_leaves_the_planes_alone(support) -> None:
    """No ``n_sub``, no snapping: the box moves and the two planes do not.

    Kills a default snap, which would silently move the port plane of every
    caller that only meant to shorten the outline -- and would then have to
    declare a ``x_port`` nobody asked it to touch.
    """
    raw = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1"))
    cropped = raw.cropped_to_strip()

    assert cropped.x_port == raw.x_port
    assert cropped.x_far == raw.x_far
    assert cropped.port == raw.port
    assert cropped.supplied == ("eps_r", "length")
    assert cropped != raw
    assert cropped.length == pytest.approx(raw.x_far) == pytest.approx(0.03222)

    # Which is why the plain crop still does not mesh: the port plane is 86.5
    # cells and the line 235.7 at 0.1 mm, and only the snap fixes that.
    with pytest.raises(
            ValueError, match="n_ref = 8.650000 mm / 0.100000 mm") as caught:
        cropped.to_cell_counts(n_sub=16, n_pml=12)
    assert "n_line = 23.570000 mm / 0.100000 mm = 235.700000 cells" \
        in str(caught.value)


def test_the_snapped_span_stays_inside_the_copper(support) -> None:
    """Every mesh, coarse or fine, snaps inward from the copper it was given.

    Kills a snap to the *nearest* boundary, which at a coarse mesh would push
    the port plane behind the pad or the far plane past the end of the track --
    the study would then drive a strip the board does not have.
    """
    raw = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1"))

    for n_sub in (2, 4, 8, 16, 20, 32, 64):
        snapped = raw.cropped_to_strip(n_sub=n_sub)
        assert snapped.x_port >= raw.x_port
        assert snapped.x_far <= raw.x_far
        assert snapped.x_far > snapped.x_port
        assert snapped.length == snapped.x_far

        cell = snapped.h / n_sub
        for value in (snapped.x_port, snapped.x_far):
            assert value / cell == pytest.approx(round(value / cell), abs=1e-9)

