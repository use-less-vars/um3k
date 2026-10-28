"""Five-rung convergence ladder of the anchor, STEP 2/3/4 driver.

Implements, in order and separately invocable:

  * STEP 2 -- the driven ladder of section 1.3 (ny = 16, 32, 64, 128, 256 with
    nx = ny/8) through the live ``emfit.mode2d.solve_modes``, classified by the
    AMENDMENT v2 rule (section 8.4 of the pre-registration: drop a candidate
    whose ``|eps_eff - 1| <= 1e-8``, require ``log10(D/R) >= 6`` with
    ``D = max dropped |curl_ratio|`` and ``R = min retained |curl_ratio|``,
    count stays ``k = 16``).  Each level is written to ``out/level<N>.json``
    immediately after that level finishes, before the next level starts.
  * STEP 3 -- the secondary mixed gate of section 4.4 at levels 1, 2 and 3
    only, with ``dense=None`` so the ``_MIXED_DENSE_MAX`` cap decides.
  * STEP 4 -- the section 6 negative control (geometry B, ``t = b/8``).

The script imports and calls the live solver; it never rebuilds, mirrors or
re-derives the discrete pencil and never calls an eigensolver of its own.  It
computes no slope and issues no verdict beyond the per-mode contamination flag
(``|beta_h - beta_ref| / beta_ref > 0.5``) and the ``|move| < 1e-6`` void test
of section 6.4.

Usage: ``python ladder.py driven 1 2 3 4 5`` / ``python ladder.py mixed 1 2 3``
/ ``python ladder.py control``.
"""

import json
import resource
import sys
import time
from pathlib import Path

import numpy as np


def _repo_root(start):
    """First directory at or above ``start`` that contains ``emfit/``."""
    here = Path(start).resolve()
    for cand in (here, *here.parents):
        if (cand / "emfit").is_dir():
            return cand
    raise RuntimeError("no emfit/ above " + str(start))


ROOT = _repo_root(Path(__file__).parent)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import emfit.mode2d as mode2d  # noqa: E402
from anchor_reference import (  # noqa: E402
    A, B, BETA_REF_DOC, EPS_EFF_DOC, EPS_R, K0, T, diagnose, poles, solve_ref,
)

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

LEVEL_NY = {1: 16, 2: 32, 3: 64, 4: 128, 5: 256}

# --- frozen parameters -----------------------------------------------------
SIGMA_MULT = 0.5                       # section 8.3 of the document
SIGMA = SIGMA_MULT * K0 * K0           # 990434.54085811926
K_CAND = 16                            # section 4.3 rule 1 / 8.4
EPS_EFF_TOL = 1e-8                     # section 8.4, v2 replacement rule
GAP_DECADES = 6.0                      # section 8.4, v2 separation guard
ENDPOINT = float(np.sqrt(EPS_R) * K0)  # 1990.411556294948
LOWEST_REF = float(BETA_REF_DOC[2])    # 944.6029788248537
CONTAMINATION = 0.5                    # task-level flag, >50 % deviation
VOID_MOVE = 1e-6                       # section 6.4

# --- geometry B (section 6): the slab is half as thick ---------------------
T_B = B / 8.0                          # 0.0009765625
BETA_REF_B = {
    1: 1370.1426441407846,
    2: 1220.4777421405508,
    3: 868.5400506458038,
}


def rule(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78, flush=True)


def peak_rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def build_mesh(ny, t):
    """Level mesh of section 1.3/1.4 for slab thickness ``t``."""
    nx = ny // 8
    h = B / ny
    xs = A * np.arange(nx + 1) / nx
    ys = B * np.arange(ny + 1) / ny
    mesh = mode2d.structured_mesh(xs, ys)
    if not np.any(ys == t):
        raise SystemExit("interface y = t is not a node line at ny = %d" % ny)
    eps_r_callable = lambda c: np.where(c[:, 1] < t, EPS_R, 1.0)   # noqa: E731
    boundaries = (
        lambda P: P[:, 1] == 0.0,      # y = 0
        lambda P: P[:, 1] == B,        # y = b
        lambda P: P[:, 0] == 0.0,      # x = 0
        lambda P: P[:, 0] == A,        # x = a
    )
    return mesh, eps_r_callable, boundaries, nx, h


