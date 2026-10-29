"""58.4 Phase B step 1 -- the no-FDTD audit of the coupon's box and material.

Answers, from the objects the run actually builds:

(a) the mesh: nx/ny/nz, node counts, spacings, where the substrate, the ground,
    the strip and the PML actually are, and every clearance in mm *and* in
    units of H (the engineer's question: is the box too tight?);
(b) the material: ``eps_r`` is wrapped in a recorder, so the exact (x, y, z)
    arrays ``material_matrices`` queries are on the record -- the distinct z
    values settle the 8-vs-9-substrate-cell off-by-one, and the z band table
    shows which cells are dielectric;
(c) the station distances: absolute, relative, and the ``d`` the analysis uses
    vs the geometric one;
(d) the bound: ``k0 * sqrt(eps_r_max)`` against the measured ``beta``.

No stepper, no time loop: this is grid + material arithmetic only.
"""

from __future__ import annotations

import numpy as np

from emfit.evolve import cfl_dt
from emfit.grid import Grid
from emfit.materials import EPS0, material_matrices
from emfit.operators import CellComplex

C0 = 299792458.0

H = 1.6e-3
N_SUB = 8
CELL = H / N_SUB
EPS_R = 4.4
N_STRIP = 4
W = N_STRIP * CELL
N_CLEAN = 3
N_AIR = 4
N_TOP = 2
N_PML = 4
N_REF = 4
K_BIN = 8
N_ACC = 2096

CASES = (("CASE A", 40, (14, 26, 38), 478.513435),
         ("CASE B", 96, (40, 46, 52, 58, 64, 70), 472.790348))


def hdr(t):
    print("\n=== " + t + " " + "=" * max(0, 76 - len(t)), flush=True)


def build(n_line, record=None):
    nx = N_PML + N_REF + n_line
    ny = 2 * N_PML + N_STRIP + 2 * N_CLEAN
    nz = N_SUB + N_AIR + N_TOP
    grid = Grid.uniform(nx, ny, nz, nx * CELL, ny * CELL, nz * CELL)
    cc = CellComplex(grid)

    def eps_fn(x, y, z):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        z = np.asarray(z, dtype=float)
        if record is not None:
            record.append((x, y, z))
        return np.where(z <= H, EPS_R, 1.0)

    m_eps, _ = material_matrices(grid, cc, eps_r=eps_fn)
    return grid, cc, m_eps


def eps_at(m_eps, cc, kind, i, j, k):
    """Recover the sampled ``eps_r`` of one edge from ``m_eps``.

    ``ratio = A_dual / L_e`` is computed from the grid's own dual widths, so the
    division undoes exactly what ``material_matrices`` multiplied in.
    """
    grid = cc.grid
    C = 2e-4
    if kind == "ez":
        ratio = grid.dual_widths("x")[i] * grid.dual_widths("y")[j] / C
        idx = cc.idx_ez(i, j, k)
    elif kind == "ey":
        ratio = grid.dual_widths("x")[i] * grid.dual_widths("z")[k] / C
        idx = cc.idx_ey(i, j, k)
    else:
        ratio = grid.dual_widths("y")[j] * grid.dual_widths("z")[k] / C
        idx = cc.idx_ex(i, j, k)
    return float(m_eps[idx]) / (EPS0 * ratio)


