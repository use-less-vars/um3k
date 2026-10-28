# Dispatch 47: the deflated ladder at levels 1 to 3

Status: result 1 matches on all seven measurable rows and result 2 holds at
levels 1 and 2; level 3 is FAILED-TO-MEASURE, so both are FAILED-TO-MEASURE as
whole requirements; result 3 is indicative only; the negative control passes
at level 1; no verdict on the section 4 criterion is formed.

## 1. Status and what this document reports

This document reports the readings of dispatch 47 against the three results
frozen in section B of `docs/design/d47_acceptance.md`, together with the two
numbers section 3.c of the pre-registration attaches to result 1, the
inertness test Amendment 1 demands for itself, the level 3 outcome, and the
negative control. It is written after the runs. It alters no threshold, edits
no frozen document, and adds only itself to the tree.

Verdicts, in the vocabulary of section D of the acceptance document:

| item | verdict | section |
| --- | --- | --- |
| result 1, value-matched spectrum preservation | PASS on all seven measurable rows; the two level-3 entries are FAILED-TO-MEASURE; FAILED-TO-MEASURE as a nine-value requirement | 3 |
| result 1's two accompanying numbers | built dimension of `Z` equals the closed-form count at both measured levels; two residual legs at 0.0, the third at or below 4.5e-18; level 3 ABSENT | 4 |
| result 2, fundamental presence | PASS at levels 1 and 2; FAILED-TO-MEASURE at level 3; FAILED-TO-MEASURE as an every-level requirement | 5 |
| result 3, by-order comparison | reported, labelled indicative, no order estimate formed | 6 |
| the run's own classification block | records a retained candidate above the endpoint, which its own note calls a run failure | 6 |
| inertness of the Amendment 1 rebind | "the seven check 1 rows", Amendment 1's shorthand for the table rows of section A of the acceptance document, are unmoved; the stored artefacts differ at byte level | 7 |
| level 3 | FAILED-TO-MEASURE, iteration cap exhausted at 45401 of 45400 | 8 |
| negative control | PASS on all four conditions, at level 1 | 11 |
| the section 4 acceptance criterion | no verdict formed; levels 4 and 5 are outside scope | 11 |

Authority and provenance, in the order this document defers to them:

1. `docs/design/deflation_preregistration.md`, with Amendment 1 appended to
   it. This is the authority for every threshold, for the 1e-12 bound, for the
   verdict vocabulary of its section 5, and for the budget rule Amendment 1
   introduced.
2. `docs/design/d47_acceptance.md`, which records how this dispatch reads
   those thresholds. Every rule quoted in sections 3 to 6 is quoted from it,
   and nothing in it is a new decision.
3. The run's own records and log lines, quoted verbatim wherever a number
   depends on prose: the classification note in section 6, the log lines in
   section 8, the control record in section 11.
4. `.scratch/d47/number_sheet.md`, the machine-written extraction of the JSON
   artefacts. Every number below is taken from it or from one of the documents
   quoted above; no number is transcribed from memory.

Input sha256, all recomputed in the workspace while this document was written
and all agreeing with the number sheet:

| artefact | sha256 |
| --- | --- |
| `docs/design/d47_acceptance.md` | 7000971eaca167e9cf5380c878d203c7965fb74c33ade4889ad3761c856544d0 |
| `.scratch/d47/number_sheet.md` | 407170e4eb09df48d69ad12c1c131925ce6f2dade4d839980bfa0b33cab550b0 |
| `docs/design/d45_negative_control_addendum.md` | 0931d33685d29e8f7f4c9d769072a11ad8338273fb4af20eb489b87fae24b05d |
| `tools/host/anchor/records/level1.json` | 4824369de524d916e0744ac2ed6d28a158841c8dc6ef024c6b98a6c3ff670af9 |
| `tools/host/anchor/records/negative_control.json` | 369cd7cf671537ffcb922b0765a875d3981c84055e7843a5ee7b7e7aa0628e3e |
| `.scratch/d47/out/level1.json` | 63ed745fa61dc404a6f660a4d6b651e633b303d547ec89d5721555902c43d5fd |
| `.scratch/d47/amend1/level1.json` | c8984786931fa9209f66dc045b0e3308a9d19c23b7ec4a4d6d567ffab7f53cce |
| `.scratch/d47/out/level2.json` | e5e6eb2733e1f7292d51f7c6dd9cf8e2ce0ca8ea87c0597cfaa715b89ed368da |
| `.scratch/d47/amend1/level2.json` | 276cdc2506526f89c328138e6ee5dfaa7e1776dd727439c3a47168d3f55b5761 |
| `.scratch/d47/out/deflated_level1.json` | d4e956d99dd14977767acccdc7d114e1621da91217ea8dc35059bd069ddfea56 |
| `.scratch/d47/amend1/deflated_level1.json` | 7b4c7db4b7d444e73377cca28483100989a5fa631bba975fe456948cd1a55a2e |
| `.scratch/d47/out/deflated_level2.json` | 84315b3214de4ee3c26c1cfaaa28684d7f53644bd7a35a94e59bb5ce74dd1eef |
| `.scratch/d47/amend1/deflated_level2.json` | 2530cc790c3ee5850eae7041363abf4c7d9522a0e6729fbe601c4bd98221c95b |
| `.scratch/d47/level3.attempt1.log` | dafef95071b4f67172ab711e8e36e207b3741865e88530259b3eed18a70378e4 |
| `.scratch/d47/level3.log` | de7b228d32297628df6e989487399292f5929c446ab5e5456949d80d7314b892 |
| `.scratch/d47/level3.driver.log` | e42fd669e0aa09d4f6a663859144ec3368627d437af0361fee7ca0a94bd7c3eb |
| `.scratch/d47/level3_amend1.driver.log` | e65adc4045f1f8a4b8f8bce89a34dc88fbcc8203e2a639b516bc4436e346d5f4 |

`tools/host/anchor/out/negative_control.json` holds the same bytes as the
records copy of the control,
369cd7cf671537ffcb922b0765a875d3981c84055e7843a5ee7b7e7aa0628e3e, so the two
locations are one record and not two.

## 2. What was run

The deflated ladder at levels 1, 2 and 3. Scope, quoted from section E of the
acceptance document:

> "Levels 1, 2 and 3 only, which is 78, 348 and 1464 free degrees of freedom.
  Levels 4 and 5 are outside the scope of this dispatch and no number from
  them is reported. No verdict on the section 4 acceptance criterion can be
  formed from levels 1 to 3, and none is formed here."

The route. The step is recorded as "step 2 (driven ladder), DEFLATED route --
diagnostic, off preregistration", solved by
`emfit.mode2d.solve_modes_deflated` with `deflated_dense_max` 6000. It is a
diagnostic route and not the pre-registered driven path. The three results are
read off it because the acceptance document asks for them there, and not
because it is the registered route; that is stated once here and then not
repeated at every number.

The meshes. Level 1: ny 16, nx 2, h 0.00048828125, 51 nodes, 64 triangles, 114
edges, 36 PEC, 78 free. Level 2: ny 32, nx 4, 256 triangles, 420 edges, 72
PEC, 348 free. Level 3 is 1464 free by section E, and produced nothing.

The solver outcomes:

| level | solver beta | solver eps_eff | solver residual |
| --- | --- | --- | --- |
| 1 | 1736.2570207158667 | 1.5218514286533655 | 2.6864322525155373e-08 |
| 2 | 1736.7133938676964 | 1.5226515675767016 | 2.4788391100008954e-07 |

The deflated level-1 call took 0.0657956600189209 s and the level-2 call
15.031271934509277 s. The level-1 record's own driven-path timing is
0.06679129600524902 s at a peak RSS of 79.0625 MB.

Amendment 1 and its budget. The rebind is injected in the driver and not in
the library. `emfit/mode2d.py` is byte-identical to its committed state; the
change lives in `.scratch/d47/run_deflated.py`, which rebinds the module
attribute. The driver log records it, quoted:

    arpack rebind: emfit.mode2d.eigsh -> maxiter = 40 * n (original: scipy.sparse.linalg._eigen.arpack.arpack.eigsh)

The budget that rebind produced at level 3, quoted from `level3.log` line 9:

      arpack budget: n=1135 k=16 maxiter=45400 (=40*1135)

