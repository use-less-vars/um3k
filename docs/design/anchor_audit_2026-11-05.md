# Anchor provenance audit — 2026-11-05

Dispatch `anchor-audit-2026-11-05`. Read-only provenance audit. **No host execution, no openEMS run, no new
physics.** Every number below is traced to a file or a `path:line`; nothing was recomputed into existence
except the elementary arithmetic that is shown.

**The β hypothesis is dead.** The previous pass refuted it: four targets want four different β spread over
15.604623 rad/m (6.74 % of 231.55) with disjoint tolerance windows, so no single β satisfies the s11 phase
and either |Γ| anchor together. What is alive is the finding that **three anchors disagree and none of them
has a documented error bar.** This document establishes which anchor is defensible, and with what bound.

**Pre-registration.** §2 below was written and saved **before any audit work was performed** — before any
file outside this document was read for this task. Sections 3 onward were filled in afterwards. The git
history of this file, not its own assertion, is what proves the order.

| pass | content | status |
|---|---|---|
| 1 | §1 inputs, §2 brackets **verbatim**, §3 method | written before the audit |
| 2 | §4–§8 results | written after |

## 1. Inputs

| input | value | source |
|---|---|---|
| series-R anchor | \|Γ\| = 0.34465 | `docs/design/closed_form_with_two_wave_beta_2026-11-02.md`:14 |
| complex-load anchor | \|Γ\| = 0.307 (82.115 − j20.782 Ω at Z0 47.54) | `docs/design/beta_refit_test_2026-11-05.md` §1 |
| TE s11 phase | −107.68 deg | same |
| TE s21 phase | +9.11 deg | same |
| station phasors | n = 9, 8 selected | `evidence/termination/build_A_50ohm_p51_phasors.json` |
| ε_eff model | 3.343938310019 (static, Hammerstad–Jensen at w/h = 2.0, ε_r = 4.4) | `emfit/microstrip.py` |
| ε_eff Laplace static | 3.35001 | `docs/design/beta_refit_test_2026-11-05.md` §8 |

## 2. Pre-registered brackets (verbatim, unedited)

> A1: Z0 span < 2 % across all documented sources => the anchor is roughly knowable; re-derive 0.34465 with a stated tolerance and treat it as usable; the residual question narrows.
> A2: Z0 span 2-5 % => the anchor carries an error bar comparable to the 5.5 % residual itself; the residual is NOT interpretable at this precision without a new Z0 measurement.
> A3: Z0 span > 5 % => the anchor is UNKNOWABLE from the record. The 5.5 % question cannot be answered against 0.34465 until Z0 is fixed. This is the honest finding, not a failure.
> A4 (falsifier): the record shows exactly one distance used for every phase quantity => the last pass's s21 finding is WRONG and must be retracted; recalibrate the whole plane/span story.

The span in A1–A3 is defined here, before the audit, as the **full range across all documented Z0 sources**
(max − min, as a percentage of the smallest), because that is the number a bracket of this shape can act
on; a scatter about a mean would understate a systematic disagreement between methods.

## 3. Method

Two tasks, both read-only: **Task A** collects every Z0 in the record with its provenance and asks whether
any uncertainty is documented; **Task B** takes every phase/magnitude/impedance leaf in the artefact and
asks what operation actually produced it, over what distance, at what β. Then §7 maps the measured span
onto §2. Nothing was fitted, run or solved.

## 4. Task A — Z0 provenance

**Ten `Z0` values appear in the record. Exactly one carries a documented uncertainty.**

