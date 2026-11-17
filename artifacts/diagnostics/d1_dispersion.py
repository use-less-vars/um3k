import numpy as np, json
P='/workspace/artifacts/reference_sim_volume.npz'
d=np.load(P, allow_pickle=True)
ez=d['ez_ycut']            # (2400,62,22) f32
x=d['x_mm'].astype(float); z=d['z_mm'].astype(float)
cell=float(d['cell_m'])*1e3; dt=float(d['dt_s'])
v_meas=float(d['v_measured_m_s']); v_an=float(d['v_analytic_m_s'])
NT=ez.shape[0]
print('ez_ycut',ez.shape,'cell_mm',cell,'dt_s',dt)
print('v_measured',v_meas,'v_analytic',v_an,'v*dt mm',v_meas*dt*1e3)

# per-frame profile: |Ez| max over z  -> f(x)
prof=np.empty((NT,x.size),dtype=np.float32)
for f in range(NT):
    prof[f]=np.abs(ez[f]).max(axis=1)
gmax=float(prof.max()); gi,gx=np.unravel_index(int(np.argmax(prof)),prof.shape)
print('global |Ez| max %.4f V/m at frame %d, x=%.2f mm'%(gmax,gi,x[gx]))

# ---- peak tracking (parabolic sub-sample) over the travelling window
def peakpos(f, lo=5, hi=57):
    p=prof[f,lo:hi]
    k=int(np.argmax(p))
    if 0<k<len(p)-1:
        y0,y1,y2=p[k-1],p[k],p[k+1]
        den=(y0-2*y1+y2)
        off=0.5*(y0-y2)/den if den!=0 else 0.0
    else: off=0.0
    return x[lo+k]+off*cell, float(p[k]), lo+k
rows=[]
for f in range(120,400):
    xp,amp,ki=peakpos(f)
    rows.append((f,xp,amp,ki))
amp_arr=np.array([r[2] for r in rows])
strong=[r for r in rows if r[2]>0.3*gmax]     # well above noise
print('peak-track window: frames %d..%d, %d frames above 30%% of max'%(rows[0][0],rows[-1][0],len(strong)))
if strong:
    print('  first strong frame %d (x=%.3f mm amp=%.3f)'%(strong[0][0],strong[0][1],strong[0][2]))
    print('  last  strong frame %d (x=%.3f mm amp=%.3f)'%(strong[-1][0],strong[-1][1],strong[-1][2]))
    # per-step displacement from the strong run
    dstep=[]
    for a,b in zip(strong[:-1],strong[1:]):
        if b[0]-a[0]==1: dstep.append(b[1]-a[1])
    dstep=np.array(dstep)
    print('  consecutive-frame peak displacement: n=%d median %.4f mm  mean %.4f  IQR %.4f..%.4f'%(
        dstep.size,np.median(dstep),dstep.mean(),np.percentile(dstep,25),np.percentile(dstep,75)))
    tot=strong[-1][1]-strong[0][1]; nst=strong[-1][0]-strong[0][0]
    print('  span: x %.3f -> %.3f mm over %d steps = %.4f mm/step'%(strong[0][1],strong[-1][1],nst,tot/nst))
    print('  implied v = %.5e m/s (ratio to v_measured %.3f)'%(tot/nst*1e-3/dt,(tot/nst*1e-3/dt)/v_meas))

# ---- cross-correlation of consecutive profiles (window x index 12..52)
lo,hi=12,53
def lag_mm(a,b,maxlag=8):
    a=a[lo:hi]-a[lo:hi].mean(); b=b[lo:hi]-b[lo:hi].mean()
    na=np.linalg.norm(a); nb=np.linalg.norm(b)
    if na==0 or nb==0: return None,0.0
    best=None
    rs={}
    for L in range(-maxlag,maxlag+1):
        s=0.0; n=0
        for i in range(a.size):
            j=i+L
            if 0<=j<b.size:
                s+=a[i]*b[j]; n+=1
        if n< a.size-abs(L)-2: continue
        rs[L]=s/(na*nb)
    if not rs: return None,0.0
    Ls=sorted(rs); vals=[rs[L] for L in Ls]
    k=int(np.argmax(vals)); L=Ls[k]
    off=0.0
    if 0<k<len(vals)-1:
        den=(vals[k-1]-2*vals[k]+vals[k+1])
        if den!=0: off=0.5*(vals[k-1]-vals[k+1])/den
    return (L+off)*cell, vals[k]
print('\ncross-correlation, window x idx %d..%d'%(lo,hi-1))
for rng in [(160,340),(200,320),(200,260),(150,200),(340,600)]:
    ds=[];cs=[]
    for f in range(rng[0],rng[1]):
        L,c=lag_mm(prof[f],prof[f+1])
        if L is not None and c>0.5:
            ds.append(L); cs.append(c)
    if ds:
        ds=np.array(ds)
        print('  frames %d..%d: n=%d median %.4f mm/step mean %.4f  v=%.5e m/s  (median corr %.3f)'%(
            rng[0],rng[1]-1,ds.size,np.median(ds),ds.mean(),np.median(ds)*1e-3/dt,np.median(cs)))
    else:
        print('  frames %d..%d: no usable lag'%rng)

# ---- per-frame p99.5 "breathing" (shared scale vs per-frame scale)
ceil=float(np.percentile(np.abs(ez[::20]).ravel(),99.5))   # cheap global-ish ceiling
p=[];frames=list(range(0,NT,40))+[NT-1]
for f in frames:
    a=np.abs(ez[f])
    p.append((f,float(a.max()),float(np.percentile(a,99.5))))
print('\nglobal p99.5 over every 20th frame = %.4f V/m ; global max = %.4f'%(ceil,gmax))
print('frame  |Ez|max   p99.5    p99.5/global_p99.5')
for f,mx,pq in p:
    print('%5d %9.4f %9.4f   %8.4f'%(f,mx,pq,pq/ceil))
json.dump({'gmax':gmax,'gmax_frame':int(gi),'gmax_x_mm':float(x[gx])},open('/workspace/artifacts/diagnostics/d1_head.json','w'))
