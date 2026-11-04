# Z0 provenance and the twin record — 2026-11-04

Read-only analysis of `emfit/` and `evidence/termination/`. No source change, no FDTD run, no commit. Line numbers are HEAD, `emfit/studies.py` unless another file is named.
Task A: where the station fit's `Im(Z0)` comes from. Task B: why one record carries two `Z0` pairs. Task C: whether the twin artefact grades AC-3.

## 0. Records and provenance

Authoritative twin: `evidence/termination/build_A_50ohm_twin_p51_s11fix_twin.json` (untracked, 9012 B, sha256 `0477dbb3…69908a`, mtime 2026-11-01T23:28:59); parent
`build_A_50ohm_twin_p51_s11fix.json` tracked at HEAD (blob `b59573bc…`, 16594 B, sha256 `8ca42bce…d98e2d18`), cited by rows `s11-port-reference-2026-11-02`,
`s11-one-wave-vs-two-wave-2026-11-02` and `s11_one_wave_vs_two_wave_2026-11-02.md`:55, :59. The older `build_A_50ohm_twin_p51_twin.json` (9019 B, `9a6bd65d…aa1328a`,
2026-11-01T21:56:25) has an untracked parent but is numerically identical on every number — zc `47.53661998575833+1.9309048088852248j`, |s21| `0.9979654737487207`, |s11|
`0.011138463116453862`, `line.z0` `49.4259949734449+16.33275604971187j`, alpha `3.156516450473238`; beta `231.0873600620821` in the twin against `231.55331672912826` loaded —
so no result depends on the choice. Loaded arm: `build_A_50ohm_p51_phasors.json`. The twin is a **load-free through reference**, not an absorbing termination:
`run.reference_produced` populated, `run.kwargs.loads` dropped, `geometry.load_station_excluded` 0.0, `n_pml` 6 at both ends, no resistor anywhere.

## 1. Task A — provenance of `Im(Z0)`

**The fit reproduced.** `run.station_fit.z0 = 47.364066848187235 + 1.6449807931078728j` reproduced bit-identically from `build_A_50ohm_p51_phasors.json` `/s11/station_phasors`
with `fit_station_impedance(fit_x, fit_v, fit_i, beta=231.55331672912826)` (8 of 9 stations, `fit_selected` last false; `studies.py:3471` → `emfit/ports.py:1429`, alpha 0.0 at
`:1430`/`:1510`): `|gamma_v| = 0.32588679434738205`, `|z0| = 47.3926237953676`, `arg z0 = 1.9891` deg. `beta*fit_span = 231.5533*0.0084 = 1.9450478605246773` rad is the
**s11-fit span**, not the station span 0.0096.

