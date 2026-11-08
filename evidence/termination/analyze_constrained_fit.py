#!/usr/bin/env python3
"""A1: constrained two-wave fit of the measured station phasors.

The line model is fixed before any data is touched::

    e_minus(x) = exp(-1j * beta * x)
    e_plus(x)  = exp(+1j * beta * x)
    V(x)       = Vf * e_minus(x) + Vb * e_plus(x)
    I(x)       = (Vf * e_minus(x) - Vb * e_plus(x)) / Z0

``x`` is measured from the SMALLEST station x of the record, so the fit
returns the two wave amplitudes referred to the first station's plane and
``Gamma = Vb / Vf`` is the reflection on that plane.

For a fixed ``(Z0, beta)`` the fit is linear in ``[Vf, Vb]`` and is solved by
ordinary least squares on the stacked rows::

    [ V_k    ]   [ e_minus_k   e_plus_k ] [ Vf ]
    [ I_k*Z0 ] = [ e_minus_k  -e_plus_k ] [ Vb ]

with the residual taken over every station and both rows.  ``beta`` is found
by a grid search followed by local refinement; ``Z0`` is either given
(F1, F2, F4) or found on a 1-D grid nested in the beta search (F3, the
control that asks whether the free fit is degenerate over a short span).

Because the two design columns are orthonormal up to the factor ``2*N``
(``|e_minus| = |e_plus| = 1`` and the cross terms cancel between the V row
and the I row), the least-squares solution has a closed form::

    Vf = sum_k e_minus_k^* (V_k + Z0 I_k) / (2 N)
    Vb = sum_k e_plus_k^*  (V_k - Z0 I_k) / (2 N)

which is what :func:`solve_at` uses; :func:`cross_check` re-solves one case
with ``numpy.linalg.lstsq`` and prints the difference, so the shortcut cannot
drift from the fit it claims to be.

Pure numpy + stdlib.  Reads one JSON artefact and writes one JSON artefact;
runs no FDTD, imports nothing from the ``emfit`` package, writes nothing else.

Run from the repo root::

    python3 evidence/termination/analyze_constrained_fit.py
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    REPO_ROOT / "evidence" / "termination" / "build_A_50ohm_p50_plane.json")
DEFAULT_OUTPUT = (
    REPO_ROOT / "evidence" / "termination" / "constrained_fit_p51.json")

C_M_S = 299792458.0

# The two fixed reference impedances the earlier evidence quotes.
Z0_REAL = 47.305815
Z0_COMPLEX = complex(47.305815, 1.5582)

# Reported for comparison, not used by any fit: the port |S11| of the record
# (s11.magnitude_one_wave_station_fit and s11.magnitude of the artefact).
S11_PORT_TARGET = 0.326
# |Gamma| the earlier FREE fit is said to return; the F3 control.
GAMMA_FREE_REFERENCE = 0.245
# "close to" for the closing YES/NO lines: 0.02 on |Gamma|.
CLOSE_TOL = 0.02

# beta grid: wide enough to bracket every eps_eff in [1, 3] (122 .. 212 rad/m)
# and the value the artefact itself stores (232.8 rad/m).
BETA_LO, BETA_HI, BETA_COARSE = 20.0, 600.0, 1161
REFINE_ROUNDS, REFINE_POINTS = 4, 201

# F3's Z0 grid.
Z0_LO, Z0_HI, Z0_COARSE = 20.0, 120.0, 401

# F4: the stations nearest the load, by their node column (js).
F4_JS = (44, 47, 50)
F4_JS_WITH_41 = (41, 44, 47, 50)


# --------------------------------------------------------------------------
# artefact reading
# --------------------------------------------------------------------------
def load_record(path: Path) -> dict:
    """The nine station phasors, their x, and the record's own scalars."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    geometry = doc.get("geometry") or {}
    station = (doc.get("s11") or {}).get("station_phasors") or {}

    x = [float(v) for v in station["x_m"]]
    js = [int(v) for v in station["js"]]
    v = np.array([complex(re, im) for re, im in
                  zip(station["v_re"], station["v_im"])], dtype=complex)
    i = np.array([complex(re, im) for re, im in
                  zip(station["i_re"], station["i_im"])], dtype=complex)

    if not (len(x) == len(js) == v.size == i.size):
        raise ValueError(
            "the station phasor block is ragged: x_m=%d js=%d v=%d i=%d"
            % (len(x), len(js), v.size, i.size))

    order = np.argsort(np.asarray(x), kind="stable")
    return {
        "doc": doc,
        "f_hz": float(geometry["f_hz"]),
        "geometry_f_hz": float(geometry["f_hz"]),
        "cell_m": float(geometry.get("cell_m", float("nan"))),
        "x_m": np.asarray(x, dtype=float)[order],
        "js": [js[k] for k in order],
        "v": v[order],
        "i": i[order],
        "fit_selected": list(station.get("fit_selected") or []),
        "beta_used": float(station.get("beta_used", float("nan"))),
        "deembed_distance_m": station.get("deembed_distance_m"),
        "s11_magnitude": (doc.get("s11") or {}).get("magnitude"),
        "s11_magnitude_one_wave": (
            doc.get("s11") or {}).get("magnitude_one_wave_station_fit"),
        "s11_phase_deg": (doc.get("s11") or {}).get("phase_deg"),
        "line_beta": (doc.get("line") or {}).get("beta"),
        "geometry": geometry,
    }


