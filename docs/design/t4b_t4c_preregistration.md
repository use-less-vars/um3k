# T4b / T4c — two new tests and one operational invariant, pre-registered: mesh-independence of the conductor field, eigenvalue convergence, and the residual-first rule

Pre-registration only. No solve, no gate run, no field reconstruction. Every figure below is a reading
from an artefact that already exists, named where it appears, or a quotient of two such readings.

**This document supersedes nothing and amends nothing.** It does not edit
`docs/design/t4_amp_ratio.md`, it does not edit `docs/design/m3c_gate_v2.md`, it moves no existing
threshold, and it rewrites no earlier verdict. `T4_amp` remains registered **FAIL** (Physics).

## 0. What this is not

`T4_amp` is registered **FAIL**, in Physics, and this document does not walk that back. It does not
reinterpret the ratio, it does not add an allowance, it does not reopen the `|Q - 1| <= 0.10` bar, and
it does not claim the failing measurement was measuring the wrong thing.

What it does is register **two new tests** and **one operational invariant**. The reason is narrow and
factual: the `T4_amp` measurement asked a question the data cannot answer. A single global energy ratio
`R` has no single-`h` limit to converge along in this geometry (§1), so "does `R` converge?" was never
answerable from the five banked meshes, and the answer to "is the conductor-region field the same field
on every mesh?" is not the same question and is answerable. `T4b` asks it. `T4c` asks a narrower
question that *is* well-posed — does the eigenvalue converge — and asks it on a ladder that does not yet
exist. The invariant (§4) is not a test at all: it is the precondition under which any of these numbers
may be believed.

## 1. Motivation — `R` is one number over three regions whose ratios differ by `40x`

`R = sum(e_z_vv^2) / sum(e_y^2)` is one global energy ratio. Decomposed by region on the fixed analytic
lattices (`CELL = 1e-4`, `W = 0.02`, `H = 0.0076`, `HSUB = 0.0016`, `Y0 = 0.0085`, `Y1 = 0.0115`,
`tolerance = 1e-9`, `mesh_independent = true`; `mode_overlap.json:lattice`), with the masks of
`mode_overlap.json:region_notes` — `strip_footprint` a row mask on `y` (`Y0 <= y <= Y1`, all `z`),
`substrate` a column mask (`z <= HSUB`), `air` a column mask (`z > HSUB`), `partition_exact = true` —
over the ten meshes of the axis sweep:

| region | `R` range |
|---|---|
| `strip_footprint` | `24.568518898` - `35.941761637` |
| `substrate` | `6.178042807` - `6.992095190` |
| `air` | `0.854638066` - `0.960334386` |
| global (all three) | `3.42` - `3.74` |

The global `R` of `~3.4`-`3.7` is therefore a weighted average of components that differ by `~40x`,
and the weights are themselves mesh-dependent: the `e_y` strip-footprint energy fraction climbs
`0.082289` -> `0.092995` -> `0.104386` -> `0.110099` -> `0.111532` across the campaign
(`docs/design/t4_amp_ratio.md` 14.5; `1.3553x` over the series). Refining the mesh moves the mixture,
not only the parts. The derivation is `docs/design/t4_amp_ratio.md` §15; the artefacts are
`tools/host/sparse-probe/mode_overlap.py` (commit `0a28615`) and
`tools/host/sparse-probe/axis_sweep.py` (commit `0f92dfe`).

Two results are already established and motivate the split:

1. **The hump is not mode tracking.** `lambda` is strictly monotone decreasing across the five campaign
   meshes (`96752.519700848279172` -> `96617.808797000368941` -> `96501.437696076784050` ->
   `96431.677574227433070` -> `96421.549011048933608`; steps `-135`, `-116`, `-69.8`, `-10.1`), the
   mode shape is frozen across `3.2x` refinement (peak `|e_y|` at `z = HSUB` on every mesh, exactly one
   sign change along `y` on every mesh, strip/air peak ratio `0.2597`-`0.2726`), and the single-process
   re-run reproduces the committed per-run records **bit-for-bit**, recorder delta `0.00e+00` on `R`,
   `corr_ey` and `corr_ez_vv` for all five meshes. A branch change would not preserve all of that.
2. **`R` humps along the transverse axis alone and along the `z` axis alone** (`axis_sweep.json:verdict`),
   so `R` is **not a monotone function of any single refinement parameter**. Whatever the hump is, a
   one-parameter convergence story for `R` does not exist to be tested.

