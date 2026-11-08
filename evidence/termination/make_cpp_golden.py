"""Freeze a tiny FIT stepping problem as a golden file for the C++ port.

``tests/test_cpp_parity.py`` reads ``tests/data/cpp_golden_step.npz`` (v1) and
``tests/data/cpp_golden_step_v2.npz`` (v2) and checks that the compiled kernel
reproduces these numbers.  Both files are *generated from the Python reference*
-- :func:`emfit.evolve.step_explicit`, which ``FITStepper.step`` calls -- so
there is exactly one source of truth and the golden data can never drift away
from the pure-Python scheme.

Two cases, on the same 4x3x2 grid, with the same fixed seed convention, at
``0.9 * cfl_dt``, three steps each:

* **v1** -- the lossless, source-free, non-PML, non-PEC step: one branch of
  several.  Written first and kept byte-for-byte: it is the independent witness
  the C++ port was validated against, so regenerating it to match the kernel
  would destroy the only thing it is good for.
* **v2** -- *every* branch of ``step_explicit`` active at once: a PML on one
  axis (its two damping factor vectors stored as plain arrays), a non-zero
  conductance distribution ``m_sigma`` on a subset of edges (so the lossy
  constants ``loss_num`` / ``loss_den`` are stored), a PEC mask (its int64
  ``pec_idx`` stored) and a non-zero current source ``j`` (stored).  The v2 file
  carries everything a caller needs to reproduce the run through the kernel with
  no access to ``emfit`` internals -- no ``pml`` object is stored, because the
  kernel consumes the two factor vectors, not the layer.

Everything here is small on purpose (4x3x2 cells, 3 steps): the point is an
exact, bytes-level comparison of the update, not a physics run.

Raw CSR pieces are stored rather than the sparse matrices themselves so that a
C++ kernel can be handed the arrays directly, with no scipy on the other side.

Run from the repository root::

    python3 evidence/termination/make_cpp_golden.py            # v1 only (default)
    python3 evidence/termination/make_cpp_golden.py --v2       # v2 only
    python3 evidence/termination/make_cpp_golden.py --v1 --v2  # both

The default is v1-only on purpose: ``--v2`` must not silently rewrite the file
that the existing parity tests treat as a frozen witness.
"""

from __future__ import annotations

import os
import sys

# Runnable as a plain script from anywhere: put the repository root on the path
# (pytest gets this for free from pyproject's pythonpath = ["."]).
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np
import scipy.sparse as sp

from emfit.evolve import FITStepper, cfl_dt, step_explicit
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.operators import CellComplex
from emfit.pml import PML

NX, NY, NZ = 4, 3, 2
H = 0.1
SEED = 20261109
N_STEPS = 3

OUT = os.path.join("tests", "data", "cpp_golden_step.npz")
OUT_V2 = os.path.join("tests", "data", "cpp_golden_step_v2.npz")

# v2 only: the branch ingredients.  Fixed here, recorded in the file.
SIGMA_VALUE = 1e-3          # conductance [S] on the selected edges
SIGMA_FRACTION = 0.2        # fraction of edges that carry it
SIGMA_SEED = 20261109       # which edges got it
SEED_J = 20261110           # the current source
PML_AXES = ("x",)           # one axis, as the dispatch asks
PML_THICKNESS = 1           # the grid is 4 cells wide; thickness 1 is all it has


def _grid():
    g = Grid.uniform(NX, NY, NZ, lx=NX * H, ly=NY * H, lz=NZ * H)
    cc = CellComplex(g)
    m_eps, m_mu = material_matrices(g, cc)
    return g, cc, m_eps, m_mu


def _print(name, a):
    if a.ndim == 0:
        print(f"  {name:22s} scalar {a.dtype} = {a.item()!r}")
    else:
        print(f"  {name:22s} {str(a.shape):12s} {a.dtype}")


def _write(out, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, **out)
    size = os.path.getsize(path)
    print(f"\nwrote {path}: {size} bytes ({size / 1024:.1f} KiB)")
    print(f"{len(out)} arrays:")
    for key in sorted(out):
        _print(key, out[key])


