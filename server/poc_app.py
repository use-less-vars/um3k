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
import datetime
import errno
import json
import re
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
# The structure registry: which artefacts belong to which physical case, and
# which cell counts each of them is on. Read from the repo root. Every entry
# point below defaults to the entry named here.
DEFAULT_STRUCTURE = "build_A_50ohm"
STRUCTURES_FILE = "structures.json"
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


def load_multifreq(npz_path: Path):
    """Read the multi-frequency |S11| / |S21| sweep beside the dump.

    Returns ``{"path", "points", "skipped", ...}`` or None; ``points`` are dicts
    with keys ``f_ghz``, ``s11``, ``s21``, ``artefact``, ``k``,
    ``beta_ambiguous``, ``beta``, ``beta_model``, sorted by frequency and
    otherwise as recorded. Nothing here interpolates, smooths or re-orders into a
    curve: a
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


def build_frequency_chart(mf: dict, title: str | None = None) -> dict:
    """Render |S11| and |S21| vs frequency to a PNG data URI.

    Returns ``{"image": data_uri | None, "rows": [...], "reason": str | None}``.
    matplotlib is a project dependency, but it is imported HERE, lazily and
    guarded: the numpy-only paths (--help, --list-keys) must never need it, and
    a missing or broken matplotlib has to cost the picture, not the page - the
    caller falls back to the text rows.

    Markers only, no connecting line: a line between two recorded bins is a
    claim about the frequencies between them, and no run covers those. Bins whose
    dispersion branch is unresolved get their own open marker and one note - they
    stay discrete points at their recorded frequency, they are not smoothed or
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

    definite = [point for point in mf["points"] if not point.get("beta_ambiguous")]
    ambiguous = [point for point in mf["points"] if point.get("beta_ambiguous")]
    try:
        fig, ax = plt.subplots(figsize=(5.4, 1.9), dpi=110)
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
_PORT_FIELDS = ("v_re", "v_im", "i_re", "i_im")
STATE_SCHEMA = "emfit.poc-state/1"
RESIDUAL_BASIS = "50/(50 + 2*z0)"
# Why two extents and not one: the domain box is what was SOLVED, the sampled
# span is what the npz STORES, and on x they are nx cells versus the n_stations
# captured planes. The basis string ships with the numbers so a reader never has
# to guess which of the two a millimetre figure came from.
EXTENT_BASIS = (
    "domain_mm = nx*cell (the simulated box); sampled_mm = the span of the "
    "field samples actually stored in the npz (9 planes of 0.4 mm = 3.6 mm "
    "here)"
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


def _multifreq_path(npz_path: Path, structure):
    """The sweep file for this page: the entry's, else the one beside the dump."""
    declared = _structure_artifact_path(structure, "multifreq")
    if declared is not None:
        return declared
    for candidate in _multifreq_candidates(npz_path):
        if candidate.is_file():
            return candidate
    return None


def _field_dump_block(info: dict, path: Path) -> dict:
    """The field-dump half: cells from the ARRAY SHAPE, never from a record.

    TWO extents, deliberately kept apart. ``extent_domain_mm`` is the simulated
    box, nx cells across. ``extent_sampled_mm`` is the span of the samples the
    npz actually stores - and on x that is the n_stations captured planes, not
    nx. One number called "extent" cannot say which of the two it means, and
    here they differ by a factor of seven (24.8 mm vs 3.6 mm): reading the
    domain box as "the field I have" is the misreading this split exists to
    make impossible. ``extent_basis`` says it in words as well.

    The two extents therefore come from two different places, and the counts
    behind them are named for where they were read: nx/ny/nz are the DOMAIN
    cells the record declares, while the sampled span is the STORED array's own
    shape. Those do not agree on every axis - the stored plane is 9 x 213 x 22
    inside a 62 x 212 x 22 box, one row more in y than the box has cells - so
    borrowing the domain count for the sampled y would report 84.8 mm for an
    array that spans 85.2 mm.
    """
    plane = info[PLANE_KEY]
    nx_domain, ny_domain, nz_domain = int(info["nx"]), int(info["ny"]), int(info["nz"])
    cell_m = float(info["cell_m"])
    cell_mm = cell_m * 1e3
    n_stations_sampled, ny_sampled, nz_sampled = (int(n) for n in plane.shape)
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
            "x": round(n_stations_sampled * cell_mm, 9),
            "y": round(ny_sampled * cell_mm, 9),
            "z": round(nz_sampled * cell_mm, 9),
        },
        "extent_basis": EXTENT_BASIS,
        "stations_x_mm": [idx * cell_mm for idx in range(n_stations_sampled)],
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


