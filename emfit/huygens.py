"""Geometry of a closed, axis-aligned Huygens surface on the FIT Yee grid.

What this module is
-------------------
:class:`HuygensBounds` is a *request*: six metric bounds in metres, the two
planes normal to each axis.  :meth:`HuygensBounds.conform_to` turns that request
into :class:`SurfaceSamples`, the finite set of points at which the field
components a near-to-far-field transform needs actually live on this complex --
with the outward normal, the box face each point belongs to, and the flat
indices of the field samples sitting there.

It is *only* geometry: no time loop, no DFT, no flux weights, no tolerances.

Where the fields live, and why the box snaps
--------------------------------------------
:mod:`emfit.operators` stores the magnetic field on the **primal** faces:
``FX`` has shape ``(nx+1, ny, nz)``, ``FY`` ``(nx, ny+1, nz)`` and ``FZ``
``(nx, ny, nz+1)``.  The staggering is the one
:func:`emfit.materials.material_matrices` uses (and :mod:`emfit.pml` restates):
a face normal to ``x`` sits at a *node* along ``x`` and at *cell centres*
across it,

    FX(i, j, k)  at  ( x[i],  yc[j],  zc[k] )      i = 0..nx   (nxn layers)
    FY(i, j, k)  at  ( xc[i],  y[j],  zc[k] )      j = 0..ny
    FZ(i, j, k)  at  ( xc[i],  yc[j],  z[k]  )     k = 0..nz

with ``xc`` the cell-centre coordinates ``(x[j] + x[j+1]) / 2``.  So an ``H``
sample on a face normal to ``x`` is *exactly* on a node plane ``x = grid.x[p]``,
and at cell centres in the two transverse directions.  A conformed Huygens box
is therefore the set of **node planes** nearest the requested bounds --
``grid.x[p]``, ``grid.y[q]``, ``grid.z[r]`` -- and ``snap_delta`` records, per
box face, how far that face had to move to land on one.

Consequence worth stating plainly: two different box faces can never share a
sample point, because at a box corner one face is at a node plane transversely
while the other is at a cell centre.  "Corners and box edges are counted once"
is thus satisfied without any corner bookkeeping; there is nothing to
de-duplicate.  A `Contour`-style half-weight corner scheme (see
:class:`emfit.nearfield.Contour`) is *not* reproduced here and is not needed.

Sample ordering
---------------
Deterministic and documented, so a field record can be reproduced from the
indices alone:

* faces in the fixed order ``xmin, xmax, ymin, ymax, zmin, zmax``
  (``face_id`` = 0..5);
* within a face, the two transverse indices run with the **first** one
  outermost and the second innermost -- ``j`` then ``k`` on the x-normal faces,
  ``i`` then ``k`` on the y-normal faces, ``i`` then ``j`` on the z-normal
  faces, each over the half-open range of the conformed box;
* the index ranges are the conformed cell ranges, so the faces of the box tile
  the surface exactly once.

``face_index``
--------------
``(N, 3)``, one slot per primal-face block ``(FX, FY, FZ)``: the sample *is* the
primal face of its own orientation (``FX`` on an x-normal box face), so exactly
one slot holds a flat index into a ``(n_faces,)`` ``h`` vector and the other two
hold ``-1``.

``edge_index``
--------------
``(N, 4)``, never ``-1``: every sample sits on a primal face, and a primal face
is bounded by exactly four primal edges.  They are listed as

* slots 0-1: the two edges along the **first** transverse direction, lower
  index first;
* slots 2-3: the two along the **second** transverse direction, lower index
  first,

where "first/second transverse direction" is ascending axis order excluding the
face normal.  Concretely, straight off
:meth:`emfit.operators.CellComplex.curl` (whose row for a face lists exactly
these four edges, the two of a pair with opposite signs):

    x-normal  FX(p, j, k)  [EY(p, j, k),  EY(p, j, k+1), EZ(p, j, k),  EZ(p, j+1, k)]
    y-normal  FY(i, q, k)  [EX(i, q, k),  EX(i, q, k+1), EZ(i, q, k),  EZ(i+1, q, k)]
    z-normal  FZ(i, j, r)  [EX(i, j, r),  EX(i, j+1, r), EY(i, j, r),  EY(i+1, j, r)]

so the pair to average for the tangential ``E`` at the sample is

    x-normal:  E_y from slots 0-1,  E_z from slots 2-3
    y-normal:  E_x from slots 0-1,  E_z from slots 2-3
    z-normal:  E_x from slots 0-1,  E_y from slots 2-3

Each pair is two edges of one block, one cell apart, straddling the cell centre
the sample sits on: the sample lies exactly halfway between them, so the pair
average is *centred* on the sample (an ``O(h^2)`` approximation of the
tangential component there for a smooth field).  That is the reason to carry
four flat indices rather than one per block -- the consumer can form both
averages without knowing where on the box the sample is and without re-deriving
the strides.

No gaps at the box edges
------------------------
The enumerated set is exactly the set of primal faces bounding the cell block
``[p0, p1) x [q0, q1) x [r0, r1)`` -- the cells `p0..p1-1` by
`q0..q1-1` by `r0..r1-1`, which span exactly the requested box.
It is therefore a *closed* surface in the discrete (FIT)
sense: every cell face of the block is either interior (counted twice with
opposite normals, and cancelling) or bounding (counted exactly once, which is
what is sampled), so the discrete divergence theorem holds on the enumerated set
by telescoping rather than to truncation error.  That closedness is also why the
transverse sample sets stop half a cell short of the box edges -- at the
transverse cell centres, ``h/2`` from the edge: a sample half a cell further
out would sit on a face that is not part of the block's boundary.  The
gap is the discretisation itself, not an omission, and no extra samples are
needed to close the surface.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np

__all__ = ["FACE_NAMES", "HuygensBounds", "SurfaceSamples"]

#: the six box faces, in the order ``face_id`` uses
FACE_NAMES = ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")

#: outward unit normal per ``face_id``
_NORMALS = np.array(
    (
        (-1.0, 0.0, 0.0),  # xmin
        (1.0, 0.0, 0.0),   # xmax
        (0.0, -1.0, 0.0),  # ymin
        (0.0, 1.0, 0.0),   # ymax
        (0.0, 0.0, -1.0),  # zmin
        (0.0, 0.0, 1.0),   # zmax
    ),
    dtype=float,
)

#: a snap larger than this is reported through :mod:`warnings`
SNAP_WARN_TOL = 1e-9


@dataclass(frozen=True)
class HuygensBounds:
    """A closed axis-aligned box asked for in metres.

    The box is a *request*: :meth:`conform_to` moves it onto the nearest
    node planes, because those are where the ``H`` samples of this Yee complex
    live (see the module docstring).  The bounds themselves are never silently
    altered.

    Parameters
    ----------
    xmin, xmax, ymin, ymax, zmin, zmax : float
        Face positions in metres.  Each pair must satisfy ``min < max``; the
        values must be finite.  Booleans are rejected: ``True`` is not a length
        in metres, and ``float(True) == 1.0`` would otherwise slip through.
    """

    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float

    def __post_init__(self):
        for name in FACE_NAMES:
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)):
                raise TypeError(
                    f"{name}={value!r}: a Huygens bound is a length in metres, "
                    f"not a boolean")
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise TypeError(
                    f"{name}={value!r}: expected a real number of metres, "
                    f"got {type(value).__name__}") from None
            if not math.isfinite(value):
                raise ValueError(f"{name}={value!r}: bounds must be finite")
            object.__setattr__(self, name, value)
        for lo, hi in (("xmin", "xmax"), ("ymin", "ymax"), ("zmin", "zmax")):
            a = getattr(self, lo)
            b = getattr(self, hi)
            if not a < b:
                raise ValueError(
                    f"{lo}={a!r} and {hi}={b!r}: need {lo} < {hi} to span a "
                    f"non-empty interval")

    def describe(self):
        """One line naming the six requested bounds, in metres."""
        return (
            f"HuygensBounds(xmin={self.xmin:.6g} m, xmax={self.xmax:.6g} m, "
            f"ymin={self.ymin:.6g} m, ymax={self.ymax:.6g} m, "
            f"zmin={self.zmin:.6g} m, zmax={self.zmax:.6g} m)"
        )

    def conform_to(self, cc):
        """Snap onto this complex's node planes and enumerate the surface.

        Returns a :class:`SurfaceSamples`.  Each of the six faces is moved to
        the *nearest* node plane along its own axis (ties go to the lower
        index); the signed displacement is reported in ``snap_delta`` and, when
        it exceeds ``1e-9`` m, through :func:`warnings.warn` -- the samples are
        returned either way, because a caller who asked for a slightly
        off-grid surface still wants the geometry.

        Raises
        ------
        ValueError
            If the requested interval along an axis is so narrow that both of
            its bounds snap to the same node plane: such a box encloses no
            cells and has no interior surface to sample.
        """
        grid = cc.grid
        planes = []
        snap_delta = np.zeros(6, dtype=float)
        for axis in "xyz":
            nodes = np.asarray(getattr(grid, axis), dtype=float)
            # a periodic axis carries n distinct planes (the seam node is the
            # first node again), which is exactly the number of H layers there.
            layers = grid.nodes(axis)
            lo = float(getattr(self, f"{axis}min"))
            hi = float(getattr(self, f"{axis}max"))
            p0 = int(np.argmin(np.abs(nodes[:layers] - lo)))
            p1 = int(np.argmin(np.abs(nodes[:layers] - hi)))
            snap_delta[2 * "xyz".index(axis)] = float(nodes[p0]) - lo
            snap_delta[2 * "xyz".index(axis) + 1] = float(nodes[p1]) - hi
            if p1 <= p0:
                raise ValueError(
                    f"{axis}min={lo!r} and {axis}max={hi!r} both snap to the "
                    f"node plane {axis}[{p0}]={float(nodes[p0])!r}: the "
                    f"conformed box would enclose no cells.  Widen the "
                    f"interval by at least one cell.")
            planes.append((p0, p1))

        for face, name in enumerate(FACE_NAMES):
            if abs(snap_delta[face]) > SNAP_WARN_TOL:
                warnings.warn(
                    f"HuygensBounds.conform_to: face {name} moved "
                    f"{snap_delta[face]:+.6g} m to land on the nearest "
                    f"H-sample plane (requested "
                    f"{getattr(self, name):.6g} m, using "
                    f"{getattr(self, name) + snap_delta[face]:.6g} m)",
                    stacklevel=2)

        return _build_samples(cc, planes, snap_delta)


@dataclass(frozen=True)
class SurfaceSamples:
    """The conformed Huygens surface: one record per sample point.

    The arrays are copies owned by this object and marked read-only, so the
    frozen promise is not merely decorative.

    Attributes
    ----------
    coordinates : (N, 3) float64
        Sample positions in metres, i.e. face centres of the primal faces the
        field lives on (module docstring).
    normals : (N, 3) float64
        Outward unit normal of the box face the sample belongs to; axis
        aligned, so every entry is 0 or +-1.
    face_id : (N,) int8
        Which box face: 0..5 for ``xmin, xmax, ymin, ymax, zmin, zmax``.
    edge_index : (N, 4) int64
        Flat primal-edge indices into a ``(n_edges,)`` ``e`` vector: the four
        edges bounding the sample's primal face, in the fixed order documented
        in the module docstring (slots 0-1 the first transverse direction,
        slots 2-3 the second, lower index first in each pair).  Every entry is
        a real index -- this array carries no ``-1``.
    face_index : (N, 3) int64
        Flat primal-face indices into a ``(n_faces,)`` ``h`` vector, one slot
        per block ``(FX, FY, FZ)``, ``-1`` where that block has no face at the
        point.
    snap_delta : (6,) float64
        Signed displacement in metres applied to each box face to land it on
        the nearest node plane; ordered as ``FACE_NAMES``.
    """

    coordinates: np.ndarray
    normals: np.ndarray
    face_id: np.ndarray
    edge_index: np.ndarray
    face_index: np.ndarray
    snap_delta: np.ndarray

    def __post_init__(self):
        coords = np.array(self.coordinates, dtype=float)
        if coords.ndim != 2 or coords.shape[1] != 3:
            raise ValueError(
                f"coordinates: expected shape (N, 3), got {coords.shape}")
        n = coords.shape[0]
        normals = np.array(self.normals, dtype=float)
        face_id = np.array(self.face_id, dtype=np.int8)
        edge_index = np.array(self.edge_index, dtype=np.int64)
        face_index = np.array(self.face_index, dtype=np.int64)
        snap_delta = np.array(self.snap_delta, dtype=float).reshape(-1)
        for name, arr, shape in (
            ("normals", normals, (n, 3)),
            ("face_id", face_id, (n,)),
            ("edge_index", edge_index, (n, 4)),
            ("face_index", face_index, (n, 3)),
            ("snap_delta", snap_delta, (6,)),
        ):
            if arr.shape != shape:
                raise ValueError(
                    f"{name}: expected shape {shape}, got {arr.shape}")
        if np.any(edge_index < 0):
            raise ValueError(
                "edge_index: the four bounding edges of each face always "
                "exist, so no entry may be -1")
        for arr in (coords, normals, face_id, edge_index, face_index, snap_delta):
            arr.flags.writeable = False
        object.__setattr__(self, "coordinates", coords)
        object.__setattr__(self, "normals", normals)
        object.__setattr__(self, "face_id", face_id)
        object.__setattr__(self, "edge_index", edge_index)
        object.__setattr__(self, "face_index", face_index)
        object.__setattr__(self, "snap_delta", snap_delta)

    def face_counts(self):
        """Number of samples on each box face, ordered as ``FACE_NAMES``."""
        return np.bincount(self.face_id, minlength=len(FACE_NAMES)).astype(
            np.int64)


def _build_samples(cc, planes, snap_delta):
    """Enumerate the conformed surface, in the documented order."""
    grid = cc.grid
    node = {a: np.asarray(getattr(grid, a), dtype=float) for a in "xyz"}
    mid = {a: 0.5 * (node[a][1:] + node[a][:-1]) for a in "xyz"}
    (p0, p1), (q0, q1), (r0, r1) = planes

    coordinates = []
    normals = []
    face_id = []
    edge_index = []
    face_index = []

    def push(face, coords, edges, faces):
        n = coords.shape[0]
        coordinates.append(coords)
        normals.append(np.tile(_NORMALS[face], (n, 1)))
        face_id.append(np.full(n, face, dtype=np.int8))
        edge_index.append(np.stack(edges, axis=1))
        face_index.append(np.stack(faces, axis=1))

    absent = np.int64(-1)

    # x-normal faces (face_id 0, 1): plane x = x[p], samples are FX(p, j, k)
    for face, p in ((0, p0), (1, p1)):
        jj, kk = np.meshgrid(np.arange(q0, q1), np.arange(r0, r1), indexing="ij")
        i = np.full(jj.size, p, dtype=np.int64)
        j = jj.reshape(-1).astype(np.int64)
        k = kk.reshape(-1).astype(np.int64)
        push(
            face,
            np.stack([np.full(i.size, node["x"][p]), mid["y"][j], mid["z"][k]],
                     axis=1),
            # EY(p, j, k), EY(p, j, k+1), EZ(p, j, k), EZ(p, j+1, k)
            [cc.idx_ey(i, j, k),
             cc.idx_ey(i, j, k + 1),
             cc.idx_ez(i, j, k),
             cc.idx_ez(i, j + 1, k)],
            [cc.idx_fx(i, j, k),
             np.full(i.size, absent, dtype=np.int64),
             np.full(i.size, absent, dtype=np.int64)],
        )

    # y-normal faces (face_id 2, 3): plane y = y[q], samples are FY(i, q, k)
    for face, q in ((2, q0), (3, q1)):
        ii, kk = np.meshgrid(np.arange(p0, p1), np.arange(r0, r1), indexing="ij")
        i = ii.reshape(-1).astype(np.int64)
        j = np.full(ii.size, q, dtype=np.int64)
        k = kk.reshape(-1).astype(np.int64)
        push(
            face,
            np.stack([mid["x"][i], np.full(i.size, node["y"][q]), mid["z"][k]],
                     axis=1),
            # EX(i, q, k), EX(i, q, k+1), EZ(i, q, k), EZ(i+1, q, k)
            [cc.idx_ex(i, j, k),
             cc.idx_ex(i, j, k + 1),
             cc.idx_ez(i, j, k),
             cc.idx_ez(i + 1, j, k)],
            [np.full(i.size, absent, dtype=np.int64),
             cc.idx_fy(i, j, k),
             np.full(i.size, absent, dtype=np.int64)],
        )

    # z-normal faces (face_id 4, 5): plane z = z[r], samples are FZ(i, j, r)
    for face, r in ((4, r0), (5, r1)):
        ii, jj = np.meshgrid(np.arange(p0, p1), np.arange(q0, q1), indexing="ij")
        i = ii.reshape(-1).astype(np.int64)
        j = jj.reshape(-1).astype(np.int64)
        k = np.full(ii.size, r, dtype=np.int64)
        push(
            face,
            np.stack([mid["x"][i], mid["y"][j], np.full(i.size, node["z"][r])],
                     axis=1),
            # EX(i, j, r), EX(i, j+1, r), EY(i, j, r), EY(i+1, j, r)
            [cc.idx_ex(i, j, k),
             cc.idx_ex(i, j + 1, k),
             cc.idx_ey(i, j, k),
             cc.idx_ey(i + 1, j, k)],
            [np.full(i.size, absent, dtype=np.int64),
             np.full(i.size, absent, dtype=np.int64),
             cc.idx_fz(i, j, k)],
        )

    return SurfaceSamples(
        coordinates=np.concatenate(coordinates, axis=0),
        normals=np.concatenate(normals, axis=0),
        face_id=np.concatenate(face_id),
        edge_index=np.concatenate(edge_index, axis=0).astype(np.int64),
        face_index=np.concatenate(face_index, axis=0).astype(np.int64),
        snap_delta=snap_delta,
    )
