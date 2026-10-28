"""Level-1 smoke test of the analytic convergence anchor (ny = 16 only).

No ladder, no slope, no pass/fail verdict: this driver exercises ONE rung and
prints every number it produced.  It imports and calls the live
``emfit.mode2d.solve_modes`` and never rebuilds the discrete pencil.

What it does, in order
  1. re-solves the analytic reference of docs/design/anchor_preregistration.md
     section 2.2-2.4 and reports the worst relative difference against the
     document's frozen geometry-A roots (stop at > 1e-14);
  2. reproduces the section 2.6 ``eps_r = 1`` self-check table;
  3. builds the level-1 mesh (ny = 16, nx = 2, square cells h = b/16),
     confirms the material interface y = t is a node line, and reports the
     total / PEC / free edge counts;
  4. calls ``solve_modes(..., k=16)`` once and prints the whole 16-candidate
     audit table;
  5. applies the frozen spurious-mode filter of section 4.3 literally
     (drop ``curl_ratio <= 1e-10``, sort survivors by ``beta_sq`` descending,
     take three, require a 7-decade gap) and prints the outcome.

Exit codes: 0 = every check printed, 2 = reference mismatch, 3 = internal.
"""

import inspect
import sys
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
    A, B, BETA_EPS1_DOC, BETA_REF_DOC, EPS_EFF_DOC, EPS_R, F, K0, T,
    diagnose, poles, solve_ref,
)

# --- level 1 of the ladder of section 1.3: ny = 16, nx = ny/8 = 2 ----------
NY = 16
NX = NY // 8
H = B / NY

# --- the shift handed to solve_modes ---------------------------------------
# solve_modes has no default for sigma and the pre-registration does not name a
# value, so one had to be chosen: half the vacuum wavenumber squared.  It is not
# free of consequences -- sigma = k0^2 was tried first and makes the
# shift-invert factorisation exactly singular, because the discrete curl-free
# (gradient) eigenvectors of this mesh sit at eps_eff = 1 exactly, i.e. at
# beta_sq = k0^2 = sigma (section 5 of the run log).  Every number below is
# conditional on this one arbitrary choice.
SIGMA_MULT = 0.5
SIGMA = SIGMA_MULT * K0 * K0

REF_TOL = 1e-14        # section 2.5: the reference is good to ~1e-16 relative
CURL_CUT = 1e-10       # section 4.3, frozen
K_CAND = 16            # section 4.3, frozen
GAP_DECADES = 7.0      # section 4.3, frozen


