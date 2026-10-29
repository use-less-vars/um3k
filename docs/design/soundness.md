# Soundness of the claims in `docs/design/` — tiered ledger

**Written:** dispatch 52b, task 1, sections 1-5. Sections 6-10 are written by a second
pass and are appended below section 5 rather than stubbed.
**Basis:** the sweep recorded row for row in `docs/design/d52b_claim_inventory.md`
(12 documents, 13 sections, 143 rows [VERIFIED this session]).
**Provenance:** every quantitative statement is tagged. `[VERIFIED this session]` means I
measured it or read it in this session. `[RELAYED]` means it comes from a prior
dispatch's report and I did not re-open the source. `[USER]` means the brief asserted it.
An untagged number is `RELAYED` by default, so I tag actively rather than rely on that.

---

## 1. Status and consequence level

Consequence level: **MODERATE** [USER — the brief set it].

MODERATE means: if a claim in this ledger is wrong, the cost is engineering time and a
wrong published number. It does not mean a wrong number is harmless. It means the number
does not select a part, size a structure, or certify anything that people stand under.

Two disclaimers, each on its own line because burying them would defeat the point:

**This document does not claim the code is fit for any safety-critical purpose.** Nothing
in the sweep supports that, and no tier below should be read as an approach to it.

**This document does not replace build-and-measure.** A ledger entry is never a substitute
for running the thing. The strongest row here, at E1, is a mathematical argument about a
pencil; a reader who needs a number for their geometry still has to run the solver on
their geometry.

The authority question, plainly: this is one engineer's grading. It is not an accredited
assessment, not an audit by a second party, and not a consensus of anyone. One auditor,
one pass, no inter-rater check on any of the 143 rows [VERIFIED this session]. Section 9,
written in the later pass, says where I distrust my own grading; where I already know of
a soft boundary it is flagged in the row (the E3/E5 line is the soft one).

---

## 2. Vocabulary — and why it is not the brief's vocabulary

Seven grades. Each is one line.

- **E1 Proven** — mathematical argument, no numerical dependence.
- **E2 Verified** — measured against an *independent* analytic reference, convergence rate
  demonstrated, at least 3 resolutions reported.
- **E3 Characterised** — measured against some reference but with incomplete convergence
  evidence; OR a heuristic or selection rule with measured behaviour and no derivation.
- **E4 Calibrated** — agrees with an external tool or external measurement, with no
  internal error analysis.
- **E5 Asserted** — believed, stated, or derived on paper but not measured. **Not citable.**
- **X Withdrawn** — the document itself retracts, supersedes, or contradicts the claim
  elsewhere.
- **UNKNOWN** — the document does not say enough to classify it.

### 2.1 The rename, and the collision that forced it

The dispatch calls these tiers `T1`-`T5` [USER]. This document uses `E1`-`E5` instead, and
the reason is not taste. The repository already spends `T1`..`T7` on **live gate clause
identifiers**: `T1_stab`, `T2_agree` (deferred, recorded FAIL at 9.03x TOL), `T3_scale`,
`T4_amp` (recorded FAIL at 44.09%), `T5_ez_corr`, `T5_ey_corr`, `T5_fringe_excess`,
`T6_fit_route`, registered in `docs/design/m3c_gate_v2.md` sections 9 and 10.2 and
implemented around lines 634-640 of that file [RELAYED — the audit read them; I did not
re-open the file for this pass].

Those identifiers are not dormant. `T4_amp` is a recorded FAIL and `T2_agree` is scored at
9.03x its tolerance on the fit [RELAYED; rows D09, D10]. Writing "claim C1 is T2" one line
away from "T2_agree is a 4.52% measurement against a 0.5% tolerance" is exactly the
ambiguity this ledger exists to remove: two meanings for one token, neither wrong on its
own page, and a reader who picks the wrong one gets a verified claim and a failing gate
confused for each other.

The mapping is by position. No semantic change was intended; the rename is purely a
collision fix.

| brief | document | meaning |
|---|---|---|
| T1 | **E1** | Proven — mathematical argument, no numerical dependence |
| T2 | **E2** | Verified — measured vs independent analytic reference, convergence demonstrated, >=3 resolutions |
| T3 | **E3** | Characterised — measured with incomplete convergence, or heuristic with measured behaviour |
| T4 | **E4** | Calibrated — agrees with an external tool or measurement, no internal error analysis |
| T5 | **E5** | Asserted — believed, not measured, not citable |
| — | **X** | Withdrawn |
| — | **UNKNOWN** | The document does not say enough to classify |

### 2.2 Where the vocabulary comes from

It is **ours**. Defined above, for this project. The general practice of grading evidence
and tracing a claim to what actually supports it is ordinary in verification and
validation work, and that is the whole of the claim: no external standard, framework,
level scheme or published taxonomy is being invoked, and none should be cited as authority
for any tier assignment in this document.

### 2.3 Claim identifiers

Claims are `C1`..`Cn`. On first use in any document a claim id is written adjacent to the
word *claim* — "claim C3", not a bare "C3". The repository contains `c1_spectrum.npz`,
`c2b_preregistration.md`, `c2b_shapes.png`, and a bare `C2` is genuinely ambiguous between
a claim and a file. No line in this document says "see C2" without the word *claim*
nearby.

---

## 3. Scope of the sweep, and what it does not cover

Twelve documents are in scope, read in this order, with these row counts [VERIFIED this
session — from the coverage table in `d52b_claim_inventory.md`]:

| # | document | lines | row ids | rows |
|---|---|---|---|---|
| 1 | `core_contract.md` | 372 | A01-A08 | 8 |
| 2 | `cpp_solver_arch.md` | 314 | A09-A16 | 8 |
| 3 | `modalport_ownership.md` | 217 | A17-A24 | 8 |
| 4 | `job_schema.md` | 278 | A25-A32 | 8 |
| 5 | `normalization_scheme.md` | 352 | A33-A41 | 9 |
| 6 | `visual_engine_arch.md` | 436 | A42-A47 | 6 |
| 7 | `corr_ez_vv_threshold.md` | 312 | A48-A54 | 7 |
| 8 | `physics_invariant_layer.md` | 765 | B01-B14 | 14 |
| 9 | `sparse_eigenmode.md` | 777 | C01-C15 | 15 |
| 10 | `m3c_gate_v2.md` | 959 | D01-D16 | 16 |
| 11 | `zfree_shape.md` | 541 | E01-E16 | 16 |
| 12 | `t4_amp_ratio.md` | 1316 | F01-F14, G01-G14 | 28 |
| | **total** | **6639** | | **143** |

### 3.1 The cut, owned as a judgement

In scope: the documents that currently **stand** as design or measurement record — the
twelve above.

Out of scope: every `d4*_acceptance.md` and `d4*_result*` document, `d52_acceptance.md`,
this dispatch's own `d52b_acceptance.md`, and every `*_preregistration.md`.

The reason is that those are dispatch records, not design claims. They report what a
dispatch found, in past tense, under their own per-claim `[VERIFIED]`/`[RELAYED]` tags.
Tiering them would grade the process rather than the physics, and the ledger would fill
with rows that say nothing about the present.

The cost of the cut, stated rather than hidden: **this ledger cannot claim to have tiered
everything in `docs/design`. It has tiered everything standing.** If the boundary is read
differently by a supervisor, the fix is to add documents and rows, not to rebuild the
method.

### 3.2 How the sweep was done

One auditor, one pass, per-document reads, with a cap of about 14-16 rows per document
(`t4_amp_ratio.md`, at 1316 lines [VERIFIED this session], was split into two halves of
14 rows each). Load-bearing claims were prioritised over exhaustive extraction, so the
143 rows are a **prioritised census, not an exhaustive one**: a claim the document spends
a paragraph on is in, a claim it mentions in a subordinate clause is usually out.

The full sweep is committed as `docs/design/d52b_claim_inventory.md`, row for row, with
per-document tier counts computed from the rows rather than typed. Committed, not left in
`.scratch/`, because a gitignored inventory is not evidence — it is a file on one machine
that a reader of the claim cannot consult. `job_schema.md` is the worked example of what
that costs: its J1-J7 criteria are asserted to have been frozen before any artefact
existed, the pre-registration that would show the ordering lives in gitignored, unversioned
`.scratch/`, and the ordering is therefore unverifiable today and tiers E5 (row A32).

