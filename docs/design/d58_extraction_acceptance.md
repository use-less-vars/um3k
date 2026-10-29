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

## 10.6 ERRATUM (appended before T1 step 0, before any field value is loaded)

Clause 10.3 required that any revision of this pre-registration be recorded as an
ERRATUM appended to this section, never as an edit to the rows above. This is that
erratum. It was written after sections 10.2 and 10.3 were committed (db5a9ec) and
before any field value was measured. Sections 10.2 and 10.3 stand unedited. What
follows pre-registers a fourth outcome, pins a direction convention and a naming
convention, amends the T1 measurement definition, re-aims T2, and bounds what T3
is allowed to claim.

### 10.6.1 The direction convention, pinned

The normal component of D is continuous across the interface,
eps_below * E_below = eps_above * E_above. The dielectric occupies the region
below the interface with eps_below = 4.4, and air occupies the region above with
eps_above = 1.0. Therefore

    E_below / E_above = 1 / 4.4 = 0.2273
    E_above / E_below = 4.4

The quantity compared against 4.4 is E_above / E_below: the interface-normal
component just above the interface, divided by the same component just below it.
T1 reports BOTH orientations. Writing "the ratio against 4.4" without naming the
orientation is a factor-of-4.4 defect and is not permitted in this document.

### 10.6.2 The quantity named by role, not by letter

Three naming systems collide in this codebase. m2.structured_mesh(XS, ZS) makes
the SECOND coordinate the height. mode2d's longitudinal field e_z is the
PROPAGATION direction. And e_at(...)[...,1] is the height component. The "z" in
corr_ez_vv therefore does not denote the same object as the "z" in e_z.

The component compared in this test is the one NORMAL TO THE INTERFACE,
e_at(...)[...,1] * CELL, the second cross-section coordinate. The longitudinal
field mode.e_z is TANGENTIAL to the interface and is not part of this test: it
must be continuous, and a jump of 4.4 must not be sought in it. A reader who
resolves "e_z" by letter measures the wrong field, obtains a ratio near 1.0, and
concludes that the physics is broken.

### 10.6.3 T1 amended: three constructions, and the control

For each rung, T1 reports THREE ratios of the same component, each in both
orientations:

  (a) metric-lattice one-row-either-side. The reporting grid is 201 x 76 over
      20 x 7.6 mm, so dy = 0.1 mm, and the interface falls on row 16 exactly.
      This is the construction corr_ez_vv already lives on.
  (b) mesh one-cell-either-side. Here delta = dz, which shrinks across the
      ladder: 2.0e-4, 1.6e-4, 1.333e-4, 1.143e-4, 8.0e-5 m.
  (c) extrapolated one-sided limits. The interface value from below and the
      interface value from above, each obtained by extrapolating from the two
      samples on its own side. THIS IS THE PRIMARY NUMBER.

Each of (a), (b) and (c) is computed identically on corr_ez_vv (the solver's
extracted field) and on A_ez (the exact analytic field).

The measured quantity is not E(h - delta) / E(h + delta) itself. To first order
that ratio is

    E(h - d) / E(h + d) ~ [ E(h-) / E(h+) ] * (1 - delta / L_below - delta / L_above)

so it carries a physical term proportional to delta on top of whatever
discretisation error exists. And delta is fixed by the construction, not by the
solver: on the metric lattice delta is 0.1 mm on every rung and does not shrink
at all, while on the mesh delta = dz shrinks by a factor of 2.5 across the
ladder. The same solver therefore yields a constant deficit (fitted exponent ~ 0,
which 10.3 scores as STRUCTURAL) or a shrinking deficit (fitted exponent ~ 1,
which 10.3 scores as DISCRETISATION) purely according to which lattice is read.
Constructions (a) and (b) are reported in order to DEMONSTRATE that dependence.
Neither is interpreted.

The discrimination quantity, stated once so that there is no ambiguity later:

    The only number whose h-dependence means anything is the
    solver-minus-analytic residual, computed identically on both
    fields, at the extrapolated one-sided limits of construction (c).

Neither absolute deficit qualifies.

### 10.6.4 Fourth outcome, pre-registered: the sampling artefact

