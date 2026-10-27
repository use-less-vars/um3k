# `C2b` Step 0 -- the `corr_e_z` noise floor

## Purpose

`C2b` is written against a change in `corr_e_z`, and `corr_e_z` has no measured noise floor: nobody has run the same statistic twice on two different meshes of one box and taken the difference. On `beta` the floor is known and quoted (`0.3993 %` in `beta`, `0.8001 %` in `eps`, two codes on one cross-section, `zfree_diagnosis.md` §7.2 item 3). Step 0 measures the corresponding floor for the shape statistic, so that a later `C2b` falsifier can distinguish a wall effect from mesh noise instead of assuming the distinction away.

## What is being measured

Two sources of scatter, and they are different things. **(i) Mesh scatter** -- same physics, same box, same walls, two different meshes. **(ii) Wall scatter** -- same box, same mesh, changed wall treatment. A defensible floor needs (i), and needs (ii) to be shown smaller than the effect or explicitly unresolved.

What exists today, from static read of the logs. **Mesh scatter is measured**: `|corr_e_z| = 0.119160432391342` on 31x17 and `0.119317006502073` on 41x22 (`.scratch/logs/corr_ez_followup.txt:205`, `:212`; same PMC box, same basis, independent caches). **Wall scatter is measured at fixed mesh** (see `## Tolerance`): the PEC-pencil value, `0.147291446944630`, comes from `tools/host/c1-audit/pecbox_variant.py`, which executes the same audit on the same 31x17 mesh -- 527 nodes, 960 triangles, 1486 edges -- with only the wall classification changed, 42 PEC edges against 104. `.scratch/logs/mesh41.log:18`, `mesh51.log:18` and `mesh51b.log:18` all print `corr_e_z = 0.14619976001754773`, but that line is the shared 31x17 preamble in each log, not the refined mesh's own statistic, and the value is RETRACTED (§8.1; `corr_ez_followup.txt:117`, `:200`: no candidate reproduces it). It is not a replicate of anything and is not used here.

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

**Wall tolerance: MEASURED, at fixed mesh.** The wall replicate exists and is same-mesh, same-box, same-code-path. `tools/host/c1-audit/pecbox_variant.py` rebuilds nothing: it wraps only `emfit.mode2d.pec_edge_mask` and `emfit.mode2d.pec_node_mask` (`:366-367`) and then executes the audit itself, `import c1_audit` (`:371`), so the mesh comes from `c1_audit.py`'s own builder `structured_mesh(XS, ZS)` (`c1_audit.py:287-289`) and the correlations are the audit's own. The three open walls (`wall_y=0mm`, `wall_y=20mm`, `wall_z=7.6mm`; `pecbox_variant.py:181-193`) are the only change: PEC edges `42 -> 104` and `free_edges` `1444 -> 1382`, while `nodes 527 / tris 960 / edges 1486 / xs 31 / ys 17` are unchanged (`out/pecbox_run.log:36`, `:53`; `out/pecbox_table.txt` header against `out/c1_table.txt`). The audit's own routine reproduces the PMC anchor on the PMC configuration (`out/c1_table.txt` col `738`, `corr_e_z +0.1191604` against anchor `0.11916043239134175`), so the pair is not cross-estimator.

The measured shift: `0.147291446944630 - 0.119160432391342` = **`0.028131014553288`** absolute; relative, `0.028131014553288 / 0.119160432391342` = **`0.2361`** = **23.6 %**; against the mesh floor, `0.028131014553288 / 0.000156574110731` = **`179.7`**, i.e. **`~180x`** the mesh term.

One caveat, recorded not hidden: the box's number is its best-`|corr_e_y|` propagating mode, column `699` (`out/pecbox_run.log:82`), not the PMC run's column `738`, which is unavailable under the walls (`:84`, `:86`). The walls add a second propagating mode -- 2 in `out/pecbox_table.txt` against 1 in `out/c1_table.txt` -- and the two matched modes are the same physical mode on the `eps_eff` axis (`3.606095` against `3.629512`, 0.65 %). The shift is therefore a wall effect carrying a mode-selection difference that the walls themselves caused.

**What this does to the premise.** The premise that `corr_e_z` is a stable, physics-carrying quantity holds under mesh refinement and FAILS under wall change, so `corr_e_z` can be used as an observable only within one wall set. That is acceptable for `C2b`, which changes the mesh at fixed walls, but it means `corr_e_z` cannot be used to compare the PEC and PMC pencils.

## Acceptance

A `C2b` run is only capable of falsifying something if both of the following hold.

* **`beta` criterion.** The reported `beta` change must exceed **`0.3993 %`**, the two-code floor on the same cross-section (`zfree_diagnosis.md` §7.2 item 3); below it the run cannot tell its own effect from cross-code disagreement, and the `eps` reading is judged at `0.8001 %`.
* **`corr_e_z` criterion.** `||corr_e_z|_patched - |corr_e_z|_baseline|` must exceed the Step 0 threshold, `3.1315e-4` absolute, against a noise level of `1.5657e-4`. The effect on the table is the PEC-vs-PMC shift, `0.147291446944630 - 0.119160432391342` = **`0.028131014553288`**, about **180x** the step-1/step-2 spread and 23.6 % relative: large enough that the measurement is *capable* of resolving it. That number is the *wall* term, measured at fixed mesh; it is not the term `C2b` varies, which is the mesh at fixed walls.

