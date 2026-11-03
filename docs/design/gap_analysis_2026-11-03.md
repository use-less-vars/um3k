# Gap analysis 2026-11-03 — the 16–19 pp `s21` gap

**Status: analysis of record, read-only.** No solve was run, no `.py` file was edited, no committed artefact was modified; `emfit/studies.py` is byte-identical throughout. Every number below is a stored artefact field or literal arithmetic on one, and nothing is re-fitted from raw fields. Dispatch `gap-analysis-2026-11-03`.

## 1. The question, the scope, and the artefacts

`|s21|` on the loaded 50 Ω series-R arms sits well above the series-R anchor `T = 2Z₀/(2Z₀+R)`, and the modal launch *widened* the gap rather than closing it. This dispatch asks which of the four hypotheses left open by `strip_termination_refuted_2026-11-03.md` §4 accounts for it, and how many percentage points each can carry:

* **H1** — evanescent residue from the load, still present at the extraction plane and decaying with plane distance.
* **H2** — a residual reflection off the xmax PML, i.e. the plane sweep sampling a standing wave.
* **H3a** — Z₀ mismatch: the anchor's substituted 47.53662 Ω against the run's own fitted Z₀.
* **H3b** — quasi-TEM correction to the anchor's Z₀.

Artefacts read, all pre-existing: `build_A_50ohm_v3_modal.json` and `build_A_50ohm_v3_lumped_check.json` (the launch pair, plane 51); the five-plane reference-free sweep `build_A_50ohm_sweepN{51,53,55,57,59}.json` on the A mesh (nx 72); and the cross-mesh series `build_A_50ohm_v3b_c{51,53,55,57,59}.json` (nx 62). No new measurement was made for this document.

## 2. Anchor, gap, and the validity of the sweep window

`T_anchor(Z0_SERIES_ANCHOR = 47.53662) = 0.655346499464684`.

| arm | plane-51 magnitude | gap vs anchor |
|---|---|---|
| lumped launch | 0.7628473102840976 | 16.4037 pp |
| modal launch | 0.7803754200773916 | 19.0783 pp |

The gap is relative — `(mag/T − 1)·100`. The modal launch moves the magnitude **up** by +2.2977 %, taking the gap from 16.4037 pp to 19.0783 pp: the launch is not the source of the gap, and is now ruled out as one.

**Geometry, and why the sweep is admissible.** All five `sweepN` artefacts are the same config: nx 72, ny 212, nz 22, 335808 cells, n_pml 6, n_sub 4, n_line 64, n_strip 8, ix_port 8, ix_far 72, cell 0.0004, h 0.0016, w 0.0032, eps_r 4.4 — `GEOM_IDENTICAL = True`. PML starts at `nx − n_pml = 66`, so the last clean plane is 65 and planes 51, 53, 55, 57, 59 all sit outside it: the trend is a clean-line trend and no stop-rule fires.

The `v3b_c` series is a **different** geometry (nx 62, 289168 cells, n_line 54, n_pml 6): its last clean plane is 55 and PML starts at 56, so `c51`/`c53`/`c55` are usable while `c57`/`c59` are inside the absorber. The record shows it as a magnitude collapse — 0.7600910333803181, 0.7489356474942055, 0.7434621158755802, then 0.6681161101336922 and 0.05460536142032808 — so those last two are absorber artefacts, used only as a corroborating check and never in a fit.

## 3. H1 — evanescent residue at the extraction plane: PRESENT

Five distinct solves on one mesh give magnitude against plane:

| plane | magnitude | phase_deg | raw_phase_deg | s11 magnitude | s11 phase_deg |
|---|---|---|---|---|---|
| 51 | 0.7628473102840976 | 59.49866046655281 | 137.2951714995182 | 0.03379343163562476 | −74.04316655497415 |
| 53 | 0.7517891786585884 | 60.951999587531795 | 125.62276694761186 | 0.023745848823574577 | −39.59892018728143 |
| 55 | 0.7461547372364731 | 63.094550737572405 | 114.63957442476713 | 0.02279652692191677 | −19.826471030207397 |
| 57 | 0.7418756393514595 | 65.47292951840032 | 103.89220953270971 | 0.023302031876297685 | −10.484879748414476 |
| 59 | 0.7378317576531221 | 67.89611334353144 | 93.1896496849555 | 0.02366037233907586 | −5.709538162176381 |

On every one of these records `raw_magnitude == magnitude`, so no de-embedding is hiding the trend. Fit `mag(Δ) = A + B·exp(−C·Δ)` with `Δ = plane − 51`:

| parameter | value | note |
|---|---|---|
| A | 0.732349452526682 ± 0.00288036 | the asymptote, mag(∞) |
| B | 0.037084500417724 ± 0.00216249 | 3.71 % of the plane-51 magnitude |
| C | 0.203186317916544 ± 0.03890627 | per plane; poorly constrained |
| resid RMS | 0.00050577 | residuals `[0.00023, −0.00072, 0.00038, 0.00058, −0.00047]` |

Successive differences are `[−0.01105813, −0.00563444, −0.0042791, −0.00404388]`; the first interval decays 0.51 where the single-exponential form demands roughly 0.76 / 0.95 as the later intervals do — so **C is poorly constrained** and the extrapolation is a one-parameter continuation over an 8-plane window, not a converged decay constant. The ±0.00288 on A already reflects that. The test is `B > 2 %` and `C > 0`; both hold, so **H1 is present**.

The asymptote `mag(∞) = 0.732349452526682` is 11.7500 pp above the anchor against 16.4037 pp at plane 51, so the evanescent term removes **4.6537 pp (±0.44 pp from the uncertainty on A)** of the lumped gap. `A/M(51) = 0.960021019480219`.

**§H1 erratum, 2026-11-03 — the printed A/B/C do not reproduce the printed residuals.**

Audited against the committed fit parameters, the quoted set does not generate
the quoted residual vector. Evaluating A=0.732349452526682, B=0.037084500417724,
C=0.203186317916544 on the five published points (Δ = 0, 2, 4, 6, 8) gives
residuals [−0.006587, −0.005260, −0.002643, −0.001433, −0.001814], all one sign,
summing to −0.0177, RMS 0.004084 — eight times the quoted 0.00050577. A hand
re-fit of the same five points gives A ≈ 0.7332, B ≈ 0.0296, C ≈ 0.211,
RMS ≈ 5.2e-4, reproducing the quoted A and RMS but not B/C. The most likely
reading is a typographical transposition in A/B/C at transcription time; the
residual vector is from a genuine fit (it sums to exactly zero, so it is a real
free-offset LSQ residual), but not from the parameters printed beside it.

**Blast radius:** nil for the refutation. The 63/65 measurements (0.729132,
0.724569) land 6–8e-3 below every candidate asymptote, including both parameter
sets. **The refutation stands against every candidate anchor.** It stands also
against the anchor itself (0.6553) — the series is far above it at every plane.

**Action:** future readers must cite the *re-fit* (A≈0.7332, B≈0.0296, C≈0.211)
as the working parameters, not the originally printed set. **Tagged:**
[MEASURED, worker audit 2026-11-03] for the residual discrepancy;
[ESTIMATE] for the re-fit.

**Companion note: the sweepN series spans the `5dda96d` schema boundary.**
Planes 51/53/55/57/59 were run 2026-11-01 (pre-`5dda96d`, `s11.magnitude` =
gamma_plane, 0.0338 at plane 51); planes 63/65 were run 2026-11-03
(post-`5dda96d`, `s11.magnitude` = two-wave modulus, 0.3256). **`|s21|` is
unaffected** — `5dda96d` did not touch the `s21` writer — so the H1 fit is
legitimate. **`s11.magnitude` must not be compared across the boundary**;
it is two quantities under one key. [MEASURED, worker + this session]

