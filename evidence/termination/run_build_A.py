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
#: Everything under here is EVIDENCE -- a document a reader opens as the record
#: of ONE certified run.  A run that does not reproduce a document may not write
#: to it; the one home for that decision is ``resolve_artefact_out`` below.
EVIDENCE_DIR = (REPO / "evidence").resolve()
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


def _re_im(value) -> dict | None:
    """A complex as the artefact's ``{"re", "im"}`` pair, ``None`` in and out.

    Same two-part split ``_z_eff_block`` and ``reference_residual`` already use,
    and the same ``finite_or_none`` guard: a non-finite part is written as null
    rather than as the bare ``NaN`` token ``json.dumps`` would emit.
    """
    if value is None:
        return None
    z = complex(value)
    return {"re": finite_or_none(z.real), "im": finite_or_none(z.imag)}


def _load_edge_block(res) -> dict | None:
    """The phasor on every E_z edge of the load's own column, or ``None``.

    ``None`` in, ``None`` out: a run without ``--dump-load-edges`` leaves
    ``res.load_edges``/``res.load_edge_v`` None and this emits nothing, so the
    artefact keeps exactly the keys it had.  The edge indices are the linear
    global edge numbers ``cc.idx_ex`` produced for that one node column, so a
    reader can put each phasor back on the mesh without re-deriving the column.
    """
    edges = getattr(res, "load_edges", None)
    phasors = getattr(res, "load_edge_v", None)
    if edges is None or phasors is None:
        return None
    import numpy as np

    idx = np.asarray(edges).ravel()
    v = np.asarray(phasors, dtype=complex).ravel()
    if idx.size == 0 or idx.size != v.size:
        return None
    loads = res.geometry.get("loads") or ()
    block = {
        "n_edges": int(idx.size),
        "edge_indices": [int(e) for e in idx],
        "x_load_m": (float(loads[0]["x"]) if loads else None),
        "v_re": [finite_or_none(z.real) for z in v],
        "v_im": [finite_or_none(z.imag) for z in v],
        "v_magnitude": [finite_or_none(abs(z)) for z in v],
        "v_phase_deg": [finite_or_none(np.degrees(np.angle(z))) for z in v],
    }
    # Only when it happened: a key saying "nothing was nulled" on every record
    # would be noise, and an absent key is the frozen shape.
    if any(block[key].count(None)
           for key in ("v_re", "v_im", "v_magnitude", "v_phase_deg")):
        block["nonfinite_replaced"] = True
    return block


def _s21_plane_block(res) -> dict | None:
    """The cut plane's own two travelling waves, or ``None`` when it was not cut.

    ``None`` in, ``None`` out: ``res.s21_plane_x`` is set only inside the cut
    branch, so a station-span record emits nothing and the artefact keeps the
    keys it had.  These are the phasors ``gamma_plane = b/a`` was formed from,
    stored rather than recomputed, so that reflection can be re-derived from the
    file alone.
    """
    x = getattr(res, "s21_plane_x", None)
    if x is None:
        return None
    return {
        "x_m": finite_or_none(x),
        "v": _re_im(res.s21_plane_v),
        "i": _re_im(res.s21_plane_i),
        "a": _re_im(res.s21_plane_a),
        "b": _re_im(res.s21_plane_b),
    }


def write_field_snapshot(res, out_path: Path) -> Path | None:
    """Write the field snapshot beside the artefact as ``<stem>_fields.npz``.

    ``None`` in, ``None`` out: a run without ``--dump-fields`` leaves
    ``res.field_e_final``/``field_h_final`` None and nothing is written, so the
    artefact's directory is what it was.  Everything stored is a plain numeric
    array or scalar -- no object dtype, no pickle -- so the file reads back with
    ``np.load(..., allow_pickle=False)``; that is why nothing may put a Python
    object in ``arrays``.  The plane blocks are omitted when plane capture was
    off rather than written as a placeholder.
    """
    e = getattr(res, "field_e_final", None)
    h = getattr(res, "field_h_final", None)
    if e is None and h is None:
        return None
    import numpy as np

    geo = dict(res.geometry or {})
    arrays = {}
    if e is not None:
        arrays["e"] = np.asarray(e)
    if h is not None:
        arrays["h"] = np.asarray(h)
    for key in ("plane_ez", "plane_hy", "plane_ey", "plane_hz"):
        block = getattr(res, key, None)
        if block is not None:
            arrays[key] = np.asarray(block)
    arrays["nstep"] = np.int64(res.field_snapshot_nstep)
    arrays["nx"] = np.int64(geo.get("nx", 0))
    arrays["ny"] = np.int64(geo.get("ny", 0))
    arrays["nz"] = np.int64(geo.get("nz", 0))
    arrays["cell_m"] = np.float64(geo.get("cell", 0.0))
    path = out_path.with_name(out_path.stem + "_fields.npz")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    return path


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


def quarter_wave_records(entries):
    """``geometry["load_netlist_quarter_wave"]`` as plain JSON records.

    ``emfit.studies`` builds one record per ``T`` element that declared
    ``quarter_wave_hz`` (``emfit/studies.py:2561-2660``) and hangs them on the
    geometry whenever there is at least one.  The scalar filter at each writer
    below drops a list of dicts for the same reason it drops ``loads``, so
    without this a declared tone would serialise exactly like a document that
    declared none.  ``[]`` and not a missing entry: the caller adds the key
    ONLY when this returns something, because a geometry with no declared tone
    -- and every run with no ``--netlist`` -- must keep the keys it always had.
    """
    return [{"name": str(entry["name"]),
             "declared_hz": float(entry["declared_hz"]),
             "tau_document_s": float(entry["tau_document_s"]),
             "tau_s": float(entry["tau_s"]),
             "f_hz": (None if entry.get("f_hz") is None
                      else float(entry["f_hz"])),
             "declared_tone_retuned": bool(entry["declared_tone_retuned"])}
            for entry in (entries or ())]


def netlist_geometry_record(doc, path):
    """``geometry["load_netlist"]``: which document terminated the cut, or ``None``.

    ``run.kwargs.load_netlist`` already carries the whole document, but the
    GEOMETRY is what a reader (and anything that plots a record against a mesh)
    reaches for when asking what was on this mesh -- and until this key existed a
    diode-terminated and a stub-terminated artefact had the SAME ``geometry``
    section, with the circuit recoverable only from ``run``.  So the provenance
    is written where the geometry is: the file the run was pointed at
    (``path``, resolved), the document's OWN ``name``, the element ``kinds`` it
    carries and how many elements there are -- enough to tell a diode cut
    (``["D"]``) from a stub cut (``["T", "V"]``) without re-parsing anything.
    It names the document; it does not restate its values (those are in
    ``run.kwargs.load_netlist``, the parse of the same file).

    ``None`` in, ``None`` out: the caller adds the key ONLY when this returns
    something, because a netlist-free run's geometry must stay byte-identical to
    the geometry it had before this key existed.
    """
    if doc is None:
        return None
    elements = [el for el in (doc.get("elements") or ())
                if isinstance(el, dict)]
    return {
        "path": None if path is None else str(Path(path).resolve()),
        "name": None if doc.get("name") is None else str(doc.get("name")),
        "kinds": sorted({str(el["kind"]) for el in elements
                         if el.get("kind") is not None}),
        "n_elements": len(elements),
    }


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


# ----------------------------------------------------------------------
# emfit-vis: a time-series field dump, and its numpy-only self test
# ----------------------------------------------------------------------
# Everything below is additive.  Nothing here is on any existing path: a run
# without --vis-dump and without --selftest imports none of it, allocates
# none of it and returns what it always returned.  The one place the solver is
# touched is the ``frame_callback`` kwarg of ``emfit.studies.microstrip_wave``,
# which is ``None`` unless this file passes a recorder.
#
# WHY A DUMP AND NOT A FIGURE.  ``--dump-fields`` keeps ONE timestep (the last)
# and writes it beside the artefact; that is a snapshot and it cannot show a
# wave moving.  An animation needs the field at many times, on a plane the eye
# can follow, and it needs to survive the trip to a viewer that has neither
# this repository nor ``emfit``.  So the contract here is a plain ``.npz`` of
# float32 slices and the numbers needed to label its axes -- no pickle, no
# object dtype, nothing a bare ``numpy.load`` cannot read.
#
# THE EXCITATION PROBLEM.  This script drives the line with a 5.83 GHz CW tone
# because the AC-7 verdict is a phasor measurement at that frequency.  A Ricker
# wavelet centred on the SAME 5.83 GHz is at least one guided wavelength long,
# so on a 24.8 mm line it is not a travelling packet at all -- it is the whole
# line sloshing.  ``--pulse-freq-ghz`` (15.0 GHz by default) is the centre the
# VISUAL dump's wavelet is struck at, chosen to be short compared with the
# line; it overrides ``f_pulse`` only, never ``f_target``, and the reference
# frequency recorded in the file is unconditionally
# ``VIS_F_REF_HZ`` 5827786408.327286 so a reader can always say what the
# measurement frequency of this geometry is, whatever the picture was struck
# at.  A wavelet run is a VISUAL run: its s21/AC numbers are not a
# measurement and are not claimed to be.
#
# THE BUDGET.  The file is meant to be openable, so its size is planned BEFORE
# the solve starts and never discovered afterwards: ``_vis_plan_stride``
# prices ``--nsteps`` and the mesh, and if the answer is over
# ``VIS_BUDGET_MB`` it raises the effective stride and says so, loudly.
# It never fails for size -- a dump that refuses to exist is worse than a dump
# with fewer frames -- and the stride it settled on is recorded in the file as
# ``dump_stride``, so the cadence of a file is read from the file.

#: Version 2 adds the dump PROVENANCE: ``structure_id`` (the ``--structure``
#: arm that was simulated) and ``load_ohm`` (the load actually used). Both are
#: records of the choice, not numbers the geometry implies -- a 50 ohm and a
#: 100 ohm run can share a mesh -- so a viewer cannot derive them and must be
#: told. Version 1 files load without them and read as "unknown".
VIS_SCHEMA = "emfit.vis/2"
VIS_ENGINE = "emfit.fdtd.fit-leapfrog/microstrip_wave"
VIS_DEFAULT_OUT = "evidence/vis_dump.npz"
VIS_SELFTEST_DEFAULT = "artifacts/vis_dump_selftest.npz"
#: Hard size ceiling for the whole file [MB decimal].  Chosen so the artefact
#: is small enough to hand to a browser-side viewer without a download step.
VIS_BUDGET_MB = 45.0
#: One x-cut pair every Nth KEPT y-cut frame.  Stated as a constant because it
#: is a relationship and not a knob: ``ez_xcut_*`` has one frame for every
#: ``VIS_XCUT_STRIDE`` frames of ``ez_ycut``, so ``nt_x == ceil(nt / 10)``
#: and the two arrays share a time base without a second time array to say so.
VIS_XCUT_STRIDE = 10
#: The measurement frequency of this geometry, recorded unconditionally.  This
#: is ``geometry.f`` of every banked Run A artefact (k = 8 of the 0.4 mm-cell
#: ladder: c0 * k / (2 pi ... )) and is NOT moved by --pulse-freq-ghz.
VIS_F_PULSE_HZ = 15.0e9
VIS_F_REF_HZ = 5827786408.327286
#: Phase velocity the line was measured at (parent briefing, 1.5814e8 m/s,
#: lambda_g 27.14 mm at 5.828 GHz): the SAME parent measurement the banked beta
#: below comes from, rounded to five figures.  It is the speed the self test's
#: packet travels at and the loose check on ``v_analytic_m_s``, so a broken
#: derivation is visible as a disagreement with this number rather than as a
#: plausible number nothing can check.  It is NOT a fallback and is never
#: written into ``v_measured_m_s`` under any circumstances.
VIS_V_FALLBACK_M_S = 1.5814e8

#: The BANKED (frozen) phase constant of this line: Run A's own line fit on the
#: 0.4 mm-cell geometry, i.e. lambda_g = 2*pi/beta = 27.1366 mm at f_ref.  Every
#: dump derives ``v_analytic_m_s`` from THIS number and never from the run's own
#: fitted ``res.beta``, because the two are different quantities: the
#: pulse-excited 800-step record fits 261.6 rad/m (1.3995e8 m/s, 11 % low),
#: which is a property of the window that record kept and not of the line, and
#: following it would make ``v_analytic_m_s`` and ``t_traverse_ns`` move with
#: the step count instead of recording the line.
VIS_BETA_BANKED_RAD_PER_M = 231.55331672912826

#: Fixed geometry facts this file records verbatim: the port plane is the
#: ``n_pml + n_ref`` node layer, the load sits at 20.0 mm, the substrate is
#: 1.6 mm of eps_r 4.4 and the strip is 3.2 mm (8 cells) wide.
VIS_PORT_X_MM = 3.2
VIS_LOAD_X_MM = 20.0
VIS_SUBSTRATE_H_MM = 1.6
VIS_STRIP_W_MM = 3.2
VIS_EPS_R = 4.4
#: Highest node column the velocity fit may use.  The far absorber starts at
#: column 56 on the default 62-column mesh, and a packet inside an absorber is
#: not a travelling packet; 48 keeps a whole PML thickness (and then some)
#: between the last fitted frame and the far wall.
VIS_VELOCITY_COLUMN_CAP = 48
#: How many columns past the port column the reduced-profile argmax must have
#: travelled before a frame enters the fit window.  A frame whose peak still sits
#: on the port column is the SOURCE, not a packet: its column is constant, so it
#: carries no slope, and fitting it drags the result toward "stationary".
VIS_VELOCITY_DETACH_COLS = 2
#: Smallest number of windowed frames, and smallest net column advance, a fit
#: may have and still be called a velocity.  These are floors on the
#: measurement's information content, not tolerances: five samples spanning one
#: column are a direction, not a speed.
VIS_VELOCITY_MIN_FRAMES = 8
VIS_VELOCITY_MIN_ADVANCE_COLS = 6
#: How far the windowed fit may disagree with the analytic phase velocity before
#: the measurement is called UNRELIABLE, as a fraction.  On a 50 ohm load at the
#: far end of a line whose |s11| is ~1 the argmax of a 1-D |Ez| profile hops
#: between the incident packet and its echo: the fit is then arithmetically
#: clean and physically wrong, so "a different number" has to be scored, not
#: quoted.  0.15 admits what an argmax that can only move in whole columns can
#: do (2 % at the 800-step cadence) and rejects the 25-30 % a mixed fit produces.
VIS_VELOCITY_RELIABLE_TOL = 0.15

