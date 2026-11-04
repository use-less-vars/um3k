# Residual vs configuration survey -- 2026-11-04

**Status:** complete, read-only. Nothing was run, edited or re-graded to produce it. Population: every
artefact in `evidence/termination/` (61 JSON files).

**Question:** is the |s11| residual against the series-R anchor a property of the *configuration* -- which
load, which line length, which station span -- or of the *estimator* used to read it?

**Answer:** of how the reflection is read, not of the configuration. On one geometry (n = 64, R = 50 ohm,
load at 20 mm) the two-wave read is -5.54 percent, AC-3's pre-fix one-wave field -32.64 percent, the
post-fix one-wave field -5.44 percent; the code vintage moves it further. Over the same rows, doubling the
load moves the residual 2 pp. The record's own hypothesis is V1; it does not fire.

## 1. The anchor, and how it was recovered

The load is a series resistor at the end of the line, so at the load plane `Gamma = R/(2*Z0 + R)` and
`T = 2*Z0/(2*Z0 + R)`. The two anchors a record prints -- 0.34465 (R = 50 ohm), 0.51263 (R = 100 ohm) --
invert to `Z0 = 47.5373` and `47.5362 ohm`, agreeing to 2e-5 and 0.006 percent under the TE 47.54. Used
here: `Z0 = 47.5373 ohm` throughout, |s11| anchor 0.344650 / 0.512624, |s21| anchor 0.655350 / 0.487376.

The 0.724 figure in `complex_load_analysis_2026-11-04.md` is a TE complex-load model, printed by no
artefact here, and is **not** used. A record with no load has no anchor: section 4.

## 2. Population, and how it was counted

61 files found: 58 run artefacts plus 3 grade outputs (`graded.json`, `graded_v2.json`,
`graded_v2_refix.json`; keys criteria/verdict/inputs, no S-parameters) which are excluded. Of the 58:
**36 comparable**; **12 nc** -- reflection not transported to the measurement plane, |s11| 0.02-0.05 against
an anchor of 0.34 (`p51_noref`, `sweepN51/53/55/57/59`, `through_p51`, `v3b_c51/c53/c55/c57`, `twin_p51`),
kept in the table with no residual so the hole is visible; **10 not anchored** -- no load, section 4.

The `|s11|` column is AC-3's `ac.AC-3.achieved.s11_abs`: one-wave `s11.magnitude_one_wave_station_fit`
where present (25 of 58), else two-wave `s11.magnitude`, every row tagged `1w`/`2w`. `src` is `s` where the
record prints the anchor in its own `validation_reason` (26 of 58), `d` where the anchor is the closed form
and only sibling records print it.

## 3. The table

`span/gap` is `line.station_fit_cells` x 0.4 mm, first to last station, then the distance from the last
station to the load. `same sign` = the |s11| and |s21| residuals carry the same sign. The |s21| columns are
context, not a verdict: 13 of the 36 comparable rows read |s21| above 1.0 with one passive load in the
model, and this survey does not diagnose that.

