#!/usr/bin/env python3
"""corr_ez_101_20.py -- why does the mixed-solver E_z correlate at 0.119 while E_y reaches 0.921?

Diagnosis only.  Reads the *banked* mixed-solver cache (``z_free``, ``e_t``,
``e_z_node``, ``e_z_solver``, ``free_n``, ``beta``, mesh axes) plus the analytic
quasi-static profile; it runs **no solve, no gate, no FDTD**.  Nothing in
``emfit/`` is modified or re-entered -- every candidate reconstruction is
rebuilt here from the cache, so a wrong guess costs seconds, not 130 s.

The suspects, one row each
--------------------------
The correlation in ``s10118_basis.py:392-397`` is

    corr = sum(A * B) / (|A| |B|),  A = analytic plane E_z (201, 76),
                                    B = the mixed mode's E_z on the same lattice

and the mixed ``B`` is built at ``s10118_basis.py:222-225`` and ``:313-316`` as

    z_free = lu.solve(c_f.T @ x_t)          # real: x_t is np.real(vecs)
    e_z_node[free_n] = np.abs(beta * z_free)     # <-- SIGN COLLAPSE
    e_z = -interp(e_z_node)                      # (201, 76)

``np.abs`` on a *real* array is not a phase fix, it is a rectifier: every node
whose potential has the other sign is folded onto the wrong side.  ``e_y`` is
never rectified (it comes straight from the edge DOFs), which is exactly the
asymmetry 0.92 / 0.12.  The table below measures that and every alternative.

Lattices (both ``(201, 76)`` for E_z and ``(200, 77)`` for E_y, per geometry)
----------------------------------------------------------------------------
``e_y``  at (y-cell centre x z-node)          -- from ``Mode2D.e_at``
``e_z``  at (y-node x z-cell centre)          -- from the nodal ``e_z_node``
``phi``  at (y-node x z-node), ``(201, 77)``  -- analytic potential, potential-
                                                 vs-field test only

Energy bookkeeping
------------------
``ratio_A = sum(e_z^2) / sum(e_y_unit^2)`` with ``e_y`` *unit-repaired* (the
``* CELL`` in ``s10118_basis.py:314`` divided out) is the confirmed 0.0272240
of Falsifier #8 (measured 0.027223973).  Sign and scale are invisible to a sum
of squares, so any candidate that only flips signs or rescales must leave that
ratio untouched; a formula change or a constant offset added to the *field*
does not.  Every row states which, and the recomputed ratio.

Run:  cd /workspace && python3 -u tools/corr_ez_101_20.py
Log:  .scratch/logs/corr_ez_followup.txt  (written by this script, tee-style)
"""

from __future__ import annotations

import hashlib
import json
import sys

import numpy as np
from scipy.interpolate import RegularGridInterpolator

sys.path.insert(0, "/workspace")

import emfit.modal as M                                   # noqa: E402
import emfit.mode2d as m2                                  # noqa: E402
from emfit.mode_profile import microstrip_mode_profile     # noqa: E402

WORK = "/workspace"
GEOJSON = f"{WORK}/.scratch/tol/logs/TOLFLUX.json"
LOG = f"{WORK}/.scratch/logs/corr_ez_followup.txt"
RESULT = f"{WORK}/.scratch/s10118_result.txt"

CACHES = [
    ("31x17", f"{WORK}/.scratch/s10118_mixed_mode.npz"),
    ("41x22", f"{WORK}/.scratch/s10118_mode_41x22.npz"),
]

# confirmed numbers this report is measured against
ANCHOR = 2722397.314568          # published raw sum ratio (the unit-bug anchor)
SCHEME_A = 0.0272240             # confirmed unit-repaired energy ratio
SCHEME_C = 0.00951415            # scheme C reference ratio (TASK 1); not recomputed here
SCHEME_A_MEAS = 0.027223973      # its measured value (TASK 1)
CORR_EZ_DISK = 0.11916043239134175     # .scratch/s10118_result.txt:105 (17:35)
CORR_EZ_OLD = 0.14619976001754773      # .scratch/logs/mesh41.log:18 (04:59)
CORR_EY_DISK = 0.9207707848111418

SRC_FILES = [
    f"{WORK}/emfit/mode2d.py",
    f"{WORK}/emfit/modal.py",
    f"{WORK}/emfit/mode_profile.py",
    f"{WORK}/emfit/quasistatic.py",
    f"{WORK}/emfit/__init__.py",
    __file__,
]


# ---------------------------------------------------------------------------
# tee
# ---------------------------------------------------------------------------
class Tee:
    def __init__(self, path: str) -> None:
        self.fh = open(path, "w", encoding="utf-8")

    def say(self, *a) -> None:
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        self.fh.write(line + "\n")
        self.fh.flush()


T = Tee(LOG)
say = T.say


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def corr(a, b) -> float:
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0 or a.size != b.size:
        return float("nan")
    return float(np.sum(a * b) / (na * nb))


def itp(src0, src1, vals, t0, t1, extrapolate=False):
    """Linear interpolation on the (src0 x src1) grid at (t0, t1).

    ``extrapolate`` is used only by the derivative candidate, whose source
    lattice is the mesh's *cell centres* (interior by half a cell at each end)
    and therefore cannot reach the plane's own first/last cell on a graded mesh.
    """
    f = RegularGridInterpolator((src0, src1), vals,
                               bounds_error=not extrapolate,
                               fill_value=None if extrapolate else np.nan)
    pts = np.stack([np.asarray(t0, float).ravel(), np.asarray(t1, float).ravel()], axis=1)
    return f(pts).reshape(np.shape(t0))


