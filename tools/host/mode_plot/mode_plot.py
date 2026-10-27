#!/usr/bin/env python3
"""mode_plot.py -- the C2b picture: analytic plane basis vs the *extracted* e_z.

WHAT THIS FILE IS
-----------------
The repository's first visualisation, and therefore deliberately small: it reads
the two banked spectra, reconstructs one scalar field from each, and draws

    row 1   the analytic plane-mode e_z               (the reference)
    row 2   the extracted e_z of the identified mode  (the thing under audit)
    row 3   analytic - extracted                      (what |corr_e_z| = 0.12 looks like)
            plus, in the third column, PMC - PEC      (what closing the box does)

for the two runs that exist on disk:

    column 1   PMC / open top    tools/host/c1-audit/out/c1_spectrum.npz      QZ col 738
    column 2   PEC / closed box  tools/host/c1-audit/out/pecbox_spectrum.npz  QZ col 699

Nothing is solved here.  Every number plotted is either read from an npz or
recomputed from it by the *same* arithmetic the audit used (see below).

DATA CONTRACT (both npz files have identical keys -- ONE call site writes them)
-----------------------------------------------------------------------------
np.savez() in tools/host/c1-audit/c1_audit.py:551-570 (NPZ_PATH, c1_audit.py:147);
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
    k0                        scalar wavenumber (164.179... rad/m).
    lam (n_qz,), complex      QZ eigenvalues; lam[j] IS beta^2 (pencil
                              A x = beta^2 B x, emfit/mode2d.py:1003-1005).
    vecs_real (n_free, n_qz)  real part of EVERY eigenvector; column index == QZ
                              column number.  This is e_t on the free edges.
    j (n_prop,)               the QZ column indices of the propagating rows.
    beta_sq, eps_eff, corr_ey, corr_ez (n_prop,)   per-mode metrics (signed).
    A_ez (201, 76)            THE ANALYTIC FIELD, banked (c1_audit.py:405-408 from
                              M.plane_mode).  Index [y, z-mid]: axis 0 is the
                              transverse coordinate on the node lattice
                              (0 .. 20 mm), axis 1 is the vertical mid-cell
                              lattice (0.05 .. 7.55 mm).

Why the extracted field is NOT just read from the npz: no key banks it.  The
audit keeps only the two scalar correlations for every column and discards the
arrays, so the field has to be reconstructed -- by exactly the route the audit
(and pecbox_variant.py's `dominant` column) already used.

RECONSTRUCTION OF THE EXTRACTED e_z (copied, not invented)
----------------------------------------------------------
    blocks   m1, m_eps, c, k_zz, m_zz = m2.assemble_mixed(mesh, eps_r=eps_of)
             h  = k_zz[free_n][:, free_n] - k0^2 m_zz[free_n][:, free_n]
             cf = c[free_e][:, free_n];  lu = splu(h)
                                                     c1_audit.py:386-389
    column   x = vecs_real[:, col]; x /= ||x||         c1_audit.py:455-459
    e_z      z_free = lu.solve(cf.T @ x); e_z_node[free_n] = beta * z_free
                                                     c1_audit.py:471-473
             (emfit/mode2d.py:1174-1175 keeps 1j*beta*z_free; the audit drops the
              global i, and this plot drops it too -- same sign convention as the
              banked corr_e_z, which is what the self-check below relies on.)
    lattice  ez_grid = e_z_node.reshape(nz, nx)        c1_audit.py:490
             e_z = -RegularGridInterpolator((ZS, XS), ez_grid)(pts) sampled at
             the plane lattice y = i*cell, z = (k+0.5)*cell, then reshaped
             (NYN, NZN-1)                              c1_audit.py:490-493
    eps      eps_of(p) = where(p[:,1] <= h + 1e-12, eps_r, 1)   c1_audit.py:274
             h, eps_r from the same geojson the audit reads (c1_audit.py:143,
             246-250).  m_zz carries eps_r, so this is not optional.

SELF-CHECK (the reason a blind-written first run can still be trusted)
---------------------------------------------------------------------
After the reconstruction, corr(A_ez, e_z) is compared with the banked corr_e_z
for that column, and the banked eps_eff is compared with the declared constant.
A mismatch raises -- the script never plots a field it could not reproduce.
Expected values, from the runs' own tables:

    c1_table.txt:16      col 738  eps_eff 3.6295122080769704  corr_e_z +0.119160432391342
    pecbox_table.txt:16  col 699  eps_eff 3.606094999644309  corr_e_z +0.147291446944630

(An earlier task brief had these two eps_eff values transposed; the tables and
run.log:41,49 / pecbox_run.log:73,82,88-89 agree with each other and with the
physics -- closing the lid lowers eps_eff -- so the table values are used.)

GAUGE (sign)
------------
A generalised eigenvector is defined up to an arbitrary scalar and LAPACK fixes
no sign, so column 738 may come back as +x or -x (c1_audit.py docstring, "Why the
criterion uses |corr|").  For the picture only, the extracted field is multiplied
by sign(corr_e_z) so that it lands in the same lobe as the reference.  Nothing is
*compared* on a sign: every comparison below uses magnitudes.

COLOUR / SCALES
---------------
Each field is RMS-normalised (divided by its own root-mean-square over the
lattice), so the colour scale is in units of the field's own RMS.  Every panel
has its own symmetric, zero-centred limit and the numeric vmax is printed in that
panel's title -- there is no shared colour bar, by design, because the analytic
field is ~10x peakier than the extracted one and a shared scale would flatten the
latter to invisibility.

Read-only w.r.t. the repo: writes docs/design/c2b_shapes.pdf and .png, nothing
else, and never touches emfit/.

Run:
    tools/host/mode_plot/run.sh
or directly:
    cd <repo> && python3 -u tools/host/mode_plot/mode_plot.py
"""

