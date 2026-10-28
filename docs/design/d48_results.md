# Dispatch 48: classification of the slab family at beta = sqrt(eps_r) * k0

Measured under the rule frozen in `docs/design/d48_acceptance.md` (commit
`979c011`), before any candidate was classified. No threshold in that document
was altered after measurement, no file under `emfit/` was edited, and no other
document was rewritten.

## 1. The question, and the answer in one paragraph

The deflated ladder of dispatch 47 returned a family of candidates at
`eps_eff` = 2, that is at `beta_sq` = 3961738.16343248 = 2 k0^2
(`.scratch/d47/out/level1.json`, `classification.candidates_all[i].beta_sq`),
and the question put to this dispatch is whether that family is a second
structural artefact of the same kind as the gradient family, or a physical
mode. Applying the frozen rule of `d48_acceptance.md:147-165` to the eleven
slab members returns **SPURIOUS-CURL-FREE**: every one of the eleven has an
absolute curl ratio below `10 * g`, none is `physical`, none is
`intermediate`, and the largest member clears the band by a factor of
3.0273198660887313. This verdict is a statement about the tree's curl metric at
the resolution the stored data affords. It is not a statement that the
arithmetic eigenvalues are wrong, and it does not decide between the two
absolute forms of the curl test, on which the members split (section 8).

## 2. Locators, and what a number in this document means

Files are referred to by shorthand, each resolved once here, with the sha256
prefix of the bytes read for this dispatch:

- `U1`, `U2` — `tools/host/anchor/records/level1.json`,
  `level2.json`: the undeflated anchor records, `4824369de524d916` /
  `ab592077ab235f8f`, 13472 / 13432 bytes.
- `L1`, `L2` — `.scratch/d47/out/level1.json`, `level2.json`: the d47 first
  pass, `63ed745fa61dc404` / `e5e6eb2733e1f729`.
- `A1`, `A2` — `.scratch/d47/amend1/level1.json`, `level2.json`: the d47
  second pass (amendment 1), `c8984786931fa920` / `276cdc2506526f89`.
- `D1`, `D2`, `D1a`, `D2a` — the four `deflated_level{1,2}.json` metadata
  files, `d4e956d99dd14977`, `84315b3214de4ee3`, `7b4c7db4b7d444e7`,
  `2530cc790c3ee585`.

A per-candidate number is cited as `<record>`,
`classification.candidates_all[i].<field>`; a census number as `<record>`,
`classification.<field>`. Geometry in every record is A (`t = b/4`), b
0.0078125, k0 1407.4335088082273, eps_r 2.0; level 1 is 51 nodes, 64
triangles, 114 edges, 36 PEC nodes, 78 free dofs (`D1`, top-level keys);
level 2 is 256 triangles, 420 edges, 72 PEC nodes, 348 free dofs (`D2`).
`g` and `m` are the names the frozen rule gives the two calibration
quantities (`d48_acceptance.md:147-148`) and they keep those names here.

## 3. The instrument as the tree defines it

The per-candidate quantity is `curl_ratio`, `ratios[i] = float(v @
(k_q[free][:, free] @ v))` at `emfit/mode2d.py:940`. The tolerance
`_CURL_RTOL = 1.0e-10` is fixed at `emfit/mode2d.py:135`, and the test at
`:950-952` is `acceptable = np.abs(ratios) >= _CURL_RTOL * r_max`, with
`r_max` the largest absolute ratio in the candidate set. The test in the code
is therefore **relative to the set maximum**, while
`docs/design/anchor_preregistration.md:604` states the same threshold in
absolute form. Both forms are reported below and neither is chosen
(`d48_acceptance.md:112-114`).

`r_max` is 11483257.963360295 in `L1` and 4053012.356217793 in `L2`
(maximum of `classification.candidates_all[*].curl_ratio` over all sixteen
candidates). Against those, the slab family's maxima are 3.855614075468485e-17
and 2.1835570196393492e-16 of the set maximum — sixteen and fifteen decades
below the relative floor.

