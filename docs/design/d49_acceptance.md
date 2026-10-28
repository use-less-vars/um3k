# Dispatch 49: acceptance criteria

Dated 2026-10-28. Frozen on commit: the commit that first contains this file is
the freeze, and from that moment nothing here is editable in place.

**This document is frozen before the Task 1 census was run, and the census
outcome is not known at freeze time.** Nothing below reports a measurement made
in dispatch 49. The numbers it carries are carried, not measured, and they say
what the dispatch is allowed to conclude rather than what it has concluded.

It decides nothing that the documents it cites already decide, and it relaxes
no threshold: no floor, band, tolerance, budget or candidate count in any
earlier document is widened by this one.

Provenance tags, as in `docs/design/d48_acceptance.md` and
`docs/design/deflation_preregistration.md`:

- `[USER]` the supervisor's brief for this dispatch, transcribed without
  alteration.
- `[VERIFIED this session]` read out of the tree in this session by direct read
  of the cited `file:line`, or computed by arithmetic on such reads. The
  citation is given so the claim can be re-checked.
- `[RELAYED]` carried from an earlier dispatch or from recollection and not
  re-verified here. **A statement carrying no tag is `[RELAYED]`.**

## 1. Provenance and what is frozen

This document governs dispatch 49 and nothing else. It fixes, before the fact:
what the dispatch inherits as settled (section 2), what it inherits as broken
or under-specified (sections 3 and 4), what it is forbidden to do (section 5),
what Task 1 must report to be considered done (section 6), the gate that ends
the dispatch early (section 7), and what Task 2 and the ladder runs must
satisfy if the gate clears (sections 9 and 10).

It was written after `docs/design/d48_results.md` and after
`docs/design/deflation_v2_preregistration.md` entered the tree, and it changes
neither. Its purpose is that the census result and the preservation result be
read against criteria fixed while both were unknown.

The one thing this document cannot do is make the census succeed. If the census
returns the harmful answer, the criteria below are met by reporting it and
ending the dispatch, not by working around it (section 7).

## 2. The carried verdict and its companions

These are frozen inputs. They are [RELAYED] and are re-read from the cited
documents at the start of the dispatch, not re-derived.

- **The verdict.** Dispatch 48 classified the family at
  `beta = sqrt(eps_r) * k0` as **SPURIOUS-CURL-FREE**, on both passes: 11
  members curl-free, 0 physical, 0 intermediate
  (`docs/design/d48_results.md` sections 5 to 7) [RELAYED].
- **The band-factor arithmetic.** Counting the members above the band
  `factor * g` at factors 1, 2, 3, 4 and 10 gives 8, 4, 3, 0, 0 respectively
  (`docs/design/d48_results.md` section 9) [RELAYED]. The verdict therefore
  holds for any band factor of 4 or more and becomes `UNDETERMINED` at 3 or
  less. The frozen factor of 10 is not renegotiated here; the arithmetic is
  recorded because it is the whole of the verdict's stability.
- **The uncalibrated call.** Without the two calibration endpoints the honest
  call on this family would have been `UNDETERMINED`, not
  `SPURIOUS-CURL-FREE` (`docs/design/d48_results.md` section 8) [RELAYED].

**Correction of record, stated in the terms it was got wrong. The phrase "the
margin is decades" was asserted in dispatch 48 and is FALSE; the margin is a
factor of four.** The largest member sits 3.0273198660887313 below the frozen
band (8.849983581104381e-10 against `T1` = 2.6791731109636385e-09), which is a
factor of three, not a factor of ten, and the count column above is zero from
factor 4 upward [RELAYED from `docs/design/d48_results.md` sections 6 and 9].
The separation between the two thresholds, `T2 / T1` = 1609668495085.0112, is
where a decade figure exists in that document, and it describes the gap between
the two calibration populations, not the margin by which any member clears the
band. Downstream text must not restate the margin in decades.

## 3. The specification defect, named

**The absolute curl floor and the code's relative form are two definitions of
one quantity, and they disagree.**

- Absolute, pre-registered: `docs/design/anchor_preregistration.md:604`, "Drop
  every candidate whose `Mode2D.curl_ratio <= 1e-10`" [VERIFIED this session].
- Relative to the set maximum: `emfit/mode2d.py:950-952`, `acceptable =
  np.abs(ratios) >= _CURL_RTOL * r_max` with `_CURL_RTOL = 1.0e-10` at
  `:135` [VERIFIED this session].

On the eleven-member slab family the two forms classify 9 of the 11 members
differently: the absolute form keeps 9 members as physical and the relative form
calls all 11 curl-free (`docs/design/d48_results.md` section 8) [RELAYED].

This is recorded as a **SPECIFICATION DEFECT**, not as a measurement result.
Two definitions of the same quantity giving different answers means the
quantity, as the tree defines it, is under-specified; it does not mean either
measurement is wrong, and it does not overturn the verdict of section 2. The
rule that follows: **any downstream citation of the dispatch-48 verdict must
carry this defect with it.** A sentence that quotes `SPURIOUS-CURL-FREE` and not
the defect is a mis-citation, in this dispatch and in any later one.

