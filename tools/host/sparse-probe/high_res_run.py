#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""high_res_run.py -- the pre-registered JOINT mesh-refinement ladder for
``R_extracted`` (the `T4_amp` operand).

WHAT THIS IS
------------
Five rungs of ``tools/host/c1-audit/c1_audit.py``, run one after another, with
the mesh refined in all three bands AT ONCE -- strip, first-axis air, and the
second-axis substrate|interface|air triple -- and everything else held fixed
(geometry, frequency, criterion, column-selection rule, ``R_analytic``).  Each
rung reports the scored quantity

    Q = R_extracted / R_analytic                    (R_analytic = 2.8101021387524523)

against the bar that was registered before any refined-mesh number was taken,
``|Q - 1| <= 0.10``, i.e. ``R_extracted`` in [2.52909192487721, 3.09111235262770].

Rung 0 is the BANKED CONTROL: strip 12, air 9, z 8|4|4, the 31 x 17 node mesh
the capture in ``tools/host/c1-audit/out/`` was taken on.  It must return
``R_extracted`` equal to ``4.0489791163982565`` within a relative 1e-6, with
``n_eligible = 1``.  The selected column index is NOT part of that gate: on this
identical mesh the solver selects the same mode at column 732 while the banked capture
records column 738, with R agreeing to 8e-13, so a column index is not reproducible
across builds and column indices are printed as diagnostics
only.  If the gate fails, the harness is wrong rather than the
physics, so the driver stops there, says so, and does NOT run rungs 1-4.

Why joint: earlier sweeps moved one band at a time and left the others.  Strip
refinement alone is flat to 0.13 % over 3x; the first-axis air band alone is the
only band that moved ``R`` but was still 6.0 % above the upper edge at its
densest reachable point (N = 22 -> 3.2761300897590); the z band alone moved it
the wrong way.  Refining all three together is the one experiment those three
did not perform, and it is the mechanism ``docs/design/t4_amp_ratio.md`` §9.6
names as "a re-meshed run".

THIS IS THE DENSE QZ PATH
-------------------------
``emfit`` has no sparse eigensolver and nothing here adds one: every rung runs
the same dense QZ pencil as the banked capture, only bigger.  ``emfit`` refuses
above ``_MIXED_DENSE_MAX = 3000`` free edges, so rungs 2-4 are only reachable
through ``C1_ALLOW_DENSE_ABOVE_MAX=1`` -- which this driver sets, and sets ONLY
for the rungs that need it (free_e > 3000).  Consequence: the family is capped
by memory and by O(n^3) time, not by physics, and the last rung of the ladder
is a resource decision, not a convergence decision.

COST MODEL (documented, not measured, for rungs not yet run)
------------------------------------------------------------
    peak RAM  ~ 5.5 x 8 n_free^2 bytes      (one matrix = 8 n^2; five live
                                             copies is what the QZ path holds:
                                             H, C, the two QZ workspaces and
                                             the accumulation -- see README.md)
    wall      ~ 45 s x (n_free / 1444)^3    (dense QZ is cubic; rung 0's own
                                             log shows ~21 s, so the 45 s base
                                             is ~2x pessimistic on purpose)
Rung 0's measured wall time replaces the 45 s base as soon as it is known, and
the revised estimates are printed before rung 1 starts.

USAGE
-----
    ./high_res_run.sh                  # rungs 0-3 (rung 4 is opt-in)
    ./high_res_run.sh --dry-run        # plan table only; creates nothing
    ./high_res_run.sh --rungs 0,1,2,3,4
    ./high_res_run.sh --include-rung4
    ./high_res_run.sh --max-gb 12 --timeout 7200
    ./high_res_run.sh --rungs 3,4 --resume   # control validated from a PREVIOUS pass
    python3 -u high_res_run.py --help

A ladder is scored against the banked control, so a selection that does not start at
rung 0 is REFUSED unless ``--resume`` validates the rung-0 capture already on disk;
with ``--resume`` the control is produced from a previous pass and the report says so.
A selection with a hole in it is refused outright, and a pass with no usable control
produces NO verdict (``T4_amp: NOT EVALUATED``) and exits non-zero.