**What offset would manufacture `Im = +1.645` ohm.** A relative E/H time offset δ rotates `z0` by `ωδ` and leaves `|z0|`, `|gamma_v|` and `|gamma_i|` untouched, so it must
supply exactly `arg z0 = 0.03471661075984311` rad = 1.9891 deg: `ω = 2π*5827786408.327286 = 3.6617e10` rad/s, `δ = 0.0347166/ω = 9.480992992349922e-13` s = `1.2431970472109202`
dt (`geometry.dt = 7.626299478123987e-13` s); in space `δx = 0.0347166/beta = 0.00014992923120360526` m = `0.37482307800901316` cell (`geometry.cell = 0.0004` m, one third of
the 1.2 mm station spacing), i.e. 12.5 % of a station interval and 1.56 % of the 0.0096 station span. The scheme's own constants fall elsewhere: 0.5 dt = 0.1507 cell → `Im =
47.364*tan(0.013963) = +0.661` ohm; 1 dt = 0.3015 cell → `+1.323` ohm.

**A1 — temporal staggering between the E and H sampling uncompensated, so `Im(Z0)` may carry a systematic phase error. VERDICT: does not fire.** Stated plainly, the required
offset is **sub-cell** (0.375 cell, 2.49 half-steps), so on magnitude alone A1 is **not** excluded — say so rather than let the verdict imply it was. It does not fire because
no staggering constant the scheme can have takes that value: 1.2432 dt is neither 0.5 nor 1.0 dt, and the two admissible constants predict +0.661 and +1.323 ohm against the
observed +1.645, so staggering is at most a partial, non-exclusive contributor and not the source.

**A2 — E and H aligned, collocated or compensated by the fit, so `Im(Z0)` is physical, or fit noise. VERDICT: FIRES — this is the answer.** Supporting evidence: the s11 path
never consumes the reference (`studies.py:3563-3567`, `emfit/ports.py:1517`, `emfit/ports.py:1385-1399`); the only reference read in that block is the dead `if station_fit is
None` branch at `studies.py:3603-3606`; and the reference only ever enters s21 (`studies.py:3660-3675` / `:3637-3657` / `:3676-3687`), where `forward_ratio` (`:1766-1800`,
rescaled `ratio ** (run_span/station_span)`) returns 1 bit-for-bit on the station planes. Two decisive negatives: (1) the estimator is unbiased — a synthetic lossless one-wave
at the same 8 stations returns zc to 1.5e-15 with |gamma_v| 1.8e-16; (2) the unmodelled decay is not the cause — refitting the real phasors at the fitted `alpha =
3.156516450473238` gives `47.27528626366384 + 1.8638615174299071j`, so `Im/Re` only moves 3.47 % → 3.94 % (alpha 1 → `47.33618154732435+1.714466317668478j`; alpha 6 →
`47.19342503018462+2.0598722389808732j`). Conclusion: `Im = +1.645` ohm (`Im/Re` 3.47 %) is a property of the measured station phasors — a differential decay and phase between
the `v` and `i` series over 1.945 rad of span at `|gamma_v| = 0.3259` — not of a phasor timing offset. Order-of-magnitude cross-check only, **not a decomposition**: a synthetic
pure-decay wave through the `alpha = 0` fit returns a spurious `|gamma_v| = 0.007587381794950257` against the twin's `s11.magnitude` `0.011138463116453862`, so part of the
twin's apparent 1.1 % reflection is the unmodelled 3 % decay — a bound, not a split (the twin stores no phasors, §4).

**A3 — ambiguous, escalate. VERDICT: does not fire.** A2 is not ambiguous: the phasors reproduce the recorded number bit-for-bit and both candidate artefact mechanisms were
tested and rejected above.

## 2. Task B — the two `Z0` pairs in one record

`line.z0` is `MicrostripWave.z0 = -complex(v_port/i_trunc)` at `:3553` — **one plane's V/I inside the port's own near field** (negated because `plate_current` sums the ground
return antiparallel; docstring `:1468-1476`, comment `:3544-3552`; written loaded at `run_build_A.py:1789-1790`, twin `:953-954`). `station_fit.z0` is the two-wave station fit
`amp_v[0]/amp_i[0]` (`emfit/ports.py:1516`) over the 8 stations at the fitted beta (`studies.py:3471`; loaded `run_build_A.py:1573-1578`, twin `:811-814`, whose `zc_basis` says
"the twin's `station_fit.z0` … not the closed-form z0"). `reference_block` (`run_build_A.py:776-837`) is **one** code path emitted twice (`:1510`, `:903`), so the twin and the
loaded arm cannot disagree. So `49.4259949734449+16.33275604971187j` (`line.z0`) and `47.53661998575833+1.9309048088852248j` (`reference_produced.zc`) are **two different
quantities, not a contradiction** — +7 % real, ×8 imaginary, the port near field (the "+17 deg excess phase" the docstring names; here arg 18.28 deg against the loaded
`line.z0` arg −20.33 deg, `|line.z0| = 45.26`) — and only `zc` is ever consumed, as the normalisation (`studies.py:1760`).

**B1 — twin Z0 agrees with the loaded real component, with small imaginary part. VERDICT: FIRES.** Twin `station_fit.z0 = 47.53661998575833+1.9309048088852248j` against loaded
`47.364066848187235+1.6449807931078728j`: real parts agree to 0.36 %, imaginary parts 1.645 → 1.931 (0.29 ohm apart). The load-free field and the loaded field give the same
line impedance, so the twin is a usable normalisation.

**B2 — twin `z0_re` ≈ 44.21, i.e. the retired `beta_one` value is the line Z0, re-opening DR-29. VERDICT: does not fire.** The real part is 47.54, not 44.21
(`44.207500737130495 + 0.3794459968505162j` is the pre-fix `beta_one` fit and is superseded).

**B3 — twin `z0_re` neither ≈ 47.36 nor 44.21, ambiguous, escalate. VERDICT: does NOT fire** — but the bracket set has a defect that must be recorded with it: B1 and B3
**overlap** for real parts between 47.36 and 47.54, i.e. about 0.35 %, so B3's literal "neither ≈ 47.36" must not be allowed to fire on a 0.36 % difference. That is a defect in
the bracket set, not a finding.

## 3. Task C — AC-3

The bar is `|S11| <= 1.0e-3` **and** `||S21| - 1| <= 1.0e-3` (`docs/design/absorbing_termination_scope.md`:235-238, `:560`). Pre-registered: **C1** meets the bar with
conditions 1-5 verified → first AC-3 pass; **C2** |S11| in 1e-3..0.02 or ||S21|-1| > 1e-3 → no pass, twin values become the grading target; **C3** |S11| > 0.02 or |S21| outside
[0.98, 1.02] → ungradeable, escalate. **VERDICT: none of C1, C2, C3 applies. Correct label: UNCLASSIFIED, raw values preserved.** Raw: `|s11| = 0.011138463116453862` (11× the
1e-3 bar), `|s21| = 0.9979654737487207` (`||S21|-1| = 2.035e-3`, 2× the bar); and `|s21| == |raw|` to 1e-16 because `deembed_transmission` with a real beta is unit modulus. The
reason is structural: the artefact is a **load-free through reference**, not an absorbing termination and not an arm — `run.reference_produced` populated, `run.kwargs.loads`
dropped, `s21_plane` None, `geometry.load_station_excluded` 0.0, `n_pml` 6 at both ends, no resistor anywhere — so AC-3 is not addressed by this artefact at all and must
**not** be re-graded from it. C2 is deliberately **not** applied: C2 would make the twin a grading target and it is not a candidate subject.

## 4. Not verifiable from the artefacts

- The twin's station phasors (no `station_phasors` block): the `+0.1726+0.2859j` cross-record `station_fit` gap and any decomposition of the twin's `|s11| = 0.011138` into decay artefact against field.
- `station_fit_lossy` z0 for either record — never written to JSON.
- `beta_one` on this block — stored null (reconstructed elsewhere as `fit_beta(n_wave=1)` = 286.35930483082825).
- Any AC-3 verdict for the twin — no load by construction, so the gate has nothing to grade.
- `meta.git_rev` — null (DR-28).

## 5. Convention notes cited above

`deembed_reflection` (`emfit/ports.py:1673`) carries `exp(-2j beta d)`; `line_s21`/`deembed_transmission` (`:1707-1731`) carries `exp(+1j beta distance)`, contrast documented
at `:1716-1719`. `LineFit.alpha` is `:1010`. Loads in the loaded arm resolve at `studies.py:3070` (`loads_used[-1]["column"]`), not in `emfit/evolve.py`.
