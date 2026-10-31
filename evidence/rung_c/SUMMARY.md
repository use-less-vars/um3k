# Rung C: the `h = 0.2 mm` FDTD run, and the frozen verdict it converts

Marks: **[M]** measured against an artefact that exists in this tree (a JSON, a log, a line count);
**[L]** read from a named file and cited there; **[R]** relayed (an owner assertion or an out-of-tree
number carried into this record with no artefact behind it, marked and **not graded**). Every number
below carries one of the three.

Reference used by all three rungs, unchanged: `beta_hj_kj_graded = 384.7489756770833 rad/m` at the
common tone `10.19862621457275 GHz` [M, the three JSONs]. `d` is `100 * (beta / ref - 1)` in
**percentage points (pp)**; `gap` is `100 * (beta_eig / beta_fdtd - 1)` in **percent**. Both are
recomputed here from the JSONs rather than read from them, so `d` and `gap` are the *recomputed*
values and agree with the stored ones to the digits printed.

## 0. Verdict of record

**DISCRETISATION IMPLICATED.** `PREREG` (via `evidence/h_refine/PREREG.md` §4) requires, on **both**
solvers, (a) a monotone fall of `d` across the rungs and (b) a total fall of at least
`3 * Delta_min = 0.2202` pp, with `Delta_min = 0.0734` pp. Both clauses are met on both solvers:

- FDTD: `0.902013 -> 0.550356 -> 0.372884` pp, monotone, total fall **0.52913** pp = `2.4x` the
  threshold [M].
- EIG: `1.293492 -> 0.934587 -> 0.755037` pp, monotone, total fall **0.53846** pp = `2.4x` the
  threshold [M].

The withheld third rung was the *only* reason the frozen verdict read INCONCLUSIVE (§150, and
`evidence/h_refine/SUMMARY.md` §4, third clause); with rung C measured that clause is discharged and
the verdict moves. **The verdict is about the two discretisation residuals, not about either solver
being correct** — §5 and §9 bound it.

This section is not quotable on its own: the order was not determined, E2 was not achieved, and the
launch attribution for rung C remains open — see §7 and §9.

## 1. The three rungs

| rung | `h` mm | grid | cells | `npml` | steps | strip cells | `beta_fdtd` | `d_fdtd` pp | `beta_eig` | `d_eig` pp | gap % | RSS MB | FDTD s | EIG s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 0.4 | (68, 218, 28) | 415 072 | 12 | 2400 | 2 | 388.2194613 | +0.902013 | 389.7256713 | +1.293492 | 0.387979 | 388.36 | 232.0 | 22.39 |
| B | 0.26667 | (101, 327, 42) | 1 387 134 | 18 | 3600 | 3 | 386.8664667 | +0.550356 | 388.3447897 | +0.934587 | 0.382127 | 1069.74 | 595.5 | 39.72 |
| C | 0.2 | (134, 436, 56) | 3 271 744 | 24 | 4800 | 4 | 386.1836441 | +0.372884 | 387.6539712 | +0.755037 | 0.380733 | 2388.48 | 1335.56 | 4.20 |

All fifteen numbers in the three right-hand columns plus both betas are [M], read from the three JSONs;
`d`, `gap` and the falls are recomputed from them. Rungs A and B are the frozen `h_refine` rows and
were **not** re-run.

## 2. Fall against the pre-registered threshold

| solver | `d(A)` | `d(B)` | `d(C)` | steps | monotone | total fall | threshold `3*Delta_min` | clause |
|---|---|---|---|---|---|---|---|---|
| FDTD | 0.902013 | 0.550356 | 0.372884 | -0.35166, -0.17747 | yes | **0.52913** | 0.2202 | PASS |
| EIG | 1.293492 | 0.934587 | 0.755037 | -0.35890, -0.17955 | yes | **0.53846** | 0.2202 | PASS |

Each individual step also exceeds `Delta_min = 0.0734` pp by at least `2.4x` [M]. The two solvers'
total falls differ by `0.52913 - 0.53846 = 0.00933` pp, i.e. they agree with each other to well inside
`Delta_min` — the same statement that made the *gap* look h-invariant in §4.

**Read this as a statement about `h`, not about truth.** A residual that falls when the mesh is
refined is discretisation. It does not say the remaining `0.373 / 0.755` pp at rung C is zero, and it
does not say the reference is right; see §5.

