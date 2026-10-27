#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# tools/host/mode_plot/run.sh -- draw the C2b pictures, metric named explicitly
#
# WHAT IT PRODUCES (no argument = --metric both, three PDFs + three PNGs)
#   docs/report/figures/c2b_mode_shape_corrected.pdf  corr_ez_vv + corr_ey  (the metric
#                                                     that is actually right)
#   docs/design/mispaired_metric_before.pdf           corr_ez_superseded + corr_ey (the
#                                                     SUPERSEDED pairing, same panels,
#                                                     same axes, same colour limits)
#   docs/design/c2b_shapes.pdf                        a second copy of the corrected
#                                                     figure at the historical path
#   each .pdf also gets a sibling .png (200 dpi)
#   tools/host/mode_plot/out/run.log                  this script's full output
#
#   The metric is chosen by --metric {corrected,before,both} on mode_plot.py; it is
#   never inferred, and corr_ez (the npz compatibility alias of the superseded
#   number) is never plotted.  Pass flags through: REPO=/path $0 --help
#
# EXPECTED COST
#   a few seconds: no eigensolve.  Two sparse assemblies (31x17 mixed pencil,
#   a few thousand edges), two sparse LUs of the (n_free_n x n_free_n) system
#   block, two interpolations onto the 201x76 plane lattice, and the render.
#   Memory: well under 200 MB.
#
# WHAT IT DOES
#   1. resolves the repo root (git first, then a walk up looking for emfit/)
#   2. exports C1_REPO so tools/host/_bootstrap.py finds the same tree
#   3. runs tools/host/mode_plot/mode_plot.py, teeing stdout+stderr into
#      out/run.log, and returns the python exit status unchanged
#
# WHAT IT NEEDS
#   the two banked spectra written by tools/host/c1-audit:
#       out/c1_spectrum.npz      (run.sh)          PMC / open top
#       out/pecbox_spectrum.npz  (pecbox_variant.py) PEC / closed box
#   and the geometry .scratch/tol/logs/TOLFLUX.json that both of those read.
#   This script does NOT create any of them: if a file is missing, mode_plot.py
#   refuses with a message naming the script that should have produced it.
#
# EXIT STATUS
#   0  figure written
#   2  could not locate the repository
#   3  mode_plot.py refused to plot (see the REFUSED block in run.log); this is
#      the interesting failure -- it means the reconstruction did not reproduce
#      a banked number, or a field was empty/NaN.  It is never a blank figure.
#   *  any other non-zero status is passed through from python3 unchanged.
#
# PROVENANCE
#   Model of this script: tools/host/c1-audit/run.sh (same header, same repo
#   resolution, same tee/status idiom).  The numbers drawn come from
#   tools/host/c1-audit/c1_audit.py:551-570 and from the redirected copy that
#   pecbox_variant.py:291-326 writes; the reconstruction of the extracted field
#   follows c1_audit.py:386-493.
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- repo root: a caller-set REPO wins (same precedence as _bootstrap.py),
# --- then git, then a walk up until a dir containing emfit/ is found.
REPO="${REPO:-}"
if [ -z "$REPO" ]; then
    REPO="$(git -C "$HERE" rev-parse --show-toplevel 2>/dev/null || true)"
fi
if [ -z "$REPO" ] || [ ! -d "$REPO/emfit" ]; then
    REPO=""
    PROBE="$HERE"
    while [ "$PROBE" != "/" ]; do
        if [ -d "$PROBE/emfit" ]; then REPO="$PROBE"; break; fi
        PROBE="$(cd "$PROBE/.." && pwd)"
    done
fi
if [ -z "$REPO" ]; then
    echo "FATAL: could not locate the repository root from $HERE." >&2
    echo "       Looked for REPO in the environment, then a git top-level," >&2
    echo "       then walked up for a dir containing emfit/.  Set REPO=<path>:" >&2
    echo "         REPO=/path/to/repo $0" >&2
    exit 2
fi

# _bootstrap.py consults REPO then C1_REPO; export both so a caller-set REPO is
# honoured and the walk from mode_plot.py lands on the same tree.
export C1_REPO="$REPO"
export REPO="$REPO"

OUT="$HERE/out"
mkdir -p "$OUT"
LOG="$OUT/run.log"

echo "EXPECTED COST: a few seconds (2 sparse assemblies, 2 sparse LUs, no eigensolve)"
echo "repo      : $REPO"
if [ -d "$REPO/emfit" ]; then
    echo "emfit     : FOUND  ($REPO/emfit)"
else
    echo "emfit     : MISSING ($REPO/emfit) -- mode_plot.py will not import"
fi
echo "out dir   : $OUT"
echo "outputs   : $REPO/docs/report/figures/c2b_mode_shape_corrected.pdf + .png  (corrected)"
echo "            $REPO/docs/design/mispaired_metric_before.pdf + .png           (before)"
echo "            $REPO/docs/design/c2b_shapes.pdf + .png                        (corrected, historical path)"
echo "log       : $LOG"
echo "started   : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "git HEAD  : $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 'not a git checkout')"
echo "python3   : $(command -v python3 || echo 'NOT FOUND')"
printf '%s\n' "----------------------------------------------------------------------"

# tee, but report python's status (not tee's): ${PIPESTATUS[0]}
set +e
python3 -u "$HERE/mode_plot.py" "$@" 2>&1 | tee -a "$LOG"
STATUS="${PIPESTATUS[0]}"
set -e

echo "DONE run.sh elapsed=${SECONDS}s exit=${STATUS} log=${LOG}"
if [ "$STATUS" -eq 3 ]; then
    echo "NOTE: exit 3 = mode_plot.py refused to draw.  The reason is the" >&2
    echo "      'REFUSED' block above; no figure was written or overwritten." >&2
fi
exit "$STATUS"
