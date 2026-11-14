"""Field-recording tests for :mod:`emfit.huygens_fields`.

Why these tests look the way they do
------------------------------------
The values a near-to-far-field transform consumes are the tangential ``E`` and
``H`` *at the sample points*, and every way of getting them wrong is quiet: a
transposed pair of stencil slots averages the wrong two cells and smooths the
pattern, an ``H`` paired with a stale ``E`` adds a phase slope that looks like a
material, and a ``dt``-independent weight turns a spectrum into a number with no
units.  None of that raises; all of it changes an answer.  So the tests here pin
three separate things:

* the *stencil slots* are checked against a hand-written table of
  :meth:`CellComplex.idx_*` calls, not against the implementation's own
  ordering.  A flat-index array is only useful if it can be consumed, so the
  table is transcribed from the staggering (documented in
  :mod:`emfit.huygens`), never derived from ``h_face_index`` itself;
* the *gathers* are checked with fields that have an exact answer at the sample
  points: an affine field (reproduced exactly by any centred average) and a
  time-harmonic one (reproduced exactly by the half-step midpoint average).
  A field with a known answer at a known position does not need a reference
  solver to be a decisive test;
* the *leapfrog half step* is measured, not assumed: the same recording is made
  at ``dt`` and at ``dt/2``, and the magnetic error has to fall by four while
  the naive single-sided error falls by two.  That is the difference between the
  scheme this module implements and the obvious one, so it is the difference the
  test asserts.

The grids are 4x3x2 and 6x5x4 cells of side 0.1 m -- small enough that every
array can be eyeballed when something fails.  The second grid exists for one
reason: a box strictly inside the domain, ``x[1]..x[4]``, ``y[1]..y[3]``,
``z[1]..z[3]``, so that no ``H`` stencil is clamped and the centroid test is
testing the stencil rather than the clamp.  On the 4x3x2 grid the box reaches
``z[0]`` and ``z[nz]``, which is where the clamping *is* reachable, and one test
uses it for exactly that.

A note on the units and the one factor that is left in
------------------------------------------------------
Each accumulated entry is a sum of ``field * dt * exp(-j w t)``: no normalisation,
no division by the sample count.  The raw ``H`` entries additionally carry the
real factor ``cos(w dt / 2)`` from the midpoint average.  That factor is a
property of the sum, so it is measured on :attr:`SurfaceRecorder.H_t_raw`, where
it lives, rather than on :attr:`SurfaceRecorder.H_t`, which divides it out
(``debias``): ``test_half_step_averaging_is_exact`` asserts it *to the last bit*
rather than asserting the entries "are close", because a factor that is believed
to be there and is measured to be there is the whole reason the average is
taken; and it then shows that the same factor is second order while the
single-sided alternative is first order.
``test_recorder_debias_removes_the_half_step_factor`` pins the division itself.
"""

from __future__ import annotations

import os
import tempfile
import warnings

import numpy as np
import pytest

from emfit.grid import Grid
from emfit.huygens import HuygensBounds, SurfaceSamples
from emfit.huygens_fields import SurfaceRecorder, surface_areas
from emfit.operators import CellComplex

NX, NY, NZ = 4, 3, 2
H = 0.1
X0, X1 = 1, 3
Y0, Y1 = 1, 2
Z0, Z1 = 0, 2

#: a box strictly inside the domain, so that no H stencil is clamped
NI = (6, 5, 4)


def _complex():
    """The 4x3x2 grid with the box of :mod:`tests.test_huygens_bounds`."""
    grid = Grid.uniform(NX, NY, NZ, NX * H, NY * H, NZ * H)
    cc = CellComplex(grid)
    bounds = HuygensBounds(
        xmin=grid.x[X0], xmax=grid.x[X1],
        ymin=grid.y[Y0], ymax=grid.y[Y1],
        zmin=grid.z[Z0], zmax=grid.z[Z1])
    return grid, cc, bounds.conform_to(cc)


def _interior():
    """The 6x5x4 grid with a box that stays off every domain boundary."""
    nx, ny, nz = NI
    grid = Grid.uniform(nx, ny, nz, nx * H, ny * H, nz * H)
    cc = CellComplex(grid)
    bounds = HuygensBounds(
        xmin=grid.x[1], xmax=grid.x[nx - 2],
        ymin=grid.y[1], ymax=grid.y[ny - 2],
        zmin=grid.z[1], zmax=grid.z[nz - 2])
    return grid, cc, bounds.conform_to(cc)


def _nodes_mid(grid):
    node = {a: np.asarray(getattr(grid, a), dtype=float) for a in "xyz"}
    mid = {a: 0.5 * (node[a][1:] + node[a][:-1]) for a in "xyz"}
    return node, mid


def _block_positions(grid, axis, kind):
    """Positions of every entry of one block, in the block's own shape.

    ``kind="edge"``: the block of the ``axis`` edge component, node placed
    along ``axis`` and cell centred across it.  ``kind="face"``: the block of
    the ``axis`` face component, the other way round.  The ragged staggering is
    the reason this is spelled out instead of read off the grid: if the
    convention were wrong, every centroid would be half a cell out.
    """
    node, mid = _nodes_mid(grid)
    names = "xyz"
    comps = []
    for b, name in enumerate(names):
        if kind == "edge":
            comps.append(mid[name] if b == axis else node[name])
        else:
            comps.append(node[name] if b == axis else mid[name])
    shape = (grid.edge_shape(names[axis]) if kind == "edge"
             else grid.face_shape(names[axis]))
    assert tuple(len(c) for c in comps) == tuple(shape), (
        f"{kind} block {names[axis]}: axis lengths {[len(c) for c in comps]} "
        f"do not match the grid's {tuple(shape)}")
    return np.stack(np.meshgrid(*comps, indexing="ij"), axis=-1)


def _flat_positions(grid, cc, axis, kind):
    """Positions of one block, in *block local* flat order.

    Index with ``h_face_index``/``face_index`` **after** subtracting the
    complex's ``off_f*``/``off_e*`` offset for that component: the recorder
    speaks global flat indices, the block arrays are stored per block.
    """
    pos = _block_positions(grid, axis, kind)
    return pos.reshape(-1, 3)


class _Shim:
    """The smallest thing :meth:`SurfaceRecorder.accumulate` will accept."""

    def __init__(self, e, h, dt, time=0.0):
        self.e = e
        self.h = h
        self.dt = dt
        self.time = time


# ----------------------------------------------------------------------
# h_face_index: the eight slots of the two stencils
# ----------------------------------------------------------------------

def test_h_face_index_structure():
    """Every slot is a real index into its own block, and the array is frozen."""
    grid, cc, samples = _complex()
    idx = samples.h_face_index
    assert idx.shape == (samples.face_id.size, 8)
    assert idx.dtype == np.int64
    assert np.all(idx >= 0)
    with pytest.raises(ValueError):
        idx[0, 0] = -1

    normal_axis = np.asarray(samples.face_id) // 2
    off = {0: cc.off_fx, 1: cc.off_fy, 2: cc.off_fz}
    size = {a: int(np.prod(grid.face_shape("xyz"[a]))) for a in range(3)}
    for a in range(3):
        tang = [b for b in range(3) if b != a]
        for slot_axis, component in ((0, tang[0]), (1, tang[1])):
            sel = normal_axis == a
            block = idx[sel, 4 * slot_axis:4 * slot_axis + 4]
            assert block.size > 0
            assert np.all(block >= off[component])
            assert np.all(block < off[component] + size[component])


def test_h_face_index_matches_hand_table():
    """The eight slots, decoded, are the faces the staggering says they are."""
    grid, cc, samples = _interior()
    for n in range(samples.face_id.size):
        face = int(samples.face_id[n])
        a = face // 2
        flat = int(samples.face_index[n, a])
        local = flat - (cc.off_fx, cc.off_fy, cc.off_fz)[a]
        ijk = np.unravel_index(local, grid.face_shape("xyz"[a]))
        i, j, k = (int(v) for v in ijk)
        if a == 0:
            p = i
            expect = [
                cc.idx_fy(p - 1, j, k), cc.idx_fy(p, j, k),
                cc.idx_fy(p - 1, j + 1, k), cc.idx_fy(p, j + 1, k),
                cc.idx_fz(p - 1, j, k), cc.idx_fz(p, j, k),
                cc.idx_fz(p - 1, j, k + 1), cc.idx_fz(p, j, k + 1),
            ]
        elif a == 1:
            q = j
            expect = [
                cc.idx_fx(i, q - 1, k), cc.idx_fx(i, q, k),
                cc.idx_fx(i + 1, q - 1, k), cc.idx_fx(i + 1, q, k),
                cc.idx_fz(i, q - 1, k), cc.idx_fz(i, q, k),
                cc.idx_fz(i, q - 1, k + 1), cc.idx_fz(i, q, k + 1),
            ]
        else:
            r = k
            expect = [
                cc.idx_fx(i, j, r - 1), cc.idx_fx(i, j, r),
                cc.idx_fx(i + 1, j, r - 1), cc.idx_fx(i + 1, j, r),
                cc.idx_fy(i, j, r - 1), cc.idx_fy(i, j, r),
                cc.idx_fy(i, j + 1, r - 1), cc.idx_fy(i, j + 1, r),
            ]
        assert list(samples.h_face_index[n]) == [int(v) for v in expect], (
            f"sample {n} (face {face}) slots disagree with the hand table")


def test_h_stencil_centroid_is_the_sample_point():
    """One cell centre transversely, two half cells normally: mean == sample."""
    grid, cc, samples = _interior()
    pos = {a: {kind: _flat_positions(grid, cc, a, kind)
               for kind in ("edge", "face")} for a in range(3)}
    idx = samples.h_face_index
    off = {0: cc.off_fx, 1: cc.off_fy, 2: cc.off_fz}
    normal_axis = np.asarray(samples.face_id) // 2
    for a in range(3):
        tang = [b for b in range(3) if b != a]
        sel = normal_axis == a
        for slot_axis, component in ((0, tang[0]), (1, tang[1])):
            block = idx[sel, 4 * slot_axis:4 * slot_axis + 4]
            points = pos[component]["face"][block - off[component]]
            centroid = points.mean(axis=1)
            assert np.allclose(centroid, samples.coordinates[sel], atol=1e-12), (
                f"face {a}-normal, component {component}: stencil centroid is "
                f"not the sample point")