Amendment 1 writes the cap as 40 * n, and n is the deflated dimension. At
level 3 that dimension is 1135 = 1464 - 329: the 1464 free degrees of freedom
of section E of the acceptance document, less the 329 gradient columns that
deflation removes. The applied budget is therefore the amended budget itself
and not an approximation of it, the cap of 45400 being 40 * 1135 exactly, and
1135 is the n the ARPACK call itself reports.

Artefacts. `.scratch/d47/run_deflated.py` (driver, carrying the rebind),
`.scratch/d47/run_level3.sh`, `.scratch/d47/out/level1.json`,
`out/level2.json`, `out/deflated_level1.json`, `out/deflated_level2.json`
(first pass), `.scratch/d47/amend1/` holding the same four names (re-run under
Amendment 1), `.scratch/d47/level3.attempt1.log`,
`.scratch/d47/level3.driver.log`, `.scratch/d47/level3_amend1.driver.log`,
`.scratch/d47/level3.log`, and `.scratch/d47/number_sheet.md`. Neither `out/`
nor `amend1/` holds a level-3 JSON.

## 3. Result 1: value-matched spectrum preservation

The rule, quoted from section B.1 of the acceptance document:

       |beta^2_def - beta^2_frozen| / max(1, |beta^2_frozen|) <= 1e-12

written on beta^2, "and the same inequality written on beta". The bound is
"fixed before the run and is not adjustable afterwards". Every frozen beta^2
is of order 1e6 and every beta of order 1e3, so the max(1, .) wrapper selects
the absolute value at every row and both legs are relative tests.

Frozen against returned, seven measurable rows:

| row | level | frozen beta | frozen beta^2 | nearest index | returned beta | returned beta^2 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1 | 1736.2570207158685 | 3014588.4419851443 | 3 | 1736.2570207158667 | 3014588.4419851378 |
| 1 | 1 | 1636.5986739978343 | 2678455.2197314696 | 4 | 1636.5986739978343 | 2678455.2197314696 |
| 2 | 1 | 1296.9723776897456 | 1682137.3484901919 | 5 | 1296.9723776897467 | 1682137.3484901949 |
| 3 | 1 | 952.9911948312771 | 908192.2174259451 | 6 | 952.991194831277 | 908192.2174259449 |
| 4 | 1 | none | -179735.7274530737 | 7 | none | -179735.72745307558 |
| 5 | 2 | 1296.4632008496378 | 1680816.8311572883 | 12 | 1296.46320084964 | 1680816.831157294 |
| 6 | 2 | 946.6516295409791 | 896149.3077125911 | 13 | 946.6516295409775 | 896149.3077125882 |

The same rows against the bound:

| row | rel dev on beta^2 | rel dev on beta | match |
| --- | --- | --- | --- |
| 0 | 2.162569832588934e-15 | 1.0476498478294861e-15 | True |
| 1 | 0.0 | 0.0 | True |
| 2 | 1.799376471973004e-15 | 8.765555818861977e-16 | True |
| 3 | 2.5636714253484e-16 | 1.192947409569128e-16 | True |
| 4 | 1.0525169405629708e-14 | not applicable | True (beta^2 leg only) |
| 5 | 3.4630579510195553e-15 | 1.7537996859010159e-15 | True |
| 6 | 3.2476541806432718e-15 | 1.6813109262531784e-15 | True |

Seven of seven match. The worst deviation is row 4's 1.0525169405629708e-14,
two orders of magnitude inside the bound; every other row is smaller. Row 1
reproduces its frozen values bit for bit on both legs.

Row 4 carries no beta in the frozen record, which stores the negative
eigenvalue in slot 16 as beta^2 = -179735.7274530737. The beta form of the
rule binds on the eight entries of the nine that carry a beta, so this row is
tested on its beta^2 leg alone and its beta leg is named here as not
applicable rather than as a pass.

The two level-3 entries could not be measured, and that is named as such
rather than as a miss:

| row | level | frozen beta | frozen beta^2 | outcome |
| --- | --- | --- | --- | --- |
| 7 | 3 | 1296.3400089040304 | 1680497.4186853017 | FAILED-TO-MEASURE |
| 8 | 3 | 945.1123879493056 | 893237.4258552386 | FAILED-TO-MEASURE |

