#!/usr/bin/env python3
"""Fine-rung runner for the E11 H2 probe: n_sub = 6 (~0.27 mm cell).

WHY A WRAPPER
-------------
`evidence/termination/run_build_A.py` has no CLI flag for the mesh-refinement
knobs. Its `build_kwargs()` literal (run_build_A.py:502-525) hard-codes
n_sub 4 / n_air 12 / n_top 6 / n_clean 96 / n_pml 6 and does NOT pass n_strip
or n_ref at all, so those two fall through to the emfit/studies.py defaults
(MS_N_STRIP 8 at :1202, MS_N_REF 2 at :1206). Refining the cell therefore
requires changing seven values that no flag reaches. This module changes them
by wrapping `build_kwargs` in memory, after the base module is imported and
before `main()` builds the mesh. Nothing on disk is edited: run_build_A.py and
everything under emfit/ are byte-identical to the versions the coarse rung ran.

Import by file path (`importlib.util.spec_from_file_location`) is safe because
run_build_A.py inserts the repository root on sys.path itself at :110-112
before importing emfit, so the by-path import inherits a working import
context. The module is registered in sys.modules under its own name first, so
any intra-module lookup that goes through sys.modules still resolves.

WHY `check_mesh` IS RE-RUN
--------------------------
`check_mesh()` (run_build_A.py:396) refuses n_top < 0 and n_top != n_pml when
n_pml is nonzero (emfit/studies.py:2555-2557 requires n_top == n_pml). The
base build already passes it; the wrapper passes it again on the *patched*
kwargs so a mismatch introduced here fails at build time rather than after a
2-minute solve.

CELL AND BOX ARITHMETIC
-----------------------
nz = n_top + n_air + n_sub = 9 + 18 + 6 = 33
ny = 2*(n_pml + n_clean) + n_strip = 2*(9 + 144) + 12 = 318
nx = n_pml + n_ref + n_line = 9 + 3 + 96 = 108   (with --n-line 96)
grid 108 x 318 x 33 = 1,133,352 cells (coarse rung: 72 x 212 x 22 = 335,808,
i.e. 3.375x), cell h/n_sub = 1.6e-3/6 = 2.6667e-4 m (coarse: 4.0e-4 m). The
box is unchanged at 84.8 x 8.8 x 28.8 mm; strip 12 cells = 3.2 mm (the
emfit/studies.py:2582 strip-must-equal-width guard still holds), PML 2.4 mm,
side clearance 38.4 mm.

THE COARSE RUNG IS THE SAME SCRIPT UNPATCHED
--------------------------------------------
The coarse anchor for the H2 comparison is
`run_build_A.py --n-line 64 --load-at-mm 20 --load-ohm 50
--mem-ceiling-mb 2000 --s21-plane-index 51` run *directly* (as recorded in
build_A_50ohm_p51_phasors.json meta.argv). This wrapper is used for the fine
rung only, so the rung-to-rung delta is attributable to the mesh and not to a
second code path.

PLANE INDEX IS PASSED THROUGH UNCHANGED
---------------------------------------
`--s21-plane-index N` is forwarded verbatim: run_build_A.py:520-521 assigns it
directly to the plane COLUMN, and its default-policy / upstream-guard branch
(:534-580) runs only when the flag is absent.

The column-to-x map is node-layer arithmetic, x = ix * cell, with no
half-cell offset and no n_pml term (emfit/studies.py:2863, :2940, :3037,
:3630). At the fine cell 2.666666666666667e-4 m: load column 75 = 20.0000 mm,
plane column 76 = 20.2667 mm (column 77 = 20.5333 mm). At the coarse cell
4.0e-4 m: load column 50 = 20.0000 mm, plane column 51 = 20.4000 mm. 20.4 mm
is NOT a node on the fine mesh -- 20.4 / 0.266667 = 76.5, a half-cell tie
between columns 76 and 77 -- so the earlier version of this paragraph, which
put column 76 at 20.4 mm and coarse column 51 at 20.0 mm, was wrong on both
figures.

The two rungs are nonetheless comparable, and exactly so: both extraction
planes sit one column downstream of their OWN load (coarse 50 -> 51, fine
75 -> 76), which is the harness's documented default plane policy
(`col = ... else ix_load + 1`, run_build_A.py:559, policy stated at :535-559).
`--s21-plane-index 76` therefore reproduces the default the policy would have
chosen on this mesh rather than departing from it; the flag sets
`plane_from_default_policy` False (:1698-1699) without changing the column.
What the rungs share is same-rule-same-ordinal, not the same coordinate: only
the physical size of that one cell differs, 0.4000 mm coarse against 0.2667 mm
fine. That is stated in the preregistration (§7.5).

GEOMETRY IS PROVEN FROM THE ARTEFACT, NOT THE LOG
-------------------------------------------------
There is no startup echo to read: every print this harness makes is
post-solve. Geometry is therefore proven either by `--dry-run` beforehand or
by the post-run `geometry` block of the artefact (grid, cells, cell, n_sub,
n_line, loads, s21_plane_index) -- never from a launch-time log line.

Usage:
    python3 evidence/termination/run_build_A_nsub6.py \
        --n-line 96 --load-at-mm 20 --load-ohm 50 \
        --mem-ceiling-mb 2000 --s21-plane-index 76 --nsteps 3600 --dry-run
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "run_build_A.py"

#: The seven mesh keys build_kwargs() has no flag for (run_build_A.py:502-525).
FINE_OVERRIDES = {
    "n_sub": 6,
    "n_strip": 12,
    "n_air": 18,
    "n_top": 9,
    "n_pml": 9,
    "n_clean": 144,
    "n_ref": 3,
}


def _load_base_module():
    """Import run_build_A.py by file path and register it in sys.modules."""
    spec = importlib.util.spec_from_file_location("run_build_A", BASE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError("cannot build import spec for %s" % BASE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_build_A = _load_base_module()

_original_build_kwargs = run_build_A.build_kwargs


def build_kwargs(args):
    """Patch the seven mesh keys onto the kwargs the base build produced."""
    kwargs = _original_build_kwargs(args)
    kwargs.update(FINE_OVERRIDES)
    run_build_A.check_mesh(kwargs)
    return kwargs


run_build_A.build_kwargs = build_kwargs


def main(argv=None):
    return run_build_A.main(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
