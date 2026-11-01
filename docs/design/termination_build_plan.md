# Termination build 2a -- the implementation plan for the absorbing termination (A1 / A2 / A3)

**Status.** Plan only. No code was written, no solver run was performed, no gate was re-priced, no
number was moved, `PREREG.md` is untouched. Every figure below is either read out of the tree at
the line cited, quoted from a banked record, or marked as a ruling; one number is marked
`ESTIMATE` and one `UNVERIFIED` and neither is used as if it were measured.

**Provenance tags.** `[M]` read or measured in this tree (source, grep, or the one arithmetic
probe in §5); `[L]` quoted from the decision ledger or a banked evidence record; `[R]` a ruling,
convention or bar set by the owner or by the scoping document, not a measurement;
`[UNVERIFIED]` not checkable from the tree.

**The brief was checked before this plan was written, and one of its claims does not hold.** Three
claims hold: the scoping document exists at 593 lines / 38,408 B and carries the five
disagreements (§2), the three edits A1/A2/A3 (§3, L116-156) and the seven pre-registered criteria
AC-1..AC-7 (§5, L222-275) exactly as the brief describes [M]; the two commits named in the brief
are the last two on the branch and they are the gen7 catalogue and the AC-7 pass over this same
document [M]; and the working tree is clean apart from the six untracked artefacts that §6
(L308-311) keeps uncommitted [M]. The fourth claim -- that `emfit/ports.py:3-13` is the
load-bearing "the stepper is PEC-only" constraint on where a load may sit -- is **contradicted by
the scoping document's own item D1**, which says that claim about `FITStepper` is stale and false
in the current tree (`emfit/evolve.py:92-96`). The contradiction is set out in §3 and **is
reported, not adopted**. The build still proceeds, on the constraint the scope puts in its place:
the transverse-cut rule of `decisions.md:421` plus AC-6 provenance.

This file is a correction pass over the same document: it was restructured into the eight issued
sections, A2 was given its own section, A3 now names the functions it builds on, and the
ports.py premise is reported rather than relied on.

---

## 1. Goal

Three edits, one of them compositional, and nothing else -- the scoping document's own words
(§3, L118: *"Three edits, one of them compositional. Nothing else."*) [L]. A1 in §2, A2 in §3, A3
in §4; the guard that keeps them from moving the lossless path is §5, the fences are §6, the bars
are §7, and the failure modes are §8.

It does **not** deliver: a matched source (`emfit/modalport.py:323` is a *soft source*, `:19`
needs a reflection-free time window) [M]; a new boundary condition (the PML at `emfit/pml.py` and
the Mur boundary at `emfit/abc.py:149` stay where they are) [M]; a second material matrix; or any
change to the mesh, the cell counts or the excitation. **Option B, an equivalent current
source, is not an alternative to A1** -- a matched terminator has to absorb incident energy while
a source injects it (scope L143-149) [R].

**What it costs, against the gate that is actually in force.** No run in this line of work is
larger than a run already recorded, because the load is a plane inside the existing box (scope
L329-331) [R]. Banked per-run figures [L]: cells `415072` at h = 0.4 mm and `3271744` at h = 0.2 mm;
grid `68 x 218 x 28` and `134 x 436 x 56`; step `7.626299478123987e-13` s and
`3.813149739061944e-13` s; steps `2400` and `4800`; `wall_fdtd_s` `232.00763625791296` and
`1335.5644034249708` (`evidence/h_refine/h040.json:105,124,134,148`;
`evidence/rung_c/h020.json:135,154,164,191`). Against the per-run `1400` s gate that is `0.166`
and `1.048` of the budget -- the h = 0.2 run passes with 64 s of headroom, and three of them are
`4006.7` s of **session** time, about 67 minutes, which is a scheduling cost and not a gate
comparison (ruling 2, `L510-518`) [L]. **Memory is an `ESTIMATE`, arithmetic and not
measurement**: order 10 MB per array at h = 0.4 and about 78 MB at h = 0.2, i.e. order 0.24 GB for
three arrays at h = 0.2, and no JSON in `evidence/` records a memory figure, so the estimate must
be replaced by a measured number in AC-6's record before it is quoted anywhere (scope L342-350)
[L]. **Re-runs on failure:** AC-1 to AC-5 can all fail at R1 or R2, which are in-process and cost
seconds; R3 is the only rung that spends the wall budget (scope L352-354) [R].