| observed | condition | pre-registered interpretation |
| --- | --- | --- |
| the solver-minus-analytic residual of construction (c) is consistent with zero at every rung | the residual interval covers zero across the whole ladder | SAMPLING ARTEFACT: there is no under-jump defect. The deficit seen in the naive constructions is the physical variation of the mode across one sampling step, and the exact analytic field reproduces it under identical sampling. The 13.85% under-jump claim recorded in D58.1 is WITHDRAWN as an erratum. The T1/T2/T3 line measured a sampling convention, and the ~44% R offset requires an entirely different explanation. |

This outcome is live, and it is the one that matters most, because it would mean
two dispatches were spent on an artefact while the real offset sits unexplained.
It is pre-registered here, before the measurement. It takes precedence over both
rows of 10.3 whenever its condition holds.

### 10.6.5 T2 re-aimed: the Nedelec normal component

The measured component lives in the first-order Nedelec (Whitney) space of e_t,
not in the continuous P1 space of the nodal longitudinal field. Across an
interior edge the Nedelec space constrains the tangential component and leaves
the normal component unconstrained, so a normal jump of 4.4 is REPRESENTABLE by
this basis. Moreover R3 established that the interface coincides with a mesh line
on all five rungs (HSUB/dz = 8, 10, 12, 14, 20, residual exactly 0), so no
triangle straddles the interface and eps_r evaluated at the triangle centroid is
exact everywhere. The eps-misassignment hypothesis is therefore dead, and with it
the reading of the under-jump as P1 nodal smearing.

T2's target is the smearing that the Nedelec basis actually produces for the
normal component. The standard nodal P1 smearing derivation is retained in this
document only as a note recording why it does not apply: it addresses the wrong
space for this component.

### 10.6.6 T3's resolving power, stated before it is used

dz spans 2.0e-4 to 8.0e-5 m, a factor of 2.5, over five rungs (interface node
index 8, 10, 12, 14, 20). A fitted exponent over that span will carry a standard
error of order 0.3. That is enough to separate p ~ 0 from p ~ 1, which is the
discrimination 10.3 asks for. It is NOT enough to certify a rate, to distinguish
p = 1 from p = 2, or to support any statement of the form "converges at first
order". No such statement is to be made from T3.

### 10.6.7 What R3 and R4 settled

R3, interface geometry. The interface is p[:,1] = HSUB = 0.0016 m, dielectric
below with eps_r = 4.4, air above (c1_audit.py:405-406, HSUB from the geojson
fixture at c1_audit.py:348). The axes are band-built and non-uniform
(c1_audit.py:394-397) and the mesh is m2.structured_mesh(XS, ZS). The interface is
a mesh line on every rung. Per-rung resolution from npz metadata only: nodes
527 / 861 / 1275 / 1769 / 3321; edges 1486 / 2460 / 3674 / 5128 / 9720; free
edges 1444 / 2404 / 3604 / 5044 / 9604; free nodes 483 / 803 / 1203 / 1683 / 3203.

R4, the REPRO gate. c1_audit.py:990-998 guards the gate behind bank_col >= 0 and
banked_col == int(bank_col); the comparison is R_extracted == ANCHOR_R_EXTRACTED
with ANCHOR_R_EXTRACTED = 4.0489791163982565 at c1_audit.py:214. The sibling gates
REPRO e_y and REPRO e_z already use the relative tolerance REPRO_RTOL = 1e-6 at
c1_audit.py:262; only R is exact. The gate has never fired: zero occurrences of
the banked REPRO R line exist in the repository, and all 14 recorded R lines take
the no-anchor branch. A derived relative tolerance therefore re-scores ZERO
historical records. It removes a latent trap, in that rung-0 re-runs sit 7.87e-13
from the anchor and would fail exact equality, without changing any verdict.
Whether the column-identity guard should also be changed is reported by D58.2,
not decided by it.

## 10.7 ERRATUM II (appended after T1/T3 were measured, before §10.8 is interpreted)

Nine clauses. Every one of them is a self-correction, and every one is backed by a
re-measurement of the field already banked in the rung archives, not by a new
solve. Provenance: `.scratch/d582/t1_probe.py`, `.scratch/d582/t1_allrungs.py`,
`.scratch/d582/t1_final.py` and their JSON outputs `t1_probe_out.json`,
`t1_allrungs.json`, `t1_final.json`; the analytic control is
`.scratch/d582/build_analytic_control.py` -> `analytic_control.npz`.

