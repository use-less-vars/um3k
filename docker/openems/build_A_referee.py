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
              called "Unused", or a lumped load with "Active cells: 0" --
              only on --port2-api element, the one arm whose load must own
              cell volume; a zero-thickness port is EXPECTED to read 0, see
              trap (13)), or
              the strip did not attach ON THE SOLVE PATH (there the "Number
              of PEC edges:" line is REQUIRED and must clear its floor; a
              SETUP-ONLY probe does not require it -- see
              audit_solver_output(phase=...)), or no --strip candidate passed
              its setup probe.  Nothing downstream of that is readable; see
              trap (11).
    Exit 5  = --with-bindings was requested but openEMS is not importable, so
              the model was never exercised at all.  A plain --dry-run (no
              --with-bindings) still exits 0 in that situation.
    Exit 6  = openEMS rejected the CONSTRUCTION of port 2 (the load): the
              binding raised while building csx.AddLumpedElement(...) or
              FDTD.AddLumpedPort(2, ...).  This is NOT exit 4 -- exit 4 means
              the load was built and the LOG condemns it ("Active cells: 0"
              on the element arm, or an unused-primitive line naming it), while
              6 means it was never built at all.  The diagnostic prints the
              API name, the exact call, the exception verbatim, and the retry
              ladder  --port2-api port -> port-priority -> port-zext ->
              element.

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

(12) AddLumpedPort(2, ...) is NOT the same construction as transcribing what
    ports.py:266-271 does.  A 2026-11-12 host probe,
        --probe-only --strip priority --port2-api element
    printed, verbatim,
        Warning: Unused primitive (type: Box) detected in property: port_2_resist!
    so a hand-built csx.AddLumpedElement("port_2_resist", ...) plus our OWN
    AddBox(priority=10) does NOT attach the load -- CSXCAD drops it the way it
    dropped the strip sheets in trap (11).  AddLumpedPort(2, ...) is the
    construction with evidence BEHIND it: the 2026-11-09 full solve built the
    load through it, and its port_ut_2 / port_it_2 post-process to
    V2/I2 = 50.00 ohm -- terminated correctly.  'element' is therefore an
    ALTERNATIVE that was DEMOTED on 2026-11-12; never make it the default
    again without a probe that shows the load's cells ACTIVE.

(13) A zero-thickness lumped port (or element) is a SURFACE impedance: it owns
    no cell volume, so `Active cells: 0` on its LOAD line is EXPECTED for a
    port that works perfectly.  The 2026-11-09 solve measured V2/I2 = 50.00
    ohm through AddLumpedPort(2, ...) -- a terminated 50 ohm load -- and this
    file nonetheless failed it for reading `Active cells: 0`.  That guard was
    MISCALIBRATED, and the 'repair' it drove -- AddLumpedElement, i.e. the
    'element' arm -- emitted
        Warning: Unused primitive (type: Box) detected in property: port_2_resist!
    and genuinely BROKE the load (trap (12)): a fix applied to a non-fault.
    The guard now demands `Active cells > 0` ONLY for --port2-api element, the
    one arm that gives the element cell volume.  On port / port-priority /
    port-zext `Active cells: 0` is ACCEPTED, and the ONLY load failure there
    is an unused-primitive line naming the port property.  Corollary for
    accept_note(): on those arms the load's ACTIVATION belongs in the
    NOT-verified clause, never in the established one.  What IS established is
    the port's PRESENCE -- and only through the absence of such an
    unused-primitive line (on a full solve, also its port_ut_2/port_it_2 V/I
    ratio).  Its `Active cells` count is evidence in neither direction.

(14) FDTD.AddMSLPort(1, <strip property>, ...) is NOT "the lumped port under
    another name".  Three of its failure modes are SILENT:
    (a) z GEOMETRY.  ports.py:348 assigns MSL_stop[exc] = MSL_start[exc]
        BEFORE the metal box is added, so the metal plane comes from START[z]
        and STOP[z] is DISCARDED for it.  The box must therefore START on the
        strip plane (z = z_strip = 1.6 mm); stop[z] survives only as the FAR
        END of the three voltage probes (ports.py:373-374) and as the sign of
        upside_down (ports.py:326).  Give both ends the same z and NOTHING
        raises: the metal still lands correctly, but upside_down = sign(0) = 0,
        the excitation vector is scaled to zero and the launch excites
        nothing at all.  port1_box() and msl_probe_planes() both refuse that
        box, so the silence cannot reach a solve.
    (b) ORDER.  MSLPort reads GetLines(prop_ny) in its CONSTRUCTOR
        (ports.py:351-353) and raises "At least 5 lines in propagation
        direction required!" if the mesh has not been handed over yet.
        build_model() must call g.SetLines(...) BEFORE add_port1(); it does
        (SetLines at ~1305-1315, add_port1 at ~1341), and that order is the
        reason, not a matter of taste.
    (c) FIVE probe records, not two.  There is no port_ut_1 / port_it_1 in an
        MSL run: the voltage probes are port_1_utA / utB / utC and the
        current probes are port_1_itA / itB (ports.py:382 adds TWO current
        probes; ports.py:440 indexes I_delta[0]).  extract_s11() would raise
        FileNotFoundError on the lumped names, and port1_probe_names() is the
        one place that knows which set this run wrote.

