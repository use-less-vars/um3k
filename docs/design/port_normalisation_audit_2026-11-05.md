# Port normalisation audit — Stage A1: the chain to `|Gamma_port|` = 0.3255649

*Dated 2026-11-05. Stage A1 of a measurement-side audit. **This file's skeleton and the frozen
brackets below (§2) were written to disk BEFORE any code was read and BEFORE any arithmetic was done**, so
that the brackets cannot be adjusted after the numbers are seen. The audit that fills §3–§8 was performed
against them and was not permitted to move them. Read-only: no source edit, no FDTD run, no commit.*

## 1. Scope, method and what this audit is not

**Record audited (single leaf, pinned).** `evidence/termination/build_A_50ohm_p51_phasors.json`. This is the
only artefact carrying `/s11/station_phasors`, so it is the only one from which the measurement side can be
re-derived; its `s11` block is bit-identical to `build_A_50ohm_v3_betafix.json`. The audited number is
`/s11/magnitude` = **0.32556486641109117**.

**Premise correction (recording an earlier mis-attribution).** `build_A_50ohm_twin_p51.json` does *not* carry
the audited value: it carries `/s11/magnitude` 0.0489985288420461 @ 60.259986 deg, `gamma_plane` 0.0489985,
`line.z0` 42.43786214405251 ∓ j15.727993189312496, `line.beta` 286.359 against a model 223.353. The audited
value lives in `p51_phasors` / `v3_betafix` (and 17 further artefacts, per §7).

**Method.** Read-only, in this order: (1) the code path that writes the field, from the raw sample arrays to
the scalar (§3); (2) the termination the code actually builds (§4); (3) every `z0`/`zc` in the record and how
each is defined (§5); (4) the arithmetic that would be required to move the number by −4.90 % (§6); (5) a scan
for any second-frequency instance of the field (§7); (6) the phase path (§8). Grades against the §2 brackets
follow in §9 without any bracket being moved.

**What this audit is not.** It is not a fix, a re-run or a refit. No FDTD was executed, no source file was
edited, no commit was made. It does not adjudicate which `z0` is physically correct — it only records which
`z0` each number is computed from. It does not explain the +7.18 deg phase residual beyond the decomposition
already banked in `docs/design/beta_refit_test_2026-11-05.md`.

## 2. Frozen brackets — candidate causes, written before the audit

Framing, frozen with the brackets: the target is a **magnitude deficit of −4.90 %** (`|Gamma_port|` measured
**low**), with the phase residual left roughly where it is (**+7.18 deg**, measured s11 arg −100.499 deg
against a −107.68 deg reference).

| # | Candidate cause | What it predicts |
|---|---|---|
| **M1** | **Normalisation impedance.** The `zc` used in the A/B split is not the line's own modal `Z0` (different definition, or a fixed/stale value), so `B/A` is a pseudo-reflection scaled by a wrong impedance. | An essentially **CONSTANT** magnitude ratio across frequency; the phase moves only through the `gamma_v` rotation. |
| **M2** | **Inconsistent voltage/current sampling.** V and I are discretised on different supports (V a strip-cell line integral, I a loop enclosing a different flux), so the ratio is not `Gamma` even with the correct `zc`. | A ratio **constant in frequency but geometry-dependent**, and typically a phase error too. |
| **M3** | **De-embed / reference plane.** The de-embedding moves the reference plane or scales by a non-unit factor. | A ratio that **GROWS with frequency** (the error is in `beta*d`). |
| **M4** | **The load is not a 50 ohm series R.** The termination's realised impedance differs from its nominal value (lumped-element discretisation, staircase, sheet conductance) by ~7.9 %. | A magnitude error with **essentially NO phase error**; the error should be **insensitive to `Z0`**. |
| **M5** | **Wrong closed form.** `50/(2*Z0+50)` is the wrong formula for the topology actually built (e.g. shunt rather than series, or the reference plane of the formula is not the reference plane of the de-embed). | A residual with **no bug anywhere**; means the whole anchor question is mis-posed. |
| **M6** | **(falsifier)** The emitted `|Gamma_port|` is arithmetically what the code's own intermediate quantities imply, the load is a clean series R, and `zc` is the modal `Z0` — i.e. the measurement side is **CORRECT**. | The −5 % is a **physics effect not yet accounted for**; the audit must say so rather than manufacture a code defect. |