# --------------------------------------------------------------------------
# the constrained fit
# --------------------------------------------------------------------------
def solve_at(v, i, x, z0, betas):
    """OLS in ``[Vf, Vb]`` at each beta for one fixed ``z0``.

    Returns ``(ssr, vf, vb)``, each of length ``len(betas)``.
    """
    b = np.asarray(betas, dtype=float).reshape(-1)
    e_minus = np.exp(-1j * np.outer(b, x))   # (B, N), forward
    e_plus = np.exp(+1j * np.outer(b, x))    # (B, N), backward
    n = float(x.size)
    z0 = complex(z0)

    vf = (np.conj(e_minus) @ (v + z0 * i)) / (2.0 * n)
    vb = (np.conj(e_plus) @ (v - z0 * i)) / (2.0 * n)

    row_v = v[None, :] - (vf[:, None] * e_minus + vb[:, None] * e_plus)
    row_i = (z0 * i)[None, :] - (vf[:, None] * e_minus - vb[:, None] * e_plus)
    ssr = np.sum(np.abs(row_v) ** 2 + np.abs(row_i) ** 2, axis=1)
    return ssr, vf, vb


def cross_check(v, i, x, z0, beta):
    """max |dVf| + |dVb| between the closed form and ``numpy.linalg.lstsq``."""
    ssr, vf, vb = solve_at(v, i, x, z0, [beta])
    e_minus = np.exp(-1j * beta * x)
    e_plus = np.exp(+1j * beta * x)
    design = np.zeros((2 * x.size, 2), dtype=complex)
    design[0::2, 0] = e_minus
    design[0::2, 1] = e_plus
    design[1::2, 0] = e_minus
    design[1::2, 1] = -e_plus
    rhs = np.zeros(2 * x.size, dtype=complex)
    rhs[0::2] = v
    rhs[1::2] = complex(z0) * i
    ref, *_ = np.linalg.lstsq(design, rhs, rcond=None)
    return float(max(abs(ref[0] - vf[0]), abs(ref[1] - vb[0]))), float(ssr[0])


def beta_search(v, i, x, z0):
    """Coarse beta grid, then REFINE_ROUNDS local grids.  Returns a fit."""
    betas = np.linspace(BETA_LO, BETA_HI, BETA_COARSE)
    ssr, _, _ = solve_at(v, i, x, z0, betas)
    k = int(np.argmin(ssr))
    edge = k in (0, BETA_COARSE - 1)
    best = float(betas[k])
    step = float(betas[1] - betas[0])
    for _ in range(REFINE_ROUNDS):
        grid = np.linspace(best - step, best + step, REFINE_POINTS)
        sub, _, _ = solve_at(v, i, x, z0, grid)
        best = float(grid[int(np.argmin(sub))])
        step = 2.0 * step / (REFINE_POINTS - 1)
    ssr, vf, vb = solve_at(v, i, x, z0, [best])
    return {
        "beta": best,
        "vf": complex(vf[0]),
        "vb": complex(vb[0]),
        "ssr": float(ssr[0]),
        "beta_at_grid_edge": bool(edge),
        "z0": complex(z0),
        "z0_free": False,
    }


