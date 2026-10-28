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

import hashlib
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


# --- section 6 negative control: governing arithmetic ----------------------
# docs/design/d45_negative_control_addendum.md was written before the run and
# fixes what section 6 of the pre-registration leaves open.  Nothing here
# amends it: PAIR_TOL is a pairing distance, MOVE_BAND/EPS_EFF_BAND are the
# addendum's readings of "a few percent" / the 4-d.p. fingerprints.
ADDENDUM = ROOT / "docs" / "design" / "d45_negative_control_addendum.md"
RECORD_A = Path(__file__).resolve().parent / "records" / "level1.json"
PAIR_TOL = 0.02                 # addendum section 2: 2 per cent relative in beta
MOVE_BAND = 0.02                # addendum section 3: |r - p| <= 0.02
EPS_EFF_BAND = 0.02             # addendum section 4: |eps_eff - ref| <= 0.02
BETA_REF_B_ORDERED = [BETA_REF_B[1], BETA_REF_B[2], BETA_REF_B[3]]
EPS_EFF_REF_B = [(b / K0) ** 2 for b in BETA_REF_B_ORDERED]


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


def sha256_file(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def record_a_candidates(path):
    """Geometry A candidates from the committed record (addendum section 1).

    Uses the record's own filter-survival flags when it carries them; otherwise
    recomputes retention with the same rule (``|eps_eff - 1| <= EPS_EFF_TOL``
    is dropped).  Positional ``matched_by_order`` is deliberately not used:
    addendum section 2 records that it pairs an artifact at level 1.
    """
    rec = json.loads(path.read_text())
    rows = rec["classification"]["candidates_all"]
    use_flags = all("kept" in r for r in rows)
    kept, dropped = [], []
    for r in rows:
        survives = bool(r["kept"]) if use_flags else (
            abs(r["eps_eff"] - 1.0) > EPS_EFF_TOL)
        row = {"index": r.get("index"), "beta": r.get("beta"),
               "beta_sq": r.get("beta_sq"), "eps_eff": r.get("eps_eff"),
               "curl_ratio": r.get("curl_ratio"),
               "drop_reason": (None if survives else
                               r.get("drop_reason") or
                               "|eps_eff - 1| <= %.0e" % EPS_EFF_TOL)}
        (kept if survives else dropped).append(row)
    physical = [r for r in kept
                if r["beta"] is not None and r["beta_sq"] is not None
                and r["beta_sq"] > 0.0]
    physical.sort(key=lambda r: -r["beta_sq"])
    route = ("committed 'kept' flag" if use_flags
             else "recomputed |eps_eff - 1| <= %.0e" % EPS_EFF_TOL)
    return rec, kept, dropped, physical, route


def pair_by_value(beta_refs, candidates, tol=PAIR_TOL):
    """Addendum section 2: nearest retained physical candidate within ``tol``."""
    out = []
    for i, ref in enumerate(beta_refs):
        ranked = sorted(((abs(c["beta"] - ref) / ref, c) for c in candidates),
                        key=lambda t: t[0])
        entry = {"mode": i + 1, "beta_ref": ref, "paired": False,
                 "candidate": None, "distance": None,
                 "nearest": [{"beta": c["beta"], "distance": float(d)}
                             for d, c in ranked[:3]]}
        if ranked:
            best_d, best = ranked[0]
            if best_d <= tol:
                entry["paired"] = True
                entry["distance"] = float(best_d)
                entry["candidate"] = {"index": best["index"], "beta": best["beta"],
                                      "beta_sq": best["beta_sq"],
                                      "eps_eff": best["eps_eff"],
                                      "curl_ratio": best["curl_ratio"]}
        out.append(entry)
    return out


def _fmt_beta(x):
    return "n/m" if x is None else "%.15g" % x


def run_control():
    """STEP 4: section 6 negative control, geometry B at level 1.

    Inputs, pairing and the readings of conditions 1-3 are taken from
    docs/design/d45_negative_control_addendum.md, which was written before
    this run.  The solver path is the undeflated one the committed geometry A
    records came from (addendum section 8).
    """
    rule("NEGATIVE CONTROL (section 6), geometry B: t = b/8")
    t0 = time.time()

    addendum_sha = sha256_file(ADDENDUM) if ADDENDUM.exists() else None
    record_sha = sha256_file(RECORD_A)

    # ---- geometry A: the committed record, addendum section 1 -------------
    rec_a, kept_a, dropped_a, phys_a, route_a = record_a_candidates(RECORD_A)
    print("  geometry A record: %s" % RECORD_A)
    print("    sha256 %s" % record_sha)
    print("    retention route: %s ; kept %d, dropped %d, physical %d"
          % (route_a, len(kept_a), len(dropped_a), len(phys_a)))

    # ---- geometry B analytic poles, then the live solve -------------------
    rejected = []
    roots_b = solve_ref(T_B, rejected=rejected)[::-1]
    eps_eff_ref_b = list(EPS_EFF_REF_B)
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
    ys = B * np.arange(ny + 1) / ny
    node_hits = np.where(ys == T_B)[0]
    node_index = int(node_hits[0]) if node_hits.size else None
    node_exact = bool(node_hits.size > 0 and np.all(ys[node_hits] == T_B))
    print("  interface y = t_B = %.17g at ny = %d: node index %s, bit-exact %s"
          % (T_B, ny, node_index, node_exact))

    t_solve = time.time()
    res = mode2d.solve_modes(mesh, K0, SIGMA, eps_r=eps_call,
                             boundaries=boundaries, k=K_CAND)
    wall_b = time.time() - t_solve
    rec_b = classify(mesh, res, "geometry_B_level%d" % L, roots_b, eps_eff_ref_b)
    print("  geometry B solve: wall %.3f s  solver beta %.17g  eps_eff %.17g"
          "  residual %.3e  (module %s)"
          % (wall_b, res.beta, res.eps_eff, res.residual, mode2d.__file__))
    print("  retained geometry B candidates (beta^2 descending):")
    print("    %-4s %-22s %-22s %-20s %s"
          % ("idx", "beta", "beta^2", "eps_eff", "curl_ratio"))
    if rec_b["retained"]:
        for r in rec_b["retained"]:
            print("    %-4d %-22s %-22s %-20.12g %+.8e"
                  % (r["index"],
                     "n/a (beta^2<0)" if r["beta"] is None else "%.17g" % r["beta"],
                     "%.17g" % r["beta_sq"], r["eps_eff"], r["curl_ratio"]))
    else:
        print("    (none retained)")

    phys_b = [r for r in rec_b["retained"]
              if r["beta"] is not None and r["beta_sq"] > 0.0]

    # ---- pairing by value, addendum section 2 -----------------------------
    pair_a = pair_by_value(list(BETA_REF_DOC), phys_a)
    pair_b = pair_by_value(BETA_REF_B_ORDERED, phys_b)
    print("  pairings (nearest retained physical candidate, tol %.2f relative):"
          % PAIR_TOL)
    print("    %-4s %-20s %-20s %-11s %-20s %-20s %-11s"
          % ("mode", "A ref", "A paired", "A dist", "B ref", "B paired", "B dist"))
    for pa, pb in zip(pair_a, pair_b):
        print("    %-4d %-20.15g %-20s %-11s %-20.15g %-20s %-11s"
              % (pa["mode"], pa["beta_ref"], _fmt_beta(pa["candidate"] and
                                                       pa["candidate"]["beta"]),
                 "n/m" if pa["distance"] is None else "%.3e" % pa["distance"],
                 pb["beta_ref"], _fmt_beta(pb["candidate"] and
                                           pb["candidate"]["beta"]),
                 "n/m" if pb["distance"] is None else "%.3e" % pb["distance"]))
    for pa, pb in zip(pair_a, pair_b):
        for tag, p in (("A", pa), ("B", pb)):
            if not p["paired"]:
                print("    NOT PAIRED: geometry %s mode %d (beta_ref %.17g); nearest: %s"
                      % (tag, p["mode"], p["beta_ref"],
                         ", ".join("%.17g at %.3e" % (n["beta"], n["distance"])
                                   for n in p["nearest"]) or "no candidates"))

    paired_idx_a = {p["candidate"]["index"] for p in pair_a if p["paired"]}
    paired_idx_b = {p["candidate"]["index"] for p in pair_b if p["paired"]}
    surplus_a = [r for r in phys_a if r["index"] not in paired_idx_a]
    surplus_b = [r for r in phys_b if r["index"] not in paired_idx_b]
    for tag, surplus in (("A", surplus_a), ("B", surplus_b)):
        for r in surplus:
            print("    unpaired retained candidate (geometry %s): beta %.17g"
                  "  eps_eff %.16f  -- not recognised by the analytic census,"
                  " not counted as a mode (addendum section 5)"
                  % (tag, r["beta"], r["eps_eff"]))

    # ---- condition 1: the movement band -----------------------------------
    cond1 = []
    for i, mode in enumerate((1, 2, 3)):
        ca, cb = pair_a[i]["candidate"], pair_b[i]["candidate"]
        p = (BETA_REF_B[mode] - BETA_REF_DOC[i]) / BETA_REF_DOC[i]
        if ca is None or cb is None:
            cond1.append({
                "mode": mode, "beta_A": None if ca is None else ca["beta"],
                "beta_B": None if cb is None else cb["beta"],
                "r": None, "p": p, "r_minus_p": None, "band": MOVE_BAND,
                "verdict": "NOT MEASURED",
                "why": "no retained physical candidate inside %.2f relative "
                       "in geometry %s" % (PAIR_TOL, "A" if ca is None else "B"),
            })
        else:
            r = (cb["beta"] - ca["beta"]) / ca["beta"]
            cond1.append({
                "mode": mode, "beta_A": ca["beta"], "beta_B": cb["beta"],
                "r": r, "p": p, "r_minus_p": r - p, "band": MOVE_BAND,
                "verdict": "PASS" if abs(r - p) <= MOVE_BAND else "FAIL",
                "why": None,
            })

    # ---- condition 2: eps_eff fingerprints -------------------------------
    eps_b = [pair_b[i]["candidate"]["eps_eff"] if pair_b[i]["paired"] else None
             for i in range(3)]
    cond2 = []
    for i, mode in enumerate((1, 2, 3)):
        ref = EPS_EFF_REF_B[i]
        e = eps_b[i]
        if e is None:
            cond2.append({"mode": mode, "eps_eff": None, "ref": ref, "delta": None,
                          "strictly_decreasing": None, "band": EPS_EFF_BAND,
                          "verdict": "NOT MEASURED",
                          "why": "geometry B mode not paired"})
            continue
        delta = e - ref
        dec, why = True, []
        if i < 2:
            nxt = eps_b[i + 1]
            if nxt is None:
                dec, why = None, why + ["mode %d unmeasured" % (mode + 1)]
            elif not (e > nxt):
                dec = False
                why.append("eps_eff[%d] <= eps_eff[%d]" % (mode, mode + 1))
        if i > 0:
            prv = eps_b[i - 1]
            if prv is None:
                if dec is True:
                    dec = None
                why.append("mode %d unmeasured" % (mode - 1))
            elif not (prv > e):
                dec = False
                why.append("eps_eff[%d] <= eps_eff[%d]" % (mode - 1, mode))
        if dec is None:
            verdict = "NOT MEASURED"
        else:
            verdict = "PASS" if (abs(delta) <= EPS_EFF_BAND and dec) else "FAIL"
        cond2.append({"mode": mode, "eps_eff": e, "ref": ref, "delta": delta,
                      "strictly_decreasing": dec, "band": EPS_EFF_BAND,
                      "verdict": verdict, "why": "; ".join(why) or None})

    # ---- condition 3: the analytic census --------------------------------
    census = {
        "endpoint": ENDPOINT,
        "analytic_betas_A": list(BETA_REF_DOC),
        "analytic_betas_B": list(BETA_REF_B_ORDERED),
        "n_analytic_below_endpoint_A": sum(1 for b in BETA_REF_DOC if b < ENDPOINT),
        "n_analytic_below_endpoint_B": sum(1 for b in BETA_REF_B_ORDERED
                                           if b < ENDPOINT),
        "n_solver_roots_below_endpoint_B": sum(1 for b in roots_b if b < ENDPOINT),
        "fourth_analytic_mode_exists": False,
        "note": "the analytic census has exactly three modes strictly below "
                "sqrt(eps_r)*k0; a retained candidate can therefore pair to no "
                "fourth analytic mode (addendum section 5). Candidates at the "
                "endpoint and candidates with beta^2 < 0 are not counted.",
    }
    census_ok = (census["n_analytic_below_endpoint_A"] == 3
                 and census["n_analytic_below_endpoint_B"] == 3)
    cond3 = []
    for i, mode in enumerate((1, 2, 3)):
        pa, pb = pair_a[i]["paired"], pair_b[i]["paired"]
        if not (pa and pb):
            verdict, why = "NOT MEASURED", "mode not paired in geometry %s" % (
                "A" if not pa else "B")
        elif not census_ok:
            verdict, why = "FAIL", "analytic census is not three below the endpoint"
        else:
            verdict, why = "PASS", None
        cond3.append({"mode": mode, "paired_A": pa, "paired_B": pb,
                      "census_ok": census_ok, "verdict": verdict, "why": why})

    # ---- condition 4: the anchor is connected (as written) ---------------
    cond4 = []
    for i, mode in enumerate((1, 2, 3)):
        r = cond1[i]["r"]
        if r is None:
            cond4.append({"mode": mode, "move": None, "void_move": VOID_MOVE,
                          "void": None, "verdict": "NOT MEASURED"})
        else:
            v = bool(abs(r) < VOID_MOVE)
            cond4.append({"mode": mode, "move": r, "void_move": VOID_MOVE,
                          "void": v, "verdict": "VOID" if v else "PASS"})
    void = any(c["void"] for c in cond4 if c["void"] is not None)

    # ---- verdict ----------------------------------------------------------
    not_measured = [i + 1 for i in range(3)
                    if not (pair_a[i]["paired"] and pair_b[i]["paired"])]
    any_fail = any(c["verdict"] == "FAIL"
                   for group in (cond1, cond2, cond3) for c in group)
    if void:
        overall, code = "VOID", 2
    elif any_fail:
        overall, code = "FAIL", 1
    elif not_measured:
        overall, code = "NOT MEASURED", 1
    else:
        overall, code = "PASS", 0

    print()
    print("  %-4s %-19s %-19s %-12s %-12s %-12s %-5s %-5s %-5s %s"
          % ("mode", "beta_A", "beta_B", "r", "p", "r-p", "C1", "C2", "C3", "C4"))
    for i in range(3):
        ca, cb = pair_a[i]["candidate"], pair_b[i]["candidate"]
        print("  %-4d %-19s %-19s %-12s %-12s %-12s %-5s %-5s %-5s %s"
              % (i + 1,
                 _fmt_beta(None if ca is None else ca["beta"]),
                 _fmt_beta(None if cb is None else cb["beta"]),
                 "n/m" if cond1[i]["r"] is None else "%+.6f" % cond1[i]["r"],
                 "%+.6f" % cond1[i]["p"],
                 "n/m" if cond1[i]["r_minus_p"] is None
                 else "%+.3e" % cond1[i]["r_minus_p"],
                 cond1[i]["verdict"][:4], cond2[i]["verdict"][:4],
                 cond3[i]["verdict"][:4], cond4[i]["verdict"][:4]))
    print("  condition 3 census: A %d, B %d analytic modes below the endpoint %.12f;"
          " solver roots below it in B: %d"
          % (census["n_analytic_below_endpoint_A"],
             census["n_analytic_below_endpoint_B"], ENDPOINT,
             census["n_solver_roots_below_endpoint_B"]))
    print("  harness void (section 6.4 / addendum section 6):", void)
    print("  OVERALL: %s  (exit %d)" % (overall, code))

    payload = {
        "step": "4 (negative control, section 6)",
        "addendum": {"path": str(ADDENDUM.relative_to(ROOT)), "sha256": addendum_sha},
        "input_record": {
            "path": str(RECORD_A.relative_to(ROOT)), "sha256": record_sha,
            "retention_route": route_a,
            "kept": kept_a, "dropped": dropped_a, "physical_retained": phys_a,
            "matched_by_order_in_record": rec_a["classification"]["matched_by_order"],
            "matched_by_order_note": "not used: positional matching pairs an "
                                     "artifact at level 1 (addendum section 2)",
        },
        "geometry": "B (t = b/8)", "level": L, "ny": ny, "nx": nx, "h": h,
        "t_A": T, "t_B": T_B, "t_node_index": node_index,
        "t_node_line_bit_exact": node_exact,
        "b": B, "a": A, "eps_r": EPS_R, "k0": K0, "sigma": SIGMA,
        "k_candidates": K_CAND,
        "analytic": {
            "A": {"beta": list(BETA_REF_DOC), "eps_eff": list(EPS_EFF_DOC)},
            "B": {"beta": BETA_REF_B_ORDERED, "eps_eff": eps_eff_ref_b,
                  "poles": sorted(poles(T_B)), "roots": [float(b) for b in roots_b],
                  "rejected_brackets": [[b, rr, sc] for (b, rr, sc) in rejected],
                  "diagnose": ref_check},
        },
        "measured": {
            "A": {"source": "records/level1.json", "candidates": phys_a},
            "B": {"source": "live undeflated solve",
                  "solver_beta": float(res.beta),
                  "solver_eps_eff": float(res.eps_eff),
                  "solver_residual": float(res.residual),
                  "solver_module": mode2d.__file__,
                  "n_pec": int(res.n_pec), "n_free": int(res.n_dof),
                  "candidates_all": rec_b["candidates_all"],
                  "retained": rec_b["retained"],
                  "unpaired_retained": surplus_b,
                  "solve_wall_s": wall_b},
        },
        "pairings": {
            "rule": "addendum section 2: nearest retained physical candidate "
                    "within the distance, each geometry against its own "
                    "analytic betas, then A to B through the shared analytic "
                    "mode index",
            "tol_relative": PAIR_TOL, "A": pair_a, "B": pair_b,
            "unpaired_retained_A": surplus_a,
        },
        "conditions": {
            "1_movement": {"rule": "|r - p| <= %.2f" % MOVE_BAND,
                           "band": MOVE_BAND, "per_mode": cond1},
            "2_eps_eff": {"rule": "|eps_eff - ref| <= %.2f and the measured "
                                  "triple strictly decreasing in mode index"
                                  % EPS_EFF_BAND,
                          "band": EPS_EFF_BAND, "ref": eps_eff_ref_b,
                          "per_mode": cond2},
            "3_census": {"census": census, "per_mode": cond3},
            "4_connected": {"rule": "void iff |beta_B - beta_A| / beta_A < %.0e"
                                    " for any paired mode" % VOID_MOVE,
                            "void_move": VOID_MOVE, "per_mode": cond4,
                            "harness_void": void},
        },
        "verdict": overall,
        "exit_code": code,
        "exit_code_semantics": {
            "0": "overall PASS: all four conditions hold on all three modes",
            "2": "VOID: |beta_B - beta_A| / beta_A < 1e-6 for a paired mode "
                 "(section 6.4 / addendum section 6); the exercise is void",
            "1": "FAIL or NOT MEASURED: a measured condition failed, or a mode "
                 "could not be paired inside the distance; NOT MEASURED is not "
                 "a pass and not a fail",
        },
        "not_measured_modes": not_measured,
        "wall_time_s": time.time() - t0,
    }
    dump(OUT / "negative_control.json", payload)
    return code


def main(argv):
    if not argv:
        argv = ["driven", "1", "2", "3", "4", "5"]
    what = argv[0]
    if what == "driven":
        run_driven([int(a) for a in argv[1:]] or [1, 2, 3, 4, 5])
    elif what == "mixed":
        run_mixed([int(a) for a in argv[1:]] or [1, 2, 3])
    elif what == "control":
        return run_control()
    else:
        raise SystemExit("usage: ladder.py {driven|mixed|control} [levels...]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
