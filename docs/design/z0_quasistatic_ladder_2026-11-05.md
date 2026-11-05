# Quasi-static `Z0` refinement ladder — 2026-11-05 (Dispatch 10)

Read-only analysis. No source change, no host run, no commit. One new doc (this file) plus one row in
`docs/design/dispatch_log.md`.

## 1. Context

The anchor question of `docs/design/anchor_audit_2026-11-05.md` is a one-line arithmetic problem that
cannot be closed until `Z0` is known: the series-`R` reference is `50 / (2*Z0 + 50)`, and the seven
`Z0` candidates on record span 47.36 – 50.09 ohm, i.e. 5.6 % in `Z0` and 2.5 % in the anchor. The
audit graded the *sensitivity* (`d ln|Gamma| / d ln Z0 = -0.65535`, so a 1 % error in `Z0` is 0.66 %
in the anchor) but it did not produce an eighth, independent `Z0`; that is this dispatch.

The candidates, exactly as they stand in their own artefacts (quoted verbatim from the audit's §2
table; none is re-derived here):

| # | candidate | value [ohm] | provenance |
|---|---|---|---|
| 1 | modal, quasistatic box (`n_clean`=200, `n_air`=200) | `50.088` | `emfit/mode_profile.py:586-596`, pinned by `tests/test_mode_profile.py:29-33` |
| 2 | twin fitted `zc` | `47.53661998575833 + j1.9309048088852248` | twin branch of the POST artefact |
| 3 | station fit @ `beta_base` | `47.3641 + j1.6450` | `run.station_fit` of the POST artefact |
| 4 | station fit @ `beta_rawphase` | `47.9250 + j1.8768` | refit from banked station phasors |
| 5 | station fit @ `beta_hammerstad` | `47.9415 + j1.8837` | refit from banked station phasors |
| 6 | TE | `47.54` | in no artefact (`complex_load_analysis_2026-11-04.md`) |
| 7 | `z0_model` | `48.0987` | library line model |

Measured `|Gamma_port| = 0.3255649` (two-wave `|B/A|`, POST arm). Reference numbers held fixed for the
whole document, not recomputed:

* `k0 = 122.14137132890411` rad/m
* converged quasistatic `eps_eff = 3.35001` at `n_clean` = `n_air` = 200 (`emfit/mode_profile.py:588-596`;
  `tests/test_mode_profile.py:29-33`), treated as validated and not re-litigated here
* modal `Z0 = 50.088` ohm — the only candidate carrying an error bar (~1 %)
* anchor at `Z0 = 50.088`: `50/(2*50.088+50) = 0.332942`

## 2. Method

The library's own quasi-static solver, no new code. `emfit/quasistatic.py:334`
(`z0_eps_eff(grid, eps_r=1.0, fixed=None) -> (Z0, eps_eff)`) returns
`eps_eff = C'/C'_air` and `Z0 = sqrt(eps_eff)/(C0*C')`, which is `1/(C0*C'_air)`
(`emfit/quasistatic.py:25-26`, `:337-341`); `C' = phi^T K phi / (V^2 length)`
(`emfit/quasistatic.py:20-22`, `:318-320`), `length` read off the grid and never chosen by the caller
(`:262`, `:304-308`).

The mesh constraint is enforced, not assumed: **exactly one** periodic axis (the line axis) and
**one cell thick** along it (`emfit/quasistatic.py:28-30`, guard at `:95-112`), transverse nodes from
`node_shape` (`:116`), flat indices from `node_index` (`:127`). The grid is therefore built by the
*same* code path `emfit/mode_profile.py` uses, not by a copy of it: the section constructor
`_section(h, w, n_sub, n_clean, n_air)` (`emfit/mode_profile.py:447`) at
`emfit/mode_profile.py:467-469` — `Grid.uniform(1, ny, nz, cell, ny*cell, nz*cell,
periodic=(True, False, False))` with `ny = 2*n_clean + n_strip`, `nz = n_sub + n_air` — and the
conductor list `_conductors(grid, n_clean, n_strip, n_sub)` (`emfit/mode_profile.py:473-484`), which is
the call site's own pair of calls at `emfit/mode_profile.py:625-626`.

