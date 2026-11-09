#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""openEMS referee for E11 termination build A (coarse p51 operating point).

WHAT THIS IS
    An INDEPENDENT cross-check, in a third-party FDTD engine, of the 2-D FIT
    result recorded in

        evidence/termination/build_A_50ohm_p51_phasors.json

    It reconstructs the reference's own grid, layer stack and termination
    and asks one question:

        does an independent solver also see |S11| ~ 0.33 at 5.8278 GHz
        for a 50 ohm SERIES termination on a 3.2 mm strip?

    It is not a model of the physical DUT.  It is a referee on one number.

STATUS: AUTHORED, UNEXERCISED.
    openEMS cannot be run in the environment where this file was written:
    no docker binary, no /var/run/docker.sock, host shell banned, network
    banned (see docs/design/openems_referee_spec_2026-11-10.md, section 5
    "BLOCKER").  Nothing in this file has ever been executed against openEMS.
    Do not treat any number it prints as a validated model result.

USAGE
    # 1. geometry echo only.  Needs NO openEMS bindings.  Never calls Run().
    python3 build_A_referee.py --dry-run

    # 2. build the CSX model, then run openEMS's SETUP-ONLY path -- mesh and
    #    operators are built, NOTHING is time stepped (seconds, not ~49 s) and
    #    the solver's own setup output is scanned for dropped geometry.  This
    #    is the cheap pre-flight and it needs the bindings.
    python3 build_A_referee.py --dry-run --with-bindings

    # 0. --strip selects how the strip is represented (default: auto).
    #    auto setup-probes priority -> slab -> sheet and keeps the first that
    #    passes; metal is the 2026-11-09 control and is EXPECTED to fail;
    #    slab is a physics deviation (a 0.4 mm PEC slab).  Cannot be resolved
    #    without the bindings -- see "STRIP REPRESENTATION" below.

    # 2b. ONE representation, ONE setup probe, in a process that has run
    #     nothing else -- the fallback when `auto`'s in-process probes
    #     disagree with each other (openEMS keeps process-global state).
    #     Requires an EXPLICIT --strip X (exit 2 otherwise).
    python3 build_A_referee.py --probe-only --strip slab

    # 3. real solve -- NOT runnable from the authoring environment.
    docker build -t openems:bookworm docker/openems
    mkdir -p evidence/referee
    docker run --rm -v "$PWD/evidence/referee:/work/out" openems:bookworm \
        python3 /work/build_A_referee.py --out /work/out

    Exit 0  = whatever was asked for completed.
    Exit 2  = usage error -- today: --probe-only without an explicit
              --strip X.
    Exit 3  = solve ran but produced no port records (model is wrong).
    Exit 4  = openEMS reported geometry it did not apply (a primitive it
              called "Unused", or a lumped load with "Active cells: 0"), or
              the strip did not attach ON THE SOLVE PATH (there the "Number
              of PEC edges:" line is REQUIRED and must clear its floor; a
              SETUP-ONLY probe does not require it -- see
              audit_solver_output(phase=...)), or no --strip candidate passed
              its setup probe.  Nothing downstream of that is readable; see
              trap (11).
    Exit 5  = --with-bindings was requested but openEMS is not importable, so
              the model was never exercised at all.  A plain --dry-run (no
              --with-bindings) still exits 0 in that situation.

--------------------------------------------------------------------------
API TRAPS ALREADY PAID FOR -- do not re-learn these the hard way
--------------------------------------------------------------------------
(1) `from openEMS import openEMS as OEMS` binds the CLASS, not the module.
    Instantiate: FDTD = OEMS().
(2) SetBoundaryCond() needs exactly a 6-element list, tokens spelled
    'PML_8', 'PML_3', 'PML_0', 'PEC', 'PMC', 'MUR' -- nothing else.
    'PML', 'PML-8', 'PML_6', 'periodic', 'PEC_0', 'MUR_0' and lowercase
    all raise.  There is NO 6-cell PML in openEMS; 3 and 8 only.
(3) openEMS/ports.py references np.float, removed in numpy >= 1.24.
    The np.float/int/complex/bool aliases MUST be restored on the numpy
    module BEFORE `from openEMS import ports` is executed.  See _shim().
(4) csx.DefineGrid() is broken in this build.  Use
        g = csx.GetGrid(); g.SetDeltaUnit(1.0)
        g.SetLines("x", xs) ... ; g.GetQtyLines("x")  # direction required
        g.IsValid()
    An explicit mesh is MANDATORY -- there is no auto-mesh fallback.
(5) ContinuousStructure has no AddBox()/SetGrid().  Boxes hang off a
    PROPERTY:  sub = csx.AddMaterial("substrate", epsilon=4.4); sub.AddBox(...).
    Do not copy smoke_solve.py's air box into a real model -- trap (11).
