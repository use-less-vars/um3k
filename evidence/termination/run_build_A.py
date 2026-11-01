#!/usr/bin/env python3
"""Run A of the absorbing-termination build: ONE graded run, ONE load, no reference.

What this run is
----------------
Source at port ``p1`` (the study's own soft source plane, ``ix_port``), a 50 ohm
``series_r`` :class:`emfit.board.Load` at port ``p2`` (the far end of the line),
extraction on the load's own cut plane via ``s21_plane="cut"``.  One run.  There
is deliberately **no reference run**: with ``reference=None`` the cut branch does
not raise, it degrades to ``zc_split = zc`` + ``line_s21(...)`` and sets
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
    4 = 0.4 mm cell, ``n_air`` 12, ``n_top`` 6, ``n_clean`` 96 (0.8 mm strip ->
    ``n_strip`` 2 cells at that cell), ``n_pml`` 6, ``n_ref`` 2, and ``n_line``
    taken from ``--n-line``.

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
    cells, so the earlier 357,616 read 27.3 % high): at the default ``n_line``
    54 the grid is **62 x 206 x 22 = 280,984 cells** (``nx = n_pml + n_ref +
    n_line = 6+2+54``; ``ny = 2*n_pml + n_strip + 2*n_clean = 12+2+192``;
    ``nz = n_sub + n_air + n_top = 4+12+6``; ``ix_port = n_pml + n_ref = 8``),
    dt 7.626299478123987e-13 s (set by the 0.4 mm cell, so the z extent does not
    move it), 2400 steps, 1.830 ns simulated.  Run E (``n_line`` 79) is
    87 x 206 x 22 = 394,284 cells.  An earlier revision of this file said
    68 x 218 x 28 = 415,072 cells, borrowed from ``evidence/h_refine/h040.json``
    [M]: that grid belongs to the eigensolver ladder row and is WRONG here.  The
    corrected figure is the one in ``README.md`` and in the commit message.

    Cost, and it is a FLOOR rather than a measurement: the six field components
    alone are ``6 x 8 B x cells`` = 13.5 MB on Run A (6 x 8 x 280,984 =
    13,487,232 B) and 18.9 MB on Run E (6 x 8 x 394,284 = 18,925,632 B).  That
    arithmetic excludes the materials matrices, the edge lists and interpreter
    overhead, so a peak RSS is strictly larger and is UNMEASURED -- as is the
    wall time, since no run of this build has ever been recorded
    (``evidence/termination/`` holds no ``build_A_50ohm.json`` and no
    ``build_E_50ohm.json``) -- against the per-run 1400 s wall gate and the
    ``--mem-ceiling-mb 2000`` trip that both runs are launched under; a trip
    writes a ``.trip.json`` marker and exits 3 or 4, and a trip is not a
    licence to relaunch.

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
        "n_strip": 2,
        "n_line": int(args.n_line),
        "n_pml": 6,
        "nsteps": 2400,
        "loads": (load,),
        "reference": None,
        "s21_plane": S21_PLANE,
        "excite": "cw",
    }
    check_mesh(kwargs)
    return kwargs


def describe_kwargs(kwargs: dict) -> dict:
    """JSON-safe view of the call, including the load specification (AC-6)."""
    from emfit.board import Load  # noqa: F401  (documented import site)

    loads = kwargs["loads"]
    return {
        "h_m": kwargs["h"],
        "cell": "h / n_sub",
        "n_sub": kwargs["n_sub"],
        "n_air": kwargs["n_air"],
        "n_top": kwargs["n_top"],
        "n_clean": kwargs["n_clean"],
        "n_strip": kwargs["n_strip"],
        "n_line": kwargs["n_line"],
        "n_pml": kwargs["n_pml"],
        "nsteps": kwargs["nsteps"],
        "excite": kwargs["excite"],
        "s21_plane": kwargs["s21_plane"],
        "reference": None,
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


def ac_block(res, *, load_mm: float, load_ohm: float, peak_mb: float,
             wall_s: float) -> dict:
    """AC-1..AC-7, each with the achieved value beside its pass/fail.

    A criterion that Run A structurally cannot close says so in
    ``closable_in_run_a``/``status`` rather than being scored on a proxy.  Bars are
    quoted from ``docs/design/absorbing_termination_scope.md:222-270`` [R] and are
    not adjusted here (AC-2).
    """
    import math

    s21 = complex(res.s21)
    s11 = complex(res.s11)
    s21_abs = abs(s21)
    s11_abs = abs(s11)
    gamma_plane = res.gamma_plane
    plane_index = res.s21_plane_index
    load_index = res.geometry.get("s21_plane_index")

    # --- AC-7's phase, and why it is the RAW one --------------------------
    # `line_s21` de-embeds with the run's OWN measured beta: `emfit/ports.py:
    # 1707-1731` returns `s21 * exp(+1j*beta*distance)`, and the cut branch
    # calls it as `line_s21(a_port, x_port, a_cut, x_cut, beta)`
    # (`emfit/studies.py:3242`).  So, with `t` the load's own transmission and
    # `d` the extraction distance,
    #
    #     arg(s21)     = arg t + (beta_meas - beta_true) * d   -> flat in L
    #     arg(s21_raw) = arg t - beta_true * d                -> slope -beta
    #
    # The de-embedded phase is degenerate by construction: whatever the line
    # does, its slope in L is ~0 because the de-embedding has already removed
    # beta*d using a beta measured from that same run.  AC-7 is therefore scored
    # on `s21.raw_phase_deg`, never on `s21.phase_deg`.
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
                "load_plane_index": load_index,
                "s21_plane_index": plane_index,
                "indices_agree": bool(load_index is not None
                                      and plane_index is not None
                                      and int(load_index) == int(plane_index)),
                "gamma_plane_recorded": bool(
                    gamma_plane is not None
                    and math.isfinite(complex(gamma_plane).real)
                    and math.isfinite(complex(gamma_plane).imag)),
            },
            "pass": bool(load_index is not None
                         and plane_index is not None
                         and int(load_index) == int(plane_index)
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
                            "run's own measured beta and is flat in L by "
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
                "note": ("The de-embedded slope is the one that should read "
                         "~0 -- it is degenerate by construction and must "
                         "never be quoted as a beta. The raw slope is the "
                         "AC-7 quantity, but from ONE run it equals "
                         "beta - arg(t)/dL: that assumes arg t = 0, and it is "
                         "only defined modulo the branch spacing above. "
                         "Neither number is an AC-7 verdict."),
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
    ap.add_argument("--dry-run", action="store_true",
                    help="build and print the call, write nothing, run no FDTD")
    args = ap.parse_args(argv)
    label = (args.label if args.label else
             (Path(args.out).stem.replace("build_", "").split("_")[0].upper()
              or LABEL))

    out_path = Path(args.out).resolve()
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
        print(json.dumps({
            "meta": meta,
            "call": {"function": "emfit.studies.microstrip_wave",
                     "kwargs": describe_kwargs(kwargs)},
            "artefact": str(out_path),
            "note": "dry run: no FDTD, nothing written",
        }, indent=2, sort_keys=True))
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
    trip = Trip(out_path, mem_ceiling_mb=args.mem_ceiling_mb,
                wall_limit_s=args.wall_limit_s,
                argv=meta["argv"], started_utc=started_utc).start()

    try:
        t_call = time.monotonic()
        res = studies.microstrip_wave(**kwargs)
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
    cells = int(g.get("nx", 0)) * int(g.get("ny", 0)) * int(g.get("nz", 0))

    # AC-7's beta_modal is deliberately NOT computed here: a hand-rolled call to
    # emfit.mode_profile on a reconstructed geometry would smuggle a number that
    # no AC-7 verdict may rest on. The field is emitted as null and said to be
    # null.
    beta_modal = None

    ac = ac_block(res, load_mm=args.load_at_mm, load_ohm=args.load_ohm,
                  peak_mb=peak_mb, wall_s=wall_s)
    ac["AC-7"]["beta_modal_recorded"] = beta_modal

    s21 = complex(res.s21)
    s21_raw = complex(res.s21_raw)
    gp = complex(res.gamma_plane)
    s11 = complex(res.s11)

    payload = {
        "meta": dict(meta, **{
            "status": "ok",
            "finished_utc": datetime.now(timezone.utc).isoformat(
                timespec="seconds"),
            "wall_call_s": wall_call,
            "wall_total_s": wall_s,
            "peak_rss_mb": peak_mb,
            "tripped": False,
        }),
        "run": {
            "label": label,
            "source_port": "p1",
            "load_port": "p2",
            "function": "emfit.studies.microstrip_wave",
            "kwargs": describe_kwargs(kwargs),
            "loaded_without_reference": bool(res.loaded_without_reference),
            "loaded_without_reference_note": (
                "True means no LineReference was supplied, so the cut branch "
                "degraded to zc_split = zc and line_s21(...): the line constant "
                "used to transport the port plane to the cut is the run's own "
                "zc/beta, not a load-free measurement. Stated, not hidden."),
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
            "phase_deg_basis": (
                "s21 de-embedded with this run's own measured beta "
                "(line_s21, emfit/ports.py:1729): slope in L ~0 BY "
                "CONSTRUCTION. Not the AC-7 quantity."),
            "raw_phase_deg_basis": (
                "s21_raw, no de-embedding applied: this is the AC-7 "
                "quantity, and it carries -beta*L."),
            "planes_m": [float(res.s21_planes[0]), float(res.s21_planes[1])],
            "s21_plane_index": res.s21_plane_index,
        },
        "s11": {
            "magnitude": abs(s11),
            "phase_deg": float(np.degrees(np.angle(s11))),
            "deembed_distance_m": float(res.deembed_distance),
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
            "z0_re": float(complex(res.z0).real),
            "z0_im": float(complex(res.z0).imag),
            "eps_eff": (None if res.loaded_without_reference
                        else float(res.eps_eff)),
            "gamma_re": float(complex(res.gamma).real),
            "gamma_im": float(complex(res.gamma).imag),
        },
        "ac": ac,
        "summary_line": res.summary(),
    }
    write_json(out_path, payload)
    print(f"wrote {out_path}")
    print(f"label={label} cells={cells} wall={wall_s:.1f}s "
          f"peak_rss={peak_mb:.1f}MB "
          f"|s21|={abs(s21):.9f} arg={np.degrees(np.angle(s21)):.4f}deg "
          f"|s11|={abs(s11):.6e} cut_plane={res.s21_plane_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
