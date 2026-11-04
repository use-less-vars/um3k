# Session open — Generation 8

**Written 2026-11-04, at HEAD `52986ff`. Reader: the incoming engineer; read this FIRST, then `session_close_gen8` if it exists, then `docs/design/defect_register.md`, then the active scope.**

## How this document was written

Drafted by the outgoing Generation 8 at HEAD `52986ff`. Every claim carries its warrant: **[M]** measured while writing this file, **[L]** read from the tree or the artefact named beside it, **[R]** relayed and unchecked. **The artefact always wins over this text:** if a number here disagrees with `evidence/termination/*.json`, the register or the dispatch log, the file on disk is right — record the disagreement in the next row rather than editing the artefact to match.

One boundary, so it is not read as an omission: §2 details the **five commits that closed the session**; the earlier half of the same 2026-11-04 arc (`48e9d5d` onward) is recorded row by row at `docs/design/dispatch_log.md`:13-19 [L]. `git log --oneline` from `ce16cdf` is the authoritative list, not this file.

## 1. Where we are

The absorbing-termination build is where Generation 7 left it: the phase mechanism works, the magnitude chain does not, and the graded quantity is `s11` at the load plane. **AC-3 is false on every arm** — `s11_at_plane.magnitude` 0.0490 / 0.4266 / 0.3132 against a 1e-3 bar — and unmeetable, not merely failing, while the strip runs PEC into the far wall [L, `defect_register.md`, DR-16 "Related"].

Generation 8 produced no new gate verdict; it produced an `s11` trustworthy enough to grade later. Post-fix artefacts de-embed `s11.phase_deg` with the same beta as the magnitude beside it, from one line at `emfit/studies.py:3387` (`fit_one.beta` → `fit_two.beta`) [L] — main-record-only, see the `_bin_metrics` exception in §3. The station phasors behind the one-wave fit are banked (`build_A_50ohm_p51_phasors.json:/s11/station_phasors`, n 9, `fit_selected` 8 [L]). And the +40.367460 % one-wave modulus jump the fix caused (`magnitude_one_wave_station_fit` 0.23216690987276836 → 0.32588679434738205, `s11.magnitude` bit-identical at 0.32556486641109117) is **derived** from those phasors at both betas, not argued [L, `s11_refit_from_phasors_2026-11-04b.md`; `dispatch_log.md`:19]. Six reserved defects are now registered (DR-24..DR-29); the older DR-19 stays OPEN with an explicit trail.

## The residual that blocks AC-3

**AC-3's bar is a matching bar, not an anchor comparison.** `absorbing_termination_scope.md`:235-238: "On the matched load, `|S11| <= 1.0e-3` and `| |S21| - 1 | <= 1.0e-3`" [L]. The s11 key it grades is the **one-wave** station fit, `s11.magnitude_one_wave_station_fit`, not the two-wave `s11.magnitude` published beside it [`defect_register.md`:406-422, DR-24] [L]. The three numbers that recur beside this gate in the analysis docs (0.34465, 0.307, 0.724) are not AC-3's bar. They are **references**, and they are three different objects.

**Reference 1 — series-R, s11 only: 0.34465.** The closed-form reflection of a series 50 ohm resistor in a 47.54 ohm line, `R/(2*Z0 + R) = 50/(50 + 2*47.54)` [`defect_register.md`:342]; the same quantity appears as `r = 0.344653501` at `Z0 = 47.53662`, where the docstring says plainly "**Z0 = 47.53662 ohm is stated, not fitted**" [`closed_form_with_two_wave_beta_2026-11-02.md`:14] [L]. Every artefact's `s11.validation_reason` carries it, e.g. "it reads 0.3256 against the series-R anchor 0.34465, i.e. 5.54 percent low" [`evidence/termination/build_A_50ohm_p51_phasors.json`:385] [L]. It is a model prediction for a pure resistance, not a measurement and not a gate bar.

**Reference 2 — complex-load TE, s11: 0.307.** `S11 = (Z - Z0)/(Z + Z0)` evaluated on the **measured** plane impedance `82.11518049761072 - j20.78227124428749` ohm at `Z0 = 47.54` real, giving `|S11| = 0.307214` [`complex_load_analysis_2026-11-04.md`:151; inputs at `:16-18`] [L]. That doc labels the row "TE reference, not in any artefact" (`:18`).

