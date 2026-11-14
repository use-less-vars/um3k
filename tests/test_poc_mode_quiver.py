"""The Mode panel's transverse ARROW field: two components, one cross-section.

What is proven here is the compute half of the overlay, and it is a different
kind of claim from a picture: the module helpers are called directly, with a
DOUBLED solver (a ``SimpleNamespace`` whose ``e_at`` is a plain function of the
points it is handed), so a failure points at the layer that failed.

The claims, one per test:

* the arrow lattice is the SAME square sampling the ``|E|`` picture uses, taken
  every ``MODE_QUIVER_STRIDE``-th sample - 10 x 10 = 100 arrows on the shipped
  48-cell grid - and only those samples are ever asked for;
* a sample the interpolation cannot answer for (``Mode2D.e_at`` raises
  ``ValueError`` outside the triangulation) is left NaN and COUNTED out loud,
  because an arrow at a point the field was never evaluated at would be an
  invented arrow;
* a solver that refuses some other way loses the arrows and keeps the panel -
  the helper never raises;
* a CANDIDATE is sampled through ``e_at_candidate``, so a picker row's arrows
  come from that row's eigenvector and not from the fundamental's;
* every anchor sits exactly where ``_mode_picture_grid`` puts the coloured cell
  it stands on (``x`` fixed, ``y`` off the grid centre, ``z`` off the grid's own
  axis, all in MILLIMETRES) and every shaft lies IN the cross-section plane;
* the shaft is the field's own unit direction and a length LINEAR in ``|E_t|``,
  peaking at ``MODE_QUIVER_MAX_LEN_FRACTION`` of the shorter side of the sampled
  box - and that fraction is 80 % of one lattice cell, which is why two
  neighbouring arrows cannot overlap;
* nothing drawable (no vector grid, a non-finite extent, a field that is zero
  everywhere) returns EMPTY arrays rather than a lattice of zero-length glyphs;
* pyvista builds one glyph per arrow from a POINT-data array - the installed
  build has no ``vectors=`` keyword on ``PolyData``, and ``scale=False`` would
  draw every arrow at unit length and throw the recorded magnitudes away.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries tests/test_poc_playback.py adds, so `import
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

CELLS = 48  # poc_app.MODE_GRID_CELLS, the shipped sampling
STRIDE = 5  # poc_app.MODE_QUIVER_STRIDE


def _linear(points):
    """A field with no zeros in it: (E_y, E_z) = (1, 2) at every point asked."""
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    return np.stack(
        [np.ones(points.shape[0]), np.full(points.shape[0], 2.0)], axis=1
    )


def _solver(field=_linear, *, outside=None, grid_axes=None):
    """A doubled solved mode: the two attributes the vector grid reads off one.

    ``e_at`` behaves like ``Mode2D.e_at`` in the one way that matters here - it
    raises ``ValueError`` when ANY point handed to it is outside the mesh, which
    is exactly what makes the whole-array answer unrecoverable and the mask a
    point-by-point question. ``calls`` records how many points each call asked
    for, so "only the strided samples are sampled" is checkable.
    """
    calls = []

    def e_at(points):
        points = np.asarray(points, dtype=float).reshape(-1, 2)
        calls.append(int(points.shape[0]))
        if outside is not None:
            bad = [bool(outside(y, z)) for y, z in points]
            if any(bad):
                raise ValueError("point outside the mesh")
        return field(points)

    solver = SimpleNamespace(mesh=SimpleNamespace(grid_axes=grid_axes), e_at=e_at)
    solver.calls = calls
    return solver


def test_the_arrow_lattice_is_the_picture_grid_taken_every_stride():
    """100 arrows of 2304 samples, one per lattice cell, on the strided rows/cols."""
    assert poc_app.MODE_GRID_CELLS == CELLS
    assert poc_app.MODE_QUIVER_STRIDE == STRIDE
    clock = _solver()
    grid = poc_app._mode_vector_grid(clock, (2e-3, 1e-3))
    assert grid.shape == (CELLS, CELLS, 2)
    finite = np.isfinite(grid).all(axis=2)
    assert int(finite.sum()) == 100
    rows, cols = np.nonzero(finite)
    assert set(rows.tolist()) == set(range(0, CELLS, STRIDE))
    assert set(cols.tolist()) == set(range(0, CELLS, STRIDE))
    # The samples are the two components, not their magnitude: (1, 2) survives.
    assert np.allclose(grid[finite][:, 0], 1.0)
    assert np.allclose(grid[finite][:, 1], 2.0)


def test_only_the_strided_samples_are_ever_asked_for():
    """A 48 x 48 picture must not cost 2304 samples of the field."""
    clock = _solver()
    poc_app._mode_vector_grid(clock, (2e-3, 1e-3))
    assert clock.calls == [100]


def test_a_sample_outside_the_mesh_is_masked_and_counted(capsys):
    """Half of the lattice is out of the mesh: NaN there, and said out loud."""
    clock = _solver(outside=lambda y, z: y < 0.0)
    grid = poc_app._mode_vector_grid(clock, (2e-3, 1e-3))
    finite = np.isfinite(grid).all(axis=2)
    # y = -2e-3 .. 0 is out; the strided y picks 0..20 are the five out of ten that
    # fall on the empty side, so only the last five columns survive.
    assert int(finite.sum()) == 50
    assert set(np.nonzero(finite)[1].tolist()) == {25, 30, 35, 40, 45}
    assert not np.isfinite(grid[:, 0]).any()
    err = capsys.readouterr().err
    assert (
        "[poc_app] mode vector field: 50 of 100 sampled points inside the mesh, "
        "50 masked (no arrow drawn on those)" in err
    )


def test_a_solver_that_refuses_some_other_way_costs_the_arrows_only(capsys):
    """The helper NEVER raises: an unusable solver leaves an all-NaN grid."""

    def boom(points):
        raise RuntimeError("no interpolation")

    solver = SimpleNamespace(mesh=SimpleNamespace(grid_axes=None), e_at=boom)
    grid = poc_app._mode_vector_grid(solver, (2e-3, 1e-3))
    assert not np.isfinite(grid).any()
    assert "[poc_app] mode vector field refused: no interpolation" in (
        capsys.readouterr().err
    )


def test_a_candidate_is_sampled_through_e_at_candidate():
    """A pick's arrows are that candidate's field, never the fundamental's."""
    seen = []

    def e_at(points):
        raise AssertionError("the fundamental must not be sampled for a candidate")

    def e_at_candidate(index, points):
        seen.append(int(index))
        points = np.asarray(points, dtype=float).reshape(-1, 2)
        return np.stack(
            [np.full(points.shape[0], 3.0), np.zeros(points.shape[0])], axis=1
        )

    solver = SimpleNamespace(
        mesh=SimpleNamespace(grid_axes=None),
        e_at=e_at,
        e_at_candidate=e_at_candidate,
    )
    grid = poc_app._mode_vector_grid(solver, (2e-3, 1e-3), index=2)
    assert seen == [2]
    finite = np.isfinite(grid).all(axis=2)
    assert int(finite.sum()) == 100
    assert np.allclose(grid[finite][:, 0], 3.0)
    assert np.allclose(grid[finite][:, 1], 0.0)


