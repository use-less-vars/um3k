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

    # 2. build the CSX model and stop before Run() (needs the bindings).
    python3 build_A_referee.py --dry-run --with-bindings

    # 3. real solve -- NOT runnable from the authoring environment.
    docker build -t openems:bookworm docker/openems
    mkdir -p evidence/referee
    docker run --rm -v "$PWD/evidence/referee:/work/out" openems:bookworm \
        python3 /work/build_A_referee.py --out /work/out

    Exit 0  = whatever was asked for completed.
    Exit 3  = solve ran but produced no port records (model is wrong).

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
    material:  air = csx.AddMaterial("air", epsilon=1); air.AddBox(...).
(6) AddLumpedPort()/AddMSLPort() are SOLVER methods (FDTD.*), not csx.*.
    start/stop must lie on grid lines and may differ ONLY along p_dir.
(7) There is no SetSolverType() and no SetMaxThreads().  Thread count is a
    Run() kwarg:  Run(path, cleanup=, setup_only=, verbose=, numThreads=).
    SetTimeStepMethod() does exist.  Run() takes no timestep-count kwarg.
(8) PML_8 eats 8 CELLS per side, PML_3 eats 3.  Budget the grid for it.
(9) Files written from inside a bind mount come out root-owned.
(10) SetEndCriteria() takes a LINEAR ratio, and the solver prints 10*log10
    of it.  Default 1e-6 == -60 dB.  SetNumberOfTimeSteps() default is 1e9.

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
import math
import os
import sys

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


def echo(p: dict, stream=sys.stdout) -> None:
    """Print the geometry echo.  Pure arithmetic -- needs no openEMS."""
    stream.write(ECHO)
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


def build_model(p: dict):
    """Build the CSX model and the solver.  Does NOT call Run()."""
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
    air = csx.AddMaterial("air", epsilon=1.0)
    air.AddBox(start=[0.0, 0.0, 0.0],
               stop=[p["x_max"], p["y_max"], p["z_max"]])

    sub = csx.AddMaterial("substrate", epsilon=EPS_R)
    sub.AddBox(start=[0.0, 0.0, 0.0],
               stop=[p["x_max"], p["y_max"], p["h_sub"]])

    metal = csx.AddMetal("strip")
    # Sheet A: feed side, port plane -> load cell.
    metal.AddBox(start=[p["x_port"], p["y_lo"], p["z_strip"]],
                 stop=[p["x_load"], p["y_hi"], p["z_strip"]])
    # Sheet B: stub side, after the load cell, runs into xmax.
    # The strip is genuinely CUT: an empty cell carries the termination.
    metal.AddBox(start=[p["x_gap_hi"], p["y_lo"], p["z_strip"]],
                 stop=[p["x_max"], p["y_hi"], p["z_strip"]])

    # trap (6): ports are SOLVER methods; start/stop differ only along p_dir.
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
    FDTD.AddLumpedPort(
        2, R_TERM,
        start=[p["x_load"], p["y_lo"], p["z_strip"]],
        stop=[p["x_gap_hi"], p["y_hi"], p["z_strip"]],
        p_dir="x", excite=0.0)

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


def run_solve(p: dict, outdir: str, dry_run: bool, threads: int = 2) -> int:
    """Build the model and (unless dry_run) run it.  Returns an exit code."""
    FDTD, _csx = build_model(p)

    if dry_run:
        print("BUILD OK: CSX model constructed, FDTD.Run() NOT called.")
        return 0

    os.makedirs(outdir, exist_ok=True)
    # trap (7): thread count is a Run() kwarg; there is no SetMaxThreads().
    FDTD.Run(outdir, cleanup=True, verbose=1, numThreads=threads)

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
                    help="with --dry-run, also build the CSX model "
                         "(requires openEMS)")
    ap.add_argument("--threads", type=int, default=2,
                    help="Run(numThreads=...) (default: 2)")
    args = ap.parse_args(argv)

    p = plan()

    # The echo is always printed first: it is the audit trail, and it is the
    # one thing that must be reviewable without the solver installed.
    echo(p)

    if args.dry_run and not args.with_bindings:
        print("RESULT: DRY-RUN -- geometry echo only, openEMS never imported,")
        print("        FDTD.Run() not called. This script is AUTHORED-")
        print("        UNEXERCISED; nothing here is a validated model result.")
        return 0

    try:
        return run_solve(p, args.out, args.dry_run, args.threads)
    except ImportError as exc:
        print("\nRESULT: NO-BINDINGS -- openEMS is not importable here (%s)." % exc)
        print("        Geometry echo above is pure arithmetic and stands.")
        print("        The model itself is AUTHORED-UNEXERCISED.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
