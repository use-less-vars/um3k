"""``server/trame_vtk_hardening.py``: what it patches, and what it promises.

The page re-draws every tick, so the stock trame_vtk 2.11.17 bookkeeping is the
problem these tests pin:

* ``serialize.remove`` raises out of a VTK delete observer for an id it no longer
  tracks (``serializers/serialize.py:44-46``, ``list.remove`` on a plain list) -
  it must become total, and ``DELETE_CALLBACKS`` must keep O(1) membership;
* ``helpers.data_array_sha_mapping`` is keyed on the array POINTER and never
  pruned, so it grows without bound AND can answer one array with another
  array's hash once an address is recycled - it must stay bounded and it must
  never answer for an object it was not built from;
* ``helpers.data_table_to_list`` re-unpacks the whole table on every export - an
  unchanged table must be memoised, and the memo must return the same JSON.

Everything here is behaviour of the installed hardening, not of trame_vtk: the
patches are applied by ``install()`` and are undoable, so each test states the
state it needs rather than inheriting it from the previous test.

The parity test at the bottom is the load-bearing one: the SAME scene serialised
with and without the patch must come out byte-for-byte identical once pointer
ids are normalised (they differ between processes by construction).
"""

from __future__ import annotations

import gc
import json
import os
import subprocess
import sys
import types
import weakref
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "server"), str(REPO_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_VENV_SITE = REPO_ROOT / ".venv" / "lib" / "python3.12" / "site-packages"
if _VENV_SITE.is_dir() and str(_VENV_SITE) not in sys.path:
    sys.path.append(str(_VENV_SITE))

pytest.importorskip("trame_vtk", reason="the module under test patches trame_vtk")
pytest.importorskip("vtkmodules", reason="the arrays under test are VTK arrays")

import importlib  # noqa: E402

import trame_vtk_hardening as hardening  # noqa: E402  (after the importorskip guards)
import vtkmodules.vtkCommonCore as vtk_core  # noqa: E402
from trame_vtk.modules.vtk.serializers import cache, helpers  # noqa: E402
from trame_vtk.modules.vtk.serializers import synchronization_context as sync  # noqa: E402

#: ``from ...serializers import serialize`` would hand back the FUNCTION of that
#: name: the package ``__init__`` re-exports it over the module.
serialize = importlib.import_module("trame_vtk.modules.vtk.serializers.serialize")

#: Everything ``install()`` reports having replaced, by name.
EXPECTED_PATCHES = {
    "serialize.remove",
    "serialize.DELETE_CALLBACKS",
    "helpers.digest",
    "helpers.data_array_sha_mapping",
    "helpers.data_table_to_list",
    "cache.cache_properties(PROP_CACHE)",
    "sync.SynchronizationContext.data_array_cache",
}


@pytest.fixture(autouse=True)
def patched():
    """Every test in this file runs against the patched serializers.

    ``install()`` is idempotent and silent once installed, so this is a no-op for
    all but the first test; the teardown re-installs because two tests deliberately
    uninstall (the kill switch, the boot test) and one runs a report-only install.
    """
    hardening.install()
    yield hardening._STATE["report"]
    if not hardening._STATE["installed"]:
        hardening.install()


def _float_array(value, count=4):
    """A VTK float array holding ``value``, ``value + 1``, ... - content is what matters."""
    array = vtk_core.vtkFloatArray()
    array.SetNumberOfComponents(1)
    array.SetNumberOfTuples(count)
    for index in range(count):
        array.SetValue(index, float(value) + index)
    return array


# ---------------------------------------------------------------------------
# what install() reports - and that a second install is a no-op
# ---------------------------------------------------------------------------


def test_install_reports_the_patches_it_applied_and_is_idempotent(capfd):
    capfd.readouterr()  # drop anything already buffered: this test counts lines
    hardening.uninstall()

    report = hardening.install()

    assert report["status"] == "patched", report
    assert set(report["patches"]) == EXPECTED_PATCHES, report["patches"]
    assert report["trame_vtk_version"], "the report must name the version it inspected"
    assert report["problems"] == []

    err = capfd.readouterr().err
    lines = [line for line in err.splitlines() if "trame_vtk hardening" in line]
    assert len(lines) == 1, f"expected ONE hardening line on stderr, got: {err!r}"
    assert "patched" in lines[0]
    assert str(report["trame_vtk_version"]) in lines[0]

    again = hardening.install()

    assert again["status"] == "already_installed", again
    assert set(again["patches"]) == EXPECTED_PATCHES
    assert "trame_vtk hardening" not in capfd.readouterr().err, (
        "a second install re-printed the line; a boot must not narrate twice"
    )


# ---------------------------------------------------------------------------
# P1 - remove() is total, DELETE_CALLBACKS keeps working
# ---------------------------------------------------------------------------


def test_remove_of_an_unknown_id_does_not_raise_and_a_known_id_is_forgotten(patched):
    """A delete event for an id nobody tracks used to raise out of the observer."""
    serialize.remove("instance-id-that-was-never-tracked")  # must not raise

    serialize.DELETE_CALLBACKS.append("tracked-id")
    assert "tracked-id" in serialize.DELETE_CALLBACKS
    serialize.remove("tracked-id")
    assert "tracked-id" not in serialize.DELETE_CALLBACKS

    serialize.remove("tracked-id")  # twice: discarding a gone id is still a no-op


# ---------------------------------------------------------------------------
# P2 - the sha map is bounded and never answers for another array
# ---------------------------------------------------------------------------


def test_the_sha_map_stays_bounded_under_churn(patched):
    """The unpatched map grows with every array the page ever built."""
    churn = 300
    for index in range(churn):
        array = _float_array(index)
        helpers.digest(array)
        del array  # one tick: the array is gone with the frame it was drawn in

    leaked = len(helpers.data_array_sha_mapping)
    assert leaked <= 16, (
        f"the sha map kept {leaked} entries after {churn} dropped arrays: it is "
        "still growing with the number of arrays the page has ever built"
    )

    # While arrays ARE alive they must all be tracked - a cache that is bounded
    # by dropping live entries would re-hash every array on every tick.
    held = [_float_array(index) for index in range(50)]
    for array in held:
        helpers.digest(array)
    assert len(helpers.data_array_sha_mapping) >= 50

    del held
    gc.collect()
    assert len(helpers.data_array_sha_mapping) <= 16, (
        "the records outlived the arrays they describe"
    )


def test_the_digest_cache_evicts_at_its_cap(patched):
    """The hard cap, unit-tested: 40 live arrays against a cache that holds 8."""
    bounded = hardening._DigestCache(maxsize=8)
    alive = []
    for index in range(40):
        array = _float_array(index)
        alive.append(array)  # alive on purpose: nothing may be pruned by the weakref
        bounded.lookup(array, helpers.hash_data_array, helpers.reference_id)

    assert len(bounded) == 8
    assert bounded.recomputed == 40


def test_a_recycled_address_cannot_be_answered_with_another_arrays_sha(patched):
    """The real defect: the unpatched map is keyed on the POINTER.

    Once a freed array's address comes back as a different array, the old record
    answers for it - a stale hash handed to a fresh array.  The hardening keys on
    ``id()`` but validates with the weakref it stored, so a record only ever
    answers for the very object it was built from.
    """
    digests = hardening._DIGEST_CACHE
    digests.clear()

    first = _float_array(1.0)
    sha_first = helpers.digest(first)
    del first
    gc.collect()

    second = _float_array(2.0)  # may well land on the freed address
    sha_second = helpers.digest(second)
    assert sha_second == helpers.hash_data_array(second)
    assert sha_second != sha_first

    # Forge exactly the record the pointer-keyed implementation would have left
    # behind: right key, right mtime, and a weakref to a DIFFERENT object.
    other = _float_array(9.0)
    digests.data[id(second)] = {
        "sha": sha_first,
        "mtime": second.GetMTime(),
        "ref": weakref.ref(other),
        "instance": helpers.reference_id(second),
        "fingerprint": (helpers.reference_id(second), second.GetMTime(), None),
    }
    assert helpers.digest(second) != sha_first, (
        "a stale record answered for an array it was not built from"
    )
    assert helpers.digest(second) == sha_second


# ---------------------------------------------------------------------------
# P3 - the lookup-table export is memoised
# ---------------------------------------------------------------------------


def test_data_table_to_list_memoises_an_unchanged_table(patched):
    import vtk

    lut = vtk.vtkLookupTable()
    lut.SetNumberOfTableValues(16)
    lut.Build()
    table = lut.GetTable()

    hardening._TABLE_CACHE.clear()
    recomputed = hardening._TABLE_CACHE.recomputed

    first = helpers.data_table_to_list(table)
    same = helpers.data_table_to_list(lut.GetTable())

    assert same is first, "an unchanged table was re-unpacked"
    assert hardening._TABLE_CACHE.recomputed == recomputed + 1
    assert hardening._TABLE_CACHE.hits >= 1

    # Same JSON as the list-of-lists it replaces: tuple-of-tuples, same numbers.
    assert isinstance(first, tuple) and all(isinstance(row, tuple) for row in first)
    components = table.GetNumberOfComponents()
    values = [table.GetValue(index) for index in range(table.GetNumberOfValues())]
    expected = [
        values[index * components : (index + 1) * components]
        for index in range(len(values) // components)
    ]
    assert [list(row) for row in first] == expected


# ---------------------------------------------------------------------------
# fail-safe: a trame_vtk this module does not understand is left alone
# ---------------------------------------------------------------------------


def test_a_module_that_does_not_match_is_reported_and_never_raises(patched):
    """A missing seam must produce a report, not an exception and not a patch."""
    real = {"serialize": serialize, "cache": cache, "helpers": helpers, "sync": sync}
    stubs = {}
    for key, module in real.items():
        stub = types.ModuleType(f"trame_vtk.stub.{key}")
        stub.__dict__.update(module.__dict__)
        stub.__name__ = f"trame_vtk.stub.{key}"
        stubs[key] = stub
    del stubs["helpers"].digest  # the attribute P2 wraps

    real_remove = serialize.remove
    report = hardening.install(modules=stubs)

    assert report["status"] == "not_patched", report
    assert any("digest" in problem for problem in report["problems"]), report["problems"]
    assert serialize.remove is real_remove, "a report-only run patched the real module"
    assert callable(helpers.digest)
    assert hardening._STATE["installed"] is True


def test_the_kill_switch_leaves_trame_vtk_alone(monkeypatch, capfd):
    capfd.readouterr()
    hardening.uninstall()
    original_remove = serialize.remove

    monkeypatch.setenv("POC_NO_VTK_PATCH", "1")
    report = hardening.install()
    assert report["status"] == "disabled", report
    assert serialize.remove is original_remove, "the kill switch still patched"
    assert "trame_vtk hardening" not in capfd.readouterr().err

    monkeypatch.setenv("POC_NO_VTK_PATCH", "0")
    report = hardening.install()
    assert report["status"] == "patched", report
    assert serialize.remove is not original_remove
    assert "trame_vtk hardening" in capfd.readouterr().err


# ---------------------------------------------------------------------------
# the load-bearing one: the wire payload does not change
# ---------------------------------------------------------------------------

#: One scene, serialised twice, with every 16-hex-digit pointer id normalised to
#: its first-appearance index.  Run in a subprocess twice: patched and killed.
_CHILD = r'''
import json
import re
import sys

import trame_vtk_hardening as hardening

report = hardening.install()
print("STATUS=%s" % report["status"], file=sys.stderr)

import vtkmodules.vtkCommonCore as vtk_core
import numpy as np
import pyvista as pv
from trame_vtk.modules.vtk.serializers import (
    SynchronizationContext,
    helpers,
    initialize_serializers,
    serialize,
)

initialize_serializers()

for i in range(120):
    array = vtk_core.vtkFloatArray()
    array.SetNumberOfComponents(1)
    array.SetNumberOfTuples(4)
    for j in range(4):
        array.SetValue(j, float(i * 4 + j))
    helpers.digest(array)
    del array

print("SHA_MAP_LEN=%d" % len(helpers.data_array_sha_mapping), file=sys.stderr)

plotter = pv.Plotter(off_screen=True)
plotter.suppress_rendering = True
mesh = pv.Sphere()
mesh.point_data["q"] = np.linspace(0, 1, mesh.n_points)
plotter.add_mesh(mesh, scalars="q", colormap="viridis", show_scalar_bar=False)
plotter.add_axes()
context = SynchronizationContext()
payload = [serialize(None, plotter.ren_win, "1", context, 1) for _ in range(2)]

blob = json.dumps(payload, sort_keys=True, default=str)
seen = {}


def normalise(match):
    token = match.group(0)
    if token not in seen:
        seen[token] = "PTR%04d" % len(seen)
    return seen[token]


sys.stdout.buffer.write(re.sub(r"[0-9a-f]{16}", normalise, blob).encode())
sys.stdout.flush()
'''


def test_the_patched_and_unpatched_serializers_emit_the_same_payload(tmp_path):
    child = tmp_path / "parity_child.py"
    child.write_text(_CHILD, encoding="utf-8")

    env = dict(os.environ)
    env.pop("POC_NO_VTK_PATCH", None)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT), str(REPO_ROOT / "server"), str(_VENV_SITE)]
    )

    def run(child_env):
        return subprocess.run(
            [sys.executable, str(child)],
            cwd=str(REPO_ROOT),
            env=child_env,
            capture_output=True,
            timeout=240,
        )

    on = run(env)
    off = run(dict(env, POC_NO_VTK_PATCH="1"))

    assert on.returncode == 0, on.stderr.decode("utf-8", "replace")[-3000:]
    assert off.returncode == 0, off.stderr.decode("utf-8", "replace")[-3000:]
    assert b"STATUS=patched" in on.stderr, on.stderr.decode("utf-8", "replace")[-2000:]
    assert b"trame_vtk hardening" in on.stderr
    assert b"STATUS=disabled" in off.stderr
    assert b"trame_vtk hardening" not in off.stderr

    assert len(on.stdout) > 5000, f"the payload is suspiciously small: {len(on.stdout)} B"
    assert on.stdout == off.stdout, (
        "the patched serializers emitted a different payload than the stock ones"
    )


