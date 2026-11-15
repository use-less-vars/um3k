"""The volume ARROW field: three colocated components, one lattice of arrows.

What is proven here is the compute half of the overlay, and it is a different
kind of claim from a picture: ``poc_app._volume_arrows`` is called directly with
the loader's own ``info`` dict, so a failure points at the layer that failed.

The claims, one per test:

* a UNIFORM field gives one identical shaft at every sampled cell - the lattice
  carries no per-cell state a uniform input cannot produce;
* each shaft keeps the field's OWN direction, normalised (so a sign reversal is
  visible), and the direction comes back out of two different magnitudes;
* the length is LINEAR in ``|E|`` - magnitudes 1 : 2 : 4 give lengths in the
  ratio 1 : 2 : 4 - and the peak arrow is exactly one arrow-cell long;
* ``stride`` really does select the lattice: exact arrow counts for 1, 2, 3, and
  2795 on the real 62 x 212 x 22 shape, which is ``ceil(n / stride)`` per axis
  and not ``floor``;
* arrows sit at CELL CENTRES - ``(i + 0.5) * cell_mm`` - and strictly inside the
  volume's extent, because that is where the colocation put the values;
* nothing drawable (no dict, no volume, zero everywhere, wrong shape, no cell
  size) returns EMPTY ``(0, 3)`` arrays rather than raising or returning None;
* a bad cell size (0, negative, NaN, infinity) and a bad stride (0, negative) are
  refused rather than silently clamped;
* the real dump survives end to end with finite points, finite shafts and no
  shaft longer than its own stride cell;
* pyvista builds one glyph per arrow from a POINT-data array;
* ``_volume_quiver_mesh`` - the seam run_web draws from - glyphs the REAL
  dump's whole field in one call, and its mesh carries exactly one glyph per
  arrow of that same lattice, measured against a one-arrow glyph;
* that mesh needs no repair before a renderer sees it: every vertex is finite
  and sits inside the dump's own extent plus one arrow length;
* the same seam returns None - not an empty mesh, not a raise - when there is
  no volume at all or the volume is zero everywhere, which is the branch that
  keeps run_web's checkbox honest on a dump with no vectors in it.
* the loader can DEFER the colocation (``e_raw=True``) and stash the raw edge
  vector instead; the deferred route glyphs the SAME mesh as the eager one -
  same point count, same cell count, same coordinates - so the saving is a
  delay and not a second answer;
* a dump with no ``e`` edge vector at all still loads under either flag: one
  stderr line, no volume key, no raw key, no raise - and the mesh seam then
  returns None, so run_web never even builds that checkbox.
* the seam SAYS why it drew nothing - the house ``[poc_app]`` stderr line in
  every branch - and on a forced failure it prints the exception and its
  traceback before returning None, because that is the only way an operator
  can tell "no vectors in this dump" from "the arrow path broke";
* the port-plane view is drawn BLACK, not white, because the plotter's
  background is white (a source check: the add_mesh call lives inside run_web's
  ``_show_volume_quiver`` closure, which needs a live trame page to reach);
* the port-plane LABEL admits that its x is the FALLBACK constant when the
  record carries no port plane, and is byte-identical to the recorded-x label
  otherwise;
* a port slice that cannot be drawn costs the SLICE and not the page: a stub
  plotter that refuses the image still gets the outline, the axes, the markers
  and both corner labels, so ``_draw_scene`` never raises out of that branch.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries tests/test_poc_mode_quiver.py adds, so `import
        # poc_app` resolves from server/poc_app.py
        sys.path.insert(0, _p)

# pyvista lives in the repo's own venv in this image (its bin/python is broken,
# the site-packages tree is not). Inert where it is installed normally. Only the
# glyph test below needs it, so the import is guarded inside that test: every
# other test here is numpy-only.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import poc_app  # noqa: E402  (sys.path above is why this import is not at the top)

STRIDE = poc_app.VOLUME_QUIVER_STRIDE  # 5, the shipped lattice
FRACTION = poc_app.VOLUME_QUIVER_MAX_LEN_FRACTION  # 0.9 of one arrow cell
DEFAULT_DUMP = REPO_ROOT / poc_app.DEFAULT_INPUT
#: One tenth of a millimetre: any small positive METRES value works, and a
#: sub-millimetre cell keeps every coordinate in this file easy to read.
CELL_M = 1.0e-4
CELL_MM = CELL_M * 1e3


def _info(volume, cell_m=CELL_M):
    """The loader's ``info`` dict, with only the two keys this helper reads."""
    return {poc_app.VOLUME_KEY: volume, "cell_m": cell_m}


def _uniform(shape, vector):
    """A volume whose every sample is the same ``vector``."""
    nx, ny, nz = shape
    return np.broadcast_to(np.asarray(vector, dtype=float), (nx, ny, nz, 3)).copy()


