# Anchor-note extraction from `evidence/termination/*.json`

Extracts the 'anchor does not describe the structure' note from the 6 records identified in `residual_vs_configuration_survey_2026-11-04.md` §5. TE Q1 requires this before any anchor decision. No anchor value overwritten; this is record inspection only.

Wrap note: the provenance line above, the six rows of §1, the three rows of §3 and the six rows of §4
exceed 126 characters. Each is either the mandated verbatim provenance sentence or a table cell holding a
verbatim record string, which a wrap would alter. Every other line is <= 126 characters.

## 1. The six records that carry the note

Population: 61 JSON under `evidence/termination/`; 26 carry a non-empty `s11.validation_reason`, and only
those 26 are in scope. The note was found by exact-substring search on its 331 characters, not by filename,
so membership is measured, not inherited from the survey's candidate list. It is present in exactly 6
records -- exactly the 6 the survey listed (`v3c`, `B_v3c`, `B_v3d`, `E_v3c`, `E_v3d`, `twin_p51_s11fix`),
so **the survey's count and membership are CONFIRMED, not corrected.**

The note is character-identical in all six (whole-string equality, at offsets 734, 735, 735, 735, 735 and
829 into the respective reasons). It contains no `|`, so this table needs no cell escaping.

|artefact slug|note text (verbatim, identical in all six records)|s11.magnitude|s11.magnitude_one_wave_station_fit|
|---|---|---|---|
|build_A_50ohm_v3c|Structural note (2026-11-02): the strip mask is PEC-continuous from the port plane to the far xmax PEC wall (emfit/studies.py:2704-2712), so the load sits in series with a shorted stub instead of terminating a matched line; the series-R anchor cited above therefore does not describe this structure. See dispatch_log.md 2026-11-02.|0.32556486641109117|0.23216690987276836|
|build_B_100ohm_v3c|Structural note (2026-11-02): the strip mask is PEC-continuous from the port plane to the far xmax PEC wall (emfit/studies.py:2704-2712), so the load sits in series with a shorted stub instead of terminating a matched line; the series-R anchor cited above therefore does not describe this structure. See dispatch_log.md 2026-11-02.|0.47388432093505184|0.3558844270127778|
|build_B_100ohm_v3d|Structural note (2026-11-02): the strip mask is PEC-continuous from the port plane to the far xmax PEC wall (emfit/studies.py:2704-2712), so the load sits in series with a shorted stub instead of terminating a matched line; the series-R anchor cited above therefore does not describe this structure. See dispatch_log.md 2026-11-02.|0.47388432093505184|0.3558844270127778|
|build_E_50ohm_v3c|Structural note (2026-11-02): the strip mask is PEC-continuous from the port plane to the far xmax PEC wall (emfit/studies.py:2704-2712), so the load sits in series with a shorted stub instead of terminating a matched line; the series-R anchor cited above therefore does not describe this structure. See dispatch_log.md 2026-11-02.|0.29695101670715723|0.2230811132203571|
|build_E_50ohm_v3d|Structural note (2026-11-02): the strip mask is PEC-continuous from the port plane to the far xmax PEC wall (emfit/studies.py:2704-2712), so the load sits in series with a shorted stub instead of terminating a matched line; the series-R anchor cited above therefore does not describe this structure. See dispatch_log.md 2026-11-02.|0.29695101670715723|0.2230811132203571|
|build_A_50ohm_twin_p51_s11fix|Structural note (2026-11-02): the strip mask is PEC-continuous from the port plane to the far xmax PEC wall (emfit/studies.py:2704-2712), so the load sits in series with a shorted stub instead of terminating a matched line; the series-R anchor cited above therefore does not describe this structure. See dispatch_log.md 2026-11-02.|0.23216690987276836|ABSENT — key not present in `s11`; this record's `s11.magnitude` is itself the one-wave value|

