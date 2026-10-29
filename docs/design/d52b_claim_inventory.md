# D52b claim inventory — raw sweep output

**What this is.** The raw claim inventory taken by the single evidence sweep commissioned
in dispatch 52b: what each standing design document asserts, what it actually offers in
support, and the tier that offer supports. It is the evidence base behind the claim ledger
in `docs/design/soundness.md`. It is not a findings list and not a priority list, and it is
not a substitute for the ledger: `soundness.md` is the ledger of record and carries every
citable claim, with scope, dependencies, expiry trigger and promotion requirement. This file
is the working record underneath it.

**Pointer on rows A17 and A18 (appended, dispatch 55A).** The row grades at lines 107-108 below
(both E3) are superseded for citational use: A17 and A18 are **UNVERIFIED** under
`docs/design/pairing_rule_preregistration.md:477-483`, which requires any document citing them to say
so. The graded position is in `docs/design/soundness.md` section 6 (the `modalport_ownership.md`
tier-spread cell, annotated in place) and section 13 (C1 loses A18 and stays E3; C9 is Withdrawn).
No cell of this file is altered; both tier cells still read E3, because this file is the sweep output
and not a rewrite of it.

**How it was produced.** One evidence auditor, one pass, twelve standing design documents,
13 sections — `t4_amp_ratio.md` was swept in two halves and so appears twice in the sweep
notes. There was no second auditor, no second pass and no inter-rater check. The notes were
taken document by document as each was read, and are reproduced here row for row: the rows
are the sweep output, not a rewrite of it. Only the table header line is normalised, because
the six source files spell the column differently; no cell content was altered.

**Tier vocabulary.** Ours, not borrowed. It follows the general evidence-grading tradition
that separates proof from measurement from assertion; no external scheme is cited as
authority for it.

| tier | name | one line |
|---|---|---|
| E1 | Proven | Mathematical argument; the claim does not rest on a numerical result. |
| E2 | Verified | Measured against an independent analytic reference with the convergence rate demonstrated at three or more resolutions. |
| E3 | Characterised | Measured against a reference with incomplete convergence evidence, or a heuristic whose measured behaviour is reported and whose derivation is absent. |
| E4 | Calibrated | Agrees with an external tool or measurement, with no internal error analysis. |
| E5 | Asserted | Believed and stated, not measured. Not citable. |
| X | Withdrawn | Was asserted and has been withdrawn. |
| UNKNOWN | UNKNOWN | The document states a number whose provenance it does not give, so no tier is assignable. |

**Row format.** `| id | claim | tier | evidence | scope |`. The fourth column is the one
that carries the information: it states **what the document actually offers** — the
measurement, the reference, the number of resolutions, the derivation, or nothing — and not
the claim restated in other words. A row whose fourth column only paraphrases the second has
not been audited.

**Blunt limitations.**

- **One auditor, one pass.** No second auditor and no inter-rater agreement check. Every tier
  below is one person's judgement on one read of one document.
- **Tier assignment is judgemental.** The vocabulary is defined above; where an offer sits
  between two definitions the auditor picked one and did not record the alternatives.
- **The E3/E5 boundary is the softest.** Both can describe an unmeasured or weakly measured
  number. The line taken is that E3 requires a measurement and a named reference while E5
  requires neither, but a reader who reads a given row the other way is not being careless.
- **`t4_amp_ratio.md` was swept in two halves by two passes** — part 1 at lines 1-667 (rows
  `F01`-`F14`), part 2 at lines 668-1316 (rows `G01`-`G14`). The two halves were read and
  tiered separately, so strictness may differ across the seam at line 668, and the same kind
  of offer may be tiered differently on either side of it.
- **Ten rows are not five-field rows.** Their cells contain a pipe — `\|Q-1\|`, `\|corr\|`,
  `1.4e-13` beside a literal `|`, and so on — so those rows split into more than five fields
  when parsed. They are reproduced exactly as written rather than repaired, because repairing
  them would change the record; the counting method below is robust to them.

## Coverage

Twelve documents, 13 sections, 143 rows. Line counts are `wc -l` on the documents as swept;
items 8, 10 and 11 were recorded without a line count in the sweep notes and are counted here.

| # | document | lines | row ids | sections | rows |
|---|---|---|---|---|---|
| 1 | `core_contract.md` | 372 | `A01`-`A08` | 1 | 8 |
| 2 | `cpp_solver_arch.md` | 314 | `A09`-`A16` | 1 | 8 |
| 3 | `modalport_ownership.md` | 217 | `A17`-`A24` | 1 | 8 |
| 4 | `job_schema.md` | 278 | `A25`-`A32` | 1 | 8 |
| 5 | `normalization_scheme.md` | 352 | `A33`-`A41` | 1 | 9 |
| 6 | `visual_engine_arch.md` | 436 | `A42`-`A47` | 1 | 6 |
| 7 | `corr_ez_vv_threshold.md` | 312 | `A48`-`A54` | 1 | 7 |
| 8 | `physics_invariant_layer.md` | 765 | `B01`-`B14` | 2 | 14 |
| 9 | `sparse_eigenmode.md` | 777 | `C01`-`C14`, plus `C15` in the supplementary section | 1 | 15 |
| 10 | `m3c_gate_v2.md` | 959 | `D01`-`D16` | 1 | 16 |
| 11 | `zfree_shape.md` | 541 | `E01`-`E16` | 2 | 16 |
| 12 | `t4_amp_ratio.md` | 1316 | `F01`-`F14` (part 1), `G01`-`G14` (part 2) | 1 | 28 |
| | **total** | **6 639** | | **13** | **143** |

## 1. core_contract.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| A01 | PEC-box anchor: beta^2/k0^2 = 0.438322827 vs predicted 0.438278, rel_delta 1.022e-4, PASS at tol 0.02 | E3 | 10 GHz, 20 x 7.6 mm vacuum PEC box; decisions.md:7666-7668 + pecbox_variant.py:544-603 self-test; one resolution only, no convergence; doc itself calls it "a *formulation* validation, not a *problem* validation" | YES — explicit formulation-vs-problem limit |
| A02 | SELF_TEST_BETA_TOL = 0.02 is reused verbatim as the swap gate | E5 | asserted as "roughly 200x the measured 1.022e-4 and about 5x the 0.3993 % inter-code floor"; floor relayed second-hand from zfree_diagnosis.md §7.2; no derivation, no convergence, no sensitivity study | PARTLY — doc states where the floor came from, not why 5x is right |
| A03 | Dropping the k_q term would make beta^2/k0^2 read 1.0 instead of 0.4383 | E5 | assertion + pointer to code comment (emfit/mode2d.py:1017-1022); no run, no number produced or measured anywhere | NO |
| A04 | ANCHOR_DT = 1.9065748695309721e-13 s (driver literal) | E5 | driver literal at .scratch/tol/tol_driver.py:101-108 while cfl_dt (emfit/evolve.py:68-79) computes the bound inside the core; no derivation of the value shown; no interface carries it | PARTLY — called a "comparability number" |
| A05 | ANCHOR_N = 4,894,400 on ANCHOR_GRID = (322,200,76) | E5 | number appears as a "grid-bound literal, not a core-independent fact"; the same figure in decisions.md:7045 as mesh_cells is an observed equality, not an argument | YES — declared grid-bound |
| A06 | "second 769,356,828-byte sparse copy" of the system exists at run time | E5 | only source is a driver source comment (.scratch/tol/tol_driver.py:73-74); no measurement, no RSS or allocator trace | NO |
| A07 | wall_s = 4210.484 s (70.2 min) for the recorded solve | E4 | "cached wall time" quoted at tools/gates_101_20.py:229-237; single recorded value, no repeat, no error analysis; doc says wall time is reported and never compared | YES — explicitly excluded from verdicts |
| A08 | Bitwise determinism across machine, thread count or BLAS is not supported by anything in the repo | E5 | asserted limitation backed only by a pointer to the record (decisions.md:7065); no experiment either way | YES — stated as a limitation |

