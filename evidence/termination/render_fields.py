#!/usr/bin/env python3
"""Render the field dump ``build_A_50ohm_p51_ghostwave_fields.npz`` to PNG.

Convention: every complex array is plotted as its REAL PART, consistently.
``Re(Ez)`` in V/m is what the colourbars say; magnitudes appear nowhere.

Axis mapping, established from the source (not guessed):

* ``plane_ez`` is allocated ``np.zeros((n_stations, cc.nyn, cc.nz))`` at
  ``emfit/studies.py:3074`` and filled ``plane_ez[i] += phase * pl_ez[ix]`` at
  ``emfit/studies.py:3333`` from ``pl_ez = stepper.e[...].reshape(cc.nxn,
  cc.nyn, cc.nz)`` (``:3319-3320``), sliced ``pl_ez[ix]`` where ``ix`` is the
  station's index along ``x``.  So
  array index 0 = station along the line (x, the propagation direction),
  array index 1 = ``j`` (y, transverse across the strip width),
  array index 2 = ``k`` (z, the substrate normal / the gap direction).
* ``nyn = ny + 1 = 213`` and ``nzn = nz + 1 = 23``
  (``emfit/operators.py:51``, nodes = cells + 1).  ``E_z`` edges sit on the
  y-node layer and at z cell centres -- ``idx_ez`` strides ``(j % self.nyn) *
  self.nz`` with ``n_ez = nxn * nyn * nz`` (``emfit/operators.py:56, 90-92``)
  -- hence 213 in index 1 and 22 in index 2.  ``E_y`` edges are staggered the
  other way, on the z-node layer: ``idx_ey`` strides ``(k % self.nzn)`` with
  ``n_ey = nxn * ny * nzn`` (``emfit/operators.py:55, 86-88``), hence the
  ``(9, 212, 23)`` shape.  That is the half-cell (0.2 mm) Yee offset, and it
  is why the two plane families do not share a shape.

Length origin: the assumed origin is the (0, 0, 0) corner of the FDTD domain,
i.e. the first sample of each axis is at 0 mm and lengths are
``index * cell_m * 1000``.  No absolute fiducial is documented in the dump, so
this is a relative origin only.

Usage
-----
    python evidence/termination/render_fields.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = "evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz"
DEFAULT_OUTDIR = "evidence/termination/figures"
PLANE_KEY = "plane_ez"
COLORBAR_LABEL = "Re(Ez) [V/m]"


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (REPO_ROOT / p)


def _load(path: Path) -> dict:
    with np.load(path) as d:
        return {
            "plane_ez": np.asarray(d[PLANE_KEY]),
            "nstep": int(d["nstep"]),
            "nx": int(d["nx"]),
            "ny": int(d["ny"]),
            "nz": int(d["nz"]),
            "cell_m": float(d["cell_m"]),
        }


# ----------------------------------------------------------------------
# plot 1: 2-D heatmap of one station
# ----------------------------------------------------------------------
def plot_ez_slice(field: np.ndarray, station: int, n_station: int, cell_mm: float,
                  dpi: int, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n_j, n_k = field.shape
    # cell-centred extent in mm: sample j sits at j*cell, cells span +-half a cell
    x0, x1 = -0.5 * cell_mm, (n_j - 0.5) * cell_mm
    y0, y1 = -0.5 * cell_mm, (n_k - 0.5) * cell_mm
    vmax = float(np.max(np.abs(field))) or 1.0

    fig, ax = plt.subplots(figsize=(9.0, 4.2), dpi=dpi)
    im = ax.imshow(field, origin="lower", aspect="equal", cmap="RdBu_r",
                   extent=(x0, x1, y0, y1), vmin=-vmax, vmax=vmax,
                   interpolation="nearest")
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label(COLORBAR_LABEL)
    ax.set_xlabel("y / strip width [mm]  (array index 1, j: y-node layer, "
                  f"{n_j} samples)")
    ax.set_ylabel(f"z / substrate normal [mm]  (array index 2, k: {n_k} cells)")
    ax.set_title(f"Re(Ez) on the station plane, station {station} of "
                 f"{n_station} (array index 0 = x, the propagation direction)",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(out, dpi=dpi)
    plt.close(fig)


# ----------------------------------------------------------------------
# plot 2: 3-D render (pyvista primary, matplotlib 3-D fallback)
# ----------------------------------------------------------------------
def _plane_points(field: np.ndarray, station: int, cell_mm: float):
    n_j, n_k = field.shape
    x_mm = station * cell_mm
    y_mm = np.arange(n_j) * cell_mm
    z_mm = np.arange(n_k) * cell_mm
    Y, Z = np.meshgrid(y_mm, z_mm)  # (n_k, n_j), row-major over j
    pts = np.column_stack([np.full(Y.size, x_mm), Y.ravel(), Z.ravel()])
    return pts, field.ravel(), (n_k, n_j), x_mm, y_mm, z_mm


def plot_ez_3d_pyvista(field: np.ndarray, station: int, cell_mm: float, dpi: int,
                       out: Path, dims) -> None:
    import pyvista as pv

    pv.OFF_SCREEN = True  # before any plotting
    try:
        pv.start_xvfb()
    except Exception as exc:  # xvfb not installed: fine off-screen
        print(f"[render_fields] start_xvfb unavailable ({type(exc).__name__}: {exc}); "
              "continuing off-screen", file=sys.stderr)

    nx, ny, nz = dims
    pts, vals, (n_k, n_j), x_mm, y_mm, z_mm = _plane_points(field, station, cell_mm)
    grid = pv.StructuredGrid()
    grid.points = pts
    grid.dimensions = (n_k, n_j, 1)
    grid[COLORBAR_LABEL] = vals

    p = pv.Plotter(off_screen=True, window_size=(1400, 900))
    p.add_mesh(grid, cmap="RdBu_r", show_edges=False, scalar_bar_args={
        "title": COLORBAR_LABEL, "vertical": True})
    box = (0.0, nx * cell_mm, 0.0, ny * cell_mm, 0.0, nz * cell_mm)
    p.add_mesh(pv.Box(bounds=box), style="wireframe", color="black",
               line_width=1.0, opacity=0.5)
    p.show_bounds(xlabel="x [mm]", ylabel="y [mm]", zlabel="z [mm]",
                  grid="back", location="outer", font_size=9)
    p.add_axes(xlabel="x [mm]", ylabel="y [mm]", zlabel="z [mm]")
    p.camera_position = "xz"
    p.view_isometric()
    p.camera.zoom(0.85)
    p.screenshot(str(out), scale=1)
    p.close()


def plot_ez_3d_matplotlib(field: np.ndarray, station: int, cell_mm: float, dpi: int,
                          out: Path, dims, note: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import cm, colors

    nx, ny, nz = dims
    y_mm = np.arange(field.shape[0]) * cell_mm
    z_mm = np.arange(field.shape[1]) * cell_mm
    Y, Z = np.meshgrid(y_mm, z_mm)
    X = np.full_like(Y, station * cell_mm)
    vmax = float(np.max(np.abs(field))) or 1.0
    norm = colors.Normalize(vmin=-vmax, vmax=vmax)

    fig = plt.figure(figsize=(10.0, 6.5), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(X, Y, Z, facecolors=cm.RdBu_r(norm(field.T)),
                    rstride=1, cstride=1, shade=False, linewidth=0)
    # wireframe box of the simulation domain for scale
    bx, by, bz = nx * cell_mm, ny * cell_mm, nz * cell_mm
    for xx in (0.0, bx):
        for yy in (0.0, by):
            ax.plot([xx, xx], [yy, yy], [0, bz], color="0.35", lw=0.6)
        for zz in (0.0, bz):
            ax.plot([xx, xx], [0, by], [zz, zz], color="0.35", lw=0.6)
    for yy in (0.0, by):
        for zz in (0.0, bz):
            ax.plot([0, bx], [yy, yy], [zz, zz], color="0.35", lw=0.6)
    ax.set_xlabel("x [mm] (propagation)", fontsize=8)
    ax.set_ylabel("y / strip width [mm] (array index 1)", fontsize=8)
    ax.set_zlabel("z / normal [mm] (array index 2)", fontsize=8)
    ax.view_init(elev=22, azim=-62)
    ax.set_title(f"Re(Ez) station plane {station} + domain box {bx:.1f} x "
                 f"{by:.1f} x {bz:.1f} mm", fontsize=10)
    sm = cm.ScalarMappable(norm=norm, cmap="RdBu_r")
    cb = fig.colorbar(sm, ax=ax, pad=0.08, shrink=0.7)
    cb.set_label(COLORBAR_LABEL)
    if note:
        fig.text(0.01, 0.005, note, fontsize=6.5, color="0.4")
    fig.tight_layout()
    fig.savefig(out, dpi=dpi)
    plt.close(fig)


# ----------------------------------------------------------------------
# plot 3: standing-wave envelope over the nine stations
# ----------------------------------------------------------------------
def plot_envelope(plane: np.ndarray, out: Path, dpi: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    env = np.max(np.abs(plane), axis=(1, 2))  # max |Ez| per station
    idx = np.arange(env.size)
    fig, ax = plt.subplots(figsize=(7.0, 4.0), dpi=dpi)
    ax.plot(idx, env, "-o", color="C0", lw=1.4, ms=6)
    ax.set_xlabel("station index (array index 0 = x, the propagation direction)")
    ax.set_ylabel("max |Ez| over the plane [V/m]")
    ax.set_title("Standing-wave envelope of |Ez| across the nine station planes",
                 fontsize=10)
    ax.grid(True, alpha=0.3)
    for x, v in zip(idx, env):
        ax.annotate(f"{v:.0f}", (x, v), textcoords="offset points",
                    xytext=(0, 7), ha="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(out, dpi=dpi)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=DEFAULT_INPUT,
                    help=f"field dump npz, relative to the repo root (default: {DEFAULT_INPUT})")
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR,
                    help=f"output directory, relative to the repo root (default: {DEFAULT_OUTDIR})")
    ap.add_argument("--station", type=int, default=4,
                    help="station plane index into axis 0 (default: 4, the middle of 9)")
    ap.add_argument("--dpi", type=int, default=150, help="raster resolution (default: 150)")
    ap.add_argument("--backend", default="auto", choices=("auto", "pyvista", "matplotlib"),
                    help="3-D renderer for plot 2 (default: auto = pyvista if importable)")
    args = ap.parse_args(argv)

    src = _resolve(args.input)
    outdir = _resolve(args.outdir)
    if not src.is_file():
        print(f"[render_fields] input not found: {src}", file=sys.stderr)
        return 2
    outdir.mkdir(parents=True, exist_ok=True)

    d = _load(src)
    plane = d["plane_ez"]
    cell_mm = d["cell_m"] * 1e3
    n_station = plane.shape[0]
    if not 0 <= args.station < n_station:
        print(f"[render_fields] --station {args.station} outside 0..{n_station - 1}",
              file=sys.stderr)
        return 2

    # REAL PART everywhere, consistently.
    field = plane[args.station].real.astype(float)
    dims = (d["nx"], d["ny"], d["nz"])

    print(f"[render_fields] {src}")
    print(f"[render_fields] cell_m = {d['cell_m']} m ({cell_mm} mm/cell), "
          f"nstep = {d['nstep']}, domain {dims[0]}x{dims[1]}x{dims[2]} cells = "
          f"{dims[0] * cell_mm:.1f} x {dims[1] * cell_mm:.1f} x "
          f"{dims[2] * cell_mm:.1f} mm")
    print(f"[render_fields] plane_ez {plane.shape}; station {args.station}; "
          f"plotting Re(Ez) (not magnitude)")

    p1 = outdir / f"ez_slice_station{args.station}.png"
    plot_ez_slice(field, args.station, n_station, cell_mm, args.dpi, p1)

    backend = args.backend
    if backend == "auto":
        try:
            import pyvista  # noqa: F401
            backend = "pyvista"
        except Exception:
            backend = "matplotlib"
    p2 = outdir / f"ez_3d_station{args.station}.png"
    note = ""
    if backend == "pyvista":
        try:
            plot_ez_3d_pyvista(field, args.station, cell_mm, args.dpi, p2, dims)
        except Exception as exc:
            note = f"matplotlib fallback: pyvista raised {type(exc).__name__}: {exc}"
            print(f"[render_fields] {note}", file=sys.stderr)
            plot_ez_3d_matplotlib(field, args.station, cell_mm, args.dpi, p2, dims, note)
    else:
        note = ("rendered with the matplotlib 3-D fallback: pyvista/vtk is not "
                "importable in this environment")
        print(f"[render_fields] {note}", file=sys.stderr)
        plot_ez_3d_matplotlib(field, args.station, cell_mm, args.dpi, p2, dims, note)

    p3 = outdir / "ez_envelope.png"
    plot_envelope(plane, p3, args.dpi)

    print("[render_fields] outputs (absolute path, bytes):")
    rc = 0
    for out in (p1, p2, p3):
        if out.is_file():
            print(f"  {out.resolve()}  {out.stat().st_size}")
        else:
            print(f"  {out.resolve()}  MISSING")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