def _lengths(vectors):
    return np.sqrt(np.sum(vectors * vectors, axis=1))


def _samples(axis_n, stride):
    """The cell indices the arrow lattice keeps on an axis of ``axis_n`` cells."""
    return np.arange(0, axis_n, stride)


def test_a_uniform_field_gives_identical_arrows_at_every_sampled_cell():
    """One direction and one magnitude in; one identical shaft out, 12 times."""
    nx, ny, nz, stride = 4, 6, 3, 2
    volume = _uniform((nx, ny, nz), (1.0, -2.0, 2.0))
    points, vectors = poc_app._volume_arrows(_info(volume), stride=stride)
    # arange(0, 4, 2) holds 2 indices, arange(0, 6, 2) holds 3, arange(0, 3, 2)
    # holds 2, so 2 * 3 * 2 = 12 arrows. A count that came out 3 x 3 x 2 or
    # 4 x 6 x 3 would mean the stride was applied to something other than the
    # cell indices.
    assert points.shape == (12, 3)
    assert vectors.shape == (12, 3)
    # A uniform field cannot produce two different shafts: any scatter here means
    # the helper is mixing in per-cell state (an anchor, an index) that the
    # field does not contain.
    assert np.all(vectors == vectors[0])
    lengths = _lengths(vectors)
    assert np.all(lengths > 0.0)
    assert np.all(lengths == lengths[0])


def test_each_shaft_keeps_the_fields_own_direction():
    """Direction normalised per arrow, not per lattice."""
    direction = np.array([0.0, 3.0, 4.0])  # |d| = 5: deliberately NOT a unit vector
    unit = direction / np.linalg.norm(direction)
    nx, ny, nz = 2, 4, 2
    volume = np.zeros((nx, ny, nz, 3))
    # Two DIFFERENT magnitudes of the SAME direction, so a wrong normalisation
    # shows: normalising by the lattice peak instead of by each arrow would give
    # the weaker sample a longer shaft than its field justifies, and dividing the
    # shaft by its own length would then not return the unit vector.
    volume[0, 0, 0] = direction * 1.0
    volume[1, 3, 1] = direction * 2.5

    points, vectors = poc_app._volume_arrows(_info(volume), stride=1)
    assert points.shape == (2, 3)
    lengths = _lengths(vectors)
    recovered = vectors / lengths[:, None]
    # Tight on purpose: the only arithmetic between the field and the recovered
    # direction is one multiplication by a scalar and one division by it, so the
    # answer is a couple of ulps away - not a percent. A loose tolerance would
    # also pass for a lattice-wide normalisation.
    np.testing.assert_allclose(recovered, np.tile(unit, (2, 1)), rtol=1e-12, atol=0.0)


def test_length_is_linear_in_magnitude():
    """1 : 2 : 4 in, 1 : 2 : 4 out, anchored at the peak."""
    nx, ny, nz = 3, 3, 3
    direction = np.array([0.0, 3.0, 4.0])
    volume = np.zeros((nx, ny, nz, 3))
    cells = ((0, 0, 0), (1, 1, 1), (2, 2, 2))
    for magnitude, (i, j, k) in zip((1.0, 2.0, 4.0), cells):
        volume[i, j, k] = direction * magnitude

    points, vectors = poc_app._volume_arrows(_info(volume), stride=1)
    assert points.shape == (3, 3)
    lengths = np.sort(_lengths(vectors))
    # The magnitudes are 1, 2 and 4, so consecutive lengths differ by a factor of
    # exactly 2 - the ratio the DATA has, not a constant fitted to a measurement.
    # A square root, a logarithm or a clip anywhere in the length would move it.
    assert lengths[1] / lengths[0] == 2.0
    assert lengths[2] / lengths[1] == 2.0
    # And the peak shaft is exactly one arrow cell long: the fraction times the
    # stride times the cell, which is what keeps the head inside its own cell.
    peak_len = FRACTION * 1 * CELL_MM
    np.testing.assert_allclose(lengths[-1], peak_len, rtol=1e-12)