## 2. cpp_solver_arch.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| A09 | `M_C` at free_e = 1444 (order 1927) has inertia 1444/483/0 and cond 2.1156e5 | E3 | measured, sourced to sparse_eigenmode.md:529-533 and :336; single size, no independent reference for the conditioning, no convergence; the indefinite *structure* is argued, the numbers are not | YES — one size only |
| A10 | rung1 (sc=16): nnz(M_C) = 35,351 = 0.00344 n^2, nnz(L+U) = 214,641, fill 66.9/row, factor 2.58e-3 GB, splu 0.00756 s | E3 | measured rung table sparse_eigenmode.md:334-349, one mesh, single timing sample, no repeat or uncertainty; timings carry no error analysis | PARTLY — one rung named |
| A11 | At free_e = 30000: route A 8.99e8 nnz / 10.8 GB / 343 s vs route C 7.03e6 nnz / 0.0843 GB / 0.156 s | E3 | explicit two-point power-law fit through two measured rungs; doc labels the whole subsection "EXTRAPOLATED ... Nothing here was measured at the target mesh" | YES — labelled EXTRAPOLATED twice |
| A12 | BLAS thread count 1 vs 4 moves beta^2 by 8.13e-11 relative on the same capture | E3 | decisions.md:7192, one capture pair; decisions.md:7365 quoted in the same page says it shows determinism, "not repeatability" | YES — determinism-not-repeatability caveat quoted |
| A13 | Port gate: binding PASS/FAIL at \|rel(beta^2)\| <= 1e-8; 1e-11 reported but never citable; residual > 1e-6 is INVALID | E3 | thresholds sized by arithmetic from the 8.13e-11 thread null and the 9.79e-12 round-off figure, plus the 0.54 % wrong-pencil magnitude of 7.3; no gate-level demonstration | YES — 5.9 table states what each row may certify |
| A14 | Incumbent cost: 259,760 dof k=4 21.0 s at 682 MiB, k=6 hit the 300 s cap with no data; 115,232 dof 155 s wall, 315.64 MiB | E3 | decisions.md:6119-6123 recorded runs, single sample each, no repeat or variance; 148.18 s in-process quoted alongside 155 s wall | PARTLY — recorded runs, provenance given |
| A15 | Judged meshes: M4 30,672 free edges (58/44/35-17-18) and M3 28,980 (56/43/34-17-17) | E3 | mode_overlap.json:285-301 / :228-248, including sigma 96335.2458966532 and 96404.93625838071, mesh_checks_ok = true, R = 3.473702068959308; single recorded probe per mesh | YES — 30,000-class mesh row removed as unexecutable |
| A16 | A wrong-pencil variant lands +0.54 % / +1.08 % off (98360.7 / 98375.3 vs 97833.1) at abs(corr_ey) 0.55 vs 0.92 | E3 | sparse_eigenmode.md:588-596, measured against a reference lambda; one geometry, one shift, no refinement series; this is the sizing evidence for A13 | PARTLY — one case, magnitudes stated |

## 3. modalport_ownership.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| A17 | Placed-route beta on 31x17 is 336.675159 vs analytic 309.981864 rad/m (+8.61 %), 41x22 +8.87 % | E3 | .scratch/s10118_payload.txt:26 and decisions.md:6844; but the doc's own §3 table rules the "analytic" reference is a fit on the *same capture* with a different profile, so it is a consistency reference, not an independent one | YES — non-independence named in the fact table |
| A18 | Post-repair placed beta 326.910765 / 327.094486 / 327.280996 rad/m = +5.46 / +5.52 / +5.58 %; eps +11.2 / +11.3 / +11.5 % | E3 | three meshes, same script, same lattice; drift is monotone **outward** with refinement and no convergence rate is offered; reference non-independent as A17 | YES — "neither gap is attributed to anything" |
| A19 | Eigen route sits +0.90 / +0.64 / +0.48 % on beta and +1.82 / +1.28 / +0.96 % on eps | E3 | three resolutions with a converging trend but no demonstrated order and no fitting, against the same non-independent analytic reference | PARTLY |
| A20 | sum(e_z^2)/sum(e_y^2) = 2.72e6 / 2.64e6 / 2.54e6, about -3 % per refinement, not converged at 51x19 | E3 | measured on three meshes; monotone drift, not converged; no reference value for the expected ratio (the §8(b) band is a separate proposal) | YES — "not converged at 51x19" |
| A21 | beta and eps are one number: beta/sqrt(eps) = 164.1794 rad/m for all six published pairs | E1 | algebraic: modal.py:578 computes eps from beta on the next line; six pairs agree to 1.1e-7 relative, which is input rounding | YES — only the fitted beta carries information |
| A22 | emfit/modal.py is absent from the repository; the only copy is .scratch/wt-m3b-diag/emfit/modal.py (935 lines, 39846 bytes) | E1 | ls/search of the package plus the sys.path.append at s10118_basis.py:42; .scratch/ is gitignored at .gitignore:34 | YES — named as a provenance hole |
| A23 | Proposed extraction-consistency gate: \|beta_a - beta_b\| / beta_a <= 1.0e-3 | E5 | doc states in terms "The number is proposed, not derived; the operator should rule on it"; sizing argument is the 0.476 % disputed gap and a 3.14 rad station span | YES — self-declared as proposed |
| A24 | Proposed amplitude gate: R <= 1e-2 if `e_z` is longitudinal, or 0.1 <= R <= 10 if it is transverse | E3 | band argued from quasi-static microstrip scaling (longitudinal is O(t/h); both-transverse energies of order one); band width is a judgement, and the branch that applies is explicitly unresolved | YES — branch-conditional, caveat §8(b) |

## 4. job_schema.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| A25 | Schema parses, Draft202012 check_schema accepts it, example validates, jsonschema cross-check agrees with 0 errors | E4 | own validator exit 0 plus "cross-check: jsonschema agrees"; agreement with a second library, no independent error analysis; single library version (4.26.0), single machine | YES — design-only banner, nothing implemented in emfit/ |
| A26 | Every property-bearing node is closed (7 nodes, 0 not closed) and three mutations each exit 1 at the exact JSON pointer | E1 | executed: /materials missing, /seed unexpected, /frequencies_ghz/0 > 1000.0; each fixture is JSON-valid so rejection is attributable to the constraint | YES — 3 mutations only, self-chosen |
| A27 | Exit 2 means "could not check", exit 1 means "checked and wrong"; malformed input exits 2 | E1 | printed transcript; four exit codes (0/1/1/1) unchanged under python3 -S | PARTLY |
| A28 | Keyword inventory: 21 distinct keywords, 0 unsupported, 15 implemented, 6 annotation-only, fail-closed on unknown | E3 | self-reported by the validator's own --list-keywords; no external keyword-coverage reference; "0 unsupported" is as good as the tool's own inventory | NO |
| A29 | Hz/GHz guard: frequencies_ghz capped at 1000.0 GHz = 1 THz, fifty times above the 1-20 GHz working range | E1 | arithmetic on code-verified constants (demos.py:392 bounds 1.0-20.0, :52 defaults 5.0); 2.4e9-vs-2.4 error sits nine orders above; mutation m3 confirms rejection | YES — declared a unit guard, not a physics claim |
| A30 | Example is UNLOADED and cannot reproduce demo_microstrip_stub, which defaults load_value 200.0 at load_at_mm 12.8 mm | E1 | demos.py:118-119 and :55 against a schema with no load member; arithmetic recomputed (0.8 mm cell, 46 cells, 36.8 mm line) | YES — divergence #6 recorded, not repaired |
| A31 | Tolerance is one global {kind: sparam_abs, value}; it reproduces the decisions.md:7089 scope defect rather than repairing it | E1 | schema field map + decisions.md:7089 quoted; per-observable tolerances deferred to v2 | YES — named as a real divergence |
| A32 | The J1-J7 criteria were frozen before any artefact existed, so they could not be redefined post hoc | E5 | author's assertion only; the prereg lives at .scratch/dispatch41_task2_prereg.md, which is gitignored and unversioned, so ordering is not independently checkable; the doc itself admits renumbering, a substituted criterion and one added criterion | YES — the doc states the criteria are "a restatement ... not authentic as a quotation" |

