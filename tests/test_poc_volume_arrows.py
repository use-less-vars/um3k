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
* pyvista builds one glyph per arrow from a POINT-data array.
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