def test_stride_selects_the_lattice_and_the_counts_are_exact():
    """ceil per axis, never floor - the off-by-one that drops the far face."""
    nx, ny, nz = 4, 6, 3
    volume = np.ones((nx, ny, nz, 3))
    info = _info(volume)
    # arange(0, 4, s) x arange(0, 6, s) x arange(0, 3, s):
    #   s = 1 -> 4 x 6 x 3 = 72
    #   s = 2 -> 2 x 3 x 2 = 12
    #   s = 3 -> 2 x 2 x 1 = 4   (0 and 3 on x, 0 and 3 on y, only 0 on z)
    for stride, expected in ((1, 72), (2, 12), (3, 4)):
        points, vectors = poc_app._volume_arrows(info, stride=stride)
        assert points.shape == (expected, 3), stride
        assert vectors.shape == (expected, 3), stride

    # The real production shape. 62 // 5 = 12 but there are 13 kept indices
    # (0, 5, ..., 60); 212 -> 43 (0, ..., 210); 22 -> 5 (0, ..., 20). So
    # 13 x 43 x 5 = 2795. On this synthetic all-ones volume nothing can be
    # masked out, so equality is the honest assertion here - unlike the real dump
    # below, where exact zeros in the far field legitimately thin the lattice.
    big = np.ones((62, 212, 22, 3))
    points, _ = poc_app._volume_arrows(_info(big), stride=5)
    assert points.shape == (2795, 3)


def test_arrows_sit_at_cell_centres_inside_the_volume():
    """Half a cell in from the face, on every axis."""
    nx, ny, nz, stride = 4, 6, 3, 2
    volume = _uniform((nx, ny, nz), (0.0, 1.0, 0.0))
    points, _ = poc_app._volume_arrows(_info(volume), stride=stride)
    assert points.shape == (12, 3)

    for axis, cells in enumerate((nx, ny, nz)):
        kept = _samples(cells, stride)
        expected = (kept + 0.5) * CELL_MM
        # Every coordinate is the centre of a kept cell - the same expression the
        # helper uses, so this is an exact membership test and not a tolerance.
        assert np.all(np.isin(points[:, axis], expected)), axis
        # Strictly inside the extent: a face-anchored arrow (i * cell_mm) would
        # put the i = 0 column at exactly 0.0 and the far one on the boundary,
        # which is the bug this line catches.
        assert np.all(points[:, axis] > 0.0), axis
        assert np.all(points[:, axis] < cells * CELL_MM), axis
        # And each centre is used the same number of times - once per combination
        # of the OTHER two axes - so the lattice is a full product and not, say,
        # one arrow per diagonal.
        for value in expected:
            assert np.count_nonzero(points[:, axis] == value) == 12 // len(expected)


def test_nothing_drawable_returns_empty_arrays():
    """EMPTY ``(0, 3)`` pairs, never None and never a raise."""
    good = _uniform((2, 2, 2), (1.0, 0.0, 0.0))
    defects = [
        None,                                   # not a dict at all
        {},                                     # no volume, no cell size
        {poc_app.VOLUME_KEY: good},             # no cell_m
        {"cell_m": CELL_M},                     # no volume
        _info(np.zeros((2, 2, 2, 3))),          # zero everywhere: no direction
        _info(np.full((2, 2, 2, 3), np.nan)),   # NaN everywhere: no field
        _info(np.zeros((2, 2, 2))),             # ndim 3: a scalar volume
        _info(np.zeros((2, 2, 2, 2))),          # last axis 2: not three components
        _info(np.zeros((2, 2, 2, 4))),          # last axis 4: not a vector either
    ]
    for defect in defects:
        out = poc_app._volume_arrows(defect)
        # Shapes, not truthiness: an empty tuple is falsy too, and so is a tuple
        # of two empty arrays - asserting on truthiness would pass for a return
        # of () or None, which is exactly what the caller cannot handle.
        assert isinstance(out, tuple) and len(out) == 2, defect
        points, vectors = out
        assert isinstance(points, np.ndarray) and points.shape == (0, 3), defect
        assert isinstance(vectors, np.ndarray) and vectors.shape == (0, 3), defect


def test_a_nan_or_zero_sample_gets_no_arrow_and_the_others_still_do():
    """The mask is per SAMPLE: one bad cell costs one arrow, not the lattice."""
    volume = np.zeros((2, 2, 2, 3))
    volume[0, 0, 0] = (1.0, 0.0, 0.0)
    volume[0, 1, 0] = (np.nan, 0.0, 0.0)
    volume[1, 0, 0] = (0.0, 2.0, 0.0)
    # (1, 1, 0) and everything else stay literal zeros, which have no direction.
    points, vectors = poc_app._volume_arrows(_info(volume), stride=1)
    assert points.shape == (2, 3)
    assert np.all(np.isfinite(points)) and np.all(np.isfinite(vectors))
    # The two survivors are the cells that were given a direction; the NaN cell
    # and the zero cells are gone, so a NaN cannot poison the peak either (the
    # remaining length ratio is 1 : 2, from |1| and |2|).
    assert sorted(points[:, 0].tolist()) == [0.5 * CELL_MM, 1.5 * CELL_MM]
    lengths = _lengths(vectors)
    np.testing.assert_allclose(np.sort(lengths)[1] / np.sort(lengths)[0], 2.0, rtol=1e-12)