## 5. normalization_scheme.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| A33 | The printed ratio 2.722397e6 is exactly 1e8 x a physical ratio: 2722397.314568 / 1e8 = 0.0272240 | E1 | algebra: `* CELL` applied to the e_y side alone (s10118_split_check.py:24) against a numerator with no length factor; 1/CELL^2 = 1e8 with CELL = 1e-4, reproduced on three meshes | YES — factor is 1e8 "and no more than 1e8" |
| A34 | No eigenvector scale can move the ratio; amplitude pinning is excluded | E1 | homogeneity of degree 0 in the eigenvector amplitude for ratio, mass ratio, Rayleigh quotient and v/i; stored vector already unit 2-norm | YES — class (ii) only |
| A35 | Unit-repaired Scheme A ratio: 0.0272240 / 0.0264298 / 0.0253657 on 31x17 / 41x22 / 51x19 | E3 | three meshes measured; ~7 % mesh spread exceeds the ~2.5 % staggering band and is still falling, so convergence unsettled; doc states A is confirmed as a *definition*, not as a converged number | YES — explicit "definition, not the last digit" |
| A36 | De-staggered variants (both routes, linear/cubic/quintic, three meshes) stay within ~1.5 % of A and ~2.9x above Scheme C | E3 | 2 routes x 3 orders x 3 meshes measured (ROUTE-CC 200/76, ROUTE-NN 201/77 with 552 of 15477 extrapolated nodes); reference C is itself withdrawn, so this is an exclusion, not a validation | YES — falsifier #8 recorded as fired |
| A37 | Scheme C (mesh-exact mass-matrix ratio) = 0.00951415, rms E_z/rms E_y = 0.09753, L = 0.312 mm | UNKNOWN | computed from cached z_free and m_zz/m1; WITHDRAWN 2026-10-26 as a reference definition on the de-staggered measurement; current status is neither confirmed nor refuted as a number, only excluded as the reference | YES — withdrawal and its reason stated |
| A38 | Quasi-TEM bracket R in [3.9e-3, 2.5e-1] from R ~ beta^2 <L^2> at L = 0.2 mm / h / h/2 | E1 | derivation from E_z = -i beta phi, E_t = -grad phi; bracket is a property of the estimate, not a measurement; A's 0.0272 sits inside it | YES — bracket only, "never a candidate definition" |
| A39 | The ratio carries ~7 % mesh sensitivity from interpolating the nodal E_z off a graded 0.2/1.0 mm mesh onto a 0.1 mm lattice | E3 | three-mesh drift -2.92 % then -4.02 %, entirely inside rms_e_z (3.9999 -> 3.9944 -> 3.8508) while rms_e_y is stable to 1.6 %; a mechanism is proposed, no interpolation-error study | YES — "too noisy to distinguish schemes at the 10 % level" |
| A40 | corr_e_y = 0.9208 vs corr_e_z = 0.1192 against the analytic profile; the E_z block is a solve-side defect | E3 | overlap print plus a battery of exclusions (gauge variants 0.009491 / 0.050802, sign oracle 0.197856, E-dot-dl -0.1173 vs analytic control 0.7706, integral(e_z dz) = 0 violated); mesh-independent 0.119160 to 0.119317 | PARTLY — "which revision produced 0.1462 remains unresolved" |
| A41 | Every V/m in the document is a dimensional inference; the string V/m appears nowhere in emfit/ | E5 | argued from Whitney-basis 1/length factors and docstrings; no unit is ever carried or checked in code | YES — flagged at the head as an inference |

## 6. visual_engine_arch.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| A42 | A full 3D field grid serialises to ~82.4 MB, about 125x the incumbent's measured 656,469-byte response | E1 | arithmetic on cited run 322 x 200 x 40 at 0.1 mm (decisions.md:812): 2,576,000 cells, ~7.73e6 edges, complex64 61.8 MB, base64 82.4 MB; nothing executed; basis named (recomputation from cited inputs) | YES - only routes are server-side extraction or declared decimation; decimation ratio OPEN |
| A43 | Response budget 656,469 bytes leaves 282,217 bytes for a viewer on the animation page | E1 | arithmetic: recorded 280,689-byte animation -> ceil(280689/3)*4 = 374,252 base64 chars; 656,469 - 374,252 = 282,217; budget source decisions.md:14 | YES - budget proposed, not yet enforced by a running test |
| A44 | Six browser-free acceptance tests are specified but none was executed; sphere tolerance is proposed, not measured | E5 | section 9 asserts PASS/FAIL verdicts over bytes and numbers; tolerance "0.5 * sqrt(dx^2+dy^2+dz^2)" explicitly not measured ("no code was executed for it"); no browser binary exists | YES - section 9.7 states what the suite does not establish |
| A45 | `tests/test_demo_picker.py:96-98` forbids `<script` on all five served page types, so no client-side viewer is admissible | E1 | existing shipped gate cited at :122, :152, :169, :187, :205, docstring "a page is not exempt"; checkable by reading the file, binary outcome | YES - guard condition: binds served pages, not the engine |
| A46 | Rulings taken at Dispatch 43: R2 keeps pages script-free; R3 admits field arrays as a binary sidecar, absent case legal | E1 | ruling table section 11 rows 5 and 8, argued in 9.6; recorded as rulings, appended not substituted | YES - explicitly governance, no measurement claimed |
| A47 | Isosurface library licence and encumbrance are unverified; no licence file or vendoring record exists in the tree | UNKNOWN | section 7.2 marked OPEN, "recorded as unverified"; no licence file, no vendoring record, and per the doc "no search for the answer was performed" | YES - declared unverified at the point of use |

## 7. corr_ez_vv_threshold.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| A48 | The bar is self-referential: T = L - 2*S_good, where S_good is the spread of the legs it judges | E3 | rule stated in closed form (section 3.2, section 4); heuristic placing a bar two spreads below its own population, with the circularity stated rather than derived away | YES - section 5: reproducibility screen, "not an accuracy statement" |
| A49 | S_good = 0.0132433711770793, the 31x17 -> 41x22 PMC step, replayed to worst abs delta = 4.302e-16 with solves=0 | E3 | replay log :70-74 with input sha256 digests, execs only the metric block, injects banked z_free; only one refinement pair, two distinct meshes, no independent sigma or third mesh | YES - "not a dispersion: two points, one refinement pair" |
| A50 | Bar T = 0.9352867303487647 - 2(0.0132433711770793) = 0.9088, rounded up to 0.91, moves no banked verdict | E1 | arithmetic on cited operands; rounding delta 0.0012 = 0.0906 S_good; window [0.9088, 0.91) contains no banked leg; basis named (recomputation) | YES - section 5 separates inertia from a safety argument |
| A51 | The bar records reproducibility, not correctness; a common-mode bias on both meshes would not be detected | E1 | closed-form argument in section 3.2: min - 2*(max-min) cannot reject its own population; no sigma, so the argument is logical, not measured | YES - section 5, and accuracy deferred to decisions.md 5.3 |
| A52 | Only four banked legs exist; the bar has never been exercised as an independent discriminator | E1 | decisions.md:7874-7877: three pass, column 704 at 0.083134346 also fails corr_e_y at -0.426418989, so it would be rejected without the bar | YES - called "the limit of the evidence" |
| A53 | Legacy F = 1.5657e-4 must not be substituted: 2F would raise the bar to 0.94, above the weakest passing leg | E1 | arithmetic: 0.9352867303487647 - 3.1315e-4 = 0.9349735821273027 -> 0.94 on the grid; F cited at c2b_preregistration.md:29, :44 | YES - section 3.1: ratio 84.5821 "descriptive only", not a conversion factor |
| A54 | 0.91 is not transferable to corr_e_y; the same rule on its own spread would give 0.89 | E3 | corr_e_y legs 0.920770784811142 and -0.938702180035899 with own spread 0.017931395224757, then 0.920770784811142 - 2(0.017931395224757) = 0.88491 -> 0.89; NO PROVENANCE - these three numbers carry no citation in the note or its provenance table | PARTLY - flagged for the M3c gate, "not changed here" |