## 2. A1 - the load conductance on m_sigma

The function it sits beside is `_sigma_diag` at `emfit/materials.py:290-292`, whose docstring is
*"Edge-wise conductance `sigma * A~_e / L_e` [S]"* [M]. The load takes the **same** shape, for a
different reason: a non-negative conductance per primal edge, nonzero only on the edge set of the
chosen transverse plane, **added** to the conductivity-derived `(n_edges,)` vector that `m_sigma`
already accepts (`emfit/evolve.py:92-96`) [M]. `emfit/evolve.py:154-157` then turns the sum into
`loss_num` / `loss_den` without knowing which part came from conductivity and which from the load
[M]. The precedent is in the tree, in the docstring: *"Both material conductivity and a lumped
load are just a conductance between two edges."* [M]

**What stays identical.** The object handed to the stepper is still one `(n_edges,)` diagonal;
there is no second material matrix, no new solver state, and nothing else in the tree writes that
vector (risk 4, scope L381-386) [R]. Addition, not composition of two models. Shape only -- no
line count is claimed, and the scope's own estimate of size is *"One construction function, one
plane-selection parameter threaded through the study, one replacement extraction path. This is an
estimate of shape, not of effort"* (L154-156) [L].

**What could go wrong, in A1's own terms** [R]: (a) **double-counting**, if a second conductance
path is added beside this one for any reason at all -- the same work then leaves the line twice
and no number in the run will say so (risk 4, §8); (b) a conductance that is numerically fine but
sits on a plane that is **not a cut**, which is A1 succeeding and A2 failing -- the failure mode
that looks like nothing (risk 1, §8).

## 3. A2 - placement at the transverse cut

**Which cut -- both ports, or one?** The tree does not answer this in code: no call site on the
port path takes a plane index today [M], so this is a ruling and is labelled as one [R].
**Recommendation: one cut per port under test, with the load at the far / terminated port only.**
The source port keeps the existing soft source (`emfit/modalport.py:323` *"soft source"*, and
`:19` says the source "needs a reflection-free time window, not a matched load") and its two-probe
split, unchanged [M]. The wording in the ledger and the scope is singular, which is the whole of
the documentary support for "one": scope L140-141 says *"the two-half fit goes away at the
terminated port"* [L]; `decisions.md:433` carries the same wording [L]; `decisions.md:421` says
*"a cut is the only place an element can sit without the solver inventing a boundary condition"*
[L]; and `decisions.md:62` records that the far end is an absorber [L]. A second load at the
source port is not forbidden by anything measured, and nothing in this plan asks for one.

**The ports.py passage, quoted verbatim (`emfit/ports.py:3-11`)** [M]:

```
Why two probes and not a lumped load
------------------------------------
The obvious way to terminate a gap port is a series resistor: measure the
voltage across the gap, divide by ``R``, and call that the port current.  That
needs a *resistive* termination on a mesh edge, and
:class:`emfit.evolve.FITStepper` only knows how to pin PEC constraints -- there
is no resistive edge in the discrete model to divide by.  Faking one would put
a number in the code that no part of the solver enforces, and every S-parameter
built on it would be wrong in a way no test could catch.
```

Line 12 is blank and line 13 begins "So this module does not terminate anything.  Instead it
**splits the standing wave on the line into travelling waves**", which is the module's own
statement of what it does instead [M]; the quote is cut at 11 because that is where the claim
under dispute ends. The scoping document quotes
exactly **lines 7-11** of this passage, word for word identically, at its L49-53 [L].

