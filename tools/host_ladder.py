#!/usr/bin/env python3
"""Host-only ladder: the FDTD driver against a sparse 2-D modal reference.

Why this tool exists
--------------------
The in-package mode solver (``emfit.mode2d``) is a good reference at coarse
cells and a poor one when the cell is refined: its transverse (deflated)
pencil and the dense *mixed* pencil disagree by about 11 % at ``h = 0.2 mm``
(364.79 against 406.98 rad/m on the ``cl = 1.0H`` box), so a ladder built on
it would be reporting the solver rather than the line.  This tool therefore
takes its modal reference from the *sparse mixed* pencil -- Route C, shift
inverted -- and it runs the repository's own FDTD driver beside it on a box
that is cell-for-cell the same physical region.  What is compared is then
two discretisations of the same problem, not two different problems.

Route C, and why ``eigs`` and not ``eigsh``
-------------------------------------------
The pencil is

    K = [[A, 0], [0, 0]],     M = [[m, -c], [-c^T, h]],
    A = k0^2 m_eps - k_q  (symmetrised),   h = k_zz - k0^2 m_zz,

and it is solved at ``sigma`` shifted by ``eigs``, never by ``eigsh``: ``M``
is *indefinite* (the ``h`` block is negative in the substrate), and ``eigsh``
assumes a symmetric-definite pencil and will silently return junk rather than
raise.  The shift-invert operator is one explicit ``splu`` factorisation,
reused through ``OPinv``.

Where it runs
-------------
On the **host**, not in a container: ``python3 tools/host_ladder.py`` from the
repository root, with numpy, scipy and the repository importable.  It reads
the repository and writes exactly one file, the JSON named by ``--json`` --
and it writes nothing at all if any rung fails a hard check, because a
partial sweep presented as a sweep is a lie.  Hard failures, each of which
stops the run with a non-zero exit:

  * peak RSS above ``--mem-ceiling-mb``;
  * FDTD attenuation above ``--alpha-floor-db-per-mm``;
  * an eigenpair whose residual exceeds ``1e-8``;
  * the modal box failing to match the FDTD box cell-for-cell.

The frequency the two halves are compared at is not the requested tone but
the tone the FDTD actually accumulated its phasors at: the geometry the driver
returns carries the DFT-snapped ``f``, and ``k0 = 2 pi f / c`` is built from
that.  Comparing against the *requested* tone instead would put a parts-per-
thousand frequency error straight into ``beta`` and call it a mesh gap.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import LinearOperator, eigs, splu

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import d585_modal as dm                                          # noqa: E402
from emfit import mode2d, studies                                # noqa: E402

C0 = 299792458.0
H_SUB = 1.6e-3                      # substrate thickness, studies.MS_H
ER = 4.4                            # studies.MS_EPS_R
RUNGS_MM = (0.4, 0.26667, 0.2, 0.16, 0.13333)
SIGMA_MULT = 0.76                   # sigma = 0.76 * k0^2 * eps_r
K_EIGS = 16
TOL_RESID = 1e-8
CURL_FLOOR = 1e-6
EIGS_MAXITER = 5000
EIGS_TOL = 0.0
DB_PER_NP = 8.685889638             # 8.685889638 * alpha[Np/m] = dB/m
F0_GHZ_DEF = 10.0096                # dm.FREQ_DEF: the tone the paper's k0 is at
OUT_DEF = ".scratch/host_ladder.json"
ALPHA_MEASURED = (
    ("default box fit", 0.02145),
    ("npml10 span fit", 0.0278),
    ("lid sweep", 0.01388),
)


class LadderError(RuntimeError):
    """A rung failed a hard check.  The ladder stops and writes no JSON."""


# ---------------------------------------------------------------------------
# process facts
# ---------------------------------------------------------------------------
def rss_mb():
    """Peak resident set of this process, and which ``ru_maxrss`` unit branch."""
    raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return raw / (1024.0 * 1024.0), \
            "darwin: ru_maxrss is bytes, divided by 1 MiB"
    return raw / 1024.0, "linux: ru_maxrss is KiB, divided by 1024"


def git_rev():
    """Short HEAD, or a string saying why it could not be read."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:       # noqa: BLE001
        return f"unavailable: {type(exc).__name__}: {exc}"
    if out.returncode != 0:
        return f"unavailable: git exited {out.returncode}: " \
               f"{(out.stderr or '').strip()}"
    return out.stdout.strip()