Neither result is a defence of the failing number. Both say the same thing: `R` as a global scalar is
the wrong instrument for a convergence test here, and two better-posed tests are available.

## 2. `T4b_conductor_corr` — is the conductor-region field the same field on every mesh?

### 2.1 The definition, at full precision

Field `e_z_vv`. Region `strip_footprint` = row mask on `y`, `Y0 <= y <= Y1` (`Y0 = 8.5e-3`,
`Y1 = 11.5e-3`), all `z` columns. On the `e_z_vv` lattice (`200`-`201` x `76`-`77` at `CELL = 1e-4`,
`e_z_vv_axes = yn_node x zc_mid`) that mask is a **31 x 76 slab**, `31` y-node rows by `76` z-mid
columns.

Statistic: the absolute Pearson correlation `|corr(a, b)|` of the slab between two meshes, taken over
**all 10 off-diagonal pairs** of the five banked campaign meshes
(`mode_overlap.json:pairwise_abs_corr.e_z_vv.strip_footprint`):

| mesh | spec (`strip/yair/z`) | free edges |
|---|---|---|
| `M5_ctrl_rung4` | `36/22/20-10-10` | `9604` |
| `M1_fe11888` | `36/27/22-11-11` | `11888` |
| `M2_fe19665` | `47/35/28-14-14` | `19665` |
| `M3_fe28980` | `56/43/34-17-17` | `28980` |
| `M4_fe30672` | `58/44/35-17-18` | `30672` |

**Registered threshold: `min` over the 10 pairs `>= 0.99`.**

### 2.2 The measured value, which the registration is made against

| pair | `\|corr\|` (e_z_vv, strip_footprint) | against `0.99` |
|---|---|---|
| `M5`-`M2` | `0.9988226233736953` | min of the ten |
| `M1`-`M2` | `0.9989140294772695` | |
| `M5`-`M4` | `0.9989414993425664` | |
| `M5`-`M3` | `0.9989558004936799` | |
| `M1`-`M4` | `0.9991784474646487` | |
| `M1`-`M3` | `0.99919052192113` | |
| `M2`-`M3` | `0.9993134100595398` | |
| `M2`-`M4` | `0.9993732856116622` | |
| `M5`-`M1` | `0.9995420435394514` | |
| `M3`-`M4` | `0.9999426701804677` | max of the ten |

`min = 0.9988226233736953`, `max = 0.9999426701804677`, spread `max - min = 0.0011200468067724`.
The minimum exceeds the threshold by `0.0088226233736953`.

### 2.3 The second clause, `e_y`, stated separately

The `e_z_vv` number is strong enough to hide a weaker one, so the `e_y` clause is registered on its own
terms and must be quoted with its own number. Field `e_y`; same region mask; on the `e_y` lattice that
is a **30 x 77 slab** (`e_y_axes = yc_mid x zn_node`, `30` y-mid rows by `77` z-node columns).
Threshold on the same statistic: **`min` over the 10 pairs `>= 0.98`.**

Observed (`mode_overlap.json:pairwise_abs_corr.e_y.strip_footprint`): `min = 0.985637534849262`
(`M5`-`M3`), `max = 0.9978035015672908` (`M5`-`M1`), spread `max - min = 0.0121659667180288`. The
minimum exceeds `0.98` by `0.005637534849262`. The `e_y` clause is the weaker of the two on every
measure — lower minimum, an order of magnitude larger spread (`10.9x`) — and a `T4b` pass is not
reported as a single verdict without both numbers.

### 2.4 What `T4b` certifies, which is not accuracy

**`T4b` certifies MESH-INDEPENDENCE of the conductor-region field shape. It does NOT certify accuracy.
A `T4b` pass means "the conductor field no longer changes as the mesh is refined", not "the conductor
field is correct". This is the single most important sentence in this section and it is why the test is
scoped to agreement among the sparse meshes and nothing more.**

The reason is measured, not rhetorical. Each of these five meshes agrees with the **independent dense
Route-C reference** only at `|corr|` `0.9665079165495419`-`0.9770688452278082` (`e_z_vv`) and
`0.9699299418485586`-`0.9859547875012363` (`e_y`) **in the global domain**
(`mode_overlap.json:reference_agreement`) — i.e. below the `0.99` that `T4b` requires of mesh *pairs*.
Mutual agreement at `>= 0.99` between meshes that each sit at `~0.97` with the reference is a statement
about the meshes, and nothing in it touches the reference.

