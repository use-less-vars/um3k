# A behavioural S-parameter block in an explicit leapfrog loop: an enquiry

Status: OPEN enquiry against commit `a69ed43`. Not a decision, a plan or a gate; no code
proposed. Read-only: nothing was run, measured or fitted. Every claim carries a
`file:line`; anything that does not is marked as a claim.

## 1. What this document is

An enquiry into one object: a device known only by its two-port S-parameters — a
Touchstone file — attached at the port or at the terminating cut of the field solver,
whose port currents the time loop must produce by convolving its admittance.

The subject is a *behavioural block*, not a material property. Nothing here concerns a
frequency-dependent permittivity distributed over cells; the tree's parking lot for that
is `docs/roadmap.md:324-326` and it stays parked. A block is an object with terminals, and
this solver already has a terminal interface (§3); a per-cell material has nothing to
attach to.

## 2. The question

How does a device known only by `S(f)` enter the explicit leapfrog loop such that:

(i) the discrete step has an exact energy statement, in the shape of
`emfit/terminations.py:214-216`;
(ii) the fitted model cannot manufacture energy;
(iii) the existing `|S11|^2 + |S21|^2` gate (§7) can grade the result;
(iv) per-step cost stays inside the virtue of a nineteen-line explicit stencil
(`emfit/evolve.py:114-132`) — cheap per-step work, no iteration.

The four are not independent and none of them is about choosing an algorithm. (i) is
bookkeeping, (ii) is a property of the fitted object, (iii) is an existing gate's reach,
(iv) is the loop. A proposal that answers one and not the others is a different proposal
from this one.

The rule this document leans on throughout is `docs/design/defect_register.md:849`: "a
gate that sums two numbers must be able to say which estimator produced each, or it is
summing a measurement and a residual". It is quoted because it makes the provenance
question (Q5) askable, nothing more.

## 3. What already exists

The tree already has the interface a behavioural block would use, and has shipped one
1-port instance of it.

`emfit/terminations.py:26` defines `TerminalPort` (exported, `:23`), described at `:27` as
"The edge bundle one lumped termination is attached to". `L` (`:31-34`) is an incidence
matrix mapping terminal currents onto edges — "Topology only, no lengths", and reversing a
terminal's orientation flips the corresponding column. `W_E` (`:35-38`) is the edge metric,
used only as the coefficient matrix of a solve. Terminal voltages are `L.T @ e` (`:91`,
returned `:109`); edge current densities are `solve(W_E, L @ i)` (`:111-112`). The
load-bearing sentence is `:42-47`: terminal power `v @ i` and field power `e @ (W_E @ j)`
"agree identically -- for any `L` and any *invertible* `W_E`", and symmetry of `W_E` is
never used. That identity is algebraic, so a device attached at four terminals instead of
two inherits it without new mathematics. Sign convention at `:49-55`.

`RLCState` (`:235-236`) is the shipped 1-port behavioural block: history is three vectors
of length `n_terminals` (`:256-258`); a step never mutates state and returns a new one
(`:262-264`); the coupling is expressed "entirely in the port's voltage and
current_density functionals" (`:271-272`). `step_rlc` (`:294`) "Solves the block (n_t x
n_t) that couples the load current to the terminal voltage" (`:297-298`) with "no Newton
iteration ... involved or needed" (`:299-300`); `:198` is that single solve. The driver is
`emfit/coupling.py:289` `run_terminated`, whose docstring `:290-297` states that each step
is one `step_rlc` call around the load-free update, the load reacting only through the
port's own edges.

Both Touchstone directions exist: `emfit/ports.py:1801` `write_touchstone(handle, freqs,
s, *, z0=50.0, fmt="ri")` writes an option line at `:1804` carrying `z0` and the data
format, and `:1859` `read_touchstone` returns `(freqs, s[f, out, in])`.

There is a provenance-token precedent, from DR-43: `emfit/studies.py:1693-1698` adds
`s21_provenance`, "the estimator that produced it and the plane it was taken on, e.g.
`cut_plane@20.400mm`; `None` when no admissible estimator exists and no number may be
published"; initialised `:4047-4048`, set only on the cut branch (`:4119`), left `None` on
the span-ratio branch (`:4142-4148`), carried into the record (`:4300`, `:4445`).

