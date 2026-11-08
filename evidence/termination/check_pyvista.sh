#!/bin/sh
# check_pyvista.sh -- diagnostic for the pyvista/vtk stack behind
# evidence/termination/render_fields.py.
#
# WHY THIS EXISTS
#   render_fields.py needs numpy + vtk + pyvista.  When it fails, the message
#   ("No module named 'vtk'", a missing libGL.so.1 raised at import time, or a
#   pip that belongs to a DIFFERENT interpreter than the one that runs the
#   script) points at three very different fixes, and guessing between them
#   wastes a round trip.  This script asks one interpreter -- python3 as
#   resolved on PATH -- the six questions that separate those cases, and then
#   prints the fix for whichever case it actually found.
#
# CONTRACT (deliberate, do not "tidy" this away)
#   * pure diagnostic: reads only, writes no file, installs nothing, no
#     network.  The apt/pip lines at [6/6] are PRINTED, never executed.
#   * it NEVER aborts early and ALWAYS exits 0.  Every check is allowed to
#     fail; a failing check prints its own FAIL/SKIPPED line and the next
#     check still runs.  That is why `set -e` is deliberately absent (set -u
#     stays, so every variable is initialised below).
#   * POSIX sh only: no [[ ]], no arrays, no pipefail.
#
# Usage:  sh evidence/termination/check_pyvista.sh
#
set -u

# ---- helpers -------------------------------------------------------------
# kv <KEY> <blob> : value of the "KEY=value" line inside <blob>, or empty.
kv() {
    printf '%s\n' "${2:-}" | sed -n "s/^$1=//p" | head -n 1
}

# tag <tag> <label> <value> : one labelled output line; UNAVAILABLE if empty.
tag() {
    if [ -n "${3:-}" ]; then
        printf '%s\n' "$1 $2 = $3"
    else
        printf '%s\n' "$1 $2 = UNAVAILABLE"
    fi
}

# apt_for <soname> : the Debian/Ubuntu package providing exactly that soname,
# or empty.  Conservative on purpose: an unmapped soname must print as
# unmapped rather than be guessed at.
apt_for() {
    case "$1" in
        libGL.so.1)        printf '%s' libgl1 ;;
        libXrender.so.1)   printf '%s' libxrender1 ;;
        libXt.so.6)        printf '%s' libxt6 ;;
        libXext.so.6)      printf '%s' libxext6 ;;
        libSM.so.6)        printf '%s' libsm6 ;;
        libICE.so.6)       printf '%s' libice6 ;;
        libxkbcommon.so.0) printf '%s' libxkbcommon0 ;;
        libfontconfig.so.1) printf '%s' libfontconfig1 ;;
        libfreetype.so.6)  printf '%s' libfreetype6 ;;
        libglapi.so.0)     printf '%s' libglapi-mesa ;;
        libosmesa.so.6)    printf '%s' libosmesa6 ;;
        *)                 printf '%s' "" ;;
    esac
}

# probe <LABEL> <python source> : run one import probe in its own interpreter.
# stdout and stderr are captured with two runs of the same one-liner so that
# nothing here has to create a temp file (this script writes no files).
# Sets PROBE_OUT and PROBE_OK (1 = exit 0) for the caller.
probe() {
    _label=$1
    _code=$2
    PROBE_OK=0
    PROBE_OUT=""
    _st=0
    PROBE_OUT=$(python3 -c "$_code" 2>/dev/null) || _st=$?
    if [ "$_st" -eq 0 ]; then
        PROBE_OK=1
    fi
    printf '%s\n' "[3/6] $_label: stdout = ${PROBE_OUT:-<empty>}"
    printf '%s\n' "[3/6] $_label: exit status = $_st"
    if [ "$_st" -eq 0 ]; then
        printf '%s\n' "[3/6] $_label: stderr = <none>"
    else
        _err=""
        _err=$(python3 -c "$_code" 2>&1 >/dev/null) || true
        printf '%s\n' "[3/6] $_label: stderr (first 5 lines):"
        if [ -n "$_err" ]; then
            printf '%s\n' "$_err" | head -n 5 | sed 's/^/[3\/6]   | /'
        else
            printf '%s\n' "[3/6]   | <none>"
        fi
    fi
}

