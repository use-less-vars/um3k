#!/usr/bin/env python3
"""Run A of the absorbing-termination build: ONE graded run, ONE load, no reference.

What this run is
----------------
Source at port ``p1`` (the study's own soft source plane, ``ix_port``), a 50 ohm
``series_r`` :class:`emfit.board.Load` at port ``p2`` (the far end of the line),
extraction on the load's own cut plane via ``s21_plane="cut"``.  One run.  There
is deliberately **no reference run** -- unless ``--with-twin`` is passed, which
supplies one from a load-free twin of the same mesh (off by default; see
"Load-free twin" below).  With ``reference=None`` the cut branch does not raise,
it degrades to ``zc_split = zc`` + ``line_s21(...)`` and sets
``loaded_without_reference=True`` on the result.  That degradation is recorded in
the artefact rather than hidden, because it is the difference between a
measured line constant and an assumed one.

One-shot by construction
------------------------
This script is written to be typed once.  An FDTD run interrupted mid-integration
cannot be resumed, only repeated, so the resource trip below is *hard*: it kills
the process at the limit and leaves a ``.trip.json`` marker instead of a result.
There is no retry loop anywhere in this file, and a trip is not to be silently
re-launched -- a second attempt is a new decision, not a resumption.

The trip clause is RE-IMPLEMENTED here, not inherited.  ``tools/host_ladder.py``
owns the frozen ``--mem-ceiling-mb`` machinery, its RU_MAXRSS reading and its
JSON payload shape, but that file is out of the fence for this dispatch and is not
touched.  The thresholds below are copied from it deliberately, so a number
cannot drift while the machinery differs.

Usage (the one command to type, from the repository root):

    python3 evidence/termination/run_build_A.py

Dry run (builds the arguments, writes nothing, starts no FDTD):

    python3 evidence/termination/run_build_A.py --dry-run

Load-free twin, opt-in (``--with-twin``, off by default)
-------------------------------------------------------
``--with-twin`` adds ONE extra FDTD run of the same line with the load taken
out -- the ``loads`` key dropped rather than passed empty, ``s21_plane`` left
``None`` because a load-free record has no cut plane to name -- and hands that
run's travelling-wave fit to the loaded run as an
``emfit.studies.LineReference`` (``LineReference.from_wave(twin)``).  The loaded
``s21`` is then the load's own transmission instead of this run's de-embedding
residual, and ``loaded_without_reference`` comes back False from the library.
Same script, same mesh, same source: only the load and the extraction plane
differ, which is what lets the reference cancel a shared error instead of
assuming one away.

Two consequences, neither optional:

* the wall cost roughly DOUBLES (two solves, not one).  The trip is armed once,
  before the twin, and its ``--wall-limit-s`` budget is the whole PROCESS -- it
  is not re-armed for the second solve, so a two-run wall time has to fit in
  it, and the RSS high-water mark it watches is the process's;
* the twin's own record is written beside the artefact as ``<stem>_twin.json``:
  a first-class run record, not a debug dump.

Without the flag no second solve runs and the artefact is exactly what it was.

**What the reference can normalise, and what it cannot.**  The twin's fit is a
``LineReference`` over its own first and last probe station, and the loaded run
extracts on ``s21_plane="cut"`` -- the load's own plane, which is not a probe
station -- so the reference is asked to normalise a run measured on a different
span than the one its ratio was measured on.  ``forward_ratio`` no longer
refuses that: it treats the ratio as a *residual* (the ``a+`` fit has already
divided out ``exp(gamma x)``, so a perfect reference gives 1) and returns it
raised to ``run_span / station_span``, which is the only rescaling that
composes -- two hops must equal one -- and which returns the measured ratio bit
for bit on the station planes themselves, the exponent being 1.  Two things
follow for anyone reading a twin artefact: the residual is an error *measured*
over the station span (9.6 mm on the smoke), and the number applied at the
load plane is that error raised to the span ratio, not an error measured
there -- **1.75** on runs A and B, whose load sits 16.8 mm from the port, and
about **2.79** on run E, whose load sits at 30 mm and so 26.8 mm from it; and
a plane pair equal to the stations is the pass-through case, so it is worth
recording which pair a run used.  ``build_smoke_50ohm_twin.json`` carries the
twin half of exactly that (``line.station_span_m``, ``s21.planes_m``).  The
transport's near miss, and why it is not ``exp(-gamma * dL)``, is DR-16 in
``docs/design/defect_register.md``.

Three runs, one code shape
--------------------------
Length and load value are flags, not code paths: ``--n-line`` sets the line
(54 -> 62 columns, Run A; 79 -> 87 columns, Run E), ``--load-at-mm`` sets the
load's position (and therefore ``dL`` between two runs), ``--load-ohm`` sets
the termination (50 ohm graded; 100 ohm = the exploratory arm of scope L520
Ruling 3, a band check and not an acceptance criterion).  Nothing else about
the arithmetic changes, which is what makes the two lengths in AC-7
a comparison of lengths rather than of scripts.  The paste-ready invocations
are in ``evidence/termination/README.md``; the artefacts are graded by
``evidence/termination/grade_2b.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT_DEFAULT = REPO / "evidence" / "termination" / "build_A_50ohm.json"
TRIP_SUFFIX = ".trip.json"

# --- the trip clause, re-implemented (see module docstring) -------------------
# Both numbers are the frozen ones, quoted, not re-derived.
#   * memory: ``tools/host_ladder.py:1160`` default ``--mem-ceiling-mb 2000.0``
#     [M], and the dispatch's own explicit ``--mem-ceiling-mb 2000``.
#   * wall: the per-run 1400 s gate that
#     ``docs/design/termination_build_plan.md:48-52`` prices both frozen rows
#     against [L].
WALL_LIMIT_S_DEFAULT = 1400.0
MEM_CEILING_MB_DEFAULT = 2000.0
RSS_POLL_S = 0.5

# --- the run, as named by the dispatch ---------------------------------------
# The code shape is fixed: line length and load value are FLAGS (--n-line,
# --load-ohm), never a second copy of this script.  The names below are what the
# flags fall back to, so Run A is exactly what was graded.
LABEL = "A"
LOAD_VALUE_OHM = 50.0
LOAD_KIND = "series_r"
S21_PLANE = "cut"
N_LINE_DEFAULT = 54

# Series-R anchor for the s11 prose below: the twin reference's zc, prose only,
# never passed to a solver, fit or verdict.
Z0_SERIES_ANCHOR = 47.53661998575833


def rss_mb() -> float:
    """Peak RSS of this process [MB].

    Same basis as the frozen rows: ``resource.getrusage(RUSAGE_SELF).ru_maxrss``,
    a process-wide high-water mark, which on Linux is KiB and is divided by 1024
    (``evidence/h_refine/h040.json`` key ``meta.rss_basis`` [M]).
    """
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def cgroup_limit_mb() -> float | None:
    """The container's memory ceiling [MB], or ``None`` when unlimited/unknown."""
    for path in ("/sys/fs/cgroup/memory.max",
                 "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(path, "r", encoding="ascii") as fh:
                raw = fh.read().strip()
        except OSError:
            continue
        if not raw or raw == "max":
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        if value <= 0 or value > (1 << 50):
            return None
        return value / (1024.0 * 1024.0)
    return None


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def finite_or_none(value):
    """``float(value)``, or ``None`` for a non-finite number.

    ``write_json`` dumps with ``json.dumps``'s default ``allow_nan=True``, so a
    nan that reached it would be written as the bare literal ``NaN``, which no
    strict parser accepts.  A field that is legitimately nan -- ``s11_at_plane``
    on a record extracted over the station span -- is converted here instead.
    """
    import math

    value = float(value)
    return value if math.isfinite(value) else None


def load_records(entries):
    """``geometry["loads"]`` as plain JSON records, ``[]`` when there are none.

    ``emfit.studies`` builds these as ``{kind, value, x, column, n_edges}``
    (``emfit/studies.py:2744-2746``) and hangs them on the geometry whenever a
    load was actually placed.  The scalar filter at each writer below drops a
    tuple of dicts, so without this a loaded record would serialise exactly like
    a load-free one.  ``[]`` and not a missing key: a reader can then say which
    of the two it is holding without knowing the writer.
    """
    return [{"kind": str(entry["kind"]),
             "value": float(entry["value"]),
             "x": float(entry["x"]),
             "column": int(entry["column"]),
             "n_edges": int(entry["n_edges"])}
            for entry in (entries or ())]


class Trip:
    """Hard resource trip: kills the process, leaves a marker, never retries.

    Exit codes: 3 = memory ceiling, 4 = wall ceiling.  A marker file is written
    *before* the process dies, so a trip is visible even when the interpreter is
    not given a chance to unwind.
    """

    def __init__(self, out_path: Path, *, mem_ceiling_mb: float,
                 wall_limit_s: float, argv: list[str], started_utc: str):
        self.out_path = out_path
        self.mem_ceiling_mb = float(mem_ceiling_mb)
        self.wall_limit_s = float(wall_limit_s)
        self.argv = list(argv)
        self.started_utc = started_utc
        self.t0 = time.monotonic()
        self.peak_mb = rss_mb()
        self.tripped = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._watch, name="trip",
                                        daemon=True)

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def _watch(self) -> None:
        while not self._stop.wait(RSS_POLL_S):
            rss = rss_mb()
            if rss > self.peak_mb:
                self.peak_mb = rss
            if self.peak_mb > self.mem_ceiling_mb:
                self._fire("memory", 3,
                           f"peak RSS {self.peak_mb:.1f} MB exceeded "
                           f"--mem-ceiling-mb {self.mem_ceiling_mb:.1f} MB")
            if self.elapsed() > self.wall_limit_s:
                self._fire("wall", 4,
                           f"wall {self.elapsed():.1f} s exceeded "
                           f"--wall-limit-s {self.wall_limit_s:.1f} s")

    def _fire(self, kind: str, code: int, reason: str) -> None:
        self.tripped = True
        marker = self.out_path.with_name(self.out_path.stem + TRIP_SUFFIX)
        write_json(marker, {
            "schema_version": 1,
            "label": LABEL,
            "status": "trip",
            "trip_kind": kind,
            "reason": reason,
            "exit_code": code,
            "one_shot": ("A trip is NOT a licence to relaunch: this run is "
                         "one-shot, and a second attempt is a new decision."),
            "mem_ceiling_mb": self.mem_ceiling_mb,
            "wall_limit_s": self.wall_limit_s,
            "peak_rss_mb": self.peak_mb,
            "elapsed_s": self.elapsed(),
            "started_utc": self.started_utc,
            "argv": self.argv,
            "result_written": False,
        })
        sys.stderr.write(f"\nTRIP ({kind}): {reason}\n"
                         f"marker: {marker}\n")
        sys.stderr.flush()
        sys.stdout.flush()
        os._exit(code)

    def start(self) -> "Trip":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()


