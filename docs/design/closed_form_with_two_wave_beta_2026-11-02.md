# The closed form with the two-wave beta: what the data select

**Status:** analysis on recorded artefacts. Nothing re-run, no artefact modified.
**Date:** 2026-11-02
**Parent note:** `docs/design/strip_termination_design_2026-11-02.md` (the strip is PEC to the far wall, so L is a stub length, not a load-to-open distance).

## 1. The closed form

A series resistance R in a line of impedance Z0, shorted a distance L beyond the load:

    |b2/a1| = | t / (1 + r * exp(-2j * beta * L)) |
    t = 2*Z0 / (2*Z0 + R)          r = R / (2*Z0 + R)

**Z0 = 47.53662 ohm is stated, not fitted.** With R = 50 ohm that gives `t = 0.655346499`, `r = 0.344653501`, and `t = 1 - r` identically, so the family is bounded by 1 for every beta, Z0 and L. No artefact in this directory stores a scalar `z0`: the field is split into `line.z0_re` / `line.z0_im`, and the 47.53662 used here is an external choice. Its substitution is made visible in section 4 rather than left implicit.

## 2. Inputs, verified against the artefacts

**Arm A** - `evidence/termination/build_A_50ohm_v3_beta2wave.json`, every handed figure confirmed: `nx = 72`, `n_pml = 6`, `ix_port = 8`, `geometry.loads[0].column = 50`, `line.beta_two_wave = 231.55331672912826`, `line.beta = 286.35930483082825`, `line.beta_model = 223.35306683909533`, `s21.magnitude = s21.raw_magnitude = 0.7628473102840976`, `s11.magnitude = 0.32556486641109117`, `s21_plane_index = 51` (requested 51.0). Cell is 0.4 mm, so load-to-wall = 22 cells = 8.80 mm and load-to-PML-front = 16 cells = 6.40 mm.

**Arm D** - `evidence/termination/build_A_50ohm_v3b_c51.json`: `nx = 62`, `n_pml = 6`, `s21.magnitude = 0.7600910333803181` (handed 0.7600910, confirmed), `line.beta_model = 223.35306683909533` confirmed, and the two values not handed are `line.beta = 286.86868916283123` and `z0_re = 42.75850315700394`, `z0_im = -16.046149777568516`. **`geometry.loads` is `null` in this artefact**, so the cut column is not recorded; `ix_load = 50` is *inferred* from `s21_plane_requested = 51` and the writer's default of cut + 1. Load-to-wall = 12 cells = 4.80 mm, load-to-PML-front = 6 cells = 2.40 mm. D carries **no `beta_two_wave`**, so A's `231.55331672912826` is used as a **proxy - this is an assumption, not a measurement of D**.

**Sweep - a provenance correction.** The five handed magnitudes `0.7628473, 0.751789, 0.746155, 0.741876, 0.737832` are **not** in `build_A_50ohm_v3b_c5{1,3,5,7,9}.json`. They are in `build_A_50ohm_sweepN5{1,3,5,7,9}.json`, which lives on the **nx = 72** mesh and at planes 51/53/55/57/59, and they match those files to the seventh digit (`0.7517891786585884`, `0.7461547372364731`, `0.7418756393514595`, `0.7378317576531221`). The `v3b_c5*` files are a different, nx = 62 series and hold `0.7489356474942055`, `0.7434621158755802`, `0.6681161101336922`, `0.05460536142032808` for planes 53/55/57/59. The last two of those collapse because planes 57 and 59 sit at and past the clean boundary `nx - n_pml - 1 = 55`. This note uses the `sweepN*` series, which is the one the handed numbers came from and the one that is a clean single-variable sweep against arm A's own mesh.

## 3. Result table