def test_a_bad_cell_size_or_stride_is_refused():
    """Refused, not clamped: a guessed cell size would misplace every arrow."""
    volume = _uniform((2, 3, 2), (1.0, 0.0, 0.0))
    for bad_cell in (0.0, -1.0, float("nan"), float("inf")):
        points, vectors = poc_app._volume_arrows(_info(volume, cell_m=bad_cell))
        assert points.shape == (0, 3), bad_cell
        assert vectors.shape == (0, 3), bad_cell
    for bad_stride in (0, -3):
        points, vectors = poc_app._volume_arrows(_info(volume), stride=bad_stride)
        assert points.shape == (0, 3), bad_stride
        assert vectors.shape == (0, 3), bad_stride


def test_the_real_dump_gives_a_finite_bounded_lattice():
    """End to end on the shipped dump: something, all finite, nothing too long."""
    info = poc_app.load_dump(DEFAULT_DUMP, e_volume=True)
    assert poc_app.VOLUME_KEY in info
    points, vectors = poc_app._volume_arrows(info)
    n = int(points.shape[0])
    # AT MOST 2795, not exactly: a real far-field sample can be an exact zero or
    # a NaN, and the mask drops it - rightly, since neither has a direction. The
    # exact 2795 is asserted on the synthetic all-ones volume above, where
    # nothing can be masked.
    assert 0 < n <= 2795
    assert points.shape == (n, 3) and vectors.shape == (n, 3)
    assert np.all(np.isfinite(points)) and np.all(np.isfinite(vectors))
    cell_mm = float(info["cell_m"]) * 1e3
    bound = FRACTION * STRIDE * cell_mm
    lengths = _lengths(vectors)
    assert np.all(lengths > 0.0)
    # Every shaft fits inside its own stride cell - the whole point of anchoring
    # the maximum length to ``stride * cell_mm`` rather than to the box span.
    assert np.all(lengths <= bound * (1.0 + 1e-12))
    # And the peak arrow reaches exactly that bound, so the bound is not merely
    # an upper limit the data happens to sit under.
    np.testing.assert_allclose(np.max(lengths), bound, rtol=1e-12)


def test_pyvista_builds_one_glyph_per_arrow_from_point_data():
    """One glyph per arrow, MEASURED on this pyvista - no count taken on faith."""
    try:
        import pyvista as pv
    except Exception as exc:  # noqa: BLE001 - the overlay is not always available
        pytest.skip(f"pyvista not importable here: {exc}")
    volume = _uniform((4, 6, 3), (1.0, 2.0, -0.5))
    points, vectors = poc_app._volume_arrows(_info(volume), stride=2)
    n_arrows = int(points.shape[0])
    assert n_arrows == 12
    # A synthetic volume, not the real dump: the claim under test is glyph
    # construction from a point-data array, and a 12-arrow cloud proves it in
    # milliseconds without carrying a 2795-arrow mesh through the filter.
    cloud = pv.PolyData(points)
    cloud.point_data["volume_e_arrows"] = vectors
    assert cloud.point_data["volume_e_arrows"].shape == (n_arrows, 3)
    arrows = cloud.glyph(orient="volume_e_arrows", scale="volume_e_arrows", factor=1.0)
    assert arrows.n_cells > 0
    # One glyph per arrow, measured: this pyvista builds ONE arrow from a
    # one-arrow cloud, and the N-arrow glyph must be exactly N of those - the
    # same cells AND the same points. A filter that merged arrows into one mesh
    # would break the proportionality, and no count here is written down.
    one = pv.PolyData(points[:1])
    one.point_data["volume_e_arrows"] = vectors[:1]
    single = one.glyph(orient="volume_e_arrows", scale="volume_e_arrows", factor=1.0)
    assert single.n_cells > 0
    assert single.n_points > 0
    assert arrows.n_cells == n_arrows * single.n_cells
    assert arrows.n_points == n_arrows * single.n_points