---

## 4. The result that matters: E2 is empty

Zero of 143 rows earned E2 [VERIFIED this session].

The histogram, counted from the rows rather than hand-tallied [VERIFIED this session]:

| E1 | E2 | E3 | E4 | E5 | X | UNKNOWN | total |
|---|---|---|---|---|---|---|---|
| 37 | 0 | 58 | 3 | 28 | 15 | 2 | 143 |

Two counting notes for anyone re-deriving this. The tier cell is not at a fixed field
position: five rows (`A13`, `A23`, `G04`, `G06`, `G14`) carry an escaped pipe in the claim
cell, so a naive `awk` on the fourth field reports 138 rows in total and E3 54 / E5 27
against the true 58 / 28 [VERIFIED this session]. Re-counters should match on
`^(E[1-5]|X|UNKNOWN)$`, first matching cell, whatever its position.

What the empty column means, without euphemism: the project has **one** independent
analytic reference — the partial-height PEC closed box — and it is never used as a
convergence yardstick. It is used once as an anchor, at a single mesh, against a 0.02
tolerance that is itself asserted rather than derived (rows A01, A02). Everywhere else the
numeric comparisons are against another module's own output, against a fit on the same
data, or against a second discretisation of the same geometry. That is enough for E3, and
it is not E2, and the difference is not pedantry: an E3 number can be wrong in a way the
comparison cannot see, because a second discretisation shares the first one's assumptions.

The consequence for the gate is direct. **No gate criterion may be given the force of an
independently verified claim, because there are none.** The strongest thing a criterion can
inherit from this ledger today is E3 plus a stated scope, and it should be written that way.

Two things would change the column, and both are cheap relative to what the corpus already
spends (thousands of lines and multiple 300-second-capped solves [RELAYED; rows A14, C01]):

1. Pick one geometry with a separable analytic solution and sweep it at three or more
   resolutions, reporting the observed order. The anchor protocol in row B13 specifies
   exactly this and has never been run.
2. State the order that is observed even when it is not two. A measured order of 0.96, or
   the finding that no order is identifiable, is an E2-grade result if it is done against
   an independent reference at 3+ resolutions; what keeps the corpus at E3 is that neither
   is reported as a convergence measurement (rows F13, G01).

---

## 5. The claim ledger

Two rules govern everything below.

**A row's tier is a ceiling.** No claim here is promoted above the tier of the inventory
row or rows it rests on, and a claim resting on two rows takes the weaker.

**Promotion requires names a measurement or an argument, not "more evidence".** Every
`promotion requires` cell below says what specific thing is missing. If I could not name
it, the claim is not in 5.1.

**AMENDED (dispatch 54).** Two of the rows this ledger rests on were demoted after this section
was written: A17 and A18 are UNVERIFIED at `pairing_rule_preregistration.md:477-483`. C1 loses one
of its four rows and C9 loses both of its own. The two claim rows below are amended in place, and
section 13 carries the reasoning and the tier each of them lands on.

### 5.1 Citable claims

