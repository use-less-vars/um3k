# T4b / T4c — two new tests and one operational invariant, pre-registered: mesh-independence of the conductor field, eigenvalue convergence, and the residual-first rule

Pre-registration only. No solve, no gate run, no field reconstruction. Every figure below is a reading
from an artefact that already exists, named where it appears, or a quotient of two such readings.

**Status, 2026-10-28: this document now carries one result and one non-certification.** §3.5 reports
the `40k`/`50k`/`60k` ladder, now run, scored at the registered `1e-4` per step. §3.6 records what that
pass does not certify and does not reach. Everything else is the registration text as it was written, and
where a sentence below is now stale it is corrected **forward** — by a dated note placed beside the
original sentence, never by rewriting it, because a pre-registration that is edited after its result is
not a pre-registration. The intro above ("No solve, no gate run, no field reconstruction") therefore
describes this document **as registered**; it no longer describes this document as it stands.

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

**STATUS UPDATE, 2026-10-28: EVALUABLE, EVALUATED, PASS.** Three statements in this section are now
superseded, and they are named here verbatim rather than deleted, because the record of what was
registered before any mesh existed is the point of registering: "no mesh in that ladder has been solved"
(first paragraph), "**no banked step anywhere in the record meets `1e-4`**" (after the fine-end table),
and "**`T4c` STATUS: PRE-REGISTERED, NOT YET EVALUABLE**" (closing). The ladder has been run, and the
criterion scored in §3.5 is **this** criterion: `1e-4` per successive step over `40k`/`50k`/`60k`,
relative against the finer value, monotone in `free_e` — no widening of the bar, no re-scoping to another
ladder, no change of denominator convention, no allowance. The pre-run paragraphs above stay exactly as
written.

### 3.5 The registered ladder, run: `T4c` scores **PASS** at the registered `1e-4`

**Verdict: `T4c` PASS, at the original `1e-4` per-step bar, on the `40k` / `50k` / `60k` ladder it was
pinned to.** Two successive steps exist; **both** are inside the bar, by `9.68x` and `17.91x`; and
`lambda` is strictly monotone decreasing, which is the other half of the registered condition. No
denominator was changed, no step was dropped, no rung was added after the fact.

Source: `tools/host/sparse-probe/out_highres/high_res_sweep.json` plus one record per rung under
`points/` (`hi40k_nx835.json`, `hi50k_nx1043.json`, `hi60k_nx1251.json`), written by
`tools/host/sparse-probe/high_res_sweep.py`, `generated = 2026-10-28T04:59:35`, `executed = true`.
Environment as recorded: Python `3.12.15`, SciPy `1.18.1`, `threads = 1`, `mp_max_free_e = 40000`,
`shim_mode = auto`. Thresholds in force at the run: `max_free_e_hard = 120000`, `mem_headroom = 0.5`,
`max_rel_residual = 1e-8`, `residual_bar = 1e-6`, `q_bar = 0.1`, `r_analytic = 2.8101021387524523`.
**Refusals: `[]` — `0 of 3` meshes refused, `n_points_failed = 0`.**

| rung | mesh spec | `nx` | nodes | `n_edges` | `n_pec_edges` | free edges (offset) | `n_dof` |
|---|---|---|---|---|---|---|---|
| `40k` | `12/411/8-4-4` | `835` | `14195` | `40882` | `846` | `40036` (`+36`) | `53391` |
| `50k` | `12/515/8-4-4` | `1043` | `17731` | `51074` | `1054` | `50020` (`+20`) | `66705` |
| `60k` | `12/619/8-4-4` | `1251` | `21267` | `61266` | `1262` | `60004` (`+4`) | `80020` |

Three rungs, one cross-section (`strip 12`, `z` lobes `8-4-4`, `nz = 17`), `yair` growing
`411` -> `515` -> `619`, so `free_e` is linear in `nx` alone (`free_e = 48 * nx - 44`, recorded per
point as `law`, agreeing with the closed form at all three). The `free_e` offsets are not slack: `nx`
must be odd, so each rung lands a few edges above its nominal target. They change no arithmetic below.

**The criterion, scored step by step.** Convention as §3.2: `(lambda_next - lambda_prev) / lambda_next`,
relative against the finer value; the coarser denominator is printed beside it.