## 8. physics_invariant_layer.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| B01 | Seven invariants I1-I7 specified, none tested; I7 passes trivially on today's lossless, frequency-independent materials | E5 | Status block: "writes no test, injects no defect, runs no solver and reports no number of its own"; section 3.8 says I7 "passes trivially ... rather than a test of the current ones" | YES - declared as design only, no authorisation to run |
| B02 | Tolerances derive from IEEE double unit roundoff u = 2^-53 = 1.1102230246251565e-16, with gamma_n = n*u/(1-n*u) | E1 | arithmetic: gamma_100 = 1.1102230246251688e-14, recomputable from the stated formula; u cited as the double roundoff, no measurement involved | YES - forwards error bound applies to accumulated sums only |
| B03 | Eigenpair tolerance is the measured residual in the B^-1 norm: abs(mu - lambda) <= sqrt(r^T B^-1 r) | E1 | derived bound via C = B^-1/2 A B^-1/2 symmetric; the doc states "the measured residual in the B^-1 norm is the tolerance" | YES - requires B symmetric positive definite |
| B04 | Mixed pencil has an indefinite B, so that bound is unavailable; _MIXED_RESIDUAL_TOL = 1.0e-3 stays a diagnostic, not a gate | E1 | argument in 3.1 (B^-1/2 does not exist as a real transform; needs eigenvector condition number from QZ, to be measured) plus cited code line 150 | YES - explicitly "keeps it that way" |
| B05 | A curl-curl sign flip is silent in all seven invariants; only the analytic anchor fires | E1 | section 1.3 gives seven separate algebraic reasons (k_q symmetric either way, flipped beta^2 still positive, same scaling degree, ...); no injection was run, the table is undischarged | YES - 1.10 states the claim must be discharged by injection |
| B06 | A coupling sign flip leaves A and B identical entry by entry, so only the pairing form of I3 fires | E1 | section 1.4: A = k0^2 m_eps - k_q contains no c, B = m1 - c D c^T is even in c; blindness is "by construction rather than by margin" | YES - beta-side invariants blind, longitudinal field damaged |
| B07 | Coupling perturbed by 1e-3 moves beta^2 by order 2*eps*s_c, so detection is conditional on the modal share s_c | E1 | derivation in 1.6 (first-order change -2 eps c D c^T), s_c defined as modal share of eliminated longitudinal energy and reported per case | YES - "does not claim row 2 unconditionally" |
| B08 | s10118: two bases, one geometry, beta = 309.9818636706751 vs 326.9107654423116 (+5.46%); purity 0.013875 vs 0.206827 | E3 | measured once on a 1444-free-edge / 483-free-node mesh, results in .scratch/s10118_result.txt (untracked); reference is another discretisation, no convergence, no refinement | PARTLY - doc notes the file is untracked and a reader may not have it |
| B09 | A figure labelled passivity reads 2.0013807961296104 on one basis; above one is impossible, so that basis is inadmissible | E5 | physics argument (closed lossless box) is sound, but NO PROVENANCE for the number: the result file has no s11/s21 key, "no way to trace it to a computation" | YES - inadmissible as evidence, not claimed wrong by computation |
| B10 | The s10118 comparison harness dropped the 1j and applied np.abs, so it compared a mirrored reduction, not the solver's e_z | E5 | stated from reading .scratch/logs/s10118_basis.py, which is untracked; "the finding is stated here in this document's own words" - not re-verifiable from the repo | YES - finding scoped to the harness, repair is a separate task |
| B11 | I6 flags the mixed path today: it normalises in the plain 2-norm against a documented e^T B e = 1 | E1 | code/document mismatch cited to emfit/mode2d.py:1127-1130 vs the container docstring at :636; same defect as decisions.md:7008, left OPEN | YES - recorded, not resolved; blocks the acceptance row |
| B12 | Measured mixed-pencil asymmetry is 8.2e-17 relative and 3.8e-17 absolute; a small-pencil check gave 1.5e-15 and 2.2e-16 | E5 | NO PROVENANCE: four numbers from "a numerical check on symmetric pencils of order two to four", with no script, log, path or mesh named; not reproducible from the document | PARTLY - the check's scope (order 2-4, indefinite B) is stated |
| B13 | Anchor: exact transcendental TE/TM root by in-test bisection, meshes h to h/8, expected observed order p = 2 | E5 | 4.2-4.5 give the dispersion relations and the four-mesh protocol, but "no numeric beta is asserted", "the numerics are to be measured; the band is not fixed here" | YES - unfitted interface excluded from p, TM kink recorded as caveat |
| B14 | The 'physics invariants (9.1)' row of the acceptance table stays UNMEASURED, pending a pre-registered normalisation change | E1 | section 5.2: the normalisation defect is a physics change, amplitude enters every extraction, so no figure is citable until pre-registered; "the emptiness ... is a queue position" | YES - names the blocking reason and the gate that stays at 1e-8 |

## 9. sparse_eigenmode.md

777 lines. Swept in two sections: the main C section (rows `C01`-`C14`) and a
supplementary section written after `m3c_gate_v2.md` because the C section hit its
20-word row cap (row `C15`). `C15` is shown here with its document rather than in its
source position; its row content is unchanged.

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| C01 | Dense path on the target mesh needs 16.7 GB per matrix and ~41 days (QZ) | E5 | labelled **ESTIMATED**, "inherited arithmetic, not timings"; 41-day figure traced to `.scratch/logs/s10118_d.py:11` (untracked); no run, no timing, no allocator trace | YES - labelled ESTIMATED and disowned in section 9 |
| C02 | Section 4's stiffness-side pencil is not the code's: returns lambda = 26953.0 vs reference 97833.1 at sigma = 1 | E3 | section 4.2 defect columns on both audit rungs (`rung01_sparse_report.json`): lambda 26953.009476 / 26953.002674 vs dense QZ 97833.057851 / 97328.308109; R 1830 / 1931 vs 4.05 / 3.78; abs(corr_ey) 0.36 vs 0.92 | YES - two rungs, sigma = 1 and shift moved to 0.999 beta^2 (+0.54 %/+1.08 %) |
| C03 | Route C reproduces the dense reference beta^2 to 12.2 / 12.5 digits on both audit rungs | E3 | section 4.2 measured rung table, evidence key `rungs.*.route_C`; lambda and R agree to 12+ digits, residual 2.59e-15 / 8.49e-18 | YES - two rungs only; target mesh explicitly unverified (section 9) |
| C04 | B = m1_f - c D c^T is indefinite: cholesky(B) raises LinAlgError on all four rungs | E1 | executed binary check at sc = 4, 12, 24, 48; docstring cites 565 of 1592 eigenvalues negative | YES - four rungs on this geometry |
| C05 | Every block except c D c^T assembles exactly symmetric; asymmetry <= 1.4e-13 comes only from that product | E1 | max|block - block^T| = 0.000e+00 for m1_f, m_eps_f, k_q_f, h on all rungs; max|B_raw - B_raw^T| 4.3e-15 ... 1.4e-13 | PARTLY - roundoff-level claim is measured, not proved, and host-dependent |
| C06 | Primary pencil breaks the documented `eigsh` M= contract (M indefinite) but fits the LinearOperator form | E1 | verbatim scipy 1.18.1 docstrings quoted in section 6 plus measured indefiniteness (C04); M= retained only as diagnostic | YES - route C operator form named as the compliant one |
| C07 | Fill/row rises only 53.7 -> 58.7 from sc = 4 to 200, so factorisation is not O(n^2) | E3 | section 5.2 table measured on the **REJECTED** matrix (137.9 at target n = 60587); "not O(n^2)" is an inference, the 58.7 -> 137.9 jump unexplained | YES - explicit warning that these are rejected-pencil numbers |
| C08 | Route C rung1: splu 0.00756 s, nnz(L+U) = 214,641, fill/row 66.9, factor 2.58e-3 GB | E3 | section 4.2 measured; single host, single run, no repeats or error bars; 0.43 ms per apply is arithmetic on 0.00901 s / 21 OPinv | YES - rung1 only, host not characterised |
| C09 | Target-mesh route C cost 0.0843 GB / 0.156 s, 127.99x under route A's 10.8 GB / 343 s | E5 | labelled **EXTRAPOLATED**: two-point power law through sc = 12 and 16 only; no rung-4 or target-mesh measurement exists | YES - stated in erratum, section 4.2 and section 9 |
| C10 | M_C inertia at rung0 is 1444 positive, 483 negative, 0 zero, so M_C is nonsingular | E3 | one-off dense eigh (`mc_inertia_check.py`), 1927 x 1927, cond 211559.9, smallest abs(lambda) 1.03e-4, no zero eigenvalue | PARTLY - one rung; sections 7-8 then assume nonsingularity at n = 60587 |
| C11 | h is SPD (cond_2 1738) and the negativity sits in the Schur complement h - c^T m1_f^-1 c | E1 | Sylvester/congruence argument plus measured ldl(h) min diag(D) 0.306 and m1_f eigenvalues 0.112 .. 3.158 | YES - argument is exact, inputs measured at rung0 only |
| C12 | Section 5.2 fill/solve figures (fill/row 137.9, splu 0.38 s, solve 12.82 ms) belong to the rejected pencil | E1 | the doc's own label warning; those numbers are measured on a pencil the note rejects, so they cannot be carried to route C | YES - stated in section 5.2 and repeated in section 9 |
| C13 | The global argmax of beta^2 at mode2d.py:1167 may select the most oscillatory mode, not the fundamental | E5 | section 7 says it was "not something this note measured"; section 9 lists it as an open question needing a measurement | YES - flagged as open, not resolved |
| C14 | Shift-invert makes sigma an input and k a real truncation; the audit's banked numbers must be re-taken | E1 | code quotes mode2d.py:1150-1167, :1010-1016, :1085-1090 and c1_audit.py:478 consuming `chosen`; no numerics claimed | YES - verdict limited to result semantics, not accuracy |
| C15 | §1 says no eig/eigsh/eigs call was made; §4.2 reports eigsh runs (21 OPinv) on routes A/B/B2/C. | X | sparse_eigenmode.md :58-60 "No eig/eigsh/eigs call was made while producing it; every number below..." vs :314-323 per-route table and :347 "eigsh wall time / OPinv calls ... / 21"; §9 :753-759 retro-scopes the ban to assembly measurements only | partial — the narrowing exists only at §9 :755-759; §1 :58-60 states no such limit |