def num(value, spec=".4f"):
    """Optional number, or ``n/a`` -- a refused fit stays visible as missing."""
    if value is None:
        return "n/a"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{v:{spec}}" if math.isfinite(v) else "n/a"


# ---------------------------------------------------------------------------
# FDTD half
# ---------------------------------------------------------------------------
def run_fdtd(h_mm, *, clearance, npml, nsteps, f0_hz, strip_cells):
    """One straight-guide microstrip run on the repository's own driver.

    The physical box is ``strip + 2 * (clearance * H)`` wide and
    ``H + clearance * H`` tall, with ``npml`` absorbing cells outside it on
    the two lateral faces and on top -- the geometry of the validated default
    record, moved by ``clearance`` only.  ``n_line`` is scaled with the cell
    so the stations at ``MS_X_FIRST``..``MS_X_LAST`` still lie inside the
    line; at the default cell it reproduces ``MS_N_LINE`` exactly.
    """
    h_m = h_mm * 1e-3
    n_sub = int(round(H_SUB / h_m))
    if n_sub < 1:
        raise LadderError(f"h = {h_mm:g} mm is coarser than the substrate "
                          f"H = {H_SUB * 1e3:g} mm")
    cell = H_SUB / n_sub
    n_edge_f = clearance * H_SUB / cell
    n_edge = int(round(n_edge_f))
    if abs(n_edge - n_edge_f) > 1e-9:
        raise LadderError(f"clearance {clearance:g} H is not a whole number of "
                          f"cells at h = {h_mm:g} mm ({n_edge_f:.6f})")
    if nsteps is None:
        nsteps = int(round(studies.MS_NSTEPS * n_sub / studies.MS_N_SUB))
    n_line = int(round(studies.MS_N_LINE * (H_SUB / studies.MS_N_SUB) / cell))
    t0 = time.perf_counter()
    wave = studies.microstrip_wave(
        h=H_SUB, w=strip_cells * cell, eps_r=ER,
        n_sub=n_sub, n_air=n_edge, n_top=npml,
        n_strip=strip_cells, n_clean=n_edge,
        n_pml=npml, n_ref=studies.MS_N_REF, n_line=n_line,
        x_first=studies.MS_X_FIRST, x_last=studies.MS_X_LAST,
        n_stations=studies.MS_N_STATIONS, f_target=f0_hz, nsteps=nsteps,
        keep_slice=False, audit=False, sink=studies.FigureSink())
    wall = time.perf_counter() - t0
    gy = dict(wave.geometry)
    return dict(wave=wave, wall=wall, geometry=gy, n_sub=n_sub, cell=cell,
                n_edge=n_edge, nsteps=nsteps, n_line=n_line,
                n_cells=int(gy["nx"]) * int(gy["ny"]) * int(gy["nz"]))


# ---------------------------------------------------------------------------
# modal half: Route C
# ---------------------------------------------------------------------------
class CountedSolve:
    """One ``splu`` factorisation, counting the applications ``eigs`` makes."""

    def __init__(self, lu):
        self.lu, self.calls = lu, 0

    def __call__(self, b):
        self.calls += 1
        return self.lu.solve(np.asarray(b).ravel())