# ---- state shared between checks ----------------------------------------
IN_VENV=unknown
EXECUTABLE=""
NUMPY_OK=0
VTK_OK=0
PYVISTA_OK=0
VTKDIR=""
MISSING_SONAMES=""
APT_PKGS=""
APT_MAP=""

printf '%s\n' "==================================================="
printf '%s\n' " check_pyvista.sh -- pyvista / vtk diagnostic"
printf '%s\n' " date: $(date 2>/dev/null || printf '%s' 'date unavailable')"
printf '%s\n' " cwd : $(pwd 2>/dev/null || printf '%s' 'pwd unavailable')"
printf '%s\n' "==================================================="

# ---- [1/6] which python -------------------------------------------------
printf '\n%s\n' "[1/6] WHICH PYTHON"
_which=""
_which=$(command -v python3 2>/dev/null) || _which=""
if [ -n "$_which" ]; then
    tag "[1/6]" "which python3" "$_which"
else
    printf '%s\n' "[1/6] which python3 = NOT-FOUND (no python3 on PATH)"
fi

printf '%s\n' "[1/6] python3 -VV :"
python3 -VV 2>&1 | sed 's/^/[1\/6]   /' || true

_pyinfo=""
_pyinfo=$(python3 -c '
import platform, sys
print("EXECUTABLE=" + sys.executable)
print("VERSION=" + " ".join(sys.version.split()))
print("PREFIX=" + sys.prefix)
print("BASE_PREFIX=" + sys.base_prefix)
print("PLATFORM=" + platform.platform())
print("IN_VENV=" + str(sys.prefix != sys.base_prefix))
' 2>&1) || true

EXECUTABLE=$(kv EXECUTABLE "$_pyinfo")
IN_VENV=$(kv IN_VENV "$_pyinfo")
if [ -z "$IN_VENV" ]; then
    IN_VENV=unknown
fi

tag "[1/6]" "sys.executable" "$EXECUTABLE"
tag "[1/6]" "sys.version" "$(kv VERSION "$_pyinfo")"
tag "[1/6]" "sys.prefix" "$(kv PREFIX "$_pyinfo")"
tag "[1/6]" "sys.base_prefix" "$(kv BASE_PREFIX "$_pyinfo")"
tag "[1/6]" "platform.platform()" "$(kv PLATFORM "$_pyinfo")"
tag "[1/6]" "IN_VENV (sys.prefix != sys.base_prefix)" "$IN_VENV"

if [ -n "${VIRTUAL_ENV:-}" ]; then
    tag "[1/6]" "environment VIRTUAL_ENV" "$VIRTUAL_ENV"
else
    printf '%s\n' "[1/6] environment VIRTUAL_ENV = NOT-SET"
fi

if [ -z "$EXECUTABLE" ]; then
    printf '%s\n' "[1/6] the introspection one-liner did not produce EXECUTABLE; raw output (first 5 lines):"
    printf '%s\n' "$_pyinfo" | head -n 5 | sed 's/^/[1\/6]   | /'
fi

# ---- [2/6] repo-local virtualenvs ---------------------------------------
printf '\n%s\n' "[2/6] REPO-LOCAL VIRTUALENVS (paths relative to cwd above)"
for _p in .venv/bin/python venv/bin/python env/bin/python; do
    if [ -x "$_p" ]; then
        printf '%s\n' "[2/6] $_p = EXISTS (executable)"
    else
        printf '%s\n' "[2/6] $_p = ABSENT"
    fi
done

_venvs=""
_venvs=$(ls -d /home/*/PycharmProjects/EE/.venv 2>/dev/null) || _venvs=""
if [ -n "$_venvs" ]; then
    printf '%s\n' "$_venvs" | sed 's/^/[2\/6] found: /'
else
    printf '%s\n' "[2/6] /home/*/PycharmProjects/EE/.venv = ABSENT"
fi

# ---- [3/6] import control pair ------------------------------------------
printf '\n%s\n' "[3/6] IMPORT CONTROL PAIR (numpy / vtk / pyvista, one interpreter each)"

probe "A numpy  " 'import numpy; print(numpy.__version__)'
NUMPY_OK=$PROBE_OK

probe "B vtk    " 'import vtk; print(vtk.VTK_VERSION)'
VTK_OK=$PROBE_OK

probe "C pyvista" 'import pyvista; print(pyvista.__version__)'
PYVISTA_OK=$PROBE_OK

printf '%s\n' "[3/6] conclusion:"
if [ "$NUMPY_OK" -ne 1 ]; then
    printf '%s\n' "[3/6]   (i) THE INTERPRETER OR ITS PACKAGING IS BROKEN: numpy ALSO failed, so this is not a missing-package problem. Look at [1/6] sys.prefix vs sys.base_prefix, at [5/6] pip, and at the numpy traceback above before installing anything."
elif [ "$VTK_OK" -ne 1 ] || [ "$PYVISTA_OK" -ne 1 ]; then
    printf '%s\n' "[3/6]   (ii) THE PACKAGES ARE SIMPLY NOT INSTALLED: numpy imports fine, so the interpreter and its site-packages work; only vtk and/or pyvista are absent. This is the case [6/6] fixes with an install."
else
    printf '%s\n' "[3/6]   (iii) ALL THREE IMPORT FINE: numpy, vtk and pyvista all load in this interpreter, so a render_fields.py failure is NOT an import problem -- look inside the script itself (bad npz key, backend selection, display/xvfb)."
fi

# ---- [4/6] shared-library check -----------------------------------------
printf '\n%s\n' "[4/6] SHARED-LIBRARY CHECK (vtk only)"
if [ "$VTK_OK" -ne 1 ]; then
    printf '%s\n' "[4/6] SKIPPED: probe B (import vtk) failed, so there is no vtkmodules tree to inspect."
else
    VTKDIR=$(python3 -c 'import vtkmodules, os; print(os.path.dirname(vtkmodules.__file__))' 2>/dev/null) || VTKDIR=""
    if [ -n "$VTKDIR" ]; then
        tag "[4/6]" "vtkmodules package dir" "$VTKDIR"
    else
        printf '%s\n' "[4/6] vtkmodules package dir = UNAVAILABLE"
    fi

    _so=""
    if [ -n "$VTKDIR" ]; then
        _so=$(ls -1 "$VTKDIR"/libvtkCommonCore*.so* 2>/dev/null | head -n 1) || _so=""
        if [ -z "$_so" ]; then
            _so=$(find "$VTKDIR" -name 'libvtkCommonCore*.so*' 2>/dev/null | head -n 1) || _so=""
        fi
    fi

    if [ -z "$_so" ]; then
        printf '%s\n' "[4/6] NO-SO-FOUND: no libvtkCommonCore*.so* in that directory or below it."
        _sos=""
        if [ -n "$VTKDIR" ]; then
            _sos=$(find "$VTKDIR" -name '*.so*' 2>/dev/null | head -n 20) || _sos=""
        fi
        if [ -n "$_sos" ]; then
            printf '%s\n' "[4/6] .so files that ARE there (first 20):"
            printf '%s\n' "$_sos" | sed 's/^/[4\/6]   /'
        else
            printf '%s\n' "[4/6] .so files that ARE there: none"
        fi
    else
        tag "[4/6]" "shared object" "$_so"
        if command -v ldd >/dev/null 2>&1; then
            _ldd=""
            _ldd=$(ldd "$_so" 2>&1) || true
            _miss=""
            _miss=$(printf '%s\n' "$_ldd" | grep 'not found' || true)
            if [ -n "$_miss" ]; then
                printf '%s\n' "[4/6] FAIL: ldd reports missing shared libraries:"
                printf '%s\n' "$_miss" | sed 's/^/[4\/6]   /'
                MISSING_SONAMES=$(printf '%s\n' "$_miss" | awk '{print $1}' | sort -u)
            else
                printf '%s\n' "[4/6] NO-MISSING-SONAMES: ldd resolved every dependency of that object."
                printf '%s\n' "$_ldd" | grep -E 'not a dynamic executable|statically linked' | sed 's/^/[4\/6] note: /' || true
            fi
        else
            printf '%s\n' "[4/6] LDD-NOT-AVAILABLE: ldd is not on PATH, cannot inspect $_so"
        fi
    fi
fi

# Soname -> Debian package mapping, built here so [6/6] only prints it.
if [ -n "$MISSING_SONAMES" ]; then
    for _sn in $MISSING_SONAMES; do
        _pkg=$(apt_for "$_sn")
        if [ -n "$_pkg" ]; then
            APT_MAP="$APT_MAP    $_sn -> $_pkg
"
            APT_PKGS="$APT_PKGS $_pkg"
        else
            APT_MAP="$APT_MAP    $_sn -> (no mapping known)
"
        fi
    done
    APT_PKGS=$(printf '%s\n' $APT_PKGS | sort -u | tr '\n' ' ')
fi

# ---- [5/6] pip posture ---------------------------------------------------
printf '\n%s\n' "[5/6] PIP POSTURE"
printf '%s\n' "[5/6] python3 -m pip --version :"
python3 -m pip --version 2>&1 | sed 's/^/[5\/6]   /' || true

printf '%s\n' "[5/6] python3 -m pip list | grep -iE 'vtk|pyvista|trame|numpy|meshio|imageio' :"
_plist=""
_plist=$(python3 -m pip list 2>/dev/null | grep -iE 'vtk|pyvista|trame|numpy|meshio|imageio') || _plist=""
if [ -n "$_plist" ]; then
    printf '%s\n' "$_plist" | sed 's/^/[5\/6]   /'
else
    printf '%s\n' "[5/6]   <none of those packages listed> -- the expected output on a bare install, not an error."
fi

# ---- [6/6] suggested fix -------------------------------------------------
printf '\n%s\n' "[6/6] SUGGESTED FIX (driven only by what [1]-[5] found)"
if [ "$IN_VENV" = "true" ] && [ -n "$EXECUTABLE" ]; then
    printf '%s\n' "[6/6] IN_VENV is true, so install into that exact interpreter:"
    printf '%s\n' "$EXECUTABLE -m pip install pyvista trame"
    printf '%s\n' "[6/6] and run render_fields.py with that SAME interpreter, e.g.:"
    printf '%s\n' "$EXECUTABLE evidence/termination/render_fields.py"
else
    printf '%s\n' "[6/6] IN_VENV is $IN_VENV, so there is no venv interpreter to install into; the fix targets the user site:"
    printf '%s\n' "python3 -m pip install --user pyvista trame"
    printf '%s\n' "[6/6] note: pip may refuse --user in some environments (PEP 668 externally-managed, or a read-only site-packages); if it does, use a venv instead:"
    printf '%s\n' "python3 -m venv .venv && .venv/bin/python -m pip install pyvista trame"
fi

if [ -n "$MISSING_SONAMES" ]; then
    printf '%s\n' "[6/6] [4/6] reported missing sonames, so the system libraries must be installed too:"
    printf '%s\n' "$APT_MAP" | sed '/^$/d'
    printf '%s\n' "sudo apt-get install -y $APT_PKGS"
else
    printf '%s\n' "[6/6] NO-APT-NEEDED"
fi

printf '\n%s\n' "check_pyvista.sh: done -- every check above ran, nothing was installed (this script always exits 0)."
exit 0