Grading is **FIRED / NOT FIRED / NOT TESTABLE**, each with its deciding number or line, in §9.

## 3. Q1 — The chain, raw fields to the scalar

**Q1 answer: the audited scalar is a voltage-series-only fitted reflection coefficient referred to z = 0. No
normalisation impedance enters it; de-embedding enters it as a unit-modulus rotation only — unit-modulus for the real `beta` this run uses; in general the factor carries `exp(-2*alpha*d)`, and `fit_beta` returns a real phase constant here, so `alpha = 0`.**

The chain has two distinct A/B splits and they must not be conflated.

**(a) The fitted split (station fit).** `emfit/ports.py:1429` `fit_station_impedance` calls, at `:1511-1518`:

```
amp_v, ... = _two_wave_fit(u, v, beta, alpha)
amp_i, ... = _two_wave_fit(u, i, beta, alpha)
z0      = complex(amp_v[0] / amp_i[0])      # :1516
 gamma_v = complex(amp_v[1] / amp_v[0])      # :1517
 gamma_i = complex(amp_i[1] / amp_i[0])
```

`_two_wave_fit` (`emfit/ports.py:1385`) does `phi = _fit_design(u, beta, 2, alpha)` then
`amps, *_ = np.linalg.lstsq(phi, series)`; at `alpha = 0` the basis is the `exp(∓j*beta*u)` pair, so the two
returned amplitudes are the forward and backward travelling amplitudes. Therefore:

- `z0` is **a fitted ratio `A_V / A_I`**, not a closed form and not a separately supplied `Z0` (`:1516`).
- `gamma_v = B_V / A_V` is computed **from the voltage series alone** (`:1517`). **No impedance appears in it,
  so no normalisation choice can scale `|gamma_v|`.** This is the line that decides M1 for this leaf.
- The docstring at `emfit/ports.py:1451-1456` states `z0` is positive only when `i` is forward-oriented (the
  caller negates the ground return).

`|gamma_v|` is banked as `/s11/magnitude_one_wave_station_fit` = **0.32588679434738205**.

**(b) The two-wave `fit_beta` split — the audited number.** `/s11/magnitude` = 0.32556486641109117 is
`s11_two_wave_mag`, recorded at `evidence/termination/run_build_A.py:1723` as the modulus of `B/A` from
`fit_beta(n_wave=2)`, referred to z = 0, plane-invariant at `alpha = 0`, **not de-embedded**. Its difference
from `|gamma_v|` is 3.22e−4 (0.10 %), i.e. the two estimators agree to a tenth of a percent.

**(c) The split that *does* use `zc` (a different quantity).** `emfit/studies.py:1282` `_wave_amplitude` returns,
at `:1294`, `0.5*(v + sign*zc*i)*exp(sign*gamma*x)`; `forward_wave_amplitude` (`:1297`, sign +1) and
`backward_wave_amplitude` (`:1354`, sign −1) give `A = 0.5(v + zc*i)e^{+gamma x}`, `B = 0.5(v - zc*i)e^{-gamma x}`.
Call sites `emfit/studies.py:3643-3650` (`[v_port], [-i_trunc]` at the port, `[v_cut], [i_cut]` at the cut) and
`:3653` (`gamma_plane = b_cut/a_cut`; 3654-3656 is the s21 branch, not `gamma_plane`). The `zc` source is `emfit/studies.py:3604-3607`
(`station_fit.z0`, else `reference.zc`, else raise); with a reference present the cut branch reuses
`reference.gamma` / `reference.zc` (`:3637-3639`). This path produces `gamma_plane`, banked as
`/s11_at_plane` = 0.05221997820357112 @ −119.27329211020283 deg — **a different, zc-dependent quantity, three
orders of magnitude away in phase and 6× in magnitude from the audited leaf.** It is not the audited number.

**(d) De-embed and propagation to metrics.** `emfit/ports.py:1673-1705` `deembed_reflection` computes
`out = gamma * exp(-2j*beta*distance)`. Distance banked = 0.0072 m. Magnitude-invariance is asserted in code at
`emfit/studies.py:3573-3575` (`abs(abs(gamma_port) - abs(gamma_measured)) < 1e-9`); the banked assertion
residual in `docs/design/beta_refit_test_2026-11-05.md` is `|Gamma_port| − |gamma_v|` = 5.6e−17. The scalar
reaches the metrics bin path at `emfit/studies.py:2037-2041` and is consumed as `abs(result.gamma_port)` at
`emfit/studies.py:4324, 4928, 5128, 5211`, fed from `:3953, 3986` (`v_port=v_port, i_port=-i_trunc,
 a_port=a_port, b_port=b_port` at `:3985`).

