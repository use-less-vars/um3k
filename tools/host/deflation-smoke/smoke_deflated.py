"""DEVELOPMENT ARTEFACT - plumbing check only, not a result.

No acceptance number is produced by this script: it only checks that the
deflated solver wires together (shapes, orthogonality, selection), and the
pre-registered anchor ladder is deliberately not touched -- no import of
``tools/host/anchor/`` and none of the ladder geometries or rung sizes appear
below.  Every case is a synthetic box, sized to run in about a second.

What is checked
---------------
CASE 1  homogeneous ``eps_r = mu_r = 1`` box, 6 x 6 cells, PEC on all four
        walls: the gradient columns ``Z`` are exactly the nodes strictly inside
        the box, ``Z`` and ``R`` have the shapes that implies, and the two
        defining identities of ``R`` (``Z^T B R = 0``, ``R^T B R = I``) hold at
        roundoff.
CASE 2  the same construction on an 8 x 8 cell ``2.0 x 1.0`` box with
        ``k0^2 = 5`` (above the TE10 cutoff ``(pi/2)^2``), shifted with
        ``sigma = 4.0 < k0^2`` so that plain shift-invert lands inside the
        gradient cluster at ``beta^2 = k0^2``.  The candidate lists of
        ``solve_modes`` and ``solve_modes_deflated`` are printed and the
        spurious count (``|beta^2 - k0^2| / k0^2 <= 1e-9``) is compared.
CASE 3  on the CASE 2 box, the largest positive ``beta^2`` of the deflated
        solve is compared with the analytic TE10 value ``k0^2 - (pi/a)^2``.
        That is a coarse-mesh consistency check on an 8-cell-wide mesh, not an
        acceptance number, and the loose bound below says so.

Run from anywhere:  python tools/host/deflation-smoke/smoke_deflated.py
Exit code is 0 when every check passes, 1 otherwise.
"""

import os
import sys

import numpy as np

# --- make the repository root importable without asking the caller to do it --
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = _HERE
while not os.path.isdir(os.path.join(_ROOT, "emfit")):
    _PARENT = os.path.dirname(_ROOT)
    if _PARENT == _ROOT:
        raise SystemExit("cannot find the repository root above %s" % _HERE)
    _ROOT = _PARENT
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from emfit import mode2d as m2  # noqa: E402  (after the sys.path insert)

#: Slack of the nodal wall predicates [m]; the walls sit exactly on coordinates.
WALL_TOL = 1e-12

#: Relative tolerance for "this identity holds at roundoff".
ROUNDOFF = 1e-12

#: A candidate counts as spurious when its ``beta^2`` equals ``k0^2`` this
#: closely -- the gradient space is an exact null space of the pencil, so the
#: separation is roundoff against an O(1) eigenvalue scale.
SPURIOUS_RTOL = 1e-9

#: Loose band on the CASE 3 coarse-mesh comparison.  Not an acceptance number.
CASE3_LOOSE = 5.0e-2

_PASSED = []
_FAILED = []


def check(ok, label, detail):
    """Record and print one PASS/FAIL line; *detail* always names its quantity."""
    tag = "PASS" if ok else "FAIL"
    (_PASSED if ok else _FAILED).append(label)
    print("[%s] %s -- %s" % (tag, label, detail))


def walls(lx, ly):
    """Four PEC node predicates, one per wall of the ``lx x ly`` box."""
    return (
        lambda p: np.abs(p[:, 0] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 0] - lx) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - 0.0) <= WALL_TOL,
        lambda p: np.abs(p[:, 1] - ly) <= WALL_TOL,
    )


def gradient_basis(mesh, boundaries, eps_r=1.0, mu_r=1.0):
    """Rebuild ``(free, B_free, cols, Z, R, info)`` the way the solver does.

    ``solve_modes_deflated`` keeps ``Z`` and ``R`` internal, so the smoke check
    rebuilds them from the same private helpers the solver calls
    (``_per_triangle``, ``assemble``, ``pec_edge_mask``, ``pec_node_mask``,
    ``_gradient_columns``, ``_incidence``, ``_complement_basis``).  This is a
    plumbing check, so reaching into those helpers is the point.
    """
    eps_t = m2._per_triangle(eps_r, mesh, "eps_r")
    mu_t = m2._per_triangle(mu_r, mesh, "mu_r")
    _k_q, m_mu, _m_eps = m2.assemble(mesh, eps_r=eps_t, mu_r=mu_t)
    mask = m2.pec_edge_mask(mesh, boundaries)
    free = np.flatnonzero(~mask)
    b_free = m_mu[free][:, free]
    cols = m2._gradient_columns(mesh, eps_t, mu_t, m2.pec_node_mask(mesh, boundaries))
    z = m2._incidence(mesh, free, cols)
    r, info = m2._complement_basis(b_free, z)
    return free, b_free, cols, z, r, info


