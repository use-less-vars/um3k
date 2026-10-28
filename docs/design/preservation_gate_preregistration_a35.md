# Pre-registration — preservation gate at contrast 2.5 (geometry A-3.5)

Dispatch 51, task 2. Frozen before any discrete solve at `eps_r = 3.5`.

## 1. Purpose and position in the sequence

Dispatch 51 measures the deflation-block residual `residual_eps_mu` at a third
permittivity contrast and asks whether its growth with contrast is a power law.
Contrast is `c = eps_r - 1` (vacuum background, `mu_r = 1`), giving

| geometry | `eps_r` | contrast `c` | status |
|---|---|---|---|
| A-1.5 | 1.5 | 0.5 | measured (`.scratch/d50/pg_a15.json`) |
| A | 2.0 | 1.0 | measured (dispatch 49) |
| A-3.5 | 3.5 | 2.5 | **this dispatch** |

Two contrasts are already measured. Their ratio fixes a two-point exponent
`p = log2(residual_A / residual_A-1.5)`. A-3.5 supplies the third point, and it
is the point that tests the power law rather than deriving it.

## 2. Predictive band (registered, not fitted)

The two-point exponent is recomputed here from the JSON records rather than
taken from the dispatch text:

| level | residual A-1.5 | residual A | ratio A/A-1.5 | `p = log2(ratio)` |
|---|---|---|---|---|
| 1 | 1.521622e-2 | 2.8203e-2 | 1.853483 | 0.8903 |
| 2 | 7.311272e-3 | 1.3526e-2 | 1.850027 | 0.8873 |
| 3 | 3.585053e-3 | 6.6275e-3 | 1.848683 | 0.8863 |

mean `p = 0.8880`, spread `0.004` across levels. The dispatch's `~0.90` refines
to `0.8880`, and the exponent is not exactly level-independent — the
factorisation below is therefore registered as approximate, not exact.

**Registered band, level 3: `p_3` in `[0.75, 1.05]`** — `+/- 0.15` about 0.8880,
widened symmetrically rather than centred on the value under test.

Expressed as a prediction for the level-1 residual, using
`residual_L1(A-3.5) = 1.521622e-2 * 5^p` (contrast ratio `2.5/0.5 = 5`):

- `p = 0.75` -> `5.088e-2`
- `p = 0.888` -> `6.353e-2` (point prediction)
- `p = 1.05` -> `8.244e-2`

so the registered equivalent prediction is **`residual_L1(A-3.5)` in
`[5.088e-2, 8.244e-2]`**.

The band was fixed from the two lower contrasts alone. It is not fitted to
A-3.5 and cannot be adjusted after A-3.5 is run.

## 3. Falsifiers

Any one firing makes the power-law reading BREAKING. All four are computed from
the A-3.5 record, the A record, and `.scratch/d50/pg_a15.json`.

- **F1** — `p_3` outside `[0.75, 1.05]`.
- **F2** — `residual_L1(A-3.5) >= 0.1`. This is a mildness bound on how far the
  removed deflation block sits from the null space of `(M_eps - M_mu)`. It is
  *not* a statement about any eigenvector; see §4.
- **F3** — the residual not strictly increasing in contrast at every level:
  requires `residual(c=0.5) < residual(c=1.0) < residual(c=2.5)` for each of
  levels 1, 2, 3.
- **F4** — the three per-level exponents `p_1, p_2, p_3` spanning more than
  0.15. F4 tests the factorisation `residual(c, h) = g(c) * phi(h)`: if the
  contrast exponent depends materially on mesh level then the law is not
  separable, and a single exponent misdescribes it even when `p_3` is in band.

F1 and F2 overlap but are not redundant. At `p_3 = 1.10` the level-1 residual is
`8.93e-2`, which fires F1 and not F2; the two separate only below
`p_3 ~ 1.15`. F2 exists so that a residual approaching `O(1)` is called out as
a magnitude anomaly independently of the exponent.

## 4. What `residual_eps_mu` is, and what it is not

The measured definition (`emfit/mode2d.py:1592-1595`):

