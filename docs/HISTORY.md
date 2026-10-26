# A history of `emfit`

How the machine we are building got to where it is: the order the pieces arrived in,
the measurement that forced each turn, and — the part histories usually leave out —
the numbers that were believed for a while and then withdrawn.

This is not the manual (that is `README.md`), not the current state (that is
`docs/OUTLINE.md`), not the plan (`docs/roadmap.md`), and not the full argument
(that is `decisions.md`, which is 6 772 lines long and growing). It is the narrative
those four files imply when you read them together, for someone meeting the project
for the first time.

Every claim below is one command away from its evidence. Commit subjects are quoted
where they carry the story; `decisions.md` section numbers are given where the
argument lives there; every number is quoted with the test or the run that pins it.

On dates: the record was written fast. The file dates and the timestamps inside
`decisions.md` put the whole span at roughly a week, 2026-10-19 to 2026-10-26, with
the bulk of the analysis in the last three days of it. That is worth knowing up
front, because the density of the record is not the density of a leisurely project.

---

## The short version

A time-domain electromagnetic solver was built core-first: topology, then an energy
invariant, then an eigensolver used as a ruler to measure the discretisation, then
absorbers, then scattering. Once it could scatter, it needed something to scatter
*from*, so it learned to read a KiCad board. Reading a board turned out to be much
easier than simulating one, so the project stopped trying to import and started
building a coupon board it could afford to mesh and could actually measure. That
required ports, and ports turned out to be the hard part — the place where the
project has spent most of its life since, and where it learned to write a test down
*before* running it, and to retract its own published numbers when the test said so.

The five turns that matter:

| # | Turn | What forced it |
|---|------|----------------|
| 1 | Topology first, energy before results | The energy invariant is exact or it is not; an integrator whose drift you have not measured cannot be trusted to measure anything else. |
| 2 | The eigensolver as a *ruler*, not a product | A cavity has a closed-form spectrum, so it can grade the discretisation: 1.213 % coarse, 0.615 % fine, ratio 0.507 against the theoretical 0.510. |
| 3 | From importing a board to building one | The real board (CMEX) is 549 319 edges and ~14 000 steps: unaffordable, and at 1 mm its pours are eight solid plates. Importing was not the same problem as simulating. |
| 4 | From features to audit | An 8 % passivity excess on a microstrip that survived eleven explanations. The project has not gone back to adding features at the old rate since. |
| 5 | Pre-registration and the negative register | With the easy explanations gone, the only way to keep the record honest was to write the falsifier before the run, and to keep a list of the dead ends. |

---

## 1. Before the first commit: a plan with acceptance tests in it

The first thing in the repository is not code. `8d87840 packaging, README and the
M0-M6 roadmap` lands the packaging, the README and a roadmap that defines six
milestones — and, in its own opening paragraph, the rule the whole project has been
run by since:

> A milestone is **done** only when it ships a runnable demo *and* a test that locks
> a physical number (reference value + explicit tolerance), so a regression turns red
> instead of becoming an opinion.

Two consequences of that one sentence shaped everything after it. First, every
milestone had to nominate its reference *value* in advance: the analytic box
spectrum, the Mie series, the Hammerstad-Jensen impedance, `1.000` for a matched
line. Second — and this is the part that turned out to be the interesting one — a
milestone whose reference cannot be reached with the machinery that exists is not
"nearly done". It is blocked, and saying so is the deliverable. M1 and M2 both ended
up in exactly that position, and both were recorded that way rather than rounded up.

## 2. Day one: topology, and the instrument that measures the solver

`c152462 M0: FIT cell complex, Hodge material matrices, exact leapfrog`.

The foundation is a deliberate split. Maxwell's equations are written on interlocked
cell complexes with the incidence operators `G`, `C`, `S` holding only `-1, 0, +1` —
pure topology, no geometry — and all the metric pushed into the diagonal Hodge stars
`M_eps`, `M_mu`. The payoff is a solver where a uniform grid and a graded grid run
*identical* algebra, and it is asserted rather than assumed:
`tests/test_operators.py::test_operators_are_metric_free`.

