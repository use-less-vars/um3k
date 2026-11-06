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

*Correction added 2026-11-05 (Dispatch 11), originals retained: the width in the sentence above is wrong
for the board it names. The production board is `w = 3.2e-3` m — `MS_W` at `emfit/studies.py:1159` with
`MS_N_STRIP = 8` at `:1197`, cell `h / n_sub` with `n_sub = 4` (`:1188`), and `/geometry/` in the artefact
agrees (`w` 0.0032, `n_strip` 8, `cell_m` 0.0004, `grid` 62x212x22). `3.0e-3` is
`W_CONVERGED` from `tests/test_mode_profile.py:64` (used at `:83`), a test fixture, not this board.
The ladder below is therefore a 3.0 mm solve; the board-width re-run is §9.*

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

   *Forward pointer added 2026-11-05 (Dispatch 11): this item is **withdrawn**, not qualified — the ladder
   was run at `w = 3.0e-3` m while the board is `3.2e-3` m wide, and the extraction cluster it calls a
   systematic is the board-width closed form. See §9, and §2's dated correction.*

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

## 9. Addendum 2026-11-05 — the ladder was run at the wrong width (Dispatch 11)

*Appended 2026-11-05. Nothing above this heading is edited: §1–§7 stand as written, including the
geometry line in §2. This section is the correction and the re-run it forces.*

### 9.1 Why — the width in §2 is not the board's width

