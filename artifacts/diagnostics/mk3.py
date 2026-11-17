import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
z=np.load('artifacts/reference_sim_volume.npz',allow_pickle=True)
x=z['x_mm'].astype(float); zz=z['z_mm'].astype(float)
k=3; a=np.abs(z['e_abs_volume'][k,:,106,:]); b=np.abs(z['e_abs_volume'][k+1,:,106,:])
g=max(a.max(),b.max())
fig,ax=plt.subplots(1,2,figsize=(9,3))
for i,d in enumerate((a,b)):
    ax[i].imshow(d.T,origin='lower',aspect='auto',extent=[x[0],x[-1],zz[0],zz[-1]],cmap='turbo',vmin=0,vmax=g)
    ax[i].set_title('volume k=%d -> step %d (max %.1f V/m)'%(k+i,301+100*i,d.max()),fontsize=8)
    ax[i].set_xlabel('x [mm]',fontsize=7); ax[i].tick_params(labelsize=6)
fig.suptitle('e_abs_volume y=42.4 mm, shared linear scale; 100 steps = 10.5 mm = 43%% of 24.4 mm domain',fontsize=8)
fig.savefig('artifacts/diagnostics/b3_volume_xz_k3_k4_shared_scale.png',dpi=80,bbox_inches='tight')
print('b3 written')