One gate was passed before any number below was quoted. Reconstructing J1 from
the banked field at rung 0 reproduces the D58.1 value 3.7903993750636298 to an
absolute difference of 8.9e-16. The 13.85 % deficit is therefore
script-reproducible and is no longer a doc-only number. Rung 4 was never opened
(9604 x 9604, ~738 MB); its R is taken from the dense anchor record already in
`evidence/t4/rung4_dense_anchor.json`.

### 10.7.1 The comparator is the analytic one-sided limit, not the label 4.4

The analytic field's one-sided limit of E_above / E_below at HSUB is
**4.3991693494**, not 4.4. The two differ because the exact solution is not
locally constant across the sampling step used to evaluate it. Every residual in
§10.8 is reported against 4.3991693494, and the value against the nominal 4.4 is
reported alongside it, because the two conventions differ by 0.017 percentage
points and a reader comparing this section to D58.1 will otherwise find a
discrepancy that is not a discrepancy. Rung 0 under construction (a):
-13.838 % against 4.3991693494, -13.855 % against 4.4.

Quoting a residual "versus 4.4" without saying so is not permitted from here on.

### 10.7.2 The D58.1 headline number was doc-only and code-unreproducible

J1 = 3.7903993750636298 was recorded in the D58.1 close-out with no surviving
script that produces it. No committed or scratch artefact reproduced it; the
close-out's own §8 records that `_tmp_field_audit.py` was deleted. This is the
same class of defect as a number that reads as measured but is in fact
transcribed.

It is now reproduced from the banked rung-0 field to 8.9e-16 (see the gate above).
The rule that follows: **every J1 quoted in this project must carry its
reproduction residual.** A J1 without one is an assertion, not a measurement.

### 10.7.3 Construction (c-half) is topology-dependent. §10.6.3's PRIMARY is WITHDRAWN.

§10.6.3 designated construction (c), the extrapolated one-sided limits, as the
PRIMARY number. The measurement shows that the (c-half) variant of that
construction is not a property of the field at all: it is a property of where the
fixed 0.1 mm reporting lattice happens to fall relative to a rung-dependent
element boundary.

Evidence, from the rung meshes' own z-element bounds at the two column pairs the
construction straddles (all values in mm):

| column pair | rung 0 | rung 1 | rung 2 | rung 3 |
| --- | --- | --- | --- | --- |
| cols 14 / 15 | SAME element [1.4, 1.6] | SAME element [1.44, 1.6] | DIFFER: [1.3333, 1.4667] vs [1.4667, 1.6] | DIFFER: [1.3714, 1.4857] vs [1.4857, 1.6] |
| cols 16 / 17 | SAME element [1.6, 2.1] | SAME [1.6, 2.0] | SAME [1.6, 1.9333] | SAME [1.6, 1.8857] |

At rungs 0 and 1 the two columns of the 14/15 pair are inside one element and the
ratio between them measures nothing but interpolation along an edge. At rungs 2
and 3 they sit in two different elements. That switch is exactly the clustering
seen in §10.8's table, where (c-half) reads -11.992 % and -11.287 % at rungs 0
and 1 and then jumps to -3.108 % and -3.158 % at rungs 2 and 3 while the
underlying field has only been refined.

A statistic that changes discontinuously when the mesh moves under a fixed
lattice is measuring the mesh's topology, not the physics. **I introduced that
defect**: §10.6.3 was written before the element straddle was known, and it
elevated a lattice artefact to PRIMARY. The PRIMARY designation is withdrawn.

**Construction (a), the metric-lattice one-row-either-side ratio, becomes the
ladder statistic.** It is not preferred because it is better - it carries its own
constant sampling bias, quantified in §10.8.3 - but because it is the only
construction that is evaluated at the same physical locations on every rung and
is therefore comparable across the ladder at all.

### 10.7.4 The ladder refines y and z together, so the exponent is a bounded range

The five rungs refine the strip direction and the height direction
simultaneously; neither is held fixed while the other shrinks:

| rung | dz_sub (m) | dy_strip (m) | J_a = E16/E15 | residual vs 4.3991693494 | J_c-half | residual | d = 4.3992 - J_a | d / dz_sub | d / dy_strip |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 2.0000e-4 | 2.7273e-4 | 3.790399 | -13.838 % | 3.871625 | -11.992 % | 0.60877 | 3044 | 2232 |
| 1 | 1.6000e-4 | 2.0000e-4 | 3.892549 | -11.516 % | 3.902621 | -11.287 % | 0.50662 | 3166 | 2533 |
| 2 | 1.3333e-4 | 1.5789e-4 | 3.980319 | -9.521 % | 4.262465 | -3.108 % | 0.41885 | 3141 | 2653 |
| 3 | 1.1429e-4 | 1.3043e-4 | 4.030652 | -8.377 % | 4.260264 | -3.158 % | 0.36852 | 3225 | 2825 |

The deficit d is positive and shrinks monotonically across rungs 0-3. Normalising
it by dz_sub gives 3044 / 3166 / 3141 / 3225, constant to +/-2.4 % about a mean of
3144 with a standard deviation of 76.3. Normalising the SAME deficits by dy_strip
gives 2232 / 2533 / 2653 / 2825, drifting by +26.6 % across the same four rungs.

The reading is that dz controls the deficit and dy does not. The fitted exponent
of d against dz_sub over rungs 0-3 is **p_z = 0.91 with a statistical standard
error of 0.03**. The exponent against dy_strip is 0.73, but because of the 26.6 %
drift in the ratio it is not a stable number and must not be quoted as one.

**Pre-registered bound, stated before §10.8 is scored: 0.7 <= p <= 1.0.** That is
the honest interval after the simultaneous refinement and after §10.6.6's +/-0.3
standard error over a dz span of only 1.75x (2.0e-4 to 1.1429e-4 across rungs 0-3,
not the 2.5x of rungs 0-4). The point estimate is 0.91; the interval is what gets
scored.

§10.6.6 remains in force verbatim: "converges at first order" is not a permitted
sentence, and no rate is certified from this ladder.

### 10.7.5 (c-half) moves the rung-0 median by +2.1 % and the cause is not established

At rung 0 the median of construction (c-half) is 3.871625 against 3.790399 for
construction (a), a shift of +2.1 %. The shift is not explained. At rung 0 columns
16 and 17 sit in ONE element [1.6, 2.1] mm, so the denominator factor
median(1.5 - 0.5 * E15/E14) is exactly 1.000000 and construction (c-half) should
reduce to construction (a) exactly.

It does not. The discrepancy is recorded here, unexplained, specifically so that
it is not later read as a validated cross-check of (c-half) against (a). I do not
have a mechanism for it. The per-rung denominator factors are
1.000000 / 1.000000 / 0.95516 / 0.95732 and the per-rung median(E15/E14) values
are 1.000000 / 1.000000 / 0.9177 / 0.9213, so the two constructions agree only
where the straddle does not occur - which is the same topology dependence
diagnosed in 10.7.3, still not an explanation of the rung-0 residual.

### 10.7.6 Caveat (v) is RETRACTED

§10.6.5 and the D58.2 §10 preamble carried a caveat that the mesh might be
non-uniform in the interface band and that the interface might not be a mesh line
on all rungs. The measured geometry contradicts it on all three counts:

- the axes are graded (band-built), but HSUB/dz is an integer on every rung, and
  the band immediately above HSUB is refined down to 2.0e-4 m at rung 4;
- the interface is a mesh line on every rung, as R3 already recorded;
- columns 16 and 17 share one element on every rung (table in 10.7.3).

Caveat (v) is withdrawn rather than left standing as a hedge. The interface
straddle that does matter is the 14/15 column pair, and it is documented above
with its own numbers.

### 10.7.7 The in-strip rows are a differenced diagnostic only, and the close-out's abs() is a defect

The in-strip rows give, at rung 0, extracted -0.29014037829123107 against the
D58.1 close-out's +0.29014037829123102. The two agree to every printed digit and
differ in sign because the close-out applied an undisclosed `abs()`. Same class of
defect as 10.7.2: a specific that reads as measured while carrying a silent
transformation.

