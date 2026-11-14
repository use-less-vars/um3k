"""Presentation tests for the Far Field tab's module-level panel builder.

The subject is :func:`poc_app.build_far_field_panel`: the ONE function that
turns a Huygens surface archive into the picture, the rows and the single
sentence the Far Field tab shows, and the ONE place the page is told "there is
no archive" instead of dying on it.

WHY this is reachable from a test at all: the builder is MODULE-LEVEL, for
exactly the reason ``poc_app.build_frequency_chart`` is - a tab's payload has to
be checkable without a browser, a port or a trame widget, or the only way to
learn what the page would show is to open one. The layout that consumes it is
still asserted, by reading the source of ``run_web_vis`` (the last test): a
``VTab``'s ``value`` and its ``VTabsWindowItem``'s ``value`` have to be the SAME
string, and nothing short of a running browser can observe that from outside.

The archive is a real one - the exact field of a Hertzian dipole on a closed
cube, with ``J_s = n x H_t`` and ``M_s = -n x E_t``, written through
``np.savez`` and read back by :func:`emfit.ntff.load_surface_dump` - because a
PNG that was merely ``not None`` would pass whatever the numbers were.
"""

from __future__ import annotations

import inspect
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server")):
    if _p not in sys.path:
        # the same two entries artifacts/verify_wd.py adds, so `import poc_app`
        # resolves from server/poc_app.py
        sys.path.insert(0, _p)

# In this image pyvista/trame/vtk live in the repo's own venv (its bin/python is
# broken, the site-packages tree is not).  On a host where they are installed
# normally this directory is either absent or already on sys.path, so the block
# is inert there.
_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from emfit.materials import C0, ETA0  # noqa: E402
from emfit.ntff import (  # noqa: E402
    SCHEMA_VERSION,
    SURFACE_DUMP_KEYS,
    SURFACE_DUMP_SCHEMA,
    SurfaceDump,
)

pytest.importorskip(
    "pyvista", reason="pyvista is the web UI's renderer; the page needs it"
)
pytest.importorskip(
    "trame.app", reason="trame serves the page; run_web_vis needs it"
)
pytest.importorskip(
    "trame.ui.vuetify3",
    reason="trame.ui.vuetify3 is what run_web_vis builds its layout with",
)

import poc_app as app  # noqa: E402

DIPOLE_FREQ = 1.0e9
DIPOLE_MOMENT = 1.0e-3
LAM = C0 / DIPOLE_FREQ
HALF_WIDTH = LAM / 3.0
N_PATCH = 8


# ---------------------------------------------------------------------------
# The fixture: a real archive, from first principles
#
# copied from tests/test_antenna.py: tests/ is not a package, so it cannot be
# imported.  Same reasoning there, one level up: the recipe is copied, not
# imported, because pytest promises nothing about test modules importing each
# other.
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
def archive(tmp_path_factory):
    """One dipole archive on disk, written once for every test that reads it."""
    path = tmp_path_factory.mktemp("farfield") / "dipole_surface.npz"
    return _save(_cube_dump(N_PATCH), path)


# ---------------------------------------------------------------------------
# The refusals: the answers the tab exists to give
# ---------------------------------------------------------------------------

def test_no_archive_names_the_missing_input():
    """A run with no --surface-dump gets a sentence naming the flag, not a blank tab."""
    panel = app.build_far_field_panel(None)
    assert panel["image"] is None
    assert panel["rows"] == []
    assert "--surface-dump" in panel["reason"]
    assert panel["caption"].strip()
    assert panel["number"] == ""


def test_a_missing_archive_is_a_reason_not_a_crash(tmp_path):
    """A mistyped path costs the panel one short line, never the page."""
    panel = app.build_far_field_panel(tmp_path / "not_here.npz")
    assert panel["image"] is None
    assert panel["rows"] == []
    reason = panel["reason"]
    assert reason.strip()
    assert reason.isascii()
    assert "\n" not in reason and "\r" not in reason
    assert len(reason) <= 180


# ---------------------------------------------------------------------------
# The success: one picture, its rows, and the ONE number
# ---------------------------------------------------------------------------

def test_a_real_archive_becomes_a_png_data_uri(archive):
    """The archive becomes an embedded PNG plus (label, value) rows - not an empty tab."""
    panel = app.build_far_field_panel(archive)
    image = panel["image"]
    assert image is not None
    assert image.startswith("data:image/png;base64,")
    assert len(image) > 2000
    rows = panel["rows"]
    assert rows
    for row in rows:
        assert isinstance(row, tuple) and len(row) == 2
        assert isinstance(row[0], str) and isinstance(row[1], str)
    assert isinstance(panel["freq"], float) and panel["freq"] > 0.0
    assert isinstance(panel["peak_d_dbi"], float)


def test_the_number_names_both_directivity_and_frequency(archive):
    """The number carries the dBi AND the MHz it was taken at; either alone is unusable."""
    number = app.build_far_field_panel(archive)["number"]
    assert "dBi" in number
    assert "MHz" in number


def test_two_calls_agree(archive):
    """Two calls on one archive publish the same picture and the same sentence."""
    first = app.build_far_field_panel(archive)
    second = app.build_far_field_panel(archive)
    assert first["image"] == second["image"]
    assert first["number"] == second["number"]


def test_the_archive_is_still_refused_as_a_page_dump(archive):
    """load_any_dump still refuses a surface archive, so the two inputs stay apart."""
    with pytest.raises(SystemExit):
        app.load_any_dump(archive)


# ---------------------------------------------------------------------------
# The wiring: one tab value, one window-item value, two emitters
# ---------------------------------------------------------------------------

def test_the_tab_and_its_window_item_share_one_value():
    """A VTab value must EQUAL its VTabsWindowItem's, and a browser is the only other witness.

    WHY a source assertion is the right instrument here.  The tab bar and the
    tab window are two independent widget trees, and vuetify matches them by
    the ``value`` string they are each given.  A mismatch does not raise and
    does not log: the tab bar highlights a tab and the window renders NOTHING,
    which is only observable once a real browser runs the Vue component.  There
    is no browser here, so the source is read instead - it is the only place
    both strings can be compared.  The same reading has to find BOTH emitters
    (inside the tab window, and in the flat stack shown when trame-vuetify is
    absent) and the loader in the layout-time call list, because a panel with a
    tab but no payload shows the empty strings the page booted with.
    """
    src = inspect.getsource(app.run_web_vis)
    assert 'tab_cls("Far Field", value="far_field")' in src
    assert 'tabs_item_cls(value="far_field")' in src
    # Count CALL SITES, not occurrences: the ``def`` line carries the same text.
    calls = [line.strip() for line in src.splitlines()
             if line.strip() == "_emit_far_field_panel()"]
    assert len(calls) == 2
    assert "_load_far_field_panel," in src