No level-3 eigenpair was returned, so these two values were neither found nor
failed to be found. Section 8 gives the reason. The consequence is that the
nine-value requirement is FAILED-TO-MEASURE as a whole: every value that could
be tested reappears after deflation within the bound, and two of the nine were
not testable. It is not a PASS of the requirement and nothing here relaxes
section 5.a of the pre-registration.

## 4. The two numbers that accompany result 1

Why they are required, quoted from section B of the acceptance document:

> "Section 3.c records why they are necessary, namely that a strict subspace
  `Z` is an under-removal which leaves every frozen value in place and passes
  result 1 while the cluster has not been removed in full."

The built dimension of `Z` against the structural count:

| level | built dim of Z | closed-form count | free DOF | columns, n_free less z_dim | block-diag ratio |
| --- | --- | --- | --- | --- | --- |
| 1 | 11 | 11 | 78 | 67 | 0.9659258262891854 |
| 2 | 69 | 69 | 348 | 279 | 0.9125795739517983 |
| 3 | ABSENT | ABSENT | 1464 | ABSENT | ABSENT |

The residual ratios of section 2.d and the orthogonality of the built
subspace:

| level | z orthogonality, abs | z orthogonality, rel | r_gram_dev | residual grad | residual eps-mu | residual pencil |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1.2157219620641853e-15 | 1.6897281902898433e-17 | 2.668090019845927e-16 | 0.0 | 0.0 | 4.4489541781437845e-18 |
| 2 | 3.896522001803983e-15 | 1.0506178012447048e-17 | 6.015096752685323e-16 | 0.0 | 0.0 | 5.167358015355723e-19 |

At both measured levels the built dimension of `Z` equals the closed-form
structural count exactly: 11 against 11 for 78 free degrees of freedom, 69
against 69 for 348. The failure mode section 3.c names is therefore not what
happened at levels 1 and 2. A strict subspace would show a built dimension
below the structural count, and it would show up here as a smaller `Z` with
the residual ratios still small; instead the two numbers agree, the two vanish
identically on the gradient and eps-mu legs, and the pencil residual sits at
4.4489541781437845e-18 and 5.167358015355723e-19, which is round-off on a
pencil of order the stiffness scale. The column counts 67 and 279 follow by
subtraction and are the dense sizes the run was allowed to reach under
`deflated_dense_max` 6000.

At level 3 both numbers are ABSENT, with the rest of level 3.

## 5. Result 2: fundamental presence

The requirement, quoted from section B.2 of the acceptance document: "The
fundamental's beta^2 at each of levels 1, 2 and 3, set against the frozen
value 2678455.2197314696 and the analytic value 1637.9985692980779. Presence
is mandatory at every level, which is inherited and not a new requirement."

| level | frozen beta^2 | returned beta | returned beta^2 | rel dev from frozen beta | distance to analytic, relative |
| --- | --- | --- | --- | --- | --- |
| 1 | 2678455.2197314696 | 1636.5986739978343 | 2678455.2197314696 | 0.0 | 0.000854637681914113 |
| 2 | 2678455.2197314696 | 1637.6502447965015 | 2681898.3242820413 | 0.0006425343093419632 | 0.00021265250660483599 |
| 3 | 2678455.2197314696 | ABSENT | ABSENT | ABSENT | ABSENT |

Level 1 returns the fundamental's beta^2 bit for bit, row 1 of section 3, both
legs exactly 0.0. Level 2 returns it at candidate index 11, and the
0.0006425343093419632 by which its beta differs from the frozen value is the
distance between level 1 and level 2 rather than a deflation error: the frozen
value is a level-1 number being compared against a level-2 solve, which is
exactly what the acceptance document asks for. Against its own analytic value
the level-2 fundamental sits 0.00021265250660483599 away, and the level-1
fundamental 0.000854637681914113 away.

Presence at level 2 is something the deflated route bought. Section 7 of
`docs/design/d45_anchor_results.md` records the undeflated level-2 run as
retaining two candidates, 1296.4632008496378 and 946.6516295409791, with no
fundamental among them. The deflated level-2 run returns the fundamental among
its retained candidates.

Level 3 is FAILED-TO-MEASURE for the reason section 8 gives: no level-3
artefact exists. Since presence is mandatory at every level, the requirement
is FAILED-TO-MEASURE as a whole; levels 1 and 2 pass it, and that split is
stated rather than averaged.