**Consequence for the audit.** The audited number is a fitted `B/A` from the voltage/field series with no
normalisation impedance in its definition, and the de-embed is unit-modulus for the real `beta` used here (in
general the factor carries `exp(-2*alpha*d)`, `emfit/ports.py:1690-1696`; this run's `fit_beta` returns a real phase
constant, so `alpha = 0`). Any candidate cause that
works by (i) choosing a different `zc` or (ii) scaling in the de-embed is therefore *arithmetically unable* to
change `0.3255649`. What can change it is the **basis** used for the fit — i.e. `beta` (§6).

## 4. Q2 — The load: what termination the code actually builds

**Q2 answer: a genuine 50.000 Ω series resistor interrupting the strip. The realised value is 50.000 Ω to
machine precision, not 7.9 % off.**

The topology is built in `emfit/studies.py:2882-2886`:

```
if load.kind == "series_r":
    edges = cc.idx_ex([ix_load], j_points, k_strip).ravel()
    pec[edges] = False
    # One element spread over the ``len(edges)`` parallel paths.
    sigma[edges] += 1.0 / (edges.size * float(load.value))
```

Three facts follow directly from those four lines:

1. **The strip is genuinely cut.** `pec[edges] = False` frees the PEC at the load column, so the two strip
   halves communicate only through the lumped element — this is a series element, not a shunt and not a
   sheet-conductance patch.
2. **The parallel split is compensated exactly.** Each of the `len(edges)` parallel E_x edges receives
   `sigma = 1/(N*R)`, i.e. is a resistor of value `N*R`; `N` such resistors in parallel give
   `R_eff = N*R / N = R = 50.000 Ω` exactly. The `edges.size` factor is precisely the correction that makes
   the staircase discretisation value-exact; there is no residual discretisation error in the nominal value.
3. **Geometry.** `ix_load` = column 50 (20.0 mm); the last fitted station is cell 47 (18.8 mm), so the nearest
   station sits 1.2 mm from the load — which is why the artefact records `load_station_excluded: true` and
   fits 8 of 9 stations (cells `[26,29,32,35,38,41,44,47]`, `span_m` 0.0084).

So a −7.271 % load error would require `load.value` itself to be wrong or the `series_r` branch not to be
taken. Neither is supported by the record: the built value is 50.000 Ω.

## 5. Q3 — `zc`: origin, value, and definition

**Q3 answer: `zc` is `A_V/A_I` from a two-wave least-squares fit to the eight station samples. Its value in
this artefact is 47.3641 + j1.6450 Ω. It does not enter the audited number (§3a).**

Every impedance in the record, with its origin:

| quantity | value (Ω) | where it comes from |
|---|---|---|
| `/run/station_fit/z0` | **47.364066848187235 + j1.6449807931078728** | `emfit/ports.py:1516`, `A_V/A_I` from the station fit — the `zc` actually used in the `gamma_plane` split |
| `zc` in the twin artefact | 47.5366 + j1.9309 | same definition, different run/mesh leaf |
| `z0_model` | 48.0987 | Hammerstad closed form (model, not measured) |
| modal `Z0` | 50.088 | modal/`eps_eff` route; `eps_eff` is **null** in the betafix artefact |
| board-width quasi-static limit | **48.023741** | `docs/design/z0_quasistatic_ladder_2026-11-05.md:382` (window 48.004–48.028) — the anchor of the −4.90 % (§6) |
| `/line/z0` in the artefact | 42.43786214405251 − j15.727993189312496 | **basis unstated**; differs from `/run/station_fit/z0` *in the same file*. Recorded as an unresolved inconsistency; not interpreted here, and not used by any candidate in §2. |

Note the shape of the distribution: the station-fit `z0` (47.36 + j1.64) is a *complex fitted ratio*; the modal
and quasi-static values sit at 48.02–50.09. **Nothing in the record is above 50.09 Ω**, which is the number
that decides M1 in §6.

## 6. Q4 — The reconciliation arithmetic

All arithmetic below is closed form; every input is a banked number (§3–§5).

