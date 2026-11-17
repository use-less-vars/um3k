import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
z=np.load('artifacts/reference_sim_volume.npz',allow_pickle=True)
x=z['x_mm'].astype(float); zz=z['z_mm'].astype(float); j=106
frames=[3,4,12]
A=[np.abs(z['ez_ycut'][f]) for f in frames]   # (x,z)
g=float(max(a.max() for a in A)); g=max(g,1e-30)
fig,ax=plt.subplots(1,3,figsize=(11,3.2))
for i,a in enumerate(A):
    im=ax[i].imshow(a.T,origin='lower',aspect='auto',extent=[x[0],x[-1],zz[0],zz[-1]],
                    cmap='turbo',vmin=0,vmax=g)
    ax[i].set_title('ez_ycut frame %d (max %.2e V/m)'%(frames[i],a.max()),fontsize=8)
    ax[i].set_xlabel('x [mm]',fontsize=7); ax[i].set_ylabel('z [mm]',fontsize=7)
    ax[i].tick_params(labelsize=6)
fig.suptitle('SHARED linear colour scale vmin=0 vmax=%.2e V/m : frames 3/4/12 are turn-on (|Ez|~1e-13)'%g,fontsize=8)
fig.colorbar(im,ax=ax,shrink=0.8,label='|Ez| [V/m]')
fig.savefig('artifacts/diagnostics/b1_ez_ycut_frames_3_4_12_shared_scale.png',dpi=90,bbox_inches='tight')
print('b1 ok',g)