| step | `lambda` before | `lambda` after | absolute | relative (finer) | relative (coarser) | vs `1e-4` |
|---|---|---|---|---|---|---|
| `40k` -> `50k` | `95889.18208402561` | `95888.19176210178` | `-0.990321923833` | `1.0327881939e-05` | `1.0327775275e-05` | **PASS**, `9.68x` inside |
| `50k` -> `60k` | `95888.19176210178` | `95887.65639467127` | `-0.535367430508` | `5.5832778758e-06` | `5.5832467030e-06` | **PASS**, `17.91x` inside |

**`2 of 2` steps meet `1e-4`; `lambda` is strictly monotone decreasing; the direction half of the
condition is satisfied on every rung.** Whole-ladder spread: `95889.18208402561 - 95887.65639467127 =
1.52568935434` absolute, `1.591096431507866e-05` over `max` and `1.591121747789216e-05` over `min` —
i.e. the entire three-rung ladder moves less than **one fifth** of a single step's allowance
(`0.159x` of `1e-4`). The two rungs are `9.681x` apart in `free_e`; the answer moves `1.6e-05`.

**What "PASS" means here, and nothing more.** It means the registered convergence condition is met on
the registered ladder. It is scored on `lambda`. It says nothing about `R` (§3.6), nothing about
`T4_amp`, and nothing about accuracy against a dense reference — each rung records
`anchor = None` with `anchor_note`: no dense anchor exists above `~3000` free edges, so every verdict
here is `SELF_CONSISTENT` (residual, enlarged-pencil residual, and the `x2 == D_c^T x1` identity), not a
reproduction of a reference eigenpair. Self-consistency per rung, as recorded:

| rung | residual | residual, enlarged pencil | `x2` vs `D_c^T x1` (rel.) | `eps_eff` |
|---|---|---|---|---|
| `40k` | `1.5527873334932968e-12` | `6.312744455557535e-19` | `9.072127188276239e-13` | `3.5573962895705598` |
| `50k` | `2.152731713758068e-12` | `6.111586526973199e-19` | `4.719296257601582e-12` | `3.5573595495811183` |
| `60k` | `2.5489994505965004e-12` | `5.423777957245537e-19` | `1.862700857955338e-12` | `3.5573396879651416` |

Cost and shape, for the record and not as a criterion: `nnz_S` `596655` / `745583` / `894511`, factor
`nnz` `3482697` / `4353648` / `5218009`, fill per row `65.23981417305134` / `65.27697728465402` /
`65.21940580199232`, factor memory `0.041792364` / `0.052243776` / `0.062616108` GB, `t_splu`
`0.27513273898512125` / `0.30346789001487195` / `0.38073511503171176` s, `t_eigsh` `0.38941675692331046`
/ `0.5035539170494303` / `0.5699685489526019` s, `opinv_calls` `21` at every rung, `wall_s` `4.9` /
`5.74` / `6.22` (`child_wall_s` `5.59` / `6.62` / `7.09`, `wall_s_total` `19.3`), `peak_rss_mib` `237.7`
/ `279.9` / `315.7` (`peak_rss_mib_max` `315.7`). Memory was never the constraint: the hard guard is
`120000` free edges and the largest rung is `60004`.
**`wall_s` and `peak_rss_mib` are load-dependent; the numerics are not.** These figures were measured
on a loaded host (`loadavg` `~2.9` on `12` cores); the identical code on an idle host gave `wall_s`
`2.21` / `2.35` / `2.43` and `peak_rss_mib` `236.0` / `268.5` / `307.8`, i.e. `~2.6x` less wall for the
same numerics — `lambda`, `R`, `residual` and `sigma` are **bit-identical** between the two runs. The
cost figures here are therefore an **upper bound measured on a loaded host**, and what the gate scores
is the numerics, not the timings.

**The bar that was authorised in advance and deliberately not used.** Before this run the bar `2e-4` was
authorised, on the strength of one neighbouring number: the campaign's finest step, `M3` -> `M4`, at
`1.0504460136124583e-04`, is `5.0 %` above `1e-4`. **That authorisation was not used.** The ladder passes
at `1e-4` with `9.7x` and `17.9x` to spare, so moving the bar would have bought nothing and cost the
result its meaning: a bar relaxed because a *different* mesh pair missed it by `5 %` is a bar aimed at a
number, not at a regime. `2e-4` is recorded here as **authorised, not adopted, and not needed**. If this
ladder had come in between `1e-4` and `2e-4`, the verdict would have been FAIL and `2e-4` would still not
have been applied in this document; that would have been a decision for the project owner, named as such.