**The finding, stated plainly.** The brief directs this plan to cite `ports.py:3-13` as the
load-bearing constraint that a load cannot sit on a mesh edge, because the stepper is PEC-only.
That is **contradicted by the scoping document itself**: item **D1** (`absorbing_termination_scope.md`
L46-64) records that the claim is **stale and false in the current tree**, because
`emfit/evolve.py:92-96` accepts an `m_sigma` conductance and `:154-157` uses it -- which is the
entire mechanism A1 relies on. The false part is specifically the sentence about `FITStepper`; the
part about `ports.py` itself is true, and the module says so at `ports.py:39`: *"Nothing here
touches the stepper."* [M]. `ports.py` is 1918 lines / 83,854 B with 34 top-level `def`/`class`
and **zero writes into any solver state** -- the only mutations in the file are at `:1177`,
`:1528-1532`, `:1908` and `:1917`, all inside its own probe bookkeeping [M/L]. So the brief's
premise is reported here rather than papered over, and the paragraph above is quoted because it
is the passage the brief named, not because it is the constraint. **The real constraint on where a
load may sit is the cut rule (`decisions.md:421`) plus AC-6 provenance** -- the extraction plane
and the load plane must be the same variable -- not a PEC-only stepper.

## 4. A3 - S-parameter extraction from the same plane

A3 is a **replacement** of the two-half fit, not a repair of it: `decisions.md:433` -- *"The fix
is to replace the two-half fit with a single plane at the cut, not to repair the halves."* [L]

**The nearest existing function is named, and it already exists in the package** [M]. Both of
these are in `emfit/studies.py`:

- `def line_s21(a1, x1, a2, x2, beta) -> tuple[complex, complex]:` at `emfit/studies.py:1242` --
  docstring *"``|S21|`` between two planes from the forward amplitudes on them"*; inputs are the
  forward amplitudes of two fits already shifted onto their own planes `x1` / `x2`, plus the phase
  constant `beta`; output is a complex pair. This is the S21-from-two-planes algebra A3 needs,
  written once.
- `def forward_wave_amplitude(v, i, x, gamma, zc, indices=None) -> np.ndarray:` at
  `emfit/studies.py:1296` -- docstring *"The wave travelling towards ``+x``, de-embedded to
  ``x = 0``"*; inputs are gap voltage `v` [V], trace current `i` [A], position `x` [m],
  propagation constant `gamma` [1/m], characteristic impedance `zc` [ohm] and optional `indices`;
  output is an array. This is the forward-amplitude construction that feeds the function above.

So the question A3 has to answer is **which plane those functions are handed**, not whether the
algebra exists. The port-side primitives are already there too, in `emfit/ports.py`'s `__all__`:
`travelling_waves`, `reflection`, `transmission`, `suggest_probe_spacing` -- its module docstring
states S11 as `v_minus / v_plus` at the probe-1 reference plane via `reflection()`, S21 from the
forward amplitudes at the two ports de-embedded by the known phase via `transmission()`, and that
`travelling_waves` refuses the half-wavelength-degenerate case instead of returning noise [M].

**Input, output, and the bar that already exists.** The current approach's record is `|S11|`
`3.618e-4` and `|S21|` `1.000000583` at `tests/test_port_parallel_plate.py:277` [L]. A3 does not get
to pick a new bar: AC-3 (`L235`) is `|S11| <= 1.0e-3` **and** `| |S21| - 1 | <= 1.0e-3`, which is
2.8x the recorded floor, and ruling 1 (scope `L498`) requires the **achieved** value to be reported
beside pass/fail so that a result sitting on the floor is visibly different from one just inside
the bar [R].

## 5. The guard: how AC-1 is checked

AC-1 (`L222`) is the only silent failure mode in the change, and it turns on two facts that this
plan checked directly rather than inferring.

**Pre-change behaviour, measured.** The constructor guards on `np.any(ms)` (`emfit/evolve.py:152`),
so an **all-zero** vector is already dropped to `None`-equivalent and the lossless branch at
`:197-198` is taken [M]. Reproduced as arithmetic, five lines against the logic at `:143-157` and
`:197-200`, with `n = 4`, `dt = 1e-12`, `m_eps = 1.558e-14` [M]:

| argument | `loss_den is None` | `m_sigma` stored | `e_out` from the same `e0`, `ce` |
|---|---|---|---|
| `m_sigma=None` | `True` | `None` | `[0.12573022, -0.13210486, 0.64042265, 0.10490012]` |
| `m_sigma=np.zeros(4)` | `True` | `None` | `[0.12573022, -0.13210486, 0.64042265, 0.10490012]` |

`np.array_equal` on the two outputs is `True`, `max|diff| = 0.0` [M]; numpy 2.5.4 [M]. The probe is
arithmetic on the branch, not a solve: it reproduces the guard and the update expression and
nothing else, and it does **not** stand in for AC-1's real requirement, which is that every number
in the existing evidence set be unchanged **to the last stored digit** (L224-225) [R].

**Post-change check, stated explicitly.** After A1 lands, the **same probe is re-run** and the two
rows above are expected **identical** -- same `loss_den is None` values, same stored `m_sigma`,
same `e_out`, `np.array_equal` `True`, `max|diff| = 0.0`. A divergence on either row means exactly
one of two things: the guard at `evolve.py:152` was bypassed, or `loss_den` was built for an
all-zero vector. Either one is **AC-1 failed**: record it and stop, do not convert the probe into
a tolerance.

**Call-site census -- the AC-1 exposure, and where it actually is.** Seventeen `FITStepper`
constructions exist in the tree; **exactly three of them can pass an array at all**, the other
fourteen never mention `m_sigma` [M]:

| site | argument | branch taken today |
|---|---|---|
| `emfit/evolve.py:316` (`Leapfrog`, adapter) | `m_sigma=system.M_sigma.diag` - an array, always | lossless whenever the material conductivity is zero, because `np.any` is `False` [M] |
| `emfit/studies.py:2649-2651` | `stepper_kwargs = {} if m_sigma is None else {"m_sigma": m_sigma}`, with `m_sigma` set at `:2607` (`None`) and `:2633` (`sigma if np.any(sigma) else None`) | the **only** lossy call site in the package; already normalises an all-zero vector to `None` [M] |
| `tests/test_evolve_loads.py:147-151` | `None` omits the kwarg; the `:143` branch passes explicit zeros | both branches asserted at `:230-233` (`loss_den is None` twice, then `is not None` when armed) [M] |
| `emfit/scatter.py:367`, `emfit/studies.py:487`, `emfit/studies.py:678` | omitted | lossless [M] |
| `tests/test_d583_harness.py:72`, `test_port_parallel_plate.py:186`, `test_energy.py:56`, `:223`, `test_periodic.py:39`, `test_modalport.py:425`, `test_pml_audit.py:99`, `test_pml.py:215`, `:282`, `test_abc.py:86` | omitted | lossless [M] |

Docstring examples at `emfit/pml.py:98` and `emfit/abc.py:99` are prose, not call sites [M].
Outside `emfit/evolve.py:143-157` and `:197-204`, the only code that touches `loss_num` /
`loss_den` is `tests/test_evolve_loads.py:230-233`, which only reads them [M]; nothing assigns
them from outside the constructor, so there is no existing route that bypasses the `:152` guard
[M].

**What that means for AC-1.** Handing a zero vector to a site that used to pass `None` is **not**
an AC-1 risk, and the probe above is why: the guard drops it before any arithmetic is selected
[M]. The exposure is the other three cases, and all three are loud or fenced rather than silent:
(a) a **nonzero** conductance on a plane when no load was specified -- this is risk 3 (scope
L375-379) and it moves history while every toleranced test still passes, which is exactly why
AC-1 is exact equality rather than a tolerance [R]; (b) a wrongly shaped vector -- a `ValueError`
naming the expected edge count (`evolve.py:149-151`) [M], loud; (c) new code that assigns
`loss_num` / `loss_den` directly, bypassing the guard -- no such code exists today [M] and §6
forbids it [R]. The census therefore adds no new AC-1 hazard to the ones the scoping document
already lists.

## 6. What stays untouched