def check_mesh(kwargs: dict) -> None:
    """Fail closed in a millisecond if the mesh cannot be built.

    ``emfit/studies.py:2555-2562`` remains the authority: it raises on a negative
    ``n_top`` and on a non-zero ``n_top`` that differs from ``n_pml``.  This guard
    reproduces that one inequality and nothing else, for one reason -- the runs
    this script launches died inside the first second of a 1400 s wall gate on
    exactly it, and a ValueError raised after the process, the trip thread and
    the artefact header are up is a worse way to learn it than a refusal to
    start.  If the two ever disagree, the solver is right and this is wrong.
    """
    n_top, n_pml = int(kwargs["n_top"]), int(kwargs["n_pml"])
    if n_top < 0:
        raise SystemExit(
            f"REFUSED: n_top={n_top} is negative. "
            f"emfit/studies.py:2555 raises on this; nothing here can fix it.")
    if n_top and n_top != n_pml:
        raise SystemExit(
            f"REFUSED: n_top={n_top} does not match n_pml={n_pml}: one PML "
            f"object carries ONE thickness for every wall it opens "
            f"(emfit/studies.py:2557).  Pass n_top={n_pml} for the matched lid "
            f"the validated reference run used "
            f"(evidence/board_poc/A_microstrip.json, values.npml 6, mesh "
            f"62 x 44 x 22), or n_top=0 for a plain PEC lid -- which no "
            f"artefact in this repo records.")


def build_kwargs(args: argparse.Namespace) -> dict:
    """The one call's arguments, assembled in one place so nothing is retyped.

    The mesh is the h = 0.4 mm *cell* configuration: substrate 1.6 mm / ``n_sub``
    4 = 0.4 mm cell, ``n_air`` 12, ``n_top`` 6, ``n_clean`` 96, ``n_pml`` 6,
    ``n_ref`` 2, and ``n_line`` taken from ``--n-line``.  ``n_strip`` is NOT
    passed: it falls to the library default ``MS_N_STRIP`` 8
    (``emfit/studies.py:1195-1196``), which is 8 x 0.4 mm = 3.2 mm = ``MS_W`` --
    the strip the closed-form reference in ``emfit/microstrip.py`` actually
    describes, and the width the artefact records as ``geometry.w``.  This file
    used to pass ``n_strip`` 2 (0.8 mm) while ``w`` stayed ``MS_W`` 3.2 mm, so the
    mesh was 4x narrower than the strip the phase reference is computed for: a
    disagreement only the AC-7 comparison could see, because ``w`` sizes nothing
    in the grid (``emfit/studies.py:3129-3130`` vs the strip loop at
    ``emfit/studies.py:2595-2600``).  ``emfit/studies.py:2582`` now raises on that
    disagreement rather than meshing one strip and quoting another.

    ``n_top`` is 6, and it is 6 *because* ``n_pml`` is 6: the zmax face is a
    matched layer, not a lid, and one PML object carries one thickness for every
    wall it opens (``emfit/studies.py:2555-2562``; ``MS_N_TOP`` and its comment
    at ``emfit/studies.py:1190-1194``).  The 12 this file used to carry came from
    ``evidence/h_refine/h040.json`` ``rungs[0].n_top``, i.e. from the same
    borrowing as the 68 x 218 grid below: that row's ``npml`` is *also* 12,
    because its PML is 4.8 mm at a 0.4 mm cell (``rungs[0].pml_mm`` 4.8).  Ours
    is 6, so the lid has to be 6; the mismatch is not silently clipped, it is a
    ValueError thrown when the grid is built, i.e. after the process has started.
    Nothing about the reference changes: the validated microstrip run
    (``evidence/board_poc/A_microstrip.json``, ``values.npml`` 6, mesh
    "62 x 44 x 22 cells at 0.4000 mm" = ``n_sub`` 4 + ``n_air`` 12 + ``n_top`` 6
    through z) has a 6-cell lid on 6-cell laterals, and every row of
    ``evidence/box_sweep/`` records ``n_top`` 6 against ``npml`` 6.  ``n_top`` 0
    (a plain PEC lid) is admissible but is not what was measured: no artefact in
    this repo records it.

    PRICE, corrected 2026-11-01 (``n_top`` 12 -> 6 shortened z from 28 to 22
    cells and ``n_strip`` 2 -> 8 widened y from 206 to 212, so the earlier
    357,616 read 23.7 % high): at the default ``n_line`` 54 the grid is
    **62 x 212 x 22 = 289,168 cells** (``nx = n_pml + n_ref + n_line = 6+2+54``;
    ``ny = 2*n_pml + n_strip + 2*n_clean = 12+8+192``; ``nz = n_sub + n_air +
    n_top = 4+12+6``; ``ix_port = n_pml + n_ref = 8``), dt
    7.626299478123987e-13 s (set by the 0.4 mm cell, so neither the z nor the y
    extent moves it), 2400 steps, 1.830 ns simulated.  Run E (``n_line`` 79) is
    87 x 212 x 22 = 405,768 cells.  Both are +2.91 % on the 206-wide grid the
    ``n_strip`` 2 revision priced and ran (280,984 and 394,284 cells, the figures
    the artefacts and ``README.md`` record), so cell count is not the reason to
    re-measure.  An earlier revision of this file said 68 x 218 x 28 = 415,072
    cells, borrowed from ``evidence/h_refine/h040.json`` [M]: that grid belongs
    to the eigensolver ladder row and is WRONG here.

    Cost, and it is a MEASUREMENT, not a floor: the runs of this build are
    recorded, and each artefact carries its own ``peak_rss_mb`` and
    ``wall_total_s`` [M] -- Run A 297.82 MB / 38.76 s
    (``build_A_50ohm.json``), Run B 297.46 MB / 40.65 s (``build_B_100ohm.json``),
    Run E 380.99 MB / 52.20 s (``build_E_50ohm.json``).  Against the per-run
    1400 s wall gate that is 2.8 % on Run A and 3.7 % on Run E; against the
    ``--mem-ceiling-mb 2000`` trip both runs are launched under, it is 14.9 % and
    19.0 %.
    A trip writes a ``.trip.json`` marker and exits 3 or 4, and a trip is not a
    licence to relaunch.  The floor this paragraph used to quote -- the six field
    components alone, ``6 x 8 B x cells`` = 13.5 MB on Run A (6 x 8 x 280,984 =
    13,487,232 B) and 18.9 MB on Run E (6 x 8 x 394,284 = 18,925,632 B) -- is
    what the measured RSS contains on top of the materials matrices, the edge
    lists and interpreter overhead; it is retained only as the reason the
    measured figure is ~20x it.  CAVEAT, and it matters because the mesh above
    changed after those numbers were taken: every figure in this paragraph was
    measured on the ``n_strip`` 2 mesh, i.e. 206 cells wide, 280,984 cells (Run A)
    and 394,284 (Run E).  The corrected grid is 212 wide, 289,168 and 405,768
    cells (+2.91 %), and no run of this script has been recorded on it, so the
    recorded RSS and wall times are a LOWER BOUND for the corrected grid rather
    than a measurement of it.

    The load adds no cell, no column and no solver state: it is a conductance on
    edges that already exist.  The grid is therefore recorded as ACHIEVED in the
    artefact (``geometry.grid`` / ``geometry.cells``) and not asserted here -- a
    price that is only quoted is a price nobody checked.
    """
    from emfit.board import Load

    load = Load(args.load_at_mm * 1e-3, LOAD_KIND, float(args.load_ohm))
    kwargs = {
        "h": 1.6e-3,
        "n_sub": 4,
        "n_air": 12,
        "n_top": 6,
        "n_clean": 96,
        "n_line": int(args.n_line),
        "n_pml": 6,
        "nsteps": 2400,
        "loads": (load,),
        "reference": None,
        # Absent flag => S21_PLANE, i.e. the load's own cut, byte for byte what
        # this dict has always carried.  --s21-plane-index N moves the far
        # extraction probe onto node column N (downstream only; the library
        # refuses an upstream index) for a plane-convergence sweep.
        "s21_plane": (S21_PLANE if args.s21_plane_index is None
                      else int(args.s21_plane_index)),
        "excite": "cw",
        "launch": args.launch,
        "flux_projection": bool(args.flux_projection),
    }
    if args.s21_plane_index is None and kwargs["loads"]:
        # DEFAULT PLANE POLICY.  With the flag absent the probe is S21_PLANE
        # ("cut"), which the library reads as the LOAD's own node column -- a
        # plane sitting on the lumped element and reading its near field: the
        # recorded Run A artefacts give |s21| 1.106-1.134 on that column and
        # 0.760-0.807 one column downstream, same mesh, ratio 1.45-1.49.  The
        # default is therefore one column DOWNSTREAM of the load's own column:
        # still fixed by the load's position alone, still the first plane the
        # element is behind, and no longer on it.  The column is re-derived
        # here exactly as emfit/studies.py:2727 places the load,
        #     ix_load = int(floor(position / cell + 0.5)),   cell = h / n_sub,
        # so the default follows a change of mesh or of load position instead
        # of being a number typed twice.  The payload records
        # plane_from_default_policy=True beside the requested plane, so a
        # column chosen here is never read as one chosen by hand.  No load in
        # the kwargs (the load-free twin) keeps "cut" and the station span.
        import math

        cell_m = float(kwargs["h"]) / float(kwargs["n_sub"])
        ix_load = int(math.floor(float(kwargs["loads"][0].position)
                                 / cell_m + 0.5))
        kwargs["s21_plane"] = ix_load + 1
    check_mesh(kwargs)
    return kwargs


