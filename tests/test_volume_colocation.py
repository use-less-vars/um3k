"""The cell-centred E volume: the colocation rule, and the loader flag that asks.

The dump already ships the solver's flat three-component ``e`` vector, but each
component sits on its own staggered edges, so it is not a vector field a picture
can read.  ``emfit.operators.edge_to_cell_centres`` puts all three on the cell
centres, and ``load_dump(..., e_volume=True)`` wires it in behind a keyword that
defaults OFF.

The claims, one per test:

* the four-edge mean agrees with a brute-force loop written here, on EVERY
  element of a small grid - not a sample;
* a uniform field comes back as the same constant, so the weights sum to one;
* ONE edge set to 1 lands as exactly 0.25 on the four cells it corners, and 0
  everywhere else - which is what "the four neighbours are being averaged"
  means, and what a nearest-edge (no averaging) copy would fail;
* the wrong-size vector is refused with a message naming both counts;
* the last cell ``(nx-1, ny-1, nz-1)`` reads the far point layers rather than
  wrapping to the near ones - the rule is written with no modulus precisely
  because those four neighbours are in range;
* ``load_dump`` with the flag off reads the real default dump exactly as before
  (same keys, same values), and with the flag on adds the volume with the
  designed shape and values.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import poc_app  # noqa: E402 - the path above is what makes it importable
from emfit.operators import CellComplex, Grid, edge_to_cell_centres  # noqa: E402

DEFAULT_DUMP = REPO_ROOT / poc_app.DEFAULT_INPUT


def _mesh(nx, ny, nz):
    grid = Grid.uniform(nx, ny, nz, float(nx), float(ny), float(nz))
    return CellComplex(grid)


def _pattern(n):
    """A deterministic, sign-changing, non-symmetric flat vector."""
    return np.cos(np.arange(n, dtype=float) * 0.37) * 3.0 + 0.01 * np.arange(
        n, dtype=float) - 1.5


def _brute_force_centre(flat, cc, component, i, j, k):
    """The four-edge mean for one component and one cell, spelled out here.

    Deliberately independent of the implementation: the neighbours are listed by
    hand from the staggering, and the sum is written in the same order the rule
    states so the comparison can be exact rather than ``approx``.
    """
    if component == "x":            # EX at (i+1/2, j, k): j, j+1 by k, k+1
        four = [cc.idx_ex(i, j, k), cc.idx_ex(i, j + 1, k),
                cc.idx_ex(i, j, k + 1), cc.idx_ex(i, j + 1, k + 1)]
    elif component == "y":          # EY at (i, j+1/2, k): i, i+1 by k, k+1
        four = [cc.idx_ey(i, j, k), cc.idx_ey(i + 1, j, k),
                cc.idx_ey(i, j, k + 1), cc.idx_ey(i + 1, j, k + 1)]
    else:                           # EZ at (i, j, k+1/2): i, i+1 by j, j+1
        four = [cc.idx_ez(i, j, k), cc.idx_ez(i + 1, j, k),
                cc.idx_ez(i, j + 1, k), cc.idx_ez(i + 1, j + 1, k)]
    total = flat[four[0]] + flat[four[1]] + flat[four[2]] + flat[four[3]]
    return 0.25 * total


# --------------------------------------------------------------------------- #
# the colocation rule
# --------------------------------------------------------------------------- #
def test_every_element_agrees_with_a_brute_force_loop():
    nx, ny, nz = 3, 4, 2
    cc = _mesh(nx, ny, nz)
    flat = _pattern(cc.n_edges)

    ex, ey, ez = edge_to_cell_centres(flat, nx, ny, nz)
    assert ex.shape == ey.shape == ez.shape == (nx, ny, nz)

    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                assert ex[i, j, k] == _brute_force_centre(flat, cc, "x", i, j, k)
                assert ey[i, j, k] == _brute_force_centre(flat, cc, "y", i, j, k)
                assert ez[i, j, k] == _brute_force_centre(flat, cc, "z", i, j, k)


def test_a_uniform_field_is_that_constant_at_every_centre():
    nx, ny, nz = 2, 3, 3
    cc = _mesh(nx, ny, nz)
    value = 7.5
    ex, ey, ez = edge_to_cell_centres(np.full(cc.n_edges, value), nx, ny, nz)
    assert np.all(ex == value)
    assert np.all(ey == value)
    assert np.all(ez == value)


def test_one_edge_lands_as_a_quarter_on_the_four_cells_it_corners():
    nx, ny, nz = 2, 3, 3
    cc = _mesh(nx, ny, nz)
    flat = np.zeros(cc.n_edges)
    # EX(1, 1, 1) is interior in y and z, so four cells share it: j in {0, 1}
    # crossed with k in {0, 1}, at i = 1.
    flat[cc.idx_ex(1, 1, 1)] = 1.0

    ex, ey, ez = edge_to_cell_centres(flat, nx, ny, nz)
    assert np.all(ey == 0.0) and np.all(ez == 0.0)

    corners = {(1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1)}
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if (i, j, k) in corners:
                    assert ex[i, j, k] == 0.25
                else:
                    assert ex[i, j, k] == 0.0
    assert np.count_nonzero(ex) == 4


def test_the_wrong_size_vector_names_both_counts():
    nx, ny, nz = 3, 2, 2
    cc = _mesh(nx, ny, nz)
    expected = cc.n_ex + cc.n_ey + cc.n_ez
    with pytest.raises(ValueError) as excinfo:
        edge_to_cell_centres(np.zeros(expected - 1), nx, ny, nz)
    message = str(excinfo.value)
    assert str(expected - 1) in message
    assert str(expected) in message
    assert "n_ex" in message


def test_the_last_cell_reads_the_far_layers_and_does_not_wrap():
    nx, ny, nz = 2, 2, 2
    cc = _mesh(nx, ny, nz)
    flat = _pattern(cc.n_edges)
    ex, ey, ez = edge_to_cell_centres(flat, nx, ny, nz)

    i, j, k = nx - 1, ny - 1, nz - 1
    # The four neighbours of the last cell are the LAST point layers, not the
    # first ones, and all four are inside the flat vector.
    far = [cc.idx_ex(i, j, k), cc.idx_ex(i, j + 1, k),
           cc.idx_ex(i, j, k + 1), cc.idx_ex(i, j + 1, k + 1)]
    for index in far:
        assert 0 <= index < flat.size
    far_mean = 0.25 * (flat[far[0]] + flat[far[1]] + flat[far[2]] + flat[far[3]])
    assert ex[i, j, k] == far_mean
    # The wrapped reading -- the same four slots taken through the near layers --
    # is a different number here, so the assertion above cannot pass by luck.
    near = [cc.idx_ex(i, 0, k), cc.idx_ex(i, 1, k),
            cc.idx_ex(i, 0, 0), cc.idx_ex(i, 1, 0)]
    near_mean = 0.25 * (flat[near[0]] + flat[near[1]]
                        + flat[near[2]] + flat[near[3]])
    assert ex[i, j, k] != near_mean

    far_y = [cc.idx_ey(i, j, k), cc.idx_ey(i + 1, j, k),
             cc.idx_ey(i, j, k + 1), cc.idx_ey(i + 1, j, k + 1)]
    far_z = [cc.idx_ez(i, j, k), cc.idx_ez(i + 1, j, k),
             cc.idx_ez(i, j + 1, k), cc.idx_ez(i + 1, j + 1, k)]
    assert ey[i, j, k] == 0.25 * (flat[far_y[0]] + flat[far_y[1]]
                                 + flat[far_y[2]] + flat[far_y[3]])
    assert ez[i, j, k] == 0.25 * (flat[far_z[0]] + flat[far_z[1]]
                                 + flat[far_z[2]] + flat[far_z[3]])
    assert np.all(np.isfinite(ex)) and np.all(np.isfinite(ey))
    assert np.all(np.isfinite(ez))


# --------------------------------------------------------------------------- #
# the loader flag
# --------------------------------------------------------------------------- #
def _expected_flat_dict(path):
    """Exactly what ``load_dump`` returned before the volume flag existed."""
    with np.load(path) as data:
        return {
            "path": path,
            poc_app.PLANE_KEY: np.asarray(data[poc_app.PLANE_KEY]),
            "nstep": int(data["nstep"]),
            "nx": int(data["nx"]),
            "ny": int(data["ny"]),
            "nz": int(data["nz"]),
            "cell_m": float(data["cell_m"]),
        }


def test_the_flag_defaults_off():
    assert poc_app.load_dump.__kwdefaults__ == {"e_volume": False, "e_raw": False}


def test_flag_off_reads_the_default_dump_exactly_as_before():
    info = poc_app.load_dump(DEFAULT_DUMP)
    expected = _expected_flat_dict(DEFAULT_DUMP)
    assert set(info) == set(expected)
    for key, value in expected.items():
        if key == "path":
            assert info[key] == value
        elif isinstance(value, np.ndarray):
            assert np.array_equal(info[key], value)
        else:
            assert info[key] == value
    assert poc_app.VOLUME_KEY not in info


def test_flag_on_adds_the_cell_centred_volume():
    info = poc_app.load_dump(DEFAULT_DUMP, e_volume=True)
    nx, ny, nz = info["nx"], info["ny"], info["nz"]
    volume = info[poc_app.VOLUME_KEY]
    assert volume.shape == (nx, ny, nz, 3)
    assert volume.dtype == np.float64

    with np.load(DEFAULT_DUMP) as data:
        flat = np.asarray(data["e"])
    ex, ey, ez = edge_to_cell_centres(flat, nx, ny, nz)
    assert np.array_equal(volume[..., 0], ex)
    assert np.array_equal(volume[..., 1], ey)
    assert np.array_equal(volume[..., 2], ez)
    # The plane and the scalars are untouched by asking for the volume.
    assert np.array_equal(info[poc_app.PLANE_KEY],
                          _expected_flat_dict(DEFAULT_DUMP)[poc_app.PLANE_KEY])


def test_flag_on_without_an_e_key_says_so_and_keeps_the_plane(tmp_path, capsys):
    path = tmp_path / "plane_only.npz"
    plane = np.zeros((3, 4, 5), dtype=complex)
    np.savez(path, plane_ez=plane, nstep=np.array(1), nx=np.array(2),
             ny=np.array(3), nz=np.array(4), cell_m=np.array(1e-4))

    info = poc_app.load_dump(path, e_volume=True)
    assert poc_app.VOLUME_KEY not in info
    assert np.array_equal(info[poc_app.PLANE_KEY], plane)
    assert info["nx"] == 2 and info["ny"] == 3 and info["nz"] == 4
    lines = [line for line in capsys.readouterr().err.splitlines() if line]
    assert len(lines) == 1
    assert "no 'e' edge vector" in lines[0]


def test_a_2d_plane_is_still_refused_with_the_volume_flag_on(tmp_path):
    path = tmp_path / "flat_plane.npz"
    np.savez(path, plane_ez=np.zeros((4, 5)),
             nstep=np.array(1), nx=np.array(2), ny=np.array(3), nz=np.array(4),
             cell_m=np.array(1e-4))
    with pytest.raises(SystemExit) as excinfo:
        poc_app.load_dump(path, e_volume=True)
    assert excinfo.value.code == 2
