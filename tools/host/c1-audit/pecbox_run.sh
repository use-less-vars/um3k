#!/usr/bin/env bash
# =============================================================================
# tools/host/c1-audit/pecbox_run.sh
#
# PEC-closed-box variant of run.sh.  Runs pecbox_variant.py, which performs the
# *same* 31 x 17 mixed solve as c1_audit.py but closes the 20 x 7.6 mm cross
# section with three outer PEC walls on top of the two existing conductors:
#
#     ground  z = 0                                    with y in [0, W]
#     strip   z = 1.6 mm                               with y in [8.5, 11.5] mm
#     wall    y = 0                     (NEW)
#     wall    y = W = 20 mm             (NEW)
#     wall    z = H = 7.6 mm            (NEW)
#
# i.e. a fully PEC-closed 20 x 7.6 mm box.  The walls are added at the emfit API
# level (the mode2d.pec_edge_mask / mode2d.pec_node_mask boundary predicates the
# solver itself calls), not by editing anything: emfit/ is untouched on disk and
# the two functions are restored from a finally block.
#
# This driver is deliberately dumb, exactly like run.sh: it prints the cost
# expectation, the git / python provenance, the exact python invocation it is
# about to make, and then hands over with stdout+stderr teed into
# out/pecbox_run.log.  Extra arguments are passed straight through to the python
# program (pecbox_variant.py understands --self-test-anchor and tolerates any
# other argument by reporting it and ignoring it).
#
# EXPECTED COST
#   * dense QZ (scipy.linalg.eig on the generalised pencil): ~95-100 s.  The
#     closed box makes *more* edges PEC than the open geometry, so the pencil
#     shrinks slightly: ~1382 x 1382 instead of run.sh's 1444 x 1444 (the mesh
#     is still 31 x 17 nodes -> 1486 edges; the PEC cut removes ~104 instead of
#     ~42 edges).  The exact counts are printed by the program, not assumed
#     here -- the O(n^3) QZ is still the dominant cost either way.
#   * peak RAM ~1-2 GB while the QZ runs (a, b dense + the QZ workspace).
#   * per-eigenvalue loop: one sparse LU back-substitution (e_z), one
#     Mode2D.e_at on 200*77 = 15400 points (e_y), one grid interpolation on
#     201*76 = 15276 points (e_z), two correlations.  ~10-20 s per pass.
#   * optional --self-test-anchor adds one extra full solve (the plain vacuum
#     20 x 7.6 mm PEC box at 10 GHz), so budget roughly double for that run.
#   * TOTAL ~2-4 min wall clock for the default run, ~4-8 min with the
#     self-test.
#
# OUTPUTS
#   tools/host/c1-audit/out/pecbox_run.log        this run's stdout+stderr
#   tools/host/c1-audit/out/pecbox_spectrum.npz   eigenvalues, real
#                                                 eigenvectors, per-column
#                                                 e_y/e_z correlations
#   tools/host/c1-audit/out/pecbox_table.txt      the full table
#
#   c1_audit.py itself writes out/c1_spectrum.npz and out/c1_table.txt when it
#   is imported; pecbox_variant.py redirects those two writes onto the pecbox_*
#   names above and verifies (sha256, before/after) that the originals were not
#   touched, so a run of this driver never overwrites run.sh's artefacts.
#
# LIVENESS: the underlying c1_audit.py run prints its own
#   "PROGRESS [heartbeat] <elapsed> s phase=<phase>"
# heartbeat (at least every 25 s), a per-column PROGRESS line inside the loop,
# and a "DONE c1_audit.py ..." summary; pecbox_variant.py then prints its own
# report block.  This driver prints its own "DONE pecbox_run.sh ..." line last.
#
# Read-only w.r.t. the repo: nothing outside tools/host/c1-audit/out/ is written.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- repository root -------------------------------------------------------
# Same discovery as run.sh, and for the same reason: NEVER count ".." levels
# for this (this file lives three levels below the root, and counting resolved
# REPO to <repo>/tools, so `import emfit` died with ModuleNotFoundError).
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
# One answer only: hand the discovered root to the program (c1_audit.py reads
# C1_REPO, and pecbox_variant.py honours it too) so it cannot re-derive another.
export C1_REPO="$REPO"
OUT="$HERE/out"
mkdir -p "$OUT"
LOG="$OUT/pecbox_run.log"

# The exact invocation, quoted, so the log records what was actually run.
INVOCATION="python3 -u \"$HERE/pecbox_variant.py\""
for _arg in "$@"; do
    INVOCATION="$INVOCATION \"$_arg\""
done

echo "EXPECTED COST: dense QZ ~95-100 s (pencil slightly smaller than run.sh's"
echo "               1444 x 1444 because the closed box makes ~104 instead of"
echo "               ~42 edges PEC; still the 31x17 node mesh, ~1382 free),"
echo "               ~1-2 GB RAM peak, per-eigenvalue loop ~10-20 s,"
echo "               TOTAL ~2-4 min wall clock (~4-8 min with --self-test-anchor)."
echo "               A PROGRESS line is printed at least every 30 s."
echo "variant  : PEC-closed 20 x 7.6 mm box (+ walls y=0, y=20mm, z=7.6mm)"
echo "repo     : $REPO"
if [ -d "$REPO/emfit" ]; then
    echo "emfit    : $REPO/emfit (FOUND)"
else
    echo "emfit    : $REPO/emfit (MISSING)"
fi
echo "out dir  : $OUT"
echo "log      : $LOG"
echo "invoke   : $INVOCATION"
echo "started  : $(date -Is)"
echo "git HEAD : $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '(git unavailable)')"
echo "python3  : $(python3 -V 2>&1)"
echo "------------------------------------------------------------------------"

# Keep the exit status of the *python* step (not tee's) and still print a DONE
# line, so a crashed run is obvious in the log rather than a silent truncation.
set +e
python3 -u "$HERE/pecbox_variant.py" "$@" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
set -e

echo "DONE pecbox_run.sh elapsed=${SECONDS}s exit=${STATUS} log=${LOG}"
exit "$STATUS"
