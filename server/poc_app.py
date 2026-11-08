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

Two layers sit on top of that volume, and the comments beside each say why they
are built the way they are:

    * a toolbar toggle switches the ONE 3D view between the |Ez| volume and the
      port-plane cross-section (the captured station nearest the port plane);
    * three markers place the numbers in space: the load plane in red, the S11
      port plane and the S21 extraction plane as labelled points. Their x comes
      from the study record written beside the npz, never from typed-in
      literals; the extraction plane's validity is shown on its own marker,
      because a plane past the load reads a collapsed field and that has to be
      visible rather than inferred.

Two more layers were added after those, and the comments beside each say the
same thing they said above: nothing between recorded samples is invented.

    * two cut sliders pick ONE y sample and ONE z sample and draw the sheet
      through them, one sample thick - a slice through the captured array, not a
      resample of it. The S11 / load / S21 markers are then related to those
      sheets in the corner legend: which marker lies ON a drawn cut, and which
      is off both because its x is outside the captured slab (the load sits at
      20.0 mm, the slab ends at 3.2 mm). No marker is moved or clipped to fit.
    * a |S11| / |S21| vs frequency panel. The record beside the dump is a SINGLE
      frequency, so a curve cannot come from it: the panel reads a separate
      multi-frequency sweep artefact beside the dump, plots the recorded rows as
      markers only (no line, nothing between the bins), and says in words when
      no such sweep is on disk.

STATUS: the web path (trame server, layout, slider callbacks, panel placement)
    is UNTESTED. Only the numpy / CLI path (--help, --list-keys) has been
    exercised. Treat any browser-side behaviour as unverified. All four layers
    above were added in the same environment: pyvista, trame and VTK are not
    installed here, so they have never been rendered either. The halves that do
    not need those packages - the sweep loader and the matplotlib panel image -
    were run against the real artefacts on disk.
"""

from __future__ import annotations

import argparse
import errno
import json
import sys
from pathlib import Path

import numpy as np

# server/ sits ONE level below the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT = "evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz"
PLANE_KEY = "plane_ez"
# The |S11|/|S21| vs frequency sweep the panel reads, when a dump ships one.
# The record written beside the dump carries ONE frequency (geometry.f_hz), so a
# curve cannot come from it; this is a different artefact of the same study. It
# is looked for beside the dump first, then at this repo-relative path.
DEFAULT_MULTIFREQ = "evidence/termination/build_A_50ohm_multifreq_summary.json"
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


# --- where each reported number is measured ---------------------------------
#
# The npz carries grid metadata only (nstep, nx/ny/nz, cell_m); it holds no
# plane positions at all. Those live in the study record written beside the
# dump under the same stem with a .json suffix
# (evidence/termination/run_build_A.py writes it). The three constants below are
# FALLBACKS for a dump shipped without its record: the UI prints the word
# FALLBACK beside any position that came from them, so a reader can tell a
# recorded plane from a typed-in one without opening this file.
#
# 20.0 mm is the Build A load, 20.4 mm is one cell past the load column (50) at
# cell 0.4 mm, and 0.0 mm is the port end of the line.
FALLBACK_LOAD_MM = 20.0
FALLBACK_S11_MM = 0.0
FALLBACK_S21_MM = 20.4


def _as_float(value):
    """float() or None, never raising. Used on optional record keys."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _record_candidates(npz_path: Path) -> list[Path]:
    """Candidate record paths for a dump, best first.

    The dump and its record do not always share a stem exactly: the shipped
    field dump is ``..._ghostwave_fields.npz`` while the study that produced it
    wrote ``..._ghostwave.json``. Both spellings are tried instead of guessing
    one and silently reporting "no record".
    """
    candidates = [npz_path.with_suffix(".json")]
    stem = npz_path.stem
    for suffix in ("_fields", "_planes", "_dump"):
        if stem.endswith(suffix):
            candidates.append(
                npz_path.with_name(stem[: -len(suffix)] + ".json")
            )
            break
    return candidates


def load_record(npz_path: Path):
    """Read the study record stored beside the dump; None if there is none.

    Optional by design: the viewer has to open the dump on its own. Every
    failure path is a stderr note plus None - never an exception - because the
    operator's only feedback here is the browser page.
    """
    candidates = _record_candidates(npz_path)
    record_path = next((p for p in candidates if p.is_file()), None)
    if record_path is None:
        print(
            "[poc_app] no study record beside the dump (tried "
            + ", ".join(str(p) for p in candidates)
            + "); plane positions fall back to the built-in constants",
            file=sys.stderr,
        )
        return None
    try:
        with record_path.open(encoding="utf-8") as fh:
            record = json.load(fh)
    except Exception as exc:  # noqa: BLE001 - optional input, never fatal
        print(f"[poc_app] record {record_path} unreadable: {exc}", file=sys.stderr)
        return None
    if not isinstance(record, dict):
        print(
            f"[poc_app] record {record_path} is not a JSON object; ignoring it",
            file=sys.stderr,
        )
        return None
    # Provenance in the log too, not only in the browser: whoever reads the log
    # has to be able to tell which file the plane positions came from.
    print(f"[poc_app] study record: {record_path}")
    return record


# --- the |S11| / |S21| vs frequency sweep ------------------------------------
#
# WHY a second file: the record beside the dump is a SINGLE-frequency run - it
# stores one geometry.f_hz, one s11.magnitude, one s21.magnitude. A curve drawn
# from it would be one point dressed up as a trend. The study that sweeps f
# writes a summary JSON with one row per frequency instead, and that file is an
# artefact of its own: it is looked for beside the dump first, then at
# DEFAULT_MULTIFREQ. Both are optional in exactly the way load_record is -
# every failure path is a stderr note plus None, never an exception.


