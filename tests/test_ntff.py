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

import math
import warnings

import numpy as np
import pytest

from emfit.grid import Grid
from emfit.huygens import HuygensBounds
from emfit.huygens_fields import SurfaceRecorder
from emfit.materials import C0, ETA0
from emfit.ntff import (
    FarField,
    SCHEMA_VERSION,
    SurfaceDump,
    far_field,
    integration_angles,
    load_surface_dump,
    radiation_vectors,
    total_radiated_power,
)
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


# ---------------------------------------------------------------------------
# The transform, graded against the one radiator whose far field is known in
# closed form.  The fields below are written out from the source integral
# (first principles) rather than imported from another test module, so the
# fixture and the thing it grades cannot share a mistake: the surface record
# is the *exact* dipole field sampled on a closed cube, the transform is asked
# what that cube radiates, and the answer is compared with the dipole's own
# pattern, its own radiated power, and its own near-field flux through the
# same cube.
#
# The box half-width is ``LAM / 3`` (a third of a wavelength, side ``2 LAM/3``)
# at ``f = 1 GHz``: close enough in that the 1/r, 1/r^2 and 1/r^3 terms all
# matter on the record -- which is the point, a far-field-only fixture would
# not exercise the equivalent currents -- and small enough that a modest
# number of patches keeps the one-point rule accurate.
# ---------------------------------------------------------------------------

DIPOLE_FREQ = 1.0e9
DIPOLE_MOMENT = 1.0e-3
LAM = C0 / DIPOLE_FREQ
HALF_WIDTH = LAM / 3.0


def _frame(axis):
    """An orthonormal frame whose third column is ``axis``."""
    u3 = np.asarray(axis, dtype=float)
    u3 = u3 / np.linalg.norm(u3)
    if abs(u3[0]) < 0.9:
        helper = np.array([1.0, 0.0, 0.0])
    else:
        helper = np.array([0.0, 1.0, 0.0])
    u1 = np.cross(helper, u3)
    u1 = u1 / np.linalg.norm(u1)
    u2 = np.cross(u3, u1)
    return np.stack((u1, u2, u3), axis=1)


def _dipole_fields(pos, freq=DIPOLE_FREQ, moment=DIPOLE_MOMENT,
                   axis=(0.0, 0.0, 1.0)):
    """``E`` and ``H`` phasors of a Hertzian dipole (first principles).

    A current element ``I dl = j omega m`` along ``+z`` has, at a point
    ``r (cos phi sin theta, sin phi sin theta, cos theta)``::

        E_r  = eta m cos(theta) / (2 pi r^2) (1 + 1/(jkr)) e^{-jkr}
        E_th = eta m sin(theta) / (4 pi r) (jk) (1 + 1/(jkr) - 1/(kr)^2) e^{-jkr}
        H_ph =     m sin(theta) / (4 pi r) (jk) (1 + 1/(jkr))      e^{-jkr}

    with every other component zero -- the standard multipole expansion of the
    retarded vector potential truncated at the electric dipole.  ``e^{+j omega
    t}`` is the kernel's convention, hence the outgoing ``e^{-jkr}`` and the
    ``+jk`` prefactors.  ``axis`` only rotates the frame: the field is built
    along ``+z`` and rotated back, so an ``x``-directed dipole costs nothing.
    """
    pos = np.atleast_2d(np.asarray(pos, dtype=float))
    rot = _frame(axis)
    local = pos @ rot
    x, y, z = local[:, 0], local[:, 1], local[:, 2]
    r = np.sqrt(x * x + y * y + z * z)
    rho = np.hypot(x, y)
    k = 2.0 * math.pi * freq / C0
    jkr = 1j * k * r
    out = np.exp(-jkr)
    cos_t = z / r
    sin_t = rho / r
    e_r = (ETA0 * moment * cos_t / (2.0 * math.pi * r ** 2)
           * (1.0 + 1.0 / jkr) * out)
    # 1/(jkr)**2 == -1/(k r)**2, so THIS sign is what makes the closed-surface
    # flux equal P_rad at every radius; see
    # test_dipole_fixture_conserves_power_on_a_sphere.
    e_t = (ETA0 * moment * sin_t / (4.0 * math.pi * r) * (1j * k)
           * (1.0 + 1.0 / jkr + 1.0 / jkr ** 2) * out)
    h_p = (moment * sin_t / (4.0 * math.pi * r) * (1j * k)
           * (1.0 + 1.0 / jkr) * out)
    cos_p, sin_p = x / rho, y / rho
    u_r = local / r[:, None]
    u_th = np.stack((cos_t * cos_p, cos_t * sin_p, -sin_t), axis=-1)
    u_ph = np.stack((-sin_p, cos_p, np.zeros_like(r)), axis=-1)
    e_local = e_r[:, None] * u_r + e_t[:, None] * u_th
    h_local = h_p[:, None] * u_ph
    return e_local @ rot.T, h_local @ rot.T