def rule(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def reference_check():
    rule("1. ANALYTIC REFERENCE (section 2.2-2.4), geometry A: t = b/4, eps_r = 2")
    print("b = %.17g   t = %.17g   a = %.17g" % (B, T, A))
    print("f = %.17g Hz   k0 = %.17g rad/m   k0*b = %.17g = 3.5*pi"
          % (F, K0, K0 * B))
    print("poles  :", ", ".join("%.12f" % p for p in sorted(poles(T))))
    print("top    : sqrt(eps_r)*k0 = %.12f" % (np.sqrt(EPS_R) * K0))

    rejected = []
    roots = solve_ref(T, rejected=rejected)    # ascending
    desc = roots[::-1]                         # the document's order
    print()
    print("root-finder: %d root(s) accepted, %d bracket(s) rejected"
          % (len(roots), len(rejected)))
    for beta, rr, scale in rejected:
        print("  rejected beta = %.17g  term scale = %.3e  rel.residual = %.3e"
              "  (a cut point of 2.2(b), i.e. a pole)" % (beta, scale, rr))
    print()
    print("root-finder, beta descending:")
    for i, beta in enumerate(desc):
        rr, scale = diagnose(beta, T)
        print("  mode %d  beta = %.17g   beta*b/pi = %.15f   eps_eff = %.16f"
              "   term scale = %.3e  rel.residual = %.3e"
              % (i + 1, beta, beta * B / np.pi, (beta / K0) ** 2, scale, rr))
    if len(desc) != len(BETA_REF_DOC):
        print("  RESULT: STOP (%d roots, the document registers %d)"
              % (len(desc), len(BETA_REF_DOC)))
        return desc, float("inf")

    print()
    print("vs the frozen document (section 2.4):")
    worst = 0.0
    for i, (beta, doc) in enumerate(zip(desc, BETA_REF_DOC)):
        rel = abs(beta - doc) / abs(doc)
        worst = max(worst, rel)
        print("  mode %d  recomputed %.17g  doc %.17g  rel.diff %.3e"
              % (i + 1, beta, doc, rel))
        print("          eps_eff    %.16f  doc %.16f  rel.diff %.3e"
              % ((beta / K0) ** 2, EPS_EFF_DOC[i],
                 abs((beta / K0) ** 2 - EPS_EFF_DOC[i]) / EPS_EFF_DOC[i]))
    print("  WORST RELATIVE DIFFERENCE vs document = %.3e   (limit %.0e)"
          % (worst, REF_TOL))
    print("  RESULT:", "PASS" if worst <= REF_TOL else "STOP")
    return desc, worst


def eps1_self_check():
    rule("2. SECTION 2.6 SELF-CHECK, eps_r = 1 (relation must collapse to sin(kappa*b)=0)")
    rejected = []
    roots = solve_ref(T, eps_r=1.0, rejected=rejected)[::-1]
    closed = [np.pi * np.sqrt(12.25 - n * n) / B for n in (1, 2, 3)]
    print("  %d root(s) accepted, %d bracket(s) rejected on a cut point"
          % (len(roots), len(rejected)))
    print("  n   closed form            root-finder           doc (2.6)          rel.diff vs closed"
          "   rel.diff vs doc")
    worst = 0.0
    for i, n in enumerate((1, 2, 3)):
        cf = closed[i]
        rf = roots[i]
        rel = abs(rf - cf) / cf
        worst = max(worst, rel)
        print("  %d   %.17g   %.17g   %.12f   %.3e   %.3e"
              % (n, cf, rf, BETA_EPS1_DOC[i], rel,
                 abs(rf - BETA_EPS1_DOC[i]) / BETA_EPS1_DOC[i]))
    print("  worst closed-form vs root-finder = %.3e  -> %s"
          % (worst, "PASS" if worst <= 1e-12 else "STOP"))
    print("  (the document quotes 2.6 to 12 digits, so its own column can only be"
          " matched to ~1e-14)")
    return worst


def build_level1():
    rule("3. LEVEL-1 MESH (ny = %d, nx = %d, h = b/%d)" % (NY, NX, NY))
    xs = A * np.arange(NX + 1) / NX
    ys = B * np.arange(NY + 1) / NY
    mesh = mode2d.structured_mesh(xs, ys)

    on_interface = np.flatnonzero(ys == T)
    print("  xs = [0, a], xs[1] = %.17g ; ys[0] = 0, ys[-1] = %.17g" % (xs[1], ys[-1]))
    print("  cell size hx = %.17g   hy = %.17g   equal = %s"
          % (xs[1] - xs[0], ys[1] - ys[0], (xs[1] - xs[0]) == (ys[1] - ys[0])))
    print("  node line at y = t exactly: indices %s (t = %.17g)"
          % (on_interface.tolist(), T))
    for j in on_interface:
        print("      ys[%d] = %.17g  == t : %s" % (j, ys[j], ys[j] == T))
    if on_interface.size != 1:
        raise SystemExit("interface y = t is not a single node line")

    eps_r_callable = lambda c: np.where(c[:, 1] < T, EPS_R, 1.0)   # noqa: E731
    boundaries = (
        lambda P: P[:, 1] == 0.0,      # y = 0
        lambda P: P[:, 1] == B,        # y = b
        lambda P: P[:, 0] == 0.0,      # x = 0
        lambda P: P[:, 0] == A,        # x = a
    )
    print("  mesh: n_nodes = %d  n_tris = %d  n_edges = %d"
          % (mesh.n_nodes, mesh.n_tris, mesh.n_edges))
    return mesh, eps_r_callable, boundaries


def solve(mesh, eps_r_callable, boundaries):
    rule("4. LIVE SOLVER")
    print("  emfit.mode2d    :", mode2d.__file__)
    print("  solve_modes is  : %s.%s at %s"
          % (mode2d.solve_modes.__module__, mode2d.solve_modes.__name__,
             inspect.getsourcefile(mode2d.solve_modes)))
    print("  signature       :", str(inspect.signature(mode2d.solve_modes)))
    print("  identical to emfit.mode2d.solve_modes:",
          mode2d.solve_modes is getattr(
              sys.modules["emfit.mode2d"], "solve_modes"))
    print("  sigma = %.17g  ( %g * k0^2 )" % (SIGMA, SIGMA_MULT))
    print("  k = %d candidates" % K_CAND)
    res = mode2d.solve_modes(mesh, K0, SIGMA, eps_r=eps_r_callable,
                             boundaries=boundaries, k=K_CAND)
    print("  returned Mode2D: n_dof = %d  n_pec = %d  n_edges = %d"
          % (res.n_dof, res.n_pec, mesh.n_edges))
    print("  total DOF (all edges) = %d ; PEC-eliminated = %d ; free = %d"
          % (mesh.n_edges, res.n_pec, res.n_dof))
    print("  free == n_edges - n_pec :", res.n_dof == mesh.n_edges - res.n_pec)
    return res


def candidate_table(res):
    rule("5. CANDIDATE AUDIT TABLE (all %d, beta_sq descending)" % K_CAND)
    rows = sorted(zip(res.candidates, res.curl_ratio),
                  key=lambda p: -p[0][0])
    print("  idx  beta (rad/m)    beta_sq         eps_eff          curl_ratio     "
          "beta*b/pi")
    for i, ((bsq, ee), cr) in enumerate(rows):
        beta = np.sqrt(bsq) if bsq >= 0.0 else float("nan")
        print("  %3d  %13.6f  %+.8e  %+.10f  %+.4e  %11.6f"
              % (i, beta, bsq, ee, cr, beta * B / np.pi))
    return rows


def frozen_filter(rows, desc):
    rule("6. FROZEN SPURIOUS-MODE FILTER (section 4.3), applied literally")
    dropped = [r for r in rows if r[1] <= CURL_CUT]       # "curl_ratio <= 1e-10"
    dropped_abs = [r for r in rows if abs(r[1]) <= CURL_CUT]
    kept = [r for r in rows if r[1] > CURL_CUT]
    kept.sort(key=lambda p: -p[0][0])
    kept3 = kept[:3]

    print("  rule 1: k = %d requested                -> %d candidates returned"
          % (K_CAND, len(rows)))
    print("  rule 2: drop curl_ratio <= %.0e (as written) -> %d dropped, %d kept"
          % (CURL_CUT, len(dropped), len(kept)))
    print("          (reading |curl_ratio| <= %.0e would drop %d, keep %d)"
          % (CURL_CUT, len(dropped_abs), len(rows) - len(dropped_abs)))
    print("  rule 3: survivors sorted by beta_sq desc, first three taken")

    for label, drop in (("as written", dropped), ("|.|", dropped_abs)):
        keep = [r for r in rows if r not in drop]
        keep.sort(key=lambda p: -p[0][0])
        top = keep[:3]
        max_drop = max((abs(r[1]) for r in drop), default=0.0)
        min_keep = min((abs(r[1]) for r in keep), default=0.0)
        if max_drop > 0.0 and min_keep > 0.0:
            dec = np.log10(max_drop / min_keep)
        else:
            dec = float("inf")
        print()
        print("  [%s] largest dropped |curl_ratio| = %.4e ; smallest kept |curl_ratio| = %.4e"
              % (label, max_drop, min_keep))
        print("  [%s] separation = %.2f decades  (require >= %.0f) -> %s"
              % (label, dec, GAP_DECADES,
                 "meets the frozen rule" if dec >= GAP_DECADES else "FAILS the frozen rule"))
        print("  [%s] the three kept:" % label)
        for i, ((bsq, ee), cr) in enumerate(top):
            beta = np.sqrt(bsq) if bsq >= 0.0 else float("nan")
            ref = desc[i]
            print("      kept %d  beta = %13.6f  eps_eff = %+.8f  curl = %+.4e"
                  "  vs beta_ref %.6f  e = %.4f%%"
                  % (i + 1, beta, ee, cr, ref,
                     100.0 * abs(beta - ref) / ref))

    print()
    print("  KEPT (as written), beta_sq descending, and the by-order match of section 5:")
    print("  order   beta_kept        beta_ref        e = |d|/beta_ref")
    for i, ((bsq, ee), cr) in enumerate(kept3):
        beta = np.sqrt(bsq) if bsq >= 0.0 else float("nan")
        ref = desc[i]
        print("    %d     %.10f    %.10f    %.6e"
              % (i + 1, beta, ref, abs(beta - ref) / ref))

    print()
    print("  beta of every kept candidate vs the endpoint sqrt(eps_r)*k0 = %.6f:"
          % (np.sqrt(EPS_R) * K0))
    for i, ((bsq, ee), cr) in enumerate(kept3):
        beta = np.sqrt(bsq) if bsq >= 0.0 else float("nan")
        print("    kept %d  beta = %.6f  %s endpoint"
              % (i + 1, beta, "ABOVE" if beta > np.sqrt(EPS_R) * K0 else "below"))
    return dropped, kept3, kept, dropped_abs


def main():
    desc, worst = reference_check()
    eps1_self_check()
    mesh, eps_r_callable, boundaries = build_level1()
    res = solve(mesh, eps_r_callable, boundaries)
    rows = candidate_table(res)
    frozen_filter(rows, desc)
    rule("LEVEL 1 SMOKE TEST FINISHED -- no slope, no verdict computed")
    return 0 if worst <= REF_TOL else 2


if __name__ == "__main__":
    raise SystemExit(main())
