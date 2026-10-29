# PROVENANCE: promoted from .scratch/d582/ by D58.2 on 2026-10-29.
# See docs/design/d58_extraction_acceptance.md sections 10.8.3 and 10.9.4.
# WHAT IT DOES: builds the exact analytic field on the same geometry and banks it
#   (analytic_control.npz) so that every construction can be run on the exact
#   solution as well as on the extracted one. This is the control that decides
#   whether a measured deficit is a property of the field or of the sampling.
# ESTABLISHED BY IT: construction (a) biases the analytic ratio 5.092 % HIGH;
#   construction (c-half) recovers 4.4 to -0.0189 %. So (a)'s bias has the wrong
#   sign to explain a LOW measurement, which is what withdrew the sampling
#   artefact outcome in 10.8.3.
# OUTPUT: .scratch/d582/analytic_control.npz
# ORIGINAL PATH: .scratch/d582/build_analytic_control.py (copy retained there).

#!/usr/bin/env python3
"""Build the analytic plane-mode reference pair exactly as
tools/host/c1-audit/c1_audit.py does, persist to .scratch/d582/analytic_control.npz,
then print diagnostics.  Writes nothing outside .scratch/d582/."""
import sys, os, json, traceback
from math import floor, ceil

sys.path.insert(0, '/workspace')
import numpy as np
import emfit.modal as M
import emfit.mode2d as m2
from emfit.mode_profile import microstrip_mode_profile

OUTDIR = '/workspace/.scratch/d582'
NPZ = os.path.join(OUTDIR, 'analytic_control.npz')
GEOJSON = '/workspace/.scratch/tol/logs/TOLFLUX.json'
os.makedirs(OUTDIR, exist_ok=True)

G = json.load(open(GEOJSON))['geometry']
W, H = G['width'], G['height']
HSUB, WSTRIP, EPS_R = G['h'], G['w'], G['eps_r']
N_SUB, K_STRIP, J_CENTRE = G['n_sub'], G['k_strip'], G['j_centre']
NY, NZ, CELL = G['ny'], G['nz'], G['cell']
Y0, Y1 = W/2 - WSTRIP/2, W/2 + WSTRIP/2


def axis(edges, cells):
    pieces = [np.linspace(a, b, n+1) for (a, b), n in zip(edges, cells)]
    out = pieces[0]
    for p in pieces[1:]:
        out = np.concatenate([out, p[1:]])
    return out


XS = axis([(0.0, Y0), (Y0, Y1), (Y1, W)], [9, 12, 9])          # C1_Y_AIR_CELLS=9, C1_STRIP_CELLS=12
ZS = axis([(0.0, HSUB), (HSUB, 0.0036), (0.0036, H)], [8, 4, 4])  # C1_Z_CELLS='8,4,4'

NYN, NZN = NY + 1, NZ + 1
yn_node = np.arange(NYN) * CELL
zn_node = np.arange(NZN) * CELL
yc_mid = (np.arange(NYN - 1) + 0.5) * CELL
zc_mid = (np.arange(NZN - 1) + 0.5) * CELL

print('geometry:', dict(CELL=CELL, HSUB=HSUB, WSTRIP=WSTRIP, EPS_R=EPS_R, Y0=Y0, Y1=Y1,
                        NY=NY, NZ=NZ, NYN=NYN, NZN=NZN, W=W, H=H,
                        K_STRIP=K_STRIP, J_CENTRE=J_CENTRE, N_SUB=N_SUB), flush=True)
print('XS len %d [-1]=%.12g  ZS len %d [-1]=%.12g' % (len(XS), XS[-1], len(ZS), ZS[-1]), flush=True)

# ---- the slow part: construction ----
try:
    prof = microstrip_mode_profile(HSUB, WSTRIP, EPS_R, n_sub=N_SUB)
    print('prof built', flush=True)
    PANA = M.plane_mode(prof, nyn=NYN, nzn=NZN, k_strip=K_STRIP,
                        iy_strip_centre=J_CENTRE, cell=CELL)
    print('plane_mode returned', flush=True)
    A_ez = np.asarray(PANA.e_z, dtype=float)   # (NYN, NZN-1) transverse NODE x height MID-CELL
    A_ey = np.asarray(PANA.e_y, dtype=float)   # (NYN-1, NZN) transverse MID-CELL x height NODE
