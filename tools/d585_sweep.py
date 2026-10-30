"""58.5 -- clearance sweep on the SAME FDTD measurement pipeline as d584_widebox.

One process, a batch of configurations, one JSON line appended (and flushed)
per completed case.  Everything the measurement depends on is held fixed and
only three things move:

    the air clearance (``clearance_scale`` x the 3H reference, in CELLS),
    ``nx`` (the guide length, given directly),
    the station window (``station_lo .. station_hi``, 6-cell spacing).

Held constant: substrate thickness (z cells 0..7, H = 1.600 mm), the
below-ground and all PML thicknesses (4 cells), the strip width in cells (4,
W = 0.800 mm), eps_r 4.4, CELL = 200 um, k (DFT bin index) and hence dt, f0 and
k0.  ``ny`` and ``nz`` are DERIVED from the clearance:

    air = round(24 * clearance_scale)      # cells, reference 24 = 3.000 H
    ny  = 2*N_PML + N_STRIP + 2*air
    nz  = N_SUB + air + N_PML              # upper PML inner node = nz - N_PML

which reproduces the validated reference (air 24 -> ny 60, nz 36) exactly.

The material setup, the strip PEC, the port drive, the capture, the two-field
split and every extraction line are transcribed from ``tools/d584_widebox.py``;
nothing under ``emfit/`` is touched.

Optional per-case spec keys (both defaults to absent):

    "dump": "<path>.npz"          -- per-station arrays of the single run
    "windows": [[lo, hi], ...]    -- re-fit alpha/beta on station sub-windows,
                                     one jsonl line per window named
                                     "<case>_w<lo>_<hi>".  The solver still
                                     runs ONCE per case; the windows are pure
                                     post-processing on the stored phasors.

    python -u tools/d585_sweep.py --spec spec.json --out results.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback

import numpy as np

from emfit.evolve import FITStepper, cfl_dt
from emfit.grid import Grid
from emfit.materials import EPS0, material_matrices
from emfit.modal_harness import ModalStationCapture, build_mode_plane
from emfit.operators import CellComplex
from emfit.pml import PML

C0 = 299792458.0
DB = 8.685889638065036  # nepers -> dB

# --- the coupon (constant, as validated) -----------------------------------
H = 1.6e-3
N_SUB = 8
CELL = H / N_SUB
EPS_R = 4.4
N_STRIP = 4
W = N_STRIP * CELL
N_TOP = 2                 # air cells above the strip covered by the zmax PML
N_PML = 4
N_REF = 4
N_WARM = 600
K_BIN = 8
REF_AIR = 24              # = round(3 * H / CELL): the validated 3H clearance
STATION_STEP = 6


# ---------------------------------------------------------------------------
# geometry -- the ONLY thing the sweep changes
# ---------------------------------------------------------------------------
def geometry(clearance_scale, nx, station_lo, station_hi):
    air = int(round(REF_AIR * float(clearance_scale)))
    if air < 1:
        raise ValueError(f"clearance_scale {clearance_scale!r} gives {air} air cells")
    ny = 2 * N_PML + N_STRIP + 2 * air
    nz = N_SUB + air + N_PML
    stations = tuple(range(int(station_lo), int(station_hi) + 1, STATION_STEP))
    if len(stations) < 2:
        raise ValueError(f"station window {station_lo}..{station_hi} yields "
                         f"{len(stations)} station(s); need at least 2")
    nx = int(nx)
    if int(stations[-1]) >= nx - N_PML:
        raise ValueError(f"station {stations[-1]} is inside the xmax PML "
                         f"(nx {nx}, PML {N_PML})")
    if int(stations[0]) <= N_PML:
        raise ValueError(f"station {stations[0]} is inside the xmin PML")
    return dict(air=air, nx=nx, ny=ny, nz=nz, stations=stations)


# ---------------------------------------------------------------------------
# build -- transcribed from d584_widebox.build(), with ny/nz/j0 from geometry
# ---------------------------------------------------------------------------
def build(g):
    nx, ny, nz = g["nx"], g["ny"], g["nz"]
    air = g["air"]
    grid = Grid.uniform(nx, ny, nz, nx * CELL, ny * CELL, nz * CELL)
    cc = CellComplex(grid)
    m_eps, m_mu = material_matrices(
        grid, cc, eps_r=lambda x, y, z: np.where(z <= H, EPS_R, 1.0))

    ix_port = N_PML + N_REF
    k_strip = N_SUB
    j0 = N_PML + air
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
    iy_centre = j0 + N_STRIP // 2
    mode = build_mode_plane(cc, h=H, w=W, eps_r=EPS_R, n_sub=N_SUB,
                            k_strip=k_strip, iy_strip_centre=iy_centre,
                            n_clean=air, n_air=air + N_PML - N_TOP)
    eps_max = float(np.max(m_eps)) / (EPS0 * CELL)
    return dict(cc=cc, stepper=stepper, mode=mode, ix_port=ix_port,
                j0=j0, j1=j1, mesh=(nx, ny, nz), grid=grid, eps_max=eps_max)


# ---------------------------------------------------------------------------
# extraction helpers
# ---------------------------------------------------------------------------
def fit_line(x, y):
    """Least-squares line: slope, intercept, residual rms."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    A = np.vstack([x, np.ones_like(x)]).T
    (slope, inter), *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - (slope * x + inter)
    return float(slope), float(inter), float(np.sqrt(np.mean(r ** 2)))


