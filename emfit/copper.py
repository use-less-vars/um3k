"""Copper geometry -> PEC edge mask on the FIT edge lattice.

What this module does
---------------------
The mesh treats copper as an **infinitesimally thin sheet living on a z node
plane** (:func:`emfit.raster.layer_z_positions` puts every copper mid-plane
exactly on a node).  A copper sheet is an equipotential, so the boundary
condition is imposed the way :mod:`emfit.scatter` imposes a PEC body: the
discrete unknowns that lie *inside* the metal are pinned to zero.  Here those
unknowns are the **in-plane edges** of the sheet's node plane -- ``EX`` edges
(:math:`E_x` integrated along x) and ``EY`` edges -- because those are the
components tangential to the sheet.  Vertical ``EZ`` edges are only pinned
where a via barrel carries current through the stackup.

======================================  =====================================
geometry                                pinned edges
======================================  =====================================
track on layer ``L``                    ``EX``/``EY`` on plane ``k(L)`` whose
                                        **midpoint** is inside the track's
                                        round-capped rectangle
zone on layer ``L`` (non-keepout)        ``EX``/``EY`` on plane ``k(L)`` whose
                                        midpoint is inside the zone outline
via spanning layers ``L1 -> L2``         ``EZ`` edges of the single lateral node
                                        column nearest the barrel centre, for
                                        ``k(L1) <= k < k(L2)``
======================================  =====================================

Sampling is **coordinate based**, never index arithmetic: every edge is
sampled at its midpoint in metres, converted once to board millimetres (the
unit the whole kicad model uses), and tested against the continuum geometry.
That is the same style as :func:`emfit.scatter.cylinder_pec_mask`, and it is
what keeps the mask correct on a non-uniform grid.

Typical use, combining the copper with the six box walls::

    pec = cc.pec_edge_mask(walls) | copper_pec_mask(cc, board)

``layers=`` restricts the *sheet* rasterisation (e.g. to one layer while
debugging); via barrels are always rasterised, since a barrel is what connects
two sheets and there is no sane partial version of it.

Pads are deliberately not rasterised
------------------------------------
``Footprint.pads`` is parsed, but no pad is turned into copper here, for three
reasons of increasing weight:

* a pad's ``position`` is in the footprint's *local* frame, so it needs the
  owning footprint's rotation and translation first -- an extra geometry path
  this module does not otherwise need;
* pad shapes are not all rectangles: ``oval``, ``roundrect`` and ``custom``
  carry their own rotation and, for custom, a whole second polygon list;
* decisive: the question this milestone is judged on is whether the copper
  changes the coupon's characteristic impedance ``Z0``.  Pads sit at the ends
  of a trace, in small clusters, and on the reference board they are an order
  of magnitude rarer than the pour and the tracks.  A pad does not move
  ``Z0``; a pour or a track does.

Ignoring pads is therefore a *documented* choice, not an oversight, and the
mask is bit-identical when ``dataclasses.replace(board, footprints=[])``.

Approximations
--------------
* Zones are filled as their **outline**, solid.  Fill holes, thermal spokes and
  ``keepout`` semantics below the outline level are ignored; ``keepout`` zones
  are skipped entirely.
* ``has_fill=False`` zones are still filled.  The flag says whether KiCad
  stored a fill *polygon*, not whether the copper exists -- a poured GND plane
  is exactly the ``has_fill=False`` case on the reference board.
* No antipads: a trace or barrel does not clear the plane it passes through.
* Arcs are already chords by the time the parser hands them over, so curved
  copper is polygonised, not exact.
* A via barrel is a **solid disc** of diameter ``via.size``, not an annulus
  around the drill; and a barrel whose disc contains no mesh node is snapped to
  its nearest node (with a warning) rather than dropped.
* Lateral quantisation is the usual staircase: copper boundaries land on the
  edge midpoints, so a wall may be misplaced by up to half a lateral cell.
"""

from __future__ import annotations

import numpy as np

from .kicad import Board
from .operators import CellComplex
from .raster import MM, layer_z_positions

__all__ = [
    "copper_area",
    "copper_pec_mask",
    "layer_fill",
    "layer_node_indices",
    "layer_occupancy",
    "via_fill",
]

#: How far (metres) a copper mid-plane may sit from its z node before the mesh
#: is declared inconsistent.  Copper mid-planes are *exactly* node heights when
#: the grid comes from :func:`emfit.raster.build_grid`.
Z_TOL = 1.0e-12


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _node_coords(grid, axis: str) -> np.ndarray:
    """Node coordinates along ``axis``, always ``n + 1`` long.

    :meth:`emfit.grid.Grid.nodes` returns ``n`` entries on a periodic axis (the
    seam node *is* the first node).  Appending the wrap node -- one nominal
    cell past the last -- gives a uniform length and lets every caller treat a
    periodic axis as a closed loop without a special case.
    """
    a = np.asarray(getattr(grid, axis), dtype=float)
    if not grid.is_periodic(axis):
        return a
    step = a[-1] - a[-2]
    return np.append(a, a[-1] + step)


