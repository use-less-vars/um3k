# `CORR_EZ_VV_MIN` — the derivation of the `|corr_ez_vv|` selection bar

Design note. **One constant changes: `CORR_EZ_VV_MIN`, `0.90` → `0.91`** (`tools/host/c1-audit/c1_audit.py:175`).
`CORR_EY_MIN = 0.90` (`:155`) and `CORR_EZ_MAX = 0.30` (`:156`) are untouched and still define
`shape_pair_ok_legacy`. **No solve, no gate, no re-run was performed for this note**; every number below is either
already banked in an artefact or arithmetic on banked numbers.

This note exists because the bar it replaces was a round number that borrowed another metric's threshold.
`decisions.md` §7 item 2 says it in as many words — *"The threshold needs a derivation, not a round number"* — and
`reports/2026-10-27_16-16-34_Dispatch_22___corr_ez_metric_correction_and_supers.md` §8 item (2) says the same.
This is that derivation, **and §3.2 states the one respect in which it is circular**: the scale it uses is measured
from the same passing legs the bar judges. The number is not affected; the label and the falsification condition are.

---

## 1. The statistic the bar gates

`|corr(A_ez, e_z_vv)|`, where

* `A_ez` is the vertical component of the analytic plane reference, on the `(NYN, NZN-1)` plane lattice
  (`c1_audit.py:412-426`; `A_ez` assigned at `:432`), and
* `e_z_vv = E_tz[:, :, 1] * CELL` is the solver's **own transverse** vertical component, sampled on the same
  lattice in `e_at`'s `(x, y)` = `(iyy, izz)` order (`c1_audit.py:520-521`).

The pairing is same-component: a **vertical** reference against the **vertical** mode component. That is the whole
content of the 2026-10-27 correction, and it is what makes this statistic a fidelity measure at all
(`decisions.md` §1; `docs/design/zfree_shape.md` banner). The superseded statistic — vertical reference against
the **longitudinal** field `beta*z_free` — is still computed and retained as `corr_ez_superseded_longitudinal`
(`c1_audit.py:530-534`); **nothing in this note applies to it.**

The comparison expression is `c1_audit.py:557-559`:

```python
ok_arr = np.array([bool(r[8]) and np.isfinite(r[4]) and np.isfinite(r[5])
                   and abs(r[4]) >= CORR_EY_MIN and abs(r[5]) >= CORR_EZ_VV_MIN
                   for r in rows], dtype=bool)
```

so the constant enters as a **lower bound on `|corr_ez_vv|`**, inside the `abs()`. The screen is on the magnitude
because an eigenvector's sign is arbitrary (LAPACK): the 41x22 leg carries the opposite sign to the 31x17 leg on
*both* components, because `A_ez`/`A_ey` are fixed analytic arrays and the sign belongs to the mode
(`.scratch/logs/d22_41x22_replay.txt:69-78`). Both the signed and the absolute value are printed
(`c1_audit.py:641-650`), so nothing is hidden.

## 2. The measured population

Signed, 15 significant digits, from `decisions.md:7874-7877` and the Dispatch 22 report table; the two PMC legs
re-derived through the patched code path in `.scratch/logs/d22_41x22_replay.txt:32-33,42-43`.

| leg | box | column | `corr_ez_vv` | `|corr_ez_vv|` | `|corr_ez_vv|/|corr_e_y|` | passes 0.91? |
|---|---|---|---|---|---|
| 31x17 | PMC | 738 | `+0.935286730348765` | `0.935286730348765` | 1.0158 | yes |
| 41x22 | PMC | 1318 | `-0.948530101525844` | `0.948530101525844` | 1.0105 | yes |
| 31x17 | PEC | 699 | `+0.936929717079781` | `0.936929717079781` | 1.0270 | yes |
| 31x17 | PEC | 704 | `-0.083134346` | `0.083134346` | — | no |