def test_h_stencil_is_one_sided_on_the_domain_boundary():
    """At the boundary the normal pair collapses and the sample is half a cell off."""
    grid, cc, samples = _complex()
    idx = samples.h_face_index
    normal_axis = np.asarray(samples.face_id) // 2
    z_faces = np.flatnonzero(normal_axis == 2)
    assert z_faces.size > 0
    pos = _flat_positions(grid, cc, 0, "face")
    zc = 0.5 * (np.asarray(grid.z)[1:] + np.asarray(grid.z)[:-1])
    for i in z_faces:
        # both tangential components: H_x from FX (slots 0-3), H_y from FY (4-7)
        assert idx[i, 0] == idx[i, 1]
        assert idx[i, 4] == idx[i, 5]
        centroid_z = pos[idx[i, 0:2] - cc.off_fx].mean(axis=0)[2]
        assert np.isclose(centroid_z, zc[np.argmin(np.abs(zc - centroid_z))])
        assert abs(centroid_z - samples.coordinates[i, 2]) == pytest.approx(
            0.5 * H, abs=1e-12)


def _flat_positions_from_shape(grid, shape):
    """Positions of every entry of one block, in block-local flat order.

    ``shape`` is ``grid.face_shape(axis)`` / ``grid.edge_shape(axis)``, i.e. the
    xyz-ordered shape of the block.  Which block axis is node placed and which
    is cell centred is *read off that shape* against the grid's own coordinate
    arrays -- an axis with ``n + 1`` entries sits on node planes, one with ``n``
    entries on cell centres -- rather than assumed here.
    """
    node, mid = _nodes_mid(grid)
    comps = []
    for b, name in enumerate("xyz"):
        if shape[b] == node[name].size and node[name].size != mid[name].size:
            comps.append(node[name])
        elif shape[b] == mid[name].size:
            comps.append(mid[name])
        else:
            raise AssertionError(
                f"block axis {name} of shape {tuple(shape)} matches neither "
                f"{node[name].size} node planes nor {mid[name].size} centres")
    return np.stack(np.meshgrid(*comps, indexing="ij"), axis=-1).reshape(-1, 3)


def _block_of(flat, offsets, sizes):
    """Which component block of the flat field vector holds each index.

    Read off the ``CellComplex`` block offsets alone: the blocks are contiguous
    ranges, so membership identifies the component without knowing which slot
    of a group is "supposed" to hold which component.
    """
    flat = np.asarray(flat, dtype=np.int64)
    out = np.full(flat.shape, -1, dtype=np.int64)
    for b, (off, n) in enumerate(zip(offsets, sizes)):
        out[(flat >= off) & (flat < off + n)] = b
    assert np.all(out >= 0), "a flat index fell in no block of the field vector"
    return out


def _index_on(planes, value):
    """Index of ``value`` in a 1-D coordinate array, or ``-1`` if absent."""
    d = np.abs(np.asarray(planes, dtype=float) - float(value))
    i = int(np.argmin(d))
    return i if d[i] <= 1e-12 else -1


@pytest.mark.parametrize("case", ["interior", "boundary"])
def test_stencil_slot_order_is_forced_by_geometry_alone(case):
    """Slot order follows from *where the faces are* -- no table, no convention.

    The hand table in :func:`test_h_face_index_matches_hand_table` encodes the
    same convention the module does, so on its own it cannot catch a
    *transposed* pair: the centroid test sees the same four points, and an
    affine gather is reproduced exactly by any centred average, so both are
    blind to a permutation inside a four-slot group.  This test pins the
    arrangement a permutation breaks, using only ``grid.x/y/z``, the block
    shapes and the ``CellComplex`` offsets -- it never asks which slot is meant
    to hold what:

    * the four faces of a group average onto the sample point, except where the
      documented one-sided clamp leaves a residual of exactly half a cell
      across the box normal -- and the tangential residuals are zero always;
    * slots 0 and 1 are the *normal* pair: equal in both tangential
      coordinates, both at cell centres across the normal, one cell apart
      there, and straddling the sample plane;
    * slots 0 and 2 share the normal coordinate exactly (they are also cell
      centres there) and differ only across the component's own direction,
      where both sit on adjacent node planes.  That is what makes the pair
      0-1 the normal pair and 0-2 the transverse one; a transposition of 1 and
      2 swaps those two properties and fails here;
    * the same two statements for ``edge_index``: each pair averages onto the
      sample, and its members differ only across the tangential direction that
      is neither the box normal nor the edge's own, on adjacent node planes.

    Both an interior box and one that reaches the domain boundary are covered,
    because the clamp is only reachable on the second.
    """
    grid, cc, samples = _interior() if case == "interior" else _complex()
    node, mid = _nodes_mid(grid)
    offs_f = (cc.off_fx, cc.off_fy, cc.off_fz)
    sizes_f = tuple(int(np.prod(grid.face_shape(a))) for a in "xyz")
    offs_e = (cc.off_ex, cc.off_ey, cc.off_ez)
    sizes_e = tuple(int(np.prod(grid.edge_shape(a))) for a in "xyz")
    pos_f = {a: _flat_positions_from_shape(grid, grid.face_shape("xyz"[a]))
             for a in range(3)}
    pos_e = {a: _flat_positions_from_shape(grid, grid.edge_shape("xyz"[a]))
             for a in range(3)}
    assert [pos_f[a].shape[0] for a in range(3)] == list(sizes_f)
    assert [pos_e[a].shape[0] for a in range(3)] == list(sizes_e)

    normal_axis = np.asarray(samples.face_id) // 2
    for a in range(3):
        sel = np.flatnonzero(normal_axis == a)
        assert sel.size > 0, f"no sample on the {('xyz')[a]}-normal faces"
        coords = samples.coordinates[sel]
        tangential = [b for b in range(3) if b != a]
        normal_planes = node["xyz"[a]]
        normal_centres = mid["xyz"[a]]

        # ---- the eight H faces: two groups of four --------------------
        h_comps = []
        for g in range(2):
            block = samples.h_face_index[sel, 4 * g:4 * g + 4]
            comp = _block_of(block, offs_f, sizes_f)
            assert np.all(comp == comp[:, :1]), (
                f"{case}, face {a}-normal, group {g}: the four slots are not "
                f"all in one component block")
            comp = int(comp[0, 0])
            h_comps.append(comp)
            assert comp != a, (
                f"{case}, face {a}-normal, group {g}: an H component along the "
                f"face normal is not tangential")
            pts = pos_f[comp][block - offs_f[comp]]
            where = (f"{case}, face {'xyz'[a]}-normal, group {g} "
                     f"(component {'xyz'[comp]})")

            # (2) the four positions average onto the sample point
            mean = pts.mean(axis=1)
            for b in tangential:
                assert np.allclose(mean[:, b], coords[:, b], rtol=0, atol=1e-12), (
                    f"{where}: the stencil is not centred on the sample in the "
                    f"{'xyz'[b]} direction")
            for m in range(pts.shape[0]):
                residual = abs(mean[m, a] - coords[m, a])
                if residual <= 1e-12:
                    continue
                # the documented clamp: the normal pair collapsed onto one
                # face, so the average sits half a cell inside the boundary
                p = _index_on(normal_planes, coords[m, a])
                assert 0 <= p < normal_planes.size, (
                    f"{where}: sample {sel[m]} is not on a node plane")
                half = 0.5 * (normal_planes[1] - normal_planes[0] if p == 0
                              else normal_planes[-1] - normal_planes[-2])
                assert residual == pytest.approx(half, abs=1e-12), (
                    f"{where}: normal residual {residual} is neither zero nor "
                    f"the half cell a one-sided stencil leaves")
                assert block[m, 0] == block[m, 1], (
                    f"{where}: a normal residual without the clamped pair is "
                    f"not the documented behaviour")

            # (3a) slots 0 and 1 are the normal pair
            p0, p1 = pts[:, 0], pts[:, 1]
            for b in tangential:
                assert np.allclose(p0[:, b], p1[:, b], rtol=0, atol=1e-12), (
                    f"{where}: slots 0 and 1 differ across the tangential "
                    f"{'xyz'[b]} direction, so they are not the normal pair")
            for m in range(pts.shape[0]):
                i0 = _index_on(normal_centres, p0[m, a])
                i1 = _index_on(normal_centres, p1[m, a])
                assert i0 >= 0 and i1 >= 0, (
                    f"{where}: slots 0 and 1 are not at cell centres across "
                    f"the normal")
                assert abs(i1 - i0) <= 1, (
                    f"{where}: slots 0 and 1 are {abs(i1 - i0)} cells apart "
                    f"across the normal, not a straddling pair")
                if i0 == i1:
                    continue  # one-sided: the same centre twice
                assert (min(p0[m, a], p1[m, a]) < coords[m, a]
                        < max(p0[m, a], p1[m, a])), (
                    f"{where}: slots 0 and 1 do not straddle the sample plane")

            # (3b) slots 0 and 2 differ only across the component
            p2 = pts[:, 2]
            assert np.allclose(p0[:, a], p2[:, a], rtol=0, atol=1e-12), (
                f"{where}: slots 0 and 2 differ across the box normal, so 0-2 "
                f"is not the transverse pair")
            other = [b for b in tangential if b != comp][0]
            assert np.allclose(p0[:, other], p2[:, other], rtol=0, atol=1e-12), (
                f"{where}: slots 0 and 2 differ across the {('xyz')[other]} "
                f"direction, which is neither the normal nor the component")
            for m in range(pts.shape[0]):
                j0 = _index_on(node["xyz"[comp]], p0[m, comp])
                j2 = _index_on(node["xyz"[comp]], p2[m, comp])
                assert j0 >= 0 and j2 >= 0, (
                    f"{where}: slots 0 and 2 are not on node planes along the "
                    f"component")
                assert abs(j2 - j0) == 1, (
                    f"{where}: slots 0 and 2 are {abs(j2 - j0)} cells apart "
                    f"along the component, not one")
        assert sorted(h_comps) == tangential, (
            f"{case}, face {a}-normal: the two H groups are not the two "
            f"tangential components")

        # ---- the four E edges: two pairs of two -----------------------
        e_comps = []
        for g in range(2):
            block = samples.edge_index[sel, 2 * g:2 * g + 2]
            comp = _block_of(block, offs_e, sizes_e)
            assert np.all(comp == comp[:, :1]), (
                f"{case}, face {a}-normal, edge pair {g}: the two slots are not "
                f"in one component block")
            comp = int(comp[0, 0])
            e_comps.append(comp)
            assert comp != a, (
                f"{case}, face {a}-normal, edge pair {g}: an edge along the face "
                f"normal does not bound the face")
            pts = pos_e[comp][block - offs_e[comp]]
            where = (f"{case}, face {'xyz'[a]}-normal, edge pair {g} "
                     f"(component {'xyz'[comp]})")

            # the pair averages onto the sample point in all three coordinates
            assert np.allclose(pts.mean(axis=1), coords, rtol=0, atol=1e-12), (
                f"{where}: the pair is not centred on the sample point")
            other = [b for b in range(3) if b not in (a, comp)][0]
            for b in (a, comp):
                assert np.allclose(pts[:, 0, b], pts[:, 1, b], rtol=0, atol=1e-12), (
                    f"{where}: the two edges differ across the {'xyz'[b]} "
                    f"direction, which is not transverse to them")
            assert np.all(np.abs(pts[:, 0, other] - pts[:, 1, other]) > 1e-12), (
                f"{where}: the two edges do not straddle the sample in the "
                f"{('xyz')[other]} direction")
            for m in range(pts.shape[0]):
                k0 = _index_on(node["xyz"[other]], pts[m, 0, other])
                k1 = _index_on(node["xyz"[other]], pts[m, 1, other])
                assert k0 >= 0 and k1 >= 0 and abs(k1 - k0) == 1, (
                    f"{where}: the pair is not one cell apart on node planes")
        assert sorted(e_comps) == tangential, (
            f"{case}, face {a}-normal: the two E pairs are not the two "
            f"tangential components")