What survives: sign agreement between the extracted and analytic fields holds at
every rung (analytic value at the same rows: -0.5271279459), and the in-strip
quantity therefore carries information only when differenced between constructions
and rungs. Its absolute value is not interpretable and is not quoted as a
physical quantity anywhere in this document or downstream of it.

The in-strip values themselves, per rung, are
-0.29014037829123107 / -0.31301 / -0.32748 / -0.33735 for construction (a) and
-0.28951 / -0.31225 / -0.32300 / -0.33984 for (c-half).

### 10.7.8 q25 in the D58.1 close-out §4 is STALE and reproduces under no method

The close-out reports a first quartile of 2.8353371399424034. Recomputation from
the banked rung-0 field gives 2.7755641349300126 under `linear`, 2.7699 under
`lower`, 2.7926 under `higher`, 2.7699 under `nearest` and 2.7812 under `midpoint`.
No percentile method reproduces the documented value, and it is not an order
statistic of the current field either: it lies strictly between
sorted[46] = 2.833946904180182 and sorted[47] = 2.8395078472290676.

The same computation reproduces the median 3.7903993750636307 and the third
quartile 4.1970357464264385 bit-exactly. The field and mask are therefore the
right ones and the discrepancy is confined to the documented q25 itself, which
most likely came from a superseded field or an earlier mask.

Consequence: **the D58.1 close-out's IQR must not be quoted, in any document,
until it is regenerated from the banked field.** The median is unaffected.

### 10.7.9 The J2 claim is RETRACTED

An interim claim in this dispatch held that E17/E16 is piecewise constant, and
therefore that construction choice carries no freedom on the strip rows. The
medians support it - median(E17/E16) = 1.000000 and median|E17/E16 - 1| = 0 on
every rung - and the medians are misleading.

`np.array_equal(E17, E16)` is False on all 40 / 50 / 60 / 72 of the 201 rows at
rungs 0 / 1 / 2 / 3 respectively that deviate by more than 1e-12, and the maximum
|E17/E16 - 1| is 2.95 / 3.44 / 3.96 / 4.49. The large deviations sit at the rows
where the field crosses zero, which is exactly where a ratio is meaningless and
exactly where a median cannot see the problem.

The claim "piecewise constant, therefore no construction freedom" is WITHDRAWN.
No compensating claim of "estimator bias" is made in its place: the evidence
supports neither the original statement nor its opposite, and the honest position
is that the strip-row ratio is not yet characterised.

## 10.8 T1/T3 RESULT

**Outcome: the DISCRETISATION branch of the §10 three-outcome table.** With the
qualification that the scored quantity does not share that behaviour, which is
10.8.1 and which must be read before the outcome is quoted anywhere.

### 10.8.1 GATE IMPLICATION - read this before the outcome

**The interface jump deficit is discretisation. The gate metric is not, and the
gate remains failing.**

J1's convergence says nothing about the quantity the control gate scores. R does
not converge. From the `R_extracted` key banked in every rung archive - no solves:

| rung | R_extracted | residual vs R_analytic = 2.810 |
| --- | --- | --- |
| 0 | 4.048979 | +44.1 % |
| 1 | 3.780332 | +34.5 % |
| 2 | 3.567308 | +27.0 % |
| 3 | 3.612717 | +28.6 % |
| 4 | 3.575412753195199 (dense anchor record) | +27.2 % |

R is non-monotone across the ladder, excursions by 13.5 % between rungs 0 and 2
(4.048979 to 3.567308), and settles about +27 % above the analytic reference at
rungs 2, 3 and 4. There is no shrinking trend to fit; there is a decaying
transient on the coarsest rungs superimposed on a plateau 27 % too high.

The consequence for the gate is structural, not cosmetic:

- **R_REGISTERED = ANCHOR_R_EXTRACTED = 4.0489791163982565 (c1_audit.py:214) is
  the rung-0 value.** Rung 0 is the least-converged point on the ladder. The
  banked rung-0 archive gives 4.0489791163950715, which differs from the anchor
  constant by 3.2e-12 - an agreement in magnitude with the 7.87e-13 re-run
  residual already recorded in §10.6.7, and small enough that the two are the
  same number for gate purposes.