The second measure the brief names, `residual_grad`, is subspace-level:
`info["residual_grad"] = _ratio(_frob_norm(kq_f @ z), _frob_norm(kq_f) *
z_norm)` at `emfit/mode2d.py:1331`, documented at `:1260-1264` as 0 meaning
exactly in the null space. It is 0.0 at level 1 and at level 2 (`D1`, `D2`,
`deflation.residual_grad`), as are `residual_eps_mu` and, to round-off,
`residual_pencil` (4.4489541781437845e-18 and 5.167358015355723e-19). It is
identical across the two passes (`D1a`, `D2a`) and it cannot separate one
candidate from another; the per-candidate analogue used in what follows is
`curl_ratio`. Deflation metadata are otherwise identical between the passes:
`z_dim` 11 with closed form 11 and `n_columns` 67 at level 1, `z_dim` 69 with
closed form 69 and `n_columns` 279 at level 2.

## 4. Endpoints and the two thresholds, evaluated before classification

**Endpoint G** (`d48_acceptance.md:134-141`): the gradient family in `U1`. It
is present and carries per-candidate curl ratios: eleven members at indices 2
to 12, all with `eps_eff` = 1 to within 2.1e-15
(`U1`,`classification.candidates_all[2..12].eps_eff`). Endpoint G is therefore
not ABSENT and no substitute was invented.

| idx | beta | eps_eff | curl_ratio | T1 / abs(c) |
| --- | --- | --- | --- | --- |
| 2 | 1407.4335088082282 | 1.0000000000000013 | 8.062809977508971e-11 | 3.3229e+01 |
| 3 | 1407.4335088082278 | 1.0000000000000007 | -1.5597863041551842e-10 | 1.7177e+01 |
| 4 | 1407.4335088082278 | 1.0000000000000007 | -8.954906737125078e-11 | 2.9918e+01 |
| 5 | 1407.4335088082278 | 1.0000000000000004 | -7.289663823913732e-11 | 3.6753e+01 |
| 6 | 1407.4335088082278 | 1.0000000000000004 | 5.606681334849376e-11 | 4.7785e+01 |
| 7 | 1407.4335088082275 | 1.0000000000000004 | 4.440540234007879e-11 | 6.0334e+01 |
| 8 | 1407.4335088082275 | 1.0000000000000002 | 3.5302376941387836e-11 | 7.5892e+01 |
| 9 | 1407.4335088082273 | 1.0000000000000002 | 9.350709576752479e-11 | 2.8652e+01 |
| 10 | 1407.4335088082273 | 1.0 | 2.6791731109636385e-10 | 1.0000e+01 |
| 11 | 1407.433508808227 | 0.9999999999999996 | -1.4366571542772984e-10 | 1.8649e+01 |
| 12 | 1407.433508808226 | 0.9999999999999979 | -2.2676322651385317e-10 | 1.1815e+01 |

`g` = 2.6791731109636385e-10, the level-1 value at index 10. Over the eleven
members the absolute ratios span 3.5302376941387836e-11 to that value, a
factor of 7.589214503634816 — a round-off population, not a set with a zero in
it. **Threshold one: `T1 = 10 * g = 2.6791731109636385e-09`.**

**Endpoint A** (`d48_acceptance.md:143-145`): the candidates in `L1` and `L2`
that reproduce the frozen analytic values of rows 0 to 3 and rows 5 and 6 of
`docs/design/d47_results.md:148-156`. They are `L1` indices 3, 4, 5, 6 and `L2`
indices 12, 13.

