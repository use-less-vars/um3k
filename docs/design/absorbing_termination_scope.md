# Absorbing termination: scoping document

**Status.** Scoping only. No code was written, no host run was performed, no solver file
was modified to produce this document. Every claim below carries a `path:line` citation or
a `decisions.md` reference; the few that cannot be carried that way are marked as estimates
in the sentence itself. Prepared for review before any implementation is scheduled.

**Why this document exists.** The owner named absorbing termination as the first lever:
*"the only lever that moves the extraction floor, and the extraction floor is what makes
S-params unquotable."* He asked for a scoping document, not a build, with six required
contents, listed as (a) to (f) below and answered in that order. Host runs are excluded by
instruction and none were made.

---

## 1. The answer in one paragraph

The termination does not need a new boundary condition, a new material matrix, or a
resistive edge bolted onto a PEC-only stepper. The conductance star a lumped load needs
already exists in the stepper: `emfit/evolve.py:83` is `class FITStepper`, `:92-96`
documents `m_sigma` as *"Diagonal of the conductance star: a non-negative conductance [S]
per primal edge. Both material conductivity and a lumped load are just a conductance
between two edges. `None` or an all-zero vector leaves the lossless update untouched, bit
for bit"*, `:154-157` computes the trapezoidal coefficients, and `:197-204` applies them.
An analytic reflection harness for exactly that path already passes
(`tests/test_evolve_loads.py`, 311 lines: `:216` bit-for-bit lossless, `:240` series
resistor, `:264` shunt capacitor). What is missing is the **port**: nothing in the
repository composes a load onto a transverse cut and extracts S-parameters from that same
plane, and no recorded run in `evidence/` is terminated in a load at all (search for
`series_r`, `shunt_c`, `port_load` across `evidence/` and `tools/` returns zero matches).
The minimal change is therefore at the port plane, not in the solver. The one piece of
real engineering is the seam: the default S-parameter path and the load share a station as
their seam, which is why the default path returns `|s21| > 1` and, on a bare open, a
`beta` with a standard error of `57` (`decisions.md:433`).

---

## 2. Five disagreements with the premise as it was put to me

The premise was that `emfit/ports.py` states a PEC-only constraint, that the termination
machinery is absent, and that the choice is between a resistive edge and an equivalent
current source. Four of those five points do not survive a reading of the tree, and the
fifth changes the shape of the answer. Each item below is anchored, and each is offered as
a correction to the premise, not to the owner: three of these costs are mine, not his.

**D1. `ports.py:7-11` is stale as a statement about the stepper.** The module docstring
says:

> `needs a *resistive* termination on a mesh edge, and`
> `:class:\`emfit.evolve.FITStepper\` only knows how to pin PEC constraints -- there`
> `is no resistive edge in the discrete model to divide by. Faking one would put`
> `a number in the code that no part of the solver enforces, and every S-parameter`
> `built on it would be wrong in a way no test could catch.`

That claim about `FITStepper` is false in the current tree (`evolve.py:92-96`, above), and
the false part is the part about the stepper. The part about `ports.py` itself is true and
is stated twelve lines later: `ports.py:39` reads *"Nothing here touches the stepper. These
are the analytic primitives of a port."* `ports.py` is 1918 lines and 83854 bytes with 34
top-level `def`/`class` and **zero writes into any solver state** - no assignment to
`m_sigma`, `m_eps`, `m_mu`, `loss_num`, `loss_den` or `pec_idx` anywhere in the file; the
only mutations are fit workspace arrays at `:1177`, `:1528-1532`, `:1908`, `:1917`. So the
docstring's scope statement is accurate and its capability statement is out of date. Which
reading holds does not matter for the decision: either way, the machinery a load needs is
in the stepper.

**D2. Absorbing boundaries are not missing.** `emfit/abc.py` is 348 lines and implements a
first-order Mur boundary (`:149 class Mur1Boundary`) with passing tests
(`tests/test_abc.py:253 test_mur_absorbs_outgoing_pulse`, `:285 test_pec_control_reflects`).
`emfit/pml.py` is 808 lines with its own test
(`tests/test_pml.py:249 test_pml_reflects_at_least_10_db_less_than_mur`). What is missing is
the port, and the record already says so in those words: `decisions.md:9344` -
*"**(ii) Termination exists; what is missing is the port.**"*