# ----------------------------------------------------------------------
# metric
# ----------------------------------------------------------------------

def test_surface_areas_sum_to_the_box_area():
    grid, cc, samples = _complex()
    areas = surface_areas(cc, samples)
    assert areas.shape == (samples.face_id.size,)
    assert np.all(areas > 0.0)
    lx = grid.x[X1] - grid.x[X0]
    ly = grid.y[Y1] - grid.y[Y0]
    lz = grid.z[Z1] - grid.z[Z0]
    assert float(areas.sum()) == pytest.approx(
        2.0 * (lx * ly + ly * lz + lx * lz), rel=1e-14)
    assert np.allclose(areas, H * H)


def test_surface_areas_of_an_empty_surface_are_empty():
    grid, cc, samples = _complex()
    empty = SurfaceSamples(
        coordinates=np.zeros((0, 3)),
        normals=np.zeros((0, 3)),
        face_id=np.zeros((0,), dtype=np.int8),
        edge_index=np.zeros((0, 4), dtype=np.int64),
        face_index=np.zeros((0, 3), dtype=np.int64),
        h_face_index=np.zeros((0, 8), dtype=np.int64),
        snap_delta=np.zeros(6),
    )
    areas = surface_areas(cc, empty)
    assert areas.shape == (0,)
    with pytest.raises(ValueError, match="no samples"):
        SurfaceRecorder(empty, 1e6, cc=cc)


# ----------------------------------------------------------------------
# gathers
# ----------------------------------------------------------------------

def test_recorder_gathers_affine_fields_exactly():
    """A centred average reproduces an affine field exactly, at the sample point."""
    grid, cc, samples = _interior()
    rng = np.random.default_rng(0)
    a_mat = rng.normal(size=(3, 3))
    offset = rng.normal(size=3)

    e = np.zeros(cc.n_edges)
    for axis, off_e, n_e in ((0, cc.off_ex, cc.n_ex),
                             (1, cc.off_ey, cc.n_ey),
                             (2, cc.off_ez, cc.n_ez)):
        pos = _flat_positions(grid, cc, axis, "edge")
        assert pos.shape[0] == n_e
        e[off_e:off_e + n_e] = (pos @ a_mat.T + offset)[:, axis]
    h = np.zeros(cc.n_faces)
    for axis, off_f, n_f in ((0, cc.off_fx, cc.n_fx),
                             (1, cc.off_fy, cc.n_fy),
                             (2, cc.off_fz, cc.n_fz)):
        pos = _flat_positions(grid, cc, axis, "face")
        assert pos.shape[0] == n_f
        h[off_f:off_f + n_f] = (pos @ a_mat.T + offset)[:, axis]

    dt = 1e-12
    freq = 1e6
    rec = SurfaceRecorder(samples, freq, cc=cc)
    shim = _Shim(e, h, dt, time=dt)
    rec(dt, shim)
    assert rec.n_samples == 0  # the first call only primes the state
    shim.time = 2.0 * dt
    rec(shim)
    assert rec.n_samples == 1
    assert rec.t_last == pytest.approx(dt, rel=0, abs=0)

    weight = dt * np.exp(-2j * np.pi * freq * dt)
    analytic = samples.coordinates @ a_mat.T + offset
    normal_axis = np.asarray(samples.face_id) // 2
    for a in range(3):
        tang = [b for b in range(3) if b != a]
        sel = normal_axis == a
        for slot_axis, component in ((0, tang[0]), (1, tang[1])):
            # the gather is the raw sum; the de-bias and the metric/window
            # divides are what E_t and H_t apply on read, and this test is
            # about what accumulate() reads
            got_e = rec.E_t_raw[0, sel, slot_axis] / weight
            got_h = rec.H_t_raw[0, sel, slot_axis] / weight
            assert np.allclose(got_e, analytic[sel, component], atol=1e-12), (
                f"face {a}-normal slot {slot_axis}: E gather is not the "
                f"component at the sample point")
            assert np.allclose(got_h, analytic[sel, component], atol=1e-12), (
                f"face {a}-normal slot {slot_axis}: H gather is not the "
                f"component at the sample point")
            # and the public property is the physical field, not that sum: one
            # gather of a uniform metric over one half window
            unit = H * 0.5 * rec.n_samples * dt      # gather length x half window
            got_phys = rec.E_t[0, sel, slot_axis] / (weight / unit)
            assert np.allclose(got_phys, analytic[sel, component], atol=1e-12), (
                f"face {a}-normal slot {slot_axis}: E_t is not the physical "
                f"V/m component")


def test_half_step_averaging_is_exact():
    """The midpoint average leaves a pure cos(w dt/2) and no phase error.

    Measured on :attr:`SurfaceRecorder.H_t_raw`: the factor is a property of the
    accumulated sum, and ``H_t`` divides it out (tested separately).
    """
    grid, cc, samples = _complex()
    freq = 1e6
    omega = 2.0 * np.pi * freq
    cycles = 100.0

    def record(nsteps, dt):
        rec = SurfaceRecorder(samples, freq, cc=cc)
        e = np.zeros(cc.n_edges)
        h = np.zeros(cc.n_faces)
        shim = _Shim(e, h, dt)
        times = []
        for k in range(1, nsteps + 1):
            e[:] = np.cos(omega * k * dt)
            h[:] = np.cos(omega * (k - 0.5) * dt)
            shim.time = k * dt
            rec(shim)
            if k < nsteps:
                times.append(k * dt)
        times = np.asarray(times)
        ref = dt * np.sum(np.exp(-2j * np.pi * freq * times)
                          * np.cos(omega * times))
        single = dt * np.sum(np.exp(-2j * np.pi * freq * times)
                             * np.cos(omega * (times + 0.5 * dt)))
        return rec, ref, single, dt

    dt = 1.0 / (cycles * freq)
    rec, ref, single, dt = record(100, dt)
    assert rec.n_samples == 99
    assert rec.t_last == pytest.approx(99 * dt, rel=0, abs=1e-18)

    # the raw E entries are the plain rectangle-rule sum
    assert rec.E_t_raw[0, 0, 0] == pytest.approx(ref, rel=1e-12)
    assert np.allclose(rec.E_t_raw[0], ref, rtol=1e-12)

    # ... and E_t is that sum turned into a physical phasor: the gather length
    # and the half window are divided out
    unit = H * 0.5 * rec.n_samples * dt      # gather length x half window
    assert rec.E_t[0, 0, 0] == pytest.approx(ref / unit, rel=1e-12)
    assert np.allclose(rec.E_t[0], ref / unit, rtol=1e-12)

    # the H entries are the same sum times a pure real cos(w dt/2)
    assert rec.H_t_raw[0, 0, 0].imag == pytest.approx(0.0, abs=1e-12 * abs(ref))
    assert rec.H_t_raw[0, 0, 0].real == pytest.approx(
        ref.real * np.cos(0.5 * omega * dt), rel=1e-12)

    err_pair = abs(rec.H_t_raw[0, 0, 0] / ref - 1.0)
    err_single = abs(single / ref - 1.0)
    # the *exact* closed form of these two truncated sums: with th = w dt the
    # n_samples = 99 point window is one sample short of a whole number of half
    # periods, leaving  single/ref = exp(j th/2) + j sin(th/2)/((n-1)/2)
    th = omega * dt
    exact_single = abs(np.exp(0.5j * th) - 1.0
                       + 1j * np.sin(0.5 * th) / ((rec.n_samples - 1) / 2.0))
    assert err_single == pytest.approx(exact_single, rel=1e-12)
    # ... whose leading term is the ideal 2 sin(w dt/4) shown here; the rest is
    # the finite-window residual (2% at this n_samples)
    assert err_single == pytest.approx(2.0 * np.sin(0.25 * omega * dt),
                                       rel=3e-2)
    assert err_pair == pytest.approx(1.0 - np.cos(0.5 * omega * dt), rel=1e-10)
    assert err_pair < err_single / 50.0

    rec2, ref2, single2, dt2 = record(200, 0.5 * dt)
    err_pair2 = abs(rec2.H_t_raw[0, 0, 0] / ref2 - 1.0)
    err_single2 = abs(single2 / ref2 - 1.0)
    assert 3.9 < err_pair / err_pair2 < 4.1  # O(dt^2)
    assert 1.9 < err_single / err_single2 < 2.1  # O(dt)