| record | idx | beta | eps_eff | curl_ratio | T2 / abs(c) |
| --- | --- | --- | --- | --- | --- |
| L1 | 3 | 1736.2570207158667 | 1.5218514286533655 | 43125.80549597068 | 1.0000e-01 |
| L1 | 4 | 1636.5986739978343 | 1.3521616569484933 | 785938.0820841284 | 5.4872e-03 |
| L1 | 5 | 1296.9723776897467 | 0.8491915816227388 | 394355.4698929659 | 1.0936e-02 |
| L1 | 6 | 952.991194831277 | 0.4584816966495741 | 1282546.6726233843 | 3.3625e-03 |
| L2 | 12 | 1296.46320084964 | 0.8485249462831854 | 393673.6817123026 | 1.0955e-02 |
| L2 | 13 | 946.6516295409775 | 0.452402087540363 | 1286133.3998208093 | 3.3531e-03 |

`m` = 43125.80549597068, `L1` index 3. **Threshold two: `T2 = m / 10 =
4312.580549597068`.** The two thresholds are separated by `T2 / T1` =
1609668495085.0112, that is 12.206736443994961 decades (12.2). The gap is a
property of the two calibration populations, measured before classification;
the frozen decade factor of 10 was fixed at `d48_acceptance.md:172-173` before
either number was seen.

## 5. The slab family, member by member

Membership is `eps_eff` = 2 to within 1.5e-13. Eleven candidates satisfy it:
three in `L1` (indices 0, 1, 2) and eight in `L2` (indices 0 to 7). The
`eps_eff` = 2 family is **absent from `U1` and `U2`**: `U1`'s sixteen
candidates are the eleven gradient members and five others at `eps_eff`
1.5218514286533689, 1.3521616569484933, 0.8491915816227373, 0.4584816966495742
and -0.09073579324957178 (`U1`,`classification.candidates_all[0,1,13,14,15]`).

| level | idx | beta | eps_eff | curl_ratio | abs(c) | T1 / abs(c) | class |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | 0 | 1990.41155629495 | 2.0000000000000044 | 4.7037326706944863e-23 | 4.7037326706944863e-23 | 5.6958e+13 | curl-free |
| L1 | 1 | 1990.411556294948 | 1.9999999999999998 | -7.755809876311815e-11 | 7.755809876311815e-11 | 34.5441 | curl-free |
| L1 | 2 | 1990.411556294947 | 1.9999999999999984 | -4.4275011035767524e-10 | 4.4275011035767524e-10 | 6.0512 | curl-free |
| L2 | 0 | 1990.4115562949266 | 1.999999999999957 | 4.819582271948345e-10 | 4.819582271948345e-10 | 5.5589 | curl-free |
| L2 | 1 | 1990.4115562949232 | 1.9999999999999505 | 7.847081998678099e-10 | 7.847081998678099e-10 | 3.4142 | curl-free |
| L2 | 2 | 1990.411556294911 | 1.9999999999999254 | -1.878098367329647e-10 | 1.878098367329647e-10 | 14.2654 | curl-free |
| L2 | 3 | 1990.4115562949087 | 1.999999999999921 | -8.849983581104381e-10 | 8.849983581104381e-10 | 3.0273 | curl-free |
| L2 | 4 | 1990.411556294896 | 1.9999999999998952 | -4.715228565572416e-10 | 4.715228565572416e-10 | 5.6820 | curl-free |
| L2 | 5 | 1990.411556294894 | 1.9999999999998912 | 3.713923515542898e-10 | 3.713923515542898e-10 | 7.2139 | curl-free |
| L2 | 6 | 1990.4115562948928 | 1.9999999999998888 | -8.333012398847185e-10 | 8.333012398847185e-10 | 3.2151 | curl-free |
| L2 | 7 | 1990.4115562948778 | 1.999999999999859 | 8.732225963310949e-10 | 8.732225963310949e-10 | 3.0681 | curl-free |

The class column is the frozen rule applied to the `T1` column: `curl-free`
because `abs(c) <= T1` in every row (`d48_acceptance.md:152`), and no row
reaches `T2` (`:153`), so no row is `intermediate` (`:154`).