def test_an_anchor_sits_where_the_picture_puts_the_cell_it_stands_on():
    """x fixed, y off the grid centre, z off the grid axis - all in millimetres."""
    gy = np.linspace(-1e-3, 1e-3, CELLS)
    gz = np.linspace(0.0, 2e-3, CELLS)
    data = np.zeros((CELLS, CELLS, 2))
    data[7, 11] = (3.0, 4.0)  # indexed (z, y), the layout `grid` already uses
    result = {
        "grid_vec": data,
        "grid_vec_axes": (gy, gz),
        "extent": (1e-3, 2e-3),
    }
    points, vectors = poc_app._mode_quiver_arrows(
        result, x_mm=20.4, y_centre_mm=2.5
    )
    assert points.shape == (1, 3)
    assert vectors.shape == (1, 3)
    assert points[0, 0] == pytest.approx(20.4)
    assert points[0, 1] == pytest.approx(2.5 + 1e3 * gy[11])
    assert points[0, 2] == pytest.approx(1e3 * gz[7])
    # (3, 4) is |E| = 5, the peak, so its shaft is the longest one drawn.
    longest = poc_app.MODE_QUIVER_MAX_LEN_FRACTION * min(2.0, 2.0)
    assert vectors[0, 0] == 0.0
    assert np.hypot(vectors[0, 1], vectors[0, 2]) == pytest.approx(longest)
    assert vectors[0, 1] == pytest.approx(0.6 * longest)
    assert vectors[0, 2] == pytest.approx(0.8 * longest)