def _multifreq_candidates(npz_path: Path) -> list[Path]:
    """Candidate multi-frequency summary paths for a dump, best first."""
    candidates: list[Path] = []
    try:
        candidates.extend(sorted(npz_path.parent.glob("*multifreq*summary*.json")))
    except Exception as exc:  # noqa: BLE001 - a bad parent dir is not fatal
        print(f"[poc_app] sweep scan skipped: {exc}", file=sys.stderr)
    fallback = _resolve(DEFAULT_MULTIFREQ)
    if fallback not in candidates:
        candidates.append(fallback)
    return candidates


def load_multifreq(npz_path: Path):
    """Read the multi-frequency |S11| / |S21| sweep beside the dump.

    Returns ``{"path", "points", "skipped", ...}`` or None; ``points`` are
    ``(f_ghz, |S11|, |S21|, artefact)`` tuples, sorted by frequency and otherwise
    as recorded. Nothing here interpolates, smooths or re-orders into a curve: a
    row whose ``errors`` list is not empty, or which is missing a frequency or
    either magnitude, is DROPPED and counted, because drawing it as zero would
    invent a measurement.
    """
    candidates = _multifreq_candidates(npz_path)
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        print(
            "[poc_app] no multi-frequency sweep beside the dump (tried "
            + ", ".join(str(p) for p in candidates)
            + "); the |S11|/|S21| panel will say so",
            file=sys.stderr,
        )
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            summary = json.load(fh)
    except Exception as exc:  # noqa: BLE001 - optional input, never fatal
        print(f"[poc_app] sweep {path} unreadable: {exc}", file=sys.stderr)
        return None
    if not isinstance(summary, dict):
        print(
            f"[poc_app] sweep {path} is not a JSON object; ignoring it",
            file=sys.stderr,
        )
        return None
    rows = summary.get("rows")
    if not isinstance(rows, list):
        print(
            f"[poc_app] sweep {path} has no rows list; ignoring it",
            file=sys.stderr,
        )
        return None

    points = []
    skipped: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            skipped.append("a row that is not an object")
            continue
        label = row.get("artefact") or "a row with no artefact name"
        f_ghz = _as_float(row.get("f_ghz_used"))
        if f_ghz is None:
            f_hz = _as_float(row.get("f_hz_used"))
            f_ghz = None if f_hz is None else f_hz / 1e9
        s11 = _as_float(row.get("s11.magnitude"))
        s21 = _as_float(row.get("s21.magnitude"))
        if f_ghz is None or s11 is None or s21 is None:
            skipped.append(f"{label} (no frequency or no magnitude)")
            continue
        errors = row.get("errors") or []
        if errors:
            skipped.append(f"{label} (errors: {errors})")
            continue
        points.append((f_ghz, s11, s21, str(label)))

    if not points:
        print(
            f"[poc_app] sweep {path}: no usable rows "
            f"({len(skipped)} skipped)",
            file=sys.stderr,
        )
        return None
    points.sort(key=lambda point: point[0])
    # Provenance in the log too, not only in the panel: whoever reads this has to
    # be able to tell which file the plotted rows came from.
    print(
        f"[poc_app] multi-frequency sweep: {path} "
        f"({len(points)} rows kept, {len(skipped)} skipped)"
    )
    for note in skipped:
        print(f"[poc_app]   skipped {note}", file=sys.stderr)
    return {
        "path": path,
        "points": points,
        "skipped": skipped,
        "dossier": summary.get("dossier"),
        "generated_utc": summary.get("generated_utc"),
        "bin_spacing_mhz": _as_float(summary.get("bin_spacing_mhz")),
    }


def _own_frequency_ghz(record):
    """The dump's own recorded frequency in GHz, or None.

    Reported next to the sweep so the two are never confused: the dump is one
    run at one frequency, the sweep is a different set of runs.
    """
    if not isinstance(record, dict):
        return None
    geom = record.get("geometry")
    if not isinstance(geom, dict):
        return None
    f_hz = _as_float(geom.get("f_hz"))
    if f_hz is None:
        f_hz = _as_float(geom.get("f"))
    return None if f_hz is None else f_hz / 1e9


def _frequency_rows(mf: dict) -> list[str]:
    """The recorded rows as plain text: the fallback when no chart is drawn."""
    rows = [f"{'f [GHz]':>9}  {'|S11|':>7}  {'|S21|':>7}  artefact"]
    for f_ghz, s11, s21, artefact in mf["points"]:
        rows.append(f"{f_ghz:9.4f}  {s11:7.4f}  {s21:7.4f}  {artefact}")
    return rows


def _frequency_caption(mf: dict, record) -> str:
    """One line naming the source file, the row count, and what was NOT done."""
    caption = (
        f"{len(mf['points'])} recorded frequencies from {mf['path'].name} - "
        "markers only, no line and no interpolation: nothing was solved "
        "between these bins"
    )
    if mf.get("bin_spacing_mhz"):
        caption += f" (bin spacing {mf['bin_spacing_mhz']:.1f} MHz)"
    own_f = _own_frequency_ghz(record)
    if own_f is not None:
        caption += (
            f"; the dump beside this panel is a single-frequency run at "
            f"{own_f:.4f} GHz (record.geometry.f_hz) and its own numbers are "
            "not among these rows"
        )
    return caption