**Step 0 — reproduce the target.** The anchor is `50/(2*Z0 + 50)` at the board-width quasi-static limit
`Z0 = 48.023741 Ω` (`docs/design/z0_quasistatic_ladder_2026-11-05.md:382`; carried in
`docs/design/defect_register.md:665,671`):

```
anchor  = 50/(2*48.023741 + 50) = 0.342354
measured= 0.3255649
residual= 0.3255649/0.342354 - 1 = -4.904 %      (=-0.437 dB)
```

The target is reproduced exactly. The `Z0` that would reproduce the measured value through the same closed form
is **51.7896** Ω (+7.84 % above the anchor) — see Step 1; the anchor is not a free parameter in this direction. (Board's own 20 mm box, `Z0 = 48.209081` → anchor 0.341488, −4.663 %; 3.0 mm limit,
`Z0 = 49.9015` → −2.459 %.)

**Step 1 — what size of `z0` error would produce −4.90 %?** From the sensitivity recorded in
`docs/design/anchor_audit_2026-11-05.md` (`d ln|Gamma| = -(1-|Gamma|) d ln Z0`, factor `1-0.342354 = 0.657646`; an earlier draft carried 0.65535 = 1-0.344654, which belongs to the superseded twin-`zc` anchor at 47.5366 ohm — a carried-forward stale sensitivity of the same class as DR-27):

```
d ln|Gamma| = ln(0.3255649/0.342354) = -0.050287
d ln Z0     = -0.050287 / -0.657646 = +0.07646  =>  Z0 would need to be 7.95 % HIGH  (51.84 ohm)
```

Solving the closed form exactly (`Z0 = 25/|Gamma| - 25`) gives `Z0` = **51.7896 Ω**, i.e. **7.84 % HIGH**; the
linear route above is the same statement to within the linearisation. No `z0` anywhere in the record exceeds
50.09 Ω (§5) and the largest candidate (modal 50.088) is only +4.30 % above the anchor — still **3.3 % short**
of the 51.7896 Ω that M1 would need. **A wrong `z0` cannot produce the observed deficit** — and, independently, the audited
number is `zc`-free (§3a, `emfit/ports.py:1517`).

**Step 2 — what size of load error would produce it?**

```
R/(2*48.023741 + R) = 0.3255649   =>   R_eff = 46.3643 ohm   (7.271 % LOW)
```

The code builds `R_eff = 50.000 Ω` exactly (§4, `emfit/studies.py:2882-2886`). **The load is not the cause.**

**Step 3 — the closure: the `beta` basis.** `|gamma_v| = B_V/A_V` is a fit against `exp(∓j*beta*u)`; the
value of `beta` sets how much of the standing wave is attributed to `B` rather than `A`. The banked
sensitivity sweep in `docs/design/beta_refit_test_2026-11-05.md` (§7.1, §9) is decisive:

| `beta` | source | `|Gamma_port|` | vs anchor 0.342354 |
|---|---|---|---|
| **231.5533** | station fit (banked `/line/beta`) | 0.32588679434738205 | **−4.81 %** |
| 223.5813 | raw-phase estimate | 0.3420459260106945 | −0.09 % |
| **223.3531** | Hammerstad `beta_model` | **0.34251672805157274** | **+0.048 %** |

The third row reproduces the anchor to **+0.048 %** — i.e. the −4.90 % deficit is *entirely* explained by the
fitted `beta` sitting **3.67 % above** the modal `beta_model` (231.5533 vs 223.3531; `231.5533/223.3531 - 1 =
+3.67 %`). This is a `zc`-free lever, consistent with §3a and §6-Step 1. It is not free money: the station data
*reject* the lower `beta` (`resid_v` 8.2× worse for `beta_model`), so the `beta` discrepancy is the open defect
— but it is a **`beta`-basis** defect, not a normalisation defect.

**Step 4 — the phase residual.** De-embedding moves the argument by exactly `-2*beta*d`
(`emfit/ports.py:1673-1705`) with `d = 0.0072 m`. The decomposition banked in
`docs/design/beta_refit_test_2026-11-05.md` splits the +9.06 deg `beta` move into **+6.577 deg** de-embed and
**+2.483 deg** `gamma_v` rotation; at the banked `beta` the residual is **+7.18 deg** (−100.499 deg measured
against the −107.68 deg TE s11 prediction, `docs/design/beta_refit_test_2026-11-05.md:29`,
`docs/design/anchor_audit_2026-11-05.md:27`). Magnitude and phase track the same lever.