def spurious_count(candidates, k0_sq):
    """Number of candidates with ``|beta^2 - k0^2| / k0^2 <= SPURIOUS_RTOL``."""
    return sum(
        1
        for beta_sq, _eps_eff in candidates
        if abs(beta_sq - k0_sq) / k0_sq <= SPURIOUS_RTOL
    )


def report_candidates(tag, res, k0_sq):
    """Print one solver's full candidate list, one line per candidate."""
    print("  %s: chosen=%d beta^2=%.9e eps_eff=%.6f (%d candidates)"
          % (tag, res.chosen, res.beta_sq, res.beta_sq / k0_sq,
             len(res.candidates)))
    for i, (beta_sq, eps_eff) in enumerate(res.candidates):
        print("    %s[%d] beta^2=% .9e eps_eff=% .6f curl_ratio=% .3e "
              "|beta^2-k0^2|/k0^2=% .3e"
              % (tag, i, beta_sq, eps_eff, res.curl_ratio[i],
                 abs(beta_sq - k0_sq) / k0_sq))


# ----------------------------------------------------------------------
# CASE 1: the gradient columns of a homogeneous box, and the split R
# ----------------------------------------------------------------------
def case1():
    nx = ny = 6
    lx = ly = 1.0
    print("")
    print("CASE 1  homogeneous eps_r = mu_r = 1 box, %d x %d cells over %.3f x "
          "%.3f m, PEC on all four walls" % (nx, ny, lx, ly))
    mesh = m2.box_mesh(lx, ly, nx, ny)
    boundaries = walls(lx, ly)
    free, b_free, cols, z, r, info = gradient_basis(mesh, boundaries)

    # every triangle has eps_r == 1/mu_r, so the gradient columns must be
    # exactly the nodes strictly inside the box
    inside = np.flatnonzero(
        (mesh.nodes[:, 0] > WALL_TOL)
        & (mesh.nodes[:, 0] < lx - WALL_TOL)
        & (mesh.nodes[:, 1] > WALL_TOL)
        & (mesh.nodes[:, 1] < ly - WALL_TOL)
    )
    n_free = int(free.size)
    z_dim = int(info["z_dim"])
    p = int(r.shape[1])
    expected_z_dim = (nx - 1) * (ny - 1)
    print("  mesh: %d nodes, %d triangles, %d edges, %d free edge DOFs"
          % (mesh.n_nodes, mesh.n_tris, mesh.n_edges, n_free))

    check(np.array_equal(np.sort(cols), inside),
          "gradient columns are the nodes strictly inside the box",
          "%d columns vs %d interior nodes" % (cols.size, inside.size))
    check(z_dim == expected_z_dim,
          "z_dim == (nx-1)(ny-1)",
          "z_dim=%d, (nx-1)(ny-1)=%d" % (z_dim, expected_z_dim))
    check(z.shape == (n_free, expected_z_dim),
          "Z shape is (n_free, z_dim)",
          "Z shape=%s, n_free=%d, z_dim=%d" % (z.shape, n_free, expected_z_dim))
    check(r.shape == (n_free, n_free - expected_z_dim),
          "R shape is (n_free, n_free - z_dim)",
          "R shape=%s, n_free-z_dim=%d" % (r.shape, n_free - expected_z_dim))

    ztb = z.T @ b_free
    orth_abs = float(np.linalg.norm(ztb @ r))
    orth_scale = float(np.linalg.norm(ztb.toarray())) * float(np.linalg.norm(r))
    orth_rel = orth_abs / orth_scale if orth_scale > 0.0 else float("nan")
    check(orth_rel <= ROUNDOFF,
          "Z^T B R == 0 at roundoff",
          "||Z^T B R||_F = %.3e, divided by ||Z^T B||_F ||R||_F = %.3e "
          "-> relative %.3e (tolerance %.0e)"
          % (orth_abs, orth_scale, orth_rel, ROUNDOFF))

    gram_dev = float(
        np.linalg.norm(r.T @ (b_free @ r) - np.eye(p)) / np.sqrt(p)
    )
    check(gram_dev <= ROUNDOFF,
          "R^T B R == I at roundoff",
          "||R^T B R - I||_F / sqrt(p) = %.3e with p=%d (tolerance %.0e)"
          % (gram_dev, p, ROUNDOFF))
    print("  cross-check against _complement_basis: ||Z^T B R||_F = %.3e, "
          "||R^T B R - I||_F/sqrt(p) = %.3e"
          % (info["z_orthogonality_abs"], info["r_gram_dev"]))
    return z_dim, orth_rel, gram_dev


