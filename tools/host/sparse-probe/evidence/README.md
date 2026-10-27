# sparse-probe evidence

Text artefacts of the ladder runs whose binaries live in `out/` (git-ignored, see
`../.gitignore`).  Every `.npz` is 17-46 MB and is *not* committed; its sha256 is.
Nothing here is a new measurement -- these files are byte copies of files the run
already wrote, kept so the numbers quoted in `docs/design/t4_amp_ratio.md` can be
re-derived from a clean checkout.

`run.log.txt` is a byte-identical copy of the run's `run.log`; the `.txt` suffix is
only because the repository root `.gitignore` ignores `*.log`.

## Runs

    dir                              rung  mesh strip/air/z   free_e  nodes  col*   R_extracted        Q        |Q-1|     n_elig  repro  elapsed
    rung0_s12_a9_z8-4-4                0   12 /  9 / 8|4|4     1444    527   732  4.0489791163950715  1.440865  0.440865     1    PASS    20.1 s
    rung1_s16_a12_z10-5-5              1   16 / 12 / 10|5|5    2404    861  1224  3.7803319900157453  1.345265  0.345265     1    FAIL**  108.7 s
    run_a_rung0_s12_a9_z8-4-4          0   12 /  9 / 8|4|4     1444    527   732  4.0489791163950715  1.440865  0.440865     1    PASS    19.8 s
    run_b_rung0_s12_a9_z8-4-4          0   12 /  9 / 8|4|4     1444    527   732  4.0489791163950715  1.440865  0.440865     1    PASS    21.1 s

    *  the QZ column index is a DIAGNOSTIC, not a mode identifier and never a gate
       (README.md, "Column indices are not reproducible across runs").  The banked
       capture of the same rung-0 mesh holds 738 for the same mode; these runs select
       732, and R agrees with the banked value to 7.9e-13 relative.
    ** rung 1 is a re-meshed run: there is no banked column for it, so the
       reproduction check has nothing to reproduce and is EXPECTED to report FAIL.
       It is not a fault; the control is rung 0, and rung 0 passed.

`ladder/` holds the three driver reports:

    summary_HIGHRES.txt   the scored ladder (rung 1; rung 0 did not run in this pass)
    summary_run_a.txt     the first rung-0-only control probe
    summary_run_b.txt     the second, byte-identical control probe

## What each directory contains

    env.json         the exact environment the audit was given (C1_* keys and thread
                     pinning); this is the only input record -- the audit has no CLI
    c1_table.txt     the audit's own criterion table (columns, correlations, the one
                     row that passes)
    run.log.txt      full audit stdout/stderr: mesh arithmetic, the banked-mesh check,
                     the reproduction check, and the DONE line with elapsed/repro
    npz.sha256       sha256 of the (uncommitted) c1_spectrum.npz this directory's
                     numbers were read out of

The npz payload that the numbers above come from is not needed to read them: every
value in the table is printed in `run.log.txt` (the `DONE ... R_extracted=` line) and
in `c1_table.txt` (col, beta_sq, corr_e_y, corr_ez_vv).

## The banked capture is untouched

These runs never wrote into `tools/host/c1-audit/out/`.  Verified after the ladder:

    c1_spectrum.npz    05387390cf2977364c2e6f62a1c694149fc13754d054c9c51bbccbabcf9568d4
    pecbox_spectrum.npz 92d283155a5e2fe5607e5867f8ebab2d7861c682e60274a8667f5dcd80340f18

Both are the values the capture was banked with; the control rung reproduced that
mesh's DOF count (`31 x 17`, `free_e = 1444`) exactly, which is what makes rung 0 a
control and not a sixth data point.
