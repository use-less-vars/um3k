import numpy as np
d=np.load('/workspace/artifacts/reference_sim_volume.npz',allow_pickle=True)
ez=d['ez_ycut']; x=d['x_mm'].astype(float); cell=float(d['cell_m'])*1e3
dt=float(d['dt_s']); v_meas=float(d['v_measured_m_s'])
NT=ez.shape[0]
prof=np.empty((NT,x.size))
for f in range(NT): prof[f]=np.abs(ez[f]).max(axis=1)
print('v_meas*dt = %.5f mm/step ; per 100 steps = %.3f mm ; domain x = %.1f mm'%(
    v_meas*dt*1e3, v_meas*dt*1e3*100, x[-1]))
# centroid of p^2 over the interior (drop the 3 cells at each end)
lo,hi=3,59
xs=x[lo:hi]
def cent(f):
    p=prof[f,lo:hi]**2
    s=p.sum()
    return (xs*p).sum()/s if s>0 else np.nan
def front(f,frac=0.2):
    p=prof[f]
    m=p.max()
    if m<=0: return np.nan
    idx=np.nonzero(p>frac*m)[0]
    return x[idx[0]] if idx.size else np.nan
print('\ncentroid & leading-edge tracking (frames 150..380)')
prev=None; dc=[]; df=[]
for f in range(150,381):
    c=cent(f); fr=front(f)
    if prev is not None:
        pfc,pff,pxc=prev
        if np.isfinite(c) and np.isfinite(pfc): dc.append((f,c-pfc))
        if np.isfinite(fr) and np.isfinite(pff): df.append((f,fr-pff))
    prev=(c,fr,c)
for name,arr in (('centroid',dc),('leading edge (20%% of frame max)',df)):
    a=np.array([v for _,v in arr])
    a=a[np.abs(a)<0.4]        # drop jumps off the grid ends
    print('  %-30s n=%3d median %+.4f  mean %+.4f  IQR %+.4f..%+.4f mm/step -> v=%.3e m/s'%(
        name,a.size,np.median(a),a.mean(),np.percentile(a,25),np.percentile(a,75),np.median(a)*1e-3/dt))
# windowed medians
for lo_f,hi_f in ((150,200),(200,260),(260,320),(320,380),(380,500)):
    a=np.array([v for f,v in dc if lo_f<=f<hi_f]); a=a[np.abs(a)<0.4]
    b=np.array([v for f,v in df if lo_f<=f<hi_f]); b=b[np.abs(b)<0.4]
    if a.size or b.size:
        print('  frames %3d-%3d: centroid %.4f mm (n=%d)   front %.4f mm (n=%d)'%(
            lo_f,hi_f-1,np.median(a) if a.size else float('nan'),a.size,
            np.median(b) if b.size else float('nan'),b.size))
# energy decay
print('\nframe energy sum(|Ez|^2) per plane, every 200 frames')
for f in range(0,NT,200):
    a=np.abs(ez[f]); print('  %4d  %.4e'%(f,float((a*a).sum())))