def main_v1() -> int:
    g, cc, m_eps, m_mu = _grid()

    C = cc.curl()             # (n_faces, n_edges)
    C_tilde = cc.curl_dual()  # (n_edges, n_faces), a CSC view of C.T
    print(f"C        : {type(C).__module__}.{type(C).__name__} "
          f"shape={C.shape} dtype={C.dtype} format={C.format}")
    print(f"C_tilde  : {type(C_tilde).__module__}.{type(C_tilde).__name__} "
          f"shape={C_tilde.shape} dtype={C_tilde.dtype} "
          f"format={C_tilde.format}")
    assert sp.issparse(C) and C.format == "csr", "C is expected to be CSR"
    assert C_tilde.format == "csc", (
        "C_tilde is a zero-copy .transpose(copy=False) view of the CSR C, so "
        f"it is CSC; got {C_tilde.format}.  The stored golden data and the "
        "C++ kernel assume that fact is known, not re-derived.")
    assert C.shape[0] == cc.n_faces and C.shape[1] == cc.n_edges
    assert C_tilde.shape == (cc.n_edges, cc.n_faces)

    dt = 0.9 * cfl_dt(g)
    inv_m_eps = 1.0 / np.asarray(m_eps, dtype=float).ravel()
    inv_m_mu = 1.0 / np.asarray(m_mu, dtype=float).ravel()

    rng = np.random.default_rng(SEED)
    e = rng.standard_normal(cc.n_edges)
    h = rng.standard_normal(cc.n_faces)

    out: dict[str, np.ndarray] = {
        "e0": e.copy(),
        "h0": h.copy(),
        # Faraday operator, exactly as Python holds it (CSR).
        "C_data": C.data.copy(),
        "C_indices": C.indices.astype(np.int64),
        "C_indptr": C.indptr.astype(np.int64),
        "C_shape": np.asarray(C.shape, dtype=np.int64),
        # Ampere operator, exactly as Python holds it (CSC view of C.T) ...
        "C_tilde_data": C_tilde.data.copy(),
        "C_tilde_indices": C_tilde.indices.astype(np.int64),
        "C_tilde_indptr": C_tilde.indptr.astype(np.int64),
        "C_tilde_shape": np.asarray(C_tilde.shape, dtype=np.int64),
        # ... and the same operator converted to CSR, which is the layout the
        # C++ row loop consumes.  Both are stored so a parity failure can be
        # attributed to summation order instead of being blamed on a typo.
        "C_tilde_csr_data": C_tilde.tocsr().data.copy(),
        "C_tilde_csr_indices": C_tilde.tocsr().indices.astype(np.int64),
        "C_tilde_csr_indptr": C_tilde.tocsr().indptr.astype(np.int64),
        "inv_m_mu": inv_m_mu,
        "inv_m_eps": inv_m_eps,
        "dt": np.asarray(dt, dtype=float),
        # Problem extent / bookkeeping.
        "n_edges": np.asarray(cc.n_edges, dtype=np.int64),
        "n_faces": np.asarray(cc.n_faces, dtype=np.int64),
        "nx": np.asarray(NX, dtype=np.int64),
        "ny": np.asarray(NY, dtype=np.int64),
        "nz": np.asarray(NZ, dtype=np.int64),
        "lx": np.asarray(NX * H, dtype=float),
        "ly": np.asarray(NY * H, dtype=float),
        "lz": np.asarray(NZ * H, dtype=float),
        "seed": np.asarray(SEED, dtype=np.int64),
        "n_steps": np.asarray(N_STEPS, dtype=np.int64),
    }

    for step_no in range(1, N_STEPS + 1):
        step_explicit(e, h, C, C_tilde, inv_m_mu, inv_m_eps, dt)
        out[f"e{step_no}"] = e.copy()
        out[f"h{step_no}"] = h.copy()

    _write(out, OUT)
    return 0