from __future__ import annotations

import json
import os
import sys
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
PDF_PATH = os.path.join(DESIGN, "c2b_shapes.pdf")
PNG_PATH = os.path.join(DESIGN, "c2b_shapes.png")

# ---------------------------------------------------------------------------
# the two banked runs, and the column each one's identified mode sits in
#
# `col` is the QZ column; eps_eff / corr_* / beta_sq are the values the runs
# themselves printed, kept ONLY to locate the column and to gate the
# reconstruction (see SELF-CHECK above).  Sources, verbatim:
#   PMC: out/c1_table.txt:16, out/run.log:41,49,54-55
#   PEC: out/pecbox_table.txt:16-17, out/pecbox_run.log:73,82,88-89
# ---------------------------------------------------------------------------
RUNS = (
    dict(key="pmc",
         label="PMC / open top",
         npz="c1_spectrum.npz",
         col=738,
         eps_eff=3.6295122080769704,
         beta_sq=9.7833058e4,
         corr_ey=+0.920770784811142,
         corr_ez=+0.119160432391342),
    dict(key="pec",
         label="PEC / closed box",
         npz="pecbox_spectrum.npz",
         col=699,
         eps_eff=3.606094999644309,
         beta_sq=9.7201850e4,
         corr_ey=+0.912343044811209,
         corr_ez=+0.147291446944630),
)

#: npz keys this script needs; a missing one is named in the error, never zeros
REQUIRED_KEYS = ("xs", "zs", "n_edges", "n_nodes", "free_e", "free_n", "k0",
                 "lam", "vecs_real", "j", "beta_sq", "eps_eff",
                 "corr_ey", "corr_ez", "A_ez")