Five of the six store a two-wave `magnitude` with a one-wave `magnitude_one_wave_station_fit` beside it.
`twin_p51_s11fix` stores no one-wave key, and its own first sentence says its `magnitude` *is* the one-wave
station fit (`0.23216690987276836`), which is the value 18 other records keep in the one-wave column. So
that record's `magnitude` is not comparable with the other five, and the note's antecedent ("the series-R
anchor cited above") resolves differently there -- see §4.

## 2. Is it one reason or several?

One reason, character-identical rather than merely similar. The distinguishing clause, quoted from §1 and
wrapped here for readability only:

> the strip mask is PEC-continuous from the port plane to the far xmax PEC wall (emfit/studies.py:2704-2712),
> so the load sits in series with a shorted stub instead of terminating a matched line; the series-R anchor
> cited above therefore does not describe this structure.

Keyword spread over the 26 inspected records: `PEC-continuous` 6, `shorted stub` 6, `2704` 6, `does not
describe` 6, `does not apply` 0, `not applicable` 0. Every hit is one of the six note-carriers; none of the
20 no-note records contains any part of the argument, so there is no second wording, no weaker variant, and
no record that gestures at the objection without spelling it out.

**X1 fires. X2 does not fire** -- nothing differs materially to weigh.

Qualification that X1 should not be read past: six identical strings are one authored sentence copied six
times, not six independent derivations. That establishes the claim is uniformly *stated*, not that the
PEC-continuity argument is *true*; no code was read, so `emfit/studies.py:2704-2712` was not checked
against the sentence citing it.

## 3. Records that carry no note (3 of the 20, in full)

The 20 no-note records carry only 3 distinct strings: 18 byte-identical copies of the R=50 boilerplate,
plus `v3_farstations` and `v3_modal`, which are that boilerplate with two words changed. Word-level diff:

* `build_A_50ohm_v3_farstations` (1 record): 2 changes -- `0.3256` -> `0.3186`; `5.54` -> `7.57`
* `build_A_50ohm_v3_modal` (1 record): 2 changes -- `0.3256` -> `0.3254`; `5.54` -> `5.58`

|artefact slug|s11.magnitude|s11.validation_reason (in full)|
|---|---|---|
|build_A_50ohm_p51_phasors|0.32556486641109117|the magnitude above is the modulus of the two-wave B/A, not the one-wave station-fit reflection (that is kept beside it as magnitude_one_wave_station_fit).  On the R=50 record it reads 0.3256 against the series-R anchor 0.34465, i.e. 5.54 percent low.  The residual disagreement is unexplained: no read of station_fit.gamma_v or of the reference construction has been done, so the status stays. Residual is configuration-dependent: 5.5% (n=64, load 20mm), 7.6% (n=54, 100 ohm), 13.8% (n=79, load 30mm). The two-wave modulus is better than one-wave but not converged -- the load's near-field extends to the last station and contaminates the fit. Moving the extraction plane further from the load, or modal projection, would reduce it.|
|build_A_50ohm_v3_farstations|0.31855316298171493|the magnitude above is the modulus of the two-wave B/A, not the one-wave station-fit reflection (that is kept beside it as magnitude_one_wave_station_fit).  On the R=50 record it reads 0.3186 against the series-R anchor 0.34465, i.e. 7.57 percent low.  The residual disagreement is unexplained: no read of station_fit.gamma_v or of the reference construction has been done, so the status stays. Residual is configuration-dependent: 5.5% (n=64, load 20mm), 7.6% (n=54, 100 ohm), 13.8% (n=79, load 30mm). The two-wave modulus is better than one-wave but not converged -- the load's near-field extends to the last station and contaminates the fit. Moving the extraction plane further from the load, or modal projection, would reduce it.|
|build_A_50ohm_v3_modal|0.32542053779079727|the magnitude above is the modulus of the two-wave B/A, not the one-wave station-fit reflection (that is kept beside it as magnitude_one_wave_station_fit).  On the R=50 record it reads 0.3254 against the series-R anchor 0.34465, i.e. 5.58 percent low.  The residual disagreement is unexplained: no read of station_fit.gamma_v or of the reference construction has been done, so the status stays. Residual is configuration-dependent: 5.5% (n=64, load 20mm), 7.6% (n=54, 100 ohm), 13.8% (n=79, load 30mm). The two-wave modulus is better than one-wave but not converged -- the load's near-field extends to the last station and contaminates the fit. Moving the extraction plane further from the load, or modal projection, would reduce it.|

`build_A_50ohm_p51_phasors` stands for the 18-copy cluster character for character; the other 17
(`sweepN63`, `sweepN65`, `v3_beta2wave`, `v3_betafix`, `v3_flux_off_pin`, `v3_flux_p51`, `v3_flux_p55`,
`v3_flux_p63`, `v3_flux_p65`, `v3_fluxcur_p51`, `v3_fluxcur_p55`, `v3_fluxcur_p63`, `v3_fluxcur_p65`,
`v3_lumped_check`, `v3_settling`, `v3_twin_check`, `v3_zeff`) are not reprinted because their strings are
identical, not similar. Several of them store a *different* one-wave value (`0.23216690987276836` where
`p51_phasors` stores `0.32588679434738205`) while carrying the same boilerplate that quotes `0.3256` -- a
separate inconsistency in the boilerplate, recorded here and not graded by any bracket of this dispatch.

Two things the no-note strings concede on their own terms: the residual is called "unexplained", and the
named remedy ("Moving the extraction plane further from the load") is exactly the lever the survey
measured as making the number worse.

## 4. Contradictions: note present AND an anchor residual still reported

**Fires on 6 of 6.** In every note-carrying record the same string first computes a percent-low residual
against the series-R anchor and only then appends the structural note saying that anchor does not describe
the structure. The residual is never marked superseded; the only backward pointer is the trailing "See
dispatch_log.md 2026-11-02". A reader who stops at the residual keeps the number and never meets the
retraction, which is the last thing in the string.

|artefact slug|residual still computed in the same string (verbatim fragment)|anchor quoted|percent|
|---|---|---|---|
|build_A_50ohm_v3c|On the R=50 record it reads 0.3256 against the series-R anchor 0.34465, i.e. 5.54 percent low.|0.34465|5.54|
|build_B_100ohm_v3c|On the R=100 record it reads 0.4739 against the series-R anchor 0.51263, i.e. 7.56 percent low.|0.51263|7.56|
|build_B_100ohm_v3d|On the R=100 record it reads 0.4739 against the series-R anchor 0.51263, i.e. 7.56 percent low.|0.51263|7.56|
|build_E_50ohm_v3c|On the R=50 record it reads 0.2970 against the series-R anchor 0.34465, i.e. 13.84 percent low.|0.34465|13.84|
|build_E_50ohm_v3d|On the R=50 record it reads 0.2970 against the series-R anchor 0.34465, i.e. 13.84 percent low.|0.34465|13.84|
|build_A_50ohm_twin_p51_s11fix|The trustworthy reflection on this record is the two-wave B/A: \|Gamma\| = 0.32556, 5.4% below the series-R anchor 0.345.|0.345|5.4|

Second, narrower inconsistency on `twin_p51_s11fix`: its `0.34465` is **not** its anchor. There `0.34465`
is the synthetic-fit result ("the two-wave fit returns |Gamma|=0.34465 exactly") while the anchor is
written `0.345`. So a `0.34465` grep used as an anchor marker misclassifies that record, and misclassifies
`B_v3c`/`B_v3d` the opposite way (no `0.34465` at all). §5 counts string presence and flags the distinction
rather than silently repurposing it.

**X3 fires.** The consistency measured in §2 is consistency of the sentence, not of the record: six records
state the same caveat and six records keep computing the number the caveat withdraws.

## 5. Counts, measured from the files

|quantity|measured|
|---|---|
|JSON files under `evidence/termination/`|61|
|records inspected (non-empty `s11.validation_reason`)|26|
|contain `0.34465` in `s11.validation_reason`|24|
|contain `0.34465` anywhere in the record file|24|
|carry the note|6|
|do not carry the note|20|
|distinct `validation_reason` strings across the 26|7|
|store `magnitude` = 0.32556486641109117 ("the same 0.325565")|19|
|of those, carrying the note|1 (`v3c`)|
|of those, no note|18|

The 2 records without `0.34465` are `build_B_100ohm_v3c` and `build_B_100ohm_v3d`; both quote the R=100
anchor `0.51263` instead, and both carry the note. So the note is not confined to records quoting the R=50
anchor: 4 of the 6 quote `0.34465`, 2 of the 6 quote `0.51263`.

**Correction owed to §5 of the survey.** It says "6 of the 26 records quoting the anchor 0.34465".
Measured, 26 is the number of records with a `validation_reason` and 24 is the number quoting `0.34465`, so
the exact statement is "6 of the 26 records with a `validation_reason`, 4 of the 24 quoting `0.34465`".
The qualitative claim -- 6 carry the note, 18 print `0.325565` without one -- is correct as written: 19
records store that magnitude, 1 (`v3c`) carries the note, the other 18 do not.

## 6. Brackets

|bracket|fires|why, measured|
|---|---|---|
|X1|YES|one reason, character-identical in 6 of 6; no variant wording exists in the population|
|X2|no|nothing differs materially; the 3 no-note strings differ in 2 words each|
|X3|YES|6 of 6 report a residual against the anchor the note calls inapplicable, in the same string|
|X4|no|it says verbatim "the series-R anchor cited above therefore does not describe this structure"|

On X4: the survey's paraphrase is faithful and, if anything, understated -- the note does not call the
anchor imprecise, it says the anchor *does not describe this structure*. So §5's reading is not a
misreading and needs no correction beyond the denominator in §5 above.

## 7. What this dispatch does not settle

Whether the PEC-continuity argument is sound. It was read here only as text: `emfit/studies.py:2704-2712`
was not opened, nothing was re-run, and no anchor value was recomputed, overwritten or withdrawn. If X3 is
accepted, the open question for the anchor decision is not "is the note right" but "which number
stands" -- and as the records currently read, both stand, in the same sentence, with no marker.

