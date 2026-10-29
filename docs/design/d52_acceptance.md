# Dispatch 52 — acceptance criteria

Status: NOT FROZEN. This file records what dispatch 52 must deliver and how it will be
judged. It is written before any other artifact of the dispatch is produced.

## 0. Provenance tags

Every number in this dispatch's artifacts carries a tag:

- `[VERIFIED this session]` — read out of the tree, or computed and hand-checked, during
  this dispatch.
- `[RELAYED]` — carried forward from an earlier dispatch's record without re-derivation.
- `[USER]` — supplied by the supervisor in the dispatch brief.

An untagged number is RELAYED. A tag that cannot be justified is a defect in the artifact.

## 1. Fences

1. No preservation-gate run is permitted in dispatch 52. Not a dry run, not a smoke test.
2. No edits under `emfit/`.
3. `tools/host/anchor/preservation_gate.py` is frozen and read-only. The A-1.5 module is
   frozen and read-only.
4. `decisions.md` is append-only. Existing bytes are preserved; the dispatch appends one
   block and proves the prefix by hash.
5. **Task 4 ends the dispatch.** There is no Task 5.

## 2. Task 1 — one block appended to `decisions.md`

One block, five clauses (a)–(e):

(a) The PASSes recorded for geometry A and for A-1.5 are **contrast-contingent**. They were
    obtained with an h-independent pairing tolerance that was never tested at the contrast
    where it binds. This is a statement of scope, not a retraction. No annihilation
    occurred in either run, and the contraction sequences for both are clean.

(b) A-3.5 has **no registered verdict**. `STOPPED` is an apparatus event, not a physical
    finding. The supplementary level-2 and level-3 numbers obtained at c = 2.5 are
    **non-gate evidence** of convergence at that contrast: citable as evidence, never as a
    verdict.

(c) Deficiencies D1–D7 as recorded. D1 and D7 are named as **specification defects authored
    by the supervisor**. The worker's refusal to select the favourable F1 estimator is
    credited **by name**.

(d) Over-removal: the effect is monotone in contrast, sub-power-law, with curvature −0.145
    that is mesh-independent, and the product form `g(c)·φ(h)` holds. The validity window
    ≈ c ≲ 5 is stated as an **extrapolation from three contrasts — a hypothesis, not a
    gate result**.

(e) Geometry A's five-digit independent reproduction is recorded as confirming solver
    determinism.

## 3. Task 2 — author `docs/design/pairing_rule_preregistration.md` (not frozen)

The document must contain, in this order:

1. **Defect statement**, with the three level-1 pairing distances that motivate it.
2. **One** replacement rule, chosen from exactly two options:

   (a) an h-dependent `tol(level)` derived from the second-order scheme; the constant must
       predate A-3.5, and any constant chosen by looking at A-3.5's level-1 error is a
       **fit** and voids the gate; **or**

   (b) **continuity tracking**: identify modes at the finest level, track them backward
       through the coarser levels, test pairing by the contraction sequence, and state how
       the rule distinguishes a *shifted* mode (a discretisation artefact) from a
       *disappeared* mode (annihilation).

3. **A mandatory feasibility argument**: the expected level-1 error at the contrast to be
   registered, and the margin by which the chosen rule clears it, stated *before* the run.
4. **The missing clause**: a pairing stop at level 1 that is not an annihilation stop, with
   its own verdict token, distinct from both the annihilation token and the
   measurement-failure token.
5. **Frozen gate criteria unchanged**: strict monotone decrease of the error series; per-step
   order within 1.7–2.3; the `5e-3` supporting bound; route-3 at `0.04`; the monotonicity
   flag; and an empty unpaired list.
6. **Symmetry clause**: if the new rule changes geometry A's or A-1.5's prior verdict, that
   is a **finding**, reported and not suppressed — and it must be stated in advance, not
   discovered afterwards.
7. **What the rule does not test.**

## 4. Task 3 — adversarial review before freeze

The user's requirement: construct the input that makes the gate **vacuously pass** and the
input that makes it **vacuously fail**, and report whether the pre-registration catches each.

Minimum five attacks:

| # | attack |
|---|---|
| i | zero physical modes |
| ii | correct mode count, with one mode replaced by a spurious state |
| iii | coarsest mesh only, no finer levels |
| iv | every mode annihilated at level 1 but present at levels 2–3 |
| v | contrast high enough that discretisation error exceeds the new tolerance at every level |

Attacks and outcomes are recorded **in the pre-registration, as a table**. The document is
then revised in response.

## 5. Task 4 — freeze and close out

Commit the revised pre-registration including the adversarial table. **Do not run it.**

The close-out reports: the commit; the adversarial table; every disagreement with this
brief; and a direct statement of whether the pairing rule now has a plausible validity
region, or whether the redesign should be reconsidered.

## 6. Deviations found before any editing

Two statements in the dispatch brief were checked against the tree before this file was
written. Per the rule that the artifact wins, the tree governs:

1. The brief refers to `decisions.md`. There is no `docs/decisions.md`; the file is at the
   repository root, `/workspace/decisions.md`. Task 1 appends to the root file.
2. The brief's level-1 pairing distance for geometry A at order 3 is quoted as `8.55e-4`.
   That is A's **order-1** distance (`8.54638e-04`). A's order-3 level-1 distance is
   **`8.88015e-03`** [VERIFIED this session]. The defect statement in Task 2 therefore uses
   the corrected triple: A `8.88015e-03`, A-1.5 `8.25001e-03`, A-3.5 `2.23535e-02`
   [VERIFIED this session]. The argument the three numbers support is unchanged — but note
   that A-1.5's distance is *smaller* than A's, so the three do not increase monotonically
   in contrast.

## 7. Acceptance

Dispatch 52 is accepted when, and only when: `docs/design/d52_acceptance.md` (this file)
exists; one block has been appended to `/workspace/decisions.md` covering (a)–(e); and
`docs/design/pairing_rule_preregistration.md` exists containing items 1–7, the rejection
argument for the rule not chosen, the feasibility argument, the symmetry clause, the new
verdict token, and the adversarial table.

## 8. Post-review amendment to section 4

Section 4 recorded Task 3's five attacks as predictions, written before any independent review
existed. The review has now run, so that record is closed here rather than left as a plan.

- The reviewer was given the pre-registration document and its own reading of the gate source,
  and no access to this acceptance document, the run records, or the dispatch history.
- It returned fourteen findings: six accepted as corrections to the rule, one as a correction
  to a number, three as editorial repairs, one rejected as mechanically wrong but substantively
  right, one rejected outright, and three attacks reported as not landing.
- The two blocker findings were that R3 lacked exclusivity, so two reference roots could be
  served by one computed mode and still PASS, and that no absolute accuracy floor remained below
  the finest level. Both are now respectively blocked and disclosed in the pre-registration.
- All five of section 4's predicted attacks behaved as predicted, in the sense that each is now
  caught by a named clause: (i) no seed at all returns FAILED-TO-MEASURE by R2, (ii) a spurious
  state dies at R4, (iii) an incomplete level set returns `levels_incomplete` and never PASS,
  (iv) a mode lost at the coarsest solved level returns `UNTRACKED-AT-COARSE` rather than
  STOPPED, and (v) contrast beyond the validated range returns `contrast_beyond_validated`.
- The pre-registration is now revision 2. The prediction in its section 8 was written before
  the review and was not adjusted afterwards; every accepted amendment tightens the rule, and
  none of them binds on the case the prediction concerns.

What this amendment does not claim: the review was performed by the same worker family that
performed the implementation work, so it is independent of the document but not of the
environment. No third party has examined either artefact.
