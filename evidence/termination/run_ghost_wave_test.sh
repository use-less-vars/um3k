#!/bin/sh
# Ghost-wave / phantom-mode test on the 50 ohm Run A build, plane 51.
#
# PURPOSE
#   One graded 50 ohm series-R run at plane 51 that carries, beside the usual
#   artefact, everything a post-hoc mode analysis needs:
#     * load_edge_dump -- the phasor on every E_z edge of the load's own column,
#       so the element's own current/voltage distribution can be compared edge
#       by edge against a driven mode profile;
#     * s21_plane -- the cut plane's two travelling waves (v, i, a, b) as they
#       were divided to make gamma_plane, so that reflection can be re-derived
#       from the file alone;
#     * <stem>_fields.npz -- the last time step's E and H fields plus the four
#       plane-capture phasor blocks (plane_ez, plane_hy, plane_ey, plane_hz),
#       which is where a ghost wave living between the stations would show up.
#
# ARTEFACTS (written beside this script)
#   build_A_50ohm_p51_ghostwave.json         the run record, with load_edge_dump
#                                            and s21_plane at its top level
#   build_A_50ohm_p51_ghostwave_fields.npz   e, h, plane_ez, plane_hy, plane_ey,
#                                            plane_hz + nstep, nx, ny, nz, cell_m
#                                            (plain numeric arrays: read back
#                                            with np.load(..., allow_pickle=False))
#
# PLANE CAPTURE
#   The four plane blocks are allocated only when the library's plane-capture
#   channel says so.  run_build_A.py does not pass the `plane_capture` kwarg at
#   all, so the channel is its documented environment variable, set below --
#   microstrip_wave then resolves it and records "plane_capture": "env" in the
#   plane record.  Unset, the .npz simply has no plane_* keys; nothing fails.
#
# ONE SHOT
#   An FDTD run cannot be resumed, only repeated, and a repeat is a new decision.
#   The trip clause inside the Python is hard: a memory trip exits 3 and writes
#   .trip.json, a wall trip exits 4.  Do not relaunch it in a loop, and do not
#   run this script twice over the same artefact.
#
# EXPECTED RUNTIME
#   One loaded solve on the Run A mesh (62 x 44 x 22 cells, nsteps from
#   build_kwargs): the frozen single-run row is ~<1400 s wall, peak RSS well
#   under the 2000 MB ceiling.  Field snapshots add ~2 field-sized arrays plus
#   0.58 MB of default-coupon planes, and the compressed .npz is written once
#   after the loop, so the wall cost is the solve plus a few seconds.

set -eu

cd "$(dirname "$0")/../.."

EMFIT_PLANE_CAPTURE=1 python3 evidence/termination/run_build_A.py \
    --out evidence/termination/build_A_50ohm_p51_ghostwave.json \
    --dump-load-edges \
    --dump-fields
