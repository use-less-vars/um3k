# sparse-probe: the joint mesh-refinement ladder for `R_extracted`

`high_res_run.py` runs five rungs of `tools/host/c1-audit/c1_audit.py` back to back,
refining the mesh in all three bands **at once** -- strip, first-axis air, and the
second-axis `substrate|interface|air` triple -- while holding everything else fixed
(geometry, `f0 = 7833566197.718491 Hz`, the criterion, the column-selection rule,
`R_analytic`). Each rung reports

    Q = R_extracted / R_analytic            R_analytic = 2.8101021387524523

scored against the bar that was registered **before** any refined-mesh number was
taken: `|Q - 1| <= 0.10`, i.e. `R_extracted` in
[2.52909192487721, 3.09111235262770].

Rung 0 is the banked control (the exact 31 x 17 mesh the capture in
`tools/host/c1-audit/out/` was taken on). It is a **gate, not a data point**: it must
return `n_eligible = 1` and `R_extracted` within a relative `1e-6` of
`4.0489791163982565`. If either half fails, the harness is wrong rather than the
physics, so the driver stops, says `HARNESS FAULT`, and runs no further rung. No number
is ever scored against a control that failed.

The gate is **not** on which QZ column was selected; see "Column indices are not
reproducible" below.

## Files

    high_res_run.sh    launcher: finds the repo root (nearest ancestor with emfit/,
                       or $EE_ROOT) and execs the driver with all args passed through
    high_res_run.py    the driver: plan, per-rung subprocess, report, summary
    README.md          this file
    out/               created by a real run; one directory per rung plus
                       summary_HIGHRES.txt

## Quick start

    ./high_res_run.sh --dry-run            # plan table + per-rung env; runs nothing, creates nothing
    ./high_res_run.sh --rungs 0            # rung 0 only: the gate (~25-45 s)
    ./high_res_run.sh                      # rungs 0-3, the pre-registered ladder
    ./high_res_run.sh --include-rung4      # add rung 4 (opt-in)
    ./high_res_run.sh --rungs 0,1,2,3,4
    ./high_res_run.sh --max-gb 12 --timeout 7200
    python3 -u high_res_run.py --help

`--dry-run` is the only mode that touches nothing; every other invocation shells out
to the audit. `--solver sparse` is accepted as a value and then refused with an
explanation (see *This is the dense QZ path* below).

## The pre-registered rule (do not edit)

The ordering is *bar first, number second, verdict third* (`decisions.md`). The bar
was locked while `R_extracted` for a refined mesh was unknown, so a refined-mesh number
can support or refute the operand but can never choose what "agrees" means.

Exactly two outcomes are reachable, and there is no third branch:

* **inside the band** -- `|Q - 1| <= 0.10` at some measured rung: the operand is
  mesh-converged within the registered tolerance, and `R_analytic` is not excluded at
  that tolerance.
* **outside the band** at every measured rung: the operand is not mesh-converged by
  this ladder, and the outstanding question is the *mechanism*, not a new threshold.

`docs/design/t4_amp_ratio.md` §9.6 permits exactly one revisit of this operand, and the
revisit must name a **mechanism** ("a re-meshed run", e.g.) rather than a new number.
Using a post-hoc number from this ladder to move the bar is a breach, not a correction.
If a rung lands outside the band, the report prints diagnostic branches **d1** and
**d2** and leaves the bar where it is; the bar is never re-derived from a result.

## The ladder

`nx = 1 + 2*Y_AIR + STRIP`, `nz = 1 + sum(Z_CELLS)`, `nodes = nx*nz`,
`edges = 3*nx*nz - 2*nx - 2*nz + 1` (triangulated rectangle), `n_pec = (nx-1) + STRIP`,
`free_e = edges - n_pec`. Printed by `--dry-run`:

    rung role             STRIP Y_AIR Z_CELLS      nx   nz  nodes  edges free_e  mtx GB  peak GB     est s
       0 banked control      12     9 8,4,4        31   17    527   1486   1444   0.016     0.09        45
       1 joint, 1.33x        16    12 10,5,5       41   21    861   2460   2404   0.043     0.24       208
       2 joint, 1.67x        20    15 12,6,6       51   25   1275   3674   3604   0.097     0.53       700  *
       3 joint, 2.00x        24    18 14,7,7       61   29   1769   5128   5044   0.190     1.04      1918  *
       4 joint, 2.67x        36    22 20,10,10     81   41   3321   9720   9604   0.687     3.78     13239  *

    * above emfit's _MIXED_DENSE_MAX = 3000: reachable only through
      C1_ALLOW_DENSE_ABOVE_MAX=1, which the driver sets for exactly those rungs.

Rung 0 reproduces the banked capture's DOF count exactly (`31 x 17`, `free_e = 1444`,
peak 0.09 GB), which is what makes it a control rather than a sixth data point.
Projected totals: rungs 0-3 ~48 min, rungs 0-4 ~4.47 h, from the model below.