Z0 = 47.53662 ohm, R = 50 ohm, cell = 0.4 mm. `beta_model = 223.353066839` rad/m; `beta_two_wave = 231.553316729` rad/m (A's value; on D it is a proxy).

| arm | L variant | beta variant | predicted | measured | rel error |
|---|---|---|---|---|---|
| A | wall, 22 cells (8.80 mm) | beta_model 223.353067 | 0.8234808 | 0.7628473 | **+7.948 %** |
| A | wall, 22 cells (8.80 mm) | beta_two_wave 231.553317 | 0.7784291 | 0.7628473 | **+2.043 %** |
| A | PML front, 16 cells (6.40 mm) | beta_model 223.353067 | 0.9695966 | 0.7628473 | +27.102 % |
| A | PML front, 16 cells (6.40 mm) | beta_two_wave 231.553317 | 0.9875963 | 0.7628473 | +29.462 % |
| D | wall, 12 cells (4.80 mm) | beta_model 223.353067 | **0.7593421** | 0.7600910 | **-0.098 %** |
| D | wall, 12 cells (4.80 mm) | beta_two_wave 231.553317 (proxy) | 0.7830278 | 0.7600910 | +3.018 % |
| D | PML front, 6 cells (2.40 mm) | beta_model 223.353067 | 0.5445227 | 0.7600910 | -28.361 % |
| D | PML front, 6 cells (2.40 mm) | beta_two_wave 231.553317 (proxy) | 0.5491054 | 0.7600910 | -27.758 % |
| A | wall, 22 cells | line.beta 286.359305 (fitted, not an anchor) | 0.5660185 | 0.7628473 | -25.802 % |
| A | PML front, 16 cells | line.beta 286.359305 (fitted) | 0.9071461 | 0.7628473 | +18.916 % |
| D | wall, 12 cells | line.beta 286.868689 (fitted) | 0.9452945 | 0.7600910 | +24.366 % |
| D | PML front, 6 cells | line.beta 286.868689 (fitted) | 0.5857950 | 0.7600910 | -22.931 % |

**Sanity check, and it passes.** D at L = 12 cells (4.80 mm), `beta_model = 223.35306683909533`, Z0 = 47.53662 computes to **0.7593420900**, i.e. 0.7593421 to the seven digits the check names (difference -9.7e-9, pure rounding of the target). The arithmetic in this note is therefore reproducing the same number the earlier hand calculation produced, independently, and the rest of the table is comparable with it.

**Sensitivity, so the Z0 substitution is not smuggled.** D's own impedance magnitude is `|z0| = sqrt(42.7585^2 + 16.0461^2) = 45.670214746`; A's is `45.258611480`. With Z0 = 45.670214746: D at 12 cells reads 0.7505703 (-1.253 % instead of -0.098 %), D at 6 cells 0.5341890 (-29.72 %), A at 22 cells 0.8162189 (+6.996 %). With A's own |z0| = 45.258611480: D at 12 cells 0.7485561 (-1.518 %), A at 22 cells 0.8145429 (+6.777 %). So substituting the "true" Z0 moves D's agreement from 0.1 % to 1.3 % but **does not change any conclusion**, and the PML-front variants stay 27-30 % away under every Z0.

## 4. Implication: wall or PML front

**Implication (amended 2026-11-02, after the data review).** The closed-form `t/(1 + r·exp(−2jβL))` predicts a strong L-dependence: A (L = 22 cells, 8.8 mm) and D (L = 12 cells, 4.8 mm) should differ by ≈8.3 % in |s21|. The measured values are 0.7628473 (A) and 0.7600910 (D) — **0.36 % apart**. The model's L-dependence is *absent from the data*. Two further mismatches confirm the same reading: the closed form gives a single scalar per configuration and cannot predict a per-plane curve, while the measured sweep drops 3.3 % across planes 51–59; and the −0.098 % agreement at D's single (L, β) pair is a point coincidence on a curve the data does not otherwise trace. **Consequence:** the wall-vs-PML question remains `[UNVERIFIED]` and is not resolvable at the pre-termination geometry. Resolving it requires the termination fix (dispatch 2), after which the relevant comparison is between measured |s21| and the terminated-line prediction `T = 2Z₀/(2Z₀+R)`, which does not depend on L because there is no downstream short. **The passivity ceiling argument is unaffected** — it uses no β, no Z₀, no L, and no reflector hypothesis — and remains the strongest single claim this investigation has produced. **This paragraph corrects an earlier draft** which read the D match as evidence for the wall-as-reflector hypothesis; the match is real at one point, the model's structure is not supported by the data, and the earlier draft's language should not be quoted.

**But the closed form is degenerate in beta times L, and that must be said plainly.** The prediction depends on beta and L only through the product `beta * L`, so any pair with a matching product returns the same number: A's wall/L = 22 at beta_model is the same prediction as 21 cells at 233.9 rad/m, or 19 cells at 258.5 rad/m. [UNVERIFIED] The wall-vs-front discrimination survives this degeneracy because moving the reflector from cell 22 to cell 16 changes the product by a factor 1.375 at fixed beta, which no plausible beta correction absorbs; but the *cell count* itself is not independently established by this data. What the data establish is "the reflector is well downstream of the load, at or near the far wall", not "exactly 22 cells at exactly 223.35 rad/m".

**The fitted beta disagrees with the beta the closed form wants, and this is the sharpest tension in the table.** `line.beta` is 286.359305 on A and 286.868689 on D; at those betas the closed form reads 0.5660185 and 0.9452945 against measured 0.7628 and 0.7601 - 25.8 % and 24.4 % out on opposite signs. The closed form wants 223-232 rad/m, the station fit gives 286-287 rad/m, and they cannot both be the propagation constant of this structure. [UNVERIFIED] Either the station fit is absorbing the stub, or the model's L is not the physical L. The termination fix in the parent note is the experiment that separates these: with the metal stopped at the PML start, the reflector distance becomes an independent geometric fact rather than a fitted one.

## 5. Cross-check against the sweep

The sweep is `build_A_50ohm_sweepN5{1,3,5,7,9}.json` (nx = 72, same mesh and same load as arm A), planes 51/53/55/57/59, measured `0.7628473 / 0.7517892 / 0.7461547 / 0.7418756 / 0.7378318`.

**The closed form does not trace it, and the honest reason is that it cannot.** The closed form is a single number for the transmission *through the load*; the span from the port to plane N is a matched, lossless length of the same line, whose magnitude is 1. So the model's prediction is **independent of N**: flat at 0.8234808 (beta_model, L = 22) or 0.7784291 (beta_two_wave, L = 22) across all five planes. The measured values are neither flat nor at that level - they fall monotonically by 3.3 % over the eight cells.

Two readings, both reported because neither wins:

* **Model as N-independent (correct reading):** predicted 0.8234808 at every N, measured 0.7628-0.7378, so the level is off by 7-11 % and the drift is unexplained. The drift is real but small, and small drift with a large level offset is what a residual standing wave looks like, not what a wrong beta looks like.
* **Model fed L = N - ix_load (the reading the question invites):** 0.4889, 0.5010, 0.5262, 0.5671, 0.6268 for N = 51..59 at beta_model - it **rises** by 28 % while the measurement falls, and it is 15-36 % low throughout. This reading is wrong on its face: L is the distance to the reflector, not the distance to the probe.

What the sweep actually reports is the wave *after* it has traversed plane N, in a line that is shorted at `nx`, so the reading is a forward wave plus a reflected one whose relative phase accumulates as `beta * (2 * (nx - N))`. A per-plane curve in this geometry is therefore a stub interference pattern, not a transmission. The sweep cannot validate or refute the closed form; it can only say that the structure is reflecting, which is the parent note's claim. Its real use is as the before/after instrument in the checkpoint plan: after the strip fix the residual drift should shrink or vanish, and the level should move toward the closed-form value at `L = nx_clean - ix_load`.
