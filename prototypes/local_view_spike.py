"""Local-view (client-side) animation spike for a 2400-frame volume.

Question this prototype answers
------------------------------
Can the 2400-frame y-cut field animation be driven entirely in the browser from
a *single* payload, i.e. without the server pushing a new image or a new scene
on every frame?

Mechanism used
--------------
``VtkLocalView`` ships the *geometry* once; the client renders with vtk.js.  The
scene JSON carries no bulk arrays (arrays are transferred by hash over a binary
RPC), so the whole time series is packed into ONE point-data array with 2400
components -- component ``k`` is frame ``k`` -- on ONE 62x22 plane, and pushed
exactly once.  ``prototypes/local_view_spike.js`` then does the per-frame work:
pick component ``k`` out of the already-uploaded buffer, hand that column to the
vtk.js array as a 1-component array, re-render.  Colour mapping is fixed once on
the server (256-entry ``vtkLookupTable`` + global symmetric clim) and serialised
once, so client and server agree on the colormap.

What is NOT claimed here: nothing in this file proves anything about a browser,
GPU, frame rate or pixel parity with a server-side rendering.  The measurable
claims are wire bytes, scene shape, label text and the absence of a per-frame
server round-trip.

Run headless (no HTTP server, no render window shown)::

    PYTHONPATH=.:.venv/lib/python3.12/site-packages python3 \
        prototypes/local_view_spike.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
JS_PATH = HERE / "local_view_spike.js"
DEFAULT_NPZ = Path("artifacts/volume_s59.npz")

#: name of the single packed point-data array (frame k == component k)
ARRAY_NAME = "ez_all"
#: trame view name used in the scene state key ``scene_<VIEW_NAME>``
VIEW_NAME = "spike_local"
#: Vue ref the JS reaches through ``window.trame.refs[...]``
JS_REF = "spike_local"

LUT_SIZE = 256
CLIM_PERCENTILE = 99.5
DEFAULT_FPS = 24.0

#: the only arrays this prototype is allowed to read out of the npz
REQUIRED_KEYS = ("ez_ycut", "frame_index", "nsteps", "x_mm", "y_mm", "z_mm")
#: never read: ~GB-scale field cube, irrelevant here
FORBIDDEN_KEYS = ("e_abs_volume",)

#: every npz key actually read, in order (checked by the tests)
LOADED_KEYS: list[str] = []

#: symmetric clim is global (one value for the whole time series) and memoised
_CLIM_CACHE: dict[tuple, tuple[float, float]] = {}
CLIM_CALLS = 0


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_volume(path: str | Path = DEFAULT_NPZ) -> dict[str, np.ndarray]:
    """Read only :data:`REQUIRED_KEYS` from ``path``, recording what was read."""
    path = Path(path)
    out: dict[str, np.ndarray] = {}
    with np.load(path, allow_pickle=False) as npz:
        available = set(npz.files)
        missing = [k for k in REQUIRED_KEYS if k not in available]
        if missing:
            raise KeyError(f"{path}: missing required array(s) {missing}")
        for key in REQUIRED_KEYS:
            if key in FORBIDDEN_KEYS:  # defensive, cannot happen by construction
                raise RuntimeError(f"refusing to load {key!r}")
            out[key] = np.asarray(npz[key])
            LOADED_KEYS.append(key)
    return out


def frame_indices(volume: dict[str, np.ndarray]) -> np.ndarray:
    """The frame's own step numbers, as int64 (shape ``(nframes,)``)."""
    return np.asarray(volume["frame_index"]).astype(np.int64).ravel()


def stride_of(fi: np.ndarray) -> int:
    """Constant spacing between consecutive frame numbers (1 here)."""
    fi = np.asarray(fi)
    if fi.size < 2:
        return 1
    diffs = np.diff(fi)
    if not np.all(diffs == diffs[0]):
        raise ValueError("frame_index is not uniformly spaced; stride is meaningless")
    return int(diffs[0])


def label_for_frame(fi: np.ndarray, k: int, stride: int) -> str:
    """Overlay text for frame ``k``.

    The denominator is the *largest frame number* (``frame_index.max()``), never
    ``nsteps - 1``: with 2400 steps numbered 1..2400 the last frame must read
    "Step 2400 / 2400", not "Step 2400 / 2399".
    """
    fi = np.asarray(fi)
    k = int(k)
    if not 0 <= k < fi.size:
        raise IndexError(f"frame {k} outside 0..{fi.size - 1}")
    return f"Step {int(fi[k])} / {int(fi.max())} (Stride {int(stride)})"


