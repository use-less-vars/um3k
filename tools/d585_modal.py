"""Cross-section eigenmodes of the straight microstrip, under both closures.

Three questions, one cross-section:

``closures``
    ``open`` (ground + strip only, Neumann elsewhere) vs ``pec_box`` (ground +
    strip + lateral walls + top) on the **identical** box: how much of the
    historical ``beta`` disagreement was geometry and how much closure.
``airsweep``
    fixed closure ``open``, air clearance swept in units of ``H``: where does
    ``beta`` stop moving?
``refine``
    fixed clearance, ``H / h = 8, 12, 16``: the observed order ``p`` of
    ``beta(h) = beta_exact + C h^p`` against the Hammerstad quasi-static
    ``beta = 365 rad/m``.
``validate``
    the two solvers on one geometry: the sparse ARPACK engine
    (:func:`emfit.mode2d.solve_modes`) against the dense mixed QZ
    (:func:`emfit.mode2d.solve_modes_mixed`) that ``tools/modal_beta_probe.py``
    used.  The mixed QZ is kept **only** for this: it is O(n^3) with a dense
    ``B`` block and dies on the boxes the sweep needs.

Engine
------
``solve_modes(mesh, k0, sigma, eps_r=eps, boundaries=bounds, k=k)`` -- ARPACK
shift-invert on ``(K_q - k0^2 M_eps) e = beta^2 M_mu e``, i.e. the transverse
pencil (no ``e_z``).  ``sigma`` is placed just above the physical ceiling
``k0^2 er`` (every physical mode has ``eps_eff = beta^2/k0^2 < er``) and the
whole candidate list is reported; nothing here trusts ``mode.chosen``.

Substrate field-energy fraction
-------------------------------
``f_sub = e^T M_eps,sub e / e^T M_eps e`` with ``M_eps,sub`` assembled at
``eps = er`` inside the substrate and ``0`` in air: the *transverse* electric
energy carried in the substrate.  :class:`emfit.mode2d.Mode2D` exposes
``e_t`` for the chosen mode only (``candidates`` is a list of
``(beta_sq, eps_eff)`` pairs and carries no vectors), so non-chosen rows
report ``f_sub = None`` -- the fraction is reported for the mode the solver
picked, which for this line is the quasi-TEM one.  Including the longitudinal
``e_z`` needs the mixed pencil and is not done here.
"""

from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np

from emfit import mode2d

C0 = 299792458.0

H_DEF = 1.6e-3
W_DEF = 8e-4
ER_DEF = 4.4
FREQ_DEF = 10.0096e9
TOL = 1e-9
HAMMERSTAD_BETA = 365.0
OUT_DEF = "/workspace/.scratch/d585/modal.json"


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def section(h, clearance, *, H=H_DEF, W=W_DEF, clearance_lateral=None):
    """Transverse box at cell ``h``: substrate + ``clearance * H`` of air.

    The substrate is ``H`` thick and is snapped to a whole number of cells
    (``nz_sub = round(H / h)``, then the cell is re-derived as ``H / nz_sub``,
    so the interface at ``y = H`` always falls on a mesh line -- the strip
    lives on it).  Air sits ``nz_air`` cells above; the lateral padding is
    ``ny_clean`` cells on each side of the ``W``-wide strip.
    """
    nz_sub = int(round(H / h))
    if nz_sub < 1:
        raise ValueError(f"h = {h:g} is coarser than the substrate H = {H:g}")
    cell = H / nz_sub
    clear_lat = clearance if clearance_lateral is None else clearance_lateral
    nz_air = int(round(clearance * H / cell))
    ny_strip = max(int(round(W / cell)), 1)
    ny_clean = int(round(clear_lat * H / cell))
    ny = ny_strip + 2 * ny_clean
    nz = nz_sub + nz_air
    ly, lz = ny * cell, nz * cell
    mesh = mode2d.box_mesh(ly, lz, ny, nz)
    return dict(
        mesh=mesh, h=h, cell=cell, h_ratio=H / cell, clearance=clearance,
        clearance_lateral=clear_lat, ny=ny, nz=nz, ny_strip=ny_strip,
        ny_clean=ny_clean, nz_sub=nz_sub, nz_air=nz_air, ly=ly, lz=lz,
        H=H, W=W, k0=2.0 * np.pi * FREQ_DEF / C0,
    )


