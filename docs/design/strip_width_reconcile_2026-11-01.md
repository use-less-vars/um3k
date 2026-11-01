# Strip width, reconciled: what the mesh contains, what the closed form was told, and what AC-7 graded

**Slug** `strip-width-reconcile-2026-11-01`. **Status: reads only.** No code changed, no run
performed, no artefact re-graded, no gate re-priced, no verdict moved, nothing written under
`emfit/`, `evidence/` or `decisions.md`. Every number below is quoted from a file named beside it,
or is arithmetic over numbers so quoted; the one exception is §5, which is a closed-form solve run
here and labelled as such. `emfit/studies.py`, `emfit/board.py`, `emfit/mode_profile.py`,
`emfit/demos.py`, `emfit/cli.py` line numbers are as they stand in this tree.

---

## 1. The three widths, and which of them agree

Four widths are in play. Two of them are 0.8 mm and two are 3.2 mm.

| # | the width | where it is recorded | value |
|---|---|---|---|
| 1 | the strip the **mesh** contains | `build_A_50ohm.json` `geometry.n_strip` 2.0 x `geometry.cell_m` 0.0004 | **0.8 mm** |
| 2 | the width the **artefact nominates** | `geometry.w` / `run.kwargs` (`Microstrip` closed form, `emfit/studies.py:3129`) | **3.2 mm** |
| 3 | the width the **run's own closed form** was evaluated at | same as 2 — `line.beta_model` 223.3531, `line.z0_model` 48.0987, `eps_eff_model` 3.34394 | **3.2 mm** |
| 4 | the width the **grader's AC-7 reference** was evaluated at | `evidence/termination/grade_2b.py:227`, `w = float(kw["n_strip"]) * cell`; `graded.json` `AC-7.beta_modal.w_m` | **0.8 mm** |

Rows 1 and 4 agree (both the mesh). Rows 2 and 3 agree (both the nomination). **Rows 1 and 2 do
not agree, by a factor of four**, and nothing in the tree says so on the page that carries both:
`build_A_50ohm.json` emits `"w": 0.0032` and `"n_strip": 2.0` eleven keys apart.

