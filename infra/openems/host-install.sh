#!/usr/bin/env bash
# install.sh — build CSXCAD + openEMS from source into a private prefix.
#
# RUN AS ROOT:   sudo bash /home/jojo/openems-host/install.sh
# SKIP THE 3-MIN SMOKE SOLVE:   sudo SKIP_SMOKE=1 bash /home/jojo/openems-host/install.sh
#
# Design notes:
#  * Prefix is /opt/openems; system python is NEVER touched (no pip into it,
#    no --break-system-packages). Reachability is via a .pth file + ldconfig.
#  * Builds are executed as user "jojo" through runuser, so build artefacts in
#    $BUILD stay jojo-owned instead of root-owned. Every build command goes
#    through the as_jojo() helper — that is the ONE mechanism used throughout
#    (no mixing with su/sudo -u).
#  * PROBED FACT (grep of both repos' CMakeLists.txt): neither CSXCAD nor
#    openEMS defines PYTHON_INSTALL_PATH / PYTHON_EXECUTABLE / PYTHON_SITE_*
#    cache variables. Their python bindings are built by python/setup.py, which
#    honours the CSXCAD_INSTALL_PATH and OPENEMS_INSTALL_PATH env vars and
#    installs into <prefix>/lib/pythonX.Y/{site,dist}-packages via --prefix.
#    So the bindings are installed with setup.py, not with a CMake flag.
#  * Idempotent: re-running is safe — every build stage first wipes its source
#    and build tree, so no stale CMakeCache.txt is reused (e.g. a cached
#    fparser_INCLUDE_DIR-NOTFOUND); ldconfig/.pth are overwritten.
set -euo pipefail

PREFIX="/opt/openems"
BUILD="/home/jojo/openems-host/build"
LOG="/home/jojo/openems-host/install.log"
OWNER="jojo"
SKIP_SMOKE="${SKIP_SMOKE:-0}"
SMOKE_SCRIPT="/home/jojo/PycharmProjects/EE/docker/openems/smoke_solve.py"
SMOKE_OUT="/tmp/host-oems-sim"
LDCONF="/etc/ld.so.conf.d/openems.conf"
PTH_DIR="/usr/lib/python3/dist-packages"
PTH="${PTH_DIR}/openems.pth"
PY_TAG="$(python3 -c 'import sys; print("python%d.%d" % sys.version_info[:2])')"
# The ONE directory the python bindings live in, and the only thing $PTH points
# at.  `setup.py install --prefix` would instead scatter an egg into
# $PREFIX/local/lib/pythonX.Y/dist-packages, a second location nothing looks at.
PYDEST="$PREFIX/lib/$PY_TAG/dist-packages"
BINDINGS_OK=1          # cleared if the python bindings do not build / import

mkdir -p "$(dirname "$LOG")"
# shellcheck disable=SC2086
exec > >(tee -a "$LOG") 2>&1
echo "=== openEMS host install started $(date -Is) — log: $LOG ==="

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: must run as root (sudo bash $0)"; exit 1
fi
if ! id "$OWNER" >/dev/null 2>&1; then
    echo "ERROR: build user '$OWNER' does not exist"; exit 1
fi

# ---- single mechanism for dropping privileges -----------------------------
as_jojo() { runuser -u "$OWNER" -- "$@"; }