## 10. m3c_gate_v2.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| D01 | CORR_EY_MIN=0.89 is in force; threshold 0.9207707848111419 − 2×0.017931395224757 = 0.8849 rounded up. | E1 | arithmetic on two banked PMC leg correlations (c1_audit.py:216-233, :234); doc itself: "arithmetic on two banked numbers, not a measurement" | yes — two legs only, no FDTD, no gate run |
| D02 | The 0.89 population is two PMC mesh legs; adding a disputed third leg would give 0.86. | E5 | §3.3 max−min arithmetic 0.026359135224690 → 0.8596; zfree_shape.md:77; label defect at decisions.md:8004-8005 | yes — no two-mesh convergence claim (decisions.md:8014) |
| D03 | T5_ez_corr bar 0.91 = 0.9352867303487647 − 2×0.0132433711770793 = 0.9088 rounded up. | E1 | arithmetic on three banked legs; derivation comment c1_audit.py:237-254; rounding costs 0.0012 = 0.09 spreads | partial — three solve legs, no independent reference |
| D04 | T5_ez_corr discriminates: three banked legs pass by 1.9–2.9 spreads; col-704 witness fails by 62 spreads. | E3 | legs 0.935286730348765 / 0.948530101525844 / 0.936929717079781; witness |0.083134346|; in force, second site pecbox_variant.py:511-513 | partial — population is three solve legs |
| D05 | T5_fringe_excess 2.0 bar ships RED; both recorded legs (2.849, 2.89) exceed it, 1.42× and 1.45×. | E3 | D_R/√(A_R·E_R) on 1.5 < |y−10| ≤ 3.1 mm, decisions.md:7958-7972; implemented nowhere; legs differ 1.4% | yes — two legs, no third resolution, decomposition ad hoc |
| D06 | Fringe verdict does not depend on 2.0; any bar in (1.0, 2.849) fails both legs. | E1 | §3.5 interval arithmetic; 2.0 is midpoint 1.9245/1.9450 rounded up on a 0.1 grid | yes — bar is policy, not a measured value |
| D07 | Legacy CORR_EZ_MAX=0.30 cannot be violated: recorded 0.1192/0.1462/0.1979/0.1991 sit 1.5–2.5× below. | E1 | c1_audit.py:235 applied :728-730; decisions.md:7938 "corr_ez contributed nothing" | yes — legacy, superseded, non-selecting |
| D08 | T4_amp has no threshold and cannot fail; withdrawn 1e-2 and 0.1–10 bands must never be reinstated. | E5 | no statement, no X (decisions.md:7258); appears in no .py; bands "derived from nothing, present in no implementation" (decisions.md:7256-7258) | stated, but §10.2/§12 later register ±10% and record FAIL |
| D09 | T4_amp FAIL at 44.09%: R_extracted 4.0489791163982565 vs analytic 2.8101021387524523, band ±10%. | E3 | Q=1.440865461991999, 4.41× the half-width outside [2.529,3.091]; t4_amp_ratio.md §9.1-9.6 | yes — metric documented bad, R non-convergent, no mesh in band |
| D10 | T2_agree fails at 9.03× T2_TOL on the scored fit; second fit passes with 1.25× margin. | E3 | 326.9107654423116 vs 312.7827646322591 = 4.516873%; TOLFLUX 314.03158662735785 = 0.399262% | yes — reference is the same solver's beta_eigen, n=2 |
| D11 | T1_TOL=0.005 is "measured, not derived"; mixed basis raises instead of evaluating a 12× span. | E5 | gates_101_20.py:132, provenance comment :100-131; NotImplementedError :486-493; 3.06/2.99% span 6.24% | yes — no run recorded; "an error is not a failure" |
| D12 | T3_TOL=1e-5 gates only the plane_Ey slot; the flux route is blind at 1.0256e-8. | E5 | gates_101_20.py:221, detection :758-762; sensitivity ladder :224; definition (ii) decisions.md:7254 | yes — a definition choice, no gate run recorded |
| D13 | T6_fit_route reuses 0.005: one fit at 0.399262% passes by 1.25×; not accuracy evidence. | E5 | beta_eigen 312.7827646322591 vs 314.03158662735785; registered, no implementation, in no .py | yes — n=1, explicitly not cross-solver or FDTD |
| D14 | REPRO_RTOL=1e-6 is exercised: recorded drift 0.1462 against anchor 0.1192 overshoots four decades. | E3 | c1_audit.py:977-985 vs ANCHOR_CORR_EZ 0.11916043239134175; witness .scratch/logs/mesh51.log:18 | yes — the only clause with a historical witness |
| D15 | Air band is the only knob: N=22 still 3.2761300897590 against 2.810; strip flat, z wrong way. | E3 | t4_amp_ratio.md §9.7-9.8 sweeps; fitted intercepts Q_inf 1.19997/1.2428 outside band; rms 0.0882/0.0809 | yes — convergence premise mis-specified, dense ceiling N=25 |
| D16 | Closure PASSes T4b (0.9988/0.9856) and T4c (1e-4), yet the gate verdict stays FAIL. | E3 | 10 mesh-pair minima; lambda 95889.18/95888.19/95887.66 with steps 1.03e-5, 5.58e-6; 2e-4 refused, M+s12 pooling refused | yes — mesh-independence is never accuracy; λ converged is not R converged |