**Untouched by name:** `emfit/mode2d.py`, `emfit/pml.py` (808 lines), `emfit/abc.py` (348 lines),
the mesh and cell counts (`emfit/studies.py:2556-2559`, `emfit/grid.py:113-114`),
`emfit/board.py:566 to_cell_counts`, the excitation (`emfit/modalport.py:323`, `:19`), the
append-only ledger, `d5854a` entry `[2]`, and the six untracked artefacts (`d80_96.md`,
`d94_96.md`, `docs/design/c2b_shapes.pdf`, `docs/design/c2b_shapes.png`,
`docs/design/mispaired_metric_before.png`, `docs/report/figures/c2b_mode_shape_corrected.png`) --
scope §6, L279-311 [R].

**The write fence for this dispatch** is narrower still: this file, one row in
`docs/design/dispatch_log.md`, and the item-8 paragraph at
`docs/design/theory_round2_memo.md:13` -- that line, replaced with the owner's verbatim text, and
no other line of that file [R].

**Two stop rules, both pre-registered elsewhere and both binding here:** **a bar that fails is
recorded, not moved** (AC-2, `L231`); and **if a matched load leaves `|S11|` where it was --
unmoved at `3.618e-4`, no better -- then termination was never the extraction floor, the premise is
wrong, and the response is to record that and stop rather than to go looking for a smaller number
by another route** (falsifier of last resort, `L272-275`) [L].

**One known defect is recorded here and not repaired:** `tests/test_port_parallel_plate.py:339-340`
carries a docstring with a word missing; the 3 % it describes is real and asserted at `:358` and
`:360` (scope L540-545) [L]. It is a citation defect in a test docstring, not a behaviour of the
solver, and fixing it is outside this fence.

## 7. Acceptance criteria, one line each

Each line is a bound already pre-registered in the scoping document (§5), not a fresh ruling; the
line number is the anchor. They are graded at the three rungs, and the attribution rules say which
failure means what (scope L206-211) [L]: **R1** is `tests/test_evolve_loads.py` extended to a real
grid transverse cut, keeping that file's **existing** tolerances rather than tightening them
(`s21` 1 %, `s11` 2 %, absorbed fraction 2 %, assembled conductance `1e-12` absolute against
`diag(Sigma)`, scope L175-180) [R]; **R2** **replaces** a terminal, not adds one -- the same
geometry, source and mesh with the far PML replaced by a matched load at the cut, required to
reproduce the recorded `S11` `3.618e-4` and `|S21|` `1.000000583` within these bars, with the
oblique case at `tests/test_port_parallel_plate.py:334` still landing on Fresnel `-1/3` within the
3 % recorded at `:337-339` [L]; **R3** is the end-to-end batch -- matched, two mismatched, and the
open control that is known-bad today (`|s21| > 1`, `beta` standard error `57`, `decisions.md:433`)
[L]. Attribution: R1 failing means the conductance is wrong; R2 failing with R1 passing means the
load is in the wrong place or a second boundary condition was added beside it; R3 failing with R1
and R2 passing means the extraction is still not the same plane as the load -- the only informative
failure of the three [R]. R3 is last because it is the only rung that spends the wall budget (scope
L352-354) [R].

- **AC-1** (`L222`) - bit-for-bit losslessness: the `loss_den is None` branch at
  `emfit/evolve.py:197` is still taken and every existing number is unchanged **to the last stored
  digit** - exact equality, not a tolerance, checked by re-running the §5 probe [R].
- **AC-2** (`L231`) - no existing tolerance is widened to make anything pass: a bar that fails is
  recorded, not moved [R].
- **AC-3** (`L235`) - `|S11| <= 1.0e-3` **and** `| |S21| - 1 | <= 1.0e-3`, with the achieved
  `|S11|` printed beside pass/fail so a result sitting on the `3.618e-4` floor is visibly
  different from one just inside the bar (ruling 1, scope `L498`) [R].
- **AC-4** (`L246`) - at least 2 unmatched loads, each `|Gamma|` within 3 % of
  `|R - Zc| / (R + Zc)` -- the 3 % borrowed from the already-recorded oblique check at
  `tests/test_port_parallel_plate.py:337-339` [R].