--------------------------------------------------------------------------
NUMERIC FIELDS, AND THE LOAD AS ITS OWN VERDICT
--------------------------------------------------------------------------
openEMS separates a label from its colon with a TAB -- "Number of PEC edges
<TAB>: 1119" -- so the space-only patterns this file used to carry matched
nothing in a real log.  Every labelled integer now goes through _find_int(),
and the two fields that can belong to more than one primitive ("Active
cells", "Number of PEC edges") are read out of the headed block that owns
them (_section()), with the reader TOLD when a block cannot be located
instead of being handed a number from somewhere else.

The strip and the load are DIFFERENT verdicts.  What CSXCAD keeps for the
strip proves nothing about the load, and the load's own line is the only thing
that speaks for it: the 2026-11-09 run printed "--- Series/Parallel Lumped RLC
load ---" with "Active cells: 0" in the same log as the strip's primitives,
and on a zero-thickness arm that reading is EXPECTED rather than a fault (trap
(13)), so it is evidence about which arm built the load, not about the strip.
A strip verdict must not be able to answer for the load.  resolve_strip()
therefore judges the strip ONLY and can RESOLVE whatever the load's line says,
while a "LOAD: ..." line reports the load, verbatim and separately, on every
path: it is exit 4 on a real solve and a note on a setup probe.
--port2-api chooses how the load is built; the chosen API, its rationale and
the exact call are printed.

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
import cmath
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
        "  port 2 priority     : %s (see the PORT 2 API line; forwarded only "
        "by --port2-api port-priority / port-zext)" % priority,
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


# ---------------------------------------------------------------------------
# PORT 2 (THE LOAD): WHICH API BUILDS IT.
#
# The load is the primitive this file spent 2026-11-09 .. 2026-11-12
# misjudging.  The 2026-11-09 host run printed
#
#     --- Series/Parallel Lumped RLC load ---
#     Active cells: 0
#
# and this file read that as a dead load.  It is not one (trap (13)): the
# 50 ohm termination WAS activated on that arm -- its port_ut_2 / port_it_2
# post-process to V2/I2 = 50.00 ohm, a correctly terminated 50 ohm load -- and
# `Active cells: 0` is the EXPECTED reading for a zero-thickness lumped port,
# which is a surface impedance and owns no cell volume.  That count proves
# nothing either way about whether the load attached.  What WOULD show a
# dropped load is an "Unused primitive" line naming the port property (trap
# (12)), and no such line can be squared with a V2/I2 of 50.00 ohm.  The recon
# (infra/openems/reference/) says exactly what AddLumpedPort(2, R, ...) builds
# for it:
#
#   openEMS.pyx:339   def AddLumpedPort(self, port_nr, R, start, stop, p_dir,
#                                      excite=0, **kw)
#                     -> ports.LumpedPort(self.__CSX, port_nr, R, start,
#                                         stop, p_dir, excite, **kw)
#   ports.py:107-109  self.priority = 0
#                     if 'priority' in kw: self.priority = kw['priority']
#   ports.py:266-271  lumped_R = CSX.AddLumpedElement(lbl, ny=self.exc_ny,
#                                                     caps=True, R=self.R)
#                     lumped_R.AddBox(self.start, self.stop,
#                                     priority=self.priority)
#   ports.py:280-296  the port_2_ut / port_2_it probe boxes
#   CSXCAD.pyx:382    def AddLumpedElement(self, name, **kw)
#
# So the load is ONE zero-thickness AddBox on ONE LumpedElement property, and
# a priority reaches it only through **kw.
#
# STATUS 2026-11-12.  Two host runs have now answered part of that question:
#   * the 2026-11-09 FULL SOLVE built the load with AddLumpedPort(2, R_PORT,
#     ...) -- no priority kwarg -- and its port_ut_2 / port_it_2 post-process
#     to V2/I2 = 50.00 ohm, i.e. a correctly terminated 50 ohm load.  'port'
#     is therefore the DEFAULT.
#   * a 2026-11-12 --probe-only run with --port2-api element printed
#         Warning: Unused primitive (type: Box) detected in property:
#         port_2_resist!
#     so writing ports.py:266-271 out by hand -- AddLumpedElement plus OUR OWN
#     AddBox(priority=10) -- does NOT attach the load.  That arm is a
#     REGRESSION, not a fix: 'element' was DEMOTED on 2026-11-12 and stays
#     only so a known-worse alternative can still be reproduced (trap (12)).
# --port2-api keeps all four arms, prints the choice, its rationale and the
# exact call on every path, and records the answer a host run produces.
# ---------------------------------------------------------------------------

PORT2_API = "port"           # replaced from --port2-api in main()
PORT2_API_CHOICES = ("port", "element", "port-priority", "port-zext")

# Which arm's load has to own cell volume, and which arms are plane-thin.
# Trap (13): 'port' and 'port-priority' build the zero-thickness element that
# ports.py:266-271 builds -- a SURFACE impedance owning no cell volume, so
# "Active cells: 0" is the EXPECTED reading for a working load.  'port-zext'
# is deliberately NOT listed as zero-thickness (it fills one z cell), but its
# count is still not failed on: see load_verdict().  'element' is the only arm
# whose element must be seen to occupy a cell, so it is the only arm that
# FAILS on "Active cells: 0".
PORT2_CELLS_REQUIRED_ARMS = ("element",)
PORT2_ZERO_THICKNESS_ARMS = ("port", "port-priority")

PORT2_RATIONALE = {
    "element": (
        "ALTERNATIVE, DEMOTED 2026-11-12 -- build the element the way "
        "ports.py:266-296 builds it: csx.AddLumpedElement('port_2_resist', "
        "caps=True, R=50) plus one AddBox(priority=...) plus the port_2_ut / "
        "port_2_it probe boxes, all written out HERE, so this file owns the "
        "box and the priority instead of Port's **kw plumbing.  DEMOTED "
        "because a 2026-11-12 host probe (--probe-only --strip priority "
        "--port2-api element) printed, verbatim, \"Warning: Unused primitive "
        "(type: Box) detected in property: port_2_resist!\" -- transcribing "
        "ports.py does NOT attach the load.  It is a REGRESSION against "
        "'port', kept only so it can be reproduced; do not promote it."),
    "port": (
        "DEFAULT -- FDTD.AddLumpedPort(2, 50, ...) with NO priority kwarg, so "
        "Port keeps self.priority = 0 (ports.py:107-109) and hands 0 to the "
        "element's AddBox (ports.py:271).  This is the construction with "
        "evidence behind it: the 2026-11-09 full solve built the load through "
        "exactly this call, and its port_ut_2 / port_it_2 post-process to "
        "V2/I2 = 50.00 ohm, i.e. a correctly terminated 50 ohm load.  The "
        "evidence is that post-processed V2/I2; no host log of that run's "
        "LOAD lines is quoted in this file, so this entry makes no claim "
        "about their 'Active cells' count."),
    "port-priority": (
        "FDTD.AddLumpedPort(2, 50, ..., priority=10): openEMS.pyx:339 "
        "forwards **kw into Port.__init__, so 10 lands on the element's "
        "AddBox (ports.py:107-109, 271) and the load wins the one cell the "
        "strip boxes argue over.  This is the construction this file carried "
        "before --port2-api existed.  It is NOT the one with evidence: the "
        "2026-11-09 run whose V2/I2 came out at 50.00 ohm went through "
        "AddLumpedPort(2, ...) with no priority kwarg at all, so treat the "
        "priority as UNTESTED rather than as the fix."),
    "port-zext": (
        "EXPERIMENT -- give the element ONE CELL of z extent (%g .. %g mm) "
        "instead of zero so it has cell volume at all, plus priority=10.  A "
        "plane-thin element that occupies no cell was the leading SUSPECT "
        "for 'Active cells: 0'; that suspicion is now WEAK, because the "
        "plane-thin AddLumpedPort(2, ...) of 2026-11-09 post-processed to "
        "V2/I2 = 50.00 ohm, yet this is still the one API that changes the "
        "geometry to test it.  It is a PHYSICS DEVIATION: the load fills a "
        "0.4 mm cell "
        "above the strip plane."
        % (K_STRIP * CELL * 1e3, (K_STRIP + 1) * CELL * 1e3)),
}

_AXIS = {"x": 0, "y": 1, "z": 2}     # CheckNyDir's mapping, x -> 0
_PORT2_P_DIR = "x"                    # the load resists the LONGITUDINAL E_x


# ---------------------------------------------------------------------------
# PORT 1 (THE LAUNCH): WHICH API BUILDS IT.
# The launch is a z-directed lumped PLANE: zero thickness in x at x_port, the
# full 8-cell strip width in y, from the ground wall (z = 0) up to the strip
# plane.  It is NOT a 2026-11-09 suspect -- those logs called the LOAD into
# question -- so nothing here is promoted as a fix; the arms exist so the
# launch can be moved independently of the load when a run has to be split.
#   mslport          -- DEFAULT.  FDTD.AddMSLPort(...): the reference's own
#                       microstrip port (infra/openems/reference/ports.py),
#                       which adds its own metal, writes its own FIVE probes
#                       and takes Z_ref from the FIELDS instead of from a
#                       declared 50 ohm.  A different PRIMITIVE, not a tweak
#                       of the lumped plane.
#   lumped           -- the original call, written out verbatim in add_port1()
#   priority         -- the same zero-volume plane, priority= forwarded to Port
#   x-cell           -- the box grows ONE CELL in x, so port and strip SHARE
#                       volume: a PHYSICS DEVIATION, not a fix
#   x-cell-priority  -- x-cell's geometry AND priority's kwarg at once
# The four lumped arms are the 2026-11-09 geometry and stay selectable; they
# are the only arms that were ever run, so they remain the control.
# ---------------------------------------------------------------------------
PORT1_API = "mslport"        # replaced from --port1-api in main()
PORT1_API_CHOICES = ("mslport", "lumped", "x-cell", "priority",
                     "x-cell-priority")

PORT1_RATIONALE = {  # one entry per arm; "mslport" is the DEFAULT, "lumped"
                     # is the 2026-11-09 control and is UNCHANGED, "priority"
                     # is TEST 3, "x-cell" is TEST 2 plus its deviation,
                     # "x-cell-priority" is both at once.
    "mslport": (
        "DEFAULT -- FDTD.AddMSLPort(1, <strip property>, start=[x_port, y_lo, "
        "z_strip], stop=[x_port+cell, y_hi, 0.0], prop_dir='x', exc_dir='z', "
        "excite=1).  This is the reference's own microstrip port "
        "(infra/openems/reference/ports.py:311-448): it adds the strip metal "
        "itself (ports.py:346-349), writes FIVE probes of its own "
        "(port_1_utA/B/C, port_1_itA/B), and takes Z_ref from the measured "
        "fields (ports.py:447) instead of from a declared 50 ohm.  It is the "
        "only arm whose extraction is ports.py's arithmetic, so it is the "
        "only arm that can be compared with the reference at all."),
    "lumped": (
        "DEFAULT, unchanged -- FDTD.AddLumpedPort(1, 50, ...) with p_dir='z', "
        "excite=1.0 and NO priority kwarg: a zero-volume plane at x_port "
        "spanning the 8-cell strip width and the full substrate height.  This "
        "is the call this file has always made, and it is the one the "
        "2026-11-09 runs made, so it stays the default."),
    "priority": (
        "FDTD.AddLumpedPort(1, 50, ..., priority=10): openEMS.pyx forwards "
        "**kw into Port.__init__, so 10 lands on the element's AddBox -- the "
        "same hop port 2's 'port-priority' arm uses.  It changes who owns a "
        "contested cell, NOT the geometry.  There is no evidence either way "
        "for the launch: nothing in the 2026-11-09 logs implicates it, so "
        "treat this as UNTESTED rather than as an improvement."),
    "x-cell": (
        "EXPERIMENT, and a PHYSICS DEVIATION -- give the launch ONE CELL of x "
        "extent (%g mm) instead of zero.  Zero-volume geometry was a suspect "
        "for the load, so the same question can be asked of the launch, but "
        "the answer costs physics: port and strip then SHARE the same x cell, "
        "so the launch sits inside the strip's cell instead of on a plane "
        "touching it." % (CELL * 1e3,)),
    "x-cell-priority": (
        "EXPERIMENT -- x-cell's one-cell-thick box AND priority=10 together.  "
        "It carries x-cell's PHYSICS DEVIATION and priority's lack of "
        "evidence at the same time, so a result from it answers neither "
        "question on its own."),
}


def _num(v: float) -> str:
    """One coordinate as the exact Python float the call receives."""
    return repr(float(v))


def _nums(points) -> str:
    """A start/stop triple as '[x, y, z]', exact floats."""
    return "[%s]" % ", ".join(_num(v) for v in points)


def _port2_probe_boxes(p: dict) -> list:
    """Port 2's two probe boxes: [(name, start, stop, kwargs)].

    Transcribed from ports.py:280-296, not invented.  The VOLTAGE probe spans
    the element box in p_dir and is collapsed to zero extent at each end; the
    CURRENT probe is collapsed to zero extent at the MIDDLE and carries
    weight = direction (+1 here: x_gap_hi > x_load) and norm_dir = exc_ny.
    The names are ports.py's own lbl_temp.format(...): 'port_2_ut',
    'port_2_it'.  These are the two files the extraction plan reads.
    """
    ny = _AXIS[_PORT2_P_DIR]
    start, stop = port2_box(p)
    mid = [0.5 * (start[i] + stop[i]) for i in range(3)]
    u_start = list(mid)
    u_start[ny] = start[ny]
    u_stop = list(mid)
    u_stop[ny] = stop[ny]
    i_start = list(start)
    i_start[ny] = mid[ny]
    i_stop = list(stop)
    i_stop[ny] = mid[ny]
    direction = 1 if stop[ny] > start[ny] else -1
    return [
        ("port_2_ut", u_start, u_stop, {"p_type": 0, "weight": -1}),
        ("port_2_it", i_start, i_stop,
         {"p_type": 1, "weight": direction, "norm_dir": ny}),
    ]


def _port2_call_text(p: dict, priority) -> str:
    """The exact port-2 construction the API in force performs, as source.

    Printed, not paraphrased: the reader has to be able to compare this with
    the log the solver actually produced.
    """
    start, stop = port2_box(p)
    prio = "" if priority is None else ", priority=%r" % (priority,)
    if PORT2_API == "element":
        out = ['resist = csx.AddLumpedElement("port_2_resist", caps=True, '
               'R=%r)' % (R_TERM,),
               "resist.AddBox(start=%s, stop=%s%s)"
               % (_nums(start), _nums(stop), prio)]
        for name, p_start, p_stop, kw in _port2_probe_boxes(p):
            kw_text = ", ".join("%s=%r" % (k, kw[k]) for k in sorted(kw))
            out.append('probe = csx.AddProbe("%s", %s)' % (name, kw_text))
            out.append("probe.AddBox(start=%s, stop=%s)"
                       % (_nums(p_start), _nums(p_stop)))
        return "\n".join("      " + line for line in out)
    kw = {"p_dir": _PORT2_P_DIR, "excite": 0.0}
    if PORT2_API != "port" and priority is not None:
        kw["priority"] = priority
    kw_text = ", ".join("%s=%r" % (k, kw[k]) for k in sorted(kw))
    return ("      FDTD.AddLumpedPort(2, %r, start=%s, stop=%s, %s)"
            % (R_TERM, _nums(start), _nums(stop), kw_text))


def port2_report(p: dict, priority=None, stream=sys.stdout) -> None:
    """Say which API builds the load, why, and the exact call.  Never a guess.

    The echo calls this because the echo is the only thing reviewable on a
    machine with no openEMS installed, and the load is the primitive whose
    construction the 2026-11-09 logs called into question.
    """
    start, stop = port2_box(p)
    stream.write("PORT 2 API: %s -- %s\n"
                 % (PORT2_API, PORT2_RATIONALE[PORT2_API]))
    stream.write("  exact call:\n%s\n" % _port2_call_text(p, priority))
    stream.write("  box                  : start = %s, stop = %s\n"
                 % (_nums(start), _nums(stop)))
    stream.write("  cell span            : %d in x, %d in y, %s in z\n"
                 % (int(round((stop[0] - start[0]) / CELL)),
                    int(round((stop[1] - start[1]) / CELL)),
                    "0 (plane)" if abs(stop[2] - start[2]) < 1e-15
                    else "%d" % int(round((stop[2] - start[2]) / CELL))))
    if PORT2_API == "port":
        prio_note = "none -- this API never forwards one (Port default 0)"
    elif priority is None:
        prio_note = "none -- the representation passes none (Port default 0)"
    else:
        prio_note = repr(priority)
    stream.write("  priority             : %s\n" % prio_note)


class Port2BuildError(SystemExit):
    """Exit 6: openEMS refused to CONSTRUCT the load.  Never a traceback.

    SystemExit on purpose -- it is a BaseException, so the `except Exception`
    clauses that turn a candidate probe into "candidate X: REJECTED" cannot
    swallow it.  A binding that rejects the load's construction is NOT a strip
    verdict, and reporting it as one sends the operator hunting the wrong
    thing; it aborts the run with the retry ladder instead.
    """

    def __init__(self, lines):
        self.lines = lines
        super().__init__(6)


def _port2_build_failure(p: dict, priority, exc: BaseException):
    """Say exactly which construction failed, then exit 6.  One place."""
    print("PORT 2 BUILD FAILED -- exit 6", file=sys.stderr)
    print("  API                 : --port2-api %s" % PORT2_API, file=sys.stderr)
    print("  openEMS raised      : %s: %s"
          % (type(exc).__name__, exc), file=sys.stderr)
    print("  exact call it was building:", file=sys.stderr)
    print(_port2_call_text(p, priority), file=sys.stderr)
    print("  This is a CONSTRUCTION failure: the load was never built at all.",
          file=sys.stderr)
    print("  It is NOT exit 4 -- exit 4 means the load WAS built and the log "
          "condemns it (\"Active cells: 0\" on the element arm, or an "
          "unused-primitive line naming it).", file=sys.stderr)
    print("  RETRY LADDER (most likely first):", file=sys.stderr)
    print("      --port2-api port  ->  port-priority  ->  port-zext  ->  "
          "element", file=sys.stderr)
    print("  i.e.  python3 %s --strip %s --port2-api <next>"
          % (sys.argv[0], PORT2_API), file=sys.stderr)
    raise Port2BuildError(None)


def add_port2(FDTD, csx, p: dict, priority=None) -> None:
    """Add the load (port 2) by the API --port2-api selected.  Never Run().

    PORT2_API is read HERE, at call time, so main() can set it once and every
    path that builds a model -- setup probe, dry-run probe, solve -- builds
    the same primitive.

    NOTHING raised by the binding escapes as a traceback: a TypeError from a
    C++ signature that does not accept a kwarg is a real possibility here (see
    trap (3) for the same class of failure), and a traceback costs the
    operator a host round trip without telling them what to try next.  Exit 6
    and the ladder say it.
    """
    try:
        _add_port2(FDTD, csx, p, priority)
    except Port2BuildError:
        raise
    except Exception as exc:                  # noqa: BLE001 -- see docstring
        _port2_build_failure(p, priority, exc)


def _add_port2(FDTD, csx, p: dict, priority=None) -> None:
    """The construction itself.  Every binding call lives inside here."""
    start, stop = port2_box(p)
    if PORT2_API == "element":
        # ports.py:266-271, written out here: no Port object, no **kw hop.
        # ports.py:267 passes ny=self.exc_ny, and exc_ny is
        # CSXCAD.Utilities.CheckNyDir(p_dir) (ports.py:22,260).  CheckNyDir is
        # NOT in infra/openems/reference/ -- it is a CSXCAD module this tree
        # does not carry -- so the integer it returns for p_dir='x' is not
        # knowable from the files here.  ny is therefore OMITTED rather than
        # guessed: a wrong 0 is worse than its absence.  AddBox carries start
        # AND stop, which is what defines the box.
        resist = csx.AddLumpedElement("port_2_resist", caps=True, R=R_TERM)
        if priority is None:
            resist.AddBox(start=start, stop=stop)
        else:
            resist.AddBox(start=start, stop=stop, priority=priority)
        # ports.py:280-296: the two probes.  KEPT because run_solve() requires
        # port_ut_2 / port_it_2 to exist (see the `missing = [...]` check), so
        # dropping them would turn this arm into a guaranteed exit 3.
        for name, p_start, p_stop, kw in _port2_probe_boxes(p):
            csx.AddProbe(name, **kw).AddBox(start=p_start, stop=p_stop)
        return
    kw = {"p_dir": _PORT2_P_DIR, "excite": 0.0}
    if PORT2_API != "port" and priority is not None:
        kw["priority"] = priority
    FDTD.AddLumpedPort(2, R_TERM, start=start, stop=stop, **kw)


def port2_box(p: dict) -> tuple:
    """(start, stop) of the load's box, for the PORT 2 API in force.

    Only 'port-zext' moves it: a zero-thickness element has no cell volume for
    the solver to activate, so that API gives the load ONE CELL of z extent.
    The box is consumed by port_boxes(), check_boxes(), the pre-flight and the
    active-cell expectation, so all of them follow the API with no second
    table to keep in step.
    """
    start = [p["x_load"], p["y_lo"], p["z_strip"]]
    stop = [p["x_gap_hi"], p["y_hi"], p["z_strip"]]
    if PORT2_API == "port-zext":
        stop = [p["x_gap_hi"], p["y_hi"], p["z_strip"] + CELL]
    return start, stop


PORT1_DEVIATION = (
    "PORT 1 (%s): port box overlaps the strip by one cell in x -- DEVIATION "
    "from the zero-volume launch; port and strip share volume.")


def port1_cell(p: dict) -> float:
    """The x cell port 1 sits on, taken FROM THE MESH, not from CELL.

    p["xs"] is _lines(NX) -- [i*CELL for i in range(NX+1)] -- and is what
    build_model() hands to g.SetLines("x", p["xs"]), so this is the width the
    solver will actually see (0.4 mm on the reference grid).  A grid change
    moves the port's box with it instead of leaving a stale constant behind.
    """
    xs = p["xs"]
    i = int(round(p["x_port"] / CELL))
    if i < 0 or i + 1 >= len(xs):
        raise SystemExit(
            "PORT 1 BOX: x_port = %.12g m has no cell to its right; an x-cell "
            "launch needs one" % (p["x_port"],))
    return xs[i + 1] - xs[i]


def port1_box(p: dict) -> tuple:
    """(start, stop) of the launch's box, for the PORT 1 API in force.

    The launch is z-directed: zero extent in x at x_port, the full 8-cell
    strip width in y, ground wall (z = 0) up to the strip plane.  Only the two
    x-cell arms move it, and they move it in x -- into the strip's own cell.
    The box is consumed by port_boxes(), check_boxes(), the pre-flight and the
    active-cell expectation, so all of them follow the API with no second
    table to keep in step.
    """
    if PORT1_API == "mslport":
        # MANDATORY GEOMETRY -- do not "tidy" this back to z = 0 / h_sub.
        # ports.py:348 does  MSL_stop[exc_ny] = MSL_start[exc_ny]  BEFORE it
        # adds the metal, so stop[z] is DISCARDED for the metal: the strip
        # plane comes from start[z] and must therefore BE z_strip.  stop[z]
        # survives only where ports.py still uses it -- as the far end of the
        # three voltage probes (ports.py:373-374) and as the sign source for
        # upside_down (ports.py:326).  A z extent of exactly 0 would give
        # upside_down = sign(0) = 0, hence exc_vec = 0: a silent zero
        # excitation with no error anywhere.
        start = [p["x_port"], p["y_lo"], p["z_strip"]]
        stop = [p["x_port"] + port1_cell(p), p["y_hi"], 0.0]
        if start[2] == stop[2]:
            raise SystemExit(
                "PORT 1 BOX (mslport): z_strip == stop z == %.12g m, so the "
                "MSL excitation would be scaled by upside_down = sign(0) = 0 "
                "and the launch would excite nothing" % (start[2],))
        return start, stop
    start = [p["x_port"], p["y_lo"], 0.0]
    stop = [p["x_port"], p["y_hi"], p["h_sub"]]
    if PORT1_API in ("x-cell", "x-cell-priority"):
        stop = [p["x_port"] + port1_cell(p), p["y_hi"], p["h_sub"]]
    return start, stop


def _port1_call_text(p: dict, priority) -> str:
    """The exact port-1 construction the API in force performs, as source.

    Printed, not paraphrased: the reader has to be able to compare this with
    the log the solver actually produced.
    """
    start, stop = port1_box(p)
    if PORT1_API == "mslport":
        # No priority= here: Port.__init__ defaults self.priority to 0
        # (ports.py:107-109) and MSLPort forwards it unconditionally
        # (ports.py:349), so the metal already lands at priority 0 -- the
        # same priority the lumped arms get by passing none.
        return ("      FDTD.AddMSLPort(1, <strip property>, start=%s, stop=%s,"
                " prop_dir='x', exc_dir='z', excite=1)"
                % (_nums(start), _nums(stop)))
    kw = {"p_dir": "z", "excite": 1.0}
    if PORT1_API in ("priority", "x-cell-priority") and priority is not None:
        kw["priority"] = priority
    kw_text = ", ".join("%s=%r" % (k, kw[k]) for k in sorted(kw))
    return ("      FDTD.AddLumpedPort(1, %r, start=%s, stop=%s, %s)"
            % (R_PORT, _nums(start), _nums(stop), kw_text))


def port1_report(p: dict, priority=None, stream=sys.stdout) -> None:
    """Say which API builds the launch, why, and the exact call.

    Same contract as port2_report(): the echo calls this, and the echo is the
    only thing reviewable on a machine with no openEMS installed.  For the two
    x-cell arms it also prints PORT1_DEVIATION -- moving the launch into the
    strip's cell is a physics change and every report of it says so.
    """
    start, stop = port1_box(p)
    stream.write("PORT 1 API: %s -- %s\n"
                 % (PORT1_API, PORT1_RATIONALE[PORT1_API]))
    stream.write("  exact call:\n%s\n" % _port1_call_text(p, priority))
    stream.write("  box                  : start = %s, stop = %s\n"
                 % (_nums(start), _nums(stop)))
    stream.write("  cell span            : %d in x, %d in y, %d in z\n"
                 % (int(round((stop[0] - start[0]) / CELL)),
                    int(round((stop[1] - start[1]) / CELL)),
                    int(round((stop[2] - start[2]) / CELL))))
    if PORT1_API == "mslport":
        prio_note = ("0 -- Port.__init__'s default (ports.py:107-109), "
                     "forwarded by MSLPort (ports.py:349); never a kwarg here")
    elif PORT1_API in ("lumped", "x-cell"):
        prio_note = "none -- this API never forwards one (Port default 0)"
    elif priority is None:
        prio_note = "none -- the representation passes none (Port default 0)"
    else:
        prio_note = repr(priority)
    stream.write("  priority             : %s\n" % prio_note)
    if PORT1_API == "mslport":
        _pl = msl_probe_planes(p)
        _fl = msl_bias_floor(p)
        stream.write(
            "  primitive            : FDTD.AddMSLPort -- the reference's own "
            "microstrip port,\n"
            "                         ports.py:311-448.  NOT a lumped plane: "
            "it adds metal,\n"
            "                         probes and its own extraction.\n"
            "  property object      : REUSED -- the strip's own property.  "
            "ports.py:349\n"
            "                         calls metal_prop.AddBox(..., "
            "priority=self.priority), i.e.\n"
            "                         priority 0, so the port metal "
            "coalesces with the strip\n"
            "                         instead of contesting it.\n"
            "  metal plane          : z = %s m == START z.  ports.py:348 does\n"
            "                         MSL_stop[exc] = MSL_start[exc]: stop z is "
            "DISCARDED\n"
            "                         for the metal.  stop z = 0.0 here "
            "supplies only the\n"
            "                         U-probe span and the excitation sign.\n"
            "  U probes             : 3, spanning z = %s -> 0.0 m (full "
            "start[exc]->stop[exc],\n"
            "                         ports.py:373-374); p_type=0.\n"
            "  I probes             : 2, FLATTENED on the strip plane "
            "z = %s m\n"
            "                         (ports.py:386); p_type=1, "
            "weight=direction, norm_dir=prop.\n"
            "  probe records        : %s\n"
            "  Z reference          : from the FIELDS -- "
            "sqrt(Et*dEt/(Ht*dHt)), ports.py:447.\n"
            "                         NOT a declared 50 ohm, and NOT asserted "
            "to equal one.\n"
            "  measplane            : x_port + 0.5*cell = %s m -> mesh index "
            "%d of %d,\n"
            "                         tie resolved DOWNWARD (numpy argmin "
            "returns the first\n"
            "                         minimum; the measplane sits exactly "
            "between two nodes).\n"
            "  prope_idx            : %r (clamped=%s, wraps grid=%s)\n"
            "  U probe x            : %s m   U_delta = %s m\n"
            "  I probe x            : %s m   I_delta = %s m\n"
            "  PEC accounting       : the MSL metal box is COINCIDENT with "
            "strip sheet A's\n"
            "                         first x cell -- same x span, same 8 y "
            "cells, flat at\n"
            "                         z_strip -- so it adds NO PEC area; the "
            "expected face count\n"
            "                         and PEC_EDGES_FLOOR are unchanged, and a "
            "FLOOR could not\n"
            "                         be broken by added metal anyway.\n"
            % (_num(p["z_strip"]), _num(p["z_strip"]), _num(p["z_strip"]),
               " ".join(PORT1_MSL_PROBES), _num(_pl["measplane_pos"]),
               _pl["meas_pos_idx"], len(p["xs"]) - 1, _pl["prope_idx"],
               _pl["clamped"], _pl["wrap"],
               _nums(_pl["u_pos"]), _nums(_pl["u_delta"]),
               _nums(_pl["i_pos"]), _nums(_pl["i_delta"])))
        stream.write(
            "  BIAS FLOOR (computed, not assumed): beta*dx = %.6f rad.  A "
            "two-wave field at\n"
            "    the exact probe planes gives %s\n"
            "    -- the reference estimator's own error at that reflection "
            "coefficient.\n"
            % (_fl["beta_dx_rad"],
               ", ".join("gamma=%.6g -> |dS11| = %.3e, Z_ref/Z_line = %.6f"
                         % (r["gamma"], r["s11_error_abs"],
                            r["z_ref_over_z_line"]) for r in _fl["rows"])))
    if PORT1_API in ("x-cell", "x-cell-priority"):
        stream.write(PORT1_DEVIATION % (PORT1_API,) + "\n")


def add_port1(FDTD, p: dict, priority=None, strip_prop=None) -> None:
    """Add the launch (port 1) by the API --port1-api selected.  Never Run().

    PORT1_API is read HERE, at call time, so main() can set it once and every
    path that builds a model -- setup probe, dry-run probe, solve -- builds
    the same primitive.

    The 'lumped' arm performs the ORIGINAL literal call, unchanged, because it
    is the default and must keep reproducing the geometry this file has always
    had; every other arm goes through port1_box().  Unlike add_port2() there is
    NO exit-6 wrapper: the load is the primitive with a construction-failure
    history, the launch has none, so a binding that refuses this call surfaces
    as the exception it is rather than as a port-1 verdict.
    """
    if PORT1_API == "lumped":
        FDTD.AddLumpedPort(
            1, R_PORT,
            start=[p["x_port"], p["y_lo"], 0.0],
            stop=[p["x_port"], p["y_hi"], p["h_sub"]],
            p_dir="z", excite=1.0)
        return
    if PORT1_API == "mslport":
        if strip_prop is None:
            raise SystemExit(
                "PORT 1 (mslport): no strip property handed in.  The MSL port "
                "adds its own metal ON the strip plane, so it must reuse the "
                "strip's property object; build_model() has to call "
                "add_port1(FDTD, p, priority=..., strip_prop=strip).")
        start, stop = port1_box(p)
        # excite is an INT here, not an impedance: ports.py:403 multiplies it
        # into a -1/0/+1 vector.  No priority kwarg -- see port1_report().
        FDTD.AddMSLPort(1, strip_prop, start=start, stop=stop,
                        prop_dir="x", exc_dir="z", excite=1)
        return
    start, stop = port1_box(p)
    kw = {"p_dir": "z", "excite": 1.0}
    if PORT1_API in ("priority", "x-cell-priority") and priority is not None:
        kw["priority"] = priority
    FDTD.AddLumpedPort(1, R_PORT, start=start, stop=stop, **kw)


def port_boxes(p: dict) -> list:
    """Both port footprints as (label, start, stop, propagation_axis).

    build_model() does not add these as primitives -- AddLumpedPort() creates
    them -- but they are checked against the same mesh, because a port that
    misses the grid is the other way a model quietly turns into air.

    Each footprint comes from its own box function -- port1_box() /
    port2_box() -- so --port1-api and --port2-api move them and the pre-flight
    moves with them.
    """
    start1, stop1 = port1_box(p)
    start2, stop2 = port2_box(p)
    # The MSL arm propagates along +x (ports.py:321, CheckNyDir(prop_dir)):
    # its metal is ONE cell of x on the strip plane, FLAT in z.  Reporting
    # p_dir="z" for it would make check_boxes() reject a box that is flat in z
    # along the very axis it claims to propagate on.
    if PORT1_API == "mslport":
        first = ("port 1 launch (x-directed, MSLPort)", start1, stop1, "x")
    else:
        first = ("port 1 launch (z-directed)", start1, stop1, "z")
    return [first, ("port 2 load (x-directed)", start2, stop2, "x")]


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
    for _n, (label, start, stop, p_dir) in enumerate(port_boxes(p)):
        idx = mesh_indices(start, stop)
        if _n == 0 and PORT1_API == "mslport":
            # The MSL port is the one box the plane rule above cannot describe:
            # it runs from the strip plane DOWN to the ground wall, so its z
            # index span is descending and its "cross-section" is the strip
            # width, not a launch aperture.  These are its own assertions --
            # replacing the generic ones for THIS arm only, never relaxing them
            # for the four lumped arms, which keep the code below untouched.
            n_x = int(round((stop[0] - start[0]) / CELL))
            if n_x != 1:
                raise SystemExit(
                    "PRE-FLIGHT FAILED: %s spans %d cells in x (%s .. %s); "
                    "AddMSLPort draws its metal patch over exactly ONE cell of "
                    "x from start[0], so any other span is a different line "
                    "length and a different reference plane"
                    % (label, n_x, _mm(start[0]).strip(), _mm(stop[0]).strip()))
            n_y = int(round((stop[1] - start[1]) / CELL))
            strip_w = p["y_hi"] - p["y_lo"]
            if n_y < 1 or (stop[1] - start[1]) != strip_w:
                raise SystemExit(
                    "PRE-FLIGHT FAILED: %s spans %d cells in y (%s .. %s = "
                    "%s), but the strip is %s wide; ports.py puts both the "
                    "launch patch and all five probes on this box's y span, so "
                    "a narrower port excites only part of the line and a wider "
                    "one adds metal off the strip"
                    % (label, n_y, _mm(start[1]).strip(), _mm(stop[1]).strip(),
                       _mm(stop[1] - start[1]).strip(), _mm(strip_w).strip()))
            if start[2] != p["z_strip"] or stop[2] != 0.0:
                raise SystemExit(
                    "PRE-FLIGHT FAILED: %s has z = %s .. %s, expected z_strip "
                    ".. 0.0 (%s .. %s); ports.py:348 overwrites stop[z] with "
                    "start[z] before adding the metal, so start[z] IS the strip "
                    "plane, stop[z] survives only as the far end of the U "
                    "probes, and any other z span measures a different voltage"
                    % (label, _num(start[2]), _num(stop[2]),
                       _mm(p["z_strip"]).strip(), _mm(0.0).strip()))
            if p["z_strip"] == 0.0:
                raise SystemExit(
                    "PRE-FLIGHT FAILED: %s has z_strip = %s; the metal plane is "
                    "start[z] alone, so z_strip == 0.0 would put the launch on "
                    "the GROUND plane -- the port would short the line instead "
                    "of exciting it" % (label, _num(p["z_strip"])))
            rows.append((label, idx,
                         "p_dir=%s, 1 cell in x, %d cells in y, z nodes "
                         "%d..%d (strip plane down to ground)"
                         % (p_dir, n_y, idx[4], idx[5])))
            continue
        axes = {"x": (idx[0], idx[1]), "y": (idx[2], idx[3]),
                "z": (idx[4], idx[5])}
        flat = [ax for ax in ("x", "y", "z") if axes[ax][0] == axes[ax][1]]
        # A port is normally a PLANE: exactly one flat axis.  --port2-api
        # port-zext deliberately gives the load one cell of z, so NO flat axis
        # (a volume) is accepted too; two flat axes is a line, not a port.
        if len(flat) > 1:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s has zero extent on %r; a port must be "
                "a plane element (one flat axis) or a volume (none, --port2-api "
                "port-zext)" % (label, flat))
        if flat and flat[0] == p_dir:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s is flat along its own p_dir=%r, so it "
                "occupies no cell to excite" % (label, p_dir))
        lo, hi = axes[p_dir]
        if hi <= lo:
            raise SystemExit(
                "PRE-FLIGHT FAILED: %s spans less than one cell along "
                "p_dir=%r (%d..%d)" % (label, p_dir, lo, hi))
        cross = [axes[ax][1] - axes[ax][0] for ax in ("x", "y", "z")
                 if ax != p_dir and ax not in flat]
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
@@PORT1@@
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
    stream.write(ECHO.replace("@@PORT1@@", _port1_echo_lines(p)))
    # Port 1's construction is printed too: which API built the launch, and --
    # for the two x-cell arms -- the physics deviation that comes with it.
    port1_report(p, priority=None if rep == "metal" else STRIP_PRIORITY,
                 stream=stream)
    for _line in strip_report_lines(p, rep):
        stream.write(_line + "\n")
    # Port 2 is the primitive whose construction the 2026-11-09 logs called
    # into question, so how it is built is printed HERE too: this echo is the
    # one thing reviewable on a machine with no openEMS installed.
    port2_report(p, priority=None if rep == "metal" else STRIP_PRIORITY,
                 stream=stream)
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
    # HOW it is built is --port1-api's job (PORT1_API, and the rationale quoted
    # above it).  add_port1()'s 'lumped' arm is this very call, written out
    # verbatim; port1_report() prints the API in force on the echo and
    # port1_box() moves the pre-flight with it.
    # strip_prop: the MSL arm adds its metal onto the STRIP's property, so
    # the launch and the strip share one material instead of two that CSXCAD
    # would have to arbitrate.  The lumped arms ignore the argument.
    add_port1(FDTD, p, priority=strip_priority, strip_prop=strip)

    # Port 2 -- THE LOAD.  A series element must resist the longitudinal
    # current, so it lies ALONG the strip: one cell in x, full width in y.
    # p_dir='x' is the load orientation; p_dir='y' would short the strip
    # edge-to-edge (E_y rails) and give a shunt, |Gamma| = 0.027 instead of
    # 0.345.  The reference builds 9 parallel E_x edges for exactly this
    # reason -- see doc section 2 for the arithmetic.
    #
    # HOW port 2 is built is --port2-api's job (PORT2_API, and the rationale
    # quoted from infra/openems/reference/ above it).  The 2026-11-09 run got
    # "Active cells: 0" from this primitive, so this file no longer assumes
    # one construction is the only one; port2_report() prints the API in
    # force, its rationale and the exact call, and add_port2() builds it, on
    # the echo and on every path that reaches here.
    add_port2(FDTD, csx, p, priority=strip_priority)

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
# PORT 1 EXTRACTION -- ports.py's OWN ARITHMETIC AND ITS OWN BIAS FLOOR
#
# The MSL arm does not write port_ut_1 / port_it_1.  It writes FIVE records of
# its own and takes its reference impedance from the FIELDS, so neither the
# lumped extraction nor a declared 50 ohm applies to it.  Everything below is
# ports.py's arithmetic restated, so the echo can print what that arithmetic
# will report -- including the error it carries -- before any solve exists.
# ---------------------------------------------------------------------------