Then the leapfrog update, and one number that had to be exact: the discrete energy
`U = ½ e·M_eps·e + ½ h·M_mu·h − (dt/2)(Ce)·h`. Relative drift `8.5e-16` over 1 800
steps. The invariant is fragile in a specific, instructive way — drop the `(dt/2)(Ce)·h`
term and the drift becomes `3.7e-1`; use the wrong time level for `h` and it becomes
`3.4e-1` — which is why the test exists rather than a comment.

The CFL bound was then found to be *sharp*, not merely satisfied: stable at 1.01×
the bound, divergent at 1.02× with growth to `6.7e122`.

With an integrator that conserves energy, the next question is whether it solves the
right equations, and the answer was not "look at a field plot" but "grade it against
a box". `6cabcfa resonances: dense FIT eigenproblem + validated PEC-cavity spectrum`
built the dense pencil `Cᵀ M_mu⁻¹ C e = ω² M_eps e` on the free edges and compared
six modes of a 1.0 × 0.7 × 0.5 m cavity against the analytic spectrum: mean error
1.213 % on a 10×7×5 grid, 0.615 % on 14×10×7, every mode below the analytic value,
and an error ratio of **0.507** against the theoretical `1/1.4² = 0.510`. That ratio
is the point. It is not a number the solver produces; it is the *order* of the
discretisation, measured, and it is what makes the 1.213 % mean something other than
"close enough". Spurious modes — 216 and 702 of them, the gradient null space the PEC
constraint does not remove — are filtered by a static eigenvalue cut, and the count is
pinned in the test.

M0 closed at 71 tests in 10–20 s. It closed with two instruments in the box, not one:
an integrator and a ruler.

## 3. Absorbers: Mur, then a matched layer with no split fields

`cfc53f3 abc: first-order Mur absorbing boundary` — a cheap edge-history update on
the boundary's tangential edges. No new unknowns, no change to `C`. Measured on a
2-D PEC duct: `-49.58 dB` of reflection, against `-49.24 dB` of discrete-dispersion
theory. That agreement is the honest reading of Mur here — the boundary is sitting on
the *dispersion floor* of the grid, so the number measures the grid, not the boundary.

Then `a57d47d pml: a matched lossy layer, as the absorbing boundary`, and a design
choice that is still the most economical thing in the codebase: the layer is a matched
lossy medium — electric conductivity with a magnetic loss normalised so
`sigma_m/mu0 = sigma_e/eps0`, impedance-matched to vacuum at every depth — implemented
as a **per-step multiplicative damping on the tangential fields**, so there are no
split fields, no stretched coordinates, no tensorial material, no new unknowns.
`-79.09 dB` at normal incidence against Mur's `-49.58`.

Two things were learned about it that are worth more than the number. The reflection
follows a *wavelength* law, not a cell count: about one wavelength of layer gives
`-52 dB`, about two gives `-79 dB`, and 20 versus 40 cells per wavelength at the same
physical thickness agree to `0.6 dB`. And it saturates: beyond roughly `1.5 Np` per
cell the reflection stalls near `-45 dB`, so past that point adding cells buys nothing
and the *grading* is the limit. `7f69291 pml tests, and the layer thickness as a
wavelength law` locked that in.

What was not achieved is on the record too. M1's acceptance test asked for a PEC
**sphere** at ka = 1 and ka = 3 to better than 0.5 dB. What exists is a PEC
**cylinder** in 2-D TM at ka = 3 only, at 1.83 dB rms and 3.20 dB worst case against
Mie. The roadmap keeps the original criterion and adds, underneath it, the sentence
that describes the project's whole working style: *the criteria above are the plan as
originally written and are left unchanged; where they stand today is this.*

## 4. The scattering detour, and a milestone that could not be reached

`20c274c` (PEC cylinder), `2fdd966` (near-to-far-field transform, bistatic RCS study),
`ac01c1f mie: exact 2-D Mie series for a PEC cylinder (TM_z), with its own audit`.

