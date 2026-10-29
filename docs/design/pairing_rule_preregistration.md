# Pairing rule pre-registration

## 0. Ledger consequence, written before the rule is frozen

This block was added after the rule was drafted and before it froze. It answers three questions
a reader of `docs/design/soundness.md` will ask, without moving that document's ledger: a
pre-registration promotes nothing on its own, and section 8's prediction demotes nothing.

**What a pass promotes: nothing, and nothing above E3 by construction.** No row of that ledger's
section 5.1 cites the pairing step, so no claim's "promotion requires" column names a pairing
run. The two rows a pass can support are claim C21 (E3, "the mode is the same mode at every mesh
size", whose scope limit says "identity is by overlap, not against an analytic mode") and claim
C3 (E3, "deflation is safe in the presence of dielectric", a HYPOTHESIS above eps_r 3.5). A
pass adds a pre-registered, reference-root-based cross-mesh identity result at one contrast to
claim C21's evidence, and a measured absence of mode loss at contrast 2.5 to claim C3's. It meets
neither promotion requirement: claim C21's is "an analytic mode shape for the same geometry" and
claim C3's is "one inertia computation per rung at eps_r = 1.5 / 2.5 / 3.5 / 5.0". The ceiling
is not E3 for want of data either: E2 is an empty category in that ledger (section 4, zero of 143
rows), so there is no grade between E3 and E2 for a result of this kind to occupy, and a reader
who expects this rule to produce one is expecting the vocabulary to award something it has never
awarded.

**What a fail would demote.** Claim C21 (E3) is the row a clean FAIL contradicts: if a mode is
not the same mode at two mesh sizes on this geometry, the sentence "the mode is the same mode at
every mesh size" is false for that geometry, and the ledger has no grade meaning measured-and-
refuted. The nearest available action is withdrawal in the sense of its section 7.1 -- a FAIL
here moves claim C21 from E3 to X, or forces a cut-down scope; E5 would be the wrong
destination, because E5 means believed but unmeasured and would understate a counterexample.
Claim C3 (E3) is not demoted by the same failure: it is a statement about M_C's nonsingularity,
measured by inertia, and a mode that evaporates does not make a matrix indefinite. What a FAIL
removes is the reading of the contrast-2.5 record as "nothing was lost", which claim C3 does not
carry. A FAILED-TO-MEASURE demotes nothing: that is the point of the token, and section 4.2
exists so that a physics failure cannot be laundered into one.

**What happens to claim C1 if this fails: nothing.** claim C1 (E3) is that beta agrees with the
analytic value for a closed PEC box partially filled with dielectric over eps_r in [1.5, 3.5] at
levels 1-3, and it rests on inventory row A01's 1.022e-4 vacuum anchor plus rows A18-A20, not on
the pairing step. A pairing failure is a statement about which computed eigenvalue is identified
with which reference root -- identification and tracking -- and not about the distance between a
beta and its analytic value: the distances are this rule's input, and they are recorded whether a
pair is accepted or refused. A-3.5 makes it concrete: the frozen gate's STOPPED left 2.23535e-02
unpaired at level 1, and that number is as usable as evidence about beta accuracy after the
refusal as before it. So a FAIL here leaves claim C1 untouched, removes claim C21 (E3), and
endangers claim C3's (E3) reading of the contrast-2.5 record as a record of nothing lost.

## 1. Status and scope

This document specifies a replacement for the frozen preservation gate's pairing step. It does
not modify the gate. `tools/host/anchor/preservation_gate.py` is frozen and is not edited by
this dispatch; the rule below is specified for a future module and, when implemented, must be
registered as a new gate and not as an amendment to that file.

**Status: pre-registered, not in force.** This document is committed at dispatch 52 Task 4. It
authorises no run. Declaring its thresholds binding is a separate act that has not occurred.

Scope: the pairing step only. The falsification criteria that consume the paired errors --
monotone decrease, per-step order in [1.7, 2.3], the `5e-3` supporting bound, route-3 at
`0.04`, the monotonicity flag and the empty-unpaired-list requirement -- are carried over
unchanged and are restated in section 7 so that no reader has to assume it.

Geometry, mesh ladder and solver are unchanged from the frozen gate: `LEVELS = (1, 2, 3)`,
i.e. `ny` in {16, 32, 64}, `k0 = 1407.433509`, `sigma = 990434.5409`, `t = 0.001953125`,
`b = 0.0078125`, `k_candidates = 16`, `arpack_budget_factor = 40`, solver
`emfit.mode2d.solve_modes_deflated_v2`.

## 2. The defect

The frozen gate pairs each analytic reference root to a computed candidate if and only if

    e = |beta - beta_root| / |beta_root|  <=  PAIR_TOL = 2e-2

and it applies that same constant at every level. At the two contrasts where the gate has
ever issued a PASS this constant was never doing any exclusion work. The level-1 pairing
distances at order 3 are:

| geometry | contrast `c = eps_r - 1` | level-1 distance at order 3 | fraction of `2e-2` |
|---|---|---|---|
| A     | 1.0 | `8.88015e-03` | 0.444 |
| A-1.5 | 0.5 | `8.25001e-03` | 0.413 |
| A-3.5 | 2.5 | `2.23535e-02` | 1.118 |

All three figures are `[VERIFIED this session]`. The third exceeds the constant; the first two
use less than half of it. Two consequences follow, and both are the defect:

1. **At the contrasts where the gate passed, the tolerance was not tested.** A rule that has
   never rejected anything is not evidence that it rejects nothing wrongly.

2. **At the contrast where it binds, the tolerance stopped the run without any physical event
   to report.** The A-3.5 record `.scratch/d51/pg_a35.json` stopped at level 1 with orders 3
   and 4 unpaired at 1.118 and 3.549 times the tolerance, on a mesh whose eigensolve had
   converged 16 of 16 candidates with no abort. No mode had disappeared. The recorded verdict
   was `STOPPED`, whose reason string names possible annihilation.

A third fact, measured on all four records held, governs the design: **no candidate was
eligible for more than one reference root at any level of any record**, so the number of
eligible candidates per root was 0 or 1 everywhere. The tolerance therefore never had to
discriminate between two competing claimants. Its only effect was to decide whether a track
was reported at all, which means its value controlled the run's ability to measure and not
the run's ability to distinguish. That is why the repair below removes the absolute test
rather than tuning it.

Note on provenance: an earlier statement of this defect quoted `8.55e-4` as geometry A's
order-3 level-1 distance. That figure is A's *order-1* distance (`8.54638e-04`); A's order-3
distance is the `8.88015e-03` tabulated above. The corrected triple is used throughout. The
correction does not weaken the argument, but it shows that the three distances do not increase
monotonically in contrast: A-1.5's is slightly the smaller of the first two.

## 3. Which repair, and why not the other one

Two repairs were available. This document selects the second, and the rejection of the first
is arithmetic rather than preference: the alternative fails on numbers that were measured
before the document was written.

### 3.1 Rejected: an h-dependent tolerance

The proposal is `tol(level) = tol_1 * 4^-(level-1)`, justified by the second-order rate of
the scheme. It is rejected for three reasons.

**It cannot be chosen without fitting A-3.5.** Pairing all four reference roots on the
level-1 rung at contrast 2.5 requires an absolute level-1 tolerance above `7.09799e-02`,
the order-4 level-1 distance, which is 3.549 times the frozen `2e-2`. Any constant that
predates A-3.5 must be derived from data at contrast 1.0 or below, where the largest
level-1 distance observed is `8.88015e-03`. Ten times that datum is `8.9e-2`, which clears
the required `7.098e-2` by only 1.25 times. A constant whose value is governed by the
single datum it must accommodate is a fit, whatever story is attached to it, and a rule
fitted to the case that motivated it cannot gate that case.

**At the width that works, the test is inert.** A level-1 tolerance of `8.9e-2` exceeds the
largest level-1 distance seen anywhere on this line by 1.25 times, and exceeds the level-1
distances at contrast 0.5 and 1.0 by a factor of ten. Under it no annihilation at the coarse
rung could be detected, and the coarse rung is where an annihilation signal is largest. The
repair would buy a pass at contrast 2.5 by removing the gate's ability to fail anywhere.

**It tests the wrong quantity.** An absolute distance at a fixed level does not separate a
mode that has disappeared from a mode that has been badly approximated; both produce a large
distance. Only the behaviour of that distance as the mesh refines separates them, and a rule
that thresholds a single rung is by construction blind to it. This is the same defect as D7
recursively: the repair relocates the constant, it does not change what is measured.

### 3.2 Selected: continuity tracking

The physical spectrum does not depend on the mesh. Its computed image does, and the image's
error is smooth in `h` at a rate fixed by the discretisation scheme. Identity should therefore
be established from the *sequence* of errors across levels rather than from a distance at one
level. That replaces an untestable absolute constant with a testable prediction -- the rate --
and the rate is a property of the scheme that predates every geometry in this project.

The rule keeps the frozen `2e-2` exactly where the frozen gate's use of it was never in doubt:
at the finest level, where the discretisation error is smallest. At contrast 2.5 the worst
finest-level error is `4.73091e-03`, which is 0.2365 of that band, so the constant still
separates and is still doing legitimate work there. It removes the absolute test only at the
coarser rungs, where it was never validated and where it binds.

## 4. The rule

Notation: `L = 3` is the finest solved level; frozen reference roots `r_o`, `o = 1..n`, in
descending order; `C_k` is the set of computed candidates with real `beta` on level `k`;
`e_{o,k} = |c - r_o| / r_o` for the candidate `c` assigned to root `o` at level `k`.

**R1 -- Seed (finest level only).** For each root `o`, let `c*` minimise `e_{o,L}` over
`C_L`, giving `e_{o,L}`. The root seeds if and only if both hold:
  (a) `e_{o,L} <= SEED_TOL` with `SEED_TOL = 2e-2` (unchanged);
  (b) the assignment is a **mutual nearest neighbour**: `r_o` is also the nearest reference
      root to `c*`. Condition (b) needs no constant and settles attribution when two roots
      compete for one candidate.
No absolute test is applied at any level other than `L`.

**R2 -- Instrument control.** A root that fails R1 may be reported as annihilated only after
four preconditions hold.
  - If no root seeds at all: **FAILED-TO-MEASURE** -- reason `no seed: instrument not working
    at this contrast/level`. A run that cannot see its own reference modes has measured
    nothing, and it may not return PASS.
  - If root `o` does not seed while another root's candidate lies inside root `o`'s own
    `SEED_TOL` neighbourhood: **FAILED-TO-MEASURE**, reason `attribution_conflict`. One
    candidate competing for two roots is an attribution failure, not physics, and reporting
    it as annihilation would reintroduce the defect this document exists to repair.
  - The level-`L` spectrum must be demonstrably complete: the real-beta candidate count at
    `L` must exceed the number of reference roots, and the ARPACK iteration budget must not
    have been exhausted, both read from the run record. Otherwise **FAILED-TO-MEASURE**,
    reason `spectrum_short`: absence from an incomplete candidate set is not absence from the
    spectrum.
  - STOPPED is licensed only at contrast `c <= 2.5`, the range over which `SEED_TOL` has any
    validation (section 5, section 9.6). Above it, **FAILED-TO-MEASURE**, reason
    `contrast_beyond_validated`.
  - With those met and root `o` still unseeded: **STOPPED** -- annihilation suspected, the
    reason string naming the control roots and which preconditions held.

**R3 -- Backward tracking.** For `k = L-1` down to `1`, for each live track: let `S` be the set
of candidates `c` in `C_k` with `|c - r_o| / r_o <= TRACK_WINDOW * max(e_{o,k+1}, E_FLOOR)`,
`TRACK_WINDOW = 6.0`, `E_FLOOR = 1e-12`. The floor exists so that an exact match at the
previous level does not collapse the window to zero: without it the most accurate seed would
be the one that cannot be tracked.
  - `|S| = 1`: the track continues; record `e_{o,k}` for that candidate. Assignment is
    **exclusive at every level**: a candidate may serve at most one track. A collision is
    **FAILED-TO-MEASURE**, reason `assign_collision`, never resolved by distance, because
    distance is precisely what the collision has already failed to decide.
  - `|S| = 0`: the track cannot be continued at level `k`. See R5 -- this is not annihilation.
  - `|S| >= 2`: **ambiguous**, FAILED-TO-MEASURE (`ambiguous: more than one candidate inside
    the tracking window at level k`). No silent tie-break on distance.

**R4 -- Contraction test.** For every consecutive pair on a track, `rho_{o,k} = e_{o,k} /
 e_{o,k+1}`, and the pair is accepted only if `RATIO_LO <= rho_{o,k} <= RATIO_HI`, with
`RATIO_LO = 2.5` and `RATIO_HI = 6.0`. If `e_{o,k+1} = 0` then `rho = +inf`
by definition, which lies outside the band and returns that same non-verdict; P2 is
correspondingly unevaluable when its denominator is zero. The upper edge of the band is
redundant with R3, whose window already bounds this ratio by `TRACK_WINDOW`; it is retained
so the constant reads as a band, and R4 in practice rejects *too-fast* contraction only. A
track with any pair outside that band is **not
paired**: **FAILED-TO-MEASURE**, reason `track exists but does not converge at the scheme
rate; candidate not identified`. A spurious computed state that happens to sit near a root on
the finest mesh does not contract at the scheme rate, and dies here.

**R5 -- Coarse-untracked.** `UNTRACKED-AT-COARSE` (section 6) is reserved for a level that was
solved, contained candidates, and yielded `|S| = 0` for a track that seeded at `L`. It is not
PASS, not FAIL, and not an annihilation report. A level that was never solved is a different
thing and must not be reported as a tracking failure: if the recorded level set is not the
full `LEVELS`, the outcome is **FAILED-TO-MEASURE**, reason `levels_incomplete`, naming the
missing levels. A single-level run therefore never returns PASS and never returns
`UNTRACKED-AT-COARSE`.

**R6 -- Verdict.** Once every root is paired on every level, P1, P2, P3 and the route-3 check
are evaluated exactly as frozen (section 7). A root that produced `e_{o,k}` for all `k`
supplies them; a root that did not cannot supply P1, and P1 is then unevaluable rather than
satisfied.

### 4.1 Constants and their provenance

`SEED_TOL = 2e-2` is the existing `PAIR_TOL`, unchanged in value, retained only where it was
validated.

The band constants are **not** independent of measured data, and claiming otherwise would
repeat the error section 3.1 convicts. `TRACK_WINDOW = RATIO_HI = 6.0` and `RATIO_LO = 2.5`
are width factors on the scheme's second-order ratio of 4, giving `[4 / 1.6, 4 * 1.5]`. The
ladder ratio 4 is the scheme's. The widths 1.6 and 1.5 were chosen so the band contains every
contraction measured in this project with margin while remaining strictly wider than the band
P2 implies (section 4.2). That is a calibration, and it is disclosed as one.

What matters is what the calibration was allowed to decide. The band contains all eight
measured per-track contractions -- 3.751, 4.561, 4.061, 3.799, 3.934, 4.126, 4.020, 3.949 --
with margin 1.50 at the lower edge and 1.32 at the upper, binding at order 2 between levels 1
and 2. It was not narrowed or widened to reverse any verdict, and it did not decide the A-3.5
outcome: what moved that outcome was seeding at the finest level, not the ratio band. The
rejected `tol_1`, by contrast, had to be set above `7.09799e-02`, the failing datum itself,
for its verdict to move, which is why section 3.1 calls that a fit rather than a calibration.

Two further notes. `WINDOW_FACTOR = 1.5` at line 68 is the ARPACK endpoint window,
dimensionally unrelated to a convergence ratio; the coincidence that both read 1.5 must not be
mistaken for a derivation. And changing the mesh refinement factor invalidates both band
edges, which are tied to the ladder ratio.

### 4.2 Division of labour between pairing and physics

The pairing band `[2.5, 6.0]` is deliberately WIDER than the band P2 implies. P2 accepts
`p_k = log2(e_k/e_{k+1})` in `[1.7, 2.3]`, which is a contraction ratio in `[3.25, 4.92]`.
The wider pairing band exists so that pairing never pre-empts the physics criterion: a track
that pairs cleanly and then fails P2 is a **FAIL**, which is a statement about the physics,
and not a FAILED-TO-MEASURE, which is a statement about the instrument. Were the pairing band
as narrow as P2, P2 could never fire, and the gate would be unable to distinguish a wrong
rate from an untracked one.

## 5. Feasibility of the rule on its target case

A rule that cannot fire is not a rule. This section shows, before any run, that the rule has
room to operate on the case that motivated it: geometry A-3.5, contrast 2.5, three levels.
All figures come from records already on disk.

**Seed margin.** The worst per-root finest-level error is `4.73091e-03` at order 4, against
`SEED_TOL = 2e-2`, a margin of **4.23 times**. All four roots seed:
`e_{o,3} = 1.51045e-04, 3.45262e-04, 1.36925e-03, 4.73091e-03`.

**Window and ratio margins, per root.** R3 builds each window from that root's own
`e_{o,k+1}`, so the margins must be computed row-wise, not on the worst-error series.

| root | `e_1` | `e_2` | `e_3` | L3 seed margin | L1 window margin | `rho_1` | `rho_2` |
|---|---|---|---|---|---|---|---|
| 1 | 2.22906e-03 | 5.94175e-04 | 1.51045e-04 | 132.4 | 1.60 | 3.751 | 3.934 |
| 2 | 6.49604e-03 | 1.42437e-03 | 3.45262e-04 | 57.9 | 1.32 | 4.561 | 4.126 |
| 3 | 2.23535e-02 | 5.50412e-03 | 1.36925e-03 | 14.6 | 1.48 | 4.061 | 4.020 |
| 4 | 7.09799e-02 | 1.86827e-02 | 4.73091e-03 | 4.23 | 1.58 | 3.799 | 3.949 |

The binding window case is order 2: `6.0 * 1.42437e-03 = 8.546e-03` against an actual `e_1` of
`6.49604e-03`, a margin of **1.32 times**. Order 4, which carries the worst error, is the
loosest at 1.58. The window is never binding, but its tightest margin is 1.32, not 1.58.

Per-track contractions span `3.751` to `4.561` against `[2.5, 6.0]`, i.e. **1.50 times**
clearance at the lower edge and **1.32 at the upper**, the upper edge binding at order 2
between levels 1 and 2.

**Uniqueness.** At level 1 the nearest rival candidate is at least `8.515` times the paired
distance, and the nearest other root is at least `5.501` times away, so R3 returns exactly one
candidate and R1(b) is not contested.

**The point of the exercise.** The expected level-1 error, `7.09799e-02`, is 3.549 times the
frozen tolerance. That is precisely why no absolute rule can work here, and why this rule
applies no absolute test at level 1.

**Prediction.** The rule returns **PASS** on A-3.5 at contrast 2.5, derived from the composed
series (levels 1 from `pg_a35.json`, levels 2 and 3 from `pg_a35_l23.json`). A single
three-level run is required to confirm it; if the composed and single-run results disagree,
that is a finding about run composition and must be reported as one.

## 6. The missing clause, and one new token

D4 and D7 ask what happens when a reference mode cannot be found on a coarse rung. The frozen
gate had no answer and reported the coarse rung's distance as an ordinary failure. The
discriminator added here is principled: the physical spectrum is independent of the mesh, so a
mode seen at the finest level exists; failure to carry it onto a coarser rung is a resolution
phenomenon and can never be evidence of annihilation. Annihilation requires absence at the
finest level, and R2 governs that case with a control comparison.

New token: `COARSE_UNTRACKED = "UNTRACKED-AT-COARSE"` with exit code `4`, added to the module
constants and to the `EXIT` map, which currently holds `{PASS: 0, FAIL: 1,
FAILED-TO-MEASURE: 2, STOPPED: 3}`. The token enum is a fixed set of four constants; this
makes five. Its meaning: *a root seeded at the finest level could not be tracked onto a
coarser level; the rule declines to issue a verdict and explicitly does not report
annihilation.* It is distinct from STOPPED, which means annihilation is suspected, and from
FAILED-TO-MEASURE, which means the instrument was insufficient.

Consequence, stated here rather than discovered later: P1 requires `e_1`, `e_2` and `e_3` all
to be present, so an untracked coarse rung makes P1 unevaluable, and an unevaluable condition
is not a passed one.

`levels_incomplete`, `spectrum_short`, `attribution_conflict`, `contrast_beyond_validated` and
`assign_collision` are **reasons**, not tokens. Each is reported under FAILED-TO-MEASURE, so
the token set stays at five and the exit codes stay distinct.

**Precedence.** One run yields one token, and the order is fixed here because a reader uses it
to decide whether annihilation was reported:

`FAILED-TO-MEASURE` > `UNTRACKED-AT-COARSE` > `STOPPED` > `FAIL` > `PASS`.

Each inversion has a reason. Measurement failure outranks everything because no other token is
sound when the instrument is not. `UNTRACKED-AT-COARSE` outranks `STOPPED` because a
resolution failure anywhere means the run cannot certify that a missing mode was annihilated
rather than lost to the mesh. `STOPPED` outranks `FAIL` because a suspected annihilation is a
stronger claim than a wrong rate. `FAIL` outranks `PASS` trivially. Every per-root outcome is
written to the record, so a token that loses precedence is not lost.

## 7. What does not change

The rule changes which `e_{o,k}` are computed and what a missing one means. It changes no
threshold. Verbatim from the gate source:

| name | value | line | role |
|---|---|---|---|
| `LEVELS` | `(1, 2, 3)` | 62 | levels solved |
| `PAIR_TOL` | `2e-2` | 63 | pairing band; retained as `SEED_TOL` at level 3 only |
| `ORDER_LO` | `1.7` | 64 | P2 lower bound |
| `ORDER_HI` | `2.3` | 65 | P2 upper bound |
| `P3_MAX` | `5e-3` | 66 | computed; never consulted by `verdict()` |
| `ROUTE3_MIN` | `0.04` | 67 | minimum relative root gap |
| `WINDOW_FACTOR` | `1.5` | 68 | ARPACK window |
| `ARPACK_BUDGET_FACTOR` | `40` | 69 | ARPACK budget |

P1: all three `e_{o,k}` present and `e_{o,1} > e_{o,2} > e_{o,3}` strictly.
P2: both `p_k = log2(e_{o,k} / e_{o,k+1})` in `[1.7, 2.3]`.
P3: bound `5e-3`. It is computed and recorded but is **not** a verdict condition -- the source
computes `p3` and never reads it back -- so no PASS or FAIL in this document depends on it,
and section 8 cites it only as a diagnostic.
Route 3: `min_k |r_k - r_{k+1}| / r_{k+1} >= 0.04` over descending roots.

## 8. What this rule predicts for each existing geometry, stated in advance

Stating outcomes before the rule exists as code is the only defence against the rule being
tuned after the fact. Under the new rule:

**A (contrast 1.0) and A-1.5 (contrast 0.5) both remain PASS, unchanged.** Their worst
finest-level errors are `5.39284e-04` and `5.14478e-04`, at least 37 times inside the seed
tolerance, so every root seeds trivially and every measured contraction lies well inside
`[2.5, 6.0]`. If either verdict changes when the rule is implemented, that is a finding and
is reported, not suppressed.

**A-3.5 is expected to PASS.** The composed series satisfies P1 on all four orders, all eight
`p_k` lie in `[1.7, 2.3]` (1.9079, 1.9759 / 2.1896, 2.0446 / 2.0219, 2.0071 / 1.9255,
1.9815), the worst recorded P3 diagnostic is `4.73091e-03` at 0.95 of its bound (recorded, not gating
-- section 7), route 3 gives `0.182662`
against `0.04`, and there are four roots against a minimum of three.

**This is a conflict of interest and is declared here, in advance, in the document itself.**
The redesign was motivated by a failure at contrast 2.5, and the redesign predicts a pass at
contrast 2.5. Two defences are offered and neither is a reason to suppress the prediction.
First, P1, P2, P3 and route 3 are untouched by the redesign and are satisfied on measured
numbers, so the pass is not produced by the change. Second, the supplementary two-level
record already indicated that no mode was lost at contrast 2.5, so the redesign makes the
gate agree with evidence that predates it. A reader is entitled to treat the predicted pass
as contaminated by the redesign and to weight it accordingly; that is why it is written here
before the code exists.

## 9. What this rule does not test

A rule whose limits are stated in advance is auditable. These are its limits.

1. **Correctness of the frozen reference roots.** If an analytic root is wrong, and a computed
   mode happens to sit near the wrong value, the pairing succeeds cleanly. The rule tests
   agreement with the reference list, not the reference list.
2. **Losses at or above the finest solved level.** The rule seeds at level 3 and inherits every
   error level 3 already contains. A mode absent from level 3 is either annihilated or
   invisible to the solver, and R2 distinguishes those two only by the control comparison, not
   by any property of the missing mode itself.
3. **Simultaneous identity swaps.** If two tracks exchange candidates at the same level, both
   may remain inside their windows and their ratio bands. R3 is a local rule and has no
   global assignment.
4. **Completeness of the physical spectrum** beyond the `n` frozen roots. A computed mode with
   no reference root is not examined.
5. **The annihilation question itself.** The rule detects failure to track a mode that exists.
   It does not decide whether evaporation at high contrast is real, and it must not be cited
   as evidence either way.
6. **The usable contrast range.** `SEED_TOL` is validated at contrast 2.5 and below. Nothing
   here establishes that it holds at much higher contrast, and the honest statement is stronger
   than that: the contrast dependence of the finest-level error is *not* a power law on this
   data. For the order-3 mode, `e_3` runs `5.14478e-04 -> 5.39284e-04 -> 1.36925e-03` over
   contrasts 0.5, 1.0, 2.5, giving two-point exponents of **0.068** and then **1.017**. An
   exponent that moves by a factor of fifteen over a factor of five in contrast is not a rate,
   and no extrapolation from it is available.

7. **Absolute accuracy below the finest level.** The rule bounds `e_{o,L}` absolutely and every
   coarser error only relatively, so a level-1 error of up to `4^2 * SEED_TOL = 0.32` is
   admissible by construction; A-3.5's accepted `7.09799e-02` is exactly that effect. This is
   a consequence of seeding at the finest level rather than an oversight, but it means the
   rule certifies *correspondence*, not *accuracy*: a geometric chain of wrong states that
   satisfies every relative test is not excluded by anything here. The one criterion that
   would bound absolute accuracy, `P3_MAX = 5e-3`, is computed and never consulted. Closing
   that is a change to P3 and is not claimed.

The only defensible claim is therefore narrow: the rule operates on geometry A-3.5 at contrast
2.5 with a 4.23 times seed margin, and its upper limit in contrast is unknown.

## 10. Adversarial review, and what it changed

Section 1 said this document was not in force. It was therefore reviewed before freezing rather
than after. An independent reviewer, given this document and its own reading of the gate source
and nothing else, produced fourteen findings. Six were accepted as corrections to the rule, one
was accepted as a correction to a number, three were accepted as editorial repairs, one was
rejected as mechanically wrong but substantively right, one was rejected outright, and three
attacks were reported as not landing. The rule was amended in place; this document is not
append-only and the amendment is disclosed here rather than hidden by re-issuing it.

| # | finding | severity | disposition |
|---|---|---|---|
| 1 | R3 had no exclusivity: two tracks could claim one candidate and PASS | BLOCKER | **accepted** -- exclusivity at every level, `assign_collision` |
| 2 | no absolute accuracy floor below `L`; a geometric chain of wrong states passes | BLOCKER | **partly accepted** -- disclosed as section 9.7; the proposed cap **refused** |
| 3 | R2 convicts annihilation on a candidate set never shown complete | MAJOR | **accepted** -- `spectrum_short` precondition |
| 4 | R2 reports attribution failure as annihilation | MAJOR | **accepted** -- `attribution_conflict` |
| 5 | D7 relocated to the finest level, where section 9.6 concedes no rate is known | MAJOR | **accepted** -- STOPPED licensed only at `c <= 2.5` |
| 6 | R5 would report a never-solved level as a tracking failure | MAJOR | **accepted** -- `levels_incomplete` |
| 7 | token precedence undefined when roots fail differently | MAJOR | **accepted** -- total order added to section 6 |
| 8 | the `6.0 = 4 * 1.5` derivation reuses an unrelated constant; band is calibrated | MAJOR | **accepted** -- section 4.1 rewritten as a disclosed calibration |
| 9 | "1.52 times margin to each edge" is false | MINOR | **accepted** -- true margins are 1.50 and 1.32 |
| 10 | section 5's window margin may mix two roots' series | MINOR | **mechanism rejected, substance accepted** -- margins are now per root, and the minimum is 1.32, not 1.58 |
| 11 | `e = 0` unspecified: exact seed collapses its own window; `rho` divides by zero | MAJOR | **accepted** -- `E_FLOOR`, `rho = +inf`, P2 unevaluable |
| 12 | R4's upper edge is dead code; empty candidate sets ill-defined | MINOR | **accepted** -- stated in R4; empty set is FAILED-TO-MEASURE |
| 13 | P3 presented as a criterion and as inert in the same section | MINOR | **accepted** -- section 7 now says it gates nothing |
| 14 | exit code 4 collides; `SEED_TOL` smuggled | NONE | **confirmed** -- code 4 is free, `PAIR_TOL` is quoted verbatim |

### 10.1 The refusal, and why

Finding 2 proposed an absolute cap, `CAP_1 = 4e-2`, on the level-1 error, made part of the
verdict. It is refused because it would fail the case this rule exists to serve: A-3.5's level-1
error is `7.09799e-02`, so `CAP_1 = 4e-2` turns the predicted PASS into a FAIL. A cap set above
`7.098e-2` would be set from the failing datum -- the exact manoeuvre section 3.1 rejects in the
`tol_1` proposal. There is no value of `CAP_1` that both passes A-3.5 and is independent of it.
What is accepted is the *disclosure*: section 9.7 now states plainly that the rule certifies
correspondence rather than accuracy, that an absolute error of up to `0.32` at level 1 is
admissible by construction, and that the criterion which would bound it, `P3_MAX`, gates
nothing. A rule that documents its blind spot is auditable; one that hides it behind a fitted
cap is not.

### 10.2 Finding 10, stated precisely

The reviewer suspected that section 5's window margin paired the level-2 error of one root with
the level-1 error of another. It did not: `1.86827e-02` and `7.09799e-02` are both order 4. But
the reviewer was right that a single-row margin cannot represent a per-root rule, and computing
all four rows exposed a worse error than the one alleged. The binding window case is order 2 at
1.32, not order 4 at 1.58, and the per-track ratio spread is `3.751` to `4.561`, not the `3.93`
to `4.13` that section 4.1 had quoted from levels 2 and 3 only. Both figures are corrected above.

### 10.3 What the review did not change

Section 8's predicted PASS at contrast 2.5 was written before the review and survives it
unchanged. Every accepted amendment makes the rule **stricter**, with one neutral exception
(`E_FLOOR`, which can only widen a window). The prediction was not adjusted to accommodate the
amendments, and no amendment was softened to protect the prediction. None of the new
preconditions binds on A-3.5: all four roots seed, so R2's conditions are never reached; the
minimum cross-root separation is `5.501` times the paired distance, so no `assign_collision`;
`E_FLOOR` is nine orders below the smallest error; and the composed series supplies all three
levels, so `levels_incomplete` cannot fire.

What the review did establish is that the rule as first written could have returned PASS on a
run where two roots were served by one computed mode, and on a run where every level was wrong
in a self-consistent geometric progression. Both are now either blocked or disclosed. That is
the value of reviewing a pre-registration before it freezes, and it is why the review happened
in this order.

**Revision record.** Revision 2. Revision 1 was sections 1 to 9 as first drafted; revision 2 amends
R2, R3, R4, R5 and section 6 for findings 1, 3, 4, 5, 6, 7, 11 and 12, and sections 4.1, 5, 7,
8 and 9 for findings 8, 9, 10, 13 and 2. The document is still not in force; freezing remains a
separate act.

## 11. Attacks constructed and not executed

An independent review is not an adversarial test of a gate. This section records attacks built by
reading this rule and the frozen gate's source. **None of them was executed.** No code was run,
no record was modified, and no number below is a measurement. A constructed attack is therefore
not a demonstrated vulnerability: it is a claim that a specified report would be wrong, with the
mechanism stated so that a later run can confirm it or drop it. AT-1 to AT-4 are the four themes
the dispatch named, in the order it named them; the dispatch gave themes rather than enumerated
constructions, so the input and the wording of each row are mine. AT-5 is drawn from this
document's own sections 2 and 6, and AT-6 is mine.

### 11.1 Coverage of the five attacks the dispatch named

This subsection exists so that a reader can check, for each of the five attacks the dispatch
named, that it was answered here and by what.

| dispatched attack | status | where answered |
|---|---|---|
| (1) mode identity by column ordering when two modes are near-degenerate | OPENED (new row) | AT-1 below; the mechanism is stated there in full, and its ledger consequence is section 0 against claim C21 |
| (2) decorrelation of the pairing assignment when the mode set is re-sorted by a different key | OPENED (new row) | AT-2 below |
| (3) a gate applied to a level where the deflation subspace itself changed | OPENED (new row) | AT-3 below |
| (4) a pass achieved by comparing a run against itself | CLOSED (pre-existing) | section 10, finding 11: `E_FLOOR` and `rho = +inf` already make the exact degenerate form FAILED-TO-MEASURE, without anything in this section. Only the perturbed form -- a self-generated ladder carrying a small non-zero perturbation -- survives, as AT-4 below |
| (5) annihilation misreport via the STOPPED/UNTRACKED-AT-COARSE precedence (the `c <= 2.5` STOPPED licence) | NOT DISTINGUISHABLE | section 10, findings 4 and 5 close the attribution-misreport case and withdraw the licence for `c > 2.5`, but nothing in the rule separates a genuinely lost mode from a discretisation artefact at `c <= 2.5`; the part that is still open is recorded as AT-7 below |

| id | attack | constructed input | what the gate reports | why that report is wrong | minimum revision that closes it | closed today? |
|---|---|---|---|---|---|---|
| AT-1 | mode identity by column ordering when two modes are near-degenerate | two reference roots about 4.2% apart (above route 3's `0.04`) with their two computed candidates exchanged, by the same amount, at every level -- for instance a dielectric step moved so the two modes cross between two of the levels | PASS: every track stays inside `SEED_TOL` at level 3, both contractions stay inside `[2.5, 6.0]`, and route 3 is read off the reference list at 0.042 | the rule tests that a beta lies near a root and never that the mode is the same mode. A swap that is self-consistent across levels leaves every distance and every ratio inside band, so cross-level identity is assumed by the assignment rather than measured. The ledger's claim C21 is the row that says this needs an overlap test, and the invariant layer that might have caught a swap has no measured result at all (inventory row B01, E5, not citable) | one eigenvector overlap per tracked pair, `abs(v_k . v_k+1)` with a stated bar, recorded per track per level and required before a track may continue | no -- section 9.7 discloses the family of geometric chains; no term of the rule detects one |
| AT-2 | decorrelation of the pairing assignment when the mode set is re-sorted by a different key | one physical case run twice, candidates sorted by `abs(beta)` and then by `Re(beta)` (or ascending against descending), with the `k_candidates = 16` cut falling between two different betas in the two runs | not one wrong report but a report that changes between runs: PASS, or FAILED-TO-MEASURE from `ambiguous` or `assign_collision`, or UNTRACKED-AT-COARSE, depending on which side of the cut a surviving mode lands | the physics is identical and the verdict is not. The sort key appears nowhere in the rule, so two records cannot be compared without it, and the collision and ambiguity tokens are defined on an assignment that the cut can move. A verdict a re-sort can flip is not a measurement | pin one canonical sort key in the rule and in the record, and state the `k_candidates` window as a pre-registered quantity rather than as an implementation default | no -- section 1 fixes `k_candidates = 16` and says nothing about ordering |
| AT-3 | a gate applied to a level where the deflation subspace itself changed | three levels of which the coarsest deflates a spurious pair of the recorded kind (`t4_amp_ratio.md` section 15.8: five shifts returned a bogus pair at residual `9.89e-01`), while levels 2-3 deflate nothing spurious | PASS whenever a track exists: nothing in R1-R6 reads the deflated set, and `spectrum_short` counts only the level-3 real betas against the number of roots | the three levels are then not three discretisations of one operator, and the contraction band measures the difference between two operator splittings as if it were a refinement rate. The rule names the shift and the budget and never the set the shift deflates | record the deflated eigenvalue set per level in the artefact, and refuse a track whose level-`L` candidate lies inside a coarser level's deflated set, with its own token | no |
| AT-4 | a pass achieved by comparing a run against itself | a reference ladder produced by the solver under test -- the converged `ny = 64` betas used as the level-3 reference, and the same procedure at 32 and 16 | the exact version is FAILED-TO-MEASURE, because `e = 0` collapses the window onto `E_FLOOR` and `rho = +inf` sits outside the band: finding 11 catches it, not the design. Add a small geometric perturbation to each level's reference and the same run reports PASS | the record then measures self-consistency, and a clean PASS is evidence about the code rather than about the physics. R1 tests the distance to the reference and cannot see where the reference came from; section 9.1 says this in words and nothing enforces it | a provenance field on the reference ladder -- generator, source rows, hash -- in the schema, plus a rule that the ladder may not be produced by the solver being graded | no -- disclosed in section 9.1, not implemented |
| AT-5 | annihilation misreported through the STOPPED and UNTRACKED-AT-COARSE precedence | a genuine loss of a mode at contrast `<= 2.5`, and separately a coarse-rung solver failure that loses the mode at level 1 only | STOPPED (exit 3, "annihilation suspected") for the first, UNTRACKED-AT-COARSE (exit 4) for the second | both tokens assert a cause the rule cannot establish. The frozen gate's STOPPED at contrast 2.5 was itself a discretisation artefact with no physical event (section 2), and this rule changes the vocabulary and adds preconditions without adding a discriminator between a lost mode and a lost track. Sections 9.2 and 9.5 concede exactly that | solver-side evidence before either token may be emitted -- an inertia computation per rung, or the residual and overlap of the vanishing branch -- otherwise FAILED-TO-MEASURE | no -- partial mitigation only, from `contrast_beyond_validated` (finding 5) and `spectrum_short` (finding 3) |
| AT-6 | one root's instrument failure masks another root's physics failure, through the total order in section 6 | a four-root record at contrast 2.5 in which root 3 truly vanishes while roots 2 and 3 are degenerate enough to raise `attribution_conflict` or `assign_collision` | FAILED-TO-MEASURE (exit 2). The order FAILED-TO-MEASURE, then UNTRACKED-AT-COARSE, then STOPPED, then FAIL, then PASS is a join over roots, so the least informative outcome wins the record | the record contains a physical event and reports an instrument problem, and the token carries no trace of the root that vanished; a reader downstream sees "could not measure" about a run that measured something. The order is defended as conservative and is conservative in the wrong direction here, protecting the instrument's reputation at the cost of the finding | emit per-root verdicts as a vector and keep the joined token for compatibility, and require the unpaired-root list in the artefact under every token rather than only under STOPPED | no -- section 6 defines the order and does not say the per-root detail survives it |
| AT-7 | a genuine solver-side loss of a mode at contrast `<= 2.5`, correctly attributed and with a complete spectrum | a root whose computed branch the solver annihilates at contrast 2.5, with the pairing clean (one candidate, uniquely paired, so `attribution_conflict` is not raised), all three levels present and `spectrum_short` not raised -- a real loss that the record can attribute correctly | PASS or FAIL on the surviving roots, with no token recording that a mode was lost | the rule can only report a vanishing mode through STOPPED, and AT-5 shows that token has no discriminator. Once the loss is attributed correctly and the spectrum is complete, `contrast_beyond_validated` and `spectrum_short` are both silent, so a cleanly measured loss of a real mode produces no report at all: the record reads as a complete measurement of a spectrum that is missing a mode | the same solver-side evidence AT-5 asks for -- per-rung inertia, or the residual and overlap of the vanishing branch -- promoted from a precondition of STOPPED to a required per-root artefact field, so that a lost mode is reported with no cause claim attached | no |

**What I would change first.** One revision closes most of this surface, and it is not a change to
the rule's arithmetic: extend the record, not the tolerance. Two additions -- a per-track
cross-level eigenvector overlap with a stated bar, and the deflated eigenvalue set per level --
make AT-1, AT-3 and AT-5's missing discriminator decidable, and they cost two columns and one
array per level. Neither touches `SEED_TOL`, the contraction band, P1, P2, P3 or route 3, so
section 8's prediction is unaffected and the revision cannot be accused of being tuned to protect
it. AT-2 and AT-6 are cheaper still: a canonical sort key written into the rule, and a per-root
verdict vector written into the artefact, are text and format changes with no numerical content.
AT-4 cannot be closed inside the gate at all, because it is a statement about where the reference
came from, and it belongs in the schema that registers the run.

**The vacuous-pass direction, stated separately.** AT-1, AT-2 and AT-4 can produce PASS. AT-3
produces PASS unless the deflated set is recorded. AT-5 and AT-6 do not produce PASS: they convert
a report into a different report, and AT-6 removes the record's ability to say that a mode was
lost, which is the one outcome this rule exists to preserve. The asymmetry is worth stating
because the attacks that produce PASS are the ones that will be cited: a FAIL invites a rerun, a
FAILED-TO-MEASURE invites a repair, and a PASS is quoted. Of the six, AT-4 is the one I would
expect to bite in normal use rather than in principle, because nothing in the workflow forecloses
building the reference ladder from a converged run's own output -- which is what inventory rows
A17 and A18 record the corpus already doing on another geometry -- and because section 8 here
predicts a PASS at the contrast that motivated the redesign, so the first clean PASS arrives at
the configuration where a vacuous pass is hardest to see.
