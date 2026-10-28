#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""routeC_mesh_probe.py -- Route C at an ARBITRARY ladder-shaped mesh.

WHAT THIS IS
------------
`rung4_routeC_probe.py` answers one question: does the corrected enlarged
pencil fit at rung 4?  It is pinned to rung 4 -- its mesh comes from
`high_res_run.RUNGS[4]`, its shift defaults to the pinned rung-3 beta_sq, and
it writes one JSON into `out_rung4/`.  This script is the MESH-PARAMETERISED
generalisation: the mesh is a command-line argument and the shift is explicit
or taken from a named banked rung.  The pipeline itself is NOT copied --
`build_problem` and `run_route_c` are imported from `rung4_routeC_probe as r4`
and called unchanged, so there is exactly one implementation of the Route-C
assembly in this repository.

WHY IT CAN BE TRUSTED: THE LADDER IS THE TEST
---------------------------------------------
The dense ladder has banked records for rungs 0-4
(`out/rung<n>_*/c1_spectrum.npz`).  For any mesh that has one, this script
loads `{beta_sq, R_extracted, eps_eff, corr_ey, corr_ez_vv}` out of that record
and hands it to `r4.run_route_c` as the dense anchor, so `verdict_of` reports
digit agreement against a measurement this script did not make.  Two rungs have
pre-registered expectations:

    20/15/12-6-6  free_e 3604 -> beta_sq 97049.12560615598  R 3.5673083405263886
    24/18/14-7-7  free_e 5044 -> beta_sq 96873.88868040126  R 3.6127170292894397

A faithful generalisation reproduces both to double precision.  Above ~3000
free edges `emfit`'s dense QZ refuses (`_MIXED_DENSE_MAX = 3000`), so above
that there is NO dense reference on disk: `anchor` is null, `comparison` is
null, and the verdict is `verdict_of`'s SELF-CONSISTENCY verdict (residuals +
the `x2 == h^-1 c^T x1` identity).  That is not reproduction and is never
reported as such.

TWO REFUSALS
------------
1. SIZE.  `free_e > MAX_FREE_E` (40000) is refused before any assembly.  The
   Route-C factor at that size is several times the pencil size and the
   measurement, not the guess, decides whether it fits in RAM; a mesh that
   would swap is refused instead.
2. DENSE MATERIALISATION.  No `(n_edges x n_edges)` dense array is ever
   formed.  `r4.build_problem` carries two max-abs DIAGNOSTICS that call
   `.toarray()` on a sparse difference:

       d_m1 = max|m1 - m_mu|        (n_edges x n_edges)
       d_me = max|m_eps_m - m_eps|  (n_edges x n_edges)

   At rung 4 (n_edges 9720) that is 0.70 GiB each; at 30k edges, ~7.25 GiB
   each.  The number they compute is exactly `max(|M.data|)`, i.e. O(nnz), so
   `DenseShim` intercepts an oversized `.toarray()` and returns that SAME
   value as a 0-d array, recording every interception in
   `shim.interceptions`.  Three modes exist so the substitution can be PROVED
   inert rather than assumed:

       --shim off   no interception (refused outright if the diagnostic would
                    exceed DENSE_CAP_BYTES, so "off" can never blow up)
       --shim auto  intercept only above DENSE_CAP_BYTES (256 MiB); inert on
                    rungs 0-3, active at rung 4 and above
       --shim on    intercept above SHIM_FLOOR_BYTES (1 MiB), i.e. at rung 3
                    too -- used to re-run a 5044-free-edge mesh with the shim
                    active and show the digits do not move

OUTPUT
------
`tools/host/sparse-probe/out_mesh/<label>.json` (created with
`os.makedirs(exist_ok=True)`), one compact JSON line on stdout, and a short
human summary.  Nothing else is written.  The ladder's own trees
(`<repo>/out`, `tools/host/sparse-probe/out`) are REFUSED as output
destinations: writing into them would corrupt the records this script
validates against.

USAGE
-----
    python3 -u routeC_mesh_probe.py --mesh '20/15/12-6-6' --sigma 97230.97980133683 --shim off
    python3 -u routeC_mesh_probe.py --mesh '24/18/14-7-7' --sigma-from '20/15/12-6-6'
    python3 -u routeC_mesh_probe.py --ladder     # banked trend + 30k candidates
    python3 -u routeC_mesh_probe.py --help

