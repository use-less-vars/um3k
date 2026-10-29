# Preservation gate: the contrast series at `eps_r` = 1.5, 2.0 and 3.5

**Verdicts of record.** The registered A-3.5 run over levels 1-3 issued `STOPPED` at level 1 and no verdict on any falsifier. The supplementary A-3.5 run over levels 2-3 only issued `FAILED-TO-MEASURE`. A re-run of geometry A through the same launcher issued `PASS`. The substantive measurement this dispatch produces is that **the over-removal residual is not a single power law in contrast**: the local log-log slope falls from 0.888 over `c` in [0.5, 1] to 0.743 over `c` in [1, 2.5].

Throughout, `c = eps_r - 1` with `mu_r = 1`, so the three geometries are `c = 0.5`, `c = 1.0` and `c = 2.5`. "Order" in every table below is the rank of an analytic mode counted from the highest; `e_k` is the relative error of that mode at ladder level `k`; `p_k` is the observed rate `log2(e_k / e_{k+1})`.

## 1. Records

All three runs used the frozen gate `tools/host/anchor/preservation_gate.py`, sha256 `7a0c04b2efbe9fefd2e5a2f7ccbfba3ca8500cb9506cda40e789201396dd2d1b`, which this dispatch did not modify; it was re-hashed after the final run and the hash is unchanged. All three used the launcher `tools/host/anchor/preservation_gate_a35.py`, 260 lines, sha256 `74ef97e46adea9f3086b6eb9b4363b78503e5c045907eca7636dfa26ef9b4d6b`. That launcher is generic over `--eps-r`; the `a35` in its name records the dispatch that froze it, not a constraint, and it produced all three records below.

| run | record | sha256 | verdict |
|---|---|---|---|
| A-3.5, levels 1-3 | `.scratch/d51/pg_a35.json` | `264de00884dd163c8d3d6f2048c032e2f091b6d8cf05666b4980feb4b033bced` | `STOPPED` |
| A-3.5, levels 2-3 | `.scratch/d51/pg_a35_l23.json` | `b64d0d4eee36e12c1293ff12fa85d4e60960ae3cc7871d3a03a4471ad2833956` | `FAILED-TO-MEASURE` |
| A, levels 1-3 | `.scratch/d51/pg_a20.json` | `f2bd1ffd0f8c4117094244eb740c59688b69568f7de55bbef3a49413d00745bd` | `PASS` |

Companion files. A-3.5 levels 1-3: log `.scratch/d51/pg_a35.log`, 45 lines, sha256 `ff8ec0d4f2521333d763129aeac07abd25199af2632404912f93c79b5ada126a`; clusters `.scratch/d51/pg_a35_clusters.json`, sha256 `6a0a53180aaa275773ae4fb491f5fb50b5aa70c730e0d612ca8f7b67bdeb7d27`, overall `VACUOUS`. A-3.5 levels 2-3: log sha256 `e291ff3f3a369e7c693badf4409530edf093365121f49f8b56c6d5cfdb6a7ca3`; clusters sha256 `f146e1321f761940e924a4dd8c443ea0d71a06b00c5299709c8a36fc24ca992c`, overall `SAFE`. A: log sha256 `0053fbe5ac60ecf58056d0262cff7fe8252cd093d0073545c3176c20e93f9c15`; clusters sha256 `778ba296dea186ddd083b2dfe420204d4e3d83b39a3b163640e44dbf284c11fd`, overall `SAFE`.

## 2. The registered run: `STOPPED` at level 1

The run halted at level 1 and issued no verdict on falsifiers F1 to F4. Its recorded reason is: `gate section 8: root unpaired at level 1 (possible annihilation); run stopped, no verdict issued`.

Level 1 is a healthy mesh: `ny = 16`, `nx = 2`, `h = 4.8828125e-04`, 51 nodes, 114 edges, 64 triangles, `n_free = 78`. The eigensolve did not struggle: `n_converged = 16` against `k_candidates = 16`, `arpack_budget_factor = 40`, `aborted = false`, `abort_error = null`, wall time 0.0691 s. Four analytic roots were frozen for this contrast, in descending order 2294.5823384403725, 1338.0519914416536, 1131.3902369039729 and 643.89201636736937, in the window [0, 3949.600488469103]. The route-3 proximity test passed: minimum 0.18266177999131986 at pair 2.