**Reference 3 — the same complex-load model, s21: 0.724.** `S21 = 2*Z0/(Z + Z0)` on the same `Z` and `Z0`: `|S21| = 0.724087`, carried everywhere as 0.724 [`complex_load_analysis_2026-11-04.md`:18, `:151`; `s11_refit_from_phasors_2026-11-04b.md`:59] [L]. References 2 and 3 are one model read at two ports. Reference 1 is a different model and has no s21 partner.

**Every measured value with its own signed deviation** (4 s.f.; measured values bit-exact from the artefacts):

| measured quantity | value | reference | signed deviation |
|---|---|---|---|
| `s11.magnitude`, two-wave, both records | 0.32556486641109117 | 0.34465 (series-R) | **-5.537 %** |
| `magnitude_one_wave_station_fit`, POST | 0.32588679434738205 | 0.34465 (series-R) | **-5.444 %** |
| `magnitude_one_wave_station_fit`, PRE | 0.23216690987276836 | 0.34465 (series-R) | **-32.64 %** |
| `s11.magnitude`, two-wave | 0.32556486641109117 | 0.307 (complex-load) | **+6.047 %** |
| `magnitude_one_wave_station_fit`, POST | 0.32588679434738205 | 0.307 (complex-load) | **+6.152 %** |
| `s21.magnitude`, POST | 0.7644184907560716 | 0.724 (complex-load) | **+5.583 %** |
| `s21.magnitude`, PRE | 0.7628473102840976 | 0.724 (complex-load) | **+5.366 %** |

PRE = `build_A_50ohm_v3_flux_off_pin.json`:286-288 and `:301`; POST = `build_A_50ohm_p51_phasors.json`:286-288 and `:397` [L]. The two-wave s11 value is bit-identical across the two records; the graded one-wave value is not (+40.367460 %).

**The references are not interchangeable, and one cross-port comparison in circulation is mismatched.** The two s11 references differ from each other by **12.26 %** (0.34465 against 0.307) — more than any deviation in the table — so "s11 is 5 % off" is not a statement until the reference is named. Comparing `s11` to 0.307 and `s21` to 0.724 is like-for-like: one model, one `Z0`, one port each. Comparing `s11` to 0.34465 is not like-for-like and cannot be paired with `s21`/0.724 at all, because reference 1 has no s21 partner: it is a series-R closed form for the reflection only.

**Settled: the beta route is dead as an explanation of this residual.** The prediction that `|gamma_v|` does not move with beta is refuted on the record — it **moves +40.37 %** — and what is beta-free is the two-wave fitted modulus `s11.magnitude`, a different quantity [`s11_refit_from_phasors_2026-11-04b.md`:58; `dispatch_log.md`:19] [L]. The beta fix moves `s21.magnitude` by 0.2059 % (0.7628473102840976 -> 0.7644184907560716), far short of the ~5.5 % excess, so beta is not the source of the residual.

**Not settled: one common scale error, or two distinct biases.** The mismatched pair cannot decide it. The like-for-like pair agrees to **0.46 %** (`|s11|/0.307` = 1.06047 against `|s21|/0.724` = 1.05583 [`s11_refit_from_phasors_2026-11-04b.md`:59]), which is the shape a common scale factor would leave — but only at `Z0 = 47.54`, the TE value that "is stored in no artefact", and the same pair splits to `f_s11 = 0.959571` against `f_s21 = 1.104000` (13.08 %) at the run's own station-fit `Z0` [`complex_load_analysis_2026-11-04.md` section 5, items 1 and 3] [L]. An agreement that exists only at a `Z0` no artefact holds is a property of the reference pair, not of the measurement. Meanwhile the deviation AC-3's own key carries, -5.444 %, is negative where both like-for-like deviations are positive and similar in size. And the 12.26 % gap between the two s11 references is itself unexplained: two references that disagree by 12 % cannot adjudicate a 5.5 % residual.

