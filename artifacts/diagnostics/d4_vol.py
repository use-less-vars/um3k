import numpy as np
z=np.load('artifacts/reference_sim_volume.npz',allow_pickle=True)
si=z['e_abs_volume_step_index'].astype(int); v=z['e_abs_volume']
x=z['x_mm'].astype(float); y=z['y_mm'].astype(float); zz=z['z_mm'].astype(float)
print('step_index',si.tolist())
out=[]
for k in range(v.shape[0]):
    a=np.abs(v[k]); i=np.unravel_index(int(a.argmax()),a.shape)
    out.append((k,int(si[k]),float(a.max()),x[i[0]],y[i[1]],zz[i[2]]))
for r in out[:14]: print('k=%2d step %4d max %8.3f V/m at x=%.1f y=%.1f z=%.1f mm'%r)
import json; json.dump(out,open('artifacts/diagnostics/volume_max_track.json','w'))
p=np.array([[r[2],r[3],r[5]] for r in out])
print('k=3->4 peak x %.2f -> %.2f (d=%.2f mm, %.2f mm/frame)'%(p[3,1],p[4,1],p[4,1]-p[3,1],p[4,1]-p[3,1]))
print('k=3->12: x %.2f -> %.2f over 9 frames = %.3f mm/frame'%(p[3,1],p[12,1],(p[12,1]-p[3,1])/9))