# ---------------------------------------------------------------------------
# and the line is on a real boot, once
# ---------------------------------------------------------------------------


def test_a_real_boot_prints_the_hardening_line_once(tmp_path, capfd):
    pytest.importorskip("trame.app", reason="trame serves the page")
    pytest.importorskip("trame.ui.vuetify3", reason="run_web_vis builds this UI")
    import test_animation_volume as av  # noqa: PLC0415 - heavy, and needs trame
    import test_poc_bare_board as bb  # noqa: PLC0415 - ditto

    capfd.readouterr()  # the fixtures above may already have printed
    hardening.uninstall()
    page = bb._page(tmp_path)
    try:
        with av._render_doubled():
            bb._boot(page["info"], page)
    finally:
        hardening.install()

    err = capfd.readouterr().err
    lines = [line for line in err.splitlines() if "trame_vtk hardening" in line]
    assert len(lines) == 1, f"expected ONE hardening line on a boot, got {lines!r}"
    assert "patched" in lines[0]


# ---------------------------------------------------------------------------
# and the boot survives a copy that lost the sibling module
# ---------------------------------------------------------------------------

#: A real boot whose ``trame_vtk_hardening`` import hits a poison shim: this file
#: is copied around without its sibling, and the app still has to come up.
_CHILD_BOOT = r'''
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])  # the poison shim must win over server/

import test_animation_volume as av
import test_poc_bare_board as bb

work = Path(sys.argv[2])
page = bb._page(work)
with av._render_doubled():
    bb._boot(page["info"], page)  # asserts internally that it reached server.start
print("BOOT_OK")
sys.stdout.flush()
'''


