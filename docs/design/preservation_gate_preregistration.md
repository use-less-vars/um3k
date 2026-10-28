# The preservation gate, pre-registered

**Status: frozen.** This file was written and committed before any run of the geometry it governs. It may not be amended after seeing a result. An amendment made after a run is void as authored, by construction, because the whole point of the previous failure was an amendment authored after a result.

**Provenance.** `[USER]` supplied in the dispatch 50 brief; `[RELAYED]` carried from the dispatch 49 record and not re-measured here; `[VERIFIED]` re-measured in this dispatch by a named command. Untagged numbers are `[RELAYED]`.

## 1. Why there is a new gate

Amendment 3 of `docs/design/deflation_preregistration.md` added a widened-preservation clause requiring the finite-mesh solver to reproduce an analytic root to `1e-12`. It is void as authored: unsatisfiable by 7.8 to 10.3 orders on this ladder, and internally contradictory with frozen section 3, which states that the analytic values are not a comparison target here. The recording is `decisions.md`, dispatch 50 Task 1.

The measurements taken against that clause are diagnostic evidence and nothing else. They are not a pass and not a fail and may not be cited as either. This file replaces the clause with a statistic that can be met, and states before the run what precision is reachable and why.

## 2. The quantities, defined

`beta_ref` — an analytic root, in rad/m, from `tools/host/anchor/anchor_reference.py::solve_ref`, called as `solve_ref(t, eps_r=..., b=..., k0=...)`. The routine is validated and fully parameterised; the geometry is carried entirely by these arguments.

`beta_k` — the discrete candidate paired to `beta_ref` at ladder level k, by the pairing rule of `docs/design/deflation_v2_preregistration.md` section 3.b, clauses B1 to B6, unchanged. Levels k = 1, 2, 3 only; levels 4 and 5 are unreachable through the dense complement, whose cap `_DEFLATED_DENSE_MAX = 6000` free degrees of freedom is unchanged by fence.

`e_k` — the paired relative error against the analytic root:

```
e_k = |beta_k - beta_ref| / |beta_ref|
```

**`e_k` is measured on `beta`, never on `beta_sq`.** This is a defined term because the two differ by a factor of two at leading order and the difference has already produced a false reading. The Amendment 3 cells — 1.7839e-2, 1.0388e-3 and 1.7085e-3 at level 1, for the roots 892274.78760478646, 1680391.8232021632 and 2683039.3130225502 — are relative errors in `beta_sq`. The identification-table cells — 8.8801e-3, 5.1925e-4 and 8.5464e-4 at level 1 — are relative errors in `beta`, for the same three roots after the square root. Each Amendment 3 cell is twice its counterpart to the digits recorded, which reconciles the two records and confirms the factor. A figure quoted without saying which base it is on is ambiguous and must not be compared with either.

`p_k` — the observed order across one level step:

```
p_k = log2(e_k / e_{k+1}),  k = 1, 2
```

Three levels give two values of `p` per root, and `e_k / e_{k+1} = 2**p_k`.

## 3. The statistic and the pass conditions

The gate is a convergence test, not an agreement test. For every root in the frozen set of section 5:

- **P1, monotone.** `e_1 > e_2 > e_3`, strictly. A statistic that does not fall with level is not converging, whatever its magnitude.
- **P2, order.** `1.7 <= p_1 <= 2.3` and `1.7 <= p_2 <= 2.3`, equivalently `e_k / e_{k+1}` in `[3.2490, 4.9246]`. This is frozen section 4's order band, tested on the order itself. The band was written for the order, so applying it directly to a ratio of errors would be a category error; the translation is stated here so that it cannot be made later.
- **P3, supporting only and not sufficient.** `e_3 <= 5e-3`, with its feasibility argued in section 4. Failing P3 while passing P1 and P2 is reported as an anomaly and is not a gate failure. Passing P3 while failing P1 or P2 is a gate failure, because a single level can be lucky and a rate cannot.

PASS requires P1 and P2 for every root. FAIL requires some root to violate P1 or P2 where no recorded pairing rejection explains the violation. FAILED-TO-MEASURE is section 10.

## 4. Feasibility argument