If Step 0 returns a floor within an order of magnitude of `0.028131014553288`, `corr_e_z` cannot carry the `C2b` argument on this box and the pre-registration must be rewritten around an observable with a floor below the effect.

## What would invalidate Step 0 itself

* **Mesh scatter as large as the effect being hunted.** If steps 1-3 span a range comparable to `0.0281`, then `corr_e_z` is a mesh-noise statistic on this box, the PEC-vs-PMC shift is uninterpretable, and `C2b` needs a different observable rather than a tighter tolerance.
* **The 51x19 extraction disagreeing with both existing points in one direction only**, which would say the two banked values are not replicates of one quantity.
* **A non-identical step 5**, which makes every other row a single sample with no dispersion and forces the extraction to be fixed before any floor is quoted.
* **A sign flip in `corr_e_y` between any two rows that is not uniform**, since the papered-over alternative -- comparing signed `corr_e_z` -- would then report a 0.238 difference where the magnitude axis reports `1.6e-4`.

## Fences

No solver modification. Step 0 changes meshes and walls only, never the physics, and never anything under `emfit/`: it reads banked caches and calls the diagnostic script and the PEC-variant script as they stand. No new solve is authorised except the PEC-walled variant at 31x17 if its cache is absent, and that run changes boundary conditions, not formulation. Nothing here re-opens `D1`, the attribution rule, or the `1e-12` guard (§7.3 item 3): Step 0 is a measurement of the statistic `C2b` will be judged on, not a patch.

**Fence -- the wall set is part of the observable.** `corr_e_z` is MESH-stable (0.13 % across 31x17 -> 41x22) but WALL-sensitive (~24 % for the same mesh with the three open walls closed). Every `C2b` run and every `C2b` comparison is therefore executed at FIXED walls. A `corr_e_z` value is not comparable across wall sets, and any `C2b` result quoted without its wall set is meaningless.

**Fence -- the station set is part of the observable.** Any C2b beta comparison must use the same station set as the baseline, station 0 included. The phaselag subset sweep shows that dropping station 0 moves beta by about 1 % on its own — station 0 sits 1.7 mm from the port, so the field there is evanescent-contaminated, and it is the outlier in every bad subset. One percent is the same order as several of the effects C2b exists to resolve. Change the station set and the comparison measures the change, not C2b.

## Amendment A1 -- 2026-10-27 -- the wall pair's mode identity, and closure of the `## Tolerance` wall item

**Standing of this section.** Appended, not inserted: the pre-registered text above stands exactly as written and is not edited here. The file's convention to date has been in-place edit plus a commit message (`e3837e4` original, `131f560` "wall tolerance measured at fixed mesh, not pending"); this item is appended instead, because what it settles is a caveat the measurement recorded rather than a prediction it falsified, and a pre-registration's prediction should not be rewritten after the fact. No solve was run for it: every number below is read from a file that already existed, and the only operation performed on them is the division printed beside it.

**Paths.** Written `out/...`, as elsewhere in this file; the resolved directory is `tools/host/c1-audit/out`, printed by the runs themselves (`out/pecbox_run.log:8`). From the repository root the bare `out/` holds only `refbox/`, so `out/` in this file always means the audit's own output directory.

**The two rows, as recorded.** Same code path, same 31 x 17 node mesh, walls the only change. `beta_sq` is `beta^2/k0^2`; `residual` is the audit's own eigen-residual, not a correlation error.

| run | row | col | `eps_eff` | `beta_sq` | `corr_e_y` | `corr_e_z` | residual |
|---|---|---|---|---|---|---|---|
| PMC, open top | `out/c1_table.txt:16` | 738 | `3.6295122080769704` | `9.7833058e4` | `+0.920770784811142` | `+0.119160432391342` | `4.035e-16` |
| PEC, closed box | `out/pecbox_table.txt:16` | 699 | `3.606094999644309` | `9.7201850e4` | `+0.912343044811209` | `+0.147291446944630` | `1.833e-15` |

Source per number: `eps_eff` and the eigen-residual from the full-precision solve lines, `out/run.log:27` and `out/pecbox_run.log:56`; `beta_sq`, `corr_e_y` and `corr_e_z` from the six-figure table rows, `out/c1_table.txt:16` and `out/pecbox_table.txt:16`, and at printed full precision from the verdict lines `out/run.log:49` and `out/pecbox_run.log:82`; magnitudes re-printed at `out/run.log:54-55` and `out/pecbox_run.log:88-89`.

**The wall sensitivity, in the pre-registered measure.** The measure is the one `## Tolerance` already fixes (line 33 above): the magnitude of `corr_e_z`, never the signed value (line 13), relative to the PMC member of the pair.

    S_wall = ( |corr_e_z|_closed - |corr_e_z|_open ) / |corr_e_z|_open
           = ( 0.147291446944630 - 0.119160432391342 ) / 0.119160432391342
           = 0.028131014553288 / 0.119160432391342
           = 0.2361  =  23.6 %

