"""Presentation tests for :mod:`emfit.antenna`.

The subject is a viewer, so the tests are about the two things a viewer can get
wrong without anything raising: drawing a *different* pattern from the one the
kernel measured, and dying on input it should have survived.

The archive is a real one -- the exact field of a Hertzian dipole sampled on a
closed cube, with ``J_s = n x H_t`` and ``M_s = -n x E_t``, written through
``np.savez`` and read back by :func:`emfit.ntff.load_surface_dump` -- for the
same reason ``tests/test_ntff.py`` builds its fixture that way: a dipole has a
known peak directivity, ``10 log10(1.5) = 1.7609`` dBi, so the picture and the
``peak_d_dbi`` row can be graded against physics rather than against this
module's own arithmetic.  The fixture recipe below is a copy, not an import, of
the one in ``tests/test_ntff.py``: test modules are not a package, so sharing it
would mean importing across test files, which pytest does not promise.

Everything here runs in well under a second: six faces of 8 x 8 patches, two
plane cuts of 181 angles each.
"""

import base64
import math

import numpy as np
import pytest

from emfit.antenna import build_far_field_report
from emfit.materials import C0, ETA0
from emfit.ntff import (
    SCHEMA_VERSION,
    SURFACE_DUMP_KEYS,
    SURFACE_DUMP_SCHEMA,
    SurfaceDump,
    dbi,
    load_surface_dump,
    plane_cut,
)

#: The report's contract: exactly these keys, on success and on failure alike.
REPORT_KEYS = {
    "image", "rows", "reason", "caption", "freq", "peak_d_dbi", "p_rad",
    "plane_labels",
}

DIPOLE_FREQ = 1.0e9
DIPOLE_MOMENT = 1.0e-3
LAM = C0 / DIPOLE_FREQ
HALF_WIDTH = LAM / 3.0
N_PATCH = 8

#: A Hertzian dipole radiates ``sin^2(theta)``, so its directivity peaks at
#: ``3/2``: this is the number the picture has to agree with.
DIPOLE_PEAK_DBI = 10.0 * math.log10(1.5)      # 1.76091...

#: MEASURED residual: the report peaks at 1.7482341 dBi on this fixture, i.e.
#: 0.0126785 dB below ``10 log10(1.5)``.  The tolerance is that measurement
#: plus 10 % -- enough for the quadrature, far too little to hide a dB-scale
#: normalisation error.
MEASURED_RESIDUAL_DBI = 0.0126785
TOL_DBI = 0.0140


# ---------------------------------------------------------------------------
# The fixture: a real archive, from first principles
# ---------------------------------------------------------------------------

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


def _dipole_fields(pos, freq, moment, axis=(0.0, 0.0, 1.0)):
    """``E`` and ``H`` phasors of a Hertzian dipole along ``axis``, in V/m, A/m."""
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


def _cube_geometry(n_patch, half=HALF_WIDTH):
    """Patch centres, outward normals, face ids, areas and the step of a cube."""
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
    """A tangential 3-vector in the writer's ascending-axis slot order."""
    axis_of = np.argmax(normals != 0.0, axis=1)
    out = np.empty((vec.shape[0], 2), dtype=np.complex128)
    for axis in range(3):
        mask = axis_of == axis
        if not mask.any():
            continue
        keep = [i for i in range(3) if i != axis]
        out[mask] = vec[mask][:, keep]
    return out


def _cube_dump(n_patch, freqs=(DIPOLE_FREQ,), axis=(0.0, 0.0, 1.0)):
    """The exact dipole field on a closed cube, as the writer would record it."""
    coords, normals, face_id, dA, step = _cube_geometry(n_patch)
    freqs = np.atleast_1d(np.asarray(freqs, dtype=float))
    n_freq, n = freqs.size, coords.shape[0]
    e_t = np.empty((n_freq, n, 2), dtype=np.complex128)
    h_t = np.empty((n_freq, n, 2), dtype=np.complex128)
    j_s = np.empty((n_freq, n, 3), dtype=np.complex128)
    m_s = np.empty((n_freq, n, 3), dtype=np.complex128)
    flux_face = np.empty((n_freq, n), dtype=np.complex128)
    for i, freq in enumerate(freqs):
        e, h = _dipole_fields(coords, freq, DIPOLE_MOMENT, axis)
        e = e - normals * np.einsum("qc,qc->q", e, normals)[:, None]
        h = h - normals * np.einsum("qc,qc->q", h, normals)[:, None]
        e_t[i] = _slots(e, normals)
        h_t[i] = _slots(h, normals)
        j_s[i] = np.cross(normals, h)
        m_s[i] = -np.cross(normals, e)
        flux_face[i] = (np.einsum("qc,qc->q", np.cross(e, np.conj(h)),
                                  normals) * dA)
    return SurfaceDump(
        schema_version=SCHEMA_VERSION,
        stray=False,
        dt=1.0 / (40.0 * float(freqs.max())),
        dx=step, dy=step, dz=step,
        colocation_rule="analytic fixture: E and H co-located at the patch "
                        "centre",
        freqs=freqs,
        coordinates=coords,
        normals=normals,
        face_id=face_id,
        dA=dA,
        E_t=e_t, H_t=h_t, J_s=j_s, M_s=m_s,
        flux=0.5 * np.real(flux_face.sum(axis=1)),
        flux_face=flux_face,
    )