The audit itself is invoked once per rung, in its own process, with its
environment built from scratch (every inherited ``C1_*`` is dropped first, so a
stale knob in the caller's shell cannot silently move a rung).  Each rung writes
its environment to ``env.json`` and its full stdout/stderr to ``run.log`` before
the numbers are read back out of the rung's own ``c1_spectrum.npz``.
"""
import argparse
import json
import math
import os
import queue
import re
import subprocess
import sys
import threading
import time

import numpy as np

# ---------------------------------------------------------------------------
# paths -- this file lives at <repo>/tools/host/sparse-probe/high_res_run.py,
# which is THREE levels below the repository root.  Never count ".." levels
# loosely: a wrong count yields <repo>/tools and `import emfit` inside the audit
# then fails with ModuleNotFoundError (tools/host/c1-audit/c1_audit.py:149-158
# carries the same trap).  The audit is run by path, with cwd at its own
# directory, exactly as tools/host/c1-audit/run.sh does it.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir))
AUDIT_DIR = os.path.join(REPO, "tools", "host", "c1-audit")
AUDIT = os.path.join(AUDIT_DIR, "c1_audit.py")

# ---------------------------------------------------------------------------
# registered constants.  NONE of these may be edited after a rung has been run:
# the bar and the analytic reference were fixed before any refined-mesh number
# existed (decisions.md, "bar first, number second, verdict third").
# ---------------------------------------------------------------------------
R_ANALYTIC = 2.8101021387524523
R_REGISTERED = 4.0489791163982565      # rung-0 / banked operand; the control
Q_BAND = 0.10                          # |Q - 1| <= 0.10, locked
BAND_LO = R_ANALYTIC * (1.0 - Q_BAND)  # 2.52909192487721
BAND_HI = R_ANALYTIC * (1.0 + Q_BAND)  # 3.09111235262770
CONTROL_RTOL = 1e-6                     # rung-0 gate: |R - R_REGISTERED| / R <= this
# There is deliberately NO column-index constant here.  The banked capture's
# identified column (738) is not reproducible: on the identical rung-0 mesh the
# solver selects column 732 while the banked cache holds 738, for the same mode,
# with R agreeing to 8e-13 -- two fresh runs both reported 732, so the index is a
# property of the build and the cache, not of the physics.  A column index is
# therefore never a gate and never a mode identifier; every column number printed
# by this driver is a DIAGNOSTIC, and modes are identified by beta_sq and R.
CONTROL_FREE_E = 1444                  # rung 0, and the cost-model denominator
CONTROL_SECONDS = 45.0                 # cost-model base (rung 0's log shows ~21 s)
QZ_POWER = 3.0                         # dense QZ: wall ~ n^3
MEM_FACTOR = 5.5                       # live dense copies of n^2*8 bytes
MIXED_DENSE_MAX = 3000                 # emfit/mode2d.py:151, guard default
PROGRESS_S = 30.0                      # heartbeat period while a rung runs

# ---------------------------------------------------------------------------
# the ladder.  nx = 1 + 2*yair + strip, nz = 1 + sum(z); the mesh arithmetic
# behind every row was verified against emfit.structured_mesh + pec_edge_mask
# before this file was written (README.md carries the table).
# ---------------------------------------------------------------------------
RUNGS = [
    {"rung": 0, "role": "banked control",  "strip": 12, "yair": 9,  "z": (8, 4, 4)},
    {"rung": 1, "role": "joint, 1.33x",    "strip": 16, "yair": 12, "z": (10, 5, 5)},
    {"rung": 2, "role": "joint, 1.67x",    "strip": 20, "yair": 15, "z": (12, 6, 6)},
    {"rung": 3, "role": "joint, 2.00x",    "strip": 24, "yair": 18, "z": (14, 7, 7)},
    {"rung": 4, "role": "joint, 2.67x",    "strip": 36, "yair": 22, "z": (20, 10, 10)},
]
DEFAULT_RUNGS = [0, 1, 2, 3]

PREREG = """
====================================================================================================
PRE-REGISTRATION -- read before the first rung; it was written before any rung of THIS ladder ran.
====================================================================================================
SCORED QUANTITY   Q = R_extracted / R_analytic,  R_analytic = 2.8101021387524523 (unchanged, §1).
THE BAR (locked)  |Q - 1| <= 0.10 on the dimensionless ratio, equivalently
                  0.90 <= Q <= 1.10, equivalently R_extracted in
                  [2.52909192487721, 3.09111235262770].  Quoted verbatim from the ruling of record:
                  "`T4_amp`'s pass condition is `|Q - 1| <= 0.10` on the scored quantity
                   `Q = R_extracted / R_analytic`, equivalently `0.90 <= Q <= 1.10`.  ... The band is
                   defined on the dimensionless ratio `Q`; the interval on `R_extracted` is a
                   consequence of that definition and is not a second, separate bar."
                  "Locked by pre-registration.  The bar was registered before any measurement was
                   taken on the refined mesh, and it is not to be moved after that measurement:
                   bar first, number second, verdict third."
THE MECHANISM     This ladder IS the mechanism that docs/design/t4_amp_ratio.md §9.6 requires a
                  revisit to name: "a re-meshed run".  Verbatim: "Any change is governed by the
                  revisit clause at docs/design/t4_amp_ratio.md §9.6, which permits exactly one
                  revisit, requires it to be pre-registered here with its tolerance, mechanism and
                  date, and requires it to name a mechanism (a changed column-selection rule, a
                  re-meshed run, a different leg, a resolved estimator question) rather than a new
                  number."  No column-selection rule, leg or estimator is changed here; only the
                  mesh.  If a rung ever reports n_eligible != 1, that is a FINDING reported as such
                  and NOT a licence to re-select a column.
THE READING       Exactly two outcomes.  No third branch.
                  (1) If the last completed rung's Q lies inside [0.90, 1.10], T4_amp PASSES, and
                      the ladder is the §9.6 revisit's measurement.
                  (2) Otherwise T4_amp remains FAIL, the bar is untouched, the constraint binds, and
                      no further mesh refinement is nameable as a mechanism until a DIFFERENT one
                      is named.  A ladder that converges to something outside the band is a
                      negative about the mesh, not a partial credit.
                  The diagnostic reading is pre-registered too, because it is the branch that
                  carries information even when (2) fires:
                  (d1) |R_extracted - R_analytic| falls monotonically and the 1/n_free extrapolant
                       lands inside the band  ->  the discrepancy is discretisation, and the bar
                       can be met by a run at the fitted resolution;
                  (d2) it is flat or non-monotone, or the extrapolant stays above 3.09111235262770
                       ->  the mesh is NOT the mechanism, and the ladder has eliminated it.
                  Rung 0 is a gate, not a data point: if it fails either half of the gate --
                  n_eligible = 1, and |R - 4.0489791163982565| / 4.0489791163982565 <= 1e-6 --
                  the run stops and reports a HARNESS fault.  No rung is scored against a control
                  that failed.  The gate is on the number and on there being exactly one eligible
                  column; it is NOT on which column index was selected.  QZ column ordering is not
                  reproducible: on the identical rung-0 mesh the solver selects column 732 while
                  the banked cache holds 738, for the same mode, with R agreeing to 8e-13.  A
                  column index is a diagnostic here, never a mode identifier, never a gate.
WHAT IS FIXED     geometry, f0 = 7833566197.718491 Hz, the criterion, column-selection rule,
                  R_analytic, the bar, and the ordering of the readings above.  Only strip cells,
                  first-axis air cells and the z triple move, together, per rung.
POST-HOC USE OF A NUMBER FROM THIS LADDER TO MOVE THE BAR IS A BREACH, not a correction.
====================================================================================================
"""

# ---------------------------------------------------------------------------
# mesh arithmetic.  Verified against emfit (structured_mesh + pec_edge_mask) for
# every rung of this ladder before the driver was written -- numbers in README.md.
#   nx    = 1 + 2*yair + strip            (mirror-symmetric first axis)
#   nz    = 1 + sum(z)                    (substrate | interface | air)
#   edges = 3*nx*nz - 2*nx - 2*nz + 1     (right-triangle mesh, closed form)
#   n_pec = (nx - 1) + strip              (ground row + the strip itself)
#   free  = edges - n_pec                 (the QZ pencil size)
# ---------------------------------------------------------------------------


def mesh_counts(strip, yair, z):
    nx = 1 + 2 * yair + strip
    nz = 1 + int(sum(z))
    nodes = nx * nz
    tris = 2 * (nx - 1) * (nz - 1)
    edges = 3 * nx * nz - 2 * nx - 2 * nz + 1
    n_pec = (nx - 1) + strip
    free_e = edges - n_pec
    one_matrix_gb = (free_e ** 2) * 8 / float(2 ** 30)
    return {
        "nx": nx, "nz": nz, "nodes": nodes, "tris": tris, "edges": edges,
        "n_pec": n_pec, "free_e": free_e,
        "matrix_gb": one_matrix_gb,
        "peak_gb": MEM_FACTOR * one_matrix_gb,
    }


def check_mesh_arithmetic(r, c, data):
    """Recompute this rung's counts from (strip, yair, z) and check them against the
    mesh the audit actually built.  Returns a list of mismatch strings ([] = ok).

    npz key ``free_e`` is the INDEX ARRAY of the free edges, so its size is the
    free-edge count; the identity checked is free_e == n_edges - n_pec with
    n_pec = (nx - 1) + strip."""
    if data is None:
        return ["no npz: the built mesh cannot be checked"]
    bad = []
    if data["free_e"] != c["free_e"]:
        bad.append("free_e: npz (size of its free-edge array) %d vs recomputed %d"
                   % (data["free_e"], c["free_e"]))
    if data["n_edges"] != c["edges"]:
        bad.append("n_edges: npz %d vs recomputed %d" % (data["n_edges"], c["edges"]))
    if data["n_nodes"] != c["nodes"]:
        bad.append("n_nodes: npz %d vs recomputed %d" % (data["n_nodes"], c["nodes"]))
    if data["free_e"] != data["n_edges"] - c["n_pec"]:
        bad.append("npz internal: free_e %d but n_edges - n_pec = %d - %d = %d"
                   % (data["free_e"], data["n_edges"], c["n_pec"],
                      data["n_edges"] - c["n_pec"]))
    return bad


def control_gate(data):
    """The rung-0 gate, in ONE place: (ok, relative, detail).

    |R - R_REGISTERED| / |R_REGISTERED| <= CONTROL_RTOL AND n_eligible == 1.  Both
    constants are used, never retyped.  An absent/unreadable capture fails.
    """
    if data is None:
        return False, float("inf"), "no readable npz: the control gate cannot be evaluated"
    rel = abs(data["R_extracted"] - R_REGISTERED) / abs(R_REGISTERED)
    rel_ok = rel <= CONTROL_RTOL
    one_ok = data["n_eligible"] == 1
    detail = ("R_extracted %.17g vs registered %.17g -> relative %.3e (gate %.0e) %s;"
              " n_eligible %d (gate: exactly 1) %s"
              % (data["R_extracted"], R_REGISTERED, rel, CONTROL_RTOL,
                 "PASS" if rel_ok else "FAIL", data["n_eligible"],
                 "PASS" if one_ok else "FAIL"))
    return (rel_ok and one_ok), rel, detail


def validate_control_capture(ctrl_dir):
    """Validate a rung-0 capture written by a PREVIOUS pass.  -> (ok, note, why).

    Five refusals, each naming itself: directory absent, npz absent, npz not loadable,
    free_e not rung 0's, control gate not passed (the gate test includes n_eligible == 1).
    free_e and n_eligible are read out of the npz itself, so none of this is taken on
    faith: c1-audit/c1_audit.py:857 stores ``n_eligible``, and the npz key ``free_e`` is
    the INDEX ARRAY of the free edges, so its SIZE is the count.  The directory is
    located by rung_dirname(0) + out_root upstream; this function never lists out_root.
    """
    if not os.path.isdir(ctrl_dir):
        return False, None, "the rung-0 directory is absent: %s" % ctrl_dir
    reason = []
    data = read_rung_npz(ctrl_dir, reason)
    if data is None:
        return False, None, (reason[0] if reason else
                             "the rung-0 capture could not be read: %s" % ctrl_dir)
    if data["free_e"] != CONTROL_FREE_E:
        return False, None, ("its free_e is %d, not rung 0's %d: that capture is a different"
                             " mesh, not the banked control" % (data["free_e"], CONTROL_FREE_E))
    ok, _rel, detail = control_gate(data)
    if not ok:
        return False, None, "the control gate fails on it: %s" % detail
    note = ("rung 0 (banked control) was NOT run in this pass: the control is the capture"
            " already on disk in\n  %s\n  validated now -- %s" % (ctrl_dir, detail))
    return True, note, None


def est_seconds(free_e, base=CONTROL_SECONDS):
    return base * (float(free_e) / CONTROL_FREE_E) ** QZ_POWER


def rung_dirname(r):
    return "rung%d_s%d_a%d_z%s" % (
        r["rung"], r["strip"], r["yair"], "".join(str(v) + "-" for v in r["z"]).rstrip("-"))


# ---------------------------------------------------------------------------
# environment for one rung.  Every inherited C1_* is dropped first: the audit is
# env-configured only (no argument parser), so a stale C1_STRIP_CELLS in the
# caller's shell would silently move a rung.  One answer only.
# ---------------------------------------------------------------------------
def build_env(r, out_dir, free_e):
    env = {k: v for k, v in os.environ.items() if not k.startswith("C1_")}
    env["C1_REPO"] = REPO
    env["C1_OUTDIR"] = out_dir
    env["C1_STRIP_CELLS"] = str(r["strip"])
    env["C1_Y_AIR_CELLS"] = str(r["yair"])
    env["C1_Z_CELLS"] = ",".join(str(v) for v in r["z"])
    if r["rung"] != 0:
        # a refinement rung is a different mesh ON PURPOSE: the banked-cache
        # guard is a mesh-identity gate and would hard-exit otherwise.
        env["C1_ALLOW_REMESH"] = "1"
    if free_e > MIXED_DENSE_MAX:
        # above emfit's dense cap, opt in explicitly AND loudly (the audit prints
        # a banner).  Never set for a rung that does not need it.
        env["C1_ALLOW_DENSE_ABOVE_MAX"] = "1"
    # thread pinning, so the wall clock compares rung to rung
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    return env


ECHO_PREFIXES = ("mesh ", "dof ", "spectrum ", "solve_modes_mixed ", "DENSE ", "note ",
                 "VERDICT", "REPRO", "REPRODUCTION", "wrote ", "DONE ", "WARNING", "banked ")


def run_one(r, out_dir, env, timeout, log_path):
    """Run the audit for one rung.  Streams its output, tees to log_path, echoes
    the lines that carry numbers, and heartbeats every PROGRESS_S seconds."""
    t0 = time.monotonic()
    c = mesh_counts(r["strip"], r["yair"], r["z"])
    sys.stdout.write(
        "\n== rung %d/%d  %s  strip=%d yair=%d z=%s  ->  %dx%d nodes, %d free edges\n"
        "   projected peak %.2f GB, projected wall %.0f s%s\n" % (
            r["rung"], len(RUNGS) - 1, r["role"], r["strip"], r["yair"],
            ",".join(str(v) for v in r["z"]), c["nx"], c["nz"], c["free_e"],
            c["peak_gb"], est_seconds(c["free_e"]),
            "  (above emfit's %d cap: C1_ALLOW_DENSE_ABOVE_MAX=1)" % MIXED_DENSE_MAX
            if c["free_e"] > MIXED_DENSE_MAX else ""))
    sys.stdout.flush()

    proc = subprocess.Popen(
        [sys.executable, "-u", AUDIT], cwd=AUDIT_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    q = queue.Queue()

    def _reader():
        try:
            for line in proc.stdout:
                q.put(line)
        finally:
            q.put(None)

    th = threading.Thread(target=_reader, daemon=True)
    th.start()

    lines = []
    log = open(log_path, "w", encoding="utf-8", errors="replace")
    next_beat = PROGRESS_S
    timed_out = False
    try:
        while True:
            try:
                line = q.get(timeout=1.0)
            except queue.Empty:
                line = ""
            if line is None:
                break
            if line:
                log.write(line)
                log.flush()
                lines.append(line.rstrip("\n"))
                s = line.rstrip("\n")
                if s.startswith(ECHO_PREFIXES):
                    sys.stdout.write("   | " + s + "\n")
                    sys.stdout.flush()
            el = time.monotonic() - t0
            if el >= next_beat:
                next_beat += PROGRESS_S
                sys.stdout.write("   PROGRESS rung=%d/%d free_e=%d t=%.0fs%s\n" % (
                    r["rung"], len(RUNGS) - 1, c["free_e"], el,
                    "  (heartbeat; no numbers yet)" if not lines else ""))
                sys.stdout.flush()
            if timeout and el > timeout:
                timed_out = True
                proc.kill()
                break
    finally:
        log.close()
    rc = proc.wait()
    wall = time.monotonic() - t0
    return {"lines": lines, "rc": rc, "wall": wall, "timed_out": timed_out}


# ---------------------------------------------------------------------------
# read one rung's captures back out of its own npz.  Nothing is inferred from
# stdout that the npz carries; nothing is inferred from the npz that only stdout
# carries (elapsed, banked_src and repro live only in the log).
# ---------------------------------------------------------------------------
def _why(reason, msg):
    """Record why a capture could not be read (a no-op when no sink was passed)."""
    if reason is not None:
        reason.append(msg)


def read_rung_npz(out_dir, reason=None):
    p = os.path.join(out_dir, "c1_spectrum.npz")
    if not os.path.exists(p):
        _why(reason, "c1_spectrum.npz is absent from %s" % out_dir)
        return None
    try:
        d = np.load(p, allow_pickle=False)
    except Exception as exc:                     # report it, never crash the ladder on it
        # c1-audit/c1_audit.py:816 writes this npz with np.savez, which is NOT atomic:
        # a kill mid-write leaves a truncated zip.  That is a REPORTED condition here,
        # not an uncaught exception that takes the whole pass down with it.
        _why(reason, "c1_spectrum.npz in %s does not load (%s: %s)"
             % (out_dir, type(exc).__name__, exc))
        return None
    g = lambda k, dv=None: (d[k] if k in d.files else dv)
    res = {
        "npz": p,
        # npz key "free_e" holds the INDEX ARRAY of the free edges (shape (free_e,)),
        # not a count: int(a[0]) reads the first index (1).  Its size is the count.
        "free_e": int(np.size(g("free_e"))) if g("free_e") is not None else -1,
        "n_nodes": int(g("n_nodes", -1)),
        "n_edges": int(g("n_edges", -1)),
        "R_extracted": float(g("R_extracted", float("nan"))),
        "R_extracted_ok": bool(g("R_extracted_ok", False)),
        "bank_col": int(g("bank_col", -1)),
        "identified_col": int(g("identified_col", -1)),
        "chosen_col": int(g("chosen_col", g("identified_col", -1))),
        "n_eligible": int(g("n_eligible", -1)),
        "eligible_cols": [int(v) for v in np.atleast_1d(g("eligible_cols", []))],
        "R_by_col": [float(v) for v in np.atleast_1d(g("R_by_col", []))],
        "corr_ey_by_col": [float(v) for v in np.atleast_1d(g("corr_ey_by_col", []))],
        "corr_ez_vv_by_col": [float(v) for v in np.atleast_1d(g("corr_ez_vv_by_col", []))],
        "beta_sq_all": np.atleast_1d(g("beta_sq_all", [])),
        "beta_sq": float(np.atleast_1d(g("beta_sq", [float("nan")]))[0]),
        "beta": float(np.atleast_1d(g("beta", [float("nan")]))[0]),
        "eps_eff": float(np.atleast_1d(g("eps_eff", [float("nan")]))[0]),
        "ok": bool(np.atleast_1d(g("ok", [False]))[0]),
        "k0": float(g("k0", float("nan"))),
    }
    return res


DONE_ELAPSED = re.compile(r"elapsed=([0-9.]+)s")
DONE_REPRO = re.compile(r"repro=(\w+)")
BANKED_SRC = re.compile(r"banked_src=('([^']*)'|\"([^\"]*)\")")


def parse_log(lines):
    out = {"elapsed": None, "repro": None, "banked_src": None, "done_line": None}
    for s in lines:
        if s.startswith("DONE "):
            out["done_line"] = s
            m = DONE_ELAPSED.search(s)
            if m:
                out["elapsed"] = float(m.group(1))
            m = DONE_REPRO.search(s)
            if m:
                out["repro"] = m.group(1)
        m = BANKED_SRC.search(s)
        if m:
            out["banked_src"] = m.group(2) if m.group(2) is not None else m.group(3)
    return out


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def per_rung_block(r, c, run, data, parsed):
    L = []
    L.append("-" * 100)
    L.append("RUNG %d/%d   %s   strip=%d  yair=%d  z=%s   (%d x %d nodes)" % (
        r["rung"], len(RUNGS) - 1, r["role"], r["strip"], r["yair"],
        ",".join(str(v) for v in r["z"]), c["nx"], c["nz"]))
    L.append("-" * 100)
    for s in run["lines"]:
        if s.startswith(("mesh ", "dof ")):
            L.append("  " + s)
    L.append("  mesh (projected) : nodes %d, tris %d, edges %d, n_pec %d, free_e %d"
             % (c["nodes"], c["tris"], c["edges"], c["n_pec"], c["free_e"]))
    L.append("  exit             : rc=%d%s   wall clock %.1f s   audit self-report %s" % (
        run["rc"], "  TIMED OUT" if run["timed_out"] else "", run["wall"],
        ("%.1f s" % parsed["elapsed"]) if parsed["elapsed"] else "n/a"))
    if data is None:
        L.append("  npz              : MISSING -- no numbers to report for this rung")
        if parsed["done_line"]:
            L.append("  done line        : " + parsed["done_line"])
        return "\n".join(L)
    L.append("  npz              : free_e %d, n_nodes %d, n_edges %d, ok %s"
             % (data["free_e"], data["n_nodes"], data["n_edges"], data["ok"]))
    bad = check_mesh_arithmetic(r, c, data)
    if bad:
        L.append("  mesh arithmetic  : MISMATCH -- " + "; ".join(bad))
    else:
        L.append("  mesh arithmetic  : OK -- free_e %d = n_edges %d - n_pec %d, all recomputed"
                 " from strip=%d yair=%d z=%s"
                 % (data["free_e"], c["edges"], c["n_pec"], r["strip"], r["yair"],
                    ",".join(str(v) for v in r["z"])))
    L.append("  columns (DIAGNOSTIC ONLY -- never a gate, never a mode identifier):")
    L.append("      identified_col %d, chosen_col %d, bank_col %d, n_eligible %d, eligible %s"
             % (data["identified_col"], data["chosen_col"], data["bank_col"],
                data["n_eligible"], data["eligible_cols"]))
    L.append("      QZ column ordering identifies nothing: on the rung-0 control mesh the banked")
    L.append("      capture records 738 while today's runs select 732 for the same mode, with R")
    L.append("      agreeing to 8e-13.  These numbers identify this run on this machine only.")
    L.append("  banked_src       : %s" % (parsed["banked_src"] or "n/a (not printed)"))
    L.append("  repro            : %s" % (parsed["repro"] or "n/a"))
    L.append("  beta / eps_eff   : %.9f / %.9f" % (data["beta"], data["eps_eff"]))
    L.append("  R_extracted      : %.16g   ok=%s   (T4_amp reads Q = %.9f)"
             % (data["R_extracted"], data["R_extracted_ok"],
                data["R_extracted"] / R_ANALYTIC))
    L.append("  eligible columns :")
    L.append("      %6s %18s %18s %12s %12s %6s" %
             ("col", "beta_sq", "R_by_col", "corr_ey", "corr_ez_vv", "ok"))
    for i, col in enumerate(data["eligible_cols"]):
        bs = float("nan")
        try:
            if data["beta_sq_all"].size > col:
                bs = float(np.real(data["beta_sq_all"][col]))
        except Exception:
            pass
        R_by = data["R_by_col"][i] if i < len(data["R_by_col"]) else float("nan")
        cy = data["corr_ey_by_col"][i] if i < len(data["corr_ey_by_col"]) else float("nan")
        cz = data["corr_ez_vv_by_col"][i] if i < len(data["corr_ez_vv_by_col"]) else float("nan")
        L.append("      %6d %18.7f %18.12g %12.9f %12.9f %6s" %
                 (col, bs, R_by, cy, cz, data["R_extracted_ok"]))
    return "\n".join(L)


def cross_rung_block(results):
    L = ["=" * 100,
         "CROSS-RUNG  --  the operand against free edges (nothing here is a fit yet)",
         "=" * 100,
         "  %4s %8s %10s %20s %12s %12s %8s %9s %5s %5s" % (
             "rung", "free_e", "n_nodes", "R_extracted", "|R-R_an|", "|R-R_reg|",
             "Q", "n_elig", "bank*", "ok")]
    for e in results:
        d = e["data"]
        if d is None:
            L.append("  %4d %8d %10s %20s" % (e["rung"]["rung"], e["counts"]["free_e"],
                                             "-", "NPZ MISSING"))
            continue
        L.append("  %4d %8d %10d %20.13g %12.6f %12.6f %8.5f %9d %5d %5s" % (
            e["rung"]["rung"], d["free_e"], d["n_nodes"], d["R_extracted"],
            abs(d["R_extracted"] - R_ANALYTIC), abs(d["R_extracted"] - R_REGISTERED),
            d["R_extracted"] / R_ANALYTIC, d["n_eligible"], d["bank_col"], d["ok"]))
    L.append("  reference: R_analytic %.16g   R_registered %.16g   band [%.14g, %.14g]" % (
        R_ANALYTIC, R_REGISTERED, BAND_LO, BAND_HI))
    L.append("  * bank* is the QZ column index this run happened to select.  It is a DIAGNOSTIC:")
    L.append("    column ordering is not reproducible -- on the rung-0 control mesh the banked")
    L.append("    capture records 738 and today's runs select 732, same mode, R agreeing to 8e-13.")
    L.append("    So it is neither a gate nor a mode identifier; the rungs are compared by free_e,")
    L.append("    R_extracted and beta_sq only.")
    return "\n".join(L)


def _smooth(vals):
    """Structural reading of a short sequence, declared before it is looked at:
    smooth = every successive difference has the same sign (monotone), or no single
    step exceeds twice the median absolute step (no isolated jump).  A sequence with
    a missing value, or with fewer than three points, is not claimed either way."""
    if any(v != v for v in vals):
        return False, "a value is missing (nan): smoothness is NOT claimed"
    if len(vals) < 3:
        return True, "fewer than 3 rungs: smoothness is not testable and is not claimed"
    d = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    steps = ", ".join("%+.6g" % x for x in d)
    signs = {(x > 0) - (x < 0) for x in d if x != 0}
    if len(signs) <= 1:
        return True, "monotone (steps %s)" % steps
    med = float(np.median([abs(x) for x in d]))
    if med > 0.0 and all(abs(x) <= 2.0 * med for x in d):
        return True, "no isolated jump (steps %s, median |step| %.6g)" % (steps, med)
    return False, "one step dominates (steps %s, median |step| %.6g)" % (steps, med)


def stability_block(results):
    L = ["=" * 100,
         "STABILITY  --  read by physics and by number, never by column index",
         "=" * 100,
         "  A QZ column index is not reproducible: on the identical rung-0 mesh the solver",
         "  selects column 732 while the banked cache holds 738, for the same mode, with R",
         "  agreeing to 8e-13.  So no column index below is evidence of anything, and none of",
         "  them is compared against anything.",
         "  What is checked instead, for every rung:",
         "    (1) exactly one criterion-passing column (n_eligible == 1);",
         "    (2) R_extracted varies smoothly with the free-edge count;",
         "    (3) the SELECTED mode's beta_sq (= eps_r * k0^2, k0^2 = 2.694e4, so of order",
         "        1.185e5) varies smoothly with the free-edge count -- the mode must not change",
         "        identity as the mesh refines, which a column index cannot report and beta_sq can.",
         "  Smoothness is the declared test in _smooth(): monotone, or no step above twice the",
         "  median step.  This is a structural reading only.  The bar of record is",
         "  |Q - 1| <= 0.10, it is untouched here, and nothing below is scored against it.",
         ""]
    meas = [(e["rung"]["rung"], e["data"]) for e in results if e["data"]]
    if not meas:
        L.append("  no rung produced numbers: nothing is being checked.")
        return "\n".join(L)

    per = []
    for rr, d in meas:
        cols = []
        for i, col in enumerate(d["eligible_cols"]):
            bs = float("nan")
            try:
                if d["beta_sq_all"].size > col:
                    bs = float(np.real(d["beta_sq_all"][col]))
            except Exception:
                pass
            cols.append({
                "col": col,
                "beta_sq": bs,
                "R": d["R_by_col"][i] if i < len(d["R_by_col"]) else float("nan"),
                "corr_ey": (d["corr_ey_by_col"][i]
                            if i < len(d["corr_ey_by_col"]) else float("nan")),
                "corr_ez_vv": (d["corr_ez_vv_by_col"][i]
                               if i < len(d["corr_ez_vv_by_col"]) else float("nan")),
            })
        per.append({"rung": rr, "free_e": d["free_e"], "n_eligible": d["n_eligible"],
                    "cols": cols, "beta_sq": d["beta_sq"], "R": d["R_extracted"]})

    L.append("  every eligible column of every rung (indices are diagnostics):")
    L.append("  %4s %8s %6s" % ("rung", "free_e", "n_elig"))
    for p in per:
        L.append("  %4d %8d %6d" % (p["rung"], p["free_e"], p["n_eligible"]))
        if not p["cols"]:
            L.append("        (no eligible column listed in this npz)")
        for e in p["cols"]:
            L.append("        col %6d  beta_sq %18.7f  R_by_col %18.12g  corr_ey %+.9f"
                     "  corr_ez_vv %+.9f"
                     % (e["col"], e["beta_sq"], e["R"], e["corr_ey"], e["corr_ez_vv"]))
    L.append("")
    L.append("  the selected mode per rung -- these are the numbers that are compared:")
    L.append("  %4s %8s %22s %20s" % ("rung", "free_e", "R_extracted", "beta_sq"))
    for p in per:
        L.append("  %4d %8d %22.15g %20.9g"
                 % (p["rung"], p["free_e"], p["R"], p["beta_sq"]))
    L.append("")

    multi = [p for p in per if p["n_eligible"] != 1]
    if multi:
        for p in multi:
            L.append("  FINDING -- rung %d reports n_eligible = %d.  Every eligible column of"
                     " that rung:" % (p["rung"], p["n_eligible"]))
            for e in p["cols"]:
                L.append("      col %6d  beta_sq %18.7f  R_by_col %18.12g"
                         % (e["col"], e["beta_sq"], e["R"]))
        L.append("  Reported as a finding.  It is NOT a licence to re-select a column, and the")
        L.append("  pre-registration forbids using it to move the bar.")
    else:
        L.append("  every rung kept exactly one criterion-passing column.")

    sR, dR = _smooth([p["R"] for p in per])
    sB, dB = _smooth([p["beta_sq"] for p in per])
    L.append("")
    L.append("  verdict components:")
    L.append("     n_eligible == 1 on every rung           : %s"
             % ("YES" if not multi else "NO (rung(s) %s)" % ", ".join(str(p["rung"]) for p in multi)))
    L.append("     R_extracted smooth in free_e            : %s  [%s]"
             % ("YES" if sR else "NO", dR))
    L.append("     selected beta_sq smooth in free_e       : %s  [%s]"
             % ("YES" if sB else "NO", dB))
    ok = (not multi) and sR and sB
    L.append("  verdict: %s"
             % ("STABLE -- one column is selected on every rung, and both the reading and the"
                " mode's eigenvalue move smoothly with the mesh."
                if ok else
                "NOT STABLE -- see the component that failed.  A failure here is a harness or"
                " identification finding, not physics, and it is not a reason to move the bar."))
    return "\n".join(L)


def fit_block(results):
    # one entry per MEASURED rung, rung number carried alongside -- a skipped rung
    # must not shift the labels of the points either side of it.
    pts = [(e["rung"]["rung"], e["data"]["free_e"], e["data"]["R_extracted"])
           for e in results if e["data"]]
    L = ["=" * 100, "FITS  --  diagnostics only; neither is a law and neither moves the bar", "=" * 100]
    if len(pts) < 2:
        L.append("  fewer than two measured rungs: no fit, and no extrapolant may be quoted.")
        return "\n".join(L)
    labels = [p[0] for p in pts]
    x = np.array([p[1] for p in pts], dtype=float)
    y = np.array([p[2] for p in pts], dtype=float)
    dev = np.abs(y - R_ANALYTIC)

    L.append("  (a) log|R - R_analytic| = c + p log(free_e)    [is the residual shrinking at all?]")
    if np.all(dev > 0) and len(pts) >= 2:
        lx, ly = np.log(x), np.log(dev)
        p, c = np.polyfit(lx, ly, 1)
        pred = c + p * lx
        resid = ly - pred
        L.append("      p = %+.4f   c = %+.4f   rms(log residual) = %.4f" % (p, c, float(np.sqrt(np.mean(resid ** 2)))))
        for i in range(len(pts)):
            L.append("      rung %d: free_e %6d  dev %.6e  log10 dev %+9.4f  resid %+9.4f"
                     % (labels[i], int(x[i]), dev[i], math.log10(dev[i]), resid[i]))
        L.append("      A p near 0 means the residual is flat: refinement is not reducing it.")
        L.append("      A free p fitted to four noisy points is NOT a convergence order -- with")
        L.append("      sign-alternating deltas at the 1e-3 level (the strip sweep) p is not")
        L.append("      identifiable, and it is quoted above as a diagnostic, not as an order.")
    else:
        L.append("      not fittable (a residual is exactly zero or a rung is missing).")

    L.append("")
    L.append("  (b) R = a/free_e + R_inf    [two-parameter least squares; where does it extrapolate?]")
    A = np.column_stack([np.ones_like(x), 1.0 / x])
    sol, *_ = np.linalg.lstsq(A, y, rcond=None)
    R_inf, a = float(sol[0]), float(sol[1])
    r = y - A.dot(sol)
    L.append("      a = %+.6e   R_inf = %.12f   rms(residual) = %.6e" % (a, R_inf, float(np.sqrt(np.mean(r ** 2)))))
    for i in range(len(pts)):
        L.append("      rung %d: free_e %6d  R %.13g  fit %.13g  resid %+.6e" % (
            labels[i], int(x[i]), y[i], float(A.dot(sol)[i]), float(r[i])))
    L.append("      distance of R_inf to R_analytic  : %+.6f  (%+.3f %%)" % (
        R_inf - R_ANALYTIC, 100.0 * (R_inf - R_ANALYTIC) / R_ANALYTIC))
    L.append("      distance of R_inf to R_registered: %+.6f  (%+.3f %%)" % (
        R_inf - R_REGISTERED, 100.0 * (R_inf - R_REGISTERED) / R_REGISTERED))
    L.append("      R_inf inside the band [%.12g, %.12g] : %s" % (BAND_LO, BAND_HI,
                                                                 BAND_LO <= R_inf <= BAND_HI))
    L.append("      A 1/n_free form is a guess with no derivation behind it; read it as a trend,")
    L.append("      and only alongside (a).  Neither extrapolant is scored.")
    return "\n".join(L)


def rule_block(results, blocker=None, blocker_detail=None):
    """The registered reading, applied without adjustment.

    A VERDICT REQUIRES A CONTROL, and there are exactly two ways to have one: rung 0 ran
    in THIS pass, or a rung-0 capture from an EARLIER pass was validated by --resume (such
    an entry sits in ``results`` carrying no ``run``, which is how provenance is read
    here).  Otherwise the ladder is UNANCHORED and the verdict steps are not executed at
    all.  ``blocker`` is a short reason set by main() when the in-pass control gate
    FAILED -- the same refusal, for a different cause.
    """
    L = ["=" * 100, "THE REGISTERED READING, APPLIED WITHOUT ADJUSTMENT (two outcomes, no third)", "=" * 100]
    meas = [(e["rung"]["rung"], e["data"]) for e in results if e["data"]]
    if not meas:
        L.append("  no rung produced numbers: nothing is read, and nothing is softened.")
        L.append("  T4_amp: NOT EVALUATED (no numbers)")
        return "\n".join(L)
    devs = [(rr, abs(d["R_extracted"] - R_ANALYTIC)) for rr, d in meas]
    ctrl_entry = next((e for e in results
                       if e["rung"]["rung"] == 0 and e["data"] is not None), None)
    ctrl = ctrl_entry["data"] if ctrl_entry is not None else None
    from_previous = ctrl_entry is not None and ctrl_entry.get("run") is None
    L.append("  step 1 -- the control.")
    if ctrl is None:
        L.append("     rung 0 did not run in this pass, and no rung-0 capture from an earlier")
        L.append("     pass was validated with --resume: the ladder is UNANCHORED.")
    else:
        gate_ok, rel, gate_detail = control_gate(ctrl)
        rel_ok = rel <= CONTROL_RTOL
        one_ok = ctrl["n_eligible"] == 1
        ok = gate_ok
        L.append("     rung 0 R_extracted %.17g vs registered %.17g -> relative %.3e"
                 % (ctrl["R_extracted"], R_REGISTERED, rel))
        L.append("       gate: relative <= %.0e  -> %s" % (CONTROL_RTOL,
                                                          "PASS" if rel_ok else "FAIL"))
        L.append("     rung 0 n_eligible %d, gate: exactly 1 -> %s"
                 % (ctrl["n_eligible"], "PASS" if one_ok else "FAIL"))
        L.append("     rung 0 columns, DIAGNOSTIC ONLY and not part of the gate: identified_col %d,"
                 % ctrl["identified_col"])
        L.append("       chosen_col %d, bank_col %d, eligible %s.  A QZ column index is this"
                 % (ctrl["chosen_col"], ctrl["bank_col"], ctrl["eligible_cols"]))
        L.append("       run's ordering on this machine: on this identical mesh the solver picks 732")
        L.append("       while the banked cache holds 738, for the same mode, with R agreeing to")
        L.append("       8e-13.  So it is never a mode identifier and never a gate.")
        L.append("     control verdict: %s" % ("PASSED -- the rungs below are scorable" if ok
                                              else "FAILED -- harness fault, not physics"))
        L.append("     control source: %s" % ("a PREVIOUS pass -- validated with --resume; rung 0"
                                              " was NOT re-run in this pass" if from_previous
                                              else "rung 0, run in this pass"))
    reason = None
    detail = None
    if ctrl is None:
        reason = "unanchored"
        detail = ("there is no control in this pass: rung 0 was not run and no rung-0 capture"
                  " was validated with --resume")
    elif blocker is not None:
        reason = blocker
        detail = blocker_detail or blocker
    if reason is not None:
        L.append("")
        L.append("  NO VERDICT WAS PRODUCED.")
        L.append("     %s." % detail)
        L.append("     The bar |Q - 1| <= 0.10 is scored against the banked control, so with no")
        L.append("     usable control there is nothing to score: Q is not computed, the band is")
        L.append("     not compared, and the (d1)/(d2) diagnostic is not read.  Steps 2-5 below")
        L.append("     are deliberately NOT executed, and nothing above is a T4_amp reading.")
        L.append("")
        L.append("  T4_amp: NOT EVALUATED (%s)" % reason)
        L.append("")
        L.append("  remedy:")
        if ctrl is None:
            L.append("     run rung 0 in the same pass:   ./high_res_run.sh --rungs 0,1,2,3,4")
            L.append("     or validate a previous pass's rung-0 capture (it must pass the control")
            L.append("     gate on disk) and resume above it:")
            L.append("                                    ./high_res_run.sh --rungs <rungs> --resume")
        else:
            L.append("     a failed control is a HARNESS fault, not physics: no rung is scored")
            L.append("     against it.  Re-run rung 0 (--force, or move its directory aside) and")
            L.append("     find out why the control moved before any rung of this ladder is read.")
        return "\n".join(L)
    last_rr, last = meas[-1]
    Q = last["R_extracted"] / R_ANALYTIC
    L.append("  step 2 -- the operand at the last completed rung (rung %d)." % last_rr)
    L.append("     R_extracted = %.16g   Q = %.12f   |Q-1| = %.12f   band half-width 0.10"
             % (last["R_extracted"], Q, abs(Q - 1.0)))
    L.append("  step 3 -- the verdict, from the bar fixed BEFORE these numbers existed.")
    inside = BAND_LO <= last["R_extracted"] <= BAND_HI
    L.append("     R_extracted %s the band [%.14g, %.14g]" %
             ("is INSIDE" if inside else "is OUTSIDE", BAND_LO, BAND_HI))
    L.append("     T4_amp: %s" % ("PASS" if inside else "FAIL"))
    if not inside:
        L.append("     Over the band by %.4fx the half-width (%.4f %% relative error against a 10 %% allowance)."
                 % (abs(Q - 1.0) / Q_BAND, 100.0 * abs(Q - 1.0)))
    L.append("  step 4 -- the diagnostic (pre-registered (d1)/(d2)), which is read even when FAIL.")
    L.append("     |R - R_analytic| per rung: %s" %
             ", ".join("r%d %.6f" % x for x in devs))
    if from_previous:
        L.append("     (this chain covers only the rungs run in THIS pass: rung 0 is the")
        L.append("      validated capture from a previous pass, not one of these steps)")
    mono = all(devs[i][1] >= devs[i + 1][1] for i in range(len(devs) - 1))
    L.append("     non-increasing with refinement: %s" % ("YES" if mono else "NO"))
    L.append("     -> branch %s" % ("(d1) discretisation is the mechanism, in SHAPE" if mono else
                                    "(d2) the mesh is NOT the mechanism: refinement has been eliminated"))
    if mono:
        L.append("        SHAPE is not convergence: a monotone sequence whose last step has not")
        L.append("        shrunk does not establish a limit (the same reading the warm-up scan got).")
    L.append("  step 5 -- the bar.")
    L.append("     |Q - 1| <= 0.10 on Q = R_extracted/R_analytic is UNMOVED; R_analytic is UNMOVED;")
    L.append("     the column-selection rule is UNMOVED.  Bar first, number second, verdict third.")
    L.append("     Nothing in this report may be used to re-open docs/design/t4_amp_ratio.md §9.6:")
    L.append("     its one permitted revisit is the mechanism this ladder already is (a re-meshed")
    L.append("     run), and it is spent by running it, not by failing it.")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# plan (dry run)
# ---------------------------------------------------------------------------
def print_plan(sel, out_root, base_seconds):
    print("=" * 100)
    print("PLAN  --  joint refinement of strip + first-axis air + z, everything else fixed")
    print("=" * 100)
    print("  %4s %-16s %5s %5s %-10s %4s %4s %6s %6s %6s %7s %8s %9s" % (
        "rung", "role", "STRIP", "Y_AIR", "Z_CELLS", "nx", "nz", "nodes", "edges",
        "free_e", "mtx GB", "peak GB", "est s"))
    tot = 0.0
    for r in sel:
        c = mesh_counts(r["strip"], r["yair"], r["z"])
        t = est_seconds(c["free_e"], base_seconds)
        tot += t
        print("  %4d %-16s %5d %5d %-10s %4d %4d %6d %6d %6d %7.3f %8.2f %9.0f%s" % (
            r["rung"], r["role"], r["strip"], r["yair"], ",".join(str(v) for v in r["z"]),
            c["nx"], c["nz"], c["nodes"], c["edges"], c["free_e"], c["matrix_gb"],
            c["peak_gb"], t, "  *" if c["free_e"] > MIXED_DENSE_MAX else ""))
    print("  * above emfit's _MIXED_DENSE_MAX = %d: reachable only through" % MIXED_DENSE_MAX)
    print("    C1_ALLOW_DENSE_ABOVE_MAX=1, which the driver sets for exactly those rungs.")
    print("  projected total wall clock: %.0f s = %.1f min = %.2f h  (dense QZ, n^3 model;"
          % (tot, tot / 60.0, tot / 3600.0))
    print("  rung 0's own log shows ~21 s, so this base is about 2x pessimistic)")
    print("  arithmetic: nx = 1 + 2*Y_AIR + STRIP,  nz = 1 + sum(Z_CELLS),")
    print("              edges = 3*nx*nz - 2*nx - 2*nz + 1,  free_e = edges - ((nx-1) + STRIP)")
    print("")
    print("ENVIRONMENT PER RUNG (the audit is env-only; every inherited C1_* is dropped first)")
    for r in sel:
        c = mesh_counts(r["strip"], r["yair"], r["z"])
        env = build_env(r, os.path.join(out_root, rung_dirname(r)), c["free_e"])
        print("  rung %d -> %s" % (r["rung"], os.path.join(out_root, rung_dirname(r))))
        for k in sorted(env):
            if k.startswith("C1_"):
                print("      %-26s = %s" % (k, env[k]))
    print("")
    print("NOTHING WAS CREATED AND NOTHING WAS RUN: this is the plan for the invocation above.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Pre-registered joint mesh-refinement ladder for R_extracted (T4_amp operand).")
    ap.add_argument("--rungs", default=None,
                    help="comma-separated rung indices, e.g. 0,1,2,3 (default %s)"
                         % ",".join(str(v) for v in DEFAULT_RUNGS))
    ap.add_argument("--include-rung4", action="store_true",
                    help="add rung 4 (9604 free edges, ~3.7 h projected) to the selection")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan table and the per-rung environment; run nothing")
    ap.add_argument("--out-root", default=os.path.join(HERE, "out"),
                    help="root for per-rung output directories (default <here>/out)")
    ap.add_argument("--max-gb", type=float, default=8.0,
                    help="skip any rung whose projected peak RAM exceeds this (default 8)")
    ap.add_argument("--timeout", type=float, default=0.0,
                    help="per-rung wall-clock cap in seconds; 0 = no cap (default)")
    ap.add_argument("--force", action="store_true",
                    help="allow a rung to run into a non-empty output directory")
    ap.add_argument("--resume", action="store_true",
                    help="permit a rung selection that does NOT start at rung 0, provided the"
                         " rung-0 capture already on disk validates against the control gate;"
                         " the control is then reported as coming from a PREVIOUS pass")
    ap.add_argument("--solver", default="dense", choices=("dense", "sparse"),
                    help="'dense' is the only implemented path")
    a = ap.parse_args(argv)

    if a.solver != "dense":
        raise SystemExit(
            "--solver sparse: NOT IMPLEMENTED.  emfit has no sparse eigensolver; this ladder is\n"
            "the dense QZ path (free_e up to 9604, ~3.8 GB peak, O(n^3) time).  A sparse solver\n"
            "would be a design at docs/design/sparse_eigenmode.md, an unimplemented path, and a\n"
            "re-registration event -- the banked numbers would have to be re-taken on it before\n"
            "any number from it could be scored against R_analytic.  Nothing is run.")

    if a.rungs:
        try:
            sel_idx = sorted({int(t) for t in a.rungs.split(",") if t.strip()})
        except ValueError:
            raise SystemExit("--rungs must be comma-separated integers, got %r" % a.rungs)
    else:
        sel_idx = list(DEFAULT_RUNGS)
    if a.include_rung4 and 4 not in sel_idx:
        sel_idx = sorted(set(sel_idx) | {4})
    known = {r["rung"] for r in RUNGS}
    bad = [i for i in sel_idx if i not in known]
    if bad:
        raise SystemExit("unknown rung(s) %s; known: %s" % (bad, sorted(known)))
    sel = [r for r in RUNGS if r["rung"] in sel_idx]
    out_root = os.path.abspath(a.out_root)

    # ----------------------------------------------------------------------
    # the control is the ANCHOR of the ladder.  A selection that is not a
    # contiguous run starting at rung 0 cannot be scored against anything, so it
    # is refused HERE -- before a directory is made, before a rung is run.  The
    # alternative is what this driver used to do: run the rungs, then emit a
    # verdict from a report whose step 1 says the ladder is unanchored.
    # ----------------------------------------------------------------------
    rung_ids = [r["rung"] for r in sel]
    holes = [i for i in range(rung_ids[0], rung_ids[-1] + 1) if i not in set(rung_ids)]
    if holes:
        raise SystemExit(
            "--rungs %s has a GAP at %s.  A ladder is a SEQUENCE of refinements: the\n"
            "registered (d1)/(d2) reading is a statement about consecutive mesh steps, and a\n"
            "hole is a jump, not a step.  Name every rung from %d to %d, or trim the\n"
            "selection to a contiguous run.  Nothing was created and nothing was run."
            % (",".join(str(v) for v in rung_ids), ",".join(str(v) for v in holes),
               rung_ids[0], rung_ids[-1]))
    resume_note = None
    ctrl_dir = None
    if rung_ids[0] != 0:
        if not a.resume:
            raise SystemExit(
                "--rungs %s does not start at rung 0: the ladder would be UNANCHORED.\n"
                "  Rung 0 is the CONTROL -- the banked mesh, the gate that says these runs come\n"
                "  off the same pipeline as the registered capture.  A verdict scored against no\n"
                "  control is not a verdict, so the selection is refused before any rung runs.\n"
                "  Either include rung 0 in the same pass:\n"
                "      ./high_res_run.sh --rungs 0,%s\n"
                "  or validate the rung-0 capture already on disk and resume above it:\n"
                "      ./high_res_run.sh --rungs %s --resume\n"
                "  Nothing was created and nothing was run."
                % (",".join(str(v) for v in rung_ids),
                   ",".join(str(v) for v in rung_ids),
                   ",".join(str(v) for v in rung_ids)))
        ctrl_dir = os.path.join(out_root, rung_dirname(RUNGS[0]))
        vok, resume_note, vwhy = validate_control_capture(ctrl_dir)
        if not vok:
            raise SystemExit(
                "--resume REFUSED: the rung-0 capture in\n"
                "  %s\n"
                "failed validation: %s.\n"
                "  --resume exists to CARRY a control forward, not to assume one.  Nothing was\n"
                "  run: including rung 0 in this pass is the other way to have a control."
                % (ctrl_dir, vwhy))

    print(PREREG)

    if a.dry_run:
        print_plan(sel, out_root, CONTROL_SECONDS)
        print("")
        print("RUN THIS: tools/host/sparse-probe/high_res_run.sh")
        print("DONE")
        return 0

    if not os.path.exists(AUDIT):
        raise SystemExit("audit not found: %s" % AUDIT)

    print("=" * 100)
    print("high_res_run.py -- joint mesh-refinement ladder, %d rung(s): %s" %
          (len(sel), ",".join(str(r["rung"]) for r in sel)))
    print("=" * 100)
    print("repo       : %s" % REPO)
    print("audit      : %s" % AUDIT)
    print("python     : %s" % sys.version.split()[0])
    print("out root   : %s" % out_root)
    print("max peak   : %.1f GB (a rung above it is SKIPPED and reported, never shrunk to fit)" % a.max_gb)
    print("timeout    : %s" % ("none" if not a.timeout else "%.0f s per rung" % a.timeout))
    print("control    : %s" % ("rung 0 from a PREVIOUS pass (--resume, validated against the"
                               " control gate on disk)"
                               if resume_note is not None else "rung 0 runs in this pass"))
    print("")

    os.makedirs(out_root, exist_ok=True)
    results = []
    base_seconds = CONTROL_SECONDS
    control_fault = None

    if resume_note is not None:
        # the control is a PREVIOUS pass's rung-0 capture, validated above.  It enters
        # ``results`` as a rung-0 entry carrying data but NO ``run``: that absence is how
        # rule_block reads its provenance, and it is labelled as such in every block.
        c0 = mesh_counts(RUNGS[0]["strip"], RUNGS[0]["yair"], RUNGS[0]["z"])
        results.append({"rung": RUNGS[0], "counts": c0, "data": read_rung_npz(ctrl_dir),
                        "run": None, "parsed": None,
                        "skipped": "not run in this pass: control validated from a previous"
                                   " pass (%s)" % ctrl_dir})
        print("control    : rung 0 is a PREVIOUS pass's capture, validated now -- not re-run")
        print("  " + resume_note.replace("\n", "\n  "))

    for r in sel:
        c = mesh_counts(r["strip"], r["yair"], r["z"])
        d = os.path.join(out_root, rung_dirname(r))
        if c["peak_gb"] > a.max_gb:
            print("SKIP  rung %d: projected peak %.2f GB > --max-gb %.1f.  Reported, not shrunk."
                  % (r["rung"], c["peak_gb"], a.max_gb))
            results.append({"rung": r, "counts": c, "data": None, "run": None,
                            "parsed": None, "skipped": "peak %.2f GB > %.1f GB" %
                            (c["peak_gb"], a.max_gb)})
            continue
        if os.path.isdir(d) and os.listdir(d) and not a.force:
            raise SystemExit(
                "output directory is not empty: %s\n"
                "  a rung's captures are evidence: they are not overwritten by accident.\n"
                "  move it aside, or pass --force to reuse it." % d)
        os.makedirs(d, exist_ok=True)
        env = build_env(r, d, c["free_e"])
        with open(os.path.join(d, "env.json"), "w", encoding="utf-8") as fh:
            json.dump({k: env[k] for k in sorted(env) if k.startswith(("C1_", "OMP_", "OPENBLAS", "MKL"))},
                      fh, indent=2, sort_keys=True)
        run = run_one(r, d, env, a.timeout, os.path.join(d, "run.log"))
        parsed = parse_log(run["lines"])
        data = read_rung_npz(d)
        results.append({"rung": r, "counts": c, "data": data, "run": run,
                        "parsed": parsed, "skipped": None})

        # the declared rung arithmetic, checked against the mesh that was actually built
        badm = check_mesh_arithmetic(r, c, data)
        if badm:
            print("   MESH ARITHMETIC MISMATCH (rung %d): %s" % (r["rung"], "; ".join(badm)))
            print("   the rung's declared strip/yair/z and the built mesh disagree; no number")
            print("   from this rung is reported as if it were on the declared mesh.")
        elif data is not None:
            print("   mesh arithmetic OK: free_e %d = n_edges %d - n_pec %d (recomputed from"
                  " strip=%d yair=%d z=%s)" % (data["free_e"], c["edges"], c["n_pec"],
                                               r["strip"], r["yair"],
                                               ",".join(str(v) for v in r["z"])))

        if r["rung"] == 0:
            ok_gate, rel, gate_detail = control_gate(data)
            ok = ok_gate and not badm
            print("== rung 0 CONTROL: R_extracted=%s (relative %.3e, gate %.0e) "
                  "n_eligible=%s (gate 1) -> %s"
                  % ((data["R_extracted"] if data else "n/a"), rel, CONTROL_RTOL,
                     (data["n_eligible"] if data else "n/a"),
                     "PASSED" if ok else "FAILED"))
            if data:
                print("   columns (DIAGNOSTIC ONLY, not part of the gate): identified_col=%d "
                      "chosen_col=%d bank_col=%d eligible=%s"
                      % (data["identified_col"], data["chosen_col"], data["bank_col"],
                         data["eligible_cols"]))
            if not ok:
                control_fault = (
                    "rung 0 did not pass the control gate: R_extracted=%s vs registered %r "
                    "(relative %.3e, gate %.0e), n_eligible=%s (gate: exactly 1) and mesh "
                    "arithmetic %s.  Column indices are not part of the gate."
                    % ((data["R_extracted"] if data else None), R_REGISTERED, rel, CONTROL_RTOL,
                       (data["n_eligible"] if data else None),
                       ("OK" if not badm else "MISMATCH [" + "; ".join(badm) + "]")))
                print("   HARNESS FAULT -- stopping.  The banked control is the anchor of the")
                print("   whole ladder; a rung scored against a failed control measures the")
                print("   harness, not the physics.  No later rung is run and nothing is patched")
                print("   here to make it agree.")
                break
            if data and data["free_e"] == CONTROL_FREE_E and run["wall"] > 0:
                base_seconds = run["wall"]
                print("   time base recalibrated from the control: %.1f s (was %.1f s)"
                      % (base_seconds, CONTROL_SECONDS))
                for rr in sel:
                    if rr["rung"] > 0:
                        cc = mesh_counts(rr["strip"], rr["yair"], rr["z"])
                        print("   revised estimate rung %d: %.0f s" % (rr["rung"], est_seconds(cc["free_e"], base_seconds)))
        if run["timed_out"]:
            print("   TIMED OUT at %.0f s -- rung abandoned, ladder continues." % a.timeout)

    lines = [PREREG]
    for e in results:
        if e["run"] is None:
            lines.append("-" * 100)
            lines.append("RUNG %d/%d   %s   SKIPPED -- %s" % (
                e["rung"]["rung"], len(RUNGS) - 1, e["rung"]["role"], e["skipped"]))
            continue
        lines.append(per_rung_block(e["rung"], e["counts"], e["run"], e["data"], e["parsed"]))
    lines.append(cross_rung_block(results))
    lines.append(stability_block(results))
    lines.append(fit_block(results))
    # a verdict needs a control under it, and there are two ways to have none: the
    # in-pass gate FAILED, or there was no rung-0 capture at all.
    verdict_blocker = None
    verdict_blocker_detail = None
    if control_fault:
        verdict_blocker = "control failed"
        verdict_blocker_detail = control_fault
    anchored = any(e["rung"]["rung"] == 0 and e["data"] is not None for e in results)
    no_verdict = (verdict_blocker is not None) or (not anchored)

    lines.append(rule_block(results, verdict_blocker, verdict_blocker_detail))
    if control_fault:
        lines.append("=" * 100)
        lines.append("STOPPED: " + control_fault)
        lines.append("=" * 100)
    if no_verdict:
        lines.append("=" * 100)
        lines.append("NO VERDICT PRODUCED: %s." %
                     ("the in-pass control gate FAILED" if control_fault else
                      "the ladder is UNANCHORED -- no rung-0 control in this pass"))
        lines.append("T4_amp: NOT EVALUATED (%s)" % (verdict_blocker or "unanchored"))
        lines.append("  The bar |Q - 1| <= 0.10 was NOT touched: no Q was computed and no band")
        lines.append("  comparison was made, so nothing in this report is a T4_amp reading.  The")
        lines.append("  bar is not scored against a control that does not exist, and it is not")
        lines.append("  softened to fit the rungs that did run.")
        if control_fault:
            lines.append("  remedy: a failed control is a HARNESS fault, not physics.  Re-run")
            lines.append("  rung 0 (--force, or move its directory aside) and find out why the")
            lines.append("  control moved before any rung of this ladder is read.")
        else:
            lines.append("  remedy: run rung 0 in the same pass --")
            lines.append("             ./high_res_run.sh --rungs 0,%s"
                         % ",".join(str(r["rung"]) for r in sel))
            lines.append("          or validate a rung-0 capture already on disk and resume:")
            lines.append("             ./high_res_run.sh --rungs %s --resume"
                         % ",".join(str(r["rung"]) for r in sel))
        lines.append("=" * 100)
    lines.append("")
    lines.append("RUN THIS: tools/host/sparse-probe/high_res_run.sh")
    text = "\n".join(lines)

    print("")
    print(text)
    summary = os.path.join(out_root, "summary_HIGHRES.txt")
    with open(summary, "w", encoding="utf-8") as fh:
        fh.write(text + "\n")
    print("")
    print("summary written: %s" % summary)
    if no_verdict:
        print("DONE (no verdict)")
        return 3
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
