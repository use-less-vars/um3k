# Dispatch 58 — acceptance criteria

**Frozen before any code for dispatch 58 is read.** This file is the contract. Where this file and a later artifact disagree, the artifact wins, and the disagreement is recorded in the close-out rather than silently reconciled.

Scope: four tasks, in the order given. Task 4 is gated on the first three.

## 0. Standing rules

- **R1 — artifact wins.** No claim about project state from memory, from a previous dispatch, or from the brief. Every such claim is read from a file, and the file is named.
- **R2 — searched absences are stated as searches.** "X does not exist" is only admissible as "zero occurrences of X across these N named files, binaries skipped by size". Bare "I don't see it" is not evidence.
- **R3 — provenance tiers, on every number.** `[MEASURED]` (produced by a run whose output is on disk), `[ARTIFACT]` (read out of a source or log file, quoted), `[RELAYED]` (asserted by the dispatch brief and not yet verified here), `[ABSENT]` (searched for and not found, per R2), `[INFERRED]` (reasoning, not observation). A number without a tier is a defect.
- **R4 — freeze.** `docs/design/t4_amp_ratio.md` stays frozen and is not edited, even where it is contradicted by code. `viz/` stays fenced and uncommitted. `component_map.md` and any `d58_*` file other than this one belong to another agent and are not written to.
- **R5 — no post-hoc estimator choice.** Every statistic in this dispatch has its estimator named in this file before the data is seen. A better estimator that occurs to the analyst later is reported as an addition, not substituted.
- **R6 — no line numbers in briefs.** Code is referenced by file, symbol and quoted text, never by line number.

## 1. Task 1 — the interface-jump test

Hypothesis `[RELAYED]`: `E_z` is normal to the substrate interface and jumps by a factor of the permittivity ratio there; a surface integral of `E_z**2` that straddles that discontinuity without respecting it is systematically biased, and that bias is the +27% to +44% offset recorded in the 57c close-out.

The hypothesis has a predicted number and can fail.

- **T1.1** Report the interface location and the permittivities on each side, quoted `[ARTIFACT]` from the geometry/profile inputs, with the file named. The expected jump ratio is `eps_substrate / eps_superstrate` from those inputs. It is **not** to be taken as 3.6 by assumption, even if 3.6 is the expected answer.
- **T1.2** The expected jump ratio is **stated and committed before the measurement is made**, in the task log, in this dispatch's own working notes.
- **T1.3** Measure `E_z` on the audit's own sampled lattice (`_ezc_pts`, the `(x, y) = (XS, ZS)` order lattice), on the rung-0 mesh, and report the profile across the interface. Estimator **J1**, fixed now: the ratio of `|E_z|` at the first node above the interface to `|E_z|` at the last node below it.
- **T1.4** Estimator **J2**, fixed now, as a robustness check only: linear extrapolation to the interface from the two nearest nodes on each side, same ratio. J2 is reported and is not decisive on its own.
- **T1.5** Report whether the quadrature used for the surface integral crosses the interface; if it does, how many quadrature points span the discontinuity, and whether the lattice places the interface at a node, between nodes, or is staircased.
- **T1.6 Decision table, pre-registered.** Let `d = |J1 / (eps_substrate/eps_superstrate) - 1|`.
  - `d <= 0.10` -> **consistent**: the jump is physical; the extraction is not implicated by this test.
  - `0.10 < d <= 0.50` -> **inconclusive**: report J2; do not claim either way.
  - `d > 0.50` -> **inconsistent**: `E_z` does not jump where physics requires, the extraction is implicated, and everything downstream of the extracted ratio is void until that is fixed.
- **T1.7 The decisive test of "explained".** Recompute both sums — the reference sum from the deposited profile and the solved sum from the eigenvector — with interface-aware quadrature that splits the integral at the interface, and report the resulting `R` and `Q` at rung 0. The offset is **explained** only if the corrected `Q` falls inside the band, and the fraction of the offset accounted for is stated as a number. Anything else is **not explained**, whatever the jump ratio says.
- **T1.8** Report the corrected `R_ANALYTIC` alongside the registered literal. If interface-aware quadrature changes the reference, that is a finding about the reference and must be reported as one — the ruler test in 57c established that the literal is reproduced exactly from the deposited profile, not that the deposited profile's own quadrature respects the discontinuity.

**What Task 1 may not conclude:** that the field is wrong. T1 measures an extraction property. A consistent jump implicates the extraction; an inconsistent jump implicates the solve; neither establishes the other without T1.7.

## 2. Task 2 — the certification operand

Design only. **No implementation in this dispatch.** The pre-registration has to be rewritten, not patched.

