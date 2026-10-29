"""58.4 Phase B step 2 -- the widened transverse box, CASE B line, everything else identical.

Same harness sequence, same capture, same two-field split, same per-station
metrics as ``tools/modal_splitfix.py``; the only change is the transverse box:
PML moved out to a 3*H clearance on both the lateral walls and the top.

    lateral : N_CLEAN 3 -> 24   (24 cells = 4.8 mm = 3.000 H)
    top     : N_AIR   4 -> 26   (26 + 2 - 4 = 24 cells = 4.8 mm = 3.000 H)
    ny      : 18 -> 60,  nz : 14 -> 36

CELL, H, W, eps_r, the substrate band (z cells 0..7), the strip (z node 8),
n_acc = 2096, k = 8 and therefore dt / f0 / k0 / beta-bound are unchanged.
Same six station indices 40 / 46 / 52 / 58 / 64 / 70.
"""

from __future__ import annotations

import time

import numpy as np

from emfit.evolve import FITStepper, cfl_dt
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.modal_harness import (ModalStationCapture, build_mode_plane,
                                 split_forward_backward)
from emfit.operators import CellComplex
from emfit.pml import PML

C0 = 299792458.0
DB = 8.685889638065036

H = 1.6e-3
N_SUB = 8
CELL = H / N_SUB
EPS_R = 4.4
N_STRIP = 4
W = N_STRIP * CELL
N_CLEAN = 24          # was 3
N_AIR = 26            # was 4
N_TOP = 2
N_PML = 4
N_REF = 4
N_WARM = 600
K_BIN = 8
N_ACC = 2096

N_LINE = 96
STATIONS = (40, 46, 52, 58, 64, 70)
BOUND = 440.048305


def hdr(t):
    print("\n=== " + t + " " + "=" * max(0, 76 - len(t)), flush=True)


