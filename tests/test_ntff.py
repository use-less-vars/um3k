"""Archive-reader tests for :mod:`emfit.ntff`.

Why these tests look the way they do
------------------------------------
:func:`emfit.ntff.load_surface_dump` is a boundary: on one side a ``.npz``
written by :meth:`emfit.huygens_fields.SurfaceRecorder.save_npz`, on the
other the arrays a far-field transform will consume.  Two things have to be
true of it, and they are tested separately.

The first is that it is *transparent*: what comes back must be the record the
recorder made, to the last bit, with the dtypes and the shapes the writer
documents.  So the round trip is not compared against a hand-built expected
array -- that would test this test's arithmetic -- but against the live
recorder's own properties, saved and re-read, with ``np.array_equal``.  A
reader that quietly casts, transposes or rescales a phasor fails that
comparison, and nothing about the comparison has to be trusted beyond
``numpy``.

The second is that it is *strict*.  Every way an archive can be wrong here is
quiet downstream: a dropped key becomes a ``KeyError`` inside the transform, a
scaled normal scales one face's contribution, a zero area drops a face from a
closed surface, and a single ``nan`` spreads over the whole pattern.  So each
validation rule gets its own test, and each test asserts the substring of the
message that names the offending key and index -- because the message is the
only thing that tells the caller which recording produced the bad archive.

The archive under test is always a *real* one, produced by the recorder from a
recorded surface rather than assembled by the test: a synthesised archive can
disagree with the writer and leave both half right.  The corruptions are then
applied to a copy of that real archive, one key at a time, so a failing test
names the rule that broke rather than the fixture.
"""

import numpy as np
import pytest

from emfit.grid import Grid
from emfit.huygens import HuygensBounds
from emfit.huygens_fields import SurfaceRecorder
from emfit.ntff import SCHEMA_VERSION, SurfaceDump, load_surface_dump
from emfit.operators import CellComplex

NX, NY, NZ = 4, 3, 2
H = 0.1

#: two frequencies, so that an axis swap of the frequency axis cannot hide
FREQS = (1.0e9, 2.0e9)
DT = 2.0e-12


class _Shim:
    """The smallest thing :meth:`SurfaceRecorder.accumulate` will accept."""

    def __init__(self, e, h, dt, time=0.0):
        self.e = e
        self.h = h
        self.dt = dt
        self.time = time


def _complex():
    """A 4x3x2 grid with a closed box on node planes."""
    grid = Grid.uniform(NX, NY, NZ, NX * H, NY * H, NZ * H)
    cc = CellComplex(grid)
    bounds = HuygensBounds(
        xmin=grid.x[1], xmax=grid.x[3],
        ymin=grid.y[1], ymax=grid.y[2],
        zmin=grid.z[0], zmax=grid.z[2])
    return grid, cc, bounds.conform_to(cc)


def _archive(tmp_path, name="surface.npz"):
    """Record a surface for real, save it, and hand back (grid, rec, path).

    The grid unknowns are arbitrary but fixed and non-zero: nothing here is a
    measurement, and a zero field would make every cross product and every
    power in the archive zero, which is exactly the archive a broken reader
    could pass.  The values only have to be reproducible.
    """
    grid, cc, samples = _complex()
    rec = SurfaceRecorder(samples, FREQS, cc=cc)
    rng = np.random.default_rng(20261114)
    e = rng.normal(size=cc.n_edges)
    h = rng.normal(size=cc.n_faces)
    rec(_Shim(e, h, DT, time=DT))
    rec(_Shim(e, h, DT, time=2.0 * DT))
    assert rec.n_samples == 1
    path = tmp_path / name
    rec.save_npz(path)
    return grid, rec, path


def _rewritten(tmp_path, path, name, *, drop=(), **changes):
    """``path`` copied to ``name``, with keys dropped or replaced."""
    with np.load(path) as data:
        keys = {key: data[key] for key in data.files}
    for key in drop:
        del keys[key]
    keys.update(changes)
    out = tmp_path / name
    np.savez(out, **keys)
    return out


def _message(path):
    """The message :func:`load_surface_dump` raises for ``path``."""
    with pytest.raises(ValueError) as excinfo:
        load_surface_dump(path)
    return str(excinfo.value)


# ----------------------------------------------------------------------
# The round trip: the recorder's own numbers, bit for bit
# ----------------------------------------------------------------------

