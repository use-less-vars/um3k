"""STEP (b): lateral-box sweep of the mode2d Z0 estimator at the low-frequency limit.

Fixed: cell 0.4 mm, lz = 4 mm, f = 1e8 Hz.  Swept: ly = 8 / 16 / 32 mm.
Writes one line per point to ``artifacts/box_sweep_z0.txt`` as soon as it is
computed (so a timeout cannot lose finished points) and prints unbuffered.
"""
from __future__ import annotations

import time

import numpy as np

from emfit import mode2d

C0 = 299792458.0
TOL = 1e-12
W, H, EPS_R = 3.2e-3, 1.6e-3, 4.4
CELL = 0.4e-3
LZ = 4e-3
F = 1e8
OUT = "artifacts/box_sweep_z0.txt"


def run(ly: float) -> dict:
    nyc, nzc = int(round(ly / CELL)), int(round(LZ / CELL))
    mesh = mode2d.box_mesh(ly, LZ, nyc, nzc)
    y0, y1 = ly / 2.0 - W / 2.0, ly / 2.0 + W / 2.0
    eps = lambda p: np.where(p[:, 1] <= H + TOL, EPS_R, 1.0)        # noqa: E731
    ground = lambda p: p[:, 1] <= TOL                              # noqa: E731
    strip = lambda p: ((np.abs(p[:, 1] - H) <= TOL)                # noqa: E731
                       & (p[:, 0] >= y0 - TOL) & (p[:, 0] <= y1 + TOL))
    k0 = 2.0 * np.pi * F / C0
    t = time.time()
    z0, beta, eps_eff, conv = mode2d.mode_z0_from_power(
        mesh, k0, eps_r=eps, boundaries=(ground, strip)
    )
    dt = time.time() - t
    return dict(ly_mm=ly * 1e3, nyc=nyc, nzc=nzc, nodes=mesh.n_nodes,
                edges=mesh.n_edges, z0=float(z0), beta=float(beta),
                eps_eff=float(eps_eff), converged=bool(conv), seconds=dt)


HEADER = ("| ly [mm] | cells | nodes | edges | Z0 [ohm] | beta [rad/m] "
          "| eps_eff | converged | wall [s] |")

with open(OUT, "w") as fh:
    fh.write(HEADER + "\n")
    fh.write("|---:|---|---:|---:|---:|---:|---:|---|---:|\n")
    fh.flush()
    print(HEADER, flush=True)
    for ly in (8e-3, 16e-3, 32e-3):
        try:
            r = run(ly)
        except Exception as exc:                                    # noqa: BLE001
            print(f"ly={ly*1e3:.0f} mm  FAILED: {type(exc).__name__}: {exc}",
                  flush=True)
            fh.write(f"| {ly*1e3:.0f} | - | - | - | FAILED: "
                     f"{type(exc).__name__}: {exc} | | | | |\n")
            fh.flush()
            continue
        line = (f"| {r['ly_mm']:.0f} | {r['nyc']}x{r['nzc']} | {r['nodes']} "
                f"| {r['edges']} | {r['z0']:.6f} | {r['beta']:.6f} "
                f"| {r['eps_eff']:.6f} | {r['converged']} | {r['seconds']:.1f} |")
        print(line, flush=True)
        fh.write(line + "\n")
        fh.flush()

print("DONE", flush=True)
