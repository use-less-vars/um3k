#!/usr/bin/env bash
# =============================================================================
# tools/host/attribution/run.sh
#
# Which mechanism produces the 6.41 % analytic-internal eps_eff gap -- estimator
# bias in emfit/ports.py:fit_beta, or a phantom carrying a beta that is not the
# beta it was generated with?  attribution.py answers it with phantoms of known
# beta fitted four ways (one-wave fit, two-wave fit, two-station phase
# difference, least-squares phase slope), and the readings are printed with the
# verdict last.
#
# COST: no solve, no solver output, no data file required.  About a thousand
# 9- to 13-station fit_beta calls, each a 2048-point beta scan.
# TOTAL tens of seconds (--quick is roughly a third).  OUTPUT: out/run.log only.
# Read-only w.r.t. the repo; emfit/ is only imported.  The driver is dumb: it
# prints the provenance, hands over to attribution.py, keeps the *python* exit
# status out of the pipe, and prints its own DONE line last.
#
# To settle branch (b) rather than merely bound it, hand it a phantom:
#     tools/host/attribution/run.sh --phantom path/to/phantom.npz
# where the npz holds z, v and ideally beta_label (see attribution.py --help).
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
# One answer only: hand the root to attribution.py so it cannot re-derive a
# different one.
export C1_REPO="$REPO"
OUT="$HERE/out"
mkdir -p "$OUT"
LOG="$OUT/run.log"

echo "EXPECTED COST: no solve -- phantoms are synthetic station phasors, the real"
echo "               gap enters as a quoted literal, and nothing is read from disk"
echo "               unless --phantom/--archive is given.  About a thousand"
echo "               9- to 13-station fit_beta calls, each a 2048-point beta scan."
echo "               TOTAL tens of seconds; --quick is roughly a third."
echo "repo     : $REPO"
echo "emfit    : $REPO/emfit (FOUND)"
echo "out dir  : $OUT"
echo "log      : $LOG"
echo "invoke   : python3 -u $HERE/attribution.py $*"
echo "started  : $(date -Is)"
echo "git HEAD : $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo '(git unavailable)')"
echo "python3  : $(python3 -V 2>&1)"
echo "------------------------------------------------------------------------"

# Keep the *python* step's exit status (not tee's) and still print a DONE line,
# so a crashed run is obvious in the log rather than a silent truncation.
set +e
python3 -u "$HERE/attribution.py" "$@" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
set -e

echo "DONE attribution elapsed=${SECONDS}s exit=${STATUS} log=${LOG}"
exit "$STATUS"
