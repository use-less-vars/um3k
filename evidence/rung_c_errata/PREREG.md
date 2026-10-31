# Pre-registration (append-only erratum): the rung-C sizing gate, resource budget only

Frozen 2026-10-31, before `h = 0.2 mm` has ever been run and before any row exists in this directory.
Append-only. This file **amends one number in a frozen document** and nothing else; §10 shows the
original and the amended clause side by side, and §9 makes the unamended text binding if any guard
fires.

Related records, all frozen earlier and all unedited by this dispatch:

- `evidence/h_refine/PREREG.md` -- the gate being amended (§5) and the verdict rule being *not*
  amended (§4).
- `evidence/h_refine/SUMMARY.md` -- §4 the measured scaling and the priced refusal of rung C.
- `evidence/box_sweep/SUMMARY.md`, `docs/design/box_sweep_preregistration.md` -- where the 900 s
  number and the resolution floor come from.

## 0. Scope: one quantity, and the line drawn around it

**In scope.** The wall-clock ceiling in `h_refine` PREREG §5: `wall_fdtd_s > 900` becomes
`wall_fdtd_s > 1400`.

**Out of scope, explicitly and permanently.** The `peak_rss_mb > 4000` clause (unchanged). The
verdict rule in `h_refine` PREREG §4 (unchanged, including `Delta_min = 0.0734 pp` and the `3*Delta_min
= 0.22 pp` threshold). The graded reference and its `1e-6` reproduction tolerance. The confound
declarations. The "if it trips, it is not run and never extrapolated" clause (unchanged, and re-pinned
in §9 G2). Anything about `h = 0.16 mm`, the box, the strip, `T2_agree`, the C++ port.

The distinction this file rests on: **a wall-clock ceiling is a budget, not a threshold.** It cannot be
result-biased, because nothing in the graded quantity `beta_fdtd` depends on how long the solve took --
`nsteps` is fixed independently (and re-derived by the driver, §7), so a rung that costs 1163 s and a
rung that costs 900 s produce the same number. The physics thresholds in §4 are the ones that decide a
verdict, and they are not touched.

## 1. What the gate was, and what it was calibrated on

`h_refine` PREREG §5, frozen 2026-10-31, verbatim:

> Hard stop, per rung, on either: `peak_rss_mb > 4000` or `wall_fdtd_s > 900`. The gate is applied to
> the **measured** value of the previous rung's scaling, re-priced before each launch, not to a guess.
> If rung C trips the gate it is **not run**, the table is published with two rungs, and the verdict
> for h = 0.2 is "not measured, gate tripped" - never extrapolated.

Provenance of the two numbers in it [L, inferred but consistent across both frozen files]:

- `900 s` and `4000 MB` are the `box_sweep`-era runaway guards. `box_sweep`'s six arms cost
  `7.98 / 13.44 / 23.17 / 55.66 / 11.80 / 21.92 s` at `51 832` -- `280 984` cells and `150.9` --
  `295.0` MB [M, `evidence/box_sweep/SUMMARY.md`]. `900 s` is `16x` the largest arm of that sweep,
  `4000 MB` is `13.6x` its largest RSS. They were sized to catch a runaway in a sweep of
  sub-60-second runs.
- `h_refine` then designed (§2 of its PREREG) a three-rung ladder in which the third rung costs
  `5.0x` the first in FDTD wall (`1163 s` vs `232.0 s` [M]). **`900 s` sits between rung B's measured
  `595.5 s` and rung C's projected `1163 s`, i.e. inside the range its own design table spans.** The
  gate and the design were inconsistent from the freeze: the ladder was designed to reach a rung that
  the inherited guard could not authorise.

That inconsistency, not the quality of any model, is what this erratum repairs.

## 2. The measured record the gate acted on

`evidence/h_refine/SUMMARY.md` §4 [M]:

| quantity | measured exponent (from A -> B) | rung C priced from B (h ratio 1.3333) | original gate |
|---|---|---|---|
| cells | `p = 2.976` (a priori 3) | `3.27 M` | -- |
| FDTD wall | `p = 2.325` | **`1163 s`** | `> 900 s -> TRIP` |
| peak RSS | `p = 2.499` | `2195 MB` | `< 4000 MB -> pass` |

and the naive `h^-4` pricing (`cells x nsteps`, i.e. `cells ~ h^-3` with the driver's `nsteps ~ h^-1`)
gives **`1882 s`** from B. **Both models trip the original gate; neither trips the memory gate.** The
nonzero `beta` of this erratum is therefore a budget decision about a run that every model says costs
between 19 and 31 minutes, against a ceiling of 15.

## 3. Provenance correction: `163.65 s` is not a rung-C price

A claim in circulation for this dispatch is that rung C was "priced at 163.65 s from a linear-in-cells
model". The artefacts do not support the second half of that sentence, and the record is corrected
here so that the erratum is not built on it:

- `163.65 s` is the **six-config total** of `box_sweep`, priced on the recorded `1.15e7 cell-steps/s`
  rate: `10.82 + 17.65 + 31.31 + 58.64 + 16.72 + 28.52 s` [M,
  `evidence/box_sweep/SUMMARY.md:39`; `docs/design/box_sweep_preregistration.md:40`; `decisions.md`
  ~9362]. It is a cost forecast for six 52--281 k-cell arms, compared against their measured
  `7.98 / ... / 21.92 s`. It has never described rung C.
- The linear-in-cells model did produce a rung-C number, but it was a **cell count**, not a time:
  "`box_sweep`-era estimates costed **6.9 M cells** for this rung from a linear-in-cells model"
  [M, `evidence/h_refine/SUMMARY.md:73-75`].
- At that era's rate and the driver's rung-C `nsteps = 4800` (§7), `6.9 M` cells is
  `6.9e6 * 4800 / 1.15e7 = 2880 s`. **So the superseded model would also have refused rung C** -- it
  was wrong by `2.11x` in cells and `1.37x` in rate (rung B actually achieved
  `1.387e6 * 3600 / 595.5 = 8.39e6 cell-steps/s` [M]), and it was wrong in the *same direction* the
  gate was already refusing. This is the reason the erratum cannot be argued as "the gate rested on a
  bad model": the gate rested on the measured scaling (§2), and the bad model agrees with it about the
  verdict. The erratum is a **budget** amendment (§1), full stop.

## 4. The amendment, and the rule that produced the number

    ceiling_wall_fdtd_s : 900  ->  1400
    rule                : ceiling = the next 100 s at or above 1.20 x the projected wall_fdtd_s

`1163 * 1.20 = 1395.6 -> 1400 s` [M from §2]. `1400 / 1163 = 1.204`, i.e. 20 % of headroom on the
central projection, which is roughly the spread between the two defensible models *below* the h^-4
outlier (`1163` measured-exponent, `1882` naive). Nothing else in §5 changes.

Why 20 % and not more: a ceiling far above the projection is not a gate. Why not 0: a ceiling equal to
the projection converts every small scheduling penalty into a refused run, and refuses by *accident*
what the design wanted measured.

**The honest weakness, stated before the run.** Under the naive `h^-4` pricing the amended gate still
trips (`1882 > 1400`) [M]. The amendment therefore does **not** make rung C affordable under every
defensible model; it authorises **one** run under the measured-exponent price, which is the better
model here because it is fitted to this instrument's own two measured rungs. If the run's measured
`wall_fdtd_s` exceeds `1400`, it is killed and reported as a trip (§9 G2) -- the same clause as
before, with a different number. This must not be described afterwards as "C was affordable".

## 5. Why the argument is not "wall clock does not matter"

It does matter -- it is machine time, and `900 s` was a real decision. The argument is narrower, and
has three parts:

1. **The ceiling is not a threshold.** `beta_fdtd` is extracted from a fixed `nsteps` record by the
   two-station fit; the wall time is a consequence of the cell count and the solver's throughput. No
   clause in §4 of `h_refine` reads `wall_fdtd_s`. Amending a budget cannot move a physics verdict.
2. **The exceeded quantity was a cost projection, and the projection's *purpose* was to protect the
   operator, not the result.** Terminating on a budget *after* seeing a result would be the biasing
   move; setting the budget *before* the run cannot be, and this file is frozen before any `h = 0.2`
   row exists.
3. **The gate could not have permitted the ladder it was attached to** (§1). A guard that forbids the
   experiment the document designs is a drafting error about a budget, and the smallest repair is to
   move the budget, not to shrink the experiment.

What this erratum does **not** claim: that 20 minutes of machine time is free; that the projection is
certain (it is a two-point extrapolation with `p = 2.325 +/-`); that a third rung will be informative
(it may be non-monotone and produce INCONCLUSIVE again -- §6).

## 6. What is graded: nothing new, and the verdict that is superseded

No new thresholds, no new reference, no new tolerance. If rung C runs, `h_refine` PREREG §4 is applied
**unchanged** to the three-rung sequence:

- **DISCRETISATION IMPLICATED** if `d` falls monotonically across the three rungs and the total fall is
  `>= 0.22 pp`;
- **DISCRETISATION NOT THE EXPLANATION** if the total fall is `< 0.22 pp`;
- **INCONCLUSIVE** otherwise (non-monotone, or a rung missing/tripped).

Consequences, declared now:

- The published two-rung verdict **INCONCLUSIVE** stands as the verdict of that record and is not
  re-read. A three-rung run **supersedes** it by re-applying the same rule to a longer sequence, and
  the supersession is recorded as such.
- If rung C is refused again under the amended gate, the record stays exactly as it is: two rungs, the
  third "not measured, gate tripped", never extrapolated (§9 G2). The amendment does not create an
  entitlement to a three-rung answer.
- **A non-monotone third rung is a real possibility** and it costs a full run to find out. The
  post-hoc two-rung reading (`h_refine` SUMMARY §3) is `+0.90201 -> +0.55036 pp`, which extrapolates
  to a small positive residual rather than a crossing; nothing here predicts which side of zero a
  third rung lands on, and a crossing would be INCONCLUSIVE under §4, not a discovery.

## 7. Run configuration required by the erratum (all of it load-bearing)

    python3 tools/host_ladder.py --h 0.2 --clearance 3.0 \
        --box-lateral-mult 8.0 --box-lid-mult 1.0 \
        --pml-mm 4.8 --mem-ceiling-mb 4000 \
        --strip-width-mm 0.8 --json evidence/rung_c_errata/h020.json

- **`--mem-ceiling-mb 4000`, not the default.** The tool's default is `2000` [M, source 896] and the
  projection is `2195 MB` [M] -- a run with defaults would abort **on memory at 91 % of peak**, and the
  record would then read "rung C refused" for a reason that has nothing to do with the gate. The value
  `1400` used for smoke runs is worse still and must never be used here.
- **`--mem-ceiling-mb` is not `peak_rss_mb`.** The ceiling is a self-imposed abort; the `4000 MB`
  clause in the gate is what is graded. Both are stated because they are easy to confuse.
- **`--npml`/`--nsteps` are not pinned.** The absorber is pinned in millimetres (`--pml-mm 4.8`) and
  `npml` re-derives as `round(4.8/0.2) = 24`; `nsteps` re-derives as
  `round(MS_NSTEPS * n_sub / MS_N_SUB) = round(2400 * 8 / 4) = 4800` [M, source 316]. Pinning either
  by hand would silently change the run that was priced -- `nsteps` is half of the cost model.
- **One run at a time, in a `6144 MB`-class container**, cgroup verified before launch (the `h_refine`
  rungs recorded `6144 MB` [M]; the container this file was written in reports `512 MB` [M,
  `/sys/fs/cgroup/memory.max`], which cannot host a `2195 MB` peak at all).
- Expected cost: `~1163 s` FDTD + `~90 s` modal [L, modal extrapolated from A `22.4 s` / B `39.7 s` at
  `n_dof 12 443 -> 27 977` [M]) ~= `21 min`.

## 8. The strip is pinned in metres and lands exactly, again

At `h = 0.2 mm`, `cell = 1.6/8 = 0.200 mm` and `--strip-width-mm 0.8` gives `n_strip = 4`, meshed width
`0.800 mm` -- identical to the two measured rungs [M, `resolve_strip`; `h_refine` PREREG §2 table].
So the third rung does not move the line, and a fall in `d` cannot be a strip-width effect. (If the
strip-width sweep files at `evidence/strip_width/` is run first, its result is *not* an input here:
`h` and `W` are held and the two dispatches share no arm.)

## 9. Invalidating guards (frozen)

- **G1 physics untouched** -- the §4 verdict rule, `Delta_min`, the `0.22 pp` threshold, the graded
  reference and its `1e-6` tolerance are byte-identical to `h_refine` PREREG before and after this
  erratum. Any edit to them voids this file.
- **G2 trip clause, re-pinned** -- if rung C's own measured `wall_fdtd_s > 1400` or
  `peak_rss_mb > 4000`, the run is stopped/withheld, the table is published with two rungs, the third
  is "not measured, gate tripped", and it is **never extrapolated**. There is no retry with a larger
  ceiling inside this dispatch.
- **G3 same instrument** -- `tools/host_ladder.py` sha256 must still be
  `1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` and `tools/d585_modal.py`
  `8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6` [M, identical to the `box_sweep`
  §12 freeze]. If either moved, the third rung is not on the same instrument as the first two and the
  three-rung sequence is not gradeable.
- **G4 reference reproduction** -- at rung C's realised tone, `hammerstad_beta` must reproduce the
  frozen pin to `1e-6` relative; the `h = 0.4` pin is a tone artefact, so the check is run against the
  pinned function, not against a memorised number.
- **G5 completeness** -- exit `0`, `meta.status == 'ok'`, `meta.abort_reason is None`, and the cell
  count within `5 %` of the `3.27 M` projection. A run that aborts inside the ceiling is ungraded.
- **G6 one-shot** -- exactly one `h = 0.2` run is authorised. Re-running until the wall fits, or
  re-running after a trip, is outside this file's grant.

## 10. The amended clause, side by side (frozen)

| field | `h_refine` PREREG §5 (frozen 2026-10-31) | as amended by this erratum | status |
|---|---|---|---|
| wall clock | `wall_fdtd_s > 900` | `wall_fdtd_s > 1400` | **AMENDED** |
| memory | `peak_rss_mb > 4000` | `peak_rss_mb > 4000` | unchanged |
| pricing basis | "the measured value of the previous rung's scaling, re-priced before each launch" | same | unchanged |
| on trip | "not run ... published with two rungs ... never extrapolated" | same | unchanged |
| verdict rule | `h_refine` §4, `Delta_min = 0.0734 pp`, `3*Delta_min = 0.22 pp` | same | unchanged |

## 11. Standing adversarial review before the freeze (rule 1 of `session_close_gen5.md` §3)

Run against §0-§10, before the freeze.

| # | attack | disposition |
|---|---|---|
| A1 | "This is moving the goalposts after seeing the answer." | **Disclosed, and narrowed.** The run it authorises has never produced a number, so there is no outcome to select for; the exceeded quantity was a cost projection with no route into the graded quantity (§5); and the amended ceiling is `1.204x` the projection, not open-ended. It is still a post-hoc change to a frozen document, and the reader is asked to judge that on §1 (the gate never permitted the design) rather than on good faith. |
| A2 | "You claim the model was wrong; the model agrees with the gate." | **Changed the argument.** §3: `163.65 s` is not a rung-C price at all, and the superseded 6.9 M-cell model prices C at `2880 s`, which trips `900 s` too. The erratum is therefore argued as a budget amendment (§1), not as a model correction. |
| A3 | "`1882 s` still trips `1400 s`, so the gate is still arbitrary." | **Accepted and stated** (§4, §6). The amendment does not make C affordable under every defensible model. It authorises one run under the measured-exponent price; a trip at `> 1400 s` is reported as a trip and never extrapolated (G2). |
| A4 | "If you can move one number you can move any of them." | **Changed.** §0 lists what is out of scope permanently, §9 G1 makes any edit to the physics clauses void this file, and §4 fixes the rule that produced `1400` (`next 100 s >= 1.20x projection`) so that the *next* rung is re-priced by a rule and frozen in its own pre-reg, not by this file's precedent. |
| A5 | "The default `--mem-ceiling-mb 2000` would have aborted rung C on memory and you would have reported a trip." | **Changed.** §7 makes `--mem-ceiling-mb 4000` explicit and explains that a defaults run aborts at `91 %` of the projected peak, i.e. before the number exists. `1400`, the smoke-run value, is named as unusable. |
| A6 | "Half the cost is `nsteps` and you never mentioned it." | **Changed.** §7: `nsteps` re-derives to `4800` at `h = 0.2` and must not be pinned; the `1163 / 1882 s` projections both already include it (`cells x nsteps`). |
| A7 | "The verdict will be quietly re-read as if it had always been three rungs." | **Changed.** §6 separates the two records: the two-rung `INCONCLUSIVE` stands as published, a three-rung run supersedes it by re-applying §4, and a trip leaves the record exactly as it is. |
| A8 | "`2195 MB` and `3.27 M` cells are a two-point extrapolation; you are buying a run on a fitted line." | **Disclosed.** `p = 2.325` is fitted between two rungs, `1.5x` apart in `h` but only `1.333x` for the step being extrapolated, and FDTD wall scales *softer* than cells (§2), so the fit can be wrong in both directions. G5's `5 %` cell-count check and G2's stop clause are the only protections, and neither makes the projection an estimate of anything but this machine. |
| A9 | "One run, `21 min`, and the answer may be `INCONCLUSIVE` again -- what was bought?" | **Accepted.** A third rung is bought, not a verdict. §6 states that non-monotonicity is a live possibility and would be INCONCLUSIVE. The purchase is that the h term stops being a two-point line with an unknown order. |
| A10 | "Self-review again." | **Disclosed.** Same seat as the document it amends. Mitigation: every clause above is a rule over numbers a reader can recompute from `evidence/h_refine/` and this file; the amendment is one line (§10) and a reader who rejects §5's argument can restore `900` without reading the rest. |

## 12. What this erratum does NOT establish

- It does not validate the linear-in-cells model, the `h^-4` model, or the measured exponents -- it
  prices a run and says which pricing it believed.
- It does not re-read, soften or overturn the published two-rung verdict, and it does not make a third
  rung likely to change it.
- It does not authorise `h = 0.16 mm`, a fourth rung, a retry after a trip, or any further budget
  amendment (each needs its own dated erratum).
- It says nothing about the box (that is `evidence/strip_width/` Q2), the strip width (same file, Q1),
  the reference's accuracy, or absolute agreement.
- It does not claim 20 minutes of machine time is cheap.

## 13. Freeze declaration

Frozen 2026-10-31T01:53Z, before any `h = 0.2 mm` row existed anywhere in this tree. Provenance of the
code the run would use [M, `sha256sum`]: `tools/host_ladder.py`
`1cd1a3eee4e76cd8e3672decafc35145eaf761c3cde1a900feca87f8087abeb9` (1106 lines), `tools/d585_modal.py`
`8ba8e2a86294418b7e91fa324a00dd246eaaf0e9e41bd2051156e0858e4d53a6`, `emfit/studies.py`
`578650bc59b1dbaa09832ec3dde2c0058fa69e0dcee56c2e8a4cc7ff37e802ac`. Python 3.12.15, numpy 2.5.4,
scipy 1.18.1 [M].

No `decisions.md` write is claimed by this dispatch; decisions text goes to
`docs/design/<dispatch>_decisions_block.md` for Agent A to merge (standing rule 2).