| # | source | value (Ω) | \|Z\| (Ω) | where | documented uncertainty |
|---|---|---|---|---|---|
| i | mode-profile / modal | 50.088 | 50.088 | `emfit/mode_profile.py`:651 | **yes, ≈ ± 1 %**: 0.3 % at 5 mm of wall drift (`:589-590`), and 0.57 / 0.78 / 1.16 % of the power outside the box at the three trial widths (`:99-104`) |
| ii | station fit, β_base | 47.364066848187235 + j1.6449807931078728 | 47.393 | `evidence/termination/build_A_50ohm_p51_phasors.json` `/run/station_fit` (`:279-280`) | none |
| iii | station fit, β_rawphase | 47.9250 + j1.8768 | 47.962 | `docs/design/beta_refit_test_2026-11-05.md` §8 | none |
| iv | station fit, β_hammerstad | 47.9415 + j1.8837 | 47.978 | same | none |
| v | twin station fit `zc` | 47.53661998575833 + j1.9309048088852248 | 47.576 | twin `reference_block`; quoted at `docs/design/z0_provenance_and_twin_2026-11-04.md` | none |
| vi | TE reference | 47.54 | 47.54 | `docs/design/complex_load_analysis_2026-11-04.md` | none — and it is in **no artefact** |
| vii | `summary_line` `z0_model` | 48.0987 | 48.0987 | artefact `summary_line` | none |
| viii | settling plane `z_plane` | 44.9658 − j2.5380 | 45.037 | `docs/design/complex_load_analysis_2026-11-04.md` | none |
| ix | `line.z0` (port V/I) | 42.43786214405251 − j15.727993189312496 | 45.258 | artefact (`:190-191`) | none — a **different quantity** (port V/I, not a wave impedance), DR-29 |
| x | station fit, stale β_one | 44.207500737130495 + j0.3794459968505162 | 44.209 | pre-fix `beta_one` fit, superseded | none — **EXCLUDED** from the spans below |

**Why the fits have no error bar.** None of (ii)–(v) is accompanied by a bootstrap, a covariance, or a
curvature-based σ: the `sigma_beta_from_curvature` field is **ABSENT** from the artefact, so the β these fits
are conditioned on is itself point-valued. Their spread is therefore not a confidence interval in any
statistical sense — it is a set of equally undocumented point estimates produced by different, all
defensible, estimator choices. That is precisely the condition A1–A3 were written to test.

**The spans (§2 definition: max − min, as a percentage of the smallest).**

- **Full live set** (i)–(ix), excluding the stale (x): 45.037 → 50.088, i.e. 5.051 / 45.037 = **11.22 %**.
- Including the stale fit for completeness: 44.209 → 50.088 = **13.30 %**. Recorded, not used — a superseded
  estimator is not a source.
- **Narrowest defensible subset** — the four that are neither superseded nor a different quantity, and that
  any reader would accept as candidate anchors (TE 47.54, twin 47.5366, `z0_model` 48.0987, modal 50.088):
  2.5514 / 47.5366 = **5.37 %**. (Entering the twin as its magnitude 47.576 instead of its real part makes the
  TE the minimum and gives 2.548 / 47.54 = 5.36 %; the two differ in the second decimal and neither changes
  the grading. 5.37 % is the figure carried throughout.)

**Sensitivity — what a `Z0` span costs in `\|Γ\|`.** For a series load, `\|Γ\| = Z0/(2Z0 + R)`, so
`d ln\|Γ\| = −(1 − \|Γ\|) d ln Z0`; at `\|Γ\| = 0.34465` the factor is −0.65535. A 5.37 % `Z0` span is
therefore **3.5 %** in `\|Γ\|`, and 11.22 % is **7.3 %**. The residual in dispute is **5.54 %**. The span is
of the same size as the quantity it is supposed to adjudicate — which is the whole finding.

**Re-deriving the anchor says which `Z0` it was built from.** `50/(2·47.53662 + 50) = 0.3446535` reproduces the
recorded 0.34465, so **the anchor's `Z0` is row (v), the twin's fitted `zc`** — a fit output transplanted out of
a twin artefact, quoted to six decimals, carrying no error bar, and not produced by the run the anchor is
applied to. At the modal `Z0`: `50/(2·50.088 + 50) = 0.332942`, i.e. −3.40 % against the anchor. The measured
0.3255649 then reads **−2.22 %** against the re-derived anchor instead of −5.54 %. Nothing was re-graded here;
the point is only that "the residual" is not a property of the measurement alone.

## 5. Task B — plane/span audit