- **T2.1** State what the control gate presently certifies, and say plainly whether that is correctness or self-consistency with a historical artefact. The 57c finding `[MEASURED]` is that the anchor operand sits 4.41x the band half-width from the analytic reference, so a control pass and a band pass are mutually exclusive. That finding is the premise of this task and is not re-litigated.
- **T2.2** Enumerate at least three candidate replacements and argue each: (a) control against an independently computed analytic `R`; (b) control against a different independently known-correct case; (c) retire the control gate and rely on the band alone; (d) any further candidate the evidence supports.
- **T2.3** For each candidate, state what failure it would catch and what failure it would miss. A candidate that catches nothing is reported as such.
- **T2.4** Recommend one, with the recommendation separated from the argument so a reader can disagree with the conclusion without redoing the work.
- **T2.5** State explicitly what the recommendation would require to be re-registered, and whether it invalidates any banked rung.

## 3. Task 3 — run the sparse path for real

- **T3.1** Identify what currently forces `C1_ALLOW_DENSE_ABOVE_MAX=1`, quoted `[ARTIFACT]`, and what the cap would have to be raised to.
- **T3.2** Run the ladder through the actual sparse route — `splu` + `LinearOperator` + `eigsh`, the path the probe measured at 9604 edges — with no dense fallback active.
- **T3.3** **Prove per rung that the run was sparse**, from the run's own output — the dense banner must be absent, the environment variable unset, and the code path attested in the log. A sparse claim not backed by per-rung proof is a false close (see §6).
- **T3.4** Per rung, report: free edges, dense-or-sparse, factorisation time, `nnz`, peak memory, residual on both pencils, and `beta`. A missing field is reported as missing, not omitted.
- **T3.5** Pre-registered tolerance for "sparse reproduces dense": relative eigenpair residual `<= 1e-10` **and** relative `beta` agreement `<= 1e-8` against the banked dense value. Both are required; agreement in `beta` alone with no residual is not a reproduction claim.
- **T3.6** If the sparse path cannot run at some rung, report the failure mode and the rung. Inability to run is a finding. It is not a licence to extrapolate from the rungs that did run.
- **T3.7** Report each rung as one of: reproduces dense within tolerance, disagrees, or did not run. No aggregate verdict over the ladder until every rung has one of those three labels.

## 4. Task 4 — order p, gated

- **T4.1** Runs only if all three of the following hold: Task 1's verdict is **consistent**; Task 2 delivered a proposal (T2.1-T2.5 all answered); Task 3 labelled every rung and, where it reported a divergence, reported it as a finding rather than a workaround.
- **T4.2** If Task 1's verdict is **inconsistent**, Task 4 must not start. An order measured through an extraction that is implicated is void.
- **T4.3** Order p is measured against `order_p_preregistration.md`, amended by 57b's Task 0 if that landed. If the pre-registration is absent or unamended, report that and stop — do not substitute a fresh derivation for the frozen one.
- **T4.4** Report the fitted order with its confidence interval and the mesh range used. A single-mesh slope is not an order.

## 5. Close-out requirements

The close-out document must contain, in this order:

- (a) The jump table: expected ratio, J1, J2, `d`, and the T1.6 verdict, with the interface location and permittivities quoted `[ARTIFACT]`.
- (b) The T1.7 recomputation: corrected `R`, corrected `Q`, the fraction of offset accounted for, and an explicit statement that the 27-44% offset is **explained**, **eliminated**, or **still open**.
- (c) The operand proposal (T2.1-T2.5), marked design-only.
- (d) The per-rung sparse-vs-dense table, with the per-rung sparsity proof of T3.3.
- (e) **Every disagreement** between this brief and the artifacts, dispatch-said versus artifact-says, with tiers. The 57c close-out recorded nine; that is the expected order of magnitude, not a ceiling.
- (f) Whether Task 4 ran, and if not, which of T4.1's three conditions failed.

## 6. False closes, to be avoided and then declared avoided

1. **"Offset explained" without T1.7.** The jump ratio alone never explains an offset; only the recomputed `Q` inside the band does.
2. **A jump decision made with an estimator chosen after seeing the profile.** J1 and J2 are fixed in §1; any other estimator is an addition.
3. **"Route C validated" from a run that silently went dense.** Requires T3.3 per-rung proof.
4. **"Sparse works" from `beta` agreement alone.** Requires residuals too (T3.5).
5. **Implementing the new operand inside this dispatch.** Task 2 is design only.
6. **Quoting any `[RELAYED]` figure from the brief as measured.** The predicted jump is `[RELAYED]` until T1.3 runs; the `2.3e-18` residual and the station-fit values remain `[RELAYED]` and `[ABSENT]` from 57c.
7. **Order p reported from a run that started before Task 1's verdict.** T4.1/T4.2.
8. **Any claim about project state that was not read from a named artifact.** This is the 57c failure mode, twenty-eight times over: the offset was asserted, the worst rung was asserted, the station fit's path was asserted, and the sparse path's execution was asserted, and none of the four had been read. R1 and R2 exist for this.

## 7. Out of scope

This dispatch does not: fix the extraction, write the new operand, land the sparse route, close Route C, or produce a physics verdict on the solved field. It produces three answers to three questions and one gated order measurement, each with a pre-registered decision rule.