**D3. The record is more decided than the premise assumes, and in two directions.**
`decisions.md:62` is headed *"## The far end is an absorber, and every reflection number is
attributed to it"*: the strip is run into the `n_pml`-cell absorber and is deliberately not
terminated in a load. `decisions.md:120` is headed *"## The lateral PML is not the sink
either; mode-matched port deferred to gate G4"*, with the deferral *"recorded with its
reason, not as an open TODO"* (`:124`). But `decisions.md:421` is headed *"## A lumped
element at a transverse cut: the series branch passes its pre-registered test, the shunt
branch is an envelope and not a validation"*, and reports real load runs: the series branch
recovers the commanded resistance *"within `1` per cent"*, the shunt branch is *"`9.04` per
cent low"*. So a lumped load at a cut is not an open question in this repository; it is a
measured thing with a measured error bar, and the part that is missing is the *port*
composed around it.

**D4. `decisions.md:66` (no resistor anywhere) is superseded and must not be cited as
current.** It sits inside the D3 block, which describes the far-end absorber as built.
`decisions.md:421-431`, which is later, reports `series_r` runs and recovered resistances.
Only the later entry is current. This matters because a document that quotes `:66` as the
design intent would conclude the repository has decided *against* loads, when in fact the
same ledger contains load measurements five hundred sections earlier.

**D5. The gap is analytic, not architectural - and that is the uncomfortable part.** Every
measured configuration in `evidence/` is PML-terminated. There is **no recorded JSON for a
loaded or terminated port**: searching `evidence/` and `tools/` for `series_r`, `shunt_c`
and `port_load` returns nothing, and `port_load` does not appear anywhere in the repository
at all (census over `*.py`: `pml` 446, `impedance` 208, `absorb` 166, `lumped` 37,
`resistive` **3** matching lines - `ports.py:7`, `ports.py:9`, `studies.py:1470` -
`port_load` **0**; counts are matching lines per file, not raw occurrences). The three
`resistive` hits are the two stale docstring lines and one study comment. So the honest
statement is not that the code is wrong or that the code is missing; it is that a
capability which exists and passes unit tests has never been composed into a port and never
been measured on the real geometry.