## 6. Result 3: by-order comparison, indicative

The label is the acceptance document's: "By-order comparison against the
analytic ladder, with per-mode relative error and level-to-level ratios,
labelled indicative. No order estimate is formed as a verdict in this
dispatch." None is formed here.

| order | analytic beta | level 1 matched beta | level 1 rel error | level 2 matched beta | level 2 rel error | level 3 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1637.9985692980779 | 1990.41155629495 | 0.21514853163021364 | 1990.4115562949266 | 0.21514853163019934 | ABSENT |
| 2 | 1296.2992799512633 | 1990.411556294948 | 0.5354568093023866 | 1990.4115562949232 | 0.5354568093023675 | ABSENT |
| 3 | 944.6029788248537 | 1990.411556294947 | 1.1071408844921768 | 1990.411556294911 | 1.1071408844921382 | ABSENT |

Level-to-level ratios, level 2 over level 1: 0.9999999999999882 for order 1,
0.9999999999999876 for order 2 and 0.9999999999999818 for order 3. Level 3
over level 2 is ABSENT.

The candidates that the positional match selected, with their own diagnostics
at level 1:

| order | eps_eff | eps_eff ref | curl ratio | contaminated |
| --- | --- | --- | --- | --- |
| 1 | 2.0000000000000044 | 1.3544758398156966 | 4.7037326706944863e-23 | False |
| 2 | 1.9999999999999998 | 0.8483103899760305 | -7.755809876311815e-11 | True |
| 3 | 1.9999999999999984 | 0.45044611773722776 | -4.4275011035767524e-10 | True |

At level 2 the same three candidates read eps_eff 1.999999999999957,
1.9999999999999505 and 1.9999999999999254, with curl ratios
4.819582271948345e-10, 7.847081998678099e-10 and -1.878098367329647e-10, and
contaminated flags False, True and True.

The reading these numbers support is that the positional match selected one
state family three times. All six eps_eff values equal 2.0 to thirteen
significant figures, which is eps_r, and all six betas sit at
1990.4115562949..., which the addendum identifies as the endpoint beta equal
to the square root of eps_r times k0. The per-mode relative errors
0.21514853163021364, 0.5354568093023866 and 1.1071408844921768 are therefore
the spacing of that family against the analytic ladder and not a measure of
convergence, and the level-to-level ratios of 1.0 record that refinement does
not move it at all. This is reported because result 3 asks for the numbers; it
is not promoted to an order estimate, and the ratios of unity are the opposite
of what an order estimate would need.

Recorded against the level-1 spectrum, because a reader of section 3 alone
would not see it. The level-1 classification block returns 16 candidates,
retains 16, drops none and names 4 as surplus; the level-2 block returns 16,
retains 16, drops none and names 11 as surplus. The filter rule is
`|eps_eff - 1| <= 1e-08` with a gap rule `log10(D/R) >= 6`, and at level 1
the separation test is recorded as vacuous because the dropped set is empty,
so the gap rule decided nothing. One retained candidate sits above the
endpoint, index 0 at beta 1990.41155629495 with beta^2 3961738.1634324854 and
eps_eff 2.0000000000000044, and the level-1 record's own note on it, quoted:

> "RETAINED CANDIDATE ABOVE THE ENDPOINT 1990.411556: section 5 makes this a
  run failure"

The contamination flag orders at level 1 are 2 and 3. Level 2 records no
above-endpoint candidate. This document does not overrule that note: the run's
own classification stage reports a failure, it sits beside the PASS of section
3, and the two are reported together.

## 7. Inertness of the amendment

Amendment 1 requires its own inertness to be shown, quoted verbatim:

> "Inertness, to be shown and not asserted. Levels 1 and 2 are re-measured
  under the rebind and the seven check 1 rows of the acceptance document are
  re-applied to the same 1e-12 bound. Any movement there voids this entry and
  the reading that depends on it."

The clause names "the seven check 1 rows", which is Amendment 1's shorthand
and not the acceptance document's vocabulary: `docs/design/d47_acceptance.md`
never uses the word "check". The rows it means are the table rows of its
section A, five at level 1 and two at level 2, compared against the 1e-12
bound of section 3.b of the pre-registration. Every one of those seven rows
is unmoved against that bound: the table in section 3 is the re-run's table,
and all seven match at 1e-12, worst 1.0525169405629708e-14.