The second companion is a limit on the instrument. `residual_grad` is
subspace-level — `info["residual_grad"] = _ratio(_frob_norm(kq_f @ z),
_frob_norm(kq_f) * z_norm)` at `emfit/mode2d.py:1331` — and it is 0.0 at levels
1 and 2 by construction, because `Z` is built from the gradient space
[VERIFIED this session]. There is no per-candidate value of it and none can be
derived. `curl_ratio` is therefore doing work it was not designed for: it is a
spurious-mode audit field on a candidate, not a classifier of families, and the
verdict in section 2 is a verdict produced by a measure reused outside its
design intent. Both companions travel with the verdict.

## 4. The unresolved `g`

`g` is the largest absolute curl ratio among the eleven members of the
gradient family at `beta = k0`, and it is the calibration constant of the whole
verdict. Its value is disputed between two documents:

- `docs/design/d45_anchor_results.md:67` gives the level-1 gradient cluster as
  spanning 1.1e-12 to 4.0e-10 [VERIFIED this session].
- The dispatch-48 record gives the same eleven members as spanning
  3.5302376941387836e-11 to 2.6791731109636385e-10, and takes
  `g` = 2.6791731109636385e-10 from the record rather than from the prose
  (`docs/design/d48_results.md` section 4) [RELAYED].

**Recorded as UNRESOLVED and NON-BLOCKING.** Standing condition: **it must be
resolved before `g` is cited again** in any document that quotes a band or a
margin, and this dispatch does not cite a fresh one.

Why it is non-blocking: both candidate values of `g` clear the verdict at band
factor 4 or more. Taking `g` = 2.6791731109636385e-10, the band at factor 4 is
1.0716692443854554e-09 against a largest member of 8.849983581104381e-10;
taking the prose's 4.0e-10, the band at factor 4 is 1.6e-09 against the same
member. Both are above it, so the direction of the verdict does not depend on
which document is right, only its margin [arithmetic on the two cited spans,
RELAYED from the dispatch-48 record]. The census of section 6 does not use `g`
at all except through AC1.3, where the band is named and not recomputed.

## 5. Fences

1. **`emfit/` edits are authorised for Task 2 only, and they are additive.**
   Nothing under `emfit/` is edited in Task 1. In Task 2 the v1 deflation route
   stays callable and unchanged; the extension is a new route beside it.
2. **No levels 4 or 5.** No mesh, no solve, no formula evaluation presented as a
   measurement at either level. The deflated dense route is capped at 6000 free
   DOFs and level 4 is at that cap.
3. **No budget change for level 3.** The `40 * n` pre-commitment stands as
   frozen in `docs/design/deflation_v2_preregistration.md` section 4. **A
   failure to converge at `40 * n` is a finding about the diagnosis, not a
   measurement failure and not licence to raise the budget.** Raising it after
   the fact would convert a falsified prediction into an open question, which is
   the one thing section 12 of this document names as failure.
4. **`decisions.md` is append-only.** No byte of existing text is touched; the
   dispatch's record is appended, with hashes verified before and after.
5. **Task 2 ends the dispatch.** Nothing is implemented beyond the extension,
   the amendment of AC2.1 and the ladder runs of section 10.

## 6. Task 1, the gating census (read-only)

Task 1 asks the analytic side one question and measures nothing in the solver.
It writes no file under `emfit/`, `tests/` or `tools/`.

- **AC1.1 — enumerate every root of the dispersion relation.** Using the
  validated analytic reference routine, enumerate every root in a beta window
  wide enough to include `2*k0^2` comfortably on both sides. State the window,
  and state why it is wide enough: the criterion is that a root belonging to the
  same branch as the one under test, on either side of it, is inside the window,
  so that "no root at `2*k0^2`" cannot be an artefact of the window's edge. The
  window is a stated number, not a convenience.
- **AC1.2 — the root at or near `2*k0^2`.** Report whether a physical root
  exists at or near `beta^2 = 2*k0^2` = 3961738.16343248. If one exists, give
  its `beta^2`, its distance from `2*k0^2` (absolute and relative), and the
  achieved root precision — the bracket width or the residual that establishes
  how precisely the root is located. A root reported without its precision is
  not reported.
- **AC1.3 — the safety criterion.** If any analytic root lies within the band
  the curl test used — that is, within the calibrated band `T1` named in
  section 4, carried with its unresolved `g` — then **the extension is
  FORBIDDEN and the dispatch ends.** If none does, state that removal cannot
  annihilate a physical mode **for this geometry only**, and mark the guarantee
  as geometry-specific and not general: it licenses the extension on geometry A
  at `t = b/4`, `eps_r = 2` and says nothing about any other geometry, aspect
  ratio, permittivity or level set.
- **AC1.4 — the widened preservation set.** Report how many analytic roots
  exist in the window at all. That count is the size of the widened preservation
  set required by AC2.1: every one of them must reappear after extended
  deflation within the existing 1e-12 bound.