def build_modal(h_m, *, clearance, strip_cells, k0, er=ER):
    """Assemble the transverse box and both pencils at cell ``h``."""
    nz_sub = int(round(H_SUB / h_m))
    if nz_sub < 1:
        raise LadderError(f"h = {h_m * 1e3:g} mm is coarser than H")
    cell = H_SUB / nz_sub
    # W is the strip the FDTD mesh actually contains (n_strip cells), not
    # dm's 0.8 mm default: at h = 0.4 mm that default is a 2-cell strip, and
    # the box would then be 26 cells wide against the FDTD's 32.
    geo = dm.section(h_m, clearance, H=H_SUB, W=strip_cells * cell)
    geo["k0"] = float(k0)
    mesh = geo["mesh"]
    bounds = dm.boxes(geo)["open"]
    eps = dm.eps_fun(geo, er)
    t0 = time.perf_counter()
    k_q, m_mu, m_eps = mode2d.assemble(mesh, eps_r=eps)
    m1, m_eps_mixed, c, k_zz, m_zz = mode2d.assemble_mixed(mesh, eps_r=eps)
    t_asm = time.perf_counter() - t0
    free_e = np.flatnonzero(~mode2d.pec_edge_mask(mesh, bounds))
    free_n = np.flatnonzero(~mode2d.pec_node_mask(mesh, bounds))
    n_e, n_n = int(free_e.size), int(free_n.size)
    m1_f = m1[free_e][:, free_e].tocsc()
    k_q_f = k_q[free_e][:, free_e].tocsc()
    m_eps_f = m_eps[free_e][:, free_e].tocsc()
    c_f = c[free_e][:, free_n].tocsc()
    h_blk = (k_zz[free_n][:, free_n] - k0 * k0 * m_zz[free_n][:, free_n]).tocsc()
    lu_h = splu(h_blk)
    a = (k0 * k0 * m_eps_f - k_q_f).tocsc()
    a.sum_duplicates()
    A = (0.5 * (a + a.T)).tocsc()
    return dict(geo=geo, mesh=mesh, k0=float(k0), n_e=n_e, n_n=n_n,
                m1_f=m1_f, k_q_f=k_q_f, m_eps_f=m_eps_f, A=A, c_f=c_f,
                h=h_blk, lu_h=lu_h, t_asm=t_asm,
                factor_nnz_h=int(lu_h.L.nnz + lu_h.U.nnz))


def route_c(pb, sigma, k):
    """Shift-inverted ``eigs`` on the mixed pencil; returns (rec, lam, vec)."""
    n_e, n_n = pb["n_e"], pb["n_n"]
    A, m1_f, c_f, h_blk = pb["A"], pb["m1_f"], pb["c_f"], pb["h"]
    KC = sp.block_diag([A, sp.csc_matrix((n_n, n_n))], format="csc")
    MC = sp.bmat([[m1_f, (-c_f).tocsc()],
                  [(-c_f.T).tocsc(), h_blk]], format="csc")
    S = (KC - float(sigma) * MC).tocsc()
    big = int(S.shape[0])
    rec = dict(sigma=float(sigma), n=big, nnz_S=int(S.nnz))
    t0 = time.perf_counter()
    lu = splu(S)
    rec["t_splu_s"] = time.perf_counter() - t0
    fact = int(lu.L.nnz + lu.U.nnz)
    rec.update(factor_nnz=fact, fill_per_row=fact / float(big),
               factor_memory_gb_measured=fact * 12 / 1e9)
    op = CountedSolve(lu)
    OP = LinearOperator(shape=(big, big), matvec=op, dtype=float)
    v0 = np.ones(big) / math.sqrt(big)
    t1 = time.perf_counter()
    try:
        lam, vec = eigs(KC, k=k, M=MC, sigma=float(sigma), which="LM",
                        OPinv=OP, maxiter=EIGS_MAXITER, tol=EIGS_TOL, v0=v0)
    except Exception as exc:                                    # noqa: BLE001
        rec["eigs_error"] = f"{type(exc).__name__}: {exc}"
        rec["t_eigs_s"] = time.perf_counter() - t1
        rec["opinv_calls"] = op.calls
        return rec, None, None
    rec["t_eigs_s"] = time.perf_counter() - t1
    rec["opinv_calls"] = op.calls
    rec["n_conv"] = int(np.size(lam))
    return rec, lam, vec


