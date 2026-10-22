#!/usr/bin/env bash
# m3a smoke -- one short CW record of the 7.8333 GHz board tone with the
# cross-section (plane) phasor capture switched ON, then the plane-phasor flux
# compared per station against the time-domain station Poynting mean that the
# same record carries.  Gate: every station within 1 pc of the closed-form
# scale N**2/4.
#
#   bash .scratch/host/m3a-smoke/run.sh            # preflight + solve + checks
#   bash .scratch/host/m3a-smoke/run.sh --force    # same, overwrite a good dump
#
# `set -e` is deliberately absent: every failure must still reach the later
# sections and leave manifest.md behind.  `set -u` and `set -o pipefail` are on.
# No prompts, no `read`, no `>/dev/null` anywhere.
#
# Exit codes:
#   0 PASS | 2 usage | 10 interpreter | 11 numpy/scipy | 12 emfit/inputs
#  13 disk  | 14 memory | 15 clobber refused | 16 solve failed | 17 artefacts
#  18 analysis | 19 gate FAIL
#  20 solve-context probe (the runner's own imports, before any solve)
#  21 warm-up pair half-set / non-numeric / POY_SMOKE disagreeing with it
#  22 root or run directory could not be resolved (no write was attempted)
set -u
set -o pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# The repository root is found by walking UP from the script, not by counting
# `..` segments.  A fixed relative path is only correct at one exact depth, and
# it fails silently the moment the script is copied elsewhere (a scan run
# directory, a proof copy, a deeper scratch tree): the old `${SELF_DIR}/../../..`
# resolves to a real, wrong directory rather than to nothing.  The walk is
# bounded, and a directory qualifies as the root on the two markers a checkout
# always carries: an `emfit/` directory, or a `.git` (a directory in a normal
# clone, a plain file in a worktree).
ROOT=""
WALK_DIR="${SELF_DIR}"
WALK_N=0
while [ "${WALK_N}" -lt 8 ]; do
    if [ -d "${WALK_DIR}/emfit" ] || [ -e "${WALK_DIR}/.git" ]; then
        ROOT="${WALK_DIR}"
        break
    fi
    WALK_UP="$(cd "${WALK_DIR}/.." && pwd -P)" || break
    [ "${WALK_UP}" = "${WALK_DIR}" ] && break
    WALK_DIR="${WALK_UP}"
    WALK_N=$(( WALK_N + 1 ))
done
if [ -z "${ROOT}" ]; then
    echo "run.sh: cannot find the repository root above ${SELF_DIR}" >&2
    echo "run.sh: searched that directory and up to 8 parent directories for 'emfit/' (a directory) or '.git' (a directory or a worktree file)" >&2
    echo "run.sh: nothing was written -- exit 22" >&2
    exit 22
fi
if ! cd "${ROOT}"; then
    echo "run.sh: cannot cd to ${ROOT}" >&2
    echo "run.sh: the root was located by the walk above but cannot be entered" >&2
    echo "run.sh: nothing was written -- exit 22" >&2
    exit 22
fi

# `RUN_DIR` is where every artefact of this run lands.  It defaults to the
# script's own directory -- the historical behaviour, unchanged -- and is
# validated below, once the invocation's own refusals have had their say.
RUN_DIR="${RUN_DIR:-${SELF_DIR}}"

# `python3 /path/to/script.py` puts the *script's own directory* at
# `sys.path[0]`; it never puts the current directory there.  The `cd` above
# therefore does nothing for the runner in `.scratch/m2/`, whose imports of
# `emfit` would otherwise fail with `ModuleNotFoundError: No module named
# 'emfit'`.  The repository root is exported here, once, as the single source
# of truth for every python invocation below (preflight and solve alike).
PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONPATH

RUNNER="${ROOT}/.scratch/m2/board_run_cw_poynting.py"
TONE_GHZ="7.8333"
SMOKE_DEFAULT="1785"          # established smoke length: n_warm 446, n_acc 1339
MEM_REQ_MB=3800               # this board's own production guard (peak 2.8-3.6 GB)
DISK_REQ_MB=200               # artefacts are < 10 MB; 200 MiB is the headroom asked

FORCE=0
PREFLIGHT_ONLY=0
REUSE=0
case "${1:-}" in
    "")               ;;
    --force)          FORCE=1 ;;
    --preflight-only) PREFLIGHT_ONLY=1 ;;
    --reuse-record)   REUSE=1 ;;
    *) echo "usage: bash $0 [--force] [--preflight-only] [--reuse-record]   (no argument = full smoke)" >&2
       echo "  --force           overwrite a plane record that is already complete" >&2
       echo "  --preflight-only  stop after the import probes, print the solve command" >&2
       echo "  --reuse-record    skip the solve and check the complete record already on disk" >&2
       echo "  POY_WARM=N POY_NACC=M" >&2
       echo "                    move the warm-up split for the settling scan: n_warm=N, n_acc=M," >&2
       echo "                    record POY_SMOKE=N+M.  The two must be set TOGETHER; either one" >&2
       echo "                    alone, a non-numeric value, or a POY_SMOKE != N+M exits 21" >&2
       exit 2 ;;
esac

SOLVE_OUT="${RUN_DIR}/solve.out"
MANIFEST="${RUN_DIR}/manifest.md"
STATUS="${RUN_DIR}/status.tsv"
ART_TXT="${RUN_DIR}/artefacts.txt"
ANA_TXT="${RUN_DIR}/analysis.txt"
ANA_JSON="${RUN_DIR}/analysis.json"
VERDICT_TXT="${RUN_DIR}/verdict.txt"

# ---- warm-up split: POY_WARM / POY_NACC, resolved and refused ---------
# This block runs BEFORE the first write to the run directory (the `: >`
# truncations just below), before the disk (13) / memory (14) / clobber (15)
# probes and before the solve.  A half-set pair, a non-numeric pair or a
# POY_SMOKE that disagrees with the pair is a bad invocation, and a bad
# invocation must not touch the run directory -- not even by truncating
# manifest.md -- so every refusal below exits 21 from here.
#
# POY_WARM=n_warm and POY_NACC=n_acc are the settling scan's knob: they move
# the warm-up split without moving the record, so every point of the scan
# shares one record length (nsteps = POY_SMOKE = POY_WARM + POY_NACC).  They
# are a pair on purpose -- set one alone and the other would have to be
# guessed, which is exactly what this script refuses to do.
POY_WARM="${POY_WARM:-}"
POY_NACC="${POY_NACC:-}"
SMOKE_WAS_SET=0
if [ -n "${POY_SMOKE:-}" ]; then SMOKE_WAS_SET=1; fi
POY_SMOKE="${POY_SMOKE:-${SMOKE_DEFAULT}}"

# Digits only, and non-empty: that is what "positive integer" means here.
WARM_INT=0
NACC_INT=0
SMOKE_INT=0
case "${POY_WARM}" in
    ""|*[!0-9]*) WARM_INT=0 ;;
    *)           WARM_INT=1 ;;
esac
case "${POY_NACC}" in
    ""|*[!0-9]*) NACC_INT=0 ;;
    *)           NACC_INT=1 ;;
esac
case "${POY_SMOKE}" in
    ""|*[!0-9]*) SMOKE_INT=0 ;;
    *)           SMOKE_INT=1 ;;
esac

if [ -z "${POY_WARM}" ] && [ -z "${POY_NACC}" ]; then
    # Neither set (or both empty): the record every earlier M3a run produced.
    # The arithmetic here is the runner's own default, replayed for display.
    warm_source="default-fraction"
    n_acc_source="default-fraction"
    N_WARM=$(( POY_SMOKE / 4 ))
    N_ACC=$(( POY_SMOKE - POY_SMOKE / 4 ))
elif [ -z "${POY_WARM}" ] || [ -z "${POY_NACC}" ]; then
    # Exactly one of the pair: refuse rather than guess the missing half.
    if [ -n "${POY_WARM}" ]; then
        PAIR_SET="POY_WARM=${POY_WARM}"
        PAIR_MISSING="POY_NACC"
    else
        PAIR_SET="POY_NACC=${POY_NACC}"
        PAIR_MISSING="POY_WARM"
    fi
    echo "run.sh: warm-up pair half-set: ${PAIR_SET} was set, ${PAIR_MISSING} is missing" >&2
    echo "run.sh: POY_WARM and POY_NACC must be given together -- they are the pair that fixes the warm-up split (n_warm, n_acc) for the settling scan" >&2
    echo "run.sh: refusing to guess ${PAIR_MISSING}: set it too, or unset ${PAIR_SET%%=*} as well for the default nsteps/4 split -- exit 21" >&2
    exit 21