def test_the_shaft_is_the_unit_direction_and_a_length_linear_in_the_field():
    """Twice the field is twice the arrow; the peak arrow is the longest one."""
    gy = np.linspace(0.0, 1e-3, CELLS)
    gz = np.linspace(0.0, 1e-3, CELLS)
    data = np.full((CELLS, CELLS, 2), np.nan)
    data[0, 0] = (0.0, 2.0)  # |E| = 2: the peak
    data[3, 6] = (1.0, 0.0)  # |E| = 1: half of it
    result = {
        "grid_vec": data,
        "grid_vec_axes": (gy, gz),
        "extent": (1e-3, 1e-3),
    }
    points, vectors = poc_app._mode_quiver_arrows(result, x_mm=0.0)
    assert points.shape == (2, 3)
    longest = poc_app.MODE_QUIVER_MAX_LEN_FRACTION * 1.0
    lengths = np.hypot(vectors[:, 1], vectors[:, 2])
    assert lengths.max() == pytest.approx(longest)
    assert lengths.min() == pytest.approx(0.5 * longest)
    assert np.all(np.abs(lengths) <= longest + 1e-12)
    # In the plane, and pointing the way the field points.
    assert np.allclose(vectors[:, 0], 0.0)
    assert vectors[0, 1] == pytest.approx(0.0)
    assert vectors[0, 2] == pytest.approx(lengths[0])
    assert vectors[1, 1] == pytest.approx(lengths[1])
    assert vectors[1, 2] == pytest.approx(0.0)


def test_the_longest_arrow_fits_inside_its_own_lattice_cell():
    """The WHY behind the fraction, as arithmetic rather than a comment."""
    cell_fraction = STRIDE / (CELLS - 1)
    assert cell_fraction == pytest.approx(5.0 / 47.0)
    assert poc_app.MODE_QUIVER_MAX_LEN_FRACTION == pytest.approx(0.8 * cell_fraction)


