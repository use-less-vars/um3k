"""Probe: is the pipeline's forward-amplitude ``beta`` the cross-section eigenmode?

A straight, uniform microstrip through-line is driven CW on a DFT bin and
sampled at three station planes once the record is in steady state.  Three
numbers for the same mode at the same ``f0``:

``beta_raw``
    ``-angle(v2 / v1) / d`` on the raw station phasors.  No split, no trial
    beta -- the total field's phase slope.
``beta_pipeline``
    the *primary* estimator: split station pair ``(x1, x2)`` into forward and
    backward waves with :func:`emfit.ports.travelling_waves` (via
    :func:`emfit.modal_harness.split_forward_backward`), split ``(x2, x3)`` the
    same way, and take the phase slope of the *forward* amplitudes,
    ``-angle(a_f(x2) / a_f(x1)) / d``.  The trial ``beta`` handed to the split
    is iterated to the answer it produces (fixed point).
``beta_EIG``
    :func:`emfit.mode2d.solve_modes_mixed` on the cross-section at the same
    ``f0``: a dense QZ solve of the mixed ``(e_t, e_z)`` pencil.  Two boundary
    closures are reported, because the FDTD uses PML on the lateral walls and
    the top while the eigenmode solver has only PEC/Neumann: ``open``
    (ground + strip only, Neumann elsewhere) and ``pec_box`` (ground + strip +
    both lateral walls + top).  The two bracket the FDTD answer.

Nothing here is a fit: every ``beta`` is a phase slope or an eigenvalue.
Also reported: ``|b/a|`` per station (how much of the plane is not the
forward wave) and the implied ``eps_eff = (beta / k0)^2``.
"""

from __future__ import annotations

import json
import os
import time

import numpy as np

from emfit import mode2d
from emfit.evolve import FITStepper, cfl_dt
from emfit.grid import Grid
from emfit.materials import material_matrices
from emfit.modal_harness import (ModalStationCapture, build_mode_plane,
                                 split_forward_backward)
from emfit.operators import CellComplex
from emfit.pml import PML

C0 = 299792458.0

# --- the coupon (studies.microstrip_wave recipe, line lengthened) -----------
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
N_LINE = 40
N_WARM = 600
K_BIN = 8
N_ACC = 2096
D_CELLS = 12

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out",
                   "modal_beta_probe.json")


def _json_default(o):
    """FIX 1: complex -> [re, im]; everything else through float()."""
    if isinstance(o, complex):
        return [float(o.real), float(o.imag)]
    if isinstance(o, np.ndarray):
        return o.tolist()
    return float(o)


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
    return cc, stepper, ix_port, k_strip, j0, j1, (nx, ny, nz)


def drive_edges(cc, ix_port, k_strip, j0, j1):
    return np.unique(np.concatenate(
        [cc.idx_ez(np.array([ix_port]), np.array([j]),
                   np.arange(0, k_strip)).ravel() for j in range(j0, j1 + 1)]))


def run_fdtd():
    cc, stepper, ix_port, k_strip, j0, j1, mesh = build()
    dt = float(stepper.dt)
    f0 = K_BIN / (N_ACC * dt)
    stations = np.array([ix_port + 6, ix_port + 6 + D_CELLS,
                         ix_port + 6 + 2 * D_CELLS], dtype=int)
    mode = build_mode_plane(cc, h=H, w=W, eps_r=EPS_R, n_sub=N_SUB,
                            k_strip=k_strip, iy_strip_centre=j0 + N_STRIP // 2,
                            n_clean=N_CLEAN, n_air=N_AIR)
    cap = ModalStationCapture(cc, mode, stations, f0=f0, dt=dt, limit=N_ACC,
                              n_warm=N_WARM)
    port_edges = drive_edges(cc, ix_port, k_strip, j0, j1)

    def drive(n):
        cur = np.zeros(cc.n_edges, dtype=float)
        cur[port_edges] = min(1.0, (n + 1) / N_WARM) * np.sin(
            2.0 * np.pi * f0 * n * dt)
        return cur

    t0 = time.perf_counter()
    res = cap.run(stepper, drive=drive)
    wall = time.perf_counter() - t0
    res.update(f0=f0, dt=dt, wall_s=wall, mesh=mesh, n_edges=cc.n_edges,
               port_ix=int(ix_port), stations=[int(s) for s in stations],
               n_steps=N_WARM + N_ACC)
    return res