(6) AddLumpedPort()/AddMSLPort() are SOLVER methods (FDTD.*), not csx.*.
    start/stop must lie on grid lines.  A port is a PLANE element: exactly
    one axis has zero extent, that axis is never p_dir, and p_dir must span
    at least one cell.  A lumped port MAY span its cross-section -- port 1
    here spans the whole 8-cell strip width in y.  (Earlier revisions of this
    trap said start/stop "may differ ONLY along p_dir": true of
    smoke_solve.py's single-cell port, false of this model.)  check_boxes()
    enforces the real rule.
(7) There is no SetSolverType() and no SetMaxThreads().  Thread count is a
    Run() kwarg:  Run(path, cleanup=, setup_only=, verbose=, numThreads=).
    SetTimeStepMethod() does exist.  Run() takes no timestep-count kwarg.
(8) PML_8 eats 8 CELLS per side, PML_3 eats 3.  Budget the grid for it.
(9) Files written from inside a bind mount come out root-owned.
(10) SetEndCriteria() takes a LINEAR ratio, and the solver prints 10*log10
    of it.  Default 1e-6 == -60 dB.  SetNumberOfTimeSteps() default is 1e9.
(11) A full-domain `epsilon=1` air box is NOT harmless filler.  Both host
    runs of 2026-11-09 opened with one, and openEMS dropped every primitive
    that lay inside it --
        Warning: Unused primitive (type: Box) detected in property: substrate!
        Warning: Unused primitive (type: Box) detected in property: strip!  x2
        --- Series/Parallel Lumped RLC load --- / Active cells: 0
    -- then solved EMPTY AIR over the ground plane and wrote port records
    anyway (|S11| = 1.0003, V1/I1 = 317 ohm, port1->port2 = -94 dB).  The
    background is already vacuum; never add an air box.  Nothing raises when
    a primitive is dropped, so build_model() now refuses to build a box that
    cannot occupy a cell and Run() output is scanned for both strings.
   WHICH CSXCAD rule drops those primitives is INFERENCE, not verified: the
    bindings source is not vendored in this workspace.  The evidence is which
    primitives were dropped (every one strictly inside the air box) and which
    was not (the air box itself).

--------------------------------------------------------------------------
EXTRACTION PLAN (reader + DFT helpers implemented in this file; still never
run against a live solve from the authoring environment)
--------------------------------------------------------------------------
The solver writes port_ut_1 / port_it_1 / port_ut_2 / port_it_2 into the
output directory as ASCII -- '%'-prefixed header lines, then
"time<TAB>value", and with NO file extension.  To compare against the
artefact:

    f  = 5.827786408327286e9                      # the artefact's own bin
    U1 = DFT(port_ut_1, f) ; I1 = DFT(port_it_1, f)
    Zref = 50.0
    S11 = (U1/Zref - I1) / (U1/Zref + I1)

f is not a free choice: it is exactly 8/(1800*dt) of the reference run, so
that both engines are sampled on the same bin.  |S11| is a MAGNITUDE and a
magnitude is invariant under a shift of the reference plane, so no
de-embedding is needed for the comparison this referee exists to make.  The
phase is NOT comparable without de-embedding to x = 20.4 mm (the artefact's
s21_plane_index = 51); the reference plane here is x = 3.2 mm.

|S21| is NOT obtainable from this file.  It needs a second lumped port
downstream (~x = 24 mm) plus a de-embed back to x = 20.4 mm over 3.6 mm.
That is a separate build; do not mix AddMSLPort in to get it.
"""

from __future__ import annotations

import argparse
import contextlib
import math
import os
import re
import sys
import tempfile

# ---------------------------------------------------------------------------
# Reference operating point and grid.  All values traced to the artefact
# evidence/termination/build_A_50ohm_p51_phasors.json and to
# emfit/studies.py (the generator's library).  Nothing here is inferred.
# ---------------------------------------------------------------------------

C0 = 2.99792458e8                     # m/s
CELL = 0.4e-3                         # uniform cell, ALL three axes

# --- x: propagation axis, 72 cells = 28.8 mm -------------------------------
#     recipe: n_pml6 + n_ref2 + n_line64
NX = 72
N_PML_X = 6
N_REF = 2
N_LINE = 64

# --- y: transverse axis, 212 cells = 84.8 mm -------------------------------
#     recipe: 2*n_pml12 + n_strip8 + 2*n_clean96
NY = 212
N_PML_Y = 12
N_STRIP = 8
N_CLEAN = 96

# --- z: vertical axis, 22 cells = 8.8 mm -----------------------------------
#     recipe: n_sub4 + n_air12 + n_top6
NZ = 22
N_SUB = 4
N_AIR = 12
N_TOP = 6

K_STRIP = N_SUB                       # strip plane z-index: 4 -> 1.6 mm
J_CENTRE = 106                        # strip centre y-index
IX_PORT = 8                           # launch port column -> x = 3.2 mm
IX_LOAD = 50                          # load column -> x = 20.0 mm
IX_PLANE = 51                         # artefact s21_plane_index -> x = 20.4 mm

EPS_R = 4.4                           # substrate
W_STRIP = N_STRIP * CELL              # 3.2 mm
H_SUB = N_SUB * CELL                  # 1.6 mm
R_TERM = 50.0                         # series termination, ohm
R_PORT = 50.0                         # port reference impedance, ohm

F_REF = 5827786408.327286             # Hz -- the artefact's own DFT bin
DT_REF = 7.626299478123987e-13        # s   -- the artefact's own timestep

NSTEPS_CAP = 40000                    # hard cap; ~16700 implied by DT_REF
END_CRIT = 1e-6                       # LINEAR ratio -> -60 dB

# Artefact values this referee is comparing against (report only; the script
# never asserts them, they are the thing under test).
S11_ARTEFACT = 0.32556486641109117
S11_STATUS = "UNVALIDATED"
Z0_STATION_FIT = 47.364066848187235 + 1.6449807931078728j


def _mm(v: float) -> str:
    return "%9.4f mm" % (v * 1e3)


def _lines(n: int) -> list[float]:
    """Node coordinates 0 .. n*CELL inclusive.  Plain list, no numpy."""
    return [i * CELL for i in range(n + 1)]


def plan() -> dict:
    """Derive every number the model needs, from the recipe counts only."""
    j_lo = J_CENTRE - N_STRIP // 2            # 102
    j_hi = j_lo + N_STRIP                     # 110
    p = {
        "xs": _lines(NX), "ys": _lines(NY), "zs": _lines(NZ),
        "x_max": NX * CELL, "y_max": NY * CELL, "z_max": NZ * CELL,
        "cells": NX * NY * NZ,
        "x_port": IX_PORT * CELL,             # 3.2 mm
        "x_load": IX_LOAD * CELL,             # 20.0 mm
        "x_gap_hi": (IX_LOAD + 1) * CELL,     # 20.4 mm
        "x_plane": IX_PLANE * CELL,           # 20.4 mm
        "j_lo": j_lo, "j_hi": j_hi,
        "y_lo": j_lo * CELL,                  # 40.8 mm
        "y_hi": j_hi * CELL,                  # 44.0 mm
        "w_strip": W_STRIP, "h_sub": H_SUB,
        "z_strip": K_STRIP * CELL,            # 1.6 mm
        "z_air_top": (K_STRIP + N_AIR) * CELL,   # 6.4 mm
        "n_edges": N_STRIP + 1,               # 9 -- the reference's y-node lines
    }
    p["span_port_load"] = p["x_load"] - p["x_port"]          # 16.8 mm
    p["sigma_edge"] = 1.0 / (p["n_edges"] * R_TERM)          # 1/450 S
    _self_check(p)
    return p


def _self_check(p: dict) -> None:
    """Fail loudly if the recipe counts stop reproducing the artefact's box.

    The reference box is 0.0288 x 0.0848 x 0.0088 m.  If these drift, the
    grid no longer matches the thing being refereed and the comparison is
    meaningless -- better to crash than to silently model a different line.
    """
    for got, want, name in (
        (p["x_max"], 0.0288, "x extent"),
        (p["y_max"], 0.0848, "y extent (NOT 0.04 -- see doc section 1)"),
        (p["z_max"], 0.0088, "z extent"),
        (p["w_strip"], 0.0032, "strip width"),
        (p["h_sub"], 0.0016, "substrate height"),
        (100 * p["cells"] / 100, 335808, "cell count"),
    ):
        if abs(got - want) > 1e-12 * max(1.0, abs(want)):
            raise SystemExit(
                "SELF-CHECK FAILED: %s = %r, expected %r" % (name, got, want))
    t = 0.99 * CELL / (C0 * math.sqrt(3.0))
    if abs(t - DT_REF) > 1e-3 * DT_REF:
        raise SystemExit(
            "SELF-CHECK FAILED: dt = %.6e s, artefact recorded %.6e s"
            % (t, DT_REF))


# ---------------------------------------------------------------------------
# STRIP REPRESENTATION.  The strip is a 3.2 mm wide PEC sheet on the top face
# of the substrate, CUT into two sheets by the one-cell load gap.  It has always
# been built as zero-thickness metal boxes, and the 2026-11-09 host runs show
# CSXCAD dropping exactly those two primitives ("Unused primitive ... strip!
# x2") while keeping the substrate.  WHICH rule drops a zero-extent box is not
# verified; WHAT to do about it is a choice, so the choice is an explicit CLI
# option and each representation is built by its own small function below.
#
# Nothing else varies between representations: same grid, same boundaries,
# same port geometry, same frequencies, same geometry table.  Only the strip
# property, the strip z extent and the strip priority change.
# ---------------------------------------------------------------------------


class StripUnavailable(Exception):
    """A representation could not be constructed at all (e.g. no such CSX type)."""


STRIP_PRIORITY = 10      # any value above the CSX default 0 wins; 10 is
                         # arbitrary-but-fixed and deliberately NOT tuned.


def _strip_metal(csx, p):
    """CONTROL -- today's code, unchanged: plain metal, flat, no priority.

    This is the representation the 2026-11-09 host runs used when CSXCAD
    dropped both sheets, so --strip metal must keep reproducing that failure.
    """
    return csx.AddMetal("strip"), None, 0.0


def _strip_priority(csx, p):
    """H2 test -- identical zero-thickness boxes, priority=10 on each AddBox.

    Tests "first-added-wins ownership at equal priority" with ZERO physics
    deviation: the geometry is the control's to the bit, only the priority
    changes.
    """
    return csx.AddMetal("strip"), STRIP_PRIORITY, 0.0


def _strip_slab(csx, p):
    """H1 test -- if zero thickness is the problem, give the strip one cell.

    PHYSICS DEVIATION, and every report of this representation says so: a
    0.4 mm PEC slab is 25% of the 1.6 mm substrate height, so it is not the
    reference's zero-thickness sheet.
    """
    return csx.AddMetal("strip"), STRIP_PRIORITY, CELL


def _strip_sheet(csx, p):
    """CSXCAD ConductingSheet, plus the same flat boxes at priority 10.

    ONE attempt only: no guessed-kwarg retries and no probing of conductivity
    or thickness names.  CSXCAD.pyx:402 AddConductingSheet(name, **kw) forwards
    straight into CSProperties.fromTypeName(), and the Python-side kwarg names
    are not vendored here, so a retry loop would be guessing.  If the call
    refuses, its exception text is reported VERBATIM.
    """
    try:
        return csx.AddConductingSheet("strip"), STRIP_PRIORITY, 0.0
    except Exception as exc:          # verbatim evidence, not a control flow
        raise StripUnavailable(
            'csx.AddConductingSheet("strip") raised %s: %s'
            % (type(exc).__name__, exc))


STRIP_REPS = {
    "metal": {
        "builder": _strip_metal, "exact": True, "dz": 0.0,
        "what": 'csx.AddMetal("strip") + 2 flat boxes, NO priority (control)',
    },
    "priority": {
        "builder": _strip_priority, "exact": True, "dz": 0.0,
        "what": 'csx.AddMetal("strip") + 2 flat boxes, AddBox(priority=10)',
    },
    "slab": {
        "builder": _strip_slab, "exact": False, "dz": CELL,
        "what": 'csx.AddMetal("strip") + 2 boxes 1 cell thick in z, '
                'AddBox(priority=10) -- PHYSICS DEVIATION',
    },
    "sheet": {
        "builder": _strip_sheet, "exact": True, "dz": 0.0,
        "what": 'csx.AddConductingSheet("strip") + 2 flat boxes, '
                'AddBox(priority=10)',
    },
}

# --strip accepts all five; auto is the default.  metal is deliberately NOT
# first in the probe order: it is the representation known to fail.
STRIP_CHOICES = ("auto", "metal", "priority", "slab", "sheet")
STRIP_CANDIDATES = ("priority", "slab", "sheet")


def strip_dz(rep: str) -> float:
    """The strip's z extent for `rep`; 'auto' has none of its own.

    'auto' is resolved BEFORE any model is built, so any table or check asked
    for it is the zero-thickness one and strip_report_lines() labels it as
    unresolved.  Never invent a thickness for an unprobed representation.
    """
    return 0.0 if rep == "auto" else STRIP_REPS[rep]["dz"]


def strip_build(csx, p: dict, rep: str) -> tuple:
    """Build ONE strip property for `rep`.  Returns (property, priority, dz).

    `priority` is None when the representation passes none (the control) and
    is otherwise the value handed to AddBox() and to port 2's AddLumpedPort().
    `dz` is the strip's z extent in metres: 0.0 for a zero-thickness sheet.
    Raises StripUnavailable if the CSX type itself does not exist.
    """
    return STRIP_REPS[rep]["builder"](csx, p)


def strip_report_lines(p: dict, rep: str) -> list:
    """The representation-in-force lines.  Shared by echo() and the resolver."""
    if rep == "auto":
        return ["strip representation   : auto (UNRESOLVED -- candidates are "
                "setup-probed in the order %s, never by a solve)"
                % " -> ".join(STRIP_CANDIDATES)]
    dz = STRIP_REPS[rep]["dz"]
    z0 = p["z_strip"]
    k1 = K_STRIP + int(round(dz / CELL))
    priority = "none (CSX default 0)" if rep == "metal" else str(STRIP_PRIORITY)
    return [
        "strip representation   : %s  [%s]" % (rep, STRIP_REPS[rep]["what"]),
        "  AddBox priority     : %s" % priority,
        "  port 2 priority     : %s (same value on AddLumpedPort)" % priority,
        "  z span              : %s .. %s (z nodes %d..%d, %s)"
        % (_mm(z0).strip(), _mm(z0 + dz).strip(), K_STRIP, k1,
           "zero thickness" if not dz
           else "%.4f mm thick -- PHYSICS DEVIATION" % (dz * 1e3)),
    ]


def strip_exactness_line(rep: str) -> str:
    """One sentence: is `rep` the reference geometry, or a physics deviation?"""
    if STRIP_REPS[rep]["exact"]:
        return ("YES -- %s; no physics deviation, so any number this run "
                "produces is comparable to the reference"
                % STRIP_REPS[rep]["what"])
    dz = STRIP_REPS[rep]["dz"]
    return ("NO -- PHYSICS DEVIATION: a %g mm PEC slab is %.1f%% of the %g mm "
            "substrate height.  Evidence from this run must say so."
            % (dz * 1e3, 100.0 * dz / H_SUB, H_SUB * 1e3))


# ---------------------------------------------------------------------------
# GEOMETRY TABLE.  ONE list of boxes, consumed by both the primitive pre-flight
# (check_boxes) and build_model().  Two code paths that build the same geometry
# will eventually disagree; one table cannot disagree with itself.  Trap (11)
# records what that disagreement cost on 2026-11-09.
# ---------------------------------------------------------------------------

def geometry_boxes(p: dict, rep: str = "metal") -> list:
    """Every geometric box the model needs, as (property, label, start, stop).

    The coordinates mirror the arithmetic build_model() has always used; no
    value here is new.  The strip is genuinely CUT: sheet A stops at the load
    cell, sheet B resumes one cell later, and the empty cell carries the
    termination.

    `rep` moves exactly ONE face: the strip's UPPER z face, by
    STRIP_REPS[rep]["dz"].  A zero-thickness representation leaves it on the
    strip plane as before; the slab representation lifts it by one cell, and
    that lift is the whole of its physics deviation.
    """
    x_max = p["x_max"]
    y_lo, y_hi = p["y_lo"], p["y_hi"]
    z_strip = p["z_strip"]
    dz = strip_dz(rep)
    z_upper = z_strip + dz
    thickness = ", 1 cell thick (slab)" if dz else ", zero-thickness"
    return [
        ("substrate",
         "substrate, eps_r = %g" % EPS_R,
         [0.0, 0.0, 0.0],
         [x_max, p["y_max"], p["h_sub"]]),
        ("strip",
         "strip sheet A (feed)" + thickness,
         [p["x_port"], y_lo, z_strip],
         [p["x_load"], y_hi, z_upper]),
        ("strip",
         "strip sheet B (stub)" + thickness,
         [p["x_gap_hi"], y_lo, z_strip],
         [x_max, y_hi, z_upper]),
    ]


def port_boxes(p: dict) -> list:
    """Both port footprints as (label, start, stop, propagation_axis).

    build_model() does not add these as primitives -- AddLumpedPort() creates
    them -- but they are checked against the same mesh, because a port that
    misses the grid is the other way a model quietly turns into air.
    """
    return [
        ("port 1 launch (z-directed)",
         [p["x_port"], p["y_lo"], 0.0],
         [p["x_port"], p["y_hi"], p["h_sub"]],
         "z"),
        ("port 2 load (x-directed)",
         [p["x_load"], p["y_lo"], p["z_strip"]],
         [p["x_gap_hi"], p["y_hi"], p["z_strip"]],
         "x"),
    ]


def mesh_indices(start, stop) -> tuple:
    """(i0, i1, j0, j1, k0, k1) node indices for a box; SystemExit if off-mesh.

    A box whose faces do not land on grid lines is exactly the box openEMS
    drops without saying so (trap 11), so an off-mesh coordinate is a hard
    failure here, never a warning.
    """
    out = []
    for axis in range(3):
        for coord in (start[axis], stop[axis]):
            idx = int(round(coord / CELL))
            if abs(coord - idx * CELL) > 1e-9:
                raise SystemExit(
                    "OFF-MESH BOX: coordinate %.12g m does not lie on the "
                    "%.4g mm grid (nearest node %.12g m, off by %.3g m)"
                    % (coord, CELL * 1e3, idx * CELL, coord - idx * CELL))
            out.append(idx)
    return tuple(out)


def check_boxes(p: dict, rep: str = "metal") -> list:
    """Arithmetic pre-flight: prove every box occupies at least one cell.

    Returns [(label, mesh_index, note)]; raises SystemExit naming the box that
    failed.  Every condition here is one whose violation makes CSXCAD discard
    the primitive -- the failure the 2026-11-09 runs paid for twice.

    `rep` is needed here because the z rule is the one thing that depends on
    it: a zero-thickness representation (metal, priority, sheet) must be FLAT
    in z, the slab must be EXACTLY ONE cell thick in z.
    """
    boxes = geometry_boxes(p, rep)
    slab = strip_dz(rep) != 0.0
    rows = []

    # --- the substrate ----------------------------------------------------
    # It must be a slab, and it must be THIS slab: x 0..NX, y 0..NY,
    # z 0..N_SUB.  A different index is a different transmission line.
    _prop, label, start, stop = boxes[0]
    idx = mesh_indices(start, stop)
    if idx[4] == idx[5]:
        raise SystemExit(
            "PRE-FLIGHT FAILED: %s is FLAT in z (k0 == k1 == %d); a "
            "zero-thickness slab is not a substrate" % (label, idx[4]))
    if idx != (0, NX, 0, NY, 0, N_SUB):
        raise SystemExit(
            "PRE-FLIGHT FAILED: substrate occupies mesh index %r, expected %r"
            % (idx, (0, NX, 0, NY, 0, N_SUB)))
    rows.append((label, idx, "full x/y footprint, %d cells thick"
                 % (idx[5] - idx[4])))

    # --- the two strip sheets ---------------------------------------------
    for _prop, label, start, stop in boxes[1:]:
        idx = mesh_indices(start, stop)
        flat = [ax for ax, a, b in (("x", idx[0], idx[1]),
                                    ("y", idx[2], idx[3]),
                                    ("z", idx[4], idx[5])) if a == b]
        if slab:
            if idx[5] - idx[4] != 1:
                raise SystemExit(
                    "PRE-FLIGHT FAILED: %s is %d cells thick in z (k %d..%d); "
                    "representation %r requires EXACTLY one cell"
                    % (label, idx[5] - idx[4], idx[4], idx[5], rep))
        elif flat != ["z"]:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s has zero extent on %r; a "
                "zero-thickness strip sheet must be flat in z ONLY"
                % (label, flat))
        if idx[4] != K_STRIP:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s sits on z node %d, expected %d (z = %s)"
                % (label, idx[4], K_STRIP, _mm(p["z_strip"]).strip()))
        if idx[1] <= idx[0] or idx[3] <= idx[2]:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s spans less than one cell (x %d..%d, "
                "y %d..%d)" % (label, idx[0], idx[1], idx[2], idx[3]))
        note = ("on z node %d, %d x %d cells"
                % (idx[4], idx[1] - idx[0], idx[3] - idx[2]))
        if slab:
            note += (", %d cell thick (z nodes %d..%d)"
                     % (idx[5] - idx[4], idx[4], idx[5]))
        rows.append((label, idx, note))

    # --- the two ports -----------------------------------------------------
    # A port is a PLANE element: exactly one axis has zero extent, that axis
    # is never p_dir, and p_dir itself must span at least one cell.  A lumped
    # port MAY span its cross-section -- port 1 deliberately spans the whole
    # 8-cell strip width in y.  See trap (6).
    for label, start, stop, p_dir in port_boxes(p):
        idx = mesh_indices(start, stop)
        axes = {"x": (idx[0], idx[1]), "y": (idx[2], idx[3]),
                "z": (idx[4], idx[5])}
        flat = [ax for ax in ("x", "y", "z") if axes[ax][0] == axes[ax][1]]
        if len(flat) != 1:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s has zero extent on %r; a port must be "
                "a plane element, flat on exactly one axis" % (label, flat))
        if flat[0] == p_dir:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s is flat along its own p_dir=%r, so it "
                "occupies no cell to excite" % (label, p_dir))
        lo, hi = axes[p_dir]
        if hi <= lo:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s spans less than one cell along "
                "p_dir=%r (%d..%d)" % (label, p_dir, lo, hi))
        cross = [axes[ax][1] - axes[ax][0] for ax in ("x", "y", "z")
                 if ax != p_dir and ax != flat[0]]
        if min(cross) < 1:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s has less than one cell of "
                "cross-section" % label)
        rows.append((label, idx, "p_dir=%s, %d cells" % (p_dir, hi - lo)))

    # --- the thickness every other number rests on -------------------------
    if abs(p["h_sub"] - N_SUB * CELL) > 1e-15:
        raise SystemExit(
            "PRE-FLIGHT FAILED: h_sub = %.17g m but N_SUB*CELL = %.17g m"
            % (p["h_sub"], N_SUB * CELL))

    return rows


# The geometry echo.  This block is the contract with the design record
# docs/design/openems_referee_spec_2026-11-10.md -- keep the two in step.
ECHO = """\
=== GEOMETRY ECHO (openEMS referee, E11 termination build A, coarse p51) ======
cell                  : 0.4000 mm  (uniform on all three axes)
grid [cells]          : nx=72 ny=212 nz=22  -> 335808 cells
  x (propagation)     : 28.8000 mm   0.0000 .. 28.8000   n_pml6+n_ref2+n_line64
  y (transverse)      : 84.8000 mm   0.0000 .. 84.8000   2*n_pml12+n_strip8+2*n_clean96
  z (vertical)        :  8.8000 mm   0.0000 ..  8.8000   n_sub4+n_air12+n_top6
  !! y extent is 84.8 mm, NOT 40 mm.  geometry.y_extent = 0.04 in the
  !! artefact is the +-20 mm truncation window of the plate_current
  !! integral (studies.py:1427), not a geometric extent.  Building to
  !! 40 mm would be a factor-of-two error in transverse domain size.
substrate             : eps_r = 4.4, z = 0.0000 .. 1.6000 mm (4 cells), h = 1.6000 mm
ground                : z = 0 plane, PEC boundary (zmin is the ground wall)
strip (PEC sheet)     : w = 3.2000 mm, y = 40.8000 .. 44.0000 mm, z = 1.6000 mm
  sheet A (feed)      : x =  3.2000 .. 20.0000 mm   (cols 8..50)
  sheet B (stub)      : x = 20.4000 .. 28.8000 mm   (cols 51..72)
  gap                 : x = 20.0000 .. 20.4000 mm   <- one cell, THE LOAD
load                  : SERIES 50.000 ohm across the gap, column 50
  orientation         : p_dir = 'x'  (longitudinal, resists E_x)
  reference structure : 9 parallel E_x edges, sigma = 1/(9*50) = 2.2222e-03 S each
                        -> exactly 50 ohm total (studies.py:2925-2931)
  openEMS equivalent  : cut strip + lumped element spanning the full 3.2 mm
                        width in y, one cell in x.  NOT a z-directed element
                        and NOT a shunt to ground -- see doc section 2.
launch port 1         : LUMPED, x = 3.2000 mm (col 8), ground -> strip
  span                : z = 0 .. 1.6000 mm, y = 40.8000 .. 44.0000 mm
  impedance           : 50 ohm, excite = 1.0
probe port 2          : the load element itself (excite = 0, R = 50)
                        -> port_ut_2 / port_it_2 are the referee's V and I
reference plane       : x = 3.2000 mm.  |S11| is compared as a MAGNITUDE only,
                        which is plane-invariant.  The artefact's extraction
                        plane was x = 20.4000 mm (s21_plane_index = 51);
                        phases are NOT comparable without de-embedding.
boundary conditions   : xmin=PML_3  xmax=PML_8  ymin=PML_8  ymax=PML_8
                        zmin=PEC    zmax=PML_8
  DEVIATION           : the dispatch asked for "PML 6 cells".  openEMS has no
                        PML_6 (only PML_3 / PML_8 / PML_0 / MUR).  Resolved
                        per face without touching the grid.
  xmin = PML_3        : FORCED.  PML_8 would consume columns 0..7 and the
                        launch port sits at column 8.  No freedom here.
  zmin = PEC          : this IS the reference's ground plane; a PML or MUR
                        here would be physically wrong.
  MUR rejected        : smoke test measured a -18.58 dB energy floor.
excitation            : Gaussian, f0 = fc = 5.827786408 GHz
dt (expected)         : 7.626299478124e-13 s
end criteria          : SetEndCriteria(1e-06) LINEAR == -60 dB, set EXPLICITLY
timestep cap          : SetNumberOfTimeSteps(40000)
threads               : 2, passed to Run() (there is no SetMaxThreads)
target                : |S11| at f = 5.827786408327286 GHz
  artefact value      : 0.3255648664110912   (s11.validation_status = UNVALIDATED)
  series-R anchor     : |R/(R+2*Z0)| = 0.345475  at Z0 = 47.364067+j1.644981
                        (artefact quotes 0.34465 -> implies Z0 = 47.537,
                         a value that appears NOWHERE in the artefact)
  shunt anchor        : 0.027073  <-- if you match THIS you built a shunt.
================================================================================
"""


def echo(p: dict, rep: str = "metal", stream=sys.stdout) -> None:
    """Print the geometry echo.  Pure arithmetic -- needs no openEMS."""
    stream.write(ECHO)
    for _line in strip_report_lines(p, rep):
        stream.write(_line + "\n")
    stream.write("derived: port->load span = %s, sigma per E_x edge = %s S\n"
                 % (_mm(p["span_port_load"]), p["sigma_edge"]))
    stream.write("derived: load cell = [%s, %s] x [%s, %s] x z=%s\n"
                 % (_mm(p["x_load"]).strip(), _mm(p["x_gap_hi"]).strip(),
                    _mm(p["y_lo"]).strip(), _mm(p["y_hi"]).strip(),
                    _mm(p["z_strip"]).strip()))
    beta = 231.55331672912826            # rad/m, the artefact's two-wave beta
    span = p["span_port_load"]           # 16.8 mm, launch port -> load column
    de = p["x_plane"] - p["x_port"]      # 17.2 mm, launch plane -> artefact plane
    stream.write("derived: beta = %.6f rad/m (artefact, two-wave)\n" % beta)
    stream.write("derived: round trip over the %.4f mm port->load span = "
                 "2*beta*L = %.6f rad = %.2f deg\n"
                 % (span * 1e3, 2 * beta * span,
                    math.degrees(2 * beta * span)))
    stream.write("derived: one-way de-embed from the launch plane to the "
                 "artefact plane (%s) = beta*L = %.6f rad = %.2f deg\n"
                 % (_mm(de).strip(), beta * de, math.degrees(beta * de)))
    # trap (11): prove on paper, before the solver is imported at all, that
    # every primitive occupies cells.  A box that occupies none is a box
    # CSXCAD drops, and it drops it without raising anything.
    _rows = check_boxes(p, rep)
    stream.write("--- primitive pre-flight (mesh node index, checked before "
                 "build) ---\n")
    for _label, _idx, _note in _rows:
        stream.write("  %-42s x %2d:%2d  y %3d:%3d  z %2d:%2d   %s\n"
                     % (_label, _idx[0], _idx[1], _idx[2], _idx[3],
                        _idx[4], _idx[5], _note))
    stream.write("  air box  (none: an epsilon=1 air box is inert and was "
                 "what the 2026-11-09 runs paid for)\n")
    stream.write("target : |S11| = %.16f (%s), phase %.6f deg (phase not comparable)\n"
                 % (S11_ARTEFACT, S11_STATUS, -100.49921155605985))
    stream.flush()


# ---------------------------------------------------------------------------
# openEMS bindings.  Imported lazily, inside a guard, so that --dry-run can
# produce the geometry echo on a machine with no openEMS installed.  This is
# not a workaround for the blocker: it is how the file stays reviewable.
# ---------------------------------------------------------------------------

def _shim():
    """Trap (3): restore the aliases numpy >= 1.24 removed.

    MUST run before `from openEMS import ports`, because ports.py does
    `np.float(...)` at import time and numpy 1.24+ raises AttributeError.
    """
    import numpy as np
    for name, typ in (("float", float), ("int", int),
                      ("complex", complex), ("bool", bool)):
        if not hasattr(np, name):
            setattr(np, name, typ)
    return np


def build_model(p: dict, rep: str = "metal"):
    """Build the CSX model and the solver.  Does NOT call Run().

    `rep` selects how the strip is represented; see STRIP REPRESENTATION
    above.  Nothing else in the model depends on it.
    """
    _shim()

    from openEMS import openEMS as OEMS      # trap (1): this is the CLASS
    from CSXCAD import ContinuousStructure

    FDTD = OEMS()
    FDTD.SetGaussExcite(F_REF, F_REF)

    # trap (2): 6 elements, exact tokens, no PML_6 in existence.
    # trap (8): PML_8 eats 8 cells per side.
    FDTD.SetBoundaryCond([
        "PML_3",    # xmin -- forced by the port at column 8
        "PML_8",    # xmax -- strip runs into it
        "PML_8",    # ymin
        "PML_8",    # ymax
        "PEC",      # zmin -- this IS the ground plane
        "PML_8",    # zmax -- consumes 8 of 22 cells, starts 4.0 mm above strip
    ])

    csx = ContinuousStructure()
    FDTD.SetCSX(csx)

    # trap (4): explicit mesh is mandatory; DefineGrid() is broken.
    g = csx.GetGrid()
    g.SetDeltaUnit(1.0)                      # we hand it metres directly
    g.SetLines("x", p["xs"])
    g.SetLines("y", p["ys"])
    g.SetLines("z", p["zs"])
    if not g.IsValid():
        raise SystemExit("mesh invalid: explicit grid did not validate")

    # trap (5): boxes hang off materials, not off the structure.
    # trap (11): the primitives come from geometry_boxes() -- the SAME table
    # check_boxes() just validated -- so a geometry edit cannot reach one and
    # miss the other.  No `epsilon=1.0` air box: the background is already
    # vacuum, such a box perturbs nothing, and it is what the 2026-11-09 runs
    # paid a full solve for twice.
    check_boxes(p, rep)
    substrate = csx.AddMaterial("substrate", epsilon=EPS_R)
    strip, strip_priority, _dz = strip_build(csx, p, rep)
    for _prop, _label, _start, _stop in geometry_boxes(p, rep):
        if _prop == "strip":
            if strip_priority is None:
                strip.AddBox(start=_start, stop=_stop)
            else:
                strip.AddBox(start=_start, stop=_stop,
                             priority=strip_priority)
        else:
            substrate.AddBox(start=_start, stop=_stop)

    # trap (6): ports are SOLVER methods (FDTD.*), not csx.*.  A port is a
    # PLANE element: exactly one axis has zero extent, that axis is never
    # p_dir, and p_dir must span at least one cell.  The other two axes
    # MAY span their whole cross-section -- port 1 spans the entire
    # 8-cell strip width in y.  check_boxes() enforces exactly this.
    # Port 1 -- vertical lumped launch, ground wall (z=0) up to the strip.
    FDTD.AddLumpedPort(
        1, R_PORT,
        start=[p["x_port"], p["y_lo"], 0.0],
        stop=[p["x_port"], p["y_hi"], p["h_sub"]],
        p_dir="z", excite=1.0)

    # Port 2 -- THE LOAD.  A series element must resist the longitudinal
    # current, so it lies ALONG the strip: one cell in x, full width in y.
    # p_dir='x' is the load orientation; p_dir='y' would short the strip
    # edge-to-edge (E_y rails) and give a shunt, |Gamma| = 0.027 instead of
    # 0.345.  The reference builds 9 parallel E_x edges for exactly this
    # reason -- see doc section 2 for the arithmetic.
    #
    # Port 2 carries the SAME priority as the strip property, because the load
    # has to win the very cell the strip boxes are fighting over.  PART 4
    # provenance for the kwarg (the bindings are not vendored here, so these
    # are the lines the forwarded kwarg lands in):
    #   infra/openems/reference/ports.py:96-119, Port.__init__ sets
    #       self.priority = 0
    #       if 'priority' in kw: self.priority = kw['priority']
    #     and that value is consumed by
    #       lumped_R.AddBox(self.start, self.stop, priority=self.priority)
    #   infra/openems/reference/openEMS.pyx:339 forwards **kw into it:
    #       def AddLumpedPort(self, port_nr, R, start, stop, p_dir,
    #                         excite=0, **kw)
    port2_kw = {} if strip_priority is None else {"priority": strip_priority}
    FDTD.AddLumpedPort(
        2, R_TERM,
        start=[p["x_load"], p["y_lo"], p["z_strip"]],
        stop=[p["x_gap_hi"], p["y_hi"], p["z_strip"]],
        p_dir="x", excite=0.0, **port2_kw)

    # Convergence: linear ratio, rendered by the solver as 10*log10 = -60 dB.
    FDTD.SetEndCriteria(END_CRIT)            # explicit, do not rely on default
    FDTD.SetNumberOfTimeSteps(NSTEPS_CAP)    # hard cap; no Run() kwarg exists

    return FDTD, csx


# --------------------------------------------------------------------------
# PORT RECORDS.  openEMS writes them as ASCII with '%'-prefixed header lines
# and NO file extension (port_ut_1, ...); some workflows keep h5-suffixed
# copies instead.  The extension-less file is tried first.
# --------------------------------------------------------------------------

Z_REF = 50.0                    # ohm -- the artefact's reference impedance


def _port_paths(outdir: str, name: str):
    """The two candidate paths for a port basename; the plain one comes first."""
    plain = os.path.join(outdir, name)
    return plain, plain + ".h5"


def read_port_ascii(path: str):
    """(t, x) from an openEMS ASCII port record ('%'-prefixed headers)."""
    import numpy as np
    data = np.loadtxt(path, comments="%", ndmin=2)
    return data[:, 0], data[:, 1]


def read_port_h5(path: str):
    """(t, x) from an h5-suffixed port record (legacy layout, first dataset)."""
    import h5py
    import numpy as np
    with h5py.File(path, "r") as f:
        data = np.array(f[sorted(f.keys())[0]], dtype=float)
    return data[:, 0], data[:, 1]


def read_port(outdir: str, name: str):
    """(t, x) for port `name`: extension-less ASCII first, then `<name>.h5`.

    Raises FileNotFoundError naming BOTH candidates if neither can be read.
    """
    plain, h5 = _port_paths(outdir, name)
    if os.path.exists(plain):
        return read_port_ascii(plain)
    if os.path.exists(h5):
        return read_port_h5(h5)
    raise FileNotFoundError(
        "port record %r not found: tried %r and %r" % (name, plain, h5))


def dft_at(t, x, f: float) -> complex:
    """One bin of the DFT of a stored time series, at frequency `f` [Hz]."""
    import numpy as np
    t = np.asarray(t, dtype=float)
    x = np.asarray(x, dtype=float)
    dt = float(np.median(np.diff(t)))
    return complex(np.sum(x * np.exp(-2j * math.pi * f * t)) * dt)


def extract_s11(outdir: str, f: float = F_REF, zref: float = Z_REF) -> dict:
    """S11 at bin `f` from port_ut_1 / port_it_1 (the magnitude is the point)."""
    t_u, u = read_port(outdir, "port_ut_1")
    t_i, i = read_port(outdir, "port_it_1")
    U = dft_at(t_u, u, f)
    I = dft_at(t_i, i, f)
    a = U / zref
    return {"f_hz": f, "zref_ohm": zref, "U": U, "I": I,
            "s11": (a - I) / (a + I)}


# ---------------------------------------------------------------------------
# SOLVER OUTPUT GUARD.  openEMS's C++ core writes its warnings to fd 1 and 2,
# not to Python's sys.stdout, so the two strings that say "I did not apply your
# geometry" never reach a print().  Capture the file descriptors, then insist
# on having seen a clean setup.  Trap (11).
# ---------------------------------------------------------------------------

_UNUSED_PAT = re.compile(r"Unused primitive")
_ZERO_LOAD_PAT = re.compile(r"Active cells:\s*0(?:\D|\Z)")
_PEC_EDGES_PAT = re.compile(r"Number of PEC edges:\s*(\d+)")
_ACTIVE_PAT = re.compile(r"Active cells:\s*(\d+)")
_VERSION_PAT = re.compile(
    r"openEMS 64bit -- version \S+|CSXCAD -- Version: \S+"
    r"|hdf5\s+-- Version: \S+")

# --- the attachment floor ---------------------------------------------
# The two strip sheets lie ON the K_STRIP plane, so each contributes one PEC
# face per (x, y) cell on that plane -- but ONLY if the strip attaches at all.
# When CSXCAD drops both sheets (trap 11) the only PEC left is the port-1
# plane, and the 2026-11-09 broken runs reported 32 PEC edges.
#
#     sheet A  x nodes  8..50  ->  50 -  8 = 42 cells x 110 - 102 = 8 = 336
#     sheet B  x nodes 51..72  ->  72 - 51 = 21 cells x 110 - 102 = 8 = 168
#                                     (50-8)*8 + (72-51)*8 = 336 + 168 = 504
#
# PEC_EDGES_FLOOR is 504 rounded DOWN, for slack: the solver counts edges, not
# faces, so its number need not equal 504 exactly.  It is a CONSTANT and is
# deliberately not recomputed here -- _expected_pec_faces() recomputes 504
# from the box table, so a geometry edit moves the expected value while the
# floor stays put and the comparison stays honest.
PEC_EDGES_FLOOR = 500


@contextlib.contextmanager
def _captured_output():
    """Send fd 1 AND fd 2 to a temp file for the duration of the block.

    Redirecting sys.stdout is not enough: the solver writes from C++.  Yields
    the open file object.  `finally` restores both descriptors, so a solver
    exception cannot leave the process mute.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    saved = (os.dup(1), os.dup(2))
    tmp = tempfile.TemporaryFile(mode="w+b")
    try:
        os.dup2(tmp.fileno(), 1)
        os.dup2(tmp.fileno(), 2)
        yield tmp
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])
            tmp.seek(0)


