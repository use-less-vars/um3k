"""Geometry tests for :mod:`emfit.huygens`.

Why these tests look the way they do
------------------------------------
The Huygens surface is the input to a near-to-far-field transform, so the two
things that must not be wrong are *where the samples are* and *that every point
of the surface is represented once*.  A duplicated sample silently doubles a
patch of equivalent current; a missing one leaves a hole the transform cannot
see.  Both show up in a pattern as a smooth, plausible-looking error, which is
exactly the kind of bug a test has to catch by construction instead of by
comparison against a reference.

So the tests are structural rather than numerical:

* the *request* (six metric bounds) is validated, including the two ways a
  number can look fine and still be wrong -- non-finite, and ``True``, which
  :func:`float` happily turns into ``1.0``;
* the *conformed surface* is checked to be closed (every sample lies on one of
  the six planes), duplicate-free (no two samples share a position) and
  complete (the per-face counts add up to the total);
* the *indices* are checked by decoding them, not by re-deriving them: the
  four ``edge_index`` entries of a sample are turned back into positions in
  metres and compared against the operator matrix ``C``, whose row for a face
  is exactly its four bounding edges.  A flat index is only useful if it can
  be consumed, so neither the offsets nor the neighbour steps are taken from
  the implementation.  ``face_index`` is checked to be in range and to be
  ``-1`` exactly in the two slots whose block cannot have a sample there -- a
  wrong sentinel is worse than an out-of-range index, because ``arr[-1]``
  reads the last element of the field vector silently.

The grid is 4x3x2 cells of side 0.1 m, so the whole module runs in well under a
second and every array can be eyeballed when a test fails.  The bounds are node
planes ``x[1]..x[3]``, ``y[1]..y[2]``, ``z[0]..z[2]``: aligned with the grid,
so the *aligned* box leaves ``snap_delta`` at exactly zero, and one test moves a
single face off the grid to check that exactly that face reports a delta and
warns.

A note on what "sample" means here
----------------------------------
``H`` lives on the *primal* faces of this complex (``FX`` shape ``(nx+1, ny,
nz)`` and so on), staggered as a node plane along the normal and cell centres
across it.  A conformed box is therefore a set of node planes, and a sample sits
at a cell centre in the two transverse directions -- which is why a box corner
does not appear twice: the two faces meeting there disagree on the transverse
staggering.  ``test_every_sample_lies_on_the_conformed_surface`` pins the
positions; the uniqueness assertion in
``test_surface_is_enumerated_exactly_once`` pins the "no corner bookkeeping
needed" claim.
"""

from __future__ import annotations

import numpy as np
import pytest

from emfit.grid import Grid
from emfit.huygens import FACE_NAMES, HuygensBounds, SurfaceSamples
from emfit.operators import CellComplex

NX, NY, NZ = 4, 3, 2
H = 0.1

#: node-plane indices the aligned test box uses, per axis
X0, X1 = 1, 3
Y0, Y1 = 1, 2
Z0, Z1 = 0, 2


def _complex():
    g = Grid.uniform(NX, NY, NZ, lx=NX * H, ly=NY * H, lz=NZ * H)
    return CellComplex(g)


def _box(cc):
    """The aligned test box: node planes X0..X1, Y0..Y1, Z0..Z1."""
    g = cc.grid
    return HuygensBounds(g.x[X0], g.x[X1], g.y[Y0], g.y[Y1], g.z[Z0], g.z[Z1])


def _expected_counts():
    """Samples per face: (transverse cells of one axis) x (the other)."""
    return np.array(
        [
            (Y1 - Y0) * (Z1 - Z0),  # xmin
            (Y1 - Y0) * (Z1 - Z0),  # xmax
            (X1 - X0) * (Z1 - Z0),  # ymin
            (X1 - X0) * (Z1 - Z0),  # ymax
            (X1 - X0) * (Y1 - Y0),  # zmin
            (X1 - X0) * (Y1 - Y0),  # zmax
        ],
        dtype=np.int64,
    )