The record also carries a `consistency` block whose margin is
`|corr(a,b)| - max(|corr(a,ref)|, |corr(b,ref)|) >= 0`: a pair passes when two meshes agree **more with
each other than either agrees with the reference**. That direction can equally signal a shared
mesh-induced bias, and it behaves exactly as a weak test should — under it `e_z_vv` passes `10/10`
(`margin_min = 0.009012094703758966`) while `e_y` passes only `4/10` (`margin_min =
-0.007177504813400626`), failing `M5` x `{M2, M3, M4}` and `M1` x `{M2, M3, M4}`. Recorded so that
`T4b` is never cited as an accuracy check and the `consistency` block is never cited as one either.

## 3. `T4c_eigenvalue` — does `lambda` converge, and by how much per step?

### 3.1 Proposed, verbatim

> lambda moves monotonically with mesh size AND relative change per step <= 1e-4

### 3.2 Evaluated against the banked axis sweep, before registration

Source: `tools/host/sparse-probe/out_mesh/axis_sweep.json`, ten meshes, `n_converged = {y: 5, z: 5}`,
`nonconverged_specs = []`, residual gate `1e-6`. Convention for every relative step quoted in this
document: `(lambda_next - lambda_prev) / lambda_next`, i.e. **against the finer mesh's value** — the
convention that reproduces every figure already in the record.

Transverse sweep (`z` lobes fixed `34-17-17`):

| spec (`strip/yair`) | free edges | `lambda` | `\|d lambda / lambda\|` | vs `1e-4` |
|---|---|---|---|---|
| `22/20` | `12694` | `96883.12213680988` | — | — |
| `27/22` | `14525` | `96804.73548050332` | `8.0973989461848473e-04` | FAIL |
| `35/28` | `18597` | `96640.32186527594` | `1.7012941601807902e-03` | FAIL |
| `43/34` | `22669` | `96534.89794116202` | `1.0920809610030424e-03` | FAIL |
| `44/35` | `23280` | `96520.8943526043` | `1.4508349359638645e-04` | FAIL |

`0 of 4` steps meet `1e-4`. `lambda` is **strictly decreasing** (all four steps negative), which is the
monotone half of the proposal satisfied; total relative spread `3.7388120470980583e-03`.

`z`-lobe sweep (transverse fixed `56/43`; the fourth rung is the shared corner `56/43/34-17-17`, which
is campaign mesh `M3` reproduced in a fresh process):

| spec (`z` lobes) | free edges | `lambda` | `\|d lambda / lambda\|` | vs `1e-4` |
|---|---|---|---|---|
| `20-10-10` | `17024` | `96355.30163011796` | — | — |
| `22-11-11` | `18732` | `96373.32043448607` | `1.8696880305541560e-04` | FAIL |
| `28-14-14` | `23856` | `96410.06041564513` | `3.8108036651636061e-04` | FAIL |
| `34-17-17` | `28980` | `96431.67757422743` | `2.2417071989298820e-04` | FAIL |
| `35-17-18` | `29834` | `96430.53093501292` | `1.1890831704340804e-05` | PASS |

`1 of 4` steps meet `1e-4`, and `lambda` **increases and then reverses**: the last step moves
`-1.1466392145084683` absolute (`-1.1890831704340804e-05` relative). Total relative spread
`7.9202131530568657e-04`.

Loosened, the same eight steps score: at `1e-3`, transverse `2 of 4`, `z` `4 of 4`; at `1e-2`, both
`4 of 4`.

### 3.3 The problem, plainly

Applied retroactively to the data that exist, the proposed criterion **fails 7 of 8 steps**. A
pre-registration whose threshold existing data already fails is not a test that can fail; it is a
recorded foregone failure, and recording it would add nothing to the record except a formality. It
cannot be registered as written against the meshes we have.

### 3.4 Resolution: scope, not slack

`T4c` is registered **against the `40k` / `50k` / `60k` sweep**
(`tools/host/sparse-probe/high_res_sweep.py`, `TARGETS = (40000, 50000, 60000)` at
`:196`) — **PREPARED, NOT RUN**: no output of that script exists in
`tools/host/sparse-probe/out_mesh/`, and no mesh in that ladder has been solved. It is **not**
registered against the `9.6k`-`30.7k` campaign meshes, on which §3.2-3.3 have already shown it failing.