Census, for completeness, from the `classification` block of each record:
`U1` retains 5 of 16 with `n_dropped` 11, all eleven dropped as gradient or
substrate (`|eps_eff - 1| <= 1e-08 (gradient/substrate, v2 8.4)`), and
`n_surplus` 1; `U2` retains 2 of 16 (`FEWER THAN THREE RETAINED (2): section 5
forbids extrapolating missing modes`); `L1`, `L2`, `A1`, `A2` each retain 16 of
16 with `n_dropped` 0 and `separation_vacuous` true. `above_endpoint` is the
empty list in all six records.

## 6. Verdict, and the margin that carries it

Every member falls in the same class, so the verdict follows mechanically from
`d48_acceptance.md:161`: **SPURIOUS-CURL-FREE**. Tally: 11 `curl-free`,
0 `physical`, 0 `intermediate` (`MIXED` and `UNDETERMINED` at `:163-165` are
therefore not triggered).

The largest member is `L2` index 3 at 8.849983581104381e-10, which sits
`T1 / abs(c)` = 3.0273198660887313 times below threshold one, and
4.872981412988006e+12 times below threshold two. The smallest is `L1` index 0
at 4.7037326706944863e-23, 5.6958e+13 times below threshold one; the second
smallest is `L1` index 1 at 7.755809876311815e-11, and the median of the eleven
is 4.715228565572416e-10. The family spans 13.274499833655176 decades
internally, five of them contributed by `L1` index 0 alone.

## 7. Second pass: the verdict reproduces, the digits do not

The classification above was recomputed from the amendment-1 pass (`A1`, `A2`)
before anything was written here. Every one of the eleven members is still
`curl-free`, the max is still `L2` index 3, and the verdict is still
SPURIOUS-CURL-FREE — **the verdict reproduces and the digits do not.**

| member | first pass (abs) | second pass (abs) | abs deviation | T1 / abs(c), 2nd |
| --- | --- | --- | --- | --- |
| L1 0 | 4.7037326706944863e-23 | 1.9361291252359751e-10 | 1.9361291252355047e-10 | 13.8378 |
| L1 1 | 7.755809876311815e-11 | 8.446739793955873e-11 | 6.909299176440579e-12 | 31.7184 |
| L1 2 | 4.4275011035767524e-10 | 6.912168825019474e-10 | 2.484667721442722e-10 | 3.8760 |
| L2 0 | 4.819582271948345e-10 | 7.225559142663486e-10 | 2.405976870715141e-10 | 3.7079 |
| L2 1 | 7.847081998678099e-10 | 7.213894799082587e-10 | 6.331871995955121e-11 | 3.7139 |
| L2 2 | 1.878098367329647e-10 | 5.565501049925259e-10 | 3.687402682595612e-10 | 4.8139 |
| L2 3 | 8.849983581104381e-10 | 1.3685760370402963e-09 | 4.835776789298581e-10 | 1.9576 |
| L2 4 | 4.715228565572416e-10 | 3.6033039224789156e-10 | 1.1119246430935002e-10 | 7.4353 |
| L2 5 | 3.713923515542898e-10 | 3.181932348272443e-10 | 5.31991167270455e-11 | 8.4200 |
| L2 6 | 8.333012398847185e-10 | 6.465515870795829e-11 | 7.686460811767602e-10 | 41.4379 |
| L2 7 | 8.732225963310949e-10 | 7.385825905616887e-10 | 1.3464000576940617e-10 | 3.6275 |

The largest absolute deviation is 7.686460811767602e-10 (`L2` index 6, second
pass `A2`,`classification.candidates_all[6].curl_ratio`); the largest relative
deviation is 4116154681362.1177 on `L1` index 0, whose first-pass value is
4.7e-23 and therefore round-off against round-off. On the second pass the
largest member clears threshold one by `T1 / abs(c)` = 1.9576355558275444, so
the margin halves and the verdict is unmoved.

