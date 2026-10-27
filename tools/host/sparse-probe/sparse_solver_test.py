#!/usr/bin/env python3
"""Standalone probe: can the 2-D mixed mode pencil be solved *sparsely*?

Run:  python3 sparse_solver_test.py          (no arguments, no multiprocessing)

The production route (``emfit.mode2d.solve_modes_mixed``) forms a DENSE pencil
and hands it to a dense QZ.  That route is dead above ``free_e ~ 2400``.  This
script asks, on the two coarse rungs of the same discretisation, whether the
same pencil can be attacked with sparse factorisations instead, and how the
answer scales to ``free_e ~ 30000``.

Nothing here re-derives a dense reference: the targets are HARD-CODED from the
banked dense records (rung-0 31x17, rung-1 41x21).  Three routes are measured:

  Route A  shift-invert GENERALISED ``eigsh(A, M=B, sigma)`` with
           ``OPinv = splu(A - sigma B)``.  B carries ``c D c^T`` and is dense,
           so ``A - sigma B`` is structurally dense: the number of nonzeros of
           the matrix and of its LU factor is measured, not assumed.
  Route B  the enlarged (block) pencil from docs/design/sparse_eigenmode.md,
           ``K = [[A, -c], [-c^T, h]]``, ``M = diag(m1, 0)``, ``sigma = 1``,
           whose shift is structurally sparse.
  Route C  intentionally SKIPPED: plain shift-invert on the *transverse*
           operator with a diagonal mass is the wrong pencil, because
           ``B = m1 - c D c^T`` is not ``diag(m1)``.  Recorded, not run.

Route B2 (diagnostic, NOT in the design note) is the SAME enlarged pencil as
route B with the shift placed just below the dense target instead of
``sigma = 1``.  ``sigma = 1`` asks ARPACK for the eigenvalue nearest ONE, while
the fundamental sits at ``beta_sq ~ 1e5``; B2 therefore separates "wrong shift"
from "wrong pencil".  Both are reported.

Assembly/extraction is re-used from ``emfit`` (``mode2d.structured_mesh``,
``assemble``, ``assemble_mixed``, ``Mode2D``, ``mode_profile``) rather than from
``high_res_run.py``: importing that module would have meant touching a file
belonging to the live production run, and ``emfit`` is what ``high_res_run.py``
calls anyway.  That the re-used path is faithful is not assumed -- it is checked
here by reproducing the banked dense scalars to ~10 digits.

Per rung it checks the mesh/mask/block invariants against banked counts, forms
``A`` (sparse) and ``B`` (dense through ``c D c^T``), runs the routes, and
compares only SCALE-INVARIANT scalars against the dense targets: ``beta_sq``,
``R = sum(e_z_vv^2)/sum(e_y^2)`` and ``|corr|`` against the analytic plane
mode.  It then extrapolates the measured fill to ``free_e ~ 30000``, writes
``evidence/sparse/rung01_sparse_report.json``, and EXITS NONZERO when no sparse
route reproduces the committed reference (a spurious eigenpair must never be
reported as a success).

FORBIDDEN (task constraint) and therefore not touched: out/** and out/prev/**,
high_res_run.py/.sh, c1_audit.py, git, and any dense QZ/eig on the 2404-DOF
rung.  ``emfit`` is imported read-only.
"""

from __future__ import annotations

import json
import math
import os
import platform
import sys
import time
from pathlib import Path

# Thread caps BEFORE numpy/scipy are imported -- single-thread BLAS keeps the
# timings comparable between routes.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import numpy as np                                    # noqa: E402
import scipy.sparse as sp                             # noqa: E402
from scipy.sparse.linalg import (                     # noqa: E402
    ArpackNoConvergence,
    LinearOperator,
    eigsh,
    splu,
)

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import emfit.mode2d as m2                             # noqa: E402
import emfit.modal as M                               # noqa: E402
from emfit.mode_profile import microstrip_mode_profile  # noqa: E402

OUT_DIR = ROOT / "tools/host/sparse-probe/evidence/sparse"
OUT_JSON = OUT_DIR / "rung01_sparse_report.json"        # deliverable evidence file

# ---------------------------------------------------------------------------
# Hard-coded dense targets.  NEVER re-derived here.
# ---------------------------------------------------------------------------
RUNGS = {
    "rung0": {
        "name": "rung0_s12_a9_z8-4-4",
        "y_air": 9, "strip": 12, "z": (8, 4, 4),
        "mesh": {"nodes": 527, "tris": 960, "edges": 1486, "free_edges": 1444,
                 "free_nodes": 483, "nnz_h": 3141, "nnz_c": 5431},
        "dense": {"R": 4.0489791163950715,
                  "R_anchor_quoted": 4.0489791163982565,
                  "beta_sq": 97833.0578509992,
                  "beta": 312.7827646322591,
                  "eps_eff": 3.6295122080769704,
                  "corr_ey": 0.920770784810962,
                  "corr_ez_vv": 0.935286730348701,
                  "n_dof": 1927, "n_pec": 42, "n_eligible": None},
    },
    "rung1": {
        "name": "rung1_s16_a12_z10-5-5",
        "y_air": 12, "strip": 16, "z": (10, 5, 5),
        "mesh": {"nodes": 861, "tris": 1600, "edges": 2460, "free_edges": 2404,
                 "free_nodes": 803, "nnz_h": 5309, "nnz_c": 9163},
        "dense": {"R": 3.780331990015745,
                  "beta_sq": 97328.3081094,
                  "beta": 311.97485172,
                  "eps_eff": 3.610786479,
                  "corr_ey": 0.938008866588009,
                  "corr_ez_vv": 0.948121953787983,
                  "n_dof": 3207, "n_pec": 56, "n_eligible": 1},
    },
}
ORDER = ("rung0", "rung1")

# Acceptance thresholds for the verdict / exit code.  Loose on digits (a sparse
# pair converges to a relative residual, not to dense-QZ rounding) but strict on
# the residual: a small beta_sq that fell out of a NON-eigenvector must never be
# reported as a success -- that is the failure mode this probe guards against.
MIN_DIGITS_BETA_SQ = 6.0
MIN_DIGITS_R = 4.0
MAX_REL_RESIDUAL = 1e-8
# Route B is implemented as the design note prescribes (sigma = 1).  Route B2
# re-runs the IDENTICAL enlarged matrix with the shift just below the target;
# it is a diagnostic that separates "wrong shift" from "wrong pencil".
B2_SHIFT_FACTOR = 0.999

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def timed(fn):
    """``(value, seconds)``."""
    t0 = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - t0


def axis(edges, cells):
    pieces = [np.linspace(a, b, n + 1) for (a, b), n in zip(edges, cells)]
    out = pieces[0]
    for p in pieces[1:]:
        out = np.concatenate([out, p[1:]])
    return out


def corr(a, b):
    """Cosine overlap, copied verbatim from c1_audit.py:302-313."""
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0 or a.size != b.size:
        return float("nan")
    return float(np.sum(a * b) / (na * nb))


def dense_fro(arr):
    return float(np.sqrt(np.einsum("ij,ij->", arr, arr)))


def digits(measured, target):
    """Decimal digits of agreement; 16.0 when bit-identical."""
    if measured is None or not (np.isfinite(measured) and np.isfinite(target)):
        return None
    if target == 0.0:
        return None
    rel = abs(measured - target) / abs(target)
    if rel == 0.0:
        return 16.0
    return float(-math.log10(rel))


