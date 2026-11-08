"""Freeze a tiny FIT stepping problem as a golden file for the C++ port.

``tests/test_cpp_parity.py`` reads ``tests/data/cpp_golden_step.npz`` and checks
that the compiled kernel reproduces these numbers.  The file is *generated from
the Python reference* -- :func:`emfit.evolve.step_explicit`, which
``FITStepper.step`` calls -- so there is exactly one source of truth and the
golden data can never drift away from the pure-Python scheme.

Everything here is small on purpose (4x3x2 cells, 3 steps): the point is an
exact, bytes-level comparison of the update, not a physics run.

Raw CSR pieces are stored rather than the sparse matrices themselves so that a
C++ kernel can be handed the arrays directly, with no scipy on the other side.

Run from the repository root::

    python3 evidence/termination/make_cpp_golden.py
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

from emfit.evolve import cfl_dt, step_explicit
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.operators import CellComplex

NX, NY, NZ = 4, 3, 2
H = 0.1
SEED = 20261109
N_STEPS = 3

OUT = os.path.join("tests", "data", "cpp_golden_step.npz")


def main() -> int:
    g = Grid.uniform(NX, NY, NZ, lx=NX * H, ly=NY * H, lz=NZ * H)
    cc = CellComplex(g)
    m_eps, m_mu = material_matrices(g, cc)

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

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    np.savez_compressed(OUT, **out)

    size = os.path.getsize(OUT)
    print(f"\nwrote {OUT}: {size} bytes ({size / 1024:.1f} KiB)")
    print(f"{len(out)} arrays:")
    for key in sorted(out):
        a = out[key]
        if a.ndim == 0:
            print(f"  {key:22s} scalar {a.dtype} = {a.item()!r}")
        else:
            print(f"  {key:22s} {str(a.shape):12s} {a.dtype}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