def test_recorder_debias_removes_the_half_step_factor():
    """``H_t`` divides out cos(pi f dt); ``H_t_raw`` keeps it.

    ``dt = 1 / (4 f)`` makes ``pi f dt = pi / 4``, so the factor is
    ``cos(pi/4) = 1/sqrt(2)`` -- a 29 % effect, far outside any tolerance, and
    the corrected value has to come back exactly.  Nine calls emit eight
    samples at ``dt, 2 dt, ..., 8 dt``, which is two whole periods, so the
    rectangle-rule integral of a uniform tone is analytically ``4 * dt`` times
    the amplitude (``cos^2`` sums to ``n / 2 = 4``) and exactly real.
    """
    grid, cc, samples = _complex()
    freq = 1e6
    omega = 2.0 * np.pi * freq
    dt = 1.0 / (4.0 * freq)
    e_amp, h_amp = 3.0, 5.0

    rec = SurfaceRecorder(samples, freq, cc=cc)
    e = np.zeros(cc.n_edges)
    h = np.zeros(cc.n_faces)
    # the injected arrays are *fields* carried as grid voltages, so each is
    # weighted by its own metric: e_amp / h_amp are field amplitudes, and the
    # uniform field is not a uniform array on the H side (truncated L_dual)
    e_unit = _uniform_e(cc, np.ones(3))
    h_unit = _uniform_h(cc, np.ones(3))
    l_slot = _slot_dual_length(cc, samples)
    shim = _Shim(e, h, dt)
    for k in range(1, 10):
        e[:] = e_amp * np.cos(omega * k * dt) * e_unit
        h[:] = h_amp * np.cos(omega * (k - 0.5) * dt) * h_unit
        shim.time = k * dt
        rec(shim)

    assert rec.n_samples == 8
    # sanity: the raw E sum is the plain rectangle-rule integral, undivided
    # the raw sum is the voltage integral, so it carries the gather length
    assert rec.E_t_raw[0, 0, 0] == pytest.approx(
        4.0 * dt * e_amp * H, rel=1e-12)
    assert np.allclose(rec.E_t_raw, 4.0 * dt * e_amp * H, rtol=1e-12)

    # the injected edge voltage is ``e_amp L_e`` here (uniform metric 0.1), and
    # the read divides by that same L_e and the half window -- so e_amp is back
    unit = H * 0.5 * rec.n_samples * dt      # gather length x half window
    assert rec.E_t[0, 0, 0] == pytest.approx(e_amp, rel=1e-12)
    assert np.allclose(rec.E_t, e_amp, rtol=1e-12)

    # the raw sum is the same integral times cos(pi f dt) = cos(pi/4)
    bias = np.cos(np.pi * freq * dt)
    assert bias == pytest.approx(1.0 / np.sqrt(2.0), rel=1e-15)
    assert rec.H_t_raw[0, 0, 0].imag == pytest.approx(
        0.0, abs=1e-12 * 4.0 * dt * h_amp * H)
    assert rec.H_t_raw[0, 0, 0].real == pytest.approx(
        4.0 * dt * h_amp * bias * H, rel=1e-12)
    # slot 0 of sample 0 is on interior planes, so its mean L_dual is H; the
    # array as a whole is not, and l_slot says by how much
    assert np.allclose(rec.H_t_raw, 4.0 * dt * h_amp * bias * l_slot,
                       rtol=1e-12)

    # ... and H_t puts the de-bias back and turns the sum into a field -- 50 A/m
    assert rec.H_t[0, 0, 0] == pytest.approx(h_amp, rel=1e-12)
    assert np.allclose(rec.H_t, h_amp, rtol=1e-12)

    # the de-bias is exactly 1/cos(pi f dt) and nothing else: undo the metric
    # and half-window divides on the one slot whose mean L_dual is H and what is
    # left is that single real factor -- the division is pinned directly here
    window = 0.5 * rec.n_samples * dt
    meas = (rec.H_t[0, 0, 0] / rec.H_t_raw[0, 0, 0]) * (H * window)
    assert abs(meas * bias - 1.0) <= 1e-14

    # a correction that cannot be told apart from the raw sum is not a test
    assert not np.allclose(rec.H_t, rec.H_t_raw)


# ----------------------------------------------------------------------
# calling forms, and not touching the simulation
# ----------------------------------------------------------------------

def test_recorder_accepts_both_call_forms():
    grid, cc, samples = _complex()
    rng = np.random.default_rng(1)
    e0 = rng.normal(size=cc.n_edges)
    h0 = rng.normal(size=cc.n_faces)
    dt = 1e-12
    freqs = np.array([1e6, 3e6])

    a = SurfaceRecorder(samples, freqs, cc=cc)
    shim = _Shim(e0.copy(), h0.copy(), dt)
    for k in range(1, 4):
        shim.time = k * dt
        a(k * dt, shim)

    b = SurfaceRecorder(samples, freqs, cc=cc)
    shim_b = _Shim(e0.copy(), h0.copy(), dt)
    for k in range(1, 4):
        shim_b.time = k * dt
        b(shim_b)

    assert a.n_samples == b.n_samples == 2
    assert np.array_equal(a.E_t, b.E_t)
    assert np.array_equal(a.H_t, b.H_t)
    assert a.t_last == b.t_last


def test_recorder_leaves_the_stepper_untouched():
    grid, cc, samples = _complex()
    rng = np.random.default_rng(2)
    e0 = rng.normal(size=cc.n_edges)
    h0 = rng.normal(size=cc.n_faces)
    shim = _Shim(e0.copy(), h0.copy(), 1e-12)
    e_copy = shim.e.copy()
    h_copy = shim.h.copy()
    rec = SurfaceRecorder(samples, 1e6, cc=cc)
    for k in range(1, 5):
        shim.time = k * shim.dt
        rec(shim)
    assert np.array_equal(shim.e, e_copy)
    assert np.array_equal(shim.h, h_copy)
    assert rec.n_samples == 3


def test_recorder_runs_inside_a_real_time_loop():
    """As a ``run`` callback: K steps give K-1 samples, and the loop is unharmed."""
    from emfit.evolve import FITStepper, cfl_dt
    from emfit.materials import material_matrices

    grid, cc, samples = _complex()
    m_eps, m_mu = material_matrices(grid, cc)
    stepper = FITStepper(cc, m_eps, m_mu, dt=0.9 * cfl_dt(grid))
    rec = SurfaceRecorder(samples, 1e6, cc=cc)
    stepper.run(3, callback=rec)
    assert rec.n_samples == 2
    assert rec.t_last == pytest.approx(2 * stepper.dt, rel=1e-15)
    assert np.all(np.isfinite(rec.E_t))
    assert np.all(np.isfinite(rec.H_t))


# ----------------------------------------------------------------------
# what is refused
# ----------------------------------------------------------------------

@pytest.mark.parametrize("freqs", [[], [0.0], [-1e6], [np.nan], [np.inf], 0.0])
def test_recorder_rejects_unusable_frequencies(freqs):
    grid, cc, samples = _complex()
    with pytest.raises(ValueError, match="freqs|at least one frequency"):
        SurfaceRecorder(samples, freqs, cc=cc)


def test_recorder_requires_the_cell_complex():
    grid, cc, samples = _complex()
    bounds = HuygensBounds(xmin=grid.x[X0], xmax=grid.x[X1],
                           ymin=grid.y[Y0], ymax=grid.y[Y1],
                           zmin=grid.z[Z0], zmax=grid.z[Z1])
    with pytest.raises(ValueError, match="cc"):
        SurfaceRecorder(bounds, 1e6)
    with pytest.raises(ValueError, match="cc"):
        SurfaceRecorder(samples, 1e6)


def test_recorder_rejects_a_non_surface():
    grid, cc, samples = _complex()
    with pytest.raises(TypeError, match="HuygensBounds or SurfaceSamples"):
        SurfaceRecorder((0.0, 1.0, 0.0, 1.0, 0.0, 1.0), 1e6, cc=cc)


def test_recorder_accepts_a_request_and_conforms_it():
    grid, cc, _ = _complex()
    bounds = HuygensBounds(xmin=grid.x[X0], xmax=grid.x[X1],
                           ymin=grid.y[Y0], ymax=grid.y[Y1],
                           zmin=grid.z[Z0], zmax=grid.z[Z1])
    rec = SurfaceRecorder(bounds, np.float64(2e6), cc=cc)
    assert rec.n_surface == rec.samples.face_id.size
    assert rec.freqs.shape == (1,)
    assert rec.face_areas.shape == (rec.n_surface,)
    assert np.isnan(rec.t_last)
    assert rec.n_samples == 0
    assert rec.E_t.shape == (1, rec.n_surface, 2)
    assert rec.H_t.shape == (1, rec.n_surface, 2)


# ----------------------------------------------------------------------
# flux: the direct Poynting integral over the surface
# ----------------------------------------------------------------------
#
# A uniform, time-harmonic driver makes the surface power an exact number, so it
# can be asserted against a formula instead of against the implementation.  With
# E and H constant in space and one recorded frequency, every recorded entry is
# the field times ``PHASOR * exp(-j w dt)``.  The gather sums the voltages
# ``E . L_e`` and ``H . L_dual``; reading an entry back divides by that same
# mean length and by the half window ``dt / 2`` of one sample, which is where
# the factor 2 comes from -- ``PHASOR = 2``, dimensionless, because a driver
# that is constant in time has no ``cos(w dt)`` (that factor belongs to a tone).
# ``H_t``
# already has the ``cos(pi f dt)`` of the half-step average divided out on
# read, so nothing is de-biased a second time here.  The phase cancels in
# ``0.5 Re(E_t x conj(H_t))``, so a face of area ``A`` and normal ``n`` gives
# ``0.5 (E x H) . n A PHASOR^2`` -- no ``dt^2``, no metric, and area once.

FLUX_FREQ = 1e6
FLUX_DT = 1e-7
E_CONST = np.array([3.0, -2.0, 5.0])
H_CONST = np.array([7.0, 1.5, -4.0])
#: The half-step de-bias H_t divides out: 0.9510565162951535 at this step.
DEBIAS = float(np.cos(np.pi * FLUX_FREQ * FLUX_DT))
#: ``(E x H)_z``, the only Poynting component a z-normal face can see.
S_Z = float(np.cross(E_CONST, H_CONST)[2])
#: ``|E_t|`` per unit injected field value: dimensionless, exactly 2 here (the
#: gather length and the half window ``dt / 2`` cancel, and a constant-in-time
#: driver has no ``cos(w dt)`` -- that factor belongs to a tone only).
PHASOR = 2.0
#: The left-over phase of a single recorded entry: ``exp(-j w t)`` at ``t = dt``.
PHASE = np.exp(-2j * np.pi * FLUX_FREQ * FLUX_DT)


def _edge_length(cc, axis):
    """``L_e`` of every edge of one block, shape ``edge_shape(axis)``.

    Built by gathering the 1-D widths with ``np.indices``: the *route* is
    deliberately different from the ``reshape`` broadcast the production code
    uses, so a mis-aligned broadcast there cannot hide behind a matching one
    here.  The numbers are the same grid metric.
    """
    grid = cc.grid
    k = np.indices(grid.edge_shape(axis))["xyz".index(axis)].ravel()
    return np.asarray(grid.widths(axis), dtype=float)[k]


def _face_dual_length(cc, axis):
    """``L_dual`` of every face of one block, shape ``face_shape(axis)``.

    The dual length is the length the ``H`` unknown is a voltage over, i.e. the
    ``L_dual`` of ``m_mu = mu0 A_f / L_dual``.  On a bounded axis
    :meth:`Grid.dual_widths` truncates the two outer node planes to half a
    cell, so this array is *not* uniform even on a uniform grid.  Gathered with
    ``np.indices``, again independently of the production broadcast.
    """
    grid = cc.grid
    k = np.indices(grid.face_shape(axis))["xyz".index(axis)].ravel()
    return np.asarray(grid.dual_widths(axis), dtype=float)[k]