The reconciliation is one line of code. `evidence/termination/run_build_A.py:294` sets
`"n_strip": 2` as a bare literal inside the kwargs dict. That literal is the **only** thing in the
entire stack that makes the meshed strip 0.8 mm. The library's default is
`MS_N_STRIP = 8` (`emfit/studies.py:1195-1196`, "#: Cells across the strip width."), and
8 x 0.4 mm = 3.2 mm = `MS_W` (`emfit/studies.py:1158`, "#: Strip width of the default
cross-section [m]; ``w/h = 2``"). Omitting the literal would have produced a consistent 3.2 mm run
in which the mesh, `geometry.w` and the closed form all said the same thing.

## 2. Why the two can diverge at all: where a width becomes a mesh

`emfit/studies.py:2274` `def microstrip_wave(` takes **both** `w: float = MS_W` (`:2277`) and
`n_strip: int = MS_N_STRIP` (`:2282`) as independent keyword parameters. They are not linked by
any assertion:

- The mesh is built from `n_strip` alone: `ny = 2*n_pml + n_strip + n_clean_lo + n_clean_hi`
  (`:2583`) and the strip's y-extent is `j1 = j0 + n_strip` (`:2596`). `w` does not appear.
- The closed form is built from `w` alone: `emfit/studies.py:3129`
  `line = Microstrip(w=float(w), h=float(h), eps_r=float(eps_r), t=COPPER_T)`, with
  `beta_model = float(line.beta(f0))` (`:3131`). `n_strip` does not appear.
- The validation block (`:2544`) bounds `n_strip >= 1` and nothing else; there is no
  `n_strip == round(w/cell)` check anywhere in `microstrip_wave`.
- `check_mesh` (`run_build_A.py:204-228`) reproduces exactly one inequality, `n_top == n_pml`, and
  says so in its own docstring.

So the two widths are two parameters, and a caller that passes both takes responsibility for them
agreeing. Five other places in the library already take that responsibility, and say why:

1. `emfit/mode_profile.py:453-464` derives the cell count from the width — `cell = h/int(n_sub)`
   (`:453`), `n_strip = int(round(w / cell))` (`:458`), and raises when `w` is not a whole number of
   cells (`:459-464`). One source of truth.
2. `emfit/studies.py` `microstrip_wave_board` (:3730-3826) meshes `n_strip=counts["n_strip"]`
   (`:3735`) and hands the closed form the width the mesh contains —
   `strip_cells = int(values.get("strip_cells", MS_N_STRIP))` (`:3777`),
   `board_cell = board_h / MS_N_SUB` (`:3778`), `board_w = strip_cells * board_cell` (`:3779`),
   passed as `w=board_w` at `:3806` and again at `:3820`. The comment at `:3772-3774` is the
   doctrine: *"``w`` on its own does not move the strip — the strip is ``n_strip`` cells wide — so
   the width handed to the closed form below is the width the mesh contains, not a separate wish."*
3. `emfit/board.py` `MicrostripBoard.to_cell_counts` (`:585-650`) converts the board's `w` into
   cells: `cell = self.h / n_sub` (`:613`), the dimension tuple carries
   `("n_strip", self.w, 0, "the strip width")` (`:614-620`), and it returns
   `{"n_strip": int(round(wanted["n_strip"])), …}` (`:644-650`) — "ready to pass to
   `emfit.studies.microstrip_wave`" (`:590-591`). At `h` 1.6 mm / `n_sub` 4 this returns **8**.
4. `emfit/demos.py:36-39` states the same doctrine verbatim, and `:80-85` passes
   `w=int(strip_cells) * cell` beside `n_strip=int(strip_cells)`.
5. `emfit/cli.py:5065-5070` exposes a `strip_cells` parameter, not a width in mm, with the rationale
   *"This is the quantity the simulation actually contains; the width in mm is strip_cells * cell"*.

`evidence/termination/run_build_A.py` is the one caller in the tree that sets both by hand, and it
sets them four factors apart. Its own docstring states the 0.8 mm strip as a given without ever
checking it against the board's `w`: `:234-237` — *"``n_clean`` 96 (0.8 mm strip -> ``n_strip`` 2
cells at that cell)"*. The `ny` formula it quotes at `:256-266` embeds `n_strip = 2`
(`12+2+192`), so the 2-cell strip is in the grid it prices; the width `w` is not.

## 3. The three runs as banked

All three artefacts carry `geometry.w = 0.0032`, `geometry.n_strip = 2.0` and
`geometry.cell_m = 0.0004` — i.e. every one of them meshed an **0.8 mm** strip while recording a
**3.2 mm** width.

| run | argv | grid | cells | peak RSS | wall | `line.beta` | `line.beta_model` | \|s21\| | \|s11\| |
|---|---|---|---|---|---|---|---|---|---|
| A | `--n-line 54 --load-at-mm 20 --load-ohm 50` | 62x206x22 | 280,984 | 297.816 MB | 38.762 s | 251.5242 | 223.3531 | 1.105185 | 0.219615 |
| E | `--n-line 79 --load-at-mm 30 --load-ohm 50` | 87x206x22 | 394,284 | 380.992 MB | 52.195 s | 170.4524 | 223.3531 | 1.013186 | 0.236123 |
| B | `--n-line 54 --load-at-mm 20 --load-ohm 100` | 62x206x22 | 280,984 | 297.461 MB | 40.649 s | 271.0560 | 223.3531 | 1.145042 | 0.351786 |

`beta_model` is **identical to the last digit in all three** (223.35306683909533) because it is a
function of `w`, `h` and `eps_r` only — it never sees `n_strip`, the grid or the load. That
identity is the clearest single piece of evidence that the closed form and the mesh are describing
different objects: three meshes, two loads, two lengths, one closed form.

Verdicts as banked: `AC-3` false in all three (A: `|s11|` 0.219615 against a 1e-3 bar; `||s21|-1|`
0.105185); `AC-5` false ("magnitude half only"); `AC-6` true; `AC-2` true; `AC-1`/`AC-4`/`AC-7` null
in the artefact (AC-7 is graded outside them, in `graded.json`).

## 4. What AC-7 actually graded, and what it would have said at 3.2 mm