def read_captured(tmp) -> str:
    """Everything the solver wrote to fd 1/2, as text."""
    tmp.seek(0)
    return tmp.read().decode("utf-8", "replace")


def report_solver_provenance(text: str) -> None:
    """Echo the engine versions out of the solver's own banner, or say so."""
    hits = _VERSION_PAT.findall(text)
    if not hits:
        print("solver provenance: NO version banner in the solver output -- "
              "this result cannot be attributed to an engine build.")
        return
    print("solver provenance:")
    for line in hits:
        print("  %s" % line)


def _expected_pec_faces(p: dict, rep: str = "metal") -> int:
    """PEC faces the strip sheets should contribute if they attach (504).

    Recomputed from the same box table the model is built from, so it tracks
    the geometry; PEC_EDGES_FLOOR deliberately does not.
    """
    total = 0
    for _prop, _label, start, stop in geometry_boxes(p, rep):
        if _prop != "strip":
            continue
        i0, i1, j0, j1, k0, k1 = mesh_indices(start, stop)
        total += (i1 - i0) * (j1 - j0) * (2 if k1 > k0 else 1)
    return total


def _expected_active_cells(p: dict) -> list:
    """[(port label, cells it should activate)] -- 8 cells each here.

    A port is a plane element: the cells it activates are the product of its
    spans on the axes that are neither its p_dir nor the one axis it is flat
    on.  Both ports span the 8-cell strip width in y.
    """
    out = []
    for label, start, stop, p_dir in port_boxes(p):
        i0, i1, j0, j1, k0, k1 = mesh_indices(start, stop)
        axes = {"x": (i0, i1), "y": (j0, j1), "z": (k0, k1)}
        flat = [ax for ax in ("x", "y", "z") if axes[ax][0] == axes[ax][1]]
        cells = 1
        for ax in ("x", "y", "z"):
            if ax == p_dir or ax in flat:
                continue
            cells *= axes[ax][1] - axes[ax][0]
        out.append((label, cells))
    return out