except Exception:
    print('CONSTRUCTION FAILED -- traceback verbatim:', flush=True)
    traceback.print_exc()
    sys.stdout.flush()
    sys.exit(3)

# ---- persist FIRST ----
np.savez_compressed(
    NPZ,
    A_ez=A_ez, A_ey=A_ey, XS=XS, ZS=ZS,
    yn_node=yn_node, zn_node=zn_node, yc_mid=yc_mid, zc_mid=zc_mid,
    CELL=np.array(CELL), HSUB=np.array(HSUB), WSTRIP=np.array(WSTRIP), EPS_R=np.array(EPS_R),
    Y0=np.array(Y0), Y1=np.array(Y1), NY=np.array(NY), NZ=np.array(NZ),
    NYN=np.array(NYN), NZN=np.array(NZN), W=np.array(W), H=np.array(H),
    K_STRIP=np.array(K_STRIP), J_CENTRE=np.array(J_CENTRE), N_SUB=np.array(N_SUB),
)
print('WROTE %s bytes=%d' % (NPZ, os.path.getsize(NPZ)), flush=True)

# ================= diagnostics =================
print('\n=== (a) array fingerprints ===', flush=True)
for nm, arr in (('A_ez', A_ez), ('A_ey', A_ey)):
    print('%-5s dtype=%s shape=%s isfinite=%s min=%.17g max=%.17g sum=%.17g'
          % (nm, arr.dtype, arr.shape, bool(np.all(np.isfinite(arr))),
             float(np.min(arr)), float(np.max(arr)), float(np.sum(arr))), flush=True)

print('\n=== (b) shape guard ===', flush=True)
print('expect A_ez (%d,%d) A_ey (%d,%d); got A_ez %s A_ey %s'
      % (NYN, NZN-1, NYN-1, NZN, A_ez.shape, A_ey.shape), flush=True)
assert A_ez.shape == (NYN, NZN-1), A_ez.shape
assert A_ey.shape == (NYN-1, NZN), A_ey.shape
print('SHAPE GUARD OK', flush=True)

print('\n=== (c) height lattices ===', flush=True)
print('zc_mid[:3] =', repr(zc_mid[:3]), flush=True)
print('zc_mid[-1] = %.17g' % zc_mid[-1], flush=True)
print('diff(zc_mid)[:2] =', repr(np.diff(zc_mid)[:2]), flush=True)
print('zn_node[:3] =', repr(zn_node[:3]), flush=True)
print('zn_node[-1] = %.17g' % zn_node[-1], flush=True)

fcol = (HSUB - CELL/2) / CELL
j_below = int(floor(fcol)); j_above = int(ceil(fcol))
print('fractional column index of HSUB in zc_mid = (HSUB-CELL/2)/CELL = %.17g' % fcol, flush=True)
print('j_below=floor= %d (zc_mid=%.17g)  j_above=ceil= %d (zc_mid=%.17g)'
      % (j_below, zc_mid[j_below], j_above, zc_mid[j_above]), flush=True)
print('residual HSUB-zc_mid[j_below] = %.17g ; HSUB-zc_mid[j_above] = %.17g'
      % (HSUB - zc_mid[j_below], HSUB - zc_mid[j_above]), flush=True)
hit = np.flatnonzero(np.isclose(zn_node, HSUB, rtol=0.0, atol=1e-15))
k_iface = int(hit[0]) if hit.size else -1
print('exact index where zn_node==HSUB: %d ; residual zn_node[k]-HSUB = %.17g'
      % (k_iface, (zn_node[k_iface]-HSUB) if k_iface >= 0 else float('nan')), flush=True)

print('\n=== (d) transverse lattice ===', flush=True)
print('yn_node[:2] =', repr(yn_node[:2]), flush=True)
print('yn_node[-1] = %.17g' % yn_node[-1], flush=True)
print('Y0 = %.17g  Y1 = %.17g' % (Y0, Y1), flush=True)
fy0 = Y0/CELL; fy1 = Y1/CELL
print('fractional row index of Y0 in yn_node = %.17g ; of Y1 = %.17g' % (fy0, fy1), flush=True)
print('fractional row index of Y0 in yc_mid  = %.17g ; of Y1 = %.17g'
      % ((Y0-CELL/2)/CELL, (Y1-CELL/2)/CELL), flush=True)

