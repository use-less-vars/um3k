#!/usr/bin/env python3
"""Probe the FULL 2x2 block pencil of the 2-D modal problem.

Task C of the audit follow-up asks three questions about the pencil that
``tools/host_ladder.route_c`` forms (``tools/host_ladder.py:556-558``)::

    K = block_diag([A, 0])                     (n_e + n_n square, n_n rows zero)
    M = [[m1_ff, -c_f], [-c_f^T, h]]           h = k_zz - k0^2 m_zz

1. does ``ker(K)`` carry ZERO or INFINITE eigenvalues, and with what
   multiplicity;
2. is ``ker(M)`` trivial;
3. is the pencil regular.

The blocks are the ones ``build_modal`` assembles, so nothing is re-derived:
``A = 0.5*(a + a^T)`` with ``a = k0^2 m_eps - k_q``, ``m1_ff``/``m_eps_ff``/
``k_q_ff`` the free-edge blocks, ``c_f`` the edge/node coupling and ``h`` the
``k_zz - k0^2 m_zz`` longitudinal block (``tools/host_ladder.py:519-566``).

Stages
------
``--stage struct``  assemble, measure the structural facts (rank/sigma of A
                    and h by SVD; rank and nonsingularity of M by LU, because
                    a 1691^2 SVD costs ~100 s in this container; the exact
                    zero block of K), cache the dense pencils.
``--stage qz``      load the cache, run the dense QZ (``dggev``, real
                    nonsymmetric) on the full 1691 (or 429) square pencil,
                    classify every eigenpair, compare the finite spectrum with
                    the condensed pencil mode2d's dense path solves, locate the
                    quasi-TEM mode and measure kernel-vs-mode separation.
``--stage all``     both, one process.

The cache lives under ``--cache`` (default ``.scratch/kerpencil``) INSIDE the
tree: nothing is written to ``/tmp``, which does not persist between container
calls.

Run from the repository root::

    python3 evidence/matrix_audit/ker_pencil_harness.py --h 0.4 --stage struct
    python3 evidence/matrix_audit/ker_pencil_harness.py --h 0.4 --stage qz

Every number printed is written to ``--out`` as JSON as well.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import host_ladder as hl  # noqa: E402

#: the k0 sec. 158.5 used for h040/h080 (evidence/matrix_audit/h040.json)
K0 = 209.78570331727553
CLEARANCE = 3.0
W_M = 0.8e-3
#: sec. 158.5's quasi-TEM eigenvalue at h = 0.4 mm (beta = 385.02147433414683)
LAM_TEM_H040 = 148241.5356984401


def fingerprint(mesh) -> str:
    """sha1 over nodes|edges|tris, shapes included -- the B3 fingerprint."""
    h = hashlib.sha1()
    for arr in (mesh.nodes, mesh.edges, mesh.tris):
        a = np.ascontiguousarray(arr)
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()[:16]


def rank_sigma(a: np.ndarray) -> dict:
    """rank and extreme singular values, numpy's own default tolerance."""
    t0 = time.perf_counter()
    s = sla.svdvals(a)
    tol = float(s[0]) * max(a.shape) * float(np.finfo(float).eps)
    return {
        "shape": list(a.shape),
        "rank": int((s > tol).sum()),
        "sigma_max": float(s[0]),
        "sigma_min": float(s[-1]),
        "tol": tol,
        "cond": float(s[0] / s[-1]) if s[-1] > 0 else float("inf"),
        "t_s": time.perf_counter() - t0,
    }


def lu_facts(a: np.ndarray) -> dict:
    """Nonsingularity evidence without an SVD (a 1691^2 SVD is ~100 s here).

    ``dgetrf`` gives the pivots; a matrix is nonsingular iff no pivot is zero
    up to rounding, so ``rank_lu`` and the pivot ratio are a conservative
    statement, and ``slogdet`` gives the determinant's sign and magnitude.
    """
    n = a.shape[0]
    t0 = time.perf_counter()
    lu, piv = sla.lu_factor(a)
    d = np.abs(np.diag(lu))
    tol = float(d.max()) * n * float(np.finfo(float).eps)
    sign, logdet = np.linalg.slogdet(a)
    return {
        "shape": list(a.shape),
        "rank_lu": int((d > tol).sum()),
        "n_zero_pivots": int((d <= tol).sum()),
        "min_abs_pivot": float(d.min()),
        "max_abs_pivot": float(d.max()),
        "pivot_ratio": float(d.min() / d.max()) if d.max() > 0 else 0.0,
        "tol": tol,
        "det_sign": float(sign),
        "log_abs_det": float(logdet),
        "t_s": time.perf_counter() - t0,
    }


