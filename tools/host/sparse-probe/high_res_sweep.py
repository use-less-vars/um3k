#!/usr/bin/env python3
"""high_res_sweep.py — the 40k / 50k / 60k sparse Route-C sweep.

PREPARED, NOT RUN
-----------------
This file was written by a dispatch that was explicitly forbidden to run it.
Nothing here has been executed: no solve, no mesh assembly, no timing.  Every
number the plan prints *before* a point runs is an ESTIMATE derived from the
~30k records already on disk (``out_mesh/M1..M4``), and every number a point
writes *after* it runs is MEASURED in that point's own process.  The two are
kept in separate keys so a reader can never mistake one for the other.

WHERE THIS SITS
---------------
The sparse Route-C story so far:

  * ``rung4_routeC_probe.py`` (r4) — the single-shot driver.  Fixed rung-3
    geometry, dense QZ anchor, ``DEFAULT_SIGMA`` = 0.999 * rung-3 beta_sq.
  * ``routeC_mesh_probe.py`` (mp) — the mesh-parameterised driver.  It takes a
    ``(strip, yair, z)`` cross-section, assembles through ``r4.build_problem``,
    runs ``r4.run_route_c``, and refuses any ``free_e > mp.MAX_FREE_E``
    (40000) *before* assembly.  It produced M1..M4, the ladder that reached
    30672 free edges in 0.69 s (commit 4603e6d, written up in bf7a2fb).
  * this file — the next ladder, three points at ~40k / ~50k / ~60k free
    edges, driven from a *shell-able* parent that spawns one child process per
    point so that each point's peak RSS is its own high-water mark.

It deliberately does NOT call ``mp.probe_once``: that entry point refuses above
40000 free edges and we are going above it.  It calls the same three r4
primitives ``mp.probe_once`` calls (``load_context`` / ``analytic_reference`` /
``build_problem`` / ``run_route_c``) plus ``r4.verdict_of``, and replaces mp's
flat refusal with a *memory pre-flight* against ``/proc/meminfo`` MemAvailable.
mp itself is left untouched — its 40000 guard still holds for its own callers.

THE FREE-EDGE LAW
-----------------
Everything about the planned shapes follows from one identity.  For a
cross-section ``(strip, yair, z)`` with ``nz = 1 + sum(z)``:

    nx      = 1 + 2*yair + strip
    edges   = 3*nx*nz - 2*nx - 2*nz + 1
    n_pec   = (nx - 1) + strip
    free_e  = edges - n_pec
            = 3*(nz - 1)*nx + (2 - 2*nz - strip)

i.e. **with the cross-section held fixed, free_e is strictly LINEAR in nx**
(slope ``3*(nz-1)``, intercept ``2 - 2*nz - strip``).  Only the y-extent of the
air box may grow; ``nx`` is the y-node count and there is no third index.

The dispatch quotes ``free = 48*nx - 44``.  Matching coefficients:

    3*(nz - 1) = 48      ->  nz = 17   (a 16-cell z axis, e.g. 8-4-4)
    2 - 2*nz - strip = -44  ->  strip = 2 - 2*17 + 44 = 12

So the stated law is exactly the **rung-0 cross-section (strip 12) with an
8-4-4 z stack**, and the only thing that changes between points is how far the
air box reaches in y:

    nx = 1 + 2*yair + 12   =>   yair = (nx - 13) / 2

which forces **nx to be odd** (an even nx has no integer yair) — hence the
planned node counts below are the nearest odd nx to ``(target + 44) / 48``,
never the exact nominal target:

    target   nx     yair   free_e (actual)   offset
    40000    835    411    40036             +36
    50000    1043   515    50020             +20
    60000    1251   619    60004             +4

The script never trusts that table: ``plan_fixed`` recomputes nx from the
derived law, calls ``r4.mesh_counts`` on the candidate and reports the ACTUAL
free_e together with its offset from the nominal target.  When a band of nx is
inadmissible (parity, yair < 1) it scans +/-5 and takes the closest admissible
candidate.

Anisotropy caveat: holding strip and z fixed while growing yair makes the air
box increasingly elongated in y.  ``strip`` is the rung-0 cross-section, so the
die itself does not change, but the ratio (air box in y) / (air box in z) grows
line by line.  Any y-drift in R across the three points therefore confounds
extent with aspect ratio, and the sweep cannot separate them.  That is a
property of the requested family, not a bug; the ``--family ladder`` option
exists partly so a future run can cross-check against a family that scales all
three axes together.

The ~30k ladder (M1..M4) was NOT this family.  It scaled strip, yair and z
together (36/22/20-10-10 ... 58/44/35-17-18), which makes free_e roughly
quadratic in strip (free_e ~ 9*strip^2), not ``48*nx - 44``.  ``--family
ladder`` reproduces that shape here (fixed ratios yair/strip = 22/36 and
z/strip = 20/36), and the payload records which law the chosen family actually
obeys, so the two families are never silently confused.

MEASURED vs ESTIMATED
---------------------
MEASURED (per point, in that point's own process): free_e (from the assembled
problem, cross-checked against ``mesh_counts``), beta_sq, R_extracted, eps_eff,
corr_ey, corr_ez_vv, residual, residual_in_enlarged_pencil,
x2_matches_DcTx1_rel, eigenvalue, nnz_S, factor_nnz, fill_per_row,
factor_memory_gb_measured, t_splu_s, t_eigsh_s, opinv_calls, peak RSS, wall.

ESTIMATED (pre-flight only, never overwriting a measurement): n_dof, fill per
row, factor memory.  Both scale laws are anchored on the one record we have --
n_dof/free_e from the ~30k run, and fill-per-row growing like sqrt(n_dof) --
and are labelled ``*_est`` everywhere.  The pre-flight is deliberately loose:
it exists to refuse a point that cannot possibly fit in RAM, not to predict the
answer.

R_extracted NAMING
------------------
``route_c["R"]`` is R as *extracted from the sparse eigenpair*.  Every record
here stores it as ``R_extracted`` and adds ``R_extracted_note`` saying so,
because ``R_ANALYTIC`` (2.8101021387524523) is the quantity it is compared
against and a bare ``R`` invites exactly that confusion.  ``Q = R_extracted /
R_ANALYTIC`` and ``Q_inside_bar`` is ``|Q - 1| <= Q_BAR`` (0.10).

THE SHIFT
---------
sigma is the interior shift; it must sit just below the eigenvalue of interest
or ``eigsh`` converges to the wrong end.  We do not invent it:

  * the seed is ``0.999 * beta_sq`` of the ~30k record, read at run time from
    ``out_mesh/*.json`` by picking the record whose free_e is closest to 30000
    (that is M4_fe30672.json, 30672 free edges);
  * each subsequent point chains ``0.999 * (previous point's beta_sq)`` -- the
    exact convention M1->M4 already used (M3 ran at 96404.936 = 0.999 x M2's
    96501.438);
  * ``--no-chain`` freezes the seed for all three points, for the case where
    chaining is suspected of walking the shift away from the eigenvalue;
  * ``--one`` REFUSES to run without an explicit ``--sigma``: a child process
    that guesses its own shift would make the sweep unreproducible.

OUTPUT
------
    out_highres/points/hi40k_nx835.json     one record per point
    out_highres/points/hi50k_nx1043.json
    out_highres/points/hi60k_nx1251.json
    out_highres/high_res_sweep.json         the aggregate payload

``out_highres/`` is the only directory this script will write to.  ``out/``,
``out_mesh/`` and ``out_rung4/`` are refused by name, because they belong to
other runs that are still in flight; ``out_mesh/`` is read (it holds the seed
record) but never written.

USAGE
-----
    ./high_res_sweep.sh --plan              # print the three points, run nothing
    ./high_res_sweep.sh                     # the actual sweep (one child per point)
    ./high_res_sweep.sh --no-chain          # freeze sigma at the 30k seed
    ./high_res_sweep.sh --family ladder     # the 30k shape instead of strip-12
    ./high_res_sweep.sh --targets 40000     # a single point

Exit codes: 0 = every point ran and stayed self-consistent; 1 = a point failed
or fell outside the Q bar; 2 = refused before running (bad out dir, mesh above
the hard free-edge cap, or an estimated factor that does not fit in RAM).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

# One thread per process: the sweep is a memory story, not a throughput story,
# and BLAS thread pools inflate RSS by tens of MiB in ways that vary run to run.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
             "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import rung4_routeC_probe as r4          # noqa: E402
import routeC_mesh_probe as mp           # noqa: E402

# ---------------------------------------------------------------- constants --

ALLOWED_OUT_DIR = HERE / "out_highres"
FORBIDDEN_OUT_DIRS = (ROOT / "out", HERE / "out", HERE / "out_mesh",
                      HERE / "out_rung4")
REPORT_DIR = HERE / "out_mesh"

PROBE = "high_res_sweep"
PREPARED_NOT_RUN = (
    "written by a dispatch forbidden to run it: this file has not been "
    "executed, no solve has been performed, and no measured value below "
    "originated from it"
)

TARGET_30K = 30000
TARGETS = (40000, 50000, 60000)

MAX_FREE_E_HARD = 120000          # absolute refusal, well above the 60k point
MEM_HEADROOM = 0.5                # estimated factor memory must fit in half of MemAvailable
SHIFT_FACTOR = r4.C_SHIFT_FACTOR  # 0.999
BYTES_PER_NNZ = r4.BYTES_PER_NNZ  # 12

R_ANALYTIC = mp.R_ANALYTIC
Q_BAR = mp.Q_BAR

# Both anchors come from the ~30k record (30672 free edges) and are used ONLY
# for the pre-flight estimate; nothing measured is derived from them.
FILL_PER_ROW_REF = 148.1
REF_DOF = 38647
DOF_PER_FREE_E_REF = 38647 / 28980.0

# A fixed cross-section plus a growing air box: strip 12 (rung-0) and an 8-4-4
# z stack, which is exactly what "free_e = 48*nx - 44" pins (see docstring).
FAMILIES = {
    "s12": (12, (8, 4, 4)),
    "rung0": (12, (8, 4, 4)),
}
LADDER_FAMILY = "ladder"
LADDER_Y_RATIO = 22 / 36.0
LADDER_Z_RATIO = 20 / 36.0

DEFAULT_OUTDIR = ALLOWED_OUT_DIR


# ------------------------------------------------------------------ planning --

def family_law(strip, z):
    """Derive free_e(nx) for a fixed cross-section and cross-check the closed form.

    Two evaluations of ``r4.mesh_counts`` are enough because the dependence is
    affine in nx; the closed form is then checked against it so a change in
    ``mesh_counts`` cannot silently invalidate the plan.
    """
    z = tuple(int(v) for v in z)
    nz = 1 + sum(z)
    a = r4.mesh_counts(strip, 10, z)
    b = r4.mesh_counts(strip, 19, z)
    slope = (b["free_e"] - a["free_e"]) / float(b["nx"] - a["nx"])
    intercept = a["free_e"] - slope * a["nx"]
    slope_closed = 3 * (nz - 1)
    intercept_closed = 2 - 2 * nz - strip
    agrees = (abs(slope - slope_closed) < 1e-9
              and abs(intercept - intercept_closed) < 1e-9)
    return {
        "strip": int(strip),
        "z": list(z),
        "nz": int(nz),
        "slope": float(slope),
        "intercept": float(intercept),
        "slope_closed_form": float(slope_closed),
        "intercept_closed_form": float(intercept_closed),
        "law": "free_e = %g * nx + (%g)" % (slope, intercept),
        "agrees_with_closed_form": bool(agrees),
    }


def plan_fixed(target, strip, z, law):
    """Closest admissible (nx, yair) to `target` for a fixed cross-section.

    Admissibility: yair >= 1 and an integer yair, i.e. (nx - 1 - strip) even.
    Scans +/-5 around the law's real-valued solution and takes the closest.
    """
    nx0 = (target - law["intercept"]) / law["slope"]
    best = None
    for nx in range(int(nx0) - 5, int(nx0) + 6):
        if nx <= strip + 1:
            continue
        if (nx - 1 - strip) % 2 != 0:
            continue
        yair = (nx - 1 - strip) // 2
        if yair < 1:
            continue
        counts = r4.mesh_counts(strip, yair, z)
        if counts["nx"] != nx:
            continue
        key = abs(counts["free_e"] - target)
        if best is None or key < best[0]:
            best = (key, nx, yair, counts)
    if best is None:
        mp.refuse("no admissible nx for target %d with strip=%d z=%s"
                  % (target, strip, list(z)))
    _, nx, yair, counts = best
    return nx, yair, counts


def plan_ladder(target):
    """The ~30k family: strip, yair and z all scale together (quadratic law)."""
    best = None
    for strip in range(8, 161):
        yair = max(1, int(round(strip * LADDER_Y_RATIO)))
        z0 = max(1, int(round(strip * LADDER_Z_RATIO)))
        z = (z0, max(1, int(round(z0 * 0.5))), max(1, int(round(z0 * 0.55))))
        counts = r4.mesh_counts(strip, yair, z)
        key = abs(counts["free_e"] - target)
        if best is None or key < best[0]:
            best = (key, strip, yair, z, counts)
    _, strip, yair, z, counts = best
    return strip, yair, z, counts


def estimate(n_dof):
    """Pre-flight ESTIMATE of the sparse factor. NEVER overwrites a measurement."""
    fill = FILL_PER_ROW_REF * math.sqrt(max(int(n_dof), 1) / float(REF_DOF))
    nnz = fill * n_dof
    return {
        "fill_per_row_est": round(fill, 2),
        "factor_nnz_est": int(nnz),
        "factor_gb_est": round(nnz * BYTES_PER_NNZ / 1e9, 3),
        "basis": ("n_dof from free_e * %.4f; fill/row from %.1f at n_dof=%d "
                  "scaling as sqrt(n_dof); %d bytes/nnz"
                  % (DOF_PER_FREE_E_REF, FILL_PER_ROW_REF, REF_DOF, BYTES_PER_NNZ)),
    }


def plan_point(target, family):
    """Everything known about one point BEFORE it runs."""
    if family == LADDER_FAMILY:
        strip, yair, z, counts = plan_ladder(target)
        law = family_law(strip, z)
        law_note = ("ladder family: strip, yair and z scale together, so free_e "
                    "grows roughly quadratically in strip and the flat "
                    "48*nx-44 law does not apply")
    else:
        if family not in FAMILIES:
            mp.refuse("unknown --family %r (known: %s, %s)"
                      % (family, sorted(FAMILIES), LADDER_FAMILY))
        strip, z = FAMILIES[family]
        law = family_law(strip, z)
        nx, yair, counts = plan_fixed(target, strip, z, law)
        law_note = ("fixed cross-section: free_e is linear in nx only "
                    "(slope %g, intercept %g)" % (law["slope"], law["intercept"]))

    nx = counts["nx"]
    nz = counts["nz"]
    free_e = counts["free_e"]
    n_dof = int(round(free_e * DOF_PER_FREE_E_REF))
    est = estimate(n_dof)
    return {
        "target": int(target),
        "label": "hi%dk_nx%d" % (int(target) // 1000, nx),
        "family": family,
        "strip": int(strip),
        "yair": int(yair),
        "z": [int(v) for v in z],
        "mesh": "%d/%d/%s" % (strip, yair, "-".join(str(int(v)) for v in z)),
        "nx": int(nx),
        "nz": int(nz),
        "nodes": int(counts["nodes"]),
        "tris": int(counts["tris"]),
        "n_edges": int(counts["edges"]),
        "n_pec_edges": int(counts["n_pec"]),
        "free_e_expected": int(free_e),
        "free_e_nominal": int(target),
        "free_e_offset": int(free_e - target),
        "law": law["law"],
        "law_check": law,
        "law_note": law_note,
        "n_dof_estimate": n_dof,
        "est_fill_per_row": est["fill_per_row_est"],
        "est_factor_nnz": est["factor_nnz_est"],
        "est_factor_gb": est["factor_gb_est"],
        "estimate_basis": est["basis"],
    }


# ------------------------------------------------------------- pre-flight --

def mem_available_bytes():
    """MemAvailable from /proc/meminfo, or None when it cannot be read."""
    try:
        with open("/proc/meminfo", "r") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None


def preflight(pt, headroom, shim_mode):
    """Refuse a point that is over the hard cap or cannot plausibly fit in RAM."""
    if pt["free_e_expected"] > MAX_FREE_E_HARD:
        mp.refuse("%s: free_e %d exceeds the hard cap %d"
                  % (pt["label"], pt["free_e_expected"], MAX_FREE_E_HARD))

    avail = mem_available_bytes()
    checks = {
        "free_e_hard_cap": MAX_FREE_E_HARD,
        "free_e_expected": pt["free_e_expected"],
        "mem_available_gb": None if avail is None else round(avail / 2 ** 30, 2),
        "mem_headroom": float(headroom),
        "mem_limit_gb": None if avail is None else round(headroom * avail / 2 ** 30, 2),
        "est_factor_gb": pt["est_factor_gb"],
        "shim_mode": shim_mode,
        "dense_diag_bytes": None,
        "dense_cap_bytes": int(mp.DENSE_CAP_BYTES),
        "ok": True,
    }

    if avail is not None:
        limit_gb = headroom * avail / 2 ** 30
        if pt["est_factor_gb"] > limit_gb:
            mp.refuse("%s: estimated factor %.3f GB exceeds %.2f x MemAvailable "
                      "(%.2f GB); free it or lower the target"
                      % (pt["label"], pt["est_factor_gb"], headroom, limit_gb))

    if shim_mode == "off":
        # r4.build_problem takes two .toarray() maxima on n_edges x n_edges
        # sparse differences; with the shim off those are real dense arrays.
        dense = pt["n_edges"] ** 2 * 8
        checks["dense_diag_bytes"] = int(dense)
        if dense > mp.DENSE_CAP_BYTES:
            mp.refuse("%s: --shim off needs %.1f GB for a single n_edges x "
                      "n_edges diagnostic (%d^2*8) vs cap %.1f GB; use --shim auto"
                      % (pt["label"], dense / 2 ** 30, pt["n_edges"],
                         mp.DENSE_CAP_BYTES / 2 ** 30))
    else:
        checks["dense_diag_bytes"] = int(pt["n_edges"] ** 2 * 8)
    return checks


def check_out_dir(path, create=False):
    """Only out_highres/ is writable; out/, out_mesh/ and out_rung4/ are refused."""
    p = Path(path).expanduser().resolve()
    for forbidden in FORBIDDEN_OUT_DIRS:
        f = forbidden.resolve()
        if p == f or f in p.parents:
            mp.refuse("refusing to write into %s: that directory belongs to "
                      "another run (allowed: %s)" % (p, ALLOWED_OUT_DIR))
    allowed = ALLOWED_OUT_DIR.resolve()
    if p != allowed and allowed not in p.parents:
        mp.refuse("out dir must live under %s (got %s)" % (allowed, p))
    if create:
        (p / "points").mkdir(parents=True, exist_ok=True)
    return p


def print_plan(plan):
    print("plan: %d point(s), family %s" % (len(plan), plan[0]["family"]))
    print("%-16s %9s %9s %5s %5s %6s %9s %8s %10s %8s"
          % ("label", "target", "free_e", "off", "strip", "yair",
             "mesh(nx,nz)", "nodes", "est_fact_GB", "law_slope"))
    for pt in plan:
        print("%-16s %9d %9d %+5d %5d %6d %9s %8d %10.3f %8g"
              % (pt["label"], pt["target"], pt["free_e_expected"],
                 pt["free_e_offset"], pt["strip"], pt["yair"],
                 "%d,%d" % (pt["nx"], pt["nz"]), pt["nodes"],
                 pt["est_factor_gb"], pt["law_check"]["slope"]))
    for pt in plan:
        print("  %s: mesh %s  %s" % (pt["label"], pt["mesh"], pt["law"]))
    ok = all(pt["law_check"]["agrees_with_closed_form"] for pt in plan)
    print("  closed-form law check: %s" % ("agrees on every point" if ok else "MISMATCH"))
    print("  free_e here is the ACTUAL count from r4.mesh_counts, not the nominal "
          "target; the offset column is the difference.")


# --------------------------------------------------------------------- sigma --

def _find_num(obj, key):
    """Depth-first search for the first numeric value stored under `key`."""
    if isinstance(obj, dict):
        val = obj.get(key)
        if isinstance(val, bool):
            pass
        elif isinstance(val, (int, float)):
            return val
        for sub in obj.values():
            got = _find_num(sub, key)
            if got is not None:
                return got
    elif isinstance(obj, list):
        for sub in obj:
            got = _find_num(sub, key)
            if got is not None:
                return got
    return None


def seed_sigma(explicit=None, json_path=None, target=TARGET_30K):
    """sigma for the FIRST point: SHIFT_FACTOR x (beta_sq of the ~30k record).

    The record is found by scanning out_mesh/*.json and taking the one whose
    free_e is closest to `target` -- i.e. M4_fe30672.json (30672 free edges),
    the "30000 free edges in 0.69 s" run.  Nothing is hard-coded, so the seed
    follows the ladder if it is ever re-run.
    """
    if explicit is not None:
        return float(explicit), {
            "source": "--sigma (explicit)",
            "note": "seed given on the command line, not derived from out_mesh",
            "sigma": float(explicit),
        }

    if json_path is not None:
        candidates = [Path(json_path)]
    else:
        candidates = sorted(REPORT_DIR.glob("*.json"))
    if not candidates:
        mp.refuse("no JSON found in %s to seed sigma from; pass --sigma" % REPORT_DIR)

    recs = []
    for path in candidates:
        try:
            data = json.loads(Path(path).read_text())
        except (OSError, ValueError):
            continue
        free_e = _find_num(data, "free_e")
        beta_sq = _find_num(data, "beta_sq")
        if free_e is None or beta_sq is None or not beta_sq:
            continue
        recs.append({"path": str(path), "free_e": int(free_e),
                     "beta_sq": float(beta_sq)})
    if not recs:
        mp.refuse("none of %d JSON files in %s carries both free_e and beta_sq; "
                  "pass --sigma" % (len(candidates), REPORT_DIR))

    recs.sort(key=lambda r: (abs(r["free_e"] - target), r["free_e"]))
    best = recs[0]
    sigma = SHIFT_FACTOR * best["beta_sq"]
    return float(sigma), {
        "source": "nearest out_mesh record to %d free edges" % target,
        "record": best,
        "shift_factor": SHIFT_FACTOR,
        "sigma": float(sigma),
        "note": ("sigma = %.6f x %.9f (beta_sq of %s, free_e %d); each later "
                 "point chains 0.999 x the previous point's beta_sq, the same "
                 "convention the M1..M4 ladder used"
                 % (SHIFT_FACTOR, best["beta_sq"],
                    Path(best["path"]).name, best["free_e"])),
        "candidates_considered": len(recs),
    }


# ----------------------------------------------------------------- run point --

def run_point(pt, sigma, sigma_how, shim_mode):
    """Run ONE point in this process and return its full record.

    This is the only place a solve happens.  One process per point is the whole
    point of the parent/child split: ru_maxrss is a per-process high-water mark,
    so the peak RSS recorded here belongs to this mesh and nothing else.
    """
    started = time.time()
    rec = {
        "probe": PROBE,
        "prepared_not_run": PREPARED_NOT_RUN,
        "target": pt["target"],
        "label": pt["label"],
        "family": pt["family"],
        "mesh": pt["mesh"],
        "strip": pt["strip"],
        "yair": pt["yair"],
        "z": list(pt["z"]),
        "nx": pt["nx"],
        "nz": pt["nz"],
        "nodes": pt["nodes"],
        "tris": pt["tris"],
        "n_edges": pt["n_edges"],
        "n_pec_edges": pt["n_pec_edges"],
        "free_e_expected": pt["free_e_expected"],
        "free_e_nominal": pt["free_e_nominal"],
        "free_e_offset": pt["free_e_offset"],
        "law": pt["law"],
        "n_dof_estimate": pt["n_dof_estimate"],
        "est_factor_gb": pt["est_factor_gb"],
        "estimate_basis": pt["estimate_basis"],
        "sigma": float(sigma),
        "sigma_how": sigma_how,
        "shift_factor": SHIFT_FACTOR,
        "shim_mode": shim_mode,
        "anchor": None,
        "anchor_note": ("no dense anchor above ~3000 free edges: the dense QZ "
                        "reference refuses there, so the verdict is "
                        "SELF-CONSISTENCY only"),
        "environment": {
            "python": sys.version.split()[0],
            "scipy": mp.scipy.__version__,
            "mp_max_free_e": int(mp.MAX_FREE_E),
            "threads": "1",
        },
    }

    cfg = {"rung": -1, "role": pt["label"], "strip": int(pt["strip"]),
           "yair": int(pt["yair"]), "z": [int(v) for v in pt["z"]]}
    ctx = r4.load_context()
    ref = r4.analytic_reference(ctx)
    with mp.DenseShim(shim_mode):
        pb = r4.build_problem(cfg, ctx)
        route_c = r4.run_route_c(pb, ctx, ref, float(sigma), None)
    verdict = r4.verdict_of(route_c, None)

    wall = time.time() - started
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0

    # free_e as assembled, not as planned: prefer a value carried by the
    # problem, fall back to the deterministic mesh_counts.
    measured = None
    measured_src = None
    for attr in ("free_e", "n_free_e", "n_free_edges"):
        val = getattr(pb, attr, None)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            measured = int(val)
            measured_src = "problem.%s" % attr
            break
    if measured is None:
        measured = int(r4.mesh_counts(pt["strip"], pt["yair"], pt["z"])["free_e"])
        measured_src = "r4.mesh_counts (deterministic, problem exposes no free_e)"

    R_extracted = route_c.get("R")
    Q = None if R_extracted is None else float(R_extracted) / R_ANALYTIC
    residual = route_c.get("residual")
    resid_ok = residual is not None and residual <= r4.MAX_REL_RESIDUAL
    q_ok = Q is not None and abs(Q - 1.0) <= Q_BAR
    ok = bool(resid_ok and q_ok)

    rec.update({
        "free_e_measured": measured,
        "free_e_measured_source": measured_src,
        "free_e_matches_plan": measured == pt["free_e_expected"],
        "n_dof": route_c.get("n_dof", rec["n_dof_estimate"]),
        "beta_sq": route_c.get("beta_sq"),
        "R_extracted": R_extracted,
        "R_extracted_note": ("R as extracted from the sparse eigenpair "
                             "(route_c['R']); compare against R_ANALYTIC, not "
                             "against another R_extracted"),
        "R_analytic": R_ANALYTIC,
        "R_rel_error": None if R_extracted is None else (float(R_extracted) - R_ANALYTIC) / R_ANALYTIC,
        "Q": Q,
        "Q_minus_1": None if Q is None else Q - 1.0,
        "Q_bar": Q_BAR,
        "Q_inside_bar": bool(q_ok),
        "eps_eff": route_c.get("eps_eff"),
        "corr_ey": route_c.get("corr_ey"),
        "corr_ez_vv": route_c.get("corr_ez_vv"),
        "eigenvalue": route_c.get("eigenvalue"),
        "residual": residual,
        "max_rel_residual": r4.MAX_REL_RESIDUAL,
        "residual_in_enlarged_pencil": route_c.get("residual_in_enlarged_pencil"),
        "x2_matches_DcTx1_rel": route_c.get("x2_matches_DcTx1_rel"),
        "nnz_S": route_c.get("nnz_S"),
        "nnz_S_of_n2": route_c.get("nnz_S_of_n2"),
        "factor_nnz": route_c.get("factor_nnz"),
        "fill_per_row": route_c.get("fill_per_row"),
        "factor_memory_gb_measured": route_c.get("factor_memory_gb_measured"),
        "t_splu_s": route_c.get("t_splu_s"),
        "t_eigsh_s": route_c.get("t_eigsh_s"),
        "opinv_calls": route_c.get("opinv_calls"),
        "peak_rss_mib": round(peak_rss, 1),
        "peak_rss_note": ("resource.getrusage(RUSAGE_SELF).ru_maxrss of this "
                          "process only; one child per point so the high-water "
                          "mark cannot be inherited"),
        "wall_s": round(wall, 2),
        "verdict": verdict,
        "status": "ok" if ok else "inconsistent",
        "ok": ok,
        "route_c": route_c,
    })

    if not rec["free_e_matches_plan"]:
        print("  !! free_e assembled = %d but planned %d"
              % (measured, pt["free_e_expected"]))
    print("  beta_sq=%.6f  R_extracted=%.9f  |Q-1|=%.4f  residual=%.2e  "
          "peak RSS %.1f MiB  wall %.1f s"
          % (rec["beta_sq"] or float("nan"), R_extracted or float("nan"),
             abs(Q - 1.0) if Q is not None else float("nan"),
             residual if residual is not None else float("nan"),
             peak_rss, wall))
    return rec


def write_point(rec, outdir):
    path = Path(outdir) / "points" / ("%s.json" % rec["label"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=2, default=r4._json_default) + "\n")
    return path


# -------------------------------------------------------------------- sweep --

def run_sweep(plan, outdir, seed, seed_how, args):
    """Walk the plan, one child process per point, chaining sigma as we go."""
    records = []
    sigma = float(seed)
    how = dict(seed_how)
    started = time.time()

    print("\nsigma seed: %.6f" % sigma)
    print("  %s" % how.get("note", how.get("source", "explicit")))
    if not args.chain:
        print("  --no-chain: sigma will be held at this value for every point")

    for k, pt in enumerate(plan, 1):
        checks = preflight(pt, args.mem_headroom, args.shim)
        print("\n=== point %d/%d: %s  mesh %s  free_e %d (%+d vs %d) ==="
              % (k, len(plan), pt["label"], pt["mesh"], pt["free_e_expected"],
                 pt["free_e_offset"], pt["target"]))
        print("    nx=%d nz=%d nodes=%d edges=%d n_pec=%d  est factor %.3f GB "
              "(MemAvailable %.2f GB, headroom %.2f)"
              % (pt["nx"], pt["nz"], pt["nodes"], pt["n_edges"],
                 pt["n_pec_edges"], pt["est_factor_gb"],
                 checks["mem_available_gb"] if checks["mem_available_gb"] else -1.0,
                 args.mem_headroom))
        print("    sigma %.6f  (%s)" % (sigma, how.get("source", "explicit")))

        cmd = [sys.executable, "-u", str(Path(__file__).resolve()),
               "--one", str(pt["target"]),
               "--family", args.family,
               "--sigma", repr(float(sigma)),
               "--sigma-how", str(how.get("note", how.get("source", "explicit"))),
               "--outdir", str(outdir),
               "--shim", args.shim,
               "--mem-headroom", repr(float(args.mem_headroom))]

        t0 = time.time()
        proc = subprocess.run(cmd)
        child_wall = time.time() - t0
        path = Path(outdir) / "points" / ("%s.json" % pt["label"])

        rec = None
        if path.exists():
            try:
                rec = json.loads(path.read_text())
            except ValueError:
                rec = None
        if proc.returncode != 0 or rec is None:
            print("point %d FAILED: child exit %d after %.1f s (no usable record)"
                  % (k, proc.returncode, child_wall))
            records.append({"label": pt["label"], "target": pt["target"],
                            "mesh": pt["mesh"], "free_e_expected": pt["free_e_expected"],
                            "sigma": sigma, "status": "failed",
                            "child_exit": proc.returncode, "ok": False})
            continue

        rec["preflight"] = checks
        rec["child_exit"] = proc.returncode
        rec["child_wall_s"] = round(child_wall, 2)
        records.append(rec)
        print("point %d done: beta=%.6f  R_extracted=%.9f  |Q-1|=%.4f  peak RSS "
              "%.1f MiB  wall %.1f s%s"
              % (k, rec.get("beta_sq") or float("nan"),
                 rec.get("R_extracted") or float("nan"),
                 abs((rec.get("Q") or float("nan")) - 1.0),
                 rec.get("peak_rss_mib") or float("nan"),
                 child_wall,
                 "" if rec.get("ok") else "   [INCONSISTENT]"))

        if args.chain and rec.get("beta_sq"):
            prev = float(rec["beta_sq"])
            sigma = SHIFT_FACTOR * prev
            how = {"source": "chained: 0.999 x %s beta_sq" % pt["label"],
                   "previous": {"label": pt["label"], "beta_sq": prev},
                   "shift_factor": SHIFT_FACTOR, "sigma": sigma,
                   "note": ("sigma = 0.999 x %.6f (beta_sq of %s), the "
                            "convention the M1..M4 ladder used"
                            % (prev, pt["label"]))}

    return records, time.time() - started, how


# ------------------------------------------------------------------- payload --

def build_payload(args, plan, records, seed, seed_how, wall, outdir, final_how):
    done = [r for r in records if r.get("status") == "ok" and r.get("R_extracted")]
    Rs = [float(r["R_extracted"]) for r in done]

    if len(Rs) >= 2:
        first, last = Rs[0], Rs[-1]
        rel = (last - first) / first if first else 0.0
        if abs(rel) < 1e-9:
            direction = "flat"
        elif rel > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
    else:
        rel, direction = None, "insufficient points"

    interior = None
    if len(Rs) >= 2:
        devs = [(abs(r - R_ANALYTIC) / R_ANALYTIC, r["label"]) for r in done]
        devs.sort()
        interior = {"label": devs[-1][1], "max_abs_rel_dev": devs[-1][0]}

    peak_rss = [r.get("peak_rss_mib") for r in records if r.get("peak_rss_mib")]
    factor_gb = [r.get("factor_memory_gb_measured") for r in records
                 if r.get("factor_memory_gb_measured")]

    return {
        "probe": PROBE,
        "script": str(Path(__file__).resolve()),
        "prepared_not_run": PREPARED_NOT_RUN,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "environment": {
            "python": sys.version.split()[0],
            "scipy": mp.scipy.__version__,
            "mp_max_free_e": int(mp.MAX_FREE_E),
            "threads": "1",
            "r_analytic": R_ANALYTIC,
            "q_bar": Q_BAR,
        },
        "family": {
            "requested": args.family,
            "mesh_order": "strip/yair/z0-z1-z2",
            "s12_shape": "fixed strip 12 (rung-0) and 8-4-4 z: free_e = 48*nx - 44",
            "ladder_shape": ("30k family: yair/strip=%.3f, z/strip=%.3f; free_e "
                             "quadratic in strip" % (LADDER_Y_RATIO, LADDER_Z_RATIO)),
            "laws": {pt["label"]: pt["law_check"] for pt in plan},
        },
        "seed_sigma": {"value": seed, "how": seed_how, "final_chain_state": final_how},
        "chain": bool(args.chain),
        "targets": [pt["target"] for pt in plan],
        "plan": plan,
        "thresholds": {
            "max_free_e_hard": MAX_FREE_E_HARD,
            "mem_headroom": args.mem_headroom,
            "max_rel_residual": r4.MAX_REL_RESIDUAL,
            "q_bar": Q_BAR,
            "shim_mode": args.shim,
        },
        "points": records,
        "trend": {
            "n_points_ok": len(done),
            "n_points_failed": len(records) - len(done),
            "R_direction": direction,
            "R_rel_change_first_to_last": rel,
            "R_values": Rs,
            "worst_deviation_from_analytic": interior,
            "n_Q_inside_bar": sum(1 for r in done if r.get("Q_inside_bar")),
        },
        "totals": {
            "peak_rss_mib_max": max(peak_rss) if peak_rss else None,
            "factor_memory_gb_max_measured": max(factor_gb) if factor_gb else None,
            "wall_s_total": round(wall, 2),
            "all_self_consistent": bool(done) and all(r.get("ok") for r in done)
                                   and len(done) == len(records),
        },
        "notes": {
            "no_dense_anchor": ("anchor=None at every point: the dense QZ "
                                "reference refuses above ~3000 free edges, so "
                                "each verdict is SELF-CONSISTENCY (residual + "
                                "enlarged-pencil + Q bar), not an eigenvalue "
                                "comparison"),
            "why_not_routeC_mesh_probe": ("mp.MAX_FREE_E = %d refuses these "
                                          "meshes in probe_once. That guard is "
                                          "untouched; this script calls "
                                          "r4.build_problem / r4.run_route_c "
                                          "directly and substitutes its own "
                                          "MemAvailable pre-flight."
                                          % mp.MAX_FREE_E),
            "dense_shim": ("r4.build_problem takes two toarray() maxima on "
                           "n_edges x n_edges differences; --shim auto must "
                           "stay on for the 50k and 60k points"),
            "anisotropy": ("strip and z are fixed while yair grows, so the air "
                           "box gets more elongated in y every point; y-drift in "
                           "R cannot be separated from aspect-ratio drift here"),
            "free_e_offset": ("nominal targets are unreachable exactly: nx must "
                              "be odd, so each point lands a few edges above its "
                              "target (offsets are printed per point)"),
            "prepared_only": PREPARED_NOT_RUN,
        },
        "outputs": {
            "points_dir": str(Path(outdir) / "points"),
            "payload": str(Path(outdir) / "high_res_sweep.json"),
        },
    }


def print_summary(payload):
    print("\n--- sweep summary ---")
    print("%-16s %8s %9s %10s %9s %7s %8s %s"
          % ("label", "free_e", "sigma", "beta_sq", "R_extracted", "|Q-1|",
             "RSS(MiB)", "status"))
    for r in payload["points"]:
        Q = r.get("Q")
        print("%-16s %8s %9s %10s %13s %7s %8s %s"
              % (r.get("label"), r.get("free_e_measured", "-"),
                 ("%.3f" % r["sigma"]) if r.get("sigma") else "-",
                 ("%.4f" % r["beta_sq"]) if r.get("beta_sq") else "-",
                 ("%.9f" % r["R_extracted"]) if r.get("R_extracted") else "-",
                 ("%.4f" % abs(Q - 1.0)) if Q is not None else "-",
                 r.get("peak_rss_mib", "-"), r.get("status", "?")))
    t = payload["trend"]
    print("\nR direction first->last: %s (rel change %s)"
          % (t["R_direction"],
             "n/a" if t["R_rel_change_first_to_last"] is None
             else "%.3e" % t["R_rel_change_first_to_last"]))
    print("points ok/failed: %d/%d   inside Q bar: %d"
          % (t["n_points_ok"], t["n_points_failed"], t["n_Q_inside_bar"]))
    tot = payload["totals"]
    print("peak RSS max: %s MiB   factor memory max: %s GB   wall: %.1f s"
          % (tot["peak_rss_mib_max"], tot["factor_memory_gb_max_measured"],
             tot["wall_s_total"]))
    print("all self-consistent: %s" % tot["all_self_consistent"])
    print("payload: %s" % payload["outputs"]["payload"])


# ----------------------------------------------------------------------- cli --

def parse_targets(text):
    out = []
    for piece in str(text).split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            value = int(piece)
        except ValueError:
            mp.refuse("bad --targets entry %r (want comma-separated integers)" % piece)
        if value <= 0:
            mp.refuse("bad --targets entry %d (must be positive)" % value)
        out.append(value)
    if not out:
        mp.refuse("--targets is empty")
    return out


def _main(args):
    check_out_dir(args.outdir, create=False)

    if args.one is not None:
        if args.sigma is None:
            mp.refuse("--one requires an explicit --sigma: a child process must "
                      "never guess its own interior shift")
        outdir = check_out_dir(args.outdir, create=True)
        pt = plan_point(args.one, args.family)
        checks = preflight(pt, args.mem_headroom, args.shim)
        print("one-shot point: %s  mesh %s  free_e %d (planned)"
              % (pt["label"], pt["mesh"], pt["free_e_expected"]))
        print("  est factor %.3f GB; MemAvailable %s GB; headroom %.2f"
              % (pt["est_factor_gb"],
                 checks["mem_available_gb"], args.mem_headroom))
        rec = run_point(pt, args.sigma,
                        args.sigma_how or "explicit --sigma", args.shim)
        rec["preflight"] = checks
        path = write_point(rec, outdir)
        print("wrote %s" % path)
        return 0 if rec.get("ok") else 1

    targets = parse_targets(args.targets)
    plan = [plan_point(t, args.family) for t in targets]
    print_plan(plan)

    if args.plan:
        print("\n--plan: nothing was run. sigma is resolved at run time from "
              "%s (nearest record to %d free edges, x %.3f)."
              % (REPORT_DIR, TARGET_30K, SHIFT_FACTOR))
        return 0

    seed, seed_how = seed_sigma(args.sigma, args.sigma_json)
    outdir = check_out_dir(args.outdir, create=True)
    records, wall, final_how = run_sweep(plan, outdir, seed, seed_how, args)
    payload = build_payload(args, plan, records, seed, seed_how, wall, outdir,
                            final_how)
    path = Path(outdir) / "high_res_sweep.json"
    path.write_text(json.dumps(payload, indent=2, default=r4._json_default) + "\n")
    print_summary(payload)
    return 0 if payload["totals"]["all_self_consistent"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="high_res_sweep.py",
        description=("40k / 50k / 60k sparse Route-C sweep. PREPARED, NOT RUN: "
                     "this file has never been executed."),
        epilog=("exit 0 = every point ran and stayed self-consistent; "
                "1 = a point failed or fell outside the Q bar; "
                "2 = refused before running"))
    ap.add_argument("--targets", default=",".join(str(t) for t in TARGETS),
                    help="comma-separated nominal free-edge targets "
                         "(default: %(default)s)")
    ap.add_argument("--family", default="s12",
                    help="mesh family: s12/rung0 (fixed strip 12 + 8-4-4, the "
                         "48*nx-44 law) or ladder (the ~30k shape)")
    ap.add_argument("--plan", action="store_true",
                    help="print the plan and the derived laws, run nothing")
    ap.add_argument("--one", type=int, default=None, metavar="TARGET",
                    help="run a single point (internal: the parent calls this "
                         "once per point); requires --sigma")
    ap.add_argument("--sigma", type=float, default=None,
                    help="interior shift; seeds the sweep, and is mandatory with "
                         "--one")
    ap.add_argument("--sigma-json", default=None,
                    help="seed sigma from this record instead of scanning %s"
                         % REPORT_DIR)
    ap.add_argument("--sigma-how", default=None,
                    help="provenance string recorded with the point's sigma")
    ap.add_argument("--no-chain", action="store_true",
                    help="hold sigma at the seed instead of chaining "
                         "0.999 * previous beta_sq")
    ap.add_argument("--shim", default="auto", choices=("auto", "on", "off"),
                    help="r4 dense-diagnostic shim (default: %(default)s; 'off' "
                         "is refused when a diagnostic would exceed the cap)")
    ap.add_argument("--mem-headroom", type=float, default=MEM_HEADROOM,
                    help="refuse a point whose estimated factor exceeds this "
                         "fraction of MemAvailable (default: %(default)s)")
    ap.add_argument("--outdir", default=str(DEFAULT_OUTDIR),
                    help="output directory (default: %(default)s; must live "
                         "under out_highres/)")
    args = ap.parse_args(argv)
    args.chain = not args.no_chain

    try:
        return _main(args)
    except mp.Refused as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
