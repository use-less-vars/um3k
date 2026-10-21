"""Tests for ``reference_box.kicad_pcb``, the published mesh written as a board.

The microstrip results are quoted on a box of ``66 x 52 x 26`` cells of
``0.400 mm`` -- a ``1.6 mm``, ``eps_r = 4.4`` substrate, a ``3.20 mm`` strip and
a ten-cell matched layer on every absorbing face.  Those integers are what the
file exists to carry, so these tests do not restate the generator's constants:
they read the board back through :func:`emfit.kicad.load_board` and
:meth:`emfit.board.MicrostripBoard.from_kicad`, turn the geometry into cell
counts with :meth:`MicrostripBoard.to_cell_counts`, and only then compare against
``66 x 52 x 26``.  A board that drifted by one cell, or that grew a default
``eps_r``, would fail here and not in a paragraph.

Two things are pinned besides the arithmetic.  Nothing in the spec may be
*supplied*: the substrate thickness comes from the stackup and the permittivity
from the core, so ``supplied`` has to be empty -- otherwise the study would be
running on a number the caller gave rather than one the board states.  And the
file on disk has to be the text the generator writes, because a hand-edited
board is a specification nobody regenerates.

Every length in a spec is in metres; every length read out of the file, and every
message quoting one, is in millimetres.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from emfit.board import MicrostripBoard
from emfit.kicad import load_board
from emfit.studies import MS_N_AIR

#: The generator, and the board it writes -- the module states both, and the
#: tests use its statement rather than a second copy of the path.
GENERATOR = (Path(__file__).resolve().parent.parent
             / "kicad_support_project" / "generate_reference_box.py")


def _import_generator():
    """Load ``generate_reference_box.py`` from its path (it is not a package)."""
    spec = importlib.util.spec_from_file_location("generate_reference_box",
                                                  GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATE = _import_generator()
PCB_PATH = Path(GENERATE.HERE) / GENERATE.PCB_NAME
NET = "RF_IN"

#: The published box, and the mesh parameters that have to produce it.
N_SUB = 4      # substrate cells across h: cell = 1.6 mm / 4 = 0.400 mm
N_PML = 10     # matched-layer cells against every absorbing face
PUBLISHED = (66, 52, 26)


@pytest.fixture(scope="module")
def board():
    """The reference board, parsed once for the whole module."""
    assert PCB_PATH.exists(), f"{PCB_PATH} is missing: run {GENERATOR.name}"
    return load_board(PCB_PATH)


@pytest.fixture(scope="module")
def spec(board) -> MicrostripBoard:
    """The board's spec, read the way a study would read it."""
    return MicrostripBoard.from_kicad(board, net=NET)


# ---------------------------------------------------------------------------
# the file, and what it says about itself
# ---------------------------------------------------------------------------
def test_the_file_on_disk_is_what_the_generator_writes() -> None:
    assert PCB_PATH.exists(), f"{PCB_PATH} is missing: run {GENERATOR.name}"
    assert PCB_PATH.read_text(encoding="utf-8") == GENERATE.board_text(), (
        f"{PCB_PATH.name} differs from {GENERATOR.name}'s output: regenerate it "
        f"instead of editing the board, or the file states a mesh nothing "
        f"reproduces")


def test_the_substrate_comes_from_the_board_and_not_from_the_caller(
        board, spec: MicrostripBoard) -> None:
    assert spec.supplied == (), (
        "every number in the spec has to come from the file: 'supplied' names "
        "the ones the caller gave, and this board gives them all")
    assert spec.h == pytest.approx(1.6e-3)
    assert spec.h == pytest.approx(board.stackup_thickness() * 1e-3)
    assert spec.eps_r == pytest.approx(4.4)
    core = [entry for entry in board.stackup if entry.kind == "core"]
    assert [entry.epsilon_r for entry in core] == [pytest.approx(4.4)]


def test_the_outline_and_the_strip_are_the_mesh_geometry(
        spec: MicrostripBoard) -> None:
    # 66 cells of 0.4 mm along the line, 52 across it; 8 cells of strip, so
    # (20.8 - 3.2) / 2 = 8.8 mm of metal-free board each side.
    assert spec.length == pytest.approx(26.4e-3)
    assert spec.width == pytest.approx(20.8e-3)
    assert spec.w == pytest.approx(3.2e-3)
    assert spec.w_over_h == pytest.approx(2.0)
    assert spec.clearance == pytest.approx(8.8e-3)
    # 10 + 2 cells in from the xmin edge, then 54 cells to the far wall, which
    # is where the study terminates the line in its absorber.
    assert spec.x_port == pytest.approx(4.8e-3)
    assert spec.x_far == pytest.approx(26.4e-3)
    assert spec.x_far == pytest.approx(spec.length)
    assert spec.name == NET
    assert spec.loads == ()
    assert spec.port is None


def test_the_strip_is_one_segment_on_the_centre_line(board) -> None:
    assert len(board.tracks) == 1, "the reference box carries one run of line"
    track = board.tracks[0]
    assert board.net_name(track.net) == NET
    assert track.width == pytest.approx(3.2)
    assert track.start[1] == pytest.approx(10.4)
    assert track.end[1] == pytest.approx(10.4)
    assert sorted((track.start[0], track.end[0])) == [pytest.approx(4.8),
                                                      pytest.approx(26.4)]


def test_the_board_is_a_statement_of_the_mesh_and_not_a_coupon(board) -> None:
    assert [pad for pad in board.pads_in_board_frame()] == []
    assert board.footprints == []
    assert board.zones == []


# ---------------------------------------------------------------------------
# the counts
# ---------------------------------------------------------------------------
def test_the_counts_are_the_published_box(spec: MicrostripBoard) -> None:
    counts = spec.to_cell_counts(n_sub=N_SUB, n_pml=N_PML)
    assert counts == {"n_strip": 8, "n_clean": 12, "n_ref": 2, "n_line": 54,
                      "cell": pytest.approx(0.4e-3)}
    nx = N_PML + counts["n_ref"] + counts["n_line"]
    ny = 2 * N_PML + counts["n_strip"] + 2 * counts["n_clean"]
    # nz = n_sub + n_air + n_top, and one PML carries one thickness, so the lid
    # is the lateral ten cells and the air column is the study's own default.
    nz = N_SUB + MS_N_AIR + N_PML
    assert (nx, ny, nz) == PUBLISHED