def candidate_rows(res):
    """Every candidate of a ``Mode2D``, ``beta_sq`` descending."""
    rows = []
    pairs = list(zip(res.candidates, res.curl_ratio))
    pairs.sort(key=lambda p: (-p[0][0], p[1]))
    for i, ((bsq, ee), cr) in enumerate(pairs):
        rows.append({
            "index": i,
            "beta": float(np.sqrt(bsq)) if bsq >= 0.0 else None,
            "beta_sq": float(bsq),
            "eps_eff": float(ee),
            "curl_ratio": float(cr),
            "abs_curl_ratio": abs(float(cr)),
        })
    return rows


def apply_v2(rows):
    """AMENDMENT v2 classification (section 8.4).  No tuning, no fallback."""
    dropped, retained = [], []
    for r in rows:
        if abs(r["eps_eff"] - 1.0) <= EPS_EFF_TOL:
            r["kept"] = False
            r["drop_reason"] = "|eps_eff - 1| <= %.0e (gradient/substrate, v2 8.4)" % EPS_EFF_TOL
            dropped.append(r)
        else:
            r["kept"] = True
            r["drop_reason"] = None
            retained.append(r)
    retained.sort(key=lambda r: -r["beta_sq"])

    D = max((r["abs_curl_ratio"] for r in dropped), default=None)
    R = min((r["abs_curl_ratio"] for r in retained), default=None)
    vacuous = (not dropped) or (not retained)
    decades, note = None, None
    if vacuous:
        note = "vacuous: %s empty" % ("dropped set" if not dropped else "retained set")
    elif R is None or D is None:
        note = "undefined"
    elif R > 0.0:
        decades = float(np.log10(D / R)) if D > 0.0 else None
        if decades is None:
            note = "D == 0: no dropped candidate carries any curl"
    else:
        note = "R == 0: a retained candidate carries no curl"
    return dropped, retained, D, R, decades, vacuous, note


def classify(mesh, res, tag, beta_ref, eps_eff_ref):
    """Full audit record for one live solve at one level."""
    rows = candidate_rows(res)
    dropped, retained, D, R, decades, vacuous, note = apply_v2(rows)
    notes = []
    if len(retained) < 3:
        notes.append("FEWER THAN THREE RETAINED (%d): section 5 forbids "
                     "extrapolating missing modes" % len(retained))

    matched = []
    for i in range(3):
        if i < len(retained):
            r = retained[i]
            beta = r["beta"]
            e = abs(beta - beta_ref[i]) / beta_ref[i]
            matched.append({
                "order": i + 1,
                "beta": beta,
                "beta_sq": r["beta_sq"],
                "eps_eff": r["eps_eff"],
                "curl_ratio": r["curl_ratio"],
                "beta_ref": beta_ref[i],
                "eps_eff_ref": eps_eff_ref[i],
                "rel_error": e,
                "contaminated_gt_50pct": bool(e > CONTAMINATION),
            })
        else:
            matched.append({
                "order": i + 1, "beta": None, "beta_ref": beta_ref[i],
                "rel_error": None, "contaminated_gt_50pct": None,
            })

    in_trio = {id(r) for r in retained[:3]}
    surplus = [dict(r, role="surplus: %0.6f < beta < %0.6f" % (LOWEST_REF, ENDPOINT))
               for r in retained
               if id(r) not in in_trio
               and r["beta"] is not None
               and LOWEST_REF < r["beta"] < ENDPOINT]
    above = [dict(r, role="beta above sqrt(eps_r)*k0")
             for r in retained
             if r["beta"] is not None and r["beta"] > ENDPOINT]
    if above:
        notes.append("RETAINED CANDIDATE ABOVE THE ENDPOINT %.6f: section 5 "
                     "makes this a run failure" % ENDPOINT)
    contam = [m["order"] for m in matched
              if m["contaminated_gt_50pct"] is True]

    return {
        "tag": tag,
        "filter": {
            "amendment": "v2 (section 8.4)",
            "k_candidates": K_CAND,
            "drop_rule": "|eps_eff - 1| <= %.0e" % EPS_EFF_TOL,
            "gap_rule": "log10(D/R) >= %.0f, D = max dropped |curl_ratio|, "
                        "R = min retained |curl_ratio|" % GAP_DECADES,
            "decades_required": GAP_DECADES,
            "gap_satisfied": (None if decades is None else bool(decades >= GAP_DECADES)),
        },
        "candidates_all": rows,
        "retained": retained,
        "dropped": dropped,
        "n_candidates": len(rows),
        "n_retained": len(retained),
        "n_dropped": len(dropped),
        "largest_dropped_abs_curl": D,
        "smallest_retained_abs_curl": R,
        "separation_decades": decades,
        "separation_vacuous": vacuous,
        "separation_note": note,
        "matched_by_order": matched,
        "surplus_candidates": surplus,
        "n_surplus": len(surplus),
        "above_endpoint": above,
        "contamination_flag_orders": contam,
        "contaminated": bool(contam),
        "notes": notes,
    }