def rel_err(measured, target):
    if measured is None or not (np.isfinite(measured) and np.isfinite(target)):
        return None
    if target == 0.0:
        return None
    return float(abs(measured - target) / abs(target))


class CountedSolve:
    """``lu.solve`` wrapper counting matvecs (== ARPACK operator applications)."""

    def __init__(self, lu, shape):
        self.lu = lu
        self.shape = shape
        self.calls = 0

    def matvec(self, x):
        self.calls += 1
        return self.lu.solve(x)

    def operator(self):
        return LinearOperator(shape=self.shape, matvec=self.matvec, dtype=float)


def deterministic_v0(n):
    """Fixed-seed ARPACK start vector.

    ARPACK's default start vector is drawn from the global RNG, so the number of
    converged digits drifts by ~1e-8 between runs of the identical script.  That
    is fatal for an evidence file people are meant to re-run and compare, so the
    start vector is pinned here.
    """
    return np.random.RandomState(0).standard_normal(int(n))


def exception_text(exc):
    return f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# geometry / mesh
# ---------------------------------------------------------------------------
def load_context():
    tolflux = ROOT / ".scratch/tol/logs/TOLFLUX.json"
    g = json.loads(tolflux.read_text())["geometry"]
    W, H, HSUB = float(g["width"]), float(g["height"]), float(g["h"])
    WSTRIP, EPS_R = float(g["w"]), float(g["eps_r"])
    ctx = {
        "W": W, "H": H, "HSUB": HSUB, "WSTRIP": WSTRIP, "EPS_R": EPS_R,
        "N_SUB": int(g["n_sub"]), "K_STRIP": int(g["k_strip"]),
        "J_CENTRE": int(g["j_centre"]), "NY": int(g["ny"]), "NZ": int(g["nz"]),
        "CELL": float(g["cell"]), "FREQ": float(g["f"]),
        "ZZ1": 0.0036,                      # c1_audit.py ZS second breakpoint
        "Y0": W / 2.0 - WSTRIP / 2.0,
        "Y1": W / 2.0 + WSTRIP / 2.0,
    }
    ctx["k0"] = float(m2.k0_from_freq(ctx["FREQ"]))
    return ctx


def analytic_reference(ctx):
    """The plane-mode reference the |corr| anchors were measured against."""
    prof = microstrip_mode_profile(ctx["HSUB"], ctx["WSTRIP"], ctx["EPS_R"],
                                   n_sub=ctx["N_SUB"])
    nyn = ctx["NY"] + 1
    nzn = ctx["NZ"] + 1
    pana = M.plane_mode(prof, nyn=nyn, nzn=nzn, k_strip=ctx["K_STRIP"],
                        iy_strip_centre=ctx["J_CENTRE"], cell=ctx["CELL"])
    return {
        "e_y": np.asarray(pana.e_y, dtype=float),
        "e_z": np.asarray(pana.e_z, dtype=float),
        "eps_eff": float(getattr(prof, "eps_eff", float("nan"))),
        "shape_e_y": list(np.shape(pana.e_y)),
        "shape_e_z": list(np.shape(pana.e_z)),
    }


# ---------------------------------------------------------------------------
# field / scalar extraction
# ---------------------------------------------------------------------------
def mode2d_of(x_free, bsq, residual, sigma, mesh, ctx, n_e, free_e):
    """Build a Mode2D whose ``e_t`` is ``x_free`` (unit 2-norm, as the dense path)."""
    x = np.asarray(x_free, dtype=float).ravel()
    nrm = float(np.linalg.norm(x))
    if not (np.isfinite(nrm) and nrm > 0.0):
        return None, x
    x = x / nrm
    e_t = np.zeros(mesh.n_edges)
    e_t[free_e] = x
    beta = math.sqrt(bsq) if (np.isfinite(bsq) and bsq > 0.0) else float("nan")
    mode = m2.Mode2D(
        freq=ctx["FREQ"], k0=ctx["k0"], beta=beta, beta_sq=float(bsq),
        eps_eff=float(bsq) / ctx["k0"] ** 2 if np.isfinite(bsq) else float("nan"),
        residual=float(residual) if residual is not None else float("nan"),
        candidates=tuple(), curl_ratio=None, chosen=0, sigma=float(sigma),
        n_dof=int(mesh.n_edges - n_e + n_e),     # free edges + free nodes
        n_pec=int(mesh.n_edges - n_e),
        e_t=e_t, mesh=mesh, e_z=None,
    )
    return mode, x


def field_scalars(mode, ctx, ref):
    nyn, nzn = ctx["NY"] + 1, ctx["NZ"] + 1
    cell = ctx["CELL"]
    yn_node = np.arange(nyn) * cell
    zn_node = np.arange(nzn) * cell
    yc_mid = (np.arange(nyn - 1) + 0.5) * cell
    zc_mid = (np.arange(nzn - 1) + 0.5) * cell
    yy, zz = np.meshgrid(yc_mid, zn_node, indexing="ij")
    iyy, izz = np.meshgrid(yn_node, zc_mid, indexing="ij")
    ey_pts = np.stack([yy.ravel(), zz.ravel()], axis=1)
    ez_pts = np.stack([iyy.ravel(), izz.ravel()], axis=1)
    e_t = mode.e_at(ey_pts).reshape(nyn - 1, nzn, 2)
    e_y = e_t[:, :, 0] * cell
    e_tz = mode.e_at(ez_pts).reshape(nyn, nzn - 1, 2)
    e_z_vv = e_tz[:, :, 1] * cell
    num = float(np.sum(e_z_vv ** 2))
    den = float(np.sum(e_y ** 2))
    return {
        "R": (num / den) if den != 0.0 else float("nan"),
        "corr_ey": corr(ref["e_y"], e_y),
        "corr_ez_vv": corr(ref["e_z"], e_z_vv),
        "sum_e_y2": den,
        "sum_e_z_vv2": num,
    }


def compare_to_dense(scal, bsq, target, k0):
    eps_eff = bsq / k0 ** 2 if np.isfinite(bsq) else float("nan")
    return {
        "rel_err_beta_sq": rel_err(bsq, target["beta_sq"]),
        "digits_beta_sq": digits(bsq, target["beta_sq"]),
        "rel_err_R": rel_err(scal["R"], target["R"]),
        "digits_R": digits(scal["R"], target["R"]),
        "rel_err_eps_eff": rel_err(eps_eff, target["eps_eff"]),
        "abs_diff_corr_ey": (abs(abs(scal["corr_ey"]) - target["corr_ey"])
                             if np.isfinite(scal["corr_ey"]) else None),
        "abs_diff_corr_ez_vv": (abs(abs(scal["corr_ez_vv"]) - target["corr_ez_vv"])
                                if np.isfinite(scal["corr_ez_vv"]) else None),
    }