|file|n|load|span/gap mm|src|s11|est|s11 anchor|resid %|sign|s21|s21 anchor|resid %|sign|same sign|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|build_A_50ohm.json|54|50@20|--|d|0.219615|2w|0.344650|-36.28|low|1.105185|0.655350|+68.64|high|no|
|build_A_50ohm_cal.json|64|50@20|10.4-18.8/1.2|d|0.339282|2w|0.344650|-1.56|low|1.121812|0.655350|+71.18|high|no|
|build_A_50ohm_p51_phasors.json|64|50@20|10.4-18.8/1.2|s|0.325887|1w|0.344650|-5.44|low|0.764418|0.655350|+16.64|high|no|
|build_A_50ohm_sweepN63.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.729132|0.655350|+11.26|high|no|
|build_A_50ohm_sweepN65.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.724569|0.655350|+10.56|high|no|
|build_A_50ohm_twin_p51_s11fix.json|64|50@20|10.4-18.8/1.2|s|0.232167|2w|0.344650|-32.64|low|0.767557|0.655350|+17.12|high|no|
|build_A_50ohm_v2.json|54|50@20|--|d|0.332738|2w|0.344650|-3.46|low|1.113791|0.655350|+69.95|high|no|
|build_A_50ohm_v3.json|54|50@20|--|d|0.299069|2w|0.344650|-13.23|low|1.129942|0.655350|+72.42|high|no|
|build_A_50ohm_v3_beta2wave.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.762847|0.655350|+16.40|high|no|
|build_A_50ohm_v3_betafix.json|64|50@20|10.4-18.8/1.2|s|0.325887|1w|0.344650|-5.44|low|0.764418|0.655350|+16.64|high|no|
|build_A_50ohm_v3_farstations.json|64|50@20|3.6-13.2/6.8|s|0.189821|1w|0.344650|-44.92|low|0.763737|0.655350|+16.54|high|no|
|build_A_50ohm_v3_flux_off_pin.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.762847|0.655350|+16.40|high|no|
|build_A_50ohm_v3_flux_p51.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.468419|0.655350|-28.52|low|yes|
|build_A_50ohm_v3_flux_p55.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.465377|0.655350|-28.99|low|yes|
|build_A_50ohm_v3_flux_p63.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.459793|0.655350|-29.84|low|yes|
|build_A_50ohm_v3_flux_p65.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.459838|0.655350|-29.83|low|yes|
|build_A_50ohm_v3_fluxcur_p51.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.759494|0.655350|+15.89|high|no|
|build_A_50ohm_v3_fluxcur_p55.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.745970|0.655350|+13.83|high|no|
|build_A_50ohm_v3_fluxcur_p63.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.729120|0.655350|+11.26|high|no|
|build_A_50ohm_v3_fluxcur_p65.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.724552|0.655350|+10.56|high|no|
|build_A_50ohm_v3_lumped_check.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.762847|0.655350|+16.40|high|no|
|build_A_50ohm_v3_modal.json|64|50@20|10.4-18.8/1.2|s|0.232026|1w|0.344650|-32.68|low|0.780375|0.655350|+19.08|high|no|
|build_A_50ohm_v3_settling.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.762847|0.655350|+16.40|high|no|
|build_A_50ohm_v3_twin_check.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.767557|0.655350|+17.12|high|no|
|build_A_50ohm_v3_zeff.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.762847|0.655350|+16.40|high|no|
|build_A_50ohm_v3b_c59.json|54|50@20|10.4-18.8/1.2|d|0.290525|2w|0.344650|-15.70|low|0.054605|0.655350|-91.67|low|yes|
|build_A_50ohm_v3b_s11fix.json|54|50@20|10.4-18.8/1.2|d|0.341397|2w|0.344650|-0.94|low|1.116628|0.655350|+70.39|high|no|
|build_A_50ohm_v3c.json|64|50@20|10.4-18.8/1.2|s|0.232167|1w|0.344650|-32.64|low|0.767557|0.655350|+17.12|high|no|
|build_B_100ohm.json|54|100@20|--|d|0.351786|2w|0.512624|-31.38|low|1.145042|0.487376|+134.94|high|no|
|build_B_100ohm_v2.json|54|100@20|--|d|0.474119|2w|0.512624|-7.51|low|1.167515|0.487376|+139.55|high|no|
|build_B_100ohm_v3c.json|54|100@20|10.4-18.8/1.2|s|0.355884|1w|0.512624|-30.58|low|1.177980|0.487376|+141.70|high|no|
|build_B_100ohm_v3d.json|54|100@20|10.4-18.8/1.2|s|0.355884|1w|0.512624|-30.58|low|1.165027|0.487376|+139.04|high|no|
|build_E_50ohm.json|79|50@30|--|d|0.236123|2w|0.344650|-31.49|low|1.013186|0.655350|+54.60|high|no|
|build_E_50ohm_v2.json|79|50@30|--|d|0.354909|2w|0.344650|+2.98|high|1.010236|0.655350|+54.15|high|yes|
|build_E_50ohm_v3c.json|79|50@30|10.4-20/10|s|0.223081|1w|0.344650|-35.27|low|1.010236|0.655350|+54.15|high|no|
|build_E_50ohm_v3d.json|79|50@30|10.4-20/10|s|0.223081|1w|0.344650|-35.27|low|1.015230|0.655350|+54.91|high|no|
|build_A_50ohm_p51_noref.json|64|50@20|10.4-18.8/1.2|d|0.033793|2w|--|--|--|0.762847|--|--|--|--|
|build_A_50ohm_sweepN51.json|64|50@20|10.4-18.8/1.2|d|0.033793|2w|--|--|--|0.762847|--|--|--|--|
|build_A_50ohm_sweepN53.json|64|50@20|10.4-18.8/1.2|d|0.023746|2w|--|--|--|0.751789|--|--|--|--|
|build_A_50ohm_sweepN55.json|64|50@20|10.4-18.8/1.2|d|0.022797|2w|--|--|--|0.746155|--|--|--|--|
|build_A_50ohm_sweepN57.json|64|50@20|10.4-18.8/1.2|d|0.023302|2w|--|--|--|0.741876|--|--|--|--|
|build_A_50ohm_sweepN59.json|64|50@20|10.4-18.8/1.2|d|0.023660|2w|--|--|--|0.737832|--|--|--|--|
|build_A_50ohm_through_p51.json|64|50@20|10.4-18.8/1.2|d|0.033793|2w|--|--|--|0.762847|--|--|--|--|
|build_A_50ohm_twin_p51.json|64|50@20|10.4-18.8/1.2|d|0.048999|2w|--|--|--|0.767557|--|--|--|--|
|build_A_50ohm_v3b_c51.json|54|50@20|10.4-18.8/1.2|d|0.031351|2w|--|--|--|0.760091|--|--|--|--|
|build_A_50ohm_v3b_c53.json|54|50@20|10.4-18.8/1.2|d|0.023668|2w|--|--|--|0.748936|--|--|--|--|
|build_A_50ohm_v3b_c55.json|54|50@20|10.4-18.8/1.2|d|0.022092|2w|--|--|--|0.743462|--|--|--|--|
|build_A_50ohm_v3b_c57.json|54|50@20|10.4-18.8/1.2|d|0.056231|2w|--|--|--|0.668116|--|--|--|--|

