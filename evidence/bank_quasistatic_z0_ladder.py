#!/usr/bin/env python3
"""Bank the quasi-static microstrip ``Z0`` ladder as machine-readable JSON.

One invocation = one strip width = one JSON file.  The ladder is the library's
own quasi-static cross-section solve at four transverse resolutions
``n_clean = n_air = n`` for ``n`` in 100 / 200 / 400 / 800, with everything else
held fixed.  This script *measures* and then writes; no number in the emitted
JSON is transcribed from prose.

The geometry is built by the same two private helpers the production call site
uses -- ``emfit.mode_profile._section`` (:447, the mesh, the cell size and the
strip width in cells) and ``emfit.mode_profile._conductors`` (:473, ground row
at 0 V / strip row at 1 V) -- so the ladder cannot drift from the solver's own
contract.  The solve itself is ``emfit.quasistatic.z0_eps_eff`` (:334):
``eps_eff = C'/C'_air`` and ``Z0 = sqrt(eps_eff) / (C0 C')``.

``n_strip`` is NOT a parameter of the solve: ``_section`` derives it as
``round(w / cell)`` and raises if ``w`` is not a whole number of cells.  It is
reported, not passed.

Usage::

    python evidence/bank_quasistatic_z0_ladder.py --w 3.0e-3 --tag w3.0mm
    python evidence/bank_quasistatic_z0_ladder.py --w 3.2e-3 --tag w3.2mm

Writes ``<out-dir>/quasistatic_z0_ladder_<tag>.json``.  Nothing else is
written: no ``.npy``, no cache, no scratch dump.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from emfit.microstrip import z0_eps_eff as closed_form_z0_eps_eff  # noqa: E402
from emfit.mode_profile import _conductors, _section  # noqa: E402
from emfit.quasistatic import z0_eps_eff as solve_z0_eps_eff  # noqa: E402

SCHEMA = "emfit.quasistatic.z0_ladder/1"

H_M = 1.6e-3
N_SUB = 16
EPS_R = 4.4
T_M = 35e-6              # strip thickness used by the closed form (t/h = 0.021875)
RUNGS = (100, 200, 400, 800)


def _git_state() -> dict:
    """HEAD sha and dirty flag, degrading gracefully if git is absent."""
    unavailable = "unavailable (git not installed in workspace container)"
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=20,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=20,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return {"git_rev": unavailable, "git_dirty": unavailable, "git_dirty_files": unavailable}
    if head.returncode != 0:
        return {
            "git_rev": f"unavailable ({head.stderr.strip()[:120] or 'rev-parse failed'})",
            "git_dirty": unavailable,
            "git_dirty_files": unavailable,
        }
    lines = [ln for ln in status.stdout.splitlines() if ln.strip()]
    return {"git_rev": head.stdout.strip(), "git_dirty": bool(lines), "git_dirty_files": len(lines)}


def _law(n, z0_inf, a, p):
    return z0_inf + a / np.power(n, p)


def _fit(ns, ys):
    """Fit ``y = y_inf + a / n**p``; returns (popt, pcov, residuals)."""
    ns = np.asarray(ns, dtype=float)
    ys = np.asarray(ys, dtype=float)
    popt, pcov = curve_fit(_law, ns, ys, p0=[float(ys[-1]), 1.0, 2.0], maxfev=200000)
    return popt, pcov, ys - _law(ns, *popt)


def _richardson(coarse: float, fine: float, p: float) -> float:
    """``R_p = (2**p * y_fine - y_coarse) / (2**p - 1)`` on one doubling."""
    r = 2.0 ** p
    return (r * fine - coarse) / (r - 1.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--w", type=float, required=True, help="strip width [m]")
    ap.add_argument("--tag", required=True, help="short label used in the filename")
    ap.add_argument("--out-dir", default=str(REPO_ROOT / "evidence"))
    ap.add_argument("--role", default="", help="free-text role of this width")
    args = ap.parse_args()

    substrate = lambda x, y, z: np.where(z < H_M, EPS_R, 1.0)  # noqa: E731

    rungs = []
    t_start = time.perf_counter()
    for n in RUNGS:
        t0 = time.perf_counter()
        grid, cell, n_strip = _section(H_M, args.w, N_SUB, n, n)
        fixed = _conductors(grid, n, n_strip, N_SUB)
        z0, eps_eff = solve_z0_eps_eff(grid, substrate, fixed)
        wall = time.perf_counter() - t0
        ny, nz = int(grid.shape[1]), int(grid.shape[2])
        rungs.append({
            "n": int(n),
            "n_clean": int(n),
            "n_air": int(n),
            "cells_ny": ny,
            "cells_nz": nz,
            "z0_ohm": float(z0),
            "eps_eff": float(eps_eff),
            "wall_seconds": round(float(wall), 4),
        })
        print(f"  n={n:<4d} {ny}x{nz:<5d} Z0={z0:.6f} eps_eff={eps_eff:.6f} {wall:8.2f} s",
              flush=True)
    total_wall = time.perf_counter() - t_start

    ns = [r["n"] for r in rungs]
    zs = [r["z0_ohm"] for r in rungs]
    es = [r["eps_eff"] for r in rungs]

    (z0_inf, a_z, p_z), pcov_z, resid_z = _fit(ns, zs)
    (e_inf, a_e, p_e), pcov_e, resid_e = _fit(ns, es)

    # --- cross-checks ---------------------------------------------------
    three_pt, _, _ = _fit(ns[:3], zs[:3])
    pred_fine = float(_law(ns[3], *three_pt))
    rel_three = (pred_fine - zs[3]) / zs[3]

    triple_lo, _, _ = _fit(ns[:3], zs[:3])
    triple_hi, _, _ = _fit(ns[1:], zs[1:])

    rich_p1 = _richardson(zs[2], zs[3], 1.0)
    rich_p2 = _richardson(zs[2], zs[3], 2.0)

    three_pt_e, _, _ = _fit(ns[:3], es[:3])
    pred_fine_e = float(_law(ns[3], *three_pt_e))

    cf_z0, cf_eps = closed_form_z0_eps_eff(args.w / H_M, EPS_R, T_M / H_M)

    geometry = {
        "w_m": float(args.w),
        "h_m": H_M,
        "cell_m": float(H_M / N_SUB),
        "n_sub": N_SUB,
        "n_strip": int(_section(H_M, args.w, N_SUB, RUNGS[0], RUNGS[0])[2]),
        "n_strip_rule": "derived by emfit.mode_profile._section as round(w / cell); not a parameter of the solve",
        "eps_r": EPS_R,
        "n_clean_rule": "n_clean = n_air = n (both homogeneous media meshed at the same resolution)",
        "n_air_rule": "n_clean = n_air = n (both homogeneous media meshed at the same resolution)",
        "transverse_box_m": {
            "y_width_at_finest_rung_m": rungs[-1]["cells_ny"] * float(H_M / N_SUB),
            "z_height_at_finest_rung_m": rungs[-1]["cells_nz"] * float(H_M / N_SUB),
            "note": "the lateral Neumann walls sit n_clean cells each side of the strip, the top wall n_air cells above it; the thin direction is one periodic cell",
        },
    }

    medium = {"n_clean_by_rung": {r["n"]: r["n_clean"] for r in rungs},
              "n_air_by_rung": {r["n"]: r["n_air"] for r in rungs},
              "substrate": "eps_r = 4.4 below z = h, vacuum above",
              "reference_solve": "C'_air is solved with eps_r = 1 everywhere by emfit.quasistatic.z0_eps_eff"}

    payload = {
        "schema": SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **_git_state(),
        "solver": {
            "entry_point": "emfit.quasistatic.z0_eps_eff(grid, substrate, fixed)",
            "geometry_built_by": "emfit.mode_profile._section / _conductors (the production call site's own helpers)",
            "method": "finite-difference potential solve on the transverse plane; eps_eff = C'/C'_air, Z0 = sqrt(eps_eff)/(C0*C')",
            "note": "solver-only artefact: no measurement, no port residual, no comparison against any FDTD run is recorded here",
        },
        "role": args.role,
        "geometry": geometry,
        "medium": medium,
        "rungs": rungs,
        "refit": {
            "model": "Z0(n) = Z0_inf + a / n**p",
            "method": "scipy.optimize.curve_fit, p0 = [Z0(finest), 1.0, 2.0], maxfev = 200000",
            "z0_inf_ohm": float(z0_inf),
            "z0_a": float(a_z),
            "z0_p": float(p_z),
            "z0_residuals_ohm": [float(r) for r in resid_z],
            "z0_covariance": [[float(v) for v in row] for row in np.atleast_2d(pcov_z)],
            "eps_eff_inf": float(e_inf),
            "eps_eff_a": float(a_e),
            "eps_eff_p": float(p_e),
            "eps_eff_residuals": [float(r) for r in resid_e],
            "eps_eff_covariance": [[float(v) for v in row] for row in np.atleast_2d(pcov_e)],
            "covariance_is_an_error_bar": False,
            "covariance_note": "the covariance curve_fit returns on a 4-point 3-parameter fit is an over-fitting number, not an uncertainty; it is recorded for completeness and MUST NOT be quoted as an error bar on the limit",
        },
        "cross_checks": {
            "method": "all computed from the rungs measured above, in this same process",
            "three_point_predicts_finest": {
                "method": "fit the three coarsest rungs, evaluate the model at the finest n",
                "fit_z0_inf_ohm": float(three_pt[0]),
                "fit_a": float(three_pt[1]),
                "fit_p": float(three_pt[2]),
                "predicted_z0_ohm": pred_fine,
                "actual_z0_ohm": float(zs[3]),
                "relative_difference": float(rel_three),
                "predicted_eps_eff": pred_fine_e,
                "actual_eps_eff": float(es[3]),
                "relative_difference_eps": float((pred_fine_e - es[3]) / es[3]),
            },
            "pairwise_triples": {
                "method": "fit rungs (100,200,400) and (200,400,800) separately",
                "lower_triple_z0_inf_ohm": float(triple_lo[0]),
                "upper_triple_z0_inf_ohm": float(triple_hi[0]),
                "spread_ohm": float(abs(triple_hi[0] - triple_lo[0])),
            },
            "richardson": {
                "method": "R_p = (2**p * y(finest) - y(second finest)) / (2**p - 1) on the single doubling 400 -> 800",
                "p1_z0_ohm": float(rich_p1),
                "p2_z0_ohm": float(rich_p2),
            },
            "per_doubling_drift": {
                "z0_relative": [float((zs[i + 1] - zs[i]) / zs[i]) for i in range(len(zs) - 1)],
                "eps_eff_relative": [float((es[i + 1] - es[i]) / es[i]) for i in range(len(es) - 1)],
            },
        },
        "closed_form": {
            "model": "emfit.microstrip.z0_eps_eff (Hammerstad-Jensen) at this run's w/h",
            "w_over_h": float(args.w / H_M),
            "t_over_h": float(T_M / H_M),
            "t_m": T_M,
            "z0_ohm": float(cf_z0),
            "eps_eff": float(cf_eps),
            "fitted_z0_inf_ohm": float(z0_inf),
            "relative_difference_fit_minus_closed_form": float((z0_inf - cf_z0) / cf_z0),
            "eps_eff_fit_minus_closed_form": float((e_inf - cf_eps) / cf_eps),
        },
        "wall_seconds": {
            "per_rung": [r["wall_seconds"] for r in rungs],
            "total_solver": round(float(total_wall), 3),
        },
        "notes": args.role or "see role",
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"quasistatic_z0_ladder_{args.tag}.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"  Z0_inf = {z0_inf:.6f} ohm  (a {a_z:.4f}, p {p_z:.6f})")
    print(f"  eps_eff_inf = {e_inf:.6f}  (a {a_e:.4f}, p {p_e:.6f})")
    print(f"  closed form @ w = {args.w:g} m: Z0 = {cf_z0:.4f} ohm, eps_eff = {cf_eps:.6f}")
    print(f"  wrote {out_path}  ({total_wall:.1f} s solver)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