def audit_solver_output(text: str, where: str, p: dict,
                        rep: str = "metal", phase: str = "solve") -> tuple:
    """(problems, notes) for one captured solver log.  Never raises.

    PROBLEMS are the things that mean the log describes a geometry other than
    the one that was asked for.  NOTES are the numbers a reader needs in order
    to check that for themselves.  guard_solver_output() turns the former into
    exit 4 and prints the latter.

    `phase` is "setup-probe" or "solve", and it governs EXACTLY one question:
    is the ABSENCE of the "Number of PEC edges:" line evidence against the
    model?  On the solve it is -- the numbers come from that run, and a run
    that never counted PEC edges cannot show the strip attached.  On a
    SETUP-ONLY probe it is NOT: openEMS may print that line only during a full
    run, so demanding it in a setup log made `--strip auto` unable to resolve
    on a host where it was absent -- a permanent exit 4 that said nothing
    about the model and rejected candidates that had no warning against them.
    Everything else (Unused primitive, Active cells, and the floor when the
    line IS present) is identical in both phases.
    """
    if phase not in ("setup-probe", "solve"):
        raise ValueError("phase must be 'setup-probe' or 'solve', not %r"
                         % (phase,))
    problems = []
    notes = []
    for pat, what in ((_UNUSED_PAT, "a primitive CSXCAD did not apply"),
                      (_ZERO_LOAD_PAT, "a lumped load with no active cells")):
        for line in text.splitlines():
            if pat.search(line):
                problems.append("%s -> %r" % (what, line.strip()))

    expect_faces = _expected_pec_faces(p, rep)
    hits = _PEC_EDGES_PAT.findall(text)
    if not hits:
        if phase == "solve":
            problems.append(
                "expected line not found: no 'Number of PEC edges: <N>' in "
                "the captured %s log, so the strip cannot be shown to have "
                "attached" % where)
        else:
            notes.append(
                "note: no 'Number of PEC edges:' line in this setup-only log "
                "-- openEMS may print it only during a full run, so this "
                "probe judges attachment from the Unused-primitive and "
                "Active-cells signals only")
    else:
        seen = max(int(h) for h in hits)
        if seen < PEC_EDGES_FLOOR:
            problems.append(
                "the strip did not attach: %d PEC edges, below the floor of "
                "%d (representation %r; the sheets should contribute %d "
                "faces, and a dropped strip leaves only the port-1 plane)"
                % (seen, PEC_EDGES_FLOOR, rep, expect_faces))
        else:
            notes.append("%d PEC edges (floor %d; the sheets should "
                         "contribute %d faces)"
                         % (seen, PEC_EDGES_FLOOR, expect_faces))

    actives = _ACTIVE_PAT.findall(text)
    expects = _expected_active_cells(p)
    for i, count in enumerate(actives):
        if i < len(expects):
            label, expect = expects[i]
        else:
            label, expect = "an unidentified element", None
        notes.append("%s: Active cells: %s (expected %s)"
                     % (label, count, "?" if expect is None else expect))
    return problems, notes


