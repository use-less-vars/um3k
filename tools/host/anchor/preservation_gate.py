"""Preservation-gate adjudicator: pre-registered, one verdict, no tuning.

Implements ``docs/design/preservation_gate_preregistration.md`` (the gate) for
the geometry frozen in ``docs/design/preservation_gate_geometry_a15_freeze.md``
(A-1.5).  Every number that decides the verdict is a constant read off the gate
document and quoted next to the code that uses it.  The statistic::

    e_k = |beta_k - beta_ref| / |beta_ref|      # on beta, never on beta_sq
    p_k = log2(e_k / e_{k+1}),   k = 1, 2

``e_1, e_2, e_3`` index LEVELS 1, 2, 3 for one fixed root -- not modes.  Pass
conditions, for every root of the frozen set::

    P1  e_1 > e_2 > e_3, strictly
    P2  1.7 <= p_1 <= 2.3 and 1.7 <= p_2 <= 2.3
    P3  e_3 <= 5e-3   (supporting only: failing P3 alone is an anomaly, and
                       passing it cannot rescue a P1/P2 failure)

Verdicts: PASS, FAIL, FAILED-TO-MEASURE, and STOPPED for the section 8
annihilation stop rule (exit code 3).

Instrument.  The per-level solve is the d49 instrument of
``.scratch/d49/run_v2.py`` unchanged -- ``solve_modes_deflated_v2``, the same
sigma (``0.5*K0*K0``), the same ``k=CAND``, the same ARPACK budget
``maxiter = 40*n``, the same mesh construction -- with one substitution: the
mesh is built with ``build_mesh(ny, T, eps_r=eps_r)`` instead of
``build_mesh(ny, T)``.  Nothing else about the instrument is varied.  The
ladder is not used to drive the run (it hard-codes ``build_mesh(ny, T)`` at
ladder.py:263); ``build_mesh`` itself is reused so the mesh cannot drift.

Pairing prohibitions (gate section 6): pairing may not consult ``curl_ratio``
or ``eps_eff``, and one level's pairing may not use another level's.
:func:`pair_level` sees one level's candidates and the frozen set, and nothing
else; ``curl_ratio`` is read out afterwards by :func:`purity_context`.

``residual_eps_mu`` is reported with its level-to-level ratio and is never a
term of the verdict (gate section 7); non-decay is reported as an anomaly.

CLI::

    python tools/host/anchor/preservation_gate.py --reference     # static, no solve
    python tools/host/anchor/preservation_gate.py --out gate.json # runs the gate
    python tools/host/anchor/preservation_gate.py --selfcheck     # synthetic only

Only ``--out`` writes a file, and it writes exactly one JSON document holding
the per-level records (candidates with ``beta_sq`` / ``eps_eff`` /
``curl_ratio``, and ``residual_eps_mu``), the pairing audit, the e_k table and
the verdict.  No network.  Deterministic given the solver.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass

# --- frozen constants -------------------------------------------------------

LEVELS = (1, 2, 3)              # gate section 2: "Levels k = 1, 2, 3 only"
PAIR_TOL = 2e-2                 # gate section 6, inherited unchanged (B1-B6)
ORDER_LO = 1.7                  # gate section 3, P2
ORDER_HI = 2.3                  # gate section 3, P2
P3_MAX = 5e-3                   # gate section 3, P3 (supporting only)
ROUTE3_MIN = 0.04               # gate section 6, mis-pairing route 3
WINDOW_FACTOR = 1.5             # gate section 5: window [0, 1.5*ENDPOINT]
ARPACK_BUDGET_FACTOR = 40       # d49 instrument, run_v2.py ARPACK_BUDGET_FACTOR

#: Frozen geometry of the A-1.5 freeze: same thickness, lower contrast.
EPS_R_15 = 1.5

PASS = "PASS"
FAIL = "FAIL"
FAILED_TO_MEASURE = "FAILED-TO-MEASURE"
STOPPED = "STOPPED"

EXIT = {PASS: 0, FAIL: 1, FAILED_TO_MEASURE: 2, STOPPED: 3}

#: Gate section 4, the calibration table (geometry A, eps_r = 2), quoted at the
#: verdict as the precision the band was set against.  Never used as a bound.
FEASIBILITY_E3 = (5.3099e-5, 3.1419e-5, 5.3928e-4)


# --- the frozen analytic set (gate section 5) --------------------------------

@dataclass(frozen=True)
class ReferenceSet:
    """Every analytic root in the census window, strictly descending."""

    roots: tuple          # rad/m, strictly descending: the frozen set
    eps_r: float
    t: float
    k0: float
    b: float
    endpoint: float       # sqrt(eps_r) * k0
    window_top: float     # WINDOW_FACTOR * endpoint
    n_ascending: int      # how many solve_ref returned, ascending, in total
    rejected: tuple = ()  # poles solve_ref refused to accept

    @property
    def n(self):
        return len(self.roots)


def reference_roots(t=None, eps_r=EPS_R_15, b=None, k0=None) -> ReferenceSet:
    """The frozen analytic set: ``solve_ref(t, eps_r, b, k0)`` reversed.

    ``solve_ref`` returns ascending; the gate indexes roots in descending order
    with one-based ``order``.  A reader that does not reverse shifts every row
    by one, which is why the descending order is asserted here rather than
    assumed downstream.  The window is ``[0, 1.5*ENDPOINT]`` with
    ``ENDPOINT = sqrt(eps_r)*k0``; roots above ``ENDPOINT`` stay in the set.
    """
    import anchor_reference as ar

    t = ar.T if t is None else float(t)
    b = ar.B if b is None else float(b)
    k0 = ar.K0 if k0 is None else float(k0)
    rejected = []
    ascending = ar.solve_ref(t, eps_r=eps_r, b=b, k0=k0, rejected=rejected)
    descending = sorted((float(r) for r in ascending), reverse=True)
    for i in range(len(descending) - 1):
        if not descending[i] > descending[i + 1]:
            raise RuntimeError(
                "frozen set is not strictly descending at index %d: "
                "%.17g, %.17g" % (i, descending[i], descending[i + 1]))
    endpoint = math.sqrt(eps_r) * k0
    window_top = WINDOW_FACTOR * endpoint
    roots = tuple(r for r in descending if 0.0 < r <= window_top)
    if len(roots) < 3:
        raise RuntimeError(
            "only %d root(s) survive the census window [0, %r] (endpoint "
            "sqrt(eps_r)*k0 = %r, eps_r = %r); the gate needs three"
            % (len(roots), window_top, endpoint, eps_r))
    return ReferenceSet(roots=roots, eps_r=float(eps_r), t=t, k0=k0, b=b,
                        endpoint=endpoint, window_top=window_top,
                        n_ascending=len(ascending), rejected=tuple(rejected))


# --- mis-pairing route 3 (gate section 6) -----------------------------------

def route3(refs) -> dict:
    """``min_k |refs[k]-refs[k+1]| / refs[k+1]`` against ``0.04``.

    ``refs`` is the DESCENDING frozen set, so the denominator is the smaller
    root of each adjacent pair, exactly as the gate writes it.  Route 3
    depends on the spectrum and is therefore recomputed per geometry, never
    inherited from geometry A.
    """
    r = list(refs)
    pairs = [(k + 1, abs(r[k] - r[k + 1]) / r[k + 1]) for k in range(len(r) - 1)]
    if not pairs:
        return {"value": None, "pair": None, "ok": False, "pairs": [],
                "reason": "fewer than two reference roots: route 3 undefined"}
    pair, value = min(pairs, key=lambda kv: kv[1])
    return {"value": value, "pair": pair, "ok": value >= ROUTE3_MIN,
            "threshold": ROUTE3_MIN, "pairs": pairs, "reason": ""}


# --- pairing, B1 to B6, inherited unchanged (gate section 6) ----------------

def relative_error(beta, beta_ref) -> float:
    """``e = |beta - beta_ref| / |beta_ref|`` on ``beta`` only (section 2)."""
    return abs(float(beta) - float(beta_ref)) / abs(float(beta_ref))


def pair_level(candidates, refs, tol=PAIR_TOL) -> dict:
    """One level's B1-B6 exhaustion against the frozen set.

    B1: a candidate exists only if its ``beta`` is recorded.
    B2: eligible means ``e <= PAIR_TOL``, on ``beta`` and nothing else.
    B3: eligible are sorted by ``e`` ascending.
    B4: the paired candidate is the first eligible one not yet consumed;
        ``B4_monotonic`` records that the taken betas fall with ``order``.
    B5: a reference with no eligible, unconsumed candidate is unpaired.
    B6: eligible candidates left unconsumed are surplus.

    Rows are keyed by one-based ``order`` and carry ``beta_ref``, ``first`` /
    ``first_rel`` (closest eligible) and ``taken`` / ``taken_rel`` (consumed).
    ``curl_ratio`` and ``eps_eff`` are not read here, and no other level is
    visible -- both prohibitions of gate section 6.
    """
    rows, consumed, unpaired = [], {}, []
    usable = [(int(c["index"]), float(c["beta"])) for c in candidates
              if c.get("beta") is not None]
    for order, ref in enumerate(refs, start=1):
        eligible = sorted(
            ((relative_error(beta, ref), index, beta)
             for index, beta in usable if relative_error(beta, ref) <= tol),
            key=lambda t: (t[0], t[1]))
        row = {"order": order, "beta_ref": float(ref),
               "first": None, "first_rel": None,
               "taken": None, "taken_rel": None,
               "consumed": [], "n_eligible": len(eligible),
               "nearest_any_rel": min((relative_error(beta, ref)
                                       for _, beta in usable), default=None)}
        if eligible:
            row["first_rel"], row["first"], _ = eligible[0]
        taken = next((t for t in eligible if t[1] not in consumed), None)
        if taken is None:
            unpaired.append(order)
        else:
            row["taken_rel"], row["taken"], _ = taken
            consumed[taken[1]] = float(ref)
        row["consumed"] = sorted(consumed)
        rows.append(row)
    taken_betas = [next(bt for i, bt in usable if i == row["taken"])
                   for row in rows if row["taken"] is not None]
    surplus = [{"index": index, "beta": beta,
                "nearest_rel": min(relative_error(beta, ref) for ref in refs)}
               for index, beta in usable if index not in consumed]
    return {"rows": rows, "consumed": {int(k): v for k, v in consumed.items()},
            "B4_monotonic": (len(taken_betas) < 2
                             or all(taken_betas[i] > taken_betas[i + 1]
                                    for i in range(len(taken_betas) - 1))),
            "B5_unpaired_orders": unpaired,
            "B6_surplus_count": len(surplus), "B6_surplus": surplus,
            "n_candidates": len(usable)}


# --- the statistic (section 2) and the conditions (section 3) ---------------

def order(e_k, e_next):
    """``p_k = log2(e_k / e_{k+1})``; ``None`` when it is not defined."""
    if e_k is None or e_next is None:
        return None
    if e_k <= 0.0 or e_next <= 0.0:
        return None   # an exactly reproduced root: no order is measurable
    return math.log2(e_k / e_next)


def judge_root(per_level_e) -> dict:
    """P1/P2/P3 for one root.  ``per_level_e`` maps level -> ``e`` for the root.

    The index is the LEVEL: ``e[1], e[2], e[3]``.  P3 is evaluated and
    reported but is never consulted by :func:`verdict` as a pass condition.
    """
    e = [per_level_e.get(k) for k in LEVELS]
    p = [order(e[0], e[1]), order(e[1], e[2])]
    measurable = all(v is not None for v in e)
    p1 = bool(measurable and e[0] > e[1] > e[2])
    p2 = bool(p[0] is not None and p[1] is not None
              and all(ORDER_LO <= v <= ORDER_HI for v in p))
    p3 = bool(e[2] is not None and e[2] <= P3_MAX)
    return {"e": dict(zip(LEVELS, e)), "p": p, "measurable": measurable,
            "P1": p1, "P2": p2, "P3": p3}


# --- the instrument: one level, d49 unchanged except the mesh ---------------

def solve_level(level, eps_r=EPS_R_15, t=None) -> dict:
    """One rung of the frozen ladder, with ``build_mesh(ny, T, eps_r=eps_r)``.

    Everything else is the d49 instrument of ``.scratch/d49/run_v2.py``: the
    same entry point (``solve_modes_deflated_v2``), the same positional
    ``(mesh, K0, SIGMA)``, the same ``eps_r=`` / ``boundaries=`` / ``k=``
    keywords, the same ``maxiter = 40*n`` ARPACK budget.  The budget rebind is
    process-local and undone in ``finally``.
    """
    import anchor_reference as ar
    import emfit.mode2d as mode2d
    import ladder

    ny = ladder.LEVEL_NY[level]
    original_eigsh = mode2d.eigsh

    def _budgeted_eigsh(*args, **kwargs):
        n = int(args[0].shape[0])
        for banned in ("maxiter", "ncv", "tol"):
            assert banned not in kwargs, (
                "caller passed %s=; the injected maxiter would not be the only "
                "change" % banned)
        kwargs["maxiter"] = ARPACK_BUDGET_FACTOR * n
        return original_eigsh(*args, **kwargs)

    t0 = time.time()
    mode2d.eigsh = _budgeted_eigsh
    try:
        mesh, eps_call, boundaries, nx, h = ladder.build_mesh(ny, t, eps_r=eps_r)
        res = mode2d.solve_modes_deflated_v2(mesh, ar.K0, ladder.SIGMA,
                                             eps_r=eps_call,
                                             boundaries=boundaries,
                                             k=ladder.K_CAND)
    except BaseException as exc:                       # noqa: BLE001
        return {"level": level, "ny": ny, "aborted": True,
                "abort_error": "%s: %s" % (type(exc).__name__, exc),
                "wall_time_s": time.time() - t0, "candidates": []}
    finally:
        mode2d.eigsh = original_eigsh

    defl = getattr(res, "deflation", None) or {}
    return {
        "level": level, "ny": ny, "nx": int(nx), "h": float(h),
        "aborted": False, "abort_error": None,
        "wall_time_s": time.time() - t0,
        "n_nodes": int(mesh.n_nodes), "n_edges": int(mesh.n_edges),
        "n_tris": int(mesh.n_tris), "n_free": int(res.n_dof),
        "n_pec": int(res.n_pec), "n_converged": len(res.candidates),
        "solver_module": mode2d.__file__,
        "solver": "emfit.mode2d.solve_modes_deflated_v2",
        "arpack_budget_factor": ARPACK_BUDGET_FACTOR,
        "candidates": [dict(r) for r in mode2d.candidate_records(res)],
        "residual_eps_mu": defl.get("residual_eps_mu"),
        "deflation": {"z_dim": defl.get("z_dim"),
                      "column_region": defl.get("column_region"),
                      "residual_eps_mu": defl.get("residual_eps_mu"),
                      "residual_pencil": defl.get("residual_pencil")},
    }


# --- measurement across levels ---------------------------------------------

def measure(refset, eps_r=EPS_R_15, t=None, levels=LEVELS, emit=print) -> dict:
    """Drive levels 1..3 in order, pairing each before solving the next.

    Section 8: an unpaired root at any level stops the run where it happens --
    no further level is solved and no verdict is issued.
    """
    records, stop = [], None
    for level in levels:
        emit("level %d: solving (ny = %d, eps_r = %r)" % (level, 16 * 2 ** (level - 1), eps_r))
        rec = solve_level(level, eps_r=eps_r, t=t)
        records.append(rec)
        if rec["aborted"]:
            emit("  level %d ABORTED: %s" % (level, rec["abort_error"]))
            break
        pl = pair_level(rec["candidates"], refset.roots)
        rec["pairing"] = pl
        emit("  level %d: %d candidate(s), %d paired, unpaired orders %r, "
             "surplus %d" % (level, pl["n_candidates"],
                             len(pl["consumed"]), pl["B5_unpaired_orders"],
                             pl["B6_surplus_count"]))
        if pl["B5_unpaired_orders"]:
            stop = {"level": level,
                    "orders": pl["B5_unpaired_orders"],
                    "roots": [refset.roots[o - 1] for o in pl["B5_unpaired_orders"]],
                    "nearest_any_rel": {o: pl["rows"][o - 1]["nearest_any_rel"]
                                        for o in pl["B5_unpaired_orders"]},
                    "candidates": [c["beta"] for c in rec["candidates"]
                                   if c.get("beta") is not None]}
            emit("STOP: possible annihilation at level %d -- order(s) %r "
                 "unpaired after B1-B6 exhaustion; no further level is solved, "
                 "no verdict is issued" % (level, pl["B5_unpaired_orders"]))
            break

    e_by_root = {}
    for rec in records:
        pl = rec.get("pairing")
        if not pl:
            continue
        for row in pl["rows"]:
            e_by_root.setdefault(row["order"], {})[rec["level"]] = row["taken_rel"]
    judged = {o: judge_root(v) for o, v in sorted(e_by_root.items())}
    return {"records": records, "stop": stop, "judged": judged,
            "residuals": residual_series(records),
            "purity": purity_context(records)}


def residual_series(records) -> dict:
    """Gate section 7: report ``residual_eps_mu`` per level and its ratio."""
    values = [(r["level"], r.get("residual_eps_mu")) for r in records]
    got = [(k, v) for k, v in values if v is not None]
    ratios = [(got[i][0], got[i][1] / got[i + 1][1]) for i in range(len(got) - 1)
              if got[i + 1][1]]
    anomaly, why = False, ""
    if len(got) < len(LEVELS):
        anomaly, why = True, ("not recorded at every solved level; decay is not "
                              "assessable")
    elif any(r <= 1.0 for _, r in ratios):
        anomaly, why = True, ("residual_eps_mu fails to decay with level "
                              "(ratio <= 1)")
    return {"values": values, "ratios": ratios, "anomaly": anomaly, "why": why}


def purity_context(records) -> dict:
    """``curl_ratio`` of the paired candidates.  Context only, never a term.

    Called after pairing and keyed by the already-decided ``taken`` indices, so
    it cannot influence which candidate was taken (gate section 6).
    """
    out = {}
    for rec in records:
        pl = rec.get("pairing")
        if not pl:
            continue
        table = {int(c["index"]): c for c in rec["candidates"]}
        out[rec["level"]] = [
            {"order": row["order"], "index": row["taken"],
             "curl_ratio": table[row["taken"]]["curl_ratio"],
             "eps_eff": table[row["taken"]]["eps_eff"]}
            for row in pl["rows"] if row["taken"] is not None]
    return out


# --- the verdict (gate sections 3, 8, 10) ----------------------------------

def _explanation(records, order_):
    """Recorded pairing rejections that could explain a P1/P2 violation."""
    notes = []
    for rec in records:
        pl = rec.get("pairing")
        if not pl:
            continue
        row = next((r for r in pl["rows"] if r["order"] == order_), None)
        if row is not None and row["first"] is not None \
                and row["taken"] is not None and row["taken"] != row["first"]:
            notes.append("level %d: closest eligible candidate already consumed "
                         "by a lower order" % rec["level"])
        if pl["B6_surplus_count"]:
            notes.append("level %d: %d surplus candidate(s)"
                         % (rec["level"], pl["B6_surplus_count"]))
    return notes


def verdict(result, refset, levels=LEVELS) -> dict:
    """PASS / FAIL / FAILED-TO-MEASURE / STOPPED, with reasons."""
    r3 = route3(refset.roots)
    solved = [r for r in result["records"] if not r["aborted"]]

    if result["stop"] is not None:
        return {"verdict": STOPPED, "route3": r3,
                "reasons": ["gate section 8: root unpaired at level %d "
                            "(possible annihilation); run stopped, no verdict "
                            "issued" % result["stop"]["level"]],
                "judged": result["judged"]}

    reasons = []
    if refset.n < 3:
        reasons.append("fewer than three roots in the frozen set (%d)" % refset.n)
    if len(solved) < len(levels):
        reasons.append("fewer than three levels solved (%d of %d)"
                       % (len(solved), len(levels)))
    if not r3["ok"]:
        reasons.append("mis-pairing route 3 below %.2f (value %r): the pairing "
                       "is not auditable on this geometry, so no verdict is "
                       "issued" % (ROUTE3_MIN, r3["value"]))
    if reasons:
        return {"verdict": FAILED_TO_MEASURE, "reasons": reasons, "route3": r3,
                "judged": result["judged"]}

    violations, explained = [], []
    for order_, j in result["judged"].items():
        bad = []
        if not j["measurable"]:
            bad.append("e not measurable at every level")
        if not j["P1"]:
            bad.append("P1 monotone violated: e = %r"
                       % ([j["e"][k] for k in LEVELS],))
        if not j["P2"]:
            bad.append("P2 order outside [%r, %r]: p = %r"
                       % (ORDER_LO, ORDER_HI, j["p"]))
        if not bad:
            continue
        notes = _explanation(result["records"], order_)
        entry = {"order": order_, "why": bad,
                 "explained_by": notes if notes else None}
        (explained if notes else violations).append(entry)

    if explained:
        return {"verdict": FAILED_TO_MEASURE, "route3": r3,
                "judged": result["judged"],
                "reasons": ["a P1/P2 violation is explained by a recorded "
                            "pairing rejection; PASS requires P1 and P2 for "
                            "every root and section 10 has no fourth verdict, "
                            "so the outcome is FAILED-TO-MEASURE"],
                "explained": explained}
    if violations:
        return {"verdict": FAIL, "route3": r3, "judged": result["judged"],
                "violations": violations,
                "reasons": [w for v in violations for w in v["why"]]}
    return {"verdict": PASS, "route3": r3, "judged": result["judged"],
            "reasons": [],
            "P3_anomalies": [o for o, j in result["judged"].items() if not j["P3"]]}


# --- reporting -------------------------------------------------------------

def _f(v, spec=".6e"):
    return "n/a" if v is None else format(v, spec)


def report(result, vd, refset, out=sys.stdout) -> None:
    w = out.write
    w("preservation gate -- gate doc: docs/design/preservation_gate_preregistration.md\n")
    w("geometry: eps_r=%r t=%r b=%r k0=%r sigma=%r\n"
      % (refset.eps_r, refset.t, refset.b, refset.k0, result.get("sigma")))
    w("frozen set (section 5), descending, window [0, %r]:\n" % refset.window_top)
    for i, r in enumerate(refset.roots, start=1):
        w("  order %d: beta_ref = %.17g\n" % (i, r))
    r3 = vd["route3"]
    w("route 3: min |ref[k]-ref[k+1]|/ref[k+1] = %s at pair %s, threshold %.2f "
      "-> %s\n" % (_f(r3["value"], ".17g"), r3["pair"], ROUTE3_MIN,
                   "ok" if r3["ok"] else "VIOLATED"))
    w("\ne_k table (on beta; e_k indexed by LEVEL)\n")
    w("  order  %-12s %-12s %-12s %-9s %-9s  P1 P2 P3\n"
      % ("e_1", "e_2", "e_3", "p_1", "p_2"))
    for order_, j in vd["judged"].items():
        w("  %-5d  %-12s %-12s %-12s %-9s %-9s  %s  %s  %s\n"
          % (order_, _f(j["e"][1]), _f(j["e"][2]), _f(j["e"][3]),
             _f(j["p"][0], ".4f"), _f(j["p"][1], ".4f"),
             "y" if j["P1"] else "n", "y" if j["P2"] else "n",
             "y" if j["P3"] else "n"))
    w("\npairing audit (B1-B6, PAIR_TOL=%r; no curl_ratio / eps_eff input)\n" % PAIR_TOL)
    for rec in result["records"]:
        if rec["aborted"]:
            w("  level %d: ABORTED (%s)\n" % (rec["level"], rec["abort_error"]))
            continue
        pl = rec.get("pairing")
        w("  level %d: ny=%d nx=%d h=%r, %d candidate(s), B4 monotonic %s, "
          "B5 unpaired %r, B6 surplus %d\n"
          % (rec["level"], rec["ny"], rec["nx"], rec["h"], pl["n_candidates"],
             pl["B4_monotonic"], pl["B5_unpaired_orders"], pl["B6_surplus_count"]))
        for row in pl["rows"]:
            w("    order %d: beta_ref=%.17g first=%s (%s) taken=%s (%s)\n"
              % (row["order"], row["beta_ref"], row["first"],
                 _f(row["first_rel"]), row["taken"], _f(row["taken_rel"])))
    res = result["residuals"]
    w("\nresidual_eps_mu (section 7: reported, not gated)\n")
    for k, v in res["values"]:
        w("  level %d: %s\n" % (k, _f(v)))
    w("  ratios: %s\n" % (", ".join("L%d %.4f" % (k, r) for k, r in res["ratios"]) or "n/a"))
    w("  anomaly: %s\n" % (res["why"] if res["anomaly"] else "none"))
    w("\ncurl_ratio of paired candidates (context only, sections 6 and 9)\n")
    for k, rows in result["purity"].items():
        w("  level %d: %s\n" % (k, ", ".join(
            "order %d %s" % (r["order"], _f(r["curl_ratio"], ".4f")) for r in rows)))
    w("\nsection 4 calibration (geometry A, eps_r=2) e_3: %s\n"
      % ", ".join(_f(v) for v in FEASIBILITY_E3))
    if result["stop"] is not None:
        st = result["stop"]
        w("\nSTOP: possible annihilation at level %d -- order(s) %r, root(s) %r, "
          "nearest candidate distances %r, candidate set %r\n"
          % (st["level"], st["orders"], st["roots"], st["nearest_any_rel"],
             st["candidates"]))
    w("\nVERDICT: %s\n" % vd["verdict"])
    for r in vd["reasons"]:
        w("  - %s\n" % r)


# --- self-check (synthetic only) -------------------------------------------

def selfcheck() -> int:
    """Arithmetic self-check on synthetic values.  Solves no geometry."""
    ok = True

    def chk(name, cond):
        nonlocal ok
        ok = ok and bool(cond)
        print("%-58s %s" % (name, "ok" if cond else "FAIL"))

    ref = 1000.0
    chk("e is on beta", abs(relative_error(ref + 1.0, ref) - 1e-3) < 1e-15)
    chk("e is sign-symmetric",
        abs(relative_error(ref - 1.0, ref) - relative_error(ref + 1.0, ref)) < 1e-18)
    chk("p of a 4x fall is 2", abs(order(4e-4, 1e-4) - 2.0) < 1e-15)
    r3 = route3((1433.426694521395, 1259.419736217716, 874.214202584546))
    chk("route 3 is the min pair, denominator the smaller root",
        r3["pair"] == 1 and abs(r3["value"] - 0.1381643889639651) < 1e-15)
    # section 4's own table must reproduce its own verdicts (e indexed by level)
    j = judge_root({1: 8.5464e-4, 2: 2.1265e-4, 3: 5.3099e-5})
    chk("section 4 order-1 row passes P1, P2 and P3", j["P1"] and j["P2"] and j["P3"])
    chk("P3 alone is not a pass: P1 false with P3 true",
        not judge_root({1: 1e-4, 2: 2e-4, 3: 5e-5})["P1"])
    cands = [{"index": 0, "beta": 1637.0}, {"index": 1, "beta": 1297.0},
             {"index": 2, "beta": 944.0}]
    pl = pair_level(cands, (1638.0, 1296.3, 944.6))
    chk("B4 consumes each candidate once",
        sorted(pl["consumed"]) == [0, 1, 2])
    chk("B4 monotonic on descending orders", pl["B4_monotonic"])
    chk("B5 empty, B6 zero on a clean triple",
        pl["B5_unpaired_orders"] == [] and pl["B6_surplus_count"] == 0)
    pl2 = pair_level(({"index": 0, "beta": 100.0},), (1638.0, 1296.3, 944.6))
    chk("B2 keeps a 90% miss out of the band",
        pl2["B5_unpaired_orders"] == [1, 2, 3])
    print("\nselfcheck: %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


# --- CLI -------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="preservation_gate.py",
        description="Run and adjudicate the pre-registered preservation gate "
                    "(docs/design/preservation_gate_preregistration.md) on the "
                    "frozen A-1.5 geometry "
                    "(docs/design/preservation_gate_geometry_a15_freeze.md). "
                    "One verdict, no tuning.",
        epilog="PASS requires P1 and P2 for every root; P3 (e_3 <= 5e-3) is "
               "supporting only; residual_eps_mu is reported and never gated; "
               "an unpaired root stops the run (exit 3). Exit codes: "
               "0 PASS, 1 FAIL, 2 FAILED-TO-MEASURE, 3 STOPPED.")
    ap.add_argument("--out", metavar="PATH",
                    help="write the single JSON record (records, pairing audit, "
                         "e_k table, verdict) to PATH")
    ap.add_argument("--eps-r", type=float, default=EPS_R_15,
                    help="slab permittivity (default %(default)r; the frozen "
                         "A-1.5 geometry)")
    ap.add_argument("--t", type=float, default=None,
                    help="slab thickness in m (default T = B/4 = 0.001953125)")
    ap.add_argument("--levels", type=int, nargs="+", default=list(LEVELS),
                    help="ladder levels to solve (default 1 2 3)")
    ap.add_argument("--reference", action="store_true",
                    help="print the frozen analytic set and the route-3 audit "
                         "and stop (no solve)")
    ap.add_argument("--selfcheck", action="store_true",
                    help="synthetic arithmetic self-check only (no solve)")
    args = ap.parse_args(argv)

    if args.selfcheck:
        return selfcheck()

    refset = reference_roots(args.t, eps_r=args.eps_r)
    if args.reference:
        print("frozen analytic set (section 5): eps_r=%r t=%r b=%r k0=%r"
              % (refset.eps_r, refset.t, refset.b, refset.k0))
        print("  endpoint sqrt(eps_r)*k0 = %r ; window [0, %r]"
              % (refset.endpoint, refset.window_top))
        print("  solve_ref returned %d root(s) ascending; %d in the window"
              % (refset.n_ascending, refset.n))
        for i, r in enumerate(refset.roots, start=1):
            print("  order %d: beta_ref = %.17g" % (i, r))
        r3 = route3(refset.roots)
        print("  route 3: %r at pair %s against %.2f -> %s"
              % (r3["value"], r3["pair"], ROUTE3_MIN,
                 "ok" if r3["ok"] else "VIOLATED"))
        return 0

    result = measure(refset, eps_r=args.eps_r, t=refset.t, levels=args.levels)
    import ladder
    result["sigma"] = ladder.SIGMA
    vd = verdict(result, refset, levels=args.levels)
    report(result, vd, refset)
    if args.out:
        payload = {
            "gate": "docs/design/preservation_gate_preregistration.md",
            "freeze": "docs/design/preservation_gate_geometry_a15_freeze.md",
            "geometry": {"eps_r": refset.eps_r, "t": refset.t, "b": refset.b,
                         "k0": refset.k0, "sigma": ladder.SIGMA,
                         "k_candidates": ladder.K_CAND,
                         "arpack_budget_factor": ARPACK_BUDGET_FACTOR,
                         "solver": "emfit.mode2d.solve_modes_deflated_v2",
                         "mesh": "build_mesh(ny, T, eps_r=eps_r)"},
            "frozen_set": {"roots_descending": list(refset.roots),
                           "endpoint": refset.endpoint,
                           "window_top": refset.window_top,
                           "n_ascending": refset.n_ascending,
                           "rejected_at_poles": [list(map(float, r))
                                                 for r in refset.rejected]},
            "route3": vd["route3"],
            "levels": result["records"],
            "judged": {str(k): v for k, v in vd["judged"].items()},
            "residual_series": result["residuals"],
            "purity": {str(k): v for k, v in result["purity"].items()},
            "stop": result["stop"],
            "verdict": vd["verdict"],
            "reasons": vd["reasons"],
        }
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")
        print("  -> wrote %s" % args.out)
    return EXIT[vd["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