- **AC-5** (`L251`) - no `|s21| > 1 + 1e-5`, and the open control's `beta` standard error at least
  3x smaller than the `57` on record, against a PML reference in the same batch; note that the
  `5.8e-7` this sits above is the arithmetic remainder of `1.000000583`, so the tripwire is 17x
  above a remainder and is the weaker instrument for it [R].
- **AC-6** (`L260`) - the run JSON carries load value, units, plane index **and** the index of the
  plane the S-parameters came from; it is a dictionary key rather than a reconciliation only
  because A3 makes those two indices the same variable (`decisions.md:463`) [R].
- **AC-7** (`L266`) - `beta_FDTD = -d(arg S21)/dL` from two line lengths against `beta_modal` from
  `emfit.mode_profile`, `|diff| / beta_modal <= 1.0e-3` [R].

**Falsifier of last resort** (`L272-275`) [L]: if a matched load leaves `|S11|` unmoved at
`3.618e-4` -- not improved, merely where it was -- then termination was never the extraction floor,
the premise of this build is wrong, and the response is to record that and stop, not to reach for a
smaller number by some other route.

## 8. Risks, ordered by how quietly they fail

Silent first, loud last. The ordering is the point: risks 1-4 raise nothing when they go wrong.

1. **The load is placed where a cut is not.** Silent, and the costliest: the solver absorbs the
   energy happily and every S-parameter comes out a plausible `|G|` for a different problem. There
   is no exception to catch and no test that fails, only a number that is not the number being
   asked for (scope L362-365) [L].
2. **The element is sub-cell.** A 100 Ohm load discretised on this mesh already reads `9.04 %` low
   (`decisions.md:421`), so the arm can miss for a reason that has nothing to do with the
   termination; that is why 100 Ohm is graded as **exploratory** against a band rather than against
   AC-3 (ruling 3, scope `L520`), and 25 and 50 Ohm carry the graded verdict (scope L367-373)
   [L/R].
3. **The change leaks into the lossless path.** If `loss_den` is always built, every run moves onto
   the trapezoidal branch, nothing raises, and history shifts under tests that all still pass --
   the failure is a diff in a banked number, visible only if someone re-runs the record. Mitigation
   is AC-1 as exact equality, which is why it is not a tolerance (scope L375-379) [L].
4. **A second conductance path is added "for safety".** Double-count: the same work leaves the line
   twice, and the absorbed-work audit **cannot** see it, because that audit bins the matched layer
   while the load removes work on a plane the audit never looks at (`decisions.md:463`; scope
   L381-386) [L].
5. **The seam is "repaired" by repairing the halves.** The tempting wrong fix, and the one the
   ledger names in advance: replace the two-half fit, do not repair it. If it is attempted, abandon
   rather than tune (`decisions.md:433`; scope L388-391) [L].
6. **The result is unfalsifiable.** Every reference run in the tree is PML-terminated: item D5
   (scope L94-104) records **zero** JSON for a loaded port, `port_load` matching nothing, and
   `resistive` matching only three places -- `ports.py:7`, `ports.py:9`, `studies.py:1470` [M].
   So there is nothing in `evidence/` to compare a loaded run against, and the target has to be
   the closed-form answer plus a PML reference in the same batch [R].
7. **The floor does not move.** This is premise-level, not a build defect: if a matched load leaves
   `|S11|` where it was, termination was never the extraction floor. The response is to stop and
   say so, not to search for another route to a smaller number (scope L398-403, falsifier
   `L272-275`) [L].
8. **Operational.** The quiet failures have a loud sibling: work lost to a container that did not
   persist, a temp directory that was assumed to survive, a ledger edited in place instead of
   appended, a large tracked file edited without re-hashing its prefix, or two artefacts in one
   commit so that neither can be attributed. Fresh containers, no persistent temp dir, append-only
   ledger, prefix hash after editing a large tracked file, one artefact per commit (scope L405-409)
   [R].
