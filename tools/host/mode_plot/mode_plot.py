#!/usr/bin/env python3
"""mode_plot.py -- the C2b picture: analytic plane basis vs the *extracted*
mode field, drawn on an EXPLICIT metric.

WHY THIS FILE CHANGED (D22-T3)
------------------------------
The first version drew one pairing only: the analytic *vertical* reference
``A_ez`` against ``e_z``, where ``e_z`` was the LONGITUDINAL reconstruction
``-interp(beta * z_free)`` (``c1_audit.py:513-516``).  Those are two different
physical components, so the correlation the picture illustrated
(``|corr_e_z|`` = 0.119 PMC / 0.147 PEC) was a component mis-pairing, not a
shape test.  The same-component metric is ``corr_ez_vv`` (0.935 / 0.937):
component 1 of the *transverse* field sampled on the very lattice ``A_ez`` lives
on.  The audit now banks all three numbers --

    corr_ey                          A_ey (width)      vs e_y     (width)
    corr_ez_vv                       A_ez (vertical)   vs e_z_vv  (VERTICAL)
    corr_ez_superseded_longitudinal  A_ez (vertical)   vs e_z     (LONGITUDINAL)

-- and the npz key ``corr_ez`` is a *compatibility alias* for the superseded
value (``c1_audit.py:610-613``).  This script never reads that alias for
anything but a printed cross-check; the metric is chosen on the command line::

    --metric corrected   same-component: e_z_vv and e_y   [the report figure]
    --metric before      the superseded mis-pairing       [the teaching figure]
    --metric both        draw both, identical axes and colour limits (DEFAULT)

No code path substitutes one metric for another silently: every extracted panel
prints BOTH numbers in its own title -- the one it plots and the one it does not
-- and the two figures share panels, axes and colour limits by construction (see
COLOUR / SCALES).

WHAT THIS FILE IS
-----------------
A reader + renderer, deliberately small: it reads the two banked spectra,
reconstructs the extracted fields, and draws, per run,

    analytic e_z  |  extracted e_z (metric-dependent)  |  difference
    analytic e_y  |  extracted e_y                     |  difference

for the two runs that exist on disk:

    column 1   PMC / open top    tools/host/c1-audit/out/c1_spectrum.npz      QZ col 738
    column 2   PEC / closed box  tools/host/c1-audit/out/pecbox_spectrum.npz  QZ col 699

Nothing is solved here.  Every number plotted is either read from an npz or
recomputed from it by the *same* arithmetic the audit used (see below).

DATA CONTRACT (both npz files have identical keys -- ONE call site writes them)
-----------------------------------------------------------------------------
np.savez() in tools/host/c1-audit/c1_audit.py:600-625 (NPZ_PATH, c1_audit.py:147);
pecbox_spectrum.npz is the same call with the path redirected by
tools/host/c1-audit/pecbox_variant.py:291-326 (_RedirectWrites; _REDIRECT maps
NPZ_OWN -> NPZ_BOX, pecbox_variant.py:107-111).  Keys used here:

    xs (31,), zs (17,)        mesh node axes in metres; xs is the transverse
                              coordinate y (0 .. 20 mm), zs is height z
                              (0 .. 7.6 mm).  These alone rebuild the mesh.
    n_edges, n_nodes          the rebuilt mesh must match them exactly.
    free_e, free_n            the free DOF index arrays: the PEC masks are NOT
                              re-derived (that would need the geojson and the
                              BOUNDARIES tuples again).
    k0, f0                    scalar wavenumber (164.179... rad/m) and the
                              frequency it came from (f0 is carried into the
                              Mode2D field carrier; e_at does not use it).
    lam (n_qz,), complex      QZ eigenvalues; lam[j] IS beta^2 (pencil
                              A x = beta^2 B x, emfit/mode2d.py:1003-1005).
    vecs_real (n_free, n_qz)  real part of EVERY eigenvector; column index == QZ
                              column number.  This is e_t on the free edges.
    j (n_prop,)               the QZ column indices of the propagating rows.
    beta_sq, eps_eff, residual (n_prop,)      per-mode scalars (signed/real).
    corr_ey, corr_ez_vv, corr_ez_superseded_longitudinal (n_prop,)
                              per-mode metrics, signed.  corr_ez is the
                              superseded alias -- read only to assert it agrees.
    A_ey (200, 77)            THE ANALYTIC e_y, banked (c1_audit.py:420-423).
    A_ez (201, 76)            THE ANALYTIC e_z, banked.  Index [y, z-mid]:
                              axis 0 is the transverse coordinate on the node
                              lattice (0 .. 20 mm), axis 1 is the vertical
                              mid-cell lattice (0.05 .. 7.55 mm).  A_ey is the
                              transpose case: [y-mid, z-node].

RECONSTRUCTION OF THE EXTRACTED FIELDS (copied, not invented)
-------------------------------------------------------------
    blocks   m1, m_eps, c, k_zz, m_zz = m2.assemble_mixed(mesh, eps_r=eps_of)
             h  = k_zz[free_n][:, free_n] - k0^2 m_zz[free_n][:, free_n]
             cf = c[free_e][:, free_n];  lu = splu(h)
                                                     c1_audit.py:390-393
    column   x = vecs_real[:, col]; x /= ||x||         c1_audit.py:479-484
    e_t      e_t = zeros(n_edges); e_t[free_e] = x     c1_audit.py:487-488
    longitudinal (SUPERSEDED pairing only)
             z_free = lu.solve(cf.T @ x); e_z_node[free_n] = beta * z_free
                                                     c1_audit.py:491-493
             e_z_mag = itp((ZS, XS), e_z_node.reshape(nz, nx))(_ez_pts)
             e_z_superseded = -e_z_mag.reshape(NYN, NZN-1)
                                                     c1_audit.py:513-516
    same-component (CORRECTED pairing)
             e_y     = Mode2D.e_at(_ey_pts ).reshape(NYN-1, NZN  )[:, :, 0] * CELL
             e_z_vv  = Mode2D.e_at(_ezc_pts).reshape(NYN,   NZN-1)[:, :, 1] * CELL
                                                     c1_audit.py:503-511
             (_ey_pts is (y-mid, z-node); _ezc_pts is (y-node, z-mid) in e_at's
              (x, y) = (XS, ZS) order -- _ez_pts is the same lattice in (z, y)
              order for the RegularGridInterpolator and must NOT be handed to
              e_at: c1_audit.py:410-416.)
    eps      eps_of(p) = where(p[:,1] <= h + 1e-12, eps_r, 1)   c1_audit.py:283
             h, eps_r from the same geojson the audit reads.  m_zz carries eps_r,
             so this is not optional.

The Mode2D carrier is built the way c1_audit.py:495-502 builds it (a frozen
dataclass with no __post_init__, used purely to carry `e_t` + `mesh`).

SELF-CHECK (the reason a blind-written run can still be trusted)
---------------------------------------------------------------
After the reconstruction, all THREE statistics are recomputed and compared with
the banked values for that column, and the banked eps_eff is compared with the
declared constant.  A mismatch raises -- the script never plots a field it could
not reproduce.  Expected values, from the runs' own tables:

    c1_table.txt:16      col 738  eps_eff 3.6295122080769704
                                  corr_ey  +0.9207707848111419
                                  corr_ez_vv +0.9352867303487647
                                  corr_ez_superseded +0.11916043239134176
    pecbox_table.txt:16  col 699  eps_eff 3.606094999644309
                                  corr_ey  +0.9123430448112094
                                  corr_ez_vv +0.9369297170797807
                                  corr_ez_superseded +0.1472914469446296

GAUGE (sign)
------------
A generalised eigenvector is defined up to an arbitrary scalar and LAPACK fixes
no sign, so column 738 may come back as +x or -x (c1_audit.py docstring, "Why the
criterion uses |corr|").  For the picture only, EACH extracted field is
multiplied by the sign of ITS OWN correlation, so it lands in the same lobe as
the reference.  Nothing is *compared* on a sign: every metric printed is signed
and both fields are RMS-normalised, so a sign flip changes no magnitude.

COLOUR / SCALES -- AND WHY THE TWO FIGURES ARE COMPARABLE
---------------------------------------------------------
Each field is RMS-normalised (divided by its own root-mean-square over its own
lattice), so the colour scale is in units of the field's own RMS.  The extent
drawn is the FULL geometric domain in every panel (y 0..20 mm, z 0..7.6 mm plus
a half cell), not the per-lattice sub-range, so the e_z row (node lattice in y,
mid-cell in z) and the e_y row (the transpose of that) sit on identical axes.

Per-panel colour limits are computed ONCE as the maximum over BOTH metrics of
|field| in that panel slot, then handed unchanged to both figures.  Consequences,
stated because they are deliberate:

  * no panel is ever clipped;
  * the corrected figure's difference rows can look near-blank next to the
    before figure's -- that IS the result, not a rendering fault (each
    difference panel prints its own max|delta| beside the shared vmax);
  * comparing the two figures panel-by-panel is legitimate: same panels, same
    axes, same limits.

READ THIS FILE'S OUTPUT
-----------------------
It writes PDF *and* PNG next to each other.  Defaults:

    docs/report/figures/c2b_mode_shape_corrected.pdf   (corrected metric)
    docs/design/mispaired_metric_before.pdf            (superseded metric)
    docs/design/c2b_shapes.pdf                         (corrected metric; the
        pre-existing C2b artifact is refreshed so it can no longer show the
        mis-pairing -- disable with --no-c2b)

Read-only w.r.t. the data: it never writes into tools/host/c1-audit/out/ and
never touches emfit/.

Run:
    tools/host/mode_plot/run.sh
or directly:
    cd <repo> && python3 -u tools/host/mode_plot/mode_plot.py [--metric both]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time

import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.sparse.linalg import splu

# ---------------------------------------------------------------------------
# repo layout: this file lives at <repo>/tools/host/mode_plot/mode_plot.py,
# three levels below the root.  Never count ".." -- ask tools/host/_bootstrap.py
# (or take C1_REPO from run.sh); the traps are in that module's docstring.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))

#: captured before bootstrap(), which writes REPO into the environment
_REPO_ENV = (os.environ.get("REPO", "").strip()
             or os.environ.get("C1_REPO", "").strip())

sys.path.insert(0, os.path.join(HERE, os.pardir))
from _bootstrap import bootstrap  # noqa: E402

REPO = bootstrap(start=HERE)

import matplotlib  # noqa: E402

matplotlib.use("Agg")                     # headless: run.sh is a host batch job
import matplotlib.pyplot as plt           # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

import emfit.mode2d as m2                 # noqa: E402  (assemble_mixed, mesh only)

# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------
GEOJSON = os.path.join(REPO, ".scratch", "tol", "logs", "TOLFLUX.json")
C1_OUT = os.path.join(REPO, "tools", "host", "c1-audit", "out")
DESIGN = os.path.join(REPO, "docs", "design")
REPORT_FIG = os.path.join(REPO, "docs", "report", "figures")

#: default output of each metric.  The corrected figure is the report deliverable;
#: the before figure is a teaching artifact; the c2b path is the pre-existing
#: artifact, refreshed with the corrected metric so it cannot mislead.
OUT_CORRECTED = os.path.join(REPORT_FIG, "c2b_mode_shape_corrected.pdf")
OUT_BEFORE = os.path.join(DESIGN, "mispaired_metric_before.pdf")
OUT_C2B = os.path.join(DESIGN, "c2b_shapes.pdf")

# ---------------------------------------------------------------------------
# the two banked runs, and the column each one's identified mode sits in
#
# `col` is the QZ column; every other number is what the run itself banked, kept
# ONLY to locate the column and to gate the reconstruction (see SELF-CHECK).
# Sources, verbatim:
#   PMC: out/c1_table.txt:16, out/c1_spectrum.npz
#   PEC: out/pecbox_table.txt:16, out/pecbox_spectrum.npz
# ---------------------------------------------------------------------------
RUNS = (
    dict(key="pmc",
         label="PMC / open top",
         npz="c1_spectrum.npz",
         col=738,
         eps_eff=3.6295122080769704,
         beta_sq=97833.0578509992,
         corr_ey=+0.9207707848111419,
         corr_ez_vv=+0.9352867303487647,
         corr_ez_sup=+0.11916043239134176,
         residual=4.034898662672129e-16),
    dict(key="pec",
         label="PEC / closed box",
         npz="pecbox_spectrum.npz",
         col=699,
         eps_eff=3.606094999644309,
         beta_sq=97201.84986051408,
         corr_ey=+0.9123430448112094,
         corr_ez_vv=+0.9369297170797807,
         corr_ez_sup=+0.1472914469446296,
         residual=1.833218921941274e-15),
)

#: npz keys this script needs; a missing one is named in the error, never zeros
REQUIRED_KEYS = ("xs", "zs", "n_edges", "n_nodes", "free_e", "free_n", "k0",
                 "f0", "lam", "vecs_real", "j", "beta_sq", "eps_eff",
                 "residual", "corr_ey", "corr_ez_vv",
                 "corr_ez_superseded_longitudinal", "A_ey", "A_ez")

#: the two metrics, as data: which banked key is plotted, which field, and how to
#: name both in a panel title.  Nothing below may look a metric up by guesswork.
METRICS = {
    "corrected": dict(
        key="corrected",
        plotted="corr_ez_vv",
        not_plotted="corr_ez_superseded",
        field="e_z_vv",
        row="A_ez  vs  e_z_vv",
        why="component 1 of e_t on the A_ez lattice: vertical vs VERTICAL",
        legacy=False),
    "before": dict(
        key="before",
        plotted="corr_ez_superseded",
        not_plotted="corr_ez_vv",
        field="e_z_sup",
        row="A_ez  vs  e_z_superseded",
        why="-interp(beta*z_free): the LONGITUDINAL field, a different component",
        legacy=True),
}

#: |measured - banked| tolerance on the three correlations (they are O(1))
CORR_TOL = 1e-6
#: relative tolerance on eps_eff (catches a transposed constant: 0.65 % >> 1e-6)
EPS_RTOL = 1e-6
#: relative tolerance on beta^2 (the table prints 8 significant digits)
BSQ_RTOL = 1e-6

T0 = time.time()


def say(*a) -> None:
    """One flushed line (run.sh tees stdout+stderr into out/run.log)."""
    print(" ".join(str(x) for x in a), flush=True)


def corr(a, b) -> float:
    """Normalised inner product, NaN on shape mismatch / zero norm.

    Identical to the audit's statistic (tools/corr_ez_101_20.py:118-124, used at
    c1_audit.py:518-522), which is what makes the self-check below meaningful.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.shape != b.shape:
        return float("nan")
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return float("nan")
    return float(np.sum(a * b) / (na * nb))