```
residual_eps_mu = || (M_eps - M_mu) Z ||_F / ( (||M_eps||_F + ||M_mu||_F) * ||Z||_F )
```

where `Z` is the deflation block `_incidence(mesh, free, cols)` (`:1548`) and
`M_eps`, `M_mu` are the free-DOF blocks of the epsilon and mu mass operators
(`:1575-1576`); `_frob_norm` is at `:1056-1059`, `_ratio` at `:1062-1064`
(returns NaN when the denominator is not positive), and the value is published
as `extra={"deflation": info}` at `:1614`.

**No eigenvector enters the statistic.** It is a function of the deflation block
and the two mass operators only. It is a per-level scalar — never per-mode,
never aggregated across modes. It is dimensionless, and it is zero exactly when
the deflation block lies in the null space of `(M_eps - M_mu)`.

Consequence, and the reason F2 is worded as it is above: the dispatch's phrasing
"the removed subspace carries a tenth of the physical mode" misdescribes the
statistic, because no physical mode is involved in the computation. F2 is
retained at 0.1 but restated as a mildness bound on how non-null the removed
block is. This is recorded as a disagreement with the dispatch text.

## 5. Pre-run feasibility, and the criterion that must survive

Doubling the contrast cost roughly a factor 9 in accuracy between the two
measured geometries: the order-1 level-1 error was `8.55e-4` at `c = 1.0`
against `9.30e-5` at `c = 0.5`. Going from `c = 1.0` to `c = 2.5` is a factor
2.5 in contrast, so expected level-1 accuracy at A-3.5 is `1e-3` to `1e-2`.

The criterion that must still be met at A-3.5 is **P1 and P2 on all four frozen
orders**. Both are ratios and are insensitive to an overall accuracy
prefactor; a conditioning penalty moves the prefactor, not the ratio. P3
(`e_3 <= 5e-3`) is supporting only: the worst root at `eps_r = 2.0` reached
`5.3928e-4` at level 3, and a 9x penalty lands almost exactly on `5e-3`, so a
P3 breach at A-3.5 is an ANOMALY to report, not a gate failure.

The arithmetic floor is `1.8e-14`, about 16 levels below the expected level-3
value.

If P1/P2 cannot be met on some order, the outcome is FAILED-TO-MEASURE for that
order. It is not reinterpreted as a pass, and the band is not relaxed.

## 6. The frozen set of roots — four, not three

`solve_ref` at `eps_r = 3.5`, `t = T` returns **four** analytic roots in the
census window `[0, 3949.600488469103]`, every one below the endpoint
`2633.066992312735`:

| order (ascending `beta`) | `beta` |
|---|---|
| 1 | 643.892016367369 |
| 2 | 1131.390236903973 |
| 3 | 1338.051991441654 |
| 4 | 2294.582338440372 |

judged in descending order (`2294.582338440372`, `1338.051991441654`,
`1131.390236903973`, `643.892016367369`). The minimum absolute gap between
adjacent frozen roots is `206.661754537681`.

Dispatch 51 anticipated three roots. Criterion 7 of the acceptance document
(`docs/design/d51_acceptance.md`) defines the widened set as "the analytic roots
in the census window", which is four. **Four roots are therefore frozen, and
order 4 is judged on the same terms as the others rather than excluded.** The
dispatch's "three ordered roots" phrasing is superseded by its own criterion 7;
this is recorded as a disagreement with the dispatch text.

## 7. Pairing and pairing tolerance

Inherited unchanged from the frozen module: `PAIR_TOL = 2e-2` relative, applied
as `|beta - beta_ref| / beta_ref`; annihilation (a frozen root with no
candidate inside tolerance) is a STOP, not a PASS.

On the descending set the minimum relative gap is `0.182661779991` when the
denominator is the smaller member of the pair, and `0.154449719338` when the
denominator is `ref[k+1]`. Both are reported. The route-3 threshold of `0.04` is
cleared by a factor 4.57 on the stiff (smaller-denominator) convention — the
same convention on which A-1.5 returned `0.1381643889639651`.

## 8. Cluster-safety rule (new, and blocking)