**Which arm AC-3 grades, and why it matters.** AC-3 grades the one-wave station fit [`defect_register.md`:406-422], i.e. the estimator that moved from -32.64 % to -5.444 % of the series-R anchor under a one-line beta repoint, while the two-wave modulus did not move in its last digit. The graded arm is the beta-sensitive one, and DR-24 exists because the two were published under one key. A verdict written before the reference question above is answered is a verdict on a reference, not on the build.

**How much of this is independently recomputed.** The banked `station_phasors` reproduce both records' graded scalars to delta 0.0 on POST [`s11_refit_from_phasors_2026-11-04b.md` section 2, C2] [L]; the PRE record carries **no** `station_phasors` block [`s11_refit_from_phasors_2026-11-04b.md`:56], so its figures are a consistency check against the stored artefact, not an independent recomputation. Every deviation above is arithmetic on stored floats; none of it is a new run.

## 2. What landed this session

1. **`bf4c0b6` — writer: bank station phasors (x, v, i) in build_A artefacts.** New `s11.station_phasors` block (station x, v and i phasors, `beta_used`, `beta_one`, `beta_two`, `deembed_distance_m`, `status`), float64, round-trip tested bit-for-bit, explicit null/`"unavailable"` path. Additive, numerics untouched; cost flagged: n = 9 → 2131 B = +14.4 % of a 14,865 B artefact, over the 5 % budget [L, `dispatch_log.md`:18].
2. **`ba4e902` — writer: `js`, `fit_x`, `fit_selected` added to that block.** Closes the "which stations were in the fit" inference class: `station_fit_n` counts only the fit's own selection (`emfit/studies.py:2326`) [L, `dispatch_log.md`:18].
3. **`06504aa` — refit from banked phasors: the +40.37 % jump is DERIVED, not inferred.** `|gamma_v|` reproduced at both betas via `fit_station_impedance` (`emfit/ports.py:1429`, `gamma_v` `:1517`) and `deembed_reflection` (`:1673`); ratio 1.403674599993487 against observed 1.4036745999934868; `beta_one` rebuilt with `fit_beta(n_wave=1)`  [L, `dispatch_log.md`:19].
4. **`8beb9ae` — housekeeping.** 59 pre-2026-11-04 dispatch rows archived verbatim to `dispatch_log_archive_2026-Q4.md`; DR-24..DR-29 registered at `defect_register.md`:406-500; `_bin_metrics` written into the log's `## Deferred` block [L].
5. **`52986ff` — dispatch_log: DR-19 is OPEN, with its trail in the archive.** Its two 2026-11-03 rows were archived, not resolved (`dispatch_log_archive_2026-Q4.md`:75-76); the defect is intact at `defect_register.md`:302 [L].

## 3. What is open, by name and id

- **DR-19** — graded `s11` (0.326, two-wave B/A at gamma_port) and load-plane `s11_at_plane` (≈0.049) describe incompatible reflections in one artefact; `validation_status` `UNVALIDATED`. **OPEN**, HIGH, opened 2026-11-03 [`defect_register.md`:302]. Archiving its rows is not closing it.
- **DR-24** — `s11.magnitude` (two-wave) and `s11.phase_deg` (one-wave) mis-paired under one key; **OPEN**. Gates AC-3, which grades `|s11|` on `magnitude_one_wave_station_fit` [`:406-422`].
- **DR-25** — de-embed uses `beta_one` against a `beta_two` magnitude; **OPEN**, code half fixed at `emfit/studies.py:3387` [`:422-438`].
- **DR-26** — `s21.deembed_distance_m` records 0.0072 while the operation used the 0.0172 span; **OPEN**, **s21-only** — `s11_distance_and_magnitude_2026-11-04.md` §3 shows there is no s11 case [`:438-453`].
- **DR-27** — s21 `*_basis` strings describe the twin-reference branch the run did not use; **OPEN** [`:454`].
- **DR-28** — `meta.git_rev` is null, so no artefact is tieable to a commit; **OPEN** [`:470`].
- **DR-29** — four `z0` values in one artefact, `summary_line` prints `n/a` for each; **OPEN**, carrying a stale `beta_one` z0 (44.2075 + j0.3794) where `run.station_fit` is 47.3641 + j1.6450 [`:486`; `dispatch_log.md`:19].
- **No DR-30** — the de-embed trace ruled one out by name: no s11 distance defect [L, `753c438`].
- **Deferred, not open.** `_bin_metrics` (`emfit/studies.py:1947`) keeps its own `fit_one` (`:2005`-`:2006`) and de-embeds with it (`:2038`, `:2055`); callers are all under `.scratch/`, so no committed artefact is affected — but "one beta for both de-embeds" is main-record-only until it lands [`dispatch_log.md`:23]. `s11-beta-test-2026-11-04` was **deferred, not cancelled** when the one-line fix superseded it, and is **permanently blocked** regardless: there is no `--ix-port` flag on `run_build_A.py` (`ix_port = n_pml + n_ref = 8`, `:353`) [`dispatch_log.md`:14-15].

