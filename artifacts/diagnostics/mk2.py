import numpy as np, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
z=np.load('artifacts/reference_sim_volume.npz',allow_pickle=True)
x=z['x_mm'].astype(float); zz=z['z_mm'].astype(float)
frames=[3,4,12]
fig,ax=plt.subplots(1,3,figsize=(11,3.2))
for i,f in enumerate(frames):
    a=np.abs(z['ez_ycut'][f]); vm=float(np.percentile(a,99.5)) or 1e-30
    im=ax[i].imshow(a.T,origin='lower',aspect='auto',extent=[x[0],x[-1],zz[0],zz[-1]],cmap='turbo',vmin=0,vmax=vm)
    ax[i].set_title('frame %d, own p99.5 vmax=%.2e (max %.2e)'%(f,vm,a.max()),fontsize=8)
    ax[i].set_xlabel('x [mm]',fontsize=7); ax[i].tick_params(labelsize=6)
    fig.colorbar(im,ax=ax[i],shrink=0.8)
fig.suptitle('PER-FRAME percentile scale: empty turn-on frames render as full-contrast structure (breathing)',fontsize=8)
fig.savefig('artifacts/diagnostics/b2_ez_ycut_frames_3_4_12_per_frame_scale.png',dpi=90,bbox_inches='tight')
print('b2 ok')
