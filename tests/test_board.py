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
    """Reading the port off J1.1 shortens the line to the 2.0 mm run at 4.5 mm.

    Kills taking the dominant 3.0 mm width, and pins the coupon's published
    numbers so they cannot drift.
    """
    spec = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, port_pad=("J1", "1"))

    assert spec.w == pytest.approx(0.002)
    assert spec.x_port == pytest.approx(0.0045)
    assert spec.x_far == pytest.approx(0.007)
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

    # Without the port pad the same net reads exactly as it did before: the port
    # comes from the extreme x of the run that carries the dominant width.
    whole = MicrostripBoard.from_kicad(
        support, net="RF_IN", eps_r=4.4, taper="dominant")
    assert whole.w == pytest.approx(0.003)
    assert whole.x_port == pytest.approx(0.00865)
    assert whole.x_far == pytest.approx(0.03222)
    assert whole.port is None

    # A port says where the *launch* is; it says nothing about where the board
    # ends.  x_far is 7.0 mm inside a 70 mm outline, so the mesh still refuses
    # the line -- this exists so that a port cannot be read as a fix for that.
    with pytest.raises(ValueError, match="7.000000") as caught:
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
