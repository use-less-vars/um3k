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

The record also carries the dispatch-54 diagnostic fields, and no condition in
this module reads any of them.  ``surviving_sets`` is one entry per level, in
``levels`` order: the mode set the deflated solve *returned*, with its spectrum
and its deflation diagnostics.  ``deflated_sets`` is one entry per level, in
``levels`` order: what that solve's deflation *removed* -- the built deflation
dimension, the closed-form removed spectrum ``beta_sq = k0^2`` and whether that
closed form is exact on the route the level was solved on (AT-3; the two sets
are complements, and only ``deflated_sets`` is the deflated set the dispatch
asks for).  ``root_candidates_by_level`` is one entry per level, per frozen
root: every candidate that level's pairing considered, in the order it
considered them, with its ``beta``, its per-candidate ``residual`` and a
``selected`` flag (AT-5).  ``root_verdicts`` is one entry per root: ``P1``,
``P2``, ``P3``, ``measurable`` and the per-level ``e`` and ``p`` they were
computed from; it is built after the verdict is decided and is audit only.
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
    root_candidates = []
    residual_of = {int(c["index"]): c.get("residual") for c in candidates
                   if c.get("index") is not None}
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
        root_candidates.append(
            {"order": order, "beta_ref": float(ref),
             "n_eligible": len(eligible),
             "selected_index": None if taken is None else int(taken[1]),
             "candidates": [
                 {"order": order, "candidate_index": int(index),
                  "beta": float(beta), "rel": float(rel),
                  "residual": _plain(residual_of.get(int(index))),
                  "selected": bool(taken is not None
                                   and int(index) == int(taken[1]))}
                 for rel, index, beta in eligible]})
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
            "root_candidates": root_candidates,
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


# --- dispatch 54 field 1: the per-level sets (AT-3) -------------------------

#: The per-level diagnostics ``emfit.mode2d`` records on a deflated solve: the
#: eleven of dispatch 54 field 1 (``z_dim_closed_form`` ... ``residual_grad``)
#: plus the four this gate already kept.  Read out and written to the record;
#: no condition below reads any of them.  A key the result does not carry is
#: recorded as ``None``.
LEVEL_DIAGNOSTIC_KEYS = (
    "z_dim", "z_dim_closed_form", "column_region", "columns_v1",
    "columns_added", "z_dim_v2", "region_contrast", "region_rows",
    "z_dim_closed_form_v2", "n_dof", "n_columns", "residual_grad",
    "residual_eps_mu", "residual_pencil",
)


