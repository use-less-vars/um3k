#!/usr/bin/env python3
"""Minimal openEMS smoke solve: prove the FDTD engine actually executes.

WHAT THIS PROVES
    That the openEMS 0.0.35 FDTD solver runs to completion under these
    bindings: a mesh is defined, a source is excited, time stepping happens,
    and the solver writes per-port time-domain records to disk. That is all.

WHAT THIS DOES NOT PROVE
    Nothing about physics. The geometry is a 20 x 10 x 10 mm empty air box
    with two 50 ohm lumped ports; there is no microstrip, no substrate, no
    reference impedance calculation and no S-parameter extraction. A later
    unloaded-line / microstrip cross-check must build its own model and must
    not treat this file as a validated example.

    Success criterion: the solver-written file ``port_ut_1`` exists afterwards
    and its header names openEMS. Its first line is written by the C++ binary,
    not by the Python layer, which is what makes it evidence of a real solve.

USAGE
    inside the container:   python3 smoke_solve.py [OUTDIR]
    from the host:          docker run --rm -i openems:bookworm \
                                python3 - < docker/openems/smoke_solve.py
    with a bind mount:      docker run --rm -v "$PWD/out_openems:/tmp/oems/sim" \
                                openems:bookworm python3 - < docker/openems/smoke_solve.py

    OUTDIR defaults to /tmp/oems/sim. ``cleanup=True`` is passed to Run(), so
    an existing OUTDIR is cleared first -- note that files written by an
    earlier container run are root-owned and cannot be removed as the host
    user if OUTDIR is a bind mount.

MEASURED RESULT (host jojo-Swift-SFG16-71, 2 threads)
    Runtime ~3 min. Outputs (bytes): et 33216, ht 33189,
    port_it_1 1174638, port_it_2 1174523, port_ut_1 1207446, port_ut_2 1174550.
    port_ut_1 begins:
        % time-domain voltage integration by openEMS v0.0.35 @Thu Nov  5 10:02:22 2026
        % start-coordinates: (0.005,0.005,0.004) m -> [5,5,4]
        % stop-coordinates: (0.005,0.005,0.005) m -> [5,5,5]
        % t/s	voltage
"""

import os
import sys

import numpy as np

# numpy >= 1.24 removed the np.float alias, but openEMS/ports.py still does
# ``np.array(start, np.float)`` -- without this shim every AddLumpedPort /
# AddMSLPort call dies with "'module' object has no attribute 'float'".
for _alias, _builtin in (("float", float), ("int", int), ("complex", complex), ("bool", bool)):
    if not hasattr(np, _alias):
        setattr(np, _alias, _builtin)

# ``openEMS.openEMS`` is the solver CLASS, not a module: instance it, do not
# call ``OEMS.OpenEMS()``.
from openEMS import openEMS as OEMS
from CSXCAD import ContinuousStructure

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else "/tmp/oems/sim"

FDTD = OEMS()
FDTD.SetGaussExcite(1e9, 1e9)  # f0 = 1 GHz, fc = 1 GHz

# SetBoundaryCond wants a six-element list. 'MUR' is used instead of 'PML_8'
# because PML_8 consumes 8 cells per side, which on this coarse mesh would
# swallow the port region entirely.
FDTD.SetBoundaryCond(["MUR"] * 6)

csx = ContinuousStructure()
FDTD.SetCSX(csx)

# ContinuousStructure has no AddBox(): primitives are added through the
# property object.
air = csx.AddMaterial("air", epsilon=1)
air.AddBox(start=[0, 0, 0], stop=[20e-3, 10e-3, 10e-3])

# csx.DefineGrid() is broken in CSXCAD 0.6.2, and an explicit mesh is
# mandatory (there is no auto-mesh). Build it through GetGrid().
g = csx.GetGrid()
g.SetDeltaUnit(1.0)  # mesh lines below are in metres
g.SetLines("x", np.linspace(0, 20e-3, 21))
g.SetLines("y", np.linspace(0, 10e-3, 11))
g.SetLines("z", np.linspace(0, 10e-3, 11))
print("lines x:", g.GetQtyLines("x"), "y:", g.GetQtyLines("y"),
      "z:", g.GetQtyLines("z"), "valid:", g.IsValid())

# AddLumpedPort is a method on the solver, not a function in openEMS.ports.
# start/stop lie on grid lines and differ only along p_dir.
FDTD.AddLumpedPort(port_nr=1, R=50., start=[5e-3, 5e-3, 4e-3],
                   stop=[5e-3, 5e-3, 5e-3], p_dir="z", excite=1.0)
FDTD.AddLumpedPort(port_nr=2, R=50., start=[15e-3, 5e-3, 4e-3],
                   stop=[15e-3, 5e-3, 5e-3], p_dir="z", excite=0)
print("PORTS-ADDED")

# There is no SetSolverType(); thread count is a Run() keyword.
FDTD.Run(OUTDIR, cleanup=True, verbose=1, numThreads=2)
print("SOLVER-RAN")

# The solver writes the port records; a missing file means no real FDTD run
# happened even if Run() returned without raising.
port_file = os.path.join(OUTDIR, "port_ut_1")
if not os.path.isfile(port_file):
    sys.exit("SMOKE-FAILED: solver returned but did not write %s -- "
             "no FDTD time stepping took place" % port_file)

with open(port_file, "r", errors="replace") as fh:
    header = fh.readline().rstrip()
if "openEMS" not in header:
    sys.exit("SMOKE-FAILED: %s was not written by openEMS (header: %r)"
             % (port_file, header))

print("SMOKE-OK: %s (%d bytes) :: %s"
      % (port_file, os.path.getsize(port_file), header))