def _slot_dual_length(cc, samples):
    """Mean ``L_dual`` behind each ``H_t`` slot, ``(N, 2)``.

    The four faces of one slot are averaged as voltages, so the field is that
    mean voltage over this mean length.  Resolved from the raw face indices, so
    this is the independent counterpart of
    :func:`emfit.huygens_fields._metric_means`.
    """
    face_len = np.concatenate([_face_dual_length(cc, a) for a in "xyz"])
    i = np.asarray(samples.h_face_index, dtype=np.intp)
    return np.stack((face_len[i[:, :4]].mean(axis=1),
                     face_len[i[:, 4:]].mean(axis=1)), axis=1)


def _uniform_e(cc, vec):
    """A spatially uniform ``E`` *field* written into the three edge blocks.

    The grid unknown is the edge voltage ``E . L_e``, so a uniform field is a
    length-weighted array.  Spelled out rather than left implicit in the
    fixture's uniform mesh.
    """
    e = np.zeros(cc.n_edges)
    for axis, off, n in ((0, cc.off_ex, cc.n_ex),
                         (1, cc.off_ey, cc.n_ey),
                         (2, cc.off_ez, cc.n_ez)):
        e[off:off + n] = vec[axis] * _edge_length(cc, "xyz"[axis])
    return e


def _uniform_h(cc, vec):
    """A spatially uniform ``H`` *field* written into the three face blocks.

    The dual magnetic voltage is ``H . L_dual``, and ``L_dual`` is truncated on
    the outer node planes, so the array of a uniform field is genuinely
    non-uniform there -- writing ``vec[axis]`` straight into the block would
    describe a field that is 2x larger on those planes.
    """
    h = np.zeros(cc.n_faces)
    for axis, off, n in ((0, cc.off_fx, cc.n_fx),
                         (1, cc.off_fy, cc.n_fy),
                         (2, cc.off_fz, cc.n_fz)):
        h[off:off + n] = vec[axis] * _face_dual_length(cc, "xyz"[axis])
    return h


def _record(cc, samples):
    """Record the uniform driver twice, i.e. form exactly one spectral sample."""
    e = _uniform_e(cc, E_CONST)
    h = _uniform_h(cc, H_CONST)
    # constant-in-time driver: no midpoint-average attenuation exists for the
    # de-bias to remove, so this record is taken raw (see H_t docstring)
    rec = SurfaceRecorder(samples, FLUX_FREQ, cc=cc, debias=False)
    rec(FLUX_DT, _Shim(e, h, FLUX_DT, time=FLUX_DT))
    rec(_Shim(e, h, FLUX_DT, time=2.0 * FLUX_DT))
    assert rec.n_samples == 1
    assert rec.dt == FLUX_DT
    return rec


def _subset(samples, keep):
    """``samples`` restricted to the entries where ``keep`` is true."""
    keep = np.asarray(keep, dtype=bool)
    return SurfaceSamples(
        coordinates=np.asarray(samples.coordinates)[keep],
        normals=np.asarray(samples.normals)[keep],
        face_id=np.asarray(samples.face_id)[keep],
        edge_index=np.asarray(samples.edge_index)[keep],
        face_index=np.asarray(samples.face_index)[keep],
        h_face_index=np.asarray(samples.h_face_index)[keep],
        snap_delta=samples.snap_delta)


def _flipped(samples):
    """The same surface with every outward normal reversed."""
    return SurfaceSamples(
        coordinates=np.asarray(samples.coordinates),
        normals=-np.asarray(samples.normals),
        face_id=np.asarray(samples.face_id),
        edge_index=np.asarray(samples.edge_index),
        face_index=np.asarray(samples.face_index),
        h_face_index=np.asarray(samples.h_face_index),
        snap_delta=samples.snap_delta)


def _power(area):
    """``0.5 (E x H) . z * area * PHASOR^2``: power through +z, in W."""
    return 0.5 * area * S_Z * PHASOR ** 2


def _flux_scale(rec):
    """A tolerance scale for a cancelling sum: the size of one term, in W."""
    return (0.5 * PHASOR ** 2 * np.linalg.norm(E_CONST)
            * np.linalg.norm(H_CONST) * float(np.sum(rec.face_areas)))


def test_flux_of_a_closed_surface_is_zero():
    """A closed box in a uniform field lets no net power through it."""
    grid, cc, samples = _complex()
    rec = _record(cc, samples)
    face_id = np.asarray(samples.face_id)
    assert rec.n_surface == 16
    assert sorted(np.unique(face_id).tolist()) == [0, 1, 2, 3, 4, 5]
    assert float(np.sum(rec.face_areas)) == pytest.approx(0.16, rel=1e-15)

    # every face contributes 0.5 (E x H) . n A PHASOR^2 and the six
    # faces cancel in pairs; nothing else can make this sum small, so the
    # tolerance is the rounding of one term
    assert rec.flux.shape == (1,)
    assert rec.flux.dtype == np.float64
    assert abs(rec.flux[0]) <= 1e-12 * _flux_scale(rec)
    # and it is the sum of the recorded per-face integrand, not a separate path
    # two different summation routes cancel to different last bits, so the
    # tolerance is scaled by the size of one face term instead of pinned to 0
    np.testing.assert_allclose(rec.flux[0], 0.5 * rec.flux_face[0].real.sum(),
                               rtol=1e-15,
                               atol=1e-12 * np.abs(rec.flux_face[0]).max())


def test_open_surface_carries_the_power_through_the_hole():
    """Drop the two +z faces and what crosses the rest is exactly -P."""
    grid, cc, samples = _complex()
    face_id = np.asarray(samples.face_id)
    zplus = face_id == 5
    assert np.count_nonzero(zplus) == 2
    open_samples = _subset(samples, ~zplus)
    hole_samples = _subset(samples, zplus)

    # the subset is a surface of its own: no +z sample survives in it
    assert np.count_nonzero(np.asarray(open_samples.face_id) == 5) == 0
    assert sorted(np.unique(np.asarray(open_samples.face_id)).tolist()) == [0, 1, 2, 3, 4]
    assert np.asarray(open_samples.face_id).size == 14
    assert np.asarray(hole_samples.face_id).size == 2

    area = 2 * H * H                      # the two 0.1 x 0.1 z-normal faces
    power = _power(area)
    np.testing.assert_allclose(power, 0.74, rtol=1e-12, atol=0.0)

    rec_open = _record(cc, open_samples)
    assert rec_open.n_surface == 14
    assert float(np.sum(rec_open.face_areas)) == pytest.approx(0.16 - area, rel=1e-15)
    # +z faces point out of the box and (E x H).z is positive, so a closed box
    # sent +P out through them and -P through the other five: the five alone
    # carry -P
    np.testing.assert_allclose(rec_open.flux[0], -power, rtol=1e-12, atol=0.0)

    rec_hole = _record(cc, hole_samples)
    assert rec_hole.n_surface == 2
    assert float(np.sum(rec_hole.face_areas)) == pytest.approx(area, rel=1e-15)
    np.testing.assert_allclose(rec_hole.flux[0], power, rtol=1e-12, atol=0.0)

    # the recorded phasors are the physical fields, not dt-weighted sums: this is
    # the units claim of the module, made at the level a caller reads
    n_hat = np.asarray(open_samples.normals, dtype=float)
    E_vec = _tangential_to_vector(rec_open.E_t, n_hat)[0]
    H_vec = _tangential_to_vector(rec_open.H_t, n_hat)[0]
    scale = PHASOR * PHASE
    # the reconstruction places only the *tangential* part of the field (the
    # normal component is not recorded), so the reference is the projection
    E_par = E_CONST - (n_hat @ E_CONST)[:, None] * n_hat
    H_par = H_CONST - (n_hat @ H_CONST)[:, None] * n_hat
    assert np.abs(E_vec - scale * E_par).max() <= 1e-13 * np.abs(scale * E_par).max()
    assert np.abs(H_vec - scale * H_par).max() <= 1e-13 * np.abs(
        scale * H_par).max()

    # the record is only readable later if it carries its own geometry, so the
    # archive is written and read back here
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "surface.npz")
        rec_open.save_npz(path)
        with np.load(path) as data:
            assert data["schema_version"].dtype == np.int64
            assert int(data["schema_version"]) == 1
            assert data["stray"].dtype == np.bool_ and not bool(data["stray"])
            assert float(data["dt"]) == FLUX_DT
            for key in ("dx", "dy", "dz"):
                assert float(data[key]) == pytest.approx(H, rel=1e-12)
            assert np.allclose(data["freqs"], [FLUX_FREQ], rtol=0, atol=0)
            assert data["E_t"].shape == (1, 14, 2)
            assert data["H_t"].shape == (1, 14, 2)
            assert data["J_s"].shape == (1, 14, 3)
            assert data["M_s"].shape == (1, 14, 3)
            assert data["flux_face"].shape == (1, 14)
            assert data["dA"].shape == (14,)
            assert data["normals"].shape == (14, 3)
            assert np.allclose(data["dA"], rec_open.dA)
            assert np.allclose(data["flux"], rec_open.flux)
            assert "cos(pi f dt)" in str(data["colocation_rule"])

        # nothing recorded yet: the archive would be zeros with no dt, so it is
        # refused rather than written, and the refusal names the reason
        fresh = SurfaceRecorder(open_samples, FLUX_FREQ, cc=cc)
        with pytest.raises(ValueError, match="nothing recorded"):
            fresh.save_npz(os.path.join(tmp, "empty.npz"))
        fresh.save_npz(os.path.join(tmp, "stray.npz"), stray=True)
        with np.load(os.path.join(tmp, "stray.npz")) as data:
            assert bool(data["stray"])
            assert np.isnan(float(data["dt"]))
            assert np.allclose(data["flux"], 0.0, rtol=0, atol=0)