# ----------------------------------------------------------------------
# CASE 2: plain versus deflated selection across the gradient cluster
# ----------------------------------------------------------------------
def case2():
    nx = ny = 8
    lx, ly = 2.0, 1.0
    k0_sq = 5.0
    k0 = float(np.sqrt(k0_sq))
    sigma = 4.0
    k = 6
    te10_cutoff_sq = (np.pi / lx) ** 2
    print("")
    print("CASE 2  homogeneous box, %d x %d cells over %.3f x %.3f m, PEC walls; "
          "k0^2 = %.6f (TE10 cutoff^2 = %.6f), sigma = %.6f < k0^2, k = %d"
          % (nx, ny, lx, ly, k0_sq, te10_cutoff_sq, sigma, k))
    mesh = m2.box_mesh(lx, ly, nx, ny)
    boundaries = walls(lx, ly)
    print("  mesh: %d nodes, %d triangles, %d edges, %d free edge DOFs"
          % (mesh.n_nodes, mesh.n_tris, mesh.n_edges,
             int(np.count_nonzero(~m2.pec_edge_mask(mesh, boundaries)))))

    plain = m2.solve_modes(mesh, k0, sigma, boundaries=boundaries, k=k)
    deflated = m2.solve_modes_deflated(mesh, k0, sigma, boundaries=boundaries, k=k)

    report_candidates("plain", plain, k0_sq)
    report_candidates("deflated", deflated, k0_sq)

    n_plain = spurious_count(plain.candidates, k0_sq)
    n_deflated = spurious_count(deflated.candidates, k0_sq)
    print("  spurious candidates (|beta^2-k0^2|/k0^2 <= %.0e): plain=%d of %d, "
          "deflated=%d of %d"
          % (SPURIOUS_RTOL, n_plain, len(plain.candidates),
             n_deflated, len(deflated.candidates)))
    print("  deflation diagnostics: z_dim=%d of n_free=%d free DOFs, "
          "n_columns=%d, z_dim_closed_form=%r (off the ladder, diagnostics only)"
          % (deflated.deflation["z_dim"], deflated.deflation["n_free"],
             deflated.deflation["n_columns"],
             deflated.deflation["z_dim_closed_form"]))

    check(n_plain >= 1,
          "undeflated candidate set reaches into the gradient cluster",
          "%d spurious of %d candidates, plain chosen beta^2 = %.9e "
          "(eps_eff = %.6f)" % (n_plain, len(plain.candidates), plain.beta_sq,
                                plain.beta_sq / k0_sq))
    check(n_deflated == 0,
          "deflated candidate set is free of the gradient cluster",
          "%d spurious of %d candidates, deflated chosen beta^2 = %.9e "
          "(eps_eff = %.6f)" % (n_deflated, len(deflated.candidates),
                                deflated.beta_sq, deflated.beta_sq / k0_sq))
    return deflated, n_plain, n_deflated, k0_sq, lx, nx, ny


# ----------------------------------------------------------------------
# CASE 3: coarse-mesh consistency of the deflated answer with TE10
# ----------------------------------------------------------------------
def case3(deflated, k0_sq, lx, nx, ny):
    beta_sq_max = max(beta_sq for beta_sq, _eps in deflated.candidates
                      if beta_sq > 0.0)
    analytic = k0_sq - (np.pi / lx) ** 2
    rel = abs(beta_sq_max - analytic) / analytic
    print("")
    print("CASE 3  coarse-mesh consistency check, NOT an acceptance number: "
          "largest positive beta^2 of the deflated solve against analytic TE10 "
          "k0^2 - (pi/a)^2 with a = %.3f m on %d x %d cells"
          % (lx, nx, ny))
    check(rel <= CASE3_LOOSE,
          "coarse-mesh TE10 consistency (loose bound only)",
          "beta^2 = %.9e, analytic TE10 = %.9e, relative difference = %.3e "
          "(loose bound %.0e, mesh %d cells across a = %.3f m)"
          % (beta_sq_max, analytic, rel, CASE3_LOOSE, nx, lx))
    return rel


def main():
    print("DEVELOPMENT ARTEFACT - plumbing check only, not a result.")
    print("No acceptance number is produced here, and the pre-registered anchor "
          "ladder is deliberately not touched (synthetic boxes only).")
    print("emfit.mode2d from %s" % os.path.join(_ROOT, "emfit", "mode2d.py"))

    z_dim, orth_rel, gram_dev = case1()
    deflated, n_plain, n_deflated, k0_sq, lx, nx, ny = case2()
    rel = case3(deflated, k0_sq, lx, nx, ny)

    print("")
    print("SUMMARY")
    print("  checks passed: %d, failed: %d" % (len(_PASSED), len(_FAILED)))
    print("  CASE 1 z_dim = %d, ||Z^T B R||_F relative = %.3e, "
          "||R^T B R - I||_F/sqrt(p) = %.3e" % (z_dim, orth_rel, gram_dev))
    print("  CASE 2 spurious candidates (|beta^2-k0^2|/k0^2 <= %.0e): "
          "plain = %d, deflated = %d" % (SPURIOUS_RTOL, n_plain, n_deflated))
    print("  CASE 3 relative difference from analytic TE10 = %.3e "
          "(coarse mesh, not an acceptance number)" % rel)
    for label in _FAILED:
        print("  FAILED: %s" % label)
    print("RESULT: %s" % ("PASS" if not _FAILED else "FAIL"))
    return 0 if not _FAILED else 1


if __name__ == "__main__":
    sys.exit(main())