## 11. zfree_shape.md

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| E01 | E_z must vanish at the strip centre and change sign across it, so a node there is physically required. | E1 | Pure analytic argument, :58-66 (restated :491): div E = 0 with d/dx ~ 0 and d/dz -> -i beta gives E_z proportional to d_y E_y, given E_y peaked at both strip edges; no number used. | partial — node position admitted assumed (:395-398), and :358 contests that the longitudinal component owes the reference's node at all. |
| E02 | The extracted z_free is single-signed on every mesh (0 of 483 negative at 31x17, 483 of 483 at 41x22). | X | Measured counts quoted from decisions.md:7306/:7310 and the ephemeral log .scratch/logs/corr_ez_followup.txt:39-40 (mean 9.531420107e-03, min 0, fraction under 0 = 0.0000); withdrawn at :456 as class (c), a vertical field's expectation applied to the longitudinal solution. | no — stated flat in section 1 (:30-40); the retraction lives only in the appendix. |
| E03 | The shape defect is real and converged-wrong on two independent meshes (corr_e_z 0.1192 and 0.1473). | X | Whole-plane correlation of a longitudinal extraction against the vertical A_ez (:450; zfree_diagnosis.md:1098-1112); appendix :450 also finds the 0.1473 leg is corr_ez[0] of a 31x17 npz, not a 41x22 run. | no — "two independent meshes" asserted where quoted; :387-391 only says the two 0.119-class chains are unreconciled, not that the mesh label is wrong. |
| E04 | The transverse leg is sound (corr_e_y 0.9208 and 0.9123 versus 0.079 and 0.088), so the defect is longitudinal. | X | Like-for-like correlation from zfree_diagnosis.md:1098-1112; the corr_e_y half stands (class b, :451, decisions.md:7300) but the inference "the defect is longitudinal" is withdrawn. | partial — measurement scoped to two meshes; the conclusion drawn from it is retracted. |
| E05 | PEC instead of PMC shifts corr_e_z by 0.028131 (23.6 percent), about 180x the mesh floor F = 1.5657e-4. | X | mode_plot.log:20 and :26 difference, quoted against c2b_preregistration.md:29/:44; :431 corrects it to +0.0016430 (about 10.5x), and :505-509 disowns even that quotient as arithmetic across two scales. | no — the 180x quotient is stated flat at :327-328 with no dimensional caveat; the caveat is appended four hundred lines later. |
| E06 | The operator's forward map c@phi_analytic peaks at abs(corr) = 0.77 and is single-signed, a 15.2 percent ceiling. | X | Forward map scored against the vertical reference A_ez (corr_ez_followup.txt:177-180; zfree_diagnosis.md:214-230) — the mis-paired pairing; :453 retains only "0.77 is a property of c" and sends the 15.2 percent to re-derivation. | partial — :453 limits the surviving half explicitly; the ceiling was never priced against the scored quantity. |
| E07 | The extraction's sign versus the reference reverses at the strip boundary (-0.1995 under, +0.3842 outside); the control's does not. | X | Two-region correlations against A_ez (corr_ez_followup.txt:155-157, :185-186); :457 rules the reversal a property of the pairing, not of the extraction. | no — the 31x17 counterpart was never read, and that gap is disclosed only in section 6 (:387-388). |
| E08 | beta and eps_eff barely move between meshes (0.645 and 0.324 percent), so the defect is not resolution. | E3 | Scalar-against-scalar mesh comparison only (3.6295122080769704 to 3.606094999644309; 312.782765 to 311.772112, zfree_diagnosis.md:1115-1116); class (a), survives (:452). | partial — two meshes, no convergence rate, so "not resolution" is an inference from 0.6 percent drift at two resolutions. |
| E09 | The reconstruction reproduces the library's own field to machine precision (max relative difference 0.000e+00 and 8.484e-16). | E3 | zfree_diagnosis.md:213 (S8); two code paths compared against each other with A_ez absent (:459), so a capture check, not a fidelity measurement. | partial — self-consistency only, explicitly "not a capture bug", no reference enters the comparison. |
| E10 | The analytic reference is within +0.74 percent of the Hammerstad/Jensen impedance, bounding reference error under 1 percent. | E4 | External formula 3.32546 against reference 3.3500085193 (zfree_diagnosis.md:450-460), inside the 1 percent kill criterion; no error analysis and no mesh dependence offered for the 0.74 percent. | partial — bounded under 1 percent and called too small for the 4.09/8.35 percent gap, but the comparison is single-mesh. |
| E11 | The longitudinal solve is fed a wrong right-hand side: real beta at c1_audit.py:471 against 1j*beta at mode2d.py:1175. | E5 | Source-line reading only (:428-429), replicated in three re-implementations (mode_plot.py:318-334, pecbox_variant.py:410-419); no run and no arithmetic is offered. | yes — :494 and section 6 state it is an observation about source lines, untested; panel agreement cannot exclude it. |
| E12 | The field comes from inverting (k_zz - k0^2 m_zz) rather than differentiating, and smoothing cannot manufacture a sign change. | E5 | Code reading (c1_audit.py:471-473, mode2d.py:1175) plus a textbook smoothing property (:392-394); the smoothing claim is nowhere demonstrated numerically. | yes — "H5 is a reading of the code, not a measurement" (section 6). |
| E13 | A masked per-row sign census (n_sc plus the three-sign tuple over rows 85-115, columns 17-73) is the cheapest decisive measurement. | E5 | Specification only, never executed (:381-382); cost 1.6 s is an inherited estimate (zfree_diagnosis.md:1225-1227); the outcome-to-hypothesis table (:364-370) is a prediction. | yes — "nothing was run" and the 1.6 s is explicitly an estimate, not a measurement. |
| E14 | A_ez carries exactly one sign change per row on rows 84-116, always at column 16 (z = 1.600 mm = h). | E3 | Measured but threshold-dependent tally (:346-354): 132/69 at 1e-2*max = 1.578671918791774e-02 versus 82/119 at 1e-12, 30 of 30 strip rows; counted by .scratch/m8_fieldlevel.py, no convergence, no analytic reference. | partial — :351 warns against stating "no sign change" without naming the threshold; these numbers are absent from the section 7 provenance table. |
| E15 | Same-component vertical correlation is 0.9353, 0.9485 and 0.9369, and the 0.91 gate is fitted to their spread. | E3 | Measured from c1_audit.py:510-511 (:461); bar 0.9087999879946061 rounded up to 0.91 (:467-471), a threshold fitted to the very legs it screens; the 41x22 run is said to bank no correlation arrays at all (:521-522). | partial — 0.91 provisional, 2-3 legs only, and the doc withdraws its own 41x22 PEC example (:513-535). |
| E16 | Banner declares the file SUPERSEDED/VOID while sections 1-6 stand; the appended correction is itself then retracted. | X | Banner (:1-8) against :358 ("not withdrawn here"); :431 (10.5x) against :505-509 (not a detection margin at all); :480-482 (41x22 PEC column 704) against :513-535 ("both errors are mine"). | no — no single status statement survives; three append-only layers contradict the body and each other. |

## 12. t4_amp_ratio.md

1 316 lines, swept in two halves by two passes. Part 1 covers lines 1-667 (rows
`F01`-`F14`); part 2 covers lines 668-1316 (rows `G01`-`G14`). The rows are reproduced
in that order and unmerged, so any difference in strictness across line 668 stays
visible.

