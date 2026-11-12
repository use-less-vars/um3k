#!/bin/sh
# scripts/test_all.sh — full-suite runner: one pytest process per test file.
#
# WHY ONE FILE PER PROCESS, AND WHY A WRAPPER CLOCK.
# The suite does not fit in one invocation. Several tests are real FDTD solves,
# and the container's 512 MB cgroup plus the 300 s clock turn a healthy suite
# into a wall of timeouts — DR-39, docs/design/defect_register.md:696-723. The
# worst observed case expires inside a scipy CSR matvec (185108 x 190296,
# 740432 stored entries, scipy/sparse/_compressed.py:395, a real solve and not
# a pathological input): pytest-timeout's default `signal` method arms SIGALRM,
# and SIGALRM cannot interrupt a blocked C call, so the alarm fires only when
# the call returns and the report is indistinguishable from a hang and from a
# failure (DR-39:707, :714, :717, :723).
#
# Hence three flags on every call, none of them optional:
#   -o addopts=""   the `addopts = "-q"` in pyproject.toml:62 must not make the
#                   quiet flag double; `-qq` deletes the summary line and the
#                   collect-only ids (DR-39:706).
#   -o timeout=0    pytest-timeout's own SIGALRM clock is switched off, so the
#                   `timeout` below is the only clock in the run and a stall has
#                   exactly one way to be reported.
#   -q              quiet, one summary line per file.
#
# Exit 124 from `timeout` means the file was still running at the clock. That is
# STALLED, not FAILED: per DR-39:723 a timeout is not evidence of a failing
# test, and no pass count may be quoted from a run without a summary line. This
# script prints only the numbers it actually observed.
#
# Usage:
#   sh scripts/test_all.sh                          # 300 s per file
#   TEST_TIMEOUT=400 sh scripts/test_all.sh         # longer per-file clock
#   PYTHONPATH=build/cpp sh scripts/test_all.sh     # extension-dependent files
#
# Env: TEST_TIMEOUT  seconds per file (default 300)
#      PYTEST        the runner command (default: "python3 -m pytest"); it is
#                    word-split on purpose, so
#                    PYTEST="python3 -m pytest -p no:cacheprovider" works.
# Exit: 0 only if every test file passed. 1 if any file failed or stalled.
#       2 if there is nothing to run.

set -u

TEST_TIMEOUT="${TEST_TIMEOUT:-300}"
PYTEST="${PYTEST:-python3 -m pytest}"

passed=0
failed=0
stalled=0
not_passed=""

for f in tests/test_*.py; do
	if [ ! -f "$f" ]; then
		echo "test_all.sh: no tests/test_*.py found under $(pwd)" >&2
		exit 2
	fi

	printf '=== %s\n' "$f"

	# $PYTEST is intentionally unquoted: it is a command plus its arguments.
	# shellcheck disable=SC2086
	out=$(timeout "$TEST_TIMEOUT" $PYTEST "$f" -o addopts="" -o timeout=0 -q 2>&1)
	rc=$?

	# The tail is shown for every file, pass or not: per DR-39:723 the summary
	# line is the only thing that makes a count citable.
	printf '%s\n' "$out" | tail -20

	case $rc in
	0)
		passed=$((passed + 1))
		;;
	124)
		stalled=$((stalled + 1))
		not_passed="$not_passed
  STALLED  $f  (still running at the ${TEST_TIMEOUT} s clock — not a failure)"
		;;
	*)
		failed=$((failed + 1))
		not_passed="$not_passed
  FAILED   $f  (exit $rc)"
		;;
	esac
done

total=$((passed + failed + stalled))
echo
echo "=== summary: $total files — $passed passed, $failed failed, $stalled stalled (per-file clock ${TEST_TIMEOUT} s)"

if [ -n "$not_passed" ]; then
	echo "not passed:$not_passed"
	exit 1
fi

echo "all $passed files passed"
exit 0