def boxes(geo):
    """The boundary predicates of ``tools/modal_beta_probe.eigen``."""
    cell, ly, lz, H = geo["cell"], geo["ly"], geo["lz"], geo["H"]
    y0 = geo["ny_clean"] * cell
    y1 = (geo["ny_clean"] + geo["ny_strip"]) * cell
    ground = lambda p: p[:, 1] <= TOL                          # noqa: E731
    strip = lambda p: ((np.abs(p[:, 1] - H) <= TOL)            # noqa: E731
                       & (p[:, 0] >= y0 - TOL) & (p[:, 0] <= y1 + TOL))
    ymin = lambda p: p[:, 0] <= TOL                            # noqa: E731
    ymax = lambda p: p[:, 0] >= ly - TOL                       # noqa: E731
    top = lambda p: p[:, 1] >= lz - TOL                        # noqa: E731
    return {"open": (ground, strip),
            "pec_box": (ground, strip, ymin, ymax, top)}


def eps_fun(geo, er=ER_DEF):
    H = geo["H"]
    return lambda c: np.where(c[:, 1] <= H + TOL, er, 1.0)     # noqa: E731


# ---------------------------------------------------------------------------
# substrate transverse energy fraction (chosen mode only)
# ---------------------------------------------------------------------------
def f_sub_transverse(mesh, geo, e_t, *, er=ER_DEF):
    """``e^T M_eps,sub e / e^T M_eps e`` for one transverse eigenvector."""
    H = geo["H"]
    # assemble() returns (K_q, M_mu, M_eps): the eps masses are the THIRD block
    _, _, m_eps = mode2d.assemble(mesh, eps_r=eps_fun(geo, er))
    ind = lambda c: np.where(c[:, 1] <= H + TOL, er, 0.0)      # noqa: E731
    _, _, m_eps_sub = mode2d.assemble(mesh, eps_r=ind)
    num = float(e_t @ (m_eps_sub @ e_t))
    den = float(e_t @ (m_eps @ e_t))
    return (num / den) if den > 0.0 else None


# ---------------------------------------------------------------------------
# the two engines
# ---------------------------------------------------------------------------
def _header(geo, closure, engine, bounds, n_free_edge, n_free_node):
    return dict(
        engine=engine, closure=closure, h=geo["h"], cell=geo["cell"],
        clearance=geo["clearance"], clearance_lateral=geo["clearance_lateral"],
        ny=geo["ny"], nz=geo["nz"], ly=geo["ly"], lz=geo["lz"],
        h_ratio=geo["h_ratio"], k0=geo["k0"],
        n_free_edge=n_free_edge,
        n_free_node=n_free_node if n_free_node is not None else None,
        n_dof=n_free_edge + (n_free_node or 0),
        modes=[], status="ok",
    )


def _modes_from(mode, rec, f_sub_chosen, er):
    """Every candidate with ``beta_sq > 0`` and finite, one record each."""
    for i, (b_sq, e_eff) in enumerate(mode.candidates):
        b_sq = float(b_sq)
        if not np.isfinite(b_sq) or b_sq <= 0.0:
            continue
        rec["modes"].append(dict(
            index=i, beta=float(np.sqrt(b_sq)), beta_sq=b_sq,
            eps_eff=float(e_eff), curl_ratio=float(mode.curl_ratio[i]),
            residual=(float(mode.candidate_residuals[i])
                      if len(mode.candidate_residuals) > i else None),
            f_sub=(f_sub_chosen if (i == mode.chosen and f_sub_chosen is not None)
                   else None),
            is_builtin_pick=bool(i == mode.chosen),
            physical=bool(1.0 < e_eff < er),
            beta_over_hammerstad=float(np.sqrt(b_sq) / HAMMERSTAD_BETA),
        ))
    return rec


