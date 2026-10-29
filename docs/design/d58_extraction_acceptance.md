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

## 8. Location and provenance

This document was first committed at `docs/design/d58_acceptance.md`. That path was already occupied: it carries another dispatch's acceptance document (a component-map / staleness-mechanism task, committed at `9cece7b`), so the instruction to write this file at that path was a collision rather than a free slot. The collision was found after the fact, the other document was restored byte-for-byte from `9cece7b`, and this document moved to its present path in the same change. The acceptance criteria above are unchanged by the move. The collision is itself a disagreement between the brief and the artifacts and is recorded as such in the close-out.

## 9. Dispatch 58.1 acceptance criteria (frozen before measurement)

Provenance tags: [ARTIFACT] = read from a file in this repository; [MEASURED] = computed by a validated run and recorded in this document; [ARCHIVE] = quoted from the user's brief; [DERIVED] = algebra on the above; [PROPOSED] = invented here, not in the record. No line numbers (R6). The artifact wins over this document.

### 9.0 Erratum: R's formula, as stated in the D58 status report (my error, #34)

The D58 status report, and the D58.1 brief after it, wrote `R = sum(e_y**2)/sum(e_z**2)`. That is inverted.

- [ARTIFACT] tools/host/c1-audit/c1_audit.py accumulates `energies.append((float(np.sum(e_y ** 2)), float(np.sum(e_z_vv ** 2))))` and then forms R_by_col as `ez / ey` per column. Therefore **R = sum(E_z**2) / sum(E_y**2)**.
- [DERIVED] The numerator sums E_z over the staggered cell-centre-in-z lattice (201 x 76 = 15276 samples); the denominator sums E_y over the Yee lattice (200 x 77 = 15400 samples). The two sums are over different sample counts and different z-measures.
- [ARTIFACT] The analytic identity asserted in the comment at the point where A_ez is read is the same orientation, `sum(A_ez**2)/sum(A_ey**2)`. The comment is the only place it appears; no code computes it.
- No measured number in D58 changes: 4.0489791163950715 was produced by the code, not by the prose. But every direction-of-effect argument must be redone against the corrected formula, which 9.2 does.
- Standing rule added: a formula quoted out of code is checked against the assignment of the output variable, not against the accumulation tuple. That is exactly the error made here.

### 9.1 Task 1 acceptance: what R is supposed to measure

Verdict is exactly one of three, each supported by quoted tokens:

(a) an energy ratio. The quotes must contain a permittivity factor or an explicit 'energy' characterisation applied to the sums. If the record says R is an energy ratio, the estimator is required to carry eps, and Task 3 proceeds as written.
(b) a field-shape ratio. The quotes must characterise R as a shape or amplitude quantity and must not attach eps. Then the eps correction is out of scope for Task 3 and must be reported as out of scope rather than silently performed.
(c) no stated definition. The honest verdict if no document states the quantity, only the formula.

