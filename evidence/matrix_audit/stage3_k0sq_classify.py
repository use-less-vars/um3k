# EVIDENCE TIER. Unreviewed. Not production-adjacent, do not gate.
# Copied unchanged from .scratch/d161/ (session artefact; .scratch is not durable).
import json
import numpy as np
K0=209.78570331727553; ER=4.4; K0SQ=K0*K0; T2=ER*K0SQ
def orth(Z):
    U,s,_=np.linalg.svd(Z,full_matrices=False)
    return U[:, s>s[0]*1e-10]
out={}
for tag,fn in (("h040","eig_h004.npz"),("h080","eig_h008.npz")):
    d=np.load("/workspace/.scratch/d161/"+fn)
    lam=d["lam"]; vec=d["vec"]; Zair=d["Zair"]; Zsub=d["Zsub"]; hct=d["hct"]
    lr=lam.real; Qa=orth(Zair); Qs=orth(Zsub)
    r=dict(tag=tag,ne=int(Zair.shape[0]),n=int(lam.size),k0_sq=float(K0SQ),T_er=float(T2),
           dimZ=int(Qa.shape[1]),dimZsub=int(Qs.shape[1]),
           imag_rel=int((np.abs(lam.imag)>1e-6*np.abs(lr)).sum()),
           imag_max=float(np.max(np.abs(lam.imag)/np.abs(lr))),
           n_neg=int((lr<0).sum()),lam_min=float(lr.min()),lam_max=float(lr.max()))
    for w in (1e-6,1e-4,1e-3,1e-2,0.05,0.1,0.25,0.5,1.0):
        r[f"within_{w}"]=int((np.abs(lr-T2)/T2<=w).sum())
    for w in (1e-6,1e-3):
        r[f"within_k0_{w}"]=int((np.abs(lr-K0SQ)/K0SQ<=w).sum())
    o=np.argsort(np.abs(lr-T2))
    def row(i):
        e=vec[:,i]; n2=float(np.real(e.conj()@e)); z=hct@e; zn=float(np.real(z.conj()@z))
        qa=Qa.conj().T@e; qs=Qs.conj().T@e
        return dict(idx=int(i),lam=float(lr[i]),rel_er=float(abs(lr[i]-T2)/T2),
                    over_k0sq=float(lr[i]/K0SQ),over_T2=float(lr[i]/T2),
                    g_node=zn/(n2+zn),g_grad=float((qa.conj()@qa).real)/n2,
                    g_sub=float((qs.conj()@qs).real)/n2,
                    proj_grad=float(np.sqrt(((qa.conj()@qa).real)/n2)),
                    proj_sub=float(np.sqrt(((qs.conj()@qs).real)/n2)),
                    proj_node=float(np.sqrt(zn/(n2+zn))))
    r["near8"]=[row(i) for i in o[:8]]
    iTEM=int(np.argmin(np.abs(lam-148241.5356984401)))
    et=vec[:,iTEM]
    r["TEM"]=dict(idx=iTEM,lam=float(lr[iTEM]))
    r["near8_TEMcos2"]=[float(abs(et.conj()@vec[:,i])**2/(np.real(et.conj()@et)*np.real(vec[:,i].conj()@vec[:,i]))) for i in o[:8]]
    # baseline over whole spectrum
    Gn=[];Gg=[]
    for i in range(0,lam.size):
        e=vec[:,i]; n2=float(np.real(e.conj()@e)); z=hct@e; zn=float(np.real(z.conj()@z))
        Gn.append(zn/(n2+zn)); qa=Qa.conj().T@e; Gg.append(float((qa.conj()@qa).real)/n2)
    r["base_node"]=dict(median=float(np.median(Gn)),p90=float(np.quantile(Gn,0.9)),max=float(np.max(Gn)))
    r["base_grad"]=dict(median=float(np.median(Gg)),p90=float(np.quantile(Gg,0.9)),max=float(np.max(Gg)))
    # how many modes have >0.9 of energy in span(Z)?
    r["n_grad_dom"]=int(np.sum(np.array(Gg)>0.9))
    # modes whose lam is within 1e-3 of a *multiple* of k0^2 with multiplier in {1,4.4,19.36}
    r["mult_check"]={m:int((np.abs(lr-m*K0SQ)/(m*K0SQ)<=1e-3).sum()) for m in (1.0,ER,ER*ER)}
    out[tag]=r
    print("="*12,tag)
    print(json.dumps({k:v for k,v in r.items() if not isinstance(v,(list,dict))},indent=0))
    print("near8:")
    for x in r["near8"]: print("  ",json.dumps({k:(round(v,10) if isinstance(v,float) else v) for k,v in x.items()}))
    print("TEM",r["TEM"],"cos2 to near8:",[round(c,4) for c in r["near8_TEMcos2"]])
    print("base_node",r["base_node"],"base_grad",r["base_grad"],"n_grad_dom",r["n_grad_dom"],"mult",r["mult_check"])
json.dump(out,open("/workspace/.scratch/d161/stage3.json","w"),indent=1)
