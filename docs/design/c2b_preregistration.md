# `C2b` Step 0 -- the `corr_e_z` noise floor

## Purpose

`C2b` is written against a change in `corr_e_z`, and `corr_e_z` has no measured noise floor: nobody has run the same statistic twice on two different meshes of one box and taken the difference. On `beta` the floor is known and quoted (`0.3993 %` in `beta`, `0.8001 %` in `eps`, two codes on one cross-section, `zfree_diagnosis.md` §7.2 item 3). Step 0 measures the corresponding floor for the shape statistic, so that a later `C2b` falsifier can distinguish a wall effect from mesh noise instead of assuming the distinction away.

## What is being measured

Two sources of scatter, and they are different things. **(i) Mesh scatter** -- same physics, same box, same walls, two different meshes. **(ii) Wall scatter** -- same box, same mesh, changed wall treatment. A defensible floor needs (i), and needs (ii) to be shown smaller than the effect or explicitly unresolved.

What exists today, from static read of the logs. **Mesh scatter is measured**: `|corr_e_z| = 0.119160432391342` on 31x17 and `0.119317006502073` on 41x22 (`.scratch/logs/corr_ez_followup.txt:205`, `:212`; same PMC box, same basis, independent caches). **Wall scatter is ABSENT**: no replicate of one mesh under two wall sets exists at matched mesh. The only PEC-pencil value, `0.147291446944630`, comes from `tools/host/c1-audit/pecbox_variant.py`, a different code path on a changed mesh (1382 free edges against 1444), so it cannot separate a wall effect from a mesh/code difference. `.scratch/logs/mesh41.log:18`, `mesh51.log:18` and `mesh51b.log:18` all print `corr_e_z = 0.14619976001754773`, but that line is the shared 31x17 preamble in each log, not the refined mesh's own statistic, and the value is RETRACTED (§8.1; `corr_ez_followup.txt:117`, `:200`: no candidate reproduces it). It is not a replicate of anything and is not used here.

The statistic is also sign-unstable across meshes: `corr_e_y` reads `+0.92077078481114205` on 31x17 (`:43`) against `-0.93870218003589878` on 41x22 (`:126`). Step 0 therefore compares `|corr_e_z|`, never the signed value, or the comparison measures a sign convention rather than a mesh.

## Procedure

Five extractions, no solver run for four of them, in this order.

1. **31x17, PMC (baseline).** Cache `.scratch/s10118_mixed_mode.npz`, `tools/corr_ez_101_20.py`, row `1 BASELINE  -|beta*z_free| (current code path)`, correlate against the analytic `E_z`. Expected `0.119160432391342` (`corr_ez_followup.txt:205`); a deviation from the banked digits is itself a finding and stops the sequence.
2. **41x22, PMC.** Cache `.scratch/s10118_mode_41x22.npz`, same script, same row, same reference. Expected `0.119317006502073` (`:212`).
3. **51x19, PMC.** Cache `.scratch/s10118_mode_51x19.npz`, same script, same row, same reference. Never extracted; this is the new number and the one that turns an interval into a spread.
4. **31x17, PEC walls.** The PEC-walled variant of the same 31x17 node mesh, `tools/host/c1-audit/pecbox_variant.py`, which reports the overlap directly. Expected `0.147291446944630`. This is the wall replicate at fixed mesh: 31x17 against 31x17, walls the only change.
5. **Determinism repeat.** Re-run (1) unchanged. The two results must be bit-identical; a dispersion here is an extraction defect, not a floor, and invalidates the other four.

Statistic for every row: `|corr_e_z|` from the `E_z` overlap against the analytic basis, same reference field, same lattice. All five write to one log; none may be reported from a different build than the others (record the `emfit/mode2d.py` hash, as `corr_ez_followup.txt:4` does).

## Tolerance

Measured mesh spread, from the two points that exist: `0.119317006502073 - 0.119160432391342` = **`0.000156574110731`** absolute, which is **`0.1314 %`** of `0.119160432391342`. Two points give an interval and not a dispersion, so the *noise level* is taken as `F = 1.5657e-4` and the *detection threshold* is set at `2F` = **`3.1315e-4`** (0.26 % relative), the factor of two being the margin a two-point interval cannot justify being smaller. If step 3 raises `F` by more than a factor of 1.5, steps 1-3 are repeated on a fourth mesh before the floor is published.

**Wall tolerance: PENDING.** No wall replicate at fixed mesh exists (item 2 above is ABSENT). The measurement that sets it is procedure step 4 read against step 1: same mesh, same basis, walls the only change. Until that pair exists, every PEC-vs-PMC statement carries an unquantified term and no `C2b` falsifier may be written on the difference.

## Acceptance

A `C2b` run is only capable of falsifying something if both of the following hold.

* **`beta` criterion.** The reported `beta` change must exceed **`0.3993 %`**, the two-code floor on the same cross-section (`zfree_diagnosis.md` §7.2 item 3); below it the run cannot tell its own effect from cross-code disagreement, and the `eps` reading is judged at `0.8001 %`.
* **`corr_e_z` criterion.** `||corr_e_z|_patched - |corr_e_z|_baseline|` must exceed the Step 0 threshold, `3.1315e-4` absolute, against a noise level of `1.5657e-4`. The effect on the table is the PEC-vs-PMC shift, `0.147291446944630 - 0.119160432391342` = **`0.028131014553288`**, about **180x** the step-1/step-2 spread and 23.6 % relative: large enough that the measurement is *capable* of resolving it, which is not the same as its being a wall effect.

If Step 0 returns a floor within an order of magnitude of `0.028131014553288`, `corr_e_z` cannot carry the `C2b` argument on this box and the pre-registration must be rewritten around an observable with a floor below the effect.

## What would invalidate Step 0 itself

* **Mesh scatter as large as the effect being hunted.** If steps 1-3 span a range comparable to `0.0281`, then `corr_e_z` is a mesh-noise statistic on this box, the PEC-vs-PMC shift is uninterpretable, and `C2b` needs a different observable rather than a tighter tolerance.
* **The 51x19 extraction disagreeing with both existing points in one direction only**, which would say the two banked values are not replicates of one quantity.
* **A non-identical step 5**, which makes every other row a single sample with no dispersion and forces the extraction to be fixed before any floor is quoted.
* **A sign flip in `corr_e_y` between any two rows that is not uniform**, since the papered-over alternative -- comparing signed `corr_e_z` -- would then report a 0.238 difference where the magnitude axis reports `1.6e-4`.

## Fences

No solver modification. Step 0 changes meshes and walls only, never the physics, and never anything under `emfit/`: it reads banked caches and calls the diagnostic script and the PEC-variant script as they stand. No new solve is authorised except the PEC-walled variant at 31x17 if its cache is absent, and that run changes boundary conditions, not formulation. Nothing here re-opens `D1`, the attribution rule, or the `1e-12` guard (§7.3 item 3): Step 0 is a measurement of the statistic `C2b` will be judged on, not a patch.