Exit codes: 0 = self-consistent (and, if an anchor exists, within the digit
thresholds); 1 = not; 2 = refused before solving.
"""
import argparse
import json
import math
import os
import re
import resource
import sys
import time
from pathlib import Path

# Thread caps BEFORE numpy/scipy are imported -- same discipline as
# rung4_routeC_probe.py:88-94, so a timing here is comparable with the
# rung-0..4 timings already recorded.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import numpy as np                                        # noqa: E402
import scipy                                              # noqa: E402
import scipy.sparse as sp                                 # noqa: E402

HERE = Path(__file__).resolve().parent       # <repo>/tools/host/sparse-probe
ROOT = HERE.parents[2]                       # <repo>
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import rung4_routeC_probe as r4                           # noqa: E402

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------
LADDER_OUT = HERE / "out"                    # the live dense ladder (read only)
ALLOWED_OUT_DIR = HERE / "out_mesh"          # the ONLY writer of this script
FORBIDDEN_OUT_DIRS = (ROOT / "out", LADDER_OUT)

MAX_FREE_E = 40000                # refuse before assembly above this
DENSE_CAP_BYTES = 256 * 1024 * 1024          # --shim auto threshold
SHIM_FLOOR_BYTES = 1 * 1024 * 1024           # --shim on threshold

# Pre-registered scored quantity, quoted from out/summary_HIGHRES.txt:
#   Q = R_extracted / R_analytic, R_analytic = 2.8101021387524523, bar |Q-1| <= 0.10
R_ANALYTIC = 2.8101021387524523
Q_BAR = 0.10

# The ladder's own proportions (rungs 0-3: yair/strip = 0.75, z0/strip ~ 0.60),
# used only to name a mesh for a given (nx, nz) in the candidate table.
Y_RATIO = 0.75
Z_RATIO = 0.60
TARGET_FREE_E = 30000
NAMED_CANDIDATES = {(143, 69): 28980, (147, 71): 30672}

# Pre-registered validation expectations (the task's own literals).
EXPECTED = {
    "20/15/12-6-6": {"free_e": 3604, "beta_sq": 97049.12560615598,
                     "R": 3.5673083405263886},
    "24/18/14-7-7": {"free_e": 5044, "beta_sq": 96873.8886804,
                     "R": 3.6127170292894397},
}
BANKED_KEYS = ("beta_sq", "R_extracted", "eps_eff", "corr_ey", "corr_ez_vv")
ANCHOR_KEYS = ("beta_sq", "R", "eps_eff", "corr_ey", "corr_ez_vv")

MESH_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*$")
LADDER_RE = re.compile(r"^rung(\d+)_s(\d+)_a(\d+)_z(\d+)-(\d+)-(\d+)$")


class Refused(Exception):
    """Refusal before solving -- exit code 2."""


def refuse(msg):
    raise Refused(msg)


# ---------------------------------------------------------------------------
# mesh specification
# ---------------------------------------------------------------------------
def parse_mesh(spec):
    """``'strip/yair/z0-z1-z2'`` -> ``(strip, yair, (z0, z1, z2))``."""
    m = MESH_RE.match(str(spec))
    if not m:
        refuse(f"--mesh {spec!r} is not 'strip/yair/z0-z1-z2' "
               "(e.g. '20/15/12-6-6'); the ladder's own shape is "
               "strip / first-axis air cells / the z triple")
    s, a, z0, z1, z2 = (int(v) for v in m.groups())
    if s < 1 or a < 1 or min(z0, z1, z2) < 1:
        refuse(f"--mesh {spec!r} has a non-positive cell count; every axis "
               "needs at least one cell")
    return s, a, (z0, z1, z2)


def mesh_name(s, a, z):
    return f"s{s}_a{a}_z{z[0]}-{z[1]}-{z[2]}"


# ---------------------------------------------------------------------------
# the banked ladder records (read only)
# ---------------------------------------------------------------------------
def banked_record(spec, root=LADDER_OUT):
    """The ladder's own ``c1_spectrum.npz`` for this mesh, or None."""
    s, a, z = parse_mesh(spec)
    if not root.is_dir():
        return None
    for d in sorted(root.iterdir()):
        m = LADDER_RE.match(d.name)
        if not m:
            continue
        got = (int(m.group(2)), int(m.group(3)),
               (int(m.group(4)), int(m.group(5)), int(m.group(6))))
        if got != (s, a, z):
            continue
        p = d / "c1_spectrum.npz"
        if not p.is_file():
            continue
        with np.load(p, allow_pickle=True) as zf:
            vals = {k: r4._scalar(zf[k], f"{p.name}[{k!r}]") for k in BANKED_KEYS}
        return {
            "rung": int(m.group(1)), "path": str(p),
            "beta_sq": vals["beta_sq"], "R": vals["R_extracted"],
            "eps_eff": vals["eps_eff"], "corr_ey": vals["corr_ey"],
            "corr_ez_vv": vals["corr_ez_vv"],
        }
    return None


def anchor_of(record):
    if record is None:
        return None, None
    return {k: float(record[k]) for k in ANCHOR_KEYS}, record["path"]


