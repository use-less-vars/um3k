#!/usr/bin/env bash
# tools/host/run-tests/run.sh -- resumable, chunked test runner for this repo.
#
# WHY THIS EXISTS
#   The full suite (483 tests, 39 files) takes ~12 min. The agent exec tool that
#   drives these runs has a HARD CAP of ~360-420 s per call: a foreground
#   `python3 -m pytest -q` is SIGKILLed at the cap, and the aggregate summary is
#   suppressed in this repo, so a killed run leaves no verdict.
#   Detaching does NOT help either (the PID-namespace trap): `setsid nohup ... &`
#   starts in the call's container, gets its own PID namespace, and is killed when
#   that call returns -- the log then freezes mid-progress line. So: foreground,
#   ONE TEST FILE PER CALL-CHUNK, with state on disk so the next call resumes.
#
# CONTRACT
#   * State:   .scratch/test_state/<file>.done   (verdict + exact counts, one per file)
#   * Results: .scratch/junit/<file>.xml        (JUnit XML, the ONLY source of counts)
#   * Log:     .scratch/test_output.log         (append; '=== <file> ===' + exit code)
#   * Order:   sorted tests/test_*.py -- deterministic, no deselect, no -x, no --lf,
#              no -p no:cacheprovider: exactly what `python3 -m pytest -q` would run.
#   * Resume:  a file with a marker is skipped; a file that was killed mid-run has
#              no XML and no marker, so it simply runs again. Idempotent.
#   * Budget:  --budget SECONDS (default 240). Checked BEFORE starting each file;
#              a file that is already running is always allowed to finish.
#
# USAGE
#   bash tools/host/run-tests/run.sh --list           # order + pending count
#   bash tools/host/run-tests/run.sh --budget 240     # run as many files as fit
#   bash tools/host/run-tests/run.sh --summary        # exact totals from the XMLs
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
cd "$ROOT" || exit 1

STATE=.scratch/test_state
JUNIT=.scratch/junit
LOG=.scratch/test_output.log
AGG="$HERE/aggregate.py"

BUDGET=240
MODE=run
while [ $# -gt 0 ]; do
  case "$1" in
    --budget)   BUDGET="${2:-240}"; shift 2 ;;
    --budget=*) BUDGET="${1#*=}"; shift ;;
    --list)     MODE=list; shift ;;
    --summary)  MODE=summary; shift ;;
    -h|--help)  sed -n '2,40p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$STATE" "$JUNIT"
FILES=$(ls tests/test_*.py | LC_ALL=C sort)

marker(){ echo "$STATE/$(basename "$1" .py).done"; }
done_q(){ [ -f "$(marker "$1")" ]; }
pending(){ for f in $FILES; do done_q "$f" || echo "$f"; done; }

if [ "$MODE" = list ]; then
  for f in $FILES; do
    if done_q "$f"; then echo "DONE    $f  [$(cat "$(marker "$f")")]"; else echo "pending $f"; fi
  done
  echo "pending: $(pending | wc -l) of $(echo "$FILES" | wc -l) files"
  exit 0
fi

if [ "$MODE" = summary ]; then
  python3 "$AGG" --summary; exit $?
fi

PYBUF=""
command -v stdbuf >/dev/null 2>&1 && PYBUF="stdbuf -oL"

START=$(date +%s)
for f in $FILES; do
  if done_q "$f"; then continue; fi
  EL=$(( $(date +%s) - START ))
  if [ "$EL" -ge "$BUDGET" ]; then
    echo "BUDGET: elapsed ${EL}s >= ${BUDGET}s -- stopping cleanly before $f; $(pending | wc -l) file(s) still pending."
    break
  fi
  base=$(basename "$f" .py); xml="$JUNIT/$base.xml"
  echo "=== $f ===" >> "$LOG"
  T0=$(date +%s)
  $PYBUF python3 -m pytest -q --junitxml="$xml" "$f" >> "$LOG" 2>&1
  RC=$?
  W=$(( $(date +%s) - T0 ))
  echo "exit=$RC wall=${W}s" >> "$LOG"
  if [ -f "$xml" ]; then
    python3 "$AGG" --mark "$f" "$RC" "$W"
  else
    echo "RUN  $f exit=$RC wall=${W}s :: NO XML (killed mid-run?) -- left pending, will re-run"
  fi
done

REM=$(pending | wc -l)
echo "---- files pending: $REM ----"
if [ "$REM" -eq 0 ]; then python3 "$AGG" --summary; fi