The calibration quantities move less than the members: `m` recomputed on the
amendment-1 candidates is 43125.80549596975, a relative deviation of
2.159548242414843e-14 from the 43125.80549597068 used above, and `g` is taken
from `U1`, which the amendment did not touch. Betas themselves agree between
passes to at most 2.6159701249637554e-14 relative (`L2` index 7) and `beta_sq`
to at most 5.218760125871571e-14. What changed between the passes is the curl
ratio of the returned eigenvector, not the eigenvalue it was returned at — the
same thing `docs/design/deflation_preregistration.md:64` says about the
gradient cluster, that the curl ratios are round-off around a vector that is a
combination of kernel vectors plus round-off.

## 8. The two curl forms disagree, and the disagreement is a result

The frozen rule uses absolute values. The tree's own test at
`emfit/mode2d.py:950-952` is relative to the set maximum, and on this candidate
set the two forms do not agree.

- Relative form: every member is below 2.1835570196393492e-16 of `r_max` at
  level 2 and 3.855614075468485e-17 at level 1, against a floor of `1e-10`. All
  eleven are called curl-free. There is no disagreement inside this form.
- Absolute form at the pre-registered cut of `anchor_preregistration.md:604`:
  nine of the eleven lie above `1e-10` and would be retained as physical; two
  lie below it, `L1` index 0 (4.7037326706944863e-23) and `L1` index 1
  (7.755809876311815e-11, at 0.7755809876311814 of the cut). The cut falls
  inside this one family and therefore does not separate it from anything.

The disagreement is exactly the eight members with `abs(c) > 1.1e-10`: `L1`
index 2 and `L2` indices 0 to 7. `decisions.md:6086-6092` already records the
objection, that "a 1e-10 relative curl floor admits the whole near-gradient
spectrum", and nothing here overrules it.

Three alternative bands, each taken from a document rather than chosen here,
count the members differently:

| band | source | members inside | count |
| --- | --- | --- | --- |
| 1.1e-12 to 4.0e-10 | `docs/design/d45_anchor_results.md:67` | L1 1, L2 2, L2 5 | 3 of 11 |
| 2.6791731109636385e-10 to 6.61052631017697e-09 | `docs/design/deflation_preregistration.md:64` | L1 2, L2 0, L2 1, L2 3, L2 4, L2 5, L2 6, L2 7 | 8 of 11 |
| below 1e-10 (frozen absolute cut) | `anchor_preregistration.md:604` | L1 0, L1 1 | 2 of 11 |

Under the first band three members are curl-free and eight physical; under the
second eight are curl-free and three physical. Applied without a calibration
endpoint, any absolute cut in this range returns `UNDETERMINED` on the frozen
vocabulary, and that is the honest summary of the absolute leg: the family is
separable from the gradient family only because `g` was measured, not because
a fixed floor separates them.

## 9. Sensitivity of the verdict to the frozen decade factor

The frozen factor of 10 (`d48_acceptance.md:172-173`) is what carries the
verdict, and the margin is small relative to it: the largest member is
3.0273198660887313 below `10 * g`. Re-running the first test with a different
factor, keeping everything else fixed:

| factor | band | members above the band | margin `band / max` |
| --- | --- | --- | --- |
| 1 | 2.6791731109636385e-10 | 8 | 0.3027 |
| 2 | 5.358346221927277e-10 | 4 (L2 1, L2 3, L2 6, L2 7) | 0.6055 |
| 3 | 8.037519332890915e-10 | 3 (L2 3, L2 6, L2 7) | 0.9082 |
| 4 | 1.0716692443854554e-09 | 0 | 1.2109 |
| 10 (frozen) | 2.6791731109636385e-09 | 0 | 3.0273 |

So the verdict is stable for any factor of 4 or more and would become
`UNDETERMINED` at a factor of 3 or less. The frozen factor of 10 stands
unaltered and is not renegotiated here; this table records only how much of the
verdict is carried by it. On the amendment-1 pass the margin against the frozen
band is 1.9576355558275444 and the verdict is likewise `SPURIOUS-CURL-FREE`,
so the two passes agree about the sign of the margin and about its order of
magnitude, and neither is anywhere near threshold two.