else
    # Both set: both must be positive integers, and their sum is the record.
    if [ "${WARM_INT}" -eq 0 ] || [ "${NACC_INT}" -eq 0 ]; then
        echo "run.sh: warm-up pair not a pair of positive integers: POY_WARM='${POY_WARM}' POY_NACC='${POY_NACC}'" >&2
        echo "run.sh: POY_WARM and POY_NACC are step counts and must be positive integers (digits only)" >&2
        echo "run.sh: refusing to run with a non-numeric step count -- exit 21" >&2
        exit 21
    fi
    N_WARM=$(( POY_WARM ))
    N_ACC=$(( POY_NACC ))
    if [ "${N_WARM}" -lt 1 ] || [ "${N_ACC}" -lt 1 ]; then
        echo "run.sh: warm-up pair not positive: POY_WARM=${N_WARM} POY_NACC=${N_ACC}" >&2
        echo "run.sh: both must be at least 1 step (n_warm=0 is a hard start, n_acc=0 records nothing)" >&2
        echo "run.sh: refusing to run with a zero step count -- exit 21" >&2
        exit 21
    fi
    if [ "${SMOKE_WAS_SET}" -eq 1 ]; then
        # POY_SMOKE was given as well: it may only agree with the pair.
        if [ "${SMOKE_INT}" -eq 0 ] || [ "${POY_SMOKE}" -ne "$(( N_WARM + N_ACC ))" ]; then
            echo "run.sh: POY_SMOKE and the warm-up pair disagree: POY_SMOKE=${POY_SMOKE}, POY_WARM=${N_WARM}, POY_NACC=${N_ACC} (POY_WARM+POY_NACC=$(( N_WARM + N_ACC )))" >&2
            echo "run.sh: with the pair set the record length is POY_WARM + POY_NACC, so POY_SMOKE may only repeat that sum" >&2
            echo "run.sh: refusing to pick one of the two record lengths: drop POY_SMOKE, or make it $(( N_WARM + N_ACC )) -- exit 21" >&2
            exit 21
        fi
    fi
    POY_SMOKE=$(( N_WARM + N_ACC ))
    warm_source="POY_WARM"
    n_acc_source="POY_NACC"
fi