def twin_kwargs_from(kwargs: dict) -> dict:
    """The load-free twin's arguments: the loaded call with the load taken out.

    Exactly three keys move, each for a stated reason:

    * ``loads`` is **dropped**, not set to ``()``.  The twin is a line with no
      load in it, and ``emfit/studies.py:3229`` reads ``bool(loads_used)`` --
      the absence is the measurement, so the key goes rather than being passed
      as an empty list that still says "a record that carries loads".
    * ``s21_plane`` is ``None``, because ``emfit/studies.py:2692-2697`` refuses
      a named plane on a load-free record ("there is no cut for it to name").
      ``None`` is the station span, the only plane a load-free line has, and it
      is the reference's own span.
    * ``reference`` is ``None``: the twin is where the reference comes from, and
      a reference cannot be normalised against itself.

    Nothing else changes.  ``h``, ``n_sub``, ``n_air``, ``n_top``, ``n_clean``,
    ``n_line``, ``n_pml``, ``nsteps`` and ``excite`` are the loaded run's own
    values, so the two runs are one mesh with one source and the only
    difference between them is the load being measured.

    Args:
        kwargs: The loaded run's arguments, as :func:`build_kwargs` built them.

    Returns:
        A new dict; ``kwargs`` itself is not modified.
    """
    twin = dict(kwargs)
    twin.pop("loads", None)
    twin["s21_plane"] = None
    twin["reference"] = None
    return twin


def describe_reference(reference) -> dict | None:
    """JSON-safe view of the ``LineReference`` a loaded run was given.

    ``None`` in, ``None`` out: the default path passes ``reference=None`` and
    the artefact records that as it always has, so a flag-off artefact does not
    change.  When a reference is there, this says which object it is, who built
    it, and the numbers it carries -- enough to identify the twin a loaded
    result was normalised against without re-reading that twin's file.
    """
    if reference is None:
        return None
    sx = reference.station_x
    return {
        "type": "emfit.studies.LineReference",
        "built_by": "LineReference.from_wave(twin), the load-free twin run",
        "gamma_re_per_m": float(reference.gamma.real),
        "gamma_im_rad_per_m": float(reference.gamma.imag),
        "gamma_im_basis": "the twin's own fitted beta [rad/m]",
        "zc_re_ohm": float(reference.zc.real),
        "zc_im_ohm": float(reference.zc.imag),
        "n_stations": int(len(sx)),
        "station_span_m": float(sx[-1]) - float(sx[0]),
    }


def run_reference(reference) -> dict | None:
    """The six numbers of the reference the run was given, or ``None``.

    This is ``run.reference`` in the loaded artefact.  It is NOT the field the
    ``reference_in_play`` comment calls replaced: that one was
    ``kwargs.get("reference")``, read before any reference existed and so
    structurally ``None`` on every record, twin runs included.  This one is
    built from the ``LineReference`` object actually handed to the solver, and
    is ``None`` only when there was none -- the same condition as
    ``loaded_without_reference``.

    Keys are the dispatch's names, not ``describe_reference``'s suffixed ones:
    ``zc_re``/``zc_im``/``gamma_re``/``gamma_im``/``station_span_m``/
    ``n_stations``.  ``describe_reference`` above still carries the full
    description (type, built_by, gamma_im basis); this is the compact record
    beside it, so a consumer wanting the two impedances and the two propagation
    constants does not have to unpack that description.
    """
    if reference is None:
        return None
    sx = reference.station_x
    return {
        "zc_re": float(reference.zc.real),
        "zc_im": float(reference.zc.imag),
        "gamma_re": float(reference.gamma.real),
        "gamma_im": float(reference.gamma.imag),
        "station_span_m": float(sx[-1]) - float(sx[0]),
        "n_stations": int(len(sx)),
    }


def describe_kwargs(kwargs: dict) -> dict:
    """JSON-safe view of the call, including the load specification (AC-6)."""
    from emfit.board import Load  # noqa: F401  (documented import site)
    from emfit.studies import MS_N_STRIP  # the library's own n_strip default

    # ``loads`` is absent on the twin's arguments (dropped, not emptied), and
    # ``s21_plane``/``reference`` are read with ``.get`` because the twin sets
    # them to None on purpose; on the loaded call all three are present and this
    # view is what it was.
    loads = kwargs.get("loads", ())
    return {
        "launch": kwargs.get("launch"),
        "flux_projection": kwargs.get("flux_projection", False),
        "h_m": kwargs["h"],
        "cell": "h / n_sub",
        "n_sub": kwargs["n_sub"],
        "n_air": kwargs["n_air"],
        "n_top": kwargs["n_top"],
        "n_clean": kwargs["n_clean"],
        "n_strip": kwargs.get("n_strip", MS_N_STRIP),
        "n_line": kwargs["n_line"],
        "n_pml": kwargs["n_pml"],
        "nsteps": kwargs["nsteps"],
        "excite": kwargs["excite"],
        "s21_plane": kwargs.get("s21_plane"),
        "reference": describe_reference(kwargs.get("reference")),
        "loads": [
            {"position_m": float(ld.position),
             "position_mm": float(ld.position) * 1e3,
             "kind": ld.kind,
             "value": float(ld.value),
             "units": "ohm" if ld.kind == "series_r" else
                      ("farad" if ld.kind == "shunt_c" else "?"),
             "port": "p2 (far end of the line)"}
            for ld in loads
        ],
    }


def reference_block(twin, reference, *, artefact: Path, wall_s: float) -> dict:
    """What the twin produced and what the loaded run consumed, in one place.

    Emitted twice on purpose, from ONE code path: as ``run.twin`` in the loaded
    artefact (a loaded result states what it was normalised against) and as
    ``run.reference_produced`` in the twin's own artefact (the twin states what
    it handed over).  Two copies written by two pieces of code would be two
    chances to disagree about the numbers this whole flag exists to pin.

    Units, named once and not left to the reader: ``gamma_im`` is the twin's
    fitted BETA in rad/m, and ``alpha_np_per_m`` is nepers per metre of
    AMPLITUDE decay, i.e. ``emfit/ports.py:1010`` ``LineFit.alpha`` whose unit
    that docstring states as 1/m -- dB per metre is ``8.685889638 * alpha``.
    """
    sx = reference.station_x
    alpha = (float(twin.loss_fit.alpha)
             if twin.loss_fit is not None and twin.loss_fit.alpha is not None
             else None)
    g = dict(twin.geometry)
    return {
        "artefact": str(artefact),
        "gamma_re": float(reference.gamma.real),
        "gamma_im": float(reference.gamma.imag),
        "gamma_im_basis": ("the twin's own fitted BETA [rad/m]: "
                           "gamma = alpha + 1j*beta "
                           "(emfit/studies.py:1743-1749, "
                           "LineReference.from_wave)"),
        "alpha_np_per_m": alpha,
        "alpha_np_per_m_basis": (
            "nepers per metre of AMPLITUDE decay, exp(-alpha x): "
            "emfit/ports.py:1010 LineFit.alpha, whose unit is 1/m, or dB/m "
            "as 8.685889638 * alpha.  None when the twin's stations could not "
            "support a loss fit (loss_fit or loss_fit.alpha is None), and "
            "LineReference.from_wave then uses exactly 0.0 -- a line with no "
            "modelled loss, not a measured zero."),
        "zc_re": float(reference.zc.real),
        "zc_im": float(reference.zc.imag),
        "zc_basis": ("the twin's station_fit.z0: the impedance its own station "
                     "voltages and currents imply, not the closed-form z0"),
        "station_span_m": float(sx[-1]) - float(sx[0]),
        "station_span_basis": ("the twin's first to last station, "
                               "station_x[-1] - station_x[0]; forward_ratio "
                               "refuses any other pair, so this is the span the "
                               "loaded s21 was normalised over"),
        # The s11 fit's own stations and span, beside (not instead of) the
        # full span above: a station sitting on the lumped load's column is
        # dropped from the impedance fit -- emfit/studies.py
        # _station_fit_selection -- and with the default x_last = 20 mm that is
        # the last station.  ``.get`` so an older record without them reads as
        # absent rather than raising.
        "station_fit_span_m": g.get("station_fit_span_m"),
        "station_fit_basis": ("station_x[-1] - station_x[0] over the stations "
                              "the s11 fit actually used; shorter than "
                              "station_span_m when the last station sat on the "
                              "load column"),
        "load_station_excluded": g.get("load_station_excluded"),
        "station_fit_cells": g.get("station_fit_cells"),
        "station_fit_n": g.get("station_fit_n"),
        "grid": [int(g.get("nx", 0)), int(g.get("ny", 0)),
                 int(g.get("nz", 0))],
        "wall_seconds_twin": wall_s,
    }