### 3.6 What the pass does not certify: `R` does not converge, and the campaigns are not one ladder

**This section is not a caveat and it is not a hedge: it is the other half of the measurement.** The
eigenvalue converges beautifully on this ladder. The energy ratio does not converge at all, is not
monotone, and is `12`-`15 %` above the analytic value at every rung. Both facts come from the same three
solves. Quoting the first without the second would be quoting half a solve.

| rung | `R_extracted` | vs `R_analytic` `2.8101021387524523` | `Q` | `\|Q - 1\|` | `\|Q - 1\|` vs the `0.10` bar |
|---|---|---|---|---|---|
| `40k` | `3.184188500254623` | `+13.312 %` | `1.1331219802808472` | `0.13312198028084724` | `1.3312x` outside |
| `50k` | `3.2242746409436047` | `+14.739 %` | `1.1473869922660622` | `0.14738699226606217` | `1.4739x` outside |
| `60k` | `3.153215686647681` | `+12.210 %` | `1.1221000273134392` | `0.12210002731343916` | `1.2210x` outside |

**`R` does not approach `R_analytic`.** It sits at `3.184` / `3.224` / `3.153` against `2.810`: flat,
non-monotone, with a hump at `50k` (`+1.258912 %` from `40k`, then `-2.203874 %` to `60k`). Endpoint to
endpoint `40k` -> `60k` is `-0.972707 %` **against the `40k` value** (`-0.982261 %` by this document's
finer-value convention) — the payload's own `trend.R_rel_change_first_to_last = -0.009727066599375415`
uses the coarser denominator there, unlike §3.2. **The payload's `trend.R_direction` reads
`"decreasing"`, and that label is an endpoint-only statement: the sequence `3.184` -> `3.224` -> `3.153`
is not decreasing.** The label is quoted here so it is not mistaken for a claim about the sequence.

**All seven meshes now measured are outside `|Q - 1| <= 0.10`.** These three at `0.1221`-`0.1474`; the
campaign's five at `0.2207`-`0.3043` (`M4` `0.22074353791060441` to `M2` `0.30429524231479066`). There is
no mesh in the record, at any resolution, inside the bar. Every rung here is `status:
solved_off_bar`, `ok: false`, `child_exit: 1` for exactly this reason — the eigenpair is self-consistent
and the ratio is off the bar. That is not a defect of the ladder; it is the measurement.

**`lambda` converging while `R` does not is not a contradiction, and it is not a resolution either.** It
is the live tension that `T4` work has to confront: the eigenvalue is a property of the discrete operator
and settles as the operator settles, while `R` is a weighted ratio over three regions whose ratios differ
by `~40x` and whose weights are mesh-dependent (§1). A converged eigenvalue does not make `R` converged,
and a `T4c` PASS must never be quoted as support for `T4_amp`. **`T4_amp` remains FAIL, in Physics, at
`44.09 %`, with `|Q - 1| <= 0.10` on `R_extracted` in `[2.52909192487721, 3.09111235262770]` untouched.**
The pass moves no other row in §6 and no clause in §5.

**`R`'s non-monotonicity is not solver noise.** Every rung's eigenpair is self-consistent to `~1e-12`
(table in §3.5), and the recorded mode correlations are stable in magnitude across rungs —
`corr_ez_vv` `+0.9744828302045693` / `-0.9745057271595093` / `+0.9745258112132862`, `corr_ey`
`+0.953368248307638` / `-0.9426999153519491` / `+0.9486238464730392`. The sign flips are the
eigenvector's global sign convention, not a mode change. The hump in `R` is in the measurement.

**The `M` campaign is not a ladder, and the two campaigns are not one sequence.** Recorded because it is
tempting to concatenate them and the concatenation is not licensed:

| step | `lambda` before | `lambda` after | absolute | relative (finer) | vs `1e-4` | vs `2e-4` |
|---|---|---|---|---|---|---|
| `M5` -> `M1` | `96752.51970084828` | `96617.80879700037` | `-134.710903848` | `1.3942657728e-03` | fail | fail |
| `M1` -> `M2` | `96617.80879700037` | `96501.43769607678` | `-116.371100924` | `1.2059001783e-03` | fail | fail |
| `M2` -> `M3` | `96501.43769607678` | `96431.67757422743` | `-69.7601218494` | `7.2341499810e-04` | fail | fail |
| `M3` -> `M4` | `96431.67757422743` | `96421.54901104893` | `-10.1285631785` | `1.0504460136e-04` | fail | **PASS** |

The campaign's diagonal has **four** steps, not three, and at `1e-4` it scores **`0 of 4`**; at `2e-4` it
would score **`1 of 4`**. So a campaign-scoped reading of `T4c` — had one been attempted — would have
failed at `1e-4` and still failed at `2e-4`. The relaxation that was authorised for the `s12` ladder would
not have rescued it, which is a second reason it was not applied: it would have moved the bar without
moving the verdict.

Why the campaigns are not one sequence, stated as arithmetic rather than as a caveat: (i) they are
different cross-sections — campaign `M4` is `58/44/35-17-18`, this ladder's `40k` is `12/411/8-4-4`; the
mesh is not the same object at a different `h`. (ii) The join is enormous: `M4` -> `hi40k` is
`(95889.18208402561 - 96421.54901104893) / 95889.18208402561 = -5.5518976745e-03`, which is **`52.85x`
the finest within-campaign step** (`M3` -> `M4`) and `537.56x` the first ladder step. A step two orders
larger than the steps being tested is a different sequence, not a next rung. (iii) The extrapolants
disagree: a least-squares line in `1/free_e` (the natural variable, `free_e` proportional to `h^-2`, using
each campaign's recorded `free_e` including the `+36`/`+20`/`+4` offsets) gives `96276.1533639126` for the
campaign's five points against `95884.5478902379` for this ladder's three — a difference of `391.605474`
in `lambda`, `4.08e-03` relative to the `s12` extrapolant, i.e. `41x` the `1e-4` bar and `395x` the actual
first ladder step. (In `free_e` rather than `1/free_e`: `96822.3920247657` vs `95892.1652776572`.) Two
campaigns whose extrapolants disagree by `41x` the bar cannot be pooled into one convergence claim. **This
is a secondary observation and it is explicitly not the register: `T4c` is scored on §3.5 and nowhere
else.**

**Hedges on §3.5-§3.6, all recorded in the payload's own `notes` and not repaired here.** (i)
`no_dense_anchor`: no dense QZ reference exists above `~3000` free edges, so nothing above is an
eigenvalue *comparison*; it is self-consistency only. (ii) `anisotropy`: `strip` and `z` are fixed while
`yair` grows, so the air box gets more elongated in `y` at every rung, and the `y`-drift in `R` cannot be
separated from an aspect-ratio drift — the `50k` hump is recorded, not explained or attributed. (iii)
`free_e_offset`: the nominal targets are unreachable exactly because `nx` must be odd; the offsets
`+36`/`+20`/`+4` are printed per point and change no arithmetic in this section. (iv) The two campaigns'
flags are **not** comparable and are not tabulated together: this ladder's per-point `ok` is `false`
because `ok` requires residual **and** `|Q - 1| <= q_bar`, while the campaign's `overall.self_consistent`
is `true` because it is residual-only; correspondingly the payload carries
`all_eigenpairs_self_consistent: true` beside `all_self_consistent: false`, and
`n_points_solved: 3`, `n_points_solved_off_bar: 3`, `n_Q_inside_bar: 0`, `n_points_ok: 0`. Reading either
flag as a verdict on the other campaign is a category error.

### 3.7 Observed convergence, recorded and explicitly NOT a gate

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

### 3.8 Falsification

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

**Now implemented, and still never exercised — a supersession, not an edit.** The paragraph above is the
state of the record when it was written and it stays as written. Two things have changed and neither is a
rewrite of it. (1) `high_res_sweep.py` now carries the ladder: every point record under
`tools/host/sparse-probe/out_highres/points/` carries `sigma_ladder` (a list, not a scalar),
`sigma_requested`, `sigma_used` and `sigma_retries`, and each rung records one ladder entry with its own
`sigma`, `lambda`, `R` and `residual`. (2) **The ladder was never exercised.** All three rungs solved on
the **first** attempt, at residual `1.5527873334932968e-12` / `2.152731713758068e-12` /
`2.5489994505965004e-12` — four to five orders inside the `1e-6` bar — so `sigma_retries = 0` and
`sigma_ladder` holds exactly **one** entry at every rung, with `sigma = sigma_requested = sigma_used =
96325.12746203788`. That figure is the seed from `seed_sigma`: `0.999 x 96421.54901104893` (the `beta_sq`
of `out_mesh/M4_fe30672.json`, `30672` free edges), chosen from `10` candidates as the nearest `out_mesh`
record to `30000` free edges, and each later rung chains `0.999 x` the previous rung's `beta_sq`.

**Stated bluntly: the retry path is implemented and EMPIRICALLY UNTESTED.** "The rule is now in this
script" is a statement about code. The only evidence in the record that a ladder retry actually recovers
a bad solve is still the `43/34/34-17-17` lock-on at `9.89e-01` and its recovery at `sigma = 96100`, and
that is one incident, one mesh, in `axis_sweep.py`. A `T4c` PASS computed on first-attempt solves is
therefore evidence about the ladder's convergence and **no evidence at all** about the retry path; the two
must not be quoted as one. The condition is not hypothetical — three rungs is three chances for it to
happen, and it did not, which is a fact about these three shifts, not about the rule.

**Scope, restated because it is now load-bearing.** The invariant still registers no physics test and
changes no number. It is now the precondition under which §3.5's three residuals are quoted at all, and
those three are quoted in full above for that reason.

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

**Status of this table at 2026-10-28.** The `T4c` row is the only row that has moved: it is now **scored
PASS** at its registered `1e-4`, on the `40k`/`50k`/`60k` ladder, `2 of 2` steps, `9.68x` and `17.91x`
inside (§3.5). SUPERSEDED by section 8 of this file - do not cite this line as current. Both `T4b` rows are unchanged and remain unevaluated as registered, and the §4 invariant row
is unchanged. **`T4c`'s pass moves no other row**: `T4_amp` remains **FAIL** in Physics, and §3.6 records
that the same three solves sit `12`-`15 %` high on `R` and outside `|Q - 1| <= 0.10` by `1.22x`-`1.47x`, so
the `T4c` PASS must never be cited as support for `T4_amp` or for the `T4b` clauses.

## 7. Open items this document does not close

1. `high_res_sweep.py` has no sigma ladder (§4) — required before `T4c` can be evaluated.
2. `T4c`'s ladder is prepared and unrun (§3.4) — no `40k`/`50k`/`60k` mesh exists.
3. No banked step meets `1e-4` (§3.4) — the threshold is a target, not a description.
4. `T4b` is mesh-independence, never accuracy (§2.4) — the accuracy question stays with `T4_amp` and with
   the dense Route-C reference, where the meshes sit at `~0.97`, not at `0.99`.

**Status at 2026-10-28: items 1-3 are closed by measurement, item 4 is not.**

- **Item 1 — CLOSED.** The sigma ladder is implemented in `high_res_sweep.py` and recorded per point:
  `sigma_ladder`, `sigma_requested`, `sigma_used`, `sigma_retries` on every rung. It was **never
  triggered** — `sigma_retries = 0`, one ladder entry per rung (§4). Implemented is not tested; see §4.
- **Item 2 — CLOSED.** The ladder was run. Three rungs solved, `0` refusals, `0` failures, `n_dof`
  `53391`/`66705`/`80020` (§3.5).
- **Item 3 — CLOSED, in the other direction.** Two banked steps now meet `1e-4` with margin, not merely
  approach it: `1.0327881939e-05` (`9.68x` inside) and `5.5832778758e-06` (`17.91x` inside). The sentence
  this item records was true of the record before this run and is false of it now (§3.4 status update).
- **Item 4 — STANDS, and §3.6 attaches the same caution to `T4c`.** `T4b` is still mesh-independence and
  never accuracy. What is new is that `T4c`'s PASS needs the identical caution for the identical reason:
  self-consistency without a dense anchor is not accuracy, and a converged `lambda` is not a converged
  `R`. The pass is a convergence result and it certifies no physics (§3.6).

## 8. Dispatch 42 — `T4b` scored as new work, `T4c` cited by reference, two errata recorded append-only

**What this section is.** Dispatch 42 scores `T4b` from the cross-mesh overlap artefact, which no earlier
section scores; it cites `T4c`'s already-recorded PASS without restating it; and it records two errata
against text that is left standing. No existing line of this document is edited, reworded, renumbered or
deleted. Where this section and an earlier line disagree, both stay on the page and the disagreement is
named: a correction written over the record is a correction nobody can audit afterwards.

### 8.1 Provenance

Supplied with the dispatch, recorded unaltered. None of it is re-derived in this section.

- HEAD at time of writing: `d981e17`.
- `tools/host/sparse-probe/out_mesh/mode_overlap.json` introduced at commit `0a28615` ("sparse-probe:
  cross-mesh mode overlap -- the hump is NOT branch tracking").
- `T4c` PASS scored at commit `9b04455` ("T4c: score the eigenvalue ladder at its registered 1e-4 (PASS), ..."),
  on evidence `tools/host/sparse-probe/out_highres/high_res_sweep.json` plus the three points
  `tools/host/sparse-probe/out_highres/points/hi40k_nx835.json`, `hi50k_nx1043.json`, `hi60k_nx1251.json`.
- Registration commit for this document: `d74f6ce`.
- The artefact as scored: `27,282` bytes, sha256
  `95f21ebe8f7f26d1dbc44cac649eecea5cc12e5518d8cc32cf7b1dae7e3e19df`, written by
  `tools/host/sparse-probe/mode_overlap.py`.

**No calendar date is asserted for this section.** The artefact carries its own
`generated_utc = 2026-10-28T03:00:56Z`; that stamps the JSON, and it is quoted here in that role only.

### 8.2 `T4b`, scored: **PASS** on both clauses

**Registered thresholds, unchanged.** `e_z_vv`: `min` over the 10 pairs `>= 0.99` (`:94`). `e_y`: `min`
over the 10 pairs `>= 0.98` (`:119`). The registered statistic is the `strip_footprint` slab of §2.1 —
`Y0 <= y <= Y1 (+tol); row mask, all z` — masked to `31` rows for `e_z_vv` and `30` rows for `e_y`. No
threshold, region or definition was moved to score it, and the numbers below were recomputed from the
artefact rather than copied from §2.2 or from `:100`-`:112`.

| pair | `e_z_vv` at `strip_footprint` | `e_y` at `strip_footprint` |
|---|---|---|
| `M5`-`M1` | `0.99954204353945142` | `0.99780350156729081` |
| `M5`-`M2` | `0.99882262337369532` | `0.98894088905801447` |
| `M5`-`M3` | `0.99895580049367994` | `0.98563753484926198` |
| `M5`-`M4` | `0.99894149934256637` | `0.98708786933438752` |
| `M1`-`M2` | `0.99891402947726948` | `0.9905964431537051` |
| `M1`-`M3` | `0.99919052192113` | `0.98862869688521127` |
| `M1`-`M4` | `0.99917844746464868` | `0.9899229788322117` |
| `M2`-`M3` | `0.99931341005953978` | `0.99505334990176519` |
| `M2`-`M4` | `0.99937328561166217` | `0.99282464644427737` |
| `M3`-`M4` | `0.99994267018046767` | `0.99636376950559491` |

- **`e_z_vv`** — `min = 0.99882262337369532` at `M5`-`M2`; `max = 0.99994267018046767` at `M3`-`M4`;
  `spread = 0.0011200468067723568`; `margin = +0.0088226233736953263` against `0.99`. **PASS.**
- **`e_y`** — `min = 0.98563753484926198` at `M5`-`M3`; `max = 0.99780350156729081` at `M5`-`M1`;
  `spread = 0.012165966718028831`; `margin = +0.0056375348492619937` against `0.98`. **PASS.**

**Both clauses PASS.** The binding clause is `e_y`, exactly as `:512` expected it to be, and it clears
its bar by `0.0056` — the small margin is recorded rather than rounded. §6's two rows at `:511`-`:512`
recorded both `T4b` clauses as unevaluated; this section is their evaluation, and those rows are left as
they stand, so the status of `T4b` is read from the two places together.

**The exact command that produced every number above**, run from the repository root, output shown
nowhere and numbers transcribed above:

```bash
python3 - <<'PY'
import json, itertools
g17 = lambda x: '%.17g' % x
d = json.load(open('tools/host/sparse-probe/out_mesh/mode_overlap.json'))
LAB = d['labels']; S = {l: l.split('_')[0] for l in LAB}
PR = [(a, b) for a, b in itertools.combinations(LAB, 2)]
REG = 'strip_footprint'
THR = {'e_z_vv': 0.99, 'e_y': 0.98}
print('artefact   : tools/host/sparse-probe/out_mesh/mode_overlap.json')
print('generated  :', d['generated_utc'])
print('region     :', REG, '=', d['region_notes'][REG])
print('mask counts:', d['region_notes']['mask_counts'])
print('thresholds :', THR, '(preregistered)')
print('pairs      :', len(PR))
for f in ('e_z_vv', 'e_y'):
    M = d['pairwise_abs_corr'][f][REG]
    RA = d['reference_agreement'][f]
    rows = [(abs(M[a][b]), a, b) for a, b in PR]
    print('\n== %s @ %s ==' % (f, REG))
    for v, a, b in rows:
        print('   %-3s-%-3s %s' % (S[a], S[b], g17(v)))
    lo = min(rows); hi = max(rows)
    print('   min      %s  at %s-%s' % (g17(lo[0]), S[lo[1]], S[lo[2]]))
    print('   max      %s  at %s-%s' % (g17(hi[0]), S[hi[1]], S[hi[2]]))
    print('   spread   %s' % g17(hi[0] - lo[0]))
    print('   margin   %s   (min minus %s)' % (g17(lo[0] - THR[f]), g17(THR[f])))
    print('   verdict  %s (min against %s)' % ('PASS' if lo[0] >= THR[f] else 'FAIL', g17(THR[f])))
    cons = [(abs(M[a][b]) - max(abs(RA[a]), abs(RA[b])), a, b) for a, b in PR]
    np_ = sum(1 for r, a, b in cons if r >= 0)
    print('   consistency @ %s: npairs %d npass %d margin_min %s margin_max %s'
          % (REG, len(cons), np_, g17(min(r for r, a, b in cons)), g17(max(r for r, a, b in cons))))
    print('   fails    : %s' % (', '.join('%s-%s' % (S[a], S[b]) for r, a, b in cons if r < 0) or 'none'))
    G = d['pairwise_abs_corr'][f]['global']
    gl = [abs(G[a][b]) - max(abs(RA[a]), abs(RA[b])) for a, b in PR]
    print('   [global-domain recompute] npass %d margin_min %s margin_max %s'
          % (sum(1 for x in gl if x >= 0), g17(min(gl)), g17(max(gl))))
    print('   [stored consistency block] npass %d margin_min %s margin_max %s'
          % (d['consistency'][f]['npass'], g17(d['consistency'][f]['margin_min']), g17(d['consistency'][f]['margin_max'])))
res = [(e['residual'], e['label']) for e in d['meshes']]
print('\n== residuals (rule 4: <= 1e-6) ==')
for v, l in res:
    print('   %-3s %s  <=1e-6 %s' % (S[l], g17(v), v <= 1e-6))
print('   span %s .. %s ; all<=1e-6 %s' % (g17(min(v for v, _ in res)), g17(max(v for v, _ in res)), all(v <= 1e-6 for v, _ in res)))
print('\n== reference_agreement (range per field) ==')
for f in ('e_z_vv', 'e_y'):
    vs = list(d['reference_agreement'][f].values())
    print('   %s min %s max %s' % (f, g17(min(vs)), g17(max(vs))))
PY
```

### 8.3 What the pass certifies: mesh-independence, never accuracy

`T4b` compares meshes against each other. A pass says the conductor-region field is the same field on
every mesh in the set; it says nothing about whether that field is right, and §2.4 (`:127`) already says
so. The artefact measures the distance this test does not close: `reference_agreement` against the
analytic reference is `0.96650791654954193` to `0.97706884522780824` for `e_z_vv`, and
`0.96992994184855863` to `0.98595478750123633` for `e_y`. Mutual agreement at `0.9988` between meshes
that each sit near `0.97` with the reference is a statement about the meshes. The accuracy question stays
with `T4_amp` and with the dense Route-C reference, and this section moves neither.

### 8.4 §4's residual rule: satisfied `5 of 5`

The rule at `:452`-`:455`: any solve reporting residual `> 1e-6` is invalid and may not be banked, scored
or cited. The artefact carries one residual per mesh:

- `M5_ctrl_rung4` `1.3817866142195237e-11`
- `M1_fe11888` `1.100478257696839e-12`
- `M2_fe19665` `3.5519869473546238e-12`
- `M3_fe28980` `3.2639272825896974e-12`
- `M4_fe30672` `6.0610533647728821e-11`

All five are `<= 1e-6`: five of five, so every mesh in the `T4b` set is admissible to be scored at all.
This is a precondition, not a result; it certifies nothing about the answers.

### 8.5 `T4c` — cited by reference, not restated

`T4c` is **PASS** at its registered `1e-4`, recorded in §3.5 (`:244`) and scored at commit `9b04455` on
the `40k`/`50k`/`60k` ladder with the evidence files named in §8.1. This section does not restate that
verdict, re-quote its margins or re-score it, because a verdict recorded twice is a verdict that can
drift, and the second copy is always the one that gets cited.

### 8.6 Errata E1 — the stored `consistency` block is global-domain, and §2's statistic is not

`mode_overlap.json` carries a `consistency` block, quoted at `:141`-`:147` as `10/10` for `e_z_vv`
(`margin_min = 0.009012094703758966`) and `4/10` for `e_y` (`margin_min = -0.007177504813400626`,
failing `M5` x `{M2, M3, M4}` and `M1` x `{M2, M3, M4}`). Those figures are computed over the **global**
field domain, not over the `strip_footprint` slab that §2.1 registers as the statistic. Recomputed at
`strip_footprint` under the block's own definition,
`|corr(a,b)| - max(|corr(a,ref)|, |corr(b,ref)|) >= 0`:

| field | npairs | npass | `margin_min` | `margin_max` | failing pairs |
|---|---|---|---|---|---|
| `e_z_vv` | `10` | `10` | `0.021886955265871699` | `0.029370002975015019` | none |
| `e_y` | `10` | `9` | `-0.00031725265197435348` | `0.020968676452317814` | `M5`-`M3` |

**How the domain mismatch was identified, rather than inferred.** Recomputing the same definition from
the **global** matrix reproduces the stored block to the last digit in both fields — `10/10`,
`0.009012094703758966` / `0.021942535331667679` for `e_z_vv`; `4/10`, `-0.0071775048134006258` /
`0.013072794511649999` for `e_y`. The block is internally consistent; it is answering a different
question than the one §2 registers.

**What follows from this, and what does not.** The document understates itself: at the registered region
`e_y` is `9/10` with a single failing pair, not `4/10` with six. The error is conservative — the document
claims less than its own registered region supports — and **no verdict changes**: both `T4b` clauses are
`min` over pairwise absolute correlation (`:511`-`:512`) and never consult the `consistency` block, so
the PASS in §8.2 rests on numbers this errata does not touch. The block also remains unusable as an
accuracy check in either domain, for the reason `:147` gives. Lines `:141`-`:147` are left exactly as
written.

### 8.7 Errata E2 — the residual span at `:490` is too narrow at the bottom

`:490` states that the banked residuals span `1e-11` to `6e-11`. Three of the five values listed on the
following two lines are `1e-12`, not `1e-11`: `M1` `1.100478257696839e-12`, `M2`
`3.5519869473546238e-12`, `M3` `3.2639272825896974e-12`. The true span is `1.100478257696839e-12` to
`6.0610533647728821e-11`, i.e. `1.10e-12` to `6.06e-11`. The five listed values are right and the
sentence bounding them is wrong. Nothing gates on the span — the gate is `<= 1e-6` (§4) and it is
satisfied five of five (§8.4) — so no verdict moves either way. `:490` is left as written.

### 8.8 `T4_amp` — unchanged

`T4_amp` is **FAIL** (Physics) against `|Q - 1| <= 0.10` (`decisions.md:8176`), measured at `44.09 %`
(`decisions.md:8234`), and that bar is not moved, not widened and not re-scoped here; no re-run is
planned. A `T4b` pass cannot soften it: §5's boundary clause (`:498`) already forbids reading an
additional test as an excuse, and §8.3 says the same in the other direction.

### 8.9 Append-only note

This section was appended to the end of the document. No existing line was modified, reworded, renumbered
or deleted: the two errata of §8.6 and §8.7 point at the lines they correct instead of overwriting them,
and the `T4b` scoring of §8.2 stands beside §6's rows rather than replacing them.