## 3. The order is not determined, and it is not 2

Apparent order from adjacent pairs, `p = log(d1/d2) / log(h1/h2)`, and from the first-to-last pair:

| solver | A→B | B→C | A→C |
|---|---|---|---|
| FDTD | **1.2185** | **1.3532** | **1.2744** |
| EIG | **0.8016** | **0.7415** | **0.7767** |

A three-point least-squares fit of the `PREREG` §4 model `d(h) = d0 + C * h^p` gives FDTD
`d0 = -0.17589`, `C = 2.6312`, `p = 0.9739` (SSR `5.5e-12`), and EIG `d0 = +0.21562`, `C = 2.6915`,
`p = 0.9987` (SSR `3.2e-12`) [M, computed]. **Three parameters against three points is an
interpolating fit with no degrees of freedom**, so `p ~ 1` is *consistent with* a first-order ladder
and is **not** a determined order; the honest sentence is "the observed fall is consistent with
`p ≈ 1`".

**E2 (second-order convergence) is NOT achieved.** No pairwise order is anywhere near `2.0`; the
largest is `1.3532`. A first-order residual in a scheme that is nominally second order is the
expected signature of a *non-smooth feature* — the 90° strip edge, meshed as a staircase — and that
reading is a hypothesis, not a measurement.

### 3.1 A relayed order does not reproduce

The brief carried the order triple "FDTD `1.22 / 0.59 / 1.28`". Two of the three reproduce and one
does not:

- `1.22` ↔ **A→B `1.2185`** [M].
- `1.28` ↔ **A→C `1.2744`** [M] (to two decimals).
- `0.59` ↔ **not reproducible from any pair of the three graded rungs.** `B→C` is `1.3532`, `A→B` is
  `1.2185`, `A→C` is `1.2744`. No pairing, and no combination of the stored `d` values, yields
  `0.59`. The value is [R] and is **not** recorded here as a result.

The EIG triple "`0.80 / 0.74 / 0.77`" *does* reproduce exactly: `0.8016 / 0.7415 / 0.7767` [M]. So the
relayed EIG half is traceable and the relayed FDTD half is not; the discrepancy is declared rather
than reconciled by choosing the pairing that fits. A reader who needs `0.59` should treat it as
unsourced until an artefact produces it.

## 4. E4 candidate: the gap is `h`-invariant

`gap = 0.387979 -> 0.382127 -> 0.380733 %` over a `2x` refinement in cell size, total movement
**0.00725 pp** [M], which is `10x` *smaller* than `Delta_min = 0.0734` pp and `30x` smaller than the
`0.2202` pp the ladder demands elsewhere.

This is a **candidate E4**, not a verdict: "the EIG-vs-FDTD discrepancy is invariant under mesh
refinement" survives the refinement that kills the discretisation residual, so the surviving
`≈0.38 %` is a property of the *solver bases* (material averaging on the strip, the eigenpath's
cross-section treatment, the tone being fixed rather than solved for), not of `h`. It is stated as a
candidate because no pre-registration in this tree fixes E4's decision rule, and because §5's floor
hypothesis is the mechanism it most obviously supports.

## 5. The floor hypothesis — **HYPOTHESIS**, not a result

Rung C leaves a *non-zero* residual on both solvers: `0.372884` pp FDTD and `0.755037` pp EIG [M].
Two coincidences are worth recording, and neither is a demonstration:

- `0.372884` pp FDTD is numerically close to the "extraction bias `0.377` pp" quoted in the brief [R].
  **Its provenance is not in this tree** — no artefact, pre-registration or ledger line found by search
  carries `0.377` as an extraction bias, so it is recorded as [R] / [UNVERIFIED] and not graded.
- `0.755037` pp EIG is numerically close to the `≈ +0.72` pp transverse-box error reported at the base
  box [L, `evidence/box_sweep/SUMMARY.md` §8.1, L178 for the `+0.72` pp figure and L186 for the
  `rel_gap` triple; `rel_gap 0.8946 -> 0.2229 -> 0.2347`].