def twin_artefact(twin, reference, *, twin_kwargs: dict, meta: dict,
                  loaded_path: Path, artefact_path: Path, wall_s: float,
                  peak_mb: float) -> dict:
    """The twin's own artefact: a run record, not a debug dump.

    Same shape as the loaded artefact (``meta``, ``run``, ``geometry``, ``s21``,
    ``s11``, ``line``, ``summary_line``) because it is the same kind of thing:
    one FDTD run of one mesh, with its own status, its own wall time, and its
    own geometry as ACHIEVED rather than as intended.  The one thing it does not
    have is a load, and the record says that where a reader would look for it --
    ``run.kwargs.loads`` is empty because the key was dropped, and
    ``run.kwargs.s21_plane`` is None.

    Written before the loaded solve starts, so a loaded run that dies does not
    take the twin's record with it.
    """
    import numpy as np

    g = dict(twin.geometry)
    geom = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer))
                else v)
            for k, v in g.items()
            if isinstance(v, (int, float, str, np.floating, np.integer))}
    geom["loads"] = load_records(g.get("loads"))
    cells = int(g.get("nx", 0)) * int(g.get("ny", 0)) * int(g.get("nz", 0))
    rb = reference_block(twin, reference, artefact=artefact_path, wall_s=wall_s)
    s21 = complex(twin.s21)
    s21_raw = complex(twin.s21_raw)
    s11 = complex(twin.gamma_port)

    return {
        "meta": dict(meta, **{
            "study": f"termination-build-{meta.get('label')}-twin",
            "status": "ok",
            "finished_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "wall_call_s": wall_s,
            "wall_total_s": wall_s,
            "peak_rss_mb": peak_mb,
            "tripped": False,
            "twin_of": str(loaded_path),
            "trip_note": (
                "ONE trip was armed before this run and it covers both solves: "
                "--wall-limit-s is a PROCESS budget, so it is not re-armed for "
                "the loaded run that follows, and the RSS high-water mark it "
                "watches is the process's, not this run's.  A second Trip would "
                "write the same .trip.json marker twice."),
        }),
        "run": {
            "label": f"{meta.get('label')}-twin",
            "role": (f"the load-free twin of the loaded run in "
                     f"{loaded_path.name}: `loads` dropped (not emptied), "
                     f"`s21_plane` None, everything else -- mesh, source, "
                     f"steps -- the loaded run's own"),
            "source_port": "p1",
            "load_port": "none -- this record carries no load",
            "function": "emfit.studies.microstrip_wave",
            "kwargs": describe_kwargs(twin_kwargs),
            "loaded_without_reference": bool(twin.loaded_without_reference),
            "loaded_without_reference_note": (
                "False on a load-free record by construction: there is no load "
                "for a missing reference to have normalised "
                "(emfit/studies.py:3229)."),
            "reference_produced": rb,
            "s21_plane_note": (
                "s21_plane is None here because emfit/studies.py:2692-2697 "
                "refuses a named plane on a load-free record; None is the "
                "station span, which is the reference's own span."),
        },
        "geometry": dict(geom, **{
            "cells": cells,
            "grid": [int(g.get("nx", 0)), int(g.get("ny", 0)),
                     int(g.get("nz", 0))],
            "cell_m": geom.get("cell"),
            "dt_s": geom.get("dt"),
            "nsteps": geom.get("nsteps"),
            "f_hz": geom.get("f"),
            "s21_plane_index": g.get("s21_plane_index"),
        }),
        "s21": {
            "magnitude": abs(s21),
            "phase_rad": float(np.angle(s21)),
            "phase_deg": float(np.degrees(np.angle(s21))),
            "real": s21.real,
            "imag": s21.imag,
            "raw_magnitude": abs(s21_raw),
            "raw_phase_rad": float(np.angle(s21_raw)),
            "raw_phase_deg": float(np.degrees(np.angle(s21_raw))),
            "planes_m": [float(twin.s21_planes[0]), float(twin.s21_planes[1])],
            "s21_plane_index": twin.s21_plane_index,
            "s21_plane_requested": g.get("s21_plane_requested"),
            "basis": (
                "the station span, not a cut plane: s21_plane is None on this "
                "record and a load-free line has no cut for a plane to name.  "
                "De-embedded with this run's own beta (emfit/studies.py:3261, "
                "line_s21 at :1242).  What the loaded run is normalised by is "
                "`reference_produced` above, not this number."),
        },
        "s11": {
            "magnitude": abs(s11),
            "phase_deg": float(np.degrees(np.angle(s11))),
            "deembed_distance_m": float(twin.deembed_distance),
            "basis": (
                "gamma_port, the reflection moved to the port plane.  "
                "gamma_plane is nan on every record extracted over the station "
                "span (emfit/studies.py MicrostripWave.gamma_plane), so it is "
                "left out rather than written as nan.  "
                "still the one-wave station-fit reflection at the port plane; "
                "the two-wave path was repointed on the loaded record only."),
        },
        "line": {
            "beta": float(twin.beta),
            "beta_model": float(twin.beta_model),
            "z0_re": float(complex(twin.z0).real),
            "z0_im": float(complex(twin.z0).imag),
            "eps_eff": float(twin.eps_eff),
            "eps_eff_model": float(twin.eps_eff_model),
            "gamma_re": float(complex(twin.gamma).real),
            "gamma_im": float(complex(twin.gamma).imag),
            "alpha_np_per_m": rb["alpha_np_per_m"],
            "alpha_np_per_m_basis": rb["alpha_np_per_m_basis"],
            "station_span_m": rb["station_span_m"],
            "station_fit_span_m": rb.get("station_fit_span_m"),
            "station_fit_basis": rb.get("station_fit_basis"),
            "load_station_excluded": rb.get("load_station_excluded"),
            "station_fit_cells": rb.get("station_fit_cells"),
            "station_fit_n": rb.get("station_fit_n"),
        },
        "summary_line": twin.summary(),
    }