**Net Q4 answer.** The −4.90 % is fully accounted for by the `beta` basis (residual +0.048 % after
substitution). No bracket M1–M5 fires, and M6's premise is *not* reached, because the deficit is no longer
unaccounted.

## 7. Q5 — Frequency leverage

**Q5 answer: NOT TESTABLE — there is no second frequency in the banked record.**

A scan for the value 0.32556486641109117 across `evidence/**` returned **19 artefacts**, and every one of them
is at `f = 5827786408.327286 Hz` with `excite = cw`. There is no sweep, no second frequency point, and no
`|Gamma|` vs `f` table anywhere in the banked evidence. Consequently the discriminate that M1 (ratio and
residual **constant** in frequency) and M3 (residual **growing** with `f` via `beta*d`) rest on **cannot be
applied from banked data**. This is a plain negative, not a soft statement: the data does not exist.

Q5's role in the audit is therefore (i) to record the absence, and (ii) to note that M1 and M3 were decided by
*code and arithmetic* instead — M1 by `emfit/ports.py:1517` (no impedance in `gamma_v`) plus the 51.7896 Ω
requirement in §6, and M3 by the de-embed, which is unit-modulus at `alpha = 0` (`emfit/ports.py:1673-1705`; in
general its magnitude is `exp(-2*alpha*d)`, `:1690-1696`) plus the 5.6e−17
magnitude assertion (`emfit/studies.py:3573-3575`). A future multi-frequency run is the cheapest independent
check on the `beta` closure of §6-Step 3 and is listed in §10.

## 8. Q6 — Phase

**Q6 answer: the phase residual is the same `beta` lever as the magnitude residual, plus the reference-plane
rotation; it carries no separate normalisation content.**

