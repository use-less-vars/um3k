# D58.1 Close-out: what R measures, why the offset is not an estimator artefact, and the interface under-jump

Provenance tags: [ARTIFACT] read from a file in this repository; [MEASURED] computed by a run validated against a banked number; [DERIVED] algebra on the above; [PROPOSED] invented here and explicitly not established; [ARCHIVE] quoted from a prior brief. No line numbers (R6). The artifact wins over this document.

## 0. Verdict

1. R is *called* an energy ratio throughout the record, in six independent files, but the estimator implements no energy weighting: it is a plain ratio of summed squared field components. [ARTIFACT] The label and the code disagree.
2. Weighting R by eps does not shrink the 44 % discrepancy; it grows it by a factor 1.896 [MEASURED]. Even against an eps-weighted analytic comparator, which is the like-for-like comparison, Q moves away from 1, from 1.4408654619908656 to 1.492783748381989, a widening of 11.78 % [MEASURED].
3. The two remaining corrections are quantitatively irrelevant: measure +0.057 % of the gap, lattice +5.17 % of the gap (or +0.98 % under the de-stagger rule the frozen document already uses) [MEASURED]. The corrections cannot supply the -77.4 % of the gap that band entry requires.
4. Therefore the 44 % offset is not an artefact of the estimator. It is a property of the field.
5. The one measured field property of the right sign and roughly the right size is the interface jump: the extracted normal field steps by 3.7903993750636298 across the interface where eps_r = 4.4 requires 4.4 [MEASURED], an under-jump of 13.85 %. A two-box model of that defect accounts for about 47 % of the measured excess substrate share of E_z [DERIVED-model, section 5]. That is a hypothesis, not a fit, and it is not a correction.

## 1. What R is supposed to measure (Task 1)

Verdict: **(a) an energy ratio**, stated explicitly, in six independent files [ARTIFACT]:

- docs/report/sec_modes.tex: "the energy ratio $R = \sum e_{z,vv}^2 / \sum e_y^2$ --- the $e_z$ component at its $vv$ lattice placement over the $e_y$ component".
- tools/host/c1-audit/c1_audit.py, comment beside the bank write: "vertical / in-plane energy ratio of the EXTRACTED field ... the T4_amp numerator".
- docs/design/57c_closeout.md, T1.5: "R is an energy ratio and dimensionless; Q is dimensionless".
- docs/design/t4_amp_ratio.md: "the extracted vertical-over-in-plane energy ratio agrees with the analytic one".
- decisions.md: refers to R as an energy ratio and to the vertical-over-in-plane construction.
- docs/design/normalization_scheme.md: distinguishes an energy ratio from a "bare-field ratio" precisely by whether eps_r is carried, which is the distinction this audit turns on.

Against that, the same number is called an "amplitude ratio" in four other files [ARTIFACT], and docs/design/t4_amp_ratio.md's own table gives `sqrt(R)` as the amplitude ratio. So the record is not silent and not consistent: it labels one quantity two ways, and the estimator implements neither label's weighting.

Negative evidence, and it is decisive for Task 3: docs/design/t4_amp_ratio.md states "the ratio is plain node sums of squares: no quadrature weights, no trapezoid factors, no background subtraction" [ARTIFACT]. The absence of eps is therefore documented, not accidental.

Searched, with no statement of the measured quantity found: `proxy`, `mode ratio` (zero hits across the design set); the sparse-probe sources contain no `energy ratio` or `permittivity` token at all [ARTIFACT].

## 2. The eps-weighting test (Task 2)

Reconstruction validated by reproducing R0 = 4.0489791163950715 exactly, with sum(E_y^2) = 0.08977401529330839 and sum(E_z^2) = 0.3634931131175374 [MEASURED].

| quantity | value |
|---|---|
| f_z, substrate share of sum E_z^2 | 0.88352753599695644 |
| f_y, substrate share of sum E_y^2, interface node to air (primary) | 0.32692842897550339 |
| f_y, interface node to substrate (bracket) | 0.42145217800703211 |
| R0 | 4.0489791163950715 |
| R_eps, primary | 7.6777890348550359 |
| R_eps, bracket | 6.6635855589316773 |
| R_eps/R0, primary | 1.8962283613087152 |
| (1 + 3.4 f_z)/(1 + 3.4 f_y), primary | 1.8962283613087161 |

The identity reproduces the measured ratio to 8.9e-16, so the eps vector is correctly aligned with z and the direction of the effect is not a misalignment artefact [MEASURED].

The preregistered biconditional was: R_eps < R0 iff f_z < f_y. Measured f_z = 0.8835 is greater than f_y = 0.327 [MEASURED], so **R_eps > R0** and eps weighting **increases** the discrepancy by 89.6 % (65 % under the bracket). The brief's direction is falsified.

Spatial distribution, which is the number that decides the direction: E_z is far more substrate-concentrated than E_y. The two shares are not close, so the eps weighting boosts the numerator much harder than the denominator.

The interface ambiguity is large and is reported, not resolved: moving the single z-node at z = 0.0016 between substrate and air moves f_y by 0.0945 absolute (22.4 % relative) and R_eps by 1.014 (15.2 % relative) [MEASURED]. One node layer carries about a tenth of the E_y energy.

