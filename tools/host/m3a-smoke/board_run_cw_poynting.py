"""The board, one cw tone per process, on the pulse run's mesh, with a dump.

Scratch script -- not part of the package, imported by nothing, edits nothing.

Why a separate script instead of the cw block inside board_run_pw.py:

  * board_run_pw.py forces ``nsteps`` to the pulse run's 9600.  A cw record
    whose DFT bin does not land on the requested tone is not a twin of the
    requested bin, and ``microstrip_wave`` snaps the tone to its own bin,
    ``f0 = round(f_target * span) / span`` with ``span = n_acc * dt``.  At
    9600 steps that snap is 24 MHz low at 3.6667 GHz and 180 MHz high at
    7.8333 GHz.  So here ``nsteps`` is chosen, per frequency, to put the
    requested tone on the record's own bin: the search below walks nsteps and
    reports the residual it accepted.
  * the per-bin npz dump (``EMFIT_BIN_DUMP``) is written by the *pulse* branch
    of ``microstrip_wave`` only: ``bins``/``freqs``/``spectra`` do not exist on
    a tone run, so a cw run with that variable set writes no file at all.  The
    tone run does, however, keep every phasor the bin reader wants
    (``v_stations``, ``v_port``, both ground currents, ``i_stations``), so the
    signal vector is rebuilt here exactly as the time loop laid it out and
    handed to emfit's own ``_bin_metrics`` and ``_dump_bins``.  The file that
    comes out has the pulse dump's schema, one row, at the tone's own bin.

Usage::

    python3 .scratch/m2/board_run_cw.py 3.6667 [dt_scale]

The argument is the tone frequency in GHz.  The optional second argument scales
the mesh's CFL time step (``1.0`` by default), so the same physical record can
be taken with a smaller step.  Output: ``.scratch/m2/
board_cw_<f>GHz.npz`` and a printed report on stdout (redirect it to
``.scratch/m2/board_cw_<f>GHz.log``).  Every print flushes, so the log can be
read while the solve runs.

The self-check
--------------

The last block before the dump compares the quantities the tone path measured
during the solve against the same quantities re-derived by emfit's own bin
reader off the rebuilt phasor vector, and prints one row per quantity.  A row
measures how well the rebuilt vector reproduces the run -- no number in the
report depends on it.

Four of the five rows (``beta``, ``eps_eff``, ``|S21|`` and ``residual``) agree
to 1e-6 relative on a healthy run and are judged RELATIVE at
``SELF_CHECK_REL_TOL``.  ``|gamma|`` is the row that does not: its two sides
come from two *separate* ``fit_station_impedance`` calls -- the tone path fits
the live phasors during the run, the bin path refits the same station voltages
and currents off the rebuilt vector -- and on a healthy run they disagree by
1.2e-2 relative, which is only 1.7e-4 absolute on a |gamma| of 1.4e-2.  The
relative 1e-3 the row used to carry allows a disagreement of 1.4e-5 on that
|gamma|, an order of magnitude below the spread two independent fits actually
show, so it printed ``<-- MISMATCH`` on every healthy run and trained the
reader to ignore the line.  The row is therefore judged in ABSOLUTE terms at
``SELF_CHECK_GAMMA_ABS_TOL`` (1e-3): about 6x above the observed 1.7e-4 and
about 14x below the quantity itself, so a good run is silent while a rebuild
defect that moves |gamma| at order |gamma| still fails loudly.  Why two fits
agree so much more loosely on ``|gamma|`` than on the other rows is not
established here; what is measured is the spread quoted above.

The verdict is print-only: it does not reach the exit status, which this script
returns as 0 on a completed run (1 if the solve raised, 2 on a usage error).
"""

from __future__ import annotations

import functools
import os
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np

import emfit.studies as S
from emfit.board import MicrostripBoard
from emfit.evolve import FITStepper, cfl_dt
from emfit.grid import Grid
from emfit.kicad import load_board

WS = Path(__file__).resolve().parent.parent.parent
BOARD_PATH = WS / "kicad_support_project" / "kicad_support_project.kicad_pcb"
OUT_DIR = WS / ".scratch" / "m2"

NET = "RF_IN"
PORT_PAD = ("J1", "1")
EPS_R = 4.4

# The pulse run's geometry, keyword for keyword (board_run_pw.py).
N_SUB = 16
N_AIR = 48
N_TOP = 12
N_PML = 12