`graded.json` `criteria.AC-7`: `pass: true`, `rel_error` 0.0004565049491949793 (**0.0457 %**),
`beta_fdtd_rad_per_m` 216.7621604119496, `beta_modal_rad_per_m` 216.86115860414054, and
`beta_modal.w_m: 0.0008`. The bar is 1.0e-3 (`docs/design/absorbing_termination_scope.md:266-268`).

The same measured `beta_fdtd` against the three admissible references:

| reference | width | beta (rad/m) | rel. error | in units of the 1e-3 bar |
|---|---|---|---|---|
| `emfit.mode_profile` (what AC-7 names) | 0.8 mm | 216.8612 | **-0.0457 %** | 0.46x — **pass** |
| `emfit.mode_profile` | 3.2 mm | 227.3102 | **-4.6404 %** | **46.4x** — fail |
| Hammerstad-Jensen (`line.beta_model`) | 3.2 mm | 223.3531 | **-2.9509 %** | **29.5x** — fail |

**AC-7's pass is a statement about the 0.8 mm strip that was meshed. It is not a statement about
the 3.2 mm board.** The scope bar says "compare against `beta_modal` from `emfit.mode_profile` *on
the same geometry*" (`scope:266-268`), and the grader honours that letter by taking the geometry
from the artefact's own `n_strip` and `cell_m` (`grade_2b.py:224-232`) rather than from
`geometry.w`. Read that way the verdict is correctly computed. But it cannot be quoted as evidence
that this build models a 3.2 mm microstrip: under the width the artefact nominates and the width
its own closed form was given, the *same* phase data misses the bar by 46x — and misses even the
looser 0.1 % reading of it.

`graded.json` already discloses a 2.9 % spread between the two closed forms
(`reference_spread.relative_difference` 0.029065677614499, with the note that AC-7 names
`mode_profile`): *"a verdict that moved by more than the bar between two admissible references is a
property of the reference, not of the phase."* This document's finding is the other half of that
sentence — the two admissible references are not two fits of one cross-section, they are fits of
two cross-sections four times apart, and the width is a free parameter of the call.

## 5. Both widths side by side, solved here (closed form, **not** FDTD)

`emfit.mode_profile.microstrip_mode_profile(h=1.6e-3, w=…, eps_r=4.4, n_sub=4, n_clean=96,
n_air=12)` — the box the runs actually mesh (`n_clean` 96 gives a transverse width of
206 cells x 0.4 mm = 82.4 mm, which is `geometry.width` 0.0824). This is a quasi-static transverse
eigenvalue solve (`emfit/mode_profile.py`); it shares no solver with the FDTD. **Nothing in this
section is a measurement of a run.**

| w | cells | `eps_eff` | `z0` (ohm) | beta @ `f_hz` | beta @ 6.0 GHz | `lambda_g` @ `f_hz` |
|---|---|---|---|---|---|---|
| 0.8 mm | 2 | 3.152375648868 | 85.323399796 | 216.861159 | 223.269499 | 28.9733 mm |
| 3.2 mm | 8 | 3.463476308067 | 47.119454770 | 227.310189 | 234.027302 | 27.6415 mm |
| change (4x width) | 4x | **+9.87 %** | **-44.77 %** (ratio 1.811) | +4.82 % | +4.82 % | -4.60 % |

`f_hz = 5827786408.327286` is the artefact's realised tone, not `f_target` 6.0 GHz: the record
length quantises the tone (`emfit/studies.py:2746`, `f0 = max(1, round(f_target*span))/span`, here
2.87 % below target), and the grader takes its reference at the realised `f_hz`
(`grade_2b.py:230`). Both are given above so neither is quoted for the other.

Checks: the 0.8 mm row reproduces `graded.json`'s AC-7 reference exactly (216.86115860414054 /
3.152375648868031 / 85.32339979583026), which confirms the grader's reference is the call made
here. Hammerstad-Jensen at 3.2 mm (`line.beta_model` 223.3531, `line.z0_model` 48.0987) sits
*between* the two `mode_profile` widths: +2.95 % above the 0.8 mm beta, -1.74 % below the 3.2 mm
one; its `z0_model` is 2.0 % above the 3.2 mm `mode_profile` 47.119.

