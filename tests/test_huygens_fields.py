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
            got_e = rec.E_t[0, sel, slot_axis] / weight
            # the gather is the raw sum; the de-bias is a scale H_t applies on
            # read, and this test is about what accumulate() reads
            got_h = rec.H_t_raw[0, sel, slot_axis] / weight
            assert np.allclose(got_e, analytic[sel, component], atol=1e-12), (
                f"face {a}-normal slot {slot_axis}: E gather is not the "
                f"component at the sample point")
            assert np.allclose(got_h, analytic[sel, component], atol=1e-12), (
                f"face {a}-normal slot {slot_axis}: H gather is not the "
                f"component at the sample point")


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

    # the E entries are the plain rectangle-rule sum
    assert rec.E_t[0, 0, 0] == pytest.approx(ref, rel=1e-12)
    assert np.allclose(rec.E_t[0], ref, rtol=1e-12)

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
    shim = _Shim(e, h, dt)
    for k in range(1, 10):
        e[:] = e_amp * np.cos(omega * k * dt)
        h[:] = h_amp * np.cos(omega * (k - 0.5) * dt)
        shim.time = k * dt
        rec(shim)

    assert rec.n_samples == 8
    # sanity: E is the plain rectangle-rule sum, with nothing divided out
    assert rec.E_t[0, 0, 0] == pytest.approx(4.0 * dt * e_amp, rel=1e-12)
    assert np.allclose(rec.E_t, 4.0 * dt * e_amp, rtol=1e-12)

    # the raw sum is the same integral times cos(pi f dt) = cos(pi/4)
    bias = np.cos(np.pi * freq * dt)
    assert bias == pytest.approx(1.0 / np.sqrt(2.0), rel=1e-15)
    assert rec.H_t_raw[0, 0, 0].imag == pytest.approx(
        0.0, abs=1e-12 * 4.0 * dt * h_amp)
    assert rec.H_t_raw[0, 0, 0].real == pytest.approx(
        4.0 * dt * h_amp * bias, rel=1e-12)
    assert np.allclose(rec.H_t_raw, 4.0 * dt * h_amp * bias, rtol=1e-12)

    # ... and H_t puts it back
    assert rec.H_t[0, 0, 0] == pytest.approx(4.0 * dt * h_amp, rel=1e-12)
    assert np.allclose(rec.H_t, 4.0 * dt * h_amp, rtol=1e-12)

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