def build_state_dump(info: dict, structure, structures=None) -> dict:
    """The whole page state as one JSON document, numpy-only.

    A report, not a picture: it lists the artefacts this page would composite, the
    cell count each one is on, and the seam between them. Anything unparseable is
    null - a state dump that invents a number to look complete is the defect this
    document exists to expose.
    """
    path = Path(info["path"])
    entry = structure if isinstance(structure, dict) else {}
    field_block = _field_dump_block(info, path)
    sparams_path = _sparams_path(path, entry)
    sparams = _sparams_block(sparams_path)
    record = _field_record(path)
    field_text = _cells_as_text(field_block["cells"])
    sparams_text = _cells_as_text(sparams["cells"])
    mismatch = _mismatch_block(
        field_text, sparams_text, _n_line(record), sparams["n_line"]
    )
    multifreq = _multifreq_block(_multifreq_path(path, entry))
    port_waves, port_reason = _port_waves_block(sparams_path)
    return {
        "schema": STATE_SCHEMA,
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
    }


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
    state.station = int(station)
    state.station_label = _station_text(int(station), cell_mm, n_st)
    structure_id = structure.get("id") if isinstance(structure, dict) else None
    structure_options = _structure_options(structures)
    state.structure = structure_id
    state.structure_note = f"showing {structure_label}"

    # Plane positions come from the record beside the dump, so the markers and
    # the labels below cannot drift from the geometry that produced the numbers.
    record = load_record(info["path"])
    planes = _plane_layout(info, record)

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
    cut_layout = _cut_layout(info, n_j // 2, n_k // 2)
    state.cut_y = cut_layout["j"]
    state.cut_z = cut_layout["k"]
    state.cut_label = _cut_text(cut_layout)
    state.view_mode = "volume"
    state.view_label = _view_label(
        state.view_mode, planes, toggle_available, cut_layout
    )
    # The dump's own single frequency, printed beside the view toggle so the
    # number can only be read as belonging to the 3-D field on screen - never to
    # the sweep panel below, which is a different artefact.
    dump_f_ghz = _own_frequency_ghz(record)
    state.dump_freq_label = (
        f"Current 3D dump frequency: {dump_f_ghz:.4f} GHz"
        if dump_f_ghz is not None
        else "Current 3D dump frequency: not recorded beside the dump"
    )

    # The multi-frequency sweep, if one was written beside the dump. Optional
    # at every step: no file, no matplotlib, an unusable row - the 3-D view
    # still comes up, and the caption says what is missing rather than going
    # quiet.
    multifreq = load_multifreq(info["path"])
    frequency_panel = (
        None
        if multifreq is None
        else build_frequency_chart(multifreq, _chart_title(structure))
    )
    if multifreq is None:
        frequency_caption = (
            "no multi-frequency |S11|/|S21| sweep on disk yet: looked for "
            "*multifreq*summary*.json beside "
            f"{info['path']} and at {DEFAULT_MULTIFREQ}"
        )
    else:
        frequency_caption = _frequency_caption(multifreq, record)
    # The recorded station phasors. No matplotlib costs the picture and prints the
    # rows instead - build_port_wave_chart returns its rows and the reason rather
    # than raising, so the 3-D view and the caption still come up.
    port_wave_chart = (
        None if port_waves is None else build_port_wave_chart(port_waves)
    )
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
                items=structure_options,
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
                with container(fluid=True, classes="pa-0 fill-height"):
                    with html_div(
                        style=(
                            "display: flex; flex-direction: column; "
                            "height: 100%; width: 100%; overflow: hidden;"
                        )
                    ):
                        _emit_mismatch_banner()
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
                        # The two panels share one scroll box: each is a fixed
                        # height image while the plotter keeps its min-height, and
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
    info = load_dump(src)

    if args.dump_state:
        out = _resolve(args.dump_state)
        state = build_state_dump(info, structure, structures)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print(f"[poc_app] wrote {out}")
        return 0

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

    return run_web(info, args.host, args.port, station, structure, structures)


if __name__ == "__main__":
    sys.exit(main())