def solve_arpack(geo, closure, *, er=ER_DEF, k=6, max_dof=None,
                 shifts=(1.02, 1.06, 0.92)):
    """Sparse shift-invert engine: ``beta^2`` largest inside the physical band."""
    mesh, k0 = geo["mesh"], geo["k0"]
    bounds = boxes(geo)[closure]
    eps = eps_fun(geo, er)
    n_fe = int((~mode2d.pec_edge_mask(mesh, bounds)).sum())
    rec = _header(geo, closure, "arpack", bounds, n_fe, None)
    mode, err = None, None
    for mult in shifts:
        sigma = mult * k0 * k0 * er
        try:
            t0 = time.perf_counter()
            mode = mode2d.solve_modes(mesh, k0, sigma, eps_r=eps,
                                      boundaries=bounds, k=k)
            rec["wall_s"] = time.perf_counter() - t0
            rec["sigma_mult"] = mult
            rec["sigma"] = sigma
            break
        except Exception as exc:                             # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
    if mode is None:
        rec["status"] = f"arpack failed at every shift: {err}"
        return rec
    rec["n_candidates"] = len(mode.candidates)
    rec["chosen"] = int(mode.chosen)
    rec["beta_builtin_pick"] = float(mode.beta)
    rec["eps_eff_builtin_pick"] = float(mode.eps_eff)
    rec["residual_chosen"] = float(mode.residual)
    f_ch = f_sub_transverse(mesh, geo, np.real(mode.e_t), er=er)
    rec["f_sub_builtin_pick"] = f_ch
    return _modes_from(mode, rec, f_ch, er)


def solve_deflated(geo, closure, *, er=ER_DEF, k=6, max_dof=None,
                   region_widen=True, shifts=(1.02, 1.06, 0.92)):
    """Same pencil and shift ladder as :func:`solve_arpack`, gradient deflated.

    :func:`emfit.mode2d.solve_modes_deflated` removes the exact null space of
    the transverse curl from the candidate set, so the spurious
    ``beta^2 = k0^2 er`` modes that plain ARPACK returns are not candidates.

    ``region_widen=True`` (the default here) deflates every homogeneous
    contrast block -- the air block *and* the substrate interior -- which on
    this mesh is ``z_dim = 315`` columns against ``168`` for the air block
    alone; the air-only route leaves the substrate gradient modes in place and
    the six ARPACK candidates are unchanged.  ``--deflate-nowiden`` restores
    the air-only (``region_widen=False``) preregistered route.
    """
    mesh, k0 = geo["mesh"], geo["k0"]
    bounds = boxes(geo)[closure]
    eps = eps_fun(geo, er)
    n_fe = int((~mode2d.pec_edge_mask(mesh, bounds)).sum())
    rec = _header(geo, closure, "deflated", bounds, n_fe, None)
    mode, err = None, None
    for mult in shifts:
        sigma = mult * k0 * k0 * er
        try:
            t0 = time.perf_counter()
            mode = mode2d.solve_modes_deflated(
                mesh, k0, sigma, eps_r=eps, boundaries=bounds, k=k,
                region_widen=region_widen)
            rec["wall_s"] = time.perf_counter() - t0
            rec["sigma_mult"] = mult
            rec["sigma"] = sigma
            break
        except Exception as exc:                             # noqa: BLE001
            err = f"{type(exc).__name__}: {exc}"
    if mode is None:
        rec["status"] = f"deflated failed at every shift: {err}"
        return rec
    rec["region_widen"] = bool(region_widen)
    rec["n_candidates"] = len(mode.candidates)
    rec["chosen"] = int(mode.chosen)
    rec["beta_builtin_pick"] = float(mode.beta)
    rec["eps_eff_builtin_pick"] = float(mode.eps_eff)
    rec["residual_chosen"] = float(mode.residual)
    if mode.deflation:
        rec["deflation"] = {
            key: (val if isinstance(val, (int, float, str, bool, type(None)))
                  else str(val))
            for key, val in mode.deflation.items()}
    f_ch = f_sub_transverse(mesh, geo, np.real(mode.e_t), er=er)
    rec["f_sub_builtin_pick"] = f_ch
    return _modes_from(mode, rec, f_ch, er)