def rms(f) -> float:
    f = np.asarray(f, dtype=float)
    return float(np.sqrt(np.mean(np.square(f))))


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# reconstruction of one run
# ---------------------------------------------------------------------------
def reconstruct_run(spec: dict, geo: dict) -> dict:
    """Rebuild every extracted field of `spec`; return the two references too."""
    path = os.path.join(C1_OUT, spec["npz"])
    _check(os.path.exists(path),
           f"{path} does not exist.\n"
           f"  This script PLOTS banked results; it never creates them.\n"
           f"  Run tools/host/c1-audit/run.sh and tools/host/c1-audit/pecbox_variant.py "
           f"first (both write into {C1_OUT}).")

    d = np.load(path)
    missing = [k for k in REQUIRED_KEYS if k not in d.files]
    _check(not missing,
           f"{path} is missing key(s) {missing}.\n"
           f"  keys present: {list(d.files)}\n"
           f"  the file was not written by the c1_audit.py call site this script "
           f"expects (c1_audit.py:600-625).")

    HSUB = float(geo["h"])
    EPS_R = float(geo["eps_r"])
    XS = np.asarray(d["xs"], dtype=float)
    ZS = np.asarray(d["zs"], dtype=float)
    K0 = float(d["k0"])
    F0 = float(d["f0"])
    A_ez = np.asarray(d["A_ez"], dtype=float)
    A_ey = np.asarray(d["A_ey"], dtype=float)
    free_e = np.asarray(d["free_e"], dtype=np.int64)
    free_n = np.asarray(d["free_n"], dtype=np.int64)
    lam = np.asarray(d["lam"])
    vecs = np.asarray(d["vecs_real"], dtype=float)
    jj = np.asarray(d["j"], dtype=np.int64)

    col = int(spec["col"])
    where = np.flatnonzero(jj == col)
    _check(where.size == 1,
           f"{path}: QZ column {col} is not among the propagating columns "
           f"j={jj.tolist()}.\n"
           f"  Either the file is from a different run, or the identified column of "
           f"this run has changed -- re-read out/c1_table.txt (or "
           f"out/pecbox_table.txt) and update RUNS in {__file__}.")
    row = int(where[0])

    # ---- gate 0: the banked numbers are the ones this file was written with ----
    eps_file = float(np.asarray(d["eps_eff"], dtype=float)[row])
    cy_file = float(np.asarray(d["corr_ey"], dtype=float)[row])
    cvv_file = float(np.asarray(d["corr_ez_vv"], dtype=float)[row])
    csup_file = float(np.asarray(d["corr_ez_superseded_longitudinal"],
                                 dtype=float)[row])
    resid_file = float(np.asarray(d["residual"], dtype=float)[row])
    bsq = float(np.real(lam[col]))
    _check(abs(eps_file - spec["eps_eff"]) <= EPS_RTOL * abs(spec["eps_eff"]),
           f"{path}: eps_eff in the file is {eps_file!r} but RUNS expects "
           f"{spec['eps_eff']!r} "
           f"(rel {abs(eps_file - spec['eps_eff']) / abs(spec['eps_eff']):.2e}).\n"
           f"  The column/eps_eff pair in RUNS is wrong -- fix the constant, do not "
           f"loosen the tolerance.")
    _check(abs(cy_file - spec["corr_ey"]) <= CORR_TOL,
           f"{path}: corr_ey in the file is {cy_file!r} but RUNS expects "
           f"{spec['corr_ey']!r}.")
    _check(abs(cvv_file - spec["corr_ez_vv"]) <= CORR_TOL,
           f"{path}: corr_ez_vv in the file is {cvv_file!r} but RUNS expects "
           f"{spec['corr_ez_vv']!r}.")
    _check(abs(csup_file - spec["corr_ez_sup"]) <= CORR_TOL,
           f"{path}: corr_ez_superseded_longitudinal in the file is {csup_file!r} "
           f"but RUNS expects {spec['corr_ez_sup']!r}.")
    _check(abs(float(spec["beta_sq"]) - bsq) <= BSQ_RTOL * abs(bsq),
           f"{path}: beta^2 at column {col} is {bsq!r} but RUNS prints "
           f"{spec['beta_sq']!r}.")
    _check(lam.size == free_e.size and vecs.shape[0] == free_e.size,
           f"{path}: lam {lam.shape} / vecs_real {vecs.shape} disagree with "
           f"free_e ({free_e.size},).")
    _check(col < vecs.shape[1],
           f"{path}: column {col} is outside vecs_real ({vecs.shape}).")

    # the compat alias must be the superseded value -- checked, never plotted
    if "corr_ez" in d.files:
        alias = float(np.asarray(d["corr_ez"], dtype=float)[row])
        _check(abs(alias - csup_file) <= CORR_TOL,
               f"{path}: the compatibility key corr_ez ({alias!r}) is not the "
               f"superseded value ({csup_file!r}); the alias contract in "
               f"c1_audit.py:610-613 has changed and this script's "
               f"'corr_ez is NOT a shape metric' claim would be wrong.")
        say(f"  alias    : npz key corr_ez = {alias:+.15f} == "
            f"corr_ez_superseded (compat alias, never plotted)")

    # ---- mesh (rebuilt from the file's own axes, never re-derived from geojson)
    mesh = m2.structured_mesh(XS, ZS)
    _check(int(mesh.n_edges) == int(d["n_edges"])
           and int(mesh.n_nodes) == int(d["n_nodes"]),
           f"{path}: rebuilt mesh has {mesh.n_edges} edges / {mesh.n_nodes} nodes, "
           f"the file banks {int(d['n_edges'])} / {int(d['n_nodes'])}.\n"
           f"  The xs/zs in the file are not the axes this file was written with.")
    _check(np.any(ZS == HSUB),
           f"{path}: the substrate interface h={HSUB!r} is not a node of zs "
           f"(zs={ZS.tolist()}) -- eps_of would be wrong for every element.")

    def eps_of(p):
        # c1_audit.py:283-284, verbatim
        return np.where(p[:, 1] <= HSUB + 1e-12, EPS_R, 1.0)

    # ---- blocks + one LU (c1_audit.py:390-393) ------------------------------
    _t = time.time()
    m1, m_eps_m, c, k_zz, m_zz = m2.assemble_mixed(mesh, eps_r=eps_of)
    h_blk = (k_zz[free_n][:, free_n] - K0 * K0 * m_zz[free_n][:, free_n]).tocsc()
    c_f = c[free_e][:, free_n].tocsc()
    lu = splu(h_blk)
    say(f"  blocks   : h={list(h_blk.shape)} nnz={h_blk.nnz} "
        f"c_f={list(c_f.shape)} nnz={c_f.nnz} ({time.time() - _t:.2f} s)")

    # ---- the column (c1_audit.py:479-493) -----------------------------------
    x = np.real(vecs[:, col])
    nxv = float(np.linalg.norm(x))
    _check(nxv > 0.0, f"{path}: eigenvector column {col} is identically zero.")
    x = x / nxv
    beta = float(np.sqrt(bsq))
    z_free = np.asarray(lu.solve(np.asarray(c_f.T @ x).ravel()),
                        dtype=float).ravel()
    e_z_node = np.zeros(mesh.n_nodes, dtype=float)
    e_z_node[free_n] = beta * z_free

    # ---- node ordering guard (c1_audit.py:304-314, :418-432) ----------------
    _nx, _nz = int(XS.size), int(ZS.size)
    ez_grid = np.asarray(e_z_node, dtype=float).reshape(_nz, _nx)
    probe = RegularGridInterpolator(
        (ZS, XS), np.arange(_nx * _nz, dtype=float).reshape(_nz, _nx),
        bounds_error=True)
    for i in (0, _nx // 2, _nx - 1):
        for j in (0, _nz // 2, _nz - 1):
            got = float(np.asarray(probe([[ZS[j], XS[i]]])).ravel()[0])
            _check(int(got) == j * _nx + i,
                   f"node ordering guard FAILED at (i={i}, j={j}): interpolated "
                   f"index {got} != {j * _nx + i} -- the (nz, nx) reshape and the "
                   f"(ZS, XS) interpolator do not agree; every field below would "
                   f"be transposed.")

    # ---- plane lattices (c1_audit.py:400-416, :490-493) --------------------
    NYN = int(A_ez.shape[0])
    NZN = int(A_ez.shape[1]) + 1               # (201, 76) <-> NYN x (NZN - 1)
    CELL = float(geo["cell"])                  # c1_audit.py:394-397 (0.1 mm)
    cell_h = float(XS[-1]) / (NYN - 1)
    cell_v = float(ZS[-1]) / (NZN - 1)
    _check(abs(cell_h - CELL) <= 1e-9 * CELL
           and abs(cell_v - CELL) <= 1e-9 * CELL,
           f"{path}: the plane lattice is not the geojson cell (y {cell_h!r} / "
           f"z {cell_v!r} vs cell {CELL!r}); A_ez shape {A_ez.shape} does not "
           f"match xs[-1]={XS[-1]!r} / zs[-1]={ZS[-1]!r} on a CELL lattice.")
    _check(A_ey.shape == (NYN - 1, NZN),
           f"{path}: A_ey {A_ey.shape} != the e_y lattice {(NYN - 1, NZN)} "
           f"implied by A_ez {A_ez.shape}.")

    yn_node = np.arange(NYN) * cell_h             # transverse nodes, 0 .. 20 mm
    zn_node = np.arange(NZN) * cell_v             # vertical nodes,   0 .. 7.6 mm
    yc_mid = (np.arange(NYN - 1) + 0.5) * cell_h  # transverse mid-cells
    zc_mid = (np.arange(NZN - 1) + 0.5) * cell_v  # vertical mid-cells

    # e_y lattice: (ny-1, nz+1); e_z lattice: (ny+1, nz-1).  c1_audit.py:407-416.
    yy, zz = np.meshgrid(yc_mid, zn_node, indexing="ij")
    iyy, izz = np.meshgrid(yn_node, zc_mid, indexing="ij")
    _ey_pts = np.stack([yy.ravel(), zz.ravel()], axis=1)     # e_at (x, y) order
    _ezc_pts = np.stack([iyy.ravel(), izz.ravel()], axis=1)  # e_at (x, y) order
    _ez_pts = np.stack([izz.ravel(), iyy.ravel()], axis=1)   # (z, y) interpolator

    # ---- the transverse field carrier (c1_audit.py:495-511) ----------------
    e_t = np.zeros(mesh.n_edges, dtype=float)
    e_t[free_e] = x
    MODE = m2.Mode2D(
        freq=F0, k0=K0, beta=beta, beta_sq=bsq,
        eps_eff=eps_file, residual=resid_file,
        candidates=tuple(), curl_ratio=None, chosen=col, sigma=1.0,
        n_dof=int(free_e.size), n_pec=int(mesh.n_edges - free_e.size),
        e_t=e_t, mesh=mesh, e_z=None,
    )
    _t = time.time()
    E_t = MODE.e_at(_ey_pts).reshape(NYN - 1, NZN, 2)
    e_y = E_t[:, :, 0] * CELL          # *CELL as in s10118_basis.py:314; corr is
                                       # invariant to it, kept for faithfulness
    E_tz = MODE.e_at(_ezc_pts).reshape(NYN, NZN - 1, 2)
    e_z_vv = E_tz[:, :, 1] * CELL      # SAME COMPONENT as A_ez: vertical
    say(f"  e_at     : {_ey_pts.shape[0]} + {_ezc_pts.shape[0]} points "
        f"({time.time() - _t:.2f} s)")

    itp = RegularGridInterpolator((ZS, XS), ez_grid, bounds_error=True)
    e_z_mag = itp(_ez_pts).reshape(NYN, NZN - 1)
    e_z_sup = -e_z_mag                 # s10118_basis.py:369 (E: strip -> ground)

    # ---- gate 1: reproduce ALL THREE banked statistics ---------------------
    cy_mine = corr(A_ey, e_y)
    cvv_mine = corr(A_ez, e_z_vv)
    csup_mine = corr(A_ez, e_z_sup)
    for name, mine, banked in (
            ("corr_ey", cy_mine, cy_file),
            ("corr_ez_vv", cvv_mine, cvv_file),
            ("corr_ez_superseded", csup_mine, csup_file)):
        _check(np.isfinite(mine),
               f"{path}: reconstructed {name} is not finite -- a field has zero "
               f"norm or the shapes disagree (A_ez {A_ez.shape}, A_ey {A_ey.shape}, "
               f"e_z_vv {e_z_vv.shape}, e_y {e_y.shape}, e_z {e_z_sup.shape}).")
        _check(abs(mine - banked) <= CORR_TOL,
               f"{path}: reconstructed {name} = {mine!r} but the file banks "
               f"{banked!r} (delta {abs(mine - banked):.3e}).\n"
               f"  The reconstruction does not reproduce the audit, so this picture "
               f"would show a field the audit never scored.  Do NOT loosen this "
               f"tolerance -- find the difference (eps_of? k0? column? the lattice "
               f"order of _ezc_pts vs _ez_pts? the sign of the interpolated field?) "
               f"first.")

    say(f"  column   : QZ col {col}  beta={beta:.6f}  beta^2={bsq:.7e}  "
        f"eps_eff={eps_file!r}  residual={resid_file:.2e}")
    say(f"  corr     : corr_ey={cy_file:+.15f} (mine {cy_mine:+.15f})   "
        f"corr_ez_vv={cvv_file:+.15f} (mine {cvv_mine:+.15f})")
    say(f"             corr_ez_superseded={csup_file:+.15f} "
        f"(mine {csup_mine:+.15f})  [the mis-paired number]")
    say(f"  fields   : A_ez {A_ez.shape} rms={rms(A_ez):.6e}  "
        f"A_ey {A_ey.shape} rms={rms(A_ey):.6e}")
    say(f"             e_z_vv {e_z_vv.shape} rms={rms(e_z_vv):.6e}  "
        f"e_y {e_y.shape} rms={rms(e_y):.6e}  "
        f"e_z_sup {e_z_sup.shape} rms={rms(e_z_sup):.6e}")

    # ---- gauge fix + normalisation (picture only; no comparison uses the sign)
    def _unit(f, sgn, what):
        _check(sgn != 0.0, f"{path}: banked {what} is exactly 0 -- no gauge.")
        return sgn * np.asarray(f, dtype=float) / rms(f)

    A_ez_u = A_ez / rms(A_ez)
    A_ey_u = A_ey / rms(A_ey)
    E_vv_u = _unit(e_z_vv, float(np.sign(cvv_file)), "corr_ez_vv")
    E_sup_u = _unit(e_z_sup, float(np.sign(csup_file)),
                    "corr_ez_superseded_longitudinal")
    E_y_u = _unit(e_y, float(np.sign(cy_file)), "corr_ey")
    say(f"  gauge    : sign(corr_ez_vv)={np.sign(cvv_file):+.0f}  "
        f"sign(corr_ez_superseded)={np.sign(csup_file):+.0f}  "
        f"sign(corr_ey)={np.sign(cy_file):+.0f}")

    return dict(
        spec=spec, path=path, col=col, beta=beta, bsq=bsq,
        eps_eff=eps_file, residual=resid_file,
        corr_ey=cy_file, corr_ez_vv=cvv_file, corr_ez_sup=csup_file,
        corr_ey_mine=cy_mine, corr_ez_vv_mine=cvv_mine,
        corr_ez_sup_mine=csup_mine,
        A_ez_raw=A_ez, A_ey_raw=A_ey, e_z_vv_raw=e_z_vv, e_y_raw=e_y,
        e_z_sup_raw=e_z_sup,
        y_ez=yn_node, z_ez=zc_mid, y_ey=yc_mid, z_ey=zn_node,
        cell=cell_h, y_hi=float(XS[-1]), z_hi=float(ZS[-1]),
        viz=dict(
            A_ez=A_ez_u, A_ey=A_ey_u,
            E={"corrected": E_vv_u, "before": E_sup_u},
            D={"corrected": A_ez_u - E_vv_u, "before": A_ez_u - E_sup_u},
            E_ey=E_y_u, D_ey=A_ey_u - E_y_u,
        ),
    )


# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------
#: the six field rows, in drawing order.  Every figure has exactly these rows.
ROWS = (
    ("A_ez", "analytic"),
    ("E_ez", "extracted"),
    ("D_ez", "difference"),
    ("A_ey", "analytic"),
    ("E_ey", "extracted"),
    ("D_ey", "difference"),
)


def _slot_arrays(viz: dict, slot: str) -> list:
    """Every array that can occupy `slot` -- i.e. one per metric where relevant."""
    if slot == "E_ez":
        return list(viz["E"].values())
    if slot == "D_ez":
        return list(viz["D"].values())
    return [viz[slot]]


def _slot_field(viz: dict, slot: str, metric: str) -> np.ndarray:
    """The array `slot` shows in the figure for `metric`."""
    if slot == "E_ez":
        return viz["E"][metric]
    if slot == "D_ez":
        return viz["D"][metric]
    return viz[slot]


def colour_limits(cases: dict) -> dict:
    """Per (run, slot) vmax, taken over EVERY metric -- shared by both figures."""
    lim = {}
    for key, case in cases.items():
        for slot, _kind in ROWS:
            vals = [float(np.max(np.abs(f)))
                    for f in _slot_arrays(case["viz"], slot)]
            lim[(key, slot)] = max(vals)
    return lim


def _panel(ax, f, yc, zc, ext, title, vmax, contours=True, cmap="RdBu_r",
           tcolor="k"):
    """One signed scalar field on a FIXED extent with an EXTERNAL colour limit."""
    _check(np.all(np.isfinite(f)),
           f"panel '{title}': the field has non-finite entries -- refusing to "
           f"plot it (a NaN/Inf would be painted as a hole).")
    _check(vmax > 0.0,
           f"panel '{title}': the shared colour limit is zero -- refusing to plot "
           f"a blank panel (that would read as agreement).")
    ax.imshow(f.T, origin="lower", extent=ext, cmap=cmap, vmin=-vmax, vmax=+vmax,
              interpolation="nearest", zorder=1)
    if contours:
        own = float(np.max(np.abs(f)))
        levels = own * np.array([0.25, 0.50, 0.75])
        cs = ax.contour(yc * 1e3, zc * 1e3, np.abs(f).T, levels=levels,
                        colors="k", linewidths=0.45, zorder=3)
        if len(cs.levels):
            ax.clabel(cs, fmt="%.2f", fontsize=4.5)
    ax.set_title(title, fontsize=6.1, linespacing=1.3, color=tcolor)
    ax.tick_params(labelsize=6, labelbottom=False, labelleft=False)
    ax.set_aspect("equal")
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])