def candidates(pb, lam, vec, k0, er=ER):
    """Residual, curl ratio and eps_eff for each converged vector.

    The residual is the pencil's own: ``||Ax - lam Bx|| / (||Ax|| + |lam|
    ||Bx||)`` with ``Bx = m x - c (h^-1 (c^T x))``, i.e. the Schur form of
    ``M`` applied without forming it.
    """
    rows = []
    n_e = pb["n_e"]
    A, m1_f, c_f, lu_h, k_q_f = (pb["A"], pb["m1_f"], pb["c_f"],
                                 pb["lu_h"], pb["k_q_f"])
    for j in range(int(np.size(lam))):
        lj = complex(lam[j])
        ratio = abs(lj.imag) / max(1e-300, abs(lj))
        x = np.real(vec[:n_e, j])
        nx = float(np.linalg.norm(x))
        if not (math.isfinite(nx) and nx > 0.0):
            continue
        x = x / nx
        l = float(lj.real)
        Ax = np.asarray(A @ x).ravel()
        Bx = np.asarray(m1_f @ x).ravel() - np.asarray(
            c_f @ lu_h.solve(np.asarray(c_f.T @ x).ravel())).ravel()
        den = float(np.linalg.norm(Ax) + abs(l) * np.linalg.norm(Bx))
        res = float(np.linalg.norm(Ax - l * Bx) / den) if den > 0.0 else None
        m1x = float(x @ (m1_f @ x))
        curl = float(x @ (k_q_f @ x)) / m1x if m1x != 0.0 else None
        eeff = l / (k0 * k0) if l > 0.0 else None
        rows.append(dict(j=j, lam=l, imag_rel=float(ratio),
                         residual=res, curl_ratio=curl, eps_eff=eeff,
                         beta_sq=l, beta=(math.sqrt(l) if l > 0.0 else None),
                         guard_imag=bool(ratio < TOL_RESID),
                         guard_curl=bool(curl is not None
                                         and abs(curl) >= CURL_FLOOR),
                         guard_eps=bool(eeff is not None
                                        and eeff < er - 1e-6)))
    return rows


def pick_mode(rows):
    """The fundamental: the largest ``beta^2`` among the physical candidates."""
    good = [r for r in rows
            if r["guard_imag"] and r["guard_curl"] and r["guard_eps"]
            and r["beta"] is not None and r["residual"] is not None]
    if not good:
        return None, []
    good.sort(key=lambda r: r["beta_sq"], reverse=True)
    return good[0], good[:3]