Of the 16 converged candidates, only 5 carry a real `beta`; candidates 5 to 15 have `beta_sq < 0` and report `beta` as null. The gate's pairing population is that real-beta subset: 2289.467585297626, 2173.7273558214615, 1346.7440247643376, 1156.680714912759 and 689.595395464334. Pairing each frozen root to its nearest real-beta candidate, with the relative distance taken over the root, reproduces the record's own `nearest_any_rel` fields exactly:

| order | relative distance | against `PAIR_TOL = 2e-2` |
|---|---|---|
| 1 | 0.002229056267479 | within |
| 2 | 0.006496035563849 | within |
| 3 | 0.022353452578832 | **unpaired**, 1.118x tolerance |
| 4 | 0.070979881618673 | **unpaired**, 3.55x tolerance |

The record's summary flags are `B4_monotonic = true`, `B5_unpaired_orders = [3, 4]` and `B6_surplus = 3`. Its deflation block reports `column_region = v1+homogeneous-blocks`, `residual_pencil = 0.008218934803669066`, `z_dim = 14` and `residual_eps_mu = 0.05592958825659055`. The level-1 cluster census found no group of two or more and is therefore safe, vacuously.

**The cause is discretisation, not annihilation.** The two unpaired orders do not shrink towards the tolerance as the mesh refines; they shrink the way a second-order scheme shrinks. Projecting the measured per-level contraction, the order-3 relative error would be 2.235 % at `ny = 16`, 0.49 % at `ny = 32` and 0.12 % at `ny = 64`, ratios 4.56 and 4.02; order 4 gives 7.098 %, 1.868 % and 0.473 %, ratios 3.80 and 3.95. Both are clean second-order sequences. Two consequences follow. First, nothing in this record is evidence of a mode disappearing; the level-1 mesh is simply too coarse to place a 2.2 % error inside a 2 % band. Second, the four-root decision did not cause the stop: order 3 alone misses by 1.118x, so the run would have stopped at level 1 on three roots as well. What failed is the inherited, `h`-independent `PAIR_TOL` being applied at contrast 2.5 on the coarsest rung, where it is an annihilation detector sitting inside the discretisation error of the scheme it is inspecting.

## 3. The supplementary run: `FAILED-TO-MEASURE` over levels 2-3

Re-running the same contrast from level 2 recovers the upper two rungs. All four frozen roots pair at both levels: `B5_unpaired_orders = []` and `B4_monotonic = true` at levels 2 and 3. Real-beta candidates number 7 of 16 at level 2 and 11 of 16 at level 3. Wall time was 0.705 s at level 2 and about 27.9 s at level 3.

| order | `e_2` | `e_3` | `p_2` |
|---|---|---|---|
| 1 | 5.941755e-04 | 1.510454e-04 | 1.9759 |
| 2 | 1.424367e-03 | 3.452624e-04 | 2.0446 |
| 3 | 5.504124e-03 | 1.369252e-03 | 2.0071 |
| 4 | 1.868269e-02 | 4.730912e-03 | 1.9815 |

Every observed rate lies inside the registered band [1.7, 2.3], and the third-level error bound `e_3 <= 5e-3` holds on all four orders, worst 4.730912e-03 at order 4 = 0.95x the bound. The run nonetheless reports `FAILED-TO-MEASURE`, and it is right to: `e_1` does not exist in a run that begins at level 2, so the gate's first-level condition P1, which requires all three level errors to exist and to satisfy e_1 greater than e_2 greater than e_3 strictly, on every root of the frozen set cannot be evaluated, and a condition that cannot be evaluated cannot be passed.