def free_z0_search(v, i, x):
    """F3: Z0 on a 1-D grid nested in the beta search."""
    betas = np.linspace(BETA_LO, BETA_HI, BETA_COARSE)
    z_grid = np.linspace(Z0_LO, Z0_HI, Z0_COARSE)
    ssr_min = np.empty(z_grid.size)
    beta_min = np.empty(z_grid.size)
    for k, z0 in enumerate(z_grid):
        ssr, _, _ = solve_at(v, i, x, z0, betas)
        j = int(np.argmin(ssr))
        ssr_min[k] = ssr[j]
        beta_min[k] = betas[j]
    k = int(np.argmin(ssr_min))
    best = (float(ssr_min[k]), float(z_grid[k]), float(beta_min[k]))
    dz = float(z_grid[1] - z_grid[0])
    db = float(betas[1] - betas[0])
    for _ in range(REFINE_ROUNDS):
        zg = np.linspace(best[1] - dz, best[1] + dz, REFINE_POINTS)
        bg = np.linspace(best[2] - db, best[2] + db, REFINE_POINTS)
        cand = best
        for z0 in zg:
            sub, _, _ = solve_at(v, i, x, z0, bg)
            j = int(np.argmin(sub))
            if float(sub[j]) < cand[0]:
                cand = (float(sub[j]), float(z0), float(bg[j]))
        best = cand
        dz /= (REFINE_POINTS - 1) / 2.0
        db /= (REFINE_POINTS - 1) / 2.0
    ssr, vf, vb = solve_at(v, i, x, best[1], [best[2]])
    return {
        "beta": best[2],
        "vf": complex(vf[0]),
        "vb": complex(vb[0]),
        "ssr": float(ssr[0]),
        "beta_at_grid_edge": False,
        "z0": complex(best[1]),
        "z0_free": True,
    }


def measure(v, i, x, fit):
    """Everything the report quotes for one fit, from the fit itself."""
    z0 = fit["z0"]
    beta = fit["beta"]
    vf, vb = fit["vf"], fit["vb"]
    n = x.size

    e_minus = np.exp(-1j * beta * x)
    e_plus = np.exp(+1j * beta * x)
    v_pred = vf * e_minus + vb * e_plus
    i_pred = (vf * e_minus - vb * e_plus) / z0
    z_pred = v_pred / i_pred
    z_meas = v / i

    gamma = vb / vf
    g_abs = abs(gamma)
    vswr_sq = ((1.0 + g_abs) / (1.0 - g_abs)) ** 2 if g_abs < 1.0 else float("inf")
    omega = 2.0 * math.pi * fit["f_hz"]
    eps_eff = (beta * C_M_S / omega) ** 2

    return {
        "z0_re": z0.real,
        "z0_im": z0.imag,
        "beta_rad_m": beta,
        "vf_re": vf.real, "vf_im": vf.imag,
        "vb_re": vb.real, "vb_im": vb.imag,
        "gamma_abs": g_abs,
        "gamma_arg_deg": float(np.degrees(np.angle(gamma))),
        "vswr_power": float(vswr_sq),
        "eps_eff": float(eps_eff),
        "rms_residual": float(math.sqrt(fit["ssr"] / (2.0 * n))),
        "max_abs_zmag_error_ohm": float(np.max(np.abs(np.abs(z_pred) - np.abs(z_meas)))),
        "zmag_pred": [float(a) for a in np.abs(z_pred)],
        "zmag_meas": [float(a) for a in np.abs(z_meas)],
        "n_stations": int(n),
        "stations_js": [int(j) for j in fit["js"]],
        "stations_x_m": [float(a) for a in x],
        "beta_at_grid_edge": fit["beta_at_grid_edge"],
        "z0_free": fit["z0_free"],
    }


def run_fit(label, note, v, i, x, js, f_hz, z0=None, free=False):
    fit = (free_z0_search(v, i, x) if free else beta_search(v, i, x, z0))
    fit["js"] = list(js)
    fit["f_hz"] = f_hz
    out = measure(v, i, x, fit)
    out["label"] = label
    out["note"] = note
    return out