The Mie module is the pattern for every reference in the project since: the reference
implementation is written *inside* the project, with its own audit, so that a
disagreement is between two things you can both inspect. The cylinder then lands at
1.83 dB rms — and the tolerance is quoted with the grid it was taken on (20 cells per
wavelength, a 2.023 % area excess, 293 pinned PEC edges against 286.5), because a
staircase number without its grid is not a number.

Then the milestone stops. M2's real target was a half-wave dipole: 73 ohm, 2.15 dBi.
There is no feed and no port in the code, so the target is unreachable — not
numerically, geometrically. That is recorded as blocked-on-geometry, and it is the
first appearance of the theme that eventually consumes the project: **the boundary
between "the solver is wrong" and "the solver has not been asked" is drawn by ports.**

Along the way, `11f6e44 grid/operators: periodic boundaries, the torus closes on itself`
made a periodic axis a boundary option rather than a second solver — one value per seam
edge, dual widths closed, topological identities intact on a torus. Nine tests.

## 5. A front door

`cba7973 cli, studies: the solver gets a front door`, then
`1af5856 webapp: a browser front end for the study registry`.

One registry (`emfit/studies.py`), two front ends: `python -m emfit list|run <study>`
and `python -m emfit serve`. Values are validated in one place (`studies.coerce`) so
that a bad or out-of-range value is reported and nothing runs, from either front end;
the web app runs one study at a time behind a lock. Five studies — `cavity`, `modes`,
`duct`, `scatter`, `rcs` — and eight figures into `docs/figures/`.

The front end exists because a solver you cannot ask a question of does not get used,
and because a study that is awkward to run is a study whose numbers do not get
re-checked. It also explains why the port later defaulted away from 8000: it is a
single-user convenience that should start, not negotiate (`0b9747b serve: bind 8010,
not the port everything else wants`).

## 6. The pivot: importing a board is not simulating one

M4 was "PCB import from KiCad", and it arrived in a rush of small, well-separated
steps: `fbdb7f0` read the board into a geometry, `867669d` rasterise it to a structured
grid with copper as thin sheets, `5e52519` rasterise tracks, zones and via barrels onto
the PEC edge mask, `5e0dcc5` a closed-form microstrip oracle to judge a numerical line
against.

Then the numbers arrived. The reference board in the tree — CMEX, a real KiCad PCB —
rasterises to 174 720 cells, 549 319 edges, ~14 331 steps at the cell size its copper
needs. And at 1 mm, its pours cover the board to within a cell, so it is eight solid
plates. CMEX is a *parser's fixture*, not a simulation target. The architecture note is
explicit that the board is reference-only and that the owner can supply a real board
when the workflow needs one.

So the project changed target: instead of importing a board large enough to be
interesting and unaffordable to solve, **build a coupon board** — small, known,
measurable with a VNA — and let that be the thing the solver is judged against. That
decision is the single largest change of direction in the history, and it happened
because a mesh count came out wrong by three orders of magnitude.

## 7. Making a board that can be measured

Five commits, all in one arc, and each one refuses a shortcut:

- `928352e board: vendor the three footprints the coupon needs` — dependency-free and
  reproducible.
- `09059ca board: generate the 70 mm microstrip coupon as text, not by hand` — the
  board file is *generated*, so the geometry is arithmetic, not typing.
- `3d6e901 check: re-measure the written board, using a reader that shares no code with
  the writer` — the verifier reads the artifact, not the intent. Result: all 60 checks
  pass.
- `999375e fab: export the gerbers and drill for the coupon` — the thing you send to a
  fab house. F.Cu 58 draws, B.Cu 3 `G36` region fills.
- `5d7739d repo: ignore KiCad's machine-local state and the agent's scratch files`.

Around it: DRC at 0 errors and 2 benign `lib_footprint_mismatch` warnings, checked
rather than assumed. And the ruling that governs all board work since, `ffbb4a4`:
**KiCad is the model and Gerber is the ground truth.** The gerber reader
(`8e14dd5 gerber: read RS-274X, and check the coupon's plotted copper against its board`)
exists so the thing that is actually manufactured can be compared against the thing
that was designed, in the same way the Mie series exists so the scattering run can be
compared against something that shares no code with it.