def build(h_mm: float) -> dict:
    """Assemble the blocks exactly as build_modal does, then densify K and M."""
    h_m = h_mm * 1e-3
    nz_sub = int(round(hl.H_SUB / h_m))
    cell = hl.H_SUB / nz_sub
    n_strip = max(int(round(W_M / cell)), 1)
    t0 = time.perf_counter()
    pb = hl.build_modal(h_m, clearance=CLEARANCE, n_strip=n_strip, w_m=W_M, k0=K0)
    t_build = time.perf_counter() - t0

    n_e, n_n = int(pb["n_e"]), int(pb["n_n"])
    big = n_e + n_n

    # the sparse pencil route_c forms, verbatim (tools/host_ladder.py:556-558)
    KC = sp.block_diag([pb["A"], sp.csc_matrix((n_n, n_n))], format="csc")
    MC = sp.bmat([[pb["m1_f"], (-pb["c_f"]).tocsc()],
                  [(-pb["c_f"].T).tocsc(), pb["h"]]], format="csc")

    K = KC.toarray()
    M = MC.toarray()
    # the dense pencil must be the sparse one: same stored entries, and the
    # same row/column sums up to summation order (BLAS order differs from
    # scipy's per-column accumulation, so equality is to round-off only)
    # (sparse nnz counts stored explicit zeros too, so compare the VALUES, not
    # the storage; nnz_of_K/M are recorded for the record)
    nnz_K, nnz_M = int(KC.nnz), int(MC.nnz)
    nz_K, nz_M = int(np.count_nonzero(K)), int(np.count_nonzero(M))
    dK = float(np.max(np.abs(np.asarray(KC.sum(axis=0)).ravel() - K.sum(axis=0))))
    dM = float(np.max(np.abs(np.asarray(MC.sum(axis=1)).ravel() - M.sum(axis=1))))
    scale = max(float(np.abs(K).max()), float(np.abs(M).max()), 1.0)
    assert dK <= 1e-12 * scale * K.shape[0], dK
    assert dM <= 1e-12 * scale * M.shape[0], dM

    return {
        "pb": pb, "K": K, "M": M, "n_e": n_e, "n_n": n_n, "big": big,
        "KC": KC, "MC": MC, "h_m": h_m, "nz_sub": nz_sub, "cell": cell,
        "dK": dK, "dM": dM, "nnz_K": nnz_K, "nnz_M": nnz_M,
        "nonzero_K": nz_K, "nonzero_M": nz_M,
        "n_strip": n_strip, "t_build": t_build,
        "A": pb["A"].toarray(),
        "m1": pb["m1_f"].toarray(),
        "c": pb["c_f"].toarray(),
        "h": pb["h"].toarray(),
        "mesh": pb["mesh"], "geo": pb["geo"],
    }


def _sparse_svds(mat, which: str = "SM", k: int = 1) -> dict:
    """Smallest (or largest) singular value of a SPARSE block, via ARPACK.

    Deliberately NOT a dense SVD of the pencil: a 1691^2 ``svdvals`` costs
    ~90 s in this container, and on ``K`` it is worse than useless because
    ``K`` is singular by construction (the bottom ``n_n`` rows are exactly
    zero) -- ``svds`` is the honest tool for the question "how far from
    singular is this block".
    """
    from scipy.sparse.linalg import svds as _svds
    t0 = time.perf_counter()
    n = min(mat.shape)
    try:
        v0 = np.ones(n)
        _, s, _ = _svds(mat, k=k, which=which, tol=1e-12, maxiter=20000, v0=v0)
        return {"which": which, "sigma": float(np.min(s) if which == "SM" else np.max(s)),
                "t_s": time.perf_counter() - t0}
    except Exception as exc:                                  # noqa: BLE001
        return {"which": which, "error": f"{type(exc).__name__}: {exc}",
                "t_s": time.perf_counter() - t0}