The threshold is not being moved to fit a number; it is being aimed at a regime. `1e-4` per step is a
forward-looking target, and the record is honest about how close the fine end is:

| reading | value |
|---|---|
| campaign final step `M3` -> `M4`, absolute | `10.128563178499462` |
| campaign final step `M3` -> `M4`, relative (against `M4`) | `1.0504460136124583e-04` |
| same step, relative (against `M3`) | `1.0503356815194976e-04` |
| transverse fine-end step (`43/34` -> `44/35`) | `1.4506244742972372e-04` (against `44/35`: `1.4508349359638645e-04`) |
| `z` fine-end step (`34-17-17` -> `35-17-18`) | `1.189069031414343e-05` (against `35-17-18`: `1.1890831704340804e-05`) |

Read that table without rounding: **no banked step anywhere in the record meets `1e-4`.** The finest
campaign step misses it by `1.050446x`, i.e. it is `5.0 %` above the target, and it is the closest
approach that exists. `T4c` is therefore a test of meshes not yet run, and its threshold is **not**
currently met by any measurement in the record. That is stated here, in the registration, so that the
threshold cannot later be described as one the data already satisfied.

**`T4c` REGISTERED AS:** monotone in `free_e` **AND** `|d lambda / lambda| <= 1e-4` per successive step,
over the `40k` / `50k` / `60k` ladder and over any further rungs added beyond it. Direction: `lambda`
must not move the wrong way at any step of that ladder.

**`T4c` STATUS: PRE-REGISTERED, NOT YET EVALUABLE.** No mesh in the registered ladder has been run, so
there is no measurement, and the test must not be reported as pass, as fail, or as a pending formality.
It becomes evaluable when at least two rungs of the `40k`/`50k`/`60k` ladder have been solved and
recorded with their residuals (§4).

### 3.5 Observed convergence, recorded and explicitly NOT a gate

The following are recorded because they are the honest account of how fast `lambda` actually moves. They
are **not** a pass criterion, they are **not** a fallback criterion, and no verdict is ever scored
against them. Denominators are named on each line.

| quantity | value | denominator |
|---|---|---|
| transverse total relative spread (`9.688e4` -> `9.652e4`) | `3.7388120470980583e-03` | `max - min` over `max` |
| same, over `min` | `3.7528432225493961e-03` | `max - min` over `min` |
| `z`-lobe total relative spread | `7.9202131530568657e-04` | `max - min` over `max` |
| same, over `min` | `0.00079264911029659963` | `max - min` over `min` |
| campaign diagonal spread (`M5`..`M4`) | `0.0034325386098227862` | `max - min` over `min` |
| same, over `max` | `0.0034207965934394549` | `max - min` over `max` |

One-line summary: **`lambda` is stable to `~4e-3` over the tested envelope, and locally converged to
`1.5e-4` (transverse) and `1.2e-5` (`z`) at the fine end.**

The `z`-lobe reversal of `1.1890831704340804e-05` is **real data, not solver noise**: the `35-17-18`
solve carries residual `3.7471545933622495e-09`, three orders inside the `1e-6` gate. No strict
monotonicity claim is therefore made for the `z` axis, and none should be inferred from the campaign
diagonal being monotone — that diagonal moves both axes at once.

### 3.6 Falsification

`T4c` fails if **any** rung in the registered ladder shows `lambda` moving in the wrong direction, or
**any** successive step exceeds `1e-4` relative. A failure is recorded as a FAIL and reported with the
step, the two `lambda` values, both denominators and the residual of both solves; it is not retried into
a pass, not averaged away over the ladder, and not re-scoped to a different ladder after the fact.

## 4. The sigma-ladder invariant — an operational rule, not a physics test

This section registers **no** test of the physics. It registers a **validity precondition** on every
number already banked and every number banked later: the rule under which a solve's output may be read
at all.

**The incident.** Mesh `43/34/34-17-17` solved at the default shift `sigma = 96777.0147917196` returned
a **spurious eigenpair**: residual `9.89e-01`, `|corr_ey|` `0.247`, `R` `0.2370`. The iteration locked
onto a nearby vector and returned it as the mode. It is shift-dependent, not mesh-dependent: `sigma` in
`{96777, 96656, 96883, 96640, 97000}` all returned the bogus pair; `sigma` in `{96100, 96400}` returned
residual `1.9e-12` and the true mode (`lambda` `96534.89794116202`, `R` `3.612955819639116`). In
`axis_sweep.json` the recovered solve is recorded at `sigma = 96389.90673255273`, residual
`2.047483451596032e-12`, `sigma_retries = 1`, with the failed attempt preserved beside it in
`sigma_ladder`.