Rung 4 holds `nx = 81` and moves the split between the strip and the air band rather
than the size: `STRIP = 36` and `Y_AIR = 22` give the same `81 x 41` mesh as
`32 / 24` did, but `n_pec = (nx - 1) + STRIP = 116` instead of `112`, so
`free_e = 9720 - 116 = 9604` (not 9608). The driver recomputes every rung's `free_e`
from `nx`, `nz` and `STRIP` and asserts it against the mesh that was actually built --
the size of the npz's `free_e` index array, its `n_edges` and its `n_nodes` -- so a rung
whose declared tuple and built mesh disagree is reported as a mismatch, not silently
scored.

### Cost model (documented, not measured, for rungs that have not been run)

    peak RAM ~ 5.5 * 8 * free_e^2 bytes
    wall     ~ 45 s * (free_e / 1444)^3

* The **5.5** counts live dense copies of the `free_e x free_e` matrix: the general
  pencil `H`, `C`, the two QZ workspaces, and the accumulation buffer. It is a
  headroom factor, not a measurement -- the audit does not sample RSS -- and it is
  deliberately generous so that `--max-gb` skips a rung *early* instead of the OOM
  killer doing it late.
* The **45 s** base is ~2x pessimistic against rung 0's own log (~21 s), again on
  purpose. As soon as rung 0 finishes, its measured wall clock **replaces** the base
  and the revised per-rung estimates are printed before rung 1 starts.
* The `n^3` power is the dense QZ scaling. If a rung overruns its `--timeout`, its
  process tree is killed, the rung is recorded as timed out, and no number is invented
  for it.

A rung whose projected peak exceeds `--max-gb` (default 8) is **skipped and reported**,
never shrunk to fit: shrinking it would silently change the experiment.

## This is the dense QZ path

`emfit` has no sparse eigensolver, and nothing here adds one. Every rung runs the same
dense QZ pencil as the banked capture, only larger. `emfit` refuses above
`_MIXED_DENSE_MAX = 3000` free edges, so rungs 2-4 exist only through
`C1_ALLOW_DENSE_ABOVE_MAX=1`, which the driver sets for exactly the rungs with
`free_e > 3000` and for no others (rung 0 and rung 1 never see it, so the control is
untouched by the opt-in). Consequences that belong in any reading of the result:

* the family is capped by memory and by `O(n^3)` time, not by physics;
* the last rung is a **resource** decision, not a convergence decision;
* a genuinely larger mesh needs `docs/design/sparse_eigenmode.md` -- an unimplemented
  design and a **re-registration event**, because the banked numbers would have to be
  re-taken on it before any number from it could be scored against `R_analytic`.
  `--solver sparse` therefore refuses rather than pretending.

## How one rung is run

The audit is env-only (the `run.sh` convention), no CLI. For each rung the driver

1. copies the current environment and **drops every inherited `C1_*` key first**, so a
   stale knob in the caller's shell cannot silently move a rung;
2. sets `C1_REPO`, `C1_OUTDIR` (`out/rung<N>_s<strip>_a<yair>_z<z1>-<z2>-<z3>`),
   `C1_STRIP_CELLS`, `C1_Y_AIR_CELLS`, `C1_Z_CELLS`, `C1_ALLOW_REMESH=1` (rungs 1-4
   only) and `C1_ALLOW_DENSE_ABOVE_MAX=1` (rungs 2-4 only), plus
   `OMP/OPENBLAS/MKL_NUM_THREADS=1` so the timing base stays comparable;
3. runs `python3 -u c1_audit.py` with `cwd` at `tools/host/c1-audit`, tees the full
   stdout/stderr to that rung's `run.log`, echoes the audit's own key lines, and prints
   a `PROGRESS` heartbeat every 30 s;
4. reads the numbers back out of **the rung's own** `c1_spectrum.npz`
   (`R_extracted`, `identified_col`, `chosen_col`, `bank_col`, `n_eligible`,
   `eligible_cols`, `R_by_col`, `corr_ey_by_col`, `corr_ez_vv_by_col`, `beta_sq`,
   `beta_sq_all`, `beta`, `eps_eff`, `free_e`, `n_edges`, `n_nodes`, ...) and cross
   checks them against `run.log` (`elapsed=`, `repro=`, `banked_src=`).
   Note that npz key `free_e` is the **index array** of the free edges, so its *size* is
   the count; reading `free_e[0]` gives `1`.

Per rung: `env.json`, `run.log`, `c1_spectrum.npz`, the audit's own tables. The
driver never writes into `tools/host/c1-audit/out/`, so the banked capture and its
hashes stay untouched.

## What the report contains

`out/summary_HIGHRES.txt`, printed to stdout as it is written:

* **PRE-REGISTRATION** -- the locked bar and the §9.6 clause, quoted verbatim, before
  any rung number is shown;
* **per rung** -- mesh and DOF arithmetic, projected vs actual counts, wall clock and
  the audit's own `elapsed`, `repro`, `banked_src`, `beta`/`eps_eff`, then
  `R_extracted`, `Q` and the eligible-column table;