def compute_clim(ez: np.ndarray, percentile: float = CLIM_PERCENTILE) -> tuple[float, float]:
    """Symmetric colour limits from the whole time series, memoised.

    The limits must not move while the animation plays, so they are computed
    once over *all* frames and reused by both the server-side LUT and the
    injected JS bootstrap.
    """
    global CLIM_CALLS
    ez = np.asarray(ez)
    key = (ez.shape, float(percentile))
    cached = _CLIM_CACHE.get(key)
    if cached is not None:
        return cached
    CLIM_CALLS += 1
    amplitude = np.abs(ez.astype(np.float32, copy=False))
    high = float(np.percentile(amplitude.astype(np.float64), percentile))
    clim = (-high, high)
    _CLIM_CACHE[key] = clim
    return clim


# --------------------------------------------------------------------------- #
# scene
# --------------------------------------------------------------------------- #
class SpikeScene:
    """One polydata plane + one packed array + a fixed colour map."""

    def __init__(self, volume: dict[str, np.ndarray], clim=None):
        import vtk
        from vtk.util import numpy_support

        self.volume = volume
        self.ez = np.asarray(volume["ez_ycut"], dtype=np.float32)
        self.nframes, self.n_a, self.n_b = self.ez.shape
        self.npts = self.n_a * self.n_b
        self.clim = tuple(clim) if clim is not None else compute_clim(self.ez)

        # (npts, nframes): frame k == component k, one contiguous block per frame
        self.components = np.ascontiguousarray(self.ez.reshape(self.nframes, self.npts).T)

        x_mm = np.asarray(volume["x_mm"], dtype=np.float64).ravel()
        z_mm = np.asarray(volume["z_mm"], dtype=np.float64).ravel()
        if x_mm.size != self.n_a or z_mm.size != self.n_b:
            raise ValueError(
                f"coordinate/array mismatch: x {x_mm.size} vs {self.n_a}, "
                f"z {z_mm.size} vs {self.n_b}"
            )
        self.x_mm, self.z_mm = x_mm, z_mm

        grid_x, grid_z = np.meshgrid(x_mm, z_mm, indexing="ij")
        points = np.column_stack(
            [grid_x.ravel(), np.zeros(self.npts), grid_z.ravel()]
        ).astype(np.float64)

        vtk_points = vtk.vtkPoints()
        vtk_points.SetData(numpy_support.numpy_to_vtk(points, deep=True))

        polys = vtk.vtkCellArray()
        for a in range(self.n_a - 1):
            for b in range(self.n_b - 1):
                i00 = a * self.n_b + b
                i01 = i00 + 1
                i10 = (a + 1) * self.n_b + b
                i11 = i10 + 1
                for tri in ((i00, i01, i11), (i00, i11, i10)):
                    polys.InsertNextCell(3)
                    for idx in tri:
                        polys.InsertCellPoint(int(idx))

        polydata = vtk.vtkPolyData()
        polydata.SetPoints(vtk_points)
        polydata.SetPolys(polys)

        packed = numpy_support.numpy_to_vtk(
            self.components, deep=True, array_type=vtk.VTK_FLOAT
        )
        packed.SetName(ARRAY_NAME)
        polydata.GetPointData().SetScalars(packed)

        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(LUT_SIZE)
        lut.SetTableRange(*self.clim)
        lut.Build()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)
        mapper.SetScalarVisibility(True)
        mapper.SetScalarModeToUsePointData()
        mapper.SetColorModeToMapScalars()
        mapper.SetLookupTable(lut)
        mapper.SetUseLookupTableScalarRange(True)
        mapper.SetScalarRange(*self.clim)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)

        renderer = vtk.vtkRenderer()
        renderer.AddActor(actor)
        renderer.SetBackground(0.1, 0.1, 0.12)

        render_window = vtk.vtkRenderWindow()
        render_window.SetOffScreenRendering(1)
        render_window.AddRenderer(renderer)

        self.polydata = polydata
        self.array = packed
        self.lut = lut
        self.mapper = mapper
        self.actor = actor
        self.renderer = renderer
        self.render_window = render_window
        self._setup_camera()

    # -- camera: fixed, deterministic, no auto-reset per frame --------------
    def _setup_camera(self) -> None:
        camera = self.renderer.GetActiveCamera()
        centre_x = float(self.x_mm.mean())
        centre_z = float(self.z_mm.mean())
        height = float(self.z_mm.max() - self.z_mm.min())
        width = float(self.x_mm.max() - self.x_mm.min())
        camera.SetFocalPoint(centre_x, 0.0, centre_z)
        camera.SetPosition(centre_x, -150.0, centre_z)
        camera.SetViewUp(0.0, 0.0, 1.0)
        camera.ParallelProjectionOn()
        camera.SetParallelScale(max(height, width / 1.7) / 2.0)
        self.renderer.ResetCameraClippingRange()

    # -- measured wire payload ---------------------------------------------
    def payload(self) -> dict:
        """Bytes the client would receive for this scene (JSON + binary arrays)."""
        from trame_vtk.modules.vtk.serializers.initialize import initialize_serializers
        from trame_vtk.modules.vtk.serializers.render_windows import (
            render_window_serializer,
        )
        from trame_vtk.modules.vtk.serializers.synchronization_context import (
            SynchronizationContext,
        )

        initialize_serializers()
        context = SynchronizationContext()
        state = render_window_serializer(None, self.render_window, "rw", context, 0)
        scene_json = json.dumps(state)
        arrays: dict[str, int] = {}
        for handle, record in list(context.data_array_cache.items()):
            vtk_array = record["array"]
            name = vtk_array.GetName() or "(unnamed)"
            arrays[name] = len(context.get_cached_data_array(handle, binary=True))
        binary_bytes = sum(arrays.values())
        return {
            "json_bytes": len(scene_json),
            "binary_bytes": binary_bytes,
            "total_bytes": len(scene_json) + binary_bytes,
            "arrays": arrays,
            "frames": int(self.nframes),
        }