# ---------------------------------------------------------------------------
# per-rung solve
# ---------------------------------------------------------------------------
def run_rung(key, cfg, ctx, ref):
    target = cfg["dense"]
    exp_mesh = cfg["mesh"]
    print(f"\n=== {key}  ({cfg['name']}) ===", flush=True)

    xs = axis([(0.0, ctx["Y0"]), (ctx["Y0"], ctx["Y1"]), (ctx["Y1"], ctx["W"])],
              [cfg["y_air"], cfg["strip"], cfg["y_air"]])
    zs = axis([(0.0, ctx["HSUB"]), (ctx["HSUB"], ctx["ZZ1"]), (ctx["ZZ1"], ctx["H"])],
              list(cfg["z"]))
    mesh, t_mesh = timed(lambda: m2.structured_mesh(xs, zs))
    print(f"  mesh {xs.size}x{zs.size} nodes={mesh.n_nodes} tris={mesh.n_tris} "
          f"edges={mesh.n_edges} ({t_mesh:.2f}s)", flush=True)

    def eps_of(p):
        return np.where(p[:, 1] <= ctx["HSUB"] + 1e-12, ctx["EPS_R"], 1.0)

    def ground(p):
        return p[:, 1] == 0.0

    def strip(p):
        return (p[:, 1] == ctx["HSUB"]) & (p[:, 0] >= ctx["Y0"] - 1e-12) \
            & (p[:, 0] <= ctx["Y1"] + 1e-12)

    boundaries = (ground, strip)          # order matters for the PEC masks
    k0 = ctx["k0"]

    def assemble():
        return m2.assemble(mesh, eps_r=eps_of, mu_r=1.0)

    (k_q, m_mu, m_eps), t_assemble = timed(assemble)
    (m1, m_eps_m, c, k_zz, m_zz), t_assemble_mixed = timed(
        lambda: m2.assemble_mixed(mesh, eps_r=eps_of))
    d_m1 = float(np.max(np.abs((m1 - m_mu).toarray()))) if (m1 - m_mu).nnz else 0.0
    d_me = float(np.max(np.abs((m_eps_m - m_eps).toarray()))) if (m_eps_m - m_eps).nnz else 0.0
    print(f"  assembled ({t_assemble:.2f}s + {t_assemble_mixed:.2f}s), "
          f"max|m1-m_mu|={d_m1:g}, max|m_eps_m-m_eps|={d_me:g}", flush=True)

    edge_pec = m2.pec_edge_mask(mesh, boundaries)
    node_pec = m2.pec_node_mask(mesh, boundaries)
    free_e = np.flatnonzero(~edge_pec)
    free_n = np.flatnonzero(~node_pec)
    n_e, n_n = int(free_e.size), int(free_n.size)

    # --- blocks ------------------------------------------------------------
    h_blk = (k_zz[free_n][:, free_n]
             - k0 * k0 * m_zz[free_n][:, free_n]).tocsc()
    c_f = c[free_e][:, free_n].tocsc()
    m1_f = m1[free_e][:, free_e].tocsc()
    m_eps_f = m_eps[free_e][:, free_e].tocsc()
    k_q_f = k_q[free_e][:, free_e].tocsc()

    mesh_checks = {
        "nodes": {"measured": int(mesh.n_nodes), "expected": exp_mesh["nodes"]},
        "tris": {"measured": int(mesh.n_tris), "expected": exp_mesh["tris"]},
        "edges": {"measured": int(mesh.n_edges), "expected": exp_mesh["edges"]},
        "free_edges": {"measured": n_e, "expected": exp_mesh["free_edges"]},
        "free_nodes": {"measured": n_n, "expected": exp_mesh["free_nodes"]},
        "nnz_h": {"measured": int(h_blk.nnz), "expected": exp_mesh["nnz_h"]},
        "nnz_c": {"measured": int(c_f.nnz), "expected": exp_mesh["nnz_c"]},
        "n_pec_edges": {"measured": int(edge_pec.sum()),
                        "expected": exp_mesh["edges"] - exp_mesh["free_edges"]},
    }
    for _, chk in mesh_checks.items():
        chk["ok"] = bool(chk["measured"] == chk["expected"])
    ok_all = all(chk["ok"] for chk in mesh_checks.values())
    print(f"  checks all-ok={ok_all}: "
          + ", ".join(f"{k}={v['measured']}{'' if v['ok'] else '(!=' + str(v['expected']) + ')'}"
                      for k, v in mesh_checks.items()), flush=True)

    # --- longitudinal block ------------------------------------------------
    lu_h, t_splu_h = timed(lambda: splu(h_blk))
    d_dense, t_solve_D = timed(lambda: lu_h.solve(np.eye(n_n)))
    print(f"  splu(h) {t_splu_h:.3f}s  factor_nnz={lu_h.L.nnz + lu_h.U.nnz}  "
          f"D=solve(I) {t_solve_D:.3f}s", flush=True)

    # --- the two pencil blocks --------------------------------------------
    def form_A():
        a = (k0 * k0 * m_eps_f - k_q_f).tocsc()
        a.sum_duplicates()
        return (0.5 * (a + a.T)).tocsc()

    A, t_A = timed(form_A)

    def form_B():
        c_f_dense = c_f.toarray()
        b = m1_f.toarray() - (c_f @ d_dense) @ c_f_dense.T
        return 0.5 * (b + b.T)

    B, t_B = timed(form_B)
    a_fro = float(np.sqrt(float(A.multiply(A).sum())))
    b_fro = dense_fro(B)
    n2 = float(n_e * n_e)
    nnz_B = int(np.count_nonzero(B))
    print(f"  A sparse ({t_A:.3f}s) nnz={A.nnz};  B dense ({t_B:.3f}s) "
          f"nonzero={nnz_B}/{int(n2)} = {nnz_B / n2:.4f} of n^2", flush=True)

    result = {
        "key": key,
        "name": cfg["name"],
        "config": {"y_air": cfg["y_air"], "strip_cells": cfg["strip"],
                   "z_split": list(cfg["z"]),
                   "n_x_nodes": int(xs.size), "n_z_nodes": int(zs.size)},
        "mesh_checks": mesh_checks,
        "mesh_checks_ok": ok_all,
        "assembly": {"t_assemble_s": t_assemble,
                     "t_assemble_mixed_s": t_assemble_mixed,
                     "max_abs_m1_minus_m_mu": d_m1,
                     "max_abs_m_eps_m_minus_m_eps": d_me},
        "blocks": {"n_free_edges": n_e, "n_free_nodes": n_n,
                   "n_dense_pencil": n_e, "n_dense_squared": int(n2),
                   "nnz_A": int(A.nnz), "nnz_m1_f": int(m1_f.nnz),
                   "nnz_m_eps_f": int(m_eps_f.nnz), "nnz_k_q_f": int(k_q_f.nnz),
                   "nnz_c_f": int(c_f.nnz), "nnz_h": int(h_blk.nnz),
                   "nnz_B_nonzero": nnz_B,
                   "frac_B_nonzero_of_n2": nnz_B / n2,
                   "fro_A": a_fro, "fro_B": b_fro,
                   "t_form_A_s": t_A, "t_form_B_s": t_B},
        "longitudinal": {"t_splu_h_s": t_splu_h,
                         "factor_nnz_h": int(lu_h.L.nnz + lu_h.U.nnz),
                         "t_solve_D_s": t_solve_D},
        "dense_targets": target,
        "route_A": [],
    }

    # --- Route A: generalised shift-invert with the dense B ---------------
    sigmas = [1.0, 0.999 * target["beta_sq"], 1.001 * target["beta_sq"]]
    bcsc = sp.csc_matrix(B)
    for sigma in sigmas:
        entry = {"route": "A", "sigma": float(sigma)}
        try:
            S, t_S = timed(lambda: (A - float(sigma) * bcsc).tocsc())
        except Exception as exc:                        # pragma: no cover
            entry["build_error"] = exception_text(exc)
            result["route_A"].append(entry)
            continue
        entry["t_build_shifted_s"] = t_S
        entry["n"] = int(S.shape[0])
        entry["nnz_S"] = int(S.nnz)
        entry["nnz_S_of_n2"] = float(S.nnz) / n2
        entry["S_is_structurally_dense"] = bool(S.nnz > 0.5 * n2)
        entry["S_density"] = float(S.nnz) / n2
        try:
            lu_S, t_lu = timed(lambda: splu(S))
        except Exception as exc:
            entry["splu_error"] = exception_text(exc)
            print(f"  [A sigma={sigma:.6g}] splu FAILED: {exception_text(exc)}",
                  flush=True)
            result["route_A"].append(entry)
            continue
        fact_nnz = int(lu_S.L.nnz + lu_S.U.nnz)
        entry.update({
            "t_splu_s": t_lu,
            "factor_nnz": fact_nnz,
            "fill_ratio_factor_over_S": fact_nnz / float(max(S.nnz, 1)),
            "fill_per_row": fact_nnz / float(S.shape[0]),
            "factor_is_effectively_dense": bool(fact_nnz > 0.2 * n2),
        })
        op = CountedSolve(lu_S, S.shape)
        try:
            (w, v), t_eig = timed(lambda: eigsh(
                A, k=1, M=B, sigma=float(sigma), which="LM",
                OPinv=op.operator(), maxiter=5000,
                v0=deterministic_v0(A.shape[0])))
            entry["t_eigsh_s"] = t_eig
            entry["opinv_calls"] = op.calls
            entry["eigenvalue"] = float(np.real(w[0]))
        except ArpackNoConvergence as exc:
            entry["eigsh_error"] = exception_text(exc)
            entry["opinv_calls"] = op.calls
            entry["partial_eigenvalues"] = [float(np.real(z)) for z in
                                            np.atleast_1d(exc.eigenvalues)]
            print(f"  [A sigma={sigma:.6g}] eigsh NO CONVERGENCE "
                  f"({op.calls} calls): {exception_text(exc)}", flush=True)
            result["route_A"].append(entry)
            continue
        except Exception as exc:
            entry["eigsh_error"] = exception_text(exc)
            entry["opinv_calls"] = op.calls
            print(f"  [A sigma={sigma:.6g}] eigsh FAILED: {exception_text(exc)}",
                  flush=True)
            result["route_A"].append(entry)
            continue

        lam = float(np.real(w[0]))
        x = np.asarray(v[:, 0], dtype=float)
        xn = x / (np.linalg.norm(x) or 1.0)
        ax = np.asarray(A @ xn).ravel()
        bx = np.asarray(B @ xn).ravel()
        entry["rayleigh_true_pencil"] = float(xn @ ax / (xn @ bx))
        entry["residual"] = float(np.linalg.norm(ax - lam * bx)
                                 / ((a_fro + abs(lam) * b_fro) * np.linalg.norm(xn)))
        mode, _ = mode2d_of(x, lam, entry["residual"], sigma, mesh, ctx, n_e, free_e)
        if mode is None:
            entry["field_error"] = "unusable eigenvector (zero/NaN norm)"
            result["route_A"].append(entry)
            continue
        scal = field_scalars(mode, ctx, ref)
        entry["beta_sq"] = lam
        entry["eps_eff"] = lam / k0 ** 2
        entry["R"] = scal["R"]
        entry["corr_ey"] = scal["corr_ey"]
        entry["corr_ez_vv"] = scal["corr_ez_vv"]
        entry["comparison"] = compare_to_dense(scal, lam, target, k0)
        cmp = entry["comparison"]
        print(f"  [A sigma={sigma:.6g}] nnz(S)={S.nnz} ({entry['nnz_S_of_n2']:.3f} n^2) "
              f"fact={fact_nnz} fill/row={entry['fill_per_row']:.1f} "
              f"splu={t_lu:.2f}s eig={t_eig:.2f}s ({op.calls} calls) "
              f"beta_sq={lam:.6f} d={cmp['digits_beta_sq']:.1f} "
              f"R={scal['R']:.12f} d={cmp['digits_R']:.1f} "
              f"|cy|={abs(scal['corr_ey']):.12f} |cz|={abs(scal['corr_ez_vv']):.12f}",
              flush=True)
        result["route_A"].append(entry)

    # --- Route B: enlarged pencil from the design note ---------------------
    route_b = {"route": "B", "sigma": 1.0,
               "definition": "K=[[A,-c_f],[-c_f.T,h_blk]], M=diag(m1_f,0)"}
    zero_en = sp.csc_matrix((n_e, n_n))
    zero_nn = sp.csc_matrix((n_n, n_n))
    zero_ne = sp.csc_matrix((n_n, n_e))
    try:
        K, t_K = timed(lambda: sp.vstack(
            [sp.hstack([A, (-c_f).tocsc()], format="csc"),
             sp.hstack([(-c_f.T).tocsc(), h_blk], format="csc")], format="csc"))
        Mm, t_M = timed(lambda: sp.block_diag([m1_f, zero_nn], format="csc"))
        S_B, t_SB = timed(lambda: (K - 1.0 * Mm).tocsc())
    except Exception as exc:                            # pragma: no cover
        route_b["build_error"] = exception_text(exc)
        result["route_B"] = route_b
        print(f"  [B] build FAILED: {exception_text(exc)}", flush=True)
    else:
        big = float(S_B.shape[0])
        route_b.update({
            "n": int(S_B.shape[0]),
            "t_build_K_s": t_K, "t_build_M_s": t_M, "t_build_shifted_s": t_SB,
            "nnz_K": int(K.nnz), "nnz_M": int(Mm.nnz), "nnz_S": int(S_B.nnz),
            "nnz_S_of_n2": float(S_B.nnz) / (big * big),
            "S_density": float(S_B.nnz) / (big * big),
            "zero_blocks_present": True,
        })
        try:
            lu_B, t_lu_B = timed(lambda: splu(S_B))
            fact_nnz_B = int(lu_B.L.nnz + lu_B.U.nnz)
            route_b.update({
                "t_splu_s": t_lu_B,
                "factor_nnz": fact_nnz_B,
                "fill_ratio_factor_over_S": fact_nnz_B / float(S_B.nnz),
                "fill_per_row": fact_nnz_B / big,
                "factor_is_effectively_dense": bool(fact_nnz_B > 0.2 * big * big),
            })
        except Exception as exc:
            route_b["splu_error"] = exception_text(exc)
            print(f"  [B] splu FAILED: {exception_text(exc)}", flush=True)
            result["route_B"] = route_b
            result["route_A"] = result["route_A"]
            return result

        op_B = CountedSolve(lu_B, S_B.shape)
        lam_b = None
        x_b = None
        x_b_full = None
        try:
            (w, v), t_eig_B = timed(lambda: eigsh(
                K, k=1, M=Mm, sigma=1.0, which="LM",
                OPinv=op_B.operator(), maxiter=5000,
                v0=deterministic_v0(K.shape[0])))
            route_b["t_eigsh_s"] = t_eig_B
            route_b["opinv_calls"] = op_B.calls
            route_b["eigenvalue"] = float(np.real(w[0]))
            lam_b = float(np.real(w[0]))
            x_b_full = np.asarray(v[:, 0], dtype=float)
            x_b = x_b_full[:n_e]
        except ArpackNoConvergence as exc:
            route_b["eigsh_error"] = exception_text(exc)
            route_b["opinv_calls"] = op_B.calls
            route_b["partial_eigenvalues"] = [float(np.real(z))
                                              for z in np.atleast_1d(exc.eigenvalues)]
            try:
                x_b_full = np.asarray(exc.eigenvectors[:, 0], dtype=float)
                x_b = x_b_full[:n_e]
            except Exception:
                x_b = None
            print(f"  [B] eigsh NO CONVERGENCE ({op_B.calls} calls): "
                  f"{exception_text(exc)}", flush=True)
        except Exception as exc:
            route_b["eigsh_error"] = exception_text(exc)
            route_b["opinv_calls"] = op_B.calls
            print(f"  [B] eigsh FAILED: {exception_text(exc)}", flush=True)

        if x_b is not None and np.all(np.isfinite(x_b)):
            xn = x_b / (np.linalg.norm(x_b) or 1.0)
            ax = np.asarray(A @ xn).ravel()
            bx = np.asarray(B @ xn).ravel()
            rq = float(xn @ ax / (xn @ bx))
            route_b["rayleigh_true_pencil"] = rq
            if lam_b is not None:
                # residual of the FULL augmented vector in the augmented pencil
                # (the old version appended a zero second block, which measured
                # the truncation, not the eigenpair).
                if x_b_full is not None and np.all(np.isfinite(x_b_full)):
                    xf = x_b_full / (np.linalg.norm(x_b_full) or 1.0)
                else:
                    xf = np.concatenate([xn, np.zeros(n_n)])
                route_b["residual_in_enlarged_pencil"] = float(
                    np.linalg.norm(K @ xf - lam_b * (Mm @ xf))
                    / ((abs(lam_b) + 1.0) * np.linalg.norm(xf)))
                y_exp = d_dense @ (c_f.T @ xn)
                route_b["x2_matches_DcTx1_rel"] = float(
                    np.linalg.norm(xf[n_e:] / (np.linalg.norm(xf[n_e:]) or 1.0)
                                   - y_exp / (np.linalg.norm(y_exp) or 1.0)))
                route_b["rayleigh_condensed_pencil"] = float(
                    xn @ (ax - c_f @ (d_dense @ (c_f.T @ xn)))
                    / (xn @ np.asarray(m1_f @ xn).ravel()))
                route_b["residual"] = float(
                    np.linalg.norm(ax - lam_b * bx)
                    / ((a_fro + abs(lam_b) * b_fro) * np.linalg.norm(xn)))
                route_b["beta_sq_from_eigenvalue"] = lam_b
                route_b["beta_sq_from_rayleigh"] = rq
                mode_b, _ = mode2d_of(xn, rq, route_b.get("residual"), 1.0,
                                      mesh, ctx, n_e, free_e)
                if mode_b is not None:
                    scal = field_scalars(mode_b, ctx, ref)
                    route_b["R"] = scal["R"]
                    route_b["corr_ey"] = scal["corr_ey"]
                    route_b["corr_ez_vv"] = scal["corr_ez_vv"]
                    route_b["comparison"] = compare_to_dense(scal, rq, target, k0)
                    route_b["comparison_note"] = (
                        "beta_sq taken from the Rayleigh quotient of Route B's "
                        "eigenvector in the mode2d pencil, because the design-note "
                        "enlarged pencil is (A - c D c^T) x = lam m1 x, not "
                        "A x = lam (m1 - c D c^T) x")
                    cmp = route_b["comparison"]
                    print(f"  [B] nnz(S)={S_B.nnz} ({route_b['nnz_S_of_n2']:.5f} n^2) "
                          f"fact={fact_nnz_B} fill/row={route_b['fill_per_row']:.1f} "
                          f"splu={t_lu_B:.2f}s eig={route_b['t_eigsh_s']:.2f}s "
                          f"lam={lam_b:.6f} rqA={rq:.6f} "
                          f"rqcond={route_b['rayleigh_condensed_pencil']:.6f} "
                          f"x2dev={route_b['x2_matches_DcTx1_rel']:.3f} "
                          f"d={cmp['digits_beta_sq']:.1f} R={scal['R']:.12f} "
                          f"d={cmp['digits_R']:.1f} "
                          f"|cy|={abs(scal['corr_ey']):.12f} "
                          f"|cz|={abs(scal['corr_ez_vv']):.12f}", flush=True)
        result["route_B"] = route_b

        # --- Route B2: SAME enlarged pencil, shift moved onto the wanted mode -
        # The design note prescribes sigma = 1.0, but the fundamental sits at
        # beta_sq ~ 1e5, so sigma = 1 asks ARPACK for "the eigenvalue nearest
        # ONE", not for the fundamental: route B therefore answers a different
        # question than the dense reference does.  Re-running the identical
        # enlarged matrix with a shift just below the dense target separates
        # "wrong shift" from "wrong pencil".  This is a DIAGNOSTIC EXTENSION
        # recorded separately; route B (sigma = 1, as specified) stays above.
        sig2 = B2_SHIFT_FACTOR * float(target["beta_sq"])
        route_b2 = {"route": "B2", "sigma": sig2,
                    "definition": "K=[[A,-c_f],[-c_f.T,h_blk]], M=diag(m1_f,0)",
                    "note": ("diagnostic: identical enlarged pencil as route B, "
                             "shift placed just below the dense target instead "
                             "of the design note's sigma=1")}
        try:
            S_B2, route_b2["t_build_shifted_s"] = timed(
                lambda: (K - sig2 * Mm).tocsc())
            lu_B2, route_b2["t_splu_s"] = timed(lambda: splu(S_B2))
        except Exception as exc:                        # pragma: no cover
            route_b2["splu_error"] = exception_text(exc)
            print(f"  [B2] build/splu FAILED: {exception_text(exc)}", flush=True)
        else:
            big2 = float(S_B2.shape[0])
            fact2 = int(lu_B2.L.nnz + lu_B2.U.nnz)
            route_b2.update({
                "n": int(S_B2.shape[0]),
                "nnz_S": int(S_B2.nnz),
                "nnz_S_of_n2": float(S_B2.nnz) / (big2 * big2),
                "factor_nnz": fact2,
                "fill_per_row": fact2 / big2,
                "fill_ratio_factor_over_S": fact2 / float(max(S_B2.nnz, 1)),
                "factor_is_effectively_dense": bool(fact2 > 0.2 * big2 * big2),
            })
            op_B2 = CountedSolve(lu_B2, S_B2.shape)
            lam2 = None
            xf2 = None
            try:
                (w2, v2), route_b2["t_eigsh_s"] = timed(lambda: eigsh(
                    K, k=1, M=Mm, sigma=sig2, which="LM",
                    OPinv=op_B2.operator(), maxiter=5000,
                    v0=deterministic_v0(K.shape[0])))
                lam2 = float(np.real(w2[0]))
                route_b2["eigenvalue"] = lam2
                xf2 = np.asarray(v2[:, 0], dtype=float)
            except ArpackNoConvergence as exc:
                route_b2["eigsh_error"] = exception_text(exc)
                route_b2["partial_eigenvalues"] = [
                    float(np.real(z)) for z in np.atleast_1d(exc.eigenvalues)]
                try:
                    xf2 = np.asarray(exc.eigenvectors[:, 0], dtype=float)
                except Exception:
                    xf2 = None
                print(f"  [B2] eigsh NO CONVERGENCE: {exception_text(exc)}",
                      flush=True)
            except Exception as exc:
                route_b2["eigsh_error"] = exception_text(exc)
                print(f"  [B2] eigsh FAILED: {exception_text(exc)}", flush=True)
            route_b2["opinv_calls"] = op_B2.calls
            if xf2 is not None and np.all(np.isfinite(xf2)):
                nf2 = float(np.linalg.norm(xf2)) or 1.0
                x1 = xf2[:n_e]
                n1 = float(np.linalg.norm(x1))
                if np.isfinite(n1) and n1 > 0.0:
                    xn2 = x1 / n1
                    y_exp = d_dense @ (c_f.T @ xn2)
                    y_got = xf2[n_e:]
                    route_b2["x2_matches_DcTx1_rel"] = float(
                        np.linalg.norm(y_got / (np.linalg.norm(y_got) or 1.0)
                                       - y_exp / (np.linalg.norm(y_exp) or 1.0)))
                    if lam2 is not None:
                        route_b2["residual_in_enlarged_pencil"] = float(
                            np.linalg.norm(K @ xf2 - lam2 * (Mm @ xf2))
                            / ((abs(lam2) + 1.0) * nf2))
                    ax2 = np.asarray(A @ xn2).ravel()
                    bx2 = np.asarray(B @ xn2).ravel()
                    route_b2["rayleigh_true_pencil"] = float(
                        xn2 @ ax2 / (xn2 @ bx2))
                    m1x = np.asarray(m1_f @ xn2).ravel()
                    cond_x = ax2 - c_f @ (d_dense @ (c_f.T @ xn2))
                    route_b2["rayleigh_condensed_pencil"] = float(
                        xn2 @ cond_x / (xn2 @ m1x))
                    if lam2 is not None:
                        m1_fro = math.sqrt(float(m1_f.multiply(m1_f).sum()))
                        res_cond = float(
                            np.linalg.norm(cond_x - lam2 * m1x)
                            / ((a_fro + abs(lam2) * m1_fro) * n1))
                        route_b2["residual_condensed_pencil"] = res_cond
                        mode2, _ = mode2d_of(xn2, lam2, res_cond, 1.0, mesh,
                                             ctx, n_e, free_e)
                        if mode2 is not None:
                            scal2 = field_scalars(mode2, ctx, ref)
                            route_b2["R"] = scal2["R"]
                            route_b2["corr_ey"] = scal2["corr_ey"]
                            route_b2["corr_ez_vv"] = scal2["corr_ez_vv"]
                            route_b2["comparison"] = compare_to_dense(
                                scal2, lam2, target, k0)
                            c2 = route_b2["comparison"]
                            print(f"  [B2 sigma={sig2:.6g}] nnz(S)={S_B2.nnz} "
                                  f"({route_b2['nnz_S_of_n2']:.5f} n^2) "
                                  f"fact={fact2} "
                                  f"fill/row={route_b2['fill_per_row']:.1f} "
                                  f"splu={route_b2['t_splu_s']:.2f}s "
                                  f"eig={route_b2['t_eigsh_s']:.2f}s "
                                  f"lam={lam2:.6f} "
                                  f"rqA={route_b2['rayleigh_true_pencil']:.6f} "
                                  f"rqcond={route_b2['rayleigh_condensed_pencil']:.6f} "
                                  f"d={c2['digits_beta_sq']:.1f} "
                                  f"R={scal2['R']:.12f} d={c2['digits_R']:.1f} "
                                  f"|cy|={abs(scal2['corr_ey']):.12f} "
                                  f"|cz|={abs(scal2['corr_ez_vv']):.12f}", flush=True)
        result["route_B2"] = route_b2

    # --- Route C: documented skip -----------------------------------------
    result["route_C"] = {
        "route": "C",
        "status": "skipped",
        "reason": ("plain shift-invert on A with a DIAGONAL mass is the wrong "
                   "pencil: B = m1 - c h^-1 c^T is not diag(m1), so the "
                   "eigenvalues of the diagonal-mass problem are not the "
                   "beta^2 of the mixed formulation. Recorded as a decision, "
                   "not run."),
    }
    return result


