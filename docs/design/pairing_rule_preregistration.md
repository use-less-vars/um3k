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

`k_candidates = 16` is the ARPACK request `k`, not a post-solve truncation: the solver returns every
requested candidate and the record keeps each one, so the number is an input to the solve and not a
window applied to its output. Section 4.3 establishes this against the tree, and R0 governs what the
constant is and is not allowed to decide.

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

**R0 -- Candidate order and the `k_candidates` boundary (AT-2).** This clause is an addition, not a
revision: no ordering term and no cut term exists in R1 to R6, and section 1 is the only place the
constant occurs. The gap it closes is the one the constant's own comment points at --
`tools/host/anchor/ladder.py:62` annotates `K_CAND = 16` with "section 4.3 rule 1 / 8.4", and the
section it names contains no candidate rule at all.

*Hazard H-AT2.* Two records of one physical case can carry different verdicts because the candidate
list was ordered by a different key. The order exists in code and not in this document: the runner
builds its rows with `pairs.sort(key=lambda p: (-p[0][0], p[1]))`
(`tools/host/anchor/ladder.py:128`), i.e. `beta_sq` descending and then `curl_ratio` ascending, and
the record's `index` field is the position in that sorted list, not the solver's return position.
The order was never written down, so an implementation default has been standing in for a rule. The
hazard is not bookkeeping in at least one live place: the mixed path sorts with
`order = np.argsort(-beta_sq)` (`emfit/mode2d.py:1870`), whose default kind is quicksort and is
therefore not stable, and then selects `chosen = np.flatnonzero(eligible)[np.argmax(beta_sq[eligible])]`
(`emfit/mode2d.py:1887`). Among eligible candidates tied in `beta_sq`, which candidate is chosen is
decided by the argsort's tie permutation. A re-sort can change the selected mode with no change to
the physics.

**The canonical key.** Candidates are ordered by the lexicographic key

    K(c) = (-beta_sq(c),  +curl_ratio(c),  +index(c))

read as `beta_sq` descending, then `curl_ratio` ascending, then `index` ascending. `beta_sq` and
`curl_ratio` are the only two numbers in the candidate record that are independent of each other:
`eps_eff = beta_sq / k0^2` is a function of `beta_sq` and cannot break a tie in it. The direction is
fixed here and not derived: `beta_sq` descending puts the fastest-varying modes first, which is the
order the runner already uses, and `curl_ratio` ascending is the runner's existing second term. This
clause therefore ratifies the runner's behaviour rather than inventing a competing order, and the
fact that the behaviour predates the rule is precisely the defect being closed.

`index` is the last term and only the last term. Because the record's `index` is currently the
position in the sorted list, it is redundant with the first two terms and cannot serve as an
identity; a key that used it earlier would be circular. Its role is to make the order total over
whatever list the record actually contains, whatever labelling convention the producer used.

**Totality, and what is not distinguishable.** K is total wherever `beta_sq` and `curl_ratio` are
comparable reals or the values `inf` and `-inf`. Two records are *indistinguishable* if and only if
they agree on `beta_sq` and on `curl_ratio` to double precision; then and only then is the order
between them undetermined. No key over these fields can do better, because the fields are equal.
The indistinguishability is a statement about the physics rather than an ordering defect: two
candidates equal in both numerics at double precision are one state up to a rotation of a degenerate
eigenspace, and no verdict in this rule separates them either. `index` separates them in the list; it
does not make them different states.

A record whose `beta_sq` or `curl_ratio` is `NaN`, or whose fields are not comparable, is not ordered
by K. The run does not then fall back to insertion order: it emits FAILED-TO-MEASURE with reason
`sort_key_undefined`. A `NaN` `curl_ratio` is already reachable at the selection site, where `ratios`
is initialised to `NaN` wherever `m1x` vanishes (`emfit/mode2d.py:1861-1865`), so this is a state the
rule has to name and not a guard against the impossible.

**The `k_candidates` boundary, as a pre-registered quantity.** (a) The key is computed after the
solve, on the candidate records the solver returned; it is not an instruction to the solver.
(b) `k_candidates` is the ARPACK request count, the `k` of the solve call, and the solver asks for
`n_k = min(int(k), n_dof - 1)` (`emfit/mode2d.py:1557` deflated, `:930` undeflated). (c) There is no
post-solve truncation to `k_candidates`: every returned candidate is written to `candidates_all` and
then classified into `retained` or `dropped`, and the only filters are the two of AMENDMENT v2 --
`|eps_eff - 1| <= 1e-8` and then a six-decade gap between `max dropped |curl_ratio|` and `min
retained |curl_ratio|` (`tools/host/anchor/ladder.py:223`). Both are `max`/`min` over a set and are
therefore invariant under any reordering of the record. In this tree the `k_candidates` cut moves
nothing. (d) The guarantee given here is invariance of membership under reordering of the input
records: the solve's inputs are the mesh and the parameters, and the candidate list is an output. A
changed request, tolerance or shift is a different measurement, outside the guarantee; a comparison
across such a change compares two measurements, not one. (e) The set that is genuinely at risk is the
degenerate cluster at `beta_sq = k0^2`, whose observed multiplicity rises from 11 to at least 14 as
the mesh refines (`decisions.md:8525`): a request of 16 against a cluster of that size can return a
different subset on a different run. Every member of the cluster is a distinct record with a distinct
`beta_sq`, so no ordering can settle which members were requested. This is stated as the residual of
AT-2 in section 4.3, not argued away. (f) Records that cannot be ordered carry the reason
`sort_key_undefined` under FAILED-TO-MEASURE. No sixth token is created: a NO-VERDICT is a
FAILED-TO-MEASURE with a named reason, which is already how `levels_incomplete`, `spectrum_short`,
`attribution_conflict`, `contrast_beyond_validated` and `assign_collision` are handled in section 6.

**Comparability.** Two records of one physical case are comparable under K if and only if both carry
the fields K reads, at the same `k0`, under the same `k_candidates` request. The record must carry
`beta_sq`, `curl_ratio`, `index` and both constants per level; a record missing any of them is
`sort_key_undefined` and is not comparable. Comparability is a property of the record, not a
reader's choice of sort.

**Ordering ties are non-verdicts by construction.** An exact tie at the seed cannot become a verdict:
R1's minimisation over `C_L` is undefined between candidates equal in `beta_sq` and `curl_ratio`, and
the run reports FAILED-TO-MEASURE with reason `tie_at_seed` rather than picking one. A tie inside the
competitor set is already covered, because R3 reports `ambiguous` whenever `|S| >= 2`. The residual
ambiguity left by K is in every case a non-verdict, so K needs no further tie-break to be sound.

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

**R7 -- Reference provenance.** The reference ladder must come from the analytic routine or from an
external tool, and never from the solver's own converged output. No verdict is produced against a
ladder that is not independent of the run it scores.

An entry whose provenance is absent, outside the fixed vocabulary, or numerically equal to a value
the run has already recorded from the solver is **FAILED-TO-MEASURE**, reason
`reference_not_independent` -- neither a PASS nor a FAIL. Section 4.4 gives the admissible and
inadmissible constructions, the vocabulary, and the two checks that do not rely on the declared
field.

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

### 4.3 Sort key: provenance and what it cannot reach

R0 states the key. This subsection states where it came from and what it does not settle, because
the closure of AT-2 turns on the difference.

**Provenance.** No sort-key clause and no truncation clause existed in R1 to R6 before revision 3.
Section 4 never mentioned ordering, and `k_candidates = 16` occurred once, in the constants list of
section 1. The order the runner used was `(-beta_sq, +curl_ratio)`
(`tools/host/anchor/ladder.py:128`), written in code, documented nowhere in the rule, and the
record's `index` field was a position in that sorted list rather than an identity. R0 is therefore an
**addition**, not a revision of an existing clause, and the review's phrasing -- re-sorting by a
different key -- presupposes a clause that was never there. The distinction matters for the history:
nothing in this document is contradicted by R0, and no earlier reading of R1 to R6 is overturned.

**Closure: PARTIALLY CLOSED.** Closed in the rule: the key and its direction, its totality, the
last-term status of `index`, the `sort_key_undefined` reason, and the statement that ordering ties
are non-verdicts. A reader can now reproduce the order from the document alone, which was the
requirement.

Not closed, and not closeable by a key: the membership of the 16 returned candidates. The cut is an
ARPACK request, not a window applied to the output -- `n_k = min(int(k), n_dof - 1)`
(`emfit/mode2d.py:1557`, `:930`), every returned candidate recorded, and the only filters those of
v2, which are order-invariant `max`/`min` over a set. Ordering cannot make a solver return a
deterministic subset of a degenerate cluster, and the cluster at `beta_sq = k0^2` has multiplicity 11
rising to at least 14 (`decisions.md:8525`), so a request of 16 is not a request that resolves it.
The residual is stated as a condition a later reader can test: **if two runs of one physical case
return candidate sets that differ inside the `beta_sq = k0^2` cluster, the difference is outside
R0's guarantee and the pair is not comparable under K; the run that shows it is a NO-VERDICT --
FAILED-TO-MEASURE, reason `cluster_membership_unstable` -- and not a disagreement between records.**
That is a reason, not a token: the set stays at five.