def _save(dump, path):
    """Write ``dump`` exactly as ``SurfaceRecorder.save_npz`` does."""
    np.savez(path, schema=SURFACE_DUMP_SCHEMA,
             **{key: getattr(dump, key) for key in SURFACE_DUMP_KEYS})
    return path


@pytest.fixture(scope="module")
def dipole_dump():
    """The dipole archive, built once for the module."""
    return _cube_dump(N_PATCH)


@pytest.fixture(scope="module")
def archive(tmp_path_factory, dipole_dump):
    """That archive on disk, written through ``np.savez`` with the schema key."""
    path = tmp_path_factory.mktemp("antenna") / "dipole_surface.npz"
    return _save(dipole_dump, path)


# ---------------------------------------------------------------------------
# The archive itself, before anything is graded against it
# ---------------------------------------------------------------------------

def test_archive_round_trips_through_the_loader(archive, dipole_dump):
    """A schema-stamped ``np.savez`` of the fixture loads back unchanged.

    Without this the picture tests would be grading a load that quietly
    reordered or dropped something.
    """
    loaded = load_surface_dump(archive)
    assert loaded.schema_version == SCHEMA_VERSION
    assert loaded.freqs.shape == (1,)
    assert float(loaded.freqs[0]) == pytest.approx(DIPOLE_FREQ)
    assert loaded.coordinates.shape == (6 * N_PATCH ** 2, 3)
    assert np.array_equal(loaded.coordinates, dipole_dump.coordinates)
    assert np.array_equal(loaded.J_s, dipole_dump.J_s)
    assert np.array_equal(loaded.dA, dipole_dump.dA)


# ---------------------------------------------------------------------------
# The picture
# ---------------------------------------------------------------------------

def test_report_draws_both_planes(archive):
    """Success returns a real PNG, both plane labels, and no reason."""
    report = build_far_field_report(archive)

    assert set(report) == REPORT_KEYS
    assert report["reason"] is None
    image = report["image"]
    assert isinstance(image, str) and image.startswith("data:image/png;base64,")
    payload = base64.b64decode(image.split(",", 1)[1])
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) > 1000

    labels = report["plane_labels"]
    assert len(labels) == 2
    assert all(isinstance(label, str) and label.isascii() for label in labels)
    assert "E" in labels[0] and "H" in labels[1]
    assert labels[0] != labels[1]
    assert report["caption"].isascii() and report["caption"].endswith(".")


def test_peak_directivity_matches_the_cuts(archive):
    """``peak_d_dbi`` is the larger of the two cuts' own peak directivity."""
    report = build_far_field_report(archive)
    dump = load_surface_dump(archive)
    e_cut = plane_cut(dump, plane="E", freq_index=0)
    h_cut = plane_cut(dump, plane="H", freq_index=0)
    expected = float(dbi(max(e_cut.D.max(), h_cut.D.max())))
    assert report["peak_d_dbi"] == pytest.approx(expected, rel=0.0, abs=1e-12)
    assert report["freq"] == pytest.approx(float(e_cut.freq))
    assert report["p_rad"] == pytest.approx(float(e_cut.P_rad))