## 4. The 10 records with no anchor

All ten are load-free twins -- the resistor removed, the run kept as a control -- so the anchor does not
exist. Nine read |s11| 0.0030-0.0111 with |s21| 0.9876-1.0022, which is what an unloaded line should read;
`build_smoke_50ohm_twin` does not.

|file|n|s11 two-wave|s21|note|
|---|---|---|---|---|
|build_A_50ohm_twin_p51_s11fix_twin.json|64|0.011138|0.997965|control|
|build_A_50ohm_twin_p51_twin.json|64|0.011138|0.997965|control|
|build_A_50ohm_v3_twin.json|54|0.003496|0.987570|control|
|build_A_50ohm_v3_twin_check_twin.json|64|0.011138|0.997965|control|
|build_A_50ohm_v3b_s11fix_twin.json|54|0.003496|0.987570|control|
|build_A_50ohm_v3c_twin.json|64|0.011138|0.997965|control|
|build_smoke_50ohm_twin.json|44|0.173160|0.002888|not a control: \|s11\| 0.1732 against \|s21\| 0.0029|
|build_B_100ohm_v3d_p51_twin.json|54|0.003496|0.987570|control|
|build_B_100ohm_v3d_twin.json|54|0.003496|0.987570|control|
|build_E_50ohm_v3d_twin.json|79|0.002975|1.002237|control|

## 5. Verdicts

**V1 -- "all residuals within +-1 % of one value (or +-1.5 % if the spread is naturally a bit wider)",
i.e. one scale factor, so per-configuration calibration closes the gate and AC-4 is re-derivable with the
residual as a stated error bound, no further mechanism hunting, move to the product layer. DOES NOT FIRE.**
The 36 comparable rows span -36.28 to +2.98 percent -- 39 pp against a 2-3 pp bar -- and the span survives
restriction to the configuration the record calls fixed: at n = 64, R = 50 ohm, load 20 mm they still span
-32.64 to -1.56 percent. The three arms the record quotes do order monotonically (5.54 / 7.56 / 13.84,
section 6), but doubling the load moves the residual 2 pp while the estimator alone moves one geometry
27 pp.

**V2 -- the residual "correlates with one configuration parameter (monotone, >=2x spread across the
parameter's range)", so the mechanism has a home in that parameter and one targeted host run would name
it. DOES NOT FIRE, and this is the closest call here.** The station-to-load gap is monotone -- 1.2 mm
-5.54, 6.8 mm -7.57, 10.0 mm -13.84 percent -- and its ends are 2.5x apart, past the bar, but the three
points are confounded: n and the load distance move with the gap. The only clean single-parameter pair is
`v3_farstations` against the 1.2 mm baseline -- same n = 64, same load at 20 mm, same estimator, only the
station window moved -- and it reads -7.57 against -5.54, **1.37x**, under the bar. Mesh n is non-monotone
in the two-wave column (-36.28 at n = 54, -5.54 at n = 64, +2.98 to -31.49 at n = 79). The load value comes
closest -- 50 against 100 ohm at n = 54 with no station window reads -3.46 against -7.51 percent, 2.17x --
but the same pair one code vintage back reads -36.28 against -31.38, 1.16x, so the spread belongs to the
vintage and not to the parameter. No parameter reproduces 2x at fixed everything else; none is named; no
host run is licensed.