#: |measured - banked| tolerance on the two correlations (they are O(1))
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
    c1_audit.py:495-496), which is what makes the self-check below meaningful.
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
    """Rebuild the extracted e_z of `spec` and return both plotted fields."""
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
           f"expects (c1_audit.py:551-570).")

    HSUB = float(geo["h"])
    EPS_R = float(geo["eps_r"])
    XS = np.asarray(d["xs"], dtype=float)
    ZS = np.asarray(d["zs"], dtype=float)
    K0 = float(d["k0"])
    A_ez = np.asarray(d["A_ez"], dtype=float)
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
    cz_file = float(np.asarray(d["corr_ez"], dtype=float)[row])
    bsq = float(np.real(lam[col]))
    _check(abs(eps_file - spec["eps_eff"]) <= EPS_RTOL * abs(spec["eps_eff"]),
           f"{path}: eps_eff in the file is {eps_file!r} but RUNS expects "
           f"{spec['eps_eff']!r} "
           f"(rel {abs(eps_file - spec['eps_eff']) / abs(spec['eps_eff']):.2e}).\n"
           f"  The column/eps_eff pair in RUNS is wrong -- fix the constant, do not "
           f"loosen the tolerance.")
    _check(abs(cy_file - spec["corr_ey"]) <= CORR_TOL,
           f"{path}: corr_e_y in the file is {cy_file!r} but RUNS expects "
           f"{spec['corr_ey']!r}.")
    _check(abs(cz_file - spec["corr_ez"]) <= CORR_TOL,
           f"{path}: corr_e_z in the file is {cz_file!r} but RUNS expects "
           f"{spec['corr_ez']!r}.")
    _check(abs(float(spec["beta_sq"]) - bsq) <= BSQ_RTOL * abs(bsq),
           f"{path}: beta^2 at column {col} is {bsq!r} but RUNS prints "
           f"{spec['beta_sq']!r}.")
    _check(lam.size == free_e.size and vecs.shape[0] == free_e.size,
           f"{path}: lam {lam.shape} / vecs_real {vecs.shape} disagree with "
           f"free_e ({free_e.size},).")
    _check(col < vecs.shape[1],
           f"{path}: column {col} is outside vecs_real ({vecs.shape}).")

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
        # c1_audit.py:274-275, verbatim
        return np.where(p[:, 1] <= HSUB + 1e-12, EPS_R, 1.0)

    # ---- blocks + one LU (c1_audit.py:386-389) ------------------------------
    _t = time.time()
    m1, m_eps_m, c, k_zz, m_zz = m2.assemble_mixed(mesh, eps_r=eps_of)
    h_blk = (k_zz[free_n][:, free_n] - K0 * K0 * m_zz[free_n][:, free_n]).tocsc()
    c_f = c[free_e][:, free_n].tocsc()
    lu = splu(h_blk)
    say(f"  blocks   : h={list(h_blk.shape)} nnz={h_blk.nnz} "
        f"c_f={list(c_f.shape)} nnz={c_f.nnz} ({time.time() - _t:.2f} s)")

    # ---- the column (c1_audit.py:455-473) -----------------------------------
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

    # ---- plane lattice (c1_audit.py:393-401, :490-493) ----------------------
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
    yc = np.arange(NYN) * cell_h                       # transverse, 0 .. 20 mm
    zc = (np.arange(NZN - 1) + 0.5) * cell_v           # vertical mid-cells
    iyy, izz = np.meshgrid(yc, zc, indexing="ij")
    pts = np.stack([izz.ravel(), iyy.ravel()], axis=1)  # (z, y): (ZS, XS) order
    itp = RegularGridInterpolator((ZS, XS), ez_grid, bounds_error=True)
    e_z = -itp(pts).reshape(NYN, NZN - 1)              # s10118_basis.py:369

    # ---- gate 1: reproduce the banked statistics ----------------------------
    cz_mine = corr(A_ez, e_z)
    _check(np.isfinite(cz_mine),
           f"{path}: corr(A_ez, e_z) is not finite -- the reconstructed field has "
           f"a zero norm or the shapes disagree ({A_ez.shape} vs {e_z.shape}).")
    _check(abs(cz_mine - cz_file) <= CORR_TOL,
           f"{path}: reconstructed corr_e_z = {cz_mine!r} but the file banks "
           f"{cz_file!r} (delta {abs(cz_mine - cz_file):.3e}).\n"
           f"  The reconstruction does not reproduce the audit, so this picture "
           f"would show a field the audit never scored.  Do NOT loosen this "
           f"tolerance -- find the difference (eps_of? k0? column? the sign of the "
           f"interpolated field?) first.")

    # ---- gauge fix + normalisation (picture only; no comparison uses the sign)
    sign_gauge = float(np.sign(cz_file))
    _check(sign_gauge != 0.0, f"{path}: banked corr_e_z is exactly 0 -- no gauge.")
    A_norm = A_ez / rms(A_ez)
    E_norm = sign_gauge * e_z / rms(e_z)

    say(f"  column   : QZ col {col}  beta={beta:.6f}  beta^2={bsq:.7e}  "
        f"eps_eff={eps_file!r}")
    say(f"  corr     : corr_e_y={cy_file:+.15f}  corr_e_z banked={cz_file:+.15f}  "
        f"reconstructed={cz_mine:+.15f}  delta={abs(cz_mine - cz_file):.2e}")
    say(f"  gauge    : extracted field multiplied by sign(corr_e_z) = "
        f"{sign_gauge:+.0f}")
    say(f"  fields   : A_ez {A_ez.shape} rms={rms(A_ez):.6e}  "
        f"e_z {e_z.shape} rms={rms(e_z):.6e}")

    return dict(spec=spec, A=A_norm, E=E_norm, A_raw=A_ez, E_raw=e_z,
                yc=yc, zc=zc, cell_h=cell_h, col=col, beta=beta, bsq=bsq,
                eps_eff=eps_file, corr_ey=cy_file, corr_ez=cz_file,
                corr_ez_mine=cz_mine, sign_gauge=sign_gauge,
                n_free_edges=int(free_e.size), path=path)


# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------
def _panel(ax, f, yc, zc, title, contours=True, cmap="RdBu_r"):
    """One signed scalar field, zero-centred, symmetric per-panel limits."""
    vmax = float(np.max(np.abs(f)))
    _check(np.all(np.isfinite(f)),
           f"panel '{title}': the field has non-finite entries -- refusing to "
           f"plot it (a NaN/Inf would be painted as a hole).")
    _check(vmax > 0.0,
           f"panel '{title}': the field is identically zero -- refusing to plot a "
           f"blank panel (that would read as agreement).")
    dy = float(yc[1] - yc[0])
    dz = float(zc[1] - zc[0])
    ext = ((yc[0] - dy / 2) * 1e3, (yc[-1] + dy / 2) * 1e3,
           (zc[0] - dz / 2) * 1e3, (zc[-1] + dz / 2) * 1e3)
    ax.imshow(f.T, origin="lower", extent=ext, cmap=cmap, vmin=-vmax, vmax=+vmax,
              interpolation="nearest", zorder=1)
    if contours:
        levels = vmax * np.array([0.25, 0.50, 0.75])
        cs = ax.contour(yc * 1e3, zc * 1e3, np.abs(f).T, levels=levels,
                        colors="k", linewidths=0.45, zorder=3)
        if len(cs.levels):
            ax.clabel(cs, fmt="%.2f", fontsize=4.5)
    ax.set_title(title, fontsize=7.0, linespacing=1.25)
    ax.tick_params(labelsize=6, labelbottom=False, labelleft=False)
    ax.set_aspect("equal")
    ax.set_xlim(ext[0], ext[1])
    ax.set_ylim(ext[2], ext[3])
    return vmax