**Four points is the whole population.** Three passing legs and one rejected one, and the rejected one
(column 704) also fails the `corr_e_y` bar at `-0.426418989`. So **the `corr_ez_vv` bar is not yet exercised as an
independent discriminator by any banked case** — column 704 would be rejected with or without it. That is not a
defect of the bar; it is the limit of the evidence, and it is the same point `decisions.md:7638` makes in its
class-(b) row ("whether the corrected metric can now supply a genuine second blow is untested — that is the M3c
gate's job").

## 3. The scale: `S_good`, the observed spread of the passing legs

```
S_good = max(passing |corr_ez_vv|) - min(passing |corr_ez_vv|)
       = |corr_ez_vv|(41x22 PMC 1318) - |corr_ez_vv|(31x17 PMC 738)
       = 0.948530101525844 - 0.9352867303487647
       = 0.0132433711770793          (+1.4159691 % of the 31x17 value)
```

Source: `.scratch/logs/d22_41x22_replay.txt:74` — `|corr_ez_vv| 41x22 - 31x17 = +0.013243 (+1.4160% of the 31x17
value)`; the two operands at full recorded precision are `:70` (`0.9352867303487647`) and `:71`
(`-0.948530101525844`). The log is produced by `.scratch/d22_41x22_replay.py` (untracked driver), which records the
`sha256` of every input, execs only the metric block (`c1_audit.py:402-416`, `:488-528` **in the pre-note revision
it hashed**; `:412-426` and `:498-538` once this note's comment grew the file), injects the banked `z_free` in place
of the forbidden solve at `:487` (now `:497`), reproduces the banked values to `worst |delta| = 4.302e-16`, and
reports `solves=0`. Both numbers are therefore on one code path, same wall set, same component, same statistic.

> **The recorded digest no longer matches the working tree, by design.** The driver hashed `c1_audit.py` as
> `b5cbccbb427c51c71b652b1c77b1c988a248110bc16bcc64f589f812b506826c`
> (`.scratch/logs/d22_41x22_replay.txt:4`) — the revision that still carried `CORR_EZ_VV_MIN = 0.90` and the old
> provisional comment. This note edits that file (comment plus `0.90 → 0.91`), so re-hashing it gives a different
> digest; that is not evidence the replay is stale. The constant is read only at the comparison (`:557-559`) and
> the three reporting sites (`:576-578`, `:634`, `:668-669`); no line that feeds a correlation reads it, so every
> measured number in the log is independent of the edit.

**Precision.** Arithmetic on the §2 table's own digits (`0.948530101525844 - 0.935286730348765`) gives
`0.0132433711770790`, `3e-16` away from the value above; the difference is only the table's rounding of the 31x17
leg to 15 dp (`…765` vs the replay's `…7647`). It is 0.0023 % of `S_good` and does not move any digit of the bar.

**What `S_good` is.** It is the spread of the three passing legs — plain max minus min. Its two extremes happen to
be the two refinements (31x17 and 41x22) of the same PMC pencil on the same component, so this spread **is also**
the one-mesh-refinement step of the statistic. Those are one number with two descriptions, **not two independent
measurements that agree**: the identity is a consequence of the population's shape, nothing more. The third passing
leg (31x17 PEC 699, `0.936929717079781`) lies strictly inside the bracket and contributes nothing to `S_good`; if a
passing leg ever fell outside it, `S_good` would exceed the mesh step and the two descriptions would separate
(§6 trigger 6).

**What `S_good` is not.** It is not a dispersion: two points, one refinement pair, no `σ`, no repeated measurement.
It is also **not exogenous to the verdict** — see §3.2, which is the part of this note the reader must not skip.

### 3.1 The legacy scale `F = 1.5657e-4` must **not** be substituted

The project's existing spread is measured on the **superseded** statistic:

```
F    = 0.119317006502073 - 0.119160432391342 = 0.000156574110731000   (0.1314 % relative)
2F   = 3.1315e-4
```

(`docs/design/c2b_preregistration.md:29`, `:44`; the same pair of numbers sits in
`.scratch/logs/corr_ez_followup.txt:205` and `:212`, and `docs/design/zfree_shape.md:325,425` quotes it.)

**There is no conversion between the two, and this note does not claim one.** `F` is a spread of
`|corr_ez_superseded|`, whose readings are ~`0.119`; `S_good` is a spread of `|corr_ez_vv|`, whose readings are
~`0.94`. Both are dimensionless correlation deficits, but of two different statistics, and nothing here maps one
onto the other. The ratio `S_good / F = 84.5821` is **descriptive only**: it sizes the mistake if the legacy number
is carried over, it is not a conversion factor, and it must not be used as one. The correct statement is the plain
one — *these are spreads of different quantities and are not interchangeable* — and the substitution test shows it
directly:

```
0.9352867303487647 - 2F = 0.9349735821273027
```

On this note's own round-up grid that is `0.94` — **above** the weakest passing leg, i.e. a bar that would reject
the very leg it was derived from. Before rounding, the weakest leg clears it by only `0.000313148221462` =
`0.0236 S_good`, a fortieth of one spread; and the 41x22 leg would clear it by `0.013556519398541` = `1.024 S_good`
— one spread. A bar that sits one spread under the strongest evidence in the population and above its weakest is
not a screen; it is a coin flip on the next refinement.

> **Conflict recorded, not edited.** `docs/design/zfree_shape.md:472` asserts that "§4.1's noise floor
> `F = 1.5657e-4` and the `2F` detection bar stand as properties of the meshes; only the statistic they were
> applied to changes, and the corrected statistic is now available to apply them to." Measured, that is not true
> for `corr_ez_vv`: the statistic's own spread is `0.0132433711770793`. The scale is a property of *the estimator*,
> not of the meshes alone. `zfree_shape.md` is append-only under its own banner discipline and was not touched by
> this note; the sentence needs a pointer, which is the main agent's call.

### 3.2 The rule is self-referential, and this is the honest label

`S_good` is computed from the same three legs that the bar is meant to judge. Written out, the rule of §4 is

```
T = min(good) - 2 * ( max(good) - min(good) )
```

— a bar placed two spreads below the worst member of its own population. Three consequences, stated rather than
buried:

1. **It cannot reject a member of its own population, and it does not certify that population.** Any set of four
   good cases has a spread, so `min - 2 * spread` will always land roughly `0.025` below the weakest good case
   whatever the case actually is. The rule is a statement about *reproducibility* — "how far below the incumbent
   population a candidate must sit to be outside the estimator's own resolution" — not about accuracy. It says
   nothing about whether the three passing legs are good; it says how far below them a new candidate must be to be
   clearly different.
2. **A common-mode bias would not be detected.** If the extraction were biased the same way on both meshes, the
   spread would shrink and the bar would follow it down. `§2` cannot rule that out with four points, and neither
   can this rule. The best available accuracy statement remains the residual decomposition of `decisions.md` §5.3.
3. **The mesh-step reading is a coincidence of this population, not a second witness.** It is available only because
   the two extremes are the two refinements of one pencil; it would vanish if the extremes were two different
   geometries, and it inflates if a passing leg lands outside the current bracket.

**Falsification.** This derivation fails — and must be redone rather than defended — if any of these holds:

* an **independent** reproducibility estimate (a third mesh giving an adjacent pair, or a repeat at fixed mesh)
  differs from `S_good` by more than `S_good` itself, i.e. by a factor of ~2 either way. Then `S_good` is
  contaminated by population structure and the bar must be taken from the independent estimate;
* a passing leg lands **outside** the current bracket `[0.9352867303487647, 0.948530101525844]`: `S_good` changes,
  and the mesh-step reading no longer equals it;
* any passing leg moves by more than `S_good`, which moves the bar with it (§6 triggers 4-6).

## 4. The rule, and the number it produces

**Rule.** For a metric whose passing population has weakest member `L` and observed spread
`S_good = max - min`:

```
T = L - k * S_good,   k = 2,   rounded UP to the next 0.01
```

**Applied:**

```
S_good = 0.948530101525844 - 0.9352867303487647 = 0.0132433711770793
T = 0.9352867303487647 - 2 * 0.0132433711770793
  = 0.9352867303487647 - 0.0264867423541586
  = 0.9087999879946061
  -> 0.91
```

**Why `k = 2`.** With `k = 1` the bar lands at `0.9220433591716854`, exactly one spread below the weakest leg —
i.e. *inside* the population's own bracket, where a single further refinement could flip the verdict on the best
evidence the project has. `k = 2` puts the bar outside the bracket: every passing leg clears it by more than one
full spread. (The two are related by construction: `41x22 - 2*S_good = 0.9220433591716854 = 31x17 - S_good`, since
`S_good` is exactly their difference.)

**Why round up — and yes, it tightens.** `0.9087999879946061` is not on the reporting grid. Rounding **up** to
`0.91` raises the bar by `0.0012000120`, which is `0.0906` of one spread: that is a **tightening**, and it is
deliberate — it is the conservative direction, and it preserves the exact guarantee "no candidate gets more than
`k` spreads of headroom". No banked leg lies in the half-open window `[0.9087999879946061, 0.91)`, so no verdict
changes hands; the nearest leg is `0.9352867303487647`. Rounding **down** to `0.90` would loosen the screen, would
land on the borrowed round number this note exists to replace, and would make the bar indistinguishable from
`CORR_EY_MIN` by inspection.

**Margins at `0.91`:**

| leg | `|corr_ez_vv|` | margin | in spreads `S_good` | relative |
|---|---|---|---|---|
| 31x17 PMC 738 | `0.935286730348765` | `+0.025286730348765` | 1.909 | 2.7036 % |
| 41x22 PMC 1318 | `0.948530101525844` | `+0.038530101525844` | 2.909 | 4.0621 % |
| 31x17 PEC 699 | `0.936929717079781` | `+0.026929717079781` | 2.033 | 2.8743 % |
| 31x17 PEC 704 | `0.083134346` | `-0.826865654` | -62.436 | — |

The bar admits a `1.455 %` relative deficit at the threshold; the passing legs sit `2.7-4.1 %` relative above it.

## 5. What `0.91` is for, and what it is not

* **It is a reproducibility screen.** Its job: reject a candidate column whose `|corr_ez_vv|` sits more than two
  spreads below the weakest leg the project has measured, i.e. outside the estimator's own refinement resolution.
  That is the entire claim.
* **Not an accuracy statement.** It does not say the extraction is `91 %` correct. It is a *selection* threshold:
  the line below which a candidate column is not the mode. The best fidelity statement in the record is the
  residual decomposition in `decisions.md` §5.3, which says the `0.935` deficit is `57-58 %` concentrated in an
  edge band — a shape, not a scalar.
* **Not an independent validation of the population.** `S_good` is measured from the three passing legs the bar
  judges (§3.2), so `0.91` records their reproducibility, not their correctness. A population biased the same way on
  both meshes would shrink the spread and drag the bar down with it.
* **Not a confidence bound.** No `σ`, no `n`: two points of the same estimator, one refinement, one wall set.
  It is a calibrated convention, stated in closed form so the next person can recompute it rather than inherit it.
* **Not transferable.** `0.91` and `0.0132433711770793` belong to `|corr_ez_vv|` on the millimetre microstrip
  pencil. Applying either to `corr_e_y`, to the superseded longitudinal statistic, or to another geometry is the
  legacy-`F` mistake of §3.1 repeated.
* **Not able to separate wall treatments.** The corrected PMC-vs-PEC wall term is
  `+0.0016429867310159274` (`decisions.md:7883`, `:7931`), which is `0.124 S_good`. A bar placed ≥ 1 spread below
  the population cannot resolve an effect an order of magnitude smaller than one spread.
* **Verdict-inert on every banked artefact.** `tools/host/c1-audit/out/c1_spectrum.npz` banks a single propagating
  column (738) at 31x17, so `0.90 → 0.91` changes no banked `shape_pair_ok`. That is *inertia*, not a safety
  argument: for a pencil with many propagating columns, any column with `0.90 ≤ |corr_ez_vv| < 0.91` would change
  hands, and no such run exists to check. Re-run rather than re-read if it matters.

## 6. Re-basing triggers

Any one of these voids the bar and restarts §4 from the data. In all cases: **recompute, do not copy
`0.0132433711770793` or `0.91` forward.**

1. A third mesh exists for the same pencil and wall treatment. Then the scale is taken from the *adjacent* pair —
   the first measurement of this quantity that is independent of the population it gates, and the point at which
   §3.2's self-reference becomes an external check.
2. The extraction path for `e_z_vv` changes — sampling order, the `CELL` scaling, the `_ezc_pts` lattice
   (`c1_audit.py:426`, `:520-521`). A different statistic gets its own bar; it does not inherit this one.
3. The **M3c gate** is stated. It must adopt this bar with its derivation, or state its own; what it must not do is
   quote `0.91` bare.
4. Any passing leg moves by more than `S_good` = `0.0132433711770793` (e.g. a new banked value, a changed
   reference placement — the same `2e-2`-scale drift the `REPRO_RTOL` comment, `c1_audit.py:178-180`, already
   guards against). Note the coupling: `S_good` is a function of the passing legs, so a move in the weakest or the
   strongest one moves the bar as well. Recompute both.
5. A new leg lands **within one `S_good` of the bar** (currently: `0.8968 … 0.9232`). That is a signal the rule is
   miscalibrated for the population, not that the mode is bad. Escalate rather than adjust the number quietly.
6. A passing leg lands **outside** the current bracket `[0.9352867303487647, 0.948530101525844]`. Then `S_good` is
   no longer the mesh-refinement step, the two descriptions of §3 separate, and the note must say which reading is
   now in force.

## 7. Provenance — every number in this note

| value | meaning | where |
|---|---|---|
| `0.935286730348765` | `corr_ez_vv`, 31x17 PMC col 738 | `decisions.md:7874`; `.scratch/logs/d22_41x22_replay.txt:33` |
| `0.948530101525844` | `corr_ez_vv`, 41x22 PMC col 1318 | `decisions.md:7875`; `.scratch/logs/d22_41x22_replay.txt:43` |
| `0.936929717079781` | `corr_ez_vv`, 31x17 PEC col 699 | `decisions.md:7876`; Dispatch 22 report §1 |
| `0.083134346` | `corr_ez_vv`, 31x17 PEC col 704 (rejected) | `decisions.md:7877`; Dispatch 22 report §1 |
| `0.0132433711770793` | `S_good`, spread of the three passing legs (= the 31x17 → 41x22 PMC step) | `.scratch/logs/d22_41x22_replay.txt:70-74` |
| `0.0264867423541586` | `2 S_good` | arithmetic |
| `0.9087999879946061` | `L - 2 S_good`, before rounding | arithmetic |
| `0.0012000120053939` | rounding delta `0.91 - T` (`0.0906 S_good`, a tightening) | arithmetic |
| `0.000156574110731` | legacy `F`: spread of the *superseded* statistic | `docs/design/c2b_preregistration.md:29` |
| `3.1315e-4` | legacy `2F` detection bar (not used here) | `docs/design/c2b_preregistration.md:29,44` |
| `84.5821` | `S_good / F`, descriptive only — **not** a conversion factor (§3.1) | arithmetic |
| `0.028131014553288` | **superseded** wall term (23.6 %), on the mis-paired metric | `decisions.md:7682` |
| `0.0016429867310159274` | corrected wall term (+0.1757 %) | `decisions.md:7883`, `:7931` |

**These are six numbers close enough to confuse by eye. They are not a converging series.** `1.5657e-4` and
`3.1315e-4` are the *superseded* metric's spread and detection bar; `0.0132433711770793` is the *corrected*
metric's spread; `0.028131014553288` is the retired wall term, `134x` too large; `0.0016429867310159274` is the
corrected one. Reconcile none of them by inspection.

## 8. Where the constant lives

| site | role |
|---|---|
| `tools/host/c1-audit/c1_audit.py:175` | **the definition** — the only numeric edit made by this note |
| `c1_audit.py:557-559` | the comparison: `abs(r[5]) >= CORR_EZ_VV_MIN` |
| `c1_audit.py:576-578` | printed run header (interpolates the constant) |
| `c1_audit.py:634` | `criterion_ez_vv` in `c1_spectrum.npz` |
| `c1_audit.py:666-669` | VERDICT line |
| `tools/host/c1-audit/pecbox_variant.py:511-513`, `:534-536` | imports `c1_audit.CORR_EZ_VV_MIN`; no numeric edit — it follows automatically |
| `docs/design/zfree_shape.md:463` | still says `0.90 (provisional)`; **stale after this note**, and append-only |
| `decisions.md:7925`, `:7990` | record `0.90` as provisional; **stale after this note**, and append-only |

## 9. What this note does not decide

* **`CORR_EY_MIN` is untouched and is now the *looser* of the two bars.** The `corr_e_y` legs are the weaker pair
  (`0.920770784811142`, `-0.938702180035899`) and their own spread is `0.017931395224757` — `1.354 S_good`. Their
  bar at `0.90` sits `1.158` of *their* spreads below their weakest leg, i.e. tighter than this note's rule would
  set it: applied with their own spread, the rule gives `0.9207707848111419 - 2 * 0.017931395224757 =
  0.8849079943616279`, which rounds up to `0.89`. Flagged for the M3c gate; **not changed here.**
* Whether the screen should test `|corr|` or the signed value. `|corr|` is correct for a LAPACK-arbitrary sign and
  is what is banked; a signed screen would require a sign convention that does not exist.
* Whether the thin evidence (§2) is enough to gate anything at all, or whether the gate should be a *shape* test on
  the edge-localised residual of `decisions.md` §5.3. This note sets the scalar bar that exists; it does not argue
  that a scalar is the right instrument.
