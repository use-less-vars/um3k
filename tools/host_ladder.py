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
the repository and writes one file, the JSON named by ``--json``, on every run
that starts the ladder -- including the runs that stop early.  ``status`` in
that file says which one it is: ``"ok"`` is the whole sweep, ``"incomplete"``
is the rungs that did finish, with ``abort_reason`` and ``failure`` naming the
check that stopped the run and the rung it stopped on, so a partial sweep
arrives labelled instead of withheld.  Hard failures, each of which stops the
run with a non-zero exit:

  * peak RSS above ``--mem-ceiling-mb``;
  * an eigenpair whose residual exceeds ``1e-8``;
  * the modal box failing to match the FDTD box **in metres** -- width,
    height, cell, substrate thickness and strip width, all compared as
    lengths (an index-only comparison cannot see a length error).

``--alpha-floor-db-per-mm`` is deliberately *not* on that list: attenuation
is reported per rung on an ``ALPHA DIAGNOSTIC`` line and never changes the
exit status.

One structure, not five
-----------------------
The strip is a property of the line, so it is pinned in **metres**:
``--strip-width-mm`` (default 0.8) is converted to cells once per rung,
``n_strip = max(round(W/cell), 1)``, and the width actually meshed is printed
for every rung.  The old ``--strip-cells`` pinned the strip in *cells*
instead; because the cell size *is* the rung (``cell = H/n_sub``), the width
then walked 3.2 -> 1.07 mm over the five rungs, i.e. the ladder was five
different lines wearing one name -- and every rung still passed an
index-for-index box check.  ``--strip-cells`` survives only as a deprecated
override that warns on stderr.

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
    """A rung failed a hard check.  The ladder stops and labels the JSON."""


class MemoryCeilingError(LadderError):
    """A BUDGET abort, not a physics failure: the rung's own numbers are valid."""

    def __init__(self, message, *, h_mm, peak_mb, row):
        super().__init__(message)
        self.h_mm = float(h_mm)
        self.peak_mb = float(peak_mb)
        self.row = row


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


CGROUP_V2 = "/sys/fs/cgroup/memory.max"
CGROUP_V1 = "/sys/fs/cgroup/memory/memory.limit_in_bytes"
CGROUP_IMPLAUSIBLE_MB = 1e9           # cgroup v1 says "unlimited" with a huge number


def cgroup_limit_mb():
    """The cgroup memory limit in MB, or None when there is no finite limit."""
    for path in (CGROUP_V2, CGROUP_V1):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read().strip()
        except OSError:
            continue
        if not raw or raw == "max":
            return None
        try:
            value_mb = float(raw) / (1024.0 * 1024.0)
        except ValueError:
            continue
        if value_mb >= CGROUP_IMPLAUSIBLE_MB:
            return None
        return value_mb
    return None


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


def opt_float(value):
    """A plain float, or ``None`` when the fit refused to produce one.

    ``None`` covers all three ways a number can be missing here: the driver
    never computed it, it computed a NaN/inf, or it is not a number at all.
    Storing ``None`` keeps a refused fit distinguishable from a measured zero
    all the way into the JSON.
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---------------------------------------------------------------------------
# the strip: metres in, cells out
# ---------------------------------------------------------------------------
def grid_for(h_mm):
    """``(n_sub, cell_m)`` -- the substrate cell count and the cell it gives."""
    h_m = h_mm * 1e-3
    n_sub = int(round(H_SUB / h_m))
    if n_sub < 1:
        raise LadderError(f"h = {h_mm:g} mm is coarser than the substrate "
                          f"H = {H_SUB * 1e3:g} mm")
    return n_sub, H_SUB / n_sub


def resolve_strip(h_mm, args):
    """``(n_strip, w_m, w_requested_m)`` for one rung: the strip pinned in METRES.

    The strip width is a property of the *line*, so it must not move when the
    cell size moves.  The supported path takes ``--strip-width-mm`` and
    derives the cell count per rung, ``n_strip = max(round(W/cell), 1)``, so
    the meshed width is W to within half a cell on every rung.

    The deprecated ``--strip-cells`` pins the strip in *cells* instead.  With
    ``cell == h`` that makes W = n_strip * h, which walks 3.2 -> 1.07 mm over
    ``RUNGS_MM``: five different lines.  It still runs, but it says so, on
    stderr, once per rung.
    """
    _, cell = grid_for(h_mm)
    if args.strip_cells is not None:
        w_m = float(args.strip_cells) * cell
        print(
            f"WARNING: --strip-cells is DEPRECATED: it pins the strip width "
            f"in CELLS, not metres.  At h = {h_mm:g} mm it gives "
            f"n_strip = {args.strip_cells} and W = {w_m * 1e3:.6f} mm; "
            f"because cell == h the width DRIFTS WITH h across the ladder "
            f"and the rungs are NOT one structure.  Use --strip-width-mm "
            f"{args.strip_width_mm:g} instead.",
            file=sys.stderr, flush=True)
        return int(args.strip_cells), w_m, w_m
    w_requested_m = float(getattr(args, "strip_width_mm", 0.8)) * 1e-3
    n_strip = max(int(round(w_requested_m / cell)), 1)
    return n_strip, float(n_strip * cell), w_requested_m


# ---------------------------------------------------------------------------
# FDTD half
# ---------------------------------------------------------------------------
def run_fdtd(h_mm, *, clearance, npml, nsteps, f0_hz, n_strip, w_m):
    """One straight-guide microstrip run on the repository's own driver.

    The physical box is ``strip + 2 * (clearance * H)`` wide and
    ``H + clearance * H`` tall, with ``npml`` absorbing cells outside it on
    the two lateral faces and on top -- the geometry of the validated default
    record, moved by ``clearance`` only.  ``n_line`` is scaled with the cell
    so the stations at ``MS_X_FIRST``..``MS_X_LAST`` still lie inside the
    line; at the default cell it reproduces ``MS_N_LINE`` exactly.

    The strip arrives as a **pair**: ``w_m`` is the width in metres (what the
    physics is) and ``n_strip`` the whole number of cells it spans (what the
    mesh is).  They are produced together by :func:`resolve_strip`, so the
    driver can never silently mesh a width that is not the one asked for.
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
        h=H_SUB, w=w_m, eps_r=ER,
        n_sub=n_sub, n_air=n_edge, n_top=npml,
        n_strip=n_strip, n_clean=n_edge,
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


