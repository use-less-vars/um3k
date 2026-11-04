# Z0 on the current record, and the factor split there - 2026-11-05

Read-only analysis of `evidence/termination/`. **No source change, no run performed, no artefact re-graded,**
no model re-run. Companion to `complex_load_analysis_2026-11-04.md` and `s11_refit_from_phasors_2026-11-04b.md`;
it corrects one sentence those left in the Gen 8 handoff. Tags: **[M]** measured here in this pass, artefact
cited beside it; **[L]** read from the project's own record.

## 1. Purpose

The committed sentence puts the split "on the primary arm at the run's own station-fit
`Z0 = 44.2075 + j0.3794`" **[L]** `complex_load_analysis_2026-11-04.md`:168. Two things are wrong with it. It names
no record, and `44.2075 + j0.3794` is the **pre-fix `beta_one`** station fit, not the current `run.station_fit`. On
the current record the pair splits by **2.424 %**, not 13.08 %, so the headline "The common-factor hypothesis does
not survive" **[L]** `:172-178` is stated at a Z0 the record does not hold.

## 2. The four reference numbers and where each one lives

| value | what it is | source |
|---|---|---|
| `0.34465` | series-R closed form `50/(50 + 2*47.54)` at a stated `Z0` | **[L]** `defect_register.md`:342, `closed_form_with_two_wave_beta_2026-11-02.md`:14 |
| `0.307` / `0.724` | one complex-load TE model, s11 and s21, at `Z0 = 47.54` | **[L]** `complex_load_analysis_2026-11-04.md`:18, `:151` ("TE reference, not in any artefact") |
| `82.11518049761072 - j20.78227124428749` ohm | measured plane impedance that model sits on | **[M]** `evidence/termination/build_A_50ohm_v3_zeff.json`:334-337, `z_eff_measurement.z_eff.{re,im}` |
| `0.46 %` vs `0.589 %` | same conclusion, two figures, both at `Z0 = 47.54` | **[L]** `s11_refit_from_phasors_2026-11-04b.md`:59 against `complex_load_analysis_2026-11-04.md`:165-167 |

Not a contradiction: at `47.54` the mean-relative split is **0.3812 %** two-wave and **0.4802 %** on the graded
one-wave `s11.magnitude_one_wave_station_fit` **[M]** (0.32588679434738205 / 0.307214 against 0.7644184907560716 /
0.724087). The refit doc's `0.307`/`0.724` are 3-s.f. truncations of those, so `0.46 %` rounds `0.4802 %`.

## 3. What the committed sentences actually say

- **[L]** `complex_load_analysis_2026-11-04.md`:19 - "| station-fit Z0 (arm) | `44.207501 + j0.379446` ohm | `run.station_fit.z0_re/z0_im` |". A key path. No artefact named.
- **[L]** `:168-171` - "On the primary arm at the run's own station-fit `Z0 = 44.2075 + j0.3794` the two factors **split**: `f_s11 = 0.9596` (`-4.0 %`) against `f_s21 = 1.1040` (`+10.4 %`) - a **13.08** % disagreement, and no common factor exists. At `42.4379 - j15.7280` they split by `3.42 %` and point the same way but are not equal."
- **[L]** `:165-167` - the `47.54` row, stated as **0.589 %**, not 0.46 %.

## 4. Which record `44.2075 + j0.3794` belongs to

**[L]** `s11_refit_from_phasors_2026-11-04b.md`:37 - "the `beta_one` row *is* the pre-fix record's
`run.station_fit` (44.207500737130495 + j0.3794459968505162)"; `:68` - "DR-29 ... 44.207500737130495 ... still quoted
where the record's own `run.station_fit` is 47.364066848187235 + j1.6449807931078728 ... a pre-fix leftover". **[M]**
`evidence/termination/build_A_50ohm_p51_phasors.json`:279-280 holds those two numbers, so the clause "at the run's own
station-fit Z0" points at the record that is not being graded.

## 5. The split at four candidate Z0 (mean-relative, POST `s21` = 0.7644184907560716 **[M]** `p51_phasors.json`:397)

| `Z0` (ohm) | what it is | `f_s11` | `f_s21` | split |
|---|---|---|---|---|
| `44.207500737130495 + j0.3794459968505162` | pre-fix `beta_one` fit, not on the current record **[L]** | 0.9595708332263146 | 1.106273672783321 | **14.20 %** |
| `47.364066848187235 + j1.6449807931078728` | **the current `run.station_fit`** **[M]** `:279-280` | 1.0302754076570086 | 1.0555606801373751 | **2.424 %** |
| `47.54` real | TE model, in no artefact **[L]** | 1.0597320197876334 | 1.0556998834268756 | **0.3812 %** |
| `42.43786214405251 - j15.727993189312496` | `line.z0` **[M]** `:190-191` | 1.0564628184579967 | 1.0961103733162 | **3.684 %** |

`f = 1/|1 + Z0/Z|` on both arms, `|s11|` = 0.32556486641109117 **[M]** `:286`. Two corrections to the
committed percentages follow:

- **Denominator.** The doc's splits are `|f_s11 - f_s21| / f_s21`, not mean-relative: `13.08 %` =
  0.144429/1.104000, `3.42 %` = 0.037393/1.093857, `0.589 %` = 0.006202/1.053530. Mean-relative on the
  POST `s21` those rows are 14.20 %, 3.684 %, 0.3812 %.
- **Arm.** `f_s21 = 1.1040` requires `s21 = 0.7628473102840976`, the PRE arm quoted as
  `build_A_50ohm_v3_flux_off_pin.json` (`_v3_zeff`, `_v3_settling`, `_v3_lumped_check` agree bit-for-bit)
  **[L]** `s11_refit_from_phasors_2026-11-04b.md`:49; there `13.08 %` is reproduced as `|delta|/f_s21` and
  `13.998 %` mean-relative. The s11 side does not move with the arm (`s11.magnitude` is bit-identical on PRE
  and POST, `:47`), so the s21 side alone carries the change: the POST `s21` gives `f_s21 = 1.106274` and 14.20 %.

## 6. Which bracket fired, and the verdict: (d)

B1 does not fire as stated (13.08 % does not reproduce under a mean denominator - 14.20 % on POST `s21`,
13.998 % on `_v3_zeff`, 13.083 % only as `|delta|/f_s21` on `_v3_zeff`). B2 does not fire (2.424 % > 2). B3 fires
in substance (0.3812 % two-wave, 0.4802 % one-wave at 47.54, i.e. sub-0.5 %, so `0.46 %` is sound arithmetic).
B4 does not fire. **B5 fires: the current fixture splits by 2.424 %, inside 2-5 %.**

**Verdict (d), intermediate.** Neither a common scale nor two full biases: the factors are 2.424 % apart on the record the
session actually grades, agree to 0.38 % only at a `Z0` no artefact stores, and diverge by 14.20 % only at a
station fit the record does not hold. Report the number as measured, do not tidy it into either a scale factor
or a pair of biases, and do not quote 13.08 % as the current record's disagreement.

## 7. What would settle it

A second artefact carrying both `z_eff_measurement` and a **named record beside every stored Z0** - the
`run.station_fit` row written with the artefact path in the same breath - plus a structured `z0_model` key. Today
`z0_model` survives only as a string in `summary_line` (`"z0_model=48.0987ohm"` **[M]** `p51_phasors.json`:418) and
`47.54` lives in no `evidence/termination/*.json` at all. Until a `Z0` can be cited with its record, every split
figure here is only as good as its bracket.