def solve_dense(geo, closure, *, er=ER_DEF, max_dof=1400):
    """The probe's dense mixed QZ -- validation only (O(n^3), dense ``B``)."""
    mesh, k0 = geo["mesh"], geo["k0"]
    bounds = boxes(geo)[closure]
    eps = eps_fun(geo, er)
    n_fe = int((~mode2d.pec_edge_mask(mesh, bounds)).sum())
    n_fn = int((~mode2d.pec_node_mask(mesh, bounds)).sum())
    rec = _header(geo, closure, "mixed_dense", bounds, n_fe, n_fn)
    if n_fe > max_dof:
        rec["status"] = (f"skipped: {n_fe} free edges exceed --max-dof={max_dof} "
                         f"(dense QZ)")
        return rec
    t0 = time.perf_counter()
    mode = mode2d.solve_modes_mixed(mesh, k0, sigma=1.0, eps_r=eps,
                                    boundaries=bounds, dense=True)
    rec["wall_s"] = time.perf_counter() - t0
    rec["n_candidates"] = len(mode.candidates)
    rec["chosen"] = int(mode.chosen)
    rec["beta_builtin_pick"] = float(mode.beta)
    rec["eps_eff_builtin_pick"] = float(mode.eps_eff)
    rec["residual_chosen"] = float(mode.residual)
    f_ch = f_sub_transverse(mesh, geo, np.real(mode.e_t), er=er)
    rec["f_sub_builtin_pick"] = f_ch
    return _modes_from(mode, rec, f_ch, er)


ENGINES = {"arpack": solve_arpack, "deflated": solve_deflated,
           "mixed_dense": solve_dense}

#: The engine used when ``--engine`` is not given.
ENGINE_DEF = "deflated"


def _solve(name, geo, closure, args):
    """Call engine ``name`` with the options that engine actually accepts."""
    kw = dict(er=args.er, max_dof=args.max_dof)
    if name != "mixed_dense":
        kw["k"] = args.k
    if name == "deflated":
        kw["region_widen"] = not args.deflate_nowiden
    return ENGINES[name](geo, closure, **kw)


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------
def print_block(rec):
    print(f"[{rec['engine']}/{rec['closure']}] h={rec['h']*1e3:g} mm "
          f"(H/h={rec['h_ratio']:g}) clearance={rec['clearance']:g}H/"
          f"{rec['clearance_lateral']:g}H ny x nz = {rec['ny']} x {rec['nz']} "
          f"free_edges={rec['n_free_edge']} dof={rec['n_dof']} "
          f"wall={rec.get('wall_s', float('nan')):.1f}s", flush=True)
    if rec["status"] != "ok":
        print(f"  {rec['status']}", flush=True)
        return
    print("  closure  idx     beta/m   eps_eff    f_sub  curl_ratio  "
          "residual  pick/phys", flush=True)
    for m in rec["modes"]:
        fs = "-" if m["f_sub"] is None else f"{m['f_sub']:.4f}"
        rsv = "-" if m.get("residual") is None else f"{m['residual']:9.3g}"
        print(f"  {rec['closure']:<7s} {m['index']:>3d}  {m['beta']:9.3f}  "
              f"{m['eps_eff']:8.4f}  {fs:>7s}  {m['curl_ratio']:10.3g}  "
              f"{rsv:>8s}  "
              f"{'*' if m['is_builtin_pick'] else ' '}"
              f"{'P' if m['physical'] else '.'}", flush=True)
    n_small = sum(1 for m in rec["modes"] if abs(m["curl_ratio"]) < 1e-3)
    tag = ""
    if rec.get("region_widen") is not None:
        tag = "  (region_widen=%s)" % rec["region_widen"]
    print(f"  -> {len(rec['modes'])} candidates, {n_small} with "
          f"|curl_ratio| < 1e-3{tag}", flush=True)


