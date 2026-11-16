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
      markers joined by a thin guide line for the eye (nothing between the bins
      is measured, solved or interpolated), and says in words when no such
      sweep is on disk.

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
import asyncio
import datetime
import errno
import json
import math
import re
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path
import time

import numpy as np

# The um3k modules are siblings in server/, which has no __init__.py: script
# form (`python3 server/poc_app.py`) puts server/ on sys.path so the bare names
# resolve; package form (`import server.poc_app` or `-m server.poc_app`) has no
# such entry and needs the relative form. Both hold state and layout only.
try:
    import um3k_context
    from um3k_panels import build_center_panel, build_left_panel, build_right_panel
except ModuleNotFoundError as exc:
    # Narrow, on purpose: only OUR two names may be re-routed. A dependency
    # missing inside them must surface as itself, not as a relative import.
    if exc.name not in ("um3k_context", "um3k_panels"):
        raise
    from . import um3k_context
    from .um3k_panels import build_center_panel, build_left_panel, build_right_panel

# server/ sits ONE level below the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_INPUT = "evidence/termination/build_A_50ohm_p51_ghostwave_fields.npz"
PLANE_KEY = "plane_ez"
# The cell-centred three-component E volume a dump can be asked for: the archive
# ships the flat staggered `e` vector, and this is the key it lands under when
# load_dump is asked to colocate it. Shape (nx, ny, nz, 3), the components last.
VOLUME_KEY = "e_centres"
# The SAME volume reduced to one |E| per cell and wrapped in a pyvista image,
# built ONCE per dump and cached here: ``_redraw_scene`` rebuilds the whole scene
# on every cut or station move, and the colocation behind that image costs ~1 s
# (measured: 0.84 s on the shipped dump), so a per-redraw build would be a
# per-move second. The value is a dict of ``image``, ``clim`` and ``n``.
VOLUME_ABS_KEY = "e_abs_grid"
# The SAME volume, still un-colocated: the archive's own flat, staggered ``e``
# vector plus the grid it belongs to, stashed by ``load_dump(..., e_raw=True)``.
# It exists so the colocation can wait for a READER instead of being paid by
# every load: the array itself is a cheap read, ``edge_to_cell_centres`` is not.
# The value is a dict of ``e`` (1-D, as stored) and ``nx``/``ny``/``nz``.
VOLUME_RAW_KEY = "e_raw"
# The |S11|/|S21| vs frequency sweep the panel reads, when a dump ships one.
# The record written beside the dump carries ONE frequency (geometry.f_hz), so a
# curve cannot come from it; this is a different artefact of the same study.
#
# One sweep PER ARM, keyed by the dump's own structure id: the page names the
# case it is showing, so the fallback is chosen BY STRUCTURE. A B dump must
# never be drawn with A's rows, and an unnamed structure gets NO fallback rather
# than A's. Looked for beside the dump first, then at the entry for this arm.
MULTIFREQ_BY_STRUCTURE = {
    "A": "evidence/termination/build_A_50ohm_multifreq_summary.json",
    "B": "evidence/termination/build_B_100ohm_multifreq_summary.json",
}
DEFAULT_MULTIFREQ = MULTIFREQ_BY_STRUCTURE["A"]
# When an arm ships no sweep at all, its OWN single run is still a measurement:
# one frequency, one |S11|, one |S21|. It is offered as a ONE-POINT sweep and
# flagged as such - never drawn as a curve, and never borrowed from the other
# arm, because B's |S11| is not A's.
SINGLE_RUN_BY_STRUCTURE = {
    # Only arms whose single-run record is ON DISK belong here: A has none, so
    # arm A's panel needs its sweep summary and gets no fallback below it.
    "B": "artifacts/vis_run_B_100ohm.json",
}
# The structure registry: which artefacts belong to which physical case, and
# which cell counts each of them is on. Read from the repo root. Every entry
# point below defaults to the entry named here.
DEFAULT_STRUCTURE = "build_A_50ohm"
STRUCTURES_FILE = "structures.json"
DEFAULT_HOST = "127.0.0.1"
# Deliberately 8080, NOT 8000: 8000 is reserved for the agent's own service on
# the operator's machine.
DEFAULT_PORT = 8080

# The wave-animation dumps (``emfit.vis/2``) are a different artefact from
# the legacy single-plane dump: they carry a TIME axis, so the loader and the
# viewer built for them are their own path. The npz ``schema`` key is what tells
# the two apart - never the file name, because a dump may be copied anywhere.
VIS_SCHEMA = "emfit.vis/2"
# Version 2 added the dump's own provenance (``structure_id``, ``load_ohm``).
# Version 1 is still READ - the fields are the same and the two extra keys were
# never required to draw the picture - so a dump written before the bump opens
# and reads as "structure: unknown" instead of being refused.
# These literals are STORED DATA, not identifiers: earlier builds wrote them
# into files, so none of them is renamed and every one still OPENS - the npz
# schemas below ("emfit.wavedude/2" until the rename, /1 before the provenance
# bump), and the info["format"] tag, which is NOT the npz schema (:500, :3092).
VIS_LEGACY_SCHEMAS = ("emfit.wavedude/1", "emfit.wavedude/2")
VIS_SCHEMAS = (VIS_SCHEMA,) + VIS_LEGACY_SCHEMAS
VIS_FORMAT = "um3k"  # what a new dump declares
VIS_FORMATS = (VIS_FORMAT, "wavedude")  # ... and what every build before it wrote
# A vis document gains a version when it gains a KEY - that is the rule /2 was
# introduced under. /3 adds ``load_series`` and its sibling ``load_series_reason``
# (the load's own recorded V(t)/I(t) trace) and changes nothing else. The legacy
# dump stays emfit.poc-state/1 byte-for-byte: a legacy dump HAS no load trace, so
# /1 never gains the two keys and that document is unchanged.
STATE_SCHEMA_VIS = "emfit.poc-state/3"
# Frames per second for the animation. The dump stores no wall-clock rate: t_ns
# is SIMULATION time, so this number is a viewing choice, and the page prints
# both times rather than implying the animation runs at the solver's rate.
DEFAULT_FPS = 24
# ONE colour ceiling for the whole animation, taken at this percentile of |Ez|
# over every stored frame of every plane. Frame-local scaling would renormalise
# on each step and make a decaying pulse look like it never decays.
COLOR_PERCENTILE = 99.5
# Cell edges ON for the animated field sheets. A smooth-shaded sheet hides the
# grid the field is sampled on, so a coarse dump reads as a continuous picture
# and the eye cannot tell one cell from the interpolation between two of them.
# Only the field sheets get this: the overlay boxes are decoration, not data.
VIS_SHOW_EDGES = True

# The solver that writes a fresh wave dump. It is NOT at the repo root: it lives
# beside the study that produced the dumps this viewer opens, and is run from
# there, so that is the path that actually works.
SOLVER_SCRIPT = REPO_ROOT / "evidence" / "termination" / "run_build_A.py"
# Everything under here is CERTIFIED: a report quotes these files. A button
# press must never be able to overwrite one, which is why solve_argv refuses any
# target inside it.
EVIDENCE_DIR = REPO_ROOT / "evidence"
# ... and this is where a live solve writes instead. Regenerable, disposable,
# and named so the page can say which of the two it is showing.
LIVE_DUMP = REPO_ROOT / "artifacts" / "live_run.npz"


def _resolve(path_str: str) -> Path:
    """Absolute paths pass through, relative ones are taken from the repo root."""
    path = Path(path_str)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def load_dump(
    path: Path, *, e_volume: bool = False, e_raw: bool = False
) -> dict:
    """Load the npz metadata plus the Ez plane. Exits with 2 on bad input.

    ``e_volume`` (keyword only, OFF by default) additionally colocates the
    archive's flat three-component ``e`` vector at the cell centres and returns
    it under :data:`VOLUME_KEY`. The dump already carries that vector -- it is
    what the solver stepped -- but each component is staggered on its own edges,
    so the one place that knows how to put all three on a common set of points
    is ``emfit.operators.edge_to_cell_centres``, and that is what is called here.
    A dump without an ``e`` key still loads: one line goes to stderr and the
    volume key is simply absent.

    ``e_raw`` (also keyword only, OFF by default) asks for that SAME vector
    WITHOUT the colocation: the archive's flat ``e`` array and the grid it
    lives on are stashed under :data:`VOLUME_RAW_KEY` and nothing else is
    computed. WHY it exists: the colocation is ~1 s on the shipped dump and the
    only thing that needs it is a picture a reader asks for, so a load that
    wants the plane must not drag it along; the work moves to the first READER
    (:func:`_volume_quiver_mesh`), which then hands over the volume
    ``e_volume=True`` would have produced, element for element.
    ``e_volume`` WINS when both flags are set -- the colocated volume is the
    answer a reader wants and the raw stash would only be a second copy of the
    same data. A dump without an ``e`` key still loads under ``e_raw``: one
    line to stderr, no raw key, no raise, exactly as above.

    ``station_x_m`` is the OPTIONAL station axis: metres, one entry per captured
    station, the x of the plane that station holds -- which is NOT ``i *
    cell_m``, because the study snaps each wanted station to the nearest grid
    cell. When the archive carries it, and it holds exactly one finite number
    per captured plane, it is published as ``info["station_x_m"]`` and
    :func:`_station_axis_mm` reads it in preference to every sidecar. It is
    optional because dumps written before it existed simply do not have the
    key: then nothing is stored (no placeholder, no NaN array) and the consumer
    falls back to the record beside the dump, or to its stated uniform
    assumption.
    """
    if not path.is_file():
        print(f"[poc_app] input not found: {path}", file=sys.stderr)
        raise SystemExit(2)

    e_flat = None
    station_x = None
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
        if (e_volume or e_raw) and "e" in data.files:
            # The array is read ONCE and merely read: this copy is the whole
            # cost of ``e_raw``, which is why it can be paid on every load.
            e_flat = np.asarray(data["e"])
        if "station_x_m" in data.files:
            # Read INSIDE the `with`: the archive's arrays are unreadable once
            # it closes. Whether it IS an axis is decided below, beside the
            # plane's own validation.
            station_x = np.asarray(data["station_x_m"], dtype=float).ravel()

    if plane.ndim != 3:
        print(
            f"[poc_app] {PLANE_KEY} has shape {plane.shape}, expected a 3D array "
            f"(station, y, z).",
            file=sys.stderr,
        )
        raise SystemExit(2)
    # One finite number per captured station, or the key is left out entirely:
    # a short axis is not a smaller axis, it is a dump whose plane count and
    # station list disagree, and guessing which is right would be a lie about
    # where every captured plane sits.
    if (
        station_x is not None
        and station_x.size == plane.shape[0]
        and bool(np.all(np.isfinite(station_x)))
    ):
        info["station_x_m"] = station_x
    if e_volume:
        if e_flat is None:
            print(
                f"[poc_app] {path} carries no 'e' edge vector: the cell-centred "
                "volume is not available from this dump.",
                file=sys.stderr,
            )
        else:
            # Imported on use, like every other emfit use in this module: the
            # CLI path (--help, --list-keys) stays stdlib + numpy only.
            from emfit.operators import edge_to_cell_centres

            ex, ey, ez = edge_to_cell_centres(
                e_flat, info["nx"], info["ny"], info["nz"])
            # ONE deliberate copy: the three components are the volume's inner
            # axis, so a reader takes e_centres[i, j, k] without gathering.
            info[VOLUME_KEY] = np.stack((ex, ey, ez), axis=-1)
    elif e_raw:
        # NO colocation here, on purpose: the stash is the vector exactly as the
        # archive stored it, plus the grid it was stored for, and the ~1 s
        # ``edge_to_cell_centres`` waits for the reader that needs it.
        if e_flat is None:
            print(
                f"[poc_app] {path} carries no 'e' edge vector: the raw edge "
                "field is not available from this dump.",
                file=sys.stderr,
            )
        else:
            info[VOLUME_RAW_KEY] = {
                "e": e_flat,
                "nx": info["nx"],
                "ny": info["ny"],
                "nz": info["nz"],
            }
    return info


# --- the wave-animation dump ------------------------------------------------
#
# Two artefacts share this viewer, and they are not versions of each other: the
# legacy dump stores ONE vector field of captured x-planes, the vis dump
# stores a SEQUENCE of them plus the geometry that produced it. The functions
# below read the second; everything above reads the first, untouched.


def _npz_scalar(data, key: str, default=float("nan")) -> float:
    """One stored 0-d value, or ``default`` when the dump does not carry it.

    A missing optional number is NOT a reason to refuse the file - the page can
    say "not recorded" for a velocity or a substrate height, and an overlay that
    is skipped is visible as a skip. It is a reason to refuse a number the
    picture cannot be drawn without, which is why the mandatory keys are
    checked separately in load_vis.
    """
    try:
        return float(data[key])
    except (KeyError, TypeError, ValueError):
        return default


def _npz_text(data, key: str):
    """One stored string, or None when the dump does not carry it."""
    try:
        return str(data[key])
    except (KeyError, TypeError, ValueError):
        return None


def _npz_int_or_none(data, key: str):
    """One stored sample INDEX, or None when the dump does not carry it.

    Not ``_npz_scalar``: a station that is not recorded must stay None all the
    way to the picture. Defaulting it would put a cut sheet at an index the dump
    never named - which is exactly what ``int(_npz_scalar(..., 0.0))`` does, and
    a state dump then reports the invented station as a measured position.
    """
    value = _npz_scalar(data, key)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return int(number)


def _vis_colour_limit(arrays, percentile: float = COLOR_PERCENTILE):
    """One |Ez| ceiling for EVERY frame, plus a flag for an all-zero cube.

    WHY one ceiling: a frame's own maximum travels with the pulse, so a clim
    taken per frame would paint the leading edge equally bright at every step and
    the decay the dump records would be invisible. The percentile (not the
    maximum) is used so one hot cell cannot flatten the rest of the picture; the
    cost is that the brightest 0.5 % of cells clip, and the page's scale label
    says so in words.

    Returns ``(0.0, ceiling, empty)``. |Ez| is a magnitude, so the floor is 0: a
    symmetric -vmax..+vmax clim would spend half the colour map on values this
    array cannot hold.
    """
    magnitudes = [
        np.abs(np.asarray(array, dtype=np.float64)).ravel() for array in arrays
    ]
    magnitudes = [flat for flat in magnitudes if flat.size]
    if not magnitudes:
        return 0.0, 1.0, True
    ceiling = float(np.percentile(np.concatenate(magnitudes), percentile))
    if not np.isfinite(ceiling) or ceiling <= 0.0:
        # An all-zero (or non-finite) cube has no scale of its own. 1.0 keeps a
        # degenerate range away from VTK, and the flag says why the page shows
        # an empty picture rather than an average-looking one.
        return 0.0, 1.0, True
    return 0.0, ceiling, False


def _is_vis(info: dict) -> bool:
    """True when ``info`` came from load_vis, not from load_dump."""
    # "format" is a serialized poc-state value, i.e. data rather than an
    # identifier, and VIS_FORMATS is the whole set the dumps on disk spell.
    return info.get("format") in VIS_FORMATS


def _frame_span_max(nt, nt_x, mode: str):
    """The LAST frame index of ``mode``'s own family, or None with no timeline.

    The two clocks are different lengths - ``nt`` counts ez_ycut, ``nt_x`` each
    of the x-cut sheets - so the range handed to the scrubber is always the
    selected family's own, never the other one's. Both counts are None on a page
    that claims no timeline (a bare field dump records no frame axis), and there
    the range is ABSENT: None is "no timeline", never "0 frames".
    """
    frames = nt if mode == "ycut" else nt_x
    return None if frames is None else int(frames) - 1


def _load_series_block(data, path: Path):
    """The load's own V(t)/I(t) trace as ONE state block, or ``(None, reason)``.

    WHY a block beside a sibling reason rather than four loose keys: that is
    precisely how this page already carries its per-port wave data
    (``port_waves`` beside ``port_waves_reason``), and a null is the only honest
    value for "no trace was taken" - a zero-filled, or zero-length-but-present,
    series would be a picture of a measurement nobody made.

    TWO absences, one answer, two sentences. A dump written before the solver
    recorded a trace carries none of these keys at all; a run that took no trace
    stores ``load_trace_present`` 0 with three EMPTY arrays (empty on purpose,
    so "no trace" cannot be read as "a trace that was all zero"). Both come back
    as ``None`` plus the reason saying WHICH of the two this is, because "the
    dump predates the feature" and "this run skipped the probe" are different
    facts and only the second one is about the run on screen.

    Never raises: this loader runs on page load for every artefact the server can
    see, so a malformed key costs this one panel and nothing else.
    """
    name = Path(path).name if path is not None else "the dump"
    try:
        names = set(data.files)
    except Exception as exc:  # noqa: BLE001 - unreadable/closed handle
        return None, f"{name}: its key list could not be read ({exc})"
    trace_keys = ("load_t_ns", "load_v", "load_i")
    if "load_trace_present" not in names and not any(k in names for k in trace_keys):
        return None, (
            f"{name} records no load trace at all - it was written before the "
            "solver started storing one"
        )
    try:
        present = int(_npz_scalar(data, "load_trace_present", 0.0))
    except (TypeError, ValueError, OverflowError):
        present = 0
    if present != 1:
        return None, f"no load trace was taken for this run ({name} says so)"
    series = {}
    for key in trace_keys:
        if key not in names:
            return None, f"{name} records a load trace but carries no {key}"
        try:
            values = np.asarray(data[key], dtype=float).ravel()
        except Exception as exc:  # noqa: BLE001 - wrong dtype or shape
            return None, f"{name}: {key} is not a numeric series ({exc})"
        if values.size == 0:
            return None, f"{name}: {key} is empty although a trace is recorded"
        if not np.all(np.isfinite(values)):
            return None, f"{name}: {key} holds non-finite samples"
        series[key] = [float(value) for value in values]
    count = len(series["load_t_ns"])
    for key in ("load_v", "load_i"):
        if len(series[key]) != count:
            return None, (
                f"{name}: {key} holds {len(series[key])} samples but load_t_ns "
                f"holds {count}; refusing to truncate to the shorter array"
            )
    # The netlist text is carried VERBATIM as well as parsed for its name: the
    # figure names the circuit when the document parses, and falls back to the
    # raw text when it does not, so a trace can never be drawn anonymously.
    netlist_json = _npz_text(data, "load_netlist_json") or ""
    netlist_name = None
    if netlist_json.strip():
        try:
            document = json.loads(netlist_json)
        except Exception:  # noqa: BLE001 - the raw text is still shown
            document = None
        if isinstance(document, dict):
            recorded = document.get("name")
            if isinstance(recorded, str) and recorded.strip():
                netlist_name = recorded.strip()
    return {
        "file": str(path),
        "n": count,
        "load_t_ns": series["load_t_ns"],
        "load_v": series["load_v"],
        "load_i": series["load_i"],
        "load_netlist_json": netlist_json,
        "netlist_name": netlist_name,
        # The terminated resistance as recorded. Carried so the figure can say
        # WHICH element these series belong to - an unlabelled V/I trace beside
        # the series_r artefact's 50 ohm record would be read as that resistor's.
        "load_ohm": _npz_scalar(data, "load_ohm"),
    }, None


def load_vis(path: Path) -> dict:
    """Load an ``emfit.vis/2`` animation dump. numpy only, no pyvista.

    Three planes are stored and they are NOT interchangeable: ``ez_ycut`` is an
    x-z sheet at one fixed y (``nt`` frames), while the two x-cuts are y-z sheets
    at two fixed x (``nt_x`` frames, written every ``dump_stride * 10`` steps).
    That asymmetry is why the time of a frame is rebuilt from that plane's own
    ``frame_index`` array below instead of from a shared counter: indexing an
    x-cut frame number into ``t_ns`` would read an instant up to ten times too
    early and never raise.

    Everything the page prints about time, position or scale is read here, so a
    missing or inconsistent axis fails with the key's own name instead of
    becoming a wrong picture later.
    """
    if not path.is_file():
        print(f"[poc_app] input not found: {path}", file=sys.stderr)
        raise SystemExit(2)

    mandatory = (
        "ez_ycut",
        "ez_xcut_near",
        "ez_xcut_far",
        "t_ns",
        "frame_index",
        "frame_index_xcut",
        "x_mm",
        "y_mm",
        "z_mm",
        "nx",
        "ny",
        "nz",
        "nt",
        "nt_x",
        "dt_s",
        "cell_m",
    )
    with np.load(path) as data:
        names = set(data.files)
        schema = str(data["schema"]) if "schema" in names else ""
        if schema not in VIS_SCHEMAS:
            print(
                f"[poc_app] {path} declares schema {schema or 'none'!r}; this "
                f"loader reads {', '.join(repr(s) for s in VIS_SCHEMAS)}.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        absent = [key for key in mandatory if key not in names]
        if absent:
            print(
                f"[poc_app] {path} declares {schema} but is missing "
                f"{', '.join(absent)}.",
                file=sys.stderr,
            )
            raise SystemExit(2)

        info = {
            "path": path,
            "format": VIS_FORMAT,
            "schema": schema,
            "engine": _npz_text(data, "engine"),
            "created_utc": _npz_text(data, "created_utc"),
            # Provenance: which arm produced this file and what it was
            # terminated in. Absent from a version-1 dump, and absent means
            # "not recorded" - the readout says so rather than guessing from
            # the geometry, which two arms can share.
            "structure_id": _npz_text(data, "structure_id"),
            "load_ohm": _npz_scalar(data, "load_ohm"),
            "ez_ycut": np.asarray(data["ez_ycut"]),
            "ez_xcut_near": np.asarray(data["ez_xcut_near"]),
            "ez_xcut_far": np.asarray(data["ez_xcut_far"]),
            "t_ns": np.asarray(data["t_ns"], dtype=float),
            "frame_index": np.asarray(data["frame_index"], dtype=int),
            "frame_index_xcut": np.asarray(data["frame_index_xcut"], dtype=int),
            "x_mm": np.asarray(data["x_mm"], dtype=float),
            "y_mm": np.asarray(data["y_mm"], dtype=float),
            "z_mm": np.asarray(data["z_mm"], dtype=float),
            "nx": int(data["nx"]),
            "ny": int(data["ny"]),
            "nz": int(data["nz"]),
            "nt": int(data["nt"]),
            "nt_x": int(data["nt_x"]),
            "dt_s": float(data["dt_s"]),
            "cell_m": float(data["cell_m"]),
            # Geometry the overlays draw. Recorded values only - a NaN here is
            # drawn as nothing and printed as "not recorded", never invented.
            # j_cut is the y SAMPLE INDEX the x-z sheet was taken from, so an
            # absent one is None: nothing may stand in for it.
            "j_cut": _npz_int_or_none(data, "j_cut"),
            "dump_stride": int(_npz_scalar(data, "dump_stride", 1.0)),
            "nstep": int(_npz_scalar(data, "nsteps", 0.0)),
            "f_ref_hz": _npz_scalar(data, "f_ref_hz"),
            "f_pulse_hz": _npz_scalar(data, "f_pulse_hz"),
            "xcut_near_mm": _npz_scalar(data, "xcut_near_mm"),
            "xcut_far_mm": _npz_scalar(data, "xcut_far_mm"),
            "port_x_mm": _npz_scalar(data, "port_x_mm"),
            "load_x_mm": _npz_scalar(data, "load_x_mm"),
            "substrate_h_mm": _npz_scalar(data, "substrate_h_mm"),
            "strip_w_mm": _npz_scalar(data, "strip_w_mm"),
            "eps_r": _npz_scalar(data, "eps_r"),
            "v_analytic_m_s": _npz_scalar(data, "v_analytic_m_s"),
            "v_measured_m_s": _npz_scalar(data, "v_measured_m_s"),
            "t_traverse_ns": _npz_scalar(data, "t_traverse_ns"),
            # The dump marks its own windowed fit good or bad; the page repeats
            # that verdict instead of re-deciding it.
            "v_measured_reliable": bool(_npz_scalar(data, "v_measured_reliable", 0.0)),
            "velocity_note": _npz_text(data, "velocity_note"),
        }
        # The optional ``|E|`` volume, and the normal answer is that there is
        # none: only a run asked for with ``--volume-stride`` writes one, and
        # then it writes all three keys together. Absent reads as three Nones
        # rather than zeros so "this dump carries no volume" cannot be
        # mistaken for "this dump carries a volume of zeroes", and a file with
        # only one of the pair is treated as carrying none: half a volume says
        # nothing about which steps its frames are.
        info["e_abs_volume"] = None
        info["e_abs_volume_step_index"] = None
        info["e_abs_volume_stride"] = None
        if "e_abs_volume" in names and "e_abs_volume_step_index" in names:
            info["e_abs_volume"] = np.asarray(
                data["e_abs_volume"], dtype=np.float32)
            info["e_abs_volume_step_index"] = np.asarray(
                data["e_abs_volume_step_index"], dtype=int)
            info["e_abs_volume_stride"] = int(
                _npz_scalar(data, "e_abs_volume_stride", 1.0))
        # The load's own probe trace, and what terminated it. Handed to the page
        # as one block beside its own reason (see _load_series_block), so that
        # "this dump predates the trace", "this run took no trace" and "here is
        # the trace" are three distinguishable states and none of them is zeros.
        # Array values leave here as plain Python lists: the page document is
        # JSON-serialised for the browser, and a numpy array must not reach it.
        info["load_series"], info["load_series_reason"] = _load_series_block(
            data, path
        )

    problems = []
    ycut, near, far = info["ez_ycut"], info["ez_xcut_near"], info["ez_xcut_far"]
    for label, array in (("ez_ycut", ycut), ("ez_xcut_near", near), ("ez_xcut_far", far)):
        if array.ndim != 3:
            problems.append(f"{label} is {array.ndim}D, expected a 3D array")
    if not problems:
        if ycut.shape != (info["nt"], info["nx"], info["nz"]):
            problems.append(
                f"ez_ycut has shape {ycut.shape}, expected (nt, nx, nz) = "
                f"({info['nt']}, {info['nx']}, {info['nz']})"
            )
        if near.shape != far.shape:
            problems.append(
                f"ez_xcut_near {near.shape} and ez_xcut_far {far.shape} differ; "
                "the two x-cuts are shown side by side and must share a grid"
            )
        elif near.shape != (info["nt_x"], info["ny"], info["nz"]):
            problems.append(
                f"ez_xcut_near has shape {near.shape}, expected (nt_x, ny, nz) = "
                f"({info['nt_x']}, {info['ny']}, {info['nz']})"
            )
        for key, size, expected in (
            ("t_ns", info["t_ns"].size, info["nt"]),
            ("frame_index", info["frame_index"].size, info["nt"]),
            ("frame_index_xcut", info["frame_index_xcut"].size, info["nt_x"]),
            ("x_mm", info["x_mm"].size, info["nx"]),
            ("y_mm", info["y_mm"].size, info["ny"]),
            ("z_mm", info["z_mm"].size, info["nz"]),
        ):
            if size != expected:
                problems.append(f"{key} has {size} entries, expected {expected}")
        # The volume is checked exactly where the planes are, and against the
        # file's own nx/ny/nz: it is drawn on the same node grid as ez_ycut, so
        # a volume whose last three axes disagree with it would be plotted at
        # the wrong mm per voxel rather than refused.
        vol = info["e_abs_volume"]
        if vol is not None:
            steps = info["e_abs_volume_step_index"]
            if vol.ndim != 4:
                problems.append(
                    f"e_abs_volume is {vol.ndim}D, expected a 4D array "
                    "(n, nx, ny, nz)"
                )
            elif vol.shape[1:] != (info["nx"], info["ny"], info["nz"]):
                problems.append(
                    f"e_abs_volume has shape {vol.shape}, expected "
                    f"(n, nx, ny, nz) = (n, {info['nx']}, {info['ny']}, "
                    f"{info['nz']})"
                )
            if vol.ndim == 4 and steps.size != vol.shape[0]:
                problems.append(
                    f"e_abs_volume has {vol.shape[0]} frames but "
                    f"e_abs_volume_step_index has {steps.size} entries; the "
                    "volume's frames and its step axis are one record and "
                    "cannot be read at two lengths"
                )
    if problems:
        for problem in problems:
            print(f"[poc_app] {path}: {problem}", file=sys.stderr)
        raise SystemExit(2)

    # Computed once, here, from every stored frame of every plane: the viewer
    # then has no way to rescale between frames because it is never given a
    # per-frame number to rescale with.
    vmin, vmax, empty = _vis_colour_limit((ycut, near, far))
    info["color_range"] = (vmin, vmax)
    info["color_range_empty"] = empty
    return info


def load_any_dump(path: Path) -> dict:
    """Open either artefact. Dispatch on the npz ``schema`` key, nothing else.

    A legacy dump carries no ``schema`` key at all, so "has a schema and it is
    not ours" is a REFUSAL rather than a fallback: a future dump format must not
    be read by this loader's shape expectations just because the filename looked
    familiar.

    A HUYGENS SURFACE DUMP is the same rule taken one step further.  It is
    handed to the reader built for it, ``emfit.ntff.load_surface_dump``, which
    validates every key and names the one that fails - and then this loader
    refuses it BY NAME, because nothing in this viewer draws surface currents:
    it is never passed to ``load_dump``, whose shape expectations are a plane
    dump's (before this dispatch existed such a file died on the missing
    ``plane_ez``), and the validated ``SurfaceDump`` is not RETURNED either:
    ``reload_page`` reads ``info.get`` and ``_plane_layout`` reads plane keys, so
    returning one would trade a named refusal for an AttributeError two frames
    down.
    """
    schema = ""
    names: tuple = ()
    if path.is_file():
        with np.load(path) as data:
            names = tuple(data.files)
            if "schema" in data.files:
                schema = str(data["schema"])
    if schema in VIS_SCHEMAS:
        return load_vis(path)
    # The discriminator on anything written since it existed, OR - for an
    # archive that predates it - this key SIGNATURE: every key
    # ``load_surface_dump`` demands is present and the plane dump's own
    # ``plane_ez`` is ABSENT.  Both halves are load-bearing.  The eighteen keys
    # are what make it a predicate rather than a guess about a filename (no
    # plane dump carries ``colocation_rule``, ``normals`` or ``dA``), and
    # ``plane_ez`` is what keeps this from claiming a plain dump if a future
    # format ever grows those keys.  The list is IMPORTED from emfit.ntff, not
    # re-typed here, so the eighteen strings have one home; it is imported here
    # rather than at module scope because this module is stdlib + numpy only at
    # import time.
    from emfit.ntff import SURFACE_DUMP_KEYS, SURFACE_DUMP_SCHEMA, load_surface_dump

    legacy_surface_signature = (
        not schema and PLANE_KEY not in names and set(SURFACE_DUMP_KEYS) <= set(names)
    )
    if schema == SURFACE_DUMP_SCHEMA or legacy_surface_signature:
        try:
            load_surface_dump(path)
        except ValueError as exc:
            print(
                f"[poc_app] {path} carries the Huygens surface dump's keys but "
                f"is not a readable one: {exc}",
                file=sys.stderr,
            )
            raise SystemExit(2)
        print(
            f"[poc_app] {path} is a Huygens surface dump (schema "
            f"{SURFACE_DUMP_SCHEMA!r}), not a field plane: it is read by "
            "emfit.ntff.load_surface_dump, which validates it, and this viewer "
            "has no surface-current renderer - it draws plane dumps and "
            "wavedude animations only.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if schema:
        print(
            f"[poc_app] {path} declares schema {schema!r}, which this viewer does "
            "not read; it reads "
            f"{', '.join(repr(s) for s in VIS_SCHEMAS)} or a legacy plane "
            "dump.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    # A legacy plane dump that gets this far IS what ``run_web`` serves: every
    # other schema above has already returned or exited, and a VIS dump never
    # reaches this line (it is dispatched to ``load_vis`` earlier and becomes
    # the ``run_web_vis`` page, whose live reload re-enters here with a fresh
    # path). It is NOT, however, the only load this line feeds: ``main()`` hands
    # the very same dict to ``--list-keys`` and ``--dump-state``, which never
    # look at a volume -- so an eager colocation here was paid by every legacy
    # CLI run as well as by the viewer (~0.95 s on the shipped dump).
    # Hence the STASH and not the colocation: reading ``e`` costs the array copy,
    # and the deferred ``edge_to_cell_centres`` is paid by the first reader that
    # actually draws arrows - the vectors checkbox's first tick.
    return load_dump(path, e_raw=True)


def _velocity_label(info: dict) -> str:
    """The velocity line, from the dump's OWN recorded numbers.

    A predicate over ``info`` and nothing else, so boot and a live page swap
    print the same sentence from the same code: a dump that arrives mid-session
    must not get a differently-worded readout than the one the app booted with.
    """
    measured = _finite(info.get("v_measured_m_s"))
    analytic = _finite(info.get("v_analytic_m_s"))
    traverse = _finite(info.get("t_traverse_ns"))
    reliability = (
        "reliable" if info.get("v_measured_reliable") else "NOT reliable"
    )
    return (
        "velocity: measured "
        + (
            f"{measured:.4e} m/s ({reliability})"
            if measured is not None
            else "not recorded"
        )
        + ", analytic "
        + (f"{analytic:.4e} m/s" if analytic is not None else "not recorded")
        + ", t_traverse "
        + (f"{traverse:.4f} ns" if traverse is not None else "not recorded")
    )


def _scale_label(info: dict) -> str:
    """The ONE colour-limit line, from this dump's own ``color_range``.

    Same reason as _velocity_label: the sentence names the ceiling of the dump
    now on screen, so it has to be rebuilt from that dump, not kept from boot.
    """
    color_range = info.get("color_range")
    if color_range is None:
        # A page with no timeline records no colour range either: there is no
        # frame to scale, so the line says that instead of quoting a limit.
        return "scale: not recorded - this page carries no colour range"
    if info.get("color_range_empty"):
        return (
            "scale: [EMPTY DUMP] every stored |Ez| is zero - 0 .. 1 is a "
            "placeholder and no frame has a scale of its own"
        )
    vmin, vmax = color_range
    return (
        f"scale: |Ez| {vmin:.4e} .. {vmax:.4e} V/m, ONE limit for EVERY "
        f"frame (p{COLOR_PERCENTILE:g} ceiling; the brightest "
        f"{100.0 - COLOR_PERCENTILE:g} % of cells clip)"
    )


def _structure_readout_text(info: dict) -> str:
    """One line of dump provenance: ``structure: A (50 Ω)``.

    Read from the DUMP, never from the structure registry: the registry says
    which case this page was started for, while this line says which arm the
    file in front of the reader was written by - the two stop agreeing the
    moment a dump is copied beside another case, which is exactly why the
    writer records them. Neither field can be derived from the geometry (two
    arms share a mesh), so a version-1 dump that carries neither reads as
    ``structure: unknown`` instead of being filled in from the registry.
    """
    structure_id = (info.get("structure_id") or "").strip()
    if not structure_id:
        return "structure: unknown"
    load_ohm = _finite(info.get("load_ohm"))
    if load_ohm is None:
        return f"structure: {structure_id}"
    return f"structure: {structure_id} ({load_ohm:g} Ω)"


def _page_source_text(info: dict, nt=None) -> str:
    """One line naming the FILE this page is showing, and what kind of page it is.

    The question it answers is the one every other readout here leaves open: the
    labels say which ARM and which COLOUR LIMIT are on screen, never which
    artefact they came off - and a page opened from a copy of a dump, or from a
    dump a solve has since replaced on disk, looks identical to one opened from
    the original. ``info["path"]`` is the file the page was actually loaded
    from, so it is the only thing that can answer it.

    The KIND is part of the same sentence because the file name alone does not
    say it: a static field snapshot has no frame axis at all (``nt`` is None,
    server/um3k_panels.py:127-140), while an animation dump carries ``nt`` frames
    along ``ez_ycut``. The station count comes from the plane stack's own shape
    and is 0 on a page that has none - reported as such, never guessed.

    Pure over its arguments, like _structure_readout_text and _scale_label, so
    boot and a live page swap print the same sentence from the same code.
    """
    try:
        name = Path(info.get("path")).name
    except (TypeError, ValueError):
        # No path, or a path object that will not stringify: the page was built
        # from an in-memory dump, which is a state this shell allows.
        name = ""
    if not name:
        return "showing: not recorded - no dump is loaded on this page"
    if nt is None:
        try:
            n_st = int(info[PLANE_KEY].shape[0])
        except (KeyError, IndexError, TypeError, AttributeError):
            # A dump with no plane stack carries no station axis at all; the
            # count is then 0 and the line says so instead of quoting one.
            n_st = 0
        if n_st <= 0:
            count = "no stations"
        elif n_st == 1:
            count = "1 station"
        else:
            count = f"{n_st} stations"
        return f"showing {name} - static field snapshot, {count}, no timeline"
    return f"showing {name} - animation, {int(nt)} frames on ez_ycut"


def _cell_mm(info: dict) -> float:
    return float(info["cell_m"]) * 1e3


def _station_text(idx: int, cell_mm: float, n_st: int, stations_mm=None) -> str:
    """Corner label for one captured station.

    ``stations_mm`` is the recorded station axis when the caller has resolved
    one (``_station_axis_mm``): then the x printed is that station's OWN x. A
    caller without it keeps the old ``idx * cell`` reading byte for byte, which
    is what a hand-built info or a page that never resolved the axis prints.
    """
    if stations_mm is None:
        x_mm = idx * cell_mm
    else:
        x_mm = float(stations_mm[max(0, min(len(stations_mm) - 1, int(idx)))])
    return f"station {idx + 1}/{n_st}   x = {x_mm:.4f} mm"


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
    """Candidate record paths for a dump, best first. NEVER raises.

    The dump and its record do not always share a stem exactly, and two naming
    conventions are on disk. The shipped field dump is
    ``..._ghostwave_fields.npz`` while the study that produced it wrote
    ``..._ghostwave.json`` (the ``_fields`` suffix is dropped). The viewer's own
    animation dumps follow a second convention: ``vis_dump_<case>.npz`` is the
    dump, ``vis_run_<case>.json`` is the record written by the run - ``dump`` in
    one stem, ``run`` in the other, same case. Every such spelling is tried
    instead of guessing one and silently reporting "no record".

    The multi-frequency summary is a THIRD artefact with a third spelling,
    ``<run-stem>_multifreq_summary.json``, appended after the single-run
    records for a reason: a record that describes THIS dump must outrank a sweep
    that merely shares its case name.

    The sibling glob is LAST, and it is the only candidate that is a guess: it
    matches a ``*_multifreq_summary.json`` in the dump's own directory whose
    name carries the same run key, which is a naming convention rather than a
    promise that the file describes this dump. Being last (and one directory
    listing rather than a search) is what keeps a name-matching summary from
    ever outranking an exact spelling.

    Total by construction: a missing parent directory, an unresolvable path or a
    bad type costs the candidates that could not be built, never the caller -
    ``load_record`` and ``_mode_view`` both treat this list as advisory.

    ``npz_path`` is coerced for the same reason ``_multifreq_candidates``
    coerces it: the caller passes ``info["path"]``, which is a ``str`` off disk
    / out of trame.  Read as a str, ``.with_suffix`` raised
    ``'str' object has no attribute 'with_suffix'`` and took the whole panel
    down with it.
    """
    candidates: list[Path] = []
    try:
        npz = Path(npz_path)
        candidates.append(npz.with_suffix(".json"))
        stem = npz.stem
        stripped = stem
        for suffix in ("_fields", "_planes", "_dump"):
            if stem.endswith(suffix):
                stripped = stem[: -len(suffix)]
                candidates.append(npz.with_name(stripped + ".json"))
                break
        # dump -> run, FIRST occurrence only: the convention is
        # ``vis_dump_<case>`` -> ``vis_run_<case>``, i.e. the prefix changes and
        # the case is untouched. Replacing every "dump" in the stem would also
        # rewrite a case whose own name happens to contain the word.
        run_stem = stripped.replace("dump", "run", 1)
        if run_stem != stripped:
            candidates.append(npz.with_name(run_stem + ".json"))
        candidates.append(npz.with_name(run_stem + "_multifreq_summary.json"))
        # The run key is what identifies this run inside a summary's name:
        # ``vis_run_B_100ohm`` -> ``B_100ohm``. A stem with no "run_" (a build
        # dump) keeps its whole stem, which simply will not match anything.
        run_key = (
            run_stem.rsplit("run_", 1)[-1] if "run_" in run_stem else run_stem
        )
        seen = set()
        for path in candidates:
            try:
                seen.add(path.resolve())
            except Exception:  # noqa: BLE001 - a path that will not resolve
                pass
        siblings: list[Path] = []
        if run_key:
            pattern = re.compile(r"(^|_)" + re.escape(run_key) + r"(_|\.|$)")
            try:
                siblings = sorted(npz.parent.glob("*_multifreq_summary.json"))
            except Exception as exc:  # noqa: BLE001 - a bad parent is not fatal
                print(
                    f"[poc_app] record scan skipped in {npz.parent}: {exc}",
                    file=sys.stderr,
                )
        for sibling in siblings:
            if not pattern.search(sibling.name):
                continue
            try:
                resolved = sibling.resolve()
            except Exception:  # noqa: BLE001 - compare what we can
                resolved = sibling
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(sibling)
    except Exception as exc:  # noqa: BLE001 - an advisory list, never a raise
        print(
            f"[poc_app] record candidates incomplete for {npz_path}: {exc}",
            file=sys.stderr,
        )
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


def _structure_key(structure_id):
    """The arm key for a structure id, or None when no arm was recorded.

    None is a REAL answer here, not a default: it means the caller named no arm,
    and every lookup that takes this key must then find nothing. Substituting
    another arm's artefact for it is the one thing this panel may not do.
    """
    if structure_id is None:
        return None
    return str(structure_id).strip().upper() or None


def _multifreq_candidates(npz_path: Path, structure_id=None) -> list[Path]:
    """Candidate multi-frequency summary paths for a dump, best first.

    ``npz_path`` is coerced ONCE, here, because every caller in this module
    passes a ``str``: ``load_multifreq(info["path"], ...)`` and
    ``_page_multifreq(...)`` both hand over a path that came out of JSON / a
    trame value, not a ``Path``.  While this read ``npz_path.parent`` directly
    the beside-dump glob raised ``'str' object has no attribute 'parent'``,
    the message did not name a directory, and the silently-swallowed failure
    meant the scan NEVER ran: every press fell through to the registry entry.
    The scan is the fix; the complaint was only ever a symptom.
    """
    scanned = Path(npz_path).parent
    sid = _structure_key(structure_id)
    beside: list[Path] = []
    try:
        beside = sorted(scanned.glob("*multifreq*summary*.json"))
    except Exception as exc:  # noqa: BLE001 - a bad parent dir is not fatal
        print(f"[poc_app] sweep scan skipped in {scanned}: {exc}", file=sys.stderr)
    # By ARM before ordering. BOTH arms' summaries can sit beside one dump, and
    # ``sorted`` would then hand a B dump A's sweep purely because "A" sorts
    # first - correctness decided by a filename's first letter. A candidate
    # whose name does not carry THIS structure's arm is not this dump's sweep; a
    # candidate list with no arm recorded cannot be matched at all, so it is
    # dropped rather than guessed at - the registry fallback below handles that
    # case, and it is the only thing that may.
    candidates: list[Path] = [p for p in beside if sid and f"_{sid}_" in p.name]
    # BY STRUCTURE, not by one constant: the fallback is the sweep registered for
    # THIS arm. An absent or unregistered id adds nothing - see _structure_key -
    # so the arm-filtered scan above is the only remaining source for it.
    default = MULTIFREQ_BY_STRUCTURE.get(sid)
    if default:
        fallback = _resolve(default)
        # Compared RESOLVED: the scan yields paths spelled the way the caller
        # spelled its dump (relative, when info["path"] is relative) while
        # ``_resolve`` yields absolute ones, so ``Path(...) != Path(...)`` for
        # the same file. Only the dedupe changes - the ORDER contract stands:
        # beside-the-dump first, registry fallback last.
        if fallback.resolve() not in {c.resolve() for c in candidates}:
            candidates.append(fallback)
    return candidates


def _absent_multifreq_reason(arm, npz_path) -> str:
    """WHY this arm has no sweep, in the page's own words. Never empty.

    It exists because ``MULTIFREQ_BY_STRUCTURE`` is a LITERAL map that knows two
    arms while the SETUP picker offers every arm the solver has: selecting an
    arm the map does not name (D, whose termination is a netlist) left the
    panels with ``load_multifreq -> None`` and a caption that listed lookups
    without ever saying the missing thing was a REGISTRY entry, not a file.
    "None" is a real answer, and this is its sentence: the arm exists, the sweep
    for it does not exist YET, and the reader is told which of the two is
    missing.

    The three cases are kept apart because they need different actions - write
    the sweep and register it, re-run the sweep, or fix the file - and one
    message for all three (the old "no S-parameter data") named none of them.
    """
    registered = MULTIFREQ_BY_STRUCTURE.get(arm)
    single = SINGLE_RUN_BY_STRUCTURE.get(arm)
    looked = f"*multifreq*summary*.json beside {Path(npz_path)}"
    if registered:
        looked += f", {registered}"
    if single:
        looked += f", {single}"
    if not arm:
        # The NO-PROVENANCE case says why nothing can be chosen, not merely that
        # nothing was: with no arm the beside-dump scan does not run at all
        # (_multifreq_candidates filters on the arm), so "no summary can be
        # chosen" alone sends a reader looking for a missing FILE when the files
        # may well be sitting there and the missing thing is the provenance that
        # says which of them is this dump's.
        head = (
            "no structure arm is recorded for this dump, so no multi-frequency "
            "summary can be chosen for it - without an arm there is no way to "
            "tell which sweep is this dump's"
        )
    elif not registered:
        head = (
            f"no multi-frequency summary is registered for arm {arm} yet - the "
            "picker offers the arm because the SOLVER has it, and its sweep is "
            "a separate artefact that has not been written"
        )
    else:
        head = (
            f"the multi-frequency summary registered for arm {arm} "
            f"({registered}) could not be read"
        )
    return f"{head}; looked for {looked}"


# --- the structure registry ------------------------------------------------
#
# WHY a registry file: the viewer used to know ONE artefact path, typed in as a
# constant, and every number on the page inherited that assumption. The page now
# names the CASE it is showing, and reads which artefacts belong to that case
# from structures.json at the repo root. An entry exists there only where an
# artefact exists on disk; a case with no dump is listed as "record only" and
# cannot be opened, rather than being opened onto a different case's numbers.
#
# Every read in this section is stdlib + numpy: --dump-state and --list-keys
# must never need trame, pyvista or matplotlib.


def _read_json(path):
    """Read a JSON object from ``path``; None (plus a stderr note) on failure."""
    try:
        with Path(path).open(encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001 - optional input, never fatal
        print(f"[poc_app] {path} unreadable: {exc}", file=sys.stderr)
        return None
    if not isinstance(data, dict):
        print(f"[poc_app] {path} is not a JSON object; ignoring it", file=sys.stderr)
        return None
    return data


def _as_int(value):
    """int() or None, never raising. Used on optional integer record keys."""
    number = _as_float(value)
    return None if number is None else int(number)


def _cells_string(nx, ny, nz) -> str:
    return f"{nx}x{ny}x{nz}"


def _parse_cells(text):
    """'62x212x22' -> {'nx': 62, 'ny': 212, 'nz': 22}; None when unparseable.

    None, never a guess: a cell count that cannot be read is REPORTED as
    missing, because a default here would silently relabel one grid as another -
    which is exactly the confusion the mismatch check exists to catch.
    """
    if not isinstance(text, str):
        return None
    parts = text.strip().lower().split("x")
    if len(parts) != 3:
        return None
    try:
        nx, ny, nz = (int(part) for part in parts)
    except ValueError:
        return None
    return {"nx": nx, "ny": ny, "nz": nz}


def _cells_as_text(cells):
    """{'nx': 62, 'ny': 212, 'nz': 22} -> '62x212x22'; None when incomplete."""
    if not isinstance(cells, dict):
        return None
    nx, ny, nz = cells.get("nx"), cells.get("ny"), cells.get("nz")
    if nx is None or ny is None or nz is None:
        return None
    return _cells_string(nx, ny, nz)


_CELLS_IN_LINE = re.compile(r"cells\s*=\s*(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+)")


def _cells_from_summary(summary_line):
    """Cell counts out of a record's summary_line, e.g. 'cells=72x212x22'.

    This is the ONLY source of the S-parameter cell count: the number is read
    from the record that produced it and never inferred from the field dump
    beside it - those two are exactly what the mismatch check compares.
    """
    if not isinstance(summary_line, str):
        return None
    match = _CELLS_IN_LINE.search(summary_line)
    if match is None:
        return None
    return _parse_cells("x".join(match.groups()))


def _n_line(record):
    """The run's n_line as recorded (run.kwargs.n_line, then geometry.n_line)."""
    if not isinstance(record, dict):
        return None
    run = record.get("run")
    if isinstance(run, dict):
        kwargs = run.get("kwargs")
        if isinstance(kwargs, dict):
            value = _as_int(kwargs.get("n_line"))
            if value is not None:
                return value
    geom = record.get("geometry")
    if isinstance(geom, dict):
        value = _as_int(geom.get("n_line"))
        if value is not None:
            return value
    return None


def _run_letter(structure, key):
    """The run label ('A', 'B') out of an entry's '<field_dump|sparams>.run'."""
    block = structure.get(key) if isinstance(structure, dict) else None
    if not isinstance(block, dict):
        return None
    text = block.get("run")
    if not isinstance(text, str):
        return None
    words = text.split()
    head = words[0].rstrip(",") if words else ""
    return head or None


def _structure_registry() -> dict:
    """The SOLVE arms, read from the solver that dispatches on them. {} if not.

    The Project picker in the SETUP column used to be bound to
    ``MULTIFREQ_BY_STRUCTURE`` - a literal map in THIS file naming A and B - so
    adding an arm over there (a ``STRUCTURES`` row, its netlist, its default
    artefact) left the panel still offering two arms, with no line in either
    file saying the two lists had drifted.  This is that missing line: the
    items are the keys of the dict the solver itself dispatches on.

    Loaded by PATH because the solver is not a module: it lives in
    ``evidence/termination`` because it is evidence, not because it is a
    package.  Importing it is safe and cheap - every one of its module-level
    imports is stdlib and all its work (argument parsing, the mesh, the solve)
    sits behind ``main()`` under an ``if __name__`` guard - so this costs one
    parse of a source file per page render and executes nothing.

    ANY failure returns ``{}``, never an exception: a panel that cannot read
    the arm list must still render (the caller falls back to the two arms it
    can name itself), and losing the whole SETUP column over a caption would be
    a far worse trade than showing a stale list.
    """
    import importlib.util

    path = REPO_ROOT / "evidence" / "termination" / "run_build_A.py"
    try:
        spec = importlib.util.spec_from_file_location("_poc_solver_arms", path)
        if spec is None or spec.loader is None:
            return {}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return {}
    structures = getattr(module, "STRUCTURES", None)
    return dict(structures) if isinstance(structures, dict) else {}


def load_structures() -> list:
    """Every usable entry of structures.json, in file order. [] when unreadable."""
    data = _read_json(REPO_ROOT / STRUCTURES_FILE)
    if not isinstance(data, dict):
        return []
    entries = data.get("structures")
    if not isinstance(entries, list):
        print(f"[poc_app] {STRUCTURES_FILE} has no structures list", file=sys.stderr)
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _structure_by_id(structure_id, structures=None):
    """The entry with this id, or None. Never invents one."""
    for entry in load_structures() if structures is None else structures:
        if entry.get("id") == structure_id:
            return entry
    return None


def _structure_label(structure) -> str:
    """The entry's human label, with the id (then the default) as fallbacks."""
    if not isinstance(structure, dict):
        return DEFAULT_STRUCTURE
    label = structure.get("label")
    if isinstance(label, str) and label:
        return label
    sid = structure.get("id")
    return sid if isinstance(sid, str) and sid else DEFAULT_STRUCTURE


def _structure_dump_path(structure):
    """The entry's npz path as written in the registry, or None."""
    block = structure.get("field_dump") if isinstance(structure, dict) else None
    path = block.get("path") if isinstance(block, dict) else None
    return path if isinstance(path, str) and path else None


def _structure_is_record_only(structure) -> bool:
    """True when this entry's field dump is not on disk, so the case cannot open.

    Decided by looking for the FILE this entry names, never by a hand-maintained
    boolean in the registry: an entry is renderable exactly while its npz is
    there, so a moved or deleted dump demotes it to record-only instead of
    quietly serving another case's field data under this one's name.
    """
    return _structure_artifact_path(structure, "field_dump") is None


def _renderable_structure_ids(structures) -> list:
    """The ids that can actually be opened: those with a field dump on disk."""
    return [
        str(entry.get("id"))
        for entry in structures
        if entry.get("id") and not _structure_is_record_only(entry)
    ]


def _record_only_refusal(requested_id, structures) -> str:
    """The refusal for an entry with no dump: name it, say why, name what works."""
    renderable = ", ".join(_renderable_structure_ids(structures))
    return (
        f"--structure {requested_id} is record only: this registry entry has "
        f"S-parameters recorded but no field dump on disk, so there is no field "
        f"data to show for it, and this viewer will not substitute a different "
        f"structure's; renderable structures: {renderable or 'none'}"
    )


def _structure_input_path(explicit, structure) -> Path:
    """Resolve the npz: --input when given, else the entry's dump, else default.

    An explicit --input wins over the registry, so a dump outside every entry (a
    new run, not yet registered) can still be opened and inspected.
    """
    if explicit:
        return _resolve(explicit)
    path = _structure_dump_path(structure)
    if path:
        return _resolve(path)
    return _resolve(DEFAULT_INPUT)


def _structure_option_label(structure) -> str:
    """Picker text for one entry: cells and run letters BEFORE it is opened.

    The label is the only place the mismatch can be shown before a case is
    opened, so it carries both cell counts and both run letters.
    """
    label = _structure_label(structure)
    # Decided by whether the npz is ON DISK, not by the registry string: an entry
    # whose dump was moved or deleted is record-only here, exactly as the CLI's
    # own refusal decides it - one rule for the picker and the command line.
    if _structure_is_record_only(structure):
        return f"{label} - record only, no field dump"
    parts = []
    field_block = structure.get("field_dump")
    field_cells = field_block.get("cells")
    field_run = _run_letter(structure, "field_dump")
    if field_cells:
        parts.append(
            f"field {field_cells}" + (f" (run {field_run})" if field_run else "")
        )
    sparams = structure.get("sparams")
    if isinstance(sparams, dict) and sparams.get("cells"):
        sparams_run = _run_letter(structure, "sparams")
        parts.append(
            f"S-params {sparams['cells']}"
            + (f" (run {sparams_run})" if sparams_run else "")
        )
    if not parts:
        return label
    return f"{label} [" + " | ".join(parts) + "]"


def _structure_options(structures=None) -> list:
    """Picker items: disabled EXACTLY where the entry has no field dump."""
    items = []
    for entry in load_structures() if structures is None else structures:
        sid = entry.get("id")
        if not isinstance(sid, str):
            continue
        item = {"title": _structure_option_label(entry), "value": sid}
        if _structure_is_record_only(entry):
            item["props"] = {"disabled": True}
        items.append(item)
    return items


def _git_head_short():
    """The commit HEAD points at, read with pathlib only - no subprocess.

    A branch ref is followed into .git/<ref>; when that file is absent the ref is
    looked up in .git/packed-refs, where a cloned or gc'd repo keeps it. Anything
    unreadable - no .git, an odd ref name, a corrupt file - is null: the state
    dump says "not knowable here" instead of guessing a commit.
    """
    git_dir = REPO_ROOT / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001 - no repo, no commit
        return None
    if not head:
        return None
    if not head.startswith("ref:"):
        # Detached HEAD: the file holds the commit itself.
        return head[:7]
    ref = head[4:].strip()
    if not ref:
        return None
    value = None
    try:
        value = (git_dir / ref).read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001 - packed refs are the other place
        value = None
    if not value:
        try:
            packed = (git_dir / "packed-refs").read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001 - nothing else to try
            return None
        for line in packed.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            fields = line.split(None, 1)
            if len(fields) == 2 and fields[1] == ref:
                value = fields[0]
                break
    if not value:
        return None
    return value[:7]


def _field_record(npz_path: Path):
    """The study record beside a dump, read quietly (the state path is a report)."""
    for candidate in _record_candidates(npz_path):
        if candidate.is_file():
            return _read_json(candidate)
    return None


def _multifreq_point(row):
    """One sweep row as a dict, or (None, why-not) when it cannot be drawn.

    Every number is read; ``k`` and ``beta_ambiguous`` ride along because the
    chart has to mark the bins whose dispersion branch is unresolved, and that
    is a property of the ROW, not of the picture.
    """
    if not isinstance(row, dict):
        return None, "a row that is not an object"
    label = row.get("artefact") or "a row with no artefact name"
    f_ghz = _as_float(row.get("f_ghz_used"))
    if f_ghz is None:
        f_hz = _as_float(row.get("f_hz_used"))
        f_ghz = None if f_hz is None else f_hz / 1e9
    s11 = _as_float(row.get("s11.magnitude"))
    s21 = _as_float(row.get("s21.magnitude"))
    if f_ghz is None or s11 is None or s21 is None:
        return None, f"{label} (no frequency or no magnitude)"
    errors = row.get("errors") or []
    if errors:
        return None, f"{label} (errors: {errors})"
    ambiguous = row.get("beta_ambiguous")
    return {
        "f_ghz": f_ghz,
        "s11": s11,
        "s21": s21,
        "artefact": str(label),
        "k": _as_int(row.get("k")),
        "beta_ambiguous": None if ambiguous is None else bool(ambiguous),
        "beta": _as_float(row.get("line.beta")),
        "beta_model": _as_float(row.get("line.beta_model")),
    }, None


def _multifreq_points(summary):
    """(points, skipped) for a sweep summary dict, sorted by recorded frequency."""
    rows = summary.get("rows") if isinstance(summary, dict) else None
    if not isinstance(rows, list):
        return [], []
    points, skipped = [], []
    for row in rows:
        point, why = _multifreq_point(row)
        if point is None:
            skipped.append(why)
            continue
        points.append(point)
    points.sort(key=lambda point: point["f_ghz"])
    return points, skipped


def load_multifreq(npz_path: Path, structure_id=None):
    """Read the multi-frequency |S11| / |S21| sweep for a dump and its arm.

    ``structure_id`` is the dump's own recorded provenance, and it selects WHICH
    arm's sweep is the fallback - it is never assumed. Returns ``{"path",
    "points", "skipped", ...}`` or None; ``points`` are dicts with keys
    ``f_ghz``, ``s11``, ``s21``, ``artefact``, ``k``, ``beta_ambiguous``,
    ``beta``, ``beta_model``, sorted by frequency and otherwise as recorded.
    Nothing here interpolates, smooths or re-orders into a curve: a
    row whose ``errors`` list is not empty, or which is missing a frequency or
    either magnitude, is DROPPED and counted, because drawing it as zero would
    invent a measurement.

    When this arm has no sweep at all its own single run is offered instead, as
    ONE point and flagged ``single_point``: the numbers are real, there is just
    one of them.
    """
    candidates = _multifreq_candidates(npz_path, structure_id)
    path = next((p for p in candidates if p.is_file()), None)
    # A LAST check on the chosen file, because the scan is not the only door:
    # the registry fallback is a LITERAL path, and an entry edited to point at
    # another arm's summary would otherwise be believed and drawn. The filename
    # carries the arm exactly as the scan matches it, so the same test applies to
    # whichever door the path came through - and a file that fails it is treated
    # as NOT FOUND (the one-point fallback below, then the reason), never
    # plotted as this dump's numbers.
    arm_key = _structure_key(structure_id)
    if path is not None and arm_key and f"_{arm_key}_" not in path.name:
        print(
            f"[poc_app] sweep {path} is not named for structure arm {arm_key}; "
            "refusing to draw it as this dump's sweep",
            file=sys.stderr,
        )
        path = None
    if path is None:
        single = _single_point_multifreq(structure_id)
        if single is not None:
            return single
        # The directory is named unconditionally: the old message ended
        # "(tried )" whenever the glob had died, which is exactly how a scan
        # that never ran survived unnoticed. A candidate list can now never be
        # printed without the directory it came from.
        # An arm-filtered scan can legitimately find NOTHING while other arms'
        # files sit right there, so the list is named as what it is: the
        # candidates for THIS structure's arm (empty when no arm was recorded).
        looked = ", ".join(str(p) for p in candidates) or "no candidate for this arm"
        print(
            f"[poc_app] no multi-frequency sweep in {Path(npz_path).parent} "
            f"(tried {looked}, none of which is a readable file); the "
            "|S11|/|S21| panel will say so",
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

    points, skipped = _multifreq_points(summary)

    if not points:
        print(
            f"[poc_app] sweep {path}: no usable rows "
            f"({len(skipped)} skipped)",
            file=sys.stderr,
        )
        return None
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
        # Not every summary carries a title or a status, and older ones carry
        # neither: absent stays absent here, and the caller derives what it can
        # rather than being handed an invented string. A sweep that exists is
        # never a single point - that flag belongs to the one-point fallback.
        "single_point": False,
        "title": summary.get("title"),
        "status": summary.get("status"),
    }


def _single_point_from_record(record, name: str):
    """The run record's own |S11| / |S21| as ONE sweep point, or None.

    Same keys as a sweep row, so the rows table, the chart and the "nearest
    recorded point" line read it without a second code path. The values are the
    record's ``s11.magnitude`` / ``s21.magnitude`` at the frequency that run was
    driven at - read off the file, not derived from anything else.
    """
    if not isinstance(record, dict):
        return None
    f_ghz = _own_frequency_ghz(record)
    s11_record = record.get("s11")
    s21_record = record.get("s21")
    s11 = (
        _as_float(s11_record.get("magnitude"))
        if isinstance(s11_record, dict)
        else None
    )
    s21 = (
        _as_float(s21_record.get("magnitude"))
        if isinstance(s21_record, dict)
        else None
    )
    if f_ghz is None or s11 is None or s21 is None:
        return None
    line = record.get("line") if isinstance(record.get("line"), dict) else {}
    return {
        "f_ghz": f_ghz,
        "s11": s11,
        "s21": s21,
        "artefact": name,
        "k": None,
        "beta_ambiguous": None,
        "beta": _as_float(line.get("beta")),
        "beta_model": _as_float(line.get("beta_model")),
    }


def _single_point_multifreq(structure_id):
    """The arm's own single run as a ONE-POINT sweep, or None.

    Called only when NO sweep was found. A single-frequency run is still a
    measurement, so the panel shows it rather than saying "nothing" - but as one
    point, flagged ``single_point``, because a curve through one point is drawn
    from the eye, not from the run. Chosen BY STRUCTURE for the same reason the
    sweep is: B's record is not A's, and an unnamed arm gets neither.
    """
    rel = SINGLE_RUN_BY_STRUCTURE.get(_structure_key(structure_id))
    if not rel:
        # No record registered for this arm is NOT an error - arm A has none on
        # disk - so this says nothing and simply offers no fallback.
        return None
    path = _resolve(rel)
    if not path.is_file():
        print(
            f"[poc_app] single-run record for {structure_id!r} not on disk: {path}",
            file=sys.stderr,
        )
        return None
    point = _single_point_from_record(_read_json(path), path.name)
    if point is None:
        print(
            f"[poc_app] single-run record {path} carries no usable "
            "|S11|/|S21|; the panel will say so",
            file=sys.stderr,
        )
        return None
    print(f"[poc_app] single-run S-parameter record: {path} (ONE point, no sweep)")
    return {
        "path": path,
        "points": [point],
        "skipped": [],
        "single_point": True,
        "title": None,
        "status": None,
        "dossier": None,
        "generated_utc": None,
        "bin_spacing_mhz": None,
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


_AMBIGUOUS_NOTE = "beta ambiguous - dispersion branch unresolved"
_DEFAULT_CHART_TITLE = "|S11|, |S21| per recorded frequency"


def _frequency_rows(mf: dict) -> list[str]:
    """The recorded rows as plain text: the fallback when no chart is drawn."""
    rows = [f"{'f [GHz]':>9}  {'|S11|':>7}  {'|S21|':>7}  {'k':>3}  artefact"]
    for point in mf["points"]:
        k_text = "-" if point.get("k") is None else f"{point['k']:d}"
        suffix = " beta ambiguous" if point.get("beta_ambiguous") else ""
        rows.append(
            f"{point['f_ghz']:9.4f}  {point['s11']:7.4f}  {point['s21']:7.4f}  "
            f"{k_text:>3}  {point['artefact']}{suffix}"
        )
    return rows


def _frequency_caption(mf: dict, record, arm=None) -> str:
    """One line: the source file, its arm, the row count, and what was NOT done."""
    # The ARM is named beside the filename, and it is not decoration: the arm is
    # what decides WHICH file could ever have been chosen (_multifreq_candidates
    # filters the beside-dump scan by it, and load_multifreq refuses a file that
    # does not carry it), so a caption naming only the file cannot show that the
    # choice was made by provenance rather than by sorting order. "structure
    # arm B" is the page's own word for it - the SETUP picker's label.
    arm_note = f" (structure arm {arm})" if arm else ""
    if mf.get("single_point"):
        # ONE point is this arm's own single run, not a sweep. Said first, before
        # any number: a one-point "curve" is the easiest thing on this page to
        # misread as a trend.
        caption = (
            f"ONE recorded point from {mf['path'].name}{arm_note} - this arm's "
            "own single run, not a frequency sweep - marker only, no line and "
            "no interpolation: a point is not a curve"
        )
    else:
        caption = (
            f"{len(mf['points'])} recorded frequencies from "
            f"{mf['path'].name}{arm_note} - markers joined by a guide line for "
            "the eye: nothing between these bins was solved or interpolated"
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
    # Only when the summary actually declares one: the summaries on disk today
    # carry no status, and an absent key must not become an empty clause.
    if mf.get("status"):
        caption += f"; summary status: {mf['status']}"
    return caption


def _s_params_nearest(mf: dict, f_ref_ghz):
    """The RECORDED point nearest a frequency: ``(point, ref_ghz, offset, why)``.

    Nothing is interpolated. The offset is not a rounding detail - it is the
    distance between the frequency the model was driven at and the bin the
    number was actually measured at, so the caller can print both and a reader
    can see whether the quoted |S11| belongs to that frequency or merely to the
    nearest one. When the dump records no reference frequency the band centre of
    the recorded bins is used instead, and ``why`` says so in words.
    """
    points = mf.get("points") or []
    if not points:
        return None, None, None, "no recorded points"
    ref_ghz = _finite(f_ref_ghz)
    if ref_ghz is None:
        lo = min(point["f_ghz"] for point in points)
        hi = max(point["f_ghz"] for point in points)
        ref_ghz = 0.5 * (lo + hi)
        why = f"the band centre {ref_ghz:.4f} GHz (the dump records no f_ref)"
    else:
        why = f"f_ref {ref_ghz:.4f} GHz"
    point = min(points, key=lambda item: abs(item["f_ghz"] - ref_ghz))
    return point, ref_ghz, abs(point["f_ghz"] - ref_ghz), why


def _s_params_number_text(mf: dict, f_ref_ghz) -> str:
    """One line: the |S11| of the recorded point nearest the driven frequency.

    The wording says "nearest recorded point" every time, and prints the offset,
    because a single number beside a curve is the easiest thing on the page to
    misread as "the |S11| at exactly this frequency". No curve is fitted and no
    value is interpolated to make the two frequencies coincide.
    """
    point, _ref_ghz, offset, why = _s_params_nearest(mf, f_ref_ghz)
    if point is None:
        return "|S11|: no recorded sweep point to quote"
    text = (
        f"|S11| {point['s11']:.4f} at {point['f_ghz']:.4f} GHz "
        f"(nearest recorded point to {why}; offset {offset:.4f} GHz, "
        "no interpolation"
    )
    if point.get("k") is not None:
        text += f"; k={point['k']}"
    if point.get("beta_ambiguous"):
        text += "; beta ambiguous"
    return text + ")"


def build_frequency_chart(mf: dict, title: str | None = None) -> dict:
    """Render |S11| and |S21| vs frequency to a PNG data URI.

    Returns ``{"image": data_uri | None, "rows": [...], "reason": str | None}``.
    matplotlib is a project dependency, but it is imported HERE, lazily and
    guarded: the numpy-only paths (--help, --list-keys) must never need it, and
    a missing or broken matplotlib has to cost the picture, not the page - the
    caller falls back to the text rows.

    A thin line joins the recorded bins as a guide to the eye, and it is the only
    thing drawn between them: nothing between two recorded frequencies was solved,
    so the line interpolates nothing the sweep reported. It sits UNDER the markers
    and carries no legend label, which keeps the legend to the four recorded point
    sets. Solid joins the definite bins, dashed the ambiguous ones; their open
    markers stay discrete points at their recorded frequency - not smoothed, not
    dropped.

    ``title`` names the selected structure; when it is not given the panel keeps a
    structure-neutral default rather than naming a run the caller did not choose.
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

    # Sorted by frequency: a guide line drawn through bins in file order would
    # double back on itself and read as a measurement it is not.
    definite = sorted(
        (point for point in mf["points"] if not point.get("beta_ambiguous")),
        key=lambda point: point["f_ghz"],
    )
    ambiguous = sorted(
        (point for point in mf["points"] if point.get("beta_ambiguous")),
        key=lambda point: point["f_ghz"],
    )
    try:
        fig, ax = plt.subplots(figsize=(5.4, 1.9), dpi=110)
        # The guide lines go down FIRST and under everything (zorder=1 against a
        # marker's default 2), and they carry no legend label: the legend counts
        # the four RECORDED point sets, and a joining line is not a fifth
        # measurement. Solid joins the definite bins - an unbroken set on one
        # dispersion branch, in frequency order. Dashed joins the ambiguous ones,
        # whose open markers sit on top of it, because the dash makes the same
        # statement the open marker makes: these bins may not be read as one
        # sequence. Fewer than two bins in a class draws no line at all, so a lone
        # recorded frequency never gains a segment it did not measure.
        for series, colour in (("s11", "#1f77b4"), ("s21", "#d62728")):
            for points, style in ((definite, "-"), (ambiguous, (0, (4, 3)))):
                if len(points) < 2:
                    continue
                ax.plot(
                    [point["f_ghz"] for point in points],
                    [point[series] for point in points],
                    color=colour,
                    linewidth=1.0,
                    linestyle=style,
                    zorder=1,
                    label="_nolegend_",
                )
        ax.plot(
            [point["f_ghz"] for point in definite],
            [point["s11"] for point in definite],
            "o",
            color="#1f77b4",
            markersize=5,
            linestyle="none",
            label="|S11|",
        )
        ax.plot(
            [point["f_ghz"] for point in definite],
            [point["s21"] for point in definite],
            "s",
            color="#d62728",
            markersize=5,
            linestyle="none",
            label="|S21|",
        )
        if ambiguous:
            ax.plot(
                [point["f_ghz"] for point in ambiguous],
                [point["s11"] for point in ambiguous],
                "o",
                markerfacecolor="none",
                markeredgecolor="#1f77b4",
                markeredgewidth=1.2,
                markersize=6,
                linestyle="none",
                label="|S11|, beta ambiguous",
            )
            ax.plot(
                [point["f_ghz"] for point in ambiguous],
                [point["s21"] for point in ambiguous],
                "s",
                markerfacecolor="none",
                markeredgecolor="#d62728",
                markeredgewidth=1.2,
                markersize=6,
                linestyle="none",
                label="|S21|, beta ambiguous",
            )
            ax.annotate(
                _AMBIGUOUS_NOTE,
                xy=(ambiguous[0]["f_ghz"], ambiguous[0]["s11"]),
                xytext=(6, -12),
                textcoords="offset points",
                fontsize=5.5,
                color="#8c6d1f",
            )
        ax.set_xlabel("frequency [GHz]", fontsize=7)
        ax.set_ylabel("magnitude", fontsize=7)
        ax.tick_params(labelsize=6)
        ax.grid(True, color="#dddddd", linewidth=0.5)
        ax.legend(fontsize=6, frameon=False, loc="best")
        ax.set_title(title or _DEFAULT_CHART_TITLE, fontsize=7)
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


# --- chart title, port waves, and the numpy-only state dump ------------------
#
# Everything below is stdlib + numpy. --dump-state is a REPORT: it says which
# artefacts this page would composite and where the seams are, and it has to do
# that on a machine with no pyvista, no trame and no matplotlib. Every number is
# read from a file; the only derived values are the two residual percentages,
# and those carry the basis string that produced them.

_PORT_TITLE = "station phasors, as recorded"
# The load trace's heading, in the same voice as _PORT_TITLE: the words say WHERE
# the numbers came from (the load's cut, as recorded) so the panel cannot be read
# as a refit, an extrapolation, or the series_r artefact's 50 ohm record.
_LOAD_SERIES_TITLE = "the load's own V(t) and I(t) at the cut, as recorded"
_PORT_FIELDS = ("v_re", "v_im", "i_re", "i_im")
STATE_SCHEMA = "emfit.poc-state/1"
RESIDUAL_BASIS = "50/(50 + 2*z0)"
# Why two extents and not one: the domain box is what was SOLVED, the sampled
# span is what the npz STORES, and on x they are nx cells versus the 25 cells
# the n_stations captured planes COVER. The basis string ships with the numbers
# so a reader never has to guess which of the two a millimetre figure came from.
EXTENT_BASIS = (
    "domain_mm = nx*cell (the simulated box); sampled_mm = the span the field "
    "samples actually stored in the npz COVER - on x the line the 9 captured "
    "planes span, 25 cells of 0.4 mm = 10.0 mm here, and on y/z the stored "
    "array's own shape (213 rows = 85.2 mm, 22 = 8.8 mm)"
)


def _utc_now() -> str:
    """ISO-8601 UTC, seconds resolution: the state dump's own timestamp."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fmt(value, digits=6) -> str:
    """A number for a text table, or 'n/a' when the record did not carry it."""
    return "n/a" if value is None else f"{value:.{digits}f}"


def _chart_title(structure) -> str:
    """The frequency chart's title, derived from the selected entry.

    No literal case name lives here any more: the page names whichever structure
    is loaded. When the entry declares a mismatch the parenthetical names BOTH
    runs, because the markers are S-parameter rows while the field beside them
    came from another run - that composite is the title's most important word.
    """
    if not isinstance(structure, dict):
        return _DEFAULT_CHART_TITLE
    title = f"{_structure_label(structure)}: " + _DEFAULT_CHART_TITLE
    if structure.get("mismatch"):
        sparams_run = _run_letter(structure, "sparams")
        field_run = _run_letter(structure, "field_dump")
        if sparams_run and field_run:
            title += f" (S-params run {sparams_run}; field run {field_run})"
    return title


def _float_list(value):
    """A list of floats as recorded, or None when it is not one."""
    if not isinstance(value, list):
        return None
    numbers = []
    for item in value:
        number = _as_float(item)
        if number is None:
            return None
        numbers.append(number)
    return numbers


def _port_waves_block(path, record=None):
    """``s11.station_phasors`` as a state block, or ``(None, reason)``.

    Every parallel array is checked against the record's own ``n`` BEFORE a single
    row is emitted. A short array is a broken artefact: zipping it silently would
    present part of a measurement as the whole of one. Returns
    ``(block, None)`` or ``(None, reason)`` - never raises, never truncates.
    """
    data = record if isinstance(record, dict) else _read_json(path)
    name = Path(path).name if path is not None else "the S-parameter record"
    if not isinstance(data, dict):
        return None, f"no readable S-parameter record at {path}"
    s11 = data.get("s11")
    if not isinstance(s11, dict):
        return None, f"{name} carries no s11 block"
    phasors = s11.get("station_phasors")
    if not isinstance(phasors, dict):
        return None, f"{name} carries no s11.station_phasors block"
    n = _as_int(phasors.get("n"))
    if n is None:
        return None, f"{name} station_phasors records no n"
    x_m = _float_list(phasors.get("x_m"))
    columns = {field: _float_list(phasors.get(field)) for field in _PORT_FIELDS}
    for label, values in [("x_m", x_m)] + list(columns.items()):
        if values is None:
            return None, f"{name} station_phasors.{label} is absent or not numeric"
        if len(values) != n:
            return None, (
                f"{name} station_phasors.{label} holds {len(values)} entries but n "
                f"= {n}; refusing to truncate to the shorter array"
            )
    stations = []
    for idx in range(n):
        row = {"x_m": x_m[idx]}
        for field in _PORT_FIELDS:
            row[field] = columns[field][idx]
        stations.append(row)
    return {
        "file": str(path),
        "beta_two": _as_float(phasors.get("beta_two")),
        "beta_used": _as_float(phasors.get("beta_used")),
        "n_stations": n,
        "status": phasors.get("status"),
        "note": phasors.get("note"),
        "stations": stations,
    }, None


def _port_wave_rows(port_waves) -> list[str]:
    """The station phasors as plain text: the fallback when no chart is drawn."""
    rows = [f"{'x [mm]':>6}  {'v_re':>11}  {'v_im':>11}  {'i_re':>11}  {'i_im':>11}"]
    for station in port_waves["stations"]:
        rows.append(
            f"{station['x_m'] * 1e3:6.3f}  {_fmt(station['v_re']):>11}  "
            f"{_fmt(station['v_im']):>11}  {_fmt(station['i_re']):>11}  "
            f"{_fmt(station['i_im']):>11}"
        )
    return rows


def _port_caption(port_waves, reason) -> str:
    """One line naming the file, and what this panel is not."""
    if port_waves is None:
        return f"no station phasors to show: {reason}"
    return (
        f"{_PORT_TITLE} - {port_waves['n_stations']} stations from "
        f"{Path(port_waves['file']).name}; markers only, nothing refitted here "
        f"(beta_two {_fmt(port_waves.get('beta_two'), 4)} rad/m, beta_used "
        f"{_fmt(port_waves.get('beta_used'), 4)} rad/m, status "
        f"{port_waves.get('status') or 'not recorded'})"
    )


def _load_series_caption(load_series, reason) -> str:
    """One line naming the trace's file, its sample count and its element.

    Same contract as _port_caption: the caption comes out whether or not anything
    can be drawn, because "no trace was taken for this run" and "the picture could
    not be drawn" are different facts and the caption is where the first is said.
    """
    if not isinstance(load_series, dict):
        return f"no load trace to show: {reason or 'the dump carries none'}"
    recorded_name = load_series.get("netlist_name")
    if isinstance(recorded_name, str) and recorded_name.strip():
        element = f"netlist circuit '{recorded_name.strip()}'"
    elif str(load_series.get("load_netlist_json") or "").strip():
        element = "a netlist circuit (unnamed in the dump)"
    else:
        ohm_text = "not recorded"
        try:
            if math.isfinite(float(load_series.get("load_ohm"))):
                ohm_text = f"{float(load_series.get('load_ohm')):g} ohm"
        except (TypeError, ValueError):
            pass
        element = f"lumped resistor ({ohm_text})"
    return (
        f"{_LOAD_SERIES_TITLE} - {load_series.get('n')} samples from "
        f"{Path(load_series.get('file') or 'the dump').name}, terminating the "
        f"cut in {element}"
    )


def build_port_wave_chart(port_waves) -> dict:
    """Render the recorded station phasors to a PNG data URI.

    Two panels - voltage and current - markers only, against x in mm. Guarded
    exactly like build_frequency_chart: matplotlib is imported lazily and a broken
    installation costs the picture, never the page, because the caller falls back
    to ``rows``. Nothing is fitted, smoothed or extrapolated off the station span.
    """
    rows = _port_wave_rows(port_waves)
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
        print(f"[poc_app] no port-wave chart (matplotlib unusable: {exc})", file=sys.stderr)
        return {"image": None, "rows": rows, "reason": f"matplotlib unusable: {exc}"}

    x_mm = [station["x_m"] * 1e3 for station in port_waves["stations"]]
    try:
        fig, (ax_v, ax_i) = plt.subplots(1, 2, figsize=(6.0, 1.9), dpi=110)
        for ax, field_re, field_im, colour, symbol in (
            (ax_v, "v_re", "v_im", "#1f77b4", "V"),
            (ax_i, "i_re", "i_im", "#d62728", "I"),
        ):
            ax.plot(
                x_mm,
                [station[field_re] for station in port_waves["stations"]],
                "o",
                color=colour,
                markersize=5,
                linestyle="none",
                label=f"{symbol} re",
            )
            ax.plot(
                x_mm,
                [station[field_im] for station in port_waves["stations"]],
                "s",
                color=colour,
                markerfacecolor="none",
                markeredgewidth=1.1,
                markersize=5,
                linestyle="none",
                label=f"{symbol} im",
            )
            ax.set_xlabel("x [mm]", fontsize=7)
            ax.tick_params(labelsize=6)
            ax.grid(True, color="#dddddd", linewidth=0.5)
            ax.legend(fontsize=6, frameon=False, loc="best")
        ax_v.set_ylabel("voltage, as recorded", fontsize=7)
        ax_i.set_ylabel("current, as recorded", fontsize=7)
        fig.suptitle(
            f"{_PORT_TITLE} - beta_two {_fmt(port_waves.get('beta_two'), 4)}, "
            f"beta_used {_fmt(port_waves.get('beta_used'), 4)}, status "
            f"{port_waves.get('status') or 'not recorded'}, "
            f"n = {port_waves['n_stations']}",
            fontsize=6.5,
        )
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.90))
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        plt.close(fig)
        png = buffer.getvalue()
    except Exception as exc:  # noqa: BLE001 - never take the server down
        print(f"[poc_app] port-wave chart skipped: {exc}", file=sys.stderr)
        return {"image": None, "rows": rows, "reason": f"chart render failed: {exc}"}

    uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    print(f"[poc_app] port-wave chart: {len(png)} PNG bytes")
    return {"image": uri, "rows": rows, "reason": None, "png_bytes": len(png)}


def build_port_series_chart(load_series) -> dict:
    """Render the load's recorded V(t)/I(t) trace to a PNG data URI.

    Two panels on ONE figure - voltage left, current right - against the same
    simulated time axis in ns. Guarded exactly like build_port_wave_chart:
    matplotlib is imported lazily and a broken installation, or a series this
    module cannot use, costs the picture and never the page.

    The x axis is deliberately given NO fixed span. A 60-step run spans a few
    hundredths of a nanosecond and a 400-step run a few nanoseconds, and this one
    figure serves both: a hard-coded range would flatten the short run into a
    single column and hide most of the long one.

    The element is named IN the figure, not only in a caption beside it. This page
    also shows the series_r artefact, whose own ``loads`` record names a 50 ohm
    resistor; an unlabelled V(t)/I(t) trace would be read as that resistor's, so
    the circuit is named (from the netlist's own ``name``, else the raw text
    truncated) whenever a netlist was supplied.

    An empty trace is a NORMAL case - no netlist and no ``--vis-dump`` trace - so
    it is a clean ``reason``, not an exception and not an empty plot.
    """
    if not isinstance(load_series, dict):
        return {
            "image": None,
            "rows": [],
            "reason": "no load trace was taken for this run",
        }
    try:
        t_ns = [float(value) for value in load_series["load_t_ns"]]
        volts = [float(value) for value in load_series["load_v"]]
        amps = [float(value) for value in load_series["load_i"]]
    except Exception as exc:  # noqa: BLE001 - a malformed block is a reason
        return {
            "image": None,
            "rows": [],
            "reason": f"the load trace is unusable: {exc}",
        }
    if not t_ns or len(volts) != len(t_ns) or len(amps) != len(t_ns):
        return {
            "image": None,
            "rows": [],
            "reason": (
                f"the load trace holds {len(t_ns)}/{len(volts)}/{len(amps)} "
                "samples (t/V/I); refusing to draw part of it"
            ),
        }

    # Which element these series belong to, resolved once and printed both in the
    # figure's title and in the rows, so the two can never drift apart.
    raw_json = load_series.get("load_netlist_json") or ""
    recorded_name = load_series.get("netlist_name")
    if isinstance(recorded_name, str) and recorded_name.strip():
        element = (
            f"netlist circuit '{recorded_name.strip()}' "
            "(series_r termination replaced)"
        )
    elif str(raw_json).strip():
        flat = " ".join(str(raw_json).split())
        element = (
            f"netlist circuit '{flat[:60]}{'...' if len(flat) > 60 else ''}' "
            "(series_r termination replaced)"
        )
    else:
        ohm = load_series.get("load_ohm")
        ohm_text = "not recorded"
        try:
            if math.isfinite(float(ohm)):
                ohm_text = f"{float(ohm):g} ohm"
        except (TypeError, ValueError):
            pass
        element = f"lumped resistor ({ohm_text})"

    rows = [
        ["element", element],
        ["samples", str(len(t_ns))],
        ["t span [ns]", f"{min(t_ns):.6g} .. {max(t_ns):.6g}"],
        ["V min / max [V]", f"{min(volts):.6g} / {max(volts):.6g}"],
        ["I min / max [A]", f"{min(amps):.6g} / {max(amps):.6g}"],
    ]

    try:
        import base64
        import io

        import matplotlib

        try:
            matplotlib.use("Agg")
        except Exception:  # noqa: BLE001 - an existing backend is acceptable
            pass
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001 - no picture, no rows, just a reason
        print(
            f"[poc_app] no port-series chart (matplotlib unusable: {exc})",
            file=sys.stderr,
        )
        return {"image": None, "rows": [], "reason": f"matplotlib unusable: {exc}"}

    fig = None
    try:
        fig, (ax_v, ax_i) = plt.subplots(1, 2, figsize=(6.0, 1.9), dpi=110)
        for ax, values, colour, symbol, unit in (
            (ax_v, volts, "#1f77b4", "V", "V"),
            (ax_i, amps, "#d62728", "I", "A"),
        ):
            ax.plot(t_ns, values, color=colour, linewidth=1.1)
            ax.set_xlabel("t [ns]", fontsize=7)
            ax.set_title(f"{symbol}(t) at the load [{unit}]", fontsize=7)
            ax.tick_params(labelsize=6)
            ax.grid(True, color="#dddddd", linewidth=0.5)
        ax_v.set_ylabel("voltage, as recorded", fontsize=7)
        ax_i.set_ylabel("current, as recorded", fontsize=7)
        fig.suptitle(
            f"load series - {element}, n = {len(t_ns)}",
            fontsize=6.5,
        )
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.90))
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight")
        png = buffer.getvalue()
    except Exception as exc:  # noqa: BLE001 - never take the server down
        print(f"[poc_app] port-series chart skipped: {exc}", file=sys.stderr)
        return {"image": None, "rows": [], "reason": f"chart render failed: {exc}"}
    finally:
        # EVERY path leaves the figure closed, including the one above: the server
        # is long-lived, so a leaked figure is a leak per page load.
        if fig is not None:
            plt.close(fig)

    uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    print(f"[poc_app] port-series chart: {len(png)} PNG bytes")
    return {"image": uri, "rows": rows, "reason": None}


def _structure_artifact_path(structure, key):
    """An entry's artefact path for ``key``, but only if it exists on disk."""
    block = structure.get(key) if isinstance(structure, dict) else None
    value = block.get("path") if isinstance(block, dict) else None
    if not isinstance(value, str) or not value:
        return None
    path = _resolve(value)
    return path if path.is_file() else None


def _sparams_path(npz_path: Path, structure):
    """The S-parameter record for this page: the entry's, else the dump's own."""
    declared = _structure_artifact_path(structure, "sparams")
    if declared is not None:
        return declared
    for candidate in _record_candidates(npz_path):
        if candidate.is_file():
            return candidate
    return None


def _multifreq_path(npz_path: Path, structure, structure_id=None):
    """The sweep file for this page: the entry's, else the one beside the dump.

    ``structure_id`` is the dump's own recorded provenance (``info["structure_id"]``,
    an arm key like ``"A"``/``"B"`` - NOT a registry id such as ``build_A_50ohm``);
    the beside-dump scan is arm-filtered, so it cannot contribute without it.
    """
    declared = _structure_artifact_path(structure, "multifreq")
    if declared is not None:
        return declared
    for candidate in _multifreq_candidates(npz_path, structure_id):
        if candidate.is_file():
            return candidate
    return None


def _field_dump_block(info: dict, path: Path) -> dict:
    """The field-dump half: CELLS from the array shape, the x axis from the record.

    TWO extents, deliberately kept apart. ``extent_domain_mm`` is the simulated
    box, nx cells across. ``extent_sampled_mm`` is the span the captured planes
    actually COVER - on x the bounding span of the station axis (last station
    minus first, plus one cell), not nx. One number called "extent" cannot say
    which of the two it means, and here they differ by more than a factor of two
    (24.8 mm vs 10.0 mm): reading the domain box as "the field I have" is the
    misreading this split exists to make impossible. ``extent_basis`` says it in
    words as well.

    The two extents therefore come from two different places, and the counts
    behind them are named for where they were read: nx/ny/nz are the DOMAIN
    cells the record declares. On y and z the sampled span is still the STORED
    array's own shape; those do not agree with the box on every axis - the
    stored plane is 9 x 213 x 22 inside a 62 x 212 x 22 box, one row more in y
    than the box has cells - so borrowing the domain count for the sampled y
    would report 84.8 mm for an array that spans 85.2 mm. On x the span comes
    from the station axis, which is where the planes actually sit; how MANY
    planes there are is a separate fact and is reported as ``n_stations``.
    """
    plane = info[PLANE_KEY]
    nx_domain, ny_domain, nz_domain = int(info["nx"]), int(info["ny"]), int(info["nz"])
    cell_m = float(info["cell_m"])
    cell_mm = cell_m * 1e3
    n_stations_sampled, ny_sampled, nz_sampled = (int(n) for n in plane.shape)
    # The record IS in scope: it sits beside the dump and is found from the
    # dump's own path, so the study's real station axis is readable here. The
    # npz's own ``station_x_m`` still wins when the dump carries one - that is
    # step 1 of _station_axis_mm - and the uniform assumption is only the last
    # resort for a dump that really has nothing recorded.
    record = _field_record(path)
    stations_x_mm, stations_src = _station_axis_mm(info, record)
    # The span COVERED on x, not ``n_stations * cell``: a plane count times the
    # cell only equals the span when the planes sit one cell apart starting at
    # the origin. For such a dump this is byte-identical to the old n_st * cell
    # (9 planes -> 3.6 mm); for the shipped study, whose nine planes run 10.4 to
    # 20.0 mm, it is 9.6 + 0.4 = 10.0 mm of covered line - 25 cells, 16 of them
    # with no plane sampled on them. How many PLANES there are stays in
    # ``n_stations``.
    span_x_mm = (
        (stations_x_mm[-1] - stations_x_mm[0]) + cell_mm
        if n_stations_sampled > 1
        else cell_mm
    )
    return {
        "file": str(path),
        "cells": {"nx": nx_domain, "ny": ny_domain, "nz": nz_domain},
        "cell_m": cell_m,
        "grid_cell_mm": round(cell_mm, 9),
        "extent_domain_mm": {
            "x": round(nx_domain * cell_mm, 9),
            "y": round(ny_domain * cell_mm, 9),
            "z": round(nz_domain * cell_mm, 9),
        },
        "extent_sampled_mm": {
            "x": round(span_x_mm, 9),
            "y": round(ny_sampled * cell_mm, 9),
            "z": round(nz_sampled * cell_mm, 9),
        },
        "extent_basis": EXTENT_BASIS,
        # The station axis is READ, never derived from the index: the study snaps
        # each wanted station to a grid cell, so ``i * cell`` would put the nine
        # captured planes over the port end of the line (see _station_axis_mm).
        # Key and shape stay exactly what they were - only the numbers change.
        "stations_x_mm": [float(value) for value in stations_x_mm],
        "stations_src": stations_src,
        "n_stations": n_stations_sampled,
        "nstep": int(info["nstep"]),
    }


def _sparams_block(path) -> dict:
    """The S-parameter half, every number read and nothing guessed.

    ``cells`` is parsed out of the record's own summary_line ("cells=72x212x22")
    and nowhere else: that line and the npz array shape are precisely the two
    numbers the mismatch check compares. Unreadable fields are null.
    """
    data = _read_json(path) if path is not None else None
    record = data if isinstance(data, dict) else {}
    s11 = record.get("s11") if isinstance(record.get("s11"), dict) else {}
    s21 = record.get("s21") if isinstance(record.get("s21"), dict) else {}
    line = record.get("line") if isinstance(record.get("line"), dict) else {}
    at_plane = (
        record.get("s11_at_plane")
        if isinstance(record.get("s11_at_plane"), dict)
        else {}
    )
    return {
        "file": None if path is None else str(path),
        "cells": _cells_from_summary(record.get("summary_line")),
        "n_line": _n_line(record),
        "s11_two_wave": _as_float(s11.get("magnitude")),
        "s11_one_wave": _as_float(s11.get("magnitude_one_wave_station_fit")),
        "s21_magnitude": _as_float(s21.get("magnitude")),
        "s11_at_plane": {
            "magnitude": _as_float(at_plane.get("magnitude")),
            "plane_index": _as_int(at_plane.get("plane_index")),
            # The record does not adjudicate this number, so neither do we: a
            # reflection read at an internal plane is quarantined until someone
            # shows it is the quantity it looks like.
            "status": "quarantined",
        },
        "beta_used": _as_float(line.get("beta")),
        "beta_model": _as_float(line.get("beta_model")),
        "validation_status": s11.get("validation_status"),
    }


def _n_line_or_unknown(value) -> str:
    return "unknown" if value is None else str(value)


def _mismatch_block(field_text, sparams_text, field_n_line, sparams_n_line) -> dict:
    """Whether the two halves of this page are even the same solve, and why not."""
    flag = bool(field_text) and bool(sparams_text) and field_text != sparams_text
    if flag:
        reason = (
            f"Field dump is {field_text} but the S-parameter record is "
            f"{sparams_text}; they come from different runs (n_line "
            f"{_n_line_or_unknown(field_n_line)} vs "
            f"{_n_line_or_unknown(sparams_n_line)}) and are not the same solve."
        )
    elif field_text and sparams_text:
        reason = (
            f"Field dump and S-parameter record both report {field_text}; the "
            "cell counts agree, which is not by itself proof of one run."
        )
    else:
        missing = "field dump" if not field_text else "S-parameter record"
        reason = (
            f"Cell counts could not be compared: the {missing} carries no "
            "readable cells=... line, so no claim is made either way."
        )
    return {
        "flag": flag,
        "reason": reason,
        "field_cells": field_text,
        "sparams_cells": sparams_text,
    }


def _residual_block(z0_ohm, s11_two_wave) -> dict:
    """One anchor and the two-wave |S11| measured against it.

    ``anchor`` is |Gamma| for a 50 ohm load in a Z0 line: 50/(50 + 2*Z0). Both the
    anchor and the percentage are derived here and ship with their basis string,
    because the whole DR-19 confusion is two denominators wearing one label.
    """
    z0 = _as_float(z0_ohm)
    s11 = _as_float(s11_two_wave)
    anchor = None if z0 is None else 50.0 / (50.0 + 2.0 * z0)
    pct = None
    if anchor is not None and s11 is not None and anchor != 0.0:
        pct = round(100.0 * (s11 / anchor - 1.0), 2)
    return {
        "z0_ohm": z0,
        "anchor": None if anchor is None else round(anchor, 6),
        "s11_over_anchor_pct": pct,
        "basis": RESIDUAL_BASIS,
    }


def _residuals_block(anchors, s11_two_wave) -> dict:
    """Both declared anchors against the same measurement; never 'validated'."""
    anchors = anchors if isinstance(anchors, dict) else {}
    independent = anchors.get("independent")
    circular = anchors.get("circular")
    return {
        "anchor_independent": _residual_block(
            independent.get("z0_ohm") if isinstance(independent, dict) else None,
            s11_two_wave,
        ),
        "anchor_circular": _residual_block(
            circular.get("z0_ohm") if isinstance(circular, dict) else None,
            s11_two_wave,
        ),
        "status": "diagnosis in progress",
        "validated": False,
        "ledger_refs": ["E1", "E11"],
    }


# --- how much to trust the numbers -----------------------------------------
#
# The Confidence & Accuracy panel is the one place on this page that says what a
# number is WORTH rather than what it is. Every row it carries is DERIVED here
# from the dump's own study record (and, when one is on disk, the referee
# extraction), nothing is typed in, and each row names its basis, so a reader
# never has to guess which file or which formula produced it.
#
# Two rules shape the wording:
#
#   * A missing number is a missing FIELD, never a zero. A sigma recorded as the
#     string "ABSENT" and a residual the writer never serialised are both printed
#     as what they are, because a page that rendered them as 0.0 would be
#     inventing the most reassuring value it could.
#   * The referee is a SECOND OPINION, not a validation. It is a different
#     extraction of the same |S11| at the same frequency, and its own mode fit
#     failed (its own scalars say so), so its agreement is printed beside that
#     failure instead of being quoted as a clean result.
REFEREE_S11_FILE = "evidence/referee/s11_extraction.json"
# The referee key this panel compares against. `s11_abs` is the referee's own
# extraction; `s11_artefact_target` is the artefact's recorded value carried
# forward, so comparing against THAT would compare the record with itself.
REFEREE_S11_KEY = "s11_abs"


def _referee_s11_path():
    """The referee extraction's resolved path, or None when it cannot be made."""
    try:
        return _resolve(REFEREE_S11_FILE)
    except Exception:  # noqa: BLE001 - a path is never worth a traceback
        return None


def _confidence_mm(meters, digits=3) -> str:
    """A recorded length in METRES printed in MILLIMETRES, or 'n/a'."""
    value = _finite(_as_float(meters))
    return "n/a" if value is None else f"{value * 1e3:.{digits}f} mm"


def _confidence_ghz(hz, digits=6) -> str:
    """A recorded frequency in HZ printed in GHZ, or 'n/a'."""
    value = _finite(_as_float(hz))
    return "n/a" if value is None else f"{value / 1e9:.{digits}f} GHz"


def _confidence_z0(z0_re, z0_im) -> str:
    """One complex impedance in ohm, or 'n/a' when either part is missing."""
    re = _finite(_as_float(z0_re))
    im = _finite(_as_float(z0_im))
    if re is None or im is None:
        return "n/a"
    sign = "+" if im >= 0.0 else "-"
    return f"{re:.4f} {sign} j{abs(im):.4f} ohm"


def _confidence_cells_per_lambda(beta, cell_m):
    """(lambda_m, cells_per_lambda) for one recorded beta, or (None, None)."""
    beta = _finite(_as_float(beta))
    cell = _finite(_as_float(cell_m))
    if beta is None or cell is None or beta <= 0.0 or cell <= 0.0:
        return None, None
    lam = 2.0 * math.pi / beta
    return lam, lam / cell


def _confidence_mesh_rows(record) -> list:
    """What was SOLVED: the cell size and the grid, cross-checked against itself.

    The grid product is multiplied here rather than trusted: a dump whose
    ``geometry.cells`` disagrees with ``nx*ny*nz`` is a dump whose cell count
    cannot be quoted, and the row says which of the two it agrees with.
    """
    geometry = record.get("geometry")
    geometry = geometry if isinstance(geometry, dict) else {}
    rows = [(
        "mesh: cell size",
        f"{_confidence_mm(geometry.get('cell_m', geometry.get('cell')))}"
        " (geometry.cell_m) - the mesh every length on this panel is counted in",
    )]
    grid = geometry.get("grid")
    axes = [_as_int(item) for item in grid] if isinstance(grid, (list, tuple)) else []
    if len(axes) != 3 or any(axis is None for axis in axes):
        rows.append(("mesh: grid", "n/a (geometry.grid is not three integers)"))
        return rows
    product = axes[0] * axes[1] * axes[2]
    recorded = _as_int(geometry.get("cells"))
    if recorded == product:
        agreement = f"the recorded geometry.cells = {recorded} AGREES"
    else:
        agreement = (
            f"the recorded geometry.cells = {recorded if recorded is not None else 'n/a'}"
            " DISAGREES with it"
        )
    rows.append((
        "mesh: grid",
        f"{axes[0]} x {axes[1]} x {axes[2]} = {product} cells (geometry.grid, "
        f"multiplied here); {agreement}",
    ))
    return rows


def _confidence_resolution_rows(record) -> list:
    """Cells per wavelength at BOTH betas: the resolution the run really had.

    ``lambda = 2*pi/beta`` is derived from the RECORDED beta and then counted in
    mesh cells, because that ratio - not the wave speed - is what decides whether
    a 0.4 mm mesh can carry this wave at all. It is printed for the measured beta
    and the model beta: the two disagree, and a reader is entitled to see both.
    """
    geometry = record.get("geometry")
    geometry = geometry if isinstance(geometry, dict) else {}
    line = record.get("line") if isinstance(record, dict) else None
    line = line if isinstance(line, dict) else {}
    cell_m = geometry.get("cell_m", geometry.get("cell"))
    rows, betas = [], {}
    for label, key, what in (
        (
            "resolution: cells per wavelength (measured beta)",
            "beta",
            "line.beta, the station fit this run's own |S11| is de-embedded with",
        ),
        (
            "resolution: cells per wavelength (model beta)",
            "beta_model",
            "line.beta_model, the quasi-static model at this geometry",
        ),
    ):
        beta = _finite(_as_float(line.get(key)))
        lam, ratio = _confidence_cells_per_lambda(beta, cell_m)
        if ratio is None:
            rows.append((label, f"n/a ({what} is not a positive number)"))
            continue
        betas[key] = beta
        rows.append((
            label,
            f"{ratio:.1f} cells per wavelength at beta = {beta:.6f} rad/m "
            f"(lambda = 2*pi/beta = {_confidence_mm(lam)}; {what})",
        ))
    measured, model = betas.get("beta"), betas.get("beta_model")
    if measured is not None and model:
        rows.append((
            "beta: measured vs model",
            f"{measured:.6f} vs {model:.6f} rad/m, "
            f"{100.0 * (measured / model - 1.0):+.2f} % (line.beta vs "
            "line.beta_model) - the fit and the model disagree, so a beta-derived "
            "number carries that spread",
        ))
    return rows


def _confidence_referee_rows(record, referee) -> list:
    """The referee extraction against this record's |S11|: agreement, then trust."""
    s11 = record.get("s11")
    s11 = s11 if isinstance(s11, dict) else {}
    geometry = record.get("geometry")
    geometry = geometry if isinstance(geometry, dict) else {}
    label = "referee: |S11| agreement"
    if not isinstance(referee, dict):
        return [(
            label,
            f"not available ({REFEREE_S11_FILE} was not read beside this dump)",
        )]
    here_f = _finite(_as_float(geometry.get("f", geometry.get("f_hz"))))
    ref_f = _finite(_as_float(referee.get("f_hz")))
    magnitude = _finite(_as_float(s11.get("magnitude")))
    theirs = _finite(_as_float(referee.get(REFEREE_S11_KEY)))
    if magnitude is None or theirs is None or theirs == 0.0:
        return [(
            label,
            "n/a (this record's s11.magnitude or the referee's "
            f"{REFEREE_S11_KEY} is missing)",
        )]
    if ref_f is not None and here_f is not None and ref_f != here_f:
        return [(
            label,
            f"not comparable: the referee recorded {_confidence_ghz(ref_f)} and "
            f"this record {_confidence_ghz(here_f)} - two frequencies are two "
            "|S11| values, and one is not a check on the other",
        )]
    rows = [(
        label,
        f"{100.0 * abs(magnitude / theirs - 1.0):.2f} % (this record "
        f"s11.magnitude = {magnitude:.6f} vs the referee's {REFEREE_S11_KEY} = "
        f"{theirs:.6f}, deviation = |a/b - 1|, both at {_confidence_ghz(here_f)})"
        " - an independent EXTRACTION, not a validation: see the mode fit below",
    )]
    ok = referee.get("mode_fit_ok")
    ratio = _finite(_as_float(referee.get("mode_fit_ratio")))
    tol = _finite(_as_float(referee.get("mode_fit_tol")))
    if ratio is not None:
        verdict = (
            "the referee's own mode solve met its tolerance"
            if ok is True
            else "the referee's own mode solve missed tolerance, so its |S11| is "
            "a second opinion and not a reference"
        )
        tol_text = "not recorded" if tol is None else f"{tol:g}"
        rows.append((
            "referee: mode fit",
            f"{'ok' if ok is True else 'FAILED'} (mode_fit_ok = {ok!r}, "
            f"mode_fit_ratio = {ratio:.2f} against mode_fit_tol = {tol_text}) - "
            f"{verdict}",
        ))
    return rows


def _confidence_extraction_rows(record) -> list:
    """What the extraction did NOT record, and the two counts that differ."""
    s11 = record.get("s11")
    s11 = s11 if isinstance(s11, dict) else {}
    line = record.get("line")
    line = line if isinstance(line, dict) else {}
    run = record.get("run")
    station = run.get("station_fit") if isinstance(run, dict) else None
    station = station if isinstance(station, dict) else {}
    rows = [(
        "extraction: fit residual",
        "not serialised - emfit/ports.py drops BetaFit.residual when the record is "
        "written, so this file carries no residual and the fit's goodness cannot "
        "be read off it",
    )]
    sigma = line.get("sigma_beta_from_curvature")
    sigma_number = _finite(_as_float(sigma))
    if isinstance(sigma, str) and sigma_number is None:
        sigma_text = (
            f"{sigma!r} recorded as TEXT (line.sigma_beta_from_curvature) - a "
            "word, not a number: there is no error bar on beta to quote"
        )
    elif sigma_number is None:
        sigma_text = "not recorded (no line.sigma_beta_from_curvature key)"
    else:
        sigma_text = (
            f"{sigma_number:.6f} (line.sigma_beta_from_curvature) - the fit's own "
            "error bar on beta"
        )
    rows.append(("extraction: beta sigma from curvature", sigma_text))
    status = s11.get("validation_status")
    status_text = (
        status.strip() if isinstance(status, str) and status.strip() else "not recorded"
    )
    reason = s11.get("validation_reason")
    if isinstance(reason, str) and reason.strip():
        one_line = " ".join(reason.split())
        if len(one_line) > 140:
            one_line = one_line[:137].rstrip() + "..."
        status_text += (
            f": {one_line!r} (one line of prose copied from the record, not a "
            "serialised field)"
        )
    rows.append(("extraction: |S11| validation status", status_text))
    phasors = s11.get("station_phasors")
    phasors = _as_int(phasors.get("n")) if isinstance(phasors, dict) else None
    fit_n = _as_int(line.get("station_fit_n"))
    span = _confidence_mm(line.get("station_fit_span_m"))
    parts = []
    if phasors is not None:
        parts.append(f"{phasors} phasors recorded (s11.station_phasors.n)")
    if fit_n is not None:
        parts.append(f"{fit_n} stations in the fit (line.station_fit_n, span {span})")
    if parts:
        excluded = line.get("load_station_excluded")
        tail = ""
        if excluded is True:
            tail = (
                " - line.load_station_excluded = True: one station is dropped, so "
                "the two counts measure different things"
            )
        rows.append(("extraction: stations", "; ".join(parts) + tail.rstrip(".")))
    if "z0_re" in line or "z0_re" in station:
        rows.append((
            "extraction: Z0 (which one was consumed)",
            f"the fit consumed run.station_fit.z0 = "
            f"{_confidence_z0(station.get('z0_re'), station.get('z0_im'))}; "
            f"line.z0 = {_confidence_z0(line.get('z0_re'), line.get('z0_im'))} is "
            "the port-plane V/I ratio and was NOT used by the fit - a z0 quoted "
            "without its key is ambiguous",
        ))
    return rows


def _confidence_caveat_rows(record) -> list:
    """Provenance, the frequency actually run, and the acceptance-criteria tally."""
    geometry = record.get("geometry")
    geometry = geometry if isinstance(geometry, dict) else {}
    meta = record.get("meta")
    meta = meta if isinstance(meta, dict) else {}
    rows = []
    here_hz = _finite(_as_float(geometry.get("f", geometry.get("f_hz"))))
    target_hz = _finite(_as_float(geometry.get("f_target")))
    if here_hz is not None:
        text = _confidence_ghz(here_hz) + " recorded (geometry.f)"
        if target_hz:
            text += (
                f" against a {_confidence_ghz(target_hz)} target "
                f"(geometry.f_target): {100.0 * (here_hz / target_hz - 1.0):+.2f} %"
            )
        text += " - every number on this panel is at the RECORDED frequency"
        rows.append(("frequency actually run", text))
    git_rev = meta.get("git_rev")
    if isinstance(git_rev, str) and git_rev.strip():
        rows.append((
            "provenance: commit",
            f"meta.git_rev = {git_rev.strip()!r}"
            + (
                f", finished {meta['finished_utc']}"
                if isinstance(meta.get("finished_utc"), str)
                else ""
            ),
        ))
    else:
        rows.append((
            "provenance: commit",
            f"meta.git_rev = {git_rev!r} - no commit was recorded, so this "
            "artefact cannot be tied to a revision",
        ))
    criteria = record.get("ac")
    if isinstance(criteria, dict) and criteria:
        passed, failed, unknown, partial = [], [], [], []
        for key, item in criteria.items():
            verdict = item.get("pass") if isinstance(item, dict) else None
            if verdict is True:
                passed.append(str(key))
                if isinstance(item, dict) and item.get("pass_scope"):
                    partial.append(str(key))
            elif verdict is False:
                failed.append(str(key))
            else:
                unknown.append(str(key))
        text = (
            f"{len(passed)} pass / {len(failed)} fail / {len(unknown)} "
            f"indeterminate of {len(criteria)} (counted from the ac block: pass "
            f"True on {', '.join(passed) or 'none'}; False on "
            f"{', '.join(failed) or 'none'}; null on {', '.join(unknown) or 'none'})"
        )
        if partial:
            text += f"; partial: {', '.join(partial)} (pass_scope)"
        rows.append(("acceptance criteria", text))
    else:
        rows.append(("acceptance criteria", "not recorded in this file"))
    return rows


def build_confidence_block(record, referee=None, record_path=None) -> dict:
    """The Confidence & Accuracy panel as DATA: rows, caption, basis, sources.

    ``record`` is a study record already parsed (the reviewer's own JSON, or
    None when the dump was shipped without one); ``referee`` is the parsed
    referee extraction or None. NO file is read here, so this is a pure function
    and a test can hand it a record with numbers of its own.

    Returns ``{"status", "rows", "caption", "basis", "sources"}``: ``rows`` is
    a list of ``(label, text)`` pairs in reading order, ``basis`` the formulas
    used and ``sources`` the keys read. NEVER raises: a panel is never worth a
    traceback, and a refusal is one of its answers.
    """
    try:
        if not isinstance(record, dict) or not record:
            return {
                "status": "no record",
                "rows": [],
                "caption": "confidence refused: no study record beside this dump",
                "basis": [],
                "sources": [],
            }
        rows = []
        rows.extend(_confidence_mesh_rows(record))
        rows.extend(_confidence_resolution_rows(record))
        rows.extend(_confidence_referee_rows(record, referee))
        rows.extend(_confidence_extraction_rows(record))
        rows.extend(_confidence_caveat_rows(record))
        return {
            "status": "ok",
            "rows": rows,
            "caption": (
                "every row is derived from the study record beside this dump; "
                "each names its own basis. A value that reads ABSENT or "
                "'not serialised' is MISSING FROM THE FILE, not zero."
            ),
            "basis": [
                "cells per wavelength = (2*pi/beta) / cell_m: lambda from the "
                "RECORDED beta, counted in mesh cells",
                "mesh product = nx*ny*nz, compared with the recorded geometry.cells",
                "beta spread = (line.beta / line.beta_model - 1) * 100",
                f"referee deviation = |s11.magnitude / {REFEREE_S11_KEY} - 1| * 100, "
                "at the referee's own recorded f_hz",
                "frequency deviation = (geometry.f / geometry.f_target - 1) * 100",
                "acceptance tally = count of ac[*].pass over True / False / null",
            ],
            "sources": [
                f"record: {record_path or 'in memory'}",
                f"referee: {REFEREE_S11_FILE} as {REFEREE_S11_KEY}",
                "geometry.cell_m, geometry.grid, geometry.cells, geometry.f, "
                "geometry.f_target",
                "line.beta, line.beta_model, line.sigma_beta_from_curvature, "
                "line.station_fit_n, line.load_station_excluded, line.z0_re, "
                "line.z0_im",
                "run.station_fit.z0_re, run.station_fit.z0_im",
                "s11.magnitude, s11.validation_status, s11.validation_reason, "
                "s11.station_phasors.n",
                "ac.*.pass, meta.git_rev",
            ],
        }
    except Exception as exc:  # noqa: BLE001 - the panel is not the page
        return {
            "status": "unavailable",
            "rows": [],
            "caption": f"confidence unavailable: {type(exc).__name__}: {exc}",
            "basis": [],
            "sources": [],
        }


def _multifreq_block(path):
    """The sweep as recorded, or None when no row could be read."""
    data = _read_json(path) if path is not None else None
    if not isinstance(data, dict):
        return None
    points, _skipped = _multifreq_points(data)
    if not points:
        return None
    return {
        "file": str(path),
        "bin_spacing_mhz": _as_float(data.get("bin_spacing_mhz")),
        "k_values": [point["k"] for point in points if point["k"] is not None],
        "ambiguous_bins": [
            point["k"]
            for point in points
            if point["beta_ambiguous"] and point["k"] is not None
        ],
        "points": [
            {
                "f_ghz": point["f_ghz"],
                "s11": point["s11"],
                "s21": point["s21"],
                "artefact": point["artefact"],
                "k": point["k"],
                "beta_ambiguous": point["beta_ambiguous"],
                "beta": point["beta"],
                "beta_model": point["beta_model"],
            }
            for point in points
        ],
    }


def _chart_block(multifreq, structure) -> dict:
    """What the chart DOES: discrete markers at recorded frequencies only."""
    points = [] if multifreq is None else [
        [point["f_ghz"], point["s11"], point["s21"]]
        for point in multifreq["points"]
    ]
    ambiguous = [] if multifreq is None else [
        point["f_ghz"] for point in multifreq["points"] if point["beta_ambiguous"]
    ]
    return {
        "mode": "markers-only",
        "interpolation": False,
        "title": _chart_title(structure),
        "points": points,
        "ambiguous_marked": ambiguous,
    }


def _mismatch_banner_text(mismatch):
    """The exact banner sentence, or None when there is nothing to warn about."""
    if not isinstance(mismatch, dict) or not mismatch.get("flag"):
        return None
    return (
        f"WARNING Field dump ({mismatch['field_cells']}) and S-parameters "
        f"({mismatch['sparams_cells']}) are from different runs. "
        "Nothing below is one solve."
    )


def _finite(value):
    """A float for JSON, or None when it is not finite.

    Strict JSON has no NaN and no Infinity, and the state dump is parsed by
    readers that reject both. A number that is not finite is reported as null,
    which is the same thing this document already says for unparseable records.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


VIS_EXTENT_BASIS = (
    "extent_domain_mm is cells x cell (the simulated box); extent_sampled_mm is "
    "the span of the stored node coordinates x_mm / y_mm / z_mm. A vis dump "
    "is a dense cube, so the two differ by one cell per axis and never by a "
    "factor; there is no captured-plane quantisation in this artefact."
)


def _vis_cut_station_block(info: dict, cell_mm: float) -> dict:
    """The x-z sheet's fixed y, in this document's own null-plus-reason form.

    The dump records the y SAMPLE INDEX ``j_cut`` the sheet was taken from, and
    that index is the only thing that may be turned into millimetres here. When
    it is absent the number is null and ``y_note`` says why - the same shape
    ``geometry_mm.strip_y`` already uses for a position the dump does not carry,
    and for the same reason: a state dump that printed y = 0.0 for a station
    nothing recorded is a position invented by the reader.
    """
    station = _finite(info.get("j_cut"))
    if station is None:
        return {
            "y": None,
            "y_note": (
                "not recorded - the dump carries no j_cut, so the y station "
                "of the x-z sheet is unknown and no sheet is drawn at one"
            ),
        }
    return {"y": round(float(int(station)) * cell_mm, 9)}


def _vis_field_block(info: dict, path: Path) -> dict:
    """The animation's own field block: a dense cube, so the extents agree.

    Same keys as _field_dump_block so one reader can read both documents, but the
    sampled span is read from the stored coordinate arrays instead of from a
    captured-plane count: this dump holds nx x ny x nz nodes on x_mm / y_mm /
    z_mm, which is what the animation interpolates over.
    """
    cell_mm = _cell_mm(info)
    nx, ny, nz = int(info["nx"]), int(info["ny"]), int(info["nz"])
    x_mm, y_mm, z_mm = info["x_mm"], info["y_mm"], info["z_mm"]

    def _span(axis) -> float:
        return float(np.max(axis) - np.min(axis)) if axis.size else 0.0

    return {
        "file": str(path),
        "cells": {"nx": nx, "ny": ny, "nz": nz},
        "cell_m": float(info["cell_m"]),
        "grid_cell_mm": round(cell_mm, 9),
        "extent_domain_mm": {
            "x": round(nx * cell_mm, 9),
            "y": round(ny * cell_mm, 9),
            "z": round(nz * cell_mm, 9),
        },
        "extent_sampled_mm": {
            "x": round(_span(x_mm), 9),
            "y": round(_span(y_mm), 9),
            "z": round(_span(z_mm), 9),
        },
        "extent_basis": VIS_EXTENT_BASIS,
        "stations_x_mm": [float(value) for value in x_mm],
        "n_stations": nx,
        "nstep": int(info["nstep"]),
    }


def _animation_block(info: dict, fps: int = DEFAULT_FPS) -> dict:
    """What the animation adds to the state dump: frames, time, scale, geometry.

    ``fps`` is a VIEWING choice and is labelled as one: ``wall_clock_s`` is how
    long the page will take to play the dump once, while ``sim_time_ns`` is the
    dump's own simulation clock. Letting the two be read as one number is how a
    reader comes to believe the solver ran at 24 frames per second.
    """
    fps = max(1, int(fps))
    vmin, vmax = info["color_range"]
    dt_ns = float(info["dt_s"]) * 1e9
    nt = int(info["nt"])
    t_ns = info["t_ns"]
    cell_mm = _cell_mm(info)
    return {
        "frames": nt,
        "frames_xcut": int(info["nt_x"]),
        "fps": fps,
        "wall_clock_s": round(nt / float(fps), 6),
        "sim_time_ns": {
            "first": _finite(t_ns[0]) if t_ns.size else None,
            "last": _finite(t_ns[-1]) if t_ns.size else None,
            "dt": _finite(dt_ns),
            "basis": (
                "t_ns = frame_index * dt_s; the two x-cut planes are written every "
                "dump_stride * 10 steps and carry their own frame_index_xcut, so "
                "their frame number must never be used to index t_ns"
            ),
        },
        "colour": {
            "vmin": _finite(vmin),
            "vmax": _finite(vmax),
            "percentile": COLOR_PERCENTILE,
            "empty": bool(info["color_range_empty"]),
            "basis": (
                "one limit for every frame of every plane: the "
                f"{COLOR_PERCENTILE:g}th percentile of |Ez| over all stored frames; "
                "a per-frame maximum would renormalise each step and hide the decay"
            ),
        },
        "planes": [
            {
                "key": "ez_ycut",
                "label": "x-z plane through the strip (one fixed y sample)",
                "shape": [int(n) for n in info["ez_ycut"].shape],
                "frames": nt,
                "fixed_mm": _vis_cut_station_block(info, cell_mm),
            },
            {
                "key": "ez_xcut_near",
                "label": "y-z plane at the near x-cut",
                "shape": [int(n) for n in info["ez_xcut_near"].shape],
                "frames": int(info["nt_x"]),
                "fixed_mm": {"x": _finite(info["xcut_near_mm"])},
            },
            {
                "key": "ez_xcut_far",
                "label": "y-z plane at the far x-cut",
                "shape": [int(n) for n in info["ez_xcut_far"].shape],
                "frames": int(info["nt_x"]),
                "fixed_mm": {"x": _finite(info["xcut_far_mm"])},
            },
        ],
        "geometry_mm": {
            "port_x": _finite(info["port_x_mm"]),
            "load_x": _finite(info["load_x_mm"]),
            "substrate_h": _finite(info["substrate_h_mm"]),
            "strip_w": _finite(info["strip_w_mm"]),
            # Not in the dump: the strip's y offset. The overlay centres it and
            # the page says so rather than implying a recorded position.
            "strip_y": "not recorded - the overlay centres the strip on the grid",
        },
        "velocity": {
            "analytic_m_s": _finite(info["v_analytic_m_s"]),
            "measured_m_s": _finite(info["v_measured_m_s"]),
            "reliable": bool(info["v_measured_reliable"]),
            "t_traverse_ns": _finite(info["t_traverse_ns"]),
            "note": info["velocity_note"],
        },
        "frequencies_hz": {
            "f_ref": _finite(info["f_ref_hz"]),
            "f_pulse": _finite(info["f_pulse_hz"]),
        },
    }


def build_state_dump(info: dict, structure, structures=None, fps: int = DEFAULT_FPS) -> dict:
    """The whole page state as one JSON document, numpy-only.

    A report, not a picture: it lists the artefacts this page would composite, the
    cell count each one is on, and the seam between them. Anything unparseable is
    null - a state dump that invents a number to look complete is the defect this
    document exists to expose.
    """
    path = Path(info["path"])
    entry = structure if isinstance(structure, dict) else {}
    field_block = (
        _vis_field_block(info, path)
        if _is_vis(info)
        else _field_dump_block(info, path)
    )
    sparams_path = _sparams_path(path, entry)
    sparams = _sparams_block(sparams_path)
    record = _field_record(path)
    field_text = _cells_as_text(field_block["cells"])
    sparams_text = _cells_as_text(sparams["cells"])
    mismatch = _mismatch_block(
        field_text, sparams_text, _n_line(record), sparams["n_line"]
    )
    multifreq = _multifreq_block(
        _multifreq_path(path, entry, info.get("structure_id")))
    port_waves, port_reason = _port_waves_block(sparams_path)
    page = {
        "schema": STATE_SCHEMA_VIS if _is_vis(info) else STATE_SCHEMA,
        "generated_utc": _utc_now(),
        "head_commit": _git_head_short(),
        "structure": {
            "id": entry.get("id"),
            "label": entry.get("label"),
            "status": entry.get("status"),
            "notes": entry.get("notes"),
        },
        "input_npz": str(path),
        "field_dump": field_block,
        "sparams": sparams,
        "mismatch": mismatch,
        "residuals": _residuals_block(entry.get("anchors"), sparams["s11_two_wave"]),
        "multifreq": multifreq,
        "port_waves": port_waves,
        # Not in the spec's key list, and deliberately so: the spec asks for
        # port_waves OR null plus a reason, and a sibling key is the only place a
        # null can carry one without changing port_waves' own shape.
        "port_waves_reason": port_reason,
        "chart": _chart_block(multifreq, entry),
        # Which artefact this document describes. The legacy dump keeps
        # emfit.poc-state/1 byte-for-byte; a vis dump is /3, because it adds the
        # keys below (format/animation under /2, load_series beside its reason
        # under /3) and reads field_dump's extents off stored nodes.
        "format": VIS_FORMAT if _is_vis(info) else "legacy",
        "animation": _animation_block(info, fps) if _is_vis(info) else None,
    }
    # The load's own V(t)/I(t) trace, added on the vis branch only - the same rule
    # the format/animation keys above follow, and the reason STATE_SCHEMA_VIS is
    # now /3: a document that gained a KEY gained a version, while the legacy dump
    # (which carries no trace to add) stays /1 exactly.
    if _is_vis(info):
        page["load_series"] = info.get("load_series")
        # A sibling slot, exactly as port_waves_reason is a sibling of port_waves:
        # a null trace has to carry the sentence saying why, and it must not be
        # folded into the block's own shape. Nothing is defaulted here - load_vis
        # always sets the reason beside the block, so a missing key means a dump
        # from a build that did not, and null is the honest value for it.
        page["load_series_reason"] = info.get("load_series_reason")
    return page


def _station_axis_mm(info: dict, record=None) -> tuple:
    """Resolve the x of each captured station, in mm, plus where the axis came from.

    Returns ``(stations_mm, src)``.  ``src`` names the key the axis was read
    from, or states that the axis is an ASSUMPTION, so the UI can print the
    provenance beside the numbers instead of a position nobody recorded.

    WHY an index is not an x: the study snaps each WANTED station to the nearest
    grid cell (``emfit/studies.py`` around :3258, ``js = floor(wanted/cell+0.5)``),
    so the nine Build A stations are cells 26, 29, 32 ... 50 - 1.2 mm apart
    starting at 10.4 mm - and NOT one cell apart starting at 0.  ``i * cell_mm``
    is therefore a shape-only guess that draws the whole captured slab over the
    port end of the line, so the axis is read from the artefacts instead:

    1. ``info["station_x_m"]`` (metres, written by the dump itself);
    2. ``record["s11"]["station_phasors"]["x_m"]`` (metres);
    3. ``record["geometry"]["station_cells"]`` (cell indices, times the cell);
    4. ``record["line"]["station_fit_cells"]`` (cell indices, same length only);
    5. ``[i * cell_mm]`` - the uniform stack, marked ASSUMED in ``src``.

    A step is accepted only when it is a real sequence of ``n_st`` finite
    numbers; anything else (missing key, non-dict record, a string, a scalar, a
    sequence of the wrong length - ``line.station_fit_cells`` has 8 entries for
    9 stations because it drops the load station) falls through.  NEVER raises.
    """
    n_st = int(info[PLANE_KEY].shape[0])
    cell_mm = _cell_mm(info)

    def _as_axis(values, scale_mm):
        """``values`` times ``scale_mm`` as mm, or None if that is not an axis."""
        if values is None or isinstance(values, (str, bytes, dict)):
            return None
        try:
            axis = [float(v) * scale_mm for v in values]
        except (TypeError, ValueError):
            return None
        if len(axis) != n_st or not bool(np.all(np.isfinite(axis))):
            return None
        return axis

    def _dig(block, *keys):
        """``block[key0][key1]...``, or None as soon as a level is not a dict."""
        for key in keys:
            if not isinstance(block, dict):
                return None
            block = block.get(key)
        return block

    for values, scale_mm, src in (
        (info.get("station_x_m"), 1e3, "station_x_m"),
        (_dig(record, "s11", "station_phasors", "x_m"), 1e3,
         "s11.station_phasors.x_m"),
        (_dig(record, "geometry", "station_cells"), cell_mm,
         "geometry.station_cells"),
        (_dig(record, "line", "station_fit_cells"), cell_mm,
         "line.station_fit_cells"),
    ):
        axis = _as_axis(values, scale_mm)
        if axis is not None:
            return axis, src

    # The stated assumption, not a measurement: one cell per station from x = 0.
    return [i * cell_mm for i in range(n_st)], (
        "ASSUMED uniform i*cell (no station axis recorded)"
    )


def _geom_mm(info: dict, record, x_s21_mm=None, x_s21_src=None) -> dict:
    """The structure's millimetres, and where each number came from.

    WHY this function exists: the numbers that place the board in space sit in
    two artefacts that use two units. A vis/engine dump carries them as npz
    scalars already in MILLIMETRES (substrate_h_mm, strip_w_mm, port_x_mm,
    load_x_mm, xcut_near_mm), while the study record beside it carries the same
    board under ``geometry`` in METRES (h, w, cell, length, width, height, and
    the port as the CELL INDEX ix_port). Mixing the two is a silent 1000x
    error, so the one multiplication by 1e3 lives here and nowhere else: a
    caller gets millimetres from one function and never reads ``geometry``
    itself. A dump written by the FIELD-snapshot exporter has NONE of the npz
    keys - which is the case this function exists for, because without the
    record the 3-D overlay has no board to draw on and silently disappears.

    WHY a missing number is None and never a constant: a substrate height of 0
    or a port at x = 0 is a claim about the board that neither the dump nor the
    record supports, and a fabricated number becomes indistinguishable from a
    measured one the moment it reaches the picture. None forces the draw site
    to name the absence instead of drawing a board that was never recorded.

    WHY ix_port and loads[0].x are converted differently: ix_port is a cell
    INDEX, so it becomes a length by multiplying by the cell size, while
    loads[0].x is already a length in metres and needs only the 1e3 unit
    change. ``src`` records which route each number took, so the page can print
    the provenance rather than asserting a position, and each label names the
    route ACTUALLY taken - including when that route is the fallback constant
    rather than the record, which is why the caller that substitutes one hands
    its own label in beside the value.

    NEVER raises: a non-dict record, a non-list ``loads``, a string where a
    number belongs, NaN and inf all fall through to the next source, and the
    final answer for that key is None.
    """

    def _num(value):
        """A finite float, or None. Never raises on a string, NaN or inf."""
        number = _as_float(value)
        if number is None:
            return None
        return number if _finite(number) is not None else None

    keys = (
        "cell_mm",
        "substrate_h_mm",
        "strip_w_mm",
        "port_x_mm",
        "load_x_mm",
        "xcut_near_mm",
        "length_mm",
        "width_mm",
        "height_mm",
    )
    out = {key: None for key in keys}
    src = {key: "absent" for key in keys}

    info_d = info if isinstance(info, dict) else {}
    record_d = record if isinstance(record, dict) else {}
    geom = record_d.get("geometry")
    if not isinstance(geom, dict):
        geom = {}

    def _take(key, value, origin):
        """The first finite source wins; a later source cannot overwrite it."""
        if out[key] is None:
            number = _num(value)
            if number is not None:
                out[key] = number
                src[key] = origin

    def _metres(value):
        """A record length in METRES as millimetres, or None."""
        number = _num(value)
        return None if number is None else number * 1e3

    # 1. The dump's own scalars, which are already millimetres, key for key.
    for key in (
        "substrate_h_mm",
        "strip_w_mm",
        "port_x_mm",
        "load_x_mm",
        "xcut_near_mm",
    ):
        _take(key, info_d.get(key), f"info.{key}")
    # ``cell`` is the one dump number stored in metres (cell_m), so it goes
    # through the same helper the rest of the page uses for that key.
    try:
        _take("cell_mm", _cell_mm(info_d), "info.cell_m")
    except Exception:  # noqa: BLE001 - a dump without cell_m still has a record
        pass

    # 2. The record's geometry, which is metres and needs the 1e3.
    for key, field in (
        ("cell_mm", "cell"),
        ("substrate_h_mm", "h"),
        ("strip_w_mm", "w"),
        ("length_mm", "length"),
        ("width_mm", "width"),
        ("height_mm", "height"),
    ):
        _take(key, _metres(geom.get(field)), f"geometry.{field}")

    # 3. The two positions the record stores in different forms. The port is a
    # CELL INDEX, so it needs the cell size; the load is a LENGTH in metres,
    # and only falls back to its column index when the x was not written.
    cell_mm = out["cell_mm"]
    if cell_mm is not None:
        ix_port = _num(geom.get("ix_port"))
        if ix_port is not None:
            _take("port_x_mm", ix_port * cell_mm, "geometry.ix_port*cell")
    loads = geom.get("loads")
    first = (
        loads[0]
        if isinstance(loads, list) and loads and isinstance(loads[0], dict)
        else {}
    )
    _take("load_x_mm", _metres(first.get("x")), "geometry.loads[0].x")
    if cell_mm is not None:
        column = _num(first.get("column"))
        if column is not None:
            _take(
                "load_x_mm",
                column * cell_mm,
                "geometry.loads[0].column*cell",
            )

    # 4. The near cut plane has no record field at all - it is a viewer choice -
    # so the only other place its x exists is the S21 extraction plane. The
    # default names the documented route for a caller that passes only the
    # value; the caller that knows better passes its own label, so a FALLBACK
    # constant is never reported as a recorded plane.
    _take("xcut_near_mm", x_s21_mm, x_s21_src or "s21_plane.x_m")

    out["src"] = src
    return out


def _plane_layout(info: dict, record) -> dict:
    """Resolve the x of the load, S11 port and S21 planes, in mm.

    Each value carries the record key it came from (``src_*``) so the UI can
    print the provenance instead of asserting a position. Priority is always
    recorded metres > recorded column index times cell size > FALLBACK constant.
    It also carries the STRUCTURE's millimetres (substrate height, strip width,
    port/load x, line length/width/height) under ``geometry_mm`` for the 3-D
    overlay, because the field-snapshot dump does not record them and the
    record does; they ride in this dict rather than in a new argument because
    ``_draw_scene`` and ``_vis_geometry`` already receive ``planes``, and
    threading a ``record`` parameter through ``_redraw_scene`` and every caller
    would change four signatures to move one dict.
    """
    n_st = int(info[PLANE_KEY].shape[0])
    cell_mm = _cell_mm(info)
    # The station axis is READ, never derived from the index: see
    # _station_axis_mm for why ``i * cell`` is not where the stations are.
    stations_mm, stations_src = _station_axis_mm(info, record)

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
    # The stations are NOT one cell apart from x = 0 - they are snapped to cells
    # 1.2 mm apart from 10.4 mm (see _station_axis_mm) - so the nearest captured
    # plane is the first station and not the origin.
    slice_index = min(range(n_st), key=lambda i: abs(stations_mm[i] - x_s11))

    # The board's own millimetres, resolved ONCE and after ``x_s21`` has its
    # final value: ``xcut_near_mm`` borrows that x when the dump did not record
    # one, so a layout resolved before the S21 plane settles would report the
    # near cut as absent on a dump that does carry it.
    geometry_mm = _geom_mm(info, record, x_s21_mm=x_s21, x_s21_src=src_s21)

    return {
        "cell_mm": cell_mm,
        "n_st": n_st,
        "stations_mm": stations_mm,
        "stations_src": stations_src,
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
        "geometry_mm": geometry_mm,
        "geometry_src": geometry_mm["src"],
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
        if planes.get("src_s11") == "FALLBACK":
            # The x above is NOT a measured position: the record carries no port
            # plane, so it falls back to the constant. Say it here, in the same
            # suffix style as the other caveats on this label, so the number is
            # not read as something the study recorded.
            label += (
                "  (port x is the FALLBACK constant "
                f"{FALLBACK_S11_MM:g} mm: the record has no port plane)"
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
# Two sliders pick ONE y sample and ONE z sample of the field on screen and draw
# the sheet through them, so the field can be read on a slice instead of through
# a volume.
#
# WHICH field they cut is not a detail: the COLOCATED |E| volume when the dump
# carries one - the lattice the solve actually produced, every sample a cell
# centre half a cell in on each axis - so the cuts and the |E| volume drawn
# beside them are the same samples of the same grid and cannot disagree about
# where a feature is. Only when the dump carries no volume does the layer fall
# back to the 9 captured x-planes over a 213 x 22 (y, z) cross section, which is
# the |Ez| picture this layer has always drawn. ``_cut_layout`` names the choice
# in its ``source`` key, ``_cut_text`` says it in the slider row,
# ``build_cut_sheets`` builds the matching sheets, and ``_cut_axis_counts`` is
# what makes the two sliders span the grid they actually index.
#
# WHY one sample thick and not a resample: the dump holds exactly these samples,
# so a cut through them is recorded data. A resampled cut would be a picture of a
# number nobody computed - the same reason the module docstring refuses to
# invent x between the 9 stations.
#
# The trap this layer has to avoid is a marker that LOOKS like it belongs to a
# cut. The S11 / load / S21 markers sit at mid-height of the y-z section and at
# x = 3.2, 20.0 and 20.4 mm. With the volume the sheets span the volume's OWN x
# extent (half a cell to ``(nx - 0.5)`` cells), so a marker is inside the slab
# exactly when its x is on the grid at all; on the FALLBACK path they span only
# the captured slab (x = 10.4 .. 20.0 mm), so the port and the S21 plane are off
# every sheet by construction. Nothing is moved, clipped or projected to make
# them fit - each marker's relation to the drawn cuts is stated in the corner
# legend instead, because a marker drawn at the edge of a sheet would be a lie
# about where the plane is. That fallback slab is the RECORDED station axis when
# the caller resolved one (``_station_axis_mm``), never ``(n_st - 1) * cell``.


def _volume_grid_dims(info: dict, grid_hint=None):
    """The ``(nx, ny, nz)`` lattice the colocated volume sits on, or None.

    ONE predicate for "does this dump carry a volume, and on which grid": the cut
    sliders read it to decide whether they slice |E| or the captured plane stack,
    and ``_volume_abs_grid`` reads it for the very same counts, so a cut sheet
    and the volume it cuts can never be built on two different lattices.

    None is the answer to two different causes and that is deliberate: no volume
    at all, and a volume whose grid nobody stated. Both mean "index the plane
    stack instead", which is the only thing a caller can do with either;
    ``_volume_abs_grid`` is the one that separates them in a sentence.

    WHY the ``nx``/``ny``/``nz`` keys alone are NOT enough: the loader publishes
    them beside the raw stash of every dump, including the ones whose volume was
    never kept, so reading them here would retarget the sliders onto a grid that
    carries no field. A volume has to be PRESENT first; the counts are read
    after it.

    Cheap on purpose - dict reads, no colocation, no pyvista import - because it
    runs on every slider construction and every redraw.
    """
    if not isinstance(info, dict):
        return None
    # The memo first: a page that already drew |E| states the lattice on the
    # image itself, and that is the strongest answer available.
    cached = info.get(VOLUME_ABS_KEY)
    if isinstance(cached, dict) and cached.get("image") is not None:
        try:
            dims = tuple(int(v) for v in cached["image"].dimensions)
        except (AttributeError, TypeError, ValueError):
            dims = None
        if dims is not None and len(dims) == 3 and min(dims) > 0:
            return dims
    raw = info.get(VOLUME_RAW_KEY)
    if info.get(VOLUME_KEY) is None and not (
        isinstance(raw, dict) and raw.get("e") is not None
    ):
        return None
    # The dump's own metadata first, then the record's ``geometry.grid``, and
    # never ``e.size``: the raw vector is staggered, so its length counts EDGES.
    for source in (info, grid_hint):
        try:
            if isinstance(source, dict):
                triple = (source.get("nx"), source.get("ny"), source.get("nz"))
            elif source is None:
                continue
            else:
                triple = tuple(source)[:3]
            dims = tuple(int(v) for v in triple)
        except (TypeError, ValueError):
            dims = None
            continue
        if len(dims) == 3 and min(dims) > 0:
            return dims
    return None


def _cut_layout(info: dict, j_cut=None, k_cut=None, stations_mm=None) -> dict:
    """Resolve which y and z sample the cut sheets sit on. Numbers only.

    Split out from build_cut_sheets so the labels, the legend and the slider
    handlers can describe the cuts without importing pyvista.

    WHICH grid the ``j`` / ``k`` index is ``source`` - the colocated |E| volume
    when the dump carries one (:func:`_volume_grid_dims`), the captured plane
    stack otherwise - and the two differ in more than their counts:

        volume : (j, k) index the volume's own (ny, nz) lattice and every sample
                 is a CELL CENTRE, so the cut sits at ``(j + 0.5) * cell`` and
                 the sheets span the volume's x extent, half a cell in at both
                 ends - the same anchor the volume is drawn at.
        planes : (j, k) index the captured (n_j, n_k) plane and the cut sits at
                 ``j * cell``, the corner of the cell the plane holds.

    ``stations_mm`` is the recorded station axis and only the PLANE fallback
    uses it: those sheets span the FIRST and LAST captured station on x, so
    ``x_lo_mm`` / ``x_hi_mm`` and the per-step ``dx_mm`` they use come from it.
    Without it the fallback keeps the old uniform span of ``0`` to
    ``(n_st - 1)`` cells, which is the same stated assumption the axis makes
    when nothing was recorded. A volume needs neither: its own grid states the
    extent, and it is the same one ``build_grid`` puts the volume on.
    """
    cell_mm = _cell_mm(info)
    dims = _volume_grid_dims(info)
    if dims is not None:
        n_x, n_j, n_k = dims
        n_st = n_x
        x_lo_mm = 0.5 * cell_mm
        x_hi_mm = (n_x - 0.5) * cell_mm
        dx_mm = cell_mm
        source = "volume"
    else:
        plane = info[PLANE_KEY]
        n_st, n_j, n_k = plane.shape
        if stations_mm is None:
            x_lo_mm = 0.0
            x_hi_mm = (n_st - 1) * cell_mm
        else:
            x_lo_mm = float(stations_mm[0])
            x_hi_mm = float(stations_mm[-1])
        dx_mm = (x_hi_mm - x_lo_mm) / (n_st - 1) if n_st > 1 else cell_mm
        source = "planes"
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
    # Half a cell IN for the volume: its samples are cell centres, so a cut
    # quoted at ``j * cell`` would name the cell CORNER, half a cell upstream of
    # the field the volume beside it draws.
    off_mm = 0.5 * cell_mm if source == "volume" else 0.0
    return {
        "cell_mm": cell_mm,
        "source": source,
        "n_st": n_st,
        "n_j": n_j,
        "n_k": n_k,
        "j": j,
        "k": k,
        "y_mm": j * cell_mm + off_mm,
        "z_mm": k * cell_mm + off_mm,
        "x_lo_mm": x_lo_mm,
        "x_hi_mm": x_hi_mm,
        "dx_mm": dx_mm,
    }


def _cut_text(layout: dict) -> str:
    """The slider label: which sample, where it is in mm, and WHICH grid.

    The plane sentence is byte for byte the one this row has always shown; the
    volume path APPENDS why its millimetres are cell centres and not cell
    corners, so an operator reading ``y = 42.6000 mm`` can tell which of the two
    lattices that number is on. ``.get`` because a fake layout may predate the
    key.
    """
    text = (
        f"cut y = {layout['j'] + 1}/{layout['n_j']} "
        f"(y = {layout['y_mm']:.4f} mm)   "
        f"cut z = {layout['k'] + 1}/{layout['n_k']} "
        f"(z = {layout['z_mm']:.4f} mm)   one sample each, no interpolation"
    )
    if layout.get("source") == "volume":
        text += "   (|E| volume cells, cell centres)"
    return text


def _cut_sheet_clim(sheet, scalars: str):
    """One cut sheet's own colour range ``(peak / 1000, peak)``, or None.

    WHY per sheet and not the volume's: a cut is a SUBSET of the field, so its
    own peak is what its samples span, and painting it on the volume's range
    spends the top of the bar on values the sheet does not have - measured on the
    shipped dump at the default cuts: 65.6 V/m on the y cut and 8.2 V/m on the z
    cut against 90.7 V/m in the volume. The 1/1000 ratio is the same 60 dB span
    ``_volume_abs_grid`` uses, for the same reason: |E| spans tens of decades, so
    a linear bar would show the peak and nothing else.

    Read off the SHEET's own array, never off the layout or the volume, so a
    caller cannot be handed a range the sheet does not have. None means the sheet
    carries no finite positive sample; the caller then drops the log scale rather
    than inventing a range, because a fabricated clim is the kind of lie this
    page refuses.
    """
    try:
        values = np.asarray(sheet.point_data[scalars], dtype=float)
    except (KeyError, TypeError):
        return None
    values = values[np.isfinite(values) & (values > 0.0)]
    if values.size == 0:
        return None
    peak = float(values.max())
    return (peak * 1e-3, peak)


def _cut_clim_text(cut_clims: dict) -> str:
    """The corner-legend line naming the range each DRAWN cut was painted on.

    WHY a sentence and not a second colour bar: two bars over one set of colours
    read as two fields. The numbers still have to be somewhere, or a reader cannot
    tell a dark cut from a dim one. ``cut_clims`` is keyed by the axis and holds
    the clim each VOLUME sheet was actually drawn on (None = drawn linear, no
    positive sample); an axis that was never reached (a refused mesh), or that
    was drawn from the plane fallback (which quotes no range), is simply not in
    it.
    """
    parts = []
    for axis in ("y", "z"):
        if axis not in cut_clims:
            continue
        clim = cut_clims[axis]
        if clim is None:
            parts.append(f"{axis} cut on a linear bar (no positive sample)")
        else:
            parts.append(f"{axis} cut {clim[0]:.4g} .. {clim[1]:.4g} V/m (log)")
    if not parts:
        return ""
    return "cut colour ranges: " + ", ".join(parts)


def build_cut_sheets(info: dict, layout: dict) -> list:
    """Build the two cut sheets as one-sample-thick pyvista images.

    Each entry is ``(axis, sheet, clim)``. ``clim`` is the ``(peak / 1000, peak)``
    colour range of THAT sheet's own samples (:func:`_cut_sheet_clim`), or None
    when it holds no finite positive value; the caller paints a volume sheet on it
    and leaves the plane sheet exactly as it has always been drawn (linear, no
    clim), so the no-volume picture does not change.

    WHICH samples they carry follows ``layout["source"]`` (:func:`_cut_layout`):

    * ``"volume"`` - the sheets are SUBSETS of the |E| image the volume view
      draws, so a cut cannot show a sample the volume beside it does not, and no
      second colocation is paid. :func:`_volume_cut_sheets` does that; when the
      volume reader refuses, this falls THROUGH to the plane sheets below rather
      than losing the cuts (the volume is not drawn then either, so the two still
      agree).
    * anything else - the captured plane stack, by the same construction as the
      port-plane view in _draw_scene (one sample drawn one thick), so no new
      primitive is introduced:

        y = j * cell : plane[:, j:j+1, :] -> dims (n_st, 1, n_k), origin y = j*cell
        z = k * cell : plane[:, :, k:k+1] -> dims (n_st, n_j, 1), origin z = k*cell

      Axis 0 is the station axis and stays the x axis of the sheet in both
      cases; VTK wants x to vary fastest, hence the Fortran ravel, as in
      build_grid. Because it is the station axis, its origin is the FIRST
      captured station and its spacing the layout's own ``dx_mm`` - not ``0.0``
      and not the cell: the stations are snapped to cells 1.2 mm apart from
      10.4 mm (see ``_station_axis_mm``), and a sheet drawn from x = 0 would sit
      off the volume.
    """
    if layout.get("source") == "volume":
        sheets = _volume_cut_sheets(info, layout)
        if sheets is not None:
            return [
                (axis, sheet, _cut_sheet_clim(sheet, "e_abs"))
                for axis, sheet in sheets
            ]

    import pyvista as pv

    plane = info[PLANE_KEY]
    n_st, n_j, n_k = plane.shape
    cell_mm = layout["cell_mm"]
    j = int(layout["j"])
    k = int(layout["k"])

    y_sheet = pv.ImageData()
    y_sheet.dimensions = (n_st, 1, n_k)
    y_sheet.spacing = (layout["dx_mm"], cell_mm, cell_mm)
    y_sheet.origin = (layout["x_lo_mm"], j * cell_mm, 0.0)
    y_sheet.point_data["ez_abs"] = np.ascontiguousarray(
        np.abs(plane[:, j : j + 1, :]).ravel(order="F"), dtype=float
    )

    z_sheet = pv.ImageData()
    z_sheet.dimensions = (n_st, n_j, 1)
    z_sheet.spacing = (layout["dx_mm"], cell_mm, cell_mm)
    z_sheet.origin = (layout["x_lo_mm"], 0.0, k * cell_mm)
    z_sheet.point_data["ez_abs"] = np.ascontiguousarray(
        np.abs(plane[:, :, k : k + 1]).ravel(order="F"), dtype=float
    )
    return [
        ("y", y_sheet, _cut_sheet_clim(y_sheet, "ez_abs")),
        ("z", z_sheet, _cut_sheet_clim(z_sheet, "ez_abs")),
    ]


def _volume_cut_sheets(info: dict, layout: dict):
    """The two cuts as SUBSETS of the |E| volume image, or None if it refused.

    Subsets, not rebuilds: ``extract_subset`` keeps the parent's sample values,
    its spacing, its origin - rebased to where the slice actually sits - and the
    ``e_abs`` array NAME, so a sheet carries the field, its lattice and its array
    without this function restating any of them (its COLOUR range is the sheet's
    own, taken by ``build_cut_sheets`` from the samples below). Measured in this
    image on a (5, 4, 3) image at cell 0.4 mm and origin
    (0.2, 0.2, 0.2): the y extent ``(0, 4, 2, 2, 0, 2)`` comes back dims
    (5, 1, 3) at origin (0.2, 1.0, 0.2) - the CELL CENTRE of j = 2, not 0.8 -
    and the z extent ``(0, 4, 0, 3, 1, 1)`` comes back (5, 4, 1) at origin
    (0.2, 0.2, 0.6).

    None means the volume reader produced no image (unusable volume, unusable
    cell, unresolved grid); the caller then draws the plane sheets, which is the
    same picture the volume branch falls back to.
    """
    cell_mm = layout.get("cell_mm") or _cell_mm(info)
    image, _meta = _volume_abs_grid(info, cell_mm)
    if image is None:
        return None
    nx, ny, nz = (int(v) for v in image.dimensions)
    # Clamped against the IMAGE's own counts, not the layout's: the two are built
    # from the same predicate, and a disagreement must cost the frame, not the
    # render (an out-of-range extent raises inside VTK).
    j = max(0, min(ny - 1, int(layout.get("j", ny // 2))))
    k = max(0, min(nz - 1, int(layout.get("k", nz // 2))))
    return [
        ("y", image.extract_subset(voi=(0, nx - 1, j, j, 0, nz - 1))),
        ("z", image.extract_subset(voi=(0, nx - 1, 0, ny - 1, k, k))),
    ]


def _marker_cut_relation(planes: dict, layout: dict) -> list[str]:
    """State, per marker, whether it lies ON a drawn cut sheet or off them.

    The three markers sit at mid-height of the y-z section, so their y and z are
    fixed while the cuts move with the sliders. A marker counts as ON a sheet
    only when its transverse coordinate is within half a cell of the cut AND its
    x is inside that sheet's own x extent; anything else is off, and the reason
    is spelled out. No marker is moved to make it fit.

    The x extent named in that reason is the one the sheets ACTUALLY span, which
    follows ``layout["source"]``: the captured slab for the plane fallback, the
    volume's own grid extent for the volume path.
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
            # WHICH object the x extent belongs to follows the layout's own
            # ``source``: the plane fallback's sheets span the CAPTURED slab (its
            # first and last station), while the volume's sheets span the VOLUME's
            # grid - origin half a cell in, ``(n_x - 0.5) * cell`` out - which is
            # not a captured slab at all. The test that decides ON-ness is the same
            # ``in_slab`` for both, and so is the tolerance; only the noun changes,
            # because naming the wrong object is how a page starts lying about the
            # picture beside it.
            if layout.get("source") == "volume":
                why.append(
                    f"its x = {x_mm:.4f} mm is outside the volume's grid extent "
                    f"{x_lo:.4f}..{x_hi:.4f} mm, so no cut sheet reaches it"
                )
            else:
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


def _print_vis_keys(info: dict) -> None:
    """Print the wave-animation metadata. numpy only - no pyvista, no trame."""
    ycut = info["ez_ycut"]
    near = info["ez_xcut_near"]
    far = info["ez_xcut_far"]
    cell_mm = _cell_mm(info)
    dt_ns = info["dt_s"] * 1e9
    t_ns = np.asarray(info["t_ns"])
    fi = np.asarray(info["frame_index"])
    fx = np.asarray(info["frame_index_xcut"])

    print(f"file        : {info['path']}")
    print(f"format      : wave animation (schema {info['schema']})")
    print(f"engine      : {info['engine']}")
    print(f"created_utc : {info['created_utc']}")
    print(f"ez_ycut     : shape={ycut.shape} dtype={ycut.dtype} (frame, x, z)")
    print(f"ez_xcut_near: shape={near.shape} dtype={near.dtype} (frame, y, z)")
    print(f"ez_xcut_far : shape={far.shape} dtype={far.dtype} (frame, y, z)")
    # The two x-cuts are NOT frames of the y-cut series: they are the same
    # simulation sampled on a coarser, independent schedule.
    print(
        f"x-cut planes: y-z sheets at x={info['xcut_near_mm']:.4f} and "
        f"x={info['xcut_far_mm']:.4f} mm"
    )
    print(f"nx/ny/nz    : {info['nx']} / {info['ny']} / {info['nz']} (cells)")
    print(f"cell_m      : {info['cell_m']:.6e} m  ({cell_mm:.6f} mm)")
    xs, ys, zs = info["x_mm"], info["y_mm"], info["z_mm"]
    # The STORED coordinate arrays are what the planes are sampled on; nx*cell_m
    # is the solver's box and is one cell wider, so both are printed and named.
    print(
        "extent      : "
        + ", ".join(
            f"{name} {axis.min():.4f} .. {axis.max():.4f}"
            for name, axis in (("x", xs), ("y", ys), ("z", zs))
            if axis.size
        )
        + f" mm (stored coordinates, {info['nx']}/{info['ny']}/{info['nz']} nodes)"
    )
    print(
        f"domain      : {info['nx'] * cell_mm:.4f} x {info['ny'] * cell_mm:.4f} x "
        f"{info['nz'] * cell_mm:.4f} mm (cell count x cell_m, the solver's box)"
    )
    print(f"nstep       : {info['nstep']} (dump_stride={info['dump_stride']})")
    print(
        f"frames      : {info['nt']} on ez_ycut, {info['nt_x']} on each x-cut "
        f"(written every dump_stride*10 steps)"
    )
    print(f"dt_s        : {info['dt_s']:.6e} s  ({dt_ns:.6f} ns per frame)")
    if t_ns.size:
        print(
            f"t_ns        : {t_ns[0]:.6f} .. {t_ns[-1]:.6f} ns "
            f"(= frame_index * dt_s)"
        )
    if fi.size:
        print(
            f"frame_index : {int(fi[0])} .. {int(fi[-1])} (ez_ycut, every step)"
        )
    if fx.size:
        print(
            f"frame_index_xcut: {int(fx[0])} .. {int(fx[-1])} (both x-cuts, "
            f"STRIDE {int(np.diff(fx).min()) if fx.size > 1 else 0}) - these are "
            f"solver frames, so their instants run "
            f"{int(fx[0]) * dt_ns:.6f} .. {int(fx[-1]) * dt_ns:.6f} ns and do "
            f"NOT line up one-for-one with the ez_ycut frames"
        )
    print(f"f_ref_hz    : {info['f_ref_hz']:.6e} Hz ({info['f_ref_hz'] / 1e9:.6f} GHz)")
    print(
        f"f_pulse_hz  : {info['f_pulse_hz']:.6e} Hz "
        f"({info['f_pulse_hz'] / 1e9:.6f} GHz)"
    )
    print(
        f"geometry    : strip_w={info['strip_w_mm']:.4f} mm, "
        f"substrate_h={info['substrate_h_mm']:.4f} mm, eps_r={info['eps_r']:.4f}, "
        f"port_x={info['port_x_mm']:.4f} mm, load_x={info['load_x_mm']:.4f} mm"
    )

    print("|Ez|        : per plane, over every stored frame")
    for label, array in (("ez_ycut", ycut), ("ez_xcut_near", near), ("ez_xcut_far", far)):
        if array.size == 0:
            print(f"  {label}: [no samples]")
            continue
        magnitudes = np.abs(np.asarray(array, dtype=np.float64))
        if magnitudes.ndim:
            per_frame = magnitudes.reshape(magnitudes.shape[0], -1).max(axis=1)
        else:
            per_frame = magnitudes.reshape(1)
        low, high = float(per_frame.min()), float(per_frame.max())
        # A frame that is exactly zero (the pulse has not arrived yet) makes the
        # ratio infinite; say so rather than printing "xinf".
        spread = f"x{high / low:.3f}" if low > 0.0 else "unbounded (a frame is all zero)"
        print(
            f"  {label}: min={magnitudes.min():.6e} max={magnitudes.max():.6e} "
            f"frame-max {low:.6e} .. {high:.6e} (spread {spread})"
        )

    vmin, vmax = info["color_range"]
    print(
        f"colour      : ONE limit for every frame and plane: |Ez| {vmin:.6e} .. "
        f"{vmax:.6e} (percentile {COLOR_PERCENTILE} of |Ez| over all stored "
        f"frames); a per-frame limit would renormalise a decaying pulse"
    )
    if info.get("color_range_empty"):
        print(
            "[EMPTY DUMP] every stored plane is zero (or non-finite): the "
            "colour limit fell back to 0 .. 1 and there is nothing to animate"
        )

    if info.get("v_measured_reliable"):
        verdict = "shift-and-correlate fit accepted by the dump"
    else:
        verdict = "fit NOT reliable - treat as an estimate"
    print(
        f"velocity    : v_measured={info['v_measured_m_s']:.6e} m/s, "
        f"v_analytic={info['v_analytic_m_s']:.6e} m/s, "
        f"t_traverse={info['t_traverse_ns']:.6f} ns ({verdict})"
    )
    note = info.get("velocity_note")
    if note:
        print(f"velocity_note: {note}")


def print_keys(info: dict) -> None:
    """Print dump metadata. numpy only - no pyvista, no trame."""
    if _is_vis(info):
        _print_vis_keys(info)
        return
    plane = info[PLANE_KEY]
    cell_mm = _cell_mm(info)
    n_st, n_j, n_k = plane.shape

    print(f"file        : {info['path']}")
    print(f"plane       : {PLANE_KEY} shape={plane.shape} dtype={plane.dtype}")
    print(f"nstep       : {info['nstep']}")
    print(f"nx/ny/nz    : {info['nx']} / {info['ny']} / {info['nz']} (cells)")
    print(f"cell_m      : {info['cell_m']:.6e} m  ({cell_mm:.6f} mm)")
    # Read, not derived from the index - see _station_axis_mm. The extent on x
    # and the listing below are what a reader compares against the geometry, so
    # both must be the same axis the 3-D view draws on, not a shape-only guess;
    # the record beside the dump is where that axis is written.
    xs_mm, _xs_src = _station_axis_mm(info, _field_record(info["path"]))
    # The x extent is the line the planes COVER - last station minus first, plus
    # one cell - not the plane count times the cell, which is the same number
    # only when the planes run one cell apart from the origin. y and z have no
    # axis of their own, so they stay count times cell, and the npz counts
    # CELLS, not nodes: axis 1 carries ny + 1 node samples.
    span_x_mm = (xs_mm[-1] - xs_mm[0]) + cell_mm if n_st > 1 else cell_mm
    print(
        f"extent      : {span_x_mm:.4f} x {n_j * cell_mm:.4f} x "
        f"{n_k * cell_mm:.4f} mm"
    )
    print(f"samples     : {n_st} x {n_j} x {n_k}")
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


def build_grid(info: dict, stations_mm=None) -> "pyvista.ImageData":
    """Build the volume's grid on the STATION AXIS the dump or record records.

    ``stations_mm`` is that axis (``_station_axis_mm``). Without it the grid is
    the uniform ``i * cell`` stack this function has always built, which is a
    stated assumption and not a measured position.

    WHY the x sampling comes from the axis: the stations are snapped to grid
    cells, so the shipped record's nine planes are 1.2 mm apart from 10.4 mm - a
    uniform ``cell_mm`` on x would stack the same nine planes at 0 .. 3.2 mm,
    over the port end of the line. The y/z axes really are one cell per sample,
    so they keep ``cell_mm`` and origin 0.
    """
    # Deferred import: keeps --help / --list-keys runnable with numpy alone.
    import pyvista as pv

    plane = info[PLANE_KEY]
    n_st, n_j, n_k = plane.shape
    dims = (n_st, n_j, n_k)
    cell_mm = _cell_mm(info)
    if stations_mm is None:
        xs_mm = [i * cell_mm for i in range(n_st)]
    else:
        xs_mm = [float(v) for v in stations_mm]

    ez_real = np.real(plane).astype(float)
    ez_abs = np.abs(plane).astype(float)
    if ez_real.shape != dims or ez_abs.shape != dims:
        print(
            f"[poc_app] grid arrays have shapes {ez_real.shape} / {ez_abs.shape}, "
            f"expected {dims}.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # A non-uniform station axis cannot be ONE spacing, so which branch applies
    # is decided on the axis itself rather than assumed.
    if n_st > 1:
        dx_mm = (xs_mm[-1] - xs_mm[0]) / (n_st - 1)
        uniform = all(
            abs(xs_mm[i] - (xs_mm[0] + i * dx_mm)) <= 1e-9 for i in range(n_st)
        )
    else:
        dx_mm = cell_mm
        uniform = True

    if uniform:
        image = pv.ImageData()
        image.dimensions = dims
        image.spacing = (dx_mm, cell_mm, cell_mm)
        image.origin = (xs_mm[0], 0.0, 0.0)
    else:
        # The same points, handed over explicitly. VTK wants x to vary fastest,
        # which is the ravel order the constructor itself uses, so the arrays
        # that follow keep the layout the uniform branch gives them.
        xs, ys, zs = np.meshgrid(
            np.asarray(xs_mm, dtype=float),
            np.arange(n_j, dtype=float) * cell_mm,
            np.arange(n_k, dtype=float) * cell_mm,
            indexing="ij",
        )
        image = pv.StructuredGrid(xs, ys, zs)

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

    # No record is read here (create_plotter only ever sees ``info``), so the
    # axis is whatever the dump itself carries: a recorded ``station_x_m`` when
    # the npz has one, the stated uniform assumption when it has not. Every
    # later frame comes from _draw_scene, which passes the record-backed axis it
    # was handed in ``planes``.
    stations_mm, _stations_src = _station_axis_mm(info)
    grid = build_grid(info, stations_mm)
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
        _station_text(0, cell_mm, n_st, stations_mm),
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


def _add_plane_marker(
    plotter,
    what: str,
    center_x: float,
    y_mid: float,
    z_mid: float,
    y_span: float,
    z_span: float,
    color: str,
    render: bool = True,
) -> None:
    """Draw ONE plane normal to x, centred at ``center_x`` - as its EDGE.

    WHAT reaches the plotter: the BOUNDARY of the rectangle, not its face: the
    four corners of the rectangle in the y-z plane at ``x = center_x``, closed
    back to the first, in the marker's colour at ``line_width=2``.

    WHY an edge and not a 25 % sheet: the field page draws the whole-volume |E|
    as a translucent, log-scaled volume, and a filled sheet the size of the
    slab's y/z cross-section laid straight across it at the load x and at the
    S11 port x hid the very field the marker exists to point at. An outline
    marks the same place and occludes nothing.

    WHY four EXPLICIT corners and not a ``pv.Plane``: a Plane is built in its own
    x-y frame and then turned by ``direction``, which leaves the caller to work
    out which of ``i_size`` / ``j_size`` landed on which WORLD axis - and that
    reasoning was wrong here, silently, for as long as these markers have
    existed. ``direction=(1, 0, 0)`` is a +90 degree turn about y, so the i axis
    (+x) lands on -z while j stays on +y: ``i_size=y_span`` drew the 84.4 mm Y
    span as a VERTICAL ribbon rising 84.4 mm out of an 8.6 mm tall box (measured
    on the shipped dump's grid, cell 0.4 mm: y 38.2 .. 46.6 and z -37.8 .. 46.6
    where the box is y 0.2 .. 84.6, z 0.2 .. 8.6 - the complaint about ribbons
    stretching far outside the board, in numbers). A corner list cannot be
    swapped: every coordinate is written in the axis it belongs to, so
    ``y_span`` is ALONG y and ``z_span`` ALONG z, centred on ``y_mid`` /
    ``z_mid``, and no rotation stands between the arguments and the picture.

    WHY ``lines_from_points`` and not the old ``extract_feature_edges``: that
    extractor existed only to reduce the Plane's triangulation to its border,
    which made the marker depend on an edge-extraction API and forced the old
    "a pyvista without one loses the marker" apology. Four points and a closed
    polyline are the oldest primitive there is, and they carry no fill to
    occlude the field with.

    WHY not ``style="wireframe"``: pyvista would then draw every triangulation
    diagonal as well, and the marker reads as a grey smear instead of a
    rectangle.

    WHY one construction for two discs: the load plane and the S11 port plane
    differ only in the x they sit at and in the colour that names them, so they
    are the same corner list twice rather than two markers that could drift
    apart - and both are normal to x, the axis either plane cuts.

    Guarded: a pyvista that cannot build a polyline, or a plotter that refuses
    one, must cost the marker and not the viewer. ``what`` names the plane in
    that message.
    """
    import pyvista as pv

    try:
        y0, y1 = y_mid - 0.5 * y_span, y_mid + 0.5 * y_span
        z0, z1 = z_mid - 0.5 * z_span, z_mid + 0.5 * z_span
        # The five points of a CLOSED rectangle: the last repeats the first, so
        # the fourth side is drawn too. Only the four edges go to the plotter -
        # the fill is what occluded the |E| volume - and each corner is written
        # in the axis it belongs to, which is the whole point of the list: no
        # rotation sits between ``y_span`` and the y extent below.
        corners = np.asarray(
            [
                (center_x, y0, z0),
                (center_x, y1, z0),  # the Y span, along y
                (center_x, y1, z1),  # the Z span, along z
                (center_x, y0, z1),
                (center_x, y0, z0),  # back to the start: the fourth side
            ],
            dtype=float,
        )
        plotter.add_mesh(
            pv.lines_from_points(corners), color=color, line_width=2, render=render
        )
    except Exception as exc:  # noqa: BLE001 - losing the plane is survivable
        print(f"[poc_app] {what} plane not drawn: {exc}", file=sys.stderr)


def _add_markers(plotter, info: dict, planes: dict) -> None:
    """Draw the two port planes and the extraction labels.

    WHY this layer exists: the finding behind it is that an extraction plane one
    column past the load reads a collapsed field. A number in a browser cannot
    be placed in space; a red plane at the load, with the other two planes
    marked beside it, can. Every position comes from ``planes`` (that is, from
    the record), and a position taken from a built-in constant is spelled out
    as FALLBACK in the legend.

    WHY a second, purple plane: the S11 port plane is the only other placeable
    surface in the record, it is parallel to the load plane and offset along x,
    and until now it was named by a label with nothing to look at. Purple is
    how it is told apart from the load; its position and extent are the load
    plane's own (same y/z centre, same spans), so the pair reads as one slice
    pair and not as two different kinds of marker.

    WHY the switches ride INSIDE ``planes``: the scene is drawn with one
    ``planes`` argument that already carries every position this layer reads, and
    a redraw is the only caller that knows the page state - so
    ``show_load_plane`` / ``show_port_plane`` join the positions there (see
    ``_scene_planes``) instead of becoming two more arguments on every scene
    function. Absent -> ON, which is the picture this layer has always drawn.

    The LABELS are drawn either way: they are the legend of where the planes
    are, so hiding a disc must not hide the sentence that places it.

    The planes are guarded: a pyvista that disagrees about a Plane keyword must
    cost the plane, not the viewer.

    The rectangles are sized from the |E| volume's grid when the dump carries a
    volume, and from the plane stack's otherwise - see the block below for why
    the two lattices sit half a cell apart.
    """
    cell_mm = planes["cell_mm"]
    # n samples span n - 1 cells: ``build_grid`` places its mesh POINTS at
    # ``i * cell`` for i in 0 .. n-1, so the drawn slab's outer faces are at
    # ``(n - 1) * cell``. Using ``n * cell`` put each marker's rectangle one
    # cell past the outermost sample at BOTH ends, so the red and purple
    # rectangles visibly overhung the volume they are cross-sections of.
    #
    # WHICH lattice those counts come from: the |E| volume's, whenever the dump
    # carries one - that is the slab the volume view draws, and it is NOT the
    # plane stack's. ``_volume_abs_grid`` places its image at
    # ``origin = (0.5 * cell,) * 3``, the CENTRE of the first cell rather than 0,
    # and spans ``n - 1`` cells from there, so the same rule read off the plane
    # counts lands half a cell outside at the near end and level at the far one:
    # on the shipped dump (ny 212, nz 22 at cell 0.4 mm) the volume's y spans
    # 0.2 .. 84.6 and its z 0.2 .. 8.6, while the 213 x 22 plane stack spans
    # 0 .. 84.8 and 0 .. 8.4. The counts are read through ``_volume_grid_dims`` -
    # the one resolver the volume and both cuts are built from, whose memo is the
    # image already on screen in the volume branch - so the markers cannot
    # disagree with the field they cross-section. No volume -> the plane stack's
    # own spans, exactly as before: a dump with no volume has nothing to line up
    # with, and every picture of one is unchanged.
    dims = _volume_grid_dims(info)
    if dims is not None:
        _n_x, n_y, n_z = (int(v) for v in dims)
        lo = 0.5 * cell_mm
        y_span = max(n_y - 1, 0) * cell_mm
        z_span = max(n_z - 1, 0) * cell_mm
        y_mid, z_mid = lo + 0.5 * y_span, lo + 0.5 * z_span
    else:
        y_span = (info[PLANE_KEY].shape[1] - 1) * cell_mm
        z_span = (info[PLANE_KEY].shape[2] - 1) * cell_mm
        y_mid, z_mid = 0.5 * y_span, 0.5 * z_span

    if planes.get("show_load_plane", True):
        _add_plane_marker(
            plotter,
            "load",
            planes["x_load_mm"],
            y_mid,
            z_mid,
            y_span,
            z_span,
            "red",
        )
    if planes.get("show_port_plane", True):
        _add_plane_marker(
            plotter,
            "S11 port",
            planes["x_s11_mm"],
            y_mid,
            z_mid,
            y_span,
            z_span,
            "purple",
            # render=False on the SECOND disc: the first one already flushes
            # the frame, the rebuild ends with one render of its own, and a
            # flush per disc would draw a scene that has just been cleared and
            # is not finished yet (and one draw is the unit the page's draw
            # count is measured in).
            render=False,
        )

    # Labels at mid-height of each plane: x is the axis that matters here, so a
    # text anchor is unambiguous where a disc is not. There are NO sphere glyphs
    # any more: sized from the y span they came out with radius >= 0.5 mm, and
    # three opaque spheres that size sat on top of the field and hid it.
    # add_point_labels draws the anchor itself, so a label keeps its position.
    points = [
        (planes["x_s11_mm"], y_mid, z_mid),
        (planes["x_load_mm"], y_mid, z_mid),
        (planes["x_s21_mm"], y_mid, z_mid),
    ]
    labels = [
        f"S11 port plane - purple\nx = {planes['x_s11_mm']:.4f} mm",
        f"load (termination) - red\nx = {planes['x_load_mm']:.4f} mm",
        _s21_label(planes),
    ]
    try:
        plotter.add_point_labels(points, labels, font_size=9, text_color="black")
    except Exception as exc:  # noqa: BLE001 - the corner legend still says it
        print(f"[poc_app] marker labels not drawn: {exc}", file=sys.stderr)


def _draw_volume_scene(
    plotter,
    info: dict,
    *,
    grid,
    cut_layout: dict,
    cell_mm: float,
    clim_override=None,
):
    """Draw the volume view's FIELD layer: the volume and the two cut sheets.

    WHY this is a function of its own with every input named: it is the part of
    a scene that decides what the reader actually sees, and it used to be
    reachable only through ``_draw_scene`` - which reads the plane dict, the
    module keys and the camera flag on its way there. Nothing below reads any of
    those. The caller hands in the grid it already built, the cut layout it
    already resolved (so the sheets and the corner legend cannot disagree about
    which y / z sample is on screen), the cell size the volume lattice is
    indexed by, and - when it has one - the range to pin the volume to.

    ``clim_override`` replaces the volume's own colour limits: the |E| volume's
    measured ``(peak * 1e-3, peak)`` and the plane-stack fallback's, which has
    no range of its own to replace. ``None`` (the default, and what
    ``_draw_scene`` passes) leaves each volume on exactly the range it had
    before this was extracted. It is NEVER applied to the cut sheets: each one
    carries the range ``build_cut_sheets`` measured off the samples that sheet
    actually holds, and one range over both would be the lie that block
    refuses.

    Returns ``(cuts_drawn, cut_clims)``: whether pyvista accepted the sheets,
    and per axis the range each volume sheet was drawn on. Both belong to the
    caller, because the corner legend is built from them and it must not claim
    a sheet that was refused or a clim nobody used.
    """
    # Which cuts were actually drawn, and on what: the legend lives in the
    # caller, these two are what it is allowed to say.
    cuts_drawn = False
    cut_clims: dict = {}

    # THE WHOLE VOLUME first, when the dump carries one: |E| over every grid
    # cell the solve produced, log-scaled (see _volume_abs_grid for the clim)
    # and MEMOISED inside that helper, because this branch runs on every cut
    # or station move.
    abs_image, abs_meta = _volume_abs_grid(info, cell_mm)
    # A caller-supplied range wins over the volume's own: that is the one
    # thing this helper exists to be able to pin, and it is applied to the
    # volume ACTUALLY drawn below - the |E| image when the dump carries one.
    volume_clim = abs_meta["clim"] if clim_override is None else clim_override
    abs_drawn = False
    if abs_image is not None:
        # WHY the title is not the plane stack's "|Ez| [V/m]": these are two
        # different fields, and the FFT normalisation makes the colocated
        # volume ~2053x smaller in V/m than the captured |Ez| planes, so one
        # bar carrying the other's title would be read as the other's scale.
        try:
            plotter.add_volume(
                abs_image,
                scalars="e_abs",
                cmap="turbo",
                log_scale=True,
                clim=volume_clim,
                scalar_bar_args={"title": "|E| [V/m] (log)"},
            )
            abs_drawn = True
        except TypeError as exc:
            # An older pyvista accepts every one of these arguments EXCEPT
            # ``log_scale``. The same image on the same clim is still worth
            # showing, so it is retried ONCE without log_scale, on a title
            # that no longer claims a log bar - and never a third time.
            print(f"[poc_app] |E| volume not drawn: {exc}", file=sys.stderr)
            try:
                plotter.add_volume(
                    abs_image,
                    scalars="e_abs",
                    cmap="turbo",
                    clim=volume_clim,
                    scalar_bar_args={"title": "|E| [V/m]"},
                )
                abs_drawn = True
            except Exception as exc_again:  # noqa: BLE001 - see below
                print(
                    f"[poc_app] |E| volume not drawn: {exc_again}",
                    file=sys.stderr,
                )
        except Exception as exc:  # noqa: BLE001 - a picture is not a crash
            # Losing the volume must cost the VOLUME: the outline, the axes,
            # the board, the markers and both corner labels are drawn after
            # this branch, and an exception escaping here would take them all
            # (``_redraw_scene`` would swallow it and keep a stale picture).
            print(f"[poc_app] |E| volume not drawn: {exc}", file=sys.stderr)
    # Exactly ONE volume actor: two of them over the same slab occlude each
    # other, and the coarser nine-plane stack would read as a shell laid over
    # the 62-station |E| field - so it is drawn only when |E| is NOT.
    # The plane fallback has no range of its own to override, so a caller's
    # clim is the ONLY range it can be pinned to - and it is passed to both of
    # its draws (the direct one below and the guarded retry after it).
    ez_style = {} if clim_override is None else {"clim": clim_override}
    if abs_image is None:
        plotter.add_volume(
            grid,
            scalars="ez_abs",
            cmap="turbo",
            scalar_bar_args={"title": "|Ez| [V/m]"},
            **ez_style,
        )
    elif not abs_drawn:
        # Only reached when a volume WAS available and the plotter refused
        # it: the same fallback, guarded, because an exception escaping here
        # would cost the outline, the axes, the board and the markers too.
        try:
            plotter.add_volume(
                grid,
                scalars="ez_abs",
                cmap="turbo",
                scalar_bar_args={"title": "|Ez| [V/m]"},
                **ez_style,
            )
        except Exception as exc:  # noqa: BLE001 - see comment above
            print(f"[poc_app] |Ez| volume not drawn: {exc}", file=sys.stderr)
    # The two cut sheets: one sample each, drawn opaque enough to read the
    # field on, each on its OWN 60 dB colour range (see below) with no bar of
    # its own - the volume's bar stays the single one on screen, and the
    # corner legend names what each cut was painted on. Guarded - losing the
    # cuts must cost the cuts, not the view.
    try:
        for _axis, sheet, sheet_clim in build_cut_sheets(info, cut_layout):
            # WHICH scalar: the volume sheets carry ``e_abs`` straight off the
            # |E| image, the fallback sheets ``ez_abs``. Read off the SHEET's
            # own arrays rather than off the layout, so a volume that refused
            # to slice (and fell back to the plane sheets) is still drawn
            # from the array it actually carries.
            scalars = "e_abs" if "e_abs" in sheet.point_data else "ez_abs"
            style = {}
            # ``clim`` is the SHEET's own range, computed by
            # ``build_cut_sheets`` from the samples the sheet actually
            # carries - never the volume's, and never guessed. WHY per sheet:
            # a cut is a subset of the field, so its peak is at most the
            # volume's and can be far below it (measured on the shipped dump
            # at the default cuts: 65.6 V/m on the y cut and 8.2 V/m on the z
            # cut against 90.7 V/m in the volume), and a sheet painted on the
            # volume's range spends the top of the bar on values it does not
            # have. The single bar on screen is still the volume's, and its
            # clim is untouched; the corner legend names each cut's range
            # instead of adding a second bar over the same colours. The
            # ``is not None`` is the belt to that brace: a sheet with no
            # finite positive sample drops the log scale instead of inventing
            # a range, because a fabricated clim is the kind of lie this page
            # refuses.
            #
            # The range is applied to the VOLUME sheets only: the plane
            # fallback has always been drawn linear with no range quoted, and
            # a dump with no volume must keep the picture it had.
            clim = sheet_clim if scalars == "e_abs" else None
            if clim is not None:
                # |E| spans tens of decades, so a linear sheet would show the
                # peak and nothing else: log, on the sheet's own 60 dB span.
                style = {"log_scale": True, "clim": clim}
            plotter.add_mesh(
                sheet,
                scalars=scalars,
                cmap="turbo",
                opacity=0.75,
                show_scalar_bar=False,
                **style,
            )
            # What this cut was ACTUALLY painted on, for the corner legend:
            # recorded only after the mesh is on the plotter, so a refused
            # sheet never gets a range claimed for it - and only for the
            # volume sheets, because the plane fallback was never on a range
            # at all and naming one beside it would describe a bar the reader
            # is not looking at.
            if scalars == "e_abs":
                cut_clims[_axis] = clim
            # THE EDGE, the same one the port plane draws above and for the
            # same reason: a sheet ONE SAMPLE thick has no flank for the light
            # to fall on, so on its own it shows colour with no visible extent
            # and the reader cannot tell where the cut stops.
            #
            # Taken from the sheet's OWN ``outline()`` and not rebuilt here as
            # a rectangle: a rectangle would have to restate the origin, the
            # spacing and the sample counts, and could then disagree with the
            # field pyvista actually drew - the one failure this page cannot
            # show. Measured on both volume sheets ((3,1,2) and (3,4,1) cut
            # from a (3,4,2) image at cell 0.4 mm): ``outline()`` returns 8
            # points and 12 line cells whose bounds equal the sheet's to
            # SINGLE precision - VTK stores an outline's points as float32,
            # so 0.2 comes back as 0.20000000298023224, ~3e-9 mm out - the
            # coincident edge pairs redundant but well formed.
            #
            # EVERY cut, volume subset and plane fallback alike: thinness is a
            # property of both sources, and two framings in one scene would be
            # an inconsistency a reader has to explain.
            #
            # ``render=False`` exactly as the port sheet uses it: the common
            # tail ends with the one render of a finished scene, so an edge
            # adds no draw to a cut redraw. It sits inside this try because
            # that is where the port sheet keeps its own edge - an edge that
            # cannot be built costs the cuts, never the outline, the axes, the
            # board, the markers or the two corner labels drawn after.
            plotter.add_mesh(
                sheet.outline(), color="black", line_width=2, render=False
            )
    except Exception as exc:  # noqa: BLE001 - see comment above
        print(f"[poc_app] cut sheets not drawn: {exc}", file=sys.stderr)
    else:
        cuts_drawn = True

    # THE TWO FACTS THE LEGEND CANNOT GUESS, handed back instead of left in
    # this function's local scope: whether pyvista accepted the sheets at all,
    # and the range each one was actually painted on. The corner legend below
    # needs both, and it must never claim a sheet that was refused or a clim
    # nobody used - so neither fact may be recomputed from the inputs here.
    return cuts_drawn, cut_clims


def _draw_scene(
    plotter,
    info: dict,
    planes: dict,
    view_mode: str,
    station: int,
    j_cut=None,
    k_cut=None,
    station_label: bool = True,
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
    # One build, used for both the volume view and the outline. The station axis
    # comes from ``planes`` - that is, from the record beside the dump - so the
    # volume, the port slice, the markers and the cut sheets all live on ONE x
    # axis and cannot disagree about where 10.4 mm is.
    grid = build_grid(info, planes.get("stations_mm"))
    # Which y / z sample the cut sheets sit on, and whether they were actually
    # drawn: the legend must not claim sheets that pyvista refused.
    cut_layout = _cut_layout(info, j_cut, k_cut, planes.get("stations_mm"))
    cuts_drawn = False
    # Axis -> the clim each cut sheet was drawn on, for the corner legend. Empty
    # in the port view (no cuts there) and in a frame pyvista refused the sheets.
    cut_clims: dict = {}

    try:
        plotter.clear()
    except Exception as exc:  # noqa: BLE001
        # Keep going: a stale picture beats a dead server.
        print(f"[poc_app] plotter.clear failed: {exc}", file=sys.stderr)

    if view_mode == "port":
        # The port-plane cross-section: the captured station nearest the port x,
        # drawn as a single-sample-thick image that IS the y-z plane at that x.
        # WHICH AXIS EACH SAMPLE LANDS ON IS DECIDED BY THE ORDER OF THESE THREE
        # COUNTS, and nothing else here: pyvista fills an ImageData point by
        # point with x varying fastest, then y, then z. With dimensions
        # (1, n_j, n_k) sample (j, k) therefore lands at (x_mm, j*cell_mm,
        # k*cell_mm) - the field as captured, on the two axes it was captured on
        # - and the sheet has ZERO extent along x because a cross-section has
        # none: every point of it is at the port x by construction.
        # The triple used to be (n_j, n_k, 1), which is wrong in a way that still
        # looks like a picture: all 213 j-samples ran along x. Measured on a
        # 213 x 22 sheet at cell 0.4 mm and x_mm 19.6, that drew bounds
        # (19.6, 104.4, 0.0, 8.4, 0.0, 0.0) - an 84.8 x 8.4 mm rectangle lying
        # flat in the z = 0 plane, sticking 84.8 mm PAST the port x rather than
        # through it, with the field rotated inside it. That is a second volume
        # seen edge-on, not the slice the label promises.
        # THE RAVEL ORDER IS THE OTHER HALF AND IT DOES NOT FOLLOW THE DIMS: it
        # is already right, and changing it with the dims would transpose the
        # field invisibly. For dims (1, n_j, n_k) VTK's own point order is
        # index = j + n_j*k (x fastest, then y, then z), which is exactly an
        # F-order ravel of the (n_j, n_k) shot - hence "F" below. Measured,
        # with one sample set to 1.0 at (j=100, k=5) of a 213 x 22 sheet at cell
        # 0.4 mm and x_mm 19.6: the F-order ravel puts that sample at
        # (19.6, 40.0, 2.0), exactly where it was captured, while the C-order
        # ravel of the same array puts it at (19.6, 30.0, 4.0). The two orders
        # are one keyword apart and the second one would be read as a field that
        # moved, so the measurement, not a convention, is what pins "F" here.
        # Guarded: a slice that cannot be read must cost the SLICE, not the
        # outline, the markers and the two labels drawn after this branch.
        try:
            idx = int(planes["slice_index"])
            if not 0 <= idx < n_st:
                raise ValueError(
                    f"slice_index {idx} is outside the {n_st} captured planes"
                )
            x_mm = planes["stations_mm"][idx]
            shot = info[PLANE_KEY][idx]
            image = pv.ImageData()
            image.dimensions = (1, int(shot.shape[0]), int(shot.shape[1]))
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
            # THE EDGE, so the slice reads as a SHEET and not as a smear. A sheet
            # one sample thick has no flank for the light to fall on, so on its
            # own it shows colour with no extent at all - the reader cannot tell
            # where the cross-section stops. The boundary is taken from the
            # image's OWN bounds rather than rebuilt here as a rectangle: a
            # rectangle would have to restate the origin, the spacing and the
            # sample counts, and could then disagree with the field pyvista
            # actually drew, which is the one failure this page cannot show.
            # Measured on this zero-thickness image, outline() returns 8 points
            # and 12 line cells whose bounds equal the image's to the last
            # float, the four x-coincident edge pairs redundant but well formed
            # - so the derived edge is exact by construction and merely draws a
            # few duplicate lines. ``render=False`` for the same reason the
            # marker legend uses it: the common tail ends with the one render of
            # a finished scene, and a render here would flush a picture that is
            # still being built (and pay a draw on every rebuild).
            plotter.add_mesh(
                image.outline(), color="black", line_width=2, render=False
            )
        except Exception as exc:  # noqa: BLE001 - see comment above
            print(
                f"[poc_app] port-plane view not drawn: {exc}", file=sys.stderr
            )
    else:
        # The volume view's field layer is ONE call now, and it says what it
        # drew: the |E| volume (or the plane-stack fallback) and the two cut
        # sheets. It hands back both facts the corner legend needs - whether the
        # sheets were really accepted, and the range each one was painted on -
        # so the legend below still cannot claim a sheet pyvista refused or a
        # clim nobody used.
        cuts_drawn, cut_clims = _draw_volume_scene(
            plotter,
            info,
            grid=grid,
            cut_layout=cut_layout,
            cell_mm=cell_mm,
        )

    plotter.add_mesh(grid.outline(), color="black", line_width=1)
    plotter.add_axes(xlabel="x [mm]", ylabel="y [mm]", zlabel="z [mm]")

    # The structure the field sits on, BEFORE the marker layer: a marker with
    # no board under it is the picture that started this.
    _vis_geometry(plotter, info, planes)
    _add_markers(plotter, info, planes)
    # WHY the station text is optional: ``position="upper_left"`` makes this a
    # VTK corner annotation, whose font is scaled against the render window - a
    # 10 pt label becomes a banner across a wide picture and cannot be sized
    # from here. The unified vis page asks for it to be skipped (:7619) and
    # says the same sentence as shell text instead; every legacy page keeps the
    # default, so its in-scene corner label is unchanged.
    if station_label:
        plotter.add_text(
            _station_text(int(station), cell_mm, n_st, planes.get("stations_mm")),
            name="station_label",
            position="upper_left",
            font_size=10,
            color="black",
        )
    legend_lines = list(
        _marker_cut_lines(planes, cut_layout, cuts_drawn, view_mode)
    )
    # The cuts' own colour ranges ride in the SAME corner legend: a second colour
    # bar over the one set of colours would read as a second field, and without
    # the numbers a reader cannot tell a dark cut from a dim one.
    clim_text = _cut_clim_text(cut_clims)
    if clim_text:
        legend_lines.append(clim_text)
    plotter.add_text(
        _marker_text(planes, legend_lines),
        name="marker_legend",
        position="lower_left",
        font_size=8,
        color="black",
    )
    # Isometric, then fit everything. The markers do not all lie inside the
    # captured slab - the S11 port plane sits at the port end of the line and the
    # S21 plane one cell past the load - so a camera framed on the slab alone
    # would hide the entire point of the layer.
    #
    # WHY only on the FIRST build of this plotter: every later build is a slider
    # move (cut or station), and re-framing there would move the picture under
    # the hand that just rotated and zoomed it - the view would snap back on the
    # next tick. Nothing that motivated the framing has changed by then: the
    # marker layer and the slab it overhangs are rebuilt identically on every
    # build, so the fit the first build found is still the fit.
    #
    # The flag lives on the PLOTTER, not in a module global and not in ``info``:
    # it is one fact about one render window, while both of those are handed in
    # fresh or copied often enough to forget it. It is written INSIDE the guarded
    # block so that a plotter refusing new attributes costs the FRAMING and not
    # the scene.
    if not getattr(plotter, "_poc_camera_framed", False):
        try:
            plotter.view_isometric()
            plotter.reset_camera()
            plotter._poc_camera_framed = True
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


def _cut_axis_counts(info: dict, n_j: int, n_k: int):
    """How many y / z samples the two cut sliders span.

    The colocated |E| volume's own ``(ny, nz)`` when the dump carries one, and
    the counts the caller passed in - the captured plane stack's - otherwise.
    WHY the caller still passes them at all: the plane stack is the fallback this
    page has always drawn and every call site already has its shape in hand, so
    this stays the ONE place that decides which grid the sliders index and no
    call site has to learn about the volume.
    """
    dims = _volume_grid_dims(info)
    if dims is not None:
        return int(dims[1]), int(dims[2])
    return int(n_j), int(n_k)


def _init_cut_state(
    state, info: dict, n_j: int, n_k: int, planes, toggle_available: bool
) -> None:
    """Set the opening cut, its label and the first view label.

    Extracted from run_web without a change of numbers: the default cut is the
    middle sample of each transverse axis, which is where the markers already
    sit, so the first frame is the picture the page has always drawn. The
    sliders move these two numbers and nothing else.

    ``n_j`` / ``n_k`` are the plane-stack FALLBACK counts; when the dump carries
    a volume the sliders span its own ``(ny, nz)`` instead
    (:func:`_cut_axis_counts`), because a slider that cannot reach the last
    volume cell would report a cut that is not where it says it is.
    """
    n_j, n_k = _cut_axis_counts(info, n_j, n_k)
    cut_layout = _cut_layout(info, n_j // 2, n_k // 2, (planes or {}).get("stations_mm"))
    state.cut_y = cut_layout["j"]
    state.cut_z = cut_layout["k"]
    state.cut_label = _cut_text(cut_layout)
    state.view_mode = "volume"
    state.view_label = _view_label(
        state.view_mode, planes, toggle_available, cut_layout
    )


def _scene_planes(planes: dict, state) -> dict:
    """Return ``planes`` with the two marker switches folded in.

    WHY the switches travel here: ``_draw_scene`` and ``_add_markers`` already
    take the ``planes`` mapping, and both ``run_web`` redraw closures plus the
    legacy callers hand that mapping straight through. Folding the page's two
    checkboxes into it keeps every one of those signatures untouched while the
    picture still follows the widgets. The layout dict itself is never mutated
    (a copy is returned), and a state object that predates the toggles -> both
    planes ON, which is the picture this app has always drawn.
    """
    return dict(
        planes,
        show_load_plane=bool(getattr(state, "show_load_plane", True)),
        show_port_plane=bool(getattr(state, "show_port_plane", True)),
    )


# Extracted from run_web's ``_redraw`` closure: the quiver callback arrives as
# a parameter because the arrow cache and the handle table belong to the page,
# not to this function, and nothing here reaches back into run_web's locals.
def _redraw_scene(
    plotter,
    info: dict,
    planes,
    state,
    _show_volume_quiver,
    station_label: bool = True,
) -> None:
    """Rebuild the scene in the one plotter. Failure leaves the old picture."""
    try:
        _draw_scene(
            plotter,
            info,
            # The marker switches are read off STATE here and handed over
            # inside the mapping the scene already carries: a checkbox writes
            # the flag and this rebuild is what shows the result, so both
            # run_web ``_redraw`` closures and every legacy caller stay
            # byte-identical. A state object that predates them -> ON.
            _scene_planes(planes, state),
            state.view_mode,
            int(state.station),
            int(state.cut_y),
            int(state.cut_z),
            # Forwards the flag as a KEYWORD: the three cut arguments stay
            # positional, and a page that never passes it keeps the in-scene
            # corner label ``_draw_scene`` has always drawn (:3889).
            station_label=station_label,
        )
        # AFTER the scene, never before it: _draw_scene clears the plotter,
        # so this one call is what keeps a ticked arrow field on screen
        # across a cut or station change.
        _show_volume_quiver()
        plotter.render()
    except Exception as exc:  # noqa: BLE001 - never take the server down
        print(f"[poc_app] redraw skipped: {exc}", file=sys.stderr)


def _on_cut_change(
    axis: str,
    value,
    state,
    n_j: int,
    n_k: int,
    info: dict,
    planes,
    toggle_available: bool,
    _redraw,
    handles,
) -> None:
    """Clamp one cut index, store it, and rebuild the scene.

    ``n_j`` / ``n_k`` are the plane-stack FALLBACK counts, and the clamp limit is
    taken from ``_cut_axis_counts`` for the same reason the sliders are: on a dump
    with a volume the two axes span the volume's grid, so clamping to the plane
    stack's count would refuse - or invent - a reachable sample.
    """
    n_j, n_k = _cut_axis_counts(info, n_j, n_k)
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
    layout = _cut_layout(
        info, int(state.cut_y), int(state.cut_z), (planes or {}).get("stations_mm")
    )
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


def _emit_cut_sliders(
    missing_widgets,
    placeholder,
    html_div,
    widgets,
    state,
    n_j: int,
    n_k: int,
    info=None,
) -> None:
    """Emit the two cut sliders, or the label alone when they cannot be.

    The rows say which sample is drawn and where it is in mm, because a
    one-sample-thick sheet cannot be counted off the screen.

    ``n_j`` / ``n_k`` are the plane-stack FALLBACK counts and ``info`` is optional
    (a caller that does not hand it over gets exactly the old slider range):
    when the dump carries a volume the range is its own ``(ny, nz)``, so a slider
    and the clamp in :func:`_on_cut_change` span the same grid.
    """
    n_j, n_k = _cut_axis_counts(info, n_j, n_k)
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


def run_web(
    info: dict,
    host: str,
    port: int,
    station: int,
    structure=None,
    structures=None,
) -> int:
    """Serve the viewer for ONE structure entry.

    ``structure`` is the registry entry the page names, ``structures`` the list
    the picker lists; both fall back to what the registry resolves on its own, so
    a caller that passes only the dump still gets a page.
    """
    structures = load_structures() if structures is None else structures
    if structure is None:
        structure = _structure_by_id(DEFAULT_STRUCTURE, structures)
    structure_label = _structure_label(structure)
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
    state.trame__title = f"{structure_label} |Ez| PoC"
    # Plane positions come from the record beside the dump, so the markers and
    # the labels below cannot drift from the geometry that produced the numbers.
    # Resolved BEFORE the first label: the station label prints the station axis
    # those planes carry, and a label built first would have to guess it.
    record = load_record(info["path"])
    planes = _plane_layout(info, record)

    state.station = int(station)
    state.station_label = _station_text(
        int(station), cell_mm, n_st, planes["stations_mm"]
    )
    structure_id = structure.get("id") if isinstance(structure, dict) else None
    structure_options = _structure_options(structures)
    state.structure = structure_id
    state.structure_note = f"showing {structure_label}"

    # The page state the banner and the port-wave panel read from: the same
    # document --dump-state writes, so the warning sentence and the two cell
    # counts inside it are the state file's own numbers - computed once, never a
    # second reading that could disagree with the report.
    page_state = build_state_dump(info, structure, structures)
    mismatch = page_state["mismatch"]
    banner_text = _mismatch_banner_text(mismatch)
    port_waves = page_state["port_waves"]
    port_reason = page_state["port_waves_reason"]
    # The toggle needs the button widget AND the toolbar that carries it: when
    # any probed widget is missing the layout falls back to a label-only bar, so
    # the label then says the toggle is unavailable rather than lying.
    toggle_available = (not missing_widgets) and ("VBtn" in widgets)
    # Default cuts: the middle sample of each transverse axis, which is where
    # the markers already sit, so the first frame is the picture the previous
    # version drew. The sliders move these two numbers and nothing else.
    _init_cut_state(state, info, n_j, n_k, planes, toggle_available)
    # The dump's own single frequency, printed beside the view toggle so the
    # number can only be read as belonging to the 3-D field on screen - never to
    # the sweep panel below, which is a different artefact.
    dump_f_ghz = _own_frequency_ghz(record)
    state.dump_freq_label = (
        f"Current 3D dump frequency: {dump_f_ghz:.4f} GHz"
        if dump_f_ghz is not None
        else "Current 3D dump frequency: not recorded beside the dump"
    )
    # The 3-D vectors are OFF at boot: the plane picture is what the page is
    # for, and the arrows are something a reader asks for. The value is the one
    # the checkbox below binds to, so it must exist before the layout is built.
    state.show_volume_quiver = False

    # The multi-frequency sweep, if one was written beside the dump. Optional
    # at every step: no file, no matplotlib, an unusable row - the 3-D view
    # still comes up, and the caption says what is missing rather than going
    # quiet.
    multifreq = load_multifreq(info["path"], info.get("structure_id"))
    frequency_panel = (
        None
        if multifreq is None
        else build_frequency_chart(
            multifreq, multifreq.get("title") or _chart_title(structure)
        )
    )
    if multifreq is None:
        # From the ARM, not from DEFAULT_MULTIFREQ: that constant is A's own
        # summary, and naming it for a B dump - let alone a D one, which has no
        # summary at all - claimed a candidate file that could never have been
        # this dump's sweep.  Rejected alternative: keeping the constant and
        # appending "or nothing", which still points a reader at A's numbers.
        frequency_caption = _absent_multifreq_reason(
            _structure_key(info.get("structure_id")), info["path"]
        )
    else:
        frequency_caption = _frequency_caption(
            multifreq, record, _structure_key(info.get("structure_id"))
        )
    # The recorded station phasors. No matplotlib costs the picture and prints the
    # rows instead - build_port_wave_chart returns its rows and the reason rather
    # than raising, so the 3-D view and the caption still come up.
    port_wave_chart = (
        None if port_waves is None else build_port_wave_chart(port_waves)
    )
    # The plotter_ui handle only exists once the layout has been built, so the
    # handlers below reach it through this dict instead of closing over it.
    handles: dict = {}

    # The glyphed whole-volume arrow field, built ONCE and lazily: the first tick
    # of the checkbox pays the glyph, every redraw after that re-adds the cached
    # mesh. ``built`` is separate from ``mesh`` because None is a real answer
    # (no volume, nothing above the floor) and must not be re-attempted on every
    # click.
    quiver_cache: dict = {"mesh": None, "built": False}

    def _clear_volume_quiver() -> None:
        """Drop this page's arrow actor. Never raises."""
        entry = handles.pop("volume_quiver", None)
        if entry is None:
            return
        try:
            plotter.remove_actor(entry["actor"], render=False)
        except Exception as exc:  # noqa: BLE001 - a stale actor is not fatal
            print(
                f"[poc_app] 3D vectors clear skipped: {exc}", file=sys.stderr
            )

    def _show_volume_quiver() -> None:
        """Put the cached arrow mesh on the plotter, or take it off. Never raises.

        Called at the END of every redraw, never from inside _draw_scene: that
        function starts with plotter.clear(), so an actor added before it is
        gone by the time it returns. Re-adding costs nothing - the mesh is
        cached, and pyvista's add_actor() replaces the actor of the same name -
        and it is what makes the arrows survive a cut or station change.
        """
        _clear_volume_quiver()
        if not state.show_volume_quiver:
            return
        mesh = quiver_cache["mesh"]
        if mesh is None:
            return
        try:
            # BLACK, not white: this plotter's background is white
            # (create_plotter calls set_background("white")), so white geometry
            # cannot be seen on it. Black is absent from the turbo colour map
            # the surface uses and is maximally distinct from that background.
            actor = plotter.add_mesh(
                mesh,
                color="black",
                lighting=False,
                show_scalar_bar=False,
                name="volume_e_quiver",
            )
            handles["volume_quiver"] = {"actor": actor}
            # Stated rather than assumed: a variant that adds the actor hidden
            # must not leave the arrows invisible with the box ticked.
            actor.SetVisibility(True)
            print(
                f"[poc_app] 3D vectors actor: "
                f"{getattr(actor, 'name', None)} bounds={actor.GetBounds()}",
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001 - the arrows are not the page
            print(f"[poc_app] 3D vectors skipped: {exc}", file=sys.stderr)

    def _redraw() -> None:
        """Rebuild the scene in the one plotter. Failure leaves the old picture."""
        _redraw_scene(plotter, info, planes, state, _show_volume_quiver)

    # Registered BEFORE the layout is built, so ctrl.toggle_view exists by the
    # time the toolbar button binds to it.
    @ctrl.set("toggle_view")
    def _on_toggle_view(**_kwargs) -> None:
        state.view_mode = "port" if state.view_mode == "volume" else "volume"
        state.view_label = _view_label(
            state.view_mode,
            planes,
            toggle_available,
            _cut_layout(
                info, int(state.cut_y), int(state.cut_z), planes.get("stations_mm")
            ),
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
        _on_cut_change(
            "y",
            value,
            state,
            n_j,
            n_k,
            info,
            planes,
            toggle_available,
            _redraw,
            handles,
        )

    @ctrl.set("cut_z")
    def _on_cut_z(*args, **_kwargs) -> None:
        value = args[0] if args else _kwargs.get("cut_z", state.cut_z)
        _on_cut_change(
            "z",
            value,
            state,
            n_j,
            n_k,
            info,
            planes,
            toggle_available,
            _redraw,
            handles,
        )

    @ctrl.set("show_volume_quiver")
    def _on_volume_quiver_toggle(*args, **_kwargs) -> None:
        """Tick or untick the 3-D arrows: build the mesh at most once, redraw."""
        value = args[0] if args else _kwargs.get("show_volume_quiver", False)
        state.show_volume_quiver = bool(value)
        # Built on the FIRST tick, not at boot: a reader who never asks for the
        # vectors never pays the glyph. ``info`` cannot change under a running
        # page, so one build per page is all there can ever be.
        if state.show_volume_quiver and not quiver_cache["built"]:
            quiver_cache["mesh"] = _volume_quiver_mesh(info)
            quiver_cache["built"] = True
        _show_volume_quiver()
        try:
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - the box still holds the truth
            print(
                f"[poc_app] 3D vectors render skipped: {exc}", file=sys.stderr
            )

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
                _station_text(idx, cell_mm, n_st, planes.get("stations_mm")),
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

    # The structure picker is a convenience exactly like the sliders, so it is
    # probed on its own: a Vuetify variant without VSelect costs the picker, never
    # the toolbar. VSelect is deliberately NOT in the probed widget tuple above -
    # putting it there would degrade the whole layout whenever only the picker is
    # unavailable.
    select_cls = None
    try:
        select_cls = getattr(widgets_module, "VSelect", None)
    except Exception as exc:  # noqa: BLE001 - optional layer
        print(f"[poc_app] VSelect unavailable: {exc}", file=sys.stderr)

    # The 3-D vectors checkbox is probed the same way and for the same reason,
    # and is offered only when this dump really carries an ``e`` edge vector to
    # arrow: a control that cannot change the picture is a lie about the page.
    # The gate is the RAW key because that is what the loader stashes on every
    # dump -- the colocation happens on the first tick, not here, so gating on
    # the colocated volume would hide the checkbox on exactly the dumps that
    # deferred it. It is deliberately NOT in the probed widget tuple above -
    # putting it there would degrade the whole toolbar whenever only the
    # checkbox is missing.
    quiver_checkbox_cls = None
    try:
        if VOLUME_RAW_KEY in info:
            quiver_checkbox_cls = getattr(widgets_module, "VCheckbox", None)
    except Exception as exc:  # noqa: BLE001 - optional layer
        print(f"[poc_app] VCheckbox unavailable: {exc}", file=sys.stderr)

    def _emit_mismatch_banner() -> None:
        """The full-width warning, or nothing at all when the two runs agree.

        The sentence and both cell counts come out of the state dump's mismatch
        block; no cell count is typed here. The block is built ONLY when that
        block is flagged, so an agreeing page carries no empty box whose presence
        would imply something is wrong.
        """
        if banner_text is None:
            return
        if html_div is None:
            if placeholder is not None:
                placeholder(banner_text)
                return
            print(
                "[poc_app] mismatch banner not shown: no html widgets",
                file=sys.stderr,
            )
            return
        with html_div(
            style=(
                "width: 100%; box-sizing: border-box; background: #fff3cd; "
                "color: #8a1c00; border: 3px solid #b00020; "
                "border-radius: 4px; padding: 8px 14px; margin: 6px 12px; "
                "font-size: 15px; font-weight: 700; line-height: 1.35;"
            )
        ):
            html_div(banner_text)

    def _emit_volume_quiver_toggle() -> None:
        """The 3-D vectors checkbox, or nothing when it cannot do anything.

        Silent when the class is missing: run_web_vis prints its own line for
        this probe, but on THIS page an absent VCheckbox costs the extra and
        nothing else, and the stderr probe message above already said so. It is
        silent when the dump has no volume too, because then there is nothing a
        tick could draw.
        """
        if quiver_checkbox_cls is None:
            return
        try:
            # A (state_name, default) tuple, the picker's own binding idiom: it
            # binds state rather than inlining a value, so the checkbox reads
            # and writes ``show_volume_quiver`` and the controller below - not
            # the widget - decides what a change means.
            quiver_checkbox_cls(
                v_model=("show_volume_quiver", False),
                label="Show 3D Vectors",
                hide_details=True,
                style="padding: 2px 0;",
            )
        except Exception as exc:  # noqa: BLE001 - a toggle is never the page
            print(
                f"[poc_app] 3D vectors toggle unavailable: {exc}", file=sys.stderr
            )

    def _emit_structure_picker() -> None:
        """The case picker: every entry, record-only ones present but disabled.

        Each label carries that entry's cell counts and run letters, so the seam
        between two runs is readable BEFORE a case is opened - the picker is the
        only place that is possible. Picking another entry cannot reload a dump
        into a running page (the npz, the record, the markers and the plotter are
        all built once), so the note beside the picker names the command that
        opens the picked case instead of pretending to switch to it.
        """
        if not structure_options:
            if placeholder is not None:
                placeholder(f"no structures in {STRUCTURES_FILE}")
            return
        if select_cls is None:
            # No VSelect: the labels still come out, disabled state spelled out in
            # words, rather than the page going quiet about the other cases.
            if placeholder is not None:
                placeholder(
                    "structure: "
                    + "; ".join(item["title"] for item in structure_options)
                )
            return
        try:
            select_cls(
                v_model=("structure", structure_id),
                # v_bind_* is the only py-name trame maps back to `:items`, and a
                # (state_name, default) TUPLE is how trame is told to bind rather
                # than to inline: it puts the tuple's second element in its own
                # state under the tuple's first element and emits that NAME as
                # the JS expression, so the attribute becomes the bare
                # `:items="structure_items"`. That indirection is the point. Any
                # literal form here - repr() or json.dumps() - would have to
                # spell Python's True/False into a JavaScript expression, where
                # `True` is an undefined identifier rather than a boolean, and the
                # record-only entries would come out enabled. Held in state the
                # value crosses to the browser as JSON, so Vuetify sees true/false
                # and `props: {disabled: ...}` survives. A LIST here must not be
                # used: trame reads a list as (state_name, default) too, but its
                # FIRST ELEMENT alone reaches the attribute, which is label text
                # where JavaScript belongs, and the whole page template is
                # compiled at once so one bad expression takes the page down. The
                # keys are the ones item_title / item_value below read: title,
                # value, and props on a record-only entry.
                v_bind_items=("structure_items", structure_options),
                # Vuetify 2 spells these item-text, Vuetify 3 item-title. Both are
                # passed because every variant is probed at runtime; whichever
                # one this variant knows is the one that names the label.
                item_title="title",
                item_text="title",
                item_value="value",
                label="structure",
                hide_details=True,
                style="max-width: 520px; margin-right: 16px;",
            )
            # The note is a plain html label, not a Vuetify fallback: the picker
            # itself is a probed widget, so a missing probed class must not take
            # the note with it. It is what tells the reader a pick cannot swap
            # the dump under a running page.
            if html_div is not None:
                html_div(
                    "{{ structure_note }}",
                    style=(
                        "align-self: center; margin-left: 4px; font-size: 13px; "
                        "color: #444;"
                    ),
                )
            elif placeholder is not None:
                placeholder("{{ structure_note }}")
        except Exception as exc:  # noqa: BLE001 - label only, never the page
            print(f"[poc_app] structure picker unavailable: {exc}", file=sys.stderr)
            if placeholder is not None:
                placeholder(f"structure: {structure_label}")

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

    def _emit_port_wave_panel() -> None:
        """Emit the recorded station phasors under the frequency panel.

        The caption comes out even when no picture could be drawn: a missing panel
        reads as "no phasors were recorded", which is a different statement from
        "matplotlib is not installed here" or "the parallel arrays were short".
        The heading is _PORT_TITLE - the same words the caption and the chart
        title use - so the panel cannot be read as a refit or an extrapolation.
        """
        if html_div is None:
            return
        with html_div(
            style="border-top: 1px solid #d0d0d0; padding: 2px 0 4px 0;"
        ):
            html_div(
                _PORT_TITLE,
                style="font-size: 12px; font-weight: 600; padding: 2px 12px;",
            )
            html_div(
                _port_caption(port_waves, port_reason),
                style="font-size: 11px; color: #333; padding: 0 12px 2px 12px;",
            )
            if port_waves is None or port_wave_chart is None:
                return
            image = port_wave_chart.get("image")
            img_cls = getattr(html_widgets, "Img", None)
            if image and img_cls is not None:
                img_cls(
                    src=image,
                    style="height: 170px; display: block; margin: 0 12px;",
                )
                return
            reason = port_wave_chart.get("reason")
            if reason:
                html_div(
                    f"no picture drawn ({reason}); the recorded rows are "
                    "printed instead",
                    style="font-size: 11px; color: #8a1c00; padding: 0 12px;",
                )
            pre_cls = getattr(html_widgets, "Pre", None)
            if pre_cls is not None:
                pre_cls(
                    "\n".join(port_wave_chart["rows"]),
                    style="font-size: 11px; margin: 0 12px;",
                )

    with SinglePageLayout(server) as layout:
        layout.icon.hide()
        layout.title.set_text(
            f"{structure_label} - |Ez| ({n_st} captured x-planes)"
        )
        if not missing_widgets:
            with layout.toolbar:
                widgets["VSpacer"]()
                _emit_structure_picker()
                widgets["VSlider"](
                    v_model=("station", station),
                    min=0,
                    max=n_st - 1,
                    step=1,
                    thumb_label=True,
                    hide_details=True,
                    style="max-width: 420px; margin-right: 16px;",
                )
                # The view toggle. The VBtn call is deliberately bare: no
                # variant, no icon, no size - those keyword names differ between
                # Vuetify 2 and 3 and cannot be checked in this environment. If
                # trame refuses the binding, the label says the toggle is gone
                # instead of taking the page down.
                if toggle_available:
                    try:
                        widgets["VBtn"]("Switch view", click=ctrl.toggle_view)
                        widgets["VLabel"]("{{ view_label }}")
                        widgets["VLabel"]("{{ dump_freq_label }}")
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
                _emit_mismatch_banner()
                if placeholder is not None:
                    with placeholder():
                        view = plotter_ui(plotter)
                else:
                    view = plotter_ui(plotter)
            elif html_div is None:
                # No html widgets: the plotter keeps the whole content area.
                with container(fluid=True, classes="pa-0 fill-height"):
                    _emit_mismatch_banner()
                    view = plotter_ui(plotter)
            else:
                # Fixed slider + panel rows around a flexed plotter, so the
                # sliders are always reachable and the panel never floats over
                # the 3-D view. The banner is FIRST in that column: a reader who
                # never scrolls still meets the warning.
                #
                # height: 100vh, not 100%: the parent is a Vuetify
                # ``fill-height`` container, and a percentage height there
                # resolves against the CONTENT, so the column grew to whatever
                # its children demanded - the sliders, the plotter's old 320px
                # floor and both panels - and the overflow:hidden below then
                # clipped the panel box off the bottom of the window instead of
                # the plotter giving up height. A fixed pixel height was
                # rejected for the mirror-image reason: it overflows any window
                # shorter than the number chosen here. Letting the column scroll
                # (overflow-y: auto) was rejected too - the 3-D view then slides
                # out of sight while the sliders stay put, which is worse than
                # the defect for a page whose whole point is the picture. One
                # viewport is the only length that matches the space the page is
                # actually allowed to occupy.
                with container(fluid=True, classes="pa-0 fill-height"):
                    with html_div(
                        style=(
                            "display: flex; flex-direction: column; "
                            "height: 100vh; width: 100%; overflow: hidden;"
                        )
                    ):
                        _emit_mismatch_banner()
                        with html_div(
                            style=(
                                "display: flex; flex-wrap: wrap; "
                                "align-items: center; padding: 2px 12px;"
                            )
                        ):
                            _emit_cut_sliders(
                                missing_widgets,
                                placeholder,
                                html_div,
                                widgets,
                                state,
                                n_j,
                                n_k,
                                info,
                            )
                            # Same row as the cut sliders: both are ways of
                            # reading the one field on screen, so they belong
                            # side by side rather than in a second toolbar row.
                            _emit_volume_quiver_toggle()
                        # min-height: 0, not a pixel floor. A flex item's
                        # default min-height is its content, so 320px was a
                        # floor the column could not shrink below: on a window
                        # shorter than that floor plus the rows above and below
                        # it, the panels box was pushed past the bottom edge.
                        # The plotter sizes itself from the box it is given, so
                        # it needs no floor of its own to stay drawable - flex:
                        # 1 1 auto is what keeps it taking every pixel the fixed
                        # rows leave.
                        with html_div(
                            style="flex: 1 1 auto; min-height: 0;"
                        ):
                            view = plotter_ui(plotter)
                        # The two panels share one scroll box: each is a fixed
                        # height image while the plotter takes the leftover height, and
                        # without this the second panel would be clipped by the
                        # column's overflow:hidden instead of shown.
                        with html_div(
                            style=(
                                "flex: 0 0 auto; max-height: 42%; "
                                "overflow-y: auto;"
                            )
                        ):
                            _emit_frequency_panel()
                            _emit_port_wave_panel()
                            html_div("{{ station_label }}")

    # Now that the plotter_ui handle exists, hand it to the toggle handler.
    handles["view"] = view

    @ctrl.set("structure")
    def _on_structure_change(*args, **_kwargs):
        """Say what picking another entry would take; never half-reload the page.

        The npz, the record, the markers and the plotter are built once, for the
        ONE structure this process was started with. Switching the dropdown cannot
        rebuild them, so the page keeps its numbers and the note names the command
        that opens the picked case.
        """
        value = args[0] if args else _kwargs.get("structure", state.structure)
        if value is None or value == structure_id:
            state.structure_note = f"showing {structure_label}"
            return
        entry = _structure_by_id(value, structures)
        state.structure_note = (
            f"{_structure_label(entry)} is not loaded in this page - re-run "
            f"python3 server/poc_app.py --structure {value} to open it "
            f"(still showing {structure_label})"
        )

    @ctrl.set("station")
    def _on_station_change(*args, **_kwargs):
        value = args[0] if args else _kwargs.get("station", state.station)
        try:
            idx = int(round(float(value)))
        except (TypeError, ValueError):
            idx = int(state.station)
        idx = max(0, min(n_st - 1, idx))
        state.station = idx
        state.station_label = _station_text(
            idx, cell_mm, n_st, planes.get("stations_mm")
        )
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


# --- the wave animation page ------------------------------------------------
#
# The legacy page below draws ONE snapshot of nine captured planes. This one
# animates a recorded sequence: a frame slider, a play/pause button and a plane
# switch. Everything it draws comes out of load_vis, and the colour limit
# is the ONE ceiling computed there, so no frame can renormalise itself.


def _vis_frame_time_ns(info: dict, mode: str, frame) -> float:
    """Simulation time of ``frame`` on the plane family ``mode``, in ns.

    ``mode`` is "ycut" or "xcut", and the two families do NOT share a clock:
    ez_ycut is written every step with frame_index 1..nt, while the x-cuts are
    written every dump_stride * 10 steps with frame_index_xcut 1..nt_x. Indexing
    t_ns with an x-cut frame number looks perfectly well formed and reads an
    instant up to ten times too early, which is why this function exists instead
    of a bare ``t_ns[frame]`` at every call site.
    """
    try:
        frame = int(round(float(frame)))
    except (TypeError, ValueError):
        return float("nan")
    if mode == "xcut":
        index = info.get("frame_index_xcut")
        if index is None or index.size == 0:
            return float("nan")
        frame = max(0, min(index.size - 1, frame))
        return float(int(index[frame]) * float(info["dt_s"]) * 1e9)
    # A page with no timeline records no clock at all: nan is this module's
    # "not recorded" and _show already renders it as exactly that.
    t_ns = info.get("t_ns")
    if t_ns is None or t_ns.size == 0:
        return float("nan")
    frame = max(0, min(t_ns.size - 1, frame))
    return float(t_ns[frame])


def _vis_phase_text(t_ns: float, t_traverse_ns: float) -> str:
    """Where the frame sits relative to one trip along the line.

    t_traverse_ns is the recorded time for the wave to cross the line once, so
    the ratio below reads as "how many line crossings in". It is a READING AID
    with a threshold at 1.0, NOT a measurement of when the load was reached: the
    sentence is the ratio of two recorded numbers and nothing else. When either
    number is missing the sentence says so instead of inventing a phase.
    """
    try:
        traverse = float(t_traverse_ns)
        time_ns = float(t_ns)
    except (TypeError, ValueError):
        return "phase: sim time not recorded"
    if not np.isfinite(traverse) or not np.isfinite(time_ns) or traverse <= 0.0:
        return "phase: t_traverse not recorded - no line-crossing ratio"
    ratio = time_ns / traverse
    if ratio < 1.0:
        return f"phase: launching ({ratio:.2f} x t_traverse, still on the line)"
    return f"phase: past the load ({ratio:.2f} x t_traverse)"


def _vis_grid(info: dict, plane_key: str, frame) -> "pyvista.ImageData":
    """One frame of one plane as a single-sample-thick ImageData.

    Deferred import: --help / --list-keys / --dump-state stay numpy-only. The
    sheet is one cell thick on its fixed axis and sits at the recorded station,
    so it is drawn as a sheet rather than smeared into a volume.
    """
    import pyvista as pv

    cell_mm = _cell_mm(info)
    array = info[plane_key]
    if array.shape[0] == 0:
        # A build, not an entry refusal: both callers wrap this in a per-plane
        # guard that drops the one sheet and says why, so the other two planes
        # still draw. An exit here would take the whole page down over one
        # empty plane, which is what the guard cannot catch.
        raise ValueError(
            f"no {plane_key} frames: the dump's {plane_key} plane holds no "
            f"samples, so no sheet is drawn for it"
        )
    frame = max(0, min(int(array.shape[0]) - 1, int(frame)))
    data = np.abs(np.asarray(array[frame], dtype=float))
    if plane_key == "ez_ycut":
        dims = (int(info["nx"]), 1, int(info["nz"]))
        # The sheet's y is the recorded SAMPLE INDEX times the cell size. With no
        # recorded index there is no station, and a sheet drawn anyway would
        # claim the field was captured at y = 0. The caller drops the sheet and
        # says why; the other two planes are unaffected.
        station = _finite(info.get("j_cut"))
        if station is None:
            raise ValueError(
                "no recorded j_cut: the dump does not say which y sample "
                "ez_ycut was taken from, so no x-z sheet is drawn"
            )
        origin = (0.0, float(int(station)) * cell_mm, 0.0)
    elif plane_key == "ez_xcut_near":
        dims = (1, int(info["ny"]), int(info["nz"]))
        origin = (float(info["xcut_near_mm"]), 0.0, 0.0)
    else:
        dims = (1, int(info["ny"]), int(info["nz"]))
        origin = (float(info["xcut_far_mm"]), 0.0, 0.0)

    image = pv.ImageData()
    image.dimensions = dims
    image.spacing = (cell_mm, cell_mm, cell_mm)
    image.origin = origin
    # VTK expects x to vary fastest, so ravel in Fortran order.
    image.point_data["ez_abs"] = np.ascontiguousarray(
        data.ravel(order="F"), dtype=float
    )
    return image


def _vis_geometry(plotter, info: dict, planes=None) -> None:
    """The ground plane, the substrate, the strip and the two port markers.

    Three of these are ASSUMPTIONS about SHAPE, not about position, and the
    comments beside them say so:

    * the strip is drawn as a zero-thickness foil on top of the substrate: the
      dump records its width and no thickness;
    * the strip's y offset is NOT recorded anywhere. The overlay centres it on
      the grid, which is the only choice the dump supports;
    * the ground plane is one flat sheet at z = 0 over the whole domain: the
      dump records no conductor thickness.

    Every part is added in its own try/except: a pyvista that refuses one part
    must cost that part, not the animation.
    """
    import pyvista as pv

    # THE THREE PLACEMENT NUMBERS, and why an absence is NAMED instead of drawn.
    # Nothing here can be positioned without the cell size and the two lateral
    # extents: drawn anyway, the substrate, the strip and the ground plane would
    # land on a guessed millimetre scale, and a board at the wrong size is read
    # as a measurement. So the cell comes from planes["cell_mm"] FIRST - the
    # already-resolved millimetre value the rest of the page uses, and the exact
    # key _add_markers reads - and only then from the dump, through _cell_mm,
    # which is a bare info["cell_m"] and so has to be called inside a try/except.
    # Returning here, rather than raising out of _draw_scene, is what keeps a
    # decoration from killing the scene it decorates.
    cell_mm = None
    cell_src = "absent"
    if isinstance(planes, dict):
        cell_mm = _finite(planes.get("cell_mm"))
        if cell_mm is not None:
            cell_src = "planes"
    if cell_mm is None:
        try:
            _cell_from_info = _finite(_cell_mm(info))
        except Exception:  # noqa: BLE001 - a dump with no cell_m is a scene, not an error
            _cell_from_info = None
        if _cell_from_info is not None:
            cell_mm = _cell_from_info
            cell_src = "info"
    nx = _finite(info.get("nx"))
    ny = _finite(info.get("ny"))

    def _shown(value):
        """The number as the diagnostic prints it; a gap is the word 'absent'."""
        return "absent" if value is None else f"{value:g}"

    if cell_mm is None or nx is None or ny is None:
        print(
            "[poc_app] geometry: not drawn - "
            f"cell_mm={cell_src}, nx={_shown(nx)}, ny={_shown(ny)}",
            file=sys.stderr,
        )
        return
    x_span = nx * cell_mm
    y_span = ny * cell_mm
    y_mid = 0.5 * y_span
    # THE FIVE STRUCTURE NUMBERS, from the board-level block FIRST.
    # On the field-snapshot page every one of those five npz keys exists and is
    # NaN (load_vis fills them through _npz_scalar, whose default is NaN), so
    # there is no KeyError to catch and every isfinite() guard below simply
    # fails: the substrate, both gold segments and both port wires were skipped
    # without a word. The record beside the dump carries the same numbers, and
    # _geom_mm has already resolved them, in mm, into planes["geometry_mm"].
    _geom_block = planes.get("geometry_mm") if isinstance(planes, dict) else None
    _geom_block = _geom_block if isinstance(_geom_block, dict) else {}
    _geom_src = _geom_block.get("src")
    _geom_src = _geom_src if isinstance(_geom_src, dict) else {}

    def _pick(key: str):
        """geometry_mm first, the dump's own key second, None if neither."""
        from_geom = _finite(_geom_block.get(key))
        if from_geom is not None:
            return from_geom
        return _finite(info.get(key))

    def _nan(value):
        """The isfinite() guards need a float: an absence is NaN, never 0.0."""
        return float("nan") if value is None else value

    _resolved = {
        "substrate_h_mm": _pick("substrate_h_mm"),
        "strip_w_mm": _pick("strip_w_mm"),
        "port_x_mm": _pick("port_x_mm"),
        "load_x_mm": _pick("load_x_mm"),
        "xcut_near_mm": _pick("xcut_near_mm"),
    }
    # ONE line, once, naming every quantity and the source it came from, so the
    # next reader knows which source was missing instead of guessing.
    if any(_value is None for _value in _resolved.values()):
        print(
            "[poc_app] geometry: not drawn - "
            + ", ".join(
                f"{key}={_geom_src.get(key) or 'absent'}" for key in _resolved
            ),
            file=sys.stderr,
        )

    substrate_h = _nan(_resolved["substrate_h_mm"])
    strip_w = _nan(_resolved["strip_w_mm"])
    port_x = _nan(_resolved["port_x_mm"])
    load_x = _nan(_resolved["load_x_mm"])
    near_xcut = _nan(_resolved["xcut_near_mm"])

    # Two surfaces that share a plane make the depth buffer flicker, and the
    # correction is below the grid the dump records. One epsilon for every
    # surface that would otherwise be coplanar: a thousandth of the substrate
    # height (0.0016 mm on the real dump, a four-hundredth of one cell).
    eps = 0.001 * substrate_h if np.isfinite(substrate_h) else 0.0

    # THE GROUND PLANE, first so it reads as the floor rather than as a lid.
    # One flat sheet just under z = 0, spanning the domain the dump recorded:
    # the return conductor the strip is measured against, whose absence is what
    # made the strip look like a foil hanging in the air. pv.Plane, not a Box:
    # a conductor has no thickness at this scale, and a box would add a second
    # surface the field sheets could be hidden behind.
    if (
        np.isfinite(x_span)
        and np.isfinite(y_span)
        and x_span > 0.0
        and y_span > 0.0
    ):
        try:
            plotter.add_mesh(
                pv.Plane(
                    center=(0.5 * x_span, y_mid, -eps),
                    direction=(0.0, 0.0, 1.0),
                    i_size=x_span,
                    j_size=y_span,
                ),
                color="dimgray",
                name="ground_plane",
            )
        except Exception as exc:  # noqa: BLE001 - losing the sheet is survivable
            print(f"[poc_app] ground plane not drawn: {exc}", file=sys.stderr)

    if np.isfinite(substrate_h) and substrate_h > 0.0:
        try:
            # 0.3, not a solid: the ground plane under it and whatever field is
            # inside the dielectric have to stay visible THROUGH it.
            plotter.add_mesh(
                pv.Box(bounds=(0.0, x_span, 0.0, y_span, 0.0, substrate_h)),
                color="steelblue",
                opacity=0.3,
                name="substrate",
            )
        except Exception as exc:  # noqa: BLE001 - losing one box is survivable
            print(f"[poc_app] substrate not drawn: {exc}", file=sys.stderr)

    # THE LINE END. The dump records no line-end constant: the x axis it stores
    # stops at its last node, 24.4 mm (24.8 mm at the outer face of the last
    # cell), while the 28.8 mm box of
    # evidence/termination/run_build_A_nsub6.py:37 belongs to a different,
    # larger domain than this artefact. The stub therefore ends where the
    # recorded x axis ends - never at a literal, and never past the grid.
    try:
        _x_axis = np.asarray(info["x_mm"], dtype=float).ravel()
        line_end = float(_x_axis[-1]) if _x_axis.size else float("nan")
    except (KeyError, TypeError, ValueError):
        line_end = float("nan")
    # near_xcut is resolved above, from planes["geometry_mm"] first: the dump's
    # own key is NaN on the field-snapshot page, and a bare read here would put
    # that NaN straight back and drop the stub of the strip.

    # THE STRIP, in TWO segments: the load is a GAP in the conductor, not the
    # end of it. Segment A runs from the port plane to the recorded load plane;
    # segment B carries on from the near x-cut plane to the end of the line, so
    # the empty span between them (20.0 .. 20.4 mm on the real dump) is what
    # the picture shows as the load.
    #
    # ASSUMPTION, both segments: zero-thickness foil, centred on y, on the
    # substrate top. The dump records neither a thickness nor a y offset; the
    # 0.05 mm of thickness the old Box invented is what is gone - a Plane has
    # no z extent at all.
    if (
        np.isfinite(strip_w)
        and strip_w > 0.0
        and np.isfinite(substrate_h)
        and np.isfinite(port_x)
        and np.isfinite(load_x)
        and load_x > port_x
    ):
        try:
            plotter.add_mesh(
                pv.Plane(
                    center=(0.5 * (port_x + load_x), y_mid, substrate_h + eps),
                    direction=(0.0, 0.0, 1.0),
                    i_size=load_x - port_x,
                    j_size=strip_w,
                ),
                color="gold",
                opacity=0.9,
                name="strip_feed",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[poc_app] strip feed not drawn: {exc}", file=sys.stderr)

    if (
        np.isfinite(strip_w)
        and strip_w > 0.0
        and np.isfinite(substrate_h)
        and np.isfinite(near_xcut)
        and np.isfinite(line_end)
        and line_end > near_xcut
    ):
        try:
            plotter.add_mesh(
                pv.Plane(
                    center=(
                        0.5 * (near_xcut + line_end),
                        y_mid,
                        substrate_h + eps,
                    ),
                    direction=(0.0, 0.0, 1.0),
                    i_size=line_end - near_xcut,
                    j_size=strip_w,
                ),
                color="gold",
                opacity=0.9,
                name="strip_stub",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[poc_app] strip stub not drawn: {exc}", file=sys.stderr)

    # THE TWO VIRTUAL PORTS. Each is the gap the port bridges: a wire from the
    # ground plane up to the strip, at the recorded x and on the strip's own
    # centre line (no y offset is recorded). Without them the strip and the
    # ground plane are two unconnected sheets and the picture never says where
    # the wave enters or leaves.
    # The load IS the gap the two segments leave, so its wire goes in the MIDDLE
    # of that gap - derived from the recorded load plane and the near x-cut
    # plane (20.2 mm on the real dump), never a literal. With no near x-cut
    # recorded the gap has no second edge, and the load plane is the only
    # position the dump supports.
    if np.isfinite(load_x) and np.isfinite(near_xcut):
        load_gap_x = 0.5 * (load_x + near_xcut)
    else:
        load_gap_x = load_x
    wire_tops = []
    if np.isfinite(substrate_h) and substrate_h > 0.0:
        for port_label, port_name, port_x_mm in (
            ("Source", "port_source", port_x),
            ("Load", "port_load", load_gap_x),
        ):
            if not np.isfinite(port_x_mm):
                continue
            try:
                plotter.add_mesh(
                    pv.Line(
                        (port_x_mm, y_mid, -eps),
                        (port_x_mm, y_mid, substrate_h + eps),
                    ),
                    color="red",
                    line_width=4,
                    name=port_name,
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[poc_app] {port_label} marker not drawn: {exc}",
                    file=sys.stderr,
                )
                continue
            wire_tops.append((port_label, port_x_mm))

    # The labels are a BONUS: the wires carry the meaning, so a pyvista without
    # a usable labelling actor costs the text and keeps both wires.
    if wire_tops:
        try:
            plotter.add_point_labels(
                [(x_mm, y_mid, substrate_h) for _label, x_mm in wire_tops],
                [label for label, _x_mm in wire_tops],
                font_size=11,
                text_color="black",
                shape_color="white",
                shape_opacity=0.6,
                show_points=False,
                always_visible=True,
                name="port_labels",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[poc_app] port labels not drawn: {exc}", file=sys.stderr)


def _probe_trame_ui():
    """A usable Trame Vuetify module pair, or None after naming what failed.

    Same probe chain as run_web, newest first, and every candidate is guarded in
    its own try/except so a broken fallback cannot escape the loop. Returns
    ``(ui_module, widgets_module, SinglePageLayout, trame_version, ui_path,
    label)``.
    """
    import importlib

    try:
        from importlib.metadata import version as _pkg_version

        trame_version = _pkg_version("trame")
    except Exception:  # noqa: BLE001 - an unknown version is not a failure
        try:
            import trame

            trame_version = getattr(trame, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            trame_version = "unknown"

    for label, ui_path, widgets_path in (
        ("vuetify3", "trame.ui.vuetify3", "trame.widgets.vuetify3"),
        ("vuetify2", "trame.ui.vuetify2", "trame.widgets.vuetify2"),
        ("vuetify", "trame.ui.vuetify", "trame.widgets.vuetify"),
    ):
        try:
            candidate_ui = importlib.import_module(ui_path)
            candidate_widgets = importlib.import_module(widgets_path)
            candidate_layout = getattr(candidate_ui, "SinglePageLayout")
        except Exception as exc:  # noqa: BLE001 - deliberate, see docstring
            print(f"[poc_app] probe {label} unusable: {exc}", file=sys.stderr)
            continue
        return (
            candidate_ui,
            candidate_widgets,
            candidate_layout,
            trame_version,
            ui_path,
            label,
        )

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
    print("[poc_app] fix: python3 -m pip install trame-vuetify", file=sys.stderr)
    print(
        "[poc_app] then re-run: python3 server/poc_app.py --input <vis.npz>",
        file=sys.stderr,
    )
    return None


#: The sequence number every solve's OWN artefact name is built from. Two
# presses must not land on one file: the second would overwrite the first, and
# the page would then report "solved -> x.json" over numbers nobody had read.
_SOLVE_RUN_LOCK = threading.Lock()
_SOLVE_RUN_SEQ = 0


def _next_solve_run_tag() -> str:
    """A readable - and UNIQUE - stamp for one solve's files.

    The clock half makes a directory listing say when the run happened; the
    sequence half is what makes the name unique, because two presses inside the
    same second would otherwise resolve to the same path.
    """
    global _SOLVE_RUN_SEQ
    with _SOLVE_RUN_LOCK:
        _SOLVE_RUN_SEQ += 1
        seq = _SOLVE_RUN_SEQ
    return f"{time.strftime('%Y%m%dT%H%M%S')}_{seq:03d}"


def _solve_netlist_slug(netlist_document) -> str:
    """The circuit's own ``name``, flattened to something a file name can hold.

    A netlist may name itself with spaces, dots or slashes, and none of those
    survive as a path component unchanged; an unnamed one still has to produce a
    readable name, so it falls back to ``custom``.  The name only has to be
    recognisable at a glance - the verbatim text is in the file beside it.
    """
    raw = ""
    if isinstance(netlist_document, dict):
        raw = str(netlist_document.get("name") or "").strip()
    slug = re.sub(r"[^A-Za-z0-9-]+", "_", raw).strip("_")
    return slug[:40] or "custom"


def solve_argv(structure_id, xcut_near_mm, out_npz, netlist_json="") -> list[str]:
    """The argv that would run a fresh field solve. BUILT here, never run.

    It exists so the command line is assertable without paying for a solve: the
    flags are the solver's OWN - ``--structure``, ``--xcut-near-mm``,
    ``--vis-dump``, ``--netlist`` and ``--out`` all already exist over there - so
    this function adds no solver option and touches no solver behaviour.

    ``structure_id`` is REQUIRED: the arm is a choice, and when the caller did
    not name one there is no default arm worth guessing.

    ``out_npz`` may not resolve anywhere under ``EVIDENCE_DIR``: those dumps are
    certified artefacts, so a UI press must never be able to clobber one.
    ``LIVE_DUMP`` is the location a live solve is meant to use.

    ``--out`` is ALWAYS passed, and it is never the solver's own default (the
    certified ``evidence/termination/build_A_50ohm.json``): without it every
    button press rewrote a file a report quotes.  It names ONE run, so two solves
    never share an artefact.

    ``netlist_json`` is the netlist as JSON TEXT, and empty means "the built-in
    resistor study".  Non-empty: the text is checked HERE (a ``ValueError``
    before anything is written or spawned), then written to a file beside that
    run's artefact - the solver's interface is a path, not a string - and passed
    as ``--netlist``.  The file is the caller's to delete once the child exits
    (``solve_netlist_file`` reads its path back out of the argv).
    """
    sid = _structure_key(structure_id)
    if not sid:
        raise ValueError(
            "solve_argv: no structure id, so no arm to solve - pass the arm "
            'key the dump records ("A" or "B")'
        )
    out = Path(out_npz)
    resolved = out.resolve()
    evidence = EVIDENCE_DIR.resolve()
    if resolved == evidence or evidence in resolved.parents:
        raise ValueError(
            f"solve_argv: refusing to write {resolved} - everything under "
            f"{evidence} is a certified artefact; write to LIVE_DUMP "
            f"({LIVE_DUMP}) instead"
        )

    # ---- the netlist, before a single file is touched -----------------------
    text = str(netlist_json or "")
    document = None
    if text.strip():
        try:
            document = json.loads(text)
        except ValueError as exc:
            raise ValueError(
                f"solve_argv: the netlist is not JSON ({exc}) - the solver loads "
                "it with json.load, so the page refuses it here instead of "
                "spawning a child that would exit on it"
            ) from exc
        if not isinstance(document, dict):
            raise ValueError(
                "solve_argv: the netlist must be a JSON OBJECT (a mapping), not "
                f"a {type(document).__name__} - that is what the solver loads"
            )

    # ---- this run's OWN artefact -------------------------------------------
    artefact = out.parent / (
        f"vis_run_{sid}_"
        f"{'resistor' if document is None else 'netlist_' + _solve_netlist_slug(document)}_"
        f"{_next_solve_run_tag()}.json"
    )
    resolved_artefact = artefact.resolve()
    if resolved_artefact == evidence or evidence in resolved_artefact.parents:
        raise ValueError(
            f"solve_argv: refusing to write {resolved_artefact} - everything "
            f"under {evidence} is a certified artefact; write to "
            f"{LIVE_DUMP.parent} instead"
        )

    argv = [
        sys.executable,
        str(SOLVER_SCRIPT),
        "--structure",
        sid,
        "--xcut-near-mm",
        # %g, so 20.4 reads as 20.4: the float's repr can carry a long tail
        # (20.400000000000002) that looks like a different number than the one
        # the user asked for.
        f"{float(xcut_near_mm):g}",
        "--vis-dump",
        str(out),
    ]
    if document is None:
        return argv + ["--out", str(artefact)]

    # The netlist reaches the solver as a FILE - that is its interface - and it
    # is written beside this run's own artefact rather than in /tmp: same
    # directory, so it cannot fail on a full tmpfs, it is obvious which run it
    # belonged to, and the caller removes it as soon as the child exits.  It is
    # named off the artefact's stem, so the pair is unmistakable in a listing.
    netlist_path = artefact.with_suffix(".netlist.json")
    netlist_path.write_text(text, encoding="utf-8")
    return argv + ["--netlist", str(netlist_path), "--out", str(artefact)]


def solve_netlist_file(argv):
    """The netlist FILE a ``solve_argv`` command line points at, else ``None``.

    ONE place reads the path back out of the argv, so the caller that has to
    DELETE the file uses the same rule as the builder above and the two cannot
    drift apart.  A line with no ``--netlist`` is a resistor run and has no file
    to clean up.
    """
    argv = list(argv or [])
    if "--netlist" not in argv:
        return None
    i = argv.index("--netlist")
    if i + 1 >= len(argv) or not str(argv[i + 1]).strip():
        return None
    return Path(argv[i + 1])


def reload_page(npz_path, structure_id=None) -> dict:
    """Everything the page reads off disk for ONE dump, as a plain dict.

    ONE code path from a path to page data: boot calls this and a reload calls
    this, so a reloaded dump cannot be loaded differently from one that booted.
    No trame object and no module global is touched by this function or by
    anything it calls, which is exactly what makes it callable again later on a
    different file - the scene redraws from whatever it is handed.

    ``structure_id`` is a FALLBACK only: the dump's own recorded provenance wins
    whenever it carries one, so a reload can never relabel a dump.

    It RAISES on a dump it cannot read - ``load_any_dump``'s refusals and the
    npz errors propagate untouched - because the UI has to be able to report a
    failed solve. Only the PANELS below it degrade quietly, as they always have.
    """
    path = Path(npz_path)
    info = load_any_dump(path)
    # The path the DUMP records, not the spelling the caller used: boot reads
    # info["path"], so a reload that read anything else could resolve a
    # different neighbour file for the same dump.
    dump_path = Path(info.get("path") or path)
    recorded = info.get("structure_id")
    sid = recorded if recorded is not None else structure_id
    # The record beside the dump: the legacy page's plane positions and every
    # caption come from it. ``load_record`` returning None is a legitimate "no
    # record" and is NOT a failed dump load, so it stays permissive.
    record = load_record(dump_path)
    if _is_vis(info):
        # An animation dump's cut planes ARE its three stored field arrays, and
        # the recorded positions are where the overlay is drawn; the sheets are
        # built from those arrays per frame by _vis_grid. Nothing is copied
        # here - the arrays are referenced - and _vis_grid's geometry is NOT
        # duplicated, because a second copy of it could drift from the drawn
        # one.
        planes = {
            "cell_mm": _cell_mm(info),
            # Kept for the legacy reader, where None already means "centre that
            # sample"; it may be None for a dump that records no station, so it
            # is passed through rather than cast.
            "j_cut": info["j_cut"],
            "xcut_near_mm": float(info["xcut_near_mm"]),
            "xcut_far_mm": float(info["xcut_far_mm"]),
            "ez_ycut": info["ez_ycut"],
            "ez_xcut_near": info["ez_xcut_near"],
            "ez_xcut_far": info["ez_xcut_far"],
        }
    else:
        planes = _plane_layout(info, record)
    return {
        "path": dump_path,
        "info": info,
        "planes": planes,
        # The dump's OWN arm, so a page can only read the sweep of the arm it
        # says it is.
        "multifreq": load_multifreq(dump_path, sid),
        "structure_id": recorded,
        "record": record,
        # Which kind of page this is, decided once here rather than re-tested by
        # every caller that has to know.
        "is_vis": _is_vis(info),
    }


# --- the 2D cross-section mode viewer (COMPUTE layer) ------------------------
#
# Nothing below draws anything: no pyvista, no trame, no matplotlib. These are
# only the numbers a mode panel would print, so they can be checked (and were
# measured) with no OpenGL context, and a test can call them in a 512 MB image.
#
# WHAT IS SOLVED: one eigenmode of the cross-section (y, z) of the microstrip,
# z = 0 on the ground plane and the strip at z = h. emfit.mode2d expands the
# transverse field on first-order Nedelec (Whitney) edge elements, and the
# eigenvalue of that pencil is beta^2 [rad^2/m^2]. So the spectral shift handed
# to the solver is k0^2 * eps_eff, NOT a beta: mixing the two units is the one
# mistake this layer can make that still returns a plausible-looking number.
#
# NO PML: emfit.mode2d has none, so the open top and sides are closed with PEC
# walls. That is a modelling CHOICE with a cost: a PEC wall is a symmetry plane,
# so the box behaves like an enclosure and truncates the fringing field instead
# of absorbing it. At the default count the walls are 8.8 mm from the centre
# against a 1.6 mm strip half-width, which keeps the effect small - but it is
# not zero, and it is part of every number reported below.

#: Run A's banked two-wave beta [rad/m]. COPIED, not re-derived: the canonical
#: number lives in ``evidence/termination/run_build_A.py`` as
#: ``VIS_BETA_BANKED_RAD_PER_M``, and this module must never re-fit it.
VIS_BETA_BANKED_RAD_PER_M = 231.55331672912826
#: Cells per side of the |E| sampling grid. A PICTURE resolution, not a solver
#: one: the mode is solved on the mesh, this only sets how finely it is sampled.
MODE_GRID_CELLS = 48
#: Take every ``stride``-th SAMPLE of that same square grid for the arrow field:
#: one arrow per lattice cell each way (10 x 10 = 100 arrows on the shipped 48),
#: which is a density a reader can follow. The picture keeps every sample; only
#: the arrows are strided, and a point the arrows do not sit on simply has none.
MODE_QUIVER_STRIDE = 5
#: Longest arrow, as a fraction of the shorter side of the sampled box. WHY this
#: number: one stride of the arrow lattice is ``MODE_QUIVER_STRIDE / (cells - 1)``
#: = 0.1064 of that side, and 80 % of it (0.0851) is the longest shaft that still
#: leaves the head inside its OWN lattice cell - so two neighbouring arrows never
#: overlap, and an arrow beside the peak cannot be read as part of it. The length
#: below the peak is scaled LINEARLY by |E_t|, so the ratio between two arrows is
#: the recorded ratio of the two fields and not a re-normalisation of it.
MODE_QUIVER_MAX_LEN_FRACTION = 0.8 * MODE_QUIVER_STRIDE / float(MODE_GRID_CELLS - 1)
#: The memo behind ``mode_view``'s "a second press is instant" promise. Keyed by
#: the record path, its mtime, the cell count and k, so an edited geometry or a
#: changed request is a miss rather than a stale answer.
_MODE_VIEW_MEMO: dict = {}


def _mode2d():
    """``emfit.mode2d``, imported ON USE so --list-keys never needs scipy.

    The viewer's CLI path (--help, --list-keys) is documented as numpy-only and
    has to stay that way; the mode solver needs scipy, so it is imported here
    and the ImportError is reported by ``mode_view`` as a reason, not a crash.
    """
    from emfit import mode2d

    return mode2d


def cross_section_mesh(
    geometry, *, lateral_cells=44, vertical_cells=22, node_cap=2500
):
    """The (y, z) cross-section of the microstrip as a rectilinear mesh.

    Returns ``(mesh, boundaries, extent)``.

    ``mesh`` is an :class:`emfit.mode2d.Mesh2D` on a structured grid. ``extent``
    is ``(y_max_m, z_max_m)``: the box spans ``-y_max .. y_max`` laterally and
    ``0 .. z_max`` vertically. The cell count actually used is recoverable from
    the mesh itself - ``len(mesh.grid_axes[0]) - 1`` lateral cells,
    ``len(mesh.grid_axes[1]) - 1`` vertical ones - and ``mode_view``'s caption
    prints both, because a node cap silently changes the picture's resolution.

    ``boundaries`` is the PEC predicate tuple ``(ground, strip, wall)``, in that
    order, ready to hand to ``solve_modes`` / ``eps_eff_laplace``. The first two
    are the CONDUCTORS - pass exactly those two to ``eps_eff_laplace``; the third
    fences the open top and sides. An edge is PEC only when both endpoints
    satisfy the SAME predicate, so the vertical gap between ground and strip is
    left free: the two conductors are never joined by their own predicates.

    Geometry (metres, ohms of nothing - measured lengths only): ``eps_r`` the
    substrate permittivity, ``h`` its thickness, ``w`` the strip width, and
    ``height`` the top of the box. The substrate fills ``0 <= z < h`` and air
    fills ``h < z <= height``; the strip is the node row at ``z == h`` within
    ``|y| <= w/2``.

    The vertical pitch is chosen so ``z == h`` lands EXACTLY on a node row (the
    strip predicate is an equality test, so a pitch that misses h would mark no
    strip at all and silently solve a bare slab); ``vertical_cells`` is a target
    that the h-alignment is allowed to round. The lateral half-extent is
    ``lateral_cells / 2`` of that same pitch, which at the default 44 x 22 is
    +/-8.8 mm against the run's own 0.4 mm cell - the calibrated box.

    ``node_cap`` is honoured by HALVING ``lateral_cells`` (kept even, so the
    grid keeps a node row at ``y == 0`` and the strip stays centred) until
    ``(lateral + 1) * (vertical + 1) <= node_cap``. A halved count therefore
    narrows the box at a FIXED pitch rather than coarsening it: the strip is
    always resolved by the same cell size, and the only thing that moves is how
    far away the PEC fence sits.
    """
    mode2d = _mode2d()
    eps_r = float(geometry["eps_r"])
    h = float(geometry["h"])
    w = float(geometry["w"])
    height = float(geometry["height"])
    if not (h > 0.0 and w > 0.0 and height > h):
        raise ValueError(
            f"cross section needs 0 < h < height and w > 0, got h={h!r}, "
            f"w={w!r}, height={height!r}"
        )

    # z axis, h-aligned so the strip predicate can be an equality test.
    pitch = height / max(1, int(vertical_cells))
    n_h = max(1, int(round(h / pitch)))
    pitch = h / n_h
    n_top = max(1, int(np.ceil((height - h) / pitch - 1e-9)))
    z_max = pitch * (n_h + n_top)
    zs = np.arange(n_h + n_top + 1) * pitch

    # y axis, node cap by halving.
    lateral = max(2, int(lateral_cells))
    lateral -= lateral % 2
    while (lateral + 1) * zs.size > node_cap and lateral > 2:
        lateral = max(2, lateral // 2)
        lateral -= lateral % 2
    y_max = 0.5 * lateral * pitch
    ys = (np.arange(lateral + 1) - lateral // 2) * pitch

    mesh = mode2d.structured_mesh(ys, zs)

    tol = 1e-12

    def ground(points):
        """The ground plane: the z = 0 node row."""
        return np.isclose(points[:, 1], 0.0, atol=tol)

    def strip(points):
        """The strip: the z = h node row within |y| <= w/2."""
        return np.isclose(points[:, 1], h, atol=tol) & (
            np.abs(points[:, 0]) <= 0.5 * w + tol
        )

    def wall(points):
        """The PEC fence: the top row and both side columns (no PML here)."""
        return np.isclose(points[:, 1], z_max, atol=tol) | np.isclose(
            np.abs(points[:, 0]), y_max, atol=tol
        )

    return mesh, (ground, strip, wall), (y_max, z_max)


def _mode_pct(value):
    """``+1.07 %``-style delta, or ``n/a`` when the reference is not recorded."""
    if value is None:
        return "n/a"
    return f"{value:+.2f} %"


def _mode_delta_pct(beta, reference):
    """``100 * (beta - reference) / reference``, or None for no reference.

    ``None`` also when the solve has no propagation constant to compare (a
    below-cutoff mode carries ``beta_rad_per_m = None``, see
    :attr:`emfit.mode2d.Mode2D.beta`): a delta against a beta that does not
    exist is not zero, it is not a number.
    """
    if beta is None:
        return None
    try:
        reference = float(reference)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(reference) or reference == 0.0:
        return None
    return 100.0 * (float(beta) - reference) / reference


def _mode_grid_axes(result, extent, cells=MODE_GRID_CELLS):
    """The ``(y, z)`` sampling axes a mode is drawn on, in metres.

    The mode's OWN mesh axes when the mesh carries them (``grid_axes``), so the
    sampling never lands outside the triangulation; the box extent otherwise.
    Shared by the |E| picture grid and the arrow grid, so the two can never
    sample different points - a coloured cell and an arrow over it disagreeing
    about where the field is would be a bug no reader can see.
    """
    y_max, z_max = (float(extent[0]), float(extent[1]))
    axes = result.mesh.grid_axes
    if axes:
        y_axis, z_axis = np.asarray(axes[0], dtype=float), np.asarray(
            axes[1], dtype=float
        )
        y_lo, y_hi = float(y_axis[0]), float(y_axis[-1])
        z_lo, z_hi = float(z_axis[0]), float(z_axis[-1])
    else:
        y_lo, y_hi, z_lo, z_hi = -y_max, y_max, 0.0, z_max
    gy = np.linspace(y_lo, y_hi, int(cells))
    gz = np.linspace(z_lo, z_hi, int(cells))
    return gy, gz


def _mode_field_grid(result, extent, cells=MODE_GRID_CELLS, index=None):
    """|E| of the solved mode on a ``(cells, cells)`` (z, y) sampling of the box.

    Sampled through ``Mode2D.e_at`` - the same Whitney interpolation the field
    is defined by - at the mesh's own axis endpoints, so the sampling never
    lands outside the triangulation (``e_at`` raises there, and the tolerance is
    tight enough that a re-derived extent would trip it).

    ``index`` samples a CANDIDATE instead of the solver's pick: the same axes,
    the same ``solved`` object, through ``Mode2D.e_at_candidate``. That is why
    the picker below needs no second solve, and why a candidate's picture and
    the fundamental's are drawn from one interpolation on one grid.
    """
    gy, gz = _mode_grid_axes(result, extent, cells)
    yy, zz = np.meshgrid(gy, gz, indexing="xy")
    points = np.stack([yy.ravel(), zz.ravel()], axis=1)
    if index is None:
        field = np.asarray(result.e_at(points), dtype=float)
    else:
        field = np.asarray(result.e_at_candidate(int(index), points), dtype=float)
    return np.hypot(field[:, 0], field[:, 1]).reshape(int(cells), int(cells))


def _mode_vector_grid(
    result, extent, cells=MODE_GRID_CELLS, stride=MODE_QUIVER_STRIDE, index=None
):
    """(E_y, E_z) of the mode on the STRIDED samples of the same box. NEVER raises.

    Shaped like ``grid`` - ``(cells, cells, 2)``, indexed ``(z, y)`` - so the two
    are one sampling of one mode and an arrow can be placed by the index its
    cell already has. What ``_mode_field_grid`` keeps as ``hypot``, this keeps as
    the two components it is made of: the transverse field in the cross-section
    plane is a two-component vector at every point, and a magnitude cannot say
    which way it points.

    Only every ``stride``-th sample is asked for - a point the picture does not
    resolve gets no arrow either - and every other entry is NaN, the one value
    an arrow is never drawn on. A sampled point the interpolation cannot answer
    for (outside the triangulation: ``Mode2D.e_at`` raises ``ValueError`` there)
    is left NaN and COUNTED, because an arrow at a point the field was never
    evaluated at would be an invented arrow.

    ``index`` samples a CANDIDATE, through ``e_at_candidate``, exactly as
    ``_mode_field_grid`` does, so a picker row and its arrows come from the same
    eigenvector and the same grid.
    """
    cells = int(cells)
    grid = np.full((cells, cells, 2), np.nan, dtype=float)
    try:
        gy, gz = _mode_grid_axes(result, extent, cells)
    except Exception as exc:  # noqa: BLE001 - the arrows are an EXTRA, not the panel
        print(f"[poc_app] mode vector field refused: {exc}", file=sys.stderr)
        return grid
    picks = np.arange(0, cells, max(1, int(stride)))
    yy, zz = np.meshgrid(gy[picks], gz[picks], indexing="xy")
    points = np.stack([yy.ravel(), zz.ravel()], axis=1)
    total = int(points.shape[0])
    try:
        if index is None:
            field = np.asarray(result.e_at(points), dtype=float)
        else:
            field = np.asarray(result.e_at_candidate(int(index), points), dtype=float)
    except ValueError:
        # ONE point outside is enough for _locate to refuse the WHOLE array, so
        # the mask is recovered point by point: that is the only way to say how
        # many were masked, and a count nobody can state is a count nobody can
        # check.
        field = None
    except Exception as exc:  # noqa: BLE001
        print(f"[poc_app] mode vector field refused: {exc}", file=sys.stderr)
        return grid
    if field is not None and field.shape != (total, 2):
        field = None
    outside = 0
    if field is None or not np.all(np.isfinite(field)):
        field = np.full((total, 2), np.nan, dtype=float)
        outside = 0
        for k in range(total):
            try:
                one = (
                    result.e_at(points[k : k + 1])
                    if index is None
                    else result.e_at_candidate(int(index), points[k : k + 1])
                )
            except ValueError:
                outside += 1
                continue
            except Exception as exc:  # noqa: BLE001 - one point is not the field
                print(
                    f"[poc_app] mode vector field point {k} skipped: {exc}",
                    file=sys.stderr,
                )
                outside += 1
                continue
            field[k] = np.asarray(one, dtype=float)[0]
    sampled = total - outside
    if sampled <= 0:
        print(
            "[poc_app] mode vector field refused: no sampled point is inside the "
            "mesh",
            file=sys.stderr,
        )
        return grid
    if outside:
        print(
            f"[poc_app] mode vector field: {sampled} of {total} sampled points "
            f"inside the mesh, {outside} masked (no arrow drawn on those)",
            file=sys.stderr,
        )
    # Rows come back with y fastest (the meshgrid above), which is the (z, y)
    # layout ``grid`` already uses - scattering them the other way round would
    # mirror the arrows into the wrong axis without raising.
    grid[np.ix_(picks, picks)] = field.reshape(picks.size, picks.size, 2)
    return grid


def _mode_caption(result, mesh) -> str:
    """The one sentence set a mode panel may print, from the numbers beside it.

    Says the three betas TOGETHER, states that the banked fit carries a
    systematic (~4 % above the run's own model) so it is never quoted alone, and
    names the mesh and the wall clock - the last unflattering facts a reader
    needs in order to distrust the number appropriately.

    When the geometry did NOT come from a study record, a provenance clause is
    appended: a solve replayed from the dump's own metadata is not the run's
    recorded solve (its drive frequency is the dump's ``f_ref_hz``) and it must
    not be printed as if it were.
    """
    beta_model = result["beta_model"]
    beta_banked = result["beta_banked"]
    model_text = (
        f"{beta_model:.4f} rad/m from the run's own record "
        f"({_mode_pct(result['delta_vs_model_pct'])} from this solve)"
        if beta_model is not None
        else "not recorded in the run's own record"
    )
    # How far run A's fit sits above the run's own model - and what is left to say
    # when one of the two numbers is absent. The both-present branch is the
    # sentence this caption has always printed, kept word for word: it is the only
    # branch a record-backed dump ever takes. The other branches exist because the
    # dump-metadata path has no record at all, and "not measurable here above the
    # run's own beta_model" is not a sentence - a missing model is named as
    # missing, never measured against.
    if beta_model is not None and beta_banked is not None:
        gap = (float(beta_banked) / float(beta_model) - 1.0) * 100.0
        systematic_text = (
            f". That banked fit sits {gap:+.1f} % above the run's own "
            "beta_model, i.e. the fit carries a systematic, so beta_banked is "
            "quoted beside the model and never on its own. "
        )
    elif beta_banked is not None:
        systematic_text = (
            ". The run's own beta_model is absent here, so how far that fit sits "
            "above it cannot be measured on this dump: beta_banked is an "
            "order-of-magnitude cross-check only, never a number to quote on its "
            "own. "
        )
    elif beta_model is not None:
        systematic_text = (
            ". No run A two-wave fit is recorded beside this dump, so there is "
            "nothing to check the run's own model against. "
        )
    else:
        systematic_text = (
            ". Neither the run's own beta_model nor run A's two-wave fit is "
            "recorded here, so beta stands alone - there is nothing beside it to "
            "check it against. "
        )
    axes = mesh.grid_axes
    lateral = int(np.asarray(axes[0]).size - 1) if axes else 0
    vertical = int(np.asarray(axes[1]).size - 1) if axes else 0
    y_max, z_max = result["extent"]
    provenance = ""
    if result.get("geometry_source", "record") != "record":
        driven_ghz = result.get("geometry_f_hz")
        driven_text = (
            f"{driven_ghz / 1e9:.4f} GHz"
            if isinstance(driven_ghz, float) and math.isfinite(driven_ghz)
            else "its recorded f_ref_hz (value not usable here)"
        )
        provenance = (
            " GEOMETRY PROVENANCE: no study record sits beside this dump, so "
            "the cross-section was read from the dump's own metadata (eps_r, "
            "substrate_h_mm, strip_w_mm, f_ref_hz, and height = nz x cell_m) "
            "and the mode was driven at the dump's own reference frequency, "
            f"{driven_text}. That is not the frequency the mode was originally "
            "solved at: where a record does exist the two differ - "
            "artifacts/vis_run_B_100ohm.json states 6.1192 GHz against a dump "
            "f_ref_hz of 5.8278 GHz - and beta moves with the drive frequency, "
            "so beta above is this replay's number, not the run's recorded one."
        )
    return (
        "2D cross-section mode (fundamental, quasi-TEM): beta = "
        f"{_fmt(result['beta_rad_per_m'], 4)} rad/m, eps_eff = "
        f"{result['eps_eff']:.6f}, "
        f"residual = {result['residual']:.2e}, curl_ratio = "
        f"{result['curl_ratio']:.3e}. Compare the three together: beta_model = "
        f"{model_text}; beta_banked = "
        + (
            f"{beta_banked:.4f} rad/m, run A's two-wave fit "
            f"({_mode_pct(result['delta_vs_banked_pct'])} from this solve)"
            if beta_banked is not None
            else "not recorded"
        )
        + systematic_text
        + f"Mesh: {lateral} lateral x {vertical} vertical cells = "
        f"{result['n_nodes']} "
        f"nodes / {result['n_edges']} edges, box +/-{y_max * 1e3:.2f} mm x "
        f"{z_max * 1e3:.2f} mm, solved in {result['seconds']:.2f} s. The open top "
        "and sides are PEC walls (this solver has no PML), so the lateral "
        "truncation is a conductor, not an absorber."
        + provenance
    )


def _mode_fail(reason: str) -> dict:
    """The refusal shape: ``ok`` False and one short, honest cause."""
    return {"ok": False, "reason": str(reason)}


def _mode_geometry_from_dump(dump):
    """Cross-section geometry from the DUMP's own metadata: ``(geometry, note)``.

    The study record is the authority - it carries the geometry the run was
    actually built on. When no record sits beside the dump, the vis dump still
    records part of that cross-section, and reading it is not the same as
    guessing: ``eps_r``, ``substrate_h_mm`` and ``strip_w_mm`` are stored
    numbers, and the box top is ``nz * cell_m`` - the stored grid, which is what
    the record's own ``height`` is too (22 cells x 0.4 mm = 8.8 mm, while the
    stored ``z_mm`` axis stops at 8.4 mm because it holds node positions, not
    the far cell face).

    ``geometry`` has the same keys and units ``cross_section_mesh`` expects
    (metres). ``note`` is the provenance when the geometry was found, and the
    plain list of ABSENT quantities when it was not: a dump that records no
    ``eps_r`` gets a refusal naming ``eps_r``, never a plausible filler. A NaN
    from a missing key (``_npz_scalar``'s default) counts as absent.

    Only stdlib + numpy: no matplotlib, no trame, no pyvista.
    """
    dump = Path(dump)
    try:
        with np.load(dump) as data:
            eps_r = _npz_scalar(data, "eps_r")
            h_mm = _npz_scalar(data, "substrate_h_mm")
            w_mm = _npz_scalar(data, "strip_w_mm")
            f_hz = _npz_scalar(data, "f_ref_hz")
            nz = _npz_scalar(data, "nz")
            cell_m = _npz_scalar(data, "cell_m")
    except Exception as exc:  # noqa: BLE001 - reported, never raised
        return None, f"{dump.name} could not be opened ({type(exc).__name__}: {exc})"

    def recorded(value):
        """The stored float, or None when it is absent or not finite."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    eps_r = recorded(eps_r)
    h_mm = recorded(h_mm)
    w_mm = recorded(w_mm)
    f_hz = recorded(f_hz)
    nz = recorded(nz)
    cell_m = recorded(cell_m)
    geometry = {
        "eps_r": eps_r,
        "h": None if h_mm is None else h_mm * 1e-3,
        "w": None if w_mm is None else w_mm * 1e-3,
        "height": None if (nz is None or cell_m is None) else nz * cell_m,
        "f_hz": f_hz,
    }
    absent = [
        name
        for name in ("eps_r", "h", "w", "height", "f_hz")
        if _as_float(geometry.get(name)) is None
    ]
    if absent:
        names = ", ".join(absent)
        return None, (
            "the dump records no cross-section geometry for this dump, so "
            f"{names} is/are absent from both the record and the npz"
        )
    return geometry, (
        "eps_r, substrate_h_mm, strip_w_mm, f_ref_hz and nz x cell_m from the "
        "dump itself"
    )


def _mode_view(page, *, lateral_cells, k, memo, started):
    """``mode_view``'s body, raising; the wrapper turns a raise into a reason."""
    if not isinstance(page, dict):
        return _mode_fail(
            f"page is {type(page).__name__}, not the dict reload_page returns"
        )
    path = page.get("path")
    if not path:
        return _mode_fail("page carries no dump path, so there is no sibling record")
    dump = Path(path)
    candidates = _record_candidates(dump)
    record_path = next((p for p in candidates if p.is_file()), None)
    # The memo key names the file that actually carries the geometry, and when it
    # last changed: the record when one exists, otherwise the dump the fallback
    # reads - so an edited input is a miss on either path.
    source = record_path if record_path is not None else dump
    try:
        key = (str(source), source.stat().st_mtime, int(lateral_cells), int(k))
    except OSError:
        key = (str(source), 0.0, int(lateral_cells), int(k))
    if key in memo:
        # The stored dict itself, deliberately: identity is the observable proof
        # that the memo answered, and it is treated as read-only by every caller.
        return memo[key]

    record = None
    if record_path is not None:
        record = page.get("record")
        if not isinstance(record, dict):
            record = _read_json(record_path)
        if not isinstance(record, dict):
            return _mode_fail(f"study record {record_path.name} is unreadable")
        geometry = record.get("geometry")
        if not isinstance(geometry, dict):
            return _mode_fail(
                f"study record {record_path.name} has no geometry block"
            )
        missing = [
            name
            for name in ("eps_r", "h", "w", "height", "f_hz")
            if _as_float(geometry.get(name)) is None
        ]
        if missing:
            return _mode_fail(f"record geometry lacks {', '.join(missing)}")
        geometry_source = "record"
    else:
        # No record is not the same as no geometry. The vis dump stores part of
        # its own cross-section, so the mode is solved from the numbers that ARE
        # recorded and the caption says which file they came from. When even
        # those are absent this refuses and NAMES them - the panel never fills
        # in an eps_r or a substrate height it did not read.
        geometry, note = _mode_geometry_from_dump(dump)
        if not isinstance(geometry, dict):
            return _mode_fail(
                "no study record beside the dump (tried "
                + ", ".join(p.name for p in candidates)
                + "), and the dump's own metadata cannot stand in for it: "
                + note
            )
        geometry_source = "dump"

    mode2d = _mode2d()
    mesh, boundaries, extent = cross_section_mesh(
        geometry, lateral_cells=lateral_cells
    )
    ground, strip, _wall = boundaries
    h = float(geometry["h"])
    eps_t = np.where(mesh.centroid[:, 1] < h, float(geometry["eps_r"]), 1.0)
    k0 = float(mode2d.k0_from_freq(float(geometry["f_hz"])))
    # Conductors only: the Laplace problem needs the union to split into exactly
    # two connected groups, and the fencing wall would join them into one.
    laplace = mode2d.eps_eff_laplace(mesh, eps_t, boundaries=(ground, strip))
    eps_eff = float(laplace["eps_eff"])
    # BETA-SQUARED units: this is the pencil's shift, in rad^2/m^2.
    sigma = k0 * k0 * eps_eff
    solved = mode2d.solve_modes(
        mesh, k0, sigma, eps_r=eps_t, boundaries=boundaries, k=int(k)
    )

    line = record.get("line") if isinstance(record, dict) else None
    line = line if isinstance(line, dict) else {}
    beta = None if solved.beta is None else float(solved.beta)
    ratios = tuple(solved.curl_ratio or ())
    result = {
        "ok": True,
        "reason": "",
        "beta_rad_per_m": beta,
        "eps_eff": float(solved.eps_eff),
        "residual": float(solved.residual),
        "curl_ratio": (
            float(ratios[int(solved.chosen)]) if ratios else float("nan")
        ),
        "beta_banked": VIS_BETA_BANKED_RAD_PER_M,
        "beta_model": _as_float(line.get("beta_model")),
        "delta_vs_banked_pct": _mode_delta_pct(
            beta, VIS_BETA_BANKED_RAD_PER_M
        ),
        "delta_vs_model_pct": _mode_delta_pct(beta, line.get("beta_model")),
        "grid": np.zeros((MODE_GRID_CELLS, MODE_GRID_CELLS)),
        "extent": extent,
        "n_nodes": int(mesh.n_nodes),
        "n_edges": int(mesh.n_edges),
        "seconds": 0.0,
        "caption": "",
        "geometry_source": geometry_source,
        # The frequency this solve was actually driven at: the caption must be
        # able to print it rather than inherit the record's, which is absent.
        "geometry_f_hz": float(geometry["f_hz"]),
    }
    # The field needs the solved mode, so it is sampled after the dict exists and
    # before the timing is closed: a caption that under-reports the wall clock is
    # exactly the kind of flattery this panel must not print.
    result["grid"] = _mode_field_grid(solved, extent)
    # The SAME box and the SAME solve, sampled for the ARROW field: (E_y, E_z) on
    # a strided lattice (MODE_QUIVER_STRIDE), so a point with no finite field
    # carries NaN and gets no arrow instead of a zero-length one. Never raises: a
    # refusal leaves an all-NaN grid and the |E| picture is what the panel shows.
    result["grid_vec"] = _mode_vector_grid(solved, extent)
    # The axes that sampling used, carried on the result so a view can place an
    # arrow without re-deriving them from ``extent``: a candidate view is a COPY
    # of this dict, so this one key covers the fundamental and every candidate.
    result["grid_vec_axes"] = _mode_grid_axes(solved, extent)
    # EVERY candidate the pencil kept, not only the one it picked, each with its
    # own |E| sampled from the SAME solve above - so a pick in the browser is a
    # lookup and never a re-solve. ``chosen`` is carried as an INDEX into
    # ``candidates`` so a picker item and a picture cannot drift apart, and the
    # records are the compute layer's own dicts: beta is None exactly where
    # ``beta_sq <= 0``, i.e. at or below cutoff, which ``_select_and_pack`` can never
    # pick - the picker repeats that instead of inventing a beta for the row.
    result["chosen"] = int(solved.chosen)
    # Named `kept`/`grids`, not `candidates`: that name above is the list of
    # record PATHS this page was searched for, and a second meaning for it in
    # the same function is how a later edit reads the wrong one.
    kept = []
    grids = []
    grid_vecs = []
    try:
        records = [dict(record) for record in mode2d.candidate_records(solved)]
    except Exception as exc:  # noqa: BLE001 - the picker is an EXTRA, the panel is not
        print(f"[poc_app] mode candidates unavailable: {exc}", file=sys.stderr)
        records = []
    for record in records:
        try:
            grid = _mode_field_grid(solved, extent, index=record["index"])
        except Exception as exc:  # noqa: BLE001 - one row is not the panel
            print(
                f"[poc_app] mode candidate #{record.get('index')} grid skipped: "
                f"{exc}",
                file=sys.stderr,
            )
            continue
        # This candidate's OWN arrow field, on the axes the fundamental above
        # used: a pick that shows a candidate's |E| must show that candidate's
        # arrows, or the arrows and the picture would describe two modes.
        grid_vec = _mode_vector_grid(solved, extent, index=record["index"])
        # Appended together and only on success, so the lists stay aligned: a
        # record whose field could not be sampled is not offered as a row the
        # picker can point at, because there would be no picture behind it.
        kept.append(record)
        grids.append(grid)
        grid_vecs.append(grid_vec)
    result["candidates"] = kept
    result["candidate_grids"] = tuple(grids)
    result["candidate_grid_vecs"] = tuple(grid_vecs)
    # Closed AFTER the candidate sampling, so the wall clock this caption prints
    # is what the press actually cost.
    result["seconds"] = time.perf_counter() - started
    result["caption"] = _mode_caption(result, mesh)
    memo[key] = result
    return result


def mode_view(page, *, lateral_cells=44, k=4, cache=None) -> dict:
    """Solve the cross-section mode for the arm a page is showing. NEVER raises.

    ``page`` is the dict :func:`reload_page` returns (or anything carrying a
    ``path``). The geometry is looked for in this order, and the order matters:

    1. the STUDY RECORD written beside the dump - it carries the geometry the
       run was actually built on, so it is the authority;
    2. the dump's OWN metadata, when no record sits beside it - ``eps_r``,
       ``substrate_h_mm``, ``strip_w_mm``, ``f_ref_hz`` and ``nz * cell_m`` are
       stored numbers, not estimates, and a solve from them is a real solve
       (the caption then says so, because its drive frequency is the dump's
       ``f_ref_hz``, not the run's recorded single frequency);
    3. a refusal from ``_mode_fail`` naming the quantities that are absent from
       BOTH - a missing ``eps_r`` is reported by name and never filled in.

    The label the answer carries, ``geometry_source``, says which of the first
    two answered. It never raises and every failure is ``{'ok': False,
    'reason': ...}``.

    Returns ``ok`` True plus ``beta_rad_per_m``, ``eps_eff``, ``residual``,
    ``curl_ratio``, ``beta_banked``, ``beta_model``, ``delta_vs_banked_pct``,
    ``delta_vs_model_pct``, ``grid`` (``|E|`` of the fundamental on a square
    sampling of the box), ``extent``, ``n_nodes``, ``n_edges``, ``seconds`` and
    ``caption``, plus ``chosen`` (the picked candidate's index), ``candidates``
    (the pencil's own records, every one it kept) and ``candidate_grids`` (the
    ``|E|`` of each, aligned with ``candidates``). It also carries the ARROW
    field those pictures can be overlaid with: ``grid_vec`` - ``(E_y, E_z)`` on
    the strided lattice ``MODE_QUIVER_STRIDE`` takes out of the same square
    sampling, NaN where the mesh has no field - ``grid_vec_axes`` (the ``(y, z)``
    sampling axes in metres, so an arrow can be placed without re-deriving them)
    and ``candidate_grid_vecs`` (one per candidate, aligned with
    ``candidates``). A view copied for a pick carries that candidate's own
    ``grid_vec``. ``k`` defaults to 4 - the
    same count ``solve_modes`` defaults to - because a panel that reports ONE
    mode while the pencil extracted four is hiding the others.

    On any bad input it returns ``{'ok': False, 'reason': ...}``
    with a short cause - a missing record, an unreadable one, a missing geometry
    key, a mesh that will not build, a solve that will not converge - because
    the caller has a browser panel to update and no way to catch anything.

    WHAT THIS IS NOT: it is not an impedance, and it never calls
    ``solve_modes_mixed`` or ``mode_z0_from_power``. Z0 is out of scope, and the
    mixed path is the one that once hung for over 300 s on this very geometry;
    the transverse (``e_t``) pencil used here is the cheap, audited one.

    ``cache`` is the memo dict, defaulting to the module-level one; a second
    press with the same record file, mtime, cell count and ``k`` returns the
    stored dict unchanged (identity, not a re-solve).
    """
    started = time.perf_counter()
    memo = _MODE_VIEW_MEMO if cache is None else cache
    try:
        return _mode_view(
            page, lateral_cells=lateral_cells, k=k, memo=memo, started=started
        )
    except Exception as exc:  # noqa: BLE001 - the panel needs a reason, not a raise
        return _mode_fail(f"{type(exc).__name__}: {exc}")


#: What the Mode control says before it has ever been pressed. The panel is an
#: EXTRA beside the animation, so its resting text states both the promise and
#: the price: one press, solved from the record beside the dump.
MODE_PANEL_HINT = (
    "Mode (2D cross-section) has not been run for this page yet: press the "
    "Mode button to solve the quasi-TEM mode of the cross-section on screen. "
    "The solve reads the study record written beside the dump and reports "
    "beta, eps_eff, the solver residual and the mesh size - it also draws the "
    "mode's |E| as a turbo sheet at the near x-cut."
)


def _animation_title_text(structure_label) -> str:
    """The page TITLE while the field dump is what is on screen.

    The 3D view draws |Ez| of the dump, so the title says |Ez|. It is a
    function, and the only place this sentence is written, because the title
    has to follow the picture: a solved mode cross-section on the same view is
    |E_t| (see ``_mode_title_text``), and a title that keeps claiming |Ez|
    over a mode picture is a false statement about what is on screen.
    """
    return f"{structure_label} - |Ez| animation"


def _mode_title_text(structure_label, index=None) -> str:
    """The page TITLE while a solved mode cross-section is on screen.

    ``index`` is the candidate the picture shows, numbered exactly as the
    picker's own rows are (``_mode_candidate_title``'s ``#index``), so the
    title and the row a reader picked never disagree. Without an index - a
    caller that does not know which candidate it drew - the title simply omits
    the number rather than guessing one.
    """
    title = f"{structure_label} - Port Mode Profiles (|E_t|)"
    if isinstance(index, int) and not isinstance(index, bool) and index >= 0:
        title += f", candidate #{index}"
    return title


def _mode_button_label(result) -> str:
    """The Mode control's LABEL for a ``mode_view`` result. NEVER raises.

    One function, because the label at boot, the label after a press and the
    label after a finished solve replaces the page must say the same thing for
    the same result: the control reports whether its panel is unsolved, solved
    or refused before a reader gets to the caption.
    """
    try:
        if not isinstance(result, dict):
            return "Mode (2D cross-section)"
        if result.get("ok"):
            beta = result.get("beta_rad_per_m")
            if isinstance(beta, (int, float)) and beta == beta:
                return f"Mode: {float(beta):.2f} rad/m"
            return "Mode: solved"
        return "Mode: refused"
    except Exception:  # noqa: BLE001 - a label is never worth a traceback
        return "Mode (2D cross-section)"


def _mode_caption_text(result) -> str:
    """The Mode panel's CAPTION for a ``mode_view`` result. NEVER raises.

    Three states, and the refusal is one of them: a press that cannot solve says
    WHY on the same line the numbers would have used, so a dump with no study
    record beside it is a visible answer rather than a button that did nothing.
    An OK result is quoted from the solve's OWN caption, so the panel never
    re-words what the compute layer measured.
    """
    try:
        if not isinstance(result, dict):
            return MODE_PANEL_HINT
        if result.get("ok"):
            caption = result.get("caption")
            if isinstance(caption, str) and caption.strip():
                return caption
            return "mode solved (the solve returned no caption)"
        reason = result.get("reason")
        text = reason.strip() if isinstance(reason, str) else ""
        return "mode refused: " + (text or "no reason given")
    except Exception:  # noqa: BLE001 - the hint is a safe floor
        return MODE_PANEL_HINT


def _mode_candidate_title(record, *, chosen=None) -> str:
    """One picker line for a ``mode2d.candidate_records`` record. NEVER raises.

    The line repeats the compute layer's own numbers and nothing else: the
    candidate's index, its beta (or the fact that it has none) and its eps_eff.
    A record whose ``beta`` is a number is propagating. One whose ``beta`` is
    None is NOT, and its ``beta_sq`` says which of the two remaining cases it
    is: exactly at cutoff (``0`` - no beta and no decay either) or evanescent
    (``< 0`` - no beta, but an ``alpha = sqrt(-beta_sq)`` Np/m decay constant).
    ``_select_and_pack`` keeps both cases only to REJECT them
    (``eligible = acceptable & (vals > 0.0)``), so each row names its case and
    says it is never pickable, rather than printing a beta it was never
    computed with. The solver's own pick is named, because the picker's first
    job is to say which row the caption above the picture is describing.
    """
    try:
        index = int(record["index"])
    except Exception:  # noqa: BLE001 - a row is not worth a traceback
        return "candidate"
    try:
        eps = record.get("eps_eff")
        eps_text = (
            f"eps_eff {float(eps):.3f}"
            if isinstance(eps, (int, float)) and eps == eps
            else "eps_eff not recorded"
        )
        beta = record.get("beta")
        if isinstance(beta, (int, float)) and beta == beta:
            text = f"#{index}  beta {float(beta):.2f} rad/m  {eps_text}"
            if chosen is not None and index == int(chosen):
                text += "  (the solver's pick)"
            return text
        beta_sq = record.get("beta_sq")
        if isinstance(beta_sq, (int, float)) and beta_sq == beta_sq:
            if beta_sq == 0.0:
                return (
                    f"#{index}  At cutoff  beta_sq 0  {eps_text}  "
                    "(never pickable)"
                )
            if beta_sq < 0.0:
                alpha = record.get("beta_imag")
                if not (
                    isinstance(alpha, (int, float)) and math.isfinite(alpha)
                ):
                    alpha = math.sqrt(-float(beta_sq))
                if math.isfinite(alpha):
                    return (
                        f"#{index}  Evanescent  alpha {alpha:.2f} Np/m  "
                        f"beta_sq {float(beta_sq):.3g}  {eps_text}  "
                        "(below cutoff, never pickable)"
                    )
                return (
                    f"#{index}  Evanescent  beta_sq {float(beta_sq):.3g}  "
                    f"{eps_text}  (below cutoff, never pickable)"
                )
        cutoff = (
            f"beta_sq {float(beta_sq):.3g}"
            if isinstance(beta_sq, (int, float)) and beta_sq == beta_sq
            else "beta_sq not recorded"
        )
        return (
            f"#{index}  no beta ({cutoff}: below cutoff, never pickable)  "
            f"{eps_text}"
        )
    except Exception:  # noqa: BLE001
        return f"#{index}"


#: The ``value`` a refusal's one picker row carries. A kept candidate's value is
#: always its own index, i.e. >= 0, so this can never name one: the select's
#: closed state (``v_model=("mode_choice", 0)``) then shows the reason with NO
#: row selected, instead of implying the solver kept a candidate it did not.
_MODE_REFUSED_VALUE = -1


def _mode_candidate_items(result):
    """The Mode picker's items for a ``mode_view`` result. NEVER raises.

    A REFUSAL yields one row carrying the solver's OWN reason, because the
    dropdown is the only channel a press offers its outcome through: an empty
    picker beside a ``mode refused: ...`` caption tells the reader that
    something failed and then hides what. That row's ``value`` is
    :data:`_MODE_REFUSED_VALUE`, which no candidate index can be, so it never
    reads as a selection and picking it is inert (``_on_mode_choice`` returns
    early: a refusal leaves ``handles["mode_result"]`` as None).

    ``[]`` for everything that genuinely carries nothing to offer: a non-dict,
    an ok result with no candidate list (a fake result from a proof, or an older
    cached dict), and a refusal that records no reason string. ``value`` on a
    candidate's item is its own index, the same number ``result['chosen']`` and
    ``candidate_grids`` are keyed by.
    """
    try:
        if not isinstance(result, dict):
            return []
        if not result.get("ok"):
            reason = result.get("reason")
            if reason is None:
                return []
            return [{"title": f"Error: {reason}", "value": _MODE_REFUSED_VALUE}]
        chosen = result.get("chosen")
        items = []
        for record in result.get("candidates") or ():
            if not isinstance(record, dict):
                continue
            index = record.get("index")
            if not isinstance(index, int):
                continue
            items.append(
                {
                    "title": _mode_candidate_title(record, chosen=chosen),
                    "value": int(index),
                }
            )
        return items
    except Exception:  # noqa: BLE001
        return []


def _mode_view_for_candidate(result, index):
    """``result`` re-pointed at one candidate's grid, or None. NEVER raises.

    None means "nothing to draw, and nothing to say": the result is a refusal,
    it carries no candidates, or the pick names an index this solve did not
    keep. The caller then leaves the picture and the caption exactly as they
    are rather than drawing the fundamental under a candidate's label.
    """
    try:
        if not isinstance(result, dict) or not result.get("ok"):
            return None
        picked = int(index)
        # A view carries the candidate's OWN arrow field beside its ``|E|``, so
        # an overlay drawn on top of a picked picture is that candidate's field
        # and not the fundamental's. The vectors are indexed by the same
        # position as the grid, and a result that carries no vectors at all (an
        # older shape, or a test fixture) is answered without one rather than
        # with the fundamental's - the STALE key is dropped so nothing can be
        # drawn from it.
        vecs = result.get("candidate_grid_vecs") or ()
        for position, (record, grid) in enumerate(
            zip(result.get("candidates") or (), result.get("candidate_grids") or ())
        ):
            if not isinstance(record, dict) or grid is None:
                continue
            if int(record.get("index")) == picked:
                view = dict(result)
                view["grid"] = grid
                if position < len(vecs) and vecs[position] is not None:
                    view["grid_vec"] = vecs[position]
                else:
                    view.pop("grid_vec", None)
                return view
        return None
    except Exception:  # noqa: BLE001
        return None


def _mode_choice_caption_text(result, index) -> str:
    """The caption for a PICKED candidate. NEVER raises, never re-words.

    The solve's own caption is returned UNCHANGED while the picker still points
    at the solver's pick, so the text a press produces is byte-for-byte the text
    a pick keeps. Only a pick that differs gets a sentence, and that sentence
    says which row is on screen and that the numbers still above it are the
    solver's - the caption's numbers are never silently turned into another
    candidate's.
    """
    base = _mode_caption_text(result)
    try:
        if not isinstance(result, dict) or not result.get("ok"):
            return base
        items = _mode_candidate_items(result)
        if not items:
            return base
        chosen = result.get("chosen")
        try:
            picked = int(index)
        except (TypeError, ValueError):
            return base
        if chosen is not None and picked == int(chosen):
            return base
        title = next((item["title"] for item in items if item["value"] == picked), None)
        if title is None:
            return base
        return (
            f"{base}  [showing candidate {title} - the numbers above are the "
            f"solver's pick, #{chosen}]"
        )
    except Exception:  # noqa: BLE001
        return base


def _mode_picture_grid(result, *, x_mm: float, y_centre_mm: float = 0.0):
    """A ``mode_view`` result as ONE y-z sheet standing at ``x_mm``. NEVER raises.

    The compute layer hands back ``grid`` (a ``(z, y)`` sampled ``|E|`` of the
    fundamental) and ``extent`` = ``(y_max_m, z_max_m)``. This maps them onto a
    single-sample-thick ``pyvista.ImageData`` in MILLIMETRES - the unit the
    plotter, the cell size and the cut-plane stations are all in - spanning y in
    [y_centre_mm - y_max, y_centre_mm + y_max] and z in [0, z_max] at one fixed
    x, which is the plane the two x-cut sheets already stand in. ``y_centre_mm``
    defaults to 0, the grid-centred default this sheet has always had.

    Returns None when there is nothing drawable: a refusal, a grid that is not a
    usable 2-D array, a non-finite or empty extent. The caller keeps its caption
    and numbers in that case - the picture is the extra, never the answer.
    """
    try:
        if not isinstance(result, dict) or not result.get("ok"):
            return None
        grid = result.get("grid")
        extent = result.get("extent")
        if grid is None or extent is None:
            return None
        data = np.asarray(grid, dtype=float)
        if data.ndim != 2 or min(data.shape) < 2:
            return None
        if not np.all(np.isfinite(data)):
            return None
        y_max_m, z_max_m = float(extent[0]), float(extent[1])
        if not (np.isfinite(y_max_m) and np.isfinite(z_max_m)):
            return None
        if y_max_m <= 0.0 or z_max_m <= 0.0:
            return None
        import pyvista as pv  # deferred: --list-keys / --dump-state stay numpy-only

        # ``grid`` is indexed (z, y) and VTK wants its FASTEST axis first, so the
        # transpose plus a Fortran ravel puts y fastest and z next - the same
        # order the dump's own x-cut sheets are handed over in. Getting this
        # wrong does not raise: it draws the cross-section mirrored into the
        # wrong axis.
        values = np.ascontiguousarray(data.T.ravel(order="F"), dtype=float)
        n_y, n_z = int(data.shape[1]), int(data.shape[0])
        y_max_mm, z_max_mm = y_max_m * 1e3, z_max_m * 1e3
        image = pv.ImageData()
        image.dimensions = (1, n_y, n_z)
        # A 1 mm stand-in along the single-sample x axis: with one point on that
        # axis the spacing cannot move the sheet, and a zero spacing would be a
        # singular transform.
        image.spacing = (1.0, 2.0 * y_max_mm / float(n_y - 1), z_max_mm / float(n_z - 1))
        image.origin = (float(x_mm), float(y_centre_mm) - y_max_mm, 0.0)
        image.point_data["mode_e_abs"] = values
        image.point_data.active_scalars_name = "mode_e_abs"
        return image
    except Exception:  # noqa: BLE001 - a picture is never worth a traceback
        return None


def _mode_quiver_arrows(result, *, x_mm: float, y_centre_mm: float = 0.0):
    """The mode's transverse field as arrow anchors and shafts, in MILLIMETRES.

    Returns ``(points, vectors)``, both ``(n, 3)``: where each arrow starts on
    the cross-section plane the picture stands in (``x`` fixed at ``x_mm``, y
    mapped exactly as ``_mode_picture_grid`` maps it, z from the grid's own
    axis) and the shaft lying IN that plane. The third component is ZERO, not
    omitted: this mode's field has two components and neither points out of the
    cross-section, so an arrow out of the plane would be a component nobody
    solved for.

    The shaft is the field's own DIRECTION - ``(E_y, E_z)`` normalised, so the
    eigenvector's sign is visible and a sign reversal cannot hide - and a length
    LINEAR in ``|E_t|``: ``MODE_QUIVER_MAX_LEN_FRACTION`` of the shorter side of
    the sampled box at the peak, in proportion below it. Two arrows therefore
    stand in the recorded ratio of the two fields, and the longest still fits
    inside its own lattice cell (see the constant).

    A NaN sample is skipped - a point with no field gets no arrow - and a result
    with no vector grid, no axes, a non-finite extent or a field that is zero
    everywhere returns EMPTY arrays. The caller then draws nothing, rather than
    a lattice of zero-length glyphs that reads as a solved zero field.
    """
    empty = (np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=float))
    try:
        if not isinstance(result, dict):
            return empty
        data = result.get("grid_vec")
        axes = result.get("grid_vec_axes")
        extent = result.get("extent")
        if data is None or axes is None or extent is None:
            return empty
        data = np.asarray(data, dtype=float)
        if data.ndim != 3 or data.shape[2] != 2 or min(data.shape[:2]) < 1:
            return empty
        gy = np.asarray(axes[0], dtype=float).ravel()
        gz = np.asarray(axes[1], dtype=float).ravel()
        if gy.size != int(data.shape[1]) or gz.size != int(data.shape[0]):
            return empty
        x_mm = float(x_mm)
        y_centre_mm = float(y_centre_mm)
        y_max_m, z_max_m = float(extent[0]), float(extent[1])
        if not (np.isfinite(y_max_m) and np.isfinite(z_max_m)):
            return empty
        if y_max_m <= 0.0 or z_max_m <= 0.0:
            return empty
        # Sampled AND non-zero: a NaN is "no field here", and a literal zero is
        # "no direction here", which an arrow cannot draw either.
        usable = np.all(np.isfinite(data), axis=2) & np.any(data != 0.0, axis=2)
        if not np.any(usable):
            return empty
        kz, ky = np.nonzero(usable)
        ey = data[kz, ky, 0]
        ez = data[kz, ky, 1]
        mag = np.hypot(ey, ez)
        peak = float(np.max(mag))
        if not np.isfinite(peak) or peak <= 0.0:
            return empty
        y_span_mm = abs(float(gy[-1]) - float(gy[0])) * 1e3
        z_span_mm = abs(float(gz[-1]) - float(gz[0])) * 1e3
        max_len_mm = MODE_QUIVER_MAX_LEN_FRACTION * min(y_span_mm, z_span_mm)
        if not np.isfinite(max_len_mm) or max_len_mm <= 0.0:
            return empty
        length = max_len_mm * mag / peak
        points = np.stack(
            [
                np.full(kz.shape, x_mm, dtype=float),
                y_centre_mm + 1e3 * gy[ky],
                1e3 * gz[kz],
            ],
            axis=1,
        )
        vectors = np.stack(
            [np.zeros(kz.shape, dtype=float), length * ey / mag, length * ez / mag],
            axis=1,
        )
        return points, vectors
    except Exception:  # noqa: BLE001 - an arrow is never worth a traceback
        return empty


#: Take every ``stride``-th CELL of the volume on each axis for the arrow field:
#: 13 x 43 x 5 = 2795 arrows on the shipped 62 x 212 x 22 grid (that is
#: ``ceil(n / stride)`` per axis, so 13 not 12 on 62), which is a density a reader
#: can follow. The volume itself keeps every cell - only the arrows are strided,
#: and a cell the arrows do not sit on simply has none.
VOLUME_QUIVER_STRIDE = 5
#: Longest arrow, as a fraction of ONE stride cell of the arrow lattice. WHY the
#: arrow's OWN cell and not the box: ``stride * cell_mm`` is the distance between
#: neighbouring arrows, so a shaft of 90 % of it keeps its head inside the cell it
#: was drawn from, and two neighbouring arrows cannot run into each other whatever
#: the field does. ``_mode_quiver_arrows`` may anchor its length to the extent of
#: the sampled box because it draws ONE sheet, where a single span bounds every
#: arrow; a volume has no such bound - tie the length to the box span and a 2 mm
#: cell in a 20 cm stack gets a 20 cm shaft, and the lattice passes through itself.
#: The length below the peak is scaled LINEARLY by ``|E|``, so the ratio between
#: two arrows is the recorded ratio of the two fields and not a re-normalisation
#: of it.
VOLUME_QUIVER_MAX_LEN_FRACTION = 0.9
#: A sample is DRAWN only if its magnitude is strictly greater than this fraction
#: of the PEAK sample's. WHY a ratio and not an absolute epsilon in V/m or mm: a
#: real solve's far field bottoms out in denormal-scale round-off, and on the
#: shipped dump 116 of the 2795 arrows had a shaft under ``1e-9`` mm - invisible
#: dots a reader mistakes for stray marks rather than for data. But the field's
#: ABSOLUTE scale moves with frequency and with drive amplitude, so a threshold in
#: V/m would be far too high at one frequency and far too low at another: it would
#: hide real structure in the quiet run and keep the noise in the loud one. "Six
#: decades below the strongest sample" is the same statement at every frequency,
#: which is the only form of it that survives a change of drive.
VOLUME_QUIVER_REL_FLOOR = 1e-6


def _volume_arrows(info, *, stride=VOLUME_QUIVER_STRIDE):
    """The colocated ``E`` volume as arrow anchors and shafts, in MILLIMETRES.

    Takes the loader's ``info`` dict -- the same way ``_mode_quiver_arrows``
    takes its result dict -- so :data:`VOLUME_KEY` and the array's layout stay a
    loader detail and no page builder has to know either.

    Returns ``(points, vectors)``, both ``(n, 3)``: one arrow per usable sample
    of the strided lattice, in MILLIMETRES. The anchor is the CENTRE of the cell
    the sample came from, ``(i + 0.5) * cell_mm`` on each axis and not
    ``i * cell_mm``: the values in the volume were averaged onto the cell centre,
    so anchoring on the face would put the arrow half a cell away from the point
    the field was actually computed at.

    WHY a volume of three components is a vector field and a single component is
    not: the archive ships the solve's flat ``e`` vector with each component
    staggered on its OWN edge set, so no two components share a point in it.

    ``emfit.operators.edge_to_cell_centres`` averages each component onto the
    common cell centres, and only after that colocation do all three live at one
    point. An ``Ez``-only volume, before that step, is a SCALAR field on a grid:
    an arrow drawn from it would invent two directions the solve never produced.
    Hence the shape check -- ``(nx, ny, nz, 3)`` exactly, three components at one
    point -- and nothing else is accepted.

    The shaft is the field's own DIRECTION (normalised, so a sign reversal cannot
    hide) and a length LINEAR in ``|E|``: ``VOLUME_QUIVER_MAX_LEN_FRACTION`` of
    the arrow's OWN stride cell at the peak, in proportion below it. Two arrows
    therefore stand in the recorded ratio of the two fields, and the longest
    still fits inside the cell it was drawn from (see the constant).

    Samples more than ``1 / VOLUME_QUIVER_REL_FLOOR`` (six decades) BELOW THE PEAK
    are dropped as well, and the drop is relative to the peak on purpose: a real
    far field bottoms out in denormal-scale round-off, which on the shipped dump
    put 116 of 2795 shafts under ``1e-9`` mm - dots a reader reads as stray marks.
    A threshold in V/m could not do this job, because the field's absolute scale
    moves with frequency and with drive amplitude. The peak is measured BEFORE the
    floor is applied and never after it, so the floor cannot shrink the reference
    it is being measured against; every survivor keeps its length in the recorded
    ratio of the fields.

    A NaN sample is skipped -- a point with no field gets no arrow -- and so is a
    literal zero, which has no direction to draw. A volume that is zero or
    unanswerable everywhere, a cell size that is not a finite positive number of
    METRES, or a stride that is not a positive integer returns EMPTY arrays: the
    caller then draws nothing, rather than a lattice of zero-length glyphs that
    reads as a solved zero field.
    """
    empty = (np.empty((0, 3), dtype=float), np.empty((0, 3), dtype=float))
    try:
        if not isinstance(info, dict):
            return empty
        volume = info.get(VOLUME_KEY)
        cell_m = info.get("cell_m")
        if volume is None or cell_m is None:
            return empty
        volume = np.asarray(volume, dtype=float)
        if volume.ndim != 4 or volume.shape[3] != 3 or min(volume.shape[:3]) < 1:
            return empty
        # METRES in the dump, millimetres in the picture - converted ONCE here so
        # no later line has to remember which unit it is holding.
        cell_mm = float(cell_m) * 1e3
        if not np.isfinite(cell_mm) or cell_mm <= 0.0:
            return empty
        try:
            stride = int(stride)
        except (TypeError, ValueError):
            return empty
        if stride < 1:
            return empty
        nx, ny, nz = (int(n) for n in volume.shape[:3])
        ix = np.arange(0, nx, stride)
        iy = np.arange(0, ny, stride)
        iz = np.arange(0, nz, stride)
        # ``ix_`` is the strided subvolume itself, gathered in one go: the mask
        # below must be applied to the SAMPLES, so peak and anchor are drawn from
        # the same set of cells the arrows sit on.
        sampled = volume[np.ix_(ix, iy, iz)]
        # Sampled AND non-zero: a NaN is "no field here", and a literal zero is
        # "no direction here", which an arrow cannot draw either.
        usable = np.all(np.isfinite(sampled), axis=3) & np.any(sampled != 0.0, axis=3)
        if not np.any(usable):
            return empty
        ai, bi, ci = np.nonzero(usable)
        vecs = sampled[ai, bi, ci]
        mag = np.sqrt(np.sum(vecs * vecs, axis=1))
        peak = float(np.max(mag))
        if not np.isfinite(peak) or peak <= 0.0:
            return empty
        # The floor is applied HERE - after ``peak`` was measured and never
        # feeding back into it. A reference that shrank with its own filter would
        # drag the whole length scale down along with the noise. Strictly
        # greater, so a field that is uniform at the peak keeps every sample
        # instead of losing the ones that merely tie with it.
        keep = mag > peak * VOLUME_QUIVER_REL_FLOOR
        if not np.any(keep):
            # Unreachable in principle: the sample that ATTAINED ``peak`` always
            # passes ``peak > peak * 1e-6``. Guarded anyway rather than argued,
            # because the cost of being wrong here is a lattice of zero arrows.
            return empty
        ai, bi, ci = ai[keep], bi[keep], ci[keep]
        vecs = vecs[keep]
        mag = mag[keep]
        max_len_mm = VOLUME_QUIVER_MAX_LEN_FRACTION * stride * cell_mm
        if not np.isfinite(max_len_mm) or max_len_mm <= 0.0:
            return empty
        length = max_len_mm * mag / peak
        points = np.stack(
            [
                (ix[ai] + 0.5) * cell_mm,
                (iy[bi] + 0.5) * cell_mm,
                (iz[ci] + 0.5) * cell_mm,
            ],
            axis=1,
        )
        vectors = length[:, None] * vecs / mag[:, None]
        return points, vectors
    except Exception:  # noqa: BLE001 - an arrow is never worth a traceback
        return empty


def _volume_quiver_polydata(points, vectors):
    """``_volume_arrows`` output as ONE pyvista point cloud, or None.

    The seam between the arrow field and a renderer, and deliberately nothing
    more: the anchors become the cloud's points and the shafts become a
    POINT-data array named ``volume_e_quiver``, so a caller can glyph ``orient``
    and ``scale`` off that one array without this function knowing what an arrow
    looks like. Glyphing is NOT done here and no plotter is created - the caller
    owns the renderer, its camera, and the decision of whether to draw at all.

    Returns None, not empty arrays, when there is nothing to hand over: this
    feeds a renderer, and a renderer can skip a None in one ``if`` where it would
    otherwise have to interrogate a zero-row cloud. Both arguments must be
    FINITE ``(n, 3)`` float-convertible arrays of the SAME ``n >= 1``; None, a
    wrong width, a mismatch, a non-finite coordinate or an empty pair are all
    None.
    """
    try:
        if points is None or vectors is None:
            return None
        pts = np.asarray(points, dtype=float)
        vecs = np.asarray(vectors, dtype=float)
        if pts.ndim != 2 or vecs.ndim != 2:
            return None
        if pts.shape[1] != 3 or vecs.shape[1] != 3:
            return None
        if pts.shape[0] < 1 or pts.shape[0] != vecs.shape[0]:
            return None
        # A NaN anchor or a NaN shaft reaches the renderer as a NaN primitive:
        # pyvista accepts the array, so the failure would surface as a broken
        # picture far from here. Refused at the seam instead.
        if not np.all(np.isfinite(pts)) or not np.all(np.isfinite(vecs)):
            return None
        import pyvista as pv  # deferred: --list-keys / --dump-state stay numpy-only

        cloud = pv.PolyData(pts)
        cloud.point_data["volume_e_quiver"] = vecs
        return cloud
    except Exception:  # noqa: BLE001 - a picture is never worth a traceback
        return None


def _volume_abs_grid(info, cell_mm, grid_hint=None):
    """The whole colocated ``E`` volume as ONE cell-centred ``|E|`` image.

    Returns ``(image, meta)``. ``image`` is a ``pyvista.ImageData`` carrying one
    POINT-data array named ``e_abs``, or None; ``meta`` is a dict of ``clim``,
    ``reason`` and ``n``, and ``reason`` is None exactly when an image came back.
    A None is never an error the caller must handle - it means "draw the picture
    you drew before" - and ``reason`` says which of the causes applied.

    WHY the whole volume and not the plane stack: the dump's ``e`` covers EVERY
    grid cell, while ``plane_ez`` holds only the nine captured stations. |E| over
    the whole volume is the field the solve actually produced, on the lattice it
    produced it on, and it is what makes a 3D field read as a field instead of a
    thin slab of nine sheets.

    WHY the colocation is deferred to this reader: the ~1 s
    ``edge_to_cell_centres`` should be paid by a page that DRAWS |E|, not by
    every load of the dump. That is the same trade ``_volume_quiver_mesh`` makes,
    and both routes land on one lattice, so a dump loaded either way draws the
    same field.

    WHY the result is MEMOISED under :data:`VOLUME_ABS_KEY`: ``_redraw_scene``
    rebuilds the whole scene on every cut or station move, so a per-redraw
    colocation would be a per-move second. ``info`` is read, and the ONLY write
    into it is that cache entry, added once and never rewritten.

    The lattice is CELL-CENTRED throughout: ``dimensions`` is the dump's own
    ``(nx, ny, nz)``, ``spacing`` is ``cell_mm``, and ``origin`` is HALF A CELL in,
    because the colocation averaged each component onto a cell centre - the same
    anchor ``_volume_arrows`` draws its shafts at. The cell counts come from the
    dump's metadata and then from ``grid_hint`` (the record's ``geometry.grid``),
    and NEVER from ``e.size``: the raw vector is staggered, so its length counts
    EDGES, not the cells the colocation lands on.

    ``clim`` is 60 dB of the field above its own floor, ``(peak / 1000, peak)``:
    |E| over a whole line spans tens of decades down into round-off (the shipped
    dump bottoms out near 1e-31 V/m), so the caller draws this image log-scaled
    or shows nothing but the peak.

    Never raises and never returns a partially built image: an unusable volume,
    an unusable cell size, an unresolved grid or any failure on the way to the
    image is ``(None, meta-with-reason)``.
    """

    def _miss(reason):
        """Nothing to draw, plus the sentence that says why."""
        return None, {"clim": None, "reason": reason, "n": 0}

    try:
        if not isinstance(info, dict):
            return _miss("no volume in this dump")
        # The cache: an EXISTING entry is returned untouched, never rebuilt and
        # never rewritten - see the docstring for why it has to exist at all.
        cached = info.get(VOLUME_ABS_KEY)
        if isinstance(cached, dict) and cached.get("image") is not None:
            return cached["image"], {
                "clim": cached["clim"],
                "reason": None,
                "n": cached["n"],
            }
        cell_mm = float(cell_mm)
        if not np.isfinite(cell_mm) or cell_mm <= 0.0:
            return _miss("no finite positive cell size for the volume")

        # WHICH volume: the loader's already-colocated one when the dump was
        # asked for it, otherwise the archive's raw staggered vector, colocated
        # HERE on the first reader - the same two routes, and the same deferred
        # cost, as ``_volume_quiver_mesh``.
        volume = info.get(VOLUME_KEY)
        if volume is None:
            raw = info.get(VOLUME_RAW_KEY)
            if not isinstance(raw, dict) or raw.get("e") is None:
                return _miss("no volume in this dump")
            # Imported on use, like every other emfit use in this module: the
            # CLI paths (--help, --list-keys) stay stdlib + numpy only.
            from emfit.operators import edge_to_cell_centres

            ex, ey, ez = edge_to_cell_centres(
                raw["e"], raw["nx"], raw["ny"], raw["nz"]
            )
            volume = np.stack((ex, ey, ez), axis=-1)

        # The cell counts: the dump's own metadata first, then the record's
        # ``geometry.grid`` when it was supplied, and never ``e.size``. The
        # predicate is SHARED with the cut sliders (``_volume_grid_dims``), so a
        # sheet and this volume are always built on one lattice.
        dims = _volume_grid_dims(info, grid_hint)
        if dims is None:
            return _miss("no (nx,ny,nz) for the volume")
        nx, ny, nz = dims

        volume = np.asarray(volume)
        if np.iscomplexobj(volume):
            # A complex volume is a PHASOR: |E| is the modulus per component, so
            # the modulus is taken FIRST. Summing the phasors' complex squares
            # would cancel phase and draw a field the solve never had.
            volume = np.abs(volume)
        volume = np.asarray(volume, dtype=float)
        if volume.ndim != 4 or volume.shape[3] != 3 or min(volume.shape[:3]) < 1:
            return _miss("the volume is not an (nx, ny, nz, 3) array")
        if tuple(volume.shape[:3]) != dims:
            # A volume that does not fill the grid its own metadata states would
            # be drawn at the wrong positions; refused whole rather than skewed.
            return _miss("the volume does not fill its (nx,ny,nz) grid")

        ex = volume[..., 0]
        ey = volume[..., 1]
        ez = volume[..., 2]
        e_abs = np.sqrt(ex * ex + ey * ey + ez * ez)
        if e_abs.size < 1:
            return _miss("the volume is empty")
        if not np.all(np.isfinite(e_abs)):
            # ONE non-finite sample poisons the colour scale and the bounds, so
            # the picture would be wrong everywhere and not just there.
            return _miss("the volume has samples that are not finite")
        hi = float(np.max(e_abs))
        if not np.isfinite(hi) or hi <= 0.0:
            # Zero everywhere: a volume with no field in it is a wrong picture.
            return _miss("the volume is zero everywhere")

        import pyvista as pv  # deferred: the numpy-only CLI paths stay module-light

        image = pv.ImageData()
        image.dimensions = (nx, ny, nz)
        image.spacing = (cell_mm, cell_mm, cell_mm)
        # ORIGIN AT HALF A CELL, and not at 0: every sample in this volume is a
        # CELL CENTRE, so the first one sits half a cell in - the anchor
        # ``_volume_arrows`` draws at (``(i + 0.5) * cell_mm``).
        image.origin = (0.5 * cell_mm, 0.5 * cell_mm, 0.5 * cell_mm)
        # ``order="F"``: the sample's inner axis is its LAST one, and ``ImageData``
        # fills its points with x varying fastest, which is Fortran order.
        image.point_data["e_abs"] = np.ascontiguousarray(
            e_abs.ravel(order="F"), dtype=float
        )
        # 60 dB above the field's own floor: three decades below the peak. Above
        # it the bar would be all peak; below it there is round-off, not field.
        clim = (hi * 1e-3, hi)
        meta = {"clim": clim, "reason": None, "n": int(e_abs.size)}
        # ADD-ONLY: one entry, set once, so a second reader fits the same image
        # and nothing already in ``info`` is touched.
        info[VOLUME_ABS_KEY] = {"image": image, "clim": clim, "n": meta["n"]}
        return image, meta
    except Exception as exc:  # noqa: BLE001 - a picture is never worth a traceback
        return _miss(f"the |E| volume could not be built: {exc}")


def _volume_quiver_mesh(info, *, stride=VOLUME_QUIVER_STRIDE):
    """The whole-volume arrow field as ONE glyphed mesh, or None.

    The second half of the seam :func:`_volume_quiver_polydata` opens: that
    function hands over the anchors and the shafts, this one glyphs them with
    the same ``glyph(orient=..., scale=..., factor=1.0)`` call ``run_web_vis``
    makes for the mode field -- one glyph per point, oriented and scaled by a
    POINT-data array -- so the arrows are drawn by the same mechanism whatever
    draws them. The ARRAY name differs (``volume_e_quiver`` here,
    ``mode_e_arrows`` there) because the two fields are different fields; the
    call does not. Nothing here knows what a plotter is - the caller owns the
    renderer and decides whether to draw at all.

    The volume comes from :data:`VOLUME_KEY` when the loader already colocated
    it, and otherwise from :data:`VOLUME_RAW_KEY`, colocated HERE on the first
    reader: that deferral is the whole point of the raw stash -- the ~1 s
    ``edge_to_cell_centres`` is paid by a page that draws arrows, not by every
    load of the dump -- and it produces the same volume, so both routes land on
    one lattice. ``info`` is READ, never written into.

    None means "draw nothing": no volume on ``info`` by EITHER route, a volume
    with no sample above the relative floor, or any failure on the way to a
    mesh. The GL context is not touched - pyvista is imported here, not at
    module scope, so the numpy-only CLI paths still never pay for it.
    """
    try:
        if VOLUME_KEY not in info:
            if VOLUME_RAW_KEY not in info:
                # Neither route: there is nothing to draw, and saying so is the
                # caller's "no arrows on this dump", not an error.
                print(
                    f"[poc_app] 3D vectors not drawn: the dump carries no "
                    f"volume (neither '{VOLUME_KEY}' nor "
                    f"'{VOLUME_RAW_KEY}' is present)",
                    file=sys.stderr,
                )
                return None
            raw = info[VOLUME_RAW_KEY]
            # Imported on use, like every other emfit use in this module.
            from emfit.operators import edge_to_cell_centres

            ex, ey, ez = edge_to_cell_centres(
                raw["e"], raw["nx"], raw["ny"], raw["nz"])
            # A COPY of info, never a write into it: one reader must not change
            # what the next one sees.
            info = dict(info)
            info[VOLUME_KEY] = np.stack((ex, ey, ez), axis=-1)
        points, vectors = _volume_arrows(info, stride=stride)
        cloud = _volume_quiver_polydata(points, vectors)
        if cloud is None:
            print(
                f"[poc_app] 3D vectors not drawn: no arrows survived the "
                f"relative floor / stride (stride={stride})",
                file=sys.stderr,
            )
            return None
        import pyvista as pv  # noqa: F401 - deferred, see the docstring

        glyphed = cloud.glyph(
            orient="volume_e_quiver", scale="volume_e_quiver", factor=1.0
        )
        print(
            f"[poc_app] 3D vectors glyphed: {glyphed.n_points} points, "
            f"{glyphed.n_cells} cells, bounds={glyphed.bounds}",
            file=sys.stderr,
        )
        return glyphed
    except Exception as exc:  # noqa: BLE001 - a picture is never worth a traceback
        # Imported here: traceback is not needed anywhere else in this module,
        # and a failure on the way to a picture is the only place it helps.
        import traceback

        print(f"[poc_app] 3D vectors not drawn: {exc}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return None


def _volume_quiver_callback(plotter, info, state, handles):
    """The vis page's arrow overlay, as the ``show()`` closure it needs.

    WHY a factory and not a closure inside ``run_web_vis``: the overlay is three
    decisions - is the box ticked, is the mesh already built, is there an actor
    to replace - and none of them needs trame, a server or a live page. Built
    here, a test drives all three with a stub plotter and a namespace for
    ``state``, which is the only way the cache and the remove path can be
    pinned at all (the legacy page's copy of this logic, ``run_web``'s
    ``_show_volume_quiver``, is only reachable through a booted page).

    WHY the cache lives in this closure and not in ``handles``: ``show()`` runs
    on EVERY redraw - each cut-slider move and each station change - while the
    glyph costs ~1 s and ~140 MiB on the real dump (:func:`_volume_quiver_mesh`).
    One build per page is all there can ever be, because ``info`` cannot change
    under a running page. ``built`` is separate from ``mesh`` because None is a
    real answer (no volume in this dump, nothing above the floor) and must not
    be re-attempted on every redraw that follows it.

    The caller owns both the renderer and the render: this function adds and
    removes ONE actor and never calls ``plotter.render()``, because
    ``_redraw_scene`` renders immediately after the seam it is injected into
    (poc_app.py:4005). ``state.show_quiver`` is the box's own flag - the
    LEGACY page's ``state.show_volume_quiver`` is a different key and is not
    read here.
    """
    cache: dict = {"mesh": None, "built": False}

    def show() -> None:
        """Put the volume arrows on the plotter, or take them off. NEVER raises."""
        try:
            if not bool(state.show_quiver):
                # Idempotent by construction: an unticked box twice pops None the
                # second time and touches no actor.
                entry = handles.pop("volume_quiver", None)
                if isinstance(entry, dict) and entry.get("actor") is not None:
                    plotter.remove_actor(entry["actor"])
                return
            if not cache["built"]:
                cache["mesh"] = _volume_quiver_mesh(info)
                cache["built"] = True
            mesh = cache["mesh"]
            if mesh is None:
                # The builder has already named its own reason (no volume, or
                # nothing above the relative floor); this line is the one that
                # says the CHECKBOX drew nothing, which is what a reader needs.
                print(
                    "[poc_app] volume arrows skipped: the dump has no volume "
                    "arrow field to draw (see the 3D vectors line above)",
                    file=sys.stderr,
                )
                return
            # One actor, replaced in place: pyvista's add_mesh replaces the actor
            # of the same name, so a second redraw cannot stack arrow fields.
            previous = handles.get("volume_quiver")
            if isinstance(previous, dict) and previous.get("actor") is not None:
                plotter.remove_actor(previous["actor"])
            # BLACK, not white: this plotter's background is white
            # (create_plotter calls set_background("white")), so white geometry
            # cannot be seen on it. Same styling as the legacy page (:4382),
            # under the name this page's handles key is.
            actor = plotter.add_mesh(
                mesh,
                color="black",
                lighting=False,
                show_scalar_bar=False,
                name="volume_quiver",
            )
            handles["volume_quiver"] = {"actor": actor}
        except Exception as exc:  # noqa: BLE001 - the arrows are not the page
            print(f"[poc_app] volume arrows skipped: {exc}", file=sys.stderr)

    return show


SOLVE_DEFAULT_XCUT_MM = 20.4


class SolveJob:
    """ONE solve, in a child process, driven from a worker thread.

    No trame in here and no plotting in here: the process boundary is the whole
    interface, so this class can be driven to completion by a test in a second.

    ``cwd`` defaults to the solver's OWN directory because the solver imports its
    siblings - started anywhere else it cannot even be imported.
    """

    #: How much of the combined output is kept. The child can print a study's
    #: worth of numbers; the operator needs the last screen of it, not all of it.
    LOG_TAIL_CHARS = 4000
    LOG_TAIL_LINES = 400

    def __init__(self, argv, cwd=None):
        self.argv = list(argv)
        self.cwd = str(SOLVER_SCRIPT.parent if cwd is None else cwd)
        self.status = "idle"
        self.returncode = None
        self._tail: deque = deque(maxlen=self.LOG_TAIL_LINES)
        self._proc = None
        self._lock = threading.Lock()

    @property
    def log(self) -> str:
        """The TAIL of the combined stdout+stderr, newest last."""
        return "".join(self._tail)[-self.LOG_TAIL_CHARS:]

    def _finish(self, returncode) -> None:
        self.returncode = returncode
        self.status = "ok" if returncode == 0 else "failed"

    def _drain(self) -> None:
        """Read whatever is left. Safe only once the child has exited."""
        stream = getattr(self._proc, "stdout", None)
        if stream is None:
            return
        for line in stream:
            self._tail.append(line)

    def start(self) -> "SolveJob":
        """Spawn the child. REFUSES to start a second one."""
        with self._lock:
            if self.status == "running":
                raise RuntimeError(
                    "SolveJob.start(): a solve is already running - one at a "
                    "time, because two would write the same LIVE_DUMP"
                )
            self._tail.clear()
            self.returncode = None
            self._proc = subprocess.Popen(
                self.argv,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self.status = "running"
        return self

    def run(self) -> str:
        """start(), then block until the child exits. THE WORKER THREAD'S CALL."""
        self.start()
        self._drain()
        self._finish(self._proc.wait())
        return self.status

    def poll(self) -> str:
        """Non-blocking: finalise here once the child has exited on its own.

        Returns the status and never raises, so a timer can call it forever.
        """
        if self.status != "running":
            return self.status
        try:
            code = self._proc.poll()
        except Exception:  # noqa: BLE001 - a dead handle is a failed solve
            code = -1
        if code is None:
            return self.status
        self._drain()
        self._finish(code)
        return self.status


#: The keys the draw path reads off the live page, and the ONLY ones apply_page
#: overwrites. Everything else in the holder is somebody else's business.
PAGE_KEYS = ("path", "info", "planes", "multifreq", "structure_id", "record")


def apply_page(holder: dict, page: dict) -> dict:
    """Make a freshly loaded page the LIVE one, in place.

    The single way a page becomes live: boot fills the holder, a finished solve
    fills it again through this function, and every draw path reads the holder.
    Nothing here clears unrelated keys - the holder also carries the app's own
    bookkeeping, and a reload must not drop it.

    Returns what changed, in terms of the page's identity: the old path, the new
    path and the keys that were actually replaced.
    """
    if not isinstance(holder, dict):
        raise TypeError(
            f"apply_page: holder must be a dict, not {type(holder).__name__}"
        )
    old_path = holder.get("path")
    changed: list[str] = []
    for key in PAGE_KEYS:
        if key not in page:
            continue
        if holder.get(key) is not page[key]:
            changed.append(key)
        holder[key] = page[key]
    if "is_vis" in page:
        holder["is_vis"] = page["is_vis"]
    return {
        "old_path": old_path,
        "new_path": holder.get("path"),
        "changed": changed,
    }


def VRow(*, style: str = "", **kw):
    """A flex-row ``html.div``; trame is imported lazily, never at module load.

    ``style`` is appended AFTER the row base style, so a caller can adjust
    flex/size hints without dropping ``display: flex; flex-direction: row``.
    """
    try:
        from trame.widgets import html as html_widgets
    except Exception as exc:  # noqa: BLE001 - trame is optional at import time
        raise RuntimeError(
            f"VRow needs trame.widgets.html, which is unavailable: {exc}"
        ) from exc
    base = "display: flex; flex-direction: row"
    return html_widgets.Div(style=f"{base}; {style}" if style else base, **kw)


def VCol(*, style: str = "", **kw):
    """A flex-column ``html.div``; trame is imported lazily, never at module load.

    ``style`` is appended AFTER the column base style, so a caller can adjust
    flex/size hints without dropping ``display: flex; flex-direction: column``.
    """
    try:
        from trame.widgets import html as html_widgets
    except Exception as exc:  # noqa: BLE001 - trame is optional at import time
        raise RuntimeError(
            f"VCol needs trame.widgets.html, which is unavailable: {exc}"
        ) from exc
    base = "display: flex; flex-direction: column"
    return html_widgets.Div(style=f"{base}; {style}" if style else base, **kw)


def build_far_field_panel(surface_dump) -> dict:
    """Integrate the ``--surface-dump`` archive and pick the ONE number.

    MODULE-LEVEL, not a closure, for exactly the reason
    ``build_frequency_chart`` (above) is: so a test can call it, and check what
    the panel publishes, without a browser, a port or a trame widget.

    WHY this panel has its own input: a far-field pattern needs the equivalent
    currents ``J_s`` and ``M_s`` on a CLOSED surface, and the animation's plane
    dump carries none - it is one sheet of |Ez| inside the volume. So the tab
    reads a second artefact, named by ``--surface-dump``, and never touches
    ``page``. That artefact also never goes through ``load_any_dump``: that
    loader refuses a Huygens archive BY NAME (see its docstring), deliberately,
    because nothing else in this viewer draws surface currents. Keeping the two
    inputs apart is what lets both statements stay true.

    The no-archive answer is returned FIRST, before any import and before the
    disk is read: most runs give no archive, and a page that paid a matplotlib
    import for a tab it cannot fill would be slower for nothing.

    The builder is imported HERE, lazily, exactly the way ``_mode2d`` imports
    its solver - this module's CLI path (``--help``, ``--list-keys``) is
    documented as numpy-only and stays that way. The builder itself is
    contracted never to raise, so what this needs to survive is only the
    import; the call is wrapped anyway, so the panel keeps that promise for the
    page even if the contract is ever broken.

    Note the S-parameters helper reaches the same end a DIFFERENT way: it is a
    module-level sibling that does its own ``import matplotlib`` inside itself,
    so there is no import of it to guard.
    """
    if not surface_dump:
        return {
            "path": None,
            "image": None,
            "rows": [],
            "reason": "no --surface-dump archive was given",
            "caption": (
                "no surface dump supplied: pass --surface-dump PATH to "
                "plot a far-field pattern"
            ),
            "number": "",
        }
    builder = None
    try:
        # Inside the function, on purpose: the numpy-only entry points
        # (``--help``, ``--list-keys``) must never need matplotlib, which is
        # the same rule ``_mode2d`` follows for its solver. That is also why
        # the import is guarded - a missing optional dependency costs this one
        # panel and one stderr line instead of the whole page.
        from emfit.antenna import build_far_field_report as builder
    except Exception as exc:  # noqa: BLE001 - the panel is an extra
        print(f"[poc_app] far-field builder unavailable: {exc}", file=sys.stderr)
    if builder is None:
        return {
            "path": str(surface_dump),
            "image": None,
            "rows": [],
            "reason": "the far-field report builder is unavailable",
            "caption": (
                "the far-field report builder could not be imported: "
                "emfit.antenna is not usable here"
            ),
            "number": "",
        }
    try:
        report = dict(builder(surface_dump))
    except Exception as exc:  # noqa: BLE001 - the panel is not the page
        # The builder is contracted never to raise. This keeps that promise
        # TRUE for the page instead of trusting it. The reason is put through
        # the same one-line/ASCII discipline ``emfit.antenna`` applies to its
        # own reasons, inlined because this module has no such helper.
        text = f"{type(exc).__name__}: {exc}"
        detail = " ".join(
            text.encode("ascii", "replace").decode("ascii").split()
        )
        reason = detail if len(detail) <= 180 else detail[:177].rstrip() + "..."
        return {
            "path": str(surface_dump),
            "image": None,
            "rows": [],
            "reason": reason,
            "caption": f"far-field report unavailable: {reason}",
            "number": "",
        }
    peak = report.get("peak_d_dbi")
    freq = report.get("freq")
    # One sentence, and it names BOTH numbers: a directivity without the
    # frequency it was taken at is not a measurement a reader can use, and
    # the archive may hold several frequencies (freq_index picks one).
    number = ""
    if peak is not None and freq is not None:
        number = f"peak directivity {peak:.2f} dBi at {freq / 1e6:.1f} MHz"
    report["path"] = str(surface_dump)
    report["number"] = number
    return report


def run_web_vis(
    info: dict,
    host: str,
    port: int,
    fps: int = DEFAULT_FPS,
    structure=None,
    structures=None,
    *,
    surface_dump=None, loaded_page=None,
) -> int:
    """Serve the animation page for an ``emfit.vis/2`` dump.

    The page is ONE plotter with three flat sheets in it; a frame only swaps the
    scalar array inside those sheets, so nothing is rebuilt between frames and no
    camera state is lost. The colour limits are fixed once at add_mesh time from
    the dump's single stored ceiling, which is what stops a frame from painting
    its own maximum as brightly as the first one.

    Only one plane family is animated at a time, because the two families do not
    share a clock (see _vis_frame_time_ns): advancing both from one slider
    would put two different instants under one frame number.

    The two x-cut planes are FIXED at the x positions the dump records, because
    those two y-z slices are all it carries and moving them would need the whole
    3-D field dumped (~2 GB) rather than two sheets.

    Every widget layer is probed and degrades on its own: no VSlider costs the
    slider (the frame label still counts), no html widgets costs the readout
    rows, and a missing pyvista.trame.ui is the only hard stop because without it
    there is no view at all.

    ``surface_dump`` is the optional Huygens surface archive the Far Field tab
    integrates. It is KEYWORD-ONLY and separate from ``info`` because it is a
    different artefact from the one being animated: the page draws a plane
    dump, and a far-field pattern can only come from currents on a closed
    surface. It is None on every run that gives no archive, which is the
    ordinary case - the tab then says so instead of showing an empty picture.
    """
    # Deliberately BEFORE any import of pyvista: on a machine without the web
    # stack the missing package must be a named message and exit 1, exactly as
    # run_web does, not a ModuleNotFoundError traceback.
    structures = load_structures() if structures is None else structures
    if structure is None:
        structure = _structure_by_id(DEFAULT_STRUCTURE, structures)
    structure_label = _structure_label(structure)

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

    import asyncio

    import pyvista as pv

    probed = _probe_trame_ui()
    if probed is None:
        return 1
    (
        ui_module,
        widgets_module,
        SinglePageLayout,
        trame_version,
        ui_path,
        variant,
    ) = probed
    print(f"[poc_app] trame {trame_version} - ui modules: {ui_path}")

    # Resolve the widget classes instead of hardcoding them, so a variant that
    # lacks one degrades to a label instead of a traceback.
    widgets = {}
    missing_widgets = []
    for name in ("VSpacer", "VSlider", "VLabel", "VContainer", "VBtn"):
        try:
            widgets[name] = getattr(widgets_module, name)
        except Exception:
            missing_widgets.append(name)
    for name in missing_widgets:
        print(f"[poc_app] widget {name} missing from {variant}", file=sys.stderr)

    html_div = None
    try:
        from trame.widgets import html as html_widgets

        html_div = getattr(html_widgets, "Div", None)
    except Exception as exc:  # noqa: BLE001 - optional layer
        print(
            f"[poc_app] trame.widgets.html unavailable ({exc}): no readout rows",
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

    from trame.app import get_server

    # THE LIVE PAGE, in ONE mutable dict. Every draw path reads `page["info"]`
    # rather than the `info` this function was called with, because a finished
    # solve REPLACES the page (apply_page) while the server keeps running. A
    # closure that captured `info` directly would keep drawing the dump that is
    # no longer on disk under the name the operator just re-solved for.
    page = dict(loaded_page) if loaded_page is not None else {
        "path": info.get("path"),
        "info": info,
        "planes": None,
        "multifreq": None,
        "record": None,
        "structure_id": info.get("structure_id"),
        "is_vis": True,
    }
    page["info"] = info

    fps = max(1, int(fps))
    # THE TIMELINE FENCE. A page that CLAIMS the animation - "format" in
    # VIS_FORMATS, which is what load_vis writes - must carry its timeline, so
    # the two frame counts are read with [] and a missing one still raises
    # KeyError("nt"): a crash naming the key is the report that the writer and
    # this reader disagree. A page that claims NOTHING (a bare field dump, which
    # records no frame axis) has no timeline at all: both counts are None, which
    # is "no timeline", never "0 frames".
    claims_timeline = _is_vis(info)
    if claims_timeline:
        nt = int(info["nt"])
        nt_x = int(info["nt_x"])
    else:
        nt = None
        nt_x = None
    cell_mm = _cell_mm(info)
    # The colour limits are the dump's own recorded range, and a page with no
    # timeline records none: 0 .. 1 is the placeholder the [EMPTY DUMP] line
    # already names, and no sheet is drawn to paint with it anyway.
    color_range = info.get("color_range")
    if color_range is None:
        vmin, vmax = 0.0, 1.0
    else:
        vmin, vmax = color_range
    # The domain's full y width, computed once for the whole page: the x-cut
    # readout quotes it so the transverse section can be read against it.
    y_span_mm = float(int(info["ny"])) * cell_mm

    plotter = pv.Plotter(off_screen=True)
    plotter.set_background("white")
    try:
        plotter.add_axes(xlabel="x [mm]", ylabel="y [mm]", zlabel="z [mm]")
    except Exception as exc:  # noqa: BLE001 - decoration only
        print(f"[poc_app] axes not drawn: {exc}", file=sys.stderr)

    # The bar's title is also the KEY pyvista stores the bar under, so the one
    # string is used both to create it here and to swap it per family in _show:
    # two different strings would be two bars.
    scalar_bar_title = "|Ez| [V/m]"

    # Three sheets, added ONCE. clim is the dump's single ceiling for every one
    # of them, so no later frame has a scale of its own to renormalise with.
    # smooth_shading=False plus the cell edges are the same statement twice: this
    # is a FIELD on a grid, so the grid stays visible and a cell's colour is not
    # smeared into its neighbour's.
    sheets: dict = {}
    for key, family in (
        ("ez_ycut", "ycut"),
        ("ez_xcut_near", "xcut"),
        ("ez_xcut_far", "xcut"),
    ):
        try:
            grid = _vis_grid(info, key, 0)
            actor = plotter.add_mesh(
                grid,
                scalars="ez_abs",
                cmap="turbo",
                clim=(vmin, vmax),
                smooth_shading=False,
                show_edges=VIS_SHOW_EDGES,
                show_scalar_bar=(family == "ycut"),
                scalar_bar_args={"title": scalar_bar_title},
            )
        except Exception as exc:  # noqa: BLE001 - one sheet is not the picture
            print(f"[poc_app] plane {key} not drawn: {exc}", file=sys.stderr)
            continue
        sheets[key] = {"grid": grid, "actor": actor, "family": family}
    if not sheets and claims_timeline:
        # A page that CLAIMS the animation with no plane drawn has no picture to
        # serve, so it has always exited here. A page with no timeline is the
        # SHELL: the per-plane lines above are the whole report, and the page
        # boots with the player absent instead of exiting over a missing one.
        print(
            "[poc_app] no plane could be drawn - check the pyvista/VTK build",
            file=sys.stderr,
        )
        return 1

    # The substrate box, the strip and the load marker are 3-D objects wrapped
    # around a plane that the camera now looks at SQUARE ON, so they are recorded
    # here - with the opacity they were drawn at - for _show() to dim in y-cut and
    # restore in x-cut. Only what _vis_geometry adds is recorded, so a later
    # decoration cannot be mistaken for the structure.
    overlay: list = []
    try:
        _already_drawn = set(plotter.actors)
        _vis_geometry(plotter, info)
        for _name, _actor in plotter.actors.items():
            if _name in _already_drawn:
                continue
            # A 2-D labels actor has no prop, and no opacity to dim: skip it
            # rather than let it abort the recording of everything after it.
            _prop = getattr(_actor, "prop", None)
            if _prop is None:
                continue
            overlay.append((_actor, float(_prop.opacity)))
    except Exception as exc:  # noqa: BLE001 - the overlay is decoration only
        print(
            f"[poc_app] overlay bookkeeping skipped: {exc}", file=sys.stderr
        )

    # No up-front camera view any more: _show() frames the plane it is actually
    # about to draw (and re-frames when the plane family changes). Parallel
    # projection is what makes that framing a 2-D picture instead of a
    # perspective one, so it is set once, here, and never touched again.
    try:
        plotter.camera.parallel_projection = True
    except Exception as exc:  # noqa: BLE001
        print(f"[poc_app] parallel projection skipped: {exc}", file=sys.stderr)

    try:
        server = get_server(
            client_type="vue3" if variant == "vuetify3" else "vue2"
        )
    except TypeError:
        # Older trame builds do not accept client_type.
        server = get_server()

    state, ctrl = server.state, server.controller
    # The dump animation is what a freshly booted page shows, so that is the
    # title it starts with. It is REPLACED, not assumed, the moment the view
    # stops showing the dump - see _set_picture_title() below.
    state.trame__title = _animation_title_text(structure_label)
    state.mode = "ycut"
    state.playing = False
    state.frame = 0
    # No timeline: the scrubber's range is ABSENT (None), never 0 frames.
    state.frame_max = _frame_span_max(nt, nt_x, "ycut")
    state.play_label = "play"

    # Keyboard shortcuts (Space = play/pause, arrows = step). The browser side is
    # server/web_assets/keyboard.js; it calls the very same trigger names the
    # buttons are bound to, so there is one implementation of each action.
    #
    # The serve KEY is deliberately relative ("__trame_kbd") while the DIRECTORY
    # is absolute: trame publishes the route and the page fetches it relative to
    # its own base href, so a relative key survives being served under a URL
    # prefix, while aiohttp resolves the directory against the process cwd, which
    # a relative path would get wrong the moment the server is started from
    # anywhere but the repo root.
    #
    # Wrapped because shortcuts are a convenience: a trame build that does not
    # take this module dict must still serve the page.
    try:
        server.enable_module(
            {
                "serve": {
                    "__trame_kbd": str(Path(__file__).resolve().parent / "web_assets")
                },
                "scripts": ["__trame_kbd/keyboard.js"],
            }
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[poc_app] keyboard shortcuts unavailable: {exc}", file=sys.stderr)

    # The S-parameters pane: the TAB owns its visibility, so there is no style
    # string, no label and no open flag here. What a headless proof can read is
    # the PANEL - built at layout time and cached in ``handles["s_params"]`` -
    # plus the payload strings pushed from it, which its tab shows as-is.
    state.s_params_caption = ""
    state.s_params_number = ""
    state.s_params_image = ""
    state.s_params_image_style = "display: none;"
    state.s_params_rows = ""
    state.s_params_rows_style = "display: none;"

    # The Far Field pane, on the same contract as the S-parameters one: the TAB
    # owns visibility, so no label, no open flag and no wrapper style - these
    # are only the payload strings its tab binds, and they exist at layout time
    # because ``_load_far_field_panel`` pushes them before the tabs are built.
    # Both styles start hidden for the reason they do one panel above: a tab
    # that is never selected must not leave a broken-image box or an empty
    # <pre> taking up room in the column, and the loader turns exactly one of
    # them on.
    state.far_field_caption = ""
    state.far_field_number = ""
    state.far_field_image = ""
    state.far_field_image_style = "display: none;"
    state.far_field_rows = ""
    state.far_field_rows_style = "display: none;"

    # The Mode panel: caption and numbers only - one press solves the 2D
    # cross-section for the page on screen and reports it on these two strings.
    # They are built by the SAME module helpers a later press uses, so the boot
    # text, the refreshed text after a solve replaces the page and the text a
    # press produces are one rule, assertable headlessly.
    state.mode_view_label = _mode_button_label(None)
    state.mode_view_caption = _mode_caption_text(None)
    # The Mode PICKER: which of the solve's own candidates the picture shows.
    # Empty until a press fills `mode_choice_items` from that press's result, so
    # the select sits there naming nothing rather than the picker inventing a
    # candidate before the pencil has run.
    state.mode_choice = 0
    state.mode_choice_items = []
    # The arrow-field toggle. OFF at boot, and off is exactly the view this
    # panel had before the overlay existed: nothing is drawn, nothing is
    # cleared, and every other control keeps the meaning it always had.
    state.show_quiver = False
    # The two marker planes. BOTH at boot: the red load plane has been in the
    # scene since the marker layer existed, and the purple S11 port plane is
    # the position the corner label already named. ON is therefore the picture
    # every page drew before these boxes existed, so a page that never touches
    # a box is unchanged.
    state.show_load_plane = True
    state.show_port_plane = True

    # The Confidence & Accuracy pane: TEXT, prose rather than a picture. Its tab
    # owns its visibility, so (like the S-parameters pane) there is no style
    # string, no label and no open flag - only the caption and the rows a
    # headless proof can read back off the state and off the cached panel.
    state.confidence_caption = ""
    state.confidence_rows = ""

    # Provenance, from the dump's own record (see _structure_readout_text).
    state.structure_readout = _structure_readout_text(info)

    state.velocity_label = _velocity_label(info)
    state.velocity_note = (
        info.get("velocity_note") or "velocity note: not recorded"
    )
    state.scale_label = _scale_label(info)

    # WHICH FILE, and which kind of page: the provenance line every other label
    # here leaves out. Rebuilt from the dump now on screen, never carried over
    # from boot, for the same reason as the two lines above.
    state.page_source_text = _page_source_text(info, nt)

    # The plotter_ui handle only exists once the layout is built, so the frame
    # handler reaches it through this dict instead of closing over it.
    handles: dict = {}

    # The page's own context: the loaded dump - either kind, since one shell now
    # opens both - and the registry the layout builders reach their callables
    # through. Nothing else is mirrored here yet, and the two modes are kept
    # apart on purpose: what the shell switches is `state.mode` ("ycut"/"xcut"),
    # while `state.view_mode` is the port / volume toggle `_init_cut_state`
    # writes once and nothing on this page ever varies, so only the legacy
    # page's toggle can make it read "port". `PageContext` has a `view_mode` of
    # its own - defaulted to the same value, read by nothing - so do not mistake
    # it for a second copy of an answer.
    ctx = um3k_context.PageContext(
        dump=um3k_context.LoadedDump.from_any_dump(page),
    )

    # --- the Y / Z cut sheets: STATE and TRIGGERS, no widgets yet -------------
    #
    # WHY GATED, and why on this particular flag: every helper below reads
    # ``info[PLANE_KEY]`` - the legacy dump's (station, y, z) stack
    # (_plane_layout :3166, _cut_layout :3369) - which an animation dump does not
    # carry at all, so calling any of them on a vis page is KeyError('plane_ez').
    # ``ctx.available.plane_stack`` is the page's own answer to "did this page
    # capture more than one x-plane" (um3k_context.py:130-145), computed once
    # from the data at boot; this does not re-read the format to guess it.
    #
    # WHY the widgets are NOT here: the two VSliders belong to the layout, built
    # far below (:9461). What is installed here is what both the layout and the
    # browser reach - the state the sliders will bind to, the two redraw pieces
    # ``_redraw_scene`` insists on, and the two triggers those sliders will fire -
    # so the cut machinery is complete and drivable before any widget exists.
    if ctx.available.plane_stack:
        plane = info[PLANE_KEY]
        # The same three reads run_web makes on its own stack (:4232-4235), so a
        # transposed shape would break in one place, not in two different ones.
        n_st = plane.shape[0]
        n_j = plane.shape[1]
        n_k = plane.shape[2]

        # The study record beside the dump is OPTIONAL: ``load_record`` answers
        # None for a missing or unreadable one and never raises (poc_app.py:907),
        # so the only failing path here is a hand-built info with no "path" key at
        # all. Both routes end in the same 14-key layout, whose ``src_*`` entries
        # then say FALLBACK: a plane position is never invented in silence.
        try:
            planes = _plane_layout(info, load_record(info["path"]))
        except Exception:  # noqa: BLE001 - a record is optional, the page is not
            planes = _plane_layout(info, None)

        # The SAME rule run_web applies (:4273), available here for the same
        # reason: this page resolves its widgets from its own probe loop over
        # ("VSpacer", "VSlider", "VLabel", "VContainer", "VBtn") at :7283, so
        # ``missing_widgets`` and ``widgets["VBtn"]`` mean what they mean there.
        # Without VBtn the label says so instead of offering a toggle.
        toggle_available = (not missing_widgets) and ("VBtn" in widgets)
        _init_cut_state(state, info, n_j, n_k, planes, toggle_available)

        # The station this page never had. ``_redraw_scene`` reads it for the
        # corner label (:3996) and run_web keeps it in state (:4249); a page
        # without it soft-fails EVERY redraw, which is a silent picture rather
        # than a loud failure. It starts on the middle captured plane for the
        # reason the cut starts on the middle sample of each axis (:3975).
        state.station = n_st // 2
        # The same sentence the corner label used to carry, as a value the SHELL
        # renders (see _emit_station_readout): built by the one helper the label
        # was built by, at the one station this page draws, so the line beside
        # the sliders cannot disagree with the picture. Published behind the same
        # gate, because a page with no stack has no station to name.
        state.station_readout = _station_text(
            int(state.station), planes["cell_mm"], n_st, planes["stations_mm"]
        )

        # The 3-D arrow field the "Show Vector Field" box owns on this page. The
        # seam keeps its zero-argument signature and its position in
        # _redraw_scene's arguments: that call runs AFTER _draw_scene and BEFORE
        # its render (:4005), and _draw_scene starts with plotter.clear(), so an
        # actor added any earlier is gone by the time the scene returns - the
        # arrows have to be re-added on every redraw, which is why the cache
        # lives inside the callback (poc_app.py:_volume_quiver_callback).
        _show_volume_quiver = _volume_quiver_callback(plotter, info, state, handles)

        def _redraw() -> None:
            """Rebuild the scene in the one plotter. Failure leaves the old picture."""
            # station_label=False: the station sentence is shell text on this
            # page (see the readout), not a corner annotation whose font grows
            # with the render window. Legacy pages keep the default (:3988).
            _redraw_scene(
                plotter,
                info,
                planes,
                state,
                _show_volume_quiver,
                station_label=False,
            )

        # Published so the BOOT can draw: on this page there are no ez_* sheets
        # to switch between, so _show below finds nothing to show and the
        # picture the browser loads would be blank. The boot draw and the two
        # sliders call this SAME function, so the first picture a user sees is
        # the picture the sliders move (:8341).
        handles["cut_redraw"] = _redraw

        # What the layout needs to emit the two sliders: only a page that
        # reached this block has a sample count to bound them with, so the
        # pair goes on `ctx` here rather than as a new argument to the
        # builder - `build_center_panel(ctx)` keeps taking only `ctx`
        # (server/um3k_panels.py:27).
        ctx.register_handle("cut_shape", (n_j, n_k))

        # Registered BEFORE the layout is built, so ctrl.cut_y / ctrl.cut_z exist
        # by the time a slider binds to them. The arguments are run_web's own
        # (:4412 and :4428) in that order: the clamp, both labels and the redraw
        # are the shipped functions, not a second copy of them.
        @ctrl.set("cut_y")
        def _on_cut_y(*args, **_kwargs) -> None:
            value = args[0] if args else _kwargs.get("cut_y", state.cut_y)
            _on_cut_change(
                "y",
                value,
                state,
                n_j,
                n_k,
                info,
                planes,
                toggle_available,
                _redraw,
                handles,
            )

        @ctrl.set("cut_z")
        def _on_cut_z(*args, **_kwargs) -> None:
            value = args[0] if args else _kwargs.get("cut_z", state.cut_z)
            _on_cut_change(
                "z",
                value,
                state,
                n_j,
                n_k,
                info,
                planes,
                toggle_available,
                _redraw,
                handles,
            )

    # A dump that captured exactly ONE x-plane is not a stack (um3k_context
    # answers plane_stack False, port_planes True), so there is nothing to cut
    # and no slider exists that could move a cut - but the page still owns a
    # picture. Without this branch it drew NOTHING: the boot and the vector
    # toggle both look for ``cut_redraw``, neither found it, and the browser
    # showed an empty view with no error. So the same draw path as the stacked
    # page, minus its sliders - ``cut_redraw`` is this page's DRAW HANDLE, not a
    # promise that a cut exists.
    elif ctx.available.port_planes:
        plane = info[PLANE_KEY]
        # The two transverse axes of the one captured plane: the shared redraw
        # reads a sample for each cut sheet even though no slider here moves
        # them, and the middle is where the stacked page opens.
        n_j = plane.shape[1]
        n_k = plane.shape[2]

        # Built exactly as the stacked branch builds it: the study record beside
        # the dump is OPTIONAL and load_record answers None without raising, so
        # the only failing path is an info with no "path" - and a plane position
        # is never invented in silence, the layout says FALLBACK.
        try:
            planes = _plane_layout(info, load_record(info["path"]))
        except Exception:  # noqa: BLE001 - a record is optional, the page is not
            planes = _plane_layout(info, None)

        cut_layout = _cut_layout(
            info, n_j // 2, n_k // 2, planes.get("stations_mm")
        )
        # EVERY field the shared redraw reads, because it catches its own
        # exceptions (:4026): a missing one is not a loud failure, it is the
        # silently blank picture this branch exists to remove. Station 0 is the
        # only captured station, so there is nothing to choose there.
        state.station = 0
        state.cut_y = cut_layout["j"]
        state.cut_z = cut_layout["k"]
        state.view_mode = "volume"

        _show_volume_quiver = _volume_quiver_callback(plotter, info, state, handles)

        def _redraw() -> None:
            """Rebuild the scene in the one plotter. Failure leaves the old picture."""
            _redraw_scene(
                plotter,
                info,
                planes,
                state,
                _show_volume_quiver,
                station_label=False,
            )

        # The boot draw and the "Show Vector Field" toggle both reach the draw
        # through this NAME, so publishing it here is the whole of the fix. No
        # sliders are registered (there is nothing they could move) and no
        # station_readout is published (um3k_panels emits that line only inside
        # its plane_stack row, so the value would be rendered by nothing).
        handles["cut_redraw"] = _redraw

    def _set_picture_title(text: str) -> None:
        """Publish the page title for whatever the 3D view is showing. NEVER raises.

        ONE string, written to the two places a page title lives: the browser
        title (``state.trame__title``) and the header the layout builds below.
        A title is a claim about the picture under it, and there are exactly
        two pictures here - the |Ez| dump animation and a solved mode
        cross-section's |E_t| - so this function is the only writer of either.
        The header setter does not exist until the layout is built
        (``_show(0, "ycut")`` runs first), so it is reached through ``handles``
        and its absence means "no layout yet", not an error.
        """
        try:
            if state.trame__title == text:
                return  # unchanged: a per-frame caller must not churn state
        except Exception:  # noqa: BLE001 - an unreadable title is not a failure
            pass
        try:
            state.trame__title = text
        except Exception as exc:  # noqa: BLE001 - a title is never the page
            print(f"[poc_app] window title not set: {exc}", file=sys.stderr)
        setter = handles.get("title_setter")
        if setter is None:
            return
        try:
            setter(text)
        except Exception as exc:  # noqa: BLE001 - decoration only
            print(f"[poc_app] header title not set: {exc}", file=sys.stderr)

    def _sync_picture_title() -> None:
        """Point the title at the field the 3D view is ACTUALLY showing.

        Same rule _show applies to the mode picture's visibility - its own
        family, and only the dump it was solved from - so a picture that
        exists but is hidden (a family switch, a solve that swapped the page)
        leaves the |Ez| title standing. Cheap enough to call on every draw:
        _set_picture_title() writes nothing when the string has not changed.
        """
        entry = handles.get("mode_actor")
        on_screen = (
            entry is not None
            and entry.get("family") == state.mode
            and entry.get("page_path") == page.get("path")
        )
        if on_screen:
            _set_picture_title(_mode_title_text(structure_label, entry.get("index")))
        else:
            _set_picture_title(_animation_title_text(structure_label))

    def _swap_scalar_bar(mode: str) -> None:
        """Leave exactly ONE bar standing, for the family now on screen.

        The y-cut sheet makes its bar at add_mesh time and the x-cut sheets make
        none, so a plane switch would otherwise keep the y-cut's bar over a field
        it does not describe. The replacement is built from the ACTIVE sheet's
        own mapper: every sheet was added with the same fixed (vmin, vmax), so
        the numbers do not move, only the actor the bar reads from does. A bar
        is decoration, so every step here degrades to a stderr line.
        """
        try:
            if scalar_bar_title in plotter.scalar_bars:
                plotter.remove_scalar_bar(
                    title=scalar_bar_title, render=False
                )
        except Exception as exc:  # noqa: BLE001 - decoration only
            print(
                f"[poc_app] stale scalar bar kept: {exc}", file=sys.stderr
            )
        try:
            entry = next(
                (
                    item
                    for item in sheets.values()
                    if item["family"] == mode
                ),
                None,
            )
            if entry is None:
                return
            plotter.add_scalar_bar(
                title=scalar_bar_title, mapper=entry["actor"].mapper
            )
        except Exception as exc:  # noqa: BLE001 - decoration only
            print(
                f"[poc_app] scalar bar for {mode} not drawn: {exc}",
                file=sys.stderr,
            )

    def _clear_mode_quiver() -> None:
        """Drop the Mode ARROW overlay. Own handle, own actor, own removal.

        The arrow field is a SECOND actor standing on the same plane as the
        picture, so every path that drops the picture has to drop this with it:
        arrows left standing over an empty view would be a field with no mode
        under it. Best-effort, for the picture's own reason - once the handle is
        gone the actor can only come back from a fresh draw, so a stuck overlay
        is invisible rather than wrong.
        """
        entry = handles.pop("mode_quiver", None)
        if entry is not None:
            try:
                plotter.remove_actor(entry["actor"], render=False)
            except Exception as exc:  # noqa: BLE001 - an orphan is not a failure
                print(
                    f"[poc_app] stale mode vector field kept: {exc}", file=sys.stderr
                )

    def _clear_mode_picture() -> None:
        """Drop the Mode picture. ONE actor, OUTSIDE ``sheets``, own handle.

        It is a still cross-section, not an animation frame: keeping it out of
        ``sheets`` is what stops _show from swapping its scalars or hiding it as
        one of the three families. Removal is best-effort - once the handle is
        gone the actor can never be made visible again except by a fresh solve,
        so a stuck picture is invisible rather than wrong.
        """
        entry = handles.pop("mode_actor", None)
        if entry is not None:
            try:
                plotter.remove_actor(entry["actor"], render=False)
            except Exception as exc:  # noqa: BLE001 - an orphan is not a failure
                print(f"[poc_app] stale mode picture kept: {exc}", file=sys.stderr)
        # The arrow overlay annotates the picture, so it goes wherever the
        # picture goes - dropped HERE, at the one place a picture is dropped, so
        # no path can leave arrows standing over a cross-section they were not
        # sampled on.
        _clear_mode_quiver()
        # Nothing mode-shaped is on this view from here on, so the page title
        # goes back to the animation's. The sync runs AFTER the pop, because
        # that is what makes it observe a view with no picture left on it -
        # run before it, it would read the handle it is about to drop and
        # keep the |E_t| title standing over the empty view. It is also
        # unconditional: a call that finds nothing to pop is still a call that
        # leaves no picture on the view, so it still re-points the title. Said
        # HERE, at the one place a picture is dropped, so every path that
        # removes one - a fresh draw, a refusal, a finished solve replacing
        # the page - resets it together.
        _sync_picture_title()

    def _draw_mode_picture(result, index=None) -> None:
        """Draw a solve's 48 x 48 |E| on the cross-section plane. NEVER raises.

        Placed in the y-z plane of the x-cut family (that is the plane the mode
        describes), one cell toward the viewer from the sheet NEAREST the eye.
        WHICH sheet that is comes off the live camera, not from a constant.

        The installed pyvista settles the direction: ``plotting/helpers.py::
        view_vectors('yz')`` is ``[1, 0, 0]`` and ``renderer.view_vector`` -
        which every ``view_*`` helper goes through - sets ``camera_position =
        (vector + center, center, viewup)``, so ``view_yz`` - the framing
        ``_show`` gives this family - puts the eye on +x. Measured, not assumed
        (pyvista 0.49.2, headless ``Plotter``, ``render()`` stubbed): a fresh
        plotter sits at ``position = (1, 1, 1)``, ``focal_point = (0, 0, 0)``;
        ``view_yz()`` leaves ``position = (1, 0, 0)``, ``focal_point = (0, 0,
        0)``, ``direction = (-1, 0, 0)``; ``view_zy()`` leaves ``position =
        (-1, 0, 0)``, ``direction = (1, 0, 0)``; and an explicit
        ``camera_position = [(5, 0, 0), (0, 0, 0), (0, 0, 1)]`` reads back
        ``position = (5, 0, 0)``, ``focal_point = (0, 0, 0)``, ``direction =
        (-1, 0, 0)``, ``focal_point - position = (-5, 0, 0)``. So ``direction``
        is ``normalize(focal_point - position)``: it points FROM the eye TOWARD
        the scene, and the eye's x is simply ``camera.position[0]``.

        The first version of this placement offset from the SMALLEST recorded x
        - the far sheet's side - which hid the picture behind both sheets. The
        second read ``camera.direction`` and negated it: correct, but only
        because it baked in the convention above. This version compares
        ``camera.position[0]`` with the sheet x values THEMSELVES, so there is
        no convention left to get backwards - the picture is put past whichever
        sheet is nearer that eye, on that eye's side, and a sign slip would have
        to be a slip in a comparison against a measured position. Standing the
        picture between the two opaque sheets, or behind the near one, is the
        bug.

        A y band centred on the grid origin would also hang half of the picture
        outside the framed strip, so it is centred on the band the x-cut sheets
        occupy. A refusal or an unusable grid CLEARS any old picture and draws
        nothing: a stale mode beside an error caption would be a lie about what
        was actually solved.

        ``index`` is the candidate this grid belongs to. It changes nothing in
        the picture - that is whatever ``result`` carries - and only names the
        candidate in the page title, which follows the picture.

        The transverse ARROW field is an OVERLAY on this picture, not part of
        it: it is off by default (``show_quiver``), it is drawn from the same
        result on the same plane, and a build that cannot draw it loses only the
        overlay - the picture above is the panel. Its handle also carries what
        the overlay needs to be redrawn later (the result, the plane and the y
        centre), so toggling it needs no second solve.
        """
        _clear_mode_picture()
        live = page["info"]
        cell_mm_now = _cell_mm(live)
        planes_mm = [
            value
            for value in (
                _finite(live.get("xcut_near_mm")),
                _finite(live.get("xcut_far_mm")),
            )
            if value is not None
        ]
        if not planes_mm:
            station = _finite(live.get("j_cut"))
            if station is not None:
                planes_mm = [station * cell_mm_now]
        if not planes_mm:
            print(
                "[poc_app] mode picture skipped: no cut-plane x recorded",
                file=sys.stderr,
            )
            return
        # The eye's x is read straight off ``plotter.camera.position`` - the
        # quantity VTK stores, measured above: view_yz leaves it at (1, 0, 0),
        # view_zy at (-1, 0, 0), and ``direction`` is nothing but
        # normalize(focal_point - position). Comparing a POSITION with the two
        # sheet x values needs no sign convention at all, which is exactly what
        # the previous ``direction``-and-negate version did need: an eye beyond
        # the larger sheet is on the +x side, one beyond the smaller sheet is on
        # the -x side, and the picture then sits one cell further out than the
        # sheet nearest that eye - never wedged between the sheets, never behind
        # the near one.
        #
        # Degenerate: an unreadable camera, or an eye x that falls BETWEEN the
        # sheets (a framing whose slab straddles the eye, where "in front" has
        # no meaning) falls back to the +x side. That is a documented constant,
        # not a guess - the installed pyvista's ``view_vectors('yz')`` is
        # [1, 0, 0], so ``view_yz``, the framing _show gives this family, puts
        # the eye on +x.
        EYE_SIDE_DEFAULT = 1.0  # view_vectors('yz') == [1, 0, 0] -> view_yz eye on +x
        try:
            eye_x_mm = float(np.asarray(plotter.camera.position, dtype=float)[0])
        except Exception as exc:  # noqa: BLE001 - an unreadable camera is not a failure
            print(f"[poc_app] mode picture eye-side fallback: {exc}", file=sys.stderr)
            eye_x_mm = None
        lo_x_mm = min(planes_mm)
        hi_x_mm = max(planes_mm)
        if eye_x_mm is None or lo_x_mm <= eye_x_mm <= hi_x_mm:
            eye_side = EYE_SIDE_DEFAULT
        else:
            eye_side = 1.0 if eye_x_mm > hi_x_mm else -1.0
        near_x_mm = hi_x_mm if eye_side > 0.0 else lo_x_mm
        x_mm_now = near_x_mm + eye_side * cell_mm_now
        # The x-cut sheets span y in [0, (ny - 1) * cell], so their centre is half
        # of that: the picture keeps its own y half-width (the solve's extent)
        # but rides on the framed band instead of straddling the origin.
        ny_now = _finite(live.get("ny"))
        y_mid_mm = (
            0.0 if ny_now is None or ny_now <= 1.0 else 0.5 * (ny_now - 1.0) * cell_mm_now
        )
        grid = _mode_picture_grid(
            result, x_mm=x_mm_now, y_centre_mm=y_mid_mm
        )
        if grid is None:
            print(
                "[poc_app] mode picture skipped: no drawable grid",
                file=sys.stderr,
            )
            return
        values = np.asarray(grid.point_data["mode_e_abs"], dtype=float)
        ceiling = float(np.nanmax(values)) if values.size else 0.0
        actor = plotter.add_mesh(
            grid,
            scalars="mode_e_abs",
            cmap="turbo",
            # Its OWN limits, from its own array: |E| of the mode is not |Ez| of
            # the dump, so borrowing the sheet's (vmin, vmax) would paint a
            # meaningless colour. No bar either, for the same reason.
            clim=(0.0, ceiling if ceiling > 0.0 else 1.0),
            smooth_shading=False,
            show_edges=False,
            show_scalar_bar=False,
            name="mode_picture",
        )
        handles["mode_actor"] = {
            "actor": actor,
            "grid": grid,
            "page_path": page.get("path"),
            "family": "xcut",
            # What the title must name if this picture is the one on screen.
            "index": index,
            # What the OVERLAY is drawn from, kept beside the picture so the
            # toggle redraws this cross-section instead of re-solving it: the
            # result (or the candidate view) plus the plane it was placed on.
            "result": result,
            "x_mm": x_mm_now,
            "y_centre_mm": y_mid_mm,
        }
        # _show's rule, applied immediately: a press made from the y-cut view
        # leaves the picture hidden instead of letting it appear edge-on.
        actor.visibility = state.mode == "xcut"
        # The overlay follows the same rule and is drawn only when it was asked
        # for: off (the default) leaves this view byte-for-byte what it was.
        if state.show_quiver:
            _draw_mode_quiver(
                result, x_mm=x_mm_now, y_centre_mm=y_mid_mm, index=index
            )
        # The picture just put on the view is |E_t| of the mode, so the title
        # says so. A press that could not draw returned above, having already
        # reset the title through _clear_mode_picture().
        _sync_picture_title()

    def _draw_mode_quiver(
        result, *, x_mm: float, y_centre_mm: float = 0.0, index=None
    ) -> None:
        """Overlay the mode's transverse arrow field on the cross-section. NEVER raises.

        WHY an overlay rather than a second picture: the arrows describe the SAME
        field the |E| picture already paints, from the SAME result - a second
        solve would be a second answer standing next to the first. WHY off by
        default: the picture alone is what the panel has always shown, so a
        browser that never asks for the arrows sees exactly the view it saw
        before and the toggle stays a pure addition.

        The arrows are anchored ON the plane the picture stands in and carry no
        x component: the field in this cross-section plane has no component out
        of itself, so an arrow leaving the plane would be an invention rather
        than a reading.

        The glyph's scale is the ARRAY NAME and not ``False``: ``scale=False``
        draws every arrow at unit length, which would throw the recorded
        magnitudes away and paint a field of equal arrows. Every failure is a
        print to stderr - the overlay is an extra, never the answer.
        """
        try:
            _clear_mode_quiver()
            points, vectors = _mode_quiver_arrows(
                result, x_mm=x_mm, y_centre_mm=y_centre_mm
            )
            if points.size == 0 or vectors.size == 0:
                print(
                    "[poc_app] mode vector field skipped: no sample to draw",
                    file=sys.stderr,
                )
                return
            # The vectors ride as POINT data named by the glyph call below: this
            # pyvista (0.49.2) has no ``vectors=`` keyword on PolyData.
            cloud = pv.PolyData(points)
            cloud.point_data["mode_e_arrows"] = vectors
            arrows = cloud.glyph(
                orient="mode_e_arrows", scale="mode_e_arrows", factor=1.0
            )
            actor = plotter.add_mesh(
                arrows,
                color="white",
                lighting=False,
                show_scalar_bar=False,
                name="mode_quiver",
            )
            handles["mode_quiver"] = {
                "actor": actor,
                "page_path": page.get("path"),
                "family": "xcut",
                "index": index,
            }
            # The picture's own rule, applied to its overlay: arrows on a hidden
            # picture are hidden too, so the y-cut view stays as clean as it was.
            actor.visibility = state.mode == "xcut"
        except Exception as exc:  # noqa: BLE001 - the overlay is an EXTRA
            print(f"[poc_app] mode vector field skipped: {exc}", file=sys.stderr)

    def _show(frame, mode=None) -> None:
        """Draw ONE frame of the selected family. Never rescales.

        The colour limits were fixed when the sheets were added, so this only
        swaps the scalar array: there is no per-frame normalisation here that
        could paint the recorded decay away.
        """
        # The LIVE page, read on every draw: a finished solve swaps the dump
        # under this closure, and the readouts below must follow it.
        info = page["info"]
        previous_mode = state.mode
        mode = state.mode if mode is None else mode
        mode = "xcut" if mode == "xcut" else "ycut"
        mode_changed = mode != previous_mode
        frames = nt if mode == "ycut" else nt_x
        try:
            index = int(round(float(frame)))
        except (TypeError, ValueError):
            index = int(state.frame)
        # A page with no timeline has no frame axis to clamp into: nothing was
        # indexed (no sheet was drawn), and the label below stays ABSENT rather
        # than claiming frame 1 of None.
        if frames is None:
            index = 0
        else:
            index = max(0, min(frames - 1, index))
        state.frame = index
        state.mode = mode

        for key, entry in sheets.items():
            visible = entry["family"] == mode
            try:
                entry["actor"].visibility = visible
            except Exception as exc:  # noqa: BLE001 - a stuck sheet is not fatal
                print(
                    f"[poc_app] sheet visibility skipped: {exc}", file=sys.stderr
                )
            if not visible:
                continue
            array = info[key]
            if array.shape[0] == 0:
                continue
            data = np.abs(
                np.asarray(
                    array[min(index, int(array.shape[0]) - 1)], dtype=float
                )
            )
            try:
                entry["grid"].point_data["ez_abs"] = np.ascontiguousarray(
                    data.ravel(order="F"), dtype=float
                )
                entry["grid"].point_data.active_scalars_name = "ez_abs"
                entry["grid"].Modified()
            except Exception as exc:  # noqa: BLE001 - keep the old frame
                print(
                    f"[poc_app] frame update skipped for {key}: {exc}",
                    file=sys.stderr,
                )

        # The Mode picture is NOT one of the three sheets and must never be
        # treated as one: it is a still cross-section, so it is shown only for
        # its OWN family (the y-z plane the x-cuts are drawn in - edge-on to the
        # y-cut camera it would be a line) and only for the dump it was solved
        # from. A family switch, or a solve that swapped the page, must never
        # resurrect it.
        mode_entry = handles.get("mode_actor")
        if mode_entry is not None:
            try:
                mode_entry["actor"].visibility = (
                    mode_entry.get("family") == mode
                    and mode_entry.get("page_path") == page.get("path")
                )
            except Exception as exc:  # noqa: BLE001 - a picture is not the page
                print(
                    f"[poc_app] mode picture visibility skipped: {exc}",
                    file=sys.stderr,
                )
        # The arrow OVERLAY follows the picture it annotates - the same family,
        # the same page - and is hidden outright while the toggle is off, so a
        # field can never outlive the cross-section it was sampled on.
        quiver_entry = handles.get("mode_quiver")
        if quiver_entry is not None:
            try:
                quiver_entry["actor"].visibility = (
                    bool(state.show_quiver)
                    and quiver_entry.get("family") == mode
                    and quiver_entry.get("page_path") == page.get("path")
                )
            except Exception as exc:  # noqa: BLE001 - an overlay is not the page
                print(
                    f"[poc_app] mode vector field visibility skipped: {exc}",
                    file=sys.stderr,
                )
        # The family switch above is also a title switch: the picture just went
        # hidden (or came back), and the title names the field now on screen.
        _sync_picture_title()

        if mode_changed:
            _swap_scalar_bar(mode)

        if mode_changed or not handles.get("camera_framed"):
            # Frame the sheet that is about to be drawn, not the whole 3-D box:
            # with all three sheets plus the substrate in view the animated field
            # was a sliver in the middle of the picture. view_xz looks along -y
            # (the y-cut sheet's own plane), view_yz along -x (the plane both
            # x-cut sheets sit in).
            bounds = None
            for entry in sheets.values():
                if entry["family"] != mode:
                    continue
                b = entry["grid"].bounds
                bounds = (
                    b
                    if bounds is None
                    else (
                        min(bounds[0], b[0]),
                        max(bounds[1], b[1]),
                        min(bounds[2], b[2]),
                        max(bounds[3], b[3]),
                        min(bounds[4], b[4]),
                        max(bounds[5], b[5]),
                    )
                )
            for actor, drawn_opacity in overlay:
                try:
                    if mode == "ycut":
                        # Square on to the x-z sheet the substrate is edge-on and
                        # would cover the field it is meant to annotate, so it is
                        # dimmed (and outlined) only for this family.
                        actor.prop.opacity = 0.15
                        actor.prop.show_edges = True
                    else:
                        actor.prop.opacity = drawn_opacity
                except Exception as exc:  # noqa: BLE001 - decoration only
                    print(
                        f"[poc_app] overlay opacity skipped: {exc}",
                        file=sys.stderr,
                    )
            try:
                if mode == "ycut":
                    plotter.view_xz(bounds=bounds, render=False)
                else:
                    plotter.view_yz(bounds=bounds, render=False)
                handles["camera_framed"] = True
            except Exception as exc:  # noqa: BLE001 - keep the previous camera
                print(
                    f"[poc_app] camera reframe skipped: {exc}",
                    file=sys.stderr,
                )

        t_ns = _vis_frame_time_ns(info, mode, index)
        state.t_label = (
            "sim time: not recorded"
            if not np.isfinite(t_ns)
            else f"sim time: t = {t_ns:.6f} ns"
        )
        state.frame_label = (
            None if frames is None else f"frame {index + 1} / {frames}"
        )
        state.phase_label = _vis_phase_text(t_ns, info.get("t_traverse_ns"))
        if mode == "ycut":
            # The y the x-z sheet sits on is READ per draw, from the LIVE page,
            # and is None when the dump records no j_cut - in which case no such
            # sheet exists to name. The readout says that rather than quoting a
            # station nothing was drawn at.
            station = _finite(info.get("j_cut"))
            state.mode_label = (
                "x-z sheet: not recorded - this dump carries no j_cut, "
                "so no x-z sheet is drawn"
                if station is None
                else (
                    f"x-z sheet at y = {float(station) * cell_mm:.4f} mm "
                    "(one recorded y sample)"
                )
            )
        else:
            # FIXED planes. These two y-z slices are the only ones the dump
            # carries, so the viewer cannot sweep x through them: that would
            # mean dumping the whole 3-D field (~2 GB) instead of two sheets.
            # The positions are read from the dump, never written as literals,
            # and the near/far names are claimed only when the recorded load
            # position agrees with them - otherwise they are slice 1 and 2.
            near_mm = _finite(info["xcut_near_mm"])
            far_mm = _finite(info["xcut_far_mm"])
            load_mm = _finite(info["load_x_mm"])
            near_side, far_side = "slice 1", "slice 2"
            if (
                near_mm is not None
                and far_mm is not None
                and load_mm is not None
                and abs(near_mm - load_mm) <= abs(far_mm - load_mm)
            ):
                near_side, far_side = "load side", "stub side"
            near_text = (
                "not recorded" if near_mm is None else f"{near_mm:.4f}"
            )
            far_text = "not recorded" if far_mm is None else f"{far_mm:.4f}"
            strip_mm = _finite(info["strip_w_mm"])
            width_mm = _finite(y_span_mm)
            strip_text = (
                "not recorded" if strip_mm is None else f"{strip_mm:.1f}"
            )
            width_text = (
                "not recorded" if width_mm is None else f"{width_mm:.1f}"
            )
            state.mode_label = (
                "Transverse cross-section (y-z) looking down the line. "
                f"Strip width = {strip_text} mm, "
                f"domain width = {width_text} mm."
                f" Planes FIXED at x = {near_text} / {far_text} mm "
                f"({near_side} / {far_side}; the dump stores only these two)."
            )
        try:
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - never take the server down
            print(f"[poc_app] render skipped: {exc}", file=sys.stderr)
        view_handle = handles.get("view")
        if view_handle is not None:
            try:
                view_handle.update()
            except Exception as exc:  # noqa: BLE001
                print(f"[poc_app] view update skipped: {exc}", file=sys.stderr)

    def _rebuild_sheets(mode=None) -> None:
        """Re-create the three field sheets from the LIVE page's own info.

        A finished solve replaces every array on the page, so the sheets built at
        boot belong to a dump that is no longer the one on screen. They are
        removed and rebuilt here with the NEW dump's single colour limit, and the
        camera is re-framed because the new domain need not have the old bounds.
        """
        nonlocal nt, nt_x, vmin, vmax, cell_mm, y_span_mm
        live = page["info"]
        nt = int(live["nt"])
        nt_x = int(live["nt_x"])
        vmin, vmax = live["color_range"]
        cell_mm = _cell_mm(live)
        y_span_mm = float(int(live["ny"])) * cell_mm
        for entry in list(sheets.values()):
            try:
                plotter.remove_actor(entry["actor"], render=False)
            except Exception as exc:  # noqa: BLE001 - a stuck sheet is invisible
                # _show() only ever makes the SELECTED family visible, so an
                # actor that refuses to be removed still cannot be seen.
                print(
                    f"[poc_app] stale sheet kept: {exc}", file=sys.stderr
                )
        sheets.clear()
        # A finished solve put a NEW dump on screen, so the mode picture was
        # solved for a page that is no longer live: it goes with the old sheets.
        # Same "one rule" as the caption helpers - after a solve the Mode panel
        # says nothing has been run, and now nothing is drawn either.
        _clear_mode_picture()
        for key, family in (
            ("ez_ycut", "ycut"),
            ("ez_xcut_near", "xcut"),
            ("ez_xcut_far", "xcut"),
        ):
            try:
                grid = _vis_grid(live, key, 0)
                actor = plotter.add_mesh(
                    grid,
                    scalars="ez_abs",
                    cmap="turbo",
                    clim=(vmin, vmax),
                    smooth_shading=False,
                    show_edges=VIS_SHOW_EDGES,
                    show_scalar_bar=(family == "ycut"),
                    scalar_bar_args={"title": scalar_bar_title},
                )
            except Exception as exc:  # noqa: BLE001 - one sheet is not the page
                print(
                    f"[poc_app] plane {key} not redrawn: {exc}", file=sys.stderr
                )
                continue
            sheets[key] = {"grid": grid, "actor": actor, "family": family}
        state.frame_max = _frame_span_max(nt, nt_x, mode or state.mode)
        # The prose lines that name THIS dump's numbers are rebuilt from `live`
        # rather than kept from boot: a solve can change the arm, the velocity
        # record and the colour ceiling all at once.
        state.structure_readout = _structure_readout_text(live)
        state.velocity_label = _velocity_label(live)
        state.scale_label = _scale_label(live)
        state.velocity_note = live["velocity_note"] or "velocity note: not recorded"
        # A finished solve put a NEW dump on screen and this one has not had its
        # mode solved, so the panel goes back to the boot text - through the very
        # helpers that set it at boot, not by re-typing the sentence here.
        state.mode_view_label = _mode_button_label(None)
        state.mode_view_caption = _mode_caption_text(None)
        # The candidates belonged to the mode solved for the PREVIOUS dump, so
        # both the kept result and the picker's items go with it: a pick here
        # must never repaint an old mode over this page's cross-section.
        handles["mode_result"] = None
        with state.suppress_change_listeners("mode_choice"):
            state.mode_choice_items = []
            state.mode_choice = 0
        handles["camera_framed"] = False
        _show(0, mode or state.mode)

    # Initial labels, set before the layout is built so the first page a browser
    # loads already carries frame 1's own numbers.
    _show(0, "ycut")

    # THE FIRST PICTURE on a plane-stack page is the cut's own redraw. The
    # sheet loop above (:7372-7406) keys off `ez_ycut` / `ez_xcut_near` /
    # `ez_xcut_far`, none of which a legacy field dump carries, so `sheets` is
    # EMPTY here and _show drew nothing: without these three lines the shell
    # would stand a blank plotter on the page. run_web draws its first picture
    # the same way (:4460), through the same function its sliders call. On
    # every other page the handle is absent and this does nothing at all, so
    # _show's behaviour there is exactly what it was.
    _cut_redraw = handles.get("cut_redraw")
    if _cut_redraw is not None:
        _cut_redraw()

    # v_model=("frame", 0) only WRITES state["frame"]: trame turns a callable
    # into a server call for EVENT kwargs (click=, change=), never for v_model,
    # so an @ctrl.set("frame") trigger would never be reached. Hang the redraw
    # off the state change itself - the slider and every other writer of
    # state.frame then take the same path.
    @state.change("frame")
    def _on_frame(frame=None, **_kwargs) -> None:
        if handles.get("suppress_frame_listener"):
            return  # the play loop drives _show() itself
        _show(state.frame if frame is None else frame, state.mode)

    @ctrl.set("mode_toggle")
    def _on_mode_toggle(**_kwargs) -> None:
        """Swap which family is animated. The two clocks are never mixed."""
        mode = "xcut" if state.mode == "ycut" else "ycut"
        state.frame_max = _frame_span_max(nt, nt_x, mode)
        if state.frame_max is None:
            # NO TIMELINE: this page carries ONE static picture and no second
            # family to swap to (both counts are None), so the press changes
            # nothing. _show() is deliberately NOT called: its x-cut readouts
            # name keys only an animation dump records, so drawing a family
            # here would raise on the very dumps that have no timeline - and a
            # "Switch plane" press must never take the server down, which is
            # exactly what int(None) used to do.
            return
        _show(min(int(state.frame), int(state.frame_max)), mode)

    # A step pressed while the animation RUNS is a SEEK, not a stop: ten frames
    # per press, so crossing a 100-frame dump while it plays is 10 presses
    # instead of 100. WHY not "always 10": on a stopped page the arrows mean
    # "the next picture", and a 10-frame jump would skip the one being examined.
    @ctrl.set("step_back")
    def _on_step_back(**_kwargs) -> None:
        """Ten frames back while playing, exactly one while stopped.

        A running animation is NOT stopped by a seek: ``state.playing`` and the
        pause label are left alone (only the stopped branch has anything to
        stop), so the play loop keeps advancing from wherever the seek landed.
        """
        # The SAME frame count the one-frame step has always used: the two
        # clocks have different lengths (nt on ez_ycut, nt_x on each x-cut) and
        # a seek has to wrap on the one on screen. ``max(1, ...)`` is the
        # zero-frame guard - an empty axis would otherwise raise
        # ZeroDivisionError in the modulo, and on a one-frame axis every step
        # lands on frame 0, which is the only frame there is.
        frames = max(1, nt if state.mode == "ycut" else nt_x)
        if state.playing:
            _show((int(state.frame) - 10) % frames, state.mode)
            return
        state.playing = False
        state.play_label = "play"
        _show((int(state.frame) - 1) % frames, state.mode)

    @ctrl.set("step_fwd")
    def _on_step_fwd(**_kwargs) -> None:
        """Ten frames forward while playing, exactly one while stopped.

        See _on_step_back: same split, same reason, same frame count.
        """
        frames = max(1, nt if state.mode == "ycut" else nt_x)
        if state.playing:
            _show((int(state.frame) + 10) % frames, state.mode)
            return
        state.playing = False
        state.play_label = "play"
        _show((int(state.frame) + 1) % frames, state.mode)

    @ctrl.set("top_view")
    def _on_top_view(**_kwargs) -> None:
        """Look straight down the z axis: the layout, not an animation frame.

        The view method is called without rendering - render() is the one call
        that can fail on this build, so it gets its own guard. A build without
        view_xy keeps the camera it had.
        """
        try:
            plotter.view_xy(render=False)
        except Exception as exc:  # noqa: BLE001 - keep the current view
            print(f"[poc_app] top view unavailable: {exc}", file=sys.stderr)
            return
        try:
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - never take the server down
            print(f"[poc_app] top view render skipped: {exc}", file=sys.stderr)

    @ctrl.set("side_view")
    def _on_side_view(**_kwargs) -> None:
        """Look along -y at the x-z section: the line seen from the side."""
        try:
            plotter.view_xz(render=False)
        except Exception as exc:  # noqa: BLE001 - keep the current view
            print(f"[poc_app] side view unavailable: {exc}", file=sys.stderr)
            return
        try:
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - never take the server down
            print(f"[poc_app] side view render skipped: {exc}", file=sys.stderr)

    def _build_s_params() -> dict:
        """Read the sweep from disk, draw it, and pick the ONE number to quote.

        Called on the FIRST open of the panel only: reading the JSON and
        rendering the PNG are the slow steps on this page and neither depends on
        the animation frame, so doing them again on every open would cost the
        same and show nothing new. The sweep is a DIFFERENT artefact from the
        animation beside it (the dump is one run at one frequency), which is why
        the caption names the file it came from.
        """
        info = page["info"]
        # The dump's OWN provenance picks the arm, so a B dump can only ever be
        # drawn from B's sweep - or from B's single run, or from nothing.
        structure_id = info.get("structure_id")
        arm = _structure_key(structure_id)
        multifreq = load_multifreq(info["path"], structure_id)
        if multifreq is None:
            # The caption carries the registry gap as well as the lookups:
            # "no S-parameter data" alone is true of four different situations
            # (no arm recorded, no summary registered for this arm, a sweep that
            # will not parse, a sweep with no usable row) and names none of them.
            return {
                "path": None,
                "points": [],
                "chart": None,
                "image": None,
                "rows": [],
                "reason": "no S-parameter data",
                "caption": (
                    "no S-parameter data for structure "
                    f"{structure_id or 'unknown'}: "
                    f"{_absent_multifreq_reason(arm, info['path'])}"
                ),
                "single_point": False,
                "number": "",
            }
        # The RESOLVED path is printed rather than assumed: load_multifreq falls
        # back to this arm's own sweep (or, with no sweep, its single run), and a
        # reader has to be able to tell which file these rows came from.
        print(
            f"[poc_app] s-params panel: "
            f"{'single-run record' if multifreq.get('single_point') else 'sweep'} "
            f"{multifreq['path']}"
        )
        # The summary's own title wins when it has one: it is the file that knows
        # which runs these rows came from. Older summaries carry none, and then
        # the registry entry names the chart exactly as it did before.
        chart = build_frequency_chart(
            multifreq, multifreq.get("title") or _chart_title(structure)
        )
        # The dump records f_ref_hz in HZ while the sweep rows are in GHz, and the
        # nearest-point comparison happens in GHz: convert here, once, so the
        # scale never has to be guessed from the printed text.
        f_ref_hz = _finite(info.get("f_ref_hz"))
        f_ref_ghz = None if f_ref_hz is None else f_ref_hz / 1e9
        return {
            "path": multifreq["path"],
            "points": multifreq["points"],
            "chart": chart,
            "image": chart.get("image"),
            "rows": chart.get("rows") or [],
            "reason": chart.get("reason"),
            "caption": _frequency_caption(
                multifreq, _field_record(info["path"]), arm
            ),
            "single_point": bool(multifreq.get("single_point")),
            "number": _s_params_number_text(multifreq, f_ref_ghz),
        }

    def _load_s_params_panel() -> None:
        """Populate the S-parameters panel; the tab owns its visibility.

        Called ONCE while the layout is being built, not from a controller
        trigger: there is no button to press any more, so the JSON parse and the
        matplotlib render are paid here and the tab is populated the first time
        it is selected. ``handles["s_params"]`` is still the cache - a second
        call re-uses the same parsed rows and the same PNG, and the state strings
        pushed from it are identical.

        Nothing here may raise: the panel is an extra, so a failure costs the
        panel and one stderr line, never the animation beside it.
        """
        try:
            if "s_params" not in handles:
                handles["s_params"] = _build_s_params()
            panel = handles["s_params"]
            caption = panel["caption"]
            # No data is still an ANSWER, and the panel shows it: the caption
            # names the arm and every path that was looked for. A panel that
            # silently stayed empty would be the worse outcome.
            image = panel.get("image")
            if image:
                state.s_params_image = image
                state.s_params_image_style = (
                    "height: 150px; display: block; margin: 4px 0;"
                )
            else:
                # No picture is a REASON, not an empty panel: the text rows are
                # the numbers the chart would have drawn, and the reason is
                # printed with the caption instead of being swallowed.
                state.s_params_rows = "\n".join(panel.get("rows") or [])
                state.s_params_rows_style = "font-size: 10px; margin: 4px 0;"
                if panel.get("reason"):
                    caption += f" (text rows instead: {panel['reason']})"
            state.s_params_caption = caption
            state.s_params_number = panel["number"]
        except Exception as exc:  # noqa: BLE001 - the panel is not the page
            print(f"[poc_app] s-params panel unavailable: {exc}", file=sys.stderr)

    def _build_confidence() -> dict:
        """Read this page's record (and the referee) and render the panel rows.

        The ONLY I/O this panel does: the record beside the dump now on screen,
        plus the referee extraction when it is on disk. The rows themselves are
        ``build_confidence_block``'s - a pure function - so what a test asserts on
        and what a reader sees are the same strings.
        """
        info = page["info"]
        referee = None
        referee_path = _referee_s11_path()
        if referee_path is not None and Path(referee_path).is_file():
            referee = _read_json(referee_path)
        block = build_confidence_block(
            _field_record(info["path"]), referee, record_path=str(info["path"])
        )
        footer = list(block.get("basis") or []) + list(block.get("sources") or [])
        lines = [f"{label}: {text}" for label, text in block.get("rows") or []]
        if footer:
            lines.append("")
            lines.extend(footer)
        return {
            "caption": block["caption"],
            "text": "\n".join(lines),
            "status": block["status"],
        }

    def _load_confidence_panel() -> None:
        """Populate the Confidence & Accuracy panel; the tab owns its visibility.

        Called ONCE while the layout is being built, like the S-parameters
        loader: reading the record and the referee file is I/O that no button
        gates any more, so it is paid at layout time and the tab holds text the
        first time it is selected. ``handles["confidence"]`` is still the cache,
        and it is dropped when a solve replaces the page.

        Nothing here may raise: the panel is an extra beside the animation, so a
        failure costs the panel and one stderr line.
        """
        try:
            if "confidence" not in handles:
                handles["confidence"] = _build_confidence()
            panel = handles["confidence"]
            # A refused panel is FILLED too: "no study record beside this dump"
            # is the answer its tab exists to show.
            state.confidence_caption = panel["caption"]
            state.confidence_rows = panel["text"]
        except Exception as exc:  # noqa: BLE001 - the panel is not the page
            print(f"[poc_app] confidence panel unavailable: {exc}", file=sys.stderr)

    def _load_far_field_panel() -> None:
        """Populate the Far Field panel; the tab owns its visibility.

        Called ONCE while the layout is being built, like the S-parameters
        loader: reading the archive and integrating the pattern are the slow
        steps and neither depends on the animation frame, so
        ``handles["far_field"]`` caches the panel and a second call republishes
        the same strings.

        A refusal is FILLED too: "no --surface-dump archive was given" is the
        answer this tab exists to give, and a tab that opened blank would read
        as a broken picture rather than as a missing input.

        Nothing here may raise: the panel is an extra, so a failure costs the
        panel and one stderr line, never the animation beside it.
        """
        try:
            if "far_field" not in handles:
                handles["far_field"] = build_far_field_panel(surface_dump)
            panel = handles["far_field"]
            caption = panel["caption"]
            image = panel.get("image")
            if image:
                state.far_field_image = image
                state.far_field_image_style = (
                    "height: 150px; display: block; margin: 4px 0;"
                )
            else:
                # No picture is a REASON, not an empty panel: the text rows are
                # the numbers the plot would have drawn, and the reason is
                # printed with the caption instead of being swallowed.
                #
                # ``rows`` from ``build_far_field_report`` are ``(label,
                # value)`` PAIRS, not strings - the S-parameters helper's rows
                # happen to be strings, so the identical-looking join there
                # works and this one would raise TypeError. Flatten each pair
                # to one line instead: the join is the whole panel, and a
                # TypeError here would cost the caption and the number too.
                state.far_field_rows = "\n".join(
                    f"{row[0]}: {row[1]}"
                    if isinstance(row, (tuple, list)) and len(row) == 2
                    else str(row)
                    for row in (panel.get("rows") or [])
                )
                state.far_field_rows_style = "font-size: 10px; margin: 4px 0;"
                if panel.get("reason"):
                    caption += f" (no picture: {panel['reason']})"
            state.far_field_caption = caption
            state.far_field_number = panel["number"]
        except Exception as exc:  # noqa: BLE001 - the panel is not the page
            print(f"[poc_app] far-field panel unavailable: {exc}", file=sys.stderr)

    @ctrl.set("mode_view_toggle")
    async def _on_mode_view(**_kwargs) -> None:
        """Solve the 2D cross-section for the page ON SCREEN, OFF the event loop.

        ``mode_view`` is a scipy mesh solve (~0.1 s, and unbounded on a bad
        geometry), so it is pushed to a worker thread: the play loop keeps
        turning while it runs. It is handed the LIVE page, so a press after a
        solve describes the dump now on screen and not the one the app booted
        with, and its result is turned into the two state strings by the module
        helpers - a refusal is shown on the same line the numbers would have
        used. Nothing here may raise: this panel is an extra beside the
        animation, so a failure costs the panel and one caption line.
        """
        try:
            result = await asyncio.to_thread(mode_view, page)
        except Exception as exc:  # noqa: BLE001 - mode_view is not supposed to raise
            result = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
        state.mode_view_label = _mode_button_label(result)
        state.mode_view_caption = _mode_caption_text(result)
        # The solve's own result is KEPT so the picker can repaint the picture at
        # another candidate without solving anything again. A refusal clears it:
        # then there is nothing the picker could honestly draw.
        handles["mode_result"] = result if result.get("ok") else None
        # A press re-points the picker at the solver's pick. It does so under
        # suppress_change_listeners because THIS handler draws the picture: the
        # write to `mode_choice` would otherwise reach the state-change listener
        # below and draw the same grid a second time.
        with state.suppress_change_listeners("mode_choice"):
            state.mode_choice_items = _mode_candidate_items(result)
            state.mode_choice = int(result.get("chosen") or 0)
        # The picture is the EXTRA, and it is attempted only AFTER the two
        # strings above are published: every step here is guarded, so a press
        # that cannot draw still shows its numbers.
        try:
            _draw_mode_picture(result, index=int(result.get("chosen") or 0))
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - the caption is already on screen
            print(
                f"[poc_app] mode picture skipped: {exc}", file=sys.stderr
            )
        view_handle = handles.get("view")
        if view_handle is not None:
            try:
                view_handle.update()
            except Exception as exc:  # noqa: BLE001
                print(f"[poc_app] view update skipped: {exc}", file=sys.stderr)

    # The Mode picker's redraw. v_model=("mode_choice", ...) only WRITES
    # state["mode_choice"]: trame turns a callable into a server call for EVENT
    # kwargs (click=, change=), never for v_model, so an @ctrl.set("mode_choice")
    # trigger would never be reached - the browser calls "trame.trigger" only for
    # the triggers it was TOLD to call. Hang the repaint off the state change
    # itself, exactly as the frame slider above does, and every writer of
    # `mode_choice` - the select, a proof, a future button - takes one path.
    @state.change("mode_choice")
    def _on_mode_choice(mode_choice=None, **_kwargs) -> None:
        """Repaint the Mode picture for the candidate the picker names."""
        result = handles.get("mode_result")
        if not isinstance(result, dict) or not result.get("ok"):
            return
        try:
            index = int(state.mode_choice if mode_choice is None else mode_choice)
        except (TypeError, ValueError):
            return
        view = _mode_view_for_candidate(result, index)
        if view is None:
            # A pick this solve cannot draw leaves the picture and the caption
            # alone: swapping nothing and SAYING nothing is the honest answer.
            return
        try:
            _draw_mode_picture(view, index=index)
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - the caption is still owed
            print(
                f"[poc_app] mode candidate picture skipped: {exc}", file=sys.stderr
            )
        state.mode_view_caption = _mode_choice_caption_text(result, index)
        view_handle = handles.get("view")
        if view_handle is not None:
            try:
                view_handle.update()
            except Exception as exc:  # noqa: BLE001
                print(f"[poc_app] view update skipped: {exc}", file=sys.stderr)

    # The arrow overlay's toggle. The checkbox only WRITES state["show_quiver"],
    # so the redraw hangs off the state change itself - the rule the frame slider
    # and the mode picker already follow, and every writer of the flag then takes
    # one path. The field is the MODE EIGENVECTOR: it does not vary from frame to
    # frame, so it is deliberately NOT wired to the scrubber - arrows that redrew
    # per frame would imply the transverse profile was being animated when it is
    # a property of the mode that was solved.
    @state.change("show_quiver")
    def _on_show_quiver(show_quiver=None, **_kwargs) -> None:
        """Draw or drop the Mode arrow overlay. NEVER raises."""
        try:
            wanted = bool(state.show_quiver if show_quiver is None else show_quiver)
            entry = handles.get("mode_actor")
            has_mode_picture = (
                isinstance(entry, dict) and entry.get("actor") is not None
            )
            if has_mode_picture:
                # The picture's own handle carries what the overlay is drawn
                # from, so the toggle repaints THIS cross-section and never
                # re-solves it - and a page that HAS a mode picture never takes
                # the redraw path below, so its behaviour is unchanged.
                if not wanted:
                    _clear_mode_quiver()
                else:
                    _draw_mode_quiver(
                        entry.get("result"),
                        x_mm=entry.get("x_mm", 0.0),
                        y_centre_mm=entry.get("y_centre_mm", 0.0),
                        index=entry.get("index"),
                    )
            else:
                # No mode picture: the field this box turns on is the 3-D VOLUME
                # arrow field of the scene, which lives through
                # handles["cut_redraw"] -> _show_volume_quiver and is therefore
                # drawn or dropped by a redraw and by nothing else. Reached
                # through the handle, because a page without a plane stack never
                # bound a redraw (a local name would be unbound there).
                redraw = handles.get("cut_redraw")
                if callable(redraw):
                    redraw()
                else:
                    _clear_mode_quiver()
                    if wanted:
                        # Nothing solved on screen and nothing to redraw: saying
                        # so is the honest answer, rather than drawing a field
                        # with no mode under it.
                        print(
                            "[poc_app] mode vector field skipped: no mode picture "
                            "to overlay",
                            file=sys.stderr,
                        )
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - the overlay is an EXTRA
            print(
                f"[poc_app] mode vector field toggle skipped: {exc}", file=sys.stderr
            )

    # The two marker-plane boxes. Same rule as the arrow field above: the box
    # only WRITES the flag, and the redraw hangs off the state change, so every
    # writer of the flag takes one path - and the picture that answers is the
    # scene rebuilt, which is what a redraw already does.
    def _redraw_for_plane_toggle(what: str) -> None:
        """Repaint the scene after a marker plane was switched. NEVER raises."""
        try:
            redraw = handles.get("cut_redraw")
            if callable(redraw):
                # Through the handle, for the arrow field's reason: a page with
                # no plane stack never bound a local _redraw (and drew no box
                # to ask for one), so there is nothing to repaint and nothing
                # to explain.
                redraw()
        except Exception as exc:  # noqa: BLE001 - a marker is an EXTRA
            print(f"[poc_app] {what} plane toggle skipped: {exc}", file=sys.stderr)

    @state.change("show_load_plane")
    def _on_show_load_plane(**_kwargs) -> None:
        """Draw or drop the red load plane. NEVER raises."""
        _redraw_for_plane_toggle("load")

    @state.change("show_port_plane")
    def _on_show_port_plane(**_kwargs) -> None:
        """Draw or drop the purple S11 port plane. NEVER raises."""
        _redraw_for_plane_toggle("S11 port")

    # The fallback expander's handler. Only the VBtn path binds it: the panels
    # path is opened and closed by Vuetify itself and never reaches the server.
    @ctrl.set("netlist_toggle")
    def _on_netlist_toggle(**_kwargs) -> None:
        """Open/close the netlist box when the build has no expansion panels."""
        state.netlist_open = not bool(state.netlist_open)

    def _emit_circuit_netlist() -> None:
        """Emit the CIRCUIT NETLIST editor: one optional multi-line box.

        WHY a box and not a form: the netlist is a whole circuit written as
        JSON, pasted in from wherever it was designed. The box is bound to
        `solve_netlist_json`, which the solve path already reads, so EMPTY and
        absent mean the same thing: the built-in 50 ohm resistor study, exactly
        as it behaved before this box existed. Nothing here validates the text
        - a netlist half-typed must never put a banner on screen while it is
        still being typed, and the field is optional besides.

        The wrapper belongs to the caller: the SETUP column folds this into its
        Circuit section and the DATA column's Circuit tab emits it bare, so
        this emits the note and the box and nothing else.

        The widget class is resolved with the same getattr idiom the controls
        use, so a variant shipping no VTextarea gets a plain note instead of a
        traceback: the editor is a convenience, the solve is the point.
        """
        note = (
            "Leave EMPTY for the built-in 50 ohm resistor study; fill it to "
            "terminate the load's cut in the circuit instead."
        )
        if html_div is not None:
            html_div(
                note,
                style="font-size: 11px; color: #333; padding: 2px 0;",
            )
        elif "VLabel" in widgets:
            widgets["VLabel"](note)
        textarea_cls = getattr(widgets_module, "VTextarea", None)
        # The box starts COLLAPSED: it is optional, and six empty rows on every
        # page load made the Circuit tab look like a form to fill in before a
        # solve could run. THREE classes, all resolved the same getattr way the
        # box is, because all three are trame-vuetify's and none is guaranteed:
        # VExpansionPanelText is NOT optional here - Vuetify renders a panel's
        # DEFAULT slot OUTSIDE the collapsible region (VExpansionPanel's own
        # render builds VExpansionPanelTitle/VExpansionPanelText for
        # props.title/props.text and then appends slots.default() as a plain
        # child), so nesting the box straight under the panel would leave it
        # permanently visible under the header. It is only collapsible inside
        # VExpansionPanelText, which is what injects the panel's $p context.
        #
        # The TEXT SURVIVES a collapse: VExpansionPanelText wraps its body in
        # ``v-show`` but gates the body on useLazy's ``hasContent``, which drops
        # back to False once the leave transition finishes - the box is really
        # UNMOUNTED, not merely hidden. That is safe here and is why the
        # binding stays ``v_model=("solve_netlist_json", "")``: the text lives
        # in SERVER state; the first element of that tuple is only the DEFAULT
        # used when the key is absent, and the key exists from boot (set to ""
        # beside the other solve state), so a remount re-reads the current value
        # and re-typing is never required.
        panels_cls = getattr(widgets_module, "VExpansionPanels", None)
        panel_cls = getattr(widgets_module, "VExpansionPanel", None)
        panel_text_cls = getattr(widgets_module, "VExpansionPanelText", None)
        if (
            textarea_cls is not None
            and panels_cls is not None
            and panel_cls is not None
            and panel_text_cls is not None
        ):
            with panels_cls(classes="mb-1"):
                # No v_model on the panels on purpose: an unselected group is
                # collapsed, and passing a model would open the first panel.
                with panel_cls(title="Add Circuit Netlist"):
                    with panel_text_cls():
                        textarea_cls(
                            v_model=("solve_netlist_json", ""),
                            label="Circuit Netlist (JSON)",
                            placeholder=(
                                "Leave empty for the built-in 50 ohm resistor "
                                "study; fill it to terminate the load's cut in "
                                "a circuit."
                            ),
                            rows=6,
                            density="compact",
                            hide_details=True,
                            classes="mb-1",
                        )
            return
        if textarea_cls is not None:
            # FALLBACK for a variant with no expansion panels (or no
            # VExpansionPanelText to put the body in): a button and the same
            # flag-driven v_if the panels express. ``state.netlist_open`` is
            # (re)set to False here rather than at boot so a re-emitted page - a
            # solve swaps the dump and rebuilds the layout - starts collapsed
            # again, exactly like the panels' unselected group.
            state.netlist_open = False
            btn_cls = getattr(widgets_module, "VBtn", None)
            if btn_cls is not None:
                btn_cls(
                    "Add Circuit Netlist",
                    click=ctrl.netlist_toggle,
                    size="small",
                    variant="text",
                    classes="mb-1",
                )
            textarea_cls(
                v_if=("netlist_open", False),
                v_model=("solve_netlist_json", ""),
                label="Circuit Netlist (JSON)",
                placeholder=(
                    "Leave empty for the built-in 50 ohm resistor study; "
                    "fill it to terminate the load's cut in a circuit."
                ),
                rows=6,
                density="compact",
                hide_details=True,
                classes="mb-1",
            )
            return
        pre_cls = getattr(html_widgets, "Pre", None)
        if pre_cls is not None:
            pre_cls(
                "netlist editor unavailable (no VTextarea) - solves stay on "
                "the built-in resistor study",
                style=(
                    "font-size: 10px; white-space: pre-wrap; "
                    "margin: 4px 0;"
                ),
            )
        elif "VLabel" in widgets:
            widgets["VLabel"](
                "netlist editor unavailable (no VTextarea) - solves stay on "
                "the built-in resistor study"
            )

    def _emit_load_series_panel(load_series, reason) -> None:
        """Emit the load's recorded V(t)/I(t) trace under the Circuit netlist box.

        WHY it takes its block and reason as ARGUMENTS rather than reading `info`
        itself: the panel is emitted from two places (the Circuit tab, and the flat
        fallback used when the tab widgets are missing) and both must show the same
        run's trace, so the source of the pair stays single.

        The caption comes out even when nothing can be drawn, for the reason
        _emit_port_wave_panel gives: "no trace was taken for this run" is a
        different statement from "matplotlib is unusable here", and only the
        caption can make the first one.

        The rows are printed even when the picture IS drawn. That is deliberate:
        the figure's axes carry no numbers a headless check can read back, so the
        rows are what proves the panel drew THIS trace - its sample count, its time
        span and its V/I extremes - and they cost two lines.
        """
        if html_div is None:
            return
        try:
            chart = build_port_series_chart(load_series)
        except Exception as exc:  # noqa: BLE001 - the chart is never the point
            chart = {
                "image": None,
                "rows": [],
                "reason": f"the trace could not be drawn: {exc}",
            }
        html_div(
            _LOAD_SERIES_TITLE,
            style="font-size: 12px; font-weight: 600; padding: 4px 0 0 0;",
        )
        html_div(
            _load_series_caption(load_series, reason),
            style="font-size: 11px; color: #333; padding: 0 0 2px 0;",
        )
        image = chart.get("image")
        img_cls = getattr(html_widgets, "Img", None)
        if image and img_cls is not None:
            img_cls(
                src=image,
                style="height: 170px; display: block; margin: 4px 0;",
            )
        elif chart.get("reason"):
            html_div(
                f"no picture drawn: {chart['reason']}",
                style="font-size: 11px; color: #8a1c00; padding: 0 0 2px 0;",
            )
        rows = chart.get("rows") or []
        pre_cls = getattr(html_widgets, "Pre", None)
        if pre_cls is not None and rows:
            pre_cls(
                "\n".join(f"{label}: {value}" for label, value in rows),
                style="font-size: 10px; margin: 4px 0;",
            )

    def _emit_solve_controls() -> None:
        """Emit the SETUP column as a four-section engineering form.

        The caller decides which column the form lands in (the SETUP VCol, or the
        bare content area on the no-container fallback), so nothing here sizes or
        places the form itself: the column owns the width, the padding and the
        scroll. The form is a plain stack rather than a VContainer for the same
        reason - a container would add its own max-width and centring on top of a
        230 px column that already has both.

        Order is the order a run is set up in: Project (which arm), Mesh &
        Geometry (where the cut plane is, which cross-section is shown), Circuit
        (the netlist that terminates the cut, if there is one), Action (the
        solve, and what it said).

        Every widget class is resolved with the same getattr idiom the controls
        use, so a variant shipping no VCard degrades to a label plus the same
        controls instead of a traceback: the cards are the frame, the controls
        are the point.
        """
        card_cls = getattr(widgets_module, "VCard", None)
        card_title_cls = getattr(widgets_module, "VCardTitle", None)
        card_text_cls = getattr(widgets_module, "VCardText", None)
        divider_cls = getattr(widgets_module, "VDivider", None)
        cards = None not in (card_cls, card_title_cls, card_text_cls)

        def _section(title: str, body, *, first: bool = False) -> None:
            """Emit ONE section: a titled card, or the flat label fallback.

            WHY cards and not expansion panels: each section holds four controls
            or fewer, so collapsing one would hide settings behind a click that
            buys no space - and a panel carries its own open/closed state, which
            is exactly the hidden state the DATA column's tabs just removed. A
            rule is drawn between sections ONLY on the fallback path, where it is
            the one thing separating them; a card already draws that edge.
            """
            if cards:
                with card_cls(classes="mb-2"):
                    card_title_cls(title)
                    with card_text_cls():
                        body()
                return
            if not first and divider_cls is not None:
                divider_cls(classes="my-2")
            if "VLabel" in widgets:
                widgets["VLabel"](title)
            body()

        def _project() -> None:
            solve_arm_field = getattr(widgets_module, "VSelect", None)
            if solve_arm_field is not None:
                # The label reads Structure because that is what the value IS -
                # the map is keyed by the arm's id; items and default are
                # behaviour and stay exactly as they were.
                solve_arm_field(
                    v_model=("solve_structure", default_arm),
                    # A LIST here is read by trame as (state_name, default) and
                    # emitted as a bare `:items="A"` - the JS identifier of the
                    # first arm. v_bind_* is the only py-name trame maps back to
                    # `:items`, and a str value there is passed through as a JS
                    # expression, so the array literal survives verbatim. Single
                    # quotes, not json.dumps: the string is re-wrapped in double
                    # quotes by trame, so a " inside it would end the attribute.
                    # The arms come from the SOLVER's own STRUCTURES, not from
                    # the MULTIFREQ_BY_STRUCTURE literal below: that map is
                    # this file's guess at which arms exist, and it silently
                    # went stale the moment the solver grew an arm it did not
                    # name.  Sorted, because the dict reads A, B (file order)
                    # but a reader looking for an arm scans a list.
                    #
                    # The literal map stays as the FALLBACK, and it is a real
                    # fallback and not a formality: _structure_registry()
                    # returns {} whenever the solver file cannot be read, and a
                    # picker with no items is a column with no way to choose.
                    v_bind_items=repr(sorted(_structure_registry())
                                      or list(MULTIFREQ_BY_STRUCTURE)),
                    label="Structure",
                    density="compact",
                    hide_details=True,
                    classes="mb-1",
                )

        def _mesh_and_geometry() -> None:
            # The old max-width/margin styles are gone: inside a card the
            # controls take the card's width, and `mb-1` restores the vertical
            # rhythm the old single-row margins provided.
            solve_xcut_field = getattr(widgets_module, "VTextField", None)
            if solve_xcut_field is not None:
                solve_xcut_field(
                    v_model=("solve_xcut_mm", SOLVE_DEFAULT_XCUT_MM),
                    label="Cut plane x [mm]",
                    type="number",
                    density="compact",
                    hide_details=True,
                    classes="mb-1",
                )
            # The Mode control sits HERE and not in Action: it does not solve
            # the structure, it redraws the cross-section of the page already on
            # screen. Its label is bound, so the button itself says whether the
            # panel is unsolved, solved or refused.
            if "VBtn" in widgets:
                widgets["VBtn"](
                    "{{ mode_view_label }}",
                    click=ctrl.mode_view_toggle,
                )
            solve_arm_field = getattr(widgets_module, "VSelect", None)
            if solve_arm_field is not None:
                # PLACEHOLDER, and disabled is the honest state: the solve takes
                # its mesh from the study record, there is no auto-meshing to
                # configure yet, and a live selector here would imply a setting
                # that changes nothing. It marks where the control will live
                # without pretending it works - hence no handler and the
                # throwaway state name.
                solve_arm_field(
                    v_model=("mesh_size_placeholder", "fixed (0.5 mm)"),
                    # Same trap: a one-element list emits `:items="fixed (0.5 mm)"`,
                    # which is not JavaScript at all. Bind the literal instead.
                    v_bind_items="['fixed (0.5 mm)']",
                    label="Mesh size",
                    density="compact",
                    hide_details=True,
                    disabled=True,
                    classes="mb-1",
                )

        def _action() -> None:
            if "VBtn" in widgets:
                # Full width and large: this is the one control that starts a
                # multi-second job, so it is the one that should read as the
                # primary action of the column.
                widgets["VBtn"](
                    "{{ solve_label }}",
                    click=ctrl.solve_start,
                    # BOUND, not a literal: the label and the enabled state are
                    # ONE decision (state.solve_disabled is set from the page
                    # beside the label), so a literal here could show "Solve"
                    # on a page the state beside it says is not solvable.
                    disabled=("solve_disabled", False),
                    size="large",
                    style="width: 100%;",
                )
            if "VLabel" in widgets:
                widgets["VLabel"]("{{ solve_status }}")

        # The SOLVE form, in its OWN guarded block: a binding failure here costs
        # the solve form, never play/pause or the S-Parameters panel.
        try:
            _section("Project", _project, first=True)
            _section("Mesh & Geometry", _mesh_and_geometry)
            _section("Circuit", _emit_circuit_netlist)
            _section("Action", _action)
        except Exception as exc:  # noqa: BLE001 - solve UI is optional
            print(
                f"[poc_app] solve controls unavailable: {exc}",
                file=sys.stderr,
            )
            if "VLabel" in widgets:
                widgets["VLabel"]("solve unavailable (binding failed)")

    def _emit_s_params_panel() -> None:
        """Emit the |S11| / |S21| panel inside its TAB, caption first.

        Everything inside is bound to state. The TAB owns visibility, so there is
        no visibility wrapper and no style string here: a tab that is not
        selected hides this content without a widget being created or destroyed,
        and the payload it shows was pushed by ``_load_s_params_panel`` before
        the tabs were built.
        """
        if html_div is None:
            return
        html_div(
            "S-Parameters",
            style="font-size: 12px; font-weight: 600; padding: 2px 0;",
        )
        # No sweep is an ANSWER, and the tab is offered on every page now
        # (``um3k_panels.RIGHT_TABS``), so the arm with no sweep registered is
        # exactly the arm that has to read this line: without it the panel
        # opened onto a blank number, an empty image and rows that do not
        # exist. The caption below still names the arm and every path that was
        # looked for, so the one-line refusal does not replace the detail.
        if (handles.get("s_params") or {}).get("path") is None:
            html_div(
                "No sweep file found",
                style="font-size: 11px; color: #333; padding: 2px 0;",
            )
            html_div(
                "{{ s_params_caption }}",
                style="font-size: 11px; color: #333; padding: 2px 0;",
            )
            return
        html_div(
            "{{ s_params_number }}",
            style="font-size: 12px; padding: 2px 0;",
        )
        html_div(
            "{{ s_params_caption }}",
            style="font-size: 11px; color: #333; padding: 2px 0;",
        )
        img_cls = getattr(html_widgets, "Img", None)
        if img_cls is not None:
            img_cls(
                src=("s_params_image", ""),
                style=("s_params_image_style", "display: none;"),
            )
        pre_cls = getattr(html_widgets, "Pre", None)
        if pre_cls is not None:
            pre_cls(
                "{{ s_params_rows }}",
                style=("s_params_rows_style", "display: none;"),
            )

    def _emit_far_field_panel() -> None:
        """Emit the far-field pattern inside its TAB, number first.

        Same shape as ``_emit_s_params_panel``: everything inside is bound to
        state, the TAB owns visibility (so no wrapper and no style string), and
        the payload was pushed by ``_load_far_field_panel`` before the tabs were
        built. The number line comes first because it is the sentence a reader
        keeps - peak directivity and the frequency it was taken at - while the
        caption says WHICH archive it came from, or why there is no picture.
        """
        if html_div is None:
            return
        html_div(
            "Far Field",
            style="font-size: 12px; font-weight: 600; padding: 2px 0;",
        )
        html_div(
            "{{ far_field_number }}",
            style="font-size: 12px; padding: 2px 0;",
        )
        html_div(
            "{{ far_field_caption }}",
            style="font-size: 11px; color: #333; padding: 2px 0;",
        )
        img_cls = getattr(html_widgets, "Img", None)
        if img_cls is not None:
            img_cls(
                src=("far_field_image", ""),
                style=("far_field_image_style", "display: none;"),
            )
        pre_cls = getattr(html_widgets, "Pre", None)
        if pre_cls is not None:
            pre_cls(
                "{{ far_field_rows }}",
                style=("far_field_rows_style", "display: none;"),
            )

    def _emit_confidence_panel() -> None:
        """Emit the Confidence & Accuracy panel as TEXT inside its TAB.

        Bound to state throughout. The TAB owns visibility, so there is no
        wrapper and no style string here. The rows are pre-wrapped monospace:
        they are a table of prose, and none of them is a picture.
        """
        if html_div is None:
            return
        html_div(
            "Confidence N-lambda",
            style="font-size: 12px; font-weight: 600; padding: 2px 0;",
        )
        html_div(
            "{{ confidence_caption }}",
            style="font-size: 11px; color: #333; padding: 2px 0;",
        )
        pre_cls = getattr(html_widgets, "Pre", None)
        if pre_cls is not None:
            pre_cls(
                "{{ confidence_rows }}",
                style=(
                    "font-size: 10px; white-space: pre-wrap; "
                    "margin: 4px 0;"
                ),
            )

    async def _play_loop(gen: int) -> None:
        """Advance one frame per wall-clock step until the trigger bumps the
        generation or state.playing is cleared.

        Runs as a background task. It must NOT be awaited from a trigger
        handler: see _on_play_toggle.
        """
        while int(handles.get("generation", 0)) == gen and state.playing:
            frames = nt if state.mode == "ycut" else nt_x
            handles["suppress_frame_listener"] = True
            try:
                _show((int(state.frame) + 1) % frames, state.mode)
                state.flush()
            finally:
                handles["suppress_frame_listener"] = False
            await asyncio.sleep(1.0 / fps)

    @ctrl.set("play_toggle")
    async def _on_play_toggle(**_kwargs) -> None:
        """Start or stop playback. Returns immediately.

        The trigger handler MUST return. An async trigger that awaits
        forever - which is what the previous while-loop-in-handler was -
        leaves the client RPC unresolved: the pause button never reaches
        the server, no other button reaches the server, and camera drags
        stop being processed. The animation still runs (the loop is inside
        the pending RPC and flushes per tick), which is what makes this
        bug look like "the controls are dead but the picture is fine".
        The play loop is scheduled with asyncio.create_task instead; the
        generation counter stops it on the second press.
        """
        generation = int(handles.get("generation", 0)) + 1
        handles["generation"] = generation
        if state.playing:
            state.playing = False
            state.play_label = "play"
            state.flush()
            return
        state.playing = True
        state.play_label = "pause"
        state.flush()
        asyncio.create_task(_play_loop(generation))

    # REGISTERED WITH @ctrl.trigger, NOT @ctrl.set. The buttons are @ctrl.set
    # controller METHODS; the trame protocol resolves what the browser calls via
    # controller.trigger_fn(name), which only knows the names @ctrl.trigger put
    # in `_triggers` (plus the auto `trigger__N` names minted for a
    # ControllerFunction handed to a widget). A @ctrl.set name is not in that
    # table, so `trame.trigger('play_toggle', ...)` finds `fn = None`, logs
    # "Trigger %s seems to be missing" and returns None - a silent no-op, not an
    # error. This name has to be a real trigger for the keyboard to reach the
    # server at all.
    @ctrl.trigger("kbd_shortcut")
    async def _on_kbd_shortcut(key=None, **_kwargs) -> None:
        """Dispatch ONE keyboard shortcut to the handler the button uses.

        The wire contract, pinned by the tests: the browser calls
        ``window.trame.trigger("kbd_shortcut", [event.key], {})``, the protocol
        does ``fn(*args)``, so ``key`` arrives positionally and is
        ``event.key``. The mapping below calls the button closures directly
        rather than duplicating their bodies, so a shortcut cannot drift from
        its button. The play handler is async, which is why this one is too
        (the protocol awaits an awaitable result).

        An unknown or missing key is a silent no-op: a client on a different
        keyboard layout must never be able to raise inside an RPC.
        """
        action = {" ": "play", "ArrowLeft": "back", "ArrowRight": "fwd"}.get(
            key if isinstance(key, str) else ""
        )
        if action == "play":
            await _on_play_toggle()
        elif action == "back":
            _on_step_back()
        elif action == "fwd":
            _on_step_fwd()

    # ---- the SOLVE control --------------------------------------------------
    # A solve is a CHILD PROCESS (see SolveJob): the page keeps drawing while it
    # runs and the only thing that crosses back is the npz it leaves behind.
    # ONE at a time, because two would write the SAME live dump.
    default_arm = _structure_key(info.get("structure_id")) or next(
        iter(MULTIFREQ_BY_STRUCTURE)
    )
    state.solve_structure = default_arm
    state.solve_xcut_mm = SOLVE_DEFAULT_XCUT_MM
    state.solve_status = "no solve run in this session"
    # The LABEL and the ENABLED state describe the PAGE, not the job: this shell
    # serves a static field snapshot as well as an animation dump, and the static
    # page (nt is None - no frame axis, um3k_panels.py:127-140) has no timeline
    # for a new run to land in. A bare "Solve" over a snapshot read as "solve
    # THIS page", which nothing here does; so the label NAMES the page it is
    # drawn on ("Solve (static field snapshot)" over a snapshot, "Solve" over an
    # animation dump) and the grey-out is there so nobody reads the button as
    # "press this to refresh the picture" - the press starts a new run, it does
    # not re-read the file this page was opened from. The machinery is not
    # missing; it just does not do that.
    static_page = nt is None
    state.solve_label = (
        "Solve (static field snapshot)" if static_page else "Solve"
    )
    state.solve_disabled = static_page
    if static_page:
        state.solve_status = (
            "this page is a static field snapshot; Solve runs a new solve and "
            "does not refresh this view"
        )
    # The netlist a solve may be run on, as JSON TEXT. It lives in the state so
    # the editor in the solve panel binds it the usual way
    # (v_model=("solve_netlist_json", "")) and the button reads it from here;
    # empty means "solve the built-in resistor study".
    state.solve_netlist_json = ""
    solve: dict = {}

    async def _watch_solve() -> None:
        """THE poll driver: the ONE thing that watches the job and lands it.

        It rides the server's own event loop, the same mechanism _play_loop uses.
        There is deliberately no timer branch: this trame exposes no timer
        widget, so a second driver could never run.

        It exits as soon as the job has a VERDICT, and exits on the first check
        when there is no job at all - it cannot poll forever.

        "idle" is not a verdict: the worker thread may not have entered run()
        yet when the task first gets the loop, and treating that instant as
        "finished" reported ``solve idle (rc=None)`` for a solve that was just
        starting. The thread always leaves "idle" (run() sets the status), so
        waiting on it cannot spin forever.
        """
        while True:
            job = solve.get("job")
            if job is None or job.status not in ("idle", "running"):
                break
            await asyncio.sleep(0.5)
        _poll_solve()

    def _start_watch() -> None:
        """Start the ONE poll driver on the loop this trigger is running on."""
        try:
            asyncio.get_running_loop().create_task(_watch_solve())
        except RuntimeError as exc:  # noqa: BLE001 - no loop, nothing to drive it
            print(
                f"[poc_app] solve result not picked up ({exc}): reopen the page "
                "to see it",
                file=sys.stderr,
            )

    def _poll_solve() -> None:
        """Watcher callback: watch the ONE job and, when it lands, show it.

        Runs on the server's own event loop, so the page swap below is the same
        thread that draws every frame - a browser that asks for frame n while
        the solve is running keeps getting the OLD page, and never a half-built
        one.
        """
        job = solve.get("job")
        if job is None:
            return
        status = job.poll()
        if status in ("idle", "running"):
            # "idle" is a child that has not been spawned yet, not a failure.
            state.solve_status = (
                f"solving {state.solve_structure} at x_cut = "
                f"{float(state.solve_xcut_mm):g} mm ..."
            )
            return
        if status != "ok":
            # The OLD page stays live and drawable: a failed solve is a message,
            # not a broken viewer.
            state.solve_status = (
                f"solve {status} (rc={job.returncode}) - the page on screen is "
                f"still the previous dump\n{job.log[-400:]}"
            )
            return
        try:
            applied = apply_page(page, reload_page(LIVE_DUMP))
        except BaseException as exc:  # noqa: BLE001 - SystemExit is a refusal
            state.solve_status = f"solve ok, but the new dump did not load: {exc}"
            print(f"[poc_app] solved dump not loaded: {exc}", file=sys.stderr)
            return
        # Both panels read the OLD page's arm: drop the caches so the refill
        # below re-reads the sweep and the record that belong to the dump now on
        # screen.
        handles.pop("s_params", None)
        handles.pop("confidence", None)
        # The far field does not read this page, but it is dropped and refilled
        # with the two above all the same: one rule for the tab payloads is what
        # keeps a reader from having to know which cache is page-scoped, and a
        # refill costs one cached report per solve, not one per frame.
        handles.pop("far_field", None)
        # Refill them HERE, not "on the next open": the tabs own visibility now,
        # so no button triggers a rebuild any more - without this the tabs would
        # keep the previous page's caption and rows for good. Both loaders
        # swallow their own failures (stderr only), so no guard is needed here.
        _load_s_params_panel()
        _load_far_field_panel()
        _load_confidence_panel()
        _rebuild_sheets()
        # WHAT a reader must do next is part of the sentence: the swap reaches
        # the page's own arrays and labels, but the browser's picture and the
        # dump line still describe the page the reader opened, so "solved" alone
        # read as "this view is now the new run" when it was not.
        state.solve_status = (
            f"solved -> {Path(applied['new_path']).name}; this page was NOT "
            "refreshed - reload it to view the new dump"
        )

    def _drop_netlist(netlist_path) -> None:
        """Delete one run's netlist FILE. Never raises: the run is over anyway.

        Called from a ``finally``, so a clean exit, a crashed child and a start
        that never happened all leave the artefacts directory equally tidy - one
        file per click would otherwise pile up unseen.
        """
        if netlist_path is None:
            return
        try:
            Path(netlist_path).unlink()
        except OSError as exc:
            print(f"[poc_app] netlist not removed: {exc}", file=sys.stderr)

    def _run_job(job, netlist_path=None) -> None:
        """Worker thread: run the solve to completion, never raising."""
        try:
            job.run()
        except BaseException as exc:  # noqa: BLE001 - a dead spawn is a failure
            print(f"[poc_app] solve could not start: {exc}", file=sys.stderr)
            job.status = "failed"
            job.returncode = None
        finally:
            # The child has exited (or never started), so the netlist file has
            # been read for the last time.
            _drop_netlist(netlist_path)

    @ctrl.set("solve_start")
    def _on_solve_start(netlist_json="", **_kwargs) -> None:
        """Start a solve and return IMMEDIATELY. The watcher brings it back.

        ``netlist_json`` is the netlist as JSON TEXT; empty (the default, and
        what an ordinary press gives) solves the built-in resistor study.  An
        explicit keyword wins, otherwise the text comes from the page's own
        slot, ``state.solve_netlist_json``.

        A STATIC page refuses HERE, before anything is spawned or written: the
        page has no timeline for a new run to land in, so a press either did
        nothing visible or replaced the dump under a page that cannot read it.
        The button is greyed out for the same reason (state.solve_disabled);
        this is the same refusal for a press that arrives anyway - a stale
        browser, or a caller driving the trigger directly.
        """
        if static_page:
            print(
                "[poc_app] solve refused: this page is a static field snapshot "
                "(no timeline), so nothing was spawned and no dump was written",
                file=sys.stderr,
            )
            state.solve_status = (
                "solve refused: this page is a static field snapshot, which has "
                "no timeline for a new run to land in - open an animation dump "
                "to solve, then reload the page to view the result"
            )
            return
        running = solve.get("job")
        if running is not None and running.status == "running":
            state.solve_status = "a solve is already running - one at a time"
            return
        structure = str(state.solve_structure or default_arm)
        try:
            xcut_mm = float(state.solve_xcut_mm)
        except (TypeError, ValueError):
            xcut_mm = SOLVE_DEFAULT_XCUT_MM
        netlist_text = str(
            netlist_json or getattr(state, "solve_netlist_json", "") or ""
        )
        # A refused netlist raises HERE, before solve_argv has written anything,
        # so a bad edit costs a message and no file and no child process.
        try:
            argv = solve_argv(
                structure, xcut_mm, LIVE_DUMP, netlist_json=netlist_text
            )
        except (ValueError, OSError) as exc:
            state.solve_status = f"refused: {exc}"
            return
        # From here a netlist file exists on disk; the worker thread's finally
        # removes it once the child is gone, and this frame's cleanup removes it
        # if the job never gets started at all.
        netlist_path = solve_netlist_file(argv)
        try:
            LIVE_DUMP.parent.mkdir(parents=True, exist_ok=True)
            job = SolveJob(argv)
            threading.Thread(
                target=_run_job,
                args=(job, netlist_path),
                daemon=True,
                name="poc-solve",
            ).start()
        except Exception as exc:  # noqa: BLE001 - report, never take the page
            _drop_netlist(netlist_path)
            state.solve_status = f"could not start the solver: {exc}"
            print(f"[poc_app] solve not started: {exc}", file=sys.stderr)
            return
        solve["job"] = job
        state.solve_status = (
            f"solving {structure} at x_cut = {xcut_mm:g} mm -> "
            f"{LIVE_DUMP.name}"
        )
        _start_watch()

    def _emit_mode_caption() -> None:
        """The Mode panel's ONE caption line - the hint, the numbers or a refusal.

        Emitted from both places this panel has ever appeared (its Modes tab and
        the flat fallback stack, which is what a build without the optional tab
        widgets gets), because those two used to spell the same ``html_div`` call
        out twice and a panel that changes in one place and not the other is two
        panels. Nothing here decides the text: ``mode_view_caption`` is set by the
        module helpers, so boot, press and refresh stay one rule.
        """
        if html_div is None:
            # html_div is optional; VLabel is the same degraded row the rest of
            # this page falls back to. Neither means the caption is simply
            # absent - the press's own picture still carries the result.
            label_cls = widgets.get("VLabel")
            if label_cls is not None:
                label_cls(
                    "{{ mode_view_caption }}",
                    style="font-size: 11px; color: #333; padding: 2px 0;",
                )
            return
        html_div(
            "{{ mode_view_caption }}",
            style="font-size: 11px; color: #333; padding: 2px 0;",
        )

    def _emit_mode_picker() -> None:
        """The candidate picker: ONE VSelect over the solve's OWN candidates.

        WHY a picker at all: the pencil keeps several transverse candidates and
        picks one by the curl/eps guard, so a panel that shows only the pick hides
        the fact that the others exist. The rows are the compute layer's own
        records and their labels repeat its numbers verbatim - including "At
        cutoff" and "Evanescent ... Np/m" for the candidates the guard can never
        choose - so the picker extends the panel's honesty rather than softening
        it.

        The items live in ``mode_choice_items`` and are filled by a PRESS, not
        here: the layout is built once at boot, before anything is solved. A
        build with no VSelect simply gets the caption and the press's own
        picture, which is the whole panel minus the picking.
        """
        # Probed HERE rather than borrowed: run_web has its own select_cls, but
        # this entry point resolves its widgets from the probe above and never
        # defined that name, so reaching for it would be a NameError at build
        # time - on the page a VSelect-less variant is supposed to survive.
        select_cls = getattr(widgets_module, "VSelect", None)
        if select_cls is None:
            # Loud, like every sibling probe: a variant without VSelect is
            # supposed to survive the picker's absence, not hide it. Silence
            # here is how a page loses the picker and nobody notices.
            print(
                "[poc_app] mode picker unavailable: this build has no VSelect",
                file=sys.stderr,
            )
            return
        try:
            select_cls(
                v_model=("mode_choice", 0),
                # Same binding idiom as the structure picker: a
                # (state_name, default) TUPLE is how trame is told to emit a
                # state NAME where JavaScript belongs, so the value crosses as
                # JSON and a dict's title/value need no quoting from Python.
                v_bind_items=("mode_choice_items", []),
                item_title="title",
                item_text="title",
                item_value="value",
                label="solved candidates",
                hide_details=True,
                style="max-width: 460px; padding: 2px 0;",
            )
        except Exception as exc:  # noqa: BLE001 - a picker is never the page
            print(f"[poc_app] mode picker unavailable: {exc}", file=sys.stderr)

    def _emit_vector_toggle() -> None:
        """The overlay toggles: the arrow field and the two marker planes.

        WHY a checkbox and not a second picture: the arrows are an OVERLAY on
        the cross-section already on screen, so the control is a yes/no about
        that overlay and not a third view to choose between. It is OFF at boot,
        so a browser that never touches it sees precisely the picture the panel
        had before the overlay existed.

        WHY the two plane boxes ride along here: they are the same kind of
        control over the same plotter - a yes/no about a marker that redraws
        the scene - so they are emitted by the same entry point rather than by
        a second one that would have to be registered and called everywhere
        this one already is. BOTH are ON at boot (the red load plane and the
        purple S11 port plane are what the scene has always drawn once the
        marker layer existed), so a page that never touches them is unchanged.
        They are emitted only where a redraw is bound (``cut_redraw``): a page
        with no plane stack has no plane to hide, and a box that hid nothing
        would be a control lying about the picture.

        Probed HERE, for the picker's own reason: this entry point resolves its
        widgets from the probe above rather than borrowing run_web's names, and
        a build without VCheckbox is supposed to lose the TOGGLE, not the panel.
        So it says so loudly and returns instead of reaching for a class that is
        not there.
        """
        checkbox_cls = getattr(widgets_module, "VCheckbox", None)
        if checkbox_cls is None:
            # Loud, like every sibling probe: a variant without VCheckbox is
            # supposed to survive the toggle's absence, not hide it.
            print(
                "[poc_app] vector field toggle unavailable: this build has no "
                "VCheckbox",
                file=sys.stderr,
            )
            return
        try:
            checkbox_cls(
                # A (state_name, default) tuple, the picker's own binding idiom:
                # trame turns it into the state NAME, so the browser writes
                # ``show_quiver`` and the @state.change handler above - not a
                # v_model - decides what a change means.
                v_model=("show_quiver", False),
                label="Show Vector Field",
                hide_details=True,
                style="padding: 2px 0;",
            )
        except Exception as exc:  # noqa: BLE001 - a toggle is never the page
            print(
                f"[poc_app] vector field toggle unavailable: {exc}", file=sys.stderr
            )
        if not callable(handles.get("cut_redraw")):
            return
        for plane_state, plane_label in (
            ("show_load_plane", "Show Load Plane (red)"),
            ("show_port_plane", "Show S11 Port Plane (purple)"),
        ):
            try:
                checkbox_cls(
                    # The same (state_name, default) binding as the box above:
                    # the browser writes the flag and the @state.change
                    # handlers decide what a change means.
                    v_model=(plane_state, True),
                    label=plane_label,
                    hide_details=True,
                    style="padding: 2px 0;",
                )
            except Exception as exc:  # noqa: BLE001 - a toggle is never the page
                print(
                    f"[poc_app] plane toggles unavailable: {exc}", file=sys.stderr
                )
        # The two discs are MARKERS, not field slices, and the boxes above are
        # where the page has to say so: a reader who takes the planes for two
        # more cross-sections reads the localized field as a broken one.
        if html_div is None:
            return
        try:
            html_div(
                "Note: Port and Load planes are X-markers. The 3D field is "
                "localized to the microstrip.",
                style="font-size: 10px; color: #555; padding: 2px 0 0 0;",
            )
        except Exception as exc:  # noqa: BLE001 - a note is never the page
            print(f"[poc_app] plane note unavailable: {exc}", file=sys.stderr)

    def _emit_station_readout() -> None:
        """The station sentence as SHELL TEXT, inside the cut row.

        WHY not in the picture: ``_station_text`` used to reach the scene through
        a VTK corner annotation, whose font is scaled against the render window,
        so on a wide page it covered the cross-section instead of captioning it.
        This page now draws the scene WITHOUT it (``_redraw``, :7648) and says
        the same sentence once, here, in the column whose sliders move the
        station - a div of ordinary page text the browser sizes with every other
        line.

        Emitted only where it has a value: ``state.station_readout`` is published
        behind the same ``plane_stack`` gate the cut row sits behind (:7625), and
        the centre column calls this from inside that gate
        (server/um3k_panels.py:58), so a page with no station axis never reaches
        it. A layout failure loses the LINE, never the page.
        """
        try:
            html_div(
                "{{ station_readout }}",
                style="padding: 2px 12px; font-size: 13px;",
            )
        except Exception as exc:  # noqa: BLE001 - a caption is never the page
            print(f"[poc_app] station readout not emitted: {exc}", file=sys.stderr)

    with SinglePageLayout(server) as layout:
        # The header is the second place the page title lives, so it is written
        # from the same helper as the browser title and re-pointed from now on
        # by _set_picture_title(): the header must describe the picture on
        # screen - the |Ez| animation, or a solved |E_t| mode cross-section -
        # rather than assume the animation for the life of the server.
        handles["title_setter"] = layout.title.set_text
        layout.title.set_text(_animation_title_text(structure_label))
        with layout.content:
            container = widgets.get("VContainer")
            if container is None or html_div is None:
                # No container or no html widgets: the plotter keeps the whole
                # content area. The player bar needs VRow, which is html
                # widgets, so on this degraded path the picture and the solve
                # controls are all there is - the toolbar that used to hold
                # the buttons is gone.
                view = plotter_ui(plotter, mode="server", add_menu=False)
                _emit_solve_controls()
            else:
                with container(fluid=True, classes="pa-0 fill-height"):
                    with html_div(
                        style=(
                            "display: flex; flex-direction: column; "
                            "height: 100vh; width: 100%; overflow: hidden;"
                        )
                    ):
                        # Three columns, left to right: SETUP (solve controls),
                        # VIEW (the 3-D picture with its player bar underneath)
                        # and DATA (readout strip, then the tabbed panels).
                        # The row claims the height the parent column leaves
                        # over: without flex here it took only its min-height
                        # and the picture never filled the page.
                        #
                        # THE SEAM: the builders below reach the page through
                        # `ctx`, so what they may call is registered here, at
                        # the layout that will use it. It has to be before the
                        # row opens - a builder is called from inside its own
                        # column, and the callable must already be there.
                        ctx.register("_emit_solve_controls", _emit_solve_controls)
                        ctx.register_handle("widgets", widgets)
                        ctx.register_handle("ctrl", ctrl)
                        ctx.register_handle("nt", nt)
                        ctx.register_handle("plotter", plotter)
                        ctx.register("html_div", html_div)
                        ctx.register("VRow", VRow)
                        ctx.register("plotter_ui", plotter_ui)
                        # The centre column's cut row (server/um3k_panels.py:
                        # build_center_panel): run_web's own emitter, plus the
                        # three of its arguments that are not already on `ctx`.
                        ctx.register("_emit_cut_sliders", _emit_cut_sliders)
                        # The station sentence that row carries, for the same
                        # reason and behind the same gate (see the emitter).
                        ctx.register("_emit_station_readout", _emit_station_readout)
                        ctx.register_handle("state", state)
                        ctx.register_handle("missing_widgets", missing_widgets)
                        # The DATA column's two page objects and its 11
                        # emitters/loaders, registered here because the column
                        # now reaches them through `ctx`.
                        ctx.register_handle("widgets_module", widgets_module)
                        ctx.register_handle("info", info)
                        ctx.register("_load_s_params_panel", _load_s_params_panel)
                        ctx.register("_load_far_field_panel", _load_far_field_panel)
                        ctx.register("_load_confidence_panel", _load_confidence_panel)
                        ctx.register("_emit_s_params_panel", _emit_s_params_panel)
                        ctx.register("_emit_far_field_panel", _emit_far_field_panel)
                        ctx.register("_emit_confidence_panel", _emit_confidence_panel)
                        ctx.register("_emit_mode_caption", _emit_mode_caption)
                        ctx.register("_emit_mode_picker", _emit_mode_picker)
                        ctx.register("_emit_vector_toggle", _emit_vector_toggle)
                        ctx.register("_emit_circuit_netlist", _emit_circuit_netlist)
                        ctx.register("_emit_load_series_panel", _emit_load_series_panel)
                        with VRow(
                            style=(
                                "flex: 1 1 auto; align-items: stretch; "
                                "min-height: 0; height: 100%; margin: 0; "
                                "width: 100%; "
                                "overflow: hidden;"
                            )
                        ):
                            with VCol(
                                style=(
                                    "flex: 0 0 230px; min-width: 200px; "
                                    "max-width: 280px; min-height: 0; "
                                    "overflow-y: auto; padding: 8px; "
                                    "border-right: 1px solid #dcdcdc"
                                )
                            ):
                                # SETUP: the solve controls, unchanged, out of
                                # the toolbar and into their own column.
                                build_left_panel(ctx)
                            with VCol(
                                style=(
                                    "flex: 1 1 0; min-width: 240px; "
                                    "min-height: 0; height: 100%;"
                                )
                            ):
                                view = build_center_panel(ctx)
                            with VCol(
                                style=(
                                    "flex: 0 1 380px; min-width: 300px; "
                                    "max-width: 460px; min-height: 0; "
                                    "overflow-y: auto; padding: 8px; "
                                    "border-left: 1px solid #dcdcdc"
                                )
                            ):
                                build_right_panel(ctx)

    handles["view"] = view

    if nt is None or nt_x is None:
        # The shell: no timeline, so there is no rate and no stride to report.
        print(
            "[poc_app] no timeline on this page: it records no frame axis, so "
            "the player bar and its scrubber are not built"
        )
    else:
        print(
            f"[poc_app] animation: {nt} frames on ez_ycut, {nt_x} on each x-cut, "
            f"played at {fps} fps (a VIEWING rate - see the sim time readout)"
        )
        print(
            "[poc_app] each frame's sim time is rebuilt from its own plane's "
            "frame index: the x-cuts are written every "
            f"{int(info['dump_stride']) * 10} steps"
        )
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
            "PoC Trame + pyvista viewer for a microstrip field dump and its "
            "S-parameter records. The structure is selected from "
            f"{STRUCTURES_FILE}; the captured x-planes are stacked at one cell "
            "spacing, so x is quantised to those positions."
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
        default=None,
        help=(
            "npz dump to read; wins over --structure when given (default: the "
            "selected structure's field_dump.path, else "
            f"{DEFAULT_INPUT})"
        ),
    )
    # The Huygens archive the Far Field tab integrates, and NOT a viewer input.
    # It never reaches load_any_dump (whose refusal of a surface archive as a
    # plane dump is deliberate and stays byte-identical), it is not read by
    # --list-keys, and it is NOT part of the --dump-state JSON - build_state_dump
    # is deliberately not given it - because that document describes the ONE
    # dump a page shows, while this is a second artefact that only feeds a tab.
    parser.add_argument(
        "--surface-dump",
        dest="surface_dump",
        metavar="PATH",
        default=None,
        help=(
            "Huygens surface archive (npz schema "
            '"emfit.surface-dump/1", emfit.ntff.SURFACE_DUMP_SCHEMA) whose '
            "far field the Far Field tab draws; a SEPARATE input from the dump "
            "the page animates (default: none - the tab then says so)"
        ),
    )
    parser.add_argument(
        "--structure",
        default=DEFAULT_STRUCTURE,
        help=(
            "structure id from "
            f"{STRUCTURES_FILE} (default: {DEFAULT_STRUCTURE})"
        ),
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
        "--dump-state",
        dest="dump_state",
        metavar="PATH",
        default=None,
        help=(
            "write a JSON snapshot of everything the viewer knows and exit "
            "(numpy only, no pyvista, no trame)"
        ),
    )
    parser.add_argument(
        "--station", type=int, default=4, help="initial station index (default: 4)"
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help=(
            "frames per second for the wave animation (default: "
            f"{DEFAULT_FPS}); applies to a {VIS_SCHEMA} dump only - "
            "a legacy station dump has no time axis and ignores it"
        ),
    )
    args = parser.parse_args(argv)

    structures = load_structures()
    structure = _structure_by_id(args.structure, structures)
    if structure is None:
        valid = ", ".join(
            str(entry.get("id")) for entry in structures if entry.get("id")
        )
        parser.error(
            f"unknown --structure {args.structure}; "
            f"valid ids: {valid or 'none (structures.json unreadable)'}"
        )

    # A record-only entry is REFUSED, never substituted: its S-parameters were
    # recorded without a field solve, and the only field data on disk belongs to
    # a different case. The check is on the resolved entry, so it covers
    # --structure OMITTED as well as given - args.structure is DEFAULT_STRUCTURE
    # there, so if the default itself had no dump this same branch would fire on
    # it, with the same message and the same exit status, rather than rendering
    # run A under the default's name. It runs before load_dump, so a refusal
    # reads nothing and writes no half-finished state file.
    if _structure_is_record_only(structure):
        parser.error(_record_only_refusal(args.structure, structures))

    # --input wins when given, then the entry's own dump, then the default - see
    # _structure_input_path. The registry never overrides an explicit path, so a
    # run that is not registered yet can still be opened.
    src = _structure_input_path(args.input, structure)
    # Dispatch on the npz schema, so one entry point opens either artefact - and
    # through the SAME call a reload uses, so boot and reload cannot load a dump
    # two different ways. Everything below still reads ``info`` exactly as it
    # did before.
    page = reload_page(src)
    info = page["info"]

    if args.dump_state:
        out = _resolve(args.dump_state)
        state = build_state_dump(info, structure, structures, fps=args.fps)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"[poc_app] wrote {out}")
        return 0

    # ONE shell for whichever artefact this turned out to be: the page above was
    # built by the same reload a browser reload uses, and the shell asks the
    # page's own context (``ctx.available``) for the machinery it needs - a field
    # dump stacks stations, an animation dump carries frames - so there is no
    # second viewer below to keep in step with this one, and no fork that can
    # hand an artefact the other artefact's page.
    #
    # ``--station`` therefore no longer selects the entry point: a station is a
    # per-page index the page itself decides (the shell starts a field page on
    # the middle captured plane), not a floodgate in front of it.
    if args.list_keys:
        print_keys(info)
        return 0

    return run_web_vis(
        info,
        args.host,
        args.port,
        args.fps,
        structure,
        structures,
        # Only ever a PATH here: the far-field reader resolves nothing and
        # must not be handed a bare relative string from a different cwd.
        surface_dump=(_resolve(args.surface_dump) if args.surface_dump else None),
        loaded_page=page,
    )


if __name__ == "__main__":
    sys.exit(main())