# ---------------------------------------------------------------------------
# shift
# ---------------------------------------------------------------------------
def resolve_sigma(args):
    """``--sigma`` > ``--sigma-from`` > the rung-3 default pinned in r4."""
    if args.sigma is not None:
        v = float(args.sigma)
        if not (math.isfinite(v) and v > 0.0):
            refuse(f"--sigma {args.sigma!r} is not finite and positive.  Route C "
                   "is shift-invert and needs a shift next to the wanted "
                   "beta_sq; there is no zero-shift fallback")
        return v, "command line (--sigma)"
    if args.sigma_from is not None:
        rec = banked_record(args.sigma_from)
        if rec is None:
            refuse(f"--sigma-from {args.sigma_from!r}: no banked ladder record "
                   f"for that mesh under {LADDER_OUT}")
        v = r4.C_SHIFT_FACTOR * float(rec["beta_sq"])
        return v, (f"--sigma-from {args.sigma_from}: "
                   f"{r4.C_SHIFT_FACTOR!r} * banked beta_sq {rec['beta_sq']!r} "
                   f"(rung {rec['rung']}, {rec['path']})")
    return r4.DEFAULT_SIGMA, (
        f"rung4_routeC_probe.DEFAULT_SIGMA = {r4.C_SHIFT_FACTOR!r} * rung-3 "
        f"beta_sq {r4.RUNG3_RECORD['beta_sq']!r} "
        f"(pinned from {r4.RUNG3_RECORD['record']})")


# ---------------------------------------------------------------------------
# the dense-materialisation shim
# ---------------------------------------------------------------------------
def _sp_base():
    base = getattr(sp, "spmatrix", None)
    if base is not None:
        return base
    return sp._base.spmatrix                       # scipy >= 1.14 fallback


def _sparse_absmax(mat):
    """``max_ij |M_ij|`` for a sparse matrix, in O(nnz).

    Identical to ``max(abs(M.toarray()))`` because ``|M_ij| >= 0``: implicit
    zeros can never exceed the largest stored magnitude, and an empty matrix
    gives 0.0.
    """
    data = getattr(mat, "data", None)
    if data is None or data.size == 0:
        return 0.0
    return float(np.max(np.abs(np.asarray(data, dtype=float))))


class DenseShim:
    """Intercept oversized ``spmatrix.toarray()`` and return the reduced value.

    Everything at or below the active threshold is passed through to the real
    ``toarray`` untouched, so the shim is inert on small meshes.  Every
    interception is recorded, so a report that shimmed is never mistakable for
    one that did not.
    """

    def __init__(self, mode="auto", cap_bytes=DENSE_CAP_BYTES,
                 floor_bytes=SHIM_FLOOR_BYTES):
        if mode not in ("auto", "on", "off"):
            refuse(f"--shim {mode!r} is not one of auto / on / off")
        self.mode = mode
        self.cap_bytes = int(cap_bytes)
        self.floor_bytes = int(floor_bytes)
        self.interceptions = []
        self._patched = {}

    def threshold(self):
        if self.mode == "on":
            return self.floor_bytes
        if self.mode == "auto":
            return self.cap_bytes
        return None

    def _active(self, nbytes):
        t = self.threshold()
        return t is not None and nbytes > t

    def _call(self, orig, mat, args, kwargs):
        shape = tuple(int(v) for v in mat.shape)
        nbytes = shape[0] * shape[1] * int(np.dtype(mat.dtype).itemsize)
        if self._active(nbytes):
            val = _sparse_absmax(mat)
            self.interceptions.append({
                "shape": list(shape), "nbytes": nbytes,
                "dense_gib": nbytes / 2 ** 30,
                "nnz": int(getattr(mat, "nnz", -1)),
                "returned": "max|M.data| as a 0-d array (O(nnz), no dense array)",
                "value": val,
            })
            return np.asarray(val)
        return orig(mat, *args, **kwargs)

    def __enter__(self):
        if self.mode == "off":
            return self
        shim, base = self, _sp_base()

        def patch(cls):
            if cls in self._patched:
                return
            orig = cls.__dict__.get("toarray")
            if orig is None:                # inherits a patched one
                return

            def toarray(instance, *a, **k):
                return shim._call(orig, instance, a, k)

            toarray.__name__ = "toarray"
            toarray.__doc__ = ("DenseShim-intercepting spmatrix.toarray "
                               f"(mode={shim.mode!r})")
            self._patched[cls] = orig
            setattr(cls, "toarray", toarray)

        patch(base)
        for name in ("_base", "_compressed", "_coo", "_dia", "_lil", "_dok",
                     "_bsr"):
            mod = sys.modules.get(f"scipy.sparse.{name}")
            if mod is None:
                continue
            for obj in list(vars(mod).values()):
                if isinstance(obj, type) and issubclass(obj, base):
                    patch(obj)
        return self

    def __exit__(self, *exc):
        for cls, orig in self._patched.items():
            setattr(cls, "toarray", orig)
        self._patched.clear()
        return False

    def report(self):
        return {
            "mode": self.mode,
            "threshold_bytes": self.threshold(),
            "cap_bytes": self.cap_bytes,
            "floor_bytes": self.floor_bytes,
            "interceptions": self.interceptions,
            "note": ("an intercepted toarray() returns max|M.data| as a 0-d "
                     "array -- the same number the dense call was computing, "
                     "in O(nnz); the dense (n_edges x n_edges) array is never "
                     "created"),
        }