def _plain(value):
    """Cast to native JSON types at this boundary (numpy never reaches the record)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "tolist"):
        return _plain(value.tolist())
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


#: The inner product the AT-1 overlap is measured in: the ``B`` of the pencil,
#: i.e. ``assemble(...)[1]`` -- ``m_mu[e, f] = INT (1/mu_r) W_e . W_f`` on the
#: FULL edge list, the matrix the solver normalises its eigenvector against
#: (``e^T B e = 1``, ``emfit/mode2d.py``).  ``eps_r`` does not enter it.  A
#: label, not a criterion: nothing in this module compares it to anything.
B_METRIC = "m_mu: assemble(mesh)[1], full edge list, 1/mu_r-weighted L2"

#: Norm floor for the cosine.  The solver normalises to ``e^T B e = 1``, so a
#: B-norm below this is numerically zero and the cosine is undefined.  A floor
#: on the DENOMINATOR, never a bound on the value itself.
AT1_B_NORM_MIN = 1e-30


def cross_level_overlap_pending(to_level, reason="not-computed") -> dict:
    """Fail-closed placeholder for one level's incoming level pair (AT-1).

    Every per-level record carries this key from the moment it is built, so the
    shape does not depend on whether an overlap could be measured.  ``value``
    is ``None`` and ``reason`` says why; :func:`measure` overwrites it with
    :func:`cross_level_overlap`'s record once the coarser level's field is in
    hand.  No condition in this module reads it.
    """
    return {"from_level": None, "to_level": int(to_level), "metric": B_METRIC,
            "n_edges_to": None, "per_root": [], "reason": reason}


def surviving_set_record(level, candidates, defl) -> dict:
    """One level's SURVIVING mode set, its spectrum and its diagnostics.

    This is what the deflated solve returned -- the complement of the removed
    set, which :func:`deflated_set_record` records.  It is not AT-3's deflated
    set and does not claim to be.

    ``candidates`` are that level's candidate records (``candidate_records``),
    which are already in the solver's own order; the spectrum is their
    ``beta_sq`` in that same order.  Nothing here sorts, filters, thresholds or
    summarises what the solver returned: ``modes`` and ``spectrum_beta_sq`` are
    carried whole.  ``n_modes`` and ``max_beta_sq`` are additional summary
    keys, never a replacement for the set.  Diagnostic values are cast to
    native types by :func:`_plain`.
    """
    modes = [{"index": int(c["index"]),
              "beta_sq": float(c["beta_sq"]),
              "beta": None if c.get("beta") is None else float(c["beta"]),
              "eps_eff": float(c["eps_eff"]),
              "curl_ratio": float(c["curl_ratio"]),
              "residual": _plain(c.get("residual"))}
             for c in candidates]
    spectrum = [m["beta_sq"] for m in modes]
    return {"level": int(level), "n_modes": len(modes),
            "spectrum_beta_sq": spectrum, "modes": modes,
            "max_beta_sq": max(spectrum) if spectrum else None,
            "cross_level_overlap": cross_level_overlap_pending(level),
            "diagnostics": {k: _plain(defl.get(k))
                            for k in LEVEL_DIAGNOSTIC_KEYS}}


#: The deflated route this gate drives: :func:`solve_level` calls
#: ``solve_modes_deflated_v2``, the widened route (``region_widen = True``).
#: A label, not a criterion -- no condition in this module reads it.
DEFLATE_ROUTE = "deflated_v2"


def deflate_route_exact(route) -> bool:
    """Is the removed spectrum *exactly* ``beta_sq = k0^2`` on this route?

    True only for the un-widened ``"deflated"`` route, whose deflation lives in
    the ``eps_r == 1/mu_r`` block where the gradient space is an exact null
    space of the pencil.  False for ``"deflated_v2"`` (widened) and for any
    route this gate does not know, so an unrecognised route makes no claim.
    """
    return route == "deflated"


def deflated_set_record(level, k0, res_or_defl, route,
                        overlap_reason="not-computed") -> dict:
    """AT-3: one level's REMOVED mode set -- what deflation took out, and why.

    The deflated subspace ``Z`` that ``emfit.mode2d`` builds is nodal gradients
    only, so every eigenvalue it removes is closed-form ``beta_sq = k0^2``
    (``emfit/mode2d.py:1482-1488``: "these are the spurious states that sit at
    ``beta^2 = k0^2``").  It is recorded as that constant, not as a
    measurement.  ``removed_count`` carries the built deflation dimension
    ``z_dim`` together with ``z_dim_closed_form`` and ``z_dim_v2`` when the
    deflation dict reports them (alongside, never instead), and ``diagnostics``
    is the :data:`LEVEL_DIAGNOSTIC_KEYS` read, shared with
    :func:`surviving_set_record`.

    ``removed_spectrum_exact`` is decided from the ROUTE alone, because that is
    all this gate measures: the ``eps_r == 1/mu_r`` block is an exact null
    space of the pencil, but ``solve_modes_deflated_v2`` widens the region and
    that widening is "a census licence, not an exactness claim" -- on it
    ``residual_eps_mu`` and ``residual_pencil`` are non-zero by construction
    (``emfit/mode2d.py:1496-1499``).  So the flag is True only on the
    un-widened route, and False for ``route = None`` (nothing removed, no
    claim made).

    ``res_or_defl`` is the level's deflation dict, or a solve result that
    carries one; anything else records as unknown (``None``) rather than
    raising.  A level that aborted keeps its route (what was attempted) and
    records ``None`` for everything it did not measure.

    ``overlap_reason`` is only the fail-closed ``reason`` of the AT-1 key
    (:func:`cross_level_overlap_pending`): ``"level-aborted"`` on the abort
    path, otherwise the placeholder :func:`measure` overwrites.
    """
    if isinstance(res_or_defl, dict):
        defl = res_or_defl
    else:
        defl = getattr(res_or_defl, "deflation", None) or {}
    # AT-3's caveat, and the reason ``removed_spectrum_exact`` is a flag and
    # not an assumption: on a homogeneous block the PHYSICAL mode is itself
    # gradient-like (``solve_modes``' docstring, ``emfit/mode2d.py:917-919``:
    # "a homogeneous ``eps_r`` makes even the physical mode a gradient, e.g.
    # the parallel-plate ``TEM``"), so the deflated set can contain a WANTED
    # mode.  Nothing below acts on the flag; it is recorded for the reader.
    return {"level": int(level),
            "route": route,
            "removed_count": {"z_dim": _plain(defl.get("z_dim")),
                              "z_dim_closed_form":
                                  _plain(defl.get("z_dim_closed_form")),
                              "z_dim_v2": _plain(defl.get("z_dim_v2"))},
            "removed_beta_sq_closed_form": (None if k0 is None
                                            else float(k0) * float(k0)),
            "removed_spectrum_exact": deflate_route_exact(route),
            "cross_level_overlap": cross_level_overlap_pending(
                level, overlap_reason),
            "diagnostics": {k: _plain(defl.get(k))
                            for k in LEVEL_DIAGNOSTIC_KEYS}}


# --- the instrument: one level, d49 unchanged except the mesh ---------------

def solve_level(level, eps_r=EPS_R_15, t=None, carry=None) -> dict:
    """One rung of the frozen ladder, with ``build_mesh(ny, T, eps_r=eps_r)``.

    Everything else is the d49 instrument of ``.scratch/d49/run_v2.py``: the
    same entry point (``solve_modes_deflated_v2``), the same positional
    ``(mesh, K0, SIGMA)``, the same ``eps_r=`` / ``boundaries=`` / ``k=``
    keywords, the same ``maxiter = 40*n`` ARPACK budget.  The budget rebind is
    process-local and undone in ``finally``.

    ``carry``, when given, is a dict that receives ``{"level", "mesh", "res"}``
    for this level, so a later level can re-express this level's eigenvector on
    its own edges (dispatch 54 field 4, :func:`cross_level_overlap`).  It is an
    out-parameter only and is never read as input here; :func:`measure` is its
    only reader, and it cannot change what this function does.
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
                "surviving_set": None,
                "deflated_set": deflated_set_record(
                    level, ar.K0, None, DEFLATE_ROUTE,
                    overlap_reason="level-aborted"),
                "root_candidates": [],
                "wall_time_s": time.time() - t0, "candidates": []}
    finally:
        mode2d.eigsh = original_eigsh

    if carry is not None:
        carry[level] = {"level": level, "mesh": mesh, "res": res}

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
        "surviving_set": surviving_set_record(
            level, mode2d.candidate_records(res), defl),
        "deflated_set": deflated_set_record(level, ar.K0, defl, DEFLATE_ROUTE),
        "root_candidates": [],
    }


