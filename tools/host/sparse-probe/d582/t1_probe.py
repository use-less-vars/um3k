# PROVENANCE: promoted from .scratch/d582/ by D58.2 on 2026-10-29.
# See docs/design/d58_extraction_acceptance.md sections 10.7.2, 10.7.4 and 10.8.
# WHAT IT DOES: single-rung probe. Loads ONE banked rung archive, reconstructs the
#   interface-normal ratio of E_z from the banked field, and reports it under
#   construction (a) (metric-lattice one row either side) and construction
#   (c-half). This is the script that first made the 13.85 % deficit
#   script-reproducible instead of doc-only.
# OUTPUT: .scratch/d582/t1_probe_out.json
# HARD GATES, in order, both must pass before any number is quoted:
#   1. rung-0 J1 must reproduce 3.7903993750636298 to absdiff < 1e-12
#      (achieved: 8.9e-16).
#   2. NEVER load rung 4. Its archive is 9604 x 9604, ~738 MB, and buys nothing:
#      R at rung 4 is already in evidence/t4/rung4_dense_anchor.json
#      (3.575412753195199) and the dense anchor record is the authority for it.
# ORIGINAL PATH: .scratch/d582/t1_probe.py (copy retained there).

import sys, os, json, glob, zipfile
sys.path.insert(0, '/workspace')
import numpy as np
try:
    from emfit import mode2d as m2
except Exception:
    import emfit.mode2d as m2
print('m2 from', m2.__file__, 'has structured_mesh', hasattr(m2,'structured_mesh'), 'Mode2D', hasattr(m2,'Mode2D'))

out = {}
# ---------------- TASK 1 ----------------
import dataclasses
P = 'tools/host/sparse-probe/out/rung0_s12_a9_z8-4-4/c1_spectrum.npz'
d = np.load(P, allow_pickle=False)
CELL=1e-4; W=0.02; H=7.6e-3; HSUB=1.6e-3; Y0=0.0085; Y1=0.0115; NYN=201; NZN=77
def sc(k): return float(np.atleast_1d(d[k]).ravel()[0])
assert np.isclose(sc('k0'), 164.17940719617263)
axis=lambda e,c: np.concatenate([np.linspace(a,b,n+1) if i==0 else np.linspace(a,b,n+1)[1:]
                                for i,((a,b),n) in enumerate(zip(e,c))])
XS=axis([(0.,Y0),(Y0,Y1),(Y1,W)],[9,12,9])
ZS=axis([(0.,HSUB),(HSUB,3.6e-3),(3.6e-3,H)],[8,4,4])
print('XS==banked', np.array_equal(XS, d['xs']), 'ZS==banked', np.array_equal(ZS, d['zs']))
mesh=m2.structured_mesh(XS,ZS)
print('mesh n_edges', mesh.n_edges, 'n_nodes', mesh.n_nodes)
assert mesh.n_edges==int(d['n_edges'])==1486 and mesh.n_nodes==int(d['n_nodes'])==527
free_e=d['free_e']; col=int(d['bank_col']); print('bank_col',col,'chosen',int(d['chosen_col']))
x=np.real(d['vecs_real'][:,col]); x=x/np.linalg.norm(x)
e_t=np.zeros(mesh.n_edges); e_t[free_e]=x
kw=dict(freq=sc('f0'),k0=sc('k0'),beta=sc('beta'),beta_sq=sc('beta_sq'),
        eps_eff=sc('eps_eff'),residual=sc('residual'),candidates=(),curl_ratio=None,
        chosen=col,sigma=1.0,n_dof=int(free_e.size),n_pec=int(mesh.n_edges-free_e.size),
        e_t=e_t,mesh=mesh,e_z=None)
names={f.name for f in dataclasses.fields(m2.Mode2D)}
print('Mode2D fields', sorted(names))
MODE=m2.Mode2D(**{k:v for k,v in kw.items() if k in names})
yn=np.arange(NYN)*CELL; zc=(np.arange(NZN-1)+0.5)*CELL
iyy,izz=np.meshgrid(yn,zc,indexing='ij')
E=MODE.e_at(np.stack([iyy.ravel(),izz.ravel()],1)).reshape(NYN,NZN-1,2)[:,:,1]*CELL
mask=(np.arange(NYN)<85)|(np.arange(NYN)>115)
ins =~mask
J1=float(np.median(E[mask,16]/E[mask,15]))
o={}
o['J1']=J1
o['GATE_absdiff']=abs(J1-3.7903993750636298)
o['n_mask']=int(mask.sum()); o['n_in']=int(ins.sum())
o['J1_q25']=float(np.percentile(E[mask,16]/E[mask,15],25))
o['J1_q75']=float(np.percentile(E[mask,16]/E[mask,15],75))
o['J1_instrip_median']=float(np.median(E[ins,16]/E[ins,15]))
o['J1_row86']=float(E[86,16]/E[86,15])
o['J1_row85']=float(E[85,16]/E[85,15])
o['J1_row84']=float(E[84,16]/E[84,15]); o['J1_row116']=float(E[116,16]/E[116,15])
o['J2_piecewise_identical_16_17']=bool(np.array_equal(E[:,16],E[:,17]))
o['J2_median']=float(np.median(E[mask,17]/E[mask,16]))
o['J2_max_abs_dev']=float(np.max(np.abs(E[:,17]/E[:,16]-1.0)))
o['J2_n_bad_gt_1e-12']=int(np.sum(np.abs(E[:,17]/E[:,16]-1.0)>1e-12))
o['Jsub_median_col15_14']=float(np.median(E[mask,15]/E[mask,14]))
o['ratio_vs_analytic_4p3991693494_pct']=100.0*(J1/4.3991693494-1.0)
o['ratio_vs_4p4_pct']=100.0*(J1/4.4-1.0)
o['row30_cols10_25']=[float(v) for v in E[30,10:25]]
o['zc_10_25']=[float(v) for v in zc[10:25]]
o['E_col_mean_abs']=[float(np.mean(np.abs(E[:,k]))) for k in range(NZN-1)]
out['task1']=o
print('TASK1', json.dumps(o, indent=1))

# ---------------- TASK 2 ----------------
t2=[]
for p in sorted(glob.glob('tools/host/sparse-probe/out/**/*.npz', recursive=True)):
    info={'path':p}
    with zipfile.ZipFile(p) as zf:
        names=zf.namelist()
        info['n_members']=len(names)
        info['members']=sorted(n[:-4] for n in names if n.endswith('.npy'))
        if 'vecs_real.npy' in names:
            with zf.open('vecs_real.npy') as f:
                magic=np.lib.format.read_magic(f)
                if magic==(1,0):
                    shape,fortran,dtype=np.lib.format.read_array_header_1_0(f)
                else:
                    shape,fortran,dtype=np.lib.format.read_array_header_2_0(f)
            info['vecs_real_shape']=list(shape); info['vecs_real_dtype']=str(dtype)
    t2.append(info)
out['task2']=t2
print('TASK2', json.dumps(t2, indent=1))
json.dump(out, open('.scratch/d582/t1_probe_out.json','w'), indent=1)
print('WROTE .scratch/d582/t1_probe_out.json')