def _spherical(theta, phi):
    """``rhat``, ``e_theta``, ``e_phi`` at flat angles, each ``(n, 3)``."""
    sin_t, cos_t = np.sin(theta), np.cos(theta)
    sin_p, cos_p = np.sin(phi), np.cos(phi)
    zero = np.zeros_like(theta)
    r_hat = np.stack((sin_t * cos_p, sin_t * sin_p, cos_t), axis=-1)
    e_th = np.stack((cos_t * cos_p, cos_t * sin_p, -sin_t), axis=-1)
    e_ph = np.stack((-sin_p, cos_p, zero), axis=-1)
    return r_hat, e_th, e_ph


def _cube_geometry(n_patch, half=HALF_WIDTH):
    """Patch centres, outward normals, face ids and areas of a closed cube.

    Face order is the writer's: ``0..5`` for ``xmin, xmax, ymin, ymax, zmin,
    zmax``, one patch per primal face cell at its centre, so the areas are all
    the same ``step^2``.
    """
    step = 2.0 * half / n_patch
    centres = (np.arange(n_patch) + 0.5) * step - half
    u, v = np.meshgrid(centres, centres, indexing="ij")
    u, v = u.ravel(), v.ravel()
    coords, normals, faces = [], [], []
    planes = ((-half, 0), (half, 0), (-half, 1), (half, 1),
              (-half, 2), (half, 2))
    for face, (value, axis) in enumerate(planes):
        a, b = [i for i in range(3) if i != axis]
        pts = np.empty((u.size, 3))
        pts[:, axis] = value
        pts[:, a] = u
        pts[:, b] = v
        normal = np.zeros(3)
        normal[axis] = -1.0 if value < 0.0 else 1.0
        coords.append(pts)
        normals.append(np.tile(normal, (u.size, 1)))
        faces.append(np.full(u.size, face, dtype=np.int8))
    return (np.concatenate(coords), np.concatenate(normals),
            np.concatenate(faces), np.full(6 * u.size, step ** 2), step)


def _slots(vec, normals):
    """A full tangential 3-vector on the two non-normal axes, ``(n, 2)``.

    Ascending axis order excluding the normal, the convention
    :meth:`SurfaceRecorder.save_npz` writes.
    """
    axis_of = np.argmax(normals != 0.0, axis=1)
    out = np.empty((vec.shape[0], 2), dtype=np.complex128)
    for axis in range(3):
        mask = axis_of == axis
        if not mask.any():
            continue
        keep = [i for i in range(3) if i != axis]
        out[mask] = vec[mask][:, keep]
    return out


def _assemble(freqs, coords, normals, face_id, dA, e_full, h_full, j_s, m_s,
              step):
    """A ``SurfaceDump`` from full 3-vectors, ready for the loader's rules."""
    freqs = np.atleast_1d(np.asarray(freqs, dtype=float))
    n_freq = freqs.size
    n = coords.shape[0]
    e_t = np.empty((n_freq, n, 2), dtype=np.complex128)
    h_t = np.empty((n_freq, n, 2), dtype=np.complex128)
    flux_face = np.empty((n_freq, n), dtype=np.complex128)
    for i in range(n_freq):
        e_t[i] = _slots(e_full[i], normals)
        h_t[i] = _slots(h_full[i], normals)
        flux_face[i] = np.einsum(
            "qc,qc->q", np.cross(e_full[i], np.conj(h_full[i])), normals) * dA
    return SurfaceDump(
        schema_version=SCHEMA_VERSION,
        stray=False,
        dt=1.0 / (40.0 * float(freqs.max())),
        dx=step,
        dy=step,
        dz=step,
        colocation_rule="analytic fixture: E and H co-located at the patch "
                        "centre",
        freqs=freqs,
        coordinates=coords,
        normals=normals,
        face_id=face_id,
        dA=dA,
        E_t=e_t,
        H_t=h_t,
        J_s=j_s,
        M_s=m_s,
        flux=0.5 * np.real(flux_face.sum(axis=1)),
        flux_face=flux_face,
    )