## 4. How work is done here

Read the two knowledge files before the first write, not after: `.thoughtmachine/knowledge/personal/lessons_learned.md` (224 lines, 33,686 B, physics/analysis/method since the split) and `lessons_learned_orchestration.md` (1,129 lines, 185,887 B, 109 sections, cluster digest on top) — worker, tooling and orchestration rules. Neither is in git (`.gitignore`:16), so they travel only by being read. The other half is `dispatch_log.md`:27+ — path ownership beats convenience, an unlisted path is not yours, `decisions.md` is single-writer.

## 5. Next dispatches, in priority order

1. **AC-3 re-price after the beta fix.** Read AC-3's bar and graded key in `absorbing_termination_scope.md`; decide which `s11` magnitude the gate reads now that `magnitude_one_wave_station_fit` moved +40.37 % and `s11.magnitude` did not; write the verdict on one artefact. Read-only on `emfit/`, one doc, one row.
2. **Register truth pass (DR-24..DR-29).** One read-only pass over `defect_register.md`:406-500 — DR-25's row states the post-`:3387` code; DR-29's stale z0 annotated as superseded, not quietly replaced; DR-26/27/28 kept OPEN with the writer location named.
3. **Artefact record defects (cheap half of DR-26/27/28).** `s21.deembed_distance_m` records the distance used; `*_basis` describes the branch that ran; `meta.git_rev` is not null. Needs a new artefact, so a host run — `--dry-run` first, cost stated before launch.
4. **`_bin_metrics` beta alignment.** `emfit/studies.py:1947`, own `fit_one` at `:2005`-`:2006`, de-embeds at `:2038`/`:2055`. Off the `build_A` path, testable without a run, retires the last exception to the one-beta claim.
5. **`--ix-port` flag, only if the ix16 differential is ever wanted.** One flag on `evidence/termination/run_build_A.py`, whose `ix_port` is derived at `:353` from an `n_pml` hardcoded at `:298`/`:318`/`:331`. It unblocks the deferred beta test without reviving it — the refit already answered that question, so this is bookkeeping, not evidence.

## 6. Honest state of knowledge

Three things are known worse than §1-§3 make them look.

**(1) The knowledge-base split was asserted, not audited.** `lessons_learned.md`:7 states that "every worker, orchestration and tooling rule was split out" to `lessons_learned_orchestration.md` (109 sections) [L]. That sentence was written **before** the split was performed and **nothing afterwards checked it lesson by lesson**: it is an intention the split was written to satisfy, not a verified partition. It cannot now be checked by diff either — the original was overwritten in place and `.thoughtmachine/` is ignored (`.gitignore`:16), so no pre-split copy exists in this workspace. Treat the split as plausible and unverified; expect stragglers in both files.

**(2) The s11 causal story is supported, not derived.** The modulus jump is reproduced at both betas, but the mechanism usually told with it — `gamma_v` evaluated at the de-embed beta — stays a hypothesis in `s11_refit_from_phasors_2026-11-04`, derived only for the modulus path in `...-04b` [L, `dispatch_log.md`:17, :19]. The phase split (+45.218186068 deg de-embed, 14.546230571 deg `gamma_v`) is arithmetic that matches, not a mechanism shown.

**(3) No number here is tied to a revision.** `meta.git_rev` is null (DR-28), so every figure above is tied to a file on disk, not a commit. A re-run that reproduces them is evidence; re-reading the same file is not.

**The engineer's role, one sentence:** mission keeper and scope defender who does not run tools or read code and who asks "why" until the answer is real — a habit that caught roughly half of this session's mistakes.