def fit_line(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    A = np.vstack([x, np.ones_like(x)]).T
    (slope, inter), *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - (slope * x + inter)
    rms = float(np.sqrt(np.mean(r ** 2)))
    return float(slope), float(inter), rms


def build():
    nx = N_PML + N_REF + N_LINE
    ny = 2 * N_PML + N_STRIP + 2 * N_CLEAN
    nz = N_SUB + N_AIR + N_TOP
    grid = Grid.uniform(nx, ny, nz, nx * CELL, ny * CELL, nz * CELL)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(
        grid, cc, eps_r=lambda x, y, z: np.where(z <= H, EPS_R, 1.0))

    ix_port = N_PML + N_REF
    k_strip = N_SUB
    j0 = N_PML + N_CLEAN
    j1 = j0 + N_STRIP

    pec = np.array(cc.pec_edge_mask(), dtype=bool)
    strip = np.zeros(cc.n_edges, dtype=bool)
    strip[cc.idx_ex(np.arange(ix_port, nx)[:, None],
                    np.arange(j0, j1 + 1)[None, :], k_strip)] = True
    strip[cc.idx_ey(np.arange(ix_port, nx + 1)[:, None],
                    np.arange(j0, j1)[None, :], k_strip)] = True
    pec |= strip

    pml = PML(grid, thickness_cells=N_PML, order=2, target=1e-4,
              walls=("xmin", "xmax", "ymin", "ymax", "zmax"), cc=cc)
    stepper = FITStepper(cc, m_eps, m_mu, dt=float(cfl_dt(grid)), pec=pec,
                         pml=pml)
    mode = build_mode_plane(cc, h=H, w=W, eps_r=EPS_R, n_sub=N_SUB,
                            k_strip=k_strip, iy_strip_centre=j0 + N_STRIP // 2,
                            n_clean=N_CLEAN, n_air=N_AIR)
    return (cc, stepper, mode, ix_port, k_strip, j0, j1, (nx, ny, nz), grid)


def main():
    cc, stepper, mode, ix_port, k_strip, j0, j1, mesh, grid = build()
    dt = float(stepper.dt)
    f0 = K_BIN / (N_ACC * dt)
    stations = np.asarray(STATIONS, dtype=int)
    nx, ny, nz = mesh
    cap = ModalStationCapture(cc, mode, stations, f0=f0, dt=dt, limit=N_ACC,
                              n_warm=N_WARM, destagger_h=False)
    port_edges = np.unique(np.concatenate(
        [cc.idx_ez(np.array([ix_port]), np.array([j]),
                   np.arange(0, k_strip)).ravel() for j in range(j0, j1 + 1)]))

    def drive(n):
        cur = np.zeros(cc.n_edges, dtype=float)
        cur[port_edges] = min(1.0, (n + 1) / N_WARM) * np.sin(
            2.0 * np.pi * f0 * n * dt)
        return cur

    t0 = time.perf_counter()
    res = cap.run(stepper, drive=drive)
    wall = time.perf_counter() - t0

    lat = j0 - N_PML
    top = nz - N_PML - k_strip
    hdr("widened box")
    print(f"  box (nx, ny, nz) = {mesh};  nx cells {nx}, ny {ny}, nz {nz}")
    print(f"  strip y-edge -> lateral PML : {lat} cells = "
          f"{lat*CELL*1e3:.4f} mm = {lat*CELL/H:.4f} H  (N_CLEAN {N_CLEAN})")
    print(f"  strip top   -> zmax PML     : {top} cells = "
          f"{top*CELL*1e3:.4f} mm = {top*CELL/H:.4f} H  (N_AIR {N_AIR}, "
          f"N_TOP {N_TOP})")
    print(f"  n_acc {N_ACC}, k {K_BIN}, dt {dt!r} s, f0 {f0!r} Hz")
    print(f"  wall-clock FDTD {wall:.2f} s")

    st = stations
    x = (st - st[0]) * CELL
    k0 = 2.0 * np.pi * f0 / C0
    th = np.pi * f0 * dt

    ae = np.array([res["a_e"][int(i)] for i in st])
    ah_raw = np.array([res["a_h"][int(i)] for i in st])
    ah_p = ah_raw * np.exp(+1j * th)
    v = np.array([res["amplitudes"][int(i)] for i in st])

    v_mode = float(mode.v_mode)
    i_mode = float(mode.i_mode)
    z0 = float(mode.z0_power)

    hdr("per station")
    print("   ix   x_mm      |a_e|        |a_h|      |a_e/a_h|  arg(a_e/a_h) deg")
    for i in range(st.size):
        r = ae[i] / ah_p[i]
        print(f"  {st[i]:3d} {x[i]*1e3:7.3f} {abs(ae[i]):12.5e} "
              f"{abs(ah_p[i]):12.5e} {abs(r):10.5f} "
              f"{np.degrees(np.angle(r)):+10.4f}")
    rr = np.abs(ae / ah_p)
    pp = np.degrees(np.angle(ae / ah_p))

    af = (ae * v_mode + z0 * ah_p * i_mode) / (2.0 * v_mode)
    ab = (ae * v_mode - z0 * ah_p * i_mode) / (2.0 * v_mode)

    hdr("alpha from a_f")
    sl, ic, rms = fit_line(x, np.log(np.abs(af)))
    alpha = -sl
    print(f"  alpha = {alpha:+11.5f} /m = {alpha*1e-3*DB:+9.5f} dB/mm "
          f"(LS on log|a_f| over {x[-1]*1e3:.3f} mm)")
    print(f"  log-amp residual rms = {rms:.6e} in ln|a_f|")
    print("  per-interval dB (adjacent stations):")
    for i in range(st.size - 1):
        dd = float(x[i + 1] - x[i])
        a_i = -np.log(abs(af[i + 1]) / abs(af[i])) / dd
        print(f"    {st[i]:3d}->{st[i+1]:3d}  d {dd*1e3:.3f} mm  "
              f"alpha {a_i:+11.4f} /m  {a_i*1e-3*DB:+9.5f} dB/mm")

    hdr("beta from a_f")
    ph = np.unwrap(np.angle(af))
    besl, _, brms = fit_line(x, ph)
    beta = -besl
    print(f"  beta = {beta:.6f} /m  (phase residual rms "
          f"{np.degrees(brms):.5f} deg)")
    print(f"  eps_eff = {(beta/k0)**2:.6f}")
    print(f"  k0 = {k0:.6f} /m ;  k0*sqrt(eps_max) = {BOUND:.6f} /m ;  "
          f"beta/bound = {beta/BOUND:.6f}  ({100.0*(beta/BOUND-1.0):+.4f} %)")
    print(f"  |a_b|/|a_f| max = {np.max(np.abs(ab)/np.abs(af)):.5f}")

    hdr("old CASE B (18 x 14 box) for comparison")
    print("  alpha +118.824 /m ;  a_e/a_h spread 2.6215e-02 mag / 1.899 deg ;  "
          "beta 472.790 /m ;  beta/bound 1.0744")
    print(f"  this run: alpha {alpha:+.3f} /m ;  spread "
          f"{rr.max()/rr.min()-1:+.4e} mag / {pp.max()-pp.min():.4f} deg ;  "
          f"beta {beta:.3f} /m ;  beta/bound {beta/BOUND:.4f}")
    print(f"\n  total wall {time.perf_counter()-t0:.2f} s (FDTD {wall:.2f} s)",
          flush=True)


if __name__ == "__main__":
    main()