## 4. H2 — PML residual reflection: bounded out

A standing wave off a reflecting absorber would appear as a periodic residual in phase and magnitude against plane. On the same five planes the de-embedded phase is linear to well inside the fit's own noise:

* slope **+1.06579178424129 deg/plane**, intercept 4.76430259744689, residuals `[+0.37897687, −0.29926757, −0.28829999, −0.04150478, +0.25009548]`, RMS **0.275888 deg**.
* The raw phase over the same records gives slope **−5.49708005220139 deg/plane** and the *same* residuals to the digit, and its offset from the de-embedded phase is exactly `beta·cell = 6.56287183644268 deg`: the de-embedding basis is confirmed, and all the residual is in the linear fit, not in the phase handling.
* A 5-parameter sinusoid on 5 points is **unidentifiable** — exact interpolation, `OptimizeWarning`, ω railed to 0.0265490039838038 (period 236.663692205276 planes). It is recorded here only as a refusal: **it is not evidence, and no number derived from it is quoted anywhere in this document.**

**What the residual can buy H2.** The expected standing-wave periods are 27.427017 planes (one-wave β = 286.35930483082825 rad/m) and 33.918675 planes (two-wave β = 231.553316729128 rad/m); the 8-plane window is 0.24 of the shorter period, so the shape is unresolvable by construction. What remains is the amplitude bound: 0.37898 deg → `|Γ_res| ≤ 0.0066144` → `|Γ_res|² ≤ 4.37502e−05`, i.e. **≤ 0.0044 pp** of gap. H2 cannot carry a 19 pp gap by three orders of magnitude.

**Second, independent test.** `s11` magnitude is plane-invariant to 0.00086532 (3.70 %) across planes 53–59, and its phase falls monotonically −74.04° → −39.60° → −19.83° → −10.48° → −5.71°: no oscillation, therefore no PML residual. Plane 51 alone reads high (0.0338 against 0.0237 at plane 53), and that single-plane excess is the load's own reactive near field — the same field H1 measures decaying. The two diagnostics agree on where the residue is.

## 5. H3a — station-fit Z₀ mismatch: real, small, and it widens the gap

The run's own fitted source impedance is `run.station_fit.z0 = 44.207500737130495 + 0.3794459968505162j`, modulus 44.2091291555027. Feeding it into the anchor gives `T = 0.63876747847091`, i.e. `ΔT = −0.0165789` in magnitude units = **−2.5298 % of T** (the modulus variant gives T = 0.638775977894062). The competing fitted impedances:

| Z₀ used | value | T | shift vs anchor |
|---|---|---|---|
| substituted anchor | 47.53662 | 0.655346499464684 | — |
| `station_fit.z0` (complex) | 44.2075 + 0.3794j | 0.63876747847091 | −2.5298 % |
| `line.z0_re` | 42.43786214405251 | 0.62928836702151 | −3.9762 % |
| `line.z0` modulus | 45.2586114802549 | 0.64417173249964 | −1.7052 % |

All three fitted variants give a **lower** Z₀ than the substituted anchor and therefore a **smaller** T, i.e. a **wider** gap — about +3.0 pp at the modal magnitude for the station-fit value. H3a is present, but it is a single-digit-pp term pointing the wrong way, and it cannot be double-counted: `line.z0 = 42.4379 − 15.7280j` is the port ratio `−v_port/i_trunc`, not the same quantity as the fitted station Z₀ (`s11-load-exoneration-and-station-degeneracy-2026-11-02`).

## 6. H3b — quasi-TEM correction to the anchor: below threshold, NOT adopted