def stage_probe(h_mm: float) -> dict:
    """Step 1: the block-level structural facts, from the SPARSE blocks.

    Cheap by construction (``build_modal`` is ~6 ms; only ``svds`` costs), so
    it runs at the big mesh too -- ``dim ker K`` and ``sigma_min(M)`` do not
    need the 1691^2 QZ to be affordable.
    """
    h_m = h_mm * 1e-3
    nz_sub = int(round(hl.H_SUB / h_m))
    cell = hl.H_SUB / nz_sub
    n_strip = max(int(round(W_M / cell)), 1)
    pb = hl.build_modal(h_m, clearance=CLEARANCE, n_strip=n_strip, w_m=W_M, k0=K0)
    n_e, n_n = int(pb["n_e"]), int(pb["n_n"])
    big = n_e + n_n
    KC = sp.block_diag([pb["A"], sp.csc_matrix((n_n, n_n))], format="csc")
    MC = sp.bmat([[pb["m1_f"], (-pb["c_f"]).tocsc()],
                  [(-pb["c_f"].T).tocsc(), pb["h"]]], format="csc")
    out: dict = {
        "h_mm": h_mm, "n_e": n_e, "n_n": n_n, "n_dof": big,
        "nz_sub": nz_sub, "cell_m": cell, "n_strip": n_strip, "k0": K0,
        "mesh_fingerprint": fingerprint(pb["mesh"]),
        "mesh": {"ny": int(pb["geo"]["ny"]), "nz": int(pb["geo"]["nz"]),
                 "cell": float(pb["geo"]["cell"])},
        "build_call": ("hl.build_modal(h_m=%r, clearance=3.0, n_strip=%d, "
                       "w_m=0.0008, k0=%r)" % (h_m, n_strip, K0)),
        "nnz": {"K": int(KC.nnz), "M": int(MC.nnz)},
        "K_bottom_rows_exactly_zero": bool(not KC[n_e:, :].nnz),
    }
    for name, mat in (("h", pb["h"]), ("A", pb["A"]), ("m1_f", pb["m1_f"]),
                      ("M_full", MC), ("K_full", KC)):
        rec = _sparse_svds(mat)
        if min(mat.shape) <= 500:      # cheap dense cross-check where affordable
            t0 = time.perf_counter()
            s = sla.svdvals(mat.toarray() if sp.issparse(mat) else mat)
            rec["sigma_min_dense"] = float(s[-1])
            rec["t_dense_s"] = time.perf_counter() - t0
        out[name] = rec
    return out


def stage_struct(h_mm: float, cache: Path) -> dict:
    b = build(h_mm)
    K, M, A, hb = b["K"], b["M"], b["A"], b["h"]
    n_e, n_n, big = b["n_e"], b["n_n"], b["big"]

    rec: dict = {
        "h_mm": h_mm,
        "n_e": n_e, "n_n": n_n, "n_dof": big,
        "nz_sub": b["nz_sub"], "cell_m": b["cell"], "n_strip": b["n_strip"],
        "k0": K0, "clearance": CLEARANCE, "w_m": W_M,
        "mesh_fingerprint": fingerprint(b["mesh"]),
        "mesh": {"ny": int(b["geo"]["ny"]), "nz": int(b["geo"]["nz"]),
                 "cell": float(b["geo"]["cell"])},
        "build_call": (
            "hl.build_modal(h_m=%r, clearance=3.0, n_strip=%d, w_m=0.0008, "
            "k0=%r)" % (h_mm * 1e-3, b["n_strip"], K0)
        ),
        "t_build_s": b["t_build"],
        "k_row_norm_f": float(sla.norm(K)),
        "m_row_norm_f": float(sla.norm(M)),
        "k_zero_block": {
            "bottom_rows_nnz": int(np.count_nonzero(K[n_e:, :])),
            "right_cols_nnz": int(np.count_nonzero(K[:, n_e:])),
        },
        "A": rank_sigma(A),
        "h_block": rank_sigma(hb),
        "M_LU": lu_facts(M),
    }
    # rank(K): the bottom n_n rows of K are EXACTLY zero (K = block_diag([A,0])),
    # so rank(K) = rank(A) and ker K has dimension exactly n_n -- no SVD of the
    # 1691^2 pencil is needed for this, and none is run (it costs ~100 s).
    zero_rows = bool(not K[n_e:, :].any())
    assert zero_rows
    rec["K_zero_block_verified_exact"] = zero_rows
    rec["rank_K"] = int(rec["A"]["rank"])
    rec["dim_ker_K"] = int(big - rec["A"]["rank"])
    assert rec["dim_ker_K"] == n_n
    # the (2,2) block of M restricted to the ker K coordinate block IS h
    assert np.array_equal(M[n_e:, n_e:], hb)
    rec["ker_K_block_is_h"] = True
    # ker K, written out: [0; y] for every y
    rec["ker_K_basis_description"] = "[0; y] with y in R^n_n (the only zero rows of K)"
    rec["algebra_prediction"] = {
        "zero_eigenvalues": n_n,
        "infinite_eigenvalues": 0,
        "why": ("K[0;y]=0 and M[0;y]=[-c_f y; h y]; h nonsingular => hy!=0 for "
                "y!=0 => M[0;y]!=0 => lambda=0 with multiplicity n_n, not 0/0"),
    }

    cache.mkdir(parents=True, exist_ok=True)
    np.save(cache / f"K_{h_mm:.2f}.npy", K)
    np.save(cache / f"M_{h_mm:.2f}.npy", M)
    np.save(cache / f"A_{h_mm:.2f}.npy", A)
    np.save(cache / f"c_{h_mm:.2f}.npy", b["c"])
    np.save(cache / f"m1_{h_mm:.2f}.npy", b["m1"])
    np.save(cache / f"h_{h_mm:.2f}.npy", hb)
    rec["cache"] = str(cache)
    return rec