def build_modal(h_m, *, clearance, n_strip, w_m, k0, er=ER):
    """Assemble the transverse box and both pencils at cell ``h``."""
    nz_sub = int(round(H_SUB / h_m))
    if nz_sub < 1:
        raise LadderError(f"h = {h_m * 1e3:g} mm is coarser than H")
    cell = H_SUB / nz_sub
    # W is the strip the FDTD mesh actually contains (n_strip cells), not
    # dm's 0.8 mm default: dm re-derives ny_strip = round(W/cell), so W must
    # be the meshed width or the two boxes would differ by the rounding.
    geo = dm.section(h_m, clearance, H=H_SUB, W=w_m)
    if int(geo["ny_strip"]) != int(n_strip):
        raise LadderError(
            f"h = {h_m * 1e3:g} mm: the modal builder made a "
            f"{geo['ny_strip']}-cell strip out of W = {w_m * 1e3:g} mm but "
            f"the FDTD mesh has {n_strip} cells -- the two halves would be "
            f"different widths")
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

    The vector is used **complex**.  It used to be truncated with
    ``np.real(vec)`` first, and for a complex eigenvector the real part is not
    an eigenvector at all, so a perfectly good eigenpair printed a residual of
    ~1.0 -- which reads exactly like ``eigs`` failing to converge when it had
    in fact converged (the ``n_conv`` count says so).  The complex residual is
    the only one that means anything here, and ``c``/``h`` are real, so the
    complex solve is done as two real ones.
    """
    rows = []
    n_e = pb["n_e"]
    A, m1_f, c_f, lu_h, k_q_f = (pb["A"], pb["m1_f"], pb["c_f"],
                                 pb["lu_h"], pb["k_q_f"])
    for j in range(int(np.size(lam))):
        lj = complex(lam[j])
        ratio = abs(lj.imag) / max(1e-300, abs(lj))
        x = np.asarray(vec[:n_e, j], dtype=complex)
        nx = float(np.linalg.norm(x))
        if not (math.isfinite(nx) and nx > 0.0):
            continue
        x = x / nx
        l = float(lj.real)
        Ax = np.asarray(A @ x).ravel()
        cTx = np.asarray(c_f.T @ x).ravel()
        y = (lu_h.solve(np.ascontiguousarray(cTx.real))
             + 1j * lu_h.solve(np.ascontiguousarray(cTx.imag)))
        Bx = np.asarray(m1_f @ x).ravel() - np.asarray(c_f @ y).ravel()
        den = float(np.linalg.norm(Ax) + abs(lj) * np.linalg.norm(Bx))
        res = float(np.linalg.norm(Ax - lj * Bx) / den) if den > 0.0 else None
        m1x = float(np.real(np.conj(x) @ (m1_f @ x)))
        curl = (float(np.real(np.conj(x) @ (k_q_f @ x))) / m1x
                if m1x != 0.0 else None)
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
            and r["beta"] is not None and r["residual"] is not None
            and r["residual"] < TOL_RESID]
    if not good:
        return None, []
    good.sort(key=lambda r: r["beta_sq"], reverse=True)
    return good[0], good[:3]


# ---------------------------------------------------------------------------
# one rung
# ---------------------------------------------------------------------------
def no_candidate_reason(rows, rec, h_mm):
    """Why nothing was picked, keeping the two causes apart.

    "no physical candidate among N converged pairs" used to be one message for
    both a solver that returned nothing and a spectrum in which every pair was
    rejected by a guard, and it named neither the guard nor the count -- so a
    run whose 16 pairs had all converged and all failed the imaginary-part
    test looked exactly like an ARPACK failure.  It is not one: ``eigs``
    converged there, and the verdict was the guard's.
    """
    if not rows:
        return (f"h = {h_mm:g} mm: no converged pairs at all -- eigs returned "
                f"nothing for this pencil "
                f"({rec.get('eigs_error', 'no eigs error recorded')})")
    n = len(rows)
    n_imag = sum(1 for r in rows if not r["guard_imag"])
    n_curl = sum(1 for r in rows if not r["guard_curl"])
    n_eps = sum(1 for r in rows if not r["guard_eps"])
    # FIX: the residual gate now actually rejects, so it has to be reportable.
    # It used to be invisible here -- pick_mode accepted any non-None value --
    # and that is how an h=0.2 candidate with residual 9.86e-01 became "the
    # fundamental".  Naming the best rejected residual makes the verdict
    # legible instead of a bare "none physical".
    n_res = sum(1 for r in rows
                if r["residual"] is None or not r["residual"] < TOL_RESID)
    killers = [name for name, count in (("imag", n_imag), ("curl", n_curl),
                                        ("eps", n_eps),
                                        ("residual", n_res)) if count == n]
    ir = [r["imag_rel"] for r in rows]
    rr = [r["residual"] for r in rows if r["residual"] is not None]
    res_best = f"{min(rr):.2e}" if rr else "n/a (no residual recorded)"
    head = (f"h = {h_mm:g} mm: all {n} candidates rejected, best residual "
            f"{res_best}" if killers else
            f"h = {h_mm:g} mm: {n} converged pairs, none physical, best "
            f"residual {res_best}")
    return (f"{head} -- per-guard rejections: imag {n_imag}/{n} "
            f"(needs |imag|/|lam| < {TOL_RESID:g}), curl {n_curl}/{n} "
            f"(needs |curl| >= {CURL_FLOOR:g}), eps {n_eps}/{n} "
            f"(needs eps_eff < {ER - 1e-6:g}), residual {n_res}/{n} "
            f"(needs |residual| < {TOL_RESID:g}); guard(s) rejecting every "
            f"pair: {', '.join(killers) if killers else 'none'}; "
            f"|imag|/|lam| over the {n} pairs spans [{min(ir):.3e}, "
            f"{max(ir):.3e}].  eigs itself converged (n_conv = {n}), so this "
            f"is a spectrum/guard verdict, not a solver failure")


def npml_for_rung(args, h_mm):
    """Absorber cells for this rung: a fixed count, or a fixed depth in mm.

    The absorber's effect on beta and alpha tracks its thickness in
    MILLIMETRES, not its cell count, so a fixed --npml thins as h refines
    (2.4 mm at h = 0.4 down to 1.2 mm at h = 0.2).  --pml-mm holds the
    thickness fixed and re-derives the count on every rung.
    """
    if args.pml_mm is None:
        return int(args.npml)
    npml = max(3, int(round(args.pml_mm / h_mm)))
    if npml > 24:
        print(f"NOTE  h = {h_mm:g} mm: --pml-mm {args.pml_mm:g} mm needs "
              f"npml = {npml} cells per face (> 24 cells) -- that is where "
              f"the box gets expensive", file=sys.stderr, flush=True)
    return npml


def run_rung(h_mm, args, rss_branch):
    """FDTD and modal on the same box at one cell size; returns the row."""
    npml = npml_for_rung(args, h_mm)
    if args.pml_mm is None:
        print(f"\n=== rung h = {h_mm:g} mm ===", flush=True)
    else:
        print(f"\n=== rung h = {h_mm:g} mm (pml {args.pml_mm:g} mm -> "
              f"npml {npml}) ===", flush=True)
    n_strip, w_m, w_requested_m = resolve_strip(h_mm, args)
    fd = run_fdtd(h_mm, clearance=args.clearance, npml=npml,
                  nsteps=args.nsteps, f0_hz=args.f0_ghz * 1e9,
                  n_strip=n_strip, w_m=w_m)
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
    # the other three beta estimates the driver banks, kept beside the
    # one-wave fit rather than folded into it: a refused fit is None, never a
    # NaN dressed up as a measurement.
    beta_two_wave = opt_float(getattr(wave, "beta_two_wave", None))
    beta_two_station = opt_float(getattr(wave, "beta_two_station", None))
    beta_model = opt_float(getattr(wave, "beta_model", None))
    fit_residual_one = opt_float(getattr(wave, "fit_residual", None))
    print(f"  FDTD  cells={fd['n_cells']} nx,ny,nz="
          f"{gy['nx']},{gy['ny']},{gy['nz']} cell={gy['cell']*1e3:.6f} mm "
          f"nsteps={fd['nsteps']} f={float(gy['f'])/1e9:.6f} GHz "
          f"beta={beta_fdtd:.4f} alpha={alpha_db_mm:.6f} dB/mm "
          f"|b/a|={ba:.5f} stations={n_stations} wall={fd['wall']:.2f} s",
          flush=True)

    # FIX 4: attenuation is a DIAGNOSTIC, never a gate.  alpha scales with the
    # box (absorber, air and length all enter it), and the 0.0139 dB/mm floor
    # was calibrated on a *different* box, so using it to decide whether this
    # box's alpha is a failure would be testing the calibration rather than
    # the line.  It is reported here -- scaled by L/H so rungs of different
    # length can be read side by side -- and it never changes the exit status.
    l_mm = float(gy["length"]) * 1e3
    h_scale_mm = float(gy["h"]) * 1e3
    alpha_scaled = alpha_db_mm * (l_mm / h_scale_mm)
    alpha_over = bool(alpha_db_mm > args.alpha_floor_db_per_mm)
    print(f"  ALPHA DIAGNOSTIC h={h_mm:g} mm alpha={alpha_db_mm:.6f} dB/mm "
          f"alpha*(L/H)={alpha_scaled:.6f} dB/mm (L={l_mm:.4f} mm, "
          f"H={h_scale_mm:g} mm, L/H={l_mm / h_scale_mm:.4f}) "
          f"floor={args.alpha_floor_db_per_mm:g} dB/mm "
          f"{'WARNING: over the floor (WARNING ONLY, exit status unchanged)' if alpha_over else 'within the floor'}"
          f" -- diagnostic only, never an abort", flush=True)

    pb = build_modal(h_mm * 1e-3, clearance=args.clearance,
                     n_strip=n_strip, w_m=w_m, k0=k0)
    geo = pb["geo"]
    print(f"  GEO   h={h_mm:g} mm cell={float(geo['cell']) * 1e3:.6f} mm "
          f"n_sub={int(geo['nz_sub'])} n_strip={int(n_strip)} "
          f"W_mm={w_m * 1e3:.6f} ny={int(geo['ny'])} nz={int(geo['nz'])} "
          f"n_edges={int(pb['mesh'].n_edges)} free_e={pb['n_e']} "
          f"n_dof={pb['n_e'] + pb['n_n']}", flush=True)
    if args.strip_cells is None:
        # round(W/cell) can only differ from W by half a cell; more than that
        # means the strip was not pinned in metres after all.
        half_cell = 0.5 * float(geo["cell"]) + 1e-18
        if abs(w_m - w_requested_m) > half_cell:
            raise LadderError(
                f"h = {h_mm:g} mm: the meshed strip is {w_m * 1e3:.6f} mm but "
                f"--strip-width-mm asked for {w_requested_m * 1e3:g} mm -- "
                f"more than the half cell ({half_cell * 1e3:.6f} mm) that "
                f"round(W/cell) can explain, so the width is not pinned in "
                f"metres as it claims to be")

    # The whole point: the modal box must be the FDTD box minus its absorbers.
    # Compared as LENGTHS IN METRES, not as cell indices.  The old form of
    # this check compared geo["ny"] against ny - 2*npml -- an algebraic
    # identity between cell counts of the *same* build, so it could only ever
    # catch an off-by-one and was structurally incapable of noticing a length
    # error: it passed on every rung of a ladder whose strip width walked
    # 3.2 -> 1.07 mm.  Lengths can fail.  The two length invariants the
    # physics actually has -- substrate thickness and strip width -- are
    # compared here too, so a strip pinned in cells can no longer agree in
    # indices while differing in metres.
    cell_m = float(gy["cell"])
    want_w = (int(gy["ny"]) - 2 * int(gy["n_pml"])) * cell_m
    want_h = (int(gy["nz"]) - int(gy["n_top"])) * cell_m
    for name, got, want in (
            ("cell", float(geo["cell"]), cell_m),
            ("modal width", float(geo["ly"]), want_w),
            ("modal height", float(geo["lz"]), want_h),
            ("substrate thickness", float(geo["nz_sub"]) * float(geo["cell"]),
             float(gy["n_sub"]) * cell_m),
            ("strip width", float(geo["ny_strip"]) * float(geo["cell"]),
             float(gy["w"]))):
        if abs(got - want) > 1e-12:
            raise LadderError(
                f"h = {h_mm:g} mm: the boxes are not the same physical region "
                f"-- {name} is {got:.12e} m in the modal box but "
                f"{want:.12e} m in the FDTD box (modal ny,nz,strip = "
                f"{geo['ny']},{geo['nz']},{geo['ny_strip']} cells; FDTD "
                f"nx,ny,nz,strip = {gy['nx']},{gy['ny']},{gy['nz']},"
                f"{gy['n_strip']} cells, npml {gy['n_pml']}, n_top "
                f"{gy['n_top']})")
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
        print(f"  EIG   {len(rows)} converged pairs, none physical -- "
              f"per-pair verdicts below", flush=True)
        for r in sorted(rows, key=lambda r: r["lam"], reverse=True):
            print(f"        j={r['j']:2d} lam={r['lam']:.9e} "
                  f"|imag|/|lam|={r['imag_rel']:.4e} "
                  f"beta={num(r['beta'], '.6f')} "
                  f"eps_eff={num(r['eps_eff'], '.6f')} "
                  f"curl={num(r['curl_ratio'], '.3e')} "
                  f"res={num(r['residual'], '.3e')} "
                  f"imag={'pass' if r['guard_imag'] else 'FAIL'} "
                  f"curl={'pass' if r['guard_curl'] else 'FAIL'} "
                  f"eps={'pass' if r['guard_eps'] else 'FAIL'}", flush=True)
        raise LadderError(no_candidate_reason(rows, rec, h_mm))
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

    # All four beta estimates on one line: the one-wave fit is what the rest
    # of the table reports, so the two-wave fit, the two-station phase
    # difference and the Hammerstad-Jensen value are shown beside it -- with
    # the two spreads that say whether the number can be believed at all.
    # A missing fit prints as n/a through num() and never aborts the rung.
    d_one_two = (None if (beta_two_wave is None or not beta_fdtd)
                 else 100.0 * (beta_two_wave - beta_fdtd) / beta_fdtd)
    d_two_eig = (None if (beta_two_wave is None or not beta_eig)
                 else 100.0 * (beta_two_wave - beta_eig) / beta_eig)
    print(f"  BETA  fit_one={num(beta_fdtd)} fit_two={num(beta_two_wave)} "
          f"two_stn={num(beta_two_station)} HJ_model={num(beta_model)} "
          f"resid1={num(fit_residual_one, '.3e')}  "
          f"(fit_one vs fit_two: {num(d_one_two, '+.2f')}% ; "
          f"fit_two vs EIG: {num(d_two_eig, '+.2f')}%)", flush=True)

    gap_pct = 100.0 * (beta_eig - beta_fdtd) / beta_fdtd
    cavity_pct = 100.0 * (k0 * k0 * ER - beta_eig * beta_eig) / (k0 * k0 * ER)
    peak_mb, branch = rss_mb()
    if branch != rss_branch:
        raise LadderError(f"the ru_maxrss unit branch changed mid-run: "
                          f"{branch!r} against {rss_branch!r}")
    row = dict(
        h_mm=float(h_mm), cell_m=float(gy["cell"]), n_cells=fd["n_cells"],
        n_sub=int(gy["n_sub"]), n_strip=int(n_strip),
        strip_width_m=float(w_m), strip_width_mm=float(w_m * 1e3),
        grid=[int(gy["nx"]), int(gy["ny"]), int(gy["nz"])],
        npml=int(gy["n_pml"]), n_top=int(gy["n_top"]),
        pml_mm=(None if args.pml_mm is None else float(args.pml_mm)),
        nsteps=int(fd["nsteps"]), f_hz=float(gy["f"]),
        f_target_hz=float(gy["f_target"]), k0=float(k0),
        dt_s=float(gy["dt"]), n_acc=int(gy["n_acc"]),
        beta_fdtd=beta_fdtd, beta_eig=beta_eig, rel_gap_pct=float(gap_pct),
        beta_fit_one=beta_fdtd, beta_fit_two=beta_two_wave,
        beta_two_station=beta_two_station, beta_model=beta_model,
        fit_residual_one=fit_residual_one,
        alpha_fdtd_db_per_mm=alpha_db_mm, b_over_a=float(ba),
        alpha_scaled_L_over_H=float(alpha_scaled),
        alpha_floor_db_per_mm=float(args.alpha_floor_db_per_mm),
        alpha_floor_exceeded=bool(alpha_over),
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
        raise MemoryCeilingError(
            f"peak RSS {peak_mb:.1f} MB is over the "
            f"{args.mem_ceiling_mb:.1f} MB ceiling",
            h_mm=h_mm, peak_mb=peak_mb, row=row)
    # FIX 4: no attenuation gate.  --alpha-floor-db-per-mm now only labels
    # the ALPHA DIAGNOSTIC line above; exceeding it is a warning, not a
    # failure, and the exit status is untouched.
    return row


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def tone_facts(row):
    """The tone asked for, and the tone the DFT actually accumulated at."""
    f_req = float(row["f_target_hz"])
    f_act = float(row["f_hz"])
    span = float(row["n_acc"]) * float(row["dt_s"])
    detune = 100.0 * (f_act - f_req) / f_req
    return (f_req / 1e9, f_act / 1e9, detune, (1.0 / span) / 1e9,
            bool(abs(detune) > 0.1))


def print_tone(row):
    f_req, f_act, detune, bin_ghz, warn = tone_facts(row)
    print(f"  TONE  f_requested={f_req:.6f} GHz f_actual={f_act:.6f} GHz "
          f"detune={detune:+.3f} % bin=1/span={bin_ghz:.6f} GHz", flush=True)
    if warn:
        print(f"  TONE  WARNING: the FDTD ran at its nearest DFT bin "
              f"({f_act:.6f} GHz), not at f_requested ({f_req:.6f} GHz), so "
              f"this ladder's beta values are NOT directly comparable to the "
              f"d585 reference table (beta 385.0214743 / 383.5905830 / "
              f"382.8754929) or to tools/d585_sweep.py results (10.009557 GHz) "
              f"without rescaling by the k0 ratio "
              f"k0_actual/k0_requested = 213.747400/209.785703 = 1.0188875",
              flush=True)


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


def write_payload(path, meta, rows):
    """Write ``dict(meta=meta, rungs=rows)`` to ``path``; return the path.

    Called from BOTH exits of the ladder, so what a run measured survives the
    run.  ``meta["status"]`` is what tells the two files apart: ``"ok"`` is
    the whole sweep, ``"incomplete"`` is a labelled fragment carrying
    ``abort_reason`` and ``failure``, so a partial file can never be mistaken
    for a sweep.  An empty ``rows`` still writes a valid payload -- a ladder
    that died on its first rung is evidence too.
    """
    payload = dict(meta=meta, rungs=rows)
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="host_ladder.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "FDTD against the sparse mixed-pencil modal reference, on one box,\n"
            "across cell sizes h = H/n_sub (H = 1.6 mm).  Host-only: needs\n"
            "numpy, scipy and the repository importable.  Writes one file,\n"
            "--json, on every run that starts the ladder: its status says\n"
            "whether it is the whole sweep or the rungs that finished before\n"
            "a hard check stopped the run."),
        epilog=(
            "exit status 1 means a rung failed a HARD check, or the process\n"
            "ran out of its RSS budget: peak RSS over the ceiling, an\n"
            "eigenpair whose residual exceeds 1e-8, or a modal box that is not\n"
            "the FDTD box minus its absorbers (all compared in metres).  The\n"
            "verdict line reads 'LADDER OK/FAIL rungs=N max_rel_gap=X%' (a\n"
            "memory-ceiling abort says 'LADDER INCOMPLETE'), and the JSON is\n"
            "written either way: meta.status is 'ok' or 'incomplete', and an\n"
            "incomplete file names what stopped the run in meta.abort_reason\n"
            "('ladder_error' / 'memory_ceiling') and meta.failure.\n\n"
            "the strip is pinned in METRES by --strip-width-mm (default\n"
            "0.8 mm); the cell count is re-derived every rung, so all rungs\n"
            "mesh the SAME line.  --strip-cells is DEPRECATED: it pins the\n"
            "strip in CELLS, so W drifts with h (3.2 -> 1.07 mm over the five\n"
            "rungs) and the run warns on stderr.\n\n"
            "attenuation is NOT a failure condition.  --alpha-floor-db-per-mm\n"
            "only labels the ALPHA DIAGNOSTIC line: alpha is reported per rung,\n"
            "never gated, and never changes the exit status."))
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
    ap.add_argument("--mem-ceiling-mb", type=float, default=2000.0,
                    metavar="MB", help="abort above this peak RSS "
                                       "(default 2000, which suits a "
                                       "host/laptop run; a container should "
                                       "pass a value below its cgroup limit)")
    ap.add_argument("--alpha-floor-db-per-mm", type=float, default=0.0139,
                    metavar="DB",
                    help="WARNING threshold for the ALPHA DIAGNOSTIC line "
                         "(dB/mm).  DIAGNOSTIC ONLY -- this never changes "
                         "exit status (default 0.0139)")
    ap.add_argument("--npml", type=int, default=None, metavar="N",
                    help=f"absorbing cells per face, held as a FIXED CELL "
                         f"COUNT (default {studies.MS_N_PML}); mutually "
                         f"exclusive with --pml-mm")
    ap.add_argument("--pml-mm", type=float, default=None, metavar="MM",
                    help="absorbing-layer thickness in mm, held FIXED across "
                         "rungs: npml = max(3, round(MM/h)) re-derived on "
                         "every rung.  The absorber must be a fixed "
                         "PHYSICAL THICKNESS, not a fixed cell count -- with "
                         "a fixed --npml the layer thins as h refines (2.4 mm "
                         "at h = 0.4 down to 1.2 mm at h = 0.2), which "
                         "silently deflates the beta gap toward zero.  "
                         "Mutually exclusive with --npml.")
    ap.add_argument("--nsteps", type=int, default=None, metavar="N",
                    help="leapfrog steps; default scales MS_NSTEPS with the "
                         "cell so the record keeps its length in time")
    ap.add_argument("--strip-width-mm", type=float, default=0.8, metavar="W_MM",
                    help="physical strip width in mm, pinned across rungs; "
                         "cell count derived per rung (default 0.8)")
    ap.add_argument("--strip-cells", type=int, default=None, metavar="N",
                    help="DEPRECATED: fix the strip at N cells; W then "
                         "drifts with h.")
    ap.add_argument("--f0-ghz", type=float, default=F0_GHZ_DEF, metavar="F",
                    help=f"requested tone in GHz (default {F0_GHZ_DEF} = the "
                         f"tone the paper's k0 is at); both halves use the "
                         f"tone the FDTD actually accumulated at")
    ap.add_argument("--k", type=int, default=K_EIGS, metavar="K",
                    help=f"eigenpairs per rung (default {K_EIGS})")
    args = ap.parse_args(argv)
    if args.npml is not None and args.pml_mm is not None:
        ap.error("--npml and --pml-mm are mutually exclusive: --npml fixes "
                 "the absorber's CELL COUNT while --pml-mm fixes its "
                 "PHYSICAL THICKNESS (npml = round(pml_mm/h) per rung), so "
                 "only one of them can define the layer")
    if args.npml is None and args.pml_mm is None:
        args.npml = int(studies.MS_N_PML)

    cg_mb = cgroup_limit_mb()
    if cg_mb is not None and cg_mb < args.mem_ceiling_mb:
        print(f"WARN  CGROUP container memory limit {cg_mb:.1f} MB is below "
              f"--mem-ceiling-mb {args.mem_ceiling_mb:.1f} MB: the effective "
              f"ceiling is the cgroup limit ({cg_mb:.1f} MB), and the process "
              f"will be OOM-killed BEFORE the tool's own check can fire -- "
              f"pass --mem-ceiling-mb below {cg_mb:.1f} MB "
              f"(e.g. {cg_mb * 0.8:.0f}) so the run aborts cleanly instead",
              file=sys.stderr, flush=True)

    rungs = RUNGS_MM if args.max_rungs == 0 else RUNGS_MM[:max(args.max_rungs, 0)]
    if args.h is not None:
        rungs = (args.h,)
    if not rungs:
        print("LADDER FAIL rungs=0 max_rel_gap=n/a: --max-rungs selected none")
        return 1

    peak_mb, branch = rss_mb()
    print(f"host_ladder: python {platform.python_version()} on "
          f"{platform.platform()}", flush=True)
    strip_desc = (f"DEPRECATED --strip-cells {args.strip_cells} cells "
                  f"(W drifts with h)"
                  if args.strip_cells is not None
                  else f"--strip-width-mm {args.strip_width_mm:g} mm "
                       f"(pinned in metres)")
    pml_desc = (f"npml {args.npml}" if args.pml_mm is None else
                f"pml {args.pml_mm:g} mm -> npml round(pml/h) per rung")
    print(f"boxes: h/H = 1/{H_SUB/1e-3:g}*n_sub, clearance {args.clearance:g} H, "
          f"{pml_desc}, strip {strip_desc}, "
          f"eps_r {ER:g}", flush=True)
    print(f"attenuation floor {args.alpha_floor_db_per_mm:g} dB/mm -- "
          f"DIAGNOSTIC ONLY, never an abort "
          f"(measured: default box fit 0.02145, npml10 span fit 0.0278, "
          f"lid sweep 0.01388 -- 0.0139 is the most permissive)", flush=True)
    print(f"eigs: k={args.k}, sigma={SIGMA_MULT:g}*k0^2*{ER:g}, "
          f"maxiter={EIGS_MAXITER}, tol={EIGS_TOL}, which=LM, "
          f"residual limit {TOL_RESID:g}", flush=True)
    print(f"peak rss {peak_mb:.1f} MB -- {branch}", flush=True)

    rows, t_start, failed, aborted = [], time.perf_counter(), None, None
    for h_mm in rungs:
        try:
            rows.append(run_rung(h_mm, args, branch))
        except MemoryCeilingError as exc:
            # Not a physics failure: the rung's candidates are real, the
            # process just outgrew the budget we gave it.
            rows.append(exc.row)
            aborted = exc
            break
        except LadderError as exc:
            failed = f"h = {h_mm:g} mm: {exc}"
            break
        if len(rows) == 1:
            print_tone(rows[0])
    wall_total = time.perf_counter() - t_start

    if failed is not None:
        gap_max = max((r["rel_gap_pct"] for r in rows), default=0.0)
        print(f"\nLADDER FAIL rungs={len(rows)} max_rel_gap={gap_max:.4f}%: "
              f"{failed}")
        peak_mb, _ = rss_mb()
    else:
        print_table(rows)
        gap_max = max(abs(r["rel_gap_pct"]) for r in rows)
        peak_mb, _ = rss_mb()
    # A ladder that wrote no rung has no tone to report; None keeps the keys
    # present in the payload instead of dropping the whole meta block.
    tone = tone_facts(rows[0]) if rows else (None,) * 5
    meta = dict(
        command_line=" ".join([os.path.basename(sys.argv[0])] + sys.argv[1:]),
        argv=list(sys.argv), git_rev=git_rev(),
        cwd=os.getcwd(), python=platform.python_version(),
        platform=platform.platform(), cpu_count=os.cpu_count(),
        rungs_mm=[float(r["h_mm"]) for r in rows],
        rungs_requested=[float(h) for h in rungs],
        max_rungs=int(args.max_rungs), clearance_h=float(args.clearance),
        strip_width_mm=float(args.strip_width_mm),
        strip_cells=(None if args.strip_cells is None
                     else int(args.strip_cells)),
        strip_pinned=("metres: n_strip = max(round(W/cell), 1) per rung"
                      if args.strip_cells is None
                      else "cells (DEPRECATED): W = n_strip*cell drifts with h"),
        npml=(None if args.pml_mm is not None else int(args.npml)),
        pml_mm=(None if args.pml_mm is None else float(args.pml_mm)),
        npml_per_rung=[int(r["npml"]) for r in rows],
        npml_note="--pml-mm holds the absorber's physical thickness fixed, "
                  "so npml is re-derived per rung and varies across the "
                  "ladder; npml_per_rung is the count actually used",
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
        alpha_floor_note="DIAGNOSTIC ONLY: labels the ALPHA DIAGNOSTIC "
                         "line, never changes exit status.  decisions.md, "
                         "clearance+1: 0.0139 +- 0.0026 dB/mm over 14.4 mm; "
                         "the most permissive of the three measured floors "
                         "(0.02145 / 0.0278 / 0.01388)",
        alpha_floor_enforced=False,
        mem_ceiling_mb=float(args.mem_ceiling_mb),
        cgroup_limit_mb=(None if cg_mb is None else float(cg_mb)),
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
        tone_f_requested_ghz=tone[0],
        tone_f_actual_ghz=tone[1],
        tone_detune_pct=tone[2],
        tone_warn=tone[4],
        complete=(aborted is None and failed is None),
        abort_reason=("memory_ceiling" if aborted is not None
                      else ("ladder_error" if failed is not None else None)),
        status=("ok" if (aborted is None and failed is None)
                else "incomplete"),
    )
    if failed is not None:
        meta["failure"] = failed
    path = write_payload(args.json, meta, rows)

    if failed is not None:
        print(f"\npartial JSON: {path} ({len(rows)} of {len(rungs)} rungs, "
              f"status incomplete)")
        print(f"wall total {wall_total:.1f} s, peak RSS {peak_mb:.1f} MB")
        return 1
    print(f"\nJSON: {path}")
    print(f"wall total {wall_total:.1f} s "
          f"(FDTD {meta['timings']['fdtd_s']:.1f} s, "
          f"modal {meta['timings']['eig_s']:.1f} s), "
          f"peak RSS {peak_mb:.1f} MB")
    if aborted is not None:
        print(f"LADDER INCOMPLETE (memory ceiling) rungs={len(rows)} "
              f"max_rel_gap={gap_max:.4f}%: peak RSS {aborted.peak_mb:.1f} MB "
              f"exceeds --mem-ceiling-mb {args.mem_ceiling_mb:.1f} after rung "
              f"h = {aborted.h_mm:g} mm; all rungs up to and including this "
              f"one produced valid candidates (see table above)")
        return 1
    print(f"LADDER OK rungs={len(rows)} max_rel_gap={gap_max:.4f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
