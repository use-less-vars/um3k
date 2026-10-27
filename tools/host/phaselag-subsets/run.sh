#!/usr/bin/env bash
# =============================================================================
# tools/host/phaselag-subsets/run.sh
#
# Is the phase-slope beta -- tools/gates_101_20.py:426-445, copied not imported
# -- a property of the line, or of the station window?  Fits it on the banked
# capture .scratch/tol/logs/TOLFLUX_planes.npz over all 9 stations and 21
# subsets of them, and prints the spread.
#
# COST: no solve (the station phasors are banked); the anchor route is a Laplace
# profile + a 9-station fit_beta.  TOTAL < 10 s.  OUTPUT: out/run.log only.
# Read-only w.r.t. the repo; emfit/ is only imported.  The driver is dumb: it
# prints the provenance, hands over to phaselag_subsets.py, keeps the *python*
# exit status out of the pipe, and prints its own DONE line last.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- repository root ---------------------------------------------------------
# NEVER count ".." levels: this file lives THREE levels below the root, and
# counting was exactly the bug that made REPO resolve to <repo>/tools, so
# `import emfit` died with ModuleNotFoundError.  Discover the root instead and
# fail loudly rather than running against a bogus one:
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
# One answer only: hand the root to phaselag_subsets.py so it cannot re-derive
# a different one.
export C1_REPO="$REPO"
OUT="$HERE/out"
mkdir -p "$OUT"
LOG="$OUT/run.log"

echo "EXPECTED COST: no solve -- the station phasors come out of the banked npz;"
echo "               the anchor route is a Laplace profile + a 9-station fit."
echo "               TOTAL well under 10 s."
echo "repo     : $REPO"
echo "emfit    : $REPO/emfit (FOUND)"
echo "out dir  : $OUT"
echo "log      : $LOG"
echo "started  : $(date -Is)"
echo "git HEAD : $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '(git unavailable)')"
echo "python3  : $(python3 -V 2>&1)"
echo "------------------------------------------------------------------------"

# Keep the *python* step's exit status (not tee's) and still print a DONE line,
# so a crashed run is obvious in the log rather than a silent truncation.
set +e
python3 -u "$HERE/phaselag_subsets.py" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
set -e

echo "DONE run.sh elapsed=${SECONDS}s exit=${STATUS} log=${LOG}"
exit "$STATUS"
