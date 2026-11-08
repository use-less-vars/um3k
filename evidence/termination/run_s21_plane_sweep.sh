#!/bin/sh
# S21 PLANE SWEEP -- Build A, 50 ohm, one extraction column per run.
#
# What this does: runs evidence/termination/run_build_A.py five times, each
# time with --s21-plane-col set to a different node column (50..54), so the
# transported |s21| and the recorded gamma_plane can be read off the SAME
# mesh at a ladder of planes.  Column 51 is what the default policy already
# picks for this geometry (load column + 1), so the ladder contains the plane
# the single ghost-wave artefact was recorded on -- it is the reference rung,
# not a new measurement.
#
# Artefact naming: run_build_A.py names its output ONLY from --out (default
# evidence/termination/build_A_50ohm.json).  Nothing in the script embeds the
# column, so every rung passes --out explicitly and writes
#     evidence/termination/build_A_50ohm_p<col>_plane.json
# beside the ghost-wave artefact.  Those JSON files are 0664 like the rest of
# the directory; this script and its reader are 0775.
#
# Cost: each rung is a full solve.  The run's own wall clock comes from
# --wall-limit-s (its default) and a run that trips it leaves a <stem>.trip
# .json marker beside its artefact; because of `set -eu` any non-zero exit
# stops the sweep, so it never walks past a tripped rung and reports the
# later columns as if they had been measured.
#
# Read the results with evidence/termination/read_s21_plane_sweep.py.
set -eu

cd "$(dirname "$0")/../.."

for col in 50 51 52 53 54; do
    echo "col=$col -> evidence/termination/build_A_50ohm_p${col}_plane.json"
    python3 evidence/termination/run_build_A.py \
        --out "evidence/termination/build_A_50ohm_p${col}_plane.json" \
        --s21-plane-col "$col"
done