def test_a_poc_app_without_its_sibling_module_still_boots(tmp_path):
    """One file, no sibling module: the boot must survive a failing import.

    Not a mock - a child process boots the same harness the other boot test uses,
    with ``trame_vtk_hardening`` resolved to a shim that raises ``ImportError``.
    """
    poison = tmp_path / "poison"
    poison.mkdir()
    (poison / "trame_vtk_hardening.py").write_text(
        'raise ImportError("trame_vtk_hardening.py is not installed next to poc_app.py")\n',
        encoding="utf-8",
    )
    child = tmp_path / "boot_without_hardening.py"
    child.write_text(_CHILD_BOOT, encoding="utf-8")

    env = dict(os.environ)
    env.pop("POC_NO_VTK_PATCH", None)
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO_ROOT),
            str(REPO_ROOT / "server"),
            str(REPO_ROOT / "tests"),
            str(_VENV_SITE),
        ]
    )
    done = subprocess.run(
        [sys.executable, str(child), str(poison), str(tmp_path)],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        timeout=240,
    )

    err = done.stderr.decode("utf-8", "replace")
    assert done.returncode == 0, err[-4000:]
    assert "BOOT_OK" in done.stdout.decode("utf-8", "replace"), err[-4000:]

    hardening_lines = [line for line in err.splitlines() if "trame_vtk hardening" in line]
    assert any("not applied" in line for line in hardening_lines), err[-4000:]
    assert not [line for line in hardening_lines if "patched" in line], (
        f"the poisoned child claimed to have patched: {hardening_lines!r}"
    )

