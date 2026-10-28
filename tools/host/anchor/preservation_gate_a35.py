"""Blocking ``eps_eff`` cluster-safety diagnostic around the preservation gate.

Dispatch 51, part A-3.5.  ``tools/host/anchor/preservation_gate.py`` (frozen)
does not read ``eps_eff`` when it pairs candidates (gate section 6), so at
``eps_r = 3.5`` a level whose candidates cluster in ``eps_eff`` can pair two
near-degenerate candidates to two analytic roots and report a small ``e_k``
for a pair the physics does not separate.  This driver does not re-implement
the gate: it calls the frozen module's own entry point, ``preservation_gate.
main(argv)``, and then reads the JSON record that entry point wrote, so every
number below is derived from the gate's own candidates.

Cluster rule (fixed, never tuned)::

    same group  <=>  |eps_eff_i - eps_eff_j| / max(|eps_eff_i|, |eps_eff_j|) <= 1e-2

and the groups are the connected components of that relation.  For every group
of size >= 2 the diagnostic reports its size, its ``eps_eff`` range, and::

    min_rel_gap = min over (candidate in group, frozen root) of
                  |beta - beta_ref| / beta_ref

i.e. the smallest analytic distance any member of the cluster has to a root the
gate could pair it with.  A level's ``min_cluster_distance`` is the smallest
such gap over its clusters.  A cluster whose distance falls below the gate's
own pairing tolerance ``PAIR_TOL`` (2e-2) is UNSAFE: there the gate cannot tell
two cluster members' partners apart, so its verdict would rest on a numerical
accident of the eigensolver rather than on the solver.

Fence (dispatch 51): levels 1-3 only.  A level above 3 stops before any work
with exit 2.  If any level is UNSAFE the run STOPS with exit 3 (the gate's own
STOPPED code); otherwise the gate's exit code is passed through unchanged
(0 PASS, 1 FAIL, 2 FAILED-TO-MEASURE, 3 STOPPED).

The gate's ``--out`` record is read and never rewritten.  The diagnostic writes
one sidecar next to it, ``<stem>_clusters.json``.

CLI::

    python tools/host/anchor/preservation_gate_a35.py
    python tools/host/anchor/preservation_gate_a35.py --eps-r 3.5 --out .scratch/d51/pg_a35.json

No network.  Deterministic: every group and index list is sorted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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

import preservation_gate as pg  # noqa: E402

#: Fixed: relative ``eps_eff`` distance that puts two candidates in one group.
CLUSTER_REL = 1e-2
#: Dispatch 51 fence: the only levels in scope.
FENCE_MAX_LEVEL = 3
#: Dispatch 51 geometry and record.
EPS_R_A35 = 3.5
OUT_A35 = ".scratch/d51/pg_a35.json"


def rel_gap(a, b) -> float:
    """``|a - b| / max(|a|, |b|)``; 0 when both are 0."""
    denom = max(abs(a), abs(b))
    return 0.0 if denom == 0.0 else abs(a - b) / denom


def cluster_groups(candidates):
    """Connected components of the ``CLUSTER_REL`` relation on ``eps_eff``.

    Returns a list of groups; each group is a list of
    ``(index, eps_eff, beta)`` triples sorted by ``(eps_eff, index)``, and the
    groups themselves are sorted by their first member.  Candidates whose
    ``eps_eff`` was not recorded are left out (they cannot be placed).
    """
    rows = [(int(c["index"]), float(c["eps_eff"]), c.get("beta"))
            for c in candidates if c.get("eps_eff") is not None]
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            if rel_gap(rows[i][1], rows[j][1]) <= CLUSTER_REL:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)

    members = {}
    for i in range(len(rows)):
        members.setdefault(find(i), []).append(rows[i])
    groups = [sorted(g, key=lambda r: (r[1], r[0])) for g in members.values()]
    return sorted(groups, key=lambda g: (g[0][1], g[0][0]))


def analyse_level(record, roots) -> dict:
    """Cluster audit of one solved level of the gate's record."""
    level = int(record["level"])
    groups = [g for g in cluster_groups(record.get("candidates") or [])
              if len(g) >= 2]
    report_groups, distance = [], None
    for g in groups:
        best = None
        for index, _eps, beta in g:
            if beta is None:
                continue          # below cutoff: no analytic distance to take
            for root in roots:
                gap = abs(float(beta) - float(root)) / float(root)
                if best is None or gap < best[0]:
                    best = (gap, int(index), float(root))
        entry = {
            "size": len(g),
            "indices": [int(i) for i, _e, _b in g],
            "eps_eff_min": min(e for _i, e, _b in g),
            "eps_eff_max": max(e for _i, e, _b in g),
            "min_rel_gap": None if best is None else best[0],
            "min_rel_gap_index": None if best is None else best[1],
            "min_rel_gap_root": None if best is None else best[2],
        }
        report_groups.append(entry)
        if best is not None and (distance is None or best[0] < distance):
            distance = best[0]

    if not report_groups:
        safe = True                       # vacuous: nothing to confuse
    elif distance is None:
        safe = False                      # a cluster with no measurable gap
    else:
        safe = distance >= pg.PAIR_TOL

    if not report_groups:
        print("cluster_safety level %d: no cluster of size >= 2 -> "
              "SAFE (vacuous)" % level)
    elif distance is None:
        print("cluster_safety level %d: no cluster member carries a beta -> "
              "UNSAFE (distance unmeasurable)" % level)
    else:
        print("cluster_safety level %d: min_cluster_distance = %.12g "
              "PAIR_TOL = %g -> %s"
              % (level, distance, pg.PAIR_TOL, "SAFE" if safe else "UNSAFE"))
    for entry in report_groups:
        print("  cluster size=%d eps_eff=[%.12g, %.12g] min_rel_gap=%s"
              % (entry["size"], entry["eps_eff_min"], entry["eps_eff_max"],
                 "n/a" if entry["min_rel_gap"] is None
                 else "%.12g" % entry["min_rel_gap"]))

    return {"level": level, "groups": report_groups,
            "min_cluster_distance": distance, "safe": safe}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="preservation_gate_a35.py",
        description="Blocking eps_eff cluster-safety diagnostic for the "
                    "preservation gate at eps_r = 3.5 (dispatch 51, part "
                    "A-3.5).  Runs the frozen gate through its own entry "
                    "point, reads the record it wrote, and stops with exit 3 "
                    "if any level's candidates cluster closer than the gate's "
                    "PAIR_TOL.",
        epilog="Fence: levels 1-3 only (a higher level exits 2 before any "
               "work).  Exit codes: the gate's own 0/1/2/3, 3 also for an "
               "unsafe cluster, 2 for a request outside the fence.")
    ap.add_argument("--eps-r", type=float, default=EPS_R_A35,
                    help="slab permittivity (default %(default)r; the A-3.5 "
                         "geometry)")
    ap.add_argument("--t", type=float, default=None,
                    help="slab thickness in m (default None -> T = B/4)")
    ap.add_argument("--levels", type=int, nargs="+", default=list(pg.LEVELS),
                    help="ladder levels to solve (default 1 2 3)")
    ap.add_argument("--out", metavar="PATH", default=OUT_A35,
                    help="the gate's single JSON record (default %(default)s); "
                         "read, never rewritten")
    ap.add_argument("--reference", action="store_true", default=None,
                    help="pass through to the gate: print the frozen analytic "
                         "set and stop (no solve, no cluster audit)")
    args = ap.parse_args(argv)

    outside = sorted({int(level) for level in args.levels
                      if int(level) > FENCE_MAX_LEVEL})
    if outside:
        sys.stderr.write("error: levels %s are outside the dispatch 51 fence "
                         "(levels 1-3 only)\n"
                         % " and ".join(str(level) for level in outside))
        sys.exit(2)

    gate_argv = ["--eps-r", repr(float(args.eps_r))]
    if args.t is not None:
        gate_argv += ["--t", repr(float(args.t))]
    gate_argv += ["--levels"] + [str(int(level)) for level in args.levels]
    out_path = Path(args.out)
    if str(out_path.parent) not in ("", "."):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    gate_argv += ["--out", str(out_path)]
    if args.reference:
        gate_argv.append("--reference")

    rc = pg.main(gate_argv)
    if args.reference:
        print("cluster_safety: --reference only (no solve) -> not measured")
        return rc

    if not out_path.exists():
        sys.stderr.write("error: the gate wrote no record at %s; the cluster "
                         "diagnostic has nothing to measure\n" % out_path)
        return 2
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    roots = [float(r) for r in payload["frozen_set"]["roots_descending"]]
    geometry = payload.get("geometry") or {}

    level_reports = [analyse_level(record, roots)
                     for record in payload.get("levels") or []]
    if any(not report["safe"] for report in level_reports):
        overall = "UNSAFE"
    elif not any(report["groups"] for report in level_reports):
        overall = "VACUOUS"
    else:
        overall = "SAFE"

    sidecar = out_path.with_name(out_path.stem + "_clusters.json")
    document = {
        "gate": "tools/host/anchor/preservation_gate.py",
        "eps_r": geometry.get("eps_r", args.eps_r),
        "t": geometry.get("t", args.t),
        "pair_tol": pg.PAIR_TOL,
        "cluster_rel_tol": CLUSTER_REL,
        "levels": level_reports,
        "overall": overall,
    }
    with open(sidecar, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, sort_keys=False)
        fh.write("\n")
    print("  -> wrote %s (overall %s)" % (sidecar, overall))

    if overall == "UNSAFE":
        print("STOP: unsafe cluster distance")
        return 3
    return rc


if __name__ == "__main__":
    sys.exit(main())