# The mesh coordinate IS a length in metres: build_model() calls
# g.SetDeltaUnit(1.0) and hands SetLines() metre values, so a probe position
# expressed in mesh units needs no conversion.  The arithmetic below still
# multiplies by this, so a future SetDeltaUnit() change breaks in ONE place.
DELTA_UNIT = 1.0

# beta in the loaded line at F_REF, rad/m.  Used ONLY by the bias floor, to
# synthesise a KNOWN two-wave field at the exact probe planes.  beta*CELL =
# 0.09262132669165131 rad on this grid, so beta = that / 0.4e-3.  It is an
# artefact value, not a solver result.
BETA_ARTEFACT = 231.55331672912826

# The five records MSLPort writes: three voltage probes along the U path and
# TWO current probes (ports.py:382; ports.py:440 indexes I_delta[0]).  None of
# the lumped names exist in an MSL run, and none of these five exist in a
# lumped run.  Trap (14c).
PORT1_MSL_PROBES = ("port_1_utA", "port_1_utB", "port_1_utC",
                    "port_1_itA", "port_1_itB")
PORT1_LUMPED_PROBES = ("port_ut_1", "port_it_1")


def port1_probe_names(p: dict) -> tuple:
    """The port-1 records the arm in force makes the solver write.

    PORT1_API is read HERE, at call time, like everywhere else.  The four
    lumped arms all go through AddLumpedPort(1, ...), whose two probe boxes
    are port_ut_1 / port_it_1; mslport writes five different records.  Nothing
    downstream may assume the lumped pair exists -- trap (14c).
    """
    if PORT1_API == "mslport":
        return PORT1_MSL_PROBES
    return PORT1_LUMPED_PROBES