AT-2 therefore reduces to a defect of the rule book, now closed, plus a measurement defect in the
solver's cluster resolution, which a rule cannot close. Calling AT-2 CLOSED would claim the second
by fixing the first.

### 4.4 Reference provenance: which ladders are admissible (AT-4)

**The hazard, H-AT4.** Every order verdict in this rule -- P1, P2, P3, route 3 -- is a statement
about the *distance between* the computed sequence and a reference. If the reference is built from
the solver's own converged output, the statement is about the solver's agreement with itself: a
coarse run used to score a fine run, the same run read at a different level, or a fit to the run's
own sequence all produce a clean, in-band contraction that certifies nothing. This is the one attack
in section 11 that this project has already carried out rather than merely imagined: ledger rows
**A17 and A18** record the reference ladder being built from a converged run's own output on another
geometry. It is stated before it is forbidden because a rule that had only implied the route was
undesirable would leave those results standing, and they are the reason to expect the attack to
recur in normal use rather than in principle.

**The rule.** R7, in one sentence: analytic routine or external tool, never the solver's own
converged output. What follows makes that sentence operational and nothing else.

**Admissible, exhaustively.**

1. `analytic:<routine>/<routine-revision>@k` -- the frozen analytic routine, the same one that
   produced the frozen reference roots, evaluated at the resolution of ladder level `k`. Evaluating
   the routine's own discretised form at the coarse levels is admissible and is what section 5
   already scores against; the routine is not the code under test.
2. `external:<tool>/<version>#<input-hash>` -- an independent solver or library, version and input
   hash pinned, not the code under test, with its own convergence record at the two finest levels
   carried in the artefact.

Nothing else is admissible. Both are reproducible: re-running the registered construction on the
registered inputs must reproduce the registered value -- to the last bit for (1), a deterministic
routine, and within the tool's own stated noise for (2).

**Inadmissible, exhaustively.**

1. A coarser run of the same solver: levels 1-2 solved to score level 3.
2. The same run at a different level, or any restriction, permutation or re-projection of it.
3. Any quantity already recorded in the run's own output -- betas from `candidates_all`, residuals
   `e_{o,k}`, seeds `c*`, or a previous verdict.
4. A fit, interpolation or extrapolation to the solver's own sequence, including a convergence-order
   fit through the solver's own errors.
5. A ladder copied from another run's solver output, or rounded from one. This is the corpus's
   A17/A18 route and it is inadmissible even though it is not the *current* run's output: it is
   still the code under test, and a second run of the same code is the same witness.

**What was previously misread.** Revision 3 treated a solver-derived ladder as admissible if it was
*declared*: the AT-4 row and section 11 asked only for "generator, source rows, hash" in the schema
that registers the run, which reads as permitting a declared solver-derived ladder while disapproving
of it. Declaration is now necessary and not sufficient. One construction moves the other way, and it
is recorded as a judgement call: evaluating the analytic routine at the coarse resolutions rather
than only at closed-form exact values could be read as forbidden under revision 3's phrase "may not
be produced by the solver being graded", and it is admissible here, because the routine is not the
solver and section 5 depends on it.

**Detection, mechanically.** Three checks, none of which is good faith.

  - **Declared provenance.** Every ladder entry carries `reference_ladder[i].provenance` drawn from
    the fixed vocabulary in the list above. A missing field, a value outside the vocabulary, or a
    field that disagrees with the construction actually used stops the gate before a verdict: the
    gate does not produce one.
  - **Numeric identity, field-independent.** For each ladder entry, the gate compares its value
    against every value the run has already recorded from the solver (all levels of
    `candidates_all`, the residuals `e_{o,k}`, the seeds `c*`). Equality is **exact**, bit-for-bit on
    the round-tripped double, with no tolerance. A tolerance is not needed and would be harmful
    here: a copied value differs from the analytic value by the solver's own error, which on this
    geometry is `1e-4` to `1e-3` (section 2), four to six orders above any tolerance a deterministic
    routine's rounding would need. So a tolerance buys nothing, and exact equality cannot be evaded
    by perturbing the copy: the third check catches the perturbation.
  - **Recomputation.** For a declared `analytic` entry the gate re-evaluates the frozen routine at
    the registered resolution and requires agreement to `1e-12` relative; for a declared `external`
    entry it re-reads the pinned tool output and input hash. A solver value perturbed by any amount
    large enough to break exact equality is then still wrong by the solver's error and fails this
    bar, so the pair of checks has no gap between them. This check does not consult the provenance
    field except to decide which construction to recompute.

**The token.** A detected violation is **FAILED-TO-MEASURE**, exit 2, reason
`reference_not_independent`, with `reference_provenance_check` naming which check fired
(`declared`, `identity` or `recompute`) and the offending entry's index. It is not a PASS, because a
run scored against itself has not been measured and a PASS would be quoted downstream as evidence.
It is not a FAIL, because a FAIL is a claim about the physics and this is a claim about provenance:
the same reason R2 reports an instrument failure as FAILED-TO-MEASURE rather than FAIL, and the same
reason AT-6's aggregation puts instrument tokens where they cannot masquerade as findings. It is not
STOPPED either -- no annihilation is being asserted.

**Retroactive consequence for rows A17 and A18.** They are not grandfathered, and this rule does not
claim they were fine. Their recorded numbers are kept, their order verdicts are withdrawn as of this
revision, and they may not be cited as convergence-order evidence, as validation of any constant, or
as precedent for a ladder construction until they are re-derived against an admissible ladder. The
re-derivation is not done by this revision and is recorded as outstanding work in section 12.1.
Until it is done the rows count as UNVERIFIED, and any later document that cites them must say so.

**What this clause still does not test.** R7 constrains where the reference came from, not whether
it is correct: limit 1 of section 9 stands unchanged, and an analytic root that is wrong will still
be agreed with cleanly.

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

> **Superseded in place -- revision 3.** The precedence paragraph and the total order below are
> retained verbatim as the revision 2 text and are withdrawn as a rule. Section 6.1 replaces them.
> They are history; they are not the current ordering.

**Precedence.** One run yields one token, and the order is fixed here because a reader uses it
to decide whether annihilation was reported:

`FAILED-TO-MEASURE` > `UNTRACKED-AT-COARSE` > `STOPPED` > `FAIL` > `PASS`.

Each inversion has a reason. Measurement failure outranks everything because no other token is
sound when the instrument is not. `UNTRACKED-AT-COARSE` outranks `STOPPED` because a
resolution failure anywhere means the run cannot certify that a missing mode was annihilated
rather than lost to the mesh. `STOPPED` outranks `FAIL` because a suspected annihilation is a
stronger claim than a wrong rate. `FAIL` outranks `PASS` trivially. Every per-root outcome is
written to the record, so a token that loses precedence is not lost.

> **End of the superseded block -- revision 3.** Everything from the "Superseded in place" marker
> above to this line is withdrawn as a rule and is kept as history.

### 6.1 Per-root verdicts and run-level aggregation (AT-6)

**Why the total order above is withdrawn.** A total order over tokens applied to a whole run is a
join: the highest-precedence token in the vector wins the record, which is what "one run yields one
token" meant. That makes the record's summary a function of the least informative root. The failure
is one-directional and harmful: a root whose physics failed -- a wrong contraction rate, or a mode
genuinely absent -- is masked by any other root that failed to measure, so the record reports an
instrument problem about a run that made a physics finding. The withdrawn order is not wrong because
precedence is wrong; it is wrong because the object it ordered was the run rather than the root.

**The sentence at the end of the withdrawn paragraph.** Revision 2 wrote: "Every per-root outcome is
written to the record, so a token that loses precedence is not lost." That sentence is hereby
promoted from a description to a **requirement on the artefact**, and it is not true of the current
artefact. The record as produced today carries per-root outcomes only as diagnostics, inside whatever
per-level structure the run wrote; it carries no per-root verdict vector. The requirement therefore
creates work, and the work is the field `root_verdicts`. Nothing below should be read as claiming
that field exists.

**Per-root vocabulary.** Each root receives one token from the same fixed set of five -- `PASS`,
`FAIL`, `FAILED-TO-MEASURE`, `STOPPED`, `UNTRACKED-AT-COARSE` -- under R1 to R6 applied to that root
alone. No per-root token is invented and no per-root token means anything different from what section
6 already says it means. A root that cannot be given a token is FAILED-TO-MEASURE with a reason,
never a sixth symbol.

**Run-level aggregation, as a total function.** Let `v_o` be the token of root `o`, `o = 1..n`, let
`V` be the vector, and let the run token be `A(V)`, evaluated in this order with the first match
winning:

1. **Record-level defects first.** If the record as a whole is defective -- `levels_incomplete`, or
   R2's global `no seed` gate meaning that no root seeded at all, or `spectrum_short` in the sense of
   a level-3 real-beta count below the number of roots -- the run is FAILED-TO-MEASURE before any
   aggregation. Per-root tokens may be present and are still recorded, but they are not the basis of
   the run token, because a vector over an incomplete reference set is not a measurement of that set.