def _overlay(ax, HSUB, y0, y1):
    """Substrate interface (dashed), the strip (thick) and its two edges."""
    ax.axhline(HSUB * 1e3, color="k", lw=0.6, ls=(0, (4, 3)), zorder=4)
    ax.plot([y0 * 1e3, y1 * 1e3], [HSUB * 1e3, HSUB * 1e3], color="k", lw=2.2,
            solid_capstyle="butt", zorder=5)
    for ye in (y0, y1):
        ax.axvline(ye * 1e3, color="0.35", lw=0.5, ls=(0, (1, 2)), zorder=4)


def _case_val(case: dict, banked: str) -> float:
    """Map a banked npz key onto the reconstructed case's own key name."""
    return case["corr_ez_sup" if banked == "corr_ez_superseded" else banked]


def _titles(case: dict, metric: dict) -> dict:
    """Panel titles for one run on one metric -- BOTH numbers, always."""
    m = metric
    plotted = _case_val(case, m["plotted"])
    other = _case_val(case, m["not_plotted"])
    vlabel = m["plotted"]
    olabel = m["not_plotted"]
    lab = case["spec"]["label"]
    col = case["col"]
    ez, ey = case["y_ez"], case["z_ez"]
    A_ez, E_ez, D_ez = (case["viz"]["A_ez"], case["viz"]["E"][m["key"]],
                        case["viz"]["D"][m["key"]])
    rel = rms(D_ez) / np.sqrt(0.5 * (rms(A_ez) ** 2 + rms(E_ez) ** 2))
    A_ey, E_ey, D_ey = case["viz"]["A_ey"], case["viz"]["E_ey"], case["viz"]["D_ey"]
    rel_y = rms(D_ey) / np.sqrt(0.5 * (rms(A_ey) ** 2 + rms(E_ey) ** 2))
    out = {}
    out["A_ez"] = (f"ANALYTIC plane basis  e_z  —  {lab}\n"
                   f"reference, unit RMS, vmax = {np.max(np.abs(A_ez)):.2f}")
    out["E_ez"] = (f"EXTRACTED e_z  —  {lab}, QZ col {col}\n"
                   f"{vlabel} = {plotted:+.4f}  (PLOTTED)\n"
                   f"{olabel} = {other:+.4f}  (not plotted)")
    out["D_ez"] = (f"A_ez − EXTRACTED e_z  ({lab})\n"
                   f"max|Δ| = {np.max(np.abs(D_ez)):.2f}   rms(Δ)/rms = {rel:.2f}\n"
                   f"vmax = {np.max(np.abs(D_ez)):.2f} own, shared later")
    out["A_ey"] = (f"ANALYTIC plane basis  e_y  —  {lab}\n"
                   f"reference, unit RMS, vmax = {np.max(np.abs(A_ey)):.2f}")
    out["E_ey"] = (f"EXTRACTED e_y  —  {lab}, QZ col {col}\n"
                   f"corr_ey = {case['corr_ey']:+.4f}  (PLOTTED, metric-independent)")
    out["D_ey"] = (f"A_ey − EXTRACTED e_y  ({lab})\n"
                   f"max|Δ| = {np.max(np.abs(D_ey)):.2f}   rms(Δ)/rms = {rel_y:.2f}")
    return out


