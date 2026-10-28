# Dispatch 47 acceptance criteria

These criteria are frozen before any deflated ladder measurement in this dispatch. Every number below is transcribed from a document already committed, and names its source. Nothing here is a new decision.

## A. The nine frozen values

Quoted from section 3 of `docs/design/deflation_preregistration.md`, committed in `d164062`, which reads them from `tools/host/anchor/records/level1.json`, `level2.json` and `level3.json`. The table is reproduced unchanged.

| level | beta | beta^2 | what it is |
| --- | --- | --- | --- |
| 1 | 1736.2570207158685 | 3014588.4419851443 | non-gradient state, the largest beta retained previously |
| 1 | 1636.5986739978343 | 2678455.2197314696 | fundamental |
| 1 | 1296.9723776897456 | 1682137.3484901919 | second mode |
| 1 | 952.9911948312771 | 908192.2174259451 | third mode, filed as surplus |
| 1 | none | -179735.7274530737 | negative eigenvalue in slot 16 |
| 2 | 1296.4632008496378 | 1680816.8311572883 | larger of the two, nearest the analytic second mode |
| 2 | 946.6516295409791 | 896149.3077125911 | smaller of the two, nearest the analytic third mode |
| 3 | 1296.3400089040304 | 1680497.4186853017 | larger of the two, nearest the analytic second mode |
| 3 | 945.1123879493056 | 893237.4258552386 | smaller of the two, nearest the analytic third mode |

Five entries at level 1, two at level 2, two at level 3. The fifth level-1 entry carries no beta, so the beta form of the rule in section 3.b binds on the eight entries that carry one.

The analytic values of section 3, tagged [RELAYED] there and used only to name entries rather than to test anything: 1637.9985692980779 for the fundamental, 1296.2992799512633 for the second mode and 944.6029788248537 for the third.

## B. The three results this dispatch reports

1. Value-matched spectrum preservation. Each of the nine values must reappear among the returned eigenpairs after deflation, satisfying

       |beta^2_def - beta^2_frozen| / max(1, |beta^2_frozen|) <= 1e-12

   written on beta^2, and the same inequality written on beta. Every match and every miss is named. The value 1e-12 is fixed before the run and is not adjustable afterwards, per section 3.b of the pre-registration.
2. Fundamental presence. The fundamental's beta^2 at each of levels 1, 2 and 3, set against the frozen value 2678455.2197314696 and the analytic value 1637.9985692980779. Presence is mandatory at every level, which is inherited and not a new requirement.
3. By-order comparison against the analytic ladder, with per-mode relative error and level-to-level ratios, labelled indicative. No order estimate is formed as a verdict in this dispatch.

Two further numbers accompany result 1, mandated by section 3.c of the pre-registration: the built dimension of `Z` against the structural count of section 2.a, and the residual ratios of section 2.d. Section 3.c records why they are necessary, namely that a strict subspace `Z` is an under-removal which leaves every frozen value in place and passes result 1 while the cluster has not been removed in full.

The full sorted beta^2 spectrum at each of levels 1, 2 and 3 is reported alongside these three results, rather than only the per-value differences.

## C. Inherited criteria, unchanged and not applied here

Quoted verbatim from section A of `docs/design/d46_acceptance.md`:

- The full acceptance criterion inherited from the anchor v1 + v2, unchanged: order band 1.7-2.3, absolute error bound at the finest mesh, by-order matching across all five levels, and the fundamental must be present at every level. Plus the two obligations deferred from v1 and never run: the mixed-path gate and the negative control.

Quoted verbatim from section B of the same file, which quotes section 6 of `docs/design/d45_anchor_results.md` as committed in `61bd071`:

- "the order band 1.7 to 2.3, the absolute bound 2.0e-3 at the finest level, monotonicity, the requested candidate count of 16, the ladder geometry and the material parameters are all as frozen in v1"

No threshold in this section is altered by this dispatch, and none of them is reachable from levels 1, 2 and 3 alone.

## D. Verdict vocabulary

PASS, FAIL and FAILED-TO-MEASURE, per section 5 of the pre-registration. FAILED-TO-MEASURE is quoted from section A of `docs/design/d46_acceptance.md` as meaning the apparatus could not resolve the modes, and it requires the same diagnostic treatment this one received. Section 5.a forbids relaxing the criterion after the fact and section 5.b fixes the amendment route.

## E. Scope

Levels 1, 2 and 3 only, which is 78, 348 and 1464 free degrees of freedom. Levels 4 and 5 are outside the scope of this dispatch and no number from them is reported. No verdict on the section 4 acceptance criterion can be formed from levels 1 to 3, and none is formed here.

## F. The two deferred obligations

Both remain unrun, per section 8 of `docs/design/d45_anchor_results.md`, which records the mixed-path and negative-control steps as NOT RUN and as outstanding obligations.

The negative control's perturbation, its expected direction of movement and its recording format are defined in section 6 of `docs/design/anchor_preregistration.md` and in section 3.6 of `docs/design/d45_acceptance.md`. This dispatch reads them there before running the control. A provenance correction is recorded: the dispatch brief for this work pointed at `docs/design/d45_anchor_results.md` for that definition, but that file contains the phrase only as a hyphenated mention of the step in section 8 and does not define the control.

## G. Provenance

The frozen values of section A are tagged [VERIFIED this session] in the pre-registration and are copied here digit for digit. The analytic values of section A are tagged [RELAYED]. The inheritance chain of section C is quoted, not paraphrased. The scope of section E is [USER], set by the dispatch and not a property of the code.