# ---------------------------------------------------------------------------
# output location
# ---------------------------------------------------------------------------
def check_out_dir(path):
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()
    for bad in FORBIDDEN_OUT_DIRS:
        b = bad.resolve()
        if p == b or b in p.parents:
            refuse(f"output directory {p} is inside the ladder's tree {b}; "
                   f"this probe writes ONLY under {ALLOWED_OUT_DIR}")
    allowed = ALLOWED_OUT_DIR.resolve()
    if not (p == allowed or allowed in p.parents):
        refuse(f"output directory {p} is outside {allowed}; this probe writes "
               "ONLY there")
    return p


# ---------------------------------------------------------------------------
# one Route-C run on one mesh
# ---------------------------------------------------------------------------
def probe_once(spec, sigma, sigma_how, label, ctx, ref, shim):
    s, a, z = parse_mesh(spec)
    exp = r4.mesh_counts(s, a, z)
    if exp["free_e"] > MAX_FREE_E:
        refuse(f"mesh {spec}: free_e {exp['free_e']} > MAX_FREE_E "
               f"{MAX_FREE_E}.  Refused before assembly: the Route-C pencil and "
               "its factor at that size are measured, not guessed, and this "
               "machine must not be driven into swap")
    if shim.mode == "off":
        diag = exp["edges"] * exp["edges"] * 8
        if diag > DENSE_CAP_BYTES:
            refuse(f"mesh {spec} with --shim off: build_problem's dense "
                   f"max-abs diagnostic is {exp['edges']}^2 * 8 = "
                   f"{diag / 2 ** 30:.2f} GiB, above {DENSE_CAP_BYTES} bytes.  "
                   "Use --shim auto (the diagnostic is replaced by the "
                   "identical O(nnz) value) or a smaller mesh")

    record = banked_record(spec)
    anchor, anchor_path = anchor_of(record)

    cfg = {"rung": -1, "role": label, "strip": s, "yair": a, "z": list(z)}
    t0 = time.perf_counter()
    with shim:
        pb = r4.build_problem(cfg, ctx)
        route_c = r4.run_route_c(pb, ctx, ref, sigma, anchor)
    wall = time.perf_counter() - t0
    verdict = r4.verdict_of(route_c, anchor)

    n_e, n_n = pb["n_e"], pb["n_n"]
    bsq = route_c.get("beta_sq")
    R = route_c.get("R")
    eps = route_c.get("eps_eff")
    q = (R / R_ANALYTIC) if (R is not None and math.isfinite(R)) else None
    cmp_ = route_c.get("comparison") or {}
    expect = EXPECTED.get(spec)

    runs_expect = None
    if expect is not None:
        runs_expect = {
            "expected": expect,
            "free_e_ok": bool(int(n_e) == int(expect["free_e"])),
            "digits_beta_sq_vs_pre_registered": r4.digits(bsq, expect["beta_sq"]),
            "digits_R_vs_pre_registered": r4.digits(R, expect["R"]),
            "digits_beta_sq_vs_banked_npz": cmp_.get("digits_beta_sq"),
            "digits_R_vs_banked_npz": cmp_.get("digits_R"),
        }

    return {
        "mesh": spec, "label": label,
        "strip": s, "yair": a, "z": list(z),
        "nx": exp["nx"], "nz": exp["nz"],
        "n_edges": int(pb["mesh"].n_edges), "n_edges_expected": exp["edges"],
        "n_pec_edges": int(pb["edge_pec"].sum()),
        "free_e": int(n_e), "free_e_expected": exp["free_e"],
        "n_free_nodes": int(n_n), "n_dof": int(n_e + n_n),
        "mesh_checks_ok": bool(pb["mesh_checks_ok"]),
        "mesh_checks": pb["mesh_checks"],
        "assembly": {"t_assemble_s": pb["t_assemble"],
                     "t_assemble_mixed_s": pb["t_assemble_mixed"],
                     "max_abs_m1_minus_m_mu": pb["d_m1"],
                     "max_abs_m_eps_m_minus_m_eps": pb["d_me"],
                     "t_splu_h_s": pb["t_splu_h"],
                     "factor_nnz_h": pb["factor_nnz_h"]},
        "blocks": {"nnz_A": int(pb["A"].nnz), "nnz_m1_f": int(pb["m1_f"].nnz),
                   "nnz_c_f": int(pb["c_f"].nnz), "nnz_h": int(pb["h_blk"].nnz),
                   "nnz_S": route_c.get("nnz_S"),
                   "nnz_S_of_n2": route_c.get("nnz_S_of_n2"),
                   "factor_nnz": route_c.get("factor_nnz"),
                   "fill_per_row": route_c.get("fill_per_row"),
                   "factor_memory_gb_measured":
                       route_c.get("factor_memory_gb_measured"),
                   "factor_is_effectively_dense":
                       route_c.get("factor_is_effectively_dense"),
                   "dense_B_if_formed_gib": n_e * n_e * 8 / 2 ** 30},
        "sigma": float(sigma), "sigma_provenance": sigma_how,
        "beta_sq": bsq, "beta": (math.sqrt(bsq) if (bsq is not None
                                and math.isfinite(bsq) and bsq > 0) else None),
        "eps_eff": eps, "R": R,
        "corr_ey": route_c.get("corr_ey"), "corr_ez_vv": route_c.get("corr_ez_vv"),
        "R_analytic": R_ANALYTIC, "Q": q,
        "abs_Q_minus_1": (abs(q - 1.0) if q is not None else None),
        "Q_inside_bar": (None if q is None else bool(abs(q - 1.0) <= Q_BAR)),
        "residual": route_c.get("residual"),
        "residual_in_enlarged_pencil": route_c.get("residual_in_enlarged_pencil"),
        "x2_matches_DcTx1_rel": route_c.get("x2_matches_DcTx1_rel"),
        "eigenvalue": route_c.get("eigenvalue"),
        "t_splu_s": route_c.get("t_splu_s"),
        "t_eigsh_s": route_c.get("t_eigsh_s"),
        "opinv_calls": route_c.get("opinv_calls"),
        "wall_s": wall,
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
        "peak_rss_note": ("ru_maxrss high-water mark of THIS process after the "
                          "run; it includes every earlier run in the same "
                          "process, so a --repeat series is monotone by "
                          "construction and the first run is the honest bound"),
        "dense_anchor": {"present": anchor is not None, "path": anchor_path,
                         "values": anchor},
        "pre_registered_check": runs_expect,
        "verdict": verdict,
        "route_c": route_c,
    }