A wider test was also run, comparing every stored leaf of the first pass
against the re-run. The four artefacts are not identical leaf for leaf, and
the differences are set out in the table below.

| artefact | first pass | Amendment 1 | leaves | leaves differing | worst abs diff | worst diff excluding timings | inert at 1e-06 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `level1.json` | 63ed745fa61d | c8984786931f | 377 / 386 | 171 | 0.7578125 (`peak_rss_mb`) | 2.60770320892334e-08 at `classification.candidates_all[10].beta_sq`, 169 differing | no |
| `level2.json` | e5e6eb2733e1 | 276cdc250652 | 430 / 430 | 232 | 13.147692203521729 (`wall_time_s`) | 2.0675361156463623e-07 at `classification.candidates_all[7].beta_sq`, 230 differing | yes |
| `deflated_level1.json` | d4e956d99dd1 | 7b4c7db4b7d4 | 29 / 29 | 4 | 0.05736708641052246 (`wall_time_s`) | 6.845263169979707e-09 at `solver_residual`, 3 differing | yes |
| `deflated_level2.json` | 84315b3214de | 2530cc790c3e | 29 / 29 | 4 | 13.147834777832031 (`wall_time_s`) | 2.624182427617655e-08 at `solver_residual`, 3 differing | yes |

The hashes are twelve-character prefixes; the full values are in section 1.
"Leaves" is first pass then re-run. In the two deflated files the differing
leaves are exactly `solver_beta`, `solver_eps_eff`, `solver_residual` and
`wall_time_s`, so the eigenvalue leaves do move, and they move by less than
the residual leaf, which carries the largest non-timing difference in both
files.

There is one structural difference between the passes. The re-run's level-1
record holds nine leaves the first pass does not, all of them under
`classification.above_endpoint[1].*`: a second above-endpoint entry, in a
record whose first-pass copy holds one. The count of such states inside the
16-candidate window is therefore not reproducible between passes, while the
physical values are, to the digits in section 3. That is the only change in
the leaf population at any level.

The conclusion this document reaches, as a decision and not as a choice
between live readings: the clause is not voided. The reason is that the
clause sets its own scope, "the seven check 1 rows ... re-applied to the same
1e-12 bound", and every one of those rows is unmoved against that bound, the
worst being 1.0525169405629708e-14, two orders inside it.

The wider digit-level reading is rejected rather than left standing. No
numerical re-run of a Krylov solve reproduces bits: the call converges on a
stopping test against residuals, not by an exact sequence, so a leaf-for-leaf
test could never be passed by any run of this solver. A condition that no run
can meet is not the condition the clause set for itself, and reading it as
one would void every entry that will ever be written.

The artefact differences that prompted that test are real, and they are
disclosed here because they belong in the record. The re-run's level-1 record
carries `classification.above_endpoint` leaves that the earlier
`out/level1.json` predates, the two runs differ in `wall_time_s` and
`peak_rss_mb` by construction, and the remaining leaf differences are
round-off: at most 2.0675361156463623e-07 absolute on values of order 1e6,
which is about 5e-14 relative, the same size as the run-to-run noise the
spectrum in section 3 already shows. None of these is a movement in the seven
rows, and the added diagnostic key does not enter any verdict quantity.

## 8. Level 3 is FAILED-TO-MEASURE

Level 3 is the level of 1464 free degrees of freedom, and it is the only level
whose reading is not a number.

Attempt 1, `.scratch/d47/level3.attempt1.log`, sha256
dafef95071b4f67172ab711e8e36e207b3741865e88530259b3eed18a70378e4, lines 7 and
8:

    ABORTED after 0 of 1 level(s): ArpackNoConvergence: ARPACK error -1: No convergence (11351 iterations, 12/16 eigenvectors converged)
    total wall time: 550.8 s

Amendment 1's remedy, then applied. The ARPACK entry point is rebound so that
the iteration cap is 40 * n. The library is untouched and the rebind lives in
the driver, as section 2 records. `.scratch/d47/level3_amend1.driver.log`,
sha256 e65adc4045f1f8a4b8f8bce89a34dc88fbcc8203e2a639b516bc4436e346d5f4, lines
2 and 4:

    [run_level3] start: 2026-10-28T19:37:10Z
    arpack rebind: emfit.mode2d.eigsh -> maxiter = 40 * n (original: scipy.sparse.linalg._eigen.arpack.arpack.eigsh)