def test_flux_absolute_level_on_a_graded_grid():
    """On a graded mesh a face area counted twice is a factor, not round-off.

    Every flux test above integrates over a uniform mesh, where ``dA`` is the
    same number on every sample: there the total is ``P`` times the number of
    faces, and the area could be applied twice (``h^2`` instead of ``h``), or
    replaced by a single nominal ``h^2``, and the sum would still come out as a
    plausible power in the right units -- wrong by a pure scale factor that no
    tolerance on a scale-free comparison can see.  A graded mesh removes that
    freedom, because the area is a per-face number: here the cell width grows by
    ``1.025`` per cell, so ``dA`` spans ``1.025**(2*18) = 2.43`` from the
    coarsest face to the finest and the exact answer is ``sum(dA)`` when the
    area is applied once, ``sum(dA**2)`` when it is applied twice.

    The driver is a spatially uniform field recorded raw (a constant-in-time
    driver has no half-step factor to de-bias), and the surface is a single open
    plane with outward ``+z`` normals.  The expectation is summed from the grid
    metric directly -- ``Grid.face_area_z`` at the plane's own node index -- so
    nothing on the expected side goes through the recorder's area helper.
    """
    n, ratio = 19, 1.025                   # 1.025**18 = 1.56 per cell width
    x = np.concatenate(([0.0], np.cumsum(ratio ** np.arange(n))))
    grid = Grid.nonuniform(x, x, x)
    cc = CellComplex(grid)
    bounds = HuygensBounds(
        xmin=grid.x[0], xmax=grid.x[n],
        ymin=grid.y[0], ymax=grid.y[n],
        zmin=grid.z[0], zmax=grid.z[n])
    samples = bounds.conform_to(cc)

    # keep the one plane whose normals point out of the box through +z
    zplus = np.asarray(samples.face_id) == 5
    assert np.count_nonzero(zplus) == n * n
    plane = _subset(samples, zplus)
    assert np.all(np.asarray(plane.normals) == np.array([0.0, 0.0, 1.0]))

    rec = _record(cc, plane)
    assert rec.n_surface == n * n

    # the areas carried by the surface are the grid's own areas of that plane
    dA = np.asarray(grid.face_area_z()[:, :, n]).ravel()
    assert dA.size == n * n
    np.testing.assert_allclose(np.sort(rec.face_areas), np.sort(dA),
                               rtol=1e-15, atol=0.0)
    # the mesh has to be graded enough for the test to be able to tell the
    # two candidate answers apart
    spread = float(dA.max() / dA.min())
    assert spread > 2.0, spread

    # per face: 0.5 (E x H).n A PHASOR^2, with one area -- not its square and
    # not a nominal h^2 -- and the fields themselves as the physical phasors
    np.testing.assert_allclose(np.sort(rec.flux_face[0].real),
                               np.sort(PHASOR ** 2 * S_Z * dA),
                               rtol=1e-14, atol=0.0)
    # and in total: 0.5 S_z PHASOR^2 sum(dA), the areas summed off the grid
    expected = 0.5 * S_Z * PHASOR ** 2 * dA.sum()
    assert expected > 1e4                      # not a cancellation-driven test
    np.testing.assert_allclose(rec.flux[0], expected, rtol=1e-13, atol=0.0)


def test_flux_sign_follows_the_normal():
    """Flip every normal and the same field carries the power the other way."""
    grid, cc, samples = _complex()
    face_id = np.asarray(samples.face_id)
    zplus = face_id == 5
    open_samples = _subset(samples, ~zplus)
    open_flipped = _flipped(open_samples)
    assert np.allclose(np.asarray(open_flipped.normals),
                       -np.asarray(open_samples.normals))

    power = _power(2 * H * H)
    rec_open = _record(cc, open_samples)
    rec_flip = _record(cc, open_flipped)
    assert np.allclose(np.asarray(rec_flip.dA), np.asarray(rec_open.dA))
    # n_hat is the only thing that changed, so the only thing that may change
    # with it is the sign
    np.testing.assert_allclose(rec_open.flux[0], -power, rtol=1e-12, atol=0.0)
    np.testing.assert_allclose(rec_flip.flux[0], power, rtol=1e-12, atol=0.0)
    np.testing.assert_allclose(rec_flip.flux[0], -rec_open.flux[0], rtol=1e-15, atol=0.0)

    # a closed box is blind to this -- it sums the five -P faces against the two
    # +P ones either way, and zero is zero -- which is exactly why the sign has
    # to be pinned on an open surface
    rec_closed_flip = _record(cc, _flipped(samples))
    assert abs(rec_closed_flip.flux[0]) <= 1e-12 * _flux_scale(rec_closed_flip)


# ----------------------------------------------------------------------
# save_npz: the archive has to be readable without the code that wrote it
# ----------------------------------------------------------------------
#
# The export is the only surface a downstream consumer touches, and every way it
# can go wrong is quiet: a missing ``dt`` leaves a dt-weighted spectrum looking
# like bare numbers, a float ``schema_version`` breaks a reader's dispatch, and a
# key respelled with a hyphen is simply absent under attribute access.  So the
# tests below pin the refusal, the key set by name, the metadata types, and a
# bit-exact round trip.  A ``.npz`` stores floats verbatim, which is why the
# payload is compared with ``assert_array_equal`` and never with ``allclose``: a
# tolerance there would hide precisely the precision change it is meant to
# catch.

#: The seven metadata keys, i.e. the numbers, the version and the rule name.
NPZ_METADATA_KEYS = (
    "schema_version", "stray", "dt", "dx", "dy", "dz", "colocation_rule")

#: The payload: the geometry, the phasors and the power.
NPZ_PAYLOAD_KEYS = (
    "freqs", "coordinates", "normals", "face_id", "dA",
    "E_t", "H_t", "J_s", "M_s", "flux", "flux_face")


def test_save_npz_refuses_an_undriven_recorder(tmp_path):
    """No sample, no archive: zeros with no ``dt`` would read as a measurement."""
    grid, cc, samples = _complex()
    fresh = SurfaceRecorder(samples, FLUX_FREQ, cc=cc)
    assert fresh.n_samples == 0
    assert fresh.dt is None

    # the refusal is the only thing that may happen: a numpy warning raised
    # while composing the message is a leak, and an archive left on disk would
    # be read later as data
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        with pytest.raises(ValueError, match="nothing recorded"):
            fresh.save_npz(tmp_path / "empty.npz")
    assert list(tmp_path.iterdir()) == []


def test_save_npz_writes_the_documented_schema(tmp_path):
    """Every documented key, with its type, and a bit-exact payload."""
    grid, cc, samples = _complex()
    rec = _record(cc, samples)
    assert rec.n_samples == 1
    path = tmp_path / "surface.npz"
    rec.save_npz(path)
    assert path.exists()
    assert list(tmp_path.iterdir()) == [path]

    with np.load(path) as data:
        # the key set is the contract, so it is asserted as a set and then by
        # name: a missing key is absent, an extra one is undocumented API
        assert set(data.files) == set(NPZ_METADATA_KEYS) | set(NPZ_PAYLOAD_KEYS)
        for key in NPZ_METADATA_KEYS + NPZ_PAYLOAD_KEYS:
            assert key in data.files

        version = data["schema_version"]
        assert version.shape == ()
        assert np.issubdtype(version.dtype, np.integer)
        assert not np.issubdtype(version.dtype, np.floating)
        assert int(version) == 1

        assert data["stray"].dtype == np.bool_
        assert not bool(data["stray"])

        # dt is the recorder's own step, unrounded: it is the summing weight,
        # so a rounded or coerced dt silently rescales the whole archive
        assert float(data["dt"]) == rec.dt
        # the spacings are the grid's mean cell widths, exact on a uniform grid
        for axis, key in zip("xyz", ("dx", "dy", "dz")):
            np.testing.assert_allclose(float(data[key]),
                                       float(np.mean(grid.widths(axis))),
                                       rtol=1e-15, atol=0.0)

        # a rule name is only usable if it is text and can be used as a name:
        # the key itself is asserted hyphen free by the set equality above, and
        # the prose has to name the time levels the averaging actually used
        assert data["colocation_rule"].dtype.kind == "U"
        rule = str(data["colocation_rule"])
        assert isinstance(rule, str)
        assert "n-1/2" in rule and "n+1/2" in rule
        assert "integer step n" in rule
        assert "cos(pi f dt)" in rule
        assert "debias=False" in rule

        # the payload is compared bit-exactly, dtype for dtype
        for key, live in (("freqs", rec.freqs),
                          ("coordinates", rec.coordinates),
                          ("normals", rec.normals),
                          ("face_id", rec.face_id),
                          ("dA", rec.dA),
                          ("E_t", rec.E_t),
                          ("H_t", rec.H_t),
                          ("J_s", rec.J_s),
                          ("M_s", rec.M_s),
                          ("flux", rec.flux),
                          ("flux_face", rec.flux_face)):
            assert np.array_equal(data[key], live), key
            assert data[key].shape == np.shape(live), key



# ----------------------------------------------------------------------
# J_s and M_s: two cross products, and nothing else
# ----------------------------------------------------------------------
#
# These are the documented outputs, and they are pure algebra on the recorded
# phasors: no average, no quadrature, no tolerance.  So the expected arrays are
# built in the test from ``E_t``, ``H_t`` and ``n_hat`` with the same two
# formulas the docstrings state, and compared bit for bit.  A dropped minus or a
# swapped operand changes a sign, and ``assert_array_equal`` reports it as the
# array mismatch it is instead of hiding it under an ``rtol``.


def _tangential_to_vector(t2, n_hat):
    """Scatter ``(n_freq, N, 2)`` tangential slots to ``(n_freq, N, 3)``.

    Written out here rather than taken from the module: the claim under test is
    that the two recorded slots plus the outward normal determine the currents,
    so the test has to place the slots itself.  Slot 0 goes to the first axis
    that is not normal to the sample, slot 1 to the second, in ascending order.
    """
    t2 = np.asarray(t2)
    n_hat = np.asarray(n_hat)
    assert t2.shape[1:] == (n_hat.shape[0], 2)
    out = np.zeros((t2.shape[0], n_hat.shape[0], 3), dtype=np.complex128)
    for axis in range(3):
        # the conformed normals are axis aligned, so this is the sample's normal
        sel = np.abs(n_hat[:, axis]) > 0.5
        first, second = [b for b in range(3) if b != axis]
        out[:, sel, first] = t2[:, sel, 0]
        out[:, sel, second] = t2[:, sel, 1]
    return out


def test_equivalent_currents_are_the_two_cross_products():
    """``J_s = n x H_t`` and ``M_s = -(n x E_t)``, exactly, by algebra alone."""
    grid, cc, samples = _complex()
    rec = _record(cc, samples)
    n_hat = np.asarray(rec.n_hat)
    assert n_hat.shape == (rec.n_surface, 3)

    E_vec = _tangential_to_vector(rec.E_t, n_hat)
    H_vec = _tangential_to_vector(rec.H_t, n_hat)
    J_expected = np.cross(n_hat[None, :, :], H_vec)
    M_expected = -np.cross(n_hat[None, :, :], E_vec)   # the minus is the claim

    # a zero field would make every assertion below vacuous; the normal
    # component of a cross product with an axis aligned normal is exactly zero,
    # so the guard is the length of each current vector, not each component
    assert np.all(np.linalg.norm(J_expected, axis=-1) > 0.0)
    assert np.all(np.linalg.norm(M_expected, axis=-1) > 0.0)

    for name in ("J_s", "M_s"):
        value = getattr(rec, name)
        assert value.shape == (1, rec.n_surface, 3), name
        assert value.dtype == np.complex128, name

    # same inputs, same result, bit for bit
    np.testing.assert_array_equal(rec.J_s, J_expected)
    np.testing.assert_array_equal(rec.M_s, M_expected)
    # and the sign is asserted on its own, so a dropped minus fails on this line
    np.testing.assert_array_equal(rec.M_s, -np.cross(n_hat[None, :, :], E_vec))
    assert not np.array_equal(rec.M_s, np.cross(n_hat[None, :, :], E_vec))