def msl_probe_planes(p: dict) -> dict:
    """The exact x planes MSLPort puts its five probes on, recomputed.

    RECONSTRUCTED from ports.py:355-390 (the bindings are not vendored in this
    workspace), so every field is named after the quantity it stands for and
    the echo prints all of them:

        measplane_pos = x_port + 0.5*cell        the measurement plane
        meas_pos_idx  = argmin(|xs - measplane_pos|)

    numpy's argmin returns the FIRST minimum, so a measplane that lands
    exactly between two nodes resolves DOWNWARD.  On this grid it does: 3.4 mm
    is halfway between the 3.2 mm and 3.6 mm nodes and node 8 wins.  The U
    probes are the node BELOW, the node itself and the node ABOVE; the I
    probes straddle the SAME centre by half a cell each (3.0 and 3.4 mm), so
    they do not sit on the U nodes and dHt is a HALF-CELL-offset difference.
    That offset is the whole reason the estimator carries a sinc() bias --
    see msl_bias_floor().

    Also returns the excitation sign.  ports.py:326 takes upside_down from
    stop[exc] - start[exc], so a box whose two z ends are EQUAL gives sign(0)
    = 0 and a SILENT zero excitation (trap 14a).  Refused here as well as in
    port1_box(), because this is the function that hands the value on.
    """
    xs = p["xs"]
    cell = port1_cell(p)
    meas = p["x_port"] + 0.5 * cell
    idx = 0
    best = abs(xs[0] - meas)
    for i in range(1, len(xs)):
        d = abs(xs[i] - meas)
        if d < best:                  # STRICT '<': a tie keeps the LOWER
            idx, best = i, d          # index, which is argmin's own rule
    lo, hi = idx - 1, idx + 1
    clamped = lo < 0 or hi > len(xs) - 1
    if clamped:
        lo = max(lo, 0)
        hi = min(hi, len(xs) - 1)
    centre = xs[idx]
    start, stop = port1_box(p)
    dz = stop[2] - start[2]
    upside_down = 0 if dz == 0.0 else (-1 if dz < 0.0 else 1)
    if upside_down == 0:
        raise SystemExit(
            "MSL PORT 1: start z == stop z == %.12g m, so upside_down = "
            "sign(0) = 0 and the excitation vector is scaled to zero: the "
            "launch would excite NOTHING, silently (trap 14a)" % (start[2],))
    return {
        "x_port": p["x_port"],
        "cell": cell,
        "measplane_pos": meas,
        "meas_pos_idx": idx,
        "prope_idx": [lo, idx, hi],
        "clamped": clamped,
        "wrap": False,                # no periodic wrap on this grid
        "u_pos": [xs[lo], centre, xs[hi]],
        "u_delta": [centre - xs[lo], xs[hi] - centre],
        "i_pos": [centre - 0.5 * cell, centre + 0.5 * cell],
        "i_delta": [cell],
        "direction": 1,               # prop_dir is +x
        "upside_down": upside_down,   # exc_dir: start z is ABOVE stop z
        "z_strip": p["z_strip"],
        "z_u_far": stop[2],
    }