# ---------------------------------------------------------------------------
# extrapolation
# ---------------------------------------------------------------------------
BYTES_PER_NNZ = 12          # SuperLU CSC factor: 8 data + 4 index


def _fit_power(x0, y0, x1, y1):
    if not (x0 > 0 and x1 > 0 and y0 > 0 and y1 > 0) or x0 == x1:
        return None, None
    p = math.log(y1 / y0) / math.log(x1 / x0)
    c = y0 / (x0 ** p)
    return p, c


def extrapolate(res0, res1, big_free_e=30000.0):
    out = {"target_free_e": big_free_e,
           "bytes_per_factor_nnz": BYTES_PER_NNZ}
    nA0, nA1 = float(res0["blocks"]["n_free_edges"]), float(res1["blocks"]["n_free_edges"])
    nB0 = float(res0["blocks"]["n_free_edges"] + res0["blocks"]["n_free_nodes"])
    nB1 = float(res1["blocks"]["n_free_edges"] + res1["blocks"]["n_free_nodes"])
    node_ratio = nB1 / nA1                       # (n_e + n_n) / n_e at rung-1
    nA_big = big_free_e
    nB_big = big_free_e * node_ratio
    out["enlarged_dim_ratio_rung1"] = node_ratio
    out["dims"] = {"A": {"n0": nA0, "n1": nA1, "n_big": nA_big},
                   "B": {"n0": nB0, "n1": nB1, "n_big": nB_big}}

    def route_block(entries0, entries1, dims, label):
        block = {}
        f0 = [e.get("fill_per_row") for e in entries0 if e.get("fill_per_row")]
        f1 = [e.get("fill_per_row") for e in entries1 if e.get("fill_per_row")]
        if not (f0 and f1):
            return {"note": "no measured factor for this route"}
        fr0, fr1 = float(np.mean(f0)), float(np.mean(f1))
        p, c = _fit_power(dims["n0"], fr0, dims["n1"], fr1)
        fr_big = (c * dims["n_big"] ** p) if (p is not None) else None
        block.update({"fill_per_row_rung0": fr0, "fill_per_row_rung1": fr1,
                      "fill_per_row_exponent": p,
                      "fill_per_row_at_big": fr_big})
        if fr_big is not None:
            fact_big = fr_big * dims["n_big"]
            block["factor_nnz_at_big"] = fact_big
            block["factor_memory_gb"] = fact_big * BYTES_PER_NNZ / 1e9
            block["factor_memory_gb_dense_reference"] = (
                dims["n_big"] ** 2 * BYTES_PER_NNZ / 1e9)
        # time fit over the measured splu times
        t0 = [e.get("t_splu_s") for e in entries0 if e.get("t_splu_s")]
        t1 = [e.get("t_splu_s") for e in entries1 if e.get("t_splu_s")]
        if t0 and t1:
            ft0 = [e.get("factor_nnz") for e in entries0 if e.get("factor_nnz")]
            ft1 = [e.get("factor_nnz") for e in entries1 if e.get("factor_nnz")]
            if ft0 and ft1:
                tp, tc = _fit_power(float(np.mean(ft0)), float(np.mean(t0)),
                                    float(np.mean(ft1)), float(np.mean(t1)))
                block["splu_time_exponent_vs_factor_nnz"] = tp
                if tp is not None and "factor_nnz_at_big" in block:
                    block["splu_time_at_big_s"] = tc * block["factor_nnz_at_big"] ** tp
        block["label"] = label
        return block

    out["route_A"] = route_block(res0["route_A"], res1["route_A"],
                                 out["dims"]["A"], "dense-B shift-invert")
    out["route_B"] = route_block([res0.get("route_B", {})], [res1.get("route_B", {})],
                                 out["dims"]["B"], "enlarged sparse pencil")
    out["route_B2"] = route_block([res0.get("route_B2", {})],
                                  [res1.get("route_B2", {})],
                                  out["dims"]["B"],
                                  "enlarged sparse pencil, shift at target")
    out["design_note_anchors"] = {
        "source": "docs/design/sparse_eigenmode.md",
        "fill_per_row": [{"n": 1431, "fill_per_row": 53.7},
                         {"n": 1927, "fill_per_row": 56.5, "nnz_S": 20991,
                          "factor_nnz": 108906, "splu_s": 0.008, "solve_ms": 0.38},
                         {"n": 13583, "fill_per_row": 58.7},
                         {"n": 60587, "fill_per_row": 137.9, "nnz_S": 687031,
                          "factor_nnz": 8352700, "splu_s": 0.38, "solve_ms": 12.82}],
    }
    return out


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def print_table(results, ext):
    print("\n" + "=" * 132)
    print("SPARSE FORMULATION PROBE -- measured vs hard-coded dense targets")
    print("=" * 132)
    hdr = (f"{'rung':6s} {'route':5s} {'sigma':>12s} {'n':>5s} {'nnz(S)':>9s} "
           f"{'nnz/n^2':>8s} {'factor':>9s} {'fill/row':>8s} {'splu s':>7s} "
           f"{'eig s':>6s} {'calls':>5s} {'beta_sq':>14s} {'dig_b':>5s} "
           f"{'R':>16s} {'dig_R':>5s} {'|corr_ey|':>12s} {'|corr_ez|':>12s}")
    print(hdr)
    print("-" * 132)
    for key in ORDER:
        res = results[key]
        tgt = res["dense_targets"]
        print(f"{key:6s} {'dense':5s} {'-':>12s} {res['blocks']['n_dense_pencil']:5d} "
              f"{res['blocks']['nnz_A']:9d} {'-':>8s} {'-':>9s} {'-':>8s} "
              f"{'-':>7s} {'-':>6s} {'-':>5s} {tgt['beta_sq']:14.6f} {'-':>5s} "
              f"{tgt['R']:16.12f} {'-':>5s} {tgt['corr_ey']:12.9f} "
              f"{tgt['corr_ez_vv']:12.9f}")
        for e in res["route_A"]:
            if "beta_sq" in e:
                c = e["comparison"]
                print(f"{key:6s} {'A':5s} {e['sigma']:12.6g} {e['n']:5d} "
                      f"{e['nnz_S']:9d} {e['nnz_S_of_n2']:8.3f} {e['factor_nnz']:9d} "
                      f"{e['fill_per_row']:8.1f} {e['t_splu_s']:7.2f} "
                      f"{e['t_eigsh_s']:6.2f} {e['opinv_calls']:5d} "
                      f"{e['beta_sq']:14.6f} {c['digits_beta_sq']:5.1f} "
                      f"{e['R']:16.12f} {c['digits_R']:5.1f} "
                      f"{abs(e['corr_ey']):12.9f} {abs(e['corr_ez_vv']):12.9f}")
            else:
                err = e.get("splu_error") or e.get("eigsh_error") or e.get("build_error")
                print(f"{key:6s} {'A':5s} {e['sigma']:12.6g} {e.get('n', 0):5d} "
                      f"{e.get('nnz_S', 0):9d} {e.get('nnz_S_of_n2', float('nan')):8.3f} "
                      f"{e.get('factor_nnz', 0):9d} ..      ..      ..     FAILED: {err}")
        b = res.get("route_B", {})
        if "R" in b:
            c = b["comparison"]
            print(f"{key:6s} {'B':5s} {1.0:12.6g} {b['n']:5d} {b['nnz_S']:9d} "
                  f"{b['nnz_S_of_n2']:8.5f} {b['factor_nnz']:9d} "
                  f"{b['fill_per_row']:8.1f} {b['t_splu_s']:7.2f} "
                  f"{b['t_eigsh_s']:6.2f} {b['opinv_calls']:5d} "
                  f"{b['rayleigh_true_pencil']:14.6f} {c['digits_beta_sq']:5.1f} "
                  f"{b['R']:16.12f} {c['digits_R']:5.1f} "
                  f"{abs(b['corr_ey']):12.9f} {abs(b['corr_ez_vv']):12.9f}")
        else:
            print(f"{key:6s} {'B':5s} {1.0:12.6g} {b.get('n', 0):5d} "
                  f"{b.get('nnz_S', 0):9d} {b.get('nnz_S_of_n2', float('nan')):8.5f} "
                  f"{b.get('factor_nnz', 0):9d} ..      ..      ..     "
                  f"FAILED: {b.get('splu_error') or b.get('eigsh_error')}")
        b2 = res.get("route_B2", {})
        if "R" in b2:
            c2 = b2["comparison"]
            print(f"{key:6s} {'B2':5s} {b2['sigma']:12.6g} {b2['n']:5d} "
                  f"{b2['nnz_S']:9d} {b2['nnz_S_of_n2']:8.5f} {b2['factor_nnz']:9d} "
                  f"{b2['fill_per_row']:8.1f} {b2['t_splu_s']:7.2f} "
                  f"{b2['t_eigsh_s']:6.2f} {b2['opinv_calls']:5d} "
                  f"{b2['eigenvalue']:14.6f} {c2['digits_beta_sq']:5.1f} "
                  f"{b2['R']:16.12f} {c2['digits_R']:5.1f} "
                  f"{abs(b2['corr_ey']):12.9f} {abs(b2['corr_ez_vv']):12.9f}")
        else:
            print(f"{key:6s} {'B2':5s} {b2.get('sigma', float('nan')):12.6g} "
                  f"{b2.get('n', 0):5d} {b2.get('nnz_S', 0):9d} "
                  f"{b2.get('nnz_S_of_n2', float('nan')):8.5f} "
                  f"{b2.get('factor_nnz', 0):9d} ..      ..      ..     "
                  f"FAILED: {b2.get('splu_error') or b2.get('eigsh_error')}")
    print("-" * 132)
    print("route C: skipped by design (B is not diag(m1); see JSON 'route_C')")
    print("note: for route B/B2 the beta_sq column is the Rayleigh quotient in the")
    print("      route-A pencil (A x = lam (m1 - c D c^T) x); for route A it is the")
    print("      returned eigenvalue of that same pencil.  B2 = route B's own enlarged")
    print("      pencil with the shift moved onto the target (diagnostic).")
    print("=" * 132)
    print("\nEXTRAPOLATION to free_e ~ 30000")
    for label, dim_key in (("route_A", "A"), ("route_B", "B"),
                           ("route_B2", "B")):
        blk = ext[label]
        if "factor_nnz_at_big" in blk:
            print(f"  {label} ({blk['label']}): fill/row {blk['fill_per_row_rung0']:.1f} "
                  f"-> {blk['fill_per_row_rung1']:.1f} (exponent "
                  f"{blk['fill_per_row_exponent']:.2f}); at n={ext['dims'][dim_key]['n_big']:.0f}: "
                  f"factor_nnz {blk['factor_nnz_at_big']:.3e}, "
                  f"~{blk['factor_memory_gb']:.1f} GB factor, "
                  f"splu ~{blk.get('splu_time_at_big_s', float('nan')):.1f} s")
        else:
            print(f"  {label}: {blk}")
    print()