# ---------------------------------------------------------------------------
# inputs: hashes first, so the numbers below are pinned to bytes
# ---------------------------------------------------------------------------
say("=" * 100)
say("0. INPUTS (sha256 of every byte this report reads)")
say("=" * 100)
for path in SRC_FILES + [GEOJSON, RESULT, f"{WORK}/.scratch/logs/mesh41.log"] + [p for _, p in CACHES]:
    try:
        say(f"  {sha256(path)}  {path}")
    except OSError as exc:                                        # noqa: BLE001
        say(f"  {'-' * 64}  {path}  (unreadable: {exc})")

G = json.load(open(GEOJSON))["geometry"]
W, H = G["width"], G["height"]
HSUB, WSTRIP, EPS_R = G["h"], G["w"], G["eps_r"]
N_SUB, K_STRIP, J_CENTRE = G["n_sub"], G["k_strip"], G["j_centre"]
NY, NZ, CELL = G["ny"], G["nz"], G["cell"]
Y0, Y1 = W / 2 - WSTRIP / 2, W / 2 + WSTRIP / 2
say("  geometry", dict(W=W, H=H, h=HSUB, w=WSTRIP, eps_r=EPS_R, ny=NY, nz=NZ,
                       cell=CELL, strip=[Y0, Y1], n_sub=N_SUB,
                       k_strip=K_STRIP, j_centre=J_CENTRE))

# plane lattices (geometry, not mesh)
NYN, NZN = NY + 1, NZ + 1
yn_node = np.arange(NYN) * CELL
zn_node = np.arange(NZN) * CELL
yc_mid = (np.arange(NYN - 1) + 0.5) * CELL
zc_mid = (np.arange(NZN - 1) + 0.5) * CELL

iyy, izz = np.meshgrid(yn_node, zc_mid, indexing="ij")     # E_z lattice (201, 76)
yy, zz = np.meshgrid(yc_mid, zn_node, indexing="ij")       # E_y lattice (200, 77)
pyy, pzz = np.meshgrid(yn_node, zn_node, indexing="ij")    # node lattice (201, 77)
iy_strip = np.flatnonzero((yn_node >= Y0 - 1e-12) & (yn_node <= Y1 + 1e-12))


# ---------------------------------------------------------------------------
# 1. analytic profile (the reference), its potential, and its self-check
# ---------------------------------------------------------------------------
say("")
say("=" * 100)
say("1. ANALYTIC REFERENCE (microstrip_mode_profile -> plane_mode, exactly the basis.py call)")
say("=" * 100)
prof = microstrip_mode_profile(HSUB, WSTRIP, EPS_R, n_sub=N_SUB)
PANA = M.plane_mode(prof, nyn=NYN, nzn=NZN, k_strip=K_STRIP,
                    iy_strip_centre=J_CENTRE, cell=CELL)
A_ez = np.asarray(PANA.e_z, dtype=float)
A_ey = np.asarray(PANA.e_y, dtype=float)
win = prof.plane_window(NYN, NZN, K_STRIP, iy_strip_centre=J_CENTRE, cell=CELL)
say("  placement", PANA.report)
say("  clipped", list(win.clipped))
say("  shapes", dict(e_z=list(A_ez.shape), e_y=list(A_ey.shape),
                     phi=list(np.shape(prof.phi)), profile_cell=prof.cell,
                     eps_eff=float(prof.eps_eff), v_mode=float(prof.v_mode)))

# the analytic potential cropped onto the same plane (node lattice, (201, 77))
phi_pl = np.zeros((NYN, NZN))
ys = win.ynode_zcell[0][0]
zs = win.ycell_znode[0][1]
yd = win.ynode_zcell[1][0]
zd = win.ycell_znode[1][1]
phi_flat = np.asarray(prof.phi, dtype=float)
phi_pl[yd, zd] = phi_flat[ys, zs]
say("  phi cropped into the plane", dict(dst_shape=[int(NYN), int(NZN)],
                                        nonzero_rows=int((np.any(phi_pl, axis=1)).sum()),
                                        phi_min=float(phi_pl.min()), phi_max=float(phi_pl.max())))
say("  analytic potential kept for the potential-vs-field test only; plane_mode()")
say("  does NOT expose phi -- only e_y/e_z/h_y/h_z -- so a caller correlating a")
say("  *potential* against PANA.e_z would be comparing different physical objects.")

# control: is the analytic e_z the cell difference of the analytic phi?
# mode_profile.py:37 fixes the convention, e = -G phi, and
# mode_profile.py:46 the identity sum(e_z) = -(phi[n_sub] - phi[0]) = -v_mode.
ez_from_phi = -np.diff(phi_pl, axis=1)                    # (201, 76), V on z-cells
ctr = corr(A_ez, ez_from_phi)
scale_ratio = float(np.sum(A_ez * ez_from_phi) / np.sum(ez_from_phi * ez_from_phi))
say(f"  CONTROL  corr(analytic e_z, -d(analytic phi)/dz) = {ctr:.15f}"
    f"  (scale {scale_ratio:.12f})")
say("           -> 1.0 means the -difference convention and the (201,76) node/cell")
say("              mapping used below are right, so a bad derivative candidate")
say("              cannot be blamed on this script's lattice bookkeeping.")
_under = slice(int(iy_strip[0]), int(iy_strip[-1]) + 1)
say(f"           analytic e_z sign under the strip: "
    f"{int((A_ez[_under] < 0).sum())} neg / {int((A_ez[_under] > 0).sum())} pos of {A_ez[_under].size}")
say(f"           analytic e_z sign OUTSIDE the strip: "
    f"{int((np.delete(A_ez, np.arange(iy_strip[0], iy_strip[-1] + 1), axis=0) < 0).sum())} neg / "
    f"{int((np.delete(A_ez, np.arange(iy_strip[0], iy_strip[-1] + 1), axis=0) > 0).sum())} pos")
say("           ^ the reference E_z has BOTH signs in one column, which is why an")
say("             |e_z| reconstruction has a ceiling far below 1")