The ladder above was run at `w = 3.0e-3` m. The board named in that same sentence ("the FDTD board's own
cell") is `3.2e-3` m wide. The two numbers are in the tree, and they are not the same number:

- `MS_W = 3.2e-3` (`emfit/studies.py:1159`) with `MS_N_STRIP = 8` (`:1197`); the board cell is
  `h / n_sub` with `n_sub = 4` (`:1188`, `:2801`), i.e. `0.4e-3` m, and `8 * 0.4e-3 = 3.2e-3`.
- The artefact agrees: `/geometry/` carries `w = 0.0032`, `n_strip = 8`, `cell_m = 0.0004`,
  `n_sub = 4`, grid `62x212x22`.
- The `3.0e-3` came from a **test fixture**, not from the board: `W_CONVERGED = 3.0e-3`
  (`tests/test_mode_profile.py:64`, used at `:83`) is the width the mode-profile convergence test is
  pinned to. `microstrip_mode_profile` itself takes `w` from its caller
  (`emfit/mode_profile.py:535-543`) and derives `n_strip = round(w / cell)` (`:458`), so `3.0e-3` is a
  legitimate argument — it is just not this board's.

The width is not cosmetic at this geometry. At `h = 1.6` mm, `eps_r = 4.4`, `t = 35` µm, the closed form
the tree already uses (`emfit/microstrip.py:141`) gives `Z0` = **49.9797** ohm at `3.0` mm and **48.0987**
ohm at `3.2` mm — **3.91 % apart** for a 6.25 % width change. And the ladder limit of §3, `49.9015` ohm,
sits **0.16 %** from the `3.0` mm closed form — i.e. the Dispatch 10 ladder reproduced the *wrong width's*
closed form to a sixth of a percent, which is exactly what a correct solve at the wrong width would do.
Meanwhile `z0_model = 48.0987`, the value §4 charges with a `+3.748 %` residual, **is** the board-width
closed form. §4 therefore compared a `3.0` mm solve against a `3.2` mm estimator and read the width
difference as an extraction bias.

### 9.2 Brackets, frozen before the run

Re-run: identical method (`emfit/quasistatic.py:334`, grid and conductors from `emfit/mode_profile.py`'s
own constructor), identical rungs (`n_clean = n_air = 100 / 200 / 400 / 800`), identical substrate
callable — only `w` changes, `3.0e-3 → 3.2e-3`, so `n_strip = round(3.2e-3 / 0.1e-3) = 32`.

- **W1** `Z0_inf(3.2 mm)` within 2 % of `48.0987` (i.e. `[47.13, 49.06]`) ⇒ the 6.25 % width difference is
  the whole story; the extraction cluster is right; the modal pair of record is a width artefact;
  **Dispatch 10 §7.3 is withdrawn**; the anchor is ~`0.3420` and the residual is back in the −5 % region —
  "the 5.5 %" stands and `Z0` is no longer excluded.
- **W2** within 1 % of `49.90` ⇒ width makes no difference in the solver, which contradicts the closed
  form's 3.91 %; the width story is wrong and §7.3 stands. Report it as a contradiction between two of our
  own tools; do not pick a winner.
- **W3** in between (`49.06 – 49.40`) ⇒ partial: width moves `Z0` by roughly half the closed-form amount;
  document honestly, no bucket.
- **W4 (falsifier)** outside `[46.5, 50.0]` ⇒ the solver or the closed form is wrong at board geometry;
  escalate, and write nothing exculpatory.

### 9.3 Task A′ — the ladder at the board width

| `n` | cells (`ny x nz`) | `Z0` (ohm) | `eps_eff` | wall (s) |
|---|---|---|---|---|
| 100 | 232 x 116 | 48.658870 | 3.412440 | 0.29 |
| 200 | 432 x 216 | 48.209081 | 3.369119 | 0.88 |
| 400 | 832 x 416 | 48.076346 | 3.356179 | 4.43 |
| 800 | 1632 x 816 | 48.040141 | 3.352632 | 27.82 |

Fit `Z0(n) = Z0_inf + a / n^p`: `Z0_inf` = **48.023741**, `a` = 2315.8844, `p` = 1.780906, residuals
−6.335e-5 / +4.988e-4 / −1.184e-3 / +7.482e-4. The covariance the fit prints (sd 1.769e-3) is an
over-fitting number, not an error bar, and is not quoted as one. `eps_eff` under the same form: limit
**3.350989**, `a` = 208.6959, `p` = 1.765468, residuals −6.9e-6 / +5.4e-5 / −1.3e-4 / +8.0e-5.
Per-doubling drift, `Z0`: −0.9244 % / −0.2753 % / −0.0753 %; `eps_eff`: −1.2695 % / −0.3841 % /
−0.1057 %.

Cross-checks: 3-point fit on `100/200/400` predicting the `800` rung; successive triples; Richardson on
the finest pair at `p = 1` and `p = 2`: 3-point fit on `100/200/400` (`a` 2119.7583, `p` 1.760701)
predicts `Z0(800)` = 48.037175 against 48.040141 measured (**+0.00617 %**); successive triples
48.020776 (`100/200/400`) vs 48.026562 (`200/400/800`), spread **0.005786**; Richardson 48.003937
(`p` = 1) / 48.028073 (`p` = 2). `eps_eff` the same way: 3-point prediction 3.352314 vs 3.352632 measured
(+0.00949 %), triples 3.350989 vs 3.351292, spread 0.000625. All of these agree inside 0.03 %, so the
ladder converged in exactly the way the 3.0 mm one did — it is the *value* that moved, not the method.

**Quoted `Z0_infinity` at board width: 48.02 ohm (window 48.004–48.028)**, **−0.156 %** from the board-width
closed form 48.0987 — the same 0.16 % agreement that made the 3.0 mm limit look correct against the 3.0 mm
closed form. The board's own box is the `n` = 200 rung (20 mm per side), **48.209081 ohm**; the limit is the
extrapolation beyond it, not a measured box.

**Bracket, graded against §9.2 as frozen: W1 FIRED.** 48.0237 lies inside [47.136726, 49.060674] and 0.156 %
from 48.0987, i.e. inside the 2 % band. **W2 NOT FIRED** (48.0237 is 3.7 % from 49.90, far outside
[49.40, 50.40]); **W3 NOT FIRED** (not in 49.06–49.40); **W4 NOT FIRED** (inside [46.5, 50.0], so the falsifier
did not fire either). Unlike Dispatch 10 §6.1, these four bands are **disjoint** — W1 and W3 touch only at the
single point 49.06 — so that frozen-set defect does not recur here and no overlap needs an operative reading.

### 9.4 Task B′ — residuals at board width

| candidate | `Z0` | residual vs board-width limit |
|---|---|---|
| modal (rung of record, `n` = 200, 20 mm box) | 50.088 | **+4.298 %** |
| twin `zc` | 47.5366 | −1.014 % |
| `beta_base` station fit | 47.3641 | **−1.374 %** |
| `beta_rawphase` station fit | 47.9250 | −0.206 % |
| `beta_hammerstad` station fit | 47.9415 | −0.171 % |
| TE | 47.54 | −1.007 % |
| `z0_model` (closed form, board width) | 48.0987 | **+0.156 %** |
| Dispatch 10 limit (**3.0 mm fixture**, not this board) | 49.9015 | +3.910 % |

The extraction cluster (twin, `beta_*`, TE) is within **1.4 %** of the board-width limit and on the low side;
the modal rung is the outlier at +4.30 %; the 9.90 figure that the previous reading was built on is only
+3.91 % high because it was measured at the wrong width.

### 9.5 Task C′ — anchors at board width

| `Z0` | anchor `50/(2*Z0+50)` | residual vs `0.3255649` | dB |
|---|---|---|---|
| board-width limit, 48.023741 | **0.342354** | **−4.904 %** | **−0.437** |
| Dispatch 10 limit 49.9015 | 0.333772 | −2.459 % | −0.216 |
| board 20 mm box (`n` = 200), 48.209081 | 0.341488 | −4.663 % | −0.415 |
| twin `zc`, 47.5366 | 0.344654 | −5.539 % | −0.495 |
| `beta_base`, 47.3641 | 0.345475 | −5.763 % | −0.516 |
| `beta_rawphase`, 47.9250 | 0.342818 | −5.033 % | −0.449 |
| `beta_hammerstad`, 47.9415 | 0.342740 | −5.011 % | −0.447 |
| TE, 47.54 | 0.344637 | −5.534 % | −0.494 |
| `z0_model` (closed form, board width), 48.0987 | 0.342003 | −4.807 % | −0.428 |
| modal rung of record, 50.088 | 0.332943 | −2.216 % | −0.195 |

The residual is **not** an artefact of the twin's fitted `zc`: at board width the twin-`zc` anchor gives
−5.539 % and the board-width limit gives −4.904 %, so the −5 % order of magnitude is reproduced *without* the
twin. Across all ten anchors the residual spans **−5.763 % … −2.216 %** — still `Z0`-dependent in size, but
the whole extraction cluster plus the board-width limit sit at ≈ −5 %, and only the modal 50.088 and the
withdrawn 49.9015 pull it towards −2 %.

### 9.6 Task D′ — does `eps_eff` discriminate the width?

`eps_eff(3.2 mm, infinity)` vs the mode-profile value at `3.0` mm (`3.35001`) and vs the FDTD
raw-phase value (`3.350776`, taken on a **loaded** run and therefore carrying the `2*arcsin(0.32556)` =
38 deg contamination envelope — it is not an independent static measurement): **3.350989 against 3.35001
(+0.0292 %) and against 3.350776 (+0.0064 %)** — but both of those comparisons pair a 3.2 mm *limit* with a
3.0 mm *rung* and are not like-for-like. At matched box (`n` = 200) the 3.0 mm rung is 3.350009 and the
3.2 mm rung 3.369119, a **+0.5704 %** width gap; against the FDTD raw-phase 3.350776 the matched-box 3.2 mm
rung sits **+0.5474 %** and the 3.0 mm rung **−0.0229 %**. Closed form discrimination: `3.0` mm → `3.3255`,
`3.2` mm → `3.3439`, a +0.55 % width gap, matched by the solver's +0.5704 % at fixed box and by the
limit-to-limit difference (3.350989 vs 3.332468, +0.018520 absolute, +0.556 %).

**So `eps_eff` does not discriminate the width.** The 0.56 % width gap in `eps_eff` is smaller than the 38 deg
contamination envelope carried by the only field-measured `eps_eff`, and that number leans weakly — therefore
unreliably — towards the 3.0 mm rung (−0.023 % against +0.547 %). What the two methods do agree on is the
*sensitivity*: they reproduce the same width difference to 0.2 %. `eps_eff` is a consistency check on the
geometry, not an arbiter between the two widths. Only `Z0` can arbitrate — its width effect is −3.76 % and its
methods agree to 0.16 % at either width — and it does so unambiguously in §9.3.

### 9.7 Verdict

(a) **`Z0_infinity` at the board's width is 48.02 ohm, window 48.004–48.028.** Four independent routes to the
limit (4-point fit, 3-point fit plus predicted rung, successive triples, Richardson at `p` = 1 and `p` = 2)
all land inside that window, and it is 0.156 % from the board-width closed form 48.0987. The board's own box
(20 mm per side, the `n` = 200 rung) is **48.209081 ohm**; the limit is the extrapolation beyond it. This is
**3.76 % below the 49.90** this doc previously quoted as production, and that 3.76 % is the whole of the
discrepancy the ladder was built to find.

(b) **What survives and what is withdrawn.**

- **§3, the ladder:** correct arithmetic at the wrong width. Kept as the record of a 3.0 mm fixture study and
  superseded, for the board, by §9.3 — not deleted, not renumbered.
- **§7.1:** the **value** 49.90 is **withdrawn as a board statement**. It is the 3.0 mm fixture's limit.
- **§7.2:** **withdrawn.** An accurate board-width `Z0` does not leave the anchor residual small — it makes
  it **larger** (−4.904 % / −0.437 dB against the 3.0 mm limit's −2.459 % / −0.216 dB), because a smaller
  `Z0` implies a larger anchor `50/(2*Z0+50)` and the measured `|Gamma_port|` does not move with it. `Z0`
  stays **excluded** as the explanation of the residual, but for a stronger reason than §7.2's, and §7.2's
  stated basis (a limit measured on this board) is void.
- **§7.3:** **withdrawn**, as already stated in the dated forward pointer in §7 and the dated correction in
  §2. The six-estimator extraction family sits within **1.4 %** of an independent quasi-static solve at the
  board's own width (modal +4.30 % is the outlier; the rest span −1.37 % … +0.16 %), not 4–5 % below it.
- **§7.4 (DR-36):** **survives and extends to `eps_eff`.** The modal `Z0` is box-limited (0.37 % high at
  `n` = 200) and so is `eps_eff`: at either width the 20 mm-box rung sits **≈ 0.53 %** above that width's
  limit (3.350009 vs 3.332468 at 3.0 mm; 3.369119 vs 3.350989 at 3.2 mm). Nothing in this re-run weakens
  DR-36; it strengthens it by exhibiting the same defect in a second quantity.
- **§6:** bracket **Z1 is void** — it fired against 49.90, which is not this board's limit. **Z2 and Z4** are
  literally still true (48.02 is absent from the station-fit cluster's band and inside [44, 52]) but are moot,
  because they graded a limit measured on the wrong geometry. **§6.1's Z1/Z3 overlap** is moot for this
  question: the W bands are disjoint, so no overlap reading is needed.

(c) **The anchor at board width: 0.342354, residual −4.904 % (−0.437 dB)** against the measured
`|Gamma_port|` = 0.3255649. The reading that "the 5.5 % is an artefact of the twin's `zc`" **does not
survive**: at board width the twin-`zc` anchor gives 0.344654 / −5.539 % and the board-width limit gives
0.342354 / −4.904 %, so the −5 % order of magnitude is reproduced *without* the twin. Across all candidates
the residual spans **−5.763 % … −2.216 %**, i.e. it remains `Z0`-dependent in size, but the whole extraction
cluster and the board-width limit sit at ≈ −5 % and only the modal 50.088 (and the withdrawn 49.9015) pull it
towards −2 %. The anchor is **not closed** here, and it is now a different question: the residual is neither a
`Z0` error nor a modal-extraction error, so it has to be sought on the measurement side (`|Gamma_port|`
itself, or the port normalisation) or accepted.

(d) **The defect is not the test.** `emfit/mode_profile.py` has **no `w` default** — `w` is a required
parameter (`:535-543`); `3.0e-3` is `W_CONVERGED` in `tests/test_mode_profile.py` (`:64`, used at `:83`) and
is a **legitimate fixture**: at `cell = h / n_sub = 0.1 mm` it is a whole number of cells, which the
constructor documents as a requirement (`:550-551`). `emfit/mode_profile.py:557-559` *does* carry
`n_sub = 16` as a default and calls `0.1 mm` "the FDTD board's `0.1 mm` cell" — and the board's cell is
0.4 mm (`n_sub = 4`, `emfit/studies.py:1188`). The defect, **DR-37**, is (i) no production-geometry binding at
the call site, (ii) the document of record describing a test constant as production, and (iii) the same
conflation of default for board written into the library's own docstring. Nothing here is a defect in the
quasi-static solver, in the ladder method or in the test suite, and no number above required a solver change
to produce.

### 9.8 Artefact bank for both ladders

*Appended 2026-11-05. Nothing above this heading is edited: §1–§7 and §9.1–§9.7 stand as written, and nothing
below adds a number to any of them. This subsection records only that both ladders now exist as
machine-readable artefacts, and what a from-scratch re-run established.*

**(a) What was banked.** Three new files, all new, nothing else changed:
`evidence/quasistatic_z0_ladder_w3.0mm.json` (Run A, the `3.0` mm test-fixture width of §2/§3),
`evidence/quasistatic_z0_ladder_w3.2mm.json` (Run B, the `3.2` mm production board width of §9.3), and the
generator `evidence/bank_quasistatic_z0_ladder.py` that produced both. The generator takes
`--w/--tag/--role/--out-dir` and writes one JSON per width. The artefacts carry the per-rung `Z0`, `eps_eff`
and wall seconds, the geometry and medium actually passed, the fit parameters, an explicit field stating that
the covariance is not an error bar, the four cross-checks described in §3/§9.3, the closed-form `Z0` at that
run's `w` with the relative difference to the fitted limit, and a `notes` field recording that Run A is a
test-fixture width and is **not** a board statement. The purpose is that the numbers of record no longer exist
only as prose in this document.

**(b) Reproduction.** Re-running from scratch on this machine reproduced both ladders rung-for-rung: all eight
`Z0` values and all eight `eps_eff` values agree to the six decimals printed in §3 and §9.3, and the fits agree
to the last quoted digit — `Z0_inf` 49.9014977 against 49.901498 with `p` 1.7912633 against 1.79126 for the
3.0 mm run, and 48.0237405 against 48.023741 with `p` 1.78090566 against 1.780906 for the 3.2 mm run. The
`eps_eff` limits are 3.3324683 at 3.0 mm (the value §7.4 already quotes as 3.332468) and 3.35098854 at 3.2 mm
(§9.3's 3.350989) — so the banked artefact reproduces this document's own `eps_eff` limit for the 3.0 mm
fixture to seven digits, a cross-check §7.4 did not previously have. Total job wall 94 s.

**(c) Finding — the two recorded wall-clock columns are not mutually comparable.** The re-run measured 36.5 s
and 40.3 s for the `n` = 800 rung at 3.0 mm and 3.2 mm respectively, on grids of 1630x816 and 1632x816 — i.e.
essentially equal cost, as the grid sizes require. The columns recorded in §3 (120.7 s) and §9.3 (27.82 s)
differ by a factor of 4.3 on those same near-identical grids, so they cannot both have been taken on one
machine under one load. The two timing columns therefore come from different machines and **must not be
compared with each other**; no number in either ladder depends on a timing and no conclusion in this document
was drawn from one. The banked JSONs carry this machine's timings, not the recorded ones.

**(d) Finding — `n_strip` is an output, not an input.** `emfit/mode_profile.py:458` derives
`n_strip = round(w / cell)` inside `_section(h, w, n_sub, n_clean, n_air)` and raises if `w` is not a whole
number of cells; it is not a parameter of the call. §9.2 and §9.3 describe the re-run as `n_strip = 32`; that
is the correct consequence of `w = 3.2e-3` at `cell = 0.1e-3`, but it is a reported outcome, not something
passed. The JSONs record it as `geometry.n_strip` alongside `geometry.n_strip_rule`.

**(e) Provenance limitation, stated honestly.** `git` is not installed in the execution container, so the
generator's graceful degradation fired and both JSONs carry `git_rev` =
`unavailable (git not installed in workspace container)` rather than a sha. Provenance of the artefacts is
therefore the commit that contains them (the run was made against tree `ce0d9e7`, HEAD at run time) rather than
a sha embedded in the file. Fixing this properly means adding `git` to the runtime image, not editing the
artefacts.