def test_nothing_drawable_gives_empty_arrays_not_zero_length_glyphs():
    """Every defect returns (0, 3) arrays: a lattice of zeros would read as a
    solved zero field, which is a claim nobody measured."""
    gy = np.linspace(0.0, 1e-3, CELLS)
    gz = np.linspace(0.0, 1e-3, CELLS)
    good = np.zeros((CELLS, CELLS, 2))
    good[0, 0] = (1.0, 0.0)
    defects = [
        None,
        "not a result",
        {},
        # no vector grid / no axes / no extent
        {"grid_vec_axes": (gy, gz), "extent": (1e-3, 1e-3)},
        {"grid_vec": good, "extent": (1e-3, 1e-3)},
        {"grid_vec": good, "grid_vec_axes": (gy, gz)},
        # a grid that is not (cells, cells, 2)
        {"grid_vec": np.zeros((CELLS, CELLS)), "grid_vec_axes": (gy, gz),
         "extent": (1e-3, 1e-3)},
        {"grid_vec": good[:, :, :1], "grid_vec_axes": (gy, gz),
         "extent": (1e-3, 1e-3)},
        # axes that do not match the grid
        {"grid_vec": good, "grid_vec_axes": (gy[:10], gz), "extent": (1e-3, 1e-3)},
        # a non-finite extent
        {"grid_vec": good, "grid_vec_axes": (gy, gz), "extent": (np.nan, 1e-3)},
        # a field with no value anywhere, and one that is zero everywhere
        {"grid_vec": np.full((CELLS, CELLS, 2), np.nan), "grid_vec_axes": (gy, gz),
         "extent": (1e-3, 1e-3)},
        {"grid_vec": np.zeros((CELLS, CELLS, 2)), "grid_vec_axes": (gy, gz),
         "extent": (1e-3, 1e-3)},
    ]
    for result in defects:
        points, vectors = poc_app._mode_quiver_arrows(result, x_mm=12.0)
        assert points.shape == (0, 3), result
        assert vectors.shape == (0, 3), result


def test_pyvista_builds_one_glyph_per_arrow_from_point_data():
    """The installed pyvista has no ``vectors=`` keyword and no unit-scale draw.

    "One glyph per arrow" is MEASURED here, not assumed: a cloud of ONE arrow
    gives the cell and point count of one glyph on this very pyvista, and the
    N-arrow glyph must then be exactly N times both. Neither 15 cells nor 31
    points is written down - a hardcoded count goes stale, and a topology-free
    check (``n_cells % 3``) passes on counts that merge arrows.
    """
    try:
        import pyvista as pv
    except Exception as exc:  # noqa: BLE001 - the overlay is not always available
        pytest.skip(f"pyvista not importable here: {exc}")
    gy = np.linspace(0.0, 1e-3, CELLS)
    gz = np.linspace(0.0, 1e-3, CELLS)
    data = np.full((CELLS, CELLS, 2), np.nan)
    data[0, 0] = (0.0, 2.0)
    data[3, 6] = (1.0, 0.0)
    data[10, 20] = (0.0, -0.5)
    result = {"grid_vec": data, "grid_vec_axes": (gy, gz), "extent": (1e-3, 1e-3)}
    points, vectors = poc_app._mode_quiver_arrows(result, x_mm=5.0, y_centre_mm=1.0)
    assert points.shape == (3, 3)
    cloud = pv.PolyData(points)
    cloud.point_data["mode_e_arrows"] = vectors
    assert cloud.point_data["mode_e_arrows"].shape == (3, 3)
    arrows = cloud.glyph(orient="mode_e_arrows", scale="mode_e_arrows", factor=1.0)
    assert arrows.n_points > 0
    # One glyph per arrow, MEASURED: this pyvista builds ONE arrow from a
    # one-arrow cloud, and the N-arrow glyph is exactly N of those - the same
    # cells AND the same points. A glyph that merged arrows into one mesh would
    # break the proportionality, and no count here is taken on faith.
    n_arrows = int(points.shape[0])
    one = pv.PolyData(points[:1])
    one.point_data["mode_e_arrows"] = vectors[:1]
    single = one.glyph(orient="mode_e_arrows", scale="mode_e_arrows", factor=1.0)
    assert single.n_cells > 0
    assert single.n_points > 0
    assert arrows.n_cells == n_arrows * single.n_cells
    assert arrows.n_points == n_arrows * single.n_points
    # And the scale really is the ARRAY: a unit-scale draw sits in a different
    # place, which is what "the recorded magnitudes are kept" has to mean.
    unit = cloud.glyph(orient="mode_e_arrows", scale=False, factor=1.0)
    assert unit.n_cells == arrows.n_cells
    assert not np.allclose(np.asarray(unit.bounds), np.asarray(arrows.bounds))