# ----------------------------------------------------------------------
# the recorded phasors: one analytic signal, sampled at its own instant
# ----------------------------------------------------------------------
#
# ``accumulate`` multiplies by ``dt * exp(-j w t)``; reading an entry back
# divides by the gather length and the half window (``L_e * dt / 2`` here, and
# the ``L_e`` cancels the one the injected voltage carries), and
# ``H_t`` additionally divides the ``cos(pi f dt)`` of the half-step average out,
# out of ``H`` and out of nothing else.
# Both are claims about a *single* analytic signal: at one emitted sample the
# ``E`` and the ``H`` have to come back with the same scale and the same phase,
# and that phase has to be the one belonging to the sample instant.  Neither
# claim can be checked against the recorder's own output -- a self-consistent
# convention is self-consistently wrong -- so the expected value is written out
# from trigonometry below.
#
# Every way this breaks is quiet and around 5 %: drop the ``1/cos(pi f dt)`` and
# ``H`` comes back 1.0515x too big; average ``H`` at two integer steps instead
# of straddling one and, after the de-bias, it comes back 1.0515x too small;
# take the de-bias from ``freqs[0]`` for every band and the second band is 3.1x
# off at these frequencies.  Hence 1e-12 rather than "close".
#
# The field is spatially uniform on purpose.  A 2-edge and a 4-face midpoint
# average reproduce a uniform field *exactly*, so what is left in the residual
# is the temporal convention alone, which is the subject here.  A dipole field
# would lay an O(h^2) spatial-averaging error on top, and no tolerance below
# 1e-3 could then tell a broken half step from it.


def _tangential_pair(vec, n_hat):
    """The two tangential components of a uniform ``vec``, in slot order.

    Slot 0 is the first axis that is not the sample's normal, slot 1 the second,
    in ascending order -- the same placement ``_tangential_to_vector`` inverts.
    """
    axis_of = np.abs(np.asarray(n_hat)).argmax(axis=1)
    pairs = np.array([[b for b in range(3) if b != a] for a in axis_of])
    return np.asarray(vec, dtype=np.complex128)[pairs]


def _two_call_tone(cc, samples, freqs):
    """One emitted sample of a spatially uniform tone at ``FLUX_FREQ``.

    ``E`` holds ``E_CONST`` at the integer steps ``dt`` and ``2 dt``; ``H`` holds
    ``H_CONST`` at the half step below each, ``t - dt/2``, which is the stagger
    a FIT stepper hands the recorder.  The recorder emits the sample at
    ``t = dt``, the time of the first call.  Nothing is scaled here: what comes
    back is the ``dt * exp(-j w t)`` sum divided by the gather length and the
    half window, and for ``H`` additionally de-biased (see the test below).
    """
    omega = 2.0 * np.pi * FLUX_FREQ
    e = np.zeros(cc.n_edges)
    h = np.zeros(cc.n_faces)
    rec = SurfaceRecorder(samples, np.atleast_1d(freqs), cc=cc)
    # E_CONST / H_CONST are field amplitudes; the arrays are voltages, so the
    # metric is carried here and the recorded field is the amplitude itself
    e_unit = _uniform_e(cc, np.asarray(E_CONST, dtype=float))
    h_unit = _uniform_h(cc, np.asarray(H_CONST, dtype=float))
    for t in (FLUX_DT, 2.0 * FLUX_DT):
        e[:] = e_unit * np.cos(omega * t)
        h[:] = h_unit * np.cos(omega * (t - 0.5 * FLUX_DT))
        rec(t, _Shim(e, h, FLUX_DT, time=t))
    assert rec.n_samples == 1
    return rec


def test_recorded_phasors_are_co_located_in_time():
    """``E_t`` and ``H_t`` are the same analytic signal at the sample instant.

    One emitted sample is one rectangle-rule term, so the recorded value is
    ``dt * exp(-j w t_emit) / (dt / 2)`` times the field at ``t_emit = dt``
    -- for ``E`` as recorded, and for ``H`` only if the half-step average and the
    de-bias are both right, because ``H`` was fed at ``t - dt/2``.  The assertion
    is on the relative error of the whole ``(N, 2)`` array, per slot, so a wrong
    slot pairing or a normal-flipped projection cannot average itself away.
    """
    grid, cc, samples = _complex()
    n_hat = np.asarray(samples.normals, dtype=float)
    omega = 2.0 * np.pi * FLUX_FREQ
    t_emit = FLUX_DT

    rec = _two_call_tone(cc, samples, FLUX_FREQ)
    # one term: dt * cos(w t_emit) * exp(-j w t_emit)
    gamma = t_emit * np.cos(omega * t_emit) * np.exp(-1j * omega * t_emit)
    # the tone is not at a trivial phase, or the phases would not be tested
    assert abs(np.angle(gamma)) > 0.1
    # a recorded entry is that sum divided by the half window of one sample
    div = 0.5 * FLUX_DT
    expected_e = _tangential_pair(gamma * E_CONST / div, n_hat)
    expected_h = _tangential_pair(gamma * H_CONST / div, n_hat)
    assert expected_e.shape == (rec.n_surface, 2)
    assert np.all(np.abs(expected_e) > 0.0)

    for name, got, want in (("E_t", rec.E_t[0], expected_e),
                            ("H_t", rec.H_t[0], expected_h)):
        err = np.abs(got - want) / np.abs(want)
        assert err.max() <= 1e-12, (name, float(err.max()))

    # ... and they are the *same* signal: one scalar separates the two
    np.testing.assert_allclose(rec.H_t[0] / expected_h,
                               rec.E_t[0] / expected_e, rtol=0.0, atol=1e-12)

    # the tolerance is doing work: an un-de-biased H is cos(pi f dt) too big,
    # i.e. the raw sum this test would be asserting if H_t were not corrected
    l_slot = _slot_dual_length(cc, samples)
    assert np.abs(rec.H_t_raw[0] / div / (expected_h * l_slot)
                  - DEBIAS).max() <= 1e-12
    assert not np.allclose(rec.H_t_raw[0] / div, expected_h * l_slot, rtol=1e-6)

    # the de-bias belongs to each band separately: a scalar taken from freqs[0]
    # leaves the second band out by cos(pi f0 dt) / cos(pi f dt), which is 3.1x
    # here, so the check below cannot be passed by a shared factor
    freqs = np.array([FLUX_FREQ, 4.0 * FLUX_FREQ])
    spread = np.cos(np.pi * freqs[0] * FLUX_DT) / np.cos(np.pi * freqs[1] * FLUX_DT)
    assert abs(spread - 1.0) > 2.0
    multi = _two_call_tone(cc, samples, freqs)
    for k, f_k in enumerate(freqs):
        # what the midpoint average leaves for a tone at FLUX_FREQ is
        # cos(pi f dt), and what accumulate() divides out is cos(pi f_k dt)
        scale = np.cos(np.pi * FLUX_FREQ * FLUX_DT) / np.cos(np.pi * f_k * FLUX_DT)
        gamma_k = (scale * FLUX_DT * np.cos(omega * t_emit)
                   * np.exp(-1j * 2.0 * np.pi * f_k * t_emit))
        want = _tangential_pair(gamma_k * H_CONST / div, n_hat)
        err = np.abs(multi.H_t[k] - want) / np.abs(want)
        assert err.max() <= 1e-12, (float(f_k), float(err.max()))


# ----------------------------------------------------------------------
# the quadrature: a closed surface around a Hertzian dipole radiates P_rad
# ----------------------------------------------------------------------
#
# What this pins, and what it does not.  The fields are evaluated *analytically*
# at the patch centres, so nothing here exercises the ``E_t`` / ``H_t`` stencil
# gather -- that is what ``test_recorded_phasors_are_co_located_in_time`` and the
# real time loop are for.  What it pins is the other half of a power
# calculation, the one that has no internal consistency to lean on: that the
# midpoint rule over a closed surface converges to the radiated power at second
# order, i.e. that the patch area, the outward normal and the ``0.5 Re(E x H*)``
# convention are used the way the module documents.  A flipped normal, a
# missing ``0.5``, a conjugated ``E`` instead of ``H``, or an ``h`` instead of
# ``h^2`` all change the limit or its sign, and none of them raise.
#
# The reference is the textbook short-dipole field with ``I dl`` a current
# moment, whose closed-surface flux is exactly
# ``P_rad = eta k^2 (I dl)^2 / (12 pi)``.  Convergence is second order in the
# cell size, so each doubling of ``N`` must cut the error by four: that ratio is
# what the tolerances are derived from below, not a number chosen to fit.

DIPOLE_FREQ = 1e9                 # lambda = 0.2998 m
DIPOLE_MOMENT = 1e-3              # I dl, in A m
C_LIGHT = 299792458.0
MU0 = 4e-7 * np.pi
EPS0 = 1.0 / (MU0 * C_LIGHT ** 2)


def _dipole_fields(pos, freq, moment):
    """Analytic ``(E, H)`` phasors of a ``z``-directed Hertzian dipole.

    Each is ``(..., 3)`` complex128 at ``pos`` ``(..., 3)``.  The phasor
    convention is ``exp(-j k r)`` in space and ``exp(-j w t)`` in time, which is
    the one ``accumulate`` sums against, so ``0.5 Re(E x conj(H))`` is the time
    averaged Poynting vector.
    """
    pos = np.asarray(pos, dtype=float)
    k = 2.0 * np.pi * freq / C_LIGHT
    eta = np.sqrt(MU0 / EPS0)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    r = np.sqrt(x * x + y * y + z * z)
    rho = np.hypot(x, y)
    cos_th = z / r
    sin_th = rho / r
    # the axis is in the patch set for odd n only; the guard keeps the field
    # finite there instead of dividing by zero (the products vanish anyway)
    cos_ph = np.divide(x, rho, out=np.ones_like(x), where=rho > 0)
    sin_ph = np.divide(y, rho, out=np.zeros_like(y), where=rho > 0)
    kr = k * r
    env = np.exp(-1j * kr)
    h_phi = (1j * k * moment * sin_th / (4.0 * np.pi * r)) * (1.0 + 1.0 / (1j * kr)) * env
    e_th = (1j * k * eta * moment * sin_th / (4.0 * np.pi * r)) * (
        1.0 + 1.0 / (1j * kr) - 1.0 / kr ** 2) * env
    e_r = (eta * moment * cos_th / (2.0 * np.pi * r ** 2)) * (1.0 + 1.0 / (1j * kr)) * env
    r_hat = np.stack((x, y, z), axis=-1) / r[..., None]
    th_hat = np.stack((cos_th * cos_ph, cos_th * sin_ph, -sin_th), axis=-1)
    ph_hat = np.stack((-sin_ph, cos_ph, np.zeros_like(sin_ph)), axis=-1)
    return e_th[..., None] * th_hat + e_r[..., None] * r_hat, h_phi[..., None] * ph_hat


