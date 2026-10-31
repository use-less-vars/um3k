# EVIDENCE TIER. Unreviewed. Not production-adjacent, do not gate.
# Copied unchanged from .scratch/d161/ (session artefact; .scratch is not durable).
import json, time, sys
from pathlib import Path
import numpy as np, scipy.linalg as sla, scipy.sparse as sp
ROOT = Path("/workspace"); sys.path.insert(0, str(ROOT))
from tools import host_ladder as hl
dm = hl.dm
mode2d = hl.mode2d
K0 = 209.78570331727553
ER = hl.ER
out = {}
def build(h_m, n_strip):
    pb = hl.build_modal(h_m, clearance=3.0, n_strip=n_strip, w_m=0.8e-3, k0=K0)
    mesh = pb["mesh"]; bounds = dm.boxes(pb["geo"])["open"]
    eps = dm.eps_fun(pb["geo"], ER)
    if hasattr(mode2d, "_per_triangle"):
        eps_t = mode2d._per_triangle(eps, mesh, "eps_r")
    else:
        eps_t = np.asarray(eps(mesh.centroid), float)
    mu_t = np.ones(mesh.n_tris)
    node_pec = mode2d.pec_node_mask(mesh, bounds)
    free_e = np.flatnonzero(~mode2d.pec_edge_mask(mesh, bounds))
    cols_air = mode2d._gradient_columns(mesh, eps_t, mu_t, node_pec)
    cols_sub = mode2d._gradient_columns(mesh, eps_t, mu_t, node_pec, region_contrast=float(ER - 1.0))
    Zair = mode2d._incidence(mesh, free_e, cols_air).toarray()
    Zsub = mode2d._incidence(mesh, free_e, cols_sub).toarray()
    Zun = np.hstack([Zair, Zsub])
    A = pb["A"].toarray(); C = pb["c_f"].toarray(); n_e, n_n = pb["n_e"], pb["n_n"]
    t0 = time.perf_counter()
    hct = pb["lu_h"].solve(C.T)
    B = pb["m1_f"].toarray() - C @ hct
    t_b = time.perf_counter() - t0
    t0 = time.perf_counter()
    lam, vec = sla.eig(A, B, right=True, left=False)
    t_qz = time.perf_counter() - t0
    np.savez_compressed(f"/workspace/.scratch/d161/eig_h{int(round(h_m*1e4)):03d}.npz",
                        lam=lam, vec=vec, Zair=Zair, Zsub=Zsub,
                        cols_air=cols_air, cols_sub=cols_sub, hct=hct, free_e=free_e)
    rec = dict(h_m=h_m, n_e=int(n_e), n_n=int(n_n), n_air_cols=int(cols_air.size),
               n_sub_cols=int(cols_sub.size), n_union=int(cols_air.size+cols_sub.size),
               rank_Zair=int(np.linalg.matrix_rank(Zair)), rank_Zsub=int(np.linalg.matrix_rank(Zsub)),
               rank_Zun=int(np.linalg.matrix_rank(Zun)),
               t_B=float(t_b), t_qz=float(t_qz), n_lambda=int(lam.size),
               n_imag_gt_1e6=int(np.sum(np.abs(lam.imag) > 1e-6*np.abs(lam))),
               max_rel_imag=float(np.max(np.abs(lam.imag)/max(np.abs(lam.real).max(),1e-300))))
    print(json.dumps(rec, indent=1))
    return rec
out["h040"] = build(0.4e-3, 2)
out["h080"] = build(0.8e-3, 1)
out["K0"] = K0; out["ER"] = ER; out["k0_sq"] = K0*K0; out["er_k0_sq"] = ER*K0*K0
json.dump(out, open("/workspace/.scratch/d161/stage1.json","w"), indent=1)
print("DONE")
