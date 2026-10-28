#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rung4_routeC_probe.py -- Route C (corrected enlarged pencil) on ladder rung 4.

WHERE THIS SITS
---------------
``tools/host/sparse-probe/high_res_run.py`` is the pre-registered JOINT
mesh-refinement ladder, and it is a DENSE QZ ladder: every rung runs the same
``emfit`` dense pencil, only bigger, and ``emfit`` refuses above
``_MIXED_DENSE_MAX = 3000`` free edges unless ``C1_ALLOW_DENSE_ABOVE_MAX=1`` is
set for that rung.  ``tools/host/sparse-probe/sparse_solver_test.py`` is the
separate probe that showed a SPARSE reformulation of the same pencil reaches the
rung-0 / rung-1 answers without ever forming the dense ``B``.  This script asks
the one question neither file answers: does that sparse route still fit at
rung 4, the rung the dense ladder cannot afford?

    rung 4 = strip 36, y_air 22, z 20|10|10
           -> nx 81, nz 41, 3321 nodes, 6400 tris, 9720 edges
           -> 116 PEC edges, 9604 free edges  (the QZ pencil size)
           -> the enlarged Route-C pencil is 12807 x 12807

The rung-4 config is parsed straight out of ``high_res_run.py`` with ``ast``.
The driver is NEVER imported (it has module-level code and shell-outs, and this
probe's report must not depend on its mutable globals), and the ladder's
``out/`` tree is NEVER read: rung 4 has no banked dense record of its own, so
there is nothing there to anchor against anyway.

ROUTE C, IN ONE PARAGRAPH
-------------------------
The reference pencil is ``A x = lam (m1 - c h^-1 c^T) x``.  Enlarging it as

    K_C = [[A, 0], [0, 0]],      M_C = [[m1, -c], [-c^T, h]]

and eliminating the auxiliary block returns exactly that pencil: block row 2
gives ``0 = lam (-c^T x + h y)`` hence ``y = h^-1 c^T x`` for any ``lam != 0``,
and block row 1 then reads ``A x = lam (m1 - c h^-1 c^T) x``.  The elimination is
sigma-independent, so the SHIFTED matrix

    K_C - sigma M_C = [[A - sigma m1, sigma c], [sigma c^T, -sigma h]]

is sparse and shift-invert LU stays sparse.  That is the entire point of the
correction (Route B carries the rank-one term on the stiffness side and
condenses to the wrong pencil ``(A - c h^-1 c^T) x = lam m1 x``).  At rung 4 the
dense ``B`` would be ``9604^2 * 8 = 0.69 GiB`` and a dense ``D = h^-1`` would be
``3203^2 * 8 = 82 MB``; NEITHER is formed here.  ``B`` is only ever applied as
``m1 x - c (h^-1 (c^T x))``, using the existing sparse LU of ``h``.

WHAT IS ***NOT*** MEASURED HERE -- READ BEFORE QUOTING ANYTHING
---------------------------------------------------------------
``tools/host/sparse-probe/evidence/sparse/rung01_sparse_report.json`` carries a
projection of Route C to a 30000-free-edge target: ``factor_memory_gb = 0.0843``
and ``splu_time_at_big_s = 0.1559`` (route B2: ``0.0847`` / ``0.1493``).  Those
are EXTRAPOLATIONS fitted to the rung-0 / rung-1 fill-per-row exponent, they
describe a DIFFERENT and BIGGER mesh, and they are NOT measured at rung 4.
Nothing in this script re-derives them and nothing here measures them: rung 4 is
9604 free edges, not 30000.  Do not quote 0.084 GB / ~0.2 s as rung-4 numbers.

There is also NO dense anchor at rung 4 (the ladder has written no
``c1_spectrum.npz`` for this rung), so every agreement field is reported as
null: ``dense_targets`` is null, ``comparison`` is null and the verdict is a
SELF-CONSISTENCY verdict (residuals and the ``x2 == h^-1 c^T x1`` identity),
never a reproduction verdict.  ``--dense-anchor PATH`` optionally supplies
``{beta_sq, R, eps_eff, corr_ey, corr_ez_vv}`` from a banked record and only
then are the agreement fields filled in.

OUTPUT
------
Exactly one file, ``tools/host/sparse-probe/out_rung4/rung4_routeC_report.json``
(mirroring the rung-01 report's schema).  Any ``--outdir`` that resolves inside
the ladder's own trees -- ``<repo>/out`` (i.e. ``/workspace/out``) or
``tools/host/sparse-probe/out`` (which contains ``out/prev``) -- is REFUSED by
``check_out_dir`` before a single byte is written.

USAGE
-----
    python3 -u rung4_routeC_probe.py                       # sigma from rung 3
    python3 -u rung4_routeC_probe.py --sigma 96777.0148...  # explicit shift
    python3 -u rung4_routeC_probe.py --dense-anchor anchor.json
    python3 -u rung4_routeC_probe.py --help

Exit codes: 0 = self-consistent (and, if an anchor was given, within the
digits thresholds); 1 = not; 2 = refused before solving.
"""
import argparse
import ast
import json
import math
import os
import platform
import sys
import time
from pathlib import Path

# Thread caps BEFORE numpy/scipy are imported -- same discipline as
# sparse_solver_test.py:66-74, so that a Route-C timing here is comparable with
# the rung-0 / rung-1 timings that file recorded.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import numpy as np                                       # noqa: E402
import scipy.sparse as sp                                # noqa: E402
from scipy.sparse.linalg import (                        # noqa: E402
    ArpackNoConvergence,
    eigsh,
    splu,
)

HERE = Path(__file__).resolve().parent          # <repo>/tools/host/sparse-probe
ROOT = HERE.parents[2]                          # <repo>
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import emfit.mode2d as m2                                # noqa: E402
import emfit.modal as M                                  # noqa: E402
from emfit.mode_profile import microstrip_mode_profile   # noqa: E402

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
HIGH_RES_RUN = HERE / "high_res_run.py"
TOLFLUX = ROOT / ".scratch/tol/logs/TOLFLUX.json"
RUNG_INDEX = 4
ZZ1 = 0.0036                    # c1_audit.py ZS second breakpoint

# The single writer of this probe.  check_out_dir() refuses everything else.
ALLOWED_OUT_DIR = HERE / "out_rung4"
OUT_JSON_NAME = "rung4_routeC_report.json"
# The ladder's trees are OFF LIMITS for writes: <repo>/out (the user-facing
# "/workspace/out") and tools/host/sparse-probe/out (the live ladder's cwd,
# whose out/prev is covered as a child).
FORBIDDEN_OUT_DIRS = (ROOT / "out", HERE / "out")

# Route C is a shift-invert run on the CORRECTED enlarged pencil, so it needs a
# shift next to the wanted mode: the same 0.999 * beta_sq placement
# sparse_solver_test.py:140 uses for its rung-0/rung-1 runs.
C_SHIFT_FACTOR = 0.999
MIN_DIGITS_BETA_SQ = 6.0        # same thresholds as sparse_solver_test.py:131-133
MIN_DIGITS_R = 4.0
MAX_REL_RESIDUAL = 1e-8
BYTES_PER_NNZ = 12              # SuperLU CSC factor: 8 data + 4 index

# Where the default shift comes from: the COMPLETED rung-3 record.  These are
# numbers read once, by hand, out of
#   tools/host/sparse-probe/out/rung3_s24_a18_z14-7-7/c1_spectrum.npz
# (keys beta_sq, beta, eps_eff, free_e, n_edges, chosen_col).  They are pinned
# here rather than read at run time because the ladder's out/ tree is not an
# input of this probe: a probe whose shift silently followed whatever the ladder
# last wrote would not be an independent measurement.
RUNG3_RECORD = {
    "record": "tools/host/sparse-probe/out/rung3_s24_a18_z14-7-7/c1_spectrum.npz",
    "keys_used": ["beta_sq", "beta", "eps_eff", "n_edges", "free_e", "chosen_col"],
    "beta_sq": 96873.8886804,
    "beta": 311.24570468,
    "eps_eff": 3.59392796,
    "n_edges": 5128,
    "free_e": 5044,
    "chosen_col": 2561,
}
DEFAULT_SIGMA = C_SHIFT_FACTOR * RUNG3_RECORD["beta_sq"]


# ---------------------------------------------------------------------------
# helpers -- copied from sparse_solver_test.py:145-228 so that the numbers this
# probe prints are computed the same way the rung-0/rung-1 report computed them
# ---------------------------------------------------------------------------
def timed(fn):
    """``(value, seconds)``."""
    t0 = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - t0


def axis(edges, cells):
    pieces = [np.linspace(a, b, n + 1) for (a, b), n in zip(edges, cells)]
    out = pieces[0]
    for p in pieces[1:]:
        out = np.concatenate([out, p[1:]])
    return out


def corr(a, b):
    """Cosine overlap, copied verbatim from c1_audit.py:302-313."""
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0 or a.size != b.size:
        return float("nan")
    return float(np.sum(a * b) / (na * nb))


def digits(measured, target):
    """Decimal digits of agreement; 16.0 when bit-identical."""
    if measured is None or target is None:
        return None
    if not (np.isfinite(measured) and np.isfinite(target)):
        return None
    if target == 0.0:
        return None
    rel = abs(measured - target) / abs(target)
    if rel == 0.0:
        return 16.0
    return float(-math.log10(rel))


def rel_err(measured, target):
    if measured is None or target is None:
        return None
    if not (np.isfinite(measured) and np.isfinite(target)):
        return None
    if target == 0.0:
        return None
    return float(abs(measured - target) / abs(target))


def exception_text(exc):
    return f"{type(exc).__name__}: {exc}"


def deterministic_v0(n):
    """Fixed-seed ARPACK start vector (ARPACK's default one drifts run to run)."""
    return np.random.RandomState(0).standard_normal(int(n))


def _json_default(obj):
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"not JSON serialisable: {type(obj)!r}")


def _scalar(value, what):
    """Accept a scalar or a length-1 list/array (npz records store length-1)."""
    arr = np.asarray(value, dtype=float).ravel()
    if arr.size != 1:
        raise SystemExit(f"REFUSED: {what} must be scalar or length-1, got {arr.size}")
    return float(arr[0])


class CountedSolve:
    """``lu.solve`` wrapper counting matvecs (== ARPACK operator applications)."""

    def __init__(self, lu, shape):
        self.lu = lu
        self.shape = shape
        self.calls = 0

    def matvec(self, x):
        self.calls += 1
        return self.lu.solve(x)

    def operator(self):
        from scipy.sparse.linalg import LinearOperator
        return LinearOperator(shape=self.shape, matvec=self.matvec, dtype=float)


# ---------------------------------------------------------------------------
# geometry / mesh -- identical to sparse_solver_test.py:228-266
# ---------------------------------------------------------------------------
def load_context():
    if not TOLFLUX.is_file():
        raise SystemExit(f"REFUSED: geometry record {TOLFLUX} is missing; the "
                         "probe takes W/H/HSUB/w/eps_r/f from it and will not "
                         "guess them")
    g = json.loads(TOLFLUX.read_text(encoding="utf-8"))["geometry"]
    W, H, HSUB = float(g["width"]), float(g["height"]), float(g["h"])
    WSTRIP, EPS_R = float(g["w"]), float(g["eps_r"])
    ctx = {
        "W": W, "H": H, "HSUB": HSUB, "WSTRIP": WSTRIP, "EPS_R": EPS_R,
        "N_SUB": int(g["n_sub"]), "K_STRIP": int(g["k_strip"]),
        "J_CENTRE": int(g["j_centre"]), "NY": int(g["ny"]), "NZ": int(g["nz"]),
        "CELL": float(g["cell"]), "FREQ": float(g["f"]),
        "ZZ1": ZZ1,
        "Y0": W / 2.0 - WSTRIP / 2.0,
        "Y1": W / 2.0 + WSTRIP / 2.0,
    }
    ctx["k0"] = float(m2.k0_from_freq(ctx["FREQ"]))
    return ctx


def analytic_reference(ctx):
    """The plane-mode reference the |corr| anchors were measured against."""
    prof = microstrip_mode_profile(ctx["HSUB"], ctx["WSTRIP"], ctx["EPS_R"],
                                   n_sub=ctx["N_SUB"])
    nyn = ctx["NY"] + 1
    nzn = ctx["NZ"] + 1
    pana = M.plane_mode(prof, nyn=nyn, nzn=nzn, k_strip=ctx["K_STRIP"],
                        iy_strip_centre=ctx["J_CENTRE"], cell=ctx["CELL"])
    return {
        "e_y": np.asarray(pana.e_y, dtype=float),
        "e_z": np.asarray(pana.e_z, dtype=float),
        "eps_eff": float(getattr(prof, "eps_eff", float("nan"))),
        "shape_e_y": list(np.shape(pana.e_y)),
        "shape_e_z": list(np.shape(pana.e_z)),
    }


# ---------------------------------------------------------------------------
# field / scalar extraction -- copied from sparse_solver_test.py:266-330
# ---------------------------------------------------------------------------
def mode2d_of(x_free, bsq, residual, sigma, mesh, ctx, n_e, free_e):
    """Build a Mode2D whose ``e_t`` is ``x_free`` (unit 2-norm, as the dense path)."""
    x = np.asarray(x_free, dtype=float).ravel()
    nrm = float(np.linalg.norm(x))
    if not (np.isfinite(nrm) and nrm > 0.0):
        return None, x
    x = x / nrm
    e_t = np.zeros(mesh.n_edges)
    e_t[free_e] = x
    beta = math.sqrt(bsq) if (np.isfinite(bsq) and bsq > 0.0) else float("nan")
    mode = m2.Mode2D(
        freq=ctx["FREQ"], k0=ctx["k0"], beta=beta, beta_sq=float(bsq),
        eps_eff=float(bsq) / ctx["k0"] ** 2 if np.isfinite(bsq) else float("nan"),
        residual=float(residual) if residual is not None else float("nan"),
        candidates=tuple(), curl_ratio=None, chosen=0, sigma=float(sigma),
        n_dof=int(mesh.n_edges - n_e + n_e),     # free edges + free nodes
        n_pec=int(mesh.n_edges - n_e),
        e_t=e_t, mesh=mesh, e_z=None,
    )
    return mode, x


def field_scalars(mode, ctx, ref):
    nyn, nzn = ctx["NY"] + 1, ctx["NZ"] + 1
    cell = ctx["CELL"]
    yn_node = np.arange(nyn) * cell
    zn_node = np.arange(nzn) * cell
    yc_mid = (np.arange(nyn - 1) + 0.5) * cell
    zc_mid = (np.arange(nzn - 1) + 0.5) * cell
    yy, zz = np.meshgrid(yc_mid, zn_node, indexing="ij")
    iyy, izz = np.meshgrid(yn_node, zc_mid, indexing="ij")
    ey_pts = np.stack([yy.ravel(), zz.ravel()], axis=1)
    ez_pts = np.stack([iyy.ravel(), izz.ravel()], axis=1)
    e_t = mode.e_at(ey_pts).reshape(nyn - 1, nzn, 2)
    e_y = e_t[:, :, 0] * cell
    e_tz = mode.e_at(ez_pts).reshape(nyn, nzn - 1, 2)
    e_z_vv = e_tz[:, :, 1] * cell
    num = float(np.sum(e_z_vv ** 2))
    den = float(np.sum(e_y ** 2))
    return {
        "R": (num / den) if den != 0.0 else float("nan"),
        "corr_ey": corr(ref["e_y"], e_y),
        "corr_ez_vv": corr(ref["e_z"], e_z_vv),
        "sum_e_y2": den,
        "sum_e_z_vv2": num,
    }


def compare_to_dense(scal, bsq, target, k0):
    eps_eff = bsq / k0 ** 2 if np.isfinite(bsq) else float("nan")
    return {
        "rel_err_beta_sq": rel_err(bsq, target["beta_sq"]),
        "digits_beta_sq": digits(bsq, target["beta_sq"]),
        "rel_err_R": rel_err(scal["R"], target["R"]),
        "digits_R": digits(scal["R"], target["R"]),
        "rel_err_eps_eff": rel_err(eps_eff, target["eps_eff"]),
        "abs_diff_corr_ey": (abs(abs(scal["corr_ey"]) - target["corr_ey"])
                             if np.isfinite(scal["corr_ey"]) else None),
        "abs_diff_corr_ez_vv": (abs(abs(scal["corr_ez_vv"]) - target["corr_ez_vv"])
                                if np.isfinite(scal["corr_ez_vv"]) else None),
    }


# ---------------------------------------------------------------------------
# the ladder: RUNGS parsed with ast, never imported
# ---------------------------------------------------------------------------
def load_ladder_rungs(path=HIGH_RES_RUN):
    """``RUNGS`` out of ``high_res_run.py`` via ``ast.literal_eval``.

    The driver is NOT imported: it has module-level code and shells out to the
    audit, and a probe that imported it would inherit whatever state that
    import left behind.  Parsing the single module-level assignment keeps this
    side-effect free, and the rung-4 mesh is then checked against the mesh
    ``emfit`` actually builds (``mesh_checks``) instead of being trusted.
    """
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f"REFUSED: ladder driver {path} not found; the rung "
                         "table is the only thing read from it")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "RUNGS":
                    found = ast.literal_eval(node.value)
    if not found:
        raise SystemExit(f"REFUSED: no module-level RUNGS assignment found in {path}")
    return found


def rung_config(rungs, index=RUNG_INDEX):
    for r in rungs:
        if int(r.get("rung", -1)) == int(index):
            return r
    raise SystemExit(f"REFUSED: rung {index} is not in the ladder table "
                     f"({[r.get('rung') for r in rungs]}); nothing to probe")


def mesh_counts(strip, yair, z):
    """Closed-form counts, mirroring ``high_res_run.py:210-...``.

    Re-implemented rather than imported (same reason as ``RUNGS``), and NOT
    trusted: every value here is compared against the mesh ``emfit`` actually
    builds, and a drift shows up as a failed ``mesh_checks`` entry.
    """
    nx = 1 + 2 * yair + strip
    nz = 1 + int(sum(z))
    nodes = nx * nz
    tris = 2 * (nx - 1) * (nz - 1)
    edges = 3 * nx * nz - 2 * nx - 2 * nz + 1
    n_pec = (nx - 1) + strip
    free_e = edges - n_pec
    return {"nx": nx, "nz": nz, "nodes": nodes, "tris": tris, "edges": edges,
            "n_pec": n_pec, "free_e": free_e}


# ---------------------------------------------------------------------------
# refusals: output location and shift
# ---------------------------------------------------------------------------
def check_out_dir(path):
    """Refuse anything under the ladder's trees; allow only ``out_rung4``."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()
    for bad in FORBIDDEN_OUT_DIRS:
        b = bad.resolve()
        if p == b or b in p.parents:
            raise SystemExit(f"REFUSED: output directory {p} is inside the "
                             f"ladder's tree {b} (out/ and out/prev are the live "
                             f"ladder's cwd, not this probe's).  This probe "
                             f"writes ONLY under {ALLOWED_OUT_DIR}")
    allowed = ALLOWED_OUT_DIR.resolve()
    if not (p == allowed or allowed in p.parents):
        raise SystemExit(f"REFUSED: output directory {p} is outside "
                         f"{allowed}; this probe writes ONLY there")
    return p


def resolve_sigma(arg):
    """Shift for Route C: ``--sigma`` if given, else 0.999 * rung-3 beta_sq."""
    if arg is None:
        return DEFAULT_SIGMA, (
            "default: C_SHIFT_FACTOR * rung-3 beta_sq = 0.999 * "
            f"{RUNG3_RECORD['beta_sq']!r} (rung-3 record "
            f"{RUNG3_RECORD['record']}, pinned in RUNG3_RECORD)")
    v = float(arg)
    if not (math.isfinite(v) and v > 0.0):
        raise SystemExit(f"REFUSED: --sigma {arg!r} is not a finite positive "
                         "number.  Route C is a shift-invert run and needs a "
                         "shift next to the wanted beta_sq; there is no "
                         f"defensible zero-shift fallback (rung-3 default "
                         f"{DEFAULT_SIGMA!r})")
    return v, "command line (--sigma)"


def load_anchor(path):
    """Optional dense target: ``{beta_sq, R, eps_eff, corr_ey, corr_ez_vv}``."""
    if not path:
        return None, None
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    if not p.is_file():
        raise SystemExit(f"REFUSED: --dense-anchor {p} does not exist.  Omit the "
                         "flag to report null agreement fields instead of a "
                         "wrong comparison")
    raw = json.loads(p.read_text(encoding="utf-8"))
    need = ("beta_sq", "R", "eps_eff", "corr_ey", "corr_ez_vv")
    missing = [k for k in need if k not in raw]
    if missing:
        raise SystemExit(f"REFUSED: --dense-anchor {p} lacks {missing}; expected "
                         f"{list(need)} (values may be scalars or length-1 "
                         "arrays, as the npz records store them)")
    return {k: _scalar(raw[k], f"anchor[{k!r}]") for k in need}, str(p)


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------
def build_problem(cfg, ctx):
    print(f"\n=== rung4 ({cfg.get('role', '')})  strip={cfg['strip']} "
          f"yair={cfg['yair']} z={cfg['z']} ===", flush=True)
    xs = axis([(0.0, ctx["Y0"]), (ctx["Y0"], ctx["Y1"]), (ctx["Y1"], ctx["W"])],
              [cfg["yair"], cfg["strip"], cfg["yair"]])
    zs = axis([(0.0, ctx["HSUB"]), (ctx["HSUB"], ctx["ZZ1"]), (ctx["ZZ1"], ctx["H"])],
              list(cfg["z"]))
    mesh, t_mesh = timed(lambda: m2.structured_mesh(xs, zs))
    print(f"  mesh {xs.size}x{zs.size} nodes={mesh.n_nodes} tris={mesh.n_tris} "
          f"edges={mesh.n_edges} ({t_mesh:.2f}s)", flush=True)

    def eps_of(p):
        return np.where(p[:, 1] <= ctx["HSUB"] + 1e-12, ctx["EPS_R"], 1.0)

    def ground(p):
        return p[:, 1] == 0.0

    def on_strip(p):
        return (p[:, 1] == ctx["HSUB"]) & (p[:, 0] >= ctx["Y0"] - 1e-12) \
            & (p[:, 0] <= ctx["Y1"] + 1e-12)

    boundaries = (ground, on_strip)          # order matters for the PEC masks
    k0 = ctx["k0"]

    (k_q, m_mu, m_eps), t_assemble = timed(
        lambda: m2.assemble(mesh, eps_r=eps_of, mu_r=1.0))
    (m1, m_eps_m, c, k_zz, m_zz), t_assemble_mixed = timed(
        lambda: m2.assemble_mixed(mesh, eps_r=eps_of))
    d_m1 = float(np.max(np.abs((m1 - m_mu).toarray()))) if (m1 - m_mu).nnz else 0.0
    d_me = float(np.max(np.abs((m_eps_m - m_eps).toarray()))) if (m_eps_m - m_eps).nnz else 0.0
    print(f"  assembled ({t_assemble:.2f}s + {t_assemble_mixed:.2f}s), "
          f"max|m1-m_mu|={d_m1:g}, max|m_eps_m-m_eps|={d_me:g}", flush=True)

    edge_pec = m2.pec_edge_mask(mesh, boundaries)
    node_pec = m2.pec_node_mask(mesh, boundaries)
    free_e = np.flatnonzero(~edge_pec)
    free_n = np.flatnonzero(~node_pec)
    n_e, n_n = int(free_e.size), int(free_n.size)

    h_blk = (k_zz[free_n][:, free_n]
             - k0 * k0 * m_zz[free_n][:, free_n]).tocsc()
    c_f = c[free_e][:, free_n].tocsc()
    m1_f = m1[free_e][:, free_e].tocsc()
    m_eps_f = m_eps[free_e][:, free_e].tocsc()
    k_q_f = k_q[free_e][:, free_e].tocsc()

    exp = mesh_counts(cfg["strip"], cfg["yair"], cfg["z"])
    mesh_checks = {
        "nodes": {"measured": int(mesh.n_nodes), "expected": exp["nodes"]},
        "tris": {"measured": int(mesh.n_tris), "expected": exp["tris"]},
        "edges": {"measured": int(mesh.n_edges), "expected": exp["edges"]},
        "free_edges": {"measured": n_e, "expected": exp["free_e"]},
        "n_pec_edges": {"measured": int(edge_pec.sum()),
                        "expected": exp["edges"] - exp["free_e"]},
        # No banked rung-4 record exists, so these are measured-only.  Their
        # "ok" is null and they are NOT part of mesh_checks_ok.
        "free_nodes": {"measured": n_n, "expected": None},
        "nnz_h": {"measured": int(h_blk.nnz), "expected": None},
        "nnz_c": {"measured": int(c_f.nnz), "expected": None},
    }
    for chk in mesh_checks.values():
        chk["ok"] = (None if chk["expected"] is None
                     else bool(chk["measured"] == chk["expected"]))
    ok_all = all(chk["ok"] is not False for chk in mesh_checks.values())
    print("  checks all-ok=" + str(ok_all) + ": " + ", ".join(
        f"{k}={v['measured']}" + ("" if v["ok"] is not False
                                  else f"(!={v['expected']})")
        for k, v in mesh_checks.items()), flush=True)

    lu_h, t_splu_h = timed(lambda: splu(h_blk))
    factor_nnz_h = int(lu_h.L.nnz + lu_h.U.nnz)
    print(f"  splu(h) {t_splu_h:.3f}s  n_h={n_n}  factor_nnz={factor_nnz_h} "
          f"(dense D would be {n_n * n_n * 8 / 1e6:.0f} MB -- never formed)",
          flush=True)

    def form_A():
        a = (k0 * k0 * m_eps_f - k_q_f).tocsc()
        a.sum_duplicates()
        return (0.5 * (a + a.T)).tocsc()

    A, t_A = timed(form_A)
    print(f"  A sparse ({t_A:.3f}s) nnz={A.nnz}  "
          f"(dense B would be {n_e * n_e * 8 / 2 ** 30:.2f} GiB -- never formed)",
          flush=True)

    return {
        "cfg": cfg, "mesh": mesh, "xs": xs, "zs": zs, "t_mesh": t_mesh,
        "k_q": k_q, "m_mu": m_mu, "m_eps": m_eps,
        "m1": m1, "m_eps_m": m_eps_m, "c": c, "k_zz": k_zz, "m_zz": m_zz,
        "t_assemble": t_assemble, "t_assemble_mixed": t_assemble_mixed,
        "d_m1": d_m1, "d_me": d_me,
        "edge_pec": edge_pec, "node_pec": node_pec,
        "free_e": free_e, "free_n": free_n, "n_e": n_e, "n_n": n_n,
        "h_blk": h_blk, "c_f": c_f, "m1_f": m1_f,
        "m_eps_f": m_eps_f, "k_q_f": k_q_f, "A": A, "t_A": t_A,
        "lu_h": lu_h, "t_splu_h": t_splu_h, "factor_nnz_h": factor_nnz_h,
        "mesh_checks": mesh_checks, "mesh_checks_ok": ok_all,
        "counts_expected": exp,
    }


class ReferencePencil:
    """``A x = lam B x`` with ``B = m1 - c h^-1 c^T``, ``B`` never formed.

    ``B`` is applied as ``m1 x - c (h^-1 (c^T x))`` off the sparse LU of ``h``.
    The residual is normalised by ``||A x|| + |lam| ||B x||`` (rung 4 has no
    formed ``B``, so its Frobenius norm is unavailable; the rung-0/rung-1 probe
    could use ``||B||_F`` because it formed the dense ``B``, which at 9604 free
    edges would cost 0.69 GiB).
    """

    def __init__(self, A, m1_f, c_f, lu_h):
        self.A, self.m1_f, self.c_f, self.lu_h = A, m1_f, c_f, lu_h
        self.a_fro = math.sqrt(float(A.multiply(A).sum()))

    def ax(self, x):
        return np.asarray(self.A @ np.asarray(x).ravel()).ravel()

    def bx(self, x):
        x = np.asarray(x).ravel()
        return np.asarray(self.m1_f @ x).ravel() - np.asarray(
            self.c_f @ self.lu_h.solve(np.asarray(self.c_f.T @ x).ravel())).ravel()

    def residual(self, x, lam):
        ax, bx = self.ax(x), self.bx(x)
        den = float(np.linalg.norm(ax) + abs(lam) * np.linalg.norm(bx))
        if not (math.isfinite(den) and den > 0.0):
            return float("nan")
        return float(np.linalg.norm(ax - lam * bx) / den)

    def rayleigh(self, x):
        x = np.asarray(x).ravel()
        den = float(x @ self.bx(x))
        if not (math.isfinite(den) and den != 0.0):
            return float("nan")
        return float(x @ self.ax(x) / den)


# ---------------------------------------------------------------------------
# Route C at rung 4
# ---------------------------------------------------------------------------
def run_route_c(pb, ctx, ref, sigma, anchor):
    n_e, n_n = pb["n_e"], pb["n_n"]
    mesh, free_e = pb["mesh"], pb["free_e"]
    A, m1_f, c_f, h_blk = pb["A"], pb["m1_f"], pb["c_f"], pb["h_blk"]
    cfg, k0 = pb["cfg"], ctx["k0"]
    n2 = float(n_e * n_e)

    zero_nn = sp.csc_matrix((n_n, n_n))
    route_c = {
        "route": "C",
        "sigma": float(sigma),
        "definition": "K=[[A,0],[0,0]], M=[[m1,-c],[-c^T,h]]",
        "expected_elimination": "A x = lam (m1 - c h^-1 c^T) x",
        "note": ("corrected enlargement: the auxiliary/rank-one term is carried "
                 "on the MASS side, so condensation returns the reference "
                 "pencil (Route B carries it on the stiffness side and "
                 "condenses to (A - c h^-1 c^T) x = lam m1 x)"),
        "dense_objects_avoided": {
            "B": f"n_e^2={int(n2)} doubles = {n2 * 8 / 2 ** 30:.2f} GiB -- never formed",
            "D": (f"n_n^2={n_n * n_n} doubles = {n_n * n_n * 8 / 1e6:.0f} MB -- "
                  "never formed; h^-1 applied as an splu solve"),
        },
    }
    try:
        KC, route_c["t_build_K_s"] = timed(
            lambda: sp.block_diag([A, zero_nn], format="csc"))
        MC, route_c["t_build_M_s"] = timed(
            lambda: sp.vstack([sp.hstack([m1_f, (-c_f).tocsc()], format="csc"),
                               sp.hstack([(-c_f.T).tocsc(), h_blk],
                                         format="csc")], format="csc"))
        S_C, route_c["t_build_shifted_s"] = timed(
            lambda: (KC - float(sigma) * MC).tocsc())
    except Exception as exc:
        route_c["build_error"] = exception_text(exc)
        print(f"  [C] build FAILED: {exception_text(exc)}", flush=True)
        return route_c

    bigC = float(S_C.shape[0])
    route_c.update({
        "n": int(S_C.shape[0]),
        "n_transverse": int(n_e), "n_auxiliary": int(n_n),
        "nnz_K": int(KC.nnz), "nnz_M": int(MC.nnz), "nnz_S": int(S_C.nnz),
        "nnz_S_of_n2": float(S_C.nnz) / (bigC * bigC),
        "S_density": float(S_C.nnz) / (bigC * bigC),
    })
    try:
        lu_C, t_lu_C = timed(lambda: splu(S_C))
    except Exception as exc:
        route_c["splu_error"] = exception_text(exc)
        print(f"  [C] splu FAILED: {exception_text(exc)}", flush=True)
        return route_c

    factC = int(lu_C.L.nnz + lu_C.U.nnz)
    route_c.update({
        "t_splu_s": t_lu_C,
        "factor_nnz": factC,
        "fill_ratio_factor_over_S": factC / float(max(S_C.nnz, 1)),
        "fill_per_row": factC / bigC,
        "factor_is_effectively_dense": bool(factC > 0.2 * bigC * bigC),
        "factor_memory_gb_measured": factC * BYTES_PER_NNZ / 1e9,
    })

    op_C = CountedSolve(lu_C, S_C.shape)
    lam_c = None
    xf_c = None
    try:
        (w_c, v_c), route_c["t_eigsh_s"] = timed(lambda: eigsh(
            KC, k=1, M=MC, sigma=float(sigma), which="LM",
            OPinv=op_C.operator(), maxiter=5000,
            v0=deterministic_v0(KC.shape[0])))
        lam_c = float(np.real(w_c[0]))
        route_c["eigenvalue"] = lam_c
        xf_c = np.asarray(v_c[:, 0], dtype=float)
    except ArpackNoConvergence as exc:
        route_c["eigsh_error"] = exception_text(exc)
        route_c["partial_eigenvalues"] = [float(np.real(z))
                                          for z in np.atleast_1d(exc.eigenvalues)]
        try:
            xf_c = np.asarray(exc.eigenvectors[:, 0], dtype=float)
        except Exception:
            xf_c = None
        print(f"  [C] eigsh NO CONVERGENCE ({op_C.calls} calls): "
              f"{exception_text(exc)}", flush=True)
    except Exception as exc:
        route_c["eigsh_error"] = exception_text(exc)
        print(f"  [C] eigsh FAILED: {exception_text(exc)}", flush=True)
    route_c["opinv_calls"] = op_C.calls

    if xf_c is None or not np.all(np.isfinite(xf_c)):
        return route_c

    z_c = xf_c / (float(np.linalg.norm(xf_c)) or 1.0)
    x_c = z_c[:n_e]
    n1c = float(np.linalg.norm(x_c))
    if not (math.isfinite(n1c) and n1c > 0.0):
        route_c["field_error"] = "unusable eigenvector (zero/NaN transverse norm)"
        return route_c
    xn = x_c / n1c

    # the enlarged-pencil residual, with the Frobenius norms of K_C and M_C
    # assembled from the blocks (K_C and M_C are sparse, so this is cheap)
    kfro = pb["A"].multiply(pb["A"]).sum()
    mfro2 = (m1_f.multiply(m1_f).sum()
             + 2.0 * c_f.multiply(c_f).sum()
             + h_blk.multiply(h_blk).sum())
    kfro = math.sqrt(float(kfro))
    mfro = math.sqrt(float(mfro2))
    kz = np.asarray(KC @ z_c).ravel()
    mz = np.asarray(MC @ z_c).ravel()
    route_c["residual_in_enlarged_pencil"] = float(
        np.linalg.norm(kz - lam_c * mz)
        / ((kfro + abs(lam_c) * mfro) * (float(np.linalg.norm(z_c)) or 1.0)))

    # y == h^-1 c^T x, checked on the normalised transverse vector (the same
    # check sparse_solver_test.py makes with its formed dense D)
    x2_exp = np.asarray(pb["lu_h"].solve(
        np.asarray(c_f.T @ xn).ravel())).ravel()
    x2_got = z_c[n_e:]
    route_c["x2_matches_DcTx1_rel"] = float(
        np.linalg.norm(x2_got / (np.linalg.norm(x2_got) or 1.0)
                       - x2_exp / (np.linalg.norm(x2_exp) or 1.0)))

    rp = ReferencePencil(A, m1_f, c_f, pb["lu_h"])
    route_c["rayleigh_true_pencil"] = rp.rayleigh(xn)
    route_c["residual"] = rp.residual(xn, lam_c)
    route_c["residual_normalisation"] = (
        "||A x - lam B x|| / (||A x|| + |lam| ||B x||) -- B is not formed at "
        "rung 4, so the ||B||_F normalisation of the rung-0/rung-1 probe is "
        "unavailable")
    route_c["beta_sq"] = lam_c
    route_c["eps_eff"] = lam_c / k0 ** 2

    mode_c, _ = mode2d_of(x_c, lam_c, route_c["residual"], float(sigma),
                          mesh, ctx, n_e, free_e)
    if mode_c is None:
        route_c["field_error"] = "unusable eigenvector (zero/NaN norm)"
        return route_c
    scal_c = field_scalars(mode_c, ctx, ref)
    route_c["R"] = scal_c["R"]
    route_c["corr_ey"] = scal_c["corr_ey"]
    route_c["corr_ez_vv"] = scal_c["corr_ez_vv"]
    if anchor is None:
        route_c["comparison"] = None
        route_c["comparison_note"] = (
            "no dense anchor at rung 4 (the ladder has written no "
            "c1_spectrum.npz for this rung), so no agreement is computed; "
            "--dense-anchor supplies one")
    else:
        route_c["comparison"] = compare_to_dense(scal_c, lam_c, anchor, k0)
        route_c["comparison_note"] = (
            "route C's eigenvalue IS the beta^2 of the reference pencil (exact "
            "block elimination), so it is compared directly, without a "
            "Rayleigh-quotient detour")
    print(f"  [C sigma={float(sigma):.6g}] nnz(S)={S_C.nnz} "
          f"({route_c['nnz_S_of_n2']:.5f} n^2) fact={factC} "
          f"fill/row={route_c['fill_per_row']:.1f} "
          f"mem={route_c['factor_memory_gb_measured']:.3f} GB "
          f"splu={t_lu_C:.2f}s eig={route_c['t_eigsh_s']:.2f}s "
          f"({op_C.calls} calls) lam={lam_c:.6f} "
          f"R={scal_c['R']:.12f} "
          f"|cy|={abs(scal_c['corr_ey']):.12f} "
          f"|cz|={abs(scal_c['corr_ez_vv']):.12f} "
          f"res={route_c['residual']:.2e} "
          f"x2dev={route_c['x2_matches_DcTx1_rel']:.2e}", flush=True)
    return route_c


def verdict_of(entry, anchor):
    """Self-consistency always; agreement only when an anchor was supplied."""
    def ok_res(value):
        return (value is not None and isinstance(value, float)
                and math.isfinite(value) and value <= MAX_REL_RESIDUAL)

    has_pair = entry.get("eigenvalue") is not None and "R" in entry
    self_ok = bool(has_pair and ok_res(entry.get("residual"))
                   and ok_res(entry.get("residual_in_enlarged_pencil")))
    out = {
        "status": ("NO_EIGENPAIR" if not has_pair
                   else ("SELF_CONSISTENT" if self_ok else "INCONSISTENT")),
        "sigma": entry.get("sigma"),
        "eigenvalue": entry.get("eigenvalue"),
        "beta_sq": entry.get("beta_sq"),
        "eps_eff": entry.get("eps_eff"),
        "R": entry.get("R"),
        "corr_ey": entry.get("corr_ey"),
        "corr_ez_vv": entry.get("corr_ez_vv"),
        "rel_residual_reference_pencil": entry.get("residual"),
        "rel_residual_enlarged": entry.get("residual_in_enlarged_pencil"),
        "x2_matches_DcTx1_rel": entry.get("x2_matches_DcTx1_rel"),
        "n": entry.get("n"), "nnz_S": entry.get("nnz_S"),
        "nnz_S_of_n2": entry.get("nnz_S_of_n2"),
        "factor_nnz": entry.get("factor_nnz"),
        "fill_per_row": entry.get("fill_per_row"),
        "factor_memory_gb_measured": entry.get("factor_memory_gb_measured"),
        "t_splu_s": entry.get("t_splu_s"),
        "factor_is_effectively_dense": entry.get("factor_is_effectively_dense"),
        "error": (entry.get("build_error") or entry.get("splu_error")
                  or entry.get("eigsh_error")),
    }
    if anchor is None:
        out["agreement"] = None
        out["agreement_note"] = (
            "null by construction: rung 4 has no banked dense record to agree "
            "with.  This verdict is SELF-CONSISTENCY only (residuals + the "
            "x2 == h^-1 c^T x1 identity), not reproduction of a reference")
    else:
        cmp_ = entry.get("comparison") or {}
        d_bsq, d_r = cmp_.get("digits_beta_sq"), cmp_.get("digits_R")
        meets = bool(d_bsq is not None and d_bsq >= MIN_DIGITS_BETA_SQ
                     and d_r is not None and d_r >= MIN_DIGITS_R)
        out["agreement"] = {
            "rel_err_beta_sq": cmp_.get("rel_err_beta_sq"),
            "digits_beta_sq": d_bsq,
            "rel_err_R": cmp_.get("rel_err_R"),
            "digits_R": d_r,
            "rel_err_eps_eff": cmp_.get("rel_err_eps_eff"),
            "abs_diff_corr_ey": cmp_.get("abs_diff_corr_ey"),
            "abs_diff_corr_ez_vv": cmp_.get("abs_diff_corr_ez_vv"),
            "meets_thresholds": meets,
            "status": ("REPRODUCES_REFERENCE" if meets else "DISAGREES"),
        }
    return out


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def print_summary(payload, path):
    v = payload["verdict"]["route_C"]
    print("\n--- rung 4 / Route C -------------------------------------------")
    print(f"  n = {v['n']}  (transverse {payload['rungs']['rung4']['blocks']['n_free_edges']}"
          f" + auxiliary {payload['rungs']['rung4']['blocks']['n_free_nodes']})")
    print(f"  sigma = {v['sigma']!r}   beta_sq = {v['beta_sq']!r}   "
          f"eps_eff = {v['eps_eff']!r}")
    print(f"  R = {v['R']!r}   |corr_ey| = {abs(v['corr_ey'])!r}   "
          f"|corr_ez_vv| = {abs(v['corr_ez_vv'])!r}")
    print(f"  factor_nnz = {v['factor_nnz']}  fill/row = {v['fill_per_row']:.1f}  "
          f"memory = {v['factor_memory_gb_measured']:.3f} GB (measured)  "
          f"splu = {v['t_splu_s']:.2f}s")
    print(f"  rel residual: reference pencil {v['rel_residual_reference_pencil']:.3e}"
          f"  enlarged pencil {v['rel_residual_enlarged']:.3e}"
          f"  x2 deviation {v['x2_matches_DcTx1_rel']:.3e}")
    print(f"  VERDICT: {v['status']}   agreement: "
          + ("null (no anchor)" if v["agreement"] is None
             else f"{v['agreement']['status']} "
                  f"digits(beta_sq)={v['agreement']['digits_beta_sq']} "
                  f"digits(R)={v['agreement']['digits_R']}"))
    print("  NOTE: the 0.0843 GB / 0.156 s Route-C projection in "
          "evidence/sparse/rung01_sparse_report.json is an EXTRAPOLATION from "
          "rung 0/1 and is NOT measured at rung 4.")
    print(f"  report: {path}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Route C (corrected enlarged pencil) at high_res_run rung 4 "
                    "(9604 free edges).  Writes ONLY to "
                    "tools/host/sparse-probe/out_rung4/.")
    ap.add_argument("--sigma", type=float, default=None,
                    help="shift for the shift-invert run (default: 0.999 * "
                         f"rung-3 beta_sq = {DEFAULT_SIGMA!r}, pinned from "
                         "out/rung3_s24_a18_z14-7-7/c1_spectrum.npz).  Refused "
                         "if non-finite or <= 0: Route C has no zero-shift "
                         "fallback")
    ap.add_argument("--dense-anchor", default=None, metavar="PATH",
                    help="optional JSON with {beta_sq, R, eps_eff, corr_ey, "
                         "corr_ez_vv} from a banked dense record.  Without it "
                         "dense_targets/comparison are null and the verdict is "
                         "self-consistency only")
    ap.add_argument("--outdir", default=str(ALLOWED_OUT_DIR),
                    help=f"output directory; must resolve inside "
                         f"{ALLOWED_OUT_DIR} (default).  Anything under the "
                         "ladder's out/ or out/prev is refused")
    args = ap.parse_args(argv)

    out_dir = check_out_dir(args.outdir)
    sigma, sigma_how = resolve_sigma(args.sigma)
    anchor, anchor_path = load_anchor(args.dense_anchor)

    t_start = time.perf_counter()
    rungs = load_ladder_rungs()
    cfg = rung_config(rungs)
    exp = mesh_counts(cfg["strip"], cfg["yair"], cfg["z"])
    print(f"workspace {ROOT}")
    print(f"rung 4 from {HIGH_RES_RUN.name}: strip={cfg['strip']} "
          f"yair={cfg['yair']} z={list(cfg['z'])}  ->  nx={exp['nx']} "
          f"nz={exp['nz']} nodes={exp['nodes']} edges={exp['edges']} "
          f"free_e={exp['free_e']}")
    print(f"sigma = {sigma!r}  [{sigma_how}]")
    print(f"output {out_dir / OUT_JSON_NAME}", flush=True)

    ctx = load_context()
    print(f"k0 = {ctx['k0']!r}  f = {ctx['FREQ']!r}  cell = {ctx['CELL']}")
    ref = analytic_reference(ctx)
    print(f"analytic plane mode: {ref['shape_e_y']} / {ref['shape_e_z']}, "
          f"eps_eff = {ref['eps_eff']!r}", flush=True)

    pb = build_problem(cfg, ctx)
    route_c = run_route_c(pb, ctx, ref, sigma, anchor)

    result = {
        "key": "rung4",
        "name": f"rung4_s{cfg['strip']}_a{cfg['yair']}_z"
                + "-".join(str(v) for v in cfg["z"]),
        "config": {"y_air": cfg["yair"], "strip_cells": cfg["strip"],
                   "z_split": list(cfg["z"]),
                   "n_x_nodes": int(pb["xs"].size), "n_z_nodes": int(pb["zs"].size)},
        "mesh_checks": pb["mesh_checks"],
        "mesh_checks_ok": pb["mesh_checks_ok"],
        "assembly": {"t_assemble_s": pb["t_assemble"],
                     "t_assemble_mixed_s": pb["t_assemble_mixed"],
                     "max_abs_m1_minus_m_mu": pb["d_m1"],
                     "max_abs_m_eps_m_minus_m_eps": pb["d_me"]},
        "blocks": {"n_free_edges": pb["n_e"], "n_free_nodes": pb["n_n"],
                   "n_dense_pencil": pb["n_e"],
                   "n_dense_squared": int(pb["n_e"] * pb["n_e"]),
                   "nnz_A": int(pb["A"].nnz), "nnz_m1_f": int(pb["m1_f"].nnz),
                   "nnz_m_eps_f": int(pb["m_eps_f"].nnz),
                   "nnz_k_q_f": int(pb["k_q_f"].nnz),
                   "nnz_c_f": int(pb["c_f"].nnz), "nnz_h": int(pb["h_blk"].nnz),
                   "t_form_A_s": pb["t_A"],
                   "dense_B_if_formed_gib": pb["n_e"] * pb["n_e"] * 8 / 2 ** 30,
                   "dense_D_if_formed_mb": pb["n_n"] * pb["n_n"] * 8 / 1e6},
        "longitudinal": {"t_splu_h_s": pb["t_splu_h"],
                         "factor_nnz_h": pb["factor_nnz_h"],
                         "solve_note": "h^-1 is applied as an splu solve; the "
                                       "dense D of the rung-0/rung-1 probe is "
                                       "deliberately not formed here"},
        "dense_targets": anchor,
        "dense_targets_note": (
            "null: the ladder has written no dense record for rung 4, so there "
            "is no target to compare with.  The rung-0/rung-1 report hard-coded "
            "its targets from banked records; there is nothing to hard-code "
            "here, and this probe does not run a dense QZ of its own"
            if anchor is None else "supplied on the command line (--dense-anchor)"),
        "route_A": [],
        "route_C": route_c,
    }

    entry_v = verdict_of(route_c, anchor)
    self_ok = entry_v["status"] == "SELF_CONSISTENT"
    agree_ok = (entry_v["agreement"] is None
                or entry_v["agreement"]["meets_thresholds"])
    exit_code = 0 if (self_ok and agree_ok) else 1

    payload = {
        "probe": ("Route C (corrected enlarged pencil) at high_res_run rung 4 -- "
                  "sparse reformulation of the 2-D mixed mode pencil"),
        "script": "tools/host/sparse-probe/rung4_routeC_probe.py",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "thread_env": {v: os.environ.get(v) for v in
                           ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                            "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
            "host_note": "rung 4 was NOT run by this script's author: the "
                         "timings, if present, are this machine's",
        },
        "geometry": {k: ctx[k] for k in ("W", "H", "HSUB", "WSTRIP", "EPS_R",
                                         "N_SUB", "K_STRIP", "J_CENTRE", "NY",
                                         "NZ", "CELL", "FREQ", "Y0", "Y1",
                                         "ZZ1", "k0")},
        "analytic_reference": {"eps_eff": ref["eps_eff"],
                               "shape_e_y": ref["shape_e_y"],
                               "shape_e_z": ref["shape_e_z"]},
        "targets_note": ("dense_targets is null: rung 4 has no banked dense "
                         "record, so this report contains no agreement fields "
                         "unless --dense-anchor was given"),
        "sigma_provenance": {
            "sigma": sigma, "how": sigma_how,
            "shift_factor": C_SHIFT_FACTOR,
            "default_sigma": DEFAULT_SIGMA,
            "rung3_record": RUNG3_RECORD,
            "note": ("Route C is shift-invert on the corrected enlarged pencil "
                     "and needs a shift next to the wanted beta_sq; the shift "
                     "is placed the same way sparse_solver_test.py places it "
                     "for rung 0/1 (0.999 * beta_sq), with rung 3's beta_sq as "
                     "the operating point"),
        },
        "dense_anchor": {"present": anchor is not None, "path": anchor_path,
                         "values": anchor},
        "routes": {"C": ("CORRECTED enlargement: K=[[A,0],[0,0]], "
                         "M=[[m1,-c],[-c^T,h]], sigma=0.999*beta_sq; condenses "
                         "to the reference pencil A x = lam (m1 - c h^-1 c^T) x. "
                         "Routes A (dense B) and B/B2 are deliberately NOT run: "
                         "at 9604 free edges the dense B alone is 0.69 GiB")},
        "rungs": {"rung4": result},
        "extrapolation": {
            "available": False,
            "reason": ("sparse_solver_test.py fits its fill-per-row exponents on "
                       "TWO measured rungs (rung 0 and rung 1).  This probe runs "
                       "ONE rung, so there is nothing to fit and no projection "
                       "is computed here"),
            "prior_projection_not_remeasured": {
                "source": "tools/host/sparse-probe/evidence/sparse/"
                          "rung01_sparse_report.json",
                "target_free_e": 30000.0,
                "route_C_factor_memory_gb": 0.08430019068778438,
                "route_C_splu_time_at_big_s": 0.15587435136032093,
                "measured_at_rung4": False,
            },
        },
        "wall_seconds": time.perf_counter() - t_start,
        "verdict": {
            "thresholds": {"min_digits_beta_sq": MIN_DIGITS_BETA_SQ,
                           "min_digits_R": MIN_DIGITS_R,
                           "max_rel_residual": MAX_REL_RESIDUAL},
            "route_C": {"rung4": entry_v},
            "overall": {
                "dense_anchor_present": anchor is not None,
                "route_C_self_consistent": bool(self_ok),
                "route_C_agrees_with_anchor": (None if anchor is None
                                               else bool(agree_ok)),
                "agreement_evaluated": anchor is not None,
                "note": ("no dense reference exists at rung 4, so no "
                         "'reproduces_reference' claim is made anywhere in this "
                         "report"),
                "exit_code": exit_code,
            },
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / OUT_JSON_NAME
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n",
                    encoding="utf-8")
    print_summary(payload, path)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
