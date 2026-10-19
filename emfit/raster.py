"""KiCad board -> FIT mesh metric and material description (milestone M4, part 1).

A printed-circuit board is a *planar stratified* structure: the conducting
geometry (tracks, pads, pours, via barrels) is essentially two-dimensional on a
handful of parallel copper sheets, and between the sheets sits a stack of
dielectric slabs.  This module turns the stackup that ``emfit.kicad`` parses
into the two things a FIT solver needs before any field can be computed:

* a **metric** -- a :class:`~emfit.grid.Grid` whose z nodes land exactly on
  every copper layer, so that a copper sheet is a *surface of nodes* and a
  later copper -> PEC mapping has cells to point at; and
* a **material description** -- ``M_eps``/``M_mu`` built from a permittivity
  callable that reproduces the dielectric slabs and puts vacuum above and below
  the board.

Units
-----
KiCad stores every length in millimetres and ``emfit.kicad`` preserves that.
This module is the boundary: :func:`_mm_to_m` (with :data:`MM`) is the *only*
place a millimetre is converted, and everything that leaves this module -- node
coordinates, widths, thicknesses, slab bounds -- is in **metres**.  Nothing
downstream ever sees a millimetre.

Layout convention
-----------------
``kicad.Board.stackup`` is listed in file order, i.e. front (top) to back
(bottom).  Here ``z = 0`` is the **bottom face of the board** (the underside of
the bottom soldermask) and ``z`` increases upward through the stack, so
``z = board thickness`` is the top face.  The bottom-up ordering is what makes
"the dielectric between copper layer k and k+1" an unambiguous slice.

Thin-sheet copper (an idealisation, not an approximation we can avoid)
---------------------------------------------------------------------
A copper foil is 35 um thick.  Resolving it as its own cell ring would force
``min(dz) <= 35 um``: at the lateral resolutions used here (``dx`` of 0.1-1 mm)
that cuts the CFL step -- ``emfit.evolve.cfl_dt`` is set by the *smallest*
width on each axis -- by a factor of 2-3, and adds z cells, for a structure
whose galvanic behaviour is indistinguishable from an infinitesimally thin
sheet at any frequency where the skin depth is much larger than the foil.  So:

* each copper layer is placed at the **mid-plane of its physical foil** and
  occupies **zero thickness** in the mesh -- copper layers are node planes;
* a dielectric interval therefore runs from one copper mid-plane to the next
  (see :func:`dielectric_intervals`), so a shared height is the same float on
  both sides and the partition is exact;
* soldermask, silkscreen and paste contribute **no** geometry and **no** nodes.
  The consequence is that the outer 27.5 um band on each side of the board --
  10 um of soldermask plus half of the outer foil -- is *outside* the meshed
  stack: the outermost copper sheets are the model's board surfaces and the air
  boxes start there.  Meshing that band would need a 13.75 um z cell and would
  cost more than a factor of two in ``dt``, for a layer whose ``eps_r`` KiCad
  does not even record.  The stackup therefore contributes
  ``t_board - 2 * 27.5 um`` of meshed dielectric, not ``t_board``.

What sets the time step
-----------------------
``emfit.evolve.cfl_dt`` is limited by the **finest cell on every axis**, so the
step is set by whichever dimension is finest -- neither ``dx`` nor the declared
board thickness picks it a priori.  On a board stackup the finest dimension is
usually a *dielectric* cell, not a lateral one: on the reference board the
thinnest mid-plane gap is 0.135 mm, so ``cells_per_dielectric=2`` already gives
a 0.0675 mm z cell against a 1 mm lateral cell, and the step is z-limited.
Subdividing the dielectrics further therefore *does* shrink ``dt``: doubling
``cells_per_dielectric`` halves the z cells and halves the step here.  The
opposite -- a step that ignores the subdivision because the slabs stay much
thicker than ``dx`` -- is a property of a particular stackup, not of this code.  It is also
the second reason the foil is not resolved: a copper ring of 35 um (17.5 um per
half) would put a 20x finer width on the z axis than the slab cell it replaces
and cut ``dt`` by a similar factor for no galvanic gain.

Not implemented in this module (next milestone, M4 part 2)
---------------------------------------------------------
There is deliberately **no copper -> PEC rasterisation here**: nothing in this
file looks at ``board.tracks``, ``board.vias``, ``board.zones`` or pads, and no
PEC mask is produced.  Turning the copper geometry into a boolean occupancy map
per layer and then into a PEC edge mask (``cc.pec_edge_mask(walls) | mask``, as
``emfit.scatter`` does for a cylinder) is the *next* step, and it is kept
separate on purpose: the metric above is exactly the substrate that rasteriser
needs (see the commented outline at the end of this file), and keeping the two
apart means the mesh and material path can be validated against the stackup
arithmetic without any copper in the picture.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .evolve import cfl_dt
from .grid import Grid
from .kicad import Board
from .materials import C0, material_matrices
from .operators import CellComplex

__all__ = [
    "MM",
    "Coupon",
    "CouponInfo",
    "build",
    "build_grid",
    "dielectric_intervals",
    "epsilon_callable",
    "layer_z_positions",
]


#: One millimetre in metres.  See the module docstring: this is the single
#: conversion constant at the KiCad boundary.
MM = 1.0e-3

#: Permittivity assumed for a dielectric layer whose ``epsilon_r`` is missing.
DEFAULT_EPS_R = 1.0

#: Ratio between adjacent vacuum cells in the air boxes above/below the board.
#: The cells grow *away* from the board, so the finest air cell is the one
#: adjacent to the board -- the one a later PML will be built from.
AIR_GRADING = 1.5

#: Edge count above which :func:`build` records a "this mesh is absurd" warning.
EDGE_WARN = 1_000_000

#: Estimated time-step count above which :func:`build` records the same warning.
STEP_WARN = 200_000


def _mm_to_m(value: float) -> float:
    """KiCad millimetres -> metres.

    The only mm -> m conversion in this module; every other length here is
    already in metres.
    """
    return float(value) * MM


# ---------------------------------------------------------------------------
# stackup -> z geometry
# ---------------------------------------------------------------------------
def _walk_stackup(board: Board, warnings: list[str] | None = None):
    """Walk the stackup bottom-up.

    Returns ``(copper, dielectric_eps, total)`` where

    * ``copper`` is ``[(layer_name, mid_plane_z_metres), ...]`` ascending --
      the mid-plane of each copper foil, measured from the board's bottom face;
    * ``dielectric_eps`` is the ``eps_r`` of each ``core``/``prepreg`` entry,
      likewise ascending;
    * ``total`` is the stackup thickness in metres.

    Entries are accumulated in millimetres (as the file declares them) and only
    the resulting heights are converted, so every height shares one arithmetic
    path and copper mid-planes and dielectric bounds agree *exactly*.
    """
    z = 0.0  # millimetres above the bottom face
    copper: list[tuple[str, float]] = []
    dielectric_eps: list[float] = []
    for entry in reversed(list(board.stackup)):
        thickness = 0.0 if entry.thickness is None else float(entry.thickness)
        if entry.is_copper:
            copper.append((entry.name, _mm_to_m(z + 0.5 * thickness)))
        elif entry.kind in ("core", "prepreg"):
            eps_r = entry.epsilon_r
            if eps_r is None:
                if warnings is not None:
                    warnings.append(
                        f"dielectric {entry.name!r} has no epsilon_r; "
                        f"assuming {DEFAULT_EPS_R}"
                    )
                eps_r = DEFAULT_EPS_R
            dielectric_eps.append(float(eps_r))
        z += thickness
    return copper, dielectric_eps, _mm_to_m(z)


def layer_z_positions(board: Board) -> dict[str, float]:
    """Copper layer name -> its z position in metres above the board bottom.

    The foil itself is infinitesimally thin (module docstring); the returned
    height is the mid-plane of the physical foil.  Keys are the stackup names
    (``"F.Cu"``, ``"In1.Cu"``, ... ``"B.Cu"``) in ascending z, so ``"B.Cu"`` is
    the lowest and ``"F.Cu"`` the highest entry.
    """
    copper, _eps, _total = _walk_stackup(board)
    return {name: mid for name, mid in copper}


def dielectric_intervals(
    board: Board, warnings: list[str] | None = None
) -> list[tuple[float, float, float]]:
    """Dielectric slabs as ``[(z_bottom, z_top, eps_r), ...]``, metres, ascending.

    There is one interval per dielectric entry of the stackup -- seven of them
    for an eight-layer board.  The boundaries are the copper mid-planes
    (:func:`layer_z_positions`), which is why the two agree exactly: a shared
    height is the *same float*, not merely a value within a tolerance.

    Because copper is a zero-thickness sheet, the intervals span mid-plane to
    mid-plane and therefore cover ``t_board`` minus the two outer bands of
    ``soldermask + half a foil`` (27.5 um each on the reference board) -- the
    mask/silk/paste bands are *not* part of the electromagnetically meshed
    stack, see the module docstring.  Their total is
    ``sum(z_top - z_bottom)``, i.e. ``mid_plane(F.Cu) - mid_plane(B.Cu)`` --
    **not** ``board.thickness``.  On the reference board that is 1.545 mm
    against a declared 1.6 mm; the 55 um difference is the two 27.5 um outer
    bands.  Describing this table in terms of the declared board thickness
    would be wrong by exactly those bands.

    A dielectric entry without ``epsilon_r`` gets :data:`DEFAULT_EPS_R` and is
    reported through ``warnings`` (a list, appended to, if given).
    """
    copper, dielectric_eps, _total = _walk_stackup(board, warnings)
    if len(copper) < 2:
        raise ValueError(
            f"board declares {len(copper)} copper layer(s); at least 2 are needed"
        )
    n_intervals = len(copper) - 1
    if len(dielectric_eps) != n_intervals:
        if warnings is not None:
            warnings.append(
                f"stackup has {len(copper)} copper layers but "
                f"{len(dielectric_eps)} dielectric entries; "
                f"padding/truncating eps_r to {n_intervals}"
            )
        dielectric_eps = (dielectric_eps + [DEFAULT_EPS_R] * n_intervals)[:n_intervals]

    # Mid-plane to mid-plane: the copper sheets are the interval boundaries, so
    # every copper height is exactly an interval bound (see layer_z_positions).
    return [
        (copper[k][1], copper[k + 1][1], dielectric_eps[k])
        for k in range(n_intervals)
    ]


# ---------------------------------------------------------------------------
# permittivity
# ---------------------------------------------------------------------------
def epsilon_callable(
    board: Board, dielectrics: list[tuple[float, float, float]] | None = None
):
    """Return ``eps_r(x, y, z)`` as a vectorised callable in metres.

    The board is laterally homogeneous in this model -- the stackup is a
    function of ``z`` only -- so the callable ignores ``x`` and ``y`` but keeps
    them in the signature that ``emfit.materials.material_matrices`` uses.  It
    returns vacuum (``1.0``) outside the meshed stack, i.e. in the air boxes
    both above the top copper mid-plane and below the bottom one, and the
    slab's ``eps_r`` in between.  The 10 um soldermask band that physically
    sits above and below the outer foils is deliberately *not* meshed (module
    docstring), so it contributes no permittivity here either: the vacuum
    starts at the outer copper mid-plane.

    Two boundary conventions are worth stating, because the FIT sampling makes
    both of them *hit*:

    * a point exactly on a **copper mid-plane** belongs to the dielectric
      *above* it (intervals are half-open, ``[z_bottom, z_top)``).  This
      matters: ``material_matrices`` samples ``EX``/``EY`` edges at z *node*
      values (``materials._centres``), and the z nodes are exactly the copper
      mid-planes, so every in-plane edge sits on one of these boundaries.  The
      rule is deterministic and the same on every layer;
    * a point exactly on a **dielectric interface** is resolved by the same
      rule -- it takes the upper slab.

    The returned array always has the broadcast shape of the inputs, which is
    what ``material_matrices`` expects (it passes one array per edge).
    """
    intervals = (
        dielectric_intervals(board) if dielectrics is None else list(dielectrics)
    )
    if not intervals:
        raise ValueError("board stackup declares no dielectric layers")
    z_bottom = np.array([float(iv[0]) for iv in intervals], dtype=float)
    z_top = np.array([float(iv[1]) for iv in intervals], dtype=float)
    eps_r = np.array([float(iv[2]) for iv in intervals], dtype=float)
    n = eps_r.size
    top = float(z_top[-1])

    def eps(x, y, z):
        xb, yb, zb = np.broadcast_arrays(
            np.asarray(x, dtype=float),
            np.asarray(y, dtype=float),
            np.asarray(z, dtype=float),
        )
        # searchsorted(side="right") on the lower bounds puts a point sitting
        # exactly on a boundary into the interval *above* it (half-open rule).
        k = np.searchsorted(z_bottom, zb, side="right") - 1
        # the last lower bound always wins the search, so the upper guard has
        # to be an explicit comparison with the top of the stack
        inside = (k >= 0) & (zb < top)
        return np.where(inside, eps_r[np.clip(k, 0, n - 1)], DEFAULT_EPS_R)

    return eps


# ---------------------------------------------------------------------------
# the mesh
# ---------------------------------------------------------------------------
def _air_widths(total: float, count: int) -> np.ndarray:
    """``count`` geometrically graded widths summing exactly to ``total``.

    Widths grow by :data:`AIR_GRADING` per cell away from the board, so the
    first (finest) cell is the one touching the board.
    """
    if count <= 0:
        return np.zeros(0, dtype=float)
    r = AIR_GRADING
    first = total * (r - 1.0) / (r ** count - 1.0)
    return first * r ** np.arange(count, dtype=float)


def _lateral_axis(start: float, stop: float, spacing: float) -> np.ndarray:
    """Uniform nodes from ``start`` to ``stop`` with a cell size at most ``spacing``.

    The cell count is rounded *up* so both region edges are nodes and no cell is
    coarser than the requested ``spacing``; the realised spacing is therefore
    ``(stop - start) / n``, within one part in ``n`` of ``spacing``.
    """
    span = stop - start
    if not span > 0.0:
        raise ValueError(f"region axis is degenerate: start={start!r} stop={stop!r}")
    n = max(1, int(math.ceil(span / spacing - 1e-12)))
    return start + span * np.arange(n + 1, dtype=float) / n


def build_grid(
    board: Board,
    region: tuple[float, float, float, float],
    dx: float,
    *,
    cells_per_dielectric: int = 2,
    air_above: float = 1.0e-3,
    air_below: float = 0.5e-3,
    air_cells: int = 3,
    periodic: tuple[bool, bool, bool] = (False, False, False),
    warnings: list[str] | None = None,
) -> Grid:
    """Mesh a stackup: one node on every copper mid-plane, one slab per dielectric.

    ``region`` is ``(xmin, ymin, xmax, ymax)`` in **KiCad board millimetres** --
    it is meant to be fed ``board.edge_bbox`` unchanged -- and is converted to
    metres here.  ``dx``, ``air_above`` and ``air_below`` are in **metres**.

    Along ``z``:

    * every copper mid-plane is a node (:func:`layer_z_positions`);
    * every dielectric interval is split into ``cells_per_dielectric`` equal
      cells, so slabs of different thickness get different cell sizes but each
      slab is resolved uniformly;
    * ``air_cells`` graded cells cover ``air_below`` below the board and
      ``air_above`` above it (see :func:`_air_widths`).

    Along ``x`` and ``y`` the mesh is uniform over ``region`` with a cell size
    at most ``dx`` (see :func:`_lateral_axis`).  Lateral refinement and any
    resolution of the copper sheets themselves are out of scope here.
    """
    dx = float(dx)
    if not dx > 0.0:
        raise ValueError(f"dx must be positive, got {dx!r}")
    cells_per_dielectric = int(cells_per_dielectric)
    if cells_per_dielectric < 1:
        raise ValueError(
            f"cells_per_dielectric must be >= 1, got {cells_per_dielectric}"
        )
    air_cells = int(air_cells)
    if air_cells < 0:
        raise ValueError(f"air_cells must be >= 0, got {air_cells}")
    if float(air_below) < 0.0 or float(air_above) < 0.0:
        raise ValueError("air_below and air_above must be non-negative")

    intervals = dielectric_intervals(board, warnings)
    z_bottom = intervals[0][0]
    z_top = intervals[-1][1]

    slabs = [
        np.linspace(lo, hi, cells_per_dielectric + 1) for lo, hi, _eps in intervals
    ]
    z = np.concatenate([slabs[0]] + [slab[1:] for slab in slabs[1:]])

    below = _air_widths(float(air_below), air_cells)
    if below.size:
        z = np.concatenate([z_bottom - np.cumsum(below)[::-1], z])
    above = _air_widths(float(air_above), air_cells)
    if above.size:
        z = np.concatenate([z, z_top + np.cumsum(above)])

    try:
        xmin, ymin, xmax, ymax = (float(v) for v in region)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(
            f"region must be (xmin, ymin, xmax, ymax) in mm, got {region!r}"
        ) from exc
    x = _lateral_axis(_mm_to_m(xmin), _mm_to_m(xmax), dx)
    y = _lateral_axis(_mm_to_m(ymin), _mm_to_m(ymax), dx)

    return Grid.nonuniform(x, y, z, periodic=periodic)


# ---------------------------------------------------------------------------
# the assembled coupon
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CouponInfo:
    """Mesh statistics recorded alongside a :class:`Coupon`.

    All widths, heights and ``dt`` are in metres (``dt`` in seconds).  ``layer_z``
    and ``dielectrics`` are the tables the mesh was built from, kept so a caller
    can check the mesh against the stackup without re-parsing the board.
    """

    n_cells: int
    n_cells_xyz: tuple[int, int, int]
    n_edges: int
    n_faces: int
    n_nodes: int
    min_width: tuple[float, float, float]
    max_width: tuple[float, float, float]
    aspect_ratio: float
    dt: float
    estimated_steps: int
    layer_z: dict[str, float] = field(default_factory=dict)
    dielectrics: tuple[tuple[float, float, float], ...] = ()
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Coupon:
    """A meshed board coupon: metric and materials only.

    ``m_eps`` has length ``cc.n_edges`` and ``m_mu`` length ``cc.n_faces`` -- the
    form ``emfit.evolve.FITStepper`` takes.  There is no copper, no PML, no
    source and no ``run`` method: those belong to the rasterisation milestone
    and to the caller.
    """

    grid: Grid
    cc: CellComplex
    m_eps: np.ndarray
    m_mu: np.ndarray
    dt: float
    info: CouponInfo


def build(
    board: Board,
    region: tuple[float, float, float, float],
    dx: float,
    *,
    cells_per_dielectric: int = 2,
    air_above: float = 1.0e-3,
    air_below: float = 0.5e-3,
    air_cells: int = 3,
    periodic: tuple[bool, bool, bool] = (False, False, False),
) -> Coupon:
    """Mesh ``board`` over ``region`` (mm) at ``dx`` metres and build materials.

    Returns a :class:`Coupon` holding the grid, the cell complex, the material
    matrices and the CFL step ``dt = cfl_dt(grid)`` -- the step set by the
    *smallest cell anywhere in the mesh* (per axis, as
    ``emfit.evolve.cfl_dt`` defines it), which for a stackup mesh is normally the
    thinnest dielectric slab divided by ``cells_per_dielectric`` rather than
    ``dx``.

    A mesh that would be absurd to evolve (more than :data:`EDGE_WARN` edges, or
    more than :data:`STEP_WARN` steps just to cross the coupon ten times) is
    **recorded in ``info.warnings`` rather than raised**: building a mesh is
    cheap, and the caller may well want to look at it anyway.
    """
    warnings: list[str] = []
    grid = build_grid(
        board,
        region,
        dx,
        cells_per_dielectric=cells_per_dielectric,
        air_above=air_above,
        air_below=air_below,
        air_cells=air_cells,
        periodic=periodic,
        warnings=warnings,
    )
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc, eps_r=epsilon_callable(board))
    dt = cfl_dt(grid)

    widths = {axis: grid.widths(axis) for axis in "xyz"}
    min_width = tuple(float(np.min(widths[a])) for a in "xyz")
    max_width = tuple(float(np.max(widths[a])) for a in "xyz")
    lateral = min(min_width[0], min_width[1])
    aspect_ratio = lateral / min_width[2]

    span = max(grid.extent)
    estimated_steps = int(math.ceil(10.0 * span / (C0 * dt)))

    if cc.n_edges > EDGE_WARN:
        warnings.append(
            f"mesh has {cc.n_edges} edges (> {EDGE_WARN}); evolution would be slow"
        )
    if estimated_steps > STEP_WARN:
        warnings.append(
            f"~{estimated_steps} steps to cross the coupon 10x (> {STEP_WARN})"
        )

    info = CouponInfo(
        n_cells=grid.n_cells,
        n_cells_xyz=tuple(int(v) for v in grid.shape),
        n_edges=cc.n_edges,
        n_faces=cc.n_faces,
        n_nodes=cc.n_nodes,
        min_width=min_width,
        max_width=max_width,
        aspect_ratio=aspect_ratio,
        dt=dt,
        estimated_steps=estimated_steps,
        layer_z=layer_z_positions(board),
        dielectrics=tuple(dielectric_intervals(board)),
        warnings=warnings,
    )
    return Coupon(grid=grid, cc=cc, m_eps=m_eps, m_mu=m_mu, dt=dt, info=info)


# ---------------------------------------------------------------------------
# NOT IMPLEMENTED HERE (next milestone, M4 part 2): copper -> PEC rasterisation
# ---------------------------------------------------------------------------
# Roughly, and deliberately not coded yet so that it cannot quietly leak into
# the metric path:
#
#   1. per copper layer, rasterise the copper geometry into a boolean occupancy
#      array of shape grid.face_shape("z") (one flag per cell face on that
#      layer): tracks as distance-from-segment < half the track width, pads and
#      zones as polygon fills (staircase accepted -- see docs/roadmap.md:209);
#   2. turn occupancy into a PEC edge mask: a copper sheet is a zero-thickness
#      equipotential, so the in-plane (EX/EY) edges on the occupied faces are
#      clamped to zero voltage, e.g.
#      mask[cc.idx_ex(...)] / mask[cc.idx_ey(...)] at that layer's z node (the
#      half-open sampling convention in epsilon_callable is what makes those
#      indices unambiguous);
#   3. combine with the six box walls: pec = cc.pec_edge_mask(walls) | mask, as
#      emfit.scatter.run_field does for its cylinder.
#
# Everything the rasteriser needs is already produced above: layer_z_positions
# gives each sheet's z node, the grid's z nodes are exactly those heights, and
# Coupon.cc provides the index helpers -- so the copper step can be added
# without changing any public signature in this file.