| id | claim | tier | evidence offered in the doc | scope limit stated? |
|---|---|---|---|---|
| F01 | R_analytic = Σ A_ez² over Σ A_ey² equals 2.810102138752 and is the scoring reference. | E3 | :5-15 table: sums 3.036149093425e+02 (15276 pts) and 1.080440832223e+02 (15400 pts) read from out/c1_spectrum.npz keys A_ez (201,76) and A_ey (200,77); quotient plus per-sample 2.832912603875 from an n-gap correction 15400/15276 = 1.008118. Measured arithmetic on another module's banked arrays; no independent analytic derivation of 2.8101 anywhere in the doc, though every verdict is scored against it. | partial — :17 concedes the arrays cannot separate the PMC and PEC legs; no error budget on the reference itself is given anywhere in lines 1-667. |
| F02 | A_ez and A_ey arrays are identical in both captures, so R_analytic cannot separate PMC 738 from PEC 699. | E3 | :17 asserts "array-identical (np.array_equal True)" between c1_spectrum.npz and pecbox_spectrum.npz. Asserted, code site not cited; §2 inventories both files' keys and shapes without re-printing the equality. Consequence is load-bearing: the denominator of every verdict comes from arrays that are the same object in both legs. | yes — explicit in :17; not repeated in §9.1 or §10.8 where the band is quoted. |
| F03 | R_extracted 4.0489791163982565 is banked as a scalar; the e_y and e_z_vv pair behind it is not banked. | E3 | :19-33 npz inventories; pair built at c1_audit.py:679-680 and :686-687, reduced to a scalar at :705, banked at :816 (keys :840-871 hold only A_ez/A_ey/scalars); decisions.md:7956 "true vertical-over-in-plane energy ratio has not been computed". Column ambiguity visible in the same artefacts: 738 → 4.0489791163982565 versus 704 → 70.635018555128326, factor 17.445142719817547. Two items are flagged as inference. | partial — the unbanked-operand limit is stated in §2/§10.4 but not where R_extracted is quoted as a measurement (:61, :124-129, :156). |
| F04 | The ±10 % bar is an uncited "standard engineering target"; looser alternatives were rejected after the 44.09 % miss was known. | E5 | :66-89. :87 justifies 10 % by "it is the standard engineering target for a 2D cross-section extraction" — no citation, no literature, no derivation; :96 admits it is "a pre-registered engineering requirement, not a derived error budget". :74-81 alternatives table (±20 %, ±25 %, ±0.2 absolute) is computed against the already-known 4.408654619919989× miss, and :83-85 rejects them on qualitative grounds ("a bar that a tweak can accidentally satisfy"). Nothing measures the scatter of R_extracted; n = 1 (:94-96). | partial — the doc says the bar was committed before any refined-mesh solve (:120) but not that it was chosen after the baseline miss was in hand. |
| F05 | Refining only the strip band moves R_extracted 0.13 % over 3×, so the verdict does not move. | E3 | :122-137; four real runs C1_STRIP_CELLS = 12/18/24/36 at 31x17/37x17/43x17/55x17, R 4.0489791164/4.0463369445/4.0514540972/4.0493407985, pair deltas +0.0653/−0.1263/+0.0522 %, every extrapolant 4.04-4.06 (:133). Measured, with a reproducibility gate (12 reproduces banked capture to 10 digits). Convergence demonstrated as absent, not achieved; corr_ey 0.9208→0.9213, modes_kept = 1, residual ~1e-16. | yes — :143 "the bar is untouched"; limits stated in §9.5 and §10.10. |
| F06 | An earlier .scratch three-mesh O(h) extrapolation landing "inside the band" is retracted as mixed-band. | X | :139 retracts the 31x17/41x22/51x19 → 4.049/3.771/3.566 trend that "would extrapolate to R_inf of roughly 2.86-3.32, inside the band"; :176 states the same trend "was mostly the first-axis air band". Both contradict :74's own band, whose upper edge is 3.09111235262770 — a range topping out at 3.32 is 7.4 % above the edge, so "inside the band" was never true even before the retraction. | partial — retraction is explicit; the mis-stated range against the band edge is not flagged. |
| F07 | Six air-band points give extrapolants from 1.86 to 5.93, a 144.7 % spread; the order is not identifiable. | E3 | :147-168; six real runs N = 6/9/12/15/18/22, R 4.4382495593902 → 3.2761300897590, pairwise deltas −8.7708 to −1.8598 % and non-monotone in size (the N = 18 step collapses to −1.86 %); linear 2.8887847283, quadratic 2.6071327418, Richardson 2.5264540 to 5.9264405, fixed-p 1.8594054; 9x11x6 multistart found 193 degenerate minima including an R_inf ≈ 5000 ridge (:168). Measured, with the misfit admitted. | yes — :164 "Not asymptotic", :168 "nothing in this sequence pins p", quoted only as diagnostics. |
| F08 | Dense solver ceiling is N = 25; its three extrapolated fits stay above the band's upper edge. | E3 | :172 claims "the hard ceiling is exact": free edges = 48·nx − 44 with nx = 2N+13; N = 26 → 3076 refused by _MIXED_DENSE_MAX = 3000 (c1_audit.py, message quoted). The N = 25 fits 3.273451/3.200400/3.189464 are extrapolants, not a run — the predictive content of the row is an extrapolation from the six points of :153-160, whose order :168 declares unidentifiable. | partial — the arithmetic ceiling is verified; that "N = 25 fits" are predictions is stated at :172 but reused at :174 as if evidence about reachability. |
| F09 | Zero of six measured points lies inside the band; the band is declared unattainable by first-axis refinement. | E3 | :174: lowest measured 3.2761300897590 is 6.0 % above the edge, and the two listed reasons are "the sequence is not asymptotically clean" and "the most optimistic fit at the hard mesh ceiling stays about 3.1 % high". Pure comparison of measured values against [2.52909192487721, 3.09111235262770]; the reachability claim rests on unidentifiable extrapolants. | yes — :174 and :143 state the bar is untouched and §9.6 revisit not invoked. |
| F10 | Lattice, domain, weighting and de-staggering variants move both operands together; worst asymmetry is 1.18 %. | E3 | :209-220 table of five variants recomputed on the same banked arrays: boundary planes dropped +0.0447/+0.0350 %, interior window −20.35/−24.10 %, trapezoid +0.0223/+0.0175 %, de-staggered +1.176/+0.2997 %. Measured variance study, but every variant is a re-reduction of the same two arrays, so it bounds reduction choices only. | partial — :220-226 bound the asymmetry at 1.18 % but the conclusion "the 44 % gap cannot be bookkeeping" is drawn for the whole 44 %. |
| F11 | The doc states convergence to 2.8101 is plausible but unproven, and indistinguishable from a limit near 3.0. | E3 | :225 "A correction, and an explicit limit": decrements −0.389/−0.337/−0.209/−0.066/−0.162 called monotone but not extrapolable; "the data cannot distinguish a limit of 2.8101 from one near 3.0". Honest self-bound on the reference, yet the same reference is used at :61 as the pass/fail reference without qualification. | yes — stated here and again at :254 (open items); not carried into §9.2 or §13.2 where R_analytic is quoted as fact. |
| F12 | The §11 claim that the head hash and line count were unchanged is withdrawn, with three hashes quoted. | X | :259-275: "the earlier claim that it had not is withdrawn"; head -51 then sha256sum was 4abbadd1… (8,124 B), "had in fact already drifted one witness further before this pass, to 323b9125…", now b6baa72… (9,008 B); the "line count unchanged (256 lines)" statement likewise withdrawn, 533 → 547 lines. §11.4 records further stale cites and non-uniform offsets +28 to +239. | yes — :358-364 "Line numbers are volatile; symbols are durable"; the withdrawal is explicit rather than silent. |
| F13 | Two rungs give an order p ≈ 0.96, explicitly labelled a consistency statement rather than a convergence result. | E3 | :399-452; two measured rungs (free_e 1444 → 2404, R 4.0489791163982565 → 3.780331990015745), h1/h0 = 0.775026165625604, p = 0.9590717710780169, p = 1 predicts Q1 within +0.27 %. Two points, two free parameters: :449-452 says "no residual, no error bar, no outlier test". | yes — explicit; rungs 2-3 named as what decides. But :512-548 notes rungs 2-4 were not yet run when written. |
| F14 | Five dense rungs keep R_extracted 26-44 % high and non-monotone, so T4_amp still FAILS at 0.272343. | E3 | :610-667; rungs 1444/2404/3604/5044/9604 with R 4.0489791163982565, 3.7803319900157453, 3.5673083405263886, 3.6127170292894397, 3.575412753195199; increments −0.2686, −0.2130, +0.0454, −0.0373; p runs +0.96/+1.22/−0.35/+0.15; rung-0 control reproduces banked R to 7.87e-13. Four of five REPRO verdicts read FAIL by design on remeshed rungs. | partial — :553-563 states this is not a convergence study; the plateau verdict (d2) is claimed from data whose increments change sign, which :668+ then has to argue. |
| G01 | Five-rung ladder increments are non-monotone (-0.269,-0.213,+0.045,-0.037); no convergence order may be claimed. | E3 | §13.3 :668-727 table; minimum at rung 2; 0-4 log-log slope -0.2508 (p=0.5015); rms(log) 0.0959 vs 0.0141 over rungs 0-2 | partial — "no order claimable" is asserted for this ladder, no alternative refinement variable is proposed |
| G02 | Registered (d1)/(d2) rule fires (d2): monotonicity fails at rung 2, not at the last rung. | E3 | rule quoted verbatim from evidence/ladder/summary_HIGHRES.txt :728-742; 1/n_free intercepts 3.36584109881959 (8.8877% above ceiling) and 3.4280430184441846 (10.9000%) | partial — doc self-flags the rule names 1/n_free while §12.3 orders in 1/h; 1/sqrt intercept 2.990608605836237 sits 3.2514% INSIDE the band |
| G03 | Route C sparse solve reproduces the dense anchor at 12807 dof to 1.78e-12 in R, 5002.9x faster. | E3 | evidence/t4/rung4_routeC_report.json: beta_sq 3.218784779622725e-12, R 1.77503391525794e-12, wall 1.955740 s vs 9784.3 s, sigma 96777.0147917196, 21 OPinv | yes — single mesh, "not a scaling law"; shift = 0.999x rung-3 beta_sq, so "cheap when bracketed", not a blind search |
| G04 | T4_amp is FAIL: |Q-1| = 0.27234263559066 against the 0.10 allowance, 2.72x over. | E3 | §13.7 :867-893; R 15.667512057780897% above the upper band edge; 510x free_e span (1444->9604); strip/y_air/z move together at every rung | partial — "(d2) eliminates THIS mesh family only"; banked Q=1.440865461991999 unaffected |
| G05 | The 205-line t4_s13_draft.md is not a pre-registration: written 43.5 s after rung-4 DONE. | X | §13.8 :918-932 draft mtime 2026-10-28 01:52:01.035717862 vs DONE 2026-10-28T01:51:17.495874934Z; draft flagged SUPERSEDED | yes — doc concedes only the (d1)/(d2) block in summary_HIGHRES.txt carries the stronger warrant |
| G06 | Five fresh meshes plus the control all fail the gate: |Q-1| 0.2207-0.3043, i.e. 2.2-2.7x allowance. | E3 | §14.3 :994-1014 tools/host/sparse-probe/out_mesh JSONs; M3 0.23615, M4 0.22074, control 0.27234; 21 OPinv each; residuals 1e-11 to 6e-11 | partial — closest approach anywhere is 2.7x out; explicit "no softening" :1030; meshes chosen after the failure |
| G07 | R humps (3.575->3.660->3.665->3.474->3.431), so nine points establish no order and no extrapolation. | E3 | §14.5 :1032-1058; rise 0.090 is twice the ladder's own largest reversal 0.045; series inverted mid-way | yes — "a hump forbids extrapolation"; no fit is performed through nine points |
| G08 | On all nine points the 1/h intercept is 3.372054, Q_inf 1.19997 = exactly 2.0x the allowance. | X | §14.7 :1077-1099 retracts the pre-rung-4 in-band reading (2.990608605836237, 3.25% inside); rms 0.0882, R^2 degrades 0.87 -> 0.7401; 1/n_free gives 3.492397 | yes — (d2) wording corrected to 1/h; both variables are now quoted rather than one selected |
| G09 | Corrections log withdraws six statements, including a shift 97101.0 that "does not exist" and a MiB/KiB error. | X | §14.8 :1100-1130: 96807.01 an arithmetic slip withdrawn, real shift 96777.0147917196 pinned in source; Q duplicates error%; --dry-run never checked; probe exit 1 a reporting bug | yes — each correction names the earlier statement it replaces |
| G10 | "Memory ceiling REMOVED, feasibility settled": 288.8 MiB vs 7.53 GB = 99x, 11.5 digits agreement. | X | §15.1 :1159-1167; 7.53 GB is §14.6 :1067's PROJECTED dense size at 30672 and 99x is against the 0.0759 GB FACTOR; peak-RSS ratio is 24.9x; the 11.5-digit agreement is at 12807 dof, no dense run exists at 30672 | no — both a projection and a smaller-mesh measurement are presented as one verified result at 30672 |
| G11 | The eigenpair is the same mode at every size: bit-for-bit reproduction, one sign change, peak pinned at HSUB. | E3 | §15.3 :1178-1222 mode_overlap.py single-process rerun d_rec=0.00e+00; cross-mesh |corr| 0.976857-0.999028; conductor corr flat at 0.998823-0.999943 | partial — same mode does not imply converged R; e_y branch test passes only 4/10 and the quoted |corr| range excludes the cited 0.969930 |
| G12 | "Eigenvalue strictly monotone decreasing, spread 3.433e-3" while its own table spans 330.97. | X | §15.3 :1187-1197 table 96752.5197...96421.5490; 330.97/96421.5 = 3.4325e-3, a RELATIVE spread printed as absolute; steps -134.71,-116.37,-69.76,-10.13 | no — the number is quoted with no unit qualifier anywhere |
| G13 | R is a weighted average of regions differing "40x", so "R converges as free_e increases" is mis-specified. | E5 | §15.5 :1264-1275 quoted ranges R_substrate 6.178-6.992 and R_air 0.855-0.960 give at most 8.18x, not 40x; §15.6 :1281 "weights 3.2x apart" vs 0.082289->0.111532 = 1.36x | partial — §15.7 :1285-1291 declares |Q-1|<=0.10 untouched and any change reserved to the project owner |
| G14 | A default-shift solve returned a spurious eigenpair (residual 0.989, |corr_ey| 0.247); lock-on is shift-dependent. | E3 | §15.8 :1292-1316 mesh 43/34/34-17-17; bogus for sigma in {96777,96656,96883,96640,97000}, true mode at {96100,96400}; axis_sweep.py ladder sigma*{1,...,.980} records sigma_retries | partial — campaign meshes cleared only by residual magnitude 1e-11 to 6e-11, not by rerun under a shifted sigma |