def ac_block(res, *, load_mm: float, load_ohm: float, peak_mb: float,
             wall_s: float, plane_from_default_policy: bool = False) -> dict:
    """AC-1..AC-7, each with the achieved value beside its pass/fail.

    A criterion that Run A structurally cannot close says so in
    ``closable_in_run_a``/``status`` rather than being scored on a proxy.  Bars are
    quoted from ``docs/design/absorbing_termination_scope.md:222-270`` [R] and are
    not adjusted here (AC-2).
    """
    import math

    s21 = complex(res.s21)
    # AC-3 grades the port-referenced reflection: ``s11`` here is ``gamma_port``,
    # which is where a user's S-parameters are quoted.  ``gamma_plane`` -- the
    # reflection on the extraction plane's own cut -- is a different quantity and
    # is graded by AC-6 below, from that block's own local name.
    s11 = complex(res.gamma_port)
    s21_abs = abs(s21)
    s11_abs = abs(s11)
    gamma_plane = res.gamma_plane
    plane_index = res.s21_plane_index
    # --- where the load actually is, and where the far PML starts ---------
    # ``load_index`` used to be read back as res.geometry["s21_plane_index"],
    # which is the SAME int(ix_extract) the wave loop stores (emfit/studies.py
    # :3608 writes it, :3669 returns it), so the old indices_agree compared a
    # value with itself and could not fail.  The load's own node column is
    # re-derived here from the load position and the cell size, with the very
    # formula emfit/studies.py:2727 uses to place the element,
    #     ix_load = int(floor(position / cell + 0.5)),   cell = h / n_sub,
    # and it is None when this run placed no load at all (geometry["loads"] is
    # written only when one was used, emfit/studies.py:3601).
    _loads_used = res.geometry.get("loads") or ()
    _cell_m = float(res.geometry.get("cell") or 0.0)
    load_column = (int(math.floor(float(load_mm) * 1e-3 / _cell_m + 0.5))
                   if _loads_used and _cell_m > 0.0 else None)
    # The last node column that is NOT inside the xmax PML: ``nx`` counts
    # nodes, the absorber owns the last ``n_pml`` cells, so ``nx - n_pml - 1``
    # is the last clean column -- a plane beyond it reads the PML, not the line.
    _nx = res.geometry.get("nx")
    _npml = res.geometry.get("n_pml")
    last_clean_plane = (int(_nx) - int(_npml) - 1
                        if _nx is not None and _npml is not None else None)
    inside_xmax_pml = (None if last_clean_plane is None or plane_index is None
                       else bool(int(plane_index) > last_clean_plane))
    # AC-6's agreement is with the REQUEST, not with a second copy of the
    # answer: an int request has to be the column the record says it landed
    # on, the name "cut" has to be the load's own column, and no request at
    # all cannot agree with anything.
    _s21_requested = res.geometry.get("s21_plane_requested")
    if plane_index is None or _s21_requested is None:
        indices_agree = False
    elif isinstance(_s21_requested, str):
        indices_agree = bool(load_column is not None
                             and int(plane_index) == int(load_column))
    else:
        indices_agree = bool(int(plane_index)
                             == int(round(float(_s21_requested))))

    # --- AC-7's phase, and why it is the RAW one --------------------------
    # `line_s21` de-embeds with the run's OWN measured beta: `emfit/ports.py:
    # 1707-1731` returns `s21 * exp(+1j*beta*distance)`, and the cut branch
    # calls it as `line_s21(a_port, x_port, a_cut, x_cut, beta)`
    # (`emfit/studies.py:3261`).  So, with `t` the load's own transmission and
    # `d` the extraction distance,
    #
    #     arg(s21)     = arg t + (beta_meas - beta_true) * d   -> flat in L
    #                                                    iff beta_meas = beta_true
    #     arg(s21_raw) = arg t - beta_true * d                -> slope -beta
    #
    # So the de-embedded phase is flat in L only to the extent that the run's
    # own measured beta is right -- it is NOT ~0 by construction, and these
    # artefacts show it is not ~0 in fact (30.05, 50.02 and -74.52 deg on A, B
    # and E; A against E is 104.57 deg over 10.0 mm, the +182.51 rad/m that
    # `graded.json` records).  AC-7 is therefore scored on `s21.raw_phase_deg`,
    # never on `s21.phase_deg`: the de-embedded phase carries the de-embedding's
    # own error rather than removing it.
    #
    # Between two runs the SAME load's arg t cancels exactly (d(arg t)/dL = 0),
    # which is why AC-7 specifies two line lengths.  Within ONE run the
    # port-to-cut pair is not an adequate substitute: it assumes arg t = 0 --
    # true for this matched load and for nothing else -- and arg() returns the
    # principal value, so one run pins beta only modulo 2*pi/dL.  Both numbers
    # are recorded below, raw slope AND de-embedded slope, so that nobody has to
    # guess which of them carried beta.
    s21_raw = complex(res.s21_raw)
    x_a, x_b = (float(res.s21_planes[0]), float(res.s21_planes[1]))
    d_l = x_b - x_a
    raw_phase_rad = math.atan2(s21_raw.imag, s21_raw.real)
    deembedded_phase_rad = math.atan2(s21.imag, s21.real)
    raw_slope = -raw_phase_rad / d_l
    deembedded_slope = -deembedded_phase_rad / d_l

    return {
        "AC-1": {
            "bar": "bit-for-bit losslessness when no load is specified: the "
                   "``loss_den is None`` branch still taken, existing numbers "
                   "identical to the last stored digit",
            "achieved": None,
            "pass": None,
            "closable_in_run_a": False,
            "status": ("not applicable to Run A: this run is loaded by "
                       "construction. Closed outside the run -- E7 guard probe "
                       "(np.array_equal True, max|diff| 0.0) plus the 45-test "
                       "default-path suite (test_studies 26, test_poynting 9, "
                       "test_plane_capture 10)."),
        },
        "AC-2": {
            "bar": "no existing tolerance anywhere is loosened",
            "achieved": ("0 tolerances changed: this script compares against the "
                         "pre-registered bars of scope section 5 and writes no "
                         "other bound"),
            "pass": True,
            "closable_in_run_a": True,
            "status": "process criterion, satisfied by inspection of this file",
        },
        "AC-3": {
            "bar": "|S11| <= 1.0e-3 and | |S21| - 1 | <= 1.0e-3",
            "achieved": {
                "s11_abs": s11_abs,
                "s21_abs": s21_abs,
                "s21_abs_minus_one": abs(s21_abs - 1.0),
                "s11_bar": 1.0e-3,
                "s21_bar": 1.0e-3,
            },
            "pass": bool(s11_abs <= 1.0e-3 and abs(s21_abs - 1.0) <= 1.0e-3),
            "closable_in_run_a": True,
            "status": "scored",
        },
        "AC-4": {
            "bar": "for at least two unmatched loads, |Gamma| within 3 %% of "
                   "|R - Zc| / (R + Zc)",
            "achieved": None,
            "pass": None,
            "closable_in_run_a": False,
            "status": ("not closable in Run A: Run A carries exactly one load "
                       "and it is matched (50 ohm). AC-4 needs at least two "
                       "unmatched loads and is a separate batch."),
        },
        "AC-5": {
            "bar": "no |s21| above 1 + 1e-5 anywhere in the batch; and the beta "
                   "standard error on the open control at least 3x smaller than "
                   "the 57 on record, against a PML-terminated reference run",
            "achieved": {
                "s21_abs": s21_abs,
                "tripwire": 1.0 + 1e-5,
                "headroom_below_tripwire": (1.0 + 1e-5) - s21_abs,
            },
            "pass": bool(s21_abs <= 1.0 + 1e-5),
            "pass_scope": "magnitude half only",
            "closable_in_run_a": False,
            "status": ("magnitude half scored on this run; the seam half needs an "
                       "open-control run against a PML-terminated reference run in "
                       "the same batch, and Run A is a single loaded run with "
                       "reference=None. `pass` here must not be read as AC-5 "
                       "closed."),
        },
        "AC-6": {
            "bar": "the run JSON carries the load specification (value, units, "
                   "plane index) and the index of the plane the S-parameters "
                   "were extracted from",
            "achieved": {
                "load_value": float(load_ohm),
                "load_units": "ohm",
                "load_kind": LOAD_KIND,
                "load_position_mm": load_mm,
                # The load's own node column, re-derived (studies.py:2727),
                # NOT read back from the extraction plane.
                "load_plane_index": load_column,
                "s21_plane_index": plane_index,
                "load_column": load_column,
                "plane_offset_from_load": (
                    None if load_column is None or plane_index is None
                    else int(plane_index) - int(load_column)),
                "last_clean_plane": last_clean_plane,
                "inside_xmax_pml": inside_xmax_pml,
                # AC-6 is NOT relaxed for a plane sweep: an acceptance gate
                # must not be widened by the run that would benefit, and a
                # plane picked from geometry could then pass unnoticed.  It
                # therefore reads pass=false on any downstream-plane artefact,
                # and this flag says so instead of hiding it.  A plane chosen by
                # build_kwargs' default policy is not a sweep at all, so the flag
                # is gated on ``not plane_from_default_policy``: otherwise every
                # flag-off run would read as a sweep and AC-6 would look
                # deliberately failed on the artefact it is meant to score.
                "plane_sweep_diagnostic": bool(
                    not plane_from_default_policy
                    and res.geometry.get("s21_plane_requested") is not None
                    and not isinstance(
                        res.geometry.get("s21_plane_requested"), str)),
                "indices_agree": bool(indices_agree),
                "gamma_plane_recorded": bool(
                    gamma_plane is not None
                    and math.isfinite(complex(gamma_plane).real)
                    and math.isfinite(complex(gamma_plane).imag)),
            },
            # pass = the plane is the one that was ASKED for, it is not
            # inside the xmax PML, and gamma_plane was recorded finite.
            "pass": bool(indices_agree
                         and inside_xmax_pml is not True
                         and math.isfinite(complex(gamma_plane).real)
                         and math.isfinite(complex(gamma_plane).imag)),
            "closable_in_run_a": True,
            "status": "scored",
        },
        "AC-7": {
            "bar": "|beta_FDTD - beta_modal| / beta_modal <= 1.0e-3, with "
                   "beta_FDTD = -d(arg S21)/dL from TWO line lengths",
            "which_phase": ("s21.raw_phase_deg -> s21.raw_phase_rad. NOT "
                            "s21.phase_deg: that one is de-embedded with this "
                            "run's own measured beta, so it is flat in L only "
                            "to the extent that beta is exact -- what "
                            "survives is (beta_meas - beta_true)*dL, not 0 by "
                            "construction (see phase_degeneracy below)."),
            "achieved": None,
            "pass": None,
            "closable_in_run_a": False,
            "ac7_status": ("not closable in one run: AC-7 is a slope across two "
                           "line lengths, and this artefact is one length"),
            "reason": ("docs/design/absorbing_termination_scope.md:266 says "
                       "`beta_FDTD = -d(arg S21)/dL` **from two line lengths** -- "
                       "a slope in L, i.e. two runs at two lengths. This run is "
                       "one length, so dL is undefined here and no proxy is "
                       "substituted. grade_2b.py takes the slope across the two "
                       "artefacts' own `s21.planes_m`, not a typed-in 10 mm."),
            "beta_modal_recorded": None,
            "phase_degeneracy": {
                "dL_m": d_l,
                "raw_phase_deg": math.degrees(raw_phase_rad),
                "deembedded_phase_deg": math.degrees(deembedded_phase_rad),
                "raw_slope_rad_per_m": raw_slope,
                "deembedded_slope_rad_per_m": deembedded_slope,
                "expected_deembedded_slope_rad_per_m": 0.0,
                "single_run_branch_spacing_rad_per_m": 2.0 * math.pi / d_l,
                "single_run_beta_resolved_only_modulo_branch": True,
                "note": ("The de-embedded slope should read ~0 only if this "
                         "run's own measured beta were exact: what the "
                         "de-embedding leaves is arg t + (beta_meas - "
                         "beta_true)*dL, so a non-zero value here is the "
                         "de-embedding's own residual and not a property of "
                         "the line -- it must never be quoted as a beta. The "
                         "raw slope is the AC-7 quantity, but from ONE run it "
                         "equals beta - arg(t)/dL: that assumes arg t = 0, and "
                         "it is only defined modulo the branch spacing above. "
                         "Neither number is an AC-7 verdict, and neither is "
                         "the field of the same name in graded.json's AC-7 "
                         "block: that one is taken across TWO runs, between "
                         "their `s21.planes_m[1]`, over the 10.0 mm between "
                         "them."),
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(f"Termination build: one load at p2, s21_plane='cut', one "
                     f"shot. Defaults are Run A ({LOAD_VALUE_OHM:g} ohm, "
                     f"n_line {N_LINE_DEFAULT}, load at 20 mm)."))
    ap.add_argument("--out", default=str(OUT_DEFAULT),
                    help="artefact path (default: %(default)s)")
    ap.add_argument("--load-at-mm", type=float, default=20.0,
                    help="load position along the line [mm] (default 20.0 = the "
                         "last measurement station, one station inside the far "
                         "absorber; the mesh quantises it to a column and the "
                         "study validates ix_port < ix_load < nx)")
    ap.add_argument("--n-line", type=int, default=N_LINE_DEFAULT,
                    help="line cells between the reference plane and the top of "
                         "the grid [cells]: nx = n_pml + n_ref + n_line, so 54 "
                         "gives 62 columns (Run A) and 79 gives 87 (Run E, the "
                         "second length AC-7 needs).")
    ap.add_argument("--load-ohm", type=float, default=LOAD_VALUE_OHM,
                    help="series_r load resistance [ohm] (default: %(default)s "
                         "= the matched load AC-3/AC-6/AC-7 are written for). "
                         "100.0 is the exploratory 100 ohm arm (scope L520 "
                         "Ruling 3): graded against a band by grade_2b.py as "
                         "EXPLORATORY, not as an AC.")
    ap.add_argument("--label", default=None,
                    help="run label written into the artefact (default: derived "
                         "from the --out stem, build_E_50ohm.json -> E). Three "
                         "runs share this script, so a hard-coded label would "
                         "make one artefact claim to be another -- exactly the "
                         "provenance defect AC-6 exists to prevent.")
    ap.add_argument("--mem-ceiling-mb", type=float,
                    default=MEM_CEILING_MB_DEFAULT,
                    help="hard peak-RSS ceiling [MB] (default: %(default)s)")
    ap.add_argument("--wall-limit-s", type=float, default=WALL_LIMIT_S_DEFAULT,
                    help="hard wall ceiling [s] (default: %(default)s)")
    ap.add_argument("--with-twin", action="store_true",
                    help="also run the load-free twin (same mesh, `loads` "
                         "dropped, s21_plane None) and normalise the loaded "
                         "s21 against its LineReference.  Roughly DOUBLES the "
                         "wall time -- two solves instead of one -- and the "
                         "single --wall-limit-s budget is a PROCESS budget "
                         "that has to cover both.  The twin's own record is "
                         "written beside --out as <stem>_twin.json.  Off by "
                         "default: without this flag the run and its artefact "
                         "are what they were (loaded_without_reference True).")
    ap.add_argument("--s21-plane-index", type=int, default=None,
                    help="move the s21 extraction probe onto this node column "
                         "[index] instead of the load's own cut, for a "
                         "plane-convergence sweep (the first N at which the "
                         "transported normalisation stops moving as N walks "
                         "downstream).  The library refuses an index UPSTREAM "
                         "of the cut.  Absent (the default): s21_plane='cut' "
                         "-- the load cut, unchanged.")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and print the call, write nothing, run no FDTD; "
                         "with --with-twin it prints the twin's arguments too "
                         "(that is where `loads` leaves the dict and s21_plane "
                         "becomes None)")
    ap.add_argument("--launch", default="lumped",
                    choices=("lumped", "modal"),
                    help="port excitation shape: \"lumped\" (default) puts one "
                         "scalar on every edge of the strip column and is what "
                         "every record this script has written so far was "
                         "driven with; \"modal\" scales those edges by the "
                         "placed microstrip E_z profile, normalised to unit "
                         "peak.  The twin takes the same value.  Design: "
                         "docs/design/modal_port_wiring_design_2026-11-03.md.")

    ap.add_argument("--flux-projection", action="store_true",
                    help="read the s21 cut's two phasors as one modal "
                         "amplitude per channel on the cut column (design "
                         "A-prime, 2026-11-03) instead of the plain sum over "
                         "that column.  Off by default: every artefact this "
                         "script has written was recorded on the summed "
                         "path, and without the flag the run is what it was.")

    args = ap.parse_args(argv)
    label = (args.label if args.label else
             (Path(args.out).stem.replace("build_", "").split("_")[0].upper()
              or LABEL))

    out_path = Path(args.out).resolve()
    # The twin's record sits beside the loaded artefact: build_A_50ohm_v3.json ->
    # build_A_50ohm_v3_twin.json.  Computed unconditionally so the dry run can
    # name it; it is only written when --with-twin is passed.
    twin_path = out_path.with_name(out_path.stem + "_twin" + out_path.suffix)
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    kwargs = build_kwargs(args)

    meta = {
        "schema_version": 1,
        "study": f"termination-build-{label}",
        "label": label,
        "status": "pending",
        "started_utc": started_utc,
        "cwd": str(Path.cwd()),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "argv": sys.argv if argv is None else [sys.argv[0]] + list(argv),
        "command_line": " ".join([Path(sys.argv[0]).as_posix()]
                                 + (sys.argv[1:] if argv is None else argv)),
        "git_rev": None,
        "trip_clause": {
            "reimplemented_not_inherited": (
                "The trip below is RE-IMPLEMENTED in this script. "
                "tools/host_ladder.py owns the frozen --mem-ceiling-mb machinery "
                "and is out of fence for this dispatch, so its thresholds were "
                "copied and its code was not. Do not mistake this for the frozen "
                "machinery."),
            "mem_ceiling_mb": float(args.mem_ceiling_mb),
            "wall_limit_s": float(args.wall_limit_s),
            "rss_basis": ("resource.getrusage(RUSAGE_SELF).ru_maxrss / 1024 "
                          "(process-wide high-water mark; Linux KiB)"),
            "rss_poll_s": RSS_POLL_S,
            "on_memory_trip": "write .trip.json, exit 3",
            "on_wall_trip": "write .trip.json, exit 4",
            "one_shot": ("A trip is not a licence to relaunch: an interrupted "
                         "FDTD run cannot be resumed, only repeated, and a repeat "
                         "is a new decision, not a resumption."),
            "retries": 0,
        },
        "cgroup_limit_mb": cgroup_limit_mb(),
    }

    if args.dry_run:
        dry = {
            "meta": meta,
            "call": {"function": "emfit.studies.microstrip_wave",
                     "kwargs": describe_kwargs(kwargs)},
            "artefact": str(out_path),
            "note": "dry run: no FDTD, nothing written",
        }
        if args.with_twin:
            # The twin's ARGUMENTS only: no FDTD, no LineReference, no file.
            # This is the one place the flag's whole difference is visible
            # without paying for two solves, so it is printed and not summarised.
            dry["twin_call"] = {
                "function": "emfit.studies.microstrip_wave",
                "kwargs": describe_kwargs(twin_kwargs_from(kwargs)),
                "artefact": str(twin_path),
                "note": ("dry run: the twin's arguments -- `loads` dropped, "
                         "s21_plane None, reference None -- with no FDTD, no "
                         "LineReference and nothing written.  The loaded call "
                         "above is the twin's plus loads and s21_plane='cut', "
                         "so the two meshes are one mesh."),
            }
        print(json.dumps(dry, indent=2, sort_keys=True))
        return 0

    cg = meta["cgroup_limit_mb"]
    if cg is not None and cg < args.mem_ceiling_mb:
        sys.stderr.write(
            f"REFUSED: --mem-ceiling-mb {args.mem_ceiling_mb:.1f} MB is above the "
            f"container limit {cg:.1f} MB, so the trip could never fire before "
            f"the container is killed. Pass --mem-ceiling-mb below {cg:.1f} MB.\n")
        return 2

    import emfit.studies as studies
    import numpy as np

    meta["pid"] = os.getpid()
    # ONE trip, armed BEFORE the twin and left armed across both solves.  Its
    # clock starts in __init__, so --wall-limit-s is a process budget: arming a
    # second Trip for the second solve would both under-count the first and
    # write the same .trip.json marker twice.
    trip = Trip(out_path, mem_ceiling_mb=args.mem_ceiling_mb,
                wall_limit_s=args.wall_limit_s,
                argv=meta["argv"], started_utc=started_utc).start()

    twin = None
    reference = None
    wall_twin = None
    try:
        if args.with_twin:
            twin_kwargs = twin_kwargs_from(kwargs)
            t_twin = time.monotonic()
            twin = studies.microstrip_wave(**twin_kwargs)
            wall_twin = time.monotonic() - t_twin
            # LOUDLY, and before the loaded solve is launched: without a station
            # fit there is no zc for LineReference.from_wave to carry, so there
            # is no reference -- and a loaded run launched anyway would quietly
            # be the no-reference run this flag exists to replace.
            if twin.station_fit is None:
                raise ValueError(
                    "the load-free twin produced no station impedance fit, so "
                    "no LineReference was produced and the loaded run was NOT "
                    "started: twin.station_fit is None (station_fit_ok="
                    f"{twin.station_fit_ok!r}).  The twin is the load-free run "
                    "of this same mesh (`loads` dropped, `s21_plane` None) and "
                    "LineReference.from_wave(emfit/studies.py:1743-1749) takes "
                    "its zc from that fit.  Re-run without --with-twin to get "
                    "the no-reference artefact, or fix whatever refused the "
                    "station impedance (see MicrostripWave.station_fit_ok, "
                    "emfit/studies.py).")
            reference = studies.LineReference.from_wave(twin)
            # Written NOW, not after the loaded solve: the twin is a result in
            # its own right and a loaded run that dies must not take it along.
            write_json(twin_path, twin_artefact(
                twin, reference, twin_kwargs=twin_kwargs, meta=meta,
                loaded_path=out_path, artefact_path=twin_path,
                wall_s=wall_twin, peak_mb=max(trip.peak_mb, rss_mb())))
        # ``reference`` is threaded BY KEY: kwargs already carries
        # "reference": None, so passing it positionally would be a duplicate
        # keyword argument (TypeError) rather than an override.
        loaded_kwargs = (dict(kwargs, reference=reference)
                         if args.with_twin else kwargs)
        t_call = time.monotonic()
        res = studies.microstrip_wave(**loaded_kwargs)
        wall_call = time.monotonic() - t_call
    finally:
        trip.stop()
    wall_s = time.monotonic() - started
    peak_mb = max(trip.peak_mb, rss_mb())

    g = dict(res.geometry)
    geom = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer))
                else v)
            for k, v in g.items()
            if isinstance(v, (int, float, str, np.floating, np.integer))}
    geom["loads"] = load_records(g.get("loads"))
    cells = int(g.get("nx", 0)) * int(g.get("ny", 0)) * int(g.get("nz", 0))

    # AC-7's beta_modal is deliberately NOT computed here: a hand-rolled call to
    # emfit.mode_profile on a reconstructed geometry would smuggle a number that
    # no AC-7 verdict may rest on. The field is emitted as null and said to be
    # null.
    beta_modal = None

    # Whether the plane came from build_kwargs' default policy rather than from
    # --s21-plane-index.  Read from the flag, which is what that policy itself
    # reads, and threaded into ac_block because ``plane_sweep_diagnostic`` must
    # keep meaning "the CALLER passed an int": after the default policy lands an
    # int in geometry["s21_plane_requested"], geometry alone cannot tell the two
    # apart, so a flag-off run would otherwise be scored as a plane sweep.
    plane_from_default_policy = bool(args.s21_plane_index is None)
    ac = ac_block(res, load_mm=args.load_at_mm, load_ohm=args.load_ohm,
                  peak_mb=peak_mb, wall_s=wall_s,
                  plane_from_default_policy=plane_from_default_policy)
    ac["AC-7"]["beta_modal_recorded"] = beta_modal

    # Flag-off: both dicts are EMPTY, so the artefact keeps the keys and the
    # values it had -- reference_used, twin and the two wall keys appear only
    # when a reference was actually used.
    twin_fields = {}
    wall_fields = {}
    if args.with_twin:
        twin_fields = {
            "reference_used": True,
            "twin": dict(reference_block(twin, reference, artefact=twin_path,
                                         wall_s=wall_twin),
                          loaded_without_reference=bool(
                              res.loaded_without_reference)),
        }
        wall_fields = {"wall_seconds_twin": wall_twin,
                       "wall_seconds_loaded": wall_call}

    s21 = complex(res.s21)
    s21_raw = complex(res.s21_raw)
    gp = complex(res.gamma_plane)
    s11 = complex(res.gamma_port)
    s11_at_plane = complex(res.gamma_plane)

    # The two-wave modulus and the series-R anchor it is quoted against: read
    # once here, used both as the emitted number and as the prose that compares
    # them, so the two cannot drift apart.
    s11_two_wave_mag = finite_or_none(abs(complex(res.gamma)))
    s11_two_wave_anchor = (args.load_ohm
                           / (2.0 * Z0_SERIES_ANCHOR + args.load_ohm))
    s11_reason_clause = (
        f"On the R={args.load_ohm:g} record it reads "
        f"{s11_two_wave_mag:.4f} against the series-R anchor "
        f"{s11_two_wave_anchor:.5f}, i.e. "
        f"{((s11_two_wave_anchor - s11_two_wave_mag)
            / s11_two_wave_anchor * 100.0):.2f} percent low."
        if s11_two_wave_mag is not None else
        f"On the R={args.load_ohm:g} record the magnitude could not be read.")

    # The bookkeeping keys in ``run`` below say what the numbers above were
    # divided by, so a reader can recompute them from the file alone: the
    # impedance the station fit produced, the forward ratio the reference
    # supplied at the two planes, and how much of the reference's own span the
    # port-to-cut distance covered.  They are records, not inputs -- nothing
    # downstream reads them, and no number above depends on them.
    fit_span_m = res.geometry.get("station_fit_span_m")
    x_port_book = float(g.get("ix_port", 0)) * float(g.get("cell", 0.0))
    ix_cut_book = res.s21_plane_index
    x_cut_book = (None if ix_cut_book is None
                  else float(ix_cut_book) * float(g.get("cell", 0.0)))
    station_span_m = float(res.station_x[-1]) - float(res.station_x[0])
    reference_exponent = (
        None if x_cut_book is None or not station_span_m
        else (x_cut_book - x_port_book) / station_span_m)
    # ``forward_ratio`` is the exact call s21 was divided by
    # (emfit/studies.py:3352 on the cut path, :3367 otherwise), so the planes
    # come from the wave itself rather than from a second guess at them.  A
    # complex is not JSON: it is split into its two parts the way
    # ``reference.zc`` already is.
    if reference is None or x_cut_book is None:
        reference_residual = None
    else:
        ref_ratio = complex(reference.forward_ratio(
            *[float(v) for v in res.s21_planes]))
        reference_residual = {"re": float(ref_ratio.real),
                              "im": float(ref_ratio.imag)}
    # The s11 fit's impedance, or None when there is no usable record -- two
    # ways to have none, and only one of them is ``station_fit is None``: the
    # refusal path leaves it None, but the no-current path fills a *blank*
    # StationFit whose z0 is complex(nan, nan) (emfit/studies.py:3178-3179,
    # _blank_station_fit at :1831).  A NaN would be written as a bare ``NaN``
    # token, which strict JSON parsers reject, so a non-finite z0 counts as
    # absent -- and ``span_m`` goes with it rather than being orphaned.
    sf_z0 = (None if res.station_fit is None
             else complex(res.station_fit.z0))
    station_fit_book = (
        None if sf_z0 is None or not (np.isfinite(sf_z0.real)
                                      and np.isfinite(sf_z0.imag))
        else {"z0_re": float(sf_z0.real), "z0_im": float(sf_z0.imag),
              "span_m": fit_span_m})

    payload = {
        "meta": dict(meta, **{
            "status": "ok",
            "finished_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "wall_call_s": wall_call,
            "wall_total_s": wall_s,
            "peak_rss_mb": peak_mb,
            "tripped": False,
        }, **wall_fields),
        "run": {
            "label": label,
            "source_port": "p1",
            "load_port": "p2",
            "function": "emfit.studies.microstrip_wave",
            "kwargs": describe_kwargs(loaded_kwargs),
            # The reference spec ACTUALLY in play on this call: the same view
            # ``describe_kwargs`` writes at run.kwargs.reference (:520), taken
            # from ``loaded_kwargs`` -- the dict the solver was called with,
            # where the twin's LineReference is threaded by key.  None only when
            # no reference was supplied.  (Replaces a ``"reference":
            # kwargs.get("reference")`` field, which was None by construction on
            # EVERY record -- including ones normalised against a twin -- and so
            # read as "no reference was applied" when one had been.)
            "reference_in_play": describe_reference(
                loaded_kwargs.get("reference")),
            "reference_note": (
                "the reference's own record -- gamma, zc, station span, the "
                "twin's artefact path -- is under run.twin in this artefact "
                "when a twin was run, and under run.reference_produced in the "
                "twin's own file.  This field is the spec of the object the "
                "solver was called with, not a second copy of it."),
            # The reference object's own six numbers, from the object the
            # solver was called with (``run_reference`` above).  ``None`` when
            # no reference was supplied, which is the only case in which the
            # run was normalised against an assumed line constant.  Additive:
            # no existing key changes, and ``reference_in_play`` beside it is
            # still the full description of the same object.
            "reference": run_reference(loaded_kwargs.get("reference")),
            **twin_fields,
            "loaded_without_reference": bool(res.loaded_without_reference),
            "loaded_without_reference_note": (
                "True means no LineReference was supplied, so the cut branch "
                "degraded to zc_split = zc and line_s21(...): the line constant "
                "used to transport the port plane to the cut is the run's own "
                "zc/beta, not a load-free measurement. Stated, not hidden."),
            # The s11 fit's impedance, not ``line.z0``: the two are different
            # numbers (``line.z0`` is the port ratio) and the cut branch of
            # emfit/studies.py:3305 divides by THIS one.  null means no usable
            # impedance record -- the fit refused (station_fit is None,
            # station_fit_ok False) OR the no-current path left a blank fit
            # with z0 = NaN; either way span_m is null too. Stated, not hidden.
            "station_fit": station_fit_book,
            # The reference's forward ratio at ``s21_planes``: what s21 was
            # divided by, so |s21| * |reference_residual| is the measured
            # ratio.  null when no reference was supplied or no cut plane was
            # set, which is exactly when nothing was divided out.
            "reference_residual": reference_residual,
            # (x_cut - x_port) / (station_x[-1] - station_x[0]): the exponent
            # the reference's exp(-gamma d) carried between those planes.
            # Written even with no reference, because it describes the geometry
            # the numbers were taken on, not the reference.
            "reference_exponent": reference_exponent,
        },
        "geometry": dict(geom, **{
            "cells": cells,
            "grid": [int(g.get("nx", 0)), int(g.get("ny", 0)),
                     int(g.get("nz", 0))],
            "cell_m": geom.get("cell"),
            "dt_s": geom.get("dt"),
            "nsteps": geom.get("nsteps"),
            "f_hz": geom.get("f"),
            "s21_plane_index": g.get("s21_plane_index"),
        }),
        "s21": {
            "magnitude": abs(s21),
            "phase_rad": float(np.angle(s21)),
            "phase_deg": float(np.degrees(np.angle(s21))),
            "real": s21.real,
            "imag": s21.imag,
            "raw_magnitude": abs(s21_raw),
            "raw_phase_rad": float(np.angle(s21_raw)),
            "raw_phase_deg": float(np.degrees(np.angle(s21_raw))),
            # raw_s21 is NOT a reference-free measurement: the two travelling
            # waves it is split into use the reference's own gamma/zc
            # (emfit/studies.py:3334-3345), so it inherits that fit's error.
            # Dividing by forward_ratio (emfit/studies.py:3352) is the only
            # step that puts the reference's exp(-gamma d) back.  True here
            # means "no reference was in play", which is the only case the raw
            # ratio comes from this run's own zc/beta
            # (emfit/studies.py:3353-3354).
            "raw_reference_independent": reference is None,
            "raw_basis": (
                "operands use reference.gamma and reference.zc; raw_magnitude "
                "differs from noref raw 0.762847 by 5.8% and is not a "
                "reference-independent measurement"),
            "phase_deg_basis": (
                "s21 de-embedded on the cut branch, and WHICH de-embedding "
                "it is depends on the branch.  With a twin reference -- the "
                "path these loaded runs take -- reference is not None, so "
                "s21 = raw_s21 / reference.forward_ratio(x_port, x_cut) "
                "(emfit/studies.py:3352) and line_s21 is NOT called; the "
                "delay is taken out by the reference's own measured forward "
                "amplitude ratio, rescaled to the run's span, not by this "
                "run's beta.  Only on the no-reference branch does line_s21 "
                "(emfit/studies.py:1242, called at :3354) multiply by "
                "exp(+1j*beta*distance) (emfit/ports.py:1707-1731) with this "
                "run's own measured beta. Flat in L only to the extent "
                "that beta is exact -- what the de-embedding leaves is "
                "arg t + (beta_meas - beta_true)*d, so the slope recorded "
                "in phase_degeneracy.deembedded_slope_rad_per_m is this "
                "run's de-embedding residual, NOT ~0 by construction. Not "
                "the AC-7 quantity, and not the same number as the field "
                "of that name in graded.json's AC-7 block, which "
                "differences two runs over 10.0 mm."),
            "raw_phase_deg_basis": (
                "s21_raw, no de-embedding applied: this is the AC-7 "
                "quantity, and it carries -beta*L."),
            "planes_m": [float(res.s21_planes[0]), float(res.s21_planes[1])],
            "s21_plane_index": res.s21_plane_index,
            "s21_plane_requested": g.get("s21_plane_requested"),
            # True when that plane came from the default policy in
            # build_kwargs rather than from --s21-plane-index.
            "plane_from_default_policy": plane_from_default_policy,
            # Gated on the same condition as AC-6's copy: a plane the default
            # policy chose is not a sweep, and the diagnostic must mean "the
            # caller asked for an index".
            "plane_sweep_diagnostic": bool(
                not plane_from_default_policy
                and g.get("s21_plane_requested") is not None
                and not isinstance(g.get("s21_plane_requested"), str)),
            # Which policy put the probe where it landed: the flag, or the
            # default (build_kwargs).  Stated per artefact so a plane read off
            # this file cannot be mistaken for one that was chosen.
            "plane_policy": ("explicit" if args.s21_plane_index is not None
                             else "default"),
            # The distance the cut branch de-embeds across, the same attribute
            # the s11 block quotes below (emfit/studies.py:3266).
            "deembed_distance_m": (
                None if res.deembed_distance is None
                else float(res.deembed_distance)),
        },
        "s11": {
            "magnitude": s11_two_wave_mag,
            "magnitude_one_wave_station_fit": finite_or_none(abs(s11)),
            "phase_deg": finite_or_none(np.degrees(np.angle(s11))),
            "deembed_distance_m": float(res.deembed_distance),
            "basis": (
                "gamma_port, the reflection moved to the port plane "
                "(emfit/studies.py:3266, declared at :1607; docstring "
                ":1527-1531).  Plane-independent: it does not move when the "
                "extraction plane moves.  "
                "modulus of B/A from fit_beta(n_wave=2), referred to z=0, plane-invariant at alpha=0, not de-embedded. phase_deg is unchanged and belongs to the one-wave station fit at the port plane, NOT to the magnitude beside it; no two-wave phase is reported because no two-wave beta is stored."),
            "validation_status": "UNVALIDATED",
            "validation_reason": (
                "the magnitude above is the modulus of the two-wave B/A, not "
                "the one-wave station-fit reflection (that is kept beside it "
                "as magnitude_one_wave_station_fit).  "
                + s11_reason_clause +
                "  The residual disagreement is unexplained: no "
                "read of station_fit.gamma_v or of the reference construction "
                "has been done, so the status stays. "
                "Residual is configuration-dependent: 5.5% (n=64, load 20mm), "
                "7.6% (n=54, 100 ohm), 13.8% (n=79, load 30mm). The two-wave "
                "modulus is better than one-wave but not converged -- the load's "
                "near-field extends to the last station and contaminates the fit. "
                "Moving the extraction plane further from the load, or modal "
                "projection, would reduce it."),
        },
        "s11_at_plane": {
            "magnitude": finite_or_none(abs(s11_at_plane)),
            "phase_deg": finite_or_none(np.degrees(np.angle(s11_at_plane))),
            "plane_index": res.s21_plane_index,
            "basis": (
                "gamma_plane, the reflection at the extraction plane itself "
                "(b_cut/a_cut).  A different quantity from s11, not "
                "interchangeable; null when the record was extracted over "
                "the station span."),
        },
        "gamma_plane": {
            "re": gp.real,
            "im": gp.imag,
            "abs": abs(gp),
            "arg_deg": float(np.degrees(np.angle(gp))),
        },
        "line": {
            "beta": float(res.beta),
            "beta_model": float(res.beta_model),
            # The two-wave fit's beta (computed emfit/studies.py:3640, field
            # declared :1599): two independent numbers for the same line
            # constant, so the artefact can show both.
            "beta_two_wave": (
                "ABSENT" if getattr(res, "beta_two_wave", None) is None
                else finite_or_none(res.beta_two_wave)),
            # ABSENT, deliberately and for a stated reason: sigma_beta_from_curvature
            # is a function (emfit/ports.py, imported at emfit/studies.py:76
            # and called at :2006, :2184, :3112) whose result is the local
            # ``sigma_beta``; the returned record carries no field of that
            # name, so this run cannot quote it without re-running the
            # curvature estimate itself.  Not recomputed here and not guessed
            # -- it is requested from emfit/studies.py (see REQUEST).
            "sigma_beta_from_curvature": (
                "ABSENT"
                if getattr(res, "sigma_beta_from_curvature", None) is None
                else finite_or_none(res.sigma_beta_from_curvature)),
            "z0_re": float(complex(res.z0).real),
            "z0_im": float(complex(res.z0).imag),
            "eps_eff": (None if res.loaded_without_reference
                        else float(res.eps_eff)),
            "gamma_re": float(complex(res.gamma).real),
            "gamma_im": float(complex(res.gamma).imag),
            # The s11 fit's own stations: a station on the lumped load's
            # column is dropped from the impedance fit, never from
            # ``station_cells`` (emfit/studies.py _station_fit_selection).
            "station_fit_span_m": res.geometry.get("station_fit_span_m"),
            "load_station_excluded": res.geometry.get("load_station_excluded"),
            "station_fit_cells": res.geometry.get("station_fit_cells"),
            "station_fit_n": res.geometry.get("station_fit_n"),
        },
        "ac": ac,
        "summary_line": res.summary(),
    }
    write_json(out_path, payload)
    print(f"wrote {out_path}")
    # The ``|s11|`` printed here is the TWO-WAVE modulus: the same number the
    # payload writes as s11.magnitude (``s11_two_wave_mag`` above = |B/A| of
    # fit_beta(n_wave=2), referred to z=0).  It used to print ``abs(s11)``,
    # which is the one-wave station-fit reflection -- a different quantity,
    # kept in the payload as magnitude_one_wave_station_fit and quoted in
    # parentheses here, labelled, so the two are never read for each other.
    s11_two_wave_txt = (f"{s11_two_wave_mag:.6e}"
                        if s11_two_wave_mag is not None
                        else f"{abs(s11):.6e}(two-wave absent,"
                             f" one-wave value)")
    print(f"label={label} cells={cells} wall={wall_s:.1f}s "
          f"peak_rss={peak_mb:.1f}MB "
          f"|s21|={abs(s21):.9f} arg={np.degrees(np.angle(s21)):.4f}deg "
          f"|s11|={s11_two_wave_txt} "
          f"(one-wave_station_fit |s11|={abs(s11):.6e}) "
          f"cut_plane={res.s21_plane_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