# ---------------------------------------------------------------------------
# one rung
# ---------------------------------------------------------------------------
def run_rung(h_mm, args, rss_branch):
    """FDTD and modal on the same box at one cell size; returns the row."""
    print(f"\n=== rung h = {h_mm:g} mm ===", flush=True)
    fd = run_fdtd(h_mm, clearance=args.clearance, npml=args.npml,
                  nsteps=args.nsteps, f0_hz=args.f0_ghz * 1e9,
                  strip_cells=args.strip_cells)
    gy = fd["geometry"]
    k0 = 2.0 * math.pi * float(gy["f"]) / C0
    wave = fd["wave"]
    if wave.loss_fit is None or wave.loss_fit.alpha is None:
        raise LadderError(f"h = {h_mm:g} mm: the FDTD loss fit is unavailable, "
                          f"so the attenuation floor cannot be checked")
    alpha_db_mm = float(wave.loss_fit.alpha) * DB_PER_NP / 1000.0
    beta_fdtd = float(wave.beta)
    eps_fdtd = float(wave.eps_eff)
    ba = abs(complex(wave.gamma))
    n_stations = int(len(wave.station_x))
    print(f"  FDTD  cells={fd['n_cells']} nx,ny,nz="
          f"{gy['nx']},{gy['ny']},{gy['nz']} cell={gy['cell']*1e3:.6f} mm "
          f"nsteps={fd['nsteps']} f={float(gy['f'])/1e9:.6f} GHz "
          f"beta={beta_fdtd:.4f} alpha={alpha_db_mm:.6f} dB/mm "
          f"|b/a|={ba:.5f} stations={n_stations} wall={fd['wall']:.2f} s",
          flush=True)

    pb = build_modal(h_mm * 1e-3, clearance=args.clearance,
                     strip_cells=args.strip_cells, k0=k0)
    geo = pb["geo"]
    # The whole point: the modal box must be the FDTD box minus its absorbers.
    want_ny = int(gy["ny"]) - 2 * int(gy["n_pml"])
    want_nz = int(gy["nz"]) - int(gy["n_top"])
    if (int(geo["ny"]) != want_ny or int(geo["nz"]) != want_nz
            or abs(float(geo["cell"]) - float(gy["cell"])) > 1e-12):
        raise LadderError(
            f"h = {h_mm:g} mm: the boxes are not the same physical region -- "
            f"modal ny,nz = {geo['ny']},{geo['nz']} cell={geo['cell']:.6e} m "
            f"but FDTD ny-2*npml,nz-n_top = {want_ny},{want_nz} "
            f"cell={float(gy['cell']):.6e} m")
    sigma = SIGMA_MULT * k0 * k0 * ER
    t0 = time.perf_counter()
    rec, lam, vec = route_c(pb, sigma, args.k)
    t_eig = time.perf_counter() - t0
    if lam is None:
        raise LadderError(f"h = {h_mm:g} mm: eigs failed -- "
                          f"{rec.get('eigs_error', 'no converged pair')}")
    rows = candidates(pb, lam, vec, k0)
    best, near = pick_mode(rows)
    if best is None:
        raise LadderError(f"h = {h_mm:g} mm: no physical candidate among "
                          f"{len(rows)} converged pairs (guards: "
                          f"|imag|/|lam| < {TOL_RESID:g}, |curl| >= "
                          f"{CURL_FLOOR:g}, eps_eff < {ER - 1e-6:g})")
    if not (best["residual"] is not None and best["residual"] < TOL_RESID):
        raise LadderError(f"h = {h_mm:g} mm: residual "
                          f"{best['residual']!r} exceeds {TOL_RESID:g} at "
                          f"beta={best['beta']:.4f}")
    beta_eig = float(best["beta"])
    eps_eig = float(best["eps_eff"])
    print(f"  EIG   n_dof={pb['n_e'] + pb['n_n']} free_e={pb['n_e']} "
          f"n_n={pb['n_n']} sigma={sigma:.6f} nnz(S)={rec['nnz_S']} "
          f"factor_nnz={rec['factor_nnz']} "
          f"factor_mem={rec['factor_memory_gb_measured']:.3f} GB "
          f"beta={beta_eig:.4f} eps_eff={eps_eig:.6f} "
          f"res={best['residual']:.3e} t_splu={rec['t_splu_s']:.2f} "
          f"t_eigs={rec['t_eigs_s']:.2f} wall={t_eig:.2f} s", flush=True)

    gap_pct = 100.0 * (beta_eig - beta_fdtd) / beta_fdtd
    cavity_pct = 100.0 * (k0 * k0 * ER - beta_eig * beta_eig) / (k0 * k0 * ER)
    peak_mb, branch = rss_mb()
    if branch != rss_branch:
        raise LadderError(f"the ru_maxrss unit branch changed mid-run: "
                          f"{branch!r} against {rss_branch!r}")
    row = dict(
        h_mm=float(h_mm), cell_m=float(gy["cell"]), n_cells=fd["n_cells"],
        grid=[int(gy["nx"]), int(gy["ny"]), int(gy["nz"])],
        npml=int(gy["n_pml"]), n_top=int(gy["n_top"]),
        nsteps=int(fd["nsteps"]), f_hz=float(gy["f"]),
        f_target_hz=float(gy["f_target"]), k0=float(k0),
        beta_fdtd=beta_fdtd, beta_eig=beta_eig, rel_gap_pct=float(gap_pct),
        alpha_fdtd_db_per_mm=alpha_db_mm, b_over_a=float(ba),
        n_stations=n_stations, eps_eff_fdtd=eps_fdtd, eps_eff_eig=eps_eig,
        cavity_shift_pct=float(cavity_pct),
        free_e=int(pb["n_e"]), free_n=int(pb["n_n"]),
        n_dof=int(pb["n_e"] + pb["n_n"]),
        wall_fdtd_s=float(fd["wall"]), wall_eig_s=float(t_eig),
        t_assembly_s=float(pb["t_asm"]), t_splu_s=float(rec["t_splu_s"]),
        t_eigs_s=float(rec["t_eigs_s"]), opinv_calls=int(rec["opinv_calls"]),
        factor_nnz=int(rec["factor_nnz"]),
        factor_memory_gb_measured=float(rec["factor_memory_gb_measured"]),
        residual=float(best["residual"]), curl_ratio=float(best["curl_ratio"]),
        n_converged=len(rows), n_physical=len(near),
        runners_up=[dict(beta=r["beta"], eps_eff=r["eps_eff"],
                         residual=r["residual"]) for r in near[1:]],
        peak_rss_mb=float(peak_mb), rss_branch=branch,
    )
    if peak_mb > args.mem_ceiling_mb:
        raise LadderError(f"h = {h_mm:g} mm: peak RSS {peak_mb:.1f} MB is over "
                          f"the {args.mem_ceiling_mb:.1f} MB ceiling")
    if alpha_db_mm > args.alpha_floor_db_per_mm:
        raise LadderError(f"h = {h_mm:g} mm: FDTD attenuation "
                          f"{alpha_db_mm:.6f} dB/mm is over the "
                          f"{args.alpha_floor_db_per_mm:g} dB/mm floor")
    return row


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
HEADER = ("{:>8} {:>9} {:>7} {:>7} {:>10} {:>10} {:>8} {:>10} {:>8} "
          "{:>4} {:>8} {:>7} {:>8} {:>8} {:>8} {:>7}")


