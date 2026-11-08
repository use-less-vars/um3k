#!/usr/bin/env python3
"""PoC web viewer for the Build A npz field dump (Trame + pyvista).

Reads evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz and serves an
interactive 3D view of the Ez field in a browser.

Run:
    python3 server/poc_app.py

Then open http://localhost:8080 in a browser.

Minimum packages: pyvista and trame (with a working VTK build). Nothing beyond
numpy is needed for the --list-keys / --help path.

IMPORTANT - what this viewer actually shows:
    The npz stores 9 CAPTURED x-planes, stacked one cell spacing apart. This is
    NOT a dense volumetric solve. The x axis is quantised to exactly 9 station
    positions, so the volume is those 9 slices resampled onto a 9 x 213 x 22
    grid. Nothing between the stations exists in the input and nothing is
    invented here.

STATUS: the web path (trame server, layout, slider callback) is UNTESTED. Only
    the numpy / CLI path (--help, --list-keys) has been exercised. Treat any
    browser-side behaviour as unverified.
"""

from __future__ import annotations

import argparse
import errno
import sys
from pathlib import Path

import numpy as np

# server/ sits ONE level below the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT = "evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz"
PLANE_KEY = "plane_ez"
DEFAULT_HOST = "127.0.0.1"
# Deliberately 8080, NOT 8000: 8000 is reserved for the agent's own service on
# the operator's machine.
DEFAULT_PORT = 8080


