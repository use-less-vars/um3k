"""mc_inertia_check.py -- one-off rung0 inertia check of h, m1_f and M_C.

Read-only: writes nothing, prints to stdout.  Rung0 only (1444 free edges).

Read-only fact-finding.  Rebuilds ONLY the blocks (no eigenproblem is solved
except the single permitted dense eigh on the 1927x1927 rung0 M_C).
Assembly path is copied verbatim from sparse_solver_test.run_rung (lines
338-380); helpers/constants are imported from that module (import is safe:
its main() is guarded by __main__).
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"

import sys
import pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp

import sparse_solver_test as sst
import emfit.mode2d as m2

np.set_printoptions(threshold=20)


def r(x):
    return repr(float(x))


cfg = sst.RUNGS["rung0"]
ctx = sst.load_context()
k0 = ctx["k0"]
print("cfg name          :", cfg["name"])
print("k0                :", r(k0))
print("FREQ              :", r(ctx["FREQ"]))
print("HSUB, ZZ1, H      :", r(ctx["HSUB"]), r(ctx["ZZ1"]), r(ctx["H"]))

# ---------------- assembly (verbatim from run_rung) ----------------
xs = sst.axis([(0.0, ctx["Y0"]), (ctx["Y0"], ctx["Y1"]), (ctx["Y1"], ctx["W"])],
              [cfg["y_air"], cfg["strip"], cfg["y_air"]])
zs = sst.axis([(0.0, ctx["HSUB"]), (ctx["HSUB"], ctx["ZZ1"]), (ctx["ZZ1"], ctx["H"])],
              list(cfg["z"]))
mesh = m2.structured_mesh(xs, zs)


def eps_of(p):
    return np.where(p[:, 1] <= ctx["HSUB"] + 1e-12, ctx["EPS_R"], 1.0)


def ground(p):
    return p[:, 1] == 0.0


def strip(p):
    return (p[:, 1] == ctx["HSUB"]) & (p[:, 0] >= ctx["Y0"] - 1e-12) \
        & (p[:, 0] <= ctx["Y1"] + 1e-12)


boundaries = (ground, strip)

(m1, m_eps_m, c, k_zz, m_zz) = m2.assemble_mixed(mesh, eps_r=eps_of)
edge_pec = m2.pec_edge_mask(mesh, boundaries)
node_pec = m2.pec_node_mask(mesh, boundaries)
free_e = np.flatnonzero(~edge_pec)
free_n = np.flatnonzero(~node_pec)
n_e, n_n = int(free_e.size), int(free_n.size)

h_blk = (k_zz[free_n][:, free_n]
         - k0 * k0 * m_zz[free_n][:, free_n]).tocsc()
c_f = c[free_e][:, free_n].tocsc()
m1_f = m1[free_e][:, free_e].tocsc()

print("mesh nodes/tris/edges : %d / %d / %d" % (mesh.n_nodes, mesh.n_tris, mesh.n_edges))
print("free_e (n_e)          :", n_e, " expected", cfg["mesh"]["free_edges"])
print("free_n (n_n)          :", n_n, " expected", cfg["mesh"]["free_nodes"])
print("nnz(h_blk)            :", int(h_blk.nnz), " expected", cfg["mesh"]["nnz_h"])
print("nnz(c_f)              :", int(c_f.nnz), " expected", cfg["mesh"]["nnz_c"])
print("nnz(m1_f)             :", int(m1_f.nnz))
print("h_blk shape           :", h_blk.shape, " m1_f shape:", m1_f.shape,
      " c_f shape:", c_f.shape)

h = h_blk.toarray()
m1d = m1_f.toarray()
cfd = c_f.toarray()

# ---------------- 1. symmetry ----------------
h_asym = float(np.max(np.abs(h - h.T)))
print("\n[1] ||h - h.T||_max =", repr(h_asym))
print("    nnz(h - h.T)     =", int(np.count_nonzero(h - h.T)))
print("    ||h||_max        =", r(np.max(np.abs(h))))

# ---------------- 2. Cholesky on h ----------------
print("\n[2] cholesky(h):")
try:
    L = sla.cholesky(h, lower=True)
    print("    SUCCESS (scipy.linalg.cholesky, lower=True)")
    print("    max|L@L.T - h| =", r(np.max(np.abs(L @ L.T - h))))
except Exception as exc:
    print("    FAILED:", type(exc).__name__, str(exc))
    # manual outer-product Cholesky to locate the first non-positive pivot
    A = h.copy()
    n = A.shape[0]
    first_bad = None
    piv = []
    for j in range(n):
        d = A[j, j] - A[j, :j] @ A[j, :j]
        if d <= 0.0 and first_bad is None:
            first_bad = j
            print("    first non-positive pivot index =", j, " pivot value =", repr(float(d)))
            break
        piv.append(float(d))
        Ljj = np.sqrt(d)
        A[j + 1:, j] = (A[j + 1:, j] - A[j + 1:, :j] @ A[j, :j]) / Ljj
        A[j, j] = Ljj
    if first_bad is None:
        print("    manual Cholesky completed (no non-positive pivot)")
    print("    min pivot seen before break =", repr(min(piv)) if piv else "n/a")

# ---------------- 3. pivoted LDLt on h ----------------
print("\n[3] scipy.linalg.ldl(h):")
lu, d, perm = sla.ldl(h)
dd = np.asarray(d)
print("    D shape:", dd.shape)
diagD = np.diag(dd)
print("    min(diag(D))          =", r(diagD.min()))
print("    count(diag(D) < 0)    =", int(np.count_nonzero(diagD < 0)))
print("    count(diag(D) == 0)   =", int(np.count_nonzero(diagD == 0)))
print("    max(diag(D))          =", r(diagD.max()))
# proper inertia of the (possibly 2x2-block) D
evD = np.linalg.eigvalsh(dd)
print("    inertia of D (eig sign): neg =", int(np.count_nonzero(evD < 0)),
      " zero =", int(np.count_nonzero(evD == 0)),
      " pos =", int(np.count_nonzero(evD > 0)))
print("    min eig(D) =", r(evD.min()), "  max eig(D) =", r(evD.max()))

# ---------------- 4. min diag(h), cond ----------------
print("\n[4] min(diag(h)) =", r(np.diag(h).min()),
      "   max(diag(h)) =", r(np.diag(h).max()))
print("    cond_2(h) (svd) =", r(np.linalg.cond(h)))
print("    ||h^-1||_inf    =", r(np.linalg.norm(np.linalg.inv(h), np.inf)))

# ---------------- 5/6. m1_f positive definite ----------------
print("\n[5] cholesky(m1_f):")
try:
    L1 = sla.cholesky(m1d, lower=True)
    print("    SUCCESS; max|L1@L1.T - m1_f| =", r(np.max(np.abs(L1 @ L1.T - m1d))))
except Exception as exc:
    print("    FAILED:", type(exc).__name__, str(exc))
print("    min(diag(m1_f)) =", r(np.diag(m1d).min()))
ev1 = np.linalg.eigvalsh(m1d)
print("    min eig(m1_f) =", r(ev1.min()), "  max eig(m1_f) =", r(ev1.max()),
      "  #neg =", int(np.count_nonzero(ev1 < 0)))
del ev1

# ---------------- 7. full M_C = [[m1_f, -c],[-c^T, h]] ----------------
MC = sp.vstack([sp.hstack([m1_f, (-c_f).tocsc()], format="csc"),
                sp.hstack([(-c_f.T).tocsc(), h_blk], format="csc")],
               format="csc").toarray()
print("\n[6] M_C shape =", MC.shape, " nnz =", int(np.count_nonzero(MC)))
print("    ||M_C - M_C.T||_max =", r(np.max(np.abs(MC - MC.T))))
ev = sla.eigh(MC, eigvals_only=True, check_finite=False)
print("    n_eig =", ev.size)
print("    min eig =", repr(float(ev[0])))
print("    max eig =", repr(float(ev[-1])))
print("    #(eig < 0)   =", int(np.count_nonzero(ev < 0)))
print("    #(eig == 0)  =", int(np.count_nonzero(ev == 0)))
print("    #(eig > 0)   =", int(np.count_nonzero(ev > 0)))
print("    3 smallest eig =", repr([float(x) for x in ev[:3]]))
print("    3 largest  eig =", repr([float(x) for x in ev[-3:]]))
print("    smallest |eig| =", repr(float(np.min(np.abs(ev)))))
print("    cond2(M_C) eigh-spectrum ratio (|max|/|min|) =", repr(float(abs(ev[-1]) / abs(ev[0]))))
print("    cond2(M_C) np.linalg.cond =", repr(float(np.linalg.cond(MC))))
print("\n[rung1 SKIPPED] rung1 M_C is 3207x3207 / 2404 free edges -- exactly at the")
print("    dense-QZ fence, so not permitted; rung0 alone settles the question.")
print("\nDONE jobB")