# Fail loudly when a bindings build produced no extension modules, instead of
# copying an empty directory and reporting success.
check_so() {  # $1=directory  $2=label
    local n
    n=$(ls -1 "$1"/*.so 2>/dev/null | wc -l) || true
    if [ "$n" -eq 0 ]; then
        echo "  ERROR: $2 -- no .so files in $1 (the build did NOT produce them)"
        return 1
    fi
    echo "  $2: $n extension module(s) in $1"
    ls -1 "$1"/*.so
}

FAILED=()

# ===========================================================================
# Step A — build dependencies (best effort: one missing package must not
# abort the run; a summary of failures is printed at the end)
# ===========================================================================
echo; echo "--- Step A: build dependencies ---"
PKGS=(
    build-essential cmake git
    libhdf5-dev libvtk9-dev libboost-dev libtinyxml-dev libcgal-dev
    libfparser-dev      # fparser.hh + libfparser.so, required by CSXCAD cmake
    cython3 python3-dev python3-numpy
    python3-h5py        # openEMS/openEMS.pyx imports h5py unconditionally
)
DEBIAN_FRONTEND=noninteractive apt-get update || echo "WARN: apt-get update failed, continuing"
for pkg in "${PKGS[@]}"; do
    if DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$pkg"; then
        echo "  OK   $pkg"
    else
        echo "  FAIL $pkg"
        FAILED+=("$pkg")
    fi
done
if [ "${#FAILED[@]}" -gt 0 ]; then
    echo "  optional packages that could NOT be installed: ${FAILED[*]}"
else
    echo "  all build dependencies installed"
fi

mkdir -p "$PREFIX" "$BUILD"
chown -R "$OWNER":"$OWNER" "$BUILD"

# Helper: always start from a pristine source tree (deterministic re-runs).
fresh_clone() {  # $1=url  $2=dir
    rm -rf "$2"
    as_jojo git clone --depth 1 "$1" "$2"
}

# ===========================================================================
# Step B — CSXCAD (FDTD geometry library + python bindings)
# ===========================================================================
echo; echo "--- Step B: CSXCAD ---"
CSX_SRC="$BUILD/CSXCAD"
CSX_BLD="$BUILD/CSXCAD-build"
fresh_clone "https://github.com/thliebig/CSXCAD.git" "$CSX_SRC"
rm -rf "$CSX_BLD"                        # never reuse a stale CMakeCache.txt
mkdir -p "$CSX_BLD"; chown "$OWNER":"$OWNER" "$CSX_BLD"
as_jojo cmake -S "$CSX_SRC" -B "$CSX_BLD" \
    -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_APPCSXCAD=OFF
as_jojo cmake --build "$CSX_BLD" -j"$(nproc)"
cmake --install "$CSX_BLD"
echo "  CSXCAD C++ library installed into $PREFIX"

# python bindings (separate setup.py build; CMake does not install them).
# Built in place as $OWNER, then copied into the single bindings directory
# $PYDEST.  `setup.py install --prefix` is deliberately NOT used: it writes a
# CSXCAD egg into $PREFIX/local/lib/pythonX.Y/dist-packages/, which no
# interpreter on this system ever looks at.
if [ -f "$CSX_SRC/python/setup.py" ]; then
    rm -rf "$CSX_SRC/python/build" "$CSX_SRC/python/dist" "$CSX_SRC/python"/*.egg-info
    if ( cd "$CSX_SRC/python" && as_jojo env CSXCAD_INSTALL_PATH="$PREFIX" \
            python3 setup.py build_ext --inplace ); then
        rm -rf "$PYDEST/CSXCAD"
        mkdir -p "$PYDEST"
        cp -a "$CSX_SRC/python/CSXCAD" "$PYDEST/"
        check_so "$PYDEST/CSXCAD" "CSXCAD python bindings" || BINDINGS_OK=0
    else
        echo "  FAIL: CSXCAD python bindings build failed (C++ library is installed; fix and re-run)"
        BINDINGS_OK=0
    fi
fi

# ===========================================================================
# Step C — openEMS (solver + python bindings)
# ===========================================================================
echo; echo "--- Step C: openEMS ---"
OEMS_SRC="$BUILD/openEMS"
OEMS_BLD="$BUILD/openEMS-build"
fresh_clone "https://github.com/thliebig/openEMS.git" "$OEMS_SRC"
rm -rf "$OEMS_BLD"                       # never reuse a stale CMakeCache.txt
mkdir -p "$OEMS_BLD"; chown "$OWNER":"$OWNER" "$OEMS_BLD"
as_jojo cmake -S "$OEMS_SRC" -B "$OEMS_BLD" \
    -DCMAKE_INSTALL_PREFIX="$PREFIX" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH="$PREFIX" \
    -DCSXCAD_ROOT="$PREFIX"
as_jojo cmake --build "$OEMS_BLD" -j"$(nproc)"
cmake --install "$OEMS_BLD"
echo "  openEMS C++ solver installed into $PREFIX"

# python bindings.  PYTHONPATH MUST contain the CSXCAD python source directory:
# openEMS/openEMS.pxd does `from CSXCAD.CSXCAD cimport _ContinuousStructure,
# ContinuousStructure`, and Cython resolves that only against cwd + sys.path.
# Without it the build dies with "'CSXCAD/CSXCAD.pxd' not found" followed by
# cascading "'_ContinuousStructure' is not a type identifier" / "cimported
# module has no attribute 'fromPtr'" errors (that was bug #1 of this script).
# CSXCAD_PYSRC_PATH is a different thing: it is only consumed by
# bootstrap/find_package.py::add_csxcad() to fill in the install_requires
# metadata -- it does NOT put the .pxd files on Cython's include path.
if [ -f "$OEMS_SRC/python/setup.py" ]; then
    rm -rf "$OEMS_SRC/python/build" "$OEMS_SRC/python/dist" "$OEMS_SRC/python"/*.egg-info
    if ( cd "$OEMS_SRC/python" && as_jojo env OPENEMS_INSTALL_PATH="$PREFIX" \
            CSXCAD_PYSRC_PATH="$CSX_SRC/python" PYTHONPATH="$CSX_SRC/python" \
            python3 setup.py build_ext --inplace ); then
        rm -rf "$PYDEST/openEMS"
        mkdir -p "$PYDEST"
        cp -a "$OEMS_SRC/python/openEMS" "$PYDEST/"
        check_so "$PYDEST/openEMS" "openEMS python bindings" || BINDINGS_OK=0
    else
        echo "  FAIL: openEMS python bindings build failed (solver binary is installed; fix and re-run)"
        BINDINGS_OK=0
    fi
fi

# ===========================================================================
# Step D — make it usable system-wide WITHOUT touching system python
# ===========================================================================
echo; echo "--- Step D: ldconfig + .pth ---"
mkdir -p "$(dirname "$LDCONF")"
echo "$PREFIX/lib" > "$LDCONF"
ldconfig
echo "  wrote $LDCONF (contains: $PREFIX/lib) and ran ldconfig"

# Exactly one bindings location: $PYDEST (defined at the top of this script).
# Older versions used `setup.py install --prefix`, which additionally leaves a
# tree at $PREFIX/local/lib/pythonX.Y/dist-packages/ holding the CSXCAD egg --
# remove it so there is no ambiguity about which copy is imported.
if [ -d "$PREFIX/local" ]; then
    rm -rf "$PREFIX/local"
    echo "  removed legacy tree $PREFIX/local (bindings now live only in $PYDEST)"
fi
# No candidate-list guessing any more: the bindings were placed in $PYDEST.
if [ -d "$PYDEST" ]; then
    mkdir -p "$PTH_DIR"
    echo "$PYDEST" > "$PTH"
    echo "  wrote $PTH -> $PYDEST"
else
    echo "  FAIL: $PYDEST does not exist -- no python bindings were installed"
    BINDINGS_OK=0
fi
echo "  ensure $PREFIX/bin is on PATH for the CLIs, e.g.: export PATH=\"$PREFIX/bin:\$PATH\""

# ===========================================================================
# Step E — verification (never fatal)
# ===========================================================================
echo; echo "--- Step E: verification ---"
if [ -x "$PREFIX/bin/openEMS" ]; then
    "$PREFIX/bin/openEMS" --help 2>&1 | head -n 5 || true
else
    echo "  WARN: $PREFIX/bin/openEMS not found"
fi
# Hard check: a solver binary without importable bindings is a half-install.
PYOUT="$(python3 -c 'import CSXCAD, openEMS; print("HOST-OEMS-OK")' 2>&1)" || true
if printf '%s\n' "$PYOUT" | grep -qx 'HOST-OEMS-OK'; then
    echo "  bindings import OK: $PYOUT"
else
    BINDINGS_OK=0
    echo "  FAIL: 'python3 -c \"import CSXCAD, openEMS\"' did not print HOST-OEMS-OK"
    echo "        actual output was:"
    printf '%s\n' "$PYOUT" | sed 's/^/          /'
    echo "        $PTH points at: $(cat "$PTH" 2>/dev/null || echo '<missing>')"
    echo "        bindings directory: $PYDEST"
    echo "        -> a solver without importable bindings is a half-install, not a success"
fi

if [ "$SKIP_SMOKE" = "1" ]; then
    echo "  SKIP_SMOKE=1 — skipping the smoke solve"
elif [ -f "$SMOKE_SCRIPT" ]; then
    echo "  running smoke solve (~3 min): $SMOKE_SCRIPT $SMOKE_OUT"
    if timeout 900 python3 "$SMOKE_SCRIPT" "$SMOKE_OUT"; then
        echo "  smoke solve finished OK"
    else
        echo "  WARN: smoke solve FAILED (see output above); the install itself is not marked failed"
    fi
else
    echo "  WARN: smoke script not found: $SMOKE_SCRIPT"
fi

# ===========================================================================
# Summary
# ===========================================================================
cat <<SUMMARY

================ SUMMARY ================
Installed / built:
  CSXCAD  (lib + bindings)  -> $PREFIX
  openEMS (solver + bindings) -> $PREFIX
  python bindings           -> $PYDEST (CSXCAD/ and openEMS/, one directory)
  python bindings importable: $([ "$BINDINGS_OK" = 1 ] && echo yes || echo "NO -- see Step E")
System files created:
  $LDCONF   (contains $PREFIX/lib; ldconfig already run)
  $PTH      (contains $PYDEST)
Package failures (optional, non-fatal): ${FAILED[*]:-none}

How to use:
  export PATH="$PREFIX/bin:\$PATH"
  openEMS --help                       # FDTD solver CLI
  AppCSXCAD                            # only if built with -DBUILD_APPCSXCAD=ON (not requested here)
  python3 -c "import CSXCAD, openEMS; print('ok')"

How to uninstall:
  rm -rf "$PREFIX"           # C++ libs, CLIs, headers AND the python bindings ($PYDEST)
  rm -f "$LDCONF" "$PTH"
  ldconfig
  rm -rf "$BUILD"          # build tree, optional
Rebuild from scratch: just re-run this script (each stage wipes + rebuilds).
=========================================
SUMMARY
echo "=== finished $(date -Is) ==="
if [ "$BINDINGS_OK" != 1 ]; then
    echo "RESULT: FAILED -- the python bindings are not built/importable (see Step E above)"
    exit 1
fi
echo "RESULT: OK -- C++ libraries, CLIs and python bindings installed"