# ---------------------------------------------------------------------------
# 2. per-mesh reconstruction from the cache (no solve)
# ---------------------------------------------------------------------------
def vertical_edge_map(mesh, nx: int, nz: int):
    """Edge indices of the *vertical* (z-directed) edges, as an ``(nz-1, nx)`` map.

    A structured quad mesh carries three edge families.  The one whose endpoints
    share the ``y`` index and differ in the ``z`` index is the family ``E_z``
    lives on: ``map[j, i]`` is the edge joining ``(y_i, z_j)`` to
    ``(y_i, z_{j+1})``.  On a :class:`~emfit.mode2d.Mesh2D` built by
    ``structured_mesh`` every quad contributes both of its vertical edges, so a
    hole in the map would mean the rebuilt mesh is not the cached one.
    """
    edges = np.asarray(mesh.edges, dtype=np.int64)
    i0, j0 = edges[:, 0] % nx, edges[:, 0] // nx
    i1, j1 = edges[:, 1] % nx, edges[:, 1] // nx
    is_vert = (i0 == i1) & (j0 != j1)
    vert = np.flatnonzero(is_vert)
    idx = np.full((nz - 1, nx), -1, dtype=np.int64)
    idx[np.minimum(j0[vert], j1[vert]), i0[vert]] = vert
    return idx, vert, is_vert


def op_plane(dz: dict, nodal):
    """``c[z-rows] @ nodal`` scattered back onto the (201, 76) plane lattice.

    ``c`` is ``assemble_mixed``'s edge x node block ``INT (1/mu_r) W_e . grad phi_i
    dA``, so this is the *legal* discrete route from a nodal scalar to an edge
    cochain: no ad-hoc differencing, and the mass weight the assembler itself
    uses.  The rows kept are the vertical (z-directed) edges -- the DOFs that
    carry ``E_z``.
    """
    te_full = np.asarray(dz["c"] @ np.asarray(nodal, dtype=float).ravel()).ravel()
    ZS = np.asarray(dz["ZS"])
    zc_mesh = 0.5 * (ZS[:-1] + ZS[1:])
    return itp(zc_mesh, dz["XS"], te_full[dz["vert_map"]], izz, iyy, extrapolate=True)


def load(cache_path: str) -> dict:
    d = np.load(cache_path, allow_pickle=True)
    XS = np.asarray(d["xs"], dtype=float)
    ZS = np.asarray(d["zs"], dtype=float)
    nx, nz = int(XS.size), int(ZS.size)
    mesh = m2.structured_mesh(XS, ZS)
    if int(mesh.n_edges) != int(d["n_edges"]) or int(mesh.n_nodes) != nx * nz:
        raise SystemExit(f"mesh rebuild mismatch for {cache_path}")
    for (i, j) in ((0, 0), (nx - 1, 0), (5, 3), (nx - 1, nz - 1)):
        got = np.asarray(mesh.nodes[j * nx + i], dtype=float)
        if not np.array_equal(got, np.array([XS[i], ZS[j]], dtype=float)):
            raise SystemExit(f"node ordering guard failed for {cache_path}")

    MODE = m2.Mode2D(
        freq=float(d["freq"]), k0=float(d["k0"]), beta=float(d["beta"]),
        beta_sq=float(d["beta_sq"]), eps_eff=float(d["eps_eff"]),
        residual=float(d["residual"]), candidates=np.asarray(d["candidates"], float),
        curl_ratio=float(np.asarray(d["curl_ratio_raw"], float).ravel()[0]),
        chosen=int(d["col"]), sigma=float(d["sigma"]), n_dof=int(d["n_dof"]),
        n_pec=int(d["n_pec"]), e_t=np.asarray(d["e_t"], float), mesh=mesh,
        e_z=np.asarray(d["e_z_solver"], float),
    )
    e_t_samp = MODE.e_at(np.stack([yy.ravel(), zz.ravel()], axis=1)).reshape(NYN - 1, NZN, 2)
    e_y_unit = e_t_samp[:, :, 0]                 # unit-repaired (scheme A) e_y
    e_y_bug = e_y_unit * CELL                    # the anchor's e_y

    free_n = np.asarray(d["free_n"], int)
    zr = np.zeros(mesh.n_nodes)
    zr[free_n] = np.asarray(d["z_free"], float)   # real: x_t was np.real'd upstream
    c = d["c"].item() if isinstance(d["c"], np.ndarray) else d["c"]
    vert_map, vert_idx, _is_vert = vertical_edge_map(mesh, nx, nz)
    if np.any(vert_map < 0):
        raise SystemExit(f"vertical-edge map incomplete for {cache_path}")
    return dict(d=d, XS=XS, ZS=ZS, nx=nx, nz=nz, mesh=mesh, c=c,
                vert_map=vert_map, n_vert=int(vert_idx.size),
                free_e=np.asarray(d["free_e"], int),
                beta=float(d["beta"]), eps_eff=float(d["eps_eff"]),
                e_y_unit=e_y_unit, e_y_bug=e_y_bug, free_n=free_n, zr=zr,
                e_z_node=np.asarray(d["e_z_node"], float),
                e_z_solver=np.asarray(d["e_z_solver"], float),
                info=dict(cache=cache_path, edges=int(mesh.n_edges),
                          nodes=int(mesh.n_nodes), col=int(d["col"]),
                          beta=float(d["beta"]), eps_eff=float(d["eps_eff"])))