**State the objection in the same breath.** The `0.72` pp box number is an error that the box sweep
*removed* by moving the lateral/lid clearance; it is not a residual known to survive at
`lat 8 / lid 1`. And the two coincidences are **magnitude-only**: nothing in this tree connects the
extraction procedure and the transverse box to a common cause, and matching two numbers to two
decimal places is not a mechanism. The hypothesis to test — *a fixed, `h`-independent floor of order
`0.3-0.8` pp sits under both solvers and the ladder is converging to it rather than to zero* — is
recorded because it predicts the next experiment (a third and fourth refinement at a *fixed* box, and
a box sweep at rung C's `h`), not because the data supports it.

## 6. Rung C anatomy

- Cell `0.0002 m`, `n_sub 8`, `npml 24`, `n_clean 192`, `n_air 24`, `n_top 24`, `n_acc 3600` [M].
- `n_dof 49719` (free nodes `37276` electric / `12443` magnetic), `dt 3.813e-13 s`, final residual
  `1.35e-13` against the `1e-8` limit — five orders inside the gate [M].
- **Zero shift-ladder retries.** `sigma_mult_used 0.76`, `sigma 152780.50791727175`, `sigma_retries 0`
  [M, with `meta.sigma_attempts` carrying exactly one entry]: the first multiplier was accepted, so the
  ladder defect disclosed in §151(f) did not fire here and the accepted rung is not a tuned one.
  **This row is also a counter-example to a pattern recorded elsewhere and should be read that way:**
  `evidence/strip_width/` yielded "the accepted multiplier is `0.76 + 0.015*(n_strip - 2)` exactly, with
  `sigma_retries == n_strip - 2`" at `n_strip 2..5` [L, dispatch row
  `strip-width-closeout-2026-10-31`, item (iii)]. Rung C has `n_strip = 4` by the tool's own pinning
  rule (`strip_pinned`: `n_strip = max(round(W/cell), 1)`, `strip_width_mm 0.8`, `meta.strip_cells`
  `None` — the count is not emitted, it is derived) [M/L] and accepted `0.76`, not `0.79`. So the
  multiplier follows the *residual*, not the strip width, exactly as `sigma_ladder_note` says, and the
  closed form holds on the strip sweep's own rows without being a law.
- **The strip is FOUR cells wide** (`0.8 mm / 0.2 mm`) where rung A had two [M]. So rung C refines the
  strip meshing as a side effect of refining `h`, and part of the fall in `d` may be strip meshing
  rather than bulk discretisation. `evidence/strip_width/` puts the strip-meshing lever at
  `0.199938 / 0.198273 / 0.170772` pp over `n_strip 2 -> 5` [L, §152.2], which is the same order as
  the whole fall recorded in §2 — **the two explanations are not separated by this experiment and
  this report does not claim they are.**
- Diagnostics that are not graded: `alpha 0.014559517 dB/mm` against a floor of `0.0139` [M] (the
  dielectric floor is a loss diagnostic, not an accuracy gate); `cavity_shift 25.246 %` [M];
  `b_over_a 0.006903` [M]; `fit_residual_one 0.008680` [M]; `eps_eff_fdtd 3.264270` vs
  `eps_eff_eig 3.289174` [M]; `beta_fit_two 386.366365` [M] against a `beta_two_station -267.886`
  [M] which is **aliased, not nonsense**. The estimator is `-angle(v_last * conj(v_first)) / span`
  (`emfit/studies.py` L2888-2889), so it can only report `beta` modulo `2*pi/span`; here the station
  span is `20.0 - 10.4 = 9.6 mm`, giving `2*pi/span = 654.498 rad/m`, and at `beta = 386.18` the phase
  turns `386.18 * 0.0096 = 3.71 rad`, more than `pi`, so the estimator wrapped exactly once:
  `-267.886 + 654.498 = 386.612 rad/m`, within `0.1 %` of both the one-wave fit `386.1836441` and the
  two-wave fit `386.366365` [M, recomputed]. The same single wrap appears on rung A (`-265.675`)
  and rung B (`-267.169`), so it is a property of the estimator's station span, not a defect of the
  field; the two-wave route contributes nothing here because the fit is aliased, not because the
  field is broken.
- Tone `10198626214.572882 Hz`, a `1.888 %` detune from the common `10.19862621457275 GHz` [M].

## 7. The wall ceiling in force was the amended `1400 s` gate, and the run met it