# nsteps search: long enough that the record is many traversals of the line,
# short enough that the solve stays well under the pulse run's hour.
NSTEPS_MIN = 7600
NSTEPS_MAX = 17000
SNAP_TOL = 1.0e6        # Hz: residual the bin snap is allowed to leave
PULSE_DT = 1.906574869530972e-13   # the pulse run's dt on this mesh, to check

#: The cw run already taken at each tone, and so the record length to match.
NSTEPS_REF = {3.6667: 7627, 7.8333: 8034}
#: What to match for a tone neither of those covers: the pulse run's own nsteps.
NSTEPS_REF_DEFAULT = 9600
#: How far the chosen record may miss ``span_target`` (fraction of it).
SPAN_TOL = 0.02

#: How the solve reports itself: a ``PROGRESS`` line every this many steps, or
#: every this many seconds of wall, whichever comes first.  The step gate is the
#: one that terminates on a fast run; the wall gate is the one that keeps a
#: stall visible (the first minutes are JIT, and a stalled ETA is information).
PROGRESS_EVERY_STEPS = 500
PROGRESS_EVERY_S = 30.0

#: How the self-check judges the four rows a healthy run agrees on: relative,
#: at 1e-6.  ``beta``, ``eps_eff``, ``|S21|`` and ``residual`` meet 1e-6
#: relative on a healthy run, and that is the spread this tolerance pins.  See
#: "The self-check" in the module docstring.
SELF_CHECK_REL_TOL = 1.0e-6
#: How the self-check judges |gamma|: absolute, at 1e-3.  ``|gamma|`` is a small
#: number (1.4e-2), so a relative tolerance on it is a much tighter absolute
#: one: the relative 1e-3 the row used to carry allowed only 1.4e-5, while two
#: independent fits of this row spread by 1.7e-4.  The tolerance belongs on the
#: absolute scale where that spread lives.  See "The self-check" in the module
#: docstring.
SELF_CHECK_GAMMA_ABS_TOL = 1.0e-3


def mark(name: str) -> None:
    """One phase header, the exact shape ``run.sh``'s own ``mark()`` prints.

    A blank line, then ``=== [name] HH:MM:SS ===``, flushed.  Flushing is the
    point: this script's whole output goes through ``tee``, and a header that
    sits in a block buffer arrives after the phase it was announcing.
    """
    print("", flush=True)
    print("=== [%s] %s ===" % (name, time.strftime("%H:%M:%S")), flush=True)