def guard_solver_output(text: str, where: str, p: dict,
                        rep: str = "metal", phase: str = "solve") -> None:
    """Exit 4 if openEMS reported geometry it did not apply.  Trap (11).

    `phase` is forwarded to audit_solver_output(); the dry-run call site is a
    setup-only probe, the solve call site is a solve.
    """
    problems, notes = audit_solver_output(text, where, p, rep, phase=phase)
    for note in notes:
        print("guard: %s" % note)
    if not problems:
        return
    print("MODEL NOT APPLIED (%s)" % where, file=sys.stderr)
    print("  openEMS said the geometry it was given is not the geometry it "
          "will solve (%d line(s)):" % len(problems), file=sys.stderr)
    for problem in problems:
        print("    %s" % problem, file=sys.stderr)
    print("  A dropped primitive means the solve runs on EMPTY AIR: "
          "|S11| ~ 1, Z ~ 300 ohm, port1->port2 ~ -94 dB.", file=sys.stderr)
    print("  Nothing downstream of this run is readable; refusing to report "
          "exit 0 for it.", file=sys.stderr)
    raise SystemExit(4)


def _setup_probe(p: dict, rep: str, threads: int = 2) -> tuple:
    """Build `rep` and run openEMS's SETUP-ONLY path; return (log, probe dir).

    No timestep is taken, so this is the cheap way to ask the only question
    that matters about a representation: does the solver KEEP the primitives
    it was given?  The probe directory is a throwaway; `outdir` is never
    touched on any path that calls this.

    The directory is RETURNED, not swallowed: every caller dumps it alongside
    the log, so the operator can go and inspect what the engine actually left
    on disk instead of trusting a verdict line.
    """
    FDTD, _csx = build_model(p, rep)
    probe_dir = tempfile.mkdtemp(prefix="oems-strip-probe-%s-" % rep)
    with _captured_output() as tmp:
        try:
            FDTD.Run(probe_dir, cleanup=True, setup_only=True, verbose=1,
                     numThreads=threads)
        finally:
            text = read_captured(tmp)
    return text, probe_dir