# ----------------------------------------------------------------------
# 1. validation of the request
# ----------------------------------------------------------------------
def test_bounds_validation_rejects_non_finite_booleans_and_inverted_pairs():
    """A bound is a finite length in metres, and ``min < max``.

    ``True`` is rejected explicitly rather than coerced: ``float(True) == 1.0``
    means a flag passed where a distance belonged would otherwise produce a
    perfectly plausible 1 m surface.  Non-finite values are rejected because
    every later step compares against them (``argmin(abs(nodes - bound))``
    would return index 0 and the box would silently collapse).
    """
    good = (0.0, 0.3, 0.0, 0.2, 0.0, 0.1)
    assert HuygensBounds(*good).describe() == (
        "HuygensBounds(xmin=0 m, xmax=0.3 m, ymin=0 m, ymax=0.2 m, "
        "zmin=0 m, zmax=0.1 m)")
    assert "\n" not in HuygensBounds(*good).describe()

    # inverted and degenerate pairs, each named in the message
    with pytest.raises(ValueError, match="xmin"):
        HuygensBounds(0.3, 0.3, 0.0, 0.2, 0.0, 0.1)
    with pytest.raises(ValueError, match="ymin"):
        HuygensBounds(0.0, 0.3, 0.2, 0.1, 0.0, 0.1)
    with pytest.raises(ValueError, match="zmax"):
        HuygensBounds(0.0, 0.3, 0.0, 0.2, 0.1, 0.0)
    with pytest.raises(ValueError, match="xmax"):
        HuygensBounds(0.4, 0.2, 0.0, 0.2, 0.0, 0.1)

    # non-finite, named per field
    for bad, field in (
        (float("nan"), "xmin"),
        (float("inf"), "xmax"),
        (float("-inf"), "zmin"),
    ):
        values = list(good)
        values[FACE_NAMES.index(field)] = bad
        with pytest.raises(ValueError, match=field):
            HuygensBounds(*values)

    # booleans are not lengths
    with pytest.raises(TypeError, match="xmin"):
        HuygensBounds(True, 0.3, 0.0, 0.2, 0.0, 0.1)
    with pytest.raises(TypeError, match="ymax"):
        HuygensBounds(0.0, 0.3, 0.0, False, 0.0, 0.1)
    with pytest.raises(TypeError, match="zmin"):
        HuygensBounds(0.0, 0.3, 0.0, 0.2, np.True_, 0.1)

    # a box narrower than one cell conforms to a single plane: no surface
    cc = _complex()
    g = cc.grid
    with pytest.raises(ValueError, match="no cells"):
        HuygensBounds(g.x[X0] + 0.001, g.x[X0] + 0.002,
                      g.y[Y0], g.y[Y1], g.z[Z0], g.z[Z1]).conform_to(cc)


# ----------------------------------------------------------------------
# 2. shapes and dtypes
# ----------------------------------------------------------------------
def test_shapes_and_dtypes_of_every_array():
    """The consumer indexes these arrays directly, so their layout is the API.

    A ``face_id`` widened to ``int64`` or an ``edge_index`` that is ``int32``
    would still "work" in numpy and then break the moment it is used as an
    index into a large field vector, so the dtypes are asserted, not assumed.
    """
    cc = _complex()
    samples = _box(cc).conform_to(cc)
    n = int(samples.coordinates.shape[0])
    assert n == int(_expected_counts().sum()) == 16

    assert isinstance(samples, SurfaceSamples)
    assert samples.coordinates.shape == (n, 3)
    assert samples.coordinates.dtype == np.float64
    assert samples.normals.shape == (n, 3)
    assert samples.normals.dtype == np.float64
    assert samples.face_id.shape == (n,)
    assert samples.face_id.dtype == np.int8
    assert samples.edge_index.shape == (n, 4)
    assert samples.edge_index.dtype == np.int64
    assert samples.face_index.shape == (n, 3)
    assert samples.face_index.dtype == np.int64
    assert samples.h_face_index.shape == (n, 8)
    assert samples.h_face_index.dtype == np.int64
    assert samples.snap_delta.shape == (6,)
    assert samples.snap_delta.dtype == np.float64

    # frozen means frozen: the arrays are this object's, and read-only
    assert not samples.coordinates.flags.writeable
    assert not samples.edge_index.flags.writeable
    assert not samples.snap_delta.flags.writeable


