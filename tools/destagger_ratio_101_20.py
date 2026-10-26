#!/usr/bin/env python3
"""destagger_ratio_101_20.py -- Falsifier #8: is the E_z/E_y power split a *staggering*
artefact?

READ-ONLY.  This script writes NO file: every input is opened ``rb``/read-only, its
sha256 is printed, and all results go to stdout.  It performs **no solve**, runs no
gate, and does not touch ``emfit/`` (the reconstruction is reproduced here
self-containedly instead of importing ``.scratch/logs/s10118_basis.py``, which is a
flat script that writes ``.scratch/s10118_result.txt`` as a side effect at module
level).

What is measured
----------------
For each of the three mixed-mode caches the placed mode is rebuilt exactly as
``s10118_basis.py:302-372`` / ``s10118_split_check.py:24-26`` did:

    e_y  on  (y_cell_centre x z_node)      = (200, 77)
    e_z  on  (y_node        x z_cell_centre) = (201, 76)

and the raw printed quantity is the ratio of unweighted sums of squares over two
*different* samplings -- ``sum(e_z^2) / sum(e_y^2)``.  On the 31x17 mesh that number
is the anchor 2722397.314568.  Two repairs are then applied, in order:

  1. UNIT REPAIR.  The 31x17 anchor carries a spurious ``* CELL`` on ``e_y``
     (``s10118_basis.py:314``), so it is larger than the physical ratio by
     ``1/CELL^2 = 1e8``.  Dividing that factor back out gives scheme A, 0.0272240 --
     the number the emfit study actually used.

  2. DE-STAGGERING.  Both components are moved onto one common grid, along two
     mutually exclusive routes, at three interpolation orders each:

        ROUTE-CC  -> cell centres (200, 76):  e_y along z  77 -> 76,  e_z along y 201 -> 200
        ROUTE-NN  -> vertices     (201, 77):  e_y along y 200 -> 201,  e_z along z  76 -> 77

     The three orders are the polynomial orders offered by scipy's
     ``RegularGridInterpolator``: ``linear`` (1), ``cubic`` (3), ``quintic`` (5).  The
     shortest source axis has 76 samples, so all three are usable.  Interpolation is
     applied to the *sampled arrays* (as specified), never by re-calling
     ``Mode2D.e_at``.  The grid is uniform with a half-cell shift, so the
     interpolation is a pure shift by 0.5*CELL.

     Two target grids are reported per route/method:
       ``full``   every target node.  On ROUTE-NN the two extreme lines of each axis
                  (y = 0, y = W; z = 0, z = H) lie half a cell *outside* the source span
                  and are therefore extrapolated -- the count and the weight of those
                  points are printed, never hidden.
       ``int``    same computation restricted to the nodes that lie inside both source
                  spans, i.e. strictly zero extrapolation.

  The comparison targets are scheme A = 0.0272240 (unit-repaired raw sum) and
  scheme C = 0.00951415 (mass-matrix quotient x_z^T M_zz x_z / (x_t^T M1 x_t)).

Usage:
    cd /workspace && python3 -u tools/destagger_ratio_101_20.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import emfit.mode2d as m2  # noqa: E402  (repo root put on sys.path for the package)

WS = "/workspace"
TOLFLUX = WS + "/.scratch/tol/logs/TOLFLUX.json"
CACHES = (
    ("31x17", WS + "/.scratch/s10118_mixed_mode.npz"),
    ("41x22", WS + "/.scratch/s10118_mode_41x22.npz"),
    ("51x19", WS + "/.scratch/s10118_mode_51x19.npz"),
)

ANCHOR = 2722397.314568          # printed by s10118_split_check.py on the 31x17 cache
SCHEME_A = 0.0272240             # unit-repaired raw sum (what the study used)
SCHEME_C = 0.00951415            # mass-matrix quotient
METHODS = ("linear", "cubic", "quintic")   # polynomial orders 1, 3, 5
MU0 = 4.0e-7 * np.pi
EPS0 = 8.8541878128e-12


def say(*a):
    print(*a, flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# inputs + sha256 (printed, and re-checked unchanged at the end: read-only proof)
# ---------------------------------------------------------------------------
PATHS = [TOLFLUX] + [p for _, p in CACHES]
say("=" * 100)
say("FALSIFIER #8 -- DE-STAGGERING OF THE E_z/E_y RATIO  (read-only: no solve, no gate, no file written)")
say("=" * 100)
say("inputs (sha256):")
H0 = {}
for p in PATHS:
    H0[p] = sha256(p)
    say(f"  {H0[p]}  {p}")

# ---------------------------------------------------------------------------
# geometry (single source of truth: the TOLFLUX run that fixed the fine grid)
# ---------------------------------------------------------------------------
with open(TOLFLUX) as fh:
    G = json.load(fh)["geometry"]
W, H, HSUB, WSTRIP = float(G["width"]), float(G["height"]), float(G["h"]), float(G["w"])
EPS_R = float(G["eps_r"])
NY, NZ, CELL = int(G["ny"]), int(G["nz"]), float(G["cell"])
NYN, NZN = NY + 1, NZ + 1
Y0, Y1 = W / 2.0 - WSTRIP / 2.0, W / 2.0 + WSTRIP / 2.0
assert (NYN, NZN) == (201, 77), (NYN, NZN)

yc_mid = (np.arange(NYN - 1) + 0.5) * CELL      # 200 transverse cell centres
zn_node = np.arange(NZN) * CELL                 # 77 vertical vertices
yn_node = np.arange(NYN) * CELL                 # 201 transverse vertices
zc_mid = (np.arange(NZN - 1) + 0.5) * CELL      # 76 vertical cell centres
yy, zz = np.meshgrid(yc_mid, zn_node, indexing="ij")     # e_y sampling points (200,77)
iyy, izz = np.meshgrid(yn_node, zc_mid, indexing="ij")   # e_z sampling points (201,76)

say("")
say("geometry  W=%.6g H=%.6g h=%.6g w=%.6g eps_r=%.6g  fine grid %dx%d CELL=%.6g"
    % (W, H, HSUB, WSTRIP, EPS_R, NY, NZ, CELL))
say("          Y0=%.6g Y1=%.6g   e_y grid (y_cell,z_node)=(%d,%d)   e_z grid (y_node,z_cell)=(%d,%d)"
    % (Y0, Y1, NYN - 1, NZN, NYN, NZN - 1))


# ---------------------------------------------------------------------------
# de-staggering helpers: pure axis-shift interpolation on the sampled arrays
# ---------------------------------------------------------------------------
def regrid(arr, axes, targets, method):
    """``arr`` sampled on ``axes`` (2 axes) -> resampled on ``targets``.

    ``fill_value=None`` + ``bounds_error=False``: scipy then *extrapolates* outside
    the source span instead of masking; the extrapolated nodes are counted and
    weighted by the caller, and a strictly-interior ratio is reported alongside.
    """
    itp = RegularGridInterpolator(tuple(axes), arr, method=method,
                                  bounds_error=False, fill_value=None)
    grids = np.meshgrid(*targets, indexing="ij")
    pts = np.stack([g.ravel() for g in grids], axis=1)
    return itp(pts).reshape(grids[0].shape)


def inside_mask(targets, axes):
    """True where the target node lies inside the source span of both axes."""
    my = (targets[0] >= axes[0][0]) & (targets[0] <= axes[0][-1])
    mz = (targets[1] >= axes[1][0]) & (targets[1] <= axes[1][-1])
    return my[:, None] & mz[None, :]


# ---------------------------------------------------------------------------
# per-mesh reconstruction
# ---------------------------------------------------------------------------
def reconstruct(path):
    d = np.load(path, allow_pickle=True)
    XS = np.asarray(d["xs"], dtype=float)
    ZS = np.asarray(d["zs"], dtype=float)
    nx, nz = int(XS.size), int(ZS.size)
    mesh = m2.structured_mesh(XS, ZS)
    if int(mesh.n_edges) != int(d["n_edges"]) or int(mesh.n_nodes) != nx * nz:
        raise SystemExit(f"mesh rebuild mismatch for {path}: "
                         f"edges {mesh.n_edges} vs {int(d['n_edges'])}")

    # node index must be j*nx + i for (XS[i], ZS[j]) -- the reshape below relies on it
    for (i, j) in ((0, 0), (nx - 1, 0), (5, 3), (nx - 1, nz - 1)):
        got = np.asarray(mesh.nodes[j * nx + i], dtype=float)
        if not np.array_equal(got, np.array([XS[i], ZS[j]], dtype=float)):
            raise SystemExit(f"node ordering guard failed for {path} at (i,j)=({i},{j})")

    MODE = m2.Mode2D(freq=float(d["freq"]), k0=float(d["k0"]), beta=float(d["beta"]),
                     beta_sq=float(d["beta_sq"]), eps_eff=float(d["eps_eff"]),
                     residual=float(d["residual"]),
                     candidates=np.asarray(d["candidates"]),
                     curl_ratio=float(np.asarray(d["curl_ratio_raw"]).ravel()[0]),
                     chosen=int(d["col"]), sigma=float(d["sigma"]),
                     n_dof=int(d["n_dof"]), n_pec=int(d["n_pec"]),
                     e_t=np.asarray(d["e_t"]), mesh=mesh,
                     e_z=np.asarray(d["e_z_solver"], dtype=float))

    # e_y at (y_cell_centre x z_node); the * CELL is the unit bug that made the anchor
    e_t_samp = MODE.e_at(np.stack([yy.ravel(), zz.ravel()], axis=1)).reshape(NYN - 1, NZN, 2)
    e_y_bug = e_t_samp[:, :, 0] * CELL
    e_y = e_t_samp[:, :, 0]                       # unit-repaired (scheme A) e_y

    # e_z at (y_node x z_cell_centre) from the nodal reconstruction, (nz,nx) layout
    ez_grid = np.asarray(d["e_z_node"], dtype=float).reshape(nz, nx)
    ez_itp = RegularGridInterpolator((ZS, XS), ez_grid, bounds_error=True)
    e_z = -ez_itp(np.stack([izz.ravel(), iyy.ravel()], axis=1)).reshape(NYN, NZN - 1)

    info = dict(mesh=path.rsplit("/", 1)[-1], xs=nx, zs=nz,
                n_edges=int(mesh.n_edges), n_nodes=int(mesh.n_nodes),
                col=int(d["col"]), beta=float(d["beta"]), eps_eff=float(d["eps_eff"]))
    return e_y, e_y_bug, e_z, info


# ---------------------------------------------------------------------------
# measure
# ---------------------------------------------------------------------------
rows = []          # one dict per (mesh, route, method)
per_mesh = []      # scheme-A style numbers per mesh
say("")
say("=" * 100)
say("A. RAW RECONSTRUCTION PER MESH (anchor reproduction + unit repair)")
say("=" * 100)
for tag, path in CACHES:
    e_y, e_y_bug, e_z, info = reconstruct(path)
    s_ez = float(np.sum(e_z ** 2))
    s_ey_bug = float(np.sum(e_y_bug ** 2))
    s_ey = float(np.sum(e_y ** 2))
    anchor = s_ez / s_ey_bug
    ratio_A = s_ez / s_ey
    n_y, n_z = float(e_y.size), float(e_z.size)
    ratio_mean = (s_ez / n_z) / (s_ey / n_y)
    per_mesh.append(dict(tag=tag, anchor=anchor, ratio_A=ratio_A, ratio_mean=ratio_mean))

    say("")
    say(f"mesh {tag}   ({info['n_edges']} edges, {info['n_nodes']} nodes, col {info['col']}, "
        f"beta {info['beta']:.8f})  cache {info['mesh']}")
    # the same ratio taken through the basis.py normalisation (one common scale
    # applied to e_y and e_z before summing); the scale cancels, but the rounding
    # of the multiplications is what a bit-for-bit reproduction has to match.
    eta_eff = float(np.sqrt(MU0 / (EPS0 * info["eps_eff"])))
    scale = 1.0 / np.sqrt(0.5 / eta_eff * (s_ey_bug + s_ez))
    anchor_scaled = float(np.sum((e_z * scale) ** 2) / np.sum((e_y_bug * scale) ** 2))
    same6 = (f"{anchor:.6f}" == f"{ANCHOR:.6f}")
    per_mesh[-1].update(anchor_scaled=anchor_scaled, anchor_same_6dp=same6)

    say(f"  sum(e_z^2)/sum(e_y^2)  RAW, e_y*CELL   = {anchor!r}")
    say(f"  same ratio after the basis.py normalisation (e_y,e_z both * scale) = {anchor_scaled!r}")
    if tag == "31x17":
        say(f"  ANCHOR CHECK  published {ANCHOR!r}:  reproduced to the published precision"
            f" (%.6f): {same6};  exact float equality: raw {anchor == ANCHOR},")
        say(f"                scaled {anchor_scaled == ANCHOR};  delta raw {anchor - ANCHOR:+.3e}"
            f" (rel {(anchor - ANCHOR) / ANCHOR:+.2e}), scaled {anchor_scaled - ANCHOR:+.3e}")
    say(f"  UNIT-REPAIRED (e_y/CELL)  sum ratio    = {ratio_A:.9f}"
        f"   (= scheme A target {SCHEME_A:.7f}, rel {ratio_A / SCHEME_A - 1:+.3e})")
    say(f"  count-normalised (ratio of means)      = {ratio_mean:.9f}"
        f"   (x{ratio_mean / ratio_A:.6f} vs the sum ratio: N_y/N_z = {n_y / n_z:.6f})")

    for route, (ty, tz) in (("CC", (yc_mid, zc_mid)), ("NN", (yn_node, zn_node))):
        say(f"  ROUTE-{route} -> {ty.size}x{tz.size} grid"
            f"  [e_y: {e_y.shape} -> {ty.size}x{tz.size}; e_z: {e_z.shape} -> {ty.size}x{tz.size}]")
        for method in METHODS:
            ey = regrid(e_y, (yc_mid, zn_node), (ty, tz), method)
            ez = regrid(e_z, (yn_node, zc_mid), (ty, tz), method)
            m_in = inside_mask((ty, tz), (yc_mid, zn_node)) & \
                   inside_mask((ty, tz), (yn_node, zc_mid))
            n_ext = int((~m_in).sum())
            r_full = float(np.sum(ez ** 2) / np.sum(ey ** 2))
            r_int = float(np.sum(ez[m_in] ** 2) / np.sum(ey[m_in] ** 2))
            w_ey = float(np.sum(ey[~m_in] ** 2) / np.sum(ey ** 2)) if n_ext else 0.0
            w_ez = float(np.sum(ez[~m_in] ** 2) / np.sum(ez ** 2)) if n_ext else 0.0
            rows.append(dict(mesh=tag, route=route, method=method, full=r_full, interior=r_int,
                             n_ext=n_ext, w_ey=w_ey, w_ez=w_ez))
            say(f"    {method:<9s} full = {r_full:.9f}   interior-only = {r_int:.9f}"
                f"   (extrapolated nodes {n_ext}"
                + (f", they carry {100 * w_ey:.3f}% of sum(e_y^2), {100 * w_ez:.3f}% of sum(e_z^2))"
                   if n_ext else ")"))

# ---------------------------------------------------------------------------
# spread across meshes / routes / orders
# ---------------------------------------------------------------------------
def stats(vals):
    v = np.asarray(vals, dtype=float)
    return dict(n=int(v.size), min=float(v.min()), max=float(v.max()),
                mean=float(v.mean()), spread_pct=float(100.0 * (v.max() - v.min()) / v.mean()),
                max_rel_pct=float(100.0 * (v.max() - v.min()) / v.min()))


say("")
say("=" * 100)
say("B. SPREAD ACROSS THE THREE MESHES, TWO ROUTES AND THREE ORDERS (18 numbers each)")
say("=" * 100)
S_full = stats([r["full"] for r in rows])
S_int = stats([r["interior"] for r in rows])
say(f"  de-staggered, FULL target grid  : n={S_full['n']}  min={S_full['min']:.9f}"
    f"  max={S_full['max']:.9f}  mean={S_full['mean']:.9f}"
    f"  spread={(S_full['max'] - S_full['min']) / S_full['mean'] * 100:.4f}% of mean"
    f" ({(S_full['max'] - S_full['min']) / S_full['min'] * 100:.4f}% of min)")
say(f"  de-staggered, INTERIOR only     : n={S_int['n']}  min={S_int['min']:.9f}"
    f"  max={S_int['max']:.9f}  mean={S_int['mean']:.9f}"
    f"  spread={(S_int['max'] - S_int['min']) / S_int['mean'] * 100:.4f}% of mean"
    f" ({(S_int['max'] - S_int['min']) / S_int['min'] * 100:.4f}% of min)")

day = [p["ratio_A"] for p in per_mesh]
say("  per-mesh unit-repaired (scheme A) ratios: "
    + ", ".join(f"{p['tag']}={p['ratio_A']:.9f}" for p in per_mesh)
    + f"   spread={100 * (max(day) - min(day)) / np.mean(day):.4f}% of mean")

say("")
say("  per-mesh / per-route / per-order table (full grid) :")
say("    mesh    route  " + "  ".join(f"{m:>12s}" for m in METHODS))
for tag, _ in CACHES:
    for route in ("CC", "NN"):
        cells = []
        for method in METHODS:
            r = next(r for r in rows if r["mesh"] == tag and r["route"] == route
                     and r["method"] == method)
            cells.append(f"{r['full']:12.9f}")
        say(f"    {tag:<7s} {route:<5s}  " + "  ".join(cells))

# ---------------------------------------------------------------------------
# verdict
# ---------------------------------------------------------------------------
mean_full = S_full["mean"]
moved = 100.0 * (mean_full / SCHEME_A - 1.0)
gap_C = mean_full / SCHEME_C
say("")
say("=" * 100)
say("C. VERDICT")
say("=" * 100)
say(f"  scheme A (unit-repaired raw sum, what the study used) = {SCHEME_A:.7f}")
say(f"  scheme C (mass-matrix quotient)                      = {SCHEME_C:.7f}   (= A / {SCHEME_A / SCHEME_C:.3f})")
say(f"  de-staggered mean ratio                              = {mean_full:.9f}")
say(f"  de-staggering moves the ratio by {moved:+.3f}% vs scheme A; "
    f"it is still {gap_C:.3f}x scheme C.")
say(f"  mesh/route/order spread (full grid) = "
    f"{(S_full['max'] - S_full['min']) / S_full['mean'] * 100:.4f}% of mean;"
    f" interior-only = {(S_int['max'] - S_int['min']) / S_int['mean'] * 100:.4f}% of mean.")

small_shift = abs(moved) < 10.0
far_from_C = gap_C > 2.0
if small_shift and far_from_C:
    say("  VERDICT: FALSIFIER #8 FAILS TO RESCUE SCHEME C.  Putting both components on one")
    say(f"           grid -- either grid, all three orders, all three meshes -- leaves the")
    say(f"           ratio at {mean_full:.6f} (+-{100 * (S_full['max'] - S_full['min']) / S_full['mean'] / 2:.3f}%), i.e. within "
        f"{abs(moved):.2f}% of the unit-repaired")
    say(f"           {SCHEME_A:.7f} and still {gap_C:.2f}x above the mass-matrix {SCHEME_C:.7f}.  The")
    say("           gap between A and C is therefore NOT a staggering artefact.")
else:
    say("  VERDICT: de-staggering MOVES the ratio materially (or into agreement with C):"
        f" moved {moved:+.3f}%, now {gap_C:.3f}x scheme C -- see the per-mesh table.")
say("")
say("  anchor 2722397.314568 on 31x17: reproduced to the published precision (%.6f): "
    f"{per_mesh[0]['anchor_same_6dp']}   (value {per_mesh[0]['anchor']!r}, scaled path "
    f"{per_mesh[0]['anchor_scaled']!r})")

H1 = {p: sha256(p) for p in PATHS}
say("  inputs unchanged after the run (sha256 identical): "
    f"{all(H0[p] == H1[p] for p in PATHS)}")

# machine-readable tail
say("")
say("JSON " + json.dumps(dict(
    anchor_31x17=per_mesh[0]["anchor"], anchor_31x17_scaled=per_mesh[0]["anchor_scaled"],
    anchor_matches_published_6dp=per_mesh[0]["anchor_same_6dp"],
    scheme_A=SCHEME_A, scheme_C=SCHEME_C,
    per_mesh={p["tag"]: dict(anchor=p["anchor"], ratio_A=p["ratio_A"],
                             ratio_mean=p["ratio_mean"]) for p in per_mesh},
    destag_full=S_full, destag_interior=S_int,
    moved_pct_vs_A=moved, ratio_to_C=gap_C,
    rows=[dict(mesh=r["mesh"], route=r["route"], method=r["method"],
               full=r["full"], interior=r["interior"], n_extrap=r["n_ext"]) for r in rows],
), sort_keys=True))