def print_table(rows):
    print("\n" + HEADER.format(
        "h[mm]", "n_cells", "free_e", "n_dof", "beta_FDTD", "beta_EIG",
        "gap[%]", "alpha", "|b/a|", "stns", "wall_FD", "wall_EIG", "rss[MB]",
        "eps_FD", "eps_EIG", "cav[%]"))
    print("-" * 146)
    for r in rows:
        print(HEADER.format(
            f"{r['h_mm']:8.5f}", f"{r['n_cells']:9d}", f"{r['free_e']:7d}",
            f"{r['n_dof']:7d}", f"{r['beta_fdtd']:10.4f}",
            f"{r['beta_eig']:10.4f}", f"{r['rel_gap_pct']:+8.4f}",
            f"{r['alpha_fdtd_db_per_mm']:10.6f}", f"{r['b_over_a']:8.5f}",
            f"{r['n_stations']:4d}", f"{r['wall_fdtd_s']:8.2f}",
            f"{r['wall_eig_s']:7.2f}", f"{r['peak_rss_mb']:8.1f}",
            f"{r['eps_eff_fdtd']:8.4f}", f"{r['eps_eff_eig']:8.4f}",
            f"{r['cavity_shift_pct']:7.3f}"))
    print("-" * 146)
    print("cav[%] is the distance of beta^2 below the k0^2*eps_r cavity ceiling "
          "(warning only, never an abort).")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="host_ladder.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "FDTD against the sparse mixed-pencil modal reference, on one box,\n"
            "across cell sizes h = H/n_sub (H = 1.6 mm).  Host-only: needs\n"
            "numpy, scipy and the repository importable.  Writes only --json,\n"
            "and writes nothing at all if a rung fails a hard check."),
        epilog=(
            "exit status 1 means a rung failed: peak RSS over the ceiling,\n"
            "attenuation over the floor, a residual over 1e-8, or a modal box\n"
            "that is not the FDTD box minus its absorbers.  The last line is\n"
            "always 'LADDER OK/FAIL rungs=N max_rel_gap=X%'.\n\n"
            "the default attenuation floor, 0.0139 dB/mm, is the most\n"
            "permissive of the three measured floors (default box fit 0.02145,\n"
            "npml10 span fit 0.0278, lid sweep 0.01388), so a rung that fails\n"
            "it is a genuine failure."))
    ap.add_argument("--max-rungs", type=int, default=3, metavar="N",
                    help="how many rungs to run, from coarse to fine "
                         "(default 3; 0 means all five)")
    ap.add_argument("--h", type=float, default=None, metavar="H_MM",
                    help="run this single cell size in mm instead of the "
                         "ladder")
    ap.add_argument("--clearance", type=float, default=3.0, metavar="NH",
                    help="lateral/top clearance, in units of H "
                         "(default 3.0)")
    ap.add_argument("--json", default=OUT_DEF, metavar="PATH",
                    help=f"where to write the results (default {OUT_DEF})")
    ap.add_argument("--mem-ceiling-mb", type=float, default=400.0,
                    metavar="MB", help="abort above this peak RSS "
                                       "(default 400)")
    ap.add_argument("--alpha-floor-db-per-mm", type=float, default=0.0139,
                    metavar="DB", help="abort above this FDTD attenuation "
                                       "(default 0.0139)")
    ap.add_argument("--npml", type=int, default=studies.MS_N_PML, metavar="N",
                    help=f"absorbing cells per face "
                         f"(default {studies.MS_N_PML})")
    ap.add_argument("--nsteps", type=int, default=None, metavar="N",
                    help="leapfrog steps; default scales MS_NSTEPS with the "
                         "cell so the record keeps its length in time")
    ap.add_argument("--strip-cells", type=int, default=studies.MS_N_STRIP,
                    metavar="N", help=f"strip width in cells "
                                      f"(default {studies.MS_N_STRIP})")
    ap.add_argument("--f0-ghz", type=float, default=F0_GHZ_DEF, metavar="F",
                    help=f"requested tone in GHz (default {F0_GHZ_DEF} = the "
                         f"tone the paper's k0 is at); both halves use the "
                         f"tone the FDTD actually accumulated at")
    ap.add_argument("--k", type=int, default=K_EIGS, metavar="K",
                    help=f"eigenpairs per rung (default {K_EIGS})")
    args = ap.parse_args(argv)

    rungs = RUNGS_MM if args.max_rungs == 0 else RUNGS_MM[:max(args.max_rungs, 0)]
    if args.h is not None:
        rungs = (args.h,)
    if not rungs:
        print("LADDER FAIL rungs=0 max_rel_gap=n/a: --max-rungs selected none")
        return 1

    peak_mb, branch = rss_mb()
    print(f"host_ladder: python {platform.python_version()} on "
          f"{platform.platform()}", flush=True)
    print(f"boxes: h/H = 1/{H_SUB/1e-3:g}*n_sub, clearance {args.clearance:g} H, "
          f"npml {args.npml}, strip {args.strip_cells} cells, "
          f"eps_r {ER:g}", flush=True)
    print(f"attenuation floor {args.alpha_floor_db_per_mm:g} dB/mm "
          f"(measured: default box fit 0.02145, npml10 span fit 0.0278, "
          f"lid sweep 0.01388 -- 0.0139 is the most permissive)", flush=True)
    print(f"eigs: k={args.k}, sigma={SIGMA_MULT:g}*k0^2*{ER:g}, "
          f"maxiter={EIGS_MAXITER}, tol={EIGS_TOL}, which=LM, "
          f"residual limit {TOL_RESID:g}", flush=True)
    print(f"peak rss {peak_mb:.1f} MB -- {branch}", flush=True)

    rows, t_start, failed = [], time.perf_counter(), None
    for h_mm in rungs:
        try:
            rows.append(run_rung(h_mm, args, branch))
        except LadderError as exc:
            failed = f"h = {h_mm:g} mm: {exc}"
            break
    wall_total = time.perf_counter() - t_start

    if failed is not None:
        peak_mb, _ = rss_mb()
        print(f"\nLADDER FAIL rungs={len(rows)} max_rel_gap="
              f"{(max((r['rel_gap_pct'] for r in rows), default=0.0)):.4f}%: "
              f"{failed}")
        print(f"no JSON written to {args.json}; {wall_total:.1f} s, peak "
              f"{peak_mb:.1f} MB")
        return 1

    print_table(rows)
    gap_max = max(abs(r["rel_gap_pct"]) for r in rows)
    peak_mb, _ = rss_mb()
    meta = dict(
        command_line=" ".join([os.path.basename(sys.argv[0])] + sys.argv[1:]),
        argv=list(sys.argv), git_rev=git_rev(),
        cwd=os.getcwd(), python=platform.python_version(),
        platform=platform.platform(), cpu_count=os.cpu_count(),
        rungs_mm=[float(r["h_mm"]) for r in rows],
        rungs_requested=[float(h) for h in rungs],
        max_rungs=int(args.max_rungs), clearance_h=float(args.clearance),
        strip_cells=int(args.strip_cells), npml=int(args.npml),
        eps_r=ER, h_substrate_m=H_SUB,
        sigma_mult=SIGMA_MULT,
        sigma_per_rung=[float(r["k0"] ** 2 * ER * SIGMA_MULT) for r in rows],
        sigma_note="sigma = sigma_mult * k0^2 * eps_r, k0 from the FDTD's "
                   "DFT-snapped tone for that rung",
        eigs=dict(solver="scipy.sparse.linalg.eigs (NOT eigsh: M is "
                         "indefinite)", k=int(args.k),
                  which="LM", maxiter=EIGS_MAXITER, tol=EIGS_TOL,
                  OPinv="one splu of (KC - sigma*MC), reused",
                  pencil="K=[[A,0],[0,0]], M=[[m,-c],[-c^T,h]], "
                         "A=0.5*((k0^2*m_eps-k_q)+(.)^T), "
                         "h=k_zz-k0^2*m_zz"),
        residual_limit=TOL_RESID,
        alpha_floor_db_per_mm=float(args.alpha_floor_db_per_mm),
        alpha_floor_note="decisions.md, clearance+1: 0.0139 +- 0.0026 dB/mm "
                         "over 14.4 mm; the most permissive of the three "
                         "measured floors (0.02145 / 0.0278 / 0.01388)",
        mem_ceiling_mb=float(args.mem_ceiling_mb),
        f0_requested_ghz=float(args.f0_ghz),
        rss_branch=branch,
        rss_basis="resource.getrusage(RUSAGE_SELF).ru_maxrss, a process-wide "
                  "high-water mark, so per-rung peak_rss_MB is cumulative",
        timings=dict(wall_total_s=float(wall_total),
                     fdtd_s=float(sum(r["wall_fdtd_s"] for r in rows)),
                     eig_s=float(sum(r["wall_eig_s"] for r in rows)),
                     assembly_s=float(sum(r["t_assembly_s"] for r in rows))),
        max_abs_rel_gap_pct=float(gap_max),
        peak_rss_mb=float(peak_mb),
        status="ok",
    )
    payload = dict(meta=meta, rungs=rows)
    path = args.json
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"\nJSON: {path}")
    print(f"wall total {wall_total:.1f} s "
          f"(FDTD {meta['timings']['fdtd_s']:.1f} s, "
          f"modal {meta['timings']['eig_s']:.1f} s), "
          f"peak RSS {peak_mb:.1f} MB")
    print(f"LADDER OK rungs={len(rows)} max_rel_gap={gap_max:.4f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