def test_denormal_samples_are_dropped_by_the_relative_floor():
    """1e-9 of the peak is round-off; 1e-3 of the peak is signal."""
    nx, ny, nz = 2, 1, 1
    # The RATIO to the peak is what decides, so the same shape is walked twice
    # with the same 1.0 peak and a weak cell either side of the floor. One of
    # these two cases alone would prove nothing: 1 survivor could come from a
    # filter that drops every weak sample, and 2 survivors could come from no
    # filter at all. Together they pin the boundary.
    for weak, survivors in ((1e-9, 1), (1e-3, 2)):
        volume = np.zeros((nx, ny, nz, 3))
        volume[0, 0, 0] = (1.0, 0.0, 0.0)  # the peak sample, always kept
        volume[1, 0, 0] = (weak, 0.0, 0.0)  # 1e-9 or 1e-3 of the peak
        points, vectors = poc_app._volume_arrows(_info(volume), stride=1)
        assert points.shape == (survivors, 3)
        lengths = _lengths(vectors)
        bound = FRACTION * 1 * CELL_MM
        if survivors == 1:
            # The strong cell keeps the FULL arrow-cell bound: dropping the
            # round-off must not rescale what is left, which is what would happen
            # if the floor were applied before ``peak`` was taken.
            np.testing.assert_allclose(lengths, [bound], rtol=1e-12)
            # And the survivor is the STRONG cell's anchor, not the weak one's.
            np.testing.assert_allclose(
                points[0], [0.5 * CELL_MM, 0.5 * CELL_MM, 0.5 * CELL_MM], rtol=0.0
            )
        else:
            # Below the floor neither cell is special, so both are drawn and the
            # pair still stands in the recorded ratio of the fields.
            np.testing.assert_allclose(lengths, [bound, bound * 1e-3], rtol=1e-12)


def test_the_floor_is_relative_to_the_peak_not_absolute():
    """The same pair scaled by 1e-20: the RATIO is unchanged, so both survive."""
    scale = 1e-20
    volume = np.zeros((2, 1, 1, 3))
    volume[0, 0, 0] = (scale, 0.0, 0.0)
    volume[1, 0, 0] = (scale * 1e-3, 0.0, 0.0)
    points, vectors = poc_app._volume_arrows(_info(volume), stride=1)
    # An ABSOLUTE epsilon in V/m fails exactly here: both magnitudes are now
    # ~1e-20, below any fixed threshold anyone would choose, so the whole arrow
    # field would vanish although its internal contrast is untouched. Being
    # relative, the floor cannot see ``scale`` at all - and the peak arrow still
    # reaches the full arrow-cell bound, so the picture does not shrink either.
    assert points.shape == (2, 3)
    lengths = _lengths(vectors)
    np.testing.assert_allclose(
        lengths, [FRACTION * 1 * CELL_MM, FRACTION * 1 * CELL_MM * 1e-3], rtol=1e-12
    )


def test_polydata_carries_the_points_and_the_point_data():
    """The cloud is the anchors plus ONE named point-data array - nothing else."""
    try:
        import pyvista as pv
    except Exception as exc:  # noqa: BLE001 - the overlay is not always available
        pytest.skip(f"pyvista not importable here: {exc}")
    volume = _uniform((4, 6, 3), (1.0, 2.0, -0.5))
    points, vectors = poc_app._volume_arrows(_info(volume), stride=2)
    n_arrows = int(points.shape[0])
    assert n_arrows == 12
    cloud = poc_app._volume_quiver_polydata(points, vectors)
    assert isinstance(cloud, pv.PolyData)
    assert cloud.n_points == n_arrows
    carried = np.asarray(cloud.point_data["volume_e_quiver"], dtype=float)
    assert carried.shape == (n_arrows, 3)
    # The shafts are carried through uninspected: this function is a seam, not a
    # normaliser, and a caller that glyphs ``scale`` off this array is relying on
    # getting back the same millimetres it handed in.
    np.testing.assert_array_equal(carried, vectors)
    # Refusals return None, not empty arrays: a renderer skips a None in one
    # ``if`` and cannot skip a cloud with no points.
    refused = [
        (None, vectors),
        (points, None),
        (points[:, 0], vectors),  # 1-D, so no per-point tuple
        (points[:, :2], vectors[:, :2]),  # two components, not three
        (points[:-1], vectors),  # mismatched n
        (points[:0], vectors[:0]),  # empty pair
        (np.array([[np.nan, 0.0, 0.0]]), np.array([[1.0, 0.0, 0.0]])),
    ]
    for pts, vecs in refused:
        assert poc_app._volume_quiver_polydata(pts, vecs) is None


def test_the_mesh_seam_glyphs_every_arrow_of_the_real_dump_once():
    """``_volume_quiver_mesh`` on the shipped dump: N arrows, N glyphs, measured.

    The claim run_web's overlay rests on. One glyph per arrow is MEASURED
    against a one-arrow glyph built by the same call, never against a count
    written down here, so a pyvista that changed the per-arrow cell count could
    not silently change the picture.
    """
    try:
        import pyvista as pv
    except Exception as exc:  # noqa: BLE001 - the overlay is not always available
        pytest.skip(f"pyvista not importable here: {exc}")
    info = poc_app.load_dump(DEFAULT_DUMP, e_volume=True)
    mesh = poc_app._volume_quiver_mesh(info)
    assert mesh is not None
    assert mesh.n_cells > 0
    points, vectors = poc_app._volume_arrows(info)
    n_arrows = int(points.shape[0])
    assert n_arrows > 0
    one = pv.PolyData(points[:1])
    one.point_data["volume_e_quiver"] = vectors[:1]
    single = one.glyph(
        orient="volume_e_quiver", scale="volume_e_quiver", factor=1.0
    )
    assert single.n_cells > 0
    assert mesh.n_cells == n_arrows * single.n_cells
    # Nothing a renderer would have to repair: every vertex finite, and every
    # vertex inside the arrow lattice's own box plus the longest shaft.
    coords = np.asarray(mesh.points, dtype=float)
    assert coords.shape == (mesh.n_points, 3)
    assert np.all(np.isfinite(coords))
    bound = FRACTION * STRIDE * float(info["cell_m"]) * 1e3
    assert np.all(coords >= points.min(axis=0) - bound)
    assert np.all(coords <= points.max(axis=0) + bound)