# --- the two arms this one script runs ---------------------------------------
# A and B are the SAME structure with a different termination: same line, same
# mesh, same load POSITION.  The only number that moves is the series_r
# resistance, which is what makes the two emfit-vis dumps comparable frame for
# frame (identical nx/ny/nz/cell_m/j_cut/port_x_mm/load_x_mm) -- and it is why
# the arm is a table entry and not a second copy of this script (header: "line
# length and load value are FLAGS").  A third arm (Run E, the second length
# AC-7 needs) is still expressed the old way, by --n-line/--out; this table
# names only the two arms whose load value is the whole difference.
#
# ``out``/``vis_dump`` are DEFAULTS, nothing more: an explicit --out /
# --vis-dump is used verbatim, so a run that names its own file gets
# exactly that file and the startup line says which numbers were resolved.
STRUCTURES = {
    "A": {
        # 50 ohm: the matched load AC-3/AC-6/AC-7 are written for.
        "load_ohm": LOAD_VALUE_OHM,
        "out": str(OUT_DEFAULT),
        "vis_dump": VIS_DEFAULT_OUT,
    },
    "B": {
        # The exploratory 100 ohm arm (scope L520 Ruling 3).  The stem names
        # this arm (build_B_100ohm -> "B"), and main() reads it back off a
        # typed --out only to WARN when a filename disagrees with the arm run;
        # it never selects the arm.  The dump gets its own name because the
        # shared one
        # (evidence/vis_dump.npz) belongs to A: one file, one arm.
        "load_ohm": 100.0,
        "out": str(REPO / "artifacts" / "build_B_100ohm.json"),
        "vis_dump": "artifacts/vis_dump_B_100ohm.npz",
    },
    "D": {
        # The diode-terminated arm: the cut is closed by a CIRCUIT, not by a
        # lumped resistance, so this row names a netlist file instead of a
        # number.  A row that carried only ``load_ohm`` would have to claim the
        # termination IS 50 ohm, and the startup line would then print
        # "series_r load 50 ohm" over a run whose load is a junction - the
        # provenance lie the NETLIST branch of that line exists to avoid.
        #
        # ``load_ohm`` is still here, and still 50: it is not the termination,
        # it is the number the cut is FREED with (the same resistance that
        # makes A's cut the matched one), and the solver needs a finite value
        # there before the netlist replaces it.
        #
        # The netlist is a PATH, and a real file in the tree rather than a
        # string built here: --netlist takes a path, the document is evidence a
        # reader can open and edit, and inlining the JSON would have made the
        # model coefficients unreadable and unreviewable.
        "netlist": str(REPO / "evidence" / "termination" / "netlists" /
                       "load_diode.json"),
        "load_ohm": LOAD_VALUE_OHM,
        "out": str(REPO / "artifacts" / "build_D_diode.json"),
        # Its own dump, for the same reason B has one: one file, one arm.
        "vis_dump": "artifacts/vis_dump_D_diode.npz",
    },
    "C": {
        # The quarter-wave stub arm: the cut is closed by a SHORT-CIRCUITED
        # length of line, and therefore -- counter-intuitively, and by design --
        # presents an OPEN at the tone this arm reports.  Zin(f) of a lossless
        # line shorted at its far end is j z0 tan(2 pi f tau), so at
        # 2 pi f tau = pi/2 it is infinite: a short at one end is an open at the
        # other.  The far end being shorted is the point, not a defect, and a
        # run whose |s21| does NOT collapse (|s11| -> 1, a notch at f0) is a
        # finding to be reported rather than a number to be repaired.
        #
        # WHY C is not a mere variation on A: A's cut is the matched 50 ohm
        # resistor (|s21| ~ 1, |s11| ~ 0).  C replaces that resistance with a
        # REACTANCE that is an open at f0, so the cut BLOCKS the wave with no
        # dissipative element anywhere in the circuit -- the arm is the one that
        # falsifies "no loss, therefore full transmission", and it is the only
        # arm whose termination transforms impedance rather than absorbing it.
        #
        # tau = 1/(4 f) AT THE TONE THE RUN IS ANALYSED AT -- not at a constant.
        # The document declares that tone (load_stub.json: quarter_wave_hz =
        # 5827786408.327286 Hz, i.e. 1/(4 * 5.827786408327286e9) =
        # 4.289793456444743e-11 s = 42.89793456444743 ps), and emfit.netlist
        # RE-DERIVES tau from the run's own geometry.f when microstrip_wave
        # parses it (parse_netlist(..., f_hz=geometry.f)).  The declaration is
        # kept self-consistent with the tau written beside it; the DELIVERED
        # delay is the quarter-wave delay of the tone in use.
        #
        # Why it cannot be a constant: the analysed tone is the DFT bin nearest
        # f_target, f0 = k/(n_acc*dt) (emfit.studies.snapped_tone), and n_acc
        # depends on n_warm AND on excite.  At nsteps = 2400, f_target = 6 GHz,
        # n_warm = nsteps//4 = 600 (the CW default) that is
        #   1800 * dt = 1.3727339060623177e-9 s -> k = 8
        #   -> f0 = 5.827786408328 GHz   (== VIS_F_REF_HZ, what every banked A
        #                                   artefact reports) -> tau = 42.898 ps
        # but on the PULSE path (excite='pulse' -> n_warm = 0) it is
        #   2400 * dt = 1.8303118747497569e-9 s -> k = 11
        #   -> f0 = 6.009904733588 GHz   -> tau = 4.1597997153410e-11 s = 41.598 ps
        # -- 3 % apart, and a stub cut for the first is NOT a quarter wave at
        # the second.  evidence/termination/run_build_A.py forces
        # excite='pulse' on any run it is given a --vis-dump for, so a banked
        # CW tau would silently describe a tone the --vis-dump run does not use.
        # emfit.studies therefore re-derives it and WARNS (stderr, naming both
        # tones) when they differ; the pair is recorded in
        # geometry.load_netlist_quarter_wave.  Hard-coding 1/(4 VIS_F_REF_HZ)
        # here is the rejected alternative: it is a second source of truth for
        # the tone, and it already drifted once.
        #
        # Against this mesh's step (cell 0.4 mm -> dt = 7.626299478123987e-13 s,
        # 0.7626299478123987 ps) the CW tau is 56.25 samples and the pulse tau
        # 54.5454... samples: NEITHER is an integer, so the line's history
        # lookup takes its linear-INTERPOLATION path (emfit.spice._line_history,
        # weight = 0.25 and 0.5454... respectively) instead of landing on one
        # sample.  That is deliberate: 56 dt = 42.707 ps is 0.44 % short of the
        # CW tau and would pull the notch off the tone, and the interpolation
        # errs by O((dS/dt * dt)^2) inside a sample without biasing the delay.
        #
        # ``load_ohm`` is the same 50 ohm D carries and for the same reason: it
        # is not the termination (the stub is), it is the number that FREES the
        # cut before the netlist replaces it.
        "netlist": str(REPO / "evidence" / "termination" / "netlists" /
                       "load_stub.json"),
        "load_ohm": LOAD_VALUE_OHM,
        "out": str(REPO / "artifacts" / "build_C_stub.json"),
        # Its own dump, for the same reason B and D have one: one arm, one file.
        "vis_dump": "artifacts/vis_dump_C_stub.npz",
    },
}
STRUCTURE_DEFAULT = "A"
#: ``--vis-dump`` with NO argument means "this structure's own default".
#: A sentinel string rather than ``const=VIS_DEFAULT_OUT``, because the
#: default has to be resolved after ``--structure`` is known.
STRUCTURE_DUMP_SENTINEL = "@structure"

# --- the arm an artefact's filename names ------------------------------------
# The arm a run simulates is chosen by --structure and by nothing else; the
# label is that arm's name.  The filename is still read, but ONLY to warn when
# it disagrees with the arm actually run: a visualisation record prepends a
# family prefix (``vis_run_B_100ohm.json``), so the arm is the first token AFTER
# those prefixes and not the first token of the stem -- reading the latter gave
# "VIS" for a 100 ohm artefact, i.e. a filename that names no arm at all and so
# could not be checked against the run.  Stems that carry no prefix keep the
# spelling they always had (``smoke_A.json`` -> SMOKE).
LABEL_STEM_PREFIXES = ("build", "vis", "run", "dump")


def label_from_stem(stem: str) -> str:
    """The arm label a ``--out`` stem names, with its family prefix skipped.

    ``build_B_100ohm`` -> ``B``, ``vis_run_B_100ohm`` -> ``B``,
    ``vis_run_A_50ohm`` -> ``A``, ``build_E_50ohm`` -> ``E``;
    ``smoke_A`` -> ``SMOKE`` (no prefix, legacy spelling kept).  The last token
    is never consumed as a prefix, so a stem cannot resolve to nothing;
    ``LABEL`` is the answer only for an empty stem.
    """
    tokens = [tok for tok in str(stem).split("_") if tok]
    i = 0
    while i < len(tokens) - 1 and tokens[i].lower() in LABEL_STEM_PREFIXES:
        i += 1
    if not tokens:
        return LABEL
    return tokens[i].upper()


def resolve_artefact_out(structure: str, *, out, netlist, vis_dump,
                         default_out: str) -> str:
    """Where this run may write its artefact: redirect a deviating run, or refuse.

    WHY THIS EXISTS.  ``--vis-dump`` makes the solve pulse-excited (a Ricker
    wavelet is only a travelling packet on a pulse, never on a CW tone) and
    ``--netlist`` replaces the ``series_r`` termination with a circuit, but
    NEITHER moves the artefact path: arm A's default ``out`` IS
    ``evidence/termination/build_A_50ohm.json``, the certified CW 50 ohm
    reference.  So ``--structure A --vis-dump ...`` used to write a pulse record
    straight over a tracked CW document -- it happened once, silently, and the
    file's own contents then contradicted everything the document is cited for.
    A DEVIATION is ``pulse`` (a dump was asked for), ``netlist`` (a document the
    arm does not own was named) or both; an arm's OWN netlist -- the one its row
    ships -- is not a deviation, which is why a bare ``--structure D`` still
    writes D's own artefact.

    Two rules, in this order:

    1. IMPLICIT path (no ``--out``), a deviation, and the default would land
       inside ``evidence/`` -> redirect to
       ``artifacts/build_<structure>_<kind>.json``, where ``<kind>`` NAMES the
       deviation (``pulse``, ``netlist``, ``pulse_netlist``).  Only arm A's
       default is inside ``evidence/``, so B/C/D keep the filenames they always
       had -- and a deviating run never reaches evidence either way.
    2. ANY path -- typed or default -- that RESOLVES inside ``evidence/`` and is
       not this arm's own canonical CW document -> ``SystemExit`` naming that
       path and telling the caller to pass ``--out artifacts/...``.  On the
       RESOLVED path, so ``--out evidence/../evidence/termination/build_A_50ohm
       .json`` from a pulse run is refused exactly like the default would be.

    REJECTED ALTERNATIVES, and why they are not this.  (a) Comparing mtimes or
    hashes AFTER the write: by then the evidence document is already the wrong
    bytes and the comparison buys nothing -- it reports the loss instead of
    preventing it.  (b) A lock file / "writing" marker: this script's trip calls
    ``os._exit``, so a killed run leaves the marker behind and the document
    half-written, and every later run then has to decide what a stale lock
    means.  A fail-closed decision taken BEFORE the first byte is written has
    neither failure mode, which is why this is a path rule and not a detector.

    Pure and cheap: no I/O beyond ``Path.resolve()``, no directory created, no
    process state read -- so it is called at argument-resolution time, ahead of
    the banner, the trip thread and the first timestep.
    """
    owned_netlist = STRUCTURES[structure].get("netlist")
    foreign_netlist = netlist is not None and (
        owned_netlist is None
        or Path(netlist).resolve() != Path(owned_netlist).resolve())
    deviations = []
    if vis_dump is not None:
        deviations.append("pulse")
    if foreign_netlist:
        deviations.append("netlist")
    canonical = Path(default_out).resolve()
    if out is None:
        path = canonical
        if deviations and path.is_relative_to(EVIDENCE_DIR):
            # Never the evidence document, and never a name that could be
            # mistaken for one: the deviation is in the filename.
            path = (REPO / "artifacts" /
                    f"build_{structure}_{'_'.join(deviations)}.json")
    else:
        path = Path(out)
    resolved = path.resolve()
    if resolved.is_relative_to(EVIDENCE_DIR) and not (
            not deviations and resolved == canonical):
        why = (" + ".join(deviations) if deviations
               else "a typed path that is not this arm's canonical document")
        raise SystemExit(
            f"REFUSED: this run would write {resolved}, inside evidence/, but "
            f"that document is not the canonical CW record of arm {structure} "
            f"this run produces ({why}). An evidence document is the record of "
            "ONE certified run and cannot be recovered once overwritten: this "
            "tree keeps no history. Pass --out artifacts/<name>.json to write "
            "this run's record outside evidence/, or drop the flag that makes "
            "it deviate from the canonical run.")
    return str(path)


def _vis_estimate_mb(nt: int, nt_x: int, nx: int, ny: int, nz: int) -> float:
    """Price a dump of ``nt`` y-cut and ``nt_x`` x-cut frames [MB decimal].

    Only the arrays are counted, and every one of them is float32 or int32, so
    this is the file's payload and not an estimate of it: the small scalars and
    the zip container are a few hundred bytes each and are below the rounding
    of a number that decides a stride.
    """
    n_ycut = max(int(nt), 0) * int(nx) * int(nz) * 4
    n_xcut = 2 * max(int(nt_x), 0) * int(ny) * int(nz) * 4
    n_axes = (int(nx) + int(ny) + int(nz) + 2 * int(nt) + 2 * int(nt_x)) * 4
    return (n_ycut + n_xcut + n_axes) / 1e6


def _vis_plan_stride(nsteps: int, stride: int, nx: int, ny: int, nz: int,
                     budget_mb: float = VIS_BUDGET_MB,
                     xcut_stride: int = VIS_XCUT_STRIDE):
    """Settle the effective stride from the step count and the mesh, and SAY SO.

    Returns ``(stride, nt, nt_x, est_mb)``.  The first stride that fits the
    budget is the one used, searched upwards one step at a time, so a dump keeps
    as many frames as it can rather than halving itself out of the interesting
    part of the record.  A raised stride is never silent: the old stride, the
    new one and the price of both go to stderr, because a file whose cadence
    changed under the caller is exactly the kind of quiet substitution this
    script's other flags are written to avoid.
    """
    import sys as _sys

    stride = max(1, int(stride))
    xcut_stride = max(1, int(xcut_stride))
    nsteps = max(0, int(nsteps))
    while True:
        nt = (nsteps + stride - 1) // stride
        nt_x = (nt + xcut_stride - 1) // xcut_stride
        est_mb = _vis_estimate_mb(nt, nt_x, nx, ny, nz)
        if est_mb <= float(budget_mb):
            if stride != max(1, int(stride)):
                pass
            return stride, nt, nt_x, est_mb
        if nt <= 1:
            # One frame is over budget only if the MESH is over budget, which
            # no stride can fix: give the single frame and warn instead of
            # looping forever.
            _sys.stderr.write(
                "VIS WARNING: a single frame of this mesh is "
                f"{est_mb:.1f} MB, above the {float(budget_mb):.0f} MB budget; "
                "stride cannot reduce it further. Writing one frame. "
                "Lower --nsteps is not the answer; a coarser x-cut is.\n")
            return stride, max(nt, 1), max(nt_x, 1), est_mb
        old = stride
        while stride == old:
            stride += 1
        _sys.stderr.write(
            f"VIS WARNING: --dump-stride {old} would write "
            f"{_vis_estimate_mb((nsteps + old - 1) // old, (((nsteps + old - 1) // old) + xcut_stride - 1) // xcut_stride, nx, ny, nz):.1f} MB "
            f"for {nsteps} steps, over the {float(budget_mb):.0f} MB budget. "
            f"RAISED the stride {old} -> {stride}: "
            f"{nt} y-cut frames + {nt_x} x-cut frames = {est_mb:.1f} MB. "
            f"The stride actually used is recorded in the file as dump_stride.\n")