Required by the standing rule adopted in `decisions.md` dispatch 50 Task 1: no numeric bound without an argument for what precision is reachable on the proposed meshes, and why.

Measured on geometry A, `t = b/4`, `eps_r = 2`, which is the reference geometry this gate is calibrated on:

| root | e_1 | e_2 | e_3 | p_1 | p_2 |
| --- | --- | --- | --- | --- | --- |
| order 1, `beta_ref = 1637.9985692980779` | 8.5464e-4 | 2.1265e-4 | 5.3099e-5 | 2.0068 | 2.0017 |
| order 2, `beta_ref = 1296.2992799512631` | 5.1925e-4 | 1.2645e-4 | 3.1419e-5 | 2.0378 | 2.0087 |
| order 3, `beta_ref = 944.60297882485338` | 8.8801e-3 | 2.1688e-3 | 5.3928e-4 | 2.0337 | 2.0078 |

Six order estimates, range 2.0017 to 2.0378. Against the band `[1.7, 2.3]` that is a margin of 0.30 at the lower edge and 0.26 at the upper.

**What is reachable, and why.** The statistic is discretisation-limited at every level that is run. The three levels above give `e_3` between 5.31e-5 and 5.39e-4, while the same solver reproduces the nine frozen discrete rows of section 3 of the deflation pre-registration to at most 3.623e-14 relative in `beta_sq`, which is 1.8e-14 in `beta` and is the arithmetic floor for a discrete-to-discrete comparison. Extrapolating the measured order, that floor is reached only about sixteen levels above level 3. No level in 1 to 3 is floor-limited, so `p_k` cannot be corrupted by round-off, and an order measured at these levels is a real measurement rather than a ratio of noise.

**Why 5e-3 and not 1e-12.** The occupied region on the evidence is `e_3` in `[5.31e-5, 5.39e-4]`. The failure signature — a removal that eats or displaces a physical mode, or a mis-pairing — shows `e` of order 1e-1 to 1, because it is a change of identity and not a loss of digits. The band between 5.4e-4 and 1e-1 is unoccupied. Any bound inside it is equally defensible, and 5e-3 is chosen because it sits inside it with 9.3 to 94 times headroom to the observed worst `e_3` and two decades of clear air to the failure signature. A bound of `1e-12` would require about seventeen further levels above level 1, six times the length of the ladder, and is unreachable by construction. Choosing it is the error this section exists to prevent.

**Expectation stated before the run.** On a geometry of this class I expect P1 and P2 to hold for every root in the frozen set, and P3 to hold with the headroom above. If the second geometry goes otherwise on P2, that is a result and is reported as one; the gate is not renegotiated in response to it.

## 5. The frozen analytic set

The widened set is every analytic root the validated reference routine returns inside the census window `[0, 2985.617334442422]` in `beta`, which is `[0, 1.5 * ENDPOINT]` with `ENDPOINT = 1990.411556294948`. The set does not belong to this file: it is established, printed and committed in the geometry freeze that immediately precedes a run, with the exact `solve_ref` call and the returned list verbatim, before any discrete solve of that geometry is executed. This file fixes the rule by which the set is established and the statistic by which it is judged; the set itself is per-geometry data.

Two consequences are pre-registered so that neither is discovered later and argued about:

- The reference routine may return roots above `ENDPOINT`. They are inside the window and are therefore inside the set. The gate tests them. The open `above_endpoint` census defect, which concerns retained candidates rather than analytic roots, is neither exercised nor repaired here.
- The set is not the nine frozen rows of section 3 of the deflation pre-registration. Those rows are a discrete-to-discrete check and remain a separate instrument check. Nothing in this file relaxes, extends or reinterprets them.

## 6. Pairing, inherited unchanged

All six clauses B1 to B6 and both prohibitions of section 3.b of `docs/design/deflation_v2_preregistration.md` apply unchanged, at every level, with `PAIR_TOL = 2e-2`. The two prohibitions are restated because they bind this gate: pairing may not consult `curl_ratio` or `eps_eff`, and pairing at one level may not use another level's pairing.