def test_the_mesh_seam_returns_none_when_there_is_nothing_to_draw():
    """No volume, or a volume that is zero everywhere: None, and no raise.

    run_web reads None as "draw nothing": this is the branch that decides a
    dump with no vectors in it still gets a working page rather than an empty
    actor or a traceback.
    """
    assert poc_app._volume_quiver_mesh({}) is None
    assert poc_app._volume_quiver_mesh(_info(np.zeros((3, 4, 2, 3)))) is None


# --------------------------------------------------------------------------- #
# the LAZY route: the loader stashes the raw vector, the first reader colocates
# --------------------------------------------------------------------------- #
def test_the_raw_flag_stashes_the_edge_vector_and_no_volume():
    """``e_raw=True``: the vector is on ``info``, the colocation has not run."""
    info = poc_app.load_dump(DEFAULT_DUMP, e_raw=True)
    # The whole saving: the deferred route carries no volume yet ...
    assert poc_app.VOLUME_KEY not in info
    raw = info[poc_app.VOLUME_RAW_KEY]
    with np.load(DEFAULT_DUMP) as data:
        flat = np.asarray(data["e"])
    # ... but it does carry the vector UNTOUCHED - same length, same values,
    # same order - so the deferred colocation reads exactly the bytes the eager
    # one read, and the delay cannot change the answer.
    assert np.array_equal(raw["e"], flat)
    # The grid travels WITH the array, which is what lets the reader colocate
    # without re-opening the archive or trusting a second copy of the shape.
    assert (raw["nx"], raw["ny"], raw["nz"]) == (
        info["nx"], info["ny"], info["nz"])
    # And the plane and its scalars are what a flag-less load hands over: asking
    # for the raw vector must not change anything a flag-less reader sees.
    plain = poc_app.load_dump(DEFAULT_DUMP)
    assert np.array_equal(info[poc_app.PLANE_KEY], plain[poc_app.PLANE_KEY])
    assert set(info) - set(plain) == {poc_app.VOLUME_RAW_KEY}


def test_the_lazy_route_glyphs_the_same_mesh_as_the_eager_one():
    """One picture, two routes: the deferral is a delay, not a second answer."""
    try:
        import pyvista as pv  # noqa: F401 - the glyph is the thing under test
    except Exception as exc:  # noqa: BLE001 - the overlay is not always available
        pytest.skip(f"pyvista not importable here: {exc}")
    eager = poc_app._volume_quiver_mesh(
        poc_app.load_dump(DEFAULT_DUMP, e_volume=True))
    lazy = poc_app._volume_quiver_mesh(poc_app.load_dump(DEFAULT_DUMP, e_raw=True))
    assert eager is not None
    assert lazy is not None
    # Counts first: a colocation that landed the components on different points
    # would change how many samples survive the relative floor, so this is not
    # merely a shape check - it is the same lattice, arrow for arrow.
    assert lazy.n_points == eager.n_points
    assert lazy.n_cells == eager.n_cells
    # And the geometry is the same to the last bit a coordinate can be trusted
    # for: both routes stack the same three fields in the same order, so any
    # difference here would mean the stash was not the archive's own array.
    np.testing.assert_allclose(
        np.asarray(lazy.points, dtype=float),
        np.asarray(eager.points, dtype=float),
        rtol=0.0,
        atol=1e-12,
    )


def test_the_raw_flag_without_an_e_key_says_so_and_draws_nothing(
    tmp_path, capsys
):
    """No ``e`` at all: one stderr line, no stash, no raise, None from the seam."""
    path = tmp_path / "plane_only.npz"
    plane = np.zeros((3, 4, 5), dtype=complex)
    np.savez(path, plane_ez=plane, nstep=np.array(1), nx=np.array(2),
             ny=np.array(3), nz=np.array(4), cell_m=np.array(1e-4))
    info = poc_app.load_dump(path, e_raw=True)
    assert poc_app.VOLUME_RAW_KEY not in info
    assert poc_app.VOLUME_KEY not in info
    assert np.array_equal(info[poc_app.PLANE_KEY], plane)
    lines = [line for line in capsys.readouterr().err.splitlines() if line]
    assert len(lines) == 1
    assert "no 'e' edge vector" in lines[0]
    # And the reader's answer is "draw nothing" rather than an empty mesh.
    assert poc_app._volume_quiver_mesh(info) is None