def _cube_patches(half, n):
    """Patch centres, outward normals and area of the cube ``[-half, half]^3``.

    ``n x n`` patches per face, all of equal area, no patch centre on a face
    edge -- so the closed surface is exactly the six faces and the sum is over
    ``6 n^2`` points.  ``n`` even keeps every centre off the ``z`` axis.
    """
    assert n % 2 == 0
    step = 2.0 * half / n
    centres = -half + (np.arange(n) + 0.5) * step
    uu, vv = (a.ravel() for a in np.meshgrid(centres, centres, indexing="ij"))
    positions, normals = [], []
    for axis, sign in ((0, 1), (0, -1), (1, 1), (1, -1), (2, 1), (2, -1)):
        first, second = [b for b in range(3) if b != axis]
        pos = np.zeros((uu.size, 3))
        pos[:, first] = uu
        pos[:, second] = vv
        pos[:, axis] = sign * half
        normal = np.zeros((uu.size, 3))
        normal[:, axis] = sign
        positions.append(pos)
        normals.append(normal)
    return np.concatenate(positions), np.concatenate(normals), step ** 2


def _dipole_flux(half, n):
    """``0.5 Re sum (E x H*) . n dA`` over the cube of half-width ``half``."""
    pos, normal, area = _cube_patches(half, n)
    e, h = _dipole_fields(pos, DIPOLE_FREQ, DIPOLE_MOMENT)
    poynting = np.cross(e, np.conj(h))
    return 0.5 * float(np.real(np.sum(poynting * normal, axis=1)).sum()) * area


def test_closed_surface_flux_converges_to_the_radiated_power():
    """The midpoint rule over a closed box converges to ``P_rad`` at order two.

    Measured on this machine, with ``lambda = 0.2998 m`` and a box of
    half-width 0.6 m: relative error ``+4.254e-04`` at ``N = 24``,
    ``+1.064e-04`` at ``N = 48`` and ``+2.66e-05`` at ``N = 96`` -- ratios
    4.00 and 4.00, the second order the rule is supposed to have.  The bounds
    below are that measurement with slack: the ratio is asserted in
    ``[3.2, 4.8]``, and the finest level is allowed ``1.2`` times the
    ``4x``-per-doubling prediction of the previous one (``1.064e-04 / 4 * 1.2 =
    3.19e-05`` versus ``2.66e-05`` measured).  A first-order rule gives 2, a
    wrong constant or a wrong normal gives a factor of order one.
    """
    k = 2.0 * np.pi * DIPOLE_FREQ / C_LIGHT
    eta = np.sqrt(MU0 / EPS0)
    p_rad = eta * k ** 2 * DIPOLE_MOMENT ** 2 / (12.0 * np.pi)
    assert p_rad == pytest.approx(4.38952755e-03, rel=1e-9)

    coarse, medium, fine = (24, 48, 96)
    flux = {n: _dipole_flux(0.6, n) for n in (coarse, medium, fine)}
    err = {n: (flux[n] - p_rad) / p_rad for n in flux}

    # outward normals on a closed surface: the power leaves, so the sum is
    # positive and within a cell's worth of quadrature of P_rad
    assert all(e > 0.0 for e in err.values())
    for n in flux:
        assert abs(err[n]) < 1e-3, (n, err[n])

    assert 3.2 <= err[coarse] / err[medium] <= 4.8, err[coarse] / err[medium]
    assert 3.2 <= err[medium] / err[fine] <= 4.8, err[medium] / err[fine]
    assert abs(err[fine]) <= abs(err[medium]) / 4.0 * 1.2, err[fine]

    # the answer is a property of the source, not of the box: a box of twice
    # the half-width sampled at the same cell size (h = 0.025 m both times)
    # reproduces it within the two quadrature errors added together
    same_cell = _dipole_flux(1.2, 2 * medium)
    assert abs(same_cell - flux[medium]) <= (abs(err[medium]) + abs(err[fine])) * p_rad

    # ... and the sign of the sum is the normals': turning them round negates
    # the flux bit for bit, so a "power" that survives that is not a flux
    pos, normal, area = _cube_patches(0.6, coarse)
    e, h = _dipole_fields(pos, DIPOLE_FREQ, DIPOLE_MOMENT)
    poynting = np.cross(e, np.conj(h))
    outward = 0.5 * float(np.real(np.sum(poynting * normal, axis=1)).sum()) * area
    inward = 0.5 * float(np.real(np.sum(poynting * -normal, axis=1)).sum()) * area
    assert inward == -outward
    assert outward == flux[coarse]

# ----------------------------------------------------------------------
# the same number, out of a real leapfrog run
# ----------------------------------------------------------------------
#
# The test above integrates an analytic field on a patch set; this one takes
# the number off the production recorder after an actual FDTD solve, so the
# whole chain is exercised: the PML-truncated grid, the soft-current source,
# the ``run`` callback, the phasor gather and the metric weighting.  Nothing
# is mocked, and the only input the answer is compared against is the
# radiated power of the dipole moment the run is discovered, after the fact,
# to be driving: ``I dl = amp h`` on one edge is a short current element of
# length ``h``, so ``P_rad = eta k^2 (amp h)^2 / (12 pi)``.
#
# Resolution and run length are chosen so that this is a *measurement* and
# not a coincidence: 20 cells per wavelength at 300 MHz, 12 cells of PML on
# each side, 40 steps per period, 12 periods to settle (the first four are
# the raised-cosine ramp of the source) and 8 periods to record, and two
# closed boxes of 6 and 8 cells half-width recorded in the *same* run so
# that box-to-box is a statement about the flux and not about the run.

@pytest.mark.slow
def test_flux_matches_the_dipole_power():
    """Production ``rec.flux`` lands on ``P_rad`` within 1.5% in a real run.

    The source is one soft-current edge at the centre of the domain, driven
    by a ramped cosine at ``f = 300 MHz``; ``I dl = amp h`` with
    ``amp = 1 A``, so the radiated power the run should show is the
    short-dipole ``P_rad``.  Both recorders are driven by one callback over
    one run (an 8-cell box and a 6-cell box half-width), which is the cheap
    half of the check: the two boxes see the same fields, so the only thing
    that can differ between them is the surface and the metrics.

    Measured here: ``+1.780e-03`` for the 6-cell box and ``+3.078e-03`` for
    the 8-cell one, ``-1.294e-03`` between them, in about 8 s (800 steps on
    a ``56^3`` grid).  Those residuals are *not* converged: the same run on a
    domain four cells narrower in each direction reads ``+6.713e-03`` and
    ``+8.128e-03``, because what is left is the dispersion of a
    20-cells-per-wavelength grid and not the recorder.  So 1.5% is an upper
    *bound* on a non-converged quantity, not an error estimate of it, and it
    is deliberately loose enough to survive that wander: a wrong ``dA``, a
    missing half-step de-bias or a flux taken with the wrong sense of the
    normals is a factor of order one, not a fraction of a percent.  The 1%
    box-to-box bound is the quadrature difference of the two surfaces, which
    is smaller still than either residual.
    """
    from emfit.evolve import FITStepper
    from emfit.materials import material_matrices
    from emfit.pml import PML

    freq = 300e6
    cells_per_lambda = 20
    h = C_LIGHT / freq / cells_per_lambda
    sub = 2 * cells_per_lambda                 # steps per period
    dt = 1.0 / (freq * sub)

    # half the domain in cells: the larger box (4 cells half-width), 12 cells
    # of air around it and a 12-cell PML wall on each side
    nh = 28
    n = 2 * nh
    grid = Grid.uniform(n, n, n, n * h, n * h, n * h)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(grid, cc)
    pml = PML(grid, thickness_cells=12, order=2, target=1e-6,
              axes=("x", "y", "z"), cc=cc)

    amp = 1.0                                  # A, on one primal edge
    w = 2.0 * np.pi * freq
    t_ramp = 4.0 / freq
    src = int(cc.idx_ez(nh, nh, nh))
    j = np.zeros(cc.n_edges)

    def drive(t):
        """Soft current on the centre edge: ramped cosine, ``j[src] = A``."""
        j[:] = 0.0
        if t < t_ramp:
            ramp = 0.5 * (1.0 - np.cos(np.pi * t / t_ramp))
        else:
            ramp = 1.0
        j[src] = amp * ramp * np.cos(w * t)
        return j

    def box(half):
        """Closed cube of ``half`` cells half-width, centred on the source."""
        lo, hi = nh - half, nh + half
        return HuygensBounds(xmin=grid.x[lo], xmax=grid.x[hi],
                             ymin=grid.y[lo], ymax=grid.y[hi],
                             zmin=grid.z[lo], zmax=grid.z[hi]).conform_to(cc)

    small = SurfaceRecorder(box(3), freq, cc=cc)
    large = SurfaceRecorder(box(4), freq, cc=cc)

    def record(stepper):
        small(stepper)
        large(stepper)

    stepper = FITStepper(cc, m_eps, m_mu, dt=dt, pml=pml)
    stepper.run((4 + 8) * sub, source=drive)
    stepper.run(8 * sub, source=drive, callback=record)

    eta = np.sqrt(MU0 / EPS0)
    k = 2.0 * np.pi * freq / C_LIGHT
    p_rad = eta * k ** 2 * (amp * h) ** 2 / (12.0 * np.pi)
    p_small = float(small.flux[0])
    p_large = float(large.flux[0])
    rel_small = p_small / p_rad - 1.0
    rel_large = p_large / p_rad - 1.0

    assert abs(rel_small) < 1.5e-2, rel_small
    assert abs(rel_large) < 1.5e-2, rel_large
    assert abs(p_small / p_large - 1.0) < 1.0e-2, p_small / p_large - 1.0