# ---------------------------------------------------------------------------
# the ladder trend + candidate meshes
# ---------------------------------------------------------------------------
def ladder_rows(root=LADDER_OUT):
    rows = []
    if not root.is_dir():
        return rows
    for d in sorted(root.iterdir(), key=lambda p: p.name):
        m = LADDER_RE.match(d.name)
        if not m:
            continue
        p = d / "c1_spectrum.npz"
        if not p.is_file():
            continue
        s, a = int(m.group(2)), int(m.group(3))
        z = (int(m.group(4)), int(m.group(5)), int(m.group(6)))
        with np.load(p, allow_pickle=True) as zf:
            vals = {k: r4._scalar(zf[k], f"{p.name}[{k!r}]") for k in BANKED_KEYS}
        exp = r4.mesh_counts(s, a, z)
        rows.append({
            "rung": int(m.group(1)), "mesh": f"{s}/{a}/{z[0]}-{z[1]}-{z[2]}",
            "record": str(p), "nx": exp["nx"], "nz": exp["nz"],
            "n_edges": exp["edges"], "free_e": exp["free_e"],
            "beta_sq": vals["beta_sq"], "R": vals["R_extracted"],
            "eps_eff": vals["eps_eff"], "corr_ey": vals["corr_ey"],
            "corr_ez_vv": vals["corr_ez_vv"],
            "Q": vals["R_extracted"] / R_ANALYTIC,
            "abs_Q_minus_1": abs(vals["R_extracted"] / R_ANALYTIC - 1.0),
        })
    rows.sort(key=lambda r: r["free_e"])
    for prev, cur in zip(rows, rows[1:]):
        cur["digits_beta_sq_vs_previous"] = r4.digits(cur["beta_sq"], prev["beta_sq"])
        cur["digits_R_vs_previous"] = r4.digits(cur["R"], prev["R"])
        cur["d_beta_sq"] = cur["beta_sq"] - prev["beta_sq"]
        cur["d_R"] = cur["R"] - prev["R"]
    return rows


def resolve_nxnz(nx, nz, y_ratio=Y_RATIO, z_ratio=Z_RATIO):
    """Name a mesh for an ``(nx, nz)`` pair using the ladder's proportions.

    ``nx = 1 + 2*yair + strip`` is over-determined by one integer, so ``strip``
    is chosen to put ``yair/strip`` closest to the ladder's own ratio, and the
    z triple is split ``(z0, z1, z2)`` with ``z0 = round(z_ratio * strip)``.
    """
    best = None
    for s in range(1, int(nx)):
        if (int(nx) - 1 - s) % 2:
            continue
        a = (int(nx) - 1 - s) // 2
        if a < 1:
            continue
        score = abs(a / s - y_ratio)
        if best is None or score < best[0]:
            best = (score, s, a)
    if best is None:
        return None
    _, s, a = best
    z0 = max(1, int(round(z_ratio * s)))
    rest = int(nz) - 1 - z0
    if rest < 2:
        return None
    z1 = rest // 2
    z2 = rest - z1
    return s, a, (z0, z1, z2)