def _resolve(path_str: str) -> Path:
    """Absolute paths pass through, relative ones are taken from the repo root."""
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def load_dump(path: Path) -> dict:
    """Load the npz metadata plus the Ez plane. Exits with 2 on bad input."""
    if not path.is_file():
        print(f"[poc_app] input not found: {path}", file=sys.stderr)
        raise SystemExit(2)

    with np.load(path) as data:
        plane = np.asarray(data[PLANE_KEY])
        info = {
            "path": path,
            PLANE_KEY: plane,
            "nstep": int(data["nstep"]),
            "nx": int(data["nx"]),
            "ny": int(data["ny"]),
            "nz": int(data["nz"]),
            "cell_m": float(data["cell_m"]),
        }

    if plane.ndim != 3:
        print(
            f"[poc_app] {PLANE_KEY} has shape {plane.shape}, expected a 3D array "
            f"(station, y, z).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return info


def _cell_mm(info: dict) -> float:
    return float(info["cell_m"]) * 1e3


def _station_text(idx: int, cell_mm: float, n_st: int) -> str:
    return f"station {idx + 1}/{n_st}   x = {idx * cell_mm:.4f} mm"


def print_keys(info: dict) -> None:
    """Print dump metadata. numpy only - no pyvista, no trame."""
    plane = info[PLANE_KEY]
    cell_mm = _cell_mm(info)
    n_st, n_j, n_k = plane.shape

    print(f"file        : {info['path']}")
    print(f"plane       : {PLANE_KEY} shape={plane.shape} dtype={plane.dtype}")
    print(f"nstep       : {info['nstep']}")
    print(f"nx/ny/nz    : {info['nx']} / {info['ny']} / {info['nz']} (cells)")
    print(f"cell_m      : {info['cell_m']:.6e} m  ({cell_mm:.6f} mm)")
    # The npz counts CELLS, not nodes: axis 1 carries ny + 1 node samples.
    print(
        f"extent      : {n_st * cell_mm:.4f} x {n_j * cell_mm:.4f} x "
        f"{n_k * cell_mm:.4f} mm"
    )
    print(f"samples     : {n_st} x {n_j} x {n_k}")

    xs_mm = [i * cell_mm for i in range(n_st)]
    print("station x/mm: " + ", ".join(f"{x:.4f}" for x in xs_mm))

    ez_real = np.real(plane)
    ez_abs = np.abs(plane)
    print(f"Re(Ez)      : min={ez_real.min():.6e}  max={ez_real.max():.6e}")
    print(f"|Ez|        : min={ez_abs.min():.6e}  max={ez_abs.max():.6e}")

    print("|Ez| max/station:")
    for i in range(n_st):
        print(f"  station {i} (x={xs_mm[i]:.4f} mm): {ez_abs[i].max():.6e}")

    peak = np.unravel_index(int(np.argmax(ez_abs)), ez_abs.shape)
    print(
        f"global |Ez| peak at station {peak[0]} (x={xs_mm[peak[0]]:.4f} mm), "
        f"sample (y={peak[1]}, z={peak[2]})"
    )


def build_grid(info: dict) -> "pyvista.ImageData":
    # Deferred import: keeps --help / --list-keys runnable with numpy alone.
    import pyvista as pv

    plane = info[PLANE_KEY]
    n_st, n_j, n_k = plane.shape
    dims = (n_st, n_j, n_k)
    cell_mm = _cell_mm(info)

    image = pv.ImageData()
    image.dimensions = dims
    image.spacing = (cell_mm, cell_mm, cell_mm)
    image.origin = (0.0, 0.0, 0.0)

    ez_real = np.real(plane).astype(float)
    ez_abs = np.abs(plane).astype(float)
    if ez_real.shape != dims or ez_abs.shape != dims:
        print(
            f"[poc_app] grid arrays have shapes {ez_real.shape} / {ez_abs.shape}, "
            f"expected {dims}.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # VTK expects x to vary fastest, so ravel in Fortran order.
    image.point_data["ez_real"] = np.ascontiguousarray(
        ez_real.ravel(order="F"), dtype=float
    )
    image.point_data["ez_abs"] = np.ascontiguousarray(
        ez_abs.ravel(order="F"), dtype=float
    )
    return image


def create_plotter(info: dict):
    # Deferred import: pyvista is only needed once we actually render.
    import pyvista as pv

    grid = build_grid(info)
    n_st = info[PLANE_KEY].shape[0]
    cell_mm = _cell_mm(info)

    # Off-screen rendering: the server host needs no display.
    plotter = pv.Plotter(off_screen=True)
    plotter.set_background("white")
    plotter.add_volume(
        grid,
        scalars="ez_abs",
        cmap="turbo",
        scalar_bar_args={"title": "|Ez| [V/m]"},
    )
    plotter.add_mesh(grid.outline(), color="black", line_width=1)
    plotter.add_axes(xlabel="x [mm]", ylabel="y [mm]", zlabel="z [mm]")
    plotter.add_text(
        _station_text(0, cell_mm, n_st),
        name="station_label",
        position="upper_left",
        font_size=10,
        color="black",
    )
    plotter.view_isometric()
    try:
        plotter.camera.zoom(0.85)
    except Exception as exc:  # camera API not exercised here
        print(f"[poc_app] camera zoom skipped: {exc}", file=sys.stderr)
    return plotter


def run_web(info: dict, host: str, port: int, station: int) -> int:
    import importlib

    from trame.app import get_server

    try:
        import trame

        trame_version = getattr(trame, "__version__", "UNKNOWN")
    except Exception:
        trame_version = "UNKNOWN"

    # Probe chain, newest first. Every candidate is guarded in its own
    # try/except: the old code guarded only the FIRST import, so a missing or
    # broken vuetify2 fallback raised straight out of this function. No
    # candidate may escape the loop here.
    ui_module = None
    widgets_module = None
    SinglePageLayout = None
    vuetify_variant = None
    vuetify_ui_path = None
    for label, ui_path, widgets_path in (
        ("vuetify3", "trame.ui.vuetify3", "trame.widgets.vuetify3"),
        ("vuetify2", "trame.ui.vuetify2", "trame.widgets.vuetify2"),
        ("vuetify", "trame.ui.vuetify", "trame.widgets.vuetify"),
    ):
        try:
            candidate_ui = importlib.import_module(ui_path)
            candidate_widgets = importlib.import_module(widgets_path)
            candidate_layout = getattr(candidate_ui, "SinglePageLayout")
        except Exception as exc:  # noqa: BLE001 - deliberate, see comment above
            print(f"[poc_app] probe {label} unusable: {exc}", file=sys.stderr)
            continue
        ui_module = candidate_ui
        widgets_module = candidate_widgets
        SinglePageLayout = candidate_layout
        vuetify_variant = label
        vuetify_ui_path = ui_path
        break

    if SinglePageLayout is None:
        print(
            "[poc_app] trame is installed but no Vuetify UI module was found.",
            file=sys.stderr,
        )
        print(f"[poc_app] trame version: {trame_version}", file=sys.stderr)
        print(
            "[poc_app] modules tried: trame.ui.vuetify3, trame.ui.vuetify2, "
            "trame.ui.vuetify",
            file=sys.stderr,
        )
        print(
            "[poc_app] fix: python3 -m pip install trame-vuetify", file=sys.stderr
        )
        print(
            "[poc_app] then re-run: python3 server/poc_app.py --station 4",
            file=sys.stderr,
        )
        return 1

    print(f"[poc_app] trame {trame_version} - ui modules: {vuetify_ui_path}")

    # Resolve the widget classes this layout needs instead of hardcoding them,
    # so a variant that lacks one degrades to a placeholder instead of a
    # traceback. The slider is a convenience, not a requirement.
    widgets = {}
    missing_widgets = []
    for name in ("VSpacer", "VSlider", "VLabel", "VContainer"):
        try:
            widgets[name] = getattr(widgets_module, name)
        except Exception:
            missing_widgets.append(name)

    placeholder = None
    if missing_widgets:
        for name in missing_widgets:
            print(
                f"[poc_app] widget {name} missing from {vuetify_variant}",
                file=sys.stderr,
            )
        try:
            from trame.widgets.html import Div

            placeholder = Div
        except Exception:
            placeholder = None
            print(
                "[poc_app] trame.widgets.html unavailable - no toolbar, "
                "plotter view only",
                file=sys.stderr,
            )

    from pyvista.trame.ui import plotter_ui

    plane = info[PLANE_KEY]
    n_st = plane.shape[0]
    cell_mm = _cell_mm(info)
    plotter = create_plotter(info)

    try:
        server = get_server(
            client_type="vue3" if vuetify_variant == "vuetify3" else "vue2"
        )
    except TypeError:
        # Older trame builds do not accept client_type.
        server = get_server()

    state, ctrl = server.state, server.controller
    state.trame__title = "Build A |Ez| PoC"
    state.station = int(station)
    state.station_label = _station_text(int(station), cell_mm, n_st)

    def _focus(idx: int) -> None:
        try:
            bounds = plotter.bounds
            y_mid = 0.5 * (bounds[2] + bounds[3])
            z_mid = 0.5 * (bounds[4] + bounds[5])
            span = max(
                bounds[1] - bounds[0],
                bounds[3] - bounds[2],
                bounds[5] - bounds[4],
                1.0,
            )
            # Look down +x: the station axis is the thin one, so keep y/z centred.
            plotter.camera_position = [
                (bounds[1] + 2.0 * span, y_mid, z_mid),
                (bounds[0], y_mid, z_mid),
                (0.0, 0.0, 1.0),
            ]
            plotter.reset_camera_clipping_range()
            plotter.add_text(
                _station_text(idx, cell_mm, n_st),
                name="station_label",
                position="upper_left",
                font_size=10,
                color="black",
            )
            plotter.render()
        except Exception as exc:
            print(f"[poc_app] station focus skipped: {exc}", file=sys.stderr)

    with SinglePageLayout(server) as layout:
        layout.title.set_text("Build A - |Ez| (9 captured x-planes)")
        if not missing_widgets:
            with layout.toolbar:
                widgets["VSpacer"]()
                widgets["VSlider"](
                    v_model=("station", station),
                    min=0,
                    max=n_st - 1,
                    step=1,
                    thumb_label=True,
                    hide_details=True,
                    style="max-width: 420px; margin-right: 16px;",
                )
                widgets["VLabel"]("{{ station_label }}")
        elif placeholder is not None:
            # No usable slider: keep a plain toolbar that still shows the label.
            with layout.toolbar:
                placeholder("{{ station_label }}")
        with layout.content:
            container = widgets.get("VContainer")
            if container is None:
                if placeholder is not None:
                    with placeholder():
                        view = plotter_ui(plotter)
                else:
                    view = plotter_ui(plotter)
            else:
                with container(fluid=True, classes="pa-0 fill-height"):
                    view = plotter_ui(plotter)

    @ctrl.set("station")
    def _on_station_change(*args, **_kwargs):
        value = args[0] if args else _kwargs.get("station", state.station)
        try:
            idx = int(round(float(value)))
        except (TypeError, ValueError):
            idx = int(state.station)
        idx = max(0, min(n_st - 1, idx))
        state.station = idx
        state.station_label = _station_text(idx, cell_mm, n_st)
        _focus(idx)
        try:
            view.update()
        except Exception as exc:
            print(f"[poc_app] view update skipped: {exc}", file=sys.stderr)

    print(f"[poc_app] serving on http://{host}:{port}")
    print("[poc_app] open that URL in a browser; Ctrl-C to stop")
    try:
        server.start(host=host, port=port, open_browser=False)
    except OSError as exc:
        in_use = getattr(exc, "errno", None) == errno.EADDRINUSE or (
            "Address already in use" in str(exc)
        )
        if not in_use:
            raise
        print(f"[poc_app] port {port} is already in use.", file=sys.stderr)
        print(
            f"[poc_app] something else is listening on {host}:{port}.",
            file=sys.stderr,
        )
        print(
            f"[poc_app] fix: python3 server/poc_app.py --port {port + 1}",
            file=sys.stderr,
        )
        return 1
    return 0


def _import_guard() -> int:
    try:
        import pyvista  # noqa: F401
        import trame  # noqa: F401
    except ImportError as exc:
        print(f"[poc_app] missing dependency: {exc}", file=sys.stderr)
        print(
            "           install with: python3 -m pip install pyvista trame",
            file=sys.stderr,
        )
        print(
            "           full diagnosis: sh evidence/termination/check_pyvista.sh",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="poc_app.py",
        description=(
            "PoC Trame + pyvista web viewer for the Build A npz field dump. The "
            "9 captured x-planes are stacked at one cell spacing - this is not a "
            "dense volumetric solve, so x is quantised to 9 positions."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python3 server/poc_app.py --list-keys\n"
            "  python3 server/poc_app.py --host 0.0.0.0 --port 8080 --station 4\n"
        ),
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"npz dump to read (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--host", default=DEFAULT_HOST, help=f"bind address (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--list-keys",
        action="store_true",
        dest="list_keys",
        help="print dump metadata and exit (numpy only, no pyvista)",
    )
    parser.add_argument(
        "--station", type=int, default=4, help="initial station index (default: 4)"
    )
    args = parser.parse_args(argv)

    src = _resolve(args.input)
    info = load_dump(src)

    n_st = info[PLANE_KEY].shape[0]
    station = args.station
    if station < 0 or station > n_st - 1:
        clamped = max(0, min(n_st - 1, station))
        print(
            f"[poc_app] --station {station} out of range 0..{n_st - 1}, "
            f"using {clamped}",
            file=sys.stderr,
        )
        station = clamped

    if args.list_keys:
        print_keys(info)
        return 0

    rc = _import_guard()
    if rc:
        return rc
    return run_web(info, args.host, args.port, station)


if __name__ == "__main__":
    sys.exit(main())