# ----------------------------------------------------------------------
# 3. positions: on the conformed surface, and nowhere else
# ----------------------------------------------------------------------
def test_every_sample_lies_on_the_conformed_surface():
    """Every sample is on the box surface, and on the face ``face_id`` names.

    "On the surface" is checked twice: at least one coordinate hits a bound
    (the point is on the skin of the box, not inside it), and the coordinate
    along the face's own axis hits that face's plane exactly.  The second form
    is the one that would catch a transposed index -- a sample built from the
    wrong transverse cell can still land on *a* plane of the box.
    """
    cc = _complex()
    g = cc.grid
    samples = _box(cc).conform_to(cc)

    lo = np.array([g.x[X0], g.y[Y0], g.z[Z0]], dtype=float)
    hi = np.array([g.x[X1], g.y[Y1], g.z[Z1]], dtype=float)

    # inside the closed box: a cell-centre transverse coordinate is strictly
    # inside, a node-plane normal coordinate is exactly on a bound.
    assert np.all(samples.coordinates >= lo - 1e-12)
    assert np.all(samples.coordinates <= hi + 1e-12)

    on_a_plane = (np.abs(samples.coordinates - lo) < 1e-12) | (
        np.abs(samples.coordinates - hi) < 1e-12)
    assert np.all(on_a_plane.any(axis=1))

    axis = (samples.face_id // 2).astype(np.int64)
    upper = (samples.face_id % 2) == 1
    plane = np.where(upper, hi[axis], lo[axis])
    along = samples.coordinates[np.arange(samples.coordinates.shape[0]), axis]
    np.testing.assert_allclose(along, plane, rtol=0.0, atol=1e-12)

    # the two transverse coordinates are cell centres: strictly inside the box
    rows = np.arange(len(axis))
    for d in (1, 2):
        t = (axis + d) % 3
        values = samples.coordinates[rows, t]
        assert np.all(values > lo[t])
        assert np.all(values < hi[t])


# ----------------------------------------------------------------------
# 4. normals
# ----------------------------------------------------------------------
def test_normals_are_unit_axis_aligned_and_point_outward():
    """``J = n x H`` and ``M = -n x E`` inherit the sign of ``n`` directly.

    A sign flip here is invisible in the sample positions and turns the
    transform into the negative of the field, so "outward" is asserted by
    geometry (``(x - centre) . n > 0``) and not just by a lookup table.
    """
    cc = _complex()
    g = cc.grid
    samples = _box(cc).conform_to(cc)

    np.testing.assert_allclose(
        np.linalg.norm(samples.normals, axis=1), 1.0, rtol=0.0, atol=0.0)
    assert np.all(np.abs(samples.normals) <= 1.0)
    # axis aligned: exactly one non-zero entry per row, and it is +-1
    assert np.array_equal(np.count_nonzero(samples.normals, axis=1),
                          np.ones(len(samples.face_id), dtype=np.int64))
    assert np.all(np.abs(samples.normals.sum(axis=1)) == 1.0)

    # the non-zero entry is the face's own axis, with the face's own sign
    axis = (samples.face_id // 2).astype(np.int64)
    assert np.array_equal(np.argmax(np.abs(samples.normals), axis=1), axis)
    sign = samples.normals[np.arange(len(axis)), axis]
    expected_sign = np.where(samples.face_id % 2 == 1, 1.0, -1.0)
    assert np.array_equal(sign, expected_sign)

    # outward: the normal must have a positive projection away from the centre
    lo = np.array([g.x[X0], g.y[Y0], g.z[Z0]], dtype=float)
    hi = np.array([g.x[X1], g.y[Y1], g.z[Z1]], dtype=float)
    centre = 0.5 * (lo + hi)
    outward = np.sum((samples.coordinates - centre) * samples.normals, axis=1)
    assert np.all(outward > 0.0)


# ----------------------------------------------------------------------
# 5. closure: every point once
# ----------------------------------------------------------------------
def test_surface_is_enumerated_exactly_once():
    """Closed, complete and duplicate free.

    A Huygens surface is only a valid equivalent-current sheet if it is a
    surface: whole, and covered once.  Duplicates double a patch of current
    (a smooth, plausible-looking error), omissions leave a hole (ditto), so
    both are checked structurally here rather than inferred from a pattern.
    """
    cc = _complex()
    samples = _box(cc).conform_to(cc)

    counts = samples.face_counts()
    assert counts.shape == (6,)
    assert counts.dtype == np.int64
    assert np.array_equal(counts, _expected_counts())
    # the faces partition the samples: nothing unclaimed, nothing counted twice
    assert int(counts.sum()) == int(samples.coordinates.shape[0])
    assert len(np.unique(samples.face_id)) == 6
    used = np.bincount(samples.face_id, minlength=6)
    assert np.array_equal(used, counts)
    assert np.all(counts > 0)

    # no position appears twice -- in particular the four box corners, each
    # shared by three faces, are not repeated; on this stagger they cannot be,
    # because one face is at a cell centre where the other is at a node.
    keys = [tuple(np.round(row, 12)) for row in samples.coordinates]
    assert len(set(keys)) == len(keys)

    # the same question asked of the face indices: one primal face per sample,
    # no primal face claimed twice.  The *edges* are deliberately not required
    # to be unique -- a bounding edge borders up to four faces, so neighbouring
    # samples legitimately name the same edge, and a box edge is shared by two
    # box faces.
    faces = samples.face_index[samples.face_index >= 0]
    assert len(np.unique(faces)) == len(faces) == len(samples.coordinates)


# ----------------------------------------------------------------------
# 6. snapping
# ----------------------------------------------------------------------
def test_aligned_bounds_do_not_move_and_one_misaligned_face_does():
    """``snap_delta`` is the honest record of how far the surface moved.

    The aligned box must report *exactly* zero -- not a tolerance-passing
    epsilon, because a downstream weight computed from the requested plane and
    a field read from the conformed plane must agree to the last bit.  A single
    face moved by a fifth of a cell must report exactly that displacement, on
    exactly that face, and warn.
    """
    cc = _complex()
    g = cc.grid

    aligned = _box(cc).conform_to(cc)
    assert np.array_equal(aligned.snap_delta, np.zeros(6))

    # 0.02 m is a fifth of a cell: still nearest to the same node plane
    moved = HuygensBounds(g.x[X0] + 0.02, g.x[X1],
                          g.y[Y0], g.y[Y1], g.z[Z0], g.z[Z1])
    with pytest.warns(UserWarning, match="xmin"):
        shifted = moved.conform_to(cc)

    assert shifted.snap_delta[0] == pytest.approx(-0.02, abs=1e-12)
    assert np.array_equal(shifted.snap_delta[1:], np.zeros(5))
    # the request moved; the surface did not
    assert np.array_equal(shifted.coordinates, aligned.coordinates)
    assert np.array_equal(shifted.face_id, aligned.face_id)
    assert np.array_equal(shifted.edge_index, aligned.edge_index)
    assert np.array_equal(shifted.face_index, aligned.face_index)


# ----------------------------------------------------------------------
# 7. indices: decoded, not re-derived
# ----------------------------------------------------------------------
def _decode_edges(cc, flat):
    """Flat primal-edge indices -> ``(block name, (i, j, k))``.

    The block shapes and offsets are read off
    :class:`~emfit.operators.CellComplex`, which is where the flat layout is
    defined, and *not* off :mod:`emfit.huygens`: the decode has to be
    independent of the code under test or it could not fail when that code is
    wrong.
    """
    blocks = (
        ("EX", cc.off_ex, (cc.nx, cc.nyn, cc.nzn)),
        ("EY", cc.off_ey, (cc.nxn, cc.ny, cc.nzn)),
        ("EZ", cc.off_ez, (cc.nxn, cc.nyn, cc.nz)),
    )
    flat = np.asarray(flat)
    names = np.full(flat.shape, "", dtype="<U2")
    ijk = np.zeros(flat.shape + (3,), dtype=np.int64)
    seen = np.zeros(flat.shape, dtype=bool)
    for name, off, shape in blocks:
        size = int(np.prod(shape))
        here = (flat >= off) & (flat < off + size)
        assert not np.any(seen & here)      # a flat index lives in one block
        seen |= here
        names[here] = name
        ijk[here] = np.stack(np.unravel_index(flat[here] - off, shape), axis=1)
    assert np.all(seen)
    return names, ijk


def _edge_positions(cc, names, ijk):
    """Positions in metres of those edges, from the documented staggering."""
    g = cc.grid
    node = {a: np.asarray(getattr(g, a), dtype=float) for a in "xyz"}
    mid = {a: 0.5 * (node[a][1:] + node[a][:-1]) for a in "xyz"}
    i, j, k = ijk[..., 0], ijk[..., 1], ijk[..., 2]
    at = np.zeros(ijk.shape, dtype=float)
    ex, ey, ez = names == "EX", names == "EY", names == "EZ"
    at[ex] = np.stack([mid["x"][i[ex]], node["y"][j[ex]], node["z"][k[ex]]],
                      axis=1)
    at[ey] = np.stack([node["x"][i[ey]], mid["y"][j[ey]], node["z"][k[ey]]],
                      axis=1)
    at[ez] = np.stack([node["x"][i[ez]], node["y"][j[ez]], mid["z"][k[ez]]],
                      axis=1)
    return at


def _cell_step(cc, axis_per_row, index_per_row):
    """One cell width along ``axis_per_row[r]`` at ``index_per_row[r]``."""
    return np.array(
        [getattr(cc.grid, "xyz"[a])[n + 1] - getattr(cc.grid, "xyz"[a])[n]
         for a, n in zip(axis_per_row, index_per_row)],
        dtype=float,
    )


def test_edge_index_names_the_four_bounding_edges_of_each_face():
    """Decode the four flat indices and check the geometry they claim.

    The consumer's next step is the tangential ``E`` at the sample: the
    2-average of slots 0-1 and of slots 2-3.  That only works if the four
    indices really are the four edges bounding the sample's primal face, one
    cell apart, straddling the sample.  Asserting the slot formulas would only
    re-state the implementation, so each flat index is decoded back to
    ``(i, j, k)``, turned into a position in metres, and held against three
    independent facts: the face's own plane, the operator matrix ``C`` (whose
    row for a face is exactly the circulation about it), and the requirement
    that a pair average lands on the sample.
    """
    cc = _complex()
    samples = _box(cc).conform_to(cc)
    n = len(samples.face_id)
    rows = np.arange(n)

    assert samples.edge_index.shape == (n, 4)
    assert samples.edge_index.dtype == np.int64
    assert np.all(samples.edge_index >= 0)
    assert np.all(samples.edge_index < cc.n_edges)

    names, ijk = _decode_edges(cc, samples.edge_index)
    at = _edge_positions(cc, names, ijk).reshape(n, 4, 3)

    axis = (samples.face_id // 2).astype(np.int64)
    # the two transverse axes, ascending, excluding the face's own axis
    t1 = np.where(axis == 0, 1, 0)
    t2 = np.where(axis == 2, 1, 2)

    # (a) all four edges lie in the sample's face plane
    in_plane = np.repeat(samples.coordinates[rows, axis][:, None], 4, axis=1)
    np.testing.assert_allclose(at[rows, :, axis], in_plane,
                               rtol=0.0, atol=1e-12)

    # (b) they are four distinct edges
    for a in range(4):
        for b in range(a + 1, 4):
            assert np.all(np.any(at[:, a, :] != at[:, b, :], axis=1))

    # (c) they are exactly the four edges of the operator's circulation row
    #     for the sample's own face -- derived from C, not from this module
    C = cc.curl()
    face = samples.face_index[samples.face_index >= 0]
    assert face.shape == (n,)
    expected = np.zeros((n, 4), dtype=np.int64)
    for r in range(n):
        row = C.indices[C.indptr[face[r]]:C.indptr[face[r] + 1]]
        assert row.size == 4
        expected[r] = np.sort(row)
    assert np.array_equal(np.sort(samples.edge_index, axis=1), expected)

    # (d) slots 0-1 are the first transverse block, 2-3 the second
    block = np.array(("EX", "EY", "EZ"))
    assert np.array_equal(names[:, 0], names[:, 1])
    assert np.array_equal(names[:, 2], names[:, 3])
    assert np.array_equal(names[:, 0], block[t1])
    assert np.array_equal(names[:, 2], block[t2])

    # (e) each pair straddles the sample: its average *is* the sample point,
    #     which is what makes the 2-average a sample of E_t at the face centre
    for lo, hi in ((0, 1), (2, 3)):
        np.testing.assert_allclose(0.5 * (at[:, lo, :] + at[:, hi, :]),
                                   samples.coordinates,
                                   rtol=0.0, atol=1e-12)

    # (f) the two edges of a pair are one cell apart, lower index first, and
    #     the step is perpendicular to the normal: slots 0-1 step along the
    #     *second* transverse axis, slots 2-3 along the first
    for pair, step_axis in (((0, 1), t2), ((2, 3), t1)):
        step = at[:, pair[1], :] - at[:, pair[0], :]
        assert np.all(step[rows, axis] == 0.0)
        assert np.array_equal(np.count_nonzero(step, axis=1),
                              np.ones(n, dtype=np.int64))
        assert np.array_equal(np.argmax(np.abs(step), axis=1), step_axis)
        lower = ijk[:, pair[0], :][rows, step_axis]
        assert np.all(step[rows, step_axis] > 0.0)
        np.testing.assert_allclose(step[rows, step_axis],
                                   _cell_step(cc, step_axis, lower),
                                   rtol=0.0, atol=1e-15)

    # face_index keeps its sentinel: one live slot per sample, on its own axis
    present = samples.face_index >= 0
    assert np.all(samples.face_index[~present] == -1)
    assert np.all(samples.face_index[present] < cc.n_faces)
    assert np.array_equal(present.sum(axis=1), np.ones(n, dtype=np.int64))
    assert np.array_equal(np.argmax(present, axis=1), axis)


# ----------------------------------------------------------------------
# 8. a periodic axis carries a wrapped seam node that is not a layer
# ----------------------------------------------------------------------
def test_periodic_axis_does_not_snap_onto_the_wrapped_seam_plane():
    """``nodes[:layers]`` is what stops a bound landing on the seam duplicate.

    ``Grid`` keeps ``nx + 1`` coordinates on a periodic axis (the last is the
    first, wrapped) while ``grid.nodes("x")`` is ``nx``: the seam is not a
    separate point layer.  ``conform_to`` therefore searches only the first
    ``nodes(axis)`` coordinates.  Without that clamp a bound just inside the
    far end of the period snaps onto ``x[nx]`` -- the *duplicate* of the
    ``x[0]`` plane -- and the box silently spans the whole period, with a snap
    of the wrong size and sign.
    """
    g = Grid.uniform(NX, NY, NZ, lx=NX * H, ly=NY * H, lz=NZ * H,
                     periodic=(True, False, False))
    cc = CellComplex(g)
    assert g.is_periodic("x")
    assert g.nodes("x") == NX           # point layers: the seam is not one
    assert g.x.size == NX + 1           # ...but the coordinate array has it

    # 0.01 m inside either end of the period: x[0] is the nearest layer to the
    # lower bound, but the *seam duplicate* x[NX] is nearer to the upper bound
    # (0.01 m) than the true last layer x[NX-1] is (0.09 m).
    box = HuygensBounds(g.x[0] + 0.01, g.x[NX - 1] + 0.09,
                        g.y[Y0], g.y[Y1], g.z[Z0], g.z[Z1])
    with pytest.warns(UserWarning):
        samples = box.conform_to(cc)

    assert samples.snap_delta[0] == pytest.approx(-0.01, abs=1e-12)
    assert samples.snap_delta[1] == pytest.approx(-0.09, abs=1e-12)
    assert np.all(samples.coordinates[samples.face_id == 0, 0] == g.x[0])
    assert np.all(samples.coordinates[samples.face_id == 1, 0] == g.x[NX - 1])
    assert not np.any(samples.coordinates[:, 0] == g.x[NX])