# --- AT-1: cross-level eigenvector overlap (dispatch 54, field 4) -----------

def fine_edge_field(coarse_res, fine_mesh):
    """Level ``c-1``'s field re-expressed as ``INT_edge E . dl`` on level ``c``.

    ``Mode2D.e_t`` is documented as ``INT_edge E . dl`` on the full edge list,
    i.e. a functional of the *field* rather than of a particular DOF vector, so
    it can legitimately be evaluated on a mesh whose edges have no
    correspondence with the mesh the mode was solved on.  For edge ``(a, b)``
    with ``L = x_b - x_a`` the midpoint rule gives

        INT_edge E . dl ~= L * E(midpoint) . t_hat = E(mid) . L,

    which is exact for a constant field and first order (``O(h^2)`` per edge,
    ``O(h)`` in the integral) for a smooth one.  ``Mode2D.e_at`` locates the
    ``(n, 2)`` midpoints and returns the Whitney sum ``(n, 2)``.

    The result is expressed on the FULL fine edge list, in the same global
    ``(lo, hi)`` orientation the solver's own ``e_t`` uses, so the two vectors
    are directly comparable -- see :func:`cross_level_overlap`.
    """
    import numpy as np
    nodes = np.asarray(fine_mesh.nodes, float)
    edges = np.asarray(fine_mesh.edges, np.int64)
    vec = nodes[edges[:, 1]] - nodes[edges[:, 0]]
    mid = 0.5 * (nodes[edges[:, 1]] + nodes[edges[:, 0]])
    field = np.asarray(coarse_res.e_at(mid), float)
    return np.einsum("ij,ij->i", field, vec)