## 10. Defects in the tree's record, and limits of this result

**(a) A span in the frozen acceptance document is stated too loosely.**
`docs/design/d48_acceptance.md:108-110` says the slab family "spans absolute
values from about 4.7e-23 to 1.37e-9". Measured, the first pass spans
4.7037326706944863e-23 to 8.849983581104381e-10, and 1.37e-9 is the
amendment-1 level-2 value (`A2` index 3, 1.3685760370402963e-09). The upper
figure in that sentence therefore mixes passes. No criterion in that document
depends on it — neither endpoint, neither threshold, and neither test is
defined using the span — and no edit is made here; this is the dated
correction.

**(b) The pre-registration's prose and the record disagree about the gradient
cluster's spread, and this record does not resolve it.**
`docs/design/d45_anchor_results.md:67` gives the level-1 gradient cluster's
absolute curl ratios as spanning 1.1e-12 to 4.0e-10. `U1`, read for this
dispatch, spans 3.5302376941387836e-11 to 2.6791731109636385e-10: narrower
above, wider below, a factor 7.589214503634816 internally rather than the
prose's 364. Both are level-1 statements about eleven members. `g` is taken
from the record and not from the prose, as `d48_acceptance.md:147` directs, and
the counterfactual table in section 8 shows what quoting the prose would have
done. Which of the two is right about the extremes is left open.

**(c) `residual_grad` cannot be reported per candidate.** It is a
subspace-level ratio (`emfit/mode2d.py:1331`, `:1260-1264`), 0.0 at both levels
and at both passes (`D1`, `D2`, `D1a`, `D2a`), and 0.0 by construction because
`Z` is built from the gradient space. No per-candidate value can be derived
from it, and the brief's request for one is answered with `curl_ratio` instead.
This is a fact about the instrument and not a defect in the run.

Beyond these: the result is a statement about `curl_ratio` on returned
eigenvectors at levels 1 and 2 only; level 3 was not run in this dispatch; and
no arithmetic conclusion (whether these eigenvalues approximate a true slab
mode) follows from a small curl ratio in either direction, because a small
curl ratio can mean "in the discrete null space" or "round-off about a
combination of null-space vectors", and the second reading is the one
`deflation_preregistration.md:64` gives for the gradient cluster.

## 11. What is not a discrepancy

`docs/design/d47_results.md:548` speaks of nine frozen values and the frozen
table at `:148-156` has seven measurable rows; the two are not in conflict,
since the difference is exactly the two level-3 values that `:548` records as
unmeasured (`:190-191` states the same in the form of a nine-value requirement
that is FAILED-TO-MEASURE as a whole), and no number in this document depends
on which of the two counts is quoted.

## 12. Disposition and pointers

Nothing was fixed, nothing under `emfit/` was edited, no threshold was changed,
and `docs/design/d48_acceptance.md` stands as written with the correction in
section 10(a) recorded here and there only. The boundary this result draws:
the slab family at `beta = sqrt(eps_r) * k0` is curl-free by the tree's
per-candidate measure at both levels and on both passes, which makes it
eligible for the same structural reading as the gradient family, and it is
*not* curl-free by the frozen absolute cut for nine of its eleven members,
which means the pre-registered filter would keep it. Those two statements are
both true and the record's position is that the second one is the open item,
not the first.

Related material, unaltered here: `decisions.md:8579-8591`, the dispatch-48
decision block, which withdraws the figure 463 as having no provenance in the
tree, states that 483 and 486 are different runs and not a miscount, records
that `.scratch/junit/` double-counts 26 `test_studies` testcases, discharges
the negative control at level 1 only, and carries the `above_endpoint` census
defect forward open; and `docs/design/deflation_v2_preregistration.md`, frozen
as commit `521c34f`, with the slab-region extension of `Z` as commit
`44292b5`. The acceptance criteria this document is measured against are
commit `979c011`.
