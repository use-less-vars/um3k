"""Headless checks for the local-view (client-side) animation spike.

Nothing here touches a browser, a GPU or a network socket: every assertion is
about the artefacts the prototype produces (npz keys read, label text, colour
limits, packed array contents, serialised wire bytes, injected JS source, and
the *absence* of a per-frame server round-trip).
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from prototypes import local_view_spike as spike

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / "artifacts" / "volume_s59.npz"

pytestmark = pytest.mark.skipif(not NPZ.exists(), reason=f"missing {NPZ}")


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def volume():
    return spike.load_volume(NPZ)


@pytest.fixture(scope="module")
def scene(volume):
    return spike.SpikeScene(volume)


@pytest.fixture(scope="module")
def app(volume):
    return spike.build_app(volume=volume)


# --------------------------------------------------------------------------- #
# 1. data access
# --------------------------------------------------------------------------- #
def test_loads_only_the_keys_it_needs_and_never_e_abs_volume(volume):
    assert "ez_ycut" in volume
    assert set(spike.LOADED_KEYS) <= set(spike.REQUIRED_KEYS)
    assert "e_abs_volume" not in spike.LOADED_KEYS
    assert not any("abs" in key for key in spike.LOADED_KEYS)
    # the field cube itself is not touched either
    assert volume["ez_ycut"].shape == (2400, 62, 22)
    assert set(volume) == set(spike.REQUIRED_KEYS)


def test_frame_numbers_and_stride(volume):
    fi = spike.frame_indices(volume)
    assert fi.size == 2400
    assert int(fi.min()) == 1 and int(fi.max()) == 2400
    assert spike.stride_of(fi) == 1
    # nsteps exists and is a scalar 2400 -- and is NOT the label denominator
    assert int(np.asarray(volume["nsteps"]).ravel()[0]) == 2400


# --------------------------------------------------------------------------- #
# 2. label text (off-by-one guard)
# --------------------------------------------------------------------------- #
def test_label_text_uses_max_frame_number_not_nsteps_minus_one(volume):
    fi = spike.frame_indices(volume)
    stride = spike.stride_of(fi)
    assert spike.label_for_frame(fi, 0, stride) == "Step 1 / 2400 (Stride 1)"
    assert spike.label_for_frame(fi, 1, stride) == "Step 2 / 2400 (Stride 1)"
    assert spike.label_for_frame(fi, 2399, stride) == "Step 2400 / 2400 (Stride 1)"


def test_no_frame_is_labelled_with_the_forbidden_denominator(volume):
    fi = spike.frame_indices(volume)
    stride = spike.stride_of(fi)
    labels = [spike.label_for_frame(fi, k, stride) for k in range(fi.size)]
    assert len(labels) == 2400
    assert not any(lab.startswith("Step 2400 / 2399") for lab in labels)
    assert not any("/ 2399" in lab for lab in labels)
    assert labels[-1] == "Step 2400 / 2400 (Stride 1)"
    assert labels[0] == "Step 1 / 2400 (Stride 1)"


def test_label_rejects_out_of_range_frames(volume):
    fi = spike.frame_indices(volume)
    with pytest.raises(IndexError):
        spike.label_for_frame(fi, 2400, 1)
    with pytest.raises(IndexError):
        spike.label_for_frame(fi, -1, 1)


# --------------------------------------------------------------------------- #
# 3. one global clim, shared by LUT / mapper / JS bootstrap
# --------------------------------------------------------------------------- #
def test_clim_is_computed_once_and_is_symbolic_of_the_whole_series(volume, scene):
    before = spike.CLIM_CALLS
    clim = spike.compute_clim(scene.ez)          # already cached -> no recompute
    assert spike.CLIM_CALLS == before
    assert clim == scene.clim

    ez = np.asarray(volume["ez_ycut"], dtype=np.float64)
    expected = float(np.percentile(np.abs(ez), spike.CLIM_PERCENTILE))
    assert clim[0] == pytest.approx(-expected, rel=1e-9)
    assert clim[1] == pytest.approx(expected, rel=1e-9)
    assert clim[0] < 0 < clim[1]
    assert clim[1] < float(np.abs(ez).max())   # clipped, not the raw max
    assert clim[1] == pytest.approx(25.2712, abs=1e-3)


def test_lut_and_mapper_use_the_same_global_clim(volume, scene):
    assert tuple(scene.lut.GetTableRange()) == pytest.approx(scene.clim)
    assert scene.lut.GetNumberOfTableValues() == spike.LUT_SIZE
    assert tuple(scene.mapper.GetScalarRange()) == pytest.approx(scene.clim)
    assert scene.mapper.GetUseLookupTableScalarRange() == 1

    cfg = spike.bootstrap_cfg(volume, scene)
    assert tuple(cfg["clim"]) == pytest.approx(scene.clim)
    # no per-frame ranges leak into the JS side
    assert len(cfg["clim"]) == 2


# --------------------------------------------------------------------------- #
# 4. the single array really holds every frame
# --------------------------------------------------------------------------- #
def test_packed_array_holds_all_2400_frames(scene, volume):
    ez = np.asarray(volume["ez_ycut"], dtype=np.float32)
    assert scene.components.shape == (scene.npts, 2400)
    assert scene.components.dtype == np.float32

    points = scene.polydata.GetPointData()
    scalars = points.GetScalars()
    assert scalars.GetName() == spike.ARRAY_NAME
    assert scalars.GetNumberOfTuples() == 1364
    assert scalars.GetNumberOfComponents() == 2400

    for k in (0, 1, 17, 1200, 2399):
        block = scene.components[:, k]
        assert np.array_equal(block, ez[k].reshape(-1)), f"frame {k} block mismatch"


def test_plane_geometry_matches_the_slice(scene, volume):
    assert scene.npts == 62 * 22
    assert scene.polydata.GetNumberOfPoints() == 1364
    assert scene.polydata.GetNumberOfPolys() == 2 * 61 * 21
    bounds = scene.polydata.GetBounds()
    assert bounds[0] == pytest.approx(float(volume["x_mm"].min()))
    assert bounds[1] == pytest.approx(float(volume["x_mm"].max()))
    assert bounds[4] == pytest.approx(float(volume["z_mm"].min()))
    assert bounds[5] == pytest.approx(float(volume["z_mm"].max()))


# --------------------------------------------------------------------------- #
# 5. no per-frame server round-trip
# --------------------------------------------------------------------------- #
_FORBIDDEN_CALLS = {
    "push_image",
    "start_animation",
    "capture_image",
    "captureImage",
    "update",
    "scene",
    "flush",
}


def _loop_bodies(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            for child in ast.walk(node):
                yield node, child


def test_no_loop_touches_the_view_per_frame():
    source = Path(spike.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders = []
    for loop, child in _loop_bodies(tree):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if child.func.attr in _FORBIDDEN_CALLS:
                offenders.append((type(loop).__name__, child.func.attr, child.lineno))
    assert offenders == [], f"view updated inside a loop: {offenders}"


def test_no_image_path_or_server_start_in_the_prototype():
    source = Path(spike.__file__).read_text(encoding="utf-8")
    lowered = source.lower()
    for needle in (
        "push_image",
        "start_animation",
        "captureimage",
        "imagedata",
        "vtkremoteview",
        ".png",
        "b64encode",
        "imencode",
        "server.start(",
    ):
        # "server.start()" only appears under the non-dry-run CLI branch; every
        # other needle must be absent from the whole module.
        if needle != "server.start(":
            assert needle not in lowered, f"forbidden mechanism present: {needle}"
    assert source.count("server.start(") == 1
    assert "--dry-run" in source


def test_the_js_loop_is_the_only_frame_driver():
    js = (REPO / "prototypes" / "local_view_spike.js").read_text(encoding="utf-8")
    assert "requestAnimationFrame" in js
    assert "setData(scratch, 1)" in js      # 1-component swap, client-side
    assert "renderWindow.render()" in js
    # the JS never talks to the server
    for needle in ("fetch(", "axios", "socket", "XMLHttpRequest", "trame.trigger"):
        assert needle not in js, f"JS must not contact the server: {needle}"


# --------------------------------------------------------------------------- #
# 6. app builds headless with a LOCAL view, not a remote one
# --------------------------------------------------------------------------- #
def test_app_builds_headless_with_a_local_view(app):
    from trame_vtk.widgets.vtk import VtkLocalView, VtkRemoteView

    assert isinstance(app.view, VtkLocalView)
    assert not isinstance(app.view, VtkRemoteView)
    assert type(app.view).__name__ == "VtkLocalView"
    # the element tag, and the ref the injected JS resolves via window.trame.refs
    assert "vtk-local-view" in str(app.view)
    assert "vtk-remote-view" not in str(app.view)
    # trame registers the component in the very registry the JS reads back:
    # :ref="(el) => trame.refs['spike_local'] = el"
    assert app.view._attributes["ref"] == (
        f':ref="(el) => trame.refs[\'{spike.JS_REF}\'] = el"'
    )
    assert app.view._attributes["view_state"] == f':viewState="scene_{spike.JS_REF}"'

    source = Path(spike.__file__).read_text(encoding="utf-8")
    assert "VtkLocalView" in source
    assert "VtkRemoteView" not in source

    # headless proof: with no client attached view.update() is a no-op, so no
    # scene state was published -- the app builds without a server round-trip
    assert app.cfg["nframes"] == 2400


def test_injected_script_carries_the_bootstrap_and_fits_in_one_state_var(app):
    script = app.script
    assert type(app.script_widget).__name__ == "Script"
    assert "function init(cfg)" in script
    assert "requestAnimationFrame" in script
    cfg_start = script.rindex("window.localViewSpike.init(") + len(
        "window.localViewSpike.init("
    )
    cfg = json.loads(script[cfg_start : script.rindex(")")])
    assert cfg == app.cfg
    assert cfg["nframes"] == 2400
    assert cfg["stride"] == 1
    assert cfg["stepTotal"] == 2400
    assert cfg["frameIndex"][:3] == [1, 2, 3]
    assert cfg["frameIndex"][-1] == 2400
    assert tuple(cfg["clim"]) == pytest.approx(app.scene.clim)
    assert cfg["ref"] == spike.JS_REF
    # the bootstrap must not carry the field data itself
    assert len(script) < 200_000


# --------------------------------------------------------------------------- #
# 7. measured payload
# --------------------------------------------------------------------------- #
def test_payload_is_one_transfer_and_the_array_dominates(scene):
    m = scene.payload()
    assert m["frames"] == 2400
    assert m["arrays"][spike.ARRAY_NAME] == 1364 * 2400 * 4
    assert m["binary_bytes"] == sum(m["arrays"].values())
    assert m["total_bytes"] == m["json_bytes"] + m["binary_bytes"]
    assert m["arrays"]["Points"] == 1364 * 3 * 8
    assert m["total_bytes"] == pytest.approx(13_361_671, abs=4096)
    # the array is ~98% of the transfer: the payload is the field, not overhead
    assert m["arrays"][spike.ARRAY_NAME] / m["total_bytes"] > 0.97


# --------------------------------------------------------------------------- #
# 8. JS asset
# --------------------------------------------------------------------------- #
def test_js_asset_exists_and_is_syntactically_valid():
    js_path = REPO / "prototypes" / "local_view_spike.js"
    assert js_path.exists()
    source = js_path.read_text(encoding="utf-8")
    assert "localViewSpike" in source
    assert len(source) < 20_000          # "small .js asset"

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available for a syntax check")
    result = subprocess.run(
        [node, "--check", str(js_path)], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr


def test_js_bootstrap_is_the_asset_plus_one_call():
    cfg = {"ref": "spike_local", "nframes": 2400}
    blob = spike.js_bootstrap(cfg)
    assert "window.localViewSpike.init(" in blob
    assert blob.rstrip().endswith(");")