## 3. The decomposition (Task 3)

G = R0 - R_analytic = 4.0489791163950715 - 2.8101021387524523 = 1.2388769776426192. Band on R is [2.52909192487721, 3.09111235262770], equivalently Q in [0.9, 1.1]; entering the band requires removing at least 23.66 % of R0, i.e. at least 77.4 % of G [DERIVED].

| stage | R | delta R | delta as % of G | Q | in band |
|---|---|---|---|---|---|
| baseline as written | 4.0489791163950715 | - | - | 1.4408654619908656 | no |
| + eps (C1) | 7.6777890348550359 | +3.6288099184599645 | +292.911240 | 2.732209953857264 | no |
| + measure (C2) | 4.0496869679415486 | +0.00070785154647712289 | +0.057137 | 1.441117357299835 | no |
| + lattice, interface-aware (C3a) | 4.1129745368796931 | +0.06399542048462159 | +5.165599 | 1.4636388052092841 | no |
| + lattice, naive de-stagger (C3b) | 4.0611143983304769 | +0.012135281935405473 | +0.979539 | - | no |
| cumulative eps then measure | 7.6785103992095252 | +3.6295177700055119 | +292.969467 | 2.7324666578199208 | no |
| cumulative eps, measure, lattice | 7.3028591086174668 | +3.2538799922223953 | +262.647547 | 2.5987877835143669 | no |

Accounting: sum of the three single deltas +3.6935131904910632 = +298.133976 % of G; cumulative +3.2538799922223953 = +262.647547 % of G; interaction term, attributed to the last stage applied, -0.43963319826866787 = -35.486429 % of G; residual, cumulative minus R_analytic, +4.4927569698650149 = +362.647547 % of G, which is 159.88 % of R_analytic [MEASURED].

Every correction has the wrong sign except in the trivial sense that two of them are too small to matter. **No combination enters the band; the closest any stage gets to Q = 1 is the baseline itself.**

Two structural findings worth more than the numbers:

- The measure correction the brief asked for does not exist in the form the brief assumed. The extraction lattice is uniform 0.1 mm on both axes [MEASURED], so there is no non-uniform axis to integrate over. The 0.2 mm and 0.5 mm spacings belong to the FEM ZS mesh, a different object from the lattice the extracted field lives on. Integrating with those spacings would integrate a differently sampled field.
- The correct trapezoid convention is one axis per operand: only the operand's *node* axis gets endpoint half-weights, because a cell-centred sample already owns a full cell width. Applied that way it reproduces the frozen document's own row to within 3e-12: extracted 4.0496869679415486 against the document's 4.0496869679447, analytic 2.8107297770526598 against 2.8107297770527 [MEASURED], [ARTIFACT]. Applying it to both axes, which is what a naive reading suggests, costs -2.4 % and is simply a weighting error.
- Once both components sit on the common cell-centred lattice, the measure correction vanishes identically, because every sample owns a full cell width. C2 is therefore not independent of C3; it is an artefact of one operand sitting on a node lattice. This is why the cumulative total is smaller than the sum of the singles.

## 4. The jump test, redesigned (Task 4)

Frozen mask: rows whose y lies outside the strip span y in [0.0085, 0.0115]. The y grid is uniform, first value 0, spacing 0.0001, 201 rows, so the mask is 170 rows out of strip, 31 in strip [MEASURED].

| statistic | value |
|---|---|
| J1 median, masked | 3.7903993750636298 |
| J1 q25, q75, masked | 2.8353371399424034, 4.1970357464264385 |
| d = abs(median/4.4 - 1) | 0.13854559657644783 |
| J1 median, in-strip 31 rows (not interpretable, conductor dominates) | 0.29014037829123102 |
| J1 at the edge row y = 0.0086 | 0.31325109108175092 |
| J2 median, air-side neighbour pair, masked | exactly 1 |

Verdict: the expectation of 4.4 fails the pre-set 10 % bar; the measured median is 13.85 % low [MEASURED]. The air-side neighbour ratio being exactly 1 confirms that the extracted E_z is piecewise constant in z within each material, so the interface step is the only z-structure the field has, and it is 14 % short.

The mask change did not move the median: the earlier out-of-strip figure was already 3.7904. What the frozen mask fixes is auditability, not the number. The number was wrong to trust in the first attempt because the selection rule was not stated, not because the median was miscomputed.

## 5. What the residual is, and what it is not

Not the estimator: sections 2 and 3 measure all three proposed corrections and none of them helps.

Candidate [PROPOSED]: the interface under-jump. Two-box model, stated so it can be attacked. Let the analytic field have substrate-to-air E_z energy ratio S = 0.78647764738342585 / 0.21352235261657415 = 3.6834. The extracted field's share f_z = 0.88352753599695644 requires an effective air energy scaled by a^2 = S(1/f_z - 1) = 0.48556, i.e. a = 0.6968. The measured jump implies a = 3.7903993750636298 / 4.4 = 0.8615, a^2 = 0.7421, hence a predicted f_z of 3.6834 / (3.6834 + 0.7421) = 0.8323 against the measured 0.88352753599695644. That explains 47 % of the excess substrate share [DERIVED-model].