def eigen(f0):
    """FIX 2: iterate mode.candidates DIRECTLY (never zip a maybe-empty tuple)."""
    nyc = 2 * N_PML + N_STRIP + 2 * N_CLEAN
    nzc = N_SUB + N_AIR + N_TOP
    ly, lz = nyc * CELL, nzc * CELL
    j0 = N_PML + N_CLEAN
    y0, y1 = j0 * CELL, (j0 + N_STRIP) * CELL
    tol = 1e-9
    mesh = mode2d.box_mesh(ly, lz, nyc, nzc)
    eps = lambda c: np.where(c[:, 1] <= H + tol, EPS_R, 1.0)   # noqa: E731
    ground = lambda p: p[:, 1] <= tol                          # noqa: E731
    strip = lambda p: ((np.abs(p[:, 1] - H) <= tol)            # noqa: E731
                       & (p[:, 0] >= y0 - tol) & (p[:, 0] <= y1 + tol))
    ymin = lambda p: p[:, 0] <= tol                            # noqa: E731
    ymax = lambda p: p[:, 0] >= ly - tol                       # noqa: E731
    top = lambda p: p[:, 1] >= lz - tol                        # noqa: E731
    k0 = 2.0 * np.pi * f0 / C0
    out = {}
    for name, bounds in (("open", (ground, strip)),
                         ("pec_box", (ground, strip, ymin, ymax, top))):
        t0 = time.perf_counter()
        mode = mode2d.solve_modes_mixed(mesh, k0, sigma=1.0, eps_r=eps,
                                        boundaries=bounds)
        wall = time.perf_counter() - t0
        residuals = tuple(mode.candidate_residuals)
        ratios = tuple(mode.curl_ratio)
        cands = []
        for i, (b_sq, e_eff) in enumerate(mode.candidates):
            b_sq = float(b_sq)
            e_eff = float(e_eff)
            cands.append(dict(
                index=i, beta_sq=b_sq,
                beta=float(np.sqrt(b_sq)) if b_sq > 0.0 else float("nan"),
                eps_eff=e_eff,
                physical=bool(1.0 < e_eff < EPS_R),
                residual=(float(residuals[i]) if i < len(residuals)
                          else float("nan")),
                curl_ratio=(float(ratios[i]) if i < len(ratios)
                            else float("nan"))))
        pos = [c for c in cands if np.isfinite(c["beta_sq"]) and c["beta_sq"] > 0]
        pos.sort(key=lambda c: -c["beta_sq"])
        above = [c for c in pos if c["eps_eff"] > EPS_R]
        out[name] = dict(wall_s=wall, n_dof=int(mode.n_dof),
                         n_pec=int(mode.n_pec), chosen=int(mode.chosen),
                         beta_builtin_pick=float(mode.beta),
                         eps_eff_builtin_pick=float(mode.eps_eff),
                         n_candidates=len(cands),
                         n_positive=len(pos),
                         n_nondpositive=len(cands) - len(pos),
                         n_above_eps_r=len(above),
                         above_eps_r=[dict(beta=c["beta"], eps_eff=c["eps_eff"],
                                           residual=c["residual"],
                                           index=c["index"]) for c in above],
                         max_eps_eff=(max((c["eps_eff"] for c in pos),
                                          default=float("nan"))),
                         n_residuals_available=len(residuals),
                         candidates=pos, candidates_all=cands)
    out["mesh"] = dict(ny=nyc, nz=nzc, ly=ly, lz=lz, k0=k0,
                       n_nodes=int(mesh.n_nodes), free_edges=int(
                           (~mode2d.pec_edge_mask(mesh, (ground, strip))).sum()))
    return out


QUASI_TEM_EPS_GUESS = 3.45     # W/H = 0.5 on eps_r 4.4 -> ~3.3-3.6