What does not exist: no convolution, no fitting, no per-device history. A regex sweep of
`emfit/` and `tests/` for
`plrc|recursive|convolut|vector_fit|residue|rational|poles|drude|lorentz|debye` returns one
hit, `emfit/abc.py:74` "Rationale:" — a false positive. **No `.s2p` exists on disk**: a
recursive glob for `**/*.s2p` matches nothing, so the first input to any such project is
missing and "where does the first S2P come from" is a question (Q1), not an assumption.
The C++ side carries no such state either (`docs/design/cpp-kernel-spec-2026-11-09.md:139`:
"no split field, no auxiliary differential equation, no convolution state").

## 4. Vector fitting and PLRC are not alternatives at the same level

Vector fitting answers one question: given samples of an admittance `Y(jω)`, which rational
function — poles and residues — reproduces them? Recursive convolution (PLRC) and
state-space/ADE answer a different one: given that rational function, how does it become a
time-marching update? PLRC carries the past in a kernel recursion over port history; a
state-space form advances one auxiliary state per pole beside the port current. Both
consume a fit; neither produces one. Presenting the three as peer options hides the real
missing artefact — per §3 there is no fitting step, and no input to fit.

The structural point is that this codebase has already chosen one of the two
representations. `terminations.py:198` solves for the branch current with the field
half-step (`:185`) folded into the same implicit step, `M` at `:200-203` being "the
field's own reactance seen from the terminals". That is a state-space step in shape:
auxiliary state (capacitor voltage, `:256-258`), a source term from the field, one exact
solve, no iteration (`:299-300`). A frequency-dependent `Y(s)` at four terminals has a
precedent to imitate. PLRC's per-port history array has none, and `evolve.py:114-132` is
nineteen lines. This is not an argument for state-space at a device, only that the
"PLRC vs ADE" question is about where state lives, which §5 answers.

## 5. Discrete energy balance

The tree holds one exact discrete energy identity: `terminations.py:214-216`, `dU_field +
dU_L + dU_C + (dt/4) R s^2 = 0` with `s = i^{n+1} + i^n`, exact because the step is one
solve (`:209-212`: "No Newton iteration ... one solve is exact"). It is also local: one
branch, one port, one field region.

**INFERRED-FROM-THEORY**, and marked as such because nothing in the tree tests it: for a
device whose admittance is rational and positive-real, the same trapezoidal step should
give `dU_field + dU_state + (dt/4) x^T D x = 0` — residual-free, in the shape of `:214-216`,
with `D` assembled from the residue matrices — and the identity should hold to machine
precision iff the immittance is positive-real. Positive-semidefinite residues are what is
supposed to buy that.

The demonstration that would settle it, stated so that it can be run and can fail: fit a
known-passive analytic 2-port (a lossy line, or an RC ladder whose `Y` is known in closed
form), step it in the coupled loop, check the identity to machine precision over a long
run; then flip one pole's real part across the axis and show the identity fails. If the
first passes and the second fails, the link between pole passivity and the discrete
identity is demonstrated. Until that experiment exists, the link is an assertion.

This repository does not accept that class of claim: the open passivity item must not be
"recorded as resolved, fixed or explained away"
(`docs/design/passivity-resolution-2026-11-09.md:13`, `:146`), and its number 1.344803
(`:7`) is still unresolved. A block arriving with a stability argument and no identity
would open a second such item.

## 6. Pole and residue passivity constraints

A rational admittance is physical only if it is passive, and passivity constrains the fit
term by term:

- poles strictly in the open left half-plane — a right-half-plane pole is a growing
  exponential, i.e. a device that manufactures energy;
- complex poles in conjugate pairs with real coefficients, so the time step stays real;
- residue matrices positive semidefinite at each pole — the frequency-domain condition
  behind `Re Y(jω) ≥ 0`, which is the passivity statement itself;
- the DC and infinite-frequency limits of the chosen form finite and physical, since a
  series inductance is not a short at infinite frequency unless the form says so.

Vector fitting as usually practised is unconstrained least squares, and nothing in that
objective forbids a right-half-plane pole; the standard repair is a stabilisation pass
that flips the offending real part and refits residues — a separate step with its own
failure modes, capable of spoiling the fit it was meant to preserve.

`Y` of a 2-port is symmetric only for a reciprocal device. The residue conditions above
constrain residues to be PSD; they make `Y` symmetric only under a reciprocity assumption
that must be declared. Without it a step written against a symmetric `Y` is answering a
different question.

The sharp point: passivity of a *fit* and passivity of an *S-parameter record* are
different assertions on different objects, measured by different code. The tree has only
the second (§7). A project that ships a fitted block adds an object no existing gate can
check — and the gate cannot see a gain pole, because a gain pole small enough to keep the
assembled solution inside 4e-9 is, by that gate, acceptable.