# --------------------------------------------------------------------------- #
# the DIAGNOSTICS: every "nothing drawn" branch says so, and so does success
# --------------------------------------------------------------------------- #
def test_the_mesh_seam_says_why_it_drew_nothing(monkeypatch, capsys):
    """``[poc_app]`` on stderr in the no-volume branch and on a forced failure.

    run_web shows the operator a page with no arrows; without these lines there
    is no way to tell an absent volume from a broken glyph. The failure case
    also has to keep returning None: the seam is called from a redraw and a
    traceback there would take the page down.
    """
    assert poc_app._volume_quiver_mesh({}) is None
    err = capsys.readouterr().err
    assert "[poc_app]" in err
    # The message has to name BOTH routes it looked for, because "no volume" is
    # only actionable if the reader knows which two keys were absent.
    assert poc_app.VOLUME_KEY in err
    assert poc_app.VOLUME_RAW_KEY in err

    def _boom(*args, **kwargs):
        raise RuntimeError("arrow path exploded")

    monkeypatch.setattr(poc_app, "_volume_arrows", _boom)
    assert poc_app._volume_quiver_mesh(_info(np.ones((3, 4, 2, 3)))) is None
    err = capsys.readouterr().err
    # The exception AND its traceback: the message alone does not say where.
    assert any(
        line.startswith("[poc_app]") and "arrow path exploded" in line
        for line in err.splitlines()
    )
    assert "Traceback (most recent call last)" in err


def test_the_volume_arrows_are_drawn_black_on_the_white_background():
    """Source check: the volume-arrow add_mesh is BLACK, and the mode one is not.

    HONESTLY: this reads server/poc_app.py rather than driving a plotter. The
    call under test lives in ``_show_volume_quiver``, a closure inside
    ``run_web`` that needs a live trame page and a GL context; neither exists in
    this container, so a behavioural version cannot be written here. What the
    check does pin is the one thing that was wrong: white geometry on the white
    background ``create_plotter`` sets cannot be seen.
    """
    source = (REPO_ROOT / "server" / "poc_app.py").read_text(encoding="utf-8")

    def _block(name):
        """The ``plotter.add_mesh(...)`` call that carries ``name=<name>``."""
        marker = f'name="{name}"'
        assert source.count(marker) == 1, marker
        end = source.index(marker)
        start = source.rindex("plotter.add_mesh(", 0, end)
        return source[start:end]

    volume = _block("volume_e_quiver")
    assert 'color="black"' in volume
    assert 'color="white"' not in volume
    # The parallel call in run_web_vis draws white arrows OVER an opaque turbo
    # surface, where white is the visible choice. It must stay as it is: the fix
    # belongs to the transparent-on-white plotter only.
    mode = _block("mode_quiver")
    assert 'color="white"' in mode


#: The ``planes`` dict as ``_plane_layout`` hands it over, trimmed to the keys
#: ``_view_label`` and ``_draw_scene`` read.
def _planes(src_s11):
    stations = [0.0, 0.4, 0.8, 1.2, 1.6, 2.0, 2.4, 2.8, 3.2]
    return {
        "cell_mm": 0.4,
        "n_st": len(stations),
        "stations_mm": stations,
        "x_load_mm": 20.0,
        "src_load": "FALLBACK",
        "ix_load": None,
        "x_s11_mm": stations[0],
        "src_s11": src_s11,
        "x_s21_mm": 20.4,
        "src_s21": "FALLBACK",
        "s21_valid": False,
        "s21_valid_src": "FALLBACK",
        "s21_reason": "no record",
        "slice_index": 0,
    }


def test_the_port_label_admits_a_fallback_x():
    """A FALLBACK port x is named as one; a recorded one says nothing extra."""
    recorded = poc_app._view_label("port", _planes("record"), True)
    # Byte-for-byte what the label said before this note existed: the caveat is
    # appended only when the x really is the constant, so a recorded study is
    # not made to look less certain than it is.
    assert recorded == "port-plane |Ez|: station 1/9, x = 0.0000 mm"

    fallback = poc_app._view_label("port", _planes("FALLBACK"), True)
    assert fallback.startswith(recorded)
    assert len(fallback) > len(recorded)
    assert "FALLBACK" in fallback[len(recorded):]
    # The number the reader would otherwise trust is named as the constant.
    assert f"{poc_app.FALLBACK_S11_MM:g} mm" in fallback

    # The volume view never shows a port x, so it must not grow the note either.
    volume = poc_app._view_label("volume", _planes("FALLBACK"), True)
    assert "FALLBACK" not in volume