def flush(out, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, default=float)
        fh.flush()
        os.fsync(fh.fileno())


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------
def cmd_closures(args, out):
    name = args.engine or ENGINE_DEF
    print(f"# closures: identical box, both closures, engine={name} "
          f"(W/H={args.W/args.H:g}, er={args.er:g}, f={FREQ_DEF/1e9:g} GHz)",
          flush=True)
    geo = section(args.h, args.clearance, H=args.H, W=args.W,
                  clearance_lateral=args.clearance_lateral)
    for closure in ("open", "pec_box"):
        rec = _solve(name, geo, closure, args)
        out.append(rec)
        flush(out, args.out)
        print_block(rec)
    return out


def cmd_airsweep(args, out):
    name = args.engine or ENGINE_DEF
    print(f"# airsweep: closure=open, engine={name}, "
          f"h={args.h*1e3:g} mm, clearance in H", flush=True)
    prev = None
    for cl in [float(c) for c in args.clearances.split(",")]:
        geo = section(args.h, cl, H=args.H, W=args.W,
                      clearance_lateral=args.clearance_lateral)
        rec = _solve(name, geo, "open", args)
        qtem = _qtem(rec)
        b = None if qtem is None else qtem["beta"]
        rec["beta_qtem"] = b
        rec["rel_change_vs_prev"] = (None if (b is None or prev is None)
                                     else abs(b - prev) / abs(prev))
        out.append(rec)
        flush(out, args.out)
        print_block(rec)
        rc = rec["rel_change_vs_prev"]
        print(f"  -> quasi-TEM beta = "
              f"{'-' if b is None else f'{b:.4f}'} /m  rel_change = "
              f"{'-' if rc is None else f'{rc*100:.4f}%'}"
              f"{'   [< 0.1%: converged]' if (rc is not None and rc < 1e-3) else ''}",
              flush=True)
        prev = b
    return out


def cmd_refine(args, out):
    name = args.engine or ENGINE_DEF
    print(f"# refine: closure={args.closure}, engine={name}, "
          f"clearance={args.clearance:g}H, Hammerstad beta = "
          f"{HAMMERSTAD_BETA:g} /m", flush=True)
    pts = []
    for h in [float(v) for v in args.hs.split(",")]:
        geo = section(h, args.clearance, H=args.H, W=args.W,
                      clearance_lateral=args.clearance_lateral)
        rec = _solve(name, geo, args.closure, args)
        out.append(rec)
        flush(out, args.out)
        print_block(rec)
        qtem = _qtem(rec)
        if qtem is not None:
            pts.append((geo["cell"], qtem["beta"], geo["h_ratio"]))
    _report_order(pts, out, args)
    return out