## Per-document tier histograms

Counted from the rows above, not typed from the sweep notes. The tier of a row is the first
pipe-delimited cell whose trimmed content is exactly `E1`-`E5`, `X` or `UNKNOWN`.

| # | document | E1 | E2 | E3 | E4 | E5 | X | UNKNOWN | rows |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `core_contract.md` | 0 | 0 | 1 | 1 | 6 | 0 | 0 | 8 |
| 2 | `cpp_solver_arch.md` | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 8 |
| 3 | `modalport_ownership.md` | 2 | 0 | 5 | 0 | 1 | 0 | 0 | 8 |
| 4 | `job_schema.md` | 5 | 0 | 1 | 1 | 1 | 0 | 0 | 8 |
| 5 | `normalization_scheme.md` | 3 | 0 | 4 | 0 | 1 | 0 | 1 | 9 |
| 6 | `visual_engine_arch.md` | 4 | 0 | 0 | 0 | 1 | 0 | 1 | 6 |
| 7 | `corr_ez_vv_threshold.md` | 4 | 0 | 3 | 0 | 0 | 0 | 0 | 7 |
| 8 | `physics_invariant_layer.md` | 8 | 0 | 1 | 0 | 5 | 0 | 0 | 14 |
| 9 | `sparse_eigenmode.md` | 6 | 0 | 5 | 0 | 3 | 1 | 0 | 15 |
| 10 | `m3c_gate_v2.md` | 4 | 0 | 7 | 0 | 5 | 0 | 0 | 16 |
| 11 | `zfree_shape.md` | 1 | 0 | 4 | 1 | 3 | 7 | 0 | 16 |
| 12 | `t4_amp_ratio.md` | 0 | 0 | 19 | 0 | 2 | 7 | 0 | 28 |
| | **total** | **37** | **0** | **58** | **3** | **28** | **15** | **2** | **143** |

**E2 is empty in all twelve documents.** Not one claim in the sweep is measured against an
independent analytic reference with the convergence rate demonstrated at three or more
resolutions. That is the shape of the corpus, not a gap in the sweep: convergence evidence in
these documents is one or two rungs and is regularly reported as absent rather than achieved.

**Counting method, and the field-position trap.** Field position is not a safe way to read
the tier. Five rows — `A13`, `A23`, `G04`, `G06`, `G14` — carry an escaped pipe inside the
claim cell, so their tier lands in the sixth field; five more — `C05`, `D04`, `D05`, `G11`,
`G13` — carry a pipe in the evidence cell and keep the tier in the fourth. An `awk` on the
fourth field alone reports `E3` 54 and `E5` 27 against the true 58 and 28. The counts above
therefore take the first tier-token cell, whatever its position.

**Row count reconciliation.** The six sweep files hold 143 rows: A 54, B 14, rest 31 (C 14 +
D 16 + `C15` 1), E 16, F 14, G 14. Earlier hand tallies summed to 144. The excess is one row,
`C15`. The C section hit its 20-word cap at `C14`, so `C15` was written in a second
`sparse_eigenmode.md` section appended after `m3c_gate_v2.md`; a tally that counts the C
range as `C01`-`C15` *and* counts the supplementary section as its own entry counts `C15`
twice. It is the only row in the sweep that can be counted twice, because it is the only row
sitting under a second heading for a document already closed. 14 + 16 + 1 = 31, not 32. The
per-file counts here are authoritative; the hand tally is used nowhere.