The rest of this thread is a sequence of small refusals to be convenient: a copper arc
is refused *by name* instead of silently dropped (`ec88551`); the outline crop is the
caller's gesture and the division is separate arithmetic (`2b785a7`); a pad can be
placed on the board and the **placement** is checked against the plot (`531c56c`) —
checked geometrically, be clear about that, because nothing electrical had been
measured at that point.

## 8. Ports: learning to launch a wave

With a board that could be meshed, the next blocker was the one M2 had already named.
The sequence is the clearest example in the project of *earn the instrument on a case
where the answer is known*:

1. `4b2e6b4` — two-probe wave decomposition, replacing a resistive lumped load. The
   load was a boundary condition, not a measurement; the two-probe split gives forward
   and backward amplitudes directly.
2. `828378a ports: prove the wave port on a parallel plate, where the answer is exact`
   — before pointing it at a microstrip, point it at a geometry with a closed form.
3. `b89da3e pml: choose which walls absorb; ports: measure the plate current` — the
   boundary condition becomes a per-problem decision, so a microstrip cannot
   accidentally get an *absorbing* ground plane. This is a class of bug that produces
   plausible numbers.
4. `7e6f2a0 ports: fit the propagation constant to every station, not to two of them`,
   then `bef387b Measure the line impedance from a station fit, with beta's uncertainty
   carried through`, then `d730884 Cross-check the station impedance against the power
   flow, and define S11 and S21 with their planes`.

Alongside: `74e9327 quasistatic: solve the cross-section, which is the oracle the wave
extraction needs`, `144e8e1`/`18784d6` a dual-face interface average that makes a
node-aligned material interface well defined, and `5ea83c5` throwing away a hand-built
edge array in favour of the dual rule.

And then, `9884668 Add the decision log, the architecture document, and stop printing
the modulus as Z0`. Three things in one commit, and the third one is the culture
changing. The decision log appears at the moment the project acquires more claims than
it can hold in its head; `decisions.md` is now 6 772 lines, and its own preface says
why:

> Every major choice in this project is recorded here together with the argument that
> was rejected, so that a later reader can tell a considered choice from an accident.

## 9. The audit era: eight per cent that would not go away

The microstrip measurement came out early and clean-looking: `Z0 = 93.39 ohm` against
a Hammerstad-Jensen analytic `89.03`, a 4.9 % excess. The project's response was to
build a discriminator rather than a story: wave-extracted `Z0` against a static solve
on the *same* geometry — agree means lateral truncation, disagree means the probe. The
lateral clearance sweep went 3.0h → 9.0h giving 51.4886 → 49.0101 ohm, and the vertical
dimension was proved irrelevant (flat to 0.01 ohm on the top wall). The acceptance
criterion was then *split*, deliberately: `Z0` within 5 % of Hammerstad-Jensen **at a
stated box**, locked as a test; 2 % only as a report-level claim from the 1/clearance
extrapolation, and that claim must quote its fit residual and its range or be called a
coincidence. As the architecture note puts it: *a test that cannot pass on the
affordable box is a bad test.*

What came next is the longest-running episode in the record: a passivity excess of
about 8 % on the board that refused every explanation offered for it. The sequence of
refutations, in the order the runs happened:

- `fb6a31e`/`711777a` — the passivity bound was made a **two-sided** test, i.e. one that
  can fail from either side, and it **failed the run**. A one-sided bound that only
  catches loss is a bound that cannot see gain.
- `a23daf0 docs: the passivity column is an amplitude ratio, and the flat-vs-rise
  reading is withdrawn` — the column was not what it said it was.
- `8f8e77f studies: the broadband sweep read the window, and the window was the fault`
  and `020b935 docs: a window is a hypothesis about its input, and one span buys 2.5:1` —
  the frequency window, not the physics, was producing the flatness.
- `4364fab docs: the lid moved, most of the sink left with it, and the numbers still do
  not quote` — the absorbing boundary was doing more of the attenuation than the copper.
- `6c5fadb Absorbed-work audit: attenuation is lateral PML leakage, not copper` — an
  actual audit of where the energy went.