def cmd_validate(args, out):
    """Named engine alone, or (no ``--engine``) ARPACK vs the dense mixed QZ."""
    geo = section(args.h, args.clearance, H=args.H, W=args.W,
                  clearance_lateral=args.clearance_lateral)
    names = ((args.engine,) if args.engine
             else ("mixed_dense", "arpack"))
    print(f"# validate: {', '.join(names)} on the SAME box, "
          f"h={args.h*1e3:g} mm, clearance={args.clearance:g}H, "
          f"closure={args.closure}", flush=True)
    rows = {}
    for engine in names:
        rec = _solve(engine, geo, args.closure, args)
        out.append(rec)
        flush(out, args.out)
        print_block(rec)
        rows[engine] = rec
    dense = [m for m in rows.get("mixed_dense", {"modes": []})["modes"]
             if m["physical"]]
    arp = [m for m in rows.get("arpack", {"modes": []})["modes"]
           if m["physical"]]
    print("  engine        bound  beta/m      eps_eff   f_sub", flush=True)
    for name in names:
        rec = rows[name]
        top = min(rec["modes"], key=lambda m: m["beta"]) if rec["modes"] else None
        s_beta = "-" if top is None else "%.3f" % top["beta"]
        s_eps = "-" if top is None else "%.4f" % top["eps_eff"]
        s_fs = "-" if (top is None or top["f_sub"] is None) else "%.4f" % top["f_sub"]
        print(f"  {name:<12s} {len(rec['modes']):>4d}  {s_beta:>9s}  "
              f"{s_eps:>8s}  {s_fs:>7s}", flush=True)
    if dense and arp:
        bd = min(dense, key=lambda m: m["beta"])["beta"]
        ba = min(arp, key=lambda m: m["beta"])["beta"]
        rel = abs(ba - bd) / abs(bd)
        agree = rel < 0.01
        print(f"  -> quasi-TEM: dense {bd:.3f} /m, arpack {ba:.3f} /m, "
              f"rel diff {rel*100:.3f}%  => "
              f"{'AGREE (<1%)' if agree else 'DISAGREE (>=1%)'}", flush=True)
        out.append(dict(kind="validate", beta_dense=bd, beta_arpack=ba,
                        rel_diff=rel, agree=bool(agree)))
        flush(out, args.out)
    return out


def _qtem(rec):
    """The quasi-TEM mode: smallest-beta mode inside the physical band."""
    cand = [m for m in rec["modes"] if m["physical"]]
    return min(cand, key=lambda m: m["beta"]) if cand else None


def _order_triple(c1, b1, c2, b2, c3, b3):
    """Order ``p`` and Richardson limit ``beta0`` from three cells.

    Fits ``beta(h) = beta0 + C h^p`` *exactly* through ``(c1, b1)``,
    ``(c2, b2)``, ``(c3, b3)``.  Eliminating ``beta0`` and ``C`` leaves the
    order as the root of

        f(p) = (b2 - b1) (c3^p - c1^p) - (b3 - b1) (c2^p - c1^p),

    bracketed on a grid and bisected -- no assumption that the three cells are
    geometrically spaced (they are not here: ``h = 0.128 mm`` snaps to
    ``H/12 = 0.1333 mm``).  ``beta0`` is then the Richardson extrapolation
    ``b1 - (b2 - b1) c1^p / (c2^p - c1^p)``.  Returns ``(p, beta0, C)``.
    """
    d12, d13 = b2 - b1, b3 - b1
    if d12 == 0.0 and d13 == 0.0:
        raise ValueError("all three betas are equal; p is not identifiable")

    def f(p):
        return d12 * (c3 ** p - c1 ** p) - d13 * (c2 ** p - c1 ** p)

    lo = hi = None
    for grid in (np.linspace(0.05, 12.0, 1200), np.linspace(-6.0, 0.05, 600)):
        vals = [f(float(p)) for p in grid]
        for i in range(len(grid) - 1):
            if (np.isfinite(vals[i]) and np.isfinite(vals[i + 1])
                    and vals[i] * vals[i + 1] < 0.0):
                lo, hi = float(grid[i]), float(grid[i + 1])
                break
        if lo is not None:
            break
    if lo is None:
        raise ValueError("no sign change of f(p); not a clean h^p sequence")
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(lo) * f(mid) <= 0.0:
            hi = mid
        else:
            lo = mid
    p = 0.5 * (lo + hi)
    c = d12 / (c2 ** p - c1 ** p)
    beta0 = b1 - c * c1 ** p
    return float(p), float(beta0), float(c)