The practical size of the mistake: a 4x error in width is a **1.81x error in `z0`** (85.32 against
47.12 ohm) and a 9.9 % error in `eps_eff`. The 0.8 mm strip is also only 2 cells wide, i.e. a
staircased PEC sheet whose own discretisation error has never been separated from the physics —
`evidence/strip_width/` exists precisely because 2-cell strips are where that separation is hardest.

## 6. What these runs cannot settle (stated, not graded)

**(a) The run's own `beta` is not a property of the line.** A and B are the same grid, the same
length, the same cut plane; only the load differs (50 against 100 ohm). Their `line.beta` is
251.5242 against 271.0560 rad/m — **+7.77 %**. Across lengths, A against E is **-32.23 %**. The
`line` block the artefact emits (`beta`, `gamma`, `z0`) is one two-wave station fit
(`emfit/studies.py:1433-1464`), and it is load-dependent. The `eps_eff` implied by those betas is
therefore not a width measurement either: 4.240666 (A), 1.947515 (E), 4.924845 (B) — the last
exceeds `eps_r` 4.4, which no quasi-TEM `eps_eff` of this cross-section can do. Only the
*difference* of raw phases across two lengths is usable, and that is what AC-7 used.

**(b) `|s11|` points both ways, so it cannot adjudicate.** Against `|R - Zc| / (R + Zc)`:

| arm | measured \|s11\| | Zc 85.323 (0.8 mm) | Zc 47.119 (3.2 mm) | Zc 48.099 (`line.z0_model`) |
|---|---|---|---|---|
| A, 50 ohm | 0.219615 | 0.261030 (**-15.9 %**) | 0.029660 (+640 %) | 0.019382 (+1033 %) |
| B, 100 ohm | 0.351786 | 0.079195 (+344 %) | 0.359440 (**-2.13 %**) | 0.350451 (**+0.38 %**) |

The 50 ohm arm leans narrow, the 100 ohm arm leans wide. The band that graded B (`graded.json` `exploratory_100ohm.band` `[0.3, 0.37]`) tests the
**measured** magnitude 0.351786, which sits inside the band whatever `Zc` is, so that check does
not discriminate between the widths; the discriminating quantity is `gamma_model`, which the
artefact computes from `Zc` 85.3234 (0.8 mm) and which the same measurement misses by 344 %,
against 0.38-2.13 % from the two 3.2 mm predictions. `exploratory_100ohm` is
`acceptance_criterion: false` under Ruling 3 (`scope:520`), so neither reading is a verdict.
Both arms also carry the same passivity defect: `|s21|` 1.105185 / 1.145042 against the 1.00001
tripwire (AC-5 false), which is exactly the class of energy error that corrupts a reflected
magnitude. The criterion that would settle the width is AC-4's 3 % test on two unmatched loads
(`scope:246-250`) — and it is `achieved: null`, deferred to 2c.

**(c) A third number, from the same run.** The two-wave fit gives `z0_re` 106.976781 and `z0_im`
-11.414184 ohm — `|z0|` 107.6, i.e. 26 % above the 0.8 mm closed form and 128 % above the 3.2 mm
one. Stated so that none of the three impedance readings is promoted to "the" impedance: the run
does not pin down its own `Zc` well enough to pin down its own width.

**Conclusion of this section.** The width question is *open on the evidence banked here*. What is
settled is only the bookkeeping: the mesh contains 0.8 mm, the artefact says 3.2 mm, the run's
closed form was told 3.2 mm, and AC-7 was graded against 0.8 mm.

## 7. Discrepancies found and deliberately not repaired

1. `evidence/termination/README.md` says Run A "closes **AC-3**". It does not:
   `build_A_50ohm.json` `ac["AC-3"].pass` is **false** (`|s11|` 0.219615 against the 1e-3 bar,
   `||s21| - 1|` 0.105185 against the same) and `graded.json` `verdict["AC-3"]` is **false**. The
   README (mtime 02:09) predates the artefacts (03:55, 04:02), so this is a stale claim rather than
   a fabricated one — but it must not be quoted, and it is not repaired here.