_RESOLVED_ANNOUNCED = False


def announce_resolution(line: str, stream=sys.stdout) -> None:
    """Print a 'STRIP REPRESENTATION RESOLVED:' line exactly ONCE.

    Two layers want to say this -- run_solve() when it resolves the
    representation, and main() when the bindings turn out to be missing -- and
    on the no-bindings path BOTH run, so the same sentence would otherwise
    appear twice in one report.  The first caller wins, later ones are silent.
    """
    global _RESOLVED_ANNOUNCED
    if _RESOLVED_ANNOUNCED:
        return
    _RESOLVED_ANNOUNCED = True
    print(line, file=stream)


# ---------------------------------------------------------------------------
# WHAT A PROBE TELLS US, AND WHAT IT MUST SHOW US.
# A captured setup log of ZERO bytes is not a statement about the model: it
# means the fd-level capture returned nothing at all, and must never be
# reported as "line missing" -- that is a verdict on the solver when the fault
# is in the harness.  And a probe that IS judged must be dumped IN FULL: a host
# run rejected all three candidates while printing only problems[0], so the
# operator could not see that no candidate had a warning against it, and the
# run told us nothing at all about what the engine had said.  Both rules are
# enforced here.
# ---------------------------------------------------------------------------

EMPTY_CAPTURE = (
    "captured setup log was EMPTY (0 bytes): the harness captured no solver "
    "output at all; this is a capture failure, not a solver verdict")