# --------------------------------------------------------------------------
# printing
# --------------------------------------------------------------------------
def print_fit(index, fit):
    print("")
    print("-" * 78)
    print("%s  %s" % (fit["label"], fit["note"]))
    print("-" * 78)
    print("  stations used      : %d   js = %s"
          % (fit["n_stations"], fit["stations_js"]))
    print("  x_m used           : %s"
          % ", ".join("%.6f" % a for a in fit["stations_x_m"]))
    print("  Z0                 : %.6f %+.6fj ohm%s"
          % (fit["z0_re"], fit["z0_im"],
             "   (FREE, found by the nested search)" if fit["z0_free"] else ""))
    print("  beta               : %.6f rad/m%s"
          % (fit["beta_rad_m"],
             "   [AT COARSE GRID EDGE]" if fit["beta_at_grid_edge"] else ""))
    print("  Vf                 : %.9f %+.9fj V" % (fit["vf_re"], fit["vf_im"]))
    print("  Vb                 : %.9f %+.9fj V" % (fit["vb_re"], fit["vb_im"]))
    print("  |Gamma|            : %.6f" % fit["gamma_abs"])
    print("  arg(Gamma)         : %.6f deg" % fit["gamma_arg_deg"])
    print("  ((1+|G|)/(1-|G|))^2: %.6f" % fit["vswr_power"])
    print("  epsilon_eff        : %.6f" % fit["eps_eff"])
    print("  RMS residual       : %.9e" % fit["rms_residual"])
    print("  max | |Z_pred| - |Z_meas| | : %.6f ohm"
          % fit["max_abs_zmag_error_ohm"])


