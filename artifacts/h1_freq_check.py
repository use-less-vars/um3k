# -*- coding: utf-8 -*-
"""H1 frequency check: does mode_z0_from_power move between 1e8 Hz and 5.827786408 GHz?

Fixed geometry (ly = 16 mm, lz = 4 mm, 0.4 mm cells -> 40 x 10), w = 3.2 mm,
h = 1.6 mm, eps_r = 4.4, PEC (ground, strip) only.  Two frequencies, one box,
no other runs.  Writes artifacts/h1_freq_check.json after EACH frequency.

Re-run verbatim (from the repo root):  PYTHONPATH=/workspace python3 artifacts/h1_freq_check.py
"""
from __future__ import annotations

import json
import os
import resource
import time
import traceback

import numpy as np

from emfit import mode2d

C0 = 299792458.0
TOL = 1e-12

W = 3.2e-3
H = 1.6e-3
EPS_R = 4.4
CELL = 0.4e-3
LY, LZ = 16e-3, 4e-3
NYC, NZC = int(round(LY / CELL)), int(round(LZ / CELL))

FREQS = [
    ("control_1e8", 1e8),
    ("record_5p8277864083272855GHz", 5827786408.3272855),
]
EXPECTED_Z0_CONTROL = 49.731985         # ly = 16 mm, 1e8 Hz, already recorded
DELTA_Z0_ABS = 0.48                     # H1 bracket threshold [ohm]

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "h1_freq_check.json")


def _microstrip_ly16():
    """(mesh, eps_r, boundaries) -- tests/test_mode2d_z0.py::_microstrip at LY=16 mm."""
    mesh = mode2d.box_mesh(LY, LZ, NYC, NZC)
    y0, y1 = LY / 2.0 - W / 2.0, LY / 2.0 + W / 2.0
    eps = lambda p: np.where(p[:, 1] <= H + TOL, EPS_R, 1.0)          # noqa: E731
    ground = lambda p: p[:, 1] <= TOL                                # noqa: E731
    strip = lambda p: ((np.abs(p[:, 1] - H) <= TOL)                  # noqa: E731
                       & (p[:, 0] >= y0 - TOL) & (p[:, 0] <= y1 + TOL))
    return mesh, eps, (ground, strip)


def flush(doc):
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, OUT)