- The control gate has therefore been certifying the worst point on the ladder as
  the reference truth.
- An interface jump that converged perfectly would leave the gate failing at
  ~+27 %, because the gate scores R, not the jump.

Anyone who reads the DISCRETISATION outcome as "the gate is on track" has read it
backwards. What §10.8 establishes is that one suspected cause of the gate's
failure - a structural under-jump at the interface - is not present. The gate's
failure has a different and larger cause, recorded as defect D-R1 in the tracker,
and the R question is now bigger than T4 and changes what T4 means.

### 10.8.2 The ladder, and what its exponent may and may not support

The measured deficits are the table in 10.7.4. The scored exponent is
**0.7 <= p <= 1.0**, the pre-registered bound, from p_z = 0.91 +/- 0.03 with dz
the controlling direction (d/dz_sub constant to +/-2.4 %, d/dy_strip drifting
+26.6 %).

Where the literal §10.3 scoring table puts this: the deficit shrinks monotonically
across rungs 0-3 and the normalised deficit is constant, so the outcome is the
DISCRETISATION row. It is not scored on the exact value of p, because the dz span
is 1.75x, the axes refine together, and §10.6.6 already bound what this ladder can
resolve. p is reported as an interval and is not extrapolated to a rate.

The mask-side sensitivity was checked before the outcome was written, because a
median over 170 rows can be moved by a handful of bad rows:

| rows dropped from each end | rung 0 | rung 1 | rung 2 | rung 3 |
| --- | --- | --- | --- | --- |
| 1 | 3.79617 | 3.90193 | 3.99470 | 4.04292 |
| 3 | 3.82062 | 3.93156 | 4.01387 | 4.06244 |
| 6 | 3.87894 | 3.97453 | 4.01846 | 4.08010 |

The statistic moves monotonically toward the interface ratio as the mask is
tightened, on every rung, and no drop changes the ordering of the rungs or the
sign of the deficit. The negative rows in the mask (2 / 6 / 4 / 3 of them, the
rung-1 minima at rows 79-81 reading -3.30 / -3.25 / -3.19) are zero crossings and
do not drive the median.

### 10.8.3 The SAMPLING ARTEFACT outcome of §10.6.4 is NOT triggered

§10.6.4 pre-registered a fourth outcome, taking precedence over the other two:
if the solver-minus-analytic residual at extrapolated one-sided limits were
consistent with zero on every rung, the whole 13.85 % deficit would be a sampling
convention and the T1/T2/T3 line would be withdrawn.

That is not what happened, and the reason is not subtle: **the analytic control
cannot produce a 13.85 % LOW.** Running the exact analytic field through
construction (a) gives a ratio 5.092 % HIGH - the sampling bias of (a) inflates
the ratio rather than deflating it - and running the same analytic field through
(c-half) recovers 4.4 to -0.0189 %.

So the estimator is validated where it can be validated, and its bias has a known
sign that is the wrong sign to explain the measured deficit. A construction that
biases +5 % high, applied to a field, still returned a value 8-13 % low. The
defect is in the field, not in the sampling.

### 10.8.4 D58.1's 13.85 % is the coarsest rung, not the deficit

D58.1 recorded a single number, 13.85 %, as "the interface under-jump". §10.8
shows that number is the rung-0 value of one construction, and that both the rung
and the construction matter:

- rung 0, construction (a): -13.838 %
- rung 3, construction (a): -8.377 %
- rung 3, construction (c-half): -3.158 %

D58.1's headline is therefore the least-converged rung read through the
construction with the largest sampling bias. It is not wrong as a measurement of
that rung; it was wrong to state it as a property of the interface on the ladder.

### 10.8.5 The limited-regularity explanation is a HYPOTHESIS, not a finding

The proposed mechanism: the exact solution has limited regularity at a dielectric
interface because the normal component has a kink there, so the energy norm and
the eigenvalues converge at the optimal rate while pointwise values near the
interface converge more slowly. That predicts the observed split - an eigenvalue
that settles quickly and a pointwise interface ratio whose deficit decays like
dz.

It is recorded as a **hypothesis**, with no measurement in this dispatch
supporting it beyond consistency, and with an explicit falsification condition:

> **Falsified if** the dz -> 0 intercept of construction (D), pre-registered in
> §10.9, lies below the analytic intercept by more than twice the combined
> standard error. The hypothesis predicts the pointwise deficit to vanish with dz;
> a non-zero intercept means it does not.

### 10.8.6 Defects that survive this result

Two defects are recorded in the workspace tracker as their own entries, on the
owner's instruction, because neither is folded into T4:

- **D-R1, R does not converge.** R ladder 4.049 / 3.780 / 3.567 / 3.613 / 3.575
  against R_analytic 2.810, non-monotone, 13.5 % excursion, ~+27 % high at rungs
  2-4, +44 % at rung 0, and the gate scores the rung-0 value. Larger than T4;
  changes what T4 means. Next diagnostic: recompute R on each rung's own mesh
  instead of the fixed 1e-4 evaluation lattice, which tests the hypothesis that
  the fixed lattice crosses the mesh scale between rungs 1 and 2 - the same
  inversion at which (c-half) splits {-12.0, -11.3} / {-3.1, -3.2}.
- **D-C1, `identified_col` = -1 at rungs 1-3.** The banked metadata reports
  `identified_col` = 738 at rung 0 and -1 at rungs 1, 2 and 3, with `n_eligible`
  = 1 on every rung. The column-identification step is not identifying a column
  on any rung above the coarsest, and whatever it feeds is silently taking a
  fallback path. Reported, not fixed.

## 10.9 PRE-REGISTRATION OF CONSTRUCTION (D)

Defined here, a priori, **before any value is measured**. Nothing in this section
has been computed. It is written now precisely because §10.7.3's failure mode was
introducing a construction and interpreting it in the same breath.

### 10.9.1 Rationale

(c) failed because it sampled where a FIXED 0.1 mm lattice happens to fall
relative to a rung-dependent element boundary. (D) samples element centroids on
each rung's OWN mesh and is therefore invariant to the lattice-mesh relationship
by construction, not by luck.

### 10.9.2 Definition

For each rung k in 0-3, on that rung's own mesh, HSUB is a mesh line:

    J_d(k)  = median over the frozen 170-row mask of  E_z(y_row, c+) / E_z(y_row, c-)

where c+ and c- are the z-centroids of the elements immediately above and
immediately below HSUB, and the mask is the same 170 rows used throughout §10.8
(frozen, inherited unchanged, not re-selected).

A second variant, J_dhalf(k), replaces each centroid value by a two-element
one-sided linear extrapolation of that side to HSUB, removing the leading
dz/2 offset.

### 10.9.3 Extrapolation (required by the owner's ruling)

Centroid values sit dz/2 from the interface, so (D) alone halves the
contamination rather than removing it. Therefore:

1. compute J_d(k) and J_dhalf(k) per rung;
2. fit J(dz_sub) linearly against dz_sub across rungs 0-3;
3. report the intercept at dz_sub = 0 with its standard error.

### 10.9.4 Control

The exact analytic field is run through the IDENTICAL procedure - same mesh, same
mask, same centroids, same extrapolation. Its intercept must reproduce
4.3991693494 within its own standard error. If the control fails to reproduce the
analytic limit, the construction is inapplicable and no conclusion is drawn from
the real field.

### 10.9.5 Pre-registered decision rule

| outcome | condition | interpretation |
| --- | --- | --- |
| A | real intercept consistent with the analytic intercept within combined SE | no structural component at the interface; the entire deficit is discretisation; §10.8.5's hypothesis gains support |
| B | real intercept below the analytic by more than 2 combined SE | structural under-jump present; report its magnitude in absolute terms and as a percentage, and retire the claim that the interface jump is a discretisation artefact |
| C | linear fit inadequate (residuals not consistent with the stated SE, or the intercept SE exceeding the measured deficit) | bounded conclusion only: report the measured values and the inadequacy of the fit; no extrapolation is quoted |

### 10.9.6 Scope and exclusions

Rung 4 is excluded (metadata-only, 738 MB, and the dense anchor already supplies
its R). No new solves: construction (D) reads the field banked in the rung
archives, exactly as §10.7-§10.8 did. This document's §10.6.6 restriction applies
unchanged: the intercept is reported as an intercept with an error bar, not as a
demonstration that anything "converges at first order".