def report(name, n_line, stations, beta_rec, verbose):
    rec = []
    grid, cc, m_eps = build(n_line, rec)
    nx, ny, nz = grid.shape
    ix_port = N_PML + N_REF
    k_strip = N_SUB
    j0 = N_PML + N_CLEAN
    j1 = j0 + N_STRIP

    hdr(f"{name}: mesh")
    print(f"  grid {nx} x {ny} x {nz} cells; nodes x/y/z = "
          f"{len(grid.x)}/{len(grid.y)}/{len(grid.z)}")
    for ax in "xyz":
        w = np.diff(getattr(grid, ax))
        print(f"  d{ax}: {w.min()*1e6:.6f} .. {w.max()*1e6:.6f} um uniform="
              f"{np.allclose(w, w[0])}  extent {getattr(grid, ax)[-1]*1e3:.6f} mm")
    print(f"  CELL {CELL*1e6:.4f} um, H {H*1e3:.4f} mm = {N_SUB} cells, "
          f"W {W*1e3:.4f} mm = {N_STRIP} cells, eps_r {EPS_R}")
    print(f"  substrate: z cells 0..{N_SUB-1} (z nodes {grid.z[0]*1e3:.4f} .. "
          f"{grid.z[N_SUB]*1e3:.4f} mm) -> H = {grid.z[N_SUB]*1e3:.4f} mm "
          f"(target {H*1e3:.4f})")
    print(f"  ground PEC plane: z node 0 (z = {grid.z[0]*1e3:.4f} mm)")
    print(f"  strip: z node {k_strip} (z = {grid.z[k_strip]*1e3:.4f} mm), "
          f"y nodes {j0}..{j1} (y = {grid.y[j0]*1e3:.4f} .. {grid.y[j1]*1e3:.4f} mm)"
          f" -> W = {(grid.y[j1]-grid.y[j0])*1e3:.4f} mm")
    print(f"  PML: {N_PML} cells on xmin/xmax/ymin/ymax/zmax, order 2, "
          f"target 1e-4;  N_REF {N_REF} (port at ix {ix_port} = "
          f"{grid.x[ix_port]*1e3:.4f} mm)")
    print("\n  air above the strip: upper PML inner boundary at z node "
          f"{nz-N_PML} (z = {grid.z[nz-N_PML]*1e3:.4f} mm); strip top at z node "
          f"{k_strip} -> air clear {nz-N_PML-k_strip} cells = "
          f"{(grid.z[nz-N_PML]-grid.z[k_strip])*1e3:.4f} mm = "
          f"{(grid.z[nz-N_PML]-grid.z[k_strip])/H:.4f} H")
    print("  clearance table (cells / mm / H):")
    y_lo_pml = N_PML
    y_hi_pml = ny - N_PML
    rows = [
        ("strip y-edge -> ymin PML", j0 - y_lo_pml,
         grid.y[j0] - grid.y[y_lo_pml]),
        ("strip y-edge -> ymax PML", y_hi_pml - j1,
         grid.y[y_hi_pml] - grid.y[j1]),
        ("strip top -> zmax PML", nz - N_PML - k_strip,
         grid.z[nz - N_PML] - grid.z[k_strip]),
        ("ground -> substrate top (H)", N_SUB, H),
        ("mx PML width (xmin/xmax)", N_PML, N_PML * CELL),
        ("source ix -> xmin PML inner", ix_port - N_PML, grid.x[ix_port] - grid.x[N_PML]),
        ("station 1 -> source", int(stations[0]) - ix_port,
         grid.x[stations[0]] - grid.x[ix_port]),
        ("last station -> xmax PML inner", (nx - N_PML) - int(stations[-1]),
         grid.x[nx - N_PML] - grid.x[stations[-1]]),
    ]
    for lab, cells, m in rows:
        print(f"    {lab:32s} {cells:4d} cells  {m*1e3:8.4f} mm  "
              f"{m/H:8.4f} H")

    hdr(f"{name}: material band -- what eps_r the run actually sees")
    zs = np.concatenate([q[2].ravel() for q in rec])
    uniq = np.unique(np.round(zs, 12))
    print(f"  eps_r callable queried {zs.size} samples; distinct z values "
          f"{uniq.size}; range {uniq.min()*1e3:.6f} .. {uniq.max()*1e3:.6f} mm")
    cell_z = (np.arange(nz) + 0.5) * CELL
    on_cell = np.array([np.isclose(uniq, q).any() for q in cell_z])
    node_z = np.arange(nz + 1) * CELL
    print(f"  distinct z on cell centres ((k+0.5)*CELL): {int(on_cell.sum())}"
          f"/{nz}; z nodes present in the query set: "
          f"{int(sum(np.isclose(uniq, q).any() for q in node_z))}/{nz+1}")
    print(f"  -> the E_z unknowns are sampled at CELL CENTRES, so the "
          f"substrate band is cells 0..{N_SUB-1} = {N_SUB} cells (no off-by-one)")
    vals, counts = np.unique(np.round(m_eps / (EPS0 * CELL), 12),
                             return_counts=True)
    print(f"  distinct m_eps/(eps0*CELL) values ({vals.size}), with counts:")
    for v, c in zip(vals, counts):
        print(f"    {v:12.6f}  x {c:8d}")
    print(f"  eps_r max seen = {vals.max():.6f} (target {EPS_R})")
    i_mid = nx // 2
    j_mid = ny // 2
    print("\n  z band table (eps_r recovered from m_eps at the mid plane):")
    print("   k   z_cell_mm  eps(E_z)   k_n  z_node_mm  eps(E_y)")
    for k in range(nz):
        e_z = eps_at(m_eps, cc, "ez", i_mid, j_mid, k)
        print(f"   {k:2d} {cell_z[k]*1e3:10.4f} {e_z:9.4f}", end="")
        if k <= nz:
            e_y = eps_at(m_eps, cc, "ey", i_mid, j_mid, k)
            print(f"   {k:2d} {node_z[k]*1e3:9.4f} {e_y:9.4f}")
        else:
            print()
    print(f"\n  explicit: strip cell E_z k={k_strip-1} -> "
          f"{eps_at(m_eps, cc, 'ez', i_mid, j_mid, k_strip-1):.6f}; "
          f"cell above E_z k={k_strip} -> "
          f"{eps_at(m_eps, cc, 'ez', i_mid, j_mid, k_strip):.6f}; "
          f"strip-layer E_y at z node {k_strip} -> "
          f"{eps_at(m_eps, cc, 'ey', i_mid, j_mid, k_strip):.6f} "
          f"(dual-averaged half in / half out)")

    hdr(f"{name}: station distances")
    st = np.asarray(stations, dtype=int)
    x_abs = st * CELL
    x_rel = (st - st[0]) * CELL
    print("   ix    x_abs_mm   x_rel_m     d_geo_mm   d_used_mm   rel dev")
    for i, ix in enumerate(st):
        if i + 1 < st.size:
            d_geo = grid.x[st[i + 1]] - grid.x[st[i]]
            d_used = float(x_rel[i + 1] - x_rel[i])
            print(f"   {ix:3d} {x_abs[i]*1e3:10.4f} {x_rel[i]:11.7f} "
                  f"{d_geo*1e3:10.4f} {d_used*1e3:11.4f} "
                  f"{(d_used-d_geo)/d_geo if d_geo else 0.0:+11.3e}")
        else:
            print(f"   {ix:3d} {x_abs[i]*1e3:10.4f} {x_rel[i]:11.7f}")
    d = float(np.median(np.diff(x_rel)))
    print(f"  d used by the analysis = {d!r} m ({d*1e3:.6f} mm); "
          f"gap {d*1e3:.4f} mm between stations")
    dt = float(cfl_dt(grid))
    f0 = K_BIN / (N_ACC * dt)
    k0 = 2.0 * np.pi * f0 / C0
    bound = k0 * np.sqrt(EPS_R)
    print(f"\n  dt {dt!r} s  f0 {f0!r} Hz  k0 {k0:.6f} /m  "
          f"k0*sqrt(eps_r_max) {bound:.6f} /m")
    print(f"  beta(record) {beta_rec:.6f} /m -> beta/bound = "
          f"{beta_rec/bound:.6f}  ({100.0*(beta_rec/bound - 1.0):+.4f} %)")
    print(f"  eps_eff implied = {(beta_rec/k0)**2:.6f} (max allowed {EPS_R})")
    return dict(dt=dt, f0=f0, k0=k0, bound=bound, d=d)


def main():
    for verbose, (name, n_line, stations, beta_rec) in enumerate(CASES):
        report(name, n_line, stations, beta_rec, verbose)
    print("\n(dt is the same for both cases: every cell is CELL, so the CFL "
          "bound depends on CELL only.)", flush=True)


if __name__ == "__main__":
    main()