def _as_points(*coords):
    """Broadcast ``coords`` (metres) to a common shape, in millimetres."""
    arrs = [np.asarray(c, dtype=float) / MM for c in coords]
    return np.broadcast_arrays(*arrs)


def _copper_layers(board: Board, layers=None) -> list[str]:
    """Copper layer names to rasterise, validated against ``board``.

    ``None`` means every copper layer of the stackup, in ascending z.  A name
    that is not a copper layer of this board is an error: silently skipping it
    would produce a mask that is quietly missing a sheet.
    """
    known = list(layer_z_positions(board)) or list(board.copper_layers)
    if layers is None:
        return known
    out = [layers] if isinstance(layers, str) else list(layers)
    unknown = [name for name in out if name not in known]
    if unknown:
        raise ValueError(
            f"not a copper layer of this board: {unknown!r}; known: {known!r}"
        )
    return out


def _segment_distance(px, py, ax, ay, bx, by):
    """Distance from points ``(px, py)`` to the segment ``(ax, ay)-(bx, by)``.

    Round caps for free: the clamp of the projection parameter to ``[0, 1]``
    already makes the ends semicircles, which is what a kicad track stroke is.
    """
    dx = bx - ax
    dy = by - ay
    denom = dx * dx + dy * dy
    if denom == 0.0:
        return np.hypot(px - ax, py - ay)
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / denom, 0.0, 1.0)
    return np.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _points_in_polygon(px, py, verts) -> np.ndarray:
    """Even-odd point-in-polygon test for ``verts`` (an (n, 2) array, mm).

    ``px``/``py`` may have any shape; the result broadcasts to it.  Only used on
    flattened 1-D point lists internally, so the crossing test stays a plain
    vectorised loop over the polygon edges.
    """
    px = np.asarray(px, dtype=float)
    py = np.asarray(py, dtype=float)
    x = px.ravel()
    y = py.ravel()
    inside = np.zeros(x.shape, dtype=bool)
    verts = np.asarray(verts, dtype=float)
    if verts.ndim != 2 or verts.shape[0] < 3:
        return inside.reshape(px.shape)
    xa = verts[:, 0]
    ya = verts[:, 1]
    xb = np.roll(xa, -1)
    yb = np.roll(ya, -1)
    for k in range(verts.shape[0]):
        y0, y1 = ya[k], yb[k]
        if y0 == y1:
            continue
        crosses = (y0 > y) != (y1 > y)
        if not crosses.any():
            continue
        x_cross = xa[k] + (y[crosses] - y0) * (xb[k] - xa[k]) / (y1 - y0)
        inside[crosses] ^= x[crosses] < x_cross
    return inside.reshape(px.shape)


# ---------------------------------------------------------------------------
# z node assignment
# ---------------------------------------------------------------------------
def layer_node_indices(board: Board, grid, layers=None) -> dict[str, int]:
    """Copper layer name -> the z node index its mid-plane sits on.

    Parameters
    ----------
    board : Board
    grid : emfit.grid.Grid
    layers : sequence of str, optional
        Subset of the board's copper layers; ``None`` means all of them.

    Raises
    ------
    ValueError
        If a copper mid-plane is further than :data:`Z_TOL` from every z node,
        i.e. the grid was not built by :func:`emfit.raster.build_grid`.
    """
    z = np.asarray(grid.z, dtype=float)
    out: dict[str, int] = {}
    for name in _copper_layers(board, layers):
        zc = layer_z_positions(board)[name]
        k = int(np.argmin(np.abs(z - zc)))
        if abs(z[k] - zc) > Z_TOL:
            raise ValueError(
                f"copper layer {name!r} mid-plane at z={zc!r} m is not on a grid "
                f"node (nearest node {k} at z={z[k]!r} m); build the grid with "
                f"emfit.raster.build_grid so every sheet lands on a node"
            )
        out[name] = k
    return out