def _empty_capture(text: str) -> bool:
    """True when the capture holds nothing but whitespace -- a HARNESS fault.

    Checked BEFORE any regex, per candidate: a missing line in an empty log is
    not evidence about the solver, and reporting it as one buries the fact
    that there was nothing to read.
    """
    return len(text.strip()) == 0


def dump_captured_log(tag: str, text: str, probe_dir: str = None) -> None:
    """Print one captured log IN FULL, delimited, BEFORE any verdict on it.

    Nothing about a probe may be hidden behind a summarised problem line: the
    operator has to be able to read the engine's own words and judge the
    verdict being drawn from them.  `probe_dir` is printed too, so the
    directory can be inspected directly.
    """
    n_lines = len(text.splitlines())
    print("--- %s: captured setup log (%d lines, %d bytes) ---"
          % (tag, n_lines, len(text.encode("utf-8"))))
    if probe_dir:
        print("    probe directory: %s" % probe_dir)
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")
    print("--- end %s log ---" % tag)


def _accept_note(text: str) -> str:
    """Which signals an ACCEPTED setup probe actually used.  Names them."""
    if _PEC_EDGES_PAT.search(text):
        return ("no 'Unused primitive' warning, no zero-active-cells load, "
                "PEC edges above the floor (signals used: Unused-primitive "
                "+ Active-cells + PEC-edges)")
    return ("no 'Unused primitive' warning, no zero-active-cells load "
            "(signals used: Unused-primitive + Active-cells; this setup-only "
            "log carries no 'Number of PEC edges:' line, which openEMS may "
            "print only during a full run)")


def _fresh_process_hint(empty_rep: str, good_rep: str) -> str:
    """The command that re-checks ONE candidate with nothing before it.

    openEMS keeps process-global state, so an EMPTY capture for one candidate
    while another candidate in the same process captured a log is evidence
    about the PROCESS, not about the model.  Name the way out of it.
    """
    return ("  HINT: candidate %r captured EMPTY in the SAME process where %r "
            "captured a non-empty log.  openEMS keeps process-global state, "
            "so a repeated Run() is not guaranteed to behave like the first; "
            "check %r alone, in a fresh process:\n"
            "      python3 %s --probe-only --strip %s"
            % (empty_rep, good_rep, empty_rep, sys.argv[0], empty_rep))


def resolve_strip(p: dict, threads: int = 2) -> tuple:
    """Try each candidate in STRIP_CANDIDATES; return (rep, its captured log).

    Every probe is SETUP-ONLY and is never a solve.  The first candidate whose
    log survives audit_solver_output(phase="setup-probe") wins, and nothing
    after it is probed.  If every candidate is rejected there is no fallback
    that reports numbers -- the numbers would describe empty air -- so that is
    exit 4.

    EVERY probed log is dumped in full before the verdict on it, accepted or
    not: see the block comment above.
    """
    winner = None
    winner_text = ""
    probed_empty = []
    probed_nonempty = []
    hinted = False
    for rep in STRIP_CANDIDATES:
        if winner is not None:
            print("candidate %s: NOT TRIED (%s accepted)" % (rep, winner))
            continue
        try:
            text, probe_dir = _setup_probe(p, rep, threads)
        except ImportError:
            # Missing bindings are NOT a candidate failure: they are an
            # environment fault that main() must see so it can exit 5.
            raise
        except StripUnavailable as exc:
            print("candidate %s: REJECTED -- %s" % (rep, exc))
            continue
        except Exception as exc:
            # Ditto for `except Exception` on purpose, NOT BaseException: a
            # binding that rejects AddBox(priority=) or AddLumpedPort(
            # priority=) raises TypeError, not StripUnavailable.  Dying there
            # costs the operator a manual host round trip -- the exact cost
            # this multi-candidate loop exists to avoid -- so record it and
            # move to the next candidate.  SystemExit is a BaseException, so a
            # guard failure inside the probe still propagates.
            print("candidate %s: REJECTED -- %s: %s"
                  % (rep, type(exc).__name__, exc))
            continue
        dump_captured_log("candidate %s" % rep, text, probe_dir)
        if _empty_capture(text):
            probed_empty.append(rep)
            print("candidate %s: REJECTED -- %s" % (rep, EMPTY_CAPTURE))
            if probed_nonempty and not hinted:
                print(_fresh_process_hint(rep, probed_nonempty[0]))
                hinted = True
            continue
        if probed_empty and not hinted:
            # The EMPTY arrived first; say so now that a good log exists to
            # compare it against, so the hint is never lost to the loop order.
            print(_fresh_process_hint(probed_empty[0], rep))
            hinted = True
        probed_nonempty.append(rep)
        problems, _notes = audit_solver_output(
            text, "setup-only strip candidate %r" % rep, p, rep,
            phase="setup-probe")
        if problems:
            print("candidate %s: REJECTED -- %s" % (rep, problems[0]))
            for extra in problems[1:]:
                print("    also: %s" % extra)
            continue
        print("candidate %s: ACCEPTED -- %s" % (rep, _accept_note(text)))
        winner, winner_text = rep, text
    if winner is None:
        announce_resolution("STRIP REPRESENTATION RESOLVED: none -- every "
                            "candidate was rejected by the setup probe",
                            stream=sys.stderr)
        raise SystemExit(4)
    announce_resolution("STRIP REPRESENTATION RESOLVED: %s" % winner)
    print("  exact geometry?      : %s" % strip_exactness_line(winner))
    return winner, winner_text