Searched locations, with hit and absence counts reported per location: every file in docs/design/ (t4_amp_ratio.md and the routeC design documents named explicitly), decisions.md, docs/report/*.tex, and the docstrings and comments in tools/host/c1-audit/ and tools/host/sparse-probe/.

If (c): a definition is proposed and argued, and the proposal must state (i) what physical quantity R proxies, (ii) why that quantity is the right comparator for the analytic deposition, (iii) what measurement would refute the proposal. A proposal that no measurement could refute is not acceptable.

### 9.2 Task 2 acceptance: the eps-weighting test, pre-registered

Frozen definitions:

- eps(z) = 4.4 for z < 0.0016, 1.0 for z > 0.0016 [ARTIFACT .scratch/tol/logs/TOLFLUX.json: eps_r = 4.4, air = 1.0].
- f_y = sum over substrate z of E_y**2, divided by the full sum of E_y**2. f_z likewise for E_z. Each computed on its own lattice with plain np.sum and no measure, so that f is a pure distribution statistic.
- R_eps = sum(eps * E_z**2) / sum(eps * E_y**2), plain sums otherwise.
- [DERIVED] R_eps/R = (1 + 3.4 f_z)/(1 + 3.4 f_y). Therefore **R_eps < R iff f_z < f_y**, exactly, with no further assumption.

That biconditional is the pre-registered claim. It replaces the brief's bare 'eps-weighting can only reduce R'. That sentence holds only under f_z < f_y, and the brief does not establish it: it is what is being measured. If the measurement falsifies the brief's direction, the brief is wrong and the arithmetic is not.

Also registered [PROPOSED, to be checked, not assumed]: E_y carries the quasi-TEM displacement under the strip and should therefore be substrate-heavy, f_y well above f_z, so R_eps < R is expected. The magnitude is not registered.

Must report: f_y, f_z, R0, R_eps, R_eps/R0, and delta R_eps = R0 - R_eps.

Validation hook, non-negotiable: the reconstruction must reproduce R0 = 4.0489791163950715 bit-exactly before any eps-weighted number is reported. If it does not, stop; a ratio derived from the wrong field is not reportable.

Interface ambiguity: the z-node at z = 0.0016 belongs to the E_y lattice and lies exactly on the interface. f_y and R_eps are therefore reported twice, once with that node assigned to the substrate and once to air, with the spread stated. It is the one genuinely ambiguous assignment in the calculation.

### 9.3 Task 3 acceptance: the decomposition (the deliverable)

Three corrections, each reported alone and then cumulatively in this frozen order:

1. eps only: R_eps as in 9.2.
2. measure only: R_m = sum(w_z * E_z**2)/sum(w_y * E_y**2), no eps, where w are dual-cell area weights on the non-uniform z-axis [MEASURED: substrate z-cells 0.2 mm, air z-cells 0.5 mm]. Rationale [DERIVED]: the dual length of a Yee sample is the z-spacing around it, and omitting it over-weights the fine (substrate) side by 2.5x.
3. lattice only: bring both sums onto a common sampling. Accepted implementation is the co-located staggered pairs, i.e. both components at z-cell-centres with E_y reduced to z-centres, with no interpolation across the interface. Any cross-interface interpolation is reported as a separate variant with its own number, because interpolating across a 4.4 jump is itself an error source.
4. all three together, interface-aware.

Then report: corrected R; corrected Q = R / 2.8101021387524523; and the band test. Q lies inside [2.52909192487721, 3.09111235262770] iff R_corrected <= 3.09111235262770 [DERIVED: the band is R_REGISTERED x [1 +/- 0.10]].

The deliverable: for each of the three corrections, delta R and its share of the gap G = R0 - R_ANALYTIC = 4.0489791163950715 - 2.8101021387524523 = 1.2388769776426192, as a percentage of G. The shares plus the residual must account for G. Convention frozen here: the interaction term is assigned to the last correction applied and is reported explicitly as interaction, never silently absorbed.

The equivalent requirement, to be quoted and tested rather than paraphrased: the corrections must remove at least 23.66% of R0, equivalently at least 77.4% of G, for corrected Q to enter the band. 'It got closer' is not a result.

A negative decomposition is a legitimate result and is reported as such, with the sign of each delta R.

### 9.4 Task 4 acceptance: the jump test, redesigned

- Mask, frozen: interface-adjacent rows only, meaning rows whose y lies outside the strip span y in [0.0085, 0.0115] (strip centre row 100 at y = 0.01, strip width 0.003) [MEASURED]. The span is excluded because under the conductor E_t = 0 dominates and the normal-component jump there is not the quantity under test.
- Quantity: J1 = |E_z(k=16)| / |E_z(k=15)|, the two z-cell-centres straddling the interface.
- Expectation: **4.4**, from eps_r = 4.4 and air = 1.0 [ARTIFACT]. 3.6 is eps_eff and is not the expectation; the D58 brief's 3.6 was error #30 and is retired here.
- Report: median and interquartile range of J1 over the masked rows, d = |median/4.4 - 1|, the masked row count, and the in-strip count for completeness. Report row 86 (strip edge) separately and flag it as an edge row.
- Agreement verdict requires |median/4.4 - 1| <= 0.10, the same 10% convention as the Q band.

### 9.5 Close-out requirements

docs/design/d58_closeout.md contains, in this order: (1) R's definition, or the finding that it has none, with the search table; (2) f_y, f_z and the eps verdict tested against the 9.2 biconditional; (3) the 9.3 decomposition with numbers; (4) the 9.4 jump under the frozen mask; (5) a disagreements section listing every point where measurement contradicts the D58.1 brief, the D58 brief, or my own earlier reports, each with the contradictory sentence quoted; (6) a fence statement naming every file touched.

### 9.6 Fences for 58.1

docs/design/d58_acceptance.md belongs to the other agent and is not written by me. decisions.md belongs to the other agent. viz/ is fenced. emfit/ is untouched except what Task 3 strictly requires, and none is expected: all three corrections are re-reductions of persisted arrays. New work lands in tools/host/c1-audit/ and docs/design/d58_closeout.md only. Commits are selective by path, never all-path.

## 10. D58.2 acceptance criteria: the jump in the solver's own discretisation, and whether it converges

### 10.1 Scope

D58.2 measures ONE thing: the vertical electric field `e_z` on the solver's own
output, immediately below and immediately above the dielectric interface, as a
ratio against the eps contrast 4.4, and then whether that deficit shrinks as the
mesh is refined. It is a question about the discretisation, not about the
estimator. D58.2 does NOT re-open the estimator question: per section 9 of
`docs/design/d58_closeout.md`, the three corrections to the extraction are
finished and their residual (the ~44% offset) is a separate, still-open problem.
No new estimator, no new operand, no re-derivation of R is in scope. This section
is written BEFORE any field value is loaded: every `result` cell below is
`PENDING`, and the interpretation table in 10.3 is fixed now, in advance.

### 10.2 Criteria

| id | criterion | bar | result |
| --- | --- | --- | --- |
| T1 | Measure `e_z` just below and just above the interface on the solver's own banked eigenvectors; report the ratio below/above against eps_r = 4.4 | The under-jump is stated as a percentage with its own uncertainty (an interval, not a point) | PENDING |
| T2 | Determine the element space that `e_z` actually lives on, and derive the smearing the actual basis must produce | A predicted under-jump percentage, falsifiable, written down BEFORE T3 runs | PENDING |
| T3 | Convergence test of the measured under-jump at three or more resolutions of the same ladder | Whether the under-jump shrinks with h, and at what rate: a fitted exponent with a standard error | PENDING |
| T4 | Replace the exact-float REPRO equality in the audit with a relative tolerance that is derived, not chosen | Tolerance derived in the document, and the count of banked statuses that flip reported | PENDING |
| T5 | Commit the field artefacts that viz panel 1 needs | A provenance line for each committed artefact, and the tier that becomes eligible | PENDING |

On T2 the predicted number is `derivation deferred to T2 execution` until the
space is read out of the code; no number is pre-registered here that the code has
not yet been shown to imply. If a continuous (P1) basis is confirmed, the
derivation to be reported is the standard nodal smearing: a nodal P1 field
carries the interface value as a weighted average of the two one-sided limits, so
on a uniform mesh the first node off the interface sees a fraction of the jump
proportional to the distance to that node divided by the cell size, and the
under-jump is that fraction of the full 1 - 1/eps_r contrast. The two lines of
algebra and the resulting percentage belong in T2's own record, not here.

### 10.3 Pre-registration: what each outcome will mean

The discriminator is T3's fitted exponent `p` in `under-jump ~ C h^p`. Exactly
one of the following three rows is the interpretation, and the row is chosen by
the fitted value alone, not by which answer is convenient.

| observed | fitted exponent | pre-registered interpretation |
| --- | --- | --- |
| under-jump shrinks with h | `p` consistent with 1 or 2 (O(h) or O(h^2)) | DISCRETISATION: the jump converges away, 13.85% is a mesh artefact of the sampled lattice, and the residual 44% offset is a separate solve defect, not a basis limitation |
| under-jump constant | `p` consistent with 0 (interval covering 0) | STRUCTURAL: the formulation cannot represent a discontinuous normal component, the jump never converges, and the remedy is a different unknown (D_z = eps_r E_z, the continuous one) or an interface-aligned mesh - not more refinement |
| e_z found on a discontinuous basis | T2 fails its own premise | T2 is VOID and the under-jump is a solve defect; T3 then measures solver convergence rather than basis representability, and the 10.2 T2 row is scored as void, not as pass |

The interpretation is fixed HERE, before T1 and T3 are computed. Any later
revision of this table must be recorded as an ERRATUM appended to this section
(section 9.0 is the precedent), never as an edit to the rows above.

### 10.4 Why the test is cheap

Every rung of the ladder already has its eigenvectors banked:
`tools/host/sparse-probe/out/rung{0..4}_*/c1_spectrum.npz`, each with 38 keys
including `vecs_real` (all eigenvectors), `free_e`, `free_n`, `xs`, `zs` (which
alone rebuild the mesh), `k0`, `f0`, `beta` and the metric arrays. No solve is
needed to obtain `e_z` on any rung: only the mesh rebuild, the mixed assembly and
a sparse LU back-substitution for the longitudinal block. The analytic references
`A_ey` and `A_ez` in those files are references, not solver output, and are not
what T1 measures. Re-solving rung 4 is out of scope for D58.2 without explicit
authorisation from the author: the rung-4 artefact is 738,560,423 bytes and its
eigenvectors are already banked.

### 10.5 Fences for 58.2

Work lands in `tools/host/` and `docs/design/d58_*` only. `emfit/` is untouched
unless T2 proves that a basis change is actually needed, and that is reported to
the author BEFORE anything in `emfit/` is touched. `viz/`, `decisions.md` and
`docs/design/d58_acceptance.md` belong to another agent and are not written by
me. Scratch goes in `.scratch/`. Commits are selective by path, never all-path.
