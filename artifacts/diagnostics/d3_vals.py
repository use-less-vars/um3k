import numpy as np
z=np.load('artifacts/reference_sim_volume.npz',allow_pickle=True)
ez=z['ez_ycut']
for f in (3,4,12,240,241):
    a=np.abs(ez[f]); print('ez_ycut f%-4d max %.6e  p99.5 %.6e  mean %.6e'%(f,a.max(),np.percentile(a,99.5),a.mean()))
v=z['e_abs_volume']
for k in (3,4,12):
    a=np.abs(v[k]); print('e_abs  k%-4d max %.6e  p99.5 %.6e  mean %.6e'%(k,a.max(),np.percentile(a,99.5),a.mean()))
print('global e_abs peak', float(np.abs(v).max()) if False else 'skip')