def _cube_dump(n_patch, axis=(0.0, 0.0, 1.0), half=HALF_WIDTH,
               freqs=(DIPOLE_FREQ,)):
    """The exact dipole field on a closed cube, as the writer would record it.

    ``J_s = n_hat x H`` and ``M_s = -n_hat x E`` are the writer's own
    construction, applied to the analytic field; ``flux_face`` is the true
    Poynting integrand, and ``cross(E, H*).n`` is unchanged by dropping the
    normal components, so using the tangential parts costs nothing.
    """
    coords, normals, face_id, dA, step = _cube_geometry(n_patch, half)
    freqs = np.atleast_1d(np.asarray(freqs, dtype=float))
    e_full, h_full, j_s, m_s = [], [], [], []
    for freq in freqs:
        e, h = _dipole_fields(coords, freq, DIPOLE_MOMENT, axis)
        e_t = e - normals * np.einsum("qc,qc->q", e, normals)[:, None]
        h_t = h - normals * np.einsum("qc,qc->q", h, normals)[:, None]
        e_full.append(e_t)
        h_full.append(h_t)
        j_s.append(np.cross(normals, h_t))
        m_s.append(-np.cross(normals, e_t))
    return _assemble(freqs, coords, normals, face_id, dA,
                     np.array(e_full), np.array(h_full), np.array(j_s),
                     np.array(m_s), step)


def _currents_dump(coord, normal, area, j_s, m_s):
    """A one-patch dump from stored currents (fields derived, not assumed)."""
    coord = np.atleast_2d(np.asarray(coord, dtype=float))
    normal = np.atleast_2d(np.asarray(normal, dtype=float))
    j_s = np.atleast_2d(np.asarray(j_s, dtype=complex))
    m_s = np.atleast_2d(np.asarray(m_s, dtype=complex))
    e_t = np.cross(normal, m_s)
    h_t = np.cross(j_s, normal)
    axis_of = int(np.argmax(normal[0] != 0.0))
    return _assemble([DIPOLE_FREQ], coord, normal,
                     np.array([axis_of], dtype=np.int8),
                     np.atleast_1d(np.asarray(area, dtype=float)),
                     e_t[None], h_t[None], j_s[None], m_s[None],
                     math.sqrt(float(np.atleast_1d(area)[0])))


def _random_dump(n_patch, seed=20240607):
    """Random *tangential* equivalent currents on the same cube."""
    coords, normals, face_id, dA, step = _cube_geometry(n_patch)
    rng = np.random.default_rng(seed)
    shape = (coords.shape[0], 3)
    raw_j = rng.normal(size=shape) + 1j * rng.normal(size=shape)
    raw_m = rng.normal(size=shape) + 1j * rng.normal(size=shape)
    j_s = raw_j - normals * np.einsum("qc,qc->q", raw_j, normals)[:, None]
    m_s = raw_m - normals * np.einsum("qc,qc->q", raw_m, normals)[:, None]
    e_t = np.cross(normals, m_s)
    h_t = np.cross(j_s, normals)
    return _assemble([DIPOLE_FREQ], coords, normals, face_id, dA,
                     e_t[None], h_t[None], j_s[None], m_s[None], step)


def _rebuild(dump, **overrides):
    """The same archive with some arrays replaced, re-validated on the way in."""
    fields = {
        "schema_version": dump.schema_version,
        "stray": dump.stray,
        "dt": dump.dt,
        "dx": dump.dx,
        "dy": dump.dy,
        "dz": dump.dz,
        "colocation_rule": dump.colocation_rule,
        "freqs": dump.freqs,
        "coordinates": dump.coordinates,
        "normals": dump.normals,
        "face_id": dump.face_id,
        "dA": dump.dA,
        "E_t": dump.E_t,
        "H_t": dump.H_t,
        "J_s": dump.J_s,
        "M_s": dump.M_s,
        "flux": dump.flux,
        "flux_face": dump.flux_face,
    }
    fields.update(overrides)
    return SurfaceDump(**fields)


def _analytic_prad(freq=DIPOLE_FREQ, moment=DIPOLE_MOMENT):
    """``eta k^2 m^2 / (12 pi)``: the dipole's total radiated power, in W."""
    k = 2.0 * math.pi * freq / C0
    return ETA0 * k ** 2 * moment ** 2 / (12.0 * math.pi)


# --- A6b: the fixture itself, before anything is graded against it ---------