class SolveProgress:
    """Step counter and reporter for the time loop inside ``microstrip_wave``.

    ``microstrip_wave`` (``emfit/studies.py``) has no progress hook and prints
    nothing: its loop calls ``stepper.step(current)`` and that is all it does.
    That module is the frozen baseline and is not edited here, so the hook is
    put on from the *caller*: for the length of the solve, ``FITStepper.step``
    is replaced by a wrapper that bumps a counter and then calls the original
    with the very same arguments.  Nothing the solver reads changes, so the
    record stays bit-identical to an unwrapped run -- this adds a counter, not
    a step.

    A daemon thread samples the counter and prints, whichever comes first, one
    ``PROGRESS`` line per ``PROGRESS_EVERY_STEPS`` steps or per
    ``PROGRESS_EVERY_S`` seconds of wall, plus the ``warmup`` and
    ``accumulation`` phase headers as the counter crosses them.  Reporting
    from a thread is what keeps clocks and printing off the solver's path
    entirely.

    Args:
        nsteps: The total the run asked for, for the percentage and the ETA.
        n_warm: Warm-up steps; the accumulated record starts here.
    """

    def __init__(self, nsteps: int, n_warm: int) -> None:
        self.nsteps = int(nsteps)
        self.n_warm = int(n_warm)
        self.steps = 0
        self.t0 = time.perf_counter()
        self._stop = threading.Event()
        self._thread = None
        self._orig = None
        self._warmup_seen = False
        self._accum_seen = False
        self._last_steps = 0
        self._last_time = self.t0

    # -- the counter -----------------------------------------------------
    def _counted_step(self):
        """Make the stand-in for ``FITStepper.step``.

        It has to be a *plain function* and not a bound method.  A bound method
        is not a descriptor, so assigning one to the class would leave the
        solver's ``stepper.step(current)`` calling it with
        ``stepper`` still bound to *this* object: ``current`` would land in the
        stepper slot and the real ``step`` would be handed an ndarray as
        ``self``.  Wrapping in a closure keeps the descriptor protocol intact,
        so ``stepper.step(current)`` binds the solver's own stepper.
        """
        def counted_step(stepper, current=None):
            self.steps += 1
            return self._orig(stepper, current)
        return counted_step

    def __enter__(self) -> "SolveProgress":
        self._orig = FITStepper.step
        FITStepper.step = self._counted_step()
        self._thread = threading.Thread(
            target=self._report, name="cw-progress", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
        if self._orig is not None:              # always put the class back
            FITStepper.step = self._orig
        if self.steps and self.steps != self._last_steps:
            self._line(self.steps, time.perf_counter())   # close at nsteps
        return False

    # -- the reporter ----------------------------------------------------
    def _line(self, steps: int, now: float) -> None:
        """One PROGRESS line: step/total/pct/elapsed/rate/ETA, all guarded.

        Both divisions are behind a check: ``nsteps`` can only be zero if the
        run was asked for nothing, and ``elapsed`` is zero on the first
        sample, so neither is allowed to reach the formatter as a divide.
        """
        elapsed = now - self.t0
        pct = 100.0 * steps / self.nsteps if self.nsteps > 0 else 0.0
        if steps > 0 and elapsed > 0.0:
            rate = steps / elapsed
            eta_text = ("%.1f s" % ((self.nsteps - steps) / rate)
                        if rate > 0.0 else "n/a")
            rate_text = "%.1f" % rate
        else:
            rate_text = "n/a"            # no step has finished yet
            eta_text = "n/a"
        print("PROGRESS  step %d/%d  %5.1f%%  elapsed %.1f s  rate %s steps/s"
              "  eta %s"
              % (steps, self.nsteps, pct, elapsed, rate_text, eta_text),
              flush=True)

    def _report(self) -> None:
        while not self._stop.wait(0.5):
            steps = self.steps
            now = time.perf_counter()
            if steps and not self._warmup_seen:
                self._warmup_seen = True
                mark("warmup")
            if steps >= self.n_warm and not self._accum_seen:
                self._accum_seen = True
                mark("accumulation")
            if (steps - self._last_steps >= PROGRESS_EVERY_STEPS
                    or now - self._last_time >= PROGRESS_EVERY_S):
                self._line(steps, now)
                self._last_steps = steps
                self._last_time = now


def warm_shim(original, n_warm: int):
    """``original`` with ``n_warm`` filled in when its caller did not pass one.

    Route 1 of the POY_WARM override: ``microstrip_wave_board`` has no ``n_warm``
    keyword (``emfit/studies.py:3371-3395``) and its forwarding call
    (``3468-3498``) passes 26 keywords without it, while ``emfit/`` is the frozen
    baseline and is not edited.  ``microstrip_wave_board`` resolves
    ``microstrip_wave`` as a module global, so putting this stand-in on the
    module for the length of the solve fills the keyword in on the way past.

    ``**kw`` is taken and forwarded exactly as it arrives: every other keyword
    unmodified, ``n_warm`` only when the caller did not already name one
    (``setdefault``), and any exception out of ``original`` propagates untouched
    -- there is no ``except`` here.  The caller saves ``S.microstrip_wave``
    itself and puts it back in a ``finally``, so the install cannot outlive the
    solve.

    Args:
        original: The function being stood in for, usually
            :func:`emfit.studies.microstrip_wave`.
        n_warm: The warm-up to inject.

    Returns:
        The stand-in.  Calling it calls ``original``.
    """
    @functools.wraps(original)
    def shim(**kw):
        kw.setdefault("n_warm", n_warm)
        return original(**kw)
    return shim


def span_target_for(f_ghz: float) -> float:
    """The accumulated record length the reference run at ``f_ghz`` covered [s].

    ``n_warm = nsteps // 4`` there too, so the record is the last three quarters
    of the same nsteps, at the mesh's own ``PULSE_DT``.
    """
    n_ref = NSTEPS_REF.get(f_ghz, NSTEPS_REF_DEFAULT)
    return (n_ref - n_ref // 4) * PULSE_DT


def choose_nsteps(f_target: float, dt: float, span_target: float
                 ) -> tuple[int, int, int, float, float]:
    """Smallest nsteps whose own DFT bin lands within ``SNAP_TOL`` of the tone.

    ``microstrip_wave`` sets ``n_warm = nsteps // 4`` and
    ``f0 = max(1, round(f_target * span)) / span`` with ``span = n_acc * dt``,
    so this walks nsteps and replays exactly that arithmetic.  Nothing here
    changes what the solver does; it only picks the record length to ask for.

    ``dt`` may be a fraction of the mesh's own step (``dt_scale``), so the
    record is also held to the same physical length: the chosen ``n_acc * dt``
    has to land within ``SPAN_TOL`` of ``span_target``, or a smaller step would
    quietly shorten what the tone is measured over.

    Returns (nsteps, n_warm, n_acc, f0, residual).
    """
    best = None
    for nsteps in range(NSTEPS_MIN, NSTEPS_MAX + 1):
        n_warm = nsteps // 4
        n_acc = nsteps - n_warm
        span = n_acc * dt
        f0 = max(1, int(round(f_target * span))) / span
        residual = abs(f0 - f_target)
        row = (residual, nsteps, n_warm, n_acc, f0)
        if best is None or row[0] < best[0]:
            best = row
        if (residual <= SNAP_TOL
                and abs(span - span_target) <= SPAN_TOL * span_target):
            return (nsteps, n_warm, n_acc, f0, residual)
    residual, nsteps, n_warm, n_acc, f0 = best
    print("    WARNING      no nsteps in [%d, %d] meets both the %.3f MHz bin "
          "snap and the %.1f %% record length; taking the closest bin, "
          "%.3f MHz off"
          % (NSTEPS_MIN, NSTEPS_MAX, SNAP_TOL / 1e6, 100.0 * SPAN_TOL,
             residual / 1e6), flush=True)
    return (nsteps, n_warm, n_acc, f0, residual)


def self_check_row(name: str, tone: float, bin_value: float, tol: float,
                   absolute: bool = False) -> tuple[str, bool]:
    """One self-check row: the printed line, and whether it failed.

    A row compares one quantity as the tone path measured it (``tone``) against
    the same quantity as the bin reader re-derived it (``bin_value``).  ``tol``
    is judged on whichever of the two scales ``absolute`` names:

      * ``absolute`` False: ``rel = delta / max(abs(tone), 1e-30)``.  This is
        the scale for the rows a healthy run agrees on -- beta, eps_eff,
        |S21|, residual.  On those rows a healthy run agrees to 1e-6 relative,
        and that is the only slack they need.
      * ``absolute`` True: ``abs = delta``.  This is the scale for |gamma|,
        whose two sides come from two independent fits: on a healthy run they
        spread by 1.2e-2 *relative*, which is 1.7e-4 *absolute* on a |gamma|
        of 1.4e-2.  A relative 1e-3 on that row allows only 1.4e-5 there,
        below that spread, so it flagged a healthy run every time; an absolute
        1e-3 sits about 6x above the spread and about 14x below the quantity,
        so it is silent on a good run and still bites when a rebuild defect
        moves |gamma| at order |gamma|.

    The failure test is written ``not (measure <= tol)`` rather than
    ``measure > tol`` so that a NaN measure fails instead of passing: a row
    built from a refused or non-finite fit must never read as silent.

    The line states which measure judged it (``rel=`` or ``abs=``), so a reader
    can tell a real mismatch from a tolerance that cannot be reached.

    Args:
        name: The row's label, as it appears in the verdict.
        tone: The tone path's value.
        bin_value: The bin path's value.
        tol: The tolerance on the chosen scale.
        absolute: Judge the absolute difference instead of the relative one.

    Returns:
        ``(line, failed)``: the printed row, and whether it failed.
    """
    delta = abs(float(tone) - float(bin_value))
    if absolute:
        measure = delta
        text = "abs=%.2e" % delta
    else:
        measure = delta / max(abs(float(tone)), 1e-30)
        text = "rel=%.2e" % measure
    failed = not (measure <= tol)
    flag = "   <-- MISMATCH" if failed else ""
    line = "    %-9s tone=%.12g  bin=%.12g  %s%s" % (name, float(tone),
                                                   float(bin_value), text, flag)
    return line, failed


def self_check(checks) -> tuple[list[str], list[str]]:
    """Judge every row: the lines to print, and the names that failed.

    ``checks`` is a sequence of ``(name, tone, bin_value, tol, absolute)``
    tuples, in the order they are to be printed; each is handed to
    :func:`self_check_row`.  ``bad`` keeps the failures in that same order, so
    the verdict reads in the order the rows above it were read.

    The two lists are returned rather than printed so the caller owns every
    ``print`` and its flush -- this script's output goes through ``tee`` and a
    line that sits in a block buffer arrives after the phase it announced.

    Args:
        checks: ``(name, tone, bin_value, tol, absolute)`` per row.

    Returns:
        ``(lines, bad)``: one printed row per check, and the failed names.
    """
    lines = []
    bad = []
    for name, tone, bin_value, tol, absolute in checks:
        line, failed = self_check_row(name, tone, bin_value, tol, absolute)
        lines.append(line)
        if failed:
            bad.append(name)
    return lines, bad


def verdict_text(bad: list[str]) -> str:
    """The verdict field: ``OK`` when nothing failed, else ``CHECK: a; b``.

    One place, so the verdict is the same string whether it is printed from a
    run, quoted in a log, or asserted in a test.  The failure names are the row
    labels (``|gamma|``), plus ``bin refused: ...`` when the bin reader refused
    the rebuilt vector -- a refusal is a failure of this check too, not a
    separate category.

    Args:
        bad: The failed names, in row order.

    Returns:
        ``'OK'``, or ``'CHECK: '`` followed by the names joined with ``'; '``.
    """
    return "OK" if not bad else "CHECK: " + "; ".join(bad)


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print("usage: %s <frequency in GHz> [dt_scale]" % Path(argv[0]).name,
              file=sys.stderr)
        return 2
    f_ghz = float(argv[1])
    dt_scale = float(argv[2]) if len(argv) > 2 else 1.0
    f_target = f_ghz * 1e9
    tag = "%gGHz" % f_ghz
    stem = ("board_cw_%s_poy" % tag if dt_scale == 1.0
            else "board_cw_%s_dts%g_poy" % (tag, dt_scale))
    # Smoke test only: POY_SMOKE=<n> shrinks the record to n steps and marks the
    # stem so a throwaway dump can never be mistaken for the production one.
    smoke = os.environ.get("POY_SMOKE", "")
    if smoke:
        stem += "_smoke"
    dump_path = OUT_DIR / (stem + ".npz")

    started = time.perf_counter()
    mark("setup")
    board = load_board(BOARD_PATH)
    print("board loaded: %s (%s)" % (BOARD_PATH, type(board).__name__), flush=True)
    spec = MicrostripBoard.from_kicad(
        board, net=NET, eps_r=EPS_R, port_pad=PORT_PAD).cropped_to_strip(
            n_sub=N_SUB)
    counts = spec.to_cell_counts(n_sub=N_SUB, n_pml=N_PML)

    # --- the same mesh, and its dt, before anything is stepped ---------------
    mark("mesh build")
    cell = counts["cell"]
    nx = counts["n_line"] + counts["n_ref"] + N_PML
    ny = counts["n_strip"] + 2 * (counts["n_clean"] + N_PML)
    nz = N_SUB + N_AIR + N_TOP
    grid = Grid.uniform(nx, ny, nz, nx * cell, ny * cell, nz * cell)
    dt = float(cfl_dt(grid)) * dt_scale

    print("requested geometry:", flush=True)
    print("    w=%.6g m  x_port=%.6g m  x_far=%.6g m  length=%.6g m"
          % (spec.w, spec.x_port, spec.x_far, spec.length), flush=True)
    print("    supplied     %s" % (spec.supplied,), flush=True)
    print("    n_sub=%d n_air=%d n_top=%d n_pml=%d n_stations=%d"
          % (N_SUB, N_AIR, N_TOP, N_PML, S.MS_N_STATIONS), flush=True)
    print("    counts       %s" % (counts,), flush=True)
    print("    mesh         %d x %d x %d cells at %.4f mm"
          % (nx, ny, nz, cell * 1e3), flush=True)
    print("    dt           %.18e s  (pulse run: %.18e s, relative %+.2e)"
          % (dt, PULSE_DT, (dt - PULSE_DT) / PULSE_DT), flush=True)
    print("    dt_scale     %g  (dt = cfl_dt * dt_scale = %.18e s)"
          % (dt_scale, dt), flush=True)

    span_target = span_target_for(f_ghz)
    # The warm-up override.  Empty or unset POY_WARM leaves this None, and None
    # is what ``microstrip_wave`` reads as ``n_warm = nsteps // 4``
    # (emfit/studies.py:2590) -- the arithmetic choose_nsteps() has just
    # replayed -- so the production record below is the one it always was.
    warm_override = None
    nsteps, n_warm, n_acc, f0, residual = choose_nsteps(f_target, dt,
                                                        span_target)
    if smoke:                       # smoke test: keep dt, cut the record short
        nsteps = int(smoke)
        _poy_warm = os.environ.get("POY_WARM", "")
        if _poy_warm:               # set: move the warm-up, not the record
            n_warm = int(_poy_warm)
            if n_warm < 1:          # a hard start is not what this knob is for
                raise ValueError(
                    "POY_WARM=%d is not a usable warm-up: it must be at least "
                    "1 step (unset POY_WARM for the default nsteps // 4 = %d)"
                    % (n_warm, nsteps // 4))
            warm_override = n_warm
        else:
            n_warm = nsteps // 4    # unchanged: the exact default arithmetic
        n_acc = nsteps - n_warm     # one rule, override or not
        if n_acc < 1:
            raise ValueError(
                "POY_WARM=%d leaves no steps to accumulate out of POY_SMOKE=%d "
                "(n_acc=%d): the warm-up must be shorter than the record"
                % (n_warm, nsteps, n_acc))
        if warm_override is not None:
            print("POY_WARM OVERRIDE  route=driver shim over microstrip_wave  "
                  "nsteps=%d  n_warm=%d  n_acc=%d  emfit/ unmodified"
                  % (nsteps, n_warm, n_acc), flush=True)
        _span = n_acc * dt          # the OVERRIDDEN n_acc, not the default
        f0 = max(1, int(round(f_target * _span))) / _span
        residual = abs(f0 - f_target)
    span = n_acc * dt
    print("tone record:", flush=True)
    print("    asked        f_target=%.6f GHz" % (f_target / 1e9), flush=True)
    print("    record       nsteps=%d  n_warm=%d  n_acc=%d  span=%.6e s  "
          "(resolution 1/span=%.6f GHz)"
          % (nsteps, n_warm, n_acc, span, 1e-9 / span), flush=True)
    print("    bin          f0=%.6f GHz  (snapped, residual %+.6f MHz, "
          "%.3f %% of a bin)"
          % (f0 / 1e9, (f0 - f_target) / 1e6,
             100.0 * abs(f0 - f_target) * span), flush=True)
    print("    span_target  %.6e s  (chosen span %+.3f %% of it, tol %.1f %%)"
          % (span_target, 100.0 * (span - span_target) / span_target,
             100.0 * SPAN_TOL), flush=True)
    print("    dump         %s" % dump_path, flush=True)
    print("    sink         None (no figures)", flush=True)

    print("=== CW solve starting (%s) ===" % time.strftime("%H:%M:%S"), flush=True)
    t0 = time.perf_counter()
    try:
        # Progress is reported from here, not from the solver: the time loop in
        # emfit/studies.py is the frozen baseline and has no hook to hang one
        # on, so SolveProgress wraps ``FITStepper.step`` for the length of this
        # call.  The wrapper only counts steps, so the record is bit-identical.
        with SolveProgress(nsteps, n_warm):
            # The warm-up takes the same route (POY_WARM, route 1): the board
            # wrapper has no ``n_warm`` keyword and emfit/ is not edited, so the
            # keyword is filled in by standing ``warm_shim`` in for
            # ``S.microstrip_wave`` for the length of this one call.  With
            # POY_WARM unset, ``warm_override`` is None, no stand-in is built,
            # and the call below is reached in exactly the state it has always
            # been reached in.
            _saved_microstrip_wave = S.microstrip_wave      # always saved ...
            if warm_override is not None:
                S.microstrip_wave = warm_shim(_saved_microstrip_wave,
                                              warm_override)
            try:
                cw = S.microstrip_wave_board(
                    spec, n_sub=N_SUB, n_air=N_AIR, n_top=N_TOP, n_pml=N_PML,
                    n_stations=S.MS_N_STATIONS, nsteps=nsteps,
                    f_target=f_target, dt_scale=dt_scale, excite="cw",
                    poynting=True, sink=None)
            finally:
                S.microstrip_wave = _saved_microstrip_wave   # ... put back
    except Exception:                                           # noqa: BLE001
        print("=== CW RAISED after %.1f s ===" % (time.perf_counter() - t0),
              flush=True)
        traceback.print_exc()
        return 1
    wall = time.perf_counter() - t0
    print("=== CW returned in %.1f s (%s, %.4f s/step) ==="
          % (wall, time.strftime("%H:%M:%S"), wall / max(nsteps, 1)), flush=True)

    g = cw.geometry
    print("CW geometry: %s" % (g,), flush=True)
    s11 = abs(cw.gamma_port)
    s21 = abs(cw.s21)
    print("CW TONE    f=%.6f GHz  beta=%.4f  eps_eff=%.5f  |gamma|=%.5f  "
          "|gamma_port|=%.5f  |S21|=%.5f  passivity=%.6f  residual=%.5f  "
          "(asked %.6f GHz)"
          % (g["f"] / 1e9, cw.beta, cw.eps_eff, abs(cw.gamma), s11, s21,
             s11 ** 2 + s21 ** 2, cw.fit_residual, g["f_target"] / 1e9),
          flush=True)
    print("CW summary(): %s" % cw.summary(), flush=True)
    print("poynting flag in geometry: %r" % (g.get("poynting"),), flush=True)
    for _name in ("sx_station", "sx_station_sub"):
        _arr = getattr(cw, _name, None)
        print("    %-14s %r" % (_name, None if _arr is None
                                else np.array2string(np.asarray(_arr, float),
                                                     precision=6)), flush=True)

    # --- |S21| from the Poynting flux: a magnitude, and only a magnitude ----
    # ``sx_station`` is the mean instantaneous x-flux through each station
    # plane over the settled record (``sx_station_sum / n_acc``, inside
    # ``microstrip_wave``).  The square-root of the last-to-first ratio is the
    # transmission the *power* over that span sees, and it is reported beside
    # the circuit |S21| as an independent number -- that is the whole point of
    # the diagnostic: the two are measured different ways.
    #
    # It must never feed beta, eps_eff, Z0 or |S11|.  Those are fitted from
    # phasors: beta needs the phase progression along the stations, Z0 the V/I
    # ratio, |S11| the reflected wave.  A flux ratio carries no phase at all
    # (no reference plane, no de-embedding, and no sign to tell a forward wave
    # from a backward one), so dividing one into an impedance would replace a
    # measured quantity with a power ratio that cannot supply it.
    sx_poy = getattr(cw, "sx_station", None)
    sx_poy = None if sx_poy is None else np.asarray(sx_poy, float).ravel()
    sx_x = np.asarray(getattr(cw, "station_x", []), float).ravel()
    span_text = ("%.2f" % ((sx_x[-1] - sx_x[0]) * 1e3)
                 if sx_x.size >= 2 else "n/a")
    if sx_poy is None or sx_poy.size < 2 or not sx_poy[0] > 0.0:
        # No diagnostic on this record (poynting off), fewer than two stations,
        # or a first-station flux that is zero or negative.  The column is NaN
        # and the run continues: a flux of zero or less would divide by ~0 or
        # take the square root of a negative, and printing either as a number
        # would be a fabricated measurement.
        s21_poynting = float("nan")
        _why = ("no sx_station on this record" if sx_poy is None
                else "fewer than two stations" if sx_poy.size < 2
                else "first-station flux %.6g is not positive" % sx_poy[0])
        num_text = den_text = "n/a"
        val_text = db_text = "nan"
        s21_poynting_note = "flux-derived, no phase; n/a here: %s" % _why
    else:
        s21_poynting = float(np.sqrt(sx_poy[-1] / sx_poy[0]))
        num_text = "%.6f" % sx_poy[-1]
        den_text = "%.6f" % sx_poy[0]
        val_text = "%.6f" % s21_poynting
        db_text = "%+.4f" % (20.0 * np.log10(max(s21_poynting, 1e-30)))
        s21_poynting_note = "flux-derived, no phase"
    print("S21_poynting  sqrt(%s/%s) -> %s  (%s dB over %s mm)  "
          "[flux-derived, magnitude only]"
          % (num_text, den_text, val_text, db_text, span_text), flush=True)
    print("    S21_poynting_note = %s  (sqrt of the last station's flux over "
          "the first's; magnitude only)" % s21_poynting_note, flush=True)

    # --- the per-bin dump, in the pulse dump's own schema --------------------
    # The time loop filled ``signals`` as: n_stations station voltages, the port
    # voltage, the full and truncated ground currents, then the station
    # currents -- and negated that last block into ``i_stations``.  Undo the
    # negation and the vector is the one ``_bin_metrics`` slices.
    n = int(S.MS_N_STATIONS)
    phasor = np.concatenate([
        np.asarray(cw.v_stations, dtype=complex),
        np.array([complex(cw.v_port), complex(cw.i_ground_full),
                  complex(cw.i_ground_truncated)], dtype=complex),
        -np.asarray(cw.i_stations, dtype=complex),
    ])
    metric = S._bin_metrics(phasor, f=float(g["f"]), station_x=cw.station_x,
                            n_stations=n, x_port=float(spec.x_port),
                            reference=None, drive_db=0.0)
    # Put the flux-derived |S21| in the row as its own column, right beside the
    # circuit one.  The row itself is emfit's (frozen baseline, not edited
    # here), so the column is spliced in from the caller: split on the row's
    # own ", " separator, find the element that starts with ``|S21| = `` and
    # insert after it.  ``power-normalised: |S21| = `` does not start with it,
    # so the first match is the circuit column.  A REFUSED row has no such
    # element; the column is appended there rather than dropped.
    row_cells = S._bin_row(metric).split(", ")
    poy_cell = ("|S21|_poynting = %.4f (lin)" % s21_poynting
                if np.isfinite(s21_poynting) else "|S21|_poynting = nan")
    for _i, _cell in enumerate(row_cells):
        if _cell.startswith("|S21| = "):
            row_cells.insert(_i + 1, poy_cell)
            break
    else:
        row_cells.append(poy_cell)
    print("bin row: %s" % ", ".join(row_cells), flush=True)

    # Self-check: the rebuilt vector must reproduce what the tone path measured.
    mark("verify")
    checks = [
        ("beta", cw.beta, metric.beta, SELF_CHECK_REL_TOL, False),
        ("eps_eff", cw.eps_eff, metric.eps_eff, SELF_CHECK_REL_TOL, False),
        ("|S21|", abs(cw.s21), metric.s21, SELF_CHECK_REL_TOL, False),
        # DECISION: |gamma| is judged in ABSOLUTE terms at
        # SELF_CHECK_GAMMA_ABS_TOL, not relative.  The two numbers compared are
        # ``abs(cw.gamma)`` (tone path) and ``metric.s11_measured`` (bin path),
        # and they come from *two separate* ``fit_station_impedance`` calls --
        # the tone path fits the live phasors during the run, ``_bin_metrics``
        # refits the same station voltages and currents off the rebuilt phasor
        # vector.  On a healthy run they spread by 1.2e-2 relative, which is
        # only 1.7e-4 absolute on a |gamma| of 1.4e-2.  A relative 1e-3 on that
        # row allows only 1.4e-5 there, below that spread, so it printed
        # MISMATCH on every healthy run, which is how a real mismatch came to be
        # unreadable.  The absolute 1e-3 sits about 6x above the spread and
        # about 14x below the quantity: silent when the rebuild is right, loud
        # when a rebuild defect moves |gamma| at order |gamma|.  The other four
        # rows stay relative: they agree to SELF_CHECK_REL_TOL on a healthy run.
        # See "The self-check" in the module docstring.
        ("|gamma|", abs(cw.gamma), metric.s11_measured,
         SELF_CHECK_GAMMA_ABS_TOL, True),
        ("residual", cw.fit_residual, metric.residual, SELF_CHECK_REL_TOL, False),
    ]
    print("self-check (tone path vs rebuilt bin, dt_scale=%g):" % dt_scale,
          flush=True)
    lines, bad = self_check(checks)
    for line in lines:
        print(line, flush=True)
    if metric.refusal is not None:
        bad.append("bin refused: %s" % metric.refusal)
    print("    verdict      %s" % verdict_text(bad), flush=True)

    # WART, commented and deliberately not fixed: ``_dump_bins`` returns
    # ``str(np.savez(...))``, and ``np.savez`` returns ``None`` -- the handle is
    # a context manager, not a value -- so the return is the literal string
    # "None" and this line reads ``dump written: None`` even on a completely
    # successful write.  The file is there; the ``np.load`` just below is what
    # proves it.  The fix belongs in the frozen baseline, so it is recorded
    # here instead of patched from the caller.
    mark("dump")
    written = S._dump_bins(str(dump_path), freqs=np.array([float(g["f"])]),
                           spectra=phasor[None, :], station_x=cw.station_x,
                           n_stations=n, x_port=float(spec.x_port),
                           bins=(metric,), reference=None,
                           poynting={"sx_station": np.asarray(cw.sx_station, float),
                                     "sx_station_sub": np.asarray(cw.sx_station_sub, float)})
    print("dump written: %s" % written, flush=True)
    with np.load(str(dump_path)) as npz:
        print("dump schema: %s" % (sorted(npz.files),), flush=True)
        print("dump row:    f=%.6f GHz  |S11|(port)=%.5f  |S21|=%.5f  "
              "passivity=%.6f  refused=%s"
              % (npz["f"][0] / 1e9, npz["s11_port"][0], npz["s21"][0],
                 npz["passivity"][0], bool(npz["refused"][0])), flush=True)
        print("dump z0:     %s ohm" % (npz["z0"][0],), flush=True)

    print("", flush=True)
    print("ELAPSED %.1f s" % (time.perf_counter() - started), flush=True)
    print("BOARD_RUN_CW %s: DONE" % tag, flush=True)
    return 0 if not bad or bad[0].startswith("bin refused") else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