def _overlap_row(coarse_res, res_f, mesh_f, b_f, e_f, order_, ic, it) -> dict:
    """One root's B-cosine between its two levels' eigenvectors (AT-1).

    ``ic`` / ``it`` are the candidate indices pairing took at the coarse and
    the fine level.  ``coarse_res.e_t`` (transported by :func:`fine_edge_field`)
    and ``res_f.e_t`` are the two full-edge-list vectors; ``w_c^T B e_f`` is
    their inner product in the pencil's ``B = m_mu``.

    Fail-closed by construction: any step that cannot be taken leaves ``value``
    ``None`` and names the reason in ``reason``.  The order of the guards is the
    order of the reasons below, so a row never reports a reason it could not
    actually establish.  ``dot`` and the two B-norms are recorded even when the
    cosine is refused, so a refusal is inspectable.
    """
    import numpy as np
    row = {"order": order_, "candidate_from": ic, "candidate_to": it,
           "value": None, "reason": None,
           "b_dot": None, "b_norm_coarse": None, "b_norm_fine": None}
    if ic is None or it is None:
        row["reason"] = "unpaired"
        return row
    # only the mode the solver selected carries a returned eigenvector: e_t is
    # index-aligned with candidates, but a candidate that was *not* chosen has
    # no stored vector to overlap
    if int(ic) != int(coarse_res.chosen) or int(it) != int(res_f.chosen):
        row["reason"] = "eigenvector-not-carried-for-candidate"
        return row
    try:
        w_c = np.asarray(fine_edge_field(coarse_res, mesh_f), float)
        e_f = np.asarray(e_f, float)
    except BaseException as exc:                       # noqa: BLE001
        row["reason"] = "interpolation-failed: %s" % type(exc).__name__
        return row
    if not (np.all(np.isfinite(w_c)) and np.all(np.isfinite(e_f))):
        row["reason"] = "non-finite"
        return row
    dot = float(w_c @ b_f.dot(e_f))
    n_c = float(w_c @ b_f.dot(w_c))
    n_f = float(e_f @ b_f.dot(e_f))
    row["b_dot"], row["b_norm_coarse"], row["b_norm_fine"] = dot, n_c, n_f
    if n_c <= AT1_B_NORM_MIN:
        row["reason"] = "zero-norm-coarse"
        return row
    if n_f <= AT1_B_NORM_MIN:
        row["reason"] = "zero-norm-fine"
        return row
    product = n_c * n_f
    if product <= 0.0:
        row["reason"] = "non-positive-norm-product"
        return row
    row["value"] = dot / math.sqrt(product)
    return row


def tracked_pairs(coarse_rec, fine_rec) -> list:
    """The ``(order, coarse_index, fine_index)`` triples pairing actually took.

    Both indices come from the already-decided pairing audit, one level each,
    so AT-1 sees exactly the candidates the gate consumed and cannot propose a
    different correspondence.  Only orders taken at BOTH levels are returned;
    an order unpaired at either end has no pair to overlap.
    """
    def _taken(rec):
        rows = ((rec or {}).get("pairing") or {}).get("rows") or []
        return {r.get("order"): r.get("taken") for r in rows}

    a, b = _taken(coarse_rec), _taken(fine_rec)
    orders = sorted(o for o in set(a) & set(b) if o is not None)
    return [(o, a[o], b[o]) for o in orders
            if a[o] is not None and b[o] is not None]