The banked phase is `/s11/phase_deg` = **−100.49921155605985 deg**, a **one-wave station fit at the port
plane** — not the two-wave phase (the artefact's basis string says so explicitly). The reference is the TE s11
prediction −107.68 deg (`docs/design/beta_refit_test_2026-11-05.md:29`,
`docs/design/anchor_audit_2026-11-05.md:27`), giving the frozen residual **+7.1808 deg**.

Two mechanisms, both already quantified and neither involving `zc` by way of a *magnitude* normalisation:

1. **De-embed rotation.** `arg -> arg - 2*beta*d`, `d = 0.0072 m`, `beta = 231.5533 rad/m`. Using the model
   `beta` instead moves the argument by +6.577 deg (`docs/design/beta_refit_test_2026-11-05.md`).
2. **`gamma_v` rotation.** The change of basis also rotates the fitted coefficient itself, +2.483 deg.

So the +9.06 deg total `beta` effect = +6.577 + +2.483 deg, and the residual at the banked `beta` is
+7.18 deg. Because de-embedding is unit-modulus at `alpha = 0` (`emfit/ports.py:1673-1705`; in general the factor carries
`exp(-2*alpha*d)`), the phase lever cannot be
construed as a normalisation-scaling bug: it is a *basis* effect, exactly as in §6-Step 3.

## 9. Grading table

Graded against the §2 brackets, which were not moved. Each grade carries its deciding number or line.

| # | Grade | Deciding number / line |
|---|---|---|
| **M1** | **NOT FIRED** | Two independent kills. (i) The audited number is `zc`-free: `emfit/ports.py:1517` `gamma_v = amp_v[1]/amp_v[0]` is computed from the **voltage series alone**; `z0` (`:1516`) never enters it. (ii) Even if it did, −4.90 % would need `Z0` = 51.7896 Ω, +7.84 % high (§6-Step 1); the largest `z0` in the record is modal 50.088 Ω (§5). |
| **M2** | **NOT TESTABLE** (for this leaf; no evidence of corruption) | The audited leaf never forms a V/I ratio. The V/I ratio exists only inside `z0` (`emfit/ports.py:1516`) and therefore only contaminates `z0` → `gamma_plane` (`emfit/studies.py:1294, :3653`), whose banked value is 0.05221997820357112 @ −119.273 deg — a different quantity (§3c). No independent support/loop evidence is banked, so the bracket cannot be tested here. |
| **M3** | **NOT FIRED** | `emfit/ports.py:1673-1705` `deembed_reflection` is `gamma * exp(-2j*beta*d)` — unit modulus for the real `beta` used here (in general the factor carries `exp(-2*alpha*d)`, `emfit/ports.py:1690-1696`; this run's `fit_beta` returns a real phase constant, so `alpha = 0`). Asserted in code at `emfit/studies.py:3573-3575` (`< 1e-9`), and achieved as 5.6e−17 in `docs/design/beta_refit_test_2026-11-05.md`. A unit-modulus map cannot produce a −4.90 % magnitude change at any frequency. |
| **M4** | **NOT FIRED** | `emfit/studies.py:2882-2886`: `series_r` → `pec[edges] = False` (strip genuinely cut) and `sigma[edges] += 1/(edges.size*load.value)`, so `R_eff = N*R/N = R = 50.000 Ω` exactly. Producing the measured value would need `R_eff = 46.3643 Ω` (7.271 % low, §6-Step 2). Realised error is 0.000 %. |
| **M5** | **NOT FIRED** (as a *form* error) | `50/(2*Z0+50)` **is** the correct closed form for a series `R` in a `Z0` line: `Gamma = R/(2*Z0+R)`, which at `Z0 = 48.023741` gives 0.342354 — matching the closure in §6-Step 3 to +0.048 %. (The `|(50-Z0)/(50+Z0)|` reading, 0.0194, is wrong for a series element.) The only defect ever present was the **`Z0` provenance** of the anchor, already audited and superseded at `docs/design/anchor_audit_2026-11-05.md:90-91` and resolved by the ladder value 48.0237 (`docs/design/z0_quasistatic_ladder_2026-11-05.md:382`). The anchor question is not mis-posed. |
| **M6** | **NOT REACHED** (premise fails; not an unaccounted physics effect) | M6 fires only if the deficit has no explanation. It has one: `beta_model` 223.3531 → `|Gamma_port|` 0.34251672805157274 vs anchor 0.342354 = **+0.048 %**, i.e. the −4.90 % is reproduced by the fitted `beta` sitting 3.67 % high (231.5533/223.3531) — `docs/design/beta_refit_test_2026-11-05.md` §7.1/§9. So there is no residual to name as unknown physics; the open item is the `beta` basis, which the station data itself contests (`resid_v` 8.2× worse at `beta_model`). |

**Summary verdict.** No bracket in the frozen set fires. The measurement side emits arithmetically what its own
intermediates imply, the load is a clean 50.000 Ω series R, and the de-embed is unit-modulus at `alpha = 0` — so the M6
*shape* of the answer holds — but the −4.90 % is not unexplained: it is the **`beta` basis** used in the
`B/A` fit, not a normalisation impedance and not the termination. The single most useful next step is to settle
`beta` (231.55 fitted vs 223.35 modal), because that is the one lever that moves both the −4.90 % magnitude and
the +7.18 deg phase.

## 10. What this audit did not reach, and what a later dispatch must compute

**Not reached — stated as negatives, not as gaps in effort:**

1. **Frequency leverage (Q5).** No multi-frequency banked `|Gamma|` exists: 19 artefacts carry the audited
   value, all at `f = 5827786408.327286 Hz`, all `excite = cw` (§7). The M1-vs-M3 frequency signature was
   never testable and was decided by code and arithmetic instead.
2. **`/line/z0` basis.** The artefact carries `/line/z0` = 42.43786214405251 − j15.727993189312496 while the
   *same file* carries `/run/station_fit/z0` = 47.3641 + j1.6450. The basis of `/line/z0` is unstated. This is
   recorded as an unresolved inconsistency and was not interpreted, because no §2 candidate consumes it.
3. **The two-wave phase.** Only the one-wave station-fit phase is banked (−100.49921155605985 deg); the
   two-wave phase that would pair with the audited `|Gamma|` is not stored, so the phase could not be compared
   like-for-like with the magnitude.
4. **No re-run, no refit, no source change.** Read-only audit; no FDTD executed. The `beta` closure relies on
   the *banked* sweep in `docs/design/beta_refit_test_2026-11-05.md`, not on new computation.

**A later dispatch must compute:**

1. **Settle `beta`.** 231.5533 (station fit) vs 223.3531 (Hammerstad) is a 3.67 % discrepancy that reproduces
   the whole −4.90 %; it must be adjudicated against the station residuals (`resid_v` 8.2× worse at the model
   value) — either the fit basis or the model is wrong, and the audit cannot tell which from banked data.
2. **A multi-frequency run of the same leaf**, to apply the M1/M3 discriminant that Q5 could not (§7):
   a constant residual confirms a basis/`zc` lever, a residual growing with `beta*d` would indicate the de-embed geometry — though with `alpha = 0` the de-embed
   factor is unit-modulus, so a magnitude residual can only grow through `exp(-2*alpha*d)`, not through `beta` alone.
3. **The `/line/z0` provenance** (item 2 above), which is currently an unlabelled impedance in the record and
   would silently corrupt any future comparison that assumes it means what `/run/station_fit/z0` means.
4. **Store the two-wave phase** next to the two-wave magnitude, so §8's comparison is like-for-like.

## 11. Corrections applied after an independent verification pass (A2), 2026-11-05

*An independent verification pass re-read every cited source line and re-derived every number in §6 and §9. It
found five defects in this document. All five are corrected in place in the sections above; they are listed here so
that a reader who saw the first version knows what changed, and so that the class of each defect is on the record
rather than in a maintainer's head.*

1. **A citation off by 14 lines.** The three lines of the fitted split (`z0`, `gamma_v`, `gamma_i`) sit at
   `emfit/ports.py:1516`–`1518` and the call range is `:1511-1518`, not at the numbers first cited, which were 14
   lines low; the docstring that states the forward-oriented-current condition is at `:1451-1456`, also cited 14
   lines low. A citation 14 lines out is not a rounding: it points at a region the author never read. Corrected in
   §3(a), §5, §6-Step 1, §7 and §9-M1/M2.
2. **A number that was never computed.** §6-Step 0 claimed that the `Z0` reproducing precisely −4.90 % was the
   anchor's own value to four decimals (48.0237 Ω), reported as "consistent with the anchor". That is the anchor
   quoted back to itself: the measured value is by construction the anchor times (1 − 4.9041 %), so a value that
   reproduces it and agrees with the anchor to four decimals is not an inversion of anything. Inverting the same
   closed form (`Z0 = 25/|Gamma| - 25`) gives **51.7896 Ω**, 7.84 % *above* the anchor — the opposite direction,
   and the one §6-Step 1 in fact needs. Corrected in §6-Step 0.
3. **A stale sensitivity.** §6-Step 1 used `1-0.342354 = 0.65535`. The correct factor is **0.657646**: 0.65535 is
   1 − 0.344654, the anchor of the superseded twin-`zc` leaf (47.5366 Ω), carried forward and never re-derived
   for this leaf. This is the DR-27 class of defect — a constant that was right somewhere else. Corrected in
   §6-Step 1, where the superseded value is now retained only as the provenance note.
4. **Minor roundings, all in the direction that flattered the conclusion.** The load that would reproduce the target
   is `R_eff` = **46.3643 Ω**, 7.271 % low, not the 7.24 % first printed; the baseline row of the §6-Step 3 closure
   table is **−4.8101 %**, not −4.82 %. Corrected in §4, §6-Step 2, §6-Step 3 and §9-M4.
5. **"Exactly unit-modulus" was an overstatement.** `exp(-2j*beta*d)` is unit-modulus only because this run's
   `fit_beta` returns a **real** phase constant; the general factor carries `exp(-2*alpha*d)` and is not
   magnitude-preserving (`emfit/ports.py:1690-1696`). `alpha = 0` is a property of this leaf, not an identity of the
   map. Qualified in §3, §7, §8, §9-M3 and §9's verdict. No grade moves, because for this leaf `alpha` is
   exactly 0 and the realised residual stays 5.6e−17.

**Net effect on the verdict: none of the six grades changes, and the M1 kill is strengthened** — the deficit would
need `Z0` = 51.79 ohm, against a largest value in the record of 50.088 ohm (modal), i.e. the record is 3.3 % short
of what M1 would require.

**Standing caveat, restated because it is the one place a reader may disagree with section 9.** The M6 grade of
NOT REACHED does not rest on a computation performed in this audit; it rests on the banked refit sweep in
`docs/design/beta_refit_test_2026-11-05.md`, in which moving `beta` from 231.5533 to 223.3531 reproduces the target
to +0.048 %. That same sweep records that the station data **reject** the lower `beta` (`resid_v` 8.2 × worse, and
the phase moving from +7.18 to +16.24 deg). The honest reading of the pair is narrower than "explained": **no
normalisation or termination defect exists on this leaf, and the magnitude residual is reproducible only through
the `beta` basis, which remains unadjudicated.** Settling `beta` is the compute that would turn this audit from a
decomposition into an explanation.