def test_fixture_flux_matches_analytic_prad():
    """The fixture's own Poynting flux through the cube is the radiated power.

    Nothing about the transform is asserted here: this is the analytic record
    graded against the closed-form ``eta k^2 m^2 / (12 pi)``, so a broken
    fixture is caught before it can make a broken transform look right.  The
    only error left is the one-point rule on each face, ``O((kh)^2)``, whose
    ratio is ``4`` per halving.
    """
    ratios = {n: float(_cube_dump(n).flux[0]) / _analytic_prad()
              for n in (8, 16, 32)}
    assert all(abs(r - 1.0) < 2.5e-2 for r in ratios.values())
    assert abs(ratios[32] - 1.0) < abs(ratios[8] - 1.0)


# --- A1: the radiation integrals, by hand ----------------------------------

def test_radiation_vectors_of_a_single_patch():
    """``J_tilde`` is one phase factor times ``J_s dA`` -- no more, no less."""
    k = 2.0 * math.pi * DIPOLE_FREQ / C0
    coord = np.array([[0.13, -0.07, 0.21]])
    normal = np.array([[0.0, 0.0, 1.0]])
    area = np.array([2.5e-3])
    j_s = np.array([[0.3 - 0.2j, 0.11j, 0.0]])
    m_s = np.array([[0.05 + 0.01j, -0.4j, 0.0]])
    dump = _currents_dump(coord, normal, area, j_s, m_s)
    theta = np.array([0.3, 1.1, math.pi / 2.0, 2.0])
    phi = np.array([0.0, 0.7, 2.4, 5.0])
    j_tilde, m_tilde = radiation_vectors(dump, theta, phi)
    r_hat, _, _ = _spherical(theta, phi)
    phase = np.exp(1j * k * (r_hat @ coord.T))[:, 0]
    assert np.allclose(j_tilde, j_s * area[:, None] * phase[:, None],
                       rtol=1e-13, atol=0.0)
    assert np.allclose(m_tilde, m_s * area[:, None] * phase[:, None],
                       rtol=1e-13, atol=0.0)


# --- A2: the vector identity, against a literal cross product --------------

def test_far_field_matches_literal_nested_cross_product():
    """``rhat x (rhat x J)`` really is what the kernel's algebra computes."""
    dump = _random_dump(3)
    theta, phi = integration_angles(5, 7)
    far = far_field(dump, theta, phi)
    k = 2.0 * math.pi * DIPOLE_FREQ / C0
    j_tilde, m_tilde = radiation_vectors(dump, theta, phi)
    r_hat, e_th, e_ph = _spherical(theta, phi)
    want_th = np.empty(theta.size, dtype=np.complex128)
    want_ph = np.empty(theta.size, dtype=np.complex128)
    for i in range(theta.size):
        r = r_hat[i]
        f = (1j * k / (4.0 * math.pi)) * (
            ETA0 * np.cross(r, np.cross(r, j_tilde[i]))
            + np.cross(r, m_tilde[i]))
        want_th[i] = f @ e_th[i]
        want_ph[i] = f @ e_ph[i]
    for got, want in ((far.E_theta, want_th), (far.E_phi, want_ph)):
        assert np.allclose(got, want, rtol=1e-13,
                           atol=1e-13 * float(np.abs(want).max()))


# --- A4: peak directivity of a Hertzian dipole is exactly 1.5 --------------

def test_hertzian_directivity_is_one_point_five():
    """``D = 4 pi U / P_rad`` at 90 degrees: 1.5, i.e. 1.7609 dBi.

    The amplitude is checked too, because ``D`` alone cannot see an overall
    scale: ``F_theta = j eta k m / (4 pi)`` at broadside is the far field of
    the same moment, so the two together pin the absolute calibration of the
    transform and not just its shape.
    """
    dump = _cube_dump(16)
    k = 2.0 * math.pi * DIPOLE_FREQ / C0
    theta = np.array([math.pi / 2.0])
    phi = np.array([0.0])
    far = far_field(dump, theta, phi)
    amplitude = abs(1j * ETA0 * k * DIPOLE_MOMENT / (4.0 * math.pi))
    assert abs(abs(far.E_theta[0]) - amplitude) <= 2.0e-2 * amplitude
    assert abs(far.D[0] - 1.5) <= 2.0e-2 * 1.5


# --- A5: the pattern is sin(theta) -----------------------------------------

def test_hertzian_pattern_is_sin_theta():
    dump = _cube_dump(16)
    theta = np.array([0.2, 0.6, 1.0, 1.4, math.pi / 2.0])
    phi = np.zeros_like(theta)
    far = far_field(dump, theta, phi)
    ratio = np.abs(far.E_theta) / np.abs(far.E_theta[-1])
    assert np.allclose(ratio, np.sin(theta), rtol=1e-2, atol=0.0)