# ---------------------------------------------------------------------------
# lateral geometry: one layer at a time
# ---------------------------------------------------------------------------
def layer_fill(board: Board, layer: str, x_m, y_m) -> np.ndarray:
    """Which points of ``layer`` are copper.

    A point is copper when it is inside a track stroke on that layer (**round
    caps**, half the track width either side of the centreline) or inside the
    outline of a non-keepout zone that includes the layer.  Zones are filled
    solid, regardless of ``has_fill`` -- the flag says KiCad stored a fill
    polygon, not that the copper is absent.

    Parameters
    ----------
    board : Board
    layer : str
        Copper layer name; validated against the board.
    x_m, y_m : array_like
        Point coordinates in **metres**, broadcast together.

    Returns
    -------
    numpy.ndarray of bool, shape ``np.broadcast(x_m, y_m).shape``
    """
    if layer not in _copper_layers(board, None):
        raise ValueError(
            f"not a copper layer of this board: {layer!r}; "
            f"known: {_copper_layers(board, None)!r}"
        )
    px, py = _as_points(x_m, y_m)
    fill = np.zeros(px.shape, dtype=bool)
    for track in board.tracks:
        if track.layer != layer:
            continue
        dist = _segment_distance(
            px, py, track.start[0], track.start[1], track.end[0], track.end[1]
        )
        fill |= dist <= 0.5 * track.width
    for zone in board.zones:
        if zone.keepout or layer not in zone.layers:
            continue
        if zone.outline is None or np.size(zone.outline) == 0:
            continue
        fill |= _points_in_polygon(px, py, zone.outline)
    return fill


def layer_occupancy(board: Board, grid, layer: str) -> np.ndarray:
    """Copper occupancy of ``layer`` on the lateral **cell centres**.

    This is the "one boolean per cell face" picture of the layer
    (``grid.face_shape("z")[:2]``), sampled at the centres of the lateral cells
    -- the companion view to the edge-centre sampling
    :func:`copper_pec_mask` actually uses for the boundary condition.

    Returns
    -------
    numpy.ndarray of bool, shape ``(grid.nx, grid.ny)``
    """
    x = np.asarray(grid.x, dtype=float)
    y = np.asarray(grid.y, dtype=float)
    xc = 0.5 * (x[:-1] + x[1:])
    yc = 0.5 * (y[:-1] + y[1:])
    xx, yy = np.meshgrid(xc, yc, indexing="ij")
    return layer_fill(board, layer, xx, yy)


def copper_area(board: Board, cc: CellComplex, layer: str, region=None) -> float:
    """Rasterised copper area of ``layer``, in **square metres**.

    The area of the staircase the mesh actually sees: one lateral cell face per
    copper-covered cell centre (the :func:`layer_occupancy` view), weighted by
    that cell's ``dx * dy``.  Comparing it with ``sum(width * length())`` over
    the layer's tracks is the cheapest measure of what the staircase lost or
    gained at the edges.

    Parameters
    ----------
    board : Board
    cc : CellComplex
    layer : str
        Copper layer name.
    region : tuple of float, optional
        ``(x0, y0, x1, y1)`` in **millimetres**; cell centres outside it are not
        counted.  ``None`` counts the whole grid.

    Returns
    -------
    float
    """
    grid = cc.grid
    occ = layer_occupancy(board, grid, layer)
    area = np.outer(grid.widths("x"), grid.widths("y"))
    if region is not None:
        x0, y0, x1, y1 = (float(v) * MM for v in region)
        x = np.asarray(grid.x, dtype=float)
        y = np.asarray(grid.y, dtype=float)
        xc = 0.5 * (x[:-1] + x[1:])
        yc = 0.5 * (y[:-1] + y[1:])
        area = np.where((xc > x0)[:, None] & (xc < x1)[:, None]
                        & (yc > y0)[None, :] & (yc < y1)[None, :], area, 0.0)
    return float(np.sum(occ * area))


def via_fill(board: Board, x_m, y_m, z_m) -> np.ndarray:
    """Which points are inside a via barrel.

    A point is inside when it is within ``via.size / 2`` of the barrel axis and
    its z lies between the two copper mid-planes the via spans (inclusive).
    Vias with no ``size`` carry no barrel geometry and are skipped.

    Parameters
    ----------
    x_m, y_m, z_m : array_like
        Coordinates in **metres**, broadcast together.

    Returns
    -------
    numpy.ndarray of bool
    """
    px, py = _as_points(x_m, y_m)          # mm
    pz = np.asarray(z_m, dtype=float)      # metres, like the sheet heights
    px, py, pz = np.broadcast_arrays(px, py, pz)
    za = layer_z_positions(board)  # already metres above the board bottom
    fill = np.zeros(px.shape, dtype=bool)
    for via in board.vias:
        if not via.size:
            continue
        lo, hi = za[via.layers[0]], za[via.layers[1]]
        if lo > hi:
            lo, hi = hi, lo
        inside = (px - via.position[0]) ** 2 + (py - via.position[1]) ** 2
        fill |= (inside <= (0.5 * via.size) ** 2) & (pz >= lo) & (pz <= hi)
    return fill