def build_frequency_chart(mf: dict) -> dict:
    """Render |S11| and |S21| vs frequency to a PNG data URI.

    Returns ``{"image": data_uri | None, "rows": [...], "reason": str | None}``.
    matplotlib is a project dependency, but it is imported HERE, lazily and
    guarded: the numpy-only paths (--help, --list-keys) must never need it, and
    a missing or broken matplotlib has to cost the picture, not the page - the
    caller falls back to the text rows.

    Markers only, no connecting line: a line between two recorded bins is a
    claim about the frequencies between them, and no run covers those.
    """
    rows = _frequency_rows(mf)
    try:
        import base64
        import io

        import matplotlib

        try:
            matplotlib.use("Agg")
        except Exception:  # noqa: BLE001 - an existing backend is acceptable
            pass
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001 - text rows instead of a picture
        print(f"[poc_app] no chart (matplotlib unusable: {exc})", file=sys.stderr)
        return {
            "image": None,
            "rows": rows,
            "reason": f"matplotlib unusable: {exc}",
        }

    freqs = [point[0] for point in mf["points"]]
    s11s = [point[1] for point in mf["points"]]
    s21s = [point[2] for point in mf["points"]]
    try:
        fig, ax = plt.subplots(figsize=(5.4, 1.9), dpi=110)
        ax.plot(
            freqs,
            s11s,
            "o",
            color="#1f77b4",
            markersize=5,
            linestyle="none",
            label="|S11|",
        )
        ax.plot(
            freqs,
            s21s,
            "s",
            color="#d62728",
            markersize=5,
            linestyle="none",
            label="|S21|",
        )
        ax.set_xlabel("frequency [GHz]", fontsize=7)
        ax.set_ylabel("magnitude", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.grid(True, color="#dddddd", linewidth=0.5)
        ax.legend(fontsize=6, frameon=False, loc="best")
        ax.set_title(
            "Build A, 50 ohm load: |S11| and |S21| per recorded frequency",
            fontsize=7,
        )
        fig.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        plt.close(fig)
        png = buffer.getvalue()
    except Exception as exc:  # noqa: BLE001 - never take the server down
        print(f"[poc_app] chart render skipped: {exc}", file=sys.stderr)
        return {
            "image": None,
            "rows": rows,
            "reason": f"chart render failed: {exc}",
        }

    uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    print(f"[poc_app] frequency chart: {len(png)} PNG bytes, {len(uri)} URI chars")
    return {"image": uri, "rows": rows, "reason": None, "png_bytes": len(png)}


def _plane_layout(info: dict, record) -> dict:
    """Resolve the x of the load, S11 port and S21 planes, in mm.

    Each value carries the record key it came from (``src_*``) so the UI can
    print the provenance instead of asserting a position. Priority is always
    recorded metres > recorded column index times cell size > FALLBACK constant.
    """
    n_st = int(info[PLANE_KEY].shape[0])
    cell_mm = _cell_mm(info)
    stations_mm = [i * cell_mm for i in range(n_st)]

    record = record if isinstance(record, dict) else {}
    geom = record.get("geometry")
    if not isinstance(geom, dict):
        geom = {}

    # Load plane: the study writes geometry.loads as [{column, kind, value, x}].
    x_load, src_load, ix_load = FALLBACK_LOAD_MM, "FALLBACK", None
    loads = geom.get("loads")
    if isinstance(loads, list) and loads and isinstance(loads[0], dict):
        ix_load = _as_float(loads[0].get("column"))
        x_load_m = _as_float(loads[0].get("x"))
        if x_load_m is not None:
            x_load, src_load = x_load_m * 1e3, "geometry.loads[0].x"
        elif ix_load is not None:
            x_load, src_load = ix_load * cell_mm, "geometry.loads[0].column"

    # S11 port reference plane: the study records it as a cell index, not an x.
    x_s11, src_s11 = FALLBACK_S11_MM, "FALLBACK"
    ix_port = _as_float(geom.get("ix_port"))
    if ix_port is not None:
        x_s11, src_s11 = ix_port * cell_mm, "geometry.ix_port"

    # S21 extraction plane: recorded x first, then either index key the study
    # writes (geometry.s21_plane_index, s11_at_plane.plane_index).
    x_s21, src_s21, ix_s21 = FALLBACK_S21_MM, "FALLBACK", None
    s21_plane = record.get("s21_plane")
    at_plane = record.get("s11_at_plane")
    if isinstance(s21_plane, dict):
        x_s21_m = _as_float(s21_plane.get("x_m"))
        if x_s21_m is not None:
            x_s21, src_s21 = x_s21_m * 1e3, "s21_plane.x_m"
    # The index keys are resolved separately from the recorded x because the
    # validity test below is a statement about INDICES: a recorded x alone does
    # not say whether the plane sits past the load column.
    for key, block in (("s21_plane_index", geom), ("plane_index", at_plane)):
        if ix_s21 is not None or not isinstance(block, dict):
            continue
        idx = _as_float(block.get(key))
        if idx is not None:
            ix_s21 = idx
            if src_s21 == "FALLBACK":
                x_s21, src_s21 = idx * cell_mm, key

    # Validity of the extraction plane. The record's own flag wins when it is
    # there; no stored record carries it yet, so the rule the solver implements
    # is applied here and labelled as computed - a plane strictly beyond the
    # load column reads a collapsed field.
    valid = None
    valid_src = "not recorded"
    reason = None
    for holder in (geom, record):
        if isinstance(holder.get("s11_at_plane_valid"), bool):
            valid = bool(holder["s11_at_plane_valid"])
            reason = holder.get("s11_at_plane_invalid_reason")
            valid_src = "recorded"
            break
    if valid is None and ix_s21 is not None and ix_load is not None:
        valid = not (ix_s21 > ix_load)
        reason = None if valid else "plane_beyond_load"
        valid_src = f"computed: plane {int(ix_s21)} vs load {int(ix_load)}"

    # The port-plane cross-section is the captured station nearest the port x.
    # The dump stacks captured planes from x = 0 at one cell spacing, so this
    # picks station 0 unless the record puts the port plane somewhere else.
    slice_index = min(range(n_st), key=lambda i: abs(stations_mm[i] - x_s11))

    return {
        "cell_mm": cell_mm,
        "n_st": n_st,
        "stations_mm": stations_mm,
        "x_load_mm": x_load,
        "src_load": src_load,
        "ix_load": ix_load,
        "x_s11_mm": x_s11,
        "src_s11": src_s11,
        "x_s21_mm": x_s21,
        "src_s21": src_s21,
        "s21_valid": valid,
        "s21_valid_src": valid_src,
        "s21_reason": reason,
        "slice_index": slice_index,
    }


def _s21_label(planes: dict) -> str:
    """The S21 marker's text, including whether its plane is usable."""
    head = f"S21 plane\nx = {planes['x_s21_mm']:.4f} mm"
    if planes["s21_valid"] is False:
        return head + f"\nPAST THE LOAD ({planes['s21_reason']}): field collapsed"
    if planes["s21_valid"] is None:
        return head + "\nvalidity not recorded"
    return head + f"\nvalid ({planes['s21_valid_src']})"


def _marker_text(planes: dict, extra_lines=None) -> str:
    """Corner legend: what each marker is, where its x came from, and its state.

    ``extra_lines`` carries the cut-sheet sentences from ``_marker_cut_lines``:
    which marker lies ON a drawn cut and which is off every cut, with the reason.
    They belong here, in the legend, because a marker that is drawn but not
    explained is exactly what this layer must not do.
    """
    lines = [
        f"S11 port  x = {planes['x_s11_mm']:9.4f} mm  [{planes['src_s11']}]",
        f"load      x = {planes['x_load_mm']:9.4f} mm  [{planes['src_load']}]",
        f"S21 plane x = {planes['x_s21_mm']:9.4f} mm  [{planes['src_s21']}]",
    ]
    if planes["s21_valid"] is False:
        lines.append(
            f"S21 plane reads a collapsed field: {planes['s21_reason']} "
            f"[{planes['s21_valid_src']}]"
        )
    elif planes["s21_valid"] is None:
        lines.append(
            "S21 plane validity: not recorded, and not derivable from this dump"
        )
    else:
        lines.append(f"S21 plane validity: {planes['s21_valid_src']}")
    lines.append(
        f"captured slab spans x = {planes['stations_mm'][0]:.4f} .. "
        f"{planes['stations_mm'][-1]:.4f} mm ({planes['n_st']} planes)"
    )
    for extra in extra_lines or ():
        lines.append(extra)
    return "\n".join(lines)


def _view_label(
    view_mode: str, planes: dict, toggle_available: bool, cuts=None
) -> str:
    """Browser-side label naming the view that is currently drawn.

    ``cuts`` is the dict from ``_cut_layout``: when it is given the label also
    says which two samples the cut sheets sit on, because a one-sample-thick
    sheet cannot be counted off a screen.
    """
    if view_mode == "port":
        idx = planes["slice_index"]
        label = (
            f"port-plane |Ez|: station {idx + 1}/{planes['n_st']}, "
            f"x = {planes['stations_mm'][idx]:.4f} mm"
        )
    else:
        label = (
            f"|Ez| volume: {planes['n_st']} captured x-planes, "
            f"x = {planes['stations_mm'][0]:.4f} .. "
            f"{planes['stations_mm'][-1]:.4f} mm"
        )
    if cuts is not None:
        label += (
            f"  cuts: y = {cuts['y_mm']:.4f} mm "
            f"(j {cuts['j'] + 1}/{cuts['n_j']}), "
            f"z = {cuts['z_mm']:.4f} mm (k {cuts['k'] + 1}/{cuts['n_k']})"
        )
        if view_mode == "port":
            label += " - not drawn in this view"
    if not toggle_available:
        # Say why the other view cannot be reached: the widget is missing, not
        # the data. Without VBtn there is nothing to click.
        label += "  (no VBtn widget in this install: view toggle unavailable)"
    return label


# --- the two Y / Z cut sheets ------------------------------------------------
#
# The volume view stacks 9 captured x-planes over a 213 x 22 (y, z) cross
# section. Two sliders pick ONE y sample and ONE z sample and draw the sheet
# through them, so the field can be read on a slice instead of through a volume.
#
# WHY one sample thick and not a resample: the dump holds exactly these samples,
# so a cut through them is recorded data. A resampled cut would be a picture of a
# number nobody computed - the same reason the module docstring refuses to
# invent x between the 9 stations.
#
# The trap this layer has to avoid is a marker that LOOKS like it belongs to a
# cut. The S11 / load / S21 markers sit at mid-height of the y-z section and at
# x = 0.0, 20.0 and 20.4 mm, while the cut sheets span only the captured slab
# (x = 0.0 .. 3.2 mm): the load and the S21 plane are off every sheet by
# construction. Nothing is moved, clipped or projected to make them fit - each
# marker's relation to the drawn cuts is stated in the corner legend instead,
# because a marker drawn at the edge of a sheet would be a lie about where the
# plane is.


def _cut_layout(info: dict, j_cut=None, k_cut=None) -> dict:
    """Resolve which y and z sample the cut sheets sit on. Numbers only.

    Split out from build_cut_sheets so the labels, the legend and the slider
    handlers can describe the cuts without importing pyvista.
    """
    plane = info[PLANE_KEY]
    n_st, n_j, n_k = plane.shape
    cell_mm = _cell_mm(info)
    j = n_j // 2 if j_cut is None else j_cut
    k = n_k // 2 if k_cut is None else k_cut
    try:
        j = max(0, min(n_j - 1, int(j)))
    except (TypeError, ValueError):
        j = n_j // 2
    try:
        k = max(0, min(n_k - 1, int(k)))
    except (TypeError, ValueError):
        k = n_k // 2
    return {
        "cell_mm": cell_mm,
        "n_st": n_st,
        "n_j": n_j,
        "n_k": n_k,
        "j": j,
        "k": k,
        "y_mm": j * cell_mm,
        "z_mm": k * cell_mm,
        "x_lo_mm": 0.0,
        "x_hi_mm": (n_st - 1) * cell_mm,
    }


def _cut_text(layout: dict) -> str:
    """The slider label: which sample, and where that sample is in mm."""
    return (
        f"cut y = {layout['j'] + 1}/{layout['n_j']} "
        f"(y = {layout['y_mm']:.4f} mm)   "
        f"cut z = {layout['k'] + 1}/{layout['n_k']} "
        f"(z = {layout['z_mm']:.4f} mm)   one sample each, no interpolation"
    )


def build_cut_sheets(info: dict, layout: dict) -> list:
    """Build the two cut sheets as one-sample-thick pyvista images.

    The same construction as the port-plane view in _draw_scene (one sample
    drawn one thick), so no new primitive is introduced:

        y = j * cell : plane[:, j:j+1, :] -> dims (n_st, 1, n_k), origin y = j*cell
        z = k * cell : plane[:, :, k:k+1] -> dims (n_st, n_j, 1), origin z = k*cell

    Axis 0 is the station axis and stays the x axis of the sheet in both cases;
    VTK wants x to vary fastest, hence the Fortran ravel, as in build_grid.
    """
    import pyvista as pv

    plane = info[PLANE_KEY]
    n_st, n_j, n_k = plane.shape
    cell_mm = layout["cell_mm"]
    j = int(layout["j"])
    k = int(layout["k"])

    y_sheet = pv.ImageData()
    y_sheet.dimensions = (n_st, 1, n_k)
    y_sheet.spacing = (cell_mm, cell_mm, cell_mm)
    y_sheet.origin = (0.0, j * cell_mm, 0.0)
    y_sheet.point_data["ez_abs"] = np.ascontiguousarray(
        np.abs(plane[:, j : j + 1, :]).ravel(order="F"), dtype=float
    )

    z_sheet = pv.ImageData()
    z_sheet.dimensions = (n_st, n_j, 1)
    z_sheet.spacing = (cell_mm, cell_mm, cell_mm)
    z_sheet.origin = (0.0, 0.0, k * cell_mm)
    z_sheet.point_data["ez_abs"] = np.ascontiguousarray(
        np.abs(plane[:, :, k : k + 1]).ravel(order="F"), dtype=float
    )
    return [("y", y_sheet), ("z", z_sheet)]


def _marker_cut_relation(planes: dict, layout: dict) -> list[str]:
    """State, per marker, whether it lies ON a drawn cut sheet or off them.

    The three markers sit at mid-height of the y-z section, so their y and z are
    fixed while the cuts move with the sliders. A marker counts as ON a sheet
    only when its transverse coordinate is within half a cell of the cut AND its
    x is inside that sheet's own x extent; anything else is off, and the reason
    is spelled out. No marker is moved to make it fit.
    """
    cell_mm = layout["cell_mm"]
    tol = 0.5 * cell_mm
    y_mid = 0.5 * layout["n_j"] * cell_mm
    z_mid = 0.5 * layout["n_k"] * cell_mm
    x_lo, x_hi = layout["x_lo_mm"], layout["x_hi_mm"]

    def in_slab(x_mm: float) -> bool:
        return (x_lo - tol) <= x_mm <= (x_hi + tol)

    lines = []
    for name, x_mm in (
        ("S11 port", planes["x_s11_mm"]),
        ("load", planes["x_load_mm"]),
        ("S21 plane", planes["x_s21_mm"]),
    ):
        on = []
        if in_slab(x_mm) and abs(y_mid - layout["y_mm"]) <= tol:
            on.append(f"the y cut (y = {layout['y_mm']:.4f} mm)")
        if in_slab(x_mm) and abs(z_mid - layout["z_mm"]) <= tol:
            on.append(f"the z cut (z = {layout['z_mm']:.4f} mm)")
        if on:
            lines.append(f"{name} marker is on " + " and ".join(on))
            continue
        why = []
        if not in_slab(x_mm):
            why.append(
                f"its x = {x_mm:.4f} mm is outside the captured slab "
                f"{x_lo:.4f}..{x_hi:.4f} mm, so no cut sheet reaches it"
            )
        if abs(y_mid - layout["y_mm"]) > tol:
            why.append(
                f"its y = {y_mid:.4f} mm is not the y cut "
                f"({layout['y_mm']:.4f} mm)"
            )
        if abs(z_mid - layout["z_mm"]) > tol:
            why.append(
                f"its z = {z_mid:.4f} mm is not the z cut "
                f"({layout['z_mm']:.4f} mm)"
            )
        lines.append(f"{name} marker is off both cuts: " + "; ".join(why))
    return lines


def _marker_cut_lines(
    planes, layout, cuts_drawn: bool, view_mode: str
) -> list[str]:
    """The cut sentences appended to the corner legend by _marker_text."""
    if not cuts_drawn:
        if view_mode == "port":
            return [
                "cut sheets: not drawn in the port view (one station only)"
            ]
        return ["cut sheets: not drawn - pyvista refused the sheets (see log)"]
    return _marker_cut_relation(planes, layout)


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


def _add_markers(plotter, info: dict, planes: dict) -> None:
    """Draw the load plane and the two extraction planes, with labels.

    WHY this layer exists: the finding behind it is that an extraction plane one
    column past the load reads a collapsed field. A number in a browser cannot
    be placed in space; a red plane at the load, with the other two planes
    marked beside it, can. Every position comes from ``planes`` (that is, from
    the record), and a position taken from a built-in constant is spelled out
    as FALLBACK in the legend.

    Both halves are guarded: a pyvista that disagrees about a Plane or a Sphere
    keyword must cost the markers, not the viewer.
    """
    import pyvista as pv

    cell_mm = planes["cell_mm"]
    y_span = info[PLANE_KEY].shape[1] * cell_mm
    z_span = info[PLANE_KEY].shape[2] * cell_mm
    y_mid, z_mid = 0.5 * y_span, 0.5 * z_span

    try:
        disc = pv.Plane(
            center=(planes["x_load_mm"], y_mid, z_mid),
            direction=(1.0, 0.0, 0.0),
            i_size=y_span,
            j_size=z_span,
        )
        plotter.add_mesh(disc, color="red", opacity=0.25)
    except Exception as exc:  # noqa: BLE001 - losing the plane is survivable
        print(f"[poc_app] load plane not drawn: {exc}", file=sys.stderr)

    # Point markers at mid-height of each plane: x is the axis that matters
    # here, so a sphere plus a label is unambiguous where a disc is not.
    points = [
        (planes["x_s11_mm"], y_mid, z_mid),
        (planes["x_load_mm"], y_mid, z_mid),
        (planes["x_s21_mm"], y_mid, z_mid),
    ]
    labels = [
        f"S11 port plane\nx = {planes['x_s11_mm']:.4f} mm",
        f"load (termination)\nx = {planes['x_load_mm']:.4f} mm",
        _s21_label(planes),
    ]
    colours = ("blue", "red", "orange")
    radius = max(0.5, 0.02 * y_span)
    for point, colour in zip(points, colours):
        try:
            plotter.add_mesh(pv.Sphere(radius=radius, center=point), color=colour)
        except Exception as exc:  # noqa: BLE001
            print(f"[poc_app] marker sphere not drawn: {exc}", file=sys.stderr)
    try:
        plotter.add_point_labels(points, labels, font_size=9, text_color="black")
    except Exception as exc:  # noqa: BLE001 - the corner legend still says it
        print(f"[poc_app] marker labels not drawn: {exc}", file=sys.stderr)


def _draw_scene(
    plotter,
    info: dict,
    planes: dict,
    view_mode: str,
    station: int,
    j_cut=None,
    k_cut=None,
) -> None:
    """Draw one view into the single existing plotter.

    WHY one plotter rebuilt rather than a second linked view: nothing in this
    file can be run where it was written (no VTK, no browser), so the smallest
    construction wins. Rebuilding one renderer is a single code path and cannot
    disagree with itself about the camera or the marker layer. Two linked
    render windows could disagree silently, which is the failure mode nobody
    can debug from the operator's side.

    ``j_cut`` / ``k_cut`` choose the y and z sample of the two cut sheets, and
    they are honoured in the volume view only: the port-plane view already IS a
    single cross-section, so two more sheets there would only occlude it. The
    corner legend always says which cuts are on screen and how each marker
    stands relative to them, which is what stops a marker from being read as
    something the sliders moved.
    """
    import pyvista as pv

    n_st = int(info[PLANE_KEY].shape[0])
    cell_mm = planes["cell_mm"]
    # One build, used for both the volume view and the outline.
    grid = build_grid(info)
    # Which y / z sample the cut sheets sit on, and whether they were actually
    # drawn: the legend must not claim sheets that pyvista refused.
    cut_layout = _cut_layout(info, j_cut, k_cut)
    cuts_drawn = False

    try:
        plotter.clear()
    except Exception as exc:  # noqa: BLE001
        # Keep going: a stale picture beats a dead server.
        print(f"[poc_app] plotter.clear failed: {exc}", file=sys.stderr)

    if view_mode == "port":
        # The port-plane cross-section: the captured station nearest the port
        # x, drawn as a single-sample-thick image so it lies in the y-z plane.
        idx = int(planes["slice_index"])
        x_mm = planes["stations_mm"][idx]
        shot = info[PLANE_KEY][idx]
        image = pv.ImageData()
        image.dimensions = (int(shot.shape[0]), int(shot.shape[1]), 1)
        image.spacing = (cell_mm, cell_mm, cell_mm)
        image.origin = (x_mm, 0.0, 0.0)
        image.point_data["ez_abs"] = np.ascontiguousarray(
            np.abs(shot).ravel(order="F"), dtype=float
        )
        plotter.add_mesh(
            image,
            scalars="ez_abs",
            cmap="turbo",
            scalar_bar_args={"title": f"|Ez| at x = {x_mm:.4f} mm [V/m]"},
        )
    else:
        plotter.add_volume(
            grid,
            scalars="ez_abs",
            cmap="turbo",
            scalar_bar_args={"title": "|Ez| [V/m]"},
        )
        # The two cut sheets: one sample each, drawn opaque enough to read the
        # field on, sharing the volume's colour scale (so only one bar is
        # shown). Guarded - losing the cuts must cost the cuts, not the view.
        try:
            for _axis, sheet in build_cut_sheets(info, cut_layout):
                plotter.add_mesh(
                    sheet,
                    scalars="ez_abs",
                    cmap="turbo",
                    opacity=0.75,
                    show_scalar_bar=False,
                )
        except Exception as exc:  # noqa: BLE001 - see comment above
            print(f"[poc_app] cut sheets not drawn: {exc}", file=sys.stderr)
        else:
            cuts_drawn = True

    plotter.add_mesh(grid.outline(), color="black", line_width=1)
    plotter.add_axes(xlabel="x [mm]", ylabel="y [mm]", zlabel="z [mm]")
    _add_markers(plotter, info, planes)
    plotter.add_text(
        _station_text(int(station), cell_mm, n_st),
        name="station_label",
        position="upper_left",
        font_size=10,
        color="black",
    )
    plotter.add_text(
        _marker_text(
            planes, _marker_cut_lines(planes, cut_layout, cuts_drawn, view_mode)
        ),
        name="marker_legend",
        position="lower_left",
        font_size=8,
        color="black",
    )
    # Isometric, then fit everything. The markers sit up to 20 mm away from a
    # 3.2 mm captured slab, so a camera framed on the slab alone would hide the
    # entire point of the layer.
    try:
        plotter.view_isometric()
        plotter.reset_camera()
    except Exception as exc:  # noqa: BLE001
        print(f"[poc_app] camera reset skipped: {exc}", file=sys.stderr)


# Everything the browser view needs beyond numpy, kept in one place so the
# preflight below can report EVERY missing package in one run instead of
# failing on one package per run.
WEB_MODULES = (
    ("trame", "trame"),
    ("trame_pyvista", "trame-pyvista"),
    ("trame_vtk", "trame-vtk"),
    ("vtk", "vtk"),
    ("pyvista", "pyvista"),
)
WEB_VUETIFY_MODULES = ("trame.ui.vuetify3", "trame.ui.vuetify2")


def check_web_requirements() -> list[str]:
    """Return pip names of web UI packages that are missing or unusable.

    Nothing here raises: a package that will not import is recorded and the
    next one is probed, so the caller can print a single install line for all
    of them.
    """
    import importlib

    missing: list[str] = []
    for module, pip_name in WEB_MODULES:
        try:
            importlib.import_module(module)
        except Exception:  # noqa: BLE001 - any failure means "not usable"
            print(
                f"[poc_app] cannot import {module} (provides: {pip_name})",
                file=sys.stderr,
            )
            missing.append(pip_name)

    for ui_path in WEB_VUETIFY_MODULES:
        try:
            importlib.import_module(ui_path)
        except Exception:  # noqa: BLE001 - try the next variant
            continue
        break
    else:
        print(
            "[poc_app] cannot import trame.ui.vuetify3 or trame.ui.vuetify2 "
            "(provides: trame-vuetify)",
            file=sys.stderr,
        )
        missing.append("trame-vuetify")

    return missing


def run_web(info: dict, host: str, port: int, station: int) -> int:
    missing = check_web_requirements()
    if missing:
        print(
            "[poc_app] the web UI cannot start: packages are missing.",
            file=sys.stderr,
        )
        print(
            "[poc_app] fix: python3 -m pip install " + " ".join(missing),
            file=sys.stderr,
        )
        print(
            "[poc_app] or:  python3 -m pip install -r requirements-web.txt",
            file=sys.stderr,
        )
        print("[poc_app] then re-run the same command.", file=sys.stderr)
        return 1
    print("[poc_app] web dependencies present")

    import importlib

    from trame.app import get_server

    try:
        from importlib.metadata import version as _pkg_version

        trame_version = _pkg_version("trame")
    except Exception:
        import trame

        trame_version = getattr(trame, "__version__", "unknown")

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
    # VBtn carries the view toggle added below; a variant without it degrades
    # to a label that says the toggle is unavailable.
    for name in ("VSpacer", "VSlider", "VLabel", "VContainer", "VBtn"):
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

    try:
        from pyvista.trame.ui import plotter_ui
    except Exception as exc:  # noqa: BLE001 - diagnose instead of traceback
        print(f"[poc_app] pyvista.trame.ui is unusable: {exc}", file=sys.stderr)
        print(
            "[poc_app] fix: python3 -m pip install -r requirements-web.txt",
            file=sys.stderr,
        )
        return 1

    plane = info[PLANE_KEY]
    n_st = plane.shape[0]
    n_j = plane.shape[1]
    n_k = plane.shape[2]
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

    # Plane positions come from the record beside the dump, so the markers and
    # the labels below cannot drift from the geometry that produced the numbers.
    record = load_record(info["path"])
    planes = _plane_layout(info, record)
    # The toggle needs the button widget AND the toolbar that carries it: when
    # any probed widget is missing the layout falls back to a label-only bar, so
    # the label then says the toggle is unavailable rather than lying.
    toggle_available = (not missing_widgets) and ("VBtn" in widgets)
    # Default cuts: the middle sample of each transverse axis, which is where
    # the markers already sit, so the first frame is the picture the previous
    # version drew. The sliders move these two numbers and nothing else.
    cut_layout = _cut_layout(info, n_j // 2, n_k // 2)
    state.cut_y = cut_layout["j"]
    state.cut_z = cut_layout["k"]
    state.cut_label = _cut_text(cut_layout)
    state.view_mode = "volume"
    state.view_label = _view_label(
        state.view_mode, planes, toggle_available, cut_layout
    )

    # The multi-frequency sweep, if one was written beside the dump. Optional
    # at every step: no file, no matplotlib, an unusable row - the 3-D view
    # still comes up, and the caption says what is missing rather than going
    # quiet.
    multifreq = load_multifreq(info["path"])
    frequency_panel = (
        None if multifreq is None else build_frequency_chart(multifreq)
    )
    if multifreq is None:
        frequency_caption = (
            "no multi-frequency |S11|/|S21| sweep on disk yet: looked for "
            "*multifreq*summary*.json beside "
            f"{info['path']} and at {DEFAULT_MULTIFREQ}"
        )
    else:
        frequency_caption = _frequency_caption(multifreq, record)
    # The plotter_ui handle only exists once the layout has been built, so the
    # handlers below reach it through this dict instead of closing over it.
    handles: dict = {}

    def _redraw() -> None:
        """Rebuild the scene in the one plotter. Failure leaves the old picture."""
        try:
            _draw_scene(
                plotter,
                info,
                planes,
                state.view_mode,
                int(state.station),
                int(state.cut_y),
                int(state.cut_z),
            )
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - never take the server down
            print(f"[poc_app] redraw skipped: {exc}", file=sys.stderr)

    # Registered BEFORE the layout is built, so ctrl.toggle_view exists by the
    # time the toolbar button binds to it.
    @ctrl.set("toggle_view")
    def _on_toggle_view(**_kwargs) -> None:
        state.view_mode = "port" if state.view_mode == "volume" else "volume"
        state.view_label = _view_label(
            state.view_mode,
            planes,
            toggle_available,
            _cut_layout(info, int(state.cut_y), int(state.cut_z)),
        )
        _redraw()
        view_handle = handles.get("view")
        if view_handle is not None:
            try:
                view_handle.update()
            except Exception as exc:  # noqa: BLE001
                print(f"[poc_app] view update skipped: {exc}", file=sys.stderr)

    def _on_cut_change(axis: str, value) -> None:
        """Clamp one cut index, store it, and rebuild the scene."""
        current = state.cut_y if axis == "y" else state.cut_z
        limit = (n_j if axis == "y" else n_k) - 1
        try:
            idx = int(round(float(value)))
        except (TypeError, ValueError):
            idx = int(current)
        idx = max(0, min(limit, idx))
        if axis == "y":
            state.cut_y = idx
        else:
            state.cut_z = idx
        layout = _cut_layout(info, int(state.cut_y), int(state.cut_z))
        state.cut_label = _cut_text(layout)
        state.view_label = _view_label(
            state.view_mode, planes, toggle_available, layout
        )
        _redraw()
        view_handle = handles.get("view")
        if view_handle is not None:
            try:
                view_handle.update()
            except Exception as exc:  # noqa: BLE001
                print(f"[poc_app] view update skipped: {exc}", file=sys.stderr)

    @ctrl.set("cut_y")
    def _on_cut_y(*args, **_kwargs) -> None:
        value = args[0] if args else _kwargs.get("cut_y", state.cut_y)
        _on_cut_change("y", value)

    @ctrl.set("cut_z")
    def _on_cut_z(*args, **_kwargs) -> None:
        value = args[0] if args else _kwargs.get("cut_z", state.cut_z)
        _on_cut_change("z", value)

    # First draw goes through the same function the toggle uses, so the marker
    # layer is on screen before the first click and both views share one camera
    # path. create_plotter's own draw is superseded here, not modified.
    _redraw()

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

    # trame's html widgets carry the cut-slider row and the frequency panel.
    # Probed exactly like the Vuetify classes: html widgets that will not import
    # cost the extra row and the panel, never the 3-D view.
    html_widgets = None
    html_div = None
    try:
        from trame.widgets import html as html_widgets

        html_div = getattr(html_widgets, "Div", None)
    except Exception as exc:  # noqa: BLE001 - optional layer
        print(
            f"[poc_app] trame.widgets.html unavailable ({exc}): "
            "no cut sliders and no frequency panel",
            file=sys.stderr,
        )

    def _emit_cut_sliders() -> None:
        """Emit the two cut sliders, or the label alone when they cannot be.

        The rows say which sample is drawn and where it is in mm, because a
        one-sample-thick sheet cannot be counted off the screen.
        """
        if missing_widgets:
            if placeholder is not None:
                placeholder("{{ cut_label }}")
            elif html_div is not None:
                html_div("{{ cut_label }}")
            return
        try:
            widgets["VLabel"]("y cut")
            widgets["VSlider"](
                v_model=("cut_y", int(state.cut_y)),
                min=0,
                max=n_j - 1,
                step=1,
                thumb_label=True,
                hide_details=True,
                style="max-width: 200px; margin: 0 10px;",
            )
            widgets["VLabel"]("z cut")
            widgets["VSlider"](
                v_model=("cut_z", int(state.cut_z)),
                min=0,
                max=n_k - 1,
                step=1,
                thumb_label=True,
                hide_details=True,
                style="max-width: 160px; margin: 0 10px;",
            )
            widgets["VLabel"]("{{ cut_label }}")
        except Exception as exc:  # noqa: BLE001 - label only, see above
            print(f"[poc_app] cut sliders unavailable: {exc}", file=sys.stderr)
            if placeholder is not None:
                placeholder("{{ cut_label }}")

    def _emit_frequency_panel() -> None:
        """Emit the |S11| / |S21| panel under the 3-D view, caption first.

        The caption always comes out, even when nothing could be plotted: a
        blank strip would look like a zero, and the whole point of this layer is
        that the sweep is a separate artefact from the dump beside it.
        """
        if html_div is None:
            return
        with html_div(
            style="border-top: 1px solid #d0d0d0; padding: 2px 0 4px 0;"
        ):
            html_div(
                frequency_caption,
                style="font-size: 11px; color: #333; padding: 2px 12px;",
            )
            if frequency_panel is None:
                return
            image = frequency_panel.get("image")
            img_cls = getattr(html_widgets, "Img", None)
            if image and img_cls is not None:
                img_cls(
                    src=image,
                    style=(
                        "height: 170px; display: block; margin: 0 12px;"
                    ),
                )
                return
            pre_cls = getattr(html_widgets, "Pre", None)
            if pre_cls is not None:
                pre_cls(
                    "\n".join(frequency_panel["rows"]),
                    style="font-size: 11px; margin: 0 12px;",
                )

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
                # The view toggle. The VBtn call is deliberately bare: no
                # variant, no icon, no size - those keyword names differ between
                # Vuetify 2 and 3 and cannot be checked in this environment. If
                # trame refuses the binding, the label says the toggle is gone
                # instead of taking the page down.
                if toggle_available:
                    try:
                        widgets["VBtn"]("Switch view", click=ctrl.toggle_view)
                        widgets["VLabel"]("{{ view_label }}")
                    except Exception as exc:  # noqa: BLE001
                        print(
                            f"[poc_app] view toggle unavailable: {exc}",
                            file=sys.stderr,
                        )
                        widgets["VLabel"](
                            "view toggle unavailable (button binding failed)"
                        )
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
            elif html_div is None:
                # No html widgets: the plotter keeps the whole content area.
                with container(fluid=True, classes="pa-0 fill-height"):
                    view = plotter_ui(plotter)
            else:
                # Fixed slider + panel rows around a flexed plotter, so the
                # sliders are always reachable and the panel never floats over
                # the 3-D view.
                with container(fluid=True, classes="pa-0 fill-height"):
                    with html_div(
                        style=(
                            "display: flex; flex-direction: column; "
                            "height: 100%; width: 100%; overflow: hidden;"
                        )
                    ):
                        with html_div(
                            style=(
                                "display: flex; flex-wrap: wrap; "
                                "align-items: center; padding: 2px 12px;"
                            )
                        ):
                            _emit_cut_sliders()
                        with html_div(
                            style="flex: 1 1 auto; min-height: 320px;"
                        ):
                            view = plotter_ui(plotter)
                        _emit_frequency_panel()

    # Now that the plotter_ui handle exists, hand it to the toggle handler.
    handles["view"] = view

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

    return run_web(info, args.host, args.port, station)


if __name__ == "__main__":
    sys.exit(main())