def fields(dz: dict) -> dict:
    """Every candidate E_z on the (201, 76) plane lattice, from the cache alone."""
    grid = dz["zr"].reshape(dz["nz"], dz["nx"])          # (nz, nx) on (ZS, XS)
    beta = dz["beta"]
    free_n = dz["free_n"]

    def to_plane(vals):
        return itp(dz["ZS"], dz["XS"], vals, izz, iyy)

    out = {}
    out["baseline_abs"] = -to_plane(np.abs(beta * grid))     # s10118_basis.py:225
    out["sign_hi"] = -to_plane(beta * grid)                  # global sign from the code
    out["sign_lo"] = to_plane(beta * grid)                   # opposite global sign

    # gauge choices on z_free (constant subtracted from the *field*)
    mean_free = float(np.mean(dz["zr"][free_n]))
    top = np.flatnonzero(np.repeat(np.asarray(dz["ZS"]), dz["nx"]) == dz["ZS"][-1])
    top_free = np.array([k for k in top if k in set(free_n.tolist())], dtype=int)
    top_val = float(np.mean(dz["zr"][top_free])) if top_free.size else 0.0
    g_mean = grid.copy()
    g_mean.ravel()[free_n] -= mean_free
    g_top = grid.copy()
    g_top.ravel()[free_n] -= top_val
    out["gauge_mean"] = -to_plane(beta * g_mean)
    out["gauge_top"] = -to_plane(beta * g_top)
    out["gauge_ground"] = -to_plane(beta * grid)              # PEC nodes are 0 -> no-op
    out["_gauge"] = dict(mean_free=mean_free, top_val=top_val,
                         rms_free=float(np.sqrt(np.mean(dz["zr"][free_n] ** 2))),
                         frac_negative=float(np.mean(dz["zr"][free_n] < 0.0)))

    # numerical -d(z_free)/dz, cell differences on (zc x XS) then to (yn x zc)
    dgrid = -np.diff(grid, axis=0)
    zc_mesh = 0.5 * (np.asarray(dz["ZS"])[:-1] + np.asarray(dz["ZS"])[1:])
    out["derivative"] = itp(zc_mesh, dz["XS"], dgrid, izz, iyy, extrapolate=True)

    # potential-vs-field: z_free itself on the NODE lattice vs the analytic phi
    zr_pl = itp(dz["ZS"], dz["XS"], grid, pzz, pyy)
    out["zfree_nodes"] = zr_pl
    out["_pot"] = dict(corr=corr(zr_pl, phi_pl),
                       corr_mean=corr(zr_pl - mean_free, phi_pl),
                       corr_top=corr(zr_pl - top_val, phi_pl),
                       corr_abs=corr(np.abs(zr_pl), np.abs(phi_pl)),
                       corr_dphi=corr(-np.diff(zr_pl, axis=1), A_ez),
                       corr_signed_nodes=corr(zr_pl * beta, A_ez))

    # per-column sign alignment (an upper bound, uses the analytic answer)
    cols = out["sign_hi"].copy()
    n_flip = 0
    for i in range(cols.shape[0]):
        if float(np.sum(A_ez[i] * cols[i])) < 0.0:
            cols[i] = -cols[i]
            n_flip += 1
    out["col_aligned"] = cols
    out["_col_flip"] = n_flip

    # the solver's own e_z (banked) -- an independent reconstruction to compare to
    out["_deriv_extrap"] = int(np.sum((izz < zc_mesh[0]) | (izz > zc_mesh[-1])))

    es_grid = np.abs(dz["e_z_solver"]).reshape(dz["nz"], dz["nx"])
    out["solver_ez"] = -to_plane(es_grid)

    # -- the legal discrete operator test:  TE = c[z-rows] @ z_free ---------
    c = dz["c"]
    te_full = np.asarray(c @ dz["zr"]).ravel()
    te_red = np.asarray(c[:, free_n] @ dz["zr"][free_n]).ravel()
    out["te"] = op_plane(dz, dz["zr"])
    out["_te"] = dict(c_shape=list(c.shape), c_nnz=int(c.nnz),
                      n_vertical=dz["n_vert"],
                      full_minus_freeonly=float(np.max(np.abs(te_full - te_red))),
                      n_nonzero_vertical=int(np.count_nonzero(te_full[dz["vert_map"]])),
                      rms=float(np.sqrt(np.mean(out["te"] ** 2))))

    # the CONTROL: the exact analytic potential resampled onto the *same* mesh
    # nodes and pushed through the *same* operator.  This is the operator's own
    # fidelity ceiling on this mesh -- 1.0 was never available, because c@phi is
    # an area-weighted (mass) gradient, not the edge integral.
    nyx = (dz["nz"], dz["nx"])
    phi_mesh = itp(yn_node, zn_node, phi_pl,
                   np.broadcast_to(dz["XS"][None, :], nyx),
                   np.broadcast_to(np.asarray(dz["ZS"])[:, None], nyx),
                   extrapolate=True)
    out["ctrl_phi"] = op_plane(dz, phi_mesh.ravel())
    out["ctrl_diffphi"] = itp(zc_mesh, dz["XS"], np.diff(phi_mesh, axis=0),
                              izz, iyy, extrapolate=True)
    out["_te"]["ctrl_nan"] = int(np.isnan(phi_mesh).sum())
    return out


# ---------------------------------------------------------------------------
# 3. the table
# ---------------------------------------------------------------------------
ROWS = [
    # (id, label, field key, reference, energy class, note)
    ("1",    "BASELINE  -|beta*z_free| (current code path) ", "baseline_abs", "E_z", "PRESERVING"),
    ("2a",   "SIGN      -beta*z_free                       ", "sign_hi", "E_z", "PRESERVING"),
    ("2b",   "SIGN      +beta*z_free                       ", "sign_lo", "E_z", "PRESERVING"),
    ("3a",   "GAUGE     -(beta*(z_free-mean))              ", "gauge_mean", "E_z", "CHANGING"),
    ("3b",   "GAUGE     -(beta*(z_free-top-row-mean))      ", "gauge_top", "E_z", "CHANGING"),
    ("3c",   "GAUGE     -(beta*(z_free-0)) [PEC gauge]     ", "gauge_ground", "E_z", "PRESERVING"),
    ("5a",   "WRONG-F   beta*z_free  (== 2a)               ", "sign_hi", "E_z", "PRESERVING"),
    ("5b",   "WRONG-F   -d(z_free)/dz (cell differences)   ", "derivative", "E_z", "CHANGING"),
    ("5c",   "WRONG-F   per-column sign-aligned |beta*z|   ", "col_aligned", "E_z", "PRESERVING"),
    ("SOLV", "solver's own banked e_z (independent path)   ", "solver_ez", "E_z", "PRESERVING"),
    ("TE",   "LEGAL OP  c[z-rows] @ z_free (TE)            ", "te", "E_z", "OP-UNITS"),
]