# --- ports.py's MSL arithmetic, transcribed and then GUARDED ----------------
# ports.py divides by probe differences without a second thought, which is
# right for a solve that is expected to work.  The referee has to survive a
# solve that did not: every division below is transcribed in ports.py's own
# order (so the same rounding survives) and then guarded, storing None for
# that quantity -- and for everything downstream of it -- instead of raising.
# A degenerate probe set must come out as a DIAGNOSED None, never as a
# ZeroDivisionError traceback from inside the thing being reported on.


def _sinc(x: float) -> float:
    """sin(x)/x with the removable singularity at 0 filled in.  numpy-free."""
    if abs(x) < 1e-15:
        return 1.0
    return math.sin(x) / x


def _msl_arithmetic(u, i, delta_unit: float, u_delta, i_delta) -> dict:
    """ports.py's MSL S11 arithmetic for ONE frequency.

    `u` is the three probe voltages (ports.py's efield -> voltage), at the
    centre plane and one cell either side, `i` the two probe currents half a
    cell either side of the measurement plane; `u_delta` / `i_delta` are the
    spacings those probes sit on (msl_probe_planes) and `delta_unit` the
    length unit the DFT bins carry (DELTA_UNIT).

    Quantities and their ports.py sources:
        uf_tot  = u[1]                       total voltage at the plane
        if_tot  = 0.5 * (i[0] + i[1])        total current at the plane
        dEt     = (u[2] - u[0]) / sum(|u_delta|) / delta_unit     dE/dx
        dHt     = (i[1] - i[0]) / |i_delta[0]| / delta_unit       dH/dx
        Z_ref   = sqrt(Et dEt / (Ht dHt))
        beta    = sqrt(-dEt dHt / (Ht Et))
        uf_inc  = 0.5 * (uf_tot + if_tot * Z_ref)
        uf_ref  = uf_tot - uf_inc
        S11     = uf_ref / uf_inc

    beta is a PROPAGATING mode's phase constant and must be real and
    positive; a numerically imaginary residual on a real beta is folded onto
    the real axis (sign dropped -- beta is reported as a magnitude, its sign
    is the launch's prop_dir and is carried by planes["direction"]).  A
    genuinely complex beta is left alone, not clipped: on a bad solve the
    shape of the failure is the information.  Nothing here raises.
    """

    def _div(num, den):
        if num is None or den is None or den == 0:
            return None
        return num / den

    uf_tot = u[1]
    if_tot = 0.5 * (i[0] + i[1])
    Et = u[1]
    Ht = if_tot

    dEt = _div(u[2] - u[0], sum(abs(x) for x in u_delta) * delta_unit)
    dHt = _div(i[1] - i[0], abs(i_delta[0]) * delta_unit)

    Z_ref = None
    beta = None
    if dEt is not None and dHt is not None:
        z_arg = _div(Et * dEt, Ht * dHt)
        if z_arg is not None:
            Z_ref = cmath.sqrt(z_arg)
        b_arg = _div(-dEt * dHt, Ht * Et)
        if b_arg is not None:
            try:
                beta = cmath.sqrt(b_arg)
            except (ValueError, OverflowError):
                beta = None
            if beta is not None:
                tol = 1e-9 * max(abs(beta.real), 1e-300)
                if abs(beta.imag) <= tol:
                    beta = complex(abs(beta.real), 0.0)

    uf_inc = None
    if Z_ref is not None:
        uf_inc = 0.5 * (uf_tot + if_tot * Z_ref)
    uf_ref = None if uf_inc is None else uf_tot - uf_inc
    s11 = _div(uf_ref, uf_inc)

    return {
        "uf_tot": uf_tot,
        "if_tot": if_tot,
        "Et": Et,
        "Ht": Ht,
        "dEt": dEt,
        "dHt": dHt,
        "Z_ref": Z_ref,
        "beta": beta,
        "uf_inc": uf_inc,
        "uf_ref": uf_ref,
        "s11": s11,
    }


def extract_s11_msl(freqs, probes, planes, delta_unit=None) -> dict:
    """extract_s11's contract, per frequency, for the MSL port.

    `freqs` is a plain sequence of frequencies; `probes` maps every record
    name in PORT1_MSL_PROBES to a sequence of complex DFT values, one per
    frequency (read_port() + dft_at() produce them); `planes` is
    msl_probe_planes(p), which supplies u_delta / i_delta.

    The dict mirrors extract_s11 key for key -- f_hz, zref_ohm, U, I, s11 --
    with one entry per frequency instead of a scalar, plus the two
    quantities only the MSL arm has, Z_ref and beta, per frequency.  U is the
    centre probe voltage Et and I the mean probe current if_tot: exactly the
    pair the wave split is performed on.  A frequency whose arithmetic was
    undecidable (a zero denominator, see _msl_arithmetic) carries None in
    s11 / Z_ref / beta rather than dropping out of step with f_hz.
    """
    du = DELTA_UNIT if delta_unit is None else float(delta_unit)
    fs = [float(f) for f in freqs]

    series = {}
    for name in PORT1_MSL_PROBES:
        if name not in probes:
            raise KeyError(
                "extract_s11_msl: probe record %r missing (have: %s)"
                % (name, ", ".join(sorted(probes)) or "nothing"))
        series[name] = list(probes[name])
        if len(series[name]) != len(fs):
            raise ValueError(
                "extract_s11_msl: probe record %r carries %d values for %d "
                "frequencies" % (name, len(series[name]), len(fs)))

    u_delta = planes["u_delta"]
    i_delta = planes["i_delta"]

    rows = []
    for k in range(len(fs)):
        u = [series["port_1_utA"][k], series["port_1_utB"][k],
             series["port_1_utC"][k]]
        i = [series["port_1_itA"][k], series["port_1_itB"][k]]
        rows.append(_msl_arithmetic(u, i, du, u_delta, i_delta))

    return {
        "f_hz": fs,
        "zref_ohm": Z_REF,
        "delta_unit": du,
        "cell": planes.get("cell"),
        "U": [r["Et"] for r in rows],
        "I": [r["if_tot"] for r in rows],
        "s11": [r["s11"] for r in rows],
        "Z_ref": [r["Z_ref"] for r in rows],
        "beta": [r["beta"] for r in rows],
        "uf_tot": [r["uf_tot"] for r in rows],
        "if_tot": [r["if_tot"] for r in rows],
        "dEt": [r["dEt"] for r in rows],
        "dHt": [r["dHt"] for r in rows],
        "uf_inc": [r["uf_inc"] for r in rows],
        "uf_ref": [r["uf_ref"] for r in rows],
    }


def extract_s11_any(outdir: str, f: float = F_REF, zref: float = Z_REF) -> dict:
    """extract_s11 for whichever port-1 API is in force.  PORT1_API is read
    HERE, at call time, so main() can set it once.

    Same signature and same SCALAR contract as extract_s11, so every caller
    downstream stays API-agnostic: the MSL arm's per-frequency lists are
    unwrapped to the single bin asked for, and the two MSL-only quantities
    (Z_ref, beta) ride alongside the shared keys.  zref applies to the lumped
    arms only -- the MSL arm measures its own Z_ref and reports it.
    """
    if PORT1_API != "mslport":
        return extract_s11(outdir, f=f, zref=zref)

    probes = {}
    for name in PORT1_MSL_PROBES:
        t, x = read_port(outdir, name)
        probes[name] = [dft_at(t, x, f)]
    row = extract_s11_msl([f], probes, msl_probe_planes(plan()), DELTA_UNIT)

    out = dict(row)
    for key in ("f_hz", "U", "I", "s11", "Z_ref", "beta", "uf_tot", "if_tot",
                "dEt", "dHt", "uf_inc", "uf_ref"):
        out[key] = row[key][0]
    return out


def msl_bias_floor(p: dict) -> dict:
    """The referee's own accuracy floor, MEASURED with three asserted identities.

    _msl_arithmetic is ports.py's arithmetic.  Fed an ideal two-wave field
    sampled at the REAL probe planes, it must return three exact answers, and
    this function feeds it exactly that and then checks each one to 1e-12:

      (1) |Z_ref| / Z_line  ==  1
      (2) beta_est / beta   ==  sinc(theta)
      (3) S11               ==  ((1-c) + (1+c)G) / ((1+c) + (1-c)G)

    with theta = beta * cell / 2 and c = cos(theta).  Note what (2) and (3)
    say about the referee rather than about the device:

    (3) is NOT G.  ports.py measures the current at the plane as the
    HALF-CELL average 0.5*(i[0] + i[1]), half a cell either side of the
    voltage plane, so the wave it splits is low by sinc(theta) and a MATCHED
    load lands at (1-c)/(1+c) instead of at 0.  At the artefact's own beta
    and cell that is 5.4e-4, and no |S11| smaller than that can be read as
    anything but zero.  Same number from the other side: the current probes
    are displaced half a cell from the voltage plane, hence the sinc.

    Synthesis, x measured from the voltage centre plane (planes["u_pos"][1]):
        U(x) = exp(+j beta x) + G exp(-j beta x)
        I(x) = (exp(+j beta x) - G exp(-j beta x)) / Z_line
    sampled at the u_pos / i_pos that msl_probe_planes() returns -- the
    geometry the solve is actually probed at, not a convenient one.

    A failed identity raises SystemExit naming it and by how much: a
    self-check that cannot fail is decoration.
    """
    planes = msl_probe_planes(p)
    cell = planes["cell"]
    z_line = Z_REF
    beta = BETA_ARTEFACT
    beta_dx = beta * cell
    theta = 0.5 * beta_dx
    c = math.cos(theta)
    floor_gamma0 = (1.0 - c) / (1.0 + c)
    x0 = planes["u_pos"][1]
    u_x = list(planes["u_pos"])
    i_x = list(planes["i_pos"])
    sinc_theta = _sinc(theta)

    names = ("|Z_ref|/Z_line - 1", "beta_est/beta - sinc(theta)",
             "S11 - closed form")
    worst = dict((n, 0.0) for n in names)
    rows = []
    for gamma in (0.0, 0.1, 0.345475, 0.6):
        def _u_at(x):
            d = x - x0
            return (cmath.exp(1j * beta * d)
                    + gamma * cmath.exp(-1j * beta * d))

        def _i_at(x):
            d = x - x0
            return ((cmath.exp(1j * beta * d)
                     - gamma * cmath.exp(-1j * beta * d)) / z_line)

        row = _msl_arithmetic([_u_at(x) for x in u_x],
                              [_i_at(x) for x in i_x],
                              DELTA_UNIT, planes["u_delta"], planes["i_delta"])
        z_ref = row["Z_ref"]
        z_over = (None if z_ref is None
                  else abs(z_ref) / z_line)
        beta_est = None if row["beta"] is None else row["beta"].real / beta
        closed = (((1.0 - c) + (1.0 + c) * gamma)
                  / ((1.0 + c) + (1.0 - c) * gamma))
        s11 = row["s11"]
        rows.append({
            "gamma": gamma,
            "s11": s11,
            "s11_closed_form": closed,
            "s11_error_abs": None if s11 is None else abs(s11 - gamma),
            "s11_form_error": None if s11 is None else abs(s11 - closed),
            "z_ref": z_ref,
            "z_ref_over_z_line": z_over,
            "beta_est_over_beta": beta_est,
        })
        seen = {
            names[0]: (float("inf") if z_over is None
                       else abs(z_over - 1.0)),
            names[1]: (float("inf") if beta_est is None
                       else abs(beta_est - sinc_theta)),
            names[2]: float("inf") if s11 is None else abs(s11 - closed),
        }
        for n in names:
            if seen[n] > worst[n]:
                worst[n] = seen[n]

    for n in names:
        if not worst[n] <= 1e-12:
            raise SystemExit(
                "msl_bias_floor SELF-CHECK FAILED: identity %r is off by "
                "%.3e (tolerance 1e-12).  _msl_arithmetic no longer "
                "reproduces ports.py's arithmetic, so every S11 this script "
                "reports is unsupported." % (n, worst[n]))

    return {
        "beta_dx_rad": beta_dx,
        "theta_rad": theta,
        "c_cos_theta": c,
        "floor_gamma0": floor_gamma0,
        "rows": rows,
        "identities": worst,
        "cell_m": cell,
        "z_line_ohm": z_line,
        "beta_rad_per_m": beta,
    }