def stage_qz(h_mm: float, cache: Path, rec_struct: dict | None) -> dict:
    K = np.load(cache / f"K_{h_mm:.2f}.npy")
    M = np.load(cache / f"M_{h_mm:.2f}.npy")
    A = np.load(cache / f"A_{h_mm:.2f}.npy")
    c = np.load(cache / f"c_{h_mm:.2f}.npy")
    m1 = np.load(cache / f"m1_{h_mm:.2f}.npy")
    hb = np.load(cache / f"h_{h_mm:.2f}.npy")
    big = K.shape[0]
    n_e = A.shape[0]
    n_n = big - n_e

    rec: dict = {"h_mm": h_mm, "n_dof": big, "n_e": n_e, "n_n": n_n,
                 "k_fro": float(sla.norm(K)), "m_fro": float(sla.norm(M))}

    # ---- dense QZ, real nonsymmetric -> dggev, homogeneous (alpha, beta) ----
    t0 = time.perf_counter()
    w, vr = sla.eig(K, M, right=True, left=False, homogeneous_eigvals=True)
    rec["t_dggev_s"] = time.perf_counter() - t0
    alpha, beta = np.asarray(w[0]), np.asarray(w[1])

    lam = np.full(big, np.nan)
    fin = beta != 0
    lam[fin] = np.real(alpha[fin] / beta[fin])
    im_rel = np.zeros(big)
    im_rel[fin] = np.abs(np.imag(alpha[fin] / beta[fin])) / np.maximum(
        1.0, np.abs(alpha[fin] / beta[fin]))

    inf_mask = (beta == 0) & (alpha != 0)
    nul_mask = (beta == 0) & (alpha == 0)
    scale = float(np.max(np.abs(lam[fin]))) if fin.any() else 1.0
    rec["scale"] = scale
    rec["tol_sweep"] = {}
    for ex in (8, 10, 12):
        tol = scale * 10.0 ** (-ex)
        n_zero = int(np.sum(fin & (np.abs(np.nan_to_num(lam)) <= tol)))
        rec["tol_sweep"][f"1e-{ex}"] = {"tol_abs": tol, "n_zero": n_zero}

    tol = scale * 1e-10
    zero_mask = fin & (np.abs(np.nan_to_num(lam)) <= tol)
    rec["tol_used"] = {"rule": "ZERO if |lambda| <= 1e-10 * max|lambda_finite|",
                       "tol_abs": tol, "scale": scale}
    rec["counts"] = {
        "n": big,
        "zero": int(zero_mask.sum()),
        "finite_nonzero": int((fin & ~zero_mask).sum()),
        "infinite": int(inf_mask.sum()),
        "zero_over_zero_singular": int(nul_mask.sum()),
        "nonfinite": int(np.sum(~fin) - inf_mask.sum() - nul_mask.sum()),
        "max_rel_imag_of_finite": float(np.max(im_rel[fin])) if fin.any() else 0.0,
    }
    rec["zero_magnitudes"] = {
        "abs_max": float(np.max(np.abs(lam[zero_mask]))) if zero_mask.any() else 0.0,
        "abs_median": float(np.median(np.abs(lam[zero_mask]))) if zero_mask.any() else 0.0,
    }
    rec["finite_magnitudes"] = {
        "abs_min": float(np.min(np.abs(lam[fin & ~zero_mask]))) if (fin & ~zero_mask).any() else 0.0,
        "abs_median": float(np.median(np.abs(lam[fin & ~zero_mask]))),
        "abs_max": float(np.max(np.abs(lam[fin & ~zero_mask]))),
        "re_median": float(np.median(lam[fin & ~zero_mask])),
    }

    # ---- per-eigenpair residuals, normalised by ||K||_F and ||M||_F -------
    t0 = time.perf_counter()
    KV = K @ vr
    MV = M @ vr
    vn = np.linalg.norm(vr, axis=0)
    vn[vn == 0] = 1.0
    rK = np.linalg.norm(KV, axis=0) / (rec["k_fro"] * vn)
    rM = np.linalg.norm(MV, axis=0) / (rec["m_fro"] * vn)
    rec["t_residuals_s"] = time.perf_counter() - t0
    rec["residuals"] = {
        "rule": ("per-column: |K v|/(|K|_F |v|) and |M v|/(|M|_F |v|); "
                 "class if the residual is <= 1e-10"),
        "t": 1e-10,
    }
    t = 1e-10
    cls_both = (rK <= t) & (rM <= t)
    cls_konly = (rK <= t) & (rM > t)
    cls_monly = (rK > t) & (rM <= t)
    cls_reg = (rK > t) & (rM > t)
    # finiteness of the *pair* (alpha, beta), for cross-tabbing the two rules
    rec["residual_classes"] = {
        "both_tiny_0_0": int(cls_both.sum()),
        "k_only_zero_eigenvalue": int(cls_konly.sum()),
        "m_only_infinite_eigenvalue": int(cls_monly.sum()),
        "neither_finite_regular": int(cls_reg.sum()),
        "max_rK_among_k_only": float(rK[cls_konly].max()) if cls_konly.any() else 0.0,
        "min_rM_among_k_only": float(rM[cls_konly].min()) if cls_konly.any() else 0.0,
        "min_max_r_among_regular": (float(np.min(np.maximum(rK[cls_reg], rM[cls_reg])))
                                    if cls_reg.any() else 0.0),
        "max_rK_among_regular": float(rK[cls_reg].max()) if cls_reg.any() else 0.0,
        "rK_quantiles": [float(q) for q in np.quantile(rK, [0, 0.25, 0.5, 0.75, 1.0])],
        "rM_quantiles": [float(q) for q in np.quantile(rM, [0, 0.25, 0.5, 0.75, 1.0])],
    }
    idx_konly = np.flatnonzero(cls_konly)
    rec["residual_classes"]["k_only_lambda_abs_max"] = (
        float(np.max(np.abs(lam[idx_konly]))) if idx_konly.size else 0.0)
    rec["residual_classes"]["k_only_lambda_abs_median"] = (
        float(np.median(np.abs(lam[idx_konly]))) if idx_konly.size else 0.0)
    rec["residual_class_vs_pencil_rule"] = {
        "k_only_that_are_finite_nonzero": int(np.sum(cls_konly & fin & ~zero_mask)),
        "zero_rule_that_are_k_only": int(np.sum(zero_mask & cls_konly)),
        "k_only_that_are_inf": int(np.sum(cls_konly & inf_mask)),
    }

    # ---- the finite spectrum must be the condensed pencil mode2d solves ----
    t0 = time.perf_counter()
    D = np.linalg.solve(hb, np.eye(n_n))          # h^{-1}, as lu_h.solve(I) does
    b_cond = m1 - (c @ D) @ c.T
    b_cond = 0.5 * (b_cond + b_cond.T)
    a_cond = 0.5 * (A + A.T)
    lam_cond = sla.eigvals(a_cond, b_cond)
    rec["t_condensed_s"] = time.perf_counter() - t0
    lam_cond_re = np.real(lam_cond)
    lam_full_re = np.sort(lam[fin & ~zero_mask])
    lam_cond_sorted = np.sort(lam_cond_re)
    if lam_full_re.size == lam_cond_sorted.size:
        rel = np.abs(lam_full_re - lam_cond_sorted) / np.maximum(
            1.0, np.abs(lam_cond_sorted))
        rec["condensed_match"] = {
            "n_full_finite": int(lam_full_re.size),
            "n_condensed": int(lam_cond_sorted.size),
            "max_abs_rel_diff": float(rel.max()),
            "median_abs_rel_diff": float(np.median(rel)),
            "n_over_1e-8": int((rel > 1e-8).sum()),
            "condensed_max_rel_imag": float(
                np.max(np.abs(np.imag(lam_cond)) / np.maximum(1.0, np.abs(lam_cond)))),
        }
    else:
        rec["condensed_match"] = {"n_full_finite": int(lam_full_re.size),
                                  "n_condensed": int(lam_cond_sorted.size),
                                  "mismatch": True}

    # ---- where does the quasi-TEM mode sit, and is ker K separable? --------
    fin_idx = np.flatnonzero(fin & ~zero_mask)
    target = LAM_TEM_H040
    j = fin_idx[int(np.argmin(np.abs(lam[fin_idx] - target)))]
    lam_j = float(lam[j])
    rec["tem"] = {
        "target_lambda": target,
        "target_beta": float(np.sqrt(target)),
        "index": int(j),
        "lambda": lam_j,
        "beta": float(np.sqrt(lam_j)) if lam_j > 0 else float("nan"),
        "rel_err_vs_158_5": float(abs(lam_j - target) / target),
        "residual_K": float(rK[j]),
        "residual_M": float(rM[j]),
        "class_residual": ("both_tiny" if (rK[j] <= t and rM[j] <= t) else
                           "k_only" if rK[j] <= t else
                           "m_only" if rM[j] <= t else "regular"),
        "class_pencil": "finite_nonzero" if np.abs(lam_j) > tol else "zero",
    }
    other = np.delete(lam[fin_idx], np.searchsorted(fin_idx, j))
    rec["tem"]["nearest_other_finite_gap"] = (
        float(np.min(np.abs(other - lam_j))) if other.size else float("nan"))
    rec["tem"]["zeros_gap"] = float(abs(lam_j - 0.0))
    # contamination of a shift-invert 'LM' search at sigma = m * lambda_TEM
    rec["separation"] = {}
    for m in (0.30, 0.70, 0.76, 0.90):
        sigma = m * target
        allv = np.where(fin, lam, np.inf)
        # shift-invert picks the largest |1/(lambda - sigma)|; ker K sits at 0
        mag = np.abs(1.0 / (allv - sigma))
        order = np.argsort(-mag)
        top = order[:16]
        rec["separation"][f"sigma_{m:.2f}"] = {
            "sigma": sigma,
            "kernel_magnitude": float(1.0 / abs(0.0 - sigma)),
            "tem_magnitude": float(1.0 / abs(target - sigma)),
            "ratio_kernel_over_tem": float((1.0 / abs(sigma)) / abs(1.0 / (target - sigma))),
            "n_kernel_in_top16": int(np.sum(np.abs(lam[top]) <= tol)),
            "n_top16": int(top.size),
            "rank_of_tem": int(np.flatnonzero(order == j)[0]) if j in order else -1,
        }
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--h", type=float, default=0.4, help="cell size in mm")
    ap.add_argument("--stage", choices=("probe", "struct", "qz", "all"),
                    default="all")
    ap.add_argument("--cache", default=".scratch/kerpencil")
    ap.add_argument("--out", default=None, help="JSON output path")
    a = ap.parse_args()
    cache = (ROOT / a.cache) if not Path(a.cache).is_absolute() else Path(a.cache)

    out: dict = {"environment": {"numpy": np.__version__,
                                 "scipy": __import__("scipy").__version__}}
    if a.stage in ("probe", "all"):
        out["probe"] = stage_probe(a.h)
    if a.stage in ("struct", "all"):
        out["struct"] = stage_struct(a.h, cache)
    if a.stage in ("qz", "all"):
        s = out.get("struct") if a.stage == "all" else None
        out["qz"] = stage_qz(a.h, cache, s)
    out["h_mm"] = a.h
    txt = json.dumps(out, indent=2, default=float)
    if a.out:
        Path(a.out).write_text(txt)
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