Geometry: production microstrip, `h = 1.6e-3` m, `w = 3.0e-3` m, `n_sub = 16` (cell = 0.1 mm, the FDTD
board's own cell), `eps_r = 4.4`, `n_clean` = `n_air` = `n`, `eps_r(x,y,z) = eps_r if z < h else 1`
substrate callable as at `emfit/mode_profile.py:627`.

Ladder rungs: `n` = 100, 200, 400, 800 cells of clean space laterally and above — 10, 20, 40, 80 mm of
box per side at 0.1 mm cells (`ny = 2*n + 30` for the 3 mm strip, `nz = n + 16` for the substrate), the
`n` = 200 rung being the production 20 mm box. *Correction added 2026-11-05, after the run; the frozen
sentence read "`n` = 100, 200, 400 … (5 mm, 10 mm, 20 mm at 0.1 mm cells)".* Two errors in that frozen
text: the half-width is `n * 0.1 mm`, twice the figures printed, and a fourth rung (`n` = 800) was added
at run time so that the fit had more points than parameters. Neither error touches a number: every `Z0`
in §3 is the solver's measured output at the stated `n`, and no bracket is phrased in millimetres.
**Validation rung first**: `n = 200` must reproduce `eps_eff = 3.35001` to a few `1e-4`;
if it does not, the grid this dispatch builds differs from `mode_profile`'s and every `Z0` below is
suspect — that is reported, not adjusted.

Convergence: `Z0(n) = Z0_inf + a/n^p` by least squares over the rungs, with Richardson at `p = 1`
reported as a cross-check. If the sequence is flat or noisy the fit is declined and the range reported.

## 3. Task A — the ladder

| `n_clean` × `n_air` | cells (`ny` × `nz`) | `Z0` [ohm] | `eps_eff` | wall clock [s] |
|---|---|---|---|---|
| 100 × 100 | 230 × 116 | 50.546918 | 3.392371 | 0.34 |
| 200 × 200 | 430 × 216 | 50.088467 | 3.350009 | 1.32 |
| 400 × 400 | 830 × 416 | 49.954238 | 3.337458 | 7.86 |
| 800 × 800 | 1630 × 816 | 49.917788 | 3.334033 | 120.7 |

Validation rung first, as promised: `eps_eff(200 × 200) = 3.350008519` against the recorded `3.35001`
— a gap of `1.5e-6`. The grid built here is `mode_profile`'s grid to every digit we can resolve, so the
ladder below is the same solver on the same geometry, not a lookalike. **PASS.**

Fit `Z0(n) = Z0_inf + a/n^p` by least squares over all four rungs (3 parameters, 4 points):

* `Z0_inf = 49.901498` ohm, `a = 2468.4`, `p = 1.79126`
* residuals `-6.0e-5 / +4.8e-4 / -1.1e-3 / +7.2e-4` ohm. The fit runs through the arithmetic floor, which
  is exactly why its covariance is not an error bar: the `±0.001695` such a fit reports is an artefact of
  4 points leaving 1 degree of freedom, and it is **not** quoted as an uncertainty anywhere below.
* `p` near 1.8 rather than 2 says the convergence is not cleanly second order and that the last two
  rungs are still creeping. That, not the covariance, is what sets the quoted window.

Cross-checks, all of which had to agree before the number was written down:

* 3-point fit on 100/200/400 only: `p = 1.772071`, `Z0_inf = 49.898667`; it predicts
  `Z0(800) = 49.914938` against the measured `49.917788` — `+0.0029` ohm, `+0.0057 %`, on a rung it
  never saw. The extrapolation is predictive at the `1e-4` relative level.
* Successive triples: `49.8987` (100/200/400) vs `49.9042` (200/400/800) — spread `0.0055` ohm, i.e. the
  limit moves 0.01 % when the window slides one rung.
* Richardson on the finest pair: `p = 1` → `49.8371`; `p = 2` → `49.9062`. The `p = 1` end is the
  pessimistic one and is the reason the window below is `49.899 – 49.904` rather than a symmetric bar.

**Quoted: `Z0_infinity = 49.90` ohm** (defensible window `49.899 – 49.904`).

Per-doubling drift: `-0.91 %` (100→200), `-0.27 %` (200→400), `-0.073 %` (400→800). Monotone, and still
falling at the finest rung. The sequence never flattens into the numerical floor — it is converging, but
the 20 mm box is not converged. That distinction is the whole of §7.

## 4. Task B — the ladder `Z0` against the seven candidates

`residual = (Z0_infinity - candidate) / candidate`.

Evaluated at the fit value `Z0_infinity = 49.9015`; using the tabulated `49.90` instead moves every
entry by less than `0.0003` percentage points.

| # | candidate | value [ohm] | residual [%] |
|---|---|---|---|
| 1 | modal | 50.088 | **-0.372** |
| 2 | twin `zc` (real part) | 47.5366 | +4.975 |
| 3 | station `beta_base` (real part) | 47.3641 | +5.357 |
| 4 | station `beta_rawphase` (real part) | 47.9250 | +4.124 |
| 5 | station `beta_hammerstad` (real part) | 47.9415 | +4.090 |
| 6 | TE | 47.54 | +4.967 |
| 7 | `z0_model` | 48.0987 | +3.748 |

Two clusters, and nothing in between that the ladder endorses. The six extraction-type candidates
(2–7) all sit `4.1 – 5.4 %` **below** the limit; the one modal candidate sits `0.37 %` **above** it. Note
also how *tight* the extraction cluster is: six independent extractions agreeing to within 1.3 % of each
other, all wrong by the same sign and nearly the same amount. That is a systematic, not a scatter, and
it is the finding of this dispatch — the ladder does not split the difference between the clusters, it
lands decisively on the modal side. This is bracket **Z1**, and it is why §5 exists.

## 5. Task C — what the "5.54 % residual" becomes under each `Z0`

Anchor `50/(2*Z0+50)`; residual of the measured `|Gamma_port| = 0.3255649` against it, in percent
(`(measured - anchor)/anchor`) and in dB (`20*log10(measured/anchor)`).

| # | `Z0` [ohm] | anchor | residual [%] | residual [dB] |
|---|---|---|---|---|
| 1 | 50.088 | 0.332942 | -2.216 | -0.195 |
| 2 | 47.5366 | 0.344654 | -5.538 | -0.495 |
| 3 | 47.3641 | 0.345475 | -5.763 | -0.516 |
| 4 | 47.9250 | 0.342818 | -5.033 | -0.449 |
| 5 | 47.9415 | 0.342740 | -5.011 | -0.447 |
| 6 | 47.54 | 0.344637 | -5.534 | -0.494 |
| 7 | 48.0987 | 0.342003 | -4.807 | -0.428 |
| — | `Z0_infinity` = 49.9015 | 0.333772 | -2.459 | -0.216 |

**The "5.54 %" is a property of the chosen `Z0`, not of the measurement.** The measured number is
`|Gamma_port| = 0.3255649` in every single row — it does not move, it is not re-derived, and no row
touches the phasors. The only quantity that changes down the table is the *reference*: the same
experiment scored against eight `Z0` values that are all on the record as defensible. A factor of 2.6
in the nominal residual (`-2.2 %` to `-5.8 %`) therefore lives entirely in the choice of denominator.

That is what makes the audit's headline `5.5 %` fragile rather than wrong: it was quoted against the
twin's fitted `zc` (row 2), which is one of the six extraction candidates the ladder now rejects. Against
the `Z0` the ladder actually endorses — either the production rung (row 1, `-2.216 %` / `-0.195 dB`) or
the converged limit (last row, `-2.459 %` / `-0.216 dB`) — the disagreement is half the headline size.

But note the *direction*, because it is the uncomfortable part: refining `Z0` downward from `50.088` to
`49.9015` makes the anchor **larger** (`0.332942` → `0.333772`) and therefore makes the residual **worse**
(`-2.216 %` → `-2.459 %`). The most accurate `Z0` on record is the one that disagrees most with the
measurement. `Z0` is not the missing 2.5 % — if anything the ladder has just removed it as a suspect and
left the residual more stubbornly unexplained than before.

## 6. Pre-registered brackets (frozen before the run)

**Z1** `Z0_infinity` within 1 % of the modal 50.088 ⇒ the modal value is right; the anchor is 0.332982,
the residual is −2.22 %, and the "5.5 %" was an artefact of using the twin's fitted `zc`.

> **Z1 — FIRED.** `Z0_infinity = 49.9015` sits `0.372 %` from `50.088`, well inside the 1 % band; the
deciding number is §4 row 1. The modal value survives as the right `Z0` to 0.4 %.

**Z2** `Z0_infinity` within 1 % of the station-fit cluster 47.36–47.54 ⇒ the fits are right and the
modal formula (or its box) is off; the residual question becomes a modal-formula question, not an
extraction question.

> **Z2 — NOT FIRED.** The nearest edge of the `47.36 – 47.54` cluster is `+4.97 %` away (twin `zc`, §4
> row 2); the station fits and TE are `4.1 – 5.4 %` away. That is an order of magnitude outside a 1 %
> band. "The fits are right and the modal formula (or its box) is off" is rejected.

**Z3** `Z0_infinity` in 48–50, between the two clusters ⇒ both are wrong-ish; the anchor is
intermediate and the residual is intermediate; document it honestly rather than picking a side.

> **Z3 — fires literally, does not fire in intent.** `49.9015 ∈ [48, 50]` is true as set membership,
> but Z3 was written to catch the case where the limit lands *between the two clusters*. It does not:
> `49.9015` is `0.37 %` from the modal value and `4.97 %` from the nearest extraction candidate — it is
> inside the modal cluster, not between clusters. Recorded true-as-written and false-in-intent; see the
> bracket-set defect below.

**Z4 (falsifier)** `Z0_infinity` outside [44, 52] ⇒ the quasi-static solver or the geometry is wrong,
which contradicts the `eps_eff` agreement; escalate.

> **Z4 — NOT FIRED.** `49.9015` is 2.1 ohm clear of the lower edge of `[44, 52]`. The falsifier did not
> trigger; the `eps_eff` agreement is not contradicted and nothing needs escalating.

Each bracket is marked FIRED / NOT FIRED with the deciding number when the ladder is filled. An
unfired bracket set is a legitimate result.

| bracket | verdict | deciding number |
|---|---|---|
| Z1 | **FIRED** | `-0.372 %` from `50.088` (band `±1 %`) |
| Z2 | NOT FIRED | nearest edge `+4.97 %` (band `±1 %`) |
| Z3 | literally true, intent false | `49.9015 ∈ [48, 50]`, but not between clusters |
| Z4 | NOT FIRED | `2.1` ohm inside `[44, 52]` |

### 6.1 Two defects found in the frozen bracket set

Both are recorded here rather than silently repaired. The frozen text above is retained unedited; the
ladder's numbers do not depend on either.

1. **Z1 and Z3 cannot both be exclusive.** Z1's 1 % band around `50.088` is `[49.887, 50.589]`; Z3's
   interval is `[48, 50]`. They overlap on `[49.887, 50.000]`, so any limit in that overlap satisfies
   both brackets simultaneously. The frozen set was therefore not a partition, and the run landed in the
   overlap (`49.9015`). Operative reading, stated before §7 is read: **Z1 governs** — it is the specific,
   discriminating bracket, and the overlap region is exactly the "modal side" of the question Z3 was
   asking. Z3 is reported as true-as-written, false-in-intent, and not used to soften Z1.
2. **Z1's printed anchor carries a transposed digit.** *Clarification added 2026-11-05 after the run; the
   frozen text above is left as it was.* Z1 states "the anchor is `0.332982`"; the correct
evaluation at `Z0 = 50.088` is `50 / (2*50.088 + 50) = 0.332942`. The residual Z1 quotes (`-2.22 %`)
   is consistent with the **correct** figure (§5 row 1 gives `-2.216 %`), so only the printed anchor digits
   are wrong, not the arithmetic behind the bracket or its firing verdict. A second, substantive point:
   Z1 froze the *rung* `Z0 = 50.088`, not the limit. Scored at the limit the anchor is `0.333772` and the
   residual `-2.459 %` (§5, last row) — so Z1's "`-2.22 %`" is a rung-number, and §7 quotes both.

## 7. Verdict

1. **`Z0` is no longer the open question.** Four rungs of the library's own quasi-static solver — the same
   grid, on the same geometry, reproducing the recorded `eps_eff` to `1.5e-6` — converge to
   **`Z0_infinity = 49.90` ohm** (window `49.899 – 49.904`), quoted as a window rather than a `±` because
   the fit's covariance is not an error bar (§3). That is **0.37 % below** the production modal `50.088`
   and **4.1 – 5.4 % above** every extraction candidate on record (§4). Bracket Z1 fired; Z2 and Z4 did
   not fire; Z3 fired only literally, and the Z1/Z3 overlap is logged as a defect in the frozen set
   (§6.1). The record's assumption that `Z0` was soft to 5.6 % is now resolved in favour of the modal side,
   and any future work that starts by re-fitting `Z0` from the measured phasors is starting from a bias.

2. **But the anchor question is *not* closed, and the ladder made it slightly worse.** At the limit the
   anchor is `0.333772` against the measured `0.3255649` — a residual of **`-2.459 %` / `-0.216 dB`**,
   still about **2.5× the 1 % bar**, and larger than the `-2.216 %` the modal *rung* gives (§5). Refining
   `Z0` downward enlarges the anchor and therefore enlarges the disagreement: the most accurate `Z0` on
   record is the one that disagrees most with the measurement. `Z0` is thus **excluded** as the explanation
   of the residual, not confirmed as it — that is a real gain, but it is a negative result, and the ~2.5 %
   has to be explained by something else.

3. **The live finding of this dispatch is the extraction bias.** Six independent extractions (twin `zc`,
   three station fits, TE, `z0_model`) land in `47.36 – 48.10` ohm — agreeing with *each other* to 1.3 % —
   while all sitting `4.1 – 5.4 %` on the same side of a limit established by an entirely different method
   that reproduces the same `eps_eff`. A common sign and a common magnitude across six differently-posed
   estimators is a **systematic**, almost certainly a shared model assumption (reference plane, series
   impedance, or the loss/radiation treatment they all inherit) rather than six coincidences of noise.
   That, not another decimal on `Z0`, is what the next dispatch should chase: the ladder has just made
   the extraction family the only remaining suspect with a magnitude big enough to matter.

4. **`50.088` is a 20 mm-box number and must never be quoted as an infinite-box result.** It is `0.91 %`
   high at `n` = 100, `0.37 %` high at `n` = 200, and still drifting `0.073 %` per doubling at `n` = 800 —
   it is a *rung*, not a converged value, yet `emfit/mode_profile.py:586-596` and the documents that cite
   it present it as converged. The fix is not a code change, it is a citation rule: quote either the rung
   with its box (`50.088 ohm @ n_clean = n_air = 200, 20 mm box`) or the limit (`49.90` ohm). Recorded as
   **DR-36** in `docs/design/defect_register.md`.

What would close the residual is not another `Z0`: it is an independent measurement-side frame (a
reference-plane / calibration check) that can move the measured `|Gamma_port|` itself. Until then the
honest statement of the anchor question is: reference `0.3338`, measured `0.3256`, `-2.46 %` / `-0.22 dB`,
with `Z0` no longer available as the explanation.