The amended run, `.scratch/d47/level3.log`, sha256
de7b228d32297628df6e989487399292f5929c446ab5e5456949d80d7314b892, 706 bytes,
modified 2026-10-28T20:04:23.211470Z, lines 9 to 11:

      arpack budget: n=1135 k=16 maxiter=45400 (=40*1135)
    ABORTED after 0 of 1 level(s): ArpackNoConvergence: ARPACK error -1: No convergence (45401 iterations, 15/16 eigenvectors converged)
    total wall time: 1632.8 s

The budget was exhausted rather than left unused: 45401 iterations against a
cap of 45400, with 15 of the 16 requested eigenvectors converged. The extra
budget bought three more converged vectors and no certificate. The wall time
went from 550.8 s to 1632.8 s and the abort is the same abort.

The consequence is written into Amendment 1 itself, quoted verbatim:

> "If 40 * n is also exhausted at level 3, the level 3 reading is
  FAILED-TO-MEASURE under section 5.a and is recorded as such, with no second
  budget and no further attempt without a new dated entry."

The condition is met literally. The reading is FAILED-TO-MEASURE. No second
budget is taken and no further attempt is made in this dispatch. Fifteen of
sixteen converged vectors are not a certifiable set: under the definition the
acceptance document quotes, FAILED-TO-MEASURE means the apparatus could not
resolve the modes, and a set with one member missing is not resolved. No
partial level-3 spectrum is reported here, and none could be, since nothing
was written.

There is no level-3 JSON in `out/` or in `amend1/`, for either the plain or
the deflated route. The absent files are `out/level3.json`,
`out/deflated_level3.json`, `amend1/level3.json` and
`amend1/deflated_level3.json`.

## 9. What is not measured

Level 3 has no result at all, and this is stated here rather than left to be
inferred from an absent file. No level-3 value appears in the spectrum, in
the rows above, in the ladder or in the level-to-level ratios; the number
sheet marks every one of those entries ABSENT.

The by-order comparison at levels 1 and 2 is indicative rather than a
measurement of the physical modes. Positional matching pairs the analytic
modes with the slab gradient family, so a small relative error there says
where the eigenvalues sit and not which physical mode was found.

Any quantity the number sheet marks ABSENT is not estimated anywhere in this
document, by interpolation or otherwise.

## 10. Close-out routes

Three routes are open. None is applied in this dispatch and none is
recommended over the others.

(a) Extend the deflation subspace Z to the slab family at eps_r * k0^2. This
is structural: it changes the deflation algebra, and it is the only one of
the three that changes what is removed rather than what is kept.

(b) Replace the eps_eff drop rule with a curl-ratio floor. This is
filter-only: it leaves the deflation algebra alone and changes which
candidates are retained.

(c) Both, taken together.

Section 5.a forbids relaxing any threshold, so any of the three needs a dated
entry written before the run it governs, not a quiet change to a filter or a
subspace. The addendum route already exists as a precedent: Amendment 1 is
itself such an entry. Which route is taken, if any, is not decided here.

## 11. The negative control, and what remains open

The control is the deferred obligation of section 6 of the anchor
pre-registration, recorded in
`tools/host/anchor/records/negative_control.json`, sha256
369cd7cf671537ffcb922b0765a875d3981c84055e7843a5ee7b7e7aa0628e3e. Its fields:
step "4 (negative control, section 6)", geometry B with t = b/8, level 1,
eps_r 2.0, k0 1407.4335088082273, 16 candidates, verdict PASS, exit code 0,
wall time 0.20717644691467285 s. Its instrument record is
`docs/design/d45_negative_control_addendum.md`, sha256
0931d33685d29e8f7f4c9d769072a11ad8338273fb4af20eb489b87fae24b05d, and its
input `tools/host/anchor/records/level1.json`, sha256
4824369de524d916e0744ac2ed6d28a158841c8dc6ef024c6b98a6c3ff670af9.