def draw_picture(cases: dict, metric: dict, lim: dict, geo: dict,
                 pdf_path: str, png_path: str, n_written: int) -> None:
    """Draw one figure for `metric` on the SHARED axes and colour limits in `lim`."""
    pmc, pec = cases["pmc"], cases["pec"]
    m = metric
    CELL = pmc["cell"]
    EXT = (-0.5 * CELL * 1e3, pmc["y_hi"] * 1e3 + 0.5 * CELL * 1e3,
           -0.5 * CELL * 1e3, pmc["z_hi"] * 1e3 + 0.5 * CELL * 1e3)
    HSUB = float(geo["h"])
    W, WSTRIP = float(geo["width"]), float(geo["w"])
    Y0, Y1 = W / 2 - WSTRIP / 2, W / 2 + WSTRIP / 2

    fig = plt.figure(figsize=(13.4, 11.2))
    gs = GridSpec(len(ROWS), 3, figure=fig, left=0.045, right=0.985, top=0.875,
                  bottom=0.045, wspace=0.08, hspace=0.42)

    axes = {}
    for r, (slot, _kind) in enumerate(ROWS):
        axes[(slot, "pmc")] = fig.add_subplot(gs[r, 0])
        axes[(slot, "pec")] = fig.add_subplot(gs[r, 1], sharex=axes[(slot, "pmc")],
                                             sharey=axes[(slot, "pmc")])
    ax_info_top = fig.add_subplot(gs[0:3, 2])
    ax_info_bot = fig.add_subplot(gs[3:6, 2])
    for ax in (ax_info_top, ax_info_bot):
        ax.axis("off")

    titles = {k: _titles(c, m) for k, c in cases.items()}
    for slot, _kind in ROWS:
        for key in ("pmc", "pec"):
            case = cases[key]
            f = _slot_field(case["viz"], slot, m["key"])
            yc = case["y_ez"] if slot in ("A_ez", "E_ez", "D_ez") else case["y_ey"]
            zc = case["z_ez"] if slot in ("A_ez", "E_ez", "D_ez") else case["z_ey"]
            tcolor = ("0.15" if not m["legacy"]
                      else ("#b2182b" if slot in ("E_ez", "D_ez") else "0.15"))
            _panel(axes[(slot, key)], f, yc, zc, EXT, titles[key][slot],
                   lim[(key, slot)], contours=slot.startswith("A") or slot == "E_ez"
                   or slot == "E_ey", tcolor=tcolor)
            _overlay(axes[(slot, key)], HSUB, Y0, Y1)
        axes[(slot, "pmc")].tick_params(labelleft=True)
        axes[(slot, "pmc")].set_ylabel("z  [mm]", fontsize=7)
        if slot.startswith("D"):
            for key in ("pmc", "pec"):
                axes[(slot, key)].tick_params(labelbottom=True)
                axes[(slot, key)].set_xlabel("y  [mm]", fontsize=7)

    head = ("C2b mode shape — CORRECTED metric: analytic plane basis vs the extracted field, "
            "same component in each row (vertical vs VERTICAL, width vs WIDTH)"
            if not m["legacy"] else
            "C2b mode shape — SUPERSEDED metric (before the fix): the VERTICAL reference "
            "was correlated with the LONGITUDINAL field — two different physical components")
    fig.text(0.045, 0.968, head, fontsize=10.5, ha="left", va="center",
             color=("k" if not m["legacy"] else "#b2182b"))
    # wrapped by hand: one 950-character line would push the tight bbox out to 25 in
    caption = textwrap.fill(
             "Columns: PMC / open top (left), PEC / closed box (middle), text (right).  "
             "Rows: analytic e_z, extracted e_z, difference; then the same three for e_y.  "
             "Same panels, same axes (y 0–20 mm, z 0–7.6 mm) and same colour limits in the "
             "corrected and the before figure — limits are the per-panel max over BOTH "
             "metrics, so no panel is clipped in either figure.  Each field is divided by "
             "its own RMS; contours are |field| at 0.25/0.50/0.75 of the panel's own max.  "
             "Dashed: substrate interface h.  Thick: strip.  Dotted verticals: the two strip "
             "edges y = 8.5 / 11.5 mm.", width=205)
    fig.text(0.045, 0.940, caption, fontsize=5.8, ha="left", va="top", color="0.25")

    # ---- text panel (top): what this is + the metric definition ------------
    if not m["legacy"]:
        metric_block = (
            "METRIC ON THIS FIGURE: corrected\n"
            "  e_z row : A_ez  vs  e_z_vv\n"
            "            = component 1 of e_t on the A_ez\n"
            "              lattice: vertical vs VERTICAL\n"
            "  e_y row : A_ey  vs  e_y\n"
            "            = component 0 of e_t on the A_ey\n"
            "              lattice: width vs WIDTH\n"
            "  both are same-component shape tests.\n"
            "  The superseded number is printed under the\n"
            "  plotted one on every extracted panel and is\n"
            "  NOT drawn anywhere on this figure.\n"
            "\n"
            "FIGURES ARE COMPARABLE\n"
            "  docs/report/figures/c2b_mode_shape_corrected.pdf\n"
            "  docs/design/mispaired_metric_before.pdf\n"
            "  identical panels, extents and vmax per panel.\n")
    else:
        metric_block = (
            "METRIC ON THIS FIGURE: before (superseded)\n"
            "  e_z row : A_ez  vs  e_z_superseded\n"
            "            = -interp(beta*z_free): the\n"
            "              LONGITUDINAL field.\n"
            "            A_ez is the VERTICAL reference, so\n"
            "            this row pairs two DIFFERENT physical\n"
            "            components -- which is why its\n"
            "            correlation is 0.12 / 0.15 and why\n"
            "            the difference row is full-scale.\n"
            "  e_y row : unchanged (width vs width) -- the\n"
            "            mis-pairing was in the e_z row only.\n"
            "  The corrected number (e_z_vv) is printed\n"
            "  under the plotted one and is NOT drawn.\n"
            "\n"
            "  This is the picture docs/design/c2b_shapes.pdf\n"
            "  used to draw.\n")
    info_top = (
        "WHAT THIS IS\n"
        "Two banked runs of the same 31x17 mixed\n"
        "pencil (y = 20 mm transverse, z = 7.6 mm):\n"
        "  PMC  c1_spectrum.npz      QZ col 738\n"
        "  PEC  pecbox_spectrum.npz  QZ col 699\n"
        "Nothing is solved here.  The e_t eigenvector\n"
        "is banked (vecs_real[:, col]); e_y and e_z_vv\n"
        "are sampled from it with Mode2D.e_at on the\n"
        "two plane lattices, and the longitudinal e_z\n"
        "is rebuilt through the audit's own LU route.\n"
        "The script refuses to draw unless ALL THREE\n"
        "banked correlations are reproduced to 1e-6.\n"
        "\n" + metric_block + "\n"
        "HOW TO READ A DIFFERENCE ROW\n"
        "* near-blank : agreement to the plotted scale\n"
        "* bright rim : disagreement at a wall or a\n"
        "  strip edge -> a boundary effect\n"
        "* speckle    : the mode is not resolved\n"
        "  (see `residual` in the audit table)\n"
        "* one lobe of one sign : a gauge or\n"
        "  normalisation mismatch, not physics\n")
    ax_info_top.text(0.0, 0.995, info_top, fontsize=5.6, va="top", ha="left",
                     family="monospace", linespacing=1.32,
                     transform=ax_info_top.transAxes)

    # ---- text panel (bottom): every number printed on this figure ----------
    corr_pmc = corr(pmc["viz"]["E"][m["key"]], pec["viz"]["E"][m["key"]])
    corr_other = corr(pmc["viz"]["E"][
        "before" if m["key"] == "corrected" else "corrected"],
        pec["viz"]["E"]["before" if m["key"] == "corrected" else "corrected"])
    lim_lines = "\n".join(
        "  " + f"{slot:<5s} vmax = {lim[('pmc', slot)]:5.2f} / {lim[('pec', slot)]:5.2f}"
        for slot, _k in ROWS)
    info_bot = (
        "NUMBERS ON THIS FIGURE\n"
        f"metric drawn : {m['key']}\n"
        f"  e_z row plotted     : {m['plotted']}\n"
        f"  e_z row NOT plotted : {m['not_plotted']}\n"
        "\n"
        "PMC / QZ col 738\n"
        f"  corr_ez_vv          = {pmc['corr_ez_vv']:+.6f}\n"
        f"  corr_ez_superseded  = {pmc['corr_ez_sup']:+.6f}\n"
        f"  corr_ey             = {pmc['corr_ey']:+.6f}\n"
        "PEC / QZ col 699\n"
        f"  corr_ez_vv          = {pec['corr_ez_vv']:+.6f}\n"
        f"  corr_ez_superseded  = {pec['corr_ez_sup']:+.6f}\n"
        f"  corr_ey             = {pec['corr_ey']:+.6f}\n"
        f"eps_eff      : {pmc['eps_eff']:.6f} / {pec['eps_eff']:.6f}\n"
        f"QZ residual  : {pmc['residual']:.2e} / {pec['residual']:.2e}\n"
        "\n"
        "SHARED, FIXED COLOUR LIMITS\n"
        "(per-panel max over BOTH metrics; identical\n"
        " in the corrected and the before figure)\n"
        f"{lim_lines}\n"
        "\n"
        "AXES HELD FIXED\n"
        "  every panel: y 0..20 mm, z 0..7.6 mm\n"
        "  (the two lattices are offset by half a cell\n"
        "   - node vs mid-cell - inside that frame)\n"
        "\n"
        "CROSS-RUN (extracted, PMC vs PEC)\n"
        f"  corr on this metric   = {corr_pmc:+.4f}\n"
        f"  corr on the other one = {corr_other:+.4f}\n"
        "\n"
        "provenance: c1_audit.py / pecbox_variant.py\n"
        "outputs (tools/host/c1-audit/out/).  This\n"
        "figure is generated by\n"
        "tools/host/mode_plot/mode_plot.py\n"
        f"--metric {m['key']}  (figure {n_written})\n")
    ax_info_bot.text(0.0, 0.995, info_bot, fontsize=5.6, va="top", ha="left",
                     family="monospace", linespacing=1.32,
                     transform=ax_info_bot.transAxes)

    fig.text(0.985, 0.008,
             f"elapsed {time.time() - T0:.1f} s   metric={m['key']}   "
             f"shared vmax: " + "  ".join(
                 f"{s}={lim[('pmc', s)]:.2f}/{lim[('pec', s)]:.2f}"
                 for s, _k in ROWS),
             fontsize=5.2, ha="right", va="bottom", color="0.4")

    for p in (pdf_path, png_path):
        os.makedirs(os.path.dirname(p), exist_ok=True)
    fig.savefig(pdf_path, bbox_inches="tight")
    if png_path:
        fig.savefig(png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

    for p in (pdf_path, png_path):
        if not p:
            continue
        _check(os.path.exists(p) and os.path.getsize(p) > 0,
               f"{p} was not written (or is empty) -- the figure did not render.")
        say(f"wrote    : {p}  ({os.path.getsize(p)} bytes)")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def _png_for(pdf_path: str) -> str:
    root, _ext = os.path.splitext(pdf_path)
    return root + ".png"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="mode_plot.py",
        description="Draw the C2b picture on an EXPLICIT metric: --metric "
                    "corrected (same component, the report figure), --metric "
                    "before (the superseded mis-pairing, the teaching figure) or "
                    "--metric both (default; identical axes and colour limits).")
    ap.add_argument("--metric", choices=("corrected", "before", "both"),
                    default="both",
                    help="which metric to draw (default: both, i.e. neither "
                         "metric is silently substituted for the other)")
    ap.add_argument("--out", default=OUT_CORRECTED,
                    help=f"corrected-metric PDF (default: {OUT_CORRECTED}); a PNG "
                         f"is written beside it")
    ap.add_argument("--before-out", default=OUT_BEFORE,
                    help=f"superseded-metric PDF (default: {OUT_BEFORE})")
    ap.add_argument("--c2b-out", default=OUT_C2B,
                    help=f"refreshed C2b artifact, corrected metric "
                         f"(default: {OUT_C2B})")
    ap.add_argument("--no-c2b", action="store_true",
                    help="do not refresh the pre-existing docs/design/c2b_shapes.pdf")
    args = ap.parse_args(argv)

    say("mode_plot.py -- analytic vs extracted field (C2b), explicit metric")
    say(f"repo     : {REPO}")
    say(f"repo env : {_REPO_ENV or '(unset; walked up from ' + HERE + ')'}")
    say(f"design   : {DESIGN}")
    say(f"report   : {REPORT_FIG}")
    say(f"c1 out   : {C1_OUT}")
    say(f"metric   : {args.metric}  "
        f"(corrected = corr_ez_vv + corr_ey; before = corr_ez_superseded + corr_ey)")

    with open(GEOJSON) as fh:
        geo = json.load(fh)["geometry"]
    HSUB, EPS_R = float(geo["h"]), float(geo["eps_r"])
    W, WSTRIP = float(geo["width"]), float(geo["w"])
    Y0, Y1 = W / 2 - WSTRIP / 2, W / 2 + WSTRIP / 2
    say("geometry :", dict(width=W, height=geo["height"], h=HSUB, strip=WSTRIP,
                           eps_r=EPS_R, strip_y=[Y0, Y1]))

    cases = {}
    for spec in RUNS:
        say(f"--- {spec['label']}  ({spec['npz']}, QZ col {spec['col']})")
        cases[spec["key"]] = reconstruct_run(spec, geo)
    pmc, pec = cases["pmc"], cases["pec"]

    # the analytic fields are banked per file; say out loud whether they agree
    dA = float(np.max(np.abs(pmc["A_ez_raw"] - pec["A_ez_raw"])))
    dAy = float(np.max(np.abs(pmc["A_ey_raw"] - pec["A_ey_raw"])))
    say(f"analytic : max|A_ez(PMC) - A_ez(PEC)| = {dA:.3e}   "
        f"max|A_ey(PMC) - A_ey(PEC)| = {dAy:.3e} "
        f"(both from M.plane_mode; the PEC mask cannot change them)")

    # cross-run quantities, computed from the loaded fields -- never hard-coded
    say("cross    : extracted PMC vs PEC")
    for mk in ("corrected", "before"):
        cc = corr(pmc["viz"]["E"][mk], pec["viz"]["E"][mk])
        say(f"           {mk:<9s} |corr(e_z PMC, e_z PEC)| = {abs(cc):.6f}")
    cyy = corr(pmc["viz"]["E_ey"], pec["viz"]["E_ey"])
    say(f"           e_y       |corr(e_y PMC, e_y PEC)| = {abs(cyy):.6f}")
    say(f"eps_eff  : PMC {pmc['eps_eff']!r}  PEC {pec['eps_eff']!r}  "
        f"rel_delta = {(pec['eps_eff'] - pmc['eps_eff']) / pmc['eps_eff']:+.6f}")
    say(f"corr_ez_vv: PMC {pmc['corr_ez_vv']:+.15f}  PEC {pec['corr_ez_vv']:+.15f}  "
        f"rel_delta = {(abs(pec['corr_ez_vv']) - abs(pmc['corr_ez_vv'])) / abs(pmc['corr_ez_vv']):+.6f}")
    say(f"corr_ez_superseded: PMC {pmc['corr_ez_sup']:+.15f}  "
        f"PEC {pec['corr_ez_sup']:+.15f}")

    # one set of colour limits, shared by every figure drawn below
    lim = colour_limits(cases)
    say("limits   : shared per-panel vmax (max over both metrics)")
    for slot, _k in ROWS:
        say(f"           {slot:<5s} PMC {lim[('pmc', slot)]:8.4f}   "
            f"PEC {lim[('pec', slot)]:8.4f}")

    targets: list[tuple] = []
    if args.metric in ("corrected", "both"):
        targets.append(("corrected", args.out))
        if not args.no_c2b:
            targets.append(("corrected", args.c2b_out))
    if args.metric in ("before", "both"):
        targets.append(("before", args.before_out))

    seen = set()
    n = 0
    for mkey, pdf in targets:
        pdf = os.path.abspath(pdf)
        if pdf in seen:
            say(f"skip     : {pdf} (duplicate target)")
            continue
        seen.add(pdf)
        n += 1
        say(f"figure   : metric={mkey}  ->  {pdf}")
        draw_picture(cases, METRICS[mkey], lim, geo, pdf, _png_for(pdf), n)

    _check(n > 0, "no figure was requested -- that is a bug in the argument handling.")
    say(f"DONE mode_plot.py elapsed={time.time() - T0:.1f} s  figures={n}  "
        f"metric={args.metric}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        # loud, one place, no traceback noise: a refusal is a bug report, not a
        # crash -- and it must never be swallowed into a half-drawn figure.
        print("REFUSED\n" + str(exc), file=sys.stderr, flush=True)
        sys.exit(3)