def _fixed_point(v1, v2, d, beta0, tol=1e-9, iters=60):
    """Iterate the trial beta handed to the two-station split to its fixed point."""
    beta = float(beta0)
    hist = []
    for _ in range(iters):
        af, ab = split_forward_backward(v1, v2, d, beta)
        beta_new = beta
        hist.append((beta, af, ab))
        break                                  # single split: see analyse()
    return hist[0]


def analyse(res):
    """DIAGNOSTIC 3: (a) a_e/a_h, (b) |a_f|/|a_b| + alpha, (c) beta per pair."""
    amps, a_e, a_h = res["amplitudes"], res["a_e"], res["a_h"]
    f0, dt, d = res["f0"], res["dt"], D_CELLS * CELL
    x = res["stations"]
    v = np.array([amps[ix] for ix in x], dtype=complex)
    k0 = 2.0 * np.pi * f0 / C0

    # (a) projection normalisation: a_e / a_h per station
    ratio = {}
    for ix in x:
        r = complex(a_e[ix]) / complex(a_h[ix])
        ratio[int(ix)] = r
    r1 = ratio[int(x[0])]
    norm_rows = []
    for ix in x:
        r = ratio[int(ix)]
        norm_rows.append(dict(
            station=int(ix), a_e=[float(complex(a_e[ix]).real),
                                  float(complex(a_e[ix]).imag)],
            a_h=[float(complex(a_h[ix]).real), float(complex(a_h[ix]).imag)],
            abs_ratio=float(abs(r)), phase_deg=float(np.degrees(np.angle(r))),
            rel_mag_vs_first=float(abs(r) / abs(r1) - 1.0),
            dphase_vs_first_deg=float(np.degrees(np.angle(r / r1)))))
    spread_mag = max(r["abs_ratio"] for r in norm_rows) / min(
        r["abs_ratio"] for r in norm_rows) - 1.0
    phases = [np.angle(ratio[int(ix)]) for ix in x]
    spread_phase_deg = float(np.degrees(max(phases) - min(phases)))

    # (c) raw slope on ALL THREE pairs
    pairs = [(0, 1), (1, 2), (0, 2)]
    raw_pairs = []
    for i, j in pairs:
        dd = (x[j] - x[i]) * CELL
        raw_pairs.append(dict(
            pair=[int(x[i]), int(x[j])], d=float(dd),
            beta=float(-np.angle(v[j] / v[i]) / dd),
            phase_rad=float(np.angle(v[j] / v[i]))))
    beta_raw = float(np.mean([p["beta"] for p in raw_pairs[:2]]))

    # pipeline: af@x1 from split(x1,x2), af@x2 from split(x2,x3); iterate trial beta
    beta = beta_raw
    hist = []
    for _ in range(60):
        af1, ab1 = split_forward_backward(v[0], v[1], d, beta)
        af2, ab2 = split_forward_backward(v[1], v[2], d, beta)
        beta_new = float(-np.angle(af2 / af1) / d)
        hist.append(beta_new)
        if abs(beta_new - beta) < 1e-9:
            beta = beta_new
            break
        beta = beta_new
    af1, ab1 = split_forward_backward(v[0], v[1], d, beta)
    af2, ab2 = split_forward_backward(v[1], v[2], d, beta)
    af3 = af2 * np.exp(-1j * beta * d)          # forward carried past station 3

    # trial-beta sensitivity of the split
    trials = {}
    for tag, b0 in (("beta_raw(14,26)", raw_pairs[0]["beta"]),
                    ("beta_raw(26,38)", raw_pairs[1]["beta"]),
                    ("beta_raw(14,38)", raw_pairs[2]["beta"]),
                    ("beta_pipeline", beta)):
        a1, _ = split_forward_backward(v[0], v[1], d, b0)
        a2, _ = split_forward_backward(v[1], v[2], d, b0)
        trials[tag] = dict(trial_beta=float(b0),
                           beta_out=float(-np.angle(a2 / a1) / d),
                           abs_af=[float(abs(a1)), float(abs(a2))])

    # (b) attenuation from the |a_f| decay (lossless -> 0)
    alpha_12 = float(-np.log(abs(af2) / abs(af1)) / d)
    alpha_13 = float(-np.log(abs(af3) / abs(af1)) / (2.0 * d))
    db_per_mm = float(-20.0 * np.log10(abs(af2) / abs(af1)) / (d * 1e3))

    # (d) drive / PML geometry
    nx, ny, nz = res["mesh"]
    geom = dict(
        nx=int(nx), ny=int(ny), nz=int(nz), cell=CELL,
        ix_port=int(res["port_ix"]),
        pml_thickness_cells=N_PML, pml_cell_extents=dict(
            xmin=[0, N_PML], xmax=[int(nx - N_PML), int(nx)],
            ymin=[0, N_PML], ymax=[int(ny - N_PML), int(ny)],
            zmax=[int(nz - N_PML), int(nz)], zmin="none (ground PEC)"),
        stations_x_index=[int(s) for s in x],
        stations_x_m=[float(s * CELL) for s in x],
        station1_cells_from_xmin_pml=int(x[0] - N_PML),
        station1_m_from_xmin_pml=float((x[0] - N_PML) * CELL),
        station1_cells_from_port=int(x[0] - res["port_ix"]),
        station1_m_from_port=float((x[0] - res["port_ix"]) * CELL),
        source_cells_from_xmin_pml=int(res["port_ix"] - N_PML),
        source_in_pml=bool(res["port_ix"] < N_PML),
        last_station_cells_from_xmax_pml=int((nx - N_PML) - x[-1]),
        line_length_m=float((nx - 2 * N_PML) * CELL))

    return dict(
        f0=f0, dt=dt, d=d, k0=k0, stations=x, v=[complex(z) for z in v],
        beta_raw=beta_raw, beta_raw_pairs=raw_pairs,
        beta_pipeline=beta, pipeline_iterations=len(hist),
        pipeline_trial_sensitivity=trials,
        eps_eff_raw=(beta_raw / k0) ** 2,
        eps_eff_pipeline=(beta / k0) ** 2,
        a_e_a_h=norm_rows, aea_h_abs_spread=float(spread_mag),
        aea_h_phase_spread_deg=float(spread_phase_deg),
        af=[complex(af1), complex(af2), complex(af3)],
        ab=[complex(ab1), complex(ab2)],
        abs_af=[float(abs(af1)), float(abs(af2)), float(abs(af3))],
        abs_ab=[float(abs(ab1)), float(abs(ab2))],
        abs_b_over_a=[float(abs(ab1 / af1)), float(abs(ab2 / af2))],
        alpha_12=alpha_12, alpha_13=alpha_13, alpha_db_per_mm=db_per_mm,
        geometry=geom)