| id | claim | tier | scope limit | evidence (row ids) | depends on | expires when | promotion requires |
|---|---|---|---|---|---|---|---|
| C1 | claim C1: the eigenfrequency beta agrees with the analytic value for a closed PEC box partially filled with dielectric, eps_r in [1.5, 3.5], levels 1-3 | E3 | that geometry, that eps_r range, levels 1-3 only. No level 4+, no open boundaries, no extrapolation in eps_r. The vacuum anchor holds at one mesh only (row A01) | A01, A19, A20 -- A18 lost to UNVERIFIED, section 13; three of four remain | C2, C3 | any change to the sigma policy, to the mode-selection argmax (row C13), or to the box geometry | an independent analytic reference for the *dielectric-filled* box, swept at 3+ resolutions with the observed order reported. The E2 scope is the target, not the current grade: what exists is a 1.022e-4 anchor in vacuum and a converging-but-orderless +0.90/+0.64/+0.48% eigen route (rows A01, A19) |
| C2 | claim C2: homogeneous-region deflation is exact when eps_r = mu_r = 1 in the deflated regions | E3 | eps_r = mu_r = 1 regions only. Nothing here licenses a dielectric block | C11, C05, C04 | — | a change to B or M_C assembly | a written proof, 3-5 lines of linear algebra, that the deflated spectrum carries the full physical spectrum plus only the k0^2 null block. The doc states exactness and proves inertia and symmetry; the exactness sentence is asserted (rows C04, C05, C11 are E1 for the structure, not for the exactness) |
| C3 | claim C3: deflation is safe in the presence of dielectric — **HYPOTHESIS** above eps_r 3.5 | E3 | measured at eps_r <= 3.5 only. eps_r up to about 5 is EXTRAPOLATED and is a HYPOTHESIS in this claim, not a result | C10, A09, C11, C08 | C2 | an indefinite M_C at any rung ends this: the nonsingularity is one rung, 1927 x 1927 (rows C10, A09) | one inertia computation per rung at eps_r = 1.5 / 2.5 / 3.5 / 5.0 on the target mesh |
| C4 | claim C4: the S-parameters are quotable | E5 | none: nothing about quotability is measured | D09, F14, G04, G06 (each a recorded FAIL against it) | C1, C19 | the recorded T4_amp and T2_agree FAILs stand until superseded | a recorded T4_amp pass inside a stated band on 3+ meshes with a demonstrated order and a stated error bar, plus T2_agree inside 0.5%. Until then every S-parameter number is a diagnostic |
| C5 | claim C5: sparse route C reproduces the dense reference and is thousands of times cheaper per solve | E3 | measured on rungs up to 12807 dof. The target-mesh cost is EXTRAPOLATED from two points (row C09, E5) and is not part of this claim | C03, G03, A11, C08, C07 | C2, C3 | a change to the splu ordering or the shift policy | a route C solve at rung 4 on the target mesh, measured, not fitted through two rungs |
| C6 | claim C6: the pencil has the structural properties the solver assumes: B indefinite, every block but c D c^T exactly symmetric, h SPD with the negativity in the Schur complement, sigma an input rather than an output | E1 | the audited assembly path only (`mode2d.py`, `c1_audit.py`) | C04, C05, C06, C11, C12, C14 | — | the moment the assembly changes; a code edit, not new evidence, expires this | nothing: E1 is the ceiling |
| C7 | claim C7: the seven invariants are blind to a curl-curl sign flip and to a coupling sign flip, and coupling detection is conditional on the modal share s_c | E1 | detection is conditional: order 2 eps s_c, so a small modal share hides a 1e-3 perturbation (row B07) | B05, B06, B07, B11, B14 | — | a change to I1-I7 or to the normalisation | nothing |
| C8 | claim C8: the numeric tolerances are derived rather than picked — gamma_n from u = 2^-53, the residual bound in the B^-1 norm, and the mixed pencil's 1e-3 kept as a diagnostic | E1 | the symmetric pencil. The mixed pencil keeps no proven bound, by construction (row B04) | B02, B03, B04 | — | a change to B or to the residual definition | nothing |
| C9 | claim C9: two different bases on one geometry disagree on beta by 5.46% -- **WITHDRAWN**, section 13 | **Withdrawn** | one mesh, 1444 free edges; the harness that produced the comparison is itself suspect (row B10) | B08 only -- A17 and A18 lost to UNVERIFIED, section 13 | — | re-running the harness on a banked capture | the same comparison on 3 meshes with the harness repaired and reviewed |
| C10 | claim C10: `job_schema` rejects malformed input, closes every property-bearing node, and distinguishes exit 1 (checked and wrong) from exit 2 (could not check) | E1 | the schema as committed; per-observable tolerances deferred to v2 | A26, A27, A29, A31 | — | a schema revision | nothing |
| C11 | claim C11: the schema example does not reproduce `demo_microstrip_stub` — the example is unloaded, the demo defaults to load_value 200.0 at 12.8 mm | E1 | arithmetic on cited defaults against the schema field map | A30, A31, A33 | — | a change to `demos.py` defaults or to schema v2 | nothing |
| C12 | claim C12: an independent validator agrees with the schema on the shipped example | E4 | agreement with a second library; no internal error analysis | A25, A28 | — | a jsonschema major-version change | a validator written against the standard by someone else, plus an external check of the 21-keyword inventory (row A28 is the validator's own self-report) |
| C13 | claim C13: the printed e_y/e_z ratio 2.722397e6 is exactly 1e8 times a physical ratio | E1 | the specific print site in `s10118_split_check.py` | A33, A34 | — | a change to the print site or the cell constant | nothing |
| C14 | claim C14: the quasi-TEM bracket puts R in [3.9e-3, 2.5e-1] at L = 0.2 mm | E1 | a property of the estimate, not of the solution; L is a chosen length, not a measured one | A38, A34 | — | a different estimate of the longitudinal scale | nothing |
| C15 | claim C15: the unit-repaired Scheme A ratio is 0.0272 with about 7% mesh spread, roughly 2.9x above Scheme C, and the spread sits inside rms_e_z | E3 | three meshes, no reference value; Scheme C was withdrawn as a reference definition (row A37, X in section 7) | A35, A36, A39, A40 | C13, C14 | Scheme C being reinstated, or a new reference definition | an independent reference for R — the analytic y-air manifold is the obvious candidate — at 3+ resolutions with the observed order reported |
| C16 | claim C16: the visual-engine size arithmetic holds: an 82.4 MB field grid, 282,217 bytes left for a viewer, and a shipped test that forbids client-side script on all five page types | E1 | arithmetic on cited runs and the shipped test | A42, A43, A45, A46 | — | a change to the response budget or to `test_demo_picker.py` | nothing |
| C17 | claim C17: the correlation bars are reproducible from their operands and move no banked verdict — T = L - 2 S_good gives 0.91 for T5_ez_corr and 0.89 for CORR_EY_MIN | E3 | the bar is self-referential and records reproducibility, not correctness (rows A48, A51) | A48, A49, A50, A51, A52, A53, A54, D01, D03 | — | any new banked leg | an independent discriminator: a leg that fails the bar whose defect is established by something other than the bar |
| C18 | claim C18: T5_ez_corr and T5_fringe_excess discriminate — banked legs pass by 1.9-2.9 spreads, the column-704 witness fails by 62 spreads; both fringe legs exceed 2.0 at 1.42x and 1.45x, and no bar in (1.0, 2.849) rescues them | E3 | e_z correlation and the fringe ratio only. The 0.91 bar is not transferable to corr_e_y (row A54) | D04, D05, D06, D07, E15, E14 | C17 | a new leg | one banked leg designed to pass that an independent check also passes, and one designed to fail that an independent check also fails |
| C19 | claim C19: T4_amp FAILS — R_extracted 4.0489791163982565 against the analytic 2.810102138752, 44.09% high, Q = 1.4409 — and five dense rungs plus five fresh meshes keep it 15.7-44.1% high and non-monotone | E3 | this mesh family only (row G04). The band itself is uncited (row F04, section 5.2) and the closure diagnostics passing does not rescue the verdict (row D16) | D09, D15, D16, F14, G04, G06, G14, A24 | C1, C15 | any change to R_analytic's definition or to the band | a convergence order from 3+ rungs, which needs a solver ceiling above N = 25 (row F08) |
| C20 | claim C20: first-axis refinement cannot reach the band — the air band gives extrapolants from 1.86 to 5.93 (144.7% spread), the order is unidentifiable, and the lowest measured point is 6.0% above the edge | E3 | the first axis and the dense ceiling. The strip band is flat to 0.13% (row F05) | F01, F05, F07, F08, F09, F10, F11, F13, G01, G02, G07 | C19 | a new axis, a coarser family, or a different R definition | an identifiable order: monotone increments over 3+ rungs with the observed order stated |
| C21 | claim C21: the mode is the same mode at every mesh size — bit-for-bit reproduction in-process, one sign change, peak pinned at HSUB | E3 | the sizes compared; identity is by overlap, not against an analytic mode | G11, A15, A16 | — | a change to the extraction | an analytic mode shape for the same geometry |
| C22 | claim C22: the `z_free` shape defect is not a resolution effect — beta and eps_eff move 0.645% and 0.324% between meshes while corr_e_z stays wrong | E3 | two meshes; the comparison is scalar to scalar | E08, E09, E14, E10 | — | a repaired longitudinal right-hand side (row E11, section 5.2) | re-running the correlation after the RHS repair and showing corr_e_z above the bar |
| C23 | claim C23: the analytic reference is within 0.74% of Hammerstad-Jensen, bounding reference error under 1% | E4 | the one geometry; an external formula only, no internal error analysis | E10 | — | a different reference construction | an independent impedance standard, or a measurement |
| C24 | claim C24: the gate constants are sized by arithmetic from measured nulls — an 8.13e-11 thread null, a 9.79e-12 round-off — and the reproduction gate is exercised at four decades of margin | E3 | single samples, no repeats or variance (rows A12, A14) | A07, A12, A13, A14, D14 | — | a change to the gate constants | repeat runs with variance on the thread null and on the incumbent timings |
| C25 | claim C25: the strip-centre boundary condition requires a node there, and the analytic A_ez shows exactly one sign change per row at column 16 | E3 | measured tally is threshold-dependent (row E14); the boundary condition is analytic (row E01) | E01, E14 | — | a change to the mesh or to the reference construction | a same-component comparison at the strip centre on 3+ meshes |
| C26 | claim C26: `emfit/modal.py` is absent from the repository; the only copy is in `.scratch/`, so a reader cannot re-run any row that depends on it | E1 | the package search plus the `sys.path` append (row A22) | A22 | — | the file being committed under version control | nothing — but note the consequence: rows computed through that file are unreproducible by a reader until it is committed |


### 5.2 Asserted, not citable

Every E5 and UNKNOWN row is accounted for here — 28 E5 and 2 UNKNOWN [VERIFIED this
session]. Nothing is omitted, because a ledger that lists only the citable material
implies the rest is settled. Withdrawn rows are not here; they belong to section 7.

| row | what is asserted | who asserts it | the one measurement that would make it citable |
|---|---|---|---|
| A02 | SELF_TEST_BETA_TOL = 0.02, described as ~200x the measured 1.022e-4 | the gate script's literal | repeat the anchor at 3 tolerances and report the null spread |
| A03 | dropping the k_q term would make beta^2/k0^2 read 1.0 instead of 0.4383 | a code comment | run once with k_q removed |
| A04 | ANCHOR_DT = 1.9065748695309721e-13 s | a driver literal | derive dt from the stated CFL limit at the anchor grid and show equality to the literal |
| A05 | ANCHOR_N = 4,894,400 on ANCHOR_GRID = (322, 200, 76) | a grid-bound literal | count free unknowns from the banked mesh |
| A06 | a second 769,356,828-byte sparse copy exists at run time | a driver comment | measure peak RSS against the two-copy prediction |
| A08 | no bitwise determinism across machine, thread count or BLAS | the author's limitation statement | the same capture on two machines, byte comparison |
| A23 | a proposed extraction-consistency gate | the document, explicitly "proposed, not derived" | execute it on the four banked legs and report which pass |
| A32 | the J1-J7 criteria were frozen before any artefact existed | the author | a committed, dated pre-registration. It is gitignored today, which is why the row is E5 and not E1 — see section 3.2 |
| A41 | every V/m in the document is a dimensional inference | argued from basis scaling | carry a unit end to end through one run and compare |
| A44 | six browser-free acceptance tests are specified, none executed | the document asserts verdicts over bytes and numbers | run the six |
| B01 | seven invariants I1-I7 specified; none tested | the status block states it writes no test | write one test per invariant and inject one defect each |
| B09 | a figure labelled passivity reads 2.0013807961296104 | quoted with no provenance | re-extract from the named matrix and print the singular values |
| B10 | the s10118 harness dropped `1j` and applied `np.abs` | a reading of an untracked script | commit the script and re-run the comparison |
| B12 | mixed-pencil asymmetry 8.2e-17 relative, 3.8e-17 absolute | "a numerical check", no provenance | measure it on a banked pencil and print the four numbers |
| B13 | the anchor protocol: exact transcendental root by in-test bisection, meshes h to h/8, expected order p = 2 | the protocol is stated; no numeric result is reported | run the four-mesh protocol |
| C01 | the dense path on the target mesh needs 16.7 GB per matrix and ~41 days | labelled ESTIMATED, inherited arithmetic | time one QZ step at a runnable size and fit the exponent |
| C09 | target-mesh route C cost 0.0843 GB / 0.156 s, 127.99x under route A | labelled EXTRAPOLATED, two-point power law | one route C run at rung 4 |
| C13 | the global argmax of beta^2 may select the most oscillatory mode rather than the fundamental | the document says it did not measure this | print the mode index and its overlap across the whole spectrum |
| D02 | the 0.89 population is two PMC legs; a disputed third leg would give 0.86 | arithmetic on the two legs | bank the third leg and recompute |
| D08 | T4_amp has no threshold and therefore cannot fail | an absence, recorded as such | the threshold existing and being registered — this one is promoted by *adding* the missing object, not by measuring |
| D11 | T1_TOL = 0.005 is "measured, not derived" | a provenance comment | re-derive it from the 12x mixed-basis span |
| D12 | T3_TOL = 1e-5 gates only the plane_Ey slot; the flux route is blind at 1.0256e-8 | the code, and a sensitivity ladder | gate the flux route as well and re-measure the blind spot |
| D13 | T6_fit_route reuses 0.005 | registered with no implementation | fit twice on independent data and report both |
| E11 | the longitudinal solve is fed a real beta where 1j*beta is needed | source reading, replicated in three re-implementations | run both right-hand sides and compare the sign structure |
| E12 | the field comes from inverting (k_zz - k0^2 m_zz) rather than differentiating | code reading plus a textbook smoothing property | compute the derivative route and compare the sign counts |
| E13 | a masked per-row sign census is the cheapest decisive measurement (1.6 s claimed) | a specification, never executed | execute it |
| F04 | the +/-10% band is "the standard engineering target" | an uncited assertion | cite a source, or derive it from the cross-section accuracy |
| G13 | R is a weighted average of regions differing by 40x, so "R converges as free_e grows" is mis-specified | quoted region ranges | compute R region by region on one banked capture |
| A37 | Scheme C ratio 0.00951415 from cached arrays, withdrawn 2026-10-26 as a reference definition | the document, which withdrew it | a re-derivation from a documented reference definition (see section 7) |
| A47 | the isosurface library's licence and encumbrance are unverified | the document, marked OPEN | a licence file or a vendoring record in the tree |


---

## 6. Document by document

Section 4 said how the ledger distributes. This section says where it came from: what each
document contributed, and what in each one is the claim I would remove first if I had to
remove one. Line counts, row counts and tier spreads are the committed histogram [VERIFIED
this session]; the findings are the readings behind rows I can name.

| document | lines | rows | tier spread | the finding that matters most |
|---|---|---|---|---|
| `core_contract.md` | 372 | `A01`-`A08` (8) | E3 1, E4 1, E5 6 | The `0.02` self-test tolerance is reused as the swap gate with no derivation (row A02); three driver literals are grid-bound with nothing counting them (rows A04, A05, A06); the one calibrated claim is a wall time (row A07). |
| `cpp_solver_arch.md` | 314 | `A09`-`A16` (8) | E3 8 | Nothing above E3. Every measurement is one size with no independent reference and no reported convergence; the costing rows are single samples (row A14); row four of the section 5 criterion table cites nothing measurable. |
| `modalport_ownership.md` | 217 | `A17`-`A24` (8) | E1 2, E3 5, E5 1 as committed; graded E1 2, E3 3, E5 1, UNVERIFIED 2 -- A17 and A18, section 13 | The `+5.46%` and `+8.61%` gaps are measured against a "reference" the document admits is a fit on the same capture (rows A17, A18). `emfit/modal.py` is absent from the repository (row A22), so no reader can re-run the comparison. |
| `job_schema.md` | 278 | `A25`-`A32` (8) | E1 5, E3 1, E4 1, E5 1 | J1-J7 are said to have been frozen before any artefact existed, and the preregistration sits in gitignored `.scratch` (row A32). The five E1 rows are E1 because they are arithmetic and commit history, not measurement. |
| `normalization_scheme.md` | 352 | `A33`-`A41` (9) | E1 3, E3 4, E5 1, UNKNOWN 1 | A `1e8` unit defect inside a printed ratio (row A33), found and traced and repaired. The repaired ratio still rests on no reference (rows A35, A39), and every V/m in the document is a dimensional inference (row A41). |
| `visual_engine_arch.md` | 436 | `A42`-`A47` (6) | E1 4, E5 1, UNKNOWN 1 | A proposal whose own discipline statement says no code ran and nothing was measured (row A44). Its load-bearing content is a negative: the shipped test forbids client-side script on all five page types (row A45). The isosurface library's licence is unverified (row A47). |
| `corr_ez_vv_threshold.md` | 312 | `A48`-`A54` (7) | E1 4, E3 3 | 12 of the document's 15 numbers carry full line citations, and the 3 that do not are exactly the ones used to derive a rival `0.89` bar (row A54, then row D02). |
| `physics_invariant_layer.md` | 765 | `B01`-`B14` (14) | E1 8, E3 1, E5 5 | Seven invariants with tolerances genuinely derived from `u = 2^-53` and from a residual bound (rows B02, B03, B04), and no measured invariant result at all (row B01). Every case-dependent factor is "to be measured", so the criterion row's UNMEASURED is correct rather than lazy (row B14). |
| `sparse_eigenmode.md` | 777 | `C01`-`C15` (15) | E1 6, E3 5, E5 3, X 1 | Section 1 says no `eig`/`eigsh`/`eigs` call was made; section 4.2 reports `eigsh` runs on four routes. Section 9 narrows section 1 retroactively and section 1 carries no such limit on its face (row C15). |
| `m3c_gate_v2.md` | 959 | `D01`-`D16` (16) | E1 4, E3 7, E5 5 | Section 6.1 says `T4_amp` "still cannot fail"; section 10.2 and section 12.1 register the plus-or-minus 10% bar and record a measured FAIL at 44.09% against it (rows D08, D09). Section 6.1 is superseded text and it is still in the file, 450 lines above the entry that supersedes it. |
| `zfree_shape.md` | 541 | `E01`-`E16` (16) | E1 1, E3 4, E4 1, E5 3, X 7 | 7 of 16 rows are withdrawn. The surviving quantitative pillars compare the reference's vertical component against the pencil's longitudinal component, which the file's own banner calls different physical quantities, while the body still says the sections stand (row E16). The "two independent meshes" claim has no second independent mesh: the second leg is `corr_ez[0]` of a different grid's npz (rows E02-E07). |
| `t4_amp_ratio.md` | 1316 | `F01`-`F14`, `G01`-`G14` (28) | E3 19, E5 2, X 7 | The pass bar is uncited: "the standard engineering target", adopted after the 44.09% miss was known (row F04). `R` as a weighted average of regions differing by an order of magnitude makes "converges as `free_e` grows" mis-specified (row G13). |

Two documents carry most of the real evidence. `physics_invariant_layer.md` is the only one
where tolerances are derived rather than chosen and where structural properties of the
pencil are proved: eight E1 rows of fourteen, and the derivations are in the text (rows
B02-B07). `corr_ez_vv_threshold.md` is the most citation-dense of the twelve: twelve of its
fifteen numbers carry line numbers, and it is short enough that I checked all fifteen.

Two documents carry the most retrieval risk. `m3c_gate_v2.md` is 959 lines in which a
superseded sentence sits in section 6.1 and its refutation sits in section 12, so a reader
who stops at section 6 quotes the first as current. `t4_amp_ratio.md` is 1316 lines with
seven live retractions and no errata block: the withdrawn reading and its replacement are
both in the body, and a search that lands in the middle returns a number that was withdrawn
two hundred lines earlier. Neither file is wrong to keep the old text — this project's
append-only rule requires it. Both files are wrong not to say, at the top, that the text
below is a chain.

---

## 7. What the documents have withdrawn from themselves

### 7.1 What X means here, and the one row that will not settle

X is the grade for a claim the document itself retracts, supersedes or contradicts
elsewhere. It is not a finding of error. An X row is usually a claim the author caught, and
the catch is the evidence; the grade records that the sentence is still readable, not that
somebody blundered.

Fifteen rows are X [VERIFIED this session]. That is the committed histogram's count, and it
is complete in the sense that fifteen is what the inventory counts — not in the sense that I
hunted for withdrawals in text I had not already read for another reason.

One row will not settle, and I am recording the choice rather than hiding it. Row A37
(Scheme C, `0.00951415`, withdrawn 2026-10-26 as a reference definition) is counted UNKNOWN
in section 4's histogram and read as a withdrawal in claim C15. I have not moved the
histogram. The reason both readings survive is that the row as written is a withdrawal note
rather than a claim, and the note does not say what replaced it: UNKNOWN is "the document
does not say enough", and X is "the document withdraws it", and this row does both. It is
the only row in 143 where I could not decide by reading, and section 9 records what I think
that says about the other 142.

### 7.2 The fifteen withdrawn rows

| row | document | what was withdrawn | what stands in its place |
|---|---|---|---|
| C15 | `sparse_eigenmode.md` | Section 1: "no `eig`/`eigsh`/`eigs` call was made while producing it" | Nothing in section 1. Section 9 narrows the ban to assembly measurements, 690 lines later. |
| E02 | `zfree_shape.md` | The `z_free` sign census: 0 of 483 negative at 31x17 against 483 of 483 at 41x22 | Nothing. A vertical field's expected sign behaviour applied to a longitudinal solution (appendix, class (c)). |
| E03 | `zfree_shape.md` | "The shape defect is real and converged-wrong on two independent meshes" (0.1192, 0.1473) | Nothing. The 0.1473 leg is `corr_ez[0]` of a 31x17 npz, not a 41x22 run. |
| E04 | `zfree_shape.md` | "The transverse leg is sound, so the defect is longitudinal" | The measurement survives as a two-mesh like-for-like comparison (class (b)); the inference drawn from it does not. |
| E05 | `zfree_shape.md` | The 0.028131 PEC-to-PMC shift, "23.6%", "180x the mesh floor" | A corrected `+0.0016430`, about `10.5x`, and then a disclaimer of even that quotient. The 180x is stated flat 100 lines above the correction. |
| E06 | `zfree_shape.md` | The forward map "peaks at 0.77, a 15.2% ceiling" | Only "0.77 is a property of `c`". The ceiling was never priced against the quantity actually scored. |
| E07 | `zfree_shape.md` | The sign reversal at the strip boundary (-0.1995 under, +0.3842 outside) | A property of the pairing, not of the extraction. The 31x17 counterpart was never read. |
| E16 | `zfree_shape.md` | The banner's SUPERSEDED against the body's "not withdrawn here" | No single status statement survives. Three append-only layers contradict the body and each other. |
| F06 | `t4_amp_ratio.md` | A three-mesh `O(h)` extrapolation to 2.86-3.32, called "inside the band" | The same trend is called "mostly the first-axis air band". The band's upper edge is 3.0911, so "inside" was never true even before the retraction. |
| F12 | `t4_amp_ratio.md` | Section 11's head-hash and line-count claim, three hashes quoted | An explicit withdrawal and the rule "line numbers are volatile; symbols are durable". The pattern — a prefix hash asserted after an append — recurs. |
| G05 | `t4_amp_ratio.md` | A 205-line draft as a pre-registration | A timestamp: the draft was written 43.5 s after rung-4 DONE. It is flagged SUPERSEDED in place. |
| G08 | `t4_amp_ratio.md` | The pre-rung-4 in-band reading, 2.9906, 3.25% inside | A 1/h intercept of 3.372054 and `Q_inf` 1.19997. Both refinement variables are now quoted rather than one selected. |
| G09 | `t4_amp_ratio.md` | Six statements in one corrections log | Named replacements, one per statement. The shift `97101.0` and the working note `96807.01` are both wrong; the committed shift is 96777.0147917196. |
| G10 | `t4_amp_ratio.md` | "Memory ceiling REMOVED, feasibility settled", 99x at 11.5 digits | Nothing. 7.53 GB is a projection at 30672 and the 11.5-digit agreement is at 12807; the measured peak-RSS ratio is 24.9x. |
| G12 | `t4_amp_ratio.md` | "Strictly monotone decreasing, spread `3.433e-3`" | Nothing. The table spans 330.97, and 330.97/96421.5 is 3.4325e-3: a relative spread printed as absolute. |

The pattern is worth one paragraph because it is the only general finding in this section.
Fourteen of the fifteen sit in two documents, and both are append-only chains in which each
pass appends a correction to a file it will not edit. That is a defensible discipline and it
is why the record is trustworthy; it is also why the files are unreadable front to back. The
retraction is often less prominent than the claim: E05's 180x is stated flat in the body and
corrected four hundred lines later, and F06 retracts a range as "mixed-band" without
noticing that the range was never inside the band it was being compared to. A reader who
wants one number should read the last layer. Nothing in the tree tells them there is a last
layer.

### 7.3 `m3c_gate_v2.md`: two statements, both in the file, one of them governing

Section 6.1 at `:496` reads: "**Verdict: still cannot fail — on the threshold, not the
datum. Do not ship.**" Section 10.2 at `:665` registers the bar, and section 12.1 at `:873`
records the measurement: `R_extracted = 4.0489791163982565` against
`R_analytic = 2.8101021387524523`, `Q = 1.440865461991999`, a relative error of
`44.086546199899894 %`, outside the registered `|Q − 1| <= 0.10` band, whose interval is
`[2.52909192487721, 3.09111235262770]` [VERIFIED this session].

The text that governs is the one with a measurement behind it and a datum it can act on —
section 10.2 and section 12.1. A clause that cannot fail cannot select, which is this
document's own rule at `:57`; once a threshold exists the clause can fail, and the recorded
`44.09 %` is it failing. The correct reading of section 6.1 is that its *verdict* is
superseded and its *"Do not ship"* survives for a different reason: `T4_amp` appears in no
`.py` file in the tree, so the clause still has no executable.

The document already says this, at `:947`, in a table row that names `:496` and answers it.
That row is 450 lines below the sentence it corrects, in a section a reader reaches only by
reading to the end. So the file passes its own audit and fails its reader. This is the one
place in twelve documents where I would ask for an edit rather than a note.

### 7.4 The passivity figures: withdrawn, and what re-derivation would look like

Two figures, `1.0142899588259895` and `2.0013807961296104`, were carried as passivity
[RELAYED — the audit read them; I did not re-open `physics_invariant_layer.md` for them].
The second is above one on a structure with no loss mechanism, and that is not a tolerance
question. A ratio of reflected-plus-transmitted power above one on a passive structure is a
statement that the structure is not passive, and no error analysis rescues it: either the
normalisation is wrong, or the quantity is not what it is labelled, or the field is not a
field of that problem.

The document itself cannot trace the number to a computation (row B09), and the project's
own record has already withdrawn the label: `decisions.md:8503` says the result file contains
no `s11` key and no `s21` key and no derivable source key, that the figures are withdrawn as
measured passivity, and that the rejection of that basis stands on physical impossibility
[VERIFIED this session]. So the ledger is not making a new finding. It is recording that a
withdrawn figure is still printed in a document that a reader will read as current.

Recorded here as withdrawn pending re-derivation. Re-derivation is a short list and I am
writing it down so it is not a mood: name the matrix, the port set and the normalisation the
figure was formed under; print `s11` and `s21` for the lossless box and for the loaded case;
show that the two figures are a power ratio and not a raw overlap; and state what the
quantity is, if it is not passivity. If no such computation exists, the figure is deleted
rather than recomputed, and section 2.1-2.3 of that document, which already says so, is the
text that stands.

### 7.5 `t4_amp_ratio.md` section 15.8: a residual that annihilates the number it is beside

Mesh `43/34/34-17-17` solved at the default shift returned a spurious eigenpair: residual
`9.89e-01`, `|corr_ey|` `0.247`, `R` `0.2370`. The lock-on is shift-dependent, not
mesh-dependent — sigma in `{96777, 96656, 96883, 96640, 97000}` all returned the bogus pair,
and sigma in `{96100, 96400}` returned residual `1.9e-12` and the true mode, `lambda`
`96534.897941162`, `R` `3.612955819639116` [VERIFIED this session].

Two things follow, and they point in opposite directions. The first is that a residual of
`9.89e-01` against an acceptance of `1e-6` is six decades out; a solver can announce this
kind of failure, and this one did, in the record. The second is that the mitigation is a
post-hoc tool: `axis_sweep.py` walks a descending shift ladder and accepts only residual
`< 1e-6`, and the campaign meshes predate it. Their clearance is by residual magnitude,
`1e-11` to `6e-11`, not by a rerun under a shifted sigma [VERIFIED this session].

So the numbers are not void, and the honest statement is narrower than "the hazard is
everywhere". Any figure from a run whose residual is not printed beside it inherits the risk,
because a lock-on that converged to `1e-6` would not be visible at all; the test that
discriminates is the residual, and it only discriminates when it is printed. The document
also shows that where the solve is genuine the shift is not a confound: `R` varies by at most
`6e-12` and `lambda` by at most `4e-10` over sigma `96100`-`96777` [VERIFIED this session].

The one measurement that closes this is cheap and I would put it above most of section 8's
list: re-solve one campaign mesh at sigma `96100` and at the default, and print `lambda`,
`R` and the residual for both. If they agree to the stated `6e-12` and `4e-10`, the campaign
is cleared for that configuration and the hazard is confined to the record that documented
it. If they do not, every number from that probe is in question, in this document and in
any other that used the same one.

### 7.6 Clauses the record itself has voided, and an honest count

The briefing asks for three void clauses from dispatches 50 and 51. I searched the record for
them and the search does not return three of that name. `decisions.md` is 8652 lines and 81
of them contain the word "void"; in the dispatch 48-52 region exactly one states that a
clause is void [VERIFIED this session]:

1. **Amendment 3's widened-preservation clause**, void as authored rather than failed
   (`decisions.md:8596`). It required a finite-mesh solver to reproduce a continuum root to
   `1e-12`, which is unsatisfiable by between 7.8 and 10.3 orders on this ladder. A clause
   that cannot be met cannot be failed, and the nine measurements taken under it are
   diagnostic evidence and may not be cited as either outcome.
2. **Falsifier F1**, vacuous under its own literal derivation (defect D1,
   `decisions.md:8626`): the estimator reads no A-3.5 datum and returns `0.886463` whatever
   A-3.5 does. Only the following equivalent-prediction line makes F1 a test.
3. **The pairing and annihilation branch**, which fired on a discretisation artefact at
   contrast 2.5 on the coarsest rung (`decisions.md:8616`, defect D4): an `h`-independent 2%
   band sat inside the discretisation error of the scheme it was inspecting, and the run
   stopped although no mode had disappeared.

One is void, two are vacuous or mis-specified, and the distinction matters. A void clause
proclaims its own impossibility; a vacuous one returns a fixed number and looks like a test.
Two of the three would have passed a reader who did not derive them, and one of them is a
falsifier.

I record this because it calibrates section 7's other finding. This record is capable of
withdrawing a clause when a clause cannot fail — it does so, in writing, with the arithmetic
— so a superseded sentence left readable in `m3c_gate_v2.md` is a document defect and not a
standing policy of the project. And the same record shows how hard a cannot-fail clause is to
see: it takes a second derivation, not a second reading.

---

## 8. What I would do first, in order

Ranked by consequence per unit of work, not by interest.

**(a) One separable analytic geometry, at three or more resolutions, with an observed
order.** This is the only route to any E2 row in the ledger, it is the cheapest claim in the
document, and the protocol already exists on paper: an exact transcendental root by in-test
bisection, meshes from `h` to `h/8`, an expected order of `p = 2` (row B13). Two documents
already have the pieces — row F13's two-rung order and row G01's non-monotone ladder are
both attempts at this from measured data that was never designed for it. Nothing else in
this list converts eleven E5 rows and nineteen E3 rows into anything stronger.

**(b) Re-derive three E1 rows from scratch, as a spot check on the audit rather than on the
documents.** E1 is where I trusted my own reading hardest and checked least: a mathematical
argument either transfers or it does not, and the ledger's authority rests on 37 rows of
"nothing to check" [VERIFIED this session]. Three rows, chosen by someone else, re-derived
without my notes. If one fails, the tier counts in section 4 are not usable.

**(c) A second auditor re-tiering the 28 E5 rows.** This is the boundary with the most work
riding on it and the least measurement behind it — 58 E3 against 28 E5 [VERIFIED this
session] — and it is the cheapest possible test of whether my discriminator is stable. Give
the second auditor the section 2 definitions and the rows, not my reasons.

**(d) The two blockers that keep `physics_invariant_layer.md` unmeasured even after a run
happens.** I6 as specified fails on the mixed path today: it normalises in the plain 2-norm
against a documented `e^T B e = 1`, which is the code-document mismatch left OPEN at
`decisions.md:7008` (row B11). And I4/I5/I6 need per-case condition numbers that nothing in
the tree computes (row B14). Anyone who runs the seven invariants next will get seven
results and no verdict on six of them, so this is a prerequisite, not a follow-up.

**(e) The section 7.5 residual audit, across documents.** One configuration, one shifted
sigma, three printed numbers. It closes a hazard that is currently bounded by an argument
rather than by a measurement, and it costs a solve.

The first action is (a). The reason is not that it is the most urgent — (d) is — but that it
is the only item on the list that changes what the ledger can say. Everything else here
improves my confidence in a grading. (a) creates the first E2 row this sweep could ever
record, and until one exists the vocabulary in section 2 has an empty category and the whole
ledger is capped at E3 by construction.

---

## 9. Where I think this is wrong

This section distrusts the artefact rather than the documents. The heading is not modesty;
each item below is a way the ledger could be wrong while every row in it is right.

**AMENDED (dispatch 53).** The reasoning below is right that E2 could be unsatisfiable by
construction; the conclusion drawn from the empty row is wrong. E2 is empty because the
instrument is uncalibrated, not because the category is null. See section 12.
**(a) The E2 bar may be unreachable by construction, which would make E2 a null category.**
E2 requires an *independent* analytic reference with a demonstrated convergence rate at three
or more resolutions. In this problem class the only independent reference in the tree is a
partial-height PEC box, and a box is separable only where the geometry is separable. If the
independent reference and the multi-resolution requirement cannot be hosted on the same
configuration — because the geometries that have closed forms are not the geometries the
solver is exercised on — then E2 is unsatisfiable as I have defined it, and the empty row in
section 4 is a fact about my definition and not about the documents. I did not test that. If
it is true, the honest repair is to split E2 rather than to leave an empty column implying
that everything measured was weak.

**(b) The E3/E5 boundary carries more weight than any other line in the document, and it is
the one line I cannot defend.** 58 rows are E3 and 28 are E5 [VERIFIED this session], and
the discriminator between them is "measured against some reference with incomplete
convergence evidence" against "stated but not measured". That is a judgement about what
counts as a measurement, and it is swayable by how confident a document sounds: a paper that
says "we measured" in a table caption moves a row up a tier. A second auditor would move, I
would guess, a third of the ledger, and I do not know in which direction. I would rather say
that than quote 37/58/28 as if it were an instrument reading.

**(c) The scope cut in section 3.1 is a judgement, not a measurement.** Twelve documents,
143 rows, a cap of 14-16 rows per document chosen for reading cost. A different reader with
the same method would have cut differently and arrived at a different 143. The counts are
reproducible from the committed inventory; the *selection* is not reproducible at all, and
the inventory records my selection rather than testing it.

**(d) The ledger repeats the failure it was written to catch, one level up.** The nine
original errors were all specifics: a mis-paired metric, a unit defect, a superseded
threshold. This document is 143 specifics with tier assignments that no one has checked —
myself included, since I assigned them while reading for the errors. That is one level up,
not one level out. The concrete repair is in section 8: re-derive three E1 rows and re-tier
the 28 E5 rows with a different auditor, and if either moves, discard the histogram rather
than caveat it.

**(e) Addition — the denominator is unknown, and the document reads as if it were 143.** The
census was prioritised: I read for load-bearing claims, and 143 is what I found, not what is
there. A document that says "143 claims, of which 37 are E1" invites the reading that the
rest of the tree is empty. It is not; I did not look for it uniformly.

**(f) Addition — my own tags are not checkable by the reader.** `[VERIFIED this session]`
means I measured it in a session that no longer exists to be inspected. For row-level figures
I worked from the committed inventory at `docs/design/d52b_claim_inventory.md` rather than
re-opening twelve documents for this pass, which is the right economy and is not the same
thing as verification. Where a reader wants to test me, sections 4, 7.2 and 7.3 are the three
places where my arithmetic is short enough to redo by hand.

---

## 10. Provenance and change log

Written on dispatch 52b, by one auditor, in two passes: sections 1-5 in the first, sections
6-10 in the second. Six inventory passes produced the rows — A (documents 1-4), B, the
remaining five documents, then E, F and G — and the criteria this document is meant to
satisfy are stated in `docs/design/d52b_acceptance.md`, which also records the report figures
I quoted from.

Four deviations from that acceptance criteria document are pre-registered there rather than
discovered here: the tier rename from `T1`-`T5` to `E1`-`E5` (that document's section 7.1,
forced by the live gate clause identifiers `T1_stab` through `T7`); the scope cut (7.3); the
two-file split between this ledger and the claim inventory (7.4); and the tally reconciliation
behind 144 against 143 (7.5), which was a double count of row C15. That document's section
7.1 also records that its own sections 7.4 and 7.5 were appended at end of file rather than
in place, to preserve a 11169-byte prefix hash.

The tagging rule is the one at the head of this file and it has not changed: `[VERIFIED this
session]` for what I measured or read, `[RELAYED]` for what came from a prior dispatch, `[USER]`
for what the brief asserted, and an untagged number defaults to RELAYED. Row-level detail in
section 7.2 comes from the inventory rather than from a fresh read of the source documents,
which section 9 records as a limit and not as a style.

Figures I independently verified in this pass, so that a reader knows which numbers to
distrust first if this document is wrong:

- 143 rows across 12 documents and 13 sections of them; per-document line counts 372, 314,
  217, 278, 352, 436, 312, 765, 777, 959, 541, 1316, totalling 6639.
- The histogram 37 E1, 0 E2, 58 E3, 3 E4, 28 E5, 15 X, 2 UNKNOWN.
- The field-position failure of a naive awk pass over the same table: 138 rows with E3 54 and
  E5 27, from ten rows whose cells contain an escaped pipe.
- The 15 X rows of section 7.2, and the per-document spread of section 6 including the
  reconciliation of each row to its document.
- Row C15's double count, which is the whole of the 144-against-143 discrepancy.
- For section 7.3: `R_extracted`, `R_analytic`, `Q`, `44.086546199899894 %` and the band
  interval, read at `m3c_gate_v2.md:868`, `:875` and `:947`.
- For section 7.4: the withdrawal entry at `decisions.md:8503`.
- For section 7.5: the residual `9.89e-01`, the five bogus sigmas, the two clean ones, and
  the `6e-12` and `4e-10` shift sensitivities, at `t4_amp_ratio.md:1292-1316`.
- For section 7.6: the single void clause at `decisions.md:8596`, and the vacuous falsifier
  and pairing branch at `:8626` and `:8616`.

**One stale sentence, recorded rather than edited.** The header at `:3-4` still says this
file "stops after section 5 rather than stubbing them", which stopped being true when this
block was appended. I have not edited it, because the append was checked against a prefix
hash and rewriting the header would break the check that proves no earlier byte moved. It is
superseded by this paragraph, which is the same treatment this document asks for in section
7.3 and the same treatment the project applies to its own record.

## 11. Appended at end of file: the pairing rule's adversarial review, and one row carried nowhere

Appended after section 10 rather than inserted, for the reason section 10 gives: no earlier byte
moves, so every line number above this one still holds.

**Where it is, and that none of it ran.** `docs/design/pairing_rule_preregistration.md` section 10
is a pre-freeze adversarial review of that rule -- fourteen findings, six accepted as corrections,
revision 2 -- and its section 11 is six gate-level attacks (AT-1 to AT-6) with the report each
would produce and the revision that would close it. None of the six was executed: no code was run
and no record exists, so they are constructed attacks and not demonstrated vulnerabilities. They
are recorded because the mechanism of each is stated and can be confirmed or dropped by one run.

**The one ledger consequence.** No row of section 5.1 cites the pairing step (checked), so no
claim moves today. The consequence is not local, though: a vacuous PASS from AT-4 or AT-1 is
indistinguishable in form from a real one, and the same verdict and record format is what any
future evidence for claim C21 (E3, mode identity across mesh sizes) or claim C3 (E3, deflation
safe with dielectric) would be made of. A gate that can return an empty PASS is a reason to
distrust its verdicts generally, not only the input that produced that one.

**One inventory row that survives into neither table.** Row B14 (E1, `physics_invariant_layer.md`)
records that the "physics invariants (9.1)" row of the acceptance table stays UNMEASURED pending
a pre-registered normalisation change. It is cited as evidence inside claim C7 (line 224) and in
section 6 (line 304) and section 8 (lines 513-514), but it has no row of its own in 5.1 or 5.2 --
so a reader of the ledger alone cannot see that the criterion row is empty because a
pre-registration is queued, not because a test is missing.

## 12. Amendment to section 9(a): E2 is empty because the instrument is uncalibrated

Section 9(a) asked whether E2 might be unsatisfiable by construction. The question was the right
one; the answer is no, and the conclusion drawn from the empty row was wrong. This section records
the correction. Section 9(a) is not edited in place and its text stands as written.

**Ruling.** E2 is not a null category. The row in section 4 is empty because the gate that would
have produced the numbers is known to be foolable seven ways, so it cannot certify what it
measured. That is a statement about the instrument. It is not a statement about the corpus, and
this section exists so that the two cannot be read as one.

**The evidence.** Geometry A, eps_r = 3.5, three resolutions. The measured orders are 2.0068,
2.0378, 2.0337 at `preservation_gate_preregistration.md:53-55`,
`preservation_gate_results_a35.md:63-65` and `decisions.md:8620` [VERIFIED this session]. A
first-order Nedelec discretisation (Whitney 1-forms) predicts order 2, so this is the convergence
rate E2 asks for: three resolutions, and a reference the solver did not produce.

Two defects in that evidence, recorded because they bound it.

(i) The second order is not consistent across its three copies -- 2.0087 at
`preservation_gate_preregistration.md:54` against 2.0089 at `preservation_gate_results_a35.md:64`
and `decisions.md:8620` [DISCREPANCY, UNRESOLVED]. Which copy is the transcription error has not
been found, so the rate is quoted to three figures and no tighter.

**AMENDED (dispatch 55A).** The discrepancy in (i) is resolved, and the defective copy is the
preregistration. The two residuals the rate rests on are committed at
`preservation_gate_results_a35.md:64` -- 1.264530e-04 and 3.141941e-05 -- and
log2(1.264530e-04 / 3.141941e-05) = 2.0088732694540137, so the second order is 2.0089. The cell at
`preservation_gate_preregistration.md:54` reads 2.0087 and is the transcription error; that file is
frozen and is not edited here, and the full record is the D54 ERRATA entry in `decisions.md`
(`:8734`, `:8738`, `:8740`). The rate is quoted as 2.0089, and (i)'s sentence about three figures is
superseded.

(ii) A second pair of orders, 1.9819 and 1.9955, is sometimes cited alongside the first. It is not
citable: the only records are `.scratch/d50/pg_a15.json:775-776` and the run log, and the inputs
are nowhere in the tree. It corroborates; it is not evidence, and it is not used here.

**The distinction.** Two claims are available here and they are not the same claim. The first is
that a convergence measurement exists for E2, on a configuration with a demonstrated rate. That is
true. The second is that the measuring instrument is trustworthy. That is not yet true. E2 stays
empty because the second claim fails, not because the first one does; a ledger that reports an
empty E2 without saying which of the two it means overstates what was found out.

**Consequence for the ledger.** The E2 count of 0 is a statement about the gate's calibration, not
about the corpus. It must not be read as "no E2 evidence exists", and no reader of section 4 alone
is entitled to infer that nothing was measured. When the gate is repaired the row becomes fillable
from evidence already in the tree; until then it stays empty, and its emptiness is a to-do about
the instrument, not a finding about the documents.

Section 9(a) proposed splitting E2 rather than leaving an empty column that implies everything
measured was weak. The split is not made here -- E2 remains one row -- because the implication 9(a)
worried about is removed by the two paragraphs above instead: the column is empty for a reason local
to the gate, and this section says so where a reader of the row will come looking.

This section was appended on dispatch 53 rather than edited into sections 9 or 10, for the reason
section 10 already gives at its end: the text up to the former final line stays byte-identical.
Stripping what dispatch 53 appended re-hashes the remainder to 56975 bytes /
`4c861fbbd0c7814edeaaee9dbbc67e83bc81b54c659e3b53dcfb87baea5c5f5c`. It sits after section 11
rather than after section 9, so it reads as an appendix to an amendment; section 9(a) is meant to be
read with it open.

---

## 13. The A17/A18 demotion, and the two claims it reaches

The pairing rule demoted two ledger rows after sections 5 and 6 were written, and the ceiling rule
in section 5 is what makes that the ledger's problem rather than the rule's. This section records
the demotion, the rows it reaches in this document, and the tier each affected claim lands on. It
is appended rather than woven in, for the reason section 10 gives at its end: everything above
keeps the bytes it already had, except the five sites named near the bottom of this section.

**What was demoted, and where the demotion is written.** Rows A17 and A18, both from
`modalport_ownership.md`. The rule is section 4.4 of `docs/design/pairing_rule_preregistration.md`:
each row's reference ladder was built from a converged run's own output on another geometry, which
the rule names as inadmissible route 5 (`:404-407`, `:435-437`). The consequence is expressed as
retroactive and it is not softened: the recorded numbers are kept, the order verdicts are
withdrawn, and the rows "count as **UNVERIFIED**, and any later document that cites them must say
so" (`:477-483`); the re-derivation is outstanding and is not scheduled by that revision
(`:972-977`). The demotion is written in the pairing rule and not in
`preservation_gate_preregistration.md`, which carries no A17/A18 text at all.

**The rule being applied, quoted, because the grading below is arithmetic and not judgement.**
Section 5: "A row's tier is a ceiling. No claim here is promoted above the tier of the inventory
row or rows it rests on, and a claim resting on two rows takes the weaker." Two consequences
follow, and they are not the same consequence. A claim that loses a row it did not exclusively
depend on loses breadth; its ceiling is recomputed over the rows that survive, and it can come out
unchanged. A claim that loses its whole evidential basis does not get a lower grade, because a
lower grade is a statement about evidence and there is none left to make it about.

**Claim C1 -- loses A18, lands on E3, on three rows of four.** C1 rested on A01, A18, A19 and A20.
A18 is the post-repair placed route (+5.46 / +5.52 / +5.58 % over three meshes) and it is one of
the claim's two measurement legs; A19 is the eigen route (+0.90 / +0.64 / +0.48 %) and A20 is the
`sum(e_z^2)/sum(e_y^2)` drift that says the ratio is not converged. A18 goes and the other three
stay. All three surviving rows are E3, so the ceiling is still E3 and C1's grade does not move.
What moves is what C1 is entitled to say: it no longer carries the placed route, so the
+5.46 / +5.52 / +5.58 % series is not citable on C1's authority, and what is left is a one-mesh
vacuum anchor against a closed-form value plus an orderless eigen route against a reference that
is not independent. The evidence cell says this; the tier cell does not change. A grade that
survives a demotion by arithmetic and a grade that survives it by inattention are identical in a
table nobody touched, and separating the two is the whole of the work here.

**Claim C9 -- loses A17 and A18, lands on Withdrawn.** C9 said that two bases on one geometry
disagree on beta by 5.46 %. Its evidence cell named B08, A17 and A18. A17 and A18 are not
supporting legs of that claim, they are its subject: the disagreement C9 reports is the one those
two rows measure. B08 is the harness row, and that row's own scope cell already records that the
harness which produced the comparison "is itself suspect" and that the comparison is one mesh of
1444 free edges. One suspect survivor and a withdrawn measurement is not a weak E3, and it is not
an E5 either, because the number C9 exists in order to state is A18's number. It is marked
**Withdrawn** in section 5.1 rather than degraded, on the reasoning `docs/design/d54_acceptance.md`
section 5 states and this ledger accepts: a degraded claim invites a later reader to treat it as
weak evidence when it is not evidence at all. If the placed route is re-derived against an
admissible ladder, C9 is re-entered from the new rows and not resurrected from these.

**What did not change, and the dependants.** C1 is depended on by C4 and C19; its grade did not
move, so neither dependence is invalidated, and a reader who traces C4 or C19 back to C1 traces it
to an E3 claim resting on three E3 rows. No row in 5.1 names C9 in its `depends on` cell, so the
withdrawal propagates no further. Section 6 is a statement about the inventory's committed tier
cells, and those cells are deliberately left reading E3 where the demotion was recorded, so the
`modalport_ownership.md` spread is annotated in place: the inventory grades that document E1 2,
E3 5, E5 1, and the graded spread is E1 2, E3 3, E5 1, UNVERIFIED 2, over the same eight rows. The
inventory file is not edited here, and neither is any other document's copy of these rows.

**Citing these rows from now on.** Any document citing A17, A18 or C9 must say the rows are
UNVERIFIED and that the re-derivation is outstanding; `pairing_rule_preregistration.md:483`
requires that sentence and is not satisfied by a bare row number. The recorded numbers are not
retracted. What is retracted is their use as convergence-order evidence, as validation of any
constant, and as precedent for a ladder construction.

**The revision the pairing rule says was not made.** That revision records at `:979-981` that
`soundness.md` and `decisions.md` were untouched. That was true of the revision. It is not true of
the dispatch, and this section is the point at which it stops being true; `decisions.md` carries
its own entry.

**The five sites, and the byte accounting.** Section 5.1 now carries one inserted marker above the
table, the C1 evidence cell loses A18, the C9 row reads **Withdrawn** with both lost rows named,
section 6's `modalport_ownership.md` tier-spread cell is annotated, and this section is appended.
Nothing else in this file moved. The pre-state is 709 lines, 60839 bytes, sha256
`15a7c0290ef137e40b6a0baec186bca0b6dd2db6f171de611571e4714f96bbab`, and that digest is
reproducible: reverse the four substitutions above, delete every byte after the former final line,
and hashing the result returns exactly that value. The post-state line count, byte count and digest
are not carried inside this file, because writing them here would change the very bytes they
describe; they are cited externally instead, in version control and in the dispatch ledger entry for
this revision, each of which records the file's hash against the file's content. The check is not a
prefix claim, because this revision edits four lines as well as appending: reconstructing the
post-state from the pre-state by those four substitutions and by the bytes after its former final
line reproduces the post-state digest recorded there exactly, so no byte outside the five named
places moved.

**Byte accounting after dispatch 55A.** Section 12's defect (i) is amended inside section 12 itself,
in bytes that dispatch 53 appended, so the amendment cannot reach a strip of that append. That is
measurable rather than argued: truncating immediately before the `## 12.` heading, with the blank line
that precedes a heading counted as part of that heading's block, returns 57809 bytes / 662 lines /
`d6834154b2554c1a822b1ff534d1b55c8c77b346f300b7cc5c2d6202baea9f70` both before and after this
dispatch, byte for byte. Section 13's recipe needs one reversal more than it names: undo the
dispatch-55A amendment as well as the four substitutions, then delete every byte after the former
final line.

The two byte figures those sections carry were **not** recomputed at dispatch 55A, and this is the
place to say so: neither reproduces from the text that survives. Truncating before `## 12.` gives
57809 bytes against section 12's 56975, a gap of 834; truncating at the former final line gives 61417
against section 13's 60839, a gap of 578. The two gaps differ by 256 bytes, which is an arithmetic
consequence of the two figures themselves: section 12's appended block measures 3608 bytes, so
56975 + 3608 = 60583 cannot equal section 13's 60839. At most one of the two figures is right, and
neither can be re-derived without the pre-dispatch-54 text, which this tree no longer carries. Both
sections keep the bytes they have; this is a disclosed defect in sections 12 and 13, not a repair,
and closing it is not dispatch 55A's to do.