def vis_geometry(kwargs: dict) -> dict:
    """The mesh integers the dump needs, derived from the call's own kwargs.

    Nothing is typed twice: ``nx = n_pml + n_ref + n_line`` and
    ``j0 = n_pml + n_clean_lo`` are ``emfit.studies.microstrip_wave``'s own
    expressions (``emfit/studies.py:2848`` and ``:2864-2867``), read off the
    library's constants rather than copied, so a mesh that moves moves this
    with it.  ``j_cut = j0 + n_strip // 2`` is the strip's centre row, which is
    where a microstrip's field is concentrated in y.
    """
    import emfit.studies as studies

    n_pml = int(kwargs.get("n_pml", studies.MS_N_PML))
    n_sub = int(kwargs.get("n_sub", 4))
    n_air = int(kwargs.get("n_air", studies.MS_N_AIR))
    n_top = int(kwargs.get("n_top", studies.MS_N_TOP))
    n_clean = int(kwargs.get("n_clean", studies.MS_N_CLEAN))
    n_strip = int(kwargs.get("n_strip", studies.MS_N_STRIP))
    n_ref = int(kwargs.get("n_ref", studies.MS_N_REF))
    nx = n_pml + n_ref + int(kwargs.get("n_line", studies.MS_N_LINE))
    ny = 2 * n_pml + n_strip + 2 * n_clean
    nz = n_sub + n_air + n_top
    cell_m = float(kwargs.get("h", 1.6e-3)) / n_sub
    j_cut = n_pml + n_clean + n_strip // 2
    return {"nx": nx, "ny": ny, "nz": nz, "cell_m": cell_m,
            "j_cut": j_cut, "n_sub": n_sub, "n_strip": n_strip}


def vis_xcut_column(xcut_mm: float, nx: int, cell_m: float,
                    which: str) -> int:
    """The node column an x-cut sits on, clamped with a WARNING if it must be.

    An x-cut outside the mesh does not exist and cannot be interpolated into
    being, and one inside the far absorber measures the absorber rather than
    the line.  Both are clamped rather than refused -- a picture is worth more
    than a refusal -- but a clamped column is a different column from the one
    asked for, so it is announced on stderr and NOT passed off as what was
    requested.  The clamp ceiling is ``nx - 1 - n_pml_like``: on the default
    mesh the far PML opens at column 56, and ``VIS_VCUT_CEIL`` below is
    the last column on the line proper.
    """
    import sys as _sys

    if cell_m <= 0:
        raise SystemExit(f"REFUSED: cell_m={cell_m!r} is not a cell size.")
    col = int(round(float(xcut_mm) * 1e-3 / float(cell_m)))
    ceil = int(nx) - 7            # nx 62 -> 55: one column short of the absorber
    ceil = max(1, min(ceil, int(nx) - 1))
    if col == ceil or 0 <= col <= ceil:
        return col
    clamped = 0 if col < 0 else ceil
    _sys.stderr.write(
        f"VIS WARNING: --xcut-{'near' if which == 'near' else 'far'}-mm "
        f"{float(xcut_mm):g} mm lands on node column {col}, outside the usable "
        f"range 0..{ceil} on this {int(nx)}-column mesh "
        f"(cell {float(cell_m) * 1e3:g} mm; past column {ceil} is the far "
        f"absorber). CLAMPED to column {clamped} = "
        f"{clamped * float(cell_m) * 1e3:.1f} mm, which is NOT the column "
        f"asked for. The column actually used is recorded in the file as "
        f"xcut_{'near' if which == 'near' else 'far'}_mm.\n")
    return clamped