`residual_eps_mu` is 2.669736e-2 at level 2 and 1.305656e-2 at level 3, a ratio of 2.0447, with `n_free` 348 and 1464. The cluster census is safe at both levels: a group of size 2 at level 2 spanning `eps_eff` [2.2673373905, 2.28414171516] with a nearest approach of 0.072987131529, and a group of size 6 at level 3 spanning [2.25370768609, 2.28542752758] with nearest approach 0.0727262464563, both about 3.6x `PAIR_TOL` and neither close to the pairing band.

**A defect in the frozen module's text.** The `FAILED-TO-MEASURE` reason string states that a P1/P2 violation is explained by a recorded pairing rejection. Neither half is true of this run. No pairing was rejected: `B5_unpaired_orders` is empty at both levels. And P2 is in band on all four orders. The only unevaluable condition is P1, and it is unevaluable because the run was configured to start at level 2, which the string does not say. The verdict itself is correct; the sentence explaining it is not, and it is frozen, so it is recorded here rather than edited.

## 4. Geometry A re-run through the same launcher: `PASS`

Run for two reasons: to confirm that the `a35` launcher reproduces a configuration whose behaviour is already known, and to put geometry A's residuals on the same footing as the other two contrasts, since the dispatch 50 figures were carried across from an earlier record. Exit code 0, under 100 s.

Analytic roots in descending order 1637.9985692980779, 1296.2992799512633 and 944.60297882485361, in a window topped at 2985.6173344424224 against an endpoint of 1990.4115562949482. Route-3 minimum 0.26359598792623057 at pair 1.

| order | `e_1` | `e_2` | `e_3` | `p_1` | `p_2` |
|---|---|---|---|---|---|
| 1 | 8.546377e-04 | 2.126525e-04 | 5.309906e-05 | 2.0068 | 2.0017 |
| 2 | 5.192456e-04 | 1.264530e-04 | 3.141941e-05 | 2.0378 | 2.0089 |
| 3 | 8.880150e-03 | 2.168796e-03 | 5.392838e-04 | 2.0337 | 2.0078 |

All three per-order conditions hold. Real-beta candidates number 4, 6 and 10 of 16 across the three levels; surplus 1, 3 and 7; `B5_unpaired_orders` is empty at every level; `residual_series.anomaly = false`.

This run is also a reproduction check, and it passes. `decisions.md:8594` and the dispatch 50 record quote geometry A's residuals as 2.8203e-2, 1.3526e-2 and 6.6275e-3; this run measures 2.820305e-2, 1.352610e-2 and 6.627469e-3, and the level-1 order-1 pairing distance 8.546377e-04 against the 0.000854637681914113 recorded for the negative control. The earlier numbers were not re-derived by hand into this document; they were re-measured independently through the same frozen gate, and they agree.

The cluster census is safe. Level 1 vacuous; level 2 a group of size 2 spanning `eps_eff` [1.50277439068, 1.50546559989] with nearest approach 0.0533222577138; level 3 a group of size 6 spanning [1.50059323415, 1.50567213658] with nearest approach 0.0525575737447. The paired `curl_ratio` triples are 785938.0821 / 394355.4699 / 1282546.6726 at level 1, 792010.2828 / 393673.6817 / 1286133.3998 at level 2 and 793578.7889 / 393544.3493 / 1287190.5355 at level 3.

## 5. The three-contrast series

| level | A-1.5, `c = 0.5` | A, `c = 1.0` | A-3.5, `c = 2.5` |
|---|---|---|---|
| 1 | 1.521622e-2 | 2.820305e-2 | 5.592959e-2 |
| 2 | 7.311272e-3 | 1.352610e-2 | 2.669736e-2 |
| 3 | 3.585053e-3 | 6.627469e-3 | 1.305656e-2 |

The A-1.5 column is `.scratch/d50/pg_a15.json`, 892 lines, verdict `PASS`, all per-order conditions holding on all three orders and `B5_unpaired_orders` empty at every level. **The A-3.5 column is a composed series and is labelled as one.** Its level-1 entry comes from the `STOPPED` registered record and its level-2 and level-3 entries from the separate levels-2-3 record, which was a different process with a different prefix of the ladder. The two records share the geodesic, the frozen roots and the frozen gate; what they do not share is a single run, and no single run ever produced A-3.5 at all three levels. The composition is legitimate for the purpose it is used for below, which is reading off how the residual varies with contrast at fixed level, but it is not a single run and must not be cited as one.