# ---- RUN_DIR: resolved, created if needed, and proved writable ---------
# Every artefact this script produces lands in RUN_DIR, so RUN_DIR has to be
# settled before the first write to it.  A run directory that cannot be
# resolved is a bad invocation, not a failed run: like the warm-up pair above,
# it must not touch anything, so every refusal here exits 22.
case "${RUN_DIR}" in
    /*) ;;
    *)  echo "run.sh: RUN_DIR must be an absolute path: RUN_DIR=${RUN_DIR}" >&2
        echo "run.sh: a relative run directory would silently mean a different place depending on the caller's cwd" >&2
        echo "run.sh: nothing was written -- exit 22" >&2
        exit 22 ;;
esac
RUN_DIR_PARENT="$(dirname "${RUN_DIR}")"
if [ ! -d "${RUN_DIR_PARENT}" ]; then
    echo "run.sh: the parent of RUN_DIR does not exist: RUN_DIR=${RUN_DIR}, parent=${RUN_DIR_PARENT}" >&2
    echo "run.sh: this script creates the run directory itself, but it will not invent a missing parent chain" >&2
    echo "run.sh: nothing was created -- exit 22" >&2
    exit 22
fi
if [ ! -d "${RUN_DIR}" ]; then
    if ! mkdir "${RUN_DIR}"; then
        echo "run.sh: cannot create the run directory: RUN_DIR=${RUN_DIR}" >&2
        echo "run.sh: its parent ${RUN_DIR_PARENT} exists, so this is a permission or name problem" >&2
        echo "run.sh: nothing was created -- exit 22" >&2
        exit 22
    fi
fi
if ! RUN_DIR="$(cd "${RUN_DIR}" && pwd -P)"; then
    echo "run.sh: cannot resolve the run directory: RUN_DIR=${RUN_DIR}" >&2
    echo "run.sh: it exists but could not be entered (permissions?)" >&2
    echo "run.sh: nothing was written -- exit 22" >&2
    exit 22
fi
if [ ! -w "${RUN_DIR}" ]; then
    echo "run.sh: the run directory is not writable: RUN_DIR=${RUN_DIR}" >&2
    echo "run.sh: every artefact of this run lands there, so there is nothing this script could do" >&2
    echo "run.sh: nothing was written -- exit 22" >&2
    exit 22
fi

: > "${MANIFEST}"
: > "${STATUS}"
: > "${ART_TXT}"
: > "${ANA_TXT}"
: > "${VERDICT_TXT}"

EMFIT_BIN_DUMP="${EMFIT_BIN_DUMP:-${RUN_DIR}/plane_record.npz}"
EMFIT_PLANE_CAPTURE=1
PYTHONUNBUFFERED=1
export POY_SMOKE POY_WARM POY_NACC EMFIT_BIN_DUMP EMFIT_PLANE_CAPTURE PYTHONUNBUFFERED
PLANE_NPZ="${EMFIT_BIN_DUMP}"

T0=$(date +%s)
TAILED=0
EARLY_REASON=""
# The solve has NOT run yet.  SOLVE_RAN stays 0 and SOLVE_RC stays the string
# sentinel NOT_RUN until the solve phase actually reports a status.  A verdict
# must be able to tell three cases apart -- solve ran and failed (SOLVE_RAN=1
# with the real code), solve never ran (SOLVE_RAN=0, SOLVE_RC=NOT_RUN), solve
# ran and succeeded (SOLVE_RAN=1, SOLVE_RC=0).  These defaults live here, with
# the other pre-solve state, and NOT beside the late ANA_RC: their old home was
# after the solve and after ARTEFACTS, where ``SOLVE_RC=99`` silently replaced
# the real exit code and made every verdict report a failure that never happened.
SOLVE_RAN=0
SOLVE_RC=NOT_RUN

mark()  { echo ""; echo "=== [$1] $(date -u +%H:%M:%S) ==="; }
mf()    { printf '%s\n' "$*" >> "${MANIFEST}"; }
saymf() { printf '%s\n' "$*" | tee -a "${MANIFEST}"; }
note()  { printf '%s\t%s\n' "$1" "$2" >> "${STATUS}"; }

tail_section() {
    [ "${TAILED}" = "1" ] && return 0
    TAILED=1
    {
        echo ""
        echo "## Exit codes  (per command, captured separately)"
        echo ""
        echo "| command | exit |"
        echo "|---|---|"
        while IFS="$(printf '\t')" read -r _n _r; do
            [ -n "${_n}" ] && printf '| `%s` | %s |\n' "${_n}" "${_r}"
        done < "${STATUS}"
        echo ""
        echo "## Wall clock"
        echo ""
        printf 'total **%s s** (%.1f min)\n' \
            "$(( $(date +%s) - T0 ))" \
            "$(awk -v s="$(( $(date +%s) - T0 ))" 'BEGIN {print s/60.0}')"
        echo ""
        echo "## Verdict"
        echo ""
        if [ -s "${VERDICT_TXT}" ]; then
            cat "${VERDICT_TXT}"
        else
            printf 'VERDICT: FAIL (did not reach the gate) -- %s\n' \
                "${EARLY_REASON:-the run stopped before the verdict was computed}"
        fi
    } >> "${MANIFEST}"
}
on_exit() {
    local c=$?
    tail_section
    echo ""
    echo "EXIT=${c}"
    echo "TOTAL_ELAPSED=$(( $(date +%s) - T0 ))s"
    echo "manifest: ${MANIFEST}"
}
trap on_exit EXIT

# =====================================================================
mark "PREFLIGHT"

saymf "# m3a smoke -- plane-phasor capture, ${TONE_GHZ} GHz board tone"
saymf ""
saymf "One short CW record with the cross-section (plane) phasor capture on, then"
saymf "the plane-phasor flux compared per station against the time-domain station"
saymf "Poynting mean of the same record. Gate: every station within 1 pc of the"
saymf "closed-form scale \`N**2/4\`."
saymf ""
saymf "- started (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# ---- host -----------------------------------------------------------
UNAME_S="$(uname -srm)"
UNAME_RC=$?
note "uname -srm" "${UNAME_RC}"
NCORES="$(nproc)"
CORE_RC=$?
[ -z "${NCORES}" ] && NCORES="$(getconf _NPROCESSORS_ONLN)"
note "nproc" "${CORE_RC}"
echo "host      ${UNAME_S}  (${NCORES} cores)"
mf "- host: ${UNAME_S}, ${NCORES} cores"

# ---- HEAD -----------------------------------------------------------
HEAD_SHA="$(git rev-parse HEAD)"
HEAD_RC=$?
note "git rev-parse HEAD" "${HEAD_RC}"
HEAD_BR="$(git rev-parse --abbrev-ref HEAD)"
BR_RC=$?
note "git rev-parse --abbrev-ref HEAD" "${BR_RC}"
echo "HEAD      ${HEAD_SHA} (${HEAD_BR})"
mf "- HEAD: \`${HEAD_SHA}\` on \`${HEAD_BR}\`"
saymf "- repo root: \`${ROOT}\` -- found by walking up from the script and stopping at the first directory that holds \`emfit/\` or \`.git\`, not by a fixed number of \`..\` segments"
saymf "- run dir: \`${RUN_DIR}\` -- every artefact of this run lands here"
saymf "- script: \`${SELF_DIR}\` -- this file's own directory, where it was copied to, which need not be the run directory"
saymf ""
saymf "**\`RUN_DIR\` is where every artefact of this run lands.** Changing it changes only where the results are written, never the physics: the record length, the warm-up split, the tone and the gate are the same wherever the bytes land. One installation of this script therefore serves every point of a scan, with only \`RUN_DIR\` varying."

# ---- interpreter, numpy/scipy, emfit ---------------------------------
echo ""
echo "-- interpreter (first candidate that passes all three probes wins)"
PY=""
PY_VER=""
BEST_FAIL=10
for cand in "${ROOT}/.venv/bin/python3" "python3"; do
    case "${cand}" in
        /*) [ -x "${cand}" ] || { echo "   skip  ${cand}  (not executable)"; continue; } ;;
    esac
    v="$("${cand}" -c 'import sys; print("%s %s" % (sys.version.split()[0], sys.executable))')"
    r1=$?
    note "python version ${cand}" "${r1}"
    echo "   ${cand}: version rc=${r1}  ${v}"
    if [ "${r1}" -ne 0 ]; then
        echo "   FAIL(interpreter): ${cand} cannot run"
        continue
    fi
    m="$("${cand}" -c 'import numpy, scipy; print("numpy %s / scipy %s" % (numpy.__version__, scipy.__version__))')"
    r2=$?
    note "import numpy, scipy (${cand})" "${r2}"
    echo "   ${cand}: numpy/scipy rc=${r2}  ${m}"
    if [ "${r2}" -ne 0 ]; then
        echo "   FAIL(numpy/scipy): ${cand} lacks numpy and/or scipy"
        BEST_FAIL=11
        continue
    fi
    e="$(cd "${ROOT}" && PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}" "${cand}" -c 'import emfit.studies as S; print("emfit.studies ok, %s=%r" % (S.BIN_DUMP_ENV, S.BIN_DUMP_ENV))')"
    r3=$?
    note "import emfit.studies (${cand})" "${r3}"
    echo "   ${cand}: emfit rc=${r3}  ${e}"
    if [ "${r3}" -ne 0 ]; then
        echo "   FAIL(emfit): ${cand} cannot import emfit.studies"
        BEST_FAIL=12
        continue
    fi
    PY="${cand}"
    PY_VER="${v}"
    break
done
if [ -z "${PY}" ]; then
    EARLY_REASON="no interpreter passed the version/numpy-scipy/emfit probes; nothing was launched"
    echo "FAIL(preflight): ${EARLY_REASON}"
    mf ""
    mf "**FAIL(preflight)**: ${EARLY_REASON}"
    exit "${BEST_FAIL}"
fi
echo "   chosen  ${PY}"
mf "- interpreter: \`${PY_VER}\` (${PY})"
mf "- PYTHONPATH (solve): \`${PYTHONPATH}\`"

# ---- solve-context import probe (exit 20) ---------------------------
echo ""
echo "-- solve-context import probe (the runner's own imports, no solve)"
# The `-c 'import emfit.studies'` check above proves only that the
# interpreter *can be told* where the package is; it says nothing about the
# context the solve actually gets.  The solve runs the runner as a file, and
# that is a different import context.  So run the real runner, on the real
# path, with the cwd and environment the solve will get, and no argument:
# `main()` then refuses at once with a printed `usage:` line and status 2,
# while every module-scope import (numpy, `emfit.studies`, `emfit.board`) has
# already run.  A numeric-looking argument is never passed -- `main()` would
# start a real solve before the import verdict could be read.
SOLVE_PROBE="${RUN_DIR}/.solve_context_probe.out"
"${PY}" -u "${RUNNER}" > "${SOLVE_PROBE}" 2>&1
SOLVE_PROBE_RC=$?
note "solve-context probe: runner with no argv" "${SOLVE_PROBE_RC}"
cat "${SOLVE_PROBE}"
SOLVE_PROBE_WHY=""
if grep -q -E 'Traceback|ModuleNotFoundError' "${SOLVE_PROBE}"; then
    SOLVE_PROBE_WHY="the runner raised while importing, in the solve's own context (see ${SOLVE_PROBE})"
elif [ "${SOLVE_PROBE_RC}" -ne 2 ]; then
    SOLVE_PROBE_WHY="the runner exited ${SOLVE_PROBE_RC} for no argument; status 2 (usage) was expected"
elif ! grep -q 'usage:' "${SOLVE_PROBE}"; then
    SOLVE_PROBE_WHY="the runner exited 2 but printed no 'usage:' line"
fi
if [ -n "${SOLVE_PROBE_WHY}" ]; then
    EARLY_REASON="solve-context probe failed: ${SOLVE_PROBE_WHY}"
    echo "FAIL(solve-context): ${EARLY_REASON}"
    mf ""
    mf "**FAIL(solve-context)**: ${EARLY_REASON}"
    exit 20
fi
rm -f "${SOLVE_PROBE}"
echo "   solve-context probe OK: imports ran, usage returned, status 2, no traceback"
mf "- solve-context probe: runner reached \`main()\` with status 2, no import traceback"

# ---- --preflight-only: print the exact solve command, then stop ------
# Placed before the disk (13) and memory (14) gates on purpose: on a box
# whose memory or disk is short, those gates would refuse before the import
# question could be answered, and the import answer is the cheap one.
if [ "${PREFLIGHT_ONLY}" -eq 1 ]; then
    echo ""
    echo "-- preflight only: from ${ROOT}, the SOLVE phase would run exactly:"
    echo ""
    echo "  cd ${ROOT}"
    echo "  PYTHONPATH=${PYTHONPATH} \\"
    echo "  POY_SMOKE=${POY_SMOKE} \\"
    echo "  POY_WARM=${POY_WARM} \\"
    echo "  POY_NACC=${POY_NACC} \\"
    echo "  EMFIT_BIN_DUMP=${PLANE_NPZ} \\"
    echo "  EMFIT_PLANE_CAPTURE=${EMFIT_PLANE_CAPTURE} \\"
    echo "  PYTHONUNBUFFERED=1 \\"
    echo "    ${PY} -u ${RUNNER} ${TONE_GHZ} 2>&1 | tee ${SOLVE_OUT}"
    echo ""
    mf "- **preflight only**: stopped after the import probes; no solve launched"
    echo "preflight-only: no solve launched, exit 0"
    exit 0
fi

# ---- disk -----------------------------------------------------------
echo ""
DISK_AVAIL_MB="$(df -Pk "${RUN_DIR}" | awk 'NR==2 {print int($4/1024)}')"
DISK_RC=$?
note "df -Pk ${RUN_DIR}" "${DISK_RC}"
echo "disk      ${DISK_AVAIL_MB} MiB free on the run dir; required ${DISK_REQ_MB} MiB (plane record ~8.8 MB on this mesh, artefacts < 10 MB)"
mf "- disk: ${DISK_AVAIL_MB} MiB free at \`${RUN_DIR}\`, ${DISK_REQ_MB} MiB required"
if [ -z "${DISK_AVAIL_MB}" ] || [ "${DISK_AVAIL_MB}" -lt "${DISK_REQ_MB}" ]; then
    EARLY_REASON="only ${DISK_AVAIL_MB:-unknown} MiB free, ${DISK_REQ_MB} MiB required"
    echo "FAIL(disk): ${EARLY_REASON}; nothing was launched"
    mf ""
    mf "**FAIL(disk)**: ${EARLY_REASON}; nothing was launched"
    exit 13
fi

# ---- memory ---------------------------------------------------------
echo ""
MEM_TOTAL_MB="$(awk '/^MemTotal:/ {printf "%d", $2/1024}' /proc/meminfo)"
MT_RC=$?
note "MemTotal (/proc/meminfo)" "${MT_RC}"
MEM_AVAIL_MB="$(awk '/^MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo)"
MA_RC=$?
note "MemAvailable (/proc/meminfo)" "${MA_RC}"
echo "memory    MemTotal ${MEM_TOTAL_MB:-unknown} MB, MemAvailable ${MEM_AVAIL_MB:-unknown} MB; required ${MEM_REQ_MB} MB"
echo "          production figure: this board coupon is a 322x200x76 mesh at 0.1 mm;"
echo "          the full 8034-step run peaked at 2.8-3.6 GB, and ${MEM_REQ_MB} MB is the"
echo "          guard that run itself used.  Plane capture adds ~8.8 MB."
mf "- memory: MemTotal ${MEM_TOTAL_MB:-unknown} MB, MemAvailable ${MEM_AVAIL_MB:-unknown} MB, ${MEM_REQ_MB} MB required (production peak 2.8-3.6 GB on the 322x200x76 mesh at 0.1 mm; plane capture +8.8 MB)"
if [ -z "${MEM_AVAIL_MB}" ] || [ "${MEM_AVAIL_MB}" -lt "${MEM_REQ_MB}" ]; then
    EARLY_REASON="MemAvailable ${MEM_AVAIL_MB:-unknown} MB < ${MEM_REQ_MB} MB required; close other large apps and re-run"
    echo "FAIL(memory): ${EARLY_REASON}; nothing was launched"
    mf ""
    mf "**FAIL(memory)**: ${EARLY_REASON}; nothing was launched"
    exit 14
fi

# ---- clobber --------------------------------------------------------
echo ""
PROBE="$("${PY}" -c '
import sys
import numpy as np
p = sys.argv[1]
# The full key set the ARTEFACTS block demands: 10 plane keys + the
# provenance key + sx_station.  A record written before ``plane_capture``
# existed is therefore stale (11 keys), not complete, and needs no --force.
KEYS = ("plane_Ey", "plane_Ez", "plane_Hy", "plane_Hz",
        "plane_station_cells", "plane_station_x", "plane_f", "plane_dt",
        "plane_n_samples", "plane_convention", "plane_capture",
        "sx_station")
try:
    with np.load(p) as z:
        miss = [k for k in KEYS if k not in z.files]
    print("GOOD" if not miss else "STALE missing=" + ",".join(miss))
except FileNotFoundError:
    print("ABSENT")
except Exception as exc:                                   # noqa: BLE001
    print("STALE unreadable=%r" % (exc,))
' "${PLANE_NPZ}")"
PROBE_RC=$?
note "clobber probe ${PLANE_NPZ}" "${PROBE_RC}"
echo "clobber   ${PLANE_NPZ}: ${PROBE:-probe produced nothing}"
case "${PROBE%% *}" in
    GOOD)
        if [ "${REUSE}" -eq 1 ]; then
            echo "          complete plane record present; REUSED as-is (--reuse-record), no re-solve"
            mf "- clobber: \`${PLANE_NPZ}\` already held a complete plane record; \`--reuse-record\` given, so the record is reused and not overwritten"
        elif [ "${FORCE}" -eq 1 ]; then
            echo "          complete plane record present; overwriting (--force)"
            mf "- clobber: \`${PLANE_NPZ}\` already held a complete plane record, overwritten (\`--force\`)"
        else
            EARLY_REASON="'${PLANE_NPZ}' already holds a complete plane record; refusing to overwrite it (re-run with --force)"
            echo "FAIL(clobber): ${EARLY_REASON}"
            mf ""
            mf "**FAIL(clobber)**: ${EARLY_REASON}"
            exit 15
        fi
        ;;
    ABSENT)
        if [ "${REUSE}" -eq 1 ]; then
            EARLY_REASON="--reuse-record was given but '${PLANE_NPZ}' does not exist (probe: ${PROBE}); --reuse-record requires a complete plane record to reuse and never re-solves"
            echo "FAIL(reuse): ${EARLY_REASON}"
            mf ""
            mf "**FAIL(reuse)**: ${EARLY_REASON}"
            exit 15
        fi
        echo "          absent -- nothing to overwrite"
        mf "- clobber: \`${PLANE_NPZ}\` absent" ;;
    *)
        if [ "${REUSE}" -eq 1 ]; then
            EARLY_REASON="--reuse-record was given but '${PLANE_NPZ}' is not a complete plane record (probe: ${PROBE}); a partial or stale record is never reused, and --reuse-record never re-solves"
            echo "FAIL(reuse): ${EARLY_REASON}"
            mf ""
            mf "**FAIL(reuse)**: ${EARLY_REASON}"
            exit 15
        fi
        echo "          not a complete plane record (${PROBE}); it will be overwritten"
        mf "- clobber: \`${PLANE_NPZ}\` was stale (${PROBE}), overwritten" ;;
esac
mkdir -p "$(dirname "${PLANE_NPZ}")"

# ---- the four env vars, resolved -------------------------------------
echo ""
echo "env       POY_SMOKE=${POY_SMOKE}"
echo "          EMFIT_BIN_DUMP=${EMFIT_BIN_DUMP}"
echo "          EMFIT_PLANE_CAPTURE=${EMFIT_PLANE_CAPTURE}"
echo "          PYTHONUNBUFFERED=${PYTHONUNBUFFERED}"
echo "          (record length ${POY_SMOKE} steps => n_warm ${N_WARM} [${warm_source}], n_acc ${N_ACC} [${n_acc_source}];"
echo "           at 0.3274 s/step that is ~$(awk -v n="${POY_SMOKE}" 'BEGIN {printf "%.1f", n*0.3274/60.0}') min)"
mf ""
mf "## Environment (resolved)"
mf ""
mf "- \`POY_SMOKE=${POY_SMOKE}\` -- record length in steps, as RESOLVED: n_warm=${N_WARM} (source \`${warm_source}\`), n_acc=${N_ACC} (source \`${n_acc_source}\`); the runner snaps the tone to its own bin"
mf "- \`POY_WARM=${POY_WARM:-<unset>}\`, \`POY_NACC=${POY_NACC:-<unset>}\` -- the warm-up pair as asked for: \`warm_source=${warm_source}\`, \`n_acc_source=${n_acc_source}\`"
mf "- \`warm_source=default-fraction\` and \`n_acc_source=default-fraction\` mean no pair was given, and n_warm=nsteps/4, n_acc=nsteps-nsteps/4 were derived exactly as every earlier M3a run derived them: the record is produced identically to every earlier M3a record"
mf "- record path: driver route 1 -- \`warm_shim\` stands in for \`emfit.studies.microstrip_wave\` for the length of the single \`microstrip_wave_board\` call, so \`n_warm\` is filled in on the way past and \`emfit/\` is unmodified"
mf "- \`EMFIT_BIN_DUMP=${EMFIT_BIN_DUMP}\` -- where emfit.studies writes the plane record"
mf "- \`EMFIT_PLANE_CAPTURE=${EMFIT_PLANE_CAPTURE}\` -- asks emfit.studies for the plane phasors; the record must echo \`plane_capture=\"env\"\` back, which is the provenance this run asserts"
mf "- \`PYTHONUNBUFFERED=${PYTHONUNBUFFERED}\` -- stdout unbuffered, so the PROGRESS lines reach \`tee\` live (python is also given \`-u\`)"
# ---- PRE-REGISTRATION ------------------------------------------------
# The settling scan, committed to the manifest BEFORE any of its numbers
# exist: three points, one fixed accept window, one stopping rule, and the
# reading each outcome licenses.  Written by the harness on every run,
# including runs that never reach the scan, so the document that carries a
# result also carries the reading that was fixed in advance.  Nothing here
# is fitted to a measurement.
PREREG_NACC=1339              # the accept window, held fixed at all three points
PREREG_WARM_A=446             # point A: the existing smoke split
PREREG_WARM_B=1000            # point B
PREREG_WARM_C=2000            # point C
PREREG_SMOKE_A=$(( PREREG_WARM_A + PREREG_NACC ))
PREREG_SMOKE_B=$(( PREREG_WARM_B + PREREG_NACC ))
PREREG_SMOKE_C=$(( PREREG_WARM_C + PREREG_NACC ))
saymf ""
saymf "## Pre-registration -- the settling scan, fixed before the data"
saymf ""
saymf "**Fixed quantity: \`POY_NACC=${PREREG_NACC}\` at all three points.** The accept window is held fixed and only the warm-up moves. Holding it fixed is what keeps the yardstick fixed: every deviation is normalised by the same \`N\`, so the closed-form scale \`N**2/4\` and the 1 pc gate mean the same thing at each point, and a change in the deviation can only be a change in the warm-up. Move both at once and the three points are not comparable to anything."
saymf ""
saymf "**The three scan points.** The record length is the pair's sum, computed here from the pair and not asserted in prose:"
saymf ""
saymf "| point | \`POY_WARM\` | \`POY_NACC\` | implied \`POY_SMOKE\` | what it is |"
saymf "|---|---|---|---|---|"
saymf "| A | ${PREREG_WARM_A} | ${PREREG_NACC} | ${PREREG_SMOKE_A} | the existing smoke split (n_warm 446, n_acc 1339); its complete record is already on disk |"
saymf "| B | ${PREREG_WARM_B} | ${PREREG_NACC} | ${PREREG_SMOKE_B} | the first genuinely longer warm-up |"
saymf "| C | ${PREREG_WARM_C} | ${PREREG_NACC} | ${PREREG_SMOKE_C} | the longest warm-up this scan pre-registers |"
saymf ""
saymf "**The three pre-registered readings, and what each one licenses.**"
saymf ""
saymf "1. **Monotone -- the worst-station deviation decreases as \`n_warm\` rises.** Settling confirmed: the smoke design moves to \`n_warm ~ ${PREREG_WARM_C}\`, and the production run is re-scoped against that split. This is the ONLY reading that licenses production."
saymf "2. **Flat -- the deviation does not move across the three points.** An instrument defect that the code reading missed: STOP AND REPORT, and production is NOT run."
saymf "3. **Non-monotone -- the deviation moves both ways (up then down, or down then up).** State the shape, add no fourth point, STOP FOR A RULING."
saymf ""
saymf "**Stopping rule.** Three points, then stop: no fourth warm-up value is added after the fact, no curve is fitted through the three deviations, and none of these three outcomes is reinterpreted once the numbers are in."
saymf ""
saymf "**These outcomes were committed before any of the three records existed.**"
saymf ""
saymf "**The honest limitation of three points.** Three points establish the direction of a trend, not rigorous monotonicity: they cannot separate a smooth decay from a step that falls between the sampled warm-ups, and they carry no error bar. A flat result is evidence about THIS instrument and THESE stations, not a proof about the method."
saymf ""
saymf "**Reproduction -- one command per point, one record file per point.** Each point writes its own record at a flat path in this run directory, so no point can overwrite another's record and no point meets the exit-15 clobber refusal; no \`--force\` is needed anywhere. Point A's complete record already exists at the default \`${RUN_DIR}/plane_record.npz\`, so point A is re-read with \`--reuse-record\` and is not re-solved:"
saymf ""
saymf '```'
saymf "cd ${ROOT}"
saymf ""
saymf "# A -- n_warm 446, n_acc ${PREREG_NACC}: re-read the record already on disk, no solve"
saymf "POY_WARM=${PREREG_WARM_A} POY_NACC=${PREREG_NACC} \\"
saymf "  bash .scratch/host/m3a-smoke/run.sh --reuse-record"
saymf ""
saymf "# B -- n_warm ${PREREG_WARM_B}, n_acc ${PREREG_NACC}: full solve into its own record"
saymf "POY_WARM=${PREREG_WARM_B} POY_NACC=${PREREG_NACC} \\"
saymf "  EMFIT_BIN_DUMP=${RUN_DIR}/plane_record_warm${PREREG_WARM_B}_nacc${PREREG_NACC}.npz \\"
saymf "  bash .scratch/host/m3a-smoke/run.sh"
saymf ""
saymf "# C -- n_warm ${PREREG_WARM_C}, n_acc ${PREREG_NACC}: full solve into its own record"
saymf "POY_WARM=${PREREG_WARM_C} POY_NACC=${PREREG_NACC} \\"
saymf "  EMFIT_BIN_DUMP=${RUN_DIR}/plane_record_warm${PREREG_WARM_C}_nacc${PREREG_NACC}.npz \\"
saymf "  bash .scratch/host/m3a-smoke/run.sh"
saymf '```'

# =====================================================================
if [ "${REUSE}" -eq 1 ]; then
    REC_MTIME="$(stat -c %y "${PLANE_NPZ}" 2>/dev/null || echo unknown)"
    REC_BYTES="$(stat -c %s "${PLANE_NPZ}" 2>/dev/null || echo unknown)"
    mark "SOLVE"
    saymf ""
    saymf "## Solve -- SKIPPED (\`--reuse-record\`)"
    saymf ""
    saymf "solve SKIPPED, record REUSED, mtime ${REC_MTIME} , ${REC_BYTES} bytes"
    saymf ""
    saymf "No solve was launched and no FDTD step was run: \`--reuse-record\` was given and"
    saymf "the record on disk is complete, so ARTEFACTS, ANALYSIS and VERDICT run against"
    saymf "that record exactly as it stands.  No solve exit code exists for this run --"
    saymf "\`SOLVE_RAN=${SOLVE_RAN}\`, \`SOLVE_RC=${SOLVE_RC}\` -- and none is invented."
    echo "solve     SKIPPED (--reuse-record); record REUSED, mtime ${REC_MTIME}, ${REC_BYTES} bytes"
else
mark "SOLVE"
saymf ""
saymf "## Invocation"
saymf ""
saymf "Exact command (stdout+stderr through \`tee\`):"
saymf ""
saymf '```'
saymf "cd ${ROOT}"
saymf "POY_SMOKE=${POY_SMOKE} POY_WARM=${POY_WARM} POY_NACC=${POY_NACC} \\"
saymf "EMFIT_BIN_DUMP=${PLANE_NPZ} EMFIT_PLANE_CAPTURE=${EMFIT_PLANE_CAPTURE} \\"
saymf "PYTHONUNBUFFERED=1 \\"
saymf "  ${PY} -u ${RUNNER} ${TONE_GHZ} 2>&1 | tee ${SOLVE_OUT}"
saymf '```'
saymf ""
saymf "\`${TONE_GHZ}\` is the runner's own argument, not an invented one: \`board_run_cw_poynting.py\`"
saymf "opens with \`def main(argv: list[str]) -> int\` (:260), refuses anything but "
saymf "\`len(argv) in (2, 3)\` with the usage \`<frequency in GHz> [dt_scale]\` (:261-265), and"
saymf "then does \`f_ghz = float(argv[1])\` (:265) and \`f_target = f_ghz * 1e9\` (:267). So"
saymf "\`${TONE_GHZ}\` is passed as the runner's own argument -- no shim, no runpy, no"
saymf "monkeypatch, no injected \`sys.argv\`."
saymf ""
saymf "\`plane_capture\` needs no in-process injection: \`emfit.studies.microstrip_wave_board\`"
saymf "defaults it to \`None\` and resolves that from \`EMFIT_PLANE_CAPTURE\`, so setting the"
saymf "variable above is the whole mechanism -- and the record's \`plane_capture\` key must read"
saymf "back \`\"env\"\`, which is what the ARTEFACTS block asserts. Nothing in emfit/ is patched."
echo "the runner prints a PROGRESS line every 500 steps or 30 s of wall, through tee"

POY_SMOKE="${POY_SMOKE}" POY_WARM="${POY_WARM}" POY_NACC="${POY_NACC}" \
    EMFIT_BIN_DUMP="${PLANE_NPZ}" EMFIT_PLANE_CAPTURE="${EMFIT_PLANE_CAPTURE}" \
    PYTHONUNBUFFERED=1 \
    "${PY}" -u "${RUNNER}" "${TONE_GHZ}" 2>&1 | tee "${SOLVE_OUT}"
PST=("${PIPESTATUS[@]}")
SOLVE_RC="${PST[0]}"
SOLVE_RAN=1     # written together with SOLVE_RC above: these two lines are the only place a solve status comes into existence
TEE_RC="${PST[1]:-0}"
note "python -u runner ${TONE_GHZ} GHz" "${SOLVE_RC}"
note "tee solve.out" "${TEE_RC}"
echo ""
echo "solve     exit=${SOLVE_RC}  tee exit=${TEE_RC}  solve.out $(wc -l < "${SOLVE_OUT}") lines"
if [ "${SOLVE_RC}" -ne 0 ]; then
    case "${SOLVE_RC}" in
        137) SOLVE_WHY="killed (137: OOM or SIGKILL)" ;;
        143) SOLVE_WHY="killed (143: SIGTERM)" ;;
        *)   SOLVE_WHY="non-zero exit (${SOLVE_RC})" ;;
    esac
    echo "FAIL(solve): ${SOLVE_WHY}"
    mf ""
    mf "**FAIL(solve)**: the solve did not return a record -- ${SOLVE_WHY}."
else
    SOLVE_WHY=""
    mf ""
    mf "The solve returned 0; \`solve.out\` holds $(wc -l < "${SOLVE_OUT}") lines."
fi
fi   # end of the --reuse-record guard: from here on ARTEFACTS/ANALYSIS/VERDICT are common to both paths

# =====================================================================
mark "ARTEFACTS"
saymf ""
saymf "## Artefacts"
saymf ""
if [ ! -s "${PLANE_NPZ}" ]; then
    echo "FAIL(artefacts): no plane record at ${PLANE_NPZ} (the solve wrote nothing)"
    ART_RC=17
    note "plane record present" "1"
    mf "**FAIL(artefacts)**: no plane record at \`${PLANE_NPZ}\`."
else
    "${PY}" -u - "${PLANE_NPZ}" <<'PY' | tee "${ART_TXT}"
import sys

import numpy as np

path = sys.argv[1]
BLOCKS = ("plane_Ey", "plane_Ez", "plane_Hy", "plane_Hz")
SCALARS = ("plane_station_cells", "plane_station_x", "plane_f", "plane_dt",
           "plane_n_samples", "plane_convention")
# 12 keys: 4 plane blocks + 6 plane scalars + the provenance key + the
# time-domain station mean that the plane phasors are compared against.
REQUIRED = BLOCKS + SCALARS + ("plane_capture", "sx_station")

try:
    z = np.load(path)
except Exception as exc:                                          # noqa: BLE001
    print("FAIL(artefacts): cannot open %s: %r" % (path, exc))
    raise SystemExit(1)

print("plane record  %s" % path)
print("keys (%d)     %s" % (len(z.files), ", ".join(sorted(z.files))))
missing = [k for k in REQUIRED if k not in z.files]
for key in REQUIRED:
    if key in z.files:
        arr = z[key]
        print("  %-20s shape=%-18s dtype=%s  bytes=%d"
              % (key, str(arr.shape), arr.dtype, arr.nbytes))
if missing:
    print("MISSING(%d)    %s" % (len(missing), ", ".join(missing)))
    print("FAIL(artefacts): the plane record does not carry every key")
    raise SystemExit(1)

checks = []


def check(name, cond, detail):
    checks.append(bool(cond))
    print("  %-4s %-42s %s" % ("ok" if cond else "FAIL", name, detail))


shape = {k: z[k].shape for k in BLOCKS}
nd3 = all(len(shape[k]) == 3 for k in BLOCKS)
check("four blocks are (n_stations, a, b)", nd3, str(shape))
n = int(z["plane_station_x"].size)
same_n = all(shape[k][0] == n for k in BLOCKS)
check("blocks agree on the station axis", same_n, "n_stations=%d" % n)
check("plane_Hz sits on plane_Ey", shape["plane_Hz"][1:] == shape["plane_Ey"][1:],
      "%s vs %s" % (shape["plane_Hz"][1:], shape["plane_Ey"][1:]))
check("plane_Hy sits on plane_Ez", shape["plane_Hy"][1:] == shape["plane_Ez"][1:],
      "%s vs %s" % (shape["plane_Hy"][1:], shape["plane_Ez"][1:]))
cplx = all(z[k].dtype.kind == "c" for k in BLOCKS)
check("four blocks are complex", cplx, str({k: str(z[k].dtype) for k in BLOCKS}))
cells = z["plane_station_cells"]
check("plane_station_cells is int, (n,)", cells.shape == (n,)
      and cells.dtype.kind in "iu", "shape=%s dtype=%s" % (cells.shape, cells.dtype))
x = np.asarray(z["plane_station_x"], dtype=float)
check("plane_station_x is float, (n,), increasing",
      x.shape == (n,) and bool(np.all(np.diff(x) > 0.0)),
      "%.4f .. %.4f mm" % (1e3 * x[0], 1e3 * x[-1]) if n else "empty")
f = float(z["plane_f"])
dt = float(z["plane_dt"])
ns = int(z["plane_n_samples"])
check("plane_f, plane_dt, plane_n_samples positive",
      f > 0.0 and dt > 0.0 and ns > 0,
      "f=%.6f GHz dt=%.6e s n_samples=%d" % (f / 1e9, dt, ns))
conv = z["plane_convention"]
check("plane_convention is a non-empty string",
      conv.dtype.kind == "U" and str(conv).strip() != "", "%d chars" % len(str(conv)))
cap = str(z["plane_capture"])
check("plane_capture reads 'env' (EMFIT_PLANE_CAPTURE)",
      cap.strip() == "env", "%r" % (cap,))
sx = np.asarray(z["sx_station"], dtype=float).ravel()
check("sx_station is (n,), finite, no zeros",
      sx.shape == (n,) and bool(np.all(np.isfinite(sx))) and bool(np.all(sx != 0.0)),
      "min=%.6e max=%.6e" % (float(sx.min()), float(sx.max())) if sx.size else "empty")
total = sum(z[k].nbytes for k in BLOCKS)
print("  plane blocks %.2f MB" % (total / 1024.0 / 1024.0))
if not all(checks):
    print("FAIL(artefacts): %d of %d checks failed"
          % (len(checks) - sum(checks), len(checks)))
    # exit 2, not 1: the keys are all there, so the record must not be
    # reported as "missing a key" -- the caller's messages differ.
    raise SystemExit(2)
print("ARTEFACTS OK: %d keys, %d stations" % (len(REQUIRED), n))
PY
    ART_RC="${PIPESTATUS[0]}"
    note "artefacts: keys, shapes, dtypes" "${ART_RC}"

    # Three-way.  Either this run solved and left a solve.out to count, or it
    # reused a solve.out an earlier solve left (report that count, tagged with
    # its origin), or there is no solve.out at all -- then no progress evidence
    # exists to count, and the state is recorded as such rather than as 0.
    if [ "${REUSE}" -eq 1 ] && [ ! -f "${SOLVE_OUT}" ]; then
        PROG="n/a (reuse)"
        PROG_RC="n/a (reuse)"
    else
        # grep -c exits 1 when it matches nothing, and that status must not
        # become a failed capture; the empty-value guard covers the one other
        # way this can go wrong, so no numeric test below sees an empty string.
        PROG="$(grep -c '^PROGRESS' "${SOLVE_OUT}" 2>/dev/null || true)"
        if [ -z "${PROG}" ]; then
            PROG=0
        fi
        printf '%s\n' "${PROG}" > "${RUN_DIR}/.prog.rc"
        PROG_RC=0
    fi
    note "progress lines in solve.out" "${PROG_RC}"
    echo "" | tee -a "${ART_TXT}"
    if [ "${REUSE}" -eq 1 ] && [ ! -f "${SOLVE_OUT}" ]; then
        echo "PROGRESS lines in solve.out: n/a (reuse)  [no solve.out in this run directory -- this run solved nothing and no earlier solve left one]" | tee -a "${ART_TXT}"
    elif [ "${REUSE}" -eq 1 ]; then
        # Provenance: this count is read from the solve.out an EARLIER run left
        # behind.  On a run that solved nothing it must never read as evidence
        # about this run, so the same number is printed with its origin attached.
        echo "PROGRESS lines in solve.out: ${PROG}  [reused solve.out from the earlier solve -- this run solved nothing]" | tee -a "${ART_TXT}"
    else
        echo "PROGRESS lines in solve.out: ${PROG}  (runner: one per 500 steps or 30 s of wall)" | tee -a "${ART_TXT}"
    fi
    # Numeric only where this run solved: under --reuse-record PROG holds the
    # reused count or the literal "n/a (reuse)", and the check is not
    # applicable to this run either way -- it must not be reported as passed.
    if [ "${REUSE}" -eq 0 ] && [ "${PROG}" -lt 1 ]; then
        echo "FAIL(artefacts): solve.out holds no PROGRESS line -- progress was not reported" | tee -a "${ART_TXT}"
        [ "${ART_RC}" -eq 0 ] && ART_RC=17
    fi
    { echo ""; echo '```'; cat "${ART_TXT}"; echo '```'; } >> "${MANIFEST}"
    if [ "${REUSE}" -eq 1 ]; then
        mf ""
        mf "The \`PROGRESS\` count above belongs to the \`solve.out\` the earlier solve left on disk, not to this run: \`--reuse-record\` launched no solve, so this run produced no PROGRESS line of its own and the count is a property of that reused artefact."
        mf ""
        mf "The check that count feeds is therefore not applicable to a reuse point rather than passed: a reuse point carries no progress evidence of its own, and where no \`solve.out\` is present at all the count is recorded as \`n/a (reuse)\` instead of a number."
    fi
    if [ "${ART_RC}" -ne 0 ]; then
        echo "FAIL(artefacts): the plane record is incomplete (see above)"
        mf ""
        mf "**FAIL(artefacts)**: the record failed the key, shape, dtype or \`plane_capture\` checks above."
    fi
fi
rm -f "${RUN_DIR}/.prog.rc"

# =====================================================================
ANA_RC=99
mark "ANALYSIS"
saymf ""
saymf "## Analysis (plane phasors vs time-domain station mean)"
saymf ""
if [ "${ART_RC}" -ne 0 ]; then
    echo "SKIPPED(analysis): the plane record is not usable"
    mf "Skipped: the plane record is not usable, so there is nothing to compare."
else
    "${PY}" -u - "${ROOT}" "${PLANE_NPZ}" "${ANA_JSON}" \
        "${POY_SMOKE}" "${N_WARM}" "${N_ACC}" "${warm_source}" "${n_acc_source}" \
        <<'PY' | tee "${ANA_TXT}"
import json
import sys

import numpy as np

root, path, json_out = sys.argv[1], sys.argv[2], sys.argv[3]
# The heredoc is quoted ('PY'), so the resolved warm-up split arrives as argv
# and is never re-expanded by the shell.  These are the numbers the run *asked
# for*; the record is cross-checked against them below, never the reverse.
smoke_asked = sys.argv[4]
warm_asked = sys.argv[5]
nacc_asked = sys.argv[6]
warm_source = sys.argv[7]
n_acc_source = sys.argv[8]
sys.path.insert(0, root)

from emfit.plane_phasor import (compare_with_time_domain,   # noqa: E402
                                flux_from_phasors)

z = np.load(path)
ey, ez = z["plane_Ey"], z["plane_Ez"]
hy, hz = z["plane_Hy"], z["plane_Hz"]
sx = np.asarray(z["sx_station"], dtype=float).ravel()
x = np.asarray(z["plane_station_x"], dtype=float).ravel()
# N is the accumulated *sample* count the phasors were summed over; the
# station count is a different number and must never be used as N (or as a
# loop bound over stations).
n = int(z["plane_n_samples"])
nst = int(x.size)
f = float(z["plane_f"])
dt = float(z["plane_dt"])

# ---- record identity: the record's OWN sample count vs N_ACC -------------
# The phasor accumulation covers only the accepted (post-warm-up) steps, so
# plane_n_samples must equal N_ACC -- not POY_SMOKE, which still contains the
# discarded warm-up.  Printed before anything below can raise, so a mismatch
# can never be silent.
print("---- record identity ----")
print("asked       POY_SMOKE=%s  n_warm=%s [%s]  n_acc=%s [%s]"
      % (smoke_asked, warm_asked, warm_source, nacc_asked, n_acc_source))
print("record      plane_n_samples N=%d  (read back from the record)" % n)
try:
    nacc_n = int(str(nacc_asked).strip())
except (TypeError, ValueError):
    nacc_n = None
try:
    smoke_n = int(str(smoke_asked).strip())
except (TypeError, ValueError):
    smoke_n = None
if nacc_n is None:
    print("!!!!! N CROSS-CHECK IMPOSSIBLE: N_ACC=%r is not an integer, so the"
          % (nacc_asked,))
    print("!!!!! record cannot be tied to the warm-up split. Do not read anything")
    print("!!!!! below as a warm-up-split result.")
elif n == nacc_n:
    print("check       record N == N_ACC == %d  (plane_n_samples == n_acc): the"
          % n)
    print("check       record holds only the accumulated part -- the warm-up steps")
    print("check       are discarded and leave no trace in the record, which is what")
    print("check       the split is supposed to do.")
    if warm_source == "default-fraction":
        print("check       caveat: this equality cannot tell the default route from")
        print("check       the shim route. With warm_source=default-fraction the asked")
        print("check       n_warm is nsteps//4 anyway, so a warm-up override that")
        print("check       never took effect would land on N_ACC=%d as well." % n)
else:
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!!!!! RECORD N != N_ACC -- THE WARM-UP SPLIT IS NOT CONFIRMED !!!!!")
    print("!!!!! record plane_n_samples = %d" % n)
    print("!!!!! asked N_ACC            = %d  (POY_SMOKE=%s, n_warm=%s [%s]) [%s]"
          % (nacc_n, smoke_asked, warm_asked, warm_source, n_acc_source))
    print("!!!!! difference             = %+d steps" % (n - nacc_n))
    print("!!!!! Expected failure mode: warm_shim silently not installed, so")
    print("!!!!! microstrip_wave_board calls microstrip_wave with no n_warm and")
    print("!!!!! microstrip_wave falls back to n_warm = nsteps//4 (emfit/studies.py:2590):")
    print("!!!!! the requested warm-up is silently replaced by a quarter of the record.")
    if smoke_n is not None:
        fb_n = smoke_n // 4
        print("!!!!! Under that fallback, the requested record length nsteps=%d"
              % smoke_n)
        print("!!!!! gives n_acc = %d - %d = %d instead of the asked %d."
              % (smoke_n, fb_n, smoke_n - fb_n, nacc_n))
        print("!!!!! The pair to recognise at a glance is therefore %d (what the"
              % (smoke_n - fb_n))
        print("!!!!! split asks for) vs a record holding a different number such as %d."
              % n)
    print("!!!!! Conversely, if this record's %d samples came out of that fallback,"
          % n)
    print("!!!!! its nsteps was about %d (the record is the last three quarters of"
          % int(round(n * 4.0 / 3.0)))
    print("!!!!! it), i.e. a quarter of the record was burned as warm-up rather than")
    print("!!!!! the requested %s steps." % (warm_asked,))
    print("!!!!! No result below may be read as a warm-up-split result until this")
    print("!!!!! difference is explained.")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
print("")

# ---- D4 caveat: printed unconditionally, before any number is emitted ----
print("---- D4 CAVEAT -- what this file does NOT measure ----")
print("(1) The half-step phase term IS printed below (-pi f dt and its cos), but it")
print("    is never gated: it is a diagnostic, not a pass/fail test.")
print("(2) What is absent is any linearity or curvature statistic, any")
print("    second-difference statistic, and any settledness test. The")
print("    phase-linearity that the M3a smoke design assumes is NOT MEASURED HERE")
print("    AT ALL: the gate below tests only the per-station amplitude scale")
print("    4*flux/(N**2*sx), not the phase and not its curvature.")
print("(3) The n_warm warm-up scan is an UNDER-POWERED test of settledness and is")
print("    recorded as NAMED DEBT, not as evidence that the record is settled.")
print("(4) Do NOT read any settledness (or phase-linearity) conclusion out of this")
print("    file. The only conclusions here are the 'gate' and 'ok' lines below, and")
print("    they speak about amplitude scale alone.")
print("")

flux = flux_from_phasors(ey, ez, hy, hz)
if flux.size != nst or sx.size != nst:
    raise SystemExit("FAIL(analysis): %d stations from the blocks, %d from the "
                     "arrays (%d sx) -- they must agree"
                     % (flux.size, nst, sx.size))
res = compare_with_time_domain(flux, sx, n_samples=n, f=f, dt=dt, tolerance=0.01)
scale = np.asarray(res["scale_measured"], dtype=float)
dev = np.asarray(res["deviation_pc"], dtype=float)
ratio = np.asarray(res["ratio"], dtype=float)
phys = 4.0 * flux / float(n * n)

print("plane_phasor.flux_from_phasors: raw flux = 0.5 Re(sum conj(E) H), no 4/N**2")
print("tone        f=%.6f GHz  dt=%.6e s  n_samples N=%d" % (f / 1e9, dt, n))
print("closed form scale_derived = N**2/4 = %.6e" % res["scale_derived"])
print("half step   -pi f dt = %+.6e rad, cos = %.12f  (in both routes, never gated)"
      % (res["half_step_rad"], res["cos_factor"]))
print("gate        |deviation| < 1.00 pc at every station (tolerance 0.01)")
print("")
print("  stn      x[mm]        sx[W]     flux_raw        flux[W]    scale_meas"
      "      dev[pc]   ratio")
for i in range(nst):
    print("  %3d %10.4f %+12.5e %+12.5e %+12.5e %+12.5e %11.6f %8.6f"
          % (i, 1e3 * x[i], sx[i], flux[i], phys[i], scale[i], dev[i], ratio[i]))
print("")
worst = int(np.argmax(dev))
print("worst       station %d: %.6f pc   max deviation %.6f pc"
      % (worst, dev[worst], float(dev.max())))
print("ratio       4 flux / (N**2 sx): min %.9f max %.9f  (1.0 = agreement)"
      % (float(ratio.min()), float(ratio.max())))
print("ok          %s" % ("yes" if res["ok"] else "no"))
payload = {
    "plane_capture": str(z["plane_capture"]),
    "n_stations": int(nst),
    "n_samples": int(n),
    "f_hz": f,
    "dt_s": dt,
    "scale_derived": float(res["scale_derived"]),
    "scale_measured": [float(v) for v in scale],
    "flux_raw": [float(v) for v in flux],
    "flux_w": [float(v) for v in phys],
    "sx_station": [float(v) for v in sx],
    "station_x_m": [float(v) for v in x],
    "deviation_pc": [float(v) for v in dev],
    "ratio": [float(v) for v in ratio],
    "max_deviation_pc": float(dev.max()),
    "worst_station": worst,
    "half_step_rad": float(res["half_step_rad"]),
    "cos_factor": float(res["cos_factor"]),
    "ok": bool(res["ok"]),
}
with open(json_out, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
print("json        %s" % json_out)
PY
    ANA_RC="${PIPESTATUS[0]}"
    note "analysis: plane phasor comparison" "${ANA_RC}"
    { echo ""; echo '```'; cat "${ANA_TXT}"; echo '```'; } >> "${MANIFEST}"
    if [ "${ANA_RC}" -ne 0 ]; then
        echo "FAIL(analysis): the comparison raised or returned non-zero"
        mf ""
        mf "**FAIL(analysis)**: the comparison did not produce numbers."
    fi
fi

# =====================================================================
mark "VERDICT"
"${PY}" -u - "${SOLVE_RAN}" "${SOLVE_RC}" "${ART_RC}" "${ANA_RC}" "${ANA_JSON}" \
    "${VERDICT_TXT}" <<'PY' | tee -a "${VERDICT_TXT}" > "${RUN_DIR}/.verdict.out"
import json
import os
import sys

# argv[2] is a solve *exit code* only when argv[1] says the solve ran.  When
# --reuse-record skipped it, the caller passes the string sentinel NOT_RUN and
# the code here is None, so "the solve failed" and "the solve never ran" can
# never be conflated -- which is exactly what the old single 99 sentinel did.
solve_ran = int(sys.argv[1])
solve_rc_raw = sys.argv[2]
art_rc, ana_rc = int(sys.argv[3]), int(sys.argv[4])
json_path, out_path = sys.argv[5], sys.argv[6]
solve_rc = int(solve_rc_raw) if solve_ran else None

data = None
if ana_rc == 0 and os.path.exists(json_path):
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

lines = []


def emit(text=""):
    lines.append(text)
    print(text)


emit("Branches evaluated, in order of precedence:")
if not solve_ran:
    emit("  [a] solve launched ................................. NO, skipped"
         " (--reuse-record reused the record on disk; no solve status was"
         " measured)")
elif solve_rc == 0:
    emit("  [a] solve returned a record ........................ yes (exit 0)")
else:
    why = {137: "137 = OOM/SIGKILL", 143: "143 = SIGTERM"}.get(
        solve_rc, "non-zero")
    emit("  [a] solve returned a record ........................ NO (exit %d, %s)"
         % (solve_rc, why))
if art_rc == 0:
    emit("  [b] plane record carries all 12 keys ............... yes"
         " (4 blocks + 6 scalars + plane_capture + sx_station)")
elif art_rc == 1:
    emit("  [b] plane record carries all 12 keys ............... NO (a key is"
         " missing: a plane_* block, a plane_* scalar, plane_capture or sx_station)")
elif art_rc == 99:
    emit("  [b] plane record carries all 12 keys ............... not reached")
else:
    emit("  [b] plane record carries all 12 keys ............... NO (checks failed,"
         " exit %d)" % art_rc)

verdict = "PASS"
reason = ""

# Three solve cases, never merged: ran and failed (a measured code), did not run
# (no code was ever measured, so none is claimed), ran and succeeded.  The first
# blocking failure wins, in the original order (solve, artefacts, analysis); an
# empty ``blocking`` means the ratio/deviation gates below decide.  The ratio
# block is untouched -- thresholds, table and wording included.
blocking = ""
if solve_ran and solve_rc != 0:
    why = {137: "OOM-killed (137)", 143: "killed by SIGTERM (143)"}.get(
        solve_rc, "non-zero exit %d" % solve_rc)
    if art_rc == 0:
        blocking = ("solve: %s -- the solve did not finish, but a complete record "
                    "is present on disk from an earlier run and it passed the "
                    "artefacts checks; this run applies no gate to it" % why)
    else:
        blocking = "solve: %s -- there is no record to check" % why
elif art_rc != 0:
    if art_rc == 1:
        blocking = ("artefacts: the plane record does not carry every key "
                    "(the missing-key branch)")
    else:
        blocking = ("artefacts: the record carries every key but a check failed "
                    "(exit %d) -- shape, dtype, plane_capture or sx_station; "
                    "see artefacts.txt" % art_rc)
elif ana_rc != 0 or data is None:
    blocking = "analysis: the plane-phasor comparison did not run to numbers"

if not solve_ran and blocking:
    blocking = "solve not run (--reuse-record); " + blocking

if blocking:
    verdict = "FAIL"
    reason = blocking
else:
    cap = str(data.get("plane_capture", "<absent>"))
    n = int(data["n_samples"])
    ratios = [float(r) for r in data["ratio"]]
    devs = [float(d) for d in data["deviation_pc"]]
    nst = int(data["n_stations"])
    worst = int(data["worst_station"])
    maxdev = float(data["max_deviation_pc"])

    def near(value, target):
        return abs(value - target) <= 1e-3 * abs(target)

    off2 = [r for r in ratios if near(r, 2.0) or near(r, 0.5)]
    offn = [r for r in ratios
            if near(r, float(n)) or near(r, 1.0 / float(n))]
    emit("  [b2] plane_capture reads 'env' ................... %s"
         % ("yes" if cap == "env" else "NO (%r)" % (cap,)))
    if maxdev < 1.0:
        emit("  [c] every station within 1 pc ...................... yes"
             " (max %.6f pc)" % maxdev)
    else:
        emit("  [c] every station within 1 pc ...................... NO"
             " (max %.6f pc at station %d)" % (maxdev, worst))
    emit("  [d] scale ratio off by exactly 2 ................... %s"
         % ("YES (ratio %.6f)" % off2[0] if off2 else
            "no (ratio %.9f .. %.9f)" % (min(ratios), max(ratios))))
    emit("  [e] scale ratio off by exactly N=%d ............... %s"
         % (n, "YES (ratio %.6f)" % offn[0] if offn else
            "no (ratio %.9f .. %.9f)" % (min(ratios), max(ratios))))

    if cap != "env":
        verdict = "FAIL"
        reason = ("artefacts: the plane record says plane_capture=%r, not 'env' "
                  "-- the capture did not come from EMFIT_PLANE_CAPTURE, so this "
                  "record is not the one this run asked for" % (cap,))
    elif off2:
        verdict = "FAIL"
        reason = ("scale: the ratio is off by exactly 2 (4*flux/(N**2*sx) = "
                  "%.6f, not 1) -- one route carries a factor of 2 the other "
                  "does not: a wrong derivation, not a physics result"
                  % off2[0])
    elif offn:
        verdict = "FAIL"
        reason = ("scale: the ratio is off by exactly N=%d (4*flux/(N**2*sx) = "
                  "%.6f) -- one route summed N samples where the other "
                  "averaged N: a wrong derivation, not a physics result"
                  % (n, offn[0]))
    elif maxdev >= 1.0:
        verdict = "FAIL"
        reason = ("magnitude: %d of %d stations outside the 1 pc gate "
                  "(worst station %d at %.6f pc)"
                  % (sum(1 for d in devs if d >= 1.0), nst, worst, maxdev))
    else:
        reason = ("every one of %d stations within 1 pc of the closed-form "
                  "scale (max %.6f pc); 4*flux/(N**2*sx) = %.9f .. %.9f"
                  % (nst, maxdev, min(ratios), max(ratios)))

emit("")
print("VERDICT: %s -- %s" % (verdict, reason))
with open(out_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines + ["", "VERDICT: %s -- %s" % (verdict, reason)])
             + "\n")
sys.exit(0 if verdict == "PASS" else 19)
PY
VERDICT_RC=$?
note "verdict: 1 pc per-station gate" "${VERDICT_RC}"

if [ -s "${VERDICT_TXT}" ]; then
    { echo ""; cat "${VERDICT_TXT}"; } >> "${MANIFEST}"
fi
tail -1 "${VERDICT_TXT}" | sed 's/^/>> /'
rm -f "${RUN_DIR}/.verdict.out"

if [ "${SOLVE_RAN}" -eq 1 ] && [ "${SOLVE_RC}" -ne 0 ]; then
    FINAL=16
elif [ "${ART_RC}" -ne 0 ]; then
    FINAL=17
elif [ "${ANA_RC}" -ne 0 ]; then
    FINAL=18
elif [ "${VERDICT_RC}" -ne 0 ]; then
    FINAL=19
else
    FINAL=0
fi
echo ""
echo "manifest  ${MANIFEST}"
exit "${FINAL}"