def _fit_window(st, x, af):
    """alpha/beta/quality on one (sub-)set of stations.  Pure post-processing."""
    sl, _, logamp_rms = fit_line(x, np.log(np.abs(af)))
    alpha = -sl
    ph = np.unwrap(np.angle(af))
    besl, _, phrms = fit_line(x, ph)
    beta = -besl

    per_interval = []
    for i in range(st.size - 1):
        dd = float(x[i + 1] - x[i])
        a_i = -np.log(abs(af[i + 1]) / abs(af[i])) / dd
        per_interval.append(a_i * 1e-3 * DB)
    return alpha, beta, phrms, logamp_rms, per_interval


# ---------------------------------------------------------------------------
# the single FDTD run
# ---------------------------------------------------------------------------
def _solve(case):
    g = geometry(case["clearance_scale"], case["nx"],
                 case["station_lo"], case["station_hi"])
    n_acc = int(case["n_acc"])
    b = build(g)
    cc, stepper, mode = b["cc"], b["stepper"], b["mode"]
    ix_port, j0, j1 = b["ix_port"], b["j0"], b["j1"]
    dt = float(stepper.dt)
    f0 = K_BIN / (n_acc * dt)
    stations = np.asarray(g["stations"], dtype=int)

    cap = ModalStationCapture(cc, mode, stations, f0=f0, dt=dt, limit=n_acc,
                              n_warm=N_WARM, destagger_h=False)
    port_edges = np.unique(np.concatenate(
        [cc.idx_ez(np.array([ix_port]), np.array([j]),
                   np.arange(0, N_SUB)).ravel() for j in range(j0, j1 + 1)]))

    def drive(n):
        cur = np.zeros(cc.n_edges, dtype=float)
        cur[port_edges] = min(1.0, (n + 1) / N_WARM) * np.sin(
            2.0 * np.pi * f0 * n * dt)
        return cur

    t0 = time.perf_counter()
    res = cap.run(stepper, drive=drive)
    wall = time.perf_counter() - t0

    st = stations
    x = (st - st[0]) * CELL
    k0 = 2.0 * np.pi * f0 / C0
    th = np.pi * f0 * dt

    ae = np.array([res["a_e"][int(i)] for i in st])
    ah = np.array([res["a_h"][int(i)] for i in st]) * np.exp(+1j * th)

    v_mode = float(mode.v_mode)
    i_mode = float(mode.i_mode)
    z0 = float(mode.z0_power)

    af = (ae * v_mode + z0 * ah * i_mode) / (2.0 * v_mode)
    ab = (ae * v_mode - z0 * ah * i_mode) / (2.0 * v_mode)

    bound = k0 * np.sqrt(b["eps_max"])

    return dict(g=g, case=case, wall=wall, steps=int(res["steps"]), st=st,
                x=x, af=af, ab=ab, k0=k0, bound=bound, f0=f0)


# ---------------------------------------------------------------------------
# station (sub-)set -> one result record
# ---------------------------------------------------------------------------
def _record(ctx, mask):
    g = ctx["g"]
    case = ctx["case"]
    k0 = ctx["k0"]

    st = ctx["st"][mask]
    x = ctx["x"][mask]
    af = ctx["af"][mask]
    ab = ctx["ab"][mask]

    alpha, beta, phrms, logamp_rms, per_interval = _fit_window(st, x, af)

    return dict(clearance_scale=float(case["clearance_scale"]),
                nx=g["nx"], ny=g["ny"], nz=g["nz"],
                cells=int(g["nx"] * g["ny"] * g["nz"]),
                wall_s=round(ctx["wall"], 3),
                alpha_per_m=round(alpha, 5),
                beta_per_m=round(beta, 5),
                eps_eff=round((beta / k0) ** 2, 6),
                ab_over_af_max=round(float(np.max(np.abs(ab) / np.abs(af))), 6),
                phase_rms_deg=round(float(np.degrees(phrms)), 6),
                logamp_rms=round(logamp_rms, 9),
                alpha_per_interval=[round(q, 6) for q in per_interval],
                beta_over_bound=round(beta / ctx["bound"], 6),
                n_steps=ctx["steps"], ok=True, error=None)