Hammerstad–Jensen at `w/h = 2`, `eps_r = 4.4`: `a(u) = 0.999530271328385`, `b(eps_r) = 0.542057589137915`, `eps_eff = 3.34393831001894` (Wheeler first-order 3.34253960411569, 0.04 % apart), `Z0_air = 89.0926625500543` → `Z0 = 48.7206203756598`, **+2.4907 %** above the substituted 47.53662, hence `T = 0.660881855407525` and `ΔT = +0.00553536` = **+0.55 pp** of magnitude = +0.8446 % of T. That is below the 1 % adoption threshold set for this dispatch, so it is **stated and not adopted**, and the correction points the *wrong* way — the aggregate H3 movement in §7 is dominated by H3a. Source: Hammerstad & Jensen (1980), "Accurate models for microstrip computer-aided design", IEEE MTT-S Int. Microwave Symp. Dig., pp. 407–409.

**Corroboration, and one impossible field.** `line.eps_eff` is present but null on all five sweep records and `line.beta_two_wave` is absent from all five, so the implied ε_eff has to come from the stored betas: `line.beta` 286.35930483082825 → **5.49663647596545, above eps_r 4.4 and therefore physically impossible** — a further symptom of the one-wave fit artefact recorded in `s11-one-wave-vs-two-wave-2026-11-02`. `line.beta_model` 223.35306683909533 → exactly 3.34393831001894, the HJ value, so the model field *is* HJ and is self-consistent. `line.beta_two_wave` 231.553316729128 → 3.593986396194. The sweep's own raw-phase slope gives β = 240.55830436697 rad/m → 3.876, i.e. −15.99 % against `line.beta` and +3.89 % against `beta_two_wave`. The measured dispersion brackets HJ rather than confirming the substituted anchor, but it does so at the few-percent level of ε_eff — it cannot close a 16 pp gap either.

## 7. Accounting, verdict, and the cheapest discriminating experiment

**Modal, the current arm.** 19.0783 pp → H1 −4.76 pp (0.7803754200773916 → 0.749176806360001) → H2 ≤ 0.0044 pp → H3 +1.94 pp (T → 0.644424632527996) → **16.2551 pp**. Net explained 2.82 pp = **14.8 %**.

**Lumped.** 16.4037 pp → H1 −4.65 pp (→ 0.732349452526682, 11.7500 pp) → H3 → **13.6439 pp**. Net 2.76 pp.

Bracket that fires: **"< 5 pp"** — it fires under either launch convention, because the gross H1 term is 4.76 pp and even that is under 5. No hypothesis exceeds the gap, so **no calculation-error flag is raised**: nothing here claims a stored number is wrong.

**Categorical verdict.** Not an anchor error — the anchor is defined in the harness path (`run_build_A.py:140`, consumed at `:1263`) and its competing Z₀ variants differ by 2.5 %, against 16 pp of gap (§5). Not a PML floor — bounded at 0.0044 pp and refuted independently by the monotone `s11` phase (§4). The residual is an **extraction / structural artefact**: with the evanescent residue removed, 16.2551 pp of gap survives. The standing candidate is the cut probe's **two-column arithmetic average** at `emfit/studies.py:2964-2968` — columns `ix_extract−1` (here 50, the load's own column) and `ix_extract` (51) — and/or the load's own field at that plane: the mechanism `s21-plane-sweep-2026-11-02` already flagged, now with the competing explanations priced out.

**Cheapest discriminating experiment.** Two extra solves on the *identical* nx 72 mesh at `--s21-plane-index 63` and `65` — ≈42 s wall each against the 41.9 s already recorded, no code change, no new geometry — compared with the H1 continuation at those planes, `mag(12) = 0.735585` and `mag(14) = 0.734505`. If they land on the continuation, the H1 asymptote is confirmed, the surviving 16.26 pp is near-field plus probe, and a full-cross-section modal flux projection replacing the two-column average at `studies.py:2964-2968` becomes the next study and the only one that can close the gap. If instead they fall toward the 0.6553 anchor, the single-exponential form is an interpolation artefact over an 8-plane window and the extraction candidate stays unfalsified. The fully discriminating test — flux projection versus two-column average on one field dump — requires a code change and is outside this dispatch's fence, so this document does not claim to have separated the two mechanisms.