def print_station_table(rec):
    x = rec["x_m"]
    x0 = float(x[0])
    z = rec["v"] / rec["i"]
    g = np.abs((z - Z0_REAL) / (z + Z0_REAL))
    print("")
    print("-" * 78)
    print("per-station Z = v/i and |Gamma| at Z0 = %.6f ohm" % Z0_REAL)
    print("-" * 78)
    print("  %-4s %-9s %-9s %-12s %-12s %-8s %s"
          % ("st", "x_m", "js", "|Z| ohm", "argZ deg", "|G|@Z0", "fit_selected"))
    for k in range(x.size):
        sel = rec["fit_selected"][k] if k < len(rec["fit_selected"]) else None
        print("  %-4s %-9.6f %-9d %-12.6f %-12.6f %-8.6f %s"
              % ("st%d" % k, x[k], rec["js"][k], abs(z[k]),
                 float(np.degrees(np.angle(z[k]))), float(g[k]), sel))
    print("  mean |G|@Z0 = %.6f   spread = %.6f   (x measured from x_min)"
          % (float(np.mean(g)), float(np.max(g) - np.min(g))))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Constrained two-wave fit in [Vf, Vb] on the station "
                    "phasors of one Build A plane artefact.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT),
                        help="plane artefact to read (default: the p50 file)")
    args = parser.parse_args(argv)

    path = Path(args.input)
    rec = load_record(path)
    x_raw = rec["x_m"]
    x0 = float(x_raw[0])
    x = x_raw - x0          # <- the fit's x origin: the smallest station x
    v, i = rec["v"], rec["i"]
    f_hz = rec["f_hz"]
    omega = 2.0 * math.pi * f_hz
    beta_eps = omega / C_M_S      # beta = omega*sqrt(eps_eff)/c

    print("=" * 78)
    print("A1  CONSTRAINED TWO-WAVE FIT:  V = Vf e^- + Vb e^+,")
    print("                              I = (Vf e^- - Vb e^+)/Z0")
    print("=" * 78)
    print("input                    = %s" % path)
    print("input bytes              = %d" % path.stat().st_size)
    print("stations                 = %d  (js = %s)"
          % (x.size, rec["js"]))
    print("x MEASURED FROM THE SMALLEST STATION x: x = x_station - x_min,")
    print("                           x_min = %.6f m (js = %d)"
          % (x0, rec["js"][0]))
    print("                           x (fit) = %s"
          % ", ".join("%.6f" % a for a in x))
    print("                           span = %.6f m"
          % float(x_raw[-1] - x_raw[0]))
    print("frequency                = %.12f Hz  (geometry.f_hz; the 'line' block"
          % f_hz)
    print("                           carries NO f_hz key)")
    print("beta from eps_eff = 1,2,3 = %.6f, %.6f, %.6f rad/m"
          % (beta_eps, beta_eps * math.sqrt(2.0), beta_eps * math.sqrt(3.0)))
    print("artefact line.beta       = %r"
          % (rec["line_beta"],))
    print("artefact beta_used       = %.12f rad/m" % rec["beta_used"])
    print("artefact cell_m          = %r" % (rec["cell_m"],))
    print("s11.magnitude_one_wave_station_fit = %r"
          % (rec["s11_magnitude_one_wave"],))
    print("s11.magnitude            = %r" % (rec["s11_magnitude"],))
    print("port |S11| (~0.326)      = %.6f ... %.6f  (the two keys above)"
          % (float(rec["s11_magnitude_one_wave"]), float(rec["s11_magnitude"])))
    print("STORED fit_selected mask = %s  (8 True, the last station js=%d is"
          % (rec["fit_selected"], rec["js"][-1]))
    print("                           the load column and was dropped by the")
    print("                           impedance fit; NO fit below honours it:"
          " all 9 stations are used except F4, which uses the last ones).")

    # cross-check of the closed-form solve against numpy.linalg.lstsq
    diff, ssr_ref = cross_check(v, i, x, Z0_REAL, 232.79891853803187)
    print("cross-check (Z0=47.305815, beta=232.798919): max |d Vf|,|d Vb| vs"
          " numpy.linalg.lstsq = %.3e" % diff)
    print("cross-check ssr                                  = %.9e" % ssr_ref)

    # ---- the fits ------------------------------------------------------
    fits = []
    fits.append(run_fit(
        "F1", "Z0 fixed real 47.305815 ohm, all 9 stations",
        v, i, x, rec["js"], f_hz, z0=complex(Z0_REAL, 0.0)))
    fits.append(run_fit(
        "F2", "Z0 fixed complex 47.305815+1.5582j ohm, all 9 stations",
        v, i, x, rec["js"], f_hz, z0=Z0_COMPLEX))

    fit3 = free_z0_search(v, i, x)
    fit3["js"] = list(rec["js"])
    fit3["f_hz"] = f_hz
    f3 = measure(v, i, x, fit3)
    f3["label"] = "F3"
    f3["note"] = ("Z0 REAL and FREE on a 1-D grid nested in the beta search "
                  "(CONTROL), all 9 stations")
    fits.append(f3)

    mask4 = [k for k, js in enumerate(rec["js"]) if js in F4_JS]
    fits.append(run_fit(
        "F4", "F1's Z0 real 47.305815 ohm, only the 3 stations nearest the "
              "load (js 44, 47, 50)",
        v[mask4], i[mask4], x[mask4],
        [rec["js"][k] for k in mask4], f_hz, z0=complex(Z0_REAL, 0.0)))

    mask4b = [k for k, js in enumerate(rec["js"]) if js in F4_JS_WITH_41]
    fits.append(run_fit(
        "F4b", "F1's Z0 real 47.305815 ohm, the last 4 stations nearest the "
               "load (js 41, 44, 47, 50) -- the '[+41]' variant of F4",
        v[mask4b], i[mask4b], x[mask4b],
        [rec["js"][k] for k in mask4b], f_hz, z0=complex(Z0_REAL, 0.0)))

    for k, fit in enumerate(fits, start=1):
        print_fit(k, fit)

    print_station_table(rec)

    # ---- the closing verdicts ------------------------------------------
    print("")
    print("=" * 78)
    print("VERDICT: does the constrained fit return |Gamma| close to 0.32?")
    print("         (YES if | |Gamma| - %.6f | <= %.3f)" % (S11_PORT_TARGET, CLOSE_TOL))
    print("=" * 78)
    yes = {}
    for fit in fits:
        ok = abs(fit["gamma_abs"] - S11_PORT_TARGET) <= CLOSE_TOL
        yes[fit["label"]] = bool(ok)
        print("%-4s %s %s  (|Gamma| = %.6f)"
              % (fit["label"], "YES" if ok else "NO ",
                 fit["label"], fit["gamma_abs"]))

    f1 = fits[0]
    f3r = f3
    degeneracy = bool(abs(f3r["gamma_abs"] - GAMMA_FREE_REFERENCE) <= CLOSE_TOL
                      and abs(f1["gamma_abs"] - S11_PORT_TARGET) <= CLOSE_TOL)
    print("")
    print("Is the free-fit bias explained by parameter degeneracy over a short")
    print("span (YES only if F3's |Gamma| is ~%.3f AND F1's is ~%.3f)?"
          % (GAMMA_FREE_REFERENCE, S11_PORT_TARGET))
    print("FREE-FIT DEGENERACY %s  (F3 |Gamma| = %.6f vs ~%.3f; F1 |Gamma| = "
          "%.6f vs ~%.3f; F3 Z0 = %.6f %+.6fj ohm)"
          % ("YES" if degeneracy else "NO ", f3r["gamma_abs"],
             GAMMA_FREE_REFERENCE, f1["gamma_abs"], S11_PORT_TARGET,
             f3r["z0_re"], f3r["z0_im"]))

    # ---- the JSON -------------------------------------------------------
    payload = {
        "script": "evidence/termination/analyze_constrained_fit.py",
        "input": str(path),
        "input_bytes": int(path.stat().st_size),
        "model": {
            "V": "Vf*exp(-j*beta*x) + Vb*exp(+j*beta*x)",
            "I": "(Vf*exp(-j*beta*x) - Vb*exp(+j*beta*x))/Z0",
            "x_origin": "smallest station x of the record",
            "x_min_m": x0,
            "gamma": "Vb/Vf",
            "solver": "ordinary least squares in [Vf, Vb]",
            "rows": "[V_k, I_k*Z0] = [[e_minus, e_plus], [e_minus, -e_plus]]",
            "beta_search": {
                "coarse_lo": BETA_LO, "coarse_hi": BETA_HI,
                "coarse_points": BETA_COARSE,
                "refine_rounds": REFINE_ROUNDS, "refine_points": REFINE_POINTS,
            },
            "z0_free_grid": {"lo": Z0_LO, "hi": Z0_HI, "points": Z0_COARSE},
        },
        "frequency_hz": f_hz,
        "frequency_source": "geometry.f_hz (the 'line' block has no f_hz key)",
        "cell_m": rec["cell_m"],
        "arsenal_beta_note": {
            "line_beta": rec["line_beta"],
            "station_beta_used": rec["beta_used"],
        },
        "port_s11": {
            "magnitude_one_wave_station_fit": rec["s11_magnitude_one_wave"],
            "magnitude": rec["s11_magnitude"],
            "phase_deg": rec["s11_phase_deg"],
        },
        "stored_fit_selected": rec["fit_selected"],
        "fit_selected_honoured": False,
        "stations": [
            {
                "st": "st%d" % k,
                "x_m": float(x_raw[k]),
                "x_rel_m": float(x[k]),
                "js": int(rec["js"][k]),
                "z_abs_ohm": float(abs(rec["v"][k] / rec["i"][k])),
                "z_arg_deg": float(np.degrees(np.angle(rec["v"][k] / rec["i"][k]))),
                "gamma_abs_at_z0_%s" % ("%.6f" % Z0_REAL): float(
                    abs((rec["v"][k] / rec["i"][k] - Z0_REAL)
                        / (rec["v"][k] / rec["i"][k] + Z0_REAL))),
                "fit_selected": rec["fit_selected"][k]
                if k < len(rec["fit_selected"]) else None,
            }
            for k in range(x.size)
        ],
        "cross_check_vs_lstsq_max_abs_diff": diff,
        "fits": {fit["label"]: fit for fit in fits},
        "verdict": {
            "close_to_0_32_tolerance": CLOSE_TOL,
            "gamma_close_to_0_32": yes,
            "free_fit_degeneracy_explained": degeneracy,
            "gamma_free_reference": GAMMA_FREE_REFERENCE,
            "gamma_port_reference": S11_PORT_TARGET,
        },
    }
    DEFAULT_OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("")
    print("wrote %s (%d bytes)" % (DEFAULT_OUTPUT, DEFAULT_OUTPUT.stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
