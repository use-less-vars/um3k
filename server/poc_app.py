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
import json
import math
import os
import re
import socket
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import time

import numpy as np

# The um3k modules are siblings in server/, which has no __init__.py: script
# form (`python3 server/poc_app.py`) puts server/ on sys.path so the bare names
# resolve; package form (`import server.poc_app` or `-m server.poc_app`) has no
# such entry and needs the relative form. Both hold state and layout only.
try:
    import step_time as _step_time
    import timeline as _timeline
    import um3k_context
    from um3k_panels import build_center_panel, build_left_panel, build_right_panel
except ModuleNotFoundError as exc:
    # Narrow, on purpose: only OUR two names may be re-routed. A dependency
    # missing inside them must surface as itself, not as a relative import.
    if exc.name not in ("step_time", "timeline", "um3k_context", "um3k_panels"):
        raise
    from . import step_time as _step_time
    from . import timeline as _timeline
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
# ... and the entry a BARE invocation boots on, so the first screen has a volume
# and a timeline on it rather than an empty page: the example volume the registry
# publishes under artifacts/. It is a PREFERENCE, not a promise - the entry is
# only usable while that one-time release artefact is on disk, so
# _boot_structure_id falls back to DEFAULT_STRUCTURE, out loud, when it is not.
PREFERRED_STRUCTURE = "reference_sim"
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
# Positions a PLAYING player advances per tick: the values the player bar's speed
# control offers, and the one it starts on. The timeline is the SOLVER STEP clock
# of the selected family (2400 y-cut positions, 240 x-cut ones), and one position
# is dt*c = 7.626299478123987e-13 s * 2.998e8 m/s ~ 0.229 mm, i.e. about ONE half
# of the 0.4 mm cell - so at rate 1 the wave moves one half-cell per tick and a
# 2400-position family takes 100 s at 24 fps, a strobe. The default 4 positions a
# tick is 4 * 0.229 mm = 0.92 mm ~ 2 cells per tick and 4 * 24 = 96 positions/s,
# i.e. ~25 s per family: legible. A VIEWING choice like DEFAULT_FPS, and - unlike
# DEFAULT_FPS - one the operator can change while watching: somebody following one
# cell fill in wants rate 1, somebody scanning a whole family wants rate 8, and
# neither should have to restart the app at a different constant to get it.
PLAY_RATES = (1, 2, 4, 8)
DEFAULT_PLAY_RATE = 4
# Positions the player advances per PAINTED frame, at the DEFAULT speed - rate 4,
# i.e. DEFAULT_PLAY_RATE above. The speed select scales it AROUND that anchor, not
# around rate 1: rate 8 doubles it, rate 4 leaves it exactly as passed, and rate 1
# divides it by four, floored at one whole position (4 -> 8, 4 -> 4, 4 -> 1).
# The pump is paint driven: a tick that does not repaint the picture advances
# nothing, so one unit of the stride is "one repaint's worth of motion". It exists
# because the two clocks that used to be conflated are not the same clock - the
# solver's step clock (what a position IS) and the display's refresh (what the
# viewer can SEE). At 24 fps and a 96 positions/s viewing rate the loop asked for a
# repaint every 10.4 ms, i.e. faster than trame's image delivery can round-trip a
# still render (a still render plus encode is tens of ms), so most of those asks
# were discarded: the sequence ON SCREEN was neither the speed the caption promised
# nor the width the stride said. Naming the unit "positions per painted frame" puts
# the number where it can be held: the stride times the paint cap IS the viewing
# rate, and --stride at stride 4 reproduces the historical default exactly (4
# positions/tick at 24 fps = 96 positions/s = the old DEFAULT_PLAY_RATE * DEFAULT_FPS).
# A VIEWING choice like DEFAULT_FPS, not a property of the dump.
DEFAULT_PLAY_STRIDE = 4
# How long a PLAYING loop keeps its hands off the timeline after the operator moved
# it. A scrub is not one event but a BURST of them - the frame slider writes
# ``state.frame`` on every mouse move, and the listener draws each of those writes -
# so a loop that published on the next tick would draw over the hand's own picture
# and drag the position back to where the animation was, one still render per move.
# Half a second is longer than the gap between two drag steps, so a drag is held from
# its first move to its last, and short enough that a single press of << PREV / NEXT
# resumes visibly at once. A VIEWING choice, like the two constants above.
SCRUB_HOLD_S = 0.5
# ONE colour ceiling for the whole animation, taken as the MEDIAN of the
# per-frame percentiles of |Ez| across every plane. Frame-local scaling would
# renormalise on each step and make a decaying pulse look like it never decays;
# a single percentile POOLED over the whole clip lets one hot frame dim all the
# others, which is what made a bounced pulse read as black.
COLOR_PERCENTILE = 99.5
# Cell edges ON for the animated field sheets. A smooth-shaded sheet hides the
# grid the field is sampled on, so a coarse dump reads as a continuous picture
# and the eye cannot tell one cell from the interpolation between two of them.
# WHETHER, not WHICH: the colour and width below cannot fix the density this
# switch is now blamed for - on a cut sheet ~212 hairlines read as a MESH laid
# over the field, and no toggle exists yet, so this value is the default only.
# Only the field sheets get this: the overlay boxes are decoration, not data.
VIS_SHOW_EDGES = True
# WHAT that mesh is drawn IN, now that it is on. A near-black cell edge reads as
# a LATTICE over a field: on the light page it competes with the colours the
# reader is being asked to compare against the bar, and swallows the shape of the
# pulse instead of annotating it. A light steel grey sits just off the
# background, so one cell is still clearly separable from the next without the
# grid becoming the picture - the user asked to see WHERE the mesh is, not to
# read the mesh. Only the field sheets take these two: the geometry actors keep
# the default mesh they were tuned for.
VIS_EDGE_COLOR = "#b8c4d0"
VIS_EDGE_WIDTH = 0.4
# How opaque the dielectric slab is drawn, and the ONE number the slider in the
# view panel moves. 0.10, not 0.3: at 0.3 the box read as a PALE SLAB that
# dimmed the ground plane and the field inside the dielectric, not as a casing.
# The slider starts here, so the shipped picture is unchanged.
VIS_SUBSTRATE_OPACITY = 0.10
# The extra dimming the slab gets square-on in the y-cut, as a FRACTION of the
# slider's value rather than an absolute opacity: at the default that is 0.08,
# the number that was there before, and it stays 0.8x whatever the slider is set
# to - an absolute second constant would win over the slider every time that
# family is selected.
VIS_SUBSTRATE_YCUT_SCALE = 0.8

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

    WHY the MEDIAN OF THE PER-FRAME ceilings: a percentile pooled over the whole
    clip is one number for every frame, so the few hot frames set the scale for
    all the rest. On ``vis_dump_1500.npz`` 538 of the 1500 frames carry a p99.5
    above 10 V/m (the record's largest cell is a 149.9 V/m spike at frame 329),
    so the pooled p99.5 came out at 24.81 V/m while the median per-frame ceiling
    was 3.20 and the median per-frame maximum was 4.15 - 97 % of the cells of a
    typical frame then sat in the darkest tenth of the map and the picture read
    as black. The median of the per-frame p99.5 values is still ONE constant for
    the whole animation (nothing rescales while the clip plays, so the decay
    stays visible), but it is decided by the TYPICAL frame instead of by the
    worst one: 3.20 V/m on that dump.

    FRAME BY FRAME, never a stacked copy of the dump: one frame's arrays are
    concatenated at a time, so the cost is O(samples) time and O(one frame)
    memory, and only the per-frame ceilings are kept. A frame that is empty or
    entirely non-finite is skipped - it has no ceiling of its own, and letting it
    contribute one would be a claim about a picture that was never drawn.

    Returns ``(0.0, ceiling, empty)``. |Ez| is a magnitude, so the floor is 0: a
    symmetric -vmax..+vmax clim would spend half the colour map on values this
    array cannot hold.
    """
    frames = []
    for array in arrays:
        block = np.abs(np.asarray(array, dtype=np.float64))
        if block.size == 0:
            continue
        if block.ndim == 0:
            block = block.reshape(1, 1)  # a bare scalar: one frame, one sample
        elif block.ndim == 1:
            block = block.reshape(1, -1)  # no frame axis to walk
        else:
            block = block.reshape(block.shape[0], -1)  # (frame, sample)
        frames.append(block)
    if not frames:
        return 0.0, 1.0, True
    ceilings = []
    for index in range(max(block.shape[0] for block in frames)):
        # The planes need not share a frame count (the x-cuts are recorded on a
        # coarser schedule), so a frame is every plane that HAS one.
        parts = [block[index] for block in frames if index < block.shape[0]]
        parts = [part for part in parts if part.size]
        if not parts:
            continue
        chunk = np.concatenate(parts)
        if not np.any(np.isfinite(chunk)):
            continue  # an all-NaN frame has no ceiling; it must not be one
        value = float(np.nanpercentile(chunk, percentile))
        if np.isfinite(value):
            ceilings.append(value)
    if not ceilings:
        return 0.0, 1.0, True
    ceiling = float(np.median(ceilings))
    if not np.isfinite(ceiling) or ceiling <= 0.0:
        # An all-zero (or non-finite) cube has no scale of its own. 1.0 keeps a
        # degenerate range away from VTK, and the flag says why the page shows
        # an empty picture rather than an average-looking one.
        return 0.0, 1.0, True
    return 0.0, ceiling, False


# The page's ONE colour window, memoised per recorded data set. Keyed on the
# IDENTITY of the planes, never on their shape: two different dumps of the same
# shape sharing a ceiling would be a per-frame rescale wearing a global label.
# The planes are held alive beside the entry, exactly as ``_TIMELINE_CACHE``
# holds its record, so a freed array's id cannot be recycled onto a new one.
GLOBAL_CLIM_CACHE: dict = {}
GLOBAL_CLIM_CACHE_LIMIT = 4
# How many times the window was actually COMPUTED. A viewer that rescaled per
# frame would grow this on every draw; one window for the whole animation grows
# it once per data set and then never again.
GLOBAL_CLIM_CALLS = 0


def global_clim(planes, percentile: float = COLOR_PERCENTILE):
    """The whole-animation |Ez| window for ``planes``, computed ONCE.

    :func:`_vis_colour_limit` is the arithmetic; this is the ONE door the page
    asks it through, and it answers from a memo after the first call. A redraw,
    a mode swap or a second reader on the same dump therefore costs O(1) and
    cannot come back with a different ceiling than the first reader got: the
    colour scale is decided at load and never moves while the animation plays.

    Returns the same ``(0.0, ceiling, empty)`` triple as
    :func:`_vis_colour_limit`. A MISS (a new data set) is O(total samples), the
    price of one window for the whole animation, paid exactly once per set.
    """
    global GLOBAL_CLIM_CALLS
    planes = tuple(planes)
    key = (tuple(id(plane) for plane in planes), float(percentile))
    hit = GLOBAL_CLIM_CACHE.get(key)
    if hit is not None and all(
        kept is asked for kept, asked in zip(hit[0], planes)
    ):
        return hit[1]
    window = _vis_colour_limit(planes, percentile)
    GLOBAL_CLIM_CALLS += 1
    if len(GLOBAL_CLIM_CACHE) >= GLOBAL_CLIM_CACHE_LIMIT:
        GLOBAL_CLIM_CACHE.clear()
    GLOBAL_CLIM_CACHE[key] = (planes, window)
    return window


def _is_vis(info: dict) -> bool:
    """True when ``info`` came from load_vis, not from load_dump."""
    # "format" is a serialized poc-state value, i.e. data rather than an
    # identifier, and VIS_FORMATS is the whole set the dumps on disk spell.
    return info.get("format") in VIS_FORMATS


def _timeline_for(info: dict):
    """The page's clock, built once per record and shared by every reader.

    :mod:`server.timeline` is the ONE place that decides how many positions the
    timeline has and which stored sample a layer shows; nothing here recomputes
    either. MEMOISED on ``id(info)`` with the record held alive beside the entry
    (see ``_volume_player_plan``): a draw asks for this on EVERY tick and the
    build is the expensive half of a tick, but keying on ``id`` alone would be
    unsound once a freed dict's id is recycled onto a new dump.
    """
    key = id(info)
    hit = _TIMELINE_CACHE.get(key)
    if hit is not None and hit[0] is info:
        return hit[1]
    built = _timeline.Timeline.from_dump(info)
    if len(_TIMELINE_CACHE) >= _TIMELINE_CACHE_LIMIT:
        _TIMELINE_CACHE.clear()
    _TIMELINE_CACHE[key] = (info, built)
    return built


def _frame_max_for(info: dict):
    """The scrubber's LAST position, or None on a page with no timeline.

    ONE number for both modes: switching plane re-aims the camera and clamps the
    position, it never rescales the timeline (that was the 10x speed change).
    """
    timeline = _timeline_for(info)
    return None if timeline is None else int(timeline.last_index)


def _position_count(info: dict) -> int:
    """How many positions the timeline has, floored at 1 for the step modulo."""
    timeline = _timeline_for(info)
    return 1 if timeline is None else max(1, int(timeline.nsteps))


def _play_rate_near(value) -> int:
    """``value`` snapped to the NEAREST offered speed; unusable values replaced.

    The speed is a UI value: it arrives from a select, from a URL, or from a script
    that set it to whatever it liked, so it is never trusted to be one of
    ``PLAY_RATES``. Nearest wins (7 becomes 8, 5 becomes 4) rather than
    default-on-anything-unknown, because the latter makes the number on screen and
    the number the loop uses disagree for the rest of the session - the caption
    would prove it, and this is the one place that decides, so the loop, the
    caption and the select cannot say different things.

    A missing/None/non-numeric value (a page built before the control existed, a
    select that never made it into the widget table) falls back on
    ``DEFAULT_PLAY_RATE``: a viewing page must always play at SOME speed. Ties go
    to the slower rate - a strobe is unreadable, and the operator asking for
    exactly a half-way speed has no preference this can violate.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return DEFAULT_PLAY_RATE
    rates = tuple(PLAY_RATES)
    return min(rates, key=lambda rate: (abs(rate - value), rate))


def _play_frames(value) -> int:
    """How many positions ``value``'s family holds, floored at 1.

    The loop divides a target position by this, so it must be a positive int.
    ``value`` is a frame COUNT, and either clock is None on a page that claims no
    timeline (see ``_frame_max_for``: None is "no timeline", never "0 frames").
    The REJECTED alternative - ``int(value)`` directly - raised TypeError inside a
    task nobody awaits: the exception was collected at GC, so the page stayed
    ``playing`` with nothing advancing and no trace to explain it. A page with no
    timeline simply holds its one position.
    """
    try:
        frames = int(value)
    except (TypeError, ValueError):
        return 1
    return max(1, frames)


def _play_stride(base_stride, rate) -> int:
    """The positions one PAINTED frame advances at speed ``rate``.

    ``base_stride`` is the per-painted-frame step at the DEFAULT speed, which is
    rate 4 (``DEFAULT_PLAY_RATE``, the speed the page opens on) - NOT at rate 1. The
    offered multipliers are applied to it around that anchor, which is what makes
    the speed select mean the same thing at every paint cap: rate 2 paints twice the
    stride, not twice the repaint rate. That is the whole reason the mapping lives
    in a function rather than being folded into the loop - ``base * rate /
    DEFAULT_PLAY_RATE`` reproduces the old positions-per-tick numbers at the default
    stride (4 * 1/4, 4 * 2/4, 4 * 4/4, 4 * 8/4 -> 1, 2, 4, 8), so the caption's "N
    steps/tick" sentence keeps saying what the picture does, while the speed select
    keeps offering the same four multipliers it always did.

    Both arguments are floored at 1 and any unusable value (None from a page built
    before the flag existed, a string from a URL, a bool) falls back on the module
    defaults. The REJECTED alternative is to use ``rate`` directly as the stride and
    let the paint cap carry the base: at --paint-fps 8 the slowest speed would then
    advance 1 position per repaint = 8 positions/s, and the operator who asked for
    "slower" would get a slideshow instead of a slower sweep. Rounding (not
    truncation) keeps the four offered multipliers exact; the max(1, ...) keeps a
    stride below one whole position - reachable with --stride 1 and a rate under the
    default - from silently freezing the player at a still frame.
    """
    try:
        base = int(base_stride)
    except (TypeError, ValueError):
        base = DEFAULT_PLAY_STRIDE
    try:
        steps = int(rate)
    except (TypeError, ValueError):
        steps = DEFAULT_PLAY_RATE
    base = max(1, base)
    steps = max(1, steps)
    return max(1, int(round(base * steps / float(DEFAULT_PLAY_RATE))))


def _play_advance(frame, stride, frames) -> int:
    """The position one painted frame after ``frame``: ``frame + stride``, wrapped.

    ``frames`` is the family length, so the wrap is the player's loop, and it is
    done HERE (not left to the caller's modulo) because the advance is what a
    painted frame IS: a position that has already wrapped is a position, whereas a
    target the clock invented has to be clamped and wrapped by whoever reads it.
    ``_play_frames`` floors the length at 1, so a page with no timeline wraps to its
    single position instead of dividing by zero.

    ``stride`` is floored at 1: zero or negative would stall or reverse the player,
    and neither is a speed the control offers. The REJECTED alternative is to
    keep :func:`_play_target`'s wall-clock integration and merely feed it a slower
    clock - it would still advance on ticks that painted nothing, which is exactly
    the invisible work this pump removes (the sequence on screen is what the
    caption describes, so it must be the sequence the loop chose).
    """
    stride = max(1, int(stride))
    frames = _play_frames(frames)
    return (int(frame) + stride) % frames


def _rate_list(rates) -> str:
    """``rates`` as prose: "1", "1 and 2", "1, 2 and 4"."""
    words = [str(int(rate)) for rate in rates]
    if len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + " and " + words[-1]


def _stride_collision_notice(base_stride) -> str:
    """The ``[poc_app]`` line that says the speed select has lost settings, or "".

    The stride is anchored at the DEFAULT speed (rate 4), so the four offered rates
    land on four different strides only while the base is big enough to give each
    of them its own number: ``--stride 1`` gives 1, 1, 1, 2 (rates 1, 2 and 4 all do
    nothing) and ``--stride 2`` gives 1, 1, 2, 4 (rates 1 and 2 are one setting).
    Nothing else on the page would ever say so - the caption quotes the stride the
    select GOT, which is right, not the stride it could have had - so the boot
    report says it once, on the same channel as every other honest line.

    "" when every rate has its own stride, which is what the default ``--stride 4``
    does (1, 2, 4, 8): a line that fires on the default is noise, and noise about a
    working page is read as a fault. A printed warning rather than ``parser.error``:
    the page is coarse, not wrong, and refusing to start would be the worse trade.
    """
    base = _play_stride(base_stride, DEFAULT_PLAY_RATE)
    strides = [_play_stride(base, rate) for rate in PLAY_RATES]
    if len(set(strides)) == len(strides):
        return ""
    shared = {}
    for rate, step in zip(PLAY_RATES, strides):
        shared.setdefault(step, []).append(rate)
    collisions = "; ".join(
        f"rates {_rate_list(members)} all advance {step} "
        f"position{'' if step == 1 else 's'} per painted frame"
        for step, members in shared.items() if len(members) > 1
    )
    return (
        f"[poc_app] --stride {base} collapses the speed select: {collisions}; "
        f"raise --stride to {DEFAULT_PLAY_STRIDE} for four distinct speeds"
    )


def _play_rate_items(rates=PLAY_RATES) -> list:
    """The speed select's items as Vuetify OBJECTS, ``title`` beside ``value``.

    Vuetify renders a row's visible text from ``item.title``, so a bare array of
    numbers (``[1, 2, 4, 8]``) leaves every row labelled by whatever fallback
    runs - the operator reported garbage ("st 1", "st 2", "8") on a control whose
    own label reads "steps per tick". The wording lives here, beside the value the
    loop and the caption use, so the three cannot disagree.
    """
    items = []
    for rate in rates:
        steps = int(rate)
        unit = "step/tick" if steps == 1 else "steps/tick"
        items.append({"title": f"{steps} {unit}", "value": steps})
    return items


def _play_target(anchor_time, anchor_frame, now, rate, fps) -> int:
    """NOT ON THE PLAYBACK PATH: nothing in this module calls it any more - the pump
    advances by painted frames now - and it survives as the documented REJECTED
    alternative only, its arithmetic pinned by tests.

    The position the wall clock says belongs on screen at ``now``.

    A PLAYING player is a clock read out as a position: ``anchor_frame`` was on
    screen at ``anchor_time``, and every 1/(rate*fps) seconds after that the
    position advances by one. The elapsed time is measured FROM THE ANCHOR and not
    accumulated tick by tick, so a tick that arrives late (the box was busy drawing
    a heavy sheet) ADVANCES FURTHER instead of stalling: the animation keeps the
    speed the caption promises and loses positions, not time.

    The REJECTED alternative is advance-by-a-fixed-number-per-tick, which is what
    this loop used to do: it is simpler, but it makes the playback speed a property
    of the machine - a slow box plays slowly, a fast one strobes, and the caption's
    "s per sweep" becomes a lie - which is precisely the honest-timing rule this
    module enforces elsewhere (sim time and wall clock are never conflated).

    ``rate``/``fps`` are floored at 1 so a zero (a select that never arrived, an
    old page) cannot divide by zero or run the position backwards. The result is
    clamped at 0 - it is an index, and a clock read before its anchor must not go
    negative - but NOT at the family length: the caller wraps it, because whether
    the player loops or stops is a property of the dump, not of time.
    """
    rate = max(1, int(rate))
    fps = max(1, int(fps))
    elapsed = float(now) - float(anchor_time)
    return max(0, int(anchor_frame) + int(elapsed * rate * fps))


def _play_reanchor(anchor_time, anchor_frame, now, current_frame, drawn_frame):
    """Adopt a position the loop did not choose as the new clock origin.

    While the player runs the position can be moved by something else: the
    scrubber, a << PREV / NEXT press, or a family swap that re-clamps the index.
    ``drawn_frame`` is what the loop itself last drew, so ``current_frame``
    differing from it means somebody else moved the player; the loop then takes
    that position as its origin AT THE CURRENT TIME and carries on from there, so
    the seek is respected instead of being overwritten on the very next tick (the
    clock would drag the position back to where nobody asked for it).

    The REJECTED alternative is to lock the player while it plays - to disable the
    slider, or to reuse the ``suppress_frame_listener`` flag for user seeks. The
    first turns a seek into a dead control; the second silences a REAL user action
    for a whole tick, and that flag exists to hide the loop's own re-entry (its
    ``_show`` writes ``state.frame``, which would otherwise fire the listener and
    draw a second time), not to hide the operator's. Returns the pair unchanged
    when nothing moved, so the common tick is a no-op.
    """
    if int(current_frame) == int(drawn_frame):
        return anchor_time, anchor_frame
    return now, int(current_frame)


def _play_caption(frames, rate, fps) -> str:
    """The one line of arithmetic the player bar prints under the speed select.

    It states the two numbers the picture cannot: how many positions a tick jumps
    and how long one full sweep takes at that speed. The sweep time is
    ``frames / (rate * fps)`` - the very quantity :func:`_play_target` integrates -
    so the sentence and the motion cannot drift apart.

    ``rate``/``fps`` are floored at 1, and a page with NO TIMELINE (``frames`` None
    or 0) gets a word instead of a duration. The REJECTED alternative is to divide
    anyway: 0 frames would raise ZeroDivisionError inside a layout builder (taking
    the column down), and a non-zero denominator over no frames would print a
    confident "0.0 s per sweep" for a page that has nothing to sweep - the same
    invented-axis dishonesty the timeline labels refuse.
    """
    rate = max(1, int(rate))
    fps = max(1, int(fps))
    if frames is None or int(frames) <= 0:
        return "no timeline"
    sweep_s = int(frames) / (rate * fps)
    return f"{rate} steps/tick at {fps} fps - {sweep_s:.1f} s per sweep"


TIME_AXIS_KEY = "time_axis"

# Where a loaded dump keeps one :class:`step_time.SurfaceSpec` per plane FAMILY.
# Filed by load_vis, read by every frame->step conversion, so the stride and
# offset in force are the ones derived from the dump's own recorded axes.
SURFACE_SPECS_KEY = "surface_specs"


@dataclass(frozen=True, eq=False)
class TimeAxis:
    """WHICH SOLVER STEP each position of the player stands on, as recorded.

    The player steps recorded captures, not steps: on a dump whose volume was
    saved every 100th step, one slider click moves the solver clock by 100 - and
    a label reading "frame 4 / 24" said nothing about that, so a decimated
    timeline could be read as one step per frame. This is the missing record,
    kept as ONE frozen value built by :func:`build_time_axis`.

    ``step_index[k]`` is the step of frame ``k`` (0-based here; the player's own
    label is 1-based). It is the PLANE family's axis - ``frame_index``, one
    recorded plane frame and one solver step per position, which is the clock
    the player steps (see ``_volume_player_plan``); the |E| volume is a
    decimated LAYER on it and no longer defines it. ``stride`` is how many steps
    one frame of THIS axis spans (1 for a plane family recorded every step),
    ``n_steps`` the run's own step count - the floor of the label's denominator
    (:attr:`max_step`) - and ``time_seconds`` the same axis in seconds, present only when the dump
    recorded a REAL ``dt_s``: an invented time base is precisely the dishonesty
    this record exists to remove, so an absent, non-finite or non-positive
    ``dt_s`` leaves it None rather than zero-filled.
    """

    step_index: np.ndarray
    stride: int
    n_steps: int
    time_seconds: np.ndarray | None = None

    @property
    def n_frames(self) -> int:
        """How many recorded frames this axis describes."""
        return int(np.asarray(self.step_index).size)

    def frame_to_step(self, frame):
        """The recorded step of 1-based ``frame``, or None off the axis."""
        try:
            position = int(frame) - 1
        except (TypeError, ValueError):
            return None
        if position < 0 or position >= self.n_frames:
            return None
        return int(self.step_index[position])

    def step_to_frame(self, step):
        """The 1-based frame recorded at the LAST step at or before ``step``.

        The last one, never an interpolation: a step between two captures has no
        picture, and the only frame that can be drawn is the earlier one. None
        when every recorded step starts after ``step``.
        """
        try:
            wanted = float(int(step))
        except (TypeError, ValueError):
            return None
        steps = np.asarray(self.step_index, dtype=float)
        if steps.size < 1:
            return None
        found = int(np.searchsorted(steps, wanted, side="right")) - 1
        return None if found < 0 else found + 1

    @property
    def max_step(self) -> int:
        """The LAST step this record reached - the label's denominator.

        ``n_steps`` is what the run's header claims; the recorded axis's last
        entry is what the dump actually holds. The larger of the two, so a
        recorded step can never outrun the denominator and the reader never
        sees "Step 2401 / 2400".
        """
        steps = np.asarray(self.step_index).ravel()
        recorded = int(steps[-1]) if steps.size else 0
        return max(int(self.n_steps), recorded)

    def label(self, frame):
        """One line naming 1-based ``frame`` and the step it was taken at.

        "Step 301 / 2400 (Stride 1)" - the step the solver had reached at this
        position, the last step the record reached (:attr:`max_step`) and the
        decimation in effect. The stride is ALWAYS stated, 1 included: a label
        that prints its stride only above 1 leaves the reader unable to tell
        "stride 1" from "stride not stated".

        ONE clock. This axis is the PLANE family's, so one position is one
        recorded plane frame and its own step; the |E| volume's decimation is a
        property of that LAYER's clock, not of this sentence, and a caller that
        draws the layer logs its reading instead (:func:`_log_volume_layer_note`).

        None is returned off the axis, so the caller can print its own words
        rather than this class inventing a frame. None too when the record is not
        ONE-BASED: a dump whose first capture sits at step 0 numbers its steps
        from a base it never states, so "Step 0 / 12" would present a zero-based
        number under a one-based denominator and misname every frame on the page.
        Such a page keeps the frame-only sentence rather than being given a step
        reading this record cannot defend.
        """
        step = self.frame_to_step(frame)
        if step is None:
            return None
        if int(np.asarray(self.step_index).ravel()[0]) < 1:
            return None
        return f"Step {step} / {self.max_step} (Stride {int(self.stride)})"


def build_time_axis(
    *,
    step_index=None,
    stride=None,
    n_steps=None,
    dt_s=None,
    n_frames=None,
) -> TimeAxis | None:
    """Build a page's :class:`TimeAxis`, or None when nothing was recorded.

    THE PRECEDENCE, in one place, so no two readers can disagree about it:

    1. the frame axis - the RECORDED ``step_index`` when the dump carries one
       (it may start at 0, or be evenly spaced at a stride of its own);
       otherwise ``arange(1, n_frames + 1)``, i.e. "one captured frame per
       step", the only claim a dump with no step axis supports;
    2. ``stride`` - the even spacing of the recorded axis when it has one,
       else the RECORDED value when the dump states one, else 1: the axis being
       DRAWN outranks the dump's single scalar, because one dump decimates its
       families differently and a scalar quoted over this axis would name a
       cadence the frames on screen contradict;
    3. ``n_steps`` - the RECORDED run length when the dump states it, else the
       last recorded step (a denominator below the frame count would claim a run
       shorter than the timeline it is the denominator of).

    None only when there is no frame axis at all - neither recorded steps nor a
    frame count: a page with no timeline gets no axis, never a zero-length one.
    """
    axis = None
    if step_index is not None:
        try:
            recorded = np.asarray(step_index, dtype=float).ravel()
        except (TypeError, ValueError):
            recorded = None
        # A backwards or non-finite axis is not a shorter axis, it is an
        # unreadable record: fall THROUGH to the frame count instead of casting
        # an order this page cannot defend into a step sequence.
        if recorded is not None and recorded.size > 0 and bool(
            np.all(np.isfinite(recorded))
        ):
            if recorded.size < 2 or not bool(np.any(np.diff(recorded) < 0.0)):
                axis = recorded.astype(int)
    if axis is None:
        try:
            frames = 0 if n_frames is None else int(n_frames)
        except (TypeError, ValueError):
            frames = 0
        if frames < 1:
            return None
        axis = np.arange(1, frames + 1, dtype=int)

    steps_apart = None
    if axis.size > 1:
        diffs = np.diff(axis.astype(float))
        if float(diffs[0]) > 0.0 and bool(np.all(diffs == diffs[0])):
            steps_apart = int(diffs[0])
    # The spacing of the axis THIS page draws is preferred over a dump-wide
    # scalar: one dump states ONE ``dump_stride`` while its families are
    # decimated differently - ``artifacts/volume_s59.npz`` records
    # ``frame_index`` spaced 1 apart and ``frame_index_xcut`` spaced 10 apart -
    # so a scalar quoted over the drawn axis prints a cadence the frames on
    # screen contradict ("Stride 1" beside frames that advance 10 steps). The
    # scalar is only a fallback for an axis with no even spacing to measure,
    # which is the rule the exporter's ``measured_stride`` and the timeline's
    # ``Timeline.stride`` already apply.
    if steps_apart:
        stride_value = steps_apart
    else:
        try:
            stride_value = int(stride)
        except (TypeError, ValueError):
            stride_value = 0
        if stride_value <= 0:
            stride_value = 1

    try:
        total = int(n_steps)
    except (TypeError, ValueError):
        total = 0
    if total <= 0:
        total = max(int(axis[-1]), int(axis.size))

    seconds = None
    try:
        dt = float(dt_s)
    except (TypeError, ValueError):
        dt = float("nan")
    if math.isfinite(dt) and dt > 0.0:
        seconds = axis.astype(float) * dt

    return TimeAxis(
        step_index=axis, stride=int(stride_value), n_steps=int(total),
        time_seconds=seconds,
    )


def _frame_label(index, frames, time_axis=None):
    """The player's step sentence, or None on a page with no timeline.

    The ONE place that sentence is composed, and ``frames`` is the count the
    PLAYER steps - the timeline's own length, ``_position_count`` - so the
    slider, the play loop and this label are all counted on ONE clock, and the
    x-cut planes are a held layer on it rather than a second clock. None is
    "no timeline", never "Step 1 / None".

    ``time_axis`` is the page's RECORDED step axis (``info["time_axis"]"), the
    PLANE family's. When it counts the SAME frames the player steps the sentence
    is read off that record - "Step 301 / 2400 (Stride 1)" - so the label names
    the solver step on screen instead of counting clicks, states the last step
    the record reached and the decimation in effect.

    ONE clock: the |E| layer's own reading is not folded in here, it is logged
    (:func:`_log_volume_layer_note`).

    A page with no axis, or one describing a different family than the player
    steps, keeps the position-counted sentence - ``Step 3 / 12`` off the
    position, never off a step the file does not claim - which is also the
    legacy two-argument call, unchanged, and the only indicator the page draws.
    """
    if frames is None:
        return None
    if time_axis is not None:
        try:
            same_clock = int(time_axis.n_frames) == int(frames)
        except (AttributeError, TypeError, ValueError):
            same_clock = False
        if same_clock:
            text = time_axis.label(int(index) + 1)
            if text is not None:
                return text
    return f"Step {int(index) + 1} / {int(frames)}"


# ---------------------------------------------------------------------------
# THE 3-D |E| VOLUME LAYER IS OFF BY DEFAULT (POC_SHOW_VOLUME)
#
# WHY: the |E| volume is a second, decimated clock drawn on top of the two
# cut-plane sheets.  It is still built and still tested, but a reader who opens
# the page gets the SHEETS - the field the dump records per plane frame - rather
# than a translucent box over them.  The layer is one environment variable away:
# POC_SHOW_VOLUME=1 puts it back with its cut sheets, its port planes, its |E|
# bar and its half of the label.
#
# WHAT IT MAY NEVER COST: the two cut-plane heatmaps.  Those are the ``sheets``
# the page adds ONCE and swaps one scalar array on per tick (see ``_show``);
# they are not part of this layer, and nothing here touches them.
#
# READ AT CALL TIME, not once at import, so a handler (or a test) can turn the
# layer on or off between draws without a re-import.
# ---------------------------------------------------------------------------

SHOW_VOLUME_LAYER_DEFAULT = False

# The runtime switch's own cell: the checkbox (:19816) binds to it and its
# handler (:18205) writes it. A PLAIN DICT and not a ``state`` attribute, for the
# very reason the Grid layer's box keeps one (:15525-15531): the boot sheets are
# built BEFORE ``server.state`` exists, and a reader that reached into state
# would NameError on the very first frame. What is NOT duplicated is the reader -
# every consumer still asks ``_volume_layer_enabled`` below, so there is exactly
# one place that answers the question.
#
# ``"on"`` is None until the box speaks, and None is NOT False. False would mean
# "somebody switched it off" and would have to beat both the environment variable
# and the page's own answer; None means "no opinion yet", so a draw that happens
# before any widget exists still gets the page policy below.
#
# ``"page"`` is the context's answer to the two-halves question
# (``Available.volume_layer_shown``, um3k_context.py:105-109): does THIS page
# carry the volume AND want it drawn. ``run_web_vis`` publishes it once, right
# after the context is built (:15873), long before the first draw.
_VOLUME_LAYER_STATE: dict = {"on": None, "page": False}


def _volume_layer_enabled() -> bool:
    """Is the 3-D |E| volume layer to be drawn?

    THE ONE READER of that question - do not add a second. The order below is
    what lets a runtime checkbox exist without moving the boot default:

    1. the switch, if it has spoken (``None`` = it has not, see above);
    2. ``POC_SHOW_VOLUME=1``, the documented opt-in;
    3. the page's own answer, published by ``run_web_vis`` before the first draw;
    4. the module constant, which stays False so a bare run is unchanged.
    """
    if _VOLUME_LAYER_STATE["on"] is not None:
        return bool(_VOLUME_LAYER_STATE["on"])
    if os.environ.get("POC_SHOW_VOLUME") == "1":
        return True
    if _VOLUME_LAYER_STATE["page"]:
        return True
    return bool(SHOW_VOLUME_LAYER_DEFAULT)


# ---------------------------------------------------------------------------
# THE PICTURE IS RENDERED BY THE SERVER UNLESS ASKED OTHERWISE (POC_LOCAL_VIEW)
#
# WHY: mode="server" (PyVistaRemoteView) renders here and streams the image, so
# the page does not depend on the client's WebGL context surviving inside a
# flexed container - that is the DEFAULT and the only behaviour a plain run has.
# mode="client" (PyVistaLocalView) moves the rendering to the BROWSER instead,
# which is what a host with no GL to render WITH wants: the server then
# suppresses its own rendering (trame_pyvista sets suppress_rendering from the
# mode) instead of pushing stills nobody can produce.
#
# WHAT IT MAY NEVER COST: the default page. Off, the mode string is "server",
# add_menu is False and the layout is built in the same order as before - one
# flag away and byte-identical, and a test pins that.
#
# READ AT CALL TIME, not once at import, so the answer handed to the layout is
# the one in force when the page is BUILT (see run_web_vis): a test can set it
# between draws without a re-import.
# ---------------------------------------------------------------------------

LOCAL_VIEW_DEFAULT = False


def _local_view_enabled(flag: bool = False) -> bool:
    """Render the centre plotter in the BROWSER?  False unless opted in.

    ``flag`` is the parsed ``--local-view``; ``POC_LOCAL_VIEW`` does the same
    without the flag (``1``/``true``). The flag WINS over the variable, because
    a run that named a mode on its command line must not be overridden by a
    leftover export.
    """
    if flag:
        return True
    if bool(LOCAL_VIEW_DEFAULT):
        return True
    value = os.environ.get("POC_LOCAL_VIEW")
    if value is None:
        return False
    return value.strip().lower() in ("1", "true")


def _local_view_notice(render_local) -> str | None:
    """The ONE boot line a browser-rendered run prints, or None when it does not.

    A helper, not an inline print, for two reasons: the sentence is the whole
    subject of a test that must not boot a server to read it, and a flag-OFF run
    has to add NOTHING to the log - None means the caller emits no line at all,
    so the default page's output stays byte-for-byte what it was.
    """
    if not render_local:
        return None
    return (
        "[poc_app] local view: the BROWSER draws the picture and this server "
        "renders nothing, so the timing screenshots (which read pixels back on "
        "the server) are unavailable; the mode is experimental and VTK's scene "
        "export is the part that can crash the process - a plain run (no "
        "--local-view) renders on the server"
    )


# ---------------------------------------------------------------------------
# OPT-IN TIMING PROBE (POC_TIMING)
#
# WHY this exists: the viewer runs on the OPERATOR's machine, so "which part of
# a tick is slow" cannot be profiled from here. This probe writes a per-tick
# timing line, a rolling summary and a few frames into the WORKSPACE, so the
# answer can be read off a file afterwards instead of guessed from a symptom.
#
# WHAT IT MAY NEVER DO: change what the viewer draws, raise into the app, or
# cost anything while disabled. Every entry point returns EARLY when the probe
# is off, every body is wrapped in try/except, and this block adds NO render
# call and changes NO existing call's arguments.
#
# ENABLEMENT: ON by default; off only when POC_TIMING is exactly "0", read ONCE
# here at import.
#
# WHERE: <repo>/artifacts/timing/, anchored on the repository root rather than
# the cwd, and never inside the source tree.
# ---------------------------------------------------------------------------

_TIMING_ENABLED = os.environ.get("POC_TIMING") != "0"
_TIMING_ROOT = Path(__file__).resolve().parent.parent / "artifacts" / "timing"
_TIMING_LOG_PATH = _TIMING_ROOT / "poc_timing.log"
_TIMING_SUMMARY_PATH = _TIMING_ROOT / "poc_timing_summary.txt"
_TIMING_FRAMES_DIR = _TIMING_ROOT / "frames"
# A screenshot is a FULL framebuffer readback, so it is rationed twice over: one
# every 100th tick, and never more than 60 files in a run.
# WHY 100 and not 25: the readback costs 40-75 ms and is spent INSIDE the tick it
# is measuring, so a shot every 25th tick polluted the very probe it feeds with a
# cost no ordinary frame pays. Every 100th tick bounds the run by the same
# 60-file cap while keeping the timing probe honest.
_TIMING_SHOT_EVERY = 100
_TIMING_SHOT_MAX = 60
_TIMING_SUMMARY_EVERY = 50

# The one mutable probe state. Everything below reads and writes THIS, so a
# tick in progress is one dict and cannot be half-reset by a second caller.
_TIMING = {
    "tick": 0,
    "t0": None,
    "index": None,
    "mode": None,
    "marks": {},
    "fields": {},
    "rows": [],
    "open": False,
    "started": False,
    "prev_tick_start": None,
    "gap_ms": None,
    "play": {},
    "pending_play": {},
    "shot_count": 0,
    "shots_ok": True,
    "shot_error_logged": False,
    "boot_done": False,
}


def _timing_ensure_dirs() -> None:
    """Create the artifact directories (never inside the source tree)."""
    _TIMING_FRAMES_DIR.mkdir(parents=True, exist_ok=True)


def _timing_num(value, digits=3):
    """Format one millisecond figure, or ``-`` when it was not measured."""
    try:
        if value is None:
            return "-"
        return f"{float(value):.{digits}f}"
    except Exception:  # noqa: BLE001 - a log line is not the app
        return "-"


def _timing_stats(values):
    """``n``/mean/median/p95/max over the measured values, or None if none."""
    try:
        data = sorted(float(v) for v in values if v is not None)
    except Exception:  # noqa: BLE001 - a summary is not the app
        return None
    if not data:
        return None
    count = len(data)
    middle = count // 2
    median = data[middle] if count % 2 else 0.5 * (data[middle - 1] + data[middle])
    tail = min(count - 1, int(round(0.95 * (count - 1))))
    return {
        "n": count,
        "mean": sum(data) / count,
        "median": median,
        "p95": data[tail],
        "max": data[-1],
    }


def _timing_mean(values):
    """Mean of the measured values, or None when none were measured."""
    try:
        data = [float(v) for v in values if v is not None]
    except Exception:  # noqa: BLE001 - a summary is not the app
        return None
    return (sum(data) / len(data)) if data else None


def _timing_span(name_a, name_b):
    """Milliseconds between two marks of THIS tick, or None if either is absent."""
    try:
        marks = _TIMING["marks"]
        first, second = marks.get(name_a), marks.get(name_b)
        if first is None or second is None:
            return None
        return (second - first) * 1000.0
    except Exception:  # noqa: BLE001 - a log line is not the app
        return None


def _timing_write(line) -> None:
    """Append ONE line, TRUNCATING the log on this process's first write.

    WHY open-per-line: the operator may kill the viewer outright, and a line
    that is already closed and on disk survives that. The truncate is keyed on
    a flag rather than the file, so a restart cannot append to the previous
    run's numbers.
    """
    try:
        if not _TIMING_ENABLED:
            return
        _timing_ensure_dirs()
        mode = "a" if _TIMING.get("started") else "w"
        with open(_TIMING_LOG_PATH, mode, encoding="utf-8") as handle:
            handle.write(str(line) + "\n")
            handle.flush()
        _TIMING["started"] = True
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return


def _timing_tick_begin(index=None, mode=None) -> None:
    """Start a tick: one perf_counter origin, plus the gap since the last one."""
    try:
        if not _TIMING_ENABLED:
            return
        now = time.perf_counter()
        probe = _TIMING
        previous = probe.get("prev_tick_start")
        probe["gap_ms"] = None if previous is None else (now - previous) * 1000.0
        probe["prev_tick_start"] = now
        probe["t0"] = now
        probe["tick"] = int(probe.get("tick", 0)) + 1
        probe["index"] = index
        probe["mode"] = None if mode is None else str(mode)
        probe["marks"] = {"t0": now}
        probe["fields"] = {}
        # The play loop measures its tick BEFORE _show begins this one; the
        # numbers it parked belong to THIS line.
        probe["play"] = probe.get("pending_play") or {}
        probe["pending_play"] = {}
        probe["open"] = True
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return


def _timing_mark(name, **fields) -> None:
    """Record a perf_counter mark (and optional scalar fields) for THIS tick."""
    try:
        if not _TIMING_ENABLED:
            return
        probe = _TIMING
        if not probe.get("open"):
            return
        probe["marks"][name] = time.perf_counter()
        if fields:
            probe["fields"].update(fields)
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return


def _timing_play_tick(period_ms, interval_ms, slip_ms) -> None:
    """Park the PLAY loop's deadline arithmetic for the next tick's line.

    WHY parked rather than written: the loop measures its tick before ``_show``
    begins the tick this row belongs to. Parking lets ONE line carry both the
    loop's slip and the draw's phases, so the two halves cannot be read out of
    step - which is the whole point of comparing them.
    """
    try:
        if not _TIMING_ENABLED:
            return
        _TIMING["pending_play"] = {
            "period_ms": period_ms,
            "interval_ms": interval_ms,
            "slip_ms": slip_ms,
        }
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return


def _timing_screenshot(plotter):
    """Time ONE viewport screenshot. Returns its ms, or None when not taken.

    WHY it runs AFTER the tick's phases are frozen: a readback costs tens of
    milliseconds, and folding it into any phase would indict the wrong code.
    WHY the guard disables the whole feature: a plotter that cannot screenshot
    (a headless backend, a test double) would otherwise raise on every ration
    tick, and the operator would be reading a log full of the same error.
    """
    try:
        probe = _TIMING
        if plotter is None or not probe.get("shots_ok"):
            return None
        # A plotter that is SUPPRESSING its rendering (a browser-rendered view:
        # trame_pyvista sets suppress_rendering=True for mode="client") has
        # never had a GL context and never will, and asking it for a picture is
        # not the harmless no-op a draw is: pyvista's render() honours the flag
        # (plotter.py:2557), but the READBACK does NOT - Plotter.image goes
        # through vtkWindowToImageFilter, which renders the window ITSELF.
        # So the flag is walked around exactly here, and a client-rendered view
        # asked for a still is a C-level crash waiting for _rendered to become
        # true. Refuse: no pixel is requested, and the result is the same None
        # (and the same untouched timing bookkeeping) as a capture that failed.
        if getattr(plotter, "suppress_rendering", False):
            return None
        tick = int(probe.get("tick", 0))
        if tick % _TIMING_SHOT_EVERY != 0:
            return None
        if int(probe.get("shot_count", 0)) >= _TIMING_SHOT_MAX:
            return None
        try:
            _timing_ensure_dirs()
            started = time.perf_counter()
            plotter.screenshot(str(_TIMING_FRAMES_DIR / ("tick_%06d.png" % tick)))
            elapsed = (time.perf_counter() - started) * 1000.0
        except Exception as exc:  # noqa: BLE001 - a picture is not the run
            probe["shots_ok"] = False
            if not probe.get("shot_error_logged"):
                probe["shot_error_logged"] = True
                print(
                    f"[poc_app] timing screenshots disabled: {exc}",
                    file=sys.stderr,
                )
                _timing_write(f"SCREENSHOT disabled at tick {tick}: {exc!r}")
            return None
        probe["shot_count"] = int(probe.get("shot_count", 0)) + 1
        # A readback is paid INSIDE the tick it is measuring, so the tick that
        # paid must say so: this is the only place that knows the shot ran.
        _stall_mark_shot(elapsed, tick)
        return elapsed
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return None


def _timing_line(row):
    """One log line for one tick. Every phase is present, ``-`` if unmeasured."""
    parts = [
        f"tick={row.get('tick')}",
        f"index={row.get('index')}",
        f"mode={row.get('mode')}",
        f"layer={row.get('layer')}",
        f"total_ms={_timing_num(row.get('total_ms'))}",
        f"sheet_ms={_timing_num(row.get('sheet_ms'))}",
        f"layer_ms={_timing_num(row.get('layer_ms'))}",
        f"render_ms={_timing_num(row.get('render_ms'))}",
        f"push_ms={_timing_num(row.get('push_ms'))}",
        f"other_ms={_timing_num(row.get('other_ms'))}",
        f"actors={row.get('actors')}",
        f"gap_ms={_timing_num(row.get('gap_ms'))}",
        f"screenshot_ms={_timing_num(row.get('screenshot_ms'))}",
        f"period_ms={_timing_num(row.get('period_ms'))}",
        f"interval_ms={_timing_num(row.get('interval_ms'))}",
        f"slip_ms={_timing_num(row.get('slip_ms'))}",
    ]
    if row.get("layer") == "MISS":
        parts.extend(
            [
                f"drop_ms={_timing_num(row.get('drop_ms'))}",
                f"scene_ms={_timing_num(row.get('scene_ms'))}",
                f"markers_ms={_timing_num(row.get('markers_ms'))}",
                f"actors_before={row.get('actors_before')}",
                f"actors_after={row.get('actors_after')}",
            ]
        )
    return " ".join(parts)


def _timing_boot(plotter, info, timeline, fps, play_rate) -> None:
    """Write the run's BOOT line, once: what versions and what dump."""
    try:
        probe = _TIMING
        if probe.get("boot_done"):
            return
        probe["boot_done"] = True
        pv_version = "unavailable"
        try:
            import pyvista as _pv

            pv_version = str(getattr(_pv, "__version__", "unavailable"))
        except Exception:  # noqa: BLE001 - the boot line is still useful
            pv_version = "unavailable"
        dump_path = None
        try:
            dump_path = info.get("path") if isinstance(info, dict) else None
        except Exception:  # noqa: BLE001 - the boot line is still useful
            dump_path = None
        nsteps = None
        try:
            nsteps = int(timeline.nsteps) if timeline is not None else None
        except Exception:  # noqa: BLE001 - the boot line is still useful
            nsteps = None
        captures = None
        try:
            volume = info.get("e_abs_volume") if isinstance(info, dict) else None
            if volume is not None and getattr(volume, "ndim", 0) >= 1:
                captures = int(volume.shape[0])
        except Exception:  # noqa: BLE001 - the boot line is still useful
            captures = None
        viewport = None
        try:
            size = plotter.window_size
            viewport = f"{int(size[0])}x{int(size[1])}"
        except Exception:  # noqa: BLE001 - the boot line is still useful
            viewport = None
        python_version = (
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}"
        )
        _timing_write(
            "BOOT "
            f"python={python_version} pyvista={pv_version} dump={dump_path} "
            f"timeline_nsteps={nsteps} e_abs_captures={captures} "
            f"fps={fps} play_rate={play_rate} viewport={viewport}"
        )
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return


def _timing_write_summary() -> None:
    """Rewrite the aggregate table for the run SO FAR. Never raises."""
    try:
        if not _TIMING_ENABLED:
            return
        rows = list(_TIMING.get("rows") or [])
        miss_rows = [r for r in rows if r.get("layer") == "MISS"]
        hit_rows = [r for r in rows if r.get("layer") == "HIT"]
        lines = ["POC TIMING SUMMARY", ""]
        lines.append(
            f"ticks={len(rows)}  miss={len(miss_rows)}  hit={len(hit_rows)}  "
            f"screenshots={int(_TIMING.get('shot_count', 0) or 0)}"
        )
        lines.append(f"log={_TIMING_LOG_PATH}")
        lines.append("")
        for label, subset in (("all ", rows), ("MISS", miss_rows), ("HIT ", hit_rows)):
            stats = _timing_stats([r.get("total_ms") for r in subset])
            if stats is None:
                lines.append(f"total_ms {label}  n=0  (nothing measured)")
                continue
            lines.append(
                f"total_ms {label}  n={stats['n']}  "
                f"mean={_timing_num(stats['mean'])}  "
                f"median={_timing_num(stats['median'])}  "
                f"p95={_timing_num(stats['p95'])}  "
                f"max={_timing_num(stats['max'])}"
            )
        lines.append("")
        lines.append("mean of each phase over ALL ticks (ms):")
        for key in (
            "sheet_ms",
            "layer_ms",
            "render_ms",
            "push_ms",
            "other_ms",
            "gap_ms",
            "screenshot_ms",
        ):
            value = _timing_mean([r.get(key) for r in rows])
            lines.append(f"  {key:<15}{_timing_num(value)}")
        lines.append("mean of the MISS-only phases over MISS ticks (ms):")
        for key in ("drop_ms", "scene_ms", "markers_ms"):
            value = _timing_mean([r.get(key) for r in miss_rows])
            lines.append(f"  {key:<15}{_timing_num(value)}")
        lines.append("")
        slip = _timing_stats([r.get("slip_ms") for r in rows])
        periods = [r.get("period_ms") for r in rows if r.get("period_ms") is not None]
        late = 0
        for r in rows:
            value, period = r.get("slip_ms"), r.get("period_ms")
            if value is not None and period is not None and value > period:
                late += 1
        lines.append("deadline slip from _play_loop (ms):")
        if slip is None:
            lines.append("  no playback tick was measured")
        else:
            lines.append(
                f"  n={slip['n']}  mean={_timing_num(slip['mean'])}  "
                f"median={_timing_num(slip['median'])}  "
                f"p95={_timing_num(slip['p95'])}  max={_timing_num(slip['max'])}  "
                f"late_ticks(slip>period)={late}"
            )
            lines.append(
                f"  period_ms={_timing_num(periods[-1] if periods else None)}  "
                "interval_ms mean="
                f"{_timing_num(_timing_mean([r.get('interval_ms') for r in rows]))}"
            )
        lines.append("")
        lines.append("worst 10 ticks (tick, index, total_ms, layer):")
        ranked = sorted(
            (r for r in rows if r.get("total_ms") is not None),
            key=lambda r: r["total_ms"],
            reverse=True,
        )[:10]
        if not ranked:
            lines.append("  none")
        for r in ranked:
            lines.append(
                f"  tick={str(r.get('tick')):>6} index={str(r.get('index')):>6} "
                f"total_ms={_timing_num(r.get('total_ms')):>9} "
                f"layer={r.get('layer')}"
            )
        _TIMING_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _TIMING_SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return


def _timing_tick_end(
    plotter=None,
    index=None,
    mode=None,
    info=None,
    timeline=None,
    fps=None,
    play_rate=None,
) -> None:
    """Finish a tick: freeze the phases, ration a screenshot, write ONE line.

    ORDER MATTERS: every phase is measured from the marks and the row is frozen
    BEFORE the screenshot is timed, so the readback's cost lands in its own
    column and never inside ``render_ms`` or ``other_ms``.
    """
    try:
        if not _TIMING_ENABLED:
            return
        probe = _TIMING
        if not probe.get("open"):
            return
        probe["open"] = False
        now = time.perf_counter()
        t0 = probe.get("t0")
        total_ms = None if t0 is None else (now - t0) * 1000.0
        if index is not None:
            probe["index"] = index
        if mode is not None:
            probe["mode"] = str(mode)
        marks = probe["marks"]
        fields = probe.get("fields") or {}
        phases = {
            "sheet_ms": _timing_span("sheet_start", "sheet_end"),
            "layer_ms": _timing_span("layer_start", "layer_end"),
            "render_ms": _timing_span("render_start", "render_end"),
            "push_ms": _timing_span("push_start", "push_end"),
        }
        measured = sum(v for v in phases.values() if v is not None)
        # The remainder is REPORTED, not hidden: a phase this probe does not
        # name yet still shows up in the total, so the columns add up.
        phases["other_ms"] = None if total_ms is None else total_ms - measured
        if "layer_hit" in marks:
            layer_state = "HIT"
        elif "miss_start" in marks:
            layer_state = "MISS"
        else:
            layer_state = "-"
        play = probe.get("play") or {}
        row = dict(
            phases,
            tick=probe.get("tick"),
            index=probe.get("index"),
            mode=probe.get("mode"),
            layer=layer_state,
            total_ms=total_ms,
            gap_ms=probe.get("gap_ms"),
            actors=None,
            screenshot_ms=None,
            period_ms=play.get("period_ms"),
            interval_ms=play.get("interval_ms"),
            slip_ms=play.get("slip_ms"),
            drop_ms=_timing_span("miss_start", "miss_drop"),
            scene_ms=_timing_span("miss_scene_start", "miss_scene_end"),
            markers_ms=_timing_span("miss_markers_start", "miss_markers_end"),
            actors_before=fields.get("actors_before"),
            actors_after=fields.get("actors_after"),
        )
        try:
            row["actors"] = len(plotter.actors)
        except Exception:  # noqa: BLE001 - a count is not the run
            row["actors"] = None
        row["screenshot_ms"] = _timing_screenshot(plotter)
        _timing_boot(plotter, info, timeline, fps, play_rate)
        _timing_write(_timing_line(row))
        probe["rows"].append(row)
        if int(probe.get("tick", 0)) % _TIMING_SUMMARY_EVERY == 0:
            _timing_write_summary()
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return


def _timing_register_exit() -> None:
    """Rewrite the summary when the process ends: the run's "at the end"."""
    try:
        import atexit

        atexit.register(_timing_write_summary)
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return


if _TIMING_ENABLED:
    _timing_register_exit()


# ---------------------------------------------------------------------------
# --profile: WHERE the per-tick time goes.
#
# The block above (_timing_*) answers "how long did this tick take". This block
# answers the next question - "and of that, how much was re-anchoring the
# clock, how much a GL draw, how many of the three cut sheets were repainted
# with the SAME plane index they already held". It EXTENDS the probe above and
# reuses its _timing_stats(); it does not replace anything.
#
# OFF BY DEFAULT. On with --profile (artefacts in --profile-dir, default
# artifacts/profile/) or with POC_PROFILE=1 / POC_TIMING=1 in the environment:
# POC_TIMING stays the alias, so one variable turns on both probes.
# POC_TICK_STALL is the third key for the same reason the second one is here: the
# stall probe below takes no marks of its own - it rides the marks this block
# takes - so switching it on must switch this block on, or it measures nothing.
#
# Every hook is wrapped: telemetry that raises must never surface as a draw
# that raises, the same rule the _timing_* block follows.
_PROFILE_ENV_KEYS = ("POC_PROFILE", "POC_TIMING", "POC_TICK_STALL")
_PROFILE_DEFAULT_DIR = (
    Path(__file__).resolve().parent.parent / "artifacts" / "profile"
)
_PROFILE_LAG_EVERY_S = 0.05
_PROFILE_STACK_EVERY_S = 0.20
_PROFILE_IDLE_EVERY_S = 1.0
_PROFILE_IDLE_GAP_S = 0.9
_PROFILE_MAX_ROWS = 20000
_PROFILE_SUMMARY_EVERY = 200
_PROFILE_PHASES = ("reanchor", "target", "draw", "flush", "yield")
# Counters a play-loop gate bumps when it skips a beat: the beat is skipped
# BEFORE _show opens a tick, so the count is carried to the next written row.
_PROFILE_GATE_COUNTS = ("paint_cap", "delivery_hold", "scrub_hold")

_PROFILE = {
    "enabled": False,
    "dir": None,
    "stamp": None,
    "files": {},
    "clock": time.perf_counter,
    "process_clock": time.process_time,
    "rusage": None,
    "started": None,
    "mark_at": None,
    "tick": None,
    "pending": None,
    "rows": [],
    "ticks": 0,
    "counts": {},
    "tick_counts": {},
    "sheets": {},
    "lag": [],
    "idle": [],
    "stacks": None,
    "last_tick_at": None,
    "lag_at": None,
    "stack_at": None,
    "idle_at": None,
    "idle_prev": None,
    "thread": None,
    "stop": False,
    # The display knobs the run was STARTED with (--fps, --msaa, --image-*), so
    # the summary can name them beside the numbers they produced.
    "knobs": {},
    # The IMAGE-DELIVERY path (trame's vtkWebPublishImageDelivery), counted where
    # trame decides to encode a frame rather than where the app asks for one, so a
    # push it drops on its own behalf is visible instead of looking like a tick
    # that forgot to push.
    "push": {
        "attempts": 0,
        "rendered": 0,
        "dropped_animation": 0,
        "dropped_untracked": 0,
        "dropped_disabled": 0,
        # True only once the wrappers are really installed: the summary then says
        # "available=no" rather than reporting a zero it could not measure.
        "available": False,
    },
    "still": {
        "n": 0,
        "ms": [],
        "total_ms": 0.0,
        "bytes": [],
        "total_bytes": 0,
    },
    "animate": {
        "calls": 0,
        "last_target_fps": None,
        "in_animation_s": 0.0,
        "last_at": None,
    },
    "client": {
        "events": [],
        "start_interaction": 0,
        "end_interaction": 0,
        "animation_start": 0,
        "animation_stop": 0,
    },
    # The delivery totals the OPEN tick started from, so a tick row reports what
    # THAT tick shipped instead of the run's running total.
    "tick_snap": None,
    "delivery_hooked": False,
}


def _profile_env_enabled() -> bool:
    """True when the ENVIRONMENT asks for the suite (--profile is separate)."""
    for key in _PROFILE_ENV_KEYS:
        value = os.environ.get(key)
        if value is not None and value.strip() not in ("", "0"):
            return True
    return False


def _profile_enabled() -> bool:
    """True while the profile suite is recording. The ONE gate the hooks use."""
    return bool(_PROFILE["enabled"])


def _profile_now() -> float:
    """Monotonic seconds. Swappable, so the tests can drive a fake clock."""
    try:
        return float(_PROFILE["clock"]())
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return 0.0


def _profile_rusage() -> tuple:
    """(utime, stime) of THIS process in seconds. Stdlib, never raises."""
    fn = _PROFILE.get("rusage")
    if fn is not None:
        try:
            pair = fn()
            return float(pair[0]), float(pair[1])
        except Exception:  # noqa: BLE001
            return 0.0, 0.0
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF)
        return float(usage.ru_utime), float(usage.ru_stime)
    except Exception:  # noqa: BLE001 - no resource module (or no permission)
        return 0.0, 0.0


def _profile_elapsed(now=None) -> float:
    """Seconds since the run started. Explicit None check: 0.0 is a legal clock."""
    if now is None:
        now = _profile_now()
    started = _PROFILE["started"]
    if started is None:
        return 0.0
    return float(now) - float(started)


def _profile_since_mark(now) -> float:
    """Seconds since the last phase mark, and moves the mark to ``now``."""
    previous = _PROFILE["mark_at"]
    _PROFILE["mark_at"] = now
    if previous is None:
        return 0.0
    return float(now) - float(previous)


def _profile_reset() -> None:
    """Forget everything recorded so far. For the tests, and for a re-run."""
    _PROFILE["tick"] = None
    _PROFILE["pending"] = None
    _PROFILE["rows"] = []
    _PROFILE["ticks"] = 0
    _PROFILE["counts"] = {}
    _PROFILE["tick_counts"] = {}
    _PROFILE["sheets"] = {}
    _PROFILE["lag"] = []
    _PROFILE["idle"] = []
    _PROFILE["stacks"] = None
    _PROFILE["last_tick_at"] = None
    _PROFILE["lag_at"] = None
    _PROFILE["stack_at"] = None
    _PROFILE["idle_at"] = None
    _PROFILE["idle_prev"] = None
    _PROFILE["started"] = None
    _PROFILE["mark_at"] = None
    # The knobs describe the RUN, not the recording: reset forgets them too, so a
    # re-configured process cannot answer with the previous run's flags.
    _PROFILE["knobs"] = {}
    # The delivery records are reset IN PLACE: the hook holds a reference to the
    # same dictionaries, so a reset that rebound them would leave the wrappers
    # counting into an orphan nobody reads.
    _PROFILE["push"].update(
        attempts=0,
        rendered=0,
        dropped_animation=0,
        dropped_untracked=0,
        dropped_disabled=0,
        available=False,
    )
    _PROFILE["still"].update(n=0, ms=[], total_ms=0.0, bytes=[], total_bytes=0)
    _PROFILE["animate"].update(
        calls=0, last_target_fps=None, in_animation_s=0.0, last_at=None
    )
    _PROFILE["client"].update(
        events=[],
        start_interaction=0,
        end_interaction=0,
        animation_start=0,
        animation_stop=0,
    )
    _PROFILE["tick_snap"] = None
    _PROFILE["delivery_hooked"] = False
    # The stall probe's samples are per-run too, but its SWITCH is not a sample:
    # a reset forgets the numbers and leaves the probe installed.
    _stall_reset()


# ---------------------------------------------------------------------------
# POC_TICK_STALL: WHICH tick stalled, and what was running when it did.
#
# The two blocks above answer "how long did this tick take" and "where did that
# time go on average". Neither answers the question an operator asks when the
# picture freezes for a second: WHICH tick was it, and was that second spent
# re-anchoring, drawing, flushing, or in a garbage collection nothing else here
# can see.
#
# So this probe rides the SAME marks the profile suite already takes
# (_profile_tick_begin / _profile_phase / _profile_yield / _profile_tick_end):
# no draw path learns that it is being measured, and the phases it sums are the
# ones that block already paid for. It adds the one sample Python cannot hand
# the profile suite directly - gc pauses, from gc.callbacks.
#
# OFF BY DEFAULT. On with POC_TICK_STALL=1 in the environment, which also turns
# the profile suite on (see _PROFILE_ENV_KEYS: the marks are taken there). A
# value greater than 1 is read as the slow-tick threshold in MILLISECONDS -
# POC_TICK_STALL=400 flags ticks at or over 400 ms - because "1" is how one
# writes "on", and reading it as a 1 ms threshold would flag every tick.
#
# A tick at or over the threshold prints ONE line to stderr and appends the same
# line to poc_tick_stall.log; the summary is poc_tick_stall.txt, rewritten every
# _STALL_SUMMARY_EVERY ticks and on exit. Both live in the run directory the
# profile suite opened (artifacts/profile/ without --profile-dir), so this probe
# never writes into the source tree.
_STALL_DEFAULT_MS = 150.0
_STALL_MAX_WORST = 20  # tick records kept, worst first
_STALL_MAX_PHASE = 20000  # samples kept per phase
_STALL_MAX_GC = 4096  # gc events kept
_STALL_MAX_LINES = 200  # stderr lines; the rest are COUNTED, not printed
_STALL_SUMMARY_EVERY = 200  # ticks between summary rewrites
# A WINDOW is _STALL_WINDOW ticks. The worst tick of each window is kept for
# ONE reason: a periodic artefact (a screenshot every 100 ticks, a summary
# rewrite every 200) owns the same slot in every window, and a per-tick list
# of ten samples of that artefact cannot say so.
_STALL_WINDOW = 100
_STALL_MAX_WINDOWS = 100  # closed windows kept; the oldest is dropped
_STALL_MAX_WINDOW_ROWS = 5  # closed windows in the summary, newest last
# Fixed order for the phase columns, so two runs are read side by side.
_STALL_PHASE_ORDER = ("reanchor", "target", "draw", "flush", "yield")

_STALL = {
    "enabled": False,
    "threshold_ms": _STALL_DEFAULT_MS,
    "ticks": 0,
    "slow": 0,
    "worst": [],
    "window": None,  # the worst tick of the window in progress
    "windows": [],  # closed windows, oldest first
    "shot": None,  # {"tick": n, "ms": elapsed} of the last screenshot taken
    "phases": {},
    "gc": {},  # generation -> {"n", "total_ms", "max_ms"}
    "gc_events": [],
    "gc_ms_total": 0.0,
    "gc_t0": None,
    "gc_hooked": False,
    "lines_printed": 0,
    "lines_suppressed": 0,
    "last_tick_at": None,
    "tick": None,
    "flush": None,  # the breakdown of the push in flight
    "flush_last": None,  # the last completed one; the flush phase reads it
    "flush_phases": {},  # flush_render/flush_pub/flush_other -> samples
    "still_calls": 0,  # still_render calls, summed over every flush
    "stills_max": 0,  # worst single tick, in renders
    "protocol": (None, None, None),  # (delivery, still_render, publish) while hooked
    "protocol_hooked": False,
}


def _stall_env_enabled() -> bool:
    """True when POC_TICK_STALL asks for the probe (blank and "0" do not)."""
    value = os.environ.get("POC_TICK_STALL")
    return value is not None and value.strip() not in ("", "0")


def _stall_env_threshold() -> float:
    """The threshold POC_TICK_STALL names, in ms; the default when it only
    switches the probe on ("1") or names something unreadable."""
    raw = os.environ.get("POC_TICK_STALL")
    if raw is None:
        return _STALL_DEFAULT_MS
    try:
        value = float(raw.strip())
    except (TypeError, ValueError):
        return _STALL_DEFAULT_MS
    if value <= 1.0:
        return _STALL_DEFAULT_MS
    return value


def _stall_enabled() -> bool:
    """True while the probe is installed. The ONE gate the hooks use."""
    return bool(_STALL["enabled"])


# --- the flush breakdown ---------------------------------------------------
# The flush phase is where an image actually leaves the server, and it was ONE
# number. Two of its parts can be timed honestly from Python, and the rest is
# named as what it is - the residual:
#
#   flush_render - time inside the DELIVERY's ``still_render``, i.e.
#                  vtkWebApplication.StillRenderToBuffer: the render, the MSAA
#                  resolve, the framebuffer readback and the JPEG encode, all in
#                  C++. It is not divisible further from here - no Python line
#                  sees between readback and encode - so it keeps that one name.
#   flush_pub    - time inside the delivery's ``publish`` on OUR stack. The wire
#                  cost is deferred (wslink/publish.py:26-40 -> schedule_coroutine),
#                  so this is payload bookkeeping, not the socket.
#   flush_other  - the residual: the trame/pyvista shims, the renderer report, the
#                  timing tick-end and anything else inside the flush phase.
#
# Because flush_other is the residual, render + pub + other == flush by
# construction, which is the invariant the tests assert.
#
# ``still=N`` is the number of still_render CALLS in the tick. It is not always
# 1: push_render retries a stale image up to three times
# (publish_image_delivery.py:195-215), so a tick that reports still=3 paid for
# three renders. That is why the time ACCUMULATES and the count is reported.
_STALL_FLUSH_PARTS = (
    ("flush_render", "render"),
    ("flush_pub", "pub"),
    ("flush_other", "other"),
)


def _stall_flush_begin():
    """Open the breakdown for ONE push. None, and no clock, when the probe is off."""
    if not _STALL["enabled"]:
        return None
    try:
        rec = {"t0": _profile_now(), "ms": 0.0, "render_ms": 0.0, "pub_ms": 0.0, "stills": 0}
        _STALL["flush"] = rec
        return rec
    except Exception:  # noqa: BLE001
        return None


def _stall_flush_cancel(rec) -> None:
    """A push that RAISED leaves half a breakdown behind; drop it."""
    if rec is None:
        return
    if _STALL["flush"] is rec:
        _STALL["flush"] = None


def _stall_flush_end(rec):
    """Close the breakdown: how long the push took. Kept for the flush phase."""
    if rec is None:
        return None
    try:
        rec["ms"] = max(0.0, (_profile_now() - float(rec["t0"])) * 1000.0)
        _STALL["flush_last"] = rec
    except Exception:  # noqa: BLE001
        pass
    finally:
        if _STALL["flush"] is rec:
            _STALL["flush"] = None
    return rec


def _stall_flush_close(ms_total) -> None:
    """Split the flush phase into render/pub/other on the OPEN tick."""
    if not _STALL["enabled"]:
        return
    try:
        total = max(0.0, float(ms_total))
        parts = _STALL["flush_last"]
        if not isinstance(parts, dict):
            parts = {}
        render = max(0.0, float(parts.get("render_ms") or 0.0))
        pub = max(0.0, float(parts.get("pub_ms") or 0.0))
        other = max(0.0, total - render - pub)
        stills = int(parts.get("stills") or 0)
        tick = _STALL["tick"]
        if tick is not None:
            tick["flush"] = {
                "render": round(render, 3),
                "pub": round(pub, 3),
                "other": round(other, 3),
                "stills": stills,
            }
        for name, key in _STALL_FLUSH_PARTS:
            value = {"render": render, "pub": pub, "other": other}[key]
            bucket = _STALL["flush_phases"].get(name)
            if bucket is None:
                bucket = []
                _STALL["flush_phases"][name] = bucket
            bucket.append(round(value, 3))
            if len(bucket) > _STALL_MAX_PHASE:
                del bucket[: len(bucket) - _STALL_MAX_PHASE]
        _STALL["still_calls"] = int(_STALL["still_calls"]) + stills
        _STALL["stills_max"] = max(int(_STALL["stills_max"]), stills)
    except Exception:  # noqa: BLE001
        return


def _stall_delivery_for(view_handle=None):
    """The trame image-delivery object - the only thing that owns still_render.

    ``still_render`` is a method of vtkWebPublishImageDelivery
    (publish_image_delivery.py:10,159), NOT of the root protocol, so the root
    protocol is only the way to reach it: getLinkProtocols() is the very list
    getRPCMethod walks to build its dispatch table (trame_server/protocol.py:131).
    Nothing here raises; an unreachable delivery is a thinner report, not a crash.
    """
    protocols = []
    try:
        from trame.app import get_server

        protocols.append(getattr(get_server(), "protocol", None))
    except Exception:  # noqa: BLE001 - no server up (headless tests)
        pass
    try:
        protocols.append(getattr(getattr(view_handle, "_helper", None), "_root_protocol", None))
    except Exception:  # noqa: BLE001
        pass
    for protocol in protocols:
        if protocol is None:
            continue
        try:
            for link in protocol.getLinkProtocols():
                if callable(getattr(link, "still_render", None)):
                    return link
        except Exception:  # noqa: BLE001
            continue
    return None


def _stall_hook_protocol(view_handle=None) -> bool:
    """Wrap the delivery's still_render/publish so the flush can be split.

    INSTANCE attributes, not a class patch: the wrap dies with the delivery, and
    ``_stall_unhook_protocol`` puts the originals back, so a probe switched off
    leaves an object indistinguishable from a fresh one. Instance attributes also
    never enter ``rpcMethods`` (built from ``__class__`` members), so RPC dispatch
    is untouched. Only ever installed while the probe is on.
    """
    if not _STALL["enabled"] or _STALL["protocol_hooked"]:
        return False
    delivery = _stall_delivery_for(view_handle)
    if delivery is None:
        return False
    try:
        still = getattr(delivery, "still_render", None)
        publish = getattr(delivery, "publish", None)
        if not callable(still):
            return False

        def probe_still_render(options, _still=still):
            rec = _STALL["flush"]
            if rec is None:
                return _still(options)
            started = _profile_now()
            try:
                return _still(options)
            finally:
                # Accumulate: one push can render three times over a stale image.
                rec["render_ms"] = float(rec.get("render_ms") or 0.0) + max(
                    0.0, (_profile_now() - started) * 1000.0
                )
                rec["stills"] = int(rec.get("stills") or 0) + 1

        def probe_publish(topic, data, *args, _publish=publish, **kwargs):
            rec = _STALL["flush"]
            started = _profile_now()
            try:
                return _publish(topic, data, *args, **kwargs)
            finally:
                if rec is not None:
                    rec["pub_ms"] = float(rec.get("pub_ms") or 0.0) + max(
                        0.0, (_profile_now() - started) * 1000.0
                    )

        delivery.still_render = probe_still_render
        if callable(publish):
            delivery.publish = probe_publish
        _STALL["protocol"] = (delivery, still, publish)
        _STALL["protocol_hooked"] = True
        return True
    except Exception:  # noqa: BLE001 - an unhookable delivery is a thinner report
        return False


def _stall_unhook_protocol() -> bool:
    """Put the two methods back. Idempotent."""
    if not _STALL["protocol_hooked"]:
        return False
    delivery, still, publish = _STALL["protocol"] or (None, None, None)
    try:
        if delivery is not None:
            if still is not None:
                delivery.still_render = still
            if publish is not None:
                delivery.publish = publish
    except Exception:  # noqa: BLE001
        return False
    finally:
        _STALL["protocol"] = None
        _STALL["protocol_hooked"] = False
    return True


def _stall_threshold_ms() -> float:
    """The threshold this run flags at, in ms."""
    try:
        return float(_STALL["threshold_ms"])
    except (TypeError, ValueError):
        return _STALL_DEFAULT_MS


def _stall_dir():
    """The run directory: the profile suite's, so the artefacts stay together."""
    directory = _PROFILE.get("dir")
    if directory is not None:
        return directory
    return _PROFILE_DEFAULT_DIR


def _stall_path():
    """Where the summary is rewritten. None only if no path can be built."""
    try:
        return Path(_stall_dir()) / "poc_tick_stall.txt"
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return None


def _stall_log_path():
    """Where the per-slow-tick lines are appended."""
    try:
        return Path(_stall_dir()) / "poc_tick_stall.log"
    except Exception:  # noqa: BLE001
        return None


def _stall_reset() -> None:
    """Forget every sample. For the tests, and for a re-run."""
    _STALL["ticks"] = 0
    _STALL["slow"] = 0
    _STALL["worst"] = []
    _STALL["window"] = None
    _STALL["windows"] = []
    _STALL["shot"] = None
    _STALL["phases"] = {}
    _STALL["gc"] = {}
    _STALL["gc_events"] = []
    _STALL["gc_ms_total"] = 0.0
    _STALL["gc_t0"] = None
    _STALL["lines_printed"] = 0
    _STALL["lines_suppressed"] = 0
    _STALL["last_tick_at"] = None
    _STALL["tick"] = None
    _STALL["flush"] = None
    _STALL["flush_last"] = None
    _STALL["flush_phases"] = {}
    _STALL["still_calls"] = 0
    _STALL["stills_max"] = 0


def _stall_gc_start(info=None) -> None:
    """gc "start": take the clock. A NESTED collection keeps the outer one's."""
    if not _STALL["enabled"]:
        return
    if _STALL["gc_t0"] is not None:
        return
    _STALL["gc_t0"] = _profile_now()


def _stall_gc_stop(info=None, now=None) -> float:
    """gc "stop": how long that collection held the interpreter, in ms."""
    if not _STALL["enabled"]:
        return 0.0
    started = _STALL["gc_t0"]
    _STALL["gc_t0"] = None
    if started is None:
        return 0.0
    now = _profile_now() if now is None else float(now)
    ms = max(0.0, (float(now) - float(started)) * 1000.0)
    generation = None
    try:
        if info is not None:
            generation = int(info.get("generation"))
    except Exception:  # noqa: BLE001 - an info dict we do not recognise
        generation = None
    _STALL["gc_ms_total"] = float(_STALL["gc_ms_total"]) + ms
    if generation is not None:
        agg = _STALL["gc"].get(generation)
        if agg is None:
            agg = {"n": 0, "total_ms": 0.0, "max_ms": 0.0}
            _STALL["gc"][generation] = agg
        agg["n"] = int(agg["n"]) + 1
        agg["total_ms"] = round(float(agg["total_ms"]) + ms, 3)
        agg["max_ms"] = round(max(float(agg["max_ms"]), ms), 3)
    events = _STALL["gc_events"]
    events.append({"gen": generation, "ms": round(ms, 3)})
    if len(events) > _STALL_MAX_GC:
        del events[: len(events) - _STALL_MAX_GC]
    return ms


def _stall_gc_callback(phase, info=None) -> None:
    """One gc.callbacks entry: "start", "stop", and nothing else."""
    try:
        if phase == "start":
            _stall_gc_start(info)
        elif phase == "stop":
            _stall_gc_stop(info)
    except Exception:  # noqa: BLE001 - a gc callback that raises aborts the gc
        return


def _stall_install_gc() -> bool:
    """Turn the probe on and hook gc. Idempotent; POC_TICK_STALL is the switch."""
    if not _stall_env_enabled():
        return False
    _STALL["enabled"] = True
    _STALL["threshold_ms"] = _stall_env_threshold()
    if _STALL["gc_hooked"]:
        return True
    try:
        import gc as _gc

        _gc.callbacks.append(_stall_gc_callback)
        _STALL["gc_hooked"] = True
    except Exception:  # noqa: BLE001 - no hook is a thinner report, not a crash
        _STALL["gc_hooked"] = False
    return bool(_STALL["gc_hooked"])


def _stall_uninstall_gc() -> bool:
    """Turn the probe off and unhook gc. Idempotent."""
    hooked = bool(_STALL["gc_hooked"])
    _stall_unhook_protocol()
    _STALL["enabled"] = False
    _STALL["gc_t0"] = None
    if not hooked:
        return False
    try:
        import gc as _gc

        while _stall_gc_callback in _gc.callbacks:
            _gc.callbacks.remove(_stall_gc_callback)
        _STALL["gc_hooked"] = False
        return True
    except Exception:  # noqa: BLE001
        return False


def _stall_tick_begin(frame=None, mode=None):
    """Open a stall record. Called from _profile_tick_begin, never by a draw."""
    if not _STALL["enabled"]:
        return None
    try:
        now = _profile_now()
        previous = _STALL["last_tick_at"]
        _STALL["last_tick_at"] = now
        _STALL["ticks"] = int(_STALL["ticks"]) + 1
        # A tick that pushes nothing must NOT inherit the previous tick's parts.
        _STALL["flush_last"] = None
        tick = {
            "n": _STALL["ticks"],
            "frame": frame,
            "mode": mode,
            "t0": now,
            # The GAP is the beat BETWEEN two ticks. A long tick whose gap is
            # also long says the loop was asleep, not that the draw cost it.
            "gap_ms": (None if previous is None else round((now - previous) * 1000.0, 3)),
            "phases": {},
            "flush": None,
            "gc_ms0": float(_STALL["gc_ms_total"]),
        }
        _STALL["tick"] = tick
        return tick
    except Exception:  # noqa: BLE001
        return None


def _stall_phase(name, ms) -> None:
    """Add one phase sample: to the OPEN tick, and to the run's per-phase bucket."""
    if not _STALL["enabled"]:
        return
    try:
        value = float(ms)
    except (TypeError, ValueError):
        return
    try:
        tick = _STALL["tick"]
        if tick is not None:
            phases = tick["phases"]
            phases[name] = round(float(phases.get(name, 0.0)) + value, 3)
        bucket = _STALL["phases"].get(name)
        if bucket is None:
            bucket = []
            _STALL["phases"][name] = bucket
        bucket.append(round(value, 3))
        if len(bucket) > _STALL_MAX_PHASE:
            del bucket[: len(bucket) - _STALL_MAX_PHASE]
    except Exception:  # noqa: BLE001
        return


def _stall_mark_shot(ms, tick=None):
    """Mark the OPEN tick as the one that paid for a screenshot, and its ms.

    Called from _timing_screenshot - the only place that KNOWS a readback ran.
    Every ration gate lives there and nowhere else: a plotter that cannot
    screenshot, a client-rendered view (suppress_rendering), the every-100-ticks
    cadence and the 60-shot budget. Re-deriving that here from the tick number
    would mark ticks whose shot was refused, which is exactly the wrong answer.
    OFF is a no-op, and so is a record that is not open.
    """
    if not _STALL["enabled"]:
        return None
    try:
        value = float(ms)
    except (TypeError, ValueError):
        return None
    try:
        mark = {"tick": tick, "ms": round(value, 3)}
        _STALL["shot"] = mark
        open_tick = _STALL["tick"]
        if open_tick is not None:
            # _timing_tick_end runs inside _show, before _profile_tick_end closes
            # this record: the mark lands on the tick it belongs to.
            open_tick["shot_ms"] = mark["ms"]
        return mark
    except Exception:  # noqa: BLE001
        return None


def _stall_window_note(record) -> None:
    """Fold one closed tick into its 100-tick window, and close the window.

    The window is derived from the probe's OWN tick count (1-100, 101-200, ...)
    so it does not depend on any other suite's clock, and the last tick of a
    window is the only tick that closes it: a run shorter than one window still
    reports the window in progress, marked.
    """
    if not _STALL["enabled"]:
        return
    try:
        n = int(record["n"])
        window = (n - 1) // _STALL_WINDOW + 1
        slim = {
            "window": window,
            "n": n,
            "frame": record.get("frame"),
            "mode": record.get("mode"),
            "total_ms": float(record["total_ms"]),
            "gap_ms": record.get("gap_ms"),
            "shot_ms": record.get("shot_ms"),
            "slow": bool(record.get("slow")),
        }
        best = _STALL["window"]
        if best is None or int(best["window"]) != window:
            # A window that never saw its 100th tick (a reset, or the run
            # ending) is replaced, never merged: it is not a full window.
            _STALL["window"] = slim
        elif slim["total_ms"] > float(best["total_ms"]):
            # >= keeps the EARLIER tick on a tie: it is the one whose cost the
            # later tick may still be paying for.
            _STALL["window"] = slim
        if n % _STALL_WINDOW == 0:
            closed = _STALL["window"]
            if closed is not None:
                windows = _STALL["windows"]
                windows.append(closed)
                del windows[:-_STALL_MAX_WINDOWS]
            _STALL["window"] = None
    except Exception:  # noqa: BLE001
        return


def _stall_window_row(record, partial) -> str:
    """One window of the summary: the ticks it spans, its worst tick, its shot."""
    window = int(record["window"])
    first = (window - 1) * _STALL_WINDOW + 1
    last = window * _STALL_WINDOW
    gap = record.get("gap_ms")
    shot = record.get("shot_ms")
    line = "  %-6s %6d-%-6d %5d %8.1f %7s %7s  %5s %s" % (
        "w%d%s" % (window, "*" if partial else ""),
        first,
        last,
        int(record["n"]),
        float(record["total_ms"]),
        "-" if gap is None else "%.1f" % float(gap),
        "-" if shot is None else "%.1f" % float(shot),
        record.get("frame"),
        record.get("mode"),
    )
    # "slow" says the window's worst tick also crossed the threshold; without it
    # the row is the worst of a quiet window, which is worth its line too.
    return line + (" slow" if record.get("slow") else "")


def _stall_tick_end(row=None):
    """Close the record: total ms, the gc inside it, and whether it was slow."""
    if not _STALL["enabled"]:
        return None
    tick = _STALL["tick"]
    _STALL["tick"] = None
    if tick is None:
        return None
    try:
        total = max(0.0, (_profile_now() - tick["t0"]) * 1000.0)
        counts = {}
        if isinstance(row, dict):
            counts = dict(row.get("counts") or {})
        record = {
            "n": tick["n"],
            "frame": tick["frame"],
            "mode": tick["mode"],
            "total_ms": round(total, 3),
            "gap_ms": tick["gap_ms"],
            "phases": dict(tick["phases"]),
            "flush": tick.get("flush"),
            "gc_ms": round(float(_STALL["gc_ms_total"]) - float(tick["gc_ms0"]), 3),
            "counts": counts,
        }
        # The readback is charged to THIS tick (see _timing_screenshot): the mark
        # was left on the open record, so nothing has to be inferred from n.
        shot_ms = tick.get("shot_ms")
        record["shot_ms"] = None if shot_ms is None else round(float(shot_ms), 3)
        threshold = _stall_threshold_ms()
        record["slow"] = bool(total >= threshold)
        if record["slow"]:
            _STALL["slow"] = int(_STALL["slow"]) + 1
            _stall_note(record, threshold)
        worst = _STALL["worst"]
        worst.append(record)
        worst.sort(key=lambda item: item["total_ms"], reverse=True)
        del worst[_STALL_MAX_WORST:]
        _stall_window_note(record)
        if int(_STALL["ticks"]) % _STALL_SUMMARY_EVERY == 0:
            _stall_write_summary()
        return record
    except Exception:  # noqa: BLE001
        return None


def _stall_line(record, threshold) -> str:
    """The slow-tick line: field=value in a fixed order, so grep works on it."""
    phases = record.get("phases") or {}
    names = [name for name in _STALL_PHASE_ORDER if name in phases]
    names += [name for name in phases if name not in names]
    parts = [
        "[poc_app] slow tick %d/%d" % (record["n"], int(_STALL["ticks"])),
        "total=%.1fms" % float(record["total_ms"]),
        "threshold=%.1fms" % float(threshold),
        "gc=%.1fms" % float(record.get("gc_ms") or 0.0),
        "frame=%s" % (record.get("frame"),),
        "mode=%s" % (record.get("mode"),),
    ]
    for name in names:
        parts.append("%s=%.1fms" % (name, float(phases[name])))
    flush = record.get("flush") or {}
    for name, key in _STALL_FLUSH_PARTS:
        if key in flush:
            parts.append("%s=%.1fms" % (name, float(flush[key])))
    if "stills" in flush:
        # How many renders the push actually cost: a stale image is retried.
        parts.append("still=%d" % int(flush["stills"]))
    counts = record.get("counts") or {}
    for name in ("render", "push", "add_mesh"):
        if name in counts:
            parts.append("%s=%d" % (name, int(counts[name])))
    gap = record.get("gap_ms")
    if gap is not None:
        parts.append("gap=%.1fms" % float(gap))
    shot = record.get("shot_ms")
    if shot is not None:
        # Absent unless a screenshot really ran: tens of ms spent inside the
        # tick that reports them, and the first thing to blame when the slow
        # ticks line up on a 100-tick cadence.
        parts.append("shot=%.1fms" % float(shot))
    return " ".join(parts)


def _stall_note(record, threshold) -> bool:
    """Print ONE bounded line for a slow tick, and append it to the run's log."""
    try:
        text = _stall_line(record, threshold)
    except Exception:  # noqa: BLE001
        return False
    if int(_STALL["lines_printed"]) >= _STALL_MAX_LINES:
        # A run that stalls on every tick would otherwise bury itself in stderr.
        # The summary still COUNTS every slow tick; only the lines are dropped.
        _STALL["lines_suppressed"] = int(_STALL["lines_suppressed"]) + 1
        return False
    _STALL["lines_printed"] = int(_STALL["lines_printed"]) + 1
    try:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
    except Exception:  # noqa: BLE001
        pass
    try:
        path = _stall_log_path()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
    except Exception:  # noqa: BLE001 - no log file is not a crash
        pass
    return True


def _stall_summary_text() -> str:
    """<= 40 lines: the header, per-phase percentiles, gc per generation, worst."""
    if not _STALL["enabled"]:
        return ""
    try:
        threshold = _stall_threshold_ms()
        out = ["POC_TICK_STALL - slow-tick probe", "-" * 60]
        out.append("run dir: %s" % (_stall_dir(),))
        out.append(
            "ticks: %d  slow(>=%.1fms): %d  lines suppressed: %d"
            % (
                int(_STALL["ticks"]),
                threshold,
                int(_STALL["slow"]),
                int(_STALL["lines_suppressed"]),
            )
        )
        out.append("")
        out.append("phase (ms)         n     p50     p95     max")
        for name in _STALL_PHASE_ORDER:
            bucket = _STALL["phases"].get(name)
            if not bucket:
                continue
            stats = _profile_stats(bucket)
            out.append(
                "  %-10s %6d %7.1f %7.1f %7.1f"
                % (name, int(stats["n"]), stats["median"], stats["p95"], stats["max"])
            )
        # Only printed when something pushed: an empty table is noise, and the
        # summary is capped at 40 lines.
        flushes = len(_STALL["flush_phases"].get("flush_other") or [])
        if flushes:
            out.append("")
            out.append("flush breakdown (ms)      n     p50     p95     max")
            for name, _key in _STALL_FLUSH_PARTS:
                bucket = _STALL["flush_phases"].get(name)
                if not bucket:
                    continue
                stats = _profile_stats(bucket)
                out.append(
                    "  %-12s %6d %7.1f %7.1f %7.1f"
                    % (name, int(stats["n"]), stats["median"], stats["p95"], stats["max"])
                )
            out.append(
                "  stills/flush: mean %.2f max %d"
                % (float(_STALL["still_calls"]) / float(flushes), int(_STALL["stills_max"]))
            )
        out.append("")
        out.append("gc (ms)           n   total     max")
        for generation in sorted(_STALL["gc"]):
            agg = _STALL["gc"][generation]
            out.append(
                "  gen%-8d %6d %7.1f %7.1f"
                % (
                    generation,
                    int(agg["n"]),
                    float(agg["total_ms"]),
                    float(agg["max_ms"]),
                )
            )
        if not _STALL["gc"]:
            out.append(
                "  (none recorded - gc hook %s)" % ("on" if _STALL["gc_hooked"] else "OFF")
            )
        # Six, not ten: the window table below reports the same ticks a
        # second way, and the summary is capped at 40 lines.
        worst = _STALL["worst"][:6]
        if worst:
            out.append("")
            out.append("worst ticks:       n    total     gap      gc   frame mode")
            for record in worst:
                gap = record.get("gap_ms")
                out.append(
                    "  %14d %8.1f %7s %7.1f  %5s %s"
                    % (
                        int(record["n"]),
                        float(record["total_ms"]),
                        "-" if gap is None else "%.1f" % float(gap),
                        float(record.get("gc_ms") or 0.0),
                        record.get("frame"),
                        record.get("mode"),
                    )
                )
        # One line per window (plus the one in progress, marked *): a periodic
        # stall repeats in the same slot of every window, and this is the table
        # that shows the repeat instead of ten samples of it.
        closed = _STALL["windows"][-_STALL_MAX_WINDOW_ROWS:]
        open_window = _STALL["window"]
        if closed or open_window is not None:
            out.append("")
            out.append(
                "worst tick per %d-tick window:  window     ticks     n    total      gap  shot_ms  frame mode"
                % _STALL_WINDOW
            )
            for window in closed:
                out.append(_stall_window_row(window, False))
            if open_window is not None:
                out.append(_stall_window_row(open_window, True))
        return "\n".join(out[:40]) + "\n"
    except Exception:  # noqa: BLE001 - a summary is not the app
        return ""


def _stall_write_summary() -> str:
    """Rewrite poc_tick_stall.txt. Returns the text either way."""
    if not _STALL["enabled"]:
        return ""
    try:
        text = _stall_summary_text()
    except Exception:  # noqa: BLE001
        return ""
    try:
        path = _stall_path()
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return text


def _profile_configure(
    enabled=True,
    directory=None,
    clock=None,
    process_clock=None,
    rusage=None,
    start_threads=True,
    register_exit=False,
):
    """Turn the suite on and open its files. Returns the run directory or None.

    A directory that cannot be created costs the run its telemetry, never the
    viewer: the in-memory records keep working with no files behind them.
    """
    if clock is not None:
        _PROFILE["clock"] = clock
    if process_clock is not None:
        _PROFILE["process_clock"] = process_clock
    if rusage is not None:
        _PROFILE["rusage"] = rusage
    _PROFILE["enabled"] = bool(enabled)
    if not _PROFILE["enabled"]:
        _PROFILE["dir"] = None
        _PROFILE["files"] = {}
        # The stall probe leans on this block's marks, so it cannot outlive it.
        _stall_uninstall_gc()
        return None
    import collections

    if _PROFILE["stacks"] is None:
        _PROFILE["stacks"] = collections.Counter()
    if _PROFILE["started"] is None:
        _PROFILE["started"] = _profile_now()
    _PROFILE["mark_at"] = _PROFILE["started"]
    if _PROFILE["stamp"] is None:
        _PROFILE["stamp"] = time.strftime("%Y%m%dT%H%M%S")
    root = Path(directory) if directory is not None else _PROFILE_DEFAULT_DIR
    try:
        if not root.is_absolute():
            root = (Path(__file__).resolve().parent.parent / root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        stamp = _PROFILE["stamp"]
        _PROFILE["dir"] = root
        _PROFILE["files"] = {
            "ticks": root / f"ticks_{stamp}.jsonl",
            "stacks": root / f"stacks_{stamp}.txt",
            "summary": root / f"summary_{stamp}.txt",
        }
    except Exception:  # noqa: BLE001 - no directory is not a crash
        _PROFILE["dir"] = None
        _PROFILE["files"] = {}
    # Installed HERE and nowhere else: POC_TICK_STALL is the switch, this block is
    # the carrier, and a probe whose marks are never taken must not claim to be on.
    _stall_install_gc()
    if register_exit:
        _profile_register_exit()
    if start_threads:
        _profile_start_thread()
    return _PROFILE["dir"]


def _profile_write(kind, line) -> bool:
    """Append ONE line to one of the run's files. Never raises."""
    path = _PROFILE["files"].get(kind)
    if path is None:
        return False
    try:
        text = line if line.endswith("\n") else line + "\n"
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)
        return True
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return False


def _profile_count(name, n=1) -> None:
    """Count one instrumented call: render / add_mesh / remove_actor."""
    try:
        _PROFILE["counts"][name] = int(_PROFILE["counts"].get(name, 0)) + int(n)
        _PROFILE["tick_counts"][name] = (
            int(_PROFILE["tick_counts"].get(name, 0)) + int(n)
        )
    except Exception:  # noqa: BLE001
        return


def _profile_attach(plotter) -> bool:
    """Wrap render/add_mesh/remove_actor ON THE INSTANCE so every call counts.

    pyvista renders for itself - ``add_mesh`` draws unless told not to - so a
    counter at OUR call sites would report one draw where the library started
    three. The wrappers are instance attributes, so they shadow the class
    methods on this plotter only. A layer that swaps ``plotter.render`` for a
    mute while it builds bypasses the wrapper for the muted calls, which is the
    honest reading: those calls never reached the GL draw.
    """
    if plotter is None or getattr(plotter, "_tm_profile_hooked", False):
        return False
    for name in ("render", "add_mesh", "remove_actor"):
        try:
            inner = getattr(plotter, name, None)
        except Exception:  # noqa: BLE001
            inner = None
        if not callable(inner):
            continue

        def _make(inner=inner, name=name):
            def _wrapped(*args, **kwargs):
                _profile_count(name)
                return inner(*args, **kwargs)

            _wrapped.__name__ = name
            return _wrapped

        try:
            setattr(plotter, name, _make())
        except Exception:  # noqa: BLE001 - a plotter that refuses is not fatal
            return False
    try:
        plotter._tm_profile_hooked = True
    except Exception:  # noqa: BLE001
        pass
    return True


def _profile_flush_pending() -> bool:
    """Write the closed-but-unwritten tick row. Called by the NEXT tick."""
    row = _PROFILE["pending"]
    if row is None:
        return False
    _PROFILE["pending"] = None
    try:
        return _profile_write("ticks", json.dumps(row, separators=(",", ":")))
    except Exception:  # noqa: BLE001
        return False


def _profile_num(value):
    """JSON-safe number: int when it is one, else float, else None."""
    if value is None or isinstance(value, bool):
        return None if value is None else value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _profile_tick_begin(frame=None, mode=None):
    """Open a tick record. Called BEFORE anything else the tick does."""
    if not _PROFILE["enabled"]:
        return None
    try:
        _profile_flush_pending()
        now = _profile_now()
        _PROFILE["ticks"] = int(_PROFILE["ticks"]) + 1
        # Per-tick counts start at zero - except the ones a play-loop gate took
        # BETWEEN ticks: those beats are skipped before _show, so they never open
        # a tick of their own and their counts are carried to the row this tick
        # is about to write instead of being wiped here.
        _PROFILE["tick_counts"] = {
            name: _PROFILE["tick_counts"][name]
            for name in _PROFILE_GATE_COUNTS
            if name in _PROFILE["tick_counts"]
        }
        _PROFILE["last_tick_at"] = now
        _PROFILE["mark_at"] = now
        # The delivery totals AS THE TICK OPENS: the row reports what trame did
        # between this snapshot and the one taken when the tick closes.
        _PROFILE["tick_snap"] = _profile_delivery_snapshot()
        tick = {
            "kind": "tick",
            "n": _PROFILE["ticks"],
            "t": round(_profile_elapsed(now), 3),
            "frame_asked": _profile_num(frame),
            "frame_published": None,
            "mode": mode,
            "wall_ms": None,
            "phases": {},
            "sheets": [],
            "assigned": [],
            "in_place": [],
            "counts": {},
            "actors": None,
            "_t0": now,
        }
        _PROFILE["tick"] = tick
        # The stall probe opens its own record at the SAME instant, so the two
        # totals describe one tick rather than two neighbouring ones.
        _stall_tick_begin(frame, mode)
        return tick
    except Exception:  # noqa: BLE001
        return None


def _profile_phase(name) -> float:
    """Close the open phase: its wall time is the time since the last mark."""
    if not _PROFILE["enabled"]:
        return 0.0
    try:
        now = _profile_now()
        ms = _profile_since_mark(now) * 1000.0
        tick = _PROFILE["tick"]
        if tick is not None:
            phases = tick["phases"]
            phases[name] = round(float(phases.get(name, 0.0)) + ms, 3)
        # The same ms, to the probe that asks which phase a slow tick burned.
        _stall_phase(name, ms)
        if name == "flush":
            # The push recorded its own parts; split the phase with them.
            _stall_flush_close(ms)
        return ms
    except Exception:  # noqa: BLE001
        return 0.0


def _profile_sheet_begin(key, mesh=None):
    """Open one cut sheet's record: the clock, and the array it holds now."""
    if not _PROFILE["enabled"]:
        return None
    buf = None
    try:
        if mesh is not None and "ez_abs" in mesh.point_data:
            buf = mesh.point_data["ez_abs"]
    except Exception:  # noqa: BLE001
        buf = None
    return {"key": key, "t0": _profile_now(), "buf": buf}


def _profile_sheet_end(rec, index=None, mesh=None):
    """Close one sheet's record: ms, the index drawn, and WHICH kind of write.

    ``changed`` is the waste metric: a sheet repainted at the index it already
    held costs a full array upload and shows the operator the identical picture.
    ``in_place`` separates ``point_data[k] = fresh_array`` (rebinds, what the
    sheet loop does) from ``point_data[k][:] = data`` (writes the buffer that is
    already there) - the two cost very different things.
    """
    if not _PROFILE["enabled"] or rec is None:
        return None
    try:
        now = _profile_now()
        ms = (now - rec["t0"]) * 1000.0
        agg = _PROFILE["sheets"].get(rec["key"])
        if agg is None:
            agg = {
                "key": rec["key"],
                "repaints": 0,
                "ms": 0.0,
                "noop": 0,
                "index_changes": 0,
                "assigned": 0,
                "in_place": 0,
                "last_index": None,
            }
            _PROFILE["sheets"][rec["key"]] = agg
        changed = agg["last_index"] is None or index != agg["last_index"]
        old_buf = rec.get("buf")
        new_buf = old_buf
        try:
            if mesh is not None and "ez_abs" in mesh.point_data:
                new_buf = mesh.point_data["ez_abs"]
        except Exception:  # noqa: BLE001
            new_buf = old_buf
        # Which KIND of write this was - and, when there is no buffer to compare,
        # UNKNOWN: an unreadable buffer must never be counted as in-place.
        in_place = None
        if old_buf is not None and new_buf is not None:
            in_place = bool(new_buf is old_buf)
        agg["repaints"] += 1
        agg["ms"] += ms
        agg["last_index"] = index
        if changed:
            agg["index_changes"] += 1
        else:
            agg["noop"] += 1
        if in_place is True:
            agg["in_place"] += 1
        elif in_place is False:
            agg["assigned"] += 1
        row = {
            "key": rec["key"],
            "ms": round(ms, 3),
            "index": _profile_num(index),
            "changed": bool(changed),
            "in_place": in_place,
        }
        tick = _PROFILE["tick"]
        if tick is not None:
            tick["sheets"].append(row)
            if in_place is True:
                tick["in_place"].append(rec["key"])
            elif in_place is False:
                tick["assigned"].append(rec["key"])
        return row
    except Exception:  # noqa: BLE001
        return None


def _profile_tick_end(frame_published=None, plotter=None, mode=None):
    """Close the tick. Its row is PARKED until the yield mark has been seen."""
    if not _PROFILE["enabled"]:
        return None
    try:
        tick = _PROFILE["tick"]
        if tick is None:
            return None
        now = _profile_now()
        tick["wall_ms"] = round(_profile_tick_wall(now), 3)
        if frame_published is not None:
            tick["frame_published"] = _profile_num(frame_published)
        if mode is not None:
            tick["mode"] = mode
        tick["counts"] = dict(_PROFILE["tick_counts"])
        # Emptied HERE as well as in _profile_tick_begin: the carry above must
        # not hand a gate count to the row after the one it was attached to.
        _PROFILE["tick_counts"] = {}
        # What the IMAGE-DELIVERY path did during this tick: pushes attempted,
        # pushes that reached the encoder, the stills it encoded and their cost.
        tick.update(_profile_delivery_delta())
        try:
            tick["actors"] = len(plotter.actors) if plotter is not None else None
        except Exception:  # noqa: BLE001
            tick["actors"] = None
        # ONE row object, shared by the in-memory list and the parked write: the
        # yield mark lands in the file only if it lands in the same row the
        # write will serialise.
        row = {key: val for key, val in tick.items() if not key.startswith("_")}
        _PROFILE["rows"].append(row)
        if len(_PROFILE["rows"]) > _PROFILE_MAX_ROWS:
            del _PROFILE["rows"][: len(_PROFILE["rows"]) - _PROFILE_MAX_ROWS]
        _PROFILE["tick"] = None
        _PROFILE["pending"] = row
        # Handed the SAME row, so a slow-tick line can say whether that tick drew.
        _stall_tick_end(row)
        if int(_PROFILE["ticks"]) % _PROFILE_SUMMARY_EVERY == 0:
            _profile_write_summary()
        return tick
    except Exception:  # noqa: BLE001
        return None


def _profile_tick_wall(now=None) -> float:
    """Wall time of the OPEN tick, ms, from its begin to ``now``.

    The WHOLE tick, not the sum of the named phases: the difference between the
    two is the time that went somewhere the marks do not cover, and hiding it
    would make the phases look like they add up when they do not.
    """
    tick = _PROFILE["tick"]
    if tick is None:
        return 0.0
    start = tick.get("_t0")
    if start is None:
        return 0.0
    return ((_profile_now() if now is None else float(now)) - start) * 1000.0


def _profile_yield() -> float:
    """Record the publish -> sleep-return span on the tick that just closed."""
    if not _PROFILE["enabled"]:
        return 0.0
    try:
        now = _profile_now()
        ms = _profile_since_mark(now) * 1000.0
        row = _PROFILE["pending"]
        if row is None and _PROFILE["rows"]:
            row = _PROFILE["rows"][-1]
        if row is not None:
            phases = row.setdefault("phases", {})
            phases["yield"] = round(float(phases.get("yield", 0.0)) + ms, 3)
        # The yield is the one phase that lands AFTER the tick closed, so the
        # stall row was already written: the sample goes to the run's buckets.
        _stall_phase("yield", ms)
        return ms
    except Exception:  # noqa: BLE001
        return 0.0


def _profile_lag_sample(now=None):
    """One loop-lag sample: how LATE the 50 ms sampler woke, in ms.

    A thread that must reacquire the GIL to wake is a fair proxy for an event
    loop that cannot hand a frame to the websocket: both are blocked by the same
    synchronous draw under the same GIL.
    """
    if not _PROFILE["enabled"]:
        return None
    try:
        now = _profile_now() if now is None else float(now)
        last = _PROFILE["lag_at"]
        _PROFILE["lag_at"] = now
        if last is None:
            return None
        lag = max(0.0, (now - last) * 1000.0 - _PROFILE_LAG_EVERY_S * 1000.0)
        _PROFILE["lag"].append(round(lag, 3))
        return lag
    except Exception:  # noqa: BLE001
        return None


def _profile_stack_sample(now=None, frames=None):
    """Aggregate every live thread's INNERMOST frame into the stack counter."""
    if not _PROFILE["enabled"]:
        return None
    try:
        if frames is None:
            frames = sys._current_frames()
        if _PROFILE["stacks"] is None:
            import collections

            _PROFILE["stacks"] = collections.Counter()
        now = _profile_now() if now is None else float(now)
        leaves = {}
        for _ident, frame in list(frames.items()):
            try:
                code = frame.f_code
            except Exception:  # noqa: BLE001
                continue
            key = f"{os.path.basename(code.co_filename)}:{code.co_name}"
            leaves[key] = leaves.get(key, 0) + 1
            _PROFILE["stacks"][key] += 1
        stamp = _profile_elapsed(now)
        top = sorted(leaves.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
        _profile_write(
            "stacks",
            "t=%.2fs threads=%d %s"
            % (stamp, len(leaves), ", ".join(f"{n}x {k}" for k, n in top)),
        )
        return leaves
    except Exception:  # noqa: BLE001
        return None


def _profile_idle_sample(now=None, cpu=None, utime=None, stime=None, counts=None):
    """One IDLE record: the CPU this process burned while it drew nothing.

    Only recorded when NO tick has run for _PROFILE_IDLE_GAP_S - that is the
    window in which an idle viewer should be free.
    """
    if not _PROFILE["enabled"]:
        return None
    try:
        now = _profile_now() if now is None else float(now)
        last_tick = _PROFILE["last_tick_at"]
        if last_tick is not None and (now - last_tick) < _PROFILE_IDLE_GAP_S:
            return None
        if cpu is None:
            cpu = float(_PROFILE["process_clock"]())
        if utime is None or stime is None:
            utime, stime = _profile_rusage()
        current = dict(_PROFILE["counts"] if counts is None else counts)
        prev = _PROFILE["idle_prev"]
        if prev is None:
            _PROFILE["idle_prev"] = {
                "t": now,
                "cpu": cpu,
                "utime": utime,
                "stime": stime,
                "counts": current,
            }
            return None
        span = now - prev["t"]
        delta = {
            key: int(value) - int(prev["counts"].get(key, 0))
            for key, value in current.items()
        }
        row = {
            "kind": "idle",
            "t": round(_profile_elapsed(now), 3),
            "idle_s": round(span, 3),
            "process_s": round(cpu - prev["cpu"], 4),
            "utime_s": round(utime - prev["utime"], 4),
            "stime_s": round(stime - prev["stime"], 4),
            "cpu_per_s": round((cpu - prev["cpu"]) / span, 4) if span > 0 else None,
            "counts": delta,
        }
        _PROFILE["idle_prev"] = {
            "t": now,
            "cpu": cpu,
            "utime": utime,
            "stime": stime,
            "counts": current,
        }
        _PROFILE["idle"].append(row)
        # The file is read in order: a parked tick row goes out FIRST, or the
        # idle record of an idle stretch would appear above the tick that ended
        # it.
        _profile_flush_pending()
        _profile_write("ticks", json.dumps(row, separators=(",", ":")))
        return row
    except Exception:  # noqa: BLE001
        return None


def _profile_start_thread():
    """Start the ONE sampler thread: lag 50 ms, stacks 200 ms, idle 1 s."""
    try:
        import threading

        if _PROFILE["thread"] is not None and _PROFILE["thread"].is_alive():
            return _PROFILE["thread"]
        _PROFILE["stop"] = False
        _PROFILE["lag_at"] = _profile_now()
        _PROFILE["stack_at"] = _PROFILE["lag_at"]
        _PROFILE["idle_at"] = _PROFILE["lag_at"]

        def _run():
            while not _PROFILE["stop"]:
                try:
                    time.sleep(_PROFILE_LAG_EVERY_S)
                    now = _profile_now()
                    _profile_lag_sample(now)
                    stack_at = _PROFILE["stack_at"]
                    if stack_at is None or now - stack_at >= _PROFILE_STACK_EVERY_S:
                        _PROFILE["stack_at"] = now
                        _profile_stack_sample(now)
                    idle_at = _PROFILE["idle_at"]
                    if idle_at is None or now - idle_at >= _PROFILE_IDLE_EVERY_S:
                        _PROFILE["idle_at"] = now
                        _profile_idle_sample(now)
                except Exception:  # noqa: BLE001 - a sampler that dies is silent
                    continue

        thread = threading.Thread(target=_run, name="tm-profile", daemon=True)
        thread.start()
        _PROFILE["thread"] = thread
        return thread
    except Exception:  # noqa: BLE001
        return None


def _profile_stop_thread() -> None:
    """Ask the sampler thread to stop. It is a daemon; this only tidies."""
    _PROFILE["stop"] = True
    _PROFILE["thread"] = None


def _profile_stats(values):
    """_timing_stats() with an empty bucket spelled out, so a summary never raises."""
    stats = _timing_stats(values)
    if stats is None:
        return {"n": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    return stats


# ---------------------------------------------------------------------------
# --profile: the IMAGE-DELIVERY path.
#
# The tick block above answers what OUR loop cost. It cannot see the other half
# of a frame's journey: trame's vtkWebPublishImageDelivery runs its own VTK
# observers, decides for itself whether an update becomes an encoded jpeg, and
# DROPS the update outright while a view is animating - it schedules a callback
# instead. From here, a tick that pushed and a tick whose image was thrown away
# look identical, so the counters live where that decision is made.
#
# The delivery instance is built inside ``server.start()`` (trame registers the
# link protocol from a configure callback, which runs at wslink server creation),
# so there is no instance to wrap when the boot code runs. The CLASS is wrapped
# instead: whichever instance the server later builds inherits the counters, and
# every wrapper DELEGATES to the bound method it replaced, so a run without
# --profile executes trame's own functions untouched.
# ---------------------------------------------------------------------------
_PROFILE_DELIVERY_METHODS = (
    "push_render",
    "still_render",
    "animate",
    "start_view_animation",
    "stop_view_animation",
)
_PROFILE_DELIVERY_EVENTS = (
    "start_interaction",
    "end_interaction",
    "animation_start",
    "animation_stop",
)
_PROFILE_DELIVERY_MAX_EVENTS = 40


def _profile_push_record(delivery, v_id, ignore_animation=False):
    """Count ONE push_render attempt, and WHY it did or did not reach the encoder.

    The three early returns in ``push_render`` are replayed here, in its own
    order, against the state it reads: ``rendered`` therefore counts the attempts
    that really got to ``still_render``, and each drop is attributed to the reason
    the library would have given rather than to "no image came out".
    """
    try:
        push = _PROFILE["push"]
        push["attempts"] = int(push["attempts"]) + 1
        tracking = getattr(delivery, "tracking_views", None)
        if not isinstance(tracking, dict) or v_id not in tracking:
            push["dropped_untracked"] = int(push["dropped_untracked"]) + 1
            return "dropped_untracked"
        info = tracking.get(v_id) or {}
        try:
            enabled = bool(info["enabled"])
        except (KeyError, TypeError):
            enabled = True
        if not enabled:
            push["dropped_disabled"] = int(push["dropped_disabled"]) + 1
            return "dropped_disabled"
        if not ignore_animation and getattr(delivery, "views_in_animations", None):
            push["dropped_animation"] = int(push["dropped_animation"]) + 1
            return "dropped_animation"
        push["rendered"] = int(push["rendered"]) + 1
        return "rendered"
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return None


def _profile_image_bytes(reply):
    """The encoded frame in a still_render reply, in bytes - None when there is none.

    ``decode=False`` is how this app's delivery is built, so ``reply["image"]``
    is already bytes and its length IS the payload. A reply with no image has no
    size, which is counted as no size rather than as a zero-byte frame.
    """
    if not isinstance(reply, dict):
        return None
    image = reply.get("image")
    if image is None:
        return None
    try:
        return len(image)
    except TypeError:
        return None


def _profile_still_record(t0, reply, now=None):
    """Record one still_render: how long the encode took, and how big it came out."""
    try:
        end = _profile_now() if now is None else float(now)
        still = _PROFILE["still"]
        ms = (end - float(t0)) * 1000.0
        still["n"] = int(still["n"]) + 1
        still["ms"].append(ms)
        still["total_ms"] = float(still["total_ms"]) + ms
        size = _profile_image_bytes(reply)
        if size is not None:
            still["bytes"].append(size)
            still["total_bytes"] = int(still["total_bytes"]) + size
        return ms
    except Exception:  # noqa: BLE001
        return None


def _profile_animate_record(delivery, now=None):
    """Record one animate() call: the rate it settled on, and the animated span.

    ``in_animation_s`` is the wall time between consecutive animate() calls WHILE
    a view is animating - the stretch in which trame drops every push it did not
    ask for. A parked frame belongs beside that number, not beside the tick rate.
    """
    try:
        end = _profile_now() if now is None else float(now)
        anim = _PROFILE["animate"]
        anim["calls"] = int(anim["calls"]) + 1
        try:
            anim["last_target_fps"] = float(delivery.target_frame_rate)
        except (AttributeError, TypeError, ValueError):
            anim["last_target_fps"] = None
        previous = anim["last_at"]
        if previous is not None and getattr(delivery, "views_in_animations", None):
            span = end - float(previous)
            if span > 0:
                anim["in_animation_s"] = float(anim["in_animation_s"]) + span
        anim["last_at"] = end
        return end
    except Exception:  # noqa: BLE001
        return None


def _profile_client_record(kind="animation_start", now=None, detail=None):
    """Record one interaction edge, with the time since the run started.

    ``detail`` is an optional dict of extra facts the edge carries (a seek says
    where it came from and where it went). It is added to the event only, never
    to the counts, so an edge that is not one of the delivery kinds still costs
    the summary nothing but its own line.
    """
    try:
        end = _profile_now() if now is None else float(now)
        client = _PROFILE["client"]
        event = {"t": round(_profile_elapsed(end), 3), "kind": str(kind)}
        if detail:
            event.update((str(key), value) for key, value in dict(detail).items())
        client["events"].append(event)
        if kind in _PROFILE_DELIVERY_EVENTS:
            client[kind] = int(client[kind]) + 1
        return kind
    except Exception:  # noqa: BLE001
        return None


def _profile_seek(handles, position):
    """Record a slider seek as a client "seek" edge - only when profiled.

    ``position`` is where the slider landed; where it came FROM is added when
    the handles already know it, so a jump of 400 frames reads as a jump rather
    than as one more tick. Nothing is drawn differently by this.
    """
    if not _PROFILE["enabled"]:
        return None
    detail = {"to": position}
    previous = handles.get("frame_seen")
    if previous is not None:
        detail["from"] = previous
    return _profile_client_record("seek", detail=detail)


def _profile_client_kind(default):
    """start_/end_interaction when a VTK observer called us, else ``default``.

    The delivery registers named closures on Start/EndInteractionEvent, so a drag
    the USER began in the view is told apart from an animation a client asked for
    over the wire by the caller's code name. Anything unreadable keeps
    ``default``: guessing here would invent a fact about where the edge came from.
    """
    try:
        name = sys._getframe(2).f_code.co_name
    except Exception:  # noqa: BLE001 - no frames to look at
        return default
    if name == "start_callback":
        return "start_interaction"
    if name == "stop_callback":
        return "end_interaction"
    return default


def _profile_delivery_snapshot():
    """The five running delivery totals a tick row reports the DELTA of."""
    try:
        return {
            "push_attempts": int(_PROFILE["push"]["attempts"]),
            "push_rendered": int(_PROFILE["push"]["rendered"]),
            "push_dropped_animation": int(_PROFILE["push"]["dropped_animation"]),
            "still_ms": float(_PROFILE["still"]["total_ms"]),
            "in_animation_s": float(_PROFILE["animate"]["in_animation_s"]),
        }
    except Exception:  # noqa: BLE001
        return None


def _profile_delivery_delta():
    """What the delivery path did DURING the tick that is closing."""
    snap = _PROFILE["tick_snap"]
    now = _profile_delivery_snapshot()
    if not isinstance(snap, dict) or now is None:
        return {}
    out = {}
    for key, value in now.items():
        change = value - snap.get(key, 0)
        out[key] = round(float(change), 3) if isinstance(value, float) else int(change)
    return out


# The ONE delivery object trame built for this process, remembered so the pump can
# ask it a question that is not about profiling: is the client mid-animation?
# ``PublishImageDelivery`` keeps the views it is animating in a plain list
# (publish_image_delivery.py:21 ``self.views_in_animations = []``), and while that
# list is non-empty its ``push_render`` returns early (:26-35), i.e. a still the
# server asks for now would be DISCARDED - the position it carries would be lost
# from the sequence on screen while the pump counted it as painted. The pump reads
# this instead of guessing, so "painted" keeps meaning "on screen".
_DELIVERY_INSTANCE = None


def _remember_delivery(instance):
    """Remember ``instance`` as the delivery object the pump may consult.

    Called from every wrapper, BEFORE the profiling gate, because the pump needs
    this answer with the suite OFF - it is a correctness fact about delivery, not
    telemetry, and a run without ``--profile`` must not animate any differently.
    """
    global _DELIVERY_INSTANCE
    _DELIVERY_INSTANCE = instance


def _delivery_animating():
    """True/False from the live delivery's view list; None when unknowable.

    ``None`` is "nobody told us" (no delivery object yet, an attribute a future
    trame renamed, a list that will not measure) and is treated as NOT animating by
    the pump: refusing to paint on a guess would freeze a playback the operator can
    see is stuck. A False/True answer is used as given. Never raises - it is read
    inside the playback loop, where an exception would end the playback.
    """
    instance = _DELIVERY_INSTANCE
    if instance is None:
        return None
    try:
        views = getattr(instance, "views_in_animations")
        return len(views) > 0
    except Exception:  # noqa: BLE001 - an unreadable list is not an answer
        return None


def _profile_wrap_delivery(cls):
    """Wrap the five delivery methods ON ``cls``. True once they are wrapped.

    Idempotent (the class carries the marker) and signature-agnostic: each wrapper
    forwards ``*args, **kwargs`` untouched, so a trame release that changes a
    signature changes nothing here except how much is measured.
    """
    if getattr(cls, "_tm_profile_wrapped", False):
        return True
    originals = {}
    for name in _PROFILE_DELIVERY_METHODS:
        inner = getattr(cls, name, None)
        if not callable(inner):
            return False
        originals[name] = inner

    def push_render(self, *args, **kwargs):
        _remember_delivery(self)
        if _PROFILE["enabled"]:
            v_id = args[0] if args else kwargs.get("v_id")
            ignore = args[1] if len(args) > 1 else kwargs.get("ignore_animation", False)
            _profile_push_record(self, v_id, ignore)
        return originals["push_render"](self, *args, **kwargs)

    def still_render(self, *args, **kwargs):
        _remember_delivery(self)
        if not _PROFILE["enabled"]:
            return originals["still_render"](self, *args, **kwargs)
        t0 = _profile_now()
        reply = None
        try:
            reply = originals["still_render"](self, *args, **kwargs)
        finally:
            # Recorded even when the encode raised: a still that took 400 ms and
            # then failed is not a still that took no time.
            _profile_still_record(t0, reply)
        return reply

    def animate(self, *args, **kwargs):
        _remember_delivery(self)
        if _PROFILE["enabled"]:
            _profile_animate_record(self)
        return originals["animate"](self, *args, **kwargs)

    def start_view_animation(self, *args, **kwargs):
        _remember_delivery(self)
        if _PROFILE["enabled"]:
            _profile_client_record(_profile_client_kind("animation_start"))
        return originals["start_view_animation"](self, *args, **kwargs)

    def stop_view_animation(self, *args, **kwargs):
        _remember_delivery(self)
        if _PROFILE["enabled"]:
            _profile_client_record(_profile_client_kind("animation_stop"))
        return originals["stop_view_animation"](self, *args, **kwargs)

    for name, wrapper in (
        ("push_render", push_render),
        ("still_render", still_render),
        ("animate", animate),
        ("start_view_animation", start_view_animation),
        ("stop_view_animation", stop_view_animation),
    ):
        wrapper.__name__ = name
        wrapper.__doc__ = originals[name].__doc__
        # wslink finds its RPCs by a marker in the FUNCTION's own __dict__ and
        # reads the CLASS attribute (protocol.py: ``"_wslinkuris" in
        # proc.__dict__``), so a wrapper that dropped it would silently
        # unregister viewport.image.animation.start / .stop. The metadata is
        # carried over verbatim; everything else about the wrapper is ours.
        try:
            wrapper.__dict__.update(getattr(originals[name], "__dict__", {}))
        except Exception:  # noqa: BLE001 - metadata that will not copy is not fatal
            pass
        try:
            setattr(cls, name, wrapper)
        except Exception:  # noqa: BLE001 - a class that refuses is not fatal
            return False
    try:
        cls._tm_profile_wrapped = True
    except Exception:  # noqa: BLE001
        pass
    return True


def _profile_hook_delivery():
    """Install the delivery wrappers. False (never an exception) when it cannot.

    Called once, from ``main``, ALWAYS - with the suite on or off. The wrappers
    used to be installed only under ``--profile``, which quietly made the pump's
    knowledge of delivery a side effect of a telemetry flag: with the suite off the
    loop could not tell that the client was mid-animation and went on advancing
    positions into stills trame discarded. What the wrappers are FOR is split in
    two now - the "remember the delivery object" step runs either way, the counting
    behind it stays gated on ``_PROFILE["enabled"]`` - so the pump sees the same
    delivery in both modes while an unmeasured run pays only a global assignment
    per call.

    An image without trame_vtk has no delivery to watch, and a run that lost half
    its telemetry is still a run. The summary then says ``available=no`` instead of
    reporting five zeros as if the delivery had been watched and found idle.
    """
    if _PROFILE["delivery_hooked"]:
        return True
    try:
        from trame_vtk.modules.vtk.protocols.publish_image_delivery import (
            vtkWebPublishImageDelivery,
        )
    except Exception:  # noqa: BLE001 - a trame that is not installed is not an error
        _PROFILE["push"]["available"] = False
        return False
    try:
        wrapped = _profile_wrap_delivery(vtkWebPublishImageDelivery)
    except Exception:  # noqa: BLE001
        wrapped = False
    _PROFILE["delivery_hooked"] = bool(wrapped)
    _PROFILE["push"]["available"] = bool(wrapped)
    return bool(wrapped)


def _profile_span(value, fmt="%.3f"):
    """A measured span as the delivery lines spell it; None is "default"."""
    if value is None:
        return "default"
    try:
        return fmt % float(value)
    except (TypeError, ValueError):
        return "default"


def _profile_event_detail(event):
    """The extra fields one client edge carries, as the event line spells them.

    A seek carries the position it left and the position it landed on, so the
    line reads "kind=seek from=40 to=440". An edge with neither prints exactly
    as it did before (the string is empty).
    """
    parts = []
    for name in ("from", "to"):
        if name in event:
            parts.append("%s=%s" % (name, _profile_span(event.get(name), "%d")))
    return (" " + " ".join(parts)) if parts else ""


def _profile_delivery_lines():
    """The image-delivery block: what trame was asked to ship, and what it did."""
    push = _PROFILE["push"]
    still = _PROFILE["still"]
    anim = _PROFILE["animate"]
    client = _PROFILE["client"]
    ms = _profile_stats([float(value) for value in still["ms"]])
    sizes = _profile_stats([float(value) for value in still["bytes"]])
    events = client["events"]
    out = [
        "push: attempts=%d rendered=%d dropped_animation=%d dropped_untracked=%d "
        "dropped_disabled=%d available=%s"
        % (
            int(push["attempts"]),
            int(push["rendered"]),
            int(push["dropped_animation"]),
            int(push["dropped_untracked"]),
            int(push["dropped_disabled"]),
            "yes" if push["available"] else "no",
        ),
        "still: n=%d p50=%.2f p95=%.2f max=%.2f bytes_p50=%.0f bytes_total=%d"
        % (
            int(still["n"]),
            ms["median"],
            ms["p95"],
            ms["max"],
            sizes["median"],
            int(still["total_bytes"]),
        ),
        "animate: calls=%d last_target_fps=%s in_animation_s=%.3f"
        % (
            int(anim["calls"]),
            _profile_span(anim["last_target_fps"], "%.1f"),
            float(anim["in_animation_s"]),
        ),
        "client: events=%d start_interaction=%d end_interaction=%d "
        "animation_start=%d animation_stop=%d first_t=%s last_t=%s"
        % (
            len(events),
            int(client["start_interaction"]),
            int(client["end_interaction"]),
            int(client["animation_start"]),
            int(client["animation_stop"]),
            _profile_span(events[0].get("t") if events else None),
            _profile_span(events[-1].get("t") if events else None),
        ),
    ]
    # A long session has thousands of edges: the per-event lines are carried only
    # while the list is short enough to read, and the counts above say how many.
    if 0 < len(events) <= _PROFILE_DELIVERY_MAX_EVENTS:
        for event in events:
            out.append(
                "ev t=%s kind=%s%s"
                % (
                    _profile_span(event.get("t")),
                    event.get("kind"),
                    _profile_event_detail(event),
                )
            )
    return out


# ---------------------------------------------------------------------------
# Render knobs, and the report that says what they became.
#
# Three facts about a run's OWN picture that no screenshot carries:
#
# * which GL stack draws it - a CPU rasteriser (llvmpipe, swrast, OSMesa) paints
#   the same field at a fraction of the speed of a GPU, so a timing that does not
#   name the renderer is a timing a reader can draw the wrong conclusion from;
# * how many samples the off-screen window REALLY took - a requested 8 that the
#   driver quietly answered with 0 is not the picture the flag asked for;
# * what the trame view does to the bytes it ships the browser - the image
#   transport is jpeg-only (see _IMAGE_TRANSPORT_ENCODING), so a png request is
#   RECORDED and reported as NOT applied rather than pretended.
#
# Every probe here degrades: what cannot be read is reported as unknown, and no
# report line ever raises into a run.
# ---------------------------------------------------------------------------
_IMAGE_ENCODINGS = ("png", "jpeg")
# trame_vtk encodes the frame itself - trame_vtk/modules/vtk/protocols/
# publish_image_delivery.py sets reply["format"] = "jpeg" with no option beside
# it - so JPEG is the ONE encoding this transport honours, whatever is asked.
_IMAGE_TRANSPORT_ENCODING = "jpeg"
# Substrings that mean "this is a CPU rasteriser, not a GPU". Lower case.
_GL_SOFTWARE_MARKERS = (
    "llvmpipe",
    "softpipe",
    "swrast",
    "software rasterizer",
    "softwarerasterizer",
    "osmesa",
    "mesa offscreen",
    "gdi generic",
    "microsoft basic render",
)


def _env_text(name, default=None):
    """A stripped environment value, or ``default`` when it is unset or blank."""
    value = os.environ.get(name)
    if value is None:
        return default
    value = str(value).strip()
    return value or default


def _env_int(name, default=None):
    """An int from the environment; unset, blank or unparsable gives ``default``."""
    value = _env_text(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _resolve_display_knobs(msaa=None, image_encoding=None, image_quality=None):
    """Validate the three display knobs. A bad value raises ValueError, named.

    Resolution is separate from the parser so the RULE has one home: a flag and
    its POC_* variable both arrive here, and a value VTK or the transport would
    silently ignore is refused instead of accepted and dropped.
    """
    resolved = {"msaa": None, "image_encoding": None, "image_quality": None}
    if msaa is not None:
        try:
            value = int(msaa)
        except (TypeError, ValueError):
            raise ValueError("--msaa must be an integer >= 0, got %r" % (msaa,))
        if value < 0:
            raise ValueError("--msaa must be an integer >= 0, got %d" % value)
        resolved["msaa"] = value
    if image_encoding is not None:
        value = str(image_encoding).strip().lower()
        if value not in _IMAGE_ENCODINGS:
            raise ValueError(
                "--image-encoding must be one of %s, got %r"
                % ("/".join(_IMAGE_ENCODINGS), image_encoding)
            )
        resolved["image_encoding"] = value
    if image_quality is not None:
        try:
            value = int(image_quality)
        except (TypeError, ValueError):
            raise ValueError(
                "--image-quality must be an integer 1..100, got %r" % (image_quality,)
            )
        if not 1 <= value <= 100:
            raise ValueError("--image-quality must be 1..100, got %d" % value)
        resolved["image_quality"] = value
    return resolved


def _display_knobs_or_exit(parser, args):
    """``_resolve_display_knobs`` over parsed args, a bad knob being a USAGE error.

    The refusal is the parser's (exit 2, the message names the flag and the
    range), so a value VTK or the transport would ignore never reaches a run
    looking like a knob that was honoured.
    """
    try:
        return _resolve_display_knobs(
            getattr(args, "msaa", None),
            getattr(args, "image_encoding", None),
            getattr(args, "image_quality", None),
        )
    except ValueError as exc:
        parser.error(str(exc))


def _knob_text(value):
    """A knob as the report spells it: its value, or default when not given."""
    return "default" if value is None else str(value)


def _value_text(value):
    """A MEASURED value for the report: itself, or ? when it was never read."""
    return "?" if value is None else str(value)


def _encoding_text(report):
    """What was ASKED for, and what the transport will actually send."""
    applied = report.get("image_encoding_applied") or "?"
    requested = report.get("image_encoding")
    if requested is None:
        return "default(%s)" % applied
    return "%s(requested)/%s(applied)" % (requested, applied)


def _gl_parse_capabilities(text):
    """Pull vendor/renderer/version out of ``ReportCapabilities()`` text.

    VTK has printed this table two ways (``OpenGL vendor string: X`` and a padded
    ``Vendor:``/``Renderer:``/``Version:`` block), so both spellings are read.
    ``Driver Version`` is deliberately NOT matched as ``Version``: it is the
    driver's number, not the GL one this report claims to quote.
    """
    found = {"vendor": None, "renderer": None, "version": None}
    labels = {
        "opengl vendor string": "vendor",
        "opengl renderer string": "renderer",
        "opengl version string": "version",
        "gl vendor": "vendor",
        "gl renderer": "renderer",
        "gl version": "version",
        "vendor": "vendor",
        "renderer": "renderer",
        "version": "version",
    }
    for line in str(text or "").splitlines():
        label, _, value = line.partition(":")
        key = labels.get(label.strip().lower())
        value = value.strip()
        if key is None or not value or found[key] is not None:
            continue
        found[key] = value
    return found


def _gl_mode(vendor, renderer):
    """``software`` for a CPU rasteriser, ``direct`` for a driver, else unknown."""
    blob = " ".join(str(part) for part in (vendor, renderer) if part).lower()
    if not blob.strip():
        return "unknown"
    for marker in _GL_SOFTWARE_MARKERS:
        if marker in blob:
            return "software"
    return "direct"


def _plotter_pushes_on_render(plotter) -> bool:
    """Whether this plotter's own ``render()`` already publishes the image.

    ``VtkRemoteView`` does not wait to be told: it registers a callback in
    pyvista's ``_on_render_callbacks``, and pyvista runs that container at the
    END of every ``render()``. On such a plotter an explicit ``view.update()``
    would ship the SAME frame a second time - one more readback and image encode
    per tick, which is nearly the whole cost of a push, for a picture the client
    already has. The container is read defensively: a pyvista that renames it has
    to cost us a duplicate push, never a tick.
    """
    callbacks = getattr(plotter, "_on_render_callbacks", None)
    if callbacks is None:
        return False
    try:
        return len(callbacks) > 0
    except Exception:  # noqa: BLE001 - an unreadable container means no
        return False


def _push_still(view_handle, site) -> bool:
    """Ship ONE still through ``view_handle``. True when an image really left.

    EVERY still in the app goes through here, so the profile can say which control
    asked for it: ``calls: push=`` stays the total (one image left the server) and
    ``push:<site>`` says who asked. Before this the counter only saw the ticks that
    happened to route through ``_show`` - a cut slider, a station change or a mode
    choice pushed pictures that were never counted at all, which is why a run could
    paint 600 ticks and still report 1330 deliveries. ``site`` is a short spelling
    picked at the call site, never anything derived from input, so the vocabulary in
    the summary stays fixed.

    A ``None`` handle means no client has attached: nobody would ever ask for the
    image, so nothing is sent and nothing is counted.
    """
    if view_handle is None:
        return False
    # The probe clocks the push and, while it is on, wraps the delivery's
    # still_render/publish so the flush phase can be split (see
    # _stall_hook_protocol). Both are no-ops with the probe off.
    stall = _stall_flush_begin()
    if stall is not None:
        _stall_hook_protocol(view_handle)
    try:
        view_handle.update()
    except Exception as exc:  # noqa: BLE001 - a lost frame is not the loop
        _stall_flush_cancel(stall)
        print(f"[poc_app] view update skipped: {exc}", file=sys.stderr)
        return False
    _stall_flush_end(stall)
    if _PROFILE["enabled"]:
        # With the suite off this costs one bool read.
        _profile_count("push")
        _profile_count("push:" + site)
    return True


def _tick_render_and_push(plotter, view_handle, site="show") -> bool:
    """Draw this tick ONCE, publish it ONCE. True when the tick painted a frame.

    Trame's image delivery OWNS the render whenever a view is attached:
    ``PublishImageDelivery.still_render`` calls the app's ``StillRenderToString``
    (or ``StillRenderToBuffer`` when it decodes) itself and stamps the reply with
    ``app.GetLastStillRenderToMTime()`` - publish_image_delivery.py:196 and :218. So
    the image the client sees is the one ``view_handle.update()`` asked for, and a
    ``plotter.render()`` in front of that update drew the SAME picture a second
    time into a window nobody reads; where pyvista's render callback is hooked up
    (see ``_plotter_pushes_on_render``) it also shipped that second copy, i.e. two
    full renders and two image encodes per tick for one visible frame - exactly the
    waste that made the pump overrun its own paint cap.

    Therefore: with a view, exactly ONE ``view_handle.update()`` and NO local
    render; with no view, nobody will ever ask for the image, and the local render
    IS the picture (headless, or before the client connects). The render marks and
    the ``draw`` phase are closed between the two halves, so a push can never be
    billed to the draw, and a push is COUNTED only when one really left the server:
    ``calls:`` counts images, not ticks. ``site`` names the caller for the
    ``push_by_site:`` breakdown (see ``_push_still``).
    """
    _timing_mark("render_start")
    rendered = False
    if view_handle is None:
        # No client-side view: rendering here is the only way pixels exist.
        try:
            plotter.render()
            rendered = True
        except Exception as exc:  # noqa: BLE001 - never take the server down
            print(f"[poc_app] render skipped: {exc}", file=sys.stderr)
    _timing_mark("render_end")
    _profile_phase("draw")
    _timing_mark("push_start")
    # ONE image leaves the server this tick, or none. With a view the update below
    # IS the render (trame renders through the app), so there is nothing else to
    # send; a real send is counted, a tick with nothing to push adds nothing.
    pushed = _push_still(view_handle, site)
    _timing_mark("push_end")
    return rendered or pushed


def _gl_capabilities(render_window):
    """The GL strings plus their mode, or None when they cannot be read SAFELY.

    ``ReportCapabilities()`` CREATES an OpenGL context, and on a box with no GL
    driver at all it does not return an error - it takes the process down with it
    (observed: "Failed to load EGL!", "libOSMesa not found", then a segfault).
    ``GetNeverRendered()`` is the cheap question that must be answered first: an
    unrendered window is reported as pending, and the run keeps its viewer.
    """
    if render_window is None:
        return None
    try:
        if render_window.GetNeverRendered():
            return None
        text = render_window.ReportCapabilities()
    except Exception:  # noqa: BLE001 - a probe is not the app
        return None
    caps = _gl_parse_capabilities(text)
    caps["mode"] = _gl_mode(caps.get("vendor"), caps.get("renderer"))
    return caps


def _window_multi_samples(plotter):
    """The off-screen window's sample count, or None when it cannot be read."""
    window = getattr(plotter, "render_window", None)
    try:
        return int(window.GetMultiSamples())
    except Exception:  # noqa: BLE001
        return None


def _apply_msaa(plotter, multi_samples):
    """Ask VTK for ``multi_samples`` samples and return what the window TOOK.

    pyvista has no plotter-level attribute for this - MSAA is a render-window
    setting, reached through ``enable_anti_aliasing("msaa", multi_samples=N)`` -
    and a driver may answer with fewer samples than it was asked for, which is
    exactly why the reply is read back instead of assumed.
    """
    if plotter is None or multi_samples is None:
        return None
    try:
        plotter.enable_anti_aliasing("msaa", multi_samples=int(multi_samples))
    except Exception as exc:  # noqa: BLE001 - the picture outranks the probe
        print(f"[poc_app] msaa {multi_samples} not applied: {exc}", file=sys.stderr)
        return None
    return _window_multi_samples(plotter)


def _image_view_kwargs(quality=None):
    """The construction kwargs that ask a trame view for a still quality.

    A trame widget only forwards a property it was BUILT with: assigning one
    after the layout HTML has been generated edits this process's copy and
    never reaches the page. So the quality has to be handed over where the view
    is created. With no quality asked for there is nothing to pass and the
    view's own default stands.
    """
    if quality is None:
        return {}
    return {"still_quality": int(quality), "interactive_quality": int(quality)}


def _view_takes_prop(view, name):
    """True when ``view`` really forwards a trame property called ``name``.

    ``hasattr`` cannot answer this for a trame element: its ``__getattr__``
    prints "<elem>.<name> is missing" and RETURNS None for a name it does not
    know, so every name looks present. The allowed keys of the widget's impl are
    the honest answer; a plain object without an impl is taken at face value.
    """
    impl = getattr(view, "_impl", None)
    allowed = getattr(impl, "allowed_keys", None)
    if allowed is None:
        return hasattr(view, name)
    try:
        return name in allowed
    except TypeError:
        return False


def _image_aware_plotter_ui(plotter_ui, quality=None):
    """Wrap ``plotter_ui`` so every view it builds carries the still quality.

    Returns ``plotter_ui`` itself when there is no quality to pass, so a run
    that asked for nothing is wired exactly as before. A caller's own keyword
    still wins; a trame build that refuses the kwargs costs one honest line and
    the view is built without them rather than taken down.
    """
    kwargs = _image_view_kwargs(quality)
    if not kwargs or plotter_ui is None:
        return plotter_ui

    def _ui(*args, **build_kwargs):
        merged = dict(build_kwargs)
        for name, value in kwargs.items():
            merged.setdefault(name, value)
        try:
            return plotter_ui(*args, **merged)
        except TypeError as exc:
            print(
                "[poc_app] image quality %s not applied: the trame view "
                "refused %s (%s)" % (quality, sorted(kwargs), exc),
                file=sys.stderr,
            )
            return plotter_ui(*args, **build_kwargs)

    _ui.__name__ = getattr(plotter_ui, "__name__", "_ui")
    return _ui


def _apply_image_knobs(view, encoding=None, quality=None):
    """Put the image knobs on the trame view and say what was actually applied.

    ``still_quality``/``interactive_quality`` are the view's REAL properties
    (VtkRemoteView passes them to the JS side as the quality it renders with),
    but they only reach the page when the view is CREATED with them - that is
    ``_image_view_kwargs``' job. What is done here is the honest read-back on
    the view that came back, plus the encoding, which has no such property: the
    transport writes the format in its protocol module, so a png request is
    reported as NOT applied rather than recorded as if it had been. Nothing
    here raises: a widget that refuses a knob costs that knob, not the page.
    """
    applied = {}
    note = None
    if view is not None and quality is not None:
        for name in ("still_quality", "interactive_quality"):
            if not _view_takes_prop(view, name):
                continue
            try:
                setattr(view, name, int(quality))
            except Exception:  # noqa: BLE001 - a widget that refuses costs a knob
                continue
            applied[name] = int(quality)
    effective = _IMAGE_TRANSPORT_ENCODING
    if encoding is not None:
        if view is not None and _view_takes_prop(view, "image_encoding"):
            try:
                view.image_encoding = encoding
                applied["image_encoding"] = encoding
                effective = encoding
            except Exception:  # noqa: BLE001
                pass
        if applied.get("image_encoding") != encoding:
            note = (
                "image encoding %s requested but NOT applied: the trame image "
                "transport sends jpeg (trame_vtk publish_image_delivery.py)"
                % encoding
            )
    return {
        "encoding": encoding,
        "quality": quality,
        "applied": applied,
        "encoding_applied": effective,
        "note": note,
    }


# The boot report, filled once per run by _renderer_report(). Read by the boot
# line and by the profile summary header, so the two cannot disagree.
_RENDERER = {
    "gl_vendor": None,
    "gl_renderer": None,
    "gl_version": None,
    "gl_mode": "unknown",
    "gl_note": None,
    "pixels": None,
    "multi_samples": None,
    "msaa_requested": None,
    "msaa_applied": None,
    "image_encoding": None,
    "image_quality": None,
    "image_encoding_applied": _IMAGE_TRANSPORT_ENCODING,
    "image_applied": {},
    "image_note": None,
}


def _renderer_report(plotter=None, image=None, msaa=None):
    """Fill and return ``_RENDERER``: what draws, at what size, with which knobs.

    ``multi_samples`` is the sample count the WINDOW holds, i.e. what --msaa
    actually got, and it is quoted beside the number that was asked for. The GL
    strings are read only through ``_gl_capabilities`` - see the segfault note
    there - so a run that has not really drawn reports them as pending.
    """
    report = {
        "gl_vendor": None,
        "gl_renderer": None,
        "gl_version": None,
        "gl_mode": "unknown",
        "gl_note": None,
        "pixels": None,
        "multi_samples": None,
        "msaa_requested": msaa,
        "msaa_applied": None,
        "image_encoding": None,
        "image_quality": None,
        "image_encoding_applied": _IMAGE_TRANSPORT_ENCODING,
        "image_applied": {},
        "image_note": None,
    }
    window = getattr(plotter, "render_window", None)
    if window is not None:
        try:
            size = window.GetSize()
            report["pixels"] = (int(size[0]), int(size[1]))
        except Exception:  # noqa: BLE001
            report["pixels"] = None
        report["multi_samples"] = _window_multi_samples(plotter)
        report["msaa_applied"] = report["multi_samples"]
        caps = _gl_capabilities(window)
        if caps is None:
            try:
                never = bool(window.GetNeverRendered())
            except Exception:  # noqa: BLE001
                never = True
            report["gl_note"] = (
                "no GL report: the window has not been rendered yet"
                if never
                else "no GL report: ReportCapabilities() could not be read"
            )
        else:
            report["gl_vendor"] = caps.get("vendor")
            report["gl_renderer"] = caps.get("renderer")
            report["gl_version"] = caps.get("version")
            report["gl_mode"] = caps.get("mode") or "unknown"
    if image is not None:
        report["image_encoding"] = image.get("encoding")
        report["image_quality"] = image.get("quality")
        report["image_applied"] = dict(image.get("applied") or {})
        report["image_encoding_applied"] = image.get("encoding_applied")
        report["image_note"] = image.get("note")
    _RENDERER.clear()
    _RENDERER.update(report)
    return _RENDERER


def _renderer_report_line(report=None) -> str:
    """The renderer report as ONE ``[poc_app]`` line: renderer, pixels, knobs.

    Said once per run, and only when the GL stack can be asked - i.e. once a
    frame has really drawn (see ``_gl_capabilities`` and
    ``_renderer_report_after_render``) - so the ``gl=``/``vendor=``/``renderer=``
    fields are either the real answer or an explicit statement that it was not
    readable. A line that said ``gl=unknown`` before anything was drawn would be
    a fact about the log, not about the box.
    """
    report = _RENDERER if report is None else report
    pixels = report.get("pixels")
    samples = _value_text(report.get("multi_samples"))
    return (
        "[poc_app] renderer: gl=%s vendor=%s renderer=%s version=%s | "
        "pixels=%s | plotter multi_samples=%s | msaa requested=%s applied=%s | "
        "trame image encoding=%s quality=%s%s%s"
        % (
            report.get("gl_mode") or "unknown",
            report.get("gl_vendor") or "?",
            report.get("gl_renderer") or "?",
            report.get("gl_version") or "?",
            ("%dx%d" % (int(pixels[0]), int(pixels[1]))) if pixels else "?",
            samples,
            _knob_text(report.get("msaa_requested")),
            samples,
            _encoding_text(report),
            _knob_text(report.get("image_quality")),
            " | " + report["gl_note"] if report.get("gl_note") else "",
            " | " + report["image_note"] if report.get("image_note") else "",
        )
    )


def _renderer_software_warning(report=None) -> str:
    """The shout a CPU rasteriser earns, or ``""`` when a GPU really drew.

    ``gl_mode == "software"`` means the strings matched ``_GL_SOFTWARE_MARKERS``
    (llvmpipe, softpipe, swrast, osmesa, ...): the frame came off the CPU, so
    every timing this run measures is a CPU timing and predicts nothing about
    frame time on real hardware. That is said in words a log scan cannot miss
    rather than left for the reader to infer from the vendor string.
    """
    report = _RENDERER if report is None else report
    if report.get("gl_mode") != "software":
        return ""
    return (
        "[poc_app] WARNING: software rasteriser - renderer=%s vendor=%s. "
        "Nothing here was drawn on a GPU, so every number this run measures is "
        "a CPU timing: it does not predict frame time on real hardware."
        % (report.get("gl_renderer") or "?", report.get("gl_vendor") or "?")
    )


def _renderer_report_lines():
    """The same report as summary-header lines (no ``[poc_app]`` prefix)."""
    report = _RENDERER
    pixels = report.get("pixels")
    lines = [
        "renderer: gl=%s vendor=%s renderer=%s version=%s"
        % (
            report.get("gl_mode") or "unknown",
            report.get("gl_vendor") or "?",
            report.get("gl_renderer") or "?",
            report.get("gl_version") or "?",
        ),
        "display: pixels=%s plotter multi_samples=%s msaa requested=%s applied=%s"
        " | trame image encoding=%s quality=%s"
        % (
            ("%dx%d" % (int(pixels[0]), int(pixels[1]))) if pixels else "?",
            _value_text(report.get("multi_samples")),
            _knob_text(report.get("msaa_requested")),
            _value_text(report.get("msaa_applied")),
            _encoding_text(report),
            _knob_text(report.get("image_quality")),
        ),
    ]
    notes = [
        note for note in (report.get("gl_note"), report.get("image_note")) if note
    ]
    if notes:
        lines.append("display note: " + "; ".join(notes))
    return lines


def _renderer_report_after_render(plotter, handles) -> bool:
    """Say the renderer report ONCE, on the first tick whose frame really drew.

    The GL strings are only askable of a window that has really rendered (see
    ``_gl_capabilities``), and a trame view's ``update()`` only QUEUES the draw:
    a report rebuilt on the same tick as the first push still finds
    ``GetNeverRendered()`` true, and would print ``gl=unknown`` a second time -
    and burn the one-shot flag doing it, so the real vendor string never reached
    the log on a GPU box at all. So the flag is set only when the line is said:
    until a frame has drawn this returns False and costs one ``GetNeverRendered()``
    per tick, then the report is rebuilt from the SAME plotter, image record and
    msaa request the boot site parked on ``handles``, printed once, and followed by
    the software-rasteriser warning when there is one. Never raises: a report is
    not the tick.
    """
    if handles is None or handles.get("renderer_reported"):
        return False
    if _RENDERER.get("gl_mode") != "unknown":
        # The boot line already answered: nothing left to add, and nothing to ask.
        handles["renderer_reported"] = True
        return False
    if "renderer_msaa" not in handles:
        # The page draws ONCE before the boot report runs (_show(0, "ycut", "boot")
        # precedes the layout that owns the view), and that draw may well be the
        # first real render - but the knob record is parked on ``handles`` only by
        # the boot report itself. A line said here would name no msaa request and
        # no image record, so it waits for the boot site to have spoken.
        return False
    window = getattr(plotter, "render_window", None)
    if window is None:
        # No window means nothing will ever answer: stay silent rather than lie.
        return False
    try:
        if window.GetNeverRendered():
            # The frame is still queued, not drawn. Ask again on a later tick and
            # keep the flag: this is the retry, not the report.
            return False
    except Exception:  # noqa: BLE001 - cannot tell, so let the report say so
        pass
    try:
        report = _renderer_report(
            plotter=plotter,
            image=handles.get("renderer_image"),
            msaa=handles.get("renderer_msaa"),
        )
        handles["renderer_reported"] = True
        print(_renderer_report_line(report))
        warning = _renderer_software_warning(report)
        if warning:
            print(warning)
        return True
    except Exception as exc:  # noqa: BLE001 - a report is not the tick
        handles["renderer_reported"] = True  # do not retry a broken report each tick
        print(f"[poc_app] renderer report skipped: {exc}", file=sys.stderr)
        return False


#: Is the one-shot actor dump asked for?  Resolved ONCE, at import, like
#: ``_TIMING_ENABLED``: a diagnostic that could change its mind mid-run would
#: describe a scene that never existed at any one instant.  Asked through
#: ``_actor_dump_wanted`` so the reason has one home.
_ACTOR_DUMP_WANTED = (os.environ.get("POC_DUMP_ACTORS") or "").strip().lower() in (
    "1",
    "true",
    "yes",
)


def _actor_dump_wanted() -> bool:
    """True when POC_DUMP_ACTORS asks for the one-shot actor dump."""
    return _ACTOR_DUMP_WANTED


def _dump_actors_once(plotter, handles, info=None) -> bool:
    """Print every actor on the plotter ONCE, on the first frame that drew.

    WHAT THIS IS FOR: a picture whose sheets come out dim, flat or invisible is
    argued about over a screenshot. The screenshot says the colour is wrong; it
    cannot say whether the actor is lit, half-transparent, hidden, or missing.
    One dump of the scene answers all four at once - name, class, visibility,
    opacity, colour, lighting and world bounds per actor, plus the domain box
    the frame is supposed to show - so the next report can quote numbers instead
    of adjectives.

    WHY IT RIDES THE RENDER GATE: it is called from the same ``if rendered:``
    branch as ``_renderer_report_after_render``, because a scene dumped before a
    frame has drawn is a half-built scene - the very state that makes a real
    defect look like a timing artefact. Like that report it is ONE-SHOT: the
    ``actors_dumped`` flag is set BEFORE the first line is printed, so a dump
    that raises halfway is still spent, and no tick ever prints it twice.

    OFF unless POC_DUMP_ACTORS=1/true/yes (see ``_actor_dump_wanted``), which is
    resolved at import rather than per call. NEVER raises: a dump is not the
    tick. Returns True only on the call that spoke.
    """
    if not _actor_dump_wanted() or handles is None or handles.get("actors_dumped"):
        return False
    # Spent HERE: a dump that fails below must not be retried on every tick.
    handles["actors_dumped"] = True
    try:
        actors = getattr(plotter.renderer, "actors", None) or {}
        print(f"[poc_app] actor dump: {len(actors)} actor(s)")
        for index, (name, actor) in enumerate(actors.items()):
            prop = getattr(actor, "prop", None)
            print(
                f"[poc_app]   {index}: name={name!r}"
                f" class={type(actor).__name__}"
                f" visibility={getattr(actor, 'visibility', None)}"
                f" opacity={getattr(prop, 'opacity', None)}"
                f" color={getattr(prop, 'color', None)}"
                f" lighting={getattr(prop, 'lighting', None)}"
                f" bounds={tuple(actor.GetBounds())}"
            )
        # Its OWN try: the domain is what the frame is judged against, and a
        # page whose info carries no extents must still list its actors.
        try:
            print(
                "[poc_app]   domain="
                f"{_plane_extent_mm(info or {}).get('domain')}"
            )
        except Exception as exc:  # noqa: BLE001 - the domain is not the dump
            print(f"[poc_app]   domain unknown: {exc}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - a dump is not the tick
        print(f"[poc_app] actor dump skipped: {exc}", file=sys.stderr)
    return True


def _profile_knobs(fps=None, msaa=None, image_encoding=None, image_quality=None):
    """Record the display knobs this run was STARTED with. Returns the record.

    Recorded whether or not the suite is on: the knobs are a fact about the run,
    and the summary must not have to guess them from an argument it never saw.
    """
    knobs = _PROFILE["knobs"]
    for name, value in (
        ("fps", fps),
        ("msaa", msaa),
        ("image_encoding", image_encoding),
        ("image_quality", image_quality),
    ):
        if value is None:
            continue
        try:
            knobs[name] = str(value) if name == "image_encoding" else int(value)
        except (TypeError, ValueError):
            continue
    return knobs


def _profile_knobs_line(knobs=None) -> str:
    """The knobs the run was started with, as the summary spells them."""
    knobs = _PROFILE["knobs"] if knobs is None else knobs
    return "knobs: fps=%s msaa=%s image_encoding=%s image_quality=%s" % (
        _knob_text(knobs.get("fps")),
        _knob_text(knobs.get("msaa")),
        _knob_text(knobs.get("image_encoding")),
        _knob_text(knobs.get("image_quality")),
    )


def _profile_row_painted(row):
    """True when this tick row's picture actually reached the browser.

    A tick the paint cap or the delivery hold held back counted a row but drew
    nothing, so it is not part of the painted span. A row with no counters is
    taken at face value (there is nothing to contradict it).
    """
    counts = row.get("counts")
    if not counts:
        return True
    try:
        return bool(
            int(counts.get("render") or 0) or int(counts.get("push") or 0)
        )
    except (TypeError, ValueError):
        return True


def _profile_painted_span(rows):
    """(paints, span seconds) over the PAINTED ticks: first painted to last.

    The span is what the picture was actually being refreshed across. Measuring
    from the first tick to the last instead would divide the paints by a stretch
    the run spent idle or paused, and report a rate the viewer never saw.
    """
    times = [
        float(row["t"])
        for row in rows
        if row.get("t") is not None and _profile_row_painted(row)
    ]
    if not times:
        return 0, 0.0
    span = (max(times) - min(times)) if len(times) > 1 else 0.0
    return len(times), span


def _profile_rate_lines(rows, fps):
    """Two DERIVED lines: achieved vs target rate, and the overrun share.

    ``rows`` are tick rows. The rate is measured over the PAINTED span - first
    painted tick to last - so a run that idled or paused is reported at the rate
    it actually painted rather than divided by the wall time it sat still. The
    second line counts the ticks that took LONGER than one frame period - the
    ones a viewer drops instead of showing. With no fps recorded there is
    nothing to compare against, so there are no lines.
    """
    try:
        target = float(fps)
    except (TypeError, ValueError):
        return []
    if target <= 0:
        return []
    paints, span = _profile_painted_span(rows)
    achieved = (paints / span) if span > 0 else 0.0
    period_ms = 1000.0 / target
    lines = [
        "target: fps=%.0f frame=%.2f ms  painted=%d over %.2f s  "
        "paints/s=%.2f vs cap %.2f (%.1f%% of target)"
        % (
            target,
            period_ms,
            paints,
            span,
            achieved,
            target,
            100.0 * achieved / target,
        )
    ]
    walls = [float(row["wall_ms"]) for row in rows if row.get("wall_ms") is not None]
    over = len([wall for wall in walls if wall > period_ms])
    lines.append(
        "over one frame period: %d of %d ticks (%.1f%%)"
        % (over, len(walls), (100.0 * over / len(walls)) if walls else 0.0)
    )
    return lines


def _profile_summary_text() -> str:
    """The summary, <=60 lines. Numbers only; the report explains them."""
    if not _PROFILE["enabled"]:
        return ""
    rows = [row for row in _PROFILE["rows"] if row.get("kind") == "tick"]
    now = _profile_now()
    elapsed = max(1e-9, _profile_elapsed(now))
    out = [f"poc_app --profile summary  run={_PROFILE['stamp']}"]
    out.append(
        "ticks=%d  elapsed=%.1fs  rate=%.2f ticks/s  dir=%s"
        % (len(rows), elapsed, len(rows) / elapsed, _PROFILE["dir"])
    )
    # The header names the PICTURE the numbers belong to, then the knobs it was
    # produced with, then the two derived lines that turn the tick count into an
    # answer about the target rate. Same order the boot report uses.
    knobs = _PROFILE["knobs"] or {}
    out.extend(_renderer_report_lines())
    out.append(_profile_knobs_line(knobs))
    out.extend(_profile_rate_lines(rows, knobs.get("fps")))
    out.append("phases (ms): phase       n     p50     p95     max")
    for name in _PROFILE_PHASES:
        values = [
            float(row["phases"][name])
            for row in rows
            if row.get("phases", {}).get(name) is not None
        ]
        stats = _profile_stats(values)
        if stats["n"]:
            out.append(
                "  %-9s %5d %7.2f %7.2f %7.2f"
                % (name, stats["n"], stats["median"], stats["p95"], stats["max"])
            )
    wall = _profile_stats(
        [float(row["wall_ms"]) for row in rows if row.get("wall_ms")]
    )
    if wall["n"]:
        out.append(
            "tick wall (ms): n=%d p50=%.2f p95=%.2f max=%.2f"
            % (wall["n"], wall["median"], wall["p95"], wall["max"])
        )
    out.append("sheets: key            repaints  p50    p95    max   no-op  assigned/in-place")
    for key in sorted(_PROFILE["sheets"]):
        agg = _PROFILE["sheets"][key]
        per = [
            float(sheet["ms"])
            for row in rows
            for sheet in row.get("sheets", [])
            if sheet.get("key") == key
        ]
        stats = _profile_stats(per)
        out.append(
            "  %-14s %8d %6.2f %6.2f %6.2f %6d %6d/%d"
            % (
                key,
                agg["repaints"],
                stats["median"],
                stats["p95"],
                stats["max"],
                agg["noop"],
                agg["assigned"],
                agg["in_place"],
            )
        )
    counts = _PROFILE["counts"]
    # ``push`` is here because it is the number that decides the tick rate: an
    # image leaves the server once per push, so it is read beside ``render``.
    out.append(
        "calls: render=%d push=%d add_mesh=%d remove_actor=%d"
        " paint_cap=%d delivery_hold=%d scrub_hold=%d"
        % (
            int(counts.get("render", 0)),
            int(counts.get("push", 0)),
            int(counts.get("add_mesh", 0)),
            int(counts.get("remove_actor", 0)),
            int(counts.get("paint_cap", 0)),
            int(counts.get("delivery_hold", 0)),
            int(counts.get("scrub_hold", 0)),
        )
    )
    # ``push`` above is HOW MANY stills left; this line is WHO asked for them. Every
    # still goes through _push_still, which bumps ``push:<site>`` beside the total, so
    # the two MUST add up - a site is a name, never a second push. Read together they
    # answer the question a bare total cannot: why a run painted 600 ticks and shipped
    # 1330 images (a play tick is one push, a solve is two - see solve_resend).
    sites = sorted(
        (
            (name[len("push:"):], int(value))
            for name, value in counts.items()
            if name.startswith("push:")
        ),
        key=lambda item: (-item[1], item[0]),
    )
    out.append(
        "push_by_site: "
        + (" ".join("%s=%d" % (name, value) for name, value in sites) or "none")
    )
    noop = sum(int(agg["noop"]) for agg in _PROFILE["sheets"].values())
    repaints = sum(int(agg["repaints"]) for agg in _PROFILE["sheets"].values())
    out.append(
        "no-op sheet repaints (index unchanged): %d of %d (%.1f%%)"
        % (noop, repaints, (100.0 * noop / repaints) if repaints else 0.0)
    )
    # The OTHER half of a frame's journey: what trame shipped, encoded and threw
    # away. Read beside the calls above, not instead of them.
    out.extend(_profile_delivery_lines())
    lag = _profile_stats([float(value) for value in _PROFILE["lag"]])
    if lag["n"]:
        out.append(
            "loop lag (ms): n=%d mean=%.2f p95=%.2f max=%.2f"
            % (lag["n"], lag["mean"], lag["p95"], lag["max"])
        )
    idle = _PROFILE["idle"]
    if idle:
        per_s = [
            float(row["cpu_per_s"])
            for row in idle
            if row.get("cpu_per_s") is not None
        ]
        stats = _profile_stats(per_s)
        out.append(
            "idle: records=%d cpu_per_s p50=%.4f max=%.4f total_process_s=%.3f"
            % (
                len(idle),
                stats["median"],
                stats["max"],
                sum(float(row.get("process_s") or 0.0) for row in idle),
            )
        )
    stacks = _PROFILE["stacks"]
    if stacks:
        total = sum(int(value) for value in stacks.values()) or 1
        out.append("top functions (stack samples, all threads):")
        for name, count in stacks.most_common(15):
            out.append("  %5d %5.1f%%  %s" % (count, 100.0 * count / total, name))
    return "\n".join(out[:60]) + "\n"


def _profile_write_summary() -> str:
    """Rewrite summary_<stamp>.txt. Returns the text either way."""
    if not _PROFILE["enabled"]:
        return ""
    try:
        text = _profile_summary_text()
    except Exception:  # noqa: BLE001 - telemetry is not the app
        return ""
    try:
        if _PROFILE["files"].get("summary") is not None:
            _PROFILE["files"]["summary"].write_text(text, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return text


def _profile_shutdown() -> None:
    """Flush what is pending and write the summary. Safe to call twice."""
    if not _PROFILE["enabled"]:
        return
    try:
        _profile_flush_pending()
        _profile_write_summary()
        _stall_write_summary()
        _profile_stop_thread()
    except Exception:  # noqa: BLE001 - the last breath is not the app either
        return


def _profile_register_exit() -> None:
    """Write the summary on exit AND on SIGTERM (a killed run still answers)."""
    try:
        import atexit

        atexit.register(_profile_shutdown)
    except Exception:  # noqa: BLE001
        pass
    try:
        import signal

        previous = signal.getsignal(signal.SIGTERM)

        def _on_term(signum, frame):
            _profile_shutdown()
            if callable(previous) and previous not in (signal.SIG_DFL, signal.SIG_IGN):
                return previous(signum, frame)
            raise SystemExit(128 + int(signum))

        signal.signal(signal.SIGTERM, _on_term)
    except Exception:  # noqa: BLE001 - not the main thread, or no signals
        pass


# ---------------------------------------------------------------------------
# TEMPORAL ALIASING REPORT
#
# Fix 1 named the solver step each frame stands on. That is still not the whole
# truth about a decimated volume: the captures are 100 steps apart, the player
# animates them as if the field travelled continuously between them, and until
# now it said nothing about it. When the field's own phase turns by more than a
# period between two stored frames, the animated motion is not the motion - it
# is an ALIAS of it.
#
# THE PHASE IS MEASURED. Two routes, both reading the recording:
#
#   1. BEST - track the complex phase of ONE probe through a plane series the
#      dump already stores frame by frame, unwrap it, and take the median
#      advance per recorded plane frame; then scale it by the volume's stride.
#   2. otherwise - the RECORDED frequency times the RECORDED ``dt_s`` times the
#      stride: phi = 2*pi*f*dt*stride. The key used is named in ``source``.
#
# No velocity, wavelength, permittivity or frequency is typed in here: the ones
# that appear are read out of ``info`` and named in ``source``. When neither
# route yields a defensible number the report says it cannot decide and NO
# banner is drawn - an invented number is the defect, not the fix.
# ---------------------------------------------------------------------------

ALIASING_FULL_PERIOD_RAD = 2.0 * math.pi
ALIASING_QUARTER_PERIOD_RAD = 0.5 * math.pi


def _aliasing_sentence(stride) -> str:
    """The banner sentence, character for character (stride substituted)."""
    return (
        f"Temporal Aliasing: Volume is decimated \u00d7{int(stride)}. "
        "Wave motion is not continuous between frames."
    )


@dataclass(frozen=True, eq=False)
class AliasingReport:
    """WHAT ONE DRAWN VOLUME FRAME DOES TO THE MOTION, read off the recording.

    ``stride`` is how many solver steps ONE stored volume frame spans, MEASURED
    from the volume's own step axis by :func:`_volume_decimation` (never from the
    recorded ``e_abs_volume_stride`` scalar), and ``frames`` is how many stored
    volume frames there are. ``phase_per_frame_rad`` is the angle a probe of the
    field turns through between two STORED volume frames - measured, never
    assumed - and ``frames_per_period`` is the same quantity as "how many stored
    frames fit into one period", i.e. how much of the motion one frame hides.
    ``source`` names where that phase came from, so no reader has to take it on
    trust.

    ``aliased`` is True when the advance passes a QUARTER period (the motion is
    undersampled against the quarter-wave convention) or a FULL one (consecutive
    frames do not even continue one another); ``severity`` says which of the two
    fired and ``reason`` states it in the measured degrees. ``text`` is the
    banner sentence, and is None whenever the page must stay silent: not
    aliased, or nothing measurable at all - in which case
    ``phase_per_frame_rad`` is None rather than a guess, because a guessed phase
    is exactly the dishonesty this record exists to remove.
    """

    stride: int
    frames: int
    phase_per_frame_rad: float | None
    frames_per_period: float | None
    source: str
    aliased: bool
    severity: str
    reason: str
    text: str | None


def _positive_float(value):
    """A finite, strictly positive float, or None - never a zero-filled one."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0.0 else None


def _longest_true_run(mask):
    """``(start, stop)`` of ``mask``'s longest unbroken True stretch, or None.

    One unbroken stretch rather than "all the good samples": unwrapping a phase
    across a gap of rejected samples would difference across the gap and report
    the gap's own angle as if it were one frame's advance.
    """
    best = None
    start = None
    total = 0
    for index, flag in enumerate(mask):
        total = index + 1
        if flag:
            if start is None:
                start = index
        elif start is not None:
            if best is None or index - start > best[1] - best[0]:
                best = (start, index)
            start = None
    if start is not None and (best is None or total - start > best[1] - best[0]):
        best = (start, total)
    return best


def _derive_surface_spec(info, name):
    """The :class:`step_time.SurfaceSpec` a dump's own axis implies for ``name``.

    ``name`` is the plane FAMILY, "ez_ycut" or "ez_xcut": both x-cut planes are
    written on the one recorded x-cut axis and therefore share one spec. Nothing
    is assumed about the cadence - it is read from the step numbers the dump
    wrote (``frame_index`` for the y-cut, ``frame_index_xcut`` for the x-cuts),
    with ``offset`` the first recorded step and ``stride`` the median positive
    gap, so a single missing frame cannot set the spacing. A dump whose axis is
    missing, empty or unreadable is described as one step per frame with no
    recorded frames - the only claim that survives, and the same fallback
    ``build_time_axis`` makes.
    """
    xcut = str(name).startswith("ez_xcut")
    axis = "x" if xcut else "y"
    steps = info.get("frame_index_xcut" if xcut else "frame_index")
    values = None
    if steps is not None:
        try:
            values = np.asarray(steps, dtype=float).ravel()
        except (TypeError, ValueError):
            values = None
    if values is None or values.size < 1:
        return _step_time.SurfaceSpec(axis=axis, position=0.0)
    stride = 1
    if values.size >= 2:
        gaps = np.diff(values)
        gaps = gaps[np.isfinite(gaps) & (gaps > 0.0)]
        if gaps.size >= 1:
            spacing = int(round(float(np.median(gaps))))
            if spacing >= 1:
                stride = spacing
    return _step_time.SurfaceSpec(
        axis=axis,
        position=0.0,
        stride=stride,
        offset=max(0, int(values[0])),
        n_frames=int(values.size),
    )


def _surface_spec(info, key):
    """The ONE description of how plane ``key`` is sampled from the step axis.

    ``step_time.SurfaceSpec`` is the single source of truth: frame ``f`` of the
    plane was captured at step ``offset + f * stride``, and no other mapping is
    legal. The spec is filed on the loaded dump by :func:`load_vis`, so every
    caller shares the one derived when the dump was read. A dict that never went
    through :func:`load_vis` (a bare fixture) is described on demand from the
    same recorded arrays.
    """
    name = "ez_xcut" if str(key).startswith("ez_xcut") else "ez_ycut"
    filed = info.get(SURFACE_SPECS_KEY)
    if isinstance(filed, dict):
        spec = filed.get(name)
        if spec is not None:
            return spec
    return _derive_surface_spec(info, name)


def _surface_frame_count(info, key, default) -> int:
    """How many frames plane ``key`` holds, per its spec; ``default`` if unrecorded.

    ``default`` is the count the dump's header states. An empty spec means "this
    dump records no step axis", NOT "this surface holds no frames", so the
    header's count is used there rather than a zero the page would draw.
    """
    count = int(_surface_spec(info, key).frame_count())
    return count if count > 0 else max(0, int(default))


def _plane_step_spacing(info, key):
    """How many solver steps ONE recorded frame of plane ``key`` stands for.

    The y-cut is sampled on ``frame_index`` and the two x-cuts on
    ``frame_index_xcut``; both are recorded step numbers, so their own spacing is
    the plane's stride. :func:`_surface_spec` is the once-and-only place that
    spacing is read off the dump, so this answers from the plane's own spec
    rather than re-measuring the axis per call. A dump whose recorded axis is
    missing or unreadable is read as one step per frame - the only claim that
    survives, and the same fallback ``build_time_axis`` makes.
    """
    return int(_surface_spec(info, key).stride)


def _phase_from_complex_planes(info, stride):
    """``(source, radians per volume frame)`` tracked through a complex plane.

    A complex plane series carries the field's PHASE frame by frame, so the
    advance is measured rather than derived from any frequency at all. The probe
    is the brightest voxel of the middle stored frame - a point inside the
    moving field - and the advance is the MEDIAN of ``diff(unwrap(angle))`` over
    the probe's longest unbroken stretch of usable samples, so one noisy window
    cannot set the answer.

    A near-zero ``|Ez|`` sample has no phase, only noise, so windows below a
    quarter of the probe's own median amplitude are rejected: reporting noise as
    motion is the failure mode this guard exists for, and an all-zero probe is
    rejected outright (its angle is 0 everywhere, which would read as perfectly
    still motion).

    The result is per RECORDED PLANE frame, so it is scaled by the volume's
    stride over the plane's own stride - one measured quantity, one conversion.
    """
    try:
        ratio = float(int(stride))
    except (TypeError, ValueError):
        return None
    for key in ("ez_ycut", "ez_xcut_near", "ez_xcut_far"):
        field = info.get(key)
        if field is None:
            continue
        try:
            array = np.asarray(field)
        except (TypeError, ValueError):
            continue
        if not np.iscomplexobj(array) or array.ndim != 3 or array.shape[0] < 3:
            continue
        amplitude = np.abs(array)
        middle = amplitude[amplitude.shape[0] // 2]
        if middle.size < 1 or not bool(np.any(np.isfinite(middle))):
            continue
        j, k = np.unravel_index(int(np.nanargmax(middle)), middle.shape)
        series = array[:, j, k]
        magnitudes = np.abs(series)
        usable = (
            np.isfinite(magnitudes)
            & np.isfinite(series.real)
            & np.isfinite(series.imag)
        )
        if int(usable.sum()) < 3:
            continue
        floor = 0.25 * float(np.median(magnitudes[usable]))
        if not floor > 0.0:
            # An all-zero probe records no field, so it records no phase.
            continue
        run = _longest_true_run(usable & (magnitudes >= floor))
        if run is None or run[1] - run[0] < 3:
            continue
        advances = np.diff(np.unwrap(np.angle(series[run[0]:run[1]])))
        advances = advances[np.isfinite(advances)]
        if advances.size < 2:
            continue
        per_interval = float(np.median(advances))
        if not math.isfinite(per_interval) or per_interval == 0.0:
            continue
        plane_stride = _plane_step_spacing(info, key)
        scale = ratio / float(plane_stride)
        phase = per_interval * scale
        if not math.isfinite(phase) or phase == 0.0:
            continue
        source = (
            f"{key} complex phase track at probe (j={int(j)}, k={int(k)}), "
            f"median of {int(advances.size)} unwrapped frame-to-frame advances "
            f"over {int(run[1] - run[0])} usable frames, scaled x{scale:g} "
            f"(volume stride over plane stride)"
        )
        return source, phase
    return None


def _phase_from_recorded_frequency(info, stride):
    """``(source, radians per volume frame)`` from a recorded f and ``dt_s``.

    phi = 2*pi*f*dt*stride, with BOTH numbers read from the dump and named in
    ``source``. ``f_pulse_hz`` is preferred over ``f_ref_hz`` because it is the
    recorded centre of the pulse the stored field IS: ``f_ref_hz`` is the
    parent beta's reference frequency, quoted by this dump for its phase-velocity
    note rather than as the carrier on screen. A missing or unusable ``dt_s``
    yields no number at all - a time step nobody recorded cannot be assumed.
    """
    dt = _positive_float(info.get("dt_s"))
    if dt is None:
        return None
    try:
        steps = float(int(stride))
    except (TypeError, ValueError):
        return None
    for key in ("f_pulse_hz", "f_ref_hz"):
        hertz = _positive_float(info.get(key))
        if hertz is None:
            continue
        phase = 2.0 * math.pi * hertz * dt * steps
        if not math.isfinite(phase) or phase == 0.0:
            continue
        source = (
            f"recorded {key} = {hertz:g} Hz x recorded dt_s = {dt:g} s "
            f"x stride {int(steps)} (phi = 2*pi*f*dt*stride)"
        )
        return source, phase
    return None


def _volume_aliasing(info):
    """The volume player's temporal-aliasing report, or None without a volume.

    PURE and cheap: one probe series (or two recorded scalars), no rescaling of
    the volume, no PyVista, no trame - so it can run once when the page is built
    and never on a per-frame path.

    None means THIS PAGE DOES NOT ANIMATE A VOLUME (a 2-D-only page, or a dump
    with no ``|E|`` volume), and the caller therefore draws no banner: the
    sentence names a decimation, and a page with nothing decimated has nothing
    to say.

    A report with ``phase_per_frame_rad = None`` is the other silence, and it is
    a different claim: there IS a volume, but this recording does not contain
    the phase advance between its frames, so the honest answer is "undecidable"
    with the why in ``reason``.
    """
    if not isinstance(info, dict):
        return None
    volume = info.get("e_abs_volume")
    if volume is None:
        return None
    # MEASURED from the volume's own step axis, never from the recorded
    # ``e_abs_volume_stride`` scalar: the shipped archive states 4 beside an axis
    # that runs 1, 101, 201, ... and only the axis describes the frames that are
    # actually stored (see ``_volume_decimation``).
    stride = _volume_decimation(info)
    try:
        frames = int(np.asarray(volume).shape[0])
    except (AttributeError, IndexError, TypeError, ValueError):
        frames = 0

    measured = _phase_from_complex_planes(info, stride)
    if measured is None:
        measured = _phase_from_recorded_frequency(info, stride)
    if measured is None:
        return AliasingReport(
            stride=int(stride),
            frames=int(frames),
            phase_per_frame_rad=None,
            frames_per_period=None,
            source="undecidable from this recording",
            aliased=False,
            severity="undecidable",
            reason=(
                "cannot decide: the dump stores no complex plane series to track "
                "a phase through, and no recorded frequency beside a usable "
                "dt_s. The phase advance between two volume frames is not in "
                "this recording, and it is not guessed here"
            ),
            text=None,
        )

    source, phase = measured
    degrees = math.degrees(phase)
    frames_per_period = 2.0 * math.pi / abs(phase)
    if phase > ALIASING_FULL_PERIOD_RAD:
        severity = "discontinuous"
        aliased = True
        reason = (
            f"the field advances {degrees:.1f} deg per volume frame, more than a "
            "full period (360 deg): consecutive stored frames do not continue "
            "one another's motion, so the player shows an alias of it"
        )
    elif phase > ALIASING_QUARTER_PERIOD_RAD:
        severity = "undersampled"
        aliased = True
        reason = (
            f"the field advances {degrees:.1f} deg per volume frame, more than a "
            "quarter period (90 deg), so the recording undersamples the motion "
            "against the quarter-wave convention"
        )
    else:
        severity = "none"
        aliased = False
        reason = (
            f"the field advances {degrees:.1f} deg per volume frame, within a "
            "quarter period (90 deg): the stored frames sample the motion"
        )

    text = None
    if aliased and int(stride) > 1:
        text = _aliasing_sentence(int(stride))
    elif aliased:
        reason += (
            "; no banner is drawn, because the sentence names a decimation and "
            "this volume is stored every step (stride 1)"
        )
    return AliasingReport(
        stride=int(stride),
        frames=int(frames),
        phase_per_frame_rad=float(phase),
        frames_per_period=float(frames_per_period),
        source=source,
        aliased=bool(aliased),
        severity=severity,
        reason=reason,
        text=text,
    )


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


def _xcut_cadence_clause(info: dict) -> str:
    """How often the two x-cut planes are written, read from the FILE.

    The archive does not record the x-cut stride as a number. It records the step
    number of every stored frame of every plane -- ``frame_index`` for
    ``ez_ycut``, ``frame_index_xcut`` for the two x-cuts -- so the cadence is
    whatever those steps say it is for the file in hand. That is the point of the
    two axes sharing one time base: a reader that repeated the exporter's stride
    as a constant here would keep printing a cadence the file no longer has, and
    nothing would raise. One x-cut frame has no spacing to report and says so
    rather than inventing one.
    """
    index = info.get("frame_index_xcut")
    if index is None:
        return "written at their own recorded cadence"
    try:
        index = np.asarray(index, dtype=np.int64).ravel()
    except (TypeError, ValueError):
        return "written at their own recorded cadence"
    if index.size < 2:
        return "written at their own recorded cadence"
    gaps = np.diff(index)
    if int(gaps[0]) <= 0 or not bool(np.all(gaps == gaps[0])):
        return "written at their own recorded cadence"
    step = int(gaps[0])
    if step == 1:
        return "written on every kept y-cut frame"
    return f"written every {step} steps"


def load_vis(path: Path) -> dict:
    """Load an ``emfit.vis/2`` animation dump. numpy only, no pyvista.

    Three planes are stored and they are NOT interchangeable: ``ez_ycut`` is an
    x-z sheet at one fixed y (``nt`` frames), while the two x-cuts are y-z sheets
    at two fixed x (``nt_x`` frames, at whatever cadence their own
    ``frame_index_xcut`` states). That asymmetry is why the time of a frame is
    rebuilt from that plane's own ``frame_index`` array below instead of from a
    shared counter: indexing an x-cut frame number into ``t_ns`` would read the
    wrong instant of the march and never raise.

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
            # The length a step axis must have IS its surface's frame count, read
            # from the spec derived off that self-same axis, so the spec and the
            # plane arrays cannot disagree about how many frames were stored.
            (
                "frame_index",
                _surface_frame_count(info, "ez_ycut", info["nt"]),
                info["nt"],
            ),
            (
                "frame_index_xcut",
                _surface_frame_count(info, "ez_xcut", info["nt_x"]),
                info["nt_x"],
            ),
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

    # THE PLAYER'S STEP AXIS, built once, here, so the label the player prints is
    # READ OFF THE DUMP instead of counted from the slider position. The clock is
    # the PLANE family's - ``frame_index``, one recorded plane frame per solver
    # step - because that is the series the player steps: the |E| volume is the
    # coarser recording and is drawn as a DECIMATED LAYER on this clock
    # (``_volume_player_plan``), so it no longer shortens it. What the dump does
    # NOT record is not invented: a missing ``nsteps`` falls back to the last
    # recorded step, and a missing or unusable ``dt_s`` leaves ``time_seconds``
    # None rather than making a time base up.
    info[TIME_AXIS_KEY] = build_time_axis(
        step_index=info["frame_index"],
        n_steps=info["nstep"],
        dt_s=info["dt_s"],
        n_frames=info["nt"],
    )

    # THE PER-SURFACE SAMPLING, derived once here from the axes just validated:
    # which step each stored frame of each plane family was captured at. Every
    # frame->step conversion on the page reads this, so one stride and one offset
    # are in force instead of a copy per call site.
    info[SURFACE_SPECS_KEY] = {
        name: _derive_surface_spec(info, name) for name in ("ez_ycut", "ez_xcut")
    }

    # Computed once, here, from every stored frame of every plane: the viewer
    # then has no way to rescale between frames because it is never given a
    # per-frame number to rescale with.
    vmin, vmax, empty = global_clim((ycut, near, far))
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
        f"frame, the median of each frame's p{COLOR_PERCENTILE:g} |Ez| so a "
        f"single hot spot cannot dim the whole clip (the brightest "
        f"{100.0 - COLOR_PERCENTILE:g} % of cells in a frame clip)"
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

    ``nt`` is the PLAYER's timeline length, which is the plane family's OWN
    count, ``_position_count``, unchanged for both views: the |E| volume is a
    decimated layer and the x-cut planes a held one, neither sets the length.
    When the two numbers differ the line quotes both - ``animation, 3
    of 12 frames on ez_ycut`` - rather than letting one number be read as a
    claim about the array it names. When they agree the plain form is
    unchanged.
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
    frames = int(nt)
    try:
        # The stored `ez_ycut` array's own count, from the DUMP: on a page whose
        # timeline is the volume's clock this is the larger number, and the
        # header has to name both instead of quoting one for the other.
        stored = int(info["nt"])
    except (KeyError, TypeError, ValueError):
        stored = frames
    if stored != frames:
        return f"showing {name} - animation, {frames} of {stored} frames on ez_ycut"
    return f"showing {name} - animation, {frames} frames on ez_ycut"


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


def _boot_structure_id(structures=None):
    """The entry a bare invocation boots on, and the line to say when it cannot.

    Returns ``(id, note)``: the id to boot on, and the ONE sentence to print on
    stderr when that id is not the preferred entry (``note`` is None when
    nothing needs saying). Announcing is left to the caller because this runs
    while the parser is being built, and only a run that actually boots on the
    default has anything to announce.

    ``PREFERRED_STRUCTURE`` is the shipped example volume, so the page a
    no-argument run lands on has a volume and a frame axis to look at. That
    artefact is a ONE-TIME release, though, and a checkout that predates it - or
    one where someone deleted it - must still boot: the answer is then the
    legacy default, stated out loud rather than substituted in silence, because
    a boot that quietly served a different entry is the lie this module refuses
    everywhere else.

    Decided by the same rule as the picker and the CLI
    (``_structure_is_record_only``: is the npz this entry names on disk), so an
    entry whose dump was moved or deleted falls back here too. A registry that
    does not carry the entry at all is the same answer for the same reason.
    """
    structures = load_structures() if structures is None else structures
    preferred = _structure_by_id(PREFERRED_STRUCTURE, structures)
    if not _structure_is_record_only(preferred):
        return PREFERRED_STRUCTURE, None
    return DEFAULT_STRUCTURE, (
        f"[poc_app] {PREFERRED_STRUCTURE}: "
        f"{_structure_dump_path(preferred) or 'its field dump'} is not on disk "
        f"- booting on the legacy default {DEFAULT_STRUCTURE} instead."
    )


def _renderable_structure_ids(structures) -> list:
    """The ids that can actually be opened: those with a field dump on disk."""
    return [
        str(entry.get("id"))
        for entry in structures
        if entry.get("id") and not _structure_is_record_only(entry)
    ]


def _record_only_refusal(requested_id, structures) -> str:
    """The refusal for a dump report on an entry with no dump: name the way through.

    Used by the two dump-READING exits (--list-keys, --dump-state), which have no
    board to describe and so cannot fall back to one. The server itself no longer
    refuses such an entry: it serves its BOARD page, so this message says so
    rather than implying the entry cannot be opened at all.
    """
    renderable = ", ".join(_renderable_structure_ids(structures))
    return (
        f"--structure {requested_id} is record only: this registry entry has "
        f"S-parameters recorded but no field dump on disk, so there is no field "
        f"data to list or to dump - the entry opens as its BOARD page and nothing "
        f"else, and this viewer will not substitute a different structure's; "
        f"renderable structures: {renderable or 'none'}"
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
    # A registry entry may record no S-parameters at all (sparams: null), and then
    # there is no path to read: read NOTHING rather than handing None to _read_json,
    # which would print a TypeError-flavoured "unreadable" line on every open.
    data = (
        record
        if isinstance(record, dict)
        else (_read_json(path) if path is not None else None)
    )
    name = Path(path).name if path is not None else "the S-parameter record"
    if not isinstance(data, dict):
        return None, f"no readable S-parameter record at {path or 'no path given'}"
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

    The two frame counts returned here are FACTS ABOUT THE FILE - how many
    frames each stored array holds - not the length of the player's clock: that
    is the timeline's, ``_position_count``, and on a recorded dump a position is
    one recorded plane frame. There is ONE clock: the x-cut planes are a LAYER
    on it, held between their own captures, exactly as the |E| volume is, so
    neither can shorten it nor rescale it when the view is switched.
    ``wall_clock_s`` is the timeline's count over ``fps``, i.e. the play time at ONE
    POSITION PER TICK - the base rate the speed control is expressed against, and
    therefore the one reading that does not depend on where the operator left that
    control. The loop advances ``DEFAULT_PLAY_RATE`` positions per tick when the
    page opens (and whatever rate the player bar is on afterwards, 1 to 8), so the
    time the page actually takes is that divided by the factor; ``_play_caption``
    does that division on the page, beside the select, so the state dump can keep
    publishing the reading that stays true whichever speed is selected. The
    ``planes`` entries below keep saying how many frames each stored array HOLDS,
    which is a fact about the file rather than about the timeline.
    """
    fps = max(1, int(fps))
    vmin, vmax = info["color_range"]
    dt_ns = float(info["dt_s"]) * 1e9
    # Facts about the FILE, not about the player's clock: how many frames each
    # stored array holds. The clock is ``_position_count``; on a recorded dump
    # the two agree, because a position is one recorded plane frame.
    nt = _surface_frame_count(info, "ez_ycut", info["nt"])
    nt_x = _surface_frame_count(info, "ez_xcut", info["nt_x"])
    t_ns = info["t_ns"]
    cell_mm = _cell_mm(info)
    return {
        "frames": nt,
        "frames_xcut": nt_x,
        "fps": fps,
        "wall_clock_s": round(nt / float(fps), 6),
        "sim_time_ns": {
            "first": _finite(t_ns[0]) if t_ns.size else None,
            "last": _finite(t_ns[-1]) if t_ns.size else None,
            "dt": _finite(dt_ns),
            "basis": (
                "t_ns = frame_index * dt_s; the two x-cut planes are "
                f"{_xcut_cadence_clause(info)} and carry their own "
                "frame_index_xcut, so their frame number must never be used to "
                "index t_ns"
            ),
        },
        "colour": {
            "vmin": _finite(vmin),
            "vmax": _finite(vmax),
            "percentile": COLOR_PERCENTILE,
            "empty": bool(info["color_range_empty"]),
            "basis": (
                "one limit for every frame of every plane: the MEDIAN of each "
                f"frame's {COLOR_PERCENTILE:g}th percentile of |Ez|, so a single "
                "hot spot cannot dim the whole clip; a per-frame limit would "
                "renormalise each step and hide the decay"
            ),
        },
        "planes": [
            {
                "key": "ez_ycut",
                "label": "x-z plane through the strip (one fixed y sample)",
                "shape": [int(n) for n in info["ez_ycut"].shape],
                "frames": int(info["nt"]),
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


def _page_has_board(info) -> bool:
    """Whether ``info`` already carries the board's own scale.

    The ONE number that decides it is the cell size: every placement in
    ``_vis_geometry`` is ``count x cell``, so a page with a cell and two counts
    has a board to draw and a page without one has nothing to draw it from.
    """
    if not isinstance(info, dict):
        return False
    return _finite(info.get("cell_m")) is not None


def _builder_board() -> dict:
    """The board a page with NO data draws, from the builder that defines it.

    WHY the builder and not a record: :func:`emfit.studies.microstrip_reference_board`
    IS the default cross-section of :func:`emfit.studies.microstrip_wave` as a
    board spec, and ``MicrostripBoard.to_cell_counts`` is the one function that
    turns a spec into the mesh that study builds. Taking the numbers from there
    means a page with no record on disk still draws the board the study would
    solve on, at the scale the builder guarantees - and a spec that stops fitting
    the mesh raises the builder's own ValueError here instead of producing a
    plausible-looking picture.

    WHY ``load_x_mm`` is NaN and ``xcut_near_mm`` is the port plane: the
    reference board declares NO load (``loads == ()``: the strip runs out into
    the far absorber), so there is no load plane to open a gap at. The strip is
    then ONE run from the port plane to the far wall, which is exactly what the
    two segment sites in ``_vis_geometry`` draw when the near cut sits on the
    port: the feed segment needs a load this board does not have, and the stub
    carries the whole line.

    ``x_mm`` is the node axis the stub ends on - cell x index, so its last entry
    is one cell short of the box, exactly as the axis a dump records.

    Returns:
        An ``info`` dict with every key the board draw sites read.
    """
    # Imported on use, like every other emfit use in this module: the CLI paths
    # (--help, --list-keys) stay stdlib + numpy only.
    from emfit import studies as studies_mod

    spec = studies_mod.microstrip_reference_board()
    counts = spec.to_cell_counts(
        n_sub=studies_mod.MS_N_SUB, n_pml=studies_mod.MS_N_PML
    )
    cell = counts["cell"]
    cell_mm = cell * 1e3
    # The outline IS the grid: the builder sizes ``length`` to ``x_far`` and
    # ``width`` to the lateral cells, so the two counts are the box over the cell
    # and never a second copy of the study's arithmetic.
    nx = int(round(spec.length / cell))
    return {
        "format": None,
        "cell_m": cell,
        "nx": nx,
        "ny": int(round(spec.width / cell)),
        "nz": studies_mod.MS_N_SUB + studies_mod.MS_N_AIR + studies_mod.MS_N_TOP,
        "substrate_h_mm": spec.h * 1e3,
        "strip_w_mm": spec.w * 1e3,
        "port_x_mm": spec.x_port * 1e3,
        "load_x_mm": float("nan"),
        "xcut_near_mm": spec.x_port * 1e3,
        "x_mm": [index * cell_mm for index in range(nx)],
    }


def _builder_page(structure_id=None) -> dict:
    """The page dict around :func:`_builder_board`: no path, no record, no timeline."""
    return {
        "path": None,
        "info": _builder_board(),
        "planes": None,
        "multifreq": None,
        "record": None,
        "structure_id": structure_id,
        "is_vis": False,
    }


def _bare_board_page(structure=None, record_path=None, structure_id=None) -> dict:
    """A page dict for a structure whose BOARD is drawn with no dump at all.

    WHY this exists: a record-only structure has a study record on disk but no
    field dump, so there is no field to paint - yet the board the study solved on
    is often fully described by that record (cell, grid counts, substrate height,
    strip width, both port positions). Booting the viewer with nothing to show
    used to leave the centre column empty; this hands the same page plumbing a
    page whose ``info`` carries those numbers, so ``_vis_geometry`` draws the
    substrate, the strip and the port wires exactly as it does over a dump.

    WHY every unknown is NaN and never a constant: the draw sites test
    ``isfinite()``, so a number the record did not carry must arrive as NaN to
    keep that part absent. A fabricated cell size would put the board at a scale
    nobody measured.

    WHY a record that resolves NO mesh falls through to :func:`_builder_page`:
    the numbers then come from the builder that defines the default cross-section
    (emfit.studies.microstrip_reference_board) rather than from a constant written
    here, and the fallback replaces the WHOLE board - a record carrying a cell but
    not the counts is still a scale nobody measured, and mixing the two sources in
    one dict would be a board neither of them describes.

    WHY ``is_vis`` is False and there is no ``nt``: this page claims NO timeline,
    which is the existing "bare field dump" case in run_web_vis (no player, no
    frame range), not a new kind of page.
    """
    sid = structure_id or (
        structure.get("id") if isinstance(structure, dict) else None
    )
    path = record_path
    if path is None and structure is not None:
        path = _structure_artifact_path(structure, "sparams")
    record = load_record(path) if path is not None else None
    geom = _geom_mm({}, record)
    geometry = record.get("geometry") if isinstance(record, dict) else None
    geometry = geometry if isinstance(geometry, dict) else {}

    def _mm(key):
        """A resolved millimetre value, or NaN when neither source had it."""
        value = _finite(geom.get(key))
        return value if value is not None else float("nan")

    def _count(key, index):
        """A grid count from the record's geometry, else from its grid list."""
        value = _as_float(geometry.get(key))
        if value is None:
            grid = geometry.get("grid")
            if isinstance(grid, list) and len(grid) > index:
                value = _as_float(grid[index])
        return value if value is not None else float("nan")

    board = {
        "format": None,
        "cell_m": _mm("cell_mm") * 1e-3,
        "nx": _count("nx", 0),
        "ny": _count("ny", 1),
        "nz": _count("nz", 2),
        "substrate_h_mm": _mm("substrate_h_mm"),
        "strip_w_mm": _mm("strip_w_mm"),
        "port_x_mm": _mm("port_x_mm"),
        "load_x_mm": _mm("load_x_mm"),
        "xcut_near_mm": _mm("xcut_near_mm"),
    }
    if not _page_has_board(board):
        print(
            "[poc_app] no study record with a mesh for "
            + _structure_label(structure)
            + ": the board is drawn from the emfit builder instead",
            file=sys.stderr,
        )
        return _builder_page(sid)
    return {
        "path": None,
        "info": board,
        "planes": None,
        "multifreq": None,
        "record": record,
        "structure_id": sid,
        "is_vis": False,
    }


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

    The ANIMATION page's ``e_abs_volume`` is the THIRD route in: a real volume,
    one the loader checked against these very ``nx``/``ny``/``nz``
    (poc_app.py:5452-5475). It is read here, and not only through the memo, for
    a timing reason: that page writes the memo when it first DRAWS
    (``_volume_frame_grid``, :14690), while its cut sliders are wired before any
    draw (:15846), so the memo alone would leave them no grid at boot - and no
    grid means the ``plane_ez`` fallback below, which is a KeyError on a dump
    that has no plane stack. The answer is the same either way, which is the
    point: before and after the first draw the cuts index ONE lattice.

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
    if (
        info.get(VOLUME_KEY) is None
        and not (isinstance(raw, dict) and raw.get("e") is not None)
        and info.get("e_abs_volume") is None
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

    A y or z cut has no axis to resample along: the sheet is ONE of the
    captured x-planes, taken slice-of-one in ``build_cut_sheets``
    (server/poc_app.py:9120; ``plane[:, j : j + 1, :]`` at :9173 and
    ``plane[:, :, k : k + 1]`` at :9181), so the planes row names that stored
    plane AND how many were captured.  Without the count the row understates
    how little the cut shows.  ``n_st`` is the captured station count ONLY on
    the planes branch (:8992, ``n_st, n_j, n_k = plane.shape``); on the volume
    branch it is the |E| volume's own ``nx`` (:8985), a different number, so
    the volume row must never print it and says instead that its millimetres
    are cell centres.  Both rows end in "no interpolation" because neither
    resamples anything.  ``.get`` because a fake layout may predate a key.
    """
    text = (
        f"cut y = {layout['j'] + 1}/{layout['n_j']} "
        f"(y = {layout['y_mm']:.4f} mm)   "
        f"cut z = {layout['k'] + 1}/{layout['n_k']} "
        f"(z = {layout['z_mm']:.4f} mm)   one sample each"
    )
    if layout.get("source") == "volume":
        return text + "   (|E| volume cells, cell centres, no interpolation)"
    n_st = layout.get("n_st")
    # A guessed count is exactly the defect this row is fixing, so anything
    # that is not a positive int drops the clause instead of printing a number.
    # ``isinstance(True, int)`` is True, hence the bool test: "True stations"
    # would be worse than no count at all.
    if not isinstance(n_st, int) or isinstance(n_st, bool) or n_st < 1:
        return text + "   (one stored x-plane, no interpolation)"
    return text + (
        f"   (one stored x-plane of {n_st} captured station"
        f"{'' if n_st == 1 else 's'}, no interpolation)"
    )


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
        if not _volume_layer_enabled():
            # The sheets are drawn BY the |E| layer: with that layer off pyvista
            # refused nothing, and saying it did would be the false claim.
            return ["cut sheets: not drawn - the |E| volume layer is off"]
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
        f"({_xcut_cadence_clause(info)})"
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
        f"{vmax:.6e} (median of each frame's p{COLOR_PERCENTILE} of |Ez|, so a "
        f"single hot spot cannot dim the whole clip); a per-frame limit would "
        f"renormalise a decaying pulse"
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


# --- the two colour bars of a field page -------------------------------------
#
# TWO fields, TWO bars: the captured |Ez| planes carry a LINEAR scale, the |E|
# volume a LOG one, and the FFT normalisation makes the colocated volume ~2053x
# smaller in V/m - so one bar over both would be read at the wrong scale.
#
# WHY the titles are module constants: a bar's TITLE is also the KEY pyvista
# stores it under, and re-using a key is NOT a second bar.  ``add_scalar_bar``
# answers a repeated title by MERGING into the standing bar and widening the
# range it shows to the UNION of every mapper bound to that key so far.  On a
# page that repaints a PER-FRAME range that union only ever grows, so the bar
# slowly stops describing the frame on screen.  One distinct title per field,
# and every rebuild REMOVES its own bar before making a new one.
#
# WHY the positions are explicit: a bar placed by pyvista takes a slot from a
# finite pool and derives its x from that slot, so a bar rebuilt once per frame
# is a bar whose position walks.  Two hand-placed rectangles cannot overlap
# (the plane bar's right edge is left of the volume bar's left edge), and no
# slot is ever consumed.
PLANE_BAR_TITLE = "Ez (Linear)"
VOLUME_BAR_TITLE = "|E| (Log)"

#: The bar the fallback |E| volume gets on a pyvista that refuses ``log_scale``:
#: the same field on the same range, but a linear ramp - and the title says so.
VOLUME_BAR_TITLE_LINEAR = "|E| (Linear)"

#: Normalised viewport rectangles: ``(position_x, position_y)`` with the theme's
#: own bar size.  The plane bar sits on the left, the volume bar on the right.
PLANE_BAR_POSITION = (0.02, 0.28)
VOLUME_BAR_POSITION = (0.88, 0.28)
BAR_WIDTH = 0.08
BAR_HEIGHT = 0.45


def plane_bar_args() -> dict:
    """``add_scalar_bar`` arguments for the plane bar, title and geometry both.

    Handed to ``add_mesh(scalar_bar_args=...)`` (pyvista forwards the mapping
    straight into ``add_scalar_bar``) and to ``add_scalar_bar`` itself, so the
    boot bar, both sheet rebuilds and the per-family swap are ONE definition -
    which is what keeps them from disagreeing about the title or the place.
    """
    return {
        "title": PLANE_BAR_TITLE,
        "position_x": PLANE_BAR_POSITION[0],
        "position_y": PLANE_BAR_POSITION[1],
        "width": BAR_WIDTH,
        "height": BAR_HEIGHT,
        "vertical": True,
    }


def _remove_scalar_bar(plotter, title: str) -> None:
    """Remove the bar stored under ``title``, when this plotter has one.

    Guarded and idempotent: it runs on the frame path, and a plotter without a
    bar - or without a scalar-bar API at all - must cost nothing.
    """
    try:
        if title in plotter.scalar_bars:
            plotter.remove_scalar_bar(title=title, render=False)
    except Exception as exc:  # noqa: BLE001 - a bar is decoration
        print(f"[poc_app] stale colour bar kept: {exc}", file=sys.stderr)


def _place_scalar_bar(plotter, *, title: str, mapper, position) -> None:
    """Stand ONE bar up under ``title``, at ``position``, reading ``mapper``.

    WHY remove-then-add and not an update: the title is a KEY, and a second
    ``add_scalar_bar`` on a standing key MERGES - the range it shows becomes the
    union of every mapper bound to that key, and the numbers on it stop being
    the ones the caller resolved.  Removing first is what makes the bar read the
    mapper handed in HERE, which is the whole point of rebuilding it per frame.

    Guarded: a page whose plotter has no scalar-bar API keeps its picture.
    """
    _remove_scalar_bar(plotter, title)
    try:
        plotter.add_scalar_bar(
            title=title,
            mapper=mapper,
            position_x=position[0],
            position_y=position[1],
            width=BAR_WIDTH,
            height=BAR_HEIGHT,
            vertical=True,
            render=False,
        )
    except Exception as exc:  # noqa: BLE001 - a bar is decoration
        print(
            f"[poc_app] colour bar {title!r} not drawn: {exc}", file=sys.stderr
        )


def _draw_volume_scene(
    plotter,
    info: dict,
    *,
    grid,
    cut_layout: dict,
    cell_mm: float,
    clim_override=None,
    clim_mode=None,
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

    ``clim_mode`` names the WINDOW that range was measured over, and is here for
    one reason: the |E| bar's title has to state it (``_volume_bar_title``). It
    moves no range - ``clim_override`` already IS the range - so passing it
    changes the reading on the bar and nothing else. ``None`` (what
    ``_draw_scene`` passes) titles the bar for the default window, which is the
    window ``abs_meta["clim"]`` is measured over.

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
    # The actor the |E| bar READS and the title that bar may honestly carry:
    # the retry below draws a LINEAR volume, and a linear ramp under a log title
    # would be the one lie a colour bar must not tell.
    abs_actor = None
    abs_bar_title = _volume_bar_title(clim_mode)
    # The |E| volume and its bar are the LAYER (`_volume_layer_enabled`): the
    # cut sheets below are not, and are drawn either way.
    if abs_image is not None and _volume_layer_enabled():
        # WHY the bar is NOT made here: ``add_volume(show_scalar_bar=True)``
        # keys its bar on a title, and the next frame of this page re-uses that
        # same title - which pyvista answers by MERGING into the standing bar
        # and widening it to the UNION of every mapper bound so far.  A
        # per-frame range would then be painted over by its own history.  The
        # bar is placed by hand BELOW, from the actor this call returns.
        # WHY its title is not the plane stack's: these are two different
        # fields, and the FFT normalisation makes the colocated volume ~2053x
        # smaller in V/m than the captured |Ez| planes, so one bar carrying the
        # other's title would be read as the other's scale.
        try:
            abs_actor = plotter.add_volume(
                abs_image,
                scalars="e_abs",
                cmap="turbo",
                log_scale=True,
                clim=volume_clim,
                show_scalar_bar=False,
            )
            abs_drawn = True
        except TypeError as exc:
            # An older pyvista accepts every one of these arguments EXCEPT
            # ``log_scale``. The same image on the same clim is still worth
            # showing, so it is retried ONCE without log_scale, on a title
            # that no longer claims a log bar - and never a third time.
            print(f"[poc_app] |E| volume not drawn: {exc}", file=sys.stderr)
            try:
                abs_actor = plotter.add_volume(
                    abs_image,
                    scalars="e_abs",
                    cmap="turbo",
                    clim=volume_clim,
                    show_scalar_bar=False,
                )
                abs_drawn = True
                abs_bar_title = _volume_bar_title(clim_mode, log_scale=False)
            except Exception as exc_again:  # noqa: BLE001 - see below
                abs_actor = None
                print(
                    f"[poc_app] |E| volume not drawn: {exc_again}",
                    file=sys.stderr,
                )
        except Exception as exc:  # noqa: BLE001 - a picture is not a crash
            # Losing the volume must cost the VOLUME: the outline, the axes,
            # the board, the markers and both corner labels are drawn after
            # this branch, and an exception escaping here would take them all
            # (``_redraw_scene`` would swallow it and keep a stale picture).
            abs_actor = None
            print(f"[poc_app] |E| volume not drawn: {exc}", file=sys.stderr)
        if abs_actor is not None:
            # The bar follows the frame it describes: it reads THIS actor's
            # mapper, on the clim this call was handed (``volume_clim``, i.e.
            # the caller's ``clim_override`` when there is one). WHY the mapper
            # lookup is guarded too: a bar is decoration, and a plotter whose
            # volume actor carries no mapper must still keep its picture.
            try:
                abs_mapper = abs_actor.mapper
            except Exception as exc:  # noqa: BLE001 - decoration only
                abs_mapper = None
                print(
                    f"[poc_app] |E| colour bar not drawn: {exc}",
                    file=sys.stderr,
                )
            if abs_mapper is not None:
                _place_scalar_bar(
                    plotter,
                    title=abs_bar_title,
                    mapper=abs_mapper,
                    position=VOLUME_BAR_POSITION,
                )
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
    elif not abs_drawn and _volume_layer_enabled():
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


# --- the two boxes the plane page frames -------------------------------------
#
# The plane page draws TWO extents and they are NOT the same box: the DOMAIN the
# solver ran on, and the narrower WINDOW of stations that was actually captured
# and saved. It used to draw one black outline taken from the field grid, and
# the field grid spans the captured stations - measured on the shipped Build A
# dump that box was x = 10.4 .. 20.0 mm inside a domain of 0.0 .. 24.4 mm, so
# the one line that was meant to frame the simulation framed the capture. Both
# boxes are derived in _plane_extent_mm and nowhere else.

#: How long one dash of the captured-window outline aims to be, in mm. The dash
#: count is rounded per edge, so every edge begins and ends on a dash.
DASH_TARGET_MM = 4.0


def _plane_extent_mm(info: dict, stations_mm=None) -> dict:
    """The DOMAIN box and the captured-station WINDOW, both in millimetres.

    ``domain`` is ``(x0, x1, y0, y1, z0, z1)``. The visualisation dumps carry
    the stored node coordinates ``info["x_mm"]`` / ``y_mm`` / ``z_mm`` and those
    are read when present. The plane dumps carry only the node counts
    ``nx``/``ny``/``nz`` plus ``cell_m``, and build_grid lays sample ``i`` at
    ``i * cell``, so there the frame is the LAST node, ``(n - 1) * cell`` - not
    ``n * cell``, which would be one cell too wide: on the shipped dump
    ``nx * cell`` is 24.8 mm while the last node is 24.4 mm. Only one of the two
    can be the frame of a picture drawn from those samples, and it is the one
    the samples sit on. ``domain`` is None when the dump carries neither the
    arrays nor a usable count/cell pair, and the caller then keeps the field
    grid's own outline rather than inventing a frame.

    ``window`` is the same box narrowed on x to the captured stations
    (``stations_mm[0] .. stations_mm[-1]``). It is None when there is no station
    axis, when the axis holds fewer than two distinct stations (a window with no
    width is not a box), when the domain is unknown (its lateral extent would
    then have to be guessed), or when the axis already spans the whole domain -
    a dashed line lying on the solid one reads as an artefact, not as a fact.

    The lateral (y/z) extent of the window IS the domain's: a captured plane is
    a full y-z slice through the line, so the station axis is the only one the
    capture narrows. That assumption is stated here because this is the one
    place the two boxes' numbers come from.
    """

    def _span(axis):
        try:
            values = np.asarray(axis, dtype=float).ravel()
        except (TypeError, ValueError):
            return None
        values = values[np.isfinite(values)]
        if values.size == 0:
            return None
        return float(values.min()), float(values.max())

    def _counts_span(source):
        """The same box from the node COUNT and the cell size, no arrays.

        Plane dumps store ``nx``/``ny``/``nz`` and ``cell_m`` only, and
        build_grid puts sample ``i`` at ``i * cell``, so the last node is
        ``(n - 1) * cell``. Returns None on anything missing or unusable.
        """
        try:
            cell_mm = float(source.get("cell_m")) * 1e3
            counts = [int(source[key]) for key in ("nx", "ny", "nz")]
        except (TypeError, ValueError, KeyError):
            return None
        if not np.isfinite(cell_mm) or cell_mm <= 0.0:
            return None
        if any(count < 1 for count in counts):
            return None
        return tuple(
            0.0 if index % 2 == 0 else (counts[index // 2] - 1) * cell_mm
            for index in range(6)
        )

    domain = None
    if isinstance(info, dict):
        x = _span(info.get("x_mm"))
        y = _span(info.get("y_mm"))
        z = _span(info.get("z_mm"))
        if x is not None and y is not None and z is not None:
            domain = (x[0], x[1], y[0], y[1], z[0], z[1])
        else:
            domain = _counts_span(info)

    window = None
    if domain is not None and stations_mm is not None:
        stations = _span(stations_mm)
        if stations is not None and stations[1] > stations[0]:
            candidate = (
                stations[0],
                stations[1],
                domain[2],
                domain[3],
                domain[4],
                domain[5],
            )
            # Only when it really is narrower: coincident boxes are one box.
            if (
                abs(candidate[0] - domain[0]) > 1e-12
                or abs(candidate[1] - domain[1]) > 1e-12
            ):
                window = candidate
    return {"domain": domain, "window": window}


def _box_edges(box) -> list:
    """The 12 edges of an axis-aligned box as pairs of (3,) endpoints."""
    x0, x1, y0, y1, z0, z1 = (float(value) for value in box)
    corners = {
        (i, j, k): np.array(
            [x1 if i else x0, y1 if j else y0, z1 if k else z0], dtype=float
        )
        for i in (0, 1)
        for j in (0, 1)
        for k in (0, 1)
    }
    edges = []
    for (i, j, k), start in corners.items():
        for axis in range(3):
            key = [i, j, k]
            if key[axis]:
                continue
            key[axis] = 1
            edges.append((start, corners[tuple(key)]))
    return edges


def _dashed_box_segments(box, target_mm: float = DASH_TARGET_MM):
    """The box's 12 edges as DASHES: ``(points, line cells)`` for one PolyData.

    WHY dashes as geometry and not a line-stipple property: a stipple set on a
    VTK property can be ignored by a render backend, and then the second box
    draws solid - indistinguishable from the domain box, which is the one thing
    this outline exists to prevent. Dashes as segments are in the buffer, so
    they are drawn wherever the line is drawn, and their count can be measured
    instead of believed.

    Each edge is cut into ``k`` dashes separated by ``k - 1`` equal gaps, ``k``
    rounded from that edge's own length, so every edge starts and ends on a dash
    and a long edge is not one speck. ``target_mm`` is the dash length aimed at;
    the rounding is what makes the pattern fill the edge exactly.
    """
    points = []
    lines = []
    target = float(target_mm)
    for start, end in _box_edges(box):
        length = float(np.linalg.norm(end - start))
        if length <= 0.0:
            continue
        dashes = max(3, int(round(length / target))) if target > 0 else 3
        step = length / (2 * dashes - 1)
        for i in range(dashes):
            first = start + (end - start) * ((2 * i) * step / length)
            second = start + (end - start) * ((2 * i + 1) * step / length)
            points.extend((first, second))
            index = len(points) - 2
            lines.extend((2, index, index + 1))
    return np.asarray(points, dtype=float).reshape(-1, 3), lines


def _add_extent_outlines(plotter, info: dict, grid, stations_mm=None) -> dict:
    """Draw the domain box SOLID and the captured window DASHED inside it.

    Returns what was really drawn - ``{"domain": ..., "window": ...}`` - so the
    corner legend can name the boxes that are on screen and stay silent about a
    window that was skipped or that pyvista refused. The two boxes come from
    ``_plane_extent_mm``, so the picture and the legend cannot derive them
    twice and disagree.
    """
    import pyvista as pv

    extent = _plane_extent_mm(info, stations_mm)
    domain = extent["domain"]
    if domain is None:
        # No stored axis: the field grid is the only extent this dump states.
        plotter.add_mesh(grid.outline(), color="black", line_width=1)
        return {"domain": None, "window": None}

    x0, x1, y0, y1, z0, z1 = domain
    # A two-point-per-axis image on the domain's own corners: its outline has
    # exactly the domain's bounds, so the frame cannot drift from the numbers by
    # restating them in a second constructor.
    box = pv.ImageData()
    box.dimensions = (2, 2, 2)
    box.spacing = (x1 - x0, y1 - y0, z1 - z0)
    box.origin = (x0, y0, z0)
    plotter.add_mesh(box.outline(), color="black", line_width=1)

    window = extent["window"]
    drawn = None
    if window is not None:
        # Guarded like every other optional layer here: a window that cannot be
        # built costs the window, never the domain frame, the axes, the board,
        # the markers or the two corner labels drawn after it.
        try:
            points, lines = _dashed_box_segments(window)
            plotter.add_mesh(
                pv.PolyData(points, lines=lines),
                color="black",
                line_width=2,
                render=False,
            )
            drawn = window
        except Exception as exc:  # noqa: BLE001 - see comment above
            print(
                f"[poc_app] captured-window outline not drawn: {exc}",
                file=sys.stderr,
            )
    return {"domain": domain, "window": drawn}


def _extent_legend(extent: dict) -> str:
    """The corner-legend sentence naming the boxes that are on screen."""
    domain = (extent or {}).get("domain")
    if domain is None:
        return ""
    text = (
        "black box = simulated domain x = "
        f"{domain[0]:.4f} .. {domain[1]:.4f} mm, y = {domain[2]:.4f} .. "
        f"{domain[3]:.4f} mm, z = {domain[4]:.4f} .. {domain[5]:.4f} mm"
    )
    window = extent.get("window")
    if window is not None:
        text += (
            "\ndashed box = captured window x = "
            f"{window[0]:.4f} .. {window[1]:.4f} mm: the stations saved in "
            "this dump"
        )
    return text


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
        # The |E| VOLUME is OPT-IN (`SHOW_VOLUME_LAYER_DEFAULT`) and is gated
        # INSIDE `_draw_volume_scene`, not here: the two cut sheets are the
        # page's field and are drawn with the layer off as well, so gating the
        # whole call is what once took the operator's planes away.

    # The ONE derivation of what this page frames: the domain box solid, the
    # captured station window dashed inside it (_plane_extent_mm). This used to
    # be ``grid.outline()``, and the field grid spans the CAPTURED stations, so
    # the page framed the window and called it the domain.
    extent = _add_extent_outlines(plotter, info, grid, planes.get("stations_mm"))
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
    # Which box is which, from the same dict that decided what to draw.
    extent_text = _extent_legend(extent)
    if extent_text:
        legend_lines.append(extent_text)
    plotter.add_text(
        _marker_text(planes, legend_lines),
        name="marker_legend",
        position="lower_left",
        font_size=8,
        color="black",
    )
    # The step indicator is NOT drawn here, and no longer on the canvas at all:
    # the ONE indicator is ``state.frame_label``, composed by
    # :func:`_frame_label` and rendered once by the side panel
    # (``server/um3k_panels.py``). A label added here would be a SECOND clock
    # beside that one - and the ``plotter.clear()`` this function opens with
    # would wipe it on the next rebuild anyway.
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
    # One still, and the profile now says it was the CUT slider that asked (see
    # _push_still): this push never went through _show and was invisible before.
    _push_still(handles.get("view"), "cut")


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


def _port_is_free(host: str, port: int) -> bool:
    """True when NOTHING is listening on ``host:port`` - a test bind succeeds.

    SO_REUSEADDR is set because the real server sets it: without it a port left
    in TIME_WAIT by the previous run reads as busy here, while the server itself
    would have bound it and the run would move a port for no reason. It does NOT
    make a port with a live listener bindable, which is the case this exists to
    detect. A probe that cannot even open a socket counts as busy, so the caller
    moves on instead of starting a server that would fail the same way.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, int(port)))
    except OSError:
        return False
    finally:
        probe.close()
    return True


def _port_holder(port: int) -> str | None:
    """``"pid 1234 python3 server/poc_app.py"`` for whoever holds ``port``.

    BEST EFFORT, and deliberately /proc-only: the kernel is the one thing that
    knows both the listening socket and the process that owns it, and the two
    alternatives both cost what this module does not otherwise pay - psutil is a
    dependency, and shelling out to ss/lsof is a subprocess that minimal images
    and containers do not carry. Every failure returns None, so the caller's
    message stays one line; naming the holder is the whole point, because "port
    8080 is busy" on its own leaves the operator guessing which of their own
    processes to go and kill.
    """
    inode = None
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(table, encoding="utf-8", errors="replace") as rows:
                next(rows, None)  # the column header
                for row in rows:
                    fields = row.split()
                    # field 3 is the socket state: 0A is TCP_LISTEN.
                    if len(fields) < 10 or fields[3] != "0A":
                        continue
                    local = fields[1]
                    if int(local.rsplit(":", 1)[1], 16) != int(port):
                        continue
                    inode = fields[9]
                    break
        except (OSError, ValueError, IndexError):
            continue
        if inode is not None:
            break
    if inode in (None, "0"):
        return None
    target = f"socket:[{inode}]"
    pid = None
    for fd in Path("/proc").glob("[0-9]*/fd/*"):
        try:
            if os.readlink(fd) == target:
                pid = int(fd.parts[2])
                break
        except OSError:
            continue
    if pid is None:
        return None
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as raw:
            cmdline = (
                raw.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
            )
    except OSError:
        cmdline = ""
    return f"pid {pid} {cmdline}".strip() if cmdline else f"pid {pid}"


def _pick_port(requested: int, is_free) -> int:
    """``requested`` when that port is free, else the next free one above it.

    A BUSY PORT IS NOT AN ERROR. It used to be reported as one: the bind was
    attempted at the very END of a boot, after the archive was loaded, every
    chart built and the animation scanned - so a port someone else held threw
    minutes of work away to print one line and exit 1. Moving up one port starts
    the same page, and the caller says in ONE line which port it left behind and
    which it took instead. ``is_free`` is injected so the scan is testable
    without binding anything.

    When nothing above is free the requested port comes back unchanged: the bind
    then fails and reports the OS error, which is the honest answer.
    """
    requested = int(requested)
    if is_free(requested):
        return requested
    candidate = requested + 1
    while candidate <= 65535:
        if is_free(candidate):
            return candidate
        candidate += 1
    return requested


def _port_for_serving(host: str, port: int) -> int:
    """The port this run will actually serve on, settled BEFORE any other work.

    Called FIRST in both serve loops - ahead of the registry read, the archive
    load, the chart builds and the frame scan - because the port is the one
    thing that can make all of that pointless. It prints ``[poc_app] pid N`` so a
    listing of listening sockets can be matched back to this run, and ONE line
    when the requested port is taken: the port, the /proc best-effort holder and
    the port this run moved to instead.
    """
    print(f"[poc_app] pid {os.getpid()}")
    requested = int(port)
    port = _pick_port(requested, lambda candidate: _port_is_free(host, candidate))
    if port != requested:
        holder = _port_holder(requested)
        print(
            f"[poc_app] port {requested} busy "
            f"({holder or 'holder unknown'}); using {port} instead"
        )
    return port


def run_web(
    info: dict,
    host: str,
    port: int,
    station: int,
    structure=None,
    structures=None,
) -> int:
    """Serve the viewer for ONE structure entry - LEGACY, [proposed-delete].

    Nothing calls this function: ``main()`` dispatches every web path to
    :func:`run_web_vis` (:13404, :13450), and this page is kept only because
    comments in this module still cite its line numbers.  See
    ``docs/kb/REGISTRY/decisions.md`` KB-4; delete it once those citations are
    rewired.

    ``structure`` is the registry entry the page names, ``structures`` the list
    the picker lists; both fall back to what the registry resolves on its own, so
    a caller that passes only the dump still gets a page.
    """
    # THE PORT IS SETTLED FIRST - see _port_for_serving. Everything below (the
    # registry, the archive load, the chart builds, the frame scan) is minutes of
    # work that a port already in use would otherwise throw away.
    port = _port_for_serving(host, port)
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
    # The temporal-aliasing report for the 3-D player, built once here from the
    # recording itself: None on a page with no volume (a 2-D page has nothing
    # decimated, so it has nothing to say), and a report whose text is None when
    # the recording cannot decide or the motion is not decimated.
    aliasing = _volume_aliasing(info)
    aliasing_text = aliasing.text if aliasing is not None else None
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
        _push_still(handles.get("view"), "toggle")

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

    def _emit_aliasing_banner() -> None:
        """The temporal-aliasing warning, or nothing at all.

        ``aliasing_text`` is None on a page with no 3-D volume, when the
        recording cannot decide the frame-to-frame phase advance, and when the
        motion is not decimated - so this block draws only when the sentence is
        true of the field on screen. The sentence itself is built by
        :func:`_volume_aliasing`; no number is typed here.
        """
        if not _volume_layer_enabled():
            # The sentence names the decimation of a volume this page is not
            # drawing, so on a layer-off page it would describe nothing.
            return
        if aliasing_text is None:
            return
        if html_div is None:
            if placeholder is not None:
                placeholder(aliasing_text)
                return
            print(
                "[poc_app] aliasing banner not shown: no html widgets",
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
            html_div(aliasing_text)

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
                _emit_aliasing_banner()
                if placeholder is not None:
                    with placeholder():
                        view = plotter_ui(plotter)
                else:
                    view = plotter_ui(plotter)
            elif html_div is None:
                # No html widgets: the plotter keeps the whole content area.
                with container(fluid=True, classes="pa-0 fill-height"):
                    _emit_mismatch_banner()
                    _emit_aliasing_banner()
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
                        _emit_aliasing_banner()
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
        _push_still(view, "station")

    print(f"[poc_app] serving on http://{host}:{port}")
    print("[poc_app] open that URL in a browser; Ctrl-C to stop")
    # NO PORT CHECK HERE: the port was settled at the TOP of this function, before
    # the archive was read and every chart built. Reaching this line with the
    # port taken means another process won a race in between, and the bind error
    # is then the truthful report - there is nothing to say here that the
    # pre-flight line did not already say, minus the work it saved.
    server.start(host=host, port=port, open_browser=False)
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
    written at their own, usually coarser cadence with frame_index_xcut 1..nt_x.
    Indexing t_ns with an x-cut frame number looks perfectly well formed and
    reads the wrong instant, which is why this function exists instead of a bare
    ``t_ns[frame]`` at every call site.
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
        # frame -> step -> seconds, in that order and through the surface's own
        # spec, so the stride that produced the frame stays visible and the time
        # is the one the step base says it is.
        step = int(_step_time.step_for_frame(_surface_spec(info, "ez_xcut"), frame))
        recorded = int(index[frame])
        if step != recorded:
            # An axis whose samples do not sit on ``offset + frame * stride`` (a
            # restart or a dropped capture leaves gaps no single spec can
            # describe): the recorded step is the only reading left, so it wins
            # over a reconstructed one.
            step = recorded
        time_base = _step_time.TimeBase(float(info["dt_s"]))
        return float(time_base.time_of(step) * 1e9)
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
            # 0.10, not 0.3: at 0.3 the box read as a PALE SLAB that dimmed the
            # ground plane and the field inside the dielectric, not as a casing.
            plotter.add_mesh(
                pv.Box(bounds=(0.0, x_span, 0.0, y_span, 0.0, substrate_h)),
                color="steelblue",
                opacity=VIS_SUBSTRATE_OPACITY,
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


#: The style of the LIVE LOG under the Solve card, and the one that keeps it off
#: screen until there is something to show. Both are BOUND to
#: ``state.solve_log_style`` (``style=("solve_log_style", _SOLVE_LOG_HIDDEN)``),
#: because the card is emitted once and a run starts later: a literal here could
#: not unhide the panel, and a page that has never run a solve would carry an
#: empty ``<pre>`` - a box of height that says nothing. The height cap is what
#: makes this a WINDOW on a log rather than the whole of it: SolveJob keeps 400
#: lines and ``log_lines`` hands over the last dozen, which is what fits.
_SOLVE_LOG_STYLE = (
    "font-size: 10px; white-space: pre-wrap; margin: 4px 0; "
    "max-height: 15em; overflow-y: auto;"
)
_SOLVE_LOG_HIDDEN = "display: none;"


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


def solve_argv(
    structure_id, xcut_near_mm, out_npz, netlist_json="", config=None
) -> list[str]:
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

    ``config`` is the Run Config form built into ONE ``RunConfig``
    (``run_config_from_form``). When it is given it is the AUTHORITY for
    ``--xcut-near-mm`` as well as for the flags only it can carry
    (``--nsteps``, ``--volume-stride``, ``--xcut-far-mm``, ``--wall-limit-s``
    and, when those boxes were filled, ``--pulse-freq-ghz`` and ``--load-ohm``):
    a press must run what the form says, and two
    sources for one flag is how a page ends up solving something it never
    displayed. ``xcut_near_mm`` stays the default for a caller with no form, and
    the no-config command line is unchanged, byte for byte.
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

    # The form, when there is one, is what the near cut MEANS: the caller's
    # positional is only the no-form default.
    near_mm = float(xcut_near_mm if config is None else config.xcut_near_mm)
    argv = [
        sys.executable,
        str(SOLVER_SCRIPT),
        "--structure",
        sid,
        "--xcut-near-mm",
        # %g, so 20.4 reads as 20.4: the float's repr can carry a long tail
        # (20.400000000000002) that looks like a different number than the one
        # the user asked for.
        f"{near_mm:g}",
        "--vis-dump",
        str(out),
    ] + _run_config_argv(config)
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


def _monotonic_axis(values):
    """One recorded step axis as an int array, or None when it cannot be read.

    None is this module's "no mapping can be defended": an absent axis, an empty
    one, or one that runs backwards (a hand-built dump).
    """
    if values is None:
        return None
    try:
        axis = np.asarray(values).ravel()
        if axis.size < 1:
            return None
        if axis.size > 1 and np.any(np.diff(axis.astype(float)) < 0.0):
            return None
        return axis.astype(int)
    except (TypeError, ValueError):
        return None


def _volume_decimation(info: dict) -> int:
    """How many solver steps ONE stored ``e_abs_volume`` frame spans, MEASURED.

    The MEDIAN difference between consecutive entries of the volume's own step
    axis (``e_abs_volume_step_index``) - what the stored frames actually do -
    and NEVER the recorded ``e_abs_volume_stride`` scalar: the shipped archive
    states 4 beside an axis that runs 1, 101, 201, ... (a KNOWN DEFECT in the
    writer), and only the axis describes the frames that are on disk - 24 of
    them, 100 steps apart, so the honest reading is 100. A median rather than a
    first difference or a mean so one dropped sample or one restart cannot
    restate the cadence of the whole film.

    1 when the decimation cannot be measured - no volume, no readable monotonic
    axis, fewer than two frames. 1 is also what makes the "Volume Decimated"
    clause DISAPPEAR rather than print "×1" over an undecimated layer.
    """
    if info.get("e_abs_volume") is None:
        return 1
    steps = _monotonic_axis(info.get("e_abs_volume_step_index"))
    if steps is None or steps.size < 2:
        return 1
    diffs = np.asarray(np.diff(steps), dtype=float)
    diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if diffs.size == 0:
        return 1
    return max(1, int(round(float(np.median(diffs)))))


_TIMELINE_CACHE: dict = {}
_TIMELINE_CACHE_LIMIT = 8

# Memo for _volume_player_plan. A page draws on EVERY tick, and the plan is a
# pure function of (info, mode): rebuilding it per tick would rebuild two 2400-entry
# searchsorted passes and a maximum.accumulate for a picture that cannot have
# changed. Capped and cleared whole rather than grown, because the entries hold the
# info dicts themselves (see below) and a long-lived viewer that opens dump after
# dump must not accumulate them.
_VOLUME_PLAN_CACHE: dict = {}
_VOLUME_PLAN_CACHE_LIMIT = 8


def _volume_player_plan(info: dict, mode: str):
    """The ONE mapping from a player position to the two indices it draws.

    THE CLOCK IS THE PLANE FAMILY'S. One player position is one recorded frame
    of the family on screen - ``frame_index`` (2400 at the reference recording)
    or ``frame_index_xcut`` (its own count, at the cadence it was recorded) -
    and therefore one solver step, which is what
    the timeline, the slider, the play loop and the label are all counted on.
    ``e_abs_volume`` is the COARSER recording: ``--volume-stride`` stores one
    volume frame every N-th y-cut frame (24 of them at the reference
    recording), so it is a DECIMATED LAYER, painted at the position's NEAREST
    capture and never the grid the player steps.

    WHY the old design was wrong: it counted the timeline in the volume's own
    frames. The finest series on the page then paid for the coarsest one - 24
    positions to reach 2400 recorded steps, so the cut planes were a slideshow
    and every plane frame between two captures was unreachable, the tail
    included - and the label had to grow a decimation clause to explain a gap
    the player itself had created. Stepping the plane frames needs no such
    clause: the plane is exact at every position, and the volume states which
    stored frame it is showing and at what step it was captured.

    Returns None when no mapping can be defended: no volume, or a step axis
    that cannot be read (absent, empty, non-monotonic) for either half. Else a
    dict of:

        ``steps``  - the recorded step of each player position, in order;
        ``frames`` - how many positions the timeline has (== len(steps));
        ``plane``  - position -> this family's stored frame (the identity: the
                     positions ARE that family's own frames);
        ``volume`` - position -> index into ``e_abs_volume``.

    NEAREST CAPTURE, ties to the EARLIER one: the volume is painted at whichever
    stored capture lies closest in solver step to the position, so it is never
    more than half a decimation stale and the two pictures cannot drift apart
    without bound. The two halves live in ONE record so every caller - the
    viewer, the colour range, the label - resolves them through the same
    indices and cannot disagree.

    MEMOISED, and the memo keeps the info DICT as well as the plan. The page draws
    this on every tick, so the work would otherwise be redone for a record that
    cannot have changed between ticks; but keying on ``id(info)`` alone would be
    unsound, because a freed dict's id can be handed to a new one - and a viewer
    that opens dump after dump frees exactly such dicts. Holding the object next to
    the plan means the id it was filed under cannot be recycled while the entry
    lives (the object stays alive), and the ``is`` check on lookup rejects an entry
    that somehow no longer belongs to the dict asked about rather than serving a
    plan for another dump's axes. The memo keeps at most
    ``_VOLUME_PLAN_CACHE_LIMIT`` entries and is cleared when full: the number of
    distinct (dump, mode) pairs on screen is 2, so the cap only ever bites on a
    long session that reloaded many dumps, and that is when the strong refs the
    entries hold should go.
    """
    key = (id(info), mode)
    hit = _VOLUME_PLAN_CACHE.get(key)
    if hit is not None and hit[0] is info:
        return hit[1]
    plan = _build_volume_player_plan(info, mode)
    if len(_VOLUME_PLAN_CACHE) >= _VOLUME_PLAN_CACHE_LIMIT:
        _VOLUME_PLAN_CACHE.clear()
    _VOLUME_PLAN_CACHE[key] = (info, plan)
    return plan


def _build_volume_player_plan(info: dict, mode: str):
    """Recompute the plan; see :func:`_volume_player_plan` for what it means.

    Split out only so the memo above is the ONE way in and cannot be bypassed by
    accident: nothing else in the module calls this, and every caller therefore
    sees the same plan object for the same record.
    """
    timeline = _timeline_for(info)
    if timeline is None:
        return None
    return timeline.plan(mode)

def _volume_layer_label(info, mode, position):
    """The |E| LAYER's half of the label, or None when there is no volume.

    The player's clock is the plane family's; this names the OTHER clock on the
    page - the stored volume frame drawn at ``position``, its own solver step,
    and how many steps one such frame spans - so neither can be read as the
    other. The text is "Frame 4 of 24, Volume Decimated ×100 @ step 301": the
    stored frame index, the decimation MEASURED by :func:`_volume_decimation`
    (appended only above 1, so an undecimated layer is never falsely labelled),
    and the step that frame was captured at - printed even when it equals the
    player's own step, because a layer that names its clock is exactly what
    stops the two being confused.

    ``mode`` is accepted and deliberately ignored: it names a VIEW, and no
    argument of this function may make a label describe a different clock (the
    same reason ``Timeline.plan`` ignores it). Nothing is recomputed here - the
    layer is read off the page's one timeline - so no caller passes a plan in and
    none can pass a different one.
    """
    timeline = _timeline_for(info)
    if timeline is None:
        return None
    return timeline.layer_label(_timeline.VOLUME_LAYER, timeline.clamp(position))



VOLUME_LAYER_NOTES_LOGGED: dict[str, None] = {}
VOLUME_LAYER_NOTES_LIMIT = 64


def _log_volume_layer_note(info, mode, position) -> None:
    """Log the |E| layer's own reading for this position, once. Never raises.

    The label states ONE clock (:meth:`TimeAxis.label`), so the layer's separate
    clock - which stored volume frame is painted, its own step, its decimation -
    is written to the log instead of folded into the sentence. Once per distinct
    sentence: this runs on every draw, and the same note on every tick would
    bury the rest of the log. Capped, so a long session that sweeps many frames
    cannot grow the dict without bound.
    """
    try:
        note = _volume_layer_label(info, mode, int(position))
        if not note or note in VOLUME_LAYER_NOTES_LOGGED:
            return
        if len(VOLUME_LAYER_NOTES_LOGGED) >= VOLUME_LAYER_NOTES_LIMIT:
            return
        VOLUME_LAYER_NOTES_LOGGED[note] = None
        print(f"[poc_app] volume layer: {note}", file=sys.stderr)
    except Exception:  # noqa: BLE001 - a log line never costs a draw
        pass


def _volume_abs_global_clim(volume):
    """The ONE colour range every frame of ``e_abs_volume`` is drawn on.

    ``(peak / 1000, peak)`` over the WHOLE stored volume: the same 60 dB span
    ``_volume_abs_grid`` takes over its own image, and taken over EVERY frame on
    purpose. A range per frame would renormalise each frame to its own peak and
    paint the recorded decay away, which is the one thing an animation must not
    do. The ceiling is the VOLUME's alone: each cut sheet is drawn on the range
    measured off its own samples (``_cut_sheet_clim``), so colours are not
    comparable between the volume and the cuts - ``VOLUME_CLIM_CAPTION`` is what
    says so on the page.

    None when there is nothing to measure - no volume, an empty one, the wrong
    rank, or a peak that is not finite and positive - and the caller then draws
    no volume layer at all rather than an unpainted one.
    """
    if volume is None:
        return None
    try:
        vol = np.asarray(volume)
        if vol.ndim != 4 or vol.size < 1:
            return None
        if np.iscomplexobj(vol):
            vol = np.abs(vol)
        peak = float(np.max(vol))
    except Exception:  # noqa: BLE001 - see the docstring's None
        return None
    if not np.isfinite(peak) or peak <= 0.0:
        return None
    return (peak * 1e-3, peak)


#: The two references the |E| volume's colour range can be measured against.
#:
#: ``"global"`` is the DEFAULT and the honest picture: ONE range measured over
#: the whole recording, so the decay from the loud frames to the weak ones is
#: painted AS decay - and a late frame that really has left the domain really
#: does come out empty. ``"per_frame"`` takes the same 60 dB span but references
#: it to the CURRENT frame's own peak, which reveals structure inside weak
#: frames at the honest cost of painting that decay away.
VOLUME_CLIM_GLOBAL = "global"
VOLUME_CLIM_PER_FRAME = "per_frame"
VOLUME_CLIM_MODES = (VOLUME_CLIM_GLOBAL, VOLUME_CLIM_PER_FRAME)

#: What the layer uses when nothing says otherwise. A page - and a caller - that
#: never mentions the mode therefore draws exactly the layer it always drew.
VOLUME_CLIM_DEFAULT = VOLUME_CLIM_GLOBAL

#: How the Color Scale control DISPLAYS each backend token. The tokens above are
#: what the layer reads, so a token is what the select's VALUE must be; these are
#: what a reader sees. Keyed BY token and walked in VOLUME_CLIM_MODES order at emit
#: time, so a mode added above with no label here raises KeyError at build time
#: instead of showing a raw token in the UI.
#:
#: WHY "Comparable" AND NOT "Absolute": the global window really does put every
#: frame of ONE volume on one measured range, so frames can be compared with each
#: other - that is the whole claim, and VOLUME_CLIM_CAPTION below is what bounds it
#: (it says nothing about the plane stack or the cut sheets). "Max Contrast" names
#: what per-frame mode buys instead of hiding it behind the neutral "Relative".
VOLUME_CLIM_TITLES = {
    VOLUME_CLIM_GLOBAL: "Global (Comparable)",
    VOLUME_CLIM_PER_FRAME: "Per-Frame (Max Contrast)",
}

#: The Run Config card's warning, character for character. It sits under the
#: select and is visible ONLY while the renormalising mode is selected: per-frame
#: scaling is legitimate, and what it costs the picture is the one thing a reader
#: choosing it has to be told. It names the mode by the TITLE the reader just
#: picked, so the warning and the control cannot describe two different windows.
VOLUME_CLIM_PER_FRAME_WARNING = (
    "Warning: Per-Frame (Max Contrast) re-references the color scale to each "
    "frame's own peak, so the amplitude decay between frames is not visible."
)


def _volume_clim_items_literal() -> str:
    """The Color Scale select's items, as the JS array literal ``v_bind_items`` wants.

    WHY A STRING AT ALL: a python LIST handed to ``v_bind_items`` is read by trame
    as ``(state_name, default)`` and emitted as a bare ``:items="A"`` - the JS
    identifier of its first element - which selects nothing (:11647 spells the trap
    out). A str there is passed through as a JS EXPRESSION instead, so the literal
    survives verbatim.

    WHY ``repr`` AND NOT ``json.dumps``: trame re-wraps this string in DOUBLE quotes
    before it reaches the attribute, so a ``"`` inside it would end the attribute
    mid-array - the second half of the same comment at :11652. ``repr`` emits single
    quotes, which Vue's expression parser accepts and which therefore survive the
    wrapping. A python list of dicts is a valid JS array of object literals, so no
    second serialiser is needed and none is introduced.
    """
    return repr(
        [
            {"title": VOLUME_CLIM_TITLES[token], "value": token}
            for token in VOLUME_CLIM_MODES
        ]
    )


#: What the Color Scale select BUYS and what it does not, character for character:
#: the caption under it in the Run Config card. The option called "Comparable"
#: claims exactly one thing - every frame of THIS volume is painted on one measured
#: range, so frames of this volume can be read against each other. It does not claim
#: comparability with the plane stack (one global p99.5 linear ceiling for every
#: frame, see ``_vis_colour_limit``) or with the cut sheets (each sheet carries the
#: range measured off the samples that sheet actually holds), and saying so HERE is
#: what keeps the option's title honest instead of merely confident.
VOLUME_CLIM_CAPTION = (
    "Global puts every frame of this volume on one measured range, so its frames "
    "can be compared with each other. The |Ez| plane sheets and each cut sheet "
    "keep ranges of their own, so colors are not comparable between them and the "
    "volume."
)


def _volume_bar_title(mode=VOLUME_CLIM_DEFAULT, *, log_scale: bool = True) -> str:
    """The |E| colour bar's title for ``mode``: the WINDOW is part of the reading.

    WHY the window goes in the title and not only in the control above it: the bar
    is what a reader's eye lands on while looking at a frame, and the same frame
    under the two modes is the same picture with a different claim about it. A bar
    that said only "|E| (Log)" would be correct in both modes and would tell nobody
    which of the two windows - the recording's, or this frame's own peak - the
    colours in front of them were referenced to.

    ``log_scale`` names the RAMP, which the title has always carried: the caller
    knows whether it drew the log volume or the older-pyvista LINEAR retry, and a
    linear ramp under a log title is the one lie a colour bar must not tell.

    An unknown ``mode`` normalises to the default (``_volume_clim_mode``), so a
    caller that passes junk gets the title of the window the layer really drew.
    """
    ramp = VOLUME_BAR_TITLE if log_scale else VOLUME_BAR_TITLE_LINEAR
    return f"{ramp} - {VOLUME_CLIM_TITLES[_volume_clim_mode(mode)]}"


def _volume_bar_titles() -> tuple:
    """Every title ``_volume_bar_title`` can produce: both ramps, both windows.

    WHY a set of them rather than the two module constants: pyvista keys a bar by
    its title, so a stale bar is only removable under the exact title it was placed
    with. The window is now IN that title, which means dropping the volume layer
    has to sweep every spelling it could have left behind - see
    ``_volume_layer_drop``.
    """
    return tuple(
        _volume_bar_title(mode, log_scale=log_scale)
        for log_scale in (True, False)
        for mode in VOLUME_CLIM_MODES
    )


def _volume_clim_warning(mode) -> str:
    """The Run Config warning for ``mode``: the text in per-frame mode, else ``""``.

    WHY it returns the TEXT and not a bool: the boot value, the change handler and
    the VAlert's condition all have to agree that the warning belongs to exactly
    one mode, and they agree by asking this one question. ``bool("")`` is False, so
    the same value drives both the alert's visibility and the sentence it shows.

    An unknown ``mode`` normalises to the default and therefore warns about
    nothing: the page is drawing the global window in that case, so a per-frame
    warning would describe a picture nobody is looking at.
    """
    if _volume_clim_mode(mode) == VOLUME_CLIM_PER_FRAME:
        return VOLUME_CLIM_PER_FRAME_WARNING
    return ""


# How many cells the box may put on the line. The grid is nx = n_pml(6) + n_ref(2)
# + n_line wide, so n_line decides how wide the board is.
# Floor 43: the board has to enclose the near cut and the load column, which at the
# box's DEFAULT cut/load position sit at column 51 (20.4 mm / 0.4 mm cell); moving the
# cut further out raises this floor.
# Ceiling 116: 124 columns is twice the reference board's 62, and nobody has a reason
# to ask this machine for more.
RUN_N_LINE_MIN = 43
RUN_N_LINE_MAX = 116
RUN_N_LINE_REFERENCE = 54
RUN_N_LINE_REFERENCE_CELLS = 289168
RUN_MESH_NX_OFFSET = 8      # n_pml 6 + n_ref 2: columns the line does not own
RUN_MESH_NY = 212           # 2*n_pml 6 + n_strip 8 + 2*n_clean 96
RUN_MESH_NZ = 22            # n_sub 4 + n_air 12 + n_top 6


def _run_n_line_board(n_line) -> str:
    """One sentence: the board this many cells on the line buys, and how it compares."""
    try:
        value = int(n_line)
    except (TypeError, ValueError):
        return (
            f"n_line: {n_line!r} is not a whole number of cells "
            f"({RUN_N_LINE_MIN}-{RUN_N_LINE_MAX})"
        )
    nx = RUN_MESH_NX_OFFSET + value
    cells = nx * RUN_MESH_NY * RUN_MESH_NZ
    ratio = cells / float(RUN_N_LINE_REFERENCE_CELLS)
    board = (
        f"board {nx} x {RUN_MESH_NY} x {RUN_MESH_NZ} = {cells:,} cells, "
        f"{ratio:.1f}x the {RUN_N_LINE_REFERENCE_CELLS:,}-cell reference mesh"
    )
    if value > RUN_N_LINE_MAX:
        return f"{board} - over the {RUN_N_LINE_MAX}-cell ceiling, the press will refuse"
    if value < RUN_N_LINE_MIN:
        return (
            f"{board} - under the {RUN_N_LINE_MIN}-cell floor, the grid would cut the "
            "near cut, the press will refuse"
        )
    if value == RUN_N_LINE_REFERENCE:
        return f"{board} (the shipped default)"
    return board


#: The Run Config form's ten controls, as ONE table: the state name the browser
#: writes, the label it reads, and the ``emfit.config.RunConfig`` field that names
#: the default. The emit loop, the boot values and the drift test all walk this,
#: so a field cannot be added to the form without a default behind it. The three
#: added rows are the dump budget - how often planes are kept, the mesh's line
#: cells, and the volume's frame cap - the knobs that decide how BIG a run's
#: output is: the cost of a press, not just its physics. Their ORDER is the
#: browser's: the budget rows sit together after the volume stride, the mesh row
#: sits with the geometry it moves, and the last two close the form.
#:
#: Those last two are the solver's RUNTIME guards rather than anything the plan
#: prices: ``--wall-limit-s`` is the trip thread's ceiling (run_build_A.py:3380,
#: tripped at :427-430, exit 4) and ``--load-ohm`` is the ``series_r`` termination
#: (:3344, used at :2093). The ceiling opens on the reference's own 1400 s
#: (:128), so a blank box states the number a bare command line would have used.
#: The load opens BLANK on purpose: the reference resolves it per ARM - A 50 ohm
#: (:692, from the LOAD_VALUE_OHM constant at :137), B 100 ohm (:703), the absent
#: flag resolved at :3593-3594 - and a box opened on A's 50 would silently
#: re-terminate an arm B press, the trap the WARNING at :3585-3588 names.
RUN_CONFIG_FIELDS = (
    ("run_nsteps", "Steps", "nsteps"),
    ("run_volume_stride", "Volume stride", "volume_stride"),
    ("run_dump_stride", "Dump stride", "dump_stride"),
    ("run_volume_frames", "Volume frames (blank = all)", "volume_frames"),
    ("run_pulse_freq_ghz", "Pulse freq [GHz]", "pulse_freq_ghz"),
    ("run_xcut_near_mm", "Cut near x [mm]", "xcut_near_mm"),
    ("run_xcut_far_mm", "Cut far x [mm]", "xcut_far_mm"),
    ("run_n_line", "Line cells (n_line)", "n_line"),
    ("run_wall_limit_s", "Wall ceiling [s]", "wall_limit_s"),
    ("run_load_ohm", "Load [ohm] (blank = arm's own)", "load_ohm"),
)


def _run_config_defaults() -> dict:
    """``{state name: default}`` for RUN_CONFIG_FIELDS, read off ``RunConfig``.

    WHY the function-local import: this module's import time is stdlib + numpy -
    ``load_vis`` reaches ``emfit.operators`` the same way (:295) and the surface
    reader ``emfit.ntff`` (:750) - so a machine with no ``emfit`` on ``sys.path``
    still imports and serves the viewer. WHY ``RunConfig`` and not ten literals:
    these ARE the reference run's knobs, and a second copy of 2400/100/20.4/22.0 -
    or of the wall ceiling's 1400 s and the load's per-arm 50/100 ohm - written
    into the UI drifts the day the reference changes. Nothing is invented on any
    path: a build where ``emfit`` cannot be imported gets an EMPTY mapping, so the
    ten fields render blank rather than with numbers this file made up.
    """
    try:
        from emfit.config import RunConfig
    except Exception as exc:  # noqa: BLE001 - a missing emfit is not a dead page
        print(
            f"[poc_app] run config defaults unavailable: {exc}", file=sys.stderr
        )
        return {}
    reference = RunConfig()
    return {
        state_name: getattr(reference, field)
        for state_name, _label, field in RUN_CONFIG_FIELDS
    }


def _run_config_form_shown(available) -> bool:
    """Is the Run Config FORM (the ten run fields) offered on this page?

    The form describes a run that has not happened yet, so it belongs exactly
    where there is nothing to look at - a page already showing a field has a run
    behind it, and those ten boxes would silently describe a job nobody is
    going to start. The four flags below are that question, asked once: a
    volume field, a plane stack, a captured port plane and a frame axis are all
    statements about the DATA (um3k_context.py:99, :123-137), so any of them
    means "a run behind this page".

    ONE predicate, because TWO questions are answered from it - whether the
    widgets are emitted at build time and whether a press may proceed - and two
    copies of the same four `getattr`s are how a page ends up offering a form
    it will not honour.
    """
    return not bool(
        getattr(available, "plane_stack", False)
        or getattr(available, "volume_field", False)
        or getattr(available, "port_planes", False)
        or getattr(available, "animation", False)
    )


def _solve_refused_page(nt, available) -> bool:
    """Does a Solve press on this page have to be REFUSED before it spawns?

    Refused only when the page has NEITHER a timeline NOR a Run Config form: no
    frame axis (``nt`` is None - a static field snapshot, um3k_panels.py:127-140)
    means a new run has nowhere to land, and no form means there is not even a
    config to run one with. A data-less page has the form, so pressing Solve
    there is the whole point of the page; an animation dump has the timeline.

    Takes ``nt`` rather than reading it, so the caller passes the axis it has
    actually swapped in (``_poll_solve`` re-reads it from the new dump) instead
    of this asking the page a second, possibly stale, time.
    """
    if nt is not None:
        return False
    return not _run_config_form_shown(available)


#: Which RunConfig fields are whole numbers, so the form's text is parsed as
#: one. The remaining five in RUN_CONFIG_FIELDS (``pulse_freq_ghz``,
#: ``xcut_near_mm``, ``xcut_far_mm``, ``wall_limit_s``, ``load_ohm``) are floats -
#: the last two are plain ``type=float`` on the reference's own parser
#: (``run_build_A.py:3380``, ``:3344``), so a whole-number box would refuse a
#: value the command line takes. The KIND is checked here
#: because ``RunConfig.validate`` refuses a float where an int belongs ("a JSON
#: 2400.0 is not 2400"), and a VTextField only ever hands over a STRING.
_RUN_CONFIG_INT_FIELDS = (
    "nsteps",
    "dump_stride",
    "volume_stride",
    "volume_frames",
    "n_line",
)


def _run_config_field_value(label, field_name, raw):
    """One RunConfig field off one form string, or ``None`` for "no opinion".

    A blank box (``""``, whitespace, an absent state field) is NOT zero and NOT a
    crash: it means the browser left that box alone, so the field is omitted and
    ``RunConfig``'s own default stands. Everything else is parsed by KIND here,
    and a string that is not a number raises a ``ValueError`` naming the box it
    was typed into - the press refuses with that sentence instead of running
    something the box did not say.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if field_name in _RUN_CONFIG_INT_FIELDS:
        try:
            return int(text)
        except ValueError:
            pass
        try:
            float(text)
        except ValueError:
            raise ValueError(
                f"{label} ({field_name}) is not a number: {raw!r}"
            ) from None
        raise ValueError(
            f"{label} ({field_name}) must be a whole number, not {raw!r}"
        )
    try:
        return float(text)
    except ValueError:
        raise ValueError(f"{label} ({field_name}) is not a number: {raw!r}") from None


def run_config_from_form(values) -> "RunConfig":
    """The ONE ``RunConfig`` a press runs, built from the Run Config form.

    ``values`` maps the state name the browser writes to the text it left there
    (``{state_name: state.<state_name>}`` for RUN_CONFIG_FIELDS). WHY a config at
    all: ``RunConfig`` is where these ten knobs are validated (whole steps, a
    positive finite pulse, the far cut beyond the near cut, a finite wall ceiling
    and load), so building it HERE means a bad box refuses the press rather than
    spawning a solver that would fail on its own argv or, worse, quietly run the
    numbers it prefers.

    Blank fields fall to ``RunConfig``'s defaults (see
    ``_run_config_field_value``), so a page nobody typed into solves exactly what
    it solved before this form existed.
    """
    from emfit.config import RunConfig

    kwargs = {}
    for state_name, label, field_name in RUN_CONFIG_FIELDS:
        value = _run_config_field_value(label, field_name, values.get(state_name))
        if value is not None:
            kwargs[field_name] = value
    try:
        config = RunConfig(**kwargs)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"run config refused: {exc}") from None
    # n_line is a MESH, and both ends of its board are physics, not taste (see
    # RUN_N_LINE_MIN / RUN_N_LINE_MAX). RunConfig only checks that it IS a whole
    # number of cells, so the range is enforced HERE, on the value it returned -
    # one place, AFTER the defaults are filled in, so a blank box (54) and a
    # typed 54 are the same press. The refusal names the board, and the solve
    # trigger already turns a ValueError into the page's own refusal sentence.
    if not RUN_N_LINE_MIN <= int(config.n_line) <= RUN_N_LINE_MAX:
        raise ValueError(
            f"run config refused: {_run_n_line_board(config.n_line)}"
        )
    return config


def _run_config_argv(config) -> list[str]:
    """The solver flags ``config`` adds, in the solver's OWN spelling.

    EMPTY for ``None``: a caller with no form gets the command line it has always
    got, byte for byte. ``--pulse-freq-ghz`` is omitted when the config carries
    ``None`` - ``None`` is the reference's own pulse, not a number to pass.

    The list carries the WHOLE form, so a press runs what the page shows: every
    box in ``RUN_CONFIG_FIELDS`` reaches the solver here. Two of them are budgets
    rather than physics: ``--dump-stride`` is a FLOOR - ``_vis_plan_stride`` may
    raise it to fit the plane budget - and ``--volume-frames`` is omitted when
    the config carries ``None``, which means no cap at all. The last two are the
    solver's RUNTIME guards: ``--wall-limit-s`` is the trip thread's ceiling
    (run_build_A.py:3380) and ``--load-ohm`` the ``series_r`` termination (:3344).
    """
    if config is None:
        return []
    flags = [
        "--nsteps",
        str(int(config.nsteps)),
        "--volume-stride",
        str(int(config.volume_stride)),
        "--xcut-far-mm",
        f"{float(config.xcut_far_mm):g}",
    ]
    if config.pulse_freq_ghz is not None:
        flags += ["--pulse-freq-ghz", f"{float(config.pulse_freq_ghz):g}"]
    # The dump budget travels with the same press: --dump-stride is a FLOOR
    # (_vis_plan_stride may raise it to fit the plane budget) and --n-line is the
    # mesh the planes are cut from.
    flags += [
        "--dump-stride",
        str(int(config.dump_stride)),
        "--n-line",
        str(int(config.n_line)),
    ]
    if config.volume_frames is not None:
        # None is "no cap", not a number to pass - the same rule
        # --pulse-freq-ghz follows above.
        flags += ["--volume-frames", str(int(config.volume_frames))]
    # The runtime guards. The ceiling is ALWAYS sent: RunConfig's default IS the
    # reference's own 1400 s (run_build_A.py:128), so an untouched box states the
    # number a bare command line would have used - the --dump-stride rule, not a
    # number this file invented. The load is sent only when a box names one:
    # ``None`` is the ARM's own termination, which the reference resolves per ARM
    # (A 50 ohm at :692, B 100 ohm at :703, both read from the absent flag at
    # :3593-3594; A's number is the LOAD_VALUE_OHM constant at :137). Sending 50
    # for an arm B press is the silent re-termination the WARNING at :3585-3588
    # names; :3589-3592 is only the comment explaining why the flag wins.
    if config.wall_limit_s is not None:
        flags += ["--wall-limit-s", f"{float(config.wall_limit_s):g}"]
    if config.load_ohm is not None:
        flags += ["--load-ohm", f"{float(config.load_ohm):g}"]
    return flags


def _volume_clim_mode(value):
    """The clim mode ``value`` asks for, or the DEFAULT when it does not ask.

    The ONE normaliser every reader goes through. An absent state field, a
    ``None``, and a string this build does not know all answer ``"global"``, so
    the mode can never silently become the renormalising one by being misspelled
    or by a control that has not been built yet.
    """
    if isinstance(value, str) and value in VOLUME_CLIM_MODES:
        return value
    return VOLUME_CLIM_DEFAULT


def _volume_abs_frame_clim(volume, frame):
    """The colour range ONE stored frame of ``e_abs_volume`` is drawn on.

    ``(peak / 1000, peak)`` over THAT frame alone: the same 60 dB span
    ``_volume_abs_global_clim`` takes over the whole clip, referenced to the
    frame's own peak instead of the recording's.

    None when the frame cannot name a reference: no volume, the wrong rank, a
    frame index off either end, or a peak that is not finite and positive. WHY
    that answer and not a tuple: ``(0.0, 0.0)`` is degenerate (every voxel sits
    at the bottom of it, and a range whose ends are equal is a range VTK must
    guess about) and any widening of it would be a number this function
    invented. ``_volume_clim_for`` turns the None into the whole-recording
    range, which is measured, finite and never inverted.
    """
    if volume is None:
        return None
    try:
        vol = np.asarray(volume)
        if vol.ndim != 4 or vol.size < 1:
            return None
        if np.iscomplexobj(vol):
            vol = np.abs(vol)
        position = int(frame)
        if position < 0 or position >= vol.shape[0]:
            return None
        peak = float(np.max(vol[position]))
    except Exception:  # noqa: BLE001 - see the docstring's None
        return None
    if not np.isfinite(peak) or peak <= 0.0:
        return None
    return (peak * 1e-3, peak)


def _volume_clim_for(volume, frame, mode):
    """The |E| volume layer's colour range under clim ``mode``.

    ``VOLUME_CLIM_PER_FRAME`` -> ``_volume_abs_frame_clim``, with the
    whole-recording range as the FALLBACK for a frame that cannot name one of
    its own (peak 0, NaN or inf - see that function). Every other value,
    ``VOLUME_CLIM_DEFAULT`` and an absent one included ->
    ``_volume_abs_global_clim``, untouched: that is what makes a caller which
    says nothing byte-identical to the layer that predates the mode.

    WHY the fallback is the GLOBAL range and not a degenerate one and not
    "draw nothing": the frame IS part of the recording, so the global range is
    the one range that is honest about it without inventing a number. A dead
    frame then shows as empty (it is below that floor, which is true) while the
    layer, its cut sheets and its markers stay drawn and in agreement. None - no
    volume at all - is passed straight through and the caller drops the layer.
    """
    if _volume_clim_mode(mode) == VOLUME_CLIM_PER_FRAME:
        clim = _volume_abs_frame_clim(volume, frame)
        if clim is not None:
            return clim
    return _volume_abs_global_clim(volume)


def _volume_frame_grid(info: dict, frame, cell_mm: float, clim):
    """ONE stored |E| frame as an ``ImageData`` on this page's own node grid.

    WHY this exists beside ``_volume_abs_grid``: that reader COLOCATED the
    archive's staggered vector onto cell centres, so its image starts half a
    cell in. ``e_abs_volume`` needs none of that - it is already a magnitude on
    the NODE grid, "the same node grid as ez_ycut" in the writer's own words
    (evidence/termination/run_build_A.py) - so the frame is placed at
    ``origin = (0, 0, 0)`` with ``spacing = cell``, which puts its first sample
    at x = 0 exactly where ``_vis_grid`` puts the animated sheet's first sample.
    The difference between the two anchors is one half cell: on the shipped dump
    (cell 0.4 mm) a volume frame drawn at the colocated anchor would stand
    0.2 mm off every sheet beside it.

    WHY it writes :data:`VOLUME_ABS_KEY`: the cut sheets (``_volume_cut_sheets``),
    ``_cut_layout`` and ``_add_markers`` all resolve their lattice through that
    memo, and a vis dump carries no ``e`` / ``volume`` for any of them to fall
    back on - without this the cuts have no grid and the markers have no
    extents. The entry is REWRITTEN on each frame change, which is the one place
    in this module that does so and the reason is that on this page the memo IS
    the current frame; it is spelled out here because ``_volume_abs_grid``
    promises the opposite ("set once, never rewritten") for the page that
    function was written for, and these two readers are the only ones that ever
    look at it.

    ``clim`` is handed in by the caller, which resolves it once per dump instead
    of once per frame. Returns the image, or None when there is nothing to place
    (no volume, no range, a frame out of range, a non-finite cell size).
    """
    try:
        volume = info.get("e_abs_volume")
        if volume is None or clim is None:
            return None
        vol = np.asarray(volume)
        if vol.ndim != 4 or vol.shape[0] < 1:
            return None
        which = max(0, min(int(vol.shape[0]) - 1, int(frame)))
        e_abs = np.asarray(vol[which], dtype=float)
        if e_abs.ndim != 3 or e_abs.size < 1:
            return None
        cell = float(cell_mm)
        if not np.isfinite(cell) or cell <= 0.0:
            return None
        nx, ny, nz = (int(v) for v in e_abs.shape)
        import pyvista as pv  # deferred, as everywhere else in this module

        image = pv.ImageData()
        image.dimensions = (nx, ny, nz)
        image.spacing = (cell, cell, cell)
        # NODE anchor, not the half-cell one: see the docstring above.
        image.origin = (0.0, 0.0, 0.0)
        # ``order="F"``: the sample's inner axis is its LAST one and ImageData
        # fills its points with x varying fastest, as in build_grid.
        image.point_data["e_abs"] = np.ascontiguousarray(
            e_abs.ravel(order="F"), dtype=float
        )
        info[VOLUME_ABS_KEY] = {
            "image": image,
            "clim": clim,
            "n": int(e_abs.size),
        }
        return image
    except Exception as exc:  # noqa: BLE001 - a picture is never worth a traceback
        print(
            f"[poc_app] |E| volume frame {frame} not built: {exc}",
            file=sys.stderr,
        )
        return None


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
    #: How much of that tail the CARD shows, line by line. The operator reads
    #: the last screen of a running solve, not the transcript: a dozen lines is
    #: the window, and a line longer than the card is trimmed exactly as
    #: ``last_line``'s is.
    LOG_LINES_SHOWN = 12
    LOG_LINE_CHARS = 160

    def __init__(self, argv, cwd=None):
        self.argv = list(argv)
        self.cwd = str(SOLVER_SCRIPT.parent if cwd is None else cwd)
        self.status = "idle"
        self.returncode = None
        self._tail: deque = deque(maxlen=self.LOG_TAIL_LINES)
        self._proc = None
        self._lock = threading.Lock()
        # THE reader thread (:_read_loop) and the two clock stamps. ``None``
        # until start(): a job that was never spawned has no duration and no
        # reader, and ``elapsed_seconds`` says so rather than printing 0 s.
        self._reader = None
        self.started_at = None
        self.ended_at = None

    @property
    def log(self) -> str:
        """The TAIL of the combined stdout+stderr, newest last."""
        return "".join(self._tail)[-self.LOG_TAIL_CHARS:]

    @property
    def elapsed_seconds(self):
        """Wall-clock seconds since start(), or since the end once it ended.

        ``None`` until start(): a job that was never spawned has no duration,
        and a made-up 0.0 would read as "finished instantly".
        """
        if self.started_at is None:
            return None
        end = self.ended_at if self.ended_at is not None else time.monotonic()
        return end - self.started_at

    @property
    def last_line(self) -> str:
        """The last non-blank output line, trimmed - what the child is doing."""
        for line in reversed(list(self._tail)):
            text = line.strip()
            if text:
                return text[-160:]
        return ""

    @property
    def log_lines(self) -> list:
        """The tail as LINES, oldest first - what the card's log panel shows.

        ``log`` is ONE string: enough for a failure sentence, but it has no
        idea where the lines break, so a card can only print it as a blob.
        A panel wants whole lines, the LAST few of them (that is where a
        running child says what it is doing) and nothing older than the box
        can show - hence the two bounds, ``LOG_LINES_SHOWN`` lines of at most
        ``LOG_LINE_CHARS`` characters each. Blank lines are dropped for
        ``last_line``'s reason: the panel is screen space, and a blank line
        spends it saying nothing.
        """
        lines = []
        for line in list(self._tail)[-self.LOG_LINES_SHOWN:]:
            text = line.strip()
            if text:
                lines.append(text[-self.LOG_LINE_CHARS:])
        return lines

    def _read_loop(self) -> None:
        """THE reader: drain the child's pipe for as long as the child lives.

        This is what makes the pipe safe. The child's stdout and stderr are
        the SAME pipe, and an unread pipe fills at ~64 KiB: the child then
        blocks on write and never exits, so the watcher waits forever on a
        solve that is only waiting for us. Reading here also turns the tail
        into a live log instead of a thing that exists and is never shown.
        """
        stream = getattr(self._proc, "stdout", None)
        if stream is None:
            return
        try:
            for line in stream:
                with self._lock:
                    self._tail.append(line)
        except (ValueError, OSError) as exc:  # noqa: BLE001 - a closed pipe
            print(  # a dead handle ends the reading, never the solve
                f"[poc_app] solve output not read to the end: {exc}",
                file=sys.stderr,
            )

    def _finish(self, returncode) -> None:
        self.returncode = returncode
        self.ended_at = time.monotonic()
        # The child's pipe is closed now, so the reader reaches EOF and returns
        # in microseconds; the timeout only bounds a handle that never closes.
        # It runs once per solve, which is why a join is affordable here.
        self._drain()
        self.status = "ok" if returncode == 0 else "failed"

    def _drain(self) -> None:
        """Read whatever is left. Safe only once the child has exited.

        With a reader thread the pipe is ALREADY being read (_read_loop), so
        there is nothing left to take here: joining the reader IS "read
        whatever is left", because once the child has exited the reader hits
        EOF and returns. The loop below stays as the fallback for a job that
        has no reader.
        """
        if self._reader is not None:
            # A reader thread owns the pipe from start() on; reading it here
            # too would steal lines from it. Joining is the whole of "read
            # whatever is left": once the child has exited the reader hits EOF
            # and returns, and the timeout only bounds a handle that never
            # closes.
            self._reader.join(timeout=2.0)
            return
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
            self.started_at = time.monotonic()
            self.ended_at = None
            self.status = "running"
            # INSIDE the lock on purpose: the reader cannot take a line
            # before the lock is released, so no start-up output is lost.
            self._reader = threading.Thread(
                target=self._read_loop,
                daemon=True,
                name="poc-solve-reader",
            )
            self._reader.start()
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
                "this tab needs a Huygens surface dump: pass --surface-dump "
                "PATH to plot a far-field pattern, and no shipped evidence "
                "file carries a surface record, so it stays empty on all of them"
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
    msaa=None, image_encoding=None, image_quality=None,
    stride=DEFAULT_PLAY_STRIDE, paint_fps=None,
    local_view=False,
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

    ``stride`` and ``paint_fps`` are the pump's two knobs and are KEYWORD-ONLY for
    the same reason: they describe how the picture is DELIVERED, not what is
    animated. ``stride`` is positions per PAINTED frame at the default speed, rate 4, and
    ``paint_fps`` is the ceiling on painted frames per second (None means "the same
    as ``fps``", i.e. one repaint per animation tick). Both are resolved HERE, once,
    so the banner, the caption, the loop body and the player clamp all quote the same
    numbers instead of each re-deriving them.
    """
    # THE PORT IS SETTLED FIRST - see _port_for_serving. Everything below (the
    # registry, the archive load, the chart builds, the frame scan) is minutes of
    # work that a port already in use would otherwise throw away.
    port = _port_for_serving(host, port)
    # The pump's two knobs, floored and de-junked ONCE. A bool is not a number here
    # (True would silently mean one position per painted frame), a None stride is a
    # page built before the flag existed, and a paint cap of 0 would divide by zero
    # in the loop's modulus - each falls back on the module defaults rather than
    # asking the operator to re-read a traceback.
    try:
        stride = int(stride)
    except (TypeError, ValueError):
        stride = DEFAULT_PLAY_STRIDE
    stride = max(1, stride)
    if paint_fps is None:
        paint_fps = int(fps)
    else:
        try:
            paint_fps = int(paint_fps)
        except (TypeError, ValueError):
            paint_fps = int(fps)
    paint_fps = max(1, paint_fps)
    # Painting faster than the loop ticks buys nothing (there is no new position to
    # paint), so the banner quotes the cap the loop can actually honour.
    paint_cap = min(paint_fps, max(1, int(fps)))
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

    try:
        import trame_vtk_hardening

        trame_vtk_hardening.install()
    except Exception as exc:  # noqa: BLE001 - a missing sibling must not stop the app
        print(f"[poc_app] trame_vtk hardening: not applied ({exc})", file=sys.stderr)

    from trame.app import get_server

    # THE LIVE PAGE, in ONE mutable dict. Every draw path reads `page["info"]`
    # rather than the `info` this function was called with, because a finished
    # solve REPLACES the page (apply_page) while the server keeps running. A
    # closure that captured `info` directly would keep drawing the dump that is
    # no longer on disk under the name the operator just re-solved for.
    # A BOOT WITH NO DATA TO DRAW still has a board. A page handed neither a
    # dump nor a page dict carries no cell and no counts, so every placement in
    # _vis_geometry would name itself absent and the centre column would open
    # empty. The builder that defines the default cross-section
    # (emfit.studies.microstrip_reference_board, via _builder_page) describes the
    # board exactly, so the page with nothing to show gets THAT board - not a
    # read of somebody else's study record, which a structure may not have at all.
    if loaded_page is None and not _page_has_board(info):
        loaded_page = _builder_page(
            structure.get("id") if isinstance(structure, dict) else None
        )
        info = loaded_page["info"]

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
    # ONE clock for the slider, the player and the picture: the timeline's, so a
    # position on the slider is one recorded plane frame and one solver step.
    # ``nt``/``nt_x`` above are the counts of the FILED arrays - what the dump
    # holds, quoted by the panels that describe the file - and the slider's own
    # maximum is ``_frame_max_for``, never these.
    # The bare board and builder page ALWAYS carry a cell, so what can lack
    # one is an arbitrary caller-supplied `info` dict: this read is tolerated
    # rather than fenced, NaN being the absence every isfinite() guard knows.
    try:
        cell_mm = _cell_mm(info)
    except (KeyError, TypeError, ValueError):
        cell_mm = float("nan")
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
    try:
        y_span_mm = float(int(info["ny"])) * cell_mm
    except (KeyError, TypeError, ValueError):
        y_span_mm = float("nan")

    plotter = pv.Plotter(off_screen=True)
    # --msaa asks the WINDOW for samples, and only when asked: a default run keeps
    # pyvista's own default (theme.multi_samples). The boot report quotes both
    # numbers, because a driver may answer with fewer than it was asked for.
    if msaa is not None:
        _apply_msaa(plotter, msaa)
    plotter.set_background("white")
    try:
        plotter.add_axes(xlabel="x", ylabel="y", zlabel="z")
    except Exception as exc:  # noqa: BLE001 - decoration only
        print(f"[poc_app] axes not drawn: {exc}", file=sys.stderr)

    # The PLANE bar: its title and its place, defined once in ``plane_bar_args``
    # so the y-cut sheet created here, the sheets rebuilt after a solve, and the
    # per-family swap in ``_show`` cannot disagree about either. The bar's title
    # is also the KEY pyvista stores it under, so the swap re-uses the same
    # string instead of adding a second bar.
    plane_args = plane_bar_args()
    scalar_bar_title = plane_args["title"]

    # The Grid box in the view panel writes this flag, and ``_cell_edges_on``
    # below is the ONE reader of it - so the sheets built at boot, the sheets
    # rebuilt after a solve and the y-cut overlay in ``_show`` cannot disagree
    # about whether the cell grid is drawn. A plain dict and not the state
    # attribute itself because the boot sheets are built BEFORE ``server.state``
    # exists (see below): a reader that reached into state would NameError on the
    # very first frame.
    edges_state = {"on": VIS_SHOW_EDGES}

    def _cell_edges_on() -> bool:
        """Whether the field sheets carry their cell grid RIGHT NOW.

        ``VIS_SHOW_EDGES`` is the module default and the box's initial value;
        ``edges_state`` is what the box has written since. AND, not OR: a page
        built with the grid off must not draw it because a box defaulted to
        True asked for it.
        """
        return bool(VIS_SHOW_EDGES) and bool(edges_state["on"])

    # The Substrate box, the same way round: the widget writes this flag and
    # ``_substrate_drawn`` is the ONE reader, so the slab drawn at boot, the one
    # re-stamped by ``_show`` on every family swap and the one the slider moves
    # cannot disagree. A dict, not state, for ``edges_state``'s reason: the
    # geometry is added before ``server.state`` is bound in this function.
    substrate_state = {"opacity": VIS_SUBSTRATE_OPACITY}

    def _substrate_drawn(mode=None) -> float:
        """The slab's opacity RIGHT NOW, for the view it is being drawn in.

        ONE reader for the geometry, the slider and ``_show``'s re-stamp. The
        y-cut is the one view that dims it further (the slab is edge-on there
        and would otherwise cover the field it annotates), and it dims it as a
        FRACTION of the slider - see ``VIS_SUBSTRATE_YCUT_SCALE``. Never raises:
        a slab at the wrong opacity is worth less than the page.
        """
        try:
            value = float(substrate_state["opacity"])
            if mode == "ycut":
                return value * VIS_SUBSTRATE_YCUT_SCALE
            return value
        except Exception:  # noqa: BLE001 - a slab is never the picture
            return VIS_SUBSTRATE_OPACITY

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
                # Page A never lit its sheets: this is a FLAT field of values, so
                # a surface normal must not shade it - light would dim the very
                # colour the reader is being asked to compare against the bar.
                lighting=False,
                show_edges=_cell_edges_on(),
                # Light and thin: the cell grid is here so the reader can see
                # WHERE the field is sampled, not to be read as a lattice.
                edge_color=VIS_EDGE_COLOR,
                line_width=VIS_EDGE_WIDTH,
                show_scalar_bar=(family == "ycut"),
                # A FRESH mapping per call: ``add_mesh`` fills in defaults on the
                # dict it is handed, so one shared dict is one sheet's arguments
                # leaking into the next.
                scalar_bar_args=plane_bar_args(),
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
    # The view holds sheets of two families and draws ONE of them; this flag
    # is the only switch that may say otherwise (read in _visible_families,
    # below, and nowhere else).
    state.show_other_family = False
    state.playing = False
    state.frame = 0
    # No timeline: the scrubber's range is ABSENT (None), never 0 frames.
    state.frame_max = _frame_max_for(info)
    state.play_label = "play"
    # The PLAY SPEED: how many positions ONE PAINTED FRAME advances, and the sentence
    # beside the select that states what that rate costs per sweep. Both are viewing
    # choices like DEFAULT_FPS, so both live in the state and both are recomputed
    # by _on_play_rate when the select moves - the caption is never a constant. The
    # caption quotes the EFFECTIVE stride (base stride x rate) and the PAINT cap, so
    # the sentence describes the sequence on screen rather than the loop's tick grid:
    # at the defaults (stride 4, paint cap = fps) it is the historical sentence.
    state.play_rate = DEFAULT_PLAY_RATE
    state.play_caption = _play_caption(
        nt, _play_stride(stride, DEFAULT_PLAY_RATE), paint_fps
    )

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

    # WHICH reference the |E| volume's colour range is measured against - the ONE
    # state name a left-panel control will write, so the layer reads it here and
    # nowhere else. "global" at boot is the picture this layer has always drawn:
    # one range over the whole recording, so the recorded decay is painted as
    # decay. "per_frame" re-references the same 60 dB window to each frame's own
    # peak, which shows structure inside weak frames and, honestly, hides that
    # decay - the warning the panel will carry, not this line.
    state.volume_clim_mode = VOLUME_CLIM_DEFAULT
    # The warning flag lives BESIDE the mode it warns about, and is INITIALISED
    # here rather than left to the first change: the card reads it on the very
    # first paint, so a flag that only appears once somebody touches the select
    # would make the warning either absent at boot or bound to nothing. Derived
    # from the mode by the same helper the change handler and the alert use, so the
    # three cannot disagree about which mode carries a warning.
    state.clim_relative_warning = bool(_volume_clim_warning(state.volume_clim_mode))

    # THE Run Config form's ten numbers, at the reference run's own defaults (see
    # ``_run_config_defaults``): the form is a STARTING POINT for a later run, so a
    # field that started at a number this file invented would make every run that
    # did not retype it a run nobody specified. Initialised beside the mode for the
    # same reason - the first paint reads them.
    _run_defaults = _run_config_defaults()
    for _run_state_name, _run_default in _run_defaults.items():
        setattr(state, _run_state_name, _run_default)
    # The board BESIDE the box, at the same default the box boots with: read on
    # the very first paint, so the range is explained before the first press -
    # a note that only appeared once somebody typed would explain nothing.
    state.run_n_line_note = _run_n_line_board(_run_defaults.get("run_n_line"))

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
        # NO ``layer_shown`` on purpose, so the context runs its own AUTOMATIC
        # policy (um3k_context.py:143-152) and answers the two-halves question
        # from the page's shape: the volume AND at most one station. Handing it
        # ``_volume_layer_enabled()`` would feed the module's boot answer into the
        # very computation that is supposed to produce that answer, and the
        # context's answer would then be stuck at whatever the switch said first.
    )
    # Publish the context's answer for the module-level draw path. ``_draw_volume_scene``
    # (:9838) and ``_draw_volume_layer`` (:16671) are module functions and cannot
    # see this context, so this cell (:1125) is the only way they learn what
    # THIS page decided - the draw path asks ``_volume_layer_enabled``, which reads it.
    # ORDER MATTERS: it is set here, before anything reads that reader - and it is,
    # because the first draw is the boot sheet build far below (:9461) and the frame
    # handler after it, not the two cut-slider steps that run in between.
    _VOLUME_LAYER_STATE["page"] = bool(ctx.available.volume_layer_shown)

    # --- the Y / Z cut sheets: STATE and TRIGGERS, no widgets yet -------------
    #
    # WHY GATED, and why on this particular flag: every helper below reads
    # ``info[PLANE_KEY]`` - the legacy dump's (station, y, z) stack
    # (_plane_layout :3166, _cut_layout :3369) - which an animation dump does not
    # carry at all, so calling any of them on a vis page is KeyError('plane_ez').
    # ``ctx.available.plane_stack`` is the page's own answer to "did this page
    # capture more than one x-plane" (um3k_context.py:143-165), computed once
    # from the data at boot; this does not re-read the format to guess it.
    #
    # WHY the widgets are NOT here: the two VSliders belong to the layout, built
    # far below (:9461). What is installed here is what both the layout and the
    # browser reach - the state the sliders will bind to, the two redraw pieces
    # ``_redraw_scene`` insists on, and the two triggers those sliders will fire -
    # so the cut machinery is complete and drivable before any widget exists.
    # --- the SAME cut sliders on an animation page ---------------------------
    #
    # WHY a second branch: a vis dump carries no ``plane_ez`` stack, so the
    # block below cannot run on it - but its |E| layer draws the SAME two cut
    # sheets (``_volume_cut_sheets`` :9139, added by ``_draw_volume_scene``
    # :9838), and those sheets were frozen at the middle j/k because
    # ``_draw_volume_layer`` asked ``_cut_layout`` with no arguments (:16848).
    # So the sliders are wired here exactly as there, and only three pieces
    # differ: ``_redraw_scene`` / ``_view_label`` are plane-stack-only (both
    # read ``planes[...]``, which this page has none of), so the redraw is
    # ``_show`` - the same call ``_redraw_for_plane_toggle`` already makes for
    # this page kind (:18078) - and the view label is not emitted on this
    # page at all (:11640 belongs to the dead run_web page), so it is not set.
    #
    # WHY ``volume_layer_shown`` and not the KEY alone: carrying the volume is
    # not drawing it - a vis dump holds ``e_abs_volume`` and still paints no
    # |E| picture while ``POC_SHOW_VOLUME`` is off (:1109-1111), so a pair of
    # sliders gated on the key would offer to move sheets that are not on
    # screen. The context ANDs the two halves at construction
    # (um3k_context.py:105-109, from the flag handed to it above).
    if not ctx.available.plane_stack and ctx.available.volume_layer_shown:
        n_j, n_k = _cut_axis_counts(info, 0, 0)
        # Opening cut = the middle, the same place the layer drew it before the
        # sliders could move it, so nothing jumps when the page loads.
        _cut_open = _cut_layout(info, n_j // 2, n_k // 2)
        state.cut_y = _cut_open["j"]
        state.cut_z = _cut_open["k"]
        state.cut_label = _cut_text(_cut_open)
        # No x-plane stack means no station sentence to show.
        state.station_readout = ""
        ctx.register_handle("cut_shape", (n_j, n_k))

        def _redraw() -> None:
            # ``_show`` is bound far below (:16953), so it is looked up at call
            # time, not captured here.
            _show(getattr(state, "frame", 0), getattr(state, "mode", None), "cut")

        def _redraw_cut(axis, value) -> None:
            # The same clamp ``_on_cut_change`` applies (:10717-10724), minus the
            # two calls that need a plane stack.
            limit = (n_j if axis == "y" else n_k) - 1
            try:
                idx = int(round(float(value)))
            except (TypeError, ValueError):
                idx = int(state.cut_y if axis == "y" else state.cut_z)
            idx = max(0, min(limit, idx))
            if axis == "y":
                state.cut_y = idx
            else:
                state.cut_z = idx
            state.cut_label = _cut_text(
                _cut_layout(info, int(state.cut_y), int(state.cut_z))
            )
            _redraw()

        # WHY no ``handles["cut_redraw"]``: this page has none on purpose (see
        # ``_redraw_for_plane_toggle``, :18078) - its boot draw is ``_show``
        # (:16953, issued once for real at boot :17450), so there is
        # nothing here that a repaint would add; installing the handle would
        # only draw the layer twice at boot.
        @ctrl.set("cut_y")
        def _on_cut_y(*args, **_kwargs) -> None:
            value = args[0] if args else _kwargs.get("cut_y", state.cut_y)
            _redraw_cut("y", value)

        @ctrl.set("cut_z")
        def _on_cut_z(*args, **_kwargs) -> None:
            value = args[0] if args else _kwargs.get("cut_z", state.cut_z)
            _redraw_cut("z", value)

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

    else:
        # A PAGE WITH NO DATA TO SLICE. Neither a plane stack nor a port-plane
        # archive resolved, so there is no cut to redraw and no sheet to frame:
        # all the page holds is what _vis_geometry drew over the board. Framing
        # it here, once, is what makes that board a picture instead of an empty
        # centre column; camera_framed_for is published so _show() does not
        # replace this view with its flat x-cut framing (which would also dim
        # the board to the overlay opacity meant for a field sheet).
        try:
            plotter.view_isometric()
            plotter.reset_camera()
            plotter._poc_camera_framed = True
            # No sheet on this page, so the set of families the camera was
            # framed for is EMPTY - and an empty set does not change when the
            # family flag does, which is what keeps this isometric view from
            # being replaced by _show()'s flat plane framing later.
            handles["camera_framed_for"] = ()
        except Exception as exc:  # noqa: BLE001 - decoration only
            print(f"[poc_app] bare board not framed: {exc}", file=sys.stderr)

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

    def _sync_picture_title(visible) -> None:
        """Point the title at the fields the 3D view is ACTUALLY showing.

        WHY the caller hands in a SET: a title is a claim about the picture
        under it, and this view can now show two pictures at once. The rule
        _show applies to the mode picture's visibility is the same rule here -
        its own family, and only the dump it was solved from - so "is this
        picture on screen" has to be asked against the same families the sheets
        were drawn for, not against the single name ``state.mode``. The set
        comes from _visible_families(), so the view keeps ONE opinion about
        what is drawn instead of the title growing its own.

        WHY the two titles are JOINED when both pictures are up: with the
        second family switched on, the |Ez| dump and the |E_t| cross-section
        are both on the page, and a title naming only one of them would lie
        about the other half of the view. With one family showing there is
        exactly one picture, so the title is that picture's own string, byte
        for byte what it was before this took a set.

        Cheap enough to call on every draw: _set_picture_title() writes
        nothing when the string has not changed.
        """
        try:
            entry = handles.get("mode_actor")
            on_screen = (
                entry is not None
                and entry.get("family") in visible
                and entry.get("page_path") == page.get("path")
            )
            index = None if entry is None else entry.get("index")
            if not on_screen:
                _set_picture_title(_animation_title_text(structure_label))
            elif len(visible) > 1:
                _set_picture_title(
                    _animation_title_text(structure_label)
                    + " + "
                    + _mode_title_text(structure_label, index)
                )
            else:
                _set_picture_title(
                    _mode_title_text(structure_label, index)
                )
        except Exception as exc:  # noqa: BLE001 - decoration only
            print(f"[poc_app] picture title kept: {exc}", file=sys.stderr)

    def _visible_families(mode: str) -> frozenset:
        """The families this view is showing, as ONE set every caller asks.

        WHY a set and not the single name ``state.mode`` used to be: each
        comparison below was a private opinion about which families are
        drawn, and a private opinion is exactly how a second plane ends up
        left visible on a frame it was never drawn for. Membership is the
        same question asked in one place, so turning the second family on
        is one flag rather than a hunt for comparison sites.
        """
        other = "xcut" if mode == "ycut" else "ycut"
        if state.show_other_family:
            return frozenset((mode, other))
        return frozenset((mode,))

    def _ycut_mode_label_text(info) -> str:
        """The on-page sentence naming the x-z sheet. NEVER raises.

        WHY ``info`` is an ARGUMENT and not a name closed over from this scope:
        _show() REBINDS ``info`` for the page it is drawing - a solve swaps the
        dump under the live page - so a helper reading the outer name would
        describe whichever page happened to be current when it was called,
        rather than the page whose frame is being labelled. Handing the page in
        keeps the sentence and the sheets it names on the same record.
        """
        # The y the x-z sheet sits on is READ per draw, from the LIVE page,
        # and is None when the dump records no j_cut - in which case no such
        # sheet exists to name. The readout says that rather than quoting a
        # station nothing was drawn at.
        station = _finite(info.get("j_cut"))
        return (
            "x-z sheet: not recorded - this dump carries no j_cut, "
            "so no x-z sheet is drawn"
            if station is None
            else (
                f"x-z sheet at y = {float(station) * cell_mm:.4f} mm "
                "(one recorded y sample)"
            )
        )

    def _xcut_mode_label_text(info) -> str:
        """The on-page sentence naming the fixed y-z planes. NEVER raises.

        An ``info`` argument for the reason above: every position in this
        sentence is READ from the dump, so it has to be read from the dump THIS
        frame is drawing. The near/far names are claimed only when the recorded
        load position agrees with them - otherwise they are slice 1 and 2.
        """
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
        return (
            "Transverse cross-section (y-z) looking down the line. "
            f"Strip width = {strip_text} mm, "
            f"domain width = {width_text} mm."
            f" Planes FIXED at x = {near_text} / {far_text} mm "
            f"({near_side} / {far_side}; the dump stores only these two)."
        )

    def _mode_label_text(info, mode: str, visible) -> str:
        """The on-page sentence naming EVERY sheet drawn on this frame. NEVER raises.

        WHY the family SET and not just ``mode``: _visible_families() is the one
        place that decides what is drawn, and with the second family switched on
        the page shows two sheets, one from each family. A sentence built from
        the mode alone would describe half the picture - the same class of bug
        as a comparison site holding its own opinion about visibility.

        WHY the primary family leads: the controls steer ``mode``, so the sheet
        they steer is named first and the second family follows it. The order is
        fixed (``mode``, then the rest sorted), so a stable page produces a
        stable string.

        WHY a failing sentence does not take the page with it: a label is
        decoration. A dump missing the keys one builder wants loses that
        builder's sentence, keeps the other, and says so on stderr.
        """
        builders = {
            "ycut": _ycut_mode_label_text,
            "xcut": _xcut_mode_label_text,
        }
        sentences = []
        others = sorted(family for family in visible if family != mode)
        for family in [mode] + others:
            build = builders.get(family)
            if build is None:
                continue
            try:
                sentences.append(build(info))
            except Exception as exc:  # noqa: BLE001 - a caption is not the page
                print(
                    f"[poc_app] {family} sheet sentence skipped: {exc}",
                    file=sys.stderr,
                )
        return " ".join(text for text in sentences if text)

    def _swap_scalar_bar(mode: str) -> None:
        """Leave exactly ONE PLANE bar standing, for the family now on screen.

        The y-cut sheet makes its bar at add_mesh time and the x-cut sheets make
        none, so a plane switch would otherwise keep the y-cut's bar over a field
        it does not describe. The replacement is built from the PRIMARY family's
        own sheet: every sheet was added with the same fixed (vmin, vmax), so
        the numbers do not move, only the actor the bar reads from does. A bar
        is decoration, so every step here degrades to a stderr line.

        WHY the primary family's sheet and not whichever sheet is "on screen":
        all three sheets carry the same field over the same fixed range, so the
        numbers on the bar are identical whichever one it reads from - the only
        thing the view varies is WHICH PLANE is drawn, and that is ``mode``. The
        x-cut family owns two sheets (near and far) with identical numbers; the
        first one in ``sheets`` order wins, deterministically, so the bar does
        not flip mapper as the sliders move.

        WHY the family SET is recorded and not just the mode: hiding the second
        family changes which sheets are drawn WITHOUT changing ``mode``, and a
        bar that only re-checks ``mode`` would keep claiming a set that is no
        longer on screen. ``handles["bar_for"]`` is written AFTER the bar is
        standing, so a rebuild that raises records nothing and the next tick
        tries again; the no-sheet branch records the set too, because "no bar is
        correct for these families" is a settled answer and not a failure - a
        stale bar that could not be removed would be worse than none, and this
        keeps it from being retried every frame as well.

        WHY the title is the plane's alone: this bar and the |E| volume's are
        two different fields on two different scales, and a title is the KEY
        pyvista stores a bar under - so this function removes and rebuilds the
        PLANE bar by name and never touches the volume's.
        """
        visible = _visible_families(mode)
        try:
            _remove_scalar_bar(plotter, scalar_bar_title)
        except Exception as exc:  # noqa: BLE001 - decoration only
            print(
                f"[poc_app] stale scalar bar kept: {exc}", file=sys.stderr
            )
        try:
            entry = None
            for item in sheets.values():
                if item["family"] == mode:
                    entry = item
                    break
            if entry is None:
                # Nothing of this family is drawn, so no bar is the right
                # answer: record the set and stop rebuilding for it every tick.
                handles["bar_for"] = visible
                return
            plotter.add_scalar_bar(
                mapper=entry["actor"].mapper, **plane_args
            )
            handles["bar_for"] = visible
            print(
                f"[poc_app] plane legend describes {scalar_bar_title!r} "
                f"for families {sorted(visible)}",
                file=sys.stderr,
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
        _sync_picture_title(_visible_families(state.mode))

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
            # A value map like the sheets, not a lit surface: the |E| mode is
            # read off the colour, and light would modulate it.
            lighting=False,
            show_edges=False,
            # The mesh stays OFF on this one, as the mode picture has always
            # been drawn. The light colour and width are declared anyway, so a
            # later decision to show this sheet's cell grid cannot arrive as the
            # black lattice the animated sheets were just rescued from.
            edge_color=VIS_EDGE_COLOR,
            line_width=VIS_EDGE_WIDTH,
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
        actor.visibility = "xcut" in _visible_families(state.mode)
        # The overlay follows the same rule and is drawn only when it was asked
        # for: off (the default) leaves this view byte-for-byte what it was.
        if state.show_quiver:
            _draw_mode_quiver(
                result, x_mm=x_mm_now, y_centre_mm=y_mid_mm, index=index
            )
        # The picture just put on the view is |E_t| of the mode, so the title
        # says so. A press that could not draw returned above, having already
        # reset the title through _clear_mode_picture().
        _sync_picture_title(_visible_families(state.mode))

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
            actor.visibility = "xcut" in _visible_families(state.mode)
        except Exception as exc:  # noqa: BLE001 - the overlay is an EXTRA
            print(f"[poc_app] mode vector field skipped: {exc}", file=sys.stderr)

    def _volume_layer_drop() -> None:
        """Take the |E| volume layer off the plotter and forget its bookkeeping.

        WHY one layer and not a set of actors: the volume, its two cut sheets and
        the port planes are built together and thrown away together, so this page
        needs exactly two operations - drop the whole layer, or build it afresh.
        ``handles["volume_layer"]`` is the entry that names the actors belonging
        to it; popping it is what keeps that entry and the screen in agreement.

        WHY the removal is guarded: this runs on the frame path, and an actor
        pyvista has already dropped must cost one actor, never the viewer.
        """
        entry = handles.pop("volume_layer", None)
        if not isinstance(entry, dict):
            return
        for _actor in entry.get("actors", ()):
            try:
                plotter.remove_actor(_actor, render=False)
            except Exception as exc:  # noqa: BLE001 - a stale actor is not fatal
                print(
                    f"[poc_app] stale volume layer actor kept: {exc}", file=sys.stderr
                )
        # WHY the volume bar dies with the layer: the bar is a reading of THIS
        # volume's |E| range. Left behind it would describe a layer that is no
        # longer on screen - and, since a title is pyvista's KEY for a bar, a
        # later frame rebuilding it under the same title would UNION the two
        # ranges instead of replacing one. EVERY spelling is cleared, not the two
        # constants: the title now states the window in force and the ramp, so
        # both modes and both ramps are swept - a bar left over from the other
        # mode would otherwise survive a mode change under a title nobody looks
        # for. ``_remove_scalar_bar`` is a no-op for a title that is not there.
        for stale_title in _volume_bar_titles():
            _remove_scalar_bar(plotter, stale_title)

    def _draw_volume_layer(index, mode, volume_frame=None) -> None:
        """Draw the |E| volume layer for the CURRENT frame, or drop it.

        WHY this is not part of ``_show``'s in-place rule: the animated sheets swap
        one scalar array because their lattice never changes, but a frame of the
        volume IS a different image - every nx*ny*nz sample on it changes - so the
        volume is REBUILT. The rebuild is cached on
        ``(page, frame, load, port, clim mode)``,
        so a redraw that lands on the same frame (the frame slider moving inside
        one saved volume step, or the app repainting for its own reasons) removes
        and rebuilds nothing, and the actor count of this page cannot grow with the
        number of frames watched.

        WHICH colour range: ``state.volume_clim_mode``, normalised through
        ``_volume_clim_mode`` so an absent or unknown value is the DEFAULT,
        "global". The mode is part of that cache key ON PURPOSE - the entry
        remembers the range it was painted on, so a mode change the key cannot
        see would be a cache HIT and the layer would keep the old mode's clim
        until the slider moved to another stored frame.

        WHEN the picture appears: this is called from ``_show`` just before its
        single ``plotter.render()``, so a frame is on screen at the same moment the
        sheets' frame is: one draw per tick, not two.

        WHICH volume frame: the slider indexes the PLANE family's own frames -
        the player's clock - while ``e_abs_volume`` is the decimated layer, one
        capture every N-th plane frame. The two are joined by the steps actually
        written into each array (``frame_index``/``frame_index_xcut`` against
        ``e_abs_volume_step_index``), never by dividing a step by a stride: a
        restart or a dropped sample leaves a non-uniform cadence behind, and
        ``step // stride`` would then point at the wrong frame.

        WHEN the caller already knows the volume frame - the player does, through
        ``_volume_player_plan``, on every position it can map - it hands it in as
        ``volume_frame`` and THAT frame is drawn: the NEAREST capture to the
        plane frame on screen. It is not re-derived here on purpose: the fallback
        below answers "the last capture at or before this step", which on its own
        is a stale layer for every plane frame sitting between two captures, and
        always painting that stale volume is the very desynchronisation the plan
        exists to remove.
        """
        try:
            info = page["info"]
            volume = info.get("e_abs_volume")
            if volume is None:
                # A dump with no volume carries no layer: dropping a stale one is
                # the whole job here, and a no-volume page is left as it was.
                _volume_layer_drop()
                return
            entry = handles.get("volume_layer")
            same_source = isinstance(entry, dict) and entry.get("source") is volume
            # The reference the range is measured against, read ONCE per draw.
            clim_mode = _volume_clim_mode(
                getattr(state, "volume_clim_mode", VOLUME_CLIM_DEFAULT)
            )
            # The |E| frame for this position comes from the player when a
            # caller hands one in, and otherwise from the timeline's ONE
            # sample-and-hold - the same lookup the label uses, so the picture
            # and the caption can never disagree about which capture this is.
            timeline = _timeline_for(info)
            if volume_frame is not None:
                vol_frame = volume_frame
            elif timeline is None:
                vol_frame = None
            else:
                vol_frame = timeline.layer_index(
                    _timeline.VOLUME_LAYER, timeline.clamp(index)
                )
            if vol_frame is None:
                _volume_layer_drop()
                print(
                    "[poc_app] |E| volume layer skipped: "
                    "this frame maps to no recorded volume sample",
                    file=sys.stderr,
                )
                return
            # The dump's OWN step at this position, read off the timeline's axis
            # (``frame_index``), never ``position + 1``: the slider indexes
            # recorded frames, and a restart or a dropped dump leaves the two
            # disagreeing. This is what the layer's readout reports, so it is
            # refreshed on a cache HIT as well as on a rebuild.
            step = None if timeline is None else int(timeline.steps[timeline.clamp(index)])
            show_load = bool(getattr(state, "show_load_plane", True))
            show_port = bool(getattr(state, "show_port_plane", True))
            # The cache key carries the TWO SWITCHES: the markers are part of this
            # layer, so toggling one must rebuild it - and nothing else.
            # WHY the MODE is part of this key: the entry remembers the range it
            # was painted on, so a mode change the key cannot see is a cache HIT
            # - the layer keeps the old mode's clim until the slider reaches
            # another stored frame, and the control looks dead.
            # WHY the CUT is part of this key too: the two sheets are actors of
            # this layer, so a moved cut must rebuild it - a HIT would leave the
            # sheets where the previous draw put them and the slider would look
            # dead.
            key = (
                page.get("path"),
                vol_frame,
                show_load,
                show_port,
                getattr(state, "cut_y", None),
                getattr(state, "cut_z", None),
                clim_mode,
            )
            if same_source and entry.get("key") == key:
                # WHY the step is rewritten on a HIT: ``step`` is the sim time this
                # layer is showing, and MANY frame-slider positions map onto ONE
                # stored volume frame - a bucket of ``dump_stride *
                # volume_stride`` steps. Returning here without refreshing it left
                # the entry naming the step of the FIRST draw in the bucket, so a
                # readout fed from it froze for the whole bucket: a silent lie
                # about simulation time. Nothing is rebuilt - only the one field
                # the hit made stale is refreshed, with the SAME value the rebuild
                # below would have stored (a lookup through ``frame_index``, never
                # ``index + 1``).
                entry["step"] = step
                _timing_mark("layer_hit")
                return
            _timing_mark("miss_start")
            _volume_layer_drop()
            _timing_mark("miss_drop")
            # The remembered range, reused ONLY on the reference it was measured
            # against: the whole-recording range is one number for every frame of
            # the recording (which is why it is remembered at all), a per-frame
            # range belongs to the frame it came from, and a range measured under
            # the OTHER mode is a different reference entirely. Everything else
            # is re-resolved here, so a mode change never inherits the old mode's
            # floor through the memo.
            reusable = (
                same_source
                and entry.get("clim_mode") == clim_mode
                and (
                    clim_mode != VOLUME_CLIM_PER_FRAME
                    or entry.get("frame") == vol_frame
                )
            )
            # WHY the WHOLE volume in the DEFAULT mode and not the frame: the
            # frames are one recording, and a range measured per frame would
            # paint the recorded decay away - the exact lie the sheets refuse.
            # "per_frame" is the SELECTABLE exception: same 60 dB span, and its
            # reference is the frame's own peak.
            clim = entry.get("clim") if reusable else None
            if clim is None:
                clim = _volume_clim_for(volume, vol_frame, clim_mode)
            if clim is None:
                print(
                    "[poc_app] |E| volume layer skipped: "
                    "the volume holds no finite sample",
                    file=sys.stderr,
                )
                return
            # The |E| image FIRST: ``_cut_layout`` and ``_volume_cut_sheets`` both
            # resolve their dims through the memo this seeds, so the cuts land on
            # exactly the lattice the volume was just built on.
            if _volume_frame_grid(info, vol_frame, cell_mm, clim) is None:
                print(
                    "[poc_app] |E| volume layer skipped: "
                    "the frame grid could not be built",
                    file=sys.stderr,
                )
                return
            # The cut follows the page's sliders (``state.cut_y`` / ``cut_z``,
            # wired at :15830). ``None`` - a page that never set them - means the
            # middle, and ``_cut_layout`` clamps both itself (:8958-8967), so a
            # stale index cannot reach the subset.
            layout = _cut_layout(
                info, getattr(state, "cut_y", None), getattr(state, "cut_z", None)
            )
            before = set(plotter.actors)
            _timing_mark("miss_actors_before", actors_before=len(before))
            # WHY the two builders are MUTED here: each ends in its own
            # ``plotter.render()`` - ``_draw_volume_scene`` issues three and
            # ``_draw_port_plane_markers`` two - and ``_show`` draws ONCE more as
            # soon as this returns. Unmuted, one miss paid six full frames to put
            # one picture on screen, five of them of a half-built layer nobody
            # ever saw. ``render`` is silenced for the duration of these two calls
            # ONLY, restored in ``finally`` so no later path inherits the mute, and
            # the single draw they were asking for is issued below, once the layer
            # is whole.
            _real_render = plotter.render
            plotter.render = lambda *args, **kwargs: None
            try:
                _timing_mark("miss_scene_start")
                _draw_volume_scene(
                    plotter,
                    info,
                    grid=None,
                    cut_layout=layout,
                    cell_mm=cell_mm,
                    clim_override=clim,
                    # The bar has to say which window this range was measured over,
                    # and the mode is the only place that knows.
                    clim_mode=clim_mode,
                )
                _timing_mark("miss_scene_end")
                _timing_mark("miss_markers_start")
                _draw_port_plane_markers(plotter, info, cell_mm, show_load, show_port)
                _timing_mark("miss_markers_end", actors_after=len(plotter.actors))
            finally:
                plotter.render = _real_render
            # THE one draw the muted builders were asking for. Guarded like the
            # rest of the layer: a failed render is one lost frame, not a lost
            # server.
            try:
                plotter.render()
            except Exception as exc:  # noqa: BLE001 - the layer is an EXTRA
                print(f"[poc_app] render skipped: {exc}", file=sys.stderr)
            handles["volume_layer"] = {
                "actors": [
                    plotter.actors[name]
                    for name in plotter.actors
                    if name not in before
                ],
                "source": volume,
                "clim": clim,
                "clim_mode": clim_mode,
                "key": key,
                "frame": vol_frame,
                "step": step,
            }
        except Exception as exc:  # noqa: BLE001 - the layer is an EXTRA
            print(f"[poc_app] |E| volume layer skipped: {exc}", file=sys.stderr)

    def _draw_port_plane_markers(
        plotter_obj, info, cell_mm, show_load, show_port
    ) -> None:
        """Mark the load, S11 and stub-side planes on the volume layer.

        WHY the positions come from the dump and not from ``_plane_layout``: this
        page reads a VIS dump, which carries no layout dict, so ``_plane_layout``
        has nothing to resolve against. The three places this layer needs ARE
        recorded - ``load_x_mm``, ``port_x_mm`` and ``xcut_far_mm`` - and when one
        of them is absent the markers are NOT invented: the layer names the key it
        is missing and draws no plane, the same rule the corner legend follows.

        WHAT they mean: ``port_x_mm`` is the SOURCE / S11 reference plane and
        ``xcut_far_mm`` the stub-side extraction plane, so the red disc and the
        purple one are the two surfaces the S-parameters are taken at.

        WHY ``s21_valid`` is None: a vis dump records where the extraction planes
        ARE, but no verdict about them. ``None`` is exactly "not recorded", and
        ``_s21_label`` then says so instead of claiming a validity it cannot know.
        """
        positions = {
            "x_load_mm": _finite(info.get("load_x_mm")),
            "x_s11_mm": _finite(info.get("port_x_mm")),
            "x_s21_mm": _finite(info.get("xcut_far_mm")),
        }
        missing = [name for name, value in positions.items() if value is None]
        if missing:
            print(
                "[poc_app] port planes not drawn: this dump does not record "
                f"{', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            return
        _add_markers(
            plotter_obj,
            info,
            dict(
                positions,
                cell_mm=cell_mm,
                s21_valid=None,
                s21_reason=None,
                s21_valid_src="not recorded",
                show_load_plane=show_load,
                show_port_plane=show_port,
            ),
        )

    def _show(frame, mode=None, site="show") -> None:
        """Draw ONE frame of the selected family. Never rescales.

        ``site`` is passed straight to the push (see ``_push_still``) and names the
        control that asked for the frame in the ``push_by_site:`` breakdown.

        The colour limits were fixed when the sheets were added, so this only
        swaps the scalar array: there is no per-frame normalisation here that
        could paint the recorded decay away.
        """
        _timing_tick_begin(frame, mode)
        if _profile_enabled():
            # ONE wrapper on the plotter INSTANCE: pyvista renders for itself
            # (add_mesh draws unless told not to), so a counter at our own call
            # sites would report one draw where the library started three.
            _profile_attach(plotter)
        _profile_tick_begin(frame, mode)
        # The LIVE page, read on every draw: a finished solve swaps the dump
        # under this closure, and the readouts below must follow it.
        info = page["info"]
        previous_mode = state.mode
        mode = state.mode if mode is None else mode
        mode = "xcut" if mode == "xcut" else "ycut"
        mode_changed = mode != previous_mode
        # ONE clock for the volume and the cut planes: the PLANE family's, so a
        # position is one recorded plane frame and one solver step. The |E|
        # volume is the coarser recording and is drawn as a DECIMATED LAYER at
        # the position's nearest capture (see ``_volume_player_plan``) - it no
        # longer decides how many positions there are.
        plan = _volume_player_plan(info, mode)
        timeline = _timeline_for(info)
        frames = None if timeline is None else int(timeline.nsteps)
        try:
            index = int(round(float(frame)))
        except (TypeError, ValueError):
            index = int(state.frame)
        # A page with no timeline has no frame axis to clamp into: nothing was
        # indexed (no sheet was drawn), and the label below stays ABSENT rather
        # than claiming frame 1 of None.
        if timeline is None:
            index = 0
        else:
            index = timeline.clamp(index)
        state.frame = index
        state.mode = mode
        # Phase "reanchor": everything up to the position being written - the
        # page read, the mode resolve and the clamp into the timeline.
        _profile_phase("reanchor")
        # The PRIMARY family's plane frame and the volume frame THIS position
        # draws: the two single indices the rest of the tick still reads (the
        # sim-time label and the |E| layer). Both fall back to the position
        # itself when there is no plan (no volume, or no readable step axis): a
        # dump with one timeline keeps the behaviour it had. The CUT SHEETS no
        # longer read it - each resolves its OWN family's stored sample below.
        plane_index = index
        if timeline is not None:
            held = timeline.layer_index(
                _timeline.XCUT_LAYER if mode == "xcut" else _timeline.YCUT_LAYER,
                index,
            )
            if held is not None:
                plane_index = int(held)
        volume_frame = plan["volume"][index] if plan is not None else None
        # Phase "target": the two indices this tick will paint, resolved.
        _profile_phase("target")

        _timing_mark("sheet_start")
        for key, entry in sheets.items():
            visible = entry["family"] in _visible_families(mode)
            try:
                entry["actor"].visibility = visible
            except Exception as exc:  # noqa: BLE001 - a stuck sheet is not fatal
                print(
                    f"[poc_app] sheet visibility skipped: {exc}", file=sys.stderr
                )
            if not visible:
                continue
            # EACH sheet maps its OWN layer: its family's recorded step axis,
            # sample and hold, is the only thing its scalars may be read at.
            # This lookup used to happen ONCE above the loop, for the primary
            # family alone, so a second family drawn in the same tick would be
            # handed the primary's stored sample - another family's frame. The
            # family NAMES the layer (server/timeline.py defines those two
            # constants for exactly these two families); a family with no layer
            # keeps the position, because no mapping is defensible for it.
            layer_name = {
                "ycut": _timeline.YCUT_LAYER,
                "xcut": _timeline.XCUT_LAYER,
            }.get(str(entry.get("family")))
            sheet_index = index
            if timeline is not None and layer_name is not None:
                held = timeline.layer_index(layer_name, index)
                if held is not None:
                    sheet_index = int(held)
            array = info[key]
            # A sheet is BUILT from a non-empty array at boot (_vis_grid reads
            # frame 0), so this can only skip a sheet this dump never had: it
            # must never be the reason a VISIBLE sheet goes without scalars.
            if array.shape[0] == 0:
                continue
            _psheet = _profile_sheet_begin(key, entry.get("grid"))
            data = np.abs(
                np.asarray(
                    array[min(sheet_index, int(array.shape[0]) - 1)], dtype=float
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
            # Closed HERE, inside the loop: the per-sheet number is this sheet's
            # own upload, not the three sheets' total.
            _profile_sheet_end(
                _psheet,
                min(sheet_index, int(array.shape[0]) - 1),
                entry.get("grid"),
            )

        _timing_mark("sheet_end")
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
                    mode_entry.get("family") in _visible_families(mode)
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
                    and quiver_entry.get("family") in _visible_families(mode)
                    and quiver_entry.get("page_path") == page.get("path")
                )
            except Exception as exc:  # noqa: BLE001 - an overlay is not the page
                print(
                    f"[poc_app] mode vector field visibility skipped: {exc}",
                    file=sys.stderr,
                )
        # The family switch above is also a title switch: the pictures just
        # went hidden (or came back), and the title names the fields now on
        # screen.
        _sync_picture_title(_visible_families(mode))

        # The bar describes a SET of families for the same reason the camera
        # does: switching the second family on changes what is drawn without
        # changing ``mode``, so the mode alone cannot say the bar is current.
        bar_for = _visible_families(mode)
        if mode_changed or handles.get("bar_for") != bar_for:
            _swap_scalar_bar(mode)

        # The camera is framed for a SET of families, not for the mode alone:
        # with the second plane switched on, twice as much field has to fit, and
        # a camera framed for the first plane is the wrong camera. The set is
        # recorded beside the view and re-compared on EVERY tick, because the
        # flag can change on a tick where the mode did not. It is the families
        # of the sheets actually ON this page - the same set the bounds below are
        # unioned over - so a page holding no sheet frames the empty set and is
        # never re-framed by a flag it does not draw.
        framed_for = tuple(
            sorted(
                {
                    entry["family"]
                    for entry in sheets.values()
                    if entry["family"] in _visible_families(mode)
                }
            )
        )
        if mode_changed or handles.get("camera_framed_for") != framed_for:
            # Frame the sheets that are about to be drawn, not the whole 3-D
            # box: with all three sheets plus the substrate in view the animated
            # field was a sliver in the middle of the picture. view_xz looks
            # along -y (the y-cut sheet's own plane), view_yz along -x (the
            # plane both x-cut sheets sit in): the PRIMARY family still chooses
            # the ANGLES, and an oblique "two planes in a cross" view is a
            # later, separate decision that this latch does not invent.
            bounds = None
            for entry in sheets.values():
                if entry["family"] not in framed_for:
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
                    if actor is plotter.actors.get("substrate"):
                        # The slab is the ONE overlay the operator can dim: it is
                        # read against the field it sits under, so its opacity is
                        # the slider's (dimmed further square-on, where it is
                        # edge-on - _substrate_drawn owns that rule).
                        actor.prop.opacity = _substrate_drawn(mode)
                    elif mode == "ycut":
                        # Square on to the x-z sheet the substrate is edge-on and
                        # would cover the field it is meant to annotate, so it is
                        # dimmed (and outlined) only for this family.
                        actor.prop.opacity = 0.08
                    else:
                        actor.prop.opacity = drawn_opacity
                    if mode == "ycut":
                        # The outline is the y-cut's alone, and it is applied
                        # OUTSIDE the opacity chain above on purpose: the slab now
                        # takes the first branch there, so a line left inside the
                        # elif would stop outlining the very box it was written
                        # for. Still ONE call, so the panel's Grid box owns it.
                        actor.prop.show_edges = _cell_edges_on()
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
                handles["camera_framed_for"] = framed_for
            except Exception as exc:  # noqa: BLE001 - keep the previous camera
                print(
                    f"[poc_app] camera reframe skipped: {exc}",
                    file=sys.stderr,
                )

        t_ns = _vis_frame_time_ns(info, mode, plane_index)
        state.t_label = (
            "sim time: not recorded"
            if not np.isfinite(t_ns)
            else f"sim time: t = {t_ns:.6f} ns"
        )
        # The axis is read from the LIVE page beside the frames: a solve that
        # swapped the dump under this page must relabel from the NEW record.
        state.frame_label = _frame_label(index, frames, info.get(TIME_AXIS_KEY))
        # The |E| layer's own reading goes to the LOG, not into the sentence:
        # one label states one clock, and the second clock is still stated
        # where an operator can read it.
        if _volume_layer_enabled():
            _log_volume_layer_note(info, mode, index)
        # The sweep time is a property of THIS page's timeline, so it is refreshed
        # on every draw beside the frame label rather than only when the select
        # moves: a finished solve, a family swap or a page swap all replace the
        # frame count under a caption that would otherwise quote the old one.
        state.play_caption = _play_caption(
            frames,
            _play_stride(
                stride,
                _play_rate_near(getattr(state, "play_rate", DEFAULT_PLAY_RATE)),
            ),
            paint_fps,
        )
        state.phase_label = _vis_phase_text(t_ns, info.get("t_traverse_ns"))
        # The sentence names EVERY sheet this frame drew, so it is built
        # from the same family set the sheets were drawn for: with the
        # second family on, a label built from ``mode`` alone would
        # describe half the picture. Primary first, so the field the
        # controls steer leads the sentence.
        state.mode_label = _mode_label_text(
            info, mode, _visible_families(mode)
        )
        # The |E| volume layer last, and BEFORE the render: it is part of this
        # frame, so it rides the single draw the sheets already paid for - and
        # it is handed the same position resolved to the two indices it paints,
        # so the volume, the cuts and the sheet cannot show two different frames.
        # A page whose dump carries no volume drops a stale layer and returns:
        # nothing else changes for it.
        _timing_mark("layer_start")
        if _volume_layer_enabled():
            _draw_volume_layer(plane_index, mode, volume_frame)
        else:
            # OFF: whatever layer an earlier tick drew is taken OFF the plotter
            # rather than orphaned, and its |E| bar with it. The drop removes
            # its own actors with ``render=False``, so a tick that draws no
            # volume still costs exactly the one render below.
            _volume_layer_drop()
        _timing_mark("layer_end")
        # ONE draw and ONE push per tick, decided in one place: a trame view
        # that pushes from its own render callback must not be pushed again
        # (see _tick_render_and_push).
        rendered = _tick_render_and_push(plotter, handles.get("view"), site)
        if rendered:
            # The GL strings are only askable once a frame has really drawn, and a
            # view push only QUEUES that draw - so this says the report on the
            # first tick that finds the window rendered, once (see
            # _renderer_report_after_render).
            _renderer_report_after_render(plotter, handles)
            # The scene dump rides the SAME "a frame really drew" gate, and for
            # the same reason: an actor listed before the draw is a half-built
            # scene. One-shot, and off unless POC_DUMP_ACTORS asks for it (see
            # _dump_actors_once). ``info`` is the page's own, already live here.
            _dump_actors_once(plotter, handles, info)
        _timing_tick_end(
            plotter,
            index=index,
            mode=mode,
            info=info,
            timeline=timeline,
            fps=fps,
            play_rate=getattr(state, "play_rate", DEFAULT_PLAY_RATE),
        )
        # Published, not asked: _show CLAMPS the position before writing it, so
        # a row that reported the request would hide the clamp.
        _profile_phase("flush")
        _profile_tick_end(state.frame, plotter=plotter, mode=mode)

    def _draw_extent_outlines() -> None:
        """Frame the sheets: domain box SOLID, captured window DASHED. NEVER raises.

        WHY this page needs it at all: the vis page drew no outline of any kind,
        so the sheets floated with no statement of the simulated domain - the one
        fact that makes a plane read as a CUT through something (page A draws the
        same frame in ``_draw_scene``, :10322, through the same helper).

        WHY it is redrawn by ``_rebuild_sheets`` and not once at boot: a finished
        solve puts a NEW dump on screen, whose counts need not be the old ones,
        so a frame kept from boot would box the domain that is no longer there.
        The previous actors are removed first (their names are remembered in
        ``handles["extent_actors"]``), so the frame is REPLACED, never stacked -
        two coincident black boxes would just be one box with two edges.

        WHY the volume layer does not own it: the box is framing, not field, so it
        must survive ``_volume_layer_drop``. It does - that drop only removes the
        actors the layer itself added.
        """
        for _actor in handles.pop("extent_actors", None) or ():
            try:
                plotter.remove_actor(_actor, render=False)
            except Exception as exc:  # noqa: BLE001 - a stale frame is invisible
                print(
                    f"[poc_app] stale extent outline kept: {exc}", file=sys.stderr
                )
        live = page.get("info") or {}
        # The grid is only read when the dump states NO axis at all (the helper
        # then frames what pyvista actually drew), so a missing sheet is not fatal.
        try:
            entry = sheets.get("ez_ycut") or next(iter(sheets.values()), None)
            grid = entry.get("grid") if isinstance(entry, dict) else None
            if grid is None:
                grid = _vis_grid(live, "ez_ycut", 0)
        except Exception as exc:  # noqa: BLE001 - the frame is decoration
            print(f"[poc_app] extent frame skipped: {exc}", file=sys.stderr)
            return
        before = set(plotter.actors)
        try:
            _add_extent_outlines(
                plotter,
                live,
                grid,
                # A vis dump records no station list, so this is None and only
                # the solid domain box is drawn - the shape of the picture the
                # dump actually states, never an invented window.
                live.get("stations_mm"),
            )
        except Exception as exc:  # noqa: BLE001 - the frame is decoration
            print(f"[poc_app] extent frame not drawn: {exc}", file=sys.stderr)
            return
        handles["extent_actors"] = [
            plotter.actors[name]
            for name in plotter.actors
            if name not in before
        ]

    def _rebuild_sheets(mode=None) -> None:
        """Re-create the three field sheets from the LIVE page's own info.

        A finished solve replaces every array on the page, so the sheets built at
        boot belong to a dump that is no longer the one on screen. They are
        removed and rebuilt here with the NEW dump's single colour limit, and the
        camera is re-framed because the new domain need not have the old bounds.
        """
        nonlocal nt, nt_x, vmin, vmax, cell_mm, y_span_mm
        live = page["info"]
        nt, nt_x = int(live["nt"]), int(live["nt_x"])
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
                # WHY no bar is made here: this loop REPLACES every sheet, and
                # a bar added under the same title would be union-merged with
                # the mappers of the sheets just dropped - the new dump's
                # (vmin, vmax) would silently widen to cover the old one. The
                # bar is placed once, below, from the sheet that survives.
                actor = plotter.add_mesh(
                    grid,
                    scalars="ez_abs",
                    cmap="turbo",
                    clim=(vmin, vmax),
                    smooth_shading=False,
                    # Same flat field as the boot sheets above, so the same
                    # statement: a rebuilt dump must not arrive lit.
                    lighting=False,
                    show_edges=_cell_edges_on(),
                    # Same light mesh as the boot sheets: a rebuilt dump must
                    # not come back as a black lattice over the field.
                    edge_color=VIS_EDGE_COLOR,
                    line_width=VIS_EDGE_WIDTH,
                    show_scalar_bar=False,
                )
            except Exception as exc:  # noqa: BLE001 - one sheet is not the page
                print(
                    f"[poc_app] plane {key} not redrawn: {exc}", file=sys.stderr
                )
                continue
            sheets[key] = {"grid": grid, "actor": actor, "family": family}
        # The plane bar is rebuilt from the sheet now on screen: the removal is
        # what drops the stale bar's claim on the title, so the new limit is
        # the one the bar reads. Never touches the |E| volume bar.
        _swap_scalar_bar(mode or state.mode)
        state.frame_max = _frame_max_for(live)
        # The prose lines that name THIS dump's numbers are rebuilt from `live`
        # rather than kept from boot: a solve can change the arm, the velocity
        # record and the colour ceiling all at once.
        state.structure_readout = _structure_readout_text(live)
        state.velocity_label = _velocity_label(live)
        state.scale_label = _scale_label(live)
        state.velocity_note = live["velocity_note"] or "velocity note: not recorded"
        # The dump line names the FILE, and a solve changes the file too. The
        # helper is pure over its arguments (_page_source_text, :882-920), so the
        # swap prints the same sentence boot did, from the same code.
        state.page_source_text = _page_source_text(live, nt)
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
        # The new dump needs its own framing, and None matches no family set,
        # so the next _show() tick re-frames (see camera_framed_for).
        handles["camera_framed_for"] = None
        # The frame belongs to the DUMP, so it is rebuilt with the sheets (see
        # _draw_extent_outlines): a solve changes the counts under it.
        _draw_extent_outlines()
        _show(0, mode or state.mode, "solve")

    # The frame, BEFORE the first frame of field: page A draws it in the same
    # place of its own draw order (after the field layer, before axes/markers),
    # and here it must exist before the volume layer takes its "actors before"
    # snapshot (:16152) so dropping that layer cannot take the box with it.
    _draw_extent_outlines()

    # Initial labels, set before the layout is built so the first page a browser
    # loads already carries frame 1's own numbers.
    _show(0, "ycut", "boot")

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
            return  # whoever set this flag draws the position itself
        value = state.frame if frame is None else frame
        if state.playing:
            # WHILE PLAYBACK RUNS, ONLY THE OPERATOR'S POSITIONS ARE DRAWN HERE.
            # The play loop publishes one position per tick, and its own write
            # comes straight back through this listener on the flush; the loop
            # names that ONE position in ``play_echo_frame`` so the echo is
            # recognised and NOT drawn a second time. Anything else on this key
            # while playing is a real seek - the scrubber, a << PREV / NEXT
            # press, a family swap that re-clamps the index - and it is drawn
            # now, so the picture matches the control a hand is on, while
            # ``state.frame`` is left exactly where the seek put it: the loop's
            # :func:`_play_reanchor` finds that position differs from the one it
            # drew itself, adopts it as the new clock origin and carries on from
            # there. The REJECTED alternative is to keep one flag over the whole
            # tick and hide every writer of ``state.frame`` behind it, which is
            # what made the scrubber and the step buttons look dead for as long
            # as the animation ran.
            echo = handles.get("play_echo_frame")
            if echo is not None and int(value) == int(echo):
                # The loop drew this position itself, so it IS the position on
                # screen: recorded as such, a later seek says where it left.
                handles["frame_seen"] = value
                return
            # EVERYTHING ELSE ON THIS KEY WHILE PLAYING IS THE OPERATOR'S, and it
            # holds the loop off the timeline for a moment: ``scrub_until`` is
            # stamped here, on the ONE path every real seek takes, and the pump
            # publishes nothing until it has passed (see the scrub gate in
            # _play_loop). WHY a stamp that EXPIRES and not a "dragging" flag: the
            # release of the drag is not reported by anything the server is
            # guaranteed to see - a client that goes away mid-drag never sends one -
            # so the hold has to run out on its own rather than wait to be lifted.
            # WHY inside ``state.playing``: with the animation stopped there is no
            # loop to hold off, and the seek below is the only draw the press needs.
            # ``time.monotonic`` and not the loop's own clock, because this listener
            # also runs on trame's server thread, where there is no running loop to
            # ask for one.
            handles["scrub_until"] = time.monotonic() + SCRUB_HOLD_S
        # A seek is a CLIENT event in the delivery's own stream, so a summary can
        # line the jump up against the paint times: from where the slider was to
        # where it landed. Off the suite nothing is recorded; what is drawn is
        # unchanged either way.
        _profile_seek(handles, value)
        handles["frame_seen"] = value
        _show(value, state.mode, "seek")

    # THE SLIDER'S OWN DRAG EVENTS, and they exist for ONE reason: the hold stamped
    # above runs out on a clock, so a thumb that has been let go would keep the pump
    # waiting for the rest of SCRUB_HOLD_S with nobody touching anything. ``start``
    # holds from the moment the thumb goes down (before it has moved), ``end`` lifts
    # the hold, so playback carries on from where the hand left it on the next beat.
    # A build whose VSlider carries no such events binds neither and loses nothing:
    # the hold then expires by itself, which is exactly the behaviour without them.
    # An ``end`` that arrives BEFORE the last frame write is followed by that write's
    # own stamp - the hold then expires by itself as well. Neither method moves the
    # position: the frame listener already drew the seek, and drawing over it is what
    # the hold is there to prevent.
    @ctrl.set("frame_scrub_start")
    def _on_frame_scrub_start(**_kwargs) -> None:
        """The thumb went down: keep the pump off the timeline from here."""
        if state.playing:
            handles["scrub_until"] = time.monotonic() + SCRUB_HOLD_S

    @ctrl.set("frame_scrub_end")
    def _on_frame_scrub_end(**_kwargs) -> None:
        """The thumb came up: let the pump carry on from where it was left."""
        handles["scrub_until"] = None

    @state.change("play_rate")
    def _on_play_rate(play_rate=None, **_kwargs) -> None:
        """Snap the selected speed to an offered one and restate its caption.

        ``play_rate`` is a bound UI value, so it arrives as whatever the client
        sent - a string from a URL, a number the select does not offer, None - and
        the loop would then advance by a rate nobody selected. The value is
        replaced with the nearest offered one here, at the ONE place that sees
        every write, and written back so the select and the caption show the speed
        actually in use.

        The write-back goes through ``suppress_change_listeners`` because it is a
        change to the very variable this listener is bound to: without it the
        write re-enters this handler, which is the shape of a flush loop rather
        than a redraw. The PLAYING loop needs no notification - it re-reads
        ``state.play_rate`` on every tick - so this handler only relabels.
        """
        raw = state.play_rate if play_rate is None else play_rate
        rate = _play_rate_near(raw)
        with state.suppress_change_listeners("play_rate"):
            state.play_rate = rate
        state.play_caption = _play_caption(
            _position_count(info), _play_stride(stride, rate), paint_fps
        )
        if _PROFILE["enabled"]:
            # A speed change is a CLIENT event in the same stream as the delivery's
            # animation start/stop: it is the one place the operator changes what the
            # picture is about to do, so a summary that cannot line it up against the
            # paint times would be reading half a conversation. Gated: with the suite
            # off this appends to nobody's list.
            _profile_client_record("speed")

    @ctrl.set("mode_toggle")
    def _on_mode_toggle(**_kwargs) -> None:
        """Swap which family is animated. The two clocks are never mixed."""
        mode = "xcut" if state.mode == "ycut" else "ycut"
        if _PROFILE["enabled"]:
            # A family swap replaces the frame count under the player and re-derives
            # the caption, so it belongs on the client timeline: a sweep that changed
            # length mid-run is otherwise indistinguishable from a paint stall.
            _profile_client_record("mode")
        # The SAME maximum in both modes: the press re-aims the camera and
        # clamps, it never rescales the timeline.
        state.frame_max = _frame_max_for(info)
        if state.frame_max is None:
            # NO TIMELINE: this page carries ONE static picture and no second
            # family to swap to (both counts are None), so the press changes
            # nothing. _show() is deliberately NOT called: its x-cut readouts
            # name keys only an animation dump records, so drawing a family
            # here would raise on the very dumps that have no timeline - and a
            # "Switch plane" press must never take the server down, which is
            # exactly what int(None) used to do.
            return
        _show(min(int(state.frame), int(state.frame_max)), mode, "mode")

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
        frames = _position_count(info)
        if state.playing:
            _show((int(state.frame) - 10) % frames, state.mode, "step")
            return
        state.playing = False
        state.play_label = "play"
        _show((int(state.frame) - 1) % frames, state.mode, "step")

    @ctrl.set("step_fwd")
    def _on_step_fwd(**_kwargs) -> None:
        """Ten frames forward while playing, exactly one while stopped.

        See _on_step_back: same split, same reason, same frame count.
        """
        frames = _position_count(info)
        if state.playing:
            _show((int(state.frame) + 10) % frames, state.mode, "step")
            return
        state.playing = False
        state.play_label = "play"
        _show((int(state.frame) + 1) % frames, state.mode, "step")

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
        _push_still(handles.get("view"), "mode_view")

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
        _push_still(handles.get("view"), "choice")

    # The Color Scale select's repaint. v_model=("volume_clim_mode", ...) only
    # WRITES state["volume_clim_mode"]: trame turns a callable into a server call
    # for EVENT kwargs (click=, change=), never for v_model, so an
    # @ctrl.set("volume_clim_mode") trigger would never be reached. The repaint
    # therefore hangs off the state change itself - the rule the frame slider
    # (:10922) and the Mode picker (:11280) already follow - and every writer of
    # the field (the select, a proof, a future button) takes ONE path.
    @state.change("volume_clim_mode")
    def _on_volume_clim_mode(volume_clim_mode=None, **_kwargs) -> None:
        """Re-reference the |E| layer's colour range and repaint it. NEVER raises.

        WHY ``_show`` and not ``plotter.render()``: the range is chosen INSIDE the
        volume-layer code path, which only ``_show`` re-enters - a bare render
        would repaint the frame on the OLD clim and the control would look dead
        until the slider moved. ``plotter.render()`` is then inside ``_show``, so
        there is exactly one draw.

        WHY EVERY STEP IS GUARDED: this handler fires on the first browser write
        and can fire before a plotter exists, on a page with no volume, or on a
        frame the page cannot name. None of those is a reason to take the server
        down, and the flag it maintains must be right even when the repaint is not
        possible.
        """
        try:
            mode = _volume_clim_mode(
                state.volume_clim_mode
                if volume_clim_mode is None
                else volume_clim_mode
            )
            state.clim_relative_warning = bool(_volume_clim_warning(mode))
            try:
                frame = int(round(float(state.frame)))
            except (TypeError, ValueError):
                frame = 0  # no frame axis yet: frame 0 is the one that is drawn
            _show(frame, getattr(state, "mode", None), "clim")
        except Exception as exc:  # noqa: BLE001 - a control is never the page
            print(
                f"[poc_app] clim mode repaint skipped: {exc}", file=sys.stderr
            )
            return
        # A SECOND still for one control: _show above already pushed this frame,
        # so this one is a duplicate send - named separately so the summary shows
        # it instead of folding it into the clim repaint's own count.
        _push_still(handles.get("view"), "clim_resend")

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
    def _plane_toggles_available() -> bool:
        """Can this page really HIDE a marker plane? NEVER raises.

        The ONE answer both the emitter and the toggle's repaint use, so a box
        cannot be offered on a page whose repaint would ignore it (nor withheld
        from one that would repaint). Two ways a page can answer:

        * it bound ``cut_redraw`` - the shared redraw rebuilds the marker layer
          with the scene (``_draw_scene`` -> ``_add_markers``);
        * it holds an |E| VOLUME - the discs are part of that volume layer and
          ``_show`` rebuilds it, its cache key carrying the two switches.

        A page with neither has no marker to hide, and the box would lie.
        """
        if callable(handles.get("cut_redraw")):
            return True
        try:
            return (page.get("info") or {}).get("e_abs_volume") is not None
        except Exception:  # noqa: BLE001 - a page dict is never a crash
            return False

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
            elif page["info"].get("e_abs_volume") is not None:
                # The |E| volume page keeps no cut_redraw (it has no plane
                # stack to re-cut), but the two marker discs ARE part of its
                # volume layer - and _show is what rebuilds that layer, its
                # cache key carrying the two switches this toggle just moved.
                # Without this branch the checkboxes were inert on this page.
                _show(state.frame, state.mode, "plane")
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

    # The other-family box. Same rule as the three controls above it: the box
    # only WRITES the flag, and the redraw hangs off the state change, so every
    # writer of the flag takes one path.
    @state.change("show_other_family")
    def _on_show_other_family(**_kwargs) -> None:
        """Draw or drop the second plane family. NEVER raises.

        WHY ``_show`` and not a bare redraw: WHICH sheets are drawn is decided
        INSIDE the draw (``_visible_families``), together with the camera bounds
        that must hold every visible sheet and the family the colour bar
        describes - none of which a re-cut re-enters. ``plotter.render()`` is
        then inside ``_show``, so there is exactly one draw.
        """
        try:
            _show(state.frame, state.mode, "family")
        except Exception as exc:  # noqa: BLE001 - a second sheet is an EXTRA
            print(
                f"[poc_app] other family toggle skipped: {exc}", file=sys.stderr
            )

    # The Grid box. The same rule a fourth time: the box only WRITES the flag,
    # and the grid it switches is applied HERE, to the sheets already on screen,
    # so the picture changes without a re-cut, a rebuild or a re-solve.
    @state.change("show_cell_edges")
    def _on_show_cell_edges(**_kwargs) -> None:
        """Add or drop the cell grid on every sheet on screen. NEVER raises.

        WHY the actors and not a redraw: the edges are a DRAWING property of the
        mesh that is already there, so nothing about the data, the camera or the
        colour bar changes - only whether the grid under the field is painted.
        """
        edges_state["on"] = bool(_kwargs.get("show_cell_edges", VIS_SHOW_EDGES))
        try:
            for entry in sheets.values():
                entry["actor"].prop.show_edges = _cell_edges_on()
        except Exception as exc:  # noqa: BLE001 - a grid is never the picture
            print(
                f"[poc_app] cell edge toggle skipped: {exc}",
                file=sys.stderr,
            )
        try:
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - one frame is not the page
            print(
                f"[poc_app] cell edge redraw skipped: {exc}",
                file=sys.stderr,
            )

    # The |E| volume layer's box. NOT the Grid box's rule a fourth time: a grid is
    # a DRAWING property of a sheet already on screen, but this layer is a picture
    # built and thrown away WHOLE (:16694, :16728), so switching it costs a real
    # redraw - through ``_show``, which is exactly where the layer is drawn or
    # dropped (:17292-17299) and what every other toggle on this page already uses.
    @state.change("show_volume_layer")
    def _on_show_volume_layer(**_kwargs) -> None:
        """Draw or drop the 3-D |E| volume layer. NEVER raises.

        Three steps, each guarded on its own because each can fail without the
        other two being wrong: the flag, the layer's cached entry, the redraw.
        """
        # 1. The flag. ``None`` in the cell means "the box has not spoken", so the
        #    fallback is the reader itself rather than a literal default.
        try:
            _VOLUME_LAYER_STATE["on"] = bool(
                _kwargs.get("show_volume_layer", _volume_layer_enabled())
            )
        except Exception as exc:  # noqa: BLE001 - a flag is never the page
            print(
                f"[poc_app] volume layer toggle ignored: {exc}", file=sys.stderr
            )
        # 2. The layer's cached entry. The cache is this HANDLE and not a module
        #    dict: the entry carries the key ``_draw_volume_layer`` compares before
        #    it paints (:16822-16831) and a HIT returns without touching the screen.
        #    Clearing the KEY - and NOT popping the entry - makes the next draw a
        #    MISS, and the miss path drops the old actors before rebuilding
        #    (:16846), so nothing is orphaned on the plotter. Without this a later
        #    ON can HIT an entry whose actors the OFF branch (:17294) already took
        #    off the plotter, and a HIT paints nothing: the switch would look dead
        #    in exactly one direction.
        try:
            entry = handles.get("volume_layer")
            if isinstance(entry, dict):
                entry["key"] = None
        except Exception as exc:  # noqa: BLE001 - a cache is never the picture
            print(
                f"[poc_app] volume layer cache not invalidated: {exc}",
                file=sys.stderr,
            )
        # 3. The redraw, in BOTH directions: ON rebuilds the layer, OFF lets the
        #    existing ``else:`` (:17294) take the stale layer and its |E| bar off
        #    the plotter. ``site`` is only the ``push_by_site:`` TIMING label the
        #    frame is accounted to (:17000-17001); this page redraws itself
        #    through the same repaint its cut sliders use, which accounts as "cut"
        #    (:15925).
        try:
            _show(getattr(state, "frame", 0), getattr(state, "mode", None), "cut")
        except Exception as exc:  # noqa: BLE001 - one frame is not the page
            print(
                f"[poc_app] volume layer redraw skipped: {exc}", file=sys.stderr
            )

    # n_line: the board-size note under the box. Same shape as the Grid box above.
    @state.change("run_n_line")
    def _on_run_n_line(**_kwargs) -> None:
        """Re-describe the n_line board for the box the browser just wrote.

        TEXT ONLY: no solve, no redraw, no spawn - the box describes the NEXT
        run, and typing in it must not start one. NEVER raises: it fires on the
        first browser write, possibly before the note exists.
        """
        try:
            state.run_n_line_note = _run_n_line_board(
                _kwargs.get("run_n_line", state.run_n_line)
            )
        except Exception as exc:  # noqa: BLE001 - a note is not worth the page
            print(f"[poc_app] n_line note ignored: {exc}", file=sys.stderr)

    # The Substrate slider. Same rule as the Grid box above it: the widget only
    # WRITES the flag, and the slab on screen is moved HERE, so a tick never
    # re-cuts, rebuilds or re-solves anything.
    @state.change("substrate_opacity")
    def _on_substrate_opacity(**_kwargs) -> None:
        """Dim or solidify the dielectric slab on the page already drawn.

        NOT a redraw: opacity is a property of an actor that is already there,
        and the camera, the colour bar and the data are untouched. NEVER raises.
        """
        try:
            substrate_state["opacity"] = float(
                _kwargs.get("substrate_opacity", VIS_SUBSTRATE_OPACITY)
            )
        except (TypeError, ValueError) as exc:  # noqa: BLE001 - a bad tick
            print(
                f"[poc_app] substrate opacity ignored: {exc}", file=sys.stderr
            )
            return
        try:
            actor = plotter.actors.get("substrate")
            if actor is not None:
                actor.prop.opacity = _substrate_drawn(
                    getattr(state, "mode", None)
                )
            plotter.render()
        except Exception as exc:  # noqa: BLE001 - the page stays up
            print(
                f"[poc_app] substrate opacity not applied: {exc}",
                file=sys.stderr,
            )

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
            # THE LOG under that line: the status names the child's LAST line,
            # the panel shows the dozen lines before it (SolveJob.log_lines, as
            # re-published by _tick_solve_status). It is a <pre> for the same
            # reason the Confidence rows are (server/poc_app.py:confidence_rows):
            # the lines are already formatted, and wrapping them is what makes
            # a long march's numbers readable. Its style is BOUND - hidden until
            # a run has printed something - and gets the same getattr fallback
            # the other html-layer panels use, so a build without that layer
            # loses the panel and keeps its button.
            pre_cls = getattr(html_widgets, "Pre", None)
            if pre_cls is not None:
                pre_cls(
                    "{{ solve_log }}",
                    style=("solve_log_style", _SOLVE_LOG_HIDDEN),
                )

        # WHICH PAGE has no field data: the GATED half of the Run Config card is a
        # form for the NEXT run, so it is offered exactly where there is nothing to
        # look at - a page already showing a field has a run behind it, and those
        # ten boxes would silently describe a job nobody is going to start.
        # Decided HERE, at build time, off the frozen snapshot the layout builders
        # read the same way (server/um3k_panels.py:83): a plain python branch emits
        # the ten fields or does not, so a page with data carries no hidden form
        # and no flag that has to stay in step with the data.
        # A one-station dump and an animation dump have a run behind them too:
        # ``port_planes`` is one captured x-plane and ``animation`` is a frame
        # axis, both statements about the DATA (um3k_context.py:99, :123-137).
        # Without them a solved vis page would offer a form whose numbers its own
        # recording already fixed. WHICH flags those are lives in the ONE
        # predicate, because the same question decides whether a press may
        # proceed (_solve_refused_page) - the branch below must never disagree
        # with the handler about it.
        has_field_data = not _run_config_form_shown(ctx.available)

        def _run_config() -> None:
            """Emit the Run Config card: Color Scale always, the form on a data-less page.

            WHY THE COLOR SCALE SELECT IS NOT GATED: it changes how the |E| volume is
            RENDERED, so it is meaningful exactly when a volume is on screen - it
            is the page WITH data that needs it, and gating it on 'no data' would
            make it dead where it matters. The ten run fields are the opposite
            kind of control (they describe a run that has not happened) and are
            gated at build time instead.
            """
            clim_cls = getattr(widgets_module, "VSelect", None)
            if clim_cls is not None:
                # The VALUE is the backend's own token, bound straight to the ONE
                # state name the |E| layer reads (state.volume_clim_mode): there is
                # no shadow state to keep in step, and the @state.change handler
                # named for it is what repaints.
                clim_cls(
                    v_model=("volume_clim_mode", VOLUME_CLIM_DEFAULT),
                    v_bind_items=_volume_clim_items_literal(),
                    item_title="title",
                    item_value="value",
                    label="Color Scale:",
                    density="compact",
                    hide_details=True,
                    classes="mb-1",
                )
            # WHAT the chosen option buys, and what it does not, directly under the
            # control: a caption is not a control, so it rides the same html_div the
            # degraded warning path uses. It is the bound on the word "Comparable" -
            # frames of this volume, not of the plane stack or the cut sheets.
            if html_div is not None:
                html_div(
                    VOLUME_CLIM_CAPTION,
                    style="font-size: 11px; color: #555; padding: 2px 0;",
                )
            # The warning, shown only while the renormalising mode is selected. The
            # flag is maintained by the change handler and true in no other state,
            # so the sentence cannot outlive the setting it describes.
            alert_cls = getattr(widgets_module, "VAlert", None)
            if alert_cls is not None:
                alert_cls(
                    VOLUME_CLIM_PER_FRAME_WARNING,
                    v_if=("clim_relative_warning", False),
                    type="warning",
                    density="compact",
                    classes="mb-1",
                )
            elif html_div is not None:
                # The degraded path: a variant with no VAlert still SAYS it, in the
                # page's own text idiom, under the same flag.
                html_div(
                    VOLUME_CLIM_PER_FRAME_WARNING,
                    v_if=("clim_relative_warning", False),
                    style="font-size: 11px; color: #8a1c00; padding: 2px 0;",
                )
            if has_field_data:
                return  # a page that already has a run behind it: no form
            run_field = getattr(widgets_module, "VTextField", None)
            if run_field is None:
                return
            defaults = _run_config_defaults()
            for state_name, label, _field in RUN_CONFIG_FIELDS:
                # The same numeric-input shape the cut plane uses (:11677): the
                # default is RunConfig's own number, never a literal here.
                run_field(
                    v_model=(state_name, defaults.get(state_name)),
                    # The form is for the NEXT run, and a solve ends with one on
                    # screen: once the dump on this page is a solved one, the
                    # boxes describe a job that has already happened. Hidden
                    # rather than rebuilt (the layout is built once, at boot)
                    # off ONE state flag, which starts true - the value this
                    # branch already decided - so a page that offers the form
                    # shows it from the first paint.
                    v_if=("run_config_visible", True),
                    label=label,
                    type="number",
                    density="compact",
                    hide_details=True,
                    classes="mb-1",
                )
            # What the n_line box BUYS, under the boxes it annotates: the same
            # sentence the refusal and the change handler produce, so the range
            # shown is the range enforced. It rides the boxes' own flag, so a page
            # that has put the form away keeps no note about it.
            if html_div is not None:
                html_div(
                    "{{ run_n_line_note }}",
                    v_if=("run_config_visible", True),
                    style="font-size: 11px; color: #555; padding: 2px 0;",
                )

        # The SOLVE form, in its OWN guarded block: a binding failure here costs
        # the solve form, never play/pause or the S-Parameters panel.
        try:
            _section("Project", _project, first=True)
            _section("Mesh & Geometry", _mesh_and_geometry)
            _section("Circuit", _emit_circuit_netlist)
            _section("Run Config", _run_config)
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
        """Pump ONE stride per PAINTED frame, until the trigger bumps the
        generation or state.playing is cleared.

        THE TICK IS NOT THE STEP ANY MORE. The tick grid is still the wall clock
        (``t0 + n/fps``, one wake-up per animation tick), but a tick now means "the
        display MIGHT paint", and only a tick that really paints advances the
        position - by ``_play_stride`` positions, wrapped by :func:`_play_advance`.
        That is what makes the caption true: it quotes positions per PAINTED frame,
        so "4 steps/tick at 24 fps" describes the sequence the viewer SEES. Advance
        on a tick whose still trame discarded and the position is spent on a frame
        nobody saw, which is exactly the mismatch between the promised sweep time
        and the picture that this loop is here to remove.

        Three gates decide whether a tick paints, and a gated tick advances NOTHING:

        * ``handles["scrub_until"]``: the operator moved the timeline and the frame
          listener drew it, so the loop keeps its hands off until the hold expires -
          a drag is a burst of seeks and this loop would answer every one of them
          with a paint of its own. In production the slider's ``end`` event lifts
          the hold as well; without it the hold runs out on its own.
        * ``paint_every``, the ``--paint-fps`` cap: at most one repaint per
          ``ceil(fps / paint_fps)`` ticks. Asking trame for a still more often than
          it can round-trip one (render + encode is tens of ms) does not produce a
          faster picture, it produces dropped stills, so the pump spends one repaint
          every N beats instead of flooding delivery with asks it will refuse.
        * ``_delivery_animating()``: while trame is animating a view client-side its
          ``push_render`` returns early (publish_image_delivery.py:26-35), so a still
          asked for now would be thrown away. Holding the position is the only
          honest option - advancing would move the sequence past a frame no client
          received.

        THE REJECTED ALTERNATIVES, both of which this loop used to be: advance
        ``rate`` positions per TICK regardless of delivery (the speed then belongs to
        the box and the encoder rather than to the operator, so the caption is a
        guess), and integrate a wall-clock target (:func:`_play_target` - still the
        honest answer for a machine that paints every tick) which keeps speed a
        property of time, so a dropped still costs a position that was never shown.
        Paint driven is the only shape in which "advanced" and "painted" cannot
        disagree.

        The LOOP IS SCHEDULED ON DEADLINES (``t0 + n/fps``), not as
        work-then-``sleep(1/fps)``: the old shape added the draw time to every
        period, so the tick rate silently fell below DEFAULT_FPS and the wall clock
        drifted away from the rate the caption quotes.

        A PAUSE PAINTS NOTHING - not a skipped paint, no paint: the trigger clears
        ``state.playing`` and bumps the generation, and both are re-checked right
        after every sleep, so a paused player costs one iteration and no draw.

        One draw per tick, and it is the loop's OWN draw: ``_show`` writes
        ``state.frame``, which fires the frame listener on the flush. The loop
        therefore names the ONE position it is about to publish in
        ``handles["play_echo_frame"]``, and the listener drops that position and
        nothing else: it is the loop's own echo, already on screen. Everything
        else on ``state.frame`` is the operator's, is drawn by the listener, and
        is then ADOPTED here by :func:`_play_reanchor` - which is why ``drawn``
        is pinned from what THIS tick published, before the yield below, and not
        read back off ``state.frame`` afterwards: read back, an operator's seek
        that landed while this coroutine was suspended looks like this loop's own
        draw, and the clock drags the position back over it. The REJECTED
        alternative is one ``suppress_frame_listener`` flag held across the whole
        tick, which silences a real seek for the duration of a draw.

        Runs as a background task. It must NOT be awaited from a trigger
        handler: see _on_play_toggle.
        """
        loop = asyncio.get_running_loop()
        # The clock origin: the position on screen NOW, at the time playback
        # started. Everything below is measured from this pair.
        t0 = loop.time()
        anchor_time = t0
        anchor_frame = int(state.frame)
        drawn = anchor_frame
        tick = 0
        # Wall clock of the PREVIOUS tick's deadline, so the log can show the
        # interval this loop actually achieved beside the one it asked for.
        _last_tick_at = None
        # The tick PERIOD is computed once and floored at 1 fps: a zero
        # would divide by zero here, before any position is drawn.
        period = 1.0 / max(1, int(fps))
        # How many TICKS one painted frame is worth: the paint cap, rounded UP so the
        # repaint rate never EXCEEDS what the operator asked for (an fps of 25 at a
        # cap of 10 is one paint every 3 ticks = 8.3/s, not every 2 = 12.5/s).
        # Computed once: fps and the cap are both fixed for the life of this task.
        paint_every = max(1, int(math.ceil(max(1, int(fps)) / max(1, int(paint_fps)))))
        while int(handles.get("generation", 0)) == gen and state.playing:
            tick += 1
            # Deadline, not period: the draw time comes out of the NEXT sleep
            # instead of being added to it (see the docstring).
            delay = (t0 + tick * period) - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            # Re-checked after the sleep: a pause, a step or a mode swap during
            # the wait may have ended this loop.
            if int(handles.get("generation", 0)) != gen or not state.playing:
                return
            # THE OPERATOR HAS THE TIMELINE IN HAND, so this beat publishes NOTHING.
            # A seek draws itself - the frame listener did it - and a loop that drew
            # over it would undo the scrub or fight the hand for the position, one
            # still render per mouse move, which is precisely the report "the
            # scrubber does nothing while it plays". Nothing here touches
            # ``play_echo_frame`` or ``drawn``: both still describe the loop's OWN
            # last paint, and that is exactly what the resumption needs -
            # :func:`_play_reanchor` finds ``state.frame`` differing from ``drawn``,
            # adopts the operator's position as the new clock origin and carries on
            # FROM WHERE THE HAND LEFT IT, so resuming costs no code of its own.
            # The hold has no ceiling: every new seek re-stamps ``scrub_until``, so a
            # long drag is held for as long as the hand is on the control.
            if time.monotonic() < float(handles.get("scrub_until") or 0.0):
                # Counted, not profiled, for the reason the two gates below give: a
                # held beat never reaches _show, so it emits no tick row of its own.
                _profile_count("scrub_hold")
                # THE DEADLINE GRID IS REBASED HERE, and that is not cosmetic:
                # ``tick`` keeps counting through the hold, so ``t0 + tick * period``
                # would run ahead of the wall clock by one period per held beat -
                # half a second of holding banks about 1.2 s of deadlines already
                # past, and the first thing a released playback would do is burn them
                # off in one burst of fast frames. Moving ``t0`` with the clock keeps
                # the grid one period away from now, so playback resumes on the next
                # beat, from the operator's position, at the rate it was asked for.
                t0 = loop.time() - tick * period
                # THE INTERVAL BASELINE IS RESET WITH IT, for the same reason: the
                # ``interval_ms`` this loop parks below is ``(_now - _last_tick_at)
                # * 1000``, and ``_last_tick_at`` is only written on a PAINTED
                # beat. Left at the last paint, the first row after a hold would
                # charge the whole stand-off to the resumed tick as one ~0.5 s
                # interval - a deliberate wait logged as a stalled loop, and the
                # row a reader uses to judge the loop against ``period_ms``.
                # Measured from the beat that lifted the hold, that row reports the
                # period the loop actually resumed at. ``drawn`` and
                # ``play_echo_frame`` are deliberately NOT touched: they describe
                # the loop's own last paint, which is what resuming needs.
                _last_tick_at = loop.time()
                # The yield is not optional, for the paint cap's reason: a beat whose
                # deadline has already passed took no sleep above.
                await asyncio.sleep(0.012)
                continue
            # THE PAINT CAP. No repaint is due on this beat, so nothing advances and
            # nothing is drawn: the position IS the picture, and a position nobody
            # painted is a position the viewer never saw. The yield is not optional -
            # a tick whose deadline has already passed took no sleep above, so without
            # it this coroutine could spin through the whole gate without ever
            # suspending and starve the websocket the frames travel on.
            if (tick - 1) % paint_every:
                # Counted, not profiled: a gated beat never reaches _show, so it
                # emits no tick row of its own - the count is attributed to the
                # next row that IS written (see _profile_tick_end).
                _profile_count("paint_cap")
                await asyncio.sleep(0)
                continue
            # THE CLIENT IS MID-ANIMATION: trame's push_render discards stills while
            # its views_in_animations list is non-empty (publish_image_delivery.py:
            # 26-35), so a still asked for now would be dropped after the work was
            # paid for. Hold the position and let the animation finish; None ("nobody
            # told us") is not animating, because refusing to paint on a guess would
            # freeze a playback that is visibly stuck.
            if _delivery_animating():
                # Same attribution as the paint cap above: a held beat has no
                # tick row, so the count rides on the next written row.
                _profile_count("delivery_hold")
                await asyncio.sleep(0)
                continue
            # The deadline this tick was DUE at, and how late it actually
            # began. Parked, not written: the tick line _show is about to
            # emit is the line these three numbers belong on.
            _now = loop.time()
            _timing_play_tick(
                period * 1000.0,
                None if _last_tick_at is None else (_now - _last_tick_at) * 1000.0,
                (_now - (t0 + tick * period)) * 1000.0,
            )
            _last_tick_at = _now
            # A FAILED TICK ENDS PLAYBACK, IT DOES NOT SILENTLY KEEP PLAYING.
            # This task is never awaited, so an exception escaping here would
            # only surface as "Task exception was never retrieved" at GC time:
            # state.playing would stay True, the button would still read
            # "pause" and nothing would ever advance - the same dead viewer as
            # a starved event loop, with no trace to explain it.
            try:
                rate = _play_rate_near(
                    getattr(state, "play_rate", DEFAULT_PLAY_RATE)
                )
                # ONE clock, whichever family is drawn: the timeline's. The
                # REJECTED alternative - the selected family's own array length -
                # made a plane toggle rescale the clock by ten (2400 positions on
                # the y-cut against 240 on the x-cut), so the same selected speed
                # played ten times faster after the switch. Read off the LIVE page
                # every tick, because a finished solve swaps the dump underneath
                # this closure.
                frames = _play_frames(_position_count(page.get("info") or info))
                now = loop.time()
                anchor_time, anchor_frame = _play_reanchor(
                    anchor_time, anchor_frame, now, int(state.frame), drawn
                )
                # ONE stride per painted frame, wrapped by the family length: the
                # clock no longer invents the position, the PAINT does.
                target = _play_advance(
                    anchor_frame, _play_stride(stride, rate), frames
                )
                # THE SUPPRESSION NAMES THE ECHO, NOT THE TICK. The position
                # about to be published is recorded BEFORE _show writes it, so
                # even a flush that fires the listener mid-draw can tell the
                # loop's write from an operator's.
                handles["play_echo_frame"] = int(target % frames)
                try:
                    # THE DRAW STAYS ON THE EVENT-LOOP THREAD, and that is not
                    # negotiable. The GL context belongs to the thread that made
                    # it: rendering it from a worker thread (asyncio.to_thread)
                    # aborted the process inside X_GLXMakeCurrent with "X Error:
                    # BadAccess" - no traceback, no exception, no exit code to
                    # read, the viewer simply disappeared. So _show and the flush
                    # that publishes what it wrote both run HERE, on the thread
                    # that owns the context.
                    _show(target % frames, state.mode, "play")
                    # _show CLAMPS the position into the timeline before it
                    # writes ``state.frame``, so the echo has to name what it
                    # PUBLISHED and not what this tick asked for: an echo that
                    # disagreed with the published value would be read as an
                    # operator's seek and drawn twice.
                    wrote = int(state.frame)
                    handles["play_echo_frame"] = wrote
                    state.flush()
                    # ``drawn`` IS THIS TICK'S OWN POSITION, PINNED BEFORE THE
                    # YIELD, and that ordering is the fix: read back off
                    # ``state.frame`` after the yield it could already hold an
                    # operator's seek - a scrub that arrived while this
                    # coroutine was suspended - and _play_reanchor would then
                    # take the seek for the loop's own draw and overwrite it on
                    # the next tick, which is exactly the "the scrubber and the
                    # step buttons do nothing while it plays" report.
                    drawn = wrote
                    # THE NEXT PAINT ADVANCES FROM WHAT WAS PUBLISHED, not from what
                    # this tick asked for and not from the wall clock: ``wrote`` is the
                    # position _show clamped and the client received, so the stride is
                    # measured off the sequence on screen. An operator's seek adopted
                    # by _play_reanchor above is respected for exactly one paint, which
                    # is why this re-anchor happens AFTER the draw and overrides it.
                    anchor_time, anchor_frame = now, wrote
                    # Dropped BEFORE the suspension point for the same reason: a
                    # change that arrives while this coroutine is suspended is
                    # the operator's and must never be mistaken for this echo.
                    handles["play_echo_frame"] = None
                    # EVERY TICK STILL YIELDS ITS THREAD. A late tick (its
                    # deadline already passed) took no sleep above, and the
                    # synchronous draw would then let this coroutine iterate
                    # without ever suspending: the websocket starves, the client
                    # stops receiving state and the picture freezes while the
                    # animation keeps advancing. sleep(0) is the suspension point
                    # the deadline sleep may not have provided.
                    await asyncio.sleep(0)
                    # Phase "yield": from the push mark to the sleep returning -
                    # what the loop spends between publishing a frame and being
                    # ready for the next one, the suspension included.
                    _profile_yield()
                finally:
                    handles["play_echo_frame"] = None
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[poc_app] playback stopped: {exc!r}",
                    file=sys.stderr,
                )
                state.playing = False
                state.play_label = "play"
                try:
                    state.flush()
                except Exception:  # noqa: BLE001
                    pass
                return

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

        Both branches append a timestamped ``pause``/``resume`` client event when
        the suite is on: the pause is the ONE moment the pump stops painting by
        operator request rather than by its own cap, so a summary that could not see
        it would blame the gap between two paints on delivery.
        """
        generation = int(handles.get("generation", 0)) + 1
        handles["generation"] = generation
        if state.playing:
            state.playing = False
            state.play_label = "play"
            if _PROFILE["enabled"]:
                _profile_client_record("pause")
            state.flush()
            return
        state.playing = True
        state.play_label = "pause"
        if _PROFILE["enabled"]:
            _profile_client_record("resume")
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
    # The LIVE LOG under that line: the same tail the status names only the END
    # of, as whole lines, re-published every half second by _tick_solve_status.
    # EMPTY and HIDDEN at boot - a page that has never run a solve has no log,
    # and an empty <pre> is a box of height that says nothing - and the style is
    # in the state (not a literal on the widget) because the widget is emitted
    # once and the run that fills it starts later.
    state.solve_log = ""
    state.solve_log_style = _SOLVE_LOG_HIDDEN
    # The LABEL and the ENABLED state describe the PAGE, not the job: this shell
    # serves a static field snapshot as well as an animation dump, and a static
    # page (nt is None - no frame axis, um3k_panels.py:127-140) has no timeline
    # for a new run to land in. A bare "Solve" over a snapshot read as "solve
    # THIS page", which nothing here does; so the label NAMES the page it is
    # drawn on ("Solve (static field snapshot)" over a snapshot, "Solve" over an
    # animation dump) and the grey-out is there so nobody reads the button as
    # "press this to refresh the picture" - the press starts a new run, it does
    # not re-read the file this page was opened from. The machinery is not
    # missing; it just does not do that.
    # REFUSED, not just greyed, only where the press would have nothing to work
    # with: no timeline AND no Run Config form (_solve_refused_page). A data-less
    # page has the form, so its Solve is the whole point of the page; the
    # decision is the shared predicate's, so this boot and the press handler and
    # the build-time form branch cannot disagree.
    static_page = _solve_refused_page(nt, ctx.available)
    state.solve_label = (
        "Solve (static field snapshot)" if static_page else "Solve"
    )
    state.solve_disabled = static_page
    # Whether the Run Config FORM is on screen: starts at the value the build-time
    # branch used (so the fields it emitted are visible from the first paint),
    # and a finished solve clears it - the dump on screen is then a run's result
    # and those boxes would describe a job that has already happened.
    state.run_config_visible = _run_config_form_shown(ctx.available)
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

    def _tick_solve_status(job) -> None:
        """Say what the running solve is doing: the clock, the last line, the log.

        The old sentence was written once at press and once at the single
        final poll, so a twenty-minute march displayed second-one text the
        whole way. It never raises: a status line is worth nothing next to a
        solve.
        """
        try:
            elapsed = job.elapsed_seconds
            if elapsed is None:
                head = f"solving {state.solve_structure} ..."
            else:
                head = (
                    f"solving {state.solve_structure} - {elapsed:.0f} s "
                    "elapsed"
                )
            tail = job.last_line
            state.solve_status = f"{head}\n{tail}" if tail else head
            # The SAME tail, as LINES and not just its end. solve_status names
            # one line, which is one line of a child that prints a study's worth
            # of numbers; the panel under it shows the last dozen (SolveJob
            # .log_lines), newest last, and it is HIDDEN again whenever the job
            # has printed nothing - a header over an empty box is worse than no
            # box.
            lines = job.log_lines
            state.solve_log = "\n".join(lines)
            state.solve_log_style = (
                _SOLVE_LOG_STYLE if lines else _SOLVE_LOG_HIDDEN
            )
        except Exception as exc:  # noqa: BLE001 - never take the page down
            print(f"[poc_app] solve status not updated: {exc}", file=sys.stderr)

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

        It also RE-PUBLISHES the status every half second (_tick_solve_status),
        which is the only reason a long solve is legible at all: that tick is
        itself wrapped, so a bad status write cannot end the watch.
        """
        while True:
            job = solve.get("job")
            if job is None or job.status not in ("idle", "running"):
                break
            _tick_solve_status(job)
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
        # The frame axis is what the new dump's own file says, not what this page
        # was opened with: the solve below replaces the data under the drawings,
        # so the closure's nt/nt_x are re-read from the page that just landed
        # (_rebuild_sheets and _show both draw off them).
        nonlocal nt, nt_x
        job = solve.get("job")
        if job is None:
            return
        status = job.poll()
        if status in ("idle", "running"):
            # "idle" is a child that has not been spawned yet, not a failure.
            _tick_solve_status(job)
            return
        # ONE duration for both outcome sentences below: the failure and the
        # success must not each read the clock (the second read would be a
        # different number, and neither of them is the interesting one).
        try:
            elapsed = (
                "?" if job.elapsed_seconds is None
                else f"{job.elapsed_seconds:.1f}"
            )
        except Exception:  # noqa: BLE001 - a clock is not the answer
            elapsed = "?"
        if status != "ok":
            # The OLD page stays live and drawable: a failed solve is a message,
            # not a broken viewer.
            # The child's own last lines are ALREADY on screen: the same
            # watcher published them into the log panel (_tick_solve_status,
            # every half second), so appending the 400-character blob here as
            # well printed the last screen of a failed solve TWICE - once as
            # lines, once as one string with no line breaks the card can use.
            # It is kept for the case the panel cannot carry it: a status set
            # before any tick ran (a build with no html layer, or a job that
            # died before the first poll), where the blob is the only copy of
            # the child's output the reader would ever see.
            shown = str(getattr(state, "solve_log", "") or "").strip()
            blob = "" if shown else f"\n{job.log[-400:]}"
            state.solve_status = (
                f"solve {status} after {elapsed} s (rc={job.returncode}) - "
                f"the page on screen is "
                f"still the previous dump{blob}"
            )
            return
        try:
            applied = apply_page(page, reload_page(LIVE_DUMP))
        except BaseException as exc:  # noqa: BLE001 - SystemExit is a refusal
            state.solve_status = f"solve ok, but the new dump did not load: {exc}"
            print(f"[poc_app] solved dump not loaded: {exc}", file=sys.stderr)
            return
        # ``ctx`` was built from the page the reader OPENED, and ``available`` is
        # frozen at construction (um3k_context.py:179-189): every flag below -
        # _solve_refused_page, the Run Config form - would otherwise keep
        # answering for the dump that is no longer on screen. The dump is
        # replaced on the SAME object and the one documented recompute path is
        # called: a fresh PageContext would drop the handles and callbacks
        # registered on this one while the layout was built (:13186-13218).
        try:
            ctx.dump = um3k_context.LoadedDump.from_any_dump(page)
            ctx.recompute_available()
        except BaseException as exc:  # noqa: BLE001 - a stale flag is not a crash
            print(
                f"[poc_app] page context not recomputed: {exc}", file=sys.stderr
            )
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
        # ---- the PICTURE, on the dump that just landed ----------------------
        # The sheets were built at boot from the page the reader opened, so the
        # new arrays have to be drawn HERE: there is no second visit, and a
        # "solved" sentence over the OLD picture read as "this view is now the
        # new run" when it was not. The axis is re-read from the new page first,
        # then one ordinary repaint - the same two steps every other handler uses
        # (_on_volume_clim_mode, :11420) - and every step can only cost the
        # redraw, never the solve that has already been applied.
        refresh_note = ""
        try:
            live_info = page.get("info") or {}
            if _is_vis(live_info):
                nt = int(live_info["nt"])
                nt_x = int(live_info["nt_x"])
            else:
                nt = None
                nt_x = None
            _rebuild_sheets()
            try:
                frame = int(round(float(state.frame)))
            except (TypeError, ValueError):
                frame = 0
            _show(frame, getattr(state, "mode", None), "solve")
            # A SECOND still for a frame _show has just pushed: a duplicate send. It
            # goes through _push_still like every other still, so the summary NAMES
            # it (push_by_site: solve_resend) instead of hiding it - before this it
            # was a push that reached the client and no counter.
            resend_view = handles.get("view")
            if resend_view is not None and not _push_still(
                resend_view, "solve_resend"
            ):
                refresh_note = " (the repeat frame was not sent)"
        except Exception as exc:  # noqa: BLE001 - the picture is not the solve
            refresh_note = f" (the picture was not refreshed: {exc})"
            print(f"[poc_app] solved page not redrawn: {exc}", file=sys.stderr)
        # The page's OWN consequences, after the data: there is now a run behind
        # this dump, so the Run Config form (a form for the NEXT run) is done
        # with, and the press is no longer the refusal it may have been - the
        # timeline just arrived.
        try:
            state.run_config_visible = False
            refused_page = _solve_refused_page(nt, ctx.available)
            state.solve_disabled = refused_page
            # The label is the boot one, recomputed the boot way (:12671-12673):
            # the page on screen is now THIS run's result, so the sentence over
            # the button has to come from this page's flags, not the old page's.
            state.solve_label = (
                "Solve (static field snapshot)" if refused_page else "Solve"
            )
        except Exception as exc:  # noqa: BLE001 - a message is not a crash
            print(
                f"[poc_app] solve page state not updated: {exc}", file=sys.stderr
            )
        # WHAT a reader gets is part of the sentence: the swap reaches the page's
        # own arrays, labels and picture, so the note only says what it cannot
        # reach - the dump line and the sheet cards built at boot.
        state.solve_status = (
            f"solved -> {Path(applied['new_path']).name} in {elapsed} s; "
            f"result loaded"
            f"{refresh_note}"
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
        page has no timeline for a new run to land in AND no Run Config form to
        run one with (_solve_refused_page), so a press either did nothing visible
        or replaced the dump under a page that cannot read it. The button is
        greyed out for the same reason (state.solve_disabled); this is the same
        refusal for a press that arrives anyway - a stale browser, or a caller
        driving the trigger directly.

        The Run Config form (RUN_CONFIG_FIELDS) is read HERE and nowhere else:
        this one handler builds the ONE ``RunConfig`` the child is given, so the
        form's boxes reach the solver by the same path a press always took - there
        is no second solve route for them to fall off.
        """
        if _solve_refused_page(nt, ctx.available):
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
        # ---- the Run Config form, as ONE validated config --------------------
        # Built HERE, at press time: the ten boxes are whatever the browser has
        # written by now, and RunConfig is where they are checked (whole steps, a
        # positive pulse, a far cut beyond the near one, a finite wall ceiling and
        # load). A box that is not a
        # number refuses the press with a sentence and spawns nothing - the same
        # shape as a refused netlist just below.
        form_values = {
            state_name: getattr(state, state_name, None)
            for state_name, _label, _field in RUN_CONFIG_FIELDS
        }
        if not str(form_values.get("run_xcut_near_mm") or "").strip():
            # A blank Run Config box has NO opinion on the near cut, so the
            # Action card's cut plane keeps the job it has always had. Text that
            # will not parse is NOT backfilled: run_config_from_form raises on it
            # just below, so the press is refused with a sentence naming the box.
            try:
                form_values["run_xcut_near_mm"] = float(state.solve_xcut_mm)
            except (TypeError, ValueError):
                pass
        try:
            run_config = run_config_from_form(form_values)
            xcut_mm = float(run_config.xcut_near_mm)
        except (TypeError, ValueError) as exc:
            print(f"[poc_app] solve refused: {exc}", file=sys.stderr)
            state.solve_status = f"refused: {exc}"
            return
        netlist_text = str(
            netlist_json or getattr(state, "solve_netlist_json", "") or ""
        )
        # A refused netlist raises HERE, before solve_argv has written anything,
        # so a bad edit costs a message and no file and no child process.
        try:
            argv = solve_argv(
                structure,
                xcut_mm,
                LIVE_DUMP,
                netlist_json=netlist_text,
                config=run_config,
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
        # The OTHER plane family's box: beside the arrow field's, and NOT behind
        # the marker guard below. That guard asks whether a page can HIDE one of
        # the two X-markers, and a family is not a marker - gating this box on it
        # would withhold the second sheet on exactly the pages that can draw it.
        try:
            checkbox_cls(
                # The same (state_name, default) binding as the box above: the
                # browser writes the flag and the @state.change handler below
                # decides what a change means. OFF at boot, so a page that never
                # touches it draws the one family it has always drawn.
                v_model=("show_other_family", False),
                label="Show Other Plane",
                hide_details=True,
                style="padding: 2px 0;",
            )
        except Exception as exc:  # noqa: BLE001 - a toggle is never the page
            print(
                f"[poc_app] other plane toggle unavailable: {exc}", file=sys.stderr
            )
        # The cell grid's box. Same (state_name, default) binding as the two
        # above, but the default is the NAME the sheets were built with rather
        # than a literal: the box must start telling the truth about the picture
        # it is beside, whatever that module flag says.
        try:
            checkbox_cls(
                v_model=("show_cell_edges", VIS_SHOW_EDGES),
                label="Grid (cell edges)",
                hide_details=True,
                style="padding: 2px 0;",
            )
        except Exception as exc:  # noqa: BLE001 - a toggle is never the page
            print(
                f"[poc_app] cell edge toggle unavailable: {exc}", file=sys.stderr
            )
        # The |E| volume layer's box: the first control on this panel that changes
        # what a MODULE-level draw function paints, rather than what one closure
        # paints. Same (state_name, default) binding as the three above, but the
        # default is asked of the ONE reader (:1128) at EMIT time rather than
        # taken from the module constant: the box must start telling the truth
        # about the picture it is beside, and that picture is whatever the page
        # policy and the environment decided.
        #
        # Emitted ONLY where the dump carries a volume: ``_draw_volume_layer``
        # (:16728) drops whatever layer is on screen and paints nothing when
        # ``e_abs_volume`` is absent, so a page without one must not be handed a
        # switch for a picture it cannot draw. ``info`` is ``run_web_vis``'s own
        # dump parameter (:15310), rebound to the live page at :15484, so at
        # emit time it IS the page's dump.
        if info.get("e_abs_volume") is not None:
            try:
                checkbox_cls(
                    v_model=("show_volume_layer", _volume_layer_enabled()),
                    label="|E| volume (3-D)",
                    hide_details=True,
                    style="padding: 2px 0;",
                )
            except Exception as exc:  # noqa: BLE001 - a toggle is never the page
                print(
                    f"[poc_app] volume layer toggle unavailable: {exc}",
                    file=sys.stderr,
                )
        # The substrate's opacity. A SLIDER and not a box: the slab is drawn over
        # the field it annotates, so how far it is seen THROUGH is a matter of
        # degree, and the operator is the one reading it. Probed and wrapped like
        # every sibling here: a build without VSlider loses the slider, not the
        # panel.
        try:
            slider_cls = getattr(widgets_module, "VSlider", None)
            if slider_cls is None:
                raise RuntimeError("this build has no VSlider")
            slider_cls(
                v_model=("substrate_opacity", VIS_SUBSTRATE_OPACITY),
                min=0.0,
                max=1.0,
                step=0.02,
                label="Substrate opacity",
                hide_details=True,
                style="padding: 2px 0;",
            )
        except Exception as exc:  # noqa: BLE001 - a slider is never the page
            print(
                f"[poc_app] substrate opacity slider unavailable: {exc}",
                file=sys.stderr,
            )
        # WHAT THIS GUARD GATES, and what it must NOT: the two MARKER boxes
        # only. The original guard asked ``cut_redraw`` and meant "a page with no
        # plane stack has no plane to hide" - true of the stack, FALSE of the |E|
        # volume page, whose marker discs are part of the volume layer and are
        # repainted by ``_show`` (``_redraw_for_plane_toggle``, :17274). On that
        # page the boxes existed in the scene with no way to switch them, which
        # is the regression this replaces. The predicate is shared with the
        # repaint so the two cannot disagree about what is hideable; a page with
        # neither a redraw nor a volume still gets nothing, because there the box
        # would hide nothing and the control would lie.
        if not _plane_toggles_available():
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

    # The still quality only reaches the browser if the view is CREATED with it
    # (a later assignment edits this process's copy, not the page), so every
    # plotter_ui call below - and the one the centre column resolves through
    # `ctx` - goes through this wrapper. With no --image-quality it is the
    # untouched plotter_ui.
    ui_with_image_knobs = _image_aware_plotter_ui(plotter_ui, image_quality)

    # WHICH VIEW the centre plotter is built as, decided HERE at LAYOUT time from
    # what the page was started with (see _local_view_enabled): --local-view, or
    # POC_LOCAL_VIEW, or neither. It is read ONCE and handed to the centre column
    # as a `local_view` handle below, so the panel builder carries neither
    # argparse nor os.environ - the same seam every other page fact uses
    # (plotter, state, info), and the reason a fake context can still build the
    # column.
    #
    # NAME: `render_local`, not `local_view`, so the parameter of that name stays
    # the thing the CALLER asked and this stays the ANSWER (flag or env) the page
    # is actually built with.
    render_local = _local_view_enabled(local_view)
    notice = _local_view_notice(render_local)
    if notice is not None:
        print(notice)

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
                # The mode the page was asked for, the same answer the centre
                # column gets: a host with no GL to render WITH is exactly the
                # case this degraded path exists for, so --local-view must not
                # go quiet here. add_menu stays False either way.
                view = ui_with_image_knobs(
                    plotter,
                    mode="client" if render_local else "server",
                    add_menu=False,
                )
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
                        ctx.register_handle("frame_max", _frame_max_for(info))
                        ctx.register_handle("plotter", plotter)
                        # Browser or server rendering for that plotter, resolved
                        # above from --local-view/POC_LOCAL_VIEW. A handle like
                        # the rest: the centre column reads it instead of
                        # reaching for the environment or the argument parser
                        # itself. ABSENT (a fake context, any caller that does
                        # not register it) the column keeps mode="server", so
                        # nothing that leaves it out changes.
                        ctx.register_handle("local_view", render_local)
                        # The PLAY SPEED the player bar offers: the values and the
                        # one the select starts on, as one handle the centre column
                        # may bind. A handle rather than a literal in the panel
                        # builder, because PLAY_RATES is the app's own viewing
                        # choice - the column must not carry a second copy of it
                        # that can drift from what the loop accepts.
                        ctx.register_handle(
                            "play_rate_options",
                            {
                                "items": _play_rate_items(PLAY_RATES),
                                "default": DEFAULT_PLAY_RATE,
                            },
                        )
                        # The speed control's widget class, resolved HERE and
                        # registered as a handle. VSelect is deliberately not in
                        # the probed ``widgets`` table (a Vuetify variant without
                        # it would cost the whole column), so the centre column
                        # cannot look it up there - and a build without it simply
                        # registers None, which is the column's signal to leave
                        # the control out.
                        ctx.register_handle(
                            "play_rate_select",
                            getattr(widgets_module, "VSelect", None)
                            if widgets_module is not None
                            else None,
                        )
                        ctx.register("html_div", html_div)
                        ctx.register("VRow", VRow)
                        ctx.register("plotter_ui", ui_with_image_knobs)
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
                                    "flex: 1 1 0; min-width: 0; "
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

    # The image knobs go on the trame VIEW (its real properties), and the renderer
    # report then names every knob beside what the GL stack actually answered.
    # The plotter is OFF-SCREEN and has not really drawn yet, so the GL strings
    # are not askable here - asking would take the process down on a box with no
    # GL driver (see _gl_capabilities) - and the line is deferred to the first
    # frame that really drew rather than guessed now.
    _image = _apply_image_knobs(view, image_encoding, image_quality)
    # Parked on ``handles`` for the renderer report: that line must name the SAME
    # image record and msaa request made here, and it runs from a tick closure
    # that never saw these locals.
    handles["renderer_image"] = _image
    handles["renderer_msaa"] = msaa
    _renderer_known = _renderer_report(plotter=plotter, image=_image, msaa=msaa)
    # The plotter is off-screen and NOTHING has drawn yet, so the GL strings are
    # not askable (see _gl_capabilities) and there is nothing honest to say about
    # them: the line is said by the first tick whose frame really drew, which is
    # where _renderer_report_after_render fires. Only a window that had ALREADY
    # drawn - it answered here, so nothing is left to add - is named now, once.
    if _renderer_known.get("gl_mode") != "unknown":
        handles["renderer_reported"] = True
        print(_renderer_report_line(_renderer_known))
        _renderer_warning = _renderer_software_warning(_renderer_known)
        if _renderer_warning:
            print(_renderer_warning)

    if nt is None or nt_x is None:
        # The shell: no timeline, so there is no rate and no stride to report.
        print(
            "[poc_app] no timeline on this page: it records no frame axis, so "
            "the player bar and its scrubber are not built"
        )
    else:
        print(
            f"[poc_app] animation: {nt} frames on ez_ycut, {nt_x} on each x-cut, "
            f"painted at most {paint_cap}/s and "
            f"{stride} position{'s' if stride != 1 else ''} per painted frame at the "
            f"default speed, rate {DEFAULT_PLAY_RATE} "
            f"(a VIEWING rate - see the sim time readout)"
        )
        # The speed select is anchored at rate 4, so a small --stride gives several
        # of its four settings the same number - say which, once, and start anyway.
        collision_notice = _stride_collision_notice(stride)
        if collision_notice:
            print(collision_notice)
        print(
            "[poc_app] each frame's sim time is rebuilt from its own plane's "
            f"frame index: the x-cuts are {_xcut_cadence_clause(info)}"
        )
    print(f"[poc_app] serving on http://{host}:{port}")
    print("[poc_app] open that URL in a browser; Ctrl-C to stop")
    # NO PORT CHECK HERE: the port was settled at the TOP of this function, before
    # the archive was read and every chart built. Reaching this line with the
    # port taken means another process won a race in between, and the bind error
    # is then the truthful report - there is nothing to say here that the
    # pre-flight line did not already say, minus the work it saved.
    server.start(host=host, port=port, open_browser=False)
    return 0


def main(argv=None) -> int:
    # The registry is read BEFORE the parser is built: the boot default is an
    # answer about this checkout (see _boot_structure_id), so the help text
    # names the entry a bare run would actually open, and the answer is
    # computed once rather than once for the help and once for the selection.
    structures = load_structures()
    boot_structure, boot_note = _boot_structure_id(structures)
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
            "  PYTHONPATH=. python3 server/poc_app.py --list-keys\n"
            "  PYTHONPATH=. python3 server/poc_app.py --host 0.0.0.0 --port 8080 --station 4\n"
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
        default=None,
        help=(
            f"structure id from {STRUCTURES_FILE} (default: {boot_structure})"
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
    parser.add_argument(
        "--stride",
        type=int,
        default=DEFAULT_PLAY_STRIDE,
        help=(
            "positions ONE PAINTED frame advances at the default speed, rate 4 "
            f"(default: {DEFAULT_PLAY_STRIDE}); the speed select scales it from "
            "there - rate 8 doubles it, rate 1 divides it by four and floors at "
            "one whole position - and 4 reproduces the historical 4 positions/tick"
        ),
    )
    parser.add_argument(
        "--paint-fps",
        dest="paint_fps",
        type=int,
        default=None,
        help=(
            "ceiling on PAINTED frames per second, i.e. on how often the "
            "animation asks trame for a still (default: the same as --fps, "
            "one repaint per animation tick); a skipped paint advances nothing"
        ),
    )
    parser.add_argument(
        "--msaa",
        type=int,
        default=_env_int("POC_MSAA"),
        help=(
            "MSAA samples for the off-screen plotter (default: pyvista's own, "
            "unchanged); POC_MSAA does the same without the flag, and the boot "
            "report line quotes requested vs applied"
        ),
    )
    parser.add_argument(
        "--image-encoding",
        dest="image_encoding",
        choices=_IMAGE_ENCODINGS,
        default=_env_text("POC_IMAGE_ENCODING"),
        help=(
            "encoding the browser is sent for each frame (default: the trame "
            "transport's own jpeg); POC_IMAGE_ENCODING does the same without "
            "the flag - the transport is jpeg-only, so a png request is "
            "recorded and reported as NOT applied"
        ),
    )
    parser.add_argument(
        "--image-quality",
        dest="image_quality",
        type=int,
        default=_env_int("POC_IMAGE_QUALITY"),
        help=(
            "quality 1..100 for the trame view's still and interactive renders "
            "(default: the view's own, unchanged); POC_IMAGE_QUALITY does the "
            "same without the flag"
        ),
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        dest="profile",
        help=(
            "record the --profile measurement suite (per-tick JSONL, loop-lag "
            "and stack samples, a summary) into --profile-dir; POC_PROFILE=1 "
            "or POC_TIMING=1 does the same without the flag"
        ),
    )
    parser.add_argument(
        "--profile-dir",
        dest="profile_dir",
        metavar="PATH",
        default=None,
        help=(
            "directory for the --profile artefacts (default: "
            f"{_PROFILE_DEFAULT_DIR})"
        ),
    )
    parser.add_argument(
        "--local-view",
        action="store_true",
        dest="local_view",
        help=(
            "render the centre plotter in the BROWSER (trame PyVistaLocalView) "
            "instead of on the server; POC_LOCAL_VIEW=1 does the same without "
            "the flag."
        ),
    )
    args = parser.parse_args(argv)
    # The pump's two knobs are INTS with a meaning, not free numbers: a stride of 0
    # would freeze the picture on its first painted frame and a paint cap of 0 would
    # divide by zero in the loop's modulus. Refused here, where the operator can read
    # which flag said what, instead of being floored into something they did not ask
    # for (a --stride 0 silently playing at 1 is the same class of lie as a caption
    # that does not match the picture).
    if args.stride < 1:
        parser.error("--stride must be at least 1 position per painted frame")
    if args.paint_fps is not None and args.paint_fps < 1:
        parser.error("--paint-fps must be at least 1 frame per second")
    # ONE rule for both routes: a flag and its POC_* variable end up in the same
    # three numbers, and a value VTK or the transport would ignore is a usage
    # error rather than a knob that silently did nothing.
    knobs = _display_knobs_or_exit(parser, args)
    # Recorded whatever the profile suite is doing: the knobs are a fact about
    # the run, and a summary written later must not have to guess them.
    _profile_knobs(
        fps=args.fps,
        msaa=knobs["msaa"],
        image_encoding=knobs["image_encoding"],
        image_quality=knobs["image_quality"],
    )
    if getattr(args, "profile", False) or _profile_env_enabled():
        # ONE switch for the whole suite; --profile-dir only says where it lands.
        # POC_TIMING is accepted as an alias so a run already started with it
        # gets the profile artefacts too, instead of needing a second variable.
        _profile_configure(
            True,
            getattr(args, "profile_dir", None),
            start_threads=True,
            register_exit=True,
        )
    # OUTSIDE the if above, because the pump's knowledge of delivery is NOT
    # telemetry: ``_delivery_animating()`` has to answer with the suite off too, or a
    # plain run keeps advancing positions into stills trame discards while a profiled
    # run does not - two different animations behind one flag. The delivery instance
    # does not exist yet (trame builds it in server.start()), so the CLASS is wrapped
    # here and every later instance inherits the counters AND remembers itself.
    # False is not an error: the summary says available=no rather than reporting five
    # zeros as a measured idle.
    _profile_hook_delivery()
    if args.structure is None:
        # The ONE place the boot default is chosen, so an explicit --structure
        # never gets a sentence about a default it did not use.
        args.structure = boot_structure
        if boot_note:
            print(boot_note, file=sys.stderr)

    structure = _structure_by_id(args.structure, structures)
    if structure is None:
        valid = ", ".join(
            str(entry.get("id")) for entry in structures if entry.get("id")
        )
        parser.error(
            f"unknown --structure {args.structure}; "
            f"valid ids: {valid or 'none (structures.json unreadable)'}"
        )

    # A record-only entry has NO field dump: its S-parameters were recorded
    # without a field solve, and the only field data on disk belongs to a
    # different case, so nothing of another structure's may be substituted for
    # it. What it does have is a board - the mesh builder describes it, and the
    # record describes it when the record carries one - so the entry opens the
    # BOARD page instead of failing: no dump, no timeline, no solve. This is the
    # default for such an entry rather than a flag, because an entry the viewer
    # cannot open at all is what the flag existed to work around. The check is on
    # the resolved entry, so it covers --structure OMITTED as well as given.
    if _structure_is_record_only(structure):
        # The two dump-reading exits below have no board to describe, so asking
        # for one of them here is a usage error rather than a chosen one.
        if args.list_keys or args.dump_state:
            parser.error(_record_only_refusal(args.structure, structures))
        bare_page = _bare_board_page(structure, structure_id=args.structure)
        return run_web_vis(
            bare_page["info"],
            args.host,
            args.port,
            args.fps,
            structure,
            structures,
            surface_dump=(
                _resolve(args.surface_dump) if args.surface_dump else None
            ),
            loaded_page=bare_page,
            stride=args.stride,
            paint_fps=args.paint_fps,
            msaa=knobs["msaa"],
            image_encoding=knobs["image_encoding"],
            image_quality=knobs["image_quality"],
            local_view=args.local_view,
        )

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
        stride=args.stride,
        paint_fps=args.paint_fps,
        msaa=knobs["msaa"],
        image_encoding=knobs["image_encoding"],
        image_quality=knobs["image_quality"],
        local_view=args.local_view,
    )


if __name__ == "__main__":
    sys.exit(main())