2. The same README carries *"no run of this build has ever been recorded (`evidence/termination/`
   holds no `build_A_50ohm.json` and no `build_E_50ohm.json`)"* and prices peak RSS and wall time as
   **"UNMEASURED"**. Both files exist and both measure it: 297.816 MB / 38.762 s (A), 380.992 MB /
   52.195 s (E). The 13.5 MB six-field arithmetic remains correct **as a floor**.
3. `run_build_A.py:268-283` carries the same stale sentence. Not repaired (reads-only dispatch).
4. `docs/design/dispatch_log.md:35` — the `termination-2b-2026-11-01` row — still prices the build
   at *"62 x 206 x 28 = 357,616 cells"*. The achieved grid is **62 x 206 x 22 = 280,984**
   (`geometry.grid`, `geometry.cells`, all three artefacts, all three `.log` files). 357,616 is the
   `n_top = 12` grid and reads **27.3 % high** (280,984 / 357,616 = 0.78566). The correction landed
   in `run_build_A.py:256-266` ("PRICE, corrected 2026-11-01") and in the README, but not in that
   row. **That row is not edited here** — it is outside this dispatch's write scope; the row added
   by this dispatch records the achieved figure instead.
5. `build_A_50ohm.json` `s21.phase_deg_basis` states *"slope in L ~0 BY CONSTRUCTION"* for the
   de-embedded phase. `graded.json` `AC-7.achieved.deembedded_slope_rad_per_m` is **182.510348**,
   against `deembedded_slope_expected_rad_per_m` 0.0 — over the 10 mm A/E pair that is a 1.825 rad
   (**104.6 deg**) residual, not zero. The de-embedded phase is *nearly* flat, not flat. It does
   not affect AC-7, which uses `raw_phase_rad` (`graded.json` `which_phase`), and it is not
   repaired.

## 8. What would reconcile it — proposed, not applied

1. **Cheapest and most faithful:** delete `"n_strip": 2` at `run_build_A.py:294` and let
   `MS_N_STRIP = 8` apply. The mesh then contains the 3.2 mm strip `geometry.w` already claims, and
   `beta_model` / `z0_model` / `eps_eff_model` become closed forms for the geometry actually meshed.
   Price: `ny` 206 -> 212, grid 62 x 212 x 22 = 289,168 cells (**+2.91 %**), `dt` and `nsteps`
   unchanged (the cell is still 0.4 mm), and the AC-7 reference becomes 227.310 rad/m (§5).
2. **Cheapest in physics:** keep `n_strip = 2` and tell the closed form the truth — pass
   `w = n_strip * cell`, as `microstrip_wave_board:3779` and `demos.py:80-85` already do. The
   artefact's `geometry.w` then becomes the width the mesh contains, which is what row 2 of §1 is
   for.
3. **The one that would have prevented this dispatch:** an assertion `n_strip == round(w / cell)`
   in `microstrip_wave`'s validation (`emfit/studies.py:2544` currently checks `n_strip >= 1` and
   nothing more), or routing `run_build_A.py` through `MicrostripBoard.to_cell_counts` /
   `microstrip_wave_board`, which cannot express the inconsistency.

None of the three is applied, and none is authorised by this dispatch.

## 9. Summary

| question | answer |
|---|---|
| What strip width did the runs mesh? | 0.8 mm — 2 cells at 0.4 mm (`geometry.n_strip` 2, `cell_m` 0.0004) |
| What width does the artefact record? | 3.2 mm (`geometry.w`) |
| What width was the run's closed form shown? | 3.2 mm (`studies.py:3129`, `w`) |
| What width was AC-7 graded against? | 0.8 mm (`grade_2b.py:227`, `w = n_strip * cell`) |
| Does AC-7 pass? | Yes — 0.0457 % against the 1e-3 bar, at 0.8 mm |
| Would it pass at 3.2 mm? | No — 4.6404 %, i.e. 46x the bar, against `mode_profile` at 3.2 mm |
| Who caused the 0.8 mm strip? | one literal, `run_build_A.py:294`, `"n_strip": 2`; the default is 8 |
| Is the width question settled by these runs? | No — `line.beta` is load-dependent and `\|s11\|` points both ways (§6); AC-4 is the criterion that would settle it, and it is deferred to 2c |