def test_peak_directivity_is_a_dipole(archive):
    """The plotted peak is the dipole's ``1.7609`` dBi to a measured tolerance.

    MEASURED: 1.7482341 dBi, a residual of 0.0126785 dB (0.29 % in linear
    terms).  The residual is the one-point-per-face quadrature of ``P_rad`` on
    an 8 x 8 cube, not a defect of this module: ``D = 4 pi U / P_rad``, and only
    ``P_rad`` is approximate here.  ``TOL_DBI`` is that measurement plus 10 %,
    so a real regression -- a wrong normalisation moves this by dB, not by
    milli-dB -- cannot hide underneath it.
    """
    report = build_far_field_report(archive)
    residual = abs(report["peak_d_dbi"] - DIPOLE_PEAK_DBI)
    assert residual < TOL_DBI, (report["peak_d_dbi"], DIPOLE_PEAK_DBI)
    assert report["peak_d_dbi"] == pytest.approx(
        DIPOLE_PEAK_DBI - MEASURED_RESIDUAL_DBI, rel=0.0, abs=1e-6)


# ---------------------------------------------------------------------------
# The rows
# ---------------------------------------------------------------------------

def test_rows_report_frequency_power_and_directivity(archive):
    """The three always-there rows, and no gain row without an input power."""
    rows = build_far_field_report(archive)["rows"]
    assert all(isinstance(row, tuple) and len(row) == 2 for row in rows)
    assert all(isinstance(cell, str) and cell.isascii()
               for row in rows for cell in row)

    by_label = {label: value for label, value in rows}
    assert by_label["Frequency"].startswith("1000.000")
    assert by_label["Frequency"].endswith("MHz")
    assert by_label["Radiated power"].endswith(" W")
    assert by_label["Peak directivity"].endswith(" dBi")
    e_row = next(label for label in by_label if label.startswith("E-plane"))
    h_row = next(label for label in by_label if label.startswith("H-plane"))
    assert "deg" in by_label[e_row] and "deg" in by_label[h_row]
    assert not any(label == "Peak gain" for label in by_label)
    assert not any("\u00b0" in cell for row in rows for cell in row)


def test_gain_row_appears_with_an_input_power(archive):
    """A positive ``p_in_w`` adds exactly one gain row."""
    plain = build_far_field_report(archive)["rows"]
    driven = build_far_field_report(archive, p_in_w=0.5)["rows"]
    gain = [value for label, value in driven if label == "Peak gain"]
    assert len(gain) == 1 and gain[0].endswith(" dBi")
    assert len(driven) == len(plain) + 1


# ---------------------------------------------------------------------------
# The degraded paths: a dict, never an exception
# ---------------------------------------------------------------------------

def test_missing_archive_is_reported(tmp_path):
    """A path that does not exist names the path, in one line."""
    missing = tmp_path / "nope.npz"
    report = build_far_field_report(missing)
    assert set(report) == REPORT_KEYS
    assert report["image"] is None
    assert report["rows"] == [] and report["plane_labels"] == []
    assert "not found" in report["reason"] and str(missing) in report["reason"]
    assert "\n" not in report["reason"]


def test_a_file_that_is_not_a_surface_dump_is_reported(tmp_path):
    """An ``.npz`` of the wrong keys is a reason, not a traceback."""
    junk = tmp_path / "junk.npz"
    np.savez(junk, junk=np.arange(3))
    report = build_far_field_report(junk)
    assert set(report) == REPORT_KEYS
    assert report["image"] is None
    assert report["reason"] and "not a surface dump" in report["reason"]
    assert "\n" not in report["reason"]


def test_out_of_range_frequency_index_is_reported(tmp_path):
    """An index the archive does not have is named with the count it exceeded."""
    two_freq = _save(_cube_dump(4, freqs=(DIPOLE_FREQ, 3.0 * DIPOLE_FREQ)),
                     tmp_path / "two_freq.npz")
    report = build_far_field_report(two_freq, freq_index=99)
    assert set(report) == REPORT_KEYS
    assert report["image"] is None
    assert "freq_index 99" in report["reason"]
    assert "2 frequencies" in report["reason"]


def test_missing_matplotlib_is_reported(archive, monkeypatch):
    """With no pyplot the module degrades instead of raising ``ImportError``."""
    monkeypatch.setattr("emfit.antenna._import_pyplot", lambda: None)
    report = build_far_field_report(archive)
    assert set(report) == REPORT_KEYS
    assert report["image"] is None
    assert report["reason"] and "matplotlib" in report["reason"]


# ---------------------------------------------------------------------------
# Housekeeping: the viewer is called in a loop, so it must not leak figures
# ---------------------------------------------------------------------------

def test_no_figure_leak(archive):
    """Every figure the report opens is closed again."""
    plt = pytest.importorskip("matplotlib.pyplot")
    before = len(plt.get_fignums())
    for _ in range(2):
        report = build_far_field_report(archive)
        assert report["reason"] is None
    assert len(plt.get_fignums()) == before