def cross_level_overlap(coarse, fine, tracked=None) -> dict:
    """AT-1: one level pair's eigenvector overlap, one row per paired root.

    ``coarse`` and ``fine`` are the ``{"level", "mesh", "res"}`` snapshots
    :func:`solve_level` writes through its ``carry`` out-parameter; ``tracked``
    is :func:`tracked_pairs` on the two solved records.  When no pairing is
    available the two levels' own selected modes are compared instead
    (``order`` ``None``), which is still a measurement, just not one the gate
    has committed to.

    Diagnostic only: :func:`verdict` and :func:`judge_root` read none of this,
    and every failure is reported as a ``reason`` rather than raised.
    """
    import numpy as np
    coarse, fine = coarse or {}, fine or {}
    out = {"from_level": coarse.get("level"), "to_level": fine.get("level"),
           "metric": B_METRIC, "n_edges_to": None, "per_root": [],
           "reason": None}
    if not coarse:
        out["reason"] = "no-coarser-level"
        return out
    res_c, mesh_c = coarse.get("res"), coarse.get("mesh")
    res_f, mesh_f = fine.get("res"), fine.get("mesh")
    if mesh_c is None or mesh_f is None:
        out["reason"] = "mesh-unavailable"
        return out
    if res_c is None or res_f is None or getattr(res_c, "e_t", None) is None \
            or getattr(res_f, "e_t", None) is None:
        out["reason"] = "eigenvector-unavailable"
        return out
    ne_f = int(mesh_f.n_edges)
    out["n_edges_to"] = ne_f
    e_f = np.asarray(res_f.e_t, float)
    if e_f.shape != (ne_f,):
        out["reason"] = "fine-eigenvector-length-mismatch"
        return out
    w_c = np.asarray(res_c.e_t, float)
    if w_c.shape != (int(mesh_c.n_edges),):
        out["reason"] = "coarse-eigenvector-length-mismatch"
        return out
    try:
        import emfit.mode2d as mode2d
        b_f = mode2d.assemble(mesh_f, eps_r=1.0, mu_r=1.0)[1].tocsr()
    except BaseException as exc:                       # noqa: BLE001
        out["reason"] = "mass-matrix-unavailable: %s" % type(exc).__name__
        return out
    pairs = list(tracked) if tracked else \
        [(None, int(res_c.chosen), int(res_f.chosen))]
    out["per_root"] = [_overlap_row(res_c, res_f, mesh_f, b_f, e_f, o, ic, it)
                       for o, ic, it in pairs]
    return out


def root_overlap_records(result) -> list:
    """Dispatch 54 field 4: the AT-1 rows gathered per root order.

    Read back out of ``result["cross_level_overlaps"]`` after the verdict has
    been issued, so it cannot change what the verdict consumed.  Every read is
    a ``.get`` on a length-agnostic lookup: a missing or half-built overlap
    section yields ``[]`` rather than raising where the gate would have run.
    """
    by_order = {}
    for pair in result.get("cross_level_overlaps") or []:
        pair = pair or {}
        for row in pair.get("per_root") or []:
            row = row or {}
            order_ = row.get("order")
            if order_ is None:
                continue
            by_order.setdefault(order_, []).append(
                {"from_level": pair.get("from_level"),
                 "to_level": pair.get("to_level"),
                 "value": row.get("value"),
                 "reason": row.get("reason")})
    return [{"order": o, "pairs": by_order[o]} for o in sorted(by_order)]


# --- measurement across levels ---------------------------------------------