- `6119f34` Im(z_c) refuted; `14199ee` the standing-wave reading of the excess **dead**;
  `ba816ea` a **CW twin** reproduces the growth at 7.8333 GHz and does not reproduce it
  at 3.6667 GHz; `cd8f578` halving the time step moves alpha by `-0.030 %`, so it is not
  a time-discretisation error.
- `807a566 docs: section 68 — the board's 8.5 pc excess is estimator-side, not field` —
  the Poynting flux falls along the line (`-3.07 %`) while the circuit quantity rises
  (`+8.47 %`). The field is fine; the way the number is computed is not.

That last one is the shape of the whole era. The project had built an instrument
(`ab948ba poynting: opt-in station flux diagnostic`), then measured the instrument's own
bias on a matched fixture (6.26 % peak-to-peak at a 0.800 mm cell, 6.31 % at 0.400 mm,
ratio 1.0044 — mesh-independent, and of *opposite sign* to the board's growth), and
only then read the board with it. The carry-forward number is deliberately small: an
interim `|S21|_poynting = 0.984519` (−0.1355 dB over 9.6 mm, 0.0141 dB/mm, 1.22× the
audited lateral leak rate of 0.01160 dB/mm), quotable **as a flux diagnostic only**.
No beta, no epsilon_eff, no Z0, no S11, no passivity statement. And a standing rule that
is still in force: *no S-parameter measured on an imported board is quotable.*

The figure then moved once more, to `0.987038` at a longer warm-up, with the 0.26
percentage-point difference recorded as warm-up sensitivity and the old number annotated
`[Superseded …]` in place rather than deleted.

## 10. Pre-registration: writing the test before the run

The distinctive habit that grew out of the audit era has a name in the record:
**pre-registration**. A section is written *before* the run, stating what will be
measured, what each possible outcome will mean, and which branch fires on which result.
Then the run happens and the section is closed with a status block.

Examples, all from commit subjects: `68200a3 docs: pre-register the Poynting
discriminator before any flux number exists`; `32d646d decisions §90 and §91: nine
eliminations recorded, and W1/W2 pre-registered before either runs`; `d4d79c5 decisions:
pre-register experiment B and the +/-2 mm port-position test`; `d20946e decisions:
port-position test pre-registered — four port planes, frozen, nothing run`;
`462c255 ... TOLFLUX pre-registered not run`; `b2a72b7 decisions.md: 99.8 amendment,
99.3 is not a discriminator; 99.9 pre-registered`.

Pre-registration is only worth anything if the negative branch actually fires and is
then believed. It does, repeatedly — `2bc3fdb decisions: the repeat ran — the tolerance
is exactly zero, and zero is not a tolerance`; `9a6d9a1 decisions §88: 0.4997 recorded as
a failure, the list of dead ends`; `fe79985 decisions §89: both surviving candidates are
dead — the air gap by measurement, the reference plane by algebra`;
`942a250 decisions §92: W1 is unevaluable by construction, W2 fails on the third
sub-check, and the reference is sound`.

The same discipline is applied to the *other* voices in the record. The log counts
errors made by the supervising side as carefully as by the implementer — `4b1992f docs:
record the tenth supervising-side error and the corrected mesh ladder`, `168227d
decisions: supervisor's six claims withdrawn, and the ordered window perturbation cannot
launch`, `173263a ... record the supervisor's two withdrawn rulings`, `04f2842 decisions:
the dispatcher's retraction of the "two readings" framing`. Nothing here is a
personality contest; it is a project that decided an error is only expensive when it is
unattributed.

## 11. The wall: memory, cost, and the modal port (M3)

The modal port — a port that projects the line fields onto a mode, so that a number can
become an S-parameter — has been the frontier for most of the second half of the
history, and it has been a *engineering* frontier as much as a physics one.

First the wall was the machine. The production mesh (`322 × 200 × 76` at 0.1 mm) exhausts
the container's memory and dies with exit 137, so the big solves moved to the host and a
harness had to be pinned and provenance-recorded (`8518f72 decisions: git is absent from
the image so landing is an operator action`, `tools/host/m3a-smoke/`). Then the memory
model itself was measured and found **low by 24.34 B/cell**, which meant the planned
configuration (C5) **does not fit** on the hardware at all (`ae196fb`), and the wall came
out at **1.47× the anchor** (`93353c7`). The project's response to that was not to buy a
machine but to pre-register a lever and to state the *price* of the wall rather than
infer it — `03e16ea` "the wall price is deferred, not measured", `65e14e7` "the gate
runs, the bits are identical, and the wall ratio is not a price". Cost became a stated
input rather than a surprise: `49bca14 nsteps: the 4000 ceiling becomes a stated cost, so
a 0.1 mm cell is askable`.

One genuinely free win in this stretch: `f065d26 operators: make curl_dual() a zero-copy
transpose of the primal curl` — the dual curl had been a separate assembly when it is,
topologically, the transpose of the primal one.

Then the physics wall, in a long accumulation of eliminations: the short-box trap
(`b6438eb`: gate-friendly epsilon_eff and beta from a shortened x are artefacts because
a reflected wave both routes ignore), the ladder run (`550f720`: |Z0| converges at first
order, epsilon_eff does not move at all, and the product's near-pass is a *cancellation*),
dispersion closures (`8c38c35`), the array audit that confirmed the solver is solving
the intended cross-section (`78f142c`: h_eff 1.600000 mm, w_eff 3.200000 mm, **0 node
differences**), the finding that 3.542 is the FDTD epsilon_V and *not* the Laplace value
(`1bf2ac6`, correcting §95.6), and the port-position dependence, which at one point put a
**10.65 % port systematic** into epsilon_V — and which was later **withdrawn**
(`cb0a2fa` recorded it, `c35d8db` withdrew it, `92bb7ee` registered port-position as a
named rival with its own pre-registration).

All of it is written up for a reader: the report grew from 30 to 68 pages
(`0ed3a91`), acquired a theory spine (transmission lines, S-parameters, Smith chart), a
glossary, a Touchstone contract, a chapter on what is exact in FIT — and then
`26630a9 report: new chapter — An open problem: an 8% passivity excess on a graded mesh`.
The project's failure is in the report, with a chapter number.

## 12. §101: the mode question in two dimensions, and a criterion retracted

The most recent phase (sections 101.14 → 101.17 and `d316ad0` at HEAD) is a careful
retreat to a simpler problem in order to answer one question: *is the microstrip mode
missing because of the formulation, the selection rule, or the assembly?*

`39d04c9 decisions.md: add §101.14 — three subsystems, the contracts they lack, five
passes; design only, authorises nothing` set the terms, in the now-standard form: a
design section that explicitly authorises no run. Then the work, in order:

- `c271109 101.15: 2D eigenmode solver -- two anchors hold, no microstrip mode found` —
  two exact anchors (the parallel plate, the slab) confirm the solver, and the microstrip
  mode does not appear.
- `91dcfc2 mode2d: add eps_eff_laplace — quasi-static capacitance-ratio cross-check` —
  an independent quasi-static reference, in the same spirit as Mie and Gerber.
- `11d3452 decisions §101.16 — Test 3 closes the strip-mode question: formulation, not
  selection or assembly` — then re-tested in corrected units (`f = 0.1 GHz`,
  `k0 = 2.095792297258034e-03` 1/mm) with 264 candidates and 12 distinct positive
  eigenvalues: maximum correlation 0.4719 against the mixed solver's 0.9902; **zero**
  candidates within ±5 % of the expected 4.071596. The conclusion survives the unit
  correction.
- `821c500 mode2d: add the mixed (e_t, e_z) mode solver — e_z inside the pencil via
  Schur complement, dense QZ, no constant-eps pollution` — and the mode appears, at
  `corr_x = 0.9902`, `eps_eff = 4.071596`, agreeing with the coarsest rung of the static
  Laplace ladder to `5.7e-07`.

And then `bde880e decisions §101.17 — mixed mode solver passes 2A and 2B, 2C
identification passes in corrected units, **power criterion retracted**`.

That retraction is the best single vignette in the project. The power-consistency
criterion asked that the power computed by a contour integral of `H_t` around the strip
match the power computed from the flux, ratio → 1. It gave ~1.11, flat in `h`, and flat
over a factor of **3 399** in `(k0 h)²` — which cannot be a discretisation error.
Rather than keep repairing the quadrature, the author computed the same functional on a
**scalar Laplace field that shares nothing with the failing path**, and got the same
11 % to `1.05e-06` relative. Then came the algebra:

```
∮ (ẑ × e_t)·dl = −∮ e_t·n̂ ds = −∫∫ div e_t dA
```

With a transverse-only field, the closed loop of `H_t` is the *charge* on the contour's
interior divided by `eps`, not a current. The true current needs the `e_z` that the Schur
complement had eliminated and that the harness filled with **zeros**. `R = 1` holds only
when there is no `eps` contrast at all — which is exactly what the homogeneous control
measured to `7.2e-14`. So the criterion was **retracted, not failed**, and the solver's
current-carrying behaviour is recorded as *still untested*. The section closes with its
own limits ("one geometry, one box, one strip width; two frequencies; not converged")
and with the cost of the attempt: the `h = 0.10` dense solve was killed at **826 s** and
2.2 GB with no output, against a three-rung static ladder that costs **1.36 s** in total
— the eigensolver is roughly 600× more expensive per useful number than the reference it
was being validated against, which is precisely why the strategy was to compare against
the reference rather than to refine the solve.

## 13. Where it stands

Read `docs/OUTLINE.md` for the current state; the honest summary is:

- **Solid:** the time-domain core and its exact energy invariant; the cavity eigensolver
  and its measured order; Mur and the matched layer; the 2-D scattering and near-field
  path with Mie beside it; the study registry behind two front ends; the board reader,
  the rasteriser and the gerber cross-check; the coupon board and its 60-check verifier.
- **Measured but not quotable:** everything on the board path that needs a mode-matched
  port. The flux diagnostic and an interim insertion loss.
- **Blocked, and known to be blocked:** the modal port (M3) — the single thing between
  the current code and a real S-parameter; the sphere/dipole acceptance bodies behind
  M1 and M2; the large-grid eigensolver (M5), where the dense path caps at 3 000 free
  edges by design and the `sigma = 0` shift-invert route is a recorded dead end; M6
  untouched.

The project is, at this moment, doing mode identification on a 6.0 × 4.0 mm box in two
dimensions because that is the smallest problem in which the question can be settled —
which is the same move as the parallel-plate wave port, the Mie series and the
no-shared-code board checker.

---

## What the record shows

Six things this history is evidence for, offered because they transfer:

1. **Build the ruler before the thing it measures.** The eigensolver was written to
   grade the discretisation, not to ship. Every later reference (Mie, Hammerstad, the
   Laplace ladder, the gerber plot) is the same idea at a smaller scale.
2. **A criterion that cannot fail is not a test.** The passivity bound became a
   two-sided test and immediately failed the run — that is the test earning its keep.
   Likewise "the tolerance is exactly zero, and zero is not a tolerance".
3. **Nothing is quotable without its provenance.** The number `0.984519` comes with its
   mesh, its record length, its warm-up, its container limits and the note that it is
   not reproducible from a clean clone. A number without that is not a result, it is a
   rumour.
4. **Cost is a measurement.** 826 s and 2.2 GB with no output, recorded as a *result*,
   is why nobody repeats it. So is 24.34 B/cell of memory error that decided a
   configuration.
5. **Try the functional on a field that shares nothing with the failing path.** The
   Laplace control settled in seconds what three rounds of quadrature checks could not.
   It is the cheapest diagnostic in the project and it should be run first.
6. **Record the dead ends with their cost.** Nine eliminations, a negative register, a
   retraction ledger, ten supervising-side errors. That list is the most reusable
   content in the repository, because it is what tells the next person where not to
   spend a day.

If you are picking this up cold, read in this order: `docs/OUTLINE.md` (what exists),
this file (how it got here), `docs/roadmap.md` (what the milestones promised and where
they fell short), the open-problem chapter of `docs/report/` (what is currently wrong),
and only then `decisions.md` — from the section numbers referenced above, not from the
top.