# --- A6c: the fixture's own field conserves power on any closed surface ----

def test_dipole_fixture_conserves_power_on_a_sphere():
    """The closed-surface real Poynting flux is ``P_rad`` at every radius.

    With ``A = 1 + 1/(jkr) - 1/(k r)^2`` and ``B = 1 + 1/(jkr)``,
    ``A conj(B) = 1 - j/(k r)^3``, whose real part is 1, so the closed-surface
    real Poynting flux equals ``eta k^2 m^2 / (12 pi)`` at any radius and
    through any closed surface -- no far-field assumption anywhere.
    """
    n_theta, n_phi = 200, 400
    d_theta = math.pi / n_theta
    d_phi = 2.0 * math.pi / n_phi
    theta = (np.arange(n_theta) + 0.5) * d_theta
    phi = (np.arange(n_phi) + 0.5) * d_phi
    theta, phi = np.meshgrid(theta, phi, indexing="ij")
    theta = theta.ravel()
    phi = phi.ravel()
    sin_theta = np.sin(theta)
    directions = np.stack((np.cos(phi) * sin_theta,
                           np.sin(phi) * sin_theta,
                           np.cos(theta)), axis=-1)
    weight = sin_theta * d_theta * d_phi
    analytic = _analytic_prad()
    for radius in (LAM / 2.0, LAM, 2.0 * LAM):
        e, h = _dipole_fields(radius * directions, DIPOLE_FREQ, DIPOLE_MOMENT)
        radial = 0.5 * np.real(np.einsum(
            "qc,qc->q", np.cross(e, np.conj(h)), directions))
        flux = float(np.sum(radial * weight)) * radius ** 2
        ratio = flux / analytic
        assert abs(ratio - 1.0) < 1e-6, (
            "closed-surface flux / P_rad = %.10f at R = %.6g lambda"
            % (ratio, radius / LAM))


# --- A3: the spherical basis, orthonormal and right handed everywhere ------

def test_the_spherical_basis_is_orthonormal_and_right_handed():
    """Section 3's basis, at interior angles and at both poles.

    ``rhat`` points along the polar axis ``+Z`` with ``phi`` measured from
    ``+X``, so the triple is the closed form written out below and nothing
    else.  What is pinned here is the whole triple at once: the closed forms
    (a basis that is orthonormal but rotated in ``phi`` would pass every other
    check and conjugate ``E_phi``), unit length, mutual orthogonality, and
    ``rhat x e_theta = e_phi`` -- the handedness sign that decides the sign of
    the far field's phase.  The poles are included because a basis is
    evaluated at whatever angle the caller asks for, and ``theta = 0`` and
    ``theta = pi`` are ordinary points of the closed form: only ``rhat`` stops
    depending on ``phi`` there, ``e_theta`` and ``e_phi`` keep their full
    meaning and stay orthonormal to it.

    Tolerances: the three vectors are ``np.sin``/``np.cos`` of the same
    angles, so an orthonormal triple can miss by a few ulps of 1 and no more
    (measured here: 1.1e-16 on the norms, 5.6e-17 on the dot products, 1.1e-16
    on the cross products, 2.2e-16 on the determinant), while the closed-form
    comparison is the identical expression and is required bit for bit.

    The helper is imported inside the test on purpose: the module's own basis
    is what has to be pinned, and the copy in this file (:func:`_spherical`)
    must not stand in for it.
    """
    from emfit.ntff import _unit_vectors

    theta = np.array([0.0, 1e-12, 0.3, math.pi / 2.0, math.pi / 2.0, 2.0,
                      math.pi - 1e-12, math.pi])
    phi = np.array([0.0, 1.0, -2.5, 0.0, math.pi / 2.0, 3.0,
                    2.0 * math.pi - 0.25, 0.0])
    r_hat, e_th, e_ph = _unit_vectors(theta, phi)

    sin_t, cos_t = np.sin(theta), np.cos(theta)
    sin_p, cos_p = np.sin(phi), np.cos(phi)
    closed = {
        "r_hat": np.stack((sin_t * cos_p, sin_t * sin_p, cos_t), axis=-1),
        "e_theta": np.stack((cos_t * cos_p, cos_t * sin_p, -sin_t), axis=-1),
        "e_phi": np.stack((-sin_p, cos_p, np.zeros_like(theta)), axis=-1),
    }
    for name, got in (("r_hat", r_hat), ("e_theta", e_th), ("e_phi", e_ph)):
        expected = closed[name]
        difference = np.abs(got - expected)
        assert np.array_equal(got, expected), (
            "%s is not the closed form: max difference %.3e at theta=%.17g, "
            "phi=%.17g" % (name, difference.max(),
                           theta[int(difference.max(axis=1).argmax())],
                           phi[int(difference.max(axis=1).argmax())]))

    eps = np.finfo(float).eps
    norms = np.stack([np.linalg.norm(v, axis=1) for v in (r_hat, e_th, e_ph)])
    worst = float(np.abs(norms - 1.0).max())
    assert worst <= 4.0 * eps, (
        "max | |v| - 1 | = %.3e = %.2f eps" % (worst, worst / eps))

    for label, first, second in (
            ("rhat . e_theta", r_hat, e_th),
            ("rhat . e_phi", r_hat, e_ph),
            ("e_theta . e_phi", e_th, e_ph)):
        worst = float(np.abs(np.einsum("qc,qc->q", first, second)).max())
        assert worst <= 4.0 * eps, (
            "max |%s| = %.3e = %.2f eps" % (label, worst, worst / eps))

    for label, got, expected in (
            ("rhat x e_theta", np.cross(r_hat, e_th), e_ph),
            ("e_theta x e_phi", np.cross(e_th, e_ph), r_hat),
            ("e_phi x rhat", np.cross(e_ph, r_hat), e_th)):
        worst = float(np.abs(got - expected).max())
        assert worst <= 4.0 * eps, (
            "%s differs from the third unit vector by %.3e = %.2f eps"
            % (label, worst, worst / eps))

    det = np.linalg.det(np.stack((r_hat, e_th, e_ph), axis=1))
    worst = float(np.abs(det - 1.0).max())
    assert worst <= 4.0 * eps, (
        "max |det[rhat, e_theta, e_phi] - 1| = %.3e = %.2f eps"
        % (worst, worst / eps))