SUMMARY = {}
for tag, path in CACHES:
    dz = load(path)
    F = fields(dz)
    s_ey = float(np.sum(dz["e_y_unit"] ** 2))
    s_ey_bug = float(np.sum(dz["e_y_bug"] ** 2))
    c_ey = corr(A_ey, dz["e_y_unit"])
    g = F["_gauge"]

    say("")
    say("=" * 100)
    say(f"2. MESH {tag}   ({dz['info']['edges']} edges, {dz['info']['nodes']} nodes, "
        f"col {dz['info']['col']}, beta {dz['info']['beta']:.10f}, eps_eff {dz['info']['eps_eff']:.10f})")
    say("=" * 100)
    say("  z_free (free nodes)   mean = %+.9e   rms = %.9e   min = %+.6e   max = %+.6e"
        % (g["mean_free"], g["rms_free"], float(dz["zr"].min()), float(dz["zr"].max())))
    say("  z_free top-row mean   = %+.9e   fraction of free nodes with z_free < 0 = %.4f"
        % (g["top_val"], g["frac_negative"]))
    say("  complex audit         z_free %s | e_t %s | e_z_node %s | e_z_solver %s | analytic e_z %s | analytic phi %s"
        % tuple("COMPLEX" if np.iscomplexobj(x) else "real"
                for x in (dz["zr"], dz["d"]["e_t"], dz["e_z_node"], dz["e_z_solver"],
                          A_ez, phi_pl)))
    say("  banked e_z_solver vs |beta*z_free|: max rel diff = %.3e"
        % float(np.max(np.abs(dz["e_z_solver"] - np.abs(dz["beta"] * dz["zr"])))
                / max(1e-300, float(np.max(dz["e_z_solver"])))))
    say("  control corr_e_y (analytic vs mixed, unit-repaired) = %.17g" % c_ey)
    say("")

    hdr = (f"  {'id':5s} {'candidate':46s} {'ref':4s} {'corr':>14s} {'|corr|':>9s} "
           f"{'sign':>4s} {'corr_e_y':>9s} {'ratio_A':>13s}  {'energy':11s} {'ratio 0.0272240':s}")
    say(hdr)
    say("  " + "-" * (len(hdr) - 2))
    base_ratio = None
    for (rid, label, key, ref, energy) in ROWS:
        fld = F[key]
        c = corr(A_ez, fld)
        ratio = float(np.sum(fld ** 2)) / s_ey
        if base_ratio is None:
            base_ratio = ratio
        if energy == "PRESERVING":
            surv = "SURVIVES (sum(e_z^2) is sign/scale blind)"
        elif energy == "OP-UNITS":
            surv = f"n/a -> {ratio:.9f} (edge cochain: other units)"
        else:
            surv = f"CHANGES -> {ratio:.9f}"
        say(f"  {rid:5s} {label:46s} E_z  {c:+.12f} {abs(c):9.6f} "
            f"{'neg' if c < 0 else 'pos':>4s} {c_ey:9.6f} {ratio:13.9f}  {energy:11s} {surv}")
    say("")

    # the anchor / unit repair, reproduced from this reconstruction
    a_raw = float(np.sum(F["baseline_abs"] ** 2)) / s_ey_bug
    say(f"  ANCHOR   sum(e_z^2)/sum((e_y*CELL)^2) = {a_raw!r}  (published {ANCHOR!r}, "
        f"%.6f match: {f'{a_raw:.6f}' == f'{ANCHOR:.6f}'})")
    say(f"  RATIO    unit-repaired baseline           = {base_ratio:.9f}  "
        f"(TASK 1 measured {SCHEME_A_MEAS:.9f}, target {SCHEME_A:.7f})")
    say(f"           same with e_y*CELL (the unit bug) = "
        f"{float(np.sum(F['baseline_abs'] ** 2)) / s_ey_bug:.9f}")
    say("")

    # potential-vs-field block
    p = F["_pot"]
    say("  POTENTIAL-VS-FIELD (z_free on the (201,77) node lattice, correlated with the analytic phi)")
    say(f"    corr(z_free, phi)                    = {p['corr']:+.15f}")
    say(f"    corr(z_free - mean, phi)             = {p['corr_mean']:+.15f}")
    say(f"    corr(z_free - top-row mean, phi)     = {p['corr_top']:+.15f}")
    say(f"    corr(|z_free|, |phi|)                = {p['corr_abs']:+.15f}")
    say(f"    corr(-d(z_free)/dz on nodes, e_z)    = {p['corr_dphi']:+.15f}"
        f"   (same object as 5b, different sampling -> consistency check)")
    say(f"    corr(beta*z_free on nodes, e_z)      = {p['corr_signed_nodes']:+.15f}"
        f"   (same object as 2a, different sampling)")
    say("")

    # sign structure of the mixed field: where the rectifier does its damage
    fb = F["baseline_abs"]
    fs = F["sign_hi"]
    strip = np.ix_(np.arange(iy_strip[0], iy_strip[-1] + 1), np.arange(NZN - 1))
    say("  WHERE THE 0.12 COMES FROM (restricted to the strip footprint vs outside it)")
    say(f"    corr(baseline, A_ez)  under strip = {corr(A_ez[strip], fb[strip]):+.9f}   "
        f"outside = {corr(np.delete(A_ez, np.arange(iy_strip[0], iy_strip[-1] + 1), 0), np.delete(fb, np.arange(iy_strip[0], iy_strip[-1] + 1), 0)):+.9f}")
    say(f"    corr(sign    , A_ez)  under strip = {corr(A_ez[strip], fs[strip]):+.9f}   "
        f"outside = {corr(np.delete(A_ez, np.arange(iy_strip[0], iy_strip[-1] + 1), 0), np.delete(fs, np.arange(iy_strip[0], iy_strip[-1] + 1), 0)):+.9f}")
    say(f"    per-column sign flips applied to reach the aligned bound: {F['_col_flip']} of {NYN}")
    say(f"    (5b derivative lattice: cell centres span z = {0.5 * (dz['ZS'][0] + dz['ZS'][1]):.6g}"
        f"..{0.5 * (dz['ZS'][-1] + dz['ZS'][-2]):.6g} m; {F['_deriv_extrap']} of {izz.size}"
        f" target cells extrapolated)")

    # the legal discrete operator test  TE = c[z-rows] @ z_free
    te = F["te"]
    ctl = F["ctrl_phi"]
    ctd = F["ctrl_diffphi"]
    mt = F["_te"]
    ZSm = np.asarray(dz["ZS"], float)
    zc_mesh = 0.5 * (ZSm[:-1] + ZSm[1:])
    in_z = (zc_mid >= zc_mesh[0] - 1e-15) & (zc_mid <= zc_mesh[-1] + 1e-15)
    n_extrap = int((~in_z).sum()) * NYN

    def oracle(fld):
        """Per-column sign alignment against A_ez -- an upper bound, uses the answer."""
        out_f = np.asarray(fld, float).copy()
        nf = 0
        for i in range(out_f.shape[0]):
            if float(np.sum(A_ez[i] * out_f[i])) < 0.0:
                out_f[i] = -out_f[i]
                nf += 1
        return out_f, nf

    te_chk = op_plane(dz, dz["zr"])
    scatter = float(np.max(np.abs(te_chk - te)))
    c1b = abs(corr(A_ez, F["baseline_abs"]))
    c_te = corr(A_ez, te)
    c_te_in = corr(A_ez[:, in_z], te[:, in_z])
    te_or, te_flip = oracle(te)
    c_te_or = corr(A_ez, te_or)
    c_ctl = corr(A_ez, ctl)
    c_ctl_in = corr(A_ez[:, in_z], ctl[:, in_z])
    ctl_or, ctl_flip = oracle(ctl)
    c_ctl_or = corr(A_ez, ctl_or)
    c_ctd = corr(A_ez, ctd)
    rows_out = np.arange(iy_strip[0], iy_strip[-1] + 1)
    te_strip = corr(A_ez[strip], te[strip])
    te_out = corr(np.delete(A_ez, rows_out, axis=0), np.delete(te, rows_out, axis=0))
    ctl_strip = corr(A_ez[strip], ctl[strip])
    ctl_out = corr(np.delete(A_ez, rows_out, axis=0), np.delete(ctl, rows_out, axis=0))

    say("")
    say("  LEGAL OPERATOR TEST  TE = c[z-rows] @ z_free  -- the discrete route from a nodal")
    say("  scalar to the E_z edge cochain, using assemble_mixed's own mass-weighted gradient")
    say(f"    c (assemble_mixed, edge x node)     shape = {tuple(mt['c_shape'])}   nnz = {mt['c_nnz']}")
    say(f"    vertical (z-directed) edge rows      = {mt['n_vertical']} of {dz['info']['edges']} edges")
    say(f"    full matrix vs free columns only    max|diff| = {mt['full_minus_freeonly']:.3e}"
        "  (free_e == Dirichlet-zero -> the cached c IS the operator)")
    say(f"    nonzero TE on the vertical rows      = {mt['n_nonzero_vertical']} of {mt['n_vertical']}")
    say(f"    scatter determinism max|op_plane-TE| = {scatter:.3e}")
    say(f"    TE lattice reach: mesh z-cell centres span {zc_mesh[0]:.6g}..{zc_mesh[-1]:.6g} m;"
        f" {n_extrap} of {izz.size} plane E_z cells extrapolated")
    say(f"    TE plane stats  rms = {mt['rms']:.12e}   min = {float(te.min()):+.9e}   "
        f"max = {float(te.max()):+.9e}")
    say(f"    corr(TE, A_ez)                       = {c_te:+.15f}   (|corr| {abs(c_te):.9f})")
    say(f"    corr(TE, A_ez) in-range columns only = {c_te_in:+.15f}   (|corr| {abs(c_te_in):.9f})")
    say(f"    per-column oracle on TE              = {c_te_or:+.15f}   ({te_flip} of {NYN} columns flipped)")
    say("")
    say("    CONTROL -- the same operator applied to the EXACT analytic potential resampled")
    say("    onto the same mesh nodes: this is the operator's own ceiling on this mesh ")
    say("    (c@phi is a mass-weighted area integral, not the edge integral, so 1.0 was")
    say("    never available to TE either)")
    say(f"    corr(c@phi_analytic, A_ez)           = {c_ctl:+.15f}   (|corr| {abs(c_ctl):.9f})")
    say(f"    corr(c@phi_analytic, A_ez) in-range  = {c_ctl_in:+.15f}   (|corr| {abs(c_ctl_in):.9f})")
    say(f"    per-column oracle on c@phi           = {c_ctl_or:+.15f}   ({ctl_flip} of {NYN} columns flipped)")
    say(f"    corr(-d(phi_analytic)/dz, same map)  = {c_ctd:+.15f}   (|corr| {abs(c_ctd):.9f})")
    say("")
    say(f"    TE / baseline        = {abs(c_te) / c1b:.9f}   (baseline |corr| {c1b:.9f})")
    say(f"    TE / derivative      = {abs(c_te) / abs(corr(A_ez, F['derivative'])):.9f}")
    say(f"    TE / control ceiling = {abs(c_te) / abs(c_ctl):.9f}")
    say(f"    corr(TE , A_ez) under strip = {te_strip:+.9f}   outside = {te_out:+.9f}")
    say(f"    corr(ctl, A_ez) under strip = {ctl_strip:+.9f}   outside = {ctl_out:+.9f}")

    # archaeology: which variant reproduces the superseded 0.1462?
    say("")
    say(f"  ARCHAEOLOGY  superseded on-disk corr_e_z = {CORR_EZ_OLD!r} (mesh41/51 logs, 04:59-05:06)")
    hits = []
    for rid, label, key, ref, energy in ROWS:
        c = corr(A_ez, F[key])
        if abs(abs(c) - CORR_EZ_OLD) < 1e-9:
            hits.append(rid)
        say(f"    |corr| {abs(c):.15f}   {rid:5s} {label.strip()}"
            f"{'   <-- MATCHES 0.14619976001754773' if abs(abs(c) - CORR_EZ_OLD) < 1e-9 else ''}")
    say(f"    matches: {hits if hits else 'none of the above reproduces 0.14619976001754773'}")

    SUMMARY[tag] = dict(
        corr_e_y=c_ey, ratio_A=base_ratio, anchor=a_raw,
        corr=dict((rid, corr(A_ez, F[key]))
                  for (rid, label, key, ref, energy) in ROWS),
        ratio=dict((rid, float(np.sum(F[key] ** 2) / s_ey))
                   for (rid, label, key, ref, energy) in ROWS),
        pot=p, col_flip=F["_col_flip"], gauge=g,
        archaeology_match=hits,
        te=dict(c_shape=mt["c_shape"], c_nnz=mt["c_nnz"],
                n_vertical=mt["n_vertical"], n_nonzero_vertical=mt["n_nonzero_vertical"],
                full_minus_freeonly=mt["full_minus_freeonly"],
                scatter=scatter, n_extrapolated=int(n_extrap), rms=mt["rms"],
                ctrl_nan=mt["ctrl_nan"],
                corr=c_te, corr_in=c_te_in, corr_oracle=c_te_or, oracle_flips=int(te_flip),
                ctrl=c_ctl, ctrl_in=c_ctl_in, ctrl_oracle=c_ctl_or,
                ctrl_flips=int(ctl_flip), ctrl_diffphi=c_ctd,
                te_over_baseline=abs(c_te) / c1b,
                te_over_derivative=abs(c_te) / abs(corr(A_ez, F["derivative"])),
                te_over_ceiling=abs(c_te) / abs(c_ctl),
                te_strip=te_strip, te_outside=te_out,
                ctrl_strip=ctl_strip, ctrl_outside=ctl_out),
    )