def main():
    res = run_fdtd()
    a = analyse(res)
    e = eigen(a["f0"])

    lines = []
    say = lines.append
    say("=" * 78)
    say("MODAL BETA PROBE -- uniform microstrip, CW on a DFT bin")
    say("=" * 78)
    say(f"mesh {res['mesh']} cells, {res['n_edges']} edges, cell {CELL:.6e} m, "
        f"H {H:.4e} m, W {W:.4e} m, eps_r {EPS_R}")
    say(f"dt {res['dt']!r} s, bin k={K_BIN}/n_acc={N_ACC} -> f0 {res['f0']!r} Hz, "
        f"n_warm {N_WARM}, total {res['n_steps']} steps")
    say(f"stations ix {a['stations']} (d = {D_CELLS} cells = {a['d']:.6e} m)")
    say(f"FDTD wall time: {res['wall_s']:.2f} s "
        f"({1e3 * res['wall_s'] / res['n_steps']:.3f} ms/step)")
    say("")
    say("-- station phasors ------------------------------------------------")
    for ix, v in zip(a["stations"], a["v"]):
        say(f"  station {ix:3d}: v = {v.real:+.6e} {v.imag:+.6e}j  "
            f"|v| = {abs(v):.6e}")

    say("")
    say("-- (a) projection normalisation: a_e / a_h per station ------------")
    for r in a["a_e_a_h"]:
        say(f"  station {r['station']:3d}: a_e = {r['a_e'][0]:+.6e} "
            f"{r['a_e'][1]:+.6e}j   a_h = {r['a_h'][0]:+.6e} "
            f"{r['a_h'][1]:+.6e}j")
        say(f"               a_e/a_h: |r| = {r['abs_ratio']:.9e}  "
            f"arg = {r['phase_deg']:+.6f} deg   "
            f"(vs station {a['stations'][0]}: |r| {r['rel_mag_vs_first']:+.3e}, "
            f"arg {r['dphase_vs_first_deg']:+.6f} deg)")
    say(f"  STATION SPREAD: |a_e/a_h| max/min - 1 = "
        f"{a['aea_h_abs_spread']:+.6e}; phase spread = "
        f"{a['aea_h_phase_spread_deg']:.6f} deg")

    say("")
    say("-- (b) forward/backward amplitudes and attenuation ----------------")
    say(f"  |a_f| at x = {a['stations'][0]}, {a['stations'][1]}, "
        f"{a['stations'][2]} (third = carried with beta): "
        f"{a['abs_af'][0]:.6e}, {a['abs_af'][1]:.6e}, {a['abs_af'][2]:.6e}")
    say(f"  |a_b| at x = {a['stations'][0]}, {a['stations'][1]}: "
        f"{a['abs_ab'][0]:.6e}, {a['abs_ab'][1]:.6e}")
    say(f"  |b/a| = {a['abs_b_over_a'][0]:.6e} (x={a['stations'][1]}), "
        f"{a['abs_b_over_a'][1]:.6e} (x={a['stations'][2]})")
    say(f"  alpha from |a_f| decay over d: {a['alpha_12']:+.6e} 1/m "
        f"({a['alpha_db_per_mm']:+.6f} dB/mm)")
    say(f"  alpha over 2d: {a['alpha_13']:+.6e} 1/m")
    say(f"  |a_f| ratio (x2/x1) = {a['abs_af'][1] / a['abs_af'][0]:.9e}")

    say("")
    say("-- (c) beta per station pair --------------------------------------")
    for p in a["beta_raw_pairs"]:
        say(f"  raw slope pair {p['pair'][0]}-{p['pair'][1]} "
            f"(d = {p['d']:.6e} m): beta_raw = {p['beta']!r} rad/m   "
            f"phase = {p['phase_rad']:+.6f} rad")
    say(f"  beta_raw (mean of the two d-spaced pairs) = {a['beta_raw']!r} rad/m"
        f"   eps_eff = {a['eps_eff_raw']:.6f}")
    say(f"  beta_pipeline (fixed point) = {a['beta_pipeline']!r} rad/m   "
        f"eps_eff = {a['eps_eff_pipeline']:.6f}   "
        f"{a['pipeline_iterations']} iterations")
    say("  trial-beta sensitivity of the forward split:")
    for tag, t in a["pipeline_trial_sensitivity"].items():
        say(f"    trial {tag:18s} = {t['trial_beta']!r} -> "
            f"beta_out = {t['beta_out']!r} rad/m  "
            f"(|a_f| {t['abs_af'][0]:.6e} -> {t['abs_af'][1]:.6e})")

    g = a["geometry"]
    say("")
    say("-- (d) drive and PML placement ------------------------------------")
    say(f"  grid {g['nx']} x {g['ny']} x {g['nz']} cells, cell "
        f"{g['cell']:.6e} m, line {g['line_length_m']:.6e} m between PML walls")
    say(f"  ix_port = {g['ix_port']} (cell index of the drive plane); "
        f"source {g['source_cells_from_xmin_pml']} cells inside the "
        f"xmin PML edge, in_pml = {g['source_in_pml']}")
    for axis, ext in g["pml_cell_extents"].items():
        say(f"  PML {axis:5s}: cells {ext}")
    say(f"  stations at ix {g['stations_x_index']} = "
        f"{[round(m * 1e3, 4) for m in g['stations_x_m']]} mm")
    say(f"  station 1 is {g['station1_cells_from_xmin_pml']} cells "
        f"({g['station1_m_from_xmin_pml']:.6e} m) from the xmin PML edge and "
        f"{g['station1_cells_from_port']} cells "
        f"({g['station1_m_from_port']:.6e} m) from the source")
    say(f"  last station is {g['last_station_cells_from_xmax_pml']} cells from "
        f"the xmax PML edge")

    m = e["mesh"]
    say("")
    say("-- eigenmode reference (same f0) ----------------------------------")
    say(f"  mode2d mesh {m['ny']}x{m['nz']} ({m['n_nodes']} nodes, "
        f"{m['free_edges']} free edges), k0 = {m['k0']!r} 1/m")
    sel = {}
    for name in ("open", "pec_box"):
        r = e[name]
        say(f"-- boundaries '{name}': n_dof {r['n_dof']}, n_pec {r['n_pec']}, "
            f"candidates {r['n_candidates']} "
            f"({r['n_positive']} with beta^2 > 0, "
            f"{r['n_nondpositive']} cut off/complex), "
            f"candidate_residuals available: {r['n_residuals_available']}, "
            f"solve {r['wall_s']:.2f} s")
        say(f"   max eps_eff over the positive spectrum = {r['max_eps_eff']!r}; "
            f"candidates with eps_eff > eps_r = {r['n_above_eps_r']}")
        for c in r["above_eps_r"]:
            say(f"     ABOVE eps_r: beta = {c['beta']!r} eps_eff = "
                f"{c['eps_eff']!r} residual {c['residual']:.3e} "
                f"[idx {c['index']}]")
        say("   full positive spectrum (beta, eps_eff, physical?, residual):")
        for c in r["candidates"]:
            say(f"     [{c['index']:3d}] beta {c['beta']!r:>22}  eps_eff "
                f"{c['eps_eff']:+.6f}  phys {str(c['physical']):5s}  res "
                f"{c['residual']:.3e}")
        phys = [c for c in r["candidates"] if c["physical"]]
        if phys:
            pick = min(phys, key=lambda c: abs(c["eps_eff"] - QUASI_TEM_EPS_GUESS))
            largest = max(phys, key=lambda c: c["eps_eff"])
            sel[name] = dict(beta=pick["beta"], eps_eff=pick["eps_eff"],
                             residual=pick["residual"])
            say(f"   QUASI-TEM pick (physical, nearest eps_eff "
                f"{QUASI_TEM_EPS_GUESS}): beta_EIG = {pick['beta']!r} rad/m, "
                f"eps_eff = {pick['eps_eff']!r}, res {pick['residual']:.3e}")
            say(f"     largest physical eps_eff = {largest['eps_eff']!r} "
                f"(beta {largest['beta']!r})")
            say(f"     (beta_pipeline - beta_EIG)/beta_EIG = "
                f"{(a['beta_pipeline'] - pick['beta']) / pick['beta']:+.6e}")
            say(f"     (beta_raw      - beta_EIG)/beta_EIG = "
                f"{(a['beta_raw'] - pick['beta']) / pick['beta']:+.6e}")
        else:
            sel[name] = None
            say("   NO physical candidate (1 < eps_eff < eps_r) in this spectrum")

    say("")
    say(f"beta_pipeline vs beta_raw: "
        f"{a['beta_pipeline'] / a['beta_raw'] - 1.0:+.3e} relative")
    if all(sel.get(k) for k in ("open", "pec_box")):
        for k in ("open", "pec_box"):
            say(f"beta_EIG[{k}] = {sel[k]['beta']!r} rad/m, "
                f"(beta_pipeline - beta_EIG)/beta_EIG = "
                f"{(a['beta_pipeline'] - sel[k]['beta']) / sel[k]['beta']:+.6e}")
    print("\n".join(lines), flush=True)

    payload = dict(fdtd=res, analysis=a, eigenmode=e,
                   config=dict(H=H, CELL=CELL, EPS_R=EPS_R, W=W, N_SUB=N_SUB,
                               N_STRIP=N_STRIP, N_PML=N_PML, N_REF=N_REF,
                               N_LINE=N_LINE, N_WARM=N_WARM, K_BIN=K_BIN,
                               N_ACC=N_ACC, D_CELLS=D_CELLS))
    with open(OUT, "w") as fh:
        json.dump(payload, fh, indent=2, default=_json_default)
    print(f"\nwrote {os.path.abspath(OUT)}", flush=True)


if __name__ == "__main__":
    main()