def _error_record(case, message, wall, ctx=None):
    g = ctx["g"] if ctx is not None else {}
    return dict(clearance_scale=_maybe_float(case.get("clearance_scale")),
                nx=case.get("nx"), ny=g.get("ny"), nz=g.get("nz"),
                cells=(int(g["nx"] * g["ny"] * g["nz"]) if g else None),
                wall_s=round(wall, 3),
                alpha_per_m=None, beta_per_m=None, eps_eff=None,
                ab_over_af_max=None, phase_rms_deg=None, logamp_rms=None,
                alpha_per_interval=None, beta_over_bound=None,
                n_steps=(ctx["steps"] if ctx is not None else None),
                ok=False, error=message)


def _maybe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def _window_mask(ctx, lo, hi):
    """Stations inside [lo, hi]; raises ValueError if the window is invalid."""
    g = ctx["g"]
    nx = g["nx"]
    if lo < 1:
        raise ValueError(f"window lo {lo} < 1")
    if hi > nx - 1:
        raise ValueError(f"window hi {hi} > nx-1 = {nx - 1}")
    if hi - lo < 4:
        raise ValueError(f"window span hi-lo = {hi - lo} < 4")
    st = ctx["st"]
    mask = (st >= lo) & (st <= hi)
    n_in = int(mask.sum())
    if n_in < 2:
        raise ValueError(f"window {lo}..{hi} contains {n_in} extracted "
                         f"station(s); need at least 2 (extracted: "
                         f"{st.tolist()})")
    return mask


def _dump(path, ctx, rec):
    """Per-station arrays of the single FDTD run, plus the headline scalars."""
    st = ctx["st"]
    af, ab = ctx["af"], ctx["ab"]
    amp = np.abs(af)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    np.savez(path,
             station_cells=st.astype(np.int64),
             amp=amp.astype(float),
             phase_rad=np.unwrap(np.angle(af)).astype(float),
             ab_over_af=(np.abs(ab) / amp).astype(float),
             af_re=af.real.astype(float), af_im=af.imag.astype(float),
             ab_re=ab.real.astype(float), ab_im=ab.imag.astype(float),
             beta_per_m=float(rec["beta_per_m"]),
             alpha_per_m=float(rec["alpha_per_m"]),
             nx=int(ctx["g"]["nx"]), ny=int(ctx["g"]["ny"]),
             nz=int(ctx["g"]["nz"]))


def run_case(case):
    """One FDTD run; returns a list of (name_suffix, record) to emit."""
    ctx = _solve(case)                                    # <-- solver, once
    base = _record(ctx, np.ones(ctx["st"].size, dtype=bool))

    if case.get("dump"):
        _dump(str(case["dump"]), ctx, base)

    windows = case.get("windows")
    if not windows:
        return [("", base)]

    lines = []
    for w in windows:
        lo, hi = int(w[0]), int(w[1])
        suffix = f"_w{lo}_{hi}"
        try:
            lines.append((suffix, _record(ctx, _window_mask(ctx, lo, hi))))
        except Exception as exc:                          # bad window: no raise
            lines.append((suffix, _error_record(
                case, f"window {lo}..{hi}: {type(exc).__name__}: {exc}",
                ctx["wall"], ctx)))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.spec) as fh:
        spec = json.load(fh)

    with open(args.out, "a") as out:
        for case in spec["cases"]:
            name = str(case.get("name", "case"))
            t0 = time.perf_counter()
            try:
                lines = run_case(case)
            except Exception as exc:                      # never kill the batch
                lines = [("", _error_record(
                    case, f"{type(exc).__name__}: {exc}",
                    time.perf_counter() - t0))]
                traceback.print_exc()
            for suffix, rec in lines:
                rec = {"name": name + suffix, **rec}
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(f"{rec['name']} alpha={rec['alpha_per_m']} "
                      f"beta={rec['beta_per_m']}", flush=True)


if __name__ == "__main__":
    main()