**V3 -- "the residual varies but no parameter correlates", so it is recorded and the instability is
characterized before any fix. FIRES.** On one geometry (n = 64, R = 50 ohm, load at 20 mm, one station
window) the reading alone produces -5.54 percent (two-wave), -32.64 (pre-fix one-wave) and -5.44 (post-fix
one-wave): 27 pp on a configuration that did not change. The code vintage produces more still -- the
A-family with no station window spans -36.28 to -3.46 percent at n = 54. Both axes that move the number
most are properties of how the reflection is read; the cleanest structural axis available (the load value,
2 pp) is the smallest of the three. This is the axis the record never tested.

**V4 (falsifier) -- the three quoted residuals do not reproduce, so `validation_reason` is prose drift, a
defect is registered, and the survey becomes the authoritative record. DOES NOT FIRE.** All three reproduce
to three decimals on the estimator they were taken on (section 6); no DR-31.

## 6. Parent addition -- estimator-restricted re-read

The three quoted residuals are two-wave readings, and that is not the column AC-3 grades. Re-read on the
two-wave column alone, over the same 36 rows:

- `0.32556486641109117 / 0.34465 = -5.537 percent` (n = 64, R = 50 at 20 mm; 19 records).
- `0.47388432093505184 / 0.51263 = -7.556 percent` (n = 54, R = 100 at 20 mm; `B_v3c`, `B_v3d`).
- `0.29695101670715723 / 0.34465 = -13.836 percent` (n = 79, R = 50 at 30 mm; `E_v3c`, `E_v3d`).

The span is -36.28 to +2.98 percent and no verdict moves; the estimator axis was never in the quoted comparison. All three
are negative -- the measured reflection is LOW; "positive = high" is not this population's convention. The file's own prose
("5.54 / 7.56 / 13.84 percent low") reproduces, as do its outliers 7.57 (`v3_farstations`, 0.318553) and 5.58 (`v3_modal`,
0.325421).

## 7. Findings

**(a) Both remedies are already on disk, and both are worse.** Every `validation_reason` closes with "Moving the extraction
plane further from the load, or modal projection, would reduce it." Both artefacts exist: on the two-wave reading they were
proposed against, `v3_modal` reads -5.58 percent and `v3_farstations` -7.57 percent, against -5.54 percent for the run they
were meant to improve. Both remedies therefore move the number the wrong way. The gap ladder of section 5 is monotone in the
direction that contradicts "move the plane further out".

**(b) The note that the anchor does not describe the structure is carried by 6 of the 26 records that quote
the anchor.** Verbatim:

> the strip mask is PEC-continuous from the port plane to the far xmax PEC wall (emfit/studies.py:2704-2712),
> so the load sits in series with a shorted stub instead of terminating a matched line; the series-R anchor
> cited above therefore does not describe this structure.

It appears in `v3c`, `B_v3c`, `B_v3d`, `E_v3c`, `E_v3d`, `twin_p51_s11fix`, and in none of the other 18
records printing the same 0.325565 as `v3c`. If it is right the residual is measured against an anchor that
does not apply. Recorded, not adjudicated.

**(c) AC-3 grades a number the prose beside it does not.** At n = 64, R = 50 ohm, load 20 mm it scores
`s11_abs` = 0.232167, i.e. -32.64 percent, on 18 records whose own sentence says 5.54 percent low: 27 pp
apart in the same record. Restated with counts only; the substance is DR-24's and is not re-diagnosed.

## 8. Namespace caution

`V1`-`V4` here are local to this doc. `A1`-`A3` in `z0_provenance_and_twin_2026-11-04.md` and `A1`-`A3` in
`spatial_collocation_audit_2026-11-04.md` are different axes under the same labels; `B1`-`B3` in
`z0_current_and_split_2026-11-05.md` and `B1`-`B6` in `deflation_v2_preregistration.md` likewise; `N1`-`N3`
and `N0a`/`N0b` belong to `near_field_subset_refit_2026-11-04.md`. `DR-nn` is the only namespace shared
across docs -- `defect_register.md`.

Nothing in this survey is a mechanism. It is a map of where the number goes wrong, and of which axis the
map is drawn on.