The five mis-pairing routes of section 3.c are re-audited on each new geometry before any verdict is issued. Route 3 in particular cannot be inherited: its check, `min_k |beta_ref[k] - beta_ref[k+1]| / beta_ref[k+1]` against `0.04`, depends on the spectrum and therefore on the geometry, so geometry A's measured 0.2636 and 0.3723 say nothing about another geometry and must be recomputed there.

`curl_ratio` is a mode-purity diagnostic and is now stored per candidate, through `emfit/mode2d.py::candidate_records` added in dispatch 50 Task 2. It is reported for the paired candidates as diagnostic context. It is not a term of this gate.

## 7. The over-removal guard: reported, not gated

`residual_eps_mu` is reported at every level, with its level-to-level ratio, for every geometry.

Measured on geometry A: 2.8203e-2, 1.3526e-2 and 6.6275e-3 at levels 1, 2 and 3. The ratios are 2.085 and 2.041 — **first order**, where the eigenpair converges at second. That mismatch is the signature of a systematic remainder rather than a vanishing one, and it is the measured cause of the over-removal finding recorded in `decisions.md` dispatch 50 Task 1.

It is a diagnostic and not a pass condition, for a stated reason. `residual_eps_mu` measures how much the retained physical subspace is disturbed by construction, and a heuristic removal may disturb it at a level that does not shrink. Binding the verdict to it would reintroduce exactly the defect this file replaces: a bound whose reachable value was never argued. What is informative is `residual_eps_mu` failing to decay at all, or growing with level; that is reported as an anomaly in the same paragraph as the verdict, and does not by itself change the verdict.

## 8. The annihilation stop rule

If any root in the frozen set has no paired discrete candidate at any level after the B1 to B6 exhaustion, that is recorded as a **possible annihilation** and the run stops there. No further level is solved, no verdict is computed, and the supervisor is told immediately, with the level, the root, the candidate set and the nearest distance. This is the catastrophe named in Amendment 2 section 1, and it is the one outcome that is never averaged into a verdict.

A root that is unpaired at every level is treated as a stop even when its nearest candidate distance is inside `PAIR_TOL`, because the difference between a mode that is gone and a pairing rule that lost it cannot be established safely inside a single run.

## 9. What this gate does not test

Stated so that a PASS cannot be read as more than it is:

- It does not prove the removed subspace is non-physical. It tests that the physical spectrum survives on the geometries actually run, and generalisation beyond them is an inference, not a measurement.
- It does not test mode purity. `curl_ratio` is reported and not gated; mode purity is row four of the C++ criterion table and remains UNMEASURED.
- It does not test passivity.
- It does not test levels 4 or 5, which the dense complement cannot reach.
- It does not repair the `above_endpoint` census defect.
- It does not establish that over-removal is absent. It establishes at most that over-removal does not corrupt the identified modes, at these levels, on these geometries.
- It says nothing about the physical status of the `eps_eff` cluster near 1.5. It records only that the cluster cannot enter the 2 per cent pairing band, at a margin of about 5.25e-2, which is 2.6 times `PAIR_TOL`.
- It does not discharge the five-level criterion of frozen section 4, which remains undischargeable for the cost reason already recorded.

## 10. Verdicts

**PASS** — P1 and P2 hold for every root in the frozen set.

**FAIL** — some root violates P1 or P2, and no recorded pairing rejection explains the violation.

**FAILED-TO-MEASURE** — fewer than three roots in the frozen set; fewer than three levels solved; a root unpaired under section 8; or a level whose solve aborted. **FAILED-TO-MEASURE is not a soft outcome.** Every diagnostic table required for a PASS is produced for it as well: the `e_k` table wherever it is measurable, the pairing audit, `residual_eps_mu` at every level, and the `curl_ratio` of the paired candidates. A FAILED-TO-MEASURE reported without those tables is not a report.

## 11. Freeze

This file is committed before the second geometry is solved. The geometry freeze — the frozen analytic set of section 5 together with the exact `solve_ref` call that produced it — and the adjudicating script are committed before any discrete solve of that geometry is executed, so that neither the set nor the statistic can be adjusted to the data afterwards. The commit hash of the freeze is the only admissible reference to this gate; a later version of this file governs nothing that has already been run.