* **cross-rung** -- `R_extracted` and `Q` per rung, in one block;
* **stability** -- index-agnostic, because a column index is not reproducible (below).
  Per rung: `n_eligible` and every eligible column's `beta_sq`, `R_by_col`, `corr_ey`,
  `corr_ez_vv`; then the *selected* mode per rung (`R_extracted`, `beta_sq`). The verdict
  is three components: `n_eligible == 1` on every rung, `R_extracted` smooth in `free_e`,
  and the selected `beta_sq` (= `eps_r * k0^2`, `k0^2 = 2.694e4`, so of order `1.185e5`)
  smooth in `free_e` -- the mode must not change identity as the mesh refines, and
  `beta_sq` can say so while a column index cannot. "Smooth" is the declared test in
  `_smooth()`: monotone, or no step above twice the median step. It is a structural
  reading only and is not scored against the bar. If a rung reports `n_eligible > 1`,
  the rung is named and every eligible column's `R` is printed; that is a finding, not a
  licence to re-select a column;
* **fits** -- (a) `log|R - R_analytic|` against `log free_e`, to show whether the
  residual is shrinking at all, and (b) `R = a/free_e + R_inf`, whose `R_inf` is placed
  against **both** candidates. These are diagnostics; neither is a law, neither moves
  the bar, and an extrapolant is only ever quoted as the fitted intercept, never as a
  rung;
* **rule** -- five steps: control gate, operand, verdict against the band, the d1/d2
  diagnostic branches, and an explicit statement that the bar has not moved.

The last line of a completed run is exactly `DONE`.

## Why joint refinement

Earlier sweeps moved one band at a time and left the others where they were:

    strip  12/18/24/36         -> 4.0489791164 / 4.0463369445 / 4.0514540972 / 4.0493407985
                                  (flat to 0.13 % over 3x -- the strip is not the mechanism)
    y_air  N = 6,8,12,16,20,22 -> 4.4382 / 4.0489 / 3.7125 / 3.5036 / 3.4384 / 3.2761
                                  (the only band that moved R, and still 6.0 % above the
                                   upper edge at its densest reachable point)
    z      12|6|8              -> 4.1029   (moved the wrong way)
           16|8|12             -> unreachable: free_e 3264 > _MIXED_DENSE_MAX = 3000

So: strip is flat, `y_air` alone does not close the gap even at its limit, `z` alone
goes the wrong way, and the `16|8|12` z point cannot be reached without the opt-in. The
one experiment those sweeps did not perform is all three bands **together**, with the
opt-in on where it is needed -- which is exactly what §9.6 calls "a re-meshed run". That
is this ladder.

## Column indices are not reproducible across runs, and never identify a mode

This is measured, not hypothesised. On the **identical** rung-0 mesh (strip 12, air 9,
`z = 8|4|4`, `free_e = 1444`) the banked capture and two fresh runs of the driver do not
agree on a QZ column, for the same physical mode:

    banked capture   identified_col 738, chosen_col 738, bank_col 738, eligible [738]
                     R_extracted 4.0489791163982565
    fresh run A      identified_col 738, chosen_col 732, bank_col 732, eligible [732]
                     R_extracted 4.0489791163950715
    fresh run B      same columns as A, same R to the last printed digit

The two fresh runs are reproducible against each other; the banked index is not
reproducible against them. `identified_col` still reads 738 in a fresh run because it is
carried over from the capture -- the column the criterion actually selects is 732. The
physics is untouched: the banked value and the fresh value agree to 8e-13 relative, and
both pass the control gate. Column ordering in a dense QZ decomposition is a property of
the LAPACK build and the matrix layout, not of the mode, so a column index is
**machine-specific**. Therefore:

* a column number is **never** a mode identifier, in prose, in a table heading, or in a
  commit message -- identify a mode by its `beta_sq` and its `R`;
* a column number is **never** a gate. The rung-0 gate is `n_eligible == 1` plus
  `R_extracted` within `1e-6` relative of `4.0489791163982565`, and nothing else;
* column numbers are still printed, because provenance is useful -- but every one of them
  is labelled a **diagnostic** in the report, and none of them is compared against
  anything.

This applies retroactively to the PEC pair `699` / `704` in the earlier notes: those two
indices are *that* machine's ordering. The physics those indices stand for is the pair

    R = 4.163656524825077      and      R = 70.63501855512833

and any future comparison should quote it that way. A reader who goes looking for modes
"699 and 704" on another machine will not find them, and nothing is wrong when that
happens.

## Guardrails

* The bar, `R_analytic`, the criterion, the column-selection rule and `f0` are
  constants at the top of `high_res_run.py`; none may be edited once a rung has run.
* The control gate is two things, and only two: `n_eligible == 1`, and
  `|R_extracted - 4.0489791163982565| / 4.0489791163982565 <= 1e-6`. The selected column
  index is **not** part of the gate (see the section above), and the same arithmetic check
  binds every rung: `free_e` recomputed from `strip`/`yair`/`z` must equal the size of
  the npz's `free_e` array and `n_edges - n_pec`.
* A skipped rung (peak over `--max-gb`) or a timed-out rung is reported as such and
  takes part in no fit and no verdict.
* Nothing is scored against a control that failed, and no rung is ever "nearly" in the
  band.