doc = {
    "what": "H1 frequency check -- mode_z0_from_power at two frequencies, one fixed box",
    "geometry": {
        "ly_m": LY, "lz_m": LZ, "cell_m": CELL, "nyc": NYC, "nzc": NZC,
        "w_m": W, "h_m": H, "eps_r": EPS_R,
        "boundaries": "PEC (ground, strip) exactly as tests/test_mode2d_z0.py::_microstrip, LY=16e-3",
        "mesh_call": "mode2d.box_mesh(16e-3, 4e-3, 40, 10)",
    },
    "call": "mode2d.mode_z0_from_power(mesh, k0, eps_r=eps, boundaries=bounds)  # sigma=1.0, k=8, guard=True",
    "c0": C0,
    "delta_z0_abs_threshold_ohm": DELTA_Z0_ABS,
    "expected_z0_control_ohm": EXPECTED_Z0_CONTROL,
    "runs": {},
}
doc["started_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
flush(doc)

mesh, eps, bounds = _microstrip_ly16()
n_nodes = int(mesh.n_nodes)
n_edges = int(mesh.edges.shape[0])
n_tris = int(getattr(mesh, "tris", getattr(mesh, "t", np.zeros((0, 3)))).shape[0]) \
    if hasattr(mesh, "tris") or hasattr(mesh, "t") else None
doc["geometry"]["n_nodes"] = n_nodes
doc["geometry"]["n_edges"] = n_edges
doc["geometry"]["n_tris"] = n_tris
doc["geometry"]["node_edge_assert_451_1250"] = (n_nodes == 451 and n_edges == 1250)
flush(doc)
print(f"[mesh] nodes={n_nodes} edges={n_edges} tris={n_tris} "
      f"assert_451_1250={n_nodes == 451 and n_edges == 1250}", flush=True)
if not (n_nodes == 451 and n_edges == 1250):
    doc["fatal"] = f"mesh is {n_nodes} nodes / {n_edges} edges, expected 451 / 1250 -- STOPPING"
    flush(doc)
    raise SystemExit(2)

for name, f in FREQS:
    k0 = 2.0 * np.pi * f / C0
    rec = {"f_hz": f, "k0_rad_per_m": k0}
    print(f"\n=== {name}: f = {f!r} Hz, k0 = {k0!r} rad/m ===", flush=True)
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t0 = time.time()
    try:
        out = mode2d.mode_z0_from_power(mesh, k0, eps_r=eps, boundaries=bounds)
    except BaseException as exc:                       # guard refusal lands here
        wall = time.time() - t0
        rec.update({
            "status": "RAISED",
            "exception_type": type(exc).__name__,
            "exception_str": str(exc),
            "traceback": traceback.format_exc(),
            "wall_s": wall,
        })
        doc["runs"][name] = rec
        flush(doc)
        print(f"[{name}] RAISED {type(exc).__name__}: {exc}", flush=True)
        print(f"[{name}] wall {wall:.2f} s -- STOPPING per stop rules (guard not relaxed)",
              flush=True)
        break
    wall = time.time() - t0
    rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    z0, beta, eps_eff, converged = out
    rec.update({
        "status": "OK",
        "returned_tuple_repr": repr(out),
        "returned_tuple_len": len(out),
        "returned_tuple_types": [type(v).__name__ for v in out],
        "z0_ohm": float(z0),
        "beta_rad_per_m": float(beta),
        "eps_eff": float(eps_eff),
        "converged": (converged if isinstance(converged, bool) else bool(converged)),
        "converged_raw_repr": repr(converged),
        "wall_s": wall,
        "peak_rss_kb": int(max(rss0, rss1)),
        "predicted_beta_selfconsistent_rad_per_m": float(np.sqrt(eps_eff) * k0),
        "predicted_beta_eps_eff_3p60_rad_per_m": float(np.sqrt(3.60) * k0),
        "expected_beta_from_record_231p5533_rad_per_m": 231.5533,
    })
    doc["runs"][name] = rec
    flush(doc)
    print(f"[{name}] Z0={z0!r} beta={beta!r} eps_eff={eps_eff!r} converged={converged!r}",
          flush=True)
    print(f"[{name}] Z0={float(z0):.6f} ohm  beta={float(beta):.6f} rad/m  "
          f"eps_eff={float(eps_eff):.6f}  wall={wall:.2f} s  peak_rss={max(rss0, rss1)/1024:.1f} MB",
          flush=True)

# ---- verdict arithmetic -------------------------------------------------
runs = doc["runs"]
if all(r.get("status") == "OK" for r in runs.values()) and len(runs) == 2:
    z_lo = runs["control_1e8"]["z0_ohm"]
    z_hi = runs["record_5p8277864083272855GHz"]["z0_ohm"]
    d = z_hi - z_lo
    doc["delta_z0"] = {
        "z0_control_1e8_ohm": z_lo,
        "z0_record_5p827786408GHz_ohm": z_hi,
        "delta_z0_ohm": d,
        "delta_z0_abs_ohm": abs(d),
        "delta_z0_pct_of_control": 100.0 * abs(d) / z_lo,
        "delta_over_threshold": abs(d) / DELTA_Z0_ABS,
        "control_reproduced_to_6dp": round(z_lo, 6) == round(EXPECTED_Z0_CONTROL, 6),
        "control_delta_vs_expected_ohm": z_lo - EXPECTED_Z0_CONTROL,
        "verdict": "H1 FIRES" if abs(d) >= DELTA_Z0_ABS else "H1 DOES NOT FIRE",
    }
    doc["mode_identity_5p827GHz"] = {
        "beta_expected_from_eps_eff_3p60": 231.6,
        "beta_returned": runs["record_5p8277864083272855GHz"]["beta_rad_per_m"],
        "beta_ratio_to_quasi_tem":
            runs["record_5p8277864083272855GHz"]["beta_rad_per_m"] / 231.6,
        "eps_eff_returned": runs["record_5p8277864083272855GHz"]["eps_eff"],
        "eps_eff_expected": 3.60,
    }
    flush(doc)
    print("\n=== VERDICT ===", flush=True)
    print(json.dumps(doc["delta_z0"], indent=2), flush=True)
    print(json.dumps(doc["mode_identity_5p827GHz"], indent=2), flush=True)
else:
    doc["verdict"] = "INCOMPLETE -- see runs"
    flush(doc)

doc["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
doc["peak_rss_kb_process"] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
flush(doc)
print(f"\n[json] {OUT} = {os.path.getsize(OUT)} bytes", flush=True)