**THE RULE.** Any solve reporting residual `> 1e-6` is **INVALID** and must be retried down the
descending ladder `sigma x {1, .996, .992, .988, .984, .980}` until a solve reports residual
`<= 1e-6`. **A result carries its residual as part of the result.** A result without a recorded
residual, or with residual `> 1e-6`, **may not be banked, scored, or cited** — the number is not
"probably fine", it is not a result.

**Implementation status, stated honestly.** The rule is implemented in
`tools/host/sparse-probe/axis_sweep.py` (ladder at `:180`, `sigma_retries` and the full `sigma_ladder`
recorded per mesh at `:209`-`:211`). It is **NOT yet implemented** in
`tools/host/sparse-probe/high_res_sweep.py`: that script carries a single shift and no retry ladder, so
`T4c`'s registered ladder cannot be evaluated honestly until §4 is implemented there. This is recorded
as an open item, not as a caveat on results that do not exist yet.

**Scope of the hazard, measured.** The banked campaign meshes are **unaffected**: residuals `1e-11` to
`6e-11` (`M5` `1.3817866142195237e-11`, `M1` `1.100478257696839e-12`, `M2`
`3.551986947354624e-12`, `M3` `3.2639272825896974e-12`, `M4` `6.061053364772882e-11`), verified in
the campaign JSONs and in `mode_overlap.json`. `sigma` is not otherwise a confound: over `sigma`
`96100`-`96777` with a genuine solve, `R` varies by at most `6e-12` and `lambda` by at most `4e-10`. The
shift moves where the spectrum is translated, not the answer — which is exactly why a bad shift can be
detected by the residual and cured by moving it.

## 5. Boundary clause

**NO existing criterion is changed by this document, and none is reinterpreted. `T4_amp` remains FAIL
(Physics). No allowance is introduced or modified. `|Q - 1| <= 0.10`, on `R_extracted` in
`[2.52909192487721, 3.09111235262770]`, is UNTOUCHED everywhere it applies. Nothing here lowers a bar:
`T4b` and `T4c` are ADDITIONAL tests that can fail, not replacements that excuse `T4_amp`, and a
`T4b`/`T4c` pass would not change the `T4_amp` verdict. Any change to an existing acceptance criterion
remains the project owner's decision, and this document makes none.**

## 6. Falsifiability summary

| test | registered condition | what a failure looks like |
|---|---|---|
| `T4b` (conductor shape, `e_z_vv`) | `min` over the 10 mesh pairs of `\|corr\|` in the 31 x 76 strip slab `>= 0.99` | any off-diagonal pair at `\|corr\| < 0.99`; today's `min` is `0.9988226233736953` on `M5`-`M2`, so one pair dropping `0.0088` fails it |
| `T4b` (`e_y` clause) | `min` over the 10 pairs in the 30 x 77 slab `>= 0.98` | any pair at `\|corr\| < 0.98`; today's `min` is `0.985637534849262` on `M5`-`M3`, i.e. `0.0056` of margin, and this is the clause expected to fail first |
| `T4c` | `lambda` monotone in `free_e` and `\|d lambda / lambda\| <= 1e-4` per step, over the `40k`/`50k`/`60k` ladder | any step exceeding `1e-4` relative, or `lambda` moving the wrong way, on any rung; the `z` axis already reverses at `1.19e-05` on the low-resolution sweep, so the monotone half is the one at risk |
| §4 invariant | every banked solve records its residual, and residual `<= 1e-6` | a solve quoted without a residual, or with residual `> 1e-6` and no ladder retry; the `43/34/34-17-17` lock-on at `9.89e-01` is the worked example of what the rule exists to catch |

## 7. Open items this document does not close

1. `high_res_sweep.py` has no sigma ladder (§4) — required before `T4c` can be evaluated.
2. `T4c`'s ladder is prepared and unrun (§3.4) — no `40k`/`50k`/`60k` mesh exists.
3. No banked step meets `1e-4` (§3.4) — the threshold is a target, not a description.
4. `T4b` is mesh-independence, never accuracy (§2.4) — the accuracy question stays with `T4_amp` and with
   the dense Route-C reference, where the meshes sit at `~0.97`, not at `0.99`.