The frozen module does not print a cluster diagnostic; A-1.5 registered one and
it failed to print. For A-3.5 it is made blocking, because four frozen roots
and ~16 candidates per level make a near-degenerate cluster the likeliest way
for a false PASS to arise.

Rule: two candidates fall in the same group when
`|eps_eff_i - eps_eff_j| / max(|eps_eff_i|, |eps_eff_j|) <= 1e-2`, and groups
are the connected components of that relation. For every group of size `>= 2`
report the group size, the `eps_eff` range, and `min_rel_gap` — the minimum of
`|beta - beta_ref| / beta_ref` over all (group member, frozen root) pairs. A
level's `min_cluster_distance` is the smallest such gap over its clusters; a
level with no cluster of size `>= 2` is vacuously safe.

Per level, print every candidate's `index`, `beta`, `eps_eff` and `curl_ratio`,
then exactly one of:

```
cluster_safety level N: min_cluster_distance = <x> PAIR_TOL = 0.02 -> SAFE|UNSAFE
cluster_safety level N: no cluster of size >= 2 -> SAFE (vacuous)
```

If any level reports UNSAFE (`min_cluster_distance < 2e-2`), the run STOPs:
`STOP: unsafe cluster distance`, no verdict, exit 3.

Control datum, registered before the run: replaying this rule against the
existing A-1.5 record finds no cluster at level 1, a cluster of size 3 at level
2 (`eps_eff` range `[1.25069361218, 1.25567211273]`, `min_rel_gap`
`0.0980645337196`) and a cluster of size 7 at level 3 (`eps_eff` range
`[1.25014830869, 1.25588424205]`, `min_rel_gap` `0.0978251290846`), both SAFE at
~4.9x `PAIR_TOL`. The diagnostic is therefore neither vacuously safe nor
trivially unsafe on real data.

## 9. Budget, and the no-second-attempt rule

The ARPACK budget is the frozen module's `ARPACK_BUDGET_FACTOR` (40) times the
defined dimension — a fixed multiple, not a tuned number. If the budget binds at
any level the outcome is FAILED-TO-MEASURE. There is no second budget and no
retry with a larger cap.

## 10. Inherited gate, unchanged

- **P1**: `e_1 > e_2 > e_3` strictly, per order.
- **P2**: `p_k = log2(e_k / e_{k+1})` in `[1.7, 2.3]` for `k = 1, 2`, per order.
- **P3**: `e_3 <= 5e-3`, supporting only.
- **Route-3**: `min` over frozen orders of `|beta_k - beta_ref| / beta_ref[k+1]`
  `<= 0.04`, descending set.
- **B4** true and **B5** empty at every level.
- Verdict vocabulary is exactly PASS / FAIL / FAILED_TO_MEASURE / STOPPED. No
  other words are available, and no verdict is issued on a STOP.

## 11. Freeze discipline

This document and `tools/host/anchor/preservation_gate_a35.py` are committed
together, before any discrete solve of the A-3.5 system. That commit is the
freeze reference.

`tools/host/anchor/preservation_gate.py` is not modified by dispatch 51; its
sha256 must remain
`7a0c04b2efbe9fefd2e5a2f7ccbfba3ca8500cb9506cda40e789201396dd2d1b`.

`preservation_gate_a35.py` is a launcher, not a second gate: it bootstraps
`sys.path` so the frozen module runs without the caller setting `PYTHONPATH`,
calls the frozen module's own `main(argv)`, and adds the §8 cluster diagnostic
by reading the record the frozen module wrote. It does not re-implement
pairing, the e-tables, P1/P2/P3, route-3, or the verdict — a second copy of
the adjudication rules would be a divergence risk. It refuses levels 4 and 5
with exit 2.

## 12. Non-claims

The A-3.5 measurement does not establish that over-removal is absent. It does
not test mode purity: row four of the acceptance table remains UNMEASURED. It
says nothing about passivity. It does not test levels 4 or 5. And because
`residual_eps_mu` contains no eigenvector, it cannot say whether any physical
mode was damaged — only how far the removed block lies from the null space of
the mass-operator difference.