def candidate_table(target=TARGET_FREE_E, tol=0.02):
    """Named 30k candidates + the ladder-shaped family near ``target``."""
    named = []
    for (nx, nz), want in sorted(NAMED_CANDIDATES.items()):
        r = resolve_nxnz(nx, nz)
        if r is None:
            named.append({"nx": nx, "nz": nz, "resolved": None,
                          "expected_free_e": want})
            continue
        s, a, z = r
        exp = r4.mesh_counts(s, a, z)
        named.append({
            "nx": nx, "nz": nz, "mesh": f"{s}/{a}/{z[0]}-{z[1]}-{z[2]}",
            "strip": s, "yair": a, "z": list(z), "edges": exp["edges"],
            "n_pec": exp["n_pec"], "free_e": exp["free_e"],
            "expected_free_e": want,
            "confirmed": bool(exp["free_e"] == want),
        })
    family = []
    for s in range(20, 121):
        a = int(round(Y_RATIO * s))
        z0 = max(1, int(round(Z_RATIO * s)))
        z1 = z0 // 2
        z = (z0, z1, z0 - z1)
        exp = r4.mesh_counts(s, a, z)
        if abs(exp["free_e"] - target) <= tol * target:
            family.append({"mesh": f"{s}/{a}/{z[0]}-{z[1]}-{z[2]}", "nx": exp["nx"],
                           "nz": exp["nz"], "free_e": exp["free_e"],
                           "n_edges": exp["edges"],
                           "dense_diagnostic_gib_if_formed":
                               exp["edges"] * exp["edges"] * 8 / 2 ** 30,
                           "dense_B_gib_if_formed":
                               exp["free_e"] ** 2 * 8 / 2 ** 30})
    family.sort(key=lambda r: abs(r["free_e"] - target))
    return {"target_free_e": target, "tolerance": tol,
            "ratio_rule": {"yair_over_strip": Y_RATIO, "z0_over_strip": Z_RATIO},
            "named": named, "family": family}