class _VisRecorder:
    """Collect ``ez`` slices inside the solve, one call per completed step.

    Installed as ``microstrip_wave(frame_callback=...)``; the loop calls it
    immediately after ``stepper.step`` (``emfit/studies.py:3244``), BEFORE the
    warm-up window filter, so a pulse run (``n_warm`` 0) and a tone run both
    record one frame per step that the stride selects -- the dump describes the
    march, not the DFT window.

    E_z lives on the primal z-edges, flat index
    ``off_ez + i*nyn*nz + j*nz + k`` (``emfit/operators.py`` ``idx_ez``;
    ``nx``/``nyn``/``nz`` are the CellComplex's point-layer counts, NOT the
    cell counts).  Both cuts are therefore a fixed integer gather: the index
    array is built once from ``stepper.cc`` and every frame is one fancy-index
    read.  No per-cell Python, no reshape of the whole 906k-edge vector, and
    nothing that depends on the frame count.

    The buffers are preallocated from the plan, so a frame that would overrun
    is a bug here and is said so, not a silent array growth in the middle of a
    1400 s solve.
    """

    def __init__(self, *, nx: int, ny: int, nz: int, nt: int, nt_x: int,
                 stride: int, j_cut: int, ix_near: int, ix_far: int,
                 xcut_stride: int = VIS_XCUT_STRIDE):
        import numpy as np

        self.nx, self.ny, self.nz = int(nx), int(ny), int(nz)
        self.nt, self.nt_x = int(nt), int(nt_x)
        self.stride = max(1, int(stride))
        self.xcut_stride = max(1, int(xcut_stride))
        self.j_cut, self.ix_near, self.ix_far = int(j_cut), int(ix_near), int(ix_far)
        self.ez_ycut = np.zeros((self.nt, self.nx, self.nz), dtype=np.float32)
        self.ez_near = np.zeros((self.nt_x, self.ny, self.nz), dtype=np.float32)
        self.ez_far = np.zeros((self.nt_x, self.ny, self.nz), dtype=np.float32)
        self.frame_index = np.zeros(self.nt, dtype=np.int32)
        self.frame_time_s = np.zeros(self.nt, dtype=np.float64)
        self.frame_max = np.zeros(self.nt, dtype=np.float64)
        self.n_written = 0
        self.dt_s = None
        self._map_ycut = None
        self._map_near = None
        self._map_far = None
        self.warnings = []

    # -- index maps, built once, off the CellComplex the stepper already has --
    def _build(self, cc):
        import numpy as np

        nx, ny, nz = self.nx, self.ny, self.nz
        if (cc.nxn, cc.nyn, cc.nz) != (nx + 1, ny + 1, nz):
            raise SystemExit(
                "VIS REFUSED: the mesh the solver built is "
                f"(nxn, nyn, nz) = {(cc.nxn, cc.nyn, cc.nz)}, but the dump was "
                f"planned for (nx + 1, ny + 1, nz) = {(nx + 1, ny + 1, nz)}. "
                "The dump's geometry was derived from the call's kwargs and the "
                "solver's grid disagrees with them; nothing is written rather "
                "than slicing the wrong cells.")
        off = cc.off_ez
        k = np.arange(nz, dtype=np.intp)
        i = np.arange(nx, dtype=np.intp)
        j = np.arange(ny, dtype=np.intp)
        self._map_ycut = (off + i[:, None] * (cc.nyn * cc.nz)
                          + self.j_cut * cc.nz + k[None, :])
        self._map_near = (off + self.ix_near * (cc.nyn * cc.nz)
                          + j[:, None] * cc.nz + k[None, :])
        self._map_far = (off + self.ix_far * (cc.nyn * cc.nz)
                         + j[:, None] * cc.nz + k[None, :])
        for name, m in (("y-cut", self._map_ycut), ("near x-cut", self._map_near),
                        ("far x-cut", self._map_far)):
            if m.max() >= cc.n_edges or m.min() < cc.off_ez:
                raise SystemExit(
                    f"VIS REFUSED: the {name} gather index reaches "
                    f"{int(m.max())}, outside the E_z block "
                    f"[{cc.off_ez}, {cc.off_ez + cc.n_ez}) of {cc.n_edges} "
                    "edges. The flat-index formula and this mesh disagree.")

    # -- one call per completed step ----------------------------------------
    def __call__(self, stepper):
        import numpy as np

        if self._map_ycut is None:
            self._build(stepper.cc)
        if self.dt_s is None:
            self.dt_s = float(stepper.dt)
        n = int(stepper.n)
        slot = n - 1
        if slot % self.stride:
            return
        fi = slot // self.stride
        if fi >= self.nt:
            raise SystemExit(
                f"VIS REFUSED: step {n} wants frame {fi} but only "
                f"{self.nt} were planned. The plan and the march disagree; a "
                "dump that silently drops its tail is worse than none.")
        e = stepper.e
        self.ez_ycut[fi] = e[self._map_ycut]
        if fi % self.xcut_stride == 0:
            xi = fi // self.xcut_stride
            if xi < self.nt_x:
                self.ez_near[xi] = e[self._map_near]
                self.ez_far[xi] = e[self._map_far]
        self.frame_index[fi] = n
        self.frame_time_s[fi] = float(stepper.time)
        self.frame_max[fi] = float(np.max(np.abs(self.ez_ycut[fi])))
        self.n_written = fi + 1

    # -- what the writer needs ----------------------------------------------
    def payload(self):
        """The recorded arrays, trimmed to the frames actually written."""
        n = self.n_written
        nt_x = min(self.nt_x, max(1, (n + self.xcut_stride - 1) // self.xcut_stride))
        return {
            "ez_ycut": self.ez_ycut[:n],
            "ez_xcut_near": self.ez_near[:nt_x],
            "ez_xcut_far": self.ez_far[:nt_x],
            "frame_index": self.frame_index[:n],
            "frame_index_xcut": self.frame_index[:nt_x * self.xcut_stride:self.xcut_stride],
            "frame_time_s": self.frame_time_s[:n],
            "dt_s": self.dt_s,
        }


def vis_analytic_velocity(
                          f_ref_hz: float = VIS_F_REF_HZ,
                          beta_rad_per_m: float = VIS_BETA_BANKED_RAD_PER_M):
    """The line's phase velocity from its guide wavelength [m/s], and its basis.

    ``lambda_g = 2*pi/beta`` and ``v = f_ref * lambda_g``.  ``beta`` is the
    BANKED parent figure ``VIS_BETA_BANKED_RAD_PER_M``, not the run's own
    fitted ``res.beta``: a pulse-excited march fits its beta out of the record it
    kept, and that fit moves with the step count (261.6 rad/m at 800 steps on
    the default mesh, i.e. 1.3995e8 m/s -- 11 % under the parent figure), so a
    file whose ``v_analytic_m_s`` followed it would move ``t_traverse_ns`` with
    the march length instead of recording the line.  The figure is frozen here,
    and the basis string returned beside it says so, because that string is what
    ends up in the file's ``velocity_note``: an analytic number whose provenance
    is not written next to it is how a constant quietly becomes a measurement.
    """
    import math

    beta = float(beta_rad_per_m)
    if not (math.isfinite(beta) and beta > 0.0):
        # Unreachable with the module constant; kept so an override that is not
        # a phase constant is loud and still yields a usable number, not a nan.
        return (float(VIS_V_FALLBACK_M_S),
                f"unusable beta {float(beta_rad_per_m)!r}; frozen parent "
                f"figure {float(VIS_V_FALLBACK_M_S):.6g} m/s")
    lambda_g = 2.0 * math.pi / beta
    v = float(f_ref_hz) * lambda_g
    return v, (f"beta={beta:.8g} rad/m (frozen parent figure, NOT this run's "
               f"fitted beta) -> lambda_g={lambda_g * 1e3:.5f} mm at "
               f"f_ref={float(f_ref_hz) / 1e9:.6f} GHz")


def measure_wave_velocity(ez_ycut, frame_index, dt_s, cell_m,
                          port_x_mm: float = VIS_PORT_X_MM,
                          load_x_mm: float = VIS_LOAD_X_MM,
                          column_cap: int = VIS_VELOCITY_COLUMN_CAP,
                          min_points: int = 5,
                          v_analytic_m_s: float | None = None) -> dict:
    """Two numbers, and only one of them is measured.

    ``v_measured_m_s`` is the ONE measurement this file makes, and it is made
    from the file's own array so a reader can repeat it: collapse ``|Ez|`` over
    z (a single ``max`` over the plane -- the field is there or it is not), take
    the peak column of that 1-D profile per frame, and least-squares fit column
    index against ``t_ns`` -- but only over the WINDOW in which that peak is a
    detached travelling packet.  ``slope * cell_m`` is metres per nanosecond by
    construction and ``/ 1e-9`` is m/s.

    The window is the whole difference between a speed and a plausible number,
    because the raw argmax of a whole-profile trace is NOT a packet tracker on
    this line.  Two regions have to be excluded, and both were measured on the
    800-step record rather than assumed:

    * BEFORE DETACHMENT the profile max sits on the source column (column 8 at
      x = 3.2 mm) frame after frame while the pulse ramps up, so those frames
      are a flat line -- no slope, and fitting them only dilutes one.  A frame
      is admitted once its peak is at least ``VIS_VELOCITY_DETACH_COLS``
      columns past the port column.
    * AFTER THE PACKET REACHES THE LOAD the global max is the load-plane
      standing-wave pile-up at column 50 (x = 20.0 mm, |Ez| 149.6 against a
      travelling packet's ~10), and it stays there: those frames are a
      STATIONARY maximum, not a travelling one.  A frame is admitted only while
      its peak is short of ``column_cap``, and the scan stops at the first frame
      that is not -- the far absorber starts at column 56 and a packet inside
      an absorber is not a travelling packet either.

    ``t_traverse_ns`` is NOT a measurement and is never presented as one: it is
    the crossing time of ``v_analytic_m_s``, the analytic phase velocity, over
    the port-to-load span.  The measured speed is a separate key and is never
    overwritten with this one -- when the fit is rejected ``v_measured_m_s`` is
    NaN and ``reason`` says what was missing -- and what a substitution would
    hide is scored in ``v_measured_reliable`` instead: 1 only when the windowed
    fit has at least ``VIS_VELOCITY_MIN_FRAMES`` frames, advances
    monotonically by at least ``VIS_VELOCITY_MIN_ADVANCE_COLS`` columns,
    and lands within ``VIS_VELOCITY_RELIABLE_TOL`` of the analytic speed.
    ``velocity_note`` says the same thing in words.
    """
    import numpy as np

    ez = np.asarray(ez_ycut, dtype=np.float32)
    fi = np.asarray(frame_index).reshape(-1)
    # The traverse time is analytic in EVERY branch, so it is computed once here
    # from the analytic phase velocity and never from whatever the peak fit did.
    v_an = (float(v_analytic_m_s) if v_analytic_m_s is not None
            else float(vis_analytic_velocity()[0]))
    t_traverse_ns = (float(load_x_mm) - float(port_x_mm)) * 1e-3 / v_an * 1e9
    out = {"v_measured_m_s": float("nan"), "measured": False,
           "points": 0, "t_traverse_ns": t_traverse_ns, "reason": "",
           "v_analytic_m_s": v_an, "v_measured_reliable": 0,
           "velocity_note": ""}

    def _reject(reason: str) -> dict:
        """Say what was not measured; v_measured stays NaN, never the analytic."""
        out["reason"] = reason
        out["velocity_note"] = (f"windowed peak tracker: no measurement "
                                f"({reason}); v_measured left NaN, t_traverse "
                                f"from analytic phase velocity")
        return out

    if ez.ndim != 3 or int(ez.shape[0]) != int(fi.size) or fi.size == 0:
        return _reject(f"cannot measure: ez_ycut has shape {ez.shape} and "
                       f"frame_index has {fi.size} entries")
    if dt_s is None or not float(dt_s) > 0.0:
        return _reject("cannot measure: no usable dt_s")
    t_ns = fi.astype(np.float64) * float(dt_s) * 1e9
    prof = np.abs(ez).max(axis=2)                       # (nt, nx)
    peak = float(prof.max()) if prof.size else 0.0
    # The port column is where the drive sits, so "detached" is a statement
    # about columns and not about amplitudes.
    port_col = int(round(float(port_x_mm) * 1e-3 / float(cell_m)))
    detach_col = port_col + int(VIS_VELOCITY_DETACH_COLS)
    cols, ts = [], []
    if peak > 0.0:
        floor = 1e-3 * peak
        for f in range(int(prof.shape[0])):
            p = prof[f]
            if not np.all(np.isfinite(p)):
                continue
            if float(p.max()) < floor:
                continue                                # nothing launched yet
            c = int(np.argmax(p))
            if c >= int(column_cap):
                break                                   # into the pile-up
            if c < detach_col:
                continue                                # still at the source
            cols.append(c)
            ts.append(float(t_ns[f]))
    out["points"] = len(cols)
    if len(cols) < int(min_points):
        return _reject(f"only {len(cols)} detached frames short of column "
                       f"{int(column_cap)} (< {int(min_points)}); the packet "
                       f"never separated from the source column "
                       f"{port_col} (detach at {detach_col})")
    ts_a = np.asarray(ts, dtype=np.float64)
    cols_a = np.asarray(cols, dtype=np.float64)
    slope, _ = np.polyfit(ts_a, cols_a, 1)
    v = float(slope) * float(cell_m) / 1e-9             # col/ns -> m/s
    n_frames = int(len(cols))
    advance = float(cols_a[-1] - cols_a[0])
    steps = np.diff(cols_a)
    drops = int(np.count_nonzero(steps < 0.0))
    monotone = bool(np.all(steps >= 0.0))
    rel = ((abs(v - v_an) / v_an)
           if (v_an > 0.0 and np.isfinite(v)) else float("inf"))
    # Everything a number needs to earn the name "velocity", checked one at a
    # time so the note can say WHICH one failed.
    why = []
    if not (np.isfinite(v) and v > 0.0):
        why.append(f"fit slope {float(slope):.4g} col/ns is not a speed")
    if n_frames < int(VIS_VELOCITY_MIN_FRAMES):
        why.append(f"{n_frames} detached frames "
                   f"(< {int(VIS_VELOCITY_MIN_FRAMES)})")
    if not monotone:
        why.append(f"argmax non-monotone ({drops} backwards steps in "
                   f"{steps.size}: a standing wave, not a travelling packet)")
    if advance < float(VIS_VELOCITY_MIN_ADVANCE_COLS):
        why.append(f"peak advances only {int(advance)} columns "
                   f"(< {int(VIS_VELOCITY_MIN_ADVANCE_COLS)})")
    if not rel <= float(VIS_VELOCITY_RELIABLE_TOL):
        why.append(f"fit {v:.6g} m/s is {100.0 * rel:.1f} % off the analytic "
                   f"{v_an:.6g} m/s (tol "
                   f"{100.0 * float(VIS_VELOCITY_RELIABLE_TOL):.0f} %)")
    span = (f"{n_frames} frames, columns {int(cols_a[0])}..{int(cols_a[-1])}, "
            f"{100.0 * rel:.1f} % from analytic {v_an:.6g} m/s")
    if why:
        out["velocity_note"] = (f"windowed peak tracker: {span} -- rejected: "
                                + "; ".join(why)
                                + "; v_measured left NaN, t_traverse from "
                                  "analytic phase velocity")
        return out
    out["v_measured_m_s"] = v
    out["measured"] = True
    out["v_measured_reliable"] = 1
    out["reason"] = (f"least-squares fit of the peak E_z column over "
                     f"{n_frames} detached frames "
                     f"({ts_a[0]:.4f}..{ts_a[-1]:.4f} ns, columns "
                     f"{int(cols_a[0])}..{int(cols_a[-1])})")
    out["velocity_note"] = (
        f"windowed peak tracker: {n_frames} frames, {int(advance)} columns, "
        f"{100.0 * rel:.2f} % from the analytic {v_an:.6g} m/s -- this is a "
        f"measured GROUP (packet) velocity of the "
        f"{VIS_F_PULSE_HZ / 1e9:.0f} GHz pulse, whereas v_analytic_m_s is "
        f"the PHASE velocity of the line at "
        f"{VIS_F_REF_HZ / 1e9:.2f} GHz from the frozen parent beta, quoted "
        f"as a SANITY BAND only and not as a prediction of v_g; on a dispersive "
        f"line v_g < v_p is expected, so landing within ~15 % of it means no "
        f"gross error, NOT that the phase velocity is verified")
    return out


def write_vis_dump(path, *, ez_ycut, ez_xcut_near, ez_xcut_far,
                   frame_index, frame_index_xcut, frame_time_s, dt_s,
                   nx: int, ny: int, nz: int, cell_m: float, j_cut: int,
                   dump_stride: int, nsteps: int, f_pulse_hz: float,
                   xcut_near_mm: float, xcut_far_mm: float,
                   structure_id: str, load_ohm: float,
                   f_ref_hz: float = VIS_F_REF_HZ,
                   beta_rad_per_m: float = VIS_BETA_BANKED_RAD_PER_M,
                   port_x_mm: float = VIS_PORT_X_MM,
                   load_x_mm: float = VIS_LOAD_X_MM,
                   substrate_h_mm: float = VIS_SUBSTRATE_H_MM,
                   strip_w_mm: float = VIS_STRIP_W_MM,
                   eps_r: float = VIS_EPS_R,
                   load_v=None, load_i=None,
                   load_netlist_json: str = "") -> dict:
    """Write the one ``.npz`` this script's animation reads, and describe it.

    Units are the file's own: millimetres and nanoseconds everywhere, ``Ez`` in
    V/m and REAL PART ONLY (the solver's field is real -- it is a leapfrog
    march, not a phasor -- so "real part" here means "the field", and the
    phasor convention lives in the artefacts, not in this file).  Every array is
    float32 or int32 and every scalar is a numpy scalar, so the result loads
    with ``np.load(path, allow_pickle=False)``.

    ``structure_id`` and ``load_ohm`` are PROVENANCE, recorded because they
    cannot be recovered from the file: the arm was chosen by ``--structure`` and
    the resistance by ``--load-ohm``, and neither leaves a trace in the fields.
    They are required arguments rather than optional ones for exactly that
    reason -- a caller with nothing to say would have to pass an empty id, and
    the reader reports that as "unknown" instead of inventing a match.

    ``t_ns`` is derived from the solver's own clock (``stepper.time`` per
    frame), not from ``frame_index * dt`` recomputed here: the two agree by
    construction and a disagreement would be a real defect rather than a
    rounding difference.

    Two speeds, and the file says which is which.  ``v_measured_m_s`` is the
    windowed peak-tracking fit of :func:`measure_wave_velocity` and is never
    overwritten with an analytic value -- when the fit is rejected it is NaN,
    not the assumption; ``v_analytic_m_s`` is ``f_ref * lambda_g`` with
    ``lambda_g = 2*pi/beta`` from the BANKED parent constant
    ``VIS_BETA_BANKED_RAD_PER_M`` (``beta_rad_per_m``), never from the
    run's own fitted ``res.beta``; ``t_traverse_ns`` is the ANALYTIC crossing
    time; and ``v_measured_reliable`` / ``velocity_note`` say out loud whether
    the measurement earned the name, the frozen provenance of the analytic
    figure included.

    ``load_v`` / ``load_i`` are the element's own V(t) and I(t), one sample per
    time step, written as ``load_v`` / ``load_i`` beside the ``load_t_ns`` axis
    they belong to.  The trace is ADDITIVE and absent means absent: no trace
    writes ``load_trace_present`` 0 and three empty arrays, never zeros,
    because a load that never sees the wave is a measurement and must not
    become indistinguishable from a run that took no trace at all.
    ``load_netlist_json`` is the netlist document the cut was terminated in
    (JSON text, empty when the load was the lumped ``series_r`` element): which
    CIRCUIT sat on the cut is no more recoverable from the fields than the arm
    or the resistance, which are provenance here for the same reason.
    ``schema`` stays ``emfit.vis/2``: every pre-existing key keeps its name,
    dtype and meaning, so a reader that ignores these five keys reads exactly
    the file it read before.
    """
    import numpy as np

    ez_ycut = np.ascontiguousarray(ez_ycut, dtype=np.float32)
    ez_near = np.ascontiguousarray(ez_xcut_near, dtype=np.float32)
    ez_far = np.ascontiguousarray(ez_xcut_far, dtype=np.float32)
    fi = np.ascontiguousarray(frame_index, dtype=np.int32)
    fi_x = np.ascontiguousarray(frame_index_xcut, dtype=np.int32)
    time_s = np.asarray(frame_time_s, dtype=np.float64).reshape(-1)
    nt = int(ez_ycut.shape[0])
    nt_x = int(ez_near.shape[0])
    if time_s.size != nt:
        raise SystemExit(
            f"VIS REFUSED: {nt} field frames but {time_s.size} frame "
            "times; the file would carry a time axis of the wrong length.")
    v_analytic, v_analytic_basis = vis_analytic_velocity(
        f_ref_hz=float(f_ref_hz), beta_rad_per_m=beta_rad_per_m)
    velocity = measure_wave_velocity(ez_ycut, fi, dt_s, cell_m,
                                     port_x_mm=port_x_mm, load_x_mm=load_x_mm,
                                     v_analytic_m_s=v_analytic)
    velocity_note = (f"{velocity['velocity_note']} "
                     f"[analytic: {v_analytic_basis}]")
    x_mm = (np.arange(nx, dtype=np.float32) * np.float32(cell_m) * 1e3)
    y_mm = (np.arange(ny, dtype=np.float32) * np.float32(cell_m) * 1e3)
    z_mm = (np.arange(nz, dtype=np.float32) * np.float32(cell_m) * 1e3)
    # --- the element's own V(t)/I(t), when the caller traced it -------------
    # One sample per step, and the axis says WHICH instant: sample n is the
    # state after step n, i.e. the solver clock at (n+1)*dt -- the same
    # convention ``t_ns`` follows, because both are read after the step.  The
    # writer is given the trace and never the times, so the axis cannot
    # disagree with the record it describes.
    if load_v is None and load_i is None:
        load_v_arr = np.zeros(0, dtype=np.float32)
        load_i_arr = np.zeros(0, dtype=np.float32)
        load_trace_present = 0
    else:
        load_v_arr = np.ascontiguousarray(
            np.asarray(load_v, dtype=np.float32).reshape(-1))
        load_i_arr = np.ascontiguousarray(
            np.asarray(load_i, dtype=np.float32).reshape(-1))
        if load_v_arr.size != load_i_arr.size:
            raise SystemExit(
                f"VIS REFUSED: {load_v_arr.size} voltage samples against "
                f"{load_i_arr.size} current samples; V(t) and I(t) are ONE "
                "record and cannot be written at two lengths.")
        if load_v_arr.size > int(nsteps):
            raise SystemExit(
                f"VIS REFUSED: {load_v_arr.size} trace samples for a "
                f"{int(nsteps)}-step run; the trace is one sample per step, "
                "so a longer record is not this run's.")
        load_trace_present = 1
    load_t_ns = ((np.arange(load_v_arr.size, dtype=np.float64) + 1.0)
                 * float(dt_s) * 1e9).astype(np.float32)
    arrays = {
        "schema": np.str_(VIS_SCHEMA),
        "engine": np.str_(VIS_ENGINE),
        "created_utc": np.str_(datetime.now(timezone.utc)
                               .isoformat(timespec="seconds")),
        "structure_id": np.str_(structure_id),
        "load_ohm": np.float64(load_ohm),
        "ez_ycut": ez_ycut,
        "ez_xcut_near": ez_near,
        "ez_xcut_far": ez_far,
        "frame_index": fi,
        "frame_index_xcut": fi_x,
        "x_mm": x_mm, "y_mm": y_mm, "z_mm": z_mm,
        "t_ns": (time_s * 1e9).astype(np.float32),
        "nx": np.int32(nx), "ny": np.int32(ny), "nz": np.int32(nz),
        "nt": np.int32(nt), "nt_x": np.int32(nt_x),
        "dt_s": np.float64(dt_s), "cell_m": np.float64(cell_m),
        "j_cut": np.int32(j_cut), "dump_stride": np.int32(dump_stride),
        "nsteps": np.int32(nsteps),
        "f_ref_hz": np.float64(f_ref_hz),
        "f_pulse_hz": np.float64(f_pulse_hz),
        "xcut_near_mm": np.float64(xcut_near_mm),
        "xcut_far_mm": np.float64(xcut_far_mm),
        "port_x_mm": np.float64(port_x_mm), "load_x_mm": np.float64(load_x_mm),
        "substrate_h_mm": np.float64(substrate_h_mm),
        "strip_w_mm": np.float64(strip_w_mm), "eps_r": np.float64(eps_r),
        "v_measured_m_s": np.float64(velocity["v_measured_m_s"]),
        "t_traverse_ns": np.float64(velocity["t_traverse_ns"]),
        "v_analytic_m_s": np.float64(velocity["v_analytic_m_s"]),
        "v_measured_reliable": np.int32(velocity["v_measured_reliable"]),
        "velocity_note": np.str_(velocity_note),
        # Additive, and appended AFTER every key above so that a reader
        # indexing the archive by name reads the same file it always did.
        "load_t_ns": load_t_ns,
        "load_v": load_v_arr,
        "load_i": load_i_arr,
        "load_trace_present": np.int32(load_trace_present),
        "load_netlist_json": np.str_(str(load_netlist_json)),
    }
    path = Path(path).resolve()
    if path.suffix != ".npz":
        # np.savez_compressed appends ".npz" to a name that does not carry it,
        # so the path reported here has to be the suffixed one it writes.
        path = path.with_name(path.name + ".npz")
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    size_mb = path.stat().st_size / 1e6
    if size_mb > VIS_BUDGET_MB:
        sys.stderr.write(
            f"VIS WARNING: {path} is {size_mb:.1f} MB, above the "
            f"{VIS_BUDGET_MB:.0f} MB budget the stride was planned "
            "against (the plan prices payload, and this is the archive).\n")
    return {"path": str(path), "size_mb": float(size_mb), "nt": nt,
            "nt_x": nt_x, "velocity": velocity}


def vis_selftest(path=VIS_SELFTEST_DEFAULT) -> dict:
    """Write a synthetic dump of the real geometry, then check it with numpy alone.

    No mesh, no solve, no FDTD: a Gaussian packet is drawn travelling at
    ``VIS_V_FALLBACK_M_S`` with a 0.345 echo off the load, into arrays of
    exactly the shape and dtype a real run produces, and the file is then
    re-opened and checked key by key.  This is what runs when the 1400 s solve
    is not available; it proves the writer, the reader contract and
    :func:`measure_wave_velocity` agree, and it proves nothing about the solver.

    The return value is JSON-able and every check is reported, pass or fail.  A
    failure raises ``SystemExit`` rather than returning a quiet ``False``.
    """
    import numpy as np

    nx, ny, nz = 62, 212, 22
    cell_m = 0.4e-3
    dt_s = 7.626299478123987e-13
    j_cut = 106
    ix_near, ix_far = 51, 55
    nt = 300
    xcut_stride = VIS_XCUT_STRIDE
    v_mm_ns = float(VIS_V_FALLBACK_M_S) * 1e-6
    sigma_mm = 1.2
    gamma = 0.345
    port_mm = float(VIS_PORT_X_MM)
    load_mm = float(VIS_LOAD_X_MM)

    x_mm = np.arange(nx) * cell_m * 1e3
    y_mm = np.arange(ny) * cell_m * 1e3
    z_mm = np.arange(nz) * cell_m * 1e3
    fi = np.arange(1, nt + 1, dtype=np.int32)
    time_s = fi.astype(np.float64) * dt_s
    t_ns = time_s * 1e9
    x0 = port_mm + v_mm_ns * t_ns
    x_img = 2.0 * load_mm - x0
    gate = (t_ns >= (load_mm - port_mm) / v_mm_ns).astype(np.float64)

    inc = np.exp(-((x_mm[None, :] - x0[:, None]) / sigma_mm) ** 2)
    ref = (gamma * np.exp(-((x_mm[None, :] - x_img[:, None]) / sigma_mm) ** 2)
           * gate[:, None])
    zprof = np.exp(-((z_mm - 1.2) / 1.5) ** 2)
    zprof = zprof / zprof.max()
    yprof = np.exp(-((y_mm - 42.4) / 2.0) ** 2)
    yprof = yprof / yprof.max()
    ez_ycut = (inc + ref)[:, :, None] * zprof[None, None, :]

    def xcut(col: int):
        xc = float(col) * cell_m * 1e3
        a = (np.exp(-((xc - x0) / sigma_mm) ** 2)
             + gamma * np.exp(-((xc - x_img) / sigma_mm) ** 2) * gate)
        return a[:, None, None] * yprof[None, :, None] * zprof[None, None, :]

    sel = np.arange(0, nt, xcut_stride)
    near, far = xcut(ix_near), xcut(ix_far)
    # Exercise the banked-beta -> v_analytic derivation, and check it BOTH ways
    # below: against an inline recomputation from the same constant (tight) and
    # against the frozen parent velocity the packet is actually drawn at
    # (loose, 1e-3).  The two differ by ~2e-5 -- 1.5814e8 is the parent figure
    # rounded, 2*pi*f_ref/beta is its unrounded value -- so a 1e-6 test against
    # the rounded number would fail for a CORRECT file.
    beta_sel = float(VIS_BETA_BANKED_RAD_PER_M)

    summary = write_vis_dump(
        path, ez_ycut=ez_ycut, ez_xcut_near=near[sel], ez_xcut_far=far[sel],
        frame_index=fi, frame_index_xcut=fi[sel], frame_time_s=time_s,
        dt_s=dt_s, nx=nx, ny=ny, nz=nz, cell_m=cell_m, j_cut=j_cut,
        dump_stride=1, nsteps=nt, f_pulse_hz=15.0e9, beta_rad_per_m=beta_sel,
        xcut_near_mm=x_mm[ix_near], xcut_far_mm=x_mm[ix_far],
        # The synthetic packet is drawn on Run A's geometry (the banked
        # port/load positions), so the provenance it records is Run A's own
        # arm and load rather than a made-up fourth structure.
        structure_id=STRUCTURE_DEFAULT,
        load_ohm=float(STRUCTURES[STRUCTURE_DEFAULT]["load_ohm"]))

    req = ("schema", "engine", "created_utc", "structure_id", "load_ohm",
           "ez_ycut", "ez_xcut_near",
           "ez_xcut_far", "frame_index", "frame_index_xcut", "x_mm", "y_mm",
           "z_mm", "t_ns", "nx", "ny", "nz", "nt", "nt_x", "dt_s", "cell_m",
           "j_cut", "dump_stride", "nsteps", "f_ref_hz", "f_pulse_hz",
           "xcut_near_mm", "xcut_far_mm", "port_x_mm", "load_x_mm",
           "substrate_h_mm", "strip_w_mm", "eps_r", "v_measured_m_s",
           "t_traverse_ns", "v_analytic_m_s", "v_measured_reliable",
           "velocity_note", "load_t_ns", "load_v", "load_i",
           "load_trace_present", "load_netlist_json")
    nt_x = int(sel.size)
    checks = []

    def check(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)})
        return bool(ok)

    with np.load(str(path), allow_pickle=False) as d:
        keys = tuple(sorted(d.files))
        missing = [k for k in req if k not in keys]
        extra = [k for k in keys if k not in req]
        check("keys", not missing and not extra,
              f"{len(keys)} keys; missing {missing}; unexpected {extra}")
        check("schema", str(d["schema"]) == VIS_SCHEMA, str(d["schema"]))
        check("engine", str(d["engine"]) == VIS_ENGINE, str(d["engine"]))
        check("structure_id", str(d["structure_id"]) == STRUCTURE_DEFAULT,
              str(d["structure_id"]))
        check("load_ohm",
              float(d["load_ohm"])
              == float(STRUCTURES[STRUCTURE_DEFAULT]["load_ohm"]),
              float(d["load_ohm"]))
        shapes = {
            "ez_ycut": (int(d["nt"]), nx, nz),
            "ez_xcut_near": (nt_x, ny, nz),
            "ez_xcut_far": (nt_x, ny, nz),
            "frame_index": (int(d["nt"]),),
            "frame_index_xcut": (nt_x,),
            "t_ns": (int(d["nt"]),),
        }
        for k, want in shapes.items():
            check(f"shape:{k}", tuple(d[k].shape) == want,
                  f"{tuple(d[k].shape)} want {want}")
        dtypes = {"ez_ycut": "float32", "ez_xcut_near": "float32",
                  "ez_xcut_far": "float32", "frame_index": "int32",
                  "frame_index_xcut": "int32", "t_ns": "float32",
                  "load_t_ns": "float32", "load_v": "float32",
                  "load_i": "float32", "load_trace_present": "int32"}
        check("dtype", all(str(d[k].dtype) == t for k, t in dtypes.items()),
              ", ".join(f"{k}={d[k].dtype}" for k in dtypes))
        for k in ("ez_ycut", "ez_xcut_near", "ez_xcut_far"):
            a = d[k]
            check(f"finite:{k}", bool(np.all(np.isfinite(a))),
                  f"max|{k}|={float(np.max(np.abs(a))):.4g}")
            check(f"nonzero:{k}", float(np.max(np.abs(a))) > 0.0,
                  f"max|{k}|={float(np.max(np.abs(a))):.4g}")
        index = d["frame_index"].astype(np.int64)
        check("frame_index_increasing", bool(np.all(np.diff(index) > 0)),
              f"{int(index[0])}..{int(index[-1])}")
        t_file = d["t_ns"].astype(np.float64)
        check("t_increasing", bool(np.all(np.diff(t_file) > 0)),
              f"{t_file[0]:.6f}..{t_file[-1]:.6f} ns")
        t_err = float(np.max(np.abs(t_file - index * dt_s * 1e9)))
        check("t_axis", t_err < 1e-5,
              f"max|t_ns - frame_index*dt_s*1e9| = {t_err:.3e} ns")
        peak_all = np.argmax(np.abs(d["ez_ycut"]).max(axis=2),
                             axis=1).astype(np.int64)
        # Only the stretch where the packet is still on the line: once it
        # reaches the cut column the echo is what is left in the window, and
        # that travels the other way on purpose.
        off = peak_all >= int(VIS_VELOCITY_COLUMN_CAP)
        first_off = int(np.argmax(off)) if bool(off.any()) else int(peak_all.size)
        seg = peak_all[:first_off]
        check("argmax_monotone",
              bool(seg.size >= 5 and np.all(np.diff(seg) >= 0)),
              f"{seg.size} frames with the peak on the line, columns "
              f"{int(seg[0])}..{int(seg[-1])}")
        vel = summary["velocity"]
        v = float(d["v_measured_m_s"])
        rel = abs(v - float(VIS_V_FALLBACK_M_S)) / float(VIS_V_FALLBACK_M_S)
        check("velocity_measured", vel["measured"] and rel < 0.05,
              f"v_measured={v:.6g} m/s vs {float(VIS_V_FALLBACK_M_S):.6g} "
              f"({100.0 * rel:.2f} %), {vel['points']} frames: {vel['reason']}")
        t_tr = float(d["t_traverse_ns"])
        t_want = ((load_mm - port_mm) * 1e-3
                  / float(VIS_V_FALLBACK_M_S) * 1e9)
        check("t_traverse", abs(t_tr - t_want) <= 0.05 * t_want,
              f"{t_tr:.6f} ns vs {t_want:.6f} ns (analytic)")
        # The synthetic packet IS a clean travelling wave, so the peak fit has
        # to survive its own reliability test here: if it cannot score 1 on a
        # case built to be measurable, the rejection rule would be rejecting
        # everything and the flag would carry no information.
        v_an = float(d["v_analytic_m_s"])
        # Tight against the same derivation (no tolerance on arithmetic), then
        # loose against the rounded parent figure the packet travels at.
        v_bank = (2.0 * np.pi * float(VIS_F_REF_HZ)
                  / float(VIS_BETA_BANKED_RAD_PER_M))
        check("v_analytic_banked",
              abs(v_an - v_bank) <= 1e-9 * v_bank,
              f"{v_an:.10g} m/s vs 2*pi*f_ref/beta_banked {v_bank:.10g} m/s "
              f"(beta={beta_sel:.8g} rad/m, run beta NOT followed)")
        check("v_analytic",
              abs(v_an - float(VIS_V_FALLBACK_M_S))
              <= 1e-3 * float(VIS_V_FALLBACK_M_S),
              f"{v_an:.6g} m/s vs the frozen parent "
              f"{float(VIS_V_FALLBACK_M_S):.6g} m/s "
              f"(lambda_g={2.0 * np.pi / beta_sel * 1e3:.5f} mm)")
        check("v_measured_reliable", int(d["v_measured_reliable"]) == 1,
              f"v_measured_reliable={int(d['v_measured_reliable'])}; "
              f"{str(d['velocity_note'])}")
        # The load trace is ADDITIVE, and the synthetic dump traces nothing:
        # present 0 with EMPTY arrays, which is the difference between "no
        # trace was taken" and "the trace was all zeros".  A reader that
        # ignores these keys reads the pre-trace file exactly.
        check("load_trace_absent",
              int(d["load_trace_present"]) == 0
              and tuple(d["load_t_ns"].shape) == (0,)
              and tuple(d["load_v"].shape) == (0,)
              and tuple(d["load_i"].shape) == (0,),
              f"present={int(d['load_trace_present'])}, "
              f"{int(d['load_t_ns'].size)} samples, 0 expected")
        check("load_netlist_json", str(d["load_netlist_json"]) == "",
              "no netlist was hung on the cut")

    bad = [c for c in checks if not c["ok"]]
    summary = {"status": "ok" if not bad else "FAIL", "path": summary["path"],
               "size_mb": summary["size_mb"], "nt": summary["nt"],
               "nt_x": summary["nt_x"], "velocity": summary["velocity"],
               "checks": checks}
    if bad:
        raise SystemExit(
            "VIS SELFTEST FAILED:\n" +
            "\n".join(f"  {c['check']}: {c['detail']}" for c in bad))
    return summary


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
        # Step count.  Absent --nsteps => 2400, the number this dict has
        # always carried (every banked Run A artefact was built on it);
        # --nsteps N drives the same grid for N steps, nothing else.
        "nsteps": int(args.nsteps),
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
    if args.netlist is not None:
        # A circuit on the load's cut, parsed HERE.  parse_netlist names the
        # element and the field it objects to, and a refusal raised before the
        # mesh, the trip thread and the artefact header exist costs a
        # millisecond instead of a launch.  The DOCUMENT (not the parsed
        # object) is what reaches microstrip_wave, so the artefact and the vis
        # dump record the same text this run was built from -- a parsed object
        # has no JSON form to record.
        netlist_path = Path(args.netlist).resolve()
        try:
            netlist_doc = json.loads(netlist_path.read_text())
        except OSError as exc:
            raise SystemExit(
                f"REFUSED: --netlist {netlist_path}: {exc}") from exc
        except ValueError as exc:
            raise SystemExit(
                f"REFUSED: --netlist {netlist_path} is not JSON: "
                f"{exc}") from exc
        from emfit.netlist import parse_netlist

        try:
            parse_netlist(netlist_doc)
        except ValueError as exc:
            raise SystemExit(
                f"REFUSED: --netlist {netlist_path}: {exc}") from exc
        kwargs["load_netlist"] = netlist_doc
    if args.s21_plane_col is not None and args.s21_plane_index is not None:
        # One int reaches the library either way, so two flags naming it would
        # only hide which of the two the artefact was built from.
        raise SystemExit(
            "--s21-plane-col %d and --s21-plane-index %d were both given: "
            "they name the same geometry[\"s21_plane\"], so only one of them "
            "can be honoured.  Pass --s21-plane-col alone."
            % (int(args.s21_plane_col), int(args.s21_plane_index)))
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
        # --s21-plane-col names that same column by hand; the default
        # expression is untouched, so a flag-off call still lands on
        # ix_load + 1 and its kwargs are what they were.
        col = (int(args.s21_plane_col) if args.s21_plane_col is not None
               else ix_load + 1)
        if col < ix_load:
            raise SystemExit(
                "--s21-plane-col %d is UPSTREAM of the load's own column %d "
                "(load at %g mm, cell = %g m): before the cut the wave has "
                "not reached the element, so the span between the two planes "
                "does not contain it and the ratio stops describing the "
                "load.  Ask for column %d or one downstream of it "
                "(emfit/studies.py:2979)."
                % (col, ix_load, float(args.load_at_mm), cell_m, ix_load))
        # Upper bound without the geometry object: nx = n_pml + n_ref + n_line
        # (emfit/studies.py:2848) with n_ref = MS_N_REF = 2
        # (emfit/studies.py:1201), and n_ref is not a kwarg this script sets.
        nx_cols = int(kwargs["n_pml"]) + 2 + int(kwargs["n_line"])
        if col >= nx_cols:
            raise SystemExit(
                "--s21-plane-col %d is past the last node column: this call "
                "has nx = %d (n_pml %d + n_ref 2 + n_line %d, "
                "emfit/studies.py:2848), so column %d does not exist."
                % (col, nx_cols, int(kwargs["n_pml"]),
                   int(kwargs["n_line"]), nx_cols))
        kwargs["s21_plane"] = col
    elif args.s21_plane_col is not None:
        # No load in the kwargs: there is no cut for a column to be
        # downstream OF.  Mirrors the library's own load-free refusal
        # (emfit/studies.py:2957-2961); unreachable from the CLI today, since
        # build_kwargs always carries the one load it was given.
        raise SystemExit(
            "--s21-plane-col was asked for on a load-free call: there is no "
            "load column for it to sit downstream of.  Leave it off, which "
            "keeps s21_plane None and measures the station span a load-free "
            "record wants.")
    if args.ms_x_window is not None:
        # Probe-station window, millimetres on the command line and metres in
        # the call.  n_stations is deliberately NOT passed beside it: the count
        # stays the library's MS_N_STATIONS, so an override moves the stations
        # and does not also change how many of them the fit sees.  The window
        # used here is the default span 9.6 mm translated down by exactly
        # 7.0 mm (10.4 -> 3.4, 20.0 -> 13.0), so the spacing stays 1.200 mm and
        # only the positions move: one variable, WHERE the fit sampled.
        x_first_mm, x_last_mm = (float(v) for v in args.ms_x_window)
        if not 0.0 < x_first_mm < x_last_mm:
            raise SystemExit(
                f"REFUSED: --ms-x-window {x_first_mm:g} {x_last_mm:g}: two "
                "ascending MILLIMETRE positions are required, first < last and "
                "both above zero.")
        kwargs["x_first"] = x_first_mm * 1e-3
        kwargs["x_last"] = x_last_mm * 1e-3
    check_mesh(kwargs)
    return kwargs