Every phase-like leaf in `evidence/termination/build_A_50ohm_p51_phasors.json`, with the operation that
actually produced it, reconstructed from the recorded values to the last digit where the record allows.

| leaf | recorded value | operation that produced it | distance | β | verdict |
|---|---|---|---|---|---|
| `/s11/phase_deg` | −100.49921155605985 | `deembed_reflection` (`emfit/studies.py`:3266, `\|·\| = 1` assertion `:3274`) | 0.0072 m | `beta_used` 231.55331672912826 (`:3387`) | **MATCH** on distance and β — but the block's own prose says the magnitude is *not* de-embedded while sitting beside a de-embedded phase, and that magnitude comes from `fit_beta(n_wave=2)` ⇒ DR-27 class |
| `/s21/phase_deg` | 5.187960321243577 | reference-free `line_s21` (`emfit/studies.py`:3686; `emfit/ports.py`:1702-1703) | **0.0172 m** | 231.55331672912826 | **MISMATCH on branch AND distance**: the value reproduces as `wrap(136.99508249088075 + deg(β·0.0172))` to 4.5e−14, while the record stores `deembed_distance_m = 0.0072` and a basis string claiming the twin `forward_ratio` branch (`:3352`) |
| `/ac/AC-7/phase_degeneracy/dL_m` | 0.0172 | recorded span | — | — | **independent confirmation** that 17.2 mm, not 7.2 mm, is the s21 distance |
| `/s21/raw_reference_independent` | `true` | run flag | — | — | vs `/s21/raw_basis`, which describes a reference-dependent construction ⇒ **MISMATCH**, and not a string-vs-string one |

**The distance is not ambiguous.** 0.0172 m = 0.0204 − 0.0032 m, the load plane at column 50 (`load_plane_index`
50, `plane_offset` 1) minus the port at 3.2 mm — two real planes the geometry already records. `/s11` uses the
7.2 mm station-to-port span; `/s21` uses the 17.2 mm port-to-load span. Both are correct for their own
operation. What is wrong is that `/s21` **records** the s11 distance.

**Everything else in the block was swept and none of it moves the phase.** `deembedded_slope_rad_per_m` =
−5.264359829565299 is a slope, never a β, and must not be quoted as one; `raw_slope` = −139.0125144;
`single_run_branch_spacing` = 365.3014713; `/run/reference_exponent` = 1.7916666666666667 against the
docstring's 1.75, with `reference_residual` null — the null being the one leaf that is *consistent* with
`loaded_without_reference` being true. **Three of ~10 leaves carry a false provenance string**, which is what
§5 of the audit sizes and what the DR-27 class note now registers.

## 6. Item 0 — the ε_eff correction at the resid_v minimum

**Item 0 was wrong as briefed, and the correction is a scope correction, not a numerical one.**

The brief asked for a sentence to be fixed: the claim that *the resid_v minimum matches the Laplace static
ε_eff*. **No such sentence exists on disk.** The only claim of that shape is the β_rawphase sentence in
`docs/design/beta_refit_test_2026-11-05.md` §8 item 7, and it is **arithmetically correct**: 0.023 % is the
agreement of β_rawphase with the β_two_wave baseline, not with Laplace. The three lines that settle it:

- ε_eff from the static model (§1): **3.343938310019** (Hammerstad–Jensen, w/h = 2.0, ε_r = 4.4).
- ε_eff Laplace static: **3.35001**.
- ε_eff implied by β_rawphase: `(231.046199503169 / 122.14137132890411)² = 3.578261` → **+6.81 %** against Laplace.
- and the baseline it is actually compared to: `(231.55331672912826 / 122.14137132890411)² = 3.593986` → **+7.28 %** against Laplace.

So the 0.023 % is a real, correctly stated agreement between two twin-family β values, and the **whole twin
β family (229.49–232.73) sits +5.4 … +8.4 % above the static solve**. That is a fact about the twin family, not
a defect in the sentence. The item was therefore resolved **in place**: a dated correction note was appended to
§8 item 7 stating that 0.023 % belongs to β_rawphase alone and quoting the two percentages above, with the
original text retained rather than rewritten. Nothing was recomputed, no threshold moved, and no conclusion of
the previous pass was reversed.