# --- A7: the phase block is a memory decision, not a numerical one ---------

def test_block_size_does_not_change_the_far_field():
    """A block of angles changes the rounding, not the answer.

    ``far_field`` never holds the ``(n_angle, n_surface)`` phase matrix whole,
    so it multiplies it in ``block``-row slices.  What that must not do is
    move the result: the radiated power is compared with ``==`` (measured
    identical to the last bit for every block tried, including a ``block``
    larger than the angle count, which is clamped to a single block), and the
    pattern is required to agree to a few ulps.

    A few ulps and not zero, because a slice of one row hands the matmul a
    different shape than a slice of thirty-five, so the accumulator rounds
    differently: measured 1.4e-14 V on ``E_theta`` (2.0 eps of its largest
    entry) and 1.6e-15 on ``U`` (3.0 eps of its largest) at ``block=1``, with
    ``block`` 4, 35 and 1000 bit for bit identical to the default.  The
    16-eps allowance below is the room a 54-term accumulation re-associated
    by the matmul needs; it is not a physical fudge, and the power -- which is
    what every caller reads -- is pinned exactly instead.

    The input power is passed so that the run is about the block: without it
    each call would also emit the by-design "input power is absent" warning.
    """
    dump = _random_dump(3)
    theta, phi = integration_angles(5, 7)
    base = far_field(dump, theta, phi, p_in_w=1.0)
    eps = np.finfo(float).eps
    scale_e = float(max(np.abs(base.E_theta).max(), np.abs(base.E_phi).max()))
    scale_u = float(base.U.max())
    scale_d = float(base.D.max())
    for block in (1, 2, 3, 7, 35, 1000):
        far = far_field(dump, theta, phi, p_in_w=1.0, block=block)
        diff_e = float(max(np.abs(far.E_theta - base.E_theta).max(),
                           np.abs(far.E_phi - base.E_phi).max()))
        diff_u = float(np.abs(far.U - base.U).max())
        diff_d = float(np.abs(far.D - base.D).max())
        assert far.P_rad == base.P_rad, (
            "block=%r moved P_rad by %r W (%.17g vs %.17g)"
            % (block, far.P_rad - base.P_rad, far.P_rad, base.P_rad))
        assert diff_e <= 16.0 * eps * scale_e, (
            "block=%r moved the pattern by %.3e V = %.2f eps of max|E|"
            % (block, diff_e, diff_e / (eps * scale_e)))
        assert diff_u <= 16.0 * eps * scale_u, (
            "block=%r moved U by %.3e = %.2f eps of max|U|"
            % (block, diff_u, diff_u / (eps * scale_u)))
        assert diff_d <= 16.0 * eps * scale_d, (
            "block=%r moved D by %.3e = %.2f eps of max|D|"
            % (block, diff_d, diff_d / (eps * scale_d)))

    for block in (0, -1, -7):
        with pytest.raises(ValueError) as excinfo:
            far_field(dump, theta, phi, p_in_w=1.0, block=block)
        message = str(excinfo.value)
        assert f"block={block}" in message, (
            "the refusal does not name block=%r: %s" % (block, message))
        assert "at least one angle" in message, message