def twin_kwargs_from(kwargs: dict) -> dict:
    """The load-free twin's arguments: the loaded call with the load taken out.

    Exactly four keys move, each for a stated reason:

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
    * ``load_netlist`` is **dropped** for the same reason as ``loads``: the
      netlist is hung on the cut the ``series_r`` load frees, so a load-free
      call has no cut to hang it on and ``emfit/studies.py:2997-3001`` refuses
      one.  Dropped, not emptied: the twin's arguments must not name a circuit
      that is not in it.

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
    twin.pop("load_netlist", None)
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


def _netlist_json(doc) -> str:
    """The netlist document as JSON text, or "" when there is no netlist.

    The records this file writes are JSON, and a netlist is a DOCUMENT: it is
    carried as text (re-serialised with sorted keys, so one file always gives
    one string), never as a summary that a reader would have to re-assemble.
    An already-parsed object -- a caller of ``microstrip_wave`` may hand one in
    -- is rendered with ``default=str`` rather than dropped: a lossy record of
    the object is still a record, and the alternative is silence.
    """
    if doc is None:
        return ""
    try:
        return json.dumps(doc, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(doc)


def describe_kwargs(kwargs: dict) -> dict:
    """JSON-safe view of the call, including the load specification (AC-6)."""
    from emfit.board import Load  # noqa: F401  (documented import site)
    from emfit.studies import MS_N_STRIP  # the library's own n_strip default

    # ``loads`` is absent on the twin's arguments (dropped, not emptied), and
    # ``s21_plane``/``reference`` are read with ``.get`` because the twin sets
    # them to None on purpose; on the loaded call all three are present and this
    # view is what it was.
    loads = kwargs.get("loads", ())
    view = {
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
    # The netlist that terminated the cut, recorded ONLY when --netlist named
    # one.  A record without this key ran the lumped ``series_r`` element of
    # ``loads`` above, which is what every banked artefact carries: absent
    # means "no netlist", never "the same netlist as last time".
    netlist_doc = kwargs.get("load_netlist")
    if netlist_doc is not None:
        doc = netlist_doc if isinstance(netlist_doc, dict) else {}
        view["load_netlist"] = {
            "name": doc.get("name"),
            "nodes": doc.get("nodes"),
            "elements": doc.get("elements"),
            "json": _netlist_json(netlist_doc),
            "tau_note": (
                "Only a T element that DECLARES 'quarter_wave_hz' has its "
                "'tau' tied to that tone: the parser refuses the document "
                "unless tau is quarter_wave_tau(quarter_wave_hz) to 1e-6 "
                "relative, so a declared tau IS the quarter-wave delay of "
                "the tone it names, while a T element without the field "
                "carries whatever tau the file gives.  "
                "emfit.studies.microstrip_wave parses the document with the "
                "tone this run is ANALYSED at (parse_netlist(..., "
                "f_hz=geometry.f)), so every declared line is re-derived for "
                "that tone and the document's own tau is not necessarily the "
                "delay simulated.  One record per declared element -- name, "
                "declared_hz, tau_document_s (the file's), tau_s (the delay "
                "the branch was built with: this runner passes the DOCUMENT, "
                "never an already-parsed Netlist, so the branch is built in "
                "that parse and tau_s IS the delay simulated), f_hz (the "
                "analysed tone) and declared_tone_retuned (declared_hz != "
                "f_hz, to 1e-9 relative) -- is in "
                "geometry.load_netlist_quarter_wave.  That key is PRESENT "
                "whenever the document declared a tone, whether or not it "
                "moved: declared_tone_retuned False means geometry.f WAS "
                "declared_hz, True means it was not (excite='pulse' sets "
                "n_warm = 0 and so moves every tone -- that is what "
                "--vis-dump forces).  It is ABSENT when the document "
                "declared no tone at all, i.e. when every tau was taken "
                "verbatim, and on any run with no --netlist."),
            "note": ("the SPICE document the cut was terminated in, hung on "
                     "the E_x edges the series_r load in `loads` frees "
                     "(emfit.studies.microstrip_wave(load_netlist=...)). Its "
                     "own elements carry every R/L/C/D value, so `loads[]."
                     "value` is NOT the circuit -- it is the lumped element "
                     "the netlist replaced."),
        }
    # The probe-station window, recorded ONLY when --ms-x-window named one.  A
    # record without this key ran the library's own span (MS_X_FIRST..MS_X_LAST,
    # emfit/studies.py:1177-1178) with MS_N_STATIONS stations, which is a
    # default and not a choice someone made, so the key is ABSENT rather than
    # zero: absent means "not asked for", never "0 mm".  Same convention as the
    # s11_settling block, which emits nothing when its flag is off.
    if "x_first" in kwargs:
        view["ms_x_window_mm"] = [float(kwargs["x_first"]) * 1e3,
                                 float(kwargs["x_last"]) * 1e3]
        view["ms_x_window_note"] = (
            "first and last probe station in MILLIMETRES, passed to "
            "emfit.studies.microstrip_wave as x_first/x_last; the station "
            "COUNT is the library default MS_N_STATIONS, so only the positions "
            "moved.  One station on the lumped load's column is dropped from "
            "the impedance fit, never from station_cells (emfit/studies.py "
            "_station_fit_selection), so the fitted span is shorter than this "
            "window when x_last lands on the load.")
    return view


def _z_eff_block(res) -> dict | None:
    """The load column's own impedance, or ``None`` when it was not measured.

    ``None`` in, ``None`` out: a run without ``--measure-z-eff`` leaves
    ``res.z_eff`` None and this emits nothing, so the artefact keeps exactly the
    keys it had.  When it was measured, both phasors are written beside the
    ratio they make, in the artefact's ``{"re", "im"}`` pairs, so ``z_eff`` can
    be recomputed from the file alone and a wrong one is falsifiable from it.
    """
    if getattr(res, "z_eff", None) is None:
        return None

    def pair(value) -> dict:
        z = complex(value)
        return {"re": float(z.real), "im": float(z.imag)}

    return {
        "f_hz": float(res.geometry["f"]),
        "v_load": pair(res.v_load),
        "i_load": pair(res.i_load),
        "z_eff": pair(res.z_eff),
        "z_eff_basis": (
            "V_load is edge_path_voltage over the E_z edges of the load's own "
            "node column -- the same helper the station voltages use -- so it "
            "is the potential difference across the element in volts.  "
            "I_load is plate_current summed as a loop integral in amperes over "
            "the two FY cell faces that straddle that node layer and "
            "averaged, exactly the expression s11_settling.i_cut uses: no mode "
            "projection and no cell width applied, so it is the physical "
            "current the element carries.  The average is there because the FY "
            "faces are cell faces and the element sits on a node layer half a "
            "cell from each.  I_load is negated to refer it to the forward "
            "trace current, as i_cut and the station currents are.  "
            "z_eff = V_load / I_load, both phasors accumulated at the record's "
            "own DFT bin over the settled window."),
    }


# A passive two-port cannot deliver more power than it receives, so a pair of
# PUBLISHED S-parameters that is physically coherent obeys
# ``|S11|^2 + |S21|^2 <= 1``.  The gate below allows a few times 1e-9 above 1.0
# and nothing more, because the arithmetic cannot excuse anything larger: the
# sum is two O(1) squares added in float64, so its own roundoff is a few ulps
# (eps = 2.2e-16), i.e. ~1e-15, and both magnitudes are published at full
# precision, so a reader re-summing them from the file inherits exactly that and
# no more.  1e-9 is the scale of the *decimal* copy a human or a grader reads
# instead -- this file prints 9 decimals (%.9f / %.9e), whose rounding moves the
# sum by at most ~1e-9 -- and 4e-9 clears both by orders of magnitude while
# staying seven orders below any real violation: a 1% excess of |S21| raises the
# sum by 2e-2.
PASSIVITY_TOL = 4.0e-9


def passivity_guard(s11_mag, s21_mag) -> dict:
    """The passivity-coherence record for one PUBLISHED (|S11|, |S21|) pair.

    Returns the dict the artefact carries as ``s11.passivity``: the sum, the
    tolerance it was compared against, and ``status`` -- ``"FAIL_PASSIVITY"``
    when the sum exceeds ``1 + PASSIVITY_TOL``, ``None`` when it does not.  The
    two magnitudes are NOT touched: nothing here clips, rounds or re-derives
    them, so a failing record still publishes the numbers that failed.

    ``None`` in (a magnitude the writer could not read) gives ``None`` for the
    sum and for the status: an absent input is not evidence of passivity, and a
    ``None`` status is what tells the caller to leave the record's pre-existing
    ``validation_status`` alone.  The key set is identical in both branches, so
    a reader never has to guess which one wrote the file.
    """
    tol = PASSIVITY_TOL
    if s11_mag is None or s21_mag is None:
        return {
            "status": None,
            "power_sum": None,
            "tolerance": tol,
            "basis": (
                "|S11|^2 + |S21|^2 on the two magnitudes this artefact "
                "publishes (s11.magnitude, the two-wave |B/A|, and "
                "s21.magnitude), compared against 1 + tolerance.  A passive "
                "two-port cannot exceed 1; the tolerance is the float64 "
                "sum's own roundoff plus the 9-decimal copy a reader may "
                "re-sum, not a physical allowance (PASSIVITY_TOL).  Not "
                "evaluated here: one of the two magnitudes is null, and an "
                "absent number is not evidence of passivity."),
            "verdict": "passivity not evaluated: a published magnitude is null",
        }
    power_sum = float(s11_mag) ** 2 + float(s21_mag) ** 2
    failed = power_sum > 1.0 + tol
    return {
        "status": "FAIL_PASSIVITY" if failed else None,
        "power_sum": power_sum,
        "tolerance": tol,
        "basis": (
            "|S11|^2 + |S21|^2 on the two magnitudes this artefact publishes "
            "(s11.magnitude, the two-wave |B/A|, and s21.magnitude), compared "
            "against 1 + tolerance.  A passive two-port cannot exceed 1; the "
            "tolerance is the float64 sum's own roundoff plus the 9-decimal "
            "copy a reader may re-sum, not a physical allowance "
            "(PASSIVITY_TOL).  The magnitudes are published unclipped and "
            "unrounded, so a failing record keeps the numbers that failed."),
        "verdict": (
            f"|S11|^2 + |S21|^2 = {power_sum:.12f} exceeds 1 + {tol:.1e} = "
            f"{1.0 + tol:.12f}: this pair of published S-parameters is not "
            f"passive"
            if failed else
            f"|S11|^2 + |S21|^2 = {power_sum:.12f} is within 1 + {tol:.1e} = "
            f"{1.0 + tol:.12f}: the published pair is passive-coherent"),
    }


def _station_phasor_block(res) -> dict:
    """The station phasors the impedance fit saw, so ``s11`` can be re-run.

    The ``s11`` block quotes two estimators and neither is checkable from the
    artefact alone: ``magnitude_one_wave_station_fit`` and ``phase_deg`` come
    from ``station_fit.gamma_v``, which is ``amp_v[1] / amp_v[0]``
    (``emfit/ports.py:1517``) -- a ratio over the complex V and I at the
    stations, and those two arrays are written nowhere.  This block writes them,
    in full float64, beside the phase constant the fit was handed, so
    ``emfit.ports.fit_station_impedance(x_m, v, i, beta_used)`` reproduces
    ``gamma_v`` and hence ``gamma_port`` exactly: the one-wave reflection is
    falsifiable from the file, not from a second run.

    ``beta_one`` is null on every record, deliberately.  ``fit_beta(n_wave=1)``
    runs (``emfit/studies.py:3386``) but only its residual reaches the record
    (``fit_residual``, ``emfit/studies.py:3948``); its phase constant is not a
    ``MicrostripWave`` field, so there is nothing to quote and a zero would be
    a wrong number rather than a missing one.  ``beta_used`` is the beta the
    station fit was actually given -- ``StationFit.beta``
    (``emfit/ports.py:1567``), falling back to ``res.beta`` when the fit was
    skipped -- and on this HEAD that is ``fit_two.beta``
    (``emfit/studies.py:3387``), i.e. equal to ``beta_two``.

    Unavailable is an explicit state, not a partial block: if the arrays are
    missing, of unequal length, non-finite, or no beta can be found, every
    number is null and ``status`` says why, matching the ``finite_or_none``
    rule that keeps nan out of the JSON.
    """
    import numpy as np

    x = np.asarray(getattr(res, "station_x", ()), dtype=float).ravel()
    v = np.asarray(getattr(res, "v_stations", ()), dtype=complex).ravel()
    i = np.asarray(getattr(res, "i_stations", ()), dtype=complex).ravel()
    station_fit = getattr(res, "station_fit", None)
    beta_used = (float(getattr(station_fit, "beta", np.nan))
                 if station_fit is not None else np.nan)
    if not np.isfinite(beta_used):
        beta_used = float(getattr(res, "beta", np.nan))
    deembed = getattr(res, "deembed_distance", None)
    beta_two = getattr(res, "beta_two_wave", None)

    note = (
        "x_m, v and i are MicrostripWave.station_x and the complex "
        "v_stations/i_stations -- metres, volts, amperes -- split into "
        "re/im so the JSON stays real.  They are the fit's inputs with one "
        "exception: the impedance fit drops any station sitting on a load "
        "column (emfit/studies.py:2326 _station_fit_selection), so when "
        "line.station_fit_n is smaller than n the same selection has to be "
        "applied before the refit.  gamma_v = amp_v[1]/amp_v[0] from "
        "fit_station_impedance(x_m, v, i, beta_used) is s11's one-wave "
        "reflection at the first station, before the deembed_distance_m "
        "shift to the port plane.  beta_one is null: the n_wave=1 phase "
        "constant is not stored on the record.  beta_used equals beta_two "
        "on this HEAD because beta is repointed to the two-wave fit "
        "(emfit/studies.py:3387) before the station fit is called.  "
        "js, fit_x and fit_selected state which of the n rows the "
        "impedance fit used: js is geometry.station_cells, one station "
        "column per row of x_m; fit_selected is the mask "
        "_station_fit_selection applied (emfit/studies.py:2326, all true "
        "when no load column was dropped); fit_x is the x_m of the "
        "selected stations in order, i.e. the x fit_station_impedance was "
        "handed.  They are read off geometry.station_fit_cells "
        "(emfit/studies.py:3820), not recomputed, so that rule keeps one "
        "home; a record without those cells writes all three as null.")

    def _geometry() -> dict:
        geometry = getattr(res, "geometry", None)
        return geometry if isinstance(geometry, dict) else {}

    n = int(x.size)
    complete = (n > 0 and v.size == n and i.size == n
                and bool(np.all(np.isfinite(x)))
                and bool(np.all(np.isfinite(v)))
                and bool(np.all(np.isfinite(i)))
                and bool(np.isfinite(beta_used)))
    # Which of the n stations the impedance fit actually saw, read off the
    # geometry record the study already publishes rather than re-derived here:
    # ``station_cells`` is the full column list (js), ``station_fit_cells`` the
    # subset ``_station_fit_selection`` kept (emfit/studies.py:2326, written at
    # emfit/studies.py:3820).  The drop rule lives in ONE place, so a change to
    # it cannot leave this block silently disagreeing; a record that does not
    # carry the cells writes the three keys null rather than a guess.
    js = fit_x = fit_selected = None
    geometry = _geometry()
    cells = geometry.get("station_cells")
    fit_cells = geometry.get("station_fit_cells")
    if (cells and fit_cells and n > 0 and len(cells) == n
            and len(fit_cells) == int(geometry.get("station_fit_n") or 0)):
        kept = {int(value) for value in fit_cells}
        mask = [int(value) in kept for value in cells]
        if sum(mask) == len(kept):
            js = [int(value) for value in cells]
            fit_selected = mask
            fit_x = [float(x[k]) for k, selected in enumerate(mask)
                     if selected]

    if not complete:
        return {
            "status": "unavailable",
            "n": None,
            "x_m": None,
            "js": None,
            "fit_x": None,
            "fit_selected": None,
            "v_re": None,
            "v_im": None,
            "i_re": None,
            "i_im": None,
            "beta_used": None,
            "beta_one": None,
            "beta_two": None,
            "deembed_distance_m": None,
            "note": note,
        }

    return {
        "status": "ok",
        "n": n,
        "x_m": [float(value) for value in x],
        "js": js,
        "fit_x": fit_x,
        "fit_selected": fit_selected,
        "v_re": [float(complex(value).real) for value in v],
        "v_im": [float(complex(value).imag) for value in v],
        "i_re": [float(complex(value).real) for value in i],
        "i_im": [float(complex(value).imag) for value in i],
        "beta_used": beta_used,
        "beta_one": None,
        "beta_two": (None if beta_two is None else finite_or_none(beta_two)),
        "deembed_distance_m": (None if deembed is None
                               else float(deembed)),
        "note": note,
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
    # Inert on a load-free twin by construction (``twin_kwargs_from`` drops
    # ``load_netlist``), and written anyway so this block stays the same shape
    # as the loaded one -- same reason ``loads`` above is emitted as ``[]``.
    qw = quarter_wave_records(g.get("load_netlist_quarter_wave"))
    if qw:
        geom["load_netlist_quarter_wave"] = qw
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
    ap.add_argument(
        "--structure", default=STRUCTURE_DEFAULT, choices=sorted(STRUCTURES),
        help="which arm of this one structure to run (default: "
             f"{STRUCTURE_DEFAULT}). The arm is chosen by THIS FLAG and by "
             "nothing else -- never by the --out filename -- because the "
             "physics must not move when a path is edited. The choice sets "
             "DEFAULTS "
             "ONLY -- the load "
             "resistance, the default --out and the default --vis-dump "
             "-- so an explicit --load-ohm / --out / --vis-dump is used "
             "verbatim. A is the graded 50 ohm load; B is the exploratory "
             "100 ohm arm (scope L520 Ruling 3). The mesh, the line length and "
             "the load POSITION are the same in both: only the series_r "
             "resistance moves, so the two runs' geometry is identical. This "
             "names a TERMINATION arm of this solver and is NOT the same "
             "vocabulary as the structure registry in server/poc_app.py "
             "(ids like build_A_50ohm, build_A_50ohm_100ohm), which is a "
             "viewer, not a solver arm.")
    ap.add_argument("--out", default=None,
                    help="artefact path (default: the --structure's own: "
                         f"A -> {STRUCTURES['A']['out']}, "
                         f"B -> {STRUCTURES['B']['out']})")
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
    ap.add_argument("--load-ohm", type=float, default=None,
                    help="series_r load resistance [ohm] (default: the "
                         "--structure's own -- 50.0 for A "
                         "= the matched load AC-3/AC-6/AC-7 are written for, "
                         "100.0 for B). "
                         "100.0 is the exploratory 100 ohm arm (scope L520 "
                         "Ruling 3): graded against a band by grade_2b.py as "
                         "EXPLORATORY, not as an AC.")
    ap.add_argument("--netlist", default=None, metavar="PATH",
                    help="terminate the load's cut in a SPICE NETLIST read "
                         "from this JSON file instead of the lumped "
                         "--load-ohm resistor. It is hung on exactly the E_x "
                         "edges a series_r load frees, through "
                         "emfit.spice.SpicePort (microstrip_wave(load_netlist="
                         "...)), so the cut, the mesh and the drive are the "
                         "resistor run's own and the only difference is where "
                         "the element's current comes from: an MNA solve in "
                         "place of the per-edge conductance 1/(n_edges*R). The "
                         "document carries its own R/L/C/D elements, so "
                         "--load-ohm is IGNORED under --netlist -- the circuit "
                         "is the netlist's, and the lumped element it replaces "
                         "frees the cut. Parsed before the mesh, the trip "
                         "thread and the artefact header exist, and refused by "
                         "emfit.netlist.parse_netlist with the element and the "
                         "field named rather than repaired. The load-free twin "
                         "has no cut, so it is dropped there with `loads`.")
    ap.add_argument("--label", default=None,
                    help="run label written into the artefact (default: the "
                         "resolved --structure, i.e. the arm actually "
                         "simulated -- never the --out filename). Three "
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
    ap.add_argument("--s21-plane-col", type=int, default=None,
                    help="the same hand-picked extraction COLUMN [index] as "
                         "--s21-plane-index, but named by the node column "
                         "the probe must land on rather than by a shift of "
                         "it -- so a sweep can step the column one at a "
                         "time (50, 51, 52, ...) and read each artefact "
                         "as the column it was asked for.  Must be the "
                         "load's own column or downstream of it (upstream "
                         "planes read the element's near field) and lower "
                         "than nx.  It cannot be combined with "
                         "--s21-plane-index.  Absent (the default): the "
                         "default policy, load column + 1.")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and print the call, write nothing, run no FDTD; "
                         "with --with-twin it prints the twin's arguments too "
                         "(that is where `loads` leaves the dict and s21_plane "
                         "becomes None)")
    ap.add_argument("--s11-settling", action="store_true",
                    help="attach the diagnostic settling block to the artefact "
                         "top level: both extraction paths' phasors, the "
                         "de-embed factor and the impedance each implies, so "
                         "one of the two s11 readings can be falsified (defect "
                         "DR-19).  Off by default; no number changes when it "
                         "is off and the key is then absent.")
    ap.add_argument("--measure-z-eff", action="store_true",
                    help="measure the complex impedance of the element on the "
                         "load's own column and attach it to the artefact top "
                         "level as z_eff_measurement: V_load from "
                         "edge_path_voltage over that column's E_z edges, "
                         "I_load from plate_current on the two FY faces that "
                         "straddle it, and z_eff = V_load / I_load at the "
                         "record's own DFT bin.  Off by default; no number "
                         "changes when it is off and the key is then absent.")
    ap.add_argument("--ms-x-window", nargs=2, type=float, default=None,
                    metavar=("FIRST_MM", "LAST_MM"),
                    help="probe-station window: the FIRST and LAST station, in "
                         "MILLIMETRES, e.g. --ms-x-window 3.4 13.0.  It is the "
                         "library's own x_first/x_last (emfit/studies.py:1177-"
                         "1178, :2455-2456, np.linspace at :2942) and nothing "
                         "else: n_stations stays at MS_N_STATIONS, so the "
                         "station COUNT does not move and only the positions "
                         "do -- which is what makes a before/after pair a test "
                         "of WHERE the fit sampled and not of how densely.  A "
                         "station on the lumped load's column is dropped from "
                         "the impedance fit (emfit/studies.py "
                         "_station_fit_selection), so a window whose x_last "
                         "lands on the load fits one station fewer than a "
                         "window that stops short of it; the default does "
                         "exactly that.  Absent (the default): x_first and "
                         "x_last are not passed at all and the call is what it "
                         "was, byte for byte.  Recorded in run.kwargs as "
                         "ms_x_window_mm only when set.")
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

    ap.add_argument("--nsteps", type=int, default=2400, metavar="N",
                    help="steps to march (default 2400, what every banked Run A "
                         "artefact was built on).  The excitation is a single "
                         "frequency CW, so only the march length changes: the "
                         "flag exists for a step-count convergence sweep and it "
                         "is the sole knob it moves.")

    ap.add_argument("--dump-load-edges", action="store_true",
                    help="record the phasor on EVERY E_z edge of the load's own "
                         "column -- edge_path_voltage over the same edges the "
                         "load is spread on, accumulated at the record's own "
                         "DFT bin on the same steps as the station voltages -- "
                         "and attach it to the artefact top level as "
                         "load_edge_dump: the edge indices, each phasor as re/im "
                         "plus magnitude and phase, and the load's x.  Off by "
                         "default; no number changes when it is off and the key "
                         "is then absent.")
    ap.add_argument("--dump-fields", action="store_true",
                    help="keep the last time step's E and H fields and the "
                         "plane-capture phasor blocks off the solver and write "
                         "them to <stem>_fields.npz beside the artefact.  The "
                         "four plane blocks need plane capture on; the library "
                         "reads that from EMFIT_PLANE_CAPTURE (an explicit "
                         "plane_capture kwarg would also do), and with capture "
                         "off those four keys are simply absent from the .npz.  "
                         "Off by default; no number changes when it is off and "
                         "no file is written.")

    # -- emfit-vis: the time-series dump of the march, and its selftest ------
    ap.add_argument(
        "--vis-dump", nargs="?", const=STRUCTURE_DUMP_SENTINEL,
        default=None, metavar="PATH",
        help="also write an emfit-vis time-series .npz (no argument: the "
             "--structure's own -- "
             f"{STRUCTURES['A']['vis_dump']} for A, "
             f"{STRUCTURES['B']['vis_dump']} for B) holding Ez on the "
             "j=j_centre z-cut "
             "along the line and on two x-cuts through it, with the frame "
             "indices and the mm/ns axes. This is a SECOND, independent "
             "product: --dump-fields still writes its own snapshot, and both "
             "can be asked for in the same run.")
    ap.add_argument(
        "--dump-stride", type=int, default=1, metavar="N",
        help="keep every Nth step in the emfit-vis dump (default 1: every "
             "step). Raised automatically, with a warning, if the planned "
             f"arrays would exceed the {VIS_BUDGET_MB:.0f} MB budget.")
    ap.add_argument(
        "--pulse-freq-ghz", type=float, default=None, metavar="GHZ",
        help="centre frequency of the pulse the emfit-vis dump records "
             f"(default {VIS_F_PULSE_HZ / 1e9:.1f} GHz). Only used "
             "together with --vis-dump, which excites the line with a "
             "pulse at this frequency instead of the default drive.")
    ap.add_argument(
        "--xcut-near-mm", type=float, default=20.4, metavar="MM",
        help="x position of the near x-cut frame of the emfit-vis dump "
             "(default 20.4 mm: on the line, just before the load).")
    ap.add_argument(
        "--xcut-far-mm", type=float, default=22.0, metavar="MM",
        help="x position of the far x-cut frame of the emfit-vis dump "
             "(default 22.0 mm: past the load).")
    ap.add_argument(
        "--selftest", nargs="?", const=VIS_SELFTEST_DEFAULT, default=None,
        metavar="PATH",
        help="write a synthetic emfit-vis .npz (numpy only: no grid, no "
             "solve), re-open it, check every key/dtype/shape and the "
             "measured velocity, print the JSON summary and exit 0. No "
             f"argument: {VIS_SELFTEST_DEFAULT}.")
    args = ap.parse_args(argv)
    # What terminates the cut (a --netlist) and how the line is driven (a
    # --vis-dump forces excite='pulse') both leave the artefact path alone, and
    # arm A's default path IS a tracked evidence document.  That is the whole
    # failure this file was repaired for, and it has ONE home below:
    # resolve_artefact_out, called before anything is written.
    # The arm comes from --structure alone. It is never inferred from the --out
    # filename: in a solver the physics is chosen by a flag, and a typo in a
    # path must not change the simulated load.
    structure = args.structure
    # The filename is still READ, but only to report a disagreement with the
    # arm actually run -- it never selects anything.  Read from the --out the
    # caller TYPED, before any default fills it in.
    stem_arm = (label_from_stem(Path(args.out).stem)
                if args.out is not None else None)
    if stem_arm is not None and stem_arm in STRUCTURES \
            and stem_arm != structure:
        sys.stderr.write(
            f"WARNING: the --out filename names arm {stem_arm} but this run is "
            f"arm {structure} ({STRUCTURES[structure]['load_ohm']:g} ohm); the "
            f"label follows the run, not the filename.\n")
    # The structure's numbers are DEFAULT VALUES, resolved here rather than in
    # the parser so that an explicit flag always wins: --structure B --load-ohm
    # 50 is B's paths with A's load, and the startup line below says so instead
    # of hiding which number came from where.
    if args.load_ohm is None:
        args.load_ohm = STRUCTURES[structure]["load_ohm"]
    # --vis-dump resolves BEFORE --out, because a dump IS a deviation -- it
    # forces excite='pulse' inside the solve -- and the rule below has to see
    # the RESOLVED value: a bare ``--vis-dump`` means "this arm's own dump",
    # which is a pulse run and must not be handed arm A's evidence artefact.
    if args.vis_dump == STRUCTURE_DUMP_SENTINEL:
        args.vis_dump = STRUCTURES[structure]["vis_dump"]
    # ONE home for "may this run write here".  A deviation (a dump, or a netlist
    # the arm does not own) with an implicit --out is redirected off an evidence
    # default, and ANY resolved path inside evidence/ that is not this arm's own
    # canonical CW document is refused -- here, at argument resolution, so the
    # refusal lands before the banner, before the trip thread and before the
    # first timestep, never mid-write.
    args.out = resolve_artefact_out(
        structure, out=args.out, netlist=args.netlist,
        vis_dump=args.vis_dump, default_out=STRUCTURES[structure]["out"])
    # The netlist is a default VALUE on the same footing as --load-ohm and
    # --out, resolved HERE and not in the parser -- and AFTER the path rule
    # above, so that "an explicit --netlist" there means one the CALLER typed.
    # An ARM's own netlist is different: it ships with the arm, so
    # ``--structure D`` alone may use it AND D's own default --out, and cannot
    # clobber A's certified reference.  The other two options were considered
    # and rejected: making --netlist required for D (a bare ``--structure D``
    # would then have no defined load), and putting the netlist in the row as
    # parsed JSON (the file is the interface; parsing it here would validate it
    # twice and drift).
    if args.netlist is None and STRUCTURES[structure].get("netlist"):
        args.netlist = STRUCTURES[structure]["netlist"]
    if args.selftest is not None:
        # The file format, not the physics: no mesh is built and no step is
        # taken, so this runs in a second and says nothing about the solve.
        print(json.dumps(vis_selftest(args.selftest), indent=2,
                         sort_keys=True, default=str))
        return 0
    # The label states the arm actually simulated -- always the resolved
    # structure, whatever the artefact happens to be called.
    label = args.label if args.label else structure

    out_path = Path(args.out).resolve()
    # Both resolved paths, out loud, before the solve: the dump's default used
    # to be structure-independent (evidence/vis_dump.npz for every arm), so a
    # B run with a bare --vis-dump would have overwritten A's picture.
    if args.netlist is not None:
        # The termination is the netlist, NOT the lumped resistor: --load-ohm is
        # still resolved (it is what frees the cut), but announcing "series_r
        # load 50 ohm" for a diode-terminated run is the provenance lie this
        # line exists to avoid.
        print(f"structure {structure}: NETLIST load "
              f"{Path(args.netlist).resolve()} (series_r termination replaced), "
              f"label {label}")
    else:
        print(f"structure {structure}: series_r load {float(args.load_ohm):g} ohm, "
              f"label {label}")
    print(f"artefact: {out_path}")
    print("vis: " + (str(Path(args.vis_dump).resolve())
                          if args.vis_dump is not None
                          else "(not requested)"))
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
        # -- emfit-vis: the time-series dump, when this run was asked for one --
        vis = None
        recorder = None
        dump_meta = None
        if args.vis_dump is not None:
            geo = vis_geometry(dict(kwargs))
            f_pulse_hz = (float(args.pulse_freq_ghz)
                          if args.pulse_freq_ghz else VIS_F_PULSE_HZ)
            stride, nt, nt_x, est_mb = _vis_plan_stride(
                int(kwargs["nsteps"]), int(args.dump_stride),
                geo["nx"], geo["ny"], geo["nz"])
            ix_near = vis_xcut_column(float(args.xcut_near_mm),
                                          geo["nx"], geo["cell_m"], "near")
            ix_far = vis_xcut_column(float(args.xcut_far_mm),
                                         geo["nx"], geo["cell_m"], "far")
            sys.stderr.write(
                f"VIS: {args.vis_dump}: {nt} frames of Ez on the "
                f"j={geo['j_cut']} z-cut ({geo['nx']}x{geo['nz']}) plus "
                f"{nt_x} frames of two x-cuts ({geo['ny']}x{geo['nz']}), "
                f"stride {stride}, ~{est_mb:.1f} MB\n"
                f"VIS: x-cuts at columns {ix_near} "
                f"({ix_near * geo['cell_m'] * 1e3:.2f} mm) and {ix_far} "
                f"({ix_far * geo['cell_m'] * 1e3:.2f} mm)\n"
                f"VIS: excite='pulse' at {f_pulse_hz / 1e9:.3f} GHz: the "
                "dump is the march of one packet, so the excitation is "
                "overridden for this run\n")
            recorder = _VisRecorder(
                nx=geo["nx"], ny=geo["ny"], nz=geo["nz"], nt=nt, nt_x=nt_x,
                stride=stride, j_cut=geo["j_cut"], ix_near=ix_near,
                ix_far=ix_far)
            dump_meta = {
                "nx": geo["nx"], "ny": geo["ny"], "nz": geo["nz"],
                "cell_m": geo["cell_m"], "j_cut": geo["j_cut"],
                "dump_stride": stride, "nsteps": int(kwargs["nsteps"]),
                "f_pulse_hz": f_pulse_hz,
                # Provenance, not geometry: which arm this run IS and what it
                # was terminated in. The dump cannot imply either.
                "structure_id": structure,
                "load_ohm": float(args.load_ohm),
                # Provenance again: which CIRCUIT terminated the cut.  Empty
                # when the load is the lumped resistor above, because then a
                # netlist in the file would describe something not in the run.
                "load_netlist_json": _netlist_json(kwargs.get("load_netlist")),
                "xcut_near_mm": ix_near * geo["cell_m"] * 1e3,
                "xcut_far_mm": ix_far * geo["cell_m"] * 1e3,
            }
            # A copy, always: without --with-twin ``loaded_kwargs`` IS
            # ``kwargs``, and this must not rewrite the record of what the
            # caller asked for (that record is reported as-run in the
            # artefact).
            # ``s21_plane`` goes with the single-tone extraction it names:
            # studies refuses it under excite="pulse" (the pulse reads its
            # band off the kept record, whose columns are the stations), and
            # the dump run's science is the packet, not S21.
            # ``load_trace=True`` is what fills the additive per-step trace
            # the dump carries (``load_t_ns`` / ``load_v`` / ``load_i``):
            # the element's own V(t) and I(t), one sample per step, read from
            # the same port the impedance extraction uses.  It goes on the
            # LOADED call only: the twin has no element, and
            # emfit/studies.py:3338-3343 refuses a trace with nothing to trace.
            loaded_kwargs = dict(loaded_kwargs, excite="pulse",
                                 f_pulse=f_pulse_hz, s21_plane=None,
                                 load_trace=True)
        t_call = time.monotonic()
        # The two dump flags go on the LOADED call only: the twin is load-free
        # by construction, and ``load_edge_dump`` refuses a record with no
        # series_r load (emfit/studies.py, the ValueError before the time loop),
        # so putting them on ``twin_kwargs`` would turn --with-twin into a
        # guaranteed failure.
        res = studies.microstrip_wave(**loaded_kwargs,
                                     s11_settling=args.s11_settling,
                                     z_eff_requested=args.measure_z_eff,
                                     load_edge_dump=args.dump_load_edges,
                                     field_snapshot=args.dump_fields,
                                     frame_callback=recorder)
        wall_call = time.monotonic() - t_call
        if recorder is not None and dump_meta is not None:
            # The analytic velocity is the BANKED parent figure and is
            # deliberately NOT taken from `res.beta`: this run is
            # pulse-excited, so its fitted beta comes from a truncated window
            # and moves with the step count (261.6 rad/m at 800 steps on the
            # default mesh -> 1.3995e8 m/s, 11 % under the parent figure),
            # which would make `v_analytic_m_s` and `t_traverse_ns` move with
            # the march length instead of recording the line.
            # `write_vis_dump` defaults `beta_rad_per_m` to
            # `VIS_BETA_BANKED_RAD_PER_M`, so `res.beta` is not passed.
            vis = write_vis_dump(args.vis_dump,
                                           **recorder.payload(), **dump_meta,
                                           # The traced element: allocated
                                           # because ``load_trace=True`` was
                                           # passed above, never re-derived
                                           # here.  ``None`` writes the "no
                                           # trace" form.
                                           load_v=res.load_trace_v,
                                           load_i=res.load_trace_i)
            vel = vis["velocity"]
            tt = vel["t_traverse_ns"]
            tt_txt = f"{tt:.4f}" if isinstance(tt, float) else "n/a"
            sys.stdout.write(
                f"VIS: wrote {vis['path']} "
                f"({vis['size_mb']:.1f} MB): {vis['nt']} Ez frames, "
                f"{vis['nt_x']} x-cut frames, v_measured="
                f"{vel['v_measured_m_s']:.6g} m/s"
                + (f" [NO MEASUREMENT: {vel['reason']}]" if not vel["measured"] else "")
                + ("" if vel["v_measured_reliable"] else
                   f" [NOT RELIABLE: {vel['velocity_note']}]")
                + f", t_traverse_ns={tt_txt} (analytic, "
                  f"v_analytic={vel['v_analytic_m_s']:.6g} m/s)"
                + ("" if res.load_trace_v is None else
                   f"; load trace {res.load_trace_v.size} samples, "
                   f"max|v|={float(np.max(np.abs(res.load_trace_v))):.6g} V, "
                   f"max|i|={float(np.max(np.abs(res.load_trace_i))):.6g} A")
                + "\n")
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
    # The declared tone, when the netlist declared one -- CONDITIONALLY, so a
    # run whose document named no tone (and every run with no --netlist) keeps
    # exactly the geometry it had before this key existed.
    qw = quarter_wave_records(g.get("load_netlist_quarter_wave"))
    if qw:
        geom["load_netlist_quarter_wave"] = qw
    # The netlist's own provenance, when one was applied -- CONDITIONALLY, for
    # the same reason as the tone above: a netlist-free run must keep exactly
    # the geometry it had before this key existed (absent means "no netlist",
    # never "the same netlist as last time").
    nl = netlist_geometry_record(kwargs.get("load_netlist"), args.netlist)
    if nl:
        geom["load_netlist"] = nl
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
    plane_from_default_policy = bool(args.s21_plane_index is None
                                     and args.s21_plane_col is None)
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

    # The passivity-coherence gate, on the pair this artefact actually
    # PUBLISHES: s11.magnitude (the two-wave |B/A| written at :3316) and |s21|
    # (s21.magnitude).  Computed once, here, so the s11 block's status, its own
    # numbers and the console line below all read one record.
    passivity = passivity_guard(s11_two_wave_mag, finite_or_none(abs(s21)))

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
            # build_kwargs rather than from --s21-plane-index or
            # --s21-plane-col -- either flag is a hand-picked column.
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
            "plane_policy": ("explicit" if (args.s21_plane_index is not None
                                            or args.s21_plane_col is not None)
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
            # The fit's own inputs and its beta, so the one-wave reflection
            # can be re-run from this file: _station_phasor_block.
            "station_phasors": _station_phasor_block(res),
            "deembed_distance_m": float(res.deembed_distance),
            "basis": (
                "gamma_port, the reflection moved to the port plane "
                "(emfit/studies.py:3266, declared at :1607; docstring "
                ":1527-1531).  Plane-independent: it does not move when the "
                "extraction plane moves.  "
                "modulus of B/A from fit_beta(n_wave=2), referred to z=0, plane-invariant at alpha=0, not de-embedded. phase_deg is unchanged and belongs to the one-wave station fit at the port plane, NOT to the magnitude beside it; no two-wave phase is reported because no two-wave beta is stored."),
            # The passivity-coherence gate: FAIL_PASSIVITY when the published
            # pair's |S11|^2 + |S21|^2 exceeds 1 + PASSIVITY_TOL, and the status
            # this writer has always published otherwise.  The status is the
            # one key the gate moves; nothing about the magnitudes above
            # changes because of it.
            "validation_status": (passivity["status"]
                                  if passivity["status"] is not None
                                  else "UNVALIDATED"),
            "validation_reason": (
                # Only a fired gate prepends, so an honest record keeps the
                # text it has always carried, character for character.
                (passivity["verdict"] + "  "
                 if passivity["status"] is not None else "")
                + "the magnitude above is the modulus of the two-wave B/A, not "
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
            # The gate's own numbers, so its verdict is recomputable from the
            # file: the sum it compared, the tolerance it compared against, and
            # the identity in words.  Written on EVERY record with a null
            # status when the gate did not fire -- an absent key could not be
            # told apart from a writer that never ran the gate at all.
            "passivity": passivity,
        },
        "s11_at_plane": {
            "magnitude": finite_or_none(abs(s11_at_plane)),
            "phase_deg": finite_or_none(np.degrees(np.angle(s11_at_plane))),
            "plane_index": res.s21_plane_index,
            "basis": (
                "gamma_plane, the reflection at the extraction plane itself "
                "(b_cut/a_cut).  A different quantity from s11, not "
                "interchangeable; null when the record was extracted over "
                "the station span.  A plane strictly beyond the load column "
                "reports no reflection coefficient, because past the load "
                "there is nothing left to reflect from: the element is "
                "behind the probe, so magnitude stays null and valid says "
                "so, with the reason beside it.  At the load's own column "
                "the ratio is still the element's reflection and the plane "
                "stays valid."),
            # Whether that plane carries a reflection of the element at all,
            # and why not when it does not.  Copied from the geometry the
            # library wrote beside the plane index, never re-derived here, so
            # the artefact and the code cannot disagree.  Both are null on a
            # record extracted over the station span, where no plane was
            # named and no such key exists.
            "valid": res.geometry.get("s11_at_plane_valid"),
            "invalid_reason": res.geometry.get("s11_at_plane_invalid_reason"),
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
    if res.s11_settling is not None:
        payload["s11_settling"] = res.s11_settling
    # Flag-off: the field is None and the key is ABSENT, so the artefact is the
    # one it was.  Same convention as the s11_settling block above.
    z_eff_block = _z_eff_block(res)
    if z_eff_block is not None:
        payload["z_eff_measurement"] = z_eff_block
    # Flag-off: ``_load_edge_block`` is None and the key is ABSENT, so the
    # artefact is the one it was.  Same convention as the two blocks above.
    load_edge_block = _load_edge_block(res) if args.dump_load_edges else None
    if load_edge_block is not None:
        payload["load_edge_dump"] = load_edge_block
    # Not flag-gated: the cut plane's own phasors are already computed and
    # stored on the record, so they cost nothing to write and the key is absent
    # only when the run did not take the cut branch at all.
    s21_plane_block = _s21_plane_block(res)
    if s21_plane_block is not None:
        payload["s21_plane"] = s21_plane_block
    # Before the JSON, so a snapshot that cannot be written fails the run rather
    # than leaving an artefact that claims a file which is not there.
    fields_path = (write_field_snapshot(res, out_path)
                   if args.dump_fields else None)
    write_json(out_path, payload)
    print(f"wrote {out_path}")
    if fields_path is not None:
        print(f"wrote {fields_path}")
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
    # The gate's verdict on that same line: the sum, the tolerance and the
    # status, so a run that publishes a non-passive pair says so in the console
    # and not only in the JSON.  ``ok`` is the unfired status, which is NOT
    # written into the artefact (that keeps its own UNVALIDATED).
    passivity_txt = (
        "passivity=not_evaluated(a published magnitude is absent)"
        if passivity["power_sum"] is None else
        f"passivity={passivity['power_sum']:.12f} "
        f"(tol {PASSIVITY_TOL:.1e}) "
        f"passivity_status={passivity['status'] or 'ok'}")
    print(f"label={label} cells={cells} wall={wall_s:.1f}s "
          f"peak_rss={peak_mb:.1f}MB "
          f"|s21|={abs(s21):.9f} arg={np.degrees(np.angle(s21)):.4f}deg "
          f"|s11|={s11_two_wave_txt} "
          f"(one-wave_station_fit |s11|={abs(s11):.6e}) "
          f"cut_plane={res.s21_plane_index} "
          f"{passivity_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
