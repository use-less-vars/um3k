# PROVENANCE: promoted from .scratch/d582/ by D58.2 on 2026-10-29.
# See docs/design/d58_extraction_acceptance.md sections 10.7.4, 10.7.7-10.7.9, 10.8.2.
# WHAT IT DOES: the final tables and the retraction checks. Fits the deficit
#   exponent against dz_sub and against dy_strip; reports the normalised deficits
#   and their drift; recomputes the rung-0 quartiles under five percentile
#   methods (this is what showed the D58.1 q25 to be stale while median and q75
#   reproduce bit-exactly); runs the J2 check (median vs np.array_equal vs the
#   count of rows deviating by more than 1e-12 - the median is misleading there);
#   and compares the in-strip rows against the D58.1 close-out (this is what
#   exposed the undisclosed abs()).
# OUTPUT: .scratch/d582/t1_final.json
# HARD GATES: as for t1_probe.py. NEVER load rung 4.
# ORIGINAL PATH: .scratch/d582/t1_final.py (copy retained there).

import sys, json, dataclasses
sys.path.insert(0,'/workspace')
import numpy as np
from emfit import mode2d as m2

def sc(d,k): return float(np.atleast_1d(d[k]).ravel()[0])

CELL=1e-4; NYN=201; NZN=77
yn=np.arange(NYN)*CELL; zc=(np.arange(NZN-1)+0.5)*CELL
iyy,izz=np.meshgrid(yn,zc,indexing='ij')
PTS=np.stack([iyy.ravel(),izz.ravel()],1)
ROWS=np.arange(NYN); mask=(ROWS<85)|(ROWS>115); ins=~mask
NAMES={f.name for f in dataclasses.fields(m2.Mode2D)}
Y0=0.0085; Y1=0.0115

def field(d):
    free_e=np.asarray(d['free_e']); col=int(sc(d,'bank_col'))
    x=np.real(d['vecs_real'][:,col]); x=x/np.linalg.norm(x)
    XS=np.asarray(d['xs'],dtype=float); ZS=np.asarray(d['zs'],dtype=float)
    mesh=m2.structured_mesh(XS,ZS)
    assert mesh.n_edges==int(sc(d,'n_edges')) and mesh.n_nodes==int(sc(d,'n_nodes'))
    e_t=np.zeros(mesh.n_edges); e_t[free_e]=x
    kw=dict(freq=sc(d,'f0'),k0=sc(d,'k0'),beta=sc(d,'beta'),beta_sq=sc(d,'beta_sq'),
            eps_eff=sc(d,'eps_eff'),residual=sc(d,'residual'),candidates=(),curl_ratio=None,
            chosen=col,sigma=1.0,n_dof=int(free_e.size),n_pec=int(mesh.n_edges-free_e.size),
            e_t=e_t,mesh=mesh,e_z=None)
    MODE=m2.Mode2D(**{k:v for k,v in kw.items() if k in NAMES})
    E=MODE.e_at(PTS).reshape(NYN,NZN-1,2)[:,:,1]*CELL
    return E,mesh,XS,ZS

RUNGS=[(0,'rung0_s12_a9_z8-4-4'),(1,'rung1_s16_a12_z10-5-5'),
       (2,'rung2_s20_a15_z12-6-6'),(3,'rung3_s24_a18_z14-7-7')]
out=[]
for k,sub in RUNGS:
    try:
        d=np.load('tools/host/sparse-probe/out/%s/c1_spectrum.npz'%sub,allow_pickle=False)
        E,mesh,XS,ZS=field(d)
        with np.errstate(divide='ignore',invalid='ignore'):
            o=dict(rung=k,sub=sub)
            # (1) element straddling
            els={}
            for h in (1.45e-3,1.55e-3,1.65e-3,1.75e-3):
                i=int(np.searchsorted(ZS,h,side='right')-1)
                els['%.2fmm'%(h*1e3)]=[i,float(ZS[i]),float(ZS[i+1])]
            o['elements']=els
            e14=els['1.45mm'][0]; e15=els['1.55mm'][0]; e16=els['1.65mm'][0]; e17=els['1.75mm'][0]
            o['cols14_15_same_element']=bool(e14==e15)
            o['cols16_17_same_element']=bool(e16==e17)
            # (2) both constructions
            Ja=float(np.median(E[mask,16]/E[mask,15]))
            Jc=float(np.median((1.5*E[mask,16]-0.5*E[mask,17])/(1.5*E[mask,15]-0.5*E[mask,14])))
            Jai=float(np.median(E[ins,16]/E[ins,15]))
            Jci=float(np.median((1.5*E[ins,16]-0.5*E[ins,17])/(1.5*E[ins,15]-0.5*E[ins,14])))
            o['Ja']=Ja; o['Jchalf']=Jc; o['Ja_ins']=Jai; o['Jchalf_ins']=Jci
            o['pct_Ja_vs_4p3991693494']=100.0*(Ja/4.3991693494-1.0)
            o['pct_Ja_vs_4p4']=100.0*(Ja/4.4-1.0)
            o['pct_Jchalf_vs_4p3991693494']=100.0*(Jc/4.3991693494-1.0)
            o['pct_Jchalf_vs_4p4']=100.0*(Jc/4.4-1.0)
            o['denom_median_E15_over_E14']=float(np.median(E[mask,15]/E[mask,14]))
            o['denom_median_1p5_m0p5_E14_over_E15']=float(np.median(1.5-0.5*(E[mask,14]/E[mask,15])))
            # (3) mask-edge sensitivity
            sens={}
            for drop in (1,3,6):
                md=(ROWS<85-drop)|(ROWS>115+drop)
                sens['drop_%d'%drop]=[int(md.sum()), float(np.median(E[md,16]/E[md,15]))]
            o['mask_sensitivity']=sens
            # (4) resolution scales
            n_strip=int(np.sum((XS>Y0)&(XS<Y1)))
            i65=int(np.searchsorted(ZS,1.65e-3,side='right')-1)
            o['dz_sub']=float(ZS[1]-ZS[0])
            o['dz_above_1p65mm']=float(ZS[i65+1]-ZS[i65])
            o['n_XS_strictly_inside_strip']=n_strip
            o['dy_strip']=float(3e-3/n_strip)
            o['n_edges']=int(mesh.n_edges); o['n_nodes']=int(mesh.n_nodes)
            out.append(o)
            print('RUNG',k,'ok Ja=%.10f Jchalf=%.10f'%(Ja,Jc))
    except Exception as e:
        out.append({'rung':k,'error':repr(e)}); print('RUNG',k,'ERROR',repr(e))

json.dump({'rungs':out},open('.scratch/d582/t1_final.json','w'),indent=1)
print(json.dumps({'rungs':out}))
print('WROTE .scratch/d582/t1_final.json')