def test_round_trip_returns_the_recorded_arrays(tmp_path):
    """Save a real record, read it back, and compare against the recorder."""
    grid, rec, path = _archive(tmp_path)
    dump = load_surface_dump(path)
    assert isinstance(dump, SurfaceDump)

    # the scalars travel with the arrays: without them the numbers have no
    # units, and ``dt`` is the weight every phasor was integrated with
    assert dump.schema_version == SCHEMA_VERSION
    assert dump.stray is False
    assert dump.dt == rec.dt
    for axis, key in zip("xyz", (dump.dx, dump.dy, dump.dz)):
        assert key == float(np.mean(grid.widths(axis)))
    assert "cos(pi f dt)" in dump.colocation_rule

    # the payload: compared against the live properties, exactly, so a cast,
    # a transpose or a rescale on the way in cannot pass
    for name, live in (("freqs", rec.freqs),
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
        got = getattr(dump, name)
        assert np.array_equal(got, live), name
        assert got.dtype == np.asarray(live).dtype, name
        assert got.shape == np.shape(live), name

    # and the two lengths are the archive's, not zero-length placeholders
    assert dump.freqs.shape == (len(FREQS),)
    assert dump.coordinates.shape[0] == rec.n_surface
    assert dump.E_t.shape == (len(FREQS), rec.n_surface, 2)
    assert dump.J_s.shape == (len(FREQS), rec.n_surface, 3)

    # the frozen promise is the reader's, not the file's: a caller cannot
    # write into the dump and change what the next stage sees
    with pytest.raises(ValueError):
        dump.E_t[0, 0, 0] = 1.0


# ----------------------------------------------------------------------
# The refusals: one test per rule
# ----------------------------------------------------------------------

def test_a_missing_key_is_refused_by_name(tmp_path):
    """An archive without ``flux`` is not a surface dump."""
    _, _, path = _archive(tmp_path)
    broken = _rewritten(tmp_path, path, "no_flux.npz", drop=("flux",))
    message = _message(broken)
    assert "load_surface_dump:" in message
    assert "not a Huygens surface archive" in message
    assert "missing key(s) flux" in message


def test_an_unknown_schema_version_is_refused(tmp_path):
    """A new writer version is a new shape rule; the reader must not guess."""
    _, _, path = _archive(tmp_path)
    broken = _rewritten(tmp_path, path, "v2.npz",
                        schema_version=np.int64(SCHEMA_VERSION + 1))
    message = _message(broken)
    assert f"schema_version={SCHEMA_VERSION + 1}" in message
    assert f"this reader knows {SCHEMA_VERSION} only" in message


def test_a_stray_archive_is_refused(tmp_path):
    """The writer's labelled zeros are not a measurement."""
    _, cc, samples = _complex()
    fresh = SurfaceRecorder(samples, FREQS, cc=cc)
    path = tmp_path / "stray.npz"
    fresh.save_npz(path, stray=True)
    message = _message(path)
    assert "stray=True" in message
    assert "labelled zeros" in message


@pytest.mark.parametrize(
    "corrupt, expected",
    (
        (np.array([2.0, 0.0, 0.0]), "has |n|=2.0"),
        (np.array([0.6, 0.8, 0.0]), "a conformed surface is axis aligned"),
    ),
    ids=("scaled", "rotated"),
)
def test_a_corrupt_normal_is_refused(tmp_path, corrupt, expected):
    """A non-unit or non-axis-aligned normal scales a whole face silently."""
    _, _, path = _archive(tmp_path)
    with np.load(path) as data:
        normals = np.array(data["normals"], dtype=float)
    normals[2] = corrupt
    broken = _rewritten(tmp_path, path, "bad_normals.npz", normals=normals)
    message = _message(broken)
    assert "normals[2]=" in message
    assert expected in message


def test_a_face_with_no_area_is_refused(tmp_path):
    """A zero area is a hole in a closed surface, and cheap to catch."""
    _, _, path = _archive(tmp_path)
    with np.load(path) as data:
        dA = np.array(data["dA"], dtype=float)
    dA[3] = 0.0
    broken = _rewritten(tmp_path, path, "zero_area.npz", dA=dA)
    message = _message(broken)
    assert "dA[3]=0.0" in message
    assert "a face area must be positive" in message


@pytest.mark.parametrize(
    ("key", "index"),
    (("E_t", (1, 4, 0)), ("flux_face", (1, 4))),
    ids=("tangential_field", "face_flux"),
)
def test_a_non_finite_entry_is_refused(tmp_path, key, index):
    """One ``nan`` poisons the spectrum; the message has to say which one."""
    _, _, path = _archive(tmp_path)
    with np.load(path) as data:
        broken_array = np.array(data[key])
    broken_array[index] = np.nan
    broken = _rewritten(tmp_path, path, f"nan_{key}.npz",
                        **{key: broken_array})
    message = _message(broken)
    assert f"{key}: 1 non-finite entry" in message
    assert f"first at index {index}" in message


def test_a_shape_inconsistency_is_refused(tmp_path):
    """``E_t`` with one sample missing: the shape names both counts."""
    _, rec, path = _archive(tmp_path)
    with np.load(path) as data:
        short = np.array(data["E_t"])[:, :-1, :]
    broken = _rewritten(tmp_path, path, "short.npz", E_t=short)
    message = _message(broken)
    n_freq, n_surface = len(FREQS), rec.n_surface
    assert (f"E_t: expected shape ({n_freq}, {n_surface}, 2) "
            f"(n_freq={n_freq}, n_surface={n_surface})") in message
    assert f"got ({n_freq}, {n_surface - 1}, 2)" in message