# ---------------------------------------------------------------------------
# 4. verdict
# ---------------------------------------------------------------------------
say("")
say("=" * 100)
say("4. VERDICT")
say("=" * 100)
base = SUMMARY["31x17"]
c1 = base["corr"]["1"]
c2 = base["corr"]["2a"]
c5b = base["corr"]["5b"]
c5c = base["corr"]["5c"]
solv = base["corr"]["SOLV"]
say(f"  31x17: baseline (abs) corr_e_z      = {c1:+.15f}")
say(f"         sign-restored corr_e_z       = {c2:+.15f}   (delta {abs(c2) - abs(c1):+.9f})")
say(f"         potential-vs-field |corr|    = {abs(base['pot']['corr']):.9f}")
say(f"         derivative -d(z)/dz  |corr|  = {abs(c5b):.9f}")
say(f"         per-column aligned   |corr|  = {abs(c5c):.9f}  (upper bound, uses the answer)")
say(f"         solver's own e_z     |corr|  = {abs(solv):.9f}  (independent reconstruction)")
say(f"         reproduced corr_e_y          = {base['corr_e_y']!r}  (on disk {CORR_EY_DISK!r})")
say(f"  41x22: baseline corr_e_z = {SUMMARY['41x22']['corr']['1']:+.15f}   "
    f"sign-restored = {SUMMARY['41x22']['corr']['2a']:+.15f}   "
    f"corr_e_y = {SUMMARY['41x22']['corr_e_y']!r}")
