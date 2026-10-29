# PROVENANCE: promoted from .scratch/d582/ by D58.2 on 2026-10-29.
# See docs/design/d58_extraction_acceptance.md sections 10.7.3-10.7.6 and 10.8.
# WHAT IT DOES: runs the probe across rungs 0-3 and produces the ladder tables:
#   J_a and J_c-half per rung, the residuals, the mask-drop sensitivity, the
#   element-straddle table (which z-element each reporting column falls in, per
#   rung) and the per-rung archive metadata used in 10.8.1.
# OUTPUT: .scratch/d582/t1_allrungs.json
# HARD GATES: as for t1_probe.py. NEVER load rung 4.
# NOTE: the element-straddle table is the evidence that withdrew the (c-half)
#   construction as PRIMARY. If this script is changed so that it re-derives the
#   straddle from a different lattice, that finding no longer follows from it.
# ORIGINAL PATH: .scratch/d582/t1_allrungs.py (copy retained there).

import sys, json, dataclasses
sys.path.insert(0, '/workspace')
import numpy as np
from emfit import mode2d as m2

def sc(d, k):
    return float(np.atleast_1d(d[k]).ravel()[0])

CELL=1e-4; NYN=201; NZN=77
yn=np.arange(NYN)*CELL; zc=(np.arange(NZN-1)+0.5)*CELL
iyy,izz=np.meshgrid(yn,zc,indexing='ij')
PTS=np.stack([iyy.ravel(),izz.ravel()],1)
ROWS=np.arange(NYN)
mask=(ROWS<85)|(ROWS>115); ins=~mask
NAMES={f.name for f in dataclasses.fields(m2.Mode2D)}

def field(d):
    free_e=np.asarray(d['free_e'])
    col=int(sc(d,'bank_col'))
    x=np.real(d['vecs_real'][:,col]); x=x/np.linalg.norm(x)
    mesh=m2.structured_mesh(np.asarray(d['xs'],dtype=float), np.asarray(d['zs'],dtype=float))
    assert mesh.n_edges==int(sc(d,'n_edges')), (mesh.n_edges, int(sc(d,'n_edges')))
    assert mesh.n_nodes==int(sc(d,'n_nodes')), (mesh.n_nodes, int(sc(d,'n_nodes')))
    e_t=np.zeros(mesh.n_edges); e_t[free_e]=x
    kw=dict(freq=sc(d,'f0'),k0=sc(d,'k0'),beta=sc(d,'beta'),beta_sq=sc(d,'beta_sq'),
            eps_eff=sc(d,'eps_eff'),residual=sc(d,'residual'),candidates=(),curl_ratio=None,
            chosen=col,sigma=1.0,n_dof=int(free_e.size),n_pec=int(mesh.n_edges-free_e.size),
            e_t=e_t,mesh=mesh,e_z=None)
    MODE=m2.Mode2D(**{k:v for k,v in kw.items() if k in NAMES})
    E=MODE.e_at(PTS).reshape(NYN,NZN-1,2)[:,:,1]*CELL
    return E, mesh, col, free_e

RUNG=[(1,'rung1_s16_a12_z10-5-5'),(2,'rung2_s20_a15_z12-6-6'),(3,'rung3_s24_a18_z14-7-7')]
res=[]
for k,sub in RUNG:
    try:
        d=np.load('tools/host/sparse-probe/out/%s/c1_spectrum.npz'%sub, allow_pickle=False)
        E,mesh,col,free_e=field(d)
        with np.errstate(divide='ignore', invalid='ignore'):
            r=E[mask,16]/E[mask,15]
            r2=E[:,17]/E[:,16]
            dev=np.abs(r2-1.0)
            ref=np.abs(E[:,16]); good=ref>=0.01*ref.max()
            o=dict(rung=k, sub=sub)
            o['n_edges']=int(mesh.n_edges); o['n_nodes']=int(mesh.n_nodes)
            o['ndof']=int(free_e.size); o['bank_col']=col
            o['identified_col']=int(sc(d,'identified_col')); o['n_eligible']=int(sc(d,'n_eligible'))
            o['R_extracted']=sc(d,'R_extracted'); o['R_by_col']=sc(d,'R_by_col')
            o['corr_ez_vv']=sc(d,'corr_ez_vv')
            J1=float(np.median(r))
            o['J1']=J1
            o['q25']=float(np.percentile(r,25)); o['q75']=float(np.percentile(r,75))
            o['J1_instrip']=float(np.median(E[ins,16]/E[ins,15]))
            o['n_neg_mask']=int(np.sum(r<0))
            idx=np.argsort(r)[:3]
            o['three_smallest_r']=[[int(mask.nonzero()[0][i]), float(r[i])] for i in idx]
            o['J2']=float(np.median(E[mask,17]/E[mask,16]))
            o['Jsub']=float(np.median(E[mask,15]/E[mask,14]))
            o['J2_max_abs_dev']=float(np.nanmax(dev))
            o['J2_dev_median_all']=float(np.nanmedian(dev))
            o['J2_dev_median_good']=float(np.nanmedian(dev[good]))
            o['n_bad_gt_1e-12']=int(np.sum(dev>1e-12))
            o['pct_vs_4p3991693494']=100.0*(J1/4.3991693494-1.0)
            o['pct_vs_4p4']=100.0*(J1/4.4-1.0)
            res.append(o)
            print('RUNG',k,'ok', json.dumps({a:o[a] for a in ('J1','q25','q75','J2','Jsub')}))
    except Exception as e:
        res.append({'rung':k,'error':repr(e)})
        print('RUNG',k,'ERROR',repr(e))

# rung-0 quantile provenance diagnostic
d0=np.load('tools/host/sparse-probe/out/rung0_s12_a9_z8-4-4/c1_spectrum.npz', allow_pickle=False)
E0,_,_,_=field(d0)
r0=E0[mask,16]/E0[mask,15]
diag=dict(
  sorted_r_38_to_50=[float(v) for v in np.sort(r0)[38:51]],
  p25_p75_by_method={m:[float(np.percentile(r0,25,method=m)), float(np.percentile(r0,75,method=m))]
                     for m in ['linear','lower','higher','nearest','midpoint']},
  rank_of_2p8353371399424034=int(np.searchsorted(np.sort(r0), 2.8353371399424034)),
  q25_linear=float(np.percentile(r0,25)), q75_linear=float(np.percentile(r0,75)),
  n_mask=int(r0.size))
out={'rungs':res,'rung0_quantile_diag':diag}
json.dump(out, open('.scratch/d582/t1_allrungs.json','w'), indent=1)
print('DIAG', json.dumps(diag, indent=1))
print('WROTE .scratch/d582/t1_allrungs.json')
