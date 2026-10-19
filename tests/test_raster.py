"""Tests for :mod:`emfit.raster` -- board stackup -> FIT metric and materials.

Two boards are used:

* ``CMEX.kicad_pcb``, the real 8-layer coupon in the repository root, loaded
  exactly the way :mod:`tests.test_kicad` loads it; and
* a synthetic 4-copper-layer board written into ``tmp_path``, so the stackup
  arithmetic can also be checked against numbers small enough to verify by
  hand, and so the ``cells_per_dielectric`` behaviour can be exercised in a
  regime that the real board does not cover.

Convention reminder: everything ``emfit.raster`` returns is in **metres**, while
:class:`emfit.kicad.Board` is in millimetres.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from emfit.evolve import cfl_dt
from emfit.grid import Grid
from emfit.kicad import load_board
from emfit.materials import C0, material_matrices
from emfit.operators import CellComplex
from emfit.raster import (
    AIR_GRADING,
    MM,
    Coupon,
    CouponInfo,
    build,
    build_grid,
    dielectric_intervals,
    epsilon_callable,
    layer_z_positions,
)

BOARD_PATH = Path(__file__).resolve().parent.parent / "CMEX.kicad_pcb"

CMEX_REGION = (164.15, 76.15, 259.475, 166.35)   # mm, == board.edge_bbox
CMEX_COPPER = ["B.Cu", "In6.Cu", "In5.Cu", "In4.Cu", "In3.Cu", "In2.Cu", "In1.Cu", "F.Cu"]
CMEX_LAYER_Z = {                                 # m, above the board's bottom face
    "B.Cu": 2.75e-5,
    "In6.Cu": 1.625e-4,
    "In5.Cu": 4.975e-4,
    "In4.Cu": 6.325e-4,
    "In3.Cu": 9.675e-4,
    "In2.Cu": 1.1025e-3,
    "In1.Cu": 1.4375e-3,
    "F.Cu": 1.5725e-3,
}
# the outer 10 um soldermask + half of the 35 um foil, on each side
OUTER_BAND = 0.0275 * MM


# ---------------------------------------------------------------------------
# the synthetic board
# ---------------------------------------------------------------------------
def _board_text(dielectrics) -> str:
    """A literal KiCad board: 4 copper layers, one dielectric per gap.

    ``dielectrics`` is a sequence of ``(kind, thickness_mm, epsilon_r)`` in
    file order (top to bottom).  Soldermask is 10 um and copper 35 um, as in
    the real board.
    """
    total = 2 * 0.01 + 4 * 0.035 + sum(t for _, t, _ in dielectrics)
    lines = [
        "(kicad_pcb (version 20221018) (generator pcbnew)",
        f"  (general (thickness {total}))",
        "  (layers",
        '    (0 "F.Cu" signal)',
        '    (1 "In1.Cu" signal)',
        '    (2 "In2.Cu" signal)',
        '    (31 "B.Cu" signal)',
        "  )",
        "  (setup",
        "    (stackup",
        '      (layer "F.SilkS" (type "Top Silk Screen"))',
        '      (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))',
        '      (layer "F.Cu" (type "copper") (thickness 0.035))',
    ]
    for index, (kind, thickness_mm, eps_r) in enumerate(dielectrics):
        lines.append(
            f'      (layer "dielectric {index + 1}" (type "{kind}") '
            f'(thickness {thickness_mm}) (material "FR4") '
            f"(epsilon_r {eps_r}) (loss_tangent 0.02))"
        )
        lines.append(f'      (layer "{("In1.Cu", "In2.Cu", "B.Cu")[index]}" '
                     f'(type "copper") (thickness 0.035))')
    lines += [
        '      (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))',
        '      (layer "B.SilkS" (type "Bottom Silk Screen"))',
        "    )",
        "  )",
        ")",
    ]
    return "\n".join(lines) + "\n"


THIN_STACKUP = [("prepreg", 0.2, 4.2), ("core", 0.8, 4.4), ("prepreg", 0.2, 4.2)]
THIN_THICKNESS = 2 * 0.01 + 4 * 0.035 + 0.2 + 0.8 + 0.2          # 1.36 mm
THIN_COPPER = ["B.Cu", "In2.Cu", "In1.Cu", "F.Cu"]
THIN_LAYER_Z = {                                                  # m
    "B.Cu": 0.0275 * MM,
    "In2.Cu": 0.2625 * MM,
    "In1.Cu": 1.0975 * MM,
    "F.Cu": 1.3325 * MM,
}

# dielectrics thick compared with the lateral step, so the CFL limit stays
# lateral-limited however many cells the slab is split into
THICK_STACKUP = [("core", 2.0, 4.0), ("core", 3.0, 4.0), ("core", 2.0, 4.0)]
THICK_THICKNESS = 2 * 0.01 + 4 * 0.035 + 2.0 + 3.0 + 2.0          # 7.16 mm


def _write_board(tmp_path, name, dielectrics):
    path = tmp_path / name
    path.write_text(_board_text(dielectrics), encoding="utf-8")
    return str(path)


@pytest.fixture
def thin_board(tmp_path):
    return load_board(_write_board(tmp_path, "thin.kicad_pcb", THIN_STACKUP))


@pytest.fixture
def thick_board(tmp_path):
    return load_board(_write_board(tmp_path, "thick.kicad_pcb", THICK_STACKUP))


# ---------------------------------------------------------------------------
# the real board
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def board():
    if not BOARD_PATH.exists():
        pytest.skip(f"missing {BOARD_PATH}")
    return load_board(str(BOARD_PATH))


@pytest.fixture(scope="module")
def coupon(board) -> Coupon:
    """The reference CMEX coupon: 1 mm lateral step, 2 cells per dielectric."""
    return build(board, CMEX_REGION, 1.0e-3)


def _cfl(grid: Grid) -> float:
    """``emfit.evolve.cfl_dt`` written out, so the step is checked twice."""
    inverse = sum(1.0 / grid.widths(("x", "y", "z")[axis]).min() ** 2 for axis in (0, 1, 2))
    return 0.99 / (C0 * np.sqrt(inverse))


# ---------------------------------------------------------------------------
# stackup arithmetic -- synthetic board
# ---------------------------------------------------------------------------
def test_layer_z_positions_from_thin_board(thin_board):
    z = layer_z_positions(thin_board)
    assert list(z) == THIN_COPPER               # bottom-up, ascending
    for name, expected in THIN_LAYER_Z.items():
        assert z[name] == pytest.approx(expected, abs=1e-15)
    assert np.all(np.diff(list(z.values())) > 0.0)


def test_dielectric_intervals_from_thin_board(thin_board):
    intervals = dielectric_intervals(thin_board)
    assert len(intervals) == 3
    assert [round(eps, 12) for _, _, eps in intervals] == [4.2, 4.4, 4.2]
    for (z0, z1, _), (z_low, z_high) in zip(
        intervals, [(THIN_LAYER_Z["B.Cu"], THIN_LAYER_Z["In2.Cu"]),
                    (THIN_LAYER_Z["In2.Cu"], THIN_LAYER_Z["In1.Cu"]),
                    (THIN_LAYER_Z["In1.Cu"], THIN_LAYER_Z["F.Cu"])]
    ):
        assert z0 == pytest.approx(z_low, abs=1e-15)
        assert z1 == pytest.approx(z_high, abs=1e-15)
    # the slabs span copper mid-plane to copper mid-plane, so the copper
    # thicknesses and the two soldermask layers are *not* part of the sum
    span = THIN_LAYER_Z["F.Cu"] - THIN_LAYER_Z["B.Cu"]
    assert sum(z1 - z0 for z0, z1, _ in intervals) == pytest.approx(span, abs=1e-15)
    assert THIN_THICKNESS * MM == pytest.approx(span + 2 * OUTER_BAND, abs=1e-15)


def test_epsilon_callable_probes_and_shape(thin_board):
    eps = epsilon_callable(thin_board)
    # the layer heights as the module computes them: a literal 0.0275*MM is one
    # ulp away from the stackup sum and would fall just outside the slab
    z = layer_z_positions(thin_board)
    assert eps(0.0, 0.0, 0.1e-3) == pytest.approx(4.2)      # first slab
    assert eps(0.0, 0.0, 0.6e-3) == pytest.approx(4.4)      # middle slab
    assert eps(0.0, 0.0, 1.2e-3) == pytest.approx(4.2)      # last slab
    assert eps(0.0, 0.0, -1.0e-3) == pytest.approx(1.0)     # below the board
    # above the *top copper mid-plane* is vacuum: the 10 um soldermask band is
    # deliberately not meshed, so the vacuum starts at the copper, not at the
    # declared board face
    # (1.33 mm is still 2.5 um *below* the mid-plane, hence dielectric)
    assert eps(0.0, 0.0, 1.33e-3) == pytest.approx(4.2)
    for above in (z["F.Cu"], 1.34e-3, 1.5e-3, 2.0e-3):
        assert eps(0.0, 0.0, above) == pytest.approx(1.0)
    # a point exactly on a copper mid-plane takes the dielectric above it --
    # except at the top of the stack, where "above" is the air box
    assert eps(0.0, 0.0, z["B.Cu"]) == pytest.approx(4.2)
    assert eps(0.0, 0.0, z["In2.Cu"]) == pytest.approx(4.4)
    assert eps(0.0, 0.0, z["F.Cu"]) == pytest.approx(1.0)

    # vectorised and shape-preserving on a 2-D mesh
    xs = np.linspace(-2.0e-3, 2.0e-3, 7)
    zs = np.linspace(-1.0e-3, 2.0e-3, 5)
    xx, zz = np.meshgrid(xs, zs, indexing="ij")
    values = eps(xx, 0.5 * MM, zz)
    assert values.shape == xx.shape
    assert np.all(np.isfinite(values))
    assert set(np.unique(values)) == {1.0, 4.2, 4.4}


def test_air_boxes_sum_to_their_budget(thin_board):
    grid = build_grid(
        thin_board,
        (0.0, 0.0, 4.0, 4.0),
        1.0e-3,
        cells_per_dielectric=2,
        air_above=1.2e-3,
        air_below=0.6e-3,
        air_cells=3,
    )
    z = grid.z
    bottom = min(THIN_LAYER_Z.values())
    top = max(THIN_LAYER_Z.values())
    assert np.diff(np.concatenate(([bottom - 0.6e-3], z[:4]))).sum() == pytest.approx(
        0.6e-3, abs=1e-15
    )
    assert np.diff(np.concatenate((z[-4:], [top + 1.2e-3]))).sum() == pytest.approx(
        1.2e-3, abs=1e-15
    )
    # graded geometrically: finest cell touches the board, ratio AIR_GRADING
    finest = z[3] - z[2]
    assert z[2] - z[1] == pytest.approx(finest * AIR_GRADING, rel=1e-12)
    assert z[1] - z[0] == pytest.approx(finest * AIR_GRADING**2, rel=1e-12)


def test_cells_per_dielectric_doubling_on_thick_slabs(thick_board):
    """With slabs thick against dx the step is lateral-limited either way."""
    region = (0.0, 0.0, 2.0, 2.0)
    dx = 1.0e-4
    coarse = build_grid(thick_board, region, dx, cells_per_dielectric=2, air_cells=3)
    fine = build_grid(thick_board, region, dx, cells_per_dielectric=4, air_cells=3)

    assert fine.nx == coarse.nx and fine.ny == coarse.ny      # lateral untouched
    assert fine.nz - 2 * 3 == 2 * (coarse.nz - 2 * 3)         # dielectric cells x2
    # z stays the coarsest axis, so dt is set by dx and barely moves
    assert coarse.widths("z").min() > dx and fine.widths("z").min() > dx
    assert _cfl(coarse) == pytest.approx(cfl_dt(coarse), rel=1e-12)
    assert _cfl(fine) == pytest.approx(cfl_dt(fine), rel=1e-12)
    assert abs(_cfl(coarse) - _cfl(fine)) < 1e-2 * _cfl(coarse)


# ---------------------------------------------------------------------------
# stackup arithmetic -- CMEX
# ---------------------------------------------------------------------------
def test_layer_z_positions(board):
    z = layer_z_positions(board)
    assert list(z) == CMEX_COPPER
    for name, expected in CMEX_LAYER_Z.items():
        assert z[name] == pytest.approx(expected, abs=1e-15)
    assert len(z) == 8


def test_dielectric_intervals(board):
    intervals = dielectric_intervals(board)
    assert len(intervals) == 7
    assert all(eps == pytest.approx(4.5) for _, _, eps in intervals)
    assert all(z1 > z0 for z0, z1, _ in intervals)

    z = layer_z_positions(board)
    span = z["F.Cu"] - z["B.Cu"]
    # exact, not approximate: the bounds are stackup sums of the same millimetres
    assert sum(z1 - z0 for z0, z1, _ in intervals) == pytest.approx(span, abs=1e-12)
    assert span == pytest.approx(1.545e-3, abs=1e-12)
    # ... and the board thickness is that span plus the two outer bands
    assert board.thickness * MM == pytest.approx(span + 2 * OUTER_BAND, abs=1e-12)


# ---------------------------------------------------------------------------
# the mesh
# ---------------------------------------------------------------------------
def test_grid_resolves_every_copper_layer(coupon, board):
    grid = coupon.grid
    cpd, air_cells = 2, 3
    assert grid.nz == 7 * cpd + 2 * air_cells == 20
    for name, value in layer_z_positions(board).items():
        assert np.any(grid.z == value), f"{name} is not a node plane"
    assert list(grid.z) == sorted(grid.z)

    bottom = layer_z_positions(board)["B.Cu"]
    top = layer_z_positions(board)["F.Cu"]
    assert grid.z[0] == pytest.approx(bottom - 0.5e-3, abs=1e-15)
    assert grid.z[-1] == pytest.approx(top + 1.0e-3, abs=1e-15)
    assert grid.z[-1] - grid.z[0] > board.thickness * MM    # air on both sides


def test_lateral_step_is_honoured(coupon):
    grid = coupon.grid
    assert grid.nx == 96 and grid.ny == 91
    assert grid.widths("x").max() <= 1.0e-3
    assert grid.widths("y").max() <= 1.0e-3
    assert grid.n_cells == grid.nx * grid.ny * grid.nz == 174720
    assert grid.extent[0] == pytest.approx(95.325e-3, rel=1e-12)
    assert grid.extent[1] == pytest.approx(90.2e-3, rel=1e-12)


def test_epsilon_reaches_the_materials_matrices(coupon, board):
    """The coupon's eps reaches ``m_eps`` through the dual interface average.

    A node plane in the *middle* of the dielectric sees dielectric on both
    sides, so it comes out 4.5 under either interface convention.  A node plane
    at the *board surface* is a dielectric/air interface lying exactly on a
    node, and the default dual average makes it the extent-weighted mean of the
    two sides -- so it is neither 4.5 nor 1.0.
    """
    grid, cc = coupon.grid, coupon.cc
    baseline, _ = material_matrices(grid, cc, eps_r=1.0)
    ratio = coupon.m_eps / baseline

    eps_d = 4.5     # the coupon's single stackup dielectric
    eps_air = 1.0   # vacuum outside the meshed stack
    z = layer_z_positions(board)
    widths = grid.widths("z")

    # An EX edge on a z node plane sits on the dual face that spans half of the
    # cell below the plane and half of the cell above it, so its coefficient is
    # the extent-weighted mean of the two eps values.  (The factor 1/2 cancels
    # in the mean; it is kept because it is the face extent being averaged.)

    # top of the stack: dielectric below, air box above
    k_top = int(np.argmin(np.abs(grid.z - z["F.Cu"])))
    assert grid.z[k_top] == z["F.Cu"]
    w_lo_top, w_up_top = 0.5 * widths[k_top - 1], 0.5 * widths[k_top]
    eps_top = (eps_d * w_lo_top + eps_air * w_up_top) / (w_lo_top + w_up_top)

    # bottom of the stack: air box below, dielectric above
    k_bot = int(np.argmin(np.abs(grid.z - z["B.Cu"])))
    assert grid.z[k_bot] == z["B.Cu"]
    w_lo_bot, w_up_bot = 0.5 * widths[k_bot - 1], 0.5 * widths[k_bot]
    eps_bot = (eps_air * w_lo_bot + eps_d * w_up_bot) / (w_lo_bot + w_up_bot)

    # exactly these four levels and no others: pure air, pure dielectric, and
    # the two hybrid planes on the board surfaces.  (The division returns
    # 4.499999999999999 for some entries, so round before comparing.)
    levels = np.unique(np.round(ratio, 12))
    expected = np.round(np.sort([eps_air, eps_top, eps_bot, eps_d]), 12)
    assert levels.size == expected.size, levels
    for got, want in zip(levels, expected):
        assert got == pytest.approx(want, abs=1e-9)

    # an EX edge on an *interior* copper node plane: dielectric on both sides,
    # so it is 4.5 whatever the interface convention
    k_inner = int(np.argmin(np.abs(grid.z - z["In3.Cu"])))
    assert grid.z[k_inner] == z["In3.Cu"]
    assert ratio[cc.idx_ex(0, 0, k_inner)] == pytest.approx(eps_d, abs=1e-12)

    assert ratio[cc.idx_ex(0, 0, k_top)] == pytest.approx(eps_top, abs=1e-9)
    assert ratio[cc.idx_ex(0, 0, k_bot)] == pytest.approx(eps_bot, abs=1e-9)

    # ... and the bottom-most node plane is inside the lower air box
    assert ratio[cc.idx_ex(0, 0, 0)] == pytest.approx(eps_air)
    assert grid.z[0] < z["B.Cu"]


def test_epsilon_callable_on_cmex(board):
    eps = epsilon_callable(board)
    z = layer_z_positions(board)
    assert eps(0.0, 0.0, 0.0) == pytest.approx(1.0)
    assert eps(0.0, 0.0, 1.0e-3) == pytest.approx(4.5)
    assert eps(0.0, 0.0, -1.0e-3) == pytest.approx(1.0)
    assert eps(0.0, 0.0, z["B.Cu"]) == pytest.approx(4.5)
    # the top copper mid-plane is the top of the meshed stack: vacuum above it
    assert eps(0.0, 0.0, z["F.Cu"]) == pytest.approx(1.0)
    assert np.asarray(eps(np.zeros(3), np.zeros(3), np.zeros(3))).shape == (3,)


def test_dt_is_the_cfl_step(coupon):
    dt = coupon.dt
    assert np.isfinite(dt) and dt > 0.0
    assert dt == pytest.approx(cfl_dt(coupon.grid), rel=1e-12)
    assert dt == pytest.approx(_cfl(coupon.grid), rel=1e-12)
    assert coupon.info.dt == dt
    # the finest cell is the thinnest dielectric slab, not dx: the thinnest
    # mid-plane gap is 0.135 mm (a 0.1 mm prepreg plus two half foils), split
    # in two by cells_per_dielectric
    assert coupon.grid.widths("z").min() == pytest.approx(0.135e-3 / 2, rel=1e-12)
    assert coupon.grid.widths("z").min() < coupon.grid.widths("x").min()


def test_cells_per_dielectric_doubling_on_cmex(board, coupon):
    """On CMEX z *is* the finest axis, so refining it halves dt."""
    fine = build_grid(board, CMEX_REGION, 1.0e-3, cells_per_dielectric=4)
    coarse = coupon.grid
    assert fine.nz == 7 * 4 + 2 * 3 == 34
    assert fine.nz - 2 * 3 == 2 * (coarse.nz - 2 * 3)
    assert fine.nx == coarse.nx and fine.ny == coarse.ny
    assert fine.widths("z").min() == pytest.approx(coarse.widths("z").min() / 2, rel=1e-12)
    assert cfl_dt(fine) == pytest.approx(_cfl(fine), rel=1e-12)
    assert cfl_dt(fine) < 0.6 * cfl_dt(coarse)


def test_copper_foils_are_never_resolved(coupon, board, thick_board):
    """The point of the thin-sheet idealisation: no z cell is a foil thickness.

    Resolving a 35 um foil -- even as a single cell -- would put a 17.5-35 um
    width on the z axis, and ``cfl_dt`` is limited by the finest width, so the
    step would fall by the ratio of that width to the dielectric cell that
    replaces it.  The mesh must therefore never contain a copper slab.
    """
    foil = 0.035 * MM
    fine = build_grid(board, CMEX_REGION, 1.0e-3, cells_per_dielectric=8)
    coarse = coupon.grid

    # z cells grow only by subdividing the seven dielectrics; the two air boxes
    # keep their three cells each and nothing else is inserted
    assert fine.nz == 7 * 8 + 2 * 3
    assert fine.nz - 2 * 3 == 4 * (coarse.nz - 2 * 3)
    for grid in (coarse, fine):
        widths = grid.widths("z")
        assert not np.any(np.isclose(widths, foil, rtol=0.0, atol=1e-12))
        assert not np.any(np.isclose(widths, foil / 2, rtol=0.0, atol=1e-12))

    # on this stack the dielectric cells are far finer than dx, so the step
    # does track the subdivision: cpd 2 -> 8 cuts it by the subdivision factor
    assert cfl_dt(fine) == pytest.approx(cfl_dt(coarse) / 4, rel=2e-3)
    assert cfl_dt(fine) == pytest.approx(_cfl(fine), rel=1e-12)

    # on a thick-slab stack the same x4 subdivision leaves dt alone (lateral
    # limiting), whereas a resolved foil would have made it collapse by
    # dx / (foil / 2) ~ 5.7
    region, dx = (0.0, 0.0, 2.0, 2.0), 1.0e-4
    coarse_thick = build_grid(thick_board, region, dx, cells_per_dielectric=2, air_cells=3)
    fine_thick = build_grid(thick_board, region, dx, cells_per_dielectric=8, air_cells=3)
    assert fine_thick.nz - 2 * 3 == 4 * (coarse_thick.nz - 2 * 3)
    assert cfl_dt(fine_thick) == pytest.approx(cfl_dt(coarse_thick), rel=2e-3)
    assert cfl_dt(coarse_thick) == pytest.approx(_cfl(coarse_thick), rel=1e-12)
    foil_limited = 0.99 / (C0 * np.sqrt(2.0 / dx**2 + (1.0 / (foil / 2)) ** 2))
    assert cfl_dt(coarse_thick) > 2.0 * foil_limited


# ---------------------------------------------------------------------------
# the coupon
# ---------------------------------------------------------------------------
def test_build_returns_materials_only(coupon):
    grid, cc = coupon.grid, coupon.cc
    assert isinstance(grid, Grid) and isinstance(cc, CellComplex)
    assert isinstance(coupon, Coupon) and isinstance(coupon.info, CouponInfo)
    assert coupon.m_eps.shape == (cc.n_edges,)
    assert coupon.m_mu.shape == (cc.n_faces,)
    assert np.all(coupon.m_mu == material_matrices(grid, cc)[1])
    # no copper, no PEC, no source: this module stops at metric + materials
    for absent in ("pec", "pec_edges", "copper", "sources", "run"):
        assert not hasattr(coupon, absent)


def test_coupon_info_matches_the_board(coupon, board):
    info = coupon.info
    grid = coupon.grid
    assert info.n_cells_xyz == grid.shape
    assert info.n_cells == grid.n_cells
    assert info.n_nodes == coupon.cc.n_nodes
    assert info.n_edges == coupon.cc.n_edges
    assert info.n_faces == coupon.cc.n_faces
    assert info.layer_z == layer_z_positions(board)
    assert info.dielectrics == tuple(dielectric_intervals(board))
    assert info.warnings == []
    assert info.estimated_steps > 0
    assert info.aspect_ratio == pytest.approx(
        min(info.min_width[0], info.min_width[1]) / info.min_width[2], rel=1e-12
    )