# --- A8: the gain is opt-in, and needs a positive input power --------------

def test_gain_is_opt_in_and_needs_a_positive_input_power():
    """``G = 4 pi U / p_in``, computed only when the caller supplies ``p_in``.

    The archive records the power crossing the surface, not the power the
    source delivered, so the reader must not invent one.  Four things are
    pinned.  (a) Without ``p_in_w`` there is no gain at all: ``G`` and
    ``p_in`` are ``None`` and a ``RuntimeWarning`` names the missing field.
    (b) With it, ``G`` is ``4 pi U / p_in`` exactly (measured residual 0.0)
    and therefore ``G = D P_rad / p_in`` to one rounding of ``D`` (measured
    2.0e-16 of ``max|G|``) -- the two routes agreeing is what says the gain
    was not normalised by something else.  (c) A zero, negative or ``nan``
    input power is refused: a gain is a ratio, and each of those prints as a
    plausible number instead of failing.  (d)
    :func:`total_radiated_power` hands back the ``P_rad`` that was measured,
    not a second quadrature that could disagree with ``D``'s denominator.
    """
    dump = _random_dump(3)
    theta, phi = integration_angles(5, 7)
    with pytest.warns(RuntimeWarning, match="input power is absent"):
        bare = far_field(dump, theta, phi)
    assert bare.G is None, "a gain was invented from an absent input power"
    assert bare.p_in is None, (
        "p_in was set to %r although no input power was passed" % (bare.p_in,))
    assert total_radiated_power(bare) == bare.P_rad, (
        "total_radiated_power = %.17g but P_rad = %.17g"
        % (total_radiated_power(bare), bare.P_rad))

    p_in = 2.0 * bare.P_rad + 0.37
    far = far_field(dump, theta, phi, p_in_w=p_in)
    assert far.p_in == p_in, (
        "p_in = %r, the caller passed %r" % (far.p_in, p_in))
    want = 4.0 * math.pi * far.U / p_in
    scale = float(np.abs(want).max())
    residual = float(np.abs(far.G - want).max()) / scale
    assert residual <= 1e-12, (
        "max |G - 4 pi U / p_in| / max|G| = %.3e" % residual)
    residual = float(np.abs(far.G - far.D * far.P_rad / p_in).max()) / scale
    assert residual <= 1e-12, (
        "max |G - D P_rad / p_in| / max|G| = %.3e (P_rad = %.17g, p_in = %r)"
        % (residual, far.P_rad, p_in))

    for bad in (0.0, -1.0, float("nan")):
        with pytest.raises(ValueError) as excinfo:
            far_field(dump, theta, phi, p_in_w=bad)
        message = str(excinfo.value)
        assert "p_in_w=" in message, message
        assert "positive and finite" in message, message
        assert repr(bad) in message, (
            "the refusal does not name p_in_w=%r: %s" % (bad, message))


# --- A9: freq_index picks the frequency it names, and only the archive's ---