**Consequence for the choice.** The owner's (f) anticipated two failure modes: a resistive
edge being non-trivial in a PEC-only stepper, and a current source needing a new material
matrix. Neither is the risk. The load is one length-`n_edges` diagonal in the same form as
the conductivity (`emfit/materials.py:290-292`, `_sigma_diag`: *"Edge-wise conductance
`sigma * A~_e / L_e` [S]"*), and there is no second matrix to write. The real risks are
listed in section 8, and the first of them is that the load gets placed somewhere a cut is
not.

---

## 3. (a) The minimal model change

Three edits, one of them compositional. Nothing else.

**A1. Build the load plane's conductance.** One construction on the materials side, in the
same form as `_sigma_diag` (`materials.py:290-292`): a non-negative conductance per primal
edge, nonzero only on the edge set of the chosen transverse plane, added to the
conductivity-derived vector that `m_sigma` already accepts (`evolve.py:92-96`). This is
addition, not a new material matrix: the object handed to the stepper is the same
`(n_edges,)` diagonal, and `evolve.py:154-157` turns it into `loss_num`/`loss_den` without
knowing whether the conductance came from a resistor or from a lossy dielectric. The
precedent that this is the right shape is not an argument, it is the docstring: *"Both
material conductivity and a lumped load are just a conductance between two edges."*

**A2. Put it at a transverse cut, not anywhere convenient.** `decisions.md:421` states the
rule: a cut is the only place an element can sit without the solver inventing a boundary
condition. This is the single most likely way to get this wrong, and the failure is silent
- see risk 1 in section 8.

**A3. Extract S-parameters from the same plane that carries the load.** This is the seam
fix and it is the substance of the change. `decisions.md:433` diagnoses the current state:
*"The default S-parameter path and the load share a station as their seam ... the default
path returns `|s21| > 1` and, on a bare open, a `beta` with a standard error of `57` ...
The fix is to replace the two-half fit with a single plane at the cut, not to repair the
halves."* A3 is therefore a replacement, not an addition: the two-half fit goes away at the
terminated port.

**Option B, the equivalent current source, is not an alternative to A1.** A matched
terminator has to absorb incident energy; a current source injects it. The repository's
source is explicitly not a terminator: `emfit/modalport.py:323` reads *"This is a **soft
source**, not a matched port terminator: the guide is"* - and `modalport.py:19` says the
class *"needs a reflection-free time window, not a matched load"*. So the excitation side
is already answered by the existing soft source, and using it as a terminator would convert
a load into a second source. **Three edits, not two models**: the load (A1), the cut (A2)
and the single-plane extraction (A3), and the current state of the repository is that A1
exists untested in situ, A2 is a stated rule with no implementation on the port path, and
A3 does not exist.

**Estimated size.** One construction function, one plane-selection parameter threaded
through the study, one replacement extraction path. This is an estimate of shape, not of
effort: no implementation was attempted, and no line count is claimed.

---

## 4. (b) The smallest experiment that can fail

Three rungs, ordered by how much of the claim each one can falsify on its own. R1 can pass
while the port does not exist - that is the present state of the repository, and the rung
is written knowing that, because it is the cheapest way to catch a load that quietly is
not a conductance. R2 is the existing integration case with its terminal replaced. R3 is
the end-to-end comparison, and it is the only rung where the extraction floor appears at
all.

### R1 - the unit rung: the load is a conductance and nothing else

`tests/test_evolve_loads.py` is 311 lines and passes today. It pins the three identities a
load has to satisfy, and it pins them against closed forms rather than against stored
numbers: at `:216` a zero-conductance plane is bit-for-bit lossless, at `:240` a series R
reproduces the analytic reflection of R against the line, at `:264` a shunt C reproduces
the analytic reflection of C. R1 is that file extended by the one case it does not cover -
the same three identities with the plane on a transverse cut of a real grid rather than on
an idealised line - and it keeps the tolerances the file already uses rather than
tightening them to make the change look better: `s21` to 1 %, `s11` to 2 %, absorbed
fraction to 2 %, and the assembled conductance to `1e-12` absolute, which is a comparison
against `diag(Sigma)` and not against any run.

### R2 - the integration rung: replace a terminal, do not add one

`tests/test_port_parallel_plate.py:270` records a measured `S11` of `3.618e-4` and, at
`:277`, `|S21| = 1.000000583` on the current path. Those two numbers are the demonstrated
floor of the existing extraction, and they are the reason this rung can be written without
inventing a target: the same geometry, the same source, the same mesh, with the far
terminal's PML replaced by a matched load at the cut. The case must then reproduce the same
two numbers to the section 5 bars, and the oblique case at `:334` must still land on the
Fresnel value `-1/3` within the 3 % already recorded at `:337-339`. R2 fails loudly if the
load is a second boundary condition wearing a resistor's clothes: the transmission case is
the one that cannot be faked by absorbing more.

### R3 - the end-to-end rung: three loads, one of them known-bad

The rung that decides the question, in the order it should be run.

1. **Matched.** `R = Zc`. Expected `|S11|` at or below the section 5 bar and `|S21|` at 1.
2. **Mismatched.** `R` chosen so `|Gamma| = |R - Zc| / (R + Zc)` is far from both 0 and 1 -
   two values, because one value can be right for the wrong reason.
3. **Open control.** The case that currently returns `|s21| > 1` and a `beta` with a
   standard error of `57` (`decisions.md:433`). It is in the batch precisely because it is
   known-bad: if the open still returns 57 and the matched load does not, the seam is in
   the extraction and not in the load, and A1 alone would not have been the fix.

Why the order matters. Each rung can pass while the next fails, and each failure names a
different culprit. R1 failing means the conductance is wrong. R2 failing with R1 passing
means the load is in the wrong place, or that a second boundary condition was added beside
it. R3 failing with R1 and R2 passing means the extraction is still not the same plane as
the load - which is the defect this document exists to remove, so it is the only failure
that is informative rather than merely negative.

---

## 5. (c) Pre-registered acceptance criteria

Written before the run and committed with the change, so that no number can choose its own
bar after the fact. Six criteria, in the order they would go wrong; AC-1 is the one that
would be violated most quietly. They are stated as bounds on evidence that does not exist
yet, which is the point of pre-registering them.

**AC-1. Bit-for-bit losslessness when no load is specified.** `evolve.py:197` branches on
`loss_den is None`. With no load on the plane, that branch must still be taken, and every
number in the existing evidence set must be unchanged to the last stored digit - not within
a tolerance, identical. This is the only silent failure mode in the whole change: if the
load machinery allocates a zero vector where the old path passed `None`, the branch is not
taken, the update at `evolve.py:197-204` runs a different arithmetic path, and existing
results move in the low digits while every toleranced test still passes. Nothing else in
the change can corrupt history without an obvious symptom; this can.

**AC-2. No widening.** No existing tolerance anywhere is loosened to accommodate the new
path. If a bar needs widening, the widening is the finding, and it is recorded as the
finding rather than applied.

**AC-3. The extraction floor moves.** On the matched load, `|S11| <= 1.0e-3` and
`| |S21| - 1 | <= 1.0e-3`. The demonstrated floor is `3.618e-4`
(`test_port_parallel_plate.py:270`); `1.0e-3` is 2.8 times it, set as a bar that a real fix
clears and a nominal one does not. It is deliberately not set at the demonstrated floor,
because matching the floor would only prove the load did not make things worse. Whether it
should be `1.0e-3` or `3.618e-4` is question 1 of section 9.

**AC-4. The load value has to matter.** For at least two unmatched loads, `|Gamma|` within
3 % of `|R - Zc| / (R + Zc)`. The 3 % is the tolerance already recorded for the Fresnel
case at `:337-339`; it is borrowed, not invented, and if it is the wrong tolerance for this
quantity then that is a legitimate objection to it rather than a reason to pick another.

**AC-5. No passivity violation, and the seam is measured rather than assumed.** No `|s21|`
above `1 + 1e-5` anywhere in the batch - the existing floor is `5.8e-7`, so the tripwire
sits 17 times above it and fires on exactly the defect recorded at `decisions.md:433`,
where the default path returns `|s21| > 1`. And the `beta` standard error on the open
control is reported against a PML-terminated reference run in the same batch: if it is not
at least 3 times smaller than the `57` on record, the seam is not fixed, whatever `S11`
says.

**AC-6. Provenance in the artefact.** The run JSON carries the load specification - value,
units, plane index - and the index of the plane the S-parameters were extracted from.
`decisions.md:463` records that the current path reports a plane the audit never looks at;
AC-6 is the criterion that makes that sentence stop being true, and it costs one
dictionary key.

**Falsifier of last resort.** A bar that fails is recorded, not moved. And if a matched
load leaves `|S11|` where it was - unmoved near `3.6e-4`, no better - then termination was
never the extraction floor, the premise of this document is wrong, and the right response
is to record that and stop rather than to go looking for a smaller number by another route.

---

## 6. (d) What stays untouched

Everything except the termination model. Specifically, and by name:

- **The mixed and transverse pencils.** `mode2d.py` is not edited. Section 161 of the
  ledger stands as written: the `beta^2 = eps_r k0^2` family is a transverse-pencil
  construction artefact, absent from the mixed pencil at both meshes, and already rejected
  at the point of use by the curl-ratio and `eps_eff` guards. Nothing in this document
  reopens it.
- **The absorbers.** `emfit/pml.py` (808 lines) and `emfit/abc.py` (348 lines,
  `Mur1Boundary` at `:149`) are not edited. The load is added *inside* the box; the PML
  stays where it is.
- **The mesh and the cell counts.** `emfit/studies.py:2556-2559`
  (`nx = n_pml + n_ref + n_line`, `ny = 2 * n_pml + n_strip + n_clean_lo + n_clean_hi`,
  `nz = n_sub + n_air + n_top`) and `emfit/grid.py:113-114` (`n_cells = nx*ny*nz`) are not
  edited. The load plane does not lengthen the box.
- **`emfit/board.py:566 to_cell_counts`.** It is a divider and a refusal - it raises when a
  geometry does not divide into integer cells or the strip misses the far wall - and it is
  the reason the far plane must *be* the wall. Not edited.
- **The excitation.** The soft source at `emfit/modalport.py:323` and its reflection-free
  window (`:19`) are not edited. If anything about the source has to change for R3, the
  change is in the wrong place.
- **The decision ledger is append-only.** Results go in as one new section after the runs,
  in the same style as every other section, and no earlier section is rewritten - including
  the stale ones named in D1 and D4, which are corrected by being superseded, as `:421`
  already supersedes `:66`.
- **`d5854a` entry[2] stays deferred.** The cross-pencil disagreement
  (`beta_dense 385.021474334043` against `beta_arpack 408.9721637956313`, `rel_diff 0.0622`,
  1691 against 1262 DOF) is not touched by this line of work and is not in this queue.
- **The six untracked artefacts stay uncommitted** (`d80_96.md`, `d94_96.md`,
  `docs/design/c2b_shapes.pdf`, `docs/design/c2b_shapes.png`,
  `docs/design/mispaired_metric_before.png`,
  `docs/report/figures/c2b_mode_shape_corrected.png`).

---

## 7. (e) Cost

All wall-clock figures below are **measured** and quoted from the evidence records; the
memory figure is marked as an estimate because no record in the tree contains one.

| Quantity | h = 0.4 | h = 0.2 | Source |
|---|---|---|---|
| Cells | 415072 | 3271744 | `evidence/h_refine/h040.json:124`, `evidence/rung_c/h020.json:154` |
| Grid | 68 x 218 x 28 | 134 x 436 x 56 | same records |
| Time step | 7.626299478123987e-13 s | 3.813149739061944e-13 s | `h040.json:105`, `h020.json:135` |
| Steps | 2400 | 4800 | `h040.json:134`, `h020.json:164` |
| FDTD wall | 232.00763625791296 s | 1335.5644034249708 s | `h040.json:148`, `h020.json:191` |
| Same box, other study | 54.35445575299673 s | - | `evidence/stations_n18.json:193` |

**Cells: zero delta.** The load is a plane inside the existing box (section 6), so no run in
this line of work is larger than a run already recorded. The cost of the change is not in
cells.

**Wall: the ladder fits at h = 0.4 and does not fit at h = 0.2.** At h = 0.4 the three R3
cases are at most 3 x 232.0 s = 696.0 s, comfortably inside the frozen 1400 s wall gate. At
h = 0.2 they are 3 x 1335.5644 s = **4006.7 s**, which is 2.86 times the gate - and even a
single h = 0.2 run sits at 1.048 of the gate, which is why only one such run at a time has
been attempted. So the h = 0.2 leg of the ladder is either one load per session or a gate
revision, and the gate is not mine to revise.

**Memory: an estimate, and labelled one.** The stepper's state is a handful of
`(n_edges,)` and `(n_cells,)` double arrays; the change adds one `(n_edges,)` diagonal, and
one or two more of the same length while the load is active (`loss_num`, `loss_den` at
`evolve.py:144-145,154-157`). With `n_edges` of order 3 x `n_cells` on an orthogonal grid,
that is order 1.25e6 doubles at h = 0.4 (about 10 MB per array) and order 9.8e6 at h = 0.2
(about 78 MB per array), i.e. order 0.24 GB for three arrays at h = 0.2. **This is
arithmetic, not measurement**: no JSON in `evidence/` records a memory figure, and the
estimate must be replaced by a measured number in AC-6's record before it is quoted
anywhere.

**Re-runs on failure.** AC-1 to AC-5 can all fail at R1 or R2, which are in-process and cost
seconds. R3 is the only rung that spends the wall budget, and R3 is the last rung for that
reason.

---

## 8. (f) What could go wrong

Ordered by how quietly it fails.

**1. The load is placed where a cut is not.** `decisions.md:421` states the rule that a cut
is the only place an element can sit without the solver inventing a boundary condition, and
the failure does not raise - it produces a plausible `|G|` belonging to a different problem.
Mitigation: A2 is a precondition of R3, not a detail of it.

**2. The element is sub-cell.** A load is exact on a transverse cut aligned with the mesh;
otherwise the geometry has a feature the audit does not model. The measured warning is
already in the ledger: the series branch recovers the commanded resistance *"within `1` per
cent"* at 25 and 50 ohm and is *"`9.04` per cent low"* at 100 ohm (`decisions.md:421`). An
impedance-dependent error of that size is indistinguishable from a `|G|` error, so the R3
ladder should live in the range where the element is validated and treat 100 ohm as a
recorded degradation point, not a test case. **This is question 3 for the owner below.**

**3. The change leaks into the lossless path.** `evolve.py:197` branches on `loss_den is
None`; a code path that always builds `loss_den` silently switches every run in the
repository onto the trapezoidal branch. Nothing raises, nothing looks different, and every
recorded number moves slightly. Mitigation: AC-1, exact equality, and it is listed first for
this reason.

**4. A second conductance path is added for safety.** Both material conductivity and a
lumped load are already the same conductance (`evolve.py:92-96`); adding a second route
would double-count the absorption, and the absorbed-work audit would not see it, because
that audit bins only the damping in the matched layer while a lumped load removes work in
the stepper *"on a plane the audit never looks at"* (`decisions.md:463`). Mitigation: A1
adds to the existing diagonal, and nothing else writes to it.

**5. The seam is repaired by repairing the halves.** `decisions.md:433` is explicit: *"The
fix is to replace the two-half fit with a single plane at the cut, not to repair the
halves."* A3 is a replacement. If a variant of this work ends up with two probes and a
correction term, it has already failed AC-5 and should be abandoned rather than tuned.

**6. The result is unfalsifiable because there is nothing to compare against.** Every
reference run in the tree is PML-terminated (D5), so the comparison target is not a previous
terminated run - it has to be the closed-form answer (R3's table) and the PML reference
under AC-5's relative rule. Mitigation: both are pre-registered above, before the code.

**7. The floor does not move.** This is the premise-level risk and it deserves its own line.
The justification for this lever is the owner's judgement, not a measurement; section 161
removed the spurious-mode candidate, so the extraction floor is still unattributed. If a
matched load leaves `|S11|` at its current value, then the terminator was not the floor,
and the correct response is to say so and stop - not to refine the load until a number
moves. AC-5's falsifier is written to catch exactly this.

**8. Operational.** Three containers, each call fresh, no persistent temp directory; the
ledger is append-only and has been truncated to zero bytes once by a temp-file redirect
(recovered, zero lost - `docs/design/session_close_gen6.md` section 6.3, entry 27). Any edit
to a large tracked file is verified by prefix hash afterwards, and results are committed one
artefact at a time.

---

## 9. What this document does not decide

It does not choose the load impedance set, the number of R3 cases beyond three, or whether
the h = 0.2 leg is run at all in the first session. It does not estimate effort. It does not
reopen section 161, `d5854a`, or the modal-solver optimisation roadmap - the coupling noted
for the theory-engineer round is only this: if termination lowers the extraction floor, the
modal solve may become the binding cost at higher mesh, which is a question about the SLEPc
and `p = 2` discussion and not about this document.

Three questions for the owner, each of which changes a number above:

1. **AC-3's bar.** Is `|S11|` at most `1.0e-3` the right bar, or should it be set at the
   demonstrated floor of 3.618e-4 (`tests/test_port_parallel_plate.py:277`)? The looser bar
   is 2.8x the floor and the tighter one risks failing on noise that already exists.
2. **The h = 0.2 leg.** One load per session, or a revision of the 1400 s gate? Three loads
   are 4006.7 s as measured, and a single run is already at 1.048 of the gate.
3. **The load range.** 25 and 50 ohm only, where the element is validated within 1 per cent,
   or include 100 ohm as a recorded degradation point at 9.04 per cent (`decisions.md:421`)?

---

## 10. References

Every citation in this document was re-read in the tree before the document was written;
the audit found no contradiction, two range drifts (`evolve.py`'s PEC zeroing is at
`:203-204`, not `:201-202`; the `decisions.md` heading for the lateral-PML deferral is at
`:120`, with `:124` being its body), and one harness not previously listed
(`tests/test_evolve_loads.py:264`, the shunt counterpart).

| Claim | Anchor |
|---|---|
| The conductance star exists | `emfit/evolve.py:83`, `:92-96`, `:144-145`, `:154-157`, `:197-204` |
| Its material form | `emfit/materials.py:290-292` |
| Analytic reflection harness | `tests/test_evolve_loads.py:216`, `:240`, `:254-257`, `:264` (311 lines) |
| Matched line and Fresnel | `tests/test_port_parallel_plate.py:270`, `:277`, `:334`, `:337-339` |
| Absorbers and their tests | `emfit/abc.py:1`, `:149` (348 lines); `emfit/pml.py` (808 lines); `tests/test_abc.py:253`, `:285`; `tests/test_pml.py:249` |
| The stale docstring and its true scope | `emfit/ports.py:7-11`, `:39` (1918 lines, 83854 bytes, zero solver-state writes) |
| The soft source is not a terminator | `emfit/modalport.py:19`, `:323`, `:363` |
| The far end is an absorber | `decisions.md:62-66` (superseded by `:421-431`) |
| The port deferral | `decisions.md:120`, `:124` |
| A lumped element at a cut | `decisions.md:421` |
| The seam defect | `decisions.md:433` |
| The audit's blind plane | `decisions.md:463` |
| Termination exists, the port does not | `decisions.md:9344` |
| Mesh counts | `emfit/studies.py:2556-2559`; `emfit/grid.py:113-114`; `emfit/board.py:566` |
| Cost, measured | `evidence/h_refine/h040.json:105,124,134,148`; `evidence/rung_c/h020.json:135,154,164,191`; `evidence/stations_n18.json:193` |
| Section 161 stands | `decisions.md` section 161 |