S11_JSON = "s11_extraction.json"      # written into outdir by report_s11()


def report_s11(outdir: str, f: float = F_REF) -> None:
    """Print and persist the S11 extraction for the arm(s) present on disk.

    extract_s11_any returns SCALARS on both arms -- the MSL branch unwraps its
    single-frequency lists -- so nothing here indexes into a list.  The bias
    floor is computed FIRST: if the referee's own arithmetic has drifted, the
    number this prints is not worth reading.

    Two arms are reported when both sets of records are on disk, because a
    referee holding both answers for the same run is worth more than one, and
    whichever matches PORT1_API is marked IN FORCE.
    """
    import json

    os.makedirs(outdir, exist_ok=True)
    p = plan()
    floor = msl_bias_floor(p)

    def _arm(arm):
        try:
            if arm == "mslport":
                probes = {}
                for name in PORT1_MSL_PROBES:
                    t, x = read_port(outdir, name)
                    probes[name] = [dft_at(t, x, f)]
                r = extract_s11_msl([f], probes, msl_probe_planes(p),
                                    DELTA_UNIT)
                return dict((k, v[0] if isinstance(v, list) and len(v) == 1
                             else v) for k, v in r.items())
            return extract_s11(outdir, f=f)
        except FileNotFoundError:
            return None

    rows = []
    for arm in ("mslport", "lumped"):
        r = _arm(arm)
        if r is not None:
            rows.append((arm, r))
    if not rows:
        raise SystemExit(
            "report_s11: %r holds neither the MSL probe records nor "
            "port_ut_1 / port_it_1 -- nothing to extract" % (outdir,))

    sys.stdout.write("S11 EXTRACTION  f = %.12g Hz  (zref = %g ohm)\n"
                     % (f, Z_REF))
    sys.stdout.write("  %-8s %-11s %-22s %-22s %s\n"
                     % ("arm", "|S11|", "Z_ref [ohm]", "beta [rad/m]",
                        "note"))
    for arm, r in rows:
        s11, z_ref, beta = r.get("s11"), r.get("Z_ref"), r.get("beta")
        sys.stdout.write(
            "  %-8s %-11s %-22s %-22s %s\n"
            % (arm,
               "None" if s11 is None else "%.6f" % abs(s11),
               "None" if z_ref is None else "%.4f%+.4fj" % (z_ref.real,
                                                           z_ref.imag),
               "None" if beta is None else "%.4f%+.4fj" % (beta.real,
                                                          beta.imag),
               "IN FORCE (--port1-api)" if arm == PORT1_API
               else "also on disk"))
    sys.stdout.write(
        "  bias floor          : |S11| is only trustworthy to ~%.1e at F_REF "
        "(G = 0) -- the\n"
        "                        referee's OWN accuracy.  WHY: Ht at the "
        "plane is the HALF-CELL\n"
        "                        average 0.5*(i[0] + i[1]), half a cell "
        "either side of the voltage\n"
        "                        plane, so the split wave is low by "
        "sinc(theta) and S11 lands at\n"
        "                        (1-c)/(1+c) = %.3e instead of 0.  Nothing "
        "smaller is a result.\n"
        % (floor["floor_gamma0"], floor["floor_gamma0"]))

    r = rows[0][1]
    for arm, rr in rows:
        if arm == PORT1_API:
            r = rr

    def _jsafe(v):
        if isinstance(v, complex):
            return [v.real, v.imag]
        if isinstance(v, dict):
            return dict((k, _jsafe(x)) for k, x in v.items())
        if isinstance(v, (list, tuple)):
            return [_jsafe(x) for x in v]
        return v

    payload = {
        "port1_api": PORT1_API,
        "f_hz": f,
        "s11_abs": None if r.get("s11") is None else abs(r["s11"]),
        "Z_ref": r.get("Z_ref"),
        "beta": r.get("beta"),
        "uf_inc": r.get("uf_inc"),
        "uf_ref": r.get("uf_ref"),
        "bias_floor": floor,
    }
    path = os.path.join(outdir, S11_JSON)
    with open(path, "w") as fh:
        json.dump(_jsafe(payload), fh, indent=2, sort_keys=True)
        fh.write("\n")
    sys.stdout.write("  written             : %s\n" % path)


def _port1_echo_lines(p: dict) -> str:
    """The text @@PORT1@@ is replaced with.  PORT1_API is read HERE.

    The four LUMPED arms reproduce, byte for byte, the three lines the token
    replaced: the z span they quote is the ground wall (z = 0, exact by
    construction, not a computed float) up to the substrate top, and _num /
    _nums are exact-float helpers, so the four-decimal millimetre text is
    formatted here rather than through them.

    The MSL arm builds a different thing and says so: AddMSLPort carries no
    impedance argument (it measures one), its metal sits on the START z --
    ports.py:348 overwrites stop[z] with start[z] -- and it writes five probe
    records instead of the lumped pair.
    """
    if PORT1_API == "mslport":
        start, stop = port1_box(p)
        return (
            "launch port 1         : MSLPORT -- FDTD.AddMSLPort, x = %.4f mm"
            " (col %d), excite = 1.0\n"
            "  span                : x = %.4f .. %.4f mm, y = %.4f .. %.4f mm,"
            " z = %.4f .. %.4f mm\n"
            "  metal plane         : z = START z = %.4f mm -- ports.py:348"
            " discards the stop z\n"
            "  probes              : %s\n"
            "  impedance           : measured from the probes (Z_ref),"
            " excite = 1.0\n"
            % (p["x_port"] * 1e3, int(round(p["x_port"] / CELL)),
               start[0] * 1e3, stop[0] * 1e3,
               start[1] * 1e3, stop[1] * 1e3,
               start[2] * 1e3, stop[2] * 1e3,
               start[2] * 1e3,
               ", ".join(PORT1_MSL_PROBES)))
    return (
        "launch port 1         : LUMPED, x = %.4f mm (col %d), ground -> strip\n"
        "  span                : z = 0 .. %.4f mm, y = %.4f .. %.4f mm\n"
        "  impedance           : %g ohm, excite = 1.0\n"
        % (p["x_port"] * 1e3, int(round(p["x_port"] / CELL)),
           p["h_sub"] * 1e3, p["y_lo"] * 1e3, p["y_hi"] * 1e3, R_PORT))



# ---------------------------------------------------------------------------
# SOLVER OUTPUT GUARD.  openEMS's C++ core writes its warnings to fd 1 and 2,
# not to Python's sys.stdout, so the two strings that say "I did not apply your
# geometry" never reach a print().  Capture the file descriptors, then insist
# on having seen a clean setup.  Trap (11).
# ---------------------------------------------------------------------------

_UNUSED_PAT = re.compile(r"Unused primitive")
_UNUSED_PROP_PAT = re.compile(
    r"Unused primitive \(type: ([^)]*)\) detected in property: (\S+?)!")

# --- headed blocks ----------------------------------------------------------
# openEMS heads each primitive's report with a "--- ... ---" line and prints
# the primitive's fields UNDERNEATH it.  "Active cells" therefore belongs to
# whichever heading precedes it, and reading it without knowing which block it
# sits in is how a zero-active LOAD gets mistaken for the strip's verdict --
# the 2026-11-09 run printed both blocks in one log.
_SECTION_HEADERS = {
    "pec": ("--- PEC ---", "PEC:"),
    "load": ("--- Series/Parallel Lumped RLC load ---", "Lumped RLC load:"),
}
_HEADING_PAT = re.compile(r"^\s*---")
# Which route answered the PEC-edge question, so the caller can PRINT it
# instead of leaving the reader to guess how the number was found.
_PEC_EDGES_ROUTE = {"how": None}
# What a lumped-element heading may say.  We do NOT know what openEMS prints
# for a plain csx.AddLumpedElement() -- that is what --port2-api element
# builds, and it is not the '--- Series/Parallel Lumped RLC load ---' block a
# lumped PORT prints.  So match on the words that survive a rename instead of
# pinning the one spelling that happened to appear in the 2026-11-09 logs.
_LOAD_WORDS = ("lumped rlc", "lumped element", "lumped load", "rlc load")


def _find_int(text, label: str):
    """The integer after `label` in `text`, or None.  TABs included.

    openEMS separates a label from its colon with a TAB --
    "Number of PEC edges<TAB>: 1119" -- so a space-only pattern matched
    nothing in a real log.  `\\s*` is what makes the space-only logs AND the
    TAB logs match; re.escape() keeps labels with regex punctuation (such as
    "Voltage excitation(s)") literal.

    `text` is a whole log or the lines of one block (_section()), so the same
    reader serves both and a caller can scope a field to the block that owns
    it.  Labels in this file's logs: "Number of PEC edges", "Active cells";
    "Voltage excitation(s)", "Number of timesteps" and "in x/y/z direction"
    are labelled the same way and are read with the same call.
    """
    lines = text.splitlines() if isinstance(text, str) else list(text)
    pat = re.compile(r"%s\s*:\s*(-?\d+)" % re.escape(label))
    for line in lines:
        hit = pat.search(line)
        if hit:
            return int(hit.group(1))
    return None


def _section_name(line: str):
    """Which headed block `line` opens, or None.  Both spellings, any case.

    Case-insensitive on purpose: a heading is a label, not a contract.  If a
    renamed or re-cased heading failed to match here the block would simply
    vanish from the parse -- and a vanished load block used to read as a dead
    load, which is the 80ce5cb failure in miniature.  Every miss is now
    reported by load_verdict() as LOAD UNVERIFIED, never as a verdict.
    """
    stripped = line.strip()
    low = stripped.lower()
    for name, headers in _SECTION_HEADERS.items():
        for head in headers:
            if low.startswith(head.lower()):
                return name
    if _HEADING_PAT.match(line):
        for word in _LOAD_WORDS:
            if word in low:
                return "load"
    return None


def _section(text, name: str) -> list:
    """The lines of the block `name` heads, heading included.  [] = no block.

    An EMPTY list is a FINDING, not a zero: every caller must say the block
    could not be located instead of reporting a number taken from somewhere
    else in the log.  The block runs from its heading to the next heading.
    """
    lines = text.splitlines() if isinstance(text, str) else list(text)
    out = []
    for line in lines:
        if out:
            if _section_name(line) is not None:
                break
            out.append(line)
        elif _section_name(line) == name:
            out.append(line)
    return out


def _pec_edges(text):
    """"Number of PEC edges", block-scoped when possible, else whole-log.

    The block scope is an OPTIMISATION, not a requirement.  We do not know the
    real header spelling in the operator's log -- "--- PEC ---" was inferred --
    so demanding the block made an unlocatable header look like a missing
    line, and on a solve log that is exit 4: "the strip cannot be shown to
    have attached" said about a log that plainly contains the count.  That is
    exactly the 80ce5cb shape, a parse demand masquerading as a verdict.

    The label is unique to the PEC summary, so the whole-log search is safe;
    it is only ever used when the block is absent or does not carry the line.
    _PEC_EDGES_ROUTE records which route answered so the caller can say so.
    """
    block = _section(text, "pec")
    if block:
        seen = _find_int(block, "Number of PEC edges")
        if seen is not None:
            _PEC_EDGES_ROUTE["how"] = "the located PEC block"
            return seen
        reason = "the located PEC block carried no 'Number of PEC edges' line"
    else:
        reason = "no '--- PEC ---' block located"
    seen = _find_int(text, "Number of PEC edges")
    if seen is not None:
        _PEC_EDGES_ROUTE["how"] = ("'Number of PEC edges' anywhere in the log "
                                   "(%s)" % reason)
        return seen
    _PEC_EDGES_ROUTE["how"] = None
    return None


def _active_cell_lines(text: str) -> list:
    """[(N, verbatim line)] for every Active-cells line inside the LOAD block."""
    out = []
    for line in _section(text, "load"):
        count = _find_int([line], "Active cells")
        if count is not None:
            out.append((count, line.rstrip()))
    return out


