#!/usr/bin/env bash
# high_res_sweep.sh — entry point for the 40k / 50k / 60k sparse Route-C sweep.
#
# PREPARED, NOT RUN: this wrapper has never been executed. Running it performs
# three real solves (one child process per point) and writes
# out_highres/points/*.json plus out_highres/high_res_sweep.json.
#
#   ./high_res_sweep.sh --plan            # print the plan, run nothing
#   ./high_res_sweep.sh                   # the sweep
#   ./high_res_sweep.sh --no-chain        # freeze sigma at the ~30k seed
#   ./high_res_sweep.sh --family ladder   # the ~30k shape instead of strip-12
#
# -u so the per-point progress lines stream instead of arriving in one burst
# when the child exits.
set -euo pipefail

cd "$(dirname "$0")"

exec python3 -u high_res_sweep.py "$@"