def _report_order(pts, out, args):
    """Observed order p and Richardson limit beta0 from the three finest meshes."""
    if len(pts) < 3:
        print("  (need >= 3 meshes for a 3-point order)", flush=True)
        return
    print("  H/h     cell/mm    beta/m   vs Hammerstad", flush=True)
    for cell, beta, hr in pts:
        print(f"  {hr:5.2f}  {cell*1e3:8.5f}  {beta:9.4f}  "
              f"{beta-HAMMERSTAD_BETA:+8.4f}", flush=True)
    (c1, b1, r1), (c2, b2, r2), (c3, b3, r3) = pts[-3:]
    try:
        p, beta0, c = _order_triple(c1, b1, c2, b2, c3, b3)
    except ValueError as exc:
        rec = dict(kind="refine_order", status=f"failed: {exc}",
                   cell_1=c1, cell_2=c2, cell_3=c3, beta_1=b1, beta_2=b2,
                   beta_3=b3)
        out.append(rec)
        flush(out, args.out)
        print(f"  order-p fit failed: {exc}", flush=True)
        return
    rec = dict(kind="refine_order", status="ok",
               h_ratio_1=r1, h_ratio_2=r2, h_ratio_3=r3,
               cell_1=c1, cell_2=c2, cell_3=c3,
               beta_1=b1, beta_2=b2, beta_3=b3,
               order_p=p, beta_exact=beta0, C=c,
               beta_exact_minus_hammerstad=beta0 - HAMMERSTAD_BETA,
               beta_exact_over_hammerstad=beta0 / HAMMERSTAD_BETA,
               note="3-point fit beta0 + C h^p through the three finest "
                    "meshes (bisection on f(p), non-uniform cells allowed)")
    out.append(rec)
    flush(out, args.out)
    print(f"  triple H/h {r1:g}/{r2:g}/{r3:g}: p = {p:.4f}, C = {c:+.4g}, "
          f"beta0 = {beta0:.4f} /m ({beta0-HAMMERSTAD_BETA:+.4f} vs "
          f"Hammerstad {HAMMERSTAD_BETA:g}, "
          f"{100.0*(beta0/HAMMERSTAD_BETA - 1.0):+.3f}%)", flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--h", type=float, default=0.2e-3)
    common.add_argument("--clearance", type=float, default=3.0)
    common.add_argument("--clearance-lateral", type=float, default=None)
    common.add_argument("--er", type=float, default=ER_DEF)
    common.add_argument("--H", type=float, default=H_DEF)
    common.add_argument("--W", type=float, default=W_DEF)
    common.add_argument("--engine", default=None, choices=sorted(ENGINES),
                        help=f"solver engine (default: {ENGINE_DEF})")
    common.add_argument("--max-dof", type=int, default=1400,
                        help="dense-QZ budget on free edges (mixed_dense only)")
    common.add_argument("--k", type=int, default=6,
                        help="eigenpairs requested per shift (arpack/deflated)")
    common.add_argument("--deflate-nowiden", action="store_true",
                        help="deflated engine: air block only "
                             "(region_widen=False; restores the old route)")
    common.add_argument("--out", default=OUT_DEF)
    common.add_argument("--hs", default="0.2e-3,0.1333e-3,0.1e-3")
    common.add_argument("--clearances", default="1.0,2.0,3.0,4.0,6.0,8.0")
    common.add_argument("--closure", default="open")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("closures", "airsweep", "refine", "validate"):
        sub.add_parser(name, parents=[common])
    args = p.parse_args(argv)

    out = []
    {"closures": cmd_closures, "airsweep": cmd_airsweep, "refine": cmd_refine,
     "validate": cmd_validate}[args.cmd](args, out)

    flush(out, args.out)
    print(f"# wrote {len(out)} records -> {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