The pairing rule, quoted from addendum section 2: "nearest retained physical
candidate within the distance, each geometry against its own analytic betas,
then A to B through the shared analytic mode index". The tolerance is 0.02
relative, retention uses the committed "kept" flag, and `not_measured_modes`
is empty, so no mode was excused.

Pairings, each mode against its own geometry's analytic beta:

| geometry | mode | beta ref | distance, relative | paired candidate |
| --- | --- | --- | --- | --- |
| A | 1 | 1637.9985692980779 | 0.000854637681914113 | 1636.5986739978343 |
| A | 2 | 1296.2992799512633 | 0.0005192456316936239 | 1296.9723776897456 |
| A | 3 | 944.6029788248537 | 0.0088801498560367 | 952.9911948312771 |
| B | 1 | 1370.1426441407846 | 0.0009051582448442991 | 1371.3828400517414 |
| B | 2 | 1220.4777421405508 | 0.0022951092066570947 | 1223.2788718430577 |
| B | 3 | 868.5400506458038 | 0.009613595501867554 | 876.8898433698841 |

Condition 1, rule "/r - p/ <= 0.02", with r and p the relative displacements
of the two geometries from their own analytic values:

| mode | beta A | beta B | r | p | r - p | verdict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1636.5986739978343 | 1371.3828400517414 | -0.16205306661909463 | -0.1635263486659064 | 0.001473282046811769 | PASS |
| 2 | 1296.9723776897456 | 1223.2788718430577 | -0.056819641739753735 | -0.05849076597000279 | 0.001671124230249052 | PASS |
| 3 | 952.9911948312771 | 876.8898433698841 | -0.07985525141695181 | -0.08052370136888307 | 0.0006684499519312576 | PASS |

Condition 2, rule "/eps_eff - ref/ <= 0.02 and the measured triple strictly
decreasing in mode index", band 0.02:

| mode | eps_eff | ref | delta | strictly decreasing | verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.9494271536405305 | 0.9477107208249235 | 0.0017164328156070718 | True | PASS |
| 2 | 0.7554316497287761 | 0.7519759548015799 | 0.003455694927196218 | True | PASS |
| 3 | 0.3881810284701141 | 0.3808236629763696 | 0.007357365493744494 | True | PASS |

Condition 3, the census: every mode is paired_A True, paired_B True, and
census_ok True. PASS.

Condition 4, the void test: void_move 1e-06, harness_void False, and every
per-mode move, which are the cond 1 values of r given above, measured False.
PASS.

The control therefore passes all four conditions, at level 1, with no mode
unmeasured.

One digit-level note so that the two documents are not read as disagreeing.
The addendum states "The worst geometry A pairing residual at level 1 is
8.88014985603658e-03 relative, on mode 3"; the stored pairing for that row is
0.0088801498560367, which differs in the last stored digits by 1.2e-16
absolute and agrees to the stated figures.

What remains open, named rather than summarised:

1. Two of the nine frozen values, both at level 3, are unmeasured. Result 1
   and result 2 are FAILED-TO-MEASURE as whole requirements for that reason,
   and Amendment 1 forbids a further attempt without a new dated entry.
2. The section 4 criterion is untouched: order band 1.7 to 2.3, the absolute
   bound at the finest mesh, by-order matching across all five levels, and the
   fundamental at every level. Levels 4 and 5 are outside the scope of this
   dispatch, and no order estimate is formed from levels 1 to 3.
3. The above-endpoint retention of section 6 and the empty dropped set stand
   on the record unresolved. The run's own note calls the retention a run
   failure under section 5; this document reports that and does not overrule
   it.
4. Level 3 produced no artefact. The budget is not the suspect: at 40 * 1135
   it is the amended budget exactly, and it was consumed in full by a
   spectrum that resists convergence. No second budget exists without a new
   dated entry, so level 3 stands where section 8 leaves it.
5. The four artefacts differ at byte level between the passes, in timing and
   memory leaves, in the added `classification.above_endpoint` entries, and
   in round-off. Section 7 records this and treats none of it as a movement
   in the seven rows.
6. The negative control ran at level 1 only, per addendum section 7, so it
   certifies the pairing procedure at one mesh and not across the ladder.

Nothing in this document is a verdict on section 4, and no threshold in
`docs/design/d47_acceptance.md` or in the pre-registration is altered by it.