def main():
    t_start = time.perf_counter()
    ctx = load_context()
    print(f"workspace {ROOT}")
    print(f"k0 = {ctx['k0']!r}  f = {ctx['FREQ']!r}  cell = {ctx['CELL']}")
    print(f"Y0 = {ctx['Y0']}  Y1 = {ctx['Y1']}  HSUB = {ctx['HSUB']}  "
          f"eps_r = {ctx['EPS_R']}")
    ref = analytic_reference(ctx)
    print(f"analytic plane mode: {ref['shape_e_y']} / {ref['shape_e_z']}, "
          f"eps_eff = {ref['eps_eff']!r}", flush=True)

    results = {}
    for key in ORDER:
        results[key] = run_rung(key, RUNGS[key], ctx, ref)

    ext = extrapolate(results["rung0"], results["rung1"])
    print_table(results, ext)

    payload = {
        "probe": "sparse formulations of the 2-D mixed mode pencil",
        "script": "tools/host/sparse-probe/sparse_solver_test.py",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "thread_env": {v: os.environ.get(v) for v in
                           ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                            "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
        },
        "geometry": {k: ctx[k] for k in ("W", "H", "HSUB", "WSTRIP", "EPS_R",
                                         "N_SUB", "K_STRIP", "J_CENTRE", "NY",
                                         "NZ", "CELL", "FREQ", "Y0", "Y1",
                                         "ZZ1", "k0")},
        "analytic_reference": {"eps_eff": ref["eps_eff"],
                               "shape_e_y": ref["shape_e_y"],
                               "shape_e_z": ref["shape_e_z"]},
        "targets_note": ("targets are hard-coded from the banked dense records; "
                         "this probe never runs a dense QZ/eig on them"),
        "routes": {"A": "eigsh(A, M=B, sigma, OPinv=splu(A-sigma*B)) -- B dense",
                   "B": "enlarged K=[[A,-c],[-c^T,h]], M=diag(m1,0), sigma=1",
                   "C": "skipped (wrong pencil: B != diag(m1))"},
        "rungs": results,
        "extrapolation": ext,
        "wall_seconds": time.perf_counter() - t_start,
    }
    # ---- verdict: does a sparse route reproduce the dense reference? -----
    def best_A(res):
        ok = [e for e in res["route_A"] if "beta_sq" in e]
        if not ok:
            return None
        return max(ok, key=lambda e: e["comparison"]["digits_beta_sq"])

    def status_of(entry):
        if "R" not in entry:
            return "NO_EIGENPAIR", None
        cmp_ = entry["comparison"]
        resid = entry.get("residual")
        ok = (cmp_["digits_beta_sq"] >= MIN_DIGITS_BETA_SQ
              and cmp_["digits_R"] >= MIN_DIGITS_R
              and resid is not None and math.isfinite(resid)
              and resid <= MAX_REL_RESIDUAL)
        return ("REPRODUCES_REFERENCE" if ok else "DISAGREES"), cmp_

    verdict = {"thresholds": {"min_digits_beta_sq": MIN_DIGITS_BETA_SQ,
                              "min_digits_R": MIN_DIGITS_R,
                              "max_rel_residual": MAX_REL_RESIDUAL},
               "route_A": {}, "route_B": {}, "route_B2": {}, "overall": {}}
    for key in ORDER:
        res = results[key]
        e = best_A(res)
        if e is None:
            verdict["route_A"][key] = {
                "status": "NO_EIGENPAIR",
                "why": "every shift failed; see routes.rungX.route_A"}
        else:
            st, c = status_of(e)
            verdict["route_A"][key] = {
                "status": st, "sigma": e["sigma"], "beta_sq": e["beta_sq"],
                "digits_beta_sq": c["digits_beta_sq"], "R": e["R"],
                "digits_R": c["digits_R"], "rel_residual": e.get("residual"),
                "nnz_S": e["nnz_S"], "nnz_S_of_n2": e["nnz_S_of_n2"],
                "factor_nnz": e["factor_nnz"],
                "fill_per_row": e["fill_per_row"],
                "factor_is_effectively_dense":
                    e["factor_is_effectively_dense"]}
        for tag, label in (("route_B", "route_B"), ("route_B2", "route_B2")):
            b = res.get(tag, {})
            st, c = status_of(b)
            verdict[label][key] = {
                "status": st, "sigma": b.get("sigma"),
                "eigenvalue": b.get("eigenvalue"),
                "beta_sq_rayleigh_routeA": b.get("rayleigh_true_pencil"),
                "beta_sq_rayleigh_condensed": b.get("rayleigh_condensed_pencil"),
                "digits_beta_sq": (c or {}).get("digits_beta_sq"),
                "digits_R": (c or {}).get("digits_R"),
                "rel_residual_routeA_pencil": b.get("residual"),
                "rel_residual_enlarged": b.get("residual_in_enlarged_pencil"),
                "x2_matches_DcTx1_rel": b.get("x2_matches_DcTx1_rel"),
                "nnz_S": b.get("nnz_S"), "factor_nnz": b.get("factor_nnz"),
                "fill_per_row": b.get("fill_per_row"),
                "factor_is_effectively_dense":
                    b.get("factor_is_effectively_dense"),
                "error": b.get("build_error") or b.get("splu_error")
                         or b.get("eigsh_error")}

    a_all = all(v["status"] == "REPRODUCES_REFERENCE"
                for v in verdict["route_A"].values())
    b_all = all(v["status"] == "REPRODUCES_REFERENCE"
                for v in verdict["route_B"].values())
    b2_all = all(v["status"] == "REPRODUCES_REFERENCE"
                 for v in verdict["route_B2"].values())
    exit_code = 0 if (a_all or b2_all) else 1
    verdict["overall"] = {
        "route_A_reproduces_reference": bool(a_all),
        "route_B_reproduces_reference": bool(b_all),
        "route_B2_reproduces_reference": bool(b2_all),
        "any_sparse_route_reproduces_reference": bool(a_all or b2_all),
        "factor_effectively_dense_route_A": [
            results[k]["route_A"][0].get("factor_is_effectively_dense")
            for k in ORDER],
        "exit_code": exit_code,
    }
    payload["verdict"] = verdict

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")

    print("\n" + "=" * 72)
    print("VERDICT")
    print("=" * 72)
    for key in ORDER:
        va = verdict["route_A"][key]
        print(f"  {key} route A : {va['status']:20s} "
              + (f"sigma={va['sigma']:.6g} beta_sq {va['beta_sq']:.6f} "
                 f"({va['digits_beta_sq']:.1f} digits), R {va['R']:.12f} "
                 f"({va['digits_R']:.1f} digits), "
                 f"rel_resid {va['rel_residual']:.2e}, "
                 f"factor {'DENSE' if va['factor_is_effectively_dense'] else 'sparse'}"
                 f" ({va['factor_nnz']} nnz)" if "beta_sq" in va
                 else va.get("why", "")))
        for tag in ("route_B", "route_B2"):
            vb = verdict[tag][key]
            print(f"  {key} {tag[-2:]:>3s}     : {vb['status']:20s} "
                  f"sigma={vb['sigma']} lam={vb['eigenvalue']} "
                  f"digits_beta_sq={vb['digits_beta_sq']} "
                  f"x2dev={vb['x2_matches_DcTx1_rel']}")
    print(f"  exit_code = {exit_code} (0 = a sparse route reproduces the "
          f"committed reference at both rungs)")
    print(f"wrote {OUT_JSON}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
