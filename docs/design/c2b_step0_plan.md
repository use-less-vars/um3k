# `C2b` Step 0 -- `corr_e_z` against strip-edge refinement alone

1. **What Step 0 measures.** The response of `|corr_e_z|` to refinement of the strip-edge cell size only.
   `h_edge` throughout is the cell dimension immediately adjacent to the strip edge; it is the single
   independent variable, and every other length scale in the mesh stays at its baseline value.

2. **Held fixed -- and why each.**
   - `h_bulk`, the bulk cell size. The bulk is not a candidate cause, and moving it would fold the
     already-banked 31 x 17 -> 41 x 22 spread back into a test of the edge.
   - Box dimensions. `corr_e_z` is measured against a fixed analytic basis; a different box is a
     different problem.
   - **The wall set**, all three open walls (`wall_y=0mm`, `wall_y=20mm`, `wall_z=7.6mm`) present in
     every step. `corr_e_z` is mesh-stable (0.13 %) but wall-sensitive (23.6 %), so it is only
     comparable within one wall set; one wall set for the whole ladder is what makes a step-to-step
     difference attributable to `h_edge` rather than to the walls.
   - Frequency and port. Both move `beta` and `eps_eff`, which enter the same comparison; changing
     either would be a second variable.
   - The station set and the station count. The pre-registration's station-set fence records that dropping
     station 0 moves `beta` by about 1 % on its own (1.7 mm from the port, evanescent-contaminated), so the station geometry has to be the baseline's.

3. **The ladder -- ESTIMATE, to be confirmed against the builder before any run.**

   | step | `h_edge` (fraction of `h_bulk`) | refinement factor vs step 0 | nodes / triangles |
   |---|---|---|---|
   | 0 | 1.0 (baseline 31 x 17 grid) | 1 | 527 / 960 as banked (`out/pecbox_run.log:36`) -- **cited, not recomputed** |
   | 1 | 0.5 | 2 | **UNKNOWN -- not computed** |
   | 2 | 0.25 | 4 | **UNKNOWN -- not computed** |
   | 3 | 0.125 | 8 | **UNKNOWN -- not computed** |

   **Table 1 is ESTIMATE only: no mesh in it has been built, and not one count for steps 1-3 is
   known.** Those cells are deliberately left `UNKNOWN` rather than filled with a plausible-looking
   integer. The values that have to be read off the existing builder -- `structured_mesh(XS, ZS)`,
   `tools/host/c1-audit/c1_audit.py:266-268` -- for the modified axis vectors are: the realised
   `h_edge`, and the node / triangle / edge triple it produces. The single known triple, 527 / 960,
   is quoted from the banked PEC-box log and is not re-derived here. Read the builder first; if it
   cannot realise a step, drop that step and say so, do not substitute one.

4. **Falsifier, stated before any result exists.** Take `F = 1.5657e-4` as the measured mesh floor
   and `2F = 3.1315e-4` as the detection threshold, both from `docs/design/c2b_preregistration.md`
   (`## Tolerance`, line 29; the threshold is also the `corr_e_z` criterion at line 44). Then:
   **if `| |corr_e_z|_step i - |corr_e_z|_step 0 |` does not exceed `3.1315e-4` at any step of the
   ladder, `C2b` is falsified and the low `e_z` correlation is not strip-edge resolution.** The
   falsifier is one-sided, and the asymmetry is the point: movement above `2F` does **not** confirm
   strip-edge resolution -- at fixed walls it is equally consistent with any other mesh-sensitive
   defect, including a wrong analytic reference (item 8).

5. **Acceptance.** The deliverable is the `|corr_e_z|` trajectory against refinement factor --
   every step tabulated, no single best value reported on its own -- together with the same
   trajectory for `|corr_e_y|` as a control. The control does real work: a `corr_e_y` trajectory that
   also moves materially would show the movement is not specific to `e_z`, and would dissolve the
   only localising evidence the diagnosis currently has (`zfree_diagnosis.md` §7.5: `corr_e_y` ~0.92
   against `corr_e_z` ~0.12 on the same column). Magnitudes only; signed values are not comparable
   across meshes.

6. **Station-0 fence.** The first station plane sits in the source's near field and is never the
   refinement probe and is never quoted alone. The statistic is computed on the fixed station set as
   a whole, station 0 included, exactly as the baseline computes it.

7. **Cost -- ESTIMATE, and nothing here is measured.** 3 solves if step 0 is taken from its banked
   cache, 4 if the baseline is re-solved as the first row of the ladder; one solve per step, no
   parameter sweeps.
   - Cell counts: **ESTIMATE**, not computed. The baseline carries 960 triangles at 31 x 17
     (banked). Steps 1-3 add cells only along the strip edge, by an amount that depends on the
     strip-edge cell fraction and cannot be calculated without reading the builder.
   - Wall-clock: **ESTIMATE**, not measured. No solve was timed in this planning pass, so no minutes
     figure is quoted here at all -- read the per-solve elapsed time off the banked run logs
     (`out/run.log`, `out/pecbox_run.log`) before any cost is published, and the ladder is 3-4 times
     that.

8. **What this plan does not establish.** It does not touch the analytic array's normalisation, which
   is a separate open item: the plane-placement function (`M.plane_mode`, `emfit/modal.py:267`) copies
   the array through the slices it returns and does not renormalise it, so nothing here makes the two
   sides commensurable in amplitude. It does not vary the wall set, so it produces no wall term and
   its numbers are not comparable across walls. And it cannot separate mesh error from a wrong
   analytic reference: if the analytic `E_z` is wrong, a flat trajectory is as consistent with that
   as with convergence.

9. **Fences.** No `emfit/` edits. No gate runs. No run of any kind at design time. Every number in
   this file is either quoted from a banked log or marked ESTIMATE, and some of those are marked
   UNKNOWN on purpose. Nothing in this document is a result.