Both mesh ratios behave: A-1.5 falls 2.0812 and 2.0394 per level, A falls 2.0851 and 2.0409, A-3.5 falls 2.0447 between levels 2 and 3.

## 6. Exponents: not a power law

Three readings of the contrast dependence, each taken level by level, each computed independently twice and agreeing:

| chain | contrast ratio | level 1 | level 2 | level 3 | mean | spread |
|---|---|---|---|---|---|---|
| A / A-1.5 | 2 | 0.890241 | 0.887552 | 0.886463 | 0.888086 | 0.003778 |
| A-3.5 / A | 2.5 | 0.747212 | 0.742061 | 0.740014 | 0.743095 | 0.007198 |
| A-3.5 / A-1.5 | 5 | 0.808811 | 0.804720 | 0.803086 | 0.805539 | 0.005725 |

If the residual were a single power law in contrast, all three rows would carry the same exponent. They do not. The local log-log slope is 0.888 over `c` in [0.5, 1] and 0.743 over `c` in [1, 2.5]; the third row, which spans the whole range, sits between them at 0.806 because it is a chord across a curve. The difference between adjacent slopes is -0.143029, -0.145491 and -0.146449 at levels 1, 2 and 3: a curvature of about -0.145 that is independent of the mesh to three significant figures.

So the dependence on contrast decelerates, and it decelerates by the same amount at every level. The other half of the same statement is that the factorisation holds: the per-level spread of the exponent is at most 0.0072 under the A-3.5-anchored readings and 0.0038 under the A/A-1.5 reading, so contrast and mesh separate well over this range. A model of the form `g(c) * phi(h)` is adequate; a model of the form `c^p * phi(h)` is not, because `p` is not one number.

No extrapolation is offered from three contrasts. Four points, one of them the reference, is enough to show that a line does not fit, and not enough to identify what does.

## 7. The four falsifiers: unassessable as registered

The registered run stopped at level 1 and issued no verdict, so there is no registered verdict on F1 to F4, and nothing in this section is one. What follows evaluates them against the composed series of section 5, which is a weaker object than the run they were registered for.

F2 does not fire. The registered bound is 1e-1 on `residual_eps_mu` at contrast 2.5, the measured level-1 value is 5.592959e-2, and the pre-registration's own equivalent band for it was [5.088e-2, 8.244e-2], which also contains the measurement.

F3 does not fire. The residual is strictly increasing in contrast at every level: 0.0152 < 0.0282 < 0.0559, 0.00731 < 0.01353 < 0.02670, 0.00359 < 0.00663 < 0.01306.

F4 does not fire. The registered span bound is 0.15; the measured per-level spans are 0.005725 and 0.007198 under the two A-3.5-anchored readings, and 0.003778 under the A/A-1.5 reading. All are more than an order of magnitude inside the bound.

F1 splits by estimator, and the pre-registration does not say which estimator it means. Under the A-1.5-anchored reading, the exponent is the base-5 one and the level-3 value is 0.803086, inside the registered band [0.75, 1.05]; F1 does not fire. Under the A-anchored reading, it is the base-2.5 one and the level-3 value is 0.740014, which is outside the band by 0.009986, one per cent of the band's width; F1 fires. Both readings are defensible against the frozen text and the two disagree on the outcome, so the honest report is that F1 is indeterminate rather than that it passes or fails. Choosing the reading that gives the preferred answer would be exactly the defect that section 8 describes.

## 8. Defects in the pre-registration and in the frozen module

Recorded, not patched. Each is a disagreement with a document this dispatch itself froze.

**D1. F1 is vacuous under its own derivation.** Section 2 defines the exponent as `log2(residual_A / residual_A-1.5)` and then registers `p_3`. That estimator reads no A-3.5 datum at all, so it returns 0.886463 whatever the A-3.5 run does. Only the following line, which writes the equivalent prediction as `1.521622e-2 * 5^p`, pins `p` as the base-5 exponent, and that is the reading under which F1 is a test rather than a restatement of an earlier measurement.