def main_v2() -> int:
    """Every branch of ``step_explicit`` at once, on the same 4x3x2 grid."""
    g, cc, m_eps, m_mu = _grid()

    C = cc.curl()
    C_tilde = cc.curl_dual()
    assert sp.issparse(C) and C.format == "csr"
    assert C_tilde.format == "csc"
    assert C.shape == (cc.n_faces, cc.n_edges)
    assert C_tilde.shape == (cc.n_edges, cc.n_faces)

    dt = 0.9 * cfl_dt(g)

    # (a) one axis of PML.  Only the two multiplier vectors enter the kernel, so
    # only those are stored -- the layer object itself stays here.
    pml = PML(g, thickness_cells=PML_THICKNESS, axes=PML_AXES, cc=cc)
    damp_e, damp_h = pml.multipliers(dt)

    # (b) conductance on a subset of edges, then the lossy constants the stepper
    # derives from it.  Read off FITStepper rather than re-derived here: the
    # point of the golden is to freeze the production path, not a copy of it.
    pec_mask = cc.pec_edge_mask(("xmin", "xmax"))
    rng_sigma = np.random.default_rng(SIGMA_SEED)
    m_sigma = np.zeros(cc.n_edges, dtype=float)
    hot = rng_sigma.random(cc.n_edges) < SIGMA_FRACTION
    m_sigma[hot] = SIGMA_VALUE
    m_sigma[pec_mask] = 0.0          # no conductance across a PEC edge

    st = FITStepper(cc, m_eps, m_mu, dt=dt, pec=pec_mask, pml=pml,
                    m_sigma=m_sigma)
    assert st.loss_den is not None, "v2 must exercise the lossy branch"
    assert st.pec_idx is not None and st.pec_idx.size > 0, "v2 must pin edges"
    assert np.any(damp_e < 1.0) and np.any(damp_h < 1.0), "v2 must damp"
    assert st.pec_idx.dtype == np.intp, f"pec_idx is {st.pec_idx.dtype}"

    loss_num = np.asarray(st.loss_num, dtype=float)
    loss_den = np.asarray(st.loss_den, dtype=float)
    inv_m_mu = np.asarray(st.inv_m_mu, dtype=float)
    inv_m_eps = np.asarray(st.inv_m_eps, dtype=float)
    pec_idx = st.pec_idx.astype(np.int64)

    # (d) a current source that is actually non-zero.
    rng_j = np.random.default_rng(SEED_J)
    j = rng_j.standard_normal(cc.n_edges)
    assert np.all(np.isfinite(j)) and np.any(j != 0.0)

    # The initial state, same convention and seed as v1.
    rng = np.random.default_rng(SEED)
    e = rng.standard_normal(cc.n_edges)
    h = rng.standard_normal(cc.n_faces)

    print(f"grid {NX}x{NY}x{NZ}, n_edges={cc.n_edges}, n_faces={cc.n_faces}")
    print(f"dt = 0.9*cfl_dt = {dt!r}")
    print(f"pml: axes={pml.walls_for('x') or PML_AXES} thickness_cells="
          f"{PML_THICKNESS}; damp_e in [{damp_e.min()!r}, {damp_e.max()!r}] "
          f"({int(np.count_nonzero(damp_e < 1.0))} of {damp_e.size} < 1), "
          f"damp_h in [{damp_h.min()!r}, {damp_h.max()!r}] "
          f"({int(np.count_nonzero(damp_h < 1.0))} of {damp_h.size} < 1)")
    print(f"m_sigma = {SIGMA_VALUE} on {int(np.count_nonzero(m_sigma))} edges; "
          f"loss_num in [{loss_num.min()!r}, {loss_num.max()!r}], "
          f"loss_den in [{loss_den.min()!r}, {loss_den.max()!r}]")
    print(f"pec_idx: {pec_idx.size} edges, dtype {pec_idx.dtype}")
    print(f"j: max|j| = {np.abs(j).max()!r}, "
          f"{int(np.count_nonzero(j))} non-zero")

    out: dict[str, np.ndarray] = {
        "case": np.asarray("v2-full-physics"),
        "e0": e.copy(),
        "h0": h.copy(),
        # Faraday operator (CSR), as Python holds it.
        "C_data": C.data.copy(),
        "C_indices": C.indices.astype(np.int64),
        "C_indptr": C.indptr.astype(np.int64),
        "C_shape": np.asarray(C.shape, dtype=np.int64),
        # Ampere operator: the CSC view Python holds, plus the CSR copy the
        # kernel's row loop consumes.  Same rationale as v1.
        "C_tilde_data": C_tilde.data.copy(),
        "C_tilde_indices": C_tilde.indices.astype(np.int64),
        "C_tilde_indptr": C_tilde.indptr.astype(np.int64),
        "C_tilde_shape": np.asarray(C_tilde.shape, dtype=np.int64),
        "C_tilde_csr_data": C_tilde.tocsr().data.copy(),
        "C_tilde_csr_indices": C_tilde.tocsr().indices.astype(np.int64),
        "C_tilde_csr_indptr": C_tilde.tocsr().indptr.astype(np.int64),
        "inv_m_mu": inv_m_mu,
        "inv_m_eps": inv_m_eps,
        "dt": np.asarray(dt, dtype=float),
        # (a) PML as the kernel takes it: two factor vectors, not an object.
        "damp_e": np.ascontiguousarray(damp_e, dtype=np.float64),
        "damp_h": np.ascontiguousarray(damp_h, dtype=np.float64),
        # (b) the lossy constants, as the stepper computed them.
        "loss_num": np.ascontiguousarray(loss_num, dtype=np.float64),
        "loss_den": np.ascontiguousarray(loss_den, dtype=np.float64),
        # (c) the PEC indices, int64 exactly as the binding declares them.
        "pec_idx": np.ascontiguousarray(pec_idx, dtype=np.int64),
        # (d) the current source.
        "j": np.ascontiguousarray(j, dtype=np.float64),
        # Problem extent / bookkeeping.
        "n_edges": np.asarray(cc.n_edges, dtype=np.int64),
        "n_faces": np.asarray(cc.n_faces, dtype=np.int64),
        "nx": np.asarray(NX, dtype=np.int64),
        "ny": np.asarray(NY, dtype=np.int64),
        "nz": np.asarray(NZ, dtype=np.int64),
        "lx": np.asarray(NX * H, dtype=float),
        "ly": np.asarray(NY * H, dtype=float),
        "lz": np.asarray(NZ * H, dtype=float),
        "seed": np.asarray(SEED, dtype=np.int64),
        "seed_j": np.asarray(SEED_J, dtype=np.int64),
        "seed_sigma": np.asarray(SIGMA_SEED, dtype=np.int64),
        "sigma_value": np.asarray(SIGMA_VALUE, dtype=float),
        "n_sigma": np.asarray(int(np.count_nonzero(m_sigma)), dtype=np.int64),
        "pml_axes": np.asarray(",".join(PML_AXES)),
        "pml_thickness_cells": np.asarray(PML_THICKNESS, dtype=np.int64),
        "n_steps": np.asarray(N_STEPS, dtype=np.int64),
    }

    # The reference run: the full argument list, every branch live.
    for step_no in range(1, N_STEPS + 1):
        step_explicit(e, h, C, C_tilde, inv_m_mu, inv_m_eps, dt,
                      loss_num, loss_den, pml, pec_idx, j)
        out[f"e{step_no}"] = e.copy()
        out[f"h{step_no}"] = h.copy()

    _write(out, OUT_V2)
    return 0


def main(argv) -> int:
    want_v1 = "--v1" in argv
    want_v2 = "--v2" in argv
    if not want_v1 and not want_v2:
        want_v1 = True          # unchanged default: v1 only, exactly as before
    unknown = [a for a in argv if a not in ("--v1", "--v2")]
    if unknown:
        print(f"unknown argument(s): {unknown}", file=sys.stderr)
        return 2
    rc = 0
    if want_v1:
        rc |= main_v1()
    if want_v2:
        rc |= main_v2()
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