## 7. What the passivity gate can and cannot see

The gate exists twice, at unequal rigour.

`evidence/termination/run_build_A.py:2192` computes `power_sum = |S11|^2 + |S21|^2` and
`:2193` fails it against `1.0 + tol` with `PASSIVITY_TOL = 4.0e-9` (`:2148`), emitting
`"status": "FAIL_PASSIVITY"` (`:2195`). The tolerance is justified at `:2144-2147`:
rounding noise is ~1e-9, and "a 1% excess of |S21| raises the sum by 2e-2". The gate
refuses to guess: `:2150-2152` says a verdict "needs two published magnitudes from the SAME
record" and otherwise reports neither "passive" nor "failed"; `:2188-2189` adds "an absent
number is not evidence of passivity", implemented as a guard at `:2251` and
`NOT_ASSESSABLE` at `:2264`.

`emfit/studies.py:2117` sums the same two magnitudes with `_BIN_PASSIVITY_SLACK = 1e-6`
(`:1923-1925`), and `:2145-2150` logs "BUG: passivity exceeds 1, not clamped" — looser by
three orders of magnitude, and reporting rather than refusing. Not the same gate.

DR-43 (`defect_register.md:814-819`, FIXED-TESTED, severity HIGH) is the case history. The
violation was ~1.15 (`:817`) on a fixture passive by construction. The cause was not
physics but *which estimator* produced `S21`: `:822` lists three branches — cut-plane
(`:4109-4120`, token `:4119`), ratio-of-ratios (`:4121-4136`), and span-end-in-load
(`:4137-4153`) which `:822` says outright is "not an S21". The six-solve table (`:824-833`)
pins it: `2400 pulse none` gives `1.151030784` FAIL while `2400 cw plane 51` gives
`0.686382016` ok, and `:838` notes "Row 2 is CW and reproduces the violation to 99.7% of
row 1's" — same geometry (`:840`: 9.6 mm span, 10.4-20.0 mm, 50 ohm series_r at 20.0 mm,
cut 20.4 mm, cut_plane @20.400 mm), two estimators. The fix commit `a69ed43` has subject
"correct S21 extraction path (cut-plane for CW, unmeasured for pulse)"; step-size stability
at `:837` (4e-9 across 2x steps).

So the gate sees one solved two-port record with both magnitudes present.
It cannot see which estimator produced each number (`:849`), a missing magnitude (it says
so, `:2264`), a gain pole inside a fitted device (§6), or artefacts predating the fix
(`:853`), and it does not cover the items at `:851` (a)-(g). It is a gate on a record, not
on a model.

A block adds a question the gate does not answer, and the geometry makes it concrete: the
load sits at 20.0 mm and the cut at 20.4 mm (`:840`), so a block attached at the cut is
measured together with 0.4 mm of line, while a block attached at the load is measured
through the de-embedding that `s21_provenance` names (`studies.py:4119`). What the gate then
grades is one of three objects — the device, the de-embedded line plus the device, or the
residual — and `:849` is exactly what makes that question askable rather than rhetorical.

## 8. Options

Per-step costs are given in operations and memory, never in seconds: nothing was run.

(a) Nothing, and declare the limitation. `ports.py:1804` writes the option line and
`:1864-1866` is the read path, so a non-behavioural model could be marked as such rather
than silently wrong. Ops: zero. Memory: zero.

(b) Zero new machinery: fit the S2P to a ladder of series/shunt R, L, C and let the
existing implicit block carry it (`step_rlc`, `:294-300`). Each element is another instance
of the shipped branch, so per step the coupled solve grows to `(n_t + M) x (n_t + M)` for
`M` elements, with `2M` scalars of state (branch current and capacitor voltage, `:256-258`).
No new kind of step and no fitting step, testable today against the existing gate. Fidelity
is limited by how well an affordable-order ladder matches the device; a poor fit is
indistinguishable from a wrong device unless the fit residual is recorded, which makes this
the cheapest option to falsify and the one needing a residual field most.

(c) State-space / ADE. One auxiliary state per pole per terminal. Per step: `n_poles x n_t`
scalars of state and a coupled solve that stays `n_t x n_t` for a linear device — the solve
does not grow with pole count, which is the whole point of the form. Generalises the 1-port
block at `:198` to four terminals with no iteration. Costs a fitting step and a
pole-stability pass (§6).