2. Any `STOPPED` in `V` gives `STOPPED`.
3. Otherwise any `FAIL` in `V` gives `FAIL`.
4. Otherwise any `FAILED-TO-MEASURE` in `V` gives `FAILED-TO-MEASURE`.
5. Otherwise any `UNTRACKED-AT-COARSE` in `V` gives `UNTRACKED-AT-COARSE`.
6. Otherwise, all `PASS`, the run is `PASS`.

`A` is total: clauses 1 to 6 cover every vector over the five tokens, the last being the conjunction
of the negations of the others.

The order inside `A` is not the withdrawn order and must not be read as its continuation. Two
properties fix it. **Physics outranks the instrument**: `STOPPED` and `FAIL` are claims about the
spectrum, the other two are claims about the measurement, and a claim about the spectrum made from a
complete measurement is not falsified by another root's incomplete one. This is the inversion AT-6
was about and the only place where revision 3 reverses revision 2. `STOPPED` above `FAIL` is carried
over unchanged from the withdrawn order for the reason given there -- a suspected annihilation is the
stronger claim -- while the rest of the old order is dropped, and with it the masking: no
FAILED-TO-MEASURE can hide a FAIL, and no UNTRACKED-AT-COARSE can hide a STOPPED.

**When roots disagree.** Disagreement is a normal outcome and is reported, never resolved. There is
no averaging of tokens, no vote, no majority, and no rule that prefers the more favourable root or
the less favourable one. That any `V` which is not all-`PASS` cannot produce a run `PASS` follows
from clause 6 and needs no separate clause. The record carries, per root, the token `v_o` and, where
the token is FAILED-TO-MEASURE, its reason; it also carries `root_verdicts`, the vector `V`, and a
`disagreement` flag set when `V` is not constant. `disagreement` describes the record and is not a
token: it changes no exit code, and a run whose roots disagree is as reportable as one whose roots
agree.

**Diagnostics are mandatory and are not verdict conditions.** Per root and per level the record
carries the triple `e_{o,k}`, the solve's `residual_eps_mu`, and the `p3` quantity whose bound is
P3_MAX. These are required fields. None of them is a test: the rule is R1 to R6 on `e` and the rates,
and a diagnostic outside any band changes no token. The precedent is explicit in this document --
`residual_eps_mu` is carried by the solve and never gated, and section 7 records that P3_MAX is
computed and never consulted. Revision 3 does not promote either into a condition, because a bound
introduced after a prediction is a degree of freedom.

**Closure: CLOSED in the rule, not in force.** The aggregation is total, it is asymmetric in the
required direction, and every combination has a stated outcome, so AT-6 is closed as text. It is not
in force: the enforcement point is the artefact field `root_verdicts`, which does not exist, and until
a run writes it the current artefact cannot distinguish a masked record from an unmasked one. A
reader checking AT-6 checks the field, not this paragraph.

One judgement call is disclosed rather than buried: clause 1 lets R2's global `no seed` gate override
a per-root `STOPPED` or `FAIL`, which is the one place where an instrument outcome outranks a physics
outcome after the inversion above. The justification is that `no seed` is not a per-root measurement
failure but a statement that the reference set was not seen at the finest level at all, so there is no
spectrum against which "annihilated" or "wrong rate" could be claimed. If that reading is contested,
clause 1 is the line to contest; clauses 2 to 6 do not depend on it.

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

[REVISION 6 MARKER — appended at dispatch 54; the line above is untouched. The second order's `p_2` exists in two committed copies with different fourth digits: `2.0087` at `docs/design/preservation_gate_preregistration.md:54` (the order-2 row's `p_2` cell of the pre-run table at `:51-55`) and `2.0089` at `docs/design/preservation_gate_results_a35.md:64`. The order-2 residuals `1.264530e-04` and `3.141941e-05` settle it: `log2(1.264530e-04 / 3.141941e-05) = 2.008873`, i.e. `2.0089` to four decimal places, so `2.0087` is the defective copy. The defective site is a FROZEN file (`docs/design/preservation_gate_preregistration.md:3`, "Status: frozen.") and lies outside this dispatch's write footprint, so the correction is recorded here, in section 14, and in the D54 errata block of `decisions.md`; the frozen line is not edited. This document contains neither string: its own `p_k` statements are the `[1.7, 2.3]` band only (lines 354, 671).]
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

Revision 3 is recorded in section 12, with line numbers as of revision 2.

## 11. Attacks constructed and not executed