def _overlay(ax, HSUB, y0, y1):
    """Substrate interface (dashed) and the strip (thick) -- geometry only."""
    ax.axhline(HSUB * 1e3, color="k", lw=0.6, ls=(0, (4, 3)), zorder=4)
    ax.plot([y0 * 1e3, y1 * 1e3], [HSUB * 1e3, HSUB * 1e3], color="k", lw=2.2,
            solid_capstyle="butt", zorder=5)


def main() -> int:
    say("mode_plot.py -- analytic vs extracted e_z (C2b)")
    say(f"repo     : {REPO}")
    say(f"repo env : {_REPO_ENV or '(unset; walked up from ' + HERE + ')'}")
    say(f"design   : {DESIGN}")
    say(f"c1 out   : {C1_OUT}")

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

    # the analytic field is banked per file; say out loud whether it is the same
    dA = float(np.max(np.abs(pmc["A_raw"] - pec["A_raw"])))
    say(f"analytic : max|A_ez(PMC) - A_ez(PEC)| = {dA:.3e} "
        f"(both come from M.plane_mode; the PEC mask cannot change it)")

    # cross-run quantities, computed from the loaded fields -- never hard-coded
    cross = pmc["E"] - pec["E"]
    cross_corr = corr(pmc["E"], pec["E"])
    cross_rel = rms(cross) / np.sqrt(0.5 * (rms(pmc["E"]) ** 2 + rms(pec["E"]) ** 2))
    say(f"cross    : |corr(e_z PMC, e_z PEC)| = {abs(cross_corr):.6f}   "
        f"rel_rms = {cross_rel:.6f}   "
        f"max|delta| = {float(np.max(np.abs(cross))):.6f}")

    # the disagreement the brief asks about, recomputed from the loaded numbers
    dz_pmc, dz_pec = abs(pmc["corr_ez"]), abs(pec["corr_ez"])
    rel_dz = (dz_pec - dz_pmc) / dz_pmc
    say(f"|corr_e_z|: PMC {dz_pmc:.15f}  PEC {dz_pec:.15f}  "
        f"rel_delta = {rel_dz:+.6f}  ({100.0 * rel_dz:+.2f} %)")
    say(f"eps_eff  : PMC {pmc['eps_eff']!r}  PEC {pec['eps_eff']!r}  "
        f"rel_delta = {(pec['eps_eff'] - pmc['eps_eff']) / pmc['eps_eff']:+.6f}")

    # ---------------- figure ------------------------------------------------
    fig = plt.figure(figsize=(13.2, 8.6))
    gs = GridSpec(3, 3, figure=fig, left=0.055, right=0.985, top=0.885,
                  bottom=0.075, wspace=0.10, hspace=0.46)
    ax_a_pmc = fig.add_subplot(gs[0, 0])
    ax_a_pec = fig.add_subplot(gs[0, 1], sharex=ax_a_pmc, sharey=ax_a_pmc)
    ax_e_pmc = fig.add_subplot(gs[1, 0], sharex=ax_a_pmc, sharey=ax_a_pmc)
    ax_e_pec = fig.add_subplot(gs[1, 1], sharex=ax_a_pmc, sharey=ax_a_pmc)
    ax_d_pmc = fig.add_subplot(gs[2, 0], sharex=ax_a_pmc, sharey=ax_a_pmc)
    ax_d_pec = fig.add_subplot(gs[2, 1], sharex=ax_a_pmc, sharey=ax_a_pmc)
    ax_d_cross = fig.add_subplot(gs[2, 2], sharex=ax_a_pmc, sharey=ax_a_pmc)
    ax_info = fig.add_subplot(gs[0:2, 2])
    ax_info.axis("off")

    yc, zc = pmc["yc"], pmc["zc"]
    _check(np.array_equal(yc, pec["yc"]) and np.array_equal(zc, pec["zc"]),
           "the two runs are not on the same plane lattice -- the PMC/PEC "
           "difference panel would be meaningless.")

    v_a_pmc = _panel(ax_a_pmc, pmc["A"], yc, zc,
                     "ANALYTIC plane basis  e_z   (reference)\n"
                     f"unit RMS, vmax = {np.max(np.abs(pmc['A'])):.2f}")
    v_a_pec = _panel(ax_a_pec, pec["A"], yc, zc,
                     "ANALYTIC plane basis  e_z   (reference)\n"
                     f"unit RMS, vmax = {np.max(np.abs(pec['A'])):.2f}")
    v_e_pmc = _panel(ax_e_pmc, pmc["E"], yc, zc,
                     f"EXTRACTED e_z — {pmc['spec']['label']}, QZ col {pmc['col']}\n"
                     f"|corr_e_y| = {abs(pmc['corr_ey']):.4f}   "
                     f"corr_e_z = {pmc['corr_ez']:+.4f}   "
                     f"vmax = {np.max(np.abs(pmc['E'])):.2f}")
    v_e_pec = _panel(ax_e_pec, pec["E"], yc, zc,
                     f"EXTRACTED e_z — {pec['spec']['label']}, QZ col {pec['col']}\n"
                     f"|corr_e_y| = {abs(pec['corr_ey']):.4f}   "
                     f"corr_e_z = {pec['corr_ez']:+.4f}   "
                     f"vmax = {np.max(np.abs(pec['E'])):.2f}")

    d_pmc = pmc["A"] - pmc["E"]
    d_pec = pec["A"] - pec["E"]
    rel_pmc = rms(d_pmc) / np.sqrt(0.5 * (rms(pmc["A"]) ** 2 + rms(pmc["E"]) ** 2))
    rel_pec = rms(d_pec) / np.sqrt(0.5 * (rms(pec["A"]) ** 2 + rms(pec["E"]) ** 2))
    v_d_pmc = _panel(ax_d_pmc, d_pmc, yc, zc,
                     f"ANALYTIC − EXTRACTED  (PMC)\n"
                     f"max|Δ| = {np.max(np.abs(d_pmc)):.2f}   "
                     f"rms(Δ)/rms = {rel_pmc:.2f}   "
                     f"vmax = {np.max(np.abs(d_pmc)):.2f}",
                     contours=False)
    v_d_pec = _panel(ax_d_pec, d_pec, yc, zc,
                     f"ANALYTIC − EXTRACTED  (PEC)\n"
                     f"max|Δ| = {np.max(np.abs(d_pec)):.2f}   "
                     f"rms(Δ)/rms = {rel_pec:.2f}   "
                     f"vmax = {np.max(np.abs(d_pec)):.2f}",
                     contours=False)
    v_d_cross = _panel(ax_d_cross, cross, yc, zc,
                       f"EXTRACTED − EXTRACTED  (PMC − PEC)\n"
                       f"max|Δ| = {np.max(np.abs(cross)):.2f}   "
                       f"|corr| = {abs(cross_corr):.4f}   "
                       f"rel.rms = {cross_rel:.2f}   "
                       f"vmax = {np.max(np.abs(cross)):.2f}",
                       contours=False)

    for ax in (ax_a_pmc, ax_a_pec, ax_e_pmc, ax_e_pec,
               ax_d_pmc, ax_d_pec, ax_d_cross):
        _overlay(ax, HSUB, Y0, Y1)
    for ax in (ax_a_pmc, ax_e_pmc, ax_d_pmc):
        ax.tick_params(labelleft=True)
        ax.set_ylabel("z  [mm]", fontsize=7)
    for ax in (ax_d_pmc, ax_d_pec, ax_d_cross):
        ax.tick_params(labelbottom=True)
        ax.set_xlabel("y  [mm]", fontsize=7)

    fig.text(0.055, 0.945,
             "C2b mode shape: analytic plane basis vs the extracted e_z "
             "(open-top PMC, left; PEC-closed box, middle)",
             fontsize=11, ha="left", va="center")
    fig.text(0.055, 0.912,
             "rows: analytic reference / extracted (QZ eigenvector, sign-gauge fixed) "
             "/ difference.  Each field is divided by its own RMS; every panel has "
             "its own zero-centred colour limit, printed as vmax.  Contours are |e_z| "
             "at 0.25/0.50/0.75 vmax.  Dashed: substrate interface; thick: strip.",
             fontsize=7.2, ha="left", va="center", color="0.25")

    info = (
        "WHAT THIS IS\n"
        "Two banked runs of the same 31x17 mixed\n"
        "pencil (y = 20 mm transverse, z = 7.6 mm):\n"
        "  PMC  c1_spectrum.npz      QZ col 738\n"
        "  PEC  pecbox_spectrum.npz  QZ col 699\n"
        "No solve happens here; the extracted field\n"
        "is rebuilt from vecs_real[:, col] by the\n"
        "audit's own LU route and is accepted only\n"
        "if it reproduces the banked corr_e_z\n"
        "(see the log: |delta| < 1e-6).\n"
        "\n"
        "HOW TO READ A DIFFERENCE ROW\n"
        "* near-blank  : the two fields agree to the\n"
        "  plotted scale (vmax in the title).\n"
        "* bright rim  : disagreement concentrated\n"
        "  at a wall -> a boundary effect (that is\n"
        "  what closing the box does).\n"
        "* fine speckle: the mode is not resolved\n"
        "  (check `residual` in out/c1_table.txt).\n"
        "* one lobe of a single sign over the whole\n"
        "  strip: a normalisation/gauge mismatch,\n"
        "  not physics -- both fields are RMS-1.\n"
        "\n"
        "NUMBERS IN THE LOG\n"
        f"|corr_e_z| PMC {dz_pmc:.6f} / PEC {dz_pec:.6f}\n"
        f"rel. delta {100.0 * rel_dz:+.2f} %\n"
        f"eps_eff {pmc['eps_eff']:.6f} / {pec['eps_eff']:.6f}\n"
        f"corr(e_z PMC, e_z PEC) = {abs(cross_corr):.4f}\n"
        f"max|A_ez(PMC) - A_ez(PEC)| = {dA:.1e}\n"
        "\n"
        "provenance: c1_audit.py / pecbox_variant.py\n"
        "outputs (tools/host/c1-audit/out/).\n"
        "This figure is generated by\n"
        "tools/host/mode_plot/mode_plot.py."
    )
    ax_info.text(0.0, 0.99, info, fontsize=6.3, va="top", ha="left",
                 family="monospace", linespacing=1.35,
                 transform=ax_info.transAxes)

    fig.text(0.985, 0.012,
             f"elapsed {time.time() - T0:.1f} s   "
             f"vmax a={v_a_pmc:.2f}/{v_a_pec:.2f}  "
             f"e={v_e_pmc:.2f}/{v_e_pec:.2f}  "
             f"d={v_d_pmc:.2f}/{v_d_pec:.2f}/{v_d_cross:.2f}",
             fontsize=5.5, ha="right", va="bottom", color="0.4")

    os.makedirs(DESIGN, exist_ok=True)
    fig.savefig(PDF_PATH, bbox_inches="tight")
    fig.savefig(PNG_PATH, dpi=200, bbox_inches="tight")
    plt.close(fig)

    for p in (PDF_PATH, PNG_PATH):
        _check(os.path.exists(p) and os.path.getsize(p) > 0,
               f"{p} was not written (or is empty) -- the figure did not render.")
        say(f"wrote    : {p}  ({os.path.getsize(p)} bytes)")
    say(f"DONE mode_plot.py elapsed={time.time() - T0:.1f} s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        # loud, one place, no traceback noise: a refusal is a bug report, not a
        # crash -- and it must never be swallowed into a half-drawn figure.
        print("REFUSED\n" + str(exc), file=sys.stderr, flush=True)
        sys.exit(3)