Read that as: the jump defect is the right sign and roughly half the right size. It is not a fit and it does not become one by being repeated. What it does establish is that the discrepancy is a property of the extracted field, at the interface, and that further estimator arithmetic cannot reach it.

A second measured asymmetry points the same way: the extracted field is more substrate-concentrated than the deposited field in *both* components, f_y 0.32692842897550339 against 0.29628174440965183 and f_z 0.88352753599695644 against 0.78647764738342585 [MEASURED]. The ratio of squares therefore inherits a real mode-shape difference, which is what an amplitude/ratio metric reports and what an energy metric would also report.

## 6. Disagreements

1. **The brief's pre-registered direction is falsified.** D58.1 Task 2 states that eps-weighting "can only reduce R, never increase it, for a substrate with eps > 1". Measured: R_eps/R0 = 1.8962283613087152, an increase of 89.6 % [MEASURED]. The direction requires f_z < f_y; the measurement gives f_z = 0.8835 against f_y = 0.327.
2. **My own formula in the D58 status report was inverted.** I wrote R = sum(e_y^2)/sum(e_z^2); the artifact computes R = sum(E_z^2)/sum(E_y^2) [ARTIFACT]. Recorded as erratum #34 in the acceptance document before any 58.1 measurement was taken.
3. **My own registered expectation in the acceptance document was also wrong.** Section 9.2 registered, as [PROPOSED], that E_y would be substrate-heavy and f_y would sit well above f_z. Measured: f_z exceeds f_y by 0.557 absolute [MEASURED]. Both the brief's guess and mine were wrong, in opposite directions, about the same pair of numbers.
4. **The brief's Task 3 premise about a missing measure does not survive.** D58.1 Task 3 posits a missing "real measure (trapz on the non-uniform axis)" and my acceptance rationale asserted that omitting the dual length over-weights the fine substrate side by 2.5x. Both are false: the extraction lattice is uniform 0.1 mm on both axes, and the correct trapezoid convention moves the extracted ratio by +0.0175 % [MEASURED].
5. **A frozen document's sentence is imprecise although its number is right.** docs/design/t4_amp_ratio.md says the ratio uses "no quadrature weights, no trapezoid factors" and its weighting row speaks of switching "both operands" to a trapezoid-weighted sum. The number in that row is reproduced exactly, but only by trapezoiding one axis per operand. Read literally, the sentence describes a weighting that is wrong by -2.4 % on the extracted ratio.
6. **My acceptance document's band wording is wrong and must be read as its arithmetic.** Section 9.3 says "Q lies inside [2.52909192487721, 3.09111235262770]"; that interval is a band on R, not on Q. The numerical criterion used throughout, R_corrected <= 3.09111235262770, is correct and unaffected.
7. **The record labels R two ways.** Six files call it an energy ratio, four call it an amplitude ratio, and docs/design/t4_amp_ratio.md tabulates sqrt(R) as the amplitude ratio. Task 3 was conditioned on the label; the label is inconsistent, and the estimator implements neither reading.
8. **A prior claim of mine about the mask overstated the defect.** The D58 close-out attributed the inconclusive jump result to a mask that selected strip rows. Under the frozen mask the median is 3.7903993750636298, the same number already reported for out-of-strip rows [MEASURED]. The defect was the absence of a stated selection rule, not a miscomputed median.

## 7. Fences and provenance

Files created by 58.1: this document, and section 9 appended to docs/design/d58_extraction_acceptance.md (committed before any measurement). No edits to emfit/, none to viz/, none to decisions.md, none to docs/design/d58_acceptance.md. One transient scratch script under tools/host/c1-audit/ was created and deleted in the same session; one pre-existing __pycache__ directory of bytecode was removed during that cleanup and is disclosed here because it was not mine to remove [ARTIFACT-disclosed by the worker].

Validation caveats, stated rather than buried: the final measurement run reproduced R0 to 4.5e-16 relative rather than exactly, which is a summation-order difference and not a different field, and its correlation gate differed by 1.7e-8 because it used a mean-centred Pearson coefficient where the audit's helper uses an uncentred cosine. The analytic arrays are nevertheless certified, by reproducing R_analytic = 2.8101021387524523 exactly and by their substrate share 0.78647764738342585 agreeing with the 78.65 % the frozen document reports.

## 8. Open items

- The eps-weighted comparator is the one number that decides whether R's energy label can be honoured at all. It is measured here once, primary convention only, and it widens Q. Confirming it under the bracket convention, and against the de-staggered lattice, is worth doing before the label is retired.
- If the interface under-jump is the cause, the next measurement is a jump test in the solver's own discretisation rather than in a re-reduction of its output, to establish whether the 13.85 % deficit is created by the solve or by the extraction.
- The amplitude-ratio reading and the energy-ratio reading of R differ by the substrate content of E_y, and no existing measurement separates them. Any future metric for this geometry should state which one it is before it is computed.