The gate in force for this run was **not** `900 s`. `PREREG` §5's `wall_fdtd_s > 900` is the `h_refine`
ceiling; the rung-C pre-registration amends it in terms — *"The wall-clock ceiling in `h_refine`
PREREG §5: `wall_fdtd_s > 900` becomes `wall_fdtd_s > 1400`"* [L, `evidence/rung_c_errata/PREREG.md`
§0 L18-19] — and carries that number into §4 (`ceiling_wall_fdtd_s : 900 -> 1400`, set by the rule
"next 100 s at or above `1.20x` the projection": `1163 * 1.20 = 1395.6 -> 1400` [L, §4 L96-99]) and into
§10's amended clause table, where the wall-clock row is marked **AMENDED** [L, §10 L214]. §9 **G2** is
the trip clause at the amended number: `wall_fdtd_s > 1400`, `peak_rss_mb > 4000`, "not measured, gate
tripped", "never extrapolated", no retry [L, §9 G2 L193-196].

The amendment was frozen **before** the run and was not withdrawn afterwards:

- `evidence/rung_c_errata/PREREG.md` states it was frozen `2026-10-31T01:53Z`, "before any
  `h = 0.2 mm` row existed anywhere in this tree" [L, §13 L251], and the file's mtime is `01:55` —
  some three hours before `evidence/rung_c/h020.json`'s `04:57` [M].
- The one erratum on that pre-registration, `evidence/rung_c_errata/ERRATA_001.md` (mtime `02:05`),
  amends §13's file hashes only. Its clause-by-clause §4 records §9 G2 as "**untouched**" and §10's
  amended table as holding "**exactly as frozen**", `wall_fdtd_s > 1400` included [L]; the erratum
  performs, prices and authorises no run.

Against that gate rung C took **`1335.56 s`** [M], which is **inside it**: `1400 / 1335.56 = 1.048`, i.e.
`4.6 %` of headroom, and the memory leg passed at `2388.48 MB` against `4000` (`1.67x` inside) [M]. **So
there is no overrun, no waiver was required, and none is claimed here.**

Three things this section does *not* do, each of them because the errata forbid it:

- **It does not re-price the gate.** The `1400` was set from the `1163 s` *projection*, not from the
  result; this report amends nothing, and the number it reports is the number it measured.
- **It does not retitle the result.** What was withdrawn is the reading, not the measurement: `900`
  was never the ceiling this run was launched under.
- **It does not say "C was affordable".** The naive `h^-4` price carried into the brief was `1882 s`,
  which **would** have tripped the `1400` gate, and `evidence/rung_c_errata/PREREG.md` §4 says the run
  must not be described afterwards as "C was affordable" for exactly that reason [L, L107-112]. The run
  had to be *measured* to learn this; the cheap price was an argument, not evidence.

One thing is left **open** rather than resolved: no row in `docs/design/dispatch_log.md` records the
*launching* of this run. The `rung-c-2026-10-31` row states "No run performed by this pass" and cites
its authorisation for writing `decisions.md` §152/§153 only. The **ceiling** question is discharged by
the amendment; the **dispatch attribution** of the run is not, and it is reported here as open, not as
satisfied.

## 8. What a longer baseline would cost — arm vs baseline

The obvious next lever is the extraction baseline (`TASK G`), so its price is recorded with the same
marks as the ladder. The relevant code facts:

- The arm length is pinned **in metres**, not in cells: `n_line = round(54 * (H_SUB / 4) / cell)`, i.e.
  `54 * 0.4 mm = 21.6 mm` at every rung [L, `tools/host_ladder.py`, argparse L1137-1196]. Measured at
  rung C the arm is `108` cells x `0.2 mm = 21.6 mm` [M], the `npml` having been re-derived from
  `--pml-mm 4.8`. (`134` is the *full* `nx`, `24` PML + `2` reference + `108` line cells; the `2x`-arm
  pricing three paragraphs below grows `nx` to `242 = 2*108 + 24 + 2`, which is the same `108`.) The scale
  this arm is measured against: `lambda_g = 2*pi/386.1836 = 16.270 mm`, so `lambda_g/2 = 8.135 mm` sits
  below the `9.6 mm` station span, which is `0.590 lambda_g = 212.42 deg` of phase.