class _FakeImageData:
    """Stands in for ``pv.ImageData``: attributes, no VTK, no GL."""

    def __init__(self):
        self.dimensions = None
        self.spacing = None
        self.origin = None
        self.point_data = {}


class _StubPlotter:
    """Records what ``_draw_scene`` asks for; can refuse the port image."""

    def __init__(self, refuse_image=True):
        self.calls = []
        self.refuse_image = refuse_image

    def clear(self):
        self.calls.append("clear")

    def add_mesh(self, mesh, **kwargs):
        if self.refuse_image and isinstance(mesh, _FakeImageData):
            raise RuntimeError("slice mesh refused")
        self.calls.append(("add_mesh", mesh))
        return object()

    def add_axes(self, **kwargs):
        self.calls.append("add_axes")

    def add_text(self, text, **kwargs):
        self.calls.append(("add_text", kwargs.get("name")))

    def view_isometric(self):
        self.calls.append("view_isometric")

    def reset_camera(self):
        self.calls.append("reset_camera")


def _drive_port_scene(monkeypatch, plotter, planes):
    """``_draw_scene`` in port mode against stubs; returns (outline, markers)."""
    import types

    # pyvista is only used for a dataset container here, so a namespace with an
    # attribute-only stand-in keeps this test free of VTK and of any GL probe.
    fake_pv = types.SimpleNamespace(ImageData=_FakeImageData)
    monkeypatch.setitem(sys.modules, "pyvista", fake_pv)

    outline = object()
    monkeypatch.setattr(
        poc_app,
        "build_grid",
        lambda _info: types.SimpleNamespace(outline=lambda: outline),
    )
    monkeypatch.setattr(
        poc_app,
        "_cut_layout",
        lambda _info, j, k: {
            "y_mm": 0.0, "j": 0, "n_j": 1,
            "z_mm": 0.0, "k": 0, "n_k": 1,
        },
    )
    markers = []
    monkeypatch.setattr(
        poc_app, "_add_markers", lambda p, i, pl: markers.append("markers")
    )
    monkeypatch.setattr(
        poc_app, "_marker_cut_lines", lambda pl, cl, drawn, vm: {}
    )
    monkeypatch.setattr(poc_app, "_marker_text", lambda pl, cuts: "legend")

    info = {poc_app.PLANE_KEY: np.ones((planes["n_st"], 4, 5), dtype=complex)}
    poc_app._draw_scene(plotter, info, planes, "port", 0)
    return outline, markers


def test_a_refused_port_slice_still_leaves_outline_markers_and_labels(
    monkeypatch, capsys
):
    """A failing port image must cost the image, not the rest of the scene.

    The stub plotter raises on exactly the ``pv.ImageData`` add_mesh, i.e. on
    the port slice alone; everything drawn AFTER that branch has to be reached
    anyway, and the failure has to be reported rather than raised.
    """
    plotter = _StubPlotter(refuse_image=True)
    outline, markers = _drive_port_scene(monkeypatch, plotter, _planes("record"))
    err = capsys.readouterr().err
    assert "[poc_app] port-plane view not drawn: slice mesh refused" in err
    # The common tail ran: outline, axes, markers, station text, marker legend,
    # camera. Without the guard the exception would have escaped here.
    assert ("add_mesh", outline) in plotter.calls
    assert "add_axes" in plotter.calls
    assert markers == ["markers"]
    assert ("add_text", "station_label") in plotter.calls
    assert ("add_text", "marker_legend") in plotter.calls
    assert "view_isometric" in plotter.calls
    assert "reset_camera" in plotter.calls


def test_an_out_of_range_port_slice_index_is_named_not_raised(monkeypatch, capsys):
    """``slice_index`` past the captured planes: refused, named, page survives."""
    planes = _planes("record")
    planes["slice_index"] = planes["n_st"]  # one past the last captured plane
    plotter = _StubPlotter(refuse_image=False)
    outline, markers = _drive_port_scene(monkeypatch, plotter, planes)
    err = capsys.readouterr().err
    # The index AND the count are in the message: "not drawn" alone would not
    # say whether the data or the viewer was wrong.
    assert "port-plane view not drawn" in err
    assert f"slice_index {planes['n_st']}" in err
    assert f"{planes['n_st']} captured planes" in err
    # Nothing was asked of the renderer for the slice, but the tail still ran.
    assert not any(
        call == ("add_mesh",)
        or (isinstance(call, tuple) and isinstance(call[1], _FakeImageData))
        for call in plotter.calls
    )
    assert ("add_mesh", outline) in plotter.calls
    assert markers == ["markers"]
    assert "reset_camera" in plotter.calls