**Task 1 is complete only when AC1.1 to AC1.4 are each answered with the number
the criterion asks for, or with an explicit statement that it could not be
measured and why.** A partial census does not clear the gate.

## 7. The stop rule

**If Task 1 finds a physical root at `beta^2 = 2*k0^2`, the dispatch stops and
reports: the census result is written up, the dispatch ends, and the remedy
becomes the pairing rule, not the deflation. This is an absolute gate, and
Task 2 may not proceed past it.** No reading of a partial or ambiguous census
counts as cleared; a census that does not answer AC1.2 and AC1.3 in the terms
above leaves the gate shut.

## 8. The risk being gated, stated plainly

The risk is not that the extension fails loudly. It is that it succeeds
silently. `docs/design/deflation_v2_preregistration.md` names it in section
1.f, at `:116`, under P1:

> If P1 is false in the harmful direction — a physical mode sitting at
> `beta^2 = 2*k0*k0` — the projection annihilates it, and the preservation check
> of section 2 cannot see it, because every frozen value is at
> `beta <= 1736.2570207158685 < 1990.411556294948`.

That is the exact failure mode the census exists to exclude: a physical mode at
`beta^2 = 2*k0^2` would be removed by the projection, the preservation check
would still pass because it tests only the seven frozen rows below that value,
and no assertion, residual or exit code in the run would report anything wrong.
The brief renders the same failure as the spectrum "coming back clean" with
"nothing would error" [USER]; the document's own words for it are that the
preservation check "cannot see it" [VERIFIED this session at the line cited].
The census of section 6 is not a formality preceding Task 2. It is the only
measurement in the dispatch that can distinguish the two cases.

## 9. Task 2, conditional on Task 1 clearing

- **AC2.1 — Amendment 3, frozen before any implementation.** Author a dated
  amendment to `docs/design/deflation_preregistration.md`, committed **before**
  any line of the extension is written, recording (i) the Task 1 census result
  as a frozen number, quoted with its precision; (ii) that the extension is
  licensed only by that census and only for this geometry; and (iii) the widened
  preservation set: every analytic root in the window must reappear after
  extended deflation within the existing 1e-12 bound, not only the seven frozen
  rows of the current check.
- **AC2.2 — additive implementation.** The extension is implemented additively.
  The v1 deflation route remains callable and unchanged, v2 remains as it is, and
  the extension is a third route. Existing tests must not change behaviour; a
  test that must be edited to pass is a failure of this criterion, not a
  maintenance step.
- **AC2.3 — the full suite.** Run the full suite and report the exact pass,
  skip and xfail counts, naming the run. Counts are reported as counts, not as
  "green".

## 10. The ladder, after implementation only

Levels 1, 2 and 3, reporting four things separately and never in one sentence:

1. **The widened preservation result**, for every analytic root in the window,
   against the 1e-12 bound: root by root, its frozen value, its returned value
   and its deviation. The seven frozen rows are a subset of this and are not a
   substitute for it.
2. **The fundamental present at every level** at all three levels, reported as
   present or absent per level.
3. **By-order matching under the new tolerance-and-bijectivity rule**, with the
   five listed mis-pairing routes of
   `docs/design/deflation_v2_preregistration.md` section 3 checked and reported
   individually — each one either exercised-and-refused or stated as not
   exercised at these levels.
4. **Level 3 against the pre-registered prediction at `40 * n`.** Convergence
   means the diagnosis was right. Non-convergence is a finding about the
   diagnosis, stated plainly and **not characterised as a measurement failure
   if the budget was fully spent**: the run spending its budget is the
   measurement, and the prediction is what failed.

## 11. Close-out requirements

The dispatch's report must contain: the commits it made; the commands it ran,
verbatim and in order; the census table of AC1.1 to AC1.4; the preservation
table of section 10 item 1; the by-order table of item 3; the level-3 outcome
against the prediction; any disagreement between this document, the brief and
the tree, stated rather than smoothed; and an explicit statement of whether
**row four of the C++ criterion table can now be marked measured**, with the
evidence that decides it either way.

## 12. What would count as failure

This document can fail, and these are the ways:

- **Task 2 proceeding without a stated census result**, or on a census that
  answers fewer than AC1.1 to AC1.4.
- **An implementation that changes v1 behaviour** — including one that changes
  it only in the digits, or only when a flag is passed.
- **A preservation claim narrower than every analytic root in the window**: the
  seven frozen rows alone, or the rows plus whichever roots happened to
  reproduce.
- **A level-3 outcome described in a way that does not distinguish convergence
  from a spent budget** — "did not converge" for a run that was not given its
  full budget, or "converged" for a run whose residual was read at a different
  tolerance.
- **Any threshold, band or tolerance widened after the fact**, including the
  1e-12 preservation bound, the band factor of 10, the `40 * n` budget and the
  effective-permittivity filter.
- **A citation of the dispatch-48 verdict that does not carry the specification
  defect of section 3** and the unresolved `g` of section 4.