print('\n=== (e) strip footprint rows on A_ez axis 0 (yn_node) ===', flush=True)
inside = np.flatnonzero((yn_node > Y0) & (yn_node < Y1))
outside = np.flatnonzero((yn_node <= Y0) | (yn_node >= Y1))
print('inside  count=%d first=%d last=%d  (yn_node first=%.10g last=%.10g)'
      % (inside.size, inside[0], inside[-1], yn_node[inside[0]], yn_node[inside[-1]]), flush=True)
print('outside count=%d  extents: below=[0..%d] above=[%d..%d]'
      % (outside.size,
         int(np.max(np.flatnonzero(yn_node <= Y0))),
         int(np.min(np.flatnonzero(yn_node >= Y1))), int(outside[-1])), flush=True)
ins_mask = np.zeros(NYN, dtype=bool); ins_mask[inside] = True
out_mask = np.zeros(NYN, dtype=bool); out_mask[outside] = True

print('\n=== (f) A_ez sign structure across interface cols %d/%d ===' % (j_below, j_above), flush=True)
lo = A_ez[:, j_below]; hi = A_ez[:, j_above]
nz_both = (lo != 0) & (hi != 0)
opp = nz_both & (np.sign(lo) != np.sign(hi))
same = nz_both & (np.sign(lo) == np.sign(hi))
print('rows with BOTH nonzero: %d' % int(nz_both.sum()), flush=True)
print('OPPOSITE nonzero sign: total=%d  inside=%d  outside=%d'
      % (int(opp.sum()), int((opp & ins_mask).sum()), int((opp & out_mask).sum())), flush=True)
print('SAME nonzero sign:     total=%d  inside=%d  outside=%d'
      % (int(same.sum()), int((same & ins_mask).sum()), int((same & out_mask).sum())), flush=True)
ex_in = inside[np.flatnonzero(opp[inside])[:3]] if np.any(opp[inside]) else inside[:3]
ex_out = outside[np.flatnonzero(opp[outside])[:3]] if np.any(opp[outside]) else outside[:3]
for tag, rows in (('inside', ex_in), ('outside', ex_out)):
    for r in rows:
        print('  example %-7s row=%d  A_ez[%d,%d]=%.17g  A_ez[%d,%d]=%.17g'
              % (tag, r, r, j_below, A_ez[r, j_below], r, j_above, A_ez[r, j_above]), flush=True)

print('\n=== (g) A_ey sign structure across interface node %d ===' % k_iface, flush=True)
if k_iface <= 0 or k_iface >= A_ey.shape[1] - 1:
    print('cannot test (k_iface=%d out of usable range)' % k_iface, flush=True)
else:
    kl = k_iface - 1; kr = k_iface + 1
    lo_e = A_ey[:, kl]; hi_e = A_ey[:, kr]
    nzc = (lo_e != 0) & (hi_e != 0)
    opp_e = nzc & (np.sign(lo_e) != np.sign(hi_e))
    same_e = nzc & (np.sign(lo_e) == np.sign(hi_e))
    print('using cols %d and %d around node %d (rows of A_ey = yc_mid, count %d)'
          % (kl, kr, k_iface, A_ey.shape[0]), flush=True)
    print('both-nonzero rows: %d' % int(nzc.sum()), flush=True)
    print('OPPOSITE: total=%d inside=%d outside=%d'
          % (int(opp_e.sum()), int(opp_e[inside].sum()), int(opp_e[outside].sum())), flush=True)
    print('SAME:     total=%d inside=%d outside=%d'
          % (int(same_e.sum()), int(same_e[inside].sum()), int(same_e[outside].sum())), flush=True)

print('\n=== (h) ratio A_ez[:,%d]/A_ez[:,%d] ===' % (j_above, j_below), flush=True)
with np.errstate(divide='ignore', invalid='ignore'):
    ratio = hi / lo
    good = np.isfinite(ratio) & (lo != 0)
for tag, m in (('INSIDE', ins_mask), ('OUTSIDE', out_mask)):
    sel = ratio[m & good]
    neg = int(np.sum(sel < 0))
    print('%-7s n=%d  min=%.17g  median=%.17g  max=%.17g  negative_ratios=%d'
          % (tag, sel.size, float(np.min(sel)), float(np.median(sel)), float(np.max(sel)), neg), flush=True)
print('ALL DONE', flush=True)