def classify_unused(text: str) -> list:
    """[(kind, VERBATIM line)] for every Unused-primitive line.  Nothing dropped.

    kind is "strip" when the dropped property is the strip, "load" when it is
    port 2 / a lumped element / anything reported under the load heading, and
    "other" otherwise.  A dropped primitive is only evidence about the strip or
    about the load if it IS the strip or the load, and which one it is cannot
    be decided by the warning text alone -- the property name and the block it
    sits in decide it.
    """
    lines = text.splitlines() if isinstance(text, str) else list(text)
    out = []
    block = None
    for line in lines:
        head = _section_name(line)
        if head is not None:
            block = head
            continue
        if _HEADING_PAT.match(line):
            # An UNRECOGNISED heading ends the previous block: carrying the old
            # block name across it would attribute the next warning to a block
            # it is not in.  None here is honest, and lands in "unattributed".
            block = None
            continue
        if not _UNUSED_PAT.search(line):
            continue
        hit = _UNUSED_PROP_PAT.search(line)
        prop = (hit.group(2) if hit else "").lower()
        # Attribution ladder.  (i) a parseable property name decides; (ii) with
        # no name, the enclosing headed block decides; (iii) with neither the
        # kind is "unattributed" -- NOT "other".  The ladder exists because an
        # unrecognised REAL strip warning used to land in "other", which is
        # only a note under scope="strip", so a broken strip could resolve
        # while its own warning was demoted to silence.  "other" must mean
        # "attributed to something that is neither", not "could not tell".
        if prop.startswith("strip"):
            kind = "strip"
        elif (prop.startswith("port_2") or prop.startswith("port2")
              or "lumped" in prop):
            kind = "load"
        elif prop:
            kind = "other"
        elif block == "pec":
            kind = "strip"
        elif block == "load":
            kind = "load"
        else:
            kind = "unattributed"
        out.append((kind, line.rstrip()))
    return out


def _stray_active_cells(text: str) -> list:
    """Every 'Active cells' line ANYWHERE in the log, verbatim, with neighbours.

    Used only when no lumped-element block could be located.  A renamed or
    relocated 'Active cells: 0' must still reach the reader: the block failing
    to parse is OUR ignorance, and it must not be able to make a real
    zero-active warning invisible.
    """
    lines = text.splitlines() if isinstance(text, str) else list(text)
    out = []
    for i, line in enumerate(lines):
        if _find_int([line], "Active cells") is None:
            continue
        out.append("LOAD: stray 'Active cells' line at log line %d: %r"
                   % (i + 1, line.rstrip()))
        for j in range(max(0, i - 2), min(len(lines), i + 3)):
            if j == i:
                continue
            out.append("LOAD:     neighbour line %d: %r"
                       % (j + 1, lines[j].rstrip()))
    return out


def load_verdict(text: str, p: dict) -> tuple:
    """(ok, lines, fatal) for the LOAD alone.  Every line starts with "LOAD:".

    The load is its own verdict because it is judged independently of the
    strip: the 2026-11-09 run printed "--- Series/Parallel Lumped RLC load
    ---" followed by "Active cells: 0" in the same log as the strip's
    primitives, and that reading speaks about the load's construction only
    (trap (13)), so a strip verdict must not be able to answer for the load.

    WHAT 'Active cells: 0' MEANS DEPENDS ON --port2-api (trap (13)).  A
    zero-thickness lumped port is a surface impedance: it owns no cell volume,
    so 0 is the EXPECTED reading on the arms that build one, and it is NOT a
    failure there.  Only 'element' -- the one arm that gives the element cell
    volume -- must show cells > 0.  On EVERY arm an unused-primitive line that
    names the port property is a real failure, and a zero-thickness reading is
    accepted only in the ABSENCE of one.

    `fatal` is True ONLY for a real signal: a LOCATED block whose reading
    fails under the arm in force, or an unused-primitive line naming the load.
    A block we cannot locate, and a located block with no Active-cells line,
    are PARSE GAPS -- ok=False, fatal=False, so the caller reports them as
    notes on both phases.  A parse gap must never be promoted to a verdict;
    that is the 80ce5cb failure.
    """
    lines = []
    if not _section(text, "load"):
        lines.append("LOAD UNVERIFIED: could not locate a lumped-element "
                     "block in this log, so 'Active cells' for the load "
                     "could not be read -- this is NOT a report that the "
                     "load is fine")
        stray = _stray_active_cells(text)
        if stray:
            lines.extend(stray)
        else:
            lines.append("LOAD: no 'Active cells' line anywhere in this log "
                         "either, so it says nothing about the load")
        return False, lines, False
    found = _active_cell_lines(text)
    if not found:
        lines.append("LOAD: the load block carries no 'Active cells' line -- "
                     "this log does not say how many cells the load activated")
        return False, lines, False
    expect = _expected_active_cells(p)[-1][1]
    cells_required = PORT2_API in PORT2_CELLS_REQUIRED_ARMS
    zero_thick = PORT2_API in PORT2_ZERO_THICKNESS_ARMS
    ok = True
    fatal = False
    # TWO streams, and they must never be mixed.  `fails` says why the block is
    # REJECTED; `readings` is what the block says when it is not.  The caller
    # routes the returned list into `problems` whenever the block is fatal, so a
    # reading travelling in it prints an "EXPECTED" sentence underneath MODEL
    # NOT APPLIED, which reads as a reason to reject the run.  A reading is
    # emitted only when the block is ACCEPTED.
    fails = []
    readings = []
    for count, raw in found:
        if count == 0 and not cells_required:
            # Trap (13).  A zero-thickness port activates no cell volume by
            # construction, so a 0 here is the shape of a WORKING load.
            if zero_thick:
                readings.append("LOAD: Active cells 0 -- EXPECTED for a "
                                "zero-thickness lumped port (a surface "
                                "impedance activates no cell volume); the "
                                "load is present unless an unused-primitive "
                                "line names it: %r" % raw.strip())
            else:
                # port-zext is NOT zero-thickness, so the sentence above would
                # be false; it is still not failed on (it is an experiment),
                # but nothing is asserted about the number either way.
                readings.append("LOAD: Active cells 0 -- NOT a failure for "
                                "--port2-api %s, which is not zero-thickness: "
                                "that arm gives the element one cell of z "
                                "extent, so no assertion is made about this "
                                "reading: %r" % (PORT2_API, raw.strip()))
            continue
        if count == 0:
            ok = False
            fatal = True
            fails.append("LOAD: Active cells 0 (expected %d) -- the load "
                         "activated NO cell, so port_ut_2/port_it_2 describe "
                         "nothing: %r" % (expect, raw.strip()))
            continue
        if cells_required:
            readings.append("LOAD: Active cells %d (expected %d): %r"
                            % (count, expect, raw.strip()))
        else:
            readings.append("LOAD: Active cells %d (no count is asserted "
                            "for --port2-api %s): %r"
                            % (count, PORT2_API, raw.strip()))
    # The zero-thickness acceptance above is conditioned on the load being
    # PRESENT, and the one line that proves it is NOT is an unused-primitive
    # line naming the port property.  That is fatal on every arm (trap (13)).
    for _kind, unused_line in classify_unused(text):
        if _kind != "load":
            continue
        ok = False
        fatal = True
        fails.append("LOAD: an unused-primitive line names the load, so the "
                     "port is NOT in the model: %s" % unused_line)
    lines.extend(fails)
    if not fails:
        lines.extend(readings)
    return ok, lines, fatal
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
    """[(port label, cells it should activate)] -- 8 cells each by THIS geometry.

    A port is a plane element: the cells it activates are the product of its
    spans on the axes that are neither its p_dir nor the one axis it is flat
    on.  Both ports span the 8-cell strip width in y.

    WHAT IS DONE WITH THE NUMBER IS --port2-api's BUSINESS, and for the load it
    is a contract on ONE arm (trap (13)).  An AddLumpedElement is a VOLUME
    impedance: it should occupy a cell, so a count of 0 there means the element
    was not attached and the block is rejected.  A lumped PORT is a
    zero-thickness SURFACE impedance: it owns no cell volume and legitimately
    activates none, so 0 is EXPECTED on those arms and this number is a
    contract against nothing.  This function only computes the geometry;
    load_verdict() decides whether the number may be acted on.
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
                        rep: str = "metal", phase: str = "solve",
                        scope: str = "all") -> tuple:
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

    `scope` says WHICH verdict this call may draw: "all" (the strip AND the
    load), "strip" or "load".  resolve_strip() audits with scope="strip",
    because a strip representation has to be judgeable on its own -- the
    2026-11-09 run printed the strip's primitives beside a load block reading
    "Active cells: 0", which on a zero-thickness arm is EXPECTED (trap (13))
    -- while the load's "LOAD: ..." lines are still emitted, as NOTES, so a
    resolution can never hide it.  A load that fails is exit 4 only where the
    call owns the load AND the log is a real solve.
    """
    if phase not in ("setup-probe", "solve"):
        raise ValueError("phase must be 'setup-probe' or 'solve', not %r"
                         % (phase,))
    if scope not in ("all", "strip", "load"):
        raise ValueError("scope must be 'all', 'strip' or 'load', not %r"
                         % (scope,))
    problems = []
    notes = []
    want_strip = scope in ("all", "strip")
    want_load = scope in ("all", "load")

    # EVERY unused-primitive line, VERBATIM, classified, and never folded into
    # one verdict: a line about the load is not evidence against the strip, or
    # the other way round.  "other" is evidence against neither, so it is a
    # problem only when this call speaks for the whole model.
    for kind, line in classify_unused(text):
        if kind in ("strip", "load"):
            about = ("a primitive CSXCAD did not apply (about the %s): %r"
                     % (kind, line))
        elif kind == "other":
            about = ("a primitive CSXCAD did not apply (about the rest of "
                     "the model): %r" % line)
        else:
            about = ("a primitive CSXCAD did not apply (UNATTRIBUTED -- no "
                     "parseable property name and no recognisable enclosing "
                     "block): %r" % line)
        # "other" and "unattributed" are PROBLEMS only where this call speaks
        # for the whole model.  Elsewhere they are printed, verbatim, as notes
        # -- demoted in the verdict but never dropped from the output, because
        # an unattributed warning might BE the strip and silence is not an
        # option.
        if ((kind == "strip" and want_strip)
                or (kind == "load" and want_load)
                or (kind in ("other", "unattributed") and scope == "all")):
            problems.append(about)
        else:
            notes.append("NOT evidence about the %s verdict, reported anyway: "
                         "%s" % (scope, about))

    if want_strip:
        expect_faces = _expected_pec_faces(p, rep)
        seen = _pec_edges(text)
        if seen is None:
            if phase == "solve":
                problems.append(
                    "expected line not found: no 'Number of PEC edges' line "
                    "ANYWHERE in the captured %s log (neither in a located "
                    "PEC block nor in the whole log), so the strip cannot be "
                    "shown to have attached" % where)
            else:
                notes.append(
                    "no 'Number of PEC edges' line in this setup-only log -- "
                    "openEMS may print it only during a full run, so this "
                    "probe judges attachment from the block-scoped "
                    "Unused-primitive signal only")
        elif seen < PEC_EDGES_FLOOR:
            problems.append(
                "the strip did not attach: %d PEC edges, below the floor of "
                "%d (representation %r; the sheets should contribute %d "
                "faces, and a dropped strip leaves only the port-1 plane)"
                % (seen, PEC_EDGES_FLOOR, rep, expect_faces))
        else:
            notes.append("%d PEC edges (floor %d; the sheets should "
                         "contribute %d faces)"
                         % (seen, PEC_EDGES_FLOOR, expect_faces))
            notes.append("PEC edges read from: %s" % _PEC_EDGES_ROUTE["how"])

    # The load is ALWAYS reported, in its own words.  The lines are notes
    # unless this call owns the load AND the log is a real solve: a missing
    # load block in a setup-only probe is a NOTE, never a permanent exit 4.
    load_ok, load_lines, load_fatal = load_verdict(text, p)
    if want_load and phase == "solve" and load_fatal:
        problems.extend(load_lines)
    else:
        notes.extend(load_lines)
    return problems, notes


def guard_solver_output(text: str, where: str, p: dict,
                        rep: str = "metal", phase: str = "solve",
                        scope: str = "all") -> None:
    """Exit 4 if openEMS reported geometry it did not apply.  Trap (11).

    `phase` and `scope` are forwarded to audit_solver_output(): the dry-run
    call site is a setup-only probe, the solve call site is a solve, and both
    speak for the whole model (scope="all").

    NOTES are printed here as `guard: ...` lines -- that is where the load's
    "LOAD: ..." lines surface on the solve path.
    """
    problems, notes = audit_solver_output(text, where, p, rep, phase=phase,
                                          scope=scope)
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