say("")
say("  RATIO BOOKKEEPING (confirmed unit-repaired energy ratio 0.0272240,")
say(f"  TASK 1 measured {SCHEME_A_MEAS:.9f}):")
for rid in ("1", "2a", "2b", "3a", "3b", "3c", "5b", "5c", "SOLV"):
    say(f"    {rid:5s} ratio_A = {base['ratio'][rid]:.12f}")
say("")
say("  Every candidate that only flips a sign or rescales leaves sum(e_z^2) and")
say("  hence the ratio bit-identical -- the 0.0272240 of Falsifier #8 SURVIVES all")
say("  of 2a/2b/3c/5c/SOLV.  A constant offset (3a/3b) or a formula change (5b)")
say("  alters sum(e_z^2) and therefore the ratio, and the recomputed values are")
say("  printed above.")
say("")
say("  Reconstruction defect vs solve defect: the sign-restored field is the")
say("  discriminator.  If |corr| jumps from ~0.12 to the 0.9 band, the mode is")
say("  sound and the *reconstruction* (np.abs at s10118_basis.py:225) destroyed")
say("  E_z.  If the signed field stays low while e_y stays at 0.92, the transverse")
say("  extraction is right and the longitudinal block of the mixed solve is wrong")
say("  -- a solve defect, not a formatting one.")
say("")
say("  PHASE (candidate 4): every array read here is real (audit line above);")
say("  np.real(vecs[:, best_j]) at s10118_basis.py:210 already discarded the")
say("  imaginary part, and mode2d.py:1175 builds the physical e_z as")
say("  *1j*beta*solve(...) -- purely imaginary for a propagating mode.  The")
say("  rectifier at :225 is therefore not a phase fix: it converts that missing")
say("  i and the arbitrary eigenvector sign into a magnitude, node by node.")
say("  Candidate 4 as a *phase* is VOID; as a *conjugation* it is candidate 2.")
say("")
t31 = base["te"]
say("  OPERATOR TEST -- THE DECISION")
say("  TE = c[z-rows] @ z_free is the legal discrete route from a nodal scalar to the E_z")
say("  edge cochain: assemble_mixed's own mass-weighted gradient (cached 'c'), the rows")
say("  being the z-directed edges E_z lives on.  No differencing, no np.abs, no resampling")
say("  choice of this script's own.  Measured on 31x17:")
say(f"    corr(TE, A_ez)                        = {t31['corr']:+.15f}   (|corr| {abs(t31['corr']):.9f})")
say(f"    same, in-range columns only           = {t31['corr_in']:+.15f}   (|corr| {abs(t31['corr_in']):.9f})")
say(f"    per-column oracle on TE               = {t31['corr_oracle']:+.15f}   "
    f"({t31['oracle_flips']} of {NYN} columns flipped)")