- Station spacing is `(20.0 - 10.4) / 8 = 1.2 mm`, i.e. `6` cells at rung C and `3` at rung A [L].
- There is **no CLI knob** for arm length, `x_first`, `x_last` or `n_stations` [L, same range].

Pricing a `2x` arm at rung C keeps the cell size and grows `nx` to `242`, i.e. `5.91 M` cells
(`1.806x`), FDTD `≈ 2412 s` (`40.2 min`) and `≈ 4.3 GB` [R, arithmetic on the [M] cell count and the
[M] `1335.56 s` / `2388.48 MB`]: the full-line reading fails **both** legs — `2412 s > 1400 s` on the
wall gate and `≈ 4.3 GB > 4000 MB` on the memory ceiling — while the station-span reading (`1814 s`,
`3212 MB` [R, same arithmetic]) fails the wall leg **only**, `1814 s > 1400 s`, since `3212 MB < 4000 MB`
**passes** the memory ceiling. The same box at `h = 0.4` does **not** need extrapolating: it is rung A's own box, and it cost
**`232.0 s`** measured [M, `evidence/h_refine/h040.json`]. The cell-step count falls from
`3 271 744 * 4800 = 1.57e10` to `415 072 * 2400 = 1.00e9`, a `15.77x` reduction in cell-steps for a
`5.76x` reduction in measured wall clock (the finer rung is more efficient per cell-step, not less).

**Recommendation, stated as a recommendation:** keep `h = 0.2` (four cells across the strip, which is
what makes §2's fall interpretable) and spend the budget on the **station baseline** — the `9.6 mm`
station span and the `8` stations (§11) — rather than on the arm, because a shorter span is what de-aliases
the two-station estimate and a longer arm does not. The
`beta_two_station -267.886` [M] in §6 is aliased by a full `2*pi` wrap, and a longer arm does not fix
that: the alias is set by the station span, so the repair is to **shorten** the span (or add stations),
not to lengthen the arm.

## 9. What this does not establish

1. **No convergence order.** §3: three points, three parameters, and no pairing anywhere near `2.0`.
2. **No converged value and no converged gap.** `d` is still falling at rung C on both solvers, so the
   `0.373 / 0.755` pp are an upper bound on any floor, not the floor.
3. **Not a clearance of either solver.** A falling residual says "discretisation", not "correct"; the
   ensemble gap of `≈0.38 %` (§4) is still the same size as the station-fit bias recorded elsewhere,
   so the gap is still not resolvable by this instrument.
4. **Not a separation of strip meshing from bulk discretisation.** §6: rung C refines both at once.
5. **Not the box.** `lat 8 / lid 1` was frozen by design on every rung; §148(h) is untouched by this
   report.
6. **The ultimate blocker is the reference, not the ladder.** `HJ+KJ` accuracy is quoted at `~0.5-1 %`
   [L, `evidence/h_refine/SUMMARY.md` §7], and every `d` in this table is a difference against that
   reference. Even a fully converged ladder lands on a number whose *truth* is only known to
   `0.5-1 %`, which is `5x` to `10x` the whole fall measured in §2. The ladder is now worth running
   once more for the order; it is not worth running to find the truth.

## 10. Provenance

All [M] numbers in this file come from three JSON artefacts in this tree: `evidence/h_refine/h040.json`
(rung A), `evidence/h_refine/h0267.json` (rung B), `evidence/rung_c/h020.json` (rung C). `d`, `gap`,
the falls, the pairwise orders and the three-point fits were **recomputed** from the `beta` values in
those files for this report; where a stored field exists (`beta_hj_kj_graded`, `sigma_retries`,
`residual`) it was cross-checked against the recomputation and agrees. Nothing in this report is
extrapolated, and no gate is re-priced.

The instrument is cited by name because `evidence/rung_c_errata/ERRATA_001.md` §3 requires any rung-C
row published after it to do so. Re-measured for this report: `tools/host_ladder.py` is
`0d7191973fe7babf53463205a1da968befcca205e725027ed83dc0267b190c9b` at **`1395` lines** — neither §13's
`1cd1a3ee…` (`1106`) nor the erratum's replacement pin `519365eb…` (`1261`) — while
`tools/d585_modal.py` (`8ba8e2a8…d53a6`, `676` lines) and `emfit/studies.py` (`578650bc…e802ac`, `5166`
lines) are **byte-identical** to their pins [M]. So §9 **G3** is **not** satisfied by measurement, and
this report does not claim it is: gradeability rests on `ERRATA_001.md` §3's argument (G3's letter
"superseded, not satisfied", the protected object — the byte-identical reference module and the
untouched numerical path — preserved prospectively), which is the erratum this row cites.