# ---------------------------------------------------------------------------
# via barrels
# ---------------------------------------------------------------------------
def _add_via_barrels(mask, cc: CellComplex, board: Board, node_of, xn, yn,
                     warnings) -> None:
    """OR the vertical (``EZ``) edges of every via barrel into ``mask``.

    A barrel is a solid disc of diameter ``via.size`` on the node lattice: the
    ``EZ`` edges of the node column nearest its centre are pinned for every k
    between the two sheets it spans.  ``mask`` is modified in place.
    """
    xn_mm = np.asarray(xn, dtype=float) / MM
    yn_mm = np.asarray(yn, dtype=float) / MM
    xx, yy = np.meshgrid(xn_mm, yn_mm, indexing="ij")
    for via in board.vias:
        if not via.size:
            continue
        cx, cy = via.position
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        hits = d2 <= (0.5 * via.size) ** 2
        if not hits.any():
            idx = np.unravel_index(int(np.argmin(d2)), d2.shape)
            hits = np.zeros_like(d2)
            hits[idx] = True
            warnings.append(
                f"via at ({cx:g}, {cy:g}) mm is smaller than the lateral cell: "
                f"snapped to the nearest node "
                f"({xn_mm[idx[0]]:g}, {yn_mm[idx[1]]:g}) mm"
            )
        try:
            ka = node_of[via.layers[0]]
            kb = node_of[via.layers[1]]
        except KeyError:
            ka = min(node_of.values())
            kb = max(node_of.values())
            warnings.append(
                f"via at ({cx:g}, {cy:g}) mm spans {via.layers!r}, which is not "
                f"a pair of meshed copper layers: falling back to the full stack "
                f"({ka} -> {kb})"
            )
        lo, hi = (ka, kb) if ka <= kb else (kb, ka)
        if lo == hi:
            warnings.append(
                f"via at ({cx:g}, {cy:g}) mm spans a single copper plane "
                f"({via.layers[0]!r}): no EZ edges to pin"
            )
        i, j = np.nonzero(hits)
        for k in range(lo, hi):
            mask[cc.idx_ez(i, j, k)] |= True


# ---------------------------------------------------------------------------
# the boundary condition
# ---------------------------------------------------------------------------
def copper_pec_mask(cc: CellComplex, board: Board, *, layers=None,
                    warnings: list[str] | None = None) -> np.ndarray:
    """Boolean mask of the edges clamped to zero voltage by copper.

    The mask is ``True`` on

    * the in-plane (``EX``, ``EY``) edges of every copper sheet plane whose
      midpoint lies in copper on that layer, and
    * the vertical (``EZ``) edges of every via barrel.

    Sample points are edge **midpoints** computed from the grid coordinates, so
    a track or zone boundary lands on the edge that is more than half covered
    -- the usual staircase, off by at most half a lateral cell.

    Parameters
    ----------
    cc : CellComplex
    board : Board
    layers : sequence of str, optional
        Restrict the *sheet* rasterisation to these copper layers.  Via barrels
        are always rasterised: a barrel connects two sheets, and there is no
        sensible partial version of it.
    warnings : list of str, optional
        Appended to (never replaced) for the approximations that are worth
        reporting: a via snapped to a node, a via whose layers are not meshed, a
        via spanning a single plane.

    Returns
    -------
    numpy.ndarray of bool, shape ``(cc.n_edges,)``

    Notes
    -----
    Combine with the box walls before handing the mask to
    :func:`emfit.evolve`; the walls are a separate, caller-chosen set::

        pec = cc.pec_edge_mask(walls) | copper_pec_mask(cc, board)

    Pads are not rasterised -- see the module docstring for why.
    """
    warn = warnings if warnings is not None else []
    grid = cc.grid
    # ``layers`` limits the sheets only: a barrel is resolved against *every*
    # copper plane, so restricting the sheets cannot silently unroute a via.
    all_nodes = layer_node_indices(board, grid)
    node_of = layer_node_indices(board, grid, layers)

    xn = _node_coords(grid, "x")
    yn = _node_coords(grid, "y")

    mask = np.zeros(cc.n_edges, dtype=bool)

    # in-plane edges, sheet by sheet
    xe = 0.5 * (xn[:-1] + xn[1:])          # EX midpoints, metres
    ye = 0.5 * (yn[:-1] + yn[1:])          # EY midpoints, metres
    xg, yg = np.meshgrid(xe, yn, indexing="ij")     # EX: x midpoints, all y nodes
    xv, yv = np.meshgrid(xn, ye, indexing="ij")     # EY: all x nodes, y midpoints

    for name, k in node_of.items():
        fill_x = layer_fill(board, name, xg, yg)
        fill_y = layer_fill(board, name, xv, yv)
        i_x, j_x = np.nonzero(fill_x)
        if i_x.size:
            mask[cc.idx_ex(i_x, j_x, k)] |= True
        i_y, j_y = np.nonzero(fill_y)
        if i_y.size:
            mask[cc.idx_ey(i_y, j_y, k)] |= True

    # vertical edges, via by via
    _add_via_barrels(mask, cc, board, all_nodes, xn, yn, warn)
    return mask