The numerator `0.028131014553288` is printed at `out/pecbox_run.log:88`; the audit's own REL_DELTA for the same pair prints `2.361e-01` at `:91`, arrived at independently inside the run. Both members are positive, so magnitude and signed value coincide for this pair and the magnitude convention at line 13 does no hidden work here. No absolute figure is mixed with a relative one in this section.

**Is the mode identity ambiguous?** No -- and the count alone does not settle it, the margin does. The open-top run printed exactly one propagating column (`out/c1_table.txt:7`; `out/run.log:34`, `:46`, `:61`), so it offered no choice at all. The closed-box run printed **two** (`out/pecbox_table.txt:7`; `out/pecbox_run.log:79`, `:102`), so it did offer one, and both candidates are recorded:

| col | `eps_eff` | `beta_sq` | `|corr_e_y|` | `|corr_e_z|` | `shape_pair_ok` | `eps_eff` distance from the open-top row |
|---|---|---|---|---|---|---|
| 699 | `3.606095` | `9.7201850e4` | `0.9123430` | `0.1472914` | True | 0.645 % |
| 704 | `0.280411` | `7.5584447e3` | `0.4264190` | `0.1209233` | False | 92.3 % |

(`out/pecbox_table.txt:16-17`; the same two rows, with `dominant = e_z` on both, at `out/pecbox_run.log:113-114`.) The runner-up is `92.3 %` away from the open-top mode on the `eps_eff` axis against the matched mode's `0.645 %`, a factor of about `143`, and it fails the audit's own shape screen (`|corr_e_y| >= 0.9 and |corr_e_z| <= 0.3`, `out/pecbox_table.txt:9`), which is why `N_PASSING_CORRELATION_SCREEN = 1` (`out/pecbox_run.log:119`). Note how the selection was actually made: by that screen, applied by the same code to both runs, and **not** by matching `eps_eff` after the fact. `eps_eff` proximity is only the post-hoc check that the screened mode is the same physical solution in both boxes, and it agrees to `0.645 %`.

**Consequence for the caveat at line 35.** Line 35 above says the shift is "a wall effect carrying a mode-selection difference that the walls themselves caused". The first half is measured and stands. The second half must not be read as an identification uncertainty that could be subtracted from `0.2361` to leave a "pure" wall term: there is no competing identification to subtract, the only other propagating solution being `92.3 %` away in `eps_eff` and failing the same screen that admits the matched one. The `0.645 %` `eps_eff` shift is therefore not an uncertainty *in* the wall term; it is part of the wall term, produced by closing the lid. Recorded as an observation and not as a mechanism: the closed-box value moves toward the analytic profile's own `eps_eff = 3.3500085193372118` (`out/run.log:32`); nothing here establishes that this is why it moved.

**What this does to the pre-registered number.** Not numerically. The pre-registration states the wall sensitivity as `23.6 %` at line 33 and as `~24 %` at line 59; this amendment re-reads the same two recorded rows and returns `0.2361` = `23.6 %`, and no tightening is claimed or available. What changes is the standing of the item. `## Tolerance` recorded the pair as carrying a mode-selection difference left unresolved; it is resolved here, with a factor of about `143` in `eps_eff` between the matched mode and the only alternative. The `## Tolerance` wall item is **CLOSED AS MEASURED**: `23.6 %` at fixed mesh, unambiguous identification, and no second wall configuration is required to quote it, because nothing in `C2b` compares wall sets (line 59). Said plainly, because the word "bound" has been used of this number: `23.6 %` is a measured shift on one box, one mesh, one pair of wall sets. It is not a statistical bound, it carries no error bar, and nothing recorded here can tighten or loosen it.

**What this does NOT establish.**

* **One mode pair on one mesh is not a convergence study.** Nothing here re-runs the closed box on 41x22 or 51x19, so the `23.6 %` inherits exactly the mesh scatter of its own row, the `0.13 %` at line 29, and no more. A wall term that varied with mesh would not be visible in this data.
* **A single propagating mode on the open-top side means no mode-identity statistics exist.** One candidate on one side and two on the other is a count, not a distribution; the `~143` factor is one comparison, not a typical margin, and it says nothing about whether other wall perturbations would produce competing modes.
* **Nothing here was re-solved.** All figures come from `out/c1_table.txt`, `out/pecbox_table.txt`, `out/run.log` and `out/pecbox_run.log` as they stand; the only operation performed was dividing two recorded numbers. In particular, `REPRO overall: FAIL` (`out/pecbox_run.log:92`) is the closed-box run being scored against open-top anchors, and is annotated as such by the run itself (`:129-132`); it is not evidence about this pair and this amendment neither reassigns nor excuses it.
* **Nothing here licenses a `corr_e_z` comparison across wall sets** (line 59), and nothing here makes `corr_e_z` a PEC-vs-PMC observable. The item closed is the wall tolerance at fixed mesh; the premise at line 37 continues to hold as written.