# --------------------------------------------------------------------------- #
# app
# --------------------------------------------------------------------------- #
def bootstrap_cfg(
    volume: dict[str, np.ndarray], scene: SpikeScene, fps: float = DEFAULT_FPS
) -> dict:
    """The JSON the injected JS receives: no bulk data, only bookkeeping."""
    fi = frame_indices(volume)
    return {
        "ref": JS_REF,
        "arrayName": ARRAY_NAME,
        "nframes": int(scene.nframes),
        "frameIndex": [int(v) for v in fi],
        "stepTotal": int(fi.max()),
        "stride": stride_of(fi),
        "clim": [float(scene.clim[0]), float(scene.clim[1])],
        "fps": float(fps),
        "autoplay": True,
    }


def js_bootstrap(cfg: dict, js_path: str | Path = JS_PATH) -> str:
    """The JS asset plus one call line, ready for an inline ``Script`` widget."""
    source = Path(js_path).read_text(encoding="utf-8")
    call = "window.localViewSpike.init(" + json.dumps(cfg) + ");"
    return source + "\n\n" + call + "\n"


class SpikeApp:
    """Everything ``build_app`` produced, so tests need no trame state spelunking."""

    def __init__(self, server, scene, view, cfg, script, script_widget):
        self.server = server
        self.scene = scene
        self.view = view
        self.cfg = cfg
        self.script = script
        self.script_widget = script_widget

    def __iter__(self):
        return iter((self.server, self.scene, self.view))


def build_app(
    volume: dict[str, np.ndarray] | None = None,
    npz: str | Path = DEFAULT_NPZ,
    js_path: str | Path = JS_PATH,
    fps: float = DEFAULT_FPS,
):
    """Build the trame app headless; returns ``(server, scene, view)``.

    Nothing is started here: ``VtkLocalView.update()`` returns early while no
    client is connected, so this can be exercised from a test process.
    """
    from trame.app import get_server
    from trame.ui.vuetify3 import SinglePageLayout
    from trame_client.widgets.client import Script
    from trame_vtk.widgets.vtk import VtkLocalView

    if volume is None:
        volume = load_volume(npz)
    scene = SpikeScene(volume)
    cfg = bootstrap_cfg(volume, scene, fps=fps)

    server = get_server("local_view_spike")
    script = js_bootstrap(cfg, js_path)

    with SinglePageLayout(server) as layout:
        layout.title.set_text("2400-frame y-cut — local view spike")
        with layout.content:
            # the *render window* is handed over (never rendered on the server);
            # ref= gives the client-side component the name the JS looks up in
            # window.trame.refs, and it also names the state key scene_<ref>.
            view = VtkLocalView(scene.render_window, ref=JS_REF)
            script_widget = Script(script)

    view.update()
    return SpikeApp(server, scene, view, cfg, script, script_widget)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build everything headless, print measurements, do not serve",
    )
    parser.add_argument("--npz", default=str(DEFAULT_NPZ))
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    args = parser.parse_args(argv)

    volume = load_volume(args.npz)
    scene = SpikeScene(volume)
    fi = frame_indices(volume)
    stride = stride_of(fi)
    payload = scene.payload()
    summary = {
        "loaded_keys": list(LOADED_KEYS),
        "frames": int(scene.nframes),
        "points": int(scene.npts),
        "polys": int(scene.polydata.GetNumberOfPolys()),
        "array": f"{ARRAY_NAME} {scene.array.GetNumberOfTuples()}x"
        f"{scene.array.GetNumberOfComponents()}",
        "clim": list(scene.clim),
        "lut_range": list(scene.lut.GetTableRange()),
        "labels": {
            "0": label_for_frame(fi, 0, stride),
            "1": label_for_frame(fi, 1, stride),
            "last": label_for_frame(fi, int(fi.size) - 1, stride),
        },
        "payload": payload,
        "streamed_update": False,
    }
    print(json.dumps(summary, indent=2))
    if args.dry_run:
        return 0
    app = build_app(volume=volume, fps=args.fps)
    app.server.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
