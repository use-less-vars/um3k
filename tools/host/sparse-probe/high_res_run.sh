#!/usr/bin/env bash
# high_res_run.sh -- thin launcher for high_res_run.py.
#
# Finds the repository root (the nearest ancestor holding emfit/) or takes it
# from $EE_ROOT, then execs the driver with every argument passed through
# untouched.  The driver resolves its own paths from __file__, so the only job
# here is to fail early and loudly if python3 or the repo root is missing.
#
#   ./high_res_run.sh --dry-run
#   ./high_res_run.sh --rungs 0
#   ./high_res_run.sh                        # rungs 0-3
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
	echo "high_res_run.sh: python3 not found on PATH" >&2
	exit 2
fi

ROOT="${EE_ROOT:-}"
if [ -z "$ROOT" ]; then
	probe="$HERE"
	while [ "$probe" != "/" ]; do
		if [ -d "$probe/emfit" ]; then
			ROOT="$probe"
			break
		fi
		probe="$(dirname -- "$probe")"
	done
fi
if [ -z "$ROOT" ] || [ ! -d "$ROOT/emfit" ]; then
	echo "high_res_run.sh: could not find a repository root containing emfit/ above" >&2
	echo "                 $HERE -- set EE_ROOT=/path/to/EE and retry" >&2
	exit 2
fi

exec python3 -u "$HERE/high_res_run.py" "$@"