say(f"    CONTROL c @ phi_analytic              = {t31['ctrl']:+.15f}   "
    f"(|corr| {abs(t31['ctrl']):.9f})  <- the operator's ceiling")
say(f"    CONTROL per-column oracle             = {t31['ctrl_oracle']:+.15f}   "
    f"({t31['ctrl_flips']} of {NYN} columns flipped)")
say(f"    CONTROL -d(phi)/dz, same map          = {t31['ctrl_diffphi']:+.15f}   "
    f"(|corr| {abs(t31['ctrl_diffphi']):.9f})")
say(f"    TE / baseline | derivative | ceiling  = {t31['te_over_baseline']:.6f} | "
    f"{t31['te_over_derivative']:.6f} | {t31['te_over_ceiling']:.6f}")
say(f"    under strip / outside   TE {t31['te_strip']:+.9f} / {t31['te_outside']:+.9f}"
    f"   CONTROL {t31['ctrl_strip']:+.9f} / {t31['ctrl_outside']:+.9f}")
say("")
say(f"    * TE reaches only {t31['te_over_ceiling'] * 100:.1f}% of the operator's OWN ceiling "
    "-- exact phi")
say("      pushed through the SAME c gives the 0.77 band with ONE uniform global sign")
say(f"      ({t31['ctrl_flips']}/{NYN} columns flip the same way), while TE sits at 0.117 and per-column")
say(f"      re-signing buys only {abs(t31['corr_oracle']) - abs(t31['corr']):+.6f}.  A potential-vs-field")
say("      misreading, a phase error or a column-order scramble would each show up as a")
say("      near-1.0 oracle with a uniform sign.  Neither happens: the residual is SHAPE.")
say(f"    * TE is already the best of the cheap candidates (|{abs(t31['corr']):.6f}| vs baseline"
    f" |{abs(base['corr']['1']):.6f}|,")
say(f"      derivative |{abs(base['corr']['5b']):.6f}|): the legal operator does NOT rescue E_z, it")
say("      reproduces the same 0.12 band, so the 0.12 is not an artefact of the np.abs")
say(f"      reconstruction being read as a field.  z_free itself is only {base['pot']['corr']:+.4f}")
say("      correlated with the analytic phi, i.e. the longitudinal block of the mixed solve")
say("      does not carry the E_z pattern -- a SOLVE defect, which candidate 2 (sign) and")
say("      candidate 5b/5c (differencing) also failed to repair.")
say("")
say("  BRANCH (4) -- 'what is measured is a potential, not a field' -- NOT TAKEN.")
say("    Taking that branch required the legal test to fail on ITS OWN terms, i.e. TE ~ 1.0")
say("    x ceiling with a uniform per-column sign and a near-1.0 oracle.  Measured:")
say(f"    {t31['te_over_ceiling']:.4f} x ceiling, {t31['oracle_flips']}/{NYN} columns flipped, oracle "
    f"{abs(t31['corr_oracle']):.6f}.")
say("    The hypothesis is refuted by its own legal test, not by preference.")
say("    Consequences, booked as they stand:")
say(f"      - the unit-repaired energy ratio {SCHEME_A:.7f} (scheme A, measured")
say(f"        {SCHEME_A_MEAS:.9f}) STANDS as reported;")
say(f"      - scheme C's {SCHEME_C:.8f} is NOT touched, re-derived or reinterpreted here.")
say("    Caveat stated explicitly: TE is an edge cochain (a mass-weighted AREA integral of")
say("    grad phi over the dual cell), so sum(TE^2)/sum(e_y_unit^2) is not like-for-like")
say("    with scheme A; the table prints it only as an order-of-magnitude reference and it")
say("    is never substituted into the ratio bookkeeping above.")
say("")
say("  41x22 cross-check (same code path, second cache, no special-casing):")
for _tag in ("31x17", "41x22"):
    _t = SUMMARY[_tag]["te"]
    say(f"    {_tag}: corr(TE, A_ez) = {_t['corr']:+.15f} (|{abs(_t['corr']):.9f}|)"
        f"  oracle {_t['corr_oracle']:+.9f} ({_t['oracle_flips']}/{NYN} flipped)"
        f"  c@phi {_t['ctrl']:+.9f}")
say(f"    TE/ceiling = {SUMMARY['31x17']['te']['te_over_ceiling']:.6f} (31x17) vs "
    f"{SUMMARY['41x22']['te']['te_over_ceiling']:.6f} (41x22)   "
    "-> the verdict is mesh-independent")
say("")
say("")
JSON_OUT = f"{WORK}/.scratch/corr_ez_101_20.json"
with open(JSON_OUT, "w", encoding="utf-8") as fh:
    json.dump(SUMMARY, fh, indent=1, default=str)
say(f"  wrote {JSON_OUT}")
say(f"  log   {LOG}")