(d) PLRC / recursive convolution on port history arrays. Per step: one recursion over a
buffer of `n_t x K` scalars, `K` the kernel length in steps (memory depth divided by `dt`);
no extra solve. Couples to `dt` in a way `cfl_dt` (`emfit/evolve.py:69`, applied `:193`)
does not know about, and has no local identity to borrow (§5).

(e) Fit first, then choose between (c) and (d). Costs an input artefact plus a fitting step
with a pole-stability pass — both absent (§3).

The ordering is by falsifiability, not preference: (a) cannot fail, (b) can fail today
against the existing gate, and (c)/(d) cannot be judged until (e) exists.

## 9. Open questions

Q1. Where does the first S2P come from — an external instrument, a vendor part, or this
solver's own `write_touchstone` (`ports.py:1801`)? The last is circular, fitting a block to
an extraction that §7 grades. Consequence: which of §8's options is testable first.

Q2. Real-device fidelity, or a canonical analytic passive 2-port (lossy line, RC ladder)
sufficient to exercise the gate? Consequence: whether the first artefact is a measurement
or a fixture, and whether "passive by construction" — DR-43's own phrase for its fixture
(`defect_register.md:817`) — is available at all.

Q3. Gradability under BOTH excitations. DR-43's lesson is that a CW run reproduced 99.7% of
a pulse run's violation (`:838`) while the branches were not interchangeable: only the cut
branch names a plane (`studies.py:4119`), and the span ratio gives `1.021737` against the
cut plane's `0.761705` on one geometry (`:4146`). A block's admittance is
frequency-domain by nature, so the pulse case may be the harder one. Consequence: state the
acceptance test for both excitations or accept grading on the easy one.

Q4. May per-step cost grow at all, given the pending C++ port of the loop? The stencil's
virtue is cheap per-step work (`evolve.py:114-132`) and the C++ kernel carries no
convolution state (`cpp-kernel-spec-2026-11-09.md:139`). Consequence: (c) and (d) get
different answers if the port must mirror this loop exactly.

Q5. Does the block need its own provenance token before it may be graded? By analogy with
`s21_provenance` (`studies.py:1693-1698`): source file, S-vs-Y, `z0`, port order, frequency
grid, fit order, fit residual. `ports.py:1859` returns `s[f, out, in]`, so port order is the
field whose absence produces a wrong answer that looks right. Consequence: if yes, `None`
must mean "may not be published", as at `:4047-4048`.

Q6. Is the device assumed reciprocal (symmetric `Y`)? If not, are §6's residue conditions
sufficient? Consequence: whether a symmetric block is the special case or the general one.

Q7. Where is the block attached — at the port (span 10.4-20.0 mm, load at 20.0 mm) or at the
cut (20.4 mm), `defect_register.md:840`? Consequence: which of §7's three objects the gate
grades.

Q8. Does the passivity gate gain model-level reach, or is a second gate wanted for the fit?
`:849` puts records in scope; §6 puts models out of reach.

## 10. What would have to be true before code

(i) a named device, or a canonical analytic one, with a provenance record (Q1, Q5); (ii) a
decision that one of §8's options is taken, the others recorded as rejected and why; (iii)
for (b) a recorded fit residual, for (c)/(d) a fitting step with a pole-stability pass (§6)
and stated tolerances; (iv) the identity experiment of §5, or an explicit statement that
the discrete energy claim is unmade; (v) an answer to Q3, the acceptance test for both
excitations; (vi) a stated per-step budget in operations and memory, never wall-clock (Q4).
Absent (i) or (vi) the rest is speculative; absent (iv) the result is unfalsifiable.

## 11. Non-claims

It does not claim a behavioural block is needed. It does not claim any method is cheap in
wall-clock terms: §8 gives operations and memory and no timings, because nothing was run. It
does not claim pole passivity survives discretisation — §5 is marked INFERRED-FROM-THEORY
and says what would settle it. It does not resolve `passivity-resolution-2026-11-09.md:7`,
`:13`, `:146`. It does not claim DR-43 is closed by the gate: the gate is the mechanism, and
`:853` still lists pre-fix artefacts. It cites no external source. It reads
`cpp-kernel-status-2026-11-09.md:10-13` as OPERATOR-REPORTED and unverified here, and
`cpp_solver_arch.md:7,21` / `cpp_full_loop_plan.md:3-4,629` as design documents, not as
working code. `pairing_rule_preregistration.md:9-18` and `:1347-1348` ("The pairing rule is still
not frozen") govern cross-mesh mode pairing, not S-parameters; the rule relied on here is
`defect_register.md:849`.