## 7. Which bracket fired

Quoted verbatim from §2; graded as written, nothing renamed or widened.

| bracket | threshold | measured | fires? |
|---|---|---|---|
| **A1** | `Z0` span < 2 % → anchor roughly knowable | 5.37 % narrow, 11.22 % full | **NO** |
| **A2** | span 2–5 % → error bar comparable to the 5.5 % residual | the span is above 5 % on every subset | **NO** — A2 is the 2–5 % band and the measurement is not in it |
| **A3** | span > 5 % → anchor UNKNOWABLE from the record | 5.37 % narrow / 11.22 % full | **FIRES** |
| **A4** | exactly one distance for every phase quantity → last pass's s21 finding WRONG, retract | 0.0072 m for `/s11`, 0.0172 m for `/s21`, each confirmed independently (§5) | **NO** — two real distances |

**A3 fires, and it fires on the narrowest subset — but only just, and that should be stated rather than
enjoyed.** The full live span is 11.22 %, more than twice the threshold; the four-source subset a careful
reader would actually defend is 5.37 %, which clears 5 % by **0.37 percentage points**. A bracket that fires
by 0.37 pp on one of two defensible populations is a bracket I would report as fired and would not lean on
harder than that. No threshold was moved in either direction to produce either number, and the subset was
fixed by the criteria in §4 (not superseded, not a different quantity), not by where it left the grade.

**A4 not firing matters as much as A3 firing.** It means the previous pass's s21 conclusion — that `/s21` carries
the 17.2 mm distance while recording 7.2 mm — survives the audit that was designed to kill it. This pass
therefore *adds* to that finding (a third provenance instance, and the boolean) rather than retracting it.

## 8. What this does and does not establish

**Established: 0.34465 is not a usable referee.** It is not a measured anchor and not an independent one. It is
the twin's fitted `zc` — row (v) — carried to six decimals with no error bar, re-derived here exactly
(`50/(2·47.53662 + 50) = 0.3446535`), and it was never produced by the run it grades. Its `Z0` uncertainty is
not smaller than the effect it is used to measure: 5.37 % on the defensible subset, 11.22 % on the live set,
translating to 3.5 % and 7.3 % in `\|Γ\|` against a residual of 5.54 %. Re-deriving the anchor at the modal
`Z0` turns the −5.54 % residual into **−2.22 %**: the size of "the residual" is a function of which `Z0` is
charged, so "5.54 % low against 0.34465" cannot be quoted as a property of the measurement.

**Not established: which `Z0` is right.** This audit bounds the disagreement; it does not resolve it. The one
source with a real error bar — modal 50.088, ≈ ± 1 % — disagrees with every station fit by about 5 %, and that
gap is a **physics question** (what the modal impedance of this cross-section actually is), not a bookkeeping
one. It is the same order as the half-cell / V-I-definition effects bounded at ≤ +2.2 Ω in
`docs/design/spatial_collocation_audit_2026-11-04.md`, so a real offset of that size is plausible but does not
absorb a 5 % gap on its own. No measurement in the record decides it, and this pass licenses **no host run**.

**Established: the plane/span story is intact, and the provenance layer is worse than one defect.** A4 did not
fire, so `/s11` at 7.2 mm and `/s21` at 17.2 mm are two correct operations with one wrong record. But the DR-27
class now has three members in three different kinds of leaf — a branch string, a distance plus stale line
references, and a boolean that contradicts its own prose. Nothing was miscomputed in any of the three; what
failed is the record of what was computed, in a record whose only remaining tie to its own tree state is that
layer (DR-28: `meta.git_rev` null).

**Cheapest fix, described and not done:** emit every basis string from the branch that actually ran, derive
`deembed_distance_m` from the plane the value was taken at instead of carrying a constant, and record **which
`Z0` each anchor was built from, with a tolerance**. That last one would have made this audit a one-line check
instead of a document.