def probe_only(p: dict, rep: str, threads: int = 2) -> int:
    """--probe-only: ONE representation, ONE setup probe, one FRESH process.

    openEMS keeps process-global state, so a second FDTD.Run() in the same
    process is NOT guaranteed to behave like the first.  `--strip auto`
    probes up to three candidates in ONE process; `--probe-only --strip X`
    reproduces the known-good single-Run path exactly, in a process that has
    built nothing before it.  It is the fallback whenever `auto`'s in-process
    probes disagree with each other or return an empty capture.

    No resolution, no solve, and `outdir` is never created.  Returns
    0 accepted / 4 rejected / 5 no bindings.
    """
    tag = "probe-only %s" % rep
    try:
        text, probe_dir = _setup_probe(p, rep, threads)
    except ImportError as exc:
        print("\nRESULT: NO-BINDINGS -- openEMS is not importable here (%s)."
              % exc)
        print("        --probe-only could not probe %r at all; nothing was "
              "built and outdir was not touched." % rep)
        return 5
    except StripUnavailable as exc:
        print("%s: REJECTED -- %s" % (tag, exc))
        return 4
    except Exception as exc:
        # Same rule as the candidate loop: a binding that rejects a kwarg is
        # a candidate failure, not a reason to die with a traceback.
        print("%s: REJECTED -- %s: %s" % (tag, type(exc).__name__, exc))
        return 4
    dump_captured_log("candidate %s" % rep, text, probe_dir)
    if _empty_capture(text):
        print("%s: REJECTED -- %s" % (tag, EMPTY_CAPTURE))
        return 4
    problems, notes = audit_solver_output(
        text, "setup-only strip candidate %r" % rep, p, rep,
        phase="setup-probe")
    for note in notes:
        print("%s: %s" % (tag, note))
    if problems:
        print("%s: REJECTED -- %s" % (tag, problems[0]))
        for extra in problems[1:]:
            print("    also: %s" % extra)
        return 4
    print("%s: ACCEPTED -- %s" % (tag, _accept_note(text)))
    print("  outdir was NOT created; this was a setup probe, not a solve.")
    return 0


def run_solve(p: dict, outdir: str, dry_run: bool, threads: int = 2,
              strip: str = "auto") -> int:
    """Build the model and (unless dry_run) run it.  Returns an exit code."""
    resolved_text = ""
    if strip == "auto":
        rep, resolved_text = resolve_strip(p, threads)
    else:
        rep = strip
        announce_resolution("STRIP REPRESENTATION RESOLVED: %s (explicit "
                            "--strip, not probed)" % rep)
        print("  exact geometry?      : %s" % strip_exactness_line(rep))

    if dry_run:
        # Setup-only probe: CSXCAD builds the mesh and the operators and then
        # stops before the first timestep.  Seconds, not ~49 s, and it prints
        # the warnings that say whether the geometry was applied.  It writes
        # to a throwaway directory: `outdir` is never touched on this path.
        # In --strip auto mode the winner's probe already produced (and
        # dumped) this text; only a probe taken HERE still needs dumping.
        if resolved_text:
            text = resolved_text
            sys.stdout.write(text)
            if text and not text.endswith("\n"):
                sys.stdout.write("\n")
        else:
            text, probe_dir = _setup_probe(p, rep, threads)
            dump_captured_log("dry-run probe %s" % rep, text, probe_dir)
            if _empty_capture(text):
                print("EMPTY CAPTURE -- %s" % EMPTY_CAPTURE)
        report_solver_provenance(text)
        guard_solver_output(text, "setup-only", p, rep, phase="setup-probe")
        print("SETUP-ONLY PROBE OK: openEMS accepted every primitive; no "
              "timestep was taken and %r was not touched." % outdir)
        return 0

    # The model is built exactly ONCE on the solve path, for the resolved
    # representation.
    FDTD, _csx = build_model(p, rep)
    os.makedirs(outdir, exist_ok=True)
    # trap (7): thread count is a Run() kwarg; there is no SetMaxThreads().
    # trap (11): fd 1/2 is captured and scanned BEFORE the port records are
    # read, so a solve on empty geometry fails with exit 4 instead of leaving
    # a plausible-looking port record set behind.
    with _captured_output() as tmp:
        try:
            FDTD.Run(outdir, cleanup=True, verbose=1, numThreads=threads)
        finally:
            text = read_captured(tmp)
    sys.stdout.write(text)
    report_solver_provenance(text)
    guard_solver_output(text, "solve", p, rep)

    missing = [n for n in ("port_ut_1", "port_it_1", "port_ut_2", "port_it_2")
               if not os.path.exists(os.path.join(outdir, n))]
    if missing:
        print("SOLVE FAILED: no port records for %s in %s"
              % (", ".join(missing), outdir), file=sys.stderr)
        return 3

    print("SOLVE OK: port records in %s" % outdir)
    print("Next: DFT port_ut_1/port_it_1 at %r Hz, then" % F_REF)
    print("      S11 = (U/Zref - I) / (U/Zref + I), Zref = 50 ohm.")
    print("      |S11| is plane-invariant; phase needs de-embedding to 20.4 mm.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="openEMS referee for E11 termination build A (p51).")
    ap.add_argument("--out", default="evidence/referee",
                    help="output directory (default: evidence/referee)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the geometry echo and stop before FDTD.Run()")
    ap.add_argument("--with-bindings", action="store_true",
                    help="with --dry-run, also build the CSX model and run "
                         "openEMS's setup-only probe -- seconds, no timestep "
                         "is taken (requires the bindings). Exits 4 if "
                         "openEMS reports geometry it did not apply.")
    ap.add_argument("--threads", type=int, default=2,
                    help="Run(numThreads=...) (default: 2)")
    ap.add_argument("--strip", choices=STRIP_CHOICES, default="auto",
                    help="how the strip is represented (default: auto = "
                         "setup-probe %s in that order and keep the first "
                         "that passes; 'metal' is the 2026-11-09 control and "
                         "is EXPECTED to fail; 'slab' is a physics "
                         "deviation)" % " -> ".join(STRIP_CANDIDATES))
    ap.add_argument("--probe-only", action="store_true",
                    help="probe ONE representation and stop: requires an "
                         "explicit --strip X (exit 2 without one), build the "
                         "model, run ONE setup probe, dump the FULL captured "
                         "log and the audit verdict, then exit 0 accepted / "
                         "4 rejected / 5 no bindings.  Never resolves, never "
                         "solves, never creates --out.  Use it when `auto`'s "
                         "in-process probes disagree.")
    args = ap.parse_args(argv)

    p = plan()

    # The echo is always printed first: it is the audit trail, and it is the
    # one thing that must be reviewable without the solver installed.
    echo(p, args.strip)

    if args.probe_only:
        # One representation, one Run(), one process.  `auto` is the
        # multi-candidate resolver and cannot be probed once, so demand the
        # explicit choice rather than guessing which candidate was meant.
        if args.strip == "auto":
            print("USAGE ERROR: --probe-only probes ONE representation, so it "
                  "requires an explicit --strip X (%s); --strip auto is the "
                  "multi-candidate resolver."
                  % " | ".join(STRIP_CANDIDATES), file=sys.stderr)
            return 2
        return probe_only(p, args.strip, args.threads)

    if args.dry_run and not args.with_bindings:
        if args.strip == "auto":
            announce_resolution(
                "STRIP REPRESENTATION RESOLVED: (unresolved) -- --strip auto "
                "probes candidates with the bindings; none was probed here.")
        else:
            announce_resolution(
                "STRIP REPRESENTATION RESOLVED: %s (explicit --strip, not "
                "probed)" % args.strip)
        print("RESULT: DRY-RUN -- geometry echo only, openEMS never imported,")
        print("        FDTD.Run() not called. This script is AUTHORED-")
        print("        UNEXERCISED; nothing here is a validated model result.")
        return 0

    try:
        return run_solve(p, args.out, args.dry_run, args.threads,
                         strip=args.strip)
    except ImportError as exc:
        if args.strip == "auto":
            announce_resolution(
                "STRIP REPRESENTATION RESOLVED: (unresolved) -- --strip auto "
                "probes candidates with the bindings; none was probed here.")
        else:
            announce_resolution(
                "STRIP REPRESENTATION RESOLVED: %s (explicit --strip, not "
                "probed)" % args.strip)
        print("\nRESULT: NO-BINDINGS -- openEMS is not importable here (%s)." % exc)
        print("        Geometry echo above is pure arithmetic and stands.")
        print("        The model itself is AUTHORED-UNEXERCISED.")
        if args.with_bindings:
            print("        --with-bindings was requested and could not be")
            print("        honoured: exit code 5, not 0 -- the model was")
            print("        never exercised.")
            return 5
        return 0


if __name__ == "__main__":
    sys.exit(main())