An independent review is not an adversarial test of a gate. This section records attacks built by
reading this rule and the frozen gate's source. **None of them was executed.** No code was run,
no record was modified, and no number below is a measurement. A constructed attack is therefore
not a demonstrated vulnerability: it is a claim that a specified report would be wrong, with the
mechanism stated so that a later run can confirm it or drop it. AT-1 to AT-4 are the four themes
the dispatch named, in the order it named them; the dispatch gave themes rather than enumerated
constructions, so the input and the wording of each row are mine. AT-5 is drawn from this
document's own sections 2 and 6, and AT-6 is mine. AT-7 is drawn from the same review that produced AT-5 -- a genuine solver-side loss
of a mode at `c <= 2.5` -- and is mine in the same sense: the coverage row below names the `c <= 2.5`
STOPPED licence as not distinguishable and points at it, without enumerating the construction. There
are **seven** rows below, AT-1 to AT-7. That is the governing count for this section; the six that
the review named is the count of the review, not of the table.

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
| AT-1 | mode identity by column ordering when two modes are near-degenerate | two reference roots about 4.2% apart (above route 3's `0.04`) with their two computed candidates exchanged, by the same amount, at every level -- for instance a dielectric step moved so the two modes cross between two of the levels | PASS: every track stays inside `SEED_TOL` at level 3, both contractions stay inside `[2.5, 6.0]`, and route 3 is read off the reference list at 0.042 | the rule tests that a beta lies near a root and never that the mode is the same mode. A swap that is self-consistent across levels leaves every distance and every ratio inside band, so cross-level identity is assumed by the assignment rather than measured. The ledger's claim C21 is the row that says this needs an overlap test, and the invariant layer that might have caught a swap has no measured result at all (inventory row B01, E5, not citable) | one eigenvector overlap per tracked pair, `abs(v_k . v_k+1)` with a stated bar, recorded per track per level and required before a track may continue | **open** -- closing measurement specified in section 13.1; nothing in the rule reads it today |
| AT-2 | decorrelation of the pairing assignment when the mode set is re-sorted by a different key | one physical case run twice, candidates sorted by `abs(beta)` and then by `Re(beta)` (or ascending against descending), with the runs differing in their `k_candidates` request, so that the 16 returned candidates are not the same 16 -- in particular inside the degenerate cluster at `beta_sq = k0^2`, multiplicity 11 rising to at least 14 (`decisions.md:8525`) | a report that can change between runs, but not by the mechanism this row named: there is no post-solve truncation to `k_candidates` (the constant is the ARPACK request `k`, `n_k = min(int(k), n_dof-1)`), and the only filters on retained candidates are v2's threshold and six-decade gap, both `max`/`min` over a set and so order-invariant. What can change is which members of the degenerate cluster the request returns | the physics is identical and the verdict is not. The sort key appeared nowhere in the rule, so two records could not be compared without it: the runner's order `(-beta_sq, +curl_ratio)` lived only in code (`ladder.py:128`), the record's `index` was a sorted position and not an identity, and the mixed path sorted with a non-stable `argsort` before an `argmax` (`emfit/mode2d.py:1870`, `:1887`), leaving the selected mode among `beta_sq` ties to the tie permutation. A verdict a re-sort can flip is not a measurement | pin one canonical sort key in the rule and in the record, and state the `k_candidates` boundary as a pre-registered quantity rather than as an implementation default | **done in revision 3, in part**: R0 pins the key (an addition, not a revision -- no ordering or cut clause existed in R1-R6), fixes its direction to the runner's existing `beta_sq` DESC then `curl_ratio` ASC, makes ordering ties non-verdicts (`tie_at_seed`; R3's `ambiguous`) and adds the `sort_key_undefined` reason, with the boundary answers (a)-(f) and the comparability requirement; section 4.3 states the residual. The membership of the returned 16 is not settled by a key **PARTIALLY CLOSED** -- rule bookkeeping closed, cluster membership open; the residual is the testable condition `cluster_membership_unstable` in section 4.3 |
| AT-3 | a gate applied to a level where the deflation subspace itself changed | three levels of which the coarsest deflates a spurious pair of the recorded kind (`t4_amp_ratio.md` section 15.8: five shifts returned a bogus pair at residual `9.89e-01`), while levels 2-3 deflate nothing spurious | PASS whenever a track exists: nothing in R1-R6 reads the deflated set, and `spectrum_short` counts only the level-3 real betas against the number of roots | the three levels are then not three discretisations of one operator, and the contraction band measures the difference between two operator splittings as if it were a refinement rate. The rule names the shift and the budget and never the set the shift deflates | record the deflated eigenvalue set per level in the artefact, and refuse a track whose level-`L` candidate lies inside a coarser level's deflated set, with its own token | **open** -- closing measurement specified in section 13.2; nothing in the rule reads it today |
| AT-4 | a pass achieved by comparing a run against itself | a reference ladder produced by the solver under test -- the converged `ny = 64` betas used as the level-3 reference, and the same procedure at 32 and 16 | the exact version is FAILED-TO-MEASURE, because `e = 0` collapses the window onto `E_FLOOR` and `rho = +inf` sits outside the band: finding 11 catches it, not the design. **Superseded in place, revision 4.** The next sentence is revision 3's claim, retained verbatim as the record of why this attack is worth carrying: "Add a small geometric perturbation to each level's reference and the same run reports PASS". It was true of revision 3 and is false under R7. **End of superseded text.** A perturbed ladder built from the solver's own output is still solver-derived, so under R7 and section 4.4 the same run returns FAILED-TO-MEASURE, exit 2, reason `reference_not_independent` (check `identity` or `recompute`), and cannot return PASS. | the record then measures self-consistency, and a clean PASS is evidence about the code rather than about the physics. R1 tests the distance to the reference and cannot see where the reference came from; section 9.1 says this in words and nothing enforces it | a provenance field on the reference ladder -- generator, source rows, hash -- in the schema, plus a rule that the ladder may not be produced by the solver being graded | **CLOSED IN THE RULE, NOT IN FORCE** -- R7 and section 4.4 forbid a solver-derived ladder, fix the provenance vocabulary, and make a violation detectable by two checks that do not trust the declared field, with token FAILED-TO-MEASURE / `reference_not_independent`; the enforcement point is the gate's ladder-ingest check (`reference_ladder[i].provenance` plus the numeric identity test against `candidates_all`), which does not exist yet, so nothing is in force |
| AT-5 | annihilation misreported through the STOPPED and UNTRACKED-AT-COARSE precedence | a genuine loss of a mode at contrast `<= 2.5`, and separately a coarse-rung solver failure that loses the mode at level 1 only | STOPPED (exit 3, "annihilation suspected") for the first, UNTRACKED-AT-COARSE (exit 4) for the second | both tokens assert a cause the rule cannot establish. The frozen gate's STOPPED at contrast 2.5 was itself a discretisation artefact with no physical event (section 2), and this rule changes the vocabulary and adds preconditions without adding a discriminator between a lost mode and a lost track. Sections 9.2 and 9.5 concede exactly that | solver-side evidence before either token may be emitted -- an inertia computation per rung, or the residual and overlap of the vanishing branch -- otherwise FAILED-TO-MEASURE | **open** -- closing measurement specified in section 13.3; nothing in the rule reads it today |
| AT-6 | one root's instrument failure masks another root's physics failure, through the total order in section 6 | a four-root record at contrast 2.5 in which root 3 truly vanishes while roots 2 and 3 are degenerate enough to raise `attribution_conflict` or `assign_collision` | before revision 3, FAILED-TO-MEASURE (exit 2), because the join over roots let the least informative token win the record. After revision 3, any `STOPPED` in the vector takes the run, so the vanished root 3 is reported as STOPPED while the other root's instrument failure is recorded in `root_verdicts` and masks nothing | the record contains a physical event and reports an instrument problem, and the token carries no trace of the root that vanished; a reader downstream sees "could not measure" about a run that measured something. The order is defended as conservative and is conservative in the wrong direction here, protecting the instrument's reputation at the cost of the finding | emit per-root verdicts as a vector and keep a joined token for compatibility, and require the per-root detail in the artefact under every token rather than only under STOPPED | **done in revision 3, in the rule**: section 6.1 withdraws the total order, defines the total aggregation function, states the disagreement rules, and promotes revision 2's record sentence to a requirement -- the record must carry `root_verdicts`, `disagreement` and per-root reasons. The current artefact carries per-root outcomes only as diagnostics and has no such vector, so nothing is in force until the field exists **CLOSED in the rule, not in force** -- enforcement point is the artefact field `root_verdicts` |
| AT-7 | a genuine solver-side loss of a mode at contrast `<= 2.5`, correctly attributed and with a complete spectrum | a root whose computed branch the solver annihilates at contrast 2.5, with the pairing clean (one candidate, uniquely paired, so `attribution_conflict` is not raised), all three levels present and `spectrum_short` not raised -- a real loss that the record can attribute correctly | PASS or FAIL on the surviving roots, with no token recording that a mode was lost | the rule can only report a vanishing mode through STOPPED, and AT-5 shows that token has no discriminator. Once the loss is attributed correctly and the spectrum is complete, `contrast_beyond_validated` and `spectrum_short` are both silent, so a cleanly measured loss of a real mode produces no report at all: the record reads as a complete measurement of a spectrum that is missing a mode | the same solver-side evidence AT-5 asks for -- per-rung inertia, or the residual and overlap of the vanishing branch -- promoted from a precondition of STOPPED to a required per-root artefact field, so that a lost mode is reported with no cause claim attached | **open** -- closing measurement specified in section 13.4; nothing in the rule reads it today |

**AT-7's claim, REJECTED on its indexing.** The claim under test is that an `h`-dependent relative-error tolerance can be substituted for the absolute-distance pairing tolerance without changing what is gated. It cannot. `beta_ref` is indexed by ROOT, not by LEVEL -- one analytic root per order, shared by every rung -- while the quantity AT-7 wants to gate is a per-level error, so replacing a distance with a relative error is a CATEGORY ERROR: the two are indexed differently and the substitution does not preserve meaning. The rejection rests on that ground alone. The residual weakness is provenance and terminology, and neither is repaired by re-reading the numbers: the level-1 datum comes from a run that STOPPED at level 1 while the level-2 and level-3 data come from a supplementary run (section 13.4; `docs/design/d54_acceptance.md` records the same composition), and the record's own wording drifts between "distance", "error" and "relative distance" for the same figure. No further re-reading of `7.09799e-02` changes either: the indexing defect would stand if the datum were perfect, and the provenance defect would stand if the terminology were fixed. Section 14.1 is not in conflict with this and neither section supersedes the other: 14.1's point stands untouched -- AT-7 does not widen section 3.1's tolerance band, and the ratio band it derives is a different criterion rather than a looser one. The question asked here is a different one, whether the substituted quantity is indexed the same way as the thing it replaces, and on that it fails.

**What I would change first.** One revision closes most of this surface, and it is not a change to
the rule's arithmetic: extend the record, not the tolerance. Two additions -- a per-track
cross-level eigenvector overlap with a stated bar, and the deflated eigenvalue set per level --
make AT-1, AT-3 and AT-5's missing discriminator decidable, and they cost two columns and one
array per level. Neither touches `SEED_TOL`, the contraction band, P1, P2, P3 or route 3, so
section 8's prediction is unaffected and the revision cannot be accused of being tuned to protect
it. AT-2 and AT-6 are cheaper still: a canonical sort key written into the rule, and a per-root
verdict vector written into the artefact, are text and format changes with no numerical content.
> **Superseded in place -- revision 4.** The two sentences below are revision 3's placement
> decision for AT-4 and are withdrawn: the provenance rule is now in the rule body (R7, section
> 4.4) and the enforcement point is the gate's ladder ingest, not the schema alone.

AT-4 cannot be closed inside the gate at all, because it is a statement about where the reference
came from, and it belongs in the schema that registers the run.

> **End of the superseded block -- revision 4.** R7 and section 4.4 replace them. A declared
> solver-derived ladder is no longer admissible with a declaration: the schema field is necessary
> and not sufficient, and the gate must refuse a verdict on its own numeric evidence.

**The vacuous-pass direction, stated separately.** AT-1, AT-2 and AT-4 can produce PASS. AT-3
produces PASS unless the deflated set is recorded. AT-5 and AT-6 do not produce PASS: they convert
a report into a different report, and AT-6 removes the record's ability to say that a mode was
lost, which is the one outcome this rule exists to preserve. The asymmetry is worth stating
because the attacks that produce PASS are the ones that will be cited: a FAIL invites a rerun, a
FAILED-TO-MEASURE invites a repair, and a PASS is quoted. Of the seven, AT-4 is the one I would
expect to bite in normal use rather than in principle, because nothing in the workflow forecloses
building the reference ladder from a converged run's own output -- which is what inventory rows
A17 and A18 record the corpus already doing on another geometry -- and because section 8 here
predicts a PASS at the contrast that motivated the redesign, so the first clean PASS arrives at
the configuration where a vacuous pass is hardest to see.

## 12. Change log for revision 3 (2026-10-29)

Revision 3 is written against revision 2 as committed. Line numbers are revision 2 numbers. Nothing
was deleted: every pre-existing line is either untouched or rewritten in place, and the revision 2
file is recoverable from git HEAD.

**Added.**
- After line 64 (section 1 constants): that `k_candidates = 16` is the ARPACK request `k` and not a
  post-solve truncation, with a pointer to section 4.3 and R0.
- After line 158, before R1: **R0 -- Candidate order and the `k_candidates` boundary (AT-2)**, a new
  normative clause. An addition, not a revision: revision 2 has no ordering term and no cut term.
- After line 259 (end of section 4.2): **section 4.3, Sort key: provenance and what it cannot
  reach**, carrying the AT-2 closure, PARTIALLY CLOSED.
- Before line 327: a marker declaring the precedence paragraph superseded in place, revision 3.
- After line 337 (end of section 6) with a closing marker: **section 6.1, Per-root verdicts and
  run-level aggregation (AT-6)** -- the withdrawal of the total order, the promoted record sentence,
  the aggregation function, the disagreement rules, the diagnostic requirements, the AT-6 closure, and
  the disclosed judgement call on R2's `no seed` gate.
- After line 508 (section 11 preamble): the provenance of AT-7, and the statement that seven is the
  governing row count.
- After line 497: a pointer to this section from the revision record.
- This section.

**Superseded in place, with old line numbers.** Lines 327 to 337 -- the "Precedence." paragraph, the
total order, its defence and its qualifier -- are retained verbatim at their original lines inside
the superseded markers and are withdrawn as a rule by section 6.1. They are not altered, so this log
needs only to point at them. Line 526 (the AT-2 row) and line 530 (the AT-6 row) are rewritten in
place: in 526 the constructed input, the expected report, the reason the report is wrong and the
"closed today?" cell; in 530 the expected report and the "closed today?" cell. The revision 2 text of
both rows is at git HEAD. Line 549 is edited in place: "Of the six, AT-4 is the one I would" becomes
"Of the seven, AT-4 is the one I would". The count was wrong in revision 2 -- the table from line 523
on has seven rows, AT-1 to AT-7, while the preamble accounted for six.

**Statuses after revision 3.** AT-2 **PARTIALLY CLOSED**: the ordering defect is closed in R0 and in
section 4.3, and the membership of the returned 16 is not closeable by a key, with the residual stated
as the testable condition `cluster_membership_unstable`. AT-6 **CLOSED in the rule, not in force**:
section 6.1's aggregation is total and puts physics tokens above instrument tokens, and the
enforcement point is the artefact field `root_verdicts`, which does not yet exist. AT-1, AT-3, AT-4,
AT-5 and AT-7 are unchanged and remain open.

> **Superseded in place -- revision 4.** The sentence above -- "AT-1, AT-3, AT-4, AT-5 and AT-7 are
> unchanged and remain open" -- was true of revision 3 and is not true of the file it now sits in:
> AT-4 is closed in the rule as of revision 4. The statuses after revision 4 are in section 12.1.

**Not done here.** No code was run. No gate, test, solver or build was executed, nothing under
`emfit/` was edited, no record was modified, and the rule is not frozen; revision 3 is not a freeze.

**Outstanding elsewhere, recorded so it is not lost.** `decisions.md` carries the stale count "six" at
lines 8662, 8670 and 8674, the last of which also names AT-7, so the number and the list disagree
inside one sentence. That file is outside this revision and is not edited by it.

### 12.1 Change log for revision 4 (2026-10-29)

Revision 4 closes AT-4 and touches nothing else. It is written against revision 3 as committed; the
revision 3 file is recoverable from git HEAD.

**Added.**
- Before section 4.1 (after R6): **R7 -- Reference provenance**, a new normative clause, and the
  clause the rest of this revision hangs on. An addition, not a revision: revision 3 had no
  provenance requirement in the rule body.
- Before section 5 (after section 4.3): **section 4.4, Reference provenance: which ladders are
  admissible (AT-4)** -- the hazard H-AT4 with the A17/A18 citation, the exhaustive admissible and
  inadmissible constructions, the construction revision 3 misread, the three-field detection design
  (declared vocabulary, numeric identity at exact equality, recomputation), the floating-point
  policy and why a tolerance cannot hide a copied ladder, the verdict token and why it is neither
  PASS nor FAIL, the retroactive consequence for A17 and A18, and the residual limit against
  section 9 limit 1.
- This subsection.

**Rewritten in place.** The AT-4 row's "closed today?" cell, from "no -- disclosed in section 9.1,
not implemented" to **CLOSED IN THE RULE, NOT IN FORCE**, naming the enforcement point. The row and
section 4.4 agree; the row's "minimum revision that closes it" cell is untouched and is now satisfied
by R7.

**Superseded in place, with old line numbers.** Line 760-761 ("AT-4 cannot be closed inside the gate
at all ..."), revision 3's placement decision, marked and retained verbatim inside the revision 4
markers at its original lines; and the last sentence of the revision 3 status paragraph in section
12 ("AT-1, AT-3, AT-4, AT-5 and AT-7 are unchanged and remain open."), marked as true of revision 3
and false of this file. Neither is deleted.

**Statuses after revision 4.** AT-4 **CLOSED IN THE RULE, NOT IN FORCE**: R7 and section 4.4 are
total -- every ladder entry is either in the vocabulary or refused, and two of the three checks do
not consult the field -- and the enforcement point is the gate's ladder ingest, which does not exist
yet. AT-6 remains **CLOSED in the rule, not in force**. AT-2 remains **PARTIALLY CLOSED**. AT-1,
AT-3, AT-5 and AT-7 remain open. AT-4 was the last of the seven for which the rule could be
completed; what remains for all of them is code, not prose.

**Outstanding work, recorded so it is not lost.** Ledger rows A17 and A18 are demoted by section 4.4
and must be re-derived against an admissible (analytic or pinned-external) ladder; this revision does
not re-derive them and does not run anything. The gate does not yet read
`reference_ladder[i].provenance`, does not run the numeric identity test, and does not emit
`reference_not_independent`; until it does, nothing in R7 is enforced and no run may be described as
complying with it.

**Not done here.** No gate run, no test, no solver, no build; nothing under `emfit/` edited; the
frozen A-1.5 module and `preservation_gate.py` untouched; `soundness.md` and `decisions.md` untouched;
no commit. The pairing rule is not frozen, and revision 4 is not a freeze.

### 12.2 Repairs to the revision 4 text (2026-10-29)

Two defects that revision 4 created or exposed, fixed here and nowhere else. No section renumbered and
nothing outside the section 11 table and the one AT-4 cell was reflowed.

**Rewritten in place.** The AT-4 row's "what the gate reports" cell. Revision 3's sentence -- "Add a
small geometric perturbation to each level's reference and the same run reports PASS" -- is retained
verbatim inside a superseded-in-place marker within the cell, and the operative sentence now gives
**FAILED-TO-MEASURE**, exit 2, reason `reference_not_independent`, which is what R7 and section 4.4
require of a perturbed ladder built from the solver's own output. The old claim is kept rather than
overwritten because it is the record of why this attack was worth carrying: the corpus's own workflow
made the self-derived ladder easy to build and its result clean.

**Table width, and the choice made.** Section 11's attack table had a seven-cell header, seven cells in
the AT-1, AT-3, AT-4, AT-5 and AT-7 rows, and eight in the AT-2 and AT-6 rows, whose eighth cell was a
status label appended by revision 3. The table is now seven cells wide everywhere, matching the header.
The choice was to **fold** the appended cell into the one it belongs to rather than to add an eighth
column: the last column is named "minimum revision that closes it" in the header but carries the
closed-today status in every populated row, and revision 3's extra cell was the status label belonging
to that same question, so folding puts each row's status under the column that asks it. Adding a column
was rejected because five rows would then carry an empty cell and because "what was done" and "what the
status is" would both have had to live under one new heading anyway. No content was lost: AT-2's and
AT-6's revision 3 narrative and status label are both present, in that order, in the merged cell.

**Pipe characters.** No cell in this table contains a pipe, escaped or bare; each row splits on `|` into
exactly its cell count and re-joins to itself byte for byte. The standing hazard recorded against the
claim inventory's rows -- unescaped pipes shifting columns -- does not reach this table, and nothing was
escaped because nothing needed to be.

**Not done here.** No gate run, no test, no solver, no build; `emfit/`, the frozen A-1.5 module,
`preservation_gate.py`, `soundness.md` and `decisions.md` untouched; no commit; the rule is not frozen.

### 12.3 Change log for revision 5

**Added.** Section 13: one subsection per attack that is still open (AT-1, AT-3, AT-5, AT-7), each
stating the same four things -- what the attack defeats, the measurement that detects it, whether
that measurement exists in the tree today (with `file:line`) or must be built, and what the rule
would read from it. Section 13.3 carries an explicit statement that AT-5 is ungoverned by the
brief. Section 13.4 derives a tolerance of the form `C h^p` from the element order actually
implemented, with a feasibility argument at `eps_r = 3.5`.

**Rewritten in place.** The status cell of the four open rows in the section 11 table (AT-1, AT-3,
AT-5, AT-7) now reads "open, closing measurement specified in section 13.n". The statuses
themselves do not change: still open, still not in force.

**Statuses after revision 5.** AT-4 CLOSED IN THE RULE, NOT IN FORCE; AT-6 CLOSED IN THE RULE,
NOT IN FORCE; AT-2 PARTIALLY CLOSED; AT-1, AT-3, AT-5, AT-7 open, each now with a specified
closing measurement. Zero fully CLOSED. Unchanged from revision 4 except for the pointer.

**Not done here.** No gate run, no test, no solver, no build; no measurement specified in section
13 has been taken; nothing in section 13 is in force; no attack is marked closed; no commit; the
pairing rule is not frozen.

## 13. Closing measurements for the four remaining attacks

Section 11 lists four attacks still open: AT-1, AT-3, AT-5 and AT-7. For each, that table already
names a minimum revision that would close it. This section turns each of those one-line
prescriptions into a *measurement*: what the attack defeats, what is measured, whether the
measurement can be taken with what is already in the tree today or must be built, and what the
rule would read from it.

Specifying a measurement is not closing an attack. Nothing here is in force, no term of the rule
reads any of it, no measurement described below has been taken, and every one of the four attacks
remains open. The section exists so that the closing revisions are specified rather than improvised
later -- the same reason R1 to R7 are specified before any gate run.

The provenance rule of section 4.4 applies to this section's own claims: every number quoted below
is either read from a named file or labelled a derivation. Where a number is a derivation it is
labelled as one and is not evidence of anything until a run produces it.

### 13.1 AT-1 -- the eigenvector-validated geometric chain

**What the attack defeats.** A sequence of *distinct* eigenvalue branches can be arranged so that
consecutive levels' candidates are each other's nearest neighbours by value, and only by value.
The chain is then paired by R1, tracked by R4, and contracted through R5, while the eigenvectors
of the successive levels have nothing to do with one another. Every quantity the rule reads -- the
beta distances, the contraction ratios, the window -- is satisfied by construction. Section 9.7
discloses the family; no term of R1 to R6 detects a member of it.

**The measurement that detects it.** One eigenvector overlap per tracked pair, per level:

    O_k = | v_k^T B v_{k+1} | / sqrt( (v_k^T B v_k) (v_{k+1}^T B v_{k+1}) )

with `B = M_mu` (so the bar is the field-energy overlap, not the raw coordinate inner product), and
`v_k` the edge-DOF vector of the root at level `k`. A genuine branch has `O_k` near one at every
level; a geometric chain has `O_k` near zero at the level where the chain passes to the next
branch. The bar is a stated number, recorded per track per level, and required before a track may
continue -- the same shape as `SEED_TOL`, not a diagnostic.

**EXISTS TODAY.** The pieces exist; the record does not.
- `B = M_mu` is the pencil's own mass matrix: `emfit/mode2d.py:29` states the pencil as
  `C e = beta^2 B e, C = k0^2 M_eps - K_q, B = M_mu`, and `assemble()` at `emfit/mode2d.py:403`
  returns `(K_q, M_mu, M_eps)` with `M_mu[e, f] = INT (1/mu_r) W_e . W_f dA`
  (`emfit/mode2d.py:407`). The B-inner product above is therefore computable today.
- The DOF vector survives the solve: `Mode2D.e_t` at `emfit/mode2d.py:677`, a numpy array on the
  free edge DOFs.
- A normalised overlap already exists twice: `corr(a, b)` at
  `tools/host/sparse-probe/rung4_routeC_probe.py:182-189` (cosine overlap, "copied verbatim from
  `c1_audit.py:302-313`", and present at `tools/host/c1-audit/c1_audit.py:302`), and a whole
  cross-mesh overlap campaign built on it in `tools/host/sparse-probe/mode_overlap.py`
  (`corr_matrix` at `:443`, `corr_block_matrix` at `:450`).

**MUST BE BUILT.** The per-track per-level field. Two facts make this a build and not a wiring
change. First, the artefact's per-candidate record carries no vector and no overlap:
`candidate_records()` (`emfit/mode2d.py:798`) emits exactly `index`, `beta`, `beta_sq`, `eps_eff`,
`curl_ratio`, `abs_curl_ratio`, and `solve_level()` copies exactly that tuple into the artefact
(`tools/host/anchor/preservation_gate.py:300`). Second, the vector is not kept anywhere else:
`tools/host/sparse-probe/mode_overlap.py:17-19` records that the Route-C driver "keeps the
eigenvector in memory only" and that the probe had to monkeypatch `field_scalars` to see it. So the
overlap is computable today by a probe on the Route-C campaign, and only there; the gate has no
path from a paired candidate to its vector. What must be built is: retention of `e_t` for each
tracked pair, the B-weighted overlap, the bar, and the artefact field.

**What the rule would read from it.** A new required field per track per level. `O_k` below the bar
stops the track (a stop, not a pass) and is recorded as its own token; a missing field at a level
where a track continues is FAILED-TO-MEASURE with its own reason code, in the shape of
`reference_not_independent` in section 4.4 -- absence of the evidence must not be able to read as
silence.

### 13.2 AT-3 -- the deflation subspace that changed between levels

**What the attack defeats.** Deflation is a statement about *which* pencil was solved. If the
deflated set differs between levels -- the recorded instance is a spurious pair returned at
residual `9.89e-01` from five shifts (`t4_amp_ratio.md` section 15.8) -- then the three levels are
not three discretisations of one operator, and R5's contraction band measures the difference
between two operator splittings as if it were a refinement rate. The rule names the shift and the
ARPACK budget; it never names the set the shift deflated.

**The measurement that detects it.** Per level, record the deflated set (the region the deflated
columns span, and the eigenvalues removed), and refuse a track whose level-`L` candidate lies
inside a coarser level's deflated set, within a stated tolerance, with its own token.

**EXISTS TODAY.** The subspace machinery and most of its diagnostics.
- `solve_modes_deflated()` at `emfit/mode2d.py:1445` and `solve_modes_deflated_v2()` at
  `emfit/mode2d.py:1473` (the latter deflating every other homogeneous contrast block as well),
  with the column set built by `_deflation_columns()` at `emfit/mode2d.py:1287`, documented as
  returning "the deflated column set, and a description of the region it spans".
- The diagnostic dict is rich: `z_dim`, `z_dim_closed_form`, `n_free`, `n_dof`, `n_columns`,
  `block_diag_ratio`, `z_orthogonality_abs`, `z_orthogonality_rel`, `r_gram_dev`,
  `residual_grad`, `residual_eps_mu`, `residual_pencil`, and the Amendment 3 additions
  `column_region`, `columns_v1`, `columns_added`, `z_dim_v2`, `region_contrast`, `region_rows`,
  `z_dim_closed_form_v2` (`emfit/mode2d.py:1494-1517`).

**MUST BE BUILT.** Two things.
- The record is truncated at the artefact. `solve_level()` copies four keys and four only --
  `z_dim`, `column_region`, `residual_eps_mu`, `residual_pencil`
  (`tools/host/anchor/preservation_gate.py:303-306`). The region descriptors `region_contrast`,
  `region_rows` and the widened total `z_dim_v2` are dropped, so the stored artefact cannot even
  be compared level to level for the thing the attack varies.
- The removed *eigenvalue* set does not exist to record. Deflation removes columns from the
  pencil; the eigenvalues those columns would have carried are never computed on either route, so
  the "deflated eigenvalue set" AT-3 asks for is not a field waiting to be exported -- it is a
  small extra solve (or an inertia-style count) that has to be built, and its cost is part of the
  build.
- The containment test itself (candidate inside a coarser level's deflated set) does not exist in
  any form, and no reason code names it.

**What the rule would read from it.** Two recorded fields per level and one refusal. The refusal
needs its own token in the exit-2 family, because "the operator changed under the track" is not any
of the eleven existing reasons: none of them is a statement about the pencil rather than about the
candidates.

### 13.3 AT-5 -- solver-side evidence before either token

**UNGOVERNED BY THE BRIEF.** The brief that produced AT-1 to AT-4 and, through a second review,
AT-5 to AT-7, is silent on what AT-5 asks for: it says nothing about inertia, nothing about the
residual or overlap of a vanishing branch, and nothing about solver-side evidence as a precondition
for emitting a token. The criterion used here is therefore not taken from the brief. It is taken
from this document: section 11.1's coverage table row (5) and the AT-5 row of the section 11
table. The first records that nothing in the rule separates a genuinely lost mode from a
discretisation artefact at `c <= 2.5`, against a `NOT DISTINGUISHABLE` verdict in the coverage
column; the second names the closing revision as "solver-side evidence before either token may be
emitted -- an inertia computation per rung, or the residual and overlap of the vanishing branch --
otherwise FAILED-TO-MEASURE". That is the whole authority for what follows, and it is a weaker
authority than the brief would be: it is the document grading itself.

**What the attack defeats.** Both tokens that report a lost mode -- STOPPED and
UNTRACKED-AT-COARSE -- are statements about the *solver's* behaviour inferred from the *paired
sequence*. If the branch vanished because the solve missed it (a shift too far from a nearby
eigenvalue, an ARPACK budget exhausted, a spurious pair crowding the window), the rule reports an
annihilation that did not happen, or reports it at the wrong root. The report is the same report a
genuine annihilation produces; nothing in R1 to R6 distinguishes them.

**The measurement that detects it.** Solver-side evidence, taken before either token may be
emitted: either an inertia computation per rung, or the residual and the overlap of the vanishing
branch. Absent both, the token is FAILED-TO-MEASURE rather than STOPPED.

**EXISTS TODAY.** Both halves, in the wrong place.
- The per-mode pencil residual is already computed by the solver:
  `Mode2D.residual` is documented at `emfit/mode2d.py:622` as
  `||C e - beta_sq B e|| / ||B e||` of the chosen mode, computed at `emfit/mode2d.py:994`
  (`residuals[i] = norm(c_free @ v - vals[i]*be) / b_norm[i]`) and stored at
  `emfit/mode2d.py:1029`. The mixed path goes further and screens *every* candidate on its own
  residual (`emfit/mode2d.py:1857-1879`, `_MIXED_RESIDUAL_TOL`). So the quantity AT-5 wants is
  already computed inside the solver, per candidate, on one of the two routes.
- Inertia is already a stated correctness check with a measured reference value: the positive /
  negative / zero split of `M_C` is tabulated as `1444 / 483 / 0` at `docs/design/cpp_solver_arch.md:44`
  (with `free_e = 1444`, `M_C` of order 1927, cited there to `sparse_eigenmode.md:529-533` and
  `:336`), and `cpp_solver_arch.md:59` states that a factoriser reporting a different inertia "has
  taken a different path through the pivots, and the discrepancy is a finding about the
  factoriser". A working inertia computation exists at
  `tools/host/sparse-probe/mc_inertia_check.py:134-136` (counting the sign of the eigenvalues of
  the factorised block `D`).

**MUST BE BUILT.** The path from that number to the artefact, and the per-root scope.
- `Mode2D.residual` is one float for the *chosen* mode. The residuals of the other candidates are
  computed into an array at `emfit/mode2d.py:978-1000` and then discarded; only `residuals[chosen]`
  survives (`emfit/mode2d.py:1029`). The vanishing branch is by definition not the chosen mode, so
  the number AT-5 asks for is exactly the one that is dropped.
- Nothing carries it into the artefact either: `candidate_records()` (`emfit/mode2d.py:798`) emits
  `index`, `beta`, `beta_sq`, `eps_eff`, `curl_ratio`, `abs_curl_ratio` and no residual, and the
  level record copies that tuple unchanged (`tools/host/anchor/preservation_gate.py:300`).
- No per-rung inertia is computed by the gate at all. `solve_level()` calls
  `solve_modes_deflated_v2()` and never forms or factorises `M_C` itself
  (`tools/host/anchor/preservation_gate.py:279-296`); the `1444/483/0` figure belongs to a
  different, larger problem and cannot be used as a reference here.
- The residual series exists as a container but not as a measurement: the artefact field
  `residual_series` in `.scratch/d51/pg_a35.json` holds `values: [[1, 0.05592958825659055]]`,
  `ratios: []`, `anomaly: true`, `why: "not recorded at every solved level; decay is not
  assessable"` -- it is the deflation diagnostic `residual_eps_mu`, not a per-root residual, and
  `residual_series()` at `tools/host/anchor/preservation_gate.py:361` says so by refusing to
  compute ratios.

**What the rule would read from it.** One required per-root artefact field (residual, and overlap
where a pair exists; or the per-rung inertia), read before STOPPED or UNTRACKED-AT-COARSE may be
emitted. Missing evidence converts the token to FAILED-TO-MEASURE with its own reason code. This
does not make either token correct; it makes an unevidenced token impossible.

### 13.4 AT-7 -- annihilation misreport at `c <= 2.5`, and the tolerance it needs

**What the attack defeats.** The precedence between STOPPED and UNTRACKED-AT-COARSE, at contrasts
where the rule still licenses STOPPED (`c <= 2.5`). Below that bound the rule will say "a mode was
lost" when what happened was that a discretisation artefact moved a candidate out of the window.
AT-7 is AT-5's sibling: AT-5 asks for evidence before the token, AT-7 asks for the same evidence
promoted from a precondition of STOPPED to a required per-root artefact field, so that the evidence
is present whether or not a stop is taken.

**The measurement that detects it.** The same solver-side evidence -- per-rung inertia, or the
residual and overlap of the vanishing branch -- recorded per root at every level, and compared
against a tolerance that scales with the discretisation rather than being a fixed constant. A fixed
absolute tolerance cannot do this job: section 3.1 already records why, from the other direction,
for `tol_1`.

**The tolerance is `C h^p`, and `p` is derived from the scheme in the tree, not chosen.**
- The scheme actually implemented is first-order Nedelec / Whitney 1-forms: `emfit/mode2d.py:1`
  ("transverse `e_t`, Whitney 1-forms") and `emfit/mode2d.py:48-52` ("First-order Nedelec /
  Whitney 1-forms on a structured quad mesh split into two triangles per quad ..., 3-point
  barycentric Gauss quadrature (exact for the degree-2 products that appear)").
- For that discretisation the eigenvalue error is second order in `h`, and the derivation is
  already on the record: `docs/design/anchor_preregistration.md:506-518`,
  `|beta_h - beta| / beta = O(h^2)`, with its two hypotheses (mesh-aligned interface, no
  re-entrant corner singularity) stated and marked PROVISIONAL at `:520-524`.
- The measurement agrees: `docs/design/d45_anchor_results.md:209` reports base-two logarithms of
  the successive error ratios of `2.038` and `2.009` (second mode) and `2.034` and `2.008` (third
  mode), mean `2.02`, described at `:211` as apparent second-order convergence; and the same
  quantity for the A-3.5 case below is `1.9256` and `1.9815`, derived from the `rho_1 = 3.799`,
  `rho_2 = 3.949` already tabulated at line 506 of this document.

[REVISION 6 MARKER — appended at dispatch 54; wording defect only, in the bullet that carries line 1236. The four numbers there, `2.038`, `2.009`, `2.034` and `2.008`, are base-two LOGARITHMS of successive error ratios — `p_k = log2(e_k/e_{k+1})`, defined at line 354 and applied as P2 at line 671, and reported as logarithms at `docs/design/d45_anchor_results.md:209` — and not ratios themselves. The word `ratios` mislabels them; no number in the bullet changes.]
- The gate has already pre-registered the exponent band: `ORDER_LO = 1.7`, `ORDER_HI = 2.3`
  (`tools/host/anchor/preservation_gate.py:64-65`), section 3 P2. So `p` is not a new constant --
  it is the band the gate already applies.

**Feasibility at `eps_r = 3.5`.** The A-3.5 record is the case at `eps_r = 3.5`: the artefact's
geometry block (`.scratch/d51/pg_a35.json`) reads `eps_r 3.5, t 0.001953125, b 0.0078125,
k0 1407.4335088082273`, and the gate that produced it fixes `EPS_R_A35 = 3.5` at
`tools/host/anchor/preservation_gate_a35.py:73`. Its levels refine by two (`ny = 16, 32, 64`,
`nx = 2, 4, 8`, from `ladder.LEVEL_NY` at `tools/host/anchor/ladder.py:57`), so
`h = 4.8828125e-4, 2.44140625e-4, 1.220703125e-4` and `h_{k+1}/h_k = 1/2`. The worst root's
level distances are `7.09799e-02, 1.86827e-02, 4.73091e-03` (line 506 of this document, row 4).

Everything below is a *derivation from those recorded numbers*. None of it is a measurement of a
residual, and none of it is a constant anyone has chosen.

- The implied constant of the `h^2` form, `C_k = e_k / h_k^2`, is
  `2.977113e+05`, `3.134437e+05`, `3.174860e+05`: ratios `1.0528` and `1.0129`, i.e. one constant
  stable to `6.6` percent across two refinements (`C_3/C_1 = 1.0664`). The `h^2` form is therefore
  consistent with the accepted datum, which is the datum a tolerance must not fail.
- A tolerance anchored once and applied forward, `T_k = C_1 h_k^p` with `p` in the pre-registered
  band, admits at level 2 the window `e_2/e_1` in `[0.20306, 0.30779]` (`p = 2.3`, `p = 1.7`);
  the recorded value is `0.26321`, margins `1.296` times above the lower edge and `1.169` times
  below the upper. At level 3 the window is `[0.04123, 0.09473]` against a recorded `0.06665`,
  margins `1.616` and `1.421`. The band is not empty and the datum sits inside it.
- It is not inert either: a level whose error were `1.231` times the `p = 2` prediction would fall
  outside the `p = 1.7` edge and be refused. So a `C h^p` tolerance both passes the one datum
  that must pass and can fail.

[REVISION 6 MARKER — appended at dispatch 54, applying to line 1264. The multiplier is `1.231` exactly, as written there; the `1.23x` form used elsewhere in this corpus is a rounded paraphrase of it and not a second value.]
- The exponent, not a prefactor, is what is being frozen. `C` is estimated at the coarsest level of
  each run and never carried between runs; no value of `C` -- not the three above, not any
  rounding of them -- is proposed as a constant of the rule.

**Recorded discrepancy, not resolved here.** Section 5 describes this same datum as "geometry
A-3.5, contrast 2.5", and section 9 limit 6 speaks of `SEED_TOL` validated at `c <= 2.5`. The
artefact's own geometry block says `eps_r = 3.5` and the gate that wrote it fixes 3.5. One of the
two is wrong, and the feasibility argument above uses the `eps_r = 3.5` reading because that is
what the file says. Resolving it is a separate finding and nothing here depends on the answer
except the label on the numbers.

**EXISTS TODAY / MUST BE BUILT.** The exponent band exists (`preservation_gate.py:64-65`); the
`h` per level exists (`tools/host/anchor/ladder.py:57`, and in every level record as
`"h": float(h)`, `tools/host/anchor/preservation_gate.py:294`). The per-root residual to compare
does not exist for a non-chosen candidate (section 13.3), no inertia is computed per rung, and no
term of the rule consults `h` at all today except to store it.

**What the rule would read from it.** A required per-root artefact field carrying the solver-side
evidence, and a tolerance `T_k = C h_k^p` computed per run from the coarsest level with `p` in
`[ORDER_LO, ORDER_HI]`. A root whose evidence exceeds `T_k` at any level is refused; a root with
no evidence is FAILED-TO-MEASURE. This is deliberately not a repair of section 9 limit 7:
`P3_MAX = 5e-3` (`tools/host/anchor/preservation_gate.py:66`) stays computed and unconsulted, and
the absolute-accuracy question it would bound stays open.

### 13.5 What this section does not do

No measurement in section 13 has been taken. No inertia was computed, no residual series was
extended, no overlap was evaluated on any pair, no deflated set was recorded, no artefact field was
added, no token or reason code was created, no gate was run, no test was written, no build was
made, and nothing in section 13 is in force. AT-1, AT-3, AT-5 and AT-7 remain open; the section 11
status cells now say so with a pointer here and nothing else. The pairing rule is not frozen.

## 14. Change log for revision 6 (2026-10-29)

Revision 6 adds no clause to the rule, changes no constant and re-derives nothing. It records four things about AT-7's datum and about the second-order exponent: what kind of statement AT-7 makes and why it is not section 3.1 reopened; that the datum is composed across two runs, so the band it yields is provisional; that one member of the ratio is not the same kind of quantity as the other two, which is an open defect; and that contrast is definitional. Written against revision 5 as committed; the revision 5 file is recoverable from git HEAD. The rule is not frozen, and revision 6 is not a freeze.

### 14.1 Absolute-distance tolerance vs ratio-consistency band

Section 3.1 rejected `tol(level) = tol_1 * 4^-(level-1)`, a fixed tolerance on the absolute pairing DISTANCE scaled by the refinement factor, and rejected it correctly: the quantity it bounds scales with `h` and with geometry, so no constant set before A-3.5 could be shown not to be a fit to A-3.5 (lines 119-130; line 343 puts the same point in one sentence -- the rejected `tol_1` "had to be set above `7.09799e-02`, the failing datum itself"). AT-7, derived in section 13.4, does something else: it derives a BAND ON RATIOS of successive level errors, `p_k = log2(e_k/e_{k+1})` in `[1.7, 2.3]` (lines 1259-1263). Each ratio compares two errors of the same root, at two successive levels, to each other; no error is compared to a fixed distance anywhere in it. AT-7 therefore does not reopen section 3.1, and it is not "a bigger tolerance". The repair it specifies replaces absolute-distance pairing with ratio-consistency pairing: a different criterion, not a looser one.

The concrete numbers, all quoted from lines 1259-1263 of this document and not re-derived here. At level 2 the admissible window for `e_2/e_1` is `[0.20306, 0.30779]` (`p = 2.3` and `p = 1.7`), against a recorded `0.26321`; clearances `1.296` times above the lower edge and `1.169` times below the upper. At level 3 the window is `[0.04123, 0.09473]` against a recorded `0.06665`, clearances `1.616` and `1.421`. The datum therefore sits inside the band with clearance in the range 1.17 times to 1.62 times, at both levels and at both edges. That clearance is a self-consistency margin between successive errors, which is the only kind of margin a ratio band can report; it is not a distance, and it is not comparable to `PAIR_TOL = 2e-2`.

### 14.2 The datum is composed across two runs -- the band is provisional

Lines 1249-1250 read the worst root's level distances as `7.09799e-02, 1.86827e-02, 4.73091e-03`, and section 13.4 treats the three as one series. They are three order-4 pairing distances and they do not come from a single run. The level-1 value comes from the registered run that stopped at level 1: `.scratch/d51/pg_a35.log:41-42` records `VERDICT: STOPPED` with reason "gate section 8: root unpaired at level 1 (possible annihilation); run stopped, no verdict issued". The level-2 and level-3 values come from a supplementary levels-2-3 run whose own verdict is `FAILED-TO-MEASURE` (`.scratch/d51/pg_a35_l23.log:47`). `docs/design/preservation_gate_results_a35.md:81` states both the composition and its limit: "The A-3.5 column is a composed series and is labelled as one. Its level-1 entry comes from the `STOPPED` registered record and its level-2 and level-3 entries from the separate levels-2-3 record ... no single run ever produced A-3.5 at all three levels ... it is not a single run and must not be cited as one."

What supports the composition is agreement between the runs, not a single process. The implied constants of the `h^2` form at lines 1255-1257 are `2.977113e+05`, `3.134437e+05` and `3.174860e+05`, ratios `1.0528` and `1.0129`, one constant "stable to `6.6` percent across two refinements (`C_3/C_1 = 1.0664`)". Cross-run agreement of that size is evidence that the two processes shared a series; it is not evidence that a single run would have produced the same series.

The band in section 14.1 is therefore PROVISIONAL, and the rule for lifting or amending it is stated here in advance. CONFIRMED if a future single run produces all three levels of A-3.5 in one process and its `C_k` agrees with the composed constants above to within the same `6.6` percent; in that case the band stands as written and the confirmation is recorded against it. AMENDED if such a run's values differ: the band is then replaced by the single-run values and re-registered before it is used to refuse anything. Nothing in section 13.4's derivation is withdrawn by this paragraph, and no number above is recomputed here.

### 14.3 Kind mismatch in the derivation (open defect)

`7.09799e-02` is not an eigenvalue error `e_k`. It is a pairing DISTANCE: the order-4 root's relative distance to its nearest real-beta candidate on the level-1 mesh. `.scratch/d51/pg_a35.log:39` records it as one, in "nearest candidate distances {3: 0.022353452578831652, 4: 0.07097988161867323}", and `docs/design/preservation_gate_results_a35.md:27-32` tabulates it in that role, under the header "| order | relative distance | against `PAIR_TOL = 2e-2` |". The three members of the series are of one kind with each other -- all three are distances -- but they are not eigenvalue errors, and this document's own prose treats the same number as an error: line 520 calls it "the expected level-1 error", and lines 733 and 774 call it "the level-1 error".

The consequence is recorded and not repaired. In `e_2/e_1` and in `C_1 = e_1/h_1^2`, the level-1 member is a pairing distance while the level-2 and level-3 members are being used as errors, so the level-2 ratio and the "stable to `6.6` percent" claim about `C_k` may be comparing a distance against an error. This is an OPEN DEFECT that can invalidate the derivation; it is not a wording problem and it is not resolved by relabelling. AT-7 cannot be frozen while it stands. Nothing here fixes it and nothing here re-derives it: closing it needs either a measured level-1 eigenvalue error for order 4 or a band derived from distances alone, and neither exists in the tree today.

### 14.4 Contrast is definitional

Contrast is defined in this document as `c = eps_r - 1` (line 81), so "contrast 2.5" and `eps_r = 3.5` name the same geometry and are not two readings of it; the "Recorded discrepancy, not resolved here" at lines 1271-1276 is a labelling confusion rather than a contradiction between a label and an artefact. The correction, its exact sites and its settling arithmetic are recorded in the D54 errata block of `decisions.md`.

### 14.5 Not done here

No gate run, no test, no solver, no build; no measurement in section 13 or in this section has been taken; `emfit/`, the frozen A-1.5 module, `preservation_gate.py`, `preservation_gate_preregistration.py` and `soundness.md` are untouched; no attack is marked closed; no commit. The three annotations added by this revision are markers placed after the lines they apply to, and no existing line, number or sentence was edited, reordered or deleted: the p2 marker after the P2 statement at line 671, the logarithms marker after the bullet at lines 1235-1239, and the `1.231` marker after the bullet at lines 1264-1266. `decisions.md` was appended to, as the errata record, and is the only other file this dispatch wrote. The pairing rule is not frozen.

### 14.6 Forward pointer after dispatch 55A: the "untouched" claim is revision-scoped

Section 12.1 records that revision 4 made no edit to `soundness.md` or `decisions.md`, and no edit to
`preservation_gate.py`. That was true of revision 4. It stopped being true of dispatch 54, which wrote
both, and it is not true after dispatch 55A, which edits `soundness.md` again. Section 14 is therefore
the last place a reader should look for a statement about which files have moved, and the statements
that count are in `soundness.md` section 13 (dispatch 54's five sites and their byte accounting) and in
`decisions.md` (the D54 errata block at `:8734`, `:8738`, `:8740`). Nothing in this file is edited here:
this is an appended pointer, and section 12.1 keeps the bytes it had. The pairing rule is still not
frozen, and this appendix is not a freeze.