def test_freq_index_selects_the_frequency_it_names():
    """Index ``i`` of a two-frequency archive is the one-frequency archive.

    ``freq_index=0`` reproduces the ``freqs=(f0,)`` record bit for bit and
    ``freq_index=1`` reproduces ``freqs=(f1,)``; the two answers also differ,
    which is the check that catches a kernel that ignores the index and
    always transforms the first frequency.  Measured: identical ``E_theta``,
    ``E_phi``, ``U``, ``G``, ``P_rad`` and ``freq`` against the single-
    frequency archives, and a difference of 1.03 times ``max|E|`` between the
    two frequencies of the twin.

    The index is the archive's, not the caller's array: ``-1`` is out of
    range here, not "the last one", and so is ``n_freq``, both refused with
    the range spelled out.  ``p_in_w`` is supplied only to keep the run about
    the frequency axis instead of the gain.
    """
    twin = _cube_dump(4, freqs=(DIPOLE_FREQ, 2.0 * DIPOLE_FREQ))
    singles = [_cube_dump(4, freqs=(freq,))
               for freq in (DIPOLE_FREQ, 2.0 * DIPOLE_FREQ)]
    theta, phi = integration_angles(4, 6)
    got = [far_field(twin, theta, phi, freq_index=index, p_in_w=1.0)
           for index in (0, 1)]
    for index, single in enumerate(singles):
        want = far_field(single, theta, phi, p_in_w=1.0)
        assert got[index].freq == want.freq, (
            "freq_index=%d gave freq=%r, the single-frequency archive holds %r"
            % (index, got[index].freq, want.freq))
        for name in ("E_theta", "E_phi", "U", "G", "theta", "phi"):
            assert np.array_equal(getattr(got[index], name),
                                  getattr(want, name)), (
                "freq_index=%d: %s differs from the one-frequency archive by "
                "%.3e" % (index, name,
                          float(np.abs(getattr(got[index], name)
                                       - getattr(want, name)).max())))
        assert got[index].P_rad == want.P_rad, (
            "freq_index=%d: P_rad = %.17g, the one-frequency archive gives "
            "%.17g" % (index, got[index].P_rad, want.P_rad))

    scale = float(max(np.abs(got[0].E_theta).max(),
                      np.abs(got[0].E_phi).max()))
    apart = float(max(np.abs(got[0].E_theta - got[1].E_theta).max(),
                      np.abs(got[0].E_phi - got[1].E_phi).max()))
    assert apart > 1e-2 * scale, (
        "freq_index 0 and 1 differ by only %.3e = %.2e of max|E| = %.6g: the "
        "index is not being read" % (apart, apart / scale, scale))

    for bad in (-1, 2):
        with pytest.raises(IndexError) as excinfo:
            far_field(twin, theta, phi, freq_index=bad)
        message = str(excinfo.value)
        assert f"freq_index={bad}" in message, message
        assert "the archive holds 2 frequencies" in message, message
        assert "0..1" in message, message


# --- A10: a current with a normal component is refused, and named ----------

def test_a_non_tangential_current_is_refused_by_entry():
    """``J_s = n_hat x H_t`` has no normal component; a record that does is.

    The writer forms the equivalent current by crossing the unit normal with a
    tangential field, so ``J_s . n_hat`` is zero to rounding -- unless the
    archive was built some other way, in which case that face's contribution
    is silently wrong and the pattern still looks like a pattern.  The reader
    therefore allows ``_NORMAL_TOL = 1e-9`` of ``max|J_s|`` and no more, and
    the refusal names the entry: ``J_s[freq, sample]``, the offending
    projection and the ratio to ``max|J_s|``.

    Both sides of that tolerance are walked here, by adding a component along
    the sample's own outward normal to sample 5 of the 54-sample cube
    :func:`_random_dump` builds.  Measured: a component of 1e-3 of
    ``max|J_s|`` is refused with ``J_s[0, 5]`` in the message, and one of
    1e-12 is accepted and transforms, moving ``P_rad`` by 1e-13 relative --
    which is why the tolerance is a relative one and not an absolute floor on
    the projection.
    """
    dump = _random_dump(3)
    theta, phi = integration_angles(4, 6)
    scale = float(np.abs(dump.J_s).max())
    sample = 5

    refused = np.array(dump.J_s, copy=True)
    refused[0, sample] += 1e-3 * scale * dump.normals[sample]
    worst = float(np.abs(np.einsum("fqc,qc->fq", refused, dump.normals)).max())
    with pytest.raises(ValueError) as excinfo:
        _rebuild(dump, J_s=refused)
    message = str(excinfo.value)
    assert f"J_s[0, {sample}]" in message, (
        "the refusal does not name the entry: %s" % message)
    assert f"|J_s . n_hat|={worst!r}" in message, (
        "the refusal does not report the measured projection %r: %s"
        % (worst, message))
    assert f"max|J_s|={scale!r}" in message, (
        "the refusal does not report max|J_s| = %r: %s" % (scale, message))
    assert "tangential to it" in message, message

    accepted = np.array(dump.J_s, copy=True)
    accepted[0, sample] += 1e-12 * scale * dump.normals[sample]
    loose = _rebuild(dump, J_s=accepted)
    far = far_field(loose, theta, phi, p_in_w=1.0)
    base = far_field(dump, theta, phi, p_in_w=1.0)
    ratio = far.P_rad / base.P_rad
    assert abs(ratio - 1.0) <= 1e-12, (
        "a 1e-12 normal component moved P_rad by %.3e relative (%.17g vs "
        "%.17g)" % (ratio - 1.0, far.P_rad, base.P_rad))