## 11. Corrections carried after the run

Appended after the report was written. **Nothing in §0-§10 is re-graded, no number is re-derived, no
gate is re-priced and no verdict moves** — the items below are the corrections this report owes,
not a second reading of the ladder. Where an item touches a printed number, the number stays where it
was printed and this section names it by line.

(a) **L237's "the `8` stations" is wrong: there are nine stations.** `emfit/studies.py` L1176-1180
sets `MS_X_FIRST = 10.4e-3`, `MS_X_LAST = 20.0e-3` and `MS_N_STATIONS = 9` [L], and the rung-C row
itself carries `n_stations: 9` [M, `evidence/rung_c/h020.json`]. The arithmetic is not a matter of
taste: a `9.6 mm` span at `1.2 mm` spacing is **eight intervals**, and eight intervals is **nine**
stations. The count changes nothing the recommendation rests on — the wrap modulus `654.498 rad/m` is
a function of the *span*, not of the station count, so the `2*pi` alias argued in §6/§7 and the advice
to spend the budget on the station baseline stand exactly as written. Only the noun is wrong; the
sentence at L237 now carries a `(§11)` pointer and is otherwise untouched.

(b) **`0.59` (order) and the relayed `0.377` pp (floor) remain [R] / [UNVERIFIED].** A further search
of this tree found no provenance for either: `0.59` reproduces from **no** pairing of the three banked
rungs (§3 still holds — pairwise `1.2185 / 1.3532 / 1.2744` FDTD, `0.8016 / 0.7415 / 0.7767` EIG, LSQ
`p = 0.9739 / 0.9987`), and `0.377` has no artefact, log, JSON field or prose source behind it. Both
are carried as relayed numbers and **not graded**; this section does not promote either to measured.

(c) **`sigma_retries = 0` on rung C stays a counter-example to the closed form in `decisions.md`
§152.11.** That rule predicts `sigma_retries == n_strip - 2`, i.e. `2` for rung C's four-cell strip;
the artefact records `0` [M]. The rule is a *strip-width-sweep* fact measured at `h = 0.4`, and rung C
was run at a different `h`, so it lies outside the rule's domain. The counter-example is recorded as a
counter-example and is **not** reconciled away by declaring the rule wrong in the sweep it came from.

(d) **Pointer to the erratum, and to the guard that fails for the second time.** Every item above is
argued at length in `evidence/rung_c_errata/ERRATA_004.md` §A-§F — §A the authorisation/attribution
split of §150(h)(iv), §B the third link of the `1106 → 1261 → 1395` hash chain, §C the §151(f)
carry-in, §D this dispatch's two rows in `docs/design/dispatch_log.md`, §E these corrections, §F the
six guards — together with the standing correction that this report's own §9 **G3 fails its letter a
second time**: it was already failed in `ERRATA_001` §9 (argued there as "superseded, not satisfied"),
and `ERRATA_004` repeats that argument rather than repairing the letter. The alternative reading —
G3 admits no amendment, therefore rung C is not gradeable at all — is **not** defeated by anything in
this section or in the erratum; it stays on the record. `ERRATA_004` adds no measurement, and this
section adds none either.

(e) **§8 L239's "a longer arm does not fix that" is too broad, and this clause narrows it.** The sentence is
true of the `beta_two_station -267.886` wrap: that alias is set by the **station span** against
`lambda_g/2 = 8.135 mm` (the `2*pi` wrap modulus `654.498 rad/m` over `9.6 mm`), so what fixes it is a
**shorter** span, or more stations — not a longer arm. It is not true of the extraction bias from finite probe
separation, `2|Gamma|/d_probe`, which a **longer** arm *does* reduce: there the bias falls with probe
separation, so lengthening the arm is the move. §8 is committed and is **not edited**; it keeps its words and
this clause carries the narrower claim beside it. The recommendation §8 makes is unchanged, because the budget
it spends is the *station baseline*, and a longer arm was never one of its two candidates.