def dump(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print("  -> wrote %s (%d bytes)" % (path.relative_to(ROOT), path.stat().st_size))


def run_driven(levels):
    beta_ref = list(BETA_REF_DOC)
    eps_eff_ref = list(EPS_EFF_DOC)
    for L in levels:
        rule("DRIVEN LADDER, LEVEL %d (ny = %d, nx = %d)" % (L, LEVEL_NY[L], LEVEL_NY[L] // 8))
        ny = LEVEL_NY[L]
        t0 = time.time()
        mesh, eps_call, boundaries, nx, h = build_mesh(ny, T)
        res = mode2d.solve_modes(mesh, K0, SIGMA, eps_r=eps_call,
                                 boundaries=boundaries, k=K_CAND)
        rec = classify(mesh, res, "level%d" % L, beta_ref, eps_eff_ref)
        wall = time.time() - t0
        payload = {
            "step": "2 (driven ladder)",
            "level": L,
            "geometry": "A (t = b/4)",
            "ny": ny,
            "nx": nx,
            "h": h,
            "h_over_b": h / B,
            "h_over_b_sq": (h / B) ** 2,
            "t": T,
            "b": B,
            "a": A,
            "eps_r": EPS_R,
            "k0": K0,
            "f_hz": float(K0 * 299792458.0 / (2.0 * np.pi)),
            "sigma": SIGMA,
            "sigma_mult": SIGMA_MULT,
            "n_nodes": int(mesh.n_nodes),
            "n_tris": int(mesh.n_tris),
            "n_edges": int(mesh.n_edges),
            "n_pec": int(res.n_pec),
            "n_free": int(res.n_dof),
            "n_free_check": int(mesh.n_edges - res.n_pec),
            "solver_chosen_index": int(res.chosen),
            "solver_beta": float(res.beta),
            "solver_eps_eff": float(res.eps_eff),
            "solver_residual": float(res.residual),
            "solver_module": mode2d.__file__,
            "wall_time_s": wall,
            "peak_rss_mb": peak_rss_mb(),
            "classification": rec,
        }
        dump(OUT / ("level%d.json" % L), payload)
        for m in rec["matched_by_order"]:
            print("  mode %d  beta %s  rel.err %s%s"
                  % (m["order"],
                     "%.6f" % m["beta"] if m["beta"] is not None else "n/a",
                     "%.3e" % m["rel_error"] if m["rel_error"] is not None else "n/a",
                     "   CONTAMINATED(>50%)" if m["contaminated_gt_50pct"] else ""))
        print("  retained %d / dropped %d ; separation %s decades (%s) ; surplus %d"
              % (rec["n_retained"], rec["n_dropped"],
                 "n/a" if rec["separation_decades"] is None
                 else "%.2f" % rec["separation_decades"],
                 rec["separation_note"] or "computed", rec["n_surplus"]))
        for n in rec["notes"]:
            print("  NOTE:", n)


def run_mixed(levels):
    """STEP 3: secondary mixed gate at levels 1-3, dense=None (never True)."""
    l3 = json.loads((OUT / "level3.json").read_text())
    e3 = {m["order"]: m["rel_error"] for m in l3["classification"]["matched_by_order"]}
    for L in levels:
        rule("MIXED GATE (section 4.4), LEVEL %d" % L)
        if L > 3:
            print("  refused: section 4.4(a) limits this path to levels 1-3")
            continue
        ny = LEVEL_NY[L]
        t0 = time.time()
        mesh, eps_call, boundaries, nx, h = build_mesh(ny, T)
        res = mode2d.solve_modes_mixed(mesh, K0, 1.0, eps_r=eps_call,
                                       boundaries=boundaries, k=8,
                                       dense=None)          # cap decides
        rec = classify(mesh, res, "mixed_level%d" % L,
                       list(BETA_REF_DOC), list(EPS_EFF_DOC))
        wall = time.time() - t0
        comp = []
        for m in rec["matched_by_order"]:
            tol = e3.get(m["order"])
            if m["rel_error"] is None or tol is None:
                comp.append({"order": m["order"], "agrees": None})
                continue
            comp.append({
                "order": m["order"],
                "mixed_rel_error": m["rel_error"],
                "driven_level3_rel_error": tol,
                "within_driven_level3_error": bool(m["rel_error"] <= tol),
            })
        gate = (None if any(c["agrees"] is None for c in comp)
                else all(c["within_driven_level3_error"] for c in comp))
        surplus_mixed = [r for r in rec["retained"]
                         if r["beta"] is not None and r["beta"] < rec["matched_by_order"][2]["beta"]]
        payload = {
            "step": "3 (secondary mixed gate, section 4.4)",
            "level": L,
            "geometry": "A (t = b/4)",
            "ny": ny,
            "nx": nx,
            "h": h,
            "dense_argument": None,
            "dense_note": "dense=None: _MIXED_DENSE_MAX decides; dense=True is "
                          "forbidden above the cap (section 4.4(d))",
            "n_nodes": int(mesh.n_nodes),
            "n_tris": int(mesh.n_tris),
            "n_edges": int(mesh.n_edges),
            "n_pec": int(res.n_pec),
            "n_free_edges": int(mesh.n_edges - res.n_pec),
            "n_dof_total": int(res.n_dof),
            "solver_beta": float(res.beta),
            "solver_eps_eff": float(res.eps_eff),
            "solver_residual": float(res.residual),
            "solver_sigma_recorded": float(res.sigma),
            "wall_time_s": wall,
            "peak_rss_mb": peak_rss_mb(),
            "classification": rec,
            "cross_check": comp,
            "cross_check_passes": gate,
            "n_extra_survivors": len(surplus_mixed),
            "extra_survivors": [{"beta": r["beta"], "eps_eff": r["eps_eff"],
                                 "curl_ratio": r["curl_ratio"]} for r in surplus_mixed],
        }
        dump(OUT / ("mixed_level%d.json" % L), payload)
        for c in comp:
            print("  order %d  mixed e %s  driven e3 %s  %s"
                  % (c["order"],
                     "n/a" if c.get("mixed_rel_error") is None else "%.3e" % c["mixed_rel_error"],
                     "n/a" if c.get("driven_level3_rel_error") is None
                     else "%.3e" % c["driven_level3_rel_error"],
                     "within" if c.get("within_driven_level3_error") else "OUTSIDE"))
        print("  cross-check passes:", gate, "; extra survivors:", len(surplus_mixed))


def run_control():
    """STEP 4: section 6 negative control, geometry B at level 1."""
    rule("NEGATIVE CONTROL (section 6), geometry B: t = b/8")
    t0 = time.time()
    rejected = []
    roots_b = solve_ref(T_B, rejected=rejected)[::-1]
    print("  geometry B poles:", ", ".join("%.12f" % p for p in sorted(poles(T_B))))
    print("  geometry B roots (%d accepted, %d bracket(s) rejected on a pole):"
          % (len(roots_b), len(rejected)))
    ref_check = []
    for i, beta in enumerate(roots_b):
        rr, scale = diagnose(beta, T_B)
        doc = BETA_REF_B.get(i + 1)
        rel = None if doc is None else abs(beta - doc) / doc
        ref_check.append({"order": i + 1, "beta": beta, "eps_eff": (beta / K0) ** 2,
                          "beta_doc": doc, "rel_diff_vs_doc": rel,
                          "rel_residual": rr, "term_scale": scale})
        print("    mode %d  beta = %.17g  eps_eff = %.16f  doc %.17g  rel.diff %.3e"
              "  rel.residual %.3e"
              % (i + 1, beta, (beta / K0) ** 2, doc if doc else float("nan"),
                 rel if rel is not None else float("nan"), rr))

    L = 1
    ny = LEVEL_NY[L]
    mesh, eps_call, boundaries, nx, h = build_mesh(ny, T_B)
    res = mode2d.solve_modes(mesh, K0, SIGMA, eps_r=eps_call,
                             boundaries=boundaries, k=K_CAND)
    rec_b = classify(mesh, res, "geometry_B_level%d" % L, roots_b, None)

    l1 = json.loads((OUT / "level1.json").read_text())
    a_betas = {m["order"]: m["beta"] for m in l1["classification"]["matched_by_order"]}

    moves = []
    for m in rec_b["matched_by_order"]:
        bA = a_betas.get(m["order"])
        bB = m["beta"]
        if bA is None or bB is None:
            moves.append({"order": m["order"], "beta_A": bA, "beta_B": bB,
                          "relative_movement": None})
            continue
        move = (bB - bA) / bA
        analytic = ((BETA_REF_B[m["order"]] - BETA_REF_DOC[m["order"] - 1])
                    / BETA_REF_DOC[m["order"] - 1])
        moves.append({
            "order": m["order"],
            "beta_A": bA,
            "beta_B": bB,
            "relative_movement": move,
            "analytic_relative_movement": analytic,
            "difference_from_analytic": move - analytic,
            "void_if_unchanged": bool(abs(move) < VOID_MOVE),
        })
        print("    mode %d  A %.6f  B %.6f  move %+.4f%%  analytic %+.4f%%  diff %+.2e"
              % (m["order"], bA, bB, 100 * move, 100 * analytic, move - analytic))

    void = any(m.get("void_if_unchanged") for m in moves)
    payload = {
        "step": "4 (negative control, section 6)",
        "level": L,
        "geometry": "B (t = b/8)",
        "t": T_B,
        "ny": ny,
        "nx": nx,
        "h": h,
        "sigma": SIGMA,
        "k_candidates": K_CAND,
        "reference_geometry_B": ref_check,
        "poles_B": sorted(poles(T_B)),
        "rejected_brackets_B": [[b, rr, sc] for (b, rr, sc) in rejected],
        "n_pec": int(res.n_pec),
        "n_free": int(res.n_dof),
        "wall_time_s": time.time() - t0,
        "classification": rec_b,
        "movements": moves,
        "harness_void": bool(void),
        "void_rule": "section 6.4: |beta_B - beta_A| / beta_A < %.0e for any of "
                     "the three -> the whole exercise is void" % VOID_MOVE,
        "crossing_check": "order pairing and eps_eff fingerprint to be read off "
                          "the two matched_by_order tables",
    }
    dump(OUT / "negative_control.json", payload)
    print("  harness void:", void)


def main(argv):
    if not argv:
        argv = ["driven", "1", "2", "3", "4", "5"]
    what = argv[0]
    if what == "driven":
        run_driven([int(a) for a in argv[1:]] or [1, 2, 3, 4, 5])
    elif what == "mixed":
        run_mixed([int(a) for a in argv[1:]] or [1, 2, 3])
    elif what == "control":
        run_control()
    else:
        raise SystemExit("usage: ladder.py {driven|mixed|control} [levels...]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