def measure(refset, eps_r=EPS_R_15, t=None, levels=LEVELS, emit=print) -> dict:
    """Drive levels 1..3 in order, pairing each before solving the next.

    Section 8: an unpaired root at any level stops the run where it happens --
    no further level is solved and no verdict is issued.
    """
    records, stop = [], None
    carry, overlaps, prev = {}, [], None
    for level in levels:
        emit("level %d: solving (ny = %d, eps_r = %r)" % (level, 16 * 2 ** (level - 1), eps_r))
        rec = solve_level(level, eps_r=eps_r, t=t, carry=carry)
        records.append(rec)
        if rec["aborted"]:
            emit("  level %d ABORTED: %s" % (level, rec["abort_error"]))
            break
        pl = pair_level(rec["candidates"], refset.roots)
        rec["pairing"] = pl
        rec["root_candidates"] = pl["root_candidates"]
        emit("  level %d: %d candidate(s), %d paired, unpaired orders %r, "
             "surplus %d" % (level, pl["n_candidates"],
                             len(pl["consumed"]), pl["B5_unpaired_orders"],
                             pl["B6_surplus_count"]))
        # AT-1: a diagnostic, computed after pairing is decided and written
        # only into the diagnostic keys -- verdict() reads none of it.
        if prev is None:
            pair = cross_level_overlap_pending(level, "no-coarser-level")
        else:
            try:
                pair = cross_level_overlap(
                    carry.get(prev["level"]), carry.get(level),
                    tracked=tracked_pairs(prev, rec))
            except BaseException as exc:               # noqa: BLE001
                pair = cross_level_overlap_pending(
                    level, "overlap-failed: %s" % type(exc).__name__)
        overlaps.append(pair)
        for _key in ("surviving_set", "deflated_set"):
            if isinstance(rec.get(_key), dict):
                rec[_key]["cross_level_overlap"] = pair
        prev = rec
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
            "cross_level_overlaps": overlaps,
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


def root_verdict_records(result, refset) -> list:
    """Dispatch 54 field 3: per-root P1/P2/P3, recorded AFTER the verdict.

    :func:`judge_root` already computes these booleans for the aggregate
    verdict and is left exactly as it is; this only reads its output back out,
    so a reader can see which root failed which predicate.  It is called from
    :func:`main` after :func:`verdict` has returned -- never before it -- so it
    cannot change what the verdict consumes, and every read here is a ``.get``
    on a length-guarded lookup, so it cannot raise where the gate would
    otherwise have run.  Root order is the dict order :func:`verdict` and
    :func:`report` iterate, i.e. ascending ``order``.
    """
    judged = result.get("judged") or {}
    roots = tuple(getattr(refset, "roots", ()) or ())
    out = []
    for order_, j in judged.items():
        j = j or {}
        e = j.get("e") or {}
        known = isinstance(order_, int) and 0 < order_ <= len(roots)
        out.append({"order": order_,
                    "beta_ref": roots[order_ - 1] if known else None,
                    "P1": j.get("P1"), "P2": j.get("P2"), "P3": j.get("P3"),
                    "measurable": j.get("measurable"),
                    "e": {k: e.get(k) for k in LEVELS},
                    "p": list(j.get("p") or [None, None])})
    return out


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
    w("\ncross-level eigenvector overlap AT-1 (reported, not gated; metric %s)\n"
      % B_METRIC)
    for pair in result.get("cross_level_overlaps") or []:
        w("  level %s -> %s (n_edges_to %s): %s\n"
          % (pair.get("from_level"), pair.get("to_level"),
             pair.get("n_edges_to"), pair.get("reason") or "measured"))
        for row in pair.get("per_root") or []:
            w("    order %s: cosine %s (%s)\n"
              % (row.get("order"), _f(row.get("value"), ".6e"),
                 row.get("reason") or "ok"))
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
            "surviving_sets": [rec.get("surviving_set")
                               for rec in result["records"]],
            "deflated_sets": [rec.get("deflated_set")
                              for rec in result["records"]],
            "root_candidates_by_level": [
                {"level": rec["level"], "roots": rec.get("root_candidates") or []}
                for rec in result["records"]],
            "root_verdicts": root_verdict_records(result, refset),
            "cross_level_overlaps": result.get("cross_level_overlaps") or [],
            "root_overlaps": root_overlap_records(result),
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