def accept_note(capture: str, scope: str, p: dict,
                rep: str = "metal") -> str:
    """What an ACCEPTED probe ESTABLISHED, and what it did NOT verify.

    A success line may assert a negative ONLY about the region of the log the
    verdict was drawn from.  The operator's 2026-11-12 run printed an
    "ACCEPTED --" note that flatly denied both signals (no unused-primitive
    warning, no zero-active load) two lines under a log that said the
    port_2_resist box was unused AND printed "LOAD: Active cells 0 (expected
    8)": the note was the STRIP's verdict, repeated as though it spoke for the
    whole model.  A note may not outrun its scope, so this one names the
    scope, says what was searched, and lists what it left unjudged -- with the
    findings this log DOES carry about those parts, because "resolved" must
    never read as "the rest is fine too".

    `scope` is the scope audit_solver_output() drew its verdict at: "all"
    (the strip AND the load AND the rest of the model), "strip" or "load".
    Only "all" searched the whole log, so only "all" may print a negative
    about the whole log -- and it says "scope=all" out loud.
    """
    if scope not in ("all", "strip", "load"):
        raise ValueError("scope must be 'all', 'strip' or 'load', not %r"
                         % (scope,))
    if _empty_capture(capture):
        # A HARNESS fault is not a model verdict: nothing was read, so nothing
        # was established, and no "nothing was reported" here is a finding.
        return ("NOTHING WAS ESTABLISHED (scope=%s): the captured log was "
                "EMPTY (%d bytes), so every 'nothing was reported' above is "
                "a statement about an empty file, not about the model"
                % (scope, len(capture.encode("utf-8"))))
    want_strip = scope in ("all", "strip")
    want_load = scope in ("all", "load")
    owned = {"all": ("strip", "load", "other", "unattributed"),
             "strip": ("strip",),
             "load": ("load",)}[scope]
    established = []
    not_verified = []
    unused = classify_unused(capture)

    # --- the scope's own Unused-primitive signal -----------------------
    in_scope = [line for kind, line in unused if kind in owned]
    if in_scope:
        established.append("an unused-primitive line this scope cannot "
                           "dismiss: %s"
                           % "; ".join(repr(line) for line in in_scope))
    elif scope == "all":
        established.append("no 'Unused primitive' line ANYWHERE in this log "
                           "(strip, load and the rest of the model searched)")
    else:
        # Deliberately NOT a flat "no unused-primitive warning": this scope
        # searched the %s's own line only, and says exactly that.
        established.append("no unused-primitive line attributed to the %s"
                           % scope.upper())

    # --- PEC edges: the strip's attachment number ----------------------
    pec = _pec_edges(capture)
    if want_strip:
        faces = _expected_pec_faces(p, rep)
        if pec is None:
            established.append(
                "no 'Number of PEC edges' line anywhere in this log (a "
                "setup-only log may carry none), so attachment rests on the "
                "Unused-primitive signal alone; the sheets should contribute "
                "%d faces" % faces)
        else:
            established.append("%d PEC edges read (floor %d; the sheets "
                               "should contribute %d faces)"
                               % (pec, PEC_EDGES_FLOOR, faces))

    # --- Active cells: the load's number -------------------------------
    load_ok, load_lines, load_fatal = load_verdict(capture, p)
    counts = [count for count, _raw in _active_cell_lines(capture)]
    expect = _expected_active_cells(p)[-1][1]
    if not want_load:
        # Outside this scope.  A strip-scoped probe never judges the load, and
        # a resolution must not be able to read as "the load is fine too":
        # whatever the log says about the load goes into the note verbatim.
        if load_ok:
            not_verified.append("the LOAD -- its 'Active cells' %s was read, "
                                "but no verdict about the load is drawn here"
                                % ", ".join(str(count) for count in counts))
        elif load_fatal:
            # Not a parse gap: this log SAYS the load activated nothing.  Lead
            # with the token, then the verbatim line, so it cannot be skimmed
            # past as one more unjudged item.
            not_verified.append("the LOAD NOT ACTIVATED (see the LOAD: line "
                                "above): %s" % load_lines[0])
        else:
            not_verified.append("the LOAD -- %s" % load_lines[0])
    elif load_ok and PORT2_API not in PORT2_CELLS_REQUIRED_ARMS:
        # Trap (13): on these arms a count is evidence in NEITHER direction --
        # it is the EXPECTED 0 (a zero-thickness surface impedance owns no
        # cell volume), or a number nothing asserts.  So the load's ACTIVATION
        # is NOT established here; only its PRESENCE is, and only through the
        # unused-primitive signal above.  Claiming more would be the
        # 2026-11-12 failure in reverse: a note outrunning its evidence.
        established.append("the LOAD's port is PRESENT -- established ONLY by "
                           "the unused-primitive signal above, never by a "
                           "cell count (--port2-api %s asserts no 'Active "
                           "cells' number here: %s; see trap (13))"
                           % (PORT2_API,
                              ", ".join(str(count) for count in counts)))
        not_verified.append("the LOAD's ACTIVATION -- 'Active cells' cannot "
                            "show it on this arm; only port_ut_2/port_it_2's "
                            "V/I ratio on a full solve does, and this note "
                            "draws no such reading")
    elif load_ok:
        established.append("the LOAD's 'Active cells' %s (expected %d)"
                           % (", ".join(str(count) for count in counts),
                              expect))
    elif load_fatal:
        # In scope and it failed for real: the same token, same verbatim line.
        not_verified.append("the LOAD NOT ACTIVATED (see the LOAD: line "
                            "above): %s" % load_lines[0])
    else:
        not_verified.append("the LOAD -- %s" % load_lines[0])

    # --- the strip when the scope does not own it ----------------------
    if not want_strip:
        if pec is None:
            not_verified.append(
                "the STRIP -- no 'Number of PEC edges' line in this log, so "
                "strip attachment was not measured at all")
        else:
            not_verified.append("the STRIP -- %d PEC edges read, but no "
                                "verdict about the strip is drawn here" % pec)

    # --- every finding this log makes OUTSIDE the scope, never dropped --
    for kind, line in unused:
        if kind not in owned:
            not_verified.append("a primitive CSXCAD did not apply (%s), "
                                "outside this scope: %r" % (kind, line))
    if not not_verified:
        not_verified.append("nothing else in THIS log -- every primitive it "
                            "mentions was searched; a setup-only log takes "
                            "no timestep, so this is not a solve result")
    if scope == "all":
        closing = ("scope=all, printed only because the WHOLE log was "
                   "searched for every one of these signals")
    else:
        closing = ("scope=%s, so this speaks for the %s ONLY -- the items "
                   "above were NOT verified here, and a full solve is the "
                   "only phase that speaks for the whole model"
                   % (scope, scope.upper()))
    return ("ACCEPTED (scope=%s): %s; NOT verified by this probe: %s; %s"
            % (scope, "; ".join(established), "; ".join(not_verified),
               closing))


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
    # ONE source of truth for the scope: the verdict is drawn at this scope, so
    # accept_note() may speak for this scope and no other.  Passing a literal
    # twice is how the audit and the note drifted apart in the first place.
    scope = "strip"
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
        problems, notes = audit_solver_output(
            text, "setup-only strip candidate %r" % rep, p, rep,
            phase="setup-probe", scope=scope)
        # The strip verdict is drawn below; the load's lines are printed
        # regardless, because a resolution must never hide a dead load.
        for note in notes:
            print("candidate %s: %s" % (rep, note))
        if problems:
            print("candidate %s: REJECTED -- %s" % (rep, problems[0]))
            for extra in problems[1:]:
                print("    also: %s" % extra)
            continue
        print("candidate %s: %s" % (rep, accept_note(text, scope, p, rep)))
        winner, winner_text = rep, text
    if winner is None:
        announce_resolution("STRIP REPRESENTATION RESOLVED: none -- every "
                            "candidate was rejected by the setup probe",
                            stream=sys.stderr)
        raise SystemExit(4)
    announce_resolution("STRIP REPRESENTATION RESOLVED: %s" % winner)
    # The resolution is a STRIP verdict; the note says so and names what it
    # did not verify, so "resolved" cannot read as "the whole model is fine".
    print("  %s" % accept_note(winner_text, scope, p, winner))
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
    # Same single source of truth as resolve_strip(): audit scope == note scope.
    scope = "strip"
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
        phase="setup-probe", scope=scope)
    for note in notes:
        print("%s: %s" % (tag, note))
    if problems:
        print("%s: REJECTED -- %s" % (tag, problems[0]))
        for extra in problems[1:]:
            print("    also: %s" % extra)
        return 4
    print("%s: %s" % (tag, accept_note(text, scope, p, rep)))
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
        # Same single source of truth as the candidate probes: the audit and
        # the note both speak for the WHOLE model, so neither is widened here.
        scope = "all"
        guard_solver_output(text, "setup-only", p, rep,
                            phase="setup-probe", scope=scope)
        if _empty_capture(text):
            # An EMPTY capture cannot show that a primitive was accepted: an
            # "accepted every primitive" line under it would be a claim about a
            # file with nothing in it, which is exactly the overreach this note
            # exists to stop.  The build DID happen, so say only that.
            print("SETUP-ONLY PROBE: the model was BUILT and openEMS.Run was "
                  "not called; %r was not touched." % outdir)
            print("NOTHING WAS VERIFIED -- the captured log was EMPTY (%d "
                  "bytes), so no primitive was checked."
                  % len(text.encode("utf-8")))
        else:
            print("SETUP-ONLY PROBE OK: openEMS accepted every primitive; no "
                  "timestep was taken and %r was not touched." % outdir)
            # guard_solver_output() above spoke for the WHOLE model
            # (scope="all"), so the note is allowed to, and has to say so.
            print(accept_note(text, scope, p, rep))
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

    # Port 1's record names come from the arm in force (trap 14c): five MSL
    # records, or the lumped pair -- never both.  Port 2's pair is unchanged.
    port1_names = port1_probe_names(p)
    missing = [n for n in port1_names + ("port_ut_2", "port_it_2")
               if not os.path.exists(os.path.join(outdir, n))]
    if missing:
        print("SOLVE FAILED: no port records for %s in %s"
              % (", ".join(missing), outdir), file=sys.stderr)
        return 3

    print("SOLVE OK: port records in %s" % outdir)
    print("Next: DFT port_ut_1/port_it_1 at %r Hz, then" % F_REF)
    print("      S11 = (U/Zref - I) / (U/Zref + I), Zref = 50 ohm.")
    print("      |S11| is plane-invariant; phase needs de-embedding to 20.4 mm.")

    # The extraction this file exists for, done while the records are still on
    # disk.  Guarded: a partial record set is a verdict about the run, not a
    # traceback out of the referee -- the solve itself already succeeded.
    try:
        report_s11(outdir)
    except (SystemExit, KeyError, FileNotFoundError, OSError, ValueError) as exc:
        print("S11 EXTRACTION UNAVAILABLE: %s" % (exc,), file=sys.stderr)
        print("  the solve succeeded and its records are in %r; only the "
              "extraction could not be completed." % outdir, file=sys.stderr)
    return 0


def main(argv=None) -> int:
    # FIRST statement: add_argument() READS PORT1_API / PORT2_API for its
    # defaults, and a `global` declared after those reads is a SyntaxError.
    global PORT1_API, PORT2_API
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
    ap.add_argument("--port1-api", choices=PORT1_API_CHOICES,
                    default=PORT1_API,
                    help="how port 1, the 50 ohm LAUNCH, is built (default: "
                         "%s). The chosen API, its rationale and the exact "
                         "call are printed by the geometry echo; see the "
                         "PORT 1 block above for what each one builds."
                         % PORT1_API)
    ap.add_argument("--port2-api", choices=PORT2_API_CHOICES,
                    default=PORT2_API,
                    help="how port 2, the 50 ohm LOAD, is built (default: %s). "
                         "The chosen API, its rationale and the exact call are "
                         "printed by the geometry echo; see the PORT 2 block "
                         "above for what each one builds." % PORT2_API)
    args = ap.parse_args(argv)

    # ONE place, before the echo and before any model is built, so the echo,
    # the setup probe, the dry run and the solve all build the same primitive.
    PORT1_API = args.port1_api
    PORT2_API = args.port2_api

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
