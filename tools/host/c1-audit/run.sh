#!/usr/bin/env bash
# =============================================================================
# tools/host/c1-audit/run.sh
#
# C1 audit: is the mixed 2-D pencil's *identified* eigenvector special, or does
# every propagating eigenvector look the same against the analytic plane basis?
# This driver is deliberately dumb: it prints the cost expectation, the git /
# python provenance, and then hands over to c1_audit.py with stdout+stderr
# teed into out/run.log.
#
# EXPECTED COST
#   * dense QZ (scipy.linalg.eig on the 1444 x 1444 generalised pencil): ~111 s
#     The mesh is 31 x 17 nodes -> 1486 edges, 1444 free after the PEC cut, so
#     the pencil is dense and the QZ is O(n^3) -- this is the dominant cost.
#   * peak RAM ~1-2 GB while the QZ runs (a, b dense + the QZ workspace).
#   * per-mode loop: one sparse LU back-substitution (e_z), one Mode2D.e_at on
#     200*77 = 15400 points (e_y), one grid interpolation on 201*76 = 15276
#     points (e_z), two correlations.  The reference lives on the
#     NYN x NZN = 201 x 77 plane lattice of 1e-4 cells -- NOT on the 31 x 17
#     mesh lattice: the mesh has 30 x 16 *cells*, but the plane samples
#     201 x 77 *points* over the same W x H extent, so the old "30*17 = 510"
#     figure was 30x low.
#     ~10-20 s per pass over the propagating columns.
#   * TOTAL ~2-4 min wall clock.
#
# STEPS (all implemented in c1_audit.py)
#   0. provenance: git HEAD, python / numpy / scipy versions
#   1. geometry -> structured mesh -> PEC masks -> k0 (+ banked-cache mesh check)
#   2. mixed solve with the dense-QZ capture hook, so EVERY eigenvector is kept
#   3. assemble_mixed() blocks, one splu() of the longitudinal block, and the
#      analytic plane reference (microstrip_mode_profile -> plane_mode)
#   4. loop over every propagating QZ column: e_y from Mode2D.e_at, e_z from the
#      LU back-substitution, corr against the analytic e_y / e_z
#   5. out/c1_spectrum.npz (lam, real eigenvectors, per-column corr) and
#      out/c1_table.txt (the full table, sorted by |corr_e_y|)
#   6. verdict block + reproduction check against the banked anchors
#      corr_e_y 0.9207707848111418 / corr_e_z 0.11916043239134175
#
# OUTPUTS
#   tools/host/c1-audit/out/run.log         this run's stdout+stderr (tee -a)
#   tools/host/c1-audit/out/c1_spectrum.npz eigenvalues, real eigenvectors,
#                                           per-column e_y/e_z correlations
#   tools/host/c1-audit/out/c1_table.txt    the full table
#
# LIVENESS: c1_audit.py runs a daemon heartbeat that prints
#   "PROGRESS [heartbeat] <elapsed> s phase=<phase>"
# at least every 25 s (so never longer than 30 s apart), plus a per-column
# PROGRESS line inside the loop, plus a final "DONE c1_audit.py ..." summary.
# This driver prints its own "DONE run.sh elapsed=... exit=..." line last.
#
# Read-only w.r.t. the repo: nothing outside tools/host/c1-audit/out/ is written,
# and emfit/ is never modified (the dense-QZ hook is installed on the module
# object for the duration of one call and restored in a finally block).
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- repository root -------------------------------------------------------
# NEVER count ".." levels for this: the script lives THREE levels below the
# root (<repo>/tools/host/c1-audit/run.sh), and counting was exactly the bug
# that made REPO resolve to <repo>/tools, so `import emfit` in c1_audit.py
# died with ModuleNotFoundError.  Discover the root instead, and fail loudly
# rather than running against a bogus one.
#   1. ask git (exact, and survives this file being moved)
#   2. otherwise walk up from $HERE until a directory containing emfit/ is hit
#   3. otherwise FATAL to stderr and exit 2
REPO="$(git -C "$HERE" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "${REPO:-}" ] || [ ! -d "$REPO/emfit" ]; then
    REPO="$HERE"
    while [ ! -d "$REPO/emfit" ]; do
        if [ "$REPO" = "/" ]; then
            echo "FATAL: cannot find the repository root." >&2
            echo "       started at : $HERE" >&2
            echo "       walked up  : to / without finding it" >&2
            echo "       looked for : <dir>/emfit (an emfit/ package directory)" >&2
            exit 2
        fi
        REPO="$(dirname "$REPO")"
    done
fi
# One answer only: hand the discovered root to c1_audit.py so that it cannot
# re-derive a different one.
export C1_REPO="$REPO"
OUT="$HERE/out"
mkdir -p "$OUT"
LOG="$OUT/run.log"

echo "EXPECTED COST: dense QZ ~111 s (1444 x 1444 pencil from the 31x17 node mesh,"
echo "               1486 edges / 1444 free after the PEC cut), ~1-2 GB RAM peak,"
echo "               per-mode loop ~10-20 s, TOTAL ~2-4 min wall clock."
echo "               A PROGRESS line is printed at least every 30 s."
echo "repo     : $REPO"
if [ -d "$REPO/emfit" ]; then
    echo "emfit    : $REPO/emfit (FOUND)"
else
    echo "emfit    : $REPO/emfit (MISSING)"
fi
echo "out dir  : $OUT"
echo "log      : $LOG"
echo "started  : $(date -Is)"
echo "git HEAD : $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '(git unavailable)')"
echo "python3  : $(python3 -V 2>&1)"
echo "------------------------------------------------------------------------"

# Keep the exit status of the *python* step (not tee's) and still print a DONE
# line, so a crashed run is obvious in the log rather than a silent truncation.
set +e
python3 -u "$HERE/c1_audit.py" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
set -e

echo "DONE run.sh elapsed=${SECONDS}s exit=${STATUS} log=${LOG}"
exit "$STATUS"