**D2. The band is not centred where the text says.** Section 2 states a tolerance of plus or minus 0.15 about 0.8880, whose band would be [0.738, 1.038]. The band actually registered is [0.75, 1.05], which is plus or minus 0.15 about 0.90. The difference is small and is not the reason for anything in this document, but the two statements are not the same statement.

**D3. A level-3 exponent is mapped onto a level-1 residual.** Section 2's equivalent prediction constrains `residual_L1` to [5.088e-2, 8.244e-2] using an exponent measured at level 3. That step presumes the level-independence of the exponent, which F4 is registered separately to test. The internally consistent level-3 equivalent, using the level-3 A-1.5 residual 3.585053e-3, is [1.199e-2, 1.943e-2].

**D4. There is no clause for a level-1 pairing stop.** Section 5 covers only a scenario in which P1 or P2 is unmeetable, and section 7 makes annihilation a stop. A pairing rejection at the coarsest rung produced by discretisation error is neither, so the registered text has no disposition for the event that actually occurred, and the run fell back on the annihilation branch. That branch exists to stop a run when a mode has disappeared; here it stopped a run in which, as section 2 shows, no mode had disappeared.

**D5. The launcher's name is narrower than its behaviour.** `preservation_gate_a35.py` is fully parameterised over `--eps-r` and produced all three records in section 1. The name records the dispatch, and was left alone rather than renamed mid-sequence, but a reader should not infer a constraint from it.

**D6. The frozen module's `FAILED-TO-MEASURE` reason string misdescribes a levels-2-onward configuration.** Detailed at the end of section 3: it attributes the outcome to a pairing rejection that did not occur and to a P2 violation that did not occur, and does not mention the actual cause, which is the absence of level 1.

**D7. `PAIR_TOL` is independent of `h` and is therefore not a valid annihilation test at every contrast.** The level-1 discretisation error at order 3 grows with contrast and reaches 2.235 % at contrast 2.5, which is 1.118x a fixed 2 % band. The rule cannot distinguish a physical disappearance from a mesh artefact on the coarsest rung, and at contrast 2.5 it reports the artefact as the disappearance. This is the frozen gate behaving as written; the defect is in the rule, and it is the reason this contrast has no registered verdict.

## 9. What this establishes and what it does not

Established. The over-removal residual grows with contrast, monotonically, at every level, and the growth is sub-power-law: a local exponent of 0.888 over `c` in [0.5, 1] and 0.743 over `c` in [1, 2.5], with the curvature about -0.145 independent of the mesh. Contrast and mesh dependence factorise, to within an exponent spread of 0.0072. No mode was destroyed at any contrast: the only annihilation signal in the record is a second-order discretisation error at `ny = 16`, in a run whose eigensolve converged 16 of 16 candidates without aborting.

Not established. Nothing here is a verdict on the four registered falsifiers, because the registered run stopped. Nothing here is evidence that the widened deflation is harmless: a residual of 5.6e-2 at contrast 2.5, some eight orders above the round-off prediction for an exactly removed null space, is large, and the fact that it does not blow up superlinearly over the measured range is not a bound on what it does at larger contrast. Nothing here identifies the function `g(c)`; three contrasts constrain a shape and do not determine it. And nothing here addresses whether the residual corrupts the extracted physical modes, which is the question the gate's own P1 to P3 conditions were meant to answer and which they answered only at contrasts 0.5 and 1.0.

## 10. Forward pointer

Two things are owed before this contrast can be called measured. Either the gate gains an `h`-dependent pairing tolerance, derived from the scheme's order and stated as a formula rather than a constant, or the contrast-2.5 configuration is gated from level 2 outward with the level-1 absence declared in the pre-registration rather than discovered by the module. The first is the better repair, because the second leaves the coarsest rung ungated and the coarsest rung is where an annihilation signal would be largest. Either way the next pre-registration on this line must carry a feasibility argument for its pairing tolerance at the contrast it is registered for, in the sense of the standing rule that no numeric bound is admissible without one.