def print_ladder(payload):
    rows = payload["ladder"]
    print("\n=== banked ladder (read from out/rung*/c1_spectrum.npz) "
          "==================")
    print(f"{'rung':>4} {'mesh':>16} {'nx':>4} {'nz':>4} {'n_edges':>8} "
          f"{'free_e':>7} {'beta_sq':>20} {'R':>20} {'Q':>8}")
    for r in rows:
        print(f"{r['rung']:>4} {r['mesh']:>16} {r['nx']:>4} {r['nz']:>4} "
              f"{r['n_edges']:>8} {r['free_e']:>7} {r['beta_sq']!r:>20} "
              f"{r['R']!r:>20} {r['Q']:>8.4f}")
    print("\n  consecutive-rung movement:")
    for r in rows:
        if "d_beta_sq" not in r:
            continue
        print(f"    {r['rung']}  d(beta_sq) = {r['d_beta_sq']:+.6f}  "
              f"digits {r['digits_beta_sq_vs_previous']:.2f}   "
              f"d(R) = {r['d_R']:+.9f}  "
              f"digits {r['digits_R_vs_previous']:.2f}")
    print(f"\n  beta_sq is monotone? "
          f"{all(r['d_beta_sq'] < 0 for r in rows if 'd_beta_sq' in r)}   "
          f"R is monotone? "
          f"{all(r['d_R'] * (rows[1]['R'] - rows[0]['R']) > 0 for r in rows if 'd_R' in r)}")
    print(f"  Q = R / R_analytic ({R_ANALYTIC!r}); bar |Q-1| <= {Q_BAR}: "
          f"inside = {[r['rung'] for r in rows if r['abs_Q_minus_1'] <= Q_BAR] or 'none'}")

    cand = payload["candidates"]
    print(f"\n=== candidate meshes near free_e {cand['target_free_e']} "
          "==================")
    for c in cand["named"]:
        if c.get("resolved") is None:
            print(f"  {c['nx']}x{c['nz']}: could not be resolved")
            continue
        print(f"  {c['nx']}x{c['nz']} -> mesh {c['mesh']:>16}  edges {c['edges']} "
              f"n_pec {c['n_pec']}  free_e {c['free_e']} "
              f"(expected {c['expected_free_e']})  "
              f"confirmed={c['confirmed']}")
    print(f"  ladder-shaped family within +-{cand['tolerance']:.0%} of "
          f"{cand['target_free_e']}:")
    for f in cand["family"][:8]:
        print(f"    {f['mesh']:>16}  {f['nx']}x{f['nz']}  free_e {f['free_e']:>6}  "
              f"dense diagnostic {f['dense_diagnostic_gib_if_formed']:.2f} GiB, "
              f"dense B {f['dense_B_gib_if_formed']:.2f} GiB "
              "(both NEVER formed)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run(args):
    out_dir = check_out_dir(args.outdir)
    os.makedirs(out_dir, exist_ok=True)

    if args.ladder:
        payload = {
            "probe": "ladder trend + 30k candidate meshes",
            "script": "tools/host/sparse-probe/routeC_mesh_probe.py",
            "R_analytic": R_ANALYTIC, "Q_bar": Q_BAR,
            "ladder": ladder_rows(),
            "candidates": candidate_table(),
        }
        path = out_dir / "ladder.json"
        path.write_text(json.dumps(payload, indent=2, default=r4._json_default)
                        + "\n", encoding="utf-8")
        print(json.dumps({"ladder": [{"rung": r["rung"], "mesh": r["mesh"],
                                      "free_e": r["free_e"],
                                      "beta_sq": r["beta_sq"], "R": r["R"],
                                      "Q": r["Q"]} for r in payload["ladder"]],
                          "named_candidates": payload["candidates"]["named"]},
                         default=r4._json_default))
        print_ladder(payload)
        print(f"  report: {path}")
        return 0

    if args.mesh is None:
        refuse("one of --mesh or --ladder is required")

    spec = args.mesh
    sigma, sigma_how = resolve_sigma(args)
    label = args.label or mesh_name(*parse_mesh(spec))
    if "/" in label or label.startswith("."):
        refuse(f"--label {label!r} must be a plain file stem (no '/')")

    ctx = r4.load_context()
    ref = r4.analytic_reference(ctx)
    exp = r4.mesh_counts(*parse_mesh(spec))
    print(f"workspace {ROOT}")
    print(f"mesh {spec}  ->  nx={exp['nx']} nz={exp['nz']} nodes={exp['nodes']} "
          f"edges={exp['edges']} n_pec={exp['n_pec']} free_e={exp['free_e']}")
    print(f"sigma = {sigma!r}  [{sigma_how}]")
    print(f"shim = {args.shim!r}  (threshold "
          f"{DenseShim(args.shim).threshold()} bytes)")
    print("note: the '=== rung4 ...' banner below is "
          "rung4_routeC_probe.build_problem's own line, unchanged; the mesh it "
          "names is the one on THIS command line", flush=True)

    runs = []
    for i in range(max(1, int(args.repeat))):
        shim = DenseShim(args.shim)
        rec = probe_once(spec, sigma, sigma_how,
                         label if i == 0 else f"{label}#{i + 1}", ctx, ref, shim)
        rec["shim"] = shim.report()
        rec["repeat_index"] = i
        runs.append(rec)
        print(f"  run {i + 1}/{max(1, int(args.repeat))}: "
              f"beta_sq = {rec['beta_sq']!r}  R = {rec['R']!r}  "
              f"eps_eff = {rec['eps_eff']!r}")
        print(f"    splu(S) {rec['t_splu_s']:.3f}s  eigsh {rec['t_eigsh_s']:.3f}s "
              f"({rec['opinv_calls']} oppinv calls)  wall {rec['wall_s']:.2f}s  "
              f"peak RSS {rec['peak_rss_mib']:.0f} MiB  "
              f"shim interceptions {len(rec['shim']['interceptions'])}")
        v = rec["verdict"]
        agr = v.get("agreement")
        print(f"    verdict {v['status']}   agreement "
              + ("null (no dense anchor)" if agr is None else
                 f"{agr['status']} digits(beta_sq)={agr['digits_beta_sq']:.2f} "
                 f"digits(R)={agr['digits_R']:.2f}")
              + f"   residual {rec['residual']:.3e} / "
                f"{rec['residual_in_enlarged_pencil']:.3e}")
        if rec.get("pre_registered_check"):
            pc = rec["pre_registered_check"]
            print(f"    pre-registered: free_e ok={pc['free_e_ok']}  "
                  f"digits(beta_sq)={pc['digits_beta_sq_vs_pre_registered']:.2f}  "
                  f"digits(R)={pc['digits_R_vs_pre_registered']:.2f}")

    canonical = runs[0]
    verdict = canonical["verdict"]
    agr = verdict.get("agreement")
    self_ok = verdict["status"] == "SELF_CONSISTENT"
    agree_ok = (agr is None or agr["meets_thresholds"])
    payload = {
        "probe": ("Route C (corrected enlarged pencil) at an arbitrary "
                  "ladder-shaped mesh -- mesh-parameterised generalisation of "
                  "rung4_routeC_probe.py, which it imports rather than copies"),
        "script": "tools/host/sparse-probe/routeC_mesh_probe.py",
        "environment": {
            "python": sys.version.split()[0], "numpy": np.__version__,
            "scipy": scipy.__version__,
            "thread_env": {v: os.environ.get(v) for v in
                           ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                            "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
        },
        "mesh": spec, "label": label,
        "sigma": {"value": sigma, "provenance": sigma_how,
                  "shift_factor": r4.C_SHIFT_FACTOR,
                  "r4_default_sigma": r4.DEFAULT_SIGMA},
        "thresholds": {"min_digits_beta_sq": r4.MIN_DIGITS_BETA_SQ,
                       "min_digits_R": r4.MIN_DIGITS_R,
                       "max_rel_residual": r4.MAX_REL_RESIDUAL,
                       "max_free_e": MAX_FREE_E,
                       "R_analytic": R_ANALYTIC, "Q_bar": Q_BAR},
        "runs": runs, "canonical": canonical,
        "overall": {"self_consistent": bool(self_ok),
                    "dense_anchor_present": canonical["dense_anchor"]["present"],
                    "agrees_with_anchor": (None if agr is None
                                           else bool(agree_ok)),
                    "exit_code": 0 if (self_ok and agree_ok) else 1},
    }
    path = out_dir / f"{label}.json"
    path.write_text(json.dumps(payload, indent=2, default=r4._json_default)
                    + "\n", encoding="utf-8")

    print("\n--- mesh probe ------------------------------------------------")
    print(f"  mesh {spec}  free_e {canonical['free_e']}  "
          f"n_dof {canonical['n_dof']}")
    print(f"  sigma = {sigma!r}  [{sigma_how}]")
    print(f"  beta_sq = {canonical['beta_sq']!r}   R = {canonical['R']!r}   "
          f"eps_eff = {canonical['eps_eff']!r}")
    print(f"  Q = {canonical['Q']!r}  |Q-1| = {canonical['abs_Q_minus_1']!r}  "
          f"bar {Q_BAR}: {canonical['Q_inside_bar']}")
    print(f"  splu(S) {canonical['t_splu_s']:.3f}s  "
          f"eigsh {canonical['t_eigsh_s']:.3f}s  "
          f"wall {canonical['wall_s']:.2f}s  "
          f"peak RSS {canonical['peak_rss_mib']:.0f} MiB  "
          f"shim {canonical['shim']['mode']} "
          f"({len(canonical['shim']['interceptions'])} intercepted)")
    print(f"  VERDICT {verdict['status']}   agreement "
          + ("null (no dense anchor for this mesh)" if agr is None else
             f"{agr['status']} digits(beta_sq)={agr['digits_beta_sq']!r} "
             f"digits(R)={agr['digits_R']!r}"))
    print(f"  report: {path}")
    print(json.dumps({k: canonical[k] for k in
                      ("mesh", "free_e", "n_dof", "sigma", "beta_sq", "R",
                       "eps_eff", "wall_s", "peak_rss_mib")},
                     default=r4._json_default))
    return 0 if (self_ok and agree_ok) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Route C at an arbitrary ladder-shaped mesh, self-validated "
                    "against the banked dense ladder rungs.  Writes ONLY to "
                    "tools/host/sparse-probe/out_mesh/.")
    ap.add_argument("--mesh", default=None, metavar="S/A/Z0-Z1-Z2",
                    help="strip cells / first-axis air cells / z triple, e.g. "
                         "'20/15/12-6-6' (ladder rung 2) or '24/18/14-7-7' "
                         "(rung 3)")
    ap.add_argument("--sigma", type=float, default=None,
                    help="shift for the shift-invert run (refused if not finite "
                         "and positive)")
    ap.add_argument("--sigma-from", default=None, metavar="MESH",
                    help="shift = 0.999 * that mesh's BANKED beta_sq, read from "
                         "out/rung*/c1_spectrum.npz")
    ap.add_argument("--outdir", default=str(ALLOWED_OUT_DIR),
                    help=f"output directory, default {ALLOWED_OUT_DIR}; the "
                         "ladder's own out/ trees are refused")
    ap.add_argument("--label", default=None,
                    help="file stem for the report (default from the mesh)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="run the whole pipeline N times (timing spread; peak "
                         "RSS is a process high-water mark)")
    ap.add_argument("--shim", choices=("auto", "on", "off"), default="auto",
                    help="dense-materialisation shim: off = never intercept "
                         "(refused if the diagnostic would exceed 256 MiB), "
                         "auto = intercept above 256 MiB, on = intercept above "
                         "1 MiB (used to prove the shim inert on a small mesh)")
    ap.add_argument("--ladder", action="store_true",
                    help="print the banked ladder trend and the 30k candidate "
                         "meshes instead of running a probe")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